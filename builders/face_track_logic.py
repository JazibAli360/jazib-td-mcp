"""face_track pure logic (no TD, stdlib only): parse the vision bridge's landmarks answer (kind 5), keep stable face
slots, One-Euro smoothing, hold-on-loss, measures (eye / mouth openness, smile, roll, yaw, pitch, centre, size), the
named CHOP channels, and the polygon / segment lists the mask and wire shaders read.

Copied verbatim into the COMP's `face_track_logic` Text DAT by builders/face_track.py, so the COMP stands alone.
Tests: test/test_face_track.py. Helper and wire format: helpers/vision_bridge/README.md.

Coordinates: everything here is IMAGE space normalized 0..1 with origin TOP-LEFT (y down), unless a name says `uv`
(origin bottom-left, as GLSL / TD textures). The helper sends origin bottom-left; parse_landmarks flips once.
"""
import json
import math
import struct

KIND_LANDMARKS = 5
HEAD = 9  # x y w h roll yaw pitch conf lmconf
# Region order = the helper's order (src/jzb_vision_bridge.mm RegionKeys). Vision's left/right are kept as sent:
# measured 26 Oct, Vision's leftEye is the eye on the IMAGE's left (the subject's right eye on an unmirrored camera).
REGIONS = ('jaw', 'brow_l', 'brow_r', 'eye_l', 'eye_r', 'pupil_l', 'pupil_r', 'nose', 'nosecrest', 'median',
           'lips_outer', 'lips_inner')
# Point counts of Vision's constellation 76 (revision 3) as measured through the helper on macOS 27.0 (26 Oct 2026):
# 87 points (76 + the two pupils + ...: Vision's own split). The CHOP always carries these so channel names never
# change between frames.
MAX_SLOTS = 32  # faces tracked at most (user 26 Oct: no hard cap of 8; Maxfaces par picks how many)

DEFAULT_COUNTS = {'jaw': 17, 'brow_l': 6, 'brow_r': 6, 'eye_l': 6, 'eye_r': 6, 'pupil_l': 1, 'pupil_r': 1, 'nose': 8,
                  'nosecrest': 6, 'median': 10, 'lips_outer': 14, 'lips_inner': 6}
CLOSED = ('eye_l', 'eye_r', 'lips_outer', 'lips_inner', 'nose')  # drawn as loops in the wire
MASK_FACE, MASK_EYES, MASK_MOUTH = 0, 1, 2
CTL_NAMES = ('present', 'slot_id', 'conf', 'x', 'y', 'w', 'h', 'cx', 'cy', 'size', 'roll', 'roll_vision', 'yaw', 'pitch',
             'eye_open_l', 'eye_open_r', 'eye_l_raw', 'eye_r_raw', 'mouth_open', 'mouth_raw', 'smile')


def _finite(v):
    return v is not None and isinstance(v, (int, float)) and math.isfinite(v)


# ------------------------------------------------------------------------------------------------ parsing
def parse_layout(text):
    """[(region, count), ...] from the answer's text JSON; DEFAULT_COUNTS order when empty/bad."""
    try:
        regs = json.loads(text)['regions']
        out = [(str(n), int(c)) for n, c in regs]
        if [n for n, _ in out] == list(REGIONS):
            return out
    except (ValueError, KeyError, TypeError):
        pass
    return [(r, DEFAULT_COUNTS[r]) for r in REGIONS]


def parse_landmarks(data, width, height, text):
    """Faces from a kind-5 answer: data = float32 LE bytes (width floats per face, height faces).
    Returns a list of dicts: rect (x, y, w, h top-left), roll/yaw/pitch (radians or None), conf, lmconf,
    regions {name: [(x, y), ...]} (top-left; a region a face lacks is an empty list). Truncated data -> ValueError."""
    if height == 0:
        return []
    layout = parse_layout(text)
    need = HEAD + 2 * sum(c for _, c in layout)
    if width != need:
        raise ValueError('row width {} != layout {}'.format(width, need))
    if len(data) != 4 * width * height:
        raise ValueError('payload {} bytes, expected {}'.format(len(data), 4 * width * height))
    vals = struct.unpack('<{}f'.format(width * height), data)
    faces = []
    for f in range(height):
        row = vals[f * width:(f + 1) * width]
        x, y, w, h, roll, yaw, pitch, conf, lmc = row[:HEAD]
        regions = {}
        k = HEAD
        for name, cnt in layout:
            pts = []
            for i in range(cnt):
                px, py = row[k + 2 * i], row[k + 2 * i + 1]
                if _finite(px) and _finite(py):
                    pts.append((px, 1.0 - py))
            regions[name] = pts if len(pts) == cnt else []
            k += 2 * cnt
        faces.append({'rect': (x, 1.0 - (y + h), w, h), 'roll': roll if _finite(roll) else None,
                      'yaw': yaw if _finite(yaw) else None, 'pitch': pitch if _finite(pitch) else None,
                      'conf': conf if _finite(conf) else 0.0, 'lmconf': lmc if _finite(lmc) else 0.0,
                      'regions': regions})
    return faces


def counts_of(faces, fallback=None):
    """Point counts per region from parsed faces (first face with the region), else fallback/DEFAULT_COUNTS."""
    base = dict(fallback or DEFAULT_COUNTS)
    for f in faces:
        for r, pts in f['regions'].items():
            if pts:
                base[r] = len(pts)
    return base


# ------------------------------------------------------------------------------------------------ geometry
def centroid(pts):
    n = float(len(pts))
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n) if pts else (0.0, 0.0)


def axis_extent(pts, aspect=1.0):
    """(length along the main axis, extent across it) of a point set; the axis joins the two farthest points.
    aspect = image width / height so distances are measured in square pixels."""
    if len(pts) < 2:
        return 0.0, 0.0
    q = [(p[0] * aspect, p[1]) for p in pts]
    best, a, b = -1.0, q[0], q[1]
    for i in range(len(q)):
        for j in range(i + 1, len(q)):
            d = (q[i][0] - q[j][0]) ** 2 + (q[i][1] - q[j][1]) ** 2
            if d > best:
                best, a, b = d, q[i], q[j]
    length = math.sqrt(best)
    if length <= 1e-9:
        return 0.0, 0.0
    ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
    across = [(p[0] - a[0]) * -uy + (p[1] - a[1]) * ux for p in q]
    return length, max(across) - min(across)


def roll_from_eyes(regions, aspect=1.0):
    """Head roll (radians, + = clockwise on screen with y down) from the line between the two eye centres."""
    el, er = regions.get('eye_l') or regions.get('pupil_l'), regions.get('eye_r') or regions.get('pupil_r')
    if not el or not er:
        return None
    (ax, ay), (bx, by) = centroid(el), centroid(er)
    if ax > bx:
        (ax, ay), (bx, by) = (bx, by), (ax, ay)
    return math.atan2((by - ay), (bx - ax) * aspect)


def norm(v, lo, hi):
    if hi == lo:
        return 0.0
    return min(1.0, max(0.0, (v - lo) / (hi - lo)))


def measures(face, aspect=1.0, eyeclosed=0.12, eyeopen=0.35, mouthmax=0.6, mouthrest=0.02):
    """Measures of one face (top-left image space). Ratios are scale-free; *_open are mapped 0..1 by the
    calibration values (raw ratios are kept as *_raw)."""
    r = face['regions']
    x, y, w, h = face['rect']
    out = {'conf': face.get('conf', 0.0), 'x': x, 'y': y, 'w': w, 'h': h, 'cx': x + w / 2.0, 'cy': y + h / 2.0,
           'size': w, 'yaw': face.get('yaw') or 0.0, 'pitch': face.get('pitch') or 0.0,
           'roll_vision': face.get('roll') or 0.0}
    for side in ('l', 'r'):
        ln, ac = axis_extent(r.get('eye_' + side) or [], aspect)
        raw = ac / ln if ln > 0 else 0.0
        out['eye_{}_raw'.format(side)] = raw
        out['eye_open_' + side] = norm(raw, eyeclosed, eyeopen)
    ln_out, _ = axis_extent(r.get('lips_outer') or [], aspect)
    inner = r.get('lips_inner') or []
    _, gap = axis_extent(inner, aspect) if inner else (0.0, 0.0)
    mraw = gap / ln_out if ln_out > 0 else 0.0
    out['mouth_raw'] = mraw
    out['mouth_open'] = norm(mraw, mouthrest, mouthmax)
    out['smile'] = smile(r.get('lips_outer') or [], aspect)
    er = roll_from_eyes(r, aspect)
    out['roll'] = er if er is not None else (face.get('roll') or 0.0)
    return out


def smile(lips, aspect=1.0):
    """Mouth-corner lift relative to the lip centre, over mouth width (+ = corners up). 0 when unknown."""
    if len(lips) < 3:
        return 0.0
    q = [(p[0] * aspect, p[1]) for p in lips]
    left = min(q, key=lambda p: p[0])
    right = max(q, key=lambda p: p[0])
    width = math.hypot(right[0] - left[0], right[1] - left[1])
    if width <= 1e-9:
        return 0.0
    cx, cy = centroid(q)
    ux, uy = (right[0] - left[0]) / width, (right[1] - left[1]) / width
    # "up" is perpendicular to the corner line, pointing to smaller y (screen up)
    nx, ny = uy, -ux
    if ny > 0:
        nx, ny = -nx, -ny
    mid = ((left[0] + right[0]) / 2.0, (left[1] + right[1]) / 2.0)
    lift = (mid[0] - cx) * nx + (mid[1] - cy) * ny
    return lift / width


# ------------------------------------------------------------------------------------------------ smoothing
class OneEuro(object):
    """One-Euro filter (Casiez et al. 2012) for one value. mincutoff Hz, beta speed coefficient."""

    def __init__(self, mincutoff=1.0, beta=0.0, dcutoff=1.0):
        self.mincutoff, self.beta, self.dcutoff = mincutoff, beta, dcutoff
        self.x = self.dx = self.t = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, x, t):
        if self.x is None or self.t is None or t <= self.t:
            self.x, self.dx, self.t = x, 0.0, t
            return x
        dt = t - self.t
        dx = (x - self.x) / dt
        ad = self._alpha(self.dcutoff, dt)
        self.dx = ad * dx + (1 - ad) * self.dx
        a = self._alpha(self.mincutoff + self.beta * abs(self.dx), dt)
        self.x = a * x + (1 - a) * self.x
        self.t = t
        return self.x


def smooth_params(smooth):
    """Smooth par 0..1 -> (mincutoff Hz, beta). 0 = off (very high cutoff), 1 = heavy."""
    s = min(1.0, max(0.0, float(smooth)))
    if s <= 0.0:
        return None
    return 30.0 * (1.0 - s) ** 2 + 0.3, 0.02 + 0.5 * (1.0 - s)


def flatten(face):
    """Numbers of a face in a fixed order (rect + every region point) for per-value smoothing."""
    v = list(face['rect'])
    for r in REGIONS:
        for p in face['regions'].get(r) or []:
            v.extend(p)
    return v


def unflatten(face, vals):
    out = dict(face)
    out['rect'] = tuple(vals[:4])
    k = 4
    regs = {}
    for r in REGIONS:
        pts = face['regions'].get(r) or []
        regs[r] = [(vals[k + 2 * i], vals[k + 2 * i + 1]) for i in range(len(pts))]
        k += 2 * len(pts)
    out['regions'] = regs
    return out


# ------------------------------------------------------------------------------------------------ tracking
STALE_S = 0.25  # no helper answer for this long (helper gone / stalled) = treat as "no faces", so slots age out


def stale(last_answer_t, now, limit=STALE_S):
    """True when the newest helper answer is older than `limit` s (or none came yet): the runtime then feeds the
    tracker an empty detection list each frame, so Holdframes / present ramp still run when answers stop."""
    return last_answer_t is None or (now - last_answer_t) > limit


class Tracker(object):
    """Stable slots for up to maxfaces faces: a new detection takes the slot whose last centre is nearest (within
    `gate` x face size), else a free slot. A slot keeps its last pose `hold` frames after loss, then `present`
    ramps to 0 over `fade` frames and the slot frees."""

    def __init__(self, maxfaces=1, hold=10, fade=6, gate=1.0):
        self.maxfaces, self.hold, self.fade, self.gate = maxfaces, hold, fade, gate
        self.slots = [None] * MAX_SLOTS
        self.next_id = 1

    def reset(self):
        self.slots = [None] * MAX_SLOTS

    def update(self, faces, t, smooth=0.0, min_conf=0.0):
        """faces: parsed detections of a new answer (or None = no new answer this frame, just age the slots)."""
        n = max(1, min(MAX_SLOTS, int(self.maxfaces)))
        for i in range(n, MAX_SLOTS):
            self.slots[i] = None
        if faces is None:
            return self._age(n, advance=True)
        faces = [f for f in faces if f.get('conf', 0.0) >= min_conf]
        faces.sort(key=lambda f: -f['rect'][2] * f['rect'][3])
        faces = faces[:n]
        taken = set()
        assign = {}
        pairs = []
        for fi, f in enumerate(faces):
            fx, fy = f['rect'][0] + f['rect'][2] / 2, f['rect'][1] + f['rect'][3] / 2
            for si in range(n):
                s = self.slots[si]
                if s is None:
                    continue
                d = math.hypot(fx - s['cx'], fy - s['cy'])
                if d <= self.gate * max(s['face']['rect'][2], f['rect'][2]):
                    pairs.append((d, fi, si))
        for d, fi, si in sorted(pairs):
            if fi in assign or si in taken:
                continue
            assign[fi] = si
            taken.add(si)
        for fi, f in enumerate(faces):
            if fi not in assign:
                for si in range(n):
                    if si not in taken and self.slots[si] is None:
                        assign[fi] = si
                        taken.add(si)
                        break
                else:
                    for si in range(n):  # evict the oldest lost slot
                        if si not in taken:
                            assign[fi] = si
                            taken.add(si)
                            self.slots[si] = None
                            break
        for fi, si in assign.items():
            self._put(si, faces[fi], t, smooth)
        for si in range(n):
            if si not in taken and self.slots[si] is not None:
                self.slots[si]['lost'] += 1
        return self._age(n, advance=False)

    def _put(self, si, face, t, smooth):
        s = self.slots[si]
        vals = flatten(face)
        sp = smooth_params(smooth)
        if s is None or s.get('nvals') != len(vals):
            s = {'id': self.next_id, 'filters': None, 'nvals': len(vals)}
            self.next_id += 1
        if sp is None:
            s['filters'] = None
            out = vals
        else:
            if s['filters'] is None or s.get('sp') != sp:
                s['filters'] = [OneEuro(sp[0], sp[1]) for _ in vals]
                s['sp'] = sp
            out = [f(v, t) for f, v in zip(s['filters'], vals)]
        s['face'] = unflatten(face, out)
        s['cx'] = s['face']['rect'][0] + s['face']['rect'][2] / 2
        s['cy'] = s['face']['rect'][1] + s['face']['rect'][3] / 2
        s['lost'] = 0
        s['age'] = 0
        s['present'] = 1.0
        self.slots[si] = s

    def _age(self, n, advance):
        out = []
        for si in range(n):
            s = self.slots[si]
            if s is None:
                out.append(None)
                continue
            if advance and s['lost'] > 0:
                s['lost'] += 1
            if s['lost'] > self.hold:
                k = s['lost'] - self.hold
                s['present'] = max(0.0, 1.0 - k / float(max(1, self.fade)))
                if s['present'] <= 0.0:
                    self.slots[si] = None
                    out.append(None)
                    continue
            out.append(s)
        return out


# ------------------------------------------------------------------------------------------------ channels
def point_channel(slot, region, i, axis):
    return 'f{}_{}_{:02d}{}'.format(slot + 1, region, i, axis)


def point_channels(maxfaces, counts=None):
    c = counts or DEFAULT_COUNTS
    names = []
    for s in range(maxfaces):
        for r in REGIONS:
            for i in range(c[r]):
                names += [point_channel(s, r, i, 'x'), point_channel(s, r, i, 'y')]
    return names


def point_values(slots, maxfaces, counts=None):
    """{channel: value} for the pts CHOP (zeros where a face or region is absent)."""
    c = counts or DEFAULT_COUNTS
    vals = {}
    for s in range(maxfaces):
        slot = slots[s] if s < len(slots) else None
        for r in REGIONS:
            pts = (slot['face']['regions'].get(r) if slot else None) or []
            for i in range(c[r]):
                px, py = pts[i] if i < len(pts) else (0.0, 0.0)
                vals[point_channel(s, r, i, 'x')] = px
                vals[point_channel(s, r, i, 'y')] = py
    return vals


def control_values(slots, maxfaces, aspect=1.0, rollunit='deg', **cal):
    """{channel: value} for the ctl CHOP: facecount + per slot f<n>_<CTL_NAMES>."""
    vals = {'facecount': 0.0}
    k = 180.0 / math.pi if rollunit == 'deg' else 1.0
    for s in range(maxfaces):
        slot = slots[s] if s < len(slots) else None
        m = measures(slot['face'], aspect, **cal) if slot else {}
        if slot and slot['present'] > 0:
            vals['facecount'] += 1
        for n in CTL_NAMES:
            if n == 'present':
                v = slot['present'] if slot else 0.0
            elif n == 'slot_id':
                v = float(slot['id']) if slot else 0.0
            else:
                v = m.get(n, 0.0)
                if n in ('roll', 'roll_vision', 'yaw', 'pitch'):
                    v *= k
            vals['f{}_{}'.format(s + 1, n)] = v
    return vals


# ------------------------------------------------------------------------------------------------ shapes
def convex_hull(pts):
    p = sorted(set(pts))
    if len(p) < 3:
        return p

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo, hi = [], []
    for q in p:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0:
            lo.pop()
        lo.append(q)
    for q in reversed(p):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], q) <= 0:
            hi.pop()
        hi.append(q)
    return lo[:-1] + hi[:-1]


def grow(poly, amount, aspect=1.0):
    """Move each vertex away from the centroid by `amount` (image-height units; negative shrinks)."""
    if not poly or amount == 0:
        return list(poly)
    cx, cy = centroid(poly)
    out = []
    for x, y in poly:
        dx, dy = (x - cx) * aspect, y - cy
        d = math.hypot(dx, dy)
        if d <= 1e-9:
            out.append((x, y))
            continue
        f = max(0.0, (d + amount) / d)
        out.append((cx + (x - cx) * f, cy + dy * f))
    return out


def scale(poly, s):
    cx, cy = centroid(poly)
    return [(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in poly]


def face_polygon(regions, forehead=0.25):
    """Face outline: hull of jaw + brows, with the brows raised by `forehead` x (brow-to-chin height) so the
    mask covers the forehead."""
    jaw = regions.get('jaw') or []
    brows = (regions.get('brow_l') or []) + (regions.get('brow_r') or [])
    if not jaw and not brows:
        return []
    if jaw and brows and forehead:
        chin_y = max(p[1] for p in jaw)
        brow_y = min(p[1] for p in brows)
        lift = (chin_y - brow_y) * forehead
        brows = brows + [(x, y - lift) for x, y in brows]
    return convex_hull(jaw + brows)


def mask_polygons(slots, aspect=1.0, grow_amt=0.0, eyeexpand=1.0, mouthexpand=1.0, forehead=0.25):
    """[(kind, [(x, y)...]), ...] top-left image space, for the mask shader."""
    polys = []
    for s in slots:
        if not s or s['present'] <= 0:
            continue
        r = s['face']['regions']
        fp = face_polygon(r, forehead)
        if len(fp) >= 3:
            polys.append((MASK_FACE, grow(fp, grow_amt, aspect)))
        for e in ('eye_l', 'eye_r'):
            if len(r.get(e) or []) >= 3:
                polys.append((MASK_EYES, grow(scale(r[e], eyeexpand), grow_amt, aspect)))
        if len(r.get('lips_outer') or []) >= 3:
            polys.append((MASK_MOUTH, grow(scale(r['lips_outer'], mouthexpand), grow_amt, aspect)))
    return polys


def poly_samples(polys):
    """CHOP samples for the mask shader (texture buffer vec4): x, v (= 1 - y), polygon index, kind.
    Never empty: a degenerate dummy polygon (kind -1) keeps the buffer valid."""
    xs, vs, ids, kinds = [], [], [], []
    for i, (kind, pts) in enumerate(polys):
        for x, y in pts:
            xs.append(x), vs.append(1.0 - y), ids.append(float(i)), kinds.append(float(kind))
    if not xs:
        xs, vs, ids, kinds = [0.0], [0.0], [0.0], [-1.0]
    return xs, vs, ids, kinds


def wire_segments(slots, showwire=True, showboxes=False):
    """Segments per slot for the wire shader: (list of (x0, v0, x1, v1)), and per slot (start, count, bbox uv).
    Open regions are polylines; CLOSED regions are loops; pupils are dots (zero-length segment)."""
    segs, faces = [], []
    for s in slots:
        if not s or s['present'] <= 0:
            continue
        start = len(segs)
        r = s['face']['regions']
        if showwire:
            for name in REGIONS:
                pts = r.get(name) or []
                if len(pts) == 1:
                    x, y = pts[0]
                    segs.append((x, 1 - y, x, 1 - y))
                    continue
                for i in range(len(pts) - 1):
                    segs.append((pts[i][0], 1 - pts[i][1], pts[i + 1][0], 1 - pts[i + 1][1]))
                if name in CLOSED and len(pts) > 2:
                    segs.append((pts[-1][0], 1 - pts[-1][1], pts[0][0], 1 - pts[0][1]))
        x, y, w, h = s['face']['rect']
        if showboxes:
            c = [(x, 1 - y), (x + w, 1 - y), (x + w, 1 - y - h), (x, 1 - y - h)]
            for i in range(4):
                segs.append(c[i] + c[(i + 1) % 4])
        if len(segs) > start:
            allx = [a for sg in segs[start:] for a in (sg[0], sg[2])]
            ally = [a for sg in segs[start:] for a in (sg[1], sg[3])]
            faces.append((float(start), float(len(segs) - start), min(allx), min(ally), max(allx), max(ally),
                          s['present']))
    if not segs:
        segs = [(0.0, 0.0, 0.0, 0.0)]
    if not faces:
        faces = [(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)]
    return segs, faces


def point_in_poly(p, poly):
    """Even-odd test, the Python twin of the mask shader."""
    c = False
    j = len(poly) - 1
    for i in range(len(poly)):
        a, b = poly[i], poly[j]
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]:
            c = not c
        j = i
    return c


def poly_area(poly):
    a = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i - 1]
        x1, y1 = poly[i]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2.0


# ------------------------------------------------------------------------------------------------ fake face
def fake_face(t=0.0, cx=0.5, cy=0.5, size=0.3, aspect=16 / 9.0, counts=None):
    """A synthetic landmark set (top-left image space) for testing the chain with the helper off. Blinks and opens
    the mouth over time t (seconds)."""
    c = counts or DEFAULT_COUNTS
    sx, sy = size / aspect, size
    blink = 0.15 + 0.85 * abs(math.sin(t * 0.9))
    mouth = 0.5 + 0.5 * math.sin(t * 1.7)

    def ring(n, ox, oy, rx, ry, a0=0.0, a1=2 * math.pi, closed=True):
        k = n if closed else max(1, n - 1)
        return [(cx + (ox + rx * math.cos(a0 + (a1 - a0) * i / k)) * sx,
                 cy + (oy + ry * math.sin(a0 + (a1 - a0) * i / k)) * sy) for i in range(n)]

    reg = {
        'jaw': ring(c['jaw'], 0, -0.05, 0.42, 0.55, math.pi * 0.95, math.pi * 0.05, closed=False),
        'brow_l': ring(c['brow_l'], -0.2, -0.28, 0.1, 0.03, math.pi, 2 * math.pi, closed=False),
        'brow_r': ring(c['brow_r'], 0.2, -0.28, 0.1, 0.03, math.pi, 2 * math.pi, closed=False),
        'eye_l': ring(c['eye_l'], -0.18, -0.15, 0.08, 0.035 * blink),
        'eye_r': ring(c['eye_r'], 0.18, -0.15, 0.08, 0.035 * blink),
        'pupil_l': [(cx - 0.18 * sx, cy - 0.15 * sy)][:c['pupil_l']],
        'pupil_r': [(cx + 0.18 * sx, cy - 0.15 * sy)][:c['pupil_r']],
        'nose': ring(c['nose'], 0, 0.05, 0.07, 0.05, math.pi * 0.0, math.pi, closed=False),
        'nosecrest': ring(c['nosecrest'], 0, -0.08, 0.0, 0.1, -math.pi / 2, math.pi / 2, closed=False),
        'median': ring(c['median'], 0, 0.0, 0.0, 0.5, -math.pi / 2, math.pi / 2, closed=False),
        'lips_outer': ring(c['lips_outer'], 0, 0.25, 0.16, 0.04 + 0.06 * mouth),
        'lips_inner': ring(c['lips_inner'], 0, 0.25, 0.12, 0.005 + 0.05 * mouth, 0, math.pi * 2 * (1 - 1.0 / max(1, c['lips_inner']))),
    }
    return {'rect': (cx - 0.45 * sx, cy - 0.6 * sy, 0.9 * sx, 1.2 * sy), 'roll': 0.0, 'yaw': 0.0, 'pitch': 0.0,
            'conf': 1.0, 'lmconf': 1.0, 'regions': reg}
