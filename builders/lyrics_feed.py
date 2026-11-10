# lyrics_feed builder - LY_lyrics_feed: synced lyrics from local .lrc files, clocked by the Spotify desktop app
# (osascript, background thread), a manual clock or a CHOP clock. Outputs current / next line + progress.
# Spec: docs/research/AS_spotifybridge_lyrics.md section 7 (local-only alternative; our own clean-room design).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/lyrics_feed.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set; custom par values kept; zkit panel refreshed in place.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy); the COMP's controls_window is closed before a rebuild
# (zkit reopens it if it was open); the panel container is never destroyed; the network pane is never moved here.
# No Python functions in op storage (T-67): state lives in DAT module dicts. ASCII only (Urdu only in .lrc files).
import os

NAME = 'LY_lyrics_feed'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = os.path.join(REPO, 'builders')
LOGIC_FILE = os.path.join(HERE, 'lyrics_feed_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
DEMO_FOLDER = os.path.join(REPO, 'test', 'fixtures', 'lyrics')

POLLER = r'''# poller: Spotify desktop now-playing via osascript in a background thread (never on the cook thread).
# The thread touches no TD op: it runs osascript, parses with plain functions handed in at start, and stores the
# result here under a lock. engine (Script CHOP) calls ensure() every cook = heartbeat; no heartbeat for 3 s
# (COMP parked, deleted, Source = manual) -> the thread ends by itself. First call waits up to 60 s, so macOS can
# show its one-time Automation prompt ("TouchDesigner wants to control Spotify").
# The control dict lives in a process-wide registry keyed by this COMP's path, not in module globals: TD rebuilds a
# DAT's .module when the DAT is cooked again (text set, force-cook from td_errors), and a fresh module would start
# a second thread while the first one still waits on osascript.
import sys
import types
import threading
import subprocess
import time

_REG = sys.modules.setdefault('jz_lyrics_feed_registry', types.ModuleType('jz_lyrics_feed_registry'))
S = _REG.__dict__.setdefault(me.parent().path + ':poll', {})
for _k, _v in (('lock', threading.Lock()), ('want', False), ('hz', 4.0), ('beat', 0.0), ('thread', None),
               ('latest', None), ('fresh', None), ('calls', 0), ('first', True), ('gen', 0)):
    S.setdefault(_k, _v)


def _loop(gen, script, parse):
    while True:
        with S['lock']:
            mine = S['thread'] is threading.current_thread() and gen == S['gen']
            if not mine or not S['want'] or time.perf_counter() - S['beat'] > 3.0:
                if mine:
                    S['thread'] = None
                return
            hz = max(0.2, float(S['hz']))
            tmo = 60.0 if S['first'] else 2.0
        t0 = time.perf_counter()
        try:
            # close_fds=False lets CPython use posix_spawn on macOS: the default fork() of the whole TD process
            # stalled TD's frame ~120 ms per poll (T-228).
            r = subprocess.run(['/usr/bin/osascript', '-e', script], capture_output=True, timeout=tmo, close_fds=False)
            rc, out, err = r.returncode, r.stdout.decode('utf-8', 'replace'), r.stderr.decode('utf-8', 'replace')
        except subprocess.TimeoutExpired:
            rc, out, err = 1, '', 'osascript timeout'
        except Exception as e:          # keep the thread alive on any OS error
            rc, out, err = 1, '', repr(e)
        t1 = time.perf_counter()
        d = parse(rc, out, err)
        d['stamp'] = 0.5 * (t0 + t1)
        d['ms'] = (t1 - t0) * 1000.0
        with S['lock']:
            if S['thread'] is not threading.current_thread():
                return                       # replaced while osascript ran: drop the reply, end
            S['latest'] = d
            S['fresh'] = d
            S['calls'] += 1
            if rc == 0 or d['state'] == 'noperm':   # a real answer: the Automation prompt is behind us
                S['first'] = False
        time.sleep(max(0.02, 1.0 / hz - (t1 - t0)))


def ensure(want, hz, script, parse):
    with S['lock']:
        S['want'] = bool(want)
        S['hz'] = hz
        S['beat'] = time.perf_counter()
        th = S['thread']
        if want and (th is None or not th.is_alive()):
            S['gen'] += 1
            th = threading.Thread(target=_loop, args=(S['gen'], script, parse), name='LY_lyrics_feed poll', daemon=True)
            S['thread'] = th
            th.start()


def take():
    """The newest poll since the last take (or None), and the latest poll."""
    with S['lock']:
        f = S['fresh']
        S['fresh'] = None
        return f, S['latest']


def stop():
    with S['lock']:
        S['want'] = False
        S['gen'] += 1
        S['thread'] = None


def stats():
    with S['lock']:
        th = S['thread']
        return {'alive': bool(th is not None and th.is_alive()), 'calls': S['calls'], 'latest': S['latest']}
'''

ENGINE_CB = r'''# engine: once per frame (ly_tick cooks it). Picks the clock (spotify / manual / chop), finds and parses the .lrc,
# looks up the line (ly_logic, tested offline) and writes channels; the DATs are rewritten only when they change.
# State lives in this module (plain dicts), not in op storage.
import os
import time

import sys
import types

# Process-wide, keyed by the COMP path (plain data): survives TD rebuilding this DAT's module (force-cook), so the
# manual clock and the loaded file do not jump back. Never op storage (T-67).
_REG = sys.modules.setdefault('jz_lyrics_feed_registry', types.ModuleType('jz_lyrics_feed_registry'))
STATE = _REG.__dict__.setdefault(me.parent().path + ':engine', {})
for _k, _v in (('ev', []), ('mclock', None), ('sclock', None), ('index', None), ('folder', None), ('files', []),
               ('path', None), ('doc', None), ('sig', None), ('track', None), ('idx', -2), ('resyncs', 0),
               ('rescan', False), ('reload', False)):
    STATE.setdefault(_k, _v)
STATE['sig'] = None          # rewrite the DATs once after a (re)build


def push(e):
    STATE['ev'].append(e)


def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return


def _read(path):
    with open(path, 'rb') as f:
        return f.read()


def _scan(L, folder):
    files, entries = [], []
    if folder and os.path.isdir(folder):
        for n in sorted(os.listdir(folder)):
            if n.lower().endswith('.lrc') and not n.startswith('.'):
                p = os.path.join(folder, n)
                files.append(p)
                try:
                    entries.append((p, L.parse_lrc(_read(p))['tags']))
                except OSError:
                    entries.append((p, {}))
    STATE['files'] = files
    STATE['index'] = L.build_index(entries)
    STATE['folder'] = folder


def _load(L, path):
    STATE['path'] = path
    STATE['doc'] = None
    if path:
        try:
            STATE['doc'] = L.parse_lrc(_read(path))
        except OSError:
            STATE['doc'] = None
    t = op('lrc_table')
    if t is None:                       # first cook during a build, before the table exists
        STATE['path'] = None
        return
    t.clear()
    t.appendRow(['idx', 'time', 'line'])
    for k, (tm, s) in enumerate((STATE['doc'] or {}).get('lines', [])):
        t.appendRow([k, '%.3f' % tm, s])


def onCook(scriptOp):
    L = op('ly_logic').module
    PL = op('poller').module
    P = parent()
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    now = time.perf_counter()
    mode = P.par.Source.eval()
    want = mode in ('auto', 'spotify')
    PL.ensure(want, P.par.Pollhz.eval(), L.APPLESCRIPT, L.parse_now_playing)
    fresh, latest = PL.take() if want else (None, None)
    chop = scriptOp.inputs[0] if scriptOp.inputs else None
    chop_ok = chop is not None and chop.numChans > 0
    src = L.pick_source(mode, latest, chop_ok)

    ev, STATE['ev'] = STATE['ev'], []
    if any(e[0] == 'rescan' for e in ev):
        STATE['rescan'] = True
    if any(e[0] == 'reload' for e in ev):
        STATE['reload'] = True
    folder = P.par.Folder.eval()
    if STATE['index'] is None or folder != STATE['folder'] or STATE['rescan']:
        _scan(L, folder)
        STATE['rescan'] = False
        STATE['reload'] = True

    forced = P.par.Lrcfile.eval().strip()
    title = artist = tid = ''
    if src == 'spotify' and latest is not None:
        title, artist, tid = latest.get('title', ''), latest.get('artist', ''), latest.get('id', '')
        track = (tid, title, artist)
        if track != STATE['track']:
            STATE['track'] = track
            path = forced or L.find_lrc(STATE['index'], tid, artist, title)
            if path is None and not forced:          # maybe the file was added since the last scan
                _scan(L, folder)
                path = L.find_lrc(STATE['index'], tid, artist, title)
            STATE['want_path'] = path
        path = forced or STATE.get('want_path')
    else:
        STATE['track'] = None
        path = forced or (STATE['files'][0] if STATE['files'] else None)
    if path != STATE['path'] or STATE['reload']:
        _load(L, path)
        STATE['reload'] = False
    doc = STATE['doc'] or {'lines': [], 'tags': {}}
    lines = doc['lines']
    flen = L.song_length(doc)

    mev = [e for e in ev if e[0] in ('seek', 'restart')]
    mlen = flen if flen > 0 else 0.0
    STATE['mclock'], mpos = L.clock_manual(STATE['mclock'], now, bool(P.par.Play.eval()), P.par.Rate.eval(),
                                          mlen, bool(P.par.Loop.eval()), mev)
    if src == 'spotify':
        STATE['sclock'], pos, rs = L.clock_spotify(STATE['sclock'], now, fresh, P.par.Drift.eval())
        STATE['resyncs'] += 1 if rs else 0
        playing = 1.0 if STATE['sclock']['playing'] else 0.0
        length = latest.get('dur', 0.0) if latest else 0.0
        length = length or flen
    elif src == 'chop':
        cn = P.par.Chopchan.eval().strip()
        ch = chop[cn] if (cn and chop[cn] is not None) else chop[0]
        pos = float(ch[0]) if ch is not None else 0.0
        playing, length = 1.0, flen
    else:
        pos, playing, length = mpos, (1.0 if P.par.Play.eval() else 0.0), flen
    eff = pos + P.par.Offset.eval()
    s = L.line_state(lines, eff, length)

    ps = (latest or {}).get('state', '') if want else ''
    if not path:
        status = ('no lyrics for %s - %s' % (artist, title)) if src == 'spotify' else 'no .lrc file (Folder / Lrcfile)'
    elif STATE['doc'] is None:
        status = 'cannot read ' + os.path.basename(path)
    else:
        status = '%s: %s' % (src, os.path.basename(path))
    if want and ps in ('noperm', 'error', 'notrunning', 'stopped') and src != 'spotify':
        status += ' | spotify ' + ps
    elif mode == 'spotify' and latest is None:
        status = 'spotify: waiting for the first poll'

    changed = 1.0 if s['idx'] != STATE['idx'] else 0.0
    STATE['idx'] = s['idx']
    sig = (s['idx'], s['cur'], s['next'], s['prev'], path, src, status, title, artist, tid)
    if sig != STATE['sig']:
        STATE['sig'] = sig
        t = op('lyrics_info')
        if t is None or op('cur_line') is None or op('next_line') is None:
            STATE['sig'] = None
            return
        t.clear()
        rows = [('key', 'value'), ('cur', s['cur']), ('next', s['next']), ('prev', s['prev']),
                ('cur_rtl', int(L.is_rtl(s['cur']))), ('next_rtl', int(L.is_rtl(s['next']))),
                ('idx', s['idx']), ('count', s['count']), ('source', src), ('status', status),
                ('title', title or doc['tags'].get('ti', '')), ('artist', artist or doc['tags'].get('ar', '')),
                ('track_id', tid), ('lrc_file', path or ''), ('poll_state', ps),
                ('poll_error', ((latest or {}).get('error', '') if want else ''))]
        for r in rows:
            t.appendRow(list(r))
        if op('cur_line').text != s['cur']:
            op('cur_line').text = s['cur']
        if op('next_line').text != s['next']:
            op('next_line').text = s['next']

    scriptOp.clear()
    scriptOp.numSamples = 1
    vals = (('pos', eff), ('length', length), ('playing', playing), ('line_idx', s['idx']),
            ('line_count', s['count']), ('line_progress', s['line_progress']), ('next_in', s['next_in']),
            ('song_progress', s['song_progress']), ('line_start', s['line_start']), ('line_changed', changed),
            ('has_lyrics', 1.0 if lines else 0.0), ('source', {'manual': 0, 'spotify': 1, 'chop': 2}[src]),
            ('poll_ms', float((latest or {}).get('ms', 0.0)) if want else 0.0), ('resyncs', STATE['resyncs']))
    for n, v in vals:
        scriptOp.appendChan(n)[0] = float(v)
    return
'''

PULSES = """# ly_pulses: Rescan / Reload / Seek / Restart -> engine (applied on its next cook).
def onPulse(par):
    eng = parent().op('engine_callbacks').module
    n = par.name
    if n == 'Rescan':
        eng.push(('rescan',))
    elif n == 'Reload':
        eng.push(('reload',))
    elif n == 'Seek':
        eng.push(('seek', parent().par.Seekto.eval()))
    elif n == 'Restart':
        eng.push(('restart',))
    return
"""

TICK = """# ly_tick: cook the engine every frame, so the DAT/CHOP outputs stay live even when only out3 (DAT) is read.
N = [0]

def onFrameStart(frame):
    N[0] += 1
    e = parent().op('engine')
    if e is not None:
        e.cook(force=True)   # plain cook() ran on ~45% of frames when nothing downstream was viewed (31550)
    return
"""

P_EXPR = "parent().par.{}.eval()"
INFO = "op('lyrics_info')['{}', 1].val"

PAGES = [
    ('Source', [
        ('Source', 'Menu', 'auto', {'names': ['auto', 'spotify', 'manual', 'chop'],
                                    'labels': ['Auto', 'Spotify app', 'Manual clock', 'CHOP clock (in1)']}),
        ('Folder', 'Folder', DEMO_FOLDER, {'label': 'LRC folder'}),
        ('Lrcfile', 'File', '', {'label': 'Force .lrc (blank = match)'}),
        ('Offset', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Offset s (+ = earlier)'}),
        ('Pollhz', 'Float', 4.0, {'min': 0.5, 'max': 10, 'label': 'Spotify polls / s'}),
        ('Drift', 'Float', 0.3, {'min': 0.05, 'max': 2, 'label': 'Resync above s'}),
        ('Chopchan', 'Str', 'pos', {'label': 'CHOP channel (s)'}),
        ('Rescan', 'Pulse', None, {'label': 'Rescan folder'}),
        ('Reload', 'Pulse', None, {'label': 'Reload file'}),
    ]),
    ('Manual', [
        ('Play', 'Toggle', True, {'label': 'Play'}),
        ('Rate', 'Float', 1.0, {'min': -2, 'max': 4, 'label': 'Rate'}),
        ('Loop', 'Toggle', True, {'label': 'Loop'}),
        ('Seekto', 'Float', 0.0, {'min': 0, 'max': 300, 'label': 'Seek to s'}),
        ('Seek', 'Pulse', None, {'label': 'Seek'}),
        ('Restart', 'Pulse', None, {'label': 'Restart'}),
    ]),
    ('Look', [
        ('Resw', 'Int', 1080, {'min': 16, 'max': 4096, 'label': 'Width'}),
        ('Resh', 'Int', 1920, {'min': 16, 'max': 4096, 'label': 'Height'}),
        ('Font', 'Str', 'Open Sans', {'label': 'Font (Latin)'}),
        ('Urdufont', 'Str', 'Noto Nastaliq Urdu', {'label': 'Font (Urdu / RTL)'}),
        ('Textmethod', 'Menu', 'auto', {'names': ['auto', 'bitmap', 'automatic', 'polygon', 'scalable'],
                                        'labels': ['Auto (bitmap for Urdu)', 'Bitmap', 'TD automatic', 'Polygon', 'Scalable']}),
        ('Cursize', 'Float', 96.0, {'min': 8, 'max': 400, 'label': 'Line px'}),
        ('Nextsize', 'Float', 54.0, {'min': 8, 'max': 300, 'label': 'Next line px'}),
        ('Margin', 'Float', 80.0, {'min': 0, 'max': 400, 'label': 'Side margin px'}),
        ('Gap', 'Float', 140.0, {'min': 0, 'max': 800, 'label': 'Line gap px'}),
        ('Shownext', 'Toggle', True, {'label': 'Show next line'}),
        ('Showbar', 'Toggle', True, {'label': 'Line progress bar'}),
        ('Barh', 'Float', 8.0, {'min': 1, 'max': 64, 'label': 'Bar px'}),
        ('Transparent', 'Toggle', False, {'label': 'Transparent bg'}),
    ]),
    ('Colours', [
        ('Curcolour', 'RGB', (1.0, 1.0, 1.0), {'label': 'Line'}),
        ('Nextcolour', 'RGB', (0.55, 0.55, 0.6), {'label': 'Next line'}),
        ('Barcolour', 'RGB', (0.95, 0.75, 0.2), {'label': 'Bar'}),
        ('Bg', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background'}),
    ]),
]

PANEL_PAGES = ['Source', 'Manual', 'Look', 'Colours']


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None or (style == 'RGB' and getattr(c.par, name + 'r', None) is not None):
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
                p.default = default
                p.val = default
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']   # slider range only: no clamps (no limits)
                p.default = default
                p.val = default
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
                p.clampMin, p.min = True, 1
                p.default = default
                p.val = default
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style in ('Str', 'File', 'Folder'):
                p = {'Str': page.appendStr, 'File': page.appendFile, 'Folder': page.appendFolder}[style](name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'RGB':
                for p, v in zip(page.appendRGB(name, label=label), default):
                    p.default = v
                    p.val = v


def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _close_window(c):
    w = c.op('controls_window')
    if w is not None and w.OPType == 'windowCOMP' and w.isOpen:
        w.par.winclose.pulse()
        return True
    return False


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = True
    return o


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _menu(par, *names):
    """Set the first menu entry that exists (menu names differ between builds)."""
    for n in names:
        if n in par.menuNames:
            par.val = n
            return n
    return None


def _const(par, v):
    par.mode = ParMode.CONSTANT
    par.val = v


def _text_top(c, name, size_par, col_par, rtl, text_dat, ypos_expr, show_expr=None):
    """One Text TOP with a FIXED script role (rtl True = Urdufont + righttoleft + bitmap at Textmethod auto).
    Its font / method / direction never flip at a line change (T-228): a bitmap face nobody holds is freed and
    reloaded at ~130-400 ms on its next use, so each slot keeps one Latin and one Urdu Text TOP and a Switch picks."""
    t = _mk(c, textTOP, name)
    t.par.outputresolution = 'custom'
    _expr(t.par.resolutionw, P_EXPR.format('Resw'))
    _expr(t.par.resolutionh, P_EXPR.format('Resh'))
    t.par.format = 'rgba8fixed'
    body = "op('{}').text".format(text_dat)
    _expr(t.par.text, body if show_expr is None else "({} if {} else '')".format(body, show_expr))
    _expr(t.par.font, P_EXPR.format('Urdufont' if rtl else 'Font'))
    _const(t.par.readingdirection, 'righttoleft' if rtl else 'lefttoright')
    # 31550: dispmethod automatic/polygon/scalable draws Arabic-script letters unjoined (isolated forms) at large
    # sizes; bitmap shapes Urdu correctly (Nastaliq + Geeza Pro, live check). Textmethod auto = bitmap for RTL lines.
    _expr(t.par.dispmethod, "('{}' if parent().par.Textmethod.eval() == 'auto' else parent().par.Textmethod.eval())"
                            .format('bitmap' if rtl else 'automatic'))
    t.par.wordwrap = True
    _menu(t.par.fontsizexunit, 'pixels')
    _expr(t.par.fontsizex, P_EXPR.format(size_par))
    t.par.keepfontratio = True
    t.par.alignx, t.par.aligny = 'center', 'center'
    _menu(t.par.positionunit, 'pixels')
    _expr(t.par.positiony, ypos_expr)
    _expr(t.par.borderspace1, P_EXPR.format('Margin'))
    _expr(t.par.borderspace2, P_EXPR.format('Margin'))
    for ch in 'rgb':
        _expr(getattr(t.par, 'fontcolor' + ch), P_EXPR.format(col_par + ch))
    t.par.bgalpha = 0
    return t


def _text_slot(c, name, size_par, col_par, rtl_key, text_dat, ypos_expr, show_expr=None):
    """name (Latin Text TOP) + name_ur (Urdu Text TOP) -> sel_<slot> Switch TOP (index = the line's cur_rtl/next_rtl).
    The unselected Text TOP is not pulled, so it does not cook; same pars per role as the old single TOP = same pixels."""
    lat = _text_top(c, name, size_par, col_par, False, text_dat, ypos_expr, show_expr)
    ur = _text_top(c, name + '_ur', size_par, col_par, True, text_dat, ypos_expr, show_expr)
    sw = _mk(c, switchTOP, 'sel_' + name.split('_', 1)[1])
    sw.inputConnectors[0].connect(lat)
    sw.inputConnectors[1].connect(ur)
    _expr(sw.par.index, "(1 if " + INFO.format(rtl_key) + " == '1' else 0)")
    sw.comment = ('Picks {0} (Latin) or {0}_ur (Urdu) by {1}; fonts never switch on a Text TOP (T-228).'
                  .format(name, rtl_key))
    return sw


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('LY_lyrics_feed: synced lyrics from local .lrc files (UTF-8, Urdu OK). Clock: Spotify desktop app '
                 '(osascript in a thread, interpolated), manual clock, or a CHOP (in1, seconds). Out: out1 TOP preview, '
                 'out2 CHOP (pos line_idx line_progress next_in ...), out3 DAT (cur next prev status ...). '
                 'Pulse Opencontrols.')
    _close_window(c)
    _pars(c, PAGES)
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)

    # 1 Clock in
    in1 = _mk(c, inCHOP, 'in1')
    in1.comment = 'Optional CHOP clock: song position in seconds (channel Chopchan, else the first). Source = chop/auto.'
    lg = _mk(c, textDAT, 'ly_logic')
    lg.text = open(LOGIC_FILE, encoding='utf-8').read()
    lg.comment = 'Pure logic (copy of builders/lyrics_feed_logic.py; tests in test/test_lyrics_feed.py).'
    pl = _mk(c, textDAT, 'poller')
    pl.text = POLLER
    pl.comment = 'Spotify desktop now-playing: osascript in a background thread, ~Pollhz, no TD ops touched there.'

    # 3 Lyrics data (written by the engine on change only)
    lrc = _mk(c, tableDAT, 'lrc_table')
    lrc.comment = 'Parsed lines of the current .lrc: idx, time (s, after the [offset:] tag), line.'
    info = _mk(c, tableDAT, 'lyrics_info')
    info.comment = 'key/value: cur next prev cur_rtl next_rtl idx count source status title artist track_id lrc_file poll_state poll_error.'
    if info.numRows < 2:
        info.clear()
        info.appendRows([['key', 'value'], ['cur', ''], ['next', ''], ['prev', ''], ['cur_rtl', '0'], ['next_rtl', '0']])
    cur = _mk(c, textDAT, 'cur_line')
    nxt = _mk(c, textDAT, 'next_line')
    # 2 Engine
    eng = _mk(c, scriptCHOP, 'engine')
    eng.inputConnectors[0].connect(in1)
    cb = eng.par.callbacks.eval()
    cb.text = ENGINE_CB
    if cb.name != 'engine_callbacks':
        cb.name = 'engine_callbacks'
    eng.par.callbacks = 'engine_callbacks'
    eng.par.setuppars.pulse()
    tick = _mk(c, executeDAT, 'ly_tick')
    tick.text = TICK
    tick.par.framestart = True
    tick.par.active = True
    pulses = _mk(c, parameterexecuteDAT, 'ly_pulses')
    pulses.text = PULSES
    pulses.par.op = c
    pulses.par.pars = 'Rescan Reload Seek Restart'
    pulses.par.custom = True
    pulses.par.builtin = False
    pulses.par.valuechange = False
    pulses.par.onpulse = True

    out3 = _mk(c, outDAT, 'out3')
    out3.inputConnectors[0].connect(info)
    feed = _mk(c, nullCHOP, 'feed')
    feed.inputConnectors[0].connect(eng)
    out2 = _mk(c, outCHOP, 'out2')
    out2.inputConnectors[0].connect(feed)

    # 4 Preview picture
    bg = _mk(c, constantTOP, 'bg')
    bg.par.outputresolution = 'custom'
    _expr(bg.par.resolutionw, P_EXPR.format('Resw'))
    _expr(bg.par.resolutionh, P_EXPR.format('Resh'))
    bg.par.format = 'rgba8fixed'
    for ch in 'rgb':
        _expr(getattr(bg.par, 'color' + ch), P_EXPR.format('Bg' + ch))
    _expr(bg.par.alpha, "0 if parent().par.Transparent.eval() else 1")
    bar = _mk(c, rectangleTOP, 'bar')
    bar.par.outputresolution = 'custom'
    _expr(bar.par.resolutionw, P_EXPR.format('Resw'))
    _expr(bar.par.resolutionh, P_EXPR.format('Resh'))
    bar.par.format = 'rgba8fixed'
    _menu(bar.par.sizeunit, 'pixels')
    _menu(bar.par.centerunit, 'pixels')
    bar.par.justifyh = 'center'               # 31550: 'left' puts the rect LEFT of the centre point (live check)
    _expr(bar.par.sizex, "max(0.0, (parent().par.Resw.eval() - 2 * parent().par.Margin.eval()) * op('feed')['line_progress'][0]) "
                         "* (1 if parent().par.Showbar.eval() else 0)")
    _expr(bar.par.sizey, P_EXPR.format('Barh'))
    _expr(bar.par.centerx, "-(parent().par.Resw.eval() / 2.0 - parent().par.Margin.eval()) + me.par.sizex.eval() / 2.0")
    _expr(bar.par.centery, "-parent().par.Gap.eval() * 0.5")
    for ch in 'rgb':
        _expr(getattr(bar.par, 'fillcolor' + ch), P_EXPR.format('Barcolour' + ch))
    bar.par.bgalpha = 0
    tcur = _text_slot(c, 'txt_cur', 'Cursize', 'Curcolour', 'cur_rtl', 'cur_line',
                      "parent().par.Gap.eval() * 0.5 + parent().par.Cursize.eval() * 0.6")
    tnext = _text_slot(c, 'txt_next', 'Nextsize', 'Nextcolour', 'next_rtl', 'next_line',
                       "-(parent().par.Gap.eval() * 0.5 + parent().par.Nextsize.eval() * 1.2)",
                       show_expr='parent().par.Shownext.eval()')
    o1 = _mk(c, overTOP, 'over_next')
    o1.inputConnectors[0].connect(tnext)
    o1.inputConnectors[1].connect(bar)
    o2 = _mk(c, overTOP, 'over_cur')
    o2.inputConnectors[0].connect(tcur)
    o2.inputConnectors[1].connect(o1)
    o3 = _mk(c, overTOP, 'over_bg')
    o3.inputConnectors[0].connect(o2)
    o3.inputConnectors[1].connect(bg)
    out1 = _mk(c, outTOP, 'out1')
    out1.inputConnectors[0].connect(o3)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    info_ = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info_ = ns['build_controls'](c.path, pages=PANEL_PAGES, d=56, cols=8)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'ly_pulses'],
         'body': 'zkit panel + window (pulse Opencontrols); ly_pulses: Rescan / Reload / Seek / Restart -> engine.'},
        {'title': '1 Clock in', 'role': 'input', 'ops': ['in1', 'ly_logic', 'poller'],
         'body': 'Spotify desktop (poller: osascript thread, ~4 Hz), manual clock, or in1 CHOP seconds. Logic in ly_logic.'},
        {'title': '2 Engine', 'role': 'process', 'ops': ['engine', 'engine_callbacks', 'ly_tick', 'feed', 'out2'],
         'body': 'Per frame: pick clock, interpolate, find + parse .lrc, look up the line. out2 = pos line_idx line_progress next_in ...'},
        {'title': '3 Lyrics data', 'role': 'output', 'ops': ['lrc_table', 'lyrics_info', 'cur_line', 'next_line', 'out3'],
         'body': 'Rewritten on change only. out3 = lyrics_info (cur next prev status ...). cur_line / next_line feed Text TOPs.'},
        {'title': '4 Preview', 'role': 'output', 'ops': ['bg', 'bar', 'txt_cur', 'txt_cur_ur', 'sel_cur', 'txt_next',
                                                         'txt_next_ur', 'sel_next', 'over_next', 'over_cur', 'over_bg', 'out1'],
         'body': 'Per line slot a Latin and an Urdu Text TOP (fixed fonts, Urdu = Urdufont + right-to-left) and a Switch; '
                 'line progress bar, bg. out1 = preview picture.'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    return {'comp': c.path, 'panel': info_, 'layout': str(lay)[:400]}
