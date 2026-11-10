"""fx_glass_rain_logic - numpy mirror of FX_glass 'rain' (builders/fx_glass_rain.py). Pure: no td.
field(W, H, P, t) == the drop layers (offset px, clear, rim); look(img, bd, P, t) == fx. ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402

M32 = 0xffffffff


def _ss(a, b, x):
    return X.smoothstep(a, b, x)


def _layer(pcx, pcy, size, sd, P, t, off, clear, rim):
    csx, csy = size, 2.0 * size
    qx, qy = pcx / csx, pcy / csy
    ix, iy = np.floor(qx).astype(np.int64), np.floor(qy).astype(np.int64)
    fx_, fy_ = qx - ix - 0.5, qy - iy - 0.5
    n = X.hsh(ix, iy, sd)
    has = n < P['Rain']
    x = (X.hsh(ix + 3, iy + 1, sd) - 0.5) * 0.6
    ph = t * (0.6 + 0.8 * X.hsh(ix + 5, iy + 7, sd)) + n * 7.0
    ph = ph - np.floor(ph)
    sl = ph + 0.05 * np.sin(18.849556 * ph)
    y = 0.42 - 0.84 * sl
    r = size * 0.16 * (0.7 + 0.6 * X.hsh(ix + 9, iy + 2, sd))
    dpx, dpy = (fx_ - x) * csx, (fy_ - y) * csy
    d = np.hypot(dpx, dpy * 0.85) - r
    m = (1 - _ss(-1.0, 1.0, d)) * has
    k = 1.0 + P['Refract']
    off[0] += -k * dpx * m
    off[1] += -k * dpy * m
    clear[:] = np.maximum(clear, m)
    rim += m * _ss(-0.35 * r, 0.0, d)
    tw = r * 0.45
    dx = np.abs((fx_ - x) * csx)
    above = (fy_ - y) * csy
    tm = (1 - _ss(0.5 * tw, tw, dx)) * (above >= 0) * (1 - _ss(0.0, 0.84 * csy, above)) * has
    clear[:] = np.maximum(clear, tm * P['Trails'])
    per = np.maximum(tw * 1.6, 1.0)
    ty = above / per - np.floor(above / per)
    tpx, tpy = (fx_ - x) * csx, (ty - 0.5) * tw * 1.6
    td = np.hypot(tpx, tpy) - tw * 0.35
    tmk = (1 - _ss(-1.0, 1.0, td)) * tm * P['Trails']
    off[0] += -k * tpx * tmk
    off[1] += -k * tpy * tmk
    clear[:] = np.maximum(clear, tmk)
    sc = size * 0.32
    sqx, sqy = pcx / sc, pcy / sc
    sx, sy = np.floor(sqx).astype(np.int64), np.floor(sqy).astype(np.int64)
    sn = X.hsh(sx, sy, (sd + 17) & M32)
    shas = sn < P['Static']
    sfx = (sqx - sx - 0.5 - (X.hsh(sx + 1, sy + 4, sd) - 0.5) * 0.5) * sc
    sfy = (sqy - sy - 0.5 - (X.hsh(sx + 6, sy + 2, sd) - 0.5) * 0.5) * sc
    life = t * 0.2 + sn * 13.0
    life = life - np.floor(life)
    fade = _ss(0.0, 0.1, life) * (1 - _ss(0.7, 1.0, life))
    sr = sc * 0.18 * (0.5 + X.hsh(sx + 2, sy + 9, sd)) * fade
    sdd = np.hypot(sfx, sfy) - sr
    sm = (1 - _ss(-1.0, 1.0, sdd)) * (sr >= 0.5) * shas
    off[0] += -k * sfx * sm
    off[1] += -k * sfy * sm
    clear[:] = np.maximum(clear, sm)
    rim += sm * _ss(-0.35 * sr, 0.0, sdd)


def field(W, H, P, t=0.0):
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5
    off = [np.zeros((H, W)), np.zeros((H, W))]
    clear = np.zeros((H, W))
    rim = np.zeros((H, W))
    L = min(max(int(round(P['Layers'])), 1), 3)
    sd = (int(P['Seed']) * 7919) & M32
    for k in range(L):
        sz = P['Size'] * (1.0, 0.6, 0.4)[k]
        _layer(pcx, pcy, sz, (sd + k * 101) & M32, P, t, off, clear, rim)
    return off, clear, rim


def look(img, bd, P, t=0.0):
    c = np.asarray(img, np.float32).astype(np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    H, W = c.shape[:2]
    BH, BW = bd.shape[:2]
    px, py = X.grid(H, W)
    off, clear, rim = field(W, H, P, t)
    qx, qy = px + 0.5 + off[0], py + 0.5 + off[1]
    sharp = X.bilinear(c, qx, qy)[..., :3]
    fog = X.bilinear(bd, qx * BW / W, qy * BH / H)[..., :3]
    k = np.maximum(clear, 1 - P['Fog'])[..., None]
    col = fog + (sharp - fog) * k
    col = col * (1 - P['Rimdark'] * np.clip(rim, 0, 1))[..., None]
    tint = np.array([P['Tintr'], P['Tintg'], P['Tintb']])
    col = col + (col * tint - col) * P['Tintamt']
    o = np.concatenate([col, c[..., 3:]], -1)
    return c + (o - c) * P['Amount']
