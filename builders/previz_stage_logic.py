"""previz_stage pure logic (no td import): wall layout, crowd rows, screen colour analysis, beams, camera presets.

Units are metres. World: x right, y up, the audience is on +z, the main LED face stands at z = 0 facing +z.
Copied into the COMP as the Text DAT `previz_logic`; offline tests: test/test_previz_stage.py.
"""
import math
import random

TAU = 2.0 * math.pi

# ---------------------------------------------------------------- LED wall

def preset_faces(layout, wallw=12.0, wallh=6.75, curve=0.0, sidew=4.0, sideh=6.75, sidefold=20.0, custom_rows=None):
    """Face table for a layout: list of dicts {name, width, height, fold, curve, lift}, left to right.
    flat = one face; sides = side, main, side; custom = custom_rows (dicts or (w, h, fold, curve, lift) tuples)."""
    main = {'name': 'main', 'width': float(wallw), 'height': float(wallh), 'fold': 0.0, 'curve': float(curve), 'lift': 0.0}
    if layout == 'sides':
        lift = max(0.0, (float(wallh) - float(sideh)) * 0.5)
        side = lambda n: {'name': n, 'width': float(sidew), 'height': float(sideh), 'fold': float(sidefold), 'curve': 0.0,
                          'lift': lift}
        return [side('left'), main, side('right')]
    if layout == 'custom':
        out = []
        for i, r in enumerate(custom_rows or []):
            if isinstance(r, dict):
                d = dict(r)
            else:
                r = list(r) + [0.0] * 5
                d = {'width': r[0], 'height': r[1], 'fold': r[2], 'curve': r[3], 'lift': r[4]}
            d.setdefault('name', 'face%d' % (i + 1))
            for k in ('width', 'height', 'fold', 'curve', 'lift'):
                d[k] = float(d.get(k) or 0.0)
            if d['width'] > 0 and d['height'] > 0:
                out.append(d)
        return out or [main]
    return [main]


def main_index(faces):
    """The face the chain grows out from: the widest (first one on a tie)."""
    best = 0
    for i, f in enumerate(faces):
        if f['width'] > faces[best]['width'] + 1e-9:
            best = i
    return best


def _segs(curve):
    return max(1, int(math.ceil(abs(curve) / 4.0)))


def _walk(x, z, heading, length, curve, n, sign):
    """Points along an arc of `length` that turns by `curve` degrees (sign +1 = toward +z when walking right)."""
    pts = [(x, z)]
    step = length / n
    for k in range(n):
        h = heading + sign * math.radians(curve) * (k + 0.5) / n
        x += step * math.cos(h)
        z += step * math.sin(h)
        pts.append((x, z))
    return pts, heading + sign * math.radians(curve)


def face_layout(faces, gap=0.0, elev=0.0, uvmode='span'):
    """Place faces edge to edge (gap between), the widest centred at x = 0, z = 0.
    fold = degrees each face turns toward the audience from its neighbour on the main side; curve = degrees the face
    itself bends (edges toward the audience). Returns {'faces': [{name, cols: [(x, z)], y0, y1, u0, u1, v0, v1}],
    'span_w', 'canvas_h', 'aspect', 'bounds'}; cols run left to right."""
    if not faces:
        faces = preset_faces('flat')
    m = main_index(faces)
    placed = [None] * len(faces)
    f = faces[m]
    n = _segs(f['curve'])
    half = max(1, n // 2) if n > 1 else 1
    if n == 1:
        w = f['width']
        placed[m] = [(-w / 2.0, 0.0), (w / 2.0, 0.0)]
        rh, lh = 0.0, math.pi
    else:
        hr = f['width'] / 2.0
        right, rh = _walk(0.0, 0.0, 0.0, hr, f['curve'] / 2.0, half, +1)
        left, lh = _walk(0.0, 0.0, math.pi, hr, f['curve'] / 2.0, half, -1)
        placed[m] = list(reversed(left)) + right[1:]
    # right of main
    x, z = placed[m][-1]
    h = rh
    for i in range(m + 1, len(faces)):
        f = faces[i]
        h += math.radians(f['fold'])
        x += gap * math.cos(h)
        z += gap * math.sin(h)
        pts, h = _walk(x, z, h, f['width'], f['curve'], _segs(f['curve']), +1)
        placed[i] = pts
        x, z = pts[-1]
    # left of main (walk leftwards, then reverse so cols read left to right)
    x, z = placed[m][0]
    h = lh
    for i in range(m - 1, -1, -1):
        f = faces[i]
        h -= math.radians(f['fold'])
        x += gap * math.cos(h)
        z += gap * math.sin(h)
        pts, h = _walk(x, z, h, f['width'], f['curve'], _segs(f['curve']), -1)
        placed[i] = list(reversed(pts))
        x, z = pts[-1]
    y0s = [elev + f['lift'] for f in faces]
    y1s = [elev + f['lift'] + f['height'] for f in faces]
    ymin, ymax = min(y0s), max(y1s)
    span = sum(f['width'] for f in faces)
    out, acc = [], 0.0
    for i, f in enumerate(faces):
        if uvmode == 'repeat':
            u0, u1, v0, v1 = 0.0, 1.0, 0.0, 1.0
        else:
            u0, u1 = acc / span, (acc + f['width']) / span
            v0, v1 = (y0s[i] - ymin) / (ymax - ymin), (y1s[i] - ymin) / (ymax - ymin)
        acc += f['width']
        out.append({'name': f['name'], 'cols': placed[i], 'y0': y0s[i], 'y1': y1s[i], 'u0': u0, 'u1': u1, 'v0': v0, 'v1': v1})
    xs = [p[0] for fc in out for p in fc['cols']]
    zs = [p[1] for fc in out for p in fc['cols']]
    if uvmode == 'repeat':
        aspect = max(f['width'] / f['height'] for f in faces)
    else:
        aspect = span / (ymax - ymin)
    return {'faces': out, 'span_w': span, 'canvas_h': ymax - ymin, 'aspect': aspect,
            'bounds': (min(xs), ymin, min(zs), max(xs), ymax, max(zs))}


def wall_mesh(layout):
    """Quads for the wall: points [(x, y, z, u, v)], quads [(a, b, c, d)] (counter-clockwise seen from +z)."""
    pts, quads = [], []
    for fc in layout['faces']:
        cols = fc['cols']
        n = len(cols) - 1
        base = len(pts)
        for k, (x, z) in enumerate(cols):
            u = fc['u0'] + (fc['u1'] - fc['u0']) * k / n
            pts.append((x, fc['y0'], z, u, fc['v0']))
            pts.append((x, fc['y1'], z, u, fc['v1']))
        for k in range(n):
            a = base + 2 * k
            quads.append((a, a + 2, a + 3, a + 1))
    return pts, quads


def length2d(cols):
    return sum(math.hypot(cols[k + 1][0] - cols[k][0], cols[k + 1][1] - cols[k][1]) for k in range(len(cols) - 1))

# ---------------------------------------------------------------- crowd

def crowd_rows(count, rows, spacing, hvar, seed, front_z, hands=0.0):
    """Seeded audience grid. Returns [(x, z, scale, ry_deg, phase, hand)] with hand 0/1; same seed = same crowd."""
    count, rows = max(0, int(count)), max(1, int(rows))
    r = random.Random(int(seed))
    per = -(-count // rows) if count else 0
    out = []
    for i in range(count):
        row, col = divmod(i, per)
        jitter = 0.25 * spacing
        x = (col - (per - 1) / 2.0) * spacing + r.uniform(-jitter, jitter) + (0.5 * spacing if row % 2 else 0.0)
        z = front_z + row * spacing * 0.9 + r.uniform(-jitter, jitter)
        s = 1.0 + r.uniform(-hvar, hvar)
        ry = r.uniform(-25.0, 25.0)
        ph = r.uniform(0.0, TAU)
        hand = 1 if r.random() < hands else 0
        out.append((x, z, s, ry, ph, hand))
    return out

# Crowd sway on the GPU (perf wave 2, 27 Oct): previz_stage.CROWD_GLSL replaced two Noise CHOPs (sparse, period 2
# samples, translate y = absTime * Swayspeed; 0.53 ms CPU per frame at 800 people). Per person a cubic B-spline of
# hashed values in time: matches the CHOPs' measured temporal correlation (0.84 / 0.53 / 0.27 / 0.10 at 0.5 / 1 / 1.5
# / 2 s at Swayspeed 0.5) and their std (0.27 x amp); neighbours independent as before (CHOP 0.11).
SWAY_RATE = 1.9       # noise cells per (second x Swayspeed)
SWAY_GAIN = 0.675     # 0.27 (CHOP std / amp) / 0.400 (std of the B-spline noise)
SWAY_SALTS = (1, 7)   # rz, ty (the Noise CHOPs' seeds)


def _lowbias(x):
    x &= 0xFFFFFFFF
    x ^= x >> 16
    x = (x * 0x7feb352d) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 0x846ca68b) & 0xFFFFFFFF
    x ^= x >> 16
    return x


def sway_value(person, cell, salt):
    """Hashed value in [-1, 1] for (person, integer cell), as CROWD_GLSL's swayV."""
    h = _lowbias((_lowbias(person * 2 + salt) + (int(cell) & 0xFFFFFFFF)) & 0xFFFFFFFF)
    return h / 4294967295.0 * 2.0 - 1.0


def sway_noise(u, person, salt):
    """Numpy-free twin of CROWD_GLSL's swayN: uniform cubic B-spline of sway_value over cells, ~unit / 0.4 std."""
    i0 = math.floor(u)
    f = u - i0
    f2, f3 = f * f, f * f * f
    w = ((1 - f) ** 3 / 6.0, (3 * f3 - 6 * f2 + 4) / 6.0, (-3 * f3 + 3 * f2 + 3 * f + 1) / 6.0, f3 / 6.0)
    return sum(wk * sway_value(person, i0 + k - 1, salt) for k, wk in enumerate(w))


def crowd_sway(t, speed, sway, person):
    """(rz deg, ty m) of one person at time t: what the crowd_xf pass adds (Sway x 6 deg, Sway x 0.06 m)."""
    u = t * speed * SWAY_RATE
    return (sway * 6.0 * SWAY_GAIN * sway_noise(u, person, SWAY_SALTS[0]),
            sway * 0.06 * SWAY_GAIN * sway_noise(u, person, SWAY_SALTS[1]))

# ---------------------------------------------------------------- screen colour analysis

def luma(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _avg(px):
    if not px:
        return (0.0, 0.0, 0.0)
    n = float(len(px))
    return (sum(p[0] for p in px) / n, sum(p[1] for p in px) / n, sum(p[2] for p in px) / n)


def dominant(px):
    """Colour of the most saturated + bright pixels (weighted), falls back to the average for grey content."""
    best, wsum, acc = None, 0.0, [0.0, 0.0, 0.0]
    for p in px:
        mx, mn = max(p[:3]), min(p[:3])
        w = (mx - mn) * mx
        w = w * w
        wsum += w
        for k in range(3):
            acc[k] += p[k] * w
    if wsum < 1e-9:
        return _avg(px)
    return tuple(a / wsum for a in acc)


def analyse(grid, cols, rows, faces_u=None):
    """grid: flat list of (r, g, b) row-major, row 0 = bottom, `cols` x `rows`.
    Returns avg, dom, left, right colours and per-face (r, g, b) from u windows [(u0, u1)]."""
    px = [tuple(p[:3]) for p in grid]
    colof = lambda c: [px[r * cols + c] for r in range(rows)]
    half = cols // 2
    left = [p for c in range(half) for p in colof(c)]
    right = [p for c in range(cols - half, cols) for p in colof(c)]
    out = {'avg': _avg(px), 'dom': dominant(px), 'left': _avg(left), 'right': _avg(right), 'faces': []}
    for u0, u1 in (faces_u or []):
        cs = [c for c in range(cols) if u0 - 1e-9 <= (c + 0.5) / cols <= u1 + 1e-9]
        if not cs:  # narrow face: nearest column
            cs = [min(cols - 1, max(0, int((u0 + u1) * 0.5 * cols)))]
        out['faces'].append(_avg([p for c in cs for p in colof(c)]))
    return out


def lag_alpha(dt, lag):
    """Per-step blend toward the target for a one-pole lag of `lag` seconds (0 = instant)."""
    if lag <= 1e-6:
        return 1.0
    return 1.0 - math.exp(-max(0.0, dt) / lag)


def lerp_follow(base, screen, follow):
    return tuple(b + (s - b) * follow for b, s in zip(base, screen))

# ---------------------------------------------------------------- beams + lights

def strobe_gate(t, hz, amount):
    """1 = full; Strobe amount pulls the 'off' half of a square wave down to 1 - amount."""
    if amount <= 0 or hz <= 0:
        return 1.0
    return 1.0 if (t * hz) % 1.0 < 0.5 else 1.0 - amount


def dir_from_angles(pan_deg, tilt_deg):
    """A beam hanging down (0, -1, 0) tilted toward +z by tilt, then panned toward +x by pan."""
    t, p = math.radians(tilt_deg), math.radians(pan_deg)
    d = (math.sin(t) * math.sin(p), -math.cos(t), math.sin(t) * math.cos(p))
    return d


def aim_to_euler(d):
    """Euler rx, rz (deg, rotate order xyz) turning (0, -1, 0) onto unit vector d: d = Rz(rz) Rx(rx) (0, -1, 0)."""
    dx, dy, dz = d
    n = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    dx, dy, dz = dx / n, dy / n, dz / n
    a = math.asin(max(-1.0, min(1.0, -dz)))
    c = math.atan2(dx, -dy)
    return math.degrees(a), math.degrees(c)


def euler_to_dir(rx, rz):
    a, c = math.radians(rx), math.radians(rz)
    return (math.cos(a) * math.sin(c), -math.cos(a) * math.cos(c), -math.sin(a))


def beam_rig(n, width, height, z, fan, tilt, sweep, sweepspeed, t):
    """n beams on a truss line `width` wide at (y=height, z). Returns [(x, y, z, pan, tilt, xfrac)]."""
    n = max(1, int(n))
    out = []
    for i in range(n):
        f = 0.5 if n == 1 else i / (n - 1.0)
        x = (f - 0.5) * width
        ph = TAU * sweepspeed * t + i * 1.7
        pan = (f - 0.5) * fan + sweep * 40.0 * math.sin(ph)
        tl = tilt + sweep * 15.0 * math.cos(ph * 0.73)
        out.append((x, height, z, pan, tl, f))
    return out


def beam_colour(mode, xfrac, react, face_u=None):
    """Colour a beam takes from the screen: average | leftright | perface | dominant."""
    if mode == 'dominant':
        return react['dom']
    if mode == 'leftright':
        return react['left'] if xfrac < 0.5 else react['right']
    if mode == 'perface' and react.get('faces'):
        best, bd = 0, 9.0
        for i, (u0, u1) in enumerate(face_u or []):
            d = 0.0 if u0 <= xfrac <= u1 else min(abs(xfrac - u0), abs(xfrac - u1))
            if d < bd:
                best, bd = i, d
        return react['faces'][min(best, len(react['faces']) - 1)]
    return react['avg']

# ---------------------------------------------------------------- camera

CAM_PRESETS = {
    # name: (eye, target) for a 12 m wall; scaled by the wall size
    'foh': ((0.0, 3.2, 30.0), (0.0, 4.5, 0.0)),
    'stageleft': ((-16.0, 4.0, 18.0), (0.0, 4.5, 2.0)),
    'stageright': ((16.0, 4.0, 18.0), (0.0, 4.5, 2.0)),
    'drone': ((0.0, 22.0, 42.0), (0.0, 1.5, 10.0)),
    'crowdpov': ((0.6, 1.7, 17.0), (0.0, 5.5, 0.0)),
    'orbit': ((0.0, 7.0, 34.0), (0.0, 4.0, 4.0)),
}
CAM_ORDER = ['foh', 'stageleft', 'stageright', 'drone', 'crowdpov', 'orbit']


def cam_pose(preset, yaw=0.0, pitch=0.0, dist=1.0, scale=1.0):
    """Eye and target for a preset, rotated around the target by yaw/pitch (deg) and scaled by dist and the wall."""
    eye, tgt = CAM_PRESETS.get(preset, CAM_PRESETS['foh'])
    tgt = tuple(v * scale if k != 1 else v * scale for k, v in enumerate(tgt))
    ex, ey, ez = (eye[0] * scale - tgt[0], eye[1] * scale - tgt[1], eye[2] * scale - tgt[2])
    r = math.sqrt(ex * ex + ey * ey + ez * ez) * max(0.05, dist)
    az = math.atan2(ex, ez) + math.radians(yaw)
    el = math.asin(max(-1.0, min(1.0, ey / (r / max(0.05, dist))))) + math.radians(pitch)
    el = max(math.radians(-80), min(math.radians(85), el))
    eye = (tgt[0] + r * math.cos(el) * math.sin(az), tgt[1] + r * math.sin(el), tgt[2] + r * math.cos(el) * math.cos(az))
    return eye, tgt


def wall_scale(span_w, canvas_h):
    """Camera scale so bigger walls stay in frame (1 for the default 12 x 6.75 m wall)."""
    return max(0.25, max(span_w / 12.0, canvas_h / 6.75))


# ---------------------------------------------------------------- quality

QUALITY_SCALE = {'draft': 0.5, 'medium': 0.75, 'high': 1.0}


def quality_settings(quality, resx, resy, msaa):
    """Render size + antialias for a Quality menu value. out1 stays resx x resy (the grade step scales up)."""
    q = QUALITY_SCALE.get(quality, 1.0)
    w, h = max(16, int(round(resx * q))), max(16, int(round(resy * q)))
    if quality == 'draft':
        aa = 'aa1'
    elif quality == 'medium' and msaa in ('aa4', 'aa8mid'):
        aa = 'aa2'
    else:
        aa = msaa
    return w, h, aa
