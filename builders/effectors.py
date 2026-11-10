# effectors builder - /project1/effectors: the shared, modular effector list (px_requirements items 11 + 12) and the thin
# adapters that let other COMPs use it. Doc: docs/builds/effectors.md. Logic: builders/effectors_logic.py (tests
# test/test_effectors.py); runtime: builders/effectors_rt.py (Text DAT eff_rt); GLSL: builders/glsl/px_common.glsl
# (packed section) + eff_consumer.glsl + eff_field2d.glsl.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/effectors.py').read(), ns)
#   ns['build']()                                     # /project1/effectors (+ sphere1 / box1 on the first build)
#   ns['add']('pts', ref='/project1/lab/FT_face_track/out_pts', tags='hands face')   # -> 'pts1'
#   ns['remove']('box1'); ns['duplicate']('sphere1'); ns['rename']('sphere2', 'left'); ns['enable']('left', False)
#   ns['attach']('/project1/lab/BO_particles')        # adapter (the builders below call it at the end of build())
# Idempotent (ops reused by name, the list and object transforms kept); T-70 safe (_sd = safe_destroy, own controls
# window closed first, pane never moved); T-67 plain data in storage; T-74 no TOP readback. ASCII only.
import os

NAME = 'effectors'
PARENT = '/project1'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
GLSL = HERE + '/glsl'
LOGIC_FILE = os.path.join(HERE, 'effectors_logic.py')
RT_FILE = os.path.join(HERE, 'effectors_rt.py')
GRID_LOGIC_FILE = os.path.join(HERE, 'effectors_grid_logic.py')
MENU_FILE = os.path.join(HERE, 'menu_logic.py')        # live dropdowns (T-233), shared with px.py
GRID_FILE = os.path.join(HERE, 'effectors_grid.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
ROWS_PATH = PARENT + '/' + NAME + '/eff_rows'
NOTES = []

# eff_rows' clock: every frame when Track = frame, or while the Lights page's Palshift is driven (an expression /
# export: a time-varying par read inside a Script CHOP does not recook it alone, T-113; live b4 31550).
FRAME_EXPR = ("absTime.frame if (parent().par.Track.eval() == 'frame' or (lambda p, c: p is not None and "
              "p.mode != c)(getattr(parent().par, 'Palshift', None), ParMode.CONSTANT)) else 0")

ROWS_CB = """# eff_rows: the packed effector buffer (effectors_logic.pack_buffer via eff_rt.cook_rows). One sample per texel,
# channels x y z w. Consumers bind it as `uniform samplerBuffer uEffRows` (Arrays page, texturebuffer).
def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = %r
        p.mode = ParMode.EXPRESSION      # the clock (effectors.py FRAME_EXPR): set here, the par is made after build()
    return

def onCook(scriptOp):
    op('eff_rt').module.cook_rows(scriptOp)
    return
""" % FRAME_EXPR

GRID_PARS = """# grid_pars: the Grid page (lane E voxel grid): Gridon / Painton park or wake /project1/effectors/grid; the paint
# pulses clear / save / load the paint volume (eff_grid.on_pulse).
def onValueChange(par, prev):
    parent().op('eff_grid').module.park()
    return

def onPulse(par):
    r = parent().op('eff_grid').module.on_pulse(par.name)
    parent().op('eff_rt').module.status(str(r))
    return
"""

WATCH = """# eff_watch: a hand edit of eff_list -> eff_rt.bump() (new Listver: rows re-parse, consumers re-select).
def onTableChange(dat):
    op('eff_rt').module.bump()
    return
"""

PULSES = """# eff_pulses: Add / Remove / Duplicate / Rename / Toggle / Sync -> eff_rt (list edits; never parked: T-100/T-107).
def onPulse(par):
    op('eff_rt').module.on_pulse(par)
    return
"""

COLLIDERS_CB = """# eff_colliders (BN_cloth adapter): in3 colliders (input 0, x y z r per sample) + the selected shared effectors as
# spheres (effectors_logic.colliders) -> the engine's collider input.
def onCook(scriptOp):
    P = parent()
    ins = scriptOp.inputs
    base = ins[0] if ins else None
    cols = []
    if base is not None and base.numChans and all(base[n] is not None for n in 'xyzr'):
        cols = [tuple(float(base[n][s]) for n in 'xyzr') for s in range(base.numSamples)]
    R = op('/project1/effectors/eff_rt')
    E = op('eff_in')
    if P.par.Effon.eval() and R is not None and E is not None and E.numChans >= 4:
        tex = E.numpyArray()[:4].T.tolist()          # one CHOP read (live: per-sample reads = 20 ms at 2115 texels)
        cols += R.module.L().colliders(tex, R.module.sel_vec(P.par.Effselect.eval()), P.par.Effpad.eval())
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    if not cols:
        return
    scriptOp.numSamples = len(cols)
    for k, n in enumerate('xyzr'):
        scriptOp.appendChan(n).vals = [c[k] for c in cols]
    return
"""


def _read(path):
    with open(path) as f:
        return f.read()


def _logic():
    ns = {'__name__': 'effectors_logic'}
    exec(compile(_read(LOGIC_FILE), LOGIC_FILE, 'exec'), ns)
    return ns


def _menu_logic():
    ns = {'__name__': 'menu_logic'}
    exec(compile(_read(MENU_FILE), MENU_FILE, 'exec'), ns)
    return ns


def _menu_src(c, name, kind):
    """menuSource of a dropdown par (spec option 'menu': kind): local on /project1/effectors itself, through the
    shared eff_rt (empty menu while the list is missing) on every other COMP."""
    ML = _menu_logic()
    if c.path == PARENT + '/' + NAME:
        return ML['local_source'](name, 'eff_rt')
    return ML['shared_source'](name, kind)


# Name fields on consumer COMPs that become dropdowns (besides Effselect, which every consumer has): COMP name ->
# {par: eff_rt.menu kind}. Builders mark new pars with 'menu': kind; this map converts COMPs built before (T-233).
MENU_TARGETS = {'GN_physarum': {'Effectors': 'objects@'}, 'GN_reaction_diffusion': {'Effectors': 'objects@'},
                'MX_prox_material': {'Effectors': 'objects', 'Envgeo': 'geos'}, 'GEN_interactive': {'Nulls': 'objects'}}
OWN_MENUS = {'Target': 'target', 'Paintselect': 'select', 'Eraseselect': 'select', 'Addref': 'refs', 'Refto': 'refs'}


def menus(c):
    """Live dropdowns on one COMP, in place (menu_logic.to_strmenu: values, expressions, page order kept): the
    shared list's own fields on /project1/effectors, else Effselect + MENU_TARGETS[c.name]. {par: result}."""
    ML = _menu_logic()
    own = c.path == PARENT + '/' + NAME
    want = dict(OWN_MENUS) if own else dict({'Effselect': 'select'}, **MENU_TARGETS.get(c.name, {}))
    out = {}
    for n, kind in want.items():
        r = ML['to_strmenu'](c, n, _menu_src(c, n, kind))
        if r is not None:
            out[n] = r
    return out


def dropdowns_upgrade(root='/project1', depth=3):
    """Live dropdowns on an existing project, no rebuild (28 Oct, user: "can u not have a drop down for these? and
    all"): /project1/effectors gets the new eff_logic / eff_rt text + the menu_logic DAT and its Target /
    Paintselect / Eraseselect become dropdowns; every other COMP under root (depth) with an Effselect par or listed
    in MENU_TARGETS gets its name fields converted. PX_pointfx has its own (px.py dropdowns_upgrade). The list
    (eff_list) and every value are kept. Pane on /project1 while it runs (T-213); close controls windows first."""
    c = op(PARENT + '/' + NAME)
    out = {}
    if c is not None:
        _text(c, 'eff_logic', _read(LOGIC_FILE), 'Pure logic (copy of builders/effectors_logic.py).')
        _text(c, 'eff_rt', _read(RT_FILE), 'Runtime: rows, list edits, objects, paths (copy of builders/effectors_rt.py).')
        _text(c, 'menu_logic', _read(MENU_FILE), 'Live dropdown items (copy of builders/menu_logic.py, T-233).')
        _close_window(c)
        out[c.path] = menus(c)
    for o in op(root).findChildren(type=COMP, maxDepth=depth):
        if o.name == 'PX_pointfx' or (c is not None and (o is c or o.path.startswith(c.path + '/'))):
            continue
        if getattr(o.par, 'Effselect', None) is not None or o.name in MENU_TARGETS:
            _close_window(o)                          # never destroy a par an open controls window shows (T-70)
            r = menus(o)
            if r:
                out[o.path] = r
    return out


def set_ref(name, ref):
    """Tie effector `name` to an object COMP (a Null of the rig, a Geometry or Light COMP): its transform drives the
    effector. ref '' unties. -> the stored (absolute) ref. Same as Target + Refto + Setref on the Effectors page."""
    return _rt().set_ref(name, ref)


def ref_upgrade():
    """In place on an existing /project1/effectors (28 Oct, user: how to tie an effector to a Null): the new eff_rt
    + menu_logic text, the Addref / Refto dropdowns + Setref pulse on the Effectors page (in their place), eff_pulses
    listening to Setref, the zkit panel refreshed (reopened when it was open). eff_list, objects and every value are
    kept. Idempotent. Pane on /project1 while it runs (T-213)."""
    c = op(PARENT + '/' + NAME)
    if c is None:
        return {'error': 'no %s/%s' % (PARENT, NAME)}
    t = c.op('eff_list')
    before = [[x.val for x in t.row(r)] for r in range(t.numRows)] if t is not None else []
    try:
        for pn in ui.panes:
            if pn.type == PaneType.NETWORKEDITOR and pn.owner is not None and \
                    (pn.owner.path + '/').startswith(c.path + '/'):
                pn.owner = op(PARENT)
    except Exception:
        pass
    was_open = _close_window(c)               # never add / sort pars a controls window shows (T-70)
    c.allowCooking = True
    _text(c, 'eff_logic', _read(LOGIC_FILE), 'Pure logic (copy of builders/effectors_logic.py).')   # same text = no-op
    _text(c, 'eff_rt', _read(RT_FILE), 'Runtime: rows, list edits, objects, paths (copy of builders/effectors_rt.py).')
    _text(c, 'menu_logic', _read(MENU_FILE), 'Live dropdown items (copy of builders/menu_logic.py, T-233).')
    Lg = _logic()
    had = [n for n in ('Addref', 'Refto', 'Setref') if getattr(c.par, n, None) is not None]
    _list_pars(c, Lg)
    m = menus(c)
    pe = c.op('eff_pulses')
    if pe is not None and pe.par.pars.eval() != PULSE_PARS:
        pe.par.pars = PULSE_PARS
    after = [[x.val for x in t.row(r)] for r in range(t.numRows)] if t is not None else []
    panel = None
    if c.op('controls/zk_cfg') is not None:
        try:
            ns = dict(globals())
            exec(_read(ZKIT_FILE), ns)
            panel = ns['refresh_panel'](c.path)
        except Exception as e:
            panel = {'error': str(e)}
    if was_open and c.op('controls_window') is not None:
        run("op(args[0]).par.winopen.pulse()", c.op('controls_window').path, delayFrames=5)
    page = next(pg for pg in c.customPages if pg.name == 'Effectors')
    return {'comp': c.path, 'added': [n for n in ('Addref', 'Refto', 'Setref') if n not in had], 'menus': m,
            'list_kept': before == after, 'rows': len(after) - 1, 'pulses': pe.par.pars.eval() if pe else None,
            'order': [x[0].tupletName for x in page.parTuplets], 'panel': panel, 'reopen': was_open}


def _grid_logic():
    ns = {'__name__': 'effectors_grid_logic'}
    exec(compile(_read(GRID_LOGIC_FILE), GRID_LOGIC_FILE, 'exec'), ns)
    return ns


def grid_texts(Lg):
    """Shader texts of the grid COMP: scatter / seed / jfa standalone, paint = the consumer prefix + eff_grid_paint."""
    return {'scatter': _read(GLSL + '/eff_grid_scatter.glsl'), 'seed': _read(GLSL + '/eff_grid_seed.glsl'),
            'jfa': _read(GLSL + '/eff_grid_jfa.glsl'), 'paint': _prefix(Lg) + _read(GLSL + '/eff_grid_paint.glsl')}


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
    if par.mode != ParMode.EXPRESSION or par.expr != e:
        par.expr = e
        par.mode = ParMode.EXPRESSION


def _wire(src, dst, i=0):
    """T-00c: connect through the destination's input connector i, then verify."""
    cur = dst.inputConnectors[i].connections if i < len(dst.inputConnectors) else []
    if cur and cur[0].owner is src:
        return
    src.outputConnectors[0].connect(dst.inputConnectors[i])


def _text(c, name, text, comment=''):
    d = _mk(c, textDAT, name, viewer=False)
    if d.text != text:
        d.text = text
    if comment:
        d.comment = comment
    return d


def _script(c, name, text, inputs=()):
    """Script CHOP + its callbacks DAT `<name>_callbacks` (the auto-docked one reused / renamed, as the RD builder)."""
    s = _mk(c, scriptCHOP, name)
    for i, src in enumerate(inputs):
        _wire(src, s, i)
    want = name + '_callbacks'
    cb = c.op(want)
    if cb is None or cb.OPType != 'textDAT':
        cb = s.par.callbacks.eval()
        if cb is None:
            cb = _mk(c, textDAT, want, viewer=False)
        elif cb.name != want and c.op(want) is None:
            cb.name = want
    if cb.text != text:
        cb.text = text
    s.par.callbacks = cb.name
    s.par.setuppars.pulse()
    return s


def _pars(c, page_name, pars):
    """Custom pars (name, style, default, opts) on page_name; existing pars and values are kept."""
    page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
    for name, style, default, o in pars:
        if getattr(c.par, name, None) is not None or getattr(c.par, name + 'r', None) is not None or \
                getattr(c.par, name + 'x', None) is not None:
            continue
        label = o.get('label', name)
        if style == 'Menu':
            p = page.appendMenu(name, label=label)[0]
            p.menuNames, p.menuLabels = o['names'], o['labels']
            p.default = p.val = default
        elif style in ('Float', 'Int'):
            p = (page.appendFloat if style == 'Float' else page.appendInt)(name, label=label)[0]
            p.normMin, p.normMax = o.get('min', 0), o.get('max', 1)      # slider range only (no limits)
            p.default = p.val = default
        elif style == 'Toggle':
            p = page.appendToggle(name, label=label)[0]
            p.default = p.val = default
        elif style == 'Pulse':
            page.appendPulse(name, label=label)
        elif style == 'Str' and o.get('menu'):     # live dropdown, free text kept (T-233)
            p = page.appendStrMenu(name, label=label)[0]
            p.menuSource = _menu_src(c, name, o['menu'])
            p.default = p.val = default
        elif style == 'Str':
            p = page.appendStr(name, label=label)[0]
            p.default = p.val = default
        elif style in ('RGB', 'XYZ'):
            ps = page.appendRGB(name, label=label) if style == 'RGB' else page.appendXYZ(name, label=label)
            for p, v in zip(ps, default):
                p.default = p.val = v
                if style == 'XYZ':
                    p.normMin, p.normMax = o.get('min', -5), o.get('max', 5)


def _slot(o, seq, name):
    """Index of the uniform block called `name` in o's vec / array sequence, else the first free one (appended):
    the adapter never moves a builder's own slots."""
    s = getattr(o.seq, seq)
    n = int(s.numBlocks)
    for k in range(n):
        if getattr(o.par, '%s%dname' % (seq, k)).eval() == name:
            return k
    for k in range(n):
        if not getattr(o.par, '%s%dname' % (seq, k)).eval():
            return k
    s.numBlocks = n + 1
    return n


def _vecs(o, specs):
    for name, ex in specs:
        k = _slot(o, 'vec', name)
        getattr(o.par, 'vec%dname' % k).val = name
        for ax, e in zip('xyzw', ex):
            p = getattr(o.par, 'vec%dvalue%s' % (k, ax))
            if isinstance(e, (int, float)):
                p.mode = ParMode.CONSTANT
                p.val = e
            else:
                _expr(p, e)


def _buffer(o, chop='eff_in'):
    k = _slot(o, 'array', 'uEffRows')
    getattr(o.par, 'array%dname' % k).val = 'uEffRows'
    getattr(o.par, 'array%dtype' % k).val = 'vec4'
    getattr(o.par, 'array%dchop' % k).val = chop
    getattr(o.par, 'array%darraytype' % k).val = 'texturebuffer'


# ------------------------------------------------------------------------------------------------ /project1/effectors

EFF_ORDER = ['Addkind', 'Addname', 'Addtags', 'Addref', 'Add', 'Target', 'Remove', 'Duplicate', 'Newname', 'Rename',
             'Toggle', 'Refto', 'Setref', 'Track', 'Sync', 'Status', 'Listver']
PULSE_PARS = 'Add Remove Duplicate Rename Toggle Sync Setref'


def _sort_page(c, page_name, order):
    """Put the page's pars in `order` (tuplet names, T-234); pars not listed keep their order after them. Only
    when the order differs (a sort is a page change the parameter dialog redraws)."""
    page = next((pg for pg in c.customPages if pg.name == page_name), None)
    if page is None:
        return False
    cur = [t[0].tupletName for t in page.parTuplets]
    want = [n for n in order if n in cur] + [n for n in cur if n not in order]
    if want == cur:
        return False
    page.sort(*want)
    return True


def _list_pars(c, Lg):
    m = lambda menu, label: {'names': Lg['names'](menu), 'labels': Lg['labels'](menu), 'label': label}
    _pars(c, 'Effectors', [
        ('Addkind', 'Menu', 'sphere', m(Lg['KINDS'], 'Kind to add')),
        ('Addname', 'Str', '', {'label': 'Name (empty = kind + n)'}),
        ('Addtags', 'Str', '', {'label': 'Tags (space separated)'}),
        ('Addref', 'Str', '', {'label': 'Tie new one to (Null / Geo / Light)', 'menu': 'refs'}),
        ('Add', 'Pulse', None, {'label': 'Add effector'}),
        ('Target', 'Str', '', {'label': 'Effector (for the pulses below)', 'menu': 'target'}),
        ('Remove', 'Pulse', None, {'label': 'Remove'}),
        ('Duplicate', 'Pulse', None, {'label': 'Duplicate'}),
        ('Newname', 'Str', '', {'label': 'New name'}),
        ('Rename', 'Pulse', None, {'label': 'Rename'}),
        ('Toggle', 'Pulse', None, {'label': 'Enable / disable'}),
        ('Refto', 'Str', '', {'label': 'Tie Target to (Null / Geo / Light)', 'menu': 'refs'}),
        ('Setref', 'Pulse', None, {'label': 'Set ref (tie / untie Target)'}),
        ('Track', 'Menu', 'frame', m(Lg['TRACK'], 'Update rows')),
        ('Sync', 'Pulse', None, {'label': 'Sync objects to the list'}),
        ('Status', 'Str', '', {'label': 'Status'}),
        ('Listver', 'Int', 0, {'label': 'List version (auto)', 'max': 1000}),
    ])
    _sort_page(c, 'Effectors', EFF_ORDER)     # pars added to a list built earlier land in their place (T-234)
    a = c.par.Addkind                         # _pars keeps existing pars: refresh the menu (new kinds, e.g. light)
    if list(a.menuNames) != Lg['names'](Lg['KINDS']):
        a.menuNames, a.menuLabels = Lg['names'](Lg['KINDS']), Lg['labels'](Lg['KINDS'])
    _pars(c, 'Lights', Lg['light_palette_pars']())
    _pars(c, 'Grid', _grid_logic()['grid_pars']())


def _rows_ops(c):
    """eff_rows (the buffer every consumer reads: #pub and disabled rows inert) + eff_rows_pub (same layout, #pub rows
    live: the grid and consumers that select a published row). Both cook only when pulled."""
    rows_ = None
    for nm, cm in (('eff_rows', 'Packed effector buffer (header + 10 texels per effector + point sets): uEffRows in '
                    'every consumer (Track = frame: every frame). #pub and disabled rows are inert placeholders here.'),
                   (PUB_ROWS, 'Same buffer with the #pub rows live (a COMP\'s published points: PX hot points, '
                    'FX_track track): read by the grid and by consumers whose Effselect names one (eff_rt.rows_for).')):
        o = _script(c, nm, ROWS_CB)
        if getattr(o.par, 'Frame', None) is not None:   # a time-dependent own par cooks the CHOP every frame even unread
            _expr(o.par.Frame, FRAME_EXPR)            # (live): frame only, or while Palshift is driven
        o.comment = cm
        if nm == 'eff_rows':
            rows_ = o
        else:
            o.nodeX, o.nodeY = rows_.nodeX, rows_.nodeY - 150
    return rows_


def build(panel=True):
    """/project1/effectors: eff_list (the list) + objects + eff_rows (packed buffer) + eff_tex (same data as a TOP)."""
    del NOTES[:]
    Lg = _logic()
    pc = op(PARENT)
    c = pc.op(NAME) or pc.create(baseCOMP, NAME)
    c.allowCooking = True                     # never parked: pulses + every consumer reads it (T-100 / T-107)
    was_open = _close_window(c)
    _list_pars(c, Lg)
    c.par.Status.readOnly = True
    c.par.Listver.readOnly = True
    lg = _text(c, 'eff_logic', _read(LOGIC_FILE), 'Pure logic (copy of builders/effectors_logic.py).')
    rt = _text(c, 'eff_rt', _read(RT_FILE), 'Runtime: rows, list edits, objects, paths (copy of builders/effectors_rt.py).')
    _text(c, 'eff_grid_logic', _read(GRID_LOGIC_FILE), 'Voxel grid logic (copy of builders/effectors_grid_logic.py).')
    _text(c, 'menu_logic', _read(MENU_FILE), 'Live dropdown items (copy of builders/menu_logic.py, T-233).')
    menus(c)                                  # Target / Paintselect / Eraseselect made before T-233 -> dropdowns
    gr = _text(c, 'eff_grid', _read(GRID_FILE), 'Voxel grid runtime: grid COMP, scatter sync, paint pulses (copy of '
               'builders/effectors_grid.py).')
    t = _mk(c, tableDAT, 'eff_list')
    head = [x.val for x in t.row(0)] if t.numRows else []
    if head != Lg['COLS']:                    # T-107: a new Table DAT is not empty; keep a real list's rows
        old = [[x.val for x in t.row(r)] for r in range(t.numRows)] if head and 'name' in head else []
        rows = Lg['parse_table'](old) if old else []
        if not rows:
            for nm, kind, tags in Lg['SEED']:
                rows, _ = Lg['add_row'](rows, kind, nm, tags=tags)
        t.clear()
        for r in Lg['table_cells'](rows):
            t.appendRow(r)
    t.comment = ('THE effector list: one row per effector (%s). Edit cells, or use the Effectors page pulses. Order = '
                 'packed row order.' % ' '.join(Lg['COLS']))
    gm = _mk(c, wireframeMAT, 'giz_mat')
    gm.comment = 'Gizmo wire material of the effector objects.'
    rows_ = _rows_ops(c)
    tex = _mk(c, choptoTOP, 'eff_tex')
    tex.par.chop = rows_.name                 # CHOP to TOP has no input connector on 31550: its `chop` par (live)
    try:
        tex.par.dataformat = 'rgba'
        tex.par.format = 'rgba32float'
    except Exception as e:
        NOTES.append('eff_tex pars: %s' % e)
    tex.comment = 'Same data as a 1-row rgba32f TOP (texel x = buffer index) for TOP pipelines / viewing.'
    pe = _mk(c, parameterexecuteDAT, 'eff_pulses', viewer=False)
    if pe.text != PULSES:
        pe.text = PULSES
    pe.par.op = c
    pe.par.pars = PULSE_PARS
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = False
    pe.par.onpulse = True
    wa = _mk(c, datexecuteDAT, 'eff_watch', viewer=False)
    if wa.text != WATCH:
        wa.text = WATCH
    wa.par.dat = t.name
    wa.par.tablechange = True
    wa.par.active = False                     # T-97 / T-113: toggle after the text is set or callbacks stay silent
    wa.par.active = True
    wa.comment = 'Hand edits of eff_list bump Listver (consumers depend on that one par, not on every cell).'
    gx = _mk(c, parameterexecuteDAT, 'grid_pars', viewer=False)
    if gx.text != GRID_PARS:
        gx.text = GRID_PARS
    gx.par.op = c
    gx.par.pars = 'Gridon Painton Paintclear Paintsave Paintload'
    gx.par.custom = True
    gx.par.builtin = False
    gx.par.valuechange = True
    gx.par.onpulse = True
    try:
        gr.module.build(grid_texts(Lg))           # parked unless Gridon / Painton (off by default)
    except Exception as e:
        NOTES.append('grid: %s' % e)
    made = rt.module.sync_objects()
    try:
        refreshed = refresh_consumers()           # consumers built before the list existed (T-159)
    except Exception as e:
        refreshed = 0
        NOTES.append('refresh_consumers: %s' % e)
    c.comment = ('Shared effectors (docs/builds/effectors.md): eff_list = the list (add / remove / duplicate / rename / '
                 'enable), objects = the effectors (move / rotate / scale), eff_rows = packed buffer every consumer '
                 'reads by name / tag (Effselect). Never parked.')
    c.par.opviewer = 'eff_tex'
    info = None
    if panel:
        try:
            ns = dict(globals())
            exec(_read(ZKIT_FILE), ns)
            info = ns['build_controls'](c.path, pages=['Effectors'], d=56, cols=8, open_window=was_open)
        except Exception as e:
            NOTES.append('zkit panel: %s' % e)
    return {'comp': c.path, 'objects': made, 'rows': t.numRows - 1, 'refreshed': refreshed, 'notes': list(NOTES),
            'panel': str(info)[:200]}


def _rt():
    c = op(PARENT + '/' + NAME)
    if c is None:
        build(panel=False)
        c = op(PARENT + '/' + NAME)
    return c.op('eff_rt').module


def add(kind='sphere', name=None, tags='', ref='', **vals):
    return _rt().add(kind, name, tags, ref, **vals)


def remove(name):
    return _rt().remove(name)


def duplicate(name, new=None):
    return _rt().duplicate(name, new)


def rename(name, new):
    return _rt().rename(name, new)


def enable(name, on=True):
    return _rt().enable(name, on)


def set_value(name, col, value):
    return _rt().set_value(name, col, value)


def _op_list(v, home=None):
    """An object-list par's eval() -> space-separated names (31550: a Render TOP's `lights` evals to a LIST of OPs,
    live b4; a str or one OP also accepted). Ops beside `home` (the Render TOP's parent) keep their bare name, so the
    COMP still works when exported / loaded elsewhere; others get their path."""
    if v is None:
        return ''
    if isinstance(v, str):
        return v.strip()
    if hasattr(v, 'path'):
        v = [v]
    return ' '.join((o.name if home is not None and o.parent() == home else o.path) for o in v
                    if o is not None and hasattr(o, 'path'))


def light_render(render_path, sel='all', keep=None):
    """Light a Render TOP with the `light` effectors (TD-native: PBR / Phong / MX MATs): its `lights` par becomes
    `keep` + the Light COMPs `sel` picks (effectors_logic.lights_expr; follows list edits). keep = None keeps the
    par's current constant value (e.g. MX's 'light1 env1'). Returns the expression."""
    r = op(render_path)
    if r is None or getattr(r.par, 'lights', None) is None:
        raise ValueError('not a Render TOP: %s' % render_path)
    p = r.par.lights
    if keep is None:
        keep = '' if p.mode == ParMode.EXPRESSION else _op_list(p.eval(), r.parent())
    e = _logic()['lights_expr'](sel, keep)
    _expr(p, e)
    return e


# ------------------------------------------------------------------------------------------------ pub_upgrade (29 Oct)
# Drop-in round: rows another COMP publishes (PX hot points, FX_track `track`, a COMP's cloud / point set) carry the
# tag `pub`; 'all' = the user's own effectors; eff_rows packs #pub and disabled rows inert (nothing of theirs read), so
# consumers hold no reference to the publishing COMP; eff_rows_pub (same layout, #pub live) feeds the grid and the
# consumers whose Effselect names a published row (eff_rt.rows_for). In place on an existing list, staged, UI-safe.
PUB_STEPS = ('p_texts', 'p_ops', 'p_tags', 'p_grid', 'p_consumers', 'done')
PUB_GAP = 10                                  # frames between two steps (never one frame: T-249 / T-250)
UPG_FILE = os.path.join(HERE, 'effectors.py')


def pub_candidates(rows_, resolve=None):
    """Names of the rows that are published but not yet tagged `pub`: PX hot rows (px_hot*, tag pxhot), FX_track's
    `track` link, and any cloud / pts / actor row whose ref lies inside another COMP that has its own pages (a module:
    resolve(ref) -> (exists, owner_has_pages)). Pure apart from resolve."""
    Lg = _logic()
    out = []
    for r in rows_:
        if Lg['is_pub'](r):
            continue
        tg = Lg['row_tags'](r)
        ref = str(r.get('ref') or '')
        pub = str(r['name']).startswith('px_hot') or 'pxhot' in tg
        pub = pub or ('track' in tg and ref.endswith('/out_pts'))
        if not pub and r.get('kind') in ('cloud', 'pts', 'actor') and ref and resolve is not None:
            ok, module = resolve(ref, r.get('kind'))
            pub = bool(ok and module)
        if pub:
            out.append(r['name'])
    return out


def _resolver(c):
    def res(ref, kind):
        o = c.op('eff_rt').module._find(ref)
        if o is None:
            return False, False
        own = o if (kind == 'actor' and o.isCOMP) else o.parent()
        if own is None or own.path == c.path or own.path.startswith(c.path + '/') or own.path in ('/', PARENT):
            return True, False
        return True, bool(len(own.customPages))
    return res


def _pub_later(step, delay=PUB_GAP):
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_pub_step'](%r)" % (UPG_FILE, step),
        delayFrames=delay, delayRef=op.TDResources)


def pub_upgrade():
    """In place on /project1/effectors (docs/builds/effectors.md "Published rows"): closes its controls window, then
    p_texts (eff_logic / eff_rt / eff_grid), p_ops (eff_rows_pub), p_tags (eff_rows_pub clock + `pub` on published
    rows), p_grid (scatter / paint passes read eff_rows_pub, relative), p_consumers (every eff_in with the old
    expression -> rows_for), done. PUB_GAP frames apart. Read pub_result() in a LATER exec; a second run reports
    changed = []. No list row is removed, renamed or re-enabled."""
    c = op(PARENT + '/' + NAME)
    if c is None:
        return {'state': 'skipped', 'why': 'no %s/%s' % (PARENT, NAME)}
    was_open = _close_window(c)
    c.store('eff_upgrade', {'state': 'running', 'step': PUB_STEPS[0], 'start': absTime.frame, 'changed': [],
                            'was_open': bool(was_open), 'rows0': c.op('eff_list').numRows - 1})
    _pub_later(PUB_STEPS[0], 3)
    return {'scheduled': PUB_STEPS, 'read': 'pub_result()'}


def pub_result():
    c = op(PARENT + '/' + NAME)
    return c.fetch('eff_upgrade', None, search=False) if c is not None else None


def _pub_work(c, step):
    ch = []
    if step == 'p_texts':
        for dat, path in (('eff_logic', LOGIC_FILE), ('eff_rt', RT_FILE), ('eff_grid', GRID_FILE)):
            d = c.op(dat)
            if d is not None and d.text != _read(path):
                d.text = _read(path)
                ch.append(dat)
    elif step == 'p_ops':
        if c.op(PUB_ROWS) is None:
            _rows_ops(c)
            ch.append(PUB_ROWS)
    elif step == 'p_tags':
        o = c.op(PUB_ROWS)
        if o is not None and getattr(o.par, 'Frame', None) is not None and \
                (o.par.Frame.mode != ParMode.EXPRESSION or o.par.Frame.expr != FRAME_EXPR):
            _expr(o.par.Frame, FRAME_EXPR)
            ch.append(PUB_ROWS + ':Frame')
        rt = c.op('eff_rt').module
        rs = rt.rows()
        names_ = pub_candidates(rs, _resolver(c))
        if names_:
            Lg = _logic()
            out = []
            for r in rs:
                d = dict(r)
                if d['name'] in names_:
                    d['tags'] = ' '.join(Lg['row_tags'](d) + [Lg['PUB_TAG']])
                out.append(d)
            rt.write_rows(out)
            ch.append('pub ' + ' '.join(names_))
    elif step == 'p_grid':
        gm, gc = c.op('eff_grid'), c.op('grid')
        if gm is not None and gc is not None:
            for o in gc.children:
                if o.OPType != 'glslTOP':
                    continue
                k = next((i for i in range(int(o.seq.array.numBlocks))
                          if getattr(o.par, 'array%dname' % i).eval() == 'uEffRows'), None)
                if k is None:
                    continue
                v0 = getattr(o.par, 'array%dchop' % k).val
                gm.module._buffer(o)
                if getattr(o.par, 'array%dchop' % k).val != v0:
                    ch.append('grid/' + o.name)
    elif step == 'p_consumers':
        ch += [p_[len(PARENT) + 1:] for p_ in pub_consumer(PARENT)]
    return ch


def pub_consumer(root_path):
    """Every adapter eff_in under root_path (a consumer COMP, or a whole network) with the pre-29-Oct expression ->
    EFF_IN_EXPR (reads eff_rows_pub only when Effselect names a #pub row). Only Select CHOPs named eff_in, only their
    `chops` expression text (no par evaluated, T-255). -> the consumer COMP paths changed."""
    r = op(root_path)
    out = []
    if r is None:
        return out
    sels = [r] if (r.OPType == 'selectCHOP' and r.name == 'eff_in') else list(r.findChildren(type=selectCHOP,
                                                                                               name='eff_in'))
    for sel in sels:
        p = sel.par.chops
        if p.mode == ParMode.EXPRESSION and p.expr == EFF_IN_OLD:
            p.expr = EFF_IN_EXPR
            out.append(sel.parent().path)
    return out


def _pub_step(step):
    c = op(PARENT + '/' + NAME)
    st = dict(c.fetch('eff_upgrade', {}, search=False) or {})
    changed = list(st.get('changed', []))
    try:
        if step == 'done':
            st['rows1'] = c.op('eff_list').numRows - 1
            st['errors'] = len([o for o in c.findChildren(maxDepth=2) if o.errors()])
            st['state'] = 'done'
            st['end'] = absTime.frame
        else:
            changed += _pub_work(c, step)
    except Exception as e:
        st['state'] = 'failed'
        st['error'] = '%s at %s: %s' % (type(e).__name__, step, e)
    st['changed'] = changed
    st['step'] = step
    c.store('eff_upgrade', st)
    k = PUB_STEPS.index(step)
    if st['state'] == 'running' and k + 1 < len(PUB_STEPS):
        _pub_later(PUB_STEPS[k + 1])


# ------------------------------------------------------------------------------------------------ adapters

# T-159: Effselect is read before the guard (a guard whose false branch reads nothing gives TD no dependency).
# The lambda uses only its arguments (TD's expression names may not be visible inside it).
RT_PATH = PARENT + '/' + NAME + '/eff_rt'
PUB_ROWS = 'eff_rows_pub'
# 29 Oct (drop-in): eff_in reads eff_rows (#pub rows inert, no reference to the publishing COMP) unless Effselect names a
# published row / tag (then eff_rows_pub): eff_rt.rows_for. An effectors COMP from before (no rows_for) = eff_rows.
EFF_IN_EXPR = ("(lambda s, r, p: ((r.module.rows_for(s) if hasattr(r.module, 'rows_for') else "
               "r.parent().op('eff_rows').path) if r is not None else p.op('eff_none').path))"
               "(me.parent().par.Effselect.eval(), op('%s'), me.parent())" % RT_PATH)
EFF_IN_OLD = ("(lambda s, r, p: '%s' if r is not None else p.op('eff_none').path)"
              "(me.parent().par.Effselect.eval(), op('%s'), me.parent())" % (ROWS_PATH, ROWS_PATH))


def refresh_consumers(root=PARENT):
    """Re-set every effector expression of every consumer under root (the COMP holding an `eff_in`, + its direct
    children). TD does not re-evaluate `op(path) is not None` when that op is CREATED (T-158 (1), T-159), so a consumer
    built before /project1/effectors keeps eff_none / zero ids until its expressions are re-set; build() calls this.
    Returns the number of pars re-set."""
    keys = (PARENT + '/' + NAME + '/', "parent().par.Effselect")
    n = 0
    r = op(root)
    if r is None:
        return 0
    rtop = globals().get('renderTOP')
    for rnd in (r.findChildren(type=rtop) if rtop is not None else []):     # light_render() Render TOPs
        p = getattr(rnd.par, 'lights', None)
        if p is not None and p.mode == ParMode.EXPRESSION and 'light_paths(' in p.expr:
            e = p.expr
            p.expr = "''"
            p.expr = e
            n += 1
    for sel in r.findChildren(type=selectCHOP, name='eff_in'):
        comp = sel.parent()
        for o in [comp] + list(comp.findChildren(maxDepth=1)):
            for p in o.pars():
                if p.mode == ParMode.EXPRESSION and any(k in p.expr for k in keys):
                    e = p.expr
                    p.expr = '0'                  # same text is a no-op (T-158): change it, then put it back
                    p.expr = e
                    n += 1
    return n


def _eff_in(c):
    none = _mk(c, constantCHOP, 'eff_none')
    for k, nm in enumerate('xyzw'):
        getattr(none.par, 'name%d' % k).val = nm                  # name0 / value0 (as cuelist / db_meter, live)
        getattr(none.par, 'value%d' % k).val = 0
    none.comment = 'Empty effector list (count 0) while /project1/effectors is missing.'
    sel = _mk(c, selectCHOP, 'eff_in')
    _expr(sel.par.chops, EFF_IN_EXPR)
    sel.comment = 'Shared effector list (/project1/effectors/eff_rows) -> uEffRows. Page Effectors: Effon, Effselect.'
    return sel


def _prefix(Lg, defines=()):
    return Lg['consumer_prefix'](_read(GLSL + '/px_common.glsl'), _read(GLSL + '/eff_consumer.glsl'), defines)


def _patch_text(Lg, dat, prefix):
    if dat is None:
        raise ValueError('shader DAT missing')
    t = Lg['with_prefix'](dat.text, prefix)
    if dat.text != t:
        dat.text = t


def _field_op(c, Lg, name, src, mode, res=None):
    """A compute GLSL TOP running eff_field2d.glsl (mode 0 force, 1 dye, 2 mask); src = input 0 or None."""
    code = _text(c, 'eff_field_compute', _prefix(Lg) + _read(GLSL + '/eff_field2d.glsl'),
                 'eff_field2d.glsl + the shared effector block (regenerated by attach).')
    g = _mk(c, glslTOP, name)
    for d in list(getattr(g, 'docked', []) or []):
        if d.valid and d.name != code.name:
            _sd(d)
    g.par.mode = 'compute'
    g.par.computedat = code.name
    g.par.format = 'rgba32float'
    if res is not None:
        g.par.outputresolution = 'custom'
        g.par.resolutionw, g.par.resolutionh = res
    if src is not None:
        _wire(src, g, 0)
    _buffer(g)
    P = 'parent().par.'
    out = [('uEffOut', (P + 'Effpush', P + 'Effswirl', P + 'Effwake', P + 'Effdye')),
           ('uEffCol', (P + 'Effcolourr', P + 'Effcolourg', P + 'Effcolourb', 0.0))] if mode != 2 else \
        [('uEffOut', (0.0, 0.0, 0.0, 0.0)), ('uEffCol', (0.0, 0.0, 0.0, 0.0))]
    _vecs(g, Lg['consumer_vecs']() + [
        ('uEffPlane', (P + 'Effcentrex', P + 'Effcentrey', P + 'Effplanew', P + 'Effplaneh')),
        ('uEffPlane2', (1.0 if src is not None else 0.0, float(mode), P + 'Effcentrez', 0.0))] + out)
    return g


def _plane_pars(w, h, extra=()):
    return [('Effcentre', 'XYZ', (0.0, 0.0, 0.0), {'label': 'Plane centre (world)'}),
            ('Effplanew', 'Float', w, {'min': 0.01, 'max': 20, 'label': 'Plane width (world)'}),
            ('Effplaneh', 'Float', h, {'min': 0.01, 'max': 20, 'label': 'Plane height (world)'})] + list(extra)


def _switch_after(c, name, a, b):
    s = _mk(c, switchTOP, name)
    _wire(a, s, 0)
    _wire(b, s, 1)
    _expr(s.par.index, '1 if parent().par.Effon.eval() else 0')
    return s


def attach_particles(c, Lg):
    _pars(c, 'Effectors', Lg['CONSUMER_PAGE'] + [
        ('Effpush', 'Float', 2.0, {'min': -10, 'max': 10, 'label': 'Push (outward)'}),
        ('Effattract', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Attract (to the surface)'}),
        ('Effvortex', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Vortex (around the up axis)'}),
        ('Effwake', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Wake (effector velocity)'}),
        ('Effdrag', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Drag near effectors'}),
        ('Effkill', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Kill at weight (0 = off)'}),
        ('Effspawn', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Spawn at effectors (fraction)'}),
        ('Effspawnr', 'Float', 0.2, {'min': 0, 'max': 2, 'label': 'Spawn radius'})])
    _eff_in(c)
    pre = _prefix(Lg, ('PXE_PARTICLES',))
    _patch_text(Lg, c.op('state_compute'), pre)
    if c.op('state_inplace') is not None:
        _patch_text(Lg, c.op('state_inplace'), pre)
    st = c.op('state')
    _buffer(st)
    P = 'parent().par.'
    _vecs(st, Lg['consumer_vecs']() + [
        ('uEffP', (P + 'Effpush', P + 'Effattract', P + 'Effvortex', P + 'Effwake')),
        ('uEffP2', (P + 'Effkill', P + 'Effspawn', P + 'Effspawnr', P + 'Effdrag'))])
    return 'BO_particles: forces / kill / spawn in state (eff_in, uEffP*)'


def _points_page(Lg):
    return Lg['CONSUMER_PAGE'] + [
        ('Effpush', 'Float', 0.3, {'min': -4, 'max': 4, 'label': 'Push (units)'}),
        ('Effdissolve', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Dissolve (+ near / - reveal near)'}),
        ('Effgrow', 'Float', 0.0, {'min': -1, 'max': 8, 'label': 'Scale near (x 1 + gain w)'}),
        ('Effdust', 'Toggle', True, {'label': 'Dust (per point thresholds)'}),
        ('Effdir', 'Menu', 'outward', {'names': ['outward', 'axis', 'velocity'],
                                       'labels': ['Away from effector', 'Effector up axis', 'Effector velocity'],
                                       'label': 'Push direction'})]


def _points_vecs(Lg):
    P = 'parent().par.'
    return Lg['consumer_vecs']() + [
        ('uEffFx', (P + 'Effpush', P + 'Effdissolve', P + 'Effgrow', 'float(%sEffdust)' % P)),
        ('uEffFx2', (P + 'Effdir.menuIndex', 0.0, 0.0, 0.0))]


def attach_splat(c, Lg):
    _pars(c, 'Effectors', _points_page(Lg))
    _eff_in(c)
    _patch_text(Lg, c.op('splat_glsl'), _prefix(Lg, ('PXE_POINTS',)))
    m = c.op('splatmat')
    _buffer(m)
    _vecs(m, _points_vecs(Lg))
    return 'BL_splat_render: push / dissolve / scale per splat in splatmat (splats stay splats)'


def attach_cloud(c, Lg):
    _pars(c, 'Effectors', _points_page(Lg))
    _eff_in(c)
    _patch_text(Lg, c.op('pc_vertex'), _prefix(Lg, ('PXE_POINTS',)))
    m = c.op('pcmat')
    _buffer(m)
    _vecs(m, _points_vecs(Lg))
    return 'BL_cloud_morph: push / dissolve / scale per point in pcmat'


def attach_fluid(c, Lg):
    _pars(c, 'Effectors', Lg['CONSUMER_PAGE'] + _plane_pars(1.125, 2.0, [
        ('Effpush', 'Float', 1.0, {'min': -20, 'max': 20, 'label': 'Push (outward)'}),
        ('Effswirl', 'Float', 0.0, {'min': -20, 'max': 20, 'label': 'Swirl'}),
        ('Effwake', 'Float', 1.0, {'min': -10, 'max': 10, 'label': 'Wake (effector velocity)'}),
        ('Effdye', 'Float', 1.0, {'min': 0, 'max': 20, 'label': 'Dye amount'}),
        ('Effcolour', 'RGB', (1.0, 0.45, 0.1), {'label': 'Dye colour'})]))
    _eff_in(c)
    fs, ss = c.op('force_sel'), c.op('src_sel')
    fp, sp = c.op('force_prep'), c.op('src_prep')
    if None in (fs, ss, fp, sp):
        raise ValueError('BN_fluid2d ops missing (force_sel / src_sel / force_prep / src_prep)')
    ef = _field_op(c, Lg, 'eff_force', fs, 0)
    ed = _field_op(c, Lg, 'eff_dye', ss, 1)
    _wire(_switch_after(c, 'eff_force_sw', fs, ef), fp, 0)
    _wire(_switch_after(c, 'eff_dye_sw', ss, ed), sp, 0)
    return 'BN_fluid2d: force (in3 path) + dye (in1 path) from the effectors (eff_force / eff_dye)'


def attach_cloth(c, Lg):
    _pars(c, 'Effectors', Lg['CPU_PAGE'] + [
        ('Effpad', 'Float', 0.02, {'min': 0, 'max': 0.5, 'label': 'Collider padding'})])
    _eff_in(c)
    col = _script(c, 'eff_colliders', COLLIDERS_CB)
    col.comment = 'in3 colliders + the selected shared effectors as spheres (x y z r) -> engine input 1.'
    in3, eng = c.op('in3'), c.op('engine')
    if eng is None:
        raise ValueError('BN_cloth engine missing')
    if in3 is not None:
        _wire(in3, col, 0)
    _wire(col, eng, 1)
    return 'BN_cloth: colliders (spheres) from the effectors via eff_colliders -> engine input 1 (grab: not built)'


def attach_fx_destroy(c, Lg):
    _pars(c, 'Effectors', Lg['CONSUMER_PAGE'] + _plane_pars(1.0, 1.0))
    _eff_in(c)
    _field_op(c, Lg, 'eff_mask', None, 2, res=(540, 960))
    return ("FX_destroy: eff_mask (weight, frame -0.5..0.5) - set a module's Masksource 'top' + Masktop 'eff_mask' "
            "(a module COMP's OP par resolves beside it, T-81; live 31550); its Point page Effector can be any "
            "/project1/effectors object")


ADAPTERS = {'BO_particles': attach_particles, 'BN_fluid2d': attach_fluid, 'BN_cloth': attach_cloth,
            'BL_splat_render': attach_splat, 'BL_cloud_morph': attach_cloud, 'FX_destroy': attach_fx_destroy}
NATIVE = {'GN_reaction_diffusion': 'native: Effectors par takes @all / @<name> / @#<tag> (engine reads eff_rt)',
          'GN_physarum': 'native: Effectors par takes @all / @<name> / @#<tag> (engine reads eff_rt)',
          'MX_prox_material': 'native: Effsource list + Effselect (builders/prox_mat.py build_unit)',
          'GEN_clone': 'native: builders/gen_clone.py wires eff_in + the prefix'}


def attach(comp_path, kind=None):
    """Add the shared-effector adapter to a consumer COMP (kind = an ADAPTERS key; default: its name)."""
    c = op(comp_path)
    if c is None or not c.isCOMP:
        raise ValueError('not a COMP: %s' % comp_path)
    k = kind or c.name
    if k in NATIVE:
        return NATIVE[k]
    f = ADAPTERS.get(k)
    if f is None:
        raise ValueError('no effector adapter for %s (have %s)' % (k, ' '.join(sorted(ADAPTERS))))
    out = f(c, _logic())
    menus(c)                                  # an Effselect made before T-233 -> dropdown
    return out


def attach_all(parent_path='/project1/lab'):
    out = {}
    for k in list(ADAPTERS) + list(NATIVE):
        c = op(parent_path + '/' + k)
        if c is None:
            continue
        try:
            out[k] = attach(c.path, k)
        except Exception as e:
            out[k] = 'failed: %s' % e
    return out
