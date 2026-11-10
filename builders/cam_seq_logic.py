"""cam_seq_logic: CS_cam_sequencer v2, a Camera COMP that stores and eases between camera presets (clean-room,
28 Oct 2026). Pure Python, no td import.

Research: docs/research/CS_camsequencer.md (public information only; no code, file or asset of the Function Store
product was used). How-to: docs/builds/cs_cam_sequencer.md. Tests: test/test_cam_seq.py.

v2 model (the original's workflow): the COMP IS the camera. A preset is the camera's own raw pars
(tx ty tz rx ry rz sx sy sz px py pz fov) plus the EASE that eases INTO it; the Look At object's transform
(tx..pz) is a SEPARATE preset table (same row order, not linked by moves). Select scrubs: integer = preset,
fraction = blend (segment i -> i+1 eased by preset i+1's EASE, the wrap N-1 -> 0 by preset 0's), Ease Override =
one curve for every segment, Spline Interpolation = a centripetal Catmull-Rom through the presets.

Ours on top: playmodes sequence / beat / random on a beat clock (quantised), any-to-any Go-to with its own blend
(never sweeps the presets in between), shake profiles, a global look target / effector, framing for portrait
frames, shortest-rotation option, Select lag.

LIFTS builders/cam_rig_logic.py (not rewritten): Director (seeded no-repeat draw + quantised holds), quant_up,
noise1, td_pars / pose (global target without a Look At op), vector helpers. Inside TD the rig module is the Text
DAT `cam_rig_logic` and is handed in with bind_rig(); offline it is imported from builders/. ASCII only.
"""
import math

try:
    import cam_rig_logic as R          # offline (builders/ on sys.path) and TD (sibling Text DAT of that name)
except Exception:                      # pragma: no cover - TD hands the module in with bind_rig()
    R = None

VERSION = 2


def bind_rig(mod):
    """TD: use this cam_rig_logic module (the COMP's Text DAT)."""
    global R
    R = mod
    return R


# ------------------------------------------------------------------------------------------------ easings (F4)
# easings.net closed forms (the standard Penner set). Names: in / out / inOut x 10 families.

FAMILIES = ('Sine', 'Quad', 'Cubic', 'Quart', 'Quint', 'Expo', 'Circ', 'Back', 'Elastic', 'Bounce')
_C1 = 1.70158
_C2 = _C1 * 1.525
_C3 = _C1 + 1.0
_C4 = 2.0 * math.pi / 3.0
_C5 = 2.0 * math.pi / 4.5


def _out_bounce(x):
    n1, d1 = 7.5625, 2.75
    if x < 1.0 / d1:
        return n1 * x * x
    if x < 2.0 / d1:
        x -= 1.5 / d1
        return n1 * x * x + 0.75
    if x < 2.5 / d1:
        x -= 2.25 / d1
        return n1 * x * x + 0.9375
    x -= 2.625 / d1
    return n1 * x * x + 0.984375


def _pw(n):
    return (lambda x: x ** n, lambda x: 1.0 - (1.0 - x) ** n,
            lambda x: (2.0 ** (n - 1)) * x ** n if x < 0.5 else 1.0 - (-2.0 * x + 2.0) ** n / 2.0)


_F = {
    'Sine': (lambda x: 1.0 - math.cos(x * math.pi / 2.0), lambda x: math.sin(x * math.pi / 2.0),
             lambda x: -(math.cos(math.pi * x) - 1.0) / 2.0),
    'Quad': _pw(2), 'Cubic': _pw(3), 'Quart': _pw(4), 'Quint': _pw(5),
    'Expo': (lambda x: 0.0 if x <= 0.0 else 2.0 ** (10.0 * x - 10.0),
             lambda x: 1.0 if x >= 1.0 else 1.0 - 2.0 ** (-10.0 * x),
             lambda x: 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else (2.0 ** (20.0 * x - 10.0) / 2.0 if x < 0.5 else
                                                                   (2.0 - 2.0 ** (-20.0 * x + 10.0)) / 2.0))),
    'Circ': (lambda x: 1.0 - math.sqrt(max(0.0, 1.0 - x * x)), lambda x: math.sqrt(max(0.0, 1.0 - (x - 1.0) ** 2)),
             lambda x: (1.0 - math.sqrt(max(0.0, 1.0 - (2.0 * x) ** 2))) / 2.0 if x < 0.5 else
             (math.sqrt(max(0.0, 1.0 - (-2.0 * x + 2.0) ** 2)) + 1.0) / 2.0),
    'Back': (lambda x: _C3 * x ** 3 - _C1 * x * x, lambda x: 1.0 + _C3 * (x - 1.0) ** 3 + _C1 * (x - 1.0) ** 2,
             lambda x: ((2.0 * x) ** 2 * ((_C2 + 1.0) * 2.0 * x - _C2)) / 2.0 if x < 0.5 else
             ((2.0 * x - 2.0) ** 2 * ((_C2 + 1.0) * (2.0 * x - 2.0) + _C2) + 2.0) / 2.0),
    'Elastic': (lambda x: 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else
                                                -(2.0 ** (10.0 * x - 10.0)) * math.sin((10.0 * x - 10.75) * _C4)),
                lambda x: 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else
                                                2.0 ** (-10.0 * x) * math.sin((10.0 * x - 0.75) * _C4) + 1.0),
                lambda x: 0.0 if x <= 0.0 else (1.0 if x >= 1.0 else (
                    -(2.0 ** (20.0 * x - 10.0) * math.sin((20.0 * x - 11.125) * _C5)) / 2.0 if x < 0.5 else
                    (2.0 ** (-20.0 * x + 10.0) * math.sin((20.0 * x - 11.125) * _C5)) / 2.0 + 1.0))),
    'Bounce': (lambda x: 1.0 - _out_bounce(1.0 - x), _out_bounce,
               lambda x: (1.0 - _out_bounce(1.0 - 2.0 * x)) / 2.0 if x < 0.5 else
               (1.0 + _out_bounce(2.0 * x - 1.0)) / 2.0),
}

PENNER = {}
for _fam in FAMILIES:
    for _k, _pre in enumerate(('in', 'out', 'inOut')):
        PENNER[_pre + _fam] = _F[_fam][_k]

EASE_NAMES = ['linear', 'smooth', 'smoother'] + [p + f for f in FAMILIES for p in ('in', 'out', 'inOut')] + ['custom']
EASE_LABELS = ['Linear', 'Smoothstep', 'Smootherstep'] + \
    ['%s %s' % ({'in': 'In', 'out': 'Out', 'inOut': 'In-out'}[p], f) for f in FAMILIES for p in ('in', 'out', 'inOut')] + \
    ['Custom (CHOP lookup)']
OVERSHOOT = set(n for n in EASE_NAMES if n.endswith(('Back', 'Elastic')))      # leave 0..1 on the way
LEGACY = {'in': 'inQuad', 'out': 'outQuad', 'sine': 'inOutSine', 'expo': 'inOutExpo', 'back': 'outBack'}


def lookup(samples, u):
    """Linear lookup of a sample list at u 0..1 (custom ease from a CHOP: first channel, any length)."""
    s = list(samples or ())
    if not s:
        return u
    if len(s) == 1:
        return float(s[0])
    x = min(1.0, max(0.0, u)) * (len(s) - 1)
    i = min(int(x), len(s) - 2)
    f = x - i
    return float(s[i]) + (float(s[i + 1]) - float(s[i])) * f


def ease(u, name='inOutSine', custom=None):
    """0..1 -> eased (input clamped; Back / Elastic leave 0..1 on the way). Unknown name = linear. The 8 names of
    cam_rig_logic keep working (smooth / smoother as there; in / out / sine / expo / back map to their Penner twins,
    `back` = outBack, the same curve as cam_rig_logic)."""
    u = min(1.0, max(0.0, float(u)))
    name = LEGACY.get(name, name)
    if name == 'smooth':
        return u * u * (3.0 - 2.0 * u)
    if name == 'smoother':
        return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)
    if name == 'custom':
        return lookup(custom, u) if custom else u
    f = PENNER.get(name)
    return f(u) if f is not None else u


# ------------------------------------------------------------------------------------------------ preset tables
# Two Table DATs: cam_presets (# EASE tx ty tz rx ry rz sx sy sz px py pz fov) and lookat_presets (# EASE tx..pz).
# '#' is the row number (rewritten on every save; "Sort #" in the pop-up reorders by it), EASE = the curve that
# eases INTO that preset (blank = the Easing par). Raw camera pars, as the camera's own parameter dialog shows them.

CAM_PARS = ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'px', 'py', 'pz', 'fov']
LOOK_PARS = CAM_PARS[:12]
ROT = (3, 4, 5)
DEFAULT_VAL = {'sx': 1.0, 'sy': 1.0, 'sz': 1.0, 'fov': 45.0}
NUM, EASECOL = '#', 'EASE'
PLAYMODES = ['manual', 'sequence', 'beat', 'random']
PLAYMODE_LABELS = ['Manual (Select)', 'Sequence (holds + transitions)', 'Beat (cuts on the grid)',
                   'Random (seeded, no repeat)']
LOOPMODES = ['loop', 'pingpong', 'once']
TRANS = ['cut', 'ease', 'arc']
TRANS_LABELS = ['Cut', 'Ease (straight)', 'Arc (swing about the look point)']
CLOCKS = ['internal', 'au', 'tl', 'chop', 'manual']
CLOCK_LABELS = ['Internal (Bpm)', 'AU_features beats', 'TL_timeline tl_beat', 'In CHOP beats', 'Manual (Seek)']
TARGETMODES = ['presets', 'op', 'effector']
TARGETMODE_LABELS = ['Look At presets', 'Global target op', 'Global target effector']


def default_vec(pars):
    return tuple(DEFAULT_VAL.get(n, 0.0) for n in pars)


def _f(x, d=0.0):
    try:
        s = str(x).strip()
        return float(s) if s != '' else d
    except (TypeError, ValueError):
        return d


def _vec3(x, d=(0.0, 0.0, 0.0)):
    try:
        return (float(x[0]), float(x[1]), float(x[2]))
    except Exception:
        return tuple(d)


def make_preset(vec, ease_name=''):
    return {'v': tuple(float(x) for x in vec), 'ease': str(ease_name or '').strip()}


def preset_rows(presets, pars):
    """Preset list -> table rows (header first). 9 significant digits (a table cell is text)."""
    rows = [[NUM, EASECOL] + list(pars)]
    for k, p in enumerate(presets):
        rows.append([str(k), p.get('ease', '')] + ['%.9g' % x for x in p['v']])
    return rows


def presets_from_rows(rows, pars):
    """Table rows -> preset list. Columns by header name (any order, extra columns ignored, missing ones take the
    par default: scale 1, fov 45, else 0). A row with no value cells is skipped; a bad cell never raises."""
    if not rows:
        return []
    head = [str(h).strip() for h in rows[0]]
    low = [h.lower() for h in head]
    col = dict((n, low.index(n.lower())) for n in pars if n.lower() in low)
    ecol = low.index('ease') if 'ease' in low else None
    dv = default_vec(pars)
    out = []
    for r in rows[1:]:
        cells = [str(x).strip() for x in r]
        if not any(cells[k] for k in col.values() if k < len(cells)):
            continue
        v = tuple(_f(cells[col[n]], dv[q]) if (n in col and col[n] < len(cells)) else dv[q]
                  for q, n in enumerate(pars))
        e = cells[ecol] if (ecol is not None and ecol < len(cells)) else ''
        out.append(make_preset(v, e))
    return out


def sort_rows_by_number(rows):
    """Pop-up "Sort #": rows reordered by their '#' cell (stable; a blank / bad '#' keeps its place), renumbered."""
    if not rows:
        return rows
    head = list(rows[0])
    k = head.index(NUM) if NUM in head else None
    body = [list(r) for r in rows[1:]]
    if k is None:
        return [head] + body
    keyed = [(_f(r[k], float(i)) if k < len(r) else float(i), i, r) for i, r in enumerate(body)]
    keyed.sort(key=lambda t: (t[0], t[1]))
    out = [head]
    for n, (_x, _i, r) in enumerate(keyed):
        r = list(r)
        if k < len(r):
            r[k] = str(n)
        out.append(r)
    return out


def edit(presets, kind, sel=None, vec=None, ease_name=''):
    """One table's edit (pure: returns (new list, selected index)). kind: init / append / insert (before sel) /
    replace (sel: new values AND the current ease, as the original's Replace) / remove / duplicate / moveup /
    movedown. vec = the captured values (init / append / insert / replace)."""
    sh = [dict(p) for p in presets]
    n = len(sh)
    i = sel if (sel is not None and 0 <= sel < n) else (n - 1 if n else None)
    if kind in ('init', 'append', 'insert', 'replace') and vec is None:
        raise ValueError('%s needs the captured values' % kind)
    if kind == 'init':
        return [make_preset(vec, ease_name)], 0
    if kind == 'append':
        sh.append(make_preset(vec, ease_name))
        return sh, len(sh) - 1
    if kind == 'insert':
        k = i if i is not None else 0
        sh.insert(k, make_preset(vec, ease_name))
        return sh, k
    if i is None:
        return sh, None
    if kind == 'replace':
        sh[i] = make_preset(vec, ease_name)
        return sh, i
    if kind == 'remove':
        sh.pop(i)
        return sh, (min(i, len(sh) - 1) if sh else None)
    if kind == 'duplicate':
        sh.insert(i + 1, dict(sh[i]))
        return sh, i + 1
    if kind == 'moveup':
        if i > 0:
            sh[i - 1], sh[i] = sh[i], sh[i - 1]
            return sh, i - 1
        return sh, i
    if kind == 'movedown':
        if i < n - 1:
            sh[i + 1], sh[i] = sh[i], sh[i + 1]
            return sh, i + 1
        return sh, i
    raise ValueError('unknown edit %r' % kind)


def edit_pair(cam, look, kind, sel=None, camv=None, lookv=None, ease_name=''):
    """The Seq page pulses (init / append / insert / replace / remove) on both tables at the same row, so row k of
    the Look At table belongs to camera preset k. lookv = the Look At op's values (None = no Look At op: its table
    keeps alignment with copies of the neighbouring row, or stays empty). When a Look At op is set for the first
    time after camera presets exist, the Look At table is padded with its current values first."""
    c2, s2 = edit(cam, kind, sel, camv, ease_name)
    look = [dict(p) for p in look]
    if kind == 'init':
        return c2, ([make_preset(lookv, ease_name)] if lookv is not None else []), s2
    if lookv is not None:
        while len(look) < len(cam):
            look.append(make_preset(lookv, ease_name))
        l2, _s = edit(look, kind, sel, lookv, ease_name)
        return c2, l2, s2
    if not look:
        return c2, look, s2
    n = len(look)
    i = sel if (sel is not None and 0 <= sel < n) else n - 1
    if kind == 'remove':
        if sel is not None and 0 <= sel < n:
            look.pop(sel)
        return c2, look, s2
    if kind == 'append':
        look.append(dict(look[-1]))
    elif kind == 'insert':
        look.insert(i, dict(look[i]))
    return c2, look, s2                                     # replace without a Look At op: its row stays


def select_parts(sel, n, loopmode='loop'):
    """Select value -> (i, j, f): segment from shot i to shot j at fraction f. loop: wraps (N-1 -> 0 is a real
    segment); pingpong: 0..N-1..0 over 2(N-1); once: clamped to 0..N-1. n 0 -> (None, None, 0); n 1 -> (0, 0, 0)."""
    if n <= 0:
        return None, None, 0.0
    if n == 1:
        return 0, 0, 0.0
    s = float(sel)
    if loopmode == 'pingpong':
        span = 2.0 * (n - 1)
        s = s % span
        if s > n - 1:
            s = span - s
            i = int(math.ceil(s - 1e-12))
            i = min(max(i, 1), n - 1)
            return i, i - 1, i - s
    elif loopmode == 'once':
        s = min(max(s, 0.0), float(n - 1))
        if s >= n - 1:
            return n - 2, n - 1, 1.0
    else:
        s = s % float(n)
    i = int(math.floor(s + 1e-12))
    f = s - i
    if f < 1e-12:
        f = 0.0
    if loopmode == 'once':
        return i, i + 1, f
    return i, (i + 1) % n, f


def selected(sel, n, loopmode='loop'):
    """The preset the Seq pulses act on: the one nearest to Select (None when there are none)."""
    if n <= 0:
        return None
    i, j, f = select_parts(sel, n, loopmode)
    return j if f >= 0.5 else i


# ------------------------------------------------------------------------------------------------ interpolation

def vlerp(a, b, e):
    return tuple(x + (y - x) * e for x, y in zip(a, b))


def wrap180(d):
    return (d + 180.0) % 360.0 - 180.0


def unwrap(a, b, rot=ROT):
    """b with its rotation channels moved by whole turns to within 180 deg of a (Shortrot)."""
    if a is None or b is None:
        return b
    b = list(b)
    for k in rot:
        if k < len(a) and k < len(b):
            b[k] = a[k] + wrap180(b[k] - a[k])
    return tuple(b)


def _dist3(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])))


def _knots(a, b, c, d, alpha=0.5):
    """Centripetal knot spacing from the POSITION channels (0..2) of the four presets; a segment with no move (rotation
    / fov only) gets 10 % of the largest spacing so the curve never folds."""
    ks = [_dist3(a, b) ** alpha, _dist3(b, c) ** alpha, _dist3(c, d) ** alpha]
    floor = max(max(ks) * 0.1, 1e-4)
    ks = [max(k, floor) for k in ks]
    return 0.0, ks[0], ks[0] + ks[1], ks[0] + ks[1] + ks[2]


def catmull(p0, p1, p2, p3, t, knots):
    """Barry-Goldman pyramid (non-uniform Catmull-Rom) on every channel; t 0 = p1, t 1 = p2."""
    t0, t1, t2, t3 = knots
    u = t1 + (t2 - t1) * t

    def L(a, b, ta, tb):
        w = (u - ta) / (tb - ta)
        return tuple(x * (1.0 - w) + y * w for x, y in zip(a, b))
    a1, a2, a3 = L(p0, p1, t0, t1), L(p1, p2, t1, t2), L(p2, p3, t2, t3)
    b1, b2 = L(a1, a2, t0, t2), L(a2, a3, t1, t3)
    return L(b1, b2, t1, t2)


def spline_vec(vecs, i, t, closed=True, tension=1.0, shortrot=False):
    """Value on the spline through `vecs` on segment i -> i+1 at t (0..1). closed: wraps (N-1 -> 0 is real);
    open: mirrored end points. tension 0..1 mixes the straight line (0) with the full spline (1)."""
    n = len(vecs)
    if n == 0:
        return None
    if n == 1:
        return tuple(vecs[0])
    if closed:
        i = i % n
        g = lambda k: tuple(vecs[k % n])
    else:
        i = min(max(i, 0), n - 2)
        g = lambda k: tuple(vecs[min(max(k, 0), n - 1)])
    a, b, c, d = g(i - 1), g(i), g(i + 1), g(i + 2)
    if not closed and i == 0:
        a = tuple(2.0 * x - y for x, y in zip(b, c))
    if not closed and i == n - 2:
        d = tuple(2.0 * x - y for x, y in zip(c, b))
    if shortrot:
        a, c = unwrap(b, a), unwrap(b, c)
        d = unwrap(c, d)
    sp = catmull(a, b, c, d, t, _knots(a, b, c, d))
    ln = vlerp(b, c, t)
    return vlerp(ln, sp, max(0.0, min(1.0, float(tension))))


def seg_ease(p_to, P):
    """The curve of a segment INTO preset p_to: its own EASE (blank = Easing) unless Ease Override (then Easing).
    Spline Interpolation without Override runs linear in time along the curve (one continuous move)."""
    override = bool(P.get('override'))
    ez = P.get('easing', 'inOutSine') if (override or not p_to.get('ease')) else p_to['ease']
    if P.get('splineinterp') and not override:
        ez = 'linear'
    return ez


def track_pose(presets, sel, P, custom=None):
    """(values, i, j, f) of one table at Select: segment preset i -> j at fraction f, eased INTO j."""
    n = len(presets)
    if n == 0:
        return None, None, None, 0.0
    lm = P.get('loopmode', 'loop')
    i, j, f = select_parts(sel, n, lm)
    vecs = [p['v'] for p in presets]
    if j == i or f == 0.0:
        return tuple(vecs[i]), i, j, f
    e = ease(f, seg_ease(presets[j], P), custom)
    sr = bool(P.get('shortrot'))
    if P.get('splineinterp'):
        tn = P.get('tension', 1.0)
        if (i + 1) % n == j:
            return spline_vec(vecs, i, e, lm == 'loop', tn, sr), i, j, f
        if (j + 1) % n == i:                                  # pingpong down: the same curve, reversed
            return spline_vec(vecs, j, 1.0 - e, lm == 'loop', tn, sr), i, j, f
    b = unwrap(vecs[i], vecs[j]) if sr else vecs[j]
    return vlerp(vecs[i], b, e), i, j, f


def arc_pos(p0, p1, l0, l1, e):
    """Camera position swinging about the (moving) look point: direction slerped, distance lerped."""
    c = vlerp(l0, l1, e)
    d0 = R.sub(p0, l0)
    d1 = R.sub(p1, l1)
    r0, r1 = R.length(d0), R.length(d1)
    if r0 < 1e-9 or r1 < 1e-9:
        return vlerp(p0, p1, e)
    n0, n1 = R.mul(d0, 1.0 / r0), R.mul(d1, 1.0 / r1)
    om = math.acos(max(-1.0, min(1.0, R.dot(n0, n1))))
    if om < 1e-6 or om > math.pi - 1e-4:
        return vlerp(p0, p1, e)
    s = math.sin(om)
    nd = R.add(R.mul(n0, math.sin((1.0 - e) * om) / s), R.mul(n1, math.sin(e * om) / s))
    return R.add(c, R.mul(nd, r0 + (r1 - r0) * e))


def blend_vecs(ac, bc, al, bl, e, mode='ease', shortrot=False):
    """Camera + look values between two states at an eased e (may leave 0..1: Back / Elastic overshoot by
    extrapolating). mode cut = the second state once e >= 0.5; arc = swing about the look point (needs both look
    states, else ease)."""
    if mode == 'cut':
        return (tuple(bc), bl) if e >= 0.5 else (tuple(ac), al)
    if shortrot:
        bc = unwrap(ac, bc)
        bl = unwrap(al, bl)
    cam = vlerp(ac, bc, e)
    look = vlerp(al, bl, e) if (al is not None and bl is not None) else (bl if bl is not None else al)
    if mode == 'arc' and al is not None and bl is not None:
        cam = tuple(arc_pos(ac[:3], bc[:3], al[:3], bl[:3], e)) + tuple(cam[3:])
    return cam, (tuple(look) if look is not None else None)


# ------------------------------------------------------------------------------------------------ shake profiles
# Layers per profile (Cinemachine-style noise profile, our numbers): (kind, hz, pos units, rot degrees, octaves).

PROFILES = {
    'off': [],
    'breath': [('noise', 0.25, 0.006, 0.25, 1)],
    'handheld': [('noise', 0.5, 0.012, 0.5, 1), ('noise', 1.2, 0.006, 0.3, 1), ('noise', 3.5, 0.002, 0.12, 1)],
    'walk': [('bob', 1.8, 0.03, 0.4, 1), ('noise', 0.6, 0.008, 0.3, 1)],
    'vehicle': [('noise', 9.0, 0.004, 0.15, 2), ('noise', 0.4, 0.004, 1.0, 1)],
    'quake': [('noise', 7.0, 0.05, 1.5, 2)],               # in bursts: decays over each beat (beat phase)
}
SHAKE_NAMES = ['off', 'breath', 'handheld', 'walk', 'vehicle', 'quake']
SHAKE_LABELS = ['Off', 'Breath (slow drift)', 'Handheld', 'Walk (bob + sway)', 'Vehicle (rumble + roll)',
                'Quake (bursts on the beat)']


def shake_bound(profile, amount=1.0, pscale=1.0, rscale=1.0):
    """Upper bound of the position offset (units, vector length) and of one rotation axis (deg) a profile adds."""
    pos = sum(l[2] for l in PROFILES.get(profile, [])) * amount * pscale
    rot = sum(l[3] for l in PROFILES.get(profile, [])) * amount * rscale
    return pos * math.sqrt(3.0), rot


def _n(t, freq, seed, k, octaves=1):
    s, a, f = 0.0, 1.0, freq
    o = max(1, int(octaves))
    for q in range(o):
        s += a * R.noise1(t * f, seed * 7 + k * 31 + q * 101)
        a *= 0.5
        f *= 2.0
    return s / (2.0 - 0.5 ** (o - 1))


def _side_axes(pos, point, up=(0.0, 1.0, 0.0)):
    f = R.norm(R.sub(point, pos))
    x = R.cross(f, up)
    x = R.norm(x, (1.0, 0.0, 0.0))
    return x, R.cross(x, f)


def shake_vec(cam, look, t, profile, amount=1.0, pscale=1.0, rscale=1.0, speed=1.0, seed=0, beat_phase=None,
              beat_kick=0.0, fov_scale=1.0):
    """Shake after the blend (noise never feeds the next preset). -> (cam, look, offset length).
    Position noise moves the camera and the look point together; rotation noise turns the aim: with a look point
    the point moves sideways by the angle at its distance (TD's Look At overrides the camera's aim; rz still rolls,
    probed live), without one it is added to rx / ry / rz."""
    layers = PROFILES.get(profile or 'off', [])
    env_b = math.exp(-6.0 * beat_phase) if beat_phase is not None else 0.0
    off, rot = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    a_all = float(amount) * float(fov_scale)
    if a_all > 0.0:
        for k, (kind, hz, pa, ra, octv) in enumerate(layers):
            a = a_all * (env_b if profile == 'quake' else 1.0)
            if a <= 0.0:
                continue
            sd = int(seed) * 13 + k
            if kind == 'bob':
                ph = 2.0 * math.pi * hz * speed * t
                off[1] += abs(math.sin(ph * 0.5)) * pa * pscale * a
                off[0] += math.sin(ph * 0.25) * pa * 0.5 * pscale * a
                rot[2] += math.sin(ph * 0.25) * ra * rscale * a
            else:
                tt = t * speed
                for ax in range(3):
                    off[ax] += _n(tt, hz, sd, ax, octv) * pa * pscale * a
                    rot[ax] += _n(tt, hz, sd, 3 + ax, octv) * ra * rscale * a
    if beat_kick > 0.0 and beat_phase is not None and env_b > 1e-4:
        sd = int(seed) * 13 + 97
        for ax in range(3):
            off[ax] += _n(t, 8.0, sd, ax) * 0.04 * beat_kick * env_b
            rot[ax] += _n(t, 8.0, sd, 3 + ax) * 1.2 * beat_kick * env_b
    c = list(cam)
    for ax in range(3):
        c[ax] += off[ax]
    lk = None
    if look is not None:
        lk = list(look)
        pt = R.add(_vec3(lk), tuple(off))
        x, y = _side_axes(tuple(c[:3]), pt)
        dist = R.length(R.sub(pt, tuple(c[:3])))
        pt = R.add(pt, R.add(R.mul(x, math.radians(rot[1]) * dist), R.mul(y, math.radians(rot[0]) * dist)))
        lk[0], lk[1], lk[2] = pt
        c[5] += rot[2]
        lk = tuple(lk)
    else:
        for ax in range(3):
            c[3 + ax] += rot[ax]
    return tuple(c), lk, R.length(tuple(off))


# ------------------------------------------------------------------------------------------------ look-at + framing

def frame_distance(radius, fov_h, resx, resy, pad=0.0):
    """Distance that fits a sphere of `radius` in the NARROWER frame angle (portrait 1080x1920: the horizontal fov;
    landscape: the vertical one, from fov_h and the aspect)."""
    th = math.tan(math.radians(max(1e-3, min(179.0, fov_h))) * 0.5)
    tv = th * float(resy) / max(float(resx), 1.0)
    half = math.atan(min(th, tv))
    return float(radius) * (1.0 + max(0.0, pad)) / max(math.sin(half), 1e-6)


def frame_cam(cam, point, radius, resx, resy, pad=0.0):
    """Keep the view direction, move the camera so `radius` around `point` fills the narrower angle."""
    d = frame_distance(radius, cam[12], resx, resy, pad)
    f = R.norm(R.sub(_vec3(point), _vec3(cam)))
    return tuple(R.sub(_vec3(point), R.mul(f, d))) + tuple(cam[3:])


def aim(cam, point, roll=0.0, order='xyz'):
    """rx ry rz that aim the camera at `point` (global target without a Look At op)."""
    v = R.td_pars(R.pose(_vec3(cam), _vec3(point), roll, cam[12]), order if order in R.ORDERS else 'xyz')
    return tuple(cam[:3]) + (v['rx'], v['ry'], v['rz']) + tuple(cam[6:])


def damp(prev, want, dt, tau):
    """Exponential smoothing of a point (tau seconds; 0 = locked)."""
    if prev is None or tau <= 0.0 or dt <= 0.0:
        return tuple(want)
    k = 1.0 - math.exp(-dt / tau)
    return R.lerp(prev, want, k)


# ------------------------------------------------------------------------------------------------ the engine

DEFAULTS = {
    'bind': True, 'playmode': 'manual', 'loopmode': 'loop', 'select': 0.0, 'override': False, 'easing': 'inOutSine',
    'trans': 'ease', 'splineinterp': False, 'tension': 1.0, 'shortrot': False, 'defaulthold': 8.0, 'tdur': 2.0,
    'quant': 4.0, 'gotoblend': 'arc', 'gototime': 1.0, 'gotoease': 'inOutSine', 'seed': 1, 'minhold': 4.0,
    'maxhold': 12.0, 'shakeprofile': 'off', 'shakeamount': 1.0, 'shakepos': 1.0, 'shakerot': 1.0, 'shakespeed': 1.0,
    'shakeseed': 0, 'shakebeat': 0.0, 'shakeperlens': False, 'fovoffset': 0.0, 'roll': 0.0, 'targetmode': 'presets',
    'lookdamp': 0.0, 'frame': False, 'framepad': 0.2, 'frameradius': 1.0, 'resx': 1080, 'resy': 1920, 'lag': 0.0,
    'bpm': 120.0, 'beatsperbar': 4, 'rord': 'xyz', 'haslook': False, 'targetpoint': None,
}


class Engine(object):
    """One camera state per frame. step(cam, look, P, beats, seconds, events, custom) -> (cam, look, info).

    cam / look = preset lists ({'v', 'ease'}); look may be empty. P = par values (DEFAULTS keys); P['haslook'] = a
    Look At op is set (the look values drive it); P['targetpoint'] = the global target's world point or None.
    events = [('goto', i)] / [('next',)] / [('prev',)] / [('random',)] / [('cut', i)]. cam None = no presets."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.seg = None
        self.k = 0
        self.dirn = 1
        self.pending = None
        self.goto = None
        self.sel_s = None
        self.look_s = None
        self.last = None           # (cam, look) before target / frame / shake
        self.last_t = None
        self.last_preset = None
        self.dir_cache = None
        self.dir_changed = False

    # -- schedule (sequence / beat / random)
    def _director(self, n, P):
        key = (n, P['playmode'], int(P['seed']), float(P['quant']), float(P['minhold']), float(P['maxhold']),
               float(P['defaulthold']), float(P['bpm']))
        if self.dir_cache is None or self.dir_cache[0] != key:
            mode = 'random' if P['playmode'] == 'random' else 'list'
            D = R.Director([dict(hold=float(P['defaulthold']))] * max(n, 1), mode, int(P['seed']),
                           max(float(P['quant']), 0.0),
                           min(float(P['minhold']), float(P['maxhold'])) if mode == 'random' else 0.0,
                           float(P['maxhold']), float(P['bpm']))
            self.dir_cache = (key, D)
            self.dir_changed = True
        return self.dir_cache[1]

    def _seg_len(self, D, i, start, k, P):
        h = D._len(i, k)
        q = float(P['quant'])
        end = R.quant_up(start + h, q) if q > 0 else start + h
        if end - start < 1e-6:
            end = start + (q if q > 0 else 1.0)
        return end - start

    def _next_index(self, D, i, n, P):
        if P['playmode'] == 'random':
            return D._next(self.k, i)
        lm = P['loopmode']
        if lm == 'pingpong' and n > 1:
            j = i + self.dirn
            if j < 0 or j >= n:
                self.dirn = -self.dirn
                j = i + self.dirn
            return j
        if lm == 'once':
            return min(i + 1, n - 1)
        return (i + 1) % n

    def _new_seg(self, D, i, start, P, cam, frm=None, fromi=None, styled=True):
        self.k += 1
        tr = P['trans'] if (styled and P['playmode'] != 'beat') else 'cut'
        if tr != 'cut' and P['splineinterp']:
            tr = 'spline'
        ln = self._seg_len(D, i, start, self.k, P)
        self.seg = {'i': i, 'start': start, 'len': ln, 'from': frm, 'fromi': fromi, 'k': self.k,
                    'tdur': min(max(float(P['tdur']), 0.0), ln), 'trans': tr, 'ease': seg_ease(cam[i], P)}

    @staticmethod
    def _at(cam, look, i):
        return tuple(cam[i]['v']), (tuple(look[i % len(look)]['v']) if look else None)

    def _sched(self, cam, look, P, beats, events, custom):
        n = len(cam)
        D = self._director(n, P)
        cut = False
        q = float(P['quant'])
        if self.dir_changed and self.seg is not None and self.seg['i'] < n and self.seg['len'] < 1e8:
            self.seg['len'] = self._seg_len(D, self.seg['i'], self.seg['start'], self.seg['k'], P)
            self.seg['tdur'] = min(self.seg['tdur'], self.seg['len'])
        self.dir_changed = False
        if self.seg is not None and (beats < self.seg['start'] - 1e-6 or self.seg['i'] >= n or
                                     beats > self.seg['start'] + self.seg['len'] + 256.0):
            self.seg = None                                   # clock jumped (seek / reset / new source): re-anchor
        if self.seg is None:
            start = math.floor(beats / q + 1e-9) * q if q > 0 else beats
            i0 = selected(P['select'], n, P['loopmode']) or 0
            self._new_seg(D, i0, start, P, cam, styled=False)
            cut = True
        for ev in events:
            if ev[0] in ('next', 'prev', 'random', 'cut'):
                at = R.quant_up(beats, q) if (q > 0 and ev[0] != 'cut') else beats
                self.pending = (at, ev[0], ev[1] if len(ev) > 1 else None)
        if self.pending is not None and beats >= self.pending[0] - 1e-9:
            at, kind, idx = self.pending
            self.pending = None
            cur = self.seg['i']
            j = {'next': (cur + 1) % n, 'prev': (cur - 1) % n}.get(kind)
            if kind == 'random':
                j = D._next(self.k + 7, cur) if n > 1 else 0
            elif kind == 'cut':
                j = idx if (idx is not None and 0 <= idx < n) else cur
            self._new_seg(D, j, at, P, cam, self.last, cur, styled=(kind != 'cut'))
            cut = True
        guard = 0
        while beats >= self.seg['start'] + self.seg['len'] - 1e-9 and guard < 64:
            guard += 1
            cur = self.seg['i']
            if P['loopmode'] == 'once' and P['playmode'] == 'sequence' and cur >= n - 1:
                self.seg['len'] = 1e9                         # once: hold the last preset
                break
            st = self.seg['start'] + self.seg['len']
            j = self._next_index(D, cur, n, P)
            self._new_seg(D, j, st, P, cam, self._at(cam, look, cur), cur)
            cut = True
        sg = self.seg
        lb = beats - sg['start']
        cv, lv = self._at(cam, look, sg['i'])
        prog = 1.0
        if sg['from'] is not None and sg['trans'] != 'cut' and sg['tdur'] > 0.0 and lb < sg['tdur']:
            prog = lb / sg['tdur']
            e = ease(prog, sg['ease'], custom)
            closed = P['loopmode'] != 'once'
            if sg['trans'] == 'spline' and sg['fromi'] is not None and (sg['fromi'] + 1) % n == sg['i']:
                cv = spline_vec([p['v'] for p in cam], sg['fromi'], e, closed, P['tension'], P['shortrot'])
                if look and len(look) == n:
                    lv = spline_vec([p['v'] for p in look], sg['fromi'], e, closed, P['tension'], P['shortrot'])
            else:
                mode = 'arc' if sg['trans'] in ('arc', 'spline') else 'ease'
                cv, lv = blend_vecs(sg['from'][0], cv, sg['from'][1], lv, e, mode, P['shortrot'])
        return cv, lv, sg['i'], prog, cut

    def goto_start(self, to, P, now):
        """Any-to-any: blend from the CURRENT output straight to preset `to` over Gototime beats (seconds by the
        bpm), Gotoblend cut / ease / arc. Never visits the presets in between."""
        dur = max(0.0, float(P['gototime'])) * 60.0 / max(float(P['bpm']), 1e-3)
        mode = P['gotoblend'] if P['gotoblend'] in TRANS else 'arc'
        if mode == 'cut':
            dur = 0.0
        self.goto = {'from': self.last, 'to': int(to), 't0': float(now), 'dur': dur, 'mode': mode,
                     'ease': P.get('gotoease') or P['easing'], 'sel': None}
        self.sel_s = float(to)

    def step(self, cam, look, P0, beats, secs, events=(), custom=None):
        P = dict(DEFAULTS)
        P.update(P0 or {})
        look = list(look or [])
        n = len(cam)
        dt = (secs - self.last_t) if self.last_t is not None else 0.0
        if dt < 0.0 or dt > 1.0:
            dt = 0.0
        info = {'preset': -1, 'select': float(P['select']), 'progress': 0.0, 'blend': 0.0, 'cut': 0.0, 'goto': 0.0,
                'beats': float(beats), 'needs_tick': False, 'shake': 0.0, 'dist': 0.0, 'bar': 0.0}
        if n == 0:
            self.last_t = secs
            return None, None, info
        evs = list(events or ())
        manual = P['playmode'] == 'manual'
        if manual:                                           # trig pulses in manual = any-to-any jumps
            cur_i = self.goto['to'] if self.goto is not None else selected(P['select'], n, P['loopmode'])
            m = []
            for ev in evs:
                if ev[0] == 'next':
                    m.append(('goto', (cur_i + 1) % n))
                elif ev[0] == 'prev':
                    m.append(('goto', (cur_i - 1) % n))
                elif ev[0] == 'random':
                    self.k += 1
                    m.append(('goto', self._director(n, dict(P, playmode='random'))._next(self.k, cur_i)
                              if n > 1 else 0))
                elif ev[0] == 'cut':
                    m.append(('goto', ev[1] if (len(ev) > 1 and ev[1] is not None) else cur_i))
                    P = dict(P, gotoblend='cut')
                else:
                    m.append(ev)
            evs = m
        for ev in evs:
            if ev[0] == 'goto' and ev[1] is not None and 0 <= ev[1] < n:
                self.goto_start(ev[1], P, secs)
                if not manual:
                    self._new_seg(self._director(n, P), ev[1], float(beats), P, cam, styled=False)
                info['cut'] = 1.0
        evs = [e for e in evs if e[0] != 'goto']
        if manual:
            sel = float(P['select'])
            if self.goto is not None:
                if self.goto['sel'] is None:
                    self.goto['sel'] = sel                    # Select as it stands when the jump starts
                elif abs(sel - self.goto['sel']) > 1e-9:
                    self.goto = None                          # the hand moved Select: it wins
                    self.sel_s = sel
            lag = float(P['lag'])
            if self.sel_s is None or lag <= 0.0:
                self.sel_s = sel
            elif dt > 0.0:
                self.sel_s += (sel - self.sel_s) * (1.0 - math.exp(-dt / lag))
            if lag > 0.0 and abs(sel - self.sel_s) > 1e-5:
                info['needs_tick'] = True
            elif lag > 0.0:
                self.sel_s = sel
            cv, i, j, f = track_pose(cam, self.sel_s, P, custom)
            lv = track_pose(look, self.sel_s, P, custom)[0] if look else None
            pi = i if (f < 0.5 or j == i) else j
            info.update(select=self.sel_s, progress=f, blend=1.0 if f > 0.0 else 0.0)
            if self.last_preset is not None and pi != self.last_preset:
                info['cut'] = 1.0
        else:
            cv, lv, pi, prog, cut = self._sched(cam, look, P, float(beats), evs, custom)
            info.update(progress=prog, blend=1.0 if prog < 1.0 else 0.0)
            if cut:
                info['cut'] = 1.0
            info['needs_tick'] = True
        if self.goto is not None:
            g = self.goto
            to = min(g['to'], n - 1)
            dc, dl = self._at(cam, look, to) if manual else (cv, lv)
            u = 1.0 if g['dur'] <= 0.0 else (secs - g['t0']) / g['dur']
            if g['from'] is None or u >= 1.0:
                self.goto = None
                cv, lv = dc, dl
            else:
                e = ease(max(0.0, u), g['ease'], custom)
                cv, lv = blend_vecs(g['from'][0], dc, g['from'][1], dl, e, g['mode'], P['shortrot'])
                info.update(goto=1.0, blend=1.0, progress=max(0.0, u))
                info['needs_tick'] = True
            pi = to
        info['preset'] = pi
        self.last_preset = pi
        self.last = (tuple(cv), tuple(lv) if lv is not None else None)
        self.last_t = secs
        return self._finish(cv, lv, P, secs, beats, info, dt)

    def _finish(self, cv, lv, P, secs, beats, info, dt):
        cam = tuple(cv)
        look = tuple(lv) if lv is not None else None
        tau = float(P['lookdamp'])
        point = None
        aimed = False
        tp = P.get('targetpoint')
        if P['targetmode'] in ('op', 'effector') and tp is not None:
            self.look_s = damp(self.look_s, _vec3(tp), dt, tau)
            point = tuple(self.look_s)
            info['needs_tick'] = True
            if P['haslook']:
                look = point + tuple((look or default_vec(LOOK_PARS))[3:])
            else:
                aimed = True
        elif look is not None and P['haslook']:
            if tau > 0.0:
                self.look_s = damp(self.look_s, look[:3], dt, tau)
                if R.length(R.sub(self.look_s, _vec3(look))) > 1e-5:
                    info['needs_tick'] = True
                look = tuple(self.look_s) + tuple(look[3:])
            else:
                self.look_s = _vec3(look)
            point = _vec3(look)
        if P['frame'] and point is not None:
            cam = frame_cam(cam, point, float(P['frameradius']), P['resx'], P['resy'], float(P['framepad']))
        c = list(cam)
        c[12] = min(170.0, max(1.0, c[12] + float(P['fovoffset'])))
        cam = tuple(c)
        if aimed:
            cam = aim(cam, point, float(P['roll']), P['rord'])
        else:
            c = list(cam)
            c[5] += float(P['roll'])
            cam = tuple(c)
        prof = P['shakeprofile']
        amt = float(P['shakeamount'])
        kick = float(P['shakebeat'])
        if (prof != 'off' and amt > 0.0) or kick > 0.0:
            fs = (cam[12] / 45.0) if P['shakeperlens'] else 1.0
            lk = look if P['haslook'] else None
            cam, lk2, info['shake'] = shake_vec(cam, lk, secs, prof, amt, float(P['shakepos']), float(P['shakerot']),
                                                float(P['shakespeed']), int(P['shakeseed']), float(beats) % 1.0, kick,
                                                fs)
            if lk2 is not None:
                look = lk2
            info['needs_tick'] = True
        if info['cut']:
            info['needs_tick'] = True                         # one more frame to put cs_cut back to 0
        info['dist'] = R.length(R.sub(point, _vec3(cam))) if point is not None else 0.0
        info['bar'] = math.floor(float(beats) / max(float(P.get('beatsperbar', 4)), 1.0))
        return cam, look, info


# ------------------------------------------------------------------------------------------------ Out CHOP contract

INFO_CHANS = ['select', 'preset', 'progress', 'blend', 'cut', 'goto', 'beats', 'bar', 'shake', 'dist', 'haslook',
              'ver']


def out_names():
    """cs_tx .. cs_fov (the camera), cs_la_tx .. cs_la_pz (the Look At op), then cs_select .. cs_ver."""
    return ['cs_' + n for n in CAM_PARS] + ['cs_la_' + n for n in LOOK_PARS] + ['cs_' + n for n in INFO_CHANS]


def out_values(cam, look, info, haslook=False, ver=0):
    c = list(cam) if cam is not None else list(default_vec(CAM_PARS))
    lk = list(look) if look is not None else list(default_vec(LOOK_PARS))
    return c + lk + [float(info.get('select', 0.0)), float(info.get('preset', -1)), float(info.get('progress', 0.0)),
                     float(info.get('blend', 0.0)), float(info.get('cut', 0.0)), float(info.get('goto', 0.0)),
                     float(info.get('beats', 0.0)), float(info.get('bar', 0.0)), float(info.get('shake', 0.0)),
                     float(info.get('dist', 0.0)), 1.0 if haslook else 0.0, float(ver)]


# ------------------------------------------------------------------------------------------------ v1 migration

def from_old_shots(rows, order='xyz', ease_default=''):
    """v1 `shots` table rows (name px py pz tx ty tz roll fov rig hold trans tdur ease ...) -> (cam presets, look
    presets). Position + target + roll -> the camera's tx..rz for `order` (so it aims right with NO Look At op),
    scale 1, pivot 0, fov; the target becomes the Look At preset (used once a Look At Null is set). Rig shots keep
    their stored pose only."""
    if not rows:
        return [], []
    head = [str(h).strip() for h in rows[0]]
    cam, look = [], []
    for r in rows[1:]:
        d = dict(zip(head, [str(x).strip() for x in r]))
        if not d.get('name'):
            continue
        pos = (_f(d.get('px')), _f(d.get('py')), _f(d.get('pz')))
        tgt = (_f(d.get('tx')), _f(d.get('ty')), _f(d.get('tz')))
        roll, fov = _f(d.get('roll')), _f(d.get('fov'), 45.0)
        e = d.get('ease', '')
        e = e if e in EASE_NAMES else ease_default
        v = R.td_pars(R.pose(pos, tgt, roll, fov), order if order in R.ORDERS else 'xyz')
        cam.append(make_preset((v['tx'], v['ty'], v['tz'], v['rx'], v['ry'], v['rz'], 1.0, 1.0, 1.0, 0.0, 0.0, 0.0,
                                v['fov']), e))
        look.append(make_preset(tgt + (0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0), e))
    return cam, look
