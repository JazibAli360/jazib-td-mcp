"""urdu_type TD runtime (copied into the COMP as the Text DAT `urdu_rt`; needs td). Pre-shaped atlas route (T-76).

Text change -> parse (bidi-lite) -> render job -> a CHILD PROCESS (system Python running the COMP's own copy of
urdu_render.py: HarfBuzz hb-view + hb-shape) writes one atlas PNG + metrics JSON into the cache folder -> the
inactive atlas Movie File In TOP gets the new file (a par change only) -> 4 frames later the slots swap together with
the new `words` table + layout, so tiles and boxes never mismatch. Cached atlases apply at once.

TD never makes a Text TOP with an Urdu font and never calls a TOP method (no numpyArray, no evalTextSize, no
cook(force) on a TOP): T-74 + T-76. Per frame only the anim Script CHOP cooks, and only while something moves
(`tick`). Module state is plain data (no functions in storage, T-67); the child process lives in a module global.
Pure ASCII.
"""
import json
import os
import subprocess
import time

C = me.parent()
L = op('urdu_type_logic').module

S = {'ver': 0, 'lay': None, 'held': None, 'aud': None, 'pending': None, 'rows': None, 'atlas': None,
     'want': None, 'staged': None, 'last_anim': None}
PROC = {'p': None, 'akey': None, 't0': 0.0, 'rows': None, 'log': None}

REBUILD_PARS = ('Text', 'Textdat', 'Line', 'Direction', 'Fontrtl', 'Fontfilertl', 'Fontltr', 'Fontfileltr',
                'Fontdigits', 'Typefacertl', 'Weight', 'Size', 'Maxwords', 'Marginem', 'Cachedir', 'Python')
RELAYOUT_PARS = ('Wordgap', 'Linegap', 'Lineh', 'Maxwidth', 'Align', 'Anchorx', 'Anchory', 'Outw', 'Outh', 'Order',
                 'Seed')
DEFAULT_PY = ('/Library/Frameworks/Python.framework/Versions/3.13/bin/python3', '/opt/homebrew/bin/python3',
              '/usr/bin/python3')


def pool():
    return int(C.fetch('jz_pool', 32, search=False))


def schedule(kind='rebuild'):
    """Coalesce: one flush per frame, rebuild wins over relayout."""
    if S['pending'] == 'rebuild':
        return
    first = S['pending'] is None
    S['pending'] = kind
    if first:
        run("op({!r}).module.flush()".format(me.path), delayFrames=1, delayRef=op.TDResources)


def flush():
    k, S['pending'] = S['pending'], None
    if k == 'rebuild':
        rebuild()
    elif k == 'relayout':
        relayout()


def trigger():
    C.store('jz_t0', float(absTime.seconds))
    S['held'] = None
    cook_anim()


def _status(s):
    s = s.encode('ascii', 'replace').decode('ascii')     # the info Text TOP never sees Urdu (T-76)
    try:
        if C.par.Status.eval() != s:
            C.par.Status.val = s
    except Exception:
        pass


def _text_source():
    d = C.par.Textdat.eval()
    rows = []
    if d is not None and getattr(d, 'family', '') == 'DAT':
        if d.isTable:
            rows = [' '.join(c.val for c in r if c.val) for r in d.rows()]
        else:
            rows = d.text.split('\n')
        rows = [r for r in rows if r.strip()]
    txt = C.par.Text.eval().replace('\\n', '\n')
    return L.select_text(txt, rows, C.par.Line.eval())


def _cache():
    d = C.par.Cachedir.eval().strip()
    if not d:                          # the builder stores <repo>/output/urdu_type/cache (any project folder)
        d = C.fetch('jz_cache', '', search=False) or os.path.join(project.folder, '..', 'output', 'urdu_type', 'cache')
    d = os.path.abspath(d)
    os.makedirs(d, exist_ok=True)
    return d


def _python():
    p = C.par.Python.eval().strip()
    if p and os.path.isfile(p):
        return p
    for q in DEFAULT_PY:
        if os.path.isfile(q):
            return q
    return None


def _bin(cache):
    """Write the COMP's own renderer + logic sources next to the cache (self-contained: the COMP carries them)."""
    b = os.path.join(cache, '_bin')
    os.makedirs(b, exist_ok=True)
    for dat, fn in (('urdu_render', 'urdu_render.py'), ('urdu_type_logic', 'urdu_type_logic.py')):
        src = C.op(dat).text
        p = os.path.join(b, fn)
        try:
            with open(p, encoding='utf-8') as f:
                same = f.read() == src
        except Exception:
            same = False
        if not same:
            with open(p + '.tmp', 'w', encoding='utf-8') as f:
                f.write(src)
            os.replace(p + '.tmp', p)
    return os.path.join(b, 'urdu_render.py')


def _fonts():
    f = {'rtl': (C.par.Fontrtl.eval(), C.par.Fontfilertl.eval()), 'ltr': (C.par.Fontltr.eval(), C.par.Fontfileltr.eval())}
    f['digits'] = (C.par.Fontdigits.eval(), '') if C.par.Fontdigits.eval().strip() else f['ltr']
    return f


def rebuild(force=False):
    """Make (or reuse) the atlas for the current text. Never touches a TOP except par values."""
    t0 = time.perf_counter()
    rows = L.parse(_text_source(), C.par.Direction.eval())
    n = min(len(rows), int(C.par.Maxwords.eval()), pool())
    rows = rows[:n]
    me_ = float(C.par.Marginem.eval())
    items = L.render_items(rows, _fonts(), float(C.par.Size.eval()), int(C.par.Weight.eval()),
                           C.par.Typefacertl.eval())
    ver = int(C.fetch('jz_render_version', 2, search=False))
    for it in items:
        it['key'] = L.render_key(it, me_, ver)
    akey = L.atlas_key([it['key'] for it in items]) if items else 'empty'
    cache = _cache()
    jp = os.path.join(cache, 'a_%s.json' % akey)
    if force and os.path.isfile(jp):
        os.remove(jp)
    S['want'] = akey
    C.par.Parsems.val = round((time.perf_counter() - t0) * 1000.0, 2)
    if os.path.isfile(jp):
        _stage(jp, rows, akey)
        return {'words': n, 'atlas': akey, 'cached': True}
    p = PROC['p']
    if p is not None and p.poll() is None:
        p.terminate()                  # a newer text wins; word PNGs already written stay cached
    py = _python()
    if py is None:
        _status('error: no python3 found (set Python)')
        return {'error': 'no python'}
    job = {'cache': cache, 'atlas': akey, 'margin_em': me_, 'items': items}
    jf = os.path.join(cache, 'job_%s.json' % akey)
    with open(jf, 'w', encoding='utf-8') as f:
        json.dump(job, f, ensure_ascii=True)
    log = open(os.path.join(cache, 'render.log'), 'a')
    PROC.update({'p': subprocess.Popen([py, '-I', _bin(cache), jf], stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                       close_fds=True, cwd=cache),
                 'akey': akey, 't0': time.perf_counter(), 'rows': rows, 'log': log})
    _status('rendering {} words'.format(n))
    run("op({!r}).module.poll()".format(me.path), delayFrames=2, delayRef=op.TDResources)
    return {'words': n, 'atlas': akey, 'cached': False}


def poll():
    p = PROC['p']
    if p is None:
        return
    el = time.perf_counter() - PROC['t0']
    if p.poll() is None:
        if el > float(C.par.Timeout.eval()):
            p.kill()
            _status('error: render timed out after {:.0f} s'.format(el))
            PROC['p'] = None
            return
        run("op({!r}).module.poll()".format(me.path), delayFrames=2, delayRef=op.TDResources)
        return
    PROC['p'] = None
    try:
        PROC['log'].close()
    except Exception:
        pass
    akey = PROC['akey']
    cache = _cache()
    jp = os.path.join(cache, 'a_%s.json' % akey)
    C.par.Renderms.val = round(el * 1000.0, 1)
    if akey != S['want']:
        return                         # superseded; the newer job is (or will be) running
    if os.path.isfile(jp):
        _stage(jp, PROC['rows'], akey)
    else:
        ep = os.path.join(cache, 'a_%s.err' % akey)
        msg = open(ep).read()[:120] if os.path.isfile(ep) else 'exit {}'.format(p.returncode)
        _status('error: ' + msg)


def _stage(jp, rows, akey):
    """Point the INACTIVE atlas at the new PNG; swap 4 frames later (the Movie File In loads it meanwhile)."""
    with open(jp, encoding='utf-8') as f:
        atlas = json.load(f)
    slot = 1 - int(C.par.Atlasslot.eval())
    mf = C.op('atlas_a' if slot == 0 else 'atlas_b')
    if mf.par.file.eval() != atlas['atlas']:
        mf.par.file = atlas['atlas']
    S['staged'] = {'atlas': atlas, 'rows': rows, 'slot': slot, 'akey': akey}
    run("op({!r}).module.swap({!r})".format(me.path, akey), delayFrames=4, delayRef=op.TDResources)


def swap(akey):
    st = S['staged']
    if st is None or st['akey'] != akey or akey != S['want']:
        return
    S['staged'] = None
    S['atlas'], S['rows'] = st['atlas'], st['rows']
    ws = L.words_from_atlas(st['rows'], st['atlas'])
    tb = C.op('words')
    cols = ['idx', 'text', 'dir', 'level', 'base', 'script', 'mixed', 'para', 'ok', 'x0', 'y0', 'x1', 'y1', 'w',
            'basey', 'adv', 'lineh', 'ax', 'ay', 'tw', 'th', 'glyphs', 'notdef', 'edge', 'key']
    tb.clear()
    tb.appendRow(cols)
    for w in ws:
        tb.appendRow([round(w[k], 2) if isinstance(w.get(k), float) else w.get(k, '') for k in cols])
    C.par.Atlasslot.val = st['slot']
    C.par.Nwords.val = len(ws)
    C.par.Atlasw.val = int(st['atlas']['w'])
    C.par.Atlash.val = int(st['atlas']['h'])
    bad = sum(1 for w in ws if not w['ok'])
    nd = sum(w['notdef'] for w in ws)
    _status('ok {} words, atlas {}x{}{}{}'.format(len(ws), st['atlas']['w'], st['atlas']['h'],
                                                  ', {} failed'.format(bad) if bad else '',
                                                  ', {} missing glyphs'.format(nd) if nd else ''))
    if C.par.Autotrigger.eval():
        C.store('jz_t0', float(absTime.seconds))
        S['held'] = None
    relayout()


def _read_words():
    tb = C.op('words')
    ws = []
    if tb is None or tb.numRows < 2 or tb[0, 'basey'] is None:
        return ws
    for i in range(1, tb.numRows):
        g = lambda k: tb[i, k].val
        w = {'idx': int(g('idx')), 'text': g('text'), 'para': int(g('para')), 'level': int(g('level')),
             'base': int(g('base')), 'rtl': 1 if g('dir') == 'rtl' else 0}
        for k in ('x0', 'x1', 'y0', 'y1', 'w', 'ax', 'ay', 'tw', 'th'):
            w[k] = float(g(k))
        if g('basey') != '':
            w['basey'] = float(g('basey'))
        ws.append(w)
    return ws


def relayout():
    t0 = time.perf_counter()
    ws = _read_words()
    p = C.par
    outw, outh = int(p.Outw.eval()), int(p.Outh.eval())
    lay = L.layout(ws, size=float(p.Size.eval()), wordgap=float(p.Wordgap.eval()), linegap=float(p.Linegap.eval()),
                   lineh=float(p.Lineh.eval()), maxwidth=float(p.Maxwidth.eval()), align=p.Align.eval(),
                   anchorx=float(p.Anchorx.eval()), anchory=float(p.Anchory.eval()), outw=outw, outh=outh)
    rk = L.ranks(lay['place'], len(ws), p.Order.eval(), int(p.Seed.eval()))
    tb = C.op('layout')
    tb.clear()
    tb.appendRow(['idx', 'text', 'line', 'vis', 'rank', 'x', 'y', 'w', 'h', 'left', 'top', 'right', 'bottom'])
    words = []
    for w in ws:
        pl = lay['place'][w['idx']]
        # shader/CHOP coordinates: TD pixels, y up
        words.append({'cx': pl['cx'], 'cy': outh - pl['cy'], 'bx0': w['x0'], 'by0': w['y0'], 'bx1': w['x1'],
                      'by1': w['y1'], 'rtl': w['rtl'], 'rank': rk[w['idx']], 'ax': w['ax'], 'ay': w['ay'],
                      'tw': w['tw'], 'th': w['th'],
                      'x': (pl['left'] + pl['right']) / 2.0, 'y': outh - (pl['top'] + pl['bottom']) / 2.0,
                      'w': pl['w'], 'h': pl['h']})
        tb.appendRow([w['idx'], w['text'], pl['line'], pl['vis'], rk[w['idx']], round(words[-1]['x'], 1),
                      round(words[-1]['y'], 1), round(pl['w'], 1), round(pl['h'], 1), round(pl['left'], 1),
                      round(pl['top'], 1), round(pl['right'], 1), round(pl['bottom'], 1)])
    S['ver'] += 1
    S['lay'] = words
    p.Nlines.val = lay['lines']
    p.Layoutms.val = round((time.perf_counter() - t0) * 1000.0, 2)
    for nm in ('anim', 'rest'):        # CHOPs only (no TOP is force-cooked)
        o = C.op(nm)
        if o is not None:
            o.cook(force=True)
    return lay['lines']


def _chan(chop, name):
    if chop is None or chop.numChans == 0:
        return None
    c = chop.chan(name)
    return None if c is None else float(c.eval())


def current_progress():
    p = C.par
    timing = p.Timing.eval()
    in2 = C.op('in2')
    elapsed = 0.0
    if timing in ('seconds', 'bpm'):
        elapsed = absTime.seconds - float(C.fetch('jz_t0', 0.0, search=False))
        if elapsed < 0.0:                          # start time stored by another session (a library .tox / a copy
            C.store('jz_t0', float(absTime.seconds))   # from another TD): re-anchor, the copy plays its intro (drop-in)
            elapsed = 0.0
    lvl = _chan(in2, 'level') if timing == 'audio' else None
    if timing == 'audio':
        raw = lvl if lvl is not None else float(p.Audiolevel.eval())
        S['aud'] = L.smooth(S['aud'], raw, float(p.Audiosmooth.eval()))
        level = S['aud']
    else:
        level = 0.0
    pr = L.progress(timing, manual=float(p.Progress.eval()), elapsed=elapsed, seconds=float(p.Seconds.eval()),
                    bpm=float(p.Bpm.eval()), beats=float(p.Beats.eval()), level=level, gain=float(p.Audiogain.eval()),
                    loop=bool(p.Loop.eval()),
                    chan_progress=_chan(in2, 'progress') if timing == 'manual' else None,
                    chan_beat=_chan(in2, 'beat') if timing == 'bpm' else None)
    if p.Hold.eval():
        if S['held'] is None:
            S['held'] = pr
        return S['held']
    S['held'] = None
    return pr


def moving():
    """True while the animation can change by itself (time-based and not finished, looping, audio, or in2 wired)."""
    p = C.par
    if p.Hold.eval():
        return False
    in2 = C.op('in2')
    if in2 is not None and in2.numChans > 0:
        return True
    t = p.Timing.eval()
    if t == 'audio':
        return True
    if t in ('seconds', 'bpm'):
        if p.Loop.eval():
            return True
        el = absTime.seconds - float(C.fetch('jz_t0', 0.0, search=False))
        dur = float(p.Seconds.eval()) if t == 'seconds' else float(p.Beats.eval()) * 60.0 / max(float(p.Bpm.eval()), 1e-6)
        return el <= dur + 0.1
    return False


def cook_anim():
    o = C.op('anim')
    if o is not None:
        o.cook(force=True)


def tick():
    """Execute DAT frame start: cook the anim CHOP only while something moves (idle text = no cooks)."""
    if C.allowCooking and S['lay'] is not None and moving():
        cook_anim()
    elif S['lay'] is None and C.op('words') is not None and C.op('words').numRows > 1:
        relayout()


def anim_cook(sop):
    """Script CHOP: one sample per pool slot, one channel per field (L.FIELDS) -> params texture row."""
    words = S['lay'] or []
    P = pool()
    p = C.par
    n = len(words)
    pr = current_progress()
    mode = p.Mode.eval()
    cols = {f: [0.0] * P for f in L.FIELDS}
    kw = dict(mode=mode, stagger=float(p.Stagger.eval()), ease_kind=p.Ease.eval(), slidex=float(p.Slidex.eval()),
              slidey=float(p.Slidey.eval()), scalefrom=float(p.Scalefrom.eval()), blurmax=float(p.Blurmax.eval()),
              pulseamt=float(p.Pulseamt.eval()))
    for i, w in enumerate(words[:P]):
        a = L.anim(w['rank'], n, pr, **kw)
        for f in ('cx', 'cy', 'bx0', 'by0', 'bx1', 'by1', 'rtl', 'ax', 'ay', 'tw', 'th'):
            cols[f][i] = w[f]
        for f in ('tx', 'ty', 'sx', 'sy', 'rot', 'alpha', 'reveal', 'blur'):
            cols[f][i] = a[f]
        cols['live'][i] = 1.0 if w['tw'] > 0 else 0.0
    cols['progress'] = [pr] * P
    sop.clear()
    sop.numSamples = P
    for f in L.FIELDS:
        sop.appendChan(f).vals = cols[f]
    return


def rest_cook(sop):
    """Script CHOP out_rest: x{i} y{i} w{i} h{i} rank{i} (TD pixels, y up; box centre)."""
    words = S['lay'] or []
    sop.clear()
    sop.numSamples = 1
    for i, w in enumerate(words):
        for k in ('x', 'y', 'w', 'h', 'rank'):
            sop.appendChan('{}{}'.format(k, i)).vals = [float(w[k])]
    return


def info_text():
    p = C.par
    return 'words {}  lines {}  render {} ms  layout {} ms  {}'.format(int(p.Nwords.eval()), int(p.Nlines.eval()),
                                                                      p.Renderms.eval(), p.Layoutms.eval(),
                                                                      p.Status.eval())
