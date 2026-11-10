# pop_rd3d_logic - numpy mirror of POP_rd3d (TC-11; builder builders/pop_rd3d.py, doc docs/builds/pop_lane_h.md
# "TC-11"). Gray-Scott on a WRAP grid (Karl Sims 3x3 Laplacian: centre -1, edges 0.2, diagonals 0.05; Du 1, Dv 0.5,
# dt 1 - the same constants as builders/reaction_diffusion_logic.py, re-stated here, not imported), the seed hash, the
# step counter (state.b) and the surface param + displacement. Runs OUTSIDE TD (T-184). ASCII only.
import math

import numpy as np

LAP_EDGE, LAP_DIAG = 0.2, 0.05
DU, DV, DT = 1.0, 0.5, 1.0
PRESETS = [
    ('coral', 0.0545, 0.062),
    ('mitosis', 0.0367, 0.0649),
    ('worms', 0.078, 0.061),
    ('spots', 0.03, 0.0625),
    ('maze', 0.029, 0.057),
    ('custom', 0.0545, 0.062),
]
PRESET_NAMES = [p[0] for p in PRESETS]
SHAPES = ['torus', 'sphere', 'plane']
TAU = 6.283185307179586
TORUS_R, TORUS_r, SPHERE_R = 0.6, 0.25, 0.7
SEED_CELL = 16
M32 = 0xFFFFFFFF


def fk(preset, customf=0.0545, customk=0.062):
    for n, f, k in PRESETS:
        if n == preset:
            return (customf, customk) if n == 'custom' else (f, k)
    raise KeyError(preset)


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


def h2(x, y, s):
    """GLSL h2 (same as pop_meshwarp): 24-bit float in [0, 1)."""
    h = lowbias((_u(y) * np.uint64(2891336453) + _u(s) * np.uint64(1597334677) + np.uint64(7)) & M32)
    h = lowbias(h ^ ((_u(x) * np.uint64(747796405)) & M32))
    return (h >> np.uint64(8)).astype(np.float64) / 16777216.0


def seed_state(w, h, seed, density=0.35, radius=0.3, dtype=np.float32):
    """Reseed: U = 1, V = 1 inside a disc (radius x cell) in cells (SEED_CELL texels) whose hash < density.
    state[..., 0] = U, 1 = V, 2 = step count, 3 = 1. Row 0 = bottom (TD texel y)."""
    y, x = np.mgrid[0:h, 0:w]
    cx, cy = x // SEED_CELL, y // SEED_CELL
    on = h2(cx, cy, seed) < density
    fx = (x % SEED_CELL + 0.5) / SEED_CELL - 0.5
    fy = (y % SEED_CELL + 0.5) / SEED_CELL - 0.5
    inside = (fx * fx + fy * fy) < radius * radius
    s = np.zeros((h, w, 4), dtype=dtype)
    s[..., 0] = 1.0
    s[..., 1] = np.where(on & inside, 1.0, 0.0)
    s[..., 3] = 1.0
    return s


def lap(a):
    e = np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)
    d = (np.roll(np.roll(a, 1, 0), 1, 1) + np.roll(np.roll(a, 1, 0), -1, 1) +
         np.roll(np.roll(a, -1, 0), 1, 1) + np.roll(np.roll(a, -1, 0), -1, 1))
    return (LAP_EDGE * e + LAP_DIAG * d - a).astype(a.dtype)


def gs_step(s, f, k, stopat=-1, du=DU, dv=DV, dt=DT):
    """One Gray-Scott step exactly as the compute pass (wrap edges). stopat >= 0 holds once count >= stopat."""
    if stopat >= 0 and s[0, 0, 2] >= stopat:
        return s.copy()
    dtp = s.dtype.type
    U, V = s[..., 0], s[..., 1]
    uvv = U * V * V
    o = s.copy()
    o[..., 0] = U + (dtp(du) * lap(U) - uvv + dtp(f) * (dtp(1) - U)) * dtp(dt)
    o[..., 1] = V + (dtp(dv) * lap(V) + uvv - dtp(f + k) * V) * dtp(dt)
    o[..., 2] = s[..., 2] + 1
    return o


def fused(s, f, k, steps, stopat=-1, tile=16, halo=4):
    """Mirror of the fused pass GSF (perf 27 Oct): per 16 x 16 workgroup, load a (tile + 2 halo)^2 region with wrapped
    coordinates, run `steps` interior updates (each cell = gs_step's maths; a cell holds once count >= stopat), keep
    the centre. Checks the tiling / wrap / halo logic against the per-step chain (gs_step x steps)."""
    h, w = s.shape[:2]
    out = s.copy()
    R = tile + 2 * halo
    for ty in range(0, h, tile):
        for tx in range(0, w, tile):
            ys = (np.arange(R) + ty - halo) % h
            xs = (np.arange(R) + tx - halo) % w
            reg = s[np.ix_(ys, xs)].copy()
            for _ in range(steps):
                nxt = gs_step(reg, f, k, -1)                        # roll-wrap inside the region: borders garbage
                hold = (reg[..., 2] >= stopat) if stopat >= 0 else np.zeros(reg.shape[:2], bool)
                nxt = np.where(hold[..., None], reg, nxt)
                reg[1:-1, 1:-1] = nxt[1:-1, 1:-1]
            cy, cx = min(tile, h - ty), min(tile, w - tx)
            out[ty:ty + cy, tx:tx + cx] = reg[halo:halo + cy, halo:halo + cx]
    return out


def run(w, h, seed, f, k, n, stopat=-1, dtype=np.float32):
    s = seed_state(w, h, seed, dtype=dtype)
    for _ in range(n):
        s = gs_step(s, f, k, stopat)
    return s


def base(shape, u, v, aspect=1.0):
    """Undisplaced surface point + its analytic outward normal for grid coords u, v in 0..1 (mirror of base())."""
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    if shape == 'torus':
        a, b = TAU * u, TAU * v
        ring = TORUS_R + TORUS_r * np.cos(b)
        p = np.stack([ring * np.cos(a), ring * np.sin(a), TORUS_r * np.sin(b)], -1)
        n = np.stack([np.cos(b) * np.cos(a), np.cos(b) * np.sin(a), np.sin(b)], -1)
    elif shape == 'sphere':
        th, ph = TAU * u, math.pi * v
        n = np.stack([np.sin(ph) * np.cos(th), -np.cos(ph), np.sin(ph) * np.sin(th)], -1)
        p = n * SPHERE_R
    else:
        p = np.stack([(u - 0.5) * aspect, v - 0.5, np.zeros_like(u)], -1)
        n = np.stack([np.zeros_like(u), np.zeros_like(u), np.ones_like(u)], -1)
    return p, n


def sample_wrap(img, u, v):
    """Bilinear, repeat on both axes (sampler extend repeat), TD texel centres."""
    H, W = img.shape[:2]
    x = np.asarray(u) * W - 0.5
    y = np.asarray(v) * H - 0.5
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    x0m, x1m, y0m, y1m = x0 % W, (x0 + 1) % W, y0 % H, (y0 + 1) % H
    a = img[y0m, x0m] * (1 - fx) + img[y0m, x1m] * fx
    b = img[y1m, x0m] * (1 - fx) + img[y1m, x1m] * fx
    return a * (1 - fy) + b * fy


def surface(shape, u, v, vtex, height, aspect=1.0):
    p, n = base(shape, u, v, aspect)
    d = sample_wrap(vtex, np.mod(u, 1.0), np.mod(v, 1.0))
    return p + n * (height * d)[..., None]
