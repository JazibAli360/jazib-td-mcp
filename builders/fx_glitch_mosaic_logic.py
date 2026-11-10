# fx_glitch_mosaic_logic - numpy mirror of FX_glitch 'mosaic' Shape hex / tri / square (7C-33 cells with beat flips;
# `lattice` / `cells` in builders/fx_glitch_mosaic.py). Cellfill centre / image are mirrored exactly (mean uses TD's
# mip chain: checked by look). Arrays: [y, x, rgba], row 0 = BOTTOM, 0..1. Pure numpy, no TD names. ASCII only.
import math

import numpy as np

SHAPES = ['quad', 'hex', 'tri', 'square']
DEFAULTS = {'Amount': 1.0, 'Shape': 1, 'Cellsize': 48.0, 'Cellfill': 0, 'Gap': 2.0, 'Gapr': 0.0, 'Gapg': 0.0,
            'Gapb': 0.0, 'Flip': 0.0, 'Flipmode': 0, 'Fliptime': 0.4, 'Recolour': 0.0, 'Edges': 0.0, 'Seed': 1}
M32 = 0xffffffff


def pars_of(over=None):
    d = dict(DEFAULTS)
    d.update(over or {})
    return d


def pcg(v):
    v = np.asarray(v, dtype=np.uint64) & M32
    s = (v * 747796405 + 2891336453) & M32
    w = (((s >> ((s >> 28) + 4)) ^ s) * 277803737) & M32
    return (w >> 22) ^ w


def h4(a, b, c, d):
    u = lambda x: (np.asarray(x).astype(np.int64) & M32).astype(np.uint64)  # noqa: E731
    k = pcg(u(a) ^ pcg(u(b) ^ pcg(u(c) ^ pcg(u(d)))))
    return (k >> 8).astype(np.float64) / 16777215.0


def lattice(qx, qy, shp):
    """-> cen x, cen y, edge (cell units), id x, id y. Same maths as the GLSL `lattice`."""
    if shp == 1:
        rx, ry = 1.0, 1.7320508
        ax, ay = np.mod(qx, rx) - 0.5 * rx, np.mod(qy, ry) - 0.5 * ry
        bx, by = np.mod(qx - 0.5 * rx, rx) - 0.5 * rx, np.mod(qy - 0.5 * ry, ry) - 0.5 * ry
        pa = ax * ax + ay * ay < bx * bx + by * by
        gx, gy = np.where(pa, ax, bx), np.where(pa, ay, by)
        cx, cy = qx - gx, qy - gy
        g1, g2 = np.abs(gx), np.abs(gy)
        edge = 0.5 - np.maximum(g1 * 0.5 + g2 * 0.8660254, g1)
        ix, iy = np.floor(cx * 2.0 + 0.5), np.floor(cy / 0.8660254 + 0.5)
    elif shp == 2:
        h = 0.8660254
        bq = qy / h
        j = np.floor(bq)
        fy = bq - j
        xs = qx - 0.5 * bq
        i = np.floor(xs)
        fx = xs - i
        up = fx + fy >= 1.0
        v0x = np.where(up, i + 1.0 + 0.5 * j, i + 0.5 * j)
        v0y = j * h
        v1x = np.where(up, i + 1.0 + 0.5 * (j + 1.0), i + 1.0 + 0.5 * j)
        v1y = np.where(up, (j + 1.0) * h, j * h)
        v2x, v2y = i + 0.5 * (j + 1.0), (j + 1.0) * h
        cx, cy = (v0x + v1x + v2x) / 3.0, (v0y + v1y + v2y) / 3.0
        e0 = np.where(up, 1.0 - fy, fy)
        e1 = np.where(up, fx + fy - 1.0, 1.0 - fx - fy)
        e2 = np.where(up, 1.0 - fx, fx)
        edge = np.minimum(e0, np.minimum(e1, e2)) * h
        ix, iy = i * 2 + up, j
    else:
        fx, fy = np.floor(qx), np.floor(qy)
        cx, cy = fx + 0.5, fy + 0.5
        edge = 0.5 - np.maximum(np.abs(qx - cx), np.abs(qy - cy))
        ix, iy = fx, fy
    return cx, cy, edge, ix.astype(np.int64), iy.astype(np.int64)


def hue_turn(c, t):
    y = c @ np.array([0.299, 0.587, 0.114])
    i = c @ np.array([0.596, -0.274, -0.322])
    q = c @ np.array([0.211, -0.523, 0.312])
    a = 6.2831853 * t
    i2, q2 = i * math.cos(a) - q * math.sin(a), i * math.sin(a) + q * math.cos(a)
    return np.stack([y + 0.956 * i2 + 0.621 * q2, y - 0.272 * i2 - 0.647 * q2, y - 1.106 * i2 + 1.703 * q2], -1)


def cells(img, P, now=0.0, last=0.0, cnt=0):
    """Shape hex / tri / square out1 (before the Amount mix) for img; stamp: now, last rebuild time, rebuild count."""
    img = np.asarray(img, dtype=np.float64)
    H, W = img.shape[:2]
    S = max(P['Cellsize'], 1.0)
    shp = int(P['Shape'])
    y, x = np.mgrid[0:H, 0:W]
    qx, qy = (x + 0.5 - 0.5 * W) / S, (y + 0.5 - 0.5 * H) / S
    cx, cy, edge, ix, iy = lattice(qx, qy, shp)
    gap = edge * S < 0.5 * P['Gap']
    ph = min(max((now - last) / max(P['Fliptime'], 1e-3), 0.0), 1.0)
    flp = (ph < 1.0) & (h4(ix, iy, cnt, int(P['Seed']) * 7919 + 3) < P['Flip'])
    gx, gy = qx - cx, qy - cy
    k = math.cos(math.pi * ph)
    back = flp & (k < 0.0)
    fm = int(P['Flipmode'])
    sgn = -1.0 if k < 0.0 else 1.0
    if fm == 0:
        gy = np.where(flp, gy / max(abs(k), 1e-3) * sgn, gy)
    elif fm == 1:
        gx = np.where(flp, gx / max(abs(k), 1e-3) * sgn, gx)
    elif fm == 2:
        f = max(1.0 - math.sin(math.pi * ph), 1e-3)
        gx, gy = np.where(flp, gx / f, gx), np.where(flp, gy / f, gy)
    else:
        a = math.pi * ph
        nx, ny = math.cos(a) * gx + math.sin(a) * gy, -math.sin(a) * gx + math.cos(a) * gy
        gx, gy = np.where(flp, nx, gx), np.where(flp, ny, gy)
    _c2x, _c2y, e2, jx, jy = lattice(cx + gx, cy + gy, shp)
    gap = gap | (flp & ((jx != ix) | (jy != iy) | (e2 * S < 0.5 * P['Gap'])))
    fill = int(P['Cellfill'])
    if fill == 2:
        sx, sy = (cx + gx) * S + 0.5 * W, (cy + gy) * S + 0.5 * H
    else:
        sx, sy = cx * S + 0.5 * W, cy * S + 0.5 * H
    if fill == 1:
        raise NotImplementedError('mean fill reads the TD mip chain')
    xi = np.clip(np.floor(sx).astype(np.int64), 0, W - 1)
    yi = np.clip(np.floor(sy).astype(np.int64), 0, H - 1)
    col = img[yi, xi, :3]
    if P['Recolour'] != 0.0:
        col = np.where(back[..., None], hue_turn(col, P['Recolour']), col)
    t = np.clip((edge * S - 0.5 * P['Gap']) / 3.0, 0.0, 1.0)
    col = col * (1.0 - P['Edges'] * (1.0 - t * t * (3.0 - 2.0 * t)))[..., None]
    out = img.copy()
    out[..., :3] = np.where(gap[..., None], np.array([P['Gapr'], P['Gapg'], P['Gapb']]), col)
    return out


def reference(img, pars=None, t=0.0, last=0.0, cnt=0):
    P = pars_of(pars)
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0.0:
        return img.copy()
    o = cells(img, P, t, last, cnt)
    return img + (o - img) * P['Amount']


def compare(td_out, ref, tol=2.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
