# test_pattern builder - TP_test_pattern: LED / projector test patterns + sync checks, out1 TOP only.
# Spec/recipe: docs/research/BB_test_patterns_sync.md section 5 (our own clean-room design; ideas from Wallin Pattern
# Generator + Video sync test wheel by Mallin, files never obtained). Pattern names follow
# stagelab/guides/JZB_Slice_Test.md. Generic face table (default one 1920x1080 wall).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/test_pattern.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set; custom par values kept; zkit panel refreshed in place.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy); the COMP's controls_window is closed before a rebuild;
# the panel container is never destroyed; the network pane is never moved here. No functions in storage. ASCII only.
import os

NAME = 'TP_test_pattern'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'test_pattern_logic.py')
SHADER_FILE = os.path.join(HERE, 'test_pattern_shader.glsl')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')

# --------------------------------------------------------------- callbacks (Text DATs inside the COMP)
COMMON = """
def _pars():
    P = parent()
    g = lambda n: getattr(P.par, n).eval()
    return {'pattern': g('Pattern'), 'channel': g('Channel'), 'level': g('Level'), 'area': g('Area'),
            'walk': g('Walk'), 'linewidth': g('Linewidth'), 'cell': g('Cell'), 'steps': g('Steps'),
            'showfaces': g('Showfaces'), 'resx': g('Resx'), 'resy': g('Resy'), 'nativewidth': g('Nativewidth'),
            'cabw': g('Cabw'), 'cabh': g('Cabh'), 'counter': g('Counter'), 'counterx': g('Counterx'),
            'countery': g('Countery'), 'countersize': g('Countersize'), 'wheel': g('Wheel'), 'wheelu': g('Wheelu'),
            'wheelv': g('Wheelv'), 'wheelsize': g('Wheelsize'), 'flash': g('Flash'), 'flashevery': g('Flashevery'),
            'blip': g('Blip'), 'bliplen': g('Bliplen'), 'fps': g('Fps')}

def _faces(L):
    P = parent()
    t = P.par.Facestable.eval() or op('faces')
    rows = [[c.val for c in r] for r in t.rows()] if t is not None and t.isDAT else []
    return L.parse_faces(rows)
"""

FACES_CB = """# faces_chop: the face table as composition-px rects (x y w h), 16 samples = GLSL uniform array uFaces.
""" + COMMON + """
def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    L = op('tp_logic').module
    p = _pars()
    rects = L.face_rects(_faces(L), p['resx'], p['resy'], p['nativewidth'])
    rects = [r for r in rects if r]
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = L.MAX_FACES
    for k, n in enumerate(('x', 'y', 'w', 'h')):
        ch = scriptOp.appendChan(n)
        for i in range(L.MAX_FACES):
            ch[i] = float(rects[i][k]) if i < len(rects) else 0.0
    return
"""

UNI_CB = """# uni: every GLSL uniform as a channel (tp_logic.uniforms), plus the blip gate.
# The Clock par (absTime.frame only while a clock feature is on) makes it cook per frame only then.
""" + COMMON + """
def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Clock', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Clock', label='Frame (clock)')[0]
        p.expr = ("absTime.frame if (parent().par.Counter.eval() or parent().par.Wheel.eval() or "
                  "parent().par.Flash.eval() or parent().par.Blip.eval() or "
                  "parent().par.Pattern.eval() == 'walk') else 0")
        p.mode = ParMode.EXPRESSION
    return

def onCook(scriptOp):
    L = op('tp_logic').module
    p = _pars()
    clock = L.needs_clock(p)
    frame = int(scriptOp.par.Clock.eval()) if getattr(scriptOp.par, 'Clock', None) is not None else 0
    p['frame'] = frame if clock else 0
    p['seconds'] = absTime.seconds if clock else 0.0
    step = 0
    if p['pattern'] == 'walk':
        sp = op('walk_speed')
        step = int(sp['step'].eval() + 1e-4) if sp is not None and sp['step'] is not None else 0
    p['step'] = step
    rects = L.face_rects(_faces(L), p['resx'], p['resy'], p['nativewidth'])
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for name, v in L.uniforms(p, rects):
        for k, x in enumerate(v):
            scriptOp.appendChan('%s%d' % (name, k))[0] = float(x)
    scriptOp.appendChan('blip')[0] = L.blip_gate(p['frame'], p['flashevery'], p['bliplen'], p['blip'])
    return
"""

CABSPEC_CB = """# cab_spec: Text TOP spec rows (x, y from bottom, text) = `column-row` per cabinet (Pattern Cabinets only).
""" + COMMON + """
def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    L = op('tp_logic').module
    p = _pars()
    scriptOp.clear()
    scriptOp.appendRow(['x', 'y', 'text'])
    if p['pattern'] != 'cabinets':
        return
    rects = L.face_rects(_faces(L), p['resx'], p['resy'], p['nativewidth'])
    s = L.scale(p['resx'], p['nativewidth'])
    rows = L.cabinet_labels(L.areas(rects, p['area'], p['resx'], p['resy']), p['cabw'] * s, p['cabh'] * s, p['resy'])
    m = op('cab_measure')
    size = m.par.fontsizex.eval() if m is not None else L.cabinet_font(p['cabw'] * s, p['cabh'] * s)
    rows = L.centre_rows(rows, size, (lambda t: m.evalTextSize(t)[0]) if m is not None else None)
    scriptOp.appendRows([[repr(x), repr(y), t] for (x, y, t) in rows])
    return
"""

SLICESPEC_CB = """# slice_spec: Text TOP spec rows: name, LED size, cabinet count per face (Pattern Slices only).
""" + COMMON + """
def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    L = op('tp_logic').module
    p = _pars()
    scriptOp.clear()
    scriptOp.appendRow(['x', 'y', 'text'])
    if p['pattern'] != 'slices':
        return
    faces = _faces(L)
    rects = L.face_rects(faces, p['resx'], p['resy'], p['nativewidth'])
    size = L.slice_font(rects)
    m = op('slice_measure')
    rows = L.centre_rows(L.slice_labels(faces, rects, p['cabw'], p['cabh'], p['resy'], size), size,
                         (lambda t: m.evalTextSize(t)[0]) if m is not None else None)
    scriptOp.appendRows([[repr(x), repr(y), t] for (x, y, t) in rows])
    return
"""

PAREXEC = """# tp_parexec: Respreset -> Resx/Resy; Resetwalk -> walk_speed back to 0.
def onValueChange(par, prev):
    if par.name == 'Respreset':
        r = op('tp_logic').module.preset_res(par.eval())
        if r:
            parent().par.Resx, parent().par.Resy = r
    return

def onPulse(par):
    if par.name == 'Resetwalk':
        op('walk_speed').par.resetpulse.pulse()
    return
"""

P = "parent().par.{}.eval()"
SC = "op('tp_logic').module.scale(parent().par.Resx.eval(), parent().par.Nativewidth.eval())"


def _logic():
    ns = {}
    exec(open(LOGIC_FILE).read(), ns)
    return ns


def _pages(Lg):
    n, lb = Lg['names'], Lg['labels']
    return [
        ('Pattern', [
            ('Pattern', 'Menu', 'cabinets', {'names': n(Lg['PATTERNS']), 'labels': lb(Lg['PATTERNS'])}),
            ('Channel', 'Menu', 'white', {'names': n(Lg['CHANNELS']), 'labels': lb(Lg['CHANNELS'])}),
            ('Level', 'Int', 255, {'min': 0, 'max': 255, 'label': 'Level (8-bit code)', 'clamp': (0, 255)}),
            ('Area', 'Menu', 'slices', {'names': n(Lg['AREAS']), 'labels': lb(Lg['AREAS'])}),
            ('Walk', 'Menu', 'across', {'names': n(Lg['WALKS']), 'labels': lb(Lg['WALKS'])}),
            ('Speed', 'Float', 10.0, {'min': 0, 'max': 120, 'label': 'Walk speed (steps/s)'}),
            ('Resetwalk', 'Pulse', None, {'label': 'Reset walk'}),
            ('Linewidth', 'Int', 2, {'min': 1, 'max': 64, 'label': 'Line width px', 'clamp': (1, None)}),
            ('Cell', 'Float', 0.0, {'min': 0, 'max': 512, 'label': 'Cell LED px (0 = cabinet)'}),
            ('Steps', 'Int', 16, {'min': 2, 'max': 256, 'label': 'Ramp steps', 'clamp': (2, None)}),
            ('Showfaces', 'Toggle', False, {'label': 'Show face outlines'}),
        ]),
        ('Cabinet', [
            ('Respreset', 'Menu', '1920x1080', {'names': n(Lg['RES_PRESETS']), 'labels': lb(Lg['RES_PRESETS']),
                                                'label': 'Resolution preset'}),
            ('Resx', 'Int', 1920, {'min': 16, 'max': 9984, 'label': 'Width px', 'clamp': (1, None)}),
            ('Resy', 'Int', 1080, {'min': 16, 'max': 3840, 'label': 'Height px', 'clamp': (1, None)}),
            ('Nativewidth', 'Float', 0.0, {'min': 0, 'max': 9984, 'label': 'Native LED width (0 = 1:1)'}),
            ('Cabw', 'Float', 128.0, {'min': 8, 'max': 512, 'label': 'Cabinet width LED px'}),
            ('Cabh', 'Float', 128.0, {'min': 8, 'max': 512, 'label': 'Cabinet height LED px'}),
        ]),
        ('Sync', [
            ('Counter', 'Toggle', False, {'label': 'Frame counter'}),
            ('Counterx', 'Int', 16, {'min': 0, 'max': 1920, 'label': 'Counter x px'}),
            ('Countery', 'Int', 16, {'min': 0, 'max': 1080, 'label': 'Counter y px'}),
            ('Countersize', 'Int', 24, {'min': 8, 'max': 128, 'label': 'Counter size px'}),
            ('Wheel', 'Toggle', False, {'label': 'Sync wheel'}),
            ('Wheelu', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Wheel x (0..1)'}),
            ('Wheelv', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Wheel y (0..1)'}),
            ('Wheelsize', 'Float', 360.0, {'min': 64, 'max': 2048, 'label': 'Wheel size px'}),
            ('Flash', 'Toggle', False, {'label': 'Flash frame'}),
            ('Flashevery', 'Int', 60, {'min': 1, 'max': 600, 'label': 'Flash every N frames', 'clamp': (1, None)}),
            ('Blip', 'Toggle', False, {'label': 'Audio blip (speakers)'}),
            ('Blipfreq', 'Float', 1000.0, {'min': 50, 'max': 8000, 'label': 'Blip Hz'}),
            ('Bliplen', 'Int', 1, {'min': 1, 'max': 30, 'label': 'Blip frames', 'clamp': (0, None)}),
            ('Blipvol', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Blip volume'}),
            ('Fps', 'Float', 60.0, {'min': 1, 'max': 240, 'label': 'Counter fps', 'expr': 'project.cookRate'}),
        ]),
        ('Layout', [
            ('Facestable', 'DAT', '', {'label': 'Face table DAT (empty = faces)'}),
        ]),
    ]


PANEL_PAGES = ['Pattern', 'Cabinet', 'Sync']


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            elif style == 'DAT':
                p = page.appendDAT(name, label=label)[0]
            if 'min' in o:
                p.normMin, p.normMax = o['min'], o['max']
            if 'clamp' in o:
                lo, hi = o['clamp']
                if lo is not None:
                    p.clampMin, p.min = True, lo
                if hi is not None:
                    p.clampMax, p.max = True, hi
            p.default = default
            p.val = default
            if 'expr' in o:
                p.expr = o['expr']
                p.mode = ParMode.EXPRESSION


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


def _script(c, cls, name, cb_text):
    s = _mk(c, cls, name)
    cb = s.par.callbacks.eval()
    want = name + '_callbacks'
    if cb is None:
        cb = _mk(c, textDAT, want)
    cb.text = cb_text
    if cb.name != want:
        cb.name = want
    s.par.callbacks = want
    if not cb.dock:
        cb.dock = s
    s.par.setuppars.pulse() if hasattr(s.par, 'setuppars') else None
    return s


def _text(c, name, font, spec=None):
    t = _mk(c, textTOP, name)
    t.par.specdat = spec if spec is not None else ''
    t.par.font = font
    t.par.fontsizexunit = 'pixels'
    t.par.alignx = 'center'
    t.par.aligny = 'center'
    t.par.positionunit = 'pixels'
    t.par.outputresolution = 'custom'
    t.par.bgalpha = 0
    t.par.fontcolorr = t.par.fontcolorg = t.par.fontcolorb = 1
    t.par.format = 'rgba8fixed'
    return t


def build(parent_path='/project1/lab', panel=True):
    Lg = _logic()
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('TP_test_pattern: LED/projector test patterns (JZB_Slice_Test names: Cabinets, Slices, Solid, Bars, '
                 'Ramp, Checker, Crosshatch, Walk + Circles, Gradient, Pixel check), exact 8-bit codes, per face or '
                 'canvas; sync: frame counter + 24-bit strip, sync wheel, flash frame, audio blip. Out: out1 TOP. '
                 'Faces: table `faces` (name x y w h, LED px) or Facestable. Pulse Opencontrols.')
    _close_window(c)
    _pars(c, _pages(Lg))
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)

    lg = _mk(c, textDAT, 'tp_logic')
    lg.text = open(LOGIC_FILE).read()
    lg.comment = 'Pure logic (copy of builders/test_pattern_logic.py; tests in test/test_test_pattern.py).'

    # 1 Faces
    faces = _mk(c, tableDAT, 'faces')
    if faces.numRows < 2 or [x.val for x in faces.row(0)] != Lg['FACE_HEADER']:
        faces.clear()
        faces.appendRows(Lg['DEFAULT_FACES'])
    faces.comment = 'Face table: name, x, y, w, h in LED px (top-left origin). Max 16 faces. Default: one 1920x1080 wall.'
    fch = _script(c, scriptCHOP, 'faces_chop', FACES_CB)
    fch.comment = 'Faces as comp-px rects (x y w h), 16 samples -> GLSL uniform array uFaces.'

    # 2 Clock
    wr = _mk(c, constantCHOP, 'walk_rate')
    wr.par.name0 = 'step'
    _expr(wr.par.value0, P.format('Speed'))
    sp = _mk(c, speedCHOP, 'walk_speed')
    sp.inputConnectors[0].connect(wr)
    sp.comment = 'Walk position in steps: integrates Speed (steps/s). Speed = fps -> one step per frame; 0 parks.'
    uni = _script(c, scriptCHOP, 'uni', UNI_CB)
    uni.comment = 'All GLSL uniforms as channels (tp_logic.uniforms) + blip gate. Cooks per frame only with a clock feature on.'

    # 3 Labels
    cs = _script(c, scriptDAT, 'cab_spec', CABSPEC_CB)
    ss = _script(c, scriptDAT, 'slice_spec', SLICESPEC_CB)
    ct = _text(c, 'cab_text', 'Open Sans', cs)
    _expr(ct.par.resolutionw, P.format('Resx'))
    _expr(ct.par.resolutionh, P.format('Resy'))
    _expr(ct.par.fontsizex, "op('tp_logic').module.cabinet_font(parent().par.Cabw.eval() * %s, parent().par.Cabh.eval() * %s)" % (SC, SC))
    st = _text(c, 'slice_text', 'Open Sans', ss)
    _expr(st.par.resolutionw, P.format('Resx'))
    _expr(st.par.resolutionh, P.format('Resy'))
    _expr(st.par.fontsizex, "op('tp_logic').module.slice_font(op('tp_logic').module.face_rects(op('tp_logic').module.parse_faces([[x.val for x in r] for r in (parent().par.Facestable.eval() or op('faces')).rows()]), parent().par.Resx.eval(), parent().par.Resy.eval(), parent().par.Nativewidth.eval()))")
    for mname, src in (('cab_measure', ct), ('slice_measure', st)):     # not drawn: spec scripts measure text widths
        mt = _text(c, mname, 'Open Sans', None)
        mt.par.resolutionw, mt.par.resolutionh = 8, 8
        _expr(mt.par.fontsizex, src.par.fontsizex.expr)
        mt.comment = 'Not drawn: %s measures label widths with it (evalTextSize) to centre the labels.' % src.par.specdat.eval().name
    lb = _mk(c, compositeTOP, 'labels')
    lb.inputConnectors[0].connect(ct)
    lb.inputConnectors[1].connect(st)
    lb.par.operand = 'add'
    lb.comment = 'Cabinet numbers + slice labels (only one is non-empty at a time). Static: cooks on change only.'
    cnt = _text(c, 'counter_text', 'Menlo', None)
    cnt.par.alignx = 'left'
    cnt.par.text.expr = "op('tp_logic').module.counter_text(op('uni')['uClock0'], op('uni')['uClock1'])"
    cnt.par.text.mode = ParMode.EXPRESSION
    _expr(cnt.par.fontsizex, P.format('Countersize'))
    _expr(cnt.par.resolutionw, "op('tp_logic').module.counter_layout(parent().par.Countersize.eval())[0]")
    _expr(cnt.par.resolutionh, "op('tp_logic').module.counter_layout(parent().par.Countersize.eval())[1]")
    cnt.par.positionx = 2

    # 4 Pattern
    g = _mk(c, glslTOP, 'pattern')
    gl = c.op('pattern_pixel')
    if gl is None:
        gl = _mk(c, textDAT, 'pattern_pixel')
    if gl.dock != g:
        gl.dock = g
    gl.text = open(SHADER_FILE).read()
    g.par.pixeldat = gl
    for dk in list(g.docked):
        if dk.valid and dk.name != 'pattern_pixel':
            _sd(dk)
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, P.format('Resx'))
    _expr(g.par.resolutionh, P.format('Resy'))
    _expr(g.par.format, "'rgba16float' if parent().par.Pattern.eval() == 'gradient' else 'rgba8fixed'")
    g.par.inputfiltertype = 'nearest'
    g.inputConnectors[0].connect(lb)
    g.inputConnectors[1].connect(cnt)
    U = ['uRes', 'uPat', 'uLit', 'uCab', 'uOpt', 'uWheel', 'uClock', 'uCnt', 'uCnt2']
    g.seq.vec.numBlocks = len(U)
    for k, un in enumerate(U):
        getattr(g.par, 'vec%dname' % k).val = un
        for j, comp in enumerate('xyzw'):
            _expr(getattr(g.par, 'vec%dvalue%s' % (k, comp)), "op('uni')['%s%d']" % (un, j))
    g.seq.array.numBlocks = 1
    g.par.array0name = 'uFaces'
    g.par.array0type = 'vec4'
    g.par.array0chop = fch
    g.par.array0arraytype = 'uniformarray'
    g.comment = 'All patterns, wheel, counter and flash in ONE pixel pass (T-46 safe). Exact 8-bit codes (gradient 16F).'
    out1 = _mk(c, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)

    # 5 Audio blip
    osc = _mk(c, audiooscillatorCHOP, 'blip_osc')
    osc.par.wavetype = 'sin'
    _expr(osc.par.frequency, P.format('Blipfreq'))
    _expr(osc.par.amp, "op('uni')['blip'] * parent().par.Blipvol.eval()")
    osc.comment = 'Blip tone, gated on the flash frame (Flashevery) for Bliplen frames. No mic anywhere.'
    ado = _mk(c, audiodeviceoutCHOP, 'blip_out')
    ado.inputConnectors[0].connect(osc)
    ado.par.device = 'BuiltInSpeakerDevice'
    _expr(ado.par.active, P.format('Blip'))
    ado.comment = 'Mac built-in speakers. Active only while Blip is on.'

    pe = _mk(c, parameterexecuteDAT, 'tp_parexec')
    pe.text = PAREXEC
    pe.par.op = c
    pe.par.pars = 'Respreset Resetwalk'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = True
    pe.par.onpulse = True

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=56, cols=8)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'tp_parexec'],
         'body': 'zkit panel + window (pulse Opencontrols); tp_parexec: resolution preset, reset walk.'},
        {'title': '1 Faces', 'role': 'input', 'ops': ['faces', 'faces_chop', 'faces_chop_callbacks', 'tp_logic'],
         'body': 'Face table (name x y w h LED px) -> comp-px rects for the shader.'},
        {'title': '2 Clock + uniforms', 'role': 'process',
         'ops': ['walk_rate', 'walk_speed', 'uni', 'uni_callbacks'],
         'body': 'Walk position (Speed CHOP), uniforms from tp_logic; per-frame only with a clock feature.'},
        {'title': '3 Labels', 'role': 'process',
         'ops': ['cab_measure', 'slice_measure', 'cab_spec', 'cab_spec_callbacks', 'slice_spec', 'slice_spec_callbacks',
                 'cab_text', 'slice_text', 'labels', 'counter_text'],
         'body': 'Text TOPs: cabinet `col-row`, slice labels, frame counter (the only anti-aliased pixels).'},
        {'title': '4 Pattern', 'role': 'output', 'ops': ['pattern', 'pattern_pixel', 'out1'],
         'body': 'One GLSL pass: pattern + face outlines + labels + wheel + counter + flash -> out1.'},
        {'title': '5 Audio blip', 'role': 'output', 'ops': ['blip_osc', 'blip_out'],
         'body': 'Sine at Blipfreq on the flash frame -> built-in speakers (Blip on only).'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    return {'comp': c.path, 'panel': info, 'layout': str(lay)[:400]}
