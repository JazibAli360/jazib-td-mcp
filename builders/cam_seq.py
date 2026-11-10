"""Builder for CS_cam_sequencer v2: a Camera COMP that stores and eases between camera presets (clean-room; research
docs/research/CS_camsequencer.md, how-to docs/builds/cs_cam_sequencer.md). TD 2025.31550.

Run inside TD (td_exec on a build TD):
    ns = dict(globals()); exec(open('<repo>/builders/cam_seq.py').read(), ns); ns['build']('/project1/lab')

The COMP IS the camera (cameraCOMP): drop it anywhere, set a Render TOP's Camera to it, activate its viewer,
navigate, Init / Append. Its custom pages, in order: Seq | Presets | About (the original's workflow and names),
then ours: Play | Clock | Shake | Look | Output. Everything inside refers to the COMP relatively (no /project1/...
path), the optional hooks are empty by default, presets live in the COMP's own two Table DATs, so a copy or a
library .tox drop is independent and works with no other COMP present.

Idempotent and T-70 safe: ops reused by name, the preset tables and par values survive a rebuild; the code DATs
are refreshed from builders/cam_seq_logic.py, cam_seq_rt.py, cam_rig_logic.py and menu_logic.py on disk. 0 GPU.
Upgrading the v1 Base COMP in place: builders/cam_seq_migrate.py. Pure ASCII.
"""
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
NAME = 'CS_cam_sequencer'
VERSION = '2.0.0'
LOGIC_FILE = os.path.join(HERE, 'cam_seq_logic.py')
RT_FILE = os.path.join(HERE, 'cam_seq_rt.py')
RIG_FILE = os.path.join(HERE, 'cam_rig_logic.py')
MENU_FILE = os.path.join(HERE, 'menu_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')


def _logic():
    import types
    rig = types.ModuleType('cam_rig_logic')
    exec(open(RIG_FILE).read(), rig.__dict__)
    ns = {'__name__': 'cam_seq_logic_build'}
    exec(open(LOGIC_FILE).read(), ns)
    ns['bind_rig'](rig)
    return ns


SRC = "me.op('cs_rt').module.menu(me, %r)"          # live dropdowns (T-233): items built on each menu read

SOLVE_CB = """# solve: one camera state per cook (cs_rt.cook). Never reads absTime here (T-143): Frame / Secs carry the
# clock and read it only while Tick is on (cs_rt turns Tick off when nothing moves: an idle sequencer = 0 cooks).
# Sel = parent().par.Select as a PAR expression: an expression-driven Select (absTime, a CHOP) makes the solve cook
# through TD's own dependency chain (reading Select inside the Python cook did not, T-257).
def onSetupParameters(scriptOp):
\tpg = None
\tfor p_ in scriptOp.customPages:
\t\tif p_.name == 'Clock':
\t\t\tpg = p_
\tpg = pg or scriptOp.appendCustomPage('Clock')
\tif getattr(scriptOp.par, 'Tick', None) is None:
\t\tpg.appendToggle('Tick', label='Tick (set by cs_rt)')
\t\tscriptOp.par.Tick = 1
\tif getattr(scriptOp.par, 'Frame', None) is None:
\t\tpg.appendFloat('Frame', label='Frame (clock, while Tick)')
\tif getattr(scriptOp.par, 'Secs', None) is None:
\t\tpg.appendFloat('Secs', label='Seconds (clock, while Tick)')
\tscriptOp.par.Frame.expr = 'absTime.frame if me.par.Tick else 0'
\tscriptOp.par.Frame.mode = ParMode.EXPRESSION
\tscriptOp.par.Secs.expr = 'absTime.seconds if me.par.Tick else 0'
\tscriptOp.par.Secs.mode = ParMode.EXPRESSION
\treturn

def onCook(scriptOp):
\t_f = scriptOp.par.Frame.eval()
\tparent().op('cs_rt').module.cook(parent(), scriptOp)
\treturn
"""

PEXEC = """# CS_cam_sequencer pulses + watched values -> cs_rt (one event per pulse, T-238). Select is NOT watched (an
# expression-driven Select would call Python every frame): the solve reads it itself.
def onPulse(par):
\tparent().op('cs_rt').module.on_pulse(parent(), par.name)
\treturn

def onValueChange(par, prev):
\tparent().op('cs_rt').module.on_value(parent(), par.name)
\treturn
"""

BIND_CB = """# Bind (write on change): cs_ver steps when the solve's state changed -> cs_rt writes the camera's pars
def onValueChange(channel, sampleIndex, val, prev):
\tparent().op('cs_rt').module.on_out(parent())
\treturn
"""

WATCH_DAT = """# a preset table edited (by hand, a pulse, the pop-up) -> cs_rt re-parses it on the next cook
def onTableChange(dat):
\tparent().op('cs_rt').module.tables_dirty(parent())
\treturn
"""

UI_EXEC = """# pop-up editor buttons -> cs_rt.ui_click
def onOffToOn(panelValue):
\tparent(2).op('cs_rt').module.ui_click(parent(2), panelValue.owner.name)
\treturn
"""

ABOUT = ('A Camera COMP that stores camera positions as presets and eases between them. Drop it in, set your Render '
         'TOP Camera to it, activate its viewer and navigate, then Init / Append. Set Xform > Look At to a Null to '
         'sequence its transform too. Drive Select (fraction = blend). Bind off = edit freely.')


def _pages(Lg):
    E, EL = Lg['EASE_NAMES'], Lg['EASE_LABELS']
    return [
        ('Seq', [
            ('Append', 'Pulse', None, {'label': 'Append'}),
            ('Replace', 'Pulse', None, {'label': 'Replace'}),
            ('Insert', 'Pulse', None, {'label': 'Insert'}),
            ('Remove', 'Pulse', None, {'label': 'Remove'}),
            ('Init', 'Pulse', None, {'label': 'Init'}),
            ('Override', 'Toggle', False, {'label': 'Ease Override'}),
            ('Easing', 'Menu', 'inOutSine', {'names': E, 'labels': EL, 'label': 'Easing'}),
            ('Splineinterp', 'Toggle', False, {'label': 'Spline Interpolation'}),
            ('Select', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Select'}),
            ('Length', 'Int', 0, {'min': 0, 'max': 64, 'label': 'Length', 'ro': True,
                                  'expr': "max(me.op('cam_presets').numRows - 1, 0)"}),
            ('Bind', 'Toggle', True, {'label': 'Bind'}),
        ]),
        ('Presets', [
            ('Opencampresets', 'Pulse', None, {'label': 'Open Cam Presets'}),
            ('Openlookatpresets', 'Pulse', None, {'label': 'Open Lookat Presets'}),
        ]),
        ('About', [
            ('Help', 'Str', ABOUT, {'label': 'About', 'ro': True}),
            ('Version', 'Str', VERSION, {'label': 'Version', 'ro': True}),
            ('Docs', 'Str', 'jazib-td-mcp docs/builds/cs_cam_sequencer.md', {'label': 'Docs', 'ro': True}),
            ('Status', 'Str', '', {'label': 'Status', 'ro': True}),
        ]),
        ('Play', [
            ('Playmode', 'Menu', 'manual', {'names': Lg['PLAYMODES'], 'labels': Lg['PLAYMODE_LABELS']}),
            ('Loopmode', 'Menu', 'loop', {'names': Lg['LOOPMODES'], 'labels': ['Loop', 'Ping-pong', 'Once']}),
            ('Quant', 'Float', 4.0, {'min': 0, 'max': 16, 'label': 'Quantise cuts (beats)'}),
            ('Defaulthold', 'Float', 8.0, {'min': 0.25, 'max': 64, 'label': 'Hold (beats)'}),
            ('Tdur', 'Float', 2.0, {'min': 0, 'max': 16, 'label': 'Transition (beats)'}),
            ('Trans', 'Menu', 'ease', {'names': Lg['TRANS'], 'labels': Lg['TRANS_LABELS'], 'label': 'Transition'}),
            ('Minhold', 'Float', 4.0, {'min': 0.25, 'max': 64, 'label': 'Random min hold'}),
            ('Maxhold', 'Float', 12.0, {'min': 0.25, 'max': 64, 'label': 'Random max hold'}),
            ('Seed', 'Int', 1, {'min': 0, 'max': 999, 'label': 'Random seed'}),
            ('Trignext', 'Pulse', None, {'label': 'Next'}),
            ('Trigprev', 'Pulse', None, {'label': 'Previous'}),
            ('Trigrandom', 'Pulse', None, {'label': 'Random'}),
            ('Trigcut', 'Pulse', None, {'label': 'Cut to selected'}),
            ('Gotopreset', 'StrMenu', '', {'label': 'Go to preset (any to any)', 'src': SRC % 'Gotopreset'}),
            ('Go', 'Pulse', None, {'label': 'Go (again)'}),
            ('Gotoblend', 'Menu', 'arc', {'names': Lg['TRANS'], 'labels': Lg['TRANS_LABELS'],
                                          'label': 'Go-to blend'}),
            ('Gototime', 'Float', 1.0, {'min': 0, 'max': 16, 'label': 'Go-to time (beats)'}),
            ('Gotoease', 'Menu', 'inOutSine', {'names': E[:-1], 'labels': EL[:-1], 'label': 'Go-to ease'}),
            ('Splinetension', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Spline amount'}),
            ('Shortrot', 'Toggle', False, {'label': 'Shortest rotation'}),
            ('Lag', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Select lag (s)'}),
            ('Customease', 'CHOP', '', {'label': 'Custom ease CHOP'}),
            ('Reset', 'Pulse', None, {'label': 'Reset playhead'}),
        ]),
        ('Clock', [
            ('Clockmode', 'Menu', 'internal', {'names': Lg['CLOCKS'], 'labels': Lg['CLOCK_LABELS']}),
            ('Bpm', 'Float', 120.0, {'min': 20, 'max': 300, 'label': 'BPM (internal / fallback)'}),
            ('Seek', 'Float', 0.0, {'min': 0, 'max': 256, 'label': 'Seek (beats, manual clock)'}),
            ('Beatsperbar', 'Int', 4, {'min': 1, 'max': 16, 'label': 'Beats per bar'}),
            ('Auop', 'COMP', '', {'label': 'AU_features COMP (optional)'}),
            ('Tlop', 'COMP', '', {'label': 'TL_timeline COMP (optional)'}),
        ]),
        ('Shake', [
            ('Shakeprofile', 'Menu', 'off', {'names': Lg['SHAKE_NAMES'], 'labels': Lg['SHAKE_LABELS']}),
            ('Shakeamount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Shake amount'}),
            ('Shakepos', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Position scale'}),
            ('Shakerot', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Rotation scale'}),
            ('Shakespeed', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Speed'}),
            ('Shakeseed', 'Int', 0, {'min': 0, 'max': 999, 'label': 'Seed'}),
            ('Shakebeat', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Beat kick'}),
            ('Shakeperlens', 'Toggle', False, {'label': 'Scale by FOV'}),
        ]),
        ('Look', [
            ('Targetmode', 'Menu', 'presets', {'names': Lg['TARGETMODES'], 'labels': Lg['TARGETMODE_LABELS']}),
            ('Targetop', 'Object', '', {'label': 'Global target op'}),
            ('Effop', 'COMP', '', {'label': 'Effectors COMP (optional)'}),
            ('Targeteff', 'StrMenu', ' ', {'label': 'Global target effector', 'src': SRC % 'Targeteff'}),
            ('Lookdamp', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Look damping (s)'}),
            ('Frame', 'Toggle', False, {'label': 'Frame the look point'}),
            ('Frameradius', 'Float', 1.0, {'min': 0.01, 'max': 20, 'label': 'Frame radius'}),
            ('Framepad', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Frame padding'}),
            ('Roll', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Roll offset'}),
            ('Fovoffset', 'Float', 0.0, {'min': -60, 'max': 60, 'label': 'FOV offset'}),
        ]),
        ('Output', [
            ('Resx', 'Int', 1080, {'min': 16, 'max': 8192, 'label': 'Frame width (framing aspect)'}),
            ('Resy', 'Int', 1920, {'min': 16, 'max': 8192, 'label': 'Frame height (framing aspect)'}),
            ('Outchop', 'Str', 'out1: cs_tx..cs_fov cs_la_tx..cs_la_pz cs_select cs_preset cs_progress cs_blend '
                               'cs_cut cs_goto cs_beats cs_bar cs_shake cs_dist cs_haslook cs_ver',
             {'label': 'Out CHOP channels', 'ro': True}),
            ('Opencontrols', 'Pulse', None, {'label': 'Open controls (zkit, optional)'}),
        ]),
    ]


NOT_WATCHED = ('Select', 'Length', 'Help', 'Version', 'Docs', 'Status', 'Outchop')


def _pars(c, pages):
    """Create pages / pars once; existing values kept (a menu that grew gets its new items, T-190)."""
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            label = o.get('label', name)
            have = getattr(c.par, name, None)
            if have is not None:
                if style == 'Menu' and list(have.menuNames) != list(o['names']):
                    have.menuNames, have.menuLabels = o['names'], o['labels']
                if style == 'StrMenu' and have.menuSource != o['src']:
                    have.menuSource = o['src']
                if o.get('expr') and have.expr != o['expr']:
                    have.expr = o['expr']
                    have.mode = ParMode.EXPRESSION
                if o.get('ro') and style == 'Str' and default is not None and name != 'Status':
                    have.readOnly = False
                    have.val = default
                    have.readOnly = True
                continue
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style == 'StrMenu':
                p = page.appendStrMenu(name, label=label)[0]
                p.menuSource = o['src']
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            else:
                p = getattr(page, 'append' + style)(name, label=label)[0]
                if 'min' in o:
                    p.normMin, p.normMax = o['min'], o['max']
            if default is not None:
                p.default = default
                p.val = default
            if o.get('expr'):
                p.expr = o['expr']
                p.mode = ParMode.EXPRESSION
            if o.get('ro'):
                p.readOnly = True
    order = [pg for pg, _p in pages]
    try:
        c.sortCustomPages(*(order + [pg.name for pg in c.customPages if pg.name not in order]))
    except Exception:
        pass


def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _mk(c, cls, name, viewer=True):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    if o.name != name:                               # buttonCOMP came back as 'b_up1' from create(..., 'b_up') (T-259)
        o.name = name
    o.viewer = viewer
    return o


def _text(c, name, path, comment):
    d = _mk(c, textDAT, name)
    t = open(path).read()
    if d.text != t:
        d.text = t
    d.comment = comment
    return d


def _table(c, name, cols, comment):
    t = _mk(c, tableDAT, name)
    if t.numRows < 1 or t[0, 0] is None or t[0, 0].val != '#':
        t.clear()
        t.appendRow(cols)
    t.comment = comment
    return t


def _watch(c, name, dat):
    w = _mk(c, datexecuteDAT, name)
    w.text = WATCH_DAT
    w.par.dat = dat
    w.par.tablechange = True
    w.par.active = True
    return w


def _solve_pars(so):
    """The solve's own clock pars (same as its onSetupParameters): Tick, Frame, Secs, Sel."""
    pg = next((p for p in so.customPages if p.name == 'Clock'), None) or so.appendCustomPage('Clock')
    if getattr(so.par, 'Tick', None) is None:
        pg.appendToggle('Tick', label='Tick (set by cs_rt)')
        so.par.Tick = 1
    for n, lab, ex in (('Frame', 'Frame (clock, while Tick)', 'absTime.frame if me.par.Tick else 0'),
                       ('Secs', 'Seconds (clock, while Tick)', 'absTime.seconds if me.par.Tick else 0'),
                       ('Sel', 'Select (follows the COMP)', 'parent().par.Select')):
        if getattr(so.par, n, None) is None:
            pg.appendFloat(n, label=lab)
        p = getattr(so.par, n)
        if p.expr != ex or p.mode != ParMode.EXPRESSION:
            p.expr = ex
            p.mode = ParMode.EXPRESSION


BUTTONS = [('b_rowm', 'Row -'), ('b_rowp', 'Row +'), ('b_up', 'Up'), ('b_down', 'Down'), ('b_add', 'Add current'),
           ('b_dup', 'Dup'), ('b_del', 'Delete'), ('b_sort', 'Sort #'), ('b_close', 'Close')]


def _popup(c):
    """Pop-up table editor (Presets page): a Window COMP showing presets_ui = a button row + an interactive OP
    Viewer of the chosen table (click a cell to edit it). Panels cook only while the window is open (0 GPU)."""
    W, H, BH = 900, 460, 30
    ui = _mk(c, containerCOMP, 'presets_ui', viewer=False)
    ui.par.w, ui.par.h = W, H
    pg = next((p for p in ui.customPages if p.name == 'Editor'), None) or ui.appendCustomPage('Editor')
    if getattr(ui.par, 'Table', None) is None:
        pg.appendStr('Table', label='Table')
        ui.par.Table = 'cam_presets'
    if getattr(ui.par, 'Row', None) is None:
        pg.appendInt('Row', label='Row')
    keep = set(n for n, _l in BUTTONS) | {'lbl', 'lbl_callbacks', 'table_view', 'ui_exec'}
    for ch in list(ui.children):
        if ch.valid and ch.name not in keep:
            _sd(ch)                                  # strays (e.g. auto-numbered buttons of an older build)
    bw = int((W - 220) / len(BUTTONS))
    for k, (nm, lab) in enumerate(BUTTONS):
        b = _mk(ui, buttonCOMP, nm, viewer=False)
        b.par.label = lab
        b.par.buttontype = 'momentary'
        b.par.x, b.par.y, b.par.w, b.par.h = 220 + k * bw, H - BH, bw - 2, BH
    lbl = _mk(ui, textCOMP, 'lbl', viewer=False)
    lbl.par.x, lbl.par.y, lbl.par.w, lbl.par.h = 4, H - BH, 212, BH
    if getattr(lbl.par, 'text', None) is not None:
        lbl.par.text = 'Cam   row #0'
    ov = _mk(ui, opviewerCOMP, 'table_view', viewer=False)
    ov.par.opviewer = '../' + ui.par.Table.eval()
    ov.par.interactive = True
    ov.par.x, ov.par.y, ov.par.w, ov.par.h = 0, 0, W, H - BH - 4
    ex = _mk(ui, panelexecuteDAT, 'ui_exec', viewer=False)
    ex.text = UI_EXEC
    ex.par.panels = ' '.join(n for n, _l in BUTTONS)
    ex.par.offtoon = True
    ex.par.active = True
    ui.comment = 'Pop-up editor: Row -/+ picks the row; Up / Down / Dup / Delete / Add current / Sort # edit the shown table.'
    w = _mk(c, windowCOMP, 'presets_window', viewer=False)
    w.par.winop = 'presets_ui'
    w.par.winw, w.par.winh = W, H
    w.par.size = 'custom' if 'custom' in w.par.size.menuNames else w.par.size.eval()
    w.comment = 'Opened by Presets > Open Cam Presets / Open Lookat Presets.'
    return ui, w


def build(parent_path='/project1/lab', name=NAME, panel=False, layout=True):
    """Build or refresh the Camera COMP `name` in parent_path. A non-camera op of that name is refused (use
    builders/cam_seq_migrate.py for the v1 Base COMP)."""
    Lg = _logic()
    pp = op(parent_path)
    c = pp.op(name)
    if c is not None and c.OPType != 'cameraCOMP':
        raise ValueError('%s is a %s, not a Camera COMP: run cam_seq_migrate.cs_migrate first' % (c.path, c.OPType))
    if c is None:
        c = pp.create(cameraCOMP, name)
        c.allowCooking = False                       # parked while it is put together (T-252 / T-254)
    c.comment = ('CS_cam_sequencer %s: a Camera COMP that eases between camera presets (clean-room). Render TOP '
                 'Camera = this COMP. Seq: Init / Append / Replace / Insert / Remove, Easing, Ease Override, Spline, '
                 'Select, Bind. Look At (Xform) = a Null to sequence it too. docs/builds/cs_cam_sequencer.md'
                 % VERSION)
    for wn in ('presets_window', 'controls_window'):
        w = c.op(wn)
        if w is not None and w.OPType == 'windowCOMP' and w.isOpen:
            w.par.winclose.pulse()
    _pars(c, _pages(Lg))

    # Data
    _table(c, 'cam_presets', ['#', 'EASE'] + Lg['CAM_PARS'],
           'Camera presets: # (row), EASE (the curve INTO this preset; blank = Easing), the camera\'s own pars '
           'tx ty tz rx ry rz sx sy sz px py pz fov. Edit here or in the pop-up (Presets page).')
    _table(c, 'lookat_presets', ['#', 'EASE'] + Lg['LOOK_PARS'],
           'Look At presets: the Look At op\'s transform per row (row k goes with camera preset k; moves in the '
           'pop-up are per table, as the original). Used when Xform > Look At is set.')
    _watch(c, 'cam_watch', 'cam_presets')
    _watch(c, 'look_watch', 'lookat_presets')
    cfg = _mk(c, tableDAT, 'cs_cfg')
    cfg.clear()
    cfg.appendRows([['key', 'value'], ['zkit', ZKIT_FILE], ['version', VERSION]])
    cfg.comment = 'Build info. zkit = where Opencontrols finds the optional panel builder (missing = no panel).'
    _text(c, 'cam_rig_logic', RIG_FILE, 'Lifted camera maths (copy of builders/cam_rig_logic.py).')
    _text(c, 'cs_logic', LOGIC_FILE, 'Pure sequencer logic (copy of builders/cam_seq_logic.py, tests test_cam_seq.py).')
    _text(c, 'menu_logic', MENU_FILE, 'Live dropdown items (copy of builders/menu_logic.py, T-233).')
    rt = _text(c, 'cs_rt', RT_FILE, 'TD runtime: edits, pop-up, menus, clock, targets, cook, Bind (builders/cam_seq_rt.py).')
    rt.module.STATE.pop(c.id, None)

    # Inputs + solve
    in1 = _mk(c, inCHOP, 'in1')
    in1.comment = 'Optional drives: select, preset (go to on change), next / prev / random / kick (rising edge), beats.'
    so = _mk(c, scriptCHOP, 'solve')
    cb = _mk(c, textDAT, 'solve_callbacks')
    cb.text = SOLVE_CB
    so.par.callbacks = 'solve_callbacks'
    _solve_pars(so)                                  # made here, not by setuppars: a parked COMP's callbacks DAT
    #                                                  may still hold its old module (T-258)
    so.inputConnectors[0].connect(in1)
    so.comment = 'One camera state per cook -> cs_* channels. Cooks only on a change or while something moves (Tick).'
    nul = _mk(c, renameCHOP, 'cs_out')
    nul.inputConnectors[0].connect(so)
    nul.par.renamefrom = 'chan*'
    nul.par.renameto = ' '.join(Lg['out_names']())
    nul.comment = 'Names the solve channels cs_* (the solve writes them in one numpy call).'
    o1 = _mk(c, outCHOP, 'out1')
    o1.inputConnectors[0].connect(nul)
    bd = _mk(c, chopexecuteDAT, 'cs_bind')
    bd.text = BIND_CB
    bd.par.chop = 'cs_out'
    bd.par.channel = 'cs_ver'
    bd.par.valuechange = True
    for k in ('offtoon', 'whileon', 'ontooff', 'whileoff'):
        if getattr(bd.par, k, None) is not None:
            setattr(bd.par, k, False)
    bd.par.active = True
    bd.comment = 'Bind = write on change: when cs_ver steps, cs_rt writes the camera pars (+ the Look At op).'

    # Controls
    pe = _mk(c, parameterexecuteDAT, 'cs_pexec')
    pe.text = PEXEC
    pe.par.op = '..'
    names = [n for _pg, ps in _pages(Lg) for (n, _s, _d, _o) in ps if n not in NOT_WATCHED]
    pe.par.pars = ' '.join(names + ['lookat', 'rord'])
    pe.par.custom, pe.par.builtin, pe.par.valuechange, pe.par.onpulse = True, True, True, True
    _popup(c)

    if c.par.Bind.eval():
        rt.module.bind(c, True)

    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=['Seq', 'Play', 'Clock', 'Shake', 'Look'], d=56, cols=8)

    lay = None
    if layout:
        stages = [
            {'title': '1 Presets', 'role': 'input', 'ops': ['cam_presets', 'lookat_presets', 'cam_watch', 'look_watch',
                                                            'cs_cfg', 'in1'],
             'body': 'cam_presets = the camera\'s pars per row (+ EASE into it); lookat_presets = the Look At op\'s. '
                     'in1 = optional CHOP drives.'},
            {'title': '2 Solve', 'role': 'process', 'ops': ['cam_rig_logic', 'cs_logic', 'menu_logic', 'cs_rt', 'solve',
                                                             'solve_callbacks'],
             'body': 'One state per cook: Select scrub / sequence / beat / random, go-to, eases, spline, look target, '
                     'framing, shake. Idle = 0 cooks.'},
            {'title': '3 Output + Bind', 'role': 'output', 'ops': ['cs_out', 'out1', 'cs_bind'],
             'body': 'out1 CHOP cs_*. cs_bind writes the camera\'s own pars (Bind on) when the state changes.'},
            {'title': 'Controls', 'role': 'control', 'ops': ['cs_pexec', 'presets_ui', 'presets_window', 'controls',
                                                             'controls_window'],
             'body': 'Pulses -> cs_rt. Pop-up preset editor (Presets page). Optional zkit panel (Opencontrols).'},
        ]
        for s_ in stages:
            s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
        stages = [s_ for s_ in stages if s_['ops']]
        try:
            lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
        except Exception as e:
            lay = 'layout skipped: %s' % e
    rt.module.poke(c)
    return {'comp': c.path, 'type': c.OPType, 'parked': not c.allowCooking, 'panel': str(info)[:200],
            'layout': str(lay)[:200]}


def relative_check(c):
    """Every par of every op inside c that names an op by an ABSOLUTE path inside c (would break on copy / drop)."""
    bad = []
    root = c.path + '/'
    for o in [c] + list(c.findChildren()):
        for p in o.pars():
            try:
                s = p.expr if p.mode == ParMode.EXPRESSION else str(p.val)
            except Exception:
                continue
            if isinstance(s, str) and (root in s or s == c.path):
                bad.append('%s:%s=%s' % (o.path, p.name, s[:80]))
    return bad
