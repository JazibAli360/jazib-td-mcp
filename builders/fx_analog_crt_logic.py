# fx_analog_crt_logic - pure maths for FX_analog modules 'crt' (+ its 'monitor' presets) and 'crtfault'.
# Copied into each module instance as the Text DAT `crt_logic` (the clock Script CHOP and the Parameter Execute use it
# there), and tested offline (test/test_fx_analog_crt.py). Pure maths + shared shader / callback texts; numpy only
# inside the reference functions; the two td_* helpers at the end run only from the module builders.
# Parity source: StageLab JZB_Lofi_CRT (stagelab/ffgl/crt/CrtLogic.h + CRT.cpp, 2026-10-16): same control names,
# ranges and constants; raster, mask, warp, flicker step, roll lock-in, Degauss envelope, purity waves are ports of it.
# Extras from docs/research/FX2_analog_video_hardware_emulation.md AV-01..AV-08 (convergence, focus, persistence,
# interlace, scan bar, phosphor colours, damper wires) and AV-07 (tear, jitter, bend, wobble, breathing, arcs, power).
# Owned by the crt lane (file names fx_analog_crt*): other FX_analog modules keep their own logic files.
# ASCII only (TD reads this file).
import math

# ---- constants (JZB_Lofi_CRT CrtLogic.h) ----
MIN_PITCH = 3            # output px per virtual line, at least (LED rule)
MIN_MASK, MAX_MASK = 3, 12
FLICKER_HZ = 24.0        # fastest flicker step rate
FLICKER_DEPTH = 0.5
LINE_FLICKER = 0.4
WARP_MAX = 0.25          # Curvature 1: each edge bows by 0.25 * half the height at the corners
CORNER_MAX = 0.5         # Corner 1: radius = a quarter of the height
ROLL_MAX = 1.5           # screens/s at Roll +-1
ROLL_BAR = 0.08          # blanking bar, fraction of the picture height
ROLL_SETTLE = 0.6        # least speed a roll finishes at after Roll goes back to 0
HUM_SPEED = 0.1          # screens/s the hum bar drifts up
HUM_DEPTH = 0.4          # Hum Bar 1 = 40 % dip at the bar centre
DEGAUSS_TAU = 0.45
DEGAUSS_FLOOR = 0.01     # below this the Degauss is over (~2.1 s)
GLOW_DIV = 8             # halation source: 1/8 of the output per axis
PURITY_RND = 0.1         # Randomness 1: colour-purity blotch amplitude
PURITY_DEGAUSS = 0.8
CONV_RND = 0.6           # Randomness 1: misconvergence, virtual px
SHAKE = 0.012            # Degauss wobble amplitude, picture fraction
# ---- FX_analog extras ----
ARC_RATE = 0.04          # Arc 1: chance per frame that an arc flash starts
ARC_DECAY = 0.5          # flash level kept per frame
GAP_RESET = 0.25         # s: a cook gap longer than this = history (persistence / weave) restarts
CLOCK_ROWS = 13          # vec4 rows the clock CHOP feeds the shaders as uniform array uK[]
MASKS = ['off', 'aperture', 'slot', 'shadow', 'lcd']
PHOSPHORS = ['colour', 'white', 'green', 'amber']
PHOSPHOR_TINT = {'colour': (1.0, 1.0, 1.0), 'white': (0.93, 0.95, 1.0), 'green': (0.25, 1.0, 0.35),
                 'amber': (1.0, 0.62, 0.12)}
# pars the clock reads (menus as index, toggles as 0/1); missing ones fall back to the defaults in clock_step
CLOCK_PARS = ['Amount', 'Roll', 'Rollbar', 'Flicker', 'Humbar', 'Humspeed', 'Seed', 'Randomness', 'Degausstime',
              'Degausscount', 'Degaussamt', 'Tearspeed', 'Arc', 'Power', 'Powertime', 'Powerdur', 'Crawl',
              'Scanbarspeed', 'Scanlines']

M32 = 0xffffffff


def _f(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def iround(x):
    """C lround for x >= 0 (half away from zero); Python round() is banker's rounding."""
    return int(math.floor(x + 0.5))


# ---- hashes (CrtLogic.h CrtHash = PCG-RXS-M-XS 32; the GLSL `pcg` in GLSL_LIB is the same) ----
def pcg(v):
    s = (v * 747796405 + 2891336453) & M32
    w = (((s >> ((s >> 28) + 4)) ^ s) * 277803737) & M32
    return ((w >> 22) ^ w) & M32


def h01(a, b):
    """CrtHash01: [0, 1), 24 bits."""
    return (pcg((a + pcg(b & M32)) & M32) >> 8) * (1.0 / 16777216.0)


def seeded_noise(seed, x):
    """Smooth 1D value noise in -1..1 (the 'slips' of roll / hum / tear speed)."""
    i = int(math.floor(x))
    f = x - i
    f = f * f * (3.0 - 2.0 * f)
    a, b = h01(i & M32, seed), h01((i + 1) & M32, seed)
    return 2.0 * (a + (b - a) * f) - 1.0


# ---- virtual raster ----
def line_pitch(out_h, lines):
    if out_h < 1 or lines < 1:
        return MIN_PITCH
    return max(MIN_PITCH, iround(float(out_h) / float(lines)))


def raster_for(w, h, lines, axis=0):
    """-> (pitch, vw, vh) of the virtual raster. axis 1 = lines run down the canvas (TV on its side): the logical
    frame is the canvas turned, so w and h swap. Square virtual pixels, each line >= 3 output px."""
    if int(axis) == 1:
        w, h = h, w
    w, h = max(int(w), 1), max(int(h), 1)
    p = line_pitch(h, int(lines))
    vh = max(1, (h + p - 1) // p)
    vw = int(_f(iround(float(w) / p), 1, w))
    return p, vw, vh


def raster_wh(w, h, lines, axis=0):
    p, vw, vh = raster_for(w, h, lines, axis)
    return vw, vh


def glow_wh(w, h, axis=0):
    if int(axis) == 1:
        w, h = h, w
    return max(1, int(w) // GLOW_DIV), max(1, int(h) // GLOW_DIV)


def raster_taps(pitch):
    return int(_f((int(pitch) + 1) // 2, 1, 8))


def sharp_slope(sharpness):
    """Sharpness 0..1 -> horizontal resample slope (1 = linear, larger = crisper); JZB formula, no upper clamp."""
    return 1.0 / max(1e-3, 1.0 - 0.92 * float(sharpness))


# ---- phosphor mask (CrtMaskChannel + 'lcd') ----
def mask_channel(kind, size, x, y):
    """Which phosphor output px (x, y) (GL order) shows: 0 R, 1 G, 2 B, -1 dark gap, -2 no mask (off).
    kind: 0 off, 1 aperture, 2 slot, 3 shadow, 4 lcd (square cells, stripes + one dark row per cell from 4 px)."""
    size = int(_f(int(size), MIN_MASK, MAX_MASK))
    x, y = max(int(x), 0), max(int(y), 0)
    sub = size // 3
    if kind == 2:
        gap = max(1, size // 4)
        yy = (y + ((x // size) & 1) * (size // 2)) % size
        if yy < gap:
            return -1
    elif kind == 3:
        row_h = max(2, (size + 1) // 2)
        row = y // row_h
        if row_h >= 3 and y % row_h == row_h - 1:
            return -1
        x += (row & 1) * (size // 2)
    elif kind == 4:
        if size >= 4 and y % size == size - 1:
            return -1
    elif kind != 1:
        return -2
    k = (x % size) // sub
    return k if k < 3 else -1


def mask_channel_np(kind, size, x, y):
    """Vectorised mask_channel (same integer formula) for whole frames."""
    import numpy as np
    size = int(_f(int(size), MIN_MASK, MAX_MASK))
    sub = size // 3
    x, y = np.maximum(x, 0), np.maximum(y, 0)
    gap = np.zeros(x.shape, dtype=bool)
    if kind == 2:
        gap = ((y + ((x // size) & 1) * (size // 2)) % size) < max(1, size // 4)
    elif kind == 3:
        row_h = max(2, (size + 1) // 2)
        if row_h >= 3:
            gap = (y % row_h) == row_h - 1
        x = x + ((y // row_h) & 1) * (size // 2)
    elif kind == 4:
        if size >= 4:
            gap = (y % size) == size - 1
    elif kind != 1:
        return np.full(x.shape, -2)
    k = (x % size) // sub
    return np.where(gap | (k >= 3), -1, k)


def mask_rows(kind, size):
    size = int(_f(int(size), MIN_MASK, MAX_MASK))
    if kind == 2:
        return 2 * size
    if kind == 3:
        return 2 * max(2, (size + 1) // 2)
    if kind == 4:
        return size
    return 1


def mask_weights(strength):
    """(dark phosphor weight, lit phosphor weight) for Mask Strength (JZB maskLD)."""
    m = float(strength)
    return 1.0 - m, 1.0 + 0.5 * m


# ---- barrel warp ----
def warp(x, y, k, aspect, curve_axis=0):
    """Screen point (-1..1) -> picture point. curve_axis 0 both, 1 'x' (left/right edges bow), 2 'y'."""
    kx, ky = k / max(aspect, 1e-6), k
    if curve_axis == 1:
        ky = 0.0
    elif curve_axis == 2:
        kx = 0.0
    return x * (1.0 + y * y * kx), y * (1.0 + x * x * ky)


# ---- flicker ----
def flicker_frames(fps):
    if not fps > 0:
        return 1
    return max(1, int(math.ceil(fps / FLICKER_HZ - 1e-4)))


def flicker_level(step, seed, randomness):
    r = _f(float(randomness), 0.0, 1.0)
    regular = 1.0 if (step & 1) else 0.0
    return regular + (h01(step & M32, (seed * 7919 + 101) & M32) - regular) * r


# ---- V-hold roll (CrtRoll) ----
def roll_step(phase, last, dt, speed):
    """-> (phase, last). Roll 0 finishes a roll in its last direction (>= 0.6 screens/s) and locks at exactly 0."""
    if not dt > 0:
        return phase, last
    if speed != 0:
        phase += speed * dt
        return phase - math.floor(phase), speed
    if phase == 0.0:
        return phase, last
    d = -1.0 if last < 0 else 1.0
    nxt = phase + d * max(abs(last), ROLL_SETTLE) * dt
    if (d > 0 and nxt >= 1.0) or (d < 0 and nxt <= 0.0):
        return 0.0, last
    return nxt, last


# ---- Degauss + purity ----
def degauss_env(since):
    if since < 0:
        return 0.0
    g = math.exp(-since / DEGAUSS_TAU)
    return 0.0 if g < DEGAUSS_FLOOR else g


def purity_waves(seed):
    """CrtPurityWaves: -> (waves[12] = 3 guns x (k1.x k1.y k2.x k2.y), phases[6] = first waves R G B, then second)."""
    waves, phases = [0.0] * 12, [0.0] * 6
    for i in range(6):
        a = 6.2831853 * h01((seed * 977 + i) & M32, 0xa1)
        f = 6.2831853 * (1.1 + 1.4 * h01((seed * 977 + i) & M32, 0xa2))
        waves[(i // 2) * 4 + (i % 2) * 2 + 0] = f * math.cos(a)
        waves[(i // 2) * 4 + (i % 2) * 2 + 1] = f * math.sin(a)
        phases[(i % 2) * 3 + i // 2] = 6.2831853 * h01((seed * 977 + i) & M32, 0xa3)
    return waves, phases


def conv_dirs(seed):
    return [2.0 * h01(seed & M32, c) - 1.0 for c in (0xc0, 0xc1, 0xc2, 0xc3)]


# ---- power off / on (crtfault, AV-07) ----
LINE_H = 0.004           # the collapsed bright line, picture heights


def power_shape(on, since, dur):
    """-> (sy, sx, gain, dot): vertical / horizontal picture scale, picture gain, centre dot level.
    Off: 0-35 % of dur squeeze to a bright line, 35-55 % the line to a dot, 55-100 % the dot fades; then black.
    On: dim and small (60 %) growing to full over dur. Steady on = (1, 1, 1, 0)."""
    d = max(float(dur), 1e-3)
    s = since / d if since >= 0 else 1e9
    if on:
        if s >= 1.0:
            return 1.0, 1.0, 1.0, 0.0
        e = s * s * (3.0 - 2.0 * s)
        return 0.6 + 0.4 * e, 0.75 + 0.25 * e, e, 0.0
    if s < 0.35:
        e = s / 0.35
        sy = 1.0 - (1.0 - LINE_H) * (e * e)
        return sy, 1.0, min(1.0 / math.sqrt(sy), 4.0), 0.0
    if s < 0.55:
        e = (s - 0.35) / 0.2
        sx = 1.0 - (1.0 - LINE_H) * e
        return LINE_H, sx, 4.0, 0.0
    if s < 1.0:
        return 0.0, 0.0, 0.0, math.exp(-6.0 * (s - 0.55) / 0.45)
    return 0.0, 0.0, 0.0, 0.0


# ---- the per-frame clock (Script CHOP `clock` -> uniform array uK[CLOCK_ROWS]) ----
def clock_init():
    return {'last': -1.0, 't': 0.0, 'roll': 0.0, 'rlast': 0.0, 'hum': 0.0, 'sub': 0, 'fstep': 0, 'frames': 0,
            'tear': 0.0, 'wob': 0.0, 'arc': 0.0, 'arcy': 0.5}


def clock_step(st, P, now, fps):
    """One cook: advance st (plain floats) by the real time since the last cook (clamped 0..0.25 s) and return the
    CLOCK_ROWS x 4 rows. Rows (vec4 uK[i]):
      0 roll shift (picture heights incl. bar), roll bar, flicker multiplier, line-flicker depth
      1 flicker step, hum depth, hum position, t (s, accumulated while cooking)
      2 purity amplitude, swirl (rad), misconvergence (virtual px), seed hash (24 bit)
      3 Degauss shake amplitude, s since Degauss, press variation, Degauss level
      4..6 purity waves R, G, B; 7 phases0 xyz + field (0/1); 8 phases1 xyz + history reset (0/1)
      9 convergence directions (R edge, R offset, B edge, B offset)
      10 tear phase, frame counter (jitter step), wobble phase, arc flash level
      11 power: sy, sx, gain, dot
      12 arc row (0..1), crawl phase (lines), scan bar position (0..1), 0"""
    g = P.get
    raw = None if st['last'] < 0 else now - st['last']
    reset = raw is None or raw > GAP_RESET or raw < 0
    dt = 0.0 if raw is None else _f(raw, 0.0, GAP_RESET)
    st['last'] = now
    st['t'] += dt
    t = st['t']
    sd = int(g('Seed', 1))
    rnd = _f(float(g('Randomness', 0.0)), 0.0, 1.0)
    A = float(g('Amount', 1.0))
    # roll
    speed = float(g('Roll', 0.0)) * ROLL_MAX
    if speed != 0 and rnd > 0:
        speed *= 1.0 + 0.6 * rnd * seeded_noise(sd * 13 + 3, t * 0.7)
    st['roll'], st['rlast'] = roll_step(st['roll'], st['rlast'], dt, speed)
    bar = float(g('Rollbar', ROLL_BAR))
    # hum
    humbar = float(g('Humbar', 0.0))
    if humbar > 0:
        st['hum'] += dt * float(g('Humspeed', HUM_SPEED)) * (1.0 + 0.8 * rnd * seeded_noise(sd * 17 + 5, t * 0.3))
        st['hum'] -= math.floor(st['hum'])
    # flicker step (<= 24 Hz in frames)
    st['sub'] += 1
    if st['sub'] >= flicker_frames(fps):
        st['sub'] = 0
        st['fstep'] = (st['fstep'] + 1) & 0xffffff
    F = float(g('Flicker', 0.0))
    flick = 1.0 - F * FLICKER_DEPTH * flicker_level(st['fstep'], sd, rnd)
    # Degauss
    dtime = float(g('Degausstime', -1.0))
    since = now - dtime if dtime >= 0 else -1.0
    env = degauss_env(since)
    gd = env * float(g('Degaussamt', 1.0))
    press = rnd * h01(int(g('Degausscount', 0)) & M32, (sd * 31 + 9) & M32) if rnd > 0 else 0.0
    swirl_dir = -1.0 if press > 0.5 * rnd and rnd > 0 else 1.0
    blotch = 1.0 if 'Scanlines' in P else 0.0       # crt: Randomness also tints (JZB); crtfault: Degauss only
    purity = PURITY_RND * rnd * A * blotch + PURITY_DEGAUSS * gd
    swirl = swirl_dir * 3.0 * (1.0 - env) + 6.2831853 * press
    conv = CONV_RND * rnd * A * blotch
    seedhash = pcg((sd + 0x51) & M32) & 0xffffff
    waves, ph = purity_waves(sd)
    field = st['frames'] & 1
    st['frames'] = (st['frames'] + 1) & 0xffffff
    # crtfault motion
    st['tear'] += dt * float(g('Tearspeed', 0.5)) * (1.0 + 0.5 * rnd * seeded_noise(sd * 19 + 7, t * 0.5))
    st['tear'] -= math.floor(st['tear'])
    st['wob'] += dt * (0.7 + 0.5 * rnd * seeded_noise(sd * 23 + 11, t * 0.4))
    st['wob'] -= math.floor(st['wob'])
    st['arc'] *= ARC_DECAY
    if st['arc'] < 1e-3:
        st['arc'] = 0.0
    if h01(st['frames'], (sd * 41 + 13) & M32) < float(g('Arc', 0.0)) * ARC_RATE:
        st['arc'] = 1.0
        st['arcy'] = h01(st['frames'], (sd * 43 + 17) & M32)
    on = float(g('Power', 1.0)) > 0.5
    ptime = float(g('Powertime', -1.0))
    psince = now - ptime if ptime >= 0 else 1e9
    sy, sx, gain, dot = power_shape(on, psince, float(g('Powerdur', 0.6)))
    crawl = t * float(g('Crawl', 0.0))
    scanbar = t * float(g('Scanbarspeed', 1.0))
    rows = [
        [st['roll'] * (1.0 + bar), bar, flick, F * rnd * LINE_FLICKER],
        [float(st['fstep']), HUM_DEPTH * humbar, st['hum'], t],
        [purity, swirl, conv, float(seedhash)],
        [SHAKE * gd, min(max(since, 0.0), 1e4), press, gd],
        waves[0:4], waves[4:8], waves[8:12],
        [ph[0], ph[1], ph[2], float(field)],
        [ph[3], ph[4], ph[5], 1.0 if reset else 0.0],
        conv_dirs(sd),
        [st['tear'], float(st['frames']), st['wob'], st['arc']],
        [sy, sx, gain, dot],
        [st['arcy'], crawl - math.floor(crawl), scanbar - math.floor(scanbar), 0.0],
    ]
    assert len(rows) == CLOCK_ROWS
    return rows


# ---- crt defaults (= the crt module's PAGES defaults; a test keeps them equal) + the 'monitor' presets ----
CRT_DEFAULTS = {
    'Amount': 1.0, 'Curvature': 0.3, 'Scanlines': 0.6, 'Mask': 'aperture', 'Halation': 0.25,
    'Lines': 480, 'Sharpness': 0.5, 'Masksize': 6, 'Maskstrength': 0.5, 'Beammin': 0.15, 'Beamgrow': 0.2,
    'Interlace': 'off', 'Interdim': 0.5, 'Crawl': 0.0, 'Lineaxis': 'x',
    'Corner': 0.3, 'Vignette': 0.3, 'Brightness': 1.2, 'Border': 'black', 'Curveaxis': 'both', 'Overscan': 0.0,
    'Glass': 0.0, 'Damper': 0,
    'Phosphor': 'colour', 'Convx': 0.0, 'Convy': 0.0, 'Convedge': 0.0, 'Focus': 0.0, 'Persistr': 0.0,
    'Persistg': 0.0, 'Persistb': 0.0, 'Glowradius': 1.0, 'Scanbar': 0.0, 'Scanbarwidth': 0.15, 'Scanbarspeed': 1.0,
    'Roll': 0.0, 'Flicker': 0.0, 'Humbar': 0.0,
    'Randomness': 0.0,
}
# Seed, Monitor, Degauss and the State page are not part of a look.

# JZB_Lofi_CRT recipes (stagelab/presets/JZB_Lofi_CRT.yaml), exact values; the rest = JZB defaults (= ours).
JZB_RECIPES = [
    ('broadcast', 'Broadcast Monitor', {'Amount': 1, 'Curvature': 0.15, 'Scanlines': 0.5, 'Mask': 'aperture',
                                        'Halation': 0.2, 'Lines': 576, 'Maskstrength': 0.35, 'Corner': 0.15,
                                        'Vignette': 0.2, 'Brightness': 1.25}),
    ('arcade', 'Arcade', {'Amount': 1, 'Curvature': 0.4, 'Scanlines': 1, 'Mask': 'slot', 'Halation': 0.35,
                          'Lines': 240, 'Sharpness': 0.8, 'Maskstrength': 0.6, 'Corner': 0.4, 'Vignette': 0.4,
                          'Brightness': 1.4}),
    ('oldtv', 'Old Television', {'Amount': 1, 'Curvature': 0.6, 'Scanlines': 0.7, 'Mask': 'shadow', 'Halation': 0.4,
                                 'Lines': 288, 'Sharpness': 0.3, 'Masksize': 9, 'Corner': 0.6, 'Vignette': 0.6,
                                 'Brightness': 1.3, 'Humbar': 0.4, 'Randomness': 0.6}),
    ('lostsync', 'Lost Sync', {'Amount': 1, 'Curvature': 0.4, 'Scanlines': 0.7, 'Mask': 'aperture', 'Halation': 0.3,
                               'Roll': 0.4, 'Flicker': 0.3, 'Humbar': 0.6, 'Randomness': 0.5}),
    ('flatscan', 'Flat Scanlines', {'Amount': 1, 'Curvature': 0, 'Scanlines': 0.8, 'Mask': 'off', 'Halation': 0.15,
                                    'Lines': 240, 'Corner': 0, 'Vignette': 0, 'Brightness': 1.3}),
]

# The 'monitor' presets: named sets (AV-08), applied whole by the crt module's Monitor menu. Tuned by eye from the
# hardware descriptions (FX2 AV-01..08), not measured from real sets.
MONITORS = [
    ('pvm', 'Sony PVM (broadcast, sharp)', {'Curvature': 0.1, 'Curveaxis': 'x', 'Scanlines': 0.9, 'Mask': 'aperture',
                                           'Masksize': 6, 'Maskstrength': 0.45, 'Lines': 480, 'Sharpness': 0.85,
                                           'Beammin': 0.12, 'Halation': 0.15, 'Corner': 0.1, 'Vignette': 0.15,
                                           'Brightness': 1.35}),
    ('bvm', 'Sony BVM (studio reference)', {'Curvature': 0.0, 'Scanlines': 0.3, 'Mask': 'aperture', 'Masksize': 3,
                                            'Maskstrength': 0.3, 'Lines': 1080, 'Sharpness': 1.0, 'Halation': 0.05,
                                            'Corner': 0.05, 'Vignette': 0.05, 'Brightness': 1.15}),
    ('trinitron', 'Trinitron TV (damper wires)', {'Curvature': 0.25, 'Curveaxis': 'x', 'Mask': 'aperture',
                                                 'Damper': 2, 'Lines': 480, 'Scanlines': 0.6, 'Halation': 0.3,
                                                 'Corner': 0.25, 'Vignette': 0.25, 'Brightness': 1.25}),
    ('broadcast', 'Broadcast monitor (JZB)', dict(JZB_RECIPES[0][2])),
    ('arcade', 'Arcade 15 kHz (JZB)', dict(JZB_RECIPES[1][2])),
    ('oldtv', 'Old television (JZB)', dict(JZB_RECIPES[2][2])),
    ('c1084', 'Commodore 1084S', {'Curvature': 0.35, 'Mask': 'shadow', 'Masksize': 6, 'Maskstrength': 0.55,
                                  'Lines': 288, 'Scanlines': 0.75, 'Sharpness': 0.6, 'Halation': 0.3, 'Convx': 0.5,
                                  'Corner': 0.35, 'Vignette': 0.35, 'Brightness': 1.3}),
    ('greenterm', 'Green terminal (P1)', {'Phosphor': 'green', 'Mask': 'off', 'Lines': 240, 'Scanlines': 0.9,
                                          'Persistg': 0.85, 'Persistr': 0.85, 'Persistb': 0.85, 'Halation': 0.5,
                                          'Glowradius': 1.5, 'Curvature': 0.35, 'Corner': 0.4, 'Vignette': 0.4,
                                          'Brightness': 1.4}),
    ('amber', 'Amber monitor (P3)', {'Phosphor': 'amber', 'Mask': 'off', 'Lines': 350, 'Scanlines': 0.8,
                                     'Persistr': 0.7, 'Persistg': 0.7, 'Persistb': 0.7, 'Halation': 0.45,
                                     'Curvature': 0.3, 'Corner': 0.35, 'Brightness': 1.35}),
    ('portable', 'B/W portable TV', {'Phosphor': 'white', 'Mask': 'off', 'Lines': 240, 'Curvature': 0.7,
                                     'Corner': 0.7, 'Vignette': 0.7, 'Halation': 0.3, 'Sharpness': 0.2,
                                     'Brightness': 1.1, 'Flicker': 0.1, 'Randomness': 0.3, 'Focus': 0.4}),
    ('watchman', 'Pocket TV (Watchman-class)', {'Phosphor': 'white', 'Mask': 'off', 'Lines': 120, 'Curvature': 0.9,
                                                'Corner': 0.8, 'Vignette': 0.8, 'Brightness': 0.95, 'Focus': 0.6,
                                                'Overscan': 0.05, 'Glass': 0.5, 'Halation': 0.2}),
    ('ledwall', 'LED-wall safe (mask >= 9 px)', {'Curvature': 0.0, 'Corner': 0.0, 'Vignette': 0.0, 'Mask': 'slot',
                                                  'Masksize': 9, 'Maskstrength': 0.35, 'Lines': 240,
                                                  'Scanlines': 0.8, 'Halation': 0.2, 'Brightness': 1.3}),
    ('deadset', 'Dead set (heavy wear)', dict(JZB_RECIPES[2][2], Roll=0.3, Flicker=0.5, Humbar=0.7, Randomness=1.0,
                                              Convx=1.5, Focus=0.8)),
]


def monitor_names():
    return ['custom'] + [m[0] for m in MONITORS]


def monitor_labels():
    return ['Custom (keep)'] + [m[1] for m in MONITORS]


def monitor_values(name):
    """Full look for a monitor name (defaults + its overrides); {} for 'custom' / unknown."""
    for key, _label, over in MONITORS:
        if key == name:
            v = dict(CRT_DEFAULTS)
            v.update(over)
            return v
    return {}


# ---------------------------------------------------------------- numpy references (offline tests + LIVE CHECKS)
# Arrays are GL order: row 0 = bottom (y = 0), float, shape (H, W, 4), premultiplied RGBA.
def sample_bilinear(img, u, v):
    """GL texture() with linear filter + clamp-to-edge ('hold'): u, v arrays in 0..1 (texel centres at (i+.5)/n)."""
    import numpy as np
    h, w = img.shape[:2]
    x = np.clip(u * w - 0.5, 0.0, w - 1.0)
    y = np.clip(v * h - 0.5, 0.0, h - 1.0)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    x1 = np.minimum(x0 + 1, w - 1)
    y1 = np.minimum(y0 + 1, h - 1)
    fx = (x - x0)[..., None]
    fy = (y - y0)[..., None]
    a = img[y0, x0] * (1 - fx) + img[y0, x1] * fx
    b = img[y1, x0] * (1 - fx) + img[y1, x1] * fx
    return a * (1 - fy) + b * fy


def raster_ref(img, lines, axis=0):
    """Twin of the crt `raster` pass (no history): box average of each virtual pixel's output block."""
    import numpy as np
    H, W = img.shape[:2]
    p, vw, vh = raster_for(W, H, lines, axis)
    S = (H, W) if axis else (W, H)
    taps = raster_taps(p)
    px = S[0] / float(vw)
    i = np.arange(vw)[None, :] + 0.0
    j = np.arange(vh)[:, None] + 0.0
    p0x, p0y = i * px, j * p
    p1x, p1y = np.minimum((i + 1) * px, S[0]), np.minimum((j + 1) * p, S[1])
    acc = np.zeros((vh, vw, 4))
    for b in range(taps):
        for a in range(taps):
            qx = p0x + (p1x - p0x) * ((a + 0.5) / taps)
            qy = p0y + (p1y - p0y) * ((b + 0.5) / taps)
            u = np.clip(qx / S[0], 0, 1) + 0 * qy
            v = np.clip(qy / S[1], 0, 1) + 0 * qx
            acc += sample_bilinear(img, v, u) if axis else sample_bilinear(img, u, v)
    return acc / float(taps * taps)


def crt_ref(img, P, rows=None):
    """Twin of the crt `fx` composite for Halation 0, Glass 0, Randomness 0, no Degauss, Interlace off/alternate,
    no history (persistence 0). P = par dict (menus by name; missing = CRT_DEFAULTS). rows = clock rows (default: a
    first-cook clock for P)."""
    import numpy as np
    g = lambda k: P.get(k, CRT_DEFAULTS.get(k))
    H, W = img.shape[:2]
    ax = 1 if g('Lineaxis') == 'y' else 0
    if rows is None:
        rows = clock_step(clock_init(), dict(P), 0.0, 60.0)
    K = np.array(rows, dtype=np.float64)
    A = float(g('Amount'))
    if A <= 0:
        return img.copy()
    pitch, vw, vh = raster_for(W, H, g('Lines'), ax)
    ras = raster_ref(img, g('Lines'), ax)
    SW, SH = (H, W) if ax else (W, H)
    qy, qx = np.mgrid[0:SH, 0:SW].astype(np.float64)
    uvx, uvy = (qx + 0.5) / SW, (qy + 0.5) / SH
    aspect = SW / float(SH)
    cx, cy = uvx * 2 - 1, uvy * 2 - 1
    k = float(g('Curvature')) * WARP_MAX * A
    cax = ['both', 'x', 'y'].index(g('Curveaxis'))
    wx, wy = warp(cx, cy, k, aspect, cax)
    cr = float(g('Corner')) * CORNER_MAX * A
    qxx = np.abs(wx) * aspect - aspect + cr
    qyy = np.abs(wy) - 1.0 + cr
    d = np.sqrt(np.maximum(qxx, 0) ** 2 + np.maximum(qyy, 0) ** 2) + np.minimum(np.maximum(qxx, qyy), 0) - cr
    tube = np.clip(0.5 - d * SH * 0.5, 0, 1)
    ov = 1.0 + float(g('Overscan')) * A
    tx, ty = (wx / ov) * 0.5 + 0.5, (wy / ov) * 0.5 + 0.5

    def phys(img_, u, v):
        return sample_bilinear(img_, v, u) if ax else sample_bilinear(img_, u, v)

    col = phys(img, np.clip(tx, 0, 1), np.clip(ty, 0, 1)) if A < 1 else np.zeros((SH, SW, 4))
    cty = ty.copy()
    blank = np.zeros_like(ty, dtype=bool)
    rs, bar = K[0, 0], K[0, 1]
    if rs != 0:
        s = np.mod(cty - rs, 1.0 + bar)
        blank = s > 1.0
        cty = np.minimum(s, 1.0)
    r2 = (cx * cx + cy * cy) * 0.5
    foc = 1.0 + float(g('Focus')) * r2 * 2.0
    sharp = sharp_slope(g('Sharpness')) / foc
    scan = float(g('Scanlines'))
    bmin, bgrow = float(g('Beammin')), float(g('Beamgrow'))
    lineflick, fstep, seedh = K[0, 3], int(K[1, 0]), int(K[2, 3])
    imode = ['off', 'alternate', 'weave'].index(g('Interlace'))
    idim, field = float(g('Interdim')), int(K[7, 3])
    crawl = K[12, 1]

    def line_at(u, j):
        jj = np.clip(j, 0, vh - 1)
        uu = np.clip(u, 0.5 / vw, 1 - 0.5 / vw)
        c = sample_bilinear(ras, uu, (jj + 0.5) / vh)
        a = c[..., 3:4]
        rgb = np.where(a > 1e-5, np.clip(c[..., :3] / np.maximum(a, 1e-30), 0, 1), 0.0)
        lin = rgb * rgb
        ji = j.astype(np.int64) + 4096
        f = np.ones_like(j)
        if lineflick > 0:
            hv = np.vectorize(lambda x: h01(((x * 73856093) & M32) ^ fstep, (seedh + 5) & M32))(ji)
            f = f * (1 - lineflick * hv)
        if imode == 1:
            f = np.where((ji & 1) != field, f * (1 - idim), f)
        return lin * f[..., None], a

    def beam_at(ctx, cty_, du, dl):
        yl = cty_ * SH / pitch + dl + crawl
        j0 = np.floor(yl - 0.5)
        d0 = (yl - 0.5 - j0)[..., None]
        xv = ctx * vw - 0.5
        xi = np.floor(xv)
        xf = np.clip((xv - xi - 0.5) * sharp + 0.5, 0, 1)
        u = (xi + 0.5 + xf) / vw + du
        L0, a0 = line_at(u, j0)
        L1, a1 = line_at(u, j0 + 1)
        s0 = (bmin + bgrow * np.sqrt(L0)) * foc[..., None]
        s1 = (bmin + bgrow * np.sqrt(L1)) * foc[..., None]
        e0, e1 = d0 / s0, (1 - d0) / s1
        bm = L0 * np.exp(-0.5 * e0 * e0) + L1 * np.exp(-0.5 * e1 * e1)
        lin = (L0 * (1 - d0) + L1 * d0) * (1 - scan) + bm * scan
        return lin, a0 * (1 - d0) + a1 * d0

    lin, a = beam_at(tx, cty, 0.0, 0.0)
    conv = K[2, 2]
    cvx, cvy, cve = float(g('Convx')), float(g('Convy')), float(g('Convedge'))
    if conv > 0 or cvx != 0 or cvy != 0:
        cd = K[9]
        grow = 1.0 + cve * r2
        duR = conv * (cd[0] * wx + 0.5 * cd[1]) / vw + cvx * grow / SW
        duB = conv * (cd[2] * wx + 0.5 * cd[3]) / vw - cvx * grow / SW
        dl = cvy * grow / pitch
        lr, _ = beam_at(tx, cty, duR, dl)
        lb, _ = beam_at(tx, cty, duB, -dl)
        lin = np.concatenate([lr[..., 0:1], lin[..., 1:2], lb[..., 2:3]], axis=-1)
    ph = g('Phosphor')
    if ph != 'colour':
        tint = np.array(PHOSPHOR_TINT[ph]) ** 2
        lin = (lin @ np.array([0.2126, 0.7152, 0.0722]))[..., None] * tint
    mk = MASKS.index(g('Mask'))
    if mk > 0:
        dark, lit = mask_weights(g('Maskstrength'))
        ch = mask_channel_np(mk, int(g('Masksize')), qx.astype(np.int64), qy.astype(np.int64))
        w = np.full(lin.shape, dark)
        for c in range(3):
            w[..., c] = np.where(ch == c, lit, dark)
        lin = lin * w
    nd = int(g('Damper'))
    if nd > 0:
        for i in range(1, nd + 1):
            row = int(SH * i / float(nd + 1))
            lin[qy.astype(int) == row] *= 0.3
    kk = np.full(ty.shape, float(g('Brightness')) * K[0, 2])
    if K[1, 1] > 0:
        hb = (0.5 + 0.5 * np.cos(6.2831853 * (ty - K[1, 2]))) ** 4
        kk = kk * (1 - K[1, 1] * hb)
    vg = 0.5 * float(g('Vignette'))
    if vg > 0:
        tcx, tcy = np.clip(tx, 0, 1), np.clip(ty, 0, 1)
        kk = kk * np.clip(16 * tcx * (1 - tcx) * tcy * (1 - tcy), 1e-4, 1) ** vg
    sb = float(g('Scanbar'))
    if sb != 0:
        dd = np.mod(ty - (1.0 - K[12, 2]), 1.0)
        kk = kk * (1 + sb * (2 * np.exp(-dd / max(float(g('Scanbarwidth')), 1e-3)) - 1))
    Pm = lin * a * kk[..., None]
    aout = a[..., 0]
    rgb = np.sqrt(np.clip(Pm / np.maximum(aout, 1e-5)[..., None], 0, 1)) * aout[..., None]
    black = g('Border') == 'black'
    crt = np.concatenate([rgb, aout[..., None]], axis=-1)
    crt[blank] = [0, 0, 0, 1.0 if black else 0.0]
    col = col * (1 - A) + crt * A
    col = col * tube[..., None]
    if black:
        col[..., 3] += 1 - tube
    col = np.clip(col, 0, 1)
    col[..., :3] = np.minimum(col[..., :3], col[..., 3:4])
    if ax:
        col = np.transpose(col, (1, 0, 2))
    return col


def fault_ref(img, P, rows, lum=0.5):
    """Twin of the crtfault pass without Degauss shake / purity and arcs. P menus by name."""
    import numpy as np
    g = lambda k, d: P.get(k, d)
    K = np.array(rows, dtype=np.float64)
    H, W = img.shape[:2]
    A = float(g('Amount', 1.0))
    sy, sx, gain, dot = [float(x) for x in K[11]]
    if A <= 0 and K[3, 3] <= 0 and (sy, sx, gain, dot) == (1.0, 1.0, 1.0, 0.0):
        return img.copy()
    qy, qx = np.mgrid[0:H, 0:W].astype(np.float64)
    u, v = (qx + 0.5) / W, (qy + 0.5) / H
    cx, cy = u - 0.5, v - 0.5
    blank = ~((np.abs(cx) <= 0.5 * sx) & (np.abs(cy) <= 0.5 * sy) & (sx > 0) & (sy > 0))
    su = cx / max(sx, 1e-4) + 0.5
    sv = cy / max(sy, 1e-4) + 0.5
    br = 1.0 + float(g('Breathe', 0.0)) * 0.08 * (lum - 0.3) * A
    su, sv = (su - 0.5) / br + 0.5, (sv - 0.5) / br + 0.5
    rs = K[0, 0] * A
    if rs != 0:
        s = np.mod(sv - rs, 1.0 + K[0, 1])
        blank = blank | (s > 1.0)
        sv = np.minimum(s, 1.0)
    tear = float(g('Tear', 0.0)) * A
    if tear != 0:
        su = su + tear * 0.5 * np.mod(sv * float(g('Tearbands', 2.0)) + K[10, 0], 1.0)
    jit = float(g('Jitter', 0.0)) * A
    if jit != 0:
        row = np.floor(sv * H).astype(np.int64) + 8192
        fr, sh = int(K[10, 1]), int(K[2, 3])
        hv = np.vectorize(lambda x: h01(((x * 2654435761) & M32) ^ fr, (sh + 7) & M32))(row)
        su = su + (hv - 0.5) * 2.0 * jit * 8.0 / W
    bend = float(g('Bend', 0.0)) * A
    if bend != 0:
        su = su + bend * 0.05 * np.exp(-(1.0 - sv) * 10.0)
    wob = float(g('Wobble', 0.0)) * A
    if wob != 0:
        su = su + wob * 0.01 * np.sin(6.2831853 * (sv * float(g('Wobblefreq', 2.0)) + K[10, 2]))
    if tear != 0:
        xx = np.mod(su, 1.0 + float(g('Tearblank', 0.12)))
        blank = blank | (xx > 1.0)
        su = np.minimum(xx, 1.0)
    col = sample_bilinear(img, np.clip(su, 0, 1), np.clip(sv, 0, 1))
    kk = np.full(v.shape, gain)
    hd = K[1, 1] * A
    if hd > 0:
        e = 1.0 + 6.0 * float(g('Humsoft', 0.5))
        hb = (0.5 + 0.5 * np.cos(6.2831853 * float(g('Humcount', 1)) * (v - K[1, 2]))) ** e
        kk = kk * (1 - hd * hb)
    col[..., :3] *= kk[..., None]
    col[blank] = [0, 0, 0, 1.0 if g('Border', 'black') == 'black' else 0.0]
    if dot > 0:
        r = np.sqrt((cx * W / H) ** 2 + cy ** 2)
        dv = dot * np.exp(-(r / 0.012) ** 2)
        col[..., :3] = np.maximum(col[..., :3], dv[..., None])
        col[..., 3] = np.maximum(col[..., 3], dv)
    col = np.clip(col, 0, 1)
    col[..., :3] = np.minimum(col[..., :3], col[..., 3:4])
    return col


def compare(td_out, ref, tol=2.0 / 255.0):
    """LIVE CHECK helper: -> {max, mean, within} of |td - ref| over RGBA (within = share of values <= tol)."""
    import numpy as np
    d = np.abs(np.asarray(td_out, dtype=np.float64)[..., :4] - np.asarray(ref, dtype=np.float64)[..., :4])
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}


# ---------------------------------------------------------------- shared texts + TD helpers (crt, crtfault)
# Plain strings and two builder-side helpers. The helpers run only from the module builders (td_exec namespace has
# the TD op classes); importing this file as the `crt_logic` DAT module never calls them.
GLSL_LIB = """
uniform vec4 uK[%d];   // clock rows (crt_logic.clock_step)
uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h01(uint a, uint b) { return float(pcg(a + pcg(b)) >> 8) * (1.0 / 16777216.0); }
vec2 degaussShake(vec2 t) {
    vec4 s = uK[3];
    if (s.x <= 0.0) return t;
    return t + s.x * vec2(sin(6.2831853 * (t.y * 2.0 + s.y * 7.0 + s.z)),
                          0.6 * sin(6.2831853 * (t.x * 1.3 + s.y * 5.0 + s.z * 1.7)));
}
vec3 purity(vec2 t, float aspect) {             // colour-purity blotches (Randomness) / Degauss swirl, per gun
    float amp = uK[2].x;
    if (amp <= 0.0) return vec3(1.0);
    vec2 p = (t - 0.5) * vec2(aspect, 1.0);
    float cs = cos(uK[2].y), sn = sin(uK[2].y);
    p = mat2(cs, sn, -sn, cs) * p;
    vec3 n = 0.5 * vec3(sin(dot(p, uK[4].xy) + uK[7].x) + sin(dot(p, uK[4].zw) + uK[8].x),
                        sin(dot(p, uK[5].xy) + uK[7].y) + sin(dot(p, uK[5].zw) + uK[8].y),
                        sin(dot(p, uK[6].xy) + uK[7].z) + sin(dot(p, uK[6].zw) + uK[8].z));
    return max(vec3(1.0) + amp * n, vec3(0.0));
}
""" % CLOCK_ROWS

CLOCK_STATE = {}                                     # per clock op path: {clk, rows, frame} (runtime only)
CLOCK_CB = """# clock: per-frame motion state of this FX_analog crt / crtfault instance (roll lock-in, flicker steps, hum,
# Degauss, power, tear, arcs) -> CLOCK_ROWS samples x (x y z w) = the shaders' uniform array uK. Maths: crt_logic
# (builders/fx_analog_crt_logic.py). State = plain floats in storage (T-67). Cooks once per frame while pulled (Frame).
def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    c = scriptOp.parent()
    L = c.op('crt_logic').module
    f = absTime.frame
    S = L.CLOCK_STATE.setdefault(scriptOp.path, {})   # module memory, not op storage: storing into the op's
    rows = S.get('rows')                              # own storage while it cooks = a cook dependency loop (live)
    if rows is None or S.get('frame') != f:
        st = S.get('clk')
        if not isinstance(st, dict):
            st = L.clock_init()
        P = {}
        for n in L.CLOCK_PARS:
            p = getattr(c.par, n, None)
            if p is not None:
                P[n] = float(p.menuIndex) if p.isMenu else float(p.eval())
        rows = L.clock_step(st, P, absTime.seconds, project.cookRate)
        S['clk'], S['rows'], S['frame'] = st, rows, f
    scriptOp.clear()
    scriptOp.isTimeSlice = False
    scriptOp.numSamples = len(rows)
    ch = [scriptOp.appendChan(n) for n in ('x', 'y', 'z', 'w')]
    for i, r in enumerate(rows):
        for k in range(4):
            ch[k][i] = float(r[k])
    return
"""

PULSE_EXEC = """# pulse_exec: Degauss pulse -> Degausstime / Degausscount (the clock turns them into the envelope); Power toggle ->
# Powertime; Monitor menu -> the whole monitor set (crt_logic.monitor_values). No per-frame Python here.
def onPulse(par):
    o = par.owner
    if par.name == 'Degauss':
        o.par.Degausstime.val = absTime.seconds
        o.par.Degausscount.val = int(o.par.Degausscount.eval()) + 1
    return

def onValueChange(par, prev):
    o = par.owner
    if par.name == 'Power' and getattr(o.par, 'Powertime', None) is not None:
        o.par.Powertime.val = absTime.seconds
    elif par.name == 'Monitor':
        for k, v in o.op('crt_logic').module.monitor_values(par.eval()).items():
            q = getattr(o.par, k, None)
            if q is not None:
                q.val = v
    return
"""


def td_common(m, H, logic_file, dat_name, pulses, changes):
    """Builder side (TD): logic DAT `crt_logic`, Script CHOP `clock` (+ docked callbacks, Frame par), Parameter
    Execute `pulse_exec` for the pulse / value-change pars named."""
    mk, expr = H['mk'], H['expr']
    lg = mk(m, textDAT, dat_name)
    with open(logic_file) as fh:
        txt = fh.read()
    if lg.text != txt:
        lg.text = txt
    lg.comment = 'builders/fx_analog_crt_logic.py (pure maths; clock + pulse_exec use it as a module).'
    s = mk(m, scriptCHOP, 'clock')
    cb = m.op('clock_callbacks')
    if cb is None:
        cb = mk(m, textDAT, 'clock_callbacks')
        cb.dock = s
    if cb.text != CLOCK_CB:
        cb.text = CLOCK_CB
    s.par.callbacks = 'clock_callbacks'
    if getattr(s.par, 'Frame', None) is None:
        pg = next((p for p in s.customPages if p.name == 'Clock'), None) or s.appendCustomPage('Clock')
        pg.appendFloat('Frame', label='Frame (clock)')
    expr(s.par.Frame, 'absTime.frame')
    s.comment = 'Per-frame motion state -> uK rows (crt_logic.clock_step); cooks once per frame while pulled.'
    pe = mk(m, parameterexecuteDAT, 'pulse_exec')
    if pe.text != PULSE_EXEC:
        pe.text = PULSE_EXEC
        pe.par.active = False                              # T-97: toggle after a text rewrite
    pe.par.op = '..'
    pe.par.pars = ' '.join(list(pulses) + list(changes))
    pe.par.valuechange = bool(changes)
    pe.par.onpulse = bool(pulses)
    pe.par.active = True
    pe.comment = 'Pulses %s, changes %s -> State pars / monitor sets.' % (' '.join(pulses), ' '.join(changes))
    return s


def td_clock_uniform(g):
    """Builder side (TD): the clock CHOP into GLSL TOP g as uniform array uK (vec4 per sample, particles pattern)."""
    g.seq.array.numBlocks = max(int(g.seq.array.numBlocks), 1)
    g.par.array0name = 'uK'
    g.par.array0type = 'vec4'
    g.par.array0chop = 'clock'
    g.par.array0arraytype = 'uniformarray'


SAVE_SNIPPET = """# allow-readback
# td_exec: save one crt / crtfault instance's input, output, pars and clock rows for check_dir
import json, os, numpy as np
m = op(%r)
d = %r
os.makedirs(d, exist_ok=True)
np.save(os.path.join(d, 'src.npy'), m.op('in1').numpyArray(delayed=False))
np.save(os.path.join(d, 'out.npy'), m.op('out1').numpyArray(delayed=False))
P = dict((p.name, p.eval()) for p in m.customPars if p.style not in ('Pulse', 'Header') and p.page.name != 'Zkit')
lum = float(m.op('avg').numpyArray(delayed=False)[0, 0, 0]) if m.op('avg') is not None else 0.5
json.dump({'module': %r, 'P': P, 'rows': [[float(k[i]) for k in m.op('clock').chans()] for i in range(m.op('clock').numSamples)],
           'lum': lum},
          open(os.path.join(d, 'meta.json'), 'w'))
"""


def save_snippet(comp_path, out_dir, module):
    """The td_exec code that saves a check set (pass it with '# allow-readback' or frames >= 2, T-74)."""
    return SAVE_SNIPPET % (comp_path, out_dir, module)


def check_dir(d, flip=False):
    """Offline half of a LIVE CHECK: compare the saved TD output with crt_ref / fault_ref (TD stays responsive)."""
    import json
    import os
    import numpy as np
    meta = json.load(open(os.path.join(d, 'meta.json')))
    src = np.load(os.path.join(d, 'src.npy')).astype(np.float64)
    out = np.load(os.path.join(d, 'out.npy')).astype(np.float64)
    if flip:
        src, out = src[::-1], out[::-1]
    if meta['module'] == 'crtfault':
        ref = fault_ref(src, meta['P'], meta['rows'], meta.get('lum', 0.5))
    else:
        ref = crt_ref(src, meta['P'], meta['rows'])
    return compare(out, ref)


if __name__ == '__main__':
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == 'check':
        print(check_dir(sys.argv[2], flip='--flip' in sys.argv))
    else:
        print('usage: python3 -I builders/fx_analog_crt_logic.py check <dir> [--flip]')
