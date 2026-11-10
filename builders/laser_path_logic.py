"""laser_path_logic: pure logic for LP_laser_path (spec docs/research/BM_lasers.md section 4). No `td` import.

Clean-room, our own code. References: ILDA IDTF14 rev 011, Ether Dream protocol page, nannou lasercube SPECIFICATION
(MIT), lasy / Abderyim et al. (draw order idea), Halabi & Chiba (corner dwell, delay calibration idea).
Copied into the COMP's `lp_logic` Text DAT by builders/laser_path.py; tests: test/test_laser_path.py.

Data model
  rows   : flat table, one point per row: x, y, r, g, b, id, corner (-1 auto, 0 guide, 1 corner)
  shape  : dict pts (N,2) float, col (N,3) float, closed bool, corner (N,) bool
  stream : dict x y r g b i flag (1-D float arrays, one sample per galvo point) + stats
Flag codes = Laser CHOP debugchan codes: 0 colour, 1 corner hold, 3 pre-blank on, 4 post-blank on, 5 blanking,
6 pre-blank off, 7 post-blank off.
No value limits anywhere (operator decides); int16 / 12-bit clamps happen only inside the wire/file packers.
"""
import math
import struct

import numpy as np

EPS = 1e-9
EVALS_PER_MS = 10000          # 2-opt candidate moves per ms of Orderms budget (offline measure, see order_shapes)
FLAG_COLOUR, FLAG_CORNER, FLAG_PREON, FLAG_POSTON, FLAG_BLANK, FLAG_PREOFF, FLAG_POSTOFF = 0, 1, 3, 4, 5, 6, 7
DRAW_FLAGS = (0, 1, 3, 7)
BLANK_FLAGS = (4, 5, 6)
PATTERNS = ['circle', 'square', 'triangle', 'star', 'grid', 'dashed', 'text', 'spiral', 'calib']
STAT_KEYS = ['points_total', 'points_draw', 'points_blank', 'frame_budget', 'frames_per_image', 'shapes', 'corners',
             'blank_travel', 'blank_travel_input', 'est_flicker_hz', 'overflow', 'stepsize_used']

# ------------------------------------------------------------------------------------------------- geometry basics


def corner_angle(p0, p1, p2):
    """Interior angle at p1 in degrees: straight line = 180, right angle = 90, reversal = 0.
    A zero-length neighbour counts as straight (no dwell)."""
    ax, ay = p0[0] - p1[0], p0[1] - p1[1]
    bx, by = p2[0] - p1[0], p2[1] - p1[1]
    la, lb = math.hypot(ax, ay), math.hypot(bx, by)
    if la < EPS or lb < EPS:
        return 180.0
    c = (ax * bx + ay * by) / (la * lb)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def hold_value(angle, minh, maxh):
    """H = lerp(maxhold, minhold, angle/180): 0 deg (reversal) -> maxhold, 180 (straight) -> minhold."""
    t = max(0.0, min(1.0, angle / 180.0))
    return maxh + (minh - maxh) * t


def hold_count(angle, minh, maxh, add=0, factor=1.0):
    """Repeat count of a corner point: add + round(factor * H). With holds in ms, factor = pps / 1000."""
    return int(add) + int(round(factor * hold_value(angle, minh, maxh)))


def ms_to_samples(ms, pps):
    return int(round(float(ms) * float(pps) / 1000.0))


def resample_edge(a, b, step):
    """Samples from a (excluded) to b (included) so no step exceeds `step`. Returns (n, 2) array, n = ceil(d/step)
    (n >= 1; a zero-length edge gives the single point b). The caller emits a once, so edges chain without duplicates."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    d = float(np.hypot(*(b - a)))
    # 1e-5 tolerance: TD CHOPs store float32, so 1.6 arrives as 1.6000000238 and /0.02 = 80.0000012 (live 26 Oct:
    # 345 samples instead of 341 for the square); a step overshoot of 1e-5 is far below galvo resolution.
    n = max(1, int(math.ceil(d / step - 1e-5))) if step > 0 else 1
    t = np.arange(1, n + 1, dtype=float) / n
    out = a[None, :] + (b - a)[None, :] * t[:, None]
    out[-1] = b
    return out


# ------------------------------------------------------------------------------------------------- shapes


def build_shapes(rows, cornertol=25.0):
    """rows: iterable of (x, y, r, g, b, id, corner) -> list of shapes, in order of first appearance of each id.
    Consecutive rows with the same id form one polyline; first == last (1e-6) -> closed (duplicate dropped).
    corner -1 = auto: a vertex is a corner when the path turns by more than `cornertol` deg (interior < 180-tol)."""
    groups, order = {}, []
    for r in rows:
        r = list(r) + [0.0] * (7 - len(r))
        sid = int(round(float(r[5])))
        if sid not in groups:
            groups[sid] = []
            order.append(sid)
        groups[sid].append([float(v) for v in r[:5]] + [float(r[6]) if len(r) > 6 else -1.0])
    shapes = []
    for sid in order:
        g = np.asarray(groups[sid], float)
        pts, col, cflag = g[:, 0:2].copy(), g[:, 2:5].copy(), g[:, 5].copy()
        closed = False
        if len(pts) > 2 and np.hypot(*(pts[0] - pts[-1])) < 1e-6:
            closed = True
            pts, col, cflag = pts[:-1], col[:-1], cflag[:-1]
        shapes.append(make_shape(pts, col, closed, cflag, cornertol))
    return shapes


def make_shape(pts, col, closed, cflag=None, cornertol=25.0):
    pts = np.asarray(pts, float).reshape(-1, 2)
    col = np.asarray(col, float).reshape(-1, 3)
    n = len(pts)
    corner = np.zeros(n, bool)
    for k in range(n):
        want = -1.0 if cflag is None else float(cflag[k])
        if want >= 0.5:
            corner[k] = True
        elif want >= 0:
            corner[k] = False
        else:
            if not closed and (k == 0 or k == n - 1):
                continue
            if n < 3:
                continue
            ang = corner_angle(pts[(k - 1) % n], pts[k], pts[(k + 1) % n])
            corner[k] = ang < 180.0 - cornertol
    return {'pts': pts, 'col': col, 'closed': bool(closed), 'corner': corner}


def shape_entry(s):
    return s['pts'][0]


def shape_exit(s):
    return s['pts'][0] if s['closed'] else s['pts'][-1]


def apply_xform(shapes, scalex=1.0, scaley=1.0, rotate=0.0, offx=0.0, offy=0.0, flipx=False, flipy=False,
                swap=False, warp=None):
    """Flip, scale, rotate (deg, counter-clockwise), offset, swap x/y, then an optional 3x3 warp grid
    (9 (x, y) targets for the source grid -1/0/1 in row-major order from bottom-left, bilinear per quadrant)."""
    c, s_ = math.cos(math.radians(rotate)), math.sin(math.radians(rotate))
    out = []
    for sh in shapes:
        p = sh['pts'].copy()
        if flipx:
            p[:, 0] = -p[:, 0]
        if flipy:
            p[:, 1] = -p[:, 1]
        p[:, 0] *= scalex
        p[:, 1] *= scaley
        x = p[:, 0] * c - p[:, 1] * s_ + offx
        y = p[:, 0] * s_ + p[:, 1] * c + offy
        p = np.stack([y, x] if swap else [x, y], axis=1)
        if warp is not None:
            p = warp_points(p, warp)
        out.append({'pts': p, 'col': sh['col'].copy(), 'closed': sh['closed'], 'corner': sh['corner'].copy()})
    return out


IDENTITY_WARP = [(-1, -1), (0, -1), (1, -1), (-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


def warp_points(p, grid):
    g = np.asarray(grid, float).reshape(3, 3, 2)          # [row (y -1,0,1)][col (x -1,0,1)]
    x, y = p[:, 0], p[:, 1]
    cx = np.clip(np.floor(x + 1.0), 0, 1).astype(int)     # quadrant (outside points extrapolate from the edge cell)
    cy = np.clip(np.floor(y + 1.0), 0, 1).astype(int)
    u = x + 1.0 - cx
    v = y + 1.0 - cy
    p00 = g[cy, cx]
    p10 = g[cy, cx + 1]
    p01 = g[cy + 1, cx]
    p11 = g[cy + 1, cx + 1]
    return ((1 - u)[:, None] * (1 - v)[:, None] * p00 + u[:, None] * (1 - v)[:, None] * p10
            + (1 - u)[:, None] * v[:, None] * p01 + u[:, None] * v[:, None] * p11)


# ------------------------------------------------------------------------------------------------- draw order


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def orient(s, reverse=False, rotation=0):
    """A copy of shape s drawn reversed (open shapes) or starting at vertex `rotation` (closed shapes)."""
    p, c, k = s['pts'], s['col'], s['corner']
    if s['closed'] and rotation:
        p, c, k = np.roll(p, -rotation, 0), np.roll(c, -rotation, 0), np.roll(k, -rotation)
    if reverse:
        p, c, k = p[::-1], c[::-1], k[::-1]
        if s['closed']:                                     # keep the same start vertex when drawn backwards
            p, c, k = np.roll(p, 1, 0), np.roll(c, 1, 0), np.roll(k, 1)
    return {'pts': p.copy(), 'col': c.copy(), 'closed': s['closed'], 'corner': k.copy()}


def blank_travel(shapes, loop=True):
    """Sum of blanked moves between consecutive shapes (+ last back to first when the image loops)."""
    n = len(shapes)
    if n < 2:
        return 0.0 if n == 0 or shapes[0]['closed'] or not loop else _dist(shape_exit(shapes[0]), shape_entry(shapes[0]))
    t = sum(_dist(shape_exit(shapes[k]), shape_entry(shapes[k + 1])) for k in range(n - 1))
    if loop:
        t += _dist(shape_exit(shapes[-1]), shape_entry(shapes[0]))
    return t


def greedy_order(shapes, start=(0.0, 0.0)):
    """Nearest entry first: open shapes may be reversed, closed shapes start at their vertex nearest the pen.
    Returns a list of (index, reverse, rotation). Candidates are one array (vectorised): ties go to the lowest
    candidate index, so the result is deterministic."""
    cv, own, rev, rot = [], [], [], []
    for i, s in enumerate(shapes):
        if s['closed']:
            cv.append(s['pts'])
            own += [i] * len(s['pts'])
            rev += [False] * len(s['pts'])
            rot += list(range(len(s['pts'])))
        else:
            cv.append(np.stack([s['pts'][0], s['pts'][-1]]))
            own += [i, i]
            rev += [False, True]
            rot += [0, 0]
    if not shapes:
        return []
    V = np.concatenate(cv, 0)
    own = np.asarray(own)
    alive = np.ones(len(V), bool)
    pen = np.asarray(start, float)
    plan = []
    for _ in range(len(shapes)):
        d = np.hypot(V[:, 0] - pen[0], V[:, 1] - pen[1])
        d[~alive] = np.inf
        k = int(np.argmin(d))
        i = int(own[k])
        plan.append((i, bool(rev[k]), int(rot[k])))
        alive[own == i] = False
        pen = shape_exit(orient(shapes[i], rev[k], rot[k]))
    return plan


def two_opt(shapes, max_evals=300000):
    """Bounded 2-opt on an oriented shape sequence (cyclic: the image loops). Reversing a run also reverses each
    open shape in it. Deterministic: stops after `max_evals` candidate moves or when no move improves."""
    seq = list(shapes)
    n = len(seq)
    if n < 3:
        return seq
    evals = 0
    improved = True
    order = np.arange(n)                      # positions -> original shape index; flips applied once at the end
    flip = np.zeros(n, bool)                  # per original shape: drawn reversed (open shapes only)
    ent = np.array([shape_entry(s) for s in seq])
    ext = np.array([shape_exit(s) for s in seq])
    cl = np.array([s['closed'] for s in seq])
    while improved and evals < max_evals:
        improved = False
        for i in range(1, n - 1):
            if evals >= max_evals:
                break
            j = np.arange(i + 1, n)
            # run i..j reversed: edges (i-1 -> i) and (j -> j+1) become (i-1 -> j') and (i' -> j+1), where a
            # reversed open shape swaps entry/exit and a closed one keeps them.
            nxt = (j + 1) % n
            old = (np.hypot(*(ext[i - 1] - ent[i])) + np.hypot(ext[j, 0] - ent[nxt, 0], ext[j, 1] - ent[nxt, 1]))
            new_in = np.where(cl[j][:, None], ent[j], ext[j])                 # entry of reversed shape j
            ri_exit = ent[i]                                  # reversed i exits where it used to enter (open or closed)
            new = (np.hypot(new_in[:, 0] - ext[i - 1, 0], new_in[:, 1] - ext[i - 1, 1])
                   + np.hypot(ri_exit[0] - ent[nxt, 0], ri_exit[1] - ent[nxt, 1]))
            evals += len(j)
            gain = old - new
            k = int(np.argmax(gain))
            if gain[k] > 1e-9:
                jj = int(j[k])
                sl = slice(i, jj + 1)
                c_ = cl[sl][::-1].copy()
                e_, x_ = ent[sl][::-1].copy(), ext[sl][::-1].copy()
                ent[sl] = np.where(c_[:, None], e_, x_)        # reversed open shape: entry <-> exit
                ext[sl] = np.where(c_[:, None], x_, e_)
                cl[sl] = c_
                o_ = order[sl][::-1].copy()
                flip[o_[~c_]] ^= True
                order[sl] = o_
                improved = True
    return [orient(seq[k], reverse=bool(flip[k])) if flip[k] else seq[k] for k in order]


def order_shapes(shapes, mode='none', start=(0.0, 0.0), budget_ms=3.0):
    """mode none | nearest | twoopt. Returns (ordered shapes, travel_before, travel_after). Never longer than the
    input order (falls back to it). budget_ms sets the deterministic 2-opt evaluation budget: EVALS_PER_MS candidate
    moves per ms (measured ~1e4/ms in CPython 3 on the M1 Max; TD's x86_64 Python under Rosetta is slower:
    LIVE CHECK own_ms in stats). Deterministic because it counts moves, not wall time."""
    before = blank_travel(shapes)
    if mode == 'none' or len(shapes) < 2:
        return list(shapes), before, before
    plan = greedy_order(shapes, start)
    seq = [orient(shapes[i], rev, rot) for i, rev, rot in plan]
    if mode == 'twoopt':
        seq = two_opt(seq, max_evals=int(max(0.0, budget_ms) * EVALS_PER_MS))
    after = blank_travel(seq)
    if after > before:
        return list(shapes), before, before
    return seq, before, after


# ------------------------------------------------------------------------------------------------- path building


class _Buf:
    def __init__(self):
        self.xy, self.rgb, self.flag = [], [], []

    def add(self, xy, rgb, flag, n=1):
        for _ in range(int(n)):
            self.xy.append((float(xy[0]), float(xy[1])))
            self.rgb.append((float(rgb[0]), float(rgb[1]), float(rgb[2])))
            self.flag.append(flag)

    def add_many(self, xys, rgbs, flag):
        for p, c in zip(xys, rgbs):
            self.add(p, c, flag)


def shape_samples(s, p):
    """One shape -> (xy list, rgb list, flag list): guide points once, corner points held, closed shapes overlapped."""
    pps = p['pps']
    fac = pps / 1000.0
    b = _Buf()
    pts, col, cor = s['pts'], s['col'], s['corner']
    n = len(pts)
    if n == 1:                                               # a dot: dwell at max hold
        b.add(pts[0], col[0], FLAG_CORNER, max(1, hold_count(0.0, p['minhold'], p['maxhold'], p['holdadd'], fac)))
        return b
    b.add(pts[0], col[0], FLAG_COLOUR)
    edges = n if s['closed'] else n - 1

    def hold_at(k):
        if not cor[k]:
            return 0
        ang = corner_angle(pts[(k - 1) % n], pts[k], pts[(k + 1) % n])
        return hold_count(ang, p['minhold'], p['maxhold'], p['holdadd'], fac)

    if s['closed']:
        b.add(pts[0], col[0], FLAG_CORNER, hold_at(0))
    for e in range(edges):
        a, z = e, (e + 1) % n
        seg = resample_edge(pts[a], pts[z], p['stepsize'])
        m = len(seg)
        t = (np.arange(1, m + 1) / m)[:, None]
        cols = col[a][None, :] * (1 - t) + col[z][None, :] * t if p.get('interpcolors', True) else \
            np.repeat(col[z][None, :], m, 0)
        b.add_many(seg, cols, FLAG_COLOUR)
        if z != 0 or not s['closed']:
            b.add(pts[z], col[z], FLAG_CORNER, hold_at(z))
    if s['closed']:
        ov = ms_to_samples(p.get('closedoverlap', 0.0), pps)
        draw = [(xy, c) for xy, c, f in zip(b.xy, b.rgb, b.flag) if f == FLAG_COLOUR][1:]
        for k in range(min(ov, len(draw))):
            b.add(draw[k][0], draw[k][1], FLAG_COLOUR)
    return b


def insert_blanks(a_xy, a_rgb, b_xy, b_rgb, p):
    """Blank move from the end of shape A to the start of shape B, Laser CHOP style phases:
    pre-blank-on (colour on, at A) -> post-blank-on (dark, at A) -> travel (dark, Bstepsize) -> pre-blank-off
    (dark, at B) -> post-blank-off (colour on, at B). ms -> samples = round(ms * pps / 1000)."""
    pps = p['pps']
    b = _Buf()
    dark = (0.0, 0.0, 0.0)
    b.add(a_xy, a_rgb, FLAG_PREON, ms_to_samples(p['preblankon'], pps))
    b.add(a_xy, dark, FLAG_POSTON, ms_to_samples(p['postblankon'], pps))
    if _dist(a_xy, b_xy) > EPS:
        mv = resample_edge(a_xy, b_xy, p['bstepsize'])
        b.add_many(mv, [dark] * len(mv), FLAG_BLANK)
    b.add(b_xy, dark, FLAG_PREOFF, ms_to_samples(p['preblankoff'], pps))
    b.add(b_xy, b_rgb, FLAG_POSTOFF, ms_to_samples(p['postblankoff'], pps))
    return b


def build_path(shapes, p):
    """Ordered shapes -> stream arrays (x, y, rgb, flag). The image loops: the last shape blanks back to the first.
    Joints closer than EPS (one closed shape on its own) get no blanking."""
    xy, rgb, flag = [], [], []
    n = len(shapes)
    bufs = [shape_samples(s, p) for s in shapes]
    for k in range(n):
        sb = bufs[k]
        xy += sb.xy
        rgb += sb.rgb
        flag += sb.flag
        nb = bufs[(k + 1) % n]
        if not sb.xy or not nb.xy:
            continue
        if n == 1 and shapes[0]['closed']:
            continue
        a, b_ = sb.xy[-1], nb.xy[0]
        if _dist(a, b_) <= EPS and (n == 1 or shapes[k]['closed']):
            continue
        bl = insert_blanks(a, sb.rgb[-1], b_, nb.rgb[0], p)
        xy += bl.xy
        rgb += bl.rgb
        flag += bl.flag
    if not xy:
        return np.zeros((0, 2)), np.zeros((0, 3)), np.zeros(0, int)
    return np.asarray(xy, float), np.asarray(rgb, float), np.asarray(flag, int)


def delay_colour(rgb, d):
    """Shift colour by d samples relative to xy (cyclic: the image loops): out[i] = in[i - d]."""
    rgb = np.asarray(rgb, float)
    if len(rgb) == 0 or d == 0:
        return rgb.copy()
    return np.roll(rgb, int(d), axis=0)


def frame_budget(pps, fps):
    """Points one frame can hold."""
    return int(round(float(pps) / max(float(fps), EPS)))


def overflow_ratio(total, budget):
    return float(total) / max(float(budget), 1.0)


def frames_per_image(total, budget):
    return max(1, int(math.ceil(float(total) / max(float(budget), 1.0) - 1e-12)))


def frame_window(total, budget, frame):
    """Sample indices one output frame carries when the image needs several frames (cyclic)."""
    if total <= 0:
        return np.zeros(0, int)
    b = min(int(budget), total)
    start = (int(frame) * b) % total
    return (start + np.arange(b)) % total


# ------------------------------------------------------------------------------------------------- engine


DEFAULTS = {
    'pps': 30000.0, 'fps': 60.0, 'stepsize': 0.02, 'bstepsize': 0.1, 'minhold': 0.1, 'maxhold': 0.3, 'holdadd': 0,
    'closedoverlap': 0.0, 'order': 'none', 'startpoint': 'centre', 'preblankon': 0.0, 'postblankon': 0.1,
    'preblankoff': 0.1, 'postblankoff': 0.0, 'colordelay': 0.0, 'interpcolors': True, 'overflow': 'frames',
    'cornertol': 25.0, 'orderms': 3.0, 'scalex': 1.0, 'scaley': 1.0, 'rotate': 0.0, 'offx': 0.0, 'offy': 0.0,
    'flipx': False, 'flipy': False, 'swap': False, 'warp': None, 'rgb': (1.0, 1.0, 1.0), 'intensity': 1.0,
    'gain': 1.0,
}


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


def run_engine(rows, p, shapes=None):
    """Whole Own engine: rows -> shapes -> transform -> order -> resample/dwell -> blank -> colour delay -> budget.
    Returns dict x y r g b i flag (float arrays) + 'stats' + 'shapes' (ordered, transformed)."""
    if shapes is None:
        shapes = build_shapes(rows, p['cornertol'])
    shapes = apply_xform(shapes, p['scalex'], p['scaley'], p['rotate'], p['offx'], p['offy'], p['flipx'],
                         p['flipy'], p['swap'], p['warp'])
    tint = np.asarray(p['rgb'], float) * float(p['gain']) * float(p['intensity'])
    for s in shapes:
        s['col'] = s['col'] * tint[None, :]
    start = (0.0, 0.0) if p['startpoint'] == 'centre' else (tuple(shape_entry(shapes[0])) if shapes else (0.0, 0.0))
    shapes, t0, t1 = order_shapes(shapes, p['order'], start, p['orderms'])
    budget = frame_budget(p['pps'], p['fps'])
    q = dict(p)
    xy, rgb, flag = build_path(shapes, q)
    if p['overflow'] == 'thin' and len(flag) > budget:
        for _ in range(6):                                   # widen the steps until it fits (operator's choice)
            r = overflow_ratio(len(flag), budget)
            if r <= 1.0:
                break
            q['stepsize'] *= r * 1.05
            q['bstepsize'] *= r * 1.05
            xy, rgb, flag = build_path(shapes, q)
    elif p['overflow'] == 'drop' and len(flag) > budget and len(shapes) > 1:
        keep = list(shapes)
        while len(keep) > 1:
            far = max(range(len(keep)), key=lambda k: float(np.hypot(*keep[k]['pts'].mean(0))))
            keep.pop(far)
            xy, rgb, flag = build_path(keep, q)
            if len(flag) <= budget:
                break
        shapes = keep
        t1 = blank_travel(shapes)
    rgb = delay_colour(rgb, ms_to_samples(p['colordelay'], p['pps']))
    n = len(flag)
    on = np.isin(flag, DRAW_FLAGS)
    inten = on.astype(float)                                  # i = beam on (colour samples), 0 on blanked ones
    st = {
        'points_total': n, 'points_draw': int(on.sum()), 'points_blank': int(n - on.sum()),
        'frame_budget': budget, 'frames_per_image': frames_per_image(n, budget), 'shapes': len(shapes),
        'corners': int(sum(int(s['corner'].sum()) for s in shapes)), 'blank_travel': round(t1, 6),
        'blank_travel_input': round(t0, 6), 'est_flicker_hz': round(p['pps'] / max(n, 1), 3),
        'overflow': round(overflow_ratio(n, budget), 4), 'stepsize_used': round(q['stepsize'], 6),
    }
    return {'x': xy[:, 0] if n else np.zeros(0), 'y': xy[:, 1] if n else np.zeros(0),
            'r': rgb[:, 0] if n else np.zeros(0), 'g': rgb[:, 1] if n else np.zeros(0),
            'b': rgb[:, 2] if n else np.zeros(0), 'i': inten, 'flag': flag.astype(float), 'stats': st,
            'shapes': shapes}


def stream_stats(x, y, r, g, b, flag=None, pps=30000.0, fps=60.0):
    """Stats for any stream (e.g. the Native Laser CHOP output): draw = any colour on."""
    n = len(x)
    on = (np.asarray(r) + np.asarray(g) + np.asarray(b)) > 1e-6
    budget = frame_budget(pps, fps)
    st = {'points_total': n, 'points_draw': int(on.sum()), 'points_blank': int(n - on.sum()),
          'frame_budget': budget, 'frames_per_image': frames_per_image(n, budget)}
    if flag is not None and len(flag):
        f = np.asarray(flag).astype(int)
        st['flag_counts'] = {int(k): int((f == k).sum()) for k in np.unique(f)}
    return st


def count_runs(flag, code):
    """Number of contiguous runs of `code` in a flag array (e.g. how many corner holds / blank moves)."""
    f = np.asarray(flag).astype(int) == int(code)
    if not len(f):
        return 0
    return int(f[0]) + int(np.sum(f[1:] & ~f[:-1]))


# ------------------------------------------------------------------------------------------------- drive


def drive_level(src, t, manual=1.0, bpm=120.0, beatdiv=1.0, audio=0.0, audioamt=1.0, chop=1.0):
    """Intensity multiplier for Intensitysrc manual | bpm | audio | chop. BPM = square LFO, on for the first half of
    each period, period = 60 / (bpm * beatdiv) s (120 BPM, beatdiv 1 -> toggles at 2 Hz)."""
    if src == 'bpm':
        f = max(bpm, 0.0) * max(beatdiv, 0.0) / 60.0
        return manual * (1.0 if (f <= 0 or (t * f) % 1.0 < 0.5) else 0.0)
    if src == 'audio':
        return manual * max(0.0, 1.0 - audioamt + audioamt * abs(audio))
    if src == 'chop':
        return manual * chop
    return manual


def strobe_gate(mode, t, bpm=120.0, beatdiv=1.0, audio=0.0, thresh=0.5):
    """Strobe on/off modulation: off -> 1, manual -> 1 (button held = caller), bpm -> square, audio -> gate."""
    if mode == 'bpm':
        f = max(bpm, 0.0) * max(beatdiv, 0.0) / 60.0
        return 1.0 if (f <= 0 or (t * f * 2.0) % 1.0 < 0.5) else 0.0
    if mode == 'audio':
        return 1.0 if abs(audio) >= thresh else 0.0
    return 1.0


# ------------------------------------------------------------------------------------------------- preview model


def galvo_coeffs(pps, bw, zeta):
    """2nd-order low-pass H(s) = w^2 / (s^2 + 2 zeta w s + w^2), w = 2 pi bw, bilinear (Tustin) at fs = pps
    with prewarp at bw. Returns (b0, b1, b2, a1, a2) of y[n] = b.x - a1 y[n-1] - a2 y[n-2]."""
    fs = float(pps)
    w = 2.0 * math.pi * float(bw)
    k = w / math.tan(min(w / (2.0 * fs), math.pi / 2 - 1e-6))   # prewarped 2/T
    k2, w2 = k * k, w * w
    a0 = k2 + 2 * zeta * w * k + w2
    b0 = w2 / a0
    return (b0, 2 * b0, b0, (2 * w2 - 2 * k2) / a0, (k2 - 2 * zeta * w * k + w2) / a0)


def biquad(x, c, y1=None):
    b0, b1, b2, a1, a2 = c
    x = np.asarray(x, float)
    y = np.empty_like(x)
    xm1 = xm2 = x[0] if len(x) else 0.0
    ym1 = ym2 = (x[0] if len(x) else 0.0) if y1 is None else y1
    for n in range(len(x)):
        v = b0 * x[n] + b1 * xm1 + b2 * xm2 - a1 * ym1 - a2 * ym2
        xm2, xm1 = xm1, x[n]
        ym2, ym1 = ym1, v
        y[n] = v
    return y


def galvo_filter(x, y, pps, bw, zeta, loop=True):
    """Mirror lag per axis. loop=True primes the filter with the tail of the image (it repeats), so frame 1 already
    shows the steady-state path."""
    c = galvo_coeffs(pps, bw, zeta)
    x, y = np.asarray(x, float), np.asarray(y, float)
    n = len(x)
    if n == 0:
        return x.copy(), y.copy()
    if loop:
        pre = min(n, 512)
        fx = biquad(np.concatenate([x[-pre:], x]), c)[pre:]
        fy = biquad(np.concatenate([y[-pre:], y]), c)[pre:]
        return fx, fy
    return biquad(x, c), biquad(y, c)


def step_overshoot(zeta):
    """Closed-form percent overshoot of a 2nd-order system (zeta < 1)."""
    return 100.0 * math.exp(-zeta * math.pi / math.sqrt(1 - zeta * zeta))


def dwell_weights(x, y, stepsize, loop=True):
    """Brightness per sample ~ 1 / (eps + speed), normalised so a sample on a normal stroke (speed = stepsize) = 1."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    if len(x) == 0:
        return np.zeros(0)
    px = np.roll(x, 1) if loop else np.concatenate([x[:1], x[:-1]])
    py = np.roll(y, 1) if loop else np.concatenate([y[:1], y[:-1]])
    sp = np.hypot(x - px, y - py)
    eps = max(stepsize, 1e-6) * 0.25
    return (stepsize + eps) / (sp + eps)


# ------------------------------------------------------------------------------------------------- test patterns


def _poly(pts, col=(1, 1, 1), sid=0, closed=True, corner=-1):
    rows = [(p[0], p[1], col[0], col[1], col[2], sid, corner) for p in pts]
    if closed:
        rows.append(rows[0])
    return rows


def pattern_rows(name, count=8, size=0.8, t=0.0, seed=7):
    """Deterministic test shapes in [-size, size]."""
    s = float(size)
    count = max(1, int(count))
    if name == 'circle':
        n = max(8, count * 8)
        a = np.arange(n) * 2 * math.pi / n
        return _poly(np.stack([s * np.cos(a), s * np.sin(a)], 1), corner=0)
    if name == 'square':
        return _poly([(-s, -s), (s, -s), (s, s), (-s, s)], corner=1)
    if name == 'triangle':
        a = math.pi / 2 + np.arange(3) * 2 * math.pi / 3
        return _poly(np.stack([s * np.cos(a), s * np.sin(a)], 1), corner=1)
    if name == 'star':
        k = max(3, count if count > 2 else 5)
        a = math.pi / 2 + np.arange(2 * k) * math.pi / k
        r = np.where(np.arange(2 * k) % 2 == 0, s, s * 0.42)
        return _poly(np.stack([r * np.cos(a), r * np.sin(a)], 1), corner=1)
    if name == 'grid':
        rows, sid = [], 0
        for yy in (-s, 0.0, s):
            for xx in (-s, 0.0, s):
                rows.append((xx, yy, 1, 1, 1, sid, 1))
                sid += 1
        return rows
    if name == 'dashed':
        rng = np.random.default_rng(seed)
        rows = []
        for k in range(count):
            c = rng.uniform(-s, s, 2)
            a = rng.uniform(0, math.pi)
            L = s * 0.08
            d = np.array([math.cos(a), math.sin(a)]) * L / 2
            rows += [(c[0] - d[0], c[1] - d[1], 1, 1, 1, k, -1), (c[0] + d[0], c[1] + d[1], 1, 1, 1, k, -1)]
        return rows
    if name == 'spiral':
        n = max(16, count * 24)
        u = np.arange(n) / (n - 1)
        a = u * 2 * math.pi * max(1, count // 2)
        r = s * (0.08 + 0.92 * u)
        return _poly(np.stack([r * np.cos(a), r * np.sin(a)], 1), closed=False, corner=0)
    if name == 'calib':
        rows = _poly([(-s, -s), (s, -s), (s, s), (-s, s)], sid=0, corner=1)
        per = 4 * 2 * s
        d = (t * 0.25 % 1.0) * per                          # a dot sweeping the square, one lap per 4 s
        side, f = int(d // (2 * s)), (d % (2 * s)) - s
        p = [(f, -s), (s, f), (-f, s), (-s, -f)][min(side, 3)]
        rows.append((p[0], p[1], 1.0, 0.25, 0.25, 1, 1))
        return rows
    return []


# ------------------------------------------------------------------------------------------------- ILDA IDTF (format 5)


def _ilda_header(fmt, n, frame, total, name='LP', company='jazibtd', projector=0):
    nm = name.encode('ascii', 'replace')[:8].ljust(8, b' ')
    co = company.encode('ascii', 'replace')[:8].ljust(8, b' ')
    return b'ILDA' + b'\x00\x00\x00' + bytes([fmt]) + nm + co + struct.pack('>HHHBB', n, frame, total, projector, 0)


def to_i16(v):
    return int(max(-32768, min(32767, int(round(float(v) * 32767.0)))))


def to_ilda_f5(frames, name='LP', company='jazibtd', projector=0):
    """frames: list of dicts with x y r g b (floats; r g b 0..1, all zero = blanked) -> ILDA format 5 bytes
    (2D true colour, records x y status B G R), big-endian, status bit 7 on the last point, bit 6 on blanked ones,
    a null header (0 records) at the end."""
    out = bytearray()
    total = len(frames)
    for fi, f in enumerate(frames):
        n = len(f['x'])
        out += _ilda_header(5, n, fi, total, name, company, projector)
        for k in range(n):
            r, g, b = (max(0, min(255, int(round(float(f[c][k]) * 255)))) for c in 'rgb')
            blank = (r | g | b) == 0
            st = (0x80 if k == n - 1 else 0) | (0x40 if blank else 0)
            out += struct.pack('>hhBBBB', to_i16(f['x'][k]), to_i16(f['y'][k]), st, b, g, r)
    out += _ilda_header(5, 0, total, total, name, company, projector)
    return bytes(out)


def from_ilda(data):
    """Reader for formats 0, 1, 4, 5 (true colour comes back as floats; index colour formats keep 'index')."""
    frames, off = [], 0
    sizes = {0: 8, 1: 6, 2: 3, 4: 10, 5: 8}
    while off + 32 <= len(data):
        h = data[off:off + 32]
        if h[:4] != b'ILDA':
            raise ValueError('bad ILDA header at %d' % off)
        fmt = h[7]
        n, frame, total, proj = struct.unpack('>HHHB', h[24:31])
        off += 32
        if n == 0:
            break
        rs = sizes[fmt]
        f = {'format': fmt, 'name': h[8:16].decode('ascii', 'replace').strip(), 'frame': frame, 'total': total,
             'x': [], 'y': [], 'r': [], 'g': [], 'b': [], 'blank': [], 'last': []}
        for k in range(n):
            rec = data[off:off + rs]
            off += rs
            if fmt == 2:
                continue
            if fmt in (4, 5):
                if fmt == 4:
                    x, y, _z, st, bb, gg, rr = struct.unpack('>hhhBBBB', rec)
                else:
                    x, y, st, bb, gg, rr = struct.unpack('>hhBBBB', rec)
            else:
                if fmt == 0:
                    x, y, _z, st, idx = struct.unpack('>hhhBB', rec)
                else:
                    x, y, st, idx = struct.unpack('>hhBB', rec)
                rr = gg = bb = idx
            blank = bool(st & 0x40)
            f['x'].append(x / 32767.0)
            f['y'].append(y / 32767.0)
            for c, v in (('r', rr), ('g', gg), ('b', bb)):
                f[c].append(0.0 if blank else v / 255.0)
            f['blank'].append(blank)
            f['last'].append(bool(st & 0x80))
        frames.append(f)
    return frames


# ------------------------------------------------------------------------------------------------- wire packers


ED_POINT = struct.Struct('<HhhHHHHHH')       # control, x, y, r, g, b, i, u1, u2 (18 bytes)
ED_STATUS = struct.Struct('<BBBBHHHHII')     # protocol, light_engine, playback, source, 3 flags, fullness, rate, count
# (20 bytes; the spec note's '<BBBBHHHHHII' has one H too many = 22 bytes)


def etherdream_pack_points(x, y, r, g, b, i=None, rate_change_first=False):
    out = bytearray()
    for k in range(len(x)):
        ctl = 0x8000 if (rate_change_first and k == 0) else 0
        iv = 1.0 if i is None else i[k]
        out += ED_POINT.pack(ctl, to_i16(x[k]), to_i16(y[k]), *(max(0, min(65535, int(round(v * 65535))))
                                                             for v in (r[k], g[k], b[k], iv)), 0, 0)
    return bytes(out)


def etherdream_parse_status(buf):
    v = ED_STATUS.unpack(buf[:ED_STATUS.size])
    keys = ['protocol', 'light_engine_state', 'playback_state', 'source', 'light_engine_flags', 'playback_flags',
            'source_flags', 'buffer_fullness', 'point_rate', 'point_count']
    return dict(zip(keys, v))


LC_MAX_POINTS = 140


def lc12(v):
    return max(0, min(4095, int(round((float(v) * 0.5 + 0.5) * 4095))))


def lasercube_pack(x, y, r, g, b, msg=0, frame=0):
    """LaserCube data datagrams (nannou spec): header a9 00 msg frame + points of 5 x u16 LE (x y r g b), 12-bit,
    centre 0x800, <= 140 points each. Returns (datagrams, next msg number); msg wraps at 255."""
    out = []
    n = len(x)
    for s in range(0, n, LC_MAX_POINTS):
        d = bytearray([0xa9, 0x00, msg & 0xff, frame & 0xff])
        for k in range(s, min(n, s + LC_MAX_POINTS)):
            d += struct.pack('<HHHHH', lc12(x[k]), lc12(y[k]), lc12(r[k] * 2 - 1), lc12(g[k] * 2 - 1),
                             lc12(b[k] * 2 - 1))
        out.append(bytes(d))
        msg = (msg + 1) & 0xff
    return out, msg


def export_check(x, y, r, g, b, i=None, name='LP'):
    """DAC-less export of one laser image (the `laser` stream): colour = rgb * i (i = 0 blanks), ILDA format 5 bytes,
    read back + compared, and the same points through the Ether Dream and LaserCube packers. No device, no socket.
    Returns (ilda_bytes, report dict)."""
    n = len(x)
    iv = [1.0] * n if i is None else [float(v) for v in i]
    col = {c: [max(0.0, min(1.0, float(v) * iv[k])) for k, v in enumerate(ch)] for c, ch in zip('rgb', (r, g, b))}
    xs = [max(-1.0, min(1.0, float(v))) for v in x]
    ys = [max(-1.0, min(1.0, float(v))) for v in y]
    data = to_ilda_f5([{'x': xs, 'y': ys, 'r': col['r'], 'g': col['g'], 'b': col['b']}], name=name)
    back = from_ilda(data)
    f = back[0] if back else {'x': [], 'y': [], 'r': [], 'blank': [], 'last': []}
    xy_err = max([abs(a - b_) for a, b_ in zip(xs + ys, f['x'] + f['y'])] or [0.0])
    col_err = max([abs(col[c][k] - f[c][k]) for c in 'rgb' for k in range(len(f[c])) if not f['blank'][k]] or [0.0])
    blank_in = sum(1 for k in range(n) if max(col['r'][k], col['g'][k], col['b'][k]) * 255 < 0.5)
    ed = etherdream_pack_points(xs, ys, col['r'], col['g'], col['b'], iv)
    lc, _ = lasercube_pack(xs, ys, col['r'], col['g'], col['b'])
    rep = {'points': n, 'ilda_bytes': len(data), 'ilda_expect': 32 + 8 * n + 32, 'frames_back': len(back),
           'points_back': len(f['x']), 'xy_err': xy_err, 'col_err': col_err, 'blank': blank_in,
           'blank_back': sum(f['blank']), 'last_flag_ok': bool(f['last']) and f['last'][-1] and sum(f['last']) == 1,
           'etherdream_bytes': len(ed), 'etherdream_expect': 18 * n, 'lasercube_datagrams': len(lc),
           'lasercube_expect': (n + LC_MAX_POINTS - 1) // LC_MAX_POINTS,
           'lasercube_max_bytes': max([len(d) for d in lc] or [0])}
    rep['ok'] = bool(rep['ilda_bytes'] == rep['ilda_expect'] and rep['points_back'] == n and xy_err <= 1.0 / 32767 + 1e-9
                     and col_err <= 0.5 / 255 + 1e-9 and rep['blank_back'] == blank_in and rep['last_flag_ok']
                     and rep['etherdream_bytes'] == rep['etherdream_expect']
                     and rep['lasercube_datagrams'] == rep['lasercube_expect'] and rep['lasercube_max_bytes'] <= 4 + 10 * 140)
    return data, rep


def lasercube_parse_info(buf):
    """GET_FULL_INFO (0x77) reply, 64 bytes: dac rate u32 LE at 10, max rate at 14, rx buffer free u16 at 19,
    rx buffer size u16 at 21."""
    if len(buf) < 23:
        raise ValueError('short info reply')
    return {'cmd': buf[0], 'fw_major': buf[2], 'fw_minor': buf[3], 'output_enabled': bool(buf[5] & 1),
            'dac_rate': struct.unpack_from('<I', buf, 10)[0], 'max_dac_rate': struct.unpack_from('<I', buf, 14)[0],
            'rx_free': struct.unpack_from('<H', buf, 19)[0], 'rx_size': struct.unpack_from('<H', buf, 21)[0]}


# ------------------------------------------------------------------------------------------------- tables


def stats_rows(st):
    rows = [['stat', 'value']]
    for k in STAT_KEYS:
        if k in st:
            rows.append([k, str(st[k])])
    for k in sorted(st):
        if k not in STAT_KEYS:
            rows.append([k, str(st[k])])
    return rows
