"""Builder for the zctl control surface COMP (spec: docs/research/BE_rudiment_zerror.md, v1).

Run inside TD (e.g. through td_exec): exec this file's text, then build('/project1/lab').
Idempotent and T-70 safe: a rebuild updates the COMP in place (ops reused by name, nothing destroyed, own window closed
first and reopened after), so binds + presets tables, knob/lock values and Zctl settings stay; the code DATs are
refreshed from builders/zctl_logic.py + builders/zctl_ext.py on disk. The panel is refilled by ZCtl.RebuildUI.
Pure ASCII.
"""
import os

ZDIR = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
NAME = 'ZC_control_surface'

APPLY_TEXT = '''# Knob<n> changed -> write the bound target parameter; Lock<n> -> binds table
def onValueChange(par, prev):
\tif par.name.startswith('Knob'):
\t\tparent().Apply(par.name)
\telif par.name.startswith('Lock'):
\t\tparent().LockChanged(par)
\treturn
'''

ACTIONS_TEXT = '''# pulses on the Zctl page -> ZCtl extension
def onPulse(par):
\tz = parent()
\tn = par.name
\tif n == 'Store':
\t\tz.Store()
\telif n == 'Storenew':
\t\tz.Store(new=True)
\telif n == 'Recall':
\t\tz.Recall()
\telif n == 'Delete':
\t\tz.DeletePreset()
\telif n == 'Randomize':
\t\tz.Randomize()
\telif n == 'Bindselected':
\t\tz.BindSelected()
\telif n == 'Unbind':
\t\tz.Unbind(z.par.Unbindknob.eval())
\telif n == 'Clearbinds':
\t\tz.ClearBinds()
\telif n == 'Stopmorph':
\t\tz.StopMorph()
\telif n == 'Opencontrols':
\t\tz.OpenControls()
\treturn
'''

TICK_TEXT = '''# runs only while a morph is going (ZCtl turns this DAT active/inactive)
def onFrameStart(frame):
\tparent().Tick()
\treturn
'''

WATCH_TEXT = '''# any edit of the binds table (by hand or by code) drops ZCtl's parsed cache
def onTableChange(dat):
\tparent().Invalidate()
\treturn
'''

CTRL_TEXT = '''# control-in hook (MIDI mapper / any CHOP): a channel named Knob3, k3, 3 or a bind's src drives that knob (0-1)
def onValueChange(channel, sampleIndex, val, prev):
\tparent().CtrlIn(channel.name, val)
\treturn
'''


def _read(n):
    with open(os.path.join(ZDIR, n), 'r', encoding='utf-8') as f:
        return f.read()


def _mk(c, pg, kind, name, label):
    """Custom par on page pg: reused when it exists (rebuild in place), created otherwise. -> (par, created)."""
    if hasattr(c.par, name):
        p = c.par[name]
        p.label = label
        return p, False
    return getattr(pg, 'append' + kind)(name, label=label)[0], True


def _page(c, name):
    for pg in c.customPages:
        if pg.name == name:
            return pg
    return c.appendCustomPage(name)


def _pars(c):
    """Zctl + State pages, idempotent: existing pars keep their values (no page is destroyed on a rebuild)."""
    pg = _page(c, 'Zctl')
    new = []

    def mk(kind, name, label, **props):
        p, made = _mk(c, pg, kind, name, label)
        for k, v in props.items():
            setattr(p, k, v)
        if made:
            new.append(p)
        return p

    mk('Toggle', 'Active', 'Active (write targets)', default=True)
    mk('Float', 'Morphtime', 'Morph time (s)', min=0, normMin=0, normMax=30, clampMin=True, default=1.0)
    mk('Menu', 'Morphcurve', 'Morph curve', menuNames=['linear', 'ease', 'smooth'],
       menuLabels=['Linear', 'Ease', 'Smooth'])
    mk('Int', 'Activepreset', 'Preset slot', min=0, normMin=0, normMax=16, clampMin=True)
    mk('Pulse', 'Store', 'Store (slot; 0 = new)')
    mk('Pulse', 'Storenew', 'Store as new')
    mk('Pulse', 'Recall', 'Recall (morph)')
    mk('Pulse', 'Delete', 'Delete preset')
    mk('Pulse', 'Stopmorph', 'Stop morph')
    mk('Float', 'Randamount', 'Random amount', min=0, max=1, normMin=0, normMax=1, clampMin=True, clampMax=True,
       default=0.5)
    mk('Pulse', 'Randomize', 'Randomize')
    mk('Str', 'Bindpath', 'Bind op (or selection)')
    mk('Str', 'Bindpar', 'Bind pars (e.g. tx ty, *)')
    mk('Pulse', 'Bindselected', 'Bind selected')
    mk('Int', 'Unbindknob', 'Knob id', min=0, normMin=0, normMax=32, clampMin=True)
    mk('Pulse', 'Unbind', 'Unbind knob')
    mk('Pulse', 'Clearbinds', 'Clear binds')
    mk('Pulse', 'Opencontrols', 'Open controls')
    pg = _page(c, 'State')
    for kind, n, lb in (('Int', 'Nbinds', 'Binds'), ('Int', 'Npresets', 'Presets'), ('Toggle', 'Morphing', 'Morphing'),
                        ('Str', 'Lasterror', 'Last error')):
        mk(kind, n, lb).readOnly = True
    for p in new:
        if not p.readOnly and p.style != 'Pulse':
            p.val = p.default


def _get(c, typ, name):
    """Reuse the op called name when it is of type typ (rebuild in place, T-70: nothing a window/pane shows is
    destroyed); create it when missing. A same-named op of another type is renamed away and destroyed later."""
    o = c.op(name)
    if o is not None and isinstance(o, typ):
        return o
    if o is not None:
        o.name = name + '_old{}'.format(o.id)
        run('o = op({})\nif o is not None: o.destroy()'.format(int(o.id)), delayFrames=3, delayRef=op.TDResources)
    return c.create(typ, name)


def build(parent_path='/project1/lab', name=NAME, demo=True):
    """Create or update the COMP in place (T-70 safe): its own window is closed first, no op or page is destroyed,
    the binds/presets tables, knob/lock values and Zctl settings stay; code DATs are refreshed from disk."""
    host = op(parent_path)
    c = host.op(name)
    was_open = False
    if c is None:
        c = host.create(baseCOMP, name)
    else:
        w = c.op('controls_window')
        if w is not None and w.isOpen:
            was_open = True
            w.par.winclose.pulse()
    _pars(c)

    for n, cols in (('binds', ['id', 'knob', 'label', 'path', 'par', 'lo', 'hi', 'kind', 'menun', 'lock', 'src']),
                    ('presets', ['id', 'name', 'values'])):
        t = c.op(n)
        if t is None:
            t = c.create(tableDAT, n)
            t.clear()
            t.appendRow(cols)
    for n in ('zctl_logic', 'zctl_ext'):
        d = _get(c, textDAT, n)
        txt = _read(n + '.py')
        if d.text != txt:
            d.text = txt

    bw = _get(c, datexecuteDAT, 'binds_watch')
    bw.text = WATCH_TEXT
    bw.par.dat = 'binds'
    bw.par.tablechange = True
    for n in ('rowchange', 'colchange', 'cellchange', 'sizechange'):
        if hasattr(bw.par, n):
            bw.par[n] = False

    _get(c, inCHOP, 'in_ctrl')
    x = _get(c, chopexecuteDAT, 'ctrl_exec')
    x.text = CTRL_TEXT
    x.par.chop = 'in_ctrl'
    x.par.valuechange = True
    x.par.offtoon = x.par.ontooff = x.par.whileon = x.par.whileoff = False

    m = _get(c, executeDAT, 'morph_tick')
    m.text = TICK_TEXT
    m.par.framestart = True
    m.par.active = False

    a = _get(c, parameterexecuteDAT, 'apply_exec')
    a.text = APPLY_TEXT
    a.par.op = '..'
    a.par.pars = 'Knob* Lock*'
    a.par.valuechange = True
    a.par.onpulse = False
    a = _get(c, parameterexecuteDAT, 'actions_exec')
    a.text = ACTIONS_TEXT
    a.par.op = '..'
    a.par.pars = '*'
    a.par.valuechange = False
    a.par.onpulse = True

    k = _get(c, parameterCHOP, 'knob_vals')
    k.par.ops = '..'
    k.par.parameters = 'Knob*'
    k.par.custom = True
    k.par.builtin = False
    o = _get(c, outCHOP, 'out_values')
    if not o.inputs or o.inputs[0] != k:
        o.inputConnectors[0].connect(k)

    if demo:
        d = _get(c, constantCHOP, 'test_const')
        for j, nm in enumerate(('speed', 'gain', 'mix')):
            d.par['const{}name'.format(j)] = nm
        nz = _get(c, noiseTOP, 'test_noise')
        nz.par.outputresolution = 'custom'
        nz.par.resolutionw, nz.par.resolutionh = 1080, 1920

    ui_ = _get(c, containerCOMP, 'controls')  # kept: RebuildUI refills it (window closed, tile off meanwhile)
    if ui_.op('zk_rt') is None:  # a zkit panel sizes itself (RebuildUI then re-reads its pars)
        ui_.par.w, ui_.par.align = 420, 'verttb'
    w = _get(c, windowCOMP, 'controls_window')
    w.par.winop = 'controls'
    w.par.title = name + ' controls'
    w.par.winw = 440

    c.par.ext0object = "op('./zctl_ext').module.ZCtl(me)"
    c.par.ext0name = 'ZCtl'
    c.par.ext0promote = True
    c.initializeExtensions()
    c.par.opviewer.expr = "me.op('out_values')"
    c.viewer = True
    for n in ('controls', 'out_values', 'knob_vals', 'binds', 'presets'):
        c.op(n).viewer = True

    z = c.ext.ZCtl
    z.SyncPars()
    z._status()
    z.ApplyAll()
    z.RebuildUI(reopen=was_open)  # deferred, T-70 safe (see ZCtl.RebuildUI)
    layout(c)
    return c


STAGES = [
    {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window'],
     'body': 'autoUI panel of pages Zctl + Knobs; window opened by Opencontrols'},
    {'title': 'Data (plain tables + code)', 'ops': ['binds', 'binds_watch', 'presets', 'zctl_logic', 'zctl_ext'],
     'body': 'binds: one row per knob -> target op.par (binds_watch drops the parsed cache on edits); presets: json of knob values; ZCtl extension + pure logic'},
    {'title': 'Control in (MIDI hook)', 'role': 'input', 'ops': ['in_ctrl', 'ctrl_exec'], 'after': ['Data (plain tables + code)'],
     'body': 'wire any CHOP in: channel Knob3 / k3 / 3 or a bind src name sets that knob 0-1'},
    {'title': 'Morph + apply', 'role': 'process', 'ops': ['actions_exec', 'morph_tick', 'apply_exec'],
     'after': ['Control in (MIDI hook)'],
     'body': 'pulses -> ZCtl; morph_tick runs only while morphing; knob change -> target par'},
    {'title': 'Output', 'role': 'output', 'ops': ['knob_vals', 'out_values'], 'after': ['Morph + apply'],
     'body': 'one channel per knob, 0-1'},
]


def layout(c):
    st = [dict(s) for s in STAGES]
    if c.op('test_const') is not None:
        st.append({'title': 'Demo targets', 'ops': ['test_const', 'test_noise'], 'after': ['Morph + apply'],
                   'body': 'test pars to bind (const0value.., period, amp, mono)'})
    return op('/jazib_mcp/handlers').module.layout_stages(c, st, True, arrange='mixed')
