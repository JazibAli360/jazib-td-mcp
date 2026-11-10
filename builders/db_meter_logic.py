# db_meter_logic - pure logic for the db_meter COMP (no td import; ASCII only).
# Spec: docs/research/BG_rudiment_db_meter.md. Copied into the COMP's 'meter_logic' Text DAT by builders/db_meter.py.
# The same functions place the bars (GLSL uniforms read the 'geometry' table) and the labels (Script TOP),
# so the labels line up with the bars at any size.
import math

EPS_AMP = 1e-6


def amp_to_db(a, floor=-60.0):
    """Linear amplitude -> dBFS, never below floor (0 or negative -> floor)."""
    a = abs(float(a))
    if a <= EPS_AMP:
        return float(floor)
    return max(float(floor), 20.0 * math.log10(a))


def db_to_amp(db):
    return 10.0 ** (float(db) / 20.0)


def db_to_frac(db, floor, ceil):
    """dB -> 0..1 along the bar (floor = 0, ceil = 1), clamped."""
    span = float(ceil) - float(floor)
    if span <= 0:
        return 0.0
    f = (float(db) - float(floor)) / span
    return 0.0 if f < 0 else (1.0 if f > 1 else f)


def frac_to_db(f, floor, ceil):
    return float(floor) + float(f) * (float(ceil) - float(floor))


def label_text(db):
    r = round(db)
    if abs(db - r) < 1e-6:
        return str(int(r))
    return '{:.1f}'.format(db)


def label_rows(floor, ceil, step, min_gap_frac=1.0 / 30.0):
    """Label dB values, top to bottom: ceil, 0 (if inside), then every `step` (anchored at 0) down to floor, plus
    floor. A grid denser than min_gap_frac (of the bar length) is widened to a multiple of step; then a candidate
    closer than min_gap_frac to an accepted label is dropped; priority order: 0, ceil, the grid, floor."""
    floor, ceil, step = float(floor), float(ceil), abs(float(step))
    if ceil <= floor:
        return []
    cands = []
    if floor <= 0.0 <= ceil:
        cands.append(0.0)
    cands.append(ceil)
    span = ceil - floor
    if step > 0:
        for k in (1, 2, 3, 4, 5, 6, 10, 12, 20, 24, 50, 100):  # widen a too-dense grid to a multiple of step
            if step * k / span >= min_gap_frac - 1e-9:
                break
        step = step * k
        # grid anchored at 0: k*step for k in ints, inside [floor, ceil]
        k_hi = int(math.floor(ceil / step + 1e-9))
        k_lo = int(math.ceil(floor / step - 1e-9))
        for k in range(k_hi, k_lo - 1, -1):
            cands.append(k * step)
    cands.append(floor)
    out = []
    for v in cands:
        f = db_to_frac(v, floor, ceil)
        if all(abs(f - db_to_frac(u, floor, ceil)) >= min_gap_frac - 1e-9 for u in out):
            out.append(v)
    return sorted(out, reverse=True)


def geometry(w, h, orient='vertical', gap=4.0, scalew=0.4, showscale=True):
    """Meter layout in pixels. 'a' = the level axis (bottom->top for vertical, left->right for horizontal),
    'c' = the cross axis (left->right for vertical, top->bottom for horizontal).
    Returns a0/a1 (bar span on a: floor..ceil), l0/l1 (clip lamp span on a), b0/b1 (both bars on c),
    bw (one bar's width), gap, s0/s1 (label strip on c; s0 == s1 when hidden), L, C (axis lengths)."""
    w, h = max(1, int(w)), max(1, int(h))
    vert = (orient != 'horizontal')
    L, C = (h, w) if vert else (w, h)
    # end padding: room for the end labels' halves (wider labels sit along the axis when horizontal)
    pad_a = max(3.0, round((0.025 if vert else 0.035) * L))
    lamp = max(3.0, round(0.012 * L))         # clip lamp thickness
    lgap = max(2.0, round(0.006 * L))         # space between lamp and bar
    a0 = pad_a
    l1 = L - pad_a
    l0 = l1 - lamp
    a1 = l0 - lgap
    pad_c = max(2.0, round(0.06 * C))
    sw = round(max(0.0, min(0.9, float(scalew))) * C) if showscale else 0.0
    s1 = C
    s0 = C - sw
    b0 = pad_c
    b1 = (s0 - max(2.0, round(0.04 * C))) if showscale else (C - pad_c)
    g = max(0.0, float(gap))
    bw = max(1.0, (b1 - b0 - g) / 2.0)
    return {'L': float(L), 'C': float(C), 'a0': float(a0), 'a1': float(a1), 'l0': float(l0), 'l1': float(l1),
            'b0': float(b0), 'b1': float(b1), 'bw': float(bw), 'gap': g, 's0': float(s0), 's1': float(s1),
            'vert': 1.0 if vert else 0.0}


def axis_pos(db, geo, floor, ceil):
    """Pixel coordinate on the level axis (continuous, 0 = low end edge) of a dB value. The shader fills a bar
    pixel whose centre (n + 0.5) is below this, so the bar top / label centre sit on the same coordinate."""
    return geo['a0'] + db_to_frac(db, floor, ceil) * (geo['a1'] - geo['a0'])


def auto_font_px(geo, fontsize=0.0):
    """Label height in px: Fontsize if > 0, else from the meter size."""
    if fontsize and fontsize > 0:
        return float(fontsize)
    if geo['vert']:
        px = min(geo['L'] / 42.0, max(1.0, geo['s1'] - geo['s0']) * 0.32)
    else:
        px = min(geo['L'] / 70.0, max(1.0, geo['s1'] - geo['s0']) * 0.45)
    return max(6.0, round(px))


def block_peak(samples):
    """Peak |x| of a block (iterable or numpy array)."""
    try:
        import numpy as np
        a = np.asarray(samples, dtype=float)
        return float(np.max(np.abs(a))) if a.size else 0.0
    except ImportError:
        s = [abs(float(x)) for x in samples]
        return max(s) if s else 0.0


def block_rms(samples):
    try:
        import numpy as np
        a = np.asarray(samples, dtype=float)
        return float(np.sqrt(np.mean(a * a))) if a.size else 0.0
    except ImportError:
        s = [float(x) for x in samples]
        return math.sqrt(sum(x * x for x in s) / len(s)) if s else 0.0


def ballistics_step(cur, target, dt, attack, release):
    """One step of the bar's ballistics in dB. Rise: instant if attack <= 0, else exponential with time
    constant `attack` s. Fall: linear at `release` dB/s (release <= 0 = instant), never below target."""
    if cur is None:
        return float(target)
    if target >= cur:
        if attack <= 0:
            return float(target)
        return cur + (target - cur) * (1.0 - math.exp(-max(0.0, dt) / attack))
    if release <= 0:
        return float(target)
    return max(float(target), cur - release * max(0.0, dt))


def peak_hold_step(state, db, t, hold, release):
    """Peak hold. state = (peak_db, peak_time) or None. The line holds `hold` s, then falls at `release` dB/s
    (release <= 0: it holds until reset); a level at or above the line re-arms it.
    Returns (new_state, shown_peak_db)."""
    if state is None:
        return (float(db), float(t)), float(db)
    pk, pt = state
    over = float(t) - pt - max(0.0, hold)
    shown = pk - release * over if (over > 0 and release > 0) else pk
    if db >= shown:
        return (float(db), float(t)), float(db)
    return (pk, pt), shown


def clip_step(clip_until, db, t, clipdb, hold):
    """Clip lamp. Returns (new_clip_until, lamp 0/1): lit while t <= clip_until; db >= clipdb re-arms it."""
    if db >= clipdb:
        clip_until = float(t) + max(0.0, hold)
        return clip_until, 1
    if clip_until is not None and t <= clip_until:
        return clip_until, 1
    return clip_until, 0


class PeakHold(object):
    """Object wrapper of peak_hold_step for tests / scripts (keep instances out of op storage, T-67)."""

    def __init__(self, hold=1.5, release=24.0):
        self.hold, self.release, self.state = hold, release, None

    def update(self, db, t):
        self.state, shown = peak_hold_step(self.state, db, t, self.hold, self.release)
        return shown

    def reset(self):
        self.state = None


def meter_step(state, raw_l, raw_r, t, p):
    """One frame for both channels. state: plain dict (storable). raw_*: dB this frame (unclamped; the clip lamp
    compares it before the bar clamps it to floor..ceil).
    p: dict floor ceil attack release hold clipdb. Returns (state, out dict l r lpeak rpeak lclip rclip)."""
    st = dict(state or {})
    last_t = st.get('t')
    if last_t is not None and float(t) < last_t:  # clock went back (project reopened): start fresh
        st, last_t = {}, None
    dt = 0.0 if last_t is None else max(0.0, float(t) - last_t)
    out = {}
    for ch, raw_in in (('l', raw_l), ('r', raw_r)):
        raw = min(max(float(raw_in), p['floor']), p['ceil'])
        cur = ballistics_step(st.get(ch), raw, dt, p['attack'], p['release'])
        cur = min(max(cur, p['floor']), p['ceil'])
        pk_state = st.get(ch + 'pk')
        pk_state = tuple(pk_state) if pk_state is not None else None
        pk_state, shown = peak_hold_step(pk_state, raw, t, p['hold'], p['release'])
        shown = min(max(shown, p['floor']), p['ceil'])
        cu, lamp = clip_step(st.get(ch + 'clip'), float(raw_in), t, p['clipdb'], p['hold'])  # unclamped
        st[ch], st[ch + 'pk'], st[ch + 'clip'] = cur, list(pk_state), cu
        out[ch], out[ch + 'peak'], out[ch + 'clip'] = cur, shown, lamp
    st['t'] = float(t)
    return st, out
