# strobe builder - FX_strobe: TOP strobe effector driven by audio / BPM / LFO / manual triggers.
# Spec: docs/research/AX_strobber.md (our own clean-room design; idea credit Strobber by Skywalker.Visuals).
# No limits (user rule 26 Oct): open ranges, no flash cap, no limiter stage; the operator decides.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/strobe.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set; custom par values kept; zkit panel refreshed in place.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy); the COMP's controls_window is closed before a rebuild
# (zkit reopens it if it was open); the panel container is never destroyed; the network pane is never moved here.
# No Python functions in op storage (T-67). ASCII only.
import os

NAME = 'FX_strobe'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'strobe_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')

SHADER = """// FX_strobe: one pass (T-46 safe). uFx = amt mode mix blackout; uColour = flash colour.
uniform vec4 uFx;
uniform vec4 uColour;
out vec4 fragColor;
void main() {
    vec4 c = texture(sTD2DInputs[0], vUV.st);
    float a = uFx.x;
    int m = int(uFx.y + 0.5);
    vec4 f = c;
    if (m == 0)      f.rgb = c.rgb + uColour.rgb * a;                 // Lift (add)
    else if (m == 1) f.rgb = c.rgb * (1.0 - a);                       // Dip (to black)
    else if (m == 2) f.rgb = mix(c.rgb, abs(c.rgb - uColour.rgb), a); // Invert (difference)
    else             f.rgb = mix(c.rgb, uColour.rgb, a);              // Colour (replace)
    if (m != 1) f.a = max(c.a, a);
    vec4 o = mix(c, f, uFx.z);
    if (uFx.w > 0.5) o = vec4(0.0, 0.0, 0.0, 1.0);                    // Blackout
    fragColor = TDOutputSwizzle(o);
}
"""

ENGINE_CB = """# engine: the strobe trigger + envelope, once per frame (logic in strobe_logic, tested offline).
# Input 0 = control CHOP (low level kick), input 1 = Keyboard In (Key). Pulses arrive through push().
# State lives in this module (plain dict), not in op storage.
STATE = {'st': None, 'ev': []}

def push(e):
    STATE['ev'].append(e)

def reset():
    STATE['st'] = None

def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def _chan(o, name):
    if o is None:
        return 0.0
    ch = o[name]
    if ch is None:
        return 0.0
    v = ch.vals
    return float(max(v)) if len(v) else 0.0

def onCook(scriptOp):
    L = op('strobe_logic').module
    P = parent()
    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0
    ins = scriptOp.inputs
    src = P.par.Source.eval()
    val = _chan(ins[0] if len(ins) > 0 else None, src) if src in L.AUDIO_SOURCES else 0.0
    kb = ins[1] if len(ins) > 1 else None
    key = 1 if (kb is not None and kb.numChans and kb[0].eval() > 0.5) else 0
    link_bpm = None
    lk = P.par.Linkchop.eval()
    if lk is not None and getattr(lk, 'isCHOP', False) and lk['tempo'] is not None:
        link_bpm = float(lk['tempo'].eval())
    p = {
        'source': src, 'threshold': P.par.Threshold.eval(), 'division': int(P.par.Division.eval()),
        'tempo': P.par.Tempo.eval(), 'bpm': P.par.Bpm.eval(), 'project_bpm': float(op('/local/time').par.tempo.eval()),
        'note': P.par.Note.eval(), 'notemod': P.par.Notemod.eval(), 'phase': P.par.Phase.eval(),
        'swing': P.par.Swing.eval(), 'rate': P.par.Rate.eval(), 'burstcount': P.par.Burstcount.eval(),
        'hold': P.par.Hold.eval(), 'attack': P.par.Attack.eval(), 'release': P.par.Release.eval(),
        'depth': P.par.Depth.eval(), 'ease': P.par.Ease.eval(), 'blackout': P.par.Blackout.eval(),
    }
    ev = STATE['ev']
    STATE['ev'] = []
    st, o = L.step(STATE['st'], absTime.seconds, {'value': val, 'key': key, 'flash': bool(P.par.Flash.eval()),
                                                  'link_bpm': link_bpm}, p, ev)
    STATE['st'] = st
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for n in ('env', 'lin', 'hit', 'count', 'beat', 'bpm', 'armed', 'hits', 'value'):
        scriptOp.appendChan(n)[0] = float(val if n == 'value' else o[n])
    scriptOp.appendChan('blackout')[0] = 1.0 if p['blackout'] else 0.0
    return
"""

PULSES = """# strobe_pulses: Fire / Burst / Resync -> engine; Tap -> tap_times + Bpm (+ resync on the tap).
def onPulse(par):
    eng = parent().op('engine_callbacks').module
    n = par.name
    if n == 'Fire':
        eng.push('fire')
    elif n == 'Burst':
        eng.push('burst')
    elif n == 'Resync':
        eng.push('resync')
    elif n == 'Tap':
        L = parent().op('strobe_logic').module
        t = parent().op('tap_times')
        taps = []
        for i in range(t.numRows):
            try:
                taps.append(float(t[i, 0].val))
            except ValueError:
                pass
        taps, bpm = L.tap_bpm(taps, absTime.seconds)
        t.clear()
        for x in taps:
            t.appendRow([repr(x)])
        if bpm is not None:
            parent().par.Bpm = round(bpm, 3)
        eng.push('resync')
    return
"""

P_EXPR = "parent().par.{}.eval()"

def _logic():
    ns = {}
    exec(open(LOGIC_FILE).read(), ns)
    return ns


def _pages(Lg):
    return [
        ('Trigger', [
            ('Source', 'Menu', 'kick', {'names': Lg['SOURCES'], 'labels': ['Kick', 'Low', 'Level', 'BPM', 'LFO', 'Manual']}),
            ('Threshold', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Threshold'}),
            ('Division', 'Menu', '1', {'names': Lg['DIVISIONS'], 'labels': ['Every', '1/2', '1/4', '1/8', '1/16'],
                                       'label': 'Every Nth'}),
            ('Hold', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Hold gap s'}),
            ('Rate', 'Float', 2.0, {'min': 0, 'max': 30, 'label': 'LFO rate Hz'}),
        ]),
        ('Tempo', [
            ('Tempo', 'Menu', 'project', {'names': Lg['TEMPOS'], 'labels': ['Project', 'Manual', 'Link', 'Tap']}),
            ('Bpm', 'Float', 120.0, {'min': 20, 'max': 300, 'label': 'BPM'}),
            ('Tap', 'Pulse', None, {'label': 'Tap'}),
            ('Note', 'Menu', 'n4', {'names': Lg['NOTES'], 'labels': Lg['NOTE_LABELS']}),
            ('Notemod', 'Menu', 'straight', {'names': Lg['NOTEMODS'], 'labels': ['Straight', 'Triplet', 'Dotted'],
                                            'label': 'Feel'}),
            ('Phase', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Phase'}),
            ('Swing', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Swing'}),
            ('Resync', 'Pulse', None, {'label': 'Resync'}),
        ]),
        ('Manual', [
            ('Fire', 'Pulse', None, {'label': 'Fire'}),
            ('Flash', 'Momentary', False, {'label': 'Flash (hold)'}),
            ('Burst', 'Pulse', None, {'label': 'Burst'}),
            ('Burstcount', 'Int', 4, {'min': 1, 'max': 32, 'label': 'Burst hits'}),
            ('Key', 'Str', 'space', {'label': 'Fire key'}),
        ]),
        ('Look', [
            ('Mode', 'Menu', 'lift', {'names': Lg['MODES'], 'labels': ['Lift', 'Dip', 'Invert', 'Colour']}),
            ('Attack', 'Float', 0.01, {'min': 0, 'max': 1, 'label': 'Attack s'}),
            ('Release', 'Float', 0.15, {'min': 0, 'max': 2, 'label': 'Release s'}),
            ('Ease', 'Menu', 'linear', {'names': Lg['EASES'], 'labels': ['Linear', 'In', 'Out', 'In-out']}),
            ('Depth', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Depth'}),
            ('Mix', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Mix'}),
            ('Colour', 'RGB', (1.0, 1.0, 1.0), {'label': 'Colour'}),
            ('Blackout', 'Toggle', False, {'label': 'Blackout'}),
        ]),
        ('Input', [
            ('Input', 'Menu', 'auto', {'names': ['auto', 'live', 'test'], 'labels': ['Auto', 'Live (in1/in2)', 'Test'],
                                       'label': 'Input source'}),
            ('Testrate', 'Float', 2.0, {'min': 0, 'max': 16, 'label': 'Test pulse Hz'}),
            ('Linkchop', 'CHOP', '', {'label': 'Link CHOP (tempo)'}),   # e.g. td_link's /project1/link/out
        ]),
    ]


PANEL_PAGES = ['Trigger', 'Tempo', 'Manual', 'Look', 'Input']


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
            elif style == 'Momentary':
                p = page.appendMomentary(name, label=label)[0]
                p.default = default
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'CHOP':
                p = page.appendCHOP(name, label=label)[0]
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


def build(parent_path='/project1/lab', panel=True):
    Lg = _logic()
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('FX_strobe: strobe effector. In: in1 TOP (picture), in2 CHOP (low level kick 0..1). Out: out1 TOP. '
                 'Triggers: audio (kick/low/level, threshold + every Nth), BPM (project/manual/link/tap, note, '
                 'swing, phase), LFO, manual (Fire, Flash hold, Burst, Key). No limits. Pulse Opencontrols.')
    _close_window(c)
    _pars(c, _pages(Lg))
    if c.par.Linkchop.val == '/project1/link/out' and op('/project1/link/out') is None:
        c.par.Linkchop = ''                  # first build's default pointed at a Link COMP that is not built
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)

    # 1 Input (picture)
    in1 = _mk(c, inTOP, 'in1')
    nz = _mk(c, noiseTOP, 'test_noise')
    nz.par.outputresolution = 'custom'
    nz.par.resolutionw, nz.par.resolutionh = 1080, 1920
    nz.par.mono = False
    nz.par.period = 2.0
    _expr(nz.par.tz, 'absTime.seconds * 0.25')
    nz.comment = 'Test picture (Input = test, or auto with nothing wired into in1). 1080x1920.'
    live_top = "(1 if parent().par.Input.eval() == 'live' or (parent().par.Input.eval() == 'auto' and any(len(cn.connections) for cn in parent().inputConnectors if cn.inOP is not None and cn.inOP.name == 'in1')) else 0)"
    # (an In TOP's .inputs stays empty when the COMP input is wired, 31550: read the COMP's connector instead)
    img = _mk(c, switchTOP, 'img_src')
    img.inputConnectors[0].connect(nz)
    img.inputConnectors[1].connect(in1)
    _expr(img.par.index, live_top)

    # 2 Control input (CHOP)
    in2 = _mk(c, inCHOP, 'in2')
    tk = _mk(c, lfoCHOP, 'test_kick')
    tk.par.wavetype = 'square'
    _expr(tk.par.frequency, P_EXPR.format('Testrate'))
    tk.par.amp, tk.par.offset = 0.5, 0.5
    tk.par.channelname = 'kick'
    tw = _mk(c, lfoCHOP, 'test_wave')
    tw.par.wavetype = 'sin'
    _expr(tw.par.frequency, P_EXPR.format('Testrate') + ' * 0.25')
    tw.par.amp, tw.par.offset = 0.5, 0.5
    tw.par.channelname = 'low level'
    tm = _mk(c, mergeCHOP, 'test_ctl')
    tm.inputConnectors[0].connect(tk)
    tm.inputConnectors[1].connect(tw)
    tm.comment = 'Test control: kick = square 0..1 at Testrate Hz, low/level = sine 0..1 at Testrate/4.'
    ctl = _mk(c, switchCHOP, 'ctl_src')
    ctl.inputConnectors[0].connect(tm)
    ctl.inputConnectors[1].connect(in2)
    _expr(ctl.par.index, "(1 if parent().par.Input.eval() == 'live' or (parent().par.Input.eval() == 'auto' and op('in2').numChans) else 0)")
    kb = _mk(c, keyboardinCHOP, 'key_in')
    _expr(kb.par.keys, P_EXPR.format('Key'))
    kb.par.panels = 'controls'
    kb.comment = 'Fire key (Key par), only while this COMP\'s controls panel has focus.'

    # 3 Engine
    lg = _mk(c, textDAT, 'strobe_logic')
    lg.text = open(LOGIC_FILE).read()
    lg.comment = 'Pure logic (copy of builders/strobe_logic.py; tests in test/test_strobe.py).'
    taps = _mk(c, tableDAT, 'tap_times')
    if taps.numCols != 1 or any(not cell.val.replace('.', '', 1).isdigit() for row in taps.rows() for cell in row):
        taps.clear()                         # a new Table DAT starts with empty cells: tap_times holds numbers only
    eng = _mk(c, scriptCHOP, 'engine')
    eng.inputConnectors[0].connect(ctl)
    eng.inputConnectors[1].connect(kb)
    cb = eng.par.callbacks.eval()
    cb.text = ENGINE_CB
    if cb.name != 'engine_callbacks':
        cb.name = 'engine_callbacks'
    eng.par.callbacks = 'engine_callbacks'
    eng.par.setuppars.pulse()
    env = _mk(c, nullCHOP, 'env')
    env.inputConnectors[0].connect(eng)
    pulses = _mk(c, parameterexecuteDAT, 'strobe_pulses')
    pulses.text = PULSES
    pulses.par.op = c
    pulses.par.pars = 'Fire Burst Resync Tap'
    pulses.par.custom = True
    pulses.par.builtin = False
    pulses.par.valuechange = False
    pulses.par.onpulse = True

    # 4 Image
    g = _mk(c, glslTOP, 'strobe')
    gl = c.op('strobe_pixel')                # the GLSL TOP's own docked pixel DAT holds the shader
    if gl is None:
        gl = _mk(c, textDAT, 'strobe_pixel')
        gl.dock = g
    gl.text = SHADER
    g.par.pixeldat = gl
    if c.op('strobe_glsl') is not None:      # first build used a separate DAT
        _sd(c.op('strobe_glsl'))
    g.par.outputresolution = 'useinput'
    g.par.format = 'useinput'
    g.inputConnectors[0].connect(img)
    g.seq.vec.numBlocks = max(2, g.seq.vec.numBlocks)
    U = [('uFx', ["op('env')['env']", "parent().par.Mode.menuIndex", P_EXPR.format('Mix'), "op('env')['blackout']"]),
         ('uColour', [P_EXPR.format('Colourr'), P_EXPR.format('Colourg'), P_EXPR.format('Colourb'), '1'])]
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)
    out1 = _mk(c, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    # Controls (zkit)
    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=56, cols=8)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'strobe_pulses'],
         'body': 'zkit panel + window (pulse Opencontrols); strobe_pulses -> engine.'},
        {'title': '1 Picture in', 'role': 'input', 'ops': ['in1', 'test_noise', 'img_src'],
         'body': 'in1 TOP or the test noise (Input: auto = in1 when wired).'},
        {'title': '2 Control in', 'role': 'input', 'ops': ['in2', 'test_kick', 'test_wave', 'test_ctl', 'ctl_src', 'key_in'],
         'body': 'in2 CHOP (low level kick, e.g. AC_audio ctl_out) or test LFOs; Keyboard In = Fire key.'},
        {'title': '3 Engine', 'role': 'process', 'ops': ['strobe_logic', 'tap_times', 'engine', 'engine_callbacks', 'env'],
         'body': 'Script CHOP per frame (strobe_logic): triggers, Hold, envelope.'},
        {'title': '4 Image', 'role': 'output', 'ops': ['strobe', 'strobe_pixel', 'strobe_info', 'out1'],
         'body': 'One GLSL pass: Lift / Dip / Invert / Colour, Mix, Blackout.'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    return {'comp': c.path, 'panel': info, 'layout': str(lay)[:400]}
