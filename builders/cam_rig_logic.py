"""cam_rig_logic: camera crane / dolly / orbit / path rigs, a view store, an auto director (cuts on beats, holds, eases),
shake, and the camera transform any COMP can bind (PX's Camera page K24, BL_splat_render's camera, previz, pointcloud).

Build plan 27 Oct (s2 "CAM_rig: NO COMP"): crane + director + view store are a few expressions, so this is pure Python
(no td import) plus a tiny binding helper (bind_exprs / apply_bind) that puts expressions on any Camera COMP. Research
FX7b TC-36 (exsstas Camera Crane: Heading / Pitch / Length arm looking at its base, clean-room; uisato procedural
camera that cuts to new angles and follows a body / hand). Doc docs/builds/cam_rig.md; tests test/test_cam_rig.py.

A camera POSE is a dict: pos (xyz), target (xyz, what it looks at), roll (degrees about the viewing axis, + = the
camera turns counter-clockwise about its own +Z, i.e. TD's local rz), fov (degrees, HORIZONTAL like px_logic.cam_viewproj
and TD's default `viewanglemethod` horizontal). Every rig returns a pose; poses blend (line or arc about the target);
shake is applied last. pose_matrix() is the camera's world matrix (columns = camera X right, Y up, Z back; TD cameras
look down their -Z); td_pars() turns it into tx ty tz rx ry rz for a Camera COMP's rotate order (default TD 'xyz').
Time: every function takes the time it needs (seconds and / or beats); the Director keeps only a schedule cache, so a
COMP may evaluate any frame in any order. ASCII only.
"""
import math
import random

VERSION = 1
EASES = [('linear', 'Linear'), ('smooth', 'Smoothstep'), ('smoother', 'Smootherstep'), ('in', 'Ease in (quad)'),
         ('out', 'Ease out (quad)'), ('sine', 'Ease in-out (sine)'), ('expo', 'Ease in-out (expo)'),
         ('back', 'Overshoot (back)')]
RIGS = [('view', 'Stored view'), ('orbit', 'Orbit'), ('crane', 'Crane (arm looking at its base)'),
        ('dolly', 'Dolly (line a -> b)'), ('path', 'Path (spline through points)'), ('follow', 'Follow a point')]
TRANS = [('cut', 'Cut'), ('ease', 'Ease (straight)'), ('arc', 'Ease (arc about the target)')]
DIRECTOR_MODES = [('list', 'Shot list in order (loops)'), ('random', 'Auto (random, never the same twice)')]
ORDERS = ('xyz', 'xzy', 'yxz', 'yzx', 'zxy', 'zyx')       # TD Camera COMP `rord`: rotate first about order[0]
UP = (0.0, 1.0, 0.0)
DEFAULT_POSE = {'pos': (0.0, 1.0, 5.0), 'target': (0.0, 1.0, 0.0), 'roll': 0.0, 'fov': 45.0}


def names(menu):
    return [m[0] for m in menu]


# ------------------------------------------------------------------------------------------------ small vector maths

def _v(a):
    return (float(a[0]), float(a[1]), float(a[2]))


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def norm(a, fb=(0.0, 0.0, -1.0)):
    n = length(a)
    return mul(a, 1.0 / n) if n > 1e-12 else tuple(fb)


def lerp(a, b, u):
    return tuple(a[k] + (b[k] - a[k]) * u for k in range(len(a)))


def _lerpf(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------------------------ eases

def ease(u, kind='smooth'):
    """0..1 -> 0..1 (clamped input). kind = EASES name or index."""
    if isinstance(kind, (int, float)) and not isinstance(kind, bool):
        kind = names(EASES)[int(kind)] if 0 <= int(kind) < len(EASES) else 'linear'
    u = min(1.0, max(0.0, float(u)))
    if kind == 'smooth':
        return u * u * (3.0 - 2.0 * u)
    if kind == 'smoother':
        return u * u * u * (u * (u * 6.0 - 15.0) + 10.0)
    if kind == 'in':
        return u * u
    if kind == 'out':
        return 1.0 - (1.0 - u) * (1.0 - u)
    if kind == 'sine':
        return 0.5 - 0.5 * math.cos(math.pi * u)
    if kind == 'expo':
        if u <= 0.0 or u >= 1.0:
            return u
        return 0.5 * 2.0 ** (20.0 * u - 10.0) if u < 0.5 else 1.0 - 0.5 * 2.0 ** (-20.0 * u + 10.0)
    if kind == 'back':                                  # overshoots ~10 % then settles (crane swing feel)
        c1 = 1.70158
        c3 = c1 + 1.0
        return 1.0 + c3 * (u - 1.0) ** 3 + c1 * (u - 1.0) ** 2
    return u


# ------------------------------------------------------------------------------------------------ poses + matrices

def pose(pos, target, roll=0.0, fov=45.0):
    return {'pos': _v(pos), 'target': _v(target), 'roll': float(roll), 'fov': float(fov)}


def axes(p, up=UP):
    """Camera axes (X right, Y up, Z back) of a pose in world space. Looking straight along `up` falls back to world
    -Z / +Z as the up hint (no NaN). Roll turns X / Y about the viewing axis (counter-clockwise seen from behind
    the camera = + about its own +Z)."""
    f = norm(sub(p['target'], p['pos']))
    u = _v(up)
    if length(cross(f, u)) < 1e-6:
        u = (0.0, 0.0, -1.0) if f[1] > 0.0 else (0.0, 0.0, 1.0)
    x = norm(cross(f, u), (1.0, 0.0, 0.0))
    y = cross(x, f)
    r = math.radians(p.get('roll', 0.0))
    if r:
        c, s = math.cos(r), math.sin(r)
        x, y = add(mul(x, c), mul(y, s)), add(mul(y, c), mul(x, -s))
    return x, y, mul(f, -1.0)


def rot3(p, up=UP):
    """3x3 rotation (rows), columns = the camera axes."""
    x, y, z = axes(p, up)
    return [[x[0], y[0], z[0]], [x[1], y[1], z[1]], [x[2], y[2], z[2]]]


def pose_matrix(p, up=UP):
    """4x4 world matrix (row-major, translation in column 3) of the camera: what a Camera COMP's worldTransform shows."""
    R = rot3(p, up)
    t = p['pos']
    return [R[0] + [t[0]], R[1] + [t[1]], R[2] + [t[2]], [0.0, 0.0, 0.0, 1.0]]


def view_matrix(p, up=UP):
    """World -> camera (inverse of pose_matrix)."""
    R = rot3(p, up)
    t = p['pos']
    rows = [[R[0][k], R[1][k], R[2][k]] for k in range(3)]                       # R^T
    return [r + [-(r[0] * t[0] + r[1] * t[1] + r[2] * t[2])] for r in rows] + [[0.0, 0.0, 0.0, 1.0]]


def proj_matrix(fov_deg, resx, resy, near=0.01, far=1000.0):
    """OpenGL projection with a HORIZONTAL fov (same as px_logic.cam_viewproj)."""
    fx = 1.0 / math.tan(math.radians(max(float(fov_deg), 1e-3)) * 0.5)
    fy = fx * float(resx) / max(float(resy), 1.0)
    n, f = float(near), float(far)
    return [[fx, 0.0, 0.0, 0.0], [0.0, fy, 0.0, 0.0], [0.0, 0.0, -(f + n) / (f - n), -2.0 * f * n / (f - n)],
            [0.0, 0.0, -1.0, 0.0]]


def matmul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(len(b))) for c in range(len(b[0]))] for r in range(len(a))]


def viewproj(p, resx, resy, near=0.01, far=1000.0, up=UP):
    """proj * view rows (clip = row . (p, 1)): the numbers a shader consumer needs without reading the Camera COMP
    back (PX rule: reading pcam back from the engine was a cook loop)."""
    return matmul(proj_matrix(p['fov'], resx, resy, near, far), view_matrix(p, up))


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]


_RF = {'x': _rx, 'y': _ry, 'z': _rz}


def matrix_from_euler(rx, ry, rz, order='xyz'):
    """3x3 of rotate order `order` (TD rord): rotate about order[0] first, then order[1], then order[2] (fixed world
    axes): R = R_order[2] . R_order[1] . R_order[0]. Degrees in."""
    ang = {'x': math.radians(rx), 'y': math.radians(ry), 'z': math.radians(rz)}
    R = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    for ax in order:
        R = matmul(_RF[ax](ang[ax]), R)
    return R


def euler_from_matrix(R, order='xyz'):
    """(rx, ry, rz) degrees with matrix_from_euler(rx, ry, rz, order) == R. Gimbal lock (middle angle +-90): the last
    angle is set to 0 and the first takes the whole turn (the matrix still round-trips)."""
    if order not in ORDERS:
        raise ValueError('rotate order %r (one of %s)' % (order, ' '.join(ORDERS)))
    i, j, k = ['xyz'.index(a) for a in order]
    s = 1.0 if order in ('xyz', 'yzx', 'zxy') else -1.0                 # cyclic orders vs the others
    sb = max(-1.0, min(1.0, -s * R[k][i]))
    b = math.asin(sb)
    if abs(sb) < 1.0 - 1e-9:
        a = math.atan2(s * R[k][j], R[k][k])
        c = math.atan2(s * R[j][i], R[i][i])
    else:                                                               # cos b = 0: only a - c (or a + c) is known
        c = 0.0
        a = math.atan2(-s * R[j][k], R[j][j])
    out = {order[0]: a, order[1]: b, order[2]: c}
    return tuple(math.degrees(out[ax]) for ax in 'xyz')


def td_pars(p, order='xyz', up=UP):
    """Pose -> Camera COMP values: tx ty tz rx ry rz (for rotate order `order`), fov. Scale 1, xord srt (TD default)."""
    rx, ry, rz = euler_from_matrix(rot3(p, up), order)
    return {'tx': p['pos'][0], 'ty': p['pos'][1], 'tz': p['pos'][2], 'rx': rx, 'ry': ry, 'rz': rz,
            'fov': p.get('fov', 45.0)}


# ------------------------------------------------------------------------------------------------ rigs

def orbit(centre=(0.0, 0.0, 0.0), radius=4.0, height=0.5, az_deg=0.0, look_offset=(0.0, 0.0, 0.0), roll=0.0,
          fov=45.0):
    """Camera on a horizontal circle (radius, height above the centre) at azimuth az (0 = +Z side, + = counter-
    clockwise seen from above), looking at centre + look_offset. Same convention as PX's orbit (pos x = r sin az)."""
    a = math.radians(az_deg)
    c = _v(centre)
    pos = (c[0] + radius * math.sin(a), c[1] + height, c[2] + radius * math.cos(a))
    return pose(pos, add(c, _v(look_offset)), roll, fov)


def orbit_at(t, centre=(0.0, 0.0, 0.0), radius=4.0, height=0.5, speed_deg=10.0, phase_deg=0.0, **kw):
    return orbit(centre, radius, height, phase_deg + speed_deg * t, **kw)


def crane(base=(0.0, 0.0, 0.0), heading=0.0, pitch=20.0, length=4.0, roll=0.0, look_offset=(0.0, 0.0, 0.0), fov=45.0):
    """exsstas-style crane (TC-36, clean-room): an arm of `length` from the base, swung by heading (degrees about Y,
    0 = +Z) and pitch (degrees above the horizon); the camera sits at the arm's end and always looks at the base
    (+ look_offset). Arcs instead of straight lines when heading / pitch are animated (LFO them)."""
    h, pt = math.radians(heading), math.radians(pitch)
    b = _v(base)
    arm = (math.cos(pt) * math.sin(h), math.sin(pt), math.cos(pt) * math.cos(h))
    return pose(add(b, mul(arm, length)), add(b, _v(look_offset)), roll, fov)


def dolly(a, b, u, target=None, ease_kind='smooth', roll=0.0, fov=45.0, look_dir=(0.0, 0.0, -1.0)):
    """Camera on the line a -> b at eased u (0..1). target = a point to keep looking at, or None = look along
    look_dir (a true dolly / truck: the view direction stays)."""
    e = ease(u, ease_kind)
    p = lerp(_v(a), _v(b), e)
    tgt = _v(target) if target is not None else add(p, norm(_v(look_dir)))
    return pose(p, tgt, roll, fov)


def _cr(p0, p1, p2, p3, t):
    """Uniform Catmull-Rom between p1 and p2."""
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * (2.0 * p1[k] + (-p0[k] + p2[k]) * t + (2.0 * p0[k] - 5.0 * p1[k] + 4.0 * p2[k] - p3[k]) * t2 +
                        (-p0[k] + 3.0 * p1[k] - 3.0 * p2[k] + p3[k]) * t3) for k in range(3))


def spline_raw(points, s, closed=False):
    """Point at segment parameter s in [0, n_segments] (Catmull-Rom through every point; ends repeat)."""
    pts = [_v(x) for x in points]
    n = len(pts)
    if n == 0:
        return (0.0, 0.0, 0.0)
    if n == 1:
        return pts[0]
    segs = n if closed else n - 1
    s = min(max(s, 0.0), float(segs)) if not closed else s % float(segs)
    i = min(int(math.floor(s)), segs - 1)
    f = s - i
    g = (lambda q: pts[q % n]) if closed else (lambda q: pts[min(max(q, 0), n - 1)])
    return _cr(g(i - 1), g(i), g(i + 1), g(i + 2), f)


class Path(object):
    """Camera path through points (Catmull-Rom), evaluated by ARC LENGTH so the speed is even (a table of `samples`
    per segment). at(u) for u 0..1 (closed: wraps)."""

    def __init__(self, points, closed=False, samples=32):
        self.points = [_v(x) for x in points]
        self.closed = bool(closed) and len(self.points) > 2
        n = len(self.points)
        segs = (n if self.closed else n - 1) if n > 1 else 0
        self.segs = segs
        self.s_tab, self.l_tab = [0.0], [0.0]
        prev = spline_raw(self.points, 0.0, self.closed)
        tot = 0.0
        for k in range(1, segs * samples + 1):
            s = k / float(samples)
            q = spline_raw(self.points, s, self.closed)
            tot += length(sub(q, prev))
            prev = q
            self.s_tab.append(s)
            self.l_tab.append(tot)
        self.length = tot

    def s_of(self, u):
        if self.segs == 0 or self.length <= 0.0:
            return 0.0
        u = (u % 1.0) if self.closed else min(max(u, 0.0), 1.0)
        L = u * self.length
        lo, hi = 0, len(self.l_tab) - 1
        while hi - lo > 1:
            m = (lo + hi) // 2
            if self.l_tab[m] <= L:
                lo = m
            else:
                hi = m
        d = self.l_tab[hi] - self.l_tab[lo]
        f = (L - self.l_tab[lo]) / d if d > 0.0 else 0.0
        return self.s_tab[lo] + (self.s_tab[hi] - self.s_tab[lo]) * f

    def at(self, u):
        return spline_raw(self.points, self.s_of(u), self.closed)

    def tangent(self, u, eps=1e-3):
        a, b = self.at(u - eps), self.at(u + eps)
        if not self.closed and (u - eps < 0.0 or u + eps > 1.0):
            a, b = self.at(max(0.0, u - eps)), self.at(min(1.0, u + eps))
        return norm(sub(b, a))


def path_pose(path, u, target=None, ahead=0.05, roll=0.0, fov=45.0, bank=0.0):
    """Pose on a Path at u. target: a point = look at it; None = look ahead along the path (`ahead` of the path,
    in u); bank (degrees per unit of turn) adds roll in curves."""
    p = path.at(u)
    if target is not None:
        return pose(p, target, roll, fov)
    tgt = path.at(u + ahead) if (path.closed or u + ahead <= 1.0) else add(p, path.tangent(u))
    if length(sub(tgt, p)) < 1e-9:
        tgt = add(p, path.tangent(u))
    r = roll
    if bank:
        t0, t1 = path.tangent(u - ahead * 0.5), path.tangent(u + ahead * 0.5)
        r += bank * cross(t0, t1)[1]                                           # signed turn about world up
    return pose(p, tgt, r, fov)


def follow(prev, target_point, offset=(0.0, 1.0, 4.0), lag=0.4, dt=1.0 / 60.0, roll=0.0, fov=45.0,
           look_lag=0.15):
    """Follow cam: the camera wants to sit at target + offset and look at the target; it reaches them with an
    exponential lag (seconds; 0 = locked). prev = last pose (None = jump). dt = seconds since prev."""
    tp = _v(target_point)
    want_pos, want_tgt = add(tp, _v(offset)), tp
    if prev is None or dt <= 0.0:
        return pose(want_pos, want_tgt, roll, fov)
    kp = 1.0 if lag <= 0.0 else 1.0 - math.exp(-dt / lag)
    kt = 1.0 if look_lag <= 0.0 else 1.0 - math.exp(-dt / look_lag)
    return pose(lerp(prev['pos'], want_pos, kp), lerp(prev['target'], want_tgt, kt), roll, fov)


# ------------------------------------------------------------------------------------------------ shake + blend

def _hash(i, seed):
    v = math.sin((i + seed * 101.0) * 127.1 + seed * 13.7) * 43758.5453
    return (v - math.floor(v)) * 2.0 - 1.0


def noise1(x, seed=0):
    """Smooth value noise in -1..1 (deterministic)."""
    i = math.floor(x)
    f = x - i
    u = f * f * (3.0 - 2.0 * f)
    return _hash(i, seed) * (1.0 - u) + _hash(i + 1, seed) * u


def shake(p, t, amp=0.0, rot_deg=0.0, freq=6.0, seed=0, octaves=2):
    """Handheld / impact shake: position jitter (amp, world units), aim jitter (rot_deg: the target moves by the
    matching angle at its distance) and roll jitter, smooth noise at freq Hz. amp = rot = 0 -> p unchanged."""
    if amp == 0.0 and rot_deg == 0.0:
        return dict(p)

    def n(k):
        s, a, f = 0.0, 1.0, freq
        for o in range(max(1, int(octaves))):
            s += a * noise1(t * f, seed * 7 + k * 31 + o * 101)
            a *= 0.5
            f *= 2.0
        return s / (2.0 - 0.5 ** (max(1, int(octaves)) - 1))
    off = (n(0) * amp, n(1) * amp, n(2) * amp)
    x, y, _z = axes(p)
    dist = length(sub(p['target'], p['pos']))
    ang = math.radians(rot_deg) * dist
    toff = add(mul(x, n(3) * ang), mul(y, n(4) * ang))
    q = dict(p)
    q['pos'] = add(p['pos'], off)
    q['target'] = add(add(p['target'], off), toff)
    q['roll'] = p['roll'] + n(5) * rot_deg
    return q


def blend(p0, p1, u, mode='ease', ease_kind='smooth'):
    """Pose between p0 and p1 at u (0..1, eased by ease_kind). mode 'cut' = p1 at u > 0; 'ease' = straight line;
    'arc' = swing around the (blended) target: distance and direction to the target interpolate separately, so the
    camera flies on an arc and keeps looking at what it frames."""
    if mode == 'cut':
        return dict(p1) if u > 0.0 else dict(p0)
    e = ease(u, ease_kind)
    tgt = lerp(p0['target'], p1['target'], e)
    if mode == 'arc':
        d0, d1 = sub(p0['pos'], p0['target']), sub(p1['pos'], p1['target'])
        l0, l1 = length(d0), length(d1)
        n0, n1 = norm(d0, (0.0, 0.0, 1.0)), norm(d1, (0.0, 0.0, 1.0))
        c = max(-1.0, min(1.0, dot(n0, n1)))
        om = math.acos(c)
        if om < 1e-6:
            dirv = n1
        elif om > math.pi - 1e-4:                                     # opposite sides: go over the top
            mid = norm(add(cross(n0, (1.0, 0.0, 0.0)), (0.0, 1e-3, 0.0)), (0.0, 1.0, 0.0))
            if abs(dot(mid, n0)) > 0.9:
                mid = (0.0, 1.0, 0.0)
            dirv = norm(lerp(lerp(n0, mid, e), lerp(mid, n1, e), e))
        else:
            s = math.sin(om)
            dirv = add(mul(n0, math.sin((1.0 - e) * om) / s), mul(n1, math.sin(e * om) / s))
        pos = add(tgt, mul(dirv, _lerpf(l0, l1, e)))
    else:
        pos = lerp(p0['pos'], p1['pos'], e)
    return {'pos': pos, 'target': tgt, 'roll': _lerpf(p0['roll'], p1['roll'], e),
            'fov': _lerpf(p0['fov'], p1['fov'], e)}


# ------------------------------------------------------------------------------------------------ view store

class Views(object):
    """Named stored views (poses). store / get / names / fly(a, b, u, mode). to_rows / from_rows = a Table DAT
    (name tx ty tz px py pz roll fov: position, target, roll, fov) so views survive in the .toe."""
    COLS = ['name', 'px', 'py', 'pz', 'tx', 'ty', 'tz', 'roll', 'fov']

    def __init__(self, views=None):
        self.v = dict((k, dict(p)) for k, p in (views or {}).items())
        self.order = list((views or {}).keys())

    def store(self, name, p):
        if name not in self.v:
            self.order.append(name)
        self.v[name] = pose(p['pos'], p['target'], p.get('roll', 0.0), p.get('fov', 45.0))
        return name

    def get(self, name):
        return dict(self.v.get(name, DEFAULT_POSE))

    def names(self):
        return list(self.order)

    def remove(self, name):
        self.v.pop(name, None)
        self.order = [n for n in self.order if n != name]

    def fly(self, a, b, u, mode='arc', ease_kind='smooth'):
        return blend(self.get(a), self.get(b), u, mode, ease_kind)

    def to_rows(self):
        out = [list(self.COLS)]
        for n in self.order:
            p = self.v[n]
            out.append([n] + ['%.6g' % x for x in p['pos'] + p['target']] + ['%.6g' % p['roll'], '%.6g' % p['fov']])
        return out

    @classmethod
    def from_rows(cls, rows):
        vs = cls()
        if not rows:
            return vs
        head = [str(h).strip() for h in rows[0]]
        for r in rows[1:]:
            d = dict(zip(head, r))
            nm = str(d.get('name', '')).strip()
            if not nm:
                continue
            f = lambda k, df=0.0: float(d.get(k, df)) if str(d.get(k, '')).strip() != '' else df
            vs.store(nm, pose((f('px'), f('py'), f('pz')), (f('tx'), f('ty'), f('tz')), f('roll'), f('fov', 45.0)))
        return vs


# ------------------------------------------------------------------------------------------------ shots + director

def shot(rig='view', hold=8.0, trans='cut', tdur=2.0, ease_kind='smooth', **params):
    """A shot: rig (RIGS name) + its params, hold (beats, the time it stays on), transition INTO it (TRANS name)
    with its duration (beats), ease. Params by rig:
      view:   name (a Views name) or pose (dict)
      orbit:  centre, radius, height, speed_deg (per second), phase_deg, look_offset
      crane:  base, heading, pitch, length, look_offset; animated by heading_speed / pitch_amp / pitch_freq / length_amp
      dolly:  a, b, target (None = look_dir), look_dir; the move runs over the shot's hold
      path:   points, closed, target, ahead, bank, loops (path turns per shot hold)
      follow: offset, lag (target = the follow point given to Director.at)
    roll / fov may be given to any rig."""
    d = {'rig': rig, 'hold': float(hold), 'trans': trans, 'tdur': float(tdur), 'ease': ease_kind}
    d.update(params)
    return d


def shot_pose(s, local_beats, local_sec, views=None, follow_point=None, prev=None, dt=0.0):
    """Pose of shot s at its local time (beats and seconds since the shot started)."""
    rig = s.get('rig', 'view')
    roll, fov = float(s.get('roll', 0.0)), float(s.get('fov', 45.0))
    hold = max(float(s.get('hold', 1.0)), 1e-6)
    if rig == 'view':
        p = dict(s['pose']) if 'pose' in s else (views.get(s.get('name', '')) if views is not None else
                                                  dict(DEFAULT_POSE))
        if 'roll' in s:
            p['roll'] = roll
        if 'fov' in s:
            p['fov'] = fov
        return p
    if rig == 'orbit':
        return orbit_at(local_sec, s.get('centre', (0.0, 0.0, 0.0)), s.get('radius', 4.0), s.get('height', 0.5),
                        s.get('speed_deg', 10.0), s.get('phase_deg', 0.0), look_offset=s.get('look_offset',
                                                                                              (0.0, 0.0, 0.0)),
                        roll=roll, fov=fov)
    if rig == 'crane':
        h = s.get('heading', 0.0) + s.get('heading_speed', 0.0) * local_sec
        pt = s.get('pitch', 20.0) + s.get('pitch_amp', 0.0) * math.sin(2.0 * math.pi * s.get('pitch_freq', 0.1) *
                                                                         local_sec)
        ln = s.get('length', 4.0) + s.get('length_amp', 0.0) * math.sin(2.0 * math.pi * s.get('pitch_freq', 0.1) *
                                                                          local_sec * 0.5)
        return crane(s.get('base', (0.0, 0.0, 0.0)), h, pt, ln, roll, s.get('look_offset', (0.0, 0.0, 0.0)), fov)
    if rig == 'dolly':
        return dolly(s.get('a', (0.0, 1.0, 6.0)), s.get('b', (0.0, 1.0, 3.0)), local_beats / hold, s.get('target'),
                     s.get('ease', 'smooth'), roll, fov, s.get('look_dir', (0.0, 0.0, -1.0)))
    if rig == 'path':
        pa = s.get('_path')
        if pa is None:
            pa = s['_path'] = Path(s.get('points', [(0.0, 1.0, 5.0), (3.0, 1.0, 0.0)]), s.get('closed', False))
        u = local_beats / hold * float(s.get('loops', 1.0))
        return path_pose(pa, u, s.get('target'), s.get('ahead', 0.05), roll, fov, s.get('bank', 0.0))
    if rig == 'follow':
        fp = follow_point if follow_point is not None else s.get('point', (0.0, 0.0, 0.0))
        return follow(prev, fp, s.get('offset', (0.0, 1.0, 4.0)), s.get('lag', 0.4), dt, roll, fov,
                      s.get('look_lag', 0.15))
    raise ValueError('unknown rig %r (%s)' % (rig, ' '.join(names(RIGS))))


def quant_up(x, q):
    """x rounded UP to a multiple of q (beats); q <= 0 = no quantisation."""
    if q <= 0:
        return x
    return math.ceil(x / q - 1e-9) * q


class Director(object):
    """Shot list -> a schedule of segments (shot index, start beat, length beats) and the pose at any beat.
    mode 'list': the shots in order, looping; 'random': the next shot is drawn (seeded) from the others, never the
    same twice in a row, hold drawn in [min_hold, max_hold]. Every cut lands on a multiple of `quant` beats (1 = beat,
    4 = bar) and no shot lasts less than min_hold. Transition INTO a segment (its shot's trans / tdur) starts at the
    cut: the previous shot keeps moving while the new one eases in (tdur clamped to the segment length).
    bpm converts beats to seconds for the moving rigs (seconds = beats * 60 / bpm) when no seconds clock is given."""

    def __init__(self, shots, mode='list', seed=1, quant=1.0, min_hold=1.0, max_hold=16.0, bpm=120.0, views=None):
        if not shots:
            raise ValueError('a director needs at least one shot')
        self.shots = [dict(s) for s in shots]
        self.mode, self.seed = mode, int(seed)
        self.quant, self.min_hold, self.max_hold = float(quant), float(min_hold), float(max(max_hold, min_hold))
        self.bpm = float(bpm)
        self.views = views
        self.sched = []              # (shot index, start beat, length beats)
        self._prev = None
        self._prev_t = None

    def _len(self, i, k):
        if self.mode == 'random':
            rng = random.Random(self.seed * 1000003 + k * 7919)
            h = self.min_hold + (self.max_hold - self.min_hold) * rng.random()
        else:
            h = self.shots[i].get('hold', 8.0)
        return max(quant_up(max(h, self.min_hold), self.quant), self.quant if self.quant > 0 else 1e-6)

    def _next(self, k, prev_i):
        n = len(self.shots)
        if self.mode != 'random':
            return k % n
        if n == 1:
            return 0
        rng = random.Random(self.seed * 7368787 + k * 104729)
        j = rng.randrange(n - 1)
        return j if prev_i is None or j < prev_i else j + 1               # never the same shot twice in a row

    def ensure(self, beats):
        """Schedule covers [0, beats]."""
        while not self.sched or self.sched[-1][1] + self.sched[-1][2] <= beats:
            k = len(self.sched)
            prev_i = self.sched[-1][0] if self.sched else None
            i = self._next(k, prev_i)
            start = self.sched[-1][1] + self.sched[-1][2] if self.sched else 0.0
            self.sched.append((i, start, self._len(i, k)))
            if len(self.sched) > 1000000:
                raise RuntimeError('schedule too long')
        return self.sched

    def segment(self, beats):
        """(k, shot index, start beat, length) of the segment holding `beats` (negative beats = segment 0)."""
        b = max(0.0, float(beats))
        self.ensure(b)
        lo, hi = 0, len(self.sched) - 1
        while lo < hi:
            m = (lo + hi + 1) // 2
            if self.sched[m][1] <= b:
                lo = m
            else:
                hi = m - 1
        i, st, ln = self.sched[lo]
        return lo, i, st, ln

    def cuts(self, b0, b1):
        """Beats where a new segment starts in (b0, b1]."""
        self.ensure(b1)
        return [s[1] for s in self.sched if b0 < s[1] <= b1]

    def at(self, beats, seconds=None, follow_point=None, dt=None):
        """Pose at `beats` (and seconds; None = beats * 60 / bpm). Returns (pose, info) with info = segment k, shot
        index, local beats, transition progress (1 = done)."""
        spb = 60.0 / max(self.bpm, 1e-6)
        sec = beats * spb if seconds is None else float(seconds)
        k, i, st, ln = self.segment(beats)
        s = self.shots[i]
        lb = max(0.0, beats - st)
        if dt is None:
            dt = (sec - self._prev_t) if self._prev_t is not None else 0.0
        cur = shot_pose(s, lb, lb * spb, self.views, follow_point, self._prev, dt)
        prog = 1.0
        if k > 0 and s.get('trans', 'cut') != 'cut':
            td = min(max(float(s.get('tdur', 0.0)), 0.0), ln)
            if td > 0.0 and lb < td:
                pi, pst, _pln = self.sched[k - 1][0], self.sched[k - 1][1], self.sched[k - 1][2]
                ps = self.shots[pi]
                plb = beats - pst
                old = shot_pose(ps, plb, plb * spb, self.views, follow_point, self._prev, dt)
                prog = lb / td
                cur = blend(old, cur, prog, s.get('trans', 'ease'), s.get('ease', 'smooth'))
        self._prev, self._prev_t = cur, sec
        return cur, {'segment': k, 'shot': i, 'local': lb, 'progress': prog, 'start': st, 'length': ln}


# ------------------------------------------------------------------------------------------------ TD binding (tiny)

BIND_PARS = ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'fov')


def bind_exprs(module_expr, clock_expr='absTime.seconds', order_expr="me.par.rord.eval()"):
    """Expressions for a Camera COMP's pars: each calls `<module_expr>.cam_par(<clock>, <rord>, '<par>')`, where
    module_expr is a Text DAT module that defines cam_par(t, order, name) (pose once per t, cached). The clock is
    read IN the expression (a time dependency only counts when the expression itself reads absTime / a CHOP, T-113)."""
    return dict((n, "%s.cam_par(%s, %s, %r)" % (module_expr, clock_expr, order_expr, n)) for n in BIND_PARS)


def apply_bind(cam, exprs, parmode):
    """Put bind_exprs() on a Camera COMP (parmode = TD's ParMode). Returns the pars set. fov only when the camera
    has a `fov` par (TD Camera COMP: yes)."""
    done = []
    for n, e in exprs.items():
        p = getattr(cam.par, n, None)
        if p is None:
            continue
        if p.mode != parmode.EXPRESSION or p.expr != e:
            p.expr = e
            p.mode = parmode.EXPRESSION
        done.append(n)
    return done


class Memo(object):
    """Pose cache for a binding module: cam_par(t, order, name) computes the pose once per (t, order)."""

    def __init__(self, fn):
        self.fn = fn                  # fn(t) -> pose
        self.key = None
        self.vals = None

    def cam_par(self, t, order, name):
        key = (float(t), str(order))
        if key != self.key:
            self.vals = td_pars(self.fn(float(t)), order if order in ORDERS else 'xyz')
            self.key = key
        return self.vals[name]
