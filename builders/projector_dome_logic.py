# projector_dome_logic - pure maths for LK_projection_room (projector planner + fulldome mode).
# No td imports: copied into the COMP as Text DAT `pd_logic`; tests: test/test_projector_dome.py.
# Specs: docs/research/AT_projector_coverage.md (formulas, recipe 6) and AW_fulldome_simulator.md (section 5, 7).
# Clean-room: ideas from asterix "Projector Coverage Tool" (par vocabulary only, paid, never obtained) and
# Theinfranet "Fulldome Simulator" (no licence, never loaded); test chart / rings are our own.
#
# Conventions (probed live on TD 2025.31550, 26 Oct 2026, see docs/builds/projector_dome.md):
# - Light COMP projmapmode simplehorzfov: projangle = full horizontal FOV across the projection map width; the
#   map's own aspect sets the height. useview + custommatrix ignored the matrix DAT, so lens shift is modelled
#   by padding: the light gets a wider symmetric frustum and the image sits off-centre inside a black canvas
#   (exact for a pinhole projector).
# - Camera COMP winx / winy: window shift in fractions of the frame width / height (+ = window moves right / up,
#   so the scene moves left / down). Through-projector camera: winx = Shifth/100, winy = Shiftv/100.
# - TD rotation order xyz: M = Rz * Ry * Rx; cameras / lights look down -Z.
# - Lens shift sh, sv: fraction of image width / height; + = image moves right / up off the lens axis.
import math

RES_PRESETS = [('custom', 'Custom'), ('wxga', '1280x800 WXGA'), ('hd', '1920x1080 HD'),
               ('wuxga', '1920x1200 WUXGA'), ('uhd', '3840x2160 UHD'), ('dci4k', '4096x2160 DCI 4K')]
RES_SIZE = {'wxga': (1280, 800), 'hd': (1920, 1080), 'wuxga': (1920, 1200), 'uhd': (3840, 2160),
            'dci4k': (4096, 2160)}
LENSINPUT = [('ratio', 'Throw ratio'), ('angle', 'Cone angle (Throw, legacy)')]
FITMODES = [('fit', 'Fit (letterbox)'), ('fill', 'Fill (crop)'), ('stretch', 'Stretch')]
VIEWMODES = [('lit', 'Lit (projected)'), ('coverage', 'Coverage'), ('pixeldensity', 'Pixel density'),
             ('brightness', 'Brightness'), ('overlap', 'Overlap')]
CAMPRESETS = [('orbit', 'Orbit'), ('plan', 'Plan (top)'), ('front', 'Front'), ('side', 'Side'),
              ('audience', 'Audience eye'), ('proja', 'Through projector A'), ('projb', 'Through projector B')]
CAMPROJ = [('persp', 'Perspective'), ('ortho', 'Orthographic')]
UNITS = [('m', 'Metres'), ('ft', 'Feet')]
DOMEMODES = [('off', 'Off'), ('preview', 'Preview (inside the dome)'), ('domemaster', 'Domemaster out')]
INPUTFORMATS = [('flat', 'Flat image (window on the dome)'), ('domemaster', 'Domemaster (fisheye)'),
                ('equirect', 'Equirectangular 360'), ('scene', 'The room (fisheye render)')]
FT_PER_M = 3.280839895
LUX_TO_NITS = 1.0 / math.pi          # diffuse screen: L = E * gain / pi
NITS_PER_FL = 3.426


def menu_index(menu, name):
    for i, (k, _) in enumerate(menu):
        if k == name:
            return i
    return 0


# ---------------------------------------------------------------- optics
def throw_from_angle(deg):
    """Full horizontal cone angle (degrees) -> throw ratio D/W."""
    a = math.radians(max(min(float(deg), 179.0), 0.01))
    return 1.0 / (2.0 * math.tan(a / 2.0))


def hfov(T):
    return 2.0 * math.degrees(math.atan(1.0 / (2.0 * T)))


def vfov(T, resx, resy):
    return 2.0 * math.degrees(math.atan(resy / (2.0 * resx * T)))


def image_size(D, T, resx, resy):
    W = D / T
    H = W * resy / float(resx)
    return W, H, math.hypot(W, H)


def resolution(preset, resx, resy):
    return RES_SIZE.get(preset, (int(resx), int(resy)))


def throw_ratio(lensinput, throwratio, coneangle):
    return throw_from_angle(coneangle) if lensinput == 'angle' else max(float(throwratio), 1e-3)


def cos_axis(T, ar, sh, sv):
    """cos of the angle between the lens axis and the ray through the image centre (lens shift)."""
    x = sh / T
    y = sv / (T * ar)
    return 1.0 / math.sqrt(1.0 + x * x + y * y)


def px_per_m(T, resx, d, cos_n=1.0, cos_f=1.0):
    """Pixels per metre on a surface (coarsest direction): pinhole projector, uniform pixels in tan space.
    d = distance projector -> point, cos_n = cos(surface normal, -ray), cos_f = cos(ray, lens axis).
    Perpendicular wall at depth z: = T*resx/z everywhere (cos_n = cos_f)."""
    if d <= 0 or cos_n <= 0:
        return 0.0
    return T * resx * cos_n / (d * cos_f * cos_f)


def lux(lumens, T, resx, resy, d, cos_n=1.0, cos_f=1.0):
    """Illuminance (lux) of a uniform image: lumens over the image area at depth z, per area stretch.
    Perpendicular wall at depth z: lumens * T^2 * ar / z^2 everywhere."""
    if d <= 0 or cos_n <= 0:
        return 0.0
    ar = resx / float(resy)
    return lumens * T * T * ar * cos_n / (d * d * cos_f ** 3)


def nits(lux_value, gain=1.0):
    return lux_value * gain * LUX_TO_NITS


def foot_lamberts(nits_value):
    return nits_value / NITS_PER_FL


def ppi(ppm):
    return ppm / 39.37007874


def mm_per_px(ppm):
    return 1000.0 / ppm if ppm > 0 else 0.0


# ---------------------------------------------------------------- lens shift via a padded projection map
def canvas(T, sh, sv, resx, resy, mapres):
    """Light COMP map for lens shift: symmetric frustum wide enough for the shifted image, image placed off-centre.
    Returns projangle (deg), canvas w, h (px) and the image rect (u0, v0, u1, v1) inside the canvas (0..1)."""
    fx = 1.0 + 2.0 * abs(sh)
    fy = 1.0 + 2.0 * abs(sv)
    ang = 2.0 * math.degrees(math.atan(fx / (2.0 * T)))
    w = max(int(round(mapres)), 8)
    h = max(int(round(w * fy * resy / (fx * float(resx)))), 8)
    cu = 0.5 + sh / fx
    cv = 0.5 + sv / fy
    hw = 0.5 / fx
    hh = 0.5 / fy
    return {'projangle': ang, 'w': w, 'h': h, 'rect': (cu - hw, cv - hh, cu + hw, cv + hh)}


# ---------------------------------------------------------------- transforms
def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return [[1, 0, 0], [0, c, -s], [0, s, c]]


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, 0, s], [0, 1, 0], [-s, 0, c]]


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _mm(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _mv(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def rotation(rx, ry, rz=0.0):
    """TD default rord xyz: M = Rz * Ry * Rx (degrees)."""
    return _mm(_rz(math.radians(rz)), _mm(_ry(math.radians(ry)), _rx(math.radians(rx))))


def basis(rx, ry, rz=0.0):
    """Right, up, forward (= -Z) unit vectors of a camera / light with these rotations."""
    m = rotation(rx, ry, rz)
    R = _mv(m, (1, 0, 0))
    U = _mv(m, (0, 1, 0))
    F = _mv(m, (0, 0, -1))
    return R, U, F


def look_angles(d):
    """(rx, ry) degrees so that -Z points along direction d (inverse of basis F)."""
    x, y, z = d
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    x, y, z = x / n, y / n, z / n
    return math.degrees(math.asin(max(-1.0, min(1.0, y)))), math.degrees(math.atan2(-x, -z))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


# ---------------------------------------------------------------- projectors
def projector(on, pos, rx, ry, T, resx, resy, lumens, sh, sv, gain=1.0):
    R, U, F = basis(rx, ry)
    return {'on': bool(on), 'pos': tuple(pos), 'rx': rx, 'ry': ry, 'R': R, 'U': U, 'F': F, 'T': T,
            'resx': resx, 'resy': resy, 'lumens': lumens, 'sh': sh, 'sv': sv, 'gain': gain}


def project(pj, P):
    """World point -> (u, v, z, d) in the projector's image (0..1 inside), z = depth along the lens axis."""
    v = _sub(P, pj['pos'])
    z = _dot(v, pj['F'])
    d = math.sqrt(_dot(v, v))
    if z <= 1e-9:
        return None
    ar = pj['resx'] / float(pj['resy'])
    u = _dot(v, pj['R']) / z * pj['T'] + 0.5 - pj['sh']
    w = _dot(v, pj['U']) / z * pj['T'] * ar + 0.5 - pj['sv']
    return u, w, z, d


def probe_point(pj, P, n):
    """Python twin of the GLSL MAT probe(): (covered, px per m, lux) at world point P with unit normal n."""
    if not pj['on']:
        return 0.0, 0.0, 0.0
    q = project(pj, P)
    if q is None:
        return 0.0, 0.0, 0.0
    u, w, z, d = q
    if u < 0 or u > 1 or w < 0 or w > 1:
        return 0.0, 0.0, 0.0
    L = tuple(c / d for c in _sub(P, pj['pos']))
    cn = max(-_dot(n, L), 0.0)
    if cn <= 0:
        return 0.0, 0.0, 0.0
    cf = z / d
    return (1.0, px_per_m(pj['T'], pj['resx'], d, cn, cf),
            lux(pj['lumens'], pj['T'], pj['resx'], pj['resy'], d, cn, cf))


def uniforms(projs):
    """vec4 rows for the GLSL MATs (6 per projector): pos+on, R, U, F, (T resx resy lumens), (sh sv gain 0)."""
    rows = []
    for pj in projs:
        rows.append(tuple(pj['pos']) + (1.0 if pj['on'] else 0.0,))
        rows.append(tuple(pj['R']) + (0.0,))
        rows.append(tuple(pj['U']) + (0.0,))
        rows.append(tuple(pj['F']) + (0.0,))
        rows.append((float(pj['T']), float(pj['resx']), float(pj['resy']), float(pj['lumens'])))
        rows.append((float(pj['sh']), float(pj['sv']), float(pj['gain']), 0.0))
    return rows


def frustum_segments(pj, length):
    """8 line segments (apex -> 4 corners, 4 rim edges) of the image frustum at depth `length`."""
    if length <= 0:
        return []
    T, ar, sh, sv = pj['T'], pj['resx'] / float(pj['resy']), pj['sh'], pj['sv']
    P, R, U, F = pj['pos'], pj['R'], pj['U'], pj['F']
    xs = ((-0.5 + sh) / T, (0.5 + sh) / T)
    ys = ((-0.5 + sv) / (T * ar), (0.5 + sv) / (T * ar))
    corners = []
    for x, y in ((xs[0], ys[0]), (xs[1], ys[0]), (xs[1], ys[1]), (xs[0], ys[1])):
        corners.append(tuple(P[i] + length * (F[i] + x * R[i] + y * U[i]) for i in range(3)))
    segs = [(tuple(P), c) for c in corners]
    segs += [(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    return segs


# ---------------------------------------------------------------- rig state (what the Script CHOPs output)
def _f(p, k, d=0.0):
    try:
        return float(p.get(k, d))
    except (TypeError, ValueError):
        return d


def rig(p):
    """p = dict of the COMP's custom par values (Readouts page excluded). Returns projectors, camera pose, map sizes."""
    T = throw_ratio(p.get('Lensinput', 'ratio'), _f(p, 'Throwratio', 1.5), _f(p, 'Throw', 43.4))
    resx, resy = resolution(p.get('Respreset', 'custom'), _f(p, 'Resx', 1920), _f(p, 'Resy', 1080))
    resx, resy = max(int(resx), 1), max(int(resy), 1)
    A = projector(True, (_f(p, 'Projx'), _f(p, 'Projy', 2.0), _f(p, 'Projz', 6.0)), _f(p, 'Projtilt'),
                  _f(p, 'Projpan'), T, resx, resy, _f(p, 'Lumens', 6000), _f(p, 'Shifth') / 100.0,
                  _f(p, 'Shiftv') / 100.0, _f(p, 'Gain', 1.0))
    TB = max(_f(p, 'Projbthrow', T), 1e-3)
    B = projector(bool(p.get('Projbon', False)), (_f(p, 'Projbx', 2.5), _f(p, 'Projby', 2.0), _f(p, 'Projbz', 6.0)),
                  _f(p, 'Projbtilt'), _f(p, 'Projbpan'), TB, resx, resy, _f(p, 'Projblumens', 6000),
                  _f(p, 'Projbshifth') / 100.0, _f(p, 'Projbshiftv') / 100.0, _f(p, 'Gain', 1.0))
    mapres = max(_f(p, 'Mapres', 1024), 8)
    ca = canvas(A['T'], A['sh'], A['sv'], resx, resy, mapres)
    cb = canvas(B['T'], B['sh'], B['sv'], resx, resy, mapres)
    cam = cam_pose(p, A, B)
    sres = max(int(_f(p, 'Shadowres', 384)), 16)
    ch = {
        'pa_T': A['T'], 'pa_hfov': hfov(A['T']), 'pa_vfov': vfov(A['T'], resx, resy), 'resx': resx, 'resy': resy,
        'pa_projangle': ca['projangle'], 'pa_mapw': ca['w'], 'pa_maph': ca['h'],
        'pa_u0': ca['rect'][0], 'pa_v0': ca['rect'][1], 'pa_u1': ca['rect'][2], 'pa_v1': ca['rect'][3],
        'pb_on': 1.0 if B['on'] else 0.0, 'pb_T': B['T'], 'pb_hfov': hfov(B['T']),
        'pb_projangle': cb['projangle'], 'pb_mapw': cb['w'], 'pb_maph': cb['h'],
        'pb_u0': cb['rect'][0], 'pb_v0': cb['rect'][1], 'pb_u1': cb['rect'][2], 'pb_v1': cb['rect'][3],
        'probe_w': sres, 'probe_h': max(int(round(sres * resy / float(resx))), 8),
    }
    for k, v in cam.items():
        ch['cam_' + k] = v
    return {'A': A, 'B': B, 'chans': ch, 'cam': cam}


def cam_pose(p, A, B):
    """Viewer camera for the preset. Orbit keeps the original LK_projection_room formula (around Lookx/Lookz)."""
    preset = p.get('Campreset', 'orbit')
    D = _f(p, 'Camdist', 10.0)
    a = math.radians(36.0 + _f(p, 'Orbit'))
    lx, ly, lz = _f(p, 'Lookx'), _f(p, 'Lookheight', 1.0), _f(p, 'Lookz')
    ortho = 1.0 if p.get('Camproj', 'persp') == 'ortho' else 0.0
    out = {'fov': _f(p, 'Camfov', 45.0), 'winx': _f(p, 'Camshiftx') / 100.0, 'winy': _f(p, 'Camshifty') / 100.0,
           'ortho': ortho, 'orthow': max(_f(p, 'Orthowidth', 10.0), 0.01)}
    if preset in ('proja', 'projb'):
        pj = A if preset == 'proja' else B
        out.update({'tx': pj['pos'][0], 'ty': pj['pos'][1], 'tz': pj['pos'][2], 'rx': pj['rx'], 'ry': pj['ry'],
                    'fov': hfov(pj['T']), 'winx': pj['sh'], 'winy': pj['sv'], 'ortho': 0.0})
        return out
    if preset == 'orbit':
        tx, ty, tz = lx + D * math.sin(a), _f(p, 'Height', 5.0), lz + D * math.cos(a)
        rx = -math.degrees(math.atan2(ty - ly, D))
        ry = math.degrees(a)
    elif preset == 'plan':
        tx, ty, tz, rx, ry = lx, ly + D, lz, -90.0, 0.0
    elif preset == 'front':
        tx, ty, tz, rx, ry = lx, ly, lz + D, 0.0, 0.0
    elif preset == 'side':
        tx, ty, tz, rx, ry = lx + D, ly, lz, 0.0, 90.0
    else:   # audience: eye height on the orbit circle, looking at the look point
        tx, ty, tz = lx + D * math.sin(a), _f(p, 'Eyeheight', 1.7), lz + D * math.cos(a)
        rx, ry = look_angles((lx - tx, ly - ty, lz - tz))
    out.update({'tx': tx, 'ty': ty, 'tz': tz, 'rx': rx, 'ry': ry})
    return out


# ---------------------------------------------------------------- readouts (probe values -> numbers)
def readouts(p, probe):
    """probe: dict a_ppm, a_d (image centre), a_avgppm, a_avgcov, a_maxmm (coarsest mm per px), b_ppm, b_d (b only if B on).
    Returns readout dict (metres, ppi, mm/px, lux, nits, fL)."""
    st = rig(p)
    A, B = st['A'], st['B']
    out = {'throwdist': 0.0, 'imgw': 0.0, 'imgh': 0.0, 'imgdiag': 0.0, 'hfov': hfov(A['T']),
           'vfov': vfov(A['T'], A['resx'], A['resy']), 'throwratio': A['T'], 'pxpm': 0.0, 'ppi': 0.0,
           'mmpx': 0.0, 'lux': 0.0, 'nits': 0.0, 'fl': 0.0, 'avgppi': 0.0, 'minppi': 0.0, 'coverage': 0.0,
           'b_throwdist': 0.0, 'b_ppi': 0.0, 'b_nits': 0.0}
    ar = A['resx'] / float(A['resy'])
    d = float(probe.get('a_d', 0.0))
    ppm = float(probe.get('a_ppm', 0.0))
    if d > 0:
        cf = cos_axis(A['T'], ar, A['sh'], A['sv'])
        z = d * cf
        W, H, Dg = image_size(z, A['T'], A['resx'], A['resy'])
        out.update({'throwdist': d, 'imgw': W, 'imgh': H, 'imgdiag': Dg})
        if ppm > 0:
            lx = A['lumens'] * A['T'] * ar * ppm / (A['resx'] * d * cf)
            out.update({'pxpm': ppm, 'ppi': ppi(ppm), 'mmpx': mm_per_px(ppm), 'lux': lx,
                        'nits': nits(lx, A['gain']), 'fl': foot_lamberts(nits(lx, A['gain']))})
    cov = float(probe.get('a_avgcov', 0.0))
    out['coverage'] = cov
    if cov > 0:
        out['avgppi'] = ppi(float(probe.get('a_avgppm', 0.0)) / cov)
    mx = float(probe.get('a_maxmm', 0.0))
    out['minppi'] = ppi(1000.0 / mx) if mx > 0 else 0.0
    if B['on']:
        bd, bp = float(probe.get('b_d', 0.0)), float(probe.get('b_ppm', 0.0))
        if bd > 0 and bp > 0:
            cf = cos_axis(B['T'], ar, B['sh'], B['sv'])
            lx = B['lumens'] * B['T'] * ar * bp / (B['resx'] * bd * cf)
            out.update({'b_throwdist': bd, 'b_ppi': ppi(bp), 'b_nits': nits(lx, B['gain'])})
    return out


def _len(v, unit):
    return ('%.2f ft' % (v * FT_PER_M)) if unit == 'ft' else ('%.2f m' % v)


def hud_text(p, r):
    """Multi-line HUD for the audience view (numbers from readouts())."""
    st = rig(p)
    A, B = st['A'], st['B']
    u = p.get('Unit', 'm')
    lines = ['Projector A  throw %.2f:1  %dx%d  %d lm  shift H %+.0f%% V %+.0f%%  F%.1f' % (
        A['T'], A['resx'], A['resy'], A['lumens'], A['sh'] * 100, A['sv'] * 100, _f(p, 'Fnum', 2.0))]
    if r.get('throwdist', 0) > 0:
        lines.append('throw %s   image %s x %s (diag %s)   hFOV %.1f  vFOV %.1f' % (
            _len(r['throwdist'], u), _len(r['imgw'], u), _len(r['imgh'], u), _len(r['imgdiag'], u),
            r['hfov'], r['vfov']))
        lines.append('image centre: %.1f ppi  %.2f mm/px   %.0f lux  %.0f nits  %.1f fL (gain %.2f)' % (
            r['ppi'], r['mmpx'], r['lux'], r['nits'], r['fl'], A['gain']))
    else:
        lines.append('image centre hits no surface   hFOV %.1f  vFOV %.1f' % (r.get('hfov', 0), r.get('vfov', 0)))
    lines.append('on surfaces %.0f%% of the image   ppi avg %.1f  min %.1f' % (
        100 * r.get('coverage', 0), r.get('avgppi', 0), r.get('minppi', 0)))
    if B['on']:
        lines.append('Projector B  throw %.2f:1   %s   %.1f ppi   %.0f nits' % (
            B['T'], _len(r.get('b_throwdist', 0), u), r.get('b_ppi', 0), r.get('b_nits', 0)))
    mode = p.get('Viewmode', 'lit')
    if mode == 'pixeldensity':
        lines.append('View: pixel density, legend 0 .. %.0f ppi (red = coarse)' % _f(p, 'Maxppi', 40))
    elif mode == 'brightness':
        lines.append('View: brightness, legend 0 .. %.0f nits' % _f(p, 'Maxnits', 500))
    elif mode == 'coverage':
        lines.append('View: coverage (A teal, B magenta, both white, grey = none)')
    elif mode == 'overlap':
        lines.append('View: overlap count (1 green, 2 amber, 3+ red)')
    return '\n'.join(lines)


# ---------------------------------------------------------------- dome (azimuthal equidistant domemaster)
# Domemaster: square, zenith at the centre, horizon (fov/2) at the circle edge; front of the dome (-Z) at the
# bottom of the image, +X (audience right) on the right. Dome frame Y up.
def dome_dir(u, v, fov=180.0):
    """Domemaster uv (0..1) -> unit direction in the dome frame, or None outside the circle."""
    x, y = 2.0 * u - 1.0, 2.0 * v - 1.0
    r = math.hypot(x, y)
    if r > 1.0:
        return None
    th = r * math.radians(fov) / 2.0
    ph = math.atan2(y, x)
    s = math.sin(th)
    return (s * math.cos(ph), math.cos(th), s * math.sin(ph))


def dome_uv(d, fov=180.0):
    """Unit direction in the dome frame -> domemaster uv, or None beyond fov/2 from the zenith."""
    x, y, z = d
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    x, y, z = x / n, y / n, z / n
    th = math.acos(max(-1.0, min(1.0, y)))
    half = math.radians(fov) / 2.0
    if th > half + 1e-9:
        return None
    r = th / half
    ph = math.atan2(z, x)
    return 0.5 + 0.5 * r * math.cos(ph), 0.5 + 0.5 * r * math.sin(ph)


def tilt_dir(d, tilt_deg):
    """Dome frame -> world: the dome tilted forward by tilt (rotation about X; + = zenith leans to the front)."""
    a = math.radians(tilt_deg)
    c, s = math.cos(a), math.sin(a)
    x, y, z = d
    return (x, c * y + s * z, -s * y + c * z)


def window_uv(d, az0, el0, hw, hh):
    """World direction -> uv of a flat image placed on the dome: centre (azimuth from the front, elevation),
    half-angles hw, hh (all degrees). None outside."""
    x, y, z = d
    az = math.degrees(math.atan2(x, -z)) - az0
    az = (az + 180.0) % 360.0 - 180.0
    el = math.degrees(math.asin(max(-1.0, min(1.0, y)))) - el0
    u = 0.5 + 0.5 * az / hw
    v = 0.5 + 0.5 * el / hh
    if 0 <= u <= 1 and 0 <= v <= 1:
        return u, v
    return None


def equirect_uv(d):
    """World direction -> equirect uv (front -Z at u 0.5, up at v 1)."""
    x, y, z = d
    lon = math.atan2(x, -z)
    lat = math.asin(max(-1.0, min(1.0, y)))
    return lon / (2.0 * math.pi) + 0.5, lat / math.pi + 0.5
