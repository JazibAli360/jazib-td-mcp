# gen_pattern_logic - pure maths of the GEN_pattern modules (no TD, no numpy). The compute GLSL in
# builders/gen_pattern.py (shared head / mains) and builders/gen_pattern_<module>.py mirrors these functions line for
# line, so a live lane can predict pixels: `expect(module, U, x, y, W, H, src)` takes the uniform values read from the
# module's `fx` GLSL TOP (U = {name: (x, y, z, w)}) and returns the rgba the shader writes at pixel (x, y) (TD: y up).
# `uniforms(spec, pars, ...)` evaluates the uniform specs offline (tests, expected numbers in docs/builds/gen_pattern.md).
# Hash = lowbias32 on uint32 (T-108: GLSL uint == Python & 0xffffffff). ASCII only.
import math

U32 = 0xffffffff
TAU = 6.283185307179586
PI = 3.141592653589793


# ------------------------------------------------------------------ shared (GLSL: GLSL_COMMON + GLSL_GEN in gen_pattern.py)
def lb32(x):
    x &= U32
    x ^= x >> 16
    x = (x * 0x7feb352d) & U32
    x ^= x >> 15
    x = (x * 0x846ca68b) & U32
    x ^= x >> 16
    return x


def h2(cx, cy, s):
    return lb32(((cx & U32) * 1597334677 & U32) ^ lb32((cy & U32) ^ ((s * 2654435761) & U32))) / 4294967296.0


def h3(cx, cy, cz, s):
    return h2(cx, cy, (s ^ lb32(((cz & U32) + 0x9e3779b9) & U32)) & U32)


def fract(x):
    return x - math.floor(x)


def gmod(x, y):
    return x - y * math.floor(x / y)


def clamp(x, a, b):
    return a if x < a else (b if x > b else x)


def mix(a, b, t):
    return a + (b - a) * t


def smooth01(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def vnoise(x, y, s):
    ix, iy = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - ix, y - iy
    fx, fy = fx * fx * (3.0 - 2.0 * fx), fy * fy * (3.0 - 2.0 * fy)
    a, b = h2(ix, iy, s), h2(ix + 1, iy, s)
    c, d = h2(ix, iy + 1, s), h2(ix + 1, iy + 1, s)
    return mix(mix(a, b, fx), mix(c, d, fx), fy)


def fbm(x, y, s, octaves):
    """0..1 value-noise fbm; each octave rotated (0.8, 0.6) x 2.03 + (17.1, 31.7), own seed s + i."""
    v, a, n = 0.0, 0.5, 0.0
    for i in range(min(int(octaves), 8)):
        v += a * vnoise(x, y, (s + i) & U32)
        n += a
        x, y = (0.8 * x - 0.6 * y) * 2.03 + 17.1, (0.6 * x + 0.8 * y) * 2.03 + 31.7
        a *= 0.5
    return v / max(n, 1e-6)


def stroke(d, w, aa):
    """1 inside a line of width w around distance d = 0, linear 1 px edge (aa = pattern units per px)."""
    return clamp(0.5 + (w * 0.5 - d) / max(aa, 1e-9), 0.0, 1.0)


def band(u, duty, aa):
    """Square wave of period 1 in u, 'on' for |fract(u) - 0.5| < duty / 2, 1 px linear edge."""
    return clamp(0.5 + (duty * 0.5 - abs(fract(u) - 0.5)) / max(aa, 1e-9), 0.0, 1.0)


def rot(x, y, a):
    c, s = math.cos(a), math.sin(a)
    return c * x - s * y, s * x + c * y


def tri(k):
    return 1.0 - abs(fract(k * 0.5) * 2.0 - 1.0)


# Palettes (menu order = GLSL PAL_* table): 0 duo (Colour A -> B), 1 solid A, then IQ cosine palettes a + b cos(2pi(ck+d))
PALETTES = ['duo', 'solid', 'rainbow', 'fire', 'ice', 'gold', 'neon', 'sunset']
PAL_LABELS = ['Duo (A -> B)', 'Solid A', 'Rainbow', 'Fire', 'Ice', 'Gold', 'Neon', 'Sunset']
COSPAL = [  # (a, b, c, d) for palettes 2..7
    ((0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (1.0, 1.0, 1.0), (0.0, 0.33, 0.67)),
    ((0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (1.0, 0.7, 0.4), (0.0, 0.15, 0.2)),
    ((0.4, 0.6, 0.8), (0.4, 0.4, 0.2), (1.0, 1.0, 1.0), (0.0, 0.05, 0.1)),
    ((0.6, 0.45, 0.2), (0.4, 0.35, 0.2), (1.0, 1.0, 1.0), (0.0, 0.05, 0.15)),
    ((0.5, 0.5, 0.5), (0.5, 0.5, 0.5), (2.0, 1.0, 0.0), (0.5, 0.2, 0.25)),
    ((0.8, 0.5, 0.4), (0.2, 0.4, 0.2), (2.0, 1.0, 1.0), (0.0, 0.25, 0.25)),
]


_PM = {}


def palmap():
    """builders/palette_map_logic.py namespace (W1-B shared palette: pal_eval = pxPal, palette_stops, pal_rows)."""
    if not _PM:
        import os
        try:
            here = os.path.dirname(os.path.abspath(__file__))
        except NameError:                                   # exec'd from a string (TD, tests)
            here = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
        exec(open(os.path.join(here, 'palette_map_logic.py')).read(), _PM)
    return _PM


def pal(k, idx, ca, cb, U=None):
    i = int(idx + 0.5)
    if i >= 8 and U is not None and 'uPal' in U:           # 'shared' (PAL modules): pxPal(k)
        return tuple(palmap()['pal_eval'](U['uPal'], U['uPalCtl'], k))
    if i <= 0:
        t = tri(k)
        return tuple(mix(ca[j], cb[j], t) for j in range(3))
    if i == 1:
        return tuple(ca[:3])
    a, b, c, d = COSPAL[min(i - 2, len(COSPAL) - 1)]
    return tuple(a[j] + b[j] * math.cos(TAU * (c[j] * k + d[j])) for j in range(3))


BLENDS = ['replace', 'add', 'screen', 'multiply', 'difference', 'alpha']
BLEND_LABELS = ['Replace (bg colour)', 'Add', 'Screen', 'Multiply', 'Difference', 'Alpha out (premultiplied)']


class Ctx(object):
    """Per-pixel shared state, as the GLSL globals T STEP AGE ENV LEVEL SEED PX RES."""

    def __init__(self, U, W, H):
        d, b = U['uDrv'], U['uBeat']
        self.T, self.STEP, self.AGE = d[0], d[1], d[2]
        self.ENV = b[0] * math.exp(-d[2] / max(b[1], 1e-3))
        self.LEVEL = b[2] * d[3]
        self.SEED = int(b[3]) & U32
        self.W, self.H = float(W), float(H)
        self.PX = U['uSp'][0] / self.H if 'uSp' in U else 1.0 / self.H


def space(U, C, px, py):
    """Pixel centre (px, py) -> pattern coords: (P - centre) / H, rotated by -(Rotate + Rotspeed t), x Scale, + drift t."""
    sp, sp2 = U['uSp'], U['uSp2']
    x, y = (px - sp[2]) / C.H, (py - sp[3]) / C.H
    a = sp[1] + sp2[2] * C.T
    x, y = rot(x, y, -a)
    return x * sp[0] + sp2[0] * C.T, y * sp[0] + sp2[1] * C.T


def compose(U, C, v, k, src):
    """gen_main's colour + blend + Amount; src = input rgba at the pixel."""
    am, col = U['uAmt'], U['uCol']
    kk = k * am[3] + col[0] + col[1] * C.T
    pc = pal(kk, am[2], U['uCa'], U['uCb'], U)
    vc = clamp(v, 0.0, 1.0)
    mode = int(am[1] + 0.5)
    fg = [pc[j] * vc for j in range(3)]
    if mode == 0:
        o = [mix(U['uBg'][j], pc[j], vc) for j in range(3)] + [1.0]
    elif mode == 1:
        o = [src[j] + fg[j] for j in range(3)] + [src[3]]
    elif mode == 2:
        o = [1.0 - (1.0 - src[j]) * (1.0 - fg[j]) for j in range(3)] + [src[3]]
    elif mode == 3:
        o = [src[j] * mix(1.0, pc[j], vc) for j in range(3)] + [src[3]]
    elif mode == 4:
        o = [abs(src[j] - fg[j]) for j in range(3)] + [src[3]]
    else:
        o = fg + [vc]
    return [mix(src[j], o[j], am[0]) for j in range(4)]


def bilinear(img, u, v, W, H):
    """GL texture() of img (rows bottom first, img[y][x] = rgba) at uv with clamp-to-edge; uv already folded."""
    x, y = u * W - 0.5, v * H - 0.5
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - x0, y - y0
    def px(i, j):
        i = 0 if i < 0 else (W - 1 if i > W - 1 else i)
        j = 0 if j < 0 else (H - 1 if j > H - 1 else j)
        return img[j][i]
    a, b, c, d = px(x0, y0), px(x0 + 1, y0), px(x0, y0 + 1), px(x0 + 1, y0 + 1)
    return [mix(mix(float(a[n]), float(b[n]), fx), mix(float(c[n]), float(d[n]), fx), fy) for n in range(4)]


def mirror_uv(u):
    return 1.0 - abs(1.0 - gmod(u, 2.0))


def luma(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


# ------------------------------------------------------------------ generators: gen_<module>(U, C, q, P, src, tex) -> (v, k)
def gen_truchet(U, C, q, P, src, tex):
    m0, m1 = U['uM0'], U['uM1']
    tile, levels, sub, lw = int(m0[0] + 0.5), int(m0[1] + 0.5), m0[2], m0[3]
    gx, gy, s, lev = q[0], q[1], 1.0, 0
    for l in range(4):
        cx, cy = int(math.floor(gx)), int(math.floor(gy))
        if l + 1 >= levels:
            break
        if h3(cx, cy, l, C.SEED ^ 0x51) >= sub:
            break
        gx, gy, s, lev = gx * 2.0, gy * 2.0, s * 2.0, l + 1
    cx, cy = int(math.floor(gx)), int(math.floor(gy))
    fx, fy = gx - cx, gy - cy
    roll = ((int(C.STEP) * 0x9E37) + int(math.floor(C.T * m1[1]))) & U32
    o = 1 if h3(cx, cy, lev, C.SEED) < 0.5 else 0
    if h3(cx, cy, lev, C.SEED ^ lb32((roll + 1) & U32)) < m1[0]:
        o ^= 1
    w = lw * (1.0 + C.LEVEL) + C.ENV * lw
    aa = C.PX * s
    if o:
        c1, c2 = (0.0, 0.0), (1.0, 1.0)
    else:
        c1, c2 = (1.0, 0.0), (0.0, 1.0)
    d1 = math.hypot(fx - c1[0], fy - c1[1])
    d2 = math.hypot(fx - c2[0], fy - c2[1])
    if tile == 0:
        v = stroke(min(abs(d1 - 0.5), abs(d2 - 0.5)), w, aa)
    elif tile == 1:
        d = abs(fx - fy) * 0.70710678 if o else abs(fx + fy - 1.0) * 0.70710678
        v = stroke(d, w, aa)
    elif tile == 2:
        side = (fx - fy) if o else (fx + fy - 1.0)
        v = clamp(0.5 + side * 0.70710678 / aa, 0.0, 1.0)
    else:
        inside = clamp(0.5 + (0.5 - min(d1, d2)) / aa, 0.0, 1.0)
        par = ((cx + cy) & 1) ^ o
        v = inside if par == 1 else 1.0 - inside
    k = m1[2] * h3(cx, cy, lev + 32, C.SEED) + 0.2 * lev
    return v, k


def _op_layer(typ, freq, ang, ph, duty, qx, qy, C):
    aa = freq * C.PX
    if typ == 0:
        return band((qx * math.cos(ang) + qy * math.sin(ang)) * freq + ph, duty, aa)
    if typ == 1:
        return band(math.hypot(qx, qy) * freq + ph, duty, aa)
    rx, ry = rot(qx, qy, -ang)
    if typ == 2:
        gx, gy = fract(rx * freq + ph) - 0.5, fract(ry * freq) - 0.5
        return clamp(0.5 + (duty * 0.5 - math.hypot(gx, gy)) / max(aa, 1e-9), 0.0, 1.0)
    if typ == 3:
        a = band(rx * freq + ph, 0.5, aa)
        b = band(ry * freq, 0.5, aa)
        return a + b - 2.0 * a * b
    n = max(math.floor(freq + 0.5), 1.0)
    r = max(math.hypot(qx, qy), 1e-4)
    u = (math.atan2(qy, qx) / TAU + ang / TAU) * n + ph
    return band(u, duty, n / (TAU * r) * C.PX)


def gen_opart(U, C, q, P, src, tex):
    m0, m1 = U['uM0'], U['uM1']
    layers, comb, warp = int(m0[0] + 0.5), int(m0[1] + 0.5), int(m0[2] + 0.5)
    A = m0[3] * (1.0 + C.LEVEL)
    qx, qy = q
    if warp == 1:
        qx += A * 0.05 * math.sin(TAU * (m1[0] * qy + 0.25 * C.T))
    elif warp == 2:
        f = 1.0 - A * math.exp(-(qx * qx + qy * qy) / 0.09)
        qx, qy = qx * f, qy * f
    elif warp == 3:
        qx, qy = rot(qx, qy, A * PI * math.exp(-(qx * qx + qy * qy) / 0.09))
    duties = U['uM5']
    v = 0.0
    for i in range(min(max(layers, 1), 3)):
        L = U['uM%d' % (2 + i)]
        li = _op_layer(int(L[0] + 0.5), L[1], L[2], L[3] * C.T + C.ENV, duties[i], qx, qy, C)
        if i == 0:
            v = li
        elif comb == 0:
            v = v + li - 2.0 * v * li
        elif comb == 1:
            v = v * li
        elif comb == 2:
            v = abs(v - li)
        elif comb == 3:
            v = v + li
        else:
            v = max(v, li)
    if m1[1] > 0.5 and (int(C.STEP) & 1) == 1:
        v = 1.0 - v
    return v, v


def _fold_square(gx, gy):
    gx, gy = abs(gx), abs(gy)
    return (gy, gx) if gy > gx else (gx, gy)


def _fold_hex(ux, uy):
    lx, ly = 1.0, 1.7320508
    ax, ay = gmod(ux, lx) - lx * 0.5, gmod(uy, ly) - ly * 0.5
    bx, by = gmod(ux - lx * 0.5, lx) - lx * 0.5, gmod(uy - ly * 0.5, ly) - ly * 0.5
    gx, gy = (ax, ay) if ax * ax + ay * ay < bx * bx + by * by else (bx, by)
    r = math.hypot(gx, gy)
    a3 = abs(gmod(math.atan2(gy, gx) + PI / 6.0, PI / 3.0) - PI / 6.0)
    return r * math.cos(a3), r * math.sin(a3)


def gen_wallpaper(U, C, q, P, src, tex):
    m0, m1 = U['uM0'], U['uM1']
    mode, n, phs, bands = int(m0[0] + 0.5), max(int(m0[1] + 0.5), 1), m0[2], m0[3]
    theta, lw, rr = m1[0] + C.ENV * 0.2617994, m1[1] * (1.0 + C.LEVEL), m1[2]
    qx, qy = q
    if mode == 0:
        ph = phs * C.T + C.ENV
        s = 0.0
        for i in range(min(n, 16)):
            a = PI * i / n
            s += math.cos(TAU * (qx * math.cos(a) + qy * math.sin(a) + ph))
        v0 = 0.5 + 0.5 * s / n
        v = 0.5 + 0.5 * math.cos(TAU * v0 * bands) if bands > 0.0 else v0
        return v, v0
    if mode in (1, 3):
        gx, gy = _fold_square(qx - math.floor(qx) - 0.5, qy - math.floor(qy) - 0.5)
    else:
        gx, gy = _fold_hex(qx, qy)
    k = clamp(math.hypot(gx, gy) * 1.41421356, 0.0, 1.0)
    if mode in (1, 2):
        dx, dy = -math.sin(theta), math.cos(theta)
        ex, ey = gx - 0.5, gy
        return stroke(abs(ex * dy - ey * dx), lw, C.PX), k
    if mode == 3:
        d = min(abs(math.hypot(gx, gy) - rr), abs(math.hypot(gx - 0.5, gy - 0.5) - rr))
    else:
        d = min(abs(math.hypot(gx, gy) - rr), abs(math.hypot(gx - 0.5, gy - 0.28867513) - rr * 0.57735))
    return stroke(d, lw, C.PX), k


def gen_domainwarp(U, C, q, P, src, tex):
    m0, m1 = U['uM0'], U['uM1']
    depth, W, octv, evo = int(m0[0] + 0.5), m0[1] * (1.0 + C.LEVEL), int(m0[2] + 0.5), m0[3]
    bands, tint = m1[0], m1[1]
    s = C.SEED
    tt = C.T * evo + C.ENV
    F = lambda x, y: 2.0 * fbm(x, y, s, octv) - 1.0
    qx, qy = q
    wx, wy = F(qx + tt * 0.31, qy), F(qx + 5.2, qy + 1.3 + tt * 0.27)
    if depth >= 2:
        wx, wy = (F(qx + W * wx + 1.7 + tt * 0.15, qy + W * wy + 9.2),
                  F(qx + W * wx + 8.3, qy + W * wy + 2.8 + tt * 0.126))
    if depth >= 3:
        wx, wy = F(qx + W * wx + 3.1, qy + W * wy + 4.7), F(qx + W * wx + 6.9, qy + W * wy + 0.4)
    v = 0.5 + (fbm(qx + W * wx, qy + W * wy, s, octv) - 0.5) * m1[2]
    k = mix(v, clamp(math.hypot(wx, wy) * 0.70710678, 0.0, 1.0), tint)
    if bands > 0.0:
        v = 0.5 + 0.5 * math.sin(TAU * v * bands)
    return v, k


GYR_RANGE = [1.5, 3.0, 1.41421356, 13.0]


def _tpms(surf, x, y, z):
    sx, cx, sy, cy, sz, cz = math.sin(x), math.cos(x), math.sin(y), math.cos(y), math.sin(z), math.cos(z)
    if surf == 0:
        return sx * cy + sy * cz + sz * cx, cx * cy - sz * sx, -sx * sy + cy * cz
    if surf == 1:
        return cx + cy + cz, -sx, -sy
    if surf == 2:
        g = sx * sy * sz + sx * cy * cz + cx * sy * cz + cx * cy * sz
        gx = cx * sy * sz + cx * cy * cz - sx * sy * cz - sx * cy * sz
        gy = sx * cy * sz - sx * sy * cz + cx * cy * cz - cx * sy * sz
        return g, gx, gy
    return 3.0 * (cx + cy + cz) + 4.0 * cx * cy * cz, -3.0 * sx - 4.0 * sx * cy * cz, -3.0 * sy - 4.0 * cx * sy * cz


def gen_gyroid(U, C, q, P, src, tex):
    m0, m1 = U['uM0'], U['uM1']
    surf, render, cont, lw = int(m0[0] + 0.5), int(m0[1] + 0.5), m0[2], m0[3] * (1.0 + 2.0 * C.ENV)
    z = m1[0] + m1[1] * C.T + m1[2] * math.hypot(q[0], q[1]) * TAU
    iso, glow = m1[3] + C.LEVEL * 0.3, U['uM2'][0]
    R = GYR_RANGE[min(max(surf, 0), 3)]
    g, gx, gy = _tpms(surf, TAU * q[0], TAU * q[1], z)
    gpx = math.hypot(gx, gy) * TAU * C.PX
    gn = g / R
    if render == 0:
        c = (g - iso * R) / R * cont
        dpx = abs(c - math.floor(c + 0.5)) / max(cont / R * gpx, 1e-6)
        v = clamp(0.5 + (lw * 0.5 - dpx), 0.0, 1.0)
    elif render == 1:
        v = clamp(0.5 + (g - iso * R) / max(gpx, 1e-6), 0.0, 1.0)
    else:
        v = math.exp(-glow * abs(gn - iso))
    return v, 0.5 + 0.5 * gn


CYM_MODES = [(1, 2), (2, 3), (1, 4), (3, 4), (2, 5), (3, 5), (1, 6), (4, 5), (3, 7), (5, 6), (2, 7), (4, 7)]


def _plate(plate, n, m, x, y):
    if plate == 0:
        return math.cos(n * PI * x) * math.cos(m * PI * y) - math.cos(m * PI * x) * math.cos(n * PI * y)
    if plate == 1:
        return math.cos(n * PI * x) * math.cos(m * PI * y) + math.cos(m * PI * x) * math.cos(n * PI * y)
    if plate == 2:
        f = 0.0
        for j in range(3):
            a = j * TAU / 3.0
            d = x * math.cos(a) + y * math.sin(a)
            f += math.cos(n * PI * d) - math.cos(m * PI * d)
        return f * 0.6666667
    return 2.0 * math.cos(n * PI * math.hypot(x, y)) * math.cos(m * math.atan2(y, x))


def gen_cymatics(U, C, q, P, src, tex):
    m0, m1 = U['uM0'], U['uM1']
    plate, render, n, m = int(m0[0] + 0.5), int(m0[1] + 0.5), m0[2], m0[3]
    msrc, morph, width, grain = int(m1[0] + 0.5), m1[1], m1[2] * (1.0 + C.LEVEL), m1[3]
    gsize, wob = U['uM2'][0], U['uM2'][1]
    x, y = q
    if msrc == 1:
        st = int(C.STEP)
        i1 = ((st % 12) + 12) % 12
        i0 = (((st - 1) % 12) + 12) % 12
        w = smooth01(C.AGE / max(morph, 1e-3))
        f = mix(_plate(plate, CYM_MODES[i0][0], CYM_MODES[i0][1], x, y),
                _plate(plate, CYM_MODES[i1][0], CYM_MODES[i1][1], x, y), w)
    else:
        f = _plate(plate, n + wob * math.sin(C.T * 0.7), m + wob * math.sin(C.T * 0.53 + 1.0), x, y)
    k = 0.5 + 0.25 * f
    if render == 1:
        return 0.5 + 0.25 * f, k
    v = math.exp(-(f / max(width, 1e-4)) ** 2) * (1.0 + C.ENV)
    if grain > 0.0:
        gc = (int(math.floor(P[0] / max(gsize, 1.0))), int(math.floor(P[1] / max(gsize, 1.0))))
        g = 1.0 if h2(gc[0], gc[1], C.SEED ^ 0x77) < v else 0.0
        v = mix(v, g, grain)
    return v, k


def gen_split(U, C, q, P, src, tex):
    m0, m1, m2, m3 = U['uM0'], U['uM1'], U['uM2'], U['uM3']
    maxd, chance, fall, rmin = int(m0[0] + 0.5), m0[1], m0[2], m0[3]
    rmax, growth, agrow, bgrow = m1[0], m1[1], m1[2], m1[3]
    slide, gap, outl, render = m2[0], m2[1], m2[2], int(m2[3] + 0.5)
    cvar, jit, newg, hold = m3[0], m3[1], m3[2], m3[3]
    prog = growth + agrow * C.T + bgrow * (C.STEP + clamp(C.AGE / max(slide, 1e-3), 0.0, 1.0))
    L = maxd + hold
    cyc = math.floor(prog / L)
    loc = prog - cyc * L
    sd = (C.SEED + ((int(cyc) * 0x632BE5AB) & U32)) & U32
    rx0, ry0, rx1, ry1 = 0.0, 0.0, C.W, C.H
    node, depth, last = 1, 0, -10.0
    for d in range(min(maxd, 10)):
        if h3(node, d, 0, sd) >= chance * (1.0 if d == 0 else max(fall, 0.0) ** d):
            break
        birth = d + jit * h3(node, d, 1, sd)
        grow = clamp(loc - birth, 0.0, 1.0)
        if grow <= 0.0:
            break
        w, h = rx1 - rx0, ry1 - ry0
        ax = 0 if w > 1.3 * h else (1 if h > 1.3 * w else (0 if h3(node, d, 2, sd) < 0.5 else 1))
        e = smooth01(grow)
        ratio = mix(1.0, mix(rmin, rmax, h3(node, d, 3, sd)), e)
        last = birth
        if ax == 0:
            pos = rx0 + w * ratio
            if P[0] < pos:
                node, rx1 = node * 2, pos
            else:
                node, rx0 = node * 2 + 1, pos
        else:
            pos = ry0 + h * ratio
            if P[1] < pos:
                node, ry1 = node * 2, pos
            else:
                node, ry0 = node * 2 + 1, pos
        depth = d + 1
    e = min(min(P[0] - rx0, rx1 - P[0]), min(P[1] - ry0, ry1 - P[1]))
    g2 = gap * 0.5
    vf = clamp(0.5 + (e - g2), 0.0, 1.0)
    vo = vf * clamp(0.5 + (g2 + outl - e), 0.0, 1.0)
    v = vf if render == 0 else (vo if render == 1 else max(0.4 * vf, vo))
    v *= (1.0 + newg * (1.0 - clamp(loc - last, 0.0, 1.0))) * (1.0 + C.LEVEL)
    k = cvar * h3(node, depth, 4, sd) + (1.0 - cvar) * depth / max(maxd, 1)
    return v, k


def gen_barcode(U, C, q, P, src, tex):
    m0, m1, m2 = U['uM0'], U['uM1'], U['uM2']
    mode, chans, bmin, maxrun = int(m0[0] + 0.5), max(int(m0[1] + 0.5), 1), max(m0[2], 1.0), max(m0[3], 1.0)
    dens, rate, scroll, svar = m1[0] + C.ENV * 0.3, m1[1], m1[2] * (1.0 + C.LEVEL), m1[3]
    gapb, thr, binv, vert = m2[0], m2[1], m2[2], m2[3] > 0.5
    cellpx, cvar = max(U['uM3'][0], 1.0), U['uM3'][1]
    A, B = (P[1], P[0]) if vert else (P[0], P[1])
    WA, WB = (C.H, C.W) if vert else (C.W, C.H)
    s = C.SEED
    roll = (int(math.floor(C.T * rate)) + ((int(C.STEP) * 0x45D9F3B) & U32)) & U32
    if mode == 1:
        bh = cellpx
    else:
        bh = WB / chans
    band_i = int(math.floor(B / bh))
    bpos = B - band_i * bh
    inband = clamp(0.5 + (min(bpos, bh - bpos) - gapb * 0.5), 0.0, 1.0)
    dirn = -1.0 if (band_i & 1) == 1 else 1.0
    sp = scroll * (1.0 + svar * (2.0 * h2(band_i, 0, s ^ 0xB1) - 1.0))
    a = A + sp * C.T * dirn
    if mode == 1:
        cx = int(math.floor(a / cellpx))
        bit = h3(cx, band_i, 0, s ^ lb32(roll)) < dens
    elif mode == 2:
        xs = int(gmod(math.floor(a / bmin) * bmin + bmin * 0.5, WA))
        yc = int(clamp(math.floor((band_i + 0.5) * bh), 0.0, WB - 1.0))
        px_, py_ = (yc, xs) if vert else (xs, yc)
        bit = luma(tex(px_, py_)) > thr
    else:
        u = int(math.floor(a / bmin))
        seg = int(math.floor(u / 16.0))
        run = 1 + int(h3(seg, band_i, 7, s ^ lb32(roll)) * maxrun)
        cid = int(math.floor(float(u) / float(run)))
        bit = h3(cid, band_i, seg, s ^ lb32((roll + 1) & U32)) < dens
    if binv > 0.5 and (int(C.STEP) & 1) == 1:
        bit = not bit
    return (1.0 if bit else 0.0) * inband, cvar * h2(band_i, 3, s)


def _col_h(i, m0, m1, C):
    h = (m0[1] + m0[2] * math.sin(TAU * (i * m0[3] + C.T * m1[0]))
         + m1[1] * (h2(i, int(C.STEP), C.SEED ^ 0xC0) - 0.5) + C.LEVEL * (0.5 + 0.5 * h2(i, 9, C.SEED)) + C.ENV * 0.3)
    return h


def gen_columns(U, C, q, P, src, tex):
    m0, m1, m2 = U['uM0'], U['uM1'], U['uM2']
    mode, cnt = int(m0[0] + 0.5), max(int(U['uM3'][0] + 0.5), 1)
    width, fall, soft, haze = m2[0], m2[1], m2[2], m2[3]
    rows, led, unlit = max(int(U['uM3'][1] + 0.5), 1), U['uM3'][2], U['uM3'][3]
    cw = C.W / cnt
    i = int(math.floor(P[0] / cw))
    if mode == 0:
        s = 0.0
        for j in range(i - 2, i + 3):
            dx = abs(P[0] - (j + 0.5) * cw)
            core = math.exp(-max(dx - width * 0.5, 0.0) / max(fall, 1e-3))
            top = _col_h(j, m0, m1, C) * C.H
            vm = clamp((top - P[1]) / max(soft, 1.0) + 0.5, 0.0, 1.0)
            s += core * vm
        if haze > 0.0:
            s *= 1.0 - haze + haze * vnoise(P[0] / 80.0, P[1] / 120.0 - C.T * 0.5, C.SEED)
        return s, (i + 0.5) / cnt
    rh = C.H / rows
    r = int(math.floor(P[1] / rh))
    lx, ly = P[0] - (i + 0.5) * cw, P[1] - (r + 0.5) * rh
    vd = clamp(0.5 + (led * 0.5 * min(cw, rh) - math.hypot(lx, ly)), 0.0, 1.0)
    if mode == 1:
        lit = 1.0 if (r + 0.5) / rows < _col_h(i, m0, m1, C) else unlit
        return vd * lit, (r + 0.5) / rows
    b = 0.5 + 0.5 * math.sin(TAU * (i * m0[3] + r * m0[3] * 0.5 + C.T * m1[0]))
    return vd * b, (i + 0.5) / cnt


# ------------------------------------------------------------------ warps: <module>_src(U, C, P) -> [(u, v, weight)], gain
def kaleido2_src(U, C, P):
    m0, m1, m2 = U['uM0'], U['uM1'], U['uM2']
    mode, n, rotr, zoom = int(m0[0] + 0.5), max(m0[1], 1.0), m0[2] + m1[3] * C.T + C.ENV * 0.5235988, m0[3] * (1.0 + 0.5 * C.LEVEL)
    cx, cy, sx, sy = m1[0], m1[1], m2[0], m2[1]
    srot, lens, cshift, vig = m2[2], m2[3], U['uM3'][0], U['uM3'][1]
    asp = C.W / C.H
    px, py = (P[0] / C.W - cx) * asp, P[1] / C.H - cy
    r = math.hypot(px, py)
    gain = 1.0
    if mode == 0:
        sector = TAU / n
        th = math.atan2(py, px) - rotr
        t = abs(gmod(th, sector) - 0.5 * sector)
        s = (r * math.cos(t), r * math.sin(t))
    elif mode in (1, 2):
        a = rotr + (0.78539816 if mode == 2 else 0.0)
        ux, uy = rot(px, py, -a)
        ux, uy = ux * n, uy * n
        s = (abs(gmod(ux + 1.0, 2.0) - 1.0) / n, abs(gmod(uy + 1.0, 2.0) - 1.0) / n)
    else:
        ux, uy = rot(px, py, -rotr)
        hn = n * 0.5
        ux, uy = ux * hn, uy * hn
        if mode == 5:
            gx, gy = gmod(ux, 1.0) - 0.5, gmod(uy, 1.0) - 0.5
            ccx, ccy = ux - gx, uy - gy
            rr = max(abs(gx), abs(gy)) * 2.0
        else:
            lx, ly = 1.0, 1.7320508
            ax, ay = gmod(ux, lx) - lx * 0.5, gmod(uy, ly) - ly * 0.5
            bx, by = gmod(ux - lx * 0.5, lx) - lx * 0.5, gmod(uy - ly * 0.5, ly) - ly * 0.5
            gx, gy = (ax, ay) if ax * ax + ay * ay < bx * bx + by * by else (bx, by)
            ccx, ccy = ux - gx, uy - gy
            rr = math.hypot(gx, gy) * 2.0
        if mode == 3:
            t = abs(gmod(math.atan2(gy, gx), PI / 3.0) - PI / 6.0)
            g = math.hypot(gx, gy)
            s = (g * math.cos(t) / hn, g * math.sin(t) / hn)
        else:
            s = ((gx / max(lens, 1e-3) + ccx * cshift) / hn, (gy / max(lens, 1e-3) + ccy * cshift) / hn)
            gain = 1.0 - vig * smooth01(rr)
    s = rot(s[0] / max(zoom, 1e-3), s[1] / max(zoom, 1e-3), srot)
    return [(mirror_uv(sx + s[0] / asp), mirror_uv(sy + s[1]), 1.0)], gain


def droste_src(U, C, P):
    m0, m1, m2 = U['uM0'], U['uM1'], U['uM2']
    ratio, strands, twist, zs = max(m0[0], 1.0001), m0[1], m0[2], m0[3]
    rotr = m1[0] + m1[1] * C.T + C.LEVEL * 0.5
    R0, cx, cy, sx, sy = m1[2] * (1.0 + 0.3 * C.LEVEL), m1[3], m2[0], m2[1], m2[2]
    zx, zy = (P[0] - cx * C.W) / C.H, (P[1] - cy * C.H) / C.H
    r = max(math.hypot(zx, zy), 1e-6)
    wx, wy = math.log(r / max(R0, 1e-6)), math.atan2(zy, zx)
    L = math.log(ratio)
    al = math.atan(strands * L / TAU) * twist
    f = 1.0 / math.cos(al)
    wx, wy = f * (wx * math.cos(al) - wy * math.sin(al)), f * (wx * math.sin(al) + wy * math.cos(al))
    wx = gmod(wx - (zs * C.T + 0.25 * C.ENV) * L, L)
    wy += rotr
    rad = math.exp(wx) * R0
    ux, uy = rad * math.cos(wy), rad * math.sin(wy)
    return [(mirror_uv(sx + ux * C.H / C.W), mirror_uv(sy + uy), 1.0)], 1.0


def infzoom_src(U, C, P):
    m0, m1 = U['uM0'], U['uM1']
    n, step, zs, lrot = max(int(m0[0] + 0.5), 1), max(m0[1], 1.0001), m0[2], m0[3]
    cx, cy, fade, rots = m1[0], m1[1], m1[2], m1[3]
    f = fract(zs * C.T + 0.5 * C.ENV)
    asp = C.W / C.H
    px, py = (P[0] / C.W - cx) * asp, P[1] / C.H - cy
    out = []
    for i in range(min(n, 8)):
        e = (i + f) / n
        mag = step ** (i + f - n * 0.5)
        a = (i + f) * lrot + rots * C.T
        ux, uy = rot(px / mag, py / mag, a)
        w = max(math.sin(PI * e), 0.0) ** max(2.0 * fade, 1e-3)
        out.append((mirror_uv(cx + ux / asp), mirror_uv(cy + uy), w))
    return out, 1.0


GENS = {'truchet': gen_truchet, 'opart': gen_opart, 'wallpaper': gen_wallpaper, 'domainwarp': gen_domainwarp,
        'gyroid': gen_gyroid, 'cymatics': gen_cymatics, 'split': gen_split, 'barcode': gen_barcode,
        'columns': gen_columns}
def _fw_seg(px, py, ax, ay, bx, by):
    pax, pay, bax, bay = px - ax, py - ay, bx - ax, by - ay
    h = clamp((pax * bax + pay * bay) / max(bax * bax + bay * bay, 1e-6), 0.0, 1.0)
    dx, dy = pax - bax * h, pay - bay * h
    return dx * dx + dy * dy


def _fw_pt(d2, w):
    w2 = w * w
    return 0.0 if d2 > 256.0 * w2 else w2 / (d2 + w2)


def _fw_f(b, D, L):
    return (1.0 - math.exp(-D * b)) / (1.0 - math.exp(-D * L))


def fw_h(sid, n, seed):
    """Shell parameter n of shell id (one lowbias32)."""
    return lb32((sid ^ ((n * 0x9E3779B9) & U32) ^ ((seed * 0x85EBCA6B) & U32)) & U32) / 4294967296.0


def fw_slot(U, C, s, N):
    """(age s, shell id) of shell slot s: the youngest of its hit stamp, Auto launch and beat launch (1e9 = none)."""
    age, sid = 1e9, 0
    h = U['uH0'] if s < 4 else U['uH1']
    st = h[s % 4]
    if st > -999.0:
        a = C.T - st
        if 0.0 <= a < age:
            age, sid = a, ((int(math.floor(st * 64.0)) & U32) * 2654435761 & U32) ^ 0x1
    R = U['uM4'][3]
    if R > 0.0:
        K = math.floor(C.T * R)
        k = K - gmod(K - s, float(N))
        a = C.T - k / R
        if k >= 0.0 and a < age:
            age, sid = a, ((int(k) & U32) * 2246822519 & U32) ^ 0xA5A5A5
    Pb = U['uM5'][0]
    if Pb > 0.0:
        K = C.STEP
        k = K - gmod(K - s, float(N))
        a = C.AGE + (K - k) * Pb
        if k >= 0.0 and a < age:
            age, sid = a, ((int(k) & U32) * 3266489917 & U32) ^ 0x5EED
    return age, sid


def fw_shells(U, C):
    """Live shells: [(slot, age, id, type)] (offline tests: burst count per hit)."""
    N = int(clamp(int(U['uM0'][1] + 0.5), 1, 8))
    out = []
    for s in range(N):
        a, sid = fw_slot(U, C, s, N)
        if a > 1e8:
            continue
        typ = int(U['uM0'][0] + 0.5)
        if typ == 0:
            typ = 1 + min(int(fw_h(sid, 2, C.SEED) * 4.0), 3)
        Ls = max(U['uM2'][0], 0.05) * (1.6 if typ == 3 else 1.0)
        if a < max(U['uM1'][3], 0.0) + Ls:
            out.append((s, a, sid, typ))
    return out


def fw_dir(typ, j, M, rt, jo, jz, ct, orient, variety):
    """Spark j's ray direction x burst radius scale (ring: tilted ellipse; peony / willow: angle-sorted, z from a
    golden-ratio sequence = a projected sphere)."""
    if typ == 2:
        phi = rt + TAU * j / M
        return rot(math.cos(phi), ct * math.sin(phi), orient)
    phi = rt + TAU * (j + 0.5 + 0.8 * (fract(j * 0.7548777 + jo) - 0.5)) / M
    z = 2.0 * fract(j * 0.6180339887 + jz) - 1.0
    k = math.sqrt(max(1.0 - z * z, 0.0)) * (1.0 - variety * fract(j * 0.5698403 + jo))
    return k * math.cos(phi), k * math.sin(phi)


def fw_window(typ, M, rt, ct, orient, ex, ey, cut):
    """The shader's spark index window for a pixel at (ex, ey) from the burst origin cg: (j0, n). Sparks outside it
    are farther than `cut` (test: test_window_is_conservative)."""
    rho, th = math.hypot(ex, ey), math.atan2(ey, ex)
    dlt = math.asin(cut / rho) if rho > cut else 4.0
    j0, n = 0, M
    if typ == 2:
        if dlt / ct < PI:
            aa = th - orient
            uu = (math.atan2(math.sin(aa) / ct, math.cos(aa)) - rt) / TAU * M
            dj = dlt / ct / TAU * M
            j0 = int(math.floor(uu - dj))
            n = min(int(math.ceil(uu + dj)) - j0 + 1, M)
    elif dlt < PI:
        uu, dj = (th - rt) / TAU * M, dlt / TAU * M
        j0 = int(math.floor(uu - dj - 0.9))
        n = min(int(math.floor(uu + dj - 0.1)) - j0 + 1, M)
    return int(gmod(j0, M)), n


def gen_fireworks(U, C, q, P, src, tex):
    m0, m1, m2, m3, m4, m5 = U['uM0'], U['uM1'], U['uM2'], U['uM3'], U['uM4'], U['uM5']
    N, M = int(clamp(int(m0[1] + 0.5), 1, 8)), int(clamp(int(m0[2] + 0.5), 1, 128))
    H, w, L, D, rise = C.H, max(m3[0], 0.1), max(m2[0], 0.05), max(m2[1], 1e-3), max(m1[3], 0.0)
    px, py = P
    V, KK = 0.0, 0.0
    fh = lambda sid, n: fw_h(sid, n, C.SEED)
    for s in range(N):
        a, sid = fw_slot(U, C, s, N)
        if a > 1e8:
            continue
        typ = int(m0[0] + 0.5)
        if typ == 0:
            typ = 1 + min(int(fh(sid, 2) * 4.0), 3)
        Ls, Ds, G, Tr = L, D, m2[2], m2[3]
        if typ == 3:
            Ls, Ds, G, Tr = Ls * 1.6, Ds * 2.5, G * 1.6, Tr * 3.0
        if a >= rise + Ls:
            continue
        cx, cy = (0.5 + (fh(sid, 0) - 0.5) * m1[2]) * C.W, mix(m1[0], m1[1], fh(sid, 1)) * H
        kb, br = fh(sid, 5), m3[1] * (1.0 + C.ENV)
        if a < rise:
            u = a / rise
            ua = max(u - 0.12, 0.0)
            d2 = _fw_seg(px, py, cx, cy * (1.0 - (1.0 - ua) * (1.0 - ua)), cx, cy * (1.0 - (1.0 - u) * (1.0 - u)))
            I = _fw_pt(d2, w * 0.8) * br * m5[1]
            V += I
            KK += I * kb
            continue
        R = m0[3] * H * (0.75 + 0.5 * fh(sid, 6)) * (1.0 + C.LEVEL)
        b = a - rise
        u = b / Ls
        fade = 1.0 - u * u
        fb, gy = _fw_f(b, Ds, Ls), -0.5 * G * H * b * b
        b0 = max(b - Tr, 0.0)
        f0, gy0 = _fw_f(b0, Ds, Ls), -0.5 * G * H * b0 * b0
        lim = 1.4 * R + 16.0 * w
        if _fw_seg(px, py, cx, cy, cx, cy + gy) > lim * lim:
            continue
        dc2 = (px - cx) ** 2 + (py - cy) ** 2
        if m3[2] > 0.0:
            Rf = 0.12 * R + w
            if dc2 < 64.0 * Rf * Rf:
                I = m3[2] * br * math.exp(-b / 0.06) * Rf * Rf / (dc2 + Rf * Rf)
                V += I
                KK += I * kb
        if m3[3] > 0.0:
            Rg = R * fb + w
            x = 1.0 - dc2 / (Rg * Rg)
            if x > 0.0:
                I = m3[3] * 0.3 * fade * x * x
                V += I
                KK += I * kb
        rt, ct, jo, orient = fh(sid, 3) * TAU, 0.25 + 0.75 * fh(sid, 4), fh(sid, 7), fh(sid, 8) * PI
        twk = u > 1.0 - m4[0]
        tk = int(math.floor(b * 24.0))
        bf = br * fade

        def acc(I, j):
            if I <= 0.0:
                return 0.0, 0.0
            if twk and h2(j, tk, sid ^ 0x77) >= 0.5:
                I *= 0.15
            return I, I * (kb + m4[1] * (fract(j * 0.381966) - 0.5) + m4[2] * u)
        if typ == 4:
            Pn = max(M // 4, 2)
            ts = m5[2] * Ls
            fts, fc0, fc = _fw_f(ts, Ds, Ls), _fw_f(max(b0 - ts, 0.0), Ds, Ls), _fw_f(max(b - ts, 0.0), Ds, Ls)
            for p_ in range(Pn):
                z = 1.0 - (2.0 * p_ + 1.0) / Pn
                rr = math.sqrt(max(1.0 - z * z, 0.0))
                phi = p_ * 2.39996323 + rt
                sp = 1.0 - m5[3] * fract(p_ * 0.5698403 + jo)
                dx, dy = rr * math.cos(phi) * sp, rr * math.sin(phi) * sp
                if b < ts:
                    dV, dK = acc(_fw_pt(_fw_seg(px, py, cx + dx * R * f0, cy + dy * R * f0 + gy0,
                                                cx + dx * R * fb, cy + dy * R * fb + gy), w) * bf, p_ * 4)
                    V, KK = V + dV, KK + dK
                    continue
                bsx, bsy = cx + dx * R * fts, cy + dy * R * fts
                for ci in range(4):
                    ca = rt + ci * PI * 0.5 + p_
                    cex, cey = math.cos(ca) * 0.35 * R, math.sin(ca) * 0.35 * R
                    dV, dK = acc(_fw_pt(_fw_seg(px, py, bsx + cex * fc0, bsy + cey * fc0 + gy0,
                                                bsx + cex * fc, bsy + cey * fc + gy), w) * bf, p_ * 4 + ci)
                    V, KK = V + dV, KK + dK
            continue
        jz = fh(sid, 9)
        for j in range(M):                     # the shader loops only fw_window's index window (same sum: test)
            dx, dy = fw_dir(typ, j, M, rt, jo, jz, ct, orient, m5[3])
            dV, dK = acc(_fw_pt(_fw_seg(px, py, cx + dx * R * f0, cy + dy * R * f0 + gy0,
                                        cx + dx * R * fb, cy + dy * R * fb + gy), w) * bf, j)
            V, KK = V + dV, KK + dK
    return V, (KK / V if V > 1e-6 else 0.0)


GENS['fireworks'] = gen_fireworks


def _bk_nd(dx, dy, r, sh, blade):
    L = math.hypot(dx, dy)
    if sh == 0:
        return L / r
    n = 5.0 if sh == 1 else (6.0 if sh == 2 else 8.0)
    seg = TAU / n
    m = gmod(math.atan2(dy, dx) - blade, seg) - 0.5 * seg
    return L * math.cos(m) / (r * math.cos(0.5 * seg))


def gen_bokeh(U, C, q, P, src, tex):
    m0, m1, m2, m3, m4 = U['uM0'], U['uM1'], U['uM2'], U['uM3'], U['uM4']
    NL, sh = int(clamp(int(m0[0] + 0.5), 1, 6)), int(m2[2] + 0.5)
    H = C.H
    px, py = P
    g = m4[1] * mix(0.5, 1.0, py / H)
    V, KK = g, g * (1.0 - py / H)
    dx_, dy_ = math.cos(m3[1]), math.sin(m3[1])
    S = C.SEED
    for l in range(NL):
        z, fl = (l + 1.0) / NL, float(l)
        rc = m0[1] * mix(m0[2], 1.0, z)
        cs = 2.2 * rc
        swx, swy = m3[2] * cs * math.sin(C.T * 0.31 + fl * 1.3), m3[2] * cs * math.cos(C.T * 0.23 + fl * 2.1)
        sp = m3[0] * mix(0.25, 1.0, z) * C.T
        ux = (px / H - dx_ * sp - swx) / cs + fl * 17.31
        uy = (py / H - dy_ * sp - swy) / cs + fl * 9.73
        clx, cly = int(math.floor(ux)), int(math.floor(uy))
        soft = clamp(m1[2] + m1[3] * abs(z - m2[0]), 0.0, 1.0)
        lf = m1[0] * mix(1.0 - m1[1], 1.0, z) * (1.0 + C.ENV) * (1.0 + C.LEVEL)
        rmax = 0.45 * (1.0 + 0.3 * C.LEVEL)
        for oy in (-1, 0, 1):
            for ox in (-1, 0, 1):
                cx, cy = clx + ox, cly + oy
                bx, by = clamp(ux, cx + 0.15, cx + 0.85) - ux, clamp(uy, cy + 0.15, cy + 0.85) - uy
                if bx * bx + by * by > rmax * rmax:
                    continue
                h = lb32((((cx & U32) * 0x8da6b343) & U32) ^ (((cy & U32) * 0xd8163841) & U32)
                         ^ ((l * 0xcb1ab31f) & U32) ^ ((S * 0x165667b1) & U32))
                if (h & 0xffff) / 65536.0 >= m0[3]:
                    continue
                ctx = cx + 0.15 + 0.7 * ((h >> 16) & 0xff) / 255.0
                cty = cy + 0.15 + 0.7 * (h >> 24) / 255.0
                hb = lb32(h ^ 0x68e31da4)
                r = mix(0.25, 0.45, (hb & 0xff) / 255.0) * cs * H * (1.0 + 0.3 * C.LEVEL)
                ddx, ddy = (ux - ctx) * cs * H, (uy - cty) * cs * H
                if ddx * ddx + ddy * ddy > r * r:
                    continue
                nd = _bk_nd(ddx, ddy, r, sh, m2[3])
                inside = clamp((1.0 - nd) / max(soft, 1.0 / r), 0.0, 1.0)
                if inside <= 0.0:
                    continue
                inside = inside * inside * (3.0 - 2.0 * inside)
                tw = 1.0 - m3[3] * (0.5 + 0.5 * math.sin(TAU * (C.T * m4[0] * (0.5 + ((hb >> 8) & 0xff) / 255.0)
                                                               + ((hb >> 16) & 0xff) / 255.0)))
                I = lf * tw * inside * (1.0 + m2[1] * smooth01((nd - 0.6) / 0.4))
                V += I
                KK += I * (hb >> 24) / 255.0
    return V, (KK / V if V > 1e-6 else 0.0)


GENS['bokeh'] = gen_bokeh


def _bm_h(s, n, seed):
    return h2(s, n, seed ^ 0xBEA3)


def _bm_profile(x, style):
    if style == 1:
        return math.exp(-x * x) + 0.25 / (1.0 + x * x / 16.0)
    return 0.0 if x > 4.0 else math.exp(-2.0 * x * x)


def _bm_beam(U, px, py, ox, oy, ang, H, style):
    m2 = U['uM2']
    dx, dy = math.cos(ang), math.sin(ang)
    ddx, ddy = px - ox, py - oy
    al = ddx * dx + ddy * dy
    if al <= 0.0:
        return 0.0
    pe = abs(ddx * dy - ddy * dx)
    fall = math.exp(-al / max(m2[2] * H, 1.0))
    if style == 1:
        return fall * _bm_profile(pe / m2[1], 1)
    return fall * _bm_profile(pe / max(m2[1] + al * math.tan(m2[0]), 1e-3), 0)


def gen_beams(U, C, q, P, src, tex):
    m0, m1, m2, m3, m4, m5 = U['uM0'], U['uM1'], U['uM2'], U['uM3'], U['uM4'], U['uM5']
    mode, style, n = int(m0[0] + 0.5), int(m0[1] + 0.5), int(clamp(int(m0[2] + 0.5), 1, 32))
    H, W = C.H, C.W
    px, py = P
    st = int(C.STEP)
    S = C.SEED
    e = smooth01(C.AGE / max(m3[2], 1e-3))
    tilt = mix(m1[1] * (2.0 * _bm_h(st - 1, 1, S) - 1.0), m1[1] * (2.0 * _bm_h(st, 1, S) - 1.0), e)
    fan = mix(m1[0] * (0.4 + 0.6 * _bm_h(st - 1, 2, S)), m1[0] * (0.4 + 0.6 * _bm_h(st, 2, S)), e)
    br = m0[3] * (1.0 + C.ENV) * (1.0 + C.LEVEL)
    V, KK, Vf, Kf = 0.0, 0.0, 0.0, 0.0
    for i in range(n):
        fi = float(i)
        ki = (fi + 0.5) / n
        F = 0.0
        if mode == 3:
            y = (fi + 0.5) / n * H + m4[3] * H * math.sin(TAU * (px / W * m5[0] + C.T * m5[1] + fi * m2[3]))
            I = _bm_profile(abs(py - y) / m2[1], style)
        else:
            sw = m1[2] * math.sin(TAU * (C.T * m1[3] + fi * m2[3]))
            if mode == 0:
                m, j = (n + 1) // 2, i // 2
                fr = j / float(m - 1) - 0.5 if m > 1 else 0.0
                ang = 0.5 * PI - tilt + fr * fan + sw
                ox, oy = (0.5 - 0.5 * m3[0]) * W, m3[1] * H
                if i & 1:
                    ang, ox = PI - ang, (0.5 + 0.5 * m3[0]) * W
            elif mode == 1:
                ti = mix(m1[1] * (2.0 * _bm_h(st - 1, 10 + i, S) - 1.0), m1[1] * (2.0 * _bm_h(st, 10 + i, S) - 1.0), e)
                ang = -0.5 * PI + ti + sw
                ox, oy = (fi + 0.5) / n * W, m3[1] * H
            else:
                ang = TAU * fi / n + m5[2] * C.T + tilt
                ox, oy = 0.5 * W, 0.5 * H
            I = _bm_beam(U, px, py, ox, oy, ang, H, style)
            if not (mode == 2 and i > 0):
                w = 6.0 * m2[1]
                F = m3[3] * w * w / ((px - ox) ** 2 + (py - oy) ** 2 + w * w)
        V += I
        KK += I * ki
        Vf += F
        Kf += F * ki
    hz = mix(1.0, 0.25 + 1.5 * fbm(px / H * m4[1], py / H * m4[1] - C.T * m4[2], S, 3), m4[0]) if V > 1e-5 else 1.0
    V, KK = (V * hz + Vf) * br, (KK * hz + Kf) * br
    return V, (KK / V if V > 1e-6 else 0.0)


GENS['beams'] = gen_beams


def _mc_h(U, C, x, y, A):
    m0 = U['uM0']
    t = C.T * m0[1]
    n = int(clamp(int(m0[2] + 0.5), 1, 8))
    for i in range(1, n + 1):
        fi = float(i)
        sp = 0.5 + 0.17 * fi
        x, y = (x + A / fi * math.sin(y * (1.3 * fi) + t * sp + fi * 1.7),
                y + A / fi * math.sin(x * (1.3 * fi) - t * sp + fi * 2.3))
    return 0.25 * (math.sin(x) + math.sin(y)) + 0.5


def gen_moltenchrome(U, C, q, P, src, tex):
    m0, m1, m2, m3 = U['uM0'], U['uM1'], U['uM2'], U['uM3']
    A = m0[0] * (1.0 + m1[0] * math.sin(TAU * C.T * m1[1])) * (1.0 + C.LEVEL) + C.ENV * 0.5
    e = C.PX * 1.5
    h0, hx, hy = _mc_h(U, C, q[0], q[1], A), _mc_h(U, C, q[0] + e, q[1], A), _mc_h(U, C, q[0], q[1] + e, A)
    nx, ny, nz = -(hx - h0) / e * m0[3], -(hy - h0) / e * m0[3], 1.0
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / ln, ny / ln, nz / ln
    rx, ry, rz = 2.0 * nz * nx, 2.0 * nz * ny, 2.0 * nz * nz - 1.0
    rex, rey = rot(rx, ry, m2[1])
    env = mix(m3[1], m3[2], smooth01(0.5 + 0.5 * rey))
    nl = int(clamp(int(m1[2] + 0.5), 0, 4))
    for j in range(nl):
        yj = (j + 0.5) / nl * 1.6 - 0.8 + 0.3 * math.sin(TAU * C.T * m2[0] + j * 2.1)
        d = (rey - yj) / m1[3]
        env += 0.9 * math.exp(-d * d)
    lx, ly, lz = math.cos(TAU * C.T * m2[0] * 0.7), math.sin(TAU * C.T * m2[0] * 0.5), 1.5
    ll = math.sqrt(lx * lx + ly * ly + lz * lz)
    env += m2[3] * max((rx * lx + ry * ly + rz * lz) / ll, 0.0) ** m2[2]
    env += m3[0] * (1.0 - nz) ** 3.0
    return env, 0.5 + 0.5 * rey


GENS['moltenchrome'] = gen_moltenchrome


def _ca_cells(x, y, n, t, s):
    gx, gy = x * n, y * n
    cx, cy = math.floor(gx), math.floor(gy)
    f1, f2 = 1e9, 1e9
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            ccx, ccy = cx + dx, cy + dy
            wx, wy = int(gmod(ccx, n)), int(gmod(ccy, n))
            a = TAU * h2(wx, wy, s)
            r = 0.25 + 0.15 * h2(wx, wy, s ^ 0x55)
            px_, py_ = ccx + 0.5 + r * math.cos(a + t), ccy + 0.5 + r * math.sin(a + 1.3 * t)
            d = math.hypot(gx - px_, gy - py_)
            if d < f1:
                f1, f2 = d, f1
            elif d < f2:
                f2 = d
    return f2 - f1


def gen_caustic(U, C, q, P, src, tex):
    m0, m1, m2 = U['uM0'], U['uM1'], U['uM2']
    mode = int(m0[0] + 0.5)
    t = C.T * m1[3]
    S = C.SEED
    if mode == 0:
        n, F = int(clamp(int(m0[1] + 0.5), 1, 16)), max(int(m0[2] + 0.5), 1)
        hxx = hxy = hyy = 0.0
        norm = 1.0 / math.sqrt(n)
        for i in range(n):
            m = int(math.floor((2.0 * h2(i, 1, S) - 1.0) * F + 0.5))
            l = int(math.floor((2.0 * h2(i, 2, S) - 1.0) * F + 0.5))
            if m == 0 and l == 0:
                m = 1
            kx, ky = TAU * m, TAU * l
            kk = kx * kx + ky * ky
            sv = math.sin(kx * q[0] + ky * q[1] + t * TAU * (0.5 + 0.5 * h2(i, 3, S)) * math.sqrt(math.sqrt(kk) / TAU)
                          + TAU * h2(i, 4, S))
            a = norm / kk
            hxx -= a * sv * kx * kx
            hxy -= a * sv * kx * ky
            hyy -= a * sv * ky * ky
        D = m0[3] * (1.0 + C.LEVEL)
        det = (1.0 + D * hxx) * (1.0 + D * hyy) - D * D * hxy * hxy
        I = max(1.0 / (abs(det) + m1[0]) - m1[1], 0.0)
    else:
        nc = max(math.floor(m2[0] + 0.5), 1.0)
        e1 = _ca_cells(q[0], q[1], nc, t * TAU * 0.5, S)
        e2 = _ca_cells(q[0] + 0.37, q[1] + 0.71, nc * 2.0, -t * TAU * 0.7, S ^ 0x9B)
        I = math.exp(-e1 / m2[1]) + 0.5 * math.exp(-e2 / (m2[1] * 1.5))
    v = I * m1[2] * (1.0 + C.ENV) * (1.0 + C.LEVEL if mode == 1 else 1.0)
    return v, min(v, 2.0) * 0.5


GENS['caustic'] = gen_caustic
WARPS = {'kaleido2': kaleido2_src, 'droste': droste_src, 'infzoom': infzoom_src}
MODULES = list(GENS) + list(WARPS)


def expect(module, U, x, y, W, H, src=None):
    """rgba the module's shader writes at integer pixel (x, y); src = input image rows (bottom first, [y][x] rgba)
    or None (black). Output is clamped to 0..1 like an 8-bit TOP stores it."""
    tex = (lambda i, j: src[j][i]) if src is not None else (lambda i, j: (0.0, 0.0, 0.0, 0.0))
    c = [float(t) for t in tex(x, y)]
    if U['uAmt'][0] <= 0.0:
        return c
    C = Ctx(U, W, H)
    P = (x + 0.5, y + 0.5)
    if module in GENS:
        q = space(U, C, P[0], P[1])
        v, k = GENS[module](U, C, q, P, c, tex)
        o = compose(U, C, v, k, c)
    else:
        taps, gain = WARPS[module](U, C, P)
        acc, ws = [0.0] * 4, 0.0
        for u, v, w in taps:
            s = bilinear(src, u, v, W, H) if src is not None else [0.0] * 4
            acc = [acc[n] + s[n] * w for n in range(4)]
            ws += w
        o = [a / max(ws, 1e-6) for a in acc]
        o = [o[0] * gain, o[1] * gain, o[2] * gain, o[3]]
        o = [mix(c[n], o[n], U['uAmt'][0]) for n in range(4)]
    return [clamp(t, 0.0, 1.0) for t in o]


# ------------------------------------------------------------------ uniforms from pars (one spec, two readers)
# A uniform spec is [(name, [x, y, z, w])] of small expressions: {Par} = the par value, {Par#} = a menu's index,
# $t (module clock + Phase), $step, $age (s since the step), $level (rack audio level), $W, $H (output size).
# The builder turns them into TD expressions (td_expr), the tests / expected numbers evaluate them here (uniforms).
import re
_PAR = re.compile(r'\{(\w+)(#?)\}')
_TOK = re.compile(r'\$(\w+)')


def subst(expr, par_fn, tok_fn):
    return _TOK.sub(lambda mt: tok_fn(mt.group(1)), _PAR.sub(lambda mt: par_fn(mt.group(1), bool(mt.group(2))), expr))


def drive(beats, bpm, every, level):
    """Rack drive -> (step, age s, level). every 0 = beat steps off (step 0, age 1000 s)."""
    if every > 0:
        st = math.floor(beats / every)
        return st, (beats - st * every) * 60.0 / max(bpm, 1.0), level
    return 0.0, 1000.0, level


PAL_SRC_FALLBACK = 'rainbow'


def pal_stops(pars, src_names, mode_names=('gradient', 'steps', 'cycle')):
    """Shared palette stops from a PAL module's pars (= pal_callbacks.stops in TD)."""
    PM = palmap()
    src = src_names[int(pars['Palsource'])]
    rows = None
    if src == 'custom':
        rows = [t.split('@') for t in str(pars.get('Palcustom', '')).replace(',', ' ').split()]
    return PM['palette_stops']({'source': src, 'mode': mode_names[int(pars['Palmode'])],
                                'reverse': bool(pars.get('Palreverse', 0))}, rows, [])


def uniforms(spec, pars, W=1080, H=1920, t=1.0, beats=0.0, bpm=120.0, level=0.0, pal_src=None):
    """spec as above; pars = {Par: value} with menus as their index (presets use indices too). PAL modules: pass
    pal_src (the Palsource menu names); U['uPal'] = the 16 rows the pal CHOP holds."""
    st, age, lv = drive(beats, bpm, pars.get('Beatevery', 0), level)
    tok = {'t': t + pars.get('Phase', 0.0), 'step': st, 'age': age, 'level': lv, 'W': W, 'H': H, 'beats': beats,
           'bpm': bpm}
    rows = None
    if pal_src is not None and 'Palsource' in pars:
        stops = pal_stops(pars, pal_src)
        rows = palmap()['pal_rows'](stops)
        tok['palcount'] = float(len(stops))
    out = {}
    for name, exprs in spec:
        vals = []
        for e in exprs:
            py = subst(str(e), lambda n, idx: repr(float(pars[n])), lambda k: repr(float(tok[k])))
            vals.append(float(eval(py, {'__builtins__': {}, 'math': math, 'max': max, 'min': min, 'float': float,
                                        'int': int})))
        out[name] = tuple(vals)
    if rows is not None:
        out['uPal'] = rows
    return out


def sample_points(W, H, n=1000, seed=7):
    """The fixed pseudo-random pixel set used by the expected numbers (doc) and gen_pattern.stats() live."""
    import random
    rnd = random.Random(seed)
    return [(rnd.randrange(W), rnd.randrange(H)) for _ in range(n)]


def stats(pixels):
    """{mean_rgb, lit (share of luma > 0.5)} of a list of rgba."""
    n = float(len(pixels))
    return {'mean_rgb': [round(sum(p[c] for p in pixels) / n, 4) for c in range(3)],
            'lit': round(sum(luma(p) > 0.5 for p in pixels) / n, 4)}


def render(module, U, W, H, step=1, src=None):
    """Offline picture (list of rows of rgba) every `step` px; for tests and expected numbers."""
    return [[expect(module, U, x, y, W, H, src) for x in range(0, W, step)] for y in range(0, H, step)]
