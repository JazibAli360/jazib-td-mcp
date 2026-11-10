"""gen_interactive_linevolume_logic - the solids and the float64 twin of GEN_interactive 'linevolume'
(builders/glsl/gen_interactive_linevolume.glsl): line-volume light sculpture (wire solids, hatch sphere, relief grid,
moire planes) as hairlines of light. One stateless pass; this file predicts any pixel from the uniforms read live
(U = {name: (x, y, z, w)}), the points texture, the mask and the slot input. Arrays are [y, x, 4] with y = 0 the
BOTTOM row (TD texel space, T-58). numpy imported inside functions. ASCII only."""
import math
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SCENES = ['wire', 'hatch', 'relief', 'moire']
SOLIDS = ['tetra', 'cube', 'octa', 'icosa', 'dodeca']
HEIGHTSOURCES = ['mask', 'luma', 'noise']
FOLLOWMODES = ['first', 'centroid']
EDGE_COUNTS = {'tetra': 6, 'cube': 12, 'octa': 12, 'icosa': 30, 'dodeca': 30}
MAXNEST = 8
MAXROWS = 512
MAXPTS = 256
_GI = {}


def gi():
    if not _GI:
        with open(os.path.join(HERE, 'gen_interactive_logic.py')) as fh:
            exec(fh.read(), _GI)
    return _GI


def _np():
    import numpy
    return numpy


# ------------------------------------------------------------------ solids (unit circumradius)
def solid_vertices(name):
    phi = (1 + math.sqrt(5)) / 2
    if name == 'tetra':
        v = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    elif name == 'cube':
        v = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    elif name == 'octa':
        v = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    elif name == 'icosa':
        v = []
        for a in (-1, 1):
            for b in (-phi, phi):
                v += [(0, a, b), (a, b, 0), (b, 0, a)]
    else:
        v = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
        ip = 1 / phi
        for a in (-ip, ip):
            for b in (-phi, phi):
                v += [(0, a, b), (a, b, 0), (b, 0, a)]
    out = []
    for p in v:
        n = math.sqrt(sum(c * c for c in p))
        out.append(tuple(c / n for c in p))
    return out


def solid_edges(verts):
    """Edges = vertex pairs at the minimum distance (exact for the five Platonic solids)."""
    n = len(verts)
    d = lambda i, j: math.sqrt(sum((verts[i][k] - verts[j][k]) ** 2 for k in range(3)))
    dmin = min(d(i, j) for i in range(n) for j in range(i + 1, n))
    return [(i, j) for i in range(n) for j in range(i + 1, n) if d(i, j) < dmin * 1.001]


_TABLE = []


def solid_table():
    """(all vertices, all edges with global indices, ranges [(v0, nv, e0, ne)] per solid in SOLIDS order)."""
    if _TABLE:
        return _TABLE[0]
    V, E, R = [], [], []
    for s in SOLIDS:
        v = solid_vertices(s)
        e = solid_edges(v)
        R.append((len(V), len(v), len(E), len(e)))
        E += [(a + len(V), b + len(V)) for a, b in e]
        V += v
    _TABLE.append((V, E, R))
    return V, E, R


def glsl_solids():
    """The const arrays the shader's `// %SOLIDS%` line is replaced with (== solid_table)."""
    V, E, R = solid_table()
    f = lambda x: '%.9f' % x
    lines = ['const vec3 LV_V[%d] = vec3[%d](%s);' % (len(V), len(V), ', '.join(
        'vec3(%s, %s, %s)' % tuple(f(c) for c in v) for v in V)),
        'const ivec2 LV_E[%d] = ivec2[%d](%s);' % (len(E), len(E), ', '.join('ivec2(%d, %d)' % e for e in E)),
        'const ivec4 LV_R[%d] = ivec4[%d](%s);' % (len(R), len(R), ', '.join('ivec4(%d, %d, %d, %d)' % r for r in R))]
    return '\n'.join(lines)


# ------------------------------------------------------------------ uniforms (offline twin of the TD expressions)
def defaults():
    return dict(Amount=1.0, Scene=0, Solid=3, Nest=1, Nestscale=0.6, Size=0.6, Dist=3.0, Fov=40.0, Rotx=20.0,
                Roty=0.0, Rotz=0.0, Spinx=0.0, Spiny=20.0, Spinz=0.0, Kick=30.0, Phase=0.0, Posx=0.0, Posy=0.0,
                Follow=0.0, Followrot=0.0, Followmode=0, Linewidth=1.5, Glow=0.4, Glowwidth=6.0, Depthfade=0.6,
                Hatchdensity=40.0, Hatchangle=0.0, Crosshatch=0, Hatchcontrast=1.0, Lightaz=45.0, Lightel=30.0, Rim=1,
                Reveal=0.0, Revealinvert=0, Rows=48, Gridwidth=1.2, Tilt=60.0, Height=0.25, Heightsource=2,
                Noisescale=3.0, Noisespeed=0.3, Occlude=1, Spacing=10.0, Moireangle=2.0, Moirescale=0.02, Drift=5.0,
                Colourspread=1.0, Seed=1, Speed=1.0, Beatgain=0.0, Beatdecay=0.25, Audiogain=0.0, Manual=0.0,
                Palette=0, Palshift=0.0, Blend=2, Colora=(0.75, 0.9, 1.0), Colorb=(1.0, 1.0, 1.0))


def light_dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return (math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a))


def uniforms(P, T, drive=(0.0, 120.0, 0.0, 0.0)):
    """{uniform: 4-tuple} the module's expressions give for pars P at module time T (clock_int + Phase)."""
    r = math.radians
    lx, ly, lz = light_dir(P['Lightaz'], P['Lightel'])
    U = {'uA': (P['Scene'], P['Solid'], P['Nest'], P['Nestscale']),
         'uB': (P['Size'], P['Dist'], 0.5 / math.tan(r(P['Fov']) * 0.5), P['Follow']),
         'uRot': (r(P['Rotx'] + P['Spinx'] * T), r(P['Roty'] + P['Spiny'] * T), r(P['Rotz'] + P['Spinz'] * T),
                  r(P['Kick'])),
         'uPos': (P['Posx'], P['Posy'], P['Followrot'], P['Followmode']),
         'uLn': (P['Linewidth'], P['Glow'], P['Glowwidth'], P['Depthfade']),
         'uHt': (P['Hatchdensity'], r(P['Hatchangle']), P['Crosshatch'], P['Hatchcontrast']),
         'uLt': (lx, ly, lz, P['Rim']),
         'uRl': (P['Rows'], P['Gridwidth'], r(P['Tilt']), P['Height']),
         'uRl2': (P['Heightsource'], P['Noisescale'], P['Noisespeed'] * T, P['Occlude']),
         'uMo': (P['Spacing'], r(P['Moireangle']), P['Moirescale'], P['Drift'] * T),
         'uMisc': (P['Reveal'], P['Revealinvert'], P['Colourspread'], P['Seed']),
         'uDrv': tuple(drive),
         'uDg': (P['Beatgain'], P['Beatdecay'], P['Audiogain'], P['Manual']),
         'uLook': (P['Blend'], P['Palette'], P['Palshift'], P['Amount']),
         'uCa': tuple(P['Colora']) + (0.0,), 'uCb': tuple(P['Colorb']) + (0.0,)}
    return dict((k, tuple(float(x) for x in v)) for k, v in U.items())


# ------------------------------------------------------------------ maths shared with the shader
def rot_matrix(rx, ry, rz):
    """R = Rz Ry Rx (row-major 3x3): X' = R X."""
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]]
    Ry = [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]
    Rz = [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    mul = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(Rz, mul(Ry, Rx))


def mv(Rm, v):
    return tuple(sum(Rm[i][k] * v[k] for k in range(3)) for i in range(3))


def project(X, D, f, off, W, H):
    """View point X (camera at (0, 0, D) looking down -z) -> (px x, px y, depth z); off in screen heights."""
    den = max(D - X[2], 1e-3)
    return (W * 0.5 + off[0] * H + X[0] * f / den * H, H * 0.5 + off[1] * H + X[1] * f / den * H, X[2])


def segdist(p, a, b):
    pax, pay, bax, bay = p[0] - a[0], p[1] - a[1], b[0] - a[0], b[1] - a[1]
    bb = bax * bax + bay * bay
    h = min(max((pax * bax + pay * bay) / bb, 0.0), 1.0) if bb > 1e-12 else 0.0
    return math.hypot(pax - bax * h, pay - bay * h), h


def _fetch(img, uv):
    """Nearest texel at uv (0..1, y up) == texelFetch(ivec2(uv * size)) clamped."""
    if img is None:
        return (0.0, 0.0, 0.0, 0.0)
    h, w = img.shape[0], img.shape[1]
    x = min(max(int(math.floor(uv[0] * w)), 0), w - 1)
    y = min(max(int(math.floor(uv[1] * h)), 0), h - 1)
    return tuple(float(v) for v in img[y, x])


def follow(U, pts, W, H):
    """(offset (x, y) screen heights, rx add, ry add) from the points (first present or centroid)."""
    off = [U['uPos'][0], U['uPos'][1]]
    pr = [q for q in (pts or [])[:MAXPTS] if q[0] > -1.0]
    if not pr:
        return off, 0.0, 0.0
    if int(U['uPos'][3] + 0.5) == 1:
        px = sum(q[0] for q in pr) / len(pr)
        py = sum(q[1] for q in pr) / len(pr)
    else:
        px, py = pr[0][0], pr[0][1]
    fo, fr = U['uB'][3], U['uPos'][2]
    off[0] += fo * (px * W - 0.5 * W) / H
    off[1] += fo * (py * H - 0.5 * H) / H
    return off, -fr * math.pi * (py - 0.5), fr * math.pi * (px - 0.5)


def _band_px(d, w):
    return min(max(0.5 + 0.5 * w - d, 0.0), 1.0)


def shade(x, y, U, W, H, pts=None, mask=None, src=None):
    """(key of the light, line coverage best, glow sum) at pixel centre (x, y) px - before colour / blend."""
    G = gi()
    gs = G['gs']()
    scene = int(U['uA'][0] + 0.5)
    size, D, f = U['uB'][0], U['uB'][1], U['uB'][2]
    off, arx, ary = follow(U, pts, W, H)
    env = G['env'](U['uDrv'][0], U['uDrv'][1], U['uDg'][0], U['uDg'][1])
    lvl = G['level'](U['uDrv'][2], U['uDg'][2], U['uDg'][3])
    rx, ry, rz = U['uRot'][0] + arx, U['uRot'][1] + ary + U['uRot'][3] * env, U['uRot'][2]
    lw, glow, gw, dfade = U['uLn'][0], U['uLn'][1] * (1.0 + lvl), max(U['uLn'][2], 1e-3), U['uLn'][3]
    best, key, gsum, dmin = 0.0, 0.0, 0.0, 1e30
    p = (x, y)
    if scene == 0:
        V, E, R = solid_table()
        v0, nv, e0, ne = R[min(max(int(U['uA'][1] + 0.5), 0), len(R) - 1)]
        Rm = rot_matrix(rx, ry, rz)
        nest = min(max(int(U['uA'][2] + 0.5), 1), MAXNEST)
        sc = size
        for _k in range(nest):
            pv = [project(tuple(c * sc for c in mv(Rm, V[v0 + i])), D, f, off, W, H) for i in range(nv)]
            for e in range(ne):
                a, b = pv[E[e0 + e][0] - v0], pv[E[e0 + e][1] - v0]
                d, h = segdist(p, a, b)
                z = a[2] + (b[2] - a[2]) * h
                zz = min(max(z / max(sc, 1e-6), -1.0), 1.0)
                fd = 1.0 - dfade * (0.5 - 0.5 * zz)
                v = fd * _band_px(d, lw)
                if v > best:
                    best = v
                if d < dmin:
                    dmin, key = d, 0.5 + 0.5 * zz
                if glow > 0:
                    gsum += fd * glow * math.exp(-d / gw)
            sc *= U['uA'][3]
    elif scene == 1:
        sx = (x - 0.5 * W) / H - off[0]
        sy = (y - 0.5 * H) / H - off[1]
        dl = math.sqrt(sx * sx + sy * sy + f * f)
        d = (sx / dl, sy / dl, -f / dl)
        bq = D * d[2]
        c = D * D - size * size
        disc = bq * bq - c
        dist = math.sqrt(max(D * D - bq * bq, 0.0))
        if U['uLt'][3] > 0.5:
            rim = abs(dist - size) * f * H / D
            v = _band_px(rim, lw)
            if v > best:
                best, key = v, 1.0
            if glow > 0:
                gsum += glow * math.exp(-rim / gw)
        if disc > 0:
            t = -bq - math.sqrt(disc)
            X = (t * d[0], t * d[1], D + t * d[2])
            n = (X[0] / size, X[1] / size, X[2] / size)
            L = U['uLt'][:3]
            sh = max(n[0] * L[0] + n[1] * L[1] + n[2] * L[2], 0.0)
            Rm = rot_matrix(rx, ry, rz)
            loc = tuple(sum(Rm[k][i] * X[k] for k in range(3)) for i in range(3))      # R^T X
            ha = U['uHt'][1]
            kk = U['uHt'][0] / max(2.0 * size, 1e-6)
            nv_ = max(abs(n[0] * d[0] + n[1] * d[1] + n[2] * d[2]), 0.2)
            aa = max(kk * (D - X[2]) / (f * H) / nv_, 1e-4)
            duty = min(max(0.5 + (sh - 0.5) * U['uHt'][3], 0.0), 1.0)
            u1 = (loc[0] * math.cos(ha) + loc[1] * math.sin(ha)) * kk
            b1 = min(max(0.5 + (duty * 0.5 - abs(u1 - math.floor(u1) - 0.5)) / aa, 0.0), 1.0)
            v = b1
            if U['uHt'][2] > 0.5:
                duty2 = min(max(2.0 * duty - 1.0, 0.0), 1.0)
                u2 = (-loc[0] * math.sin(ha) + loc[1] * math.cos(ha)) * kk
                v = max(v, min(max(0.5 + (duty2 * 0.5 - abs(u2 - math.floor(u2) - 0.5)) / aa, 0.0), 1.0))
            if v >= best:
                best, key = v, sh
    elif scene == 2:
        rows = min(max(int(U['uRl'][0] + 0.5), 1), MAXROWS)
        gwid, tilt = U['uRl'][1] * size, U['uRl'][2]
        hgt = U['uRl'][3] * (1.0 + lvl)
        hs, nsc, noff, occl = int(U['uRl2'][0] + 0.5), U['uRl2'][1], U['uRl2'][2], U['uRl2'][3] > 0.5
        ct, st = math.cos(tilt), math.sin(tilt)
        pad = 1.0 + lw + (gw * 6.0 if glow > 0 else 0.0)
        ymax = -1e30
        cy = 0.5 * H + off[1] * H
        sxx = (x - 0.5 * W) / H - off[0]
        lo_h, hi_h = min(0.0, hgt), max(0.0, hgt)
        py_at = lambda hh, z: cy + (hh * ct - z * st) * f / max(D - (hh * st + z * ct), 1e-3) * H
        for k in range(rows):
            t = k / float(rows - 1) if rows > 1 else 0.0
            z = size * (1.0 - 2.0 * t)
            den0 = max(D - z * ct, 1e-3)
            xw = sxx * den0 / f
            if abs(xw) > gwid:
                continue
            ya, yb = py_at(lo_h, z), py_at(hi_h, z)
            ylo, yhi = min(ya, yb), max(ya, yb)
            if occl and ylo > y + pad:
                break
            if yhi < y - pad:
                continue
            y0 = py_at(0.0, z)
            uv = (x / W, y0 / H)
            if hs == 0:
                hf = _fetch(mask, uv)[0]
            elif hs == 1:
                q = _fetch(src, uv)
                hf = 0.2126 * q[0] + 0.7152 * q[1] + 0.0722 * q[2]
            else:
                hf = float(gs['vnoise'](xw * nsc, z * nsc + noff, int(U['uMisc'][3])))
            py = py_at(hgt * hf, z)
            dd = abs(y - py)
            vis = min(max(py - ymax + 0.5, 0.0), 1.0) if occl else 1.0
            ymax = max(ymax, py)
            fd = 1.0 - dfade * t
            v = vis * fd * _band_px(dd, lw)
            if v > best:
                best = v
            if dd < dmin:
                dmin, key = dd, t
            if glow > 0:
                gsum += vis * fd * glow * math.exp(-dd / gw)
    else:
        sp, ang, msc, drift = max(U['uMo'][0], 1e-3), rz + U['uRot'][3] * env, U['uMo'][2], U['uMo'][3]
        qx, qy = x - (0.5 * W + off[0] * H), y - (0.5 * H + off[1] * H)
        for g in range(2):
            a = ang + (U['uMo'][1] if g == 1 else 0.0)
            s_ = sp * (1.0 + msc) if g == 1 else sp
            u = (qx * math.cos(a) + qy * math.sin(a) + (drift if g == 0 else -drift)) / s_
            dpx = abs(u + 0.5 - math.floor(u + 0.5) - 0.5) * s_
            v = _band_px(dpx, lw)
            if v > best:
                best = v
            if dpx < dmin:
                dmin, key = dpx, float(g)
            if glow > 0:
                gsum += glow * math.exp(-dpx / gw)
    rv = U['uMisc'][0]
    if rv != 0.0:
        pres = _fetch(mask, (x / W, y / H))[0]
        if U['uMisc'][1] > 0.5:
            pres = 1.0 - pres
        k_ = 1.0 + (pres - 1.0) * rv
        best *= k_
        gsum *= k_
    return key, best, gsum


def pixel(x, y, U, W, H, base, pts=None, mask=None, src=None):
    """rgba the pass writes at texel (x, y) (TD coords, y up) over base [H, W, 4]."""
    np = _np()
    gs = gi()['gs']()
    key, best, gsum = shade(x + 0.5, y + 0.5, U, W, H, pts, mask, src)
    c = gs['palette'](np.array([key * U['uMisc'][2]]), int(U['uLook'][1] + 0.5), U['uCa'][:3], U['uCb'][:3],
                      U['uLook'][2])[0]
    col = c * (best + gsum)
    a = min(max(best + gsum * (0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]), 0.0), 1.0)
    b = np.asarray(base[y, x], dtype=np.float64)[None, :]
    return gs['blend'](b, col[None, :], np.array([a]), int(U['uLook'][0] + 0.5), U['uLook'][3])[0]


def sample_points(W, H, n=200, seed=7):
    import random
    r = random.Random(seed)
    return [(r.randrange(W), r.randrange(H)) for _ in range(n)]
