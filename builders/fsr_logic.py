# fsr_logic - numpy mirror of the shared FSR 1 shaders builders/glsl/fsr_easu.glsl + fsr_rcas.glsl (AMD FidelityFX
# FSR 1 EASU + RCAS, MIT; FX7a SX-10). Never loaded in TD. Images are numpy H x W x 4 float arrays, row 0 = TD y 0
# (numpyArray order); texel (x, y) = img[y, x]. Every line follows the GLSL (float64 here; the GPU is float32 /
# rgba16float, so parity tolerances are ~1e-3). Also: bilinear (GL texture() with clamp to edge, = EASU z 0) and
# small metrics used by the tests and the live checks (edge_width, overshoot).
import numpy as np

RCAS_LIMIT = 0.25 - 1.0 / 16.0


def _luma(c):
    return c[..., 2] * 0.5 + (c[..., 0] * 0.5 + c[..., 1])


def _taps(img, qx, qy, dx, dy):
    H, W = img.shape[0], img.shape[1]
    return img[np.clip(qy + dy, 0, H - 1), np.clip(qx + dx, 0, W - 1)]


def _grid(img, OW, OH, xs=None, ys=None):
    H, W = img.shape[0], img.shape[1]
    if xs is None:
        ys, xs = np.mgrid[0:OH, 0:OW]
    xs, ys = np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)
    ppx = (xs + 0.5) * W / OW - 0.5
    ppy = (ys + 0.5) * H / OH - 0.5
    fx, fy = np.floor(ppx), np.floor(ppy)
    return fx.astype(np.int64), fy.astype(np.int64), ppx - fx, ppy - fy


def bilinear(img, OW, OH, xs=None, ys=None):
    """= fsr_easu.glsl with uEasu.z 0 (and GL texture() linear + clamp-to-edge at the output texel centres)."""
    img = np.asarray(img, dtype=np.float64)
    qx, qy, px, py = _grid(img, OW, OH, xs, ys)
    f, g = _taps(img, qx, qy, 0, 0), _taps(img, qx, qy, 1, 0)
    j, k = _taps(img, qx, qy, 0, 1), _taps(img, qx, qy, 1, 1)
    px, py = px[..., None], py[..., None]
    return (f * (1 - px) + g * px) * (1 - py) + (j * (1 - px) + k * px) * py


def _set(dirx, diry, ln, w, lA, lB, lC, lD, lE):
    dc, cb = lD - lC, lC - lB
    lx = np.maximum(np.abs(dc), np.abs(cb))
    dx = lD - lB
    dirx = dirx + dx * w
    with np.errstate(divide='ignore', invalid='ignore'):
        lx = np.where(lx > 0, np.clip(np.abs(dx) / np.where(lx > 0, lx, 1), 0, 1), 0.0)
    ln = ln + lx * lx * w
    ec, ca = lE - lC, lC - lA
    ly = np.maximum(np.abs(ec), np.abs(ca))
    dy = lE - lA
    diry = diry + dy * w
    with np.errstate(divide='ignore', invalid='ignore'):
        ly = np.where(ly > 0, np.clip(np.abs(dy) / np.where(ly > 0, ly, 1), 0, 1), 0.0)
    ln = ln + ly * ly * w
    return dirx, diry, ln


def easu(img, OW, OH, xs=None, ys=None):
    """FSR 1 EASU of img to OW x OH (or only at output texels xs, ys). Returns (..., 4)."""
    img = np.asarray(img, dtype=np.float64)
    qx, qy, px, py = _grid(img, OW, OH, xs, ys)
    T = lambda dx, dy: _taps(img, qx, qy, dx, dy)
    bC, cC = T(0, -1), T(1, -1)
    eC, fC, gC, hC = T(-1, 0), T(0, 0), T(1, 0), T(2, 0)
    iC, jC, kC, lC = T(-1, 1), T(0, 1), T(1, 1), T(2, 1)
    nC, oC = T(0, 2), T(1, 2)
    bL, cL, eL, fL, gL, hL = [_luma(c) for c in (bC, cC, eC, fC, gC, hC)]
    iL, jL, kL, lL, nL, oL = [_luma(c) for c in (iC, jC, kC, lC, nC, oC)]
    z = np.zeros_like(px)
    dirx, diry, ln = z, z, z
    dirx, diry, ln = _set(dirx, diry, ln, (1 - px) * (1 - py), bL, eL, fL, gL, jL)
    dirx, diry, ln = _set(dirx, diry, ln, px * (1 - py), cL, fL, gL, hL, kL)
    dirx, diry, ln = _set(dirx, diry, ln, (1 - px) * py, fL, iL, jL, kL, nL)
    dirx, diry, ln = _set(dirx, diry, ln, px * py, gL, jL, kL, lL, oL)
    dirR = dirx * dirx + diry * diry
    zro = dirR < 1.0 / 32768.0
    dirR = np.where(zro, 1.0, 1.0 / np.sqrt(np.where(zro, 1.0, dirR)))
    dirx = np.where(zro, 1.0, dirx)
    dirx, diry = dirx * dirR, diry * dirR
    ln = ln * 0.5
    ln = ln * ln
    stretch = (dirx * dirx + diry * diry) / np.maximum(np.abs(dirx), np.abs(diry))
    l2x, l2y = 1.0 + (stretch - 1.0) * ln, 1.0 - 0.5 * ln
    lob = 0.5 + ((1.0 / 4.0 - 0.04) - 0.5) * ln
    clp = 1.0 / lob
    aC = np.zeros(px.shape + (4,))
    aW = np.zeros_like(px)
    for (ox, oy), c in (((0, -1), bC), ((1, -1), cC), ((-1, 1), iC), ((0, 1), jC), ((0, 0), fC), ((-1, 0), eC),
                        ((1, 1), kC), ((2, 1), lC), ((2, 0), hC), ((1, 0), gC), ((1, 2), oC), ((0, 2), nC)):
        offx, offy = ox - px, oy - py
        vx = (offx * dirx + offy * diry) * l2x
        vy = (offx * (-diry) + offy * dirx) * l2y
        d2 = np.minimum(vx * vx + vy * vy, clp)
        wB = 2.0 / 5.0 * d2 - 1.0
        wA = lob * d2 - 1.0
        wB, wA = wB * wB, wA * wA
        wB = 25.0 / 16.0 * wB - (25.0 / 16.0 - 1.0)
        w = wB * wA
        aC = aC + c * w[..., None]
        aW = aW + w
    mn = np.minimum(np.minimum(fC, gC), np.minimum(jC, kC))
    mx = np.maximum(np.maximum(fC, gC), np.maximum(jC, kC))
    return np.minimum(mx, np.maximum(mn, aC / aW[..., None]))


def rcas(img, sharp=0.2, denoise=False, on=True):
    """FSR 1 RCAS on img (same size out). sharp in stops (0 = strongest)."""
    img = np.asarray(img, dtype=np.float64)
    if not on:
        return img.copy()
    H, W = img.shape[0], img.shape[1]
    pad = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode='edge')
    e = pad[1:H + 1, 1:W + 1]
    b, h = pad[0:H, 1:W + 1], pad[2:H + 2, 1:W + 1]          # b = y - 1, h = y + 1 (as in the GLSL)
    d, f = pad[1:H + 1, 0:W], pad[1:H + 1, 2:W + 2]
    bL, dL, eL, fL, hL = [_luma(c) for c in (b, d, e, f, h)]
    nz = 0.25 * (bL + dL + fL + hL) - eL
    rng = np.maximum.reduce([bL, dL, eL, fL, hL]) - np.minimum.reduce([bL, dL, eL, fL, hL])
    with np.errstate(divide='ignore', invalid='ignore'):
        nz = np.where(rng > 0, np.clip(np.abs(nz) / np.where(rng > 0, rng, 1), 0, 1), 0.0)
    nz = -0.5 * nz + 1.0
    mn4 = np.minimum(np.minimum(b, d), np.minimum(f, h))
    mx4 = np.maximum(np.maximum(b, d), np.maximum(f, h))
    hitMin = np.minimum(mn4, e) / np.maximum(4.0 * mx4, 1e-20)
    hitMax = (1.0 - np.maximum(mx4, e)) / np.minimum(4.0 * mn4 - 4.0, -1e-20)
    lobeC = np.maximum(-hitMin, hitMax)
    aflat = np.maximum(mx4[..., 3], e[..., 3]) <= np.minimum(mn4[..., 3], e[..., 3])
    lobeC[..., 3] = np.where(aflat, -RCAS_LIMIT, lobeC[..., 3])
    lobe = np.maximum(-RCAS_LIMIT, np.minimum(lobeC.max(axis=-1), 0.0)) * 2.0 ** (-sharp)
    if denoise:
        lobe = lobe * nz
    rcpL = 1.0 / (4.0 * lobe + 1.0)
    return (lobe[..., None] * (b + d + f + h) + e) * rcpL[..., None]


def fsr(img, OW, OH, sharp=0.2, denoise=False):
    return rcas(easu(img, OW, OH), sharp, denoise)


# ------------------------------------------------------------------ metrics (tests + live checks)
def edge_width(row, lo=0.1, hi=0.9):
    """10-90 % rise width (in samples, linear interpolation) of a monotone-ish step profile."""
    r = np.asarray(row, dtype=np.float64)
    a, b = r.min(), r.max()
    if b - a <= 1e-9:
        return 0.0
    n = (r - a) / (b - a)
    if n[0] > n[-1]:
        n = n[::-1]

    def cross(t):
        i = int(np.argmax(n >= t))
        if i == 0:
            return 0.0
        return (i - 1) + (t - n[i - 1]) / max(n[i] - n[i - 1], 1e-12)
    return cross(hi) - cross(lo)


def overshoot(out, src_lo, src_hi):
    """How far out leaves [src_lo, src_hi] (max over pixels / channels, 0 = none)."""
    out = np.asarray(out, dtype=np.float64)
    return float(max(np.max(out - src_hi), np.max(src_lo - out), 0.0))


def psnr(a, b):
    m = float(np.mean((np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64)) ** 2))
    return 99.0 if m <= 1e-20 else float(10.0 * np.log10(1.0 / m))


def box_down(img, k):
    """k x k box downsample (an ideal 1/k render stand-in for tests)."""
    img = np.asarray(img, dtype=np.float64)
    H, W = img.shape[0] // k * k, img.shape[1] // k * k
    return img[:H, :W].reshape(H // k, k, W // k, k, -1).mean(axis=(1, 3))
