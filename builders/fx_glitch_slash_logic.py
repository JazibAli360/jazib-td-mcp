# fx_glitch_slash_logic - numpy mirror of the FX_glitch 'slash' shader (builders/fx_glitch_slash.py).
# Pure numpy (no TD names): exec-able inside TD for live parity. Arrays are in TD's TOP readback layout: [y, x, rgba],
# row 0 = the BOTTOM row, float32 0..1. Same uint32 hash as the shader (lowbias32). ASCII only.
import math

import numpy as np

DEFAULTS = {'Amount': 1.0, 'Drive': 1, 'Open': 1.0, 'Hit': 0.0, 'Auto': 2.0, 'Count': 1, 'Placement': 0,
            'Angle': 20.0, 'Anglejitter': 30.0, 'Spread': 0.5, 'Gap': 24.0, 'Slide': 160.0, 'Randomdir': 1,
            'Jag': 0.0, 'Jagsize': 60.0, 'Seed': 1, 'Attack': 0.06, 'Hold': 0.6, 'Release': 0.4, 'Stagger': 0.05,
            'Back': 0, 'Backdim': 0.2, 'Glow': 1.0, 'Glowwidth': 4.0, 'Sparks': 0.3, 'Glowr': 1.0, 'Glowg': 0.85,
            'Glowb': 0.6, 'Pointu': 0.5, 'Pointv': 0.5}
M32 = 0xffffffff


def lb32(x):
    x = np.asarray(x, dtype=np.uint64) & M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def h3(a, b, c):
    a = np.asarray(a, dtype=np.uint64) & M32
    b = np.asarray(b, dtype=np.uint64) & M32
    c = np.asarray(c, dtype=np.uint64) & M32
    inner = lb32(b ^ lb32((c + 0x9e3779b9) & M32))
    return (lb32(((a * 1597334677) & M32) ^ inner).astype(np.float64) / 4294967296.0)


def pars_of(over=None):
    d = dict(DEFAULTS)
    d.update(over or {})
    return d


def cut_key(seed, cnt, k):
    return int(lb32((int(seed) * 7919 + int(cnt) * 104729 + int(k) * 31) & M32))


def open_amount(P, k, now, hittime):
    if int(P['Drive']) == 0:
        return float(P['Open'])
    tk = now - (hittime + k * P['Stagger'])
    if hittime < -500.0 or tk < 0.0:
        return 0.0
    if tk < P['Attack']:
        x = tk / P['Attack']
        return x * x * (3.0 - 2.0 * x)
    if tk < P['Attack'] + P['Hold'] or P['Release'] <= 0.0:
        return 1.0
    x = min(max((tk - P['Attack'] - P['Hold']) / P['Release'], 0.0), 1.0)
    return 1.0 - x * x * (3.0 - 2.0 * x)


def cuts(P, W, H, now=0.0, hittime=-1000.0, cnt=0):
    """[(k, open, centre, t, n, off, key)] for k = N-1 .. 0 with open > 0 (the shader's loop order)."""
    N = max(0, min(8, int(P['Count'] + 0.5)))
    pl = int(P['Placement'])
    sz = np.array([W, H], dtype=np.float64)
    Pt = np.array([P['Pointu'], P['Pointv']]) * sz
    out = []
    for k in range(7, -1, -1):
        if k >= N:
            continue
        key = cut_key(P['Seed'], cnt, k)
        o = open_amount(P, k, now, hittime)
        if o <= 0.0:
            continue
        jit = (float(h3(key, 1, 0)) * 2.0 - 1.0) * P['Anglejitter']
        a = math.radians(P['Angle'] + jit)
        if pl == 1:
            a = math.radians(P['Angle'] + k * 180.0 / max(N, 1) + jit)
        t = np.array([math.cos(a), math.sin(a)])
        n = np.array([-t[1], t[0]])
        cen = Pt.copy()
        if pl == 0:
            cen = Pt + (np.array([float(h3(key, 2, 0)), float(h3(key, 3, 0))]) - 0.5) * P['Spread'] * sz
        elif pl == 2:
            ext = abs(n[0]) * W + abs(n[1]) * H
            cen = Pt + n * ((k + 0.5) / max(N, 1) - 0.5) * P['Spread'] * ext
        sg = -1.0 if (P['Randomdir'] and float(h3(key, 4, 0)) < 0.5) else 1.0
        off = o * (n * P['Gap'] * 0.5 + t * P['Slide'] * 0.5 * sg)
        out.append((k, o, cen, t, n, off, key))
    return out


def _jag(u, key, P):
    s = u / max(P['Jagsize'], 1.0)
    i = np.floor(s)
    f = s - i
    ii = (i.astype(np.int64) + 1048576) & M32
    a = h3(ii, key, 11) * 2.0 - 1.0
    b = h3(ii + 1, key, 11) * 2.0 - 1.0
    return a + (b - a) * f


def _side(qx, qy, cen, t, n, key, P):
    rx, ry = qx - cen[0], qy - cen[1]
    f = rx * n[0] + ry * n[1]
    if P['Jag'] > 0.0:
        f = f - P['Jag'] * _jag(rx * t[0] + ry * t[1], key, P)
    return f


def bilinear(img, qx, qy):
    """GPU-style bilinear lookup at pixel-space coords (centres at +0.5), edge held (inputextenduv hold)."""
    Hh, W = img.shape[:2]
    x = qx - 0.5
    y = qy - 0.5
    x0 = np.floor(x)
    y0 = np.floor(y)
    fx = (x - x0)[..., None]
    fy = (y - y0)[..., None]
    x0 = x0.astype(np.int64)
    y0 = y0.astype(np.int64)
    xa, xb = np.clip(x0, 0, W - 1), np.clip(x0 + 1, 0, W - 1)
    ya, yb = np.clip(y0, 0, Hh - 1), np.clip(y0 + 1, 0, Hh - 1)
    top = img[ya, xa] * (1 - fx) + img[ya, xb] * fx
    bot = img[yb, xa] * (1 - fx) + img[yb, xb] * fx
    return top * (1 - fy) + bot * fy


def reference(img, pars=None, now=0.0, hittime=-1000.0, cnt=0):
    """The fx pass for picture img [H, W, 4] -> float out (unclipped; compare() clips like the 8-bit store)."""
    P = pars_of(pars)
    img = np.asarray(img, dtype=np.float64)
    Hh, W = img.shape[:2]
    if P['Amount'] <= 0.0:
        return img.copy()
    ys, xs = np.mgrid[0:Hh, 0:W].astype(np.float64)
    qx, qy = xs + 0.5, ys + 0.5
    alive = np.ones((Hh, W), bool)
    gap = np.zeros((Hh, W), bool)
    edge = np.full((Hh, W), 1e20)
    eo = np.zeros((Hh, W))
    gk = np.full((Hh, W), -1, np.int64)
    gu = np.zeros((Hh, W))
    gf = np.zeros((Hh, W))
    gh = np.ones((Hh, W))
    for k, o, cen, t, n, off, key in cuts(P, W, Hh, now, hittime, cnt):
        fp = _side(qx - off[0], qy - off[1], cen, t, n, key, P)
        plus = alive & (fp > 0.0)
        fm = _side(qx + off[0], qy + off[1], cen, t, n, key, P)
        minus = alive & ~plus & (fm <= 0.0)
        g = alive & ~plus & ~minus
        upd = plus & (fp < edge)
        eo[upd] = o
        edge[upd] = fp[upd]
        updm = minus & (-fm < edge)
        eo[updm] = o
        edge[updm] = -fm[updm]
        qx = np.where(plus, qx - off[0], np.where(minus, qx + off[0], qx))
        qy = np.where(plus, qy - off[1], np.where(minus, qy + off[1], qy))
        gk[g] = k
        gu[g] = ((qx - cen[0]) * t[0] + (qy - cen[1]) * t[1])[g]
        gf[g] = _side(qx, qy, cen, t, n, key, P)[g]
        gh[g] = max(o * P['Gap'] * 0.5, 1e-3)
        gap |= g
        alive &= ~g
    bm = int(P['Back'])
    if bm == 0:
        back = np.concatenate([np.zeros_like(img[..., :3]), img[..., 3:]], -1)
    elif bm == 1:
        back = np.concatenate([img[..., :3] * P['Backdim'], img[..., 3:]], -1)
    else:
        back = np.zeros_like(img)
    K = np.array([P['Glowr'], P['Glowg'], P['Glowb']])
    samp = bilinear(img, qx, qy)
    edge_glow = P['Glow'] * eo * np.exp(-np.minimum(edge, 1e6) / max(P['Glowwidth'], 1e-3))
    if P['Glow'] > 0.0:
        samp[..., :3] += K * np.where(edge < 1e19, edge_glow, 0.0)[..., None]
    outside = (qx < 0) | (qy < 0) | (qx > W) | (qy > Hh)
    res = np.where((gap | outside)[..., None], back, samp)
    if P['Sparks'] > 0.0 and gap.any():
        tick = int(max(math.floor(now * 30.0), 0))
        yy, xx = np.nonzero(gap)
        cell = (np.floor(gu[yy, xx] / 4.0).astype(np.int64) + 1048576) & M32
        keys = np.array([cut_key(P['Seed'], cnt, int(k)) for k in gk[yy, xx]], dtype=np.uint64)
        s = h3(cell, tick, keys)
        hit = s < P['Sparks'] * 0.5
        w = (1.0 - np.clip(np.abs(gf[yy, xx]) / gh[yy, xx], 0.0, 1.0)) * (0.5 + h3(cell, tick, keys + 5))
        add = (K[None, :] * P['Glow'] * w[:, None]) * hit[:, None]
        res[yy, xx, :3] += add
        res[yy, xx, 3] = np.where(hit, np.maximum(res[yy, xx, 3], np.clip(w, 0.0, 1.0)), res[yy, xx, 3])
    return img + (res - img) * P['Amount']


def regions(pars, W, H, now=0.0, hittime=-1000.0, cnt=0):
    """Per-pixel class for tests / live: 0 = picture (a piece), 1 = Back (gap, or moved in from outside)."""
    P2 = dict(pars_of(pars), Amount=1.0, Glow=0.0, Sparks=0.0, Back=2)
    out = reference(np.ones((H, W, 4)), P2, now, hittime, cnt)
    return np.where(out[..., 3] < 0.5, 1, 0)


def compare(td_out, ref, tol=2.0 / 255.0):
    """max / mean abs diff and the share of pixels over tol (rgb), ref clipped to 0..1 like the 8-bit store."""
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'over': float((d > tol).mean())}
