# gen_clone_logic - pure logic of GEN_clone (G-CLONE cloner COMP, FX0 row 70). No TD needed: the builder, the
# runtime (Text DAT `clone_logic`, same text) and the offline tests use this file.
#   * the uniform spec (one table -> the compute TOP's vec4 expressions AND the Python mirror's inputs);
#   * counts / texture size (5 texels per clone, CW clones per row);
#   * the Python mirror of builders/glsl/gen_clone_layout.glsl (clone_ref) and of the vertex transform (vertex_ref);
#   * path-points resampling by arc length (pts_resample) for the Script CHOP `pts_chop`.
# ASCII only.
import math

MODES = ['grid', 'radial', 'linear', 'path', 'points', 'random']
SOURCES = ['card', 'box', 'sphere', 'torus', 'sop']
PATHS = ['circle', 'line', 'lissajous', 'spiral', 'helix', 'points']
PLANES = ['xy', 'xz', 'yz']
AXES = ['x', 'y', 'z']
TIMEMODES = ['index', 'random', 'distance']
MAPMODES = ['off', 'colour', 'scale', 'both']
PTSOURCES = ['sop', 'chop', 'top']
TEXSOURCES = ['auto', 'test', 'top']
RINGORDER = ['newestlast', 'newestfirst']
SHADINGS = ['flat', 'lambert']
TEXELS = 5                      # per clone: pos+us, quat, colour, scale+toff, weight/index/hidden
CW_MAX = 1024                   # clones per texture row
M32 = 0xFFFFFFFF

# Uniform spec of the `clones` compute TOP. Tokens: 'Par' (eval), 'Par#' (menuIndex), number, '@time', '@n', '@cw',
# '@phase' (Pathspeed x time). Same order / names as the GLSL header.
U = [('uC0', ['Mode#', '@n', '@cw', 'Seed']),
     ('uC1', ['Countx', 'County', 'Countz', 'Centre']),
     ('uC2', ['Spacex', 'Spacey', 'Spacez', 'Radius']),
     ('uC3', ['Arcstart', 'Arcend', 'Plane#', 'Align']),
     ('uC4', ['Linx', 'Liny', 'Linz', 'Pathshape#']),
     ('uC5', ['Pathsize', 'Pathturns', 'Pathstart', 'Pathend']),
     ('uC6', ['@phase', 'Helixheight', 'Pointstep', 'Alignaxis#']),
     ('uC7', ['Boxx', 'Boxy', 'Boxz', '@time']),
     ('uM0', ['Steprx', 'Stepry', 'Steprz', 'Stepscale']),
     ('uM1', ['Stephue', 'Randhue', 'Randscale', 'Noisescale']),
     ('uM2', ['Randpx', 'Randpy', 'Randpz', 'Noisefreq']),
     ('uM3', ['Randrx', 'Randry', 'Randrz', 'Noisespeed']),
     ('uM4', ['Noisepos', 'Noiserot', 'Timeoffset', 'Timemode#']),
     ('uM5', ['Colourr', 'Colourg', 'Colourb', 'Alpha']),
     ('uM6', ['Size', 'Mapmode#', 'Mapamount', 'Mapsize']),
     ('uM7', ['Scalex', 'Scaley', 'Scalez', 0]),
     ('uEffA', ['Effoffx', 'Effoffy', 'Effoffz', 'Effpush']),
     ('uEffB', ['Effrotx', 'Effroty', 'Effrotz', 'Effscale']),
     ('uEffC', ['Effcolourr', 'Effcolourg', 'Effcolourb', 'Effcolourmix']),
     ('uEffD', ['Efftime', 'Effhide', 0, 0])]
MENUS = {'Mode': MODES, 'Plane': PLANES, 'Pathshape': PATHS, 'Alignaxis': AXES, 'Timemode': TIMEMODES,
         'Mapmode': MAPMODES}
LOGIC = "op('clone_logic').module"


def token_expr(tok):
    """TD expression for a spec token (evaluated on the compute TOP, parent() = GEN_clone)."""
    if isinstance(tok, (int, float)):
        return str(tok)
    if tok == '@time':
        return 'absTime.seconds'
    if tok == '@phase':
        return 'parent().par.Pathspeed.eval() * absTime.seconds'
    if tok == '@n':
        return '%s.count_of(parent())' % LOGIC
    if tok == '@cw':
        return '%s.cw(%s.count_of(parent()))' % (LOGIC, LOGIC)
    if tok.endswith('#'):
        return 'parent().par.%s.menuIndex' % tok[:-1]
    if tok in ('Align', 'Centre'):
        return 'float(parent().par.%s.eval())' % tok
    return 'parent().par.%s.eval()' % tok


def uniform_exprs():
    return [(name, [token_expr(t) for t in toks]) for name, toks in U]


def uniform_values(P, n, t=0.0):
    """The same vec4s from a dict of par values (menus by name) for the mirror."""
    out = {}
    for name, toks in U:
        v = []
        for tok in toks:
            if isinstance(tok, (int, float)):
                v.append(float(tok))
            elif tok == '@time':
                v.append(float(t))
            elif tok == '@phase':
                v.append(float(P.get('Pathspeed', 0.0)) * t)
            elif tok == '@n':
                v.append(float(n))
            elif tok == '@cw':
                v.append(float(cw(n)))
            elif tok.endswith('#'):
                v.append(float(MENUS[tok[:-1]].index(P[tok[:-1]])))
            else:
                v.append(float(P.get(tok, 0.0)))
        out[name] = v
    return out


DEFAULTS = {
    'Mode': 'grid', 'Count': 12, 'Seed': 1, 'Countx': 5, 'County': 9, 'Countz': 1, 'Centre': 1,
    'Spacex': 0.42, 'Spacey': 0.42, 'Spacez': 0.42, 'Radius': 1.2, 'Arcstart': 0.0, 'Arcend': 360.0, 'Plane': 'xy',
    'Align': 0, 'Alignaxis': 'y', 'Linx': 0.0, 'Liny': 0.25, 'Linz': 0.0, 'Pathshape': 'circle', 'Pathsize': 1.2,
    'Pathturns': 3.0, 'Pathstart': 0.0, 'Pathend': 1.0, 'Pathspeed': 0.0, 'Helixheight': 3.0, 'Pointstep': 1,
    'Boxx': 2.4, 'Boxy': 4.2, 'Boxz': 1.0, 'Steprx': 0.0, 'Stepry': 0.0, 'Steprz': 0.0, 'Stepscale': 0.0,
    'Stephue': 0.0, 'Randhue': 0.0, 'Randscale': 0.0, 'Noisescale': 0.0, 'Randpx': 0.0, 'Randpy': 0.0, 'Randpz': 0.0,
    'Noisefreq': 1.0, 'Randrx': 0.0, 'Randry': 0.0, 'Randrz': 0.0, 'Noisespeed': 0.5, 'Noisepos': 0.0,
    'Noiserot': 0.0, 'Timeoffset': 0.0, 'Timemode': 'index', 'Colourr': 1.0, 'Colourg': 1.0, 'Colourb': 1.0,
    'Alpha': 1.0, 'Size': 0.35, 'Mapmode': 'off', 'Mapamount': 1.0, 'Mapsize': 2.4, 'Scalex': 1.0, 'Scaley': 1.0,
    'Scalez': 1.0, 'Effoffx': 0.0, 'Effoffy': 0.0, 'Effoffz': 0.0, 'Effpush': 0.0, 'Effrotx': 0.0, 'Effroty': 0.0,
    'Effrotz': 0.0, 'Effscale': 1.0, 'Effcolourr': 1.0, 'Effcolourg': 0.3, 'Effcolourb': 0.1, 'Effcolourmix': 0.0,
    'Efftime': 0.0, 'Effhide': 0.0,
}


# ------------------------------------------------------------------------------------------------ counts
def count_for(mode, count, cx, cy, cz, npts=0, step=1):
    if mode == 'grid':
        return max(int(cx), 1) * max(int(cy), 1) * max(int(cz), 1)
    if mode == 'points':
        return int(math.ceil(max(int(npts), 0) / float(max(int(step), 1))))
    return max(int(count), 0)


def cw(n):
    return max(1, min(int(n), CW_MAX))


def tex_size(n):
    """(width, height) of the clones texture: 5 texels per clone, CW per row; at least 5 x 1."""
    c = cw(n)
    return TEXELS * c, max(1, int(math.ceil(max(int(n), 1) / float(c))))


def count_of(c):
    """TD runtime: the clone count of GEN_clone `c` (points mode reads the point texture size, no pixel readback)."""
    g = lambda n: getattr(c.par, n).eval()          # noqa: E731
    npts = 0
    if g('Mode') == 'points':
        p = c.op('pts_src')
        npts = (p.width * p.height) if p is not None else 0
    return count_for(g('Mode'), g('Count'), g('Countx'), g('County'), g('Countz'), npts, g('Pointstep'))


# ------------------------------------------------------------------------------------------------ mirror maths
def pcg(v):
    s = (v * 747796405 + 2891336453) & M32
    w = (((s >> ((s >> 28) + 4)) ^ s) * 277803737) & M32
    return ((w >> 22) ^ w) & M32


def h01(i, k):
    return (pcg(((i * 1664525) & M32) ^ pcg(k & M32)) >> 8) / 16777216.0


def _lat(c, k):
    return h01(((((c[0] + 4096) * 73856093) & M32) ^ (((c[1] + 4096) * 19349663) & M32) ^
                (((c[2] + 4096) * 83492791) & M32)), k)


def vnoise(p, k):
    f = [math.floor(x) for x in p]
    t = [x - fl for x, fl in zip(p, f)]
    t = [x * x * (3.0 - 2.0 * x) for x in t]
    c = [int(x) for x in f]

    def L(dx, dy, dz):
        return _lat((c[0] + dx, c[1] + dy, c[2] + dz), k)

    def mix(a, b, s):
        return a + (b - a) * s
    a = mix(L(0, 0, 0), L(1, 0, 0), t[0])
    b = mix(L(0, 1, 0), L(1, 1, 0), t[0])
    d = mix(L(0, 0, 1), L(1, 0, 1), t[0])
    e = mix(L(0, 1, 1), L(1, 1, 1), t[0])
    return mix(mix(a, b, t[1]), mix(d, e, t[1]), t[2])


def qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz, aw * bx + bw * ax + ay * bz - az * by,
            aw * by + bw * ay + az * bx - ax * bz, aw * bz + bw * az + ax * by - ay * bx)


def qaxis(ax, deg):
    h = math.radians(deg) * 0.5
    s = math.sin(h)
    return (math.cos(h), ax[0] * s, ax[1] * s, ax[2] * s)


def qeuler(d):
    return qmul(qaxis((0, 0, 1), d[2]), qmul(qaxis((0, 1, 0), d[1]), qaxis((1, 0, 0), d[0])))


def _norm(v):
    l = math.sqrt(sum(x * x for x in v))
    return tuple(x / l for x in v) if l > 0 else tuple(v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def qfromto(a, b):
    c = sum(x * y for x, y in zip(a, b))
    if c < -0.99999:
        o = _cross(a, (1, 0, 0)) if abs(a[0]) < 0.9 else _cross(a, (0, 1, 0))
        o = _norm(o)
        return (0.0, o[0], o[1], o[2])
    cr = _cross(a, b)
    q = (1.0 + c, cr[0], cr[1], cr[2])
    l = math.sqrt(sum(x * x for x in q))
    return tuple(x / l for x in q)


def qrot(q, v):
    w, x, y, z = q
    u = (x, y, z)
    t = _cross(u, v)
    t = (t[0] + w * v[0], t[1] + w * v[1], t[2] + w * v[2])
    c2 = _cross(u, t)
    return (v[0] + 2 * c2[0], v[1] + 2 * c2[1], v[2] + 2 * c2[2])


def hue_rot(c, turns):
    a = turns * 2.0 * math.pi
    k = (0.57735026919,) * 3
    kc = _cross(k, c)
    kd = sum(x * y for x, y in zip(k, c))
    return tuple(c[i] * math.cos(a) + kc[i] * math.sin(a) + k[i] * kd * (1.0 - math.cos(a)) for i in range(3))


def _plane(v, plane):
    if plane == 1:
        return (v[0], 0.0, v[1])
    if plane == 2:
        return (0.0, v[0], v[1])
    return (v[0], v[1], 0.0)


def _fract(x):
    return x - math.floor(x)


def path_point(t, shape, u, pts=None):
    r, turns = u['uC5'][0], max(u['uC5'][1], 0.0)
    plane = int(round(u['uC3'][2]))
    if shape == 1:
        return _plane(((t - 0.5) * r * 2.0, 0.0), plane)
    if shape == 2:
        return _plane((r * math.sin(2 * math.pi * 3.0 * t + 0.5 * math.pi), r * math.sin(2 * math.pi * 2.0 * t)),
                      plane)
    if shape == 3:
        a = 2 * math.pi * turns * t
        return _plane((r * t * math.cos(a), r * t * math.sin(a)), plane)
    if shape == 4:
        a = 2 * math.pi * turns * t
        return (r * math.cos(a), (t - 0.5) * u['uC6'][1], r * math.sin(a))
    if shape == 5:
        return pts_at(pts or [(0.0, 0.0, 0.0)], _fract(t) * (len(pts or [0]) - 1))
    a = 2 * math.pi * t
    return _plane((r * math.cos(a), r * math.sin(a)), plane)


def pts_at(pts, f):
    n = len(pts)
    a = min(max(int(math.floor(f)), 0), max(n - 1, 0))
    b = min(a + 1, max(n - 1, 0))
    s = f - a
    return tuple(pts[a][k] + (pts[b][k] - pts[a][k]) * s for k in range(3))


def layout_ref(i, n, u, pts=None):
    """(base position, align direction) of clone i (mirror of gcLayout)."""
    mode = int(round(u['uC0'][0]))
    if mode == 0:
        c = [max(int(round(x)), 1) for x in u['uC1'][:3]]
        g = (i % c[0], (i // c[0]) % c[1], i // (c[0] * c[1]))
        pos = tuple((g[k] - 0.5 * (c[k] - 1)) * u['uC2'][k] for k in range(3))
        return pos, _norm((pos[0] + 1e-6, pos[1], pos[2]))
    if mode == 1:
        span = u['uC3'][1] - u['uC3'][0]
        f = i / float(max(n, 1)) if abs(span) >= 359.999 else i / float(max(n - 1, 1))
        a = math.radians(u['uC3'][0] + span * f)
        o = _plane((math.cos(a), math.sin(a)), int(round(u['uC3'][2])))
        return tuple(x * u['uC2'][3] for x in o), o
    if mode == 2:
        k = i - (0.5 * (n - 1) if u['uC1'][3] > 0.5 else 0.0)
        off = u['uC4'][:3]
        return tuple(x * k for x in off), (_norm(off) if any(off) else (0.0, 0.0, 0.0))
    if mode == 3:
        shape = int(round(u['uC4'][3]))
        f = i / float(n - 1) if n > 1 else 0.0
        t = u['uC5'][2] + (u['uC5'][3] - u['uC5'][2]) * f + u['uC6'][0]
        if shape in (0, 2):
            t = _fract(t)
        pos = path_point(t, shape, u, pts)
        a, b = path_point(t + 1e-3, shape, u, pts), path_point(t - 1e-3, shape, u, pts)
        d = tuple(x - y for x, y in zip(a, b))
        return pos, (_norm(d) if math.sqrt(sum(x * x for x in d)) > 1e-9 else (0.0, 0.0, 0.0))
    if mode == 4:
        npts = len(pts or [])
        step = max(int(round(u['uC6'][2])), 1)
        pos = pts_at(pts or [(0.0, 0.0, 0.0)], float(min(i * step, max(npts - 1, 0))))
        return pos, (_norm(pos) if any(pos) else (0.0, 0.0, 0.0))
    s = (int(u['uC0'][3]) * 7919) & M32
    pos = tuple((h01(i, s + k) - 0.5) * u['uC7'][k - 1] for k in (1, 2, 3))
    return pos, (_norm(pos) if any(pos) else (0.0, 0.0, 0.0))


def clone_ref(i, u, pts=None, w=0.0, grad=(0.0, 0.0, 0.0), map_rgb=None):
    """The 5 texels of clone i (mirror of gen_clone_layout.glsl main). w / grad = the effector weight / gradient at
    the clone (0 = no effectors); map_rgb = the map TOP's rgb at the clone's uv (None = white)."""
    n = int(round(u['uC0'][1]))
    if i >= n:
        return [(0.0,) * 4] * TEXELS
    seed = (int(u['uC0'][3]) * 7919) & M32
    p0, d = layout_ref(i, n, u, pts)
    tmode = int(round(u['uM4'][3]))
    toff = h01(i, seed + 11) * u['uM4'][2] * n if tmode == 1 else \
        (math.sqrt(sum(x * x for x in p0)) * u['uM4'][2] if tmode == 2 else i * u['uM4'][2])
    tl = u['uC7'][3] - toff / 60.0
    rot = [u['uM0'][k] * i for k in range(3)]
    us = u['uM6'][0] * max(1.0 + u['uM0'][3] * i, 0.0)
    hue = u['uM1'][0] * i
    hr = [h01(i, seed + k) - 0.5 for k in (4, 5, 6)]
    hq = [h01(i, seed + k) - 0.5 for k in (7, 8, 9)]
    hs = h01(i, seed + 10) - 0.5
    pos = [p0[k] + 2.0 * hr[k] * u['uM2'][k] for k in range(3)]
    rot = [rot[k] + 2.0 * hq[k] * u['uM3'][k] for k in range(3)]
    us *= max(1.0 + 2.0 * hs * u['uM1'][2], 0.0)
    hue += hs * u['uM1'][1]
    if u['uM4'][0] != 0.0 or u['uM4'][1] != 0.0 or u['uM1'][3] != 0.0:
        npnt = (p0[0] * u['uM2'][3], p0[1] * u['uM2'][3], p0[2] * u['uM2'][3] + tl * u['uM3'][3])
        nv = [vnoise(npnt, seed + k) - 0.5 for k in (21, 22, 23)]
        pos = [pos[k] + 2.0 * nv[k] * u['uM4'][0] for k in range(3)]
        rot = [rot[k] + 2.0 * nv[k] * u['uM4'][1] for k in range(3)]
        us *= max(1.0 + 2.0 * nv[0] * u['uM1'][3], 0.0)
    sc = tuple(u['uM7'][:3])
    col = list(hue_rot(tuple(u['uM5'][:3]), hue)) + [u['uM5'][3]]
    if w > 0.0:
        pos = [pos[k] + w * (u['uEffA'][k] + grad[k] * u['uEffA'][3]) for k in range(3)]
        rot = [rot[k] + w * u['uEffB'][k] for k in range(3)]
        us *= max(1.0 + u['uEffB'][3] * w, 0.0)
        m = min(max(w * u['uEffC'][3], 0.0), 1.0)
        col = [col[k] + (u['uEffC'][k] - col[k]) * m for k in range(3)] + [col[3]]
        toff += w * u['uEffD'][0]
    mm = int(round(u['uM6'][1]))
    if mm > 0 and u['uM6'][2] != 0.0:
        rgb = map_rgb or (1.0, 1.0, 1.0)
        if mm in (1, 3):
            a = min(max(u['uM6'][2], 0.0), 1.0)
            col = [col[k] + (col[k] * rgb[k] - col[k]) * a for k in range(3)] + [col[3]]
        if mm in (2, 3):
            lum = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
            us *= max(1.0 + u['uM6'][2] * (lum - 1.0), 0.0)
    hidden = 1.0 if (u['uEffD'][1] > 0.0 and w >= u['uEffD'][1]) else 0.0
    if hidden:
        us = 0.0
    q = qeuler(rot)
    if u['uC3'][3] > 0.5 and any(d):
        ax = int(round(u['uC6'][3]))
        a = (1.0, 0.0, 0.0) if ax == 0 else ((0.0, 0.0, 1.0) if ax == 2 else (0.0, 1.0, 0.0))
        q = qmul(qfromto(a, _norm(d)), q)
    col = [min(max(x, 0.0), 1.0) for x in col]
    return [tuple(pos) + (us,), tuple(q), tuple(col), sc + (max(toff, 0.0),), (w, float(i), hidden, 0.0)]


def vertex_ref(tex, local, card_aspect=None):
    """World position of a local vertex of a clone (tex = clone_ref's 5 texels; mirror of the vertex shader)."""
    t0, t1, _t2, t3 = tex[0], tex[1], tex[2], tex[3]
    ql = math.sqrt(sum(x * x for x in t1))
    q = tuple(x / ql for x in t1) if ql > 1e-8 else (1.0, 0.0, 0.0, 0.0)
    s = [t3[k] * t0[3] for k in range(3)]
    if card_aspect is not None:
        s[0] *= card_aspect
    r = qrot(q, tuple(local[k] * s[k] for k in range(3)))
    return tuple(t0[k] + r[k] for k in range(3))


def ring_slice(toff, depth, order='newestlast'):
    """Texture 3D slice the pixel shader samples for a time offset (frames)."""
    k = min(max(math.floor(toff + 0.5), 0), depth - 1)
    return k if order == 'newestfirst' else depth - 1 - k


# ------------------------------------------------------------------------------------------------ path points
def pts_resample(pts, samples, closed=False):
    """Even arc-length resample of a polyline (list of xyz) to `samples` points (Script CHOP pts_chop, Pathshape
    points). Fewer than 2 points -> as given."""
    if len(pts) < 2 or samples < 2:
        return [tuple(p) for p in pts]
    P = [tuple(float(x) for x in p) for p in pts]
    if closed:
        P = P + [P[0]]
    seg = [math.sqrt(sum((b[k] - a[k]) ** 2 for k in range(3))) for a, b in zip(P, P[1:])]
    total = sum(seg)
    if total <= 0:
        return [P[0]] * samples
    out, j, acc = [], 0, 0.0
    for s in range(samples):
        d = total * s / float(samples - (0 if closed else 1))
        while j < len(seg) - 1 and acc + seg[j] < d:
            acc += seg[j]
            j += 1
        f = 0.0 if seg[j] <= 0 else min(max((d - acc) / seg[j], 0.0), 1.0)
        out.append(tuple(P[j][k] + (P[j + 1][k] - P[j][k]) * f for k in range(3)))
    return out


# ------------------------------------------------------------------------------------------------ live check helper
def uniforms_of(g):
    """TD runtime: the clones TOP's current vec4 uniform values by name (read from its pars, no GPU readback)."""
    out = {}
    for k in range(int(g.seq.vec.numBlocks)):
        nm = getattr(g.par, 'vec%dname' % k).eval()
        if nm:
            out[nm] = [float(getattr(g.par, 'vec%dvalue%s' % (k, a)).eval()) for a in 'xyzw']
    return out


def compare(c, limit=4096, pts=None):
    """TD runtime (LIVE CHECKS C3-C6): max |GPU - mirror| over the first `limit` clones, effectors off (w = 0),
    map off. Reads clones.numpyArray() once (a readback: run it in its own exec, T-117). pts = point list for
    points / points-path modes (else the mirror has none). Returns (max diff, worst clone, worst texel, n)."""
    g = c.op('clones')
    u = uniforms_of(g)
    a = g.numpyArray()                     # rows bottom-first = texture y
    n = int(round(u['uC0'][1]))
    cwv = int(round(u['uC0'][2]))
    worst = (0.0, -1, -1)
    for i in range(min(n, limit)):
        ref = clone_ref(i, u, pts=pts)
        y, x0 = i // cwv, TEXELS * (i % cwv)
        for k in range(TEXELS):
            got = a[y, x0 + k]
            for j in range(4):
                d = abs(float(got[j]) - ref[k][j])
                if k == 1:                     # q and -q are the same rotation
                    d = min(d, abs(float(got[j]) + ref[k][j]))
                if d > worst[0]:
                    worst = (d, i, k)
    return worst + (n,)
