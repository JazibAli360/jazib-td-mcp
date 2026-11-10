# fx_analog_ntsc_logic - pure maths for FX_analog module 'ntsc' (FX2 AV-10 composite encode/decode, AV-11 PAL as a
# mode). Copied into the instance's `ntsc_logic` Text DAT: the GLSL uniforms read UNI(parent()) / frame_phase(...).
# The numpy reference (resample/encode/separate/decode/upsample/reference) mirrors the four compute shaders in
# builders/fx_analog_ntsc.py line by line, so a live lane can diff every pass against it (docs/builds/fx_analog_ntsc.md).
# Arrays are in TD texture order (row 0 = bottom, as numpyArray() returns them). numpy is imported lazily (TD has it;
# UNI/derive need only math). ASCII only.
import math

STANDARDS = ['ntsc', 'pald', 'pals']
SEPS = ['none', 'notch', 'comb1', 'comb2', 'svideo']
RMAX = 24                      # FIR half-width cap (taps = 2R+1); the decode shader loops -RMAX..RMAX

# fsc MHz; nominal active samples per line at 4*fsc (so the active line lasts n/(4 fsc) us); subcarrier phase
# advance per line / per frame in cycles (NTSC 227.5 cycles/line, 525 lines; PAL 283.75 + 25 Hz offset, 625 lines);
# comb delay in lines (PAL needs 2 lines for C(n-D) = -C(n)).
STD = {
    'ntsc': {'fsc': 3.579545, 'nominal': 754, 'lineadv': 0.5, 'frameadv': 0.5, 'combd': 1, 'pal': 0, 'pald': 0},
    'pald': {'fsc': 4.43361875, 'nominal': 922, 'lineadv': 0.75, 'frameadv': 0.75, 'combd': 2, 'pal': 1, 'pald': 1},
    'pals': {'fsc': 4.43361875, 'nominal': 922, 'lineadv': 0.75, 'frameadv': 0.75, 'combd': 2, 'pal': 1, 'pald': 0},
}

# RGB -> YIQ (NTSC 1953 FCC) and RGB -> YUV (PAL); the inverses are the GLSL's decode matrices.
YIQ = ((0.299, 0.587, 0.114), (0.595716, -0.274453, -0.321263), (0.211456, -0.522591, 0.311135))
YIQ_INV = ((1.0, 0.956296, 0.621024), (1.0, -0.272122, -0.647381), (1.0, -1.106989, 1.704615))
YUV = ((0.299, 0.587, 0.114), (-0.14713, -0.28886, 0.436), (0.615, -0.51499, -0.10001))
YUV_INV = ((1.0, 0.0, 1.139835), (1.0, -0.394646, -0.580594), (1.0, 2.032112, 0.0))

PARS = ['Amount', 'Standard', 'Separation', 'Crawl', 'Hue', 'Saturation', 'Phaseerr', 'Peaking', 'Ringing', 'Noise',
        'Gain', 'Samples', 'Lines', 'Subcarrier', 'Ybw', 'Ibw', 'Qbw', 'Lineblend', 'Seed']
DEFAULTS = {'Amount': 1.0, 'Standard': 'ntsc', 'Separation': 'comb1', 'Crawl': 1.0, 'Hue': 0.0, 'Saturation': 1.0,
            'Phaseerr': 0.0, 'Peaking': 0.0, 'Ringing': 0.0, 'Noise': 0.0, 'Gain': 1.0, 'Samples': 754, 'Lines': 480,
            'Subcarrier': 1.0, 'Ybw': 4.2, 'Ibw': 1.3, 'Qbw': 0.5, 'Lineblend': 1.0, 'Seed': 1}


def _menu(v, names):
    if isinstance(v, str):
        return names.index(v) if v in names else 0
    return int(v)


def radius(fc):
    """FIR half-width for a cutoff fc (cycles/sample): ~1.2 main lobes, 2..RMAX."""
    return int(max(2, min(RMAX, math.ceil(1.2 / max(fc, 1e-4)))))


def derive(p):
    """Raw par values {Par: value} (menus as name or index) -> the numbers the shaders use."""
    q = dict(DEFAULTS)
    q.update(p or {})
    si = _menu(q['Standard'], STANDARDS)
    s = STD[STANDARDS[si]]
    ws = max(8, int(q['Samples']))
    lines = max(2, int(q['Lines']))
    active_us = s['nominal'] / (4.0 * s['fsc'])
    fs = ws / active_us                                              # MHz
    cps = float(q['Subcarrier']) * s['fsc'] / fs                     # subcarrier cycles per sample
    fc = lambda mhz: min(0.5, max(1e-3, float(mhz) / fs))
    fcY, fcI, fcQ = fc(q['Ybw']), fc(q['Ibw']), fc(q['Qbw'])
    fcYw = 0.5 * fcY                                                 # peaking: Y - wide-kernel Y
    rY, rYw, rI, rQ = radius(fcY), radius(fcYw), radius(fcI), radius(fcQ)
    return {
        'std': si, 'sep': _menu(q['Separation'], SEPS), 'ws': ws, 'lines': lines, 'fs': fs, 'cps': cps,
        'lineadv': s['lineadv'], 'frameadv': s['frameadv'], 'combd': s['combd'], 'pal': s['pal'], 'pald': s['pald'],
        'fcY': fcY, 'fcYw': fcYw, 'fcI': fcI, 'fcQ': fcQ, 'rY': rY, 'rYw': rYw, 'rI': rI, 'rQ': rQ,
        'R': max(rY, rYw, rI, rQ), 'peaking': float(q['Peaking']), 'ring': float(q['Ringing']),
        'hue': math.radians(float(q['Hue'])), 'sat': float(q['Saturation']),
        'perr': math.radians(float(q['Phaseerr'])), 'noise': float(q['Noise']), 'gain': float(q['Gain']),
        'amount': float(q['Amount']), 'lineblend': float(q['Lineblend']), 'seed': int(q['Seed']),
        'crawl': float(q['Crawl']),
    }


def frame_phase_of(d, frame):
    """Subcarrier phase offset (cycles) of frame `frame`: crawl x the standard's per-frame advance (2-frame NTSC
    repeat, 4-frame PAL repeat at Crawl 1)."""
    return (float(frame) * d['crawl'] * d['frameadv']) % 1.0


def uniforms(d):
    """vec4 uniforms (name -> 4 floats). Frame phase uF.x and frame number uF.y come from their own expressions."""
    return {
        'uS': [d['ws'], d['lines'], d['cps'], d['lineadv']],
        'uF': [0.0, 0.0, d['seed'], d['noise']],
        'uE': [d['pal'], d['gain'], d['sep'], d['combd']],
        'uK': [d['fcY'], d['fcYw'], d['fcI'], d['fcQ']],
        'uR': [d['rY'], d['rYw'], d['rI'], d['rQ']],
        'uP': [d['peaking'], d['ring'], d['hue'], d['sat']],
        'uQ': [d['perr'], d['pal'], d['pald'], d['R']],
        'uU': [d['amount'], d['lineblend'], 0.0, 0.0],
    }


# ------------------------------------------------------------------ TD side (expressions; no numpy)
_CACHE = {'key': None, 'd': None, 'u': None}


def raw(comp):
    out = {}
    for n in PARS:
        p = getattr(comp.par, n, None)
        out[n] = p.eval() if p is not None else DEFAULTS[n]
    return out


def _derived(comp):
    p = raw(comp)
    key = tuple(p[n] for n in PARS)
    if key != _CACHE['key']:
        d = derive(p)
        _CACHE.update(key=key, d=d, u=uniforms(d))
    return _CACHE


def UNI(comp):
    return _derived(comp)['u']


def frame_phase(comp, frame):
    return frame_phase_of(_derived(comp)['d'], frame)


# ------------------------------------------------------------------ numpy reference (mirrors the shaders)
def _np():
    import numpy as np
    return np


def pcg(v):
    np = _np()
    with np.errstate(over='ignore'):                                 # uint32 wraps, as in GLSL
        v = np.asarray(v, dtype=np.uint32)
        s = v * np.uint32(747796405) + np.uint32(2891336453)
        w = ((s >> ((s >> np.uint32(28)) + np.uint32(4))) ^ s) * np.uint32(277803737)
        return (w >> np.uint32(22)) ^ w


def h4(x, y, z, w):
    np = _np()
    u = lambda a: np.asarray(a, dtype=np.uint32)
    k = pcg(u(x) ^ pcg(u(y) ^ pcg(u(z) ^ pcg(u(w)))))
    return (k >> np.uint32(8)).astype(np.float64) / 16777215.0


def resample(img, ws, lines):
    """img (H, W, >=3) -> (lines, ws, 3): mean of up to 4 x 8 texels of each sample's footprint (integer picks)."""
    np = _np()
    img = np.asarray(img, dtype=np.float64)
    H, W = img.shape[:2]
    k = np.arange(ws)
    x0 = (k * W) // ws
    sx = np.maximum(1, ((k + 1) * W) // ws - x0)
    nx = np.minimum(sx, 4)
    r = np.arange(lines)
    y0 = (r * H) // lines
    sy = np.maximum(1, ((r + 1) * H) // lines - y0)
    ny = np.minimum(sy, 8)
    acc = np.zeros((lines, ws, 3))
    for j in range(8):
        my = j < ny
        yy = np.minimum(y0 + (j * sy) // np.maximum(ny, 1), H - 1)
        for i in range(4):
            mx = i < nx
            xx = np.minimum(x0 + (i * sx) // np.maximum(nx, 1), W - 1)
            m = (my[:, None] & mx[None, :]).astype(np.float64)
            acc += img[yy][:, xx, :3] * m[..., None]
    return acc / (nx[None, :] * ny[:, None])[..., None]


def _phase(d, k, r, fph):
    np = _np()
    return 2.0 * math.pi * np.mod(d['cps'] * k + d['lineadv'] * r + fph, 1.0)


def _mat(rgb, M):
    np = _np()
    return np.stack([rgb[..., 0] * M[i][0] + rgb[..., 1] * M[i][1] + rgb[..., 2] * M[i][2] for i in range(3)], -1)


def encode(grid, d, fph=0.0, frame=0):
    """(lines, ws, 3) RGB -> (lines, ws, 3): composite, Y (S-Video luma), C (S-Video chroma)."""
    np = _np()
    L, ws = grid.shape[:2]
    k = np.arange(ws)[None, :].astype(np.float64)
    r = np.arange(L)[:, None].astype(np.float64)
    th = _phase(d, k, r, fph)
    if d['pal']:
        yuv = _mat(grid, YUV)
        s = np.where(np.arange(L)[:, None] % 2 == 1, -1.0, 1.0)
        C = yuv[..., 1] * np.sin(th) + s * yuv[..., 2] * np.cos(th)
    else:
        yuv = _mat(grid, YIQ)
        C = yuv[..., 1] * np.cos(th) + yuv[..., 2] * np.sin(th)
    Y = yuv[..., 0]
    n1 = np.zeros_like(Y)
    n2 = np.zeros_like(Y)
    if d['noise'] > 0:
        K = np.broadcast_to(np.arange(ws)[None, :], Y.shape)
        R = np.broadcast_to(np.arange(L)[:, None], Y.shape)
        fr = int(frame) % 16777216
        sd = (int(d['seed']) * 7919) & 0xFFFFFFFF
        n1 = (h4(K, R, fr, sd) + h4(K, R, fr, sd + 1) - 1.0) * d['noise']
        n2 = (h4(K, R, fr, sd + 2) + h4(K, R, fr, sd + 3) - 1.0) * d['noise']
    g = d['gain']
    return np.stack([(Y + C + n1) * g, (Y + n1) * g, (C + n2) * g], -1)


def separate(enc, d):
    """(lines, ws, 3) encode output -> (lines, ws, 2): Y and C as the decoder's separator sees them."""
    np = _np()
    L, ws = enc.shape[:2]
    c = enc[..., 0]
    sep = d['sep']
    if sep == 0:
        return np.stack([c, c], -1)
    if sep == 4:
        return np.stack([enc[..., 1], enc[..., 2]], -1)
    if sep == 1:
        dd = 0.5 / d['cps']
        k = np.arange(ws).astype(np.float64)

        def at(x):
            fl = np.floor(x)
            k0 = fl.astype(int)
            f = x - fl
            a = c[:, np.clip(k0, 0, ws - 1)]
            b = c[:, np.clip(k0 + 1, 0, ws - 1)]
            return a * (1.0 - f) + b * f
        Ys = (at(k - dd) + 2.0 * c + at(k + dd)) * 0.25
        return np.stack([Ys, c - Ys], -1)
    D = d['combd']
    r = np.arange(L)
    rm = np.where(r - D < 0, r + D, r - D)
    rm = np.clip(rm, 0, L - 1)
    if sep == 2:
        c2 = c[rm]
        return np.stack([(c + c2) * 0.5, (c - c2) * 0.5], -1)
    rq = np.where(r + D > L - 1, r - D, r + D)
    rq = np.clip(rq, 0, L - 1)
    Ys = (c[rm] + 2.0 * c + c[rq]) * 0.25
    return np.stack([Ys, c - Ys], -1)


def kern(j, fc, R, ring):
    """Low-pass tap j (unnormalised; the shader divides by the weight sum), -6 dB near fc. ring 0 = Gaussian (no
    overshoot, soft edge), 0.5 = Blackman-windowed sinc (sharper, ~4-7 % overshoot), 1 = bare sinc (Gibbs ringing)."""
    if abs(j) > R:
        return 0.0
    x = float(j)
    sg = 0.1874 / fc                                    # Gaussian sigma with |H(fc)| = 0.5
    g = math.exp(-0.5 * x * x / (sg * sg))
    a = math.pi * x / (R + 1.0)
    win = 0.42 + 0.5 * math.cos(a) + 0.08 * math.cos(2.0 * a)
    sn = 1.0 if j == 0 else math.sin(2.0 * math.pi * fc * x) / (2.0 * math.pi * fc * x)
    ta = min(1.0, max(0.0, 2.0 * ring))
    tb = min(1.0, max(0.0, 2.0 * ring - 1.0))
    ws = win * sn
    return g + (ws - g) * ta + (sn - ws) * tb


def _demod(d, cs, kk, r, fph):
    np = _np()
    th = _phase(d, kk, r, fph) + d['perr']
    if d['pal']:
        s = np.where(r % 2 == 1, -1.0, 1.0)
        return 2.0 * cs * np.sin(th), 2.0 * cs * np.cos(th) * s
    return 2.0 * cs * np.cos(th), 2.0 * cs * np.sin(th)


def decode(sep, d, fph=0.0):
    """(lines, ws, 2) Y/C -> (lines, ws, 3) RGB: Y FIR (+ peaking), demodulate, I/Q (U/V) FIR, PAL-D line average,
    hue/saturation, matrix."""
    np = _np()
    L, ws = sep.shape[:2]
    k = np.arange(ws)
    r = np.arange(L)[:, None]
    r2 = np.clip(np.where(r - 1 < 0, r + 1, r - 1), 0, L - 1)
    acc = {n: np.zeros((L, ws)) for n in ('Y', 'Yw', 'a', 'b')}
    sw = {n: 0.0 for n in ('Y', 'Yw', 'a', 'b')}
    R = d['R']
    for j in range(-R, R + 1):
        valid = ((k + j >= 0) & (k + j < ws)).astype(np.float64)[None, :]   # taps off the line are skipped
        kk = np.clip(k + j, 0, ws - 1)
        ys = sep[:, kk, 0]
        cs = sep[:, kk, 1]
        wY = kern(j, d['fcY'], d['rY'], d['ring']) * valid
        wYw = kern(j, d['fcYw'], d['rYw'], d['ring']) * valid
        wI = kern(j, d['fcI'], d['rI'], d['ring']) * valid
        wQ = kern(j, d['fcQ'], d['rQ'], d['ring']) * valid
        a, b = _demod(d, cs, kk[None, :].astype(np.float64), r.astype(np.float64), fph)
        if d['pald']:
            cs2 = sep[r2[:, 0]][:, kk, 1]
            a2, b2 = _demod(d, cs2, kk[None, :].astype(np.float64), r2.astype(np.float64), fph)
            a, b = 0.5 * (a + a2), 0.5 * (b + b2)
        acc['Y'] += wY * ys
        acc['Yw'] += wYw * ys
        acc['a'] += wI * a
        acc['b'] += wQ * b
        sw['Y'] = sw['Y'] + wY
        sw['Yw'] = sw['Yw'] + wYw
        sw['a'] = sw['a'] + wI
        sw['b'] = sw['b'] + wQ
    P = d['peaking']
    Y = (1.0 + P) * acc['Y'] / sw['Y'] - P * acc['Yw'] / sw['Yw']
    a = acc['a'] / sw['a']
    b = acc['b'] / sw['b']
    ch, sh = math.cos(d['hue']), math.sin(d['hue'])
    a, b = (a * ch - b * sh) * d['sat'], (a * sh + b * ch) * d['sat']
    return _mat(np.stack([Y, a, b], -1), YUV_INV if d['pal'] else YIQ_INV)


def upsample(dec, W, H, inp, d):
    """(lines, ws, 3) -> (H, W, 4): horizontal linear; vertical nearest line mixed with bilinear by Lineblend; then
    mix with the input by Amount (alpha = input alpha)."""
    np = _np()
    L, ws = dec.shape[:2]
    inp = np.asarray(inp, dtype=np.float64)
    x = np.arange(W)
    y = np.arange(H)
    u = (x + 0.5) * ws / W - 0.5
    k0 = np.floor(u).astype(int)
    f = (u - k0)[None, :, None]
    a = np.clip(k0, 0, ws - 1)
    b = np.clip(k0 + 1, 0, ws - 1)

    def hrow(rows):
        D = dec[rows]
        return D[:, a] * (1.0 - f) + D[:, b] * f
    v = (y + 0.5) * L / H
    rn = np.clip(np.floor(v).astype(int), 0, L - 1)
    vb = v - 0.5
    r0 = np.floor(vb).astype(int)
    fv = (vb - r0)[:, None, None]
    near = hrow(rn)
    bil = hrow(np.clip(r0, 0, L - 1)) * (1.0 - fv) + hrow(np.clip(r0 + 1, 0, L - 1)) * fv
    rgb = near * (1.0 - d['lineblend']) + bil * d['lineblend']
    out = inp[..., :4].copy() if inp.shape[-1] >= 4 else np.concatenate([inp[..., :3], np.ones((H, W, 1))], -1)
    t = d['amount']
    out[..., :3] = out[..., :3] * (1.0 - t) + rgb * t
    return out


def reference(img, pars=None, frame=0, fph=None):
    """Whole module on an (H, W, 3|4) image -> {'enc', 'sep', 'dec', 'out'} (each pass as its shader writes it)."""
    d = derive(pars or {})
    if fph is None:
        fph = frame_phase_of(d, frame)
    H, W = img.shape[:2]
    g = resample(img, d['ws'], d['lines'])
    e = encode(g, d, fph, frame)
    s = separate(e, d)
    c = decode(s, d, fph)
    return {'d': d, 'grid': g, 'enc': e, 'sep': s, 'dec': c, 'out': upsample(c, W, H, img, d)}


# ------------------------------------------------------------------ LIVE CHECK helper (runs inside TD)
PASS_CH = (('enc', 3), ('sep', 2), ('dec', 3), ('up', 4))


def parity(m):
    """Instance COMP m (FX_analog/ntsc1): every pass's texture vs the numpy reference on the same in1 frame, with the
    frame phase / frame number the shaders were given. Returns {pass: max abs diff}. Read in a separate exec after
    the pars settle (T-74); pause the input and set Crawl 0 + Noise 0 for a frame-exact read (docs N2)."""
    np = _np()
    p = raw(m)
    enc = m.op('enc')
    names = [getattr(enc.par, 'vec%dname' % i).eval() for i in range(enc.seq.vec.numBlocks)]
    iF = names.index('uF')
    fph = float(getattr(enc.par, 'vec%dvaluex' % iF).eval())
    frame = int(getattr(enc.par, 'vec%dvaluey' % iF).eval())
    inp = m.op('in1').numpyArray(delayed=False).astype(np.float64)
    R = reference(inp, p, frame=frame, fph=fph)
    out = {}
    for name, ch in PASS_CH:
        got = m.op(name).numpyArray(delayed=False).astype(np.float64)[..., :ch]
        ref = R['out' if name == 'up' else name][..., :ch]
        if name == 'up' and 'fixed' in str(getattr(m.op('in1'), 'pixelFormat', '')):     # e.g. '8-bit fixed (RGBA)'
            ref = np.clip(ref, 0.0, 1.0)              # an 8-bit out clamps peaking overshoot (live: 0.018 unclipped)
        out[name] = float(np.abs(got - ref).max()) if got.shape == ref.shape else 'shape %s vs %s' % (
            got.shape, ref.shape)
    out['fph'], out['frame'] = fph, frame
    return out


# ------------------------------------------------------------------ test cards (offline tests + LIVE CHECK inputs)
BARS = ((0.75, 0.75, 0.75), (0.75, 0.75, 0.0), (0.0, 0.75, 0.75), (0.0, 0.75, 0.0), (0.75, 0.0, 0.75),
        (0.75, 0.0, 0.0), (0.0, 0.0, 0.75))


def colour_bars(W, H):
    """75 % SMPTE-order bars, vertical (constant down every column)."""
    np = _np()
    img = np.ones((H, W, 4))
    idx = (np.arange(W) * len(BARS)) // W
    img[..., :3] = np.array(BARS)[idx][None, :, :]
    return img


def luma_stripes(W, H, ws, cycles_per_sample, amp=0.3, base=0.5):
    """Grey vertical stripes at a given frequency in signal samples (cycles_per_sample = cps -> cross-colour test)."""
    np = _np()
    x = (np.arange(W) + 0.5) * ws / W
    v = base + amp * np.cos(2.0 * math.pi * cycles_per_sample * x)
    img = np.ones((H, W, 4))
    img[..., :3] = v[None, :, None]
    return img
