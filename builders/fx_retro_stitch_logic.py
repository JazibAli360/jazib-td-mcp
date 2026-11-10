# fx_retro_stitch_logic - numpy mirror of FX_retro 'stitch' (builders/fx_retro_stitch.py) fx pass, given the cell
# colours (`low`: use fx_retro_pixelart_logic.low for Colour none / levels, or the live `low` texels). Arrays: [y, x,
# rgba], row 0 = BOTTOM. Pure numpy, no TD names. ASCII only.
import numpy as np

M32 = 0xffffffff
DEFAULTS = {'Amount': 1.0, 'Style': 0, 'Pixelsize': 18.0, 'Pixelaspect': 1.0, 'Thread': 0.55, 'Twist': 3.0,
            'Gloss': 0.35, 'Shadow': 0.45, 'Jitter': 0.25, 'Strands': 4, 'Seed': 1, 'Fabricr': 0.93, 'Fabricg': 0.9,
            'Fabricb': 0.82, 'Weave': 0.18, 'Holes': 0.5, 'Skip': 0.08, 'Sampling': 1, 'Colour': 2, 'Levels': 5,
            'Dither': 0, 'Ditheramt': 1.0, 'Contrast': 1.1, 'Brightness': 0.0, 'Saturation': 1.25}


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
    a = (np.asarray(vx).astype(np.uint64) * 1597334677) & M32
    b = lb32((np.asarray(vy).astype(np.uint64) ^ ((int(k) * 2654435761) & M32)) & M32)
    return (lb32(a ^ b) >> 8).astype(np.float64) / 16777216.0


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def strand(lx, ly, A, B, W2):
    ax, ay = A
    bx, by = B
    dx, dy = bx - ax, by - ay
    L2 = np.maximum(dx * dx + dy * dy, 1e-6)
    t = np.clip(((lx - ax) * dx + (ly - ay) * dy) / L2, 0.0, 1.0)
    r = np.hypot(lx - ax - dx * t, ly - ay - dy * t) / W2
    return np.where(r < 1.0, np.sqrt(np.maximum(1.0 - r * r, 0.0)), 0.0), t


def render(img, cells, P, psx, psy):
    """img [H, W, 4] (Amount mix), cells [VH, VW, >=3] straight thread colour per cell."""
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0:
        return img.copy()
    H, W = img.shape[:2]
    cells = np.asarray(cells, dtype=np.float64)
    VH, VW = cells.shape[:2]
    y, x = np.mgrid[0:H, 0:W]
    vx, vy = x // psx, y // psy
    lx, ly = (x - vx * psx + 0.5) / psx, (y - vy * psy + 0.5) / psy
    cell = cells[np.minimum(vy, VH - 1), np.minimum(vx, VW - 1), :3]
    fabc = np.array([P['Fabricr'], P['Fabricg'], P['Fabricb']])
    fab = fabc * (1.0 - P['Weave'] * (0.5 + 0.5 * np.cos(6.2831853 * 2.0 * lx) * np.cos(6.2831853 * 2.0 * ly)))[..., None]
    cq = np.hypot(np.minimum(lx, 1 - lx), np.minimum(ly, 1 - ly))
    hole = P['Holes'] * (1.0 - smoothstep(0.06, 0.14, cq))
    fab = fab * (1.0 - 0.8 * hole)[..., None]
    sew = np.linalg.norm(cell - fabc, axis=-1) > P['Skip']
    sd = int(P['Seed']) * 7919
    j = P['Jitter'] * 0.12
    jA = ((hc(vx, vy, sd + 1) - 0.5) * j, (hc(vx, vy, sd + 2) - 0.5) * j)
    jB = ((hc(vx, vy, sd + 3) - 0.5) * j, (hc(vx, vy, sd + 4) - 0.5) * j)
    st = int(P['Style'])
    W2 = 0.5 * P['Thread'] * 0.36
    shx, shy = 0.07, -0.07
    zero = np.zeros_like(lx)
    bot = (zero, zero)
    if st == 2:
        n = max(int(P['Strands'] + 0.5), 1)
        k = (lx - ly) * n * 0.5 + n * 0.5
        fi = np.clip(np.floor(k), 0, n - 1)
        off = (fi + 0.5) / n * 2.0 - 1.0
        A = (0.5 * off + jA[0], -0.5 * off + jA[1])
        B = (1.0 + 0.5 * off + jB[0], 1.0 - 0.5 * off + jB[1])
        W2 = 0.5 * P['Thread'] * 0.7071 / n * 1.15
        top = strand(lx, ly, A, B, W2)
        shd = strand(lx - shx, ly - shy, A, B, W2)[0]
    else:
        A, B = (0.08 + jA[0], 0.08 + jA[1]), (0.92 + jB[0], 0.92 + jB[1])
        top = strand(lx, ly, A, B, W2)
        shd = strand(lx - shx, ly - shy, A, B, W2)[0]
        if st == 0:
            A2, B2 = (0.08 + jB[0], 0.92 + jB[1]), (0.92 + jA[0], 0.08 + jA[1])
            bot = strand(lx, ly, A2, B2, W2)
            shd = np.maximum(shd, strand(lx - shx, ly - shy, A2, B2, W2)[0])

    def thread(s, sgn):
        sh, t = s
        ridge = 1.0 - 0.18 * (0.5 + 0.5 * np.sin(6.2831853 * (t * P['Twist'] + sgn * 0.25 * (1.0 - sh))))
        return cell * ((0.45 + 0.55 * sh) * ridge)[..., None] + (P['Gloss'] * sh ** 8)[..., None]
    o = fab * (1.0 - P['Shadow'] * np.minimum(shd * 2.0, 1.0))[..., None]
    o = np.where((bot[0] > 0)[..., None], thread(bot, -1.0), o)
    o = np.where((top[0] > 0)[..., None], thread(top, 1.0), o)
    o = np.where(sew[..., None], o, fab)
    sa = img[..., 3:4]
    src = np.where(sa > 1e-5, img[..., :3] / np.maximum(sa, 1e-12), img[..., :3])
    fin = src + (o - src) * P['Amount']
    al = sa + (1.0 - sa) * P['Amount']
    return np.concatenate([fin * al, al], -1)


def compare(td_out, ref, tol=3.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
