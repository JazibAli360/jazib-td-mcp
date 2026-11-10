# pop_crack3d_logic - numpy mirror of POP_crack3d's pixel maths (TC-12; builder builders/pop_crack3d.py, doc
# docs/builds/pop_lane_h.md "TC-12"). 3D Worley F1 / F2 on object-space positions with a jittered cell grid (27-cell
# search), crack mask (F2 - F1 < Width), front from the Impact point, eroded cells. Runs OUTSIDE TD (T-184): the LIVE
# CHECK dumps Style 'pos' (object xyz) and Style 'data' (F1, F2 - F1, crack, reached) frames of the same view and
# compares them here. Same lowbias hash as pop_meshwarp_logic. ASCII only.
import numpy as np

from pop_meshwarp_logic import lowbias, M32

SHAPES = ['sphere', 'torus', 'box', 'custom']
STYLES = ['lit', 'lines', 'pos', 'data']
STYLE_LABELS = ['Lit surface + glowing cracks', 'Cracks only (transparent overlay)',
                'Data: object position xyz (LIVE CHECK)', 'Data: F1, F2 - F1, crack, reached (LIVE CHECK)']

DEFAULTS = {'cellscale': 4.0, 'width': 0.05, 'progress': 1.0, 'impact': (0.0, 0.0, 1.0), 'reach': 2.5,
            'erode': 0.0, 'seed': 1, 'soft': 0.05}


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


def _u(i):
    return np.asarray(i, dtype=np.int64).astype(np.uint64) & M32


def hcell(cx, cy, cz, s):
    """GLSL: lowbias((uint(c.x) * 747796405u) ^ (uint(c.y) * 1597334677u) ^ (uint(c.z) * 3812015801u) ^ (uint(s) *
    2891336453u + 11u)) - one lowbias per cell (27 Oct live cost fix, was 3 chained)."""
    k = ((_u(cx) * np.uint64(747796405)) & M32) ^ ((_u(cy) * np.uint64(1597334677)) & M32) \
        ^ ((_u(cz) * np.uint64(3812015801)) & M32) ^ ((_u(s) * np.uint64(2891336453) + np.uint64(11)) & M32)
    return lowbias(k)


def hcomp(h, k):
    """Component k of a cell hash in [0, 1): float(lowbias(h + uint(k) * 0x9E3779B9u) >> 8) / 16777216."""
    v = lowbias((np.asarray(h, dtype=np.uint64) + np.uint64(k) * np.uint64(0x9E3779B9)) & M32)
    return (v >> np.uint64(8)).astype(np.float64) / 16777216.0


def site(c, s):
    """Jittered site of integer cell c (N x 3) in cell units."""
    c = np.asarray(c, dtype=np.int64)
    h = hcell(c[..., 0], c[..., 1], c[..., 2], s)
    return c + jit(h), h


def jit(h):
    """GLSL jit(): 10-bit fields of the cell hash / 1024 (x bits 0-9, y 10-19, z 20-29)."""
    h = np.asarray(h, dtype=np.uint64)
    return np.stack([(h >> np.uint64(b)) & np.uint64(1023) for b in (0, 10, 20)], -1).astype(np.float64) / 1024.0


def worley(pos, p):
    """pos (N x 3, object space) -> F1, F2 (cell units), nearest cell (N x 3 int), its hash."""
    q = np.asarray(pos, dtype=np.float64) * p['cellscale']
    base = np.floor(q).astype(np.int64)
    F1 = np.full(q.shape[0], 1e9)
    F2 = np.full(q.shape[0], 1e9)
    cid = np.zeros_like(base)
    hid = np.zeros(q.shape[0], dtype=np.uint64)
    for dz in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                c = base + np.array([dx, dy, dz])
                st, h = site(c, int(p['seed']))
                d = np.linalg.norm(st - q, axis=-1)
                closer = d < F1
                F2 = np.where(closer, F1, np.minimum(F2, d))
                cid = np.where(closer[:, None], c, cid)
                hid = np.where(closer, h, hid)
                F1 = np.where(closer, d, F1)
    return F1, F2, cid, hid


def worley_pruned(pos, p):
    """Mirror of the shader's pruned search (perf 27 Oct): centre cell, then faces, then edges + corners, skipping a
    cell whose lower-bound squared distance (site inside the cell) is >= the current F2. Same results as worley();
    also returns the mean number of cells hashed per point."""
    q = np.asarray(pos, dtype=np.float64) * p['cellscale']
    base = np.floor(q).astype(np.int64)
    f = q - base
    lo, hi = f * f, (1.0 - f) ** 2
    F1 = np.full(q.shape[0], 1e9)
    F2 = np.full(q.shape[0], 1e9)
    cid = np.zeros_like(base)
    hid = np.zeros(q.shape[0], dtype=np.uint64)
    visits = np.zeros(q.shape[0])
    offs = [(0, 0, 0)] + [o for ps in (0, 1) for o in [(dx, dy, dz) for dz in (-1, 0, 1) for dy in (-1, 0, 1)
                                                       for dx in (-1, 0, 1)]
                          if sum(map(abs, o)) and (ps == 0) == (sum(map(abs, o)) == 1)]
    for o in offs:
        lb = sum(np.where(o[a] < 0, lo[:, a], np.where(o[a] > 0, hi[:, a], 0.0)) for a in range(3))
        go = lb < F2
        c = base + np.array(o)
        st, h = site(c, int(p['seed']))
        d = np.sum((st - q) ** 2, axis=-1)
        closer = go & (d < F1)
        F2 = np.where(closer, F1, np.where(go, np.minimum(F2, d), F2))
        cid = np.where(closer[:, None], c, cid)
        hid = np.where(closer, h, hid)
        F1 = np.where(closer, d, F1)
        visits += go
    return np.sqrt(F1), np.sqrt(F2), cid, hid, float(visits.mean())


def front(pos, p):
    """Reached by the crack front: |pos - impact| <= Reach x Progress (soft edge of width Soft, 0..1)."""
    d = np.linalg.norm(np.asarray(pos, dtype=np.float64) - np.asarray(p['impact']), axis=-1)
    R = p['reach'] * p['progress']
    return np.clip((R - d) / max(p['soft'], 1e-6) + 0.5, 0.0, 1.0)


def crack_mask(pos, p):
    """Hard crack mask (the shader smooths it over fwidth): F2 - F1 < Width AND the front reached the pixel."""
    F1, F2, _, _ = worley(pos, p)
    return ((F2 - F1) < p['width']) & (front(pos, p) > 0.5)


def eroded(pos, p):
    """Pixel is discarded: its nearest cell's hash comp 3 < Erode AND that cell's site was reached by the front."""
    F1, F2, cid, hid = worley(pos, p)
    st, _ = site(cid, int(p['seed']))
    reached = front(st / p['cellscale'], p) > 0.5
    return (hcomp(hid, 3) < p['erode']) & reached


def sphere_points(n, rng=None):
    rng = rng or np.random.default_rng(0)
    v = rng.normal(size=(n, 3))
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def check_data(pos_arr, data_arr, p, tol=2e-3):
    """LIVE CHECK: pos frame (xyz, a) + data frame (F1, F2 - F1, crack, reached) of the same view. Compares F1 and
    F2 - F1 on covered pixels away from cell borders (where the nearest-site choice can flip under float32)."""
    P = np.asarray(pos_arr, dtype=np.float64).reshape(-1, 4)
    D = np.asarray(data_arr, dtype=np.float64).reshape(-1, 4)
    m = (P[:, 3] > 0.5) & (D[:, 3] >= 0.0)
    if not m.any():
        return {'pass': False, 'cover': 0.0}
    F1, F2, _, _ = worley(P[m, :3], p)
    gap = F2 - F1
    keep = gap > 0.01                                          # skip ties at cell borders
    e1 = np.abs(D[m, 0] - F1)[keep]
    e2 = np.abs(D[m, 1] - gap)[keep]
    hard = (gap < p['width']) & (front(P[m, :3], p) > 0.5)
    agree = float(((D[m, 2] > 0.5) == hard).mean())
    out = {'cover': float(m.mean()), 'f1_p99': float(np.percentile(e1, 99)), 'gap_p99': float(np.percentile(e2, 99)),
           'crack_agree': agree, 'crack_frac': float(hard.mean())}
    out['pass'] = out['f1_p99'] <= tol and out['gap_p99'] <= tol and agree >= 0.98
    return out
