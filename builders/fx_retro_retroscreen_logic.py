# fx_retro_retroscreen_logic - numpy mirror of FX_retro 'retroscreen' (builders/fx_retro_retroscreen.py). Arrays:
# [y, x, rgba], row 0 = BOTTOM, straight alpha-1 pictures. t = absTime.seconds, frame parity, shake epoch given.
import math

import numpy as np

M32 = 0xffffffff
DEFAULTS = {'Amount': 1.0, 'Aspect': 1, 'Fill': 0, 'Margin': 0.06, 'Pixelsize': 4.0, 'Pixelaspect': 1.0,
            'Borderr': 0.42, 'Borderg': 0.35, 'Borderb': 0.8, 'Seed': 1, 'Bars': 0, 'Barheight': 40.0,
            'Barspeed': 0.4, 'Barhue': 0.0, 'Barspread': 0.08, 'Barzone': 0, 'Flicker': 0.0, 'Shake': 0.0,
            'Shakerate': 20.0, 'Fade': 0.0}
LUMA = np.array([0.2126, 0.7152, 0.0722])


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


def hs(a, b):
    return float((lb32(((int(a) * 0x9e3779b9) & M32) ^ int(lb32(b & M32))) >> 8)) / 16777216.0


def hue(h):
    h = np.asarray(h, dtype=np.float64)
    v = np.abs(((h[..., None] + np.array([0.0, 2.0 / 3.0, 1.0 / 3.0])) % 1.0) * 6.0 - 3.0) - 1.0
    return np.clip(v, 0.0, 1.0)


def render(img, P, t=0.0, parity=0, epoch=0):
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0:
        return img.copy()
    H, W = img.shape[:2]
    asp = int(P['Aspect'])
    ar = [W / H, 4 / 3, 16 / 9, 1.0, 0.75][asp]
    ax, ay = W * (1 - 2 * P['Margin']), H * (1 - 2 * P['Margin'])
    sx, sy = (ay * ar, ay) if ax / ay > ar else (ax, ax / ar)
    sx, sy = math.floor(sx + 0.5), math.floor(sy + 0.5)
    sd = int(P['Seed']) * 7919
    shx = (hs(epoch, sd + 1) - 0.5) * 2 * P['Shake']
    shy = (hs(epoch, sd + 2) - 0.5) * 2 * P['Shake']
    ox, oy = math.floor(0.5 * (W - sx) + shx + 0.5), math.floor(0.5 * (H - sy) + shy + 0.5)
    y, x = np.mgrid[0:H, 0:W]
    qx, qy = x + 0.5 - ox, y + 0.5 - oy
    inside = (qx >= 0) & (qy >= 0) & (qx < sx) & (qy < sy)
    psy = max(1, int(round(P['Pixelsize'])))
    psx = max(1, int(round(P['Pixelsize'] * P['Pixelaspect'])))
    vcx, vcy = (np.floor(qx / psx) + 0.5) * psx, (np.floor(qy / psy) + 0.5) * psy
    k = min(W / sx, H / sy) if int(P['Fill']) == 1 else max(W / sx, H / sy)
    srcx, srcy = 0.5 * W + (vcx - 0.5 * sx) * k, 0.5 * H + (vcy - 0.5 * sy) * k
    ok = inside & (srcx >= 0) & (srcy >= 0) & (srcx < W) & (srcy < H)
    s = img[np.clip(np.floor(srcy).astype(np.int64), 0, H - 1), np.clip(np.floor(srcx).astype(np.int64), 0, W - 1)]
    pic = np.where(ok[..., None], s[..., :3], 0.0)
    col = np.where(inside[..., None], pic, np.array([P['Borderr'], P['Borderg'], P['Borderb']]))
    lum = (pic * LUMA).sum(-1)
    line = np.floor(qy / psy).astype(np.int64)
    if P['Flicker'] > 0:
        col = np.where((inside & (((line + int(parity)) & 1) == 1))[..., None], col * (1 - P['Flicker']), col)
    nb = int(P['Bars'] + 0.5)
    if nb > 0:
        bar = np.zeros((H, W))
        bc = np.zeros((H, W, 3))
        ph = P['Barspeed'] * t
        for b in range(min(nb, 16)):
            cy = (0.5 + 0.45 * math.sin(6.2831853 * (ph + b * 0.61803))) * H
            d = np.abs(y + 0.5 - cy) / max(P['Barheight'] * 0.5, 1.0)
            w = np.where(d < 1.0, 0.5 + 0.5 * np.cos(math.pi * d), 0.0)
            better = (d < 1.0) & (w > bar)
            bc = np.where(better[..., None], hue(np.full((H, W), P['Barhue'] + P['Barspread'] * b)) * w[..., None], bc)
            bar = np.where(better, w, bar)
        z = int(P['Barzone'])
        if z == 0:
            col = np.where((~inside)[..., None], col + (bc - col) * bar[..., None], col)
        elif z == 1:
            m = (~inside) | (lum < 0.12)
            f = bar * np.where(inside, 1.0 - lum / 0.12, 1.0)
            col = np.where(m[..., None], col + (bc - col) * f[..., None], col)
        else:
            col = col + bc
    fd = P['Fade']
    col = col + (1.0 - col) * fd if fd >= 0 else col * (1.0 + fd)
    src = img[..., :3]
    fin = src + (col - src) * P['Amount']
    a = img[..., 3:4] + (1.0 - img[..., 3:4]) * P['Amount']
    return np.concatenate([fin * a, a], -1)


def reference(img, pars=None, t=0.0, parity=0, epoch=0):
    return render(img, pars_of(pars), t, parity, epoch)


def compare(td_out, ref, tol=2.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
