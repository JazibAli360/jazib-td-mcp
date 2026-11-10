# pop_tubes_logic - numpy mirror of POP_tubes route A (TC-08 tube geometry; builder builders/pop_tubes.py, doc
# docs/builds/pop_lane_h.md "TC-08"). History texture (K samples x N tracks, column 0 = head, xyz + time stamp),
# its shift update, the analytic heads, and the tube vertex placement of the single tall Grid POP (rows = N x (S + 3):
# S + 1 ring rows + 2 hidden seam rows per track). Runs OUTSIDE TD (T-184). ASCII only.
import math

import numpy as np

SOURCES = ['lissajous', 'vortex', 'flow', 'input']
TAU = 6.283185307179586
M32 = 0xFFFFFFFF
GAP_ROWS = 2


def lowbias(x):
    x = np.asarray(x, dtype=np.uint64) & M32
    x ^= x >> np.uint64(16)
    x = (x * np.uint64(0x7feb352d)) & M32
    x ^= x >> np.uint64(15)
    x = (x * np.uint64(0x846ca68b)) & M32
    x ^= x >> np.uint64(16)
    return x


def _u(i):
    return np.asarray(i, dtype=np.int64).astype(np.uint64) & M32


def h1(i, s):
    h = lowbias((_u(i) * np.uint64(747796405) + _u(s) * np.uint64(2891336453) + np.uint64(1)) & M32)
    return (h >> np.uint64(8)).astype(np.float64) / 16777216.0


def head(src, i, t, scale, seed, prev=None, dt=0.0, xyz=None):
    """Head position of tracks i (int array) at module time t. Mirror of head() in pop_tubes.HIST."""
    i = np.asarray(i)
    s = int(seed)
    f1, f2, f3 = 0.7 + 0.6 * h1(i, s), 0.9 + 0.6 * h1(i, s + 1), 0.5 + 0.5 * h1(i, s + 2)
    p1, p2, p3 = TAU * h1(i, s + 3), TAU * h1(i, s + 4), TAU * h1(i, s + 5)
    if src == 'lissajous' or (src == 'input' and xyz is None):
        w = TAU * 0.25 * t
        p = np.stack([0.6 * np.sin(w * f1 + p1), np.sin(w * f2 + p2), 0.6 * np.sin(w * f3 + p3)], -1)
    elif src == 'vortex':
        a = TAU * 0.25 * t * (0.5 + f1) + p1
        rr = 0.2 + 0.4 * h1(i, s + 6)
        y = 0.8 * (2.0 * h1(i, s + 7) - 1.0) + 0.1 * np.sin(TAU * 0.1 * t + p2)
        p = np.stack([rr * np.cos(a), y, rr * np.sin(a)], -1)
    elif src == 'flow':
        q = np.asarray(prev, dtype=np.float64) / max(scale, 1e-6)
        v = np.stack([np.sin(2.1 * q[..., 1] + p1) + np.cos(1.7 * q[..., 2]),
                      np.sin(1.9 * q[..., 2] + p2) + np.cos(2.3 * q[..., 0]),
                      np.sin(2.2 * q[..., 0] + p3) + np.cos(1.6 * q[..., 1])], -1) * 0.5 - 0.3 * q
        return (q + v * min(max(dt, 0.0), 0.1)) * scale
    else:
        return np.asarray(xyz, dtype=np.float64) * scale
    return p * scale


def init_hist(n, k, p_head, t):
    """Reset: every column = the head (no garbage, no NaN tangents beyond the guarded one)."""
    H = np.zeros((n, k, 4))
    H[..., :3] = np.asarray(p_head)[:, None, :]
    H[..., 3] = t
    return H


def shift(H, p_head, t):
    """One frame: column 0 = new head (xyz, t), column k = old column k - 1. Rows = tracks."""
    O = np.empty_like(H)
    O[:, 1:] = H[:, :-1]
    O[:, 0, :3] = p_head
    O[:, 0, 3] = t
    return O


def rows_for(n, sides):
    return n * (sides + 1 + GAP_ROWS)


def frame(H, i, k):
    """Tangent + Gram-Schmidt frame of track i at sample k (central difference, clamped ends)."""
    K = H.shape[1]
    a = H[i, max(k - 1, 0), :3]
    b = H[i, min(k + 1, K - 1), :3]
    T = a - b
    L = np.linalg.norm(T)
    T = T / L if L > 1e-8 else np.array([0.0, 0.0, 1.0])
    up = np.array([0.0, 1.0, 0.0])
    if abs(T @ up) > 0.99:
        up = np.array([1.0, 0.0, 0.0])
    N = up - (up @ T) * T
    N = N / np.linalg.norm(N)
    B = np.cross(T, N)
    return T, N, B


def radius_at(k, K, radius, taper):
    return radius * max(1.0 - k / max(K - 1.0, 1.0), 0.0) ** taper


def vertex(H, col, row, sides, radius, taper):
    """Grid POP point (col, row) -> (position, gap flag). Mirror of the MAT vertex shader."""
    n, K = H.shape[0], H.shape[1]
    per = sides + 1 + GAP_ROWS
    i, j = row // per, row % per
    gap = 0.0
    if j == sides + 1:
        j, gap = sides, 1.0
    elif j == sides + 2:
        i, j, gap = min(i + 1, n - 1), 0, 1.0
    T, N, B = frame(H, i, col)
    a = TAU * j / sides
    r = radius_at(col, K, radius, taper)
    return H[i, col, :3] + r * (math.cos(a) * N + math.sin(a) * B), gap


def grid_uv(col, row, cols, rows):
    """TDPos().xy + 0.5 of Grid POP point (col, row) and the shader's index recovery."""
    u, v = col / (cols - 1.0), row / (rows - 1.0)
    return u, v, int(math.floor(u * (cols - 1) + 0.5)), int(math.floor(v * (rows - 1) + 0.5))
