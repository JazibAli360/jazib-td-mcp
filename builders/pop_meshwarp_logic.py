# pop_meshwarp_logic - numpy mirror of POP_meshwarp's vertex maths (TC-07; builder builders/pop_meshwarp.py, doc
# docs/builds/pop_lane_h.md "TC-07"). Pure Python + numpy, runs OUTSIDE TD (T-184): the LIVE CHECK dumps out1 to .npy in
# a read-only exec and compares it here. Every function matches the GLSL in pop_meshwarp.py line by line (same hash,
# same constants). ASCII only.
import math

import numpy as np

MODES = ['ripple', 'swirl', 'slice', 'melt', 'wave', 'bulge', 'noise']
MODE_LABELS = ['Ripple (rings from the centre)', 'Swirl (twist round the centre)', 'Slice (bands shift on a clock)',
               'Melt (columns drip down)', 'Wave (travelling sheet wave)', 'Bulge (lens round the centre)',
               'Noise (value-noise wobble)']
TAU = 6.283185307179586
LIGHT = (0.3, 0.5, 0.8)
M32 = 0xFFFFFFFF

DEFAULTS = {'mode': 'ripple', 'strength': 0.5, 'freq': 3.0, 'time': 0.0, 'cx': 0.5, 'cy': 0.5, 'radius': 0.5,
            'depth': 0.3, 'uvwarp': 1.0, 'amount': 1.0, 'aspect': 1080.0 / 1920.0, 'shade': 0.5, 'seed': 1}


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
    """GLSL: float(lowbias(uint(i) * 747796405u + uint(s) * 2891336453u + 1u) >> 8) / 16777216.0"""
    h = lowbias((_u(i) * np.uint64(747796405) + _u(s) * np.uint64(2891336453) + np.uint64(1)) & M32)
    return (h >> np.uint64(8)).astype(np.float64) / 16777216.0


def h2(x, y, s):
    h = lowbias((_u(y) * np.uint64(2891336453) + _u(s) * np.uint64(1597334677) + np.uint64(7)) & M32)
    h = lowbias(h ^ ((_u(x) * np.uint64(747796405)) & M32))
    return (h >> np.uint64(8)).astype(np.float64) / 16777216.0


def vnoise(px, py, s):
    ix, iy = np.floor(px), np.floor(py)
    fx, fy = px - ix, py - iy
    wx, wy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    ix, iy = ix.astype(np.int64), iy.astype(np.int64)
    a, b = h2(ix, iy, s), h2(ix + 1, iy, s)
    c, d = h2(ix, iy + 1, s), h2(ix + 1, iy + 1, s)
    return (a + (b - a) * wx) * (1 - wy) + (c + (d - c) * wx) * wy


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


def warp(u, v, p):
    """(u, v) grid coords in 0..1 -> (u', v') texture lookup and dz (sheet units, height = 1). Amount scales both."""
    u = np.asarray(u, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    m = MODES.index(p['mode']) if isinstance(p['mode'], str) else int(p['mode'])
    S, F, t, asp = p['strength'], p['freq'], p['time'], p['aspect']
    qx, qy = (u - p['cx']) * asp, v - p['cy']
    r = np.sqrt(qx * qx + qy * qy)
    R = max(p['radius'], 1e-4)
    f = np.exp(-(r / R) ** 2)
    du = np.zeros_like(u)
    dv = np.zeros_like(u)
    dz = np.zeros_like(u)
    if m == 0:                                   # ripple
        h = S * np.sin(TAU * (F * r - t)) * f
        inv = np.where(r > 1e-6, 1.0 / np.maximum(r, 1e-6), 0.0)
        du, dv, dz = qx * inv * h * 0.05 / asp, qy * inv * h * 0.05, h
    elif m == 1:                                 # swirl
        a = S * math.pi * f * (0.75 + 0.25 * math.sin(TAU * t * 0.25))
        ca, sa = np.cos(a), np.sin(a)
        rx, ry = ca * qx - sa * qy, sa * qx + ca * qy
        du, dv, dz = (rx - qx) / asp, ry - qy, 0.5 * S * f
    elif m == 2:                                 # slice
        k = np.floor(v * F * 8.0).astype(np.int64)
        s = h1(k, int(p['seed']) + int(math.floor(t * 2.0))) - 0.5
        du, dz = S * 0.1 * s, S * 0.5 * s
    elif m == 3:                                 # melt
        n = vnoise(u * F * 24.0, np.zeros_like(u) + 0.5, int(p['seed']))
        amt = S * 0.35 * n * (0.5 - 0.5 * math.cos(TAU * t * 0.1))
        dv, dz = amt * v, -0.5 * amt
    elif m == 4:                                 # wave
        ph, ph2 = TAU * (F * u * asp + t), TAU * (F * 0.7 * v - 0.5 * t)
        dz = S * np.sin(ph) * np.cos(ph2) * 0.5
        du, dv = 0.02 * S * np.cos(ph) * np.cos(ph2), -0.02 * S * np.sin(ph) * np.sin(ph2)
    elif m == 5:                                 # bulge
        s = S * f
        du, dv, dz = -0.5 * s * qx / asp, -0.5 * s * qy, 0.5 * s
    elif m == 6:                                 # noise
        bx, by = u * asp * F * 4.0, v * F * 4.0
        n1 = vnoise(bx + t * 0.5, by, int(p['seed']))
        n2 = vnoise(bx + 17.3, by + t * 0.5, int(p['seed']))
        du, dv, dz = 0.05 * S * (n2 - 0.5), 0.05 * S * (n1 - 0.5), S * (n1 - 0.5)
    k_uv = p['amount'] * p['uvwarp']
    return u + du * k_uv, v + dv * k_uv, dz * p['amount'] * p['depth']


def position(u, v, p):
    _, _, dz = warp(u, v, p)
    return np.stack([(np.asarray(u) - 0.5) * p['aspect'], np.asarray(v) - 0.5, dz], -1)


def normal(u, v, p, eu, ev):
    """Finite-difference normal exactly as the vertex shader (step = one grid cell)."""
    a = position(u, v, p)
    pu = position(np.asarray(u) + eu, v, p) - a
    pv = position(u, np.asarray(v) + ev, p) - a
    n = np.cross(pu, pv)
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)


def shade(n, s):
    L = np.array(LIGHT) / np.linalg.norm(LIGHT)
    lam = np.maximum((n * L).sum(-1), 0.0)
    return 1.0 + (0.3 + 0.7 * lam - 1.0) * s


def bilinear(img, u, v):
    """Sample img (H x W x C, row 0 = bottom like a TD texture) at normalised u, v; clamp to edge (sampler 'hold')."""
    H, W = img.shape[:2]
    x = np.clip(u * W - 0.5, 0, W - 1)
    y = np.clip(v * H - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    a = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    b = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return a * (1 - fy) + b * fy


def reference_flat(img, p, W, H, edge='hold'):
    """Expected out1 when Depth = 0 and Shade = 0 (flat sheet filling the frame, pure texture warp): per output pixel
    centre, sample img at warp(u, v). The mesh interpolates uv linearly across each grid cell, so the live image differs
    from this per-pixel reference by the piecewise-linear error (LIVE CHECK tolerance, see pop_lane_h.md)."""
    q = dict(p, depth=0.0)
    y, x = np.mgrid[0:H, 0:W]
    u, v = (x + 0.5) / W, (y + 0.5) / H
    uu, vv, _ = warp(u, v, q)
    out = bilinear(img, uu, vv)
    if edge == 'zero':
        ok = ((uu >= 0) & (uu <= 1) & (vv >= 0) & (vv <= 1))[..., None]
        out = out * ok
    return out


def reference_mesh_flat(img, p, W, H, cols, rows):
    """Same as reference_flat but with uv interpolated linearly inside each grid cell (what the GPU does for the
    Grid POP quads, split into 2 triangles is ignored: bilinear-in-cell is the closer model for small cells)."""
    q = dict(p, depth=0.0)
    y, x = np.mgrid[0:H, 0:W]
    u, v = (x + 0.5) / W, (y + 0.5) / H
    gx, gy = u * (cols - 1), v * (rows - 1)
    i0 = np.clip(np.floor(gx).astype(int), 0, cols - 2)
    j0 = np.clip(np.floor(gy).astype(int), 0, rows - 2)
    fx, fy = gx - i0, gy - j0
    gu = np.arange(cols) / (cols - 1.0)
    gv = np.arange(rows) / (rows - 1.0)
    GU, GV = np.meshgrid(gu, gv)
    WU, WV, _ = warp(GU, GV, q)

    def lerp(A):
        a = A[j0, i0] * (1 - fx) + A[j0, i0 + 1] * fx
        b = A[j0 + 1, i0] * (1 - fx) + A[j0 + 1, i0 + 1] * fx
        return a * (1 - fy) + b * fy
    return bilinear(img, lerp(WU), lerp(WV))


def test_card(W, H):
    """Deterministic RGBA test image (checker + gradients), premultiplied, alpha 1."""
    y, x = np.mgrid[0:H, 0:W]
    chk = ((x // 32 + y // 32) % 2).astype(np.float64)
    img = np.stack([x / (W - 1.0), y / (H - 1.0), 0.25 + 0.5 * chk, np.ones_like(chk)], -1)
    return img


def grid_points(cols, rows):
    return cols * rows


def vfov_deg(dist, zoom):
    """Vertical fov that makes the 1-unit-tall sheet fill the frame at distance dist (Zoom 1)."""
    return 2.0 * math.degrees(math.atan(0.5 / max(dist, 0.01))) / max(zoom, 0.01)
