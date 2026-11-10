# effectors_rt - /project1/effectors runtime (copied into the Text DAT `eff_rt` by builders/effectors.py). TD 2025.31550.
# Pure logic: eff_logic (builders/effectors_logic.py). This file talks to TD only: the list table, the effector objects,
# the packed rows (eff_rows Script CHOP), the list edits (add / remove / duplicate / rename / enable) and the pulses.
# Rules kept: T-67 plain data only in storage; T-70 destroys through safe_destroy (never a panel a window shows);
# T-74 no TOP pixel reads (points come from CHOP / SOP values; an env's pixels come through its own TOP to CHOP on
# `nextframe`, the established no-stall download); T-115 class-level hasattr for worldTransform;
# T-113 the rows CHOP cooks every frame only through its Frame par (Track = frame); T-89 module state self-heals.
# ASCII only.
import math

STATE = {'prev': {}, 'pprev': {}, 't': None, 'cache': None, 'pack': {}, 'ops': {}, 'envc': {}}
OBJ_SOPS = {'box': boxSOP, 'sphere': sphereSOP, 'plane': gridSOP, 'capsule': tubeSOP, 'torus': torusSOP}
GIZMO = 0.12                       # size of the point gizmo (null / path / point-set space)


def C():
    return me.parent()


def L():
    return C().op('eff_logic').module


def table():
    return C().op('eff_list')


def rows():
    """List rows (dicts), cached per list version. The key is the Listver par (bumped by every API edit and by the
    eff_watch DAT Execute on hand edits) + numRows, so callers (cook_rows, every consumer's sel_vec expressions) depend
    on one par, not on every cell (live: reading all cells in each uniform expression = a 5-8 ms hitch per edit)."""
    t = table()
    if t is None:
        return []
    lv = getattr(C().par, 'Listver', None)
    key = (lv.eval() if lv is not None else None, t.numRows)
    c = STATE.get('cache')
    if c is not None and key[0] is not None and c[0] == key:
        return c[1]
    rs = L().parse_table([[x.val for x in t.row(r)] for r in range(t.numRows)])
    STATE['cache'] = (key, rs)
    return rs


def bump():
    """The list changed (API edit or a hand edit of eff_list): new version -> rows() re-parses, consumers re-select."""
    STATE['cache'] = None
    lv = getattr(C().par, 'Listver', None)
    if lv is not None:
        lv.val = int(lv.eval()) + 1
    _grid_sync()


def write_rows(rs):
    t = table()
    cells = L().table_cells(rs)
    t.clear()
    for r in cells:
        t.appendRow(r)
    bump()


def status(text):
    p = getattr(C().par, 'Status', None)
    if p is not None and p.eval() != text:
        p.val = str(text)[:250]


def _sd(o):
    if o is None or not o.valid:
        return None
    h = op('/jazib_mcp/handlers')                  # MCP safe destroy when installed, plain destroy elsewhere (drop-in)
    f = getattr(h.module, 'safe_destroy', None) if h is not None else None
    if f is not None:
        return f(o)
    nomcp = o                                       # T-70 exception: no MCP here, so no safe_destroy to call
    nomcp.destroy()
    return None


def _find(path):
    if not path:
        return None
    for base in (C(), C().parent()):
        try:
            o = base.op(path)
        except Exception:
            o = None
        if o is not None:
            return o
    try:
        return op(path)
    except Exception:
        return None


def _is_obj(o):
    return o is not None and o.isCOMP and hasattr(type(o), 'worldTransform')


def world(o):
    """3x4 row-major [A | t]: tdu.Matrix m[r, c] is row r, column c (live: equal to transforming the origin + unit
    axes, 3x faster)."""
    m = o.worldTransform
    return [[m[r, 0], m[r, 1], m[r, 2], m[r, 3]] for r in range(3)]


# ------------------------------------------------------------------------------------------------ selection (consumers)

def sel_vec(text):
    """[tag mask, all, id0..id3] for a consumer's Effselect (par expressions call this). Memoised per text until the
    list changes: each consumer has ~6 uniform expressions calling it, ~0.6 ms each at 100 rows (live: a 5-10 ms
    hitch per list edit without the memo)."""
    rs = rows()
    m = STATE.get('sel')
    if m is None or m[0] is not rs:
        m = STATE['sel'] = (rs, {})
    v = m[1].get(text)
    if v is None:
        v = m[1][text] = L().sel_vec(text, rs)[0]
    return v


def follows_ref(kind):
    """Kinds whose `ref` is an object COMP that moves them (tie an effector to a Null, docs/builds/effectors.md):
    the SDF objects, null, camera and light (a light ties to a Light COMP). Point sets / env / cloud keep their own
    ref meaning (a CHOP / SOP / TOP)."""
    Lg = L()
    return kind in Lg.OBJECT_KINDS or kind in ('null', 'camera') or kind == Lg.LIGHT_KIND


def source_of(r):
    """The object whose transform drives row r: its own object, or `ref` (follows_ref kinds; camera always)."""
    key = (r['kind'], r.get('ref') or '', r['name'])
    o = STATE['ops'].get(key)
    if o is not None and o.valid:
        return o
    if r['kind'] in ('camera',) or (follows_ref(r['kind']) and r.get('ref')):
        o = _find(r.get('ref'))
    else:
        o = C().op(r['name'])
    if o is not None:
        STATE['ops'][key] = o
    return o


def select_ops(sel, kinds=None):
    """Objects of the enabled effectors a selection picks (CPU consumers: GN_reaction_diffusion / GN_physarum).
    Default kinds = objects + point kinds (point sets are not objects)."""
    Lg = L()
    rs = rows()
    kinds = kinds or (Lg.OBJECT_KINDS + Lg.POINT_KINDS)
    out = []
    for i in Lg.selected(rs, sel, kinds):
        o = source_of(rs[i])
        if _is_obj(o) and o not in out:
            out.append(o)
    return out


def light_paths(sel='all'):
    """Paths of the Light COMPs of the enabled `light` effectors a selection picks (own, or `ref`): a Render TOP's
    `lights` par (effectors_logic.lights_expr) so TD-lit MATs share the lights the shader consumers read."""
    return [o.path for o in select_ops(sel, (L().LIGHT_KIND,)) if o.OPType == 'lightCOMP']


def _pv(o, name, d):
    p = getattr(o.par, name, None)
    return p.eval() if p is not None else d


def light_of(o):
    """A Light COMP's values (effectors_logic.light_values). Reading the pars inside eff_rows' cook makes it recook
    when they change (Track = change). A foreign Light COMP (`ref`) has no Ltype / area pars: its type comes
    from TD's lighttype, area 0."""
    Lg = L()
    if o is None or not o.valid or o.OPType != 'lightCOMP':
        return Lg.light_values()
    lt = _pv(o, 'Ltype', None)
    if lt is None:
        lt = Lg.TD_TO_LTYPE.get(_pv(o, 'lighttype', 'point'), 'point')
    return Lg.light_values({
        'type': lt, 'colour': (_pv(o, 'cr', 1.0), _pv(o, 'cg', 1.0), _pv(o, 'cb', 1.0)),
        'intensity': _pv(o, 'dimmer', 1.0), 'att_on': _pv(o, 'attenuated', False),
        'att_start': _pv(o, 'attenuationstart', 1.0), 'att_end': _pv(o, 'attenuationend', 100.0),
        'att_exp': _pv(o, 'attenuationexp', 1.0), 'cone_angle': _pv(o, 'coneangle', 10.0),
        'cone_delta': _pv(o, 'conedelta', 3.0), 'cone_roll': _pv(o, 'coneroll', 1.0), 'area_w': _pv(o, 'Lareaw', 0.0),
        'area_h': _pv(o, 'Lareah', 0.0)})


ENV_PAR_KEYS = {'map': 'Envmap', 'gain': 'Envgain', 'w': 'Envw', 'h': 'Envh', 'twosided': 'Envtwosided',
                'samples': 'Envsamples'}


def env_of(o):
    """An env object's values (effectors_logic.env_values) + 'pixels' (H, W, 4) from its env_px TOP to CHOP (the
    ref TOP fitted to env_fit_size by env_fit; downloadtype nextframe = one frame late, no stall). Reading the pars
    and the CHOP here makes eff_rows recook when they change."""
    Lg = L()
    if o is None or not o.valid:
        return None
    d = dict((k, _pv(o, n, None)) for k, n in ENV_PAR_KEYS.items())
    d['probe'] = (_pv(o, 'Envprobex', 0.0), _pv(o, 'Envprobey', 1.0), _pv(o, 'Envprobez', 0.0))
    ev = Lg.env_values(d)
    ch = o.op('env_px')
    if ch is not None and ch.family == 'CHOP' and ch.numChans:
        ev['pixels'] = Lg.env_pixels_from_chop([c.name for c in ch.chans()], ch.numpyArray())
    else:
        ev['pixels'] = None
    return ev


def set_env(o, **vals):
    """Set env values on an env object by effectors_logic.env_values keys (map, gain, w, h, probe, twosided,
    samples). Returns the keys it could not set."""
    bad = []
    for k, v in vals.items():
        if k == 'probe':
            for n, x in zip(('Envprobex', 'Envprobey', 'Envprobez'), tuple(v)[:3]):
                getattr(o.par, n).val = float(x)
            continue
        p = getattr(o.par, ENV_PAR_KEYS.get(k, ''), None)
        if p is None:
            bad.append(k)
        else:
            p.val = v
    return bad


def env_fit(o, axis):
    """env_fit Resolution TOP size expression (inside the env object): effectors_logic.env_fit_size."""
    d = dict((k, _pv(o, n, None)) for k, n in ENV_PAR_KEYS.items())
    return L().env_fit_size(d)[axis]


def info_2d(o):
    """Per-effector values for the 2D sims (radius, falloff, active, gain) of an object select_ops returned."""
    Lg = L()
    for r in rows():
        s = source_of(r)
        if s is not None and s.path == o.path:
            return Lg.info_2d(r)
    return None


# ------------------------------------------------------------------------------------------------ path effectors

def path_xyz(o, axis):
    """Par expression of a path effector's tx / ty / tz (Path page on the object)."""
    Lg = L()
    t = absTime.seconds * o.par.Pathspeed.eval() + o.par.Pathphase.eval()
    q = None
    if o.par.Pathshape.eval() == 'chop':
        ch = _find(o.par.Pathchop.eval())
        if ch is not None and ch.family == 'CHOP':
            q = tuple(float(ch[n][0]) if ch[n] is not None else 0.0 for n in ('tx', 'ty', 'tz'))
    p = Lg.path_point(o.par.Pathshape.eval(), t, (o.par.Pathsizex.eval(), o.par.Pathsizey.eval(),
                                                  o.par.Pathsizez.eval()),
                      (o.par.Pathcentrex.eval(), o.par.Pathcentrey.eval(), o.par.Pathcentrez.eval()), q)
    return p[axis]


# ------------------------------------------------------------------------------------------------ point sets

def _actor_chop(o):
    """An actor COMP's points: its out_pts / out_points CHOP, else its first Out CHOP."""
    for n in ('out_pts', 'out_points', 'pts'):
        c = o.op(n)
        if c is not None and c.family == 'CHOP':
            return c
    for c in o.children:
        if c.OPType == 'outCHOP':
            return c
    return None


def points_of(r):
    """World points (n, 3) float64 of a point-set row (ref = CHOP / SOP, or an actor COMP), moved by the row's object
    (point space). numpy end to end; the CHOP's numpy read is not a TOP readback (T-74)."""
    import numpy as np
    Lg = L()
    src = _find(r.get('ref'))
    if src is not None and src.isCOMP and r['kind'] == 'actor':
        src = _actor_chop(src)
    pts = np.zeros((0, 3))
    if src is None:
        return pts
    if src.family == 'CHOP' and src.numChans:
        pts = _chop_points([c.name for c in src.chans()], src.numpyArray())
    elif src.family == 'SOP':
        pts = np.array([(p.x, p.y, p.z) for p in src.points[:Lg.PTS_MAX]], dtype=np.float64).reshape(-1, 3)
    pts = pts[:Lg.PTS_MAX]
    o = C().op(r['name'])
    if _is_obj(o) and len(pts):
        w = np.array(world(o))
        pts = pts @ w[:, :3].T + w[:, 3]
    return pts


def _chop_points(names, a):
    """names + numpyArray (chans x samples) -> (n, 3): samples = points (tx ty tz / x y z / P0..2 / px py pz, else
    the first 3 channels) or, with one sample, channel groups <name>x/y/z (FT_face_track style)."""
    import numpy as np
    a = np.asarray(a, dtype=np.float64).reshape(len(names), -1) if len(names) else np.zeros((0, 0))
    if not len(names) or a.shape[1] == 0:
        return np.zeros((0, 3))
    ns = a.shape[1]
    ix = {n: i for i, n in enumerate(names)}
    if ns > 1:
        for trip in (('tx', 'ty', 'tz'), ('x', 'y', 'z'), ('P0', 'P1', 'P2'), ('px', 'py', 'pz')):
            if trip[0] in ix and trip[1] in ix:
                z = a[ix[trip[2]]] if trip[2] in ix else np.zeros(ns)
                return np.stack([a[ix[trip[0]]], a[ix[trip[1]]], z], axis=1)
        out = np.zeros((ns, 3))
        k = min(3, len(names))
        out[:, :k] = a[:k].T
        return out
    grp, keys = {}, []
    for i, n in enumerate(names):
        if not n or n[-1].lower() not in 'xyz':
            continue
        k = n[:-1]
        if k not in grp:
            grp[k] = {}
            keys.append(k)
        grp[k][n[-1].lower()] = float(a[i, 0])
    g = [(d.get('x', 0.0), d.get('y', 0.0), d.get('z', 0.0)) for d in (grp[k] for k in keys) if 'x' in d and 'y' in d]
    return np.array(g, dtype=np.float64).reshape(-1, 3)


# ------------------------------------------------------------------------------------------------ packing (eff_rows)

def light_palette(have_lights):
    """(cs, (rows, ctl)) of the Lights page (shared palette, docs/builds/palette_convention.md), or (None, None) when
    there are no lights / the source is solid (each light keeps its own colour). Reading the pars here makes eff_rows
    recook on palette edits and follow a Palshift drive."""
    P = C()
    if not have_lights or getattr(P.par, 'Lightcolsrc', None) is None:
        return None, None
    Lg = L()
    cs = Lg.light_cs(P.par.Lightcolsrc.eval(), P.par.Lightpalpos.eval(), P.par.Lightpalspread.eval(),
                     P.par.Lightkeep.eval())
    if int(round(cs[0])) == 0:
        return None, None
    key = (P.par.Palsource.eval(), P.par.Palstops.eval(), P.par.Palmode.eval(), P.par.Palinterp.eval(),
           P.par.Palreverse.eval())
    c = STATE.get('pal')
    if c is None or c[0] != key:
        c = STATE['pal'] = (key, Lg.light_palette(key[0], key[1], key[2], key[3], 0.0, key[4]))
    rows, ctl = c[1]
    sh = P.par.Palshift.eval()
    return cs, (rows, ctl[:1] + [sh - math.floor(sh)] + ctl[2:])


def grid_texels():
    """Grid region texels for eff_rows (the shared voxel grid's layer headers, eff_grid.texels); [] while the grid is
    off. Reading the Grid page here makes eff_rows recook when it changes."""
    m = C().op('eff_grid')
    return m.module.texels() if m is not None else None


def row_index(name):
    """Packed row index of effector `name` (-1 when gone): the grid's scatter passes read the cloud's transform."""
    for i, r in enumerate(rows()):
        if r['name'] == name:
            return i
    return -1


def _grid_sync():
    """Scatter passes follow the cloud rows (eff_grid.sync); quiet when the grid COMP is not built."""
    m = C().op('eff_grid')
    if m is None or C().op('grid') is None:
        return
    try:
        m.module.sync()
    except Exception as e:
        status('grid sync: %s' % e)


PUB_ROWS = 'eff_rows_pub'           # the full buffer (29 Oct): #pub rows live; read only by consumers that select one


def rows_for(text):
    """The buffer a consumer's eff_in reads for its Effselect text: eff_rows_pub when the selection explicitly reaches
    a published row (effectors_logic.wants_pub), else eff_rows (published rows inert there: no reference from the
    consumer to the publishing COMP). Falls back to eff_rows on an effectors COMP built before eff_rows_pub."""
    c = C()
    if L().wants_pub(text, rows()) and c.op(PUB_ROWS) is not None:
        return c.op(PUB_ROWS).path
    return c.op('eff_rows').path


def _buf_state(scriptOp):
    """Per-buffer cook state (velocities, pack cache): eff_rows keeps the module-level STATE keys (as before)."""
    if scriptOp.name != PUB_ROWS:
        return STATE
    st = STATE.get('pubst')
    if st is None:
        st = STATE['pubst'] = {'prev': {}, 'pprev': {}, 't': None, 'pack': {}, 'envc': {}}
    return st


def cook_rows(scriptOp):
    """eff_rows: the packed buffer (effectors_logic.pack_buffer). Track = frame: every frame (velocity, paths, point
    sets); change: only when the list or an object changes (velocities 0).
    29 Oct (drop-in): disabled rows and, in eff_rows, #pub rows are packed as placeholders (effectors_logic.placeholder):
    their objects / refs are never read, so a consumer holds no dependency on them (the grey reference lines into
    PX_pointfx1 came from every consumer -> eff_rows -> the px_hot row's object, even while it was disabled).
    eff_rows_pub (same layout, #pub rows live) is read by the grid and by consumers that select a #pub row."""
    Lg = L()
    P = C()
    full = scriptOp.name == PUB_ROWS
    st = _buf_state(scriptOp)
    track = P.par.Track.eval() if getattr(P.par, 'Track', None) is not None else 'frame'
    if track == 'frame' and getattr(scriptOp.par, 'Frame', None) is not None:
        scriptOp.par.Frame.eval()                   # dependency: cook every frame (T-113)
    dt = 0.0
    if track == 'frame':                            # reading absTime alone makes a Script CHOP cook every frame (T-85)
        t = absTime.seconds
        dt = t - st['t'] if st['t'] is not None else 0.0
        st['t'] = t
    else:
        st['t'] = None
    live = dt > 0.0 and dt < 0.25 and track == 'frame'
    rs = rows()
    effs, seen = [], set()
    for r in rs:
        if not Lg._on(r['enabled']) or (not full and Lg.is_pub(r)):
            effs.append(Lg.effector(Lg.placeholder(r)))   # nothing of it read: no dependency
            continue
        o = source_of(r)
        if track != 'frame' and r['kind'] in Lg.OBJECT_KINDS + Lg.POINT_KINDS + Lg.NON_PROX:  # frame: Frame par
            for n in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'scale'):
                p = getattr(o.par, n, None) if o is not None else None
                if p is not None:
                    p.eval()                        # dependency: recook when the object moves (Track = change)
        w = world(o) if _is_obj(o) else Lg.identity()
        pts = points_of(r) if r['kind'] in Lg.SET_KINDS else None
        c = (w[0][3], w[1][3], w[2][3])
        if pts is not None and len(pts):
            c = tuple(float(x) for x in pts.mean(axis=0))
        nm = r['name']
        seen.add(nm)
        pv = st['prev'].get(nm)
        vel = tuple((c[k] - pv[k]) / dt for k in range(3)) if (live and pv is not None) else (0.0, 0.0, 0.0)
        st['prev'][nm] = c
        ppv = None
        if pts is not None and len(pts):
            old = st['pprev'].get(nm)
            if live and old is not None and old.shape == pts.shape:
                ppv = (pts - old) / dt
            st['pprev'][nm] = pts
        lv = light_of(o) if r['kind'] == Lg.LIGHT_KIND else None
        ev = env_of(o) if r['kind'] == Lg.ENV_KIND else None
        effs.append(Lg.effector(r, w, vel, pts, ppv, lv, ev))
    for k in list(st['prev']):
        if k not in seen:
            st['prev'].pop(k, None)
            st['pprev'].pop(k, None)
    import numpy as np
    cs, pal = light_palette(any(r['kind'] == Lg.LIGHT_KIND for r in rs))
    tex = Lg.pack_buffer(effs, cache=st['pack'], list_key=(STATE.get('cache') or (None,))[0], as_array=True,
                         light_cs=cs, light_pal=pal, grid=grid_texels(), env_cache=st['envc'])
    ch = np.ascontiguousarray(tex.T.astype(np.float32))
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = len(tex)
    for k, nm in enumerate('xyzw'):
        scriptOp.appendChan(nm).copyNumpyArray(ch[k])     # per channel keeps the names (T-81 / T-82)
    if full:
        return                                          # Status belongs to eff_rows
    n = len(rs)
    over = Lg.tags_over(rs)
    nl = int(tex[1 + n * Lg.W][0]) if len(tex) > 1 + n * Lg.W else 0
    eb = Lg.env_start(tex)
    ne = int(tex[eb][0]) if eb > 0 else 0
    npub = sum(1 for r in rs if Lg.is_pub(r))
    msg = '%d effectors, %d enabled, %d lights on, %d envs on, %d point texels%s%s' % (
        n, sum(1 for r in rs if Lg._on(r['enabled'])), nl, ne, len(tex) - int(tex[0][2]),
        ', grid on' if Lg.grid_start(tex) > 0 else '',
        ', %d published (#pub: only by name / tag)' % npub if npub else '')
    if over:
        msg += '; %d tags over the %d-tag limit are ignored' % (over, Lg.MAX_TAGS)
    status(msg)


# ------------------------------------------------------------------------------------------------ objects

def _par_page(o, name):
    return next((pg for pg in o.customPages if pg.name == name), None) or o.appendCustomPage(name)


def _path_pars(o):
    if getattr(o.par, 'Pathshape', None) is not None:
        return
    Lg = L()
    pg = _par_page(o, 'Path')
    m = pg.appendMenu('Pathshape', label='Path shape')[0]
    m.menuNames, m.menuLabels = Lg.names(Lg.PATHS), Lg.labels(Lg.PATHS)
    for nm, lab, d in (('Pathspeed', 'Speed (cycles / s)', 0.1), ('Pathphase', 'Phase (cycles)', 0.0)):
        p = pg.appendFloat(nm, label=lab)[0]
        p.default = p.val = d
        p.normMin, p.normMax = -2, 2
    for nm, lab, d in (('Pathsize', 'Size (half extents)', (1.0, 0.5, 1.0)), ('Pathcentre', 'Centre', (0.0, 0.0, 0.0))):
        for p, v in zip(pg.appendXYZ(nm, label=lab), d):
            p.default = p.val = v
            p.normMin, p.normMax = -5, 5
    pg.appendCHOP('Pathchop', label='Path CHOP (tx ty tz)')
    for k, ax in enumerate(('tx', 'ty', 'tz')):
        p = getattr(o.par, ax)
        p.expr = "parent().op('eff_rt').module.path_xyz(me, %d)" % k
        p.mode = ParMode.EXPRESSION


GIZ = '_giz'                       # a light's gizmo = Geometry COMP <light name>_giz parented to the light
LIGHT_PAR_KEYS = {'type': 'Ltype', 'intensity': 'dimmer', 'att_on': 'attenuated', 'att_start': 'attenuationstart',
                  'att_end': 'attenuationend', 'att_exp': 'attenuationexp', 'cone_angle': 'coneangle',
                  'cone_delta': 'conedelta', 'cone_roll': 'coneroll', 'area_w': 'Lareaw', 'area_h': 'Lareah'}


def _light_pars(o):
    """Effector page on an own Light COMP: Ltype (point / spot / area / directional; drives TD's lighttype), area
    size. First time only: effector defaults (attenuated, range 4, cone 45 / 10, 1.5 up, pointing
    down; TD starts a Light COMP at tz 10 and clamps attenuationstart to >= 0.001)."""
    if getattr(o.par, 'Ltype', None) is not None:
        return
    Lg = L()
    pg = _par_page(o, 'Effector')
    m = pg.appendMenu('Ltype', label='Light type')[0]
    m.menuNames, m.menuLabels = Lg.names(Lg.LTYPES), Lg.labels(Lg.LTYPES)
    for nm, lab, d in (('Lareaw', 'Area width (local x)', Lg.LIGHT_DEFAULTS['area_w']),
                       ('Lareah', 'Area height (local y)', Lg.LIGHT_DEFAULTS['area_h'])):
        p = pg.appendFloat(nm, label=lab)[0]
        p.default = p.val = d
        p.normMin, p.normMax = 0, 10
    lt = o.par.lighttype
    lt.expr = "%r.get(me.par.Ltype.eval(), 'point')" % (Lg.TD_LIGHTTYPE,)
    lt.mode = ParMode.EXPRESSION
    D = Lg.LIGHT_DEFAULTS
    for n, v in (('dimmer', D['intensity']), ('attenuated', D['att_on']), ('attenuationstart', D['att_start']),
                 ('attenuationend', D['att_end']), ('attenuationexp', D['att_exp']), ('coneangle', D['cone_angle']),
                 ('conedelta', D['cone_delta']), ('coneroll', D['cone_roll']), ('tx', 0.0), ('ty', 1.5),
                 ('tz', 0.0), ('rx', -90.0)):                   # a new Light COMP starts at tz 10 (live b4)
        p = getattr(o.par, n, None)
        if p is not None:
            p.val = v


def set_light(o, **vals):
    """Set light values on a Light COMP by effectors_logic.light_values keys (type, colour, intensity, att_*, cone_*,
    area_w / area_h). Returns the keys it could not set."""
    bad = []
    for k, v in vals.items():
        if k == 'colour':
            for n, x in zip(('cr', 'cg', 'cb'), tuple(v)[:3]):
                getattr(o.par, n).val = float(x)
            continue
        p = getattr(o.par, LIGHT_PAR_KEYS.get(k, ''), None)
        if p is None:
            bad.append(k)
        else:
            p.val = v
    return bad


def giz_val(g, key):
    """Gizmo SOP expressions (inside <light>_giz): values of the light it is parented to."""
    lo = g.par.parentobject.eval() if g is not None else None
    if lo is None or not hasattr(lo, 'par'):
        return {'type': 0, 'spotr': 0.2, 'areaw': 1.0, 'areah': 0.1}.get(key, 0)
    if key == 'type':
        p = getattr(lo.par, 'Ltype', None)
        return p.menuIndex if p is not None else {'cone': 1, 'distant': 3}.get(_pv(lo, 'lighttype', 'point'), 0)
    if key == 'spotr':                           # cone of length 1: radius at the cone edge (angle / 2)
        return math.tan(math.radians(min(85.0, 0.5 * _pv(lo, 'coneangle', 45.0))))
    if key == 'areaw':
        return max(1e-3, _pv(lo, 'Lareaw', 1.0))
    if key == 'areah':
        return max(1e-3, _pv(lo, 'Lareah', 0.1))
    return 0


def _light_giz(o, show):
    """Gizmo of light o: Geometry COMP <name>_giz (Xform parent = the light, so it follows it) with a Switch SOP of 4
    wire shapes by Ltype: point = small sphere, spot = cone (length 1, apex at the light, along -Z), area = the
    w x h rectangle, directional = a thin rod along -Z."""
    c = C()
    gn = o.name + GIZ
    g = c.op(gn)
    if g is not None and g.OPType != 'geometryCOMP':
        _sd(g)
        g = None
    if g is None:
        g = c.create(geometryCOMP, gn)
        for ch in list(g.children):
            _sd(ch)
    g.store('jz_effector', True)
    g.store('jz_light_giz', o.name)
    g.par.parentxformsrc = 'specify'
    g.par.parentobject = o.name
    V = "parent(2).op('eff_rt').module.giz_val(parent(), '%s')"

    def sop(cls, name):
        s = g.op(name)
        if s is not None and s.OPType != cls.__name__:
            _sd(s)
            s = None
        return s or g.create(cls, name)
    pt = sop(sphereSOP, 'g_point')
    pt.par.radx = pt.par.rady = pt.par.radz = 0.08
    sp = sop(tubeSOP, 'g_spot')
    sp.par.orient = 'z'
    sp.par.height = 1.0
    sp.par.tz = -0.5
    sp.par.rad2.expr = V % 'spotr'                 # rad2 = the -z end (live b4 31550: rad1 sits at +z)
    sp.par.rad2.mode = ParMode.EXPRESSION
    sp.par.rad1.mode = ParMode.CONSTANT
    sp.par.rad1 = 0.001
    ar = sop(gridSOP, 'g_area')
    ar.par.orient = 'xy'
    ar.par.rows = ar.par.cols = 2
    for n, k in (('sizex', 'areaw'), ('sizey', 'areah')):
        getattr(ar.par, n).expr = V % k
        getattr(ar.par, n).mode = ParMode.EXPRESSION
    dr = sop(tubeSOP, 'g_dir')
    dr.par.orient = 'z'
    dr.par.rad1 = dr.par.rad2 = 0.015
    dr.par.height = 0.8
    dr.par.tz = -0.4
    sw = sop(switchSOP, 'shape')
    for i, s in enumerate((pt, sp, ar, dr)):
        cur = sw.inputConnectors[i].connections if i < len(sw.inputConnectors) else []
        if not (cur and cur[0].owner is s):
            s.outputConnectors[0].connect(sw.inputConnectors[i])
    sw.par.input.expr = V % 'type'                 # Switch SOP's index par is `input` (31550, live b4)
    sw.par.input.mode = ParMode.EXPRESSION
    for s in (pt, sp, ar, dr):
        s.render = s.display = False
    sw.render = sw.display = True
    g.par.material = 'giz_mat'
    g.render = g.display = show
    g.viewer = True
    g.nodeX, g.nodeY = o.nodeX, o.nodeY - 150
    g.comment = 'Gizmo of light %s (follows it; shape by its Ltype).' % o.name
    return g


def _env_pars(o):
    """Effector page on an env object (first time only): map, gain, panel size, probe, two-sided, samples."""
    if getattr(o.par, 'Envmap', None) is not None:
        return
    Lg = L()
    D = Lg.ENV_DEFAULTS
    pg = _par_page(o, 'Effector')
    m = pg.appendMenu('Envmap', label='Env map')[0]
    m.menuNames, m.menuLabels = Lg.names(Lg.ENVMAPS), Lg.labels(Lg.ENVMAPS)
    m.default = m.val = D['map']
    for nm, lab, d, hi in (('Envgain', 'Gain', D['gain'], 4), ('Envw', 'Screen width (local x)', D['w'], 20),
                           ('Envh', 'Screen height (local y)', D['h'], 20)):
        p = pg.appendFloat(nm, label=lab)[0]
        p.default = p.val = d
        p.normMin, p.normMax = 0, hi
    for p, v in zip(pg.appendXYZ('Envprobe', label='Probe (world point the light is measured at)'), D['probe']):
        p.default = p.val = v
        p.normMin, p.normMax = -5, 5
    p = pg.appendToggle('Envtwosided', label='Screen lights both sides')[0]
    p.default = p.val = D['twosided']
    p = pg.appendInt('Envsamples', label='Samples across (fit width)')[0]
    p.default = p.val = D['samples']
    p.normMin, p.normMax = 4, 128
    for n, v in (('tx', 0.0), ('ty', 1.5), ('tz', -3.0)):          # a screen behind the scene, facing it (+Z)
        getattr(o.par, n).val = v


def _env_ops(o, r):
    """Inside an env object: env_src (Select TOP = the row's ref TOP) -> env_fit (Resolution TOP, env_fit_size,
    32-bit float, mipmap smoothing = area average) -> env_px (TOP to CHOP, downloadtype nextframe: no GPU stall);
    eff_rows reads env_px (env_of). Shape = the w x h panel (Grid SOP in local XY, sized by Envw / Envh)."""
    def mk(cls, name):
        x = o.op(name)
        if x is not None and x.OPType != cls.__name__:
            _sd(x)
            x = None
        return x or o.create(cls, name)

    def tr(x, n, v):
        p = getattr(x.par, n, None)
        if p is not None:
            try:
                p.val = v
            except Exception:
                pass
    src = mk(selectTOP, 'env_src')
    ref = _find(r.get('ref'))
    src.par.top = ref.path if (ref is not None and ref.family == 'TOP') else ''  # dropin: scene ref (the user's TOP)
    fit = mk(resolutionTOP, 'env_fit')
    if not (fit.inputs and fit.inputs[0] is src):
        src.outputConnectors[0].connect(fit.inputConnectors[0])     # T-00c: through the input connector
    tr(fit, 'outputresolution', 'custom')
    for n, k in (('resolutionw', 0), ('resolutionh', 1)):
        p = getattr(fit.par, n)
        p.expr = "parent(2).op('eff_rt').module.env_fit(parent(), %d)" % k
        p.mode = ParMode.EXPRESSION
    tr(fit, 'format', 'rgba32float')
    tr(fit, 'inputfiltertype', 'mipmap')               # downsample = area average (LIVE CHECK EV1)
    px = mk(toptoCHOP, 'env_px')
    px.par.top = fit.name
    tr(px, 'downloadtype', 'nextframe')
    tr(px, 'crop', 'full')                              # default 'row' = one row only (live b2 31550)
    tr(px, 'outputcolorspace', 'passthrough')           # values as they are (float data, no colour transform)
    for k, x in enumerate((src, fit, px)):
        x.nodeX, x.nodeY = 200 * k, -200
        x.viewer = True
    s = o.op('shape')
    if s is not None and s.OPType == 'gridSOP':
        s.par.orient = 'xy'
        s.par.rows = s.par.cols = 2
        for n, pn in (('sizex', 'Envw'), ('sizey', 'Envh')):
            p = getattr(s.par, n)
            p.expr = "parent().par.%s.eval()" % pn
            p.mode = ParMode.EXPRESSION


def make_object(r):
    """The effector's object in /project1/effectors (idempotent). Object kinds = Geometry COMP + unit wire shape (the
    SDF is the unit shape x the object's transform); null / path / point sets = Geometry COMP with a small wire box
    (the gizmo; for point sets it is the points' space); light = a Light COMP (+ its gizmo <name>_giz); camera, or an
    object / light kind with `ref` = no own object."""
    Lg = L()
    k = r['kind']
    if k == 'camera' or (follows_ref(k) and r.get('ref')):
        return None
    c = C()
    o = c.op(r['name'])
    want_type = 'lightCOMP' if k == Lg.LIGHT_KIND else 'geometryCOMP'
    if o is not None and o.OPType != want_type:
        _sd(o)
        o = None
    if k == Lg.LIGHT_KIND:
        if o is None:
            o = c.create(lightCOMP, r['name'])
            o.store('jz_effector', True)
        _light_pars(o)
        o.viewer = True
        _light_giz(o, Lg._on(r.get('gizmo', '1')))
        o.comment = ('Light effector %s (tags: %s): a TD Light COMP (Effector page: type, area; Light '
                     'page: colour, dimmer, attenuation, cone). Move / rotate it; it shines along its -Z.' %
                     (r['name'], r.get('tags') or '-'))
        return o
    if o is None:
        o = c.create(geometryCOMP, r['name'])
        for ch in list(o.children):
            _sd(ch)
        o.store('jz_effector', True)
    want = gridSOP if k == Lg.ENV_KIND else OBJ_SOPS.get(k, boxSOP)
    s = o.op('shape')
    if s is not None and s.OPType != want.__name__:
        _sd(s)
        s = None
    if s is None:
        s = o.create(want, 'shape')
        if k == 'plane':
            s.par.orient = 'zx'
            s.par.sizex, s.par.sizey = 1, 1
        elif k == 'capsule':
            s.par.rad1, s.par.rad2 = 0.25, 0.25
            s.par.height = 1.0
        elif k == 'torus':
            s.par.radx, s.par.rady = 0.5, 0.15
        elif k == 'sphere':
            s.par.radx, s.par.rady, s.par.radz = 0.5, 0.5, 0.5
        elif k == Lg.ENV_KIND:
            pass                                       # Grid SOP panel, sized by _env_ops (no sizez, live b2)
        elif k not in Lg.OBJECT_KINDS:
            s.par.sizex = s.par.sizey = s.par.sizez = GIZMO
    s.render = s.display = True
    o.par.material = 'giz_mat'                     # sibling Wireframe MAT (COMP OP pars resolve beside it, T-81)
    o.render = o.display = Lg._on(r.get('gizmo', '1'))
    o.viewer = True
    if k == 'path':
        _path_pars(o)
    if k == Lg.CLOUD_KIND:
        src = o.op('cloud_src')
        if src is not None and src.OPType != 'selectTOP':
            _sd(src)
            src = None
        src = src or o.create(selectTOP, 'cloud_src')
        ref = _find(r.get('ref'))
        src.par.top = ref.path if (ref is not None and ref.family == 'TOP') else ''  # dropin: scene ref (the user's TOP)
        src.viewer = True
        src.nodeX, src.nodeY = 0, -200
        o.comment = ('Cloud effector %s (tags: %s): ref = a TOP of points (rgb = xyz in this object space, alpha > '
                     'Gridalpha = valid) -> the shared grid distance field (Grid page Gridon). Proximity for '
                     'consumers that read the grid (PXE_GRID).' % (r['name'], r.get('tags') or '-'))
        return o
    if k == Lg.ENV_KIND:
        _env_pars(o)
        _env_ops(o, r)
        o.comment = ('Env light %s (tags: %s): ref = any TOP (the LED wall / visuals) -> 9 SH coefficients in '
                     'eff_rows. Map screen = this w x h panel lights the scene along its +Z; equirect / ambient = '
                     'all around the probe. Effector page: map, gain, size, probe, samples.' %
                     (r['name'], r.get('tags') or '-'))
        return o
    o.comment = ('Effector %s (%s, tags: %s). Move / rotate / scale it; values in eff_list.' %
                 (r['name'], k, r.get('tags') or '-'))
    return o


def sync_objects():
    """Objects for every row (missing made, gizmo flag applied); objects of removed rows go (safe_destroy)."""
    Lg = L()
    keep = set()
    for r in rows():
        o = make_object(r)
        if o is not None:
            keep.add(o.name)
            if r['kind'] == Lg.LIGHT_KIND:
                keep.add(o.name + GIZ)
    for o in list(C().children):
        if o.valid and o.OPType in ('geometryCOMP', 'lightCOMP') and o.name not in keep and \
                o.fetch('jz_effector', False, search=False):
            _sd(o)
    for n in keep:
        C().op(n).store('jz_effector', True)
    _grid_sync()
    return sorted(keep)


# ------------------------------------------------------------------------------------------------ list edits

def add(kind='sphere', name=None, tags='', ref='', **vals):
    """New effector (row + object). Returns its name. A light also takes light values (effectors_logic.light_values
    keys: type, colour, intensity, att_on / att_start / att_end / att_exp, cone_angle / cone_delta / cone_roll,
    area_w / area_h), set on its own Light COMP; tag `light` is added. An env (ref = a TOP) takes env values (map,
    gain, w, h, probe, twosided, samples); tag `env` is added."""
    Lg = L()
    lvals = dict((k, vals.pop(k)) for k in list(vals) if k in Lg.LIGHT_DEFAULTS or k == 'type')
    evals = dict((k, vals.pop(k)) for k in list(vals) if k in Lg.ENV_DEFAULTS)
    for kk, tg in ((Lg.LIGHT_KIND, 'light'), (Lg.ENV_KIND, 'env')):
        if kind == kk and tg not in str(tags).replace(',', ' ').split():
            tags = (str(tags) + ' ' + tg).strip()
    rs, nm = Lg.add_row(rows(), kind, name, tags=tags, ref=ref, **vals)
    write_rows(rs)
    o = make_object(rs[-1])
    if o is not None:
        o.store('jz_effector', True)
        o.nodeX, o.nodeY = 200 * (len(rs) - 1), -400
        if kind == Lg.LIGHT_KIND:
            bad = set_light(o, **lvals)
            if bad:
                status('add %s: unknown light values %s' % (nm, ' '.join(bad)))
            g = C().op(nm + GIZ)
            if g is not None:
                g.nodeX, g.nodeY = o.nodeX, o.nodeY - 150
        if kind == Lg.ENV_KIND and evals:
            bad = set_env(o, **evals)
            if bad:
                status('add %s: unknown env values %s' % (nm, ' '.join(bad)))
    if kind == Lg.CLOUD_KIND:
        _grid_sync()                                    # its cloud_src exists now (bump ran before the object)
    return nm


def remove(name):
    write_rows(L().remove_row(rows(), name))
    o = C().op(name)
    if o is not None and o.fetch('jz_effector', False, search=False):
        _sd(o)
    g = C().op(name + GIZ)
    if g is not None and g.fetch('jz_light_giz', '', search=False) == name:
        _sd(g)
    return name


def duplicate(name, new=None):
    """Copy of an effector: same row values, a copy of its object (transform kept, moved +0.25 in x)."""
    rs, nm = L().duplicate_row(rows(), name, new)
    write_rows(rs)
    src = C().op(name)
    if src is not None and src.fetch('jz_effector', False, search=False):
        o = C().copy(src, name=nm)
        o.store('jz_effector', True)
        if o.par.tx.mode == ParMode.CONSTANT:
            o.par.tx = o.par.tx.eval() + 0.25
        o.nodeX, o.nodeY = src.nodeX + 200, src.nodeY - 150
        if o.OPType == 'lightCOMP':
            make_object([r for r in rs if r['name'] == nm][0])      # its own gizmo
    else:
        make_object([r for r in rs if r['name'] == nm][0])
    return nm


def rename(name, new):
    rs, nm = L().rename_row(rows(), name, new)
    o = C().op(name)
    write_rows(rs)
    if o is not None and nm != name:
        o.name = nm
        g = C().op(name + GIZ)
        if o.OPType == 'lightCOMP' and g is not None:
            g.name = nm + GIZ
            g.par.parentobject = nm
            g.store('jz_light_giz', nm)
    _grid_sync()                                        # a renamed cloud: its scatter pass follows
    return nm


def check_ref(kind, ref):
    """None if `ref` can tie an effector of this kind, else why not. Empty = untie. Kinds that do not follow an
    object (pts / actor / env / cloud) take any path (their ref is a CHOP / SOP / TOP, checked where it is read)."""
    ref = str(ref or '').strip()
    if not ref or not follows_ref(kind):
        return None
    o = _find(ref)
    if o is None:
        return 'no op at %s' % ref
    if o.path == C().path or o.path.startswith(C().path + '/'):
        return '%s is inside /project1/effectors (an effector object, not a rig Null)' % ref
    if kind == L().LIGHT_KIND and o.OPType != 'lightCOMP':
        return 'a light effector ties to a Light COMP (%s is a %s)' % (ref, o.OPType)
    if not _is_obj(o):
        return '%s is not an object COMP (Null / Geometry / Light)' % ref
    return None


def set_ref(name, ref):
    """Tie effector `name` to an object COMP (its transform drives the effector; the effector's own object is
    hidden, and removed by the next Sync), or untie it (ref '' / ' ': the own object comes back). -> the new ref."""
    ref = str(ref or '').strip()
    r = [x for x in rows() if x['name'] == name]
    if not r:
        raise ValueError('no effector %s' % name)
    why = check_ref(r[0]['kind'], ref)
    if why:
        raise ValueError(why)
    o = _find(ref) if ref else None
    if o is not None:
        ref = o.path                                   # stored absolute: the same op from every consumer
    set_value(name, 'ref', ref)
    own = C().op(name)
    if ref and follows_ref(r[0]['kind']) and own is not None and own.fetch('jz_effector', False, search=False):
        own.render = own.display = False               # the ref's own look shows where the effector is
    return ref


def enable(name, on=True):
    write_rows(L().set_value(rows(), name, 'enabled', '1' if on else '0'))


def set_value(name, col, value):
    write_rows(L().set_value(rows(), name, col, value))
    if col in ('gizmo', 'kind', 'ref'):
        r = [x for x in rows() if x['name'] == name]
        if r:
            make_object(r[0])
            _grid_sync()


# ------------------------------------------------------------------------------------------------ dropdowns (T-233)

def _objs(comp, parents=False, cls=None):
    """Names of the object COMPs inside comp (and in its parent: MX / GEN resolve names there too), comp excluded."""
    out = []
    for base in ([comp, comp.parent()] if parents and comp.parent() is not None else [comp]):
        for o in base.findChildren(maxDepth=1):
            if o is comp or not o.isCOMP or not hasattr(type(o), 'worldTransform'):      # class-level check (T-115)
                continue
            if (cls is None or isinstance(o, cls)) and o.name not in out:
                out.append(o.name)
    return out


OWN_KINDS = {'Target': 'target', 'Addref': 'refs', 'Refto': 'refs'}     # local dropdowns here; else 'select'


def ref_menu(ML, comp, root='/project1'):
    """Refto / Addref items: '(none)' + every Null / Geometry / Light COMP under root by path (this COMP's own
    effector objects and gizmos excluded), the Target's current ref marked. Built on a menu read only (findChildren,
    memoised 0.5 s: names + labels are two reads), never per frame. Wall clock, not absTime: a time read inside a
    menuSource evaluation could make it time-dependent (T-85 class)."""
    import time
    f = int(time.monotonic() * 2.0)
    m = STATE.get('refmenu')
    cur = ''
    tp = getattr(comp.par, 'Target', None)
    if tp is not None:
        r = [x for x in rows() if x['name'] == tp.eval().strip()]
        cur = r[0].get('ref', '') if r else ''
    if m is not None and m[0] == (f, cur):
        return m[1]
    base = op(root)
    mine = C().path
    found = {}
    # the op classes by plain name: in a DAT module they are builtins, not in globals(); findChildren(type=
    # geometryCOMP) also returns Null and Light COMPs (subclasses), so the tag comes from OPType (live b2 31550)
    tags = {'nullCOMP': 'null', 'geometryCOMP': 'geo', 'lightCOMP': 'light'}
    for cls in (nullCOMP, geometryCOMP, lightCOMP):
        if base is None:
            continue
        for o in base.findChildren(type=cls):
            if o.OPType not in tags or o.path == mine or o.path.startswith(mine + '/'):
                continue
            found[o.path] = tags[o.OPType]
    paths = sorted(found)
    short = lambda p: p[len(root) + 1:] if p.startswith(root + '/') else p
    labels = ['%s (%s)%s' % (short(p), found[p], ' = Target now' if p == cur else '') for p in paths]
    out = ML.name_menu(paths, labels, none=True)
    STATE['refmenu'] = ((f, cur), out)
    return out


def menu(comp, name, kind=None):
    """Items of a live dropdown (menu_logic.local_source / shared_source, T-233), built on each menu read: never per
    frame. kind: 'target' (one list name), 'select' (all / names / #tags helper: Effselect, Paintselect,
    Eraseselect), 'objects@' (GN_physarum / GN_reaction_diffusion Effectors: own Nulls, eff*, @shared), 'objects'
    (MX / GEN: object COMPs here and in the parent), 'geos' (Geometry COMPs inside). Never raises."""
    ML = C().op('menu_logic').module
    try:
        kind = kind or OWN_KINDS.get(name, 'select')
        if kind == 'refs':
            return ref_menu(ML, comp)
        rs = rows()
        names = [r['name'] for r in rs]
        tags = sorted(set(t for r in rs for t in str(r.get('tags', '')).replace(',', ' ').split()))
        if kind == 'target':
            return ML.name_menu(names, ['%s (%s%s)' % (r['name'], r.get('kind', ''),
                                                       '' if L()._on(r.get('enabled', '1')) else ', off') for r in rs])
        cur = getattr(comp.par, name).eval()
        if kind == 'select':
            return ML.select_menu(cur, names, tags, kinds=dict((r['name'], r.get('kind', '')) for r in rs))
        if kind == 'objects@':
            return ML.select_menu(cur, _objs(comp) + ['@' + n for n in names] + ['@#' + t for t in tags], (),
                                  all_word=None, extra=[('eff*', 'eff* (every eff Null here)'),
                                                        ('@all', '@all (the shared list)')])
        if kind == 'objects':
            return ML.select_menu(cur, _objs(comp, parents=True), (), all_word=None)
        if kind == 'geos':
            return ML.select_menu(cur, _objs(comp, cls=geometryCOMP), (), all_word=None)
    except Exception:
        pass
    return ML.Menu()


def on_pulse(par):
    P = par.owner
    try:
        n = par.name
        tgt = P.par.Target.eval().strip()
        if n == 'Add':
            ap = getattr(P.par, 'Addref', None)
            ref = ap.eval().strip() if ap is not None else ''
            kind = P.par.Addkind.eval()
            why = check_ref(kind, ref)
            if why:
                raise ValueError(why)
            o = _find(ref) if (ref and follows_ref(kind)) else None
            nm = add(kind, P.par.Addname.eval().strip() or None, P.par.Addtags.eval().strip(),
                     o.path if o is not None else ref)
            P.par.Target = nm
            if ref:
                status('added %s tied to %s' % (nm, ref))
        elif n == 'Setref' and tgt:
            rp = getattr(P.par, 'Refto', None)
            ref = set_ref(tgt, rp.eval() if rp is not None else '')
            status('%s tied to %s' % (tgt, ref) if ref else '%s untied (own object)' % tgt)
        elif n == 'Remove' and tgt:
            remove(tgt)
        elif n == 'Duplicate' and tgt:
            P.par.Target = duplicate(tgt)
        elif n == 'Rename' and tgt:
            P.par.Target = rename(tgt, P.par.Newname.eval())
        elif n == 'Toggle' and tgt:
            r = [x for x in rows() if x['name'] == tgt]
            if r:
                enable(tgt, not L()._on(r[0]['enabled']))
        elif n == 'Sync':
            sync_objects()
    except Exception as e:
        status('%s failed: %s' % (par.name, e))
