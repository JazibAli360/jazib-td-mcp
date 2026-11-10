"""effectors_grid_logic: the shared voxel grid service of /project1/effectors (lane E, 27 Oct 2026). Pure, no td import.

Build plan 27 Oct s2: ONE coarse voxel grid in the effectors COMP, built with its first two real users: the K36 / GE2
distance field (proximity from point sets > 4096 points: kind `cloud`, any TOP of points) and the SA23 painted mask
volume (effectors tagged #paint / #erase paint a persistent 3D mask). SA5 / SA3 / SA21 / SA14 read the same grid later
(PX W3). A 2D-tiled atlas in rgba32f compute TOPs (known-safe class, T-47), no Texture3D, no POP buffers (T-124).

Atlas: a cubic grid of N^3 voxels (N multiple of 8) over a cube (centre, edge `size`): voxel (x, y, z) lives at
atlas texel (x + (z % TX) * N, y + (z // TX) * N), TX = ceil(sqrt(N)) tiles across, TY = ceil(N / TX) down.
Voxel centre = origin + (v + 0.5) * cell; origin = centre - size / 2; cell = size / N.

Field pipeline (GLSL in builders/glsl/eff_grid_*.glsl, numpy twins below, same steps):
  scatter (one pass per enabled `cloud` row, chained): one workgroup = one 8^3 brick, its 512 threads walk every point
    of the cloud TOP, shared-memory atomics (exact, fixed point) add (sum of cell-local offsets xyz, count) per voxel
  seed: voxel with count > 0 -> its centroid (world xyz, 1), else (0, 0, 0, 0)
  jfa (8 passes): 3D jump flooding, 27 taps at step k = N >> j (j = 1..log2 N), then one step-1 pass (JFA+1), then
    copies: every voxel holds the seed nearest to its centre
  query: the 8 voxels around p (trilinear corners), min |p - seed|: error vs brute force < 1 cell (tested; the
    centroid stands in for the voxel's points)
Paint: per voxel centre c: paint' = clamp(paint (1 - decay dt) + rate dt (wAdd - wErase), 0, 1), w = pxeW of the
  #paint / #erase selections at c (any effector kind incl. point sets); clear -> 0. Out (paint, wAdd, wErase, 1).
Packed buffer (effectors_logic, version 3): the light header's w = G; texel G = (layer count, 2, 0, 0), then per
layer 2 texels: (origin xyz, cell), (N, TX, kind 1 field / 2 paint, 1 = on). ASCII only.
"""
import math

LAYER_FIELD = 1
LAYER_PAINT = 2
LAYER_TEXELS = 2
RES_FIELD = [('16', '16 (cheap, coarse)'), ('32', '32 (default)'), ('64', '64'), ('128', '128 (static clouds only)')]
RES_PAINT = [('32', '32'), ('64', '64 (default)'), ('96', '96'), ('128', '128')]
BRICK = 8                  # scatter workgroup = 8^3 voxels (local size 8 x 8 x 8 = 512 threads)
FX = 1024.0                # fixed-point scale of the scatter offset sums (shared uint atomics)
JFA_PASSES = 8             # covers N = 128 (7 halvings + JFA+1); smaller N: extra passes copy (step 0)
CLOUD_KIND = 'cloud'
SD_GRID = 7                # packed sdf type of a cloud row (old readers skip it: texel 6.w = 0)
GRID_DEFAULTS = {'on': False, 'centre': (0.0, 1.0, 0.0), 'size': 4.0, 'res': 32, 'alpha': 0.5,
                 'paint_on': False, 'paint_res': 64, 'paint_sel': '#paint', 'erase_sel': '#erase', 'rate': 2.0,
                 'decay': 0.0}


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(d)


def names(menu):
    return [m[0] for m in menu]


def labels(menu):
    return [m[1] for m in menu]


# ------------------------------------------------------------------------------------------------ geometry

def snap_res(n):
    """Resolution -> a multiple of BRICK in 8..256."""
    n = int(round(_f(n, 32)))
    return max(BRICK, min(256, int(math.ceil(n / float(BRICK))) * BRICK))


def tiles(N):
    """(TX, TY) tiles of the 2D atlas for N slices."""
    tx = int(math.ceil(math.sqrt(N)))
    return tx, int(math.ceil(N / float(tx)))


def atlas_size(N):
    tx, ty = tiles(N)
    return tx * N, ty * N


def geometry(centre=(0.0, 1.0, 0.0), size=4.0, N=32):
    """-> dict origin (min corner), cell, N, TX, TY, atlas (w, h)."""
    N = snap_res(N)
    size = max(_f(size, 4.0), 1e-6)
    tx, ty = tiles(N)
    c = tuple(_f(x) for x in tuple(centre)[:3])
    return {'origin': tuple(x - 0.5 * size for x in c), 'cell': size / N, 'N': N, 'TX': tx, 'TY': ty,
            'atlas': (tx * N, ty * N), 'size': size, 'centre': c}


def atlas_xy(v, N, tx):
    """Voxel (x, y, z) -> atlas texel (ax, ay) (= pxgAtlas in px_common / the shaders)."""
    x, y, z = v
    return x + (z % tx) * N, y + (z // tx) * N


def voxel_of_atlas(a, N, tx):
    """Atlas texel -> voxel (x, y, z), or None for a texel outside the used tiles."""
    ax, ay = a
    z = (ay // N) * tx + ax // N
    if z >= N:
        return None
    return ax % N, ay % N, z


def jfa_steps(N, passes=JFA_PASSES):
    """Step per JFA pass: N/2, N/4, ..., 1, then one extra 1 (JFA+1), then 0 (copy)."""
    out, k = [], N // 2
    while k >= 1 and len(out) < passes:
        out.append(k)
        k //= 2
    if len(out) < passes:
        out.append(1)
    return (out + [0] * passes)[:passes]


def dispatch(N):
    """Scatter dispatch size (workgroups x y z) = bricks per axis."""
    b = N // BRICK
    return b, b, b


# ------------------------------------------------------------------------------------------------ grid page

def grid_pars():
    """(name, style, default, opts) for the effectors COMP's Grid page."""
    m = lambda menu, label: {'names': names(menu), 'labels': labels(menu), 'label': label}
    D = GRID_DEFAULTS
    return [('Gridon', 'Toggle', D['on'], {'label': 'Distance field on (cloud effectors)'}),
            ('Gridcentre', 'XYZ', D['centre'], {'label': 'Grid centre', 'min': -10, 'max': 10}),
            ('Gridsize', 'Float', D['size'], {'label': 'Grid size (cube edge, world units)', 'min': 0.1, 'max': 40}),
            ('Gridres', 'Menu', str(D['res']), m(RES_FIELD, 'Field resolution (voxels per edge)')),
            ('Gridalpha', 'Float', D['alpha'], {'label': 'Cloud point valid when alpha >', 'min': -1, 'max': 1}),
            ('Painton', 'Toggle', D['paint_on'], {'label': 'Paint volume on'}),
            ('Paintres', 'Menu', str(D['paint_res']), m(RES_PAINT, 'Paint resolution')),
            ('Paintselect', 'Str', D['paint_sel'], {'label': 'Paint with (names / #tags)', 'menu': 'select'}),
            ('Eraseselect', 'Str', D['erase_sel'], {'label': 'Erase with (names / #tags)', 'menu': 'select'}),
            ('Paintrate', 'Float', D['rate'], {'label': 'Paint rate (full / s at weight 1)', 'min': 0, 'max': 20}),
            ('Paintdecay', 'Float', D['decay'], {'label': 'Fade (per s, 0 = stays)', 'min': 0, 'max': 2}),
            ('Paintclear', 'Pulse', None, {'label': 'Clear paint'}),
            ('Paintfile', 'Str', 'paint/effectors_paint.exr', {'label': 'Paint file (project folder)'}),
            ('Paintsave', 'Pulse', None, {'label': 'Save paint'}),
            ('Paintload', 'Pulse', None, {'label': 'Load paint'})]


def grid_values(d=None):
    v = dict(GRID_DEFAULTS)
    for k, x in (d or {}).items():
        if k in v and x is not None:
            v[k] = x
    v['on'], v['paint_on'] = bool(v['on']) and str(v['on']) not in ('0', 'False'), \
        bool(v['paint_on']) and str(v['paint_on']) not in ('0', 'False')
    v['res'], v['paint_res'] = snap_res(v['res']), snap_res(v['paint_res'])
    v['size'] = max(_f(v['size'], 4.0), 1e-6)
    v['centre'] = tuple(_f(x) for x in tuple(v['centre'])[:3])
    return v


def grid_texels(d=None):
    """Grid region texels for pack_buffer(grid=...): [] when no layer is on (G = 0 in the light header)."""
    v = grid_values(d)
    layers = []
    if v['on']:
        layers.append((LAYER_FIELD, geometry(v['centre'], v['size'], v['res'])))
    if v['paint_on']:
        layers.append((LAYER_PAINT, geometry(v['centre'], v['size'], v['paint_res'])))
    if not layers:
        return []
    out = [[float(len(layers)), float(LAYER_TEXELS), 0.0, 0.0]]
    for kind, g in layers:
        out.append([g['origin'][0], g['origin'][1], g['origin'][2], g['cell']])
        out.append([float(g['N']), float(g['TX']), float(kind), 1.0])
    return out


def read_layer(texels, kind):
    """Grid layer `kind` of a packed buffer -> geometry dict, or None (CPU twin of pxgLayer)."""
    import effectors_logic as EL
    g0 = EL.grid_start(texels)
    if g0 < 0:
        return None
    n = int(round(texels[g0][0]))
    st = max(LAYER_TEXELS, int(round(texels[g0][1])))
    for j in range(n):
        a, b = texels[g0 + 1 + j * st], texels[g0 + 2 + j * st]
        if int(round(b[2])) == kind and b[3] > 0.5:
            N = int(round(b[0]))
            tx = int(round(b[1]))
            return {'origin': tuple(a[:3]), 'cell': a[3], 'N': N, 'TX': tx, 'TY': int(math.ceil(N / float(tx))),
                    'atlas': (tx * N, int(math.ceil(N / float(tx))) * N)}
    return None


# ------------------------------------------------------------------------------------------------ numpy references

def to_atlas(vol, N, tx):
    """(N, N, N, C) volume indexed [z, y, x] -> (TY*N, TX*N, C) atlas image indexed [ay, ax]."""
    import numpy as np
    ty = int(math.ceil(N / float(tx)))
    out = np.zeros((ty * N, tx * N) + vol.shape[3:], dtype=vol.dtype)
    for z in range(N):
        ox, oy = (z % tx) * N, (z // tx) * N
        out[oy:oy + N, ox:ox + N] = vol[z]
    return out


def from_atlas(img, N, tx):
    import numpy as np
    vol = np.zeros((N, N, N) + img.shape[2:], dtype=img.dtype)
    for z in range(N):
        ox, oy = (z % tx) * N, (z // tx) * N
        vol[z] = img[oy:oy + N, ox:ox + N]
    return vol


def scatter_ref(points, g, prev=None, alpha=0.5, valid=None, f32=False):
    """CPU twin of eff_grid_scatter: world points (n, 3) -> (N, N, N, 4) [z, y, x] volume of (sum of cell-local
    offsets xyz in the shader's fixed point, count) + prev. valid (n,) alpha values (> alpha counts; None = all).
    f32 = voxel index in float32 like the GPU (live b2: points exactly on a voxel face land as the shader puts them)."""
    import numpy as np
    N = g['N']
    vol = np.zeros((N, N, N, 4)) if prev is None else np.array(prev, dtype=np.float64)
    P = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    if valid is not None:
        P = P[np.asarray(valid, dtype=np.float64).ravel() > alpha]
    if f32:
        G = ((P.astype(np.float32) - np.asarray(g['origin'], dtype=np.float32)) / np.float32(g['cell'])).astype(
            np.float64)
    else:
        G = (P - np.asarray(g['origin'])) / g['cell']
    V = np.floor(G).astype(np.int64)
    ok = np.all((V >= 0) & (V < N), axis=1)
    V, G = V[ok], G[ok]
    F = np.clip(G - V, 0.0, 1.0)
    Fq = np.floor(F * FX + 0.5) / FX                       # fixed point as the shader's uint(f * FX + 0.5)
    np.add.at(vol, (V[:, 2], V[:, 1], V[:, 0], 3), 1.0)
    for k in range(3):
        np.add.at(vol, (V[:, 2], V[:, 1], V[:, 0], k), Fq[:, k])
    return vol


def seeds_ref(vol, g):
    """CPU twin of eff_grid_seed: (N, N, N, 4) scatter volume -> seeds (N, N, N, 4) (world centroid xyz, has)."""
    import numpy as np
    N = g['N']
    out = np.zeros((N, N, N, 4))
    cnt = vol[..., 3]
    has = cnt > 0.5
    zz, yy, xx = np.meshgrid(np.arange(N), np.arange(N), np.arange(N), indexing='ij')
    vox = np.stack([xx, yy, zz], axis=-1).astype(np.float64)
    cen = np.asarray(g['origin']) + (vox + vol[..., :3] / np.maximum(cnt, 1.0)[..., None]) * g['cell']
    out[has, :3] = cen[has]
    out[has, 3] = 1.0
    return out


def jfa_pass_ref(seeds, g, k):
    """CPU twin of one eff_grid_jfa pass (step k; 0 = copy). Ties keep the first minimum in the shader's tap order
    (dz, dy, dx from -1 to 1, the voxel's own seed first)."""
    import numpy as np
    if k <= 0:
        return np.array(seeds)
    N = g['N']
    zz, yy, xx = np.meshgrid(np.arange(N), np.arange(N), np.arange(N), indexing='ij')
    cen = np.asarray(g['origin']) + (np.stack([xx, yy, zz], axis=-1) + 0.5) * g['cell']
    best = np.array(seeds)
    bd = np.where(best[..., 3] > 0.5, ((best[..., :3] - cen) ** 2).sum(-1), np.inf)
    for dz in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0 and dz == 0:
                    continue
                sz, sy, sx = zz + dz * k, yy + dy * k, xx + dx * k
                inb = (sz >= 0) & (sz < N) & (sy >= 0) & (sy < N) & (sx >= 0) & (sx < N)
                s = seeds[np.clip(sz, 0, N - 1), np.clip(sy, 0, N - 1), np.clip(sx, 0, N - 1)]
                d = np.where(inb & (s[..., 3] > 0.5), ((s[..., :3] - cen) ** 2).sum(-1), np.inf)
                better = d < bd
                best[better] = s[better]
                bd = np.where(better, d, bd)
    return best


def field_ref(points, g, alpha=0.5, valid=None):
    """Whole pipeline (scatter -> seed -> JFA_PASSES passes) -> nearest-seed volume (N, N, N, 4)."""
    s = seeds_ref(scatter_ref(points, g, alpha=alpha, valid=valid), g)
    for k in jfa_steps(g['N']):
        s = jfa_pass_ref(s, g, k)
    return s


def query_ref(field, g, P):
    """CPU twin of pxgFieldNearest: distance from points P (n, 3) to the nearest seed among the 8 voxels around each
    (clamped to the grid), 1e9 when none has a seed."""
    import numpy as np
    P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
    N = g['N']
    G = (P - np.asarray(g['origin'])) / g['cell'] - 0.5
    B = np.floor(G).astype(np.int64)
    best = np.full(len(P), 1e18)
    for c in ((0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0), (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 1, 1)):
        V = np.clip(B + np.asarray(c), 0, N - 1)
        s = field[V[:, 2], V[:, 1], V[:, 0]]
        d = np.where(s[:, 3] > 0.5, ((P - s[:, :3]) ** 2).sum(-1), 1e18)
        best = np.minimum(best, d)
    return np.where(best < 1e17, np.sqrt(best), 1e9)


def brute_nearest(points, P):
    import numpy as np
    A = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
    out = np.empty(len(P))
    for i in range(0, len(P), 256):
        d = ((P[i:i + 256, None, :] - A[None, :, :]) ** 2).sum(-1)
        out[i:i + 256] = np.sqrt(d.min(axis=1))
    return out


def voxel_centres(g):
    """(N, N, N, 3) [z, y, x] world centres."""
    import numpy as np
    N = g['N']
    zz, yy, xx = np.meshgrid(np.arange(N), np.arange(N), np.arange(N), indexing='ij')
    return np.asarray(g['origin']) + (np.stack([xx, yy, zz], axis=-1) + 0.5) * g['cell']


def paint_step_ref(prev, w_add, w_erase, rate, decay, dt, clear=False):
    """CPU twin of eff_grid_paint (per voxel arrays): -> (paint, wAdd, wErase, 1)."""
    import numpy as np
    prev = np.asarray(prev, dtype=np.float64)
    if clear:
        p = np.zeros_like(prev)
    else:
        p = np.clip(prev * max(0.0, 1.0 - decay * dt) + rate * dt * (np.asarray(w_add) - np.asarray(w_erase)),
                    0.0, 1.0)
    return np.stack([p, np.asarray(w_add) * np.ones_like(p), np.asarray(w_erase) * np.ones_like(p),
                     np.ones_like(p)], axis=-1)


def sample_ref(vol, g, P, c=0):
    """CPU twin of pxgSample (trilinear between voxel centres, clamped at the edges) of channel c."""
    import numpy as np
    P = np.asarray(P, dtype=np.float64).reshape(-1, 3)
    N = g['N']
    G = np.clip((P - np.asarray(g['origin'])) / g['cell'] - 0.5, 0.0, N - 1.0)
    B = np.minimum(np.floor(G).astype(np.int64), N - 2) if N > 1 else np.zeros_like(G, dtype=np.int64)
    F = G - B
    out = np.zeros(len(P))
    for cx in (0, 1):
        for cy in (0, 1):
            for cz in (0, 1):
                w = (F[:, 0] if cx else 1 - F[:, 0]) * (F[:, 1] if cy else 1 - F[:, 1]) * \
                    (F[:, 2] if cz else 1 - F[:, 2])
                out += w * vol[B[:, 2] + cz, B[:, 1] + cy, B[:, 0] + cx, c]
    return out


# ------------------------------------------------------------------------------------------------ consumer GLSL

def consumer_defines(field=None, paint=None):
    """Define lines a consumer adds (before px_common) to read the grid: field / paint = the GLSL sampler expression
    (a GLSL MAT: a sampler on its Samplers page, e.g. 'sEffGrid' + 'uniform sampler2D sEffGrid;'; a GLSL TOP: an
    input, e.g. 'sTD2DInputs[2]')."""
    out = []
    if field:
        out.append('#define PXE_GRID %s' % field)
    if paint:
        out.append('#define PXE_PAINT %s' % paint)
    return '\n'.join(out) + ('\n' if out else '')
