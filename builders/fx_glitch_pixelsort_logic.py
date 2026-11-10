# fx_glitch_pixelsort_logic - numpy mirror of the FX_glitch 'pixelsort' Method Lite (TC-24 masked feedback streaks;
# shaders LITE / LITE_FX in builders/fx_glitch_pixelsort.py). The true sort is checked live against its own numpy
# sort (docs/builds/fx_glitch.md). Arrays: [y, x, rgba], row 0 = BOTTOM, 0..1. Pure numpy, no TD names. ASCII only.
import math

import numpy as np

M32 = 0xffffffff
LUMA = np.array([0.2126, 0.7152, 0.0722])
DEFAULTS = {'Amount': 1.0, 'Method': 0, 'Direction': 1, 'Angle': 30.0, 'Threshby': 0, 'Lower': 0.25, 'Upper': 0.8,
            'Invert': 0, 'Reverse': 0, 'Seed': 1, 'Litelength': 8.0, 'Litedecay': 0.95, 'Litenoise': 0.0,
            'Litejitter': 0.3, 'Liteblend': 0, 'Litegain': 1.0}


def pars_of(over=None):
    d = dict(DEFAULTS)
    d.update(over or {})
    return d


def lb32(x):
    x = np.asarray(x, dtype=np.uint64) & M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def hf(a, b):
    a = np.asarray(a).astype(np.int64) & M32
    return (lb32(((a.astype(np.uint64) * 0x9e3779b9) & M32) ^ lb32(int(b) & M32)) >> 8).astype(np.float64) / 16777216.0


def direction(P):
    rv = -1.0 if P['Reverse'] else 1.0
    d = int(P['Direction'])
    if d == 0:
        return rv, 0.0
    if d == 1:
        return 0.0, -rv
    a = math.radians(P['Angle'])
    return rv * math.cos(a), rv * math.sin(a)


def _hue(c):
    mx, mn = c.max(-1), c.min(-1)
    d = mx - mn
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    sd = np.where(d > 1e-6, d, 1.0)
    h = np.where(mx == r, np.mod((g - b) / sd, 6.0), np.where(mx == g, (b - r) / sd + 2.0, (r - g) / sd + 4.0))
    return np.where(d > 1e-6, h / 6.0, 0.0)


def _sat(c):
    mx = c.max(-1)
    return np.where(mx > 1e-6, (mx - c.min(-1)) / np.where(mx > 1e-6, mx, 1.0), 0.0)


def inside(img, P, mask=None):
    c = img[..., :3]
    tb = int(P['Threshby'])
    tv = (c * LUMA).sum(-1) if tb == 0 else (_hue(c) if tb == 1 else (_sat(c) if tb == 2 else
                                                                      (mask[..., :3] * LUMA).sum(-1)))
    m = (tv >= P['Lower']) & (tv <= P['Upper'])
    return ~m if P['Invert'] else m


def _bil(T, qx, qy):
    H, W = T.shape[:2]
    x, y = qx - 0.5, qy - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    x0, y0 = x0.astype(np.int64), y0.astype(np.int64)

    def tap(ix, iy):
        ok = (ix >= 0) & (iy >= 0) & (ix < W) & (iy < H)
        v = T[np.clip(iy, 0, H - 1), np.clip(ix, 0, W - 1)]
        return np.where(ok[..., None], v, 0.0)
    a = tap(x0, y0) * (1 - fx) + tap(x0 + 1, y0) * fx
    b = tap(x0, y0 + 1) * (1 - fx) + tap(x0 + 1, y0 + 1) * fx
    return a * (1 - fy) + b * fy


def lite_step(img, prev, P, frame=0, fresh=False, mask=None):
    """One `lite` cook: picture img [H, W, 4], previous trail prev [H, W, 4] (rows 0..H-1, None = fresh) -> trail."""
    H, W = img.shape[:2]
    m = inside(img, P, mask)
    S = np.zeros((H, W, 4))
    if prev is not None and not fresh:
        dx, dy = direction(P)
        px, py = -dy, dx
        y, x = np.mgrid[0:H, 0:W]
        pcx, pcy = x + 0.5, y + 0.5
        col = np.floor((pcx * px + pcy * py) / 2.0).astype(np.int64)
        sd = int(P['Seed']) * 7919
        jit = 1.0 - P['Litejitter'] * hf(col, sd + 1)
        cu = col & M32
        nz = (hf((cu.astype(np.uint64) ^ lb32(int(frame) & M32)), sd + 2) - 0.5) * P['Litenoise']
        L = P['Litelength'] * jit
        S = _bil(np.asarray(prev, dtype=np.float64), pcx - (dx + px * nz) * L, pcy - (dy + py * nz) * L) * P['Litedecay']
    seed = np.concatenate([img[..., :3], np.ones((H, W, 1))], -1)
    return np.where(m[..., None], seed, S)


def lite_fx(img, T, P):
    c = np.asarray(img, dtype=np.float64)
    b, g = int(P['Liteblend']), P['Litegain']
    if b == 0:
        o = c[..., :3] * (1 - T[..., 3:4]) + T[..., :3] * g
    elif b == 1:
        o = np.maximum(c[..., :3], T[..., :3] * g)
    else:
        o = c[..., :3] + T[..., :3] * g
    out = c.copy()
    out[..., :3] = c[..., :3] + (o - c[..., :3]) * P['Amount']
    return out


def lite_steady(img, P, iters=120, mask=None):
    """Trail after `iters` cooks of a still picture from a fresh start (noise frame 0)."""
    T = lite_step(img, None, P, fresh=True, mask=mask)
    for _ in range(iters):
        T = lite_step(img, T, P, mask=mask)
    return T


def reference(img, pars=None, t=None, iters=120, mask=None):
    """Steady-state Lite out1 for a still picture (Litenoise must be 0 for a still result)."""
    P = pars_of(pars)
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0:
        return img.copy()
    return lite_fx(img, lite_steady(img, P, iters, mask), P)


def compare(td_out, ref, tol=2.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
