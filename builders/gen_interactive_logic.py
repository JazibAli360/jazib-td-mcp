"""gen_interactive_logic - pure logic of the GEN_interactive rack (builders/gen_interactive.py): the tracked points
every module reads (sources: demo paths, FT_face_track landmarks, /project1/effectors rows and point sets, Null COMPs,
the mouse, any CHOP), their smoothing + velocity, the packed `pts` layout, the drive envelope, and the numpy twin of
the rack's mask pass (builders/glsl/gen_interactive_mask.glsl). Hash / noise / palette / blend are GEN_sim's
(builders/gen_sim_logic.py, loaded below) because the shaders prefix gen_sim_common.glsl. Copied into the rack's
`gi_logic` Text DAT; the `pts` Script CHOP calls cook_points(). numpy only inside functions. ASCII only.

Screen convention everywhere: x, y in 0..1 of the frame, y UP (TD texel space, row 0 = bottom, T-58); pixels =
(x * W, y * H). Absent points: x = y = ABSENT (-10) and velocity 0 (a shader tests x > -1)."""
import fnmatch
import math
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
ABSENT = -10.0
CHANS = ('x', 'y', 'vx', 'vy')
SOURCES = ['demo', 'face', 'effectors', 'null', 'mouse', 'chop']
SOURCE_LABELS = ['Demo paths (no input needed)', 'FT_face_track landmarks', 'Shared effectors (/project1/effectors)',
                 'Null COMPs (tx ty on the plane)', 'Mouse (Mouse In CHOP)', 'Any CHOP (x y / tx ty)']
CHOP_UNITS = ['unit', 'signed', 'plane']
CHOP_UNIT_LABELS = ['0..1 (x y)', '-1..1 (tx ty)', 'World plane (tx ty, Plane page)']
DEMO_SHAPES = ['lissajous', 'orbit', 'wander', 'dance']
DEMO_LABELS = ['Lissajous', 'Orbit', 'Wander (noise)', 'Dance (two hands + head)']
MASK_SOURCES = ['none', 'top', 'luma']
MASK_LABELS = ['None (presence 1 everywhere)', 'Mask TOP (person mask / face mask)', 'Luma of the background']
MASK_CHANNELS = ['r', 'a', 'luma']

_GS = {}


def gs():
    """builders/gen_sim_logic.py (hash3, vnoise, palette, blend == gen_sim_common.glsl)."""
    if not _GS:
        with open(os.path.join(HERE, 'gen_sim_logic.py')) as fh:
            exec(fh.read(), _GS)
    return _GS


# ------------------------------------------------------------------ plane mapping (effectors / Nulls / chop plane)
def plane_to_screen(x, y, plane):
    """World (x, y) on the plane (cx, cy, w, h) -> screen 0..1 (y up). Default plane = BN_fluid2d's effector plane
    (centre 0, 1.125 x 2 units = the 9:16 frame)."""
    cx, cy, w, h = plane
    return ((x - cx) / (w or 1.0) + 0.5, (y - cy) / (h or 1.0) + 0.5)


# ------------------------------------------------------------------ sources -> [(x, y) or None] (0..1, y up)
def _hash01(i, s):
    return float(gs()['hash3'](i, 17, s))


_HC = {}


def _demo_hashes(n, seed):
    """[_hash01(k, seed) for k in range(4 n)], one vectorised hash3 call, cached per (n, seed): the per-point scalar
    numpy calls cost ~3.3 ms CPU per frame at n = 16 under Rosetta (perf lane 2, 27 Oct); same values bit for bit."""
    key = (int(n), int(seed))
    h = _HC.get(key)
    if h is None:
        np = gs()['_np']()
        h = [float(v) for v in gs()['hash3'](np.arange(4 * key[0]), 17, key[1])]
        if len(_HC) > 32:
            _HC.clear()
        _HC[key] = h
    return h


def demo_points(t, n, shape=0, seed=1):
    """n moving demo points (no sensor needed): 0 Lissajous, 1 orbit, 2 wander (value noise), 3 dance (n = 3 here:
    two 'hands' swinging + a 'head' bobbing; more points repeat the pattern with offsets)."""
    out = []
    G = gs()
    HS = _demo_hashes(n, seed)
    if shape == 2:                                            # wander: both noise lookups for all points at once
        np = G['_np']()
        ii = np.arange(n)
        WX = G['vnoise'](t * 0.35 + 13.1 * ii, 3.7 * ii, seed + 1)
        WY = G['vnoise'](t * 0.35 + 7.3 * ii, 5.1 * ii + 2.0, seed + 2)
    for i in range(n):
        h1, h2, h3, h4 = HS[4 * i:4 * i + 4]
        if shape == 1:
            a = t * (0.3 + 0.5 * h1) * (1 if i % 2 == 0 else -1) + 2 * math.pi * h2
            r = 0.15 + 0.25 * h3
            x, y = 0.5 + r * math.cos(a) * 1.0, 0.5 + r * math.sin(a) * 9.0 / 16.0
        elif shape == 2:
            x = 0.1 + 0.8 * float(WX[i])
            y = 0.1 + 0.8 * float(WY[i])
        elif shape == 3:
            k = i % 3
            g = i // 3
            ph = t * 2.0 * math.pi * 0.5 + g * 1.3
            if k == 2:
                x, y = 0.5 + 0.03 * math.sin(ph * 0.5), 0.72 + 0.02 * math.sin(ph)
            else:
                s_ = -1.0 if k == 0 else 1.0
                x = 0.5 + s_ * (0.22 + 0.12 * math.sin(ph + (0.0 if k == 0 else 1.7)))
                y = 0.45 + 0.18 * math.cos(ph * (1.0 if k == 0 else 1.3) + g)
            x += 0.05 * g * math.sin(g * 2.1)
        else:
            w1, w2 = 0.2 + 0.5 * h1, 0.2 + 0.5 * h2
            x = 0.5 + 0.38 * math.sin(t * w1 + 2 * math.pi * h3)
            y = 0.5 + 0.40 * math.sin(t * w2 + 2 * math.pi * h4)
        out.append((x, y))
    return out


def face_channels(names, patterns):
    """FT_face_track out_pts channel names (`f<n>_<region>_<kk>x/y`) -> ordered list of point stems matching any of
    the space-separated glob patterns (on the stem, e.g. `f1_nose_*`), in CHOP order, x and y both present."""
    pats = str(patterns or '').replace(',', ' ').split() or ['*']
    names = list(names)
    have = set(names)
    out = []
    for n in names:
        if not n.endswith('x'):
            continue
        stem = n[:-1]
        if stem + 'y' not in have or stem in out:
            continue
        if any(fnmatch.fnmatchcase(stem, p) for p in pats):
            out.append(stem)
    return out


def face_points(names, values, patterns, stride=1, n=None, mirror=False):
    """Landmarks (0..1, origin top-left, zeros when absent) -> [(x, y up) or None]. stride takes every k-th match."""
    idx = dict((nm, i) for i, nm in enumerate(names))
    stems = face_channels(names, patterns)[::max(1, int(stride))]
    out = []
    for s in stems:
        x, y = float(values[idx[s + 'x']]), float(values[idx[s + 'y']])
        if x == 0.0 and y == 0.0:
            out.append(None)
        else:
            out.append((1.0 - x if mirror else x, 1.0 - y))
    return out[:n] if n is not None else out


def effector_points(texels, rows_idx, plane, n=None, sets=True, centres=True):
    """Packed /project1/effectors buffer (list or (T, 4) array; effectors_logic.pack_buffer) + the selected row
    indices -> [(x, y) or None] on screen. Point-set rows give their points (sets), other rows their centre
    (centres). Disabled rows are skipped (the selection already drops them; texel 6.w double-checks)."""
    tx = [list(map(float, t)) for t in texels]
    if not tx:
        return []
    cnt, W = int(round(tx[0][0])), int(round(tx[0][1])) or 10
    out = []
    for i in rows_idx:
        if i < 0 or i >= cnt:
            continue
        base = 1 + i * W
        if base + 9 >= len(tx) or tx[base + 6][3] < 0.5:
            continue
        sdf, pstart, pcount = tx[base + 3][0], int(round(tx[base + 8][2])), int(round(tx[base + 8][3]))
        if sdf > 5.5 and pcount > 0:
            if sets:
                for k in range(pcount):
                    t = tx[pstart + 2 * k] if pstart + 2 * k < len(tx) else None
                    out.append(plane_to_screen(t[0], t[1], plane) if t is not None and t[3] > 0.5 else None)
        elif centres:
            c = tx[base + 4]
            out.append(plane_to_screen(c[0], c[1], plane))
    return out[:n] if n is not None else out


def chop_points(chans, units, plane, n=None):
    """{name: [samples]} of any CHOP -> points: one point per sample. units 0 (x y 0..1), 1 (tx ty -1..1),
    2 (tx ty world plane). Names tried: x/y, tx/ty, u/v, then the first two channels."""
    keys = list(chans)
    for a, b in (('x', 'y'), ('tx', 'ty'), ('u', 'v'), ('P0', 'P1')):
        if a in chans and b in chans:
            xs, ys = chans[a], chans[b]
            break
    else:
        if len(keys) < 2:
            return []
        xs, ys = chans[keys[0]], chans[keys[1]]
    out = []
    for x, y in zip(xs, ys):
        x, y = float(x), float(y)
        if units == 1:
            out.append(((x + 1.0) * 0.5, (y + 1.0) * 0.5))
        elif units == 2:
            out.append(plane_to_screen(x, y, plane))
        else:
            out.append((x, y))
    return out[:n] if n is not None else out


# ------------------------------------------------------------------ smoothing + velocity + packing
def smooth_alpha(smooth, dt):
    """One-pole factor for this frame: Smooth = the share kept per 1/60 s (0 = raw), frame-rate independent."""
    s = min(max(float(smooth), 0.0), 0.9999)
    if dt <= 0:
        return 1.0
    return 1.0 - s ** (dt * 60.0)


def step_points(state, raw, dt, smooth, n):
    """state: {'p': [(x, y) or None] * n, 'v': [(vx, vy)] * n} (kept by the runtime between cooks) -> new state.
    A point that appears starts at its raw position with velocity 0; an absent one is dropped (None)."""
    a = smooth_alpha(smooth, dt)
    old_p = list(state.get('p') or [])
    old_v = list(state.get('v') or [])
    P, V = [], []
    for i in range(n):
        r = raw[i] if i < len(raw) else None
        o = old_p[i] if i < len(old_p) else None
        if r is None:
            P.append(None)
            V.append((0.0, 0.0))
            continue
        if o is None:
            P.append((float(r[0]), float(r[1])))
            V.append((0.0, 0.0))
            continue
        p = (o[0] + (r[0] - o[0]) * a, o[1] + (r[1] - o[1]) * a)
        v = ((p[0] - o[0]) / dt, (p[1] - o[1]) / dt) if dt > 0 else (old_v[i] if i < len(old_v) else (0.0, 0.0))
        P.append(p)
        V.append(v)
    return {'p': P, 'v': V}


def pack(state, n):
    """state -> 4 channel lists (x y vx vy) of n samples; absent = ABSENT, velocity 0."""
    xs, ys, vx, vy = [], [], [], []
    P, V = state.get('p') or [], state.get('v') or []
    for i in range(n):
        p = P[i] if i < len(P) else None
        if p is None:
            xs.append(ABSENT)
            ys.append(ABSENT)
            vx.append(0.0)
            vy.append(0.0)
        else:
            v = V[i] if i < len(V) else (0.0, 0.0)
            xs.append(float(p[0]))
            ys.append(float(p[1]))
            vx.append(float(v[0]))
            vy.append(float(v[1]))
    return [xs, ys, vx, vy]


def present_count(chans):
    return sum(1 for x in chans[0] if x > -1.0)


# ------------------------------------------------------------------ drive (== gi_env / gi_level in the common GLSL)
def env(beats, bpm, gain, decay):
    """Beat pulse: gain x exp(-age / decay), age = seconds since the last whole beat (frac(beats) x 60 / bpm)."""
    age = (beats - math.floor(beats)) * 60.0 / max(bpm, 1.0)
    return gain * math.exp(-age / max(decay, 1e-3))


def level(audio, audiogain, manual):
    return audiogain * audio + manual


# ------------------------------------------------------------------ the rack's mask pass (numpy twin)
def mask_step(src_rgba, prev, channel=0, mode=1, thresh=0.5, soft=0.1, motiongain=4.0, motionsmooth=0.8,
              invert=False):
    """One cook of gi_mask (arrays [y, x, 4] float64): r = presence 0..1, g = motion (smoothed |luma - last luma| x
    gain), b = this luma (kept for the next frame), a = 1. prev = the last output (None or alpha 0 = no history: motion 0).
    mode 0 none (presence 1), 1 top (channel r / a / luma of the mask TOP), 2 luma (smoothstep of the picture's luma
    around thresh +- soft)."""
    np = gs()['_np']()
    s = np.asarray(src_rgba, dtype=np.float64)
    lum = s[..., 0] * 0.2126 + s[..., 1] * 0.7152 + s[..., 2] * 0.0722
    if mode == 0:
        pres = np.ones(lum.shape)
    elif mode == 1:
        pres = s[..., 0] if channel == 0 else (s[..., 3] if channel == 1 else lum)
        pres = np.clip(pres, 0.0, 1.0)
    else:
        lo, hi = thresh - max(soft, 1e-4), thresh + max(soft, 1e-4)
        t = np.clip((lum - lo) / (hi - lo), 0.0, 1.0)
        pres = t * t * (3 - 2 * t)
    if invert:
        pres = 1.0 - pres
    mot = np.zeros(lum.shape)
    if prev is not None:
        pv = np.asarray(prev, dtype=np.float64)
        raw = np.abs(lum - pv[..., 2]) * motiongain
        mot = np.where(pv[..., 3] > 0.5, pv[..., 1] * motionsmooth + raw * (1.0 - motionsmooth), 0.0)
    out = np.zeros(s.shape[:2] + (4,))
    out[..., 0], out[..., 1], out[..., 2], out[..., 3] = pres, mot, lum, 1.0
    return out
