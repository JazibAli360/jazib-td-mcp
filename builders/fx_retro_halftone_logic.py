# fx_retro_halftone_logic - numpy mirror of FX_retro 'halftone' (builders/fx_retro_halftone.py). Arrays [y, x, rgba],
# row 0 = BOTTOM, premultiplied (alpha 1 test pictures). Pure numpy. ASCII only.
import math

import numpy as np

M32 = 0xffffffff
DEFAULTS = {'Amount': 1.0, 'Mode': 2, 'Shape': 0, 'Sampling': 0, 'Cellsize': 14.0, 'Angle': 0.0, 'Softness': 0.0,
            'Gamma': 1.0, 'Randomness': 0.0, 'Seed': 1, 'Paperr': 0.96, 'Paperg': 0.94, 'Paperb': 0.88,
            'Inkr': 0.08, 'Inkg': 0.07, 'Inkb': 0.1}


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


def hc(vx, vy, k):
    a = ((np.asarray(vx).astype(np.int64) & M32).astype(np.uint64) * 1597334677) & M32
    b = lb32((np.asarray(vy).astype(np.int64) & M32).astype(np.uint64) ^ ((int(k) * 2654435761) & M32))
    return (lb32(a ^ b) >> 8).astype(np.float64) / 16777216.0


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def render(img, P):
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0:
        return img.copy()
    H, W = img.shape[:2]
    S = max(P['Cellsize'], 1.0)
    al = img[..., 3:4]
    straight = np.clip(np.where(al > 1e-6, img[..., :3] / np.maximum(al, 1e-12), img[..., :3]), 0, 1) ** P['Gamma']
    y, x = np.mgrid[0:H, 0:W]
    pcx, pcy = x + 0.5, y + 0.5
    md = int(P['Mode'])

    def spot(a, ch, salt):
        cs, sn = math.cos(a), math.sin(a)
        px, py = pcx - 0.5 * W, pcy - 0.5 * H
        rx, ry = (cs * px + sn * py) / S, (-sn * px + cs * py) / S
        tx, ty = np.floor(rx), np.floor(ry)
        sd = int(P['Seed']) * 7919 + salt * 31
        jx = (hc(tx, ty, sd) - 0.5) * P['Randomness'] * 0.35
        jy = (hc(tx, ty, sd + 17) - 0.5) * P['Randomness'] * 0.35
        qx, qy = rx - tx - 0.5 - jx, ry - ty - 0.5 - jy
        if int(P['Sampling']) == 0:
            ccx, ccy = (tx + 0.5) * S, (ty + 0.5) * S
            sx, sy = cs * ccx - sn * ccy + 0.5 * W, sn * ccx + cs * ccy + 0.5 * H
            c = straight[np.clip(np.floor(sy).astype(np.int64), 0, H - 1), np.clip(np.floor(sx).astype(np.int64), 0, W - 1)]
        else:
            c = straight
        if md == 0:
            v = 1.0 - (c * np.array([0.299, 0.587, 0.114])).sum(-1)
        elif md == 1:
            v = c[..., ch]
        else:
            cym = 1.0 - c
            k = cym.min(-1)
            v = k if ch == 3 else cym[..., ch] - k
        sh = int(P['Shape'])
        if sh == 0:
            d = np.hypot(qx, qy) * 1.77245385
        elif sh == 1:
            d = np.maximum(np.abs(qx), np.abs(qy)) * 2.0
        elif sh == 2:
            d = np.abs(qy) * 2.0
        else:
            d = (np.abs(qx) + np.abs(qy)) * 1.41421356
        edge = np.sqrt(np.clip(v, 0, 1))
        aa = 1.0 / S + P['Softness'] * 0.3
        out = 1.0 - smoothstep(edge - aa, edge + aa, d)
        return np.where(v <= 0.0001, 0.0, np.where(v >= 0.9999, 1.0, out))
    A = math.radians(P['Angle'])
    paper = np.array([P['Paperr'], P['Paperg'], P['Paperb']])
    ink = np.array([P['Inkr'], P['Inkg'], P['Inkb']])
    if md == 0:
        s = spot(A, 0, 0)[..., None]
        o = paper + (ink - paper) * s
    elif md == 1:
        s3 = np.stack([spot(A, 0, 0), spot(A + 0.5235988, 1, 1), spot(A + 1.0471976, 2, 2)], -1)
        o = ink + (s3 * paper - ink) * 0.85
    else:
        C, Mg, Y = spot(A + 0.2617994, 0, 0), spot(A + 1.3089969, 1, 1), spot(A, 2, 2)
        K = spot(A + 0.7853982, 3, 3)[..., None]
        pr = paper * np.stack([1 - C, 1 - Mg, 1 - Y], -1)
        o = pr + (ink - pr) * K
    o = np.clip(o, 0, 1)
    src = np.where(al > 1e-6, img[..., :3] / np.maximum(al, 1e-12), img[..., :3])
    fin = src + (o - src) * P['Amount']
    return np.concatenate([fin * al, al], -1)


def reference(img, pars=None, t=0.0):
    return render(img, pars_of(pars))


def compare(td_out, ref, tol=3.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
