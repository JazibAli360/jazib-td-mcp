"""fx_glass_floor_logic - numpy mirror of FX_glass 'floor' (builders/fx_glass_floor.py). Pure: no td.
look(img, bd, P, t=0, pal_step=None) == fx (t = Ripplespeed x seconds). ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402


def _uv_sample(img, u, v):
    H, W = img.shape[:2]
    return X.bilinear(img, u * W, v * H)


def look(img, bd, P, t=0.0, pal_step=None):
    c = np.asarray(img, np.float32).astype(np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    H, W = c.shape[:2]
    px, py = X.grid(H, W)
    u, v = (px + 0.5) / W, (py + 0.5) / H
    h = min(max(P['Horizon'], 0.0), 0.999)
    fit = P['Layout'] == 0
    above = v >= h
    top = _uv_sample(c, u, (v - h) / (1 - h))[..., :3] if fit else c[..., :3]
    dy = h - v
    sy = h + dy * P['Stretch']
    nz = X.vnoise(u * 7.0, dy * 9.0, int(P['Seed']))
    rx = P['Ripple'] * np.sin(2 * math.pi * (P['Ripplefreq'] * dy * H) * (1 + 0.5 * nz) - t) / W
    su = u + rx
    sv = (sy - h) / (1 - h) if fit else sy
    out_ = (sv <= 1.0).astype(np.float64)
    sv = np.minimum(sv, 1.0)
    bl = np.clip(dy / max(P['Blurdist'], 1e-3), 0, 1)[..., None]
    a = _uv_sample(c, su, sv)[..., :3]
    b = _uv_sample(bd, su, sv)[..., :3]
    r = a + (b - a) * bl
    fade = np.clip(1 - dy / max(P['Fade'], 1e-3), 0, 1) ** P['Fadepow']
    fr = 1 + P['Fresnel'] * (1 - np.clip(dy / max(P['Fade'], 1e-3), 0, 1))
    floorc = np.broadcast_to(np.array([P['Floorr'], P['Floorg'], P['Floorb']]), (H, W, 3)).copy()
    if P['Tiles'] > 0:
        z = 1.0 / (dy * P['Persp'] + 0.02)
        xw = (u - 0.5) * z
        fx_ = xw * P['Tiles'] * 0.1 + 0.5
        gx = np.abs(fx_ - np.floor(fx_) - 0.5)
        fz = z * 0.25
        gz = np.abs(fz - np.floor(fz) - 0.5)
        lw = P['Tilewidth']
        line = np.maximum(1 - X.smoothstep(0.0, lw, gx), 1 - X.smoothstep(0.0, lw * 2, gz * dy * P['Persp'] * 4))
        if P['Tilesrc'] == 1 and pal_step is not None:
            lc = pal_step(np.floor(z * 0.25))
        else:
            lc = np.ones((H, W, 3))
        floorc = floorc + lc * (line * P['Tileglow'] * np.clip(dy * 8, 0, 1))[..., None]
    bottom = floorc + r * (P['Reflect'] * fade * fr * out_)[..., None]
    rgb = np.where(above[..., None], top, bottom)
    alpha = np.where(above, c[..., 3], 1.0)[..., None]
    o = np.concatenate([rgb, alpha], -1)
    return c + (o - c) * P['Amount']
