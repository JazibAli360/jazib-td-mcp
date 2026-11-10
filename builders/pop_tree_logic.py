# pop_tree_logic - numpy mirror of POP_tree (TC-18 GPU recursive tree; builder builders/pop_tree.py, doc
# docs/builds/pop_lane_h.md "TC-18"). Implicit complete B-ary tree in BFS order: node k > 0 has parent (k - 1) // B and
# child slot (k - 1) % B; Depth = branchings, so levels 0..Depth and N = (B^(Depth+1) - 1) / (B - 1) segments. The GPU
# walks each node's ancestor chain from the root; this mirror builds level by level from the parents (same maths,
# float64). Runs OUTSIDE TD (T-184). ASCII only.
import math

import numpy as np

SEG_CAP = 262144
PTS_CAP = 1048576
M32 = 0xFFFFFFFF
TAU = 6.283185307179586

DEFAULTS = {'branches': 2, 'depth': 10, 'spread': 30.0, 'twist': 137.5, 'jitter': 8.0, 'ratio': 0.72,
            'length': 0.35, 'sway': 6.0, 'time': 0.0, 'progress': 1.0, 'seed': 1, 'lenjitter': 0.15,
            'width': 1.0, 'widthratio': 0.75}


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


def max_depth(b):
    """Largest Depth with N <= SEG_CAP (the builder's dims CHOP uses the same table)."""
    d = 0
    while (b ** (d + 2) - 1) // (b - 1) <= SEG_CAP:
        d += 1
    return d


def depth_eff(b, d):
    return max(0, min(int(d), max_depth(int(b))))


def nseg(b, d):
    d = depth_eff(b, d)
    return (b ** (d + 1) - 1) // (b - 1)


def seg_side(n):
    return max(int(math.ceil(math.sqrt(max(n, 1)))), 1)


def samples_eff(n, s):
    return max(1, min(int(s), PTS_CAP // max(n, 1)))


def lowbias(x):
    x = np.asarray(x, dtype=np.uint64) & M32
    x ^= x >> np.uint64(16)
    x = (x * np.uint64(0x7feb352d)) & M32
    x ^= x >> np.uint64(15)
    x = (x * np.uint64(0x846ca68b)) & M32
    x ^= x >> np.uint64(16)
    return x


def h1(i, s):
    """GLSL: float(lowbias(uint(i) * 747796405u + uint(s) * 2891336453u + 1u) >> 8) / 16777216.0"""
    i = np.asarray(i, dtype=np.int64).astype(np.uint64) & M32
    s = np.asarray(s, dtype=np.int64).astype(np.uint64) & M32
    h = lowbias((i * np.uint64(747796405) + s * np.uint64(2891336453) + np.uint64(1)) & M32)
    return (h >> np.uint64(8)).astype(np.float64) / 16777216.0


def rx(a):
    c, s = np.cos(a), np.sin(a)
    z, o = np.zeros_like(a), np.ones_like(a)
    return np.stack([np.stack([o, z, z], -1), np.stack([z, c, -s], -1), np.stack([z, s, c], -1)], -2)


def ry(a):
    c, s = np.cos(a), np.sin(a)
    z, o = np.zeros_like(a), np.ones_like(a)
    return np.stack([np.stack([c, z, s], -1), np.stack([z, o, z], -1), np.stack([-s, z, c], -1)], -2)


def rz(a):
    c, s = np.cos(a), np.sin(a)
    z, o = np.zeros_like(a), np.ones_like(a)
    return np.stack([np.stack([c, -s, z], -1), np.stack([s, c, z], -1), np.stack([z, z, o], -1)], -2)


def level_of(k, b):
    k = np.asarray(k, dtype=np.int64)
    lev = np.zeros_like(k)
    kk = k.copy()
    while (kk > 0).any():
        m = kk > 0
        lev[m] += 1
        kk[m] = (kk[m] - 1) // b
    return lev


def segments(p):
    """-> start (N x 3), end (N x 3, grown by Progress), level (N), width (N) in BFS order."""
    b = int(p['branches'])
    D = depth_eff(b, p['depth'])
    N = nseg(b, D)
    R = np.zeros((N, 3, 3))
    L = np.zeros(N)
    P0 = np.zeros((N, 3))
    lev = np.zeros(N, dtype=np.int64)
    R[0] = np.eye(3)
    L[0] = p['length']
    seed = int(p['seed'])
    spread, twist, jit = math.radians(p['spread']), math.radians(p['twist']), math.radians(p['jitter'])
    sway = math.radians(p['sway'])
    start = 1
    for l in range(1, D + 1):
        cnt = b ** l
        k = np.arange(start, start + cnt)
        par = (k - 1) // b
        slot = (k - 1) % b
        lev[k] = l
        P0[k] = P0[par] + R[par][:, :, 1] * L[par][:, None]           # parent end (full length)
        phi = slot * TAU / b + l * twist + jit * (2.0 * h1(k, seed) - 1.0)
        spr = spread + jit * (2.0 * h1(k, seed + 1) - 1.0)
        sw = np.full(cnt, sway * math.sin(p['time'] + l * 0.7) * l / max(D, 1))
        R[k] = R[par] @ ry(phi) @ rz(sw) @ rx(spr)
        L[k] = L[par] * p['ratio'] * (1.0 + p['lenjitter'] * (2.0 * h1(k, seed + 2) - 1.0))
        start += cnt
    g = np.clip(p['progress'] * (D + 1) - lev, 0.0, 1.0)
    end = P0 + R[:, :, 1] * (L * g)[:, None]
    width = p['width'] * p['widthratio'] ** lev
    return P0, end, lev, width


def texture(p):
    """The segs texture (2 * side wide x side tall rgba): texel (2x, y) = start xyz + level, (2x + 1, y) = end xyz +
    width for segment k = y * side + x; unused texels: level -1, rest 0."""
    s0, s1, lev, w = segments(p)
    n = len(lev)
    side = seg_side(n)
    T = np.zeros((side, 2 * side, 4))
    T[..., 3] = 0.0
    T[:, 0::2, 3] = -1.0
    k = np.arange(n)
    y, x = k // side, k % side
    T[y, 2 * x, :3] = s0
    T[y, 2 * x, 3] = lev
    T[y, 2 * x + 1, :3] = s1
    T[y, 2 * x + 1, 3] = w
    return T


def dust(p, samples):
    """Point positions the points MAT draws (sample j of segment k at (j + 0.5) / S), zero-length segments hidden."""
    s0, s1, lev, _ = segments(p)
    S = samples_eff(len(lev), samples)
    f = (np.arange(S) + 0.5) / S
    pts = s0[:, None, :] + (s1 - s0)[:, None, :] * f[None, :, None]
    vis = np.linalg.norm(s1 - s0, axis=-1) > 1e-7
    return pts[vis].reshape(-1, 3)
