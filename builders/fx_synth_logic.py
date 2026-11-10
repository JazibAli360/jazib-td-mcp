# fx_synth_logic - pure maths of the FX_synth modules (numpy references of the GLSL in builders/glsl/fx_synth_*.glsl).
# Offline tests: test/test_fx_synth.py. LIVE CHECKS compare TD readbacks against these (docs/builds/fx_synth.md).
# Images are float arrays (H, W, C) in TD texel order: row 0 = texel y 0 (bottom), the order of a TOP readback.
# Par dicts use the module par names; menus are given as their index (int). Change a shader -> change this file too.
# Offline / live-check helper only: the module builders never load it inside TD. ASCII only.
import math

import numpy as np

LUMA = np.array([0.2126, 0.7152, 0.0722])
TAU = 2.0 * math.pi


def lum(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def rise(x, e, s):
    """Soft step of the keys: s > 0 -> linear ramp of width s centred on e; s == 0 -> x >= e."""
    x = np.asarray(x, dtype=float)
    if s > 0:
        return np.clip((x - e) / s + 0.5, 0.0, 1.0)
    return (x >= e).astype(float)


def fract(x):
    return x - np.floor(x)


def gmod(x, y):
    """GLSL mod: x - y * floor(x / y) (result has the sign of y)."""
    return x - y * np.floor(x / y)


def hsv2rgb(h, s, v):
    h = np.asarray(h, dtype=float)
    k = np.clip(np.abs(fract(h[..., None] + np.array([0.0, 2.0 / 3.0, 1.0 / 3.0])) * 6.0 - 3.0) - 1.0, 0.0, 1.0)
    s = np.asarray(s, dtype=float)[..., None] if np.ndim(s) else s
    v = np.asarray(v, dtype=float)[..., None] if np.ndim(v) else v
    return v * (1.0 + (k - 1.0) * s)


def hue_rotate(c, deg):
    """Rodrigues rotation about the grey axis (exact at 0; r -> g -> b at +120)."""
    a = math.radians(deg)
    k = np.full(3, 1.0 / math.sqrt(3.0))
    return (c * math.cos(a) + np.cross(k, c) * math.sin(a)
            + k * (c @ k)[..., None] * (1.0 - math.cos(a)))


def pcg(v):
    v = np.asarray(v, dtype=np.uint64) & 0xFFFFFFFF
    s = (v * 747796405 + 2891336453) & 0xFFFFFFFF
    w = (((s >> ((s >> 28) + 4)) ^ s) * 277803737) & 0xFFFFFFFF
    return ((w >> 22) ^ w) & 0xFFFFFFFF


def hash01(a, b, c):
    """= GLSL h3(uvec3): float(pcg(a ^ pcg(b ^ pcg(c))) >> 8) / 16777215."""
    a, b, c = (np.asarray(x, dtype=np.uint64) & 0xFFFFFFFF for x in (a, b, c))
    return (pcg(a ^ pcg(b ^ pcg(c))) >> 8).astype(float) / 16777215.0


def bilinear(img, x, y):
    """GL linear sampling with clamp-to-edge; x, y in pixels (texel centres at i + 0.5)."""
    H, W = img.shape[:2]
    fx, fy = np.asarray(x, float) - 0.5, np.asarray(y, float) - 0.5
    x0, y0 = np.floor(fx), np.floor(fy)
    tx, ty = (fx - x0)[..., None], (fy - y0)[..., None]
    x0, y0 = x0.astype(int), y0.astype(int)
    xa, xb = np.clip(x0, 0, W - 1), np.clip(x0 + 1, 0, W - 1)
    ya, yb = np.clip(y0, 0, H - 1), np.clip(y0 + 1, 0, H - 1)
    top = img[ya, xa] * (1 - tx) + img[ya, xb] * tx
    bot = img[yb, xa] * (1 - tx) + img[yb, xb] * tx
    return top * (1 - ty) + bot * ty


def pixel_grid(W, H):
    """Texel centres (x, y) in pixels, arrays (H, W)."""
    return np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)


def to4(img):
    img = np.asarray(img, dtype=float)
    if img.shape[-1] == 4:
        return img
    return np.concatenate([img, np.ones(img.shape[:-1] + (1,))], -1)


# ------------------------------------------------------------------ colorize (AV-22 / DG-22)
CZ_MODES = ['channels', 'hue']
CZ_SOURCES = ['luma', 'rgb', 'red', 'green', 'blue']
CZ_FUNCTIONS = ['sine', 'triangle', 'saw', 'ramp']
CZ_OVERFLOWS = ['clip', 'wrap', 'fold', 'solarize']
CZ_DEFAULTS = {'Amount': 1.0, 'Mode': 0, 'Source': 0, 'Function': 0, 'Overflow': 0, 'Drive': 1.0, 'Bias': 0.0,
               'Solar': 0.5, 'Gainr': 1.0, 'Gaing': 1.0, 'Gainb': 1.0, 'Invert': 0, 'Phaser': 0.0, 'Phaseg': 0.33,
               'Phaseb': 0.67, 'Drift': 0.0, 'Huegain': 1.0, 'Huephase': 0.0, 'Sat': 1.0, 'Valuefollow': 0.0}


def cz_source(c, src):
    if src == 0:
        x = lum(c)[..., None].repeat(3, -1)
    elif src == 1:
        x = c[..., :3].copy()
    else:
        x = c[..., src - 2:src - 1].repeat(3, -1)
    return x


def cz_function(v, f):
    if f == 0:
        return 0.5 - 0.5 * np.cos(TAU * v)
    if f == 1:
        return 1.0 - np.abs(1.0 - 2.0 * fract(v))
    if f == 2:
        return fract(v)
    return v


def cz_overflow(y, o, T):
    if o == 0:
        return np.clip(y, 0.0, 1.0)
    if o == 1:
        return np.where((y < 0.0) | (y > 1.0), fract(y), y)
    if o == 2:
        return 1.0 - np.abs(1.0 - gmod(y, 2.0))
    return np.clip(np.where(y <= T, y, 2.0 * T - y), 0.0, 1.0)


def colorize(img, P, t=0.0):
    c = to4(img)
    p = dict(CZ_DEFAULTS, **P)
    if p['Amount'] <= 0:
        return c.copy()
    x = cz_source(c, int(p['Source']))
    if p['Invert']:
        x = 1.0 - x
    if int(p['Mode']) == 0:
        v = (x * np.array([p['Gainr'], p['Gaing'], p['Gainb']]) + np.array([p['Phaser'], p['Phaseg'], p['Phaseb']])
             + p['Drift'] * t)
        y = cz_function(v, int(p['Function']))
    else:
        xs = x[..., 0] if int(p['Source']) != 1 else lum(x)
        y = hsv2rgb(p['Huegain'] * xs + p['Huephase'] + p['Drift'] * t, p['Sat'],
                    1.0 + (xs - 1.0) * p['Valuefollow'])
    y = cz_overflow(y * p['Drive'] + p['Bias'], int(p['Overflow']), p['Solar'])
    out = np.concatenate([y, c[..., 3:4]], -1)
    return c + (out - c) * p['Amount']


# ------------------------------------------------------------------ bands (AV-23 / G24)
BD_SOURCES = ['luma', 'red', 'green', 'blue']
BD_FILLS = ['source', 'grey', 'rainbow', 'duotone']
BD_BACKS = ['source', 'black']
BD_DEFAULTS = {'Amount': 1.0, 'Source': 0, 'Bands': 8, 'Curve': 1.0, 'Offset': 0.0, 'Speed': 0.0, 'Wobble': 0.0,
               'Wobblerate': 0.5, 'Softness': 0.0, 'Fill': 2, 'Fillamt': 1.0, 'Background': 0, 'Linewidth': 0.0,
               'Lineopacity': 1.0, 'Major': 0, 'Majorwidth': 2.0, 'Liner': 1.0, 'Lineg': 1.0, 'Lineb': 1.0,
               'Huespan': 1.0, 'Hueoffset': 0.0, 'Colorar': 0.1, 'Colorag': 0.0, 'Colorab': 0.3, 'Colorbr': 1.0,
               'Colorbg': 0.75, 'Colorbb': 0.1}


def bd_signal(c, src, curve):
    s = lum(c) if src == 0 else c[..., src - 1]
    return np.power(np.maximum(s, 0.0), curve)


def bd_phase(p, t):
    return p['Offset'] + p['Speed'] * t + p['Wobble'] * math.sin(TAU * p['Wobblerate'] * t)


def bd_fill(k, phase, N, p, c, x0):
    kk = gmod(k, N)
    q = np.clip((k + 0.5 - phase) / N, 0.0, 1.0)
    f = int(p['Fill'])
    if f == 0:
        return np.clip(c[..., :3] * (q / np.maximum(x0, 1e-4))[..., None], 0.0, 1.0)
    if f == 1:
        return q[..., None].repeat(3, -1)
    if f == 2:
        return hsv2rgb(p['Hueoffset'] + p['Huespan'] * kk / N, 1.0, 1.0)
    A = np.array([p['Colorar'], p['Colorag'], p['Colorab']])
    B = np.array([p['Colorbr'], p['Colorbg'], p['Colorbb']])
    return A + (B - A) * q[..., None]


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def bands(img, P, t=0.0):
    c = to4(img)
    p = dict(BD_DEFAULTS, **P)
    if p['Amount'] <= 0:
        return c.copy()
    N = float(max(int(p['Bands']), 1))
    x0 = bd_signal(c, int(p['Source']), p['Curve'])
    ph = bd_phase(p, t)
    f0 = x0 * N + ph
    k = np.floor(f0)
    tt = f0 - k
    col = bd_fill(k, ph, N, p, c, x0)
    s = p['Softness']
    if s > 0:
        lo = bd_fill(k - 1, ph, N, p, c, x0)
        hi = bd_fill(k + 1, ph, N, p, c, x0)
        a = smoothstep(-s * 0.5, s * 0.5, tt)[..., None]
        b = smoothstep(1.0 - s * 0.5, 1.0 + s * 0.5, tt)[..., None]
        col = np.where((tt < 0.5)[..., None], lo + (col - lo) * a, col + (hi - col) * b)
    base = np.zeros_like(c[..., :3]) if int(p['Background']) == 1 else c[..., :3]
    filled = base + (col - base) * p['Fillamt']
    cov = bd_lines(c, p, N, f0)
    lc = np.array([p['Liner'], p['Lineg'], p['Lineb']])
    out = filled + (lc - filled) * (cov * p['Lineopacity'])[..., None]
    out = np.concatenate([out, c[..., 3:4]], -1)
    return c + (out - c) * p['Amount']


def bd_lines(c, p, N, f0):
    """Line coverage: distance (band units) to the nearest threshold / |grad f| (central differences, edge clamp)."""
    if p['Linewidth'] <= 0:
        return np.zeros(c.shape[:2])
    x = bd_signal(c, int(p['Source']), p['Curve'])
    xp = np.pad(x, 1, mode='edge')
    gx = (xp[1:-1, 2:] - xp[1:-1, :-2]) * N * 0.5
    gy = (xp[2:, 1:-1] - xp[:-2, 1:-1]) * N * 0.5
    g = np.sqrt(gx * gx + gy * gy)
    tt = fract(f0)
    dpx = np.minimum(tt, 1.0 - tt) / np.maximum(g, 1e-6)
    n = np.floor(f0 + 0.5)
    mj = int(p['Major'])
    w = np.full(x.shape, float(p['Linewidth']))
    if mj > 0:
        w = np.where(gmod(n, mj) == 0, w * p['Majorwidth'], w)
    return np.clip(w * 0.5 + 0.5 - dpx, 0.0, 1.0)


# ------------------------------------------------------------------ keyer (AV-24)
KY_KEYS = ['luma', 'chroma', 'shape', 'bluma', 'alpha', 'one']
KY_KEYB = ['none'] + KY_KEYS
KY_LOGIC = ['a', 'and', 'or', 'xor', 'a_not_b', 'multiply', 'a_gt_b']
KY_OPS = ['key', 'matte', 'alpha', 'add', 'multiply', 'min', 'max', 'difference', 'xor_bits', 'and_bits', 'or_bits']
KY_BSOURCES = ['colour', 'top']
KY_SHAPES = ['hwipe', 'vwipe', 'circle', 'diamond', 'rect', 'clock']
KY_DEFAULTS = {'Amount': 1.0, 'Keya': 0, 'Keyb': 0, 'Logic': 1, 'Invert': 0, 'Op': 0, 'Bsource': 0, 'Spill': 0.0,
               'Low': 0.5, 'High': 1.01, 'Soft': 0.05, 'Chromar': 0.0, 'Chromag': 1.0, 'Chromab': 0.0,
               'Tolerance': 0.15, 'Chromasoft': 0.1, 'Shape': 2, 'Position': 0.5, 'Shapesoft': 0.05, 'Centerx': 0.5,
               'Centery': 0.5, 'Angle': 0.0, 'Br': 0.0, 'Bg': 0.0, 'Bb': 0.0}


def cbcr(c):
    y = lum(c)
    return np.stack([(c[..., 2] - y) / 1.8556, (c[..., 0] - y) / 1.5748], -1)


def from_ycbcr(y, cb, cr):
    r = y + 1.5748 * cr
    b = y + 1.8556 * cb
    g = (y - 0.2126 * r - 0.0722 * b) / 0.7152
    return np.stack([r, g, b], -1)


def ky_shape_field(W, H, p):
    X, Y = pixel_grid(W, H)
    C = np.array([p['Centerx'] * W, p['Centery'] * H])
    a = math.radians(p['Angle'])
    ca, sa = math.cos(a), math.sin(a)

    def rot(dx, dy):
        return dx * ca + dy * sa, -dx * sa + dy * ca

    sh = int(p['Shape'])
    if sh == 0:
        return ((X / W - 0.5) * ca + (Y / H - 0.5) * sa) + 0.5
    if sh == 1:
        return (-(X / W - 0.5) * sa + (Y / H - 0.5) * ca) + 0.5
    dx, dy = X - C[0], Y - C[1]
    corners = [(0.0 - C[0], 0.0 - C[1]), (W - C[0], 0.0 - C[1]), (0.0 - C[0], H - C[1]), (W - C[0], H - C[1])]
    if sh == 2:
        R = max(math.hypot(*k) for k in corners)
        return np.sqrt(dx * dx + dy * dy) / max(R, 1e-6)
    if sh in (3, 4):
        rx, ry = rot(dx, dy)

        def metric(u, v):
            return (np.abs(u) + np.abs(v)) if sh == 3 else np.maximum(np.abs(u), np.abs(v))
        R = max(float(metric(*rot(*k))) for k in corners)
        return metric(rx, ry) / max(R, 1e-6)
    rx, ry = rot(dx, dy)
    return fract(np.arctan2(rx, ry) / TAU + 1.0)


def ky_keys(A, B, p):
    H, W = A.shape[:2]
    lA = lum(A)
    kl = rise(lA, p['Low'], p['Soft']) * (1.0 - rise(lA, p['High'], p['Soft']))
    K = np.array([[[p['Chromar'], p['Chromag'], p['Chromab']]]])
    d = np.linalg.norm(cbcr(A) - cbcr(K), axis=-1)
    kc = rise(d, p['Tolerance'], p['Chromasoft'])
    ks = 1.0 - rise(ky_shape_field(W, H, p), p['Position'], p['Shapesoft'])
    kb = rise(lum(B), p['Low'], p['Soft'])
    return [kl, kc, ks, kb, A[..., 3], np.ones((H, W))]


def ky_logic(a, b, lg):
    if lg == 0:
        return a
    if lg == 1:
        return np.minimum(a, b)
    if lg == 2:
        return np.maximum(a, b)
    if lg == 3:
        return np.abs(a - b)
    if lg == 4:
        return np.minimum(a, 1.0 - b)
    if lg == 5:
        return a * b
    return (a > b).astype(float)


def ky_bits(A, B, op):
    ua = np.floor(np.clip(A, 0, 1) * 255.0 + 0.5).astype(np.uint32)
    ub = np.floor(np.clip(B, 0, 1) * 255.0 + 0.5).astype(np.uint32)
    r = ua ^ ub if op == 8 else (ua & ub if op == 9 else ua | ub)
    return r.astype(float) / 255.0


def ky_spill(A, p):
    if p['Spill'] <= 0:
        return A
    v = cbcr(A)
    kd = cbcr(np.array([[[p['Chromar'], p['Chromag'], p['Chromab']]]]))[0, 0]
    n = np.linalg.norm(kd)
    if n < 1e-6:
        return A
    kd = kd / n
    proj = np.maximum(v @ kd, 0.0)
    v = v - p['Spill'] * proj[..., None] * kd
    rgb = from_ycbcr(lum(A), v[..., 0], v[..., 1])
    return np.concatenate([rgb, A[..., 3:4]], -1)


def keyer(img, P, bimg=None):
    """A = img, B = bimg (Bsource top) or the B colour. Returns rgba."""
    A0 = to4(img)
    p = dict(KY_DEFAULTS, **P)
    if p['Amount'] <= 0:
        return A0.copy()
    if int(p['Bsource']) == 1 and bimg is not None:
        B = to4(bimg)
    else:
        B = np.broadcast_to(np.array([p['Br'], p['Bg'], p['Bb'], 1.0]), A0.shape).copy()
    keys = ky_keys(A0, B, p)
    ka = keys[int(p['Keya'])]
    kb_i = int(p['Keyb'])
    k = ka if kb_i == 0 else ky_logic(ka, keys[kb_i - 1], int(p['Logic']))
    if p['Invert']:
        k = 1.0 - k
    A = ky_spill(A0, p)
    op = int(p['Op'])
    K = k[..., None]
    if op == 0:
        out = B + (A - B) * K
    elif op == 1:
        out = np.concatenate([K.repeat(3, -1), np.ones_like(K)], -1)
    elif op == 2:
        out = np.concatenate([A[..., :3] * K, K], -1)
    else:
        a3, b3 = A[..., :3], B[..., :3]
        if op == 3:
            C = a3 + b3
        elif op == 4:
            C = a3 * b3
        elif op == 5:
            C = np.minimum(a3, b3)
        elif op == 6:
            C = np.maximum(a3, b3)
        elif op == 7:
            C = np.abs(a3 - b3)
        else:
            C = ky_bits(a3, b3, op)
        out = np.concatenate([a3 + (C - a3) * K, A[..., 3:4]], -1)
    return A0 + (out - A0) * p['Amount']


# ------------------------------------------------------------------ ruttetra (AV-26)
RT_SIGNALS = ['luma', 'red', 'green', 'blue', 'inverse_luma']
RT_SCANS = ['horizontal', 'vertical']
RT_COLOURS = ['video', 'mono', 'heat', 'line']
RT_BACKS = ['black', 'input', 'transparent']
RT_DEFAULTS = {'Amount': 1.0, 'Lines': 96, 'Samples': 256, 'Width': 1.5, 'Intensity': 1.0, 'Blank': 0.0, 'Scan': 0,
               'Colour': 0, 'Monor': 0.35, 'Monog': 1.0, 'Monob': 0.45, 'Defxsrc': 0, 'Defx': 0.0, 'Defysrc': 0,
               'Defy': 0.12, 'Z': 0.0, 'Wave': 0.0, 'Wavefreq': 4.0, 'Wavespeed': 0.5, 'Jitter': 0.0,
               'Jitterrate': 0.0, 'Seed': 1, 'Rotate': 0.0, 'Scalex': 1.0, 'Scaley': 1.0, 'Shear': 0.0,
               'Offsetx': 0.0, 'Offsety': 0.0, 'Yaw': 0.0, 'Pitch': 0.0, 'Persp': 0.0, 'Glow': 0.6, 'Persist': 0.0,
               'Background': 0, 'Bgdim': 0.25}


def rt_signal(c, which):
    if which == 0:
        return lum(c)
    if which == 4:
        return 1.0 - lum(c)
    return c[..., which - 1]


def rt_camera(yaw, pitch):
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    return (np.array([cy, -sp * sy, -cp * sy]), np.array([0.0, cp, -sp]), np.array([sy, sp * cy, cp * cy]))


def rt_place(img, p, t, u, i):
    """Deflected + projected position (pixels) of sample u (0..1) on line i, and its colour (rgba sample).
    = fx_synth_rutt_vert.glsl place(). img = the source picture (H, W, 4); output res = input res."""
    H, W = img.shape[:2]
    a = W / float(H)
    L = float(max(int(p['Lines']), 1))
    u = np.asarray(u, float)
    i = np.asarray(i, float)
    v = (i + 0.5) / L
    if int(p['Scan']) == 0:
        uvx, uvy = u, v
        p0x, p0y = (u - 0.5) * a, v - 0.5
    else:
        uvx, uvy = v, u
        p0x, p0y = (v - 0.5) * a, u - 0.5
    col = bilinear(to4(img), uvx * W, uvy * H)
    px = p0x + p['Defx'] * rt_signal(col, int(p['Defxsrc']))
    py = p0y + p['Defy'] * rt_signal(col, int(p['Defysrc']))
    wv = p['Wave'] * np.sin(TAU * (p['Wavefreq'] * u + p['Wavespeed'] * t))
    if p['Jitter'] != 0:
        tick = int(math.floor(t * p['Jitterrate'])) if p['Jitterrate'] > 0 else 0
        jt = (hash01(i.astype(np.int64), tick, int(p['Seed'])) - 0.5) * p['Jitter']
    else:
        jt = 0.0
    if int(p['Scan']) == 0:
        py = py + wv + jt
    else:
        px = px + wv + jt
    z = p['Z'] * lum(col)
    px, py = px * p['Scalex'], py * p['Scaley']
    px = px + p['Shear'] * py
    ra = math.radians(p['Rotate'])
    px, py = px * math.cos(ra) - py * math.sin(ra), px * math.sin(ra) + py * math.cos(ra)
    px, py = px + p['Offsetx'], py + p['Offsety']
    c0, c1, c2 = rt_camera(p['Yaw'], p['Pitch'])
    rx = px * c0[0] + py * c1[0] + z * c2[0]
    ry = px * c0[1] + py * c1[1] + z * c2[1]
    rz = px * c0[2] + py * c1[2] + z * c2[2]
    w = 1.0 / np.maximum(1.0 - p['Persp'] / 3.0 * rz, 1e-4)
    sx, sy = rx * w, ry * w
    return np.stack([(sx / a + 0.5) * W, (sy + 0.5) * H], -1), col


def rt_lines(img, P, t=0.0):
    """All vertices: positions (Lines, Samples, 2) px and colours (Lines, Samples, 4)."""
    p = dict(RT_DEFAULTS, **P)
    L, S = int(p['Lines']), max(int(p['Samples']), 2)
    u = np.linspace(0.0, 1.0, S)
    U, I = np.meshgrid(u, np.arange(L))
    return rt_place(img, p, t, U, I)


def rt_expected_rows(H, lines):
    """Pixel rows (texel y) the undeflected horizontal lines cover: centre y = (i + 0.5) / Lines * H."""
    return [(i + 0.5) / lines * H for i in range(lines)]


# ------------------------------------------------------------------ scanimate (AV-27)
SC_SOURCES = ['input', 'text']
SC_COLOURS = ['ramp', 'logo']
SC_BACKS = ['black', 'input', 'transparent']
PALETTES = {                      # 4 stops: fresh -> oldest trail (sRGB-ish display values)
    'gold': [(1.0, 0.725, 0.012), (1.0, 0.267, 0.498), (0.792, 0.278, 0.914), (0.231, 0.075, 0.184)],
    'sunset': [(1.0, 0.97, 0.8), (1.0, 0.7, 0.15), (0.95, 0.2, 0.15), (0.35, 0.05, 0.4)],
    'electric': [(0.9, 1.0, 1.0), (0.1, 0.9, 1.0), (0.15, 0.25, 1.0), (0.6, 0.0, 0.8)],
    'chrome': [(1.0, 1.0, 1.0), (0.75, 0.8, 0.85), (0.3, 0.45, 0.65), (0.05, 0.08, 0.15)],
    'mono': [(1.0, 1.0, 1.0), (0.66, 0.66, 0.66), (0.33, 0.33, 0.33), (0.0, 0.0, 0.0)],
}
PALETTE_NAMES = ['gold', 'sunset', 'electric', 'chrome', 'mono']
SC_DEFAULTS = {'Amount': 1.0, 'Source': 1, 'Text': 'SCANIMATE', 'Key': 0.5, 'Keysoft': 0.1, 'Settle': 0.0,
               'Colour': 0, 'Palette': 1, 'Background': 0, 'Bend': 0.15, 'Bendfreq': 1.5, 'Bendspeed': 0.5,
               'Taper': 0.3, 'Zoom': 1.0, 'Fly': 0.2, 'Flyspeed': 0.25, 'Rotate': 0.0, 'Spin': 0.0, 'Decay': 0.93,
               'Trailzoom': 1.01, 'Trailx': 0.0, 'Traily': 0.0, 'Trailblur': 0.3, 'Bands': 0, 'Lines': 0,
               'Linegap': 0.4, 'Glow': 0.5, 'Reset': 0}


def palette(idx, x):
    stops = np.array(PALETTES[PALETTE_NAMES[int(idx)]])
    x = np.clip(np.asarray(x, float), 0.0, 1.0) * 3.0
    k = np.minimum(np.floor(x), 2).astype(int)
    f = (x - k)[..., None]
    return stops[k] + (stops[k + 1] - stops[k]) * f


def sc_warp_coords(W, H, p, t):
    """Inverse map of the warp pass: output texel centre -> source pixel coords (x, y) and a valid mask."""
    a = W / float(H)
    X, Y = pixel_grid(W, H)
    cx, cy = (X / W - 0.5) * a, Y / H - 0.5
    k = 1.0 - p['Settle']
    Z = p['Zoom'] * (1.0 + k * p['Fly'] * math.sin(TAU * p['Flyspeed'] * t))
    th = math.radians(p['Rotate'] + k * p['Spin'] * t)
    qx = (cx * math.cos(th) + cy * math.sin(th)) / Z
    qy = (-cx * math.sin(th) + cy * math.cos(th)) / Z
    s = 1.0 + k * p['Taper'] * 2.0 * qy
    b = k * p['Bend'] * a * np.sin(TAU * (p['Bendfreq'] * qy + p['Bendspeed'] * t))
    sx = (qx - b) / np.maximum(s, 1e-3)
    u, v = sx / a + 0.5, qy + 0.5
    ok = (s > 1e-3) & (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1)
    return u * W, v * H, ok


def sc_warp(src, P, t=0.0):
    """Warp pass: premultiplied logo colour + key (rgba16f state input)."""
    p = dict(SC_DEFAULTS, **P)
    s = to4(src)
    H, W = s.shape[:2]
    x, y, ok = sc_warp_coords(W, H, p, t)
    c = bilinear(s, x, y) * ok[..., None]
    m = rise(lum(c), p['Key'], p['Keysoft'])
    return np.concatenate([c[..., :3] * m[..., None], m[..., None]], -1)


def sc_trail_step(warp, prev, P):
    """One trail generation without zoom/shift/blur (point-wise part): premultiplied over of the decayed trail."""
    p = dict(SC_DEFAULTS, **P)
    d = prev * (p['Decay'] * (1.0 - p['Settle']))
    return warp + d * (1.0 - warp[..., 3:4])


def sc_colourise(tr, P):
    """Look pass colour of one trail texel (no glow, no raster lines)."""
    p = dict(SC_DEFAULTS, **P)
    a = np.clip(tr[..., 3], 0.0, 1.0)
    nb = int(p['Bands'])
    aq = np.ceil(a * nb - 1e-4) / nb if nb > 0 else a
    aq = np.maximum(aq, 0.0)
    col = palette(p['Palette'], 1.0 - a) * aq[..., None]
    if int(p['Colour']) == 1:
        w = (a ** 16)[..., None]
        col = col + (tr[..., :3] - col) * w
    return col


# ------------------------------------------------------------------ vfeedback (AV-28)
VF_KEYMODES = ['mix', 'luma_above', 'luma_below']
VF_MIRRORS = ['none', 'x', 'y', 'quad']
VF_EDGES = ['black', 'mirror', 'repeat', 'clamp']
VF_DEFAULTS = {'Amount': 1.0, 'Inject': 0.15, 'Keymode': 0, 'Key': 0.5, 'Keysoft': 0.1, 'Kick': 0.0, 'Gain': 1.0,
               'Delay': 0, 'Reset': 0, 'Zoom': 1.03, 'Rotate': 2.0, 'Shiftx': 0.0, 'Shifty': 0.0, 'Centerx': 0.5,
               'Centery': 0.5, 'Barrel': 0.0, 'Mirror': 0, 'Edge': 0, 'Blur': 0.3, 'Radius': 1.5, 'Gamma': 1.0,
               'Contrast': 1.05, 'Huestep': 3.0, 'Saturation': 1.0, 'Mask': 0.0, 'Maskpitch': 3.0, 'Noise': 0.0,
               'Autogain': 0.4, 'Target': 0.4, 'Seed': 1}
VF_IDENTITY = dict(VF_DEFAULTS, Inject=0.0, Zoom=1.0, Rotate=0.0, Blur=0.0, Contrast=1.0, Huestep=0.0, Autogain=0.0)


def vf_coords(W, H, p):
    """Sample position in the previous state for every output texel (mirror -> rotate/zoom/shift -> barrel)."""
    X, Y = pixel_grid(W, H)
    C = np.array([p['Centerx'] * W, p['Centery'] * H])
    mi = int(p['Mirror'])
    if mi in (1, 3):
        X = C[0] - np.abs(X - C[0])
    if mi in (2, 3):
        Y = C[1] - np.abs(Y - C[1])
    a = math.radians(p['Rotate'])
    dx, dy = X - C[0], Y - C[1]
    z = max(p['Zoom'], 1e-4)
    qx = C[0] + (math.cos(a) * dx + math.sin(a) * dy) / z - p['Shiftx']
    qy = C[1] + (-math.sin(a) * dx + math.cos(a) * dy) / z - p['Shifty']
    if p['Barrel'] != 0:
        nx, ny = (qx - C[0]) / (0.5 * H), (qy - C[1]) / (0.5 * H)
        k = 1.0 + p['Barrel'] * (nx * nx + ny * ny)
        qx, qy = C[0] + (qx - C[0]) * k, C[1] + (qy - C[1]) * k
    return qx, qy


def vf_edge(q, size, e):
    if e == 1:
        t = gmod(q, 2.0 * size)
        return np.minimum(t, 2.0 * size - t)
    if e == 2:
        return gmod(q, size)
    return np.clip(q, 0.5, size - 0.5)


def vf_tap(state, qx, qy, e):
    H, W = state.shape[:2]
    out = bilinear(state, vf_edge(qx, W, e), vf_edge(qy, H, e))
    if e == 0:
        inside = (qx >= 0) & (qx <= W) & (qy >= 0) & (qy <= H)
        out = out * inside[..., None]
    return out


def vf_colour(c, live, p, mean, X=None, noise=None):
    """Point-wise part of one generation (after the resample + blur) = fx_synth_vf_loop.glsl colour()."""
    c = c * p['Gain']
    c = np.power(np.maximum(c, 0.0), p['Gamma'])
    c = (c - 0.5) * p['Contrast'] + 0.5
    if p['Huestep'] != 0:
        c = hue_rotate(c, p['Huestep'])
    y = lum(c)[..., None]
    c = y + (c - y) * p['Saturation']
    if p['Mask'] > 0 and X is not None:
        st = gmod(np.floor((X - 0.5) / max(p['Maskpitch'], 1.0)), 3.0).astype(int)   # X = texel centre
        m = np.eye(3)[st] * 3.0
        c = c * (1.0 + (m - 1.0) * p['Mask'])
    if p['Autogain'] > 0:
        g = p['Target'] / max(mean, 0.02)
        c = c * (1.0 + (g - 1.0) * 0.2 * p['Autogain']) + (p['Target'] - mean) * 0.05 * p['Autogain']
    ll = lum(live)
    km = int(p['Keymode'])
    k = np.ones_like(ll) if km == 0 else (rise(ll, p['Key'], p['Keysoft']) if km == 1
                                           else 1.0 - rise(ll, p['Key'], p['Keysoft']))
    w = np.clip(p['Inject'] * k + p['Kick'], 0.0, 1.0)[..., None]
    c = c + (live[..., :3] - c) * w
    if p['Noise'] > 0 and noise is not None:
        c = c + (noise - 0.5) * p['Noise']
    return np.clip(c, 0.0, 1.0)


def vf_step(state, live, P, mean=None):
    """One full generation (no noise): resample + blur + colour. state/live (H, W, 4) -> new state rgba."""
    p = dict(VF_DEFAULTS, **P)
    s4, l4 = to4(state), to4(live)
    H, W = s4.shape[:2]
    if mean is None:
        mean = vf_mean(s4)
    e = int(p['Edge'])
    qx, qy = vf_coords(W, H, p)
    c = vf_tap(s4, qx, qy, e)[..., :3]
    if p['Blur'] > 0:
        r = p['Radius']
        acc = c.copy()
        for ox, oy in ((-r, 0), (r, 0), (0, -r), (0, r)):
            acc = acc + vf_tap(s4, qx + ox, qy + oy, e)[..., :3]
        c = c + (acc * 0.2 - c) * p['Blur']
    X, _Y = pixel_grid(W, H)
    rgb = vf_colour(c, l4, p, mean, X=X)
    return np.concatenate([rgb, l4[..., 3:4]], -1)


def mean_grid(W, H, n=64):
    """The stamp meter's sample texels: n x n grid of texel centres (= fx_synth_stamp.glsl)."""
    out = []
    for j in range(n):
        for i in range(n):
            out.append((min(int((i + 0.5) / n * W), W - 1), min(int((j + 0.5) / n * H), H - 1)))
    return out


def vf_mean(state, n=64):
    H, W = state.shape[:2]
    pts = mean_grid(W, H, n)
    xs = np.array([q[0] for q in pts])
    ys = np.array([q[1] for q in pts])
    return float(lum(state[ys, xs]).mean())


# ------------------------------------------------------------------ modulate (FX7a SX-12, Hydra modulate bank)
MD_MODES = ['modulate', 'scale', 'rotate', 'hue', 'pixelate', 'repeat', 'kaleid', 'scrollx', 'scrolly']
MD_WRAPS = ['repeat', 'mirror', 'hold', 'transparent']
MD_DEFAULTS = {'Amount': 1.0, 'Mode': 0, 'Multiple': 0.1, 'Offset': 0.0, 'Repeatx': 3.0, 'Repeaty': 3.0, 'Sides': 4.0,
               'Speed': 0.0, 'Wrap': 0, 'Bsource': 0, 'Noisescale': 1.0, 'Noisespeed': 0.2}


def md_coords(W, H, Bimg, P, t=0.0):
    """(st, uv) of modulate: st = output texel uv (H, W, 2); uv = where A is read (before wrap). Bimg is sampled at
    st (GL linear, clamp), any size."""
    p = dict(MD_DEFAULTS, **P)
    X, Y = pixel_grid(W, H)
    st = np.stack([X / W, Y / H], -1)
    hb, wb = Bimg.shape[:2]
    c = bilinear(to4(Bimg), st[..., 0] * wb, st[..., 1] * hb)
    mode, mul, ofs = int(p['Mode']), float(p['Multiple']), float(p['Offset'])
    if mode == 0:
        uv = st + (c[..., :2] - ofs) * mul
    elif mode == 1:
        f = 1.0 + ofs + mul * c[..., 0]
        f = np.where(np.abs(f) < 1e-3, np.where(f < 0, -1e-3, 1e-3), f)
        uv = (st - 0.5) / f[..., None] + 0.5
    elif mode == 2:
        a = ofs + mul * c[..., 0]
        d = st - 0.5
        uv = np.stack([np.cos(a) * d[..., 0] - np.sin(a) * d[..., 1], np.sin(a) * d[..., 0] + np.cos(a) * d[..., 1]],
                      -1) + 0.5
    elif mode == 3:
        uv = st + np.stack([c[..., 1] - c[..., 0], c[..., 2] - c[..., 1]], -1) * mul / np.array([W, H], float)
    elif mode == 4:
        cells = np.maximum(ofs + mul * c[..., :2], 1.0)
        uv = (np.floor(st * cells) + 0.5) / cells
    elif mode == 5:
        qx, qy = st[..., 0] * p['Repeatx'], st[..., 1] * p['Repeaty']
        qx = qx + (gmod(qy, 2.0) >= 1.0) + c[..., 0] * mul
        qy = qy + (gmod(qx, 2.0) >= 1.0) + c[..., 1] * mul
        uv = np.stack([fract(qx), fract(qy)], -1)
    elif mode == 6:
        d = st - 0.5
        r = np.hypot(d[..., 0], d[..., 1])
        n = max(float(p['Sides']), 1.0)
        a = gmod(np.arctan2(d[..., 1], d[..., 0]), 2.0 * math.pi / n)
        a = np.abs(a - math.pi / n)
        k = r * (1.0 + mul * c[..., 0])
        uv = 0.5 + np.stack([np.cos(a) * k, np.sin(a) * k], -1)
    elif mode == 7:
        uv = st + np.stack([mul * c[..., 0] + p['Speed'] * t, np.zeros(c.shape[:2])], -1)
    else:
        uv = st + np.stack([np.zeros(c.shape[:2]), mul * c[..., 0] + p['Speed'] * t], -1)
    am = float(p['Amount'])
    return st, st + (uv - st) * am


def modulate(img, P, bimg=None, t=0.0):
    """FX_synth modulate on img (H, W, 3|4); bimg = the modulator (None = img itself: Bsource self)."""
    p = dict(MD_DEFAULTS, **P)
    A = to4(img)
    if p['Amount'] <= 0:
        return A.copy()
    H, W = A.shape[:2]
    _st, uv = md_coords(W, H, A if bimg is None else bimg, p, t)
    wrap = int(p['Wrap'])
    out_side = (uv[..., 0] < 0) | (uv[..., 1] < 0) | (uv[..., 0] > 1) | (uv[..., 1] > 1)
    if wrap == 0:
        uv = fract(uv)
    elif wrap == 1:
        uv = 1.0 - np.abs(1.0 - gmod(uv, 2.0))
    o = bilinear(A, uv[..., 0] * W, uv[..., 1] * H)
    if wrap == 3:
        o = np.where(out_side[..., None], 0.0, o)
    return o
