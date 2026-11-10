# fx_destroy_shatter_glass_logic - numpy mirror of FX_destroy shatter's Look glass shading (FX4 D11), for offline
# tests and the live parity check (docs/builds/fx_destroy.md "Glass look (D11)" LIVE CHECKS).
# Same maths as glassSlope() / glassShade() in builders/fx_destroy_shatter.py FX: lowbias32 hash (GLSL_LIB hsh),
# per-shard tilt turned by the shard angle and grown by its z scale, bevel toward the edge, offset = slope x
# Thickness x (1 - 1/Ior), R / G / B read at off x (1 - D) / 1 / (1 + D), Schlick Fresnel rim normalised to 0 on a
# flat face, Blinn spec. Pictures are TD numpyArray()s: float32 (H, W, 4), row 0 = BOTTOM (TD y up); positions are
# pixel coordinates (x, y) with pixel centres at +0.5, like the shader's q. Pure numpy; ASCII only.
import math

import numpy as np

M32 = 0xFFFFFFFF


def lb32(x):
    x &= M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def hsh(cx, cy, s):
    """GLSL_LIB hsh(ivec2(cx, cy), uint s) -> [0, 1)."""
    a = ((cx & M32) * 1597334677) & M32
    b = lb32((cy & M32) ^ ((s * 2654435761) & M32))
    return lb32(a ^ b) / 4294967296.0


def defaults():
    return {'Ior': 1.5, 'Thickness': 60.0, 'Dispersion': 0.3, 'Tilt': 0.35, 'Bevel': 14.0, 'Fresnel': 0.8,
            'Specular': 0.4, 'Shine': 60.0, 'Lightangle': 45.0, 'Glasstint': (0.95, 0.98, 1.0),
            'Rimcolor': (0.85, 0.95, 1.0), 'Seed': 1}


def glass_slope(bi, angle, scale, be, bn, pars):
    """Pane slope (2,) of shard bi (global shard index) at edge distance be (px) with inward edge normal bn."""
    sd = int(pars['Seed']) + 911
    h = np.array([hsh(bi, 7, sd), hsh(bi, 8, sd)]) * 2.0 - 1.0
    c, s = math.cos(angle), math.sin(angle)
    t = np.array([c * h[0] - s * h[1], s * h[0] + c * h[1]]) * pars['Tilt'] * (1.0 + max(scale - 1.0, 0.0))
    bv = min(max(1.0 - be / pars['Bevel'], 0.0), 1.0) if pars['Bevel'] > 0 else 0.0
    return t - np.asarray(bn, float) * bv * bv


def offsets(slope, pars):
    """Per-channel sample offsets (px) for R, G, B."""
    off = np.asarray(slope, float) * pars['Thickness'] * (1.0 - 1.0 / max(pars['Ior'], 1e-3))
    d = pars['Dispersion']
    return off * (1.0 - d), off, off * (1.0 + d)


def fresnel_rim(slope, pars):
    """Rim term (before Rimcolor): Fresnel x (F - F0) / (1 - F0); 0 for a flat pane, grows toward grazing."""
    n = np.array([-slope[0], -slope[1], 1.0])
    n /= np.linalg.norm(n)
    ior = pars['Ior']
    f0 = ((ior - 1.0) / (ior + 1.0)) ** 2
    F = f0 + (1.0 - f0) * (1.0 - n[2]) ** 5
    return pars['Fresnel'] * (F - f0) / max(1.0 - f0, 1e-4)


def spec(slope, pars):
    n = np.array([-slope[0], -slope[1], 1.0])
    n /= np.linalg.norm(n)
    a = math.radians(pars['Lightangle'])
    L = np.array([math.cos(a), math.sin(a), 1.0])
    L /= np.linalg.norm(L)
    hv = L + np.array([0.0, 0.0, 1.0])
    hv /= np.linalg.norm(hv)
    return pars['Specular'] * max(float(n @ hv), 0.0) ** pars['Shine']


def sample(img, x, y):
    """GLSL texture() with linear filtering and inputextenduv hold at pixel position (x, y) (centres at +0.5)."""
    h, w = img.shape[:2]
    fx, fy = x - 0.5, y - 0.5
    x0, y0 = math.floor(fx), math.floor(fy)
    tx, ty = fx - x0, fy - y0

    def px(i, j):
        return img[min(max(j, 0), h - 1), min(max(i, 0), w - 1)].astype(np.float64)
    a = px(x0, y0) * (1 - tx) + px(x0 + 1, y0) * tx
    b = px(x0, y0 + 1) * (1 - tx) + px(x0 + 1, y0 + 1) * tx
    return a * (1 - ty) + b * ty


def glass_shade(img, q, slope, pars):
    """RGBA the shader writes for a flying glass shard pixel whose source position is q = (x, y) px (before the
    crack glow, Back mix and Amount mix)."""
    oR, oG, oB = offsets(slope, pars)
    cg = sample(img, q[0] + oG[0], q[1] + oG[1])
    r = sample(img, q[0] + oR[0], q[1] + oR[1])[0]
    b = sample(img, q[0] + oB[0], q[1] + oB[1])[2]
    tint = np.asarray(pars['Glasstint'], float)
    rim = np.asarray(pars['Rimcolor'], float) * (fresnel_rim(slope, pars) + spec(slope, pars))
    rgb = np.array([r, cg[1], b]) * tint + rim
    return np.array([rgb[0], rgb[1], rgb[2], cg[3]])


def pars_from_comp(m):
    """Read the Glass page + Seed of a live shatter instance COMP (TD side helper for the live check)."""
    g = lambda n: float(getattr(m.par, n).eval())      # noqa: E731
    return {'Ior': g('Ior'), 'Thickness': g('Thickness'), 'Dispersion': g('Dispersion'), 'Tilt': g('Tilt'),
            'Bevel': g('Bevel'), 'Fresnel': g('Fresnel'), 'Specular': g('Specular'), 'Shine': g('Shine'),
            'Lightangle': g('Lightangle'), 'Seed': int(g('Seed')),
            'Glasstint': (g('Glasstintr'), g('Glasstintg'), g('Glasstintb')),
            'Rimcolor': (g('Rimcolorr'), g('Rimcolorg'), g('Rimcolorb'))}


def seed_pos(cx, cy, cell, jitter, seed):
    """SEEDS_GLSL seedPos(ivec2(cx, cy)) in px."""
    sd = int(seed)
    j = np.array([hsh(cx, cy, sd), hsh(cx, cy, sd + 77)]) - 0.5
    return (np.array([cx, cy], float) + 0.5 + j * jitter) * cell


def live_points(img, b0, b1, w, cells, jitter, pars, limit=40):
    """Expected out1 RGBA at each flying shard's centre (Bevel 0, Amount 1, Fade 0, centre far from cracks).
    img = in1 numpyArray, b0 / b1 = state / state_b1 numpyArray (32, 64, 4), w = picture width, cells = Cells.
    Returns [(x, y, rgba)] with (x, y) the out1 pixel (row 0 = bottom). Overlapping shards are not resolved: compare
    with a tolerance and report the share that matches (expect >= 90 %)."""
    h = img.shape[0]
    cols = int(cells)
    cell = w / max(1, cols)
    rows = int(math.ceil(h / max(1.0, w / max(1, cols))))
    out = []
    for i in range(min(cols * rows, 2048)):
        ty, tx = divmod(i, 64)
        alpha = float(b1[ty, tx, 3])
        if alpha <= 0.0:
            continue
        cx, cy = i % cols, i // cols
        s = seed_pos(cx, cy, cell, jitter, pars['Seed'])
        pos = s + b0[ty, tx, :2].astype(float)
        x, y = int(math.floor(pos[0])), int(math.floor(pos[1]))
        if not (0 <= x < img.shape[1] and 0 <= y < h):
            continue
        ang, sc = float(b1[ty, tx, 0]), 1.0 + float(b1[ty, tx, 2])
        r = np.array([x + 0.5, y + 0.5]) - pos
        c, sn = math.cos(ang), math.sin(ang)
        q = np.array([c * r[0] + sn * r[1], -sn * r[0] + c * r[1]]) / sc + s
        slope = glass_slope(i, ang, sc, 1e9, (0.0, 1.0), pars)
        out.append((x, y, glass_shade(img, q, slope, pars)))
        if len(out) >= limit:
            break
    return out
