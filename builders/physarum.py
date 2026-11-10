# physarum builder - GN_physarum: slime mould (Jones / Jenson) agents + trail COMP. Compute GLSL for every pass
# (T-46/T-47) except the deposit: a GLSL MAT draws one 1-px point per agent into a 32F Render TOP with additive blend
# (no float atomics on Mac, research O F13; exact sums, T-112). Logic + numpy reference: builders/physarum_logic.py;
# shaders builders/glsl/ph_*.glsl; doc docs/builds/physarum.md; tests test/test_physarum.py. No limits (user rule).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/physarum.py').read(), ns); ns['build']('/project1/lab')
# build(parent_path, panel=True, upto=None): idempotent (ops reused by name, texts / pars / wires re-set, custom par
# values kept, zkit panel refreshed in place, effector Nulls created only when missing). upto=1 stops after the sim
# (no look / stats / panel) for a staged first run.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy), own controls_window closed first, network pane never moved.
# T-74/T-76: no TOP pixel readback or text measuring here; the seed Text TOP keeps TD's default typeface. No functions
# in storage (T-67). ASCII only.
import os

NAME = 'GN_physarum'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
GLSL_DIR = HERE + '/glsl'
LOGIC_FILE = os.path.join(HERE, 'physarum_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
NOTES = []

ENGINE_CB = """# engine: GN_physarum control, once per frame (logic in ph_logic.engine_step, tested offline).
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
         'deposit': _cp(o, 'Deposit'), 'falloff': _cp(o, 'Falloff'), 'active': _cp(o, 'Active')}
    R = op('/project1/effectors/eff_rt')
    if R is not None and o.parent() is not None and (o.parent().path == '/project1/effectors' or
                                                     _cp(o, 'Strength') is None):
        i = R.module.info_2d(o)                # shared effector: radius / falloff / enabled / gain from eff_list
        if i is not None:
            e.update(i)
    return e

def onCook(scriptOp):
    L = op('ph_logic').module
    P = parent()
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    ins = scriptOp.inputs
    asp = P.par.Resw.eval() / max(P.par.Resh.eval(), 1)
    # perf wave 27 Oct: the ~70 par reads (~0.17 ms) only when a par changed (ph_parwatch bumps STATE['pv']; every
    # PARAM_REFRESH frames anyway as a safety net), else the cached dict
    STATE['pn'] = STATE.get('pn', 0) + 1
    key = (STATE.get('pv', 0), asp)
    if STATE.get('p') is None or STATE.get('pkey') != key or STATE['pn'] >= 60:
        STATE['p'] = L.engine_params(lambda n: getattr(P.par, n).eval(), asp)
        STATE['pkey'], STATE['pn'] = key, 0
    p = dict(STATE['p'])
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
    STATE['o'] = o
    names = L.ENGINE_CHANS
    if STATE.get('chans') == names:
        try:                                   # values in place, no channel rebuild (T-108 (2))
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

PARWATCH = """# ph_parwatch (perf wave 27 Oct): any custom par value change (expressions included) -> the engine re-reads its pars.
def onValueChange(par, prev):
    m = op('engine_callbacks').module
    m.STATE['pv'] = m.STATE.get('pv', 0) + 1
    return
"""

UNI_HEAD = """# uni (perf wave 27 Oct): the GLSL uniforms that read the engine, as ONE vec4 uniform array uV (row k = the k-th name
# in UNI_VECS); generated by builders/physarum.py from _vec_exprs(). 44 engine-reading par expressions cost ~0.4 ms
# CPU per frame (T-214); this Script CHOP packs the same values in Python from the engine's output dict.
import numpy as np
SHAPE = {'n': None}

def onSetupParameters(scriptOp):
    return

"""

UNI_TAIL = """
def onCook(scriptOp):
    o = op('engine_callbacks').module.STATE.get('o')
    if o is None:
        return
    v = np.array(uni_rows(o, parent()), dtype=np.float32)
    if SHAPE['n'] != len(v):
        scriptOp.clear()
        scriptOp.isTimeSlice = False
        scriptOp.numSamples = len(v)
        for n in 'xyzw':
            scriptOp.appendChan(n)
        SHAPE['n'] = len(v)
    for k in range(4):
        scriptOp[k].copyNumpyArray(np.array(v[:, k], copy=True))   # T-143 (5): fresh contiguous column
    return
"""

E_RE = r"\(op\('engine'\)\['(\w+)'\]\.eval\(\) if op\('engine'\)\['\w+'\] is not None else 0\.0\)"


def uni_vecs(vx):
    """The uniform names whose expressions read the engine (they move to the uV array), in a fixed order."""
    return sorted(u for u, ex in vx.items() if any("op('engine')" in e for e in ex))


def _py_comp(e):
    import re
    e = re.sub(E_RE, lambda m: "o.get(%r, 0.0)" % m.group(1), e)
    e = e.replace('parent().par.', 'P.par.')
    return 'float(%s)' % e


def uni_text(vx):
    names = uni_vecs(vx)
    lines = ['UNI_VECS = %r' % (names,), '', 'def uni_rows(o, P):', '    return [']
    for u in names:
        lines.append('        [%s],   # %s' % (', '.join(_py_comp(e) for e in vx[u]), u))
    lines.append('    ]')
    return UNI_HEAD + '\n'.join(lines) + '\n' + UNI_TAIL


def uni_shader(text, names):
    """GLSL text: each 'uniform vec4 uX;' of an engine-fed uniform becomes '#define uX uV[k]' (bodies unchanged)."""
    import re
    hit = False
    for k, u in enumerate(names):
        text, n = re.subn(r'^uniform vec4 %s;' % u, '#define %s uV[%d]' % (u, k), text, flags=re.M)
        hit = hit or n > 0
    return ('uniform vec4 uV[%d];\n' % len(names) + text) if hit else text


ROWS_CB = """# rows: engine effector rows -> 2*NROWS samples x (x y z w) = the uRows texture buffer.
def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def onCook(scriptOp):
    L = op('ph_logic').module
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    ch = L.pack_rows(op('engine_callbacks').module.STATE['rows'])
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = len(ch[0])
    for n, vals in zip('xyzw', ch):
        scriptOp.appendChan(n).vals = vals
    return
"""

STATS_CB = """# stats (internal, not an output): in0 = tc_avg (Analyze average of fx_stat: total, cover, peak, species 0; by
# index, T-87 names), in1 = tc_aavg (fx_astat: cos, sin, live), in2 = engine. No TOP pixel readback in Python (T-74).
import math

def _i(o, i):
    return float(o[i].eval()) if o is not None and o.numChans > i else 0.0

def _e(o, n):
    return float(o[n].eval()) if o is not None and o[n] is not None else 0.0

def onCook(scriptOp):
    P = parent()
    L = op('ph_logic').module
    ins = list(scriptOp.inputs) + [None] * 3
    av, aa, en = ins[0], ins[1], ins[2]
    cook = 0.0
    for c in P.children:
        if c.family in ('TOP', 'CHOP'):
            cook += float(getattr(c, 'cpuCookTime', 0.0) or 0.0) + float(getattr(c, 'gpuCookTime', 0.0) or 0.0)
    alive = _i(aa, 2)
    w, h = L.sim_size(P.par.Resw.eval(), P.par.Resh.eval(), P.par.Simh.eval())
    vals = {'mean': _i(av, 0), 'cover': _i(av, 1), 'peak': _i(av, 2), 'meanr': _i(av, 3),
            'order': math.hypot(_i(aa, 0), _i(aa, 1)) / max(alive, 1e-9), 'alive': alive, 'steps': _e(en, 'steps'),
            'agents': _e(en, 'n'), 'cookms': cook, 'level': _e(en, 'level'), 'morph': _e(en, 'morph'),
            'nrows': _e(en, 'nrows'),
            'expected': L.expected_mean(_e(en, 'n'), _e(en, 'dep'), _e(en, 'decay'), w, h) if _e(en, 'decay') > 0 else -1.0}
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for n in L.STAT_CHANS:
        scriptOp.appendChan(n)[0] = vals[n]
    return
"""

PULSES = """# ph_pulses: Reset / Reseed / Step / Burst / Morphgo -> engine events.
def onPulse(par):
    m = {'Reset': 'reset', 'Reseed': 'reseed', 'Step': 'step', 'Burst': 'burst', 'Morphgo': 'go'}
    if par.name in m:
        parent().op('engine_callbacks').module.push(m[par.name])
    return
"""

WIRED = ("1 if any(len(cn.connections) for cn in parent().inputConnectors "
         "if cn.inOP is not None and cn.inOP.name == '{}') else 0")
PP = "parent().par.{}"
SIM = ("op('ph_logic').module.sim_size(parent().par.Resw.eval(), parent().par.Resh.eval(), "
       "parent().par.Simh.eval())[{}]")
SIMW, SIMH = SIM.format(0), SIM.format(1)
RESW = "max(1, int(parent().par.Resw.eval()))"
RESH = "max(1, int(parent().par.Resh.eval()))"
HALFW = "max(1, int(parent().par.Resw.eval()) // 2)"
HALFH = "max(1, int(parent().par.Resh.eval()) // 2)"
SIDE = "max(1, int(op('ph_logic').module.agent_side(parent().par.Agents.eval())))"
DEG = "0.017453292519943295"


def E(n):
    return "(op('engine')['{0}'].eval() if op('engine')['{0}'] is not None else 0.0)".format(n)


def _vec_exprs():
    test = "0 if {} > 0.5 else ".format(E('testmode'))
    v = {
        'uSim': (SIMW, SIMH, "parent().par.Resw.eval() / max(parent().par.Resh.eval(), 1)", PP.format('Edge.menuIndex')),
        'uAg': (E('n'), E('side'), E('nspecies'), PP.format('Speciesmode.menuIndex')),
        'uCtl': (E('run'), E('reset'), E('steps'), E('seed')),
        'uSense': (E('sa') + ' * ' + DEG, E('so'), E('ra') + ' * ' + DEG, E('jitter') + ' * ' + DEG),
        'uMove': (E('ss'), E('dep'), PP.format('Selfw'), PP.format('Otherw')),
        'uSpec': (PP.format('Speedspread'), PP.format('Maskthresh'), E('nrows'), PP.format('Heading.menuIndex')),
        'uSeed': (PP.format('Seedmode.menuIndex'), PP.format('Seedsize'), test + PP.format('Respawn.eval()'), '0'),
        'uFood': (test + PP.format('Foodw.eval()'), test + PP.format('Foodinject.eval()'), E('nrows'), '0'),
        'uTrail': (E('diffuse'), E('decay'), E('nspecies'), PP.format('Maskthresh')),
        'uLook': (PP.format('Valuemode.menuIndex'), PP.format('Lo'), PP.format('Hi'), PP.format('Colormode.menuIndex')),
        'uLook2': (PP.format('Exposure'), PP.format('Gamma'), PP.format('Alpha.menuIndex'),
                   "1 if parent().par.Premult.eval() else 0"),
        'uLook3': (PP.format('Glow'), PP.format('Agentsview'), E('nspecies'), '0'),
        'uBg': (PP.format('Bgr'), PP.format('Bgg'), PP.format('Bgb'), '1'),
    }
    for k in (1, 2, 3):
        v['uCol%d' % k] = (PP.format('Col%dr' % k), PP.format('Col%dg' % k), PP.format('Col%db' % k), '1')
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
    g.seq.vec.numBlocks = max(1, len(vecs))      # exact (a rebuild moves engine-fed vecs into uV, perf wave 27 Oct)
    if not vecs:
        g.par.vec0name = ''
    for k, (un, ex) in enumerate(vecs):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for ax, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, ax)), e)
    g.seq.array.numBlocks = max(1, len(arrays))
    if not arrays:
        g.par.array0name = ''
    for k, a in enumerate(arrays):
        un, chop = a[0], a[1]
        getattr(g.par, 'array{}name'.format(k)).val = un
        getattr(g.par, 'array{}type'.format(k)).val = 'vec4'
        getattr(g.par, 'array{}chop'.format(k)).val = chop
        getattr(g.par, 'array{}arraytype'.format(k)).val = a[2] if len(a) > 2 else 'texturebuffer'
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
    # name, tx, ty, strength, radius, deposit, comment
    ('eff1', 0.0, 0.25, 15.0, 0.15, 0.0, 'Effector 1: attractor (Strength +) - agents steer toward it.'),
    ('eff2', 0.0, -0.3, -15.0, 0.12, 0.0, 'Effector 2: repeller (Strength -) - agents steer away from it.'),
]


def _effector(c, name, tx, ty, strength, radius, deposit, comment):
    o = c.op(name)
    if o is not None:
        return o                                    # never touch the user's placement / values
    o = c.create(nullCOMP, name)
    o.par.tx, o.par.ty = tx, ty
    page = o.appendCustomPage('Effector')
    a = page.appendToggle('Active', label='Active')[0]
    a.default = a.val = True
    for n, v, lo, hi in (('Strength', strength, -20, 20), ('Radius', radius, 0.005, 0.5), ('Deposit', deposit, 0, 5)):
        p = page.appendFloat(n, label=n)[0]
        p.normMin, p.normMax = lo, hi
        p.default = p.val = v
    fo = page.appendMenu('Falloff', label='Falloff')[0]
    fo.menuNames = ['gauss', 'linear', 'hard', 'ring']
    fo.menuLabels = ['Gauss', 'Linear', 'Hard', 'Ring']
    fo.default = fo.val = 'gauss'
    o.comment = comment + ' Pars: Effector page. Plane: Planeh world units tall, centred at 0; scale = radius.'
    return o


def _shader(name):
    return _read(os.path.join(GLSL_DIR, 'ph_common.glsl')) + '\n' + _read(os.path.join(GLSL_DIR, 'ph_%s.glsl' % name))


def _deposit(c, vx):
    """Grid POP (side x side points) -> dep_geo (Select POP) with dep_mat (GLSL MAT, additive) -> deposit Render TOP."""
    g = _mk(c, gridPOP, 'pts')
    g.par.surftype = 'points'
    _expr(g.par.cols, SIDE)
    _expr(g.par.rows, SIDE)
    g.par.sizex, g.par.sizey = 1, 1
    _try(g, 'texture', 'point')                       # silences "MAT uses texture coordinates" on the render
    g.comment = 'side x side points; TDPos().xy + 0.5 = the agent texel (dep_mat).'
    m = _mk(c, glslMAT, 'dep_mat')
    for suf, fn in (('_vertex', 'deposit_vertex'), ('_pixel', 'deposit_pixel')):
        d = c.op('dep_mat' + suf) or _mk(c, textDAT, 'dep_mat' + suf)
        t = _read(os.path.join(GLSL_DIR, 'ph_%s.glsl' % fn))
        if d.text != t:
            d.text = t
    m.par.vdat = 'dep_mat_vertex'
    m.par.pdat = 'dep_mat_pixel'
    m.seq.sampler.numBlocks = max(int(m.seq.sampler.numBlocks), 1)
    m.par.sampler0name = 'sAg'
    m.par.sampler0top = 'fx_agents'
    m.par.sampler0filter = 'nearest'
    m.seq.vec.numBlocks = max(int(m.seq.vec.numBlocks), 1)
    m.par.vec0name = 'uDep'
    for ax, e in zip('xyzw', (SIMW, SIMH, E('side'), E('dep'))):
        _expr(getattr(m.par, 'vec0value' + ax), e)
    m.par.blending = True
    for n in ('srcblend', 'destblend', 'srcblenda', 'destblenda'):
        getattr(m.par, n).val = 'one'
    _try(m, 'postmultalpha', False)
    m.par.depthtest = False
    m.par.depthwriting = False
    m.comment = 'Deposit: one 1-px point per agent at its trail texel, additive (exact sums in 32F).'
    geo = _mk(c, geometryCOMP, 'dep_geo')
    for ch in list(geo.children):
        if ch.name != 'sel':
            _sd(ch)
    s = geo.op('sel') or geo.create(selectPOP, 'sel')
    s.par.pop = '../pts'
    s.render = True
    s.display = True
    geo.par.material = 'dep_mat'
    geo.comment = 'Agent points (Select POP of ../pts), material dep_mat.'
    cam = _mk(c, cameraCOMP, 'dep_cam')
    cam.comment = 'Unused by the shader (it writes clip space) but a Render TOP needs a camera.'
    r = _mk(c, renderTOP, 'deposit')
    r.par.camera = 'dep_cam'
    r.par.geometry = 'dep_geo'
    r.par.lights = ''
    r.par.outputresolution = 'custom'
    _expr(r.par.resolutionw, SIMW)
    _expr(r.par.resolutionh, SIMH)
    r.par.format = 'rgba32float'
    r.par.antialias = 'aa1'
    r.par.bgcolorr = r.par.bgcolorg = r.par.bgcolorb = r.par.bgcolora = 0
    r.comment = 'Deposit map (sim res): rgb = species deposit, a = agents per cell.'
    return r


def build(parent_path='/project1/lab', panel=True, upto=None):
    del NOTES[:]
    Lg = _logic()
    pc = op(parent_path)
    c = pc.op(NAME) or pc.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('GN_physarum: slime mould agents (sense / rotate / move / deposit) + diffusing, decaying trail. In: in1 '
                 'TOP food map / image seed, in2 TOP mask (R > Maskthresh = blocked), in5 CHOP points (x y radius '
                 'strength deposit, uv), in6 CHOP audio. Effector Nulls (eff*: + attract, - repel). Out: out1 look, '
                 'out2 raw trail (species rgb), out3 agents (x y heading species). Pulse Opencontrols.')
    was_open = _close_window(c)
    _pars(c, Lg['PAGES'])
    lg = _code(c, 'ph_logic', _read(LOGIC_FILE))
    lg.comment = 'Pure logic + numpy reference (copy of builders/physarum_logic.py; tests test/test_physarum.py).'
    vx = _vec_exprs()

    # 1 Inputs
    blank = _blank(c, 'blank', SIMW, SIMH, 'rgba32float')
    blank.comment = 'Sim-res zero (trail Feedback start + stand-in for unwired TOP inputs).'
    ablank = _blank(c, 'agents_blank', SIDE, SIDE, 'rgba32float')
    ablank.comment = 'Agent-res zero (agents Feedback start).'
    ins = {n: _mk(c, inTOP, n) for n in ('in1', 'in2')}
    st = _mk(c, textTOP, 'seed_text')
    st.par.outputresolution = 'custom'
    _expr(st.par.resolutionw, SIMW)
    _expr(st.par.resolutionh, SIMH)
    _try(st, 'text', expr=PP.format('Seedtext'))
    _try(st, 'fontsizex', expr="parent().par.Textsize.eval() * (" + SIMH + ")")
    _try(st, 'alignx', menu_like=('center', 'centre'))
    _try(st, 'aligny', menu_like=('center', 'centre'))
    st.comment = 'Text food map / seed (Seedmode text or Foodsrc text). Default font only (T-76).'
    fs = _mk(c, switchTOP, 'food_sel')
    _wire(blank, fs, 0)
    _wire(ins['in1'], fs, 1)
    _wire(st, fs, 2)
    _expr(fs.par.index, "2 if (parent().par.Seedmode.eval() == 'text' or (parent().par.Seedmode.eval() != 'image' and "
                        "parent().par.Foodsrc.eval() == 'text')) else ({})".format(WIRED.format('in1')))
    ms = _mk(c, switchTOP, 'mask_sel')
    _wire(blank, ms, 0)
    _wire(ins['in2'], ms, 1)
    _expr(ms.par.index, WIRED.format('in2'))

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
    mouse.comment = 'Screen mouse (read only when Mousemode is on; tx ty -1..1, lselect).'
    eng = _script(c, 'engine', ENGINE_CB, [in5, in6, al])
    eng.comment = 'Once per frame: run / reset (also on Agents/Simh/Res change), preset morph (go, LFO, audio), gains, kick speed, effectors + points + mouse + bursts -> rows.'
    uni = _script(c, 'uni', uni_text(vx), [eng])
    uni.comment = 'Engine-fed GLSL uniforms as one vec4 array uV (one row per name in UNI_VECS): no per-frame par expressions.'
    pw = _mk(c, parameterexecuteDAT, 'ph_parwatch')
    if pw.text != PARWATCH:
        pw.text = PARWATCH
    pw.par.op = c
    pw.par.pars = '*'
    pw.par.custom = True
    pw.par.builtin = False
    pw.par.valuechange = True
    pw.par.onpulse = False
    pw.comment = 'Any custom par change -> the engine re-reads its pars (cached otherwise).'
    rows = _script(c, 'rows', ROWS_CB, [eng])
    rows.comment = 'Effector rows -> 64 samples x (x y z w) = uRows texture buffer.'
    pulses = _mk(c, parameterexecuteDAT, 'ph_pulses')
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

    afb = _mk(c, feedbackTOP, 'agents_fb')
    _wire(ablank, afb)
    tfb = _mk(c, feedbackTOP, 'trail_fb')
    _wire(blank, tfb)

    spec = dict(Lg['PASSES'])
    res = {'sim': (SIMW, SIMH), 'out': (RESW, RESH), 'half': (HALFW, HALFH), 'agents': (SIDE, SIDE)}
    made = {}

    def mk_pass(pname):
        s_ = spec[pname]
        uv = uni_vecs(vx)
        vecs = [(u, vx[u]) for u in s_['vecs'] if u not in uv]
        arrays = [(a, 'rows') for a in s_['arrays']]
        if any(u in uv for u in s_['vecs']):
            arrays.append(('uV', 'uni', 'uniformarray'))
        w, h = res[s_['res']]
        code = _code(c, 'fx_%s_compute' % pname, uni_shader(_shader(pname), uv))
        g = _glsl(c, 'fx_' + pname, code, w, h, s_['fmt'], vecs, arrays)
        for i, n in enumerate(s_['inputs']):
            _wire(made.get(n) or c.op(n), g, i)
        made['fx_' + pname] = g
        return g

    mk_pass('maps')
    ga = mk_pass('agents')
    _try(ga, 'inputfiltertype', 'nearest')
    afb.par.top = ga.name
    made['deposit'] = _deposit(c, vx)
    gt = mk_pass('trail')
    tfb.par.top = gt.name
    out2 = _mk(c, outTOP, 'out2')
    _wire(gt, out2)
    out3 = _mk(c, outTOP, 'out3')
    _wire(ga, out3)
    if upto == 1:
        return {'comp': c.path, 'ops': len(c.children), 'notes': list(NOTES), 'upto': 1}

    # Look
    ramp = _mk(c, rampTOP, 'ramp')
    ramp.par.outputresolution = 'custom'
    ramp.par.resolutionw, ramp.par.resolutionh = 256, 1
    ramp.comment = 'Inner ramp for Colormode ramp (edit its keys) unless Ramptop names another TOP.'
    ri = _mk(c, selectTOP, 'ramp_in')
    _expr(ri.par.top, "parent().par.Ramptop.eval() or op('ramp')")
    lk = mk_pass('look')
    _try(lk, 'inputextenduv', expr="'repeat' if parent().par.Edge.eval() == 'wrap' else 'hold'")
    _try(lk, 'inputfiltertype', 'linear')
    mk_pass('preview')
    out1 = _mk(c, outTOP, 'out1')
    _wire(made['fx_look'], out1)
    pv = _mk(c, nullTOP, 'preview')
    _wire(made['fx_preview'], pv)
    pv.comment = 'Preview: look + effector / point / mouse gizmos (not an output).'

    # Stats (internal)
    mk_pass('stat')
    mk_pass('astat')
    tcs = []
    for src, an_n, tc_n in (('fx_stat', 'an_avg', 'tc_avg'), ('fx_astat', 'an_aavg', 'tc_aavg')):
        an = _mk(c, analyzeTOP, an_n)
        _wire(made[src], an)
        _try(an, 'op', 'average')
        _try(an, 'analyzechannel', 'independent')
        tc = _mk(c, toptoCHOP, tc_n)
        tc.par.top = an_n
        _try(tc, 'downloadtype', 'nextframe')
        tcs.append(tc)
    stc = _script(c, 'stats', STATS_CB, tcs + [eng])
    stc.comment = 'mean cover peak meanr order alive steps agents cookms level morph nrows expected (internal).'

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
        {'title': 'Controls', 'role': 'control', 'ops': with_docked(['controls', 'controls_window', 'ph_pulses', 'ph_logic']),
         'body': 'zkit panel (pulse Opencontrols). ph_pulses: Reset / Reseed / Step / Burst / Morphgo -> engine.'},
        {'title': 'Effectors', 'role': 'input', 'ops': with_docked([e[0] for e in EFFECTOR_DEFAULTS]),
         'body': 'Null COMPs (Effectors par: eff*). tx/ty on a Planeh-tall plane, scale = radius; Effector page: '
                 'Strength (+ attract, - repel), Radius, Deposit, Falloff. Drawn in preview.'},
        {'title': '1 Inputs', 'role': 'input',
         'ops': with_docked(['in1', 'in2', 'blank', 'agents_blank', 'seed_text', 'food_sel', 'mask_sel', 'fx_maps',
                             'fx_maps_compute']),
         'body': 'in1 food map / image seed | text, in2 mask -> fx_maps (r mask, g food).'},
        {'title': '2 Control sources', 'role': 'input',
         'ops': with_docked(['in5', 'in6', 'aud_low', 'mouse', 'engine', 'engine_callbacks', 'ph_parwatch', 'uni',
                             'uni_callbacks', 'rows', 'rows_callbacks']),
         'body': 'engine (ph_logic.engine_step): run, reset, preset morph (go / LFO / audio), gains, kick speed, '
                 'effectors + points + mouse + bursts -> rows (uRows).'},
        {'title': 'State (feedback)', 'role': 'feedback', 'ops': with_docked(['agents_fb', 'trail_fb']),
         'body': 'agents_fb <- fx_agents, trail_fb <- fx_trail (previous frame). Sources for both sim passes.'},
        {'title': '3 Agents', 'role': 'process', 'ops': with_docked(['fx_agents', 'fx_agents_compute', 'out3']),
         'body': 'fx_agents (side x side): seed on reset; sense 3 sensors -> rotate -> move. agents_fb <- fx_agents.'},
        {'title': '4 Deposit', 'role': 'process',
         'ops': with_docked(['pts', 'dep_mat', 'dep_mat_vertex', 'dep_mat_pixel', 'dep_geo', 'dep_cam', 'deposit']),
         'body': 'Grid POP points -> dep_mat reads fx_agents -> 1-px points, additive -> deposit (exact sums).'},
        {'title': '5 Trail', 'role': 'process', 'ops': with_docked(['fx_trail', 'fx_trail_compute', 'out2']),
         'body': 'fx_trail: trail + deposit -> 3x3 diffuse -> decay -> injects -> mask. trail_fb <- fx_trail.'},
        {'title': '6 Look + out', 'role': 'output',
         'ops': with_docked(['ramp', 'ramp_in', 'fx_look', 'fx_look_compute', 'out1', 'fx_preview',
                             'fx_preview_compute', 'preview']),
         'body': 'fx_look (Resw x Resh) -> out1. out2 = raw trail, out3 = agents. fx_preview = look + gizmos.'},
        {'title': '7 Stats', 'role': 'output',
         'ops': with_docked(['fx_stat', 'fx_stat_compute', 'an_avg', 'tc_avg', 'fx_astat', 'fx_astat_compute',
                             'an_aavg', 'tc_aavg', 'stats', 'stats_callbacks']),
         'body': 'fx_stat / fx_astat -> Analyze average -> stats CHOP (mean cover peak order expected ...), internal.'},
    ]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'notes': list(NOTES), 'panel': str(info)[:300],
            'layout': str(lay)[:400]}
