# fx_destroy_explode_logic - pure Python reference for FX_destroy module 'explode' (builders/fx_destroy_explode.py).
# Mirrors the `tiles` shader (grid, rest centres, analytic tile motion -> centre xyz, alpha, quaternion x scale) and
# the per-pixel ray cast of one tile, in float64, for the offline tests and the live parity check
# (docs/builds/fx_destroy_explode.md). Texel coordinates: x right, y up. No TD imports. ASCII only.
import math

M32 = 0xffffffff
NX, NY = 64, 72
NMAX = NX * NY


def lb32(x):
    x &= M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def hsh(cx, cy, s):
    """GLSL hsh(ivec2(cx, cy), s) of the rack lib (builders/fx_destroy.py GLSL_LIB)."""
    return lb32(((cx & M32) * 1597334677) & M32 ^ lb32((cy & M32) ^ ((s * 2654435761) & M32))) / 4294967296.0


def grid(W, H, cells, aspect):
    """(stride, rows, cell w, cell h) exactly as grid_exprs() in the module."""
    asp = max(0.05, aspect)
    cols = max(1, min(cells, int(math.sqrt(int(NMAX * 0.9) * asp * W / max(1, H)))))
    cw = W / cols
    return cols + 1, math.ceil(H / (cw * asp)), cw, cw * asp


def rest_centre(i, g, W, brick):
    st, rows, cw, ch = g
    row, col = i // st, i % st
    off = 0.5 * cw if brick and row % 2 == 1 else 0.0
    x0 = col * cw - off
    if row >= rows or x0 >= W or i >= NMAX:
        return None
    return (x0 + 0.5 * cw, (row + 0.5) * ch)


def tile_at(x, y, g, brick):
    st, _rows, cw, ch = g
    row = int(math.floor(y / ch))
    off = 0.5 * cw if brick and row % 2 == 1 else 0.0
    return row * st + int(math.floor((x + off) / cw))


def quat_euler(ax, ay, az):
    cx, cy, cz = math.cos(ax / 2), math.cos(ay / 2), math.cos(az / 2)
    sx, sy, sz = math.sin(ax / 2), math.sin(ay / 2), math.sin(az / 2)
    return (sx * cy * cz - cx * sy * sz, cx * sy * cz + sx * cy * sz, cx * cy * sz - sx * sy * cz,
            cx * cy * cz + sx * sy * sz)


def smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0) if b != a else (0.0 if x < a else 1.0)
    return t * t * (3 - 2 * t)


def tile(i, P, W, H, now, hit=None, centre=None):
    """b0 (x, y, z, alpha; alpha -1 = rest) and b1 (quaternion x scale) of tile i, or None for an unused slot.
    P = par dict (Mode / Drive as indices, Brick 0/1); hit = (time, cx, cy) latched; centre = live (manual)."""
    g = grid(W, H, P['Cells'], P['Aspect'])
    rc = rest_centre(i, g, W, P['Brick'])
    if rc is None:
        return None
    rest = ((rc[0], rc[1], 0.0, -1.0), (0.0, 0.0, 0.0, 1.0))
    mode, manual = int(P['Mode']), int(P['Drive']) == 1
    if manual:
        age0, ctr, valid = P['Progress'] * P['Duration'], centre, P['Progress'] * P['Duration'] > 0
    else:
        valid = hit is not None and hit[0] >= 0 and now >= hit[0]
        age0, ctr = (now - hit[0], hit[1:3]) if valid else (0.0, (0.0, 0.0))
    if not valid or P['Amount'] <= 0:
        return rest
    sd = (int(P['Seed']) * 7919) & M32
    h = [hsh(i, k, sd) for k in range(8)]
    rx, ry = rc[0] - ctr[0], rc[1] - ctr[1]
    rl = math.hypot(rx, ry)
    d = rl / math.hypot(W, H)
    a = age0 - P['Stagger'] * (d * 1.4142 + 0.25 * h[7])
    m = P['Amount']
    if mode == 2:
        tau = min(max(P['Duration'] - a, 0.0), P['Duration'])
    else:
        tau = max(a, 0.0)
        if P['Return'] > 0:
            m *= 1.0 - smoothstep(P['Hold'], P['Hold'] + P['Return'], tau)
    if tau <= 0 or m <= 0:
        return rest
    fall = math.exp(-P['Falloff'] * d * 4)
    k = P['Drag']
    I = (1 - math.exp(-k * tau)) / k if k > 1e-4 else tau
    al = min(max(1 - tau / P['Fade'], 0.0), 1.0) if P['Fade'] > 0 else 1.0
    ang = [P['Tilt'] * (2 * h[5] - 1) * I, P['Tilt'] * (2 * h[6] - 1) * I, P['Spin'] * (2 * h[4] - 1) * I]
    sc = 1.0
    if mode == 1:
        sp = abs(P['Force']) / 600 * (1 - 0.5 * P['Scatter'] + P['Scatter'] * h[2]) * (0.25 + fall)
        e = 1 - math.exp(-tau * sp)
        sw = P['Swirl'] * e
        px = (math.cos(sw) * rx - math.sin(sw) * ry) * (1 - e) + ctr[0]
        py = (math.sin(sw) * rx + math.cos(sw) * ry) * (1 - e) + ctr[1]
        pz = -P['Depth'] * H * e * (0.3 + h[3])
        sc = 1 - P['Shrink'] * e
    else:
        d0 = (rx / rl, ry / rl) if rl > 1e-3 else (0.0, 1.0)
        an = 2 * math.pi * h[1]
        dx = d0[0] + (math.cos(an) - d0[0]) * P['Scatter']
        dy = d0[1] + (math.sin(an) - d0[1]) * P['Scatter']
        L = math.hypot(dx, dy)
        dx, dy = (dx / L, dy / L) if L > 1e-4 else (math.cos(an), math.sin(an))
        c, s = math.cos(P['Swirl']), math.sin(P['Swirl'])
        dx, dy = c * dx - s * dy, s * dx + c * dy
        sp = P['Force'] * fall * (1 - 0.5 * P['Scatter'] + P['Scatter'] * h[2])
        px = rc[0] + dx * sp * I
        py = rc[1] + dy * sp * I - 0.5 * P['Gravity'] * tau * tau
        pz = P['Depth'] * H * (1.6 * h[3] - 0.3) * math.exp(-P['Falloff'] * d * 2) * I
    px, py, pz = rc[0] + (px - rc[0]) * m, rc[1] + (py - rc[1]) * m, pz * m
    ang = [x * m for x in ang]
    sc = 1 + (sc - 1) * m
    al = 1 + (al - 1) * m
    q = quat_euler(*ang)
    s_ = max(sc, 1e-4)
    return (px, py, pz, al if sc > 1e-4 else 0.0), tuple(x * s_ for x in q)


def axes(q):
    """Unit quaternion -> tile x axis, y axis, normal (columns of the rotation matrix)."""
    x, y, z, w = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y)),
            (2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x)),
            (2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y)))


def ray_local(px, py, b0, b1, W, H, F):
    """Ray from the camera (W/2, H/2, F) through pixel centre (px, py) onto tile (b0, b1): (t, local x, y) or None."""
    s = math.sqrt(sum(v * v for v in b1))
    ax, ay, az = axes(tuple(v / s for v in b1))
    E = (W / 2, H / 2, F)
    rd = (px - W / 2, py - H / 2, -F)
    dn = sum(a * b for a, b in zip(rd, az))
    if abs(dn) < 1e-9:
        return None
    t = sum((b0[k] - E[k]) * az[k] for k in range(3)) / dn
    h = [E[k] + t * rd[k] - b0[k] for k in range(3)]
    return t, sum(a * b for a, b in zip(h, ax)) / s, sum(a * b for a, b in zip(h, ay)) / s


def hit_step(h, s, now, hit, reset, centre, ignore=False, end=1e30):
    """Mirror of the HIT latch shader (explode + disintegrate): h = [hit time, cx, cy, 7], s = [seen, 0, 0, 0] or None
    (fresh texture); hit / reset = the uniform values (already voided by the rack stamp exprs). Returns (h, s)."""
    if h is None or h[3] != 7.0 or not s[0] <= now + 0.05:   # fresh, or a seen stamp from another clock (T-155/160)
        return [-1.0, centre[0], centre[1], 7.0], [max(hit, reset), 0.0, 0.0, 0.0]
    h, s = list(h), list(s)
    if reset > s[0]:
        h[0], s[0] = -1.0, reset
    if hit > s[0]:
        flying = h[0] >= 0.0 and now - h[0] < end
        if not (ignore and flying):
            h[0], h[1], h[2] = hit, centre[0], centre[1]
        s[0] = hit
    return h, s
