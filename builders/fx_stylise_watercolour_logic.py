"""fx_stylise_watercolour_logic - numpy mirror of FX_stylise 'watercolour' (builders/fx_stylise_watercolour.py).
Pure: no td. wash(img, P) == the wash pass; look(img, wash, P, pal=None) == the look pass. ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402

TAPS = 16


def div(P):
    return {0: 1, 1: 2, 2: 4}[P['Res']]


def wash(img, P):
    img = np.asarray(img, np.float32)
    H, W = img.shape[:2]
    D = div(P)
    JH, JW = int(math.ceil(H / D)), int(math.ceil(W / D))
    jx, jy = X.grid(JH, JW)
    pcx, pcy = (jx + 0.5) * D, (jy + 0.5) * D

    def S(x, y):
        return X.bilinear(img, x, y)
    gx = X.luma(S(pcx + D, pcy)) - X.luma(S(pcx - D, pcy))
    gy = X.luma(S(pcx, pcy + D)) - X.luma(S(pcx, pcy - D))
    nx, ny = X.vnoise2(pcx / max(P['Wobblescale'], 1.0), pcy / max(P['Wobblescale'], 1.0), int(P['Seed']))
    nx, ny = 2 * nx - 1, 2 * ny - 1
    gl = gx * gx + gy * gy
    ok = gl > 1e-8
    sq = np.sqrt(np.where(ok, gl, 1))
    dx, dy = np.where(ok, gx / sq, 1.0), np.where(ok, gy / sq, 0.0)
    if P['Flow'] == 1:
        dx, dy = -dy, dx
    dx, dy = dx + P['Wobble'] * nx, dy + P['Wobble'] * ny
    dl = dx * dx + dy * dy
    ok = dl > 1e-8
    sq = np.sqrt(np.where(ok, dl, 1))
    dx, dy = np.where(ok, dx / sq, 1.0), np.where(ok, dy / sq, 0.0)
    N = min(max(int(round(P['Taps'])), 2), TAPS)
    acc = np.zeros((JH, JW, img.shape[2]))
    ws = 0.0
    for k in range(N):
        f = k / (N - 1) - 0.5
        w = 1 - abs(f)
        acc += w * S(pcx + dx * 2 * f * P['Spread'], pcy + dy * 2 * f * P['Spread'])
        ws += w
    return acc / ws


def look(img, wa, P, pal=None):
    c = np.asarray(img, np.float32).astype(np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    H, W = c.shape[:2]
    JH, JW = wa.shape[:2]
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5

    def Wq(x, y):
        return X.bilinear(wa, x * JW / W, y * JH / H)
    w = Wq(pcx, pcy)
    gx = X.luma(Wq(pcx + 1.5, pcy)) - X.luma(Wq(pcx - 1.5, pcy))
    gy = X.luma(Wq(pcx, pcy + 1.5)) - X.luma(Wq(pcx, pcy - 1.5))
    rim = np.clip(np.hypot(gx, gy) * P['Edgedark'] * 4, 0, 1)
    L = X.luma(w).astype(np.float64)
    if P['Colsrc'] == 1:
        col = pal(L) if pal is not None else np.repeat(L[..., None], 3, -1)
    else:
        col = L[..., None] + (w[..., :3] - L[..., None]) * P['Saturation']
    paper = np.array([P['Paperr'], P['Paperg'], P['Paperb']])
    sd = int(P['Seed'])
    pg = 1 + P['Pigment'] * (2 * X.vnoise(pcx / max(P['Pigmentscale'], 1), pcy / max(P['Pigmentscale'], 1), sd + 3) - 1)
    gs = P['Grainscale']
    gr = 0.6 * X.vnoise(pcx / max(gs, 1), pcy / max(gs, 1), sd + 11) + \
        0.4 * X.vnoise(pcx / max(0.5 * gs, 0.5), pcy / max(0.5 * gs, 0.5), sd + 17)
    dens = pg * (1 + P['Granulation'] * (2 * gr - 1)) * (1 + 0.6 * rim)
    o = paper - (paper - col) * dens[..., None]
    t = X.smoothstep(P['Whitethr'], P['Whitethr'] + 0.1, L)[..., None]
    o = o + (paper - o) * t
    out = np.concatenate([o, c[..., 3:]], -1)
    return c + (out - c) * P['Amount']
