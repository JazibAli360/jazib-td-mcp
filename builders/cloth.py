# cloth builder - BN_cloth: cloth + soft-body (jelly) COMP, XPBD small steps in compute GLSL (T-46/T-47 safe).
# Spec: docs/research/BN_fluid_cloth_sims.md section 6 (our clean-room design); build notes + live checks:
# docs/builds/cloth.md. Pure logic: builders/cloth_logic.py (tests test/test_cloth.py). Shaders: builders/glsl/cloth_*.
# No limits (user rule): open ranges, no limiter, no warnings; the operator decides.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/cloth.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set, custom par values kept, zkit panel refreshed in place.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy), the COMP's controls_window is closed first (zkit reopens
# it), the panel container is never destroyed, the network pane is never moved here. T-74: no pixel readback here.
# T-67: no functions in op storage. ASCII only.
import os

NAME = 'BN_cloth'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
GLSL_DIR = HERE + '/glsl'
LOGIC_FILE = HERE + '/cloth_logic.py'
ZKIT_FILE = HERE + '/zkit.py'
PANEL_PAGES = ['Sim', 'Wind', 'Collide', 'Look', 'Control']
PP = 'parent().par.'
GW, GH = "int(parent().par.Gridw)", "int(parent().par.Gridh)"

ENGINE_CB = """# engine: cloth_logic.step once per frame -> named channels (1 sample) + STATE['rows'] for `uni`.
# Inputs: 0 = in5 audio CHOP, 1 = in3 colliders CHOP (x y z r, one sample each), 2 = in4 wind CHOP (x y z [strength]).
# Pulses arrive through push(). State is plain data in this module (T-67), not in op storage.
STATE = {'st': None, 'ev': [], 'rows': None}

def push(e):
    STATE['ev'].append(e)

def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def _ch(o, n):
    if o is None or not o.numChans:
        return None
    return o[n]

def onCook(scriptOp):
    L = op('cloth_logic').module
    P = parent()
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    p = {}
    for q in P.customPars:
        if q.style in ('Pulse', 'Momentary', 'Header'):
            continue
        p[q.name.lower()] = q.eval()
    ins = scriptOp.inputs
    au = ins[0] if len(ins) > 0 else None
    level = None
    if au is not None and au.numChans:
        vals = []
        for c in au.chans()[:2]:
            vals.extend(c.vals)
        level = L.audio_level(vals)
    cols = []
    co = ins[1] if len(ins) > 1 else None
    if co is not None and all(_ch(co, n) is not None for n in 'xyzr'):
        for s in range(min(L.NSPHERES, co.numSamples)):
            cols.append(tuple(float(co[n][s]) for n in 'xyzr'))
    wd = None
    wo = ins[2] if len(ins) > 2 else None
    if wo is not None and all(_ch(wo, n) is not None for n in 'xyz'):
        k = float(wo['strength'][0]) if wo['strength'] is not None else 1.0
        wd = tuple(float(wo[n][0]) * k for n in 'xyz')
    cov = None
    if p.get('mode') == 'jelly':                 # only then is the cov chain pulled (it cooks only in jelly mode)
        cv = op('cov')
        if cv is not None and cv.numChans:
            cov = {}
            for c in cv.chans():                 # TOP to CHOP adds the row index: a000 -> a00 (T-84)
                cov[c.name] = float(c[0])
                if c.name.endswith('0'):
                    cov.setdefault(c.name[:-1], float(c[0]))
    ev = STATE['ev']
    STATE['ev'] = []
    st, o = L.step(STATE['st'], absTime.seconds, {'level': level, 'colliders': cols, 'wind': wd, 'cov': cov,
                                                  'cookrate': project.cookRate}, p, ev, P.fetch('jz_smax', L.SMAX, search=False))
    STATE['st'] = st
    STATE['rows'] = o['rows']
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for n in L.ENGINE_CHANS:
        scriptOp.appendChan(n)[0] = float(o[n])
    return
"""

UNI_CB = """# uni: the engine's uniform rows as a vec4 array CHOP (channels x y z w, one sample per row = cloth_logic.ROWS).
# Read by every cloth compute shader as `uniform samplerBuffer uP` (array0, texturebuffer). Input 0 = engine (order).
def onCook(scriptOp):
    L = op('cloth_logic').module
    rows = op('engine_callbacks').module.STATE.get('rows')
    if not rows or len(rows) != L.NROWS:
        _, o = L.step(None, absTime.seconds, {}, L.DEFAULTS)
        rows = o['rows']
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = L.NROWS
    for k, n in enumerate('xyzw'):
        scriptOp.appendChan(n).vals = [float(r[k]) for r in rows]
    return
"""

STATS_CB = """# stats: out3 numbers. Inputs: 0 = st_avg_chop (Analyze average), 1 = st_max_chop (Analyze maximum), 2 = engine.
def _d(o):
    # TOP to CHOP names a 1-row image's channels <name>0 on 31550 (T-84): keep both spellings
    d = {}
    if o is not None and o.numChans:
        for c in o.chans():
            d[c.name] = float(c[0])
            if c.name.endswith('0'):
                d.setdefault(c.name[:-1], float(c[0]))
    return d

def onCook(scriptOp):
    L = op('cloth_logic').module
    ins = scriptOp.inputs
    avg = _d(ins[0] if len(ins) > 0 else None)
    mx = _d(ins[1] if len(ins) > 1 else None)
    en = _d(ins[2] if len(ins) > 2 else None)
    s = L.stats_from(avg, mx, int(parent().par.Gridw), int(parent().par.Gridh))
    for k in ('steps', 'beat', 'burst', 'kicks', 'released'):
        s[k] = en.get(k, 0.0)
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for n in L.STATS_CHANS:
        scriptOp.appendChan(n)[0] = float(s[n])
    return
"""

PULSES = """# cloth_pulses: Reset / Step / Release / Burst -> engine (applied on the next engine cook).
def onPulse(par):
    n = par.name
    if n in ('Reset', 'Step', 'Release', 'Burst'):
        parent().op('engine_callbacks').module.push(n.lower())
    return
"""


def _logic():
    ns = {}
    exec(open(LOGIC_FILE).read(), ns)
    return ns


def _shader(Lg, name):
    body = open(os.path.join(GLSL_DIR, name + '.glsl')).read()
    return Lg['glsl_header']() + body


def _menu(names, labels=None):
    return {'names': names, 'labels': labels or [n.capitalize() for n in names]}


def _pages(Lg):
    D = Lg['DEFAULTS']
    return [
        ('Sim', [
            ('Gridw', 'Int', D['gridw'], {'min': 8, 'max': 512, 'label': 'Grid width (vertices)'}),
            ('Gridh', 'Int', D['gridh'], {'min': 8, 'max': 512, 'label': 'Grid height (vertices)'}),
            ('Mode', 'Menu', D['mode'], _menu(Lg['MODES'], ['Cloth', 'Jelly (shape matching)'])),
            ('Substeps', 'Int', D['substeps'], {'min': 1, 'max': Lg['SMAX'], 'label': 'Substeps per frame'}),
            ('Dt', 'Float', D['dt'], {'min': 0, 'max': 0.05, 'label': 'Dt s (0 = 1/cook rate)'}),
            ('Timescale', 'Float', D['timescale'], {'min': 0, 'max': 2, 'label': 'Time scale'}),
            ('Gravity', 'XYZ', (D['gravityx'], D['gravityy'], D['gravityz']), {'label': 'Gravity m/s2'}),
            ('Damping', 'Float', D['damping'], {'min': 0, 'max': 10, 'label': 'Damping 1/s'}),
            ('Stretch', 'Float', D['stretch'], {'min': 0, 'max': 0.01, 'label': 'Stretch compliance'}),
            ('Shear', 'Float', D['shear'], {'min': 0, 'max': 0.01, 'label': 'Shear compliance'}),
            ('Bend', 'Float', D['bend'], {'min': 0, 'max': 1, 'label': 'Bend compliance'}),
            ('Relax', 'Float', D['relax'], {'min': 0, 'max': 2, 'label': 'Jacobi relax'}),
            ('Shape', 'Float', D['shape'], {'min': 0, 'max': 1, 'label': 'Jelly shape stiffness'}),
            ('Mass', 'Float', D['mass'], {'min': 0.01, 'max': 10, 'label': 'Mass kg (whole cloth)'}),
            ('Sizew', 'Float', D['sizew'], {'min': 0.1, 'max': 4, 'label': 'Width m'}),
            ('Sizeh', 'Float', D['sizeh'], {'min': 0.1, 'max': 4, 'label': 'Height m'}),
            ('Orient', 'Menu', D['orient'], _menu(Lg['ORIENTS'], ['Vertical (hangs)', 'Horizontal (drops)'])),
            ('Top', 'Float', D['top'], {'min': -2, 'max': 3, 'label': 'Top edge / plane y m'}),
            ('Pins', 'Menu', D['pins'], _menu(Lg['PINMODES'], Lg['PIN_LABELS'])),
            ('Tethers', 'Toggle', D['tethers'], {'label': 'Tethers to pins'}),
            ('Tetherslack', 'Float', D['tetherslack'], {'min': 1, 'max': 1.5, 'label': 'Tether slack'}),
            ('Floor', 'Toggle', D['floor'], {'label': 'Floor'}),
            ('Floory', 'Float', D['floory'], {'min': -3, 'max': 1, 'label': 'Floor y m'}),
        ]),
        ('Wind', [
            ('Windmode', 'Menu', D['windmode'], _menu(Lg['WINDMODES'], ['Off', 'Constant', 'Noise gusts',
                                                                     'Audio level', 'BPM bursts'])),
            ('Wind', 'XYZ', (D['windx'], D['windy'], D['windz']), {'label': 'Wind m/s2'}),
            ('Windgain', 'Float', D['windgain'], {'min': 0, 'max': 4, 'label': 'Wind gain'}),
            ('Aero', 'Float', D['aero'], {'min': 0, 'max': 1, 'label': 'Aero (normal pressure)'}),
            ('Turbulence', 'Float', D['turbulence'], {'min': 0, 'max': 2, 'label': 'Turbulence'}),
            ('Turbscale', 'Float', D['turbscale'], {'min': 0.1, 'max': 10, 'label': 'Turbulence scale 1/m'}),
            ('Gust', 'Float', D['gust'], {'min': 0, 'max': 4, 'label': 'Gust rate Hz'}),
            ('Bpm', 'Float', D['bpm'], {'min': 20, 'max': 300, 'label': 'BPM'}),
            ('Bpmdiv', 'Menu', D['bpmdiv'], _menu(Lg['BPMDIVS'], Lg['BPMDIV_LABELS'])),
            ('Burst', 'Pulse', None, {'label': 'Burst'}),
            ('Burstforce', 'Float', D['burstforce'], {'min': 0, 'max': 100, 'label': 'Burst m/s2'}),
            ('Burstdecay', 'Float', D['burstdecay'], {'min': 0, 'max': 2, 'label': 'Burst decay s'}),
            ('Audiogain', 'Float', D['audiogain'], {'min': 0, 'max': 10, 'label': 'Audio gain'}),
            ('Burstthresh', 'Float', D['burstthresh'], {'min': 0, 'max': 1, 'label': 'Kick threshold'}),
            ('Burstrefractory', 'Float', D['burstrefractory'], {'min': 0, 'max': 1, 'label': 'Kick gap s'}),
        ]),
        ('Collide', [
            ('Friction', 'Float', D['friction'], {'min': 0, 'max': 1, 'label': 'Friction'}),
            ('Thickness', 'Float', D['thickness'], {'min': 0, 'max': 0.1, 'label': 'Thickness m'}),
        ] + [x for k in range(1, 5) for x in (
            ('Sphere%don' % k, 'Toggle', D['sphere%don' % k], {'label': 'Sphere %d' % k}),
            ('Sphere%d' % k, 'XYZ', (D['sphere%dx' % k], D['sphere%dy' % k], D['sphere%dz' % k]),
             {'label': 'Sphere %d centre' % k}),
            ('Sphere%dr' % k, 'Float', D['sphere%dr' % k], {'min': 0, 'max': 2, 'label': 'Sphere %d radius' % k}))]),
        ('Look', [
            ('Resw', 'Int', 1080, {'min': 64, 'max': 3840, 'label': 'Render width'}),
            ('Resh', 'Int', 1920, {'min': 64, 'max': 3840, 'label': 'Render height'}),
            ('Cam', 'Menu', D['cam'], _menu(Lg['CAMS'])),
            ('Camdist', 'Float', D['camdist'], {'min': 0.5, 'max': 10, 'label': 'Camera distance m'}),
            ('Camelev', 'Float', D['camelev'], {'min': -89, 'max': 89, 'label': 'Camera elevation deg'}),
            ('Orbitspeed', 'Float', D['orbitspeed'], {'min': -90, 'max': 90, 'label': 'Orbit deg/s'}),
            ('Fov', 'Float', D['fov'], {'min': 5, 'max': 120, 'label': 'Horizontal FOV deg'}),
            ('Light', 'XYZ', (1.5, 2.5, 3.0), {'label': 'Light position'}),
            ('Shading', 'Menu', 'sheen', _menu(Lg['SHADINGS'])),
            ('Colorfront', 'RGB', (0.85, 0.12, 0.25), {'label': 'Front colour'}),
            ('Colorback', 'RGB', (0.15, 0.2, 0.55), {'label': 'Back colour'}),
            ('Texture', 'Menu', 'checker', _menu(Lg['TEXTURES'], ['Checker', 'in1 TOP', 'None'])),
            ('Texmix', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Texture mix'}),
            ('Texscale', 'Float', 12.0, {'min': 1, 'max': 64, 'label': 'Checker cells'}),
            ('Wire', 'Toggle', False, {'label': 'Wire grid'}),
            ('Bg', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background'}),
            ('Alpha', 'Toggle', False, {'label': 'Transparent background'}),
        ]),
        ('Control', [
            ('Reset', 'Pulse', None, {'label': 'Reset'}),
            ('Pause', 'Toggle', False, {'label': 'Pause'}),
            ('Step', 'Pulse', None, {'label': 'Step (paused)'}),
            ('Release', 'Pulse', None, {'label': 'Release pins'}),
            ('Testmode', 'Menu', D['testmode'], _menu(Lg['TESTMODES'], ['Off', 'Rest (no forces)',
                                                                     'Fixed (deterministic)'])),
            ('Seed', 'Int', D['seed'], {'min': 0, 'max': 100, 'label': 'Seed'}),
        ]),
    ]


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None:
                continue
            if style in ('RGB', 'XYZ') and getattr(c.par, name + ('r' if style == 'RGB' else 'x'), None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
                p.default = default
                p.val = default
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']      # slider range only: no clamps (no limits)
                p.default = default
                p.val = default
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
                p.clampMin, p.min = True, 1                    # structural: grid / substep counts >= 1
                p.default = default
                p.val = default
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style in ('RGB', 'XYZ'):
                grp = page.appendRGB(name, label=label) if style == 'RGB' else page.appendXYZ(name, label=label)
                for p, v in zip(grp, default):
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


def _mk(c, cls, name, viewer=True):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        o.viewer = viewer
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = viewer
    return o


def _expr(par, e):
    par.expr = str(e)
    par.mode = ParMode.EXPRESSION


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _text(c, name, txt, dock=None, comment=None):
    t = _mk(c, textDAT, name)
    if t.text != txt:
        t.text = txt
    if dock is not None and t.dock is not dock:
        t.dock = dock
    if comment:
        t.comment = comment
    return t


def _compute(c, name, dat_name, w_expr, h_expr, fmt='rgba32float', comment='', viewer=True):
    """Compute-mode GLSL TOP (T-47) reading its shader from `dat_name` (a shared Text DAT is fine)."""
    g = _mk(c, glslTOP, name, viewer)
    g.par.mode = 'compute'
    g.par.computedat = dat_name
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w_expr)
    _expr(g.par.resolutionh, h_expr)
    g.par.format = fmt
    g.par.autodispatchsize = True
    g.par.inputfiltertype = 'nearest'
    g.par.npasses.mode = ParMode.CONSTANT       # an earlier chain='npasses' build left an expression
    g.par.npasses = 1
    if comment:
        g.comment = comment
    for dn in ('_info', '_pixel', '_compute', '_vertex'):    # GLSL TOP docks its own DATs; ours is the compute DAT
        d = c.op(name + dn)
        if d is not None and d.name != dat_name:
            _sd(d)
    return g


def _uni(g):
    """array0 = the `uni` CHOP as `uniform samplerBuffer uP` (texturebuffer, as builders/face_track.py)."""
    g.seq.array.numBlocks = max(int(g.seq.array.numBlocks), 1)
    g.par.array0name = 'uP'
    g.par.array0type = 'vec4'
    g.par.array0chop = 'uni'
    g.par.array0arraytype = 'texturebuffer'


def _vecs(g, U):
    g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), len(U))
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            p = getattr(g.par, 'vec{}value{}'.format(k, comp))
            if isinstance(e, (int, float)):
                p.mode = ParMode.CONSTANT
                p.val = e
            else:
                _expr(p, e)


def _mi(menu, par):
    return "op('cloth_logic').module.menu_index(op('cloth_logic').module.%s, parent().par.%s.eval())" % (menu, par)


def _wired(c_name):
    """1 when the COMP input connector feeding In op `c_name` is wired (31550: an In op's .inputs stays empty)."""
    return ("any(len(cn.connections) for cn in parent().inputConnectors if cn.inOP is not None and "
            "cn.inOP.name == '%s')" % c_name)


def _eff_hook(c):
    """Shared effectors adapter (builders/effectors.py attach, docs/builds/effectors.md): Effectors page + a few ops,
    idempotent, run after every build; a failure is reported, never a broken build."""
    try:
        ns = dict(globals())
        exec(open(REPO + '/builders/effectors.py').read(), ns)
        return ns['attach'](c.path)
    except Exception as e:
        return 'effectors adapter skipped: %s' % e


def build(parent_path='/project1/lab', panel=True, smax=None, chain='unrolled'):
    """chain = 'unrolled' (sub_01..sub_NN, Substeps picks how many cook) or 'npasses' (ONE node, npasses =
    Substeps; only after LIVE CHECK P2 proves a compute GLSL TOP feeds pass n into input 0 of pass n+1)."""
    Lg = _logic()
    smax = int(smax or Lg['SMAX'])
    pc = op(parent_path)
    c = pc.op(NAME) or pc.create(baseCOMP, NAME)
    c.allowCooking = True                       # never parked while being built (user rule)
    c.comment = ('BN_cloth: cloth + jelly sim (XPBD small steps, compute GLSL). In: in1 TOP texture, in2 TOP pin mask, '
                 'in3 CHOP colliders (x y z r), in4 CHOP wind (x y z strength), in5 CHOP audio. Out: out1 TOP render, '
                 'out2 TOP positions (rgba32f, Gridw x Gridh), out3 CHOP stats. No limits. Pulse Opencontrols.')
    _close_window(c)
    _pars(c, _pages(Lg))
    c.store('jz_smax', smax if chain == 'unrolled' else Lg['SMAX'])     # plain int (T-67)

    # 1 Inputs
    in1 = _mk(c, inTOP, 'in1')
    in2 = _mk(c, inTOP, 'in2')
    in3 = _mk(c, inCHOP, 'in3')
    in4 = _mk(c, inCHOP, 'in4')
    in5 = _mk(c, inCHOP, 'in5')
    tb = _mk(c, constantTOP, 'tex_blank')
    tb.par.outputresolution = 'custom'
    tb.par.resolutionw, tb.par.resolutionh = 8, 8
    tb.par.colorr = tb.par.colorg = tb.par.colorb = 1.0
    tb.par.alpha = 1.0
    tsw = _mk(c, switchTOP, 'tex_src')
    _wire(tb, tsw, 0)
    _wire(in1, tsw, 1)
    _expr(tsw.par.index, "(1 if parent().par.Texture.eval() == 'in1' and %s else 0)" % _wired('in1'))
    tsw.comment = 'Cloth texture: in1 when Texture = in1 and wired, else white (checker is procedural).'
    pb = _mk(c, constantTOP, 'pin_blank')
    pb.par.outputresolution = 'custom'
    pb.par.resolutionw, pb.par.resolutionh = 8, 8
    pb.par.colorr = pb.par.colorg = pb.par.colorb = 0.0
    pb.par.alpha = 1.0
    psw = _mk(c, switchTOP, 'pin_src')
    _wire(pb, psw, 0)
    _wire(in2, psw, 1)
    _expr(psw.par.index, "(1 if parent().par.Pins.eval() == 'mask' and %s else 0)" % _wired('in2'))
    psw.comment = 'Pin mask (Pins = mask): in2 luma > 0.5 pins a vertex; black when not wired.'

    # 2 Engine
    _text(c, 'cloth_logic', open(LOGIC_FILE).read(),
          comment='Pure logic (copy of builders/cloth_logic.py; tests test/test_cloth.py).')
    eng = _mk(c, scriptCHOP, 'engine')
    _text(c, 'engine_callbacks', ENGINE_CB, dock=eng)
    eng.par.callbacks = 'engine_callbacks'
    _wire(in5, eng, 0)
    _wire(in3, eng, 1)
    _wire(in4, eng, 2)
    eng.par.setuppars.pulse()
    eng.comment = 'Per frame: wind / BPM / audio kicks / bursts / reset / pause / release / camera -> uniform rows.'
    uni = _mk(c, scriptCHOP, 'uni')
    _text(c, 'uni_callbacks', UNI_CB, dock=uni)
    uni.par.callbacks = 'uni_callbacks'
    _wire(eng, uni, 0)
    uni.comment = 'vec4 uP[%d] (x y z w, one sample per row) for every cloth shader.' % Lg['NROWS']
    pulses = _mk(c, parameterexecuteDAT, 'cloth_pulses')
    pulses.text = PULSES
    pulses.par.op = c
    pulses.par.pars = 'Reset Step Release Burst'
    pulses.par.custom = True
    pulses.par.builtin = False
    pulses.par.valuechange = False
    pulses.par.onpulse = True

    # 3 Rest + state
    _text(c, 'rest_compute', _shader(Lg, 'cloth_rest'))
    rest = _compute(c, 'rest', 'rest_compute', GW, GH, comment='Rest shape (xyz) + pin flag (w). Cooks on par change.')
    _wire(psw, rest, 0)
    _vecs(rest, [('uRestA', [PP + 'Gridw', PP + 'Gridh', PP + 'Sizew', PP + 'Sizeh']),
                 ('uRestB', ["1 if parent().par.Orient.eval() == 'horizontal' else 0", PP + 'Top',
                             _mi('PINMODES', 'Pins'), 0])])
    _text(c, 'init_compute', _shader(Lg, 'cloth_init'))
    ini = _compute(c, 'state_init', 'init_compute', GW + ' * 2', GH, comment='Initial state: rest + zero velocity.')
    _wire(rest, ini, 0)
    fb = _mk(c, feedbackTOP, 'state_fb')
    _wire(ini, fb, 0)
    fb.comment = 'Last frame state (2W x H: positions | velocities). Loop closes at `state`.'
    _text(c, 'nrm_compute', _shader(Lg, 'cloth_nrm'))
    nrm = _compute(c, 'nrm', 'nrm_compute', GW, GH, comment='Frame-start normals for the wind term.')
    _wire(fb, nrm, 0)
    _vecs(nrm, [('uGrid', [PP + 'Gridw', PP + 'Gridh', 0, 0])])

    # 4 Substeps (one fused XPBD pass each)
    _text(c, 'substep_compute', _shader(Lg, 'cloth_substep'))
    n_nodes = smax if chain == 'unrolled' else 1
    subs = []
    prev = fb
    for k in range(1, n_nodes + 1):
        s = _compute(c, 'sub_%02d' % k, 'substep_compute', GW + ' * 2', GH, viewer=(k == 1),
                     comment=('Substep %d: predict, Jacobi (12-stencil, XPBD), tethers, collide, velocity.' % k)
                     if k == 1 else '')
        _wire(prev, s, 0)
        _wire(rest, s, 1)
        _wire(nrm, s, 2)
        _uni(s)
        prev = s
        subs.append(s)
    k = n_nodes + 1
    while c.op('sub_%02d' % k) is not None:     # an earlier build with more substeps
        _sd(c.op('sub_%02d' % k))
        k += 1
    if chain == 'npasses':
        _expr(subs[0].par.npasses, 'max(1, int(parent().par.Substeps))')
    sel = _mk(c, switchTOP, 'sub_sel')
    for i, s in enumerate(subs):
        _wire(s, sel, i)
    _expr(sel.par.index, "max(0, min(int(parent().par.Substeps), %d) - 1)" % n_nodes if chain == 'unrolled' else '0')
    sel.comment = 'Picks the output after Substeps passes (only that chain cooks).'
    state = _mk(c, nullTOP, 'state')
    _wire(sel, state, 0)
    fb.par.top = state

    # 5 Jelly (shape matching): cooks only when Mode = jelly (the engine reads `cov` then)
    _text(c, 'cov_compute', _shader(Lg, 'cloth_cov'))
    chops = []
    for g, ax in enumerate('xyz'):
        cv = _compute(c, 'cov_' + ax, 'cov_compute', GW, GH, viewer=False,
                      comment='Jelly covariance row %s (p_%s q, p_%s) from state_fb.' % (ax, ax, ax) if g == 0 else '')
        _wire(fb, cv, 0)
        _wire(rest, cv, 1)
        _uni(cv)
        _vecs(cv, [('uCov', [g, 0, 0, 0])])
        an = _mk(c, analyzeTOP, 'cov_%s_avg' % ax, viewer=False)
        _wire(cv, an, 0)
        an.par.op = 'average'
        an.par.analyzechannel = 'independent'
        tc = _mk(c, toptoCHOP, 'cov_%s_chop' % ax, viewer=False)
        tc.par.top = an
        tc.par.crop = 'full'
        tc.par.outputcolorspace = 'passthrough'
        tc.par.downloadtype = 'nextframe'
        names = Lg['COV_CHANS'][g * 4:g * 4 + 4]
        tc.par.r, tc.par.g, tc.par.b, tc.par.a = names
        chops.append(tc)
    cov = _mk(c, mergeCHOP, 'cov', viewer=False)
    for i, tc in enumerate(chops):
        _wire(tc, cov, i)
    cov.comment = 'Jelly: mean p q^T rows + centroid (12 channels, cloth_logic.COV_CHANS) -> engine (rotation).'

    # 6 Render
    _text(c, 'pos_compute', _shader(Lg, 'cloth_pos'))
    pos = _compute(c, 'pos', 'pos_compute', GW, GH, comment='Positions (xyz, w 1) = out2; cooks only when out2 is used (the MAT reads state).')
    _wire(state, pos, 0)
    out2 = _mk(c, outTOP, 'out2')
    _wire(pos, out2, 0)
    vd = _text(c, 'cloth_vertex', _shader(Lg, 'cloth_vert'))
    pd = _text(c, 'cloth_pixel', _shader(Lg, 'cloth_frag'))
    mat = _mk(c, glslMAT, 'cloth_mat')
    mat.par.vdat = vd.name
    mat.par.pdat = pd.name
    for dn in ('_vertex', '_pixel', '_info'):
        d = c.op('cloth_mat' + dn)
        if d is not None and d.name not in (vd.name, pd.name):
            _sd(d)
    vd.dock = mat
    pd.dock = mat
    mat.seq.sampler.numBlocks = max(int(mat.seq.sampler.numBlocks), 2)
    # sPos reads `state` (left half = the positions `pos` copies), so `pos` cooks only when out2 is used (perf wave 3)
    for k, (sn, top, flt, ext) in enumerate((('sPos', state, 'nearest', 'hold'), ('sTex', tsw, 'linear', 'repeat'))):
        getattr(mat.par, 'sampler%dname' % k).val = sn
        getattr(mat.par, 'sampler%dtop' % k).val = top
        getattr(mat.par, 'sampler%dfilter' % k).val = flt
        getattr(mat.par, 'sampler%dextendu' % k).val = ext
        getattr(mat.par, 'sampler%dextendv' % k).val = ext
    E = "op('engine')['%s']"
    _vecs(mat, [('uGrid', [PP + 'Gridw', PP + 'Gridh', 0, 0]),
                ('uLook0', [_mi('SHADINGS', 'Shading'), _mi('TEXTURES', 'Texture'), PP + 'Texmix',
                            "1 if parent().par.Wire else 0"]),
                ('uLook1', [PP + 'Lightx', PP + 'Lighty', PP + 'Lightz', PP + 'Texscale']),
                ('uFront', [PP + 'Colorfrontr', PP + 'Colorfrontg', PP + 'Colorfrontb', 1]),
                ('uBack', [PP + 'Colorbackr', PP + 'Colorbackg', PP + 'Colorbackb', 1]),
                ('uCam', [E % 'cam_tx', E % 'cam_ty', E % 'cam_tz', 0])])
    mat.par.cullface = 'neither'
    mat.comment = 'Grid displaced by `state` (left half, vertex texture fetch), double-sided, own lighting.'
    geo = _mk(c, geometryCOMP, 'cloth_geo')
    for ch in list(geo.children):
        if ch.name != 'grid':
            _sd(ch)
    gr = geo.op('grid') or geo.create(gridSOP, 'grid')
    gr.par.type = 'mesh'
    gr.par.surftype = 'quads'
    gr.par.orient = 'xy'
    _expr(gr.par.rows, 'int(parent(2).par.Gridh)')
    _expr(gr.par.cols, 'int(parent(2).par.Gridw)')
    _expr(gr.par.sizex, 'parent(2).par.Sizew')
    _expr(gr.par.sizey, 'parent(2).par.Sizeh')
    gr.par.texture = 'rowcol'
    gr.render = True
    gr.display = True
    geo.par.material = mat
    geo.comment = 'Grid SOP (Gridw x Gridh points, uv rowcol); positions come from the MAT, not the SOP.'
    cam = _mk(c, cameraCOMP, 'cam')
    for k in ('tx', 'ty', 'tz', 'rx', 'ry'):
        _expr(getattr(cam.par, k), E % ('cam_' + k))
    cam.par.rz = 0
    cam.par.rord = 'xyz'
    cam.par.viewanglemethod = 'horzfov'
    _expr(cam.par.fov, PP + 'Fov')
    cam.par.near = 0.05
    cam.par.far = 100
    cam.comment = 'Camera from the engine (Cam front / orbit / top / side, Camdist, Camelev, Orbitspeed).'
    rn = _mk(c, renderTOP, 'render')
    rn.par.camera = cam
    rn.par.geometry = geo
    rn.par.lights = ''
    rn.par.outputresolution = 'custom'
    _expr(rn.par.resolutionw, PP + 'Resw')
    _expr(rn.par.resolutionh, PP + 'Resh')
    rn.par.format = 'rgba8fixed'
    rn.par.antialias = 'aa4'
    rn.par.cullface = 'neither'
    for ch, src in (('r', 'Bgr'), ('g', 'Bgg'), ('b', 'Bgb')):
        _expr(getattr(rn.par, 'bgcolor' + ch), PP + src)
    _expr(rn.par.bgcolora, '0 if parent().par.Alpha else 1')
    rn.comment = 'Render (Resw x Resh, premultiplied alpha when Alpha is on).'
    out1 = _mk(c, outTOP, 'out1')
    _wire(rn, out1, 0)

    # 7 Stats
    _text(c, 'stats_compute', _shader(Lg, 'cloth_stats'))
    stx = _compute(c, 'stats_tex', 'stats_compute', GW, GH, comment='Per vertex: max strain, energy, NaN, mean strain.')
    _wire(state, stx, 0)
    _wire(rest, stx, 1)
    _uni(stx)
    tcs = []
    for nm, opn, chans in (('st_avg', 'average', Lg['STATS_AVG_CHANS']), ('st_max', 'maximum', Lg['STATS_MAX_CHANS'])):
        an = _mk(c, analyzeTOP, nm)
        _wire(stx, an, 0)
        an.par.op = opn
        an.par.analyzechannel = 'independent'
        tc = _mk(c, toptoCHOP, nm + '_chop')
        tc.par.top = an
        tc.par.crop = 'full'
        tc.par.outputcolorspace = 'passthrough'
        tc.par.downloadtype = 'nextframe'
        tc.par.r, tc.par.g, tc.par.b, tc.par.a = chans
        tcs.append(tc)
    sts = _mk(c, scriptCHOP, 'stats')
    _text(c, 'stats_callbacks', STATS_CB, dock=sts)
    sts.par.callbacks = 'stats_callbacks'
    _wire(tcs[0], sts, 0)
    _wire(tcs[1], sts, 1)
    _wire(eng, sts, 2)
    out3 = _mk(c, outCHOP, 'out3')
    _wire(sts, out3, 0)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=56, cols=8)

    sub_names = [s.name for s in subs]
    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'cloth_pulses'],
         'body': 'zkit panel + window (pulse Opencontrols); cloth_pulses: Reset / Step / Release / Burst -> engine.'},
        {'title': '1 Inputs', 'role': 'input',
         'ops': ['in1', 'tex_blank', 'tex_src', 'in2', 'pin_blank', 'pin_src', 'in3', 'in4', 'in5'],
         'body': 'in1 texture, in2 pin mask, in3 colliders, in4 wind, in5 audio (all optional).'},
        {'title': '2 Engine', 'role': 'process', 'ops': ['cloth_logic', 'engine', 'engine_callbacks', 'uni',
                                                        'uni_callbacks'],
         'body': 'Script CHOP per frame (cloth_logic.step) -> uni: vec4 uP[] rows for every shader.'},
        {'title': '3 Rest + state', 'role': 'process',
         'ops': ['rest', 'rest_compute', 'state_init', 'init_compute', 'state_fb', 'nrm', 'nrm_compute'],
         'body': 'Rest shape + pins; state_fb = last frame (positions | velocities); frame-start normals.'},
        {'title': '4 Substeps (XPBD small steps)', 'role': 'process',
         'ops': sub_names + ['substep_compute', 'sub_sel', 'state'],
         'body': 'One fused compute pass per substep; sub_sel picks Substeps; state closes the feedback loop.'},
        {'title': '5 Jelly', 'role': 'analysis',
         'ops': ['cov_compute'] + ['cov_%s%s' % (a, s) for a in 'xyz' for s in ('', '_avg', '_chop')] + ['cov'],
         'body': 'Shape matching: mean p q^T -> engine rotation (cooks only in Mode = jelly).'},
        {'title': '6 Render', 'role': 'output',
         'ops': ['pos', 'pos_compute', 'out2', 'cloth_mat', 'cloth_vertex', 'cloth_pixel', 'cloth_geo', 'cam',
                 'render', 'out1'],
         'body': 'pos -> out2 (cooks only when used); Grid displaced by state in a GLSL MAT, own lighting -> render -> out1.'},
        {'title': '7 Stats', 'role': 'analysis',
         'ops': ['stats_tex', 'stats_compute', 'st_avg', 'st_max', 'st_avg_chop', 'st_max_chop', 'stats',
                 'stats_callbacks', 'out3'],
         'body': 'maxstretch meanstretch energy nan steps beat burst kicks released -> out3.'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    eff = _eff_hook(c)
    return {'effectors': str(eff)[:300],
            'comp': c.path, 'substep_nodes': n_nodes, 'chain': chain, 'panel': str(info)[:300],
            'layout': str(lay)[:400]}
