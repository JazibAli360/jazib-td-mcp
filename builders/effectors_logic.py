"""effectors_logic: pure logic of the shared effector list /project1/effectors (px_requirements items 11 + 12).

No td import. Copied into the Text DAT `eff_logic` by builders/effectors.py; tests test/test_effectors.py; doc
docs/builds/effectors.md. The maths is PX's (px_logic affine helpers, EFF_SDF unit shapes, falloff names) and the
GLSL side is builders/glsl/px_common.glsl (packed section, `#ifdef PXE_ROWS`), shared by every consumer.

The list is a Table DAT `eff_list` (COLS). Effector i (table order, disabled rows included so ids stay stable) is
packed into ONE vec4 texture buffer (Script CHOP `eff_rows`: channels x y z w, one sample per texel):
  texel 0          header (count N, row width W, points start texel, version)
  texel 1 + i*W + t  row of effector i, t = 0..W-1 (W = 10):
    0..2 inverse world matrix rows (world -> local)   3 (sdf type, local size xyz)
    4 (world centre xyz, world scale)                 5 (world up axis xyz, speed units/s)     [0..5 = PX uE rows]
    6 (velocity xyz, enabled)                         7 (falloff shape, radius, exponent, gain)
    8 (tag bits, kind index, points start texel, point count)
    9 (point radius, point mode 0 nearest / 1 density, density full, id = i + 1)
  lights (version >= 2), at L0 = 1 + N*W (header W): texel L0 = (light count K, LW, env base E, grid base G), then K
    blocks of LW = 7 texels, one per ENABLED `light` row in table order (see light_block): colour, position + type,
    forward + row, attenuation, cone, area half axes. Light rows are never proximity effectors (their row texel 6.w
    = 0), so a v1 consumer (W = 10 compiled in) reads a v2 buffer unchanged.
  env (version >= 3; E = 0: none): texel E = (env count M, EW, 0, 0), then M blocks of EW = 10 texels, one per ENABLED
    `env` row (SA6 screen-as-light, env_block): (gain, row index, map, 0) + 9 SH irradiance coefficients (rgb, 0).
  grid (version >= 3; G = 0: none): the shared voxel grid layers' header (effectors_grid_logic.grid_texels).
    E and G sit in the light header's z / w, which v2 readers never read: a v2 consumer reads a v3 buffer unchanged.
  points (point-set kinds), 2 texels each from the points start: (xyz, valid) (velocity xyz, speed)
Any number of effectors: consumers loop to the header count; adding / removing one changes data only (no recompile).
Consumers select by name or tag: sel_vec() -> (tag mask, all, id0..id3) for the uniforms uEffSel / uEffIds.
ASCII only.
"""
import math
import os
import sys

_BUILDERS = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
if os.path.isdir(_BUILDERS) and _BUILDERS not in sys.path:
    sys.path.insert(0, _BUILDERS)
import px_logic as PXL  # noqa: E402  (affine maths, unit SDF shapes, falloff names: one source of truth)

VERSION = 3               # 2 = light region after the rows (v1 readers ignore it); 3 = env + grid regions after it
W = 10                    # texels per effector row (PXE_W in px_common.glsl)
LW = 7                    # texels per light block (PXE_LW)
EW = 10                   # texels per env block (PXE_EW): (gain, row, map, 0) + 9 SH coefficients
ENV_MAX = 64              # envs a shader loop visits (PXE_ENV_MAX; a bound, not a list cap)
LIGHT_MAX = 256           # lights a shader loop visits (PXE_LIGHT_MAX; a bound, not a list cap)
HEADER = 1                # header texels before row 0
PTS_TEXELS = 2            # texels per point
PTS_MAX = 4096            # points per set (PXE_PTS_MAX, brute force per sample)
MAX_TAGS = 23             # user tag bits (bits 0..22); bit 23 = OWN_BIT; all survive a float32 exactly
OWN_BIT = 1 << MAX_TAGS   # 29 Oct (drop-in round): set on every row that is NOT published (#pub), so 'all' can mean
                          # "the user's own effectors" as a plain tag mask (data only: no consumer recompiles)
PUB_TAG = 'pub'           # a row another COMP publishes (PX hot points, FX_track `track`, a COMP's cloud / point set)
MAX_IDS = 4               # explicit names per consumer (uEffIds); groups use tags
SD_PTS = 6                # sdf type of a point-set row (PX types 0..5 are objects)
SD_GRID = 7               # sdf type of a cloud row (shared grid distance field; PXE_SD_GRID)

# kind, label, what it is
KINDS = [('sphere', 'Sphere'), ('box', 'Box'), ('plane', 'Plane'), ('capsule', 'Capsule'), ('torus', 'Torus'),
         ('null', 'Null (point)'), ('pts', 'Point set (CHOP / SOP)'), ('path', 'Path (moving point)'),
         ('camera', 'Camera (point at a camera)'), ('actor', 'Actor (points of another COMP)'),
         ('light', 'Light (TD Light COMP: point / spot / area / directional)'),
         ('env', 'Env light (SH9 from any TOP: screen / equirect / ambient)'),
         ('cloud', 'Cloud (point set > 4096 from a TOP, via the voxel grid field)')]   # append only: index = KINDS
OBJECT_KINDS = ('sphere', 'box', 'plane', 'capsule', 'torus')     # Geometry COMP with a wire shape = the SDF
POINT_KINDS = ('null', 'path', 'camera')                          # one point (sdf type 0)
SET_KINDS = ('pts', 'actor')                                      # point sets
LIGHT_KIND = 'light'                                              # a TD Light COMP (own, or `ref` = any Light COMP)
ENV_KIND = 'env'                                                  # SA6: ref = any TOP -> 9 SH irradiance coefficients
NON_PROX = (LIGHT_KIND, ENV_KIND)                                 # packed with enabled 0: never proximity effectors
CLOUD_KIND = 'cloud'      # K36 / GE2: ref = a TOP of points (rgb xyz in the object's space); proximity only for
                          # consumers that read the grid (PXE_GRID): texel 6.w = 0, its on flag in texel 3.y
# Env maps: how the TOP's pixels map to directions seen from the probe point
ENVMAPS = [('screen', 'Screen (a w x h panel: the object, shining along its +Z)'),
           ('equirect', 'Equirect (lat-long around the probe; object rotation turns it)'),
           ('ambient', 'Ambient (the image mean from every direction)')]
ENV_DEFAULTS = {'map': 'screen', 'gain': 1.0, 'w': 1.6, 'h': 0.9, 'probe': (0.0, 1.0, 0.0), 'twosided': False,
                'samples': 32}
# Light types (custom par Ltype on the Light COMP) -> packed index; TD's own lighttype for native lighting (TD 31550
# has point / cone / distant only: an area light lights TD MATs as a point light at its centre).
LTYPES = [('point', 'Point'), ('spot', 'Spot (cone)'), ('area', 'Area / bar (w x h)'), ('directional', 'Directional')]
TD_LIGHTTYPE = {'point': 'point', 'spot': 'cone', 'area': 'point', 'directional': 'distant'}
TD_TO_LTYPE = {'point': 'point', 'cone': 'spot', 'distant': 'directional'}
# Shading models of pxeLight (mode.x)
LMODELS = [('halflambert', 'Half-Lambert (soft)'), ('lambert', 'Lambert'), ('wrap', 'Wrap'),
           ('glow', 'No normal (glow by distance)')]
LIGHT_DEFAULTS = {'type': 'point', 'colour': (1.0, 1.0, 1.0), 'intensity': 1.0, 'att_on': True, 'att_start': 0.0,
                  'att_end': 4.0, 'att_exp': 1.0, 'cone_angle': 45.0, 'cone_delta': 10.0, 'cone_roll': 1.0,
                  'area_w': 1.0, 'area_h': 0.1}
FALLOFFS = PXL.FALLOFFS
COMBINES = PXL.COMBINES
PTMODES = [('nearest', 'Nearest point'), ('density', 'Soft density')]
PATHS = [('circle', 'Circle'), ('line', 'Line (ping-pong)'), ('lissajous', 'Lissajous'), ('figure8', 'Figure 8'),
         ('noise', 'Noise wander'), ('chop', 'CHOP (tx ty tz)')]
TRACK = [('frame', 'Every frame (velocity, paths, point sets)'), ('change', 'When they change (static rigs)')]

COLS = ['name', 'kind', 'tags', 'enabled', 'falloff', 'radius', 'exponent', 'gain', 'gizmo', 'ref', 'mode']
DEFAULTS = {'kind': 'sphere', 'tags': '', 'enabled': '1', 'falloff': 'smooth', 'radius': '0.5', 'exponent': '1',
            'gain': '1', 'gizmo': '1', 'ref': '', 'mode': 'nearest'}
SEED = [('sphere1', 'sphere', 'demo'), ('box1', 'box', 'demo')]
# falloff -> the 2D sims' own menus (GN_reaction_diffusion / GN_physarum: gauss linear hard ring)
FALL_TO_2D = {'smooth': 0, 'gaussian': 0, 'linear': 1, 'step': 2, 'core': 2, 'shell': 3}


def names(menu):
    return [m[0] for m in menu]


def labels(menu):
    return [m[1] for m in menu]


def menu_index(menu, val):
    ns = names(menu)
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return int(val)
    return ns.index(val) if val in ns else 0


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(d)


def _on(v):
    return str(v).strip().lower() not in ('', '0', 'false', 'off', 'no')


# ------------------------------------------------------------------------------------------------ the list

def parse_table(cells):
    """cells = [[header...], [row...], ...] (Table DAT values) -> list of row dicts (all COLS, defaults filled)."""
    if not cells:
        return []
    head = [str(h).strip() for h in cells[0]]
    out = []
    for r in cells[1:]:
        d = dict(DEFAULTS)
        for k, h in enumerate(head):
            if h in COLS and k < len(r):
                d[h] = str(r[k]).strip()
        d['name'] = d.get('name', '').strip()
        if d['name']:
            out.append(d)
    return out


def table_cells(rows):
    return [list(COLS)] + [[str(r.get(c, DEFAULTS.get(c, ''))) for c in COLS] for r in rows]


def valid_name(name):
    """TD op names: letters, digits, underscore; not starting with a digit."""
    s = ''.join(ch if (ch.isalnum() or ch == '_') else '_' for ch in str(name).strip())
    if not s:
        return ''
    return ('e' + s) if s[0].isdigit() else s


def next_name(kind, taken):
    k = 1
    while '%s%d' % (kind, k) in taken:
        k += 1
    return '%s%d' % (kind, k)


def add_row(rows, kind, name=None, **vals):
    """-> (rows', name). Kind must be one of KINDS; name made unique (kind + n when None/taken)."""
    if kind not in names(KINDS):
        raise ValueError('unknown effector kind %r (%s)' % (kind, ' '.join(names(KINDS))))
    taken = set(r['name'] for r in rows)
    nm = valid_name(name) if name else ''
    if not nm:
        nm = next_name(kind, taken)
    elif nm in taken:
        nm = next_name(nm.rstrip('0123456789') or nm, taken)
    d = dict(DEFAULTS)
    d.update(dict((k, str(v)) for k, v in vals.items() if k in COLS))
    d['name'], d['kind'] = nm, kind
    return rows + [d], nm


def remove_row(rows, name):
    return [r for r in rows if r['name'] != name]


def duplicate_row(rows, name, new=None):
    src = [r for r in rows if r['name'] == name]
    if not src:
        raise ValueError('no effector %r' % name)
    taken = set(r['name'] for r in rows)
    nm = valid_name(new) if new else ''
    if not nm or nm in taken:
        base = name.rstrip('0123456789') or name
        nm = next_name(base, taken)
    d = dict(src[0])
    d['name'] = nm
    i = rows.index(src[0])
    return rows[:i + 1] + [d] + rows[i + 1:], nm


def rename_row(rows, name, new):
    nm = valid_name(new)
    if not nm:
        raise ValueError('empty name')
    if nm != name and nm in set(r['name'] for r in rows):
        raise ValueError('name %r is taken' % nm)
    out = []
    for r in rows:
        d = dict(r)
        if d['name'] == name:
            d['name'] = nm
        out.append(d)
    return out, nm


def set_value(rows, name, col, value):
    if col not in COLS or col == 'name':
        raise ValueError('column %r cannot be set here' % col)
    out = []
    for r in rows:
        d = dict(r)
        if d['name'] == name:
            d[col] = str(value)
        out.append(d)
    return out


# ------------------------------------------------------------------------------------------------ tags / selection

def tag_list(rows):
    """Sorted unique tags of the list (bit k = tag_list()[k]); beyond MAX_TAGS are dropped (reported by tags_over)."""
    s = set()
    for r in rows:
        for t in str(r.get('tags', '')).replace(',', ' ').split():
            s.add(t)
    return sorted(s)[:MAX_TAGS]


def tags_over(rows):
    s = set()
    for r in rows:
        s.update(str(r.get('tags', '')).replace(',', ' ').split())
    return max(0, len(s) - MAX_TAGS)


def row_tags(row):
    return str(row.get('tags', '')).replace(',', ' ').split()


def is_pub(row):
    """A published row (tag `pub`): another COMP's output in the shared list. Never part of 'all' / '*' / empty; a
    consumer uses it only when it names it or selects one of its tags."""
    return PUB_TAG in row_tags(row)


def tag_bits(row, tags):
    b = 0 if is_pub(row) else OWN_BIT
    for t in row_tags(row):
        if t in tags:
            b |= 1 << tags.index(t)
    return b


def sel_vec(text, rows):
    """Selection text -> ([tag mask, all, id0, id1, id2, id3], unknown tokens).
    Tokens: 'all' / '*' / empty text = every enabled effector; '#tag' = a tag; a name = that effector (row index + 1);
    a bare word that is no name but a tag = that tag. More than MAX_IDS names -> the rest are reported (use a tag)."""
    toks = str(text or '').replace(',', ' ').split()
    tags = tag_list(rows)
    names_ = [r['name'] for r in rows]
    mask, allf, ids, unknown = 0, 0.0, [], []
    pub = any(is_pub(r) for r in rows)

    def _all():                                    # every enabled OWN effector (29 Oct: #pub rows are opt-in)
        return (OWN_BIT, 0.0) if pub else (0, 1.0)
    if not toks:
        m_, allf = _all()
        mask |= m_
    for t in toks:
        if t in ('all', '*'):
            m_, a_ = _all()
            mask, allf = mask | m_, max(allf, a_)
        elif t.startswith('#') and t[1:] in tags:
            mask |= 1 << tags.index(t[1:])
        elif t in names_:
            if float(names_.index(t) + 1) in ids:      # once each: the shader visits the ids themselves
                continue
            if len(ids) < MAX_IDS:
                ids.append(float(names_.index(t) + 1))
            else:
                unknown.append(t)
        elif t in tags:
            mask |= 1 << tags.index(t)
        else:
            unknown.append(t)
    ids += [0.0] * (MAX_IDS - len(ids))
    return [float(mask), allf] + ids, unknown


def wants_pub(text, rows):
    """True when a selection explicitly reaches a published row (by name, '#tag' or a bare tag word one of them
    carries): such a consumer reads the full buffer eff_rows_pub; every other consumer reads eff_rows, where #pub rows
    are inert placeholders (no op of theirs is read, so no reference reaches the publishing COMP)."""
    toks = [t for t in str(text or '').replace(',', ' ').split() if t not in ('all', '*')]
    if not toks:
        return False
    names_ = set(r['name'] for r in rows)
    for r in rows:
        if not is_pub(r):
            continue
        tg = row_tags(r)
        for t in toks:
            if t == r['name'] or (t.startswith('#') and t[1:] in tg) or (t not in names_ and t in tg):
                return True
    return False


def placeholder(row):
    """The row as eff_rows packs a #pub or disabled row: enabled 0, nothing of its objects / refs read (identity
    transform, no points, no light / env values). Ids stay stable (rows keep their places)."""
    d = dict(row)
    d['enabled'] = '0'
    return d


def selected(rows, sel, kinds=None):
    """Indices of the rows a selection picks (enabled only; optional kind filter): the CPU twin of pxeSel()."""
    v, _ = sel_vec(sel, rows)
    tags = tag_list(rows)
    ids = set(int(x) for x in v[2:] if x > 0)
    out = []
    for i, r in enumerate(rows):
        if not _on(r.get('enabled', '1')):
            continue
        if kinds is not None and r.get('kind') not in kinds:
            continue
        if v[1] > 0.5 or (tag_bits(r, tags) & int(v[0])) or (i + 1) in ids:
            out.append(i)
    return out


# ------------------------------------------------------------------------------------------------ paths

def _noise1(x, seed):
    """Smooth 1D value noise in -1..1 (deterministic, for the wander path)."""
    i = math.floor(x)
    f = x - i

    def h(n):
        v = math.sin((n + seed * 101.0) * 127.1) * 43758.5453
        return (v - math.floor(v)) * 2.0 - 1.0
    u = f * f * (3.0 - 2.0 * f)
    return h(i) * (1.0 - u) + h(i + 1) * u


def path_point(shape, t, size=(1.0, 1.0, 1.0), centre=(0.0, 0.0, 0.0), chop_xyz=None):
    """Position on a motion path at phase t (cycles; speed * seconds + phase). size = half extents per axis."""
    sx, sy, sz = [float(v) for v in size]
    cx, cy, cz = [float(v) for v in centre]
    a = 2.0 * math.pi * t
    if shape == 'line':
        f = t - math.floor(t)
        s = 4.0 * f - 1.0 if f < 0.5 else 3.0 - 4.0 * f            # -1 .. 1 .. -1 (ping-pong)
        p = (s * sx, s * sy, s * sz)
    elif shape == 'lissajous':
        p = (math.sin(a * 3.0) * sx, math.sin(a * 2.0 + 0.5 * math.pi) * sy, math.sin(a) * sz)
    elif shape == 'figure8':
        p = (math.sin(a) * sx, math.sin(2.0 * a) * 0.5 * sy, math.cos(a) * sz)
    elif shape == 'noise':
        p = (_noise1(t * 4.0, 1) * sx, _noise1(t * 4.0, 2) * sy, _noise1(t * 4.0, 3) * sz)
    elif shape == 'chop':
        q = chop_xyz or (0.0, 0.0, 0.0)
        p = (float(q[0]) * sx, float(q[1]) * sy, float(q[2]) * sz)
    else:                                                          # circle in the xz plane (y = centre)
        p = (math.cos(a) * sx, 0.0, math.sin(a) * sz)
    return (cx + p[0], cy + p[1], cz + p[2])


# ------------------------------------------------------------------------------------------------ packing

def identity():
    return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]]


def apply_affine(m, p):
    return tuple(m[r][0] * p[0] + m[r][1] * p[1] + m[r][2] * p[2] + m[r][3] for r in range(3))


def sdf_of(kind):
    """(sdf type, local size) of a kind (PX unit shapes; point kinds = type 0, point sets = SD_PTS)."""
    if kind in SET_KINDS:
        return SD_PTS, (0.0, 0.0, 0.0)
    if kind == CLOUD_KIND:
        return SD_GRID, (0.0, 0.0, 0.0)
    if kind in POINT_KINDS or kind in NON_PROX:
        return 0, (0.0, 0.0, 0.0)
    return PXL.EFF_SDF.get(kind, PXL.EFF_SDF['null'])


_EMPTY = []


def _empty():
    """One shared (0, 3) array for every row without points (live: a fresh np.zeros per row = ~1.5 ms at 100 rows)."""
    if not _EMPTY:
        import numpy as np
        e = np.zeros((0, 3))
        e.flags.writeable = False
        _EMPTY.append(e)
    return _EMPTY[0]


def _pts_array(a):
    """Points / velocities -> float64 (n, 3) array (numpy: point sets run per frame)."""
    if a is None or len(a) == 0:
        return _empty()
    import numpy as np
    return np.asarray(a, dtype=np.float64).reshape(-1, 3)[:PTS_MAX]


def effector(row, world=None, vel=(0.0, 0.0, 0.0), points=None, point_vel=None, light=None, env=None):
    """Row dict + runtime values -> the effector record pack_buffer() takes (points / point_vel as (n, 3) arrays;
    light = the Light COMP's values for a `light` row, see light_values; env = env_values(...) + 'pixels' (H, W, 3+)
    for an `env` row, see env_coeffs)."""
    pts = _pts_array(points)
    pv = _pts_array(point_vel)
    if len(pv) != len(pts):                          # missing velocities = 0 (first frame, set size changed)
        import numpy as np
        full = np.zeros_like(pts)
        k = min(len(pv), len(pts))
        full[:k] = pv[:k]
        pv = full
    lv = light_values(light) if row.get('kind') == LIGHT_KIND else None
    ev = None
    if row.get('kind') == ENV_KIND and env is not None:
        ev = env_values(env)
        ev['pixels'] = env.get('pixels')
    return {'row': row, 'world': world or identity(), 'vel': tuple(float(v) for v in vel), 'points': pts,
            'point_vel': pv, 'light': lv, 'env': ev}


# ------------------------------------------------------------------------------------------------ lights

def light_values(d=None):
    """Light COMP values -> a complete, typed dict (LIGHT_DEFAULTS filled). Keys: type (LTYPES name), colour (rgb),
    intensity (TD dimmer), att_on / att_start / att_end / att_exp (TD attenuated / attenuationstart / end / exp),
    cone_angle (TD coneangle, FULL angle, degrees) / cone_delta (TD conedelta, soft edge OUTSIDE the cone) /
    cone_roll (TD coneroll, exponent), area_w / area_h (rectangle in the light's local XY plane, x the object's
    scale). The colour packed is light_colours()' (the shared palette applied, docs/builds/palette_convention.md)."""
    v = dict(LIGHT_DEFAULTS)
    for k, x in (d or {}).items():
        if k in v and x is not None:
            v[k] = x
    t = v['type']
    v['type'] = t if t in names(LTYPES) else TD_TO_LTYPE.get(t, 'point')
    v['colour'] = tuple(_f(c, 1.0) for c in tuple(v['colour'])[:3])
    for k in ('intensity', 'att_start', 'att_end', 'att_exp', 'cone_angle', 'cone_delta', 'cone_roll', 'area_w',
              'area_h'):
        v[k] = _f(v[k], LIGHT_DEFAULTS[k])
    v['att_on'] = _on(v['att_on'])
    return v


def _unit(x, fb=(0.0, 0.0, -1.0)):
    n = math.sqrt(sum(c * c for c in x))
    return tuple(c / n for c in x) if n > 1e-12 else tuple(fb)


def light_block(world, lv, i, colour=None):
    """The LW texels of one light (row index i): world = the Light COMP's 3x4 world matrix (it shines along its -Z).
      0 (r, g, b, intensity)                 colour (linear, as the TD par) and TD dimmer
      1 (position xyz, type)                 world position; type = LTYPES index (0 point 1 spot 2 area 3 directional)
      2 (forward xyz, row index i)           unit direction the light shines (world -Z of the object)
      3 (att start, att end, att exp, att on)  TD attenuation (on = 1): f = sin(clamp((end-d)/(end-start)) pi/2)^exp
      4 (cos inner, cos outer, cone roll, 0)  spot: inner = angle/2, outer = angle/2 + delta (degrees); the
        shader ramps smoothstep(outer, inner, angle) ^ roll (TD's own cone, measured live b4 31550: max err 0.027)
      5 (area half-U xyz, 0)                 area: world half axis along local x (area_w / 2 x object scale)
      6 (area half-V xyz, 0)                 area: world half axis along local y (area_h / 2)"""
    lv = light_values(lv)
    pos = (world[0][3], world[1][3], world[2][3])
    fwd = _unit((-world[0][2], -world[1][2], -world[2][2]))
    half = max(0.0, 0.5 * lv['cone_angle'])
    outer = min(180.0, half + max(0.0, lv['cone_delta']))
    hw, hh = 0.5 * lv['area_w'], 0.5 * lv['area_h']
    col = lv['colour'] if colour is None else tuple(float(c) for c in colour)
    return [[col[0], col[1], col[2], lv['intensity']],
            [pos[0], pos[1], pos[2], float(menu_index(LTYPES, lv['type']))],
            [fwd[0], fwd[1], fwd[2], float(i)],
            [lv['att_start'], lv['att_end'], max(lv['att_exp'], 1e-3), 1.0 if lv['att_on'] else 0.0],
            [math.cos(math.radians(half)), math.cos(math.radians(outer)), max(lv['cone_roll'], 1e-3), 0.0],
            [world[0][0] * hw, world[1][0] * hw, world[2][0] * hw, 0.0],
            [world[0][1] * hh, world[1][1] * hh, world[2][1] * hh, 0.0]]


# ---- light colours through the shared palette (W1-B, docs/builds/palette_convention.md): ONE palette on the
# effectors COMP (page Lights), one colour source for every light (colsrc_pars('light') without Lightcol: `solid` =
# each Light COMP's own colour). Applied when the light rows are packed: light k (enabled order) = colsrc_eval(cs,
# rgb_k, rgb_k, k, rows, ctl), so mode `index` gives light k palette stop k and a Palshift drive (beat step) moves
# every light one stop on. The Light COMP's own colour is untouched (TD-native lighting keeps it).

def _pml():
    import palette_map_logic as PML               # builders/ is on sys.path (see the px_logic import above)
    return PML


def light_palette_pars():
    """(name, style, default, opts) for the effectors COMP's Lights page (palette sources: custom text + presets)."""
    P = _pml()
    srcs = [m for m in P.PAL_SOURCES if m[0] not in ('file', 'image')]
    m = lambda menu, label: {'names': names(menu), 'labels': labels(menu), 'label': label}
    cs = [x for x in P.colsrc_pars('light') if x[0] != 'Lightcol']
    cs = [(n, s, d, dict(o, label=o.get('label', 'Light colour source'))) for n, s, d, o in cs]
    return [('Palsource', 'Menu', 'neon_trio', m(srcs, 'Palette')),
            ('Palstops', 'Str', '#00ff66 #00e5ff #ff00cc', {'label': 'Custom stops (hex [pos], comma separated)'}),
            ('Palmode', 'Menu', 'steps', m(P.PAL_MODES, 'Palette mode')),
            ('Palinterp', 'Menu', 'oklab', m(P.PAL_INTERP, 'Blend')),
            ('Palshift', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Palette shift (drive me)'}),
            ('Palreverse', 'Toggle', False, {'label': 'Reverse palette'})] + cs


def light_palette(source='neon_trio', stops='', mode='steps', interp='oklab', shift=0.0, reverse=False):
    """Lights page values -> (rows, ctl) of the shared palette (pal_rows / pal_ctl)."""
    P = _pml()
    custom = [r.split() for r in str(stops or '').split(',') if r.strip()]
    st = P.palette_stops({'source': source, 'mode': mode, 'reverse': bool(reverse)},
                         custom_rows=custom if source == 'custom' else None)
    return P.pal_rows(st), P.pal_ctl(st, mode, interp, shift)


def light_cs(mode='solid', pos=0.0, spread=1.0, keep=0.0):
    return _pml().colsrc_vec(mode, pos, spread, keep)


def light_colours(cols, cs=None, pal=None):
    """Own colours of the enabled lights (in order) -> packed colours: colsrc_eval with attrT = k (light index)."""
    if cs is None or pal is None or int(round(cs[0])) == 0:
        return [tuple(c) for c in cols]
    P = _pml()
    return [tuple(P.colsrc_eval(cs, c, c, float(k), pal[0], pal[1])) for k, c in enumerate(cols)]


# ---- env lights (kind `env`, SA6 screen-as-light, lane E 27 Oct): any TOP -> 9 SH irradiance coefficients
# (Ramamoorthi-Hanrahan 2001). The runtime fits the TOP to a few samples (Resolution TOP -> TOP to CHOP, next frame),
# env_coeffs projects them: L_k = sum_s L(w_s) Y_k(w_s) dOmega_s, stored pre-convolved with the clamped cosine
# (A^_l = A_l / pi = 1, 2/3, 1/4), so a white Lambert surface with normal n receives E(n) / pi = sum_k c_k Y_k(n)
# (x gain; uniform white sky of radiance 1 -> 1). Maps: screen = the w x h panel of the env object (local XY,
# shining along +Z; front only unless twosided), seen from `probe`: dOmega = dA cos(theta) / r^2; equirect = lat-long
# around the probe in TD's Projection TOP convention (u 0 = +X, 0.25 = +Z, 0.5 = -X, 0.75 = -Z, v 1 = +Y; live b2); the
# object's rotation turns it; ambient = the image mean all around.

SH_K = (0.28209479177387814, 0.4886025119029199, 1.0925484305920792, 0.31539156525252005, 0.5462742152960396)
SH_A = (1.0, 2.0 / 3.0, 2.0 / 3.0, 2.0 / 3.0, 0.25, 0.25, 0.25, 0.25, 0.25)       # A_l / pi per coefficient


def env_values(d=None):
    """Env object values -> a complete, typed dict (ENV_DEFAULTS filled): map (ENVMAPS), gain, w / h (screen size in
    the object's local XY, x its scale), probe (world point the light is measured at), twosided, samples (fit width;
    height = width / 2 for equirect, width x h / w for screen)."""
    v = dict(ENV_DEFAULTS)
    for k, x in (d or {}).items():
        if k in v and x is not None:
            v[k] = x
    v['map'] = v['map'] if v['map'] in names(ENVMAPS) else 'screen'
    v['gain'] = _f(v['gain'], 1.0)
    v['w'], v['h'] = max(_f(v['w'], 1.6), 1e-6), max(_f(v['h'], 0.9), 1e-6)
    v['probe'] = tuple(_f(c, 0.0) for c in tuple(v['probe'])[:3])
    v['twosided'] = _on(v['twosided'])
    v['samples'] = max(2, min(256, int(_f(v['samples'], 32))))
    return v


def env_fit_size(ev):
    """(width, height) of the Resolution TOP the runtime fits the env TOP to."""
    ev = env_values(ev)
    w = ev['samples']
    if ev['map'] == 'equirect':
        return w, max(2, w // 2)
    if ev['map'] == 'ambient':
        return min(w, 16), min(w, 16)
    return w, max(2, int(round(w * ev['h'] / ev['w'])))


def sh_basis(D):
    """Real SH basis l <= 2 at unit directions D (n, 3) -> (n, 9). Order: Y00, Y1-1 (y), Y10 (z), Y11 (x), Y2-2 (xy),
    Y2-1 (yz), Y20 (3z^2 - 1), Y21 (xz), Y22 (x^2 - y^2) = pxeSH9 in px_common.glsl."""
    import numpy as np
    D = np.asarray(D, dtype=np.float64).reshape(-1, 3)
    x, y, z = D[:, 0], D[:, 1], D[:, 2]
    k0, k1, k2, k3, k4 = SH_K
    return np.stack([np.full(len(D), k0), k1 * y, k1 * z, k1 * x, k2 * x * y, k2 * y * z, k3 * (3.0 * z * z - 1.0),
                     k2 * x * z, k4 * (x * x - y * y)], axis=1)


def _rot_cols(world):
    """Rotation of a 3x4 world matrix (columns normalised; scale removed) + the column lengths."""
    import numpy as np
    A = np.asarray([r[:3] for r in world], dtype=np.float64)
    ln = np.linalg.norm(A, axis=0)
    return A / np.where(ln > 1e-12, ln, 1.0), ln


def env_samples(ev, world, wpx, hpx):
    """Directions (n, 3, world) + solid-angle weights (n,) of the wpx x hpx fit pixels (row 0 = the image bottom,
    TD's origin). screen: weight 0 for pixels seen from behind (front only)."""
    import numpy as np
    ev = env_values(ev)
    u = (np.arange(wpx) + 0.5) / wpx
    v = (np.arange(hpx) + 0.5) / hpx
    U, V = np.meshgrid(u, v)                              # (h, w): row y = v
    U, V = U.ravel(), V.ravel()
    R, ln = _rot_cols(world or identity())
    if ev['map'] == 'equirect':
        el = math.pi * (V - 0.5)
        az = 2.0 * math.pi * U                           # TD Projection TOP equirect (live b2): u 0 / 1 = +X,
        D = np.stack([np.cos(el) * np.cos(az), np.sin(el), np.cos(el) * np.sin(az)], axis=1) @ R.T   # .25 +Z .75 -Z
        wgt = (np.sin(math.pi * (V + 0.5 / hpx - 0.5)) - np.sin(math.pi * (V - 0.5 / hpx - 0.5))) * (2.0 * math.pi /
                                                                                              wpx)
        return D, wgt                                    # exact pixel solid angles (sum 4 pi)
    W_ = np.asarray(world or identity(), dtype=np.float64)
    loc = np.stack([(U - 0.5) * ev['w'], (V - 0.5) * ev['h'], np.zeros_like(U), np.ones_like(U)], axis=1)
    Q = loc @ W_.T                                        # world points of the pixel centres
    d = Q - np.asarray(ev['probe'], dtype=np.float64)
    r = np.linalg.norm(d, axis=1)
    D = d / np.maximum(r, 1e-9)[:, None]
    nz = R[:, 2]                                          # the panel's +Z (it shines that way)
    cs = -(D @ nz)                                        # cos between the panel normal and the way back to the probe
    cs = np.abs(cs) if ev['twosided'] else np.maximum(cs, 0.0)
    dA = (ev['w'] * ln[0] / wpx) * (ev['h'] * ln[1] / hpx)
    return D, dA * cs / np.maximum(r * r, 1e-12)


def env_pixels(pixels):
    """(H, W, >= 3) -> float64 (H, W, 3) linear rgb (alpha dropped); None / empty -> None."""
    if pixels is None:
        return None
    import numpy as np
    a = np.asarray(pixels, dtype=np.float64)
    if a.size == 0:
        return None
    if a.ndim == 2:
        a = a[None, :, :]
    return a[:, :, :3]


def env_coeffs(ev, world=None, cache=None):
    """9 x 3 pre-convolved SH coefficients of an env (ev = env_values + 'pixels'). Empty pixels -> zeros. cache (dict):
    the sample basis per (map, size, geometry) is kept (a static env re-projects with one 9 x n matmul)."""
    import numpy as np
    px = env_pixels((ev or {}).get('pixels'))
    if px is None:
        return np.zeros((9, 3))
    v = env_values(ev)
    hpx, wpx = px.shape[0], px.shape[1]
    if v['map'] == 'ambient':
        out = np.zeros((9, 3))
        out[0] = px.reshape(-1, 3).mean(axis=0) * (4.0 * math.pi * SH_K[0])
        return out
    w = world or identity()
    # id(env_samples): a reloaded eff_logic (text edit) never reuses an old basis kept in eff_rt's cache (live b2)
    key = (id(env_samples), v['map'], wpx, hpx, v['w'], v['h'], v['probe'], v['twosided'],
           tuple(round(x, 9) for r in w for x in r))
    B = cache.get(key) if cache is not None else None
    if B is None:
        D, wgt = env_samples(v, w, wpx, hpx)
        B = (sh_basis(D) * wgt[:, None]).T * np.asarray(SH_A)[:, None]          # (9, n)
        if cache is not None:
            if len(cache) > 64:
                cache.clear()
            cache[key] = B
    return B @ px.reshape(-1, 3)


def env_block(i, ev, coeffs):
    """The EW texels of one env (row index i): (gain, i, map index, 0) + 9 x (c_k rgb, 0)."""
    v = env_values(ev)
    c = [[float(x) for x in row[:3]] + [0.0] for row in coeffs]
    return [[v['gain'], float(i), float(menu_index(ENVMAPS, v['map'])), 0.0]] + c


_ENV_IDX = {}


def env_pixels_from_chop(names_, arr):
    """TOP to CHOP of the fit image -> (H, W, 4). Channels r g b a carry the row index (live T-82 / T-87 / b2: r0 g0
    b0 a0 r1 ... with crop full; row 0 = the image bottom); width = samples. Bare r g b a = one row. The name ->
    (row, channel) map is cached per name list (live b2: the per-channel Python loop was 0.35 ms per cook)."""
    import numpy as np
    key = tuple(str(n) for n in names_)
    if not key:
        return np.zeros((0, 0, 4))
    a = np.asarray(arr, dtype=np.float64).reshape(len(key), -1)
    ix = _ENV_IDX.get(key)
    if ix is None:
        ks, ys, cs = [], [], []
        for k, n in enumerate(key):
            if n and n[0] in 'rgba' and (n[1:].isdigit() or n[1:] == ''):
                ks.append(k)
                ys.append(int(n[1:]) if n[1:] else 0)
                cs.append('rgba'.index(n[0]))
        ix = (np.array(ks, dtype=np.int64), np.array(ys, dtype=np.int64), np.array(cs, dtype=np.int64))
        if len(_ENV_IDX) > 32:
            _ENV_IDX.clear()
        _ENV_IDX[key] = ix
    ks, ys, cs = ix
    if not len(ks):
        return np.zeros((0, 0, 4))
    out = np.zeros((int(ys.max()) + 1, a.shape[1], 4))
    out[:, :, 3] = 1.0
    out[ys, :, cs] = a[ks]
    return out


def _lkey(lv):
    return None if lv is None else tuple(sorted((k, tuple(x) if isinstance(x, tuple) else x) for k, x in lv.items()))


def row_texels(e, i, tags, po):
    """The W texels of effector i (po = its points' start texel, 0 without points). Pure: same inputs, same texels."""
    r = e['row']
    kind = r.get('kind', 'null')
    w = e['world']
    inv = PXL.affine_inverse(w)
    ty, size = sdf_of(kind)
    sc = abs(PXL.affine_det(w)) ** (1.0 / 3.0) or 1.0
    vel = e['vel']
    pl = e['points'] if kind in SET_KINDS else ()
    centre = (w[0][3], w[1][3], w[2][3])
    if len(pl):
        centre = tuple(float(x) for x in pl.mean(axis=0))
    if kind == CLOUD_KIND:
        size = (1.0 if _on(r.get('enabled', '1')) else 0.0, 0.0, 0.0)
    return [list(inv[0]), list(inv[1]), list(inv[2]),
            [float(ty)] + [float(x) for x in size],
            [centre[0], centre[1], centre[2], sc],
            [w[0][1], w[1][1], w[2][1], math.sqrt(sum(x * x for x in vel))],
            [vel[0], vel[1], vel[2], 1.0 if (_on(r.get('enabled', '1')) and kind not in NON_PROX + (CLOUD_KIND,))
             else 0.0],
            [float(menu_index(FALLOFFS, r.get('falloff', 'smooth'))), _f(r.get('radius'), 0.5),
             _f(r.get('exponent'), 1.0), _f(r.get('gain'), 1.0)],
            [float(tag_bits(r, tags)), float(menu_index(KINDS, kind)), float(po), float(len(pl))],
            [0.0, float(menu_index(PTMODES, r.get('mode', 'nearest'))), 1.0, float(i + 1)]]


def pack_buffer(effs, tags=None, cache=None, list_key=None, as_array=False, light_cs=None, light_pal=None,
                grid=None, env_cache=None):
    """effs = [effector(...)] in table order -> list of [x, y, z, w] texels (header + rows + points); as_array = the
    same as a float64 (T, 4) numpy array (the runtime: no list -> array conversion, live 1.3 ms at 2000 texels).
    cache (dict, optional): rows without points whose (row, world, vel, index, tags) did not change reuse their texels
    (the runtime keeps it between cooks; a static rig then packs in ~0 per effector). list_key (optional): a key that
    changes whenever any row / tag changes (the runtime's list version) - used instead of hashing every row. Same
    output with or without cache / list_key. light_cs / light_pal = the lights' colour source vec4 and the shared
    palette (rows, ctl) (light_colours; None = each light's own colour). grid = the grid region texels
    (effectors_grid_logic.grid_texels; None / [] = no grid). env_cache = a dict for env_coeffs' sample bases."""
    import numpy as np
    rows = [e['row'] for e in effs]
    tags = tag_list(rows) if tags is None else tags
    n = len(effs)
    lights = [(i, e) for i, e in enumerate(effs)
              if e['row'].get('kind') == LIGHT_KIND and _on(e['row'].get('enabled', '1'))]
    envs = [(i, e) for i, e in enumerate(effs)
            if e['row'].get('kind') == ENV_KIND and _on(e['row'].get('enabled', '1')) and e.get('env') is not None]
    l0 = HEADER + n * W
    e0 = l0 + 1 + len(lights) * LW if envs else 0
    g0 = (l0 + 1 + len(lights) * LW + ((1 + len(envs) * EW) if envs else 0)) if grid else 0
    pstart = l0 + 1 + len(lights) * LW + ((1 + len(envs) * EW) if envs else 0) + (len(grid) if grid else 0)
    blocks, pts, npts = [np.array([[float(n), float(W), float(pstart), float(VERSION)]])], [], 0
    tkey = tuple(tags) if list_key is None else None
    used = set()
    for i, e in enumerate(effs):
        kind = e['row'].get('kind', 'null')
        pl = e['points'] if kind in SET_KINDS else ()
        po = pstart + npts * PTS_TEXELS if len(pl) else 0
        if len(pl):
            v = e['point_vel']
            blk = np.empty((2 * len(pl), 4))
            blk[0::2, :3], blk[0::2, 3] = pl, 1.0                       # (xyz, valid)
            blk[1::2, :3], blk[1::2, 3] = v, np.sqrt((v * v).sum(axis=1))   # (velocity xyz, speed)
            pts.append(blk)
            npts += len(pl)
        if cache is not None and not len(pl):
            w = e['world']
            wk = (w[0][0], w[0][1], w[0][2], w[0][3], w[1][0], w[1][1], w[1][2], w[1][3], w[2][0], w[2][1], w[2][2],
                  w[2][3])
            lk = _lkey(e.get('light'))
            key = (list_key, i, wk, e['vel'], lk) if list_key is not None else \
                (tuple(sorted(e['row'].items())), wk, e['vel'], i, tkey, lk)
            used.add(key)
            tx = cache.get(key)
            if tx is None:
                tx = cache[key] = np.array(row_texels(e, i, tags, po), dtype=np.float64)
            blocks.append(tx)
        else:
            blocks.append(np.array(row_texels(e, i, tags, po), dtype=np.float64))
    if cache is not None:
        for k in [k for k in cache if k not in used]:
            del cache[k]
    blocks.append(np.array([[float(len(lights)), float(LW), float(e0), float(g0)]]))
    cols = light_colours([light_values(e.get('light'))['colour'] for _i, e in lights], light_cs, light_pal)
    for (i, e), col in zip(lights, cols):
        blocks.append(np.array(light_block(e['world'], e.get('light'), i, col), dtype=np.float64))
    if envs:
        blocks.append(np.array([[float(len(envs)), float(EW), 0.0, 0.0]]))
        for i, e in envs:
            blocks.append(np.array(env_block(i, e['env'], env_coeffs(e['env'], e['world'], env_cache)),
                                   dtype=np.float64))
    if grid:
        blocks.append(np.asarray(grid, dtype=np.float64).reshape(-1, 4))
    out = np.vstack(blocks + pts)
    return out if as_array else out.tolist()


def buffer_chans(texels):
    """Texels -> 4 channel lists (x y z w), the Script CHOP layout (one sample per texel)."""
    return [[t[c] for t in texels] for c in range(4)]


def read_row(texels, i):
    """Row i of a packed buffer (list of W texels) - the reader's view (tests, CPU consumers)."""
    return texels[HEADER + i * W: HEADER + (i + 1) * W]


def count_of(texels):
    if not texels:
        return 0
    n = int(round(texels[0][0]))
    return max(0, min(n, (len(texels) - HEADER) // W))


def light_start(texels):
    """Texel of the light region header (pxeLightBase): 1 + N * W with W read from the header; -1 before version 2."""
    if not len(texels) or texels[0][3] < 1.5:
        return -1
    return HEADER + int(round(texels[0][0])) * int(round(texels[0][1]))


def light_stride(texels):
    """Texels per light block, read from the light header (a later, wider block keeps old readers working)."""
    b = light_start(texels)
    return max(LW, int(round(texels[b][1]))) if 0 <= b < len(texels) else LW


def light_count(texels):
    b = light_start(texels)
    if b < 0 or b >= len(texels):
        return 0
    return max(0, min(int(round(texels[b][0])), (len(texels) - b - 1) // light_stride(texels)))


def read_light(texels, k):
    b = light_start(texels) + 1 + k * light_stride(texels)
    return [list(t) for t in texels[b: b + LW]]


def ext_base(texels, comp):
    """Light header component (2 = env region texel, 3 = grid region texel); -1 when absent (version < 3 / 0)."""
    b = light_start(texels)
    if b < 0 or b >= len(texels) or texels[0][3] < 2.5:
        return -1
    e = int(round(texels[b][comp]))
    return e if 0 < e < len(texels) else -1


def env_start(texels):
    return ext_base(texels, 2)


def env_count(texels):
    e = env_start(texels)
    if e < 0:
        return 0
    st = max(EW, int(round(texels[e][1])))
    return max(0, min(int(round(texels[e][0])), (len(texels) - e - 1) // st))


def read_env(texels, m):
    e = env_start(texels)
    st = max(EW, int(round(texels[e][1])))
    b = e + 1 + m * st
    return [list(t) for t in texels[b: b + EW]]


def grid_start(texels):
    return ext_base(texels, 3)


# ------------------------------------------------------------------------------------------------ CPU consumers

def colliders(texels, sel_v, pad=0.0, kinds_ok=(0, 1, 2, 4, 5)):
    """Packed buffer + sel_vec -> collider spheres [(x, y, z, r)] (BN_cloth in3 format) of the selected object /
    point effectors: sphere r = 0.5 scale, box = half diagonal, capsule / torus = outer radius, point = row radius;
    point sets = one sphere per point (row radius). Planes are skipped (no sphere)."""
    out = []
    n = count_of(texels)
    mask, allf = int(sel_v[0]), sel_v[1] > 0.5
    ids = set(int(x) for x in sel_v[2:6] if x > 0)
    for i in range(n):
        r = read_row(texels, i)
        if r[6][3] < 0.5:
            continue
        if not (allf or (int(r[8][0]) & mask) or (i + 1) in ids):
            continue
        ty = int(round(r[3][0]))
        c, sc = r[4][:3], r[4][3]
        if ty == SD_PTS:
            o, m = int(r[8][2]), int(r[8][3])
            for j in range(m):
                p = texels[o + j * PTS_TEXELS]
                out.append((p[0], p[1], p[2], r[7][1] + pad))
            continue
        if ty not in kinds_ok:
            continue
        s = r[3][1:]
        if ty == 1:
            rad = s[0] * sc
        elif ty == 2:
            rad = math.sqrt(s[0] ** 2 + s[1] ** 2 + s[2] ** 2) * sc
        elif ty == 4:
            rad = (s[0] + s[1]) * sc
        elif ty == 5:
            rad = (s[0] + s[1]) * sc
        else:
            rad = r[7][1]
        out.append((c[0], c[1], c[2], rad + pad))
    return out


def info_2d(row, kind_half=None):
    """Row -> the per-effector values GN_reaction_diffusion / GN_physarum read (their effector_row keys):
    radius = shape half size + falloff radius (world, times the object's scale there), falloff in their menu,
    active, gain (multiplies their own Effstrength / per-Null strength)."""
    kind = row.get('kind', 'null')
    half = kind_half if kind_half is not None else (0.5 if kind in ('sphere', 'box', 'capsule', 'torus') else 0.0)
    return {'radius': half + _f(row.get('radius'), 0.5), 'falloff': FALL_TO_2D.get(row.get('falloff', 'smooth'), 0),
            'active': _on(row.get('enabled', '1')), 'gain': _f(row.get('gain'), 1.0)}


# ------------------------------------------------------------------------------------------------ numpy reference

def ref_weight(texels, p, sel_v, comb=0, rscale=1.0, override=None, gain=1.0, field=None):
    """CPU twin of pxeW() without the ragged edge: weight at world point p (3,) and the best index (-1 = none).
    field = (nearest-seed volume, geometry) of the shared grid (effectors_grid_logic.field_ref): `cloud` rows take
    part as in a consumer compiled with PXE_GRID; None = as one without it (cloud rows skipped)."""
    n = count_of(texels)
    mask, allf = int(sel_v[0]), sel_v[1] > 0.5
    ids = set(int(x) for x in sel_v[2:6] if x > 0)
    w = 1.0 if comb == 2 else 0.0
    best, bw = -1, -1.0
    for i in range(n):
        r = read_row(texels, i)
        on = r[6][3] > 0.5 or (field is not None and int(round(r[3][0])) == SD_GRID and r[3][1] > 0.5)
        if not on or not (allf or (int(r[8][0]) & mask) or (i + 1) in ids):
            continue
        d = ref_sd(texels, i, p, field)
        f = r[7]
        R, k, shape = (override[0], override[1], int(override[2])) if override else (f[1], f[2], int(round(f[0])))
        wi = float(PXL.ref_fall(d, R * rscale, k, shape)) * f[3]
        if comb == 1:
            w += wi
        elif comb == 2:
            w *= wi
        elif comb == 3:
            w = w + wi - w * wi
        else:
            w = max(w, wi)
        if wi > bw:
            bw, best = wi, i
    return (0.0 if best < 0 else w * gain), best


def ref_sd(texels, i, p, field=None):
    r = read_row(texels, i)
    ty = int(round(r[3][0]))
    if ty == SD_GRID:
        if field is None:
            return 1e9
        import effectors_grid_logic as GL
        return float(GL.query_ref(field[0], field[1], [p])[0]) - r[9][0]
    if ty == SD_PTS:
        o, m = int(r[8][2]), int(r[8][3])
        bd = 1e18
        for j in range(m):
            q = texels[o + j * PTS_TEXELS]
            if q[3] < 0.5:
                continue
            bd = min(bd, sum((p[k] - q[k]) ** 2 for k in range(3)))
        return (math.sqrt(bd) if m else 1e9) - r[9][0]
    import numpy as np
    q = np.array([sum(r[row][k] * (p[k] if k < 3 else 1.0) for k in range(4)) for row in range(3)])
    return float(PXL.ref_sd_shape(ty, q, np.asarray(r[3][1:], dtype=np.float64))) * r[4][3]


def ref_light_factor(texels, k, P):
    """CPU twin of pxeLightFactor: light k at world points P (n, 3) -> (factor (n,) = attenuation x spot cone,
    L (n, 3) = unit vector from the point to the light; directional: -forward)."""
    import numpy as np
    P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
    t = [np.asarray(x, dtype=np.float64) for x in read_light(texels, k)]
    ty = int(round(t[1][3]))
    F = t[2][:3]
    if ty == 3:
        return np.ones(len(P)), np.tile(-F, (len(P), 1))
    q = np.tile(t[1][:3], (len(P), 1))
    if ty == 2:
        U, V = t[5][:3], t[6][:3]
        r = P - q
        q = q + np.outer(np.clip(r @ U / max(U @ U, 1e-12), -1.0, 1.0), U) + \
            np.outer(np.clip(r @ V / max(V @ V, 1e-12), -1.0, 1.0), V)
    dv = q - P
    d = np.sqrt((dv * dv).sum(axis=1))
    L = np.where(d[:, None] > 1e-9, dv / np.maximum(d, 1e-30)[:, None], -F)
    a = np.ones(len(P))
    if t[3][3] > 0.5:
        x = np.clip((t[3][1] - d) / max(t[3][1] - t[3][0], 1e-6), 0.0, 1.0)
        a = np.sin(x * (0.5 * math.pi)) ** t[3][2]
    if ty == 1:
        ang = np.arccos(np.clip((-L) @ F, -1.0, 1.0))
        ai, ao = math.acos(max(-1.0, min(1.0, t[4][0]))), math.acos(max(-1.0, min(1.0, t[4][1])))
        x = np.clip((ao - ang) / max(ao - ai, 1e-6), 0.0, 1.0)
        a = a * (x * x * (3.0 - 2.0 * x)) ** max(t[4][2], 1e-3)     # smoothstep in angle (fits TD's cone, live b4)
    return a, L


def ref_light(texels, k, P, N, Vw, mode=(0, 0.5, 0.0, 0.5)):
    """CPU twin of pxeLight: rgb (n, 3) light k adds at points P with unit normals N and unit view vectors Vw (point ->
    eye). mode = (model LMODELS index, wrap, spec amount, roughness)."""
    import numpy as np
    P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
    N = np.asarray(N, dtype=np.float64).reshape(-1, 3)
    Vw = np.asarray(Vw, dtype=np.float64).reshape(-1, 3)
    a, L = ref_light_factor(texels, k, P)
    m = int(mode[0])
    sp = np.zeros(len(P))
    if m == 3:
        dif = np.ones(len(P))
    else:
        ndl = (N * L).sum(axis=1)
        if m == 1:
            dif = np.maximum(ndl, 0.0)
        elif m == 2:
            dif = np.maximum((ndl + mode[1]) / (1.0 + mode[1]), 0.0)
        else:
            dif = (ndl * 0.5 + 0.5) ** 2
        if mode[2] > 0.0:
            H = L + Vw
            hl = np.sqrt((H * H).sum(axis=1))
            H = np.where(hl[:, None] > 1e-8, H / np.maximum(hl, 1e-30)[:, None], N)
            r = min(max(float(mode[3]), 0.02), 1.0)
            sh = 2.0 / r ** 4 - 2.0
            sp = np.where(ndl > 0.0, mode[2] * np.maximum((N * H).sum(axis=1), 0.0) ** sh, 0.0)
    t0 = read_light(texels, k)[0]
    col = np.asarray(t0[:3], dtype=np.float64)
    return (a * (dif + sp))[:, None] * (col * t0[3])[None, :]


def ref_lights(texels, P, N, Vw, sel_v, mode=(0, 0.5, 0.0, 0.5)):
    """CPU twin of pxeLights: sum of the selected lights (sel_v = sel_vec()[0]: 'all' = every enabled light)."""
    import numpy as np
    P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
    out = np.zeros((len(P), 3))
    mask, allf = int(sel_v[0]), sel_v[1] > 0.5
    ids = set(int(x) for x in sel_v[2:6] if x > 0)
    for k in range(light_count(texels)):
        i = int(round(read_light(texels, k)[2][3]))
        if allf or (int(read_row(texels, i)[8][0]) & mask) or (i + 1) in ids:
            out += ref_light(texels, k, P, N, Vw, mode)
    return out


def ref_env(texels, m, N):
    """CPU twin of pxeEnvIrr: env m's diffuse light at unit normals N (n, 3) -> rgb (n, 3) = gain x max(0, sum_k c_k
    Y_k(n)) (a white Lambert surface's brightness; uniform white sky of radiance 1 -> 1)."""
    import numpy as np
    t = read_env(texels, m)
    C = np.asarray([x[:3] for x in t[1:10]], dtype=np.float64)
    return np.maximum(sh_basis(N) @ C, 0.0) * t[0][0]


def ref_envs(texels, N, sel_v):
    """CPU twin of pxeEnvs: sum of the selected envs ('all' = every enabled env)."""
    import numpy as np
    N = np.asarray(N, dtype=np.float64).reshape(-1, 3)
    out = np.zeros((len(N), 3))
    mask, allf = int(sel_v[0]), sel_v[1] > 0.5
    ids = set(int(x) for x in sel_v[2:6] if x > 0)
    for m in range(env_count(texels)):
        i = int(round(read_env(texels, m)[0][1]))
        if allf or (int(read_row(texels, i)[8][0]) & mask) or (i + 1) in ids:
            out += ref_env(texels, m, N)
    return out


def env_irradiance_brute(ev, world, N):
    """Brute-force reference: sum_s L_s max(0, n . w_s) dOmega_s / pi over the fit pixels (no SH), x gain. SH9 is
    within a few % of it for smooth envs (Ramamoorthi-Hanrahan: ~1 % average); exact for l <= 2 content."""
    import numpy as np
    v = env_values(ev)
    px = env_pixels(ev.get('pixels'))
    N = np.asarray(N, dtype=np.float64).reshape(-1, 3)
    if px is None:
        return np.zeros((len(N), 3))
    if v['map'] == 'ambient':
        return np.tile(px.reshape(-1, 3).mean(axis=0) * v['gain'], (len(N), 1))
    D, wgt = env_samples(v, world or identity(), px.shape[1], px.shape[0])
    cosw = np.maximum(N @ D.T, 0.0) * wgt[None, :]
    return cosw @ px.reshape(-1, 3) / math.pi * v['gain']


def splat_normal(q, scale, view=None):
    """CPU twin of pxeSplatNormal: a splat's normal = its rotation (w, x, y, z) applied to the axis of its smallest
    scale; flipped to face `view` (point -> eye) when given."""
    import numpy as np
    q = np.asarray(q, dtype=np.float64)
    q = q / max(np.linalg.norm(q), 1e-12)
    w, x, y, z = q
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                  [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                  [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    s = np.asarray(scale, dtype=np.float64)
    k = int(np.argmin(s))          # GLSL: x if sx <= sy and sx <= sz, else y if sy <= sz, else z (first minimum)
    n = R[:, k]
    if view is not None and float(n @ np.asarray(view, dtype=np.float64)) < 0.0:
        n = -n
    return n


# ------------------------------------------------------------------------------------------------ consumer GLSL

def consumer_header(extra=()):
    """Uniform block every shader consumer prepends (with px_common.glsl after it). extra = more vec4 names."""
    out = ['// >>> effectors (builders/effectors_logic.consumer_header; data /project1/effectors/eff_rows)',
           '#define PXE_ROWS uEffRows',
           'uniform samplerBuffer uEffRows;   // packed effector list (texture buffer, Arrays page)',
           'uniform vec4 uEffSel;   // tag mask, all, on, gain',
           'uniform vec4 uEffIds;   // up to 4 effector ids (row index + 1; 0 = none)',
           'uniform vec4 uEffMix;   // combine, radius scale, ragged edge, ragged freq',
           'uniform vec4 uEffFall;  // override on, radius, exponent, shape (consumer falloff for every effector)']
    for n in extra:
        out.append('uniform vec4 %s;' % n)
    return '\n'.join(out) + '\n'


# Consumer page (Effectors) shared by the shader adapters: (name, style, default, opts)
def _m(menu, label):
    return {'names': names(menu), 'labels': labels(menu), 'label': label}


CONSUMER_PAGE = [
    ('Effon', 'Toggle', False, {'label': 'Effectors on (/project1/effectors)'}),
    ('Effselect', 'Str', 'all', {'label': 'Use effectors (all / names / #tags)', 'menu': 'select'}),   # T-233 dropdown
    ('Effgain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Weight gain'}),
    ('Effcombine', 'Menu', 'max', _m(COMBINES, 'Combine')),
    ('Effradscale', 'Float', 1.0, {'min': 0.01, 'max': 8, 'label': 'Radius scale'}),
    ('Effragged', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Ragged edge'}),
    ('Effraggedfreq', 'Float', 4.0, {'min': 0.1, 'max': 40, 'label': 'Ragged freq'}),
    ('Effoverride', 'Toggle', False, {'label': 'Own falloff (ignore per-effector)'}),
    ('Effradius', 'Float', 0.5, {'min': 0.001, 'max': 5, 'label': 'Own radius'}),
    ('Effexp', 'Float', 1.0, {'min': 0.05, 'max': 8, 'label': 'Own exponent'}),
    ('Effshape', 'Menu', 'smooth', _m(FALLOFFS, 'Own shape')),
]
CPU_PAGE = CONSUMER_PAGE[:2]

RT = "op('/project1/effectors/eff_rt')"


def sel_expr(k, sel_par="parent().par.Effselect.eval()"):
    """Par expression for component k of sel_vec (0 mask, 1 all, 2..5 ids); 0 when /project1/effectors is missing.
    The selection is read BEFORE the guard (T-159): a guard whose false branch reads nothing leaves TD with no
    dependency, so the value never refreshes when the list appears or Effselect changes. The lambda uses only its
    arguments (TD's expression names may not be visible inside it)."""
    return "((lambda s, r: r.module.sel_vec(s)[%d] if r is not None else 0)(%s, %s))" % (k, sel_par, RT)


def consumer_vecs(on="parent().par.Effon.eval()", gain="parent().par.Effgain.eval()",
                  comb="parent().par.Effcombine.menuIndex", rscale="parent().par.Effradscale.eval()",
                  rag="parent().par.Effragged.eval()", ragf="parent().par.Effraggedfreq.eval()",
                  ovr="parent().par.Effoverride.eval()", rad="parent().par.Effradius.eval()",
                  exp_="parent().par.Effexp.eval()", shape="parent().par.Effshape.menuIndex"):
    """[(uniform, 4 expressions)] for uEffSel / uEffIds / uEffMix / uEffFall."""
    return [('uEffSel', (sel_expr(0), sel_expr(1), 'float(%s)' % on, gain)),
            ('uEffIds', (sel_expr(2), sel_expr(3), sel_expr(4), sel_expr(5))),
            ('uEffMix', (comb, rscale, rag, ragf)),
            ('uEffFall', ('float(%s)' % ovr, rad, exp_, shape))]


def lights_expr(sel='all', keep=''):
    """Expression for a Render TOP's `lights` par: `keep` (its own lights, e.g. 'light1 env1') + the Light COMPs of
    the enabled `light` effectors that `sel` picks (eff_rt.light_paths), so TD-lit MATs (PBR / Phong / MX) are lit
    by the same lights the shader consumers read. Re-evaluates on list edits (light_paths reads Listver); a Render
    TOP built before /project1/effectors is re-set by effectors.build() (refresh_consumers, T-159)."""
    return ("(lambda r, k: ' '.join(([k] if k else []) + (list(r.module.light_paths(%r)) if r is not None else [])))"
            "(%s, %r)" % (str(sel), RT, str(keep).strip()))


MARK_A = '// >>> effectors adapter (builders/effectors.py attach: regenerated, do not edit inside)'
MARK_B = '// <<< effectors adapter'


def consumer_prefix(px_common_text, eff_consumer_text, defines=()):
    """The block an adapter puts in front of a consumer shader: defines + uniforms + px_common (packed only) +
    eff_consumer helpers, between MARK_A / MARK_B so a re-attach replaces it (idempotent)."""
    d = ['#define PX_PACKED_ONLY', '#define PXE_HOOK 1'] + ['#define %s 1' % x for x in defines]
    return '\n'.join([MARK_A] + d) + '\n' + consumer_header() + px_common_text.rstrip('\n') + '\n' + \
        eff_consumer_text.rstrip('\n') + '\n' + MARK_B + '\n'


def strip_prefix(text):
    """Shader text without an adapter block (any position at the top)."""
    a = text.find(MARK_A)
    if a < 0:
        return text
    b = text.find(MARK_B, a)
    if b < 0:
        return text
    e = text.find('\n', b)
    return text[:a] + (text[e + 1:] if e >= 0 else '')


def with_prefix(text, prefix):
    """Prefix put after any leading '#define' lines of the consumer (e.g. STATE_INPLACE), old block replaced."""
    t = strip_prefix(text)
    lines = t.split('\n')
    k = 0
    while k < len(lines) and lines[k].startswith('#define'):
        k += 1
    return '\n'.join(lines[:k] + [prefix.rstrip('\n')] + lines[k:])
