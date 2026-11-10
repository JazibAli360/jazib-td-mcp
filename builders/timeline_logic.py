"""TL_timeline pure logic (no td imports). Copied into the COMP's `tl_logic` Text DAT.

Clock advance, loop wrap, keyframe lanes (hold/linear/ease/bezier), timecode, snapping, markers, ruler hit tests.
Tested offline by test/test_timeline.py. Pure ASCII.
"""
import math

INTERPS = ('hold', 'linear', 'ease', 'bezier')
TCMODES = ('seconds', 'frames', 'smpte', 'bars')
RULER_FRAC = 0.2      # top part of the view = time ruler; lanes share the rest
LANE_PAD = 0.12       # fraction of a lane band left empty at top and bottom
EPS = 1e-9


def _f(x, default=0.0):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    if v != v or v in (float('inf'), float('-inf')):
        return default
    return v


# ---------------------------------------------------------------- clock
def wrap(t, a, b, loop):
    """Playhead into [a, b]: modulo when looping, clamp otherwise."""
    if b <= a:
        return a
    if loop:
        return a + (t - a) % (b - a)
    return min(max(t, a), b)


def advance(t, dt, rate, playing, loop, a, b):
    """One clock step. Returns (t, playing, wraps).

    wraps = signed number of loop wraps this step. Without loop the playhead stops at the edge it runs into
    (out for rate > 0, in for rate < 0) and playing turns False.
    """
    if b <= a:
        return a, False, 0
    if not playing:
        return t, False, 0
    # bring a playhead that sits outside the play range into it first
    if t < a or t > b:
        t = wrap(t, a, b, loop)
    nt = t + dt * rate
    if loop:
        span = b - a
        wraps = int(math.floor((nt - a) / span))
        return a + (nt - a) - wraps * span, True, wraps
    if rate > 0 and nt >= b - 1e-9:
        return b, False, 0
    if rate < 0 and nt <= a + 1e-9:
        return a, False, 0
    return nt, True, 0


def frame_of(t, fps):
    return int(math.floor(t * fps + 1e-4)) if fps > 0 else 0


def quantize_frame(t, fps):
    return frame_of(t, fps) / fps if fps > 0 else t


def step_frame(t, fps, n):
    """Move n frames from t (lands on a frame boundary)."""
    if fps <= 0:
        return t
    return (frame_of(t, fps) + n) / fps


# ---------------------------------------------------------------- grid + timecode
def beats(t, bpm):
    return t * bpm / 60.0 if bpm > 0 else 0.0


def bar_beat(t, bpm, bpb):
    """(bar, beat, sixteenth) 1-based, for t >= 0."""
    bpb = max(1, int(bpb))
    b = beats(max(t, 0.0), bpm) + 1e-6
    bar = int(b // bpb)
    beat = int(b - bar * bpb)
    six = int((b - math.floor(b)) * 4)
    return bar + 1, beat + 1, six + 1


def format_tc(t, fps, mode='smpte', bpm=120.0, bpb=4):
    sign = '-' if t < -EPS else ''
    at = abs(t)
    if mode == 'seconds':
        m = int(at // 60)
        s = at - m * 60
        return '%s%02d:%06.3f' % (sign, m, s)
    if mode == 'frames':
        return '%s%d' % (sign, frame_of(at, fps))
    if mode == 'bars':
        bar, beat, six = bar_beat(at, bpm, bpb)
        return '%s%d.%d.%d' % (sign, bar, beat, six)
    ifps = max(1, int(round(fps)))
    total = frame_of(at, ifps)
    ff = total % ifps
    secs = total // ifps
    return '%s%02d:%02d:%02d:%02d' % (sign, secs // 3600, (secs // 60) % 60, secs % 60, ff)


def grid_step(bpm, snapdiv, fps, unit='beat'):
    """Snap step in seconds: unit 'beat' = one beat / snapdiv, 'frame' = 1 / fps."""
    if unit == 'frame':
        return 1.0 / fps if fps > 0 else 0.0
    if bpm <= 0:
        return 0.0
    return 60.0 / bpm / max(1, int(snapdiv))


def snap(t, step):
    if step <= 0:
        return t
    return round(t / step) * step


# ---------------------------------------------------------------- keys / lanes
def parse_keys(rows):
    """rows: list of rows (strings), first row header time,value,interp (any order). -> sorted [(t, v, interp)]."""
    if not rows:
        return []
    head = [str(c).strip().lower() for c in rows[0]]
    if 'time' in head:
        it, iv = head.index('time'), head.index('value') if 'value' in head else 1
        ii = head.index('interp') if 'interp' in head else -1
        body = rows[1:]
    else:
        it, iv, ii, body = 0, 1, 2, rows
    out = []
    for r in body:
        if len(r) <= max(it, iv):
            continue
        try:
            t = float(r[it])
            v = float(r[iv])
        except (TypeError, ValueError):
            continue
        interp = str(r[ii]).strip().lower() if 0 <= ii < len(r) else 'linear'
        if interp not in INTERPS:
            interp = 'linear'
        out.append((t, v, interp))
    out.sort(key=lambda k: k[0])  # stable: equal times keep table order
    return out


def keys_to_rows(keys):
    rows = [['time', 'value', 'interp']]
    for t, v, i in sorted(keys, key=lambda k: k[0]):
        rows.append([_num(t), _num(v), i])
    return rows


def _num(x):
    s = '%.6f' % x
    s = s.rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def _tangent(keys, i):
    n = len(keys)
    if i <= 0 or i >= n - 1:
        return 0.0
    dt = keys[i + 1][0] - keys[i - 1][0]
    return (keys[i + 1][1] - keys[i - 1][1]) / dt if dt > EPS else 0.0


def lane_value(keys, t):
    """Value of a lane at t. keys sorted [(t, v, interp)]; interp of the left key shapes the segment."""
    if not keys:
        return 0.0
    if t < keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    # binary search for the segment [i, i+1] with t_i <= t < t_{i+1}
    lo, hi = 0, len(keys) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if keys[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    t0, v0, mode = keys[lo]
    t1, v1, _ = keys[hi]
    h = t1 - t0
    if h <= EPS:
        return v1
    u = (t - t0) / h
    if mode == 'hold':
        return v0
    if mode == 'linear':
        return v0 + (v1 - v0) * u
    if mode == 'ease':
        s = u * u * (3.0 - 2.0 * u)
        return v0 + (v1 - v0) * s
    # bezier-lite: cubic Hermite, Catmull-Rom tangents, flat at the ends
    m0, m1 = _tangent(keys, lo), _tangent(keys, hi)
    u2, u3 = u * u, u * u * u
    return ((2 * u3 - 3 * u2 + 1) * v0 + (u3 - 2 * u2 + u) * h * m0
            + (-2 * u3 + 3 * u2) * v1 + (u3 - u2) * h * m1)


def add_key(keys, t, v, interp='linear', eps=1e-4):
    """Insert a key (replace one within eps of t). Returns (new keys, index)."""
    interp = interp if interp in INTERPS else 'linear'
    ks = [k for k in keys if abs(k[0] - t) > eps]
    ks.append((t, v, interp))
    ks.sort(key=lambda k: k[0])
    return ks, ks.index((t, v, interp))


def delete_key(keys, idx):
    if 0 <= idx < len(keys):
        return keys[:idx] + keys[idx + 1:]
    return list(keys)


def move_key(keys, idx, t, v):
    """Move key idx to (t, v), keep its interp. Returns (new keys, new index)."""
    if not 0 <= idx < len(keys):
        return list(keys), -1
    interp = keys[idx][2]
    ks = keys[:idx] + keys[idx + 1:]
    ks.append((t, v, interp))
    ks.sort(key=lambda k: k[0])
    return ks, ks.index((t, v, interp))


def nearest_key(keys, t):
    if not keys:
        return -1
    return min(range(len(keys)), key=lambda i: abs(keys[i][0] - t))


def next_time(times, t, eps=1e-6):
    later = [x for x in times if x > t + eps]
    return min(later) if later else None


def prev_time(times, t, eps=1e-6):
    earlier = [x for x in times if x < t - eps]
    return max(earlier) if earlier else None


def parse_markers(rows):
    out = []
    for r in rows[1:] if rows and str(rows[0][0]).strip().lower() == 'time' else rows:
        if not r:
            continue
        try:
            t = float(r[0])
        except (TypeError, ValueError):
            continue
        out.append((t, str(r[1]) if len(r) > 1 else ''))
    out.sort(key=lambda m: m[0])
    return out


def marker_at(markers, t):
    """Name of the last marker at or before t ('' if none)."""
    name = ''
    for mt, mn in markers:
        if mt <= t + 1e-6:
            name = mn
        else:
            break
    return name


def parse_lanes(rows):
    """lanes table -> [{'name','op','par','min','max','enabled'}]; header row required."""
    if not rows:
        return []
    head = [str(c).strip().lower() for c in rows[0]]
    out = []
    for r in rows[1:]:
        d = {h: (r[i] if i < len(r) else '') for i, h in enumerate(head)}
        name = str(d.get('name', '')).strip()
        if not name:
            continue
        lo, hi = _f(d.get('min'), 0.0), _f(d.get('max'), 1.0)
        if hi == lo:
            hi = lo + 1.0
        en = str(d.get('enabled', '1')).strip().lower() not in ('0', 'false', 'off', 'no')
        out.append({'name': name, 'op': str(d.get('op', '')).strip(), 'par': str(d.get('par', '')).strip(),
                    'min': lo, 'max': hi, 'enabled': en})
    return out


def sample_curve(keys, length, n, vmin, vmax):
    """n samples over [0, length], normalised to 0..1 by vmin..vmax (for the view)."""
    span = (vmax - vmin) or 1.0
    if n <= 1:
        return [(lane_value(keys, 0.0) - vmin) / span]
    return [(lane_value(keys, length * i / (n - 1)) - vmin) / span for i in range(n)]


# ---------------------------------------------------------------- ruler view geometry (u right, v up, 0..1)
def lane_band(idx, nlanes):
    """(v_bottom, v_top) of lane idx (0 = top lane)."""
    nl = max(1, nlanes)
    h = (1.0 - RULER_FRAC) / nl
    top = 1.0 - RULER_FRAC - idx * h
    return top - h, top


def lane_at(v, nlanes):
    """-1 = ruler strip, 0..n-1 = lane, None = below/outside."""
    if v >= 1.0 - RULER_FRAC:
        return -1
    if nlanes <= 0 or v < 0:
        return None
    h = (1.0 - RULER_FRAC) / nlanes
    idx = int((1.0 - RULER_FRAC - v) / h)
    return idx if 0 <= idx < nlanes else None


def value_to_v(value, idx, nlanes, vmin, vmax):
    b, t = lane_band(idx, nlanes)
    pad = (t - b) * LANE_PAD
    span = (vmax - vmin) or 1.0
    return b + pad + (t - b - 2 * pad) * (value - vmin) / span


def v_to_value(v, idx, nlanes, vmin, vmax):
    b, t = lane_band(idx, nlanes)
    pad = (t - b) * LANE_PAD
    inner = max(t - b - 2 * pad, 1e-9)
    x = (v - b - pad) / inner
    x = min(max(x, 0.0), 1.0)
    return vmin + (vmax - vmin) * x


def u_to_time(u, length):
    return min(max(u, 0.0), 1.0) * length


def hit_key(keys, u, v, idx, nlanes, length, vmin, vmax, w, h, radius_px=8.0):
    """Index of the key under (u, v) in lane idx within radius_px pixels, else -1."""
    best, bd = -1, radius_px
    for i, (kt, kv, _) in enumerate(keys):
        ku = kt / length if length > 0 else 0.0
        kvv = value_to_v(kv, idx, nlanes, vmin, vmax)
        d = math.hypot((ku - u) * w, (kvv - v) * h)
        if d <= bd:
            best, bd = i, d
    return best
