# show_rig builder - /project1/show_rig: the MASTER SHOW RIG. A td_layer_mixer (N layers over a bank of the lab's
# look COMPs) + master FX inserts BY REFERENCE (the lab's FX_palette_map / FX_motion_trail / FX_strobe, fed through
# send Select TOPs in /project1/lab) + look presets (fades) + hooks: CQ_cuelist (cue table actions), MIDI_mapper
# (bindable pars, register/unregister), BP_io_router (rig out -> router local input, Syphon 'jazib-td master', OFF).
# Logic: builders/show_rig_logic.py (offline tests test/test_show_rig.py). Doc: docs/builds/show_rig.md.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/show_rig.py').read(), ns); ns['build']()
# Idempotent: the mixer handler is re-run (keeps par values), our runtime/exec texts re-written, tables kept.
# Cook guard (T-86 / lanes): the bank is given to the mixer as Out TOP paths (not COMPs), so the handler's own
# guard never touches allowCooking; ours (rig_logic.cook_plan) wakes what a visible layer / live insert needs and
# parks only what IT woke, never a lane's COMP (logs/active_lanes.json), never a top-level COMP.
# T-70: controls_window closed before the rebuild, nothing destroyed directly. No functions in storage (T-67).
# Network traffic: none. Router sinks stay off (O<n>active False); the rig never turns a sender on. ASCII only.
import os

NAME = 'show_rig'
PARENT = '/project1'
LAB = '/project1/lab'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
LOGIC_FILE = os.path.join(HERE, 'show_rig_logic.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
LAYERS = 6
# bank order = source index (cue rows resolve by name at build time); missing ones are skipped
LOOKS = ['TP_test_pattern', 'LK_spectrum_glass', 'LK_projection_room', 'LK_typecore', 'BO_particles', 'BN_fluid2d',
         'BN_cloth', 'BL_cloud_morph', 'BL_splat_render', 'LY_lyrics_feed', 'BJ_urdu_type', 'PV_previz_stage',
         'DC_depth_cam', 'TL_timeline', 'GN_reaction_diffusion', 'CV_person_mask', 'AU_db_meter']
SYPHON_NAME = 'jazib-td master'

RIG_RT = r'''# show_rig runtime (builders/show_rig.py): cook guard, presets + fades, hooks. Logic in rig_logic.
# Called by guard_exec (custom par change / pulse) and rig_tick (per frame: fades, 1 s re-sync, T-100).
import json
import os
LANES = '%(lanes)s'
STATUS = ('Activesources', 'Cookingnow', 'Presetname', 'Rigstatus')
_C = {'mt': None, 'lanes': []}


def L():
    return op('rig_logic').module


def lanes():
    try:
        mt = os.path.getmtime(LANES)
        if mt != _C['mt']:
            _C['lanes'] = sorted(json.load(open(LANES)).keys())
            _C['mt'] = mt
    except Exception:
        pass
    return _C['lanes']


def nlayers(c):
    return int(c.fetch('jz_layers', 0, search=False))


def bank(c):
    """[(index, label, top_path, comp_path)] from the sources table (tops given to the mixer)."""
    t = c.op('sources')
    out = []
    for r in range(1, t.numRows):
        top = t[r, 'top'].val
        o = op(top)
        comp = o.parent() if o is not None else None
        out.append((int(t[r, 'index'].val), t[r, 'label'].val, top, comp.path if comp is not None else ''))
    return out


def labels(c):
    return [b[1] for b in bank(c)]


def layers(c):
    p = c.par
    return [{'source': p['L%%dsource' %% n].menuIndex, 'opacity': p['L%%dopacity' %% n].eval(),
             'blend': p['L%%dblend' %% n].eval(), 'mute': bool(p['L%%dmute' %% n].eval()),
             'solo': bool(p['L%%dsolo' %% n].eval())} for n in range(1, nlayers(c) + 1)]


def state(c):
    lg = L()
    return {'layers': layers(c), 'Master': c.par.Master.eval(), 'Masterfx': bool(c.par.Masterfx.eval()),
            'fx': dict((k, bool(c.par[lg.FX_PAR[k]].eval())) for k in lg.FX_ORDER)}


def fx_comp(c, k):
    return c.par['Fx%%scomp' %% k].eval()


def _set(p, v):
    if p is not None and p.eval() != v:
        p.val = v


def eff(c, n):                       # td_layer_mixer API kept
    return L().effective(layers(c))[n - 1]


def active_sources(c):               # td_layer_mixer API kept (indices a visible layer shows)
    return L().shown_sources(layers(c))


def apply(c):
    """Cook guard. Master is ignored on purpose: a master blackout keeps the shown looks warm."""
    lg = L()
    mode = c.par.Guardmode.eval() if c.par.Cookguard.eval() else 'off'
    b = bank(c)
    shown = set(lg.shown_sources(layers(c)))
    live_fx = lg.fx_live(c.par.Masterfx.eval(), dict((k, c.par[lg.FX_PAR[k]].eval()) for k in lg.FX_ORDER))
    cands, wanted = {}, []
    for k, _lab, _top, comp in b:
        o = op(comp) if comp else None
        if o is None or o is c or o.path.count('/') <= 1:
            continue
        cands[o.path] = bool(o.allowCooking)
        if k in shown:
            wanted.append(o.path)
    for k in lg.FX_ORDER:
        o = fx_comp(c, k)
        if o is None:
            continue
        cands[o.path] = bool(o.allowCooking)
        if k in live_fx:
            wanted.append(o.path)
    prot = lanes() if c.par.Protectlanes.eval() else []
    owned = list(c.fetch('sr_owned', [], search=False))
    wake, park, owned = lg.cook_plan(cands, wanted, owned, prot, mode)
    for p in wake:
        op(p).allowCooking = True
    for p in park:
        op(p).allowCooking = False
    c.store('sr_owned', owned)
    fx_sources(c, live_fx, prot)
    lab = dict((x[0], x[1]) for x in b)
    eff_ = lg.effective(layers(c))
    txt = ' | '.join('L%%d %%s %%.2f' %% (n + 1, lab.get(l['source'], '?'), e)
                     for n, (l, e) in enumerate(zip(layers(c), eff_)) if e > 0) or '(nothing visible)'
    if live_fx:
        txt += ' | FX ' + '>'.join(live_fx)
    _set(c.par.Activesources, txt)
    _set(c.par.Cookingnow, ' '.join(sorted(p.rsplit('/', 1)[-1] for p in cands if op(p).allowCooking)))
    return {'wake': wake, 'park': park, 'owned': owned, 'wanted': wanted}


def fx_sources(c, live_fx, prot):
    """A live insert switches its FX COMP's own source par to the rig's send (remembered, restored when off).
    A lane's COMP is never touched."""
    lg = L()
    prev = dict(c.fetch('sr_fxprev', {}, search=False))
    for k in lg.FX_ORDER:
        o = fx_comp(c, k)
        if o is None or o.path in prot:
            continue
        pn, val = lg.FX_SOURCE[k]
        p = getattr(o.par, pn, None)
        if p is None or val not in (p.menuNames or []):
            continue
        if k in live_fx:
            if k not in prev:
                prev[k] = p.eval()
            _set(p, val)
        elif k in prev:
            _set(p, prev.pop(k))
    c.store('sr_fxprev', prev)


# ---------------------------------------------------------------- presets
def preset_rows(c):
    t = c.op('presets')
    return [[x.val for x in t.row(r)] for r in range(t.numRows)]


def recall(c, idx=None, dur=None):
    lg = L()
    rows = preset_rows(c)
    idx = int(c.par.Preset.eval()) if idx is None else int(idx)
    if not 1 <= idx < len(rows):
        _set(c.par.Rigstatus, 'preset %%d: no such row' %% idx)
        return None
    tgt, errs = lg.row_to_state(rows[0], rows[idx], labels(c), nlayers(c))
    disc, fade = lg.fade_plan(state(c), tgt, nlayers(c))
    for k, v in disc.items():
        p = c.par[k]
        if k.endswith('source'):
            p.menuIndex = int(v)
        else:
            p.val = v
    dur = float(c.par.Presetfade.eval()) if dur is None else float(dur)
    if dur > 0 and fade:
        c.store('sr_fade', {'fade': dict((k, list(v)) for k, v in fade.items()), 't0': absTime.seconds,
                            'dur': dur, 'cv': c.par.Presetcurve.eval()})
    else:
        c.unstore('sr_fade')
        for k, v in lg.fade_values(fade, 0, 0).items():
            c.par[k].val = v
    _set(c.par.Presetname, rows[idx][0])
    _set(c.par.Rigstatus, 'recall %%s%%s' %% (rows[idx][0], (' (' + '; '.join(errs) + ')') if errs else ''))
    apply(c)
    return {'disc': disc, 'fade': fade, 'errors': errs}


def store(c):
    lg = L()
    t = c.op('presets')
    idx = int(c.par.Preset.eval())
    name = c.par.Storename.eval().strip() or ('preset%%d' %% max(idx, t.numRows))
    row = lg.state_to_row(name, state(c), labels(c))
    if 1 <= idx < t.numRows:
        for j, v in enumerate(row):
            t[idx, j] = v
    else:
        t.appendRow(row)
        idx = t.numRows - 1
    _set(c.par.Rigstatus, 'stored %%s at %%d' %% (name, idx))
    return idx


def tick(c):
    f = c.fetch('sr_fade', None, search=False)
    if f is not None:
        lg = L()
        t = absTime.seconds - f['t0']
        vals = lg.fade_values(dict((k, tuple(v)) for k, v in f['fade'].items()), t, f['dur'], f['cv'])
        for k, v in vals.items():
            c.par[k].val = v
        if t >= f['dur']:
            c.unstore('sr_fade')
    if absTime.frame %% 60 == 0:     # T-100: re-sync (a Parameter Execute misses changes made while parked)
        apply(c)


# ---------------------------------------------------------------- hooks
def hook_cq(c):
    q = c.par.Cuelist.eval()
    if q is None:
        return 'no Cuelist COMP'
    on = bool(c.par.Hookcq.eval())
    h = dict(c.fetch('sr_cq', {}, search=False))
    if on:
        if 'prev' not in h:
            h['prev'] = q.par.Cuetable.eval().path if q.par.Cuetable.eval() is not None else ''
            h['woke'] = not q.allowCooking
        q.par.Cuetable = c.op('rig_cues').path
        q.allowCooking = True
        q.par.Reloadcues.pulse()
    elif h:
        q.par.Cuetable = h.get('prev', '')
        q.par.Reloadcues.pulse()
        if h.get('woke') and q.path not in lanes():
            q.allowCooking = False
        h = {}
    c.store('sr_cq', h)
    return 'cq hooked' if on else 'cq unhooked'


def hook_router(c):
    r = c.par.Router.eval()
    if r is None:
        return 'no Router COMP'
    k = int(c.par.Routerslot.eval())
    o = int(c.par.Routersink.eval())
    h = dict(c.fetch('sr_router', {}, search=False))
    names = ('S%%dkind' %% k, 'O%%dkind' %% o, 'O%%dname' %% o, 'O%%dsrc' %% o)
    if c.par.Hookrouter.eval():
        if 'prev' not in h:
            h['prev'] = dict((n, r.par[n].eval()) for n in names)
        for n, v in zip(names, ('local', 'syphon', c.par.Syphonname.eval(), 's%%d' %% k)):
            _set(r.par[n], v)
        msg = 'router S%%d = local (rig out), O%%d = Syphon %%r, SEND stays %%s' %% (
            k, o, c.par.Syphonname.eval(), 'ON' if r.par['O%%dactive' %% o].eval() else 'off')
    else:
        for n, v in h.get('prev', {}).items():
            _set(r.par[n], v)
        h = {}
        msg = 'router restored'
    c.store('sr_router', h)
    return msg


def midi(c, on):
    m = c.par.Midimapper.eval()
    if m is None or m.op('runtime') is None:
        return 'no MIDI_mapper'
    h = dict(c.fetch('sr_midi', {}, search=False))
    if on and not m.allowCooking:              # a parked COMP's DAT modules do not compile; MIDI needs it cooking
        m.allowCooking = True
        h['woke'] = True
    rt = m.op('runtime').module
    binds = L().midi_binds(nlayers(c), c.path, int(c.par.Midibank.eval()), int(c.par.Midichannel.eval()),
                           int(c.par.Midicc0.eval()), int(c.par.Midinote0.eval()))
    if on:
        for b in binds:
            rt.put_mapping(m, b)
        c.store('sr_midi', h)
        return 'midi: %%d binds registered' %% len(binds)
    if not m.allowCooking:
        return 'midi: MIDI_mapper is parked (nothing to remove while it does not cook)'
    gone = rt.remove(m, [b['id'] for b in binds])
    if h.get('woke') and m.path not in lanes():
        m.allowCooking = False
    c.store('sr_midi', {})
    return 'midi: %%d binds removed' %% len(gone)


def on_value(c, par, prev):
    n = par.name
    if n in STATUS:
        return
    if n == 'Preset' and c.par.Autorecall.eval():
        recall(c)
        return
    if n == 'Hookcq':
        _set(c.par.Rigstatus, hook_cq(c))
    elif n in ('Hookrouter', 'Routerslot', 'Routersink', 'Syphonname'):
        _set(c.par.Rigstatus, hook_router(c))
    apply(c)


def on_pulse(c, par):
    n = par.name
    if n == 'Recall':
        recall(c)
    elif n == 'Store':
        store(c)
    elif n == 'Midiregister':
        _set(c.par.Rigstatus, midi(c, True))
    elif n == 'Midiunregister':
        _set(c.par.Rigstatus, midi(c, False))
    elif n == 'Resync':
        apply(c)
'''

GUARD = '''# show_rig: custom par change / pulse -> runtime (cook guard, presets, hooks). Written by builders/show_rig.py.
def onValueChange(par, prev):
    parent().op('runtime').module.on_value(parent(), par, prev)


def onPulse(par):
    parent().op('runtime').module.on_pulse(parent(), par)
'''

TICK = '''# show_rig: per frame -> runtime.tick (preset fades; 1 s cook-guard re-sync).
def onFrameStart(frame):
    parent().op('runtime').module.tick(parent())
'''


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


def _logic():
    ns = {}
    exec(open(LOGIC_FILE).read(), ns)
    return ns


def _pages(Lg):
    fx = []
    for k in Lg['FX_ORDER']:
        fx += [(Lg['FX_PAR'][k], 'Toggle', False, {'label': 'Insert %s' % k}),
               ('Fx%scomp' % k, 'COMP', Lg['FX_DEFAULT'][k], {'label': '%s COMP (reference)' % k})]
    return [
        ('Rig', [
            ('Preset', 'Int', 1, {'label': 'Preset (row)', 'min': 1, 'max': 64}),
            ('Autorecall', 'Toggle', True, {'label': 'Recall on Preset change'}),
            ('Recall', 'Pulse', None, {'label': 'Recall preset'}),
            ('Presetfade', 'Float', 1.0, {'label': 'Preset fade s', 'min': 0.0, 'max': 10.0}),
            ('Presetcurve', 'Menu', 'ease', {'names': list(Lg['CURVES']), 'labels': ['Linear', 'Ease', 'Smooth', 'Cut'],
                                             'label': 'Preset curve'}),
            ('Storename', 'Str', '', {'label': 'Store as name'}),
            ('Store', 'Pulse', None, {'label': 'Store preset (row Preset)'}),
            ('Presetname', 'Str', '', {'label': 'Preset name', 'ro': True}),
            ('Activesources', 'Str', '', {'label': 'Visible', 'ro': True}),
            ('Cookingnow', 'Str', '', {'label': 'Cooking (bank)', 'ro': True}),
            ('Rigstatus', 'Str', '', {'label': 'Last action', 'ro': True}),
        ]),
        ('FX', fx),
        ('Guard', [
            ('Guardmode', 'Menu', 'owned', {'names': list(Lg['GUARD_MODES']),
                                            'labels': ['Owned (park only what the rig woke)',
                                                       'Strict (park every unshown source)', 'Off (hands off)'],
                                            'label': 'Cook guard mode'}),
            ('Protectlanes', 'Toggle', True, {'label': 'Never park a live lane COMP'}),
            ('Resync', 'Pulse', None, {'label': 'Re-sync guard'}),
        ]),
        ('Hooks', [
            ('Cuelist', 'COMP', '/project1/lab/CQ_cuelist', {'label': 'CQ_cuelist'}),
            ('Hookcq', 'Toggle', False, {'label': 'CQ drives the rig (rig_cues)'}),
            ('Midimapper', 'COMP', '/project1/lab/MIDI_mapper', {'label': 'MIDI_mapper'}),
            ('Midibank', 'Int', 0, {'label': 'MIDI bank (0 = always)', 'min': 0, 'max': 16}),
            ('Midichannel', 'Int', 1, {'label': 'MIDI channel (0 = any)', 'min': 0, 'max': 16}),
            ('Midicc0', 'Int', 1, {'label': 'First fader CC', 'min': 0, 'max': 127}),
            ('Midinote0', 'Int', 36, {'label': 'First button note', 'min': 0, 'max': 127}),
            ('Midiregister', 'Pulse', None, {'label': 'Register MIDI binds'}),
            ('Midiunregister', 'Pulse', None, {'label': 'Remove MIDI binds'}),
            ('Router', 'COMP', '/project1/lab/BP_io_router', {'label': 'BP_io_router'}),
            ('Hookrouter', 'Toggle', True, {'label': 'Rig out -> router input'}),
            ('Routerslot', 'Int', 1, {'label': 'Router source slot (local in)', 'min': 1, 'max': 4}),
            ('Routersink', 'Int', 1, {'label': 'Router sink (Syphon)', 'min': 1, 'max': 4}),
            ('Syphonname', 'Str', SYPHON_NAME, {'label': 'Syphon name'}),
        ]),
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
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            else:
                p = getattr(page, 'append' + style)(name, label=label)[0]
            if 'min' in o:
                p.normMin = p.min = o['min']
                p.clampMin = True
            if 'max' in o:
                p.normMax = p.max = o['max']
                p.clampMax = style == 'Int'
            if default is not None:
                p.default = default
                p.val = default
            if o.get('ro'):
                p.readOnly = True


def _connector(comp, in_name):
    for cn in comp.inputConnectors:
        if cn.inOP is not None and cn.inOP.name == in_name:
            return cn
    return None


def _send(lab, name, top_path, target, in_name, prot, notes):
    """A Select TOP in the lab (beside target) wired into target's in_name connector. Never steals a connector
    someone else wired; never touches a live lane's COMP."""
    if target is None:
        notes.append('%s: target missing' % name)
        return None
    s = lab.op(name)
    if s is None:
        s = lab.create(selectTOP, name)
        s.nodeX, s.nodeY = target.nodeX - 220, target.nodeY + 40
        s.viewer = True
    s.par.top = top_path
    s.comment = 'show_rig send (builders/show_rig.py): %s -> %s' % (top_path, target.name)
    if target.path in prot:
        notes.append('%s: %s is a live lane COMP, not wired (re-run build() once that lane is done)' % (name, target.name))
        return s
    cn = _connector(target, in_name)
    if cn is None:
        notes.append('%s: %s has no %s connector' % (name, target.name, in_name))
        return s
    cur = [x.owner for x in cn.connections]
    if cur and cur[0] is not s:
        notes.append('%s: %s.%s already wired from %s, left alone' % (name, target.name, in_name, cur[0].name))
        return s
    if not cur:
        s.outputConnectors[0].connect(cn)
    return s


def build(layers=LAYERS, panel=True, wire_sends=True):
    import json
    Lg = _logic()
    H = op('/jazib_mcp/handlers').module
    par_ = op(PARENT)
    lab = op(LAB)
    notes = []
    c = par_.op(NAME)
    if c is not None:
        c.allowCooking = True
        w = c.op('controls_window')
        if w is not None and w.isOpen:                    # T-70: never rebuild under an open window
            w.par.winclose.pulse()
    try:
        prot = sorted(json.load(open(REPO + '/logs/active_lanes.json')).keys())
    except Exception:
        prot = []
    # 1 the mixer (handler), bank as Out TOP paths so its own guard never switches a COMP
    tops, names = [], []
    for nm in LOOKS:
        o = lab.op(nm)
        t = H._source_top(o) if o is not None else None
        if t:
            tops.append(t)
            names.append(nm)
    r = H.cmd_layer_mixer(parent=PARENT, name=NAME, layers=int(layers), sources=tops, res=[1080, 1920],
                          cook_guard=True)
    c = op(r['path'])
    c.allowCooking = True
    tab = c.op('sources')
    for k, nm in enumerate(names):                    # label column = the look COMP's name (handler wrote 'out1')
        tab[k + 1, 'label'] = nm
    menu_labels = ['%d: %s' % (k, nm) for k, nm in enumerate(names)]
    for n in range(1, int(layers) + 1):
        c.par['L%dsource' % n].menuLabels = menu_labels
    # 2 our code + pars
    lg = _mk(c, textDAT, 'rig_logic')
    lg.text = open(LOGIC_FILE).read()
    lg.comment = 'Pure logic (copy of builders/show_rig_logic.py; tests in test/test_show_rig.py).'
    _pars(c, _pages(Lg))
    rt = c.op('runtime')
    rt.text = RIG_RT % {'lanes': REPO + '/logs/active_lanes.json'}
    rt.comment = 'show_rig runtime (replaces the mixer runtime; same eff/active_sources/apply API).'
    g = c.op('guard_exec')
    g.text = GUARD
    g.par.onpulse = True
    g.par.valuechange = True
    tk = _mk(c, executeDAT, 'rig_tick')
    tk.text = TICK
    tk.par.framestart = True
    tk.par.active = False                              # T-97: toggle after writing the text
    tk.par.active = True
    # 3 tables (kept across rebuilds once filled)
    pt = _mk(c, tableDAT, 'presets')
    head = Lg['preset_header'](int(layers))
    if pt.numRows < 2 or [x.val for x in pt.row(0)] != head:
        pt.clear()
        pt.appendRow(head)
        for row in Lg['default_presets'](names, int(layers)):
            pt.appendRow(row)
    pt.comment = 'Look presets (row = Preset number). Sources by look name. Store writes row Preset.'
    cq = _mk(c, tableDAT, 'rig_cues')
    if cq.numRows < 2:
        cq.clear()
        for row in Lg['demo_cues'](names, c.path):
            cq.appendRow(row)
    cq.comment = 'CQ_cuelist cue table for the rig (Hookcq sets CQ Cuetable here). kind par: <rig>:<Par> value.'
    mb = _mk(c, tableDAT, 'midi_binds')
    mb.clear()
    binds = Lg['midi_binds'](int(layers), c.path, int(c.par.Midibank), int(c.par.Midichannel), int(c.par.Midicc0),
                             int(c.par.Midinote0))
    mb.appendRow(['id', 'label', 'kind', 'number', 'par', 'mode'])
    for b in binds:
        mb.appendRow([b['id'], b['label'], b['kind'], b['number'], b['par'], b['mode']])
    mb.comment = 'Bindable controls: Midiregister adds them to MIDI_mapper (ids sr_*), Midiunregister removes them.'
    # 4 master FX inserts by reference: fx_slot in1 -> [pre_k -> ins_k (switch: through / ret_k)] -> out1
    fx = c.op('fx_slot')
    prev = fx.op('in1')
    for k in Lg['FX_ORDER']:
        pre = _mk(fx, nullTOP, 'pre_%s' % k)
        pre.inputConnectors[0].connect(prev)
        ret = _mk(fx, selectTOP, 'ret_%s' % k)
        _expr(ret.par.top, "(parent(2).par.Fx%scomp.eval().op('out1').path if parent(2).par.Fx%scomp.eval() "
                           "is not None and parent(2).par.Fx%scomp.eval().op('out1') is not None else '')" % (k, k, k))
        ins = _mk(fx, switchTOP, 'ins_%s' % k)
        ins.inputConnectors[0].connect(pre)
        ins.inputConnectors[1].connect(ret)
        _expr(ins.par.index, '1 if parent(2).par.%s else 0' % Lg['FX_PAR'][k])
        ins.comment = 'Insert %s: 0 = through, 1 = the lab COMP (fed by %s/SR_send_%s)' % (k, LAB, k)
        prev = ins
    fx.op('out1').inputConnectors[0].connect(prev)
    fx.comment = ('Master FX inserts by reference (palette -> trail -> strobe): each pre_<fx> is sent to the lab FX '
                  'COMP by a Select TOP there (SR_send_<fx>), ret_<fx> brings its out1 back. Off = through, no cook.')
    H.layout_stages(fx, [
        {'title': 'Chain', 'role': 'process', 'ops': ['in1'] + ['%s_%s' % (a, k) for k in Lg['FX_ORDER']
                                                               for a in ('pre', 'ret', 'ins')] + ['out1'],
         'body': 'in1 -> pre_k (sent to the lab FX COMP) -> ins_k picks through or ret_k (its out1) -> out1'}],
        True, arrange='mixed')
    # 5 sends in the lab (router input + FX inputs)
    sends = {}
    if wire_sends:
        sends['router'] = _send(lab, 'SR_send_router', c.op('out1').path, c.par.Router.eval(),
                                'in%d' % int(c.par.Routerslot), prot, notes)
        for k in Lg['FX_ORDER']:
            sends[k] = _send(lab, 'SR_send_%s' % k, fx.op('pre_%s' % k).path, c.par['Fx%scomp' % k].eval(), 'in1',
                             prot, notes)
    if c.par.Hookrouter.eval() and c.par.Router.eval() is not None:
        notes.append(rt.module.hook_router(c))
    # 6 controls (zkit) beside the mixer's parameter panel; controls_window shows the zkit panel
    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=['Rig', 'Mixer'] + ['Layer%d' % n for n in range(1, int(layers) + 1)]
                                    + ['FX', 'Guard', 'Hooks'], d=48, cols=8, panel_name='zk_controls',
                                    winop='zk_controls')
    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    c.comment = ('MASTER SHOW RIG (builders/show_rig.py): %d layers over %d lab looks (cook guard: only what a visible '
                 'layer shows cooks), master FX inserts by reference, presets (Preset/Recall/Store), hooks: CQ '
                 '(Hookcq -> rig_cues), MIDI (Midiregister), router (out1 -> BP_io_router local in, Syphon %r OFF). '
                 'Pulse Opencontrols.' % (int(layers), len(names), SYPHON_NAME))
    stages = [
        {'title': 'Sources', 'role': 'input', 'ops': ['sources'] + ['src%d' % k for k in range(len(names))] + ['black'],
         'body': 'Bank = the lab looks Out TOPs (Select TOPs). Only a visible layer pulls one; the guard wakes its COMP.'},
        {'title': 'Layers', 'role': 'process', 'ops': [x for n in range(1, int(layers) + 1)
                                                      for x in ('l%d_switch' % n, 'l%d_comp' % n, 'l%d_mix' % n,
                                                                'l%d_gate' % n)],
         'body': 'switch (Source) -> composite (Blend) -> cross (Opacity x mute/solo) -> gate (skipped at 0)'},
        {'title': 'Master + FX', 'role': 'process', 'ops': ['fx_slot', 'fx_bypass', 'master'],
         'body': 'Masterfx -> fx_slot inserts (palette, trail, strobe by reference); Master opacity'},
        {'title': 'Output', 'role': 'output', 'ops': ['out1'],
         'body': 'out1 -> /project1/lab/SR_send_router -> BP_io_router local in (Syphon sink OFF until the user)'},
        {'title': 'Engine', 'role': 'note', 'ops': ['rig_logic', 'runtime', 'guard_exec', 'rig_tick'],
         'body': 'Cook guard (owned / strict / off, lanes protected), presets + fades, hooks'},
        {'title': 'Show data', 'role': 'note', 'ops': ['presets', 'rig_cues', 'midi_binds'],
         'body': 'presets (row = Preset), rig_cues (CQ cue table), midi_binds (MIDI_mapper)'},
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'controls_exec', 'zk_controls'],
         'body': 'zkit panel (Opencontrols) + the mixer parameter panel'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = H.layout_stages(c, stages, True, arrange='mixed')
    guard = rt.module.apply(c)
    return {'comp': c.path, 'bank': names, 'layers': int(layers), 'guard': guard, 'notes': notes + r.get('notes', []),
            'sends': dict((k, v.path if v is not None else None) for k, v in sends.items()),
            'panel': str(info)[:200], 'layout': str(lay)[:300]}
