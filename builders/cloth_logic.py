"""cloth_logic: pure logic for BN_cloth (cloth + soft-body COMP). No td import; tested by test/test_cloth.py.

Spec: docs/research/BN_fluid_cloth_sims.md section 6 (our clean-room design), with one change found offline here:
the solver is XPBD "small steps" (Macklin et al. 2019: many substeps, ONE constraint iteration each) instead of
"2 substeps x K Jacobi iterations". Same dispatch count, 4-6x less stretch (docs/builds/cloth.md, numbers from this
file's reference solver). Every substep is ONE fused compute pass (predict + gather-Jacobi + tethers + collide +
velocity) on a 2W x H rgba32f state texture (positions left half, velocities right half), so it needs no second
output and no write conflicts (T-46/T-47: compute GLSL only).

This module holds everything that is not GPU work:
  * the uniform-row contract shared with the shaders (ROWS, glsl_header(), STENCIL),
  * rest shape, pins, rest lengths, tethers (long-range attachments, Kim et al. 2012),
  * the per-frame engine (wind / BPM / audio / burst / reset / pause / release / camera) -> uniform rows,
  * rotation extraction for jelly mode (pure Python, Mueller et al. 2016 iteration; robust for flat sheets),
  * a numpy reference solver `frame_ref` with the same maths as builders/glsl/cloth_substep.glsl.
No limits: every range is open (the operator decides). ASCII only. Copied into the COMP's `cloth_logic` Text DAT;
numpy is imported only inside the reference functions (the engine runs without it, T-48).

Texture layout: one texel per cloth vertex, i = column (0..W-1), j = row (0..H-1); TD textures start bottom-left, so
row H-1 is the TOP edge of the cloth. numpy arrays here are (H, W, ...) indexed [j, i].
"""
import math

# ------------------------------------------------------------------ menus
MODES = ['cloth', 'jelly']
ORIENTS = ['vertical', 'horizontal']
PINMODES = ['none', 'top', 'topcorners', 'corners', 'mask']       # index = shader pin mode
PIN_LABELS = ['None', 'Top edge', 'Top corners', '4 corners', 'Mask (in2)']
WINDMODES = ['off', 'constant', 'noise', 'audio', 'bpm']
CAMS = ['front', 'orbit', 'top', 'side']
SHADINGS = ['flat', 'phong', 'sheen']
TEXTURES = ['checker', 'in1', 'none']
TESTMODES = ['off', 'rest', 'fixed']
BPMDIVS = ['q4', 'q2', 'b1', 'b2', 'b4']
BPMDIV_LABELS = ['1/4 beat', '1/2 beat', '1 beat', '2 beats', '1 bar']
BPMDIV_BEATS = {'q4': 0.25, 'q2': 0.5, 'b1': 1.0, 'b2': 2.0, 'b4': 4.0}

SMAX = 32          # substep passes the builder unrolls (Substeps picks how many cook; rebuild with smax=N for more)
TIME_WRAP = 1000.0  # time fed to shader noise is wrapped (F22: big floats lose precision)
NSPHERES = 4

# ------------------------------------------------------------------ uniform rows (vec4 array `uP`, one CHOP sample each)
ROWS = [
    ('R_STEP', 'dt_sub, dt_sub^2, velocity keep factor exp(-Damping*dt_sub), run (0 = paused)'),
    ('R_GRAV', 'gravity xyz (m/s^2), reset (1 on the reset frame)'),
    ('R_WIND', 'wind acceleration xyz (m/s^2), aero (0 = plain push, 1 = normal pressure only)'),
    ('R_TURB', 'turbulence amount, spatial frequency (1/m), time (wrapped), seed'),
    ('R_GRID', 'W, H, dx, dy (rest spacing, m)'),
    ('R_COMP', 'alpha~ stretch, shear, bend (compliance / dt_sub^2), relax'),
    ('R_MASS', 'released (0/1), inverse mass per vertex, jelly shape stiffness, mode (0 cloth, 1 jelly)'),
    ('R_FLOOR', 'on, y, friction, thickness'),
    ('R_SPH0', 'sphere 0: centre xyz, radius (<= 0 = off)'),
    ('R_SPH1', 'sphere 1'),
    ('R_SPH2', 'sphere 2'),
    ('R_SPH3', 'sphere 3'),
    ('R_ROT0', 'jelly rotation row 0 xyz, valid (0/1)'),
    ('R_ROT1', 'jelly rotation row 1 xyz, 0'),
    ('R_ROT2', 'jelly rotation row 2 xyz, 0'),
    ('R_CENT', 'jelly current centroid xyz, 0'),
    ('R_REST', 'rest centroid xyz, substeps S'),
    ('R_TETH', 'tethers on (0/1), slack (1 = rest length), pin mode index, 0'),
]
ROW = {n: k for k, (n, _) in enumerate(ROWS)}
NROWS = len(ROWS)

# 12-neighbour stencil: (di, dj, type) type 0 structural, 1 shear, 2 bend
STENCIL = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0),
           (1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1),
           (2, 0, 2), (-2, 0, 2), (0, 2, 2), (0, -2, 2)]
STRUCTURAL = [s for s in STENCIL if s[2] == 0]

DEFAULTS = {
    'gridw': 128, 'gridh': 128, 'mode': 'cloth', 'substeps': 16, 'dt': 0.0, 'timescale': 1.0,
    'gravityx': 0.0, 'gravityy': -9.8, 'gravityz': 0.0, 'damping': 1.0, 'stretch': 0.0, 'shear': 0.0001,
    'bend': 0.05, 'relax': 1.5, 'shape': 0.1, 'mass': 1.0, 'sizew': 1.0, 'sizeh': 1.0, 'orient': 'vertical',
    'top': 1.0, 'pins': 'top', 'tethers': True, 'tetherslack': 1.0, 'floor': False, 'floory': -0.8,
    'windmode': 'noise', 'windx': 0.0, 'windy': 0.0, 'windz': 3.0, 'windgain': 1.0, 'aero': 0.7,
    'turbulence': 0.5, 'gust': 0.5, 'turbscale': 2.0, 'bpm': 120.0, 'bpmdiv': 'b1', 'burstforce': 25.0,
    'burstdecay': 0.3, 'audiogain': 1.0, 'burstthresh': 0.5, 'burstrefractory': 0.25,
    'friction': 0.3, 'thickness': 0.01,
    'sphere1on': False, 'sphere1x': 0.0, 'sphere1y': 0.3, 'sphere1z': 0.0, 'sphere1r': 0.3,
    'sphere2on': False, 'sphere2x': 0.0, 'sphere2y': 0.0, 'sphere2z': 0.0, 'sphere2r': 0.2,
    'sphere3on': False, 'sphere3x': 0.0, 'sphere3y': 0.0, 'sphere3z': 0.0, 'sphere3r': 0.2,
    'sphere4on': False, 'sphere4x': 0.0, 'sphere4y': 0.0, 'sphere4z': 0.0, 'sphere4r': 0.2,
    'cam': 'front', 'camdist': 2.6, 'camelev': 10.0, 'orbitspeed': 12.0, 'fov': 40.0,
    'pause': False, 'testmode': 'off', 'seed': 1,
}


def _g(p, k):
    return p[k] if k in p else DEFAULTS[k]


def menu_index(names, v):
    try:
        return names.index(v)
    except ValueError:
        return 0


# ------------------------------------------------------------------ shader contract
def glsl_header():
    """Text prepended to every cloth shader: row indices, row count, stencil, pin modes. Generated so Python and
    GLSL never disagree (test_cloth ShaderContract)."""
    out = ['// generated by cloth_logic.glsl_header(): uniform rows + stencil (do not edit in TD)']
    out.append('#define NROWS %d' % NROWS)
    for n, k in ROW.items():
        out.append('#define %s %d' % (n, k))
    out.append('#define NSPHERES %d' % NSPHERES)
    for k, n in enumerate(PINMODES):
        out.append('#define PIN_%s %d' % (n.upper(), k))
    out.append('#define NSTENCIL %d' % len(STENCIL))
    out.append('const ivec3 STENCIL[%d] = ivec3[](%s);' % (
        len(STENCIL), ', '.join('ivec3(%d, %d, %d)' % s for s in STENCIL)))
    return '\n'.join(out) + '\n'


def rest_length(di, dj, dx, dy):
    return math.sqrt((di * dx) ** 2 + (dj * dy) ** 2)


def spacing(W, H, sizew, sizeh):
    return (sizew / max(W - 1, 1), sizeh / max(H - 1, 1))


# ------------------------------------------------------------------ rest shape, pins, tethers
def rest_point(i, j, W, H, sizew, sizeh, orient='vertical', top=1.0):
    """Rest position of vertex (i, j). Vertical: XY plane, row H-1 at y = top. Horizontal: XZ plane at y = top,
    row H-1 at the back (-z)."""
    u = i / max(W - 1, 1)
    v = j / max(H - 1, 1)
    x = (u - 0.5) * sizew
    if orient == 'horizontal':
        return (x, top, (0.5 - v) * sizeh)
    return (x, top - (1.0 - v) * sizeh, 0.0)


def rest_centroid(sizew, sizeh, orient='vertical', top=1.0):
    if orient == 'horizontal':
        return (0.0, top, 0.0)
    return (0.0, top - 0.5 * sizeh, 0.0)


def pinned(i, j, W, H, pinmode, mask_value=0.0):
    """True when vertex (i, j) is pinned by the Pins menu (mask_value = in2 luma at the vertex for 'mask')."""
    if pinmode == 'top':
        return j == H - 1
    if pinmode == 'topcorners':
        return j == H - 1 and i in (0, W - 1)
    if pinmode == 'corners':
        return j in (0, H - 1) and i in (0, W - 1)
    if pinmode == 'mask':
        return mask_value > 0.5
    return False


def tether_anchors(i, j, W, H, pinmode):
    """Pinned vertices (i, j) is tethered to, in the order the shader applies them. Mask pins have none (would need
    a nearest-pin search)."""
    if pinmode == 'top':
        return [(i, H - 1)]
    if pinmode == 'topcorners':
        return [(0, H - 1), (W - 1, H - 1)]
    if pinmode == 'corners':
        return [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]
    return []


def rest_arrays(W, H, sizew, sizeh, orient='vertical', top=1.0, pinmode='top', mask=None):
    """numpy (H, W, 3) rest positions and (H, W) pin flags (1.0 pinned), as cloth_rest.glsl writes them."""
    import numpy as np
    jj, ii = np.mgrid[0:H, 0:W]
    u = ii / max(W - 1, 1)
    v = jj / max(H - 1, 1)
    R = np.zeros((H, W, 3))
    R[..., 0] = (u - 0.5) * sizew
    if orient == 'horizontal':
        R[..., 1] = top
        R[..., 2] = (0.5 - v) * sizeh
    else:
        R[..., 1] = top - (1.0 - v) * sizeh
    pin = np.zeros((H, W))
    for j in range(H):
        for i in range(W):
            mv = 0.0 if mask is None else float(mask[j, i])
            if pinned(i, j, W, H, pinmode, mv):
                pin[j, i] = 1.0
    return R, pin


# ------------------------------------------------------------------ tempo, noise, bursts
def bpm_ticks(t0, t1, bpm, div_beats=1.0):
    """Tick times in (t0, t1] for a clock at `bpm`, one tick per `div_beats` beats, ticks at k * period."""
    if bpm <= 0 or div_beats <= 0 or t1 <= t0:
        return []
    per = 60.0 / bpm * div_beats
    eps = 1e-9 * max(1.0, abs(t1))
    k0 = int(math.floor((t0 + eps) / per)) + 1
    k1 = int(math.floor((t1 + eps) / per))
    return [k * per for k in range(k0, k1 + 1)]


def _hash(n, seed=0):
    """Integer hash -> [0, 1). Deterministic, platform independent."""
    x = (int(n) * 374761393 + int(seed) * 668265263) & 0xFFFFFFFF
    x = ((x ^ (x >> 13)) * 1274126177) & 0xFFFFFFFF
    x = x ^ (x >> 16)
    return (x & 0xFFFFFF) / float(0x1000000)


def vnoise(x, seed=0):
    """Smooth 1D value noise in [0, 1)."""
    i = math.floor(x)
    f = x - i
    a, b = _hash(i, seed), _hash(i + 1, seed)
    s = f * f * (3.0 - 2.0 * f)
    return a + (b - a) * s


def burst_env(t, t_burst, decay):
    """Burst envelope: 1 at the burst, exp decay with time constant `decay` s (decay <= 0: one frame)."""
    if t_burst is None or t < t_burst:
        return 0.0
    if decay <= 0:
        return 1.0 if t - t_burst < 1e-9 else 0.0
    return math.exp(-(t - t_burst) / decay)


def _norm3(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-12 else (0.0, 0.0, 1.0)


def audio_level(vals):
    """RMS of a list of audio samples (0 for none)."""
    n = len(vals)
    if not n:
        return 0.0
    return math.sqrt(sum(v * v for v in vals) / n)


# ------------------------------------------------------------------ camera
def camera_pose(cam, t, p, centre):
    """Camera translate + rotate (tx, ty, tz, rx, ry) looking at `centre`. TD camera looks down -Z; rotate order
    xyz (pitch rx applied before yaw ry). front: on +Z; orbit: yaw = Orbitspeed deg/s; top: straight down;
    side: on +X. Camelev = elevation in degrees (front/orbit/side)."""
    d = float(_g(p, 'camdist'))
    e = float(_g(p, 'camelev'))
    if cam == 'top':
        return (centre[0], centre[1] + d, centre[2], -90.0, 0.0)
    a = {'front': 0.0, 'side': 90.0}.get(cam, float(_g(p, 'orbitspeed')) * t)
    ar, er = math.radians(a), math.radians(e)
    return (centre[0] + d * math.cos(er) * math.sin(ar), centre[1] + d * math.sin(er),
            centre[2] + d * math.cos(er) * math.cos(ar), -e, a % 360.0)


def camera_forward(rx, ry):
    """World forward of a TD camera with rotate order xyz: Ry(ry) * Rx(rx) * (0, 0, -1)."""
    a, b = math.radians(rx), math.radians(ry)
    y = math.sin(a)
    z = -math.cos(a)
    return (z * math.sin(b), y, z * math.cos(b))


# ------------------------------------------------------------------ jelly: rotation extraction
def quat_to_mat(q):
    w, x, y, z = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]]


def _qmul(a, b):
    return (a[0] * b[0] - a[1] * b[1] - a[2] * b[2] - a[3] * b[3],
            a[0] * b[1] + a[1] * b[0] + a[2] * b[3] - a[3] * b[2],
            a[0] * b[2] - a[1] * b[3] + a[2] * b[0] + a[3] * b[1],
            a[0] * b[3] + a[1] * b[2] - a[2] * b[1] + a[3] * b[0])


def extract_rotation(A, q=(1.0, 0.0, 0.0, 0.0), iters=100, tol=1e-12):
    """Rotation part of the 3x3 matrix A (list of rows), as a unit quaternion (w, x, y, z), warm-started from q.
    Mueller, Bender, Chentanez, Macklin 2016 ('A Robust Method to Extract the Rotational Part of Deformations'):
    ascends trace(R^T A), always a proper rotation, works when A is rank 2 (flat rest shape)."""
    q = tuple(q)
    for _ in range(iters):
        R = quat_to_mat(q)
        om = [0.0, 0.0, 0.0]
        den = 0.0
        for c in range(3):
            r = (R[0][c], R[1][c], R[2][c])
            a = (A[0][c], A[1][c], A[2][c])
            om[0] += r[1] * a[2] - r[2] * a[1]
            om[1] += r[2] * a[0] - r[0] * a[2]
            om[2] += r[0] * a[1] - r[1] * a[0]
            den += r[0] * a[0] + r[1] * a[1] + r[2] * a[2]
        s = 1.0 / (abs(den) + 1e-9)
        om = [o * s for o in om]
        w = math.sqrt(om[0] ** 2 + om[1] ** 2 + om[2] ** 2)
        if w < tol:
            break
        h = 0.5 * w
        sh = math.sin(h) / w
        q = _qmul((math.cos(h), om[0] * sh, om[1] * sh, om[2] * sh), q)
        n = math.sqrt(sum(x * x for x in q))
        q = tuple(x / n for x in q)
    return q


def polar_rotation(A, q=(1.0, 0.0, 0.0, 0.0), iters=100):
    """3x3 rotation (list of rows) closest to A (max trace(R^T A)); det +1 always."""
    return quat_to_mat(extract_rotation(A, q, iters))


COV_CHANS = ['a00', 'a01', 'a02', 'cx', 'a10', 'a11', 'a12', 'cy', 'a20', 'a21', 'a22', 'cz']


def cov_from_chop(vals):
    """Jelly covariance from the 12 averaged channels of the cov chain -> (A rows, centroid). The chain writes
    p q^T per vertex (q = rest - rest centroid) and p, averaged by Analyze TOPs: A = mean(p q^T); since mean(q) = 0
    this equals mean((p - c) q^T). The rotation does not care about the 1/N scale."""
    g = [float(vals.get(n, 0.0)) for n in COV_CHANS]
    A = [[g[0], g[1], g[2]], [g[4], g[5], g[6]], [g[8], g[9], g[10]]]
    return A, (g[3], g[7], g[11])


# ------------------------------------------------------------------ engine (per frame, in the Script CHOP)
def new_state():
    return {'t': None, 'steps': 0, 'reset': True, 'released': False, 't_burst': None, 'last_kick': None,
            'armed': True, 'q': (1.0, 0.0, 0.0, 0.0), 'beats': 0, 'kicks': 0}


def frame_dt(p, cookrate=60.0):
    """Seconds simulated per frame: Dt (> 0) or 1/cook rate, times Timescale. Never the wall clock (hitches)."""
    dt = float(_g(p, 'dt'))
    if dt <= 0:
        dt = 1.0 / (cookrate if cookrate > 0 else 60.0)
    return dt * float(_g(p, 'timescale'))


def substeps(p, smax=SMAX):
    try:
        s = int(_g(p, 'substeps'))
    except (TypeError, ValueError):
        s = DEFAULTS['substeps']
    return max(1, min(smax, s))


def inv_mass(p):
    n = max(1, int(_g(p, 'gridw')) * int(_g(p, 'gridh')))
    m = float(_g(p, 'mass'))
    return n / m if m > 0 else 0.0


def wind_base(p, t, level=None):
    """Steady wind acceleration (before bursts) for the Windmode."""
    mode = _g(p, 'windmode')
    g = float(_g(p, 'windgain'))
    W = (float(_g(p, 'windx')) * g, float(_g(p, 'windy')) * g, float(_g(p, 'windz')) * g)
    if mode == 'constant':
        return W
    if mode == 'noise':
        sd = int(_g(p, 'seed'))
        x = t * float(_g(p, 'gust'))
        f = 0.5 + vnoise(x, sd)                         # 0.5 .. 1.5 of the set wind
        mag = math.sqrt(W[0] ** 2 + W[1] ** 2 + W[2] ** 2)
        side = (vnoise(x + 17.3, sd + 1) - 0.5) * 0.6 * mag
        up = (vnoise(x + 41.7, sd + 2) - 0.5) * 0.3 * mag
        return (W[0] * f + side, W[1] * f + up, W[2] * f)
    if mode == 'audio':
        lv = 0.0 if level is None else float(level)
        a = lv * float(_g(p, 'audiogain'))
        return (W[0] * a, W[1] * a, W[2] * a)
    return (0.0, 0.0, 0.0)                              # off, bpm (bursts only)


def step(st, t, inp, p, events=(), smax=SMAX):
    """One frame. inp: {'level': audio level or None, 'cov': {chan: value} or None, 'colliders': [(x, y, z, r)],
    'wind': (x, y, z) extra wind (in4) or None, 'cookrate': 60}. events: 'reset' 'step' 'release' 'burst'.
    Returns (st, out) with out['rows'] = NROWS 4-tuples for the shaders and named channels (ENGINE_CHANS)."""
    st = dict(st) if st else new_state()
    ev = list(events or ())
    t = float(t)
    t_prev = st['t']
    st['t'] = t
    test = _g(p, 'testmode')
    cookrate = float(inp.get('cookrate', 60.0) or 60.0)
    if test == 'fixed':
        cookrate = 60.0

    reset = bool(st['reset'])
    st['reset'] = False
    if 'reset' in ev:
        reset = True
        st['released'] = False
        st['t_burst'] = None
    if 'release' in ev:
        st['released'] = True
    run = 0.0 if _g(p, 'pause') else 1.0
    if 'step' in ev:
        run = 1.0
    if reset:
        run = 1.0

    # bursts: manual pulse (any mode), BPM ticks (bpm mode), audio kicks (audio mode)
    mode = _g(p, 'windmode')
    beat = 0.0
    if 'burst' in ev:
        st['t_burst'] = t
    if t_prev is not None:
        ticks = bpm_ticks(t_prev, t, float(_g(p, 'bpm')), BPMDIV_BEATS.get(_g(p, 'bpmdiv'), 1.0))
        if ticks:
            beat = 1.0
            st['beats'] += len(ticks)
            if mode == 'bpm' and test != 'rest':
                st['t_burst'] = t
    level = inp.get('level')
    if mode == 'audio' and level is not None and test == 'off':
        lv = float(level) * float(_g(p, 'audiogain'))
        th = float(_g(p, 'burstthresh'))
        if st['armed'] and lv >= th:
            st['armed'] = False
            ref = float(_g(p, 'burstrefractory'))
            if st['last_kick'] is None or t - st['last_kick'] >= ref - 1e-9:
                st['last_kick'] = t
                st['t_burst'] = t
                st['kicks'] += 1
        elif not st['armed'] and lv < th * 0.8:
            st['armed'] = True

    S = substeps(p, smax)
    dt_sub = frame_dt(p, cookrate) / S
    keep = math.exp(-float(_g(p, 'damping')) * dt_sub)
    W, H = int(_g(p, 'gridw')), int(_g(p, 'gridh'))
    sizew, sizeh = float(_g(p, 'sizew')), float(_g(p, 'sizeh'))
    dx, dy = spacing(W, H, sizew, sizeh)
    a2 = dt_sub * dt_sub if dt_sub > 0 else 1.0

    grav = (float(_g(p, 'gravityx')), float(_g(p, 'gravityy')), float(_g(p, 'gravityz')))
    if test == 'fixed' and mode not in ('off', 'bpm'):
        wind = wind_base(dict(p, windmode='constant'), t)
    else:
        wind = wind_base(p, t, level)
    xw = inp.get('wind')
    if xw and test == 'off':
        wind = (wind[0] + float(xw[0]), wind[1] + float(xw[1]), wind[2] + float(xw[2]))
    e = burst_env(t, st['t_burst'], float(_g(p, 'burstdecay')))
    bdir = _norm3((float(_g(p, 'windx')), float(_g(p, 'windy')), float(_g(p, 'windz'))))
    bf = float(_g(p, 'burstforce')) * e
    wind = (wind[0] + bdir[0] * bf, wind[1] + bdir[1] * bf, wind[2] + bdir[2] * bf)
    turb = 0.0 if test in ('rest', 'fixed') else float(_g(p, 'turbulence'))
    if test == 'rest':
        grav = (0.0, 0.0, 0.0)
        wind = (0.0, 0.0, 0.0)

    spheres = []
    if test != 'rest':
        for k in range(1, NSPHERES + 1):
            if _g(p, 'sphere%don' % k):
                spheres.append((float(_g(p, 'sphere%dx' % k)), float(_g(p, 'sphere%dy' % k)),
                                float(_g(p, 'sphere%dz' % k)), float(_g(p, 'sphere%dr' % k))))
        if test == 'off':
            for c in inp.get('colliders') or ():
                if len(spheres) < NSPHERES and len(c) >= 4:
                    spheres.append(tuple(float(x) for x in c[:4]))
    spheres = (spheres + [(0.0, 0.0, 0.0, -1.0)] * NSPHERES)[:NSPHERES]

    jelly = _g(p, 'mode') == 'jelly'
    rot_valid = 0.0
    R = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    rc = rest_centroid(sizew, sizeh, _g(p, 'orient'), float(_g(p, 'top')))
    cen = rc
    if reset:
        st['q'] = (1.0, 0.0, 0.0, 0.0)
    elif jelly and inp.get('cov'):
        A, c = cov_from_chop(inp['cov'])
        flat = [x for row in A for x in row] + list(c)
        if all(math.isfinite(x) for x in flat) and any(abs(x) > 1e-12 for x in flat[:9]):
            st['q'] = extract_rotation(A, st['q'], iters=20)
            R = quat_to_mat(st['q'])
            cen = c
            rot_valid = 1.0

    fl = 1.0 if (_g(p, 'floor') and test != 'rest') else 0.0
    pm = _g(p, 'pins')
    rows = [None] * NROWS
    rows[ROW['R_STEP']] = (dt_sub, dt_sub * dt_sub, keep, run)
    rows[ROW['R_GRAV']] = (grav[0], grav[1], grav[2], 1.0 if reset else 0.0)
    rows[ROW['R_WIND']] = (wind[0], wind[1], wind[2], float(_g(p, 'aero')))
    rows[ROW['R_TURB']] = (turb, float(_g(p, 'turbscale')), math.fmod(t * float(_g(p, 'gust')), TIME_WRAP),
                           float(int(_g(p, 'seed')) % 1000))
    rows[ROW['R_GRID']] = (float(W), float(H), dx, dy)
    rows[ROW['R_COMP']] = (float(_g(p, 'stretch')) / a2, float(_g(p, 'shear')) / a2, float(_g(p, 'bend')) / a2,
                           float(_g(p, 'relax')))
    rows[ROW['R_MASS']] = (1.0 if st['released'] else 0.0, inv_mass(p), float(_g(p, 'shape')) if jelly else 0.0,
                           1.0 if jelly else 0.0)
    rows[ROW['R_FLOOR']] = (fl, float(_g(p, 'floory')), float(_g(p, 'friction')), float(_g(p, 'thickness')))
    for k in range(NSPHERES):
        rows[ROW['R_SPH0'] + k] = spheres[k]
    rows[ROW['R_ROT0']] = (R[0][0], R[0][1], R[0][2], rot_valid)
    rows[ROW['R_ROT1']] = (R[1][0], R[1][1], R[1][2], 0.0)
    rows[ROW['R_ROT2']] = (R[2][0], R[2][1], R[2][2], 0.0)
    rows[ROW['R_CENT']] = (cen[0], cen[1], cen[2], 0.0)
    rows[ROW['R_REST']] = (rc[0], rc[1], rc[2], float(S))
    rows[ROW['R_TETH']] = (1.0 if _g(p, 'tethers') else 0.0, float(_g(p, 'tetherslack')),
                           float(menu_index(PINMODES, pm)), 0.0)

    if run > 0:
        st['steps'] += S
    cam_c = rc if _g(p, 'orient') == 'vertical' else (rc[0], rc[1] - 0.5 * sizeh, rc[2])
    cam = camera_pose(_g(p, 'cam'), t, p, cam_c)
    out = {'rows': rows, 'reset': 1.0 if reset else 0.0, 'run': run, 'steps': float(st['steps']), 'beat': beat,
           'beats': float(st['beats']), 'kicks': float(st['kicks']), 'burst': e, 'level': float(level or 0.0),
           'wind_x': wind[0], 'wind_y': wind[1], 'wind_z': wind[2], 'released': 1.0 if st['released'] else 0.0,
           'cam_tx': cam[0], 'cam_ty': cam[1], 'cam_tz': cam[2], 'cam_rx': cam[3], 'cam_ry': cam[4],
           'substeps': float(S)}
    return st, out


ENGINE_CHANS = ['reset', 'run', 'steps', 'beat', 'beats', 'kicks', 'burst', 'level', 'wind_x', 'wind_y', 'wind_z',
                'released', 'cam_tx', 'cam_ty', 'cam_tz', 'cam_rx', 'cam_ry', 'substeps']

STATS_AVG_CHANS = ('maxstretch_avg', 'energy_avg', 'nan_avg', 'meanstretch')   # r g b a of the average Analyze
STATS_MAX_CHANS = ('maxstretch', 'energy_max', 'nan_max', 'meanstretch_max')   # r g b a of the maximum Analyze
STATS_CHANS = ['maxstretch', 'meanstretch', 'energy', 'nan', 'steps', 'beat', 'burst', 'kicks', 'released']


def stats_from(avg, mx, W, H):
    """out3 numbers from the Analyze average (per-vertex means) and maximum TOP to CHOPs."""
    n = float(max(1, W * H))
    return {'maxstretch': float(mx.get('maxstretch', 0.0)), 'meanstretch': float(avg.get('meanstretch', 0.0)),
            'energy': float(avg.get('energy_avg', 0.0)) * n, 'nan': round(float(avg.get('nan_avg', 0.0)) * n)}


# ------------------------------------------------------------------ numpy reference solver (same maths as GLSL)
def _shift(A, di, dj):
    """B[j, i] = A[j + dj, i + di] and the validity mask (no wrap)."""
    import numpy as np
    H, W = A.shape[:2]
    B = np.zeros_like(A)
    m = np.zeros((H, W), dtype=bool)
    i0, i1 = max(0, -di), min(W, W - di)
    j0, j1 = max(0, -dj), min(H, H - dj)
    if i1 > i0 and j1 > j0:
        B[j0:j1, i0:i1] = A[j0 + dj:j1 + dj, i0 + di:i1 + di]
        m[j0:j1, i0:i1] = True
    return B, m


def normals_ref(P):
    """Central-difference normals (one-sided at the edges) = cloth_nrm.glsl; used by the wind term."""
    import numpy as np
    H, W = P.shape[:2]
    ip = np.clip(np.arange(W) + 1, 0, W - 1)
    im = np.clip(np.arange(W) - 1, 0, W - 1)
    jp = np.clip(np.arange(H) + 1, 0, H - 1)
    jm = np.clip(np.arange(H) - 1, 0, H - 1)
    n = np.cross(P[:, ip] - P[:, im], P[jp, :] - P[jm, :])
    ln = np.linalg.norm(n, axis=-1, keepdims=True)
    return np.where(ln > 1e-12, n / np.maximum(ln, 1e-12), np.array([0.0, 0.0, 1.0]))


def _weights(pin, rows):
    import numpy as np
    released, w_inv = rows[ROW['R_MASS']][:2]
    return np.where((pin > 0.5) & (released < 0.5), 0.0, w_inv)


def predict_ref(P, V, rest, pin, N0, rows):
    """Inertial prediction (gravity + wind on the frame-start normals N0 + jelly goal); pinned = rest."""
    import numpy as np
    dt, dt2 = rows[ROW['R_STEP']][:2]
    g = np.array(rows[ROW['R_GRAV']][:3])
    wv = np.array(rows[ROW['R_WIND']][:3])
    aero = rows[ROW['R_WIND']][3]
    a = g + (1.0 - aero) * wv + aero * N0 * (N0 @ wv)[..., None]
    X = P + V * dt + a * dt2
    _, _, shape, jelly = rows[ROW['R_MASS']]
    if jelly > 0.5 and shape != 0 and rows[ROW['R_ROT0']][3] > 0.5:
        R = np.array([rows[ROW['R_ROT0']][:3], rows[ROW['R_ROT1']][:3], rows[ROW['R_ROT2']][:3]])
        c = np.array(rows[ROW['R_CENT']][:3])
        rc = np.array(rows[ROW['R_REST']][:3])
        X = X + shape * (c + (rest - rc) @ R.T - X)
    fixed = _weights(pin, rows) == 0.0
    X[fixed] = rest[fixed]
    return X


def substep_ref(P, V, rest, pin, N0, rows):
    """One fused substep = cloth_substep.glsl: predict, one gather-Jacobi pass over the 12-stencil (XPBD compliance),
    tethers, collisions + friction, velocity. Returns (X, V)."""
    import numpy as np
    dt, _, keep, run = rows[ROW['R_STEP']]
    if rows[ROW['R_GRAV']][3] > 0.5:
        return rest.copy(), np.zeros_like(V)
    if run < 0.5:
        return P.copy(), V.copy()
    X = predict_ref(P, V, rest, pin, N0, rows)
    W, H, dx, dy = rows[ROW['R_GRID']]
    al = rows[ROW['R_COMP']][:3]
    relax = rows[ROW['R_COMP']][3]
    w = _weights(pin, rows)
    corr = np.zeros_like(X)
    cnt = np.zeros(X.shape[:2])
    for di, dj, ty in STENCIL:
        Xn, m = _shift(X, di, dj)
        wn, _ = _shift(w, di, dj)
        L = rest_length(di, dj, dx, dy)
        d = X - Xn
        ln = np.linalg.norm(d, axis=-1)
        den = w + wn + al[ty]
        ok = m & (ln > 1e-9) & (den > 1e-12)
        lam = np.where(ok, -(ln - L) / np.where(ok, den, 1.0), 0.0)
        corr += (w * lam / np.where(ok, ln, 1.0))[..., None] * d
        cnt += ok
    Y = X + relax * corr / np.maximum(cnt, 1.0)[..., None]
    Y = tether_ref(Y, rest, pin, rows, w > 0)
    Y = collide_ref(Y, P, rows, w > 0)
    Vn = (Y - P) / dt * keep if dt > 0 else np.zeros_like(V)
    return Y, Vn


def tether_ref(Y, rest, pin, rows, free):
    import numpy as np
    on, slack, pmi = rows[ROW['R_TETH']][:3]
    released = rows[ROW['R_MASS']][0]
    if on < 0.5 or released > 0.5:
        return Y
    H, W = Y.shape[:2]
    pm = PINMODES[int(pmi + 0.5)]
    if pm == 'top':
        anchors = [rest[H - 1:H, :, :]]                   # per column
    else:
        anchors = [rest[j, i][None, None, :] for (i, j) in tether_anchors(0, 0, W, H, pm)]
    for A in anchors:
        lr = np.linalg.norm(rest - A, axis=-1) * slack
        d = Y - A
        dl = np.linalg.norm(d, axis=-1)
        over = free & (dl > lr) & (dl > 1e-9)
        Y = np.where(over[..., None], A + d / np.maximum(dl, 1e-12)[..., None] * lr[..., None], Y)
    return Y


def collide_ref(Y, P, rows, free):
    """Spheres then floor (projection out to radius + thickness), then friction: the tangential part of this
    substep's displacement is reduced by Friction (0..1) on vertices in contact."""
    import numpy as np
    on, fy, fr, th = rows[ROW['R_FLOOR']]
    contact = np.zeros(Y.shape[:2], dtype=bool)
    nrm = np.zeros_like(Y)
    for k in range(NSPHERES):
        cx, cy, cz, r = rows[ROW['R_SPH0'] + k]
        if r <= 0:
            continue
        c = np.array([cx, cy, cz])
        v = Y - c
        dd = np.linalg.norm(v, axis=-1)
        hit = free & (dd < r + th)
        u = np.where(dd[..., None] > 1e-9, v / np.maximum(dd, 1e-9)[..., None], np.array([0.0, 1.0, 0.0]))
        Y = np.where(hit[..., None], c + u * (r + th), Y)
        nrm = np.where(hit[..., None], u, nrm)
        contact |= hit
    if on > 0.5:
        hit = free & (Y[..., 1] < fy + th)
        Y = Y.copy()
        Y[..., 1] = np.where(hit, fy + th, Y[..., 1])
        nrm = np.where(hit[..., None], np.array([0.0, 1.0, 0.0]), nrm)
        contact |= hit
    if fr > 0:
        dP = Y - P
        tn = dP - nrm * np.sum(dP * nrm, axis=-1, keepdims=True)
        Y = np.where(contact[..., None], Y - min(fr, 1.0) * tn, Y)
    return Y


def frame_ref(P, V, rest, pin, rows):
    """One frame = the TD chain: normals once from the frame-start positions, then S fused substeps."""
    S = int(rows[ROW['R_REST']][3])
    N0 = normals_ref(P)
    for _ in range(S):
        P, V = substep_ref(P, V, rest, pin, N0, rows)
    return P, V


def jelly_rows_ref(P, rest, rows, q=(1.0, 0.0, 0.0, 0.0)):
    """Fill R_ROT*/R_CENT from positions the way the cov chain + engine do (mean p q^T, mean p). Returns (rows, q)."""
    import numpy as np
    rc = np.array(rows[ROW['R_REST']][:3])
    Q = (rest - rc).reshape(-1, 3)
    Pf = P.reshape(-1, 3)
    A = (Pf.T @ Q) / len(Pf)
    c = Pf.mean(axis=0)
    q = extract_rotation(A.tolist(), q, iters=20)
    R = quat_to_mat(q)
    rows = list(rows)
    rows[ROW['R_ROT0']] = (R[0][0], R[0][1], R[0][2], 1.0)
    rows[ROW['R_ROT1']] = (R[1][0], R[1][1], R[1][2], 0.0)
    rows[ROW['R_ROT2']] = (R[2][0], R[2][1], R[2][2], 0.0)
    rows[ROW['R_CENT']] = (float(c[0]), float(c[1]), float(c[2]), 0.0)
    return rows, q


def structural_stretch(P, rows):
    """(max, mean) of |len/L - 1| over structural springs (each spring once)."""
    import numpy as np
    W, H, dx, dy = rows[ROW['R_GRID']]
    vals = []
    for di, dj in ((1, 0), (0, 1)):
        Xn, m = _shift(P, di, dj)
        L = rest_length(di, dj, dx, dy)
        vals.append(np.abs(np.linalg.norm(P - Xn, axis=-1) / L - 1.0)[m])
    v = np.concatenate(vals)
    return float(v.max()), float(v.mean())


def stats_ref(P, V, rest, pin, rows):
    """Per-vertex stats texture as cloth_stats.glsl writes it: r = max strain of its structural springs, g = kinetic
    energy 0.5 m v^2, b = 1 if any component is not finite, a = mean strain."""
    import numpy as np
    W, H, dx, dy = rows[ROW['R_GRID']]
    w_inv = rows[ROW['R_MASS']][1]
    m = 1.0 / w_inv if w_inv > 0 else 0.0
    smax = np.zeros(P.shape[:2])
    ssum = np.zeros(P.shape[:2])
    cnt = np.zeros(P.shape[:2])
    for di, dj, _ in STRUCTURAL:
        Xn, ok = _shift(P, di, dj)
        L = rest_length(di, dj, dx, dy)
        s = np.where(ok, np.abs(np.linalg.norm(P - Xn, axis=-1) / L - 1.0), 0.0)
        smax = np.maximum(smax, s)
        ssum += s
        cnt += ok
    e = 0.5 * m * np.sum(V * V, axis=-1)
    bad = (~np.isfinite(P).all(axis=-1)) | (~np.isfinite(V).all(axis=-1))
    return np.stack([smax, e, bad.astype(float), ssum / np.maximum(cnt, 1)], axis=-1)
