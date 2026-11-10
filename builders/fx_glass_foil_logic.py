"""fx_glass_foil_logic - numpy mirror of FX_glass 'foil' (builders/fx_glass_foil.py). Pure: no td.
thinfilm(d, cost, ior, phase) == the interference colour; look(img, P, phase=0, ntime=0, pal=None) == fx. ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402

LAMBDA = np.array([650.0, 532.0, 450.0])


def thinfilm(d, cost, ior, phase):
    ph = 4 * math.pi * ior * np.asarray(d)[..., None] * np.asarray(cost)[..., None] / LAMBDA + phase
    return 0.5 + 0.5 * np.cos(ph)


def blendf(a, b, m):
    if m == 1:
        return a * b
    if m == 2:
        return 1 - (1 - a) * (1 - b)
    if m == 3:
        return np.where(a >= 0.5, 1 - 2 * (1 - a) * (1 - b), 2 * a * b)
    if m == 4:
        return a + b
    return b


def look(img, P, phase=0.0, ntime=0.0, pal=None):
    c = np.asarray(img, np.float32).astype(np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    H, W = c.shape[:2]
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5
    s = max(P['Smooth'], 0.5)

    def Lt(x, y):
        return X.luma(X.bilinear(np.asarray(img, np.float32), x, y)).astype(np.float64)
    l0, lxp, lxm = Lt(pcx, pcy), Lt(pcx + s, pcy), Lt(pcx - s, pcy)
    lyp, lym = Lt(pcx, pcy + s), Lt(pcx, pcy - s)
    lb = (l0 + lxp + lxm + lyp + lym) * 0.2
    gx, gy = (lxp - lxm) / (2 * s), (lyp - lym) / (2 * s)
    ns = max(P['Noisescale'], 1.0)
    nz = X.vnoise(pcx / ns + ntime, pcy / ns + 0.71 * ntime, int(P['Seed']))
    d = P['Base'] + P['Range'] * (lb + P['Noise'] * (nz - 0.5))
    nx, ny, nzz = -gx * P['Tilt'] * s, -gy * P['Tilt'] * s, np.ones_like(gx)
    nl = np.sqrt(nx * nx + ny * ny + nzz * nzz)
    nzz = nzz / nl
    sint = np.sqrt(np.maximum(1 - nzz * nzz, 0)) / max(P['Filmior'], 1.0)
    cost = np.sqrt(np.maximum(1 - sint * sint, 0))
    if P['Mode'] == 0:
        f = thinfilm(d, cost, P['Filmior'], phase)
    elif P['Mode'] == 1:
        t = d * cost / 600.0 + phase / (2 * math.pi)
        f = 0.5 + 0.5 * np.cos(2 * math.pi * (t[..., None] + np.array([0.0, 0.33, 0.67])))
    else:
        t = d * cost / max(P['Base'] + P['Range'], 1.0) + phase / (2 * math.pi)
        f = pal(t) if pal is not None else np.repeat(t[..., None], 3, -1)
    fl = f @ X.LUMA.astype(np.float64)
    f = fl[..., None] + (f - fl[..., None]) * P['Saturation']
    cl = X.luma(c).astype(np.float64)
    f = f + (f * (cl / np.maximum(fl, 1e-3))[..., None] - f) * P['Keepluma']
    o = blendf(c[..., :3], f, P['Blend'])
    out = np.concatenate([o, c[..., 3:]], -1)
    return c + (out - c) * P['Amount']
