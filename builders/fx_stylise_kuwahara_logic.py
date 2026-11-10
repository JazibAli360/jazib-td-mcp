"""fx_stylise_kuwahara_logic - numpy mirror of FX_stylise 'kuwahara' (builders/fx_stylise_kuwahara.py). Pure: no td.
tensor(img, D) == tens; tblur(t) == tblur; kuwahara(img, tb, P) == kuw; up(img, kw, amount) == fx. ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402

RMAX = 12


def div(P):
    return {0: 1, 1: 2, 2: 4}[P['Res']]


def tensor(img, D):
    img = np.asarray(img, np.float32)
    H, W = img.shape[:2]
    JH, JW = int(math.ceil(H / D)), int(math.ceil(W / D))
    jx, jy = X.grid(JH, JW)
    pcx, pcy = (jx + 0.5) * D, (jy + 0.5) * D

    def S(dx, dy):
        return X.bilinear(img, pcx + D * dx, pcy + D * dy)[..., :3].astype(np.float64)
    tl, tc, tr = S(-1, 1), S(0, 1), S(1, 1)
    ml, mr = S(-1, 0), S(1, 0)
    bl, bc, br = S(-1, -1), S(0, -1), S(1, -1)
    sx = ((tr + 2 * mr + br) - (tl + 2 * ml + bl)) * 0.25
    sy = ((tl + 2 * tc + tr) - (bl + 2 * bc + br)) * 0.25
    return np.stack([(sx * sx).sum(-1), (sx * sy).sum(-1), (sy * sy).sum(-1), np.ones((JH, JW))], -1)


def tblur(t):
    H, W = t.shape[:2]
    acc = np.zeros_like(t)
    ws = 0.0
    for j in range(-2, 3):
        for i in range(-2, 3):
            w = math.exp(-(i * i + j * j) / 4.5)
            ys = np.clip(np.arange(H) + j, 0, H - 1)
            xs = np.clip(np.arange(W) + i, 0, W - 1)
            acc += w * t[np.ix_(ys, xs)]
            ws += w
    return acc / ws


def kuwahara(img, tb, P, win=None):
    """win = (x0, y0, w, h) in tensor texels: only that window (live parity on a crop keeps TD responsive)."""
    img = np.asarray(img, np.float32)
    H, W = img.shape[:2]
    D = div(P)
    if win is None:
        win = (0, 0, tb.shape[1], tb.shape[0])
    x0, y0, ww, wh = win
    tb = tb[y0:y0 + wh, x0:x0 + ww]
    JH, JW = tb.shape[:2]
    jx, jy = X.grid(JH, JW)
    jx, jy = jx + x0, jy + y0
    pcx, pcy = (jx + 0.5) * D, (jy + 0.5) * D
    E, F, G = tb[..., 0], tb[..., 1], tb[..., 2]
    rt = np.sqrt(np.maximum((E - G) ** 2 + 4 * F * F, 0))
    l1, l2 = 0.5 * (E + G + rt), 0.5 * (E + G - rt)
    vx, vy = l1 - E, -F
    vl = np.sqrt(vx * vx + vy * vy)
    ok = vl > 0
    dx, dy = np.where(ok, vx / np.where(ok, vl, 1), 0.0), np.where(ok, vy / np.where(ok, vl, 1), 1.0)
    phi = -np.arctan2(dy, dx)
    A = np.where(l1 + l2 > 0, (l1 - l2) / np.where(l1 + l2 > 0, l1 + l2, 1), 0.0) * P['Anisotropy']
    r = float(int(round(P['Radius'])))
    al = P['Alpha']
    a = r * np.clip((al + A) / al, 0.1, 2.0)
    b = r * np.clip(al / (al + A), 0.1, 2.0)
    cp, sp = np.cos(phi), np.sin(phi)
    zeta = P['Zeta'] if P['Zeta'] > 0 else 2.0 / r
    zc = P['Zerocross']
    eta = (zeta + math.cos(zc)) / (math.sin(zc) ** 2)
    mxx = np.ceil(np.sqrt(a * a * cp * cp + b * b * sp * sp)).astype(int)
    mxy = np.ceil(np.sqrt(a * a * sp * sp + b * b * cp * cp)).astype(int)
    M = int(max(mxx.max(), mxy.max()))
    m = np.zeros((8, JH, JW, 4))
    s = np.zeros((8, JH, JW, 3))
    for y in range(-M, M + 1):
        for x in range(-M, M + 1):
            inb = (np.abs(x) <= mxx) & (np.abs(y) <= mxy)
            # w2 = SR (x, y): rotate by [[cp, -sp], [sp, cp]] (GLSL column-major mat2(cp, -sp, sp, cp)), then scale
            rx = cp * x + sp * y
            ry = -sp * x + cp * y
            w2x, w2y = rx * 0.5 / a, ry * 0.5 / b
            inside = inb & (w2x * w2x + w2y * w2y <= 0.25)
            if not inside.any():
                continue
            c = np.clip(X.bilinear(img, pcx + x * D, pcy + y * D)[..., :3].astype(np.float64), 0, 1)
            vxx, vyy = zeta - eta * w2x * w2x, zeta - eta * w2y * w2y
            w = [None] * 8
            w[0] = np.maximum(0, w2y + vxx) ** 2
            w[2] = np.maximum(0, -w2x + vyy) ** 2
            w[4] = np.maximum(0, -w2y + vxx) ** 2
            w[6] = np.maximum(0, w2x + vyy) ** 2
            ux, uy = 0.70710678 * (w2x - w2y), 0.70710678 * (w2x + w2y)
            vxx, vyy = zeta - eta * ux * ux, zeta - eta * uy * uy
            w[1] = np.maximum(0, uy + vxx) ** 2
            w[3] = np.maximum(0, -ux + vyy) ** 2
            w[5] = np.maximum(0, -uy + vxx) ** 2
            w[7] = np.maximum(0, ux + vyy) ** 2
            sm = sum(w)
            g = np.exp(-3.125 * (w2x * w2x + w2y * w2y)) / np.maximum(sm, 1e-8)
            g = np.where(inside, g, 0.0)
            for k in range(8):
                wk = w[k] * g
                m[k, ..., :3] += c * wk[..., None]
                m[k, ..., 3] += wk
                s[k] += c * c * wk[..., None]
    o = np.zeros((JH, JW, 4))
    for k in range(8):
        okk = m[k, ..., 3] > 0
        mw = np.where(okk, m[k, ..., 3], 1)[..., None]
        mu = m[k, ..., :3] / mw
        vr = np.abs(s[k] / mw - mu * mu)
        sg = vr.sum(-1)
        wk = np.where(okk, 1.0 / (1.0 + np.power(1000.0 * sg, 0.5 * P['Sharpness'])), 0.0)
        o[..., :3] += mu * wk[..., None]
        o[..., 3] += wk
    out = np.where(o[..., 3:] > 0, o[..., :3] / np.where(o[..., 3:] > 0, o[..., 3:], 1),
                   X.bilinear(img, pcx, pcy)[..., :3])
    return np.concatenate([out, np.ones((JH, JW, 1))], -1)


def up(img, kw, amount):
    c = np.asarray(img, np.float32).astype(np.float64)
    if amount <= 0:
        return c.copy()
    H, W = c.shape[:2]
    JH, JW = kw.shape[:2]
    px, py = X.grid(H, W)
    k = X.bilinear(kw, (px + 0.5) * JW / W, (py + 0.5) * JH / H)[..., :3]
    o = np.concatenate([k, c[..., 3:]], -1)
    return c + (o - c) * amount


def module(img, P):
    D = div(P)
    tb = tblur(tensor(img, D))
    kw = kuwahara(img, tb, P)
    return up(img, kw, P['Amount']), kw, tb
