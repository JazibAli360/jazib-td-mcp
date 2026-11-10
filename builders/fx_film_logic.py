# fx_film_logic - pure maths of the FX_film modules (no TD). The GLSL in builders/fx_film_<module>.py mirrors these
# functions; test/test_fx_film.py checks them offline and docs/builds/fx_film.md quotes the numbers they predict
# (`expected_numbers()`), so a live lane only compares. The numpy helpers at the bottom (`an_*`) are the live-check
# analysers: the live lane feeds them `numpyArray()` reads (row 0 = bottom row, x right, y up = the shaders' pixel
# coordinates) and compares with the expected numbers. scalar parts need no numpy. ASCII only.
import math

try:
    import numpy as np
except ImportError:          # pragma: no cover - only the analysers and the references need numpy
    np = None

M32 = 0xffffffff
W0, H0 = 1080, 1920          # build resolution (CLAUDE.md: vertical 1080x1920)


# ------------------------------------------------------------------ colour
def luma(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def srgb2lin(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def lin2srgb(v):
    v = max(v, 0.0)
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1.0 / 2.4) - 0.055


# ------------------------------------------------------------------ hash + noise (rack GLSL_LIB, uint32 exact)
def lb32(x):
    x &= M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def hsh(cx, cy, s):
    """GLSL hsh(ivec2(cx, cy), uint s) in [0, 1)."""
    return lb32((((cx & M32) * 1597334677) & M32) ^ lb32((cy & M32) ^ ((s * 2654435761) & M32))) / 4294967296.0


def hsh3(cx, cy, cz, s):
    return hsh(cx, cy, (s ^ lb32((cz + 0x9e3779b9) & M32)) & M32)


def smooth(f):
    return f * f * (3.0 - 2.0 * f)


def vnoise(x, y, s):
    ix, iy = int(math.floor(x)), int(math.floor(y))
    fx, fy = smooth(x - ix), smooth(y - iy)
    a, b = hsh(ix, iy, s), hsh(ix + 1, iy, s)
    c, d = hsh(ix, iy + 1, s), hsh(ix + 1, iy + 1, s)
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy


def fbm(x, y, s, octaves):
    v, a, n = 0.0, 0.5, 0.0
    for k in range(octaves):
        v += a * vnoise(x, y, (s + k * 101) & M32)
        n += a
        x, y = x * 2.03 + 17.1, y * 2.03 + 17.1
        a *= 0.5
    return v / n


# value-noise variance (position-averaged) of uniform lattice values interpolated with smoothstep: per axis
# integral of (1-s)^2 + s^2 over [0, 1] = 26/35 (exact), so a D-dimensional value noise has var (1/12) (26/35)^D.
VN_AXIS = 26.0 / 35.0


def vn_norm(dims):
    """Multiplier that makes (vnoise - 0.5) unit variance."""
    return 1.0 / math.sqrt(VN_AXIS ** dims / 12.0)


HASH_NORM = math.sqrt(12.0)  # (hash - 0.5) * sqrt(12) = unit variance


# ------------------------------------------------------------------ soft knee (StageLab JZB_Color_Bloom prefilter)
def knee_w(br, thr, kn):
    """Weight w so that excess = colour * w (br = max channel or luma)."""
    rq = min(max(br - thr + kn, 0.0), 2.0 * kn)
    rq = rq * rq / (4.0 * kn + 1e-5)
    return max(rq, br - thr) / max(br, 1e-5)


def knee_excess(c, thr, kn, by_luma=False):
    br = luma(c) if by_luma else max(c[:3])
    w = knee_w(br, thr, kn)
    return [ch * w for ch in c[:3]]


# ------------------------------------------------------------------ pyramid (padded mips, T-116 (1))
def pad_dims(w, h, scale, mult):
    """(valid w, valid h, padded w, padded h) of the extract buffer: ceil(size/scale), padded to a multiple of mult so
    every mip level up to log2(mult) is exact (T-116 (1))."""
    vw, vh = -(-w // scale), -(-h // scale)
    return vw, vh, -(-vw // mult) * mult, -(-vh // mult) * mult


def level_weights(radius_px, spread, scale=2, levels=8):
    """Normalised weights of mip levels 0..levels-1 for a glow of `radius_px` (full-res px). Level k of a buffer at
    1/scale resolution blurs ~scale * 2^k px; the centre level kc = log2(radius / scale)."""
    kc = math.log2(max(radius_px, 1e-3) / scale)
    sp = max(spread, 0.05)
    w = [math.exp(-0.5 * ((k - kc) / sp) ** 2) for k in range(levels)]
    s = sum(w)
    return [x / s for x in w] if s > 0 else [1.0] + [0.0] * (levels - 1)


# ------------------------------------------------------------------ tone curves (tonecurve module)
CURVES = ['off', 'aces_fit', 'aces_hill', 'hable', 'reinhard', 'lottes']


def aces_fit(x):
    """Narkowicz 2016 ACES fit (CC0/MIT)."""
    return min(max((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0), 1.0)


ACES_IN = [[0.59719, 0.35458, 0.04823], [0.07600, 0.90834, 0.01566], [0.02840, 0.13383, 0.83777]]
ACES_OUT = [[1.60475, -0.53108, -0.07367], [-0.10208, 1.10813, -0.00605], [-0.00327, -0.07276, 1.07602]]


def _mat(m, v):
    return [m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3)]


def aces_hill(rgb):
    """Stephen Hill's ACES RRT+ODT fit (sRGB in/out, linear)."""
    v = _mat(ACES_IN, rgb)
    v = [(a * (a + 0.0245786) - 0.000090537) / (a * (0.983729 * a + 0.4329510) + 0.238081) for a in v]
    return [min(max(a, 0.0), 1.0) for a in _mat(ACES_OUT, v)]


def hable_f(x):
    A, B, C, D, E, F = 0.15, 0.50, 0.10, 0.20, 0.02, 0.30
    return ((x * (A * x + C * B) + D * E) / (x * (A * x + B) + D * F)) - E / F


def hable(x, white):
    return hable_f(x) / hable_f(white)


def reinhard(x, white):
    return x * (1.0 + x / (white * white)) / (1.0 + x)


def lottes_bc(a, d, hdr_max, mid_in=0.18, mid_out=0.18):
    """Lottes 2016 (AMD 'Advanced techniques and optimization of HDR color pipelines') b, c for f(x) = x^a/(x^ad b + c)."""
    ad = a * d
    den = (hdr_max ** ad - mid_in ** ad) * mid_out
    b = (-(mid_in ** a) + (hdr_max ** a) * mid_out) / den
    c = ((hdr_max ** ad) * (mid_in ** a) - (hdr_max ** a) * (mid_in ** ad) * mid_out) / den
    return b, c


def lottes(x, a, d, hdr_max):
    b, c = lottes_bc(a, d, hdr_max)
    x = max(x, 0.0)
    return (x ** a) / ((x ** (a * d)) * b + c)


def curve1(x, curve, white=11.2, la=1.6, ld=0.977):
    """One channel through `curve` (aces_hill is 3-channel: use tone_rgb)."""
    if curve == 'aces_fit':
        return aces_fit(x)
    if curve == 'hable':
        return hable(x, white)
    if curve == 'reinhard':
        return reinhard(x, white)
    if curve == 'lottes':
        return lottes(x, la, ld, white)
    return x


def contrast(x, k, pivot=0.18):
    return pivot * (max(x, 0.0) / pivot) ** k


def tone_rgb(rgb, P):
    """tonecurve maths for one linear rgb (P = par dict): exposure, contrast, curve (per channel or luminance)."""
    e = 2.0 ** P.get('Exposure', 0.0)
    v = [contrast(c * e, P.get('Contrast', 1.0), P.get('Pivot', 0.18)) for c in rgb]
    cv = P.get('Curve', 'aces_fit')
    if cv == 'aces_hill':
        return aces_hill(v)
    if P.get('Curvemode', 'channel') == 'luma':
        y = luma(v)
        t = curve1(y, cv, P.get('Whitepoint', 11.2), P.get('Lcontrast', 1.6), P.get('Shoulder', 0.977))
        return [c * t / max(y, 1e-6) for c in v]
    return [curve1(c, cv, P.get('Whitepoint', 11.2), P.get('Lcontrast', 1.6), P.get('Shoulder', 0.977)) for c in v]


# ------------------------------------------------------------------ display dither (tonecurve Display page)
DITHERS = ['off', 'bayer8', 'ign', 'white', 'tpdf']


def bayer8():
    """8x8 Bayer index matrix (0..63), m[y][x]; the GLSL builds the same by bit interleave."""
    m = [[0] * 8 for _ in range(8)]
    for y in range(8):
        for x in range(8):
            v, xx, yy = 0, x, x ^ y
            for bit in range(3):
                v |= ((yy >> bit) & 1) << (2 * (2 - bit) + 1)
                v |= ((xx >> bit) & 1) << (2 * (2 - bit))
            m[y][x] = v
    return m


def bayer_index(x, y):
    """GLSL bayer8(): same bit interleave as bayer8()[y & 7][x & 7]."""
    xx, yy = x & 7, (x ^ y) & 7
    v = 0
    for bit in range(3):
        v |= ((yy >> bit) & 1) << (2 * (2 - bit) + 1)
        v |= ((xx >> bit) & 1) << (2 * (2 - bit))
    return v


def ign(x, y):
    """Jimenez interleaved gradient noise in [0, 1)."""
    f = math.modf(0.06711056 * x + 0.00583715 * y)[0]
    return math.modf(52.9829189 * f)[0]


def quantize(v, bits, t, amp=1.0):
    """Ordered / random dither: floor(v * L + 0.5 + amp (t - 0.5)) / L, t in [0, 1); amp 1 = classic rect dither."""
    L = float((1 << int(bits)) - 1)
    return math.floor(v * L + 0.5 + amp * (t - 0.5)) / L


def tile_mean_bayer(v, bits):
    """Mean of an 8x8 Bayer-dithered tile of constant v: v rounded to 1/64 LSB (exact, amp 1)."""
    return sum(quantize(v, bits, (k + 0.5) / 64.0) for k in range(64)) / 64.0


# ------------------------------------------------------------------ stock (film-stock engine)
PROCESSES = ['print', 'bleach', 'cross', 'tech2', 'tech3', 'bw']


def stock_curve(x, slope, offset, ktoe, kshoulder, white):
    """Per-channel density S-curve in stops around 0.18: Lc = slope * log2(x / 0.18) + offset, then a logistic in
    stops with toe / shoulder steepness (blended through Lc 0) and white `white`; 0.18 -> 0.18 at offset 0."""
    lc = slope * math.log2(max(x, 1e-6) / 0.18) + offset
    t = smooth(min(max((lc + 1.0) * 0.5, 0.0), 1.0))
    k = ktoe + (kshoulder - ktoe) * t
    return white / (1.0 + 2.0 ** (-lc * k) * (white / 0.18 - 1.0))


def bleach(base, opacity):
    """Bleach bypass (the classic overlay-with-own-luma shader)."""
    lum = luma(base)
    L = min(1.0, max(0.0, 10.0 * (lum - 0.45)))
    r1 = [2.0 * b * lum for b in base]
    r2 = [1.0 - 2.0 * (1.0 - lum) * (1.0 - b) for b in base]
    new = [a + (b - a) * L for a, b in zip(r1, r2)]
    return [b + (n - b) * opacity for b, n in zip(base, new)]


def sig(v, k):
    """Cross-process S curve on a display value (GLSL sig)."""
    v = min(max(v, 0.0), 1.0)
    return 0.5 * (2 * v) ** k if v < 0.5 else 1.0 - 0.5 * (2 - 2 * v) ** k


def cross_d(d, amount):
    """Cross process on display (sRGB-encoded) rgb: R steep, G mild, B flattened + lifted."""
    tgt = [sig(d[0], 1.5), sig(d[1], 1.2), 0.25 + 0.5 * d[2]]
    return [a + (b - a) * amount for a, b in zip(d, tgt)]


def tech2(rgb, dye):
    """Two-strip: red record -> `dye` (red-orange), green record ((g + b) / 2) -> its complement (1 - dye)."""
    rr, gr = rgb[0], 0.5 * (rgb[1] + rgb[2])
    return [rr * d + gr * (1.0 - d) for d in dye]


def tech3(rgb, k):
    """Three-strip dye-transfer as a white-preserving crosstalk matrix (rows sum 1): primaries pushed apart by k."""
    s = sum(rgb)
    return [max((1.0 + 3.0 * k) * c - k * s, 0.0) for c in rgb]


# ------------------------------------------------------------------ grain
GRAIN_MODELS = ['hash', 'noise3d', 'clumped']


def grain_response(L, shadow, mid, high):
    """sigma(L) = shadow (1-L)^2 + mid 2L(1-L) + high L^2 (quadratic Bezier over luma, L clamped 0..1)."""
    L = min(max(L, 0.0), 1.0)
    return shadow * (1 - L) ** 2 + mid * 2 * L * (1 - L) + high * L * L


def clump_weights(clump):
    """Octave weights (1, c, c^2) normalised to unit total variance (independent octaves)."""
    w = [1.0, clump, clump * clump]
    n = math.sqrt(sum(x * x for x in w))
    return [x / n for x in w]


def chroma_norm(ch):
    """Colour grain: 3 independent unit noises n_c, mono part n_l = (n_r + n_g + n_b) / sqrt 3; mix(n_l, n_c, ch) has
    var (1-ch)^2 + ch^2 + 2 ch (1-ch) / sqrt 3 (cov(n_l, n_c) = 1 / sqrt 3). Returns the multiplier to unit var."""
    return 1.0 / math.sqrt((1 - ch) ** 2 + ch * ch + 2 * ch * (1 - ch) / math.sqrt(3.0))


def grain_corr(ch):
    """Correlation of the red and green grain at Colour grain ch (1 = mono, 0 = independent)."""
    cov = (1 - ch) ** 2 + 2 * ch * (1 - ch) / math.sqrt(3.0)
    return cov * chroma_norm(ch) ** 2


# ------------------------------------------------------------------ leaks / burn
def envelope(since, attack, hold, release):
    """Trigger envelope (s since the pulse): ramp up over attack, hold 1, ramp down over release; 0 before / after."""
    if since < 0:
        return 0.0
    if since < attack:
        return since / max(attack, 1e-4)
    if since < attack + hold:
        return 1.0
    return max(0.0, 1.0 - (since - attack - hold) / max(release, 1e-4))


def burn_field(u, v, ox, oy, aspect, warp, scale, seed, t):
    """The burn's distance field at uv (u, v): distance from the origin (aspect-corrected, / the farthest corner)
    + warp * (fbm - 0.5). Burned where field < front."""
    dx, dy = (u - ox) * aspect, v - oy
    far = max(math.hypot((cx - ox) * aspect, cy - oy) for cx in (0, 1) for cy in (0, 1))
    return math.hypot(dx, dy) / far + warp * (fbm(u * scale * aspect + t, v * scale + 0.37 * t, seed, 3) - 0.5)


def burn_fraction(P, w=W0, h=H0, step=20):
    """Share of pixel centres with field < front (front = Level), sampled every `step` px (live check LK2)."""
    asp = w / float(h)
    front = P['Level'] * (1.0 + P['Burnwidth'] + P['Warp'])
    n = k = 0
    for y in range(step // 2, h, step):
        for x in range(step // 2, w, step):
            f = burn_field((x + 0.5) / w, (y + 0.5) / h, P['Posx'], P['Posy'], asp, P['Warp'], P['Noisescale'],
                           P['Seed'], 0.0)
            k += f < front - P['Burnwidth']
            n += 1
    return k / float(n)


# ------------------------------------------------------------------ lens: ca
def cauchy_delta(t, curve):
    """Lateral displacement factor of wavelength t (-1 = 400 nm, 0 = 550 nm, +1 = 700 nm): red = +1; Cauchy 1/lambda^2
    gives blue -2.33 (blue bends most); `curve` blends linear t (0) -> Cauchy (1)."""
    lam = 550.0 + 150.0 * t
    c = lambda l: 1.0 / (l * l)
    d = (c(550.0) - c(lam)) / (c(550.0) - c(700.0))
    return t + (d - t) * curve


def spectral_rgb(t):
    """Wavelength t -> rgb response (gaussian CIE-like fit, red has the violet bump)."""
    lam = 550.0 + 150.0 * t
    g = lambda m, s: math.exp(-((lam - m) / s) ** 2)
    return [g(600.0, 45.0) + 0.25 * g(445.0, 25.0), g(550.0, 45.0), g(450.0, 35.0)]


def spectral_weights(n):
    """Per-tap rgb weights for n taps t = -1..1, normalised per channel (white stays white)."""
    ts = [(-1.0 + 2.0 * k / (n - 1)) for k in range(n)]
    ws = [spectral_rgb(t) for t in ts]
    sums = [sum(w[c] for w in ws) for c in range(3)]
    return ts, [[w[c] / sums[c] for c in range(3)] for w in ws]


def ca_shift_px(x, y, w, h, k1, k2, cx=0.5, cy=0.5, ax=1.0, ay=1.0):
    """Radial displacement (px, along the unit radius) of the red (+1) sample at pixel centre (x, y)."""
    px, py = x + 0.5 - cx * w, y + 0.5 - cy * h
    rmax = 0.5 * math.hypot(w, h)
    rn = math.hypot(px * ax, py * ay) / rmax
    return k1 * rn * rn + k2 * rn ** 4


# ------------------------------------------------------------------ lens: streak (rotated anisotropic buffer + scan)
def streak_dims(w, h, angle_deg, ds_along, ds_across, row_max=512):
    """Rotated work frame of the streak: (Lx, Ly, ds1, ds2, nx, ny). ds1 grows so a row fits row_max texels."""
    a = math.radians(angle_deg)
    lx = w * abs(math.cos(a)) + h * abs(math.sin(a))
    ly = w * abs(math.sin(a)) + h * abs(math.cos(a))
    ds1 = max(float(ds_along), lx / row_max)
    return lx, ly, ds1, float(ds_across), int(math.ceil(round(lx / ds1, 6))), int(math.ceil(round(ly / ds_across, 6)))


def scan_brute(e, r):
    n = len(e)
    return [sum(e[i] * r ** abs(x - i) for i in range(n)) for x in range(n)]


def scan_chunked(e, r, chunk=8, threads=64):
    """The run shader's algorithm (chunked two-sided exponential scan, 3 barriers) in Python: equals scan_brute."""
    n = chunk * threads
    E = list(e) + [0.0] * (n - len(e))
    F, B = [0.0] * n, [0.0] * n
    CF, CB = [0.0] * threads, [0.0] * threads
    for t in range(threads):
        acc = 0.0
        for j in range(chunk):
            i = t * chunk + j
            acc = E[i] + r * acc
            F[i] = acc
        CF[t] = acc
        acc = 0.0
        for j in range(chunk - 1, -1, -1):
            i = t * chunk + j
            acc = E[i] + r * acc
            B[i] = acc
        CB[t] = acc
    r8 = r ** chunk
    cin = 0.0
    for u in range(threads):
        tmp = CF[u]
        CF[u] = cin
        cin = tmp + r8 * cin
    cin = 0.0
    for u in range(threads - 1, -1, -1):
        tmp = CB[u]
        CB[u] = cin
        cin = tmp + r8 * cin
    S = []
    for t in range(threads):
        for j in range(chunk):
            i = t * chunk + j
            S.append(F[i] + r ** (j + 1) * CF[t] + B[i] + r ** (chunk - j) * CB[t] - E[i])
    return S[:len(e)]


def streak_rate(length_px, ds1):
    """Per-texel decay r = exp(-ds1 / Length): the streak falls by e every Length px."""
    return math.exp(-ds1 / max(length_px, 1e-3))


# ------------------------------------------------------------------ lens: flare (Chapman pseudo flare)
def ghost_positions(light_uv, centre, dispersal, ghosts):
    """uv where ghost i of a light at light_uv lands: s_i(uv) = uvf + (C - uvf) disp i, uvf = 2C - uv; solve s_i = L.
    Returns [(i, u, v)] inside the frame (singular i (disp i = 1) skipped)."""
    out = []
    for i in range(ghosts):
        k = 1.0 - dispersal * i
        if abs(k) < 1e-6:
            continue
        uv = [2 * c - (l - c * dispersal * i) / k for l, c in zip(light_uv, centre)]
        if 0.0 <= uv[0] <= 1.0 and 0.0 <= uv[1] <= 1.0:
            out.append((i, uv[0], uv[1]))
    return out


def flare_predictions(dispersal, ghosts, centre=(0.5, 0.5), w=W0, h=H0):
    """Ghost pixel positions of every chart light: [(light index, ghost i, x px, y px)]."""
    out = []
    for k, (lx, ly) in enumerate(LIGHTS):
        for i, u, v in ghost_positions((lx / float(w), ly / float(h)), centre, dispersal, ghosts):
            out.append((k, i, int(round(u * w)), int(round(v * h))))
    return out


# ------------------------------------------------------------------ lens: star
def star_angles(points, rotation_deg):
    """Arm directions (deg, 0..360) of a `points`-point star: lines = points / 2 crossing at rotation + k 180/lines."""
    lines = max(1, points // 2)
    return sorted(((rotation_deg + k * 180.0 / lines) % 360.0) for k in range(2 * lines))


# ------------------------------------------------------------------ rack test chart (same as GLSL CHART)
CHARTS = ['lights', 'ramp', 'grey', 'patches']
LIGHTS = [(540, 960), (200, 300), (880, 1600), (200, 1600), (880, 300)]
LIGHT_R = 6.0
PATCHES = [  # 6 x 4 grid, linear rgb, row 0 = bottom
    [(0.03, 0.03, 0.03), (0.09, 0.09, 0.09), (0.18, 0.18, 0.18), (0.36, 0.36, 0.36), (0.6, 0.6, 0.6), (0.9, 0.9, 0.9)],
    [(0.5, 0.05, 0.05), (0.05, 0.5, 0.05), (0.05, 0.05, 0.5), (0.05, 0.5, 0.5), (0.5, 0.05, 0.5), (0.5, 0.5, 0.05)],
    [(0.45, 0.28, 0.2), (0.25, 0.15, 0.1), (0.1, 0.2, 0.4), (0.2, 0.3, 0.1), (0.8, 0.4, 0.05), (0.05, 0.25, 0.3)],
    [(1.0, 1.0, 1.0), (2.0, 2.0, 2.0), (4.0, 4.0, 4.0), (1.5, 0.3, 0.1), (0.1, 0.4, 1.5), (8.0, 6.0, 3.0)],
]


def chart_pixel(x, y, chart, value=4.0, bg=0.0, grey=0.5, w=W0, h=H0):
    if chart == 'lights':
        for lx, ly in LIGHTS:
            if (x + 0.5 - lx) ** 2 + (y + 0.5 - ly) ** 2 <= LIGHT_R ** 2:
                return (value, value, value)
        return (bg, bg, bg)
    if chart == 'ramp':
        v = (x + 0.5) / w
        return (v, v, v) if y < h // 2 else (0.1 * v, 0.1 * v, 0.1 * v)
    if chart == 'grey':
        return (grey, grey, grey)
    return PATCHES[min(3, y * 4 // h)][min(5, x * 6 // w)]


def chart_np(chart, value=4.0, bg=0.0, grey=0.5, w=W0, h=H0):
    """Numpy copy of the chart (h, w, 3) float32."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    out = np.zeros((h, w, 3), np.float32)
    if chart == 'lights':
        out[:] = bg
        for lx, ly in LIGHTS:
            out[(xs + 0.5 - lx) ** 2 + (ys + 0.5 - ly) ** 2 <= LIGHT_R ** 2] = value
    elif chart == 'ramp':
        v = (xs + 0.5) / w
        v = np.where(ys < h // 2, v, 0.1 * v)
        out[:] = v[..., None]
    elif chart == 'grey':
        out[:] = grey
    else:
        for r in range(4):
            for c in range(6):
                m = (ys * 4 // h == r) & (xs * 6 // w == c)
                out[m] = PATCHES[r][c]
    return out


def ext_np(img, scale, thr, kn, by_luma=False, mode=0):
    """The shared EXT pass: scale x scale box mean then soft-knee excess (mode 0) or the image (mode 1); valid region."""
    h, w = img.shape[:2]
    vh, vw = -(-h // scale), -(-w // scale)
    pad = np.pad(img[..., :3], ((0, vh * scale - h), (0, vw * scale - w), (0, 0)), mode='edge')
    m = pad.reshape(vh, scale, vw, scale, 3).mean(axis=(1, 3))
    if mode == 1:
        return m
    br = (m @ np.array([0.2126, 0.7152, 0.0722])) if by_luma else m.max(axis=2)
    rq = np.clip(br - thr + kn, 0.0, 2.0 * kn)
    rq = rq * rq / (4.0 * kn + 1e-5)
    wgt = np.maximum(rq, br - thr) / np.maximum(br, 1e-5)
    return m * wgt[..., None]


# ------------------------------------------------------------------ numpy references of the GPU passes
def bilinear_np(img, x, y):
    """GPU bilinear fetch at pixel-space coords (x, y) (texel centres at +0.5), clamp-to-edge (extend hold)."""
    h, w = img.shape[:2]
    fx, fy = np.asarray(x, np.float64) - 0.5, np.asarray(y, np.float64) - 0.5
    x0, y0 = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    ax, ay = (fx - x0)[..., None], (fy - y0)[..., None]
    cx = lambda i: np.clip(i, 0, w - 1)
    cy = lambda i: np.clip(i, 0, h - 1)
    a, b = img[cy(y0), cx(x0)], img[cy(y0), cx(x0 + 1)]
    c, d = img[cy(y0 + 1), cx(x0)], img[cy(y0 + 1), cx(x0 + 1)]
    return (a * (1 - ax) + b * ax) * (1 - ay) + (c * (1 - ax) + d * ax) * ay


def down1331_np(a):
    """One PYR level: [1 3 3 1] x [1 3 3 1] / 64 downsample by 2, edge held (fine texels 2q-1 .. 2q+2)."""
    h, w = a.shape[0] // 2, a.shape[1] // 2
    wt = np.array([1.0, 3.0, 3.0, 1.0]) / 8.0
    out = np.zeros((h, w) + a.shape[2:])
    for i in range(4):
        ys = np.clip(2 * np.arange(h) + i - 1, 0, a.shape[0] - 1)
        for j in range(4):
            xs = np.clip(2 * np.arange(w) + j - 1, 0, a.shape[1] - 1)
            out += wt[i] * wt[j] * a[ys][:, xs]
    return out


def mips_np(img, levels=8):
    """The PYR chain (rack pyr1..pyr7): level 0 = EXT, level k = down1331(level k-1); exact sizes up to the pad."""
    out = [img.astype(np.float64)]
    for _ in range(levels - 1):
        out.append(down1331_np(out[-1]))
    return out


def ext_pad_np(img, scale, mult, thr, kn, by_luma=False, mode=0):
    """The EXT buffer as the GPU writes it: valid region + edge-held padding to a multiple of mult (h, w, 3)."""
    e = ext_np(img, scale, thr, kn, by_luma, mode)
    vh, vw = e.shape[:2]
    ph, pw = -(-vh // mult) * mult, -(-vw // mult) * mult
    return np.pad(e, ((0, ph - vh), (0, pw - vw), (0, 0)), mode='edge')


WSKIP = 1e-3


def pyr_atlas(pw, ph):
    """Rack pyramid atlases (perf lane 3): {level: (op, x, y, w, h)} for an EXT buffer pw x ph (multiples of 128),
    plus the atlas sizes. pyra = levels 1..4 stacked from y 0, pyrb = levels 5..7; y = rows from the texture's row 0
    (TD's bottom row). The MIPG lvlTex constants (0.9375, 0.03125, 0.0546875) are these sizes / (pw, ph)."""
    out, y = {}, {'pyra': 0, 'pyrb': 0}
    for k in range(1, 8):
        o = 'pyra' if k <= 4 else 'pyrb'
        out[k] = (o, 0, y[o], pw >> k, ph >> k)
        y[o] += ph >> k
    out['size'] = {'pyra': (pw // 2, y['pyra']), 'pyrb': (pw // 32, y['pyrb'])}
    return out


def glow_np(ext_pad, scale, radii, spread, w=W0, h=H0, src_luma=True, levels=8, gscale=1):
    """MIPG gather (halation per-channel radii / diffusion one radius) at every full-res pixel: (h, w, 3).
    src_luma: the classic halation source (luma of the excess, alpha of EXT). gscale = full-res px per gather texel
    (perf lane 3: Quality half / quarter gather at the EXT res = scale, then a bilinear read at full res)."""
    if gscale > 1:
        gw, gh = -(-w // gscale), -(-h // gscale)
        ys, xs = np.mgrid[0:gh, 0:gw].astype(np.float64)
        G = _glow_at(ext_pad, scale, radii, spread, (xs + 0.5) * gscale / scale, (ys + 0.5) * gscale / scale,
                     src_luma, levels)
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
        return bilinear_np(G, (xs + 0.5) / gscale, (ys + 0.5) / gscale)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    return _glow_at(ext_pad, scale, radii, spread, (xs + 0.5) / scale, (ys + 0.5) / scale, src_luma, levels)


def _glow_at(ext_pad, scale, radii, spread, ex, ey, src_luma=True, levels=8):
    """The gather at EXT-texel coordinates (ex, ey)."""
    h, w = ex.shape
    M = mips_np(ext_pad, levels)
    src = [(m @ np.array([0.2126, 0.7152, 0.0722]))[..., None] if src_luma else m for m in M]
    kc = [math.log2(max(r, 1e-3) / scale) for r in radii]
    acc = np.zeros((h, w, 3))
    ws = np.zeros(3)
    for k in range(levels):
        w_ = np.array([math.exp(-0.5 * ((k - c) / max(spread, 0.05)) ** 2) for c in kc])
        if w_.max() < WSKIP:                           # the GPU skips levels that add < 0.1 % (MIPG WSKIP)
            continue
        f = 2.0 ** k                                   # level-k texel in level-0 units
        t = 0.5                                        # half a level-k texel
        tap = 0.25 * sum(bilinear_np(src[k], (ex / f) + dx * t, (ey / f) + dy * t)
                         for dx in (-1, 1) for dy in (-1, 1))
        acc += tap * w_
        ws += w_
    return acc / ws


def streak_np(img, P, w=W0, h=H0):
    """streak at Angle 0 (rows = canvas rows): exact EXT box (Along x Thickness), row scan, bilinear lookup.
    Returns the added rgb (h, w, 3) before Amount x Intensity: tint x luma(long) x (1-rl) + core."""
    ds1, ds2 = float(P['Along']), float(P['Thickness'])
    nx, ny = int(math.ceil(w / ds1)), int(math.ceil(h / ds2))
    e = ext_np(img, 1, P['Threshold'], P['Knee'])     # knee per box below: do the box first
    box = img[:ny * int(ds2), :nx * int(ds1), :3].reshape(ny, int(ds2), nx, int(ds1), 3).mean(axis=(1, 3))
    br = box.max(axis=2)
    rq = np.clip(br - P['Threshold'] + P['Knee'], 0.0, 2.0 * P['Knee'])
    rq = rq * rq / (4.0 * P['Knee'] + 1e-5)
    e = box * (np.maximum(rq, br - P['Threshold']) / np.maximum(br, 1e-5))[..., None]
    el = e @ np.array([0.2126, 0.7152, 0.0722])
    rl, rc = streak_rate(P['Length'], ds1), streak_rate(P['Corelength'], ds1)
    idx = np.arange(nx)
    K = lambda r: r ** np.abs(idx[:, None] - idx[None, :])
    S = np.einsum('jic,ik->jkc', e, K(rl))                       # long, rgb
    Sa = el @ K(rc)                                              # core, luma
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    u, v = (xs + 0.5) / ds1, (ys + 0.5) / ds2
    Sl = bilinear_np(np.concatenate([S, Sa[..., None]], axis=2), u, v)
    lum = Sl[..., :3] @ np.array([0.2126, 0.7152, 0.0722])
    tint = np.array([P['Tintr'], P['Tintg'], P['Tintb']])
    ctint = np.array([P['Coretintr'], P['Coretintg'], P['Coretintb']])
    lng = (tint * lum[..., None]) * (1 - P['Sourcecolor']) + Sl[..., :3] * P['Sourcecolor']
    return lng * (1 - rl) + ctint * P['Coregain'] * Sl[..., 3:4] * (1 - rc)


def ca_rgb_expected(img, x, y, k1, k2=0.0, curve=1.0, cx=0.5, cy=0.5):
    """RGB-mode ca output at pixel (x, y) of a picture `img` (h, w, 3+): R / G / B bilinear at their shifted spots."""
    h, w = img.shape[:2]
    px, py = x + 0.5, y + 0.5
    vx, vy = px - cx * w, py - cy * h
    n = math.hypot(vx, vy)
    dx, dy = (vx / n, vy / n) if n > 1e-4 else (0.0, 0.0)
    D = ca_shift_px(x, y, w, h, k1, k2, cx, cy)
    out = []
    for c, t in ((0, 1.0), (1, 0.0), (2, -1.0)):
        d = cauchy_delta(t, curve)
        out.append(float(bilinear_np(img[..., :3].astype(np.float64), px + dx * D * d, py + dy * D * d)[c]))
    return out


# ------------------------------------------------------------------ live-check analysers (numpy)
def an_diff(a, b):
    """max / mean abs difference of the rgb of two reads (passthrough checks: max 0)."""
    d = np.abs(a[..., :3].astype(np.float64) - b[..., :3].astype(np.float64))
    return {'max': float(d.max()), 'mean': float(d.mean()), 'changed': float((d.max(axis=2) > 1e-6).mean())}


def an_added_energy(out, inp):
    """Per-channel sum of (out - in) over the frame (glow energy)."""
    return [float((out[..., c].astype(np.float64) - inp[..., c]).sum()) for c in range(3)]


def an_profile(arr, x0, y0, angle_deg, dists, chan=None):
    """Values (luma or channel) at distances `dists` px from (x0, y0) along angle (0 = +x, 90 = +y), nearest px."""
    a = math.radians(angle_deg)
    out = []
    for d in dists:
        x, y = int(round(x0 + d * math.cos(a))), int(round(y0 + d * math.sin(a)))
        px = arr[y, x, :3].astype(np.float64)
        out.append(float(px[chan]) if chan is not None else float(px @ np.array([0.2126, 0.7152, 0.0722])))
    return out


def an_ring_peaks(arr, x0, y0, radius, n=720, base=None):
    """Angles (deg) of local maxima of luma (minus base) on a ring, strongest first (star arm count / angles)."""
    vals = []
    for k in range(n):
        a = 2 * math.pi * k / n
        x, y = int(round(x0 + radius * math.cos(a))), int(round(y0 + radius * math.sin(a)))
        v = float(arr[y, x, :3].astype(np.float64) @ np.array([0.2126, 0.7152, 0.0722]))
        if base is not None:
            v -= float(base[y, x, :3].astype(np.float64) @ np.array([0.2126, 0.7152, 0.0722]))
        vals.append(v)
    vals = np.array(vals)
    sm = np.convolve(np.concatenate([vals[-3:], vals, vals[:3]]), np.ones(7) / 7.0, mode='valid')
    pk = [k for k in range(n) if sm[k] >= sm[k - 1] and sm[k] > sm[(k + 1) % n] and sm[k] > 0.25 * sm.max()]
    pk.sort(key=lambda k: -sm[k])
    return [360.0 * k / n for k in pk], float(sm.max()), float(np.median(sm))


def an_tile_means(arr, x0, y0, tiles=8, size=8, chan=0):
    """Means of `tiles` consecutive size x size tiles starting at (x0, y0) along x (dither mean checks)."""
    return [float(arr[y0:y0 + size, x0 + k * size:x0 + (k + 1) * size, chan].astype(np.float64).mean())
            for k in range(tiles)]


def an_levels(arr, x0, y0, w, h, chan=0, bits=8):
    """Is every value in the window a multiple of 1/(2^bits - 1)? Returns the max distance (in LSB) to the grid."""
    L = float((1 << bits) - 1)
    v = arr[y0:y0 + h, x0:x0 + w, chan].astype(np.float64) * L
    return float(np.abs(v - np.round(v)).max())


def an_stats(arr, x0=100, y0=100, w=880, h=1720):
    """mean + std of luma and the rgb channels inside a window (grain checks)."""
    v = arr[y0:y0 + h, x0:x0 + w, :3].astype(np.float64)
    y = v @ np.array([0.2126, 0.7152, 0.0722])
    return {'mean': float(y.mean()), 'std': float(y.std()), 'std_rgb': [float(v[..., c].std()) for c in range(3)],
            'corr_rg': float(np.corrcoef(v[..., 0].ravel(), v[..., 1].ravel())[0, 1])}


# ------------------------------------------------------------------ expected numbers (docs/builds/fx_film.md)
def expected_numbers():
    """Every number the doc's LIVE CHECKS quote. test_fx_film asserts the doc carries each one."""
    ex = {}
    # TC: tone curves at 0.18 and 1.0 (linear), sRGB-encoded out (Inspace linear, exposure 0)
    ex['tc_aces_fit_018'] = round(aces_fit(0.18), 4)
    ex['tc_aces_fit_1'] = round(aces_fit(1.0), 4)
    ex['tc_hable_018'] = round(hable(0.18, 11.2), 4)
    ex['tc_reinhard_1'] = round(reinhard(1.0, 4.0), 4)
    ex['tc_lottes_018'] = round(lottes(0.18, 1.6, 0.977, 8.0), 4)
    ex['tc_hill_018'] = round(aces_hill([0.18, 0.18, 0.18])[0], 4)
    # dither on the 0.5 grey chart (exact in rgba16float): 8 bit -> 127.5 LSB = half the tile 127, half 128
    ex['dither_tile_mean_lsb'] = round(tile_mean_bayer(0.5, 8) * 255.0, 4)
    ex['dither_frac_up'] = sum(1 for k in range(64) if quantize(0.5, 8, (k + 0.5) / 64.0) * 255 > 127.5)
    ex['dither_4bit_levels'] = sorted(set(round(quantize(0.5, 4, (k + 0.5) / 64.0) * 15) for k in range(64)))
    # stock: neutral print curve keeps 0.18; bleach of mid grey; tech2 of white / pure red
    ex['stock_018'] = round(stock_curve(0.18, 1.0, 0.0, 1.4, 1.4, 1.6), 4)
    ex['stock_1'] = round(stock_curve(1.0, 1.0, 0.0, 1.4, 1.4, 1.6), 4)
    ex['stock_009'] = round(stock_curve(0.09, 1.0, 0.0, 1.4, 1.4, 1.6), 4)
    ex['bleach_r_of_06_03_02'] = round(bleach([0.6, 0.3, 0.2], 1.0)[0], 4)
    ex['tech2_red'] = [round(c, 3) for c in tech2([1.0, 0.0, 0.0], [1.0, 0.42, 0.16])]
    ex['tech3_red'] = [round(c, 3) for c in tech3([0.6, 0.3, 0.2], 0.15)]
    # halation / diffusion energy: lights chart value 4, thr 0.8 knee 0.2 (max channel), half-res extract
    if np is not None:
        img = chart_np('lights', 4.0)
        e = ext_np(img, 2, 0.8, 0.2)
        ex['ext_sum_half'] = round(float(e[..., 0].sum()) * 4.0, 1)          # full-res px units
        e4 = ext_np(img, 4, 0.8, 0.2)
        ex['ext_sum_quarter'] = round(float(e4[..., 0].sum()) * 16.0, 1)
    ex['hal_w_r'] = [round(x, 3) for x in level_weights(40 * 1.4, 1.0)]
    ex['hal_w_b'] = [round(x, 3) for x in level_weights(40 * 0.7, 1.0)]
    if np is not None:
        img = chart_np('lights', 4.0)
        # halation check: Radius 20, Spread 1, Tint (1, 0.3, 0.06), luma source, add, Intensity 1, Core 0, half
        ep = ext_pad_np(img, 2, 128, 0.8, 0.2)
        g = glow_np(ep, 2, [20 * 1.4, 20 * 1.0, 20 * 0.7], 1.0) * np.array([1.0, 0.3, 0.06])
        ex['hal_energy'] = [round(float(g[..., c].sum()), 1) for c in range(3)]
        ex['hal_r_at_570_960'] = round(float(g[960, 570, 0]), 4)
        ex['hal_r_at_600_960'] = round(float(g[960, 600, 0]), 4)
        # perf lane 3: Quality half gathers at the EXT res (gscale 2): energy kept, light-core peak a little lower
        gh = glow_np(ep, 2, [20 * 1.4, 20 * 1.0, 20 * 0.7], 1.0, gscale=2) * np.array([1.0, 0.3, 0.06])
        ex['hal_gq_half_energy_r'] = round(float(gh[..., 0].sum()), 1)
        ex['hal_gq_half_r_at_570_960'] = round(float(gh[960, 570, 0]), 4)
        ex['hal_gq_half_peak_ratio'] = round(float(gh[..., 0].max() / g[..., 0].max()), 3)
        # diffusion bloom check: Radius 30, Spread 1.5, Tint (1, 1, 1), Intensity 1, half
        b = glow_np(ep, 2, [30.0, 30.0, 30.0], 1.5, src_luma=False)
        ex['bloom_energy_r'] = round(float(b[..., 0].sum()), 1)
        ex['bloom_r_at_580_960'] = round(float(b[960, 580, 0]), 4)
        # streak check: Angle 0, Length 300, Corelength 40, Coregain 0, Tint (1, 1, 1), Along 8, Thickness 2
        SP = {'Along': 8, 'Thickness': 2, 'Threshold': 0.8, 'Knee': 0.2, 'Length': 300.0, 'Corelength': 40.0,
              'Coregain': 0.0, 'Tintr': 1.0, 'Tintg': 1.0, 'Tintb': 1.0, 'Coretintr': 1.0, 'Coretintg': 1.0,
              'Coretintb': 1.0, 'Sourcecolor': 0.0}
        st = streak_np(img, SP)
        ex['streak_at_640_960'] = round(float(st[960, 640, 0]), 5)
        ex['streak_at_740_960'] = round(float(st[960, 740, 0]), 5)
        ex['streak_at_640_972'] = round(float(st[972, 640, 0]), 6)
    # grain: std of a 0.5 grey with Amount 0.1, response (0.6, 1.0, 0.4) -> sigma(0.5)
    ex['grain_sigma_05'] = round(grain_response(0.5, 0.6, 1.0, 0.4), 4)
    ex['grain_std_amount01'] = round(0.1 * grain_response(0.5, 0.6, 1.0, 0.4), 4)
    ex['vn_norm2'] = round(vn_norm(2), 5)
    ex['grain_corr_05'] = round(grain_corr(0.5), 4)
    # leaks: burn fraction, Level 0.5 (origin bottom-left corner)
    ex['burn_frac'] = round(burn_fraction({'Level': 0.5, 'Burnwidth': 0.06, 'Warp': 0.25, 'Posx': 0.0, 'Posy': 0.0,
                                           'Noisescale': 3.0, 'Seed': 7}), 3)
    ex['env_mid_release'] = round(envelope(0.1 + 0.5 + 0.4, 0.1, 0.5, 0.8), 3)
    # ca: red shift at the top-right corner pixel and the frame centre (K1 12 px, K2 0)
    ex['ca_corner_px'] = round(ca_shift_px(1079, 1919, W0, H0, 12.0, 0.0), 2)
    ex['ca_blue_factor'] = round(cauchy_delta(-1.0, 1.0), 3)
    # streak dims at 0 / 90 / 30 deg (Along 8, Thickness 2)
    for a in (0, 90, 30):
        d = streak_dims(W0, H0, a, 8, 2)
        ex['streak_dims_%d' % a] = [d[4], d[5], round(d[2], 3)]
    ex['streak_ratio_100_200'] = round(math.exp(-100.0 / 300.0), 4)
    # flare ghosts of the 5 chart lights, dispersal 0.35, 6 ghosts, optical centre (0.45, 0.55)
    ex['flare_ghosts'] = flare_predictions(0.35, 6, (0.45, 0.55))
    ex['star_angles_6_15'] = [round(a, 1) for a in star_angles(6, 15.0)]
    return ex


if __name__ == '__main__':      # print the doc numbers
    for k, v in expected_numbers().items():
        print(k, v)
