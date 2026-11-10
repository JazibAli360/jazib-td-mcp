# fx_film_colour_logic - pure maths of FX_film module 'colour' (FX3 S1 ACES-style pipeline, S2 LUT load + A/B bank,
# S3 grade: exposure, white balance, ASC CDL, lift/gamma/gain, contrast, saturation / vibrance, S5 log view / split).
# Colour spaces = (transfer curve, primaries); working space = ACEScg (AP1 linear). Matrices are computed here from
# the primaries + Bradford CAT and written into the GLSL as constants (one source). `.cube` parser + strip layout are
# used by the Script TOPs in TD (exec'd by path) and by the numpy reference. ASCII only.
import math
import os

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'

SPACES = ['srgb', 'rec709', 'linear', 'acescg', 'logc3', 'slog3', 'acescct']
SPACE_LABELS = ['sRGB', 'Rec.709 (camera OETF)', 'Linear Rec.709/sRGB', 'ACEScg (AP1 linear)', 'ARRI LogC3 (EI800, AWG3)',
                'Sony S-Log3 (S-Gamut3.Cine)', 'ACEScct (AP1)']
CURVE = {'srgb': 0, 'rec709': 1, 'linear': 2, 'acescg': 2, 'logc3': 3, 'slog3': 4, 'acescct': 5}
PRIM_OF = {'srgb': 'rec709', 'rec709': 'rec709', 'linear': 'rec709', 'acescg': 'ap1', 'logc3': 'awg3',
           'slog3': 'sgamut3cine', 'acescct': 'ap1'}
PRIMARIES = {   # (R, G, B, white) xy
    'rec709': ((0.64, 0.33), (0.30, 0.60), (0.15, 0.06), (0.3127, 0.3290)),
    'ap1': ((0.713, 0.293), (0.165, 0.830), (0.128, 0.044), (0.32168, 0.33767)),
    'awg3': ((0.6840, 0.3130), (0.2210, 0.8480), (0.0861, -0.1020), (0.3127, 0.3290)),
    'sgamut3cine': ((0.766, 0.275), (0.225, 0.800), (0.089, -0.087), (0.3127, 0.3290)),
}
PRIM_ORDER = ['rec709', 'awg3', 'sgamut3cine', 'ap1']     # primaries index in the GLSL (ap1 = identity)
AP1_Y = None                                               # AP1 luminance weights (filled below)
BRADFORD = [[0.8951, 0.2664, -0.1614], [-0.7502, 1.7135, 0.0367], [0.0389, -0.0685, 1.0296]]


# ------------------------------------------------------------------ 3x3 helpers (pure python, no numpy needed)
def mmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def mvec(m, v):
    return [m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3)]


def minv(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    return [[(e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det],
            [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det],
            [(d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det]]


def xyz(xy):
    x, y = xy
    return [x / y, 1.0, (1.0 - x - y) / y]


def rgb2xyz(name):
    r, g, b, w = PRIMARIES[name]
    M = [list(col) for col in zip(xyz(r), xyz(g), xyz(b))]
    S = mvec(minv(M), xyz(w))
    return [[M[i][j] * S[j] for j in range(3)] for i in range(3)]


def cat(src_w, dst_w):
    """Bradford chromatic adaptation XYZ(src white) -> XYZ(dst white)."""
    if abs(src_w[0] - dst_w[0]) < 1e-9 and abs(src_w[1] - dst_w[1]) < 1e-9:
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    s, d = mvec(BRADFORD, xyz(src_w)), mvec(BRADFORD, xyz(dst_w))
    D = [[d[0] / s[0], 0.0, 0.0], [0.0, d[1] / s[1], 0.0], [0.0, 0.0, d[2] / s[2]]]
    return mmul(minv(BRADFORD), mmul(D, BRADFORD))


def conv(src, dst):
    """RGB(src primaries) -> RGB(dst primaries), white adapted (Bradford)."""
    return mmul(minv(rgb2xyz(dst)), mmul(cat(PRIMARIES[src][3], PRIMARIES[dst][3]), rgb2xyz(src)))


AP1_Y = rgb2xyz('ap1')[1]
TO_AP1 = dict((p, conv(p, 'ap1')) for p in PRIM_ORDER)
FROM_AP1 = dict((p, conv('ap1', p)) for p in PRIM_ORDER)


# ------------------------------------------------------------------ transfer curves (code value <-> linear)
LOGC3 = (0.010591, 5.555556, 0.052272, 0.247190, 0.385537, 5.367655, 0.092809)    # cut a b c d e f (EI 800)
SL3_B = 171.2102946929


def decode(v, curve):
    if curve == 0:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    if curve == 1:
        return v / 4.5 if v < 0.081 else ((v + 0.099) / 1.099) ** (1.0 / 0.45)
    if curve == 3:
        cut, a, b, c, d, e, f = LOGC3
        return (10.0 ** ((v - d) / c) - b) / a if v > e * cut + f else (v - f) / e
    if curve == 4:
        return (10.0 ** ((v * 1023.0 - 420.0) / 261.5) * 0.19 - 0.01 if v >= SL3_B / 1023.0
                else (v * 1023.0 - 95.0) * 0.01125 / (SL3_B - 95.0))
    if curve == 5:
        return (v - 0.0729055341958355) / 10.5402377416545 if v <= 0.155251141552511 else 2.0 ** (v * 17.52 - 9.72)
    return v


def encode(x, curve):
    if curve == 0:
        x = max(x, 0.0)
        return x * 12.92 if x <= 0.0031308 else 1.055 * x ** (1.0 / 2.4) - 0.055
    if curve == 1:
        x = max(x, 0.0)
        return 4.5 * x if x < 0.018 else 1.099 * x ** 0.45 - 0.099
    if curve == 3:
        cut, a, b, c, d, e, f = LOGC3
        return c * math.log10(max(a * x + b, 1e-10)) + d if x > cut else e * x + f
    if curve == 4:
        return ((420.0 + math.log10(max((x + 0.01) / 0.19, 1e-10)) * 261.5) / 1023.0 if x >= 0.01125
                else (x * (SL3_B - 95.0) / 0.01125 + 95.0) / 1023.0)
    if curve == 5:
        return 10.5402377416545 * x + 0.0729055341958355 if x <= 0.0078125 else (math.log2(max(x, 1e-10)) + 9.72) / 17.52
    return x


def to_work(rgb, space):
    lin = [decode(v, CURVE[space]) for v in rgb]
    return mvec(TO_AP1[PRIM_OF[space]], lin)


def from_work(rgb, space):
    lin = mvec(FROM_AP1[PRIM_OF[space]], rgb)
    return [encode(v, CURVE[space]) for v in lin]


# ------------------------------------------------------------------ grade (working AP1 linear)
def wb_gains(temp, tint):
    """Warm/cool + green/magenta gains normalised so AP1 luminance of white stays 1."""
    g = [2.0 ** (0.25 * temp), 2.0 ** (-0.25 * tint), 2.0 ** (-0.25 * temp)]
    n = sum(AP1_Y[i] * g[i] for i in range(3))
    return [v / n for v in g]


def lgg(x, lift, gamma, gain):
    y = gain * (x + lift * (1.0 - x))
    return math.copysign(abs(y) ** (1.0 / max(gamma, 1e-4)), y)


def cdl(x, slope, offset, power):
    y = x * slope + offset
    return y ** power if y > 0 else y


def grade(w, P):
    """w = AP1 linear rgb -> graded AP1 linear rgb. P keys = the module pars (RGB pars as Name + r/g/b)."""
    e = 2.0 ** P.get('Exposure', 0.0)
    g = wb_gains(P.get('Temperature', 0.0), P.get('Tint', 0.0))
    x = [w[i] * e * g[i] for i in range(3)]
    logsp = P.get('Gradespace', 'linear') == 'log'
    if logsp:
        x = [encode(v, 5) for v in x]
    for i, ch in enumerate('rgb'):
        v = cdl(x[i], P.get('Slope' + ch, 1.0), P.get('Offset' + ch, 0.0), P.get('Power' + ch, 1.0))
        v = lgg(v, P.get('Lift', 0.0) + P.get('Liftc' + ch, 0.0), P.get('Gamma', 1.0) * P.get('Gammac' + ch, 1.0),
                P.get('Gain', 1.0) * P.get('Gainc' + ch, 1.0))
        x[i] = v
    k, pv = P.get('Contrast', 1.0), P.get('Pivot', 0.18)
    if logsp:
        pl = encode(pv, 5)
        x = [(v - pl) * k + pl for v in x]
        x = [decode(v, 5) for v in x]
    else:
        x = [math.copysign(pv * (abs(v) / pv) ** k, v) for v in x]
    y = sum(AP1_Y[i] * x[i] for i in range(3))
    mx, mn = max(x), min(x)
    chroma = (mx - mn) / mx if mx > 1e-6 else 0.0
    s = P.get('Saturation', 1.0) * (1.0 + P.get('Vibrance', 0.0) * (1.0 - min(max(chroma, 0.0), 1.0)))
    return [y + (v - y) * s for v in x]


# ------------------------------------------------------------------ .cube parse + strip layout (Script TOPs use these)
def parse_cube(text):
    """-> dict(n, table[b][g][r] = (r, g, b) as a flat list in file order, dmin, dmax, title, kind '3d' / '1d')."""
    n3 = n1 = None
    dmin, dmax, title, data = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0], '', []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        t = s.split()
        k = t[0].upper()
        if k == 'TITLE':
            title = s[5:].strip().strip('"')
        elif k == 'LUT_3D_SIZE':
            n3 = int(t[1])
        elif k == 'LUT_1D_SIZE':
            n1 = int(t[1])
        elif k == 'DOMAIN_MIN':
            dmin = [float(v) for v in t[1:4]]
        elif k == 'DOMAIN_MAX':
            dmax = [float(v) for v in t[1:4]]
        elif k in ('LUT_1D_INPUT_RANGE', 'LUT_3D_INPUT_RANGE'):
            dmin, dmax = [float(t[1])] * 3, [float(t[2])] * 3
        else:
            try:
                data.append((float(t[0]), float(t[1]), float(t[2])))
            except (ValueError, IndexError):
                raise ValueError('bad .cube line: %r' % s[:60])
    if n3:
        if len(data) != n3 ** 3:
            raise ValueError('LUT_3D_SIZE %d needs %d rows, got %d' % (n3, n3 ** 3, len(data)))
        return {'n': n3, 'data': data, 'dmin': dmin, 'dmax': dmax, 'title': title, 'kind': '3d'}
    if n1:
        if len(data) != n1:
            raise ValueError('LUT_1D_SIZE %d needs %d rows, got %d' % (n1, n1, len(data)))
        return {'n': n1, 'data': data, 'dmin': dmin, 'dmax': dmax, 'title': title, 'kind': '1d'}
    raise ValueError('no LUT_3D_SIZE / LUT_1D_SIZE')


def one_d_to_3d(c, n=33):
    """A 1D LUT as an n^3 3D table (per channel curve on the grid; trilinear between grid points)."""
    d, n1 = c['data'], c['n']

    def curve(ch, v):          # v in [0, 1] of the domain
        x = min(max(v, 0.0), 1.0) * (n1 - 1)
        i = min(int(x), n1 - 2)
        f = x - i
        return d[i][ch] + (d[i + 1][ch] - d[i][ch]) * f
    out = []
    for b in range(n):
        for g in range(n):
            for r in range(n):
                out.append((curve(0, r / (n - 1.0)), curve(1, g / (n - 1.0)), curve(2, b / (n - 1.0))))
    return {'n': n, 'data': out, 'dmin': c['dmin'], 'dmax': c['dmax'], 'title': c['title'], 'kind': '1d'}


def cube_strip(c):
    """float32 (N + 1, N * N, 4): texel (b N + r, g) = LUT(r, g, b); top row header: (0) dmin + N, (1) dmax + valid.
    Row 0 = the bottom row in TD (copyNumpyArray), = texelFetch y 0."""
    if c is None:
        a = np.zeros((3, 4, 4), np.float32)
        a[2, 0, 3] = 2.0
        return a                                       # valid 0: the shader skips the slot
    if c['kind'] == '1d' and len(c['data']) != c['n'] ** 3:
        c = one_d_to_3d(c)
    n = c['n']
    t = np.asarray(c['data'], np.float32).reshape(n, n, n, 3)       # [b][g][r]
    a = np.zeros((n + 1, n * n, 4), np.float32)
    a[:n, :, :3] = t.transpose(1, 0, 2, 3).reshape(n, n * n, 3)      # row g, column b * n + r
    a[:n, :, 3] = 1.0
    a[n, 0] = [c['dmin'][0], c['dmin'][1], c['dmin'][2], n]
    a[n, 1] = [c['dmax'][0], c['dmax'][1], c['dmax'][2], 1.0]
    return a


def write_cube(path, fn, n=17, title='fx_film test'):
    """Bake fn(r, g, b) -> (r, g, b) into a .cube (red fastest). Test LUTs for the live check."""
    with open(path, 'w') as fh:
        fh.write('TITLE "%s"\nLUT_3D_SIZE %d\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n' % (title, n))
        for b in range(n):
            for g in range(n):
                for r in range(n):
                    fh.write('%.6f %.6f %.6f\n' % tuple(fn(r / (n - 1.0), g / (n - 1.0), b / (n - 1.0))))


def lut_apply(strip, v, interp='tetrahedral'):
    """Mirror of the GLSL lookup on one rgb value (strip = cube_strip output)."""
    h = strip.shape[0]
    n = int(strip[h - 1, 0, 3])
    if strip[h - 1, 1, 3] < 0.5:
        return list(v)
    dmin, dmax = strip[h - 1, 0, :3], strip[h - 1, 1, :3]
    x = [min(max((v[i] - dmin[i]) / max(dmax[i] - dmin[i], 1e-9), 0.0), 1.0) * (n - 1) for i in range(3)]
    i0 = [min(int(math.floor(x[i])), n - 2) for i in range(3)]
    f = [x[i] - i0[i] for i in range(3)]

    def C(dr, dg, db):
        r, g, b = i0[0] + dr, i0[1] + dg, i0[2] + db
        return np.asarray(strip[g, b * n + r, :3], np.float64)
    if interp == 'trilinear':
        c00 = C(0, 0, 0) * (1 - f[0]) + C(1, 0, 0) * f[0]
        c10 = C(0, 1, 0) * (1 - f[0]) + C(1, 1, 0) * f[0]
        c01 = C(0, 0, 1) * (1 - f[0]) + C(1, 0, 1) * f[0]
        c11 = C(0, 1, 1) * (1 - f[0]) + C(1, 1, 1) * f[0]
        c0 = c00 * (1 - f[1]) + c10 * f[1]
        c1 = c01 * (1 - f[1]) + c11 * f[1]
        return list(c0 * (1 - f[2]) + c1 * f[2])
    fr, fg, fb = f
    if fr >= fg:
        if fg >= fb:
            o = (1 - fr) * C(0, 0, 0) + (fr - fg) * C(1, 0, 0) + (fg - fb) * C(1, 1, 0) + fb * C(1, 1, 1)
        elif fr >= fb:
            o = (1 - fr) * C(0, 0, 0) + (fr - fb) * C(1, 0, 0) + (fb - fg) * C(1, 0, 1) + fg * C(1, 1, 1)
        else:
            o = (1 - fb) * C(0, 0, 0) + (fb - fr) * C(0, 0, 1) + (fr - fg) * C(1, 0, 1) + fg * C(1, 1, 1)
    else:
        if fb >= fg:
            o = (1 - fb) * C(0, 0, 0) + (fb - fg) * C(0, 0, 1) + (fg - fr) * C(0, 1, 1) + fr * C(1, 1, 1)
        elif fb >= fr:
            o = (1 - fg) * C(0, 0, 0) + (fg - fb) * C(0, 1, 0) + (fb - fr) * C(0, 1, 1) + fr * C(1, 1, 1)
        else:
            o = (1 - fg) * C(0, 0, 0) + (fg - fr) * C(0, 1, 0) + (fr - fb) * C(1, 1, 0) + fb * C(1, 1, 1)
    return list(o)


# ------------------------------------------------------------------ the whole pass (mirror of the GLSL)
def _rl():
    ns = {}
    exec(open(os.path.join(HERE, 'fx_film_logic.py')).read(), ns)
    return ns


def colour_px(rgb, P, lut_a=None, lut_b=None):
    """One pixel through the colour pass (no split line). Returns the output code values."""
    ins = P.get('Inspace', 'srgb')
    w = to_work(rgb, ins)
    w = grade(w, P)
    if (lut_a is not None or lut_b is not None) and P.get('Lutmix', 1.0) > 0:
        lin, lout = P.get('Lutin', 'logc3'), P.get('Lutout', 'same')
        lout = lin if lout == 'same' else lout
        v = from_work(w, lin)
        interp = P.get('Interp', 'tetrahedral')
        la = lut_apply(lut_a, v, interp) if lut_a is not None else list(v)
        lb = lut_apply(lut_b, v, interp) if lut_b is not None else la
        mo = P.get('Lutmorph', 0.0)
        l = [la[i] + (lb[i] - la[i]) * mo for i in range(3)]
        v = [v[i] + (l[i] - v[i]) * P.get('Lutmix', 1.0) for i in range(3)]
        w = to_work(v, lout)
    view, outs = P.get('Viewmode', 'none'), P.get('Outspace', 'same')
    if view == 'aces':
        R = _rl()
        lin709 = mvec(FROM_AP1['rec709'], w)
        o = [R['lin2srgb'](c) for c in R['aces_hill'](lin709)]
    else:
        outs = ins if outs == 'same' else outs
        lin = mvec(FROM_AP1[PRIM_OF[outs]], w)
        gc = P.get('Gamutclip', 0.0)
        if gc > 0:
            y = sum(AP1_Y[i] * w[i] for i in range(3))
            mn = min(lin)
            if mn < 0 and y > mn:
                t = gc * (-mn) / (y - mn)
                lin = [c + (y - c) * t for c in lin]
        o = [encode(c, CURVE[outs]) for c in lin]
    a = P.get('Amount', 1.0)
    return [rgb[i] + (o[i] - rgb[i]) * a for i in range(3)]


def expected_numbers():
    ex = {}
    ex['col_srgb_to_ap1_r'] = [round(v, 6) for v in TO_AP1['rec709'][0]]
    ex['col_logc3_018'] = round(encode(0.18, 3), 4)
    ex['col_slog3_018'] = round(encode(0.18, 4), 4)
    ex['col_acescct_018'] = round(encode(0.18, 5), 4)
    # neutral grey 0.18 linear in -> LogC3 view out (S5 log view)
    ex['col_logview_018'] = round(colour_px([0.18] * 3, {'Inspace': 'linear', 'Outspace': 'logc3'})[0], 4)
    ex['col_aces_view_018'] = round(colour_px([0.18] * 3, {'Inspace': 'linear', 'Viewmode': 'aces'})[0], 4)
    ex['col_exp1_018'] = round(colour_px([0.18] * 3, {'Inspace': 'linear', 'Exposure': 1.0})[0], 4)
    ex['col_cdl_slope2_offs'] = round(colour_px([0.1] * 3, {'Inspace': 'linear', 'Sloper': 2.0, 'Offsetr': 0.05})[0], 4)
    ex['col_lgg_lift01_gain12'] = round(colour_px([0.5] * 3, {'Inspace': 'linear', 'Lift': 0.1, 'Gain': 1.2})[0], 4)
    ex['col_wb_warm1'] = [round(v, 4) for v in colour_px([0.18] * 3, {'Inspace': 'linear', 'Temperature': 1.0})]
    return ex
