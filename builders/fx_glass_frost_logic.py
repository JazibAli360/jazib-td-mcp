"""fx_glass_frost_logic - numpy mirror of FX_glass 'frost' (builders/fx_glass_frost.py). Pure: no td.
look(img, bd, P, tick=0) == fx. ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402

M32 = 0xffffffff


def look(img, bd, P, tick=0):
    c = np.asarray(img, np.float32).astype(np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    H, W = c.shape[:2]
    BH, BW = bd.shape[:2]
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5

    def S(qx, qy, mix):
        a = X.bilinear(c, qx, qy)[..., :3]
        b = X.bilinear(bd, qx * BW / W, qy * BH / H)[..., :3]
        mix = np.asarray(mix, np.float64)
        return a + (b - a) * (mix[..., None] if mix.ndim else mix)
    sd = (int(P['Seed']) * 7919 + int(tick) * 2654435761) & M32
    mode = P['Mode']
    if mode == 0:
        hx = X.hsh(px.astype(np.int64), py.astype(np.int64), sd) - 0.5
        hy = X.hsh(px.astype(np.int64) + 4099, py.astype(np.int64) + 7, sd) - 0.5
        col = S(pcx + 2 * hx * P['Radius'], pcy + 2 * hy * P['Radius'], P['Blurmix'])
    elif mode == 1:
        a = math.radians(P['Angle'])
        tx, ty = math.cos(a), math.sin(a)
        nx, ny = -ty, tx
        w = max(P['Width'], 1.0)
        v = (pcx * nx + pcy * ny) / w
        s = v - np.floor(v) - 0.5
        k = s * w * (P['Mag'] - 1)
        e = np.abs(2 * s)
        col = S(pcx + nx * k, pcy + ny * k, P['Blurmix'] * e * e)
        col = col + (P['Rimlight'] * e ** 6)[..., None]
    else:
        cs = max(P['Cell'], 2.0)
        if P['Shape'] == 0:
            cx, cy = (np.floor(pcx / cs) + 0.5) * cs, (np.floor(pcy / cs) + 0.5) * cs
            lx, ly = (pcx - cx) / (0.5 * cs), (pcy - cy) / (0.5 * cs)
            rr = np.maximum(np.abs(lx), np.abs(ly))
        else:
            rx, ry = cs, 1.7320508 * cs
            a1x, a1y = (np.floor(pcx / rx) + 0.5) * rx, (np.floor(pcy / ry) + 0.5) * ry
            a2x = (np.floor((pcx - 0.5 * rx) / rx) + 0.5) * rx + 0.5 * rx
            a2y = (np.floor((pcy - 0.5 * ry) / ry) + 0.5) * ry + 0.5 * ry
            n1 = (pcx - a1x) ** 2 + (pcy - a1y) ** 2
            n2 = (pcx - a2x) ** 2 + (pcy - a2y) ** 2
            cx, cy = np.where(n1 < n2, a1x, a2x), np.where(n1 < n2, a1y, a2y)
            lx, ly = (pcx - cx) / (0.5 * cs), (pcy - cy) / (0.5 * cs)
            ax, ay = np.abs(lx), np.abs(ly)
            rr = np.maximum(ax * 0.5 + ay * 0.8660254, ax)
        col = S(cx + (pcx - cx) * P['Mag'], cy + (pcy - cy) * P['Mag'], P['Blurmix'])
        col = col * (1 - P['Vignette'] * rr * rr * 0.5)[..., None]
        g0 = 1 - P['Gap'] * 2
        col = col * (1 - X.smoothstep(g0 - 0.03, g0, rr))[..., None]
        col = col + (P['Rimlight'] * np.clip(rr, 0, 1) ** 8)[..., None]
    o = np.concatenate([col, c[..., 3:]], -1)
    return c + (o - c) * P['Amount']
