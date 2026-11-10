# pop_caustics_logic - numpy mirror of POP_caustics (TC-30; builder builders/pop_caustics.py, doc
# docs/builds/pop_lane_h.md "TC-30"). One parallel light ray per Grid POP point -> refractor (water heightfield,
# glass sphere, luma slab) -> floor plane -> deposit histogram (np.add.at) = the expected Render TOP sums (T-112:
# additive 1-px points at texel centres are exact in 32F). Runs OUTSIDE TD (T-184). Same constants as the GLSL.
# ASCII only.
import math

import numpy as np

from pop_meshwarp_logic import lowbias, M32

REFRACTORS = ['water', 'sphere', 'slab']
REFRACTOR_LABELS = ['Water (heightfield of travelling sines)', 'Glass sphere (in + out refraction)',
                    'Slab (top height = Thickness x in1 luma)']
TAU = 6.283185307179586
# water: 4 directional sines (direction angle rad, frequency scale, amplitude, angular speed, phase)
WAVES = [(0.0, 1.0, 1.0, 1.0, 0.0), (1.1, 1.59, 0.5, 1.3, 1.7), (2.3, 2.44, 0.3, 1.7, 4.1),
         (3.7, 3.7, 0.2, 2.3, 2.9)]

DEFAULTS = {'refractor': 'water', 'ior': 1.33, 'lightangle': 0.0, 'time': 0.0, 'lightsize': 2.0, 'floorsize': 2.0,
            'floordepth': 1.0, 'side': 128, 'simres': 128, 'amp': 0.02, 'freq': 6.0, 'radius': 0.5,
            'thickness': 0.1, 'direct': 1.0, 'jitter': 0.0, 'salt': 0}


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


def refract(I, N, eta):
    """GLSL refract() for arrays (..., 3). Returns zeros on total internal reflection (as GLSL)."""
    d = (N * I).sum(-1, keepdims=True)
    k = 1.0 - eta * eta * (1.0 - d * d)
    t = eta * I - (eta * d + np.sqrt(np.maximum(k, 0.0))) * N
    return np.where(k < 0.0, 0.0, t)


def norm(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-30)


def ray_jitter(i, j, salt, amount):
    """GLSL rayJitter: lowbias((i * 747796405) ^ (j * 1597334677) ^ (salt * 2891336453 + 11)) -> 16-bit fields, offset
    in (-0.5, 0.5) x amount of a cell (x = low half, y = high half)."""
    u = np.uint64
    k = ((np.asarray(i, u) * u(747796405)) & M32) ^ ((np.asarray(j, u) * u(1597334677)) & M32) ^ \
        ((u(int(salt) & M32) * u(2891336453) + u(11)) & M32)
    h = lowbias(k)
    jx = ((h & u(0xFFFF)).astype(np.float64) + 0.5) / 65536.0 - 0.5
    jy = ((h >> u(16)).astype(np.float64) + 0.5) / 65536.0 - 0.5
    return jx * amount, jy * amount


def ray_origins(p):
    """Ray (i, j) of side x side starts in its cell of the Lightsize square (z = 0 plane, travelling down): the centre
    plus the hashed per-frame jitter (p['jitter'] of a cell, salt p['salt'] = the frame)."""
    s = int(p['side'])
    j, i = np.mgrid[0:s, 0:s]
    jx, jy = ray_jitter(i, j, p.get('salt', 0), float(p.get('jitter', 0.0)))
    x = ((i + 0.5 + jx) / s - 0.5) * p['lightsize']
    y = ((j + 0.5 + jy) / s - 0.5) * p['lightsize']
    return x.astype(np.float64), y.astype(np.float64)


def light_dir(p):
    a = math.radians(p['lightangle'])
    return np.array([math.sin(a), 0.0, -math.cos(a)])


def water_h(x, y, p):
    h = np.zeros_like(x)
    gx = np.zeros_like(x)
    gy = np.zeros_like(x)
    for ang, fs, a, w, ph in WAVES:
        dx, dy = math.cos(ang), math.sin(ang)
        k = p['freq'] * fs
        arg = k * (dx * x + dy * y) + w * p['time'] + ph
        h += a * np.sin(arg)
        c = a * k * np.cos(arg)
        gx += c * dx
        gy += c * dy
    return h * p['amp'], gx * p['amp'], gy * p['amp']


def luma(img):
    return img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722


def sample(L, u, v):
    """Bilinear sample of a 2D array (row 0 = bottom, TD convention), clamp to edge ('hold'), normalised u, v."""
    H, W = L.shape
    x = np.clip(u * W - 0.5, 0, W - 1)
    y = np.clip(v * H - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = x - x0, y - y0
    a = L[y0, x0] * (1 - fx) + L[y0, x1] * fx
    b = L[y1, x0] * (1 - fx) + L[y1, x1] * fx
    return a * (1 - fy) + b * fy


def hits(p, img=None):
    """-> qx, qy (floor hit, world units), ok (bool) per ray, arrays side x side (row j, column i)."""
    ox, oy = ray_origins(p)
    d = np.broadcast_to(light_dir(p), ox.shape + (3,)).copy()
    o = np.stack([ox, oy, np.zeros_like(ox)], -1)
    ok = np.ones(ox.shape, bool)
    fl = -p['floordepth']
    m = REFRACTORS.index(p['refractor']) if isinstance(p['refractor'], str) else int(p['refractor'])
    eta = 1.0 / p['ior']
    if m == 0:                                            # water surface around z = 0 (rays start on it)
        h, gx, gy = water_h(ox, oy, p)
        pos = np.stack([ox, oy, h], -1)
        n = norm(np.stack([-gx, -gy, np.ones_like(gx)], -1))
        t = refract(d, n, eta)
        ok &= t[..., 2] < -1e-6
    elif m == 1:                                          # glass sphere at the origin, rays start at z = 2 R above
        R = p['radius']
        o = o + np.array([0.0, 0.0, 2.0 * R])
        b = (o * d).sum(-1)
        c = (o * o).sum(-1) - R * R
        disc = b * b - c
        hit = disc > 0.0
        s = -b - np.sqrt(np.maximum(disc, 0.0))
        p1 = o + d * s[..., None]
        n1 = p1 / R
        t1 = refract(d, n1, eta)
        s2 = -2.0 * (t1 * p1).sum(-1)
        p2 = p1 + t1 * s2[..., None]
        n2 = p2 / R
        t2 = refract(t1, -n2, p['ior'])
        tir = (np.abs(t2).sum(-1) == 0.0)
        pos = np.where(hit[..., None], p2, o)
        t = np.where(hit[..., None], t2, d)
        ok &= ~(hit & tir)
        if p['direct'] < 0.5:
            ok &= hit
        ok &= t[..., 2] < -1e-6
    else:                                                 # slab: top z = Thickness x luma, flat bottom z = 0
        L = luma(img) if img is not None else np.zeros((2, 2))
        Hh, Wh = L.shape
        u = ox / p['lightsize'] + 0.5
        v = oy / p['lightsize'] + 0.5
        top = p['thickness'] * sample(L, u, v)
        ex, ey = 1.0 / Wh, 1.0 / Hh
        gx = p['thickness'] * (sample(L, u + ex, v) - sample(L, u - ex, v)) / (2.0 * ex * p['lightsize'])
        gy = p['thickness'] * (sample(L, u, v + ey) - sample(L, u, v - ey)) / (2.0 * ey * p['lightsize'])
        n = norm(np.stack([-gx, -gy, np.ones_like(gx)], -1))
        t1 = refract(d, n, eta)
        p1 = np.stack([ox, oy, top], -1)
        s = -top / np.minimum(t1[..., 2], -1e-6)
        pb = p1 + t1 * s[..., None]
        t = refract(t1, np.broadcast_to(np.array([0.0, 0.0, 1.0]), t1.shape), p['ior'])
        tir = (np.abs(t).sum(-1) == 0.0)
        ok &= ~tir & (t1[..., 2] < -1e-6)
        pos = pb
        ok &= t[..., 2] < -1e-6
    tz = np.where(np.abs(t[..., 2]) > 1e-6, t[..., 2], -1.0)
    s = (fl - pos[..., 2]) / tz
    q = pos + t * s[..., None]
    return q[..., 0], q[..., 1], ok


def deposit(p, img=None):
    """Expected deposit (simres x simres, row 0 = bottom): rays per texel of the Floorsize square."""
    qx, qy, ok = hits(p, img)
    r = int(p['simres'])
    fx = (qx / p['floorsize'] + 0.5) * r
    fy = (qy / p['floorsize'] + 0.5) * r
    ix, iy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    inside = ok & (ix >= 0) & (ix < r) & (iy >= 0) & (iy < r)
    D = np.zeros((r, r))
    np.add.at(D, (iy[inside], ix[inside]), 1.0)
    return D


def ball_focus(ior, R):
    """Paraxial back focal distance of a ball lens measured from its centre: f = n R / (2 (n - 1))."""
    return ior * R / (2.0 * (ior - 1.0))


def tone(D, exposure, persist_steps=1, persist=0.0):
    """Look tone: steady accumulation acc = D / (1 - Persist) (geometric sum), c = 1 - exp(-exposure x acc)."""
    acc = D * sum(persist ** k for k in range(persist_steps))
    return 1.0 - np.exp(-exposure * acc)
