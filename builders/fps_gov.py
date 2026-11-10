# fps_gov builder - FG_fps_governor: a generic "hold 60 fps" controller any COMP can follow (docs/builds/fps_governor.md).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fps_gov.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts re-set, par values kept, zkit panel refreshed in place (T-70 safe: its window
# is closed first). It NEVER writes another COMP's pars: consumers read out1['quality'] (manual control wins).
# Cost: Active off = 0 cooks (the Execute DAT is off, nobody pulls perform1). No functions in op storage. ASCII only.
import os

NAME = 'FG_fps_governor'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'fps_gov_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')

PAGES = [
    ('Governor', [
        ('Active', 'Toggle', False, {'label': 'Active'}),
        ('Target', 'Float', 60.0, {'min': 24, 'max': 240, 'label': 'Target fps'}),
        ('Downafter', 'Int', 30, {'min': 1, 'max': 600, 'label': 'Down after frames'}),
        ('Upafter', 'Int', 300, {'min': 1, 'max': 3600, 'label': 'Up after frames'}),
        ('Steps', 'Int', 5, {'min': 0, 'max': 16, 'label': 'Steps'}),
        ('Floor', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Floor quality'}),
        ('Upmargin', 'Float', 3.0, {'min': 0, 'max': 16, 'label': 'Up headroom ms'}),
        ('Reset', 'Pulse', None, {'label': 'Reset'}),
    ]),
]
PANEL_PAGES = ['Governor']
WATCHED = ' '.join(n for n, _, _, _ in PAGES[0][1])

FRAME_CB = """# fg_frame: one governor tick per frame while Active (this DAT's Active follows the COMP's).
# interval = real time between frame starts (perf_counter); busy = perform1 msec every BUSY_EVERY frames.
# Op refs cached in the state (module memory, not storage); a rebuild / Reset / Active change starts a fresh state.
import time

def onFrameStart(frame):
\tt0 = time.perf_counter()
\tc = parent()
\tL = op('fg_logic').module
\tst = L.STATES.get(c.path)
\tif st is None or 'ops' not in st:
\t\tst = L.state_for(c.path)
\t\tst['ops'] = (op('perform1'), op('fg_pexec').module)
\t\tst['cfg'] = st['ops'][1].refresh(c)
\tperf, pe = st['ops']
\tlast = st.get('t_last')
\tst['t_last'] = t0
\tif last is None:
\t\treturn
\tcf = st['cfg']
\tbusy = perf['msec'][0] if st['frames'] % L.BUSY_EVERY == 0 else None
\tr = L.tick(st, (t0 - last) * 1000.0, busy, cf)
\tif r or st['frames'] % L.SHOW_EVERY == 0:
\t\tpe.write(c, L.outputs(st, cf))
\tdt = (time.perf_counter() - t0) * 1000.0
\tst['cost_ms'] = dt if st.get('cost_ms') is None else st['cost_ms'] + 0.02 * (dt - st['cost_ms'])
\treturn
"""

PEXEC = """# fg_pexec: governor pars -> config / reset (one event per pulse, T-238). write() sets vals only on change.
CH = ('quality', 'step', 'fps', 'headroom_ms')

def refresh(c):
\tL = op('fg_logic').module
\tst = L.state_for(c.path)
\tst['cfg'] = L.cfg(c.par.Target.eval(), c.par.Downafter.eval(), c.par.Upafter.eval(), c.par.Steps.eval(),
\t\t\t\t\t  c.par.Floor.eval(), c.par.Upmargin.eval())
\treturn st['cfg']

def write(c, o):
\tv = op('vals').par
\tfor i, n in enumerate(CH):
\t\tp = getattr(v, 'value%d' % i)
\t\tif p.eval() != o[n]:
\t\t\tp.val = o[n]

def reset(c):
\tL = op('fg_logic').module
\tL.STATES[c.path] = L.new_state()
\tcf = refresh(c)
\twrite(c, {'quality': 1.0, 'step': 0.0, 'fps': 0.0, 'headroom_ms': 0.0})
\treturn cf

def onPulse(par):
\tif par.name == 'Reset':
\t\treset(par.owner)
\treturn

def onValueChange(par, prev):
\tc = par.owner
\tif par.name == 'Active':
\t\treset(c)
\t\treturn
\tL = op('fg_logic').module
\tst = L.state_for(c.path)
\tcf = refresh(c)
\tif st['step'] > cf['steps']:
\t\tst['step'] = cf['steps']
\to = L.outputs(st, cf)
\tif not c.par.Active.eval():
\t\to = {'quality': 1.0, 'step': 0.0, 'fps': 0.0, 'headroom_ms': 0.0}
\twrite(c, o)
\treturn
"""


def _pars(c):
    for page_name, pars in PAGES:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            p = getattr(page, 'append' + style)(name, label=label)[0]
            if 'min' in o:
                p.normMin, p.normMax = o['min'], o['max']
                if style == 'Int':
                    p.clampMin, p.min = True, o['min']
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


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = True
    return o


def build(parent_path='/project1/lab', panel=True):
    pp = op(parent_path)
    c = pp.op(NAME) or pp.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('FG_fps_governor: hold Target fps. Active off by default (manual wins). Measures Perform CHOP frame '
                 'interval + cook ms (smoothed), steps quality 1.0 -> Floor in Steps with Downafter / Upafter '
                 'hysteresis. out1 CHOP: quality step fps headroom_ms. Never writes other COMPs: they read '
                 "op('%s/out1')['quality']. docs/builds/fps_governor.md" % c.path)
    _close_window(c)
    _pars(c)

    logic = _mk(c, textDAT, 'fg_logic')
    t = open(LOGIC_FILE).read()
    if logic.text != t:
        logic.text = t
    logic.comment = 'Pure step / hysteresis logic (copy of builders/fps_gov_logic.py; tests test/test_fps_gov.py).'

    perf = _mk(c, performCHOP, 'perform1')
    for n in ('fps', 'cpumsec', 'cook', 'droppedframes', 'timeslicestep', 'timeslicemsec'):
        setattr(perf.par, n, False)
    perf.par.msec = True                 # this frame's cook ms (headroom)
    perf.comment = 'msec = frame cook ms (headroom). Cooks only when fg_frame reads it (every BUSY_EVERY frames).'

    vals = _mk(c, constantCHOP, 'vals')
    for i, n in enumerate(('quality', 'step', 'fps', 'headroom_ms')):
        getattr(vals.par, 'name%d' % i).val = n
    if not c.par.Active.eval():
        vals.par.value0, vals.par.value1, vals.par.value2, vals.par.value3 = 1.0, 0.0, 0.0, 0.0
    vals.comment = 'Written by fg_frame / fg_pexec only on change (fps / headroom every SHOW_EVERY frames).'
    out1 = _mk(c, outCHOP, 'out1')
    out1.inputConnectors[0].connect(vals)

    pe = _mk(c, parameterexecuteDAT, 'fg_pexec')
    if pe.text != PEXEC:
        pe.text = PEXEC
    pe.par.op = c
    pe.par.pars = WATCHED
    pe.par.custom, pe.par.builtin, pe.par.valuechange, pe.par.onpulse = True, False, True, True

    fr = _mk(c, executeDAT, 'fg_frame')
    if fr.text != FRAME_CB:
        fr.text = FRAME_CB
    for n in ('start', 'create', 'framestart', 'frameend', 'playstatechange', 'devicechange', 'projectpresave',
              'projectpostsave'):
        if hasattr(fr.par, n):
            setattr(fr.par, n, n == 'framestart')
    fr.par.active.expr = 'parent().par.Active.eval()'
    fr.par.active.mode = ParMode.EXPRESSION

    pe.module.reset(c)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=56, cols=8)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'fg_pexec'],
         'body': 'zkit panel (Main = the 8 Governor pars). fg_pexec: par change -> config, Active / Reset -> fresh state.'},
        {'title': '1 Measure + step', 'role': 'process', 'ops': ['perform1', 'fg_logic', 'fg_frame'],
         'body': 'While Active: each frame start reads perform1 (frame interval + cook ms), EMA, Downafter / Upafter '
                 'hysteresis -> step 0..Steps. Off = 0 cooks.'},
        {'title': '2 Output', 'role': 'output', 'ops': ['vals', 'out1'],
         'body': "out1: quality (1.0 .. Floor), step, fps, headroom_ms. Consumers bind op('.../out1')['quality']."},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, [s_ for s_ in stages if s_['ops']], True, arrange='mixed')
    return {'comp': c.path, 'panel': str(info)[:200], 'layout': str(lay)[:300]}
