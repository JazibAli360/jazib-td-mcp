# fx_analog_signal_logic - what the FX_analog modules 'vhs' and 'signalloss' share (both use every piece today,
# no-bloat rule): pure maths (no TD; tested offline by test/test_fx_analog_vhs.py), the numpy references the live
# checks diff against (numpy imported lazily), the GLSL hash / value-noise / tape-coordinate lib, the 1x1 `stamp`
# cook clock (T-111) and the Pulse -> time/count Parameter Execute. The GLSL in builders/fx_analog_vhs.py /
# fx_analog_signalloss.py mirrors these functions line for line; docs/builds/fx_analog_vhs.md and
# fx_analog_signalloss.md use them to predict pixel numbers.
# VHS numbers follow StageLab's JZB_Lofi_VHS (stagelab/ffgl/vhs/VhsLogic.h + VHS.cpp, read-only reference) so Arena
# and TD match: virtual raster (Lines follow the picture height, whole px per line, >= 3), noise step <= 24 Hz, 48-step
# dropout loop, 9 s tracking-band sweep, Glitch burst tau 0.4 s cut at 1 %. The rack is builders/fx_analog.py (= the
# FX_glitch rack); the modules exec this file at build time. stamp() / pulse_exec() / custom_res() / setp() run in TD
# only (they take the rack's H helpers). Arrays: TD texture order (row 0 = bottom, as numpyArray() returns). ASCII only.
import math

# ------------------------------------------------------------------ shared
LINE_AXES = ['x', 'y']          # x: lines run along the canvas width (a TV upright); y: the canvas is a TV on its side
U32 = 0xffffffff


def lround(x):
    """C lround for x >= 0 (half away from zero); Python's round() is half-even and would differ at .5."""
    return int(math.floor(x + 0.5))


def tape_dims(w, h, axis):
    """(S samples per line, L lines) of a w x h picture: axis 0 = lines along x, 1 = lines along y (TV on its side)."""
    return (h, w) if axis else (w, h)


def to_tape(x, y, w, h, axis):
    """Pixel (x, y) (TD: y up) -> tape (s, l). Axis 1 turns the TV 90 deg clockwise: s = h-1-y, l = x."""
    return (h - 1 - y, x) if axis else (x, y)


def to_pix(s, l, w, h, axis):
    return (l, h - 1 - s) if axis else (s, l)


def pcg(v):
    """PCG-RXS-M-XS 32 (StageLab VhsHash, the GLSL `pcg`)."""
    s = (v * 747796405 + 2891336453) & U32
    w = (((s >> ((s >> 28) + 4)) ^ s) * 277803737) & U32
    return ((w >> 22) ^ w) & U32


def hash01(a, b):
    """StageLab VhsHash01(a, b) = GLSL h01: (pcg(a + pcg(b)) >> 8) / 2^24, in [0, 1)."""
    return (pcg((a + pcg(b & U32)) & U32) >> 8) * (1.0 / 16777216.0)


def hh(cx, cy, s):
    """GLSL hh(ivec2(cx, cy), s): 2D cell hash in [0, 1) (per-line / per-tick randomness)."""
    return (pcg(((cx * 73856093) & U32) ^ pcg(((cy * 19349663) & U32) ^ pcg(s & U32))) >> 8) * (1.0 / 16777216.0)


def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3.0 - 2.0 * t)


def ease(k):
    k = min(1.0, max(0.0, k))
    return k * k * (3.0 - 2.0 * k)


def envelope(since, tau, floor=0.01):
    """exp(-since / tau), 0 before the press and below `floor` (the burst is over)."""
    if since < 0.0 or tau <= 0.0:
        return 0.0
    g = math.exp(-since / tau)
    return 0.0 if g < floor else g


def envelope_end(tau, floor=0.01):
    """Seconds until envelope() reaches 0 (= tau ln(1/floor)); the out switch keeps the module cooking until then."""
    return tau * math.log(1.0 / floor)


# ------------------------------------------------------------------ vhs (JZB_Lofi_VHS numbers)
VHS_NOISE_HZ = 24.0
VHS_MIN_PITCH = 3
VHS_SAMPLES_PER_H = 0.75
VHS_DROPOUT_LOOP = 48
VHS_GLITCH_TAU = 0.4
VHS_GLITCH_FLOOR = 0.01
VHS_BAND_PERIOD = 9.0
VHS_LINES = ['240', '480', '576']
VHS_CHROMA_TAPS = 24            # one-sided chroma taps (StageLab: 16; 24 so 2-3 generations still fit)
VHS_MAX_LUMA_PASSES = 7         # binomial [1 2 1] passes the sig shader loops over (15 taps)
VHS_MAX_GENS = 5
# Tape speed: (extra luma [1 2 1] passes, chroma tau x, noise x, jitter x). SP = the StageLab look.
TAPE_SPEEDS = ['sp', 'lp', 'ep']
TAPE_SPEED = {'sp': (0, 1.0, 1.0, 1.0), 'lp': (1, 1.35, 1.4, 1.3), 'ep': (2, 1.7, 2.0, 1.7)}
# YIQ (FCC NTSC), used by the GLSL and the numpy reference alike.
RGB2YIQ = ((0.299, 0.587, 0.114), (0.595716, -0.274453, -0.321263), (0.211456, -0.522591, 0.311135))
YIQ2RGB = ((1.0, 0.9563, 0.6210), (1.0, -0.2721, -0.6474), (1.0, -1.1070, 1.7046))


def line_pitch(L, lines):
    if L < 1 or lines < 1:
        return VHS_MIN_PITCH
    return max(VHS_MIN_PITCH, lround(float(L) / float(lines)))


def raster(w, h, lines, axis=0):
    """Virtual raster of a w x h picture: {pitch, vw, vh, S, L, tx, ty} (StageLab VhsRasterFor + its encode taps)."""
    S, L = tape_dims(max(w, 1), max(h, 1), axis)
    pitch = line_pitch(L, int(lines))
    vh = max(1, -(-L // pitch))
    vw = min(max(1, lround(vh * VHS_SAMPLES_PER_H * S / float(L))), S)
    tx = min(8, max(1, -(-S // (2 * vw))))
    ty = min(4, max(1, -(-pitch // 2)))
    return {'pitch': pitch, 'vw': vw, 'vh': vh, 'S': S, 'L': L, 'tx': tx, 'ty': ty}


# The same raster as ONE TD expression (tuple pitch, vw, vh, tx, ty); `[k]` picks one. Tested against raster().
RASTER_LAMBDA = (
    "(lambda W, H, n, ay: (lambda S, L: (lambda pt: (lambda vh: (lambda vw: (pt, vw, vh, min(8, max(1, -(-S // (2 * vw)))),"
    " min(4, max(1, -(-pt // 2)))))(min(max(1, int(vh * 0.75 * S / float(L) + 0.5)), S)))(max(1, -(-L // pt))))"
    "(max(3, int(L / float(n) + 0.5))))(*((H, W) if ay else (W, H))))")
RASTER_ARGS = "(max(1, {src}.width), max(1, {src}.height), int(parent().par.Lines.eval()), parent().par.Lineaxis.menuIndex)"
RASTER_INDEX = {'pitch': 0, 'vw': 1, 'vh': 2, 'tx': 3, 'ty': 4}


def raster_expr(key, src="op('in1')"):
    return RASTER_LAMBDA + RASTER_ARGS.format(src=src) + "[%d]" % RASTER_INDEX[key]


def noise_frames(fps):
    """Frames per noise step so steps stay <= 24 Hz (24 -> 1, 25/30 -> 2, 50/60 -> 3)."""
    if not fps > 0:
        return 1
    return max(1, int(math.ceil(fps / VHS_NOISE_HZ - 1e-4)))


NOISE_STEP_EXPR = "float(absTime.frame // max(1, int(math.ceil(project.cookRate / 24.0 - 1e-4))))"


def dropout_index(step, seed, randomness):
    """Pattern index a noise step shows: Randomness 0 = step mod 48; r = leaves the loop with probability r."""
    r = min(1.0, max(0.0, randomness))
    if r > 0.0 and hash01(step & U32, (seed * 7919 + 17) & U32) < r:
        return (VHS_DROPOUT_LOOP + step) & U32
    return step % VHS_DROPOUT_LOOP


def seed_phase(seed):
    return hash01(seed & U32, 0x5eed)


def band_loop(t, seed):
    """Tracking band centre (0 bottom .. 1 top) at Randomness 0: 9 s sine sweep, phase from Seed."""
    return 0.5 + 0.42 * math.sin(2.0 * math.pi * (t / VHS_BAND_PERIOD + seed_phase(seed)))


def glitch_envelope(since):
    return envelope(since, VHS_GLITCH_TAU, VHS_GLITCH_FLOOR)


GLITCH_END = envelope_end(VHS_GLITCH_TAU, VHS_GLITCH_FLOOR)      # 1.842 s


def glitch_pos(n, seed, randomness):
    """Centre (0..1 of the height, 0 = bottom) of Glitch press number n."""
    loop = 0.15 + 0.7 * math.fmod(seed_phase(seed) + 0.381966 * n, 1.0)
    rnd = 0.1 + 0.8 * hash01(n & U32, (seed * 104729 + 3) & U32)
    r = min(1.0, max(0.0, randomness))
    return loop + (rnd - loop) * r


def glitch_band(since, n, seed, randomness):
    """(centre, half height, strength) of the Glitch band `since` s after press n (StageLab: drifts up, narrows)."""
    g = glitch_envelope(since)
    return (glitch_pos(n, seed, randomness) + (1.0 - g) * 0.08, 0.08 + 0.1 * g, g)


def speed(name_or_index):
    k = TAPE_SPEEDS[name_or_index] if isinstance(name_or_index, int) else name_or_index
    return TAPE_SPEED[k]


def chroma_tau(bleed, tape='sp'):
    return (0.3 + 4.7 * min(1.0, max(0.0, bleed))) * speed(tape)[1]


def chroma_shift_total(shift, gens):
    """Each dub delays the colour again (half the first copy's shift per extra generation)."""
    return shift * (1.0 + 0.5 * (max(1, int(gens)) - 1))


def chroma_weights(tau, gens, taps=VHS_CHROMA_TAPS):
    """One-sided weights of `gens` cascaded exponential filters (r = exp(-1/tau)) = negative binomial
    C(k+n-1, n-1) r^k, k = 0..taps-1, normalised: what n passes of StageLab's chroma filter give (up to the cut)."""
    n = max(1, int(gens))
    r = math.exp(-1.0 / max(tau, 1e-6))
    w, out = 1.0, []
    for k in range(taps):
        if k:
            w *= r * (k + n - 1) / float(k)
        out.append(w)
    s = sum(out)
    return [x / s for x in out]


def luma_passes(gens, tape='sp'):
    return min(VHS_MAX_LUMA_PASSES, max(1, int(gens)) + speed(tape)[0])


def luma_weights(passes):
    """`passes` [1 2 1]/4 low-passes = binomial C(2n, j) / 4^n, taps -n..n."""
    n = max(1, int(passes))
    return [math.comb(2 * n, j) / float(4 ** n) for j in range(2 * n + 1)]


def gen_saturation(gens):
    return 0.92 ** (max(1, int(gens)) - 1)


def scanline_gain(py, pitch, scan, amount):
    """Output multiplier of tape row centre py (= row + 0.5)."""
    f = 0.5 - 0.5 * math.cos(2.0 * math.pi * math.fmod(py / pitch, 1.0))
    return 1.0 - scan * amount * 0.6 * (1.0 - f)


def headswitch_rows(L, pitch, lines):
    """Tape rows (from the bottom, l = 0) the head-switch zone covers: `lines` virtual lines."""
    return min(L, max(0, int(lines)) * pitch)


def vhs_active_expr():
    """TD expression: 1 while vhs must cook (Amount > 0 or a Glitch burst still running), else 0 (in1 straight out)."""
    return ("(1 if (parent().par.Amount.eval() > 0 or absTime.seconds - parent().par.Glitchtime.eval() < %.4f) else 0)"
            % GLITCH_END)


# ------------------------------------------------------------------ signalloss
SL_CARDS = ['blue', 'snow', 'black', 'bars']
SL_INTERLACE = ['off', 'weave', 'bob', 'blend']
SL_LINE_PX = 4.0                # power-off: the picture collapses to a line this many px thick ...
SL_DOT_PX = 8.0                 # ... then to a dot this many px wide (even px: pixel centres never sit on the edge)
SL_HIT_FLOOR = 0.01
SL_BAR_LEVEL = 0.02             # the V-hold blanking bar (near black)
BARS = ((0.75, 0.75, 0.75), (0.75, 0.75, 0.0), (0.0, 0.75, 0.75), (0.0, 0.75, 0.0), (0.75, 0.0, 0.75),
        (0.75, 0.0, 0.0), (0.0, 0.0, 0.75))     # 75 % colour bars along the line


def power_state(now, off_t, on_t, dur, warm, hold, manual=-1.0):
    """-> (mode, k). mode 0 normal, 1 collapsing (k = phase 0..1), 2 off (black), 3 warming up (k = 0..1).
    manual >= 0 holds the collapse at that phase (a fader / live check); >= 1 shows the off state (black)."""
    if manual >= 0.0:
        return (1, manual) if manual < 1.0 else (2, 1.0)
    if off_t > on_t:
        p = (now - off_t) / max(dur, 1e-3)
        if p < 1.0:
            return 1, max(0.0, p)
        return (2, 1.0) if hold else (0, 0.0)
    if on_t > -999.0 and now - on_t < warm:
        return 3, max(0.0, (now - on_t) / max(warm, 1e-3))
    return 0, 0.0


def collapse(p, S, L, glow):
    """Power-off collapse at phase p: (sx, sy, gain, white). sy squeezes the TV's vertical (lines) to a line of
    SL_LINE_PX, then sx squeezes it to a dot of SL_DOT_PX, then the dot fades. Tape dims (S along a line, L lines)."""
    ly = min(1.0, SL_LINE_PX / max(L, 1))
    dx = min(1.0, SL_DOT_PX / max(S, 1))
    if p < 0.5:
        k = ease(p / 0.5)
        return 1.0, 1.0 + (ly - 1.0) * k, 1.0 + (glow - 1.0) * k, k
    if p < 0.8:
        k = ease((p - 0.5) / 0.3)
        return 1.0 + (dx - 1.0) * k, ly, glow, 1.0
    if p < 1.0:
        return dx, ly, glow * (1.0 - (p - 0.8) / 0.2), 1.0
    return dx, ly, 0.0, 1.0


def warmup(q):
    """Power-on at q 0..1: (scale, gain): the picture grows from 55 % and brightens (q^2)."""
    q = min(1.0, max(0.0, q))
    return 0.55 + 0.45 * ease(q), q * q


def collapse_lit(n, scale):
    """Rows (or columns) of n inside the collapsed picture: |i + 0.5 - n/2| <= scale n / 2 (pixel units, as the
    shader tests it)."""
    return sum(1 for i in range(n) if abs(i + 0.5 - 0.5 * n) <= 0.5 * scale * n)


def vroll_line(l, L, roll, bar):
    """V-hold, pixel units like the shader: screen tape row l -> source row, or None inside the blanking bar.
    roll = Vpos + Vroll t (+ jumps), in picture heights; the bar is `bar` picture heights tall."""
    per = L * (1.0 + bar)
    y = math.fmod(l + 0.5 + roll * L, per)
    if y < 0:
        y += per
    return None if y >= L else int(math.floor(y))


def slant_src(s, l, S, slant):
    """H-hold drift: tape sample s on line l comes from floor((s + 0.5 - slant l) mod S) (diagonal bars)."""
    return int(math.floor((s + 0.5 - slant * l) % S))


def hit_envelope(since, decay):
    return envelope(since, decay, SL_HIT_FLOOR)


def signalloss_active_expr():
    """TD expression: 1 while signalloss must cook (Amount > 0, a Hit burst, a power transition / off state, manual
    phase), else 0 (in1 straight through, the shader not pulled). Same rules as power_state + hit_envelope."""
    return ("(1 if (parent().par.Amount.eval() > 0 or parent().par.Powerphase.eval() >= 0"
            " or absTime.seconds - parent().par.Hittime.eval() < parent().par.Hitdecay.eval() * %.4f"
            " or parent().par.Offtime.eval() > parent().par.Ontime.eval()"
            " or absTime.seconds - parent().par.Ontime.eval() < parent().par.Warmup.eval()) else 0)"
            % math.log(1.0 / SL_HIT_FLOOR))


# ------------------------------------------------------------------ numpy references (offline + live checks)
def _np():
    import numpy
    return numpy


def tape_of(img, axis):
    """TD-order image (H, W, C) -> tape array (L, S, C): rows = lines from the bottom, columns = samples."""
    return img[::-1].transpose(1, 0, 2) if axis else img


def pix_of(tape, axis):
    return tape.transpose(1, 0, 2)[::-1] if axis else tape


def ref_vhs_encode(img, lines='480', axis=0):
    """Mirror of the vhs `enc` shader: per virtual sample a tx x ty point average (texelFetch at floor positions),
    RGB -> YIQ, stored rgba16float. img float (H, W, 4), TD order. Returns (L_v, S_v, 4) float16."""
    np = _np()
    f32 = np.float32
    h, w = img.shape[:2]
    R = raster(w, h, lines, axis)
    T = tape_of(np.asarray(img, dtype=f32), axis)
    S, L, vw, vh, pt, tx, ty = R['S'], R['L'], R['vw'], R['vh'], R['pitch'], R['tx'], R['ty']
    ox = np.arange(vw, dtype=f32)
    x0 = ox * f32(S) / f32(vw)
    x1 = (ox + f32(1)) * f32(S) / f32(vw)
    oy = np.arange(vh, dtype=f32)
    y0 = oy * f32(pt)
    y1 = np.minimum((oy + f32(1)) * f32(pt), f32(L))
    fi = (np.arange(tx, dtype=f32) + f32(0.5)) / f32(tx)
    fj = (np.arange(ty, dtype=f32) + f32(0.5)) / f32(ty)
    X = np.clip(np.floor(x0[:, None] + fi[None, :] * (x1 - x0)[:, None]).astype(int), 0, S - 1)    # (vw, tx)
    Y = np.clip(np.floor(y0[:, None] + fj[None, :] * (y1 - y0)[:, None]).astype(int), 0, L - 1)    # (vh, ty)
    s = T[Y[:, :, None, None], X[None, None, :, :]].mean(axis=(1, 3), dtype=f32)                  # (vh, vw, 4)
    c = np.clip(s[..., :3], 0.0, 1.0)
    M = np.array(RGB2YIQ, dtype=f32)
    out = np.concatenate([c @ M.T, s[..., 3:4]], axis=-1)
    return out.astype(np.float16)


def ref_vhs_signal(enc, sharpen=0.3, shift=1.5, tau=None, gens=1, passes=None, bleed=0.5, tape='sp'):
    """Mirror of the vhs `sig` shader on an encoded raster (L_v, S_v, 4): binomial luma low-pass + one-sided ring,
    chroma shifted right by `shift` and smeared by the negative-binomial kernel; float16 out."""
    np = _np()
    e = np.asarray(enc, dtype=np.float64)
    vh, vw = e.shape[:2]
    tau = chroma_tau(bleed, tape) if tau is None else tau
    n = luma_passes(gens, tape) if passes is None else passes
    xs = np.arange(vw)

    def col(i):
        return e[:, np.clip(i, 0, vw - 1)]

    lw = luma_weights(n)
    yl = sum(wj * col(xs - n + j)[..., 0] for j, wj in enumerate(lw))
    left = 0.5 * (col(xs - 1)[..., 0] + col(xs - 2)[..., 0])
    ys = yl + sharpen * 1.5 * (yl - left)
    cw = chroma_weights(tau, gens)
    acc = 0.0
    for k, wk in enumerate(cw):
        sx = xs - shift - k
        f0 = np.floor(sx).astype(int)
        fr = (sx - f0)[None, :, None]
        acc = acc + wk * (col(f0)[..., 1:3] * (1 - fr) + col(f0 + 1)[..., 1:3] * fr)
    out = np.concatenate([ys[..., None], acc, e[..., 3:4]], axis=-1)
    return out.astype(np.float16)


def ref_vhs_clean(img, amount=1.0, lines='480', axis=0, sharpen=0.3, shift=1.5, bleed=0.5, gens=1, tape='sp',
                  scan=0.3, sat=0.8, warmth=0.2):
    """The whole vhs module in its deterministic setting (Wobble, Flagging, Tracking, Noise, Dropouts 0, Head Switch
    and Interlace off, no Glitch): enc -> sig -> composite with Saturation / Warmth / Scanlines / Amount. Float
    (H, W, 4) out in TD order; compare with out1 within 8-bit rounding (docs/builds/fx_analog_vhs.md V3)."""
    np = _np()
    img = np.asarray(img, dtype=np.float32)
    h, w = img.shape[:2]
    R = raster(w, h, lines, axis)
    sig = ref_vhs_signal(ref_vhs_encode(img, lines, axis), sharpen, chroma_shift_total(shift, gens), None, gens,
                         None, bleed, tape).astype(np.float32)
    T = tape_of(img, axis)
    S, L, vw, vh, pt = R['S'], R['L'], R['vw'], R['vh'], R['pitch']
    l = np.arange(L)
    s = np.arange(S)
    line = np.minimum(np.floor(l / float(pt)).astype(int), vh - 1)
    u = (s + 0.5) / S
    sx = u * vw
    q = sx - 0.5
    f0 = np.floor(q).astype(int)
    fr = (q - f0)[None, :, None]
    a = sig[line][:, np.clip(f0, 0, vw - 1)]
    b = sig[line][:, np.clip(f0 + 1, 0, vw - 1)]
    e = a * (1 - fr) + b * fr                                                    # (L, S, 4)
    Y = e[..., 0] * 0.94 + 0.04
    I = e[..., 1] * sat * gen_saturation(gens) + warmth * 0.08
    Q = e[..., 2] * sat * gen_saturation(gens)
    M = YIQ2RGB
    rgb = np.clip(np.stack([Y + M[0][1] * I + M[0][2] * Q, Y + M[1][1] * I + M[1][2] * Q,
                            Y + M[2][1] * I + M[2][2] * Q], -1), 0.0, 1.0)
    sp = np.clip(np.floor(sx / vw * S).astype(int), 0, S - 1)
    inp = T[:, sp, :3]
    col = inp * (1 - amount) + rgb * amount
    py = l + 0.5
    f = 0.5 - 0.5 * np.cos(2 * np.pi * np.mod(py / pt, 1.0))
    col = col * (1.0 - scan * amount * 0.6 * (1.0 - f))[:, None, None]
    out = np.concatenate([np.clip(col, 0.0, 1.0), T[..., 3:4]], -1)
    return pix_of(out, axis)


def ref_sl_vhold(img, vpos, vbar, axis=0):
    """signalloss with only Vpos / Vbar set (Amount 1, Vroll 0): rows remapped, the bar at SL_BAR_LEVEL."""
    np = _np()
    T = tape_of(np.asarray(img, dtype=np.float32), axis)
    L = T.shape[0]
    out = np.empty_like(T)
    for l_ in range(L):
        src = vroll_line(l_, L, vpos, vbar)
        if src is None:
            out[l_, :, :3] = SL_BAR_LEVEL
            out[l_, :, 3] = T[l_, :, 3]
        else:
            out[l_, :, :3] = T[src, :, :3]
            out[l_, :, 3] = T[l_, :, 3]
    return pix_of(out, axis)


def ref_sl_slant(img, slant, axis=0):
    """signalloss with only Hslant set (Amount 1): out(s, l) = in(floor((s + 0.5 - slant l) mod S), l)."""
    np = _np()
    T = tape_of(np.asarray(img, dtype=np.float32), axis)
    L, S = T.shape[:2]
    l = np.arange(L)[:, None]
    s = np.arange(S)[None, :]
    src = np.floor(np.mod(s + 0.5 - slant * l, S)).astype(int)
    out = T.copy()
    out[..., :3] = T[l, src, :3]
    return pix_of(out, axis)


# ------------------------------------------------------------------ shared GLSL + TD helpers (vhs, signalloss)
P = "parent().par.{}.eval()"
AXIS_PAR = ('Lineaxis', 'Menu', 'x', {'names': LINE_AXES, 'labels': ['Along X (TV upright)', 'Along Y (TV on its side)']})

# pcg = StageLab VhsHash (pcg above), h01 = VhsHash01 (hash01), hh = 2D cell hash (hh), value noise, tape coordinates
# (to_tape / to_pix above).
GLSL_LIB = """
uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h01(uint a, uint b) { return float(pcg(a + pcg(b)) >> 8) * (1.0 / 16777216.0); }
float hh(ivec2 c, uint s) { return float(pcg((uint(c.x) * 73856093u) ^ pcg((uint(c.y) * 19349663u) ^ pcg(s))) >> 8)
                                   * (1.0 / 16777216.0); }
float vn1(float x, uint s) { float i = floor(x); float f = x - i; f = f * f * (3.0 - 2.0 * f);
                             return mix(hh(ivec2(int(i), 0), s), hh(ivec2(int(i) + 1, 0), s), f); }
float vn2(vec2 x, uint s) { ivec2 i = ivec2(floor(x)); vec2 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hh(i, s), hh(i + ivec2(1, 0), s), f.x), mix(hh(i + ivec2(0, 1), s), hh(i + ivec2(1, 1), s), f.x), f.y); }
float ease(float k) { k = clamp(k, 0.0, 1.0); return k * k * (3.0 - 2.0 * k); }
ivec2 tdims(ivec2 isz, bool ay) { return ay ? isz.yx : isz; }
ivec2 to_tape(ivec2 p, ivec2 isz, bool ay) { return ay ? ivec2(isz.y - 1 - p.y, p.x) : p; }
ivec2 to_pix(ivec2 t, ivec2 isz, bool ay) { return ay ? ivec2(t.y, isz.y - 1 - t.x) : t; }
"""

STAMP = """// stamp: 1x1 rgba32float in place (T-111): x = now, y = the previous cook's now. Cooks only when fx does.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;
void main() {
    vec4 s = TDImageLoadOutput(0, ivec3(0));
    if (s.x == uT.x) return;                    // a second cook in the same frame (readback / force cook): keep
    TDImageStoreOutput(0, ivec3(0), vec4(uT.x, s.x, 0.0, 1.0));
}
"""

PULSE_EXEC = """# Pulse pars -> a time stamp par (absTime.seconds) and a press counter the shaders read (no per-frame Python).
TARGET = %r

def onPulse(par):
\tt = TARGET.get(par.name)
\tif t is None:
\t\treturn
\to = par.owner
\tgetattr(o.par, t[0]).val = absTime.seconds
\tif t[1]:
\t\tc = getattr(o.par, t[1])
\t\tc.val = int(c.eval()) + 1
\treturn
"""


def stamp(m, H):
    """TD only: the 1x1 rgba32float cook clock (rack H = the fx_glitch helpers compute / uniforms)."""
    st = H['compute'](m, 'stamp', STAMP, [], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    H['uniforms'](st, [('uT', ['absTime.seconds', '0', '0', '0'])])
    st.comment = 'Cook clock: x now, y previous cook; a gap > 0.25 s = bypassed -> the previous-frame cache is stale.'
    return st


def pulse_exec(m, H, targets):
    """TD only: targets {Pulse par: (time par, count par or '')} -> Parameter Execute `pulses` (mosh pattern)."""
    pe = H['mk'](m, parameterexecuteDAT, 'pulses')  # noqa: F821 (TD global)
    txt = PULSE_EXEC % dict(targets)
    if pe.text != txt:
        pe.text = txt
        pe.par.active = False                              # T-97: toggle after a text rewrite
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = ' '.join(sorted(targets))
    pe.par.valuechange = False
    pe.par.onpulse = True
    pe.par.active = True
    pe.comment = 'Pulses %s -> time / count pars on the State page (read by the shaders).' % ' '.join(sorted(targets))
    return pe


def custom_res(g, H, w_expr, h_expr):
    """TD only: the rack's compute() takes constant sizes; analog rasters need expressions."""
    g.par.outputresolution = 'custom'
    H['expr'](g.par.resolutionw, w_expr)
    H['expr'](g.par.resolutionh, h_expr)


def setp(o, H, **kw):
    """TD only: set pars that may differ by build; '=expr' sets an expression. Returns the missing names."""
    missing = []
    for k, v in kw.items():
        p = getattr(o.par, k, None)
        if p is None:
            missing.append(k)
        elif isinstance(v, str) and v.startswith('='):
            H['expr'](p, v[1:])
        else:
            p.val = v
    return missing


def speed_list(i):
    """'[a, b, c][parent().par.Tapespeed.menuIndex]' for TAPE_SPEED column i (uniform expressions)."""
    return '[%s][parent().par.Tapespeed.menuIndex]' % ', '.join(repr(float(TAPE_SPEED[k][i])) for k in TAPE_SPEEDS)
