# fx_glitch_smear_logic - numpy mirror of the FX_glitch 'smear' mode `strips` (TC-25 pixel strips by coordinate remap,
# builders/fx_glitch_smear.py). Pure numpy (no TD names): exec-able inside TD for live parity. Arrays are in TD's TOP
# readback layout: [y, x, rgba], row 0 = the BOTTOM row, 0..1. Same uint32 hash as the shader (lowbias32). The other
# smear modes are checked live by their own numbers (docs/builds/fx_glitch.md), not mirrored here. ASCII only.
import math

import numpy as np

MODES = ['smearmax', 'smearmin', 'stretch', 'feedback', 'strips', 'radial', 'maskedge']
DEFAULTS = {'Amount': 1.0, 'Mode': 0, 'Angle': 0.0, 'Length': 160.0, 'Threshold': 0.5, 'Decay': 0.7, 'Wobble': 0.3,
            'Bandpos': 0.45, 'Bandwidth': 0.08, 'Seed': 1, 'Stripwidth': 8.0, 'Stripjitter': 1.0, 'Snap': 1.0,
            'Curve': 0.0, 'Curvefreq': 1.0, 'Speed': 0.0, 'Density': 1.0, 'Centerx': 0.5,
            'Centery': 0.5}
M32 = 0xffffffff
LUMA = np.array([0.2126, 0.7152, 0.0722])


def pars_of(over=None):
    d = dict(DEFAULTS)
    d.update(over or {})
    if isinstance(d['Mode'], str):
        d['Mode'] = MODES.index(d['Mode'])
    return d


def lb32(x):
    x = np.asarray(x, dtype=np.uint64) & M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def hk(k, salt, seed):
    """GLSL hk(int k, uint salt): per-strip hash in [0, 1). k may be negative (two's complement, as uint(int))."""
    ku = np.asarray(k).astype(np.int64) & M32
    inner = lb32((int(salt) + int(seed) * 7919) & M32)
    return (lb32(((ku.astype(np.uint64) * 0x9e3779b9) & M32) ^ inner) >> 8).astype(np.float64) / 16777216.0


def strips_geometry(W, H, P, t=0.0):
    """Per pixel (row 0 = bottom): strip index k, active mask, sample pixel (qx, qy) and along fraction f.
    Mirrors the shader's mode 4 maths in float64 (the GPU is float32: rare floor-boundary pixels differ)."""
    a = math.radians(P['Angle'])
    dx, dy = math.sin(a), -math.cos(a)                    # 0 = down (TD y up), as the other smear modes
    px, py = dy * -1.0, dx                                # perp = (-dir.y, dir.x)
    y, x = np.mgrid[0:H, 0:W]
    pcx, pcy = x + 0.5, y + 0.5
    cx, cy = pcx - 0.5 * W, pcy - 0.5 * H
    s = cx * dx + cy * dy
    tt = cx * px + cy * py
    E = abs(dx) * W + abs(dy) * H
    tb = tt + P['Curve'] * np.sin(6.2831853 * P['Curvefreq'] * s / E)
    Wd = max(P['Stripwidth'], 1.0)
    k = np.floor(tb / Wd)
    seed = int(P['Seed'])
    h1, h2, h3 = hk(k, 1, seed), hk(k, 2, seed), hk(k, 3, seed)
    active = h3 < P['Density']
    Lk = np.maximum(P['Length'] * (1.0 - P['Wobble'] * h1), 1.0)
    ph = P['Speed'] * t + h2 * Lk * P['Stripjitter']
    s0 = np.floor((s + ph) / Lk) * Lk - ph
    tc = (k + 0.5) * Wd
    ad = s0 + 0.5 - s
    sn = P['Snap'] * (tc - tb)
    qx = pcx + dx * ad + px * sn
    qy = pcy + dy * ad + py * sn
    f = (s - s0) / Lk
    return k, active, qx, qy, f


def tex0(img, qx, qy):
    """texture() at pixel-space points, bilinear, inputextenduv zero (smear's fx default)."""
    H, W = img.shape[:2]
    x, y = np.asarray(qx, dtype=np.float64) - 0.5, np.asarray(qy, dtype=np.float64) - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    x0, y0 = x0.astype(np.int64), y0.astype(np.int64)

    def T(ix, iy):
        ok = (ix >= 0) & (iy >= 0) & (ix < W) & (iy < H)
        return np.where(ok[..., None], img[np.clip(iy, 0, H - 1), np.clip(ix, 0, W - 1)], 0.0)
    return (T(x0, y0) * (1 - fx) + T(x0 + 1, y0) * fx) * (1 - fy) + (T(x0, y0 + 1) * (1 - fx) + T(x0 + 1, y0 + 1) * fx) * fy


def radial(img, P):
    H, W = img.shape[:2]
    y, x = np.mgrid[0:H, 0:W]
    pcx, pcy = x + 0.5, y + 0.5
    cx, cy = P['Centerx'] * W, P['Centery'] * H
    vx, vy = pcx - cx, pcy - cy
    r = np.hypot(vx, vy)
    R = 0.5 * math.hypot(W, H)
    ang = np.arctan2(vy, vx)
    wr = 1.0 - P['Wobble'] * hk(np.floor((ang + 3.14159265) / 6.2831853 * 256.0), 5, int(P['Seed']))
    r0 = P['Bandpos'] * R
    r1 = r0 + P['Bandwidth'] * R * wr
    rc = np.clip(r, r0, r1)
    rs = np.maximum(r, 1e-12)
    o = tex0(img, cx + vx / rs * rc, cy + vy / rs * rc)
    return np.where((r > 1e-4)[..., None], o, img)


def maskedge(img, mask, P):
    """Wobble 0 only (the shader's per-column wobble is its sin-hash)."""
    H, W = img.shape[:2]
    y, x = np.mgrid[0:H, 0:W]
    pcx, pcy = x + 0.5, y + 0.5
    a = math.radians(P['Angle'])
    dx, dy = math.sin(a), -math.cos(a)
    lum = lambda c: (c[..., :3] * LUMA).sum(-1)  # noqa: E731
    out = img.copy()
    todo = lum(tex0(mask, pcx, pcy)) <= P['Threshold']
    L = P['Length']
    N = int(min(max(math.ceil(L / 4.0), 1.0), 24.0))
    stp = L / N
    for k in range(1, N + 1):
        qx, qy = pcx - dx * stp * k, pcy - dy * stp * k
        hit = todo & (lum(tex0(mask, qx, qy)) > P['Threshold'])
        s = tex0(img, qx, qy)
        f = (k / N) * (1.0 - P['Decay'])
        out = np.where(hit[..., None], s + (img - s) * f, out)
        todo = todo & ~hit
    return out


def reference(img, pars=None, t=0.0, mask=None):
    """out1 of the smear module in mode `strips` (or Amount 0) for img [y, x, 4] (row 0 = bottom) -> float64."""
    P = pars_of(pars)
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0.0:
        return img.copy()
    if int(P['Mode']) == 5:
        return img + (radial(img, P) - img) * P['Amount']
    if int(P['Mode']) == 6:
        return img + (maskedge(img, img if mask is None else np.asarray(mask, dtype=np.float64), P) - img) * P['Amount']
    if int(P['Mode']) != 4:
        raise NotImplementedError('modes strips / radial / maskedge are mirrored')
    H, W = img.shape[:2]
    _k, active, qx, qy, f = strips_geometry(W, H, P, t)
    xi = np.clip(np.floor(qx).astype(np.int64), 0, W - 1)
    yi = np.clip(np.floor(qy).astype(np.int64), 0, H - 1)
    sm = img[yi, xi]
    gate = active & ((sm[..., :3] * LUMA).sum(-1) >= P['Threshold'])
    o = sm + (img - sm) * ((1.0 - P['Decay']) * f)[..., None]
    o = np.where(gate[..., None], o, img)
    return img + (o - img) * P['Amount']


def compare(td_out, ref, tol=2.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
