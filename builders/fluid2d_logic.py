"""fluid2d_logic: pure logic + a numpy reference of the BN_fluid2d solver (no td import; tests: test/test_fluid2d.py).

Spec: docs/research/BN_fluid_cloth_sims.md section 5 (clean-room; maths after Stam 1999 / Harris GPU Gems 38 /
Dobryakov, touchFluid read for the obstacle handling). Copied into the COMP's `fluid2d_logic` Text DAT; the Script
CHOPs call engine_step() once per frame. The reference solver (pass_* / step) uses the SAME formulas and the SAME
edge rules as builders/glsl/fluid2d_*.glsl, so a live TOP download can be compared with it (docs/builds/fluid2d.md P4).
numpy is imported lazily (only the reference needs it; the TD runtime part is plain Python, T-48).
No limits (user rule): pars are open, no flash / luminance guard. ASCII only.

Grid (MAC layout stored in one texture, arrays here are [y, x], row 0 = bottom like TD's numpyArray, T-58):
  texel (i, j) centre = (i + 0.5, j + 0.5) in cell units.
  .x = x-face velocity at (i + 1, j + 0.5)  (between cell i and i+1)
  .y = y-face velocity at (i + 0.5, j + 1)  (between cell j and j+1)
  velocity unit = sim cells per second; emitter / force velocities are given in screen heights per second
  (x Simh = cells/s; cells are square because Simw = Simh * Resw / Resh).
  divergence(i,j) = ux(i) - ux(i-1) + uy(j) - uy(j-1);  gradient: ux -= p(i+1) - p(i)   -> exactly consistent with
  the 5-point Jacobi below (a projected field's divergence goes to 0 as K grows; no checkerboard leak).
  Pressure: weighted Jacobi p' = (1-w) pc + w (sum pn - div) * 0.25, Neumann at solids (pn = pc), Relax = w.
Edges (Edge menu): wall = outside is solid (velocity 0), wrap = periodic, open = outside is fluid at p = 0.
"""
import math
import random

NEMIT = 8                 # emitter rows (3 vec4 texels each in uEmit)
EMIT_TEXELS = 3
WG = 8                    # compute workgroup 8x8
INV_BETA = 0.25
VORT_EPS = 1e-5
M_CLAMP, M_WRAP, M_CONST = 0, 1, 2
EDGES = ['wall', 'wrap', 'open']
DTMODES = ['auto', 'fixed']
AUDIOMODES = ['off', 'levelstir', 'kickburst']
BPMMODES = ['off', 'internal', 'external']
BPMDIVS = ['b4th', 'b2nd', 'b1', 'b2', 'b4', 'b8']
BPMDIV_BEATS = {'b4th': 0.25, 'b2nd': 0.5, 'b1': 1.0, 'b2': 2.0, 'b4': 4.0, 'b8': 8.0}
PATTERNS = ['ring', 'sweep', 'random', 'points']
COLORMODES = ['rgb', 'density', 'speed']
DYEBLENDS = ['add', 'over']
ALPHAMODES = ['opaque', 'density']
TESTMODES = ['off', 'zero', 'fixed']
# Quality (perf pass, 26 Oct): dye grid scale vs Resw x Resh. out1 (fx_look) always renders at Resw x Resh and
# samples the dye bilinearly, so lower quality = softer dye edges, same output size. Sim grid is Simh either way.
QUALITIES = ['high', 'balanced', 'fast']
DYE_SCALE = {'high': 1.0, 'balanced': 0.75, 'fast': 0.5}
SLEEP_DYE_PEAK = 16.0     # assumed worst dye peak (additive splats) for the sleep timer
SLEEP_FLOOR = 1.0 / 1024  # visible threshold after exposure
FIXED_STEPS = (0, 10, 20)  # Testmode fixed: one deterministic splat on each of these steps after Reset
FIXED_COLOURS = ((1.0, 0.35, 0.1), (0.2, 0.55, 1.0), (0.9, 0.2, 0.8))
DEFAULT_PALETTE = ((0.05, 0.05, 0.25), (0.35, 0.1, 0.65), (0.95, 0.2, 0.55), (1.0, 0.6, 0.15), (1.0, 1.0, 0.9))
EPS_T = 1e-9

# Custom parameters: (page, [(Name, style, default, opts)]). Names: one capital then lowercase/digits.
# Float ranges are slider ranges only (never clamps). Ints that size textures or count passes keep min 1.
PAGES = [
    ('Sim', [
        ('Simh', 'Int', 342, {'min': 16, 'max': 1024, 'clampmin': 1, 'label': 'Sim cells (height)'}),
        ('Resw', 'Int', 1080, {'min': 64, 'max': 3840, 'clampmin': 1, 'label': 'Dye width'}),
        ('Resh', 'Int', 1920, {'min': 64, 'max': 3840, 'clampmin': 1, 'label': 'Dye height'}),
        ('Quality', 'Menu', 'balanced', {'names': QUALITIES, 'labels': ['High (dye full res)', 'Balanced (dye 3/4)',
                                                                         'Fast (dye 1/2)'], 'label': 'Quality'}),
        ('Idlesleep', 'Toggle', True, {'label': 'Sleep when idle'}),
        ('Iterations', 'Int', 8, {'min': 1, 'max': 80, 'clampmin': 1, 'label': 'Pressure iterations (rebuild)'}),
        ('Relax', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Jacobi weight'}),
        ('Dtmode', 'Menu', 'auto', {'names': DTMODES, 'labels': ['Auto (1/cookRate)', 'Fixed (Dt)'], 'label': 'Time step'}),
        ('Dt', 'Float', 1.0 / 60.0, {'min': 0, 'max': 0.1, 'label': 'Dt s'}),
        ('Timescale', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Time scale'}),
        ('Veldiss', 'Float', 0.2, {'min': 0, 'max': 5, 'label': 'Velocity decay /s'}),
        ('Dyediss', 'Float', 1.0, {'min': 0, 'max': 5, 'label': 'Dye decay /s'}),
        ('Curl', 'Float', 30.0, {'min': 0, 'max': 100, 'label': 'Vorticity'}),
        ('Edge', 'Menu', 'wall', {'names': EDGES, 'labels': ['Wall', 'Wrap', 'Open'], 'label': 'Edges'}),
        ('Warmstart', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Pressure carry-over'}),
    ]),
    ('Input', [
        ('Srcgain', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Source gain (in1)'}),
        ('Maskthresh', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Mask threshold (in2)'}),
        ('Forcegain', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Force gain (in3)'}),
        ('Emitradius', 'Float', 0.03, {'min': 0.001, 'max': 0.3, 'label': 'Emitter radius'}),
        ('Emitforce', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Emitter force'}),
        ('Emitcolor', 'RGB', (1.0, 0.4, 0.1), {'label': 'Emitter colour'}),
    ]),
    ('Audio', [
        ('Audiomode', 'Menu', 'off', {'names': AUDIOMODES, 'labels': ['Off', 'Level stir', 'Kick burst'], 'label': 'Audio'}),
        ('Audiogain', 'Float', 4.0, {'min': 0, 'max': 20, 'label': 'Audio gain'}),
        ('Lowhz', 'Float', 150.0, {'min': 20, 'max': 1000, 'label': 'Low band Hz'}),
        ('Burstthresh', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Kick threshold'}),
        ('Burstrefractory', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Kick refractory s'}),
        ('Bpmmode', 'Menu', 'off', {'names': BPMMODES, 'labels': ['Off', 'Internal', 'External CHOP'], 'label': 'BPM'}),
        ('Bpm', 'Float', 120.0, {'min': 20, 'max': 300, 'label': 'BPM'}),
        ('Bpmdiv', 'Menu', 'b1', {'names': BPMDIVS, 'labels': ['1/4 beat', '1/2 beat', '1 beat', '2 beats', '1 bar', '2 bars'],
                                  'label': 'Burst every'}),
        ('Bpmpattern', 'Menu', 'ring', {'names': PATTERNS, 'labels': ['Ring', 'Sweep', 'Random', 'Points (in4)'],
                                         'label': 'Burst pattern'}),
        ('Beatchop', 'CHOP', '', {'label': 'Beat CHOP (external)'}),
        ('Burst', 'Pulse', None, {'label': 'Burst'}),
        ('Burstforce', 'Float', 1.0, {'min': 0, 'max': 5, 'label': 'Burst force'}),
        ('Burstring', 'Float', 0.12, {'min': 0, 'max': 0.5, 'label': 'Burst ring radius'}),
        ('Burstradius', 'Float', 0.04, {'min': 0.001, 'max': 0.3, 'label': 'Burst splat radius'}),
    ]),
    ('Look', [
        ('Colormode', 'Menu', 'rgb', {'names': COLORMODES, 'labels': ['Dye RGB', 'Palette by density', 'Palette by speed'],
                                      'label': 'Colour'}),
        ('Exposure', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Exposure (stops)'}),
        ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 3, 'label': 'Gamma'}),
        ('Speedref', 'Float', 300.0, {'min': 1, 'max': 2000, 'label': 'Speed for top colour (cells/s)'}),
        ('Dyeblend', 'Menu', 'add', {'names': DYEBLENDS, 'labels': ['Add', 'Over'], 'label': 'Dye blend'}),
        ('Alpha', 'Menu', 'opaque', {'names': ALPHAMODES, 'labels': ['Opaque over Bg', 'Density alpha'], 'label': 'Alpha'}),
        ('Premult', 'Toggle', True, {'label': 'Premultiplied'}),
        ('Bg', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background'}),
        ('Pal1', 'RGB', DEFAULT_PALETTE[0], {'label': 'Palette 1 (low)'}),
        ('Pal2', 'RGB', DEFAULT_PALETTE[1], {'label': 'Palette 2'}),
        ('Pal3', 'RGB', DEFAULT_PALETTE[2], {'label': 'Palette 3'}),
        ('Pal4', 'RGB', DEFAULT_PALETTE[3], {'label': 'Palette 4'}),
        ('Pal5', 'RGB', DEFAULT_PALETTE[4], {'label': 'Palette 5 (high)'}),
    ]),
    ('Control', [
        ('Reset', 'Pulse', None, {'label': 'Reset'}),
        ('Pause', 'Toggle', False, {'label': 'Pause'}),
        ('Step', 'Pulse', None, {'label': 'Step (while paused)'}),
        ('Stopat', 'Int', 0, {'min': 0, 'max': 600, 'clampmin': 0, 'label': 'Pause at step (0 = off)'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 100, 'label': 'Seed'}),
        ('Testmode', 'Menu', 'off', {'names': TESTMODES, 'labels': ['Off', 'Zero force', 'Fixed splats'], 'label': 'Test mode'}),
    ]),
]
PANEL_PAGES = [pg for pg, _ in PAGES]

# GLSL passes (compute, one file each under builders/glsl/, prefixed by fluid2d_common.glsl).
# inputs = wired op names in input order (max 3 per GLSL TOP); vecs / arrays = uniform names the shader declares.
# res: 'sim', 'dye' (Resw x Resh x Quality scale) or 'out' (Resw x Resh). 'press' is instanced K times (chain) or once with npasses.
PASSES = [
    ('pre', {'inputs': ['vel_fb', 'force_prep', 'mask_prep'], 'vecs': ['uSim', 'uStep', 'uForce'], 'arrays': ['uEmit'],
             'res': 'sim', 'fmt': 'rgba32float'}),
    ('vort', {'inputs': ['fx_pre'], 'vecs': ['uStep', 'uForce'], 'arrays': [], 'res': 'sim', 'fmt': 'rgba32float'}),
    ('div', {'inputs': ['fx_vort'], 'vecs': ['uStep'], 'arrays': [], 'res': 'sim', 'fmt': 'rgba32float'}),
    ('press', {'inputs': ['<prev>', 'fx_div'], 'vecs': ['uStep', 'uPress'], 'arrays': [], 'res': 'sim', 'fmt': 'rgba32float'}),
    ('grad', {'inputs': ['<press>', 'fx_vort'], 'vecs': ['uStep'], 'arrays': [], 'res': 'sim', 'fmt': 'rgba32float'}),
    ('advvel', {'inputs': ['fx_grad'], 'vecs': ['uStep', 'uForce'], 'arrays': [], 'res': 'sim', 'fmt': 'rgba32float'}),
    ('advdye', {'inputs': ['dye_fb', 'fx_grad', 'src_prep'], 'vecs': ['uSim', 'uStep', 'uDye'], 'arrays': ['uEmit'],
                'res': 'dye', 'fmt': 'rgba16float'}),
    ('look', {'inputs': ['fx_advdye', 'fx_grad'], 'vecs': ['uLook', 'uLook2', 'uBg', 'uPal0', 'uPal1', 'uPal2', 'uPal3', 'uPal4'],
              'arrays': [], 'res': 'out', 'fmt': 'rgba16float'}),
    ('stat', {'inputs': ['fx_grad'], 'vecs': ['uStep'], 'arrays': [], 'res': 'sim', 'fmt': 'rgba32float'}),
]
STAT_CHANS = ['maxvel', 'meanvel', 'divmax', 'dyesum', 'cookms', 'steps', 'beat', 'audiolevel']
ENGINE_CHANS = ['dt', 'run', 'steps', 'beat', 'kick', 'audiolevel', 'low', 'srcon', 'forceon', 'nemit', 'bursts', 'awake']


def dye_size(resw, resh, quality):
    """Dye grid (w, h) for Quality: Resw x Resh times DYE_SCALE (unknown quality = high)."""
    k = DYE_SCALE.get(str(quality), 1.0)
    return max(1, int(round(float(resw) * k))), max(1, int(round(float(resh) * k)))


def sleep_after(dyediss, exposure=0.0):
    """Seconds after the last injection until the dye is invisible: peak * exp(-dyediss t) * 2^exposure < floor.
    None = never (no decay)."""
    d = float(dyediss)
    if d <= 1e-6:
        return None
    gain = SLEEP_DYE_PEAK * (2.0 ** max(float(exposure), 0.0)) / SLEEP_FLOOR
    return max(2.0, math.log(gain) / d)


def menu_index(names, val):
    try:
        return names.index(val)
    except ValueError:
        return 0


def sim_size(resw, resh, simh):
    """Velocity grid (w, h): h = Simh, w follows the dye aspect so cells stay square."""
    h = max(1, int(round(float(simh))))
    w = max(1, int(round(h * float(resw) / max(float(resh), 1.0))))
    return w, h


def frame_dt(dtmode, dt, timescale, cookrate):
    """Step length s: auto = Timescale / cookRate (frame based: deterministic, a late frame does not jump), fixed = Dt * Timescale."""
    if dtmode == 'fixed':
        return float(dt) * float(timescale)
    return float(timescale) / max(float(cookrate), 1e-6)


# ---------------------------------------------------------------- control sources (pure Python, runs in TD)
def bpm_period(bpm, beats):
    return 60.0 / float(bpm) * float(beats) if bpm > 0 and beats > 0 else 0.0


def bpm_ticks(t0, t1, bpm, beats, origin=0.0):
    """Tick times in (t0, t1] on the grid origin + k * period (absolute, so no drift however long it runs)."""
    P = bpm_period(bpm, beats)
    if P <= 0 or t1 <= t0:
        return []
    k0 = int(math.floor((t0 - origin) / P + EPS_T))
    k1 = int(math.floor((t1 - origin) / P + EPS_T))
    return [origin + k * P for k in range(k0 + 1, k1 + 1)]


def block_rms(blocks):
    """RMS over every sample of every channel (lists of floats). Empty = 0."""
    n = 0
    s = 0.0
    for b in blocks or ():
        for v in b:
            s += float(v) * float(v)
            n += 1
    return math.sqrt(s / n) if n else 0.0


def kick_step(st, t, level, thresh, refractory):
    """Rising edge of level through thresh, not within refractory s of the last kick. st = {'prev', 'last'}."""
    st = dict(st) if st else {'prev': 0.0, 'last': None}
    fire = st['prev'] < thresh <= level and (st['last'] is None or t - st['last'] >= refractory - EPS_T)
    if fire:
        st['last'] = t
    st['prev'] = level
    return st, fire


def row(x, y, vx, vy, radius, dye, force, col):
    """One emitter: pos uv (0..1, y up), velocity screen heights/s, radius screen heights, amounts, rgb."""
    return (float(x), float(y), float(vx), float(vy), float(radius), float(dye), float(force), 1.0,
            float(col[0]), float(col[1]), float(col[2]), 0.0)


def pack_rows(rows):
    """8 emitters -> 24 texels x 4 channels (x y z w lists) for the uEmit texture buffer; unused rows are 0."""
    rows = list(rows)[:NEMIT]
    flat = []
    for k in range(NEMIT):
        flat.extend(rows[k] if k < len(rows) else (0.0,) * 12)
    return [flat[c::4] for c in range(4)]


def unpack_rows(chans):
    """Inverse of pack_rows: list of 12-tuples for the active rows."""
    x, y, z, w = chans
    out = []
    for k in range(len(x) // EMIT_TEXELS):
        t = []
        for j in range(EMIT_TEXELS):
            i = k * EMIT_TEXELS + j
            t.extend((x[i], y[i], z[i], w[i]))
        if t[7] > 0.5:
            out.append(tuple(t))
    return out


def ring_burst(n_burst, p):
    a = p['aspect']
    rows = []
    for k in range(NEMIT):
        ang = 2.0 * math.pi * k / NEMIT + 0.3 * n_burst
        c, s = math.cos(ang), math.sin(ang)
        rows.append(row(0.5 + p['burstring'] * c / a, 0.5 + p['burstring'] * s, c * p['burstforce'], s * p['burstforce'],
                        p['burstradius'], 1.0, 1.0, p['palette'][k % len(p['palette'])]))
    return rows


def sweep_burst(n_burst, p):
    return [row((k + 0.5) / NEMIT, 0.12, 0.0, p['burstforce'], p['burstradius'], 1.0, 1.0,
                p['palette'][(k + n_burst) % len(p['palette'])]) for k in range(NEMIT)]


def random_burst(n_burst, p):
    r = random.Random(int(p['seed']) * 7919 + n_burst)
    rows = []
    for _ in range(3):
        ang = r.uniform(0.0, 2.0 * math.pi)
        rows.append(row(r.uniform(0.2, 0.8), r.uniform(0.2, 0.8), math.cos(ang) * p['burstforce'],
                        math.sin(ang) * p['burstforce'], p['burstradius'], 1.0, 1.0,
                        p['palette'][r.randrange(len(p['palette']))]))
    return rows


def points_burst(n_burst, p, points):
    rows = []
    for k, q in enumerate(points[:NEMIT]):
        vx, vy = q.get('vx', 0.0), q.get('vy', 0.0)
        n = math.hypot(vx, vy)
        if n < 1e-9:
            ang = 2.0 * math.pi * k / max(len(points), 1)
            vx, vy, n = math.cos(ang), math.sin(ang), 1.0
        rows.append(row(q['x'], q['y'], vx / n * p['burstforce'], vy / n * p['burstforce'], p['burstradius'], 1.0, 1.0,
                        p['palette'][k % len(p['palette'])]))
    return rows


def points_from_chans(chans, p):
    """in4 CHOP -> emitter dicts. chans = {name: [sample values]}; one sample per emitter; x y needed."""
    if 'x' not in chans or 'y' not in chans:
        return []
    n = min(len(chans['x']), len(chans['y']), NEMIT)
    pts = []
    for i in range(n):
        g = lambda k, d: float(chans[k][i]) if k in chans and i < len(chans[k]) else d
        pts.append({'x': g('x', 0.5), 'y': g('y', 0.5), 'vx': g('vx', 0.0), 'vy': g('vy', 0.0),
                    'radius': g('radius', p['emitradius']), 'strength': g('strength', 1.0),
                    'col': (g('r', p['emitcolor'][0]), g('g', p['emitcolor'][1]), g('b', p['emitcolor'][2]))})
    return pts


def point_rows(points, p):
    return [row(q['x'], q['y'], q['vx'], q['vy'], q['radius'], q['strength'], q['strength'] * p['emitforce'], q['col'])
            for q in points if q['radius'] > 0]


def stir_row(t, level, low, p):
    """Audio level stir: one emitter on a slow Lissajous, strength = level, colour from the low/level ratio."""
    w1, w2 = 2.0 * math.pi * 0.13, 2.0 * math.pi * 0.21
    x, y = 0.5 + 0.3 * math.sin(w1 * t), 0.5 + 0.35 * math.sin(w2 * t + 1.0)
    dx, dy = 0.3 * w1 * math.cos(w1 * t), 0.35 * w2 * math.cos(w2 * t + 1.0)
    n = math.hypot(dx, dy) or 1.0
    col = palette_at(p['palette'], low / (level + 1e-6) if level > 0 else 0.0)
    return row(x, y, dx / n * level, dy / n * level, p['emitradius'], level, level * p['emitforce'], col)


def fixed_splats(seed, step_index):
    """Testmode fixed: deterministic splats on FIXED_STEPS (independent of the panel, for live/numpy parity)."""
    if step_index not in FIXED_STEPS:
        return []
    k = FIXED_STEPS.index(step_index)
    r = random.Random(int(seed) * 1000 + step_index)
    ang = r.uniform(0.0, 2.0 * math.pi)
    return [row(r.uniform(0.3, 0.7), r.uniform(0.3, 0.7), 0.5 * math.cos(ang), 0.5 * math.sin(ang), 0.06, 1.0, 1.0,
                FIXED_COLOURS[k])]


def palette_at(pal, t):
    """Piecewise-linear ramp over the palette colours (t 0..1, clamped like the shader)."""
    t = min(max(float(t), 0.0), 1.0) * (len(pal) - 1)
    k = min(int(math.floor(t)), len(pal) - 2)
    f = t - k
    a, b = pal[k], pal[k + 1]
    return tuple(a[i] * (1.0 - f) + b[i] * f for i in range(3))


ENGINE_DEFAULTS = {
    'dtmode': 'auto', 'dt': 1.0 / 60.0, 'timescale': 1.0, 'cookrate': 60.0, 'pause': False, 'stopat': 0,
    'testmode': 'off', 'seed': 1, 'audiomode': 'off', 'audiogain': 4.0, 'burstthresh': 0.3, 'burstrefractory': 0.15,
    'burstforce': 1.0, 'burstring': 0.12, 'burstradius': 0.04, 'bpmmode': 'off', 'bpm': 120.0, 'bpmdiv': 'b1',
    'bpmpattern': 'ring', 'emitradius': 0.03, 'emitforce': 1.0, 'emitcolor': (1.0, 0.4, 0.1),
    'palette': DEFAULT_PALETTE, 'aspect': 1080.0 / 1920.0, 'idlesleep': False, 'dyediss': 1.0, 'exposure': 0.0,
}


def engine_params(get, cookrate):
    """Build the engine params from a par getter get(Name) -> evaluated value (TD: lambda n: getattr(P.par, n).eval())."""
    p = dict(ENGINE_DEFAULTS)
    for k in ('dtmode', 'dt', 'timescale', 'pause', 'stopat', 'testmode', 'seed', 'audiomode', 'audiogain',
              'burstthresh', 'burstrefractory', 'burstforce', 'burstring', 'burstradius', 'bpmmode', 'bpm', 'bpmdiv',
              'bpmpattern', 'emitradius', 'emitforce', 'idlesleep', 'dyediss', 'exposure'):
        p[k] = get(k.capitalize())
    p['cookrate'] = cookrate
    p['emitcolor'] = (get('Emitcolorr'), get('Emitcolorg'), get('Emitcolorb'))
    p['palette'] = tuple((get('Pal%dr' % i), get('Pal%dg' % i), get('Pal%db' % i)) for i in range(1, 6))
    p['aspect'] = float(get('Resw')) / max(float(get('Resh')), 1.0)
    return p


IDLE_NOTE = ('idle: nothing drives it - wire in1 (dye) or in3 (force), Effectors on, Audio or BPM Internal '
             '(a dropped copy starts here)')


def idle_note(p, inp, effon=False):
    """Status text while NOTHING can inject dye or force (drop-in, 28 Oct: a dropped copy shows black and says why),
    else ''. Effectors drive the field on the GPU (eff_force / eff_dye), so Effon counts as a driver."""
    inp = inp or {}
    driven = (inp.get('srcwired') or inp.get('forcewired') or inp.get('points') or effon
              or p.get('audiomode', 'off') != 'off' or p.get('bpmmode', 'off') != 'off'
              or p.get('testmode', 'off') != 'off')
    return '' if driven else IDLE_NOTE


def new_engine(t=0.0):
    return {'t': None, 'origin': float(t), 'steps': 0, 'kick': None, 'beatprev': 0, 'bursts': 0, 'lastact': float(t)}


def engine_step(st, t, p, inp=None, events=()):
    """Once per frame. inp = {'points': [dicts], 'level': rms, 'low': rms, 'extbeat': 0/1}; events: 'reset' 'burst'
    'step'. Returns (st, out, rows): out has ENGINE_CHANS, rows = emitter rows for this frame (<= 8)."""
    inp = inp or {}
    ev = list(events or ())
    q = dict(ENGINE_DEFAULTS)
    q.update(p or {})
    p = q
    t = float(t)
    if st is None or 'reset' in ev:
        st = new_engine(t)
    st = dict(st)
    t_prev = st['t'] if st['t'] is not None else t
    st['t'] = t
    stopped = int(p['stopat']) > 0 and st['steps'] >= int(p['stopat'])
    run = (not p['pause'] and not stopped) or 'step' in ev
    dt = frame_dt(p['dtmode'], p['dt'], p['timescale'], p['cookrate']) if run else 0.0
    level = block_rms([inp.get('level_block', [])]) if 'level_block' in inp else float(inp.get('level', 0.0))
    low = block_rms([inp.get('low_block', [])]) if 'low_block' in inp else float(inp.get('low', 0.0))
    level *= float(p['audiogain'])
    low *= float(p['audiogain'])
    beat = False
    if p['bpmmode'] == 'internal':
        beat = len(bpm_ticks(t_prev, t, p['bpm'], BPMDIV_BEATS.get(p['bpmdiv'], 1.0), st['origin'])) > 0
    elif p['bpmmode'] == 'external':
        b = 1 if inp.get('extbeat', 0) else 0
        beat = bool(b and not st['beatprev'])
        st['beatprev'] = b
    kick = False
    if p['audiomode'] == 'kickburst':
        st['kick'], kick = kick_step(st['kick'], t, low, float(p['burstthresh']), float(p['burstrefractory']))
    points = list(inp.get('points') or [])
    rows = []
    burst = 'burst' in ev or beat or kick
    srcon = forceon = 1.0
    if p['testmode'] == 'zero':
        srcon = forceon = 0.0
    elif p['testmode'] == 'fixed':
        srcon = forceon = 0.0
        if run:
            rows = fixed_splats(p['seed'], st['steps'])
    elif run:
        if burst:
            pat = p['bpmpattern']
            if pat == 'sweep':
                rows += sweep_burst(st['bursts'], p)
            elif pat == 'random':
                rows += random_burst(st['bursts'], p)
            elif pat == 'points' and points:
                rows += points_burst(st['bursts'], p, points)
            else:
                rows += ring_burst(st['bursts'], p)
            st['bursts'] += 1
        rows += point_rows(points, p)
        if p['audiomode'] == 'levelstir' and level > 0:
            rows.append(stir_row(t, level, low, p))
    rows = rows[:NEMIT]
    if run:
        st['steps'] += 1
    # Idle sleep: awake while anything injects (emitter rows, wired in1 / in3), while paused / stopped / testing
    # (the frozen frame must stay on screen), and until the last injection's dye has decayed below visibility.
    active = (bool(rows) or not run or p['testmode'] != 'off' or 'reset' in ev
              or (inp.get('srcwired') and srcon) or (inp.get('forcewired') and forceon))
    if active or 'lastact' not in st:
        st['lastact'] = t
    awake = True
    if p['idlesleep']:
        lim = sleep_after(p['dyediss'], p['exposure'])
        awake = lim is None or (t - st['lastact']) < lim
    out = {'dt': dt, 'run': 1.0 if run else 0.0, 'steps': float(st['steps']), 'beat': 1.0 if beat else 0.0,
           'kick': 1.0 if kick else 0.0, 'audiolevel': level, 'low': low, 'srcon': srcon, 'forceon': forceon,
           'nemit': float(len(rows)), 'bursts': float(st['bursts']), 'awake': 1.0 if awake else 0.0}
    return st, out, rows


# ---------------------------------------------------------------- numpy reference solver (same maths as the GLSL)
def _np():
    import numpy as np
    return np


def vel_mode(e):
    return M_WRAP if e == 1 else (M_CLAMP if e == 2 else M_CONST)


def solid_mode(e):
    return M_WRAP if e == 1 else M_CONST


def solid_const(e):
    return 1.0 if e == 0 else 0.0


def pres_mode(e):
    return M_WRAP if e == 1 else (M_CONST if e == 2 else M_CLAMP)


dye_mode = pres_mode


def fetch(a, X, Y, mode, c=0.0):
    """a[Y, X] with the shader's resolveT edge rule (clamp / wrap / constant c outside)."""
    np = _np()
    H, W = a.shape
    if mode == M_WRAP:
        return a[Y % H, X % W]
    v = a[np.clip(Y, 0, H - 1), np.clip(X, 0, W - 1)]
    if mode == M_CONST:
        inside = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
        v = np.where(inside, v, c)
    return v


def bilerp(a, qx, qy, mode, c=0.0):
    """Bilinear at continuous texel index (qx, qy) (texel k sits at k); mix order of the shader."""
    np = _np()
    x0 = np.floor(qx)
    y0 = np.floor(qy)
    fx = qx - x0
    fy = qy - y0
    xi = x0.astype(int)
    yi = y0.astype(int)
    a00 = fetch(a, xi, yi, mode, c)
    a10 = fetch(a, xi + 1, yi, mode, c)
    a01 = fetch(a, xi, yi + 1, mode, c)
    a11 = fetch(a, xi + 1, yi + 1, mode, c)
    lo = a00 * (1.0 - fx) + a10 * fx
    hi = a01 * (1.0 - fx) + a11 * fx
    return lo * (1.0 - fy) + hi * fy


def grid(w, h):
    np = _np()
    X, Y = np.meshgrid(np.arange(w), np.arange(h))
    return X, Y


def splat(uvx, uvy, cx, cy, r, aspect):
    """Gaussian exp(-|dp|^2 / r^2), dp aspect-corrected (screen heights). Integral = pi r^2 (screen heights^2)."""
    np = _np()
    dx = (uvx - cx) * aspect
    dy = uvy - cy
    return np.exp(-(dx * dx + dy * dy) / (r * r))


def solid_from_mask(mask, thresh):
    np = _np()
    return (np.asarray(mask, dtype=float) > thresh).astype(float)


REF_DEFAULTS = {'dt': 1.0 / 60.0, 'edge': 0, 'aspect': 1080.0 / 1920.0, 'curl': 30.0, 'forcegain': 1.0,
                'maskthresh': 0.5, 'veldiss': 0.2, 'iterations': 20, 'omega': 0.8, 'warm': 0.8, 'dyediss': 1.0,
                'srcgain': 1.0, 'blend': 0, 'srcon': 1.0, 'forceon': 1.0}


def _active(rows):
    return [r for r in rows if r[7] > 0.5 and r[4] > 0.0]


def pass_pre(ux, uy, mask, force, rows, p):
    """fx_pre: curl of the incoming velocity, emitter impulses + external force on the faces, solids from the mask.
    Returns (ux, uy, solid, curl)."""
    np = _np()
    H, W = ux.shape
    X, Y = grid(W, H)
    e = p['edge']
    vm = vel_mode(e)
    V = lambda a, dx, dy: fetch(a, X + dx, Y + dy, vm, 0.0)
    eY = 0.5 * (V(uy, 1, -1) + V(uy, 1, 0))
    wY = 0.5 * (V(uy, -1, -1) + V(uy, -1, 0))
    nX = 0.5 * (V(ux, -1, 1) + V(ux, 0, 1))
    sX = 0.5 * (V(ux, -1, -1) + V(ux, 0, -1))
    w = 0.5 * ((eY - wY) - (nX - sX))
    dt = p['dt']
    nx = ux.copy()
    ny = uy.copy()
    if force is not None:
        g = p['forcegain'] * p['forceon'] * H * dt
        nx = nx + force[..., 0] * g
        ny = ny + force[..., 1] * g
    fxu, fxv = (X + 1.0) / W, (Y + 0.5) / H
    fyu, fyv = (X + 0.5) / W, (Y + 1.0) / H
    for r in _active(rows):
        nx = nx + r[2] * r[6] * H * splat(fxu, fxv, r[0], r[1], r[4], p['aspect'])
        ny = ny + r[3] * r[6] * H * splat(fyu, fyv, r[0], r[1], r[4], p['aspect'])
    sol = solid_from_mask(mask, p['maskthresh']) if mask is not None else np.zeros((H, W))
    S = lambda dx, dy: fetch(sol, X + dx, Y + dy, solid_mode(e), solid_const(e))
    nx = np.where((sol > 0.5) | (S(1, 0) > 0.5), 0.0, nx)
    ny = np.where((sol > 0.5) | (S(0, 1) > 0.5), 0.0, ny)
    return nx, ny, sol, w


def pass_vort(ux, uy, sol, w, p):
    """fx_vort: vorticity confinement f = Curl * w * (N.y, -N.x), N = normalised grad |w|, averaged onto the faces."""
    np = _np()
    H, W = ux.shape
    X, Y = grid(W, H)
    e = p['edge']
    vm = vel_mode(e)
    Aw = lambda dx, dy: fetch(w, X + dx, Y + dy, vm, 0.0)

    def vforce(dx, dy):
        w0 = Aw(dx, dy)
        nxg = 0.5 * (np.abs(Aw(dx + 1, dy)) - np.abs(Aw(dx - 1, dy)))
        nyg = 0.5 * (np.abs(Aw(dx, dy + 1)) - np.abs(Aw(dx, dy - 1)))
        ln = np.sqrt(nxg * nxg + nyg * nyg) + VORT_EPS
        return p['curl'] * w0 * nyg / ln, -p['curl'] * w0 * nxg / ln

    f0x, f0y = vforce(0, 0)
    fex, _ = vforce(1, 0)
    _, fny = vforce(0, 1)
    dt = p['dt']
    nx = ux + dt * 0.5 * (f0x + fex)
    ny = uy + dt * 0.5 * (f0y + fny)
    S = lambda dx, dy: fetch(sol, X + dx, Y + dy, solid_mode(e), solid_const(e))
    nx = np.where((sol > 0.5) | (S(1, 0) > 0.5), 0.0, nx)
    ny = np.where((sol > 0.5) | (S(0, 1) > 0.5), 0.0, ny)
    return nx, ny


def pass_div(ux, uy, sol, p):
    np = _np()
    H, W = ux.shape
    X, Y = grid(W, H)
    vm = vel_mode(p['edge'])
    d = ux - fetch(ux, X - 1, Y, vm, 0.0) + uy - fetch(uy, X, Y - 1, vm, 0.0)
    return np.where(sol > 0.5, 0.0, d)


def pass_press(pin, div, sol, p, scale=1.0):
    """One weighted-Jacobi iteration (Neumann at solids, Dirichlet 0 outside in open mode)."""
    np = _np()
    H, W = pin.shape
    X, Y = grid(W, H)
    e = p['edge']
    om = p['omega']
    pc = scale * pin
    acc = 0.0
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sn = fetch(sol, X + dx, Y + dy, solid_mode(e), solid_const(e))
        pn = scale * fetch(pin, X + dx, Y + dy, pres_mode(e), 0.0)
        acc = acc + np.where(sn > 0.5, pc, pn)
    new = (1.0 - om) * pc + om * (acc - div) * INV_BETA
    return np.where(sol > 0.5, 0.0, new)


def pass_grad(pr, ux, uy, sol, p):
    np = _np()
    H, W = ux.shape
    X, Y = grid(W, H)
    e = p['edge']
    pm = pres_mode(e)
    nx = ux - (fetch(pr, X + 1, Y, pm, 0.0) - pr)
    ny = uy - (fetch(pr, X, Y + 1, pm, 0.0) - pr)
    S = lambda dx, dy: fetch(sol, X + dx, Y + dy, solid_mode(e), solid_const(e))
    nx = np.where((sol > 0.5) | (S(1, 0) > 0.5), 0.0, nx)
    ny = np.where((sol > 0.5) | (S(0, 1) > 0.5), 0.0, ny)
    return nx, ny


def sample_x(ux, px, py, vm):
    return bilerp(ux, px - 1.0, py - 0.5, vm, 0.0)


def sample_y(uy, px, py, vm):
    return bilerp(uy, px - 0.5, py - 1.0, vm, 0.0)


def pass_advvel(ux, uy, sol, p):
    """Semi-Lagrangian self-advection of each face component from its own face position, * exp(-Veldiss dt)."""
    np = _np()
    H, W = ux.shape
    X, Y = grid(W, H)
    e = p['edge']
    vm = vel_mode(e)
    dt = p['dt']
    dec = math.exp(-p['veldiss'] * dt)
    Fx, Fy = X + 1.0, Y + 0.5
    vx, vy = ux, sample_y(uy, Fx, Fy, vm)
    nx = sample_x(ux, Fx - dt * vx, Fy - dt * vy, vm) * dec
    Gx, Gy = X + 0.5, Y + 1.0
    vx, vy = sample_x(ux, Gx, Gy, vm), uy
    ny = sample_y(uy, Gx - dt * vx, Gy - dt * vy, vm) * dec
    S = lambda dx, dy: fetch(sol, X + dx, Y + dy, solid_mode(e), solid_const(e))
    nx = np.where((sol > 0.5) | (S(1, 0) > 0.5), 0.0, nx)
    ny = np.where((sol > 0.5) | (S(0, 1) > 0.5), 0.0, ny)
    return nx, ny


def pass_advdye(dye, ux, uy, sol, src, rows, p):
    """Dye (Hd, Wd, 3) advected by the projected sim-res velocity, decayed, + source + emitter splats; 0 in solids."""
    np = _np()
    Hd, Wd = dye.shape[:2]
    H, W = ux.shape
    Xd, Yd = grid(Wd, Hd)
    e = p['edge']
    vm = vel_mode(e)
    dt = p['dt']
    u = (Xd + 0.5) / Wd
    v = (Yd + 0.5) / Hd
    psx, psy = u * W, v * H
    vx = sample_x(ux, psx, psy, vm)
    vy = sample_y(uy, psx, psy, vm)
    bx = (u - dt * vx / W) * Wd - 0.5
    by = (v - dt * vy / H) * Hd - 0.5
    dec = math.exp(-p['dyediss'] * dt)
    out = np.empty_like(dye)
    for ch in range(3):
        out[..., ch] = bilerp(dye[..., ch], bx, by, dye_mode(e), 0.0) * dec
    if src is not None:
        k = p['srcgain'] * p['srcon'] * dt
        for ch in range(3):
            out[..., ch] += src[..., ch] * src[..., 3] * k
    for r in _active(rows):
        g = r[5] * splat(u, v, r[0], r[1], r[4], p['aspect'])
        for ch in range(3):
            if p['blend'] == 0:
                out[..., ch] += r[8 + ch] * g
            else:
                a = np.clip(g, 0.0, 1.0)
                out[..., ch] = out[..., ch] * (1.0 - a) + r[8 + ch] * a
    cx = np.clip(np.floor(psx).astype(int), 0, W - 1)
    cy = np.clip(np.floor(psy).astype(int), 0, H - 1)
    solid = sol[cy, cx] > 0.5
    out[solid] = 0.0
    return out


def cell_velocity(ux, uy, X, Y, vm):
    return 0.5 * (fetch(ux, X - 1, Y, vm, 0.0) + fetch(ux, X, Y, vm, 0.0)), \
        0.5 * (fetch(uy, X, Y - 1, vm, 0.0) + fetch(uy, X, Y, vm, 0.0))


def pass_stat(ux, uy, sol, p):
    """fx_stat: (|cell velocity|, |div|) per cell."""
    np = _np()
    H, W = ux.shape
    X, Y = grid(W, H)
    vm = vel_mode(p['edge'])
    cx, cy = cell_velocity(ux, uy, X, Y, vm)
    return np.sqrt(cx * cx + cy * cy), np.abs(pass_div(ux, uy, sol, p))


def pass_look(dye, ux, uy, p, look):
    """fx_look reference. look = {mode, exposure, gamma, speedref, alpha, premult, bg, palette}. Returns (Hd, Wd, 4)."""
    np = _np()
    Hd, Wd = dye.shape[:2]
    H, W = ux.shape
    Xd, Yd = grid(Wd, Hd)
    dens = dye.max(axis=2)
    a = np.clip(dens, 0.0, 1.0)
    mode = look.get('mode', 0)
    pal = look.get('palette', DEFAULT_PALETTE)

    def ramp(t):
        t = np.clip(t, 0.0, 1.0) * 4.0
        k = np.minimum(np.floor(t), 3).astype(int)
        f = t - k
        P = np.asarray(pal, dtype=float)
        return P[k] * (1.0 - f[..., None]) + P[k + 1] * f[..., None]

    if mode == 0:
        col = dye.copy()
    elif mode == 1:
        col = ramp(a) * a[..., None]
    else:
        cs_x = np.clip(np.floor((Xd + 0.5) / Wd * W).astype(int), 0, W - 1)
        cs_y = np.clip(np.floor((Yd + 0.5) / Hd * H).astype(int), 0, H - 1)
        vx, vy = cell_velocity(ux, uy, cs_x, cs_y, M_CONST)   # the look shader has no Edge: outside = 0
        col = ramp(np.sqrt(vx * vx + vy * vy) / max(look.get('speedref', 300.0), 1e-6)) * a[..., None]
    col = col * (2.0 ** look.get('exposure', 0.0))
    col = np.power(np.maximum(col, 0.0), 1.0 / max(look.get('gamma', 1.0), 1e-4))
    out = np.empty((Hd, Wd, 4))
    if look.get('alpha', 0) == 0:
        bg = np.asarray(look.get('bg', (0.0, 0.0, 0.0)), dtype=float)
        out[..., :3] = col + bg * (1.0 - a[..., None])
        out[..., 3] = 1.0
    else:
        if look.get('premult', True):
            out[..., :3] = col
        else:
            out[..., :3] = np.where(a[..., None] > 0.0, col / np.maximum(a[..., None], 1e-30), 0.0)
        out[..., 3] = a
    return out


def new_sim(simw, simh, resw, resh):
    np = _np()
    z = np.zeros((simh, simw))
    return {'ux': z.copy(), 'uy': z.copy(), 'p': z.copy(), 'dye': np.zeros((resh, resw, 3)), 'vel': None}


def step(state, p=None, rows=(), mask=None, force=None, src=None, run=True):
    """One frame of the whole COMP (fx_pre .. fx_advdye). state from new_sim(); returns a new state whose 'vel' =
    (ux, uy, solid) after projection (what out2 / fx_stat / fx_look see)."""
    q = dict(REF_DEFAULTS)
    q.update(p or {})
    p = q
    if not run:
        s = dict(state)
        return s
    A = pass_pre(state['ux'], state['uy'], mask, force, rows, p)
    bx, by = pass_vort(A[0], A[1], A[2], A[3], p)
    d = pass_div(bx, by, A[2], p)
    pr = state['p']
    for k in range(int(p['iterations'])):
        pr = pass_press(pr, d, A[2], p, p['warm'] if k == 0 else 1.0)
    gx, gy = pass_grad(pr, bx, by, A[2], p)
    nx, ny = pass_advvel(gx, gy, A[2], p)
    dye = pass_advdye(state['dye'], gx, gy, A[2], src, rows, p)
    return {'ux': nx, 'uy': ny, 'p': pr, 'dye': dye, 'vel': (gx, gy, A[2])}


def stats(state, p=None):
    """The numbers out3 reports: maxvel, meanvel, divmax (of the projected field), dyesum (sum of r+g+b)."""
    q = dict(REF_DEFAULTS)
    q.update(p or {})
    if state.get('vel') is None:
        return {'maxvel': 0.0, 'meanvel': 0.0, 'divmax': 0.0, 'dyesum': float(state['dye'].sum())}
    gx, gy, sol = state['vel']
    sp, dv = pass_stat(gx, gy, sol, q)
    return {'maxvel': float(sp.max()), 'meanvel': float(sp.mean()), 'divmax': float(dv.max()),
            'dyesum': float(state['dye'].sum())}


def rel_l2(a, b):
    """Relative L2 error |a - b| / |b| (for the live parity check P4)."""
    np = _np()
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    n = float(np.sqrt((b * b).sum()))
    return float(np.sqrt(((a - b) ** 2).sum())) / (n if n > 0 else 1.0)


def run_fixed(steps=60, simh=64, resw=128, resh=128, seed=1, p=None):
    """Reference for live check P4: Testmode fixed, Reset, `steps` steps at Dt 1/60. Returns the final state."""
    simw, simh = sim_size(resw, resh, simh)
    q = dict(REF_DEFAULTS)
    q.update({'aspect': float(resw) / resh, 'srcon': 0.0, 'forceon': 0.0})
    q.update(p or {})
    st = new_sim(simw, simh, resw, resh)
    for k in range(steps):
        st = step(st, q, fixed_splats(seed, k))
    return st
