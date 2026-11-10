# reaction_diffusion builder - GN_reaction_diffusion: Gray-Scott reaction-diffusion COMP, all compute GLSL (T-46/T-47).
# Logic + numpy reference: builders/reaction_diffusion_logic.py; shaders builders/glsl/rd_*.glsl; doc
# docs/builds/reaction_diffusion.md; tests test/test_reaction_diffusion.py. No limits (user rule).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/reaction_diffusion.py').read(), ns); ns['build']('/project1/lab')
# build(parent_path, panel=True): idempotent (ops reused by name, texts / pars / wires re-set, custom par values kept,
# zkit panel refreshed in place, effector Nulls created only when missing).
# T-70 safe: nothing destroyed directly (_sd = safe_destroy), own controls_window closed first, network pane never moved.
# T-74/T-76: no TOP pixel readback or text measuring here; the seed Text TOP keeps TD's default typeface. No functions in storage
# (T-67). ASCII only.
import os

NAME = 'GN_reaction_diffusion'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
GLSL_DIR = HERE + '/glsl'
LOGIC_FILE = os.path.join(HERE, 'reaction_diffusion_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
NOTES = []

ENGINE_CB = """# engine: GN_reaction_diffusion control, once per frame (logic in rd_logic.engine_step, tested offline).
# in0 = in5 points CHOP, in1 = in6 audio, in2 = aud_low. Pulses arrive through push(). Effector Nulls: Effectors par.
# State lives in this module (plain data), not in op storage (T-67).
STATE = {'st': None, 'ev': [], 'rows': [], 'effs': None, 'effkey': None, 'effage': 0}

def push(e):
    STATE['ev'].append(e)

def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def _chans(o):
    if o is None or not o.numChans:
        return {}
    return dict((c.name, list(c.vals)) for c in o.chans())

def _blocks(o):
    if o is None or not o.numChans:
        return []
    return [list(c.vals) for c in o.chans()]

def _eff_ops(P):
    key = P.par.Effectors.eval()
    STATE['effage'] += 1
    if STATE['effs'] and STATE['effkey'] == key and STATE['effage'] < 30:   # empty list: look again every frame
        return [o for o in STATE['effs'] if o.valid]
    found = []
    R = op('/project1/effectors/eff_rt')
    for tok in key.split():
        if tok.startswith('@'):                # shared list: @all / @<name> / @#<tag> (docs/builds/effectors.md)
            for o in (R.module.select_ops(tok[1:]) if R is not None else []):
                if o not in found:
                    found.append(o)
            continue
        cands = []
        try:
            cands = list(P.ops(tok))
        except Exception:
            cands = []
        if not cands and ('/' in tok):
            o = op(tok)
            cands = [o] if o is not None else []
        for o in cands:
            if o is not None and o.isCOMP and hasattr(o, 'worldTransform') and o not in found:
                found.append(o)
    STATE['effs'], STATE['effkey'], STATE['effage'] = found, key, 0
    return found

def _cp(o, n):
    p = getattr(o.par, n, None)
    if p is None:
        return None
    v = p.eval()
    return p.menuIndex if p.isMenu else v

def _eff(o):
    tx, ty, sx, sy = o.par.tx.eval(), o.par.ty.eval(), o.par.sx.eval(), o.par.sy.eval()
    try:
        s, r, t = o.worldTransform.decompose()
        tx, ty, sx, sy = t[0], t[1], s[0], s[1]
    except Exception:
        pass
    e = {'tx': tx, 'ty': ty, 'sx': sx, 'sy': sy, 'strength': _cp(o, 'Strength'), 'radius': _cp(o, 'Radius'),
         'morph': _cp(o, 'Morph'), 'falloff': _cp(o, 'Falloff'), 'active': _cp(o, 'Active')}
    R = op('/project1/effectors/eff_rt')
    if R is not None and o.parent() is not None and (o.parent().path == '/project1/effectors' or
                                                     _cp(o, 'Strength') is None):
        i = R.module.info_2d(o)                # shared effector: radius / falloff / enabled / gain from eff_list
        if i is not None:
            e.update(i)
    return e

def onCook(scriptOp):
    L = op('rd_logic').module
    P = parent()
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    ins = scriptOp.inputs
    asp = P.par.Resw.eval() / max(P.par.Resh.eval(), 1)
    p = L.engine_params(lambda n: getattr(P.par, n).eval(), asp)
    inp = {'points': L.points_from_chans(_chans(ins[0] if len(ins) > 0 else None), p),
           'level': L.block_rms(_blocks(ins[1] if len(ins) > 1 else None)),
           'low': L.block_rms(_blocks(ins[2] if len(ins) > 2 else None))}
    if p['effon']:
        inp['effectors'] = [_eff(o) for o in _eff_ops(P)]
    if p['mousemode'] != 'off':
        m = op('mouse')
        if m is not None and m['tx'] is not None and m['ty'] is not None:
            down = m['lselect'].eval() > 0.5 if m['lselect'] is not None else True
            inp['mouse'] = ((m['tx'].eval() + 1.0) * 0.5, (m['ty'].eval() + 1.0) * 0.5, down)
    ev = STATE['ev']
    STATE['ev'] = []
    st, o, rows = L.engine_step(STATE['st'], absTime.seconds, p, inp, ev)
    STATE['st'] = st
    STATE['rows'] = rows
    names = L.ENGINE_CHANS
    if STATE.get('chans') == names:
        try:                                   # perf: values in place, no channel rebuild (appendChan x31 ~0.3 ms)
            for i, n in enumerate(names):
                scriptOp[i][0] = float(o[n])
            return
        except Exception:
            STATE['chans'] = None
    STATE['chans'] = names
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for n in names:
        scriptOp.appendChan(n)[0] = float(o[n])
    return
"""

ROWS_CB = """# rows: engine injector rows -> 2*NROWS samples x (x y z w) = the uRows texture buffer.
def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def onCook(scriptOp):
    L = op('rd_logic').module
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    ch = L.pack_rows(op('engine_callbacks').module.STATE['rows'])
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = len(ch[0])
    for n, vals in zip('xyzw', ch):
        scriptOp.appendChan(n).vals = vals
    return
"""

STATS_CB = """# stats (internal, not an output): in0 = tc_avg (Analyze average of fx_stat: A, B, cover, edge; read by index,
# T-87 names), in1 = engine. No TOP pixel readback in Python (T-74).
def _i(o, i):
    return float(o[i].eval()) if o is not None and o.numChans > i else 0.0

def _e(o, n):
    return float(o[n].eval()) if o is not None and o[n] is not None else 0.0

def onCook(scriptOp):
    P = parent()
    ins = list(scriptOp.inputs) + [None] * 2
    av, en = ins[0], ins[1]
    cook = 0.0
    for c in P.children:
        if c.family in ('TOP', 'CHOP'):
            cook += float(getattr(c, 'cpuCookTime', 0.0) or 0.0) + float(getattr(c, 'gpuCookTime', 0.0) or 0.0)
    vals = {'meana': _i(av, 0), 'meanb': _i(av, 1), 'cover': _i(av, 2), 'edge': _i(av, 3), 'steps': _e(en, 'steps'),
            'cookms': cook, 'level': _e(en, 'level'), 'morph': _e(en, 'morph'), 'nrows': _e(en, 'nrows')}
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for n in op('rd_logic').module.STAT_CHANS:
        scriptOp.appendChan(n)[0] = vals[n]
    return
"""

PULSES = """# rd_pulses: Reset / Reseed / Step / Burst / Morphgo -> engine events.
def onPulse(par):
    m = {'Reset': 'reset', 'Reseed': 'reseed', 'Step': 'step', 'Burst': 'burst', 'Morphgo': 'go'}
    if par.name in m:
        parent().op('engine_callbacks').module.push(m[par.name])
    return
"""

WIRED = ("1 if any(len(cn.connections) for cn in parent().inputConnectors "
         "if cn.inOP is not None and cn.inOP.name == '{}') else 0")
PP = "parent().par.{}"
SIM = ("op('rd_logic').module.sim_size(parent().par.Resw.eval(), parent().par.Resh.eval(), "
       "parent().par.Simh.eval())[{}]")
SIMW, SIMH = SIM.format(0), SIM.format(1)
RESW = "max(1, int(parent().par.Resw.eval()))"
RESH = "max(1, int(parent().par.Resh.eval()))"
HALFW = "max(1, int(parent().par.Resw.eval()) // 2)"
HALFH = "max(1, int(parent().par.Resh.eval()) // 2)"
DEG = "0.017453292519943295"
FUSED = ("1 if op('rd_logic').module.fused_ok(parent().par.Fusesteps.eval(), parent().par.Flowmode.eval(), "
         "parent().par.Anisomode.eval()) else 0")
NPASSES = ("op('rd_logic').module.rd_npasses(parent().par.Steps.eval(), op('rd_logic').module.fused_ok("
           "parent().par.Fusesteps.eval(), parent().par.Flowmode.eval(), parent().par.Anisomode.eval()))")


def E(n):
    return "(op('engine')['{0}'].eval() if op('engine')['{0}'] is not None else 0.0)".format(n)


def _vec_exprs():
    v = {
        'uSim': (SIMW, SIMH, "parent().par.Resw.eval() / max(parent().par.Resh.eval(), 1)", PP.format('Edge.menuIndex')),
        'uCtl': (E('nsteps'), E('reset'), PP.format('Mapimg'), E('seed')),
        'uSeed': (PP.format('Seedmode.menuIndex'), PP.format('Seedsize'), PP.format('Seedcount'),
                  PP.format('Seeddensity')),
        'uInj': ("0 if {} > 0.5 else parent().par.Inject.eval()".format(E('testmode')), PP.format('Maskthresh'),
                 PP.format('Morphdecay'), E('nrows')),
        'uFK': (E('fa'), E('ka'), E('fb'), E('kb')),
        'uRD': (PP.format('Da'), PP.format('Db'), PP.format('Dt'), "1 if parent().par.Clampstate.eval() else 0"),
        'uMorph': (E('morph'), PP.format('Mapmode.menuIndex'), PP.format('Mapamt'), PP.format('Mapscale')),
        'uPear': (PP.format('Fmin'), PP.format('Fmax'), PP.format('Kmin'), PP.format('Kmax')),
        'uAniso': (PP.format('Anisomode.menuIndex'), PP.format('Aniso'), "parent().par.Anisoangle.eval() * " + DEG,
                   PP.format('Anisoscale')),
        'uFlow': (PP.format('Flowmode.menuIndex'), PP.format('Flowgain'), PP.format('Flowx'), PP.format('Flowy')),
        'uFlow2': (PP.format('Flowscale'), E('ftime'), PP.format('Feedoff'), PP.format('Killoff')),
        'uBlk': (FUSED, '0', '0', '0'),
        'uLook': (PP.format('Valuemode.menuIndex'), PP.format('Lo'), PP.format('Hi'), PP.format('Colormode.menuIndex')),
        'uLook2': ("1 if parent().par.Invert.eval() else 0", PP.format('Shade'), PP.format('Shadeheight'),
                   "parent().par.Lightangle.eval() * " + DEG),
        'uLook3': (PP.format('Exposure'), PP.format('Gamma'), PP.format('Alpha.menuIndex'),
                   "1 if parent().par.Premult.eval() else 0"),
        'uEdge': (PP.format('Edgecolorr'), PP.format('Edgecolorg'), PP.format('Edgecolorb'), PP.format('Edgeglow')),
    }
    for k in range(5):
        v['uPal%d' % k] = (E('pal%dr' % k), E('pal%dg' % k), E('pal%db' % k), '1')
    return v


def _read(path):
    with open(path) as f:
        return f.read()


def _logic():
    ns = {}
    exec(_read(LOGIC_FILE), ns)
    return ns


def _shader(name):
    return _read(os.path.join(GLSL_DIR, 'rd_common.glsl')) + '\n' + _read(os.path.join(GLSL_DIR, 'rd_%s.glsl' % name))


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


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _expr(par, e):
    par.expr = str(e)
    par.mode = ParMode.EXPRESSION


def _try(o, name, value=None, expr=None, menu_like=None):
    """Set a par not confirmed on 31550 yet (LIVE CHECK): record misses in NOTES, never fail."""
    p = getattr(o.par, name, None)
    if p is None:
        NOTES.append('%s.%s: no such par' % (o.name, name))
        return None
    try:
        if menu_like is not None:
            names = list(p.menuNames)
            hit = next((m for m in names if any(k in m.lower() for k in menu_like)), None)
            if hit is None:
                NOTES.append('%s.%s: no menu entry like %s in %s' % (o.name, name, menu_like, names))
                return None
            p.val = hit
            return hit
        if expr is not None:
            _expr(p, expr)
        else:
            p.val = value
    except Exception as e:
        NOTES.append('%s.%s: %s' % (o.name, name, e))
    return p


def _menu_src(name, kind):
    """menuSource of a dropdown par (spec option 'menu': kind): /project1/effectors/eff_rt.menu builds the items on
    each menu read (menu_logic.shared_source; empty menu, free text, while the list is missing)."""
    ns = {}
    exec(open(os.path.join(HERE, 'menu_logic.py')).read(), ns)
    return ns['shared_source'](name, kind)


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
            elif style in ('Float', 'Int'):
                p = (page.appendFloat if style == 'Float' else page.appendInt)(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']     # slider range only: no clamps (no limits)
                if 'clampmin' in o:                            # texture sizes / pass counts only
                    p.min, p.clampMin = o['clampmin'], True
                p.default = default
                p.val = default
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style == 'Str' and o.get('menu'):     # live dropdown through the shared list runtime (T-233)
                p = page.appendStrMenu(name, label=label)[0]
                p.menuSource = _menu_src(name, o['menu'])
                p.default = default
                p.val = default
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'TOP':
                p = page.appendTOP(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'RGB':
                for p, v in zip(page.appendRGB(name, label=label), default):
                    p.default = v
                    p.val = v


def _glsl(c, name, code_dat, w_expr, h_expr, fmt, vecs, arrays):
    g = _mk(c, glslTOP, name)
    g.par.mode = 'compute'
    g.par.computedat = code_dat.name
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w_expr)
    _expr(g.par.resolutionh, h_expr)
    g.par.format = fmt
    g.par.autodispatchsize = True
    if vecs:
        g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), len(vecs))
        for k, (un, ex) in enumerate(vecs):
            getattr(g.par, 'vec{}name'.format(k)).val = un
            for ax, e in zip('xyzw', ex):
                _expr(getattr(g.par, 'vec{}value{}'.format(k, ax)), e)
    if arrays:
        g.seq.array.numBlocks = max(int(g.seq.array.numBlocks), len(arrays))
        for k, (un, chop) in enumerate(arrays):
            getattr(g.par, 'array{}name'.format(k)).val = un
            getattr(g.par, 'array{}type'.format(k)).val = 'vec4'
            getattr(g.par, 'array{}chop'.format(k)).val = chop
            getattr(g.par, 'array{}arraytype'.format(k)).val = 'texturebuffer'
    return g


def _code(c, name, text):
    d = _mk(c, textDAT, name)
    if d.text != text:
        d.text = text
    return d


def _blank(c, name, w, h, fmt):
    b = _mk(c, constantTOP, name)
    b.par.outputresolution = 'custom'
    _expr(b.par.resolutionw, w)
    _expr(b.par.resolutionh, h)
    b.par.format = fmt
    b.par.colorr = b.par.colorg = b.par.colorb = 0
    b.par.alpha = 0
    return b


def _script(c, name, text, inputs):
    s = _mk(c, scriptCHOP, name)
    for i, src in enumerate(inputs):
        _wire(src, s, i)
    want = name + '_callbacks'
    cb = c.op(want)
    if cb is None or cb.OPType != 'textDAT':
        cb = s.par.callbacks.eval()
        if cb is None:
            cb = _mk(c, textDAT, want)
        elif cb.name != want and c.op(want) is None:
            cb.name = want
    if cb.text != text:
        cb.text = text
    s.par.callbacks = cb.name
    s.par.setuppars.pulse()
    return s


EFFECTOR_DEFAULTS = [
    # name, tx, ty, strength, radius, morph, comment
    ('eff1', 0.0, 0.25, 0.03, 0.08, 0.0, 'Effector 1: injects B where it sits (move tx/ty, scale = radius).'),
    ('eff2', 0.0, -0.3, 0.0, 0.18, 1.0, 'Effector 2: no inject, morphs its area toward Preset B (Morph 1).'),
]


def _effector(c, name, tx, ty, strength, radius, morph, comment):
    o = c.op(name)
    if o is not None:
        return o                                    # never touch the user's placement / values
    o = c.create(nullCOMP, name)
    o.par.tx, o.par.ty = tx, ty
    page = o.appendCustomPage('Effector')
    a = page.appendToggle('Active', label='Active')[0]
    a.default = a.val = True
    for n, v, lo, hi in (('Strength', strength, -1, 1), ('Radius', radius, 0.005, 0.5), ('Morph', morph, -2, 2)):
        p = page.appendFloat(n, label=n)[0]
        p.normMin, p.normMax = lo, hi
        p.default = p.val = v
    fo = page.appendMenu('Falloff', label='Falloff')[0]
    fo.menuNames = ['gauss', 'linear', 'hard', 'ring']
    fo.menuLabels = ['Gauss', 'Linear', 'Hard', 'Ring']
    fo.default = fo.val = 'gauss'
    o.comment = comment + ' Pars: Effector page. Plane: Planeh world units tall, centred at 0.'
    return o


def build(parent_path='/project1/lab', panel=True):
    del NOTES[:]
    Lg = _logic()
    pc = op(parent_path)
    c = pc.op(NAME) or pc.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('GN_reaction_diffusion: Gray-Scott reaction-diffusion (compute GLSL, npasses = Steps). In: in1 TOP seed '
                 '/ inject image, in2 TOP mask (R > Maskthresh = blocked), in3 TOP flow (RG cells/step), in4 TOP morph '
                 'map, in5 CHOP points (x y radius strength morph, uv), in6 CHOP audio. Effector Nulls (eff*). Out: '
                 'out1 look, out2 raw state (A B morph solid). preview = look + gizmos. Pulse Opencontrols.')
    was_open = _close_window(c)
    _pars(c, Lg['PAGES'])
    lg = _code(c, 'rd_logic', _read(LOGIC_FILE))
    lg.comment = 'Pure logic + numpy reference (copy of builders/reaction_diffusion_logic.py; tests test/test_reaction_diffusion.py).'
    vx = _vec_exprs()

    # 1 Inputs
    blank = _blank(c, 'blank', SIMW, SIMH, 'rgba32float')
    blank.comment = 'Sim-res zero (Feedback start + stand-in for unwired TOP inputs).'
    ins = {n: _mk(c, inTOP, n) for n in ('in1', 'in2', 'in3', 'in4')}
    st = _mk(c, textTOP, 'seed_text')
    st.par.outputresolution = 'custom'
    _expr(st.par.resolutionw, SIMW)
    _expr(st.par.resolutionh, SIMH)
    _try(st, 'text', expr=PP.format('Seedtext'))
    _try(st, 'fontsizex', expr="parent().par.Textsize.eval() * (" + SIMH + ")")
    _try(st, 'alignx', menu_like=('center', 'centre'))
    _try(st, 'aligny', menu_like=('center', 'centre'))
    st.comment = 'Seed text (Seedmode text / Injectsrc text). Default font only (T-76).'
    ss = _mk(c, switchTOP, 'seed_sel')
    _wire(blank, ss, 0)
    _wire(ins['in1'], ss, 1)
    _wire(st, ss, 2)
    _expr(ss.par.index, "2 if (parent().par.Seedmode.eval() == 'text' or (parent().par.Seedmode.eval() != 'image' and "
                        "parent().par.Injectsrc.eval() == 'text')) else ({})".format(WIRED.format('in1')))
    sp = _mk(c, resolutionTOP, 'seed_prep')
    _wire(ss, sp)
    sp.par.outputresolution = 'custom'
    _expr(sp.par.resolutionw, SIMW)
    _expr(sp.par.resolutionh, SIMH)
    sp.par.format = 'rgba16float'
    sp.comment = 'Seed / inject image at sim res (luminance -> B).'
    for n, sel in (('in2', 'mask_sel'), ('in4', 'mmap_sel'), ('in3', 'flow_sel')):
        s = _mk(c, switchTOP, sel)
        _wire(blank, s, 0)
        _wire(ins[n], s, 1)
        _expr(s.par.index, WIRED.format(n))

    # 2 Control sources
    in5 = _mk(c, inCHOP, 'in5')
    in6 = _mk(c, inCHOP, 'in6')
    al = _mk(c, audiofilterCHOP, 'aud_low')
    _wire(in6, al)
    _try(al, 'filter', menu_like=('low',))
    if getattr(al.par, 'cutofffrequency', None) is not None:
        _try(al, 'cutofffrequency', expr=PP.format('Lowhz'))
    else:
        _try(al, 'cutoff', expr=PP.format('Lowhz'))
    al.comment = 'Low band of in6 (Lowhz) for the kick detector. Never routed to a speaker.'
    mouse = _mk(c, mouseinCHOP, 'mouse')
    mouse.comment = 'Screen mouse (read only when Mousemode = screen; tx ty -1..1, lselect).'
    eng = _script(c, 'engine', ENGINE_CB, [in5, in6, al])
    eng.comment = 'Once per frame: steps / pause / stopat, reset, preset morph (go, LFO, audio), effectors, bursts -> rows.'
    rows = _script(c, 'rows', ROWS_CB, [eng])
    rows.comment = 'Injector rows -> 64 samples x (x y z w) = uRows texture buffer.'
    pulses = _mk(c, parameterexecuteDAT, 'rd_pulses')
    if pulses.text != PULSES:
        pulses.text = PULSES
    pulses.par.op = c
    pulses.par.pars = 'Reset Reseed Step Burst Morphgo'
    pulses.par.custom = True
    pulses.par.builtin = False
    pulses.par.valuechange = False
    pulses.par.onpulse = True
    for e in EFFECTOR_DEFAULTS:
        _effector(c, *e)

    # Feedback
    fb = _mk(c, feedbackTOP, 'state_fb')
    _wire(blank, fb)

    spec = dict(Lg['PASSES'])
    res = {'sim': (SIMW, SIMH), 'out': (RESW, RESH), 'half': (HALFW, HALFH)}
    made = {}

    def mk_pass(pname, inputs):
        s_ = spec[pname]
        vecs = [(u, vx[u]) for u in s_['vecs']]
        arrays = [(a, 'rows') for a in s_['arrays']]
        w, h = res[s_['res']]
        code = _code(c, 'fx_%s_compute' % pname, _shader(pname))
        g = _glsl(c, 'fx_' + pname, code, w, h, s_['fmt'], vecs, arrays)
        for i, src in enumerate(inputs):
            _wire(src, g, i)
        made['fx_' + pname] = g
        return g

    def ins_of(pname):
        return [made.get(n) or c.op(n) for n in spec[pname]['inputs']]

    mk_pass('maps', ins_of('maps'))
    mk_pass('seed', ins_of('seed'))
    g = mk_pass('rd', ins_of('rd'))
    _try(g, 'npasses', expr=NPASSES)
    fb.par.top = g.name

    # Look
    ramp = _mk(c, rampTOP, 'ramp')
    ramp.par.outputresolution = 'custom'
    ramp.par.resolutionw, ramp.par.resolutionh = 256, 1
    ramp.comment = 'Inner ramp for Colormode ramp (edit its keys) unless Ramptop names another TOP.'
    ri = _mk(c, selectTOP, 'ramp_in')
    _expr(ri.par.top, "parent().par.Ramptop.eval() or op('ramp')")
    lk = mk_pass('look', ins_of('look'))
    # fx_look samples the state with the hardware bilinear (perf); its edge rule follows Edge (default 'zero' would
    # read A = B = 0 past the border)
    _try(lk, 'inputextenduv', expr="'repeat' if parent().par.Edge.eval() == 'wrap' else 'hold'")
    _try(lk, 'inputfiltertype', 'linear')
    mk_pass('preview', ins_of('preview'))
    out1 = _mk(c, outTOP, 'out1')
    _wire(made['fx_look'], out1)
    out2 = _mk(c, outTOP, 'out2')
    _wire(made['fx_rd'], out2)
    pv = _mk(c, nullTOP, 'preview')
    _wire(made['fx_preview'], pv)
    pv.comment = 'Preview: look + effector / point / mouse gizmos (not an output).'

    # Stats (internal)
    mk_pass('stat', ins_of('stat'))
    an = _mk(c, analyzeTOP, 'an_avg')
    _wire(made['fx_stat'], an)
    _try(an, 'op', 'average')
    _try(an, 'analyzechannel', 'independent')
    tc = _mk(c, toptoCHOP, 'tc_avg')
    tc.par.top = 'an_avg'
    _try(tc, 'downloadtype', 'nextframe')
    stc = _script(c, 'stats', STATS_CB, [tc, eng])
    stc.comment = 'meana meanb cover edge steps cookms level morph nrows (internal; read it, not an output).'

    c.par.opviewer.expr = "me.op('preview') if me.par.Showeff.eval() else me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    info = None
    if panel:
        ns = dict(globals())
        exec(_read(ZKIT_FILE), ns)
        info = ns['build_controls'](c.path, pages=Lg['PANEL_PAGES'], d=56, cols=8, open_window=was_open)

    def with_docked(names):
        out = []
        for n in names:
            o = c.op(n)
            if o is None:
                continue
            out.append(n)
            for d in list(getattr(o, 'docked', []) or []):
                if d.valid and d.name not in out:
                    out.append(d.name)
        return out

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': with_docked(['controls', 'controls_window', 'rd_pulses', 'rd_logic']),
         'body': 'zkit panel (pulse Opencontrols). rd_pulses: Reset / Reseed / Step / Burst / Morphgo -> engine.'},
        {'title': 'Effectors', 'role': 'input', 'ops': with_docked([e[0] for e in EFFECTOR_DEFAULTS]),
         'body': 'Null COMPs (Effectors par: eff*). tx/ty on a Planeh-tall plane, scale = radius; Effector page: '
                 'Strength (- erases), Radius, Morph, Falloff. Drawn in preview.'},
        {'title': '1 Inputs', 'role': 'input',
         'ops': with_docked(['in1', 'in2', 'in3', 'in4', 'blank', 'seed_text', 'seed_sel', 'seed_prep', 'mask_sel',
                             'mmap_sel', 'flow_sel', 'fx_maps', 'fx_maps_compute']),
         'body': 'in1 seed/inject image | text, in2 mask, in3 flow RG, in4 morph map -> fx_maps (mask, mmap, flow).'},
        {'title': '2 Control sources', 'role': 'input',
         'ops': with_docked(['in5', 'in6', 'aud_low', 'mouse', 'engine', 'engine_callbacks', 'rows', 'rows_callbacks']),
         'body': 'engine (rd_logic.engine_step): steps, reset, morph (go / LFO / audio), effectors + points + mouse + '
                 'bursts -> rows (uRows).'},
        {'title': '3 Seed + inject', 'role': 'process', 'ops': with_docked(['state_fb', 'fx_seed', 'fx_seed_compute']),
         'body': 'state_fb <- fx_rd. fx_seed: reset pattern, continuous inject, injector rows, local morph, mask.'},
        {'title': '4 React', 'role': 'process', 'ops': with_docked(['fx_rd', 'fx_rd_compute']),
         'body': 'fx_rd: Steps Gray-Scott steps (iso / anisotropic, optional flow advection, morph map); iso + no flow: '
                 '8 steps per dispatch in shared memory (Fusesteps).'},
        {'title': '5 Look + out', 'role': 'output',
         'ops': with_docked(['ramp', 'ramp_in', 'fx_look', 'fx_look_compute', 'out1', 'out2', 'fx_preview',
                             'fx_preview_compute', 'preview']),
         'body': 'fx_look (Resw x Resh) -> out1. out2 = raw state. fx_preview = look + gizmos (not output).'},
        {'title': '6 Stats', 'role': 'output',
         'ops': with_docked(['fx_stat', 'fx_stat_compute', 'an_avg', 'tc_avg', 'stats', 'stats_callbacks']),
         'body': 'fx_stat -> Analyze average -> stats CHOP (meana meanb cover edge ...), internal.'},
    ]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'notes': list(NOTES), 'panel': str(info)[:300],
            'layout': str(lay)[:400]}
