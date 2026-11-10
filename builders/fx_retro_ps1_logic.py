# fx_retro_ps1_logic - numpy mirror of FX_retro 'ps1' (builders/fx_retro_ps1.py FX pass). Arrays: [y, x, rgba], row
# 0 = BOTTOM, straight alpha-1 test pictures in 0..1. Pure numpy. ASCII only.
import numpy as np

M32 = 0xffffffff
PSX = np.array([-4, 0, -3, 1, 2, -2, 3, -1, -3, 1, -4, 0, 3, -1, 2, -2], dtype=np.float64)
BAY = np.array([0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5], dtype=np.float64)
DEFAULTS = {'Amount': 1.0, 'Downscale': 4.0, 'Bits': 5, 'Dither': 0, 'Ditheramt': 1.0, 'Wobble': 0.0,
            'Wobblesize': 120.0, 'Wobblerate': 15.0, 'Seed': 1}


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


def hv(vx, vy, k):
    a = (np.asarray(vx).astype(np.int64).astype(np.uint64) & M32) * 1597334677 & M32
    b = lb32((np.asarray(vy).astype(np.int64).astype(np.uint64) & M32) ^ ((int(k) * 2654435761) & M32))
    return (lb32(a ^ b) >> 8).astype(np.float64) / 16777216.0


def render(img, P, epoch=0):
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0:
        return img.copy()
    H, W = img.shape[:2]
    y, x = np.mgrid[0:H, 0:W]
    qx, qy = x + 0.5, y + 0.5
    if P['Wobble'] > 0:
        S = max(P['Wobblesize'], 1.0)
        gx, gy = qx / S, qy / S
        ix, iy = np.floor(gx).astype(np.int64), np.floor(gy).astype(np.int64)
        fx, fy = gx - ix, gy - iy
        s = (int(P['Seed']) * 7919 + int(epoch) * 104729) & M32

        def jo(a, b):
            return (hv(a, b, s) - 0.5) * 2.0 * P['Wobble'], (hv(a, b, (s + 7) & M32) - 0.5) * 2.0 * P['Wobble']
        o00, o11, o10, o01 = jo(ix, iy), jo(ix + 1, iy + 1), jo(ix + 1, iy), jo(ix, iy + 1)
        lr = fx >= fy
        dx = np.where(lr, o00[0] + (o10[0] - o00[0]) * fx + (o11[0] - o10[0]) * fy,
                      o00[0] + (o01[0] - o00[0]) * fy + (o11[0] - o01[0]) * fx)
        dy = np.where(lr, o00[1] + (o10[1] - o00[1]) * fx + (o11[1] - o10[1]) * fy,
                      o00[1] + (o01[1] - o00[1]) * fy + (o11[1] - o01[1]) * fx)
        qx, qy = qx - dx, qy - dy
    ds = max(np.floor(P['Downscale'] + 0.5), 1.0)
    vx, vy = np.floor(qx / ds).astype(np.int64), np.floor(qy / ds).astype(np.int64)
    sx = np.clip(np.floor((vx + 0.5) * ds).astype(np.int64), 0, W - 1)
    sy = np.clip(np.floor((vy + 0.5) * ds).astype(np.int64), 0, H - 1)
    s4 = img[sy, sx]
    c = s4[..., :3]
    k = (vy & 3) * 4 + (vx & 3)
    dm = int(P['Dither'])
    dv = PSX[k] if dm == 0 else ((BAY[k] + 0.5) / 16.0 * 8.0 - 4.0 if dm == 2 else np.zeros(k.shape))
    bits = min(max(int(P['Bits'] + 0.5), 1), 8)
    c8 = np.clip(np.floor(np.clip(c, 0, 1) * 255.0 + 0.5) + (dv * P['Ditheramt'])[..., None], 0.0, 255.0)
    cq = np.floor(c8 / float(1 << (8 - bits)))
    o = cq / float((1 << bits) - 1)
    src = img[..., :3]
    fin = src + (o - src) * P['Amount']
    a = img[..., 3:4] + (s4[..., 3:4] - img[..., 3:4]) * P['Amount']
    return np.concatenate([fin * a, a], -1)


def reference(img, pars=None, t=0.0):
    P = pars_of(pars)
    ep = int(t * P['Wobblerate']) if P['Wobblerate'] > 0 else 0
    return render(img, P, ep)


def compare(td_out, ref, tol=2.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
