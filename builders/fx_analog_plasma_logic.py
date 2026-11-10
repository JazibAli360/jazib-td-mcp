# fx_analog_plasma_logic - numpy mirror of FX_analog module 'plasma' (builders/fx_analog_plasma.py; FX2 AV-15).
# Pure numpy, no TD names: tests import it, and a td_exec can exec it inside TD for live parity:
#   L = {}; exec(open('<repo>/builders/fx_analog_plasma_logic.py').read(), L)
#   ref = L['reference'](op('<m>/in1').numpyArray(), L['pars_from_comp'](op('<m>')))
#   print(L['compare'](op('<m>/out1').numpyArray(), ref))       # (read in a SEPARATE exec from any par change, T-74)
# Arrays are TD numpyArray layout: [y, x, rgba] float32 0..1, row 0 = BOTTOM (TD pixel y up), same as the shader's p.
# ASCII only.
import numpy as np

# sub-field weight tables, ascending (index k = sub-field k); every table sums to 255
TABLES = [
    [1, 2, 4, 8, 16, 32, 64, 128],                       # binary8: plain 8 bits (worst contours)
    [1, 2, 4, 8, 16, 32, 48, 48, 48, 48],                # pdp10: 4 equal MSB fields (classic contour reduction)
    [1, 2, 4, 8, 16, 24, 32, 32, 32, 32, 32, 40],        # pdp12: more, smaller MSB fields (least contour)
]
TABLE_NAMES = ['binary8', 'pdp10', 'pdp12']
MOTIONS = ['vector', 'sweep', 'estimate']
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)

DEFAULTS = {
    'Amount': 1.0, 'Subfields': 0, 'Order': 0, 'Address': 6.0, 'Gamma': 2.2, 'Motion': 0, 'Motionx': 6.0,
    'Motiony': 0.0, 'Period': 2.0, 'Seed': 1,
    'Gain': 1.0, 'Estres': 8, 'Eps': 0.0004, 'Minmotion': 0.1, 'Smooth': 0.5,
    'Dither': 0.0, 'Greenlag': 0.0, 'Cells': 0.0, 'Cellsize': 6.0,
}


def P(**over):
    d = dict(DEFAULTS)
    d.update(over)
    return d


def time_centres(tb, order=0, address=0.0):
    """t_k in [0, 1): centre of sub-field k's sustain inside the frame. Each slot = address + weight (address first).
    order 0 = ascending weights in time, 1 = descending. Mirrors the shader's tk[] loop."""
    w = TABLES[tb]
    n = len(w)
    total = np.float32(n * address + 255.0)
    t = np.zeros(n, np.float32)
    cum = np.float32(0.0)
    for s in range(n):
        k = s if order == 0 else n - 1 - s
        t[k] = (cum + np.float32(address) + np.float32(0.5) * np.float32(w[k])) / total
        cum = np.float32(cum + np.float32(address) + np.float32(w[k]))
    return t


def lit_masks(codes, tb):
    """Greedy sub-field decomposition (largest weight first) -> int bit masks (bit k = sub-field k lit)."""
    w = TABLES[tb]
    rem = np.asarray(codes, np.float32).copy()
    m = np.zeros(rem.shape, np.int64)
    for j in range(len(w) - 1, -1, -1):
        on = rem >= w[j]
        rem = np.where(on, rem - np.float32(w[j]), rem)
        m |= on.astype(np.int64) << j
    return m


def decode(masks, tb):
    """Sum of lit weights (the displayed 8-bit level)."""
    w = TABLES[tb]
    s = np.zeros(np.shape(masks), np.float32)
    for k in range(len(w)):
        s += ((np.asarray(masks) >> k) & 1).astype(np.float32) * np.float32(w[k])
    return s


# lowbias32 hash, same as the shader (and builders/fx_destroy.py GLSL_LIB): uint32 maths
def lb32(x):
    x = np.asarray(x, np.uint32).copy()
    with np.errstate(over='ignore'):
        x ^= x >> np.uint32(16)
        x = (x * np.uint32(0x7feb352d)).astype(np.uint32)
        x ^= x >> np.uint32(15)
        x = (x * np.uint32(0x846ca68b)).astype(np.uint32)
        x ^= x >> np.uint32(16)
    return x


def hsh(cx, cy, s):
    with np.errstate(over='ignore'):
        a = (np.asarray(cx).astype(np.int64).astype(np.uint32) * np.uint32(1597334677)).astype(np.uint32)
        b = lb32(np.asarray(cy).astype(np.int64).astype(np.uint32) ^ np.uint32((int(s) * 2654435761) & 0xffffffff))
        return (lb32(a ^ b).astype(np.float64) * (1.0 / 4294967296.0)).astype(np.float32)


def dither_seed(seed, frame):
    return (int(seed) * 977 + int(frame)) & 0xffffffff


def codes(vals, gamma, dith):
    """8-bit code of channel values (after the panel's gamma) + dither offset (code units)."""
    v = np.maximum(np.asarray(vals, np.float32), np.float32(0.0))
    g = v if float(gamma) == 1.0 else np.power(v, np.float32(gamma)).astype(np.float32)
    x = g * np.float32(255.0) + dith
    return np.clip(np.floor(x + np.float32(0.5)), 0.0, 255.0).astype(np.float32)


def sample_field(est, w, h):
    """Bilinear (clamp to edge = inputextenduv hold) sample of the coarse est field at every full-res pixel centre."""
    eh, ew = est.shape[:2]
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (x + 0.5) / w * ew - 0.5
    v = (y + 0.5) / h * eh - 0.5
    x0 = np.floor(u).astype(np.int64)
    y0 = np.floor(v).astype(np.int64)
    fx = (u - x0)[..., None]
    fy = (v - y0)[..., None]
    xa, xb = np.clip(x0, 0, ew - 1), np.clip(x0 + 1, 0, ew - 1)
    ya, yb = np.clip(y0, 0, eh - 1), np.clip(y0 + 1, 0, eh - 1)
    e = est[..., :2].astype(np.float32)
    top = e[ya, xa] * (1 - fx) + e[ya, xb] * fx
    bot = e[yb, xa] * (1 - fx) + e[yb, xb] * fx
    return (top * (1 - fy) + bot * fy).astype(np.float32)


def motion_vector(pars, t=0.0):
    """Uniform part of the motion (px per cook): Motionx/y, x sin(2 pi t / Period) in sweep mode."""
    vx, vy = float(pars['Motionx']), float(pars['Motiony'])
    if int(pars['Motion']) == 1:
        s = np.sin(2.0 * np.pi * t / max(float(pars['Period']), 1e-3))
        vx, vy = vx * s, vy * s
    return np.float32(vx), np.float32(vy)


def reference(img, pars=None, frame=0, t=0.0, est=None):
    """The fx pass in numpy. img [h, w, 4] float32 (row 0 = bottom). est = coarse est state [eh, ew, 4] (estimate
    mode; xy = full px per cook) or None (= zero field). Returns [h, w, 4] float32 (before the 8-bit store)."""
    p = P(**(pars or {}))
    img = np.asarray(img, np.float32)
    h, w = img.shape[:2]
    amt = float(p['Amount'])
    if amt <= 0.0:
        return img.copy()
    tb = int(min(max(int(round(float(p['Subfields']))), 0), 2))
    wts = TABLES[tb]
    n = len(wts)
    tk = time_centres(tb, int(p['Order']), float(p['Address']))
    vx, vy = motion_vector(p, t)
    V = np.zeros((h, w, 2), np.float32)
    V[..., 0], V[..., 1] = vx, vy
    if int(p['Motion']) == 2 and est is not None:
        V = V + sample_field(np.asarray(est, np.float32), w, h) * np.float32(p['Gain'])
    y, x = np.mgrid[0:h, 0:w]
    pcx, pcy = x.astype(np.float32) + 0.5, y.astype(np.float32) + 0.5
    seed = dither_seed(p['Seed'], frame)
    gam, dth, gl = float(p['Gamma']), np.float32(p['Dither']), np.float32(p['Greenlag'])
    acc = np.zeros((h, w, 3), np.float32)

    def masks_at(qx, qy, chans):
        d = (hsh(qx, qy, seed) - np.float32(0.5)) * dth
        s = img[qy, qx]
        return [lit_masks(codes(s[..., c], gam, d), tb) for c in chans]

    for k in range(n):
        qx = np.clip(np.floor(pcx + V[..., 0] * (tk[k] - np.float32(0.5))).astype(np.int64), 0, w - 1)
        qy = np.clip(np.floor(pcy + V[..., 1] * (tk[k] - np.float32(0.5))).astype(np.int64), 0, h - 1)
        mr, mg, mb = masks_at(qx, qy, (0, 1, 2))
        if gl != 0.0:
            gx = np.clip(np.floor(pcx + V[..., 0] * (tk[k] + gl - np.float32(0.5))).astype(np.int64), 0, w - 1)
            gy = np.clip(np.floor(pcy + V[..., 1] * (tk[k] + gl - np.float32(0.5))).astype(np.int64), 0, h - 1)
            mg = masks_at(gx, gy, (1,))[0]
        wk = np.float32(wts[k])
        for c, m in enumerate((mr, mg, mb)):
            acc[..., c] += ((m >> k) & 1).astype(np.float32) * wk
    o = acc / np.float32(255.0)
    if gam != 1.0:
        o = np.power(o, np.float32(1.0 / gam)).astype(np.float32)
    cells = float(p['Cells'])
    if cells > 0.0:
        cs = max(float(p['Cellsize']), 1.0)
        fr = (pcx / np.float32(cs)) % 1.0
        sub = np.minimum((fr * 3.0).astype(np.int64), 2)
        msk = np.full((h, w, 3), 1.0 - cells, np.float32)
        for c in range(3):
            msk[..., c] = np.where(sub == c, 1.0, msk[..., c])
        rib = ((pcy / np.float32(cs)) % 1.0) < 0.12
        msk = np.where(rib[..., None], msk * np.float32(1.0 - cells), msk)
        o = o * msk
    out = np.empty_like(img)
    out[..., :3] = img[..., :3] * np.float32(1.0 - amt) + o * np.float32(amt)
    out[..., 3] = img[..., 3]
    return out


def cell_luma(img, E):
    """Coarse luma per E x E cell: mean of a 4 x 4 texel grid at offsets (i + 0.5) E / 4 (clamped)."""
    img = np.asarray(img, np.float32)
    h, w = img.shape[:2]
    ch, cw = (h + E - 1) // E, (w + E - 1) // E
    cy, cx = np.mgrid[0:ch, 0:cw]
    s = np.zeros((ch, cw), np.float32)
    Y = (img[..., :3] * LUMA).sum(-1).astype(np.float32)
    for j in range(4):
        for i in range(4):
            qx = np.clip(cx * E + int((i + 0.5) * E * 0.25), 0, w - 1)
            qy = np.clip(cy * E + int((j + 0.5) * E * 0.25), 0, h - 1)
            s += Y[qy, qx]
    return s / np.float32(16.0)


def est_step(img, prev, pars=None, now=1.0):
    """One cook of the est pass (in place state). prev = [ch, cw, 4] (zeros on the first cook): xy motion (full px),
    z luma, w last cook time. Same frame (now == prev.w) = unchanged; gap > 0.25 s or never cooked = reset (v 0)."""
    p = P(**(pars or {}))
    E = max(int(round(float(p['Estres']))), 1)
    L = cell_luma(img, E)
    ch, cw = L.shape
    if prev is None:
        prev = np.zeros((ch, cw, 4), np.float32)
    prev = np.asarray(prev, np.float32)
    xp, xm = np.minimum(np.arange(cw) + 1, cw - 1), np.maximum(np.arange(cw) - 1, 0)
    yp, ym = np.minimum(np.arange(ch) + 1, ch - 1), np.maximum(np.arange(ch) - 1, 0)
    gx = 0.5 * (L[:, xp] - L[:, xm])
    gy = 0.5 * (L[yp, :] - L[ym, :])
    now = np.float32(now)
    same = prev[..., 3] == now
    fresh = ~((now - prev[..., 3]) <= 0.25) | (prev[..., 3] <= 0.0)
    It = L - prev[..., 2]
    den = gx * gx + gy * gy + np.float32(p['Eps'])
    vx = -It * gx / den * np.float32(E)
    vy = -It * gy / den * np.float32(E)
    small = np.sqrt(vx * vx + vy * vy) < np.float32(p['Minmotion'])
    vx, vy = np.where(small, 0.0, vx), np.where(small, 0.0, vy)
    sm = np.float32(p['Smooth'])
    vx = vx * (1 - sm) + prev[..., 0] * sm
    vy = vy * (1 - sm) + prev[..., 1] * sm
    vx, vy = np.where(fresh, 0.0, vx), np.where(fresh, 0.0, vy)
    out = np.stack([vx, vy, L, np.full_like(L, now)], -1).astype(np.float32)
    out[same] = prev[same]
    return out


def compare(td_out, ref, tol=1.0 / 255.0):
    """Both [h, w, 4] in the same layout -> stats on 8-bit codes (rgb). Pass = max_codes <= 1 and frac_off < 1e-3."""
    a = np.round(np.asarray(td_out, np.float64)[..., :3] * 255.0)
    b = np.round(np.clip(np.asarray(ref, np.float64)[..., :3], 0, 1) * 255.0)
    d = np.abs(a - b)
    return {'max_codes': float(d.max()), 'mean_codes': float(d.mean()),
            'frac_off': float((d > tol * 255.0 + 1e-9).mean()), 'frac_any': float((d > 0).mean())}


def pars_from_comp(m):
    """Read the module COMP's pars (TD side) into the dict reference() takes (menus as index)."""
    out = {}
    for k in DEFAULTS:
        par = getattr(m.par, k, None)
        if par is None:
            continue
        out[k] = par.menuIndex if par.isMenu else par.eval()
    return out
