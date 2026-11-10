# fx_destroy builder - FX_destroy: picture in -> a short chain of destruction module slots -> Panic -> out1.
# The SAME lean rack as builders/fx_glitch.py (template: docs/builds/fx_glitch.md), copied, not abstracted: a slot is
# the module COMP + a Cross TOP (<name>_mix) + a Switch TOP (<name>_slot: 0 bypass / 1 module / 2 mix); the `slots`
# table (name module enabled order mix) is the only rack state; add / remove / reorder = this builder re-wiring.
# Module 'X' lives in builders/fx_destroy_X.py (melt, burn, shatter). Doc: docs/builds/fx_destroy.md.
# Shared here (used by 2+ modules today, no-bloat rule): extra par styles, the Mask page + GLSL (melt, burn), the
# Point page (Effector Null / Point uv: melt, burn, shatter), a pulse -> time par Parameter Execute (all three), the
# uint hash / value noise GLSL (all three), a compute GLSL helper (all three).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_destroy.py').read(), ns)
#   ns['build']('/project1/lab')                         # rack + melt1 / burn1 / shatter1 rows on first build
#   ns['add']('/project1/lab/FX_destroy', 'melt')         # melt2, wired last
#   ns['remove']('/project1/lab/FX_destroy', 'melt2'); ns['rewire'](c) after editing order in `slots`
# Idempotent; T-70 safe (_sd = safe_destroy, instance windows closed before a remove; pane never moved). ASCII only.
import os

NAME = 'FX_destroy'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
TEST_CLIP = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'
COLS = ['name', 'module', 'enabled', 'order', 'mix']
DEFAULT_ROWS = [['melt1', 'melt', 1, 1, 1], ['burn1', 'burn', 1, 2, 1], ['shatter1', 'shatter', 1, 3, 1]]


def plan_chain(rows):
    """rows: [{name, order, ...}] -> names in chain order (order, then table position). Pure; tested offline."""
    idx = [(float(r.get('order') or 0), i, r['name']) for i, r in enumerate(rows)]
    return [n for _o, _i, n in sorted(idx)]


def chain_edges(names, src='img_src'):
    """Desired (dst, connector, src) wires for the chain names, then panic + out1. Pure; tested offline."""
    e, prev = [], src
    for n in names:
        e += [(n, 0, prev), (n + '_mix', 0, prev), (n + '_mix', 1, n),
              (n + '_slot', 0, prev), (n + '_slot', 1, n), (n + '_slot', 2, n + '_mix')]
        prev = n + '_slot'
    return e + [('panic', 0, prev), ('panic', 1, src), ('out1', 0, 'panic')]


def next_name(module, taken):
    k = 1
    while '%s%d' % (module, k) in taken:
        k += 1
    return '%s%d' % (module, k)


# ------------------------------------------------------------------ shared module pieces (pure strings / specs)
MASK_SOURCES = ['none', 'luma', 'dark', 'top', 'radial']
MASK_PAGE = ('Mask', [
    ('Masksource', 'Menu', 'none', {'names': MASK_SOURCES, 'labels': ['None (everywhere)', 'Bright areas', 'Dark areas',
                                                                      'Mask TOP (r)', 'Radial (Point)']}),
    ('Masktop', 'TOP', '', {'label': 'Mask TOP'}),
    ('Masklevel', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Level / radius'}),
    ('Masksoft', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Softness'}),
    ('Maskinvert', 'Toggle', False, {'label': 'Invert'}),
])
POINT_PAGE = ('Point', [
    ('Effector', 'COMP', '', {'label': 'Effector Null (tx ty)'}),
    ('Pointu', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Point u'}),
    ('Pointv', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Point v'}),
])
STATE_PAGE = ('State', [
    ('Resettime', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Last reset (absTime s)'}),
    ('Hittime', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Last trigger (absTime s)'}),
])
PULSE_TARGET = {'Reset': 'Resettime', 'Trigger': 'Hittime'}
# State stamps are absTime s of the TD that wrote them; after a TD relaunch or a tox move they can lie in this TD's
# future and block every hit / force rest (T-155). The uniforms void a stamp later than now + 0.05 s (-1) BEFORE any
# use (also before the Auto max, else a stale Hittime hides the Auto ticks). Shared by every module with a State page.
STAMP_SLACK = 0.05


def stamp_expr(name):
    """Uniform expression: State par `name` (absTime s), or -1 when it lies in this TD's future (another clock)."""
    return ("(lambda t, n: t if t <= n + %g else -1.0)(parent().par.%s.eval(), absTime.seconds)"
            % (STAMP_SLACK, name))


def hit_expr():
    """Uniform expression: the latest hit stamp = max(Hittime voided as in stamp_expr, the last Auto tick)."""
    return ("(lambda t, n, a: max(t if t <= n + %g else -1.0, (math.floor(n / a) * a) if a > 0 else -1.0))"
            "(parent().par.Hittime.eval(), absTime.seconds, parent().par.Auto.eval())" % STAMP_SLACK)

# GLSL shared by the modules: lowbias32 hash (T-108: matches numpy uint32), value noise, fbm, luma.
GLSL_LIB = """
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hsh(ivec2 c, uint s) { return float(lb32(uint(c.x) * 1597334677u ^ lb32(uint(c.y) ^ (s * 2654435761u)))) * (1.0 / 4294967296.0); }
float hsh3(ivec3 c, uint s) { return hsh(c.xy, s ^ lb32(uint(c.z) + 0x9e3779b9u)); }
float vnoise(vec2 x, uint s) {
    ivec2 i = ivec2(floor(x)); vec2 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    float a = hsh(i, s), b = hsh(i + ivec2(1, 0), s), c = hsh(i + ivec2(0, 1), s), d = hsh(i + ivec2(1, 1), s);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float fbm(vec2 x, uint s, int oct) {
    float v = 0.0, a = 0.5, n = 0.0;
    for (int k = 0; k < 6; k++) { if (k >= oct) break; v += a * vnoise(x, s + uint(k) * 101u); n += a; x = x * 2.03 + 17.1; a *= 0.5; }
    return v / n;
}
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
"""


def mask_glsl(mask_in):
    """fxMask(uv, colour): uM = source invert level soft, uMc = point u v aspect -. Mask TOP = sTD2DInputs[mask_in]."""
    return """
uniform vec4 uM;
uniform vec4 uMc;
float fxMask(vec2 uv, vec3 col) {
    int s = int(uM.x + 0.5);
    float m = 1.0;
    if (s == 1) m = smoothstep(uM.z - uM.w, uM.z + uM.w + 1e-4, luma(col));
    else if (s == 2) m = 1.0 - smoothstep(uM.z - uM.w, uM.z + uM.w + 1e-4, luma(col));
    else if (s == 3) m = texture(sTD2DInputs[%d], uv).r;
    else if (s == 4) m = 1.0 - smoothstep(uM.z - uM.w, uM.z + uM.w + 1e-4, length((uv - uMc.xy) * vec2(uMc.z, 1.0)));
    return (uM.y > 0.5 && s > 0) ? 1.0 - m : m;
}
""" % mask_in


def pt_expr(axis, k=''):
    """Expression for the Point (uv): Effector<k> Null's tx/ty + 0.5 (the frame spans -0.5..0.5), else Point u/v."""
    t, uv = ('tx', 'Pointu') if axis == 'u' else ('ty', 'Pointv')
    return ("(lambda o: (o.par.%s.eval() + 0.5) if o is not None and hasattr(o.par, '%s') else parent().par.%s.eval())"
            "(parent().par.Effector%s.eval())" % (t, t, uv, k))


PULSE_EXEC = """# Pulse pars -> a time stamp par (absTime.seconds) the shaders compare with their state (no per-frame Python).
TARGET = %r

def onPulse(par):
    t = TARGET.get(par.name)
    if t is not None:
        getattr(par.owner.par, t).val = absTime.seconds
    return
"""


# ------------------------------------------------------------------ TD side
def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


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


def _compute(m, name, text, inputs, w_expr, h_expr, fmt='useinput', uniforms=(), readwrite=False, bufs=1,
             extend=None):
    """A compute GLSL TOP (T-47) with its shader in a docked Text DAT; uniforms = [(name, [4 exprs])]."""
    g = _mk(m, glslTOP, name)
    d = m.op(name + '_compute')
    if d is None:
        d = _mk(m, textDAT, name + '_compute')
        d.dock = g
    if d.text != text:
        d.text = text
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    for par, e in ((g.par.resolutionw, w_expr), (g.par.resolutionh, h_expr)):
        if isinstance(e, str):
            _expr(par, e)
        else:
            par.mode = ParMode.CONSTANT
            par.val = e
    g.par.format = fmt
    if readwrite:
        g.par.outputaccess = 'readwrite'
        g.par.clearoutputs = False
    if bufs > 1:
        g.par.numcolorbufs = bufs
    if extend:
        g.par.inputextenduv = extend
    for k, src in enumerate(inputs):
        cn = g.inputConnectors[k].connections
        if not cn or cn[0].owner != src:
            g.inputConnectors[k].connect(src)
    g.seq.vec.numBlocks = max(len(uniforms), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(uniforms):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)
    return g


P = "parent().par.{}.eval()"
MASK_UNIFORMS = [('uM', ['parent().par.Masksource.menuIndex', 'float(%s)' % P.format('Maskinvert'),
                         P.format('Masklevel'), P.format('Masksoft')]),
                 ('uMc', [pt_expr('u'), pt_expr('v'), 'me.inputs[0].width / max(1, me.inputs[0].height)', '0'])]


def _mask_ops(m):
    """mask_none (1x1 white) + mask_src (Select: the Mask TOP only while Masksource = top, so nothing else pulls it)."""
    mn = _mk(m, constantTOP, 'mask_none')
    mn.par.outputresolution = 'custom'
    mn.par.resolutionw, mn.par.resolutionh = 1, 1
    mn.par.colorr = mn.par.colorg = mn.par.colorb = mn.par.alpha = 1
    mn.comment = '1x1 white: the mask (and the idle state input) when nothing else is selected.'
    ms = _mk(m, selectTOP, 'mask_src')
    _expr(ms.par.top, "parent().par.Masktop.eval().path if parent().par.Masksource.eval() == 'top' and "
                      "parent().par.Masktop.eval() is not None else me.parent().op('mask_none').path")
    ms.comment = 'Mask source: the Mask TOP while Masksource = top, else mask_none.'
    return mn, ms


def _pulse_exec(m, names):
    pe = _mk(m, parameterexecuteDAT, 'pulse_exec')
    txt = PULSE_EXEC % dict((n, PULSE_TARGET[n]) for n in names)
    if pe.text != txt:
        pe.text = txt
        pe.par.active = False                              # T-97: toggle after a text rewrite
    pe.par.op = '..'
    pe.par.pars = ' '.join(names)
    pe.par.valuechange = False
    pe.par.onpulse = True
    pe.par.active = True
    pe.comment = 'Pulses %s -> time stamp pars on the State page (read by the shaders).' % ' '.join(names)
    return pe


H = {'mk': _mk, 'expr': _expr, 'sd': _sd, 'compute': _compute, 'mask_ops': _mask_ops, 'pulse_exec': _pulse_exec,
     'P': P, 'MASK_UNIFORMS': MASK_UNIFORMS, 'pt_expr': pt_expr, 'mask_glsl': mask_glsl, 'GLSL_LIB': GLSL_LIB,
     'stamp': stamp_expr, 'hit': hit_expr}


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None or getattr(c.par, name + 'r', None) is not None:
                continue
            label = o.get('label', name)
            p = None
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
            elif style == 'RGB':
                for q, v in zip(page.appendRGB(name, label=label), default):
                    q.default = v
                    q.val = v
            elif style in ('TOP', 'COMP', 'CHOP'):
                p = getattr(page, 'append' + style)(name, label=label)[0]
            if p is not None:
                p.default = default
                p.val = default


def _module(module):
    ns = dict(globals())
    exec(open(os.path.join(HERE, 'fx_destroy_%s.py' % module)).read(), ns)
    return ns


def _rows(c):
    t = c.op('slots')
    return [dict((k, t[i, k].val) for k in COLS) for i in range(1, t.numRows)]


def _cell(name, col):
    return "op('slots')['%s', '%s'].val" % (name, col)


def _slot_ops(c, name):
    """The rack's two ops around instance `name` (module COMP itself is made by _instance)."""
    mx = _mk(c, crossTOP, name + '_mix')
    _expr(mx.par.cross, 'float(%s or 0)' % _cell(name, 'mix'))
    mx.comment = 'Slot %s: dry/wet (slots.mix); only cooks when 0 < mix < 1.' % name
    sw = _mk(c, switchTOP, name + '_slot')
    _expr(sw.par.index, "0 if not int({e} or 0) or float({m} or 0) <= 0 else (1 if float({m}) >= 1 else 2)"
          .format(e=_cell(name, 'enabled'), m=_cell(name, 'mix')))
    sw.comment = 'Slot %s: 0 bypass (exact, module not cooked) / 1 module / 2 mix.' % name


# slot_gate (T-198 / T-201; same block as builders/fx_glitch.py, this rack is a copy): a Switch TOP in each module COMP right before out1: 0 = in1 (exact passthrough,
# nothing upstream in the module cooks) when the rack slot is off (slots enabled 0 or mix <= 0, the same test as the
# rack's <name>_slot Switch), 1 = the module's own output (unchanged when the slot is on). The rack's <name>_mix Cross
# TOP keeps its viewer on (user rule) and a visible viewer pulls the module even while <name>_slot bypasses it, so
# with the network pane on the rack every disabled module cooked (docs/builds/RENDER_COST.md). No slots row = on.
# A module whose out1 already comes from a slot-aware out_sel (GEN_points OUT_SEL_E) is left alone.
_SLOT_CELL = "parent(2).op('slots')[parent().name, '%s']"
SLOT_OFF_E = ("(parent(2).op('slots') is not None and (not int(float(getattr(" + _SLOT_CELL % 'enabled' +
              ", 'val', '1') or 0)) or float(getattr(" + _SLOT_CELL % 'mix' + ", 'val', '1') or 0) <= 0))")
SLOT_GATE_E = '0 if ' + SLOT_OFF_E + ' else 1'


def slot_off(enabled, mix):
    """The gate / <name>_slot test on two slots cells (strings; None = no row = on). Pure; tested offline."""
    en = '1' if enabled is None else enabled
    mx = '1' if mix is None else mix
    return not int(float(en or 0)) or float(mx or 0) <= 0


def gate_needed(src_name, src_index_expr):
    """False when out1's source is already slot-aware (an out_sel whose index reads the slots table). Pure."""
    return not (src_name == 'out_sel' and "op('slots')" in (src_index_expr or ''))


def _slot_gate(m, stages):
    """Insert / refresh `slot_gate` (in1 / module out) before out1 in module COMP m; idempotent (a module rebuild that
    re-wires out1 to its own source is re-gated). Adds it to the stage holding out1. Returns stages."""
    out1, in1 = m.op('out1'), m.op('in1')
    if out1 is None or in1 is None or not out1.inputConnectors or not out1.inputConnectors[0].connections:
        return stages
    conn = out1.inputConnectors[0].connections[0]       # an output connector (a COMP source needs it, T-111 (2))
    src = conn.owner
    g = m.op('slot_gate')
    if src is not g:
        if not gate_needed(src.name, getattr(getattr(src.par, 'index', None), 'expr', '')) or src is in1:
            _sd(g)                                        # stale gate from an older layout
            return stages
        g = _mk(m, switchTOP, 'slot_gate')
        g.inputConnectors[0].connect(in1)
        g.inputConnectors[1].connect(conn)
        out1.inputConnectors[0].connect(g)
    elif not g.inputConnectors[0].connections or g.inputConnectors[0].connections[0].owner is not in1:
        g.inputConnectors[0].connect(in1)
    _expr(g.par.index, SLOT_GATE_E)
    g.comment = ('Slot off (slots enabled 0 / mix 0) = in1 untouched, nothing in this module cooks, also when a '
                 'viewer shows the rack (RENDER_COST.md, T-198); slot on = the module output.')
    return gate_stages(stages)


def gate_stages(stages):
    """Put 'slot_gate' just before 'out1' in the stage that lists out1 (else the last stage). Pure; tested offline."""
    if not stages or any('slot_gate' in s_['ops'] for s_ in stages):
        return stages
    s_ = next((s_ for s_ in stages if 'out1' in s_['ops']), stages[-1])
    s_['ops'] = [n for n in s_['ops'] if n != 'out1'] + ['slot_gate'] + (['out1'] if 'out1' in s_['ops'] else [])
    return stages

def gate_upgrade(comp_path, name):
    """Gate-only upgrade of an EXISTING instance (main, T-152: one rack per exec): adds / refreshes `slot_gate` and
    re-applies the module's stored stage plan with it, without rebuilding the module (shaders, pars, presets stay).
    Returns the gate index (0 = slot off) or why it was skipped."""
    c = op(comp_path)
    m = c.op(name) if c is not None else None
    if m is None or not m.isCOMP:
        return {'name': name, 'error': 'no instance'}
    hm = op('/jazib_mcp/handlers').module
    plan = hm._stage_plan(m) or {}
    stages = [dict(s_, ops=[n for n in (s_.get('ops') or []) if m.op(n) is not None]) for s_ in plan.get('stages', [])]
    had = m.op('slot_gate') is not None
    stages = [s_ for s_ in _slot_gate(m, stages) if s_['ops']]
    g = m.op('slot_gate')
    if g is not None and not had and stages:
        hm.layout_stages(m, stages, plan.get('colors', True), arrange=plan.get('arrange') or 'mixed')
    return {'name': name, 'gated': g is not None, 'new': g is not None and not had,
            'index': int(g.par.index.eval()) if g is not None else None}



def _instance(c, name, module, panel=True):
    M = _module(module)
    m = c.op(name)
    if m is None or not m.isCOMP:
        m = _mk(c, baseCOMP, name)
    _pars(m, M['PAGES'])
    m.comment = 'FX_destroy module %s (%s). Pars on its custom pages; pulse Opencontrols for the zkit panel.' % (
        name, module)
    stages = _slot_gate(m, M['build'](m, H))
    m.par.opviewer.expr = "me.op('out1')"
    m.par.opviewer.mode = ParMode.EXPRESSION
    m.viewer = True
    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](m.path, pages=M['PANEL_PAGES'], d=56, cols=6)
        pt = m.op('controls/zk_presets')
        if pt is not None and pt.numRows <= 1:              # seed the module presets once (user's own kept)
            L = m.op('controls/zk_logic').module
            for slot, pname, vals in M['PRESETS']:
                pt.appendRow([slot, pname, L.DEFAULT_COLOR, L.preset_dump(vals)])
        stages = [{'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window']}] + stages
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if m.op(n) is not None]
    op('/jazib_mcp/handlers').module.layout_stages(m, [s_ for s_ in stages if s_['ops']], True, arrange='mixed')
    _slot_ops(c, name)
    return {'instance': m.path, 'panel': bool(info)}


def rewire(c):
    """Make the chain match `slots`; touches only connectors that differ. Returns the number of wires changed."""
    names = [n for n in plan_chain(_rows(c)) if c.op(n) is not None]
    changed = 0
    for dst, i, src in chain_edges(names):
        d, s = c.op(dst), c.op(src)
        conns = d.inputConnectors[i].connections
        if conns and conns[0].owner == s:
            continue
        d.inputConnectors[i].connect(s.outputConnectors[0])   # a COMP source needs its connector, not the op
        changed += 1
    return changed


def _layout(c):
    names = plan_chain(_rows(c))
    chain = []
    for n in names:
        chain += [n, n + '_mix', n + '_slot']
    stages = [
        {'title': 'Rack', 'role': 'control', 'ops': ['slots'],
         'body': 'slots: name module enabled order mix. enabled/mix live; add/remove/order = builder rewire.'},
        {'title': '1 Input', 'role': 'input', 'ops': ['in1', 'test_clip', 'img_src'],
         'body': 'in1 TOP or the stored webcam clip (Input: auto = in1 when wired).'},
        {'title': '2 Slots', 'role': 'process', 'ops': [n for n in chain if c.op(n) is not None],
         'body': 'Per slot: module COMP -> _mix (Cross) -> _slot (Switch 0 bypass / 1 module / 2 mix).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['panic', 'out1'], 'body': 'Panic = instant passthrough of the rack.'},
    ]
    stages = [s for s in stages if s['ops']]
    return op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')


def build(parent_path='/project1/lab', panel=True, rows=None):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('FX_destroy: destruction rack (melt, burn, shatter). In: in1 TOP. Out: out1 TOP. Module slots from '
                 '`slots` (builders/fx_destroy.py add/remove/rewire). Panic = instant passthrough.')
    _pars(c, [('Rack', [
        ('Panic', 'Toggle', False, {'label': 'Panic (passthrough)'}),
        ('Input', 'Menu', 'auto', {'names': ['auto', 'live', 'test'], 'labels': ['Auto', 'Live (in1)', 'Test clip']}),
    ])])
    in1 = _mk(c, inTOP, 'in1')
    tc = _mk(c, moviefileinTOP, 'test_clip')
    tc.par.file = TEST_CLIP
    tc.par.outputresolution = 'custom'
    tc.par.resolutionw, tc.par.resolutionh = 1080, 1920
    tc.par.outputaspect = 'resolution'
    tc.par.fillmode = 'fill'
    tc.comment = 'Test picture: stored 5 s webcam clip, filled to 1080x1920 (cooks only while selected).'
    img = _mk(c, switchTOP, 'img_src')
    img.inputConnectors[0].connect(tc)
    img.inputConnectors[1].connect(in1)
    _expr(img.par.index, "(1 if parent().par.Input.eval() == 'live' or (parent().par.Input.eval() == 'auto' and any("
          "len(cn.connections) for cn in parent().inputConnectors if cn.inOP is not None and cn.inOP.name == 'in1')) else 0)")
    pn = _mk(c, switchTOP, 'panic')
    _expr(pn.par.index, '1 if parent().par.Panic.eval() else 0')
    pn.comment = 'Panic: 1 = img_src straight to out1 (same frame; slots stop cooking).'
    _mk(c, outTOP, 'out1')
    t = c.op('slots')
    if t is None:
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        for r in (rows or DEFAULT_ROWS):
            t.appendRow(r)
    t.comment = 'Rack state: one row per module instance. enabled 0/1, mix 0..1 act live; order -> rewire.'
    out = []
    for r in _rows(c):
        out.append(_instance(c, r['name'], r['module'], panel=panel and c.op(r['name']) is None))
    wires = rewire(c)
    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    lay = _layout(c)
    return {'comp': c.path, 'instances': out, 'wires_changed': wires, 'layout': str(lay)[:300]}


def add(comp_path, module, name=None, order=None, enabled=1, mix=1, panel=True):
    c = op(comp_path)
    rows = _rows(c)
    name = name or next_name(module, set(r['name'] for r in rows) | set(o.name for o in c.children))
    if order is None:
        order = int(max([float(r['order'] or 0) for r in rows] + [0])) + 1
    c.op('slots').appendRow([name, module, enabled, order, mix])
    info = _instance(c, name, module, panel=panel)
    wires = rewire(c)
    _layout(c)
    return {'added': name, 'instance': info, 'wires_changed': wires}


def remove(comp_path, name):
    c = op(comp_path)
    t = c.op('slots')
    if t.row(name) is not None:
        t.deleteRow(name)
    wires = rewire(c)                                     # re-route around it first, then remove its ops
    m = c.op(name)
    if m is not None:
        w = m.op('controls_window')
        if w is not None and w.isOpen:
            w.par.winclose.pulse()
    for n in (name + '_slot', name + '_mix', name):
        _sd(c.op(n))
    _layout(c)
    return {'removed': name, 'wires_changed': wires}
