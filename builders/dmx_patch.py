# dmx_patch builder - BK_dmx_patch: fixture patch sheet + stage plot + previs + aim helper for BK_dmx_out.
# Spec: docs/research/BK_dmx_artnet_sacn.md sections 2.8, 3.4-3.6 and 7 ("Previz of fixtures"); clean-room, our own code.
# Reads BK_dmx_out (Dmxcomp par): its patch / pixels / profiles_json tables and its out3 universes CHOP. It never
# writes BK_dmx_out; the aim output (out3 here) is wired into BK_dmx_out's in2 by the operator.
# No limits (user rule): no brightness cap, no warnings; the previs shows what is sent.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/dmx_patch.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set; custom par values and the `stage` table kept; zkit panel
# refreshed in place. T-70 safe: nothing destroyed directly (_sd = safe_destroy), controls_window closed before a
# rebuild (zkit reopens it), panel container never destroyed, network pane never moved.
# T-74/T-76: no TOP read methods anywhere (no numpyArray / evalTextSize on TOPs; DMX values arrive as a CHOP).
# T-46/T-47: the only GLSL TOP is one compute pass (address map); the previs is a Render TOP (instancing).
# No Python functions in op storage (T-67). ASCII only.
import os

NAME = 'BK_dmx_patch'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
REPO = os.path.dirname(HERE)
LOGIC_FILE = os.path.join(HERE, 'dmx_patch_logic.py')
DMX_LOGIC_FILE = os.path.join(HERE, 'dmx_logic.py')
RT_FILE = os.path.join(HERE, 'dmx_patch_rt.py')
ADDRMAP_FILE = os.path.join(HERE, 'glsl', 'dmx_patch_addrmap.glsl')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
DEFAULT_DMX = '/project1/lab/BK_dmx_out'

SCRIPT_CB = """# {name}: {what} (patch_rt.{fn}).
def onSetupParameters(scriptOp):
{setup}    return

def onCook(scriptOp):
{clock}    op('patch_rt').module.{fn}(scriptOp)
    return
"""
FRAME_SETUP = """    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
"""
FRAME_READ = "    _clock = scriptOp.par.Frame.eval() if getattr(scriptOp.par, 'Frame', None) is not None else 0\n"

SRC_WATCH = """# src_watch: BK_dmx_out's patch / pixels / profiles_json changed -> sync stage (Autosync) + new plan.
def onTableChange(dat):
    op('patch_rt').module.on_source_change()
    return
"""
STAGE_WATCH = """# stage_watch: the stage plot changed (edits, Sync, Arrange, Calibrate) -> new plan.
def onTableChange(dat):
    op('patch_rt').module.on_stage_change()
    return
"""
SETTINGS = """# settings: replan pars + pulses of this COMP -> patch_rt.
def onValueChange(par, prev):
    op('patch_rt').module.on_value(par)
    return

def onPulse(par):
    op('patch_rt').module.on_pulse(par)
    return
"""
DMX_PARS = """# dmx_pars: Colororder / Univfilter / Firstuniv on BK_dmx_out changed -> new plan here.
def onValueChange(par, prev):
    op('patch_rt').module.on_dmx_value(par)
    return
"""
STATUS_TICK = """# status_tick: read-only status pars every 30 frames (never inside a cook).
def onFrameEnd(frame):
    if frame % 30 == 0:
        op('patch_rt').module.status()
    return
"""


def _logic():
    ns = {}
    exec(open(LOGIC_FILE).read(), ns)
    return ns


def _pages(Lg):
    M = 'Menu'
    return [
        ('Source', [
            ('Dmxcomp', 'COMP', DEFAULT_DMX, {'label': 'DMX out COMP'}),
            ('Univchop', 'CHOP', '', {'label': 'Universes CHOP (blank = Dmxcomp out3)'}),
            ('Chanfmt', 'Str', 'u{u}', {'label': 'Channel name ({u} = universe)'}),
            ('Autosync', 'Toggle', True, {'label': 'Auto sync stage'}),
            ('Syncpatch', 'Pulse', None, {'label': 'Sync from patch'}),
            ('Prune', 'Pulse', None, {'label': 'Prune stale rows'}),
            ('Checkpatch', 'Pulse', None, {'label': 'Check patch + stage'}),
            ('Fixtures', 'Int', 0, {'min': 0, 'max': 1000, 'label': 'Fixtures (read)', 'ro': True}),
            ('Pixelsshown', 'Int', 0, {'min': 0, 'max': 100000, 'label': 'Pixels shown (read)', 'ro': True}),
            ('Conflicts', 'Int', 0, {'min': 0, 'max': 10000, 'label': 'Slot conflicts (read)', 'ro': True}),
            ('Statems', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Python ms (read)', 'ro': True}),
        ]),
        ('Stage', [
            ('Arrange', M, 'line', {'names': Lg['LAYOUTS'], 'labels': ['Line', 'Arc', 'Grid', 'Ring']}),
            ('Arrangeset', 'Str', '*', {'label': 'Fixtures (pattern)'}),
            ('Spanx', 'Float', 12.0, {'min': 0, 'max': 40, 'label': 'Span m'}),
            ('Height', 'Float', 6.0, {'min': 0, 'max': 20, 'label': 'Height m'}),
            ('Depth', 'Float', 0.0, {'min': -20, 'max': 20, 'label': 'Depth z m'}),
            ('Curve', 'Float', 60.0, {'min': 1, 'max': 359, 'label': 'Arc deg'}),
            ('Cols', 'Int', 8, {'min': 1, 'max': 64, 'label': 'Grid columns'}),
            ('Rowgap', 'Float', 1.0, {'min': 0, 'max': 5, 'label': 'Row gap m'}),
            ('Hang', 'Toggle', True, {'label': 'Hanging (rx 180)'}),
            ('Applyarrange', 'Pulse', None, {'label': 'Arrange'}),
            ('Wallx', 'Float', 0.0, {'min': -20, 'max': 20, 'label': 'Pixel wall x'}),
            ('Wally', 'Float', 3.0, {'min': 0, 'max': 20, 'label': 'Pixel wall y'}),
            ('Wallz', 'Float', -1.0, {'min': -20, 'max': 20, 'label': 'Pixel wall z'}),
            ('Wallw', 'Float', 8.0, {'min': 0.1, 'max': 40, 'label': 'Pixel wall w'}),
            ('Wallh', 'Float', 4.5, {'min': 0.1, 'max': 40, 'label': 'Pixel wall h'}),
            ('Pixmax', 'Int', 4096, {'min': 1, 'max': 30000, 'label': 'Pixels drawn (max)'}),
        ]),
        ('View', [
            ('View', M, 'front', {'names': Lg['VIEWS'], 'labels': ['Front', 'Top', 'Side', 'Perspective']}),
            ('Fit', 'Pulse', None, {'label': 'Fit view'}),
            ('Centerx', 'Float', 0.0, {'min': -20, 'max': 20, 'label': 'Centre x'}),
            ('Centery', 'Float', 3.0, {'min': -5, 'max': 20, 'label': 'Centre y'}),
            ('Centerz', 'Float', 0.0, {'min': -20, 'max': 20, 'label': 'Centre z'}),
            ('Viewsize', 'Float', 16.0, {'min': 1, 'max': 80, 'label': 'View size m'}),
            ('Orbit', 'Float', 30.0, {'min': -180, 'max': 180, 'label': 'Orbit deg'}),
            ('Elev', 'Float', 20.0, {'min': -89, 'max': 89, 'label': 'Elevation deg'}),
            ('Fov', 'Float', 40.0, {'min': 10, 'max': 120, 'label': 'FOV deg'}),
            ('Beams', 'Toggle', True, {'label': 'Beams'}),
            ('Beamlen', 'Float', 8.0, {'min': 0, 'max': 30, 'label': 'Beam length m'}),
            ('Beamangle', 'Float', 15.0, {'min': 0, 'max': 90, 'label': 'Beam angle deg'}),
            ('Beamgain', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Beam gain'}),
            ('Bodysize', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'Fixture size m'}),
            ('Pixsize', 'Float', 0.06, {'min': 0, 'max': 0.5, 'label': 'Pixel size m'}),
            ('Pixgain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Pixel gain'}),
            ('Mingrey', 'Float', 0.12, {'min': 0, 'max': 1, 'label': 'Dark fixture grey'}),
            ('Grid', 'Toggle', True, {'label': 'Floor grid'}),
            ('Highlight', 'Str', '', {'label': 'Highlight (pattern)'}),
            ('Resw', 'Int', 1080, {'min': 64, 'max': 4096, 'label': 'Width'}),
            ('Resh', 'Int', 1920, {'min': 64, 'max': 4096, 'label': 'Height'}),
        ]),
        ('Aim', [
            ('Aimon', 'Toggle', False, {'label': 'Aim on (out3)'}),
            ('Aimset', 'Str', '*', {'label': 'Fixtures (pattern)'}),
            ('Targetx', 'Float', 0.0, {'min': -20, 'max': 20, 'label': 'Target x'}),
            ('Targety', 'Float', 0.0, {'min': -5, 'max': 20, 'label': 'Target y'}),
            ('Targetz', 'Float', 4.0, {'min': -20, 'max': 20, 'label': 'Target z'}),
            ('Targetchop', 'CHOP', '', {'label': 'Target CHOP (tx ty tz)'}),
            ('Calfixture', 'Str', '', {'label': 'Calibrate fixture'}),
            ('Calpan', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Measured pan 0..1'}),
            ('Caltilt', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Measured tilt 0..1'}),
            ('Calibrate', 'Pulse', None, {'label': 'Calibrate (at target)'}),
            ('Aimmissed', 'Int', 0, {'min': 0, 'max': 1000, 'label': 'Out of range (read)', 'ro': True}),
        ]),
        ('Sheet', [
            ('Mapmode', M, 'ownervalue', {'names': Lg['MAPMODES'], 'labels': ['Owner x value', 'Owner', 'Value heat'],
                                          'label': 'Map mode'}),
            ('Mapfirst', 'Int', 0, {'min': 0, 'max': 200, 'label': 'First row'}),
            ('Mapcount', 'Int', 16, {'min': 1, 'max': 200, 'label': 'Rows shown'}),
            ('Mapcell', 'Int', 6, {'min': 1, 'max': 16, 'label': 'Px per slot'}),
            ('Mapw', 'Int', 1024, {'min': 64, 'max': 4096, 'label': 'Map width'}),
            ('Maph', 'Int', 768, {'min': 64, 'max': 4096, 'label': 'Map height'}),
            ('Sheetname', 'Str', 'dmx_patch', {'label': 'Sheet name'}),
            ('Sheetdir', 'Folder', os.path.join(REPO, 'output', 'dmx'), {'label': 'Sheet folder'}),
            ('Exportsheet', 'Pulse', None, {'label': 'Export sheet (csv + md)'}),
        ]),
        ('Controls', [
            ('Resetdefaults', 'Pulse', None, {'label': 'Reset defaults'}),
        ]),
    ]


PANEL_PAGES = ['Source', 'Stage', 'View', 'Aim', 'Sheet', 'Controls']


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None:
                if o.get('ro'):
                    getattr(c.par, name).readOnly = True
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']      # slider range only: no clamps (no limits)
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
            elif style == 'COMP':
                p = page.appendCOMP(name, label=label)[0]
            elif style == 'CHOP':
                p = page.appendCHOP(name, label=label)[0]
            elif style == 'Folder':
                p = page.appendFolder(name, label=label)[0]
            else:
                continue
            p.default = default
            p.val = default
            if o.get('ro'):
                p.readOnly = True


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


NOTES = []


def _try(o, name, value=None, expr=None, menu_like=None):
    """Set a par; record misses (name or menu entry not on this build) in NOTES instead of failing."""
    p = getattr(o.par, name, None)
    if p is None:
        NOTES.append('%s.%s: no such par' % (o.name, name))
        return None
    try:
        if menu_like is not None:
            names = list(p.menuNames)
            hit = next((m for m in names if any(k == m.lower() for k in menu_like)), None) or \
                next((m for m in names if any(k in m.lower() for k in menu_like)), None)
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


def _table(c, name, cols):
    t = _mk(c, tableDAT, name)
    if t.numRows == 0 or not any(x.val for r in t.rows() for x in r):   # new (blank) table: header only
        t.clear()
        t.appendRow(cols)
    return t


def _script_chop(c, name, fn, what, per_frame=False, inp=None):
    s = _mk(c, scriptCHOP, name)
    cb = s.par.callbacks.eval()
    if cb is None or cb.name != name + '_callbacks':
        cb = c.op(name + '_callbacks') or _mk(c, textDAT, name + '_callbacks')
        s.par.callbacks = cb
    cb.text = SCRIPT_CB.format(name=name, what=what, fn=fn, setup=FRAME_SETUP if per_frame else '',
                               clock=FRAME_READ if per_frame else '')
    cb.dock = s
    s.par.setuppars.pulse()
    if per_frame and getattr(s.par, 'Frame', None) is not None:
        _expr(s.par.Frame, 'absTime.frame')
    if inp is not None:
        s.inputConnectors[0].connect(inp)
    return s


def _geo(c, name, sop_cls, sop_name, mat):
    g = _mk(c, geometryCOMP, name)
    for ch in list(g.children):              # a new Geometry COMP holds a default torus: ours is sop_name
        if ch.valid and ch.name != sop_name:
            _sd(ch)
    s = g.op(sop_name)
    if s is None or s.OPType != sop_cls.__name__:
        if s is not None:
            _sd(s)
        s = g.create(sop_cls, sop_name)
    s.render = s.display = True
    g.par.material = mat
    return g, s


def _instancing(g, chop, t=('tx', 'ty', 'tz'), r=None, s=None, colour_op=None, colour=None):
    g.par.instancing = True
    g.par.instanceop = chop
    g.par.instancetx, g.par.instancety, g.par.instancetz = t
    if r:
        g.par.instancerx, g.par.instancery, g.par.instancerz = r
    if s:
        g.par.instancesx, g.par.instancesy, g.par.instancesz = s
    if colour:
        _try(g, 'instancecolorop', colour_op or chop)
        _try(g, 'instancecolormode', menu_like=('replace',))
        g.par.instancer, g.par.instanceg, g.par.instanceb = colour


def _cmat(c, name, rgb, additive=False):
    m = _mk(c, constantMAT, name)
    m.par.colorr, m.par.colorg, m.par.colorb = rgb
    m.par.blending = bool(additive)
    if additive:
        _try(m, 'srcblend', menu_like=('one',))
        _try(m, 'destblend', menu_like=('one',))
        _try(m, 'depthwriting', False)
        _try(m, 'cullface', menu_like=('neither',))
    return m


def build(parent_path='/project1/lab', panel=True, dmx_path=None):
    del NOTES[:]
    Lg = _logic()
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('BK_dmx_patch: patch sheet + stage plot + previs + aim helper for BK_dmx_out (Dmxcomp). Reads its '
                 'patch/pixels/profiles tables and out3 universes; never writes it. Out: out1 previs TOP (render), '
                 'out2 address map TOP, out3 aim CHOP (<fx>.pan/.tilt 0..1 -> BK_dmx_out in2). Pulse Opencontrols.')
    was_open = _close_window(c)                                # T-70; zkit reopens it after the rebuild
    _pars(c, _pages(Lg))
    if dmx_path:
        c.par.Dmxcomp = dmx_path
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)

    # 1 Source + code
    dl = _mk(c, textDAT, 'dmx_logic')
    dl.text = open(DMX_LOGIC_FILE).read()
    dl.comment = 'Copy of builders/dmx_logic.py (BK_dmx_out logic: plan, profiles, aim). Rebuild to refresh.'
    pl = _mk(c, textDAT, 'patch_logic')
    pl.text = open(LOGIC_FILE).read()
    pl.comment = 'Pure logic = builders/dmx_patch_logic.py (tests: test/test_dmx_patch.py).'
    rt = _mk(c, textDAT, 'patch_rt')
    rt.text = open(RT_FILE).read()
    rt.comment = 'TD runtime = builders/dmx_patch_rt.py.'
    sw = _mk(c, datexecuteDAT, 'src_watch')
    sw.text = SRC_WATCH
    _expr(sw.par.dat, "op('patch_rt').module.source_dats()")
    sw.par.tablechange = True
    for k in ('rowchange', 'colchange', 'cellchange', 'sizechange'):
        _try(sw, k, False)
    dp = _mk(c, parameterexecuteDAT, 'dmx_pars')
    dp.text = DMX_PARS
    _expr(dp.par.op, "parent().par.Dmxcomp.eval() or ''")
    dp.par.pars = 'Colororder Univfilter Firstuniv'
    dp.par.custom = True
    dp.par.builtin = False
    dp.par.valuechange = True
    _try(dp, 'onpulse', False)
    uin = _mk(c, selectCHOP, 'univ_in')
    _expr(uin.par.chops, "op('patch_rt').module.univ_src()")
    uin.comment = 'Universes (u<flat> x 512) from Dmxcomp/out3, or Univchop (e.g. a DMX In CHOP; set Chanfmt).'

    # 2 Stage plot + sheet
    stage = _table(c, 'stage', Lg['STAGE_COLS'])
    stage.comment = ('Stage plot of record: name x y z (m) rx ry rz (deg, xyz order; hang = rx 180) group, '
                     'pan_zero tilt_off pan_dir tilt_dir (calibration). Edit freely; Sync/Arrange/Calibrate write it.')
    stw = _mk(c, datexecuteDAT, 'stage_watch')
    stw.text = STAGE_WATCH
    stw.par.dat = 'stage'
    stw.par.tablechange = True
    sheet = _table(c, 'sheet', Lg['SHEET_COLS'])
    sheet.comment = 'Patch sheet (generated, address order). Exportsheet writes it as csv + md.'
    rep = _mk(c, textDAT, 'report')
    rep.comment = 'Sync / Arrange / Check / Calibrate / Export results (reports only).'
    sett = _mk(c, parameterexecuteDAT, 'settings')
    sett.text = SETTINGS
    sett.par.op = c
    sett.par.pars = ' '.join(('Dmxcomp', 'Univchop', 'Chanfmt', 'Pixmax', 'Wallx', 'Wally', 'Wallz', 'Wallw', 'Wallh',
                              'Syncpatch', 'Prune', 'Applyarrange', 'Fit', 'Calibrate', 'Exportsheet', 'Checkpatch',
                              'Resetdefaults'))
    sett.par.custom = True
    sett.par.builtin = False
    sett.par.valuechange = True
    sett.par.onpulse = True
    tick = _mk(c, executeDAT, 'status_tick')
    tick.text = STATUS_TICK
    tick.par.frameend = True
    tick.par.active = True

    # 3 Decode (CPU, CHOP only)
    state = _script_chop(c, 'state', 'cook_state', 'per fixture: body + beam instance channels', inp=uin)
    ppos = _script_chop(c, 'pix_pos', 'cook_pix_pos', 'static pixel instance positions (re-cooked on plan change)')
    pcol = _script_chop(c, 'pix_col', 'cook_pix_col', 'pixel colours from the slot values', inp=uin)
    aim = _script_chop(c, 'aim', 'cook_aim', 'aim helper: <fx>.pan / <fx>.tilt 0..1 while Aimon', per_frame=True)

    # 4 Previs (Render TOP, instancing; no GLSL chain)
    mb = _cmat(c, 'mat_body', (1, 1, 1))
    mbeam = _cmat(c, 'mat_beam', (1, 1, 1), additive=True)
    mgrid = _mk(c, wireframeMAT, 'mat_grid')
    mgrid.par.colorr, mgrid.par.colorg, mgrid.par.colorb = 0.22, 0.22, 0.26
    fg, fs = _geo(c, 'fix_geo', sphereSOP, 'shape', mb)
    fs.par.rows, fs.par.cols = 8, 12
    fs.par.radx = fs.par.rady = fs.par.radz = 0.5
    _instancing(fg, state, s=('s', 's', 's'), colour=('cr', 'cg', 'cb'))
    _expr(fg.par.render, "op('state').numSamples > 0")
    bg, bs = _geo(c, 'beam_geo', tubeSOP, 'cone', mbeam)
    bs.par.orient = 'y'
    bs.par.height = 1.0
    bs.par.ty = 0.5                          # spans y 0..1: instance scale sl = length, origin at the fixture
    bs.par.rad1, bs.par.rad2 = 1.0, 0.02     # 31550 live: rad2 is the y 0 end (narrow end at the fixture)
    bs.par.rows, bs.par.cols = 2, 24
    _try(bs, 'cap', False)
    _instancing(bg, state, r=('rx', 'ry', 'rz'), s=('sr', 'sl', 'sr'), colour=('br', 'bg', 'bb'))
    _expr(bg.par.render, "parent().par.Beams.eval() and op('state').numSamples > 0")
    _try(bg, 'drawpriority', -1)
    pg, ps = _geo(c, 'pix_geo', boxSOP, 'dot', mb)
    ps.par.sizex = ps.par.sizey = ps.par.sizez = 1.0
    _instancing(pg, ppos, s=('s', 's', 's'), colour_op=pcol, colour=('r', 'g', 'b'))
    _expr(pg.par.render, "op('pix_pos').numSamples > 0")
    flg, fls = _geo(c, 'floor_geo', gridSOP, 'floor', mgrid)
    _try(fls, 'orient', menu_like=('zx',))
    fls.par.sizex, fls.par.sizey = 40, 40
    fls.par.rows, fls.par.cols = 41, 41
    _expr(flg.par.render, 'parent().par.Grid.eval()')
    cam = _mk(c, cameraCOMP, 'cam')
    for k in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz'):
        _expr(getattr(cam.par, k), "op('patch_rt').module.cam()[%r]" % k)
    _expr(cam.par.projection, "op('patch_rt').module.cam()['projection']")
    _expr(cam.par.orthowidth, "op('patch_rt').module.cam()['orthowidth']")
    _expr(cam.par.fov, "op('patch_rt').module.cam()['fov']")
    _expr(cam.par.far, "op('patch_rt').module.cam()['far']")
    cam.par.near = 0.05
    ren = _mk(c, renderTOP, 'render')
    ren.par.camera = 'cam'
    ren.par.geometry = 'floor_geo beam_geo fix_geo pix_geo'
    ren.par.lights = ''
    ren.par.outputresolution = 'custom'
    _expr(ren.par.resolutionw, 'parent().par.Resw.eval()')
    _expr(ren.par.resolutionh, 'parent().par.Resh.eval()')
    _try(ren, 'format', 'rgba16float')
    _try(ren, 'antialias', menu_like=('aa4', '4'))
    ren.par.bgcolorr, ren.par.bgcolorg, ren.par.bgcolorb = 0.02, 0.02, 0.025
    _try(ren, 'bgcolora', 1.0)
    out1 = _mk(c, outTOP, 'out1')
    out1.inputConnectors[0].connect(ren)

    # 5 Address map (one compute GLSL pass)
    own = _script_chop(c, 'owner', 'cook_owner', 'static owner id per slot, one channel per sent universe')
    otex = _mk(c, choptoTOP, 'owner_tex')
    otex.par.chop = own
    otex.par.dataformat = 'r'
    _try(otex, 'format', 'r32float')
    ltex = _mk(c, choptoTOP, 'live_tex')
    ltex.par.chop = uin
    ltex.par.dataformat = 'r'
    _try(ltex, 'format', 'r32float')
    am = _mk(c, glslTOP, 'addrmap')
    ad = c.op('addrmap_compute') or _mk(c, textDAT, 'addrmap_compute')
    ad.text = open(ADDRMAP_FILE).read()
    am.par.mode = 'compute'
    am.par.computedat = ad
    for dk in list(am.docked):               # a new GLSL TOP docks its own pixel/compute/info DATs: ours is addrmap_compute
        if dk.valid and dk.name != 'addrmap_compute' and dk.name.endswith(('_pixel', '_compute', '_vertex')):
            _sd(dk)
    ad.dock = am
    am.par.outputresolution = 'custom'
    am.par.format = 'rgba8fixed'
    _try(am, 'inputextenduv', 'zero')
    am.inputConnectors[0].connect(otex)
    am.inputConnectors[1].connect(ltex)
    _expr(am.par.resolutionw, 'parent().par.Mapw.eval()')
    _expr(am.par.resolutionh, 'parent().par.Maph.eval()')
    am.seq.vec.numBlocks = max(3, am.seq.vec.numBlocks)
    lay = "op('patch_rt').module.map_layout()"
    U = [('uMon', [lay + '[0]', 'parent().par.Mapcell.eval()', 'parent().par.Mapfirst.eval()', lay + '[2]']),
         ('uOpt', ['parent().par.Mapmode.menuIndex', 'parent().par.Mapw.eval()', 'parent().par.Maph.eval()',
                   "op('patch_rt').module.sel_owner()"]),
         ('uInfo', ["op('patch_rt').module.nfix()", '0', '0', '0'])]
    for k, (un, ex) in enumerate(U):
        getattr(am.par, 'vec{}name'.format(k)).val = un
        for comp_, e in zip('xyzw', ex):
            _expr(getattr(am.par, 'vec{}value{}'.format(k, comp_)), e)
    out2 = _mk(c, outTOP, 'out2')
    out2.inputConnectors[0].connect(am)
    out3 = _mk(c, outCHOP, 'out3')
    out3.inputConnectors[0].connect(aim)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True

    rtm = rt.module
    rtm.S['plan'] = None                     # fresh module text: plan from the current tables
    if c.par.Autosync.eval() and rtm.dmx() is not None:
        rtm.sync(False)                      # writes `stage` (new fixtures placed) + sheet; callbacks only
    else:
        rtm.replan(write=True)

    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=52, cols=8, open_window=was_open)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'settings', 'status_tick'],
         'body': 'zkit panel + window (pulse Opencontrols). settings = replan pars + pulses; status_tick = '
                 'read-only status pars every 30 frames.'},
        {'title': '1 Source', 'role': 'input',
         'ops': ['univ_in', 'src_watch', 'dmx_pars', 'dmx_logic', 'patch_logic', 'patch_rt'],
         'body': 'Reads BK_dmx_out (Dmxcomp): tables (src_watch, dmx_pars -> new plan) and out3 universes '
                 '(univ_in). Never writes it.'},
        {'title': '2 Stage plot + sheet', 'role': 'input', 'ops': ['stage', 'stage_watch', 'sheet', 'report'],
         'body': 'stage = positions / rotation / calibration per fixture (of record). sheet = generated patch '
                 'sheet; Exportsheet -> csv + md.'},
        {'title': '3 Decode', 'role': 'process',
         'ops': ['state', 'state_callbacks', 'pix_pos', 'pix_pos_callbacks', 'pix_col', 'pix_col_callbacks'],
         'body': 'DMX bytes -> what each fixture does: colour, intensity, beam direction (pan/tilt), pixel colours. '
                 'CHOP only, no TOP readback.'},
        {'title': '4 Previs', 'role': 'output',
         'ops': ['mat_body', 'mat_beam', 'mat_grid', 'fix_geo', 'beam_geo', 'pix_geo', 'floor_geo', 'cam', 'render',
                 'out1'],
         'body': 'Instanced fixtures, additive beam cones, pixel dots, floor grid; Front / Top / Side / Perspective '
                 'camera. out1.'},
        {'title': '5 Address map', 'role': 'output',
         'ops': ['owner', 'owner_callbacks', 'owner_tex', 'live_tex', 'addrmap', 'addrmap_compute', 'out2'],
         'body': 'Owner per slot (static) + live values -> ONE compute pass: fixture colour x value, conflicts red, '
                 'fixture starts white. out2.'},
        {'title': '6 Aim', 'role': 'output', 'ops': ['aim', 'aim_callbacks', 'out3'],
         'body': 'Aimon: pan/tilt for every matching moving head to hit Target -> out3 (<fx>.pan/.tilt 0..1) -> '
                 'wire into BK_dmx_out in2.'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay_ = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    return {'comp': c.path, 'dmx': c.par.Dmxcomp.eval().path if c.par.Dmxcomp.eval() is not None else None,
            'panel': info, 'notes': list(NOTES), 'layout': str(lay_)[:400]}
