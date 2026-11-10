"""zkit builder: zerror-style controls panel (knobs, presets, morph, randomise) for ANY COMP's custom parameters.

Clean-room, our own code (spec docs/research/BE_rudiment_zerror.md sections 6 + 7.0). Run inside TD 2025.31550
through td_exec:
    ns = dict(globals()); exec(open('<repo>/builders/zkit.py').read(), ns)
    ns['build_controls']('/project1/lab/SOME_COMP')            # panel for that COMP's custom pages
    ns['build_demo']('/project1/lab')                          # demo COMP ZK_controls_kit
build_controls(comp_path, pages=None, exclude=(), d=56, cols=8, panel_name='controls', open_window=False)
  * adds a 'Zkit' page to the COMP once (Opencontrols, Zktheme, Zkd, Zkcols, Zkrandamount, Zkrandomize, Zkshowall,
    Zkrebuild); existing values are kept,
  * makes/refreshes <comp>/<panel_name> (Container COMP, the panel) + <comp>/controls_window (Window COMP),
  * idempotent: ops reused by name; zk_props / zk_presets / zk_cfg collapse state survive a rebuild.
T-70 safe: the COMP's own controls_window is closed first; the panel container is never destroyed (its contents are
updated in place; only stray non-zk children of an older panel go, via safe_destroy, with the window closed); the
network pane is never moved here. No Python functions in op storage (T-67). Pure ASCII.
"""
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'zkit_logic.py')
RT_FILE = os.path.join(HERE, 'zkit_rt.py')
GLSL_FILE = os.path.join(HERE, 'zkit_face.glsl')
ESSENTIALS_FILE = os.path.join(HERE, 'zk_essentials.json')   # Main tab + macros per COMP name (missing = fallback)
DEMO = 'ZK_controls_kit'
NTEXT = 8
NHOT = 2                                                       # hot Text TOPs (zkit_rt.NHOT), docs/builds/zkit_perf.md
# zk_comp (the old all-text composite) is gone: the face shader reads each text TOP itself; an older panel's zk_comp
# is removed as a stray (safe_destroy, window closed)
ZK_OPS = ['zk_logic', 'zk_rt', 'zk_cfg', 'zk_props', 'zk_presets', 'zk_gpu', 'zk_gpu_chop', 'zk_gpu_sel', 'zk_gpu_pack',
          'zk_gpu_tex',
          'zk_tiles', 'zk_tiles_chop', 'zk_tiles_tex', 'zk_face_glsl', 'zk_face', 'zk_measure', 'zk_out',
          'zk_mouse', 'zk_keys', 'zk_keys_cb', 'zk_sync', 'zk_tick', 'zk_watch'] + \
    ['zk_ts%d' % k for k in range(NTEXT)] + ['zk_text%d' % k for k in range(NTEXT)] + \
    ['zk_hs%d' % k for k in range(NHOT)] + ['zk_hot%d' % k for k in range(NHOT)]

MOUSE_CB = '''# zk_mouse: panel values of the controls container -> zk_rt
def onValueChange(panelValue, prev):
\top('zk_rt').module.OnPanel(panelValue.name, panelValue.val, prev)
\treturn

def onOffToOn(panelValue):
\treturn

def onOnToOff(panelValue):
\treturn
'''

KEYS_CB = '''# zk_keys: active only while a value/label is being typed
def onKey(dat, keyInfo):
\top('zk_rt').module.Key(keyInfo)
\treturn

def onShortcut(dat, shortcutName, time):
\treturn
'''

SYNC_CB = '''# zk_sync: the host COMP's custom pars changed anywhere -> knobs follow (two-way); Zkit pulses
def onValueChange(par, prev):
\top('zk_rt').module.Sync(par)
\treturn

def onPulse(par):
\top('zk_rt').module.Pulse(par)
\treturn
'''

WATCH_CB = '''# zk_watch: the host's module stack (PX_pointfx px_stack) changed -> pages of modules that are off hide / show
def onTableChange(dat):
\top('zk_rt').module.StackChanged()
\treturn
'''

TICK_CB = '''# zk_tick: on only while filtered (per-knob 'filter') writes glide
def onFrameStart(frame):
\top('zk_rt').module.Tick()
\treturn
'''

ZKIT_PAGE = [
    ('Opencontrols', 'Pulse', None, {'label': 'Open controls'}),
    ('Zktheme', 'Menu', 'night', {'label': 'Theme', 'names': ['night', 'day'], 'labels': ['Night', 'Day']}),
    ('Zkd', 'Int', 56, {'label': 'Knob size px', 'min': 24, 'max': 160}),
    ('Zkcols', 'Int', 8, {'label': 'Columns', 'min': 1, 'max': 12}),
    ('Zkmaxh', 'Int', 0, {'label': 'Max height px (0 = fit screen)', 'min': 0, 'max': 4096}),   # T-231: viewport
    ('Zkrandamount', 'Float', 0.5, {'label': 'Random amount', 'min': 0.0, 'max': 1.0}),
    ('Zkrandomize', 'Pulse', None, {'label': 'Randomize'}),
    ('Zkshowall', 'Pulse', None, {'label': 'Show deleted knobs'}),
    ('Zkrebuild', 'Pulse', None, {'label': 'Rebuild panel'}),
]


def _sd(o):
    """T-70: destroy only through safe_destroy (td_exec namespace, else the MCP handlers module)."""
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


def _pack_order():
    ns = {}
    with open(LOGIC_FILE) as fh:
        exec(fh.read(), ns)
    f = ns['FIELDS']
    return [f[4 * k + j] for j in range(4) for k in range(len(f) // 4)]


PACK_ORDER = _pack_order()                                     # zk_gpu_sel channel order (k-major groups of 4)
MAX_WIRED = 3                                                  # GLSL TOP connectors from Python on 31550 (T-84)


def wire_face(face, srcs):
    """Feed srcs to the GLSL TOP as sTD2DInputs[0..n-1] in order: the first MAX_WIRED go on the connectors, the rest
    in the `tops` par (numbered after the wired ones, T-00d). A GLSL TOP has only 3 connectors (T-84: connecting
    past them raises IndexError, and outputConnectors[0].connect(face) replaces input 0), so never index past them."""
    wired = srcs[:MAX_WIRED]
    for k, s in enumerate(wired):
        cur = face.inputs[k] if k < len(face.inputs) else None
        if cur is None or cur.path != s.path:
            face.inputConnectors[k].connect(s)
    for k in range(len(face.inputConnectors) - 1, len(wired) - 1, -1):
        if face.inputConnectors[k].connections:
            face.inputConnectors[k].disconnect()
    tops = ' '.join(s.name for s in srcs[MAX_WIRED:])          # siblings: names resolve from the GLSL TOP's parent
    if face.par.tops.val != tops:
        face.par.tops = tops
    return len(wired), tops


def _add_pars(c, spec, page_name):
    page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
    for name, style, default, o in spec:
        if getattr(c.par, name, None) is not None or getattr(c.par, name + 'r', None) is not None:
            continue
        label = o.get('label', name)
        if style == 'Menu':
            p = page.appendMenu(name, label=label)[0]
            p.menuNames, p.menuLabels = o['names'], o['labels']
            p.default = default
            p.val = default
        elif style in ('Float', 'Int'):
            p = (page.appendFloat if style == 'Float' else page.appendInt)(name, label=label, size=o.get('size', 1))
            for q, v in zip(p, default if isinstance(default, (list, tuple)) else [default] * len(p)):
                q.normMin, q.normMax = o['min'], o['max']
                q.default = v
                q.val = v
        elif style == 'Toggle':
            p = page.appendToggle(name, label=label)[0]
            p.default = default
            p.val = default
        elif style == 'Momentary':
            page.appendMomentary(name, label=label)
        elif style == 'Pulse':
            page.appendPulse(name, label=label)
        elif style == 'RGB':
            for p, v in zip(page.appendRGB(name, label=label), default):
                p.default = v
                p.val = v
        elif style == 'Str':
            p = page.appendStr(name, label=label)[0]
            p.default = default
            p.val = default
        elif style == 'StrMenu':
            p = page.appendStrMenu(name, label=label)[0]
            p.menuNames, p.menuLabels = o['names'], o['labels']
            p.default = default
            p.val = default
    return page


def _screen_pts():
    """Primary screen size in points (= panel px on a Retina Mac: scaledWidth/Height; 31550: monitors[0] gives
    width 4112 / scaledWidth 2056, dpiScale 2). '' when TD cannot say (the runtime then uses its fallback)."""
    try:
        mo = [x for x in monitors if x.isPrimary] or list(monitors)
        return '%d %d' % (int(mo[0].scaledWidth), int(mo[0].scaledHeight))
    except Exception:
        return ''


def _essentials(c, path=None):
    """builders/zk_essentials.json entry for this COMP (by name) -> (main names, macros, notes). A missing / broken
    file or no entry = ([], [], [...]): the runtime then uses the fallback Main (first 12 of the first page)."""
    import json
    path = path or ESSENTIALS_FILE
    try:
        with open(path) as fh:
            data = json.load(fh)
    except (IOError, OSError, ValueError) as e:
        return [], [], ['essentials: %s' % type(e).__name__]
    entry = data.get(c.name) if isinstance(data, dict) else None
    if entry is None:
        return [], [], ['essentials: no entry for %s (fallback Main)' % c.name]

    def style(n):
        p = getattr(c.par, n, None)
        if p is not None:
            return p.style
        for q in c.customPars:
            if q.tupletName == n:
                return q.style
        return None
    return _logic()['validate_essentials'](entry, style)


def _px_default_types():
    """PX_pointfx DEFAULT_STACK types by uid (1-based), read from builders/px.py text: '1:prox_push 2:curl ...'."""
    import re
    try:
        src = open(os.path.join(HERE, 'px.py')).read()
        body = src[src.index('DEFAULT_STACK = ['):]
        body = body[:body.index(']\n')]
        return ' '.join('%d:%s' % (k + 1, t) for k, t in enumerate(re.findall(r"\('([a-z_0-9]+)', \{", body)))
    except (IOError, OSError, ValueError):
        return ''


def _add_macros(c, macros):
    """Each macro = a Float par 0..1 on the Zkit page (kept with its value when it exists; label refreshed)."""
    page = next((pg for pg in c.customPages if pg.name == 'Zkit'), None) or c.appendCustomPage('Zkit')
    Lg = _logic()
    for mc in macros:
        p = getattr(c.par, mc['name'], None)
        if p is None:
            p = page.appendFloat(mc['name'], label=mc['label'])[0]
            p.normMin, p.normMax, p.min, p.max = 0.0, 1.0, 0.0, 1.0
            p.clampMin = p.clampMax = True
            p.default = 0.0
            d0 = mc['drives'][0]
            try:
                p.val = mc['default'] if 'default' in mc else \
                    Lg['macro_init'](float(getattr(c.par, d0['par']).eval()), d0)
            except Exception:
                p.val = 0.0
        elif p.label != mc['label']:
            p.label = mc['label']


def _table(c, name, rows=None):
    t = _mk(c, tableDAT, name)
    if rows is not None and (t.numRows == 0 or t[0, 0].val != rows[0][0]):
        t.clear()                                              # a new Table DAT holds one blank cell, not nothing
        t.appendRows(rows)
    return t


def build_controls(comp_path, pages=None, exclude=(), d=56, cols=8, panel_name='controls', open_window=False,
                   winop=None, keep=(), essentials=None):
    """panel_name may be a path inside the COMP ('controls/params': the kit as one part of a bigger panel, e.g.
    TL_timeline's ruler above it); winop = what controls_window shows (relative to the COMP, default the panel);
    keep = child names of the panel that are not strays (never destroyed)."""
    c = op(comp_path)
    if c is None or not c.isCOMP:
        raise ValueError('not a COMP: %s' % comp_path)
    was_open = _close_window(c)                                # T-70: never touch a panel an open window shows
    _add_pars(c, ZKIT_PAGE, 'Zkit')
    if c.par.Zkd.eval() != d and not c.fetch('zk_built', False, search=False):
        c.par.Zkd = d
        c.par.Zkcols = cols
    panel = c.op(panel_name)
    if panel is not None and panel.OPType != 'containerCOMP':
        _sd(panel)
        panel = None
    if panel is None:
        holder = c.op(panel_name.rsplit('/', 1)[0]) if '/' in panel_name else c
        panel = holder.create(containerCOMP, panel_name.rsplit('/', 1)[-1])
        panel.viewer = True
    removed = []
    for ch in list(panel.children):                            # an older (e.g. autoUI) panel: strays go, window closed
        if ch.valid and ch.name not in ZK_OPS and ch.name not in keep and ch.OPType != 'annotateCOMP':
            removed.append(ch.name)
            _sd(ch)
    panel.comment = ('zkit controls (zerror-style knobs/presets) for %s. Open: pulse Opencontrols. LMB drag tweak '
                     '(Shift fine, Ctrl+Shift finer, Alt coarse), click = type, double click = recall on/off, MMB = '
                     'default, RMB = properties, wheel = step (Ctrl fine). Tabs = pages; wheel on empty space / titles / scrollbar '
                     'or Shift+wheel = scroll; drag the thumb.' % c.name)
    panel.par.bgalpha = 1
    # code + state
    lg = _mk(panel, textDAT, 'zk_logic')
    lg.text = open(LOGIC_FILE).read()
    cfg = _table(panel, 'zk_cfg', [['key', 'value']])
    scr = _screen_pts()
    import json as _json
    e_main, e_macros, e_notes = _essentials(c, essentials)
    _add_macros(c, e_macros)
    zl = _logic()
    for k, v in (('target', zl['target_rel'](panel.path, c.path)), ('pages', ' '.join(pages or [])), ('exclude', ' '.join(exclude)),
                 ('d', str(d)), ('cols', str(cols)), ('version', '3'), ('screen', scr), ('main', ' '.join(e_main)),
                 ('macros', _json.dumps(e_macros, separators=(',', ':'))), ('ess_notes', '; '.join(e_notes)),
                 ('uidtypes', _px_default_types() if c.op('px_stack') is not None else '')):
        if k == 'screen' and not v:
            continue
        if cfg[k, 1] is None:
            cfg.appendRow([k, v])
        elif k not in ('collapsed',):
            cfg[k, 1] = v
    if cfg['collapsed', 1] is None:
        cfg.appendRow(['collapsed', ''])
    _table(panel, 'zk_props')
    _table(panel, 'zk_presets', [['slot', 'name', 'color', 'data']])
    # draw chain: instance table -> CHOP -> float texture -> one GLSL pass (+ tile lists the same way, rewritten only
    # when the layout changes); text spec tables -> Text TOPs read by the same pass -> null
    def _datatex(tname, cname, xname, packed=False):
        tab = _table(panel, tname)
        ch = _mk(panel, dattoCHOP, cname)
        ch.par.dat = tab
        ch.par.output = 'chanperrow'
        ch.par.firstrow = 'values'
        ch.par.firstcolumn = 'names'
        src = ch
        if packed:
            # perf pass (26 Oct): 16 fields -> one RGBA row, texel k*n + i = fields 4k..4k+3 of instance i, so the
            # face reads 1 texel to reject an instance and 4 to draw it (was 4 and 16 r32 reads). Select orders the
            # fields k-major, Shuffle 'seqn' (N = 4) joins each 4 into one channel = r g b a (checked on scratch TD).
            sel = _mk(panel, selectCHOP, 'zk_gpu_sel')
            sel.inputConnectors[0].connect(ch)
            sel.par.channames = ' '.join(PACK_ORDER)
            shf = _mk(panel, shuffleCHOP, 'zk_gpu_pack')
            shf.inputConnectors[0].connect(sel)
            shf.par.method = 'seqn'
            shf.par.nval = 4
            src = shf
        tx_ = _mk(panel, choptoTOP, xname)
        tx_.par.chop = src
        tx_.par.dataformat = 'rgba' if packed else 'r'
        tx_.par.format = 'rgba32float' if packed else 'r32float'
        return tx_
    gtex = _datatex('zk_gpu', 'zk_gpu_chop', 'zk_gpu_tex', packed=True)
    ttex = _datatex('zk_tiles', 'zk_tiles_chop', 'zk_tiles_tex')
    gl = _mk(panel, textDAT, 'zk_face_glsl')
    gl.text = open(GLSL_FILE).read()
    face = _mk(panel, glslTOP, 'zk_face')
    face.par.pixeldat = gl
    for dk in list(face.docked):                               # a new GLSL TOP docks its own info/pixel/compute
        if dk.valid and dk.name not in ZK_OPS:                 # DATs; zk_face_glsl is the shader, so they go now
            _sd(dk)                                            # (not as "strays" on the next rebuild)
    face.par.outputresolution = 'custom'
    face.par.format = 'rgba8fixed'
    face.par.inputextenduv = 'zero'
    face.seq.vec.numBlocks = 9
    for k, nm in enumerate(['uInfo', 'uBg', 'uBody', 'uTrack', 'uBlue', 'uBlueDim', 'uRed', 'uWhite', 'uView']):
        getattr(face.par, 'vec%dname' % k).val = nm
    # text: Text TOP spec rows carry no font size on 31550, so one Text TOP per size bucket (zk_rt fills them)
    def _txt(name, spec_dat):
        tx = _mk(panel, textTOP, name)
        tx.par.specdat = spec_dat if spec_dat is not None else ''
        tx.par.text = ''
        tx.par.font = 'Open Sans'                              # 7.0 #1: humanist sans, regular, not mono
        tx.par.bold = False
        tx.par.fontsizexunit = 'pixels'
        tx.par.fontsizex = 20
        tx.par.alignx = 'left'
        tx.par.aligny = 'bottom'
        tx.par.positionunit = 'pixels'
        tx.par.outputresolution = 'custom'
        tx.par.bgalpha = 0
        tx.par.format = 'rgba8fixed'
        return tx
    meas = _txt('zk_measure', None)
    meas.par.resolutionw, meas.par.resolutionh = 8, 8
    meas.comment = 'Not drawn: zk_rt measures text widths with it (evalTextSize at size 20).'
    texts = []
    for k in range(NTEXT):
        texts.append(_txt('zk_text%d' % k, _table(panel, 'zk_ts%d' % k)))
    for k in range(NHOT):                                      # value text of a dragged / per-frame knob, alone
        texts.append(_txt('zk_hot%d' % k, _table(panel, 'zk_hs%d' % k)))
    old = panel.op('zk_text')
    if old is not None:
        _sd(old)
    oldt = panel.op('zk_textspec')
    if oldt is not None:
        _sd(oldt)
    wire_face(face, [gtex, ttex] + texts)                      # 0 gpu, 1 tiles, 2..9 buckets, 10..11 hot
    out = _mk(panel, nullTOP, 'zk_out')
    out.inputConnectors[0].connect(face)
    panel.par.top = out
    # behaviour
    rt = _mk(panel, textDAT, 'zk_rt')
    rt.text = open(RT_FILE).read()
    mouse = _mk(panel, panelexecuteDAT, 'zk_mouse')
    mouse.text = MOUSE_CB
    mouse.par.panels = panel
    mouse.par.panelvalue = 'u v lselect rselect mselect wheel rollover'
    mouse.par.offtoon = False
    mouse.par.ontooff = False
    mouse.par.valuechange = True
    keys = _mk(panel, keyboardinDAT, 'zk_keys')
    kcb = _mk(panel, textDAT, 'zk_keys_cb')
    kcb.text = KEYS_CB
    keys.par.callbacks = kcb
    keys.par.active = False
    for leftover in ('zk_keys_callbacks',):                    # Keyboard In makes its own callbacks DAT once
        lo_ = panel.op(leftover)
        if lo_ is not None:
            _sd(lo_)
    sync = _mk(panel, parameterexecuteDAT, 'zk_sync')
    sync.text = SYNC_CB
    sync.par.op = c
    sync.par.pars = '*'
    sync.par.custom = True
    sync.par.builtin = False
    sync.par.valuechange = True
    sync.par.onpulse = True
    if c.op('px_stack') is not None:                           # module stack: hide pages of modules that are off
        wt = _mk(panel, datexecuteDAT, 'zk_watch')
        wt.text = WATCH_CB
        wt.par.dat = c.op('px_stack')
        wt.par.tablechange = True
    tick = _mk(panel, executeDAT, 'zk_tick')
    tick.text = TICK_CB
    tick.par.framestart = True
    tick.par.active = False
    # window (opened by Opencontrols)
    win = _mk(c, windowCOMP, 'controls_window')
    wop = c.op(winop) if winop else panel
    for k, v in (('winop', zl['winop_rel'](win.path, wop.path)), ('title', c.name + ' controls'), ('size', 'automatic'),
                 ('borders', True)):
        p = getattr(win.par, k)
        if k == 'winop':                                       # drop-in: relative; an absolute old value is rewritten
            if p.val != v:
                p.val = v
            continue
        cur = p.eval()
        cur = cur.path if hasattr(cur, 'path') else cur
        if cur != v:                                           # touch the window only when something differs
            p.val = v
    c.store('zk_built', True)
    info = rt.module.Rebuild()
    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': [o for o in ('zk_mouse', 'zk_keys', 'zk_keys_cb', 'zk_sync',
                                                                     'zk_tick', 'zk_watch') if panel.op(o)],
         'body': 'Mouse (Panel Execute on this panel), keys (only while typing), host par changes (two-way) and the '
                 'per-knob filter tick (on only while values glide). All call zk_rt.'},
        {'title': '1 Code + state', 'role': 'process', 'ops': ['zk_logic', 'zk_rt', 'zk_cfg', 'zk_props', 'zk_presets'],
         'body': 'zk_logic = builders/zkit_logic.py (tested offline), zk_rt = builders/zkit_rt.py. Tables: cfg, '
                 'per-knob properties, presets (raw values as json).'},
        {'title': '2 Faces', 'role': 'process', 'ops': ['zk_gpu', 'zk_gpu_chop', 'zk_gpu_sel', 'zk_gpu_pack', 'zk_gpu_tex', 'zk_tiles',
                                                        'zk_tiles_chop', 'zk_tiles_tex', 'zk_face_glsl'],
         'body': 'One instance per drawn thing (16 fields) -> CHOP -> float texture for the face shader; zk_tiles = '
                 'per 64 px tile the instances that touch it (changes only with the layout).'},
        {'title': '3 Text', 'role': 'process', 'ops': ['zk_measure'] +
         ['zk_ts%d' % k for k in range(NTEXT)] + ['zk_text%d' % k for k in range(NTEXT)] +
         ['zk_hs%d' % k for k in range(NHOT)] + ['zk_hot%d' % k for k in range(NHOT)],
         'body': 'Open Sans, one Text TOP per font size (spec rows carry no size/colour on 31550); zk_hot0/1 hold '
                 'only the value text of a knob being dragged / changing every frame. White; the face shader colours '
                 'it.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['zk_face', 'zk_out'],
         'body': 'ONE GLSL pass draws every knob, preset, pill, frame and menu row + colours the text; each pixel '
                 'loops only over its tile. zk_out = the panel background. Cooks only when something changes.'},
    ]
    try:
        op('/jazib_mcp/handlers').module.layout_stages(panel, stages, True, arrange='mixed')
    except Exception as e:                                     # layout is cosmetic; never fail a build on it
        info += ' (layout: %s)' % e
    if open_window or was_open:                                # reopen a few frames later, after the rebuild settles
        run("o = op(%r)\nif o is not None and not o.isOpen: o.par.winopen.pulse()" % win.path, delayFrames=5,
            delayRef=op.TDResources)
    return {'panel': panel.path, 'rebuild': info, 'removed': removed, 'size': (int(panel.par.w), int(panel.par.h))}


def _cfg_target(cfg):
    """The COMP a zk_cfg table names: relative values ('..', '../..') from the panel, absolute ones (panels built
    before 28 Oct) as they are."""
    v = cfg['target', 1].val if cfg['target', 1] is not None else ''
    if not v:
        return None
    return op(v) if v.startswith('/') else cfg.parent().op(v)


def _zk_owner(panel):
    """The COMP a panel belongs to: its nearest ancestor with the Zkit page (Zkd), whatever zk_cfg says."""
    x = panel.parent()
    while x is not None and x.path != '/':
        if getattr(x.par, 'Zkd', None) is not None:
            return x
        x = x.parent()
    return None


def refresh_panel(comp_path, panel=None):
    """Roll the current kit into an existing panel, with the arguments it was built with (from its zk_cfg: pages,
    exclude; panel path and window target from the panel itself; non-zk children kept). Knob properties, presets,
    collapse, Zkd / Zkcols and the remembered tab / scroll survive (build_controls keeps them); an open window is
    closed first and reopened after (T-70). The network pane goes to the COMP's parent first (T-213 / T-215).
    -> {panel, before, after, rebuild, notes}."""
    c = op(comp_path)
    if c is None or not c.isCOMP:
        raise ValueError('not a COMP: %s' % comp_path)
    if panel is None:
        tabs = [t for t in c.findChildren(name='zk_cfg', maxDepth=3) if t.OPType == 'tableDAT' and t['target', 1] is not None]
        cands = [t.parent() for t in tabs if _cfg_target(t) is not None and _cfg_target(t).path == c.path]
        if not cands:                                          # a copy / drop: its target still names the original;
            cands = [t.parent() for t in tabs if _zk_owner(t.parent()) is not None   # the panel's own COMP wins
                     and _zk_owner(t.parent()).path == c.path]
        if not cands:
            raise ValueError('no zkit panel in %s' % comp_path)
        panel = cands[0]
    else:
        panel = c.op(panel)
    cfg = panel.op('zk_cfg')
    rel = panel.path[len(c.path) + 1:]
    pages = [x for x in cfg['pages', 1].val.split() if x] if cfg['pages', 1] is not None else []
    exclude = [x for x in cfg['exclude', 1].val.split() if x] if cfg['exclude', 1] is not None else []
    win = c.op('controls_window')
    winop = None
    if win is not None and win.OPType == 'windowCOMP':
        w = win.par.winop.eval()
        wp = w.path if hasattr(w, 'path') else str(w)
        if wp and wp != panel.path and wp.startswith(c.path + '/'):
            winop = wp[len(c.path) + 1:]
    keep = tuple(ch.name for ch in panel.children if not ch.name.startswith('zk_') and ch.OPType != 'annotateCOMP')
    before = (int(panel.par.w.eval()), int(panel.par.h.eval()))
    try:
        for pn in ui.panes:
            if pn.type == PaneType.NETWORKEDITOR and pn.owner is not None and \
                    (pn.owner.path + '/').startswith(c.path + '/'):
                pn.owner = c.parent()
    except Exception:
        pass
    d = int(c.par.Zkd.eval()) if getattr(c.par, 'Zkd', None) is not None else 56
    cols = int(c.par.Zkcols.eval()) if getattr(c.par, 'Zkcols', None) is not None else 8
    parked, a_ = [], c                                          # a parked COMP (or parent) cannot compile zk_rt:
    while a_ is not None and a_.path != '/':                    # un-park for the build, park again right after
        if not a_.allowCooking:
            parked.append(a_)
        a_ = a_.parent()
    for a_ in parked:
        a_.allowCooking = True
    try:
        r = build_controls(c.path, pages=pages or None, exclude=exclude, d=d, cols=cols, panel_name=rel,
                           winop=winop, keep=keep)
    finally:
        for a_ in parked:
            a_.allowCooking = False
    cf = panel.op('zk_cfg')
    return {'panel': panel.path, 'before': before, 'after': (int(panel.par.w.eval()), int(panel.par.h.eval())),
            'rebuild': r.get('rebuild'), 'removed': r.get('removed'), 'parked_again': [x.path for x in parked],
            'notes': '; '.join(x for x in (cf['ess_notes', 1].val if cf['ess_notes', 1] is not None else '',
                                         cf['rt_notes', 1].val if cf['rt_notes', 1] is not None else '') if x)}


# ---------------------------------------------------------------- demo COMP
DEMO_PAGES = [
    ('Look', [
        ('Period', 'Float', 1.2, {'label': 'Period', 'min': 0.1, 'max': 8.0}),
        ('Harmonics', 'Int', 3, {'label': 'Harmonics', 'min': 0, 'max': 8}),
        ('Gain', 'Float', 0.0, {'label': 'Gain', 'min': -1.0, 'max': 1.0}),
        ('Exponent', 'Float', 1.0, {'label': 'Exponent', 'min': 0.1, 'max': 4.0}),
        ('Noisetype', 'Menu', 'simplex3d', {'label': 'Type', 'names': ['simplex2d', 'simplex3d', 'perlin2d',
                                                                        'perlin3d', 'random', 'harmonic'],
                                            'labels': ['simplex2d', 'simplex3d', 'perlin2d', 'perlin3d', 'random',
                                                       'harmonic']}),
        ('Mono', 'Toggle', False, {'label': 'Mono'}),
        ('Tint', 'RGB', (0.91, 0.27, 0.11), {'label': 'Tint'}),
        ('Speed', 'Float', 0.3, {'label': 'Speed', 'min': 0.0, 'max': 4.0}),
        ('Demores', 'Menu', 'half', {'label': 'Noise res', 'names': ['full', 'half', 'quarter'],
                                     'labels': ['Full 1080x1920', 'Half (default, perf 27 Oct)', 'Quarter']}),
    ]),
    ('Motion', [
        ('Offset', 'Float', (0.0, 0.0), {'label': 'Offset', 'min': -2.0, 'max': 2.0, 'size': 2}),
        ('Rotate', 'Float', 0.0, {'label': 'Rotate', 'min': -180.0, 'max': 180.0}),
        ('Flash', 'Momentary', None, {'label': 'Flash'}),
        ('Reseed', 'Pulse', None, {'label': 'Reseed'}),
        ('Caption', 'Str', 'zkit demo', {'label': 'Caption'}),
    ]),
]


DEMO_RES_E = "max(1, int(%d * {'full': 1.0, 'half': 0.5, 'quarter': 0.25}.get(parent().par.Demores.eval(), 1.0)))"


def build_demo(parent_path='/project1/lab', open_window=False):
    """Demo: a small noise look driven by its own pars + the zkit panel. Out: out1 TOP (1080x1920)."""
    par_ = op(parent_path)
    c = par_.op(DEMO) or par_.create(baseCOMP, DEMO)
    c.comment = 'zkit demo: zerror-style controls panel (controls) on a noise look. Pulse Opencontrols. Out: out1.'
    open_window = _close_window(c) or open_window             # T-70: closed during the rebuild, reopened after
    for ch in list(c.children):                                # probe leftovers of the crashed session
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)
    for pg, spec in DEMO_PAGES:
        _add_pars(c, spec, pg)
    nz = _mk(c, noiseTOP, 'noise1')
    nz.par.outputresolution = 'custom'
    for rp, full in ((nz.par.resolutionw, 1080), (nz.par.resolutionh, 1920)):   # perf 27 Oct: Demores (half default:
        rp.expr = DEMO_RES_E % full                         # 8-harmonic simplex3d at 1080x1920 = 1.7-3 ms GPU)
        rp.mode = ParMode.EXPRESSION
    ex = {'period': "parent().par.Period", 'harmon': "parent().par.Harmonics", 'amp': "1.0 + parent().par.Gain",
          'exp': "parent().par.Exponent", 'mono': "parent().par.Mono",
          'tx': "parent().par.Offset1", 'ty': "parent().par.Offset2", 'rz': "parent().par.Rotate",
          'tz': "absTime.seconds * parent().par.Speed", 'seed': "me.fetch('seed', 1)"}
    for k, e in ex.items():
        p = getattr(nz.par, k, None)
        if p is not None:
            p.expr = e
            p.mode = ParMode.EXPRESSION
    nz.par.type.expr = "parent().par.Noisetype.eval()"
    nz.par.type.mode = ParMode.EXPRESSION
    lv = _mk(c, levelTOP, 'tint')
    lv.inputConnectors[0].connect(nz)
    lv.par.brightness1.expr = "1 + 2 * parent().par.Flash"
    lv.par.brightness1.mode = ParMode.EXPRESSION
    cm = _mk(c, constantTOP, 'tint_col')
    cm.par.outputresolution = 'custom'
    for rp, full in ((cm.par.resolutionw, 1080), (cm.par.resolutionh, 1920)):
        rp.expr = DEMO_RES_E % full
        rp.mode = ParMode.EXPRESSION
    for comp_, e in (('colorr', 'Tintr'), ('colorg', 'Tintg'), ('colorb', 'Tintb')):
        getattr(cm.par, comp_).expr = 'parent().par.%s' % e
        getattr(cm.par, comp_).mode = ParMode.EXPRESSION
    mul = _mk(c, multiplyTOP, 'tinted')
    mul.inputConnectors[0].connect(lv)
    mul.inputConnectors[1].connect(cm)
    cap = _mk(c, textTOP, 'caption')
    cap.par.outputresolution = 'custom'
    cap.par.resolutionw, cap.par.resolutionh = 1080, 1920
    cap.par.text.expr = 'parent().par.Caption'
    cap.par.text.mode = ParMode.EXPRESSION
    cap.par.font = 'Open Sans'
    cap.par.fontsizex = 64
    cap.par.bgalpha = 0
    ov = _mk(c, overTOP, 'with_caption')
    ov.inputConnectors[0].connect(cap)
    ov.inputConnectors[1].connect(mul)
    ov.par.size = 'input1'                                    # the caption's 1080x1920 (the look may be Demores-small)
    ov.par.prefit = 'fill'
    out1 = _mk(c, outTOP, 'out1')
    out1.inputConnectors[0].connect(ov)
    rs = _mk(c, parameterexecuteDAT, 'reseed')
    rs.text = ("# Reseed pulse -> new noise seed\ndef onPulse(par):\n\tif par.name == 'Reseed':\n"
               "\t\tn = op('noise1')\n\t\tn.store('seed', int(n.fetch('seed', 1)) + 1)\n\t\tn.cook(force=True)\n"
               "\treturn\n")
    rs.par.op = c
    rs.par.pars = 'Reseed'
    rs.par.custom = True
    rs.par.builtin = False
    rs.par.valuechange = False
    rs.par.onpulse = True
    res = build_controls(c.path, pages=['Look', 'Motion'], open_window=open_window)
    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window'],
         'body': 'zkit panel, two-way on Look + Motion. Pulse Opencontrols.'},
        {'title': '1 Look', 'role': 'process', 'ops': ['noise1', 'tint', 'tint_col', 'tinted', 'reseed'],
         'body': 'Noise TOP driven by the custom pars (Period, Harmonics, Gain, Exponent, Type, Mono, Offset, '
                 'Rotate, Speed), tinted by Tint; Flash = momentary brightness; Reseed = pulse.'},
        {'title': '2 Out', 'role': 'output', 'ops': ['caption', 'with_caption', 'out1'],
         'body': 'Caption (Str par, full res) over the look (Demores: noise at full / half / quarter, upscaled). '
                 'out1 = 1080x1920 picture only.'},
    ]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    res['layout'] = str(lay)[:300]
    return res


# ================================================================ debug panel skin (td_debug_panel style 'zkit')
DEBUG_SKIN_OPS = ('zk_bg_glsl', 'zk_bg', 'zk_graph_glsl', 'zk_graph')


def _logic():
    ns = {}
    with open(LOGIC_FILE) as fh:
        exec(fh.read(), ns)
    return ns


def style_debug_panel(comp, theme='night'):
    """Skin the jazib-td debug panel (td/debug.py, /project1/debug) in the kit's look without adding per-frame cost
    (T-72/T-73): Text TOP colours (param writes only when they differ), the flat view_bg swapped for zk_bg (a static
    band GLSL TOP: no inputs, no time, cooks once), the CHOP-viewer fps graph swapped for zk_graph (GLSL TOP reading
    fps_chop as a texture-buffer uniform: cooks only when fps_hist changes and only while the window shows it). Font stays Menlo:
    the view is fixed-width columns (debug_panel_rt CHARS = 61 at 7.0 px). Reversible: td_debug_panel style 'plain'
    rewires view_bg and the CHOP viewer (the zk_ ops then sit unpulled). T-70: window closed first, nothing destroyed
    except a new GLSL TOP's auto-docked DATs (never shown), reopened 10 frames later."""
    tdm = globals().get('td')
    c = comp if hasattr(comp, 'path') else op(comp)
    if c is None or c.op('rt') is None or c.op('view_comp') is None:
        raise ValueError('not a jazib-td debug panel: %s' % comp)
    L = _logic()
    if theme not in L['DEBUG_THEMES']:
        raise ValueError('theme must be one of %s' % sorted(L['DEBUG_THEMES']))
    T = L['DEBUG_THEMES'][theme]
    win = c.op('debug_window')
    was_open = bool(win is not None and win.isOpen)
    if was_open:
        win.par.winclose.pulse()
    changed = []

    def setp(o, name, v):
        p = getattr(o.par, name)
        cur = p.eval()
        if isinstance(v, float) and isinstance(cur, (int, float)) and abs(float(cur) - v) < 1e-6:
            return
        if cur == v:
            return
        p.val = v
        changed.append('%s.%s' % (o.name, name))

    def mk(cls_name, name):
        o = c.op(name)
        if o is not None and o.OPType == cls_name:
            return o
        if o is not None:
            _sd(o)
        o = c.create(getattr(tdm, cls_name), name)
        for dk in list(getattr(o, 'docked', [])):              # GLSL TOP auto-docks info/pixel/compute DATs
            if dk.valid and dk.name not in DEBUG_SKIN_OPS:
                _sd(dk)
        changed.append('+' + name)
        return o

    def text(o, s):
        if o.text != s:
            o.text = s
            changed.append(o.name + '.text')

    rt = c.op('rt').module
    for kind, col in T['text'].items():
        tx = c.op('tx_' + kind)
        if tx is not None:
            for ch, v in zip('rgb', col):
                setp(tx, 'fontcolor' + ch, float(v))
    W, H = int(rt.VIEW_W), int(rt.VIEW_H)
    kinds = [k for k, _t, _p in rt.view_lines(['', ''], [], [], 0, [])]
    bands = L['debug_bands'](kinds)
    gb = mk('textDAT', 'zk_bg_glsl')
    text(gb, L['debug_bg_glsl'](bands, theme, H, rt.PAD_TOP, rt.LINE_H))
    bg = mk('glslTOP', 'zk_bg')
    bg.viewer = False
    setp(bg, 'pixeldat', gb.name)
    for k, v in (('outputresolution', 'custom'), ('format', 'rgba8fixed')):
        setp(bg, k, v)
    setp(bg, 'resolutionw', W)
    setp(bg, 'resolutionh', H)
    comp_ = c.op('view_comp')
    old = c.op('view_bg')
    k_bg = None
    for i, conn in enumerate(comp_.inputConnectors):
        if conn.connections and conn.connections[0].owner in (old, bg):
            k_bg = i
    if k_bg is None:
        k_bg = len([x for x in comp_.inputs if x is not None])
    if not (comp_.inputConnectors[k_bg].connections and comp_.inputConnectors[k_bg].connections[0].owner == bg):
        comp_.inputConnectors[k_bg].connect(bg)
        changed.append('view_comp<-zk_bg')
    graph = c.op('fps_graph')
    gh = int(graph.par.h.eval()) if graph is not None else 110
    gt = c.op('zk_graph_tex')                                  # first skin used a CHOP to TOP (0.7 ms GPU a cook)
    if gt is not None:
        g0 = c.op('zk_graph')
        if g0 is not None and g0.inputs:
            g0.inputConnectors[0].disconnect()
        _sd(gt)
        changed.append('-zk_graph_tex')
    gg = mk('textDAT', 'zk_graph_glsl')
    rate = float(getattr(getattr(tdm, 'project', None), 'cookRate', 60.0) or 60.0)
    text(gg, L['debug_graph_glsl'](theme, rate))
    g = mk('glslTOP', 'zk_graph')
    g.viewer = False
    setp(g, 'pixeldat', gg.name)
    for k, v in (('outputresolution', 'custom'), ('format', 'rgba8fixed'), ('inputextenduv', 'hold')):
        setp(g, k, v)
    setp(g, 'resolutionw', W)
    setp(g, 'resolutionh', gh)
    if g.seq.array.numBlocks < 1:                              # fps history as a texture buffer, no CHOP to TOP
        g.seq.array.numBlocks = 1
    for k, v in (('array0name', 'uFps'), ('array0type', 'float'), ('array0arraytype', 'texturebuffer'),
                 ('array0chop', 'fps_chop')):
        setp(g, k, v)
    if graph is not None:
        if graph.par.opviewer.expr != "parent().op('zk_graph')":
            graph.par.opviewer.expr = "parent().op('zk_graph')"
            changed.append('fps_graph.opviewer')
        setp(graph, 'interactive', False)
    c.store('zk_skin', theme)
    if was_open:
        if tdm is not None and hasattr(tdm, 'run'):
            tdm.run("o = op(%r)\nif o is not None: o.par.winopen.pulse()" % win.path, delayFrames=10)
        else:
            win.par.winopen.pulse()
    return {'path': c.path, 'theme': theme, 'bands': bands, 'changed': changed, 'window_reopened': was_open}
