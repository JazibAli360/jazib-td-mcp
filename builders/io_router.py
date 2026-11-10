# io_router builder - BP_io_router: 4 sources (local / NDI In / Syphon In / movie / test) -> fit + alpha-normalise ->
# premultiplied bus (A/B cross, manual or BPM-quantised cut) -> 4 sinks (Syphon Out / NDI Out), status table.
# Spec: docs/research/BP_ndi_syphon_spout_video_io.md section 3 (v1 subset; record/touch/camera sinks+sources next).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/io_router.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, pars/wires re-set, custom par values kept. T-70: nothing destroyed directly.
# SAFETY: NDI Out / Syphon Out / NDI In are active=True when created on 31550 (seen live 26 Oct); every one gets an
# expression in the same script, so nothing sends or receives until the user turns a sink/source on
# (O<n>active / S<n>active, default off). Syphon In has no active par: its sender name is '__off__' unless kind=syphon.
# No Python functions in op storage (T-67). No audio device opened. ASCII only.
import os

NAME = 'BP_io_router'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'io_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')

ALPHA_SHADER = """// io alpha pass (spec 3.5). uMode.x: 0 premult->straight, 1 straight->premult,
// 2 drop alpha (premult in), 3 drop alpha (straight in), 4 passthrough. Single pass (T-46 safe).
uniform vec4 uMode;
out vec4 fragColor;
void main(){
  vec4 c = texture(sTD2DInputs[0], vUV.st);
  int m = int(uMode.x + 0.5);
  if (m == 0) c = vec4(c.a > 1e-4 ? c.rgb / c.a : vec3(0.0), c.a);
  else if (m == 1) c = vec4(c.rgb * c.a, c.a);
  else if (m == 2) c = vec4(c.rgb, 1.0);
  else if (m == 3) c = vec4(c.rgb * c.a, 1.0);
  fragColor = TDOutputSwizzle(c);
}
"""

TEST_SHADER = """// io test source: colour bars (top), 0..1 grey ramp (middle), horizontal alpha ramp of white + colours (bottom),
// moving bar so the picture is never static. Premultiplied output. 1080x1920.
uniform vec4 uT;
out vec4 fragColor;
void main(){
  vec2 uv = vUV.st;
  vec3 bars[6] = vec3[6](vec3(1,0,0), vec3(1,1,0), vec3(0,1,0), vec3(0,1,1), vec3(0,0,1), vec3(1,0,1));
  vec4 c;
  if (uv.y > 0.66) c = vec4(bars[int(min(5.0, uv.x * 6.0))], 1.0);
  else if (uv.y > 0.33) c = vec4(vec3(uv.x), 1.0);
  else { vec3 col = uv.y > 0.165 ? vec3(1.0) : bars[int(min(5.0, uv.y / 0.165 * 6.0))]; c = vec4(col * uv.x, uv.x); }
  float bar = step(abs(fract(uT.x * 0.25) - uv.x), 0.01);
  c = mix(c, vec4(1.0), bar);
  fragColor = TDOutputSwizzle(c);
}
"""

BUS_CB = """# bus_ctl: bus fade state machine (io_logic.bus_step), once per frame. Cut events arrive through push().
STATE = {'st': None, 'ev': []}

def push(e):
    STATE['ev'].append(e)

def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def onCook(scriptOp):
    L = op('io_logic').module
    P = parent()
    _clock = scriptOp.par.Frame.eval()
    p = {'mode': P.par.Xfademode.eval(), 'mix': P.par.Mix.eval(), 'bpm': P.par.Bpm.eval(),
         'div': float(P.par.Cutdiv.eval()), 'xfadetime': P.par.Xfadetime.eval(), 'curve': P.par.Fadecurve.eval()}
    ev = STATE['ev']
    STATE['ev'] = []
    st, o = L.bus_step(STATE['st'], absTime.seconds, p, ev)
    STATE['st'] = st
    if p['mode'] != 'manual':                       # short history for timing checks (last 1200 cooks, plain data)
        h = STATE.setdefault('hist', [])
        h.append((absTime.seconds, o['mix'], o['armed']))
        del h[:-1200]
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = 1
    for n in ('mix', 'target', 'armed', 'fading'):
        scriptOp.appendChan(n)[0] = float(o[n])
    return
"""

PULSES = """# io_pulses: Cutnow -> bus_ctl; Refreshsources -> status now.
def onPulse(par):
    if par.name == 'Cutnow':
        parent().op('bus_ctl_callbacks').module.push('cut')
    elif par.name == 'Refreshsources':
        parent().op('status_tick').module.tick(force=True)
    return
"""

STATUS_TICK = """# status_tick: every 30 frames rebuild the `status` and `issues` tables (facts only; nothing blocks).
STATE = {'last': {}, 'stale': {}, 't': None}

def _f(chop, name, default=''):
    if chop is None:
        return default
    c = chop[name]
    return default if c is None else round(float(c.eval()), 2)

def tick(force=False):
    L = op('io_logic').module
    P = parent()
    now = absTime.seconds
    dt = 0.0 if STATE['t'] is None else now - STATE['t']
    STATE['t'] = now
    rows = [L.STATUS_COLS]
    srcs, sinks = [], []
    for n in range(1, 5):
        kind = P.par['S%dkind' % n].eval()
        name = P.par['S%dname' % n].eval()
        srcs.append({'kind': kind, 'name': name, 'file': P.par['S%dfile' % n].eval()})
        out = op('s%d_out' % n)
        info = op('s%d_info' % n)
        cook = sum(o.cookTime for o in (op('s%d_sel' % n), op('s%d_fit' % n), op('s%d_alpha' % n)) if o is not None)
        stale = ''
        if kind == 'ndi':
            rf = _f(info, 'received_frames', 0)
            s = L.frame_hash_stale(STATE['last'].get(n), rf, STATE['stale'].get(n, 0.0), dt)
            STATE['last'][n], STATE['stale'][n] = rf, s
            stale = 1 if s >= P.par.Stalesec.eval() else 0
        rows.append(L.status_row(id='s%d' % n, kind=kind, name=name if kind in ('ndi', 'syphon') else '',
                    active=int(bool(P.par['S%dactive' % n].eval())) if kind == 'ndi' else (1 if kind != 'off' else 0),
                    w=out.width, h=out.height,
                    fps=_f(info, 'receive_fps') if kind == 'ndi' else '', queue=_f(info, 'queue_size') if kind == 'ndi' else '',
                    missed=_f(info, 'missed_frames') if kind == 'ndi' else '', cookms=round(cook, 3), stale=stale,
                    alpha=P.par['S%dinalpha' % n].eval() + '->premult'))
    for n in range(1, 5):
        kind = P.par['O%dkind' % n].eval()
        sinks.append({'kind': kind, 'src': P.par['O%dsrc' % n].eval(), 'name': P.par['O%dname' % n].eval(),
                      'active': P.par['O%dactive' % n].eval()})
        snd = op('o%d_ndi' % n) if kind == 'ndi' else op('o%d_syp' % n)
        info = op('o%d_info' % n)
        fmt = op('o%d_alpha' % n)
        rows.append(L.status_row(id='o%d' % n, kind=kind, name=P.par['O%dname' % n].eval(),
                    active=int(bool(snd.par.active.eval())) if kind != 'off' else 0,
                    w=fmt.width, h=fmt.height, skipped=_f(info, 'skipped_frames') if kind == 'ndi' else '',
                    queue=_f(info, 'num_connected') if kind == 'ndi' else '', cookms=round(fmt.cookTime, 3),
                    alpha='premult->' + P.par['O%doutalpha' % n].eval(),
                    note='src ' + P.par['O%dsrc' % n].eval()))
    plan = L.plan_routes(srcs, sinks)
    st = op('status')
    if force or [list(map(str, r)) for r in rows] != [[c.val for c in r] for r in st.rows()]:
        st.clear()
        st.appendRows([list(map(str, r)) for r in rows])
    iss = op('issues')
    want = [['issue']] + [[i] for i in plan['issues']]
    if [[c.val for c in r] for r in iss.rows()] != want:
        iss.clear()
        iss.appendRows(want)
    rt = op('routes')
    want = [['sink', 'kind', 'src', 'name', 'active']] + [[r['sink'], r['kind'], r['src'], r['name'], str(int(r['active']))] for r in plan['routes']]
    if [[c.val for c in r] for r in rt.rows()] != want:
        rt.clear()
        rt.appendRows(want)

def onFrameStart(frame):
    if frame % 30 == 0:
        tick()
    return
"""

P = "parent().par.{}.eval()"


def _pages():
    src_pars, sink_pars = [], []
    for n in range(1, 5):
        S = 'S%d' % n
        src_pars += [
            (S + 'kind', 'Menu', 'test' if n == 1 else 'off', {'names': ['off', 'local', 'ndi', 'syphon', 'movie', 'test'],
             'labels': ['Off', 'Local in%d' % n, 'NDI In', 'Syphon In', 'Movie', 'Test pattern'], 'label': 'S%d kind' % n}),
            (S + 'name', 'Str', '', {'label': 'S%d NDI/Syphon name' % n}),
            (S + 'active', 'Toggle', False, {'label': 'S%d NDI receive on' % n}),
            (S + 'inalpha', 'Menu', 'premult', {'names': ['premult', 'straight', 'none'],
             'labels': ['Premultiplied', 'Straight', 'None (opaque)'], 'label': 'S%d alpha in' % n}),
            (S + 'res', 'Menu', '1080x1920', {'names': ['input', '1080x1920', '1920x1080', '3840x2160', 'custom'],
             'labels': ['Input', '1080x1920', '1920x1080', '3840x2160', 'Custom'], 'label': 'S%d res' % n}),
            (S + 'resw', 'Int', 1080, {'min': 1, 'max': 8192, 'label': 'S%d custom w' % n}),
            (S + 'resh', 'Int', 1920, {'min': 1, 'max': 8192, 'label': 'S%d custom h' % n}),
            (S + 'fit', 'Menu', 'fitbest', {'names': ['fitbest', 'fill', 'native'], 'labels': ['Fit best', 'Fill', 'Native'],
             'label': 'S%d fit' % n}),
            (S + 'file', 'File', '', {'label': 'S%d movie file' % n}),
        ]
        O = 'O%d' % n
        sink_pars += [
            (O + 'kind', 'Menu', 'off', {'names': ['off', 'syphon', 'ndi'], 'labels': ['Off', 'Syphon Out', 'NDI Out'],
             'label': 'O%d kind' % n}),
            (O + 'src', 'Menu', 'bus', {'names': ['s1', 's2', 's3', 's4', 'bus'], 'labels': ['S1', 'S2', 'S3', 'S4', 'Bus'],
             'label': 'O%d source' % n}),
            (O + 'name', 'Str', 'TD_%s_%d' % (NAME, n), {'label': 'O%d sender name' % n}),
            (O + 'active', 'Toggle', False, {'label': 'O%d SEND (go-ahead)' % n}),
            (O + 'outalpha', 'Menu', 'premult', {'names': ['premult', 'straight', 'none'],
             'labels': ['Premultiplied', 'Straight', 'None (opaque)'], 'label': 'O%d alpha out' % n}),
            (O + 'fmt', 'Menu', 'fixed8', {'names': ['fixed8', 'fixed16'], 'labels': ['8-bit', '16-bit (NDI)'],
             'label': 'O%d format' % n}),
            (O + 'skip', 'Toggle', True, {'label': 'O%d NDI skip frames' % n}),
            (O + 'res', 'Menu', 'input', {'names': ['input', '1080x1920', '1920x1080', '3840x2160', 'custom'],
             'labels': ['Input', '1080x1920', '1920x1080', '3840x2160', 'Custom'], 'label': 'O%d res' % n}),
            (O + 'resw', 'Int', 1080, {'min': 1, 'max': 8192, 'label': 'O%d custom w' % n}),
            (O + 'resh', 'Int', 1920, {'min': 1, 'max': 8192, 'label': 'O%d custom h' % n}),
        ]
    s_names = ['s1', 's2', 's3', 's4']
    return [
        ('Bus', [
            ('Busa', 'Menu', 's1', {'names': s_names, 'labels': ['S1', 'S2', 'S3', 'S4'], 'label': 'Bus A'}),
            ('Busb', 'Menu', 's2', {'names': s_names, 'labels': ['S1', 'S2', 'S3', 'S4'], 'label': 'Bus B'}),
            ('Mix', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Mix A-B'}),
            ('Xfademode', 'Menu', 'manual', {'names': ['manual', 'bpm'], 'labels': ['Manual (Mix)', 'BPM cut'],
             'label': 'Fade mode'}),
            ('Bpm', 'Float', 120.0, {'min': 20, 'max': 300, 'label': 'BPM'}),
            ('Cutdiv', 'Menu', '1', {'names': ['0.25', '0.5', '1', '2', '4'], 'labels': ['1/4', '1/2', '1', '2', '4'],
             'label': 'Cut on beats'}),
            ('Xfadetime', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Fade time s'}),
            ('Fadecurve', 'Menu', 'linear', {'names': ['linear', 'smooth'], 'labels': ['Linear', 'Smooth'],
             'label': 'Fade curve'}),
            ('Cutnow', 'Pulse', None, {'label': 'Cut now'}),
            ('Stalesec', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Stale after s'}),
            ('Refreshsources', 'Pulse', None, {'label': 'Refresh status'}),
        ]),
        ('Sources', src_pars),
        ('Sinks', sink_pars),
    ]


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
                p.normMin, p.normMax = o['min'], o['max']      # slider range only, no clamps (no limits)
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
            elif style == 'File':
                p = page.appendFile(name, label=label)[0]
            p.default = default
            p.val = default


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
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = viewer
    return o


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _glsl(c, name, shader, src=None):
    g = _mk(c, glslTOP, name)
    for dk in list(g.docked):                       # GLSL TOP docks its own pixel/compute/info DATs: use the pixel one
        if dk.valid and dk.name == name + '_pixel':
            pass
    px = c.op(name + '_pixel')
    if px is None:
        px = _mk(c, textDAT, name + '_pixel')
        px.dock = g
    px.text = shader
    g.par.pixeldat = px
    if src is not None:
        g.inputConnectors[0].connect(src)
    return g


def _res_exprs(top, pre):
    m = "op('io_logic').module.parse_res(parent().par.{0}res.eval(), parent().par.{0}resw.eval(), parent().par.{0}resh.eval())".format(pre)
    _expr(top.par.outputresolution, "'useinput' if parent().par.{}res.eval() == 'input' else 'custom'".format(pre))
    _expr(top.par.resolutionw, "({} or (1080, 1920))[0]".format(m))
    _expr(top.par.resolutionh, "({} or (1080, 1920))[1]".format(m))


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('BP_io_router: 4 sources (local/NDI/Syphon/movie/test) -> fit + alpha to premult -> A/B bus -> 4 sinks '
                 '(Syphon/NDI Out, inactive until O<n>active). out1-4 sources, out5 bus, out6 stats CHOP, out7 status DAT.')
    _close_window(c)
    _pars(c, _pages())

    lg = _mk(c, textDAT, 'io_logic')
    lg.text = open(LOGIC_FILE).read()
    lg.comment = 'Pure logic (copy of builders/io_logic.py; tests in test/test_io_logic.py).'

    blank = _mk(c, constantTOP, 'blank')
    blank.par.alpha = 0
    blank.par.outputresolution = 'custom'
    blank.par.resolutionw, blank.par.resolutionh = 1080, 1920
    test = _glsl(c, 'test_src', TEST_SHADER)
    test.par.outputresolution = 'custom'
    test.par.resolutionw, test.par.resolutionh = 1080, 1920
    test.par.format = 'rgba8fixed'
    test.par.vec0name = 'uT'
    _expr(test.par.vec0valuex, 'absTime.seconds')

    # Sources
    for n in range(1, 5):
        S = 'S%d' % n
        i = _mk(c, inTOP, 'in%d' % n)
        nd = _mk(c, ndiinTOP, 's%d_ndi' % n)
        _expr(nd.par.active, "bool({0}) and {1} == 'ndi'".format(P.format(S + 'active'), P.format(S + 'kind')))
        _expr(nd.par.name, P.format(S + 'name'))
        sy = _mk(c, syphonspoutinTOP, 's%d_syp' % n)
        _expr(sy.par.sendername, "{0} if {1} == 'syphon' else '__off__'".format(P.format(S + 'name'), P.format(S + 'kind')))
        mv = _mk(c, moviefileinTOP, 's%d_mov' % n)
        _expr(mv.par.file, P.format(S + 'file'))
        _expr(mv.par.play, "{} == 'movie'".format(P.format(S + 'kind')))
        sel = _mk(c, switchTOP, 's%d_sel' % n)
        for k, src in enumerate([blank, i, nd, sy, mv, test]):
            sel.inputConnectors[k].connect(src)
        _expr(sel.par.index, 'parent().par.{}kind.menuIndex'.format(S))
        fit = _mk(c, fitTOP, 's%d_fit' % n)
        fit.inputConnectors[0].connect(sel)
        _res_exprs(fit, S)
        _expr(fit.par.fit, "{{'fitbest': 'fitbest', 'fill': 'fitoutside', 'native': 'nativeres'}}[{}]".format(P.format(S + 'fit')))
        al = _glsl(c, 's%d_alpha' % n, ALPHA_SHADER, fit)
        al.par.vec0name = 'uMode'
        mode = "op('io_logic').module.alpha_mode({}, 'premult')".format(P.format(S + 'inalpha'))
        _expr(al.par.vec0valuex, mode)
        al.bypass = False                           # bypass is a flag (no expression); mode 4 = passthrough
        nl = _mk(c, nullTOP, 's%d_out' % n)
        nl.inputConnectors[0].connect(al)
        o = _mk(c, outTOP, 'out%d' % n)
        o.inputConnectors[0].connect(nl)
        inf = _mk(c, infoCHOP, 's%d_info' % n, viewer=False)
        inf.par.op = nd

    # Bus
    cb_ = _mk(c, textDAT, 'bus_ctl_callbacks')
    cb_.text = BUS_CB
    bus = _mk(c, scriptCHOP, 'bus_ctl')
    bus.par.callbacks = cb_
    bus.par.setuppars.pulse()
    ba = _mk(c, switchTOP, 'bus_a')
    bb = _mk(c, switchTOP, 'bus_b')
    for k in range(4):
        ba.inputConnectors[k].connect(c.op('s%d_out' % (k + 1)))
        bb.inputConnectors[k].connect(c.op('s%d_out' % (k + 1)))
    _expr(ba.par.index, 'parent().par.Busa.menuIndex')
    _expr(bb.par.index, 'parent().par.Busb.menuIndex')
    bx = _mk(c, crossTOP, 'bus_x')
    bx.inputConnectors[0].connect(ba)
    bx.inputConnectors[1].connect(bb)
    _expr(bx.par.cross, "op('bus_ctl')['mix']")
    bo = _mk(c, nullTOP, 'bus_out')
    bo.inputConnectors[0].connect(bx)
    o5 = _mk(c, outTOP, 'out5')
    o5.inputConnectors[0].connect(bo)
    pul = _mk(c, parameterexecuteDAT, 'io_pulses')
    pul.text = PULSES
    pul.par.op = c
    pul.par.pars = 'Cutnow Refreshsources'
    pul.par.custom, pul.par.builtin, pul.par.valuechange, pul.par.onpulse = True, False, False, True

    # Sinks
    for n in range(1, 5):
        O = 'O%d' % n
        pk = _mk(c, switchTOP, 'o%d_pick' % n)
        for k in range(4):
            pk.inputConnectors[k].connect(c.op('s%d_out' % (k + 1)))
        pk.inputConnectors[4].connect(bo)
        _expr(pk.par.index, 'parent().par.{}src.menuIndex'.format(O))
        fit = _mk(c, fitTOP, 'o%d_fit' % n)
        fit.inputConnectors[0].connect(pk)
        _res_exprs(fit, O)
        al = _glsl(c, 'o%d_alpha' % n, ALPHA_SHADER, fit)
        al.par.vec0name = 'uMode'
        _expr(al.par.vec0valuex, "op('io_logic').module.alpha_mode('premult', {})".format(P.format(O + 'outalpha')))
        _expr(al.par.format, "'rgba16float' if {} == 'fixed16' else 'rgba8fixed'".format(P.format(O + 'fmt')))
        sy = _mk(c, syphonspoutoutTOP, 'o%d_syp' % n)
        _expr(sy.par.active, "bool({0}) and {1} == 'syphon'".format(P.format(O + 'active'), P.format(O + 'kind')))
        _expr(sy.par.sendername, P.format(O + 'name'))
        sy.inputConnectors[0].connect(al)
        nd = _mk(c, ndioutTOP, 'o%d_ndi' % n)
        _expr(nd.par.active, "bool({0}) and {1} == 'ndi'".format(P.format(O + 'active'), P.format(O + 'kind')))
        _expr(nd.par.name, P.format(O + 'name'))
        _expr(nd.par.lowperformancebehavior, "'skipframes' if {} else 'stallmainthread'".format(P.format(O + 'skip')))
        _expr(nd.par.outputpixelformat, P.format(O + 'fmt'))
        _expr(nd.par.includealpha, "{} != 'none'".format(P.format(O + 'outalpha')))
        nd.inputConnectors[0].connect(al)
        inf = _mk(c, infoCHOP, 'o%d_info' % n, viewer=False)
        inf.par.op = nd

    # Status
    for nm in ('status', 'issues', 'routes'):
        _mk(c, tableDAT, nm)
    tick = _mk(c, executeDAT, 'status_tick')
    tick.text = STATUS_TICK
    tick.par.framestart = True
    tick.par.active = True
    stats = _mk(c, nullCHOP, 'stats')
    stats.inputConnectors[0].connect(bus)
    o6 = _mk(c, outCHOP, 'out6')
    o6.inputConnectors[0].connect(stats)
    o7 = _mk(c, outDAT, 'out7')
    o7.inputConnectors[0].connect(c.op('status'))

    _expr(c.par.opviewer, "me.op('out5')")
    c.viewer = True

    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=['Bus', 'Sources', 'Sinks'], d=48, cols=10)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'io_pulses', 'io_logic'],
         'body': 'zkit panel (pulse Opencontrols); io_logic = builders/io_logic.py.'},
        {'title': '1 Sources', 'role': 'input',
         'ops': ['blank', 'test_src', 'test_src_pixel'] + [x % n for n in range(1, 5) for x in
                 ('in%d', 's%d_ndi', 's%d_syp', 's%d_mov', 's%d_info')],
         'body': 'Per source: blank / in<n> / NDI In / Syphon In / movie / test. NDI In active only with S<n>active.'},
        {'title': '2 Normalise', 'role': 'process',
         'ops': [x % n for n in range(1, 5) for x in ('s%d_sel', 's%d_fit', 's%d_alpha', 's%d_alpha_pixel', 's%d_out', 'out%d')],
         'body': 'Switch by S<n>kind -> Fit (S<n>res) -> alpha to premultiplied (one GLSL pass) -> out1-4.'},
        {'title': '3 Bus', 'role': 'process',
         'ops': ['bus_ctl_callbacks', 'bus_ctl', 'bus_a', 'bus_b', 'bus_x', 'bus_out', 'out5'],
         'body': 'A/B Cross: Mix (manual) or Cutnow quantised to the next beat division (bpm).'},
        {'title': '4 Sinks', 'role': 'output',
         'ops': [x % n for n in range(1, 5) for x in ('o%d_pick', 'o%d_fit', 'o%d_alpha', 'o%d_alpha_pixel', 'o%d_syp',
                                                        'o%d_ndi', 'o%d_info')],
         'body': 'Pick (S1-4/bus) -> Fit -> alpha out + 8/16-bit -> Syphon Out / NDI Out. Senders OFF until O<n>active.'},
        {'title': '5 Status', 'role': 'note', 'ops': ['status_tick', 'status', 'issues', 'routes', 'stats', 'out6', 'out7'],
         'body': 'Every 30 frames: status (facts), issues (reports only), routes.'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    act = {o.name: bool(o.par.active.eval()) for o in c.children if o.OPType in ('ndioutTOP', 'syphonspoutoutTOP', 'ndiinTOP')}
    return {'comp': c.path, 'senders_active': [k for k, v in act.items() if v], 'panel': str(info)[:200],
            'layout': str(lay)[:300]}
