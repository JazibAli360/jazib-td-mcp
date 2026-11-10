# fx_glitch builder - FX_glitch: picture in -> a short chain of module slots -> Panic -> out1.
# Lean on purpose (user rule 26 Oct: "dont bloat stuff just for modularity"): a slot is the module COMP plus a Cross
# TOP (<name>_mix) and a Switch TOP (<name>_slot: 0 bypass / 1 module / 2 mix); the `slots` table (name module enabled
# order mix) is the only rack state; add / remove / reorder = this builder re-wiring the chain. No codegen, no registry:
# module 'X' lives in builders/fx_glitch_X.py (template: docs/builds/fx_glitch.md).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_glitch.py').read(), ns)
#   ns['build']('/project1/lab')                        # rack + one 'smear1' slot on first build
#   ns['add']('/project1/lab/FX_glitch', 'smear')        # another instance (smear2), wired last
#   ns['remove']('/project1/lab/FX_glitch', 'smear2'); ns['rewire'](c) after editing order in `slots`
# enabled / mix edits in `slots` act live (expressions), no rewire. Idempotent; T-70 safe (_sd = safe_destroy,
# instance windows closed before a remove; pane never moved). No functions in op storage (T-67). ASCII only.
import os

NAME = 'FX_glitch'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
TEST_CLIP = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'
COLS = ['name', 'module', 'enabled', 'order', 'mix']


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


def _compute(m, name, text, ins, res=None, fmt='useinput'):
    """Compute-mode GLSL TOP `name` + docked `<name>_compute` DAT; res None = input 0's size. Inputs wired in order."""
    g = _mk(m, glslTOP, name)
    d = m.op(name + '_compute')
    if d is None:
        d = _mk(m, textDAT, name + '_compute')
        d.dock = g
    d.text = text
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    if res:
        g.par.resolutionw, g.par.resolutionh = res
    else:
        _expr(g.par.resolutionw, 'me.inputs[0].width')
        _expr(g.par.resolutionh, 'me.inputs[0].height')
    g.par.format = fmt
    for i, src in enumerate(ins):
        g.inputConnectors[i].connect(src)
    return g


def _uniforms(g, U):
    """U = [(name, [x, y, z, w expressions])] -> vec0..vecN uniforms, all expressions."""
    g.seq.vec.numBlocks = max(len(U), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)


# module helpers (block, dct, bits, mosaic use compute + uniforms; smear predates them)
H = {'mk': _mk, 'expr': _expr, 'sd': _sd, 'compute': _compute, 'uniforms': _uniforms}


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            ex = getattr(c.par, name, None)
            if ex is not None:
                if style == 'Menu' and list(ex.menuNames) != list(o['names']):   # T-175: new entries reach old COMPs
                    v = ex.eval()
                    ex.menuNames, ex.menuLabels = o['names'], o['labels']
                    if v in o['names']:
                        ex.val = v
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
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
            elif style == 'Pulse':                            # triggers (mosh Refresh, moshcut Go); no value
                page.appendPulse(name, label=label)
                continue
            elif style in ('TOP', 'CHOP'):                      # optional op references (mask, audio)
                p = getattr(page, 'append' + style)(name, label=label)[0]
            p.default = default
            p.val = default


def _module(module):
    ns = dict(globals())
    exec(open(os.path.join(HERE, 'fx_glitch_%s.py' % module)).read(), ns)
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


# slot_gate (T-198 for every rack): a Switch TOP in each module COMP right before out1: 0 = in1 (exact passthrough,
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
        hm.layout_stages(m, stages, plan.get('colors', True), arrange=plan.get('arrange') or module_arrange(m))
    return {'name': name, 'gated': g is not None, 'new': g is not None and not had,
            'index': int(g.par.index.eval()) if g is not None else None}



def _instance(c, name, module, panel=True):
    M = _module(module)
    m = c.op(name)
    if m is None or not m.isCOMP:
        m = _mk(c, baseCOMP, name)
    _pars(m, M['PAGES'])
    m.comment = 'FX_glitch module %s (%s). Pars on its custom page; pulse Opencontrols for the zkit panel.' % (name, module)
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
    op('/jazib_mcp/handlers').module.layout_stages(m, [s_ for s_ in stages if s_['ops']], True,
                                                   arrange=module_arrange(m))
    _slot_ops(c, name)
    return {'instance': m.path, 'panel': bool(info)}


def module_arrange(m):
    """Stage arrange for a module COMP: 'rows' when it holds a Feedback TOP loop ('mixed' pulls the out stage under the
    loop stage there: box overlaps, intruders), else 'mixed' (T-163)."""
    kids = getattr(m, 'children', None) or []
    return 'rows' if any(getattr(o, 'OPType', '') == 'feedbackTOP' for o in kids) else 'mixed'


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


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('FX_glitch: digital breakage rack. In: in1 TOP. Out: out1 TOP. Module slots from `slots` '
                 '(builders/fx_glitch.py add/remove/rewire). Panic = instant passthrough.')
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
        t.appendRow(['smear1', 'smear', 1, 1, 1])
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


def preset_plan(rows, presets):
    """rows = [(slot, name)] in zk_presets; presets = module PRESETS. -> (replace {slot: (name, vals)}, append
    [(slot, name, vals)], skipped [slot]): a module preset replaces the row in its slot when that row has the same
    name (a module-seeded row, possibly an older partial-state version); a free slot gets it; a slot holding a
    differently named row is the user's own and is kept. Pure; tested offline."""
    have = dict((int(float(s)), n) for s, n in rows)
    rep, app, skip = {}, [], []
    for slot, pname, vals in presets:
        if slot not in have:
            app.append((slot, pname, vals))
        elif have[slot] == pname:
            rep[slot] = (pname, vals)
        else:
            skip.append(slot)
    return rep, app, skip


def upgrade(comp_path, name, panel=True):
    """Rebuild an EXISTING instance from its module file (new pars, refreshed menus, new shader text, panel knobs) and
    bring its module presets up to date (preset_plan: same-name rows replaced, free slots filled, user rows kept).
    The way new module features reach main (by builder, one module per exec; un-park first, T-146)."""
    c = op(comp_path)
    row = next((r for r in _rows(c) if r['name'] == name), None)
    if row is None or c.op(name) is None:
        return {'error': 'no instance %s' % name}
    M = _module(row['module'])
    info = _instance(c, name, row['module'], panel=panel)
    pt = c.op(name).op('controls/zk_presets')
    res = {'instance': info}
    if pt is not None:
        L = c.op(name).op('controls/zk_logic').module
        rows = [(pt[i, 0].val, pt[i, 1].val) for i in range(1, pt.numRows)]
        rep, app, skip = preset_plan(rows, M['PRESETS'])
        for i in range(1, pt.numRows):
            s = int(float(pt[i, 0].val))
            if s in rep:
                pt[i, 3] = L.preset_dump(rep[s][1])
        for slot, pname, vals in app:
            pt.appendRow([slot, pname, L.DEFAULT_COLOR, L.preset_dump(vals)])
        res.update(replaced=sorted(rep), appended=[a[0] for a in app], kept_user=skip)
    rewire(c)
    _layout(c)
    return res


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
