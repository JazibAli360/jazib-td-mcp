# fx_retro_scaler_logic - numpy mirror of FX_retro 'scaler' (builders/fx_retro_scaler.py): source = grid (centre /
# box) or a given low-res array, modes nearest / sharp / epx / diag, Fit stretch / fit / integer. texelFetch only on
# both sides, so it is exact up to float32. Arrays: [y, x, rgba], row 0 = BOTTOM. Pure numpy. ASCII only.
import numpy as np

DEFAULTS = {'Amount': 1.0, 'Mode': 3, 'Sharpness': 1.0, 'Tolerance': 0.04, 'Fit': 0, 'Source': 0, 'Pixelsize': 8.0,
            'Sampling': 0}


def pars_of(over=None):
    d = dict(DEFAULTS)
    d.update(over or {})
    return d


def grid_source(img, P):
    H, W = img.shape[:2]
    ps = max(1, int(round(P['Pixelsize'])))
    VW, VH = (W + ps - 1) // ps, (H + ps - 1) // ps
    if int(P['Sampling']) == 0:
        ys = np.minimum(np.arange(VH) * ps + ps // 2, H - 1)
        xs = np.minimum(np.arange(VW) * ps + ps // 2, W - 1)
        return img[ys][:, xs].copy()
    out = np.zeros((VH, VW, img.shape[2]))
    for vy in range(VH):
        for vx in range(VW):
            out[vy, vx] = img[vy * ps:min(H, vy * ps + ps), vx * ps:min(W, vx * ps + ps)].reshape(-1, img.shape[2]).mean(0)
    return out


def render(img, P, src=None, src_premult=False):
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0:
        return img.copy()
    if src is None:
        src = grid_source(img, P)
    src = np.asarray(src, dtype=np.float64)
    H, W = img.shape[:2]
    Sh, Sw = src.shape[:2]
    scx, scy = W / Sw, H / Sh
    fit = int(P['Fit'])
    if fit == 1:
        scx = scy = min(scx, scy)
    elif fit == 2:
        scx = scy = max(1.0, np.floor(min(scx, scy)))
    offx, offy = 0.5 * (W - Sw * scx), 0.5 * (H - Sh * scy)
    y, x = np.mgrid[0:H, 0:W]
    tx, ty = (x + 0.5 - offx) / scx, (y + 0.5 - offy) / scy
    inside = (tx >= 0) & (ty >= 0) & (tx < Sw) & (ty < Sh)
    ix, iy = np.floor(tx).astype(np.int64), np.floor(ty).astype(np.int64)
    frx, fry = tx - ix, ty - iy

    def F(i, j):
        return src[np.clip(j, 0, Sh - 1), np.clip(i, 0, Sw - 1)]
    mode = int(P['Mode'])
    if mode == 0:
        o = F(ix, iy)
    elif mode == 1:
        kx, ky = max(scx * P['Sharpness'], 1.0), max(scy * P['Sharpness'], 1.0)
        rx, ry = 0.5 - 0.5 / kx, 0.5 - 0.5 / ky
        cx, cy = frx - 0.5, fry - 0.5
        fx = (cx - np.clip(cx, -rx, rx)) * kx + 0.5
        fy = (cy - np.clip(cy, -ry, ry)) * ky + 0.5
        qx, qy = ix + fx - 0.5, iy + fy - 0.5
        i0x, i0y = np.floor(qx).astype(np.int64), np.floor(qy).astype(np.int64)
        ax, ay = (qx - i0x)[..., None], (qy - i0y)[..., None]
        o = (F(i0x, i0y) * (1 - ax) + F(i0x + 1, i0y) * ax) * (1 - ay) + \
            (F(i0x, i0y + 1) * (1 - ax) + F(i0x + 1, i0y + 1) * ax) * ay
    else:
        Pp, A, B, C, D = F(ix, iy), F(ix, iy + 1), F(ix + 1, iy), F(ix - 1, iy), F(ix, iy - 1)

        def eq(a, b):
            return np.abs(a - b).max(-1) <= P['Tolerance']
        r0 = eq(C, A) & ~eq(C, D) & ~eq(A, B)
        r1 = eq(A, B) & ~eq(A, C) & ~eq(B, D)
        r2 = eq(D, C) & ~eq(D, B) & ~eq(C, A)
        r3 = eq(B, D) & ~eq(B, A) & ~eq(D, C)
        if mode == 2:
            top, right = fry >= 0.5, frx >= 0.5
            o = Pp.copy()
            o = np.where((top & ~right & r0)[..., None], A, o)
            o = np.where((top & right & r1)[..., None], B, o)
            o = np.where((~top & ~right & r2)[..., None], C, o)
            o = np.where((~top & right & r3)[..., None], D, o)
        else:
            w = 1.0 / max(min(scx, scy) * P['Sharpness'], 1e-3)
            u, v = 0.5 - frx, fry - 0.5

            def cov(d):
                return np.clip(d / max(w, 1e-4) + 0.5, 0.0, 1.0)[..., None]
            o = Pp.copy()
            for rr, N, d in ((r0, A, u + v), (r1, B, -u + v), (r2, C, u - v), (r3, D, -u - v)):
                o = np.where(rr[..., None], o + (N - o) * cov((d - 0.5) * 0.7071), o)
    if not src_premult:
        o = np.concatenate([o[..., :3] * o[..., 3:4], o[..., 3:4]], -1)
    o = np.where(inside[..., None], o, 0.0)
    return img + (o - img) * P['Amount']


def reference(img, pars=None, t=0.0, src=None):
    return render(img, pars_of(pars), src)


def compare(td_out, ref, tol=2.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
