# fluid2d builder - BN_fluid2d: 2D stable-fluids COMP (dye + velocity), all compute GLSL (T-46/T-47).
# Spec: docs/research/BN_fluid_cloth_sims.md section 5 (clean-room). How to build + live checks: docs/builds/fluid2d.md.
# No limits (user rule): open ranges, no luminance / flash guard; the operator decides.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fluid2d.py').read(), ns); ns['build']('/project1/lab')
# build(parent_path, panel=True, press_mode='blocked' | 'npasses' | 'chain'): idempotent (ops reused by name, texts / pars / wires
# re-set, custom par values kept, zkit panel refreshed in place). Iterations is read at build time: change it, rebuild.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy), own controls_window closed first, panel container never
# destroyed, network pane never moved. T-74/T-76: no numpyArray / evalTextSize anywhere in this builder.
# No Python functions in op storage (T-67). ASCII only.
import os

NAME = 'BN_fluid2d'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
GLSL_DIR = HERE + '/glsl'
LOGIC_FILE = os.path.join(HERE, 'fluid2d_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
NOTES = []

ENGINE_CB = """# engine: fluid2d control sources, once per frame (logic in fluid2d_logic, tested offline).
# in0 = in4 points CHOP, in1 = in5 audio, in2 = aud_low (low band of in5). Pulses arrive through push().
# State lives in this module (plain data), not in op storage (T-67). rows -> the emit Script CHOP.
STATE = {'st': None, 'ev': [], 'rows': []}

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

def onCook(scriptOp):
    L = op('fluid2d_logic').module
    P = parent()
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    ins = scriptOp.inputs
    p = L.engine_params(lambda n: getattr(P.par, n).eval(), project.cookRate)
    _w = lambda n: int(op(n).par.index.eval()) if op(n) is not None else 0
    inp = {'points': L.points_from_chans(_chans(ins[0] if len(ins) > 0 else None), p),
           'srcwired': _w('src_sel'), 'forcewired': _w('force_sel'),
           'level': L.block_rms(_blocks(ins[1] if len(ins) > 1 else None)),
           'low': L.block_rms(_blocks(ins[2] if len(ins) > 2 else None))}
    bc = P.par.Beatchop.eval()
    if bc is not None and getattr(bc, 'isCHOP', False) and bc.numChans:
        ch = bc['beat'] if bc['beat'] is not None else bc[0]
        inp['extbeat'] = 1 if ch.eval() > 0.5 else 0
    ev = STATE['ev']
    STATE['ev'] = []
    st, o, rows = L.engine_step(STATE['st'], absTime.seconds, p, inp, ev)
    sp = getattr(P.par, 'Status', None)                  # drop-in: say why a fresh copy is black
    if sp is not None and hasattr(L, 'idle_note'):
        eo = getattr(P.par, 'Effon', None)
        note = L.idle_note(p, inp, bool(eo.eval()) if eo is not None else False) or ('running' if o['awake'] else 'asleep (idle)')
        if sp.eval() != note:
            ro = sp.readOnly
            sp.readOnly = False
            sp.val = note
            sp.readOnly = ro
    STATE['st'] = st
    STATE['rows'] = rows
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for n in L.ENGINE_CHANS:
        scriptOp.appendChan(n)[0] = float(o[n])
    return
"""

EMIT_CB = """# emit: the engine's emitter rows -> 24 samples x (x y z w) = the uEmit texture buffer (3 texels per emitter).
def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def onCook(scriptOp):
    L = op('fluid2d_logic').module
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    ch = L.pack_rows(op('engine_callbacks').module.STATE['rows'])
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = len(ch[0])
    for n, vals in zip('xyzw', ch):
        scriptOp.appendChan(n).vals = vals
    return
"""

STATS_CB = """# stats: out3 numbers. in0 = tc_max (Analyze max of fx_stat: r |v|, g |div|), in1 = tc_avg (average), in2 = tc_dye
# (average of fx_advdye), in3 = engine. No TOP pixel readback in Python (T-74): TOP to CHOP does the download.
def _v(o, i):
    return float(o[i].eval()) if o is not None and o.numChans > i else 0.0

def _e(o, n):
    return float(o[n].eval()) if o is not None and o[n] is not None else 0.0

def onCook(scriptOp):
    P = parent()
    ins = list(scriptOp.inputs) + [None] * 4
    mx, av, dy, en = ins[0], ins[1], ins[2], ins[3]
    cook = 0.0
    for c in P.children:
        if c.family in ('TOP', 'CHOP'):
            cook += float(getattr(c, 'cpuCookTime', 0.0) or 0.0) + float(getattr(c, 'gpuCookTime', 0.0) or 0.0)
    vals = {'maxvel': _v(mx, 0), 'meanvel': _v(av, 0), 'divmax': _v(mx, 1),
            'dyesum': (_v(dy, 0) + _v(dy, 1) + _v(dy, 2)) * int(P.par.Resw.eval()) * int(P.par.Resh.eval()),
            'cookms': cook, 'steps': _e(en, 'steps'), 'beat': _e(en, 'beat'), 'audiolevel': _e(en, 'audiolevel')}
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for n in op('fluid2d_logic').module.STAT_CHANS:
        scriptOp.appendChan(n)[0] = vals[n]
    return
"""

PULSES = """# fluid_pulses: Reset (engine + Feedback TOPs back to blank) / Burst / Step -> engine.
def onPulse(par):
    eng = parent().op('engine_callbacks').module
    n = par.name
    if n == 'Reset':
        eng.push('reset')
        # T-85: resetpulse did not clear the loops live (31550); hold `reset` on for 3 frames instead.
        for f in ('vel_fb', 'press_fb', 'dye_fb'):
            o = parent().op(f)
            if o is not None and getattr(o.par, 'reset', None) is not None:
                o.par.reset = True
        run("c = op(args[0])\\nfor f in ('vel_fb', 'press_fb', 'dye_fb'):\\n    o = c.op(f)\\n"
            "    if o is not None: o.par.reset = False", parent().path, delayFrames=3)
    elif n == 'Burst':
        eng.push('burst')
    elif n == 'Step':
        eng.push('step')
    return
"""

UNI_HEAD = """# uni (perf 28 Oct, as GN_physarum T-214): the GLSL uniforms that read the engine (uDye uForce uStep) as ONE vec4
# uniform array uV (row k = UNI_VECS[k]); generated by builders/fluid2d.py from _vec_exprs(). The ~20 guarded
# engine-reading par expressions on 8 GLSL TOPs cost Python every frame; this Script CHOP packs the same values.
import numpy as np
SHAPE = {'n': None}

def onSetupParameters(scriptOp):
    return

"""

UNI_TAIL = """
def onCook(scriptOp):
    P = parent()
    o = scriptOp.inputs[0] if scriptOp.inputs else None

    def _e(n):
        ch = o[n] if o is not None else None
        return ch.eval() if ch is not None else 0.0
    v = np.array(uni_rows(_e, P), dtype=np.float32)
    if SHAPE['n'] != len(v):                   # (numChans raises while the CHOP cooks: never read it here)
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
    return sorted(u for u, ex in vx.items() if any("op('engine')" in str(e) for e in ex))


def _py_comp(e):
    import re
    e = re.sub(E_RE, lambda m: "_e(%r)" % m.group(1), str(e))
    e = e.replace('parent().par.', 'P.par.')
    return 'float(%s)' % e


def uni_text(vx):
    names = uni_vecs(vx)
    lines = ['UNI_VECS = %r' % (names,), '', 'def uni_rows(_e, P):', '    return [']
    for u in names:
        lines.append('        [%s],   # %s' % (', '.join(_py_comp(e) for e in vx[u]), u))
    lines.append('    ]')
    return UNI_HEAD + '\n'.join(lines) + '\n' + UNI_TAIL


def uni_shader(text, names):
    """GLSL text: each 'uniform vec4 uX;' of an engine-fed uniform becomes '#define uX uV[k]' (bodies unchanged)."""
    import re
    decl = 'uniform vec4 uV[%d];\n' % len(names)
    for k, u in enumerate(names):
        rep = '#define %s uV[%d]' % (u, k)
        text, n = re.subn(r'^uniform vec4 %s;' % u, (decl + rep) if decl else rep, text, count=1, flags=re.M)
        if n:
            decl = ''                          # uV declared once, where the first engine-fed uniform was
    return text


WIRED = ("1 if any(len(cn.connections) for cn in parent().inputConnectors "
         "if cn.inOP is not None and cn.inOP.name == '{}') else 0")
PP = "parent().par.{}"
SIMW = ("op('fluid2d_logic').module.sim_size(parent().par.Resw.eval(), parent().par.Resh.eval(), "
        "parent().par.Simh.eval())[0]")
SIMH = "max(1, int(round(parent().par.Simh.eval())))"
RESW = "max(1, int(parent().par.Resw.eval()))"
RESH = "max(1, int(parent().par.Resh.eval()))"
DYE = ("op('fluid2d_logic').module.dye_size(parent().par.Resw.eval(), parent().par.Resh.eval(), "
       "parent().par.Quality.eval())[{}]")
DYEW, DYEH = DYE.format(0), DYE.format(1)
AWAKE = ("1 if (not parent().par.Idlesleep.eval() or op('engine')['awake'] is None "
         "or op('engine')['awake'].eval() > 0.5) else 0")


def E(n):
    return "(op('engine')['{0}'].eval() if op('engine')['{0}'] is not None else 0.0)".format(n)


def _vec_exprs():
    v = {
        'uSim': (SIMW, SIMH, DYEW, DYEH),
        'uStep': (E('dt'), E('run'), PP.format('Edge.menuIndex'),
                  "parent().par.Resw.eval() / max(parent().par.Resh.eval(), 1)"),
        'uForce': (PP.format('Curl'), "parent().par.Forcegain.eval() * " + E('forceon'), PP.format('Maskthresh'),
                   PP.format('Veldiss')),
        'uDye': (PP.format('Dyediss'), "parent().par.Srcgain.eval() * " + E('srcon'), PP.format('Dyeblend.menuIndex'),
                 '0'),
        'uLook': (PP.format('Colormode.menuIndex'), PP.format('Exposure'), PP.format('Gamma'), PP.format('Speedref')),
        'uLook2': (PP.format('Alpha.menuIndex'), "1 if parent().par.Premult.eval() else 0", '0', '0'),
        'uBg': (PP.format('Bgr'), PP.format('Bgg'), PP.format('Bgb'), '0'),
    }
    for k in range(5):
        n = 'Pal%d' % (k + 1)
        v['uPal%d' % k] = (PP.format(n + 'r'), PP.format(n + 'g'), PP.format(n + 'b'), '0')
    return v


def _read(path):
    with open(path) as f:
        return f.read()


def _logic():
    ns = {}
    exec(_read(LOGIC_FILE), ns)
    return ns


def _shader(name, npasses=False):
    common = _read(os.path.join(GLSL_DIR, 'fluid2d_common.glsl'))
    body = _read(os.path.join(GLSL_DIR, 'fluid2d_%s.glsl' % name))
    if name == 'press_blocked':
        npasses = False                     # its own file: KB iterations per pass in shared memory
    return ('#define FLUID2D_NPASSES\n' if npasses else '') + common + '\n' + body


def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _sd_with_docked(o):
    if o is None or not o.valid:
        return
    for d in list(getattr(o, 'docked', []) or []):
        _sd(d)
    _sd(o)


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
    """Set a par whose name/menu is not confirmed on 31550 yet (LIVE CHECK): record misses in NOTES, never fail."""
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
            elif style == 'CHOP':
                p = page.appendCHOP(name, label=label)[0]
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
    g.seq.vec.numBlocks = max(1, len(vecs))      # exact: a rebuild moves the engine-fed vecs into uV (perf 28 Oct)
    if not vecs:
        g.par.vec0name = ''
        for ax in 'xyzw':
            p = getattr(g.par, 'vec0value' + ax)
            p.mode = ParMode.CONSTANT
            p.val = 0
    for k, (un, ex) in enumerate(vecs):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for ax, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, ax)), e)
    g.seq.array.numBlocks = max(1, len(arrays))
    if not arrays:
        g.par.array0name = ''
    for k, a in enumerate(arrays):
        getattr(g.par, 'array{}name'.format(k)).val = a[0]
        getattr(g.par, 'array{}type'.format(k)).val = 'vec4'
        getattr(g.par, 'array{}chop'.format(k)).val = a[1]
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


def _prep(c, name, src, w, h, fmt):
    r = _mk(c, resolutionTOP, name)
    _wire(src, r)
    r.par.outputresolution = 'custom'
    _expr(r.par.resolutionw, w)
    _expr(r.par.resolutionh, h)
    r.par.format = fmt
    return r


def _script(c, name, text, inputs):
    s = _mk(c, scriptCHOP, name)
    for i, src in enumerate(inputs):
        _wire(src, s, i)
    want = name + '_callbacks'                # other DATs call op('engine_callbacks').module: the name is fixed
    cb = c.op(want)
    if cb is None or cb.OPType != 'textDAT':
        cb = s.par.callbacks.eval()           # TD's own docked callbacks DAT
        if cb is None:
            cb = _mk(c, textDAT, want)
        elif cb.name != want and c.op(want) is None:
            cb.name = want
    if cb.text != text:
        cb.text = text
    s.par.callbacks = cb.name
    s.par.setuppars.pulse()
    return s


def _eff_hook(c):
    """Shared effectors adapter (builders/effectors.py attach, docs/builds/effectors.md): Effectors page + a few ops,
    idempotent, run after every build; a failure is reported, never a broken build."""
    try:
        ns = dict(globals())
        exec(open(REPO + '/builders/effectors.py').read(), ns)
        return ns['attach'](c.path)
    except Exception as e:
        return 'effectors adapter skipped: %s' % e


def status_par(c):
    """Sim page Status (read only): running / asleep / idle with what to wire (drop-in, 28 Oct). Idempotent."""
    if getattr(c.par, 'Status', None) is None:
        pg = next((x for x in c.customPages if x.name == 'Sim'), None) or c.appendCustomPage('Sim')
        p = pg.appendStr('Status', label='Status')[0]
        p.readOnly = True
    return c.par.Status


def idle_upgrade(c):
    """Existing BN_fluid2d (main / a library copy), no rebuild: Status par + fluid2d_logic + engine_callbacks texts
    (drop-in idle note). Idempotent; -> what changed. Un-parked by the caller in a later exec."""
    changed = []
    if getattr(c.par, 'Status', None) is None:
        status_par(c)
        changed.append('Status')
    for name, txt in (('fluid2d_logic', _read(LOGIC_FILE)), ('engine_callbacks', ENGINE_CB)):
        d = c.op(name)
        if d is not None and d.text != txt:
            d.text = txt
            changed.append(name)
    return changed


def build(parent_path='/project1/lab', panel=True, press_mode='blocked'):
    del NOTES[:]
    Lg = _logic()
    pc = op(parent_path)
    c = pc.op(NAME) or pc.create(baseCOMP, NAME)
    c.allowCooking = True                      # never parked while being built (user rule)
    c.comment = ('BN_fluid2d: 2D stable fluid (compute GLSL). In: in1 TOP source dye, in2 TOP mask (white = solid), '
                 'in3 TOP force (RG), in4 CHOP points (x y vx vy radius strength r g b), in5 CHOP audio. Out: out1 '
                 'dye look, out2 velocity (raw, sim res), out3 stats. Manual / BPM / audio bursts. No limits. '
                 'Pulse Opencontrols.')
    was_open = _close_window(c)                # T-70: own window closed before any rebuild (reopened by zkit)
    _pars(c, Lg['PAGES'])
    status_par(c)
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)
    lg = _code(c, 'fluid2d_logic', _read(LOGIC_FILE))
    lg.comment = 'Pure logic + numpy reference (copy of builders/fluid2d_logic.py; tests test/test_fluid2d.py).'
    vx = _vec_exprs()

    # 1 Inputs
    blank_sim = _blank(c, 'blank_sim', SIMW, SIMH, 'rgba32float')
    blank_dye = _blank(c, 'blank_dye', DYEW, DYEH, 'rgba16float')
    blank_sim.comment = 'Sim-res zero (Feedback reset source + stand-in for unwired in2 / in3).'
    blank_dye.comment = 'Dye-res zero, alpha 0 (Feedback reset source + stand-in for unwired in1).'
    ins = {}
    for n in ('in1', 'in2', 'in3'):
        ins[n] = _mk(c, inTOP, n)
    sels = {}
    for n, sel, blank in (('in1', 'src_sel', blank_dye), ('in2', 'mask_sel', blank_sim), ('in3', 'force_sel', blank_sim)):
        s = _mk(c, switchTOP, sel)
        _wire(blank, s, 0)
        _wire(ins[n], s, 1)
        _expr(s.par.index, WIRED.format(n))       # (an In TOP's .inputs stays empty when wired, 31550: read the connector)
        sels[sel] = s
    _prep(c, 'src_prep', sels['src_sel'], DYEW, DYEH, 'rgba16float').comment = 'in1 at dye res: rgb * a * Srcgain * dt is added.'
    _prep(c, 'mask_prep', sels['mask_sel'], SIMW, SIMH, 'rgba8fixed').comment = 'in2 at sim res: R > Maskthresh = solid.'
    _prep(c, 'force_prep', sels['force_sel'], SIMW, SIMH, 'rgba32float').comment = 'in3 at sim res: RG = acceleration, screen heights / s^2.'

    # 2 Control sources
    in4 = _mk(c, inCHOP, 'in4')
    in5 = _mk(c, inCHOP, 'in5')
    al = _mk(c, audiofilterCHOP, 'aud_low')
    _wire(in5, al)
    _try(al, 'filter', menu_like=('low',))
    if getattr(al.par, 'cutofffrequency', None) is not None:
        _try(al, 'cutofffrequency', expr=PP.format('Lowhz'))
    else:
        _try(al, 'cutoff', expr=PP.format('Lowhz'))
    al.comment = 'Low band of in5 (Lowhz); the engine takes its RMS for the kick detector. Never routed to a speaker.'
    eng = _script(c, 'engine', ENGINE_CB, [in4, in5, al])
    eng.comment = 'Once per frame: dt / run / steps, BPM clock, kick detector, bursts, in4 points -> emitter rows.'
    uv = uni_vecs(vx)
    uni = _script(c, 'uni', uni_text(vx), [eng])
    uni.comment = 'Engine-fed GLSL uniforms (%s) as one vec4 array uV: no per-frame par expressions (T-214).' % ' '.join(uv)
    emit = _script(c, 'emit', EMIT_CB, [eng])
    emit.comment = 'Emitter rows -> 24 samples x (x y z w) = uEmit texture buffer.'
    pulses = _mk(c, parameterexecuteDAT, 'fluid_pulses')
    if pulses.text != PULSES:
        pulses.text = PULSES
    pulses.par.op = c
    pulses.par.pars = 'Reset Burst Step'
    pulses.par.custom = True
    pulses.par.builtin = False
    pulses.par.valuechange = False
    pulses.par.onpulse = True

    # Feedback (loop ends are set below)
    vel_fb = _mk(c, feedbackTOP, 'vel_fb')
    _wire(blank_sim, vel_fb)
    press_fb = _mk(c, feedbackTOP, 'press_fb')
    _wire(blank_sim, press_fb)
    dye_fb = _mk(c, feedbackTOP, 'dye_fb')
    _wire(blank_dye, dye_fb)

    # 3..7 compute passes
    K = max(1, int(c.par.Iterations.eval()))
    blocked = press_mode == 'blocked'           # perf lane 2 (27 Oct): 8 Jacobi iterations per dispatch, 0.31x
    npasses = press_mode == 'npasses' or blocked
    spec = dict(Lg['PASSES'])
    res = {'sim': (SIMW, SIMH), 'dye': (DYEW, DYEH), 'out': (RESW, RESH)}
    made = {}

    def mk_pass(pname, opname, code_dat, inputs, extra_vecs=None):
        s_ = spec[pname]
        vecs = [(u, (extra_vecs or {}).get(u) or vx[u]) for u in s_['vecs'] if u not in uv]
        arrays = [(a, 'emit') for a in s_['arrays']]
        if any(u in uv for u in s_['vecs']):
            arrays.append(('uV', 'uni', 'uniformarray'))
        w, h = res[s_['res']]
        g = _glsl(c, opname, code_dat, w, h, s_['fmt'], vecs, arrays)
        for i, src in enumerate(inputs):
            _wire(src, g, i)
        made[opname] = g
        return g

    def code_for(pname, npass=False):
        return _code(c, 'fx_%s_compute' % pname, uni_shader(_shader(pname, npass), uv))

    def ins_of(pname):
        return [made.get(n) or c.op(n) for n in spec[pname]['inputs']]

    mk_pass('pre', 'fx_pre', code_for('pre'), [vel_fb, c.op('force_prep'), c.op('mask_prep')])
    mk_pass('vort', 'fx_vort', code_for('vort'), ins_of('vort'))
    mk_pass('div', 'fx_div', code_for('div'), ins_of('div'))
    pcode = (_code(c, 'fx_press_compute', uni_shader(_shader('press_blocked'), uv)) if blocked else code_for('press', npasses))
    chain = []
    if npasses:
        for o in [x for x in c.children if x.name.startswith('fx_press_') and x.name[9:].isdigit()]:
            _sd_with_docked(o)
        its = "max(1, int(parent().par.Iterations.eval()))"
        g = mk_pass('press', 'fx_press', pcode, [press_fb, made['fx_div']],
                    {'uPress': (PP.format('Warmstart'), PP.format('Relax'), its if blocked else '0', '0')})
        _try(g, 'npasses', expr=("(%s + 7) // 8" % its) if blocked else its)
        chain = [g]
    else:
        _sd_with_docked(c.op('fx_press') if c.op('fx_press') is not None and c.op('fx_press').OPType == 'glslTOP' else None)
        for o in [x for x in c.children if x.name.startswith('fx_press_') and x.name[9:].isdigit() and int(x.name[9:]) > K]:
            _sd_with_docked(o)
        prev = press_fb
        for k in range(1, K + 1):
            g = mk_pass('press', 'fx_press_%02d' % k, pcode, [prev, made['fx_div']],
                        {'uPress': (PP.format('Warmstart') if k == 1 else '1', PP.format('Relax'), '0', '0')})
            chain.append(g)
            prev = g
    last = chain[-1]
    press_fb.par.top = last.name
    mk_pass('grad', 'fx_grad', code_for('grad'), [last, made['fx_vort']])
    adv = mk_pass('advvel', 'fx_advvel', code_for('advvel'), ins_of('advvel'))
    vel_fb.par.top = adv.name
    ad = mk_pass('advdye', 'fx_advdye', code_for('advdye'), [dye_fb, made['fx_grad'], c.op('src_prep')])
    dye_fb.par.top = ad.name
    mk_pass('look', 'fx_look', code_for('look'), ins_of('look'))
    mk_pass('stat', 'fx_stat', code_for('stat'), ins_of('stat'))

    # Outputs (output only)
    # Idle sleep (perf pass): when the engine says nothing visible is left, out1 shows sleep_bg (what fx_look gives
    # for zero dye) and the whole sim chain is not pulled, so it costs nothing; the first injection wakes it.
    sbg = _blank(c, 'sleep_bg', RESW, RESH, 'rgba16float')
    for ch in 'rgb':
        _expr(getattr(sbg.par, 'color' + ch), "parent().par.Bg{0}.eval() if parent().par.Alpha.menuIndex == 0 else 0".format(ch))
    _expr(sbg.par.alpha, "1 if parent().par.Alpha.menuIndex == 0 else 0")
    sbg.comment = 'out1 while asleep (Idlesleep): fx_look of zero dye = Bg opaque, or transparent black.'
    osel = _mk(c, switchTOP, 'out_sel')
    _wire(made['fx_look'], osel, 0)
    _wire(sbg, osel, 1)
    _expr(osel.par.index, "0 if ({}) else 1".format(AWAKE))
    osel.comment = 'fx_look while the engine is awake, sleep_bg when idle (sim not cooked).'
    out1 = _mk(c, outTOP, 'out1')
    _wire(osel, out1)
    out2 = _mk(c, outTOP, 'out2')
    _wire(made['fx_grad'], out2)

    # Stats
    an = {}
    for n, src, how in (('an_max', 'fx_stat', 'maximum'), ('an_avg', 'fx_stat', 'average'), ('an_dye', 'fx_advdye', 'average')):
        a = _mk(c, analyzeTOP, n)
        _wire(made[src], a)
        _try(a, 'op', how)
        _try(a, 'analyzechannel', 'independent')
        an[n] = a
    tcs = []
    for n, src in (('tc_max', 'an_max'), ('tc_avg', 'an_avg'), ('tc_dye', 'an_dye')):
        t = _mk(c, toptoCHOP, n)
        t.par.top = src
        _try(t, 'downloadtype', 'nextframe')       # one frame late, no GPU stall
        tcs.append(t)
    stc = _script(c, 'stats', STATS_CB, tcs + [eng])
    stc.comment = 'out3: maxvel meanvel divmax dyesum cookms steps beat audiolevel (velocities in sim cells / s).'
    out3 = _mk(c, outCHOP, 'out3')
    _wire(stc, out3)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    # Controls (zkit)
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

    press_names = [g.name for g in chain]
    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': with_docked(['controls', 'controls_window', 'fluid_pulses', 'fluid2d_logic']),
         'body': 'zkit panel (Sim Input Audio Look Control; pulse Opencontrols). fluid_pulses: Reset / Burst / Step.'},
        {'title': '1 Inputs', 'role': 'input',
         'ops': with_docked(['in1', 'in2', 'in3', 'src_sel', 'mask_sel', 'force_sel', 'src_prep', 'mask_prep', 'force_prep']),
         'body': 'in1 source dye (dye res), in2 mask (sim res, R > Maskthresh = solid), in3 force RG (sim res). Unwired = zero.'},
        {'title': '2 Control sources', 'role': 'input',
         'ops': with_docked(['in4', 'in5', 'aud_low', 'engine', 'engine_callbacks', 'uni', 'uni_callbacks', 'emit',
                             'emit_callbacks']),
         'body': 'engine (Script CHOP, fluid2d_logic.engine_step): dt, BPM clock, kick, bursts, in4 points -> emit (uEmit).'},
        {'title': 'Feedback', 'role': 'feedback', 'ops': with_docked(['blank_sim', 'blank_dye', 'vel_fb', 'press_fb', 'dye_fb']),
         'body': 'One loop per state: vel_fb <- fx_advvel, press_fb <- last fx_press, dye_fb <- fx_advdye. Reset = blank.'},
        {'title': '3 Forces', 'role': 'process', 'ops': with_docked(['fx_pre', 'fx_pre_compute', 'fx_vort', 'fx_vort_compute']),
         'body': 'fx_pre: curl + emitter impulses + in3 force, solids from in2. fx_vort: vorticity confinement (Curl).'},
        {'title': '4 Project', 'role': 'process',
         'ops': with_docked(['fx_div', 'fx_div_compute', 'fx_press_compute'] + press_names + ['fx_grad', 'fx_grad_compute']),
         'body': 'Divergence -> %d weighted-Jacobi passes (%s) -> subtract gradient = divergence-free velocity.'
                 % (K, ('blocked (8 per pass)' if blocked else 'npasses') if npasses else 'unrolled chain')},
        {'title': '5 Advect', 'role': 'process', 'ops': with_docked(['fx_advvel', 'fx_advvel_compute', 'fx_advdye', 'fx_advdye_compute']),
         'body': 'Semi-Lagrangian: velocity at sim res, dye at dye res (+ in1 source + emitter splats).'},
        {'title': '6 Look + out', 'role': 'output', 'ops': with_docked(['fx_look', 'fx_look_compute', 'sleep_bg', 'out_sel', 'out1', 'out2']),
         'body': 'fx_look (Resw x Resh, dye sampled bilinear): colour, exposure, gamma, alpha -> out_sel -> out1 '
                 '(sleep_bg when idle). out2 = projected velocity (raw).'},
        {'title': '7 Stats', 'role': 'output',
         'ops': with_docked(['fx_stat', 'fx_stat_compute', 'an_max', 'an_avg', 'an_dye', 'tc_max', 'tc_avg', 'tc_dye',
                             'stats', 'stats_callbacks', 'out3']),
         'body': 'fx_stat (|v|, |div|) -> Analyze max / average -> TOP to CHOP -> stats -> out3.'},
    ]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    eff = _eff_hook(c)
    return {'effectors': str(eff)[:300],
            'comp': c.path, 'press': '%s x%d' % (('blocked' if blocked else 'npasses') if npasses else 'chain', K), 'ops': len(c.children),
            'notes': list(NOTES), 'panel': str(info)[:300], 'layout': str(lay)[:400]}
