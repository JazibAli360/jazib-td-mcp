# gen_points_logic - numpy mirror of the GEN_points shaders (builders/gen_points.py engine + gen_points_<module>.py).
# float64 here, float32 on the GPU. Used offline (test/test_gen_points.py) and live (gen_points.check_* run it inside
# TD on readbacks of the module's state / probe / render / acc). Mirrors, line for line:
#   GLSL_COMMON drive_globals (gen_pattern.py), px_common pxRnd / pxNoise / pxFbm / pxCurl (via px_logic np_*),
#   gen_points engine: rnd, packKA, ballPoint, project2d / project3d, tone, compose; module seed / step / place.
# Uniform values come as U = {name: (x, y, z, w)} (read live from the ops, or from uniforms() offline).
# ASCII only. numpy is imported lazily (TD has it; the module also loads without it for spec reads).
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else \
    '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
U32 = 0xFFFFFFFF
TAU = 6.283185307179586
PI = 3.141592653589793

_PX = {}
_GP = {}


def _np():
    import numpy
    return numpy


def px():
    """builders/px_logic.py (np_rnd, np_fbm, np_curl: the twins of px_common.glsl)."""
    if not _PX:
        with open(os.path.join(HERE, 'px_logic.py')) as fh:
            exec(compile(fh.read(), 'px_logic.py', 'exec'), _PX)
    return _PX


def gp():
    """builders/gen_pattern_logic.py (subst, drive, COSPAL, tri: the rack's maths)."""
    if not _GP:
        with open(os.path.join(HERE, 'gen_pattern_logic.py')) as fh:
            exec(compile(fh.read(), 'gen_pattern_logic.py', 'exec'), _GP)
    return _GP


# ------------------------------------------------------------------ uniforms offline (same spec language as GEN_pattern)
def uniforms(spec, pars, W=1080, H=1920, t=1.0, beats=0.0, bpm=120.0, level=0.0):
    """spec = [(name, [expr x4])]; tokens $t $step $age $level $W $H $RW $RH $side (gen_points.TOKENS)."""
    G = gp()
    st, age, lv = G['drive'](beats, bpm, pars.get('Beatevery', 0), level)
    q = pars.get('Quality', 1.0)
    tok = {'t': t + pars.get('Phase', 0.0), 'step': st, 'age': age, 'level': lv, 'W': W, 'H': H,
           'RW': max(1, int(W * q)), 'RH': max(1, int(H * q)), 'side': side_of(pars.get('Count', 65536))}
    out = {}
    for name, exprs in spec:
        vals = []
        for e in exprs:
            py = G['subst'](str(e), lambda n, idx: repr(float(pars[n])), lambda k: repr(float(tok[k])))
            vals.append(float(eval(py, {'__builtins__': {}, 'math': math, 'max': max, 'min': min, 'float': float,
                                        'int': int, 'abs': abs})))
        out[name] = tuple(vals)
    return out


def side_of(count):
    """State texture side for Count points (+1 reserved clock texel) == gen_points.SIDE_E."""
    return max(2, int(math.ceil(math.sqrt(max(int(count), 1) + 1))))


class Glob(object):
    """drive_globals() of GLSL_COMMON: T STEP AGE ENV LEVEL SEED (+ the engine's ASP, FR, NPTS)."""

    def __init__(self, U, asp=0.5625, fr=0, npts=0):
        d, b = U['uDrv'], U['uBeat']
        self.T, self.STEP, self.AGE = d[0], d[1], d[2]
        self.ENV = b[0] * math.exp(-d[2] / max(b[1], 1e-3))
        self.LEVEL = b[2] * d[3]
        self.SEED = int(b[3]) & U32
        self.ASP, self.FR, self.NPTS = asp, int(fr) & U32, int(npts)


def rnd(i, salt, g):
    """GLSL rnd(i, salt) = pxRnd(uint(i), salt + SEED * 7919u)."""
    np = _np()
    salt = (np.asarray(salt, dtype=np.uint64) + (g.SEED * 7919)) & U32
    i = np.asarray(i, dtype=np.uint64)
    h = px()['np_hash'](((i * 2654435761) & U32) + salt)
    return (h >> 8).astype(np.float64) / 16777216.0


def rnd3(i, salt, g):
    np = _np()
    return np.stack([rnd(i, salt, g), rnd(i, salt + 1, g), rnd(i, salt + 2, g)], -1)


def pack_ka(k, a):
    np = _np()
    return np.floor(np.clip(a, 0.0, 1.0) * 1023.0 + 0.5) + (k - np.floor(k)) * 0.999


def unpack(w):
    np = _np()
    return (w - np.floor(w)) / 0.999, np.floor(w) / 1023.0       # k, a


def ball_point(r):
    """Uniform point in the unit ball from 3 randoms (GLSL ballPoint)."""
    np = _np()
    z = 2.0 * r[..., 0] - 1.0
    ph = TAU * r[..., 1]
    s = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    return np.stack([s * np.cos(ph), s * np.sin(ph), z], -1) * np.cbrt(r[..., 2])[..., None]


def rot2(x, y, a):
    np = _np()
    c, s = np.cos(a), np.sin(a)
    return c * x - s * y, s * x + c * y


def lum(rgb):
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def pal(k, U):
    """gen_pattern pal() after ptpal's k * Spread + Offset + Huecycle * T: k -> rgb (n, 3)."""
    np = _np()
    G = gp()
    P = U['uPal']
    idx = int(P[0] + 0.5)
    k = np.asarray(k, dtype=np.float64)
    if idx <= 0:
        t = 1.0 - np.abs((k * 0.5 - np.floor(k * 0.5)) * 2.0 - 1.0)
        ca, cb = np.array(U['uCa'][:3]), np.array(U['uCb'][:3])
        return ca + (cb - ca) * t[..., None]
    if idx == 1:
        return np.broadcast_to(np.array(U['uCa'][:3]), k.shape + (3,)).copy()
    a, b, c, d = [np.array(v) for v in G['COSPAL'][min(idx - 2, len(G['COSPAL']) - 1)]]
    return a + b * np.cos(TAU * (c * k[..., None] + d))


def ptpal(k, U, g):
    P = U['uPal']
    return pal(k * P[1] + P[2] + P[3] * g.T, U)


# ------------------------------------------------------------------ projection (vertex stage) + count image
def project(kind, i, P, U, g):
    """Clip-space xy (n, 2) and a brightness factor (3D depth fade) for world points P (n, 3); visible mask."""
    np = _np()
    V, V2 = U['uView'], U['uView2']
    if kind == '2d':
        x, y = P[..., 0], P[..., 1]
        fold = max(int(U['uV2'][2] + 0.5), 1)
        if fold > 1:
            x, y = rot2(x, y, TAU * (np.asarray(i) % fold) / float(fold))
        ang = math.radians(V[1] + V2[0] * g.T)
        x, y = rot2(x, y, ang)
        x = x * V[0] + (V[2] - 0.5) * 2.0 * g.ASP
        y = y * V[0] + (V[3] - 0.5) * 2.0
        return np.stack([x / g.ASP, y], -1), np.ones(x.shape), np.ones(x.shape, bool)
    yaw, pit = math.radians(V[0] + V2[0] * g.T), math.radians(V[1])
    px_, pz = rot2(P[..., 0], P[..., 2], yaw)
    py, pz = rot2(P[..., 1], pz, pit)
    z = V[2] - pz
    vis = z > 1e-3
    zs = np.where(vis, z, 1.0)
    f = 1.0 / math.tan(math.radians(V[3]) * 0.5)
    fade = np.power(np.maximum(V[2] / zs, 0.0), V2[1])
    return np.stack([px_ * f / (g.ASP * zs), py * f / zs], -1), fade, vis


def count_image(ndc, w, W, H):
    """Additive 1-px points: weights w accumulated at the pixel each clip xy lands on (TD rows: y up)."""
    np = _np()
    fx = (ndc[:, 0] * 0.5 + 0.5) * W
    fy = (ndc[:, 1] * 0.5 + 0.5) * H
    ok = (fx >= 0) & (fx < W) & (fy >= 0) & (fy < H) & np.isfinite(fx) & np.isfinite(fy)
    img = np.zeros((H, W))
    np.add.at(img, (np.floor(fy[ok]).astype(int), np.floor(fx[ok]).astype(int)), w[ok])
    return img, ok


# ------------------------------------------------------------------ look (tone + compose) == look shader
def tone(v, U):
    """v (..., 4) accumulated rgba -> rgb, == tone() in the look pass."""
    np = _np()
    Lk, Lk2, Lk3 = U['uLk'], U['uLk2'], U['uLk3']
    n = (1.0 if U.get('uBg', (0, 0, 0, 0))[3] > 0.5 else Lk2[2] / max(Lk3[2], 1.0)) * (1.0 - Lk3[3])
    E = 2.0 ** Lk[1]
    r = v[..., :3] * n * E
    d = v[..., 3] * n
    m = int(Lk[0] + 0.5)
    if m == 1:
        col = r
    elif m == 2:
        avg = np.where(v[..., 3:4] > 0, v[..., :3] / np.where(v[..., 3:4] > 0, v[..., 3:4], 1.0), 0.0)
        b = np.log2(1.0 + d * E) * 0.25
        per = np.log2(1.0 + r) * 0.25
        col = per + (avg * b[..., None] - per) * min(max(Lk[3], 0.0), 1.0)
    else:
        col = 1.0 - np.exp(-r)
    return np.power(np.maximum(col, 0.0), 1.0 / max(Lk[2], 1e-3))


def compose(c, col, U, g):
    """Background rgba c, points rgb col -> output rgba (before the 8-bit store), == look main."""
    np = _np()
    col = col * (1.0 + U['uLk3'][1] * g.ENV)
    mode = int(U['uLk2'][3] + 0.5)
    o = np.array(c, dtype=np.float64)
    if mode == 0:
        o[..., :3] = np.array(U['uBg'][:3]) + col
        o[..., 3] = 1.0
    elif mode == 1:
        o[..., :3] = c[..., :3] + col
    elif mode == 2:
        o[..., :3] = 1.0 - (1.0 - c[..., :3]) * (1.0 - np.clip(col, 0.0, 1.0))
    elif mode == 3:
        o[..., :3] = np.maximum(c[..., :3], col)
    else:
        cc = np.clip(col, 0.0, 1.0)
        o[..., :3] = cc
        o[..., 3] = cc.max(-1)
    a = U['uLk3'][0]
    return c + (o - c) * a


# ------------------------------------------------------------------ density2d (FX5 G04)
D2_CEN = [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (0.0, 0.0), (-0.4, -0.5)]


def d2_params(U, g):
    np = _np()
    M0, M1, M2 = U['uM0'], U['uM1'], U['uM2']
    base = np.array([M0[1], M0[2], M0[3], M1[0]])
    return base + M1[1] * np.sin(TAU * M1[2] * g.T + np.array([0.0, 1.7, 3.1, 4.5])) + \
        (g.LEVEL + M2[1] * g.ENV) * np.array([0.15, -0.15, 0.075, -0.075])


def d2_ext(m, p):
    if m == 0:
        return max(1.0 + abs(p[2]), 1.0 + abs(p[3]))
    if m == 1:
        return 2.0
    if m == 2:
        return max(abs(p[3]) + 1.0, abs(p[2]) + 1.0)
    if m == 3:
        return 3.0
    return 1.05


def d2_map(m, x, y, p):
    np = _np()
    a, b, c, d = p
    if m == 0:
        return np.sin(a * y) + c * np.cos(a * x), np.sin(b * x) + d * np.cos(b * y)
    if m == 1:
        return np.sin(a * y) - np.cos(b * x), np.sin(c * x) - np.cos(d * y)
    if m == 2:
        return d * np.sin(a * x) - np.sin(b * y), c * np.cos(a * x) + np.cos(b * y)
    if m == 3:
        bb = b if abs(b) > 1e-3 else 1e-3
        return np.sin(x * y / bb) * y + np.cos(a * x - y), x + np.sin(y) / bb
    return x * x - y * y + a * x + b * y, 2.0 * x * y + c * x + d * y


def d2_seed(i, salt, U, g):
    np = _np()
    m = int(U['uM0'][0] + 0.5)
    p = d2_params(U, g)
    e = d2_ext(m, p)
    c = D2_CEN[min(m, 4)]
    x = c[0] + (rnd(i, salt, g) * 2.0 - 1.0) * e * 0.5
    y = c[1] + (rnd(i, salt + 1, g) * 2.0 - 1.0) * e * 0.5
    qx, qy = x, y
    for _k in range(12):
        qx, qy = x, y
        x, y = d2_map(m, x, y, p)
    dx, dy = x - qx, y - qy
    return np.stack([x, y, np.hypot(dx, dy), np.arctan2(dy, dx)], -1)


def density2d_seed(i, U, g):
    return d2_seed(i, 11, U, g)


def density2d_step(i, S, U, g, dt):
    np = _np()
    if dt <= 0:
        return S.copy()
    m = int(U['uM0'][0] + 0.5)
    p = d2_params(U, g)
    it = min(max(int(U['uM1'][3] + 0.5), 1), 64)
    x, y = S[:, 0].copy(), S[:, 1].copy()
    qx, qy = x, y
    with np.errstate(all='ignore'):
        for _k in range(it):
            qx, qy = x, y
            x, y = d2_map(m, x, y, p)
        r2 = x * x + y * y
    bad = ~(r2 < 1e8)
    resp = rnd(i, g.FR * 4 + 3, g) < U['uSt2'][0] * dt
    dx, dy = x - qx, y - qy
    out = np.stack([x, y, np.hypot(dx, dy), np.arctan2(dy, dx)], -1)
    sel = bad | resp
    if sel.any():
        out[sel] = d2_seed(np.asarray(i)[sel], g.FR * 4 + 7, U, g)
    return out


def density2d_place(i, S, U, g):
    np = _np()
    m = int(U['uM0'][0] + 0.5)
    p = d2_params(U, g)
    e = d2_ext(m, p)
    c = D2_CEN[min(m, 4)]
    sc = min(g.ASP, 1.0) * 0.95 / e
    P = np.stack([(S[:, 0] - c[0]) * sc, (S[:, 1] - c[1]) * sc, np.zeros(len(S))], -1)
    cb = int(U['uM2'][0] + 0.5)
    if cb == 0:
        k = S[:, 2] / e
    elif cb == 1:
        k = S[:, 3] / TAU + 0.5
    elif cb == 2:
        k = np.hypot(S[:, 0], S[:, 1]) / e
    else:
        k = rnd(i, 5, g)
    ok = (S[:, 0] * S[:, 0] + S[:, 1] * S[:, 1]) < 1e8
    return P, k, np.ones(len(S)), ok


# ------------------------------------------------------------------ attractor3d (FX5 G03)
# Centre / half-extent from long float64 RK4 runs (26 Oct, offline), rate = sim time per second for ~0.5 extents/s,
# hmax = largest stable RK4 step. Params (a, b, c) = the literature values (docs/research/FX7_gen_points_sources.md).
A3_SYSTEMS = ['lorenz', 'thomas', 'aizawa', 'halvorsen', 'dadras', 'chen', 'rossler', 'sprott', 'rabinovich',
              'fourwing']
A3_PAR = [(10.0, 28.0, 8.0 / 3.0), (0.208186, 0.0, 0.0), (0.95, 0.7, 0.6), (1.89, 0.0, 0.0), (3.0, 2.7, 1.7),
          (35.0, 3.0, 28.0), (0.2, 0.2, 5.7), (2.07, 1.79, 0.0), (0.14, 0.10, 0.0), (0.2, 0.01, -0.4)]
A3_CEN = [(0.0, 0.0, 24.5), (0.0, 0.0, 0.0), (0.0, 0.0, 0.74), (-2.9, -2.9, -2.9), (1.0, -0.5, 0.26),
          (0.5, 0.5, 25.5), (1.1, -1.45, 9.76), (0.69, 0.0, 0.0), (-0.58, 0.0, 0.65), (0.0, 0.0, -0.14)]
A3_EXT = [21.0, 3.8, 1.42, 9.2, 10.0, 21.3, 10.0, 1.0, 2.2, 2.0]
A3_RATE = [0.14, 2.5, 0.37, 0.15, 0.6, 0.09, 0.7, 0.9, 0.54, 5.0]
A3_HMAX = [0.01, 0.1, 0.02, 0.01, 0.01, 0.003, 0.02, 0.02, 0.01, 0.05]


def a3_f(s, x, y, z, k):
    np = _np()
    a, b, c = k
    if s == 0:
        return a * (y - x), x * (b - z) - y, x * y - c * z
    if s == 1:
        return np.sin(y) - a * x, np.sin(z) - a * y, np.sin(x) - a * z
    if s == 2:
        return ((z - b) * x - 3.5 * y, 3.5 * x + (z - b) * y,
                c + a * z - z * z * z / 3.0 - (x * x + y * y) * (1.0 + 0.25 * z) + 0.1 * z * x * x * x)
    if s == 3:
        return (-a * x - 4.0 * y - 4.0 * z - y * y, -a * y - 4.0 * z - 4.0 * x - z * z,
                -a * z - 4.0 * x - 4.0 * y - x * x)
    if s == 4:
        return y - a * x + b * y * z, c * y - x * z + z, 2.0 * x * y - 9.0 * z
    if s == 5:
        return a * (y - x), (c - a) * x - x * z + c * y, x * y - b * z
    if s == 6:
        return -y - z, x + a * y, b + z * (x - c)
    if s == 7:
        return y + a * x * y + x * z, 1.0 - b * x * x + y * z, x - x * x - y * y
    if s == 8:
        return y * (z - 1.0 + x * x) + b * x, x * (3.0 * z + 1.0 - x * x) + b * y, -2.0 * z * (a + x * y)
    return a * x + y * z, b * x + c * y - x * z, -z - x * y


def a3_sys(U):
    return min(max(int(U['uM0'][0] + 0.5), 0), len(A3_SYSTEMS) - 1)


def a3_par(s, U, g):
    M0, M2 = U['uM0'], U['uM2']
    f = 1.0 + 0.05 * (g.LEVEL + M2[2] * g.ENV)
    return tuple(A3_PAR[s][j] * f + M0[1 + j] for j in range(3))


def a3_seed(i, salt, U, g):
    np = _np()
    s = a3_sys(U)
    r = rnd3(i, salt, g)
    M1 = U['uM1']
    u = ball_point(r) * M1[2] if M1[3] < 0.5 else (r * 2.0 - 1.0) * M1[2]
    p = np.array(A3_CEN[s]) + u * A3_EXT[s]
    return np.concatenate([p, np.zeros((len(p), 1))], -1)


def attractor3d_seed(i, U, g):
    return a3_seed(i, 21, U, g)


def attractor3d_step(i, S, U, g, dt):
    np = _np()
    if dt <= 0:
        return S.copy()
    s = a3_sys(U)
    k = a3_par(s, U, g)
    M1 = U['uM1']
    Hh = dt * A3_RATE[s] * M1[0]
    n = min(max(max(int(M1[1] + 0.5), int(math.ceil(abs(Hh) / A3_HMAX[s]))), 1), 32)
    h = Hh / n
    x, y, z = S[:, 0].copy(), S[:, 1].copy(), S[:, 2].copy()
    with np.errstate(all='ignore'):
        for _j in range(n):
            k1 = a3_f(s, x, y, z, k)
            k2 = a3_f(s, x + 0.5 * h * k1[0], y + 0.5 * h * k1[1], z + 0.5 * h * k1[2], k)
            k3 = a3_f(s, x + 0.5 * h * k2[0], y + 0.5 * h * k2[1], z + 0.5 * h * k2[2], k)
            k4 = a3_f(s, x + h * k3[0], y + h * k3[1], z + h * k3[2], k)
            x = x + h / 6.0 * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
            y = y + h / 6.0 * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
            z = z + h / 6.0 * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2])
        c = np.array(A3_CEN[s])
        d2 = (x - c[0]) ** 2 + (y - c[1]) ** 2 + (z - c[2]) ** 2
    bad = ~(d2 < 400.0 * A3_EXT[s] ** 2)
    resp = rnd(i, g.FR * 4 + 1, g) < U['uSt2'][0] * dt
    out = np.stack([x, y, z, S[:, 3] + dt], -1)
    sel = bad | resp
    if sel.any():
        out[sel] = a3_seed(np.asarray(i)[sel], g.FR * 4 + 2, U, g)
    return out


def attractor3d_place(i, S, U, g):
    np = _np()
    s = a3_sys(U)
    c, e = np.array(A3_CEN[s]), A3_EXT[s]
    M2, M3 = U['uM2'], U['uM3']
    W = M2[1]
    P = (S[:, :3] - c) / e * W
    cb = int(M2[0] + 0.5)
    if cb == 0:
        v = a3_f(s, S[:, 0], S[:, 1], S[:, 2], a3_par(s, U, g))
        k = np.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) * A3_RATE[s] / e * M2[3]
    elif cb == 1:
        k = S[:, 3] * 0.1 * M2[3]
    elif cb == 2:
        k = (P[:, 2] / max(W, 1e-6)) * 0.5 + 0.5
    else:
        k = rnd(i, 5, g)
    a = np.clip(S[:, 3] / M3[0], 0.0, 1.0) if M3[0] > 0 else np.ones(len(S))
    ok = (P * P).sum(-1) < 1e6
    return P, k, a, ok


# ------------------------------------------------------------------ streamlines (FX5 G01)
def sl_field(p, U, g, img=None):
    """Field at world points p (n, 2): curl / angle / snapped angle / image contours / gradient / vortex / rain."""
    np = _np()
    X = px()
    M0, M1, M2, M3 = U['uM0'], U['uM1'], U['uM2'], U['uM3']
    f = int(M0[0] + 0.5)
    fr = M0[1]
    oct_ = min(max(int(M0[2] + 0.5), 1), 4)
    te = g.T * M0[3]
    q3 = np.stack([p[:, 0] * fr, p[:, 1] * fr, np.full(len(p), 0.37)], -1)
    cn = X['np_curl'](q3, te, oct_)[:, :2]
    if f == 0:
        v = cn
    elif f in (1, 2):
        a = (X['np_fbm'](np.stack([p[:, 0] * fr, p[:, 1] * fr, np.full(len(p), te)], -1), oct_, g.SEED) - 0.5) * \
            TAU * M1[2]
        if f == 2:
            st = TAU / max(M1[3], 1.0)
            a = np.floor(a / st + 0.5) * st
        v = np.stack([np.cos(a), np.sin(a)], -1)
    elif f in (3, 4):
        if img is None:
            v = np.zeros_like(p)
        else:
            H, W = img.shape[:2]
            u = p[:, 0] / (2.0 * g.ASP) + 0.5
            w = p[:, 1] * 0.5 + 0.5
            ex, ey = 2.0 / W, 2.0 / H
            L = lambda uu, vv: lum(bilinear_hold(img, uu, vv))
            gx = (L(u + ex, w) - L(u - ex, w)) * M3[0]
            gy = (L(u, w + ey) - L(u, w - ey)) * M3[0]
            v = np.stack([-gy, gx], -1) if f == 3 else np.stack([gx, gy], -1)
    elif f == 5:
        v = np.stack([-p[:, 1], p[:, 0]], -1) * M3[1] - p * M3[2]
    else:
        v = np.tile(np.array([0.0, -1.0]), (len(p), 1))
    return v + cn * M2[3]


def bilinear_hold(img, u, v):
    """texture() with linear filter + hold extend at uv (TD rows y up): img (H, W, 4)."""
    np = _np()
    H, W = img.shape[:2]
    x = np.clip(u * W - 0.5, 0, W - 1)
    y = np.clip(v * H - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    a = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    b = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return a * (1 - fy) + b * fy


def sl_spawn(i, salt, U, g, img=None):
    np = _np()
    sp = int(U['uM2'][0] + 0.5)
    rx, ry = rnd(i, salt, g), rnd(i, salt + 1, g)
    if sp == 1:
        return np.stack([np.full(len(rx), -g.ASP), ry * 2.0 - 1.0], -1)
    if sp == 2:
        a, rr = TAU * rx, 0.25 * np.sqrt(ry)
        return np.stack([rr * np.cos(a), rr * np.sin(a)], -1)
    best = np.stack([(rx * 2.0 - 1.0) * g.ASP, ry * 2.0 - 1.0], -1)
    if sp == 3 and img is not None:
        done = np.zeros(len(rx), bool)
        for k in range(16):
            qx, qy = rnd(i, salt + 2 + 2 * k, g), rnd(i, salt + 3 + 2 * k, g)
            hit = (lum(bilinear_hold(img, qx, qy)) > rnd(i, salt + 40 + k, g)) & ~done
            best[hit] = np.stack([(qx[hit] * 2.0 - 1.0) * g.ASP, qy[hit] * 2.0 - 1.0], -1)
            done |= hit
    return best


def streamlines_seed(i, U, g, img=None):
    np = _np()
    p = sl_spawn(i, 31, U, g, img)
    return np.stack([p[:, 0], p[:, 1], rnd(i, 33, g), np.zeros(len(p))], -1)


def streamlines_step(i, S, U, g, dt, img=None):
    np = _np()
    if dt <= 0:
        return S.copy()
    M1, M2 = U['uM1'], U['uM2']
    p = S[:, :2]
    sp = M1[0]
    v1 = sl_field(p, U, g, img)
    v = sl_field(p + v1 * sp * dt * 0.5, U, g, img)
    vel = v * sp
    p = p + vel * dt
    life = M1[1] * (0.5 + rnd(i, 35, g))
    prog = S[:, 2] + dt / np.maximum(life, 1e-3)
    out_ = (np.abs(p[:, 0]) > g.ASP) | (np.abs(p[:, 1]) > 1.0)
    if int(M2[1] + 0.5) == 1:
        p = np.stack([np.mod(p[:, 0] + g.ASP, 2.0 * g.ASP) - g.ASP, np.mod(p[:, 1] + 1.0, 2.0) - 1.0], -1)
        out_ = np.zeros(len(p), bool)
    dead = (prog >= 1.0) | out_
    res = np.stack([p[:, 0], p[:, 1], prog, np.arctan2(vel[:, 1], vel[:, 0])], -1)
    if dead.any():
        ii = np.asarray(i)[dead]
        q = sl_spawn(ii, g.FR * 4 + 5, U, g, img)
        res[dead] = np.stack([q[:, 0], q[:, 1], np.zeros(len(q)), np.zeros(len(q))], -1)
    return res


def streamlines_place(i, S, U, g):
    np = _np()
    M2, M3 = U['uM2'], U['uM3']
    P = np.stack([S[:, 0], S[:, 1], np.zeros(len(S))], -1)
    fd = M3[3]
    a = np.clip(S[:, 2] / fd, 0, 1) * np.clip((1.0 - S[:, 2]) / fd, 0, 1) if fd > 0 else np.ones(len(S))
    cb = int(M2[2] + 0.5)
    if cb == 0:
        k = S[:, 3] / TAU + 0.5
    elif cb == 1:
        k = S[:, 2]
    elif cb == 2:
        k = S[:, 0] / (2.0 * g.ASP) + 0.5
    else:
        k = rnd(i, 5, g)
    return P, k, a, np.ones(len(S), bool)


# ------------------------------------------------------------------ form (FX4 G-FORM, Trapcode Form)
def fm_base(i, U, g):
    """Base position B, normal N, grid uvw for point indices i (shape box / sphere / cylinder / plane)."""
    np = _np()
    M0, M1 = U['uM0'], U['uM1']
    i = np.asarray(i, dtype=np.int64)
    L = max(int(M0[1] + 0.5), 1)
    sh = int(M0[0] + 0.5)
    m = max((g.NPTS + L - 1) // L, 1)
    layer = i // m
    j = i - layer * m
    w = layer / float(L - 1) if L > 1 else np.full(len(i), 0.5)
    S = np.array([M0[2], M0[3], M1[0]])
    if sh == 1:
        z = 1.0 - 2.0 * (j + 0.5) / m
        r = np.sqrt(np.maximum(0.0, 1.0 - z * z))
        ph = j * 2.39996323
        N = np.stack([r * np.cos(ph), z, r * np.sin(ph)], -1)
        R = 0.5 * S[0] * (0.5 + 0.5 * w if L > 1 else 1.0)
        B = N * np.asarray(R)[..., None] if L > 1 else N * R
        uvw = np.stack([ph / TAU - np.floor(ph / TAU), z * 0.5 + 0.5, w * np.ones(len(i))], -1)
        return B, N, uvw
    gw = S[1] * g.ASP if sh == 4 else S[0]
    gx = max(int(math.sqrt(m * gw / max(S[1], 1e-3)) + 0.5), 1)
    gy = (m + gx - 1) // gx
    ix, iy = j % gx, j // gx
    u = ix / float(gx - 1) if gx > 1 else np.full(len(i), 0.5)
    v = iy / float(gy - 1) if gy > 1 else np.full(len(i), 0.5)
    uvw = np.stack([u * np.ones(len(i)), v * np.ones(len(i)), w * np.ones(len(i))], -1)
    if sh == 2:
        a = TAU * ix / float(gx)
        N = np.stack([np.cos(a), np.zeros(len(i)), np.sin(a)], -1)
        rs = (0.6 + 0.4 * w) if L > 1 else 1.0
        B = np.stack([N[:, 0] * 0.5 * S[0] * rs, (v - 0.5) * S[1] * np.ones(len(i)), N[:, 2] * 0.5 * S[0] * rs], -1)
        return B, N, uvw
    N = np.tile(np.array([0.0, 0.0, 1.0]), (len(i), 1))
    if sh == 4:
        B = np.stack([(uvw[:, 0] - 0.5) * S[1] * g.ASP, (uvw[:, 1] - 0.5) * S[1], np.zeros(len(i))], -1)
        return B, N, uvw
    B = np.stack([(uvw[:, 0] - 0.5) * S[0], (uvw[:, 1] - 0.5) * S[1],
                  np.zeros(len(i)) if sh == 3 else (uvw[:, 2] - 0.5) * S[2]], -1)
    return B, N, uvw


def form_eval(i, U, g, img=None):
    np = _np()
    X = px()
    M0, M1, M2, M3 = U['uM0'], U['uM1'], U['uM2'], U['uM3']
    B, N, uvw = fm_base(i, U, g)
    te = g.T * M2[1]
    q = B * M1[2] + np.array([te * 0.61, te * 0.37, M2[0] * g.T])
    oct_ = min(max(int(M1[3] + 0.5), 1), 6)
    amp = M1[1] * (1.0 + g.LEVEL)
    if int(M2[2] + 0.5) == 0:
        f = X['np_fbm'](q, oct_, g.SEED)
        kd = f
        D = N * ((f - 0.5) * 2.0 * amp)[:, None]
    else:
        c = X['np_curl'](B * M1[2] + np.array([0.0, 0.0, M2[0] * g.T]), te, min(oct_, 4))
        D = c * amp
        kd = np.clip(np.sqrt((c * c).sum(-1)) * 0.5, 0.0, 1.0)
    if M2[3] != 0.0 and img is not None:
        D = D + N * (lum(bilinear_hold(img, uvw[:, 0], uvw[:, 1])) * M2[3])[:, None]
    D = D + (rnd3(i, 51, g) * 2.0 - 1.0) * M3[0] * (1.0 + M3[3] * g.ENV)
    fa = np.ones(len(i))
    M4 = U.get('uM4', (0.0, 0.0, 0.0, 0.0))
    if M4[0] != 0.0:
        Lm = lum(bilinear_hold(img, uvw[:, 0], uvw[:, 1])) if img is not None else np.zeros(len(i))
        tt = np.clip((Lm - M4[2]) / max(1.0 - M4[2], 1e-12), 0.0, 1.0)
        gg = tt * tt * (3.0 - 2.0 * tt)
        x = g.T * M4[1] * (0.5 + rnd(i, 57, g)) + rnd(i, 58, g)
        ph = (x - np.floor(x)) * gg
        c = X['np_curl'](B * 2.0 + np.array([0.0, 0.0, 0.37 * g.T]), g.T * 0.5, 2)
        D = D + N * (M4[0] * ph)[:, None] + c * (M4[3] * ph)[:, None]
        fa = 1.0 - ph ** 4
    P = B + D
    tw = math.radians(M3[1]) * (P[:, 1] / max(0.5 * M0[3], 1e-3))
    x, z = rot2(P[:, 0], P[:, 2], tw)
    P = np.stack([x, P[:, 1], z], -1)
    cb = int(M3[2] + 0.5)
    if cb == 0:
        k = kd
    elif cb == 1:
        k = P[:, 2] / max(M1[0], 1e-3) + 0.5
    elif cb == 2:
        k = P[:, 1] / max(M0[3], 1e-3) + 0.5
    else:
        k = rnd(i, 5, g)
    return np.concatenate([P, pack_ka(k, fa)[:, None]], -1)


def form_seed(i, U, g, img=None):
    return form_eval(i, U, g, img)


def form_step(i, S, U, g, dt, img=None):
    return form_eval(i, U, g, img)


def form_place(i, S, U, g):
    np = _np()
    k, a = unpack(S[:, 3])
    return S[:, :3].copy(), k, a, np.ones(len(S), bool)


# ------------------------------------------------------------------ flame (FX5 G15, Draves & Reckase chaos game)
# Genome = 4 xforms x 25 floats: [w, colour, rot flag, a, b, c, d, e, f, v0..v15]: x' = a x + b y + c, y' = d x + e y
# + f, then sum_v v_k V_k(x', y'); colour index c <- mix(c, colour, Colorspeed). Variations (FX7 3.3; th = atan2(x, y)
# with x FIRST, r = |p|): 0 linear 1 sinusoidal 2 spherical 3 swirl 4 horseshoe 5 polar 6 handkerchief 7 heart 8 disc
# 9 spiral 10 hyperbolic 11 diamond 12 ex 13 julia 14 bent 15 fisheye. Genomes: found offline by a random search
# (entropy / occupancy of the density), 26 Oct; centre / extent = 1-99 percentile box of a 150k x 20 iteration run.
FL_NV = 16
FL_XF = 4
FL_STRIDE = 25
FL_EPS = 1e-10
FL_NAMES = ['ringswirl', 'loops', 'eye', 'orbit', 'leaf', 'hook']
_FL_SRC = [
    [(0.96, 0.0, 1, (-0.12, 0.64, 0.91, 0.47, 0.2, 0.64), {14: 1.0, 8: 0.64}),
     (0.7, 0.5, 0, (-0.43, -0.52, 0.65, -0.91, 0.97, -0.25), {3: 0.76}),
     (0.88, 1.0, 0, (0.59, 0.37, -0.14, 0.38, -0.57, -0.43), {2: 0.57, 3: 0.94})],
    [(0.33, 0.0, 1, (0.69, 0.2, 0.93, -0.31, 0.19, 0.2), {7: 0.93}),
     (0.8, 1.0, 0, (0.9, 0.07, -0.61, 0.51, -0.99, -0.34), {4: 0.68})],
    [(0.23, 0.0, 1, (0.37, -0.38, -0.73, -0.96, -0.91, 0.2), {14: 0.85}),
     (0.35, 1.0, 0, (-0.71, 0.86, -0.32, 0.46, 0.46, -0.88), {7: 0.7})],
    [(0.34, 0.0, 1, (0.98, -0.94, -0.21, 0.51, 0.95, -0.72), {8: 0.64, 3: 0.9}),
     (0.4, 0.5, 0, (-0.55, -0.36, -0.68, 0.95, 0.87, 0.89), {2: 0.31, 6: 0.69}),
     (0.75, 1.0, 0, (-0.88, 0.26, 0.97, -0.76, -0.1, -0.96), {2: 0.94, 8: 0.72})],
    [(0.61, 0.0, 1, (-0.38, -0.78, 0.57, -0.51, -0.03, 0.24), {4: 0.9}),
     (0.46, 1.0, 0, (0.93, -0.84, 0.84, -0.25, 0.66, 0.97), {2: 0.82, 12: 0.63})],
    [(0.65, 0.0, 1, (0.59, 0.83, 0.17, 0.36, 0.0, -0.45), {7: 0.87}),
     (0.56, 0.33, 0, (0.61, -0.21, -0.96, 0.81, 0.32, 0.89), {4: 0.78}),
     (0.66, 0.67, 0, (0.95, -0.46, -0.69, 0.51, -0.85, 0.44), {7: 0.59}),
     (0.57, 1.0, 0, (-0.24, 0.43, 0.38, -0.27, 0.25, 0.63), {2: 0.57})],
]


def _fl_flat():
    out = []
    for gen in _FL_SRC:
        for k in range(FL_XF):
            row = [0.0] * FL_STRIDE
            if k < len(gen):
                w, col, rot, A, V = gen[k]
                row[0], row[1], row[2] = float(w), float(col), float(rot)
                row[3:9] = [float(x) for x in A]
                for v, wv in V.items():
                    row[9 + v] = float(wv)
            out += row
    return out


FL_G = _fl_flat()
FL_CEN = [(0.205, 0.086), (0.026, 0.504), (-1.33, 0.56), (-0.198, 0.338), (0.584, 0.396), (-0.079, 0.23)]
FL_EXT = [1.93, 1.145, 3.772, 2.052, 1.013, 1.58]      # fl_measure(g, 60000, 30), 26 Oct


def fl_var(v, x, y, rw):
    """Variation v of (x, y) arrays; rw = julia's random (0..1)."""
    np = _np()
    r2 = x * x + y * y
    r = np.sqrt(r2)
    th = np.arctan2(x, y)
    if v == 0:
        return x, y
    if v == 1:
        return np.sin(x), np.sin(y)
    if v == 2:
        return x / (r2 + FL_EPS), y / (r2 + FL_EPS)
    if v == 3:
        return x * np.sin(r2) - y * np.cos(r2), x * np.cos(r2) + y * np.sin(r2)
    if v == 4:
        return (x - y) * (x + y) / (r + FL_EPS), 2.0 * x * y / (r + FL_EPS)
    if v == 5:
        return th / PI, r - 1.0
    if v == 6:
        return r * np.sin(th + r), r * np.cos(th - r)
    if v == 7:
        return r * np.sin(r * th), -r * np.cos(r * th)
    if v == 8:
        return th / PI * np.sin(PI * r), th / PI * np.cos(PI * r)
    if v == 9:
        return (np.cos(th) + np.sin(r)) / (r + FL_EPS), (np.sin(th) - np.cos(r)) / (r + FL_EPS)
    if v == 10:
        return np.sin(th) / (r + FL_EPS), r * np.cos(th)
    if v == 11:
        return np.sin(th) * np.cos(r), np.cos(th) * np.sin(r)
    if v == 12:
        p0, p1 = np.sin(th + r) ** 3, np.cos(th - r) ** 3
        return r * (p0 + p1), r * (p0 - p1)
    if v == 13:
        W = np.where(rw < 0.5, 0.0, PI)
        q = np.sqrt(r)
        return q * np.cos(th * 0.5 + W), q * np.sin(th * 0.5 + W)
    if v == 14:
        return np.where(x < 0.0, 2.0 * x, x), np.where(y < 0.0, y * 0.5, y)
    return 2.0 / (r + 1.0) * y, 2.0 / (r + 1.0) * x


def fl_morph(U, g):
    """Genome A, B and the morph weight m of this frame (== fl_m() in GLSL)."""
    np = _np()
    M0, M1, M2 = U['uM0'], U['uM1'], U['uM2']
    ng = len(FL_NAMES)
    ga = min(max(int(M0[0] + 0.5), 0), ng - 1)
    gb = min(max(int(M0[1] + 0.5), 0), ng - 1)
    m = M0[2] + M0[3] * (0.5 - 0.5 * math.cos(TAU * M1[3] * g.T)) + 0.5 * g.LEVEL + 0.25 * M2[0] * g.ENV
    return ga, gb, min(max(m, 0.0), 1.0)


def fl_coefs(U, g):
    """Morphed + rotated xform table (FL_XF, 25) of this frame (== the GLSL per-iteration fetch)."""
    np = _np()
    G = np.array(FL_G).reshape(len(FL_NAMES), FL_XF, FL_STRIDE)
    ga, gb, m = fl_morph(U, g)
    X = G[ga] + (G[gb] - G[ga]) * m
    vs, vw = int(U['uM2'][2] + 0.5), U['uM2'][1]
    if vw != 0.0 and 0 <= vs < FL_NV:
        X[:, 9 + vs] += vw * (X[:, 0] > 0)
    th = math.radians(U['uM1'][1] * g.T)
    c, s_ = math.cos(th), math.sin(th)
    for k in range(FL_XF):
        if X[k, 2] > 0.5:
            a, b, d, e = X[k, 3], X[k, 4], X[k, 6], X[k, 7]
            X[k, 3], X[k, 4] = c * a - s_ * d, c * b - s_ * e
            X[k, 6], X[k, 7] = s_ * a + c * d, s_ * b + c * e
    return X


def fl_frame(U, g):
    """Centre / extent of the morphed genome (fit)."""
    ga, gb, m = fl_morph(U, g)
    cx = FL_CEN[ga][0] + (FL_CEN[gb][0] - FL_CEN[ga][0]) * m
    cy = FL_CEN[ga][1] + (FL_CEN[gb][1] - FL_CEN[ga][1]) * m
    return cx, cy, FL_EXT[ga] + (FL_EXT[gb] - FL_EXT[ga]) * m


def fl_iter(i, x, y, c, j, X, cs, salt, g):
    """One chaos-game iteration of points i (float64); salt = (n,) or scalar uint (choice), salt + 1 = julia."""
    np = _np()
    w = X[:, 0]
    tot = w.sum()
    u = rnd(i, salt, g) * tot
    cum = np.cumsum(w)
    jj = np.full(len(x), FL_XF - 1)
    for k in range(FL_XF - 1, -1, -1):
        jj = np.where((u < cum[k]) & (w[k] > 0.0), k, jj)
    rw = rnd(i, salt + 1, g)
    nx, ny = np.zeros(len(x)), np.zeros(len(x))
    with np.errstate(all='ignore'):
        for k in range(FL_XF):
            sel = jj == k
            if not sel.any() or X[k, 0] <= 0.0:
                continue
            tx = X[k, 3] * x[sel] + X[k, 4] * y[sel] + X[k, 5]
            ty = X[k, 6] * x[sel] + X[k, 7] * y[sel] + X[k, 8]
            ox, oy = np.zeros(sel.sum()), np.zeros(sel.sum())
            for v in range(FL_NV):
                wv = X[k, 9 + v]
                if wv != 0.0:
                    vx, vy = fl_var(v, tx, ty, rw[sel])
                    ox, oy = ox + wv * vx, oy + wv * vy
            nx[sel], ny[sel] = ox, oy
    cc = X[jj, 1]
    return nx, ny, c + (cc - c) * cs, jj.astype(np.float64)


FL_WARM = 20


def fl_seed(i, salt, U, g):
    np = _np()
    X = fl_coefs(U, g)
    cs = U['uM1'][2]
    x = rnd(i, salt, g) * 2.0 - 1.0
    y = rnd(i, salt + 1, g) * 2.0 - 1.0
    c = rnd(i, salt + 2, g)
    j = np.zeros(len(x))
    for k in range(FL_WARM):
        x, y, c, j = fl_iter(i, x, y, c, j, X, cs, (salt + 8 + 2 * k) & U32, g)
        with np.errstate(all='ignore'):
            bad = ~(x * x + y * y < 1e8)
        x, y = np.where(bad, 0.1, x), np.where(bad, 0.1, y)
    return np.stack([x, y, c, j], -1)


def flame_seed(i, U, g):
    return fl_seed(np_u(i), 1000, U, g)


def np_u(i):
    np = _np()
    return np.asarray(i, dtype=np.int64)


def flame_step(i, S, U, g, dt):
    np = _np()
    if dt <= 0:
        return S.copy()
    X = fl_coefs(U, g)
    cs = U['uM1'][2]
    it = min(max(int(U['uM1'][0] + 0.5), 1), 16)
    x, y, c, j = S[:, 0].copy(), S[:, 1].copy(), S[:, 2].copy(), S[:, 3].copy()
    for k in range(it):
        x, y, c, j = fl_iter(i, x, y, c, j, X, cs, (g.FR * 64 + 2 * k + 1) & U32, g)
    with np.errstate(all='ignore'):
        bad = ~(x * x + y * y < 1e8)
    resp = rnd(i, (g.FR * 4 + 3) & U32, g) < U['uSt2'][0] * dt
    out = np.stack([x, y, c, j], -1)
    sel = bad | resp
    if sel.any():
        out[sel] = fl_seed(np.asarray(i)[sel], (g.FR * 4 + 7) & U32, U, g)
    return out


def flame_place(i, S, U, g):
    np = _np()
    cx, cy, e = fl_frame(U, g)
    sc = min(g.ASP, 1.0) * 0.95 / max(e, 1e-6)
    P = np.stack([(S[:, 0] - cx) * sc, (S[:, 1] - cy) * sc, np.zeros(len(S))], -1)
    cb = int(U['uM2'][3] + 0.5)
    if cb == 0:
        k = S[:, 2]
    elif cb == 1:
        k = S[:, 3] / (FL_XF - 1)
    elif cb == 2:
        k = np.hypot(S[:, 0] - cx, S[:, 1] - cy) / max(e, 1e-6)
    else:
        k = rnd(i, 5, g)
    ok = (S[:, 0] * S[:, 0] + S[:, 1] * S[:, 1]) < 1e8
    return P, k, np.ones(len(S)), ok


def fl_measure(gi, n=150000, its=40, seed=1):
    """Offline: centre / extent (1-99 percentile box) of genome gi (static, no morph / rotation)."""
    np = _np()
    U = {'uM0': (gi, gi, 0.0, 0.0), 'uM1': (1, 0.0, 0.5, 0.0), 'uM2': (0.0, 0.0, 0.0, 0.0),
         'uDrv': (0.0, 0.0, 1000.0, 0.0), 'uBeat': (0.0, 1.0, 0.0, 0.0), 'uSt2': (0.0, 0.5625, 1, 1)}
    g = Glob(U)
    i = np.arange(n)
    S = flame_seed(i, U, g)
    xs, ys = [], []
    for f in range(its):
        g.FR = f + 1
        S = flame_step(i, S, U, g, 1.0 / 60.0)
        if f >= 10:
            xs.append(S[:, 0])
            ys.append(S[:, 1])
    X, Y = np.concatenate(xs), np.concatenate(ys)
    ok = np.isfinite(X) & np.isfinite(Y)
    X, Y = X[ok], Y[ok]
    lo = np.percentile(X, 1), np.percentile(Y, 1)
    hi = np.percentile(X, 99), np.percentile(Y, 99)
    return ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2), max(hi[0] - lo[0], hi[1] - lo[1]) / 2


# ------------------------------------------------------------------ lsystem (FX5 G05: rewriting + turtle, cached)
# The segment table is built in Python (Script TOP `aux`, only when its pars change) and read by the state pass:
# width LS_W texels; texel 0 = (nseg, cx, cy, ext), 1 = (total length, max depth, iterations used, 0); segment j at
# 2 + 2j = (x0, y0, x1, y1) and 3 + 2j = (depth, order j / nseg, cumulative length before j, length).
LS_W = 1024
LS_MAXSEG = 131072
LS_MAXCHARS = 600000
LS_SYSTEMS = [
    ('koch', 'F', {'F': 'F+F-F-F+F'}, 90.0, 4, 'F', 0.0),
    ('snowflake', 'F--F--F', {'F': 'F+F--F+F'}, 60.0, 4, 'F', 0.0),
    ('dragon', 'F', {'F': 'F+G', 'G': 'F-G'}, 90.0, 12, 'FG', 0.0),
    ('hilbert', 'A', {'A': '+BF-AFA-FB+', 'B': '-AF+BFB+FA-'}, 90.0, 6, 'F', 0.0),
    ('gosper', 'A', {'A': 'A-B--B+A++AA+B-', 'B': '+A-BB--B-A++A+B'}, 60.0, 4, 'AB', 0.0),
    ('sierpinski', 'A', {'A': 'B-A-B', 'B': 'A+B+A'}, 60.0, 7, 'AB', 0.0),
    ('plant', 'X', {'X': 'F+[[X]-X]-F[-FX]+X', 'F': 'FF'}, 25.0, 6, 'F', 70.0),
    ('tree', 'X', {'X': 'F[+X][-X]FX', 'F': 'FF'}, 25.7, 6, 'F', 90.0),
    ('bush', 'F', {'F': 'FF+[+F-F-F]-[-F+F+F]'}, 22.5, 4, 'F', 90.0),
]
LS_NAMES = [s_[0] for s_ in LS_SYSTEMS] + ['custom']


def ls_parse_rules(texts):
    """['F=FF+[+F]', 'X -> F[X]'] -> {'F': 'FF+[+F]', 'X': 'F[X]'} (single-symbol left sides)."""
    out = {}
    for t in texts:
        t = (t or '').strip()
        if not t:
            continue
        for sep in ('->', '=', ':'):
            if sep in t:
                k, v = t.split(sep, 1)
                k = k.strip()
                if len(k) == 1:
                    out[k] = v.strip().replace(' ', '')
                break
    return out


def ls_expand(axiom, rules, iters):
    s_ = axiom
    used = 0
    for _k in range(max(int(iters), 0)):
        n = ''.join(rules.get(ch, ch) for ch in s_)
        if len(n) > LS_MAXCHARS:
            break
        s_ = n
        used += 1
    return s_, used


def ls_segments(axiom, rules, angle, iters, draw='F', heading=90.0, decay=1.0, jitter=0.0, seed=0):
    """Turtle: draw symbols move + draw, f moves, + / - turn by angle (+ jitter), | turns 180, [ ] push / pop
    (depth = bracket depth, length x decay^depth). Returns segs (n, 4) float64, depth (n,), iterations used."""
    import random
    np = _np()
    text, used = ls_expand(axiom, rules, iters)
    rng = random.Random(int(seed))
    x = y = 0.0
    h = math.radians(heading)
    a = math.radians(angle)
    stack = []
    depth = 0
    segs, deps = [], []
    dset = set(draw or 'F')
    for ch in text:
        if ch in dset or ch == 'f':
            ln = decay ** depth
            nx, ny = x + ln * math.cos(h), y + ln * math.sin(h)
            if ch != 'f':
                segs.append((x, y, nx, ny))
                deps.append(depth)
                if len(segs) >= LS_MAXSEG:
                    break
            x, y = nx, ny
        elif ch == '+' or ch == '-':
            d = a + (math.radians(jitter) * (2.0 * rng.random() - 1.0) if jitter else 0.0)
            h += d if ch == '+' else -d
        elif ch == '|':
            h += math.pi
        elif ch == '[':
            stack.append((x, y, h, depth))
            depth += 1
        elif ch == ']' and stack:
            x, y, h, depth = stack.pop()
    S = np.array(segs, dtype=np.float64).reshape(-1, 4)
    return S, np.array(deps, dtype=np.float64), used


def ls_resolve(system, axiom='', rules=(), angle=0.0, iters=0, draw='', heading=-1.0):
    """Menu entry -> (axiom, rules, angle, iters, draw, heading); custom uses the string pars; 0 / -1 = default."""
    if system in LS_NAMES[:-1]:
        _n, ax, ru, an, it, dr, hd = LS_SYSTEMS[LS_NAMES.index(system)]
    else:
        ax, ru, an, it, dr, hd = (axiom or 'F'), ls_parse_rules(rules), 90.0, 3, (draw or 'F'), 90.0
    return (ax, ru, angle if angle > 0 else an, int(iters) if iters > 0 else it, dr, heading if heading >= 0 else hd)


def ls_table(S, D, used=0):
    """Segment table (H, LS_W, 4) float32 (row 0 = texel row 0) from segs S (n, 4) and depths D."""
    np = _np()
    n = len(S)
    T = np.zeros((max(1, (2 + 2 * n + LS_W - 1) // LS_W), LS_W, 4), dtype=np.float32)
    flat = T.reshape(-1, 4)
    if n == 0:
        return T
    L = np.hypot(S[:, 2] - S[:, 0], S[:, 3] - S[:, 1])
    cum = np.concatenate([[0.0], np.cumsum(L)[:-1]])
    xs, ys = np.concatenate([S[:, 0], S[:, 2]]), np.concatenate([S[:, 1], S[:, 3]])
    cx, cy = (xs.min() + xs.max()) / 2.0, (ys.min() + ys.max()) / 2.0
    ext = max(xs.max() - xs.min(), ys.max() - ys.min()) / 2.0
    flat[0] = (n, cx, cy, max(ext, 1e-6))
    flat[1] = (L.sum(), D.max(), used, 0.0)
    flat[2:2 + 2 * n:2] = S
    flat[3:3 + 2 * n:2] = np.stack([D, np.arange(n) / float(n), cum, L], -1)
    return T


def lsystem_eval(i, U, g, aux):
    """Stateless: point i on the visible part of the segment table (== ls_eval in GLSL)."""
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    A = np.asarray(aux, dtype=np.float64).reshape(-1, 4)
    n = int(A[0, 0] + 0.5)
    out = np.zeros((len(i), 4))
    if n < 1:
        return out
    cx, cy, ext = A[0, 1], A[0, 2], A[0, 3]
    total, maxd = A[1, 0], A[1, 1]
    M0, M1 = U['uM0'], U['uM1']
    grow = M1[3]
    prog = min(max(M0[0], 0.0), 1.0) if grow <= 0 else min((g.T * grow - math.floor(g.T * grow)) * 1.2, 1.0)
    mode = int(M0[1] + 0.5)
    fr = (rnd(i, 41, g) + M0[2] * g.FR * 0.618034)
    u01 = (i + (fr - np.floor(fr))) / float(max(g.NPTS, 1))
    Ls = u01 * total * (prog if mode == 0 else 1.0)
    cum = A[3:3 + 2 * n:2, 2]
    lo = np.zeros(len(i), dtype=np.int64)
    hi = np.full(len(i), n - 1, dtype=np.int64)
    for _k in range(20):                                     # largest j with cum[j] <= L (== the GLSL search)
        mid = (lo + hi + 1) // 2
        go = cum[np.minimum(mid, n - 1)] <= Ls
        act = lo < hi
        lo = np.where(act & go, mid, lo)
        hi = np.where(act & ~go, mid - 1, hi)
    j = lo
    seg = A[2 + 2 * j]
    inf = A[3 + 2 * j]
    t = np.clip((Ls - inf[:, 2]) / np.maximum(inf[:, 3], 1e-9), 0.0, 1.0)
    vis = np.ones(len(i))
    if mode == 1:
        f = np.clip(prog * (maxd + 1.0) - inf[:, 0], 0.0, 1.0)
        vis = np.where(t <= f, 1.0, 0.0)
        vis = np.where(prog <= 0.0, 0.0, vis)
    elif prog <= 0.0:
        vis[:] = 0.0
    x = seg[:, 0] + (seg[:, 2] - seg[:, 0]) * t
    y = seg[:, 1] + (seg[:, 3] - seg[:, 1]) * t
    dn = inf[:, 0] / max(maxd, 1.0)
    if M0[3] != 0.0:
        X = px()
        q = np.stack([np.full(len(i), g.T * M1[0]), inf[:, 0] * 0.37, np.zeros(len(i))], -1)
        x = x + M0[3] * ext * dn * dn * (X['np_noise'](q, g.SEED) - 0.5) * 2.0
    sc = min(g.ASP, 1.0) * 0.95 * M1[2] / max(ext, 1e-6)
    cb = int(M1[1] + 0.5)
    k = dn if cb == 0 else (inf[:, 1] if cb == 1 else (u01 if cb == 2 else rnd(i, 5, g)))
    out[:, 0] = (x - cx) * sc
    out[:, 1] = (y - cy) * sc
    out[:, 2] = 0.0
    out[:, 3] = pack_ka(k, vis)
    return out


def lsystem_seed(i, U, g, aux=None):
    return lsystem_eval(i, U, g, aux)


def lsystem_step(i, S, U, g, dt, aux=None):
    if dt <= 0:
        return S.copy()
    return lsystem_eval(i, U, g, aux)


def lsystem_place(i, S, U, g):
    np = _np()
    k, a = unpack(S[:, 3])
    return S[:, :3].copy(), k, a, a > 0.0


# ------------------------------------------------------------------ graph (FX5 G22, force-directed constellation)
# Nodes = texels 0..N-1 (x, y, vx, vy); tree edge k -> parent(k) = floor(rnd(k, 71) k), extra edge k -> floor(rnd(k,
# 73) N) when rnd(k, 75) < Extra. Forces (Fruchterman-Reingold): repulsion K^2 d / (|d|^2 + soft) on all pairs,
# springs -d |d| / K on edges, gravity -G p, beat kick. The other points draw node glows and edge dust (place only).
def gr_n(U, g):
    return max(1, min(int(U['uM0'][0] + 0.5), g.NPTS, 4096))


def gr_parent(k, g):
    np = _np()
    k = np.asarray(k, dtype=np.int64)
    return np.where(k > 0, np.floor(rnd(k, 71, g) * k).astype(np.int64), -1)


def gr_extra(k, N, U, g):
    np = _np()
    k = np.asarray(k, dtype=np.int64)
    x = np.floor(rnd(k, 73, g) * N).astype(np.int64)
    return np.where((rnd(k, 75, g) < U['uM0'][3]) & (x != k), x, -1)


def graph_seed(i, U, g):
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    N = gr_n(U, g)
    a = TAU * rnd(i, 61, g)
    r = np.sqrt(rnd(i, 62, g)) * 0.5 * U['uM4'][1]
    out = np.zeros((len(i), 4))
    nd = i < N
    out[nd, 0] = (r * np.cos(a))[nd]
    out[nd, 1] = (r * np.sin(a))[nd]
    return out


def graph_step(i, S, U, g, dt, full=None):
    np = _np()
    if dt <= 0:
        return S.copy()
    i = np.asarray(i, dtype=np.int64)
    F0 = full if full is not None else S
    N = gr_n(U, g)
    M0, M1, M2 = U['uM0'], U['uM1'], U['uM2']
    K, rep, spring = M0[1], M1[0], M0[2]
    grav, damp, vmax = M1[1], M1[2], M1[3]
    out = np.zeros((len(i), 4))
    nd = np.where(i < N)[0]
    if len(nd) == 0:
        return out
    ii = i[nd]
    p = S[nd, :2].copy()
    v = S[nd, 2:].copy()
    Q = F0[:N, :2]
    jj = np.arange(N)
    pj = gr_parent(jj, g)
    xj = gr_extra(jj, N, U, g)
    pi_ = gr_parent(ii, g)
    xi = gr_extra(ii, N, U, g)
    F = np.zeros_like(p)
    soft = (0.05 * K) ** 2
    for c0 in range(0, len(ii), 256):
        sl = slice(c0, c0 + 256)
        d = p[sl, None, :] - Q[None, :, :]
        d2 = (d * d).sum(-1)
        same = ii[sl, None] == jj[None, :]
        fr = rep * K * K / (d2 + soft)
        fr = np.where(same, 0.0, fr)
        link = (pj[None, :] == ii[sl, None]) | (pi_[sl, None] == jj[None, :]) | (xj[None, :] == ii[sl, None]) | \
               (xi[sl, None] == jj[None, :])
        link &= ~same
        fa = np.where(link, np.sqrt(d2) / K * spring, 0.0)
        F[sl] = (d * (fr - fa)[..., None]).sum(1)
    F -= p * grav
    kx = (rnd(ii, (g.FR * 4 + 1) & U32, g) - 0.5) * 2.0
    ky = (rnd(ii, (g.FR * 4 + 2) & U32, g) - 0.5) * 2.0
    F += np.stack([kx, ky], -1) * (M2[0] * g.ENV)
    v = v * math.exp(-damp * dt) + F * dt
    sp = np.sqrt((v * v).sum(-1))
    v = np.where((sp > vmax)[:, None], v * (vmax / np.maximum(sp, 1e-12))[:, None], v)
    p = p + v * dt
    bad = ~((p * p).sum(-1) < 1e4)
    out[nd, :2] = p
    out[nd, 2:] = v
    if bad.any():
        out[nd[bad]] = graph_seed(ii[bad], U, g)
    return out


def graph_place(i, S, U, g):
    """S = the whole state (rows = point index): nodes, node glow discs, edge dust."""
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    N = gr_n(U, g)
    M2, M3 = U['uM2'], U['uM3']
    G = max(int(M3[0] + 0.5), 0)
    P = np.zeros((len(i), 3))
    k = np.zeros(len(i))
    a = np.zeros(len(i))
    ok = np.zeros(len(i), bool)
    cb = int(M2[1] + 0.5)
    cs = M2[2]

    def nk(n):
        sp = np.sqrt((S[n, 2:] ** 2).sum(-1))
        return n / float(N) if cb == 0 else (sp * cs if cb == 1 else rnd(n, 5, g))
    m = i < N
    P[m, :2] = S[i[m], :2]
    k[m] = nk(i[m])
    a[m] = M3[1]
    ok[m] = True
    m = (i >= N) & (i < N + N * G)
    if m.any():
        n = (i[m] - N) // max(G, 1)
        r = np.sqrt(rnd(i[m], 91, g)) * M3[2]
        an = TAU * rnd(i[m], 92, g)
        P[m, 0] = S[n, 0] + r * np.cos(an)
        P[m, 1] = S[n, 1] + r * np.sin(an)
        k[m] = nk(n)
        a[m] = M3[1] * 0.5
        ok[m] = True
    e0 = N + N * G
    ne = 2 * N - 1
    pe = max((g.NPTS - e0) // ne, 1)
    m = i >= e0
    if m.any():
        idx = np.where(m)[0]
        e = (i[m] - e0) // pe
        loc = (i[m] - e0) - e * pe
        tree = e < N - 1
        A_ = np.where(tree, e + 1, e - (N - 1))
        B_ = np.where(tree, gr_parent(np.where(tree, e + 1, 1), g), gr_extra(np.minimum(A_, N - 1), N, U, g))
        good = (e < ne) & (B_ >= 0) & (A_ < N)
        A_, B_ = np.clip(A_, 0, N - 1), np.clip(B_, 0, N - 1)
        fr = rnd(i[m], 93, g) + g.T * M3[3]
        t = (loc + (fr - np.floor(fr))) / float(pe)
        pa, pb = S[A_, :2], S[B_, :2]
        q = pa + (pb - pa) * t[:, None]
        L = np.sqrt(((pa - pb) ** 2).sum(-1))
        fade = np.clip(1.0 - L / M2[3], 0.0, 1.0) if M2[3] > 0 else np.ones(len(L))
        P[idx, :2] = q
        k[idx] = L * cs if cb == 2 else (nk(A_) + nk(B_)) * 0.5
        a[idx] = fade * U['uM4'][0]
        ok[idx] = good & (fade > 0.0)
    return P, k, a, ok


# ------------------------------------------------------------------ sparkle (G-SPARKLE, own clean-room design)
# Stateless twinkles: point i flashes f_i = Rate (0.5 + rnd) times per second, b = sin(pi q)^Sharp over each cycle q,
# and moves to a new place every cycle (anywhere / centre disc / bright input pixels); drawn as glint sprites.
def sparkle_eval(i, U, g, img=None):
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    M0, M1, M2 = U['uM0'], U['uM1'], U['uM2']
    f = M0[0] * (0.5 + rnd(i, 81, g))
    xx = np.maximum(g.T, 0.0) * f + rnd(i, 82, g)
    n = np.floor(xx)
    q = xx - n
    salt = (n.astype(np.int64) * 8) & U32
    mode = int(M0[1] + 0.5)
    r0, r1 = rnd(i, salt + 100, g), rnd(i, salt + 101, g)
    vis = np.ones(len(i))
    if mode == 1:
        an = TAU * r0
        rr = M0[2] * np.sqrt(r1)
        x, y = rr * np.cos(an), rr * np.sin(an)
    else:
        x, y = (r0 * 2.0 - 1.0) * g.ASP, r1 * 2.0 - 1.0
    if mode == 2:
        found = np.zeros(len(i), bool)
        for k in range(16):
            qx, qy = rnd(i, salt + 110 + 2 * k, g), rnd(i, salt + 111 + 2 * k, g)
            if img is None:
                L = np.zeros(len(i))
            else:
                L = lum(bilinear_hold(img, qx, qy))
            hit = (L > M0[3]) & ~found
            x = np.where(hit, (qx * 2.0 - 1.0) * g.ASP, x)
            y = np.where(hit, qy * 2.0 - 1.0, y)
            found |= hit
        vis = np.where(found, 1.0, 0.0)
    age = q / np.maximum(f, 1e-6)
    x = x + M1[0] * age
    y = y + M1[1] * age
    b = np.power(np.maximum(np.sin(PI * q), 0.0), M1[2])
    b = np.maximum(b, M1[3] * g.ENV * rnd(i, salt + 7, g)) * vis
    k = rnd(i, salt + 5, g)
    sz = (1.0 + (0.25 + 1.5 * rnd(i, salt + 6, g) - 1.0) * M2[0]) * (1.0 + (b - 1.0) * M2[1])
    return np.stack([x, y, pack_ka(k, b), sz], -1)


def sparkle_seed(i, U, g, img=None):
    return sparkle_eval(i, U, g, img)


def sparkle_step(i, S, U, g, dt, img=None):
    if dt <= 0:
        return S.copy()
    return sparkle_eval(i, U, g, img)


def sparkle_place(i, S, U, g):
    np = _np()
    k, a = unpack(S[:, 2])
    return np.stack([S[:, 0], S[:, 1], np.zeros(len(S))], -1), k, a, a > 0.0


# ------------------------------------------------------------------ polytope4d (FX7b TC-17, lane G 27 Oct)
# Regular 4D polytopes as edge tables (circumradius 1), analytic Clifford torus / Hopf fibration / glome; rotation in
# the six planes in the fixed order XY XZ XW YZ YW ZW; projection perspective / stereographic / ortho / slice.
P4_SHAPES = ['5cell', 'tesseract', '16cell', '24cell', '600cell', '120cell', 'clifford', 'hopf', 'glome']
P4_POLY = 6
P4_W = 1024
PHI = (1.0 + 5.0 ** 0.5) / 2.0


def _perms(v, even_only=False):
    import itertools
    out = set()
    for p in itertools.permutations(range(4)):
        if even_only:
            inv = sum(1 for a in range(4) for b in range(a + 1, 4) if p[a] > p[b])
            if inv % 2:
                continue
        out.add(tuple(v[k] for k in p))
    return out


def _signs(v):
    import itertools
    out = set()
    for sg in itertools.product((1, -1), repeat=4):
        out.add(tuple(a * b for a, b in zip(v, sg)))
    return out


def _all(base, even_only=False):
    out = set()
    for q in _perms(base, even_only):
        out |= _signs(q)
    return out


def p4_vertices(shape):
    """Vertices (V, 4) of a regular polytope, centred, circumradius 1."""
    np = _np()
    f, g = PHI, 1.0 / PHI
    if shape == '5cell':
        a = 1.0 / 5.0 ** 0.5
        V = [(1, 1, 1, -a), (1, -1, -1, -a), (-1, 1, -1, -a), (-1, -1, 1, -a), (0, 0, 0, 4 * a)]
    elif shape == 'tesseract':
        V = _signs((1, 1, 1, 1))
    elif shape == '16cell':
        V = _all((1, 0, 0, 0))
    elif shape == '24cell':
        V = _all((1, 1, 0, 0))
    elif shape == '600cell':
        V = _signs((0.5, 0.5, 0.5, 0.5)) | _all((1, 0, 0, 0)) | _all((0.5 * f, 0.5, 0.5 * g, 0.0), True)
    elif shape == '120cell':
        r5 = 5.0 ** 0.5
        V = (_all((0, 0, 2, 2)) | _all((1, 1, 1, r5)) | _all((g * g, f, f, f)) | _all((g, g, g, f * f))
             | _all((0, g * g, 1, f * f), True) | _all((0, g, f, r5), True) | _all((g, 1, f, 2), True))
    else:
        raise ValueError(shape)
    V = np.array(sorted(set(tuple(round(x, 12) for x in v) for v in V)), dtype=np.float64)
    V -= V.mean(0)
    return V / np.sqrt((V * V).sum(-1)).max()


def p4_edges(V):
    """Index pairs (E, 2) at the shortest vertex distance (the edges of a regular polytope)."""
    np = _np()
    d = np.sqrt(((V[:, None, :] - V[None, :, :]) ** 2).sum(-1))
    m = d[d > 1e-9].min()
    i, j = np.where(np.triu((np.abs(d - m) < 1e-6 * max(m, 1.0)), 1))
    return np.stack([i, j], -1)


def p4_table(shape):
    """aux texture (rows, 1024, 4) float32: texel 0 = (E, V, 0, 0); texel 1 + 2e = A.xyzw, 2 + 2e = B.xyzw.
    Analytic shapes: one empty row (E = 0)."""
    np = _np()
    if shape not in P4_SHAPES[:P4_POLY]:
        return np.zeros((1, P4_W, 4), np.float32)
    V = p4_vertices(shape)
    E = p4_edges(V)
    n = 1 + 2 * len(E)
    T = np.zeros(((n + P4_W - 1) // P4_W * P4_W, 4), np.float64)
    T[0] = (len(E), len(V), 0, 0)
    T[1:n:2] = V[E[:, 0]]
    T[2:n:2] = V[E[:, 1]]
    return T.reshape(-1, P4_W, 4).astype(np.float32)


def p4_tex(aux, q):
    q = _np().asarray(q)
    return aux[q // P4_W, q % P4_W]


def p4_rotate(p, U, g):
    """p (n, 4) -> rotated, == p4Rotate (planes XY XZ XW YZ YW ZW in this order)."""
    np = _np()
    M1, M2, M3, M4 = U['uM1'], U['uM2'], U['uM3'], U['uM4']
    sp = g.T * (1.0 + g.LEVEL)
    kk = M2[2] * g.ENV
    ang = [M1[0] + M3[0] * sp, M1[1] + M3[1] * sp, M1[2] + M3[2] * sp + kk,
           M1[3] + M3[3] * sp, M2[0] + M4[0] * sp + kk, M2[1] + M4[1] * sp]
    p = np.array(p, dtype=np.float64)
    for (a, b), d in zip(((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)), ang):
        p[:, a], p[:, b] = rot2(p[:, a], p[:, b], math.radians(d))
    return p


def p4_rotation_matrix(U, g):
    """The same rotation as a 4x4 matrix (columns = images of the axes): used by tests of the 6 planes."""
    np = _np()
    return p4_rotate(np.eye(4), U, g).T


def p4_base(i, U, g, aux=None):
    """Base 4D points (n, 4) + element / along coordinates, == p4Base."""
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    M0, M4, M5 = U['uM0'], U['uM4'], U['uM5']
    sh = int(M0[0] + 0.5)
    n = len(i)
    el, al = np.zeros(n), np.zeros(n)
    if sh < P4_POLY:
        if aux is None:
            aux = p4_table(P4_SHAPES[sh])
        E = int(aux[0, 0, 0] + 0.5)
        if E < 1:
            return np.zeros((n, 4)), el, al
        per = max(g.NPTS // E, 1)
        e = i // per
        inside = e < E
        t = np.where(inside, (i - e * per + rnd(i, 31, g)) / float(per), rnd(i, 32, g))
        e = np.where(inside, e, i % E)
        t = t + M4[2] * g.T
        t = t - np.floor(t)
        el = (e + 0.5) / float(E)
        A, B = p4_tex(aux, 1 + 2 * e).astype(np.float64), p4_tex(aux, 2 + 2 * e).astype(np.float64)
        p = A + (B - A) * t[:, None]
        jit = np.concatenate([rnd3(i, 33, g), rnd(i, 36, g)[:, None]], -1) * 2.0 - 1.0
        return p + jit * M4[3], el, t
    if sh == 6:
        m = max(int(math.ceil(math.sqrt(float(g.NPTS)))), 1)
        ib, ia = i // m, i % m
        a = TAU * ((ia + 0.5) / m + M4[2] * g.T)
        b = TAU * (ib + 0.5) / m
        r = min(max(M5[0], 0.0), 1.0)
        s = math.sqrt(max(1.0 - r * r, 0.0))
        al = a / TAU - np.floor(a / TAU)
        return np.stack([r * np.cos(a), r * np.sin(a), s * np.cos(b), s * np.sin(b)], -1), (ib + 0.5) / m, al
    if sh == 7:
        F = max(int(M5[1] + 0.5), 1)
        R = min(max(int(M5[2] + 0.5), 1), F)
        per = max(g.NPTS // F, 1)
        f = np.minimum(i // per, F - 1)
        fpr = (F + R - 1) // R
        j, mm = f // fpr, f % fpr
        th = PI * (j + 0.5) / R
        ph = TAU * mm / float(fpr) + 0.5 * j
        ps = TAU * ((i - f * per + rnd(i, 37, g)) / float(per) + M4[2] * g.T)
        c, s = np.cos(0.5 * th), np.sin(0.5 * th)
        al = ps / TAU - np.floor(ps / TAU)
        return np.stack([c * np.cos(ps), c * np.sin(ps), s * np.cos(ps + ph), s * np.sin(ps + ph)], -1), \
            (f + 0.5) / F, al
    u = rnd3(i, 41, g)
    s, c = np.sqrt(u[:, 0]), np.sqrt(1.0 - u[:, 0])
    return np.stack([s * np.cos(TAU * u[:, 1]), s * np.sin(TAU * u[:, 1]), c * np.cos(TAU * u[:, 2]),
                     c * np.sin(TAU * u[:, 2])], -1), rnd(i, 5, g), u[:, 0]


def p4_project(q, U):
    np = _np()
    M0, M5, M6 = U['uM0'], U['uM5'], U['uM6']
    pm = int(M0[1] + 0.5)
    vis = np.ones(len(q))
    x = q[:, :3].copy()
    if pm == 0:
        d = M0[2] - q[:, 3]
        ok = d > 1e-3
        x = np.where(ok[:, None], x * (M0[2] / np.where(ok, d, 1.0))[:, None], 0.0)
        vis = ok.astype(np.float64)
    elif pm == 1:
        d = 1.0 - q[:, 3]
        ok = d > 0.02
        x = np.where(ok[:, None], x / np.where(ok, d, 1.0)[:, None], 0.0)
        vis = ok.astype(np.float64)
    elif pm == 3:
        vis = np.clip(1.0 - np.abs(q[:, 3] - M6[0]) / max(M5[3], 1e-6), 0.0, 1.0)
    return x * M0[3], vis


def polytope4d_eval(i, U, g, aux=None):
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    p, el, al = p4_base(i, U, g, aux)
    q = p4_rotate(p, U, g)
    P, vis = p4_project(q, U)
    a = vis * (1.0 - U['uM6'][1] * (0.5 - 0.5 * np.clip(q[:, 3], -1.0, 1.0)))
    cb = int(U['uM2'][3] + 0.5)
    k = [np.clip(0.5 + 0.5 * q[:, 3], 0.0, 0.999), el, al, rnd(i, 5, g)][cb]
    return np.concatenate([P, pack_ka(k, a)[:, None]], -1)


def polytope4d_seed(i, U, g, aux=None):
    return polytope4d_eval(i, U, g, aux)


def polytope4d_step(i, S, U, g, dt, aux=None):
    return polytope4d_eval(i, U, g, aux)


def polytope4d_place(i, S, U, g):
    np = _np()
    k, a = unpack(S[:, 3])
    return S[:, :3].copy(), k, a, a > 0.0


# ------------------------------------------------------------------ hyperspace (FX7c card 18, lane G 27 Oct)
def hyperspace_eval(i, U, g):
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    M0, M1, M2, M3, M4 = U['uM0'], U['uM1'], U['uM2'], U['uM3'], U['uM4']
    S = max(int(M0[2] + 0.5), 1)
    s, k = i // S, i % S
    L = max(M1[1] - M1[0], 1e-3)
    spd = M0[0] * M4[0] * (1.0 + M4[1] * U['uDrv'][3])
    x = rnd(s, 61, g) * L + M0[0] * g.T
    n = np.floor(x / L)
    zh = M1[1] - (x - n * L)
    sl = (n.astype(np.int64) * 4) & U32
    r0, r1 = rnd(s, sl + 200, g), rnd(s, sl + 201, g)
    fm = int(M1[3] + 0.5)
    if fm == 0:
        q = (np.stack([r0, r1], -1) * 2.0 - 1.0) * M2[0]
    else:
        rr = (M2[1] + (1.0 - M2[1]) * r0) if fm == 1 else np.sqrt(r0)
        q = (M2[0] * rr)[:, None] * np.stack([np.cos(TAU * r1), np.sin(TAU * r1)], -1)
    zt = zh + spd * M0[1] * (1.0 + M3[0] * g.ENV)
    u = (k + M0[3] * rnd(i, (g.FR * 2 + 7) & U32, g)) / float(S) if S > 1 else np.zeros(len(i))
    iz = 1.0 / zh + (1.0 / zt - 1.0 / zh) * u
    F = 1.0 / math.tan(math.radians(M1[2]) * 0.5)
    P = q * (iz * F)[:, None]
    a = np.power(np.maximum(1.0 - u, 0.0), M2[2])
    fi = np.clip((M1[1] - zh) / (M2[3] * L), 0.0, 1.0) if M2[3] > 0 else np.ones(len(i))
    a = a * fi * np.clip(M1[1] / zh / 4.0, 0.0, 1.0)
    cb = int(M3[1] + 0.5)
    if cb == 0:
        kc = np.clip(1.0 - zh / M1[1], 0.0, 0.999)
    elif cb == 1:
        kc = rnd(s, 5, g)
    else:
        kc = np.full(len(i), min(max(spd / max(M3[2], 1e-6), 0.0), 4.0) * 0.249)
    return np.stack([P[:, 0], P[:, 1], np.zeros(len(i)), pack_ka(kc, a)], -1)


def hyperspace_seed(i, U, g):
    return hyperspace_eval(i, U, g)


def hyperspace_step(i, S, U, g, dt):
    if dt <= 0:
        return S.copy()
    return hyperspace_eval(i, U, g)


def hyperspace_place(i, S, U, g):
    np = _np()
    k, a = unpack(S[:, 3])
    return np.stack([S[:, 0], S[:, 1], np.zeros(len(S))], -1), k, a, a > 0.0


# ------------------------------------------------------------------ mirrorball (FX7c card 19, lane G 27 Oct)
def mb_light(j, nl, U):
    np = _np()
    M0, M1 = U['uM0'], U['uM1']
    j = np.asarray(j, dtype=np.float64)
    az = np.radians(M1[0] + (M1[1] * (j / float(nl - 1) - 0.5) if nl > 1 else 0.0 * j))
    el = math.radians(M0[3])
    return np.stack([np.sin(az) * math.cos(el), np.full(az.shape, math.sin(el)), np.cos(az) * math.cos(el)], -1)


def mirrorball_eval(i, U, g):
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    M0, M1, M2, M3 = U['uM0'], U['uM1'], U['uM2'], U['uM3']
    nl = min(max(int(M0[0] + 0.5), 1), 4)
    nf = max(g.NPTS // nl, 1)
    j, f = i // nf, i % nf
    out = np.zeros((len(i), 4))
    z = 1.0 - 2.0 * (f + 0.5) / nf
    rr = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    ph = f * 2.39996323
    nx, ny, nz = rr * np.cos(ph), z, rr * np.sin(ph)
    nx, nz = rot2(nx, nz, math.radians(M0[1] * g.T))
    ny, nz = rot2(ny, nz, math.radians(M0[2]))
    n = np.stack([nx, ny, nz], -1)
    Ld = mb_light(np.minimum(j, nl - 1), nl, U)
    face = (n * Ld).sum(-1)
    r = 2.0 * face[:, None] * n - Ld
    ok = (j < nl) & (face > 0.0) & (r[:, 2] < -1e-3)
    t = M1[2] / np.where(ok, -r[:, 2], 1.0)
    w = r[:, :2] * (t * M1[3])[:, None]
    tw = (np.floor(g.T * M2[3]).astype(np.int64) * 3 + 11) & U32
    a = face * (1.0 - M2[2] * rnd(f, tw, g))
    if M3[0] > 0:
        a = a * np.clip(1.0 - np.sqrt((w * w).sum(-1)) / M3[0], 0.0, 1.0)
    ok &= (a > 0.0) & (np.sqrt((w * w).sum(-1)) <= 64.0)
    a = a * (1.0 + M3[1] * g.ENV)
    sz = M2[0] * np.power(1.0 / np.maximum(np.where(ok, -r[:, 2], 1.0), 0.05), M2[1]) * (1.0 + 0.5 * M3[1] * g.ENV)
    cb = int(M3[2] + 0.5)
    kc = [(j + 0.5) / nl, rnd(f, 5, g), np.clip(0.5 + 0.25 * w[:, 0], 0.0, 0.999)][cb]
    out[:, 0], out[:, 1], out[:, 2] = w[:, 0], w[:, 1], sz
    out[:, 3] = pack_ka(kc, np.clip(a, 0.0, 1.0))
    out[~ok] = 0.0
    return out


def mirrorball_seed(i, U, g):
    return mirrorball_eval(i, U, g)


def mirrorball_step(i, S, U, g, dt):
    if dt <= 0:
        return S.copy()
    return mirrorball_eval(i, U, g)


def mirrorball_place(i, S, U, g):
    np = _np()
    k, a = unpack(S[:, 3])
    return np.stack([S[:, 0], S[:, 1], np.zeros(len(S))], -1), k, a, a > 0.0


# ------------------------------------------------------------------ nbody (FX7c card 12, lane G 27 Oct)
def nb_n(U, g):
    return min(max(int(U['uM0'][0] + 0.5), 2), min(g.NPTS, 4096))


def nb_g(U):
    return min(max(int(U['uM0'][1] + 0.5), 1), 2)


def nb_mass(j, U, g):
    np = _np()
    G, N = nb_g(U), nb_n(U, g)
    j = np.asarray(j)
    return np.where(j < G, U['uM1'][2], U['uM1'][3] * G / float(max(N - G, 1)))


def nb_gal(j, U):
    np = _np()
    G = nb_g(U)
    j = np.asarray(j, dtype=np.int64)
    return np.where(j < G, j, (j - G) % G)


def nbody_seed(i, U, g):
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    M0, M1, M2, M3 = U['uM0'], U['uM1'], U['uM2'], U['uM3']
    G, N = nb_g(U), nb_n(U, g)
    out = np.zeros((len(i), 4))
    gal = nb_gal(i, U)
    sg = np.where(gal == 0, -1.0, 1.0) if G == 2 else np.zeros(len(i))
    C = np.stack([sg * 0.5 * M2[2], sg * 0.5 * M2[1]], -1)
    V = np.stack([np.zeros(len(i)), -sg * 0.5 * M2[3]], -1)
    h = M2[0]
    r = -h * np.log(1.0 - 0.95 * rnd(i, 21, g))
    a = TAU * rnd(i, 22, g)
    x = r / h
    md = M1[3] * (1.0 - (1.0 + x) * np.exp(-x))
    e2 = M0[3] * M0[3]
    e2c = e2 + U['uM4'][3] ** 2
    vc = np.sqrt(M0[2] * r * r * (M1[2] / np.power(r * r + e2c, 1.5) + md / np.power(r * r + e2, 1.5)))
    spin = np.where((gal == 1) & (int(M3[0] + 0.5) == 1), -1.0, 1.0)
    pos = C + r[:, None] * np.stack([np.cos(a), np.sin(a)], -1)
    vel = V + (spin * vc)[:, None] * np.stack([-np.sin(a), np.cos(a)], -1)
    core = i < G
    pos[core], vel[core] = C[core], V[core]
    body = i < N
    out[body, :2], out[body, 2:] = pos[body], vel[body]
    return out


def nbody_step(i, S, U, g, dt, full=None):
    """One symplectic Euler step of the bodies in i (all pairs vs the full state); stars stay 0."""
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    F0 = full if full is not None else S
    N = nb_n(U, g)
    out = np.zeros((len(i), 4))
    if dt <= 0:
        out[i < N] = S[i < N]
        return out
    Q = F0[:N, :2]
    m = nb_mass(np.arange(N), U, g)
    e2 = U['uM0'][3] ** 2
    c2 = U['uM4'][3] ** 2
    G = nb_g(U)
    core = np.arange(N) < G
    h = dt * U['uM1'][0]
    nd = np.where(i < N)[0]
    for c0 in range(0, len(nd), 256):
        sl = nd[c0:c0 + 256]
        p = S[sl, :2]
        d = Q[None, :, :] - p[:, None, :]
        r2 = (d * d).sum(-1) + e2 + np.where(core[None, :] | (i[sl] < G)[:, None], c2, 0.0)
        acc = (d * (m[None, :] / (r2 * np.sqrt(r2)))[..., None]).sum(1)
        v = S[sl, 2:] + U['uM0'][2] * acc * h
        out[sl, 2:] = v
        out[sl, :2] = p + v * h
    return out


def nbody_place(i, S, U, g):
    """S = the whole state (rows = point index): bodies, then stars on random disc bodies."""
    np = _np()
    i = np.asarray(i, dtype=np.int64)
    M3, M4 = U['uM3'], U['uM4']
    N, G = nb_n(U, g), nb_g(U)
    j = i.copy()
    star = i >= N
    jj = G + np.floor(rnd(i, 31, g) * max(N - G, 1)).astype(np.int64)
    j = np.where(star, np.minimum(jj, N - 1), i)
    b = S[j]
    rr = M3[2] * np.sqrt(rnd(i, 32, g))
    an = TAU * rnd(i, 33, g)
    offx = np.where(star, rr * np.cos(an), 0.0)
    offz = np.where(star, rr * np.sin(an), 0.0)
    offy = (rnd(i, 34, g) * 2.0 - 1.0) * M3[1]
    P = np.stack([b[:, 0] + offx, offy, b[:, 1] + offz], -1)
    cb = int(M3[3] + 0.5)
    if cb == 0:
        k = np.sqrt((b[:, 2:] ** 2).sum(-1)) * 0.5 * M4[2]
    elif cb == 1:
        k = (nb_gal(j, U) + 0.5) * 0.5
    elif cb == 2:
        k = np.sqrt((b[:, :2] ** 2).sum(-1)) * M4[2]
    else:
        k = rnd(j, 5, g)
    a = np.where(star, M4[1], M4[0])
    return P, k, a, np.ones(len(i), bool)


# ------------------------------------------------------------------ dispatch
KIND = {'density2d': '2d', 'attractor3d': '3d', 'streamlines': '2d', 'form': '3d', 'flame': '2d', 'lsystem': '2d',
        'graph': '2d', 'sparkle': '2d', 'polytope4d': '3d', 'hyperspace': '2d', 'mirrorball': '2d', 'nbody': '3d'}
USES_IMG = ('streamlines', 'form', 'sparkle')
USES_AUX = ('lsystem', 'polytope4d')
USES_FULL = ('graph', 'nbody')


def _kw(module, img, aux, full, step_=False):
    kw = {}
    if module in USES_IMG:
        kw['img'] = img
    if module in USES_AUX:
        kw['aux'] = aux
    if step_ and module in USES_FULL:
        kw['full'] = full
    return kw


def seed(module, i, U, g, img=None, aux=None):
    return globals()[module + '_seed'](i, U, g, **_kw(module, img, aux, None))


def step(module, i, S, U, g, dt, img=None, aux=None, full=None):
    return globals()[module + '_step'](i, S, U, g, dt, **_kw(module, img, aux, full, True))


def place(module, i, S, U, g):
    """World P (n, 3), palette coordinate k, brightness a, ok mask (the module's pt_place)."""
    return globals()[module + '_place'](i, S, U, g)


def points_render(module, S, U, W, H, idx=None, img=None):
    """Expected render (H, W, 4) of the state S (n, 4) of points idx: rgb = pal * a * I, alpha = a (1-px points,
    additive) == mat vertex + pixel at Size 1. U = the MAT's uniforms. img (h, w, 4) = in1 (form 'input' colours)."""
    np = _np()
    n = len(S)
    idx = np.arange(n) if idx is None else np.asarray(idx)
    g = Glob(U, asp=U['uV2'][0] / max(U['uV2'][1], 1.0), npts=int(U['uV'][0] + 0.5))
    P, k, a, ok = place(module, idx, S, U, g)
    ndc, fade, vis = project(KIND[module], idx, P, U, g)
    a = a * fade
    use = ok & vis & (idx < int(U['uV'][0] + 0.5))
    col = ptpal(k, U, g)
    if module == 'form' and int(U['uM3'][2] + 0.5) == 4:
        if img is None:
            col = np.zeros((n, 3))
        else:
            _B, _N, uvw = fm_base(idx, U, g)
            col = bilinear_hold(img, uvw[:, 0], uvw[:, 1])[:, :3]
    if module == 'sparkle' and int(U['uM2'][2] + 0.5) == 1:
        if img is None:
            col = np.zeros((n, 3))
        else:
            col = bilinear_hold(img, S[:, 0] / (2.0 * g.ASP) + 0.5, S[:, 1] * 0.5 + 0.5)[:, :3]
    w_rgb = col * (a * U['uV'][3])[:, None]
    out = np.zeros((H, W, 4))
    cnt, okp = count_image(ndc[use], a[use], W, H)
    out[..., 3] = cnt
    for c_ in range(3):
        out[..., c_], _o = count_image(ndc[use], w_rgb[use, c_], W, H)
    return out, int(okp.sum())
