# fx_retro_pixelart_logic - numpy mirror of FX_retro 'pixelart' (builders/fx_retro_pixelart.py) for Colour none /
# levels without dither (the palette path is the palette module's maths, checked there). Arrays: [y, x, rgba], row
# 0 = BOTTOM, 0..1, straight alpha 1 test pictures. Pure numpy, no TD names. ASCII only.
import math

import numpy as np

LUMA = np.array([0.2126, 0.7152, 0.0722])
DEFAULTS = {'Amount': 1.0, 'Pixelsize': 6.0, 'Pixelaspect': 1.0, 'Sampling': 0, 'Colour': 1, 'Levels': 6,
            'Dither': 0, 'Ditheramt': 1.0, 'Contrast': 1.1, 'Brightness': 0.0, 'Saturation': 1.2, 'Seed': 1,
            'Edgeby': 0, 'Edge': 0.12, 'Outline': 0.85, 'Outliner': 0.05, 'Outlineg': 0.03, 'Outlineb': 0.08,
            'Highlight': 0.35, 'Lightangle': 135.0, 'Grid': 0.0}


def pars_of(over=None):
    d = dict(DEFAULTS)
    d.update(over or {})
    return d


def vgrid(w, h, pixelsize, aspect=1.0):
    psy = max(1, int(round(pixelsize)))
    psx = max(1, int(round(pixelsize * aspect)))
    return psx, psy, (w + psx - 1) // psx, (h + psy - 1) // psy


def pre_adjust(c, contrast, bright, sat):
    c = (c - 0.5) * contrast + 0.5 + bright
    l = (c * LUMA).sum(-1, keepdims=True)
    return np.clip(l + (c - l) * sat, 0.0, 1.0)


def quant(v, levels, thr=0.5):
    L = max(levels, 2) - 1.0
    return np.clip(np.floor(v * L + thr) / L, 0.0, 1.0)


def low(img, P):
    img = np.asarray(img, dtype=np.float64)
    H, W = img.shape[:2]
    psx, psy, VW, VH = vgrid(W, H, P['Pixelsize'], P['Pixelaspect'])
    if int(P['Sampling']) == 0:
        ys = np.minimum(np.arange(VH) * psy + psy // 2, H - 1)
        xs = np.minimum(np.arange(VW) * psx + psx // 2, W - 1)
        s = img[ys][:, xs]
    else:
        s = np.zeros((VH, VW, 4))
        for vy in range(VH):
            for vx in range(VW):
                s[vy, vx] = img[vy * psy:min(H, vy * psy + psy), vx * psx:min(W, vx * psx + psx)].reshape(-1, 4).mean(0)
    c = pre_adjust(s[..., :3], P['Contrast'], P['Brightness'], P['Saturation'])
    if int(P['Colour']) == 1:
        c = quant(c, int(P['Levels']))
    elif int(P['Colour']) == 2:
        raise NotImplementedError('palette path: see the palette module checks')
    return np.concatenate([c, s[..., 3:4]], -1), (psx, psy)


def render(img, P):
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0:
        return img.copy()
    H, W = img.shape[:2]
    lo, (psx, psy) = low(img, P)
    VH, VW = lo.shape[:2]
    y, x = np.mgrid[0:H, 0:W]
    vx, vy = x // psx, y // psy

    def Lk(dx, dy):
        return lo[np.clip(vy + dy, 0, VH - 1), np.clip(vx + dx, 0, VW - 1)]
    c = Lk(0, 0)

    def brighter(n, cc):
        dl = (n[..., :3] * LUMA).sum(-1) - (cc[..., :3] * LUMA).sum(-1)
        if int(P['Edgeby']) == 0:
            return dl > P['Edge']
        return (dl > 0) & (np.linalg.norm(n[..., :3] - cc[..., :3], axis=-1) > P['Edge'])
    edge = brighter(Lk(1, 0), c) | brighter(Lk(-1, 0), c) | brighter(Lk(0, 1), c) | brighter(Lk(0, -1), c)
    o = c[..., :3].copy()
    oc = np.array([P['Outliner'], P['Outlineg'], P['Outlineb']])
    o = np.where(edge[..., None], o + (oc - o) * P['Outline'], o)
    if P['Highlight'] > 0:
        a = math.radians(P['Lightangle'])
        ldx, ldy = int(round(math.cos(a))), int(round(math.sin(a)))
        hl = (~edge) & brighter(c, Lk(-ldx, -ldy))
        o = np.where(hl[..., None], o + (1.0 - o) * P['Highlight'], o)
    if P['Grid'] > 0:
        qx, qy = x - vx * psx, y - vy * psy
        g = (qx == 0) | (qy == psy - 1)
        o = np.where(g[..., None], o * (1.0 - P['Grid']), o)
    sa = img[..., 3:4]
    srgb = np.where(sa > 1e-5, img[..., :3] / np.maximum(sa, 1e-12), img[..., :3])
    fin = srgb + (o - srgb) * P['Amount']
    al = sa + (c[..., 3:4] - sa) * P['Amount']
    return np.concatenate([fin * al, al], -1)


def reference(img, pars=None, t=0.0):
    return render(img, pars_of(pars))


def compare(td_out, ref, tol=2.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
