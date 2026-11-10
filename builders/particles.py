# particles builder - BO_particles: GPU particle system (compute GLSL TOP state + instanced GLSL MAT render).
# Spec: docs/research/BO_particle_sims.md section 4 (engine B: compute TOP; the POP engine A is not built, see
# docs/builds/particles.md). Clean-room; design credits in the spec (Tim Gerritsen CC BY 4.0, Bridson et al. 2007).
# No limits (user rule 26 Oct): open ranges, no clamps on the look, the operator decides.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/particles.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set; custom par values kept; zkit panel refreshed in place.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy); the COMP's controls_window is closed before a rebuild;
# the panel container is never destroyed; the network pane is never moved here. No functions in op storage (T-67).
# T-74/T-76: no numpyArray()/evalTextSize() anywhere in this builder. Never touches cookRate (T-64). ASCII only.
import os

NAME = 'BO_particles'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = os.path.join(REPO, 'builders')
LOGIC_FILE = os.path.join(HERE, 'particles_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
GLSL_DIR = os.path.join(HERE, 'glsl')
PXLINES_FILE = os.path.join(HERE, 'px_lines.py')                # PX_lines builder (imported, never edited here)
PALMAP_FILE = os.path.join(HERE, 'palette_map_logic.py')        # W1-B palette (read only)
PALETTE_GLSL = os.path.join(GLSL_DIR, 'px_palette.glsl')
CLIP = os.path.join(REPO, 'media', 'webcam', 'webcam_ref_5s.mp4')
LG = "op('particles_logic').module"
PP = 'parent().par.'

ENGINE_CB = """# engine: once per frame, particles_logic.step -> the vec4 uniform rows uP[] (samples) for state + pmat.
# Input 0 = in_ctl (optional control CHOP). Pulses arrive through push(). State lives here (plain dict).
STATE = {'st': None, 'ev': [], 'frame': None, 'out': None, 'pars': None, 'npars': 0}

def push(e):
    STATE['ev'].append(e)

def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def _ctl(scriptOp, P, L):
    o = P.par.Chop.eval()
    if o is None or not getattr(o, 'isCHOP', False):
        o = scriptOp.inputs[0] if len(scriptOp.inputs) else None
    vals = {}
    if o is not None:
        for n in L.CTL_CHANS:
            ch = o[n]
            if ch is not None:
                vals[n] = float(ch.eval())
    return vals

def onCook(scriptOp):
    L = op('particles_logic').module
    P = parent()
    f = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else absTime.frame
    if STATE['out'] is None or STATE['frame'] != f:       # one sim step per frame, even if cooked twice
        pl = STATE.get('pars')
        if pl is None or STATE.get('npars') != len(P.customPars):   # par list cached (rebuilt when pars change)
            pl = [p for p in P.customPars if p.style != 'Pulse' and p.page.name not in ('Zkit', 'Lines')]
            STATE['pars'], STATE['npars'] = pl, len(P.customPars)
        raw = {}
        for p in pl:
            v = p.eval()
            if isinstance(v, (bool, int, float, str)):
                raw[p.name] = v
        ev = STATE['ev']
        STATE['ev'] = []
        ctl = _ctl(scriptOp, P, L) if raw.get('Audiosrc') == 'chop' else None
        STATE['st'], STATE['out'] = L.step(STATE['st'], raw, ctl, ev, absTime.seconds)
        STATE['frame'] = f
    rows = STATE['out']['rows']
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = len(rows)
    chans = [scriptOp.appendChan(n) for n in ('x', 'y', 'z', 'w')]
    for i, r in enumerate(rows):
        for ch, v in zip(chans, r):
            ch[i] = float(v)
    return
"""

INFO_CB = """# info: the engine's per-frame numbers as named channels (frame simt dt reset head births count side curlk size
# bright kick bass mid high level beat phase). Input 0 = engine (cook order only).
def onCook(scriptOp):
    out = op('engine_callbacks').module.STATE.get('out')
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    if out:
        for k, v in out['info'].items():
            scriptOp.appendChan(k)[0] = float(v)
    return
"""

PULSES = """# particles_pulses: Reset / Burst -> engine (applied on the next engine cook).
def onPulse(par):
    eng = parent().op('engine_callbacks').module
    if par.name == 'Reset':
        eng.push('reset')
    elif par.name == 'Burst':
        eng.push('burst')
    return
"""

PAL_CTL = ["parent().par.Palshift.eval()", "parent().par.Palmode.menuIndex", "parent().par.Palinterp.menuIndex"]
PAL_CB = """# pal: W1-B palette of BO_particles (Colormode palette): uPal[16] (r g b pos) + uPalCtl bound on pmat.
# Cooks only when a palette par changes (it reads them, T-115). The PX_lines trails read the same pars.
def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    c = scriptOp.parent()
    Pm = c.op('pal_palmap').module
    src = c.par.Palsource.eval()
    spec = {'source': src, 'mode': c.par.Palmode.eval(), 'reverse': bool(c.par.Palreverse.eval())}
    rows = None
    if src == 'custom':
        t = c.op('pal_stops')
        rows = [[cell.val for cell in t.row(i)] for i in range(t.numRows)] if t is not None else []
    stops = Pm.palette_stops(spec, rows, [])
    Pm.cook_chop(scriptOp, Pm.pal_rows(stops))
    m = c.op('pmat')
    if m is not None:
        Pm.bind_glsl(m, 'pal', [float(min(len(stops), Pm.PAL_MAX))] + %r, ParMode)
""" % (PAL_CTL,)

CONNECTED = ("any(len(cn.connections) for cn in parent().inputConnectors "
             "if cn.inOP is not None and cn.inOP.name == '{}')")
# (an In TOP's .inputs stays empty when the COMP input is wired, 31550: read the COMP's connector instead; strobe.py)

STAGES = [
    {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'particles_pulses'],
     'body': 'zkit panel + window (pulse Opencontrols). particles_pulses: Reset / Burst -> engine.'},
    {'title': '1 Inputs', 'role': 'input',
     'ops': ['in_emit', 'emit_default', 'test_clip', 'test_small', 'test_prev', 'cam_diff', 'cam_diff_compute',
             'emit_src', 'in_field', 'field_default', 'field_src', 'in_ctl'],
     'body': 'in_emit (emit map / XYZ points) or white or the webcam clip frame difference (Emit TOP). in_field = rg '
             'push. in_ctl = control CHOP (kick bass mid high level). All optional.'},
    {'title': '2 Engine (CPU)', 'role': 'process',
     'ops': ['particles_logic', 'engine', 'engine_callbacks', 'info', 'info_callbacks', 'out_info'],
     'body': 'Script CHOP once per frame (particles_logic.step): clock, emission ring, audio/BPM, uniform rows uP[20].'},
    {'title': 'State feedback', 'role': 'feedback', 'ops': ['state_init', 'state_fb', 'state_src'],
     'body': 'state_fb = last frame of state (Statemode feedback). state_init = zeros (first frame / in place).'},
    {'title': '3 Simulate (GPU compute)', 'role': 'process',
     'ops': ['state', 'state_compute', 'state_inplace', 'out_state'],
     'body': 'ONE compute pass: spawn / curl + forces / bounds per particle. rgba32float, 3 texels per particle.'},
    {'title': '4 Render', 'role': 'process', 'ops': ['pgeo', 'pmat', 'pmat_vertex', 'pmat_pixel', 'pcam', 'render'],
     'body': 'Geometry COMP instancing (manual count) + GLSL MAT fetching the state texture: no CPU readback.'},
    {'title': 'Trail feedback', 'role': 'feedback', 'ops': ['trail_blank', 'trail_fb'],
     'body': 'trail_fb = last trail frame (only cooks when Trails is on).'},
    {'title': 'Palette', 'role': 'control', 'ops': ['pal_palmap', 'pal_stops', 'pal', 'pal_callbacks'],
     'body': 'W1-B palette (Palette page): pal = uPal[16] + uPalCtl on pmat (Colormode palette); PX_lines reads the '
             'same pars.'},
    {'title': '5 Light trails (PX_lines)', 'role': 'process', 'ops': ['lines_bg', 'dots_sw', 'PX_lines', 'sw_lines'],
     'body': 'Lineson: PX_lines (built by builders/px_lines.py, not edited) draws each particle trail (Trails motion '
             'points: in_points = state, Ptstride 3, Camera = pcam) over the dots (Linedots) or black.'},
    {'title': '6 Post + out', 'role': 'output',
     'ops': ['trail', 'trail_compute', 'sw_trail', 'bloom', 'sw_bloom', 'out1'],
     'body': 'Trails (ONE compute pass, max(render, last * keep)), Bloom (stock), out1 = premultiplied RGBA 16F.'},
]


def _logic():
    ns = {}
    exec(open(LOGIC_FILE).read(), ns)
    return ns


def _glsl(name):
    return open(os.path.join(GLSL_DIR, 'particles_{}.glsl'.format(name))).read()


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if style in ('RGB', 'XYZ'):
                if getattr(c.par, name + ('r' if style == 'RGB' else 'x'), None) is not None:
                    continue
            elif getattr(c.par, name, None) is not None:
                p0 = getattr(c.par, name)
                if style == 'Menu' and list(p0.menuNames) != list(o['names']):   # menu grew (lane G: Source
                    v0 = p0.eval()                                               # strands, Colormode palette)
                    p0.menuNames, p0.menuLabels = o['names'], o['labels']
                    p0.default = default
                    if v0 in o['names']:
                        p0.val = v0
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
                p.clampMin, p.min = True, o['min']           # counts / seeds / octaves are never negative
                p.default = default
                p.val = default
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style == 'CHOP':
                p = page.appendCHOP(name, label=label)[0]
                p.default = default
                p.val = default
            elif style in ('RGB', 'XYZ'):
                ps = page.appendRGB(name, label=label) if style == 'RGB' else page.appendXYZ(name, label=label)
                for p, v in zip(ps, default):
                    if style == 'XYZ':
                        p.normMin, p.normMax = o['min'], o['max']
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


def _menu(par, choices):
    """Set the first menu entry this build accepts (menu names not in the 31550 dump); returns it or None."""
    names = list(getattr(par, 'menuNames', []) or [])
    for v in choices:
        if not names or v in names:
            try:
                par.val = v
                return v
            except Exception:
                continue
    return None


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _text(c, name, text, dock=None, comment=''):
    d = _mk(c, textDAT, name)
    if d.text != text:
        d.text = text
    if dock is not None and d.dock is not dock:
        d.dock = dock
    if comment:
        d.comment = comment
    return d


def _compute(c, name, dat_name, code, w_expr, h_expr, fmt, comment):
    g = _mk(c, glslTOP, name)
    g.par.mode = 'compute'
    _text(c, dat_name, code, dock=g)
    g.par.computedat = dat_name
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w_expr)
    _expr(g.par.resolutionh, h_expr)
    g.par.format = fmt
    g.par.autodispatchsize = True
    g.comment = comment
    for dn in ('_info', '_pixel', '_compute'):         # GLSL TOP docks its own DATs; ours is the compute DAT
        d = c.op(name + dn)
        if d is not None and d.name != dat_name:
            _sd(d)
    return g


def _uniform_array(o, chop='engine'):
    o.seq.array.numBlocks = max(int(o.seq.array.numBlocks), 1)
    o.par.array0name = 'uP'
    o.par.array0type = 'vec4'
    o.par.array0chop = chop
    o.par.array0arraytype = 'uniformarray'


def _vec0(o, name, exprs):
    o.seq.vec.numBlocks = max(int(o.seq.vec.numBlocks), 1)
    o.par.vec0name = name
    for comp, e in zip('xyzw', exprs):
        _expr(getattr(o.par, 'vec0value' + comp), str(e))


def _script(c, name, cb_text, comment):
    s = _mk(c, scriptCHOP, name)
    cb = s.par.callbacks.eval()
    want = name + '_callbacks'
    if cb is None:
        cb = _mk(c, textDAT, want)
        cb.dock = s
    cb.text = cb_text
    if cb.name != want:
        cb.name = want
    s.par.callbacks = want
    s.comment = comment
    return s


def _constant(c, name, w_expr, h_expr, fmt, rgba, comment):
    k = _mk(c, constantTOP, name)
    k.par.outputresolution = 'custom'
    _expr(k.par.resolutionw, str(w_expr))
    _expr(k.par.resolutionh, str(h_expr))
    k.par.format = fmt
    k.par.colorr, k.par.colorg, k.par.colorb, k.par.alpha = rgba
    k.comment = comment
    return k


def _palette(c):
    """W1-B palette: pal_palmap (palette_map_logic, read only), pal_stops (custom stops), pal Script CHOP binding
    uPal + uPalCtl on pmat (first bind here so the MAT compiles with the block present)."""
    pm = _text(c, 'pal_palmap', open(PALMAP_FILE).read(),
               comment='W1-B shared palette = builders/palette_map_logic.py (read-only copy).')
    stops = _mk(c, tableDAT, 'pal_stops')
    if stops.numRows == 0:
        for h, pos in (('39FF14', 0.0), ('00F0FF', 0.5), ('FF00E6', 1.0)):
            stops.appendRow([h, pos])
    stops.comment = 'Custom palette stops (Palette = custom): hex [pos] per row.'
    pal = _script(c, 'pal', PAL_CB, 'W1-B palette uPal[16] (r g b pos), re-binds uPalCtl on pmat on palette edits.')
    ns = {}
    exec(compile(open(PALMAP_FILE).read(), PALMAP_FILE, 'exec'), ns)
    src = c.par.Palsource.eval()
    rows = [[cell.val for cell in stops.row(i)] for i in range(stops.numRows)] if src == 'custom' else None
    n = len(ns['palette_stops']({'source': src, 'mode': c.par.Palmode.eval(),
                                 'reverse': bool(c.par.Palreverse.eval())}, rows, []))
    ns['bind_glsl'](c.op('pmat'), 'pal', [float(min(n, ns['PAL_MAX']))] + PAL_CTL, ParMode)
    return pal


def _lines(c, Lg):
    """Light trails (TC-08): PX_lines built INSIDE by its own builder (imported, not edited), Trails in points mode on
    the state texture (Ptstride 3 = the P texel of each particle), Camera = pcam, its pars linked to the Lines /
    Palette pages (Lg['LINE_LINKS']). Lineson off = the switch passes the dots and PX_lines never cooks."""
    ns = dict(globals())
    exec(open(PXLINES_FILE).read(), ns)
    r = ns['build'](c.path, 'PX_lines')
    lx = c.op('PX_lines')
    for k, v in Lg['LINE_CONST'].items():
        p = getattr(lx.par, k, None)
        if p is not None:
            p.mode = ParMode.CONSTANT
            p.val = v
    for k, e in Lg['line_links']().items():
        p = getattr(lx.par, k, None)
        if p is not None:
            _expr(p, e)
    _expr(lx.par.Camera, "op('pcam')")
    lx.comment = ('Light trails on the particles (PX_lines, builders/px_lines.py; pars linked to BO_particles Lines / '
                  'Palette pages; its other pages stay editable).')
    bg = _constant(c, 'lines_bg', 8, 8, 'rgba16float', (0, 0, 0, 0), 'Black under the trails (Linedots off).')
    dsw = _mk(c, switchTOP, 'dots_sw')
    _wire(bg, dsw, 0)
    _wire(c.op('sw_trail'), dsw, 1)
    _expr(dsw.par.index, '1 if {}Linedots else 0'.format(PP))
    dsw.comment = 'What the trails draw over: the dots (Linedots) or black (the dots render then never cooks).'
    _wire(dsw, lx, 0)
    _wire(c.op('state'), lx, 1)
    sl = _mk(c, switchTOP, 'sw_lines')
    _wire(c.op('sw_trail'), sl, 0)
    if not (len(sl.inputs) > 1 and sl.inputs[1] is lx):
        sl.inputConnectors[1].connect(lx.outputConnectors[0])     # a COMP connects by its output connector
    _expr(sl.par.index, '1 if {}Lineson else 0'.format(PP))
    sl.comment = 'Lineson: PX_lines (trails + dots or black); off = the dots as before.'
    lx.allowCooking = True
    return {'lines': str(r)[:200]}


def preset(comp_path, name):
    """Apply a built-in preset (name or slot) as the FULL state (defaults + preset; PRESET_KEEP untouched), T-124 (1).
    A Count change re-inits the state (as the Count par always does)."""
    c = op(comp_path)
    L = c.op('particles_logic').module
    vals = L.preset_pars(name)
    n = 0
    for k, v in vals.items():
        p = getattr(c.par, k, None)
        if p is None:
            continue
        if p.mode != ParMode.CONSTANT:
            p.mode = ParMode.CONSTANT
        p.val = v
        n += 1
    return {'preset': name, 'set': n}


def _seed_presets(c, Lg):
    """zkit preset rows for the built-in presets (full state, menus as indexes); other slots (the user's) kept."""
    pt = c.op('controls/zk_presets')
    zl = c.op('controls/zk_logic')
    if pt is None or zl is None:
        return 0
    L = zl.module
    for slot, pname, _v in Lg['PRESETS']:
        row = [slot, pname, L.DEFAULT_COLOR, L.preset_dump(Lg['preset_zk'](pname))]
        for r_ in range(1, pt.numRows):
            if pt[r_, 0].val == str(slot):
                for k, v in enumerate(row):
                    pt[r_, k] = v
                break
        else:
            pt.appendRow(row)
    return len(Lg['PRESETS'])


def _eff_hook(c):
    """Shared effectors adapter (builders/effectors.py attach, docs/builds/effectors.md): Effectors page + a few ops,
    idempotent, run after every build; a failure is reported, never a broken build."""
    try:
        ns = dict(globals())
        exec(open(REPO + '/builders/effectors.py').read(), ns)
        return ns['attach'](c.path)
    except Exception as e:
        return 'effectors adapter skipped: %s' % e


def build(parent_path='/project1/lab', panel=True):
    Lg = _logic()
    pc = op(parent_path)
    c = pc.op(NAME) or pc.create(baseCOMP, NAME)
    c.allowCooking = True                        # never parked while being built (user rule)
    c.comment = ('BO_particles: GPU particles (compute state + instanced GLSL MAT). In: in_emit TOP, in_field TOP, '
                 'in_ctl CHOP (all optional). Out: out1 TOP (premultiplied RGBA 16F), out_state TOP, out_info CHOP. '
                 'No limits. Pulse Opencontrols.')
    _close_window(c)
    _pars(c, Lg['PAGES'])
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)

    # 2 Engine (first: the uniform CHOP the shaders read must exist before they compile)
    lg = _text(c, 'particles_logic', open(LOGIC_FILE).read(),
               comment='Pure logic (copy of builders/particles_logic.py; tests in test/test_particles.py).')
    in_ctl = _mk(c, inCHOP, 'in_ctl')
    in_ctl.comment = 'Optional control CHOP (kick bass mid high level 0..1), used when Audio = CHOP and Chop is empty.'
    eng = _script(c, 'engine', ENGINE_CB, 'Once per frame: particles_logic.step -> uP[20] rows (samples, chans x y z w).')
    _wire(in_ctl, eng, 0)
    eng.par.setuppars.pulse()
    info = _script(c, 'info', INFO_CB, 'Engine numbers as channels (frame, births, kick..., beat).')
    _wire(eng, info, 0)
    oinfo = _mk(c, outCHOP, 'out_info')
    _wire(info, oinfo)
    pulses = _mk(c, parameterexecuteDAT, 'particles_pulses')
    pulses.text = PULSES
    pulses.par.op = c
    pulses.par.pars = 'Reset Burst'
    pulses.par.custom = True
    pulses.par.builtin = False
    pulses.par.valuechange = False
    pulses.par.onpulse = True

    # 1 Inputs
    in_emit = _mk(c, inTOP, 'in_emit')
    in_emit.comment = 'Emit map (luma or alpha = weight, rgb = colour) or, Source = Points, XYZ positions (a > 0).'
    edef = _constant(c, 'emit_default', 1, 1, 'rgba16float', (1, 1, 1, 1), 'White 1x1: emit everywhere.')
    clip = _mk(c, moviefileinTOP, 'test_clip')
    clip.par.file = CLIP
    _expr(clip.par.play, "parent().par.Emitinput.eval() == 'cam'")   # live 26 Oct: a playing clip + Cache cooked
    clip.comment = 'Webcam reference clip (cooks only when Emit TOP = Webcam clip diff).'
    small = _mk(c, resolutionTOP, 'test_small')
    _wire(clip, small)
    small.par.outputresolution = 'custom'
    small.par.resolutionw, small.par.resolutionh = 270, 480
    small.par.format = 'rgba8fixed'
    prev = _mk(c, cacheTOP, 'test_prev')
    _wire(small, prev)
    prev.par.cachesize = 2
    prev.par.outputindex = -1
    _expr(prev.par.active, "parent().par.Emitinput.eval() == 'cam'")  # every frame (4 ms) with Emit TOP unused
    cd = _compute(c, 'cam_diff', 'cam_diff_compute', _glsl('camdiff'), "op('test_small').width",
                  "op('test_small').height", 'rgba16float', 'Frame difference: rgb = colour, a = motion (Emit weight Alpha).')
    _wire(small, cd, 0)
    _wire(prev, cd, 1)
    _vec0(cd, 'uD', ['0.08', '0.05', '0', '0'])
    esrc = _mk(c, switchTOP, 'emit_src')
    _wire(edef, esrc, 0)
    _wire(in_emit, esrc, 1)
    _wire(cd, esrc, 2)
    _expr(esrc.par.index, '{}.emit_index({}Emitinput.eval(), {})'.format(LG, PP, CONNECTED.format('in_emit')))
    in_field = _mk(c, inTOP, 'in_field')
    in_field.comment = 'Optional push field: rg = force in x/y over the Bound size box (Field strength).'
    fdef = _constant(c, 'field_default', 1, 1, 'rgba16float', (0, 0, 0, 0), 'Zero field 1x1.')
    fsrc = _mk(c, switchTOP, 'field_src')
    _wire(fdef, fsrc, 0)
    _wire(in_field, fsrc, 1)
    _expr(fsrc.par.index, '1 if {} else 0'.format(CONNECTED.format('in_field')))

    # State feedback + 3 Simulate
    rw = "{}.state_res({}Count.eval())[0]".format(LG, PP)
    rh = "{}.state_res({}Count.eval())[1]".format(LG, PP)
    inplace = "{}Statemode.eval() == 'inplace'".format(PP)
    sinit = _constant(c, 'state_init', rw, rh, 'rgba32float', (0, 0, 0, 0), 'Zero state (first frame; in place mode).')
    sfb = _mk(c, feedbackTOP, 'state_fb')
    _wire(sinit, sfb)
    ssrc = _mk(c, switchTOP, 'state_src')
    _wire(sfb, ssrc, 0)
    _wire(sinit, ssrc, 1)
    _expr(ssrc.par.index, '1 if {} else 0'.format(inplace))
    code = _glsl('state')
    st = _compute(c, 'state', 'state_compute', code, rw, rh, 'rgba32float',
                  'ONE compute pass per frame: spawn / forces / bounds. 3 texels per particle (P age, V life, rgb r).')
    _text(c, 'state_inplace', '#define STATE_INPLACE 1\n' + code, dock=st,
          comment='Same shader, reads its own output (Statemode = In place, Output Access Read-Write).')
    _expr(st.par.computedat, "'state_inplace' if {} else 'state_compute'".format(inplace))
    _expr(st.par.outputaccess, "'readwrite' if {} else 'writeonly'".format(inplace))
    _expr(st.par.clearoutputs, '0 if {} else 1'.format(inplace))
    st.par.inputfiltertype = 'nearest'
    _uniform_array(st)
    _wire(ssrc, st, 0)
    _wire(esrc, st, 1)
    _wire(fsrc, st, 2)
    sfb.par.top = st.name
    ost = _mk(c, outTOP, 'out_state')
    _wire(st, ost)

    # 4 Render
    m = _mk(c, glslMAT, 'pmat')                  # MAT first: its auto-docked pmat_vertex/pmat_pixel get reused
    _text(c, 'pmat_vertex', open(PALETTE_GLSL).read() + _glsl('vert'), dock=m,
          comment='px_palette.glsl + particles_vert.glsl: instance -> state texels -> camera-facing quad.')
    _text(c, 'pmat_pixel', _glsl('pixel'), dock=m, comment='Soft dot, premultiplied.')
    m.par.vdat = 'pmat_vertex'
    m.par.pdat = 'pmat_pixel'
    for dn in ('_vertex', '_pixel', '_info'):
        d = c.op('pmat' + dn)
        if d is not None and d.name not in ('pmat_vertex', 'pmat_pixel'):
            _sd(d)
    _uniform_array(m)
    m.seq.sampler.numBlocks = max(int(m.seq.sampler.numBlocks), 1)
    m.par.sampler0name = 'sState'
    m.par.sampler0top = 'state'
    m.par.sampler0filter = 'nearest'
    m.par.blending = True
    m.par.srcblend = 'one'
    _expr(m.par.destblend, "'one' if {}Blend.eval() == 'add' else 'omsa'".format(PP))
    m.par.postmultalpha = False                  # the shader already outputs premultiplied colour
    m.par.depthtest = False
    m.par.depthwriting = False
    m.comment = 'Particles material: reads uP[] + sState (state TOP). Blend add or alpha over (Blend).'
    geo = _mk(c, geometryCOMP, 'pgeo')
    for ch in list(geo.children):
        if ch.name != 'quad':
            _sd(ch)
    q = geo.op('quad') or geo.create(rectangleSOP, 'quad')
    q.par.orient = 'xy'
    q.par.sizex, q.par.sizey = 1, 1
    q.par.normals = False
    q.render = True
    q.display = True
    geo.par.instancing = True
    geo.par.instancecountmode = 'manual'
    _expr(geo.par.numinstances, 'int({}Count)'.format(PP))
    geo.par.material = 'pmat'                    # a COMP's OP pars resolve beside it (projector_dome probe)
    geo.comment = 'One 1x1 quad, instanced Count times (manual count, no instance OP); pmat places each instance.'
    cam = _mk(c, cameraCOMP, 'pcam')
    # time only while orbiting: a static camera must not make every reader of pcam (PX_lines rows) cook per frame
    pose = ("{}.cam_pose({}Camdist, {}Orbit, absTime.seconds if {}Orbit else 0.0, {}Camx, {}Camy)[{{}}]"
            .format(LG, PP, PP, PP, PP, PP))
    for k, n in (('tx', 0), ('ty', 1), ('tz', 2), ('ry', 3)):
        _expr(getattr(cam.par, k), pose.format(n))
    _expr(cam.par.fov, PP + 'Fov')
    _expr(cam.par.projection, "'ortho' if {}Ortho else 'perspective'".format(PP))
    _expr(cam.par.orthowidth, '{}.ortho_width({}Camdist, {}Fov)'.format(LG, PP, PP))
    cam.par.near = 0.01
    cam.par.far = 1000
    cam.comment = 'Looks at the origin from Distance; Orbit deg/s; Pan x/y; Ortho = flat 2D look.'
    r = _mk(c, renderTOP, 'render')
    r.par.camera = 'pcam'
    r.par.geometry = 'pgeo'
    r.par.lights = ''
    r.par.outputresolution = 'custom'
    _expr(r.par.resolutionw, PP + 'Resx')
    _expr(r.par.resolutionh, PP + 'Resy')
    r.par.format = 'rgba16float'
    _menu(r.par.antialias, ('aa1', 'aa2'))       # soft dots need no MSAA; keeps fill cost down at 1M
    r.par.bgcolorr = r.par.bgcolorg = r.par.bgcolorb = r.par.bgcolora = 0
    r.par.cullface = 'neither'
    r.comment = 'Resx x Resy, 16F, transparent background (premultiplied).'

    # Trail feedback + 5 Post + out
    tb = _constant(c, 'trail_blank', "op('render').width", "op('render').height", 'rgba16float', (0, 0, 0, 0),
                   'Trail start (transparent).')
    tfb = _mk(c, feedbackTOP, 'trail_fb')
    _wire(tb, tfb)
    tr = _compute(c, 'trail', 'trail_compute', _glsl('trail'), "op('render').width", "op('render').height",
                  'rgba16float', 'Trails: max(render, last * Trail keep). Cooks only when Trails is on.')
    _wire(r, tr, 0)
    _wire(tfb, tr, 1)
    _vec0(tr, 'uT', [PP + 'Trailfade', '0', '0', '0'])
    tfb.par.top = tr.name
    swt = _mk(c, switchTOP, 'sw_trail')
    _wire(r, swt, 0)
    _wire(tr, swt, 1)
    _expr(swt.par.index, '1 if {}Trails else 0'.format(PP))
    bl = _mk(c, bloomTOP, 'bloom')
    _expr(bl.par.bloomintensity, PP + 'Bloom')
    _palette(c)
    lines = _lines(c, Lg)
    sl = c.op('sw_lines')
    _wire(sl, bl)
    swb = _mk(c, switchTOP, 'sw_bloom')
    _wire(sl, swb, 0)
    _wire(bl, swb, 1)
    _expr(swb.par.index, '1 if {}Bloom > 0 else 0'.format(PP))
    out1 = _mk(c, outTOP, 'out1')
    _wire(swb, out1)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    # Controls (zkit)
    ui = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        ui = ns['build_controls'](c.path, pages=Lg['PANEL_PAGES'], d=56, cols=8)
        _seed_presets(c, Lg)

    stages = []
    for s_ in STAGES:
        s2 = dict(s_)
        s2['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
        if s2['ops']:
            stages.append(s2)
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    eff = _eff_hook(c)
    return {'effectors': str(eff)[:300], 'lines': lines,
            'comp': c.path, 'ops': len(c.children), 'panel': str(ui)[:300], 'layout': str(lay)[:400]}
