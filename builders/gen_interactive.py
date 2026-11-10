# gen_interactive builder - GEN_interactive: artist looks driven by people (face / hands / person mask / effectors /
# mouse), as generator slots over a background (FX0 rows 42 + 68, FX5 E8 ribbon, E4 flowers, E1 pigment, E3
# linevolume). The GEN_sim rack (builders/gen_sim.py, itself the FX_glitch rack: slots table, Cross + Switch per slot,
# Panic, add/remove/rewire, background Input auto/black/live/test) is reused as is; this file adds only what all
# GEN_interactive modules read (no-bloat rule): the tracked POINTS (`pts` Script CHOP -> `pts_tex`, N x 1 rgba32f:
# x y vx vy, from demo paths / FT_face_track landmarks / /project1/effectors / Null COMPs / the mouse / any CHOP),
# the shared presence + motion MASK (`gi_mask`, from a person-mask TOP or the picture), the rack DRIVE (beats, bpm,
# audio level: GEN_pattern's drive, imported), the module Drive + State pages and full-state presets.
# Module 'X' lives in builders/gen_interactive_X.py, shaders in builders/glsl/gen_interactive_X_*.glsl (put after
# gen_sim_common.glsl + gen_interactive_common.glsl), numpy references in builders/gen_interactive_X_logic.py.
# Doc + LIVE CHECKS: docs/builds/gen_interactive.md. Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/gen_interactive.py').read(), ns)
#   ns['build']('/project1/lab')                               # rack + 'ribbon1' on first build; idempotent
#   ns['add']('/project1/lab/GEN_interactive', 'flowers')       # flowers1, wired last (zkit panel + presets)
#   ns['remove']('/project1/lab/GEN_interactive', 'flowers1'); ns['rewire'](c) after editing order in `slots`
#   ns['preset']('/project1/lab/GEN_interactive/ribbon1', 2)    # full-state preset straight onto the pars
# T-70 safe (_sd = safe_destroy); no functions in op storage (T-67); no TOP pixel reads (T-74). ASCII only.
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
with open(os.path.join(HERE, 'gen_sim.py')) as _fh:
    exec(_fh.read(), globals())                          # GEN_sim rack + helpers; names looked up at call time
_GP = dict(globals())
with open(os.path.join(HERE, 'gen_pattern.py')) as _fh:
    exec(_fh.read(), _GP)                                # GEN_pattern's rack drive (_drive): beats / bpm / level

NAME = 'GEN_interactive'
FIRST = ('ribbon1', 'ribbon')
MODULES = ['ribbon', 'flowers', 'pigment', 'linevolume', 'strings', 'parallax', 'skinner']
GI_LOGIC_FILE = os.path.join(HERE, 'gen_interactive_logic.py')
_gs_glsl_text = glsl_text
_gs_build = build
_gs_layout = _layout


def gi_logic():
    ns = {}
    with open(GI_LOGIC_FILE) as fh:
        exec(fh.read(), ns)
    return ns


LGI = gi_logic()


def glsl_text(*names):
    """gen_sim_common + gen_interactive_common + the named pass files, as one compute shader text."""
    parts = [_gs_glsl_text()]
    for n in ('gen_interactive_common',) + tuple(names):
        with open(os.path.join(GLSL_DIR, n + '.glsl')) as fh:
            parts.append(fh.read())
    return '\n'.join(parts)


def module_file(module):
    return os.path.join(HERE, 'gen_interactive_%s.py' % module)


def _module(module):
    ns = dict(globals())
    with open(module_file(module)) as fh:
        exec(fh.read(), ns)
    return ns


def module_logic(module):
    """builders/gen_interactive_<module>_logic.py as a namespace (numpy references; numpy only inside functions)."""
    ns = {}
    with open(os.path.join(HERE, 'gen_interactive_%s_logic.py' % module)) as fh:
        exec(fh.read(), ns)
    return ns


# ------------------------------------------------------------------ shared module pages / uniforms / presets
D_OP = "parent(2).op('drive')"


def drive_page(speed=1.0):
    """Every module: Speed (module clock x), beat pulse (Beatgain / Beatdecay), audio (Audiogain x rack level) and a
    Manual drive (0..1 by hand / MIDI), all summed into the module's drive target."""
    return ('Drive', [
        ('Speed', 'Float', speed, {'min': -4, 'max': 4, 'label': 'Speed (module clock x)'}),
        ('Beatgain', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Beat pulse gain'}),
        ('Beatdecay', 'Float', 0.25, {'min': 0.02, 'max': 2, 'label': 'Beat pulse decay s'}),
        ('Audiogain', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Audio -> look'}),
        ('Manual', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Manual drive'}),
    ])


STATE_PAGE_GI = ('State', [('Reset', 'Pulse', None, {'label': 'Reset (clear)'}),
                           ('Resetcount', 'Int', 0, {'min': 0, 'max': 100, 'label': 'Reset count (Reset pulse +1)'})])
DRIVE_UNIFORMS = [
    ('uDrv', ["float(%s['beats'])" % D_OP, "float(%s['bpm'])" % D_OP, "float(%s['level'])" % D_OP, '0']),
    ('uDg', [P.format('Beatgain'), P.format('Beatdecay'), P.format('Audiogain'), P.format('Manual')]),
]
TIME_EXPR = 'absTime.seconds'                             # self-clocked state passes (meta texel, gi_dt)


def page_defaults(pages):
    """{par: default} of pages (menus as index, RGB split into r/g/b); pulses / op refs / strings left out."""
    d = {}
    for _pg, pars in pages:
        for name, style, default, o in pars:
            if style == 'RGB':
                for ch, v in zip('rgb', default):
                    d[name + ch] = v
            elif style == 'Menu':
                d[name] = o['names'].index(default)
            elif style in ('Float', 'Int', 'Toggle'):
                d[name] = default
    return d


def full_presets(pages, presets):
    """Presets as FULL states (page defaults + the preset's values): a recall never inherits pars from the preset
    before it (GEN_pattern live, T-124 (1)). Preset RGB values may be given as 'Colora': (r, g, b)."""
    base = page_defaults(pages)
    out = []
    for slot, name, vals in presets:
        d = dict(base)
        for k, v in vals.items():
            if isinstance(v, (tuple, list)):
                for ch, x in zip('rgb', v):
                    d[k + ch] = x
            else:
                d[k] = v
        out.append((slot, name, d))
    return out


def preset(inst_path, slot):
    """Apply module preset `slot` (full state) straight to the instance pars (what zkit Recall sets)."""
    m = op(inst_path)
    M = _module(m.parent().op('slots')[m.name, 'module'].val)
    vals = next(v for s, _n, v in M['PRESETS'] if s == slot)
    n = 0
    for k, v in vals.items():
        p = getattr(m.par, k, None)
        if p is None:
            continue
        if p.isMenu:
            p.menuIndex = int(v)
        else:
            p.val = v
        n += 1
    return {'preset': slot, 'set': n}


def _select(m, name, expr, comment):
    s = _mk(m, selectTOP, name)
    _expr(s.par.top, expr)
    s.comment = comment
    return s


def pts_in(m):
    """The rack's points texture inside a module (Select TOP `pts`)."""
    return _select(m, 'pts', "parent(2).op('pts_tex')", 'Rack points (pts_tex): texel i = x y vx vy, absent x = -10.')


def mask_in(m):
    """The rack's presence / motion map inside a module (Select TOP `mask`)."""
    return _select(m, 'mask', "parent(2).op('gi_mask')", 'Rack mask (gi_mask): r presence, g motion, b luma.')


H = dict(H, glsl=glsl_text, pts_in=pts_in, mask_in=mask_in, drive_uniforms=DRIVE_UNIFORMS, time_expr=TIME_EXPR)

# ------------------------------------------------------------------ rack: points, mask, drive
PTS_CB = """# pts: GEN_interactive tracked points (builders/gen_interactive.py; logic in gi_logic). Maxpoints samples,
# channels x y vx vy: x y in 0..1 of the frame (y up), velocity in frame units / s, absent = x = y = -10.
# Cooks every frame while something pulls it (Frame par + absTime); state per CHOP path in module memory (T-123 (2)).
import numpy as np
STATE = {}

def onSetupParameters(scriptOp):
    if getattr(scriptOp.par, 'Frame', None) is None:
        p = scriptOp.appendCustomPage('Clock').appendFloat('Frame', label='Frame (clock)')[0]
        p.expr = 'absTime.frame'
        p.mode = ParMode.EXPRESSION
    return

def _raw(c, L, P, n, t, plane):
    src = P.Source.eval()
    if src == 'demo':
        return L.demo_points(t * P.Demospeed.eval(), n, P.Demoshape.menuIndex, int(P.Demoseed.eval()))
    if src == 'face':
        ft = op(P.Faceop.eval()) if P.Faceop.eval() else None
        ch = ft.op('out_pts') if ft is not None else None
        if ch is None or ch.numChans == 0:
            return []
        a = ch.numpyArray()
        names = [x.name for x in ch.chans()]
        return L.face_points(names, a[:, 0], P.Facepts.eval(), P.Facestride.eval(), n, P.Facemirror.eval())
    if src == 'effectors':
        rt, rows = op('/project1/effectors/eff_rt'), op('/project1/effectors/eff_rows')
        if rt is None or rows is None:
            return []
        M = rt.module
        idx = M.L().selected(M.rows(), P.Effselect.eval())
        return L.effector_points(rows.numpyArray().T, idx, plane, n, P.Effsets.eval(), P.Effcentres.eval())
    if src == 'null':
        out = []
        for nm in str(P.Nulls.eval()).split():
            o = c.op(nm) or op(nm)
            out.append(L.plane_to_screen(o.par.tx.eval(), o.par.ty.eval(), plane) if o is not None else None)
        return out
    if src == 'mouse':
        m = c.op('mouse')
        if m is None or m['tx'] is None:
            return []
        down = m['lselect'] is None or m['lselect'].eval() > 0.5
        if P.Mousepen.eval() and not down:
            return [None]
        return [((m['tx'].eval() + 1.0) * 0.5, (m['ty'].eval() + 1.0) * 0.5)]
    ch = P.Pointchop.eval()
    if ch is None or ch.numChans == 0:
        return []
    a = ch.numpyArray()
    chans = dict((x.name, a[k]) for k, x in enumerate(ch.chans()))
    return L.chop_points(chans, P.Chopunits.menuIndex, plane, n)

def onCook(scriptOp):
    c = scriptOp.parent()
    L = op('gi_logic').module
    P = c.par
    if getattr(scriptOp.par, 'Frame', None) is not None:
        scriptOp.par.Frame.eval()
    n = max(1, int(P.Maxpoints.eval()))
    t = absTime.seconds
    st = STATE.get(scriptOp.path) or {'t': None, 'p': [], 'v': []}
    dt = t - st['t'] if st['t'] is not None else 0.0
    if dt < 0.0 or dt > 0.25:
        st = {'t': None, 'p': [], 'v': []}
        dt = 0.0
    plane = (P.Planecx.eval(), P.Planecy.eval(), P.Planew.eval(), P.Planeh.eval())
    err = ''
    try:
        raw = _raw(c, L, P, n, t, plane)
    except Exception as e:
        raw, err = [], str(e)[:200]
    if dt == 0.0 and st['t'] == t:
        new = st
    else:
        new = L.step_points(st, raw, dt, P.Smooth.eval(), n)
    new['t'] = t
    new['err'] = err
    STATE[scriptOp.path] = new
    chans = L.pack(new, n)
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = n
    for k, nm in enumerate(L.CHANS):
        scriptOp.appendChan(nm).copyNumpyArray(np.array(chans[k], dtype=np.float32))
    return
"""

RACK_PAGES = [
    ('Points', [
        ('Source', 'Menu', 'demo', {'names': LGI['SOURCES'], 'labels': LGI['SOURCE_LABELS']}),
        ('Maxpoints', 'Int', 16, {'min': 1, 'max': 256, 'label': 'Points (samples of pts)'}),
        ('Smooth', 'Float', 0.5, {'min': 0, 'max': 0.99, 'label': 'Smooth (share kept per 1/60 s)'}),
        ('Demoshape', 'Menu', 'lissajous', {'names': LGI['DEMO_SHAPES'], 'labels': LGI['DEMO_LABELS']}),
        ('Demospeed', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Demo speed'}),
        ('Demoseed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Demo seed'}),
        ('Faceop', 'Str', '/project1/lab/FT_face_track', {'label': 'Face tracker COMP (out_pts)'}),
        ('Facepts', 'Str', 'f1_nose_* f1_pupil_* f1_lips_outer_*', {'label': 'Landmarks (glob on f<n>_<region>_<kk>)'}),
        ('Facestride', 'Int', 1, {'min': 1, 'max': 16, 'label': 'Landmark stride'}),
        ('Facemirror', 'Toggle', False, {'label': 'Mirror face x'}),
        ('Effselect', 'Str', 'all', {'label': 'Effectors (all / names / #tag)'}),
        ('Effsets', 'Toggle', True, {'label': 'Point sets give their points'}),
        ('Effcentres', 'Toggle', True, {'label': 'Other effectors give their centre'}),
        ('Nulls', 'Str', 'pen1', {'label': 'Null COMPs (names / paths)'}),
        ('Mousepen', 'Toggle', False, {'label': 'Mouse draws only while pressed'}),
        ('Pointchop', 'CHOP', '', {'label': 'Point CHOP (Source chop)'}),
        ('Chopunits', 'Menu', 'unit', {'names': LGI['CHOP_UNITS'], 'labels': LGI['CHOP_UNIT_LABELS']}),
        ('Planecx', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Plane centre x (world)'}),
        ('Planecy', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Plane centre y (world)'}),
        ('Planew', 'Float', 1.125, {'min': 0.1, 'max': 20, 'label': 'Plane width (world units = frame)'}),
        ('Planeh', 'Float', 2.0, {'min': 0.1, 'max': 20, 'label': 'Plane height (world units = frame)'}),
    ]),
    ('Mask', [
        ('Masksource', 'Menu', 'none', {'names': LGI['MASK_SOURCES'], 'labels': LGI['MASK_LABELS']}),
        ('Masktop', 'TOP', '', {'label': 'Mask TOP (e.g. CV_person_mask/out2, FT_face_track/out_face)'}),
        ('Maskchannel', 'Menu', 'r', {'names': LGI['MASK_CHANNELS'], 'labels': ['Red', 'Alpha', 'Luma']}),
        ('Lumathresh', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Luma threshold'}),
        ('Lumasoft', 'Float', 0.1, {'min': 0, 'max': 0.5, 'label': 'Luma softness'}),
        ('Maskinvert', 'Toggle', False, {'label': 'Invert presence'}),
        ('Motiongain', 'Float', 4.0, {'min': 0, 'max': 32, 'label': 'Motion gain'}),
        ('Motionsmooth', 'Float', 0.8, {'min': 0, 'max': 0.99, 'label': 'Motion smooth (per cook)'}),
        ('Maskw', 'Int', 270, {'min': 8, 'max': 2048, 'label': 'Mask width'}),
        ('Maskh', 'Int', 480, {'min': 8, 'max': 2048, 'label': 'Mask height'}),
    ]),
    ('Drive', [
        ('Beatsource', 'Menu', 'internal', {'names': ['internal', 'chop'],
                                            'labels': ['Internal (Bpm)', 'Beat CHOP (count + phase)']}),
        ('Bpm', 'Float', 120.0, {'min': 40, 'max': 200, 'label': 'Bpm'}),
        ('Bpmchop', 'CHOP', '', {'label': 'Bpm CHOP (e.g. AU_features/out1)'}),
        ('Bpmchan', 'Str', 'bpm', {'label': 'Bpm channel'}),
        ('Beatchop', 'CHOP', '', {'label': 'Beat CHOP (e.g. AU_features/out1)'}),
        ('Phasechan', 'Str', 'beat_phase', {'label': 'Beat phase channel'}),
        ('Countchan', 'Str', 'beat_count', {'label': 'Beat count channel'}),
        ('Audiochop', 'CHOP', '', {'label': 'Audio CHOP (e.g. AC_audio/out_ctl)'}),
        ('Audiochan', 'Str', 'low', {'label': 'Audio channel'}),
        ('Resync', 'Pulse', None, {'label': 'Resync (beat 1 now)'}),
    ]),
]

MASK_SRC = ("(lambda t: t if parent().par.Masksource.eval() == 'top' and t is not None else op('img_src'))"
            "(parent().par.Masktop.eval())")
CP = "parent().par.{}.eval()"
CPI = "parent().par.{}.menuIndex"
MASK_UNIFORMS = [('uM1', [CPI.format('Masksource'), CPI.format('Maskchannel'), CP.format('Lumathresh'),
                          CP.format('Lumasoft')]),
                 ('uM2', [CP.format('Motiongain'), CP.format('Motionsmooth'), "1 if %s else 0" % CP.format('Maskinvert'),
                          '0'])]


def _script(c, name, text):
    """Script CHOP + its callbacks DAT `<name>_callbacks` (the auto-docked one reused / renamed, as effectors.py)."""
    s = _mk(c, scriptCHOP, name)
    want = name + '_callbacks'
    cb = c.op(want)
    if cb is None or cb.OPType != 'textDAT':
        cb = s.par.callbacks.eval()
        if cb is None:
            cb = _mk(c, textDAT, want)
        elif cb.name != want and c.op(want) is None:
            cb.name = want
    if cb.text != text:
        cb.text = text
    s.par.callbacks = cb.name
    s.par.setuppars.pulse()
    return s


def _points(c):
    lg = _mk(c, textDAT, 'gi_logic')
    with open(GI_LOGIC_FILE) as fh:
        txt = fh.read()
    if lg.text != txt:
        lg.text = txt
    lg.comment = 'builders/gen_interactive_logic.py (copied): sources, smoothing, packing; pts_callbacks calls it.'
    ms = _mk(c, mouseinCHOP, 'mouse')
    ms.comment = 'Screen mouse (Source mouse only; tx ty -1..1, lselect).'
    pen = c.op('pen1')
    if pen is None:
        pen = c.create(nullCOMP, 'pen1')
        pen.viewer = True
    pen.comment = 'Manual point (Source null, Nulls = pen1): move tx / ty on the world plane (Points page).'
    s = _script(c, 'pts', PTS_CB)
    s.comment = 'Tracked points: Maxpoints samples x (x y vx vy), 0..1 y up, absent x = -10 (Points page Source).'
    tex = _mk(c, choptoTOP, 'pts_tex')
    tex.par.chop = s.name                             # CHOP to TOP has no input connector on 31550 (T-125 (1))
    tex.par.dataformat = 'rgba'
    tex.par.format = 'rgba32float'
    tex.comment = 'Points as a Maxpoints x 1 rgba32f TOP (texel i = x y vx vy) for the module shaders.'


def _mask(c):
    sel = _mk(c, selectTOP, 'mask_src')
    _expr(sel.par.top, MASK_SRC)
    sel.comment = 'Mask source: the Mask TOP (Masksource top), else the background picture (motion / luma).'
    rs = _mk(c, resolutionTOP, 'mask_small')
    rs.inputConnectors[0].connect(sel)
    rs.par.outputresolution = 'custom'
    _expr(rs.par.resolutionw, CP.format('Maskw'))
    _expr(rs.par.resolutionh, CP.format('Maskh'))
    rs.comment = 'Mask source at Maskw x Maskh.'
    w, h = CP.format('Maskw'), CP.format('Maskh')
    fb = H['state'](c, 'mask_fb', 'gi_mask', w, h, 'rgba16float')
    g = H['pas'](c, 'gi_mask', glsl_text('gen_interactive_mask'), [rs, fb], w, h, 'rgba16float', MASK_UNIFORMS)
    g.comment = 'Shared presence / motion map: r presence, g motion (frame difference, smoothed), b luma, a 1.'
    return g


def _refresh(c):
    """Re-evaluate the Select / Feedback TOP references of the rack and its modules once (an expression that named an
    op before it existed is not re-evaluated by itself, T-139 (1))."""
    ops_ = list(c.children)
    for o in list(ops_):
        if o.isCOMP:
            ops_ += list(o.children)                      # one level: the modules' own ops
    n = 0
    for o in ops_:
        if o.OPType in ('selectTOP', 'feedbackTOP'):
            o.par.top.eval()
            n += 1
    return n


def _comment(c, name, module):
    m = c.op(name)
    if m is not None:
        m.comment = ('GEN_interactive module %s (%s): draws over its slot input (Colour page Blend), reads the rack '
                     'points / mask / drive. Pars on its pages; Opencontrols = zkit panel, Reset clears.' % (name, module))


def _layout(c):
    names = plan_chain(_rows(c))
    chain = []
    for n in names:
        chain += [n, n + '_mix', n + '_slot']
    stages = [
        {'title': 'Rack', 'role': 'control', 'ops': ['slots', 'drive_pexec'],
         'body': 'slots: name module enabled order mix. enabled/mix live; add/remove/order = builder rewire.'},
        {'title': '0 Drive', 'role': 'input', 'ops': ['drive_rate', 'drive_beats', 'drive'],
         'body': 'drive: beats (internal Bpm or a beat CHOP), bpm, level (audio CHOP channel).'},
        {'title': '0 Points', 'role': 'input', 'ops': ['gi_logic', 'mouse', 'pen1', 'pts', 'pts_callbacks', 'pts_tex'],
         'body': 'pts: demo / face landmarks / effectors / Nulls / mouse / CHOP -> x y vx vy (0..1, y up).'},
        {'title': '1 Background', 'role': 'input', 'ops': ['bg', 'in1', 'test_clip', 'img_src'],
         'body': 'Input: auto (in1 if wired, else black bg) / black / live (in1) / test clip.'},
        {'title': '1 Mask', 'role': 'input', 'ops': ['mask_src', 'mask_small', 'mask_fb_blank', 'mask_fb', 'gi_mask',
                                                     'gi_mask_compute'],
         'body': 'gi_mask: presence (mask TOP / luma / 1) + motion (frame difference) at Maskw x Maskh.'},
        {'title': '2 Generators', 'role': 'process', 'ops': [n for n in chain if c.op(n) is not None],
         'body': 'Per slot: module COMP (draws over its input) -> _mix (Cross) -> _slot (Switch 0 bypass/1/2 mix).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['panic', 'out1'], 'body': 'Panic = the background straight out.'},
    ]
    for s in stages:
        s['ops'] = [n for n in s['ops'] if c.op(n) is not None]
    return op('/jazib_mcp/handlers').module.layout_stages(c, [s for s in stages if s['ops']], True, arrange='mixed')


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    _pars(c, RACK_PAGES)
    _GP['_drive'](c)                                      # drive_rate -> drive_beats -> drive (+ Resync pexec)
    _points(c)
    res = _gs_build(parent_path, panel)                   # GEN_sim rack: slots (ribbon1), background, modules
    _mask(c)
    c.comment = ('GEN_interactive: people-driven artist looks (ribbon, flowers, pigment, linevolume). In: in1 TOP '
                 '(optional background). Out: out1 TOP. Points page = what drives them (demo / face / effectors / '
                 'Null / mouse / CHOP); Mask page = presence + motion. Slots from `slots` (builders/gen_interactive.py).')
    for r in _rows(c):
        _comment(c, r['name'], r['module'])
    res['refreshed'] = _refresh(c)
    res['layout'] = str(_layout(c))[:300]
    return res


def add(comp_path, module, name=None, order=None, enabled=1, mix=1, panel=True):
    if module not in MODULES:
        raise ValueError('unknown module %r (have %s)' % (module, ', '.join(MODULES)))
    res = _rack_add(comp_path, module, name=name, order=order, enabled=enabled, mix=mix, panel=panel)
    c = op(comp_path)
    _comment(c, res['added'], module)
    _refresh(c)
    return res


# ------------------------------------------------------------------ live cost sampler (T-102 method, T-124 (3))
COST_CB = """def gi_cost_tick(path):
    m = op(path)
    o = m.op('out1')
    o.cook(force=True)
    f = o.cookAbsFrame
    names = {}
    for c in m.findChildren(depth=1):
        if c.family in ('TOP', 'CHOP') and c.cookAbsFrame == f:
            names[c.name] = [float(getattr(c, 'cpuCookTime', 0.0) or 0.0), float(getattr(c, 'gpuCookTime', 0.0) or 0.0)]
    st = m.fetch('gi_cost', {}, search=False)
    st.setdefault('rows', []).append(names)
    m.store('gi_cost', st)
"""


def cost_start(inst_path, n=120):
    """Pull the module's out1 once a frame for n frames (one queued sampler; never overlap two, T-124 (3)); read with
    cost_read() more than n frames later. Pane off the COMP (its viewers would pull too)."""
    m = op(inst_path)
    m.store('gi_cost', {'rows': []})
    script = COST_CB + 'gi_cost_tick(args[0])\n'                 # run() takes script text + args (T-139 (3))
    for k in range(n):
        run(script, inst_path, delayFrames=k + 1)
    return {'cost_started': inst_path, 'frames': n}


def cost_read(inst_path):
    """Median per op (cpu, gpu ms) and the median of the per-frame totals."""
    rows = (op(inst_path).fetch('gi_cost', {}, search=False) or {}).get('rows', [])
    if not rows:
        return {'rows': 0}
    med = lambda v: sorted(v)[len(v) // 2] if v else 0.0
    ops_ = sorted(set(k for r in rows for k in r))
    per = dict((k, [round(med([r[k][0] for r in rows if k in r]), 3), round(med([r[k][1] for r in rows if k in r]), 3)])
               for k in ops_)
    tot = [sum(a + b for a, b in r.values()) for r in rows]
    return {'rows': len(rows), 'total_median_ms': round(med(tot), 3), 'total_p90_ms': round(sorted(tot)[int(0.9 * (len(tot) - 1))], 3),
            'ops': per}
