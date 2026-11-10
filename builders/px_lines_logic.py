# px_lines_logic.py - pure logic of the PX lines pass (lane W1-C, 27 Oct 2026; doc docs/builds/px_lines.md). No td.
# Thin bright neon lines over point / splat scenes (Ruben Fro's "green lines", RUBENFRO_COVERAGE G1-G7):
#   rings (G1) - contour / slices (G4) - trails / ribbons + line vortex (G3, G5) - connect / plexus / lightning (G5)
#   - polyline / logo / typography (G6) - edges / outlines (G2, screen-space post). G7 (sweep beam) stays PX's plane
#   effector Glow (reused, not duplicated).
# Contents: the par schema (PAGES), segment planning (plan), the uniform rows uL[] (rows) + the GLSL #define header,
# camera maths, the palette spec of the COMP (W1-B convention), and float64 numpy references of every shader
# (ref_segments = px_lines_seg.glsl, ref_hist_step = px_lines_hist.glsl, ref_quad / ref_coverage = the MAT,
# ref_edges, ref_comp) + a perf model. Pure ASCII (TD reads it into a Text DAT).
import math

NAME = 'PX_lines'
SEG_W = 256                       # segments per row of the segment texture (4 texels each)
SEG_TEX = 4
SOURCES = ['rings', 'contour', 'trails', 'connect', 'polyline']
SRC_TOGGLE = {'rings': 'Rings', 'contour': 'Contour', 'trails': 'Trails', 'connect': 'Connect', 'polyline': 'Polyline'}
MAX_CENTRES = 4

ROW_NAMES = (['G0', 'G1', 'G2', 'G3', 'IV0', 'IV1', 'IV2', 'IV3', 'RN0', 'RN1', 'RN2', 'MK0', 'MK1', 'MK2',
              'ST0', 'ST1', 'ST2', 'ST3', 'CL0', 'CL1', 'CL2', 'RG0', 'RG1', 'RG2']
             + ['RC%d' % i for i in range(2 * MAX_CENTRES)]
             + ['CT0', 'CT1', 'CT2', 'CT3', 'CT4', 'TR0', 'TR1', 'TR2', 'TR3', 'TR4', 'TR5', 'TR6', 'CN0', 'CN1',
                'CN2', 'PO0', 'PO1', 'PM0', 'PM1', 'PM2', 'ED0', 'ED1', 'ED2', 'OUT0']
             + ['CN3', 'CN4'])                    # wave 4 (PX owner): connect grid index (origin, cell), (N, TX)
R = dict((n, i) for i, n in enumerate(ROW_NAMES))
NROWS = len(ROW_NAMES)

ATTR = [('along', 'Along the line (0..1)'), ('index', 'Line index (ring k, band k, track k)'),
        ('depth', 'Distance to camera (Depthnear..far)'), ('random', 'Random per line')]
EDGE_ATTR = [('luma', 'Scene luma'), ('depth', 'Depth (Depthnear..far, needs Usedepth)'), ('wipe', 'Wipe position'),
             ('screeny', 'Screen height')]
# W1-B convention (builders/palette_map_logic.py PAL_SOURCES / PAL_MODES / PAL_INTERP / COLSRC_MODES); copied names so
# this file imports nothing in TD; test_px_lines checks they equal palette_map_logic's.
COLSRC = [('solid', 'Solid colour'), ('palette', 'Palette at position'), ('attr', 'Palette by attribute'),
          ('source', 'Keep source colour'), ('index', 'Palette stop by index')]
PAL_MODES = [('gradient', 'Gradient (positioned stops)'), ('steps', 'Steps (equal bands)'),
             ('cycle', 'Cycle (wraps, last -> first)')]
PAL_INTERP = [('rgb', 'RGB'), ('oklab', 'OKLab')]
PAL_SOURCE_KEYS = ['custom', 'file', 'neon_green', 'cyan_magenta', 'neon_trio', 'acid', 'magenta_inv', 'fire',
                   'px_ramp', 'rainbow']


def _m(items):
    return {'names': [a for a, _b in items], 'labels': [b for _a, b in items]}


def _colsrc(prefix, mode, rgb):
    p = prefix[:1].upper() + prefix[1:].lower()
    return [(p + 'col', 'RGB', tuple(rgb), {}),
            (p + 'colsrc', 'Menu', mode, _m(COLSRC)),
            (p + 'palpos', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Palette position'}),
            (p + 'palspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Palette spread (x attribute)'}),
            (p + 'keep', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Keep source colour'})]


F = lambda d, lo, hi, label: ('Float', d, {'min': lo, 'max': hi, 'label': label})
I = lambda d, lo, hi, label: ('Int', d, {'min': lo, 'max': hi, 'label': label})

PAGES = [
    ('Lines', [
        ('Amount',) + F(1.0, 0, 1, 'Amount'),
        ('Outmode', 'Menu', 'composite', _m([('composite', 'Composite over in1'), ('lines', 'Lines only (PX layer)')])),
        ('Maxseg',) + I(65536, 1024, 262144, 'Segment budget'),
        ('Width',) + F(2.0, 0.25, 16, 'Core width px'),
        ('Halo',) + F(6.0, 0, 64, 'Halo radius px'),
        ('Halogain',) + F(0.35, 0, 2, 'Halo gain'),
        ('Intensity',) + F(1.5, 0, 10, 'Intensity (HDR)'),
        ('Blend', 'Menu', 'max', _m([('add', 'Add (crossings brighten)'), ('max', 'Max (clean joints)')])),
        ('Bgdim',) + F(0.0, 0, 1, 'Dim the scene under the lines'),
        ('Resx',) + I(1080, 64, 8192, 'Output width'),
        ('Resy',) + I(1920, 64, 8192, 'Output height'),
        ('Camera', 'COMP', '', {'label': 'Camera (empty = own cam)'}),
        ('Speed',) + F(1.0, -4, 4, 'Time speed'),
        ('Seed',) + I(1, 0, 999, 'Seed'),
        ('Reset', 'Pulse', None, {'label': 'Reset trails'}),
        ('Resetn',) + I(0, 0, 1000000, 'Reset count (internal)'),
    ]),
    ('Reveal', [
        ('Reveal',) + F(1.0, 0, 1, 'Reveal (draw-on 0..1)'),
        ('Cut',) + F(0.0, 0, 1, 'Cut (erase from start)'),
        ('Revsoft',) + F(0.02, 0.0001, 0.5, 'Reveal softness'),
        ('Dash',) + F(0.0, 0, 200, 'Dashes per line (0 off)'),
        ('Dashduty',) + F(0.5, 0, 1, 'Dash duty'),
        ('Dashspeed',) + F(0.0, -10, 10, 'Dash speed (dashes/s)'),
        ('Flicker',) + F(0.0, 0, 1, 'Flicker per line'),
        ('Flickerhz',) + F(12.0, 0, 60, 'Flicker rate Hz'),
        ('Maskmode', 'Menu', 'off', _m([('off', 'Off'), ('sphere', 'Sphere (inside)'), ('front', 'Front (behind plane)')])),
        ('Maskop', 'COMP', '', {'label': 'Mask object (centre + y axis)'}),
        ('Maskcentre', 'XYZ', (0.0, 0.0, 0.0), {}),
        ('Maskaxis', 'XYZ', (1.0, 0.0, 0.0), {}),
        ('Maskradius',) + F(1.0, 0, 20, 'Mask radius'),
        ('Masksoft',) + F(0.2, 0.001, 10, 'Mask softness'),
        ('Maskinvert', 'Toggle', False, {'label': 'Invert mask'}),
        ('Occlusion', 'Menu', 'over', _m([('over', 'Over everything'), ('depth', 'Depth test (in_depth)'),
                                          ('alpha', 'Behind scene alpha')])),
        ('Usedepth', 'Toggle', False, {'label': 'in_depth wired (linear eye depth in R)'}),
        ('Occbias',) + F(0.02, 0, 2, 'Occlusion bias'),
        ('Occsoft',) + F(0.05, 0.001, 2, 'Occlusion softness'),
    ]),
    ('Colour', _colsrc('line', 'solid', (0.25, 1.0, 0.4)) + _colsrc('edge', 'solid', (0.25, 1.0, 0.4)) + [
        ('Palsource', 'Menu', 'neon_green', {'names': PAL_SOURCE_KEYS, 'labels': PAL_SOURCE_KEYS}),
        ('Palfile', 'File', '', {'label': 'Palette file (source file)'}),
        ('Palmode', 'Menu', 'cycle', _m(PAL_MODES)),
        ('Palinterp', 'Menu', 'oklab', _m(PAL_INTERP)),
        ('Palreverse', 'Toggle', False, {'label': 'Reverse palette'}),
        ('Palshift',) + F(0.0, 0, 1, 'Palette shift (drive me)'),
        ('Depthnear',) + F(1.0, 0, 100, 'Depth colour near'),
        ('Depthfar',) + F(10.0, 0, 1000, 'Depth colour far'),
    ]),
    ('Points', [
        ('Ptstride',) + I(1, 1, 16, 'Texels per point (PX state 5)'),
        ('Ptcount',) + I(0, 0, 4194304, 'Points used (0 = all texels)'),
    ]),
    ('Rings', [
        ('Rings', 'Toggle', True, {'label': 'Rings on'}),
        ('Ringcount',) + I(4, 1, 32, 'Rings per centre'),
        ('Ringsegs',) + I(128, 3, 1024, 'Segments per ring'),
        ('Ringradius',) + F(0.5, 0, 20, 'Inner radius'),
        ('Ringspacing',) + F(0.15, 0, 5, 'Spacing'),
        ('Ringexpand',) + F(0.0, -4, 4, 'Expand (cycles/s, 0 = still)'),
        ('Ringspin',) + F(0.0, -720, 720, 'Spin deg/s'),
        ('Ringtilt',) + F(0.0, -90, 90, 'Tilt deg (orbits)'),
        ('Ringorbit',) + F(0.0, -720, 720, 'Orbit deg/s'),
        ('Ringface', 'Menu', 'plane', _m([('plane', 'Object / Ringnormal plane'), ('camera', 'Face the camera')])),
        ('Ringops', 'Str', '', {'label': 'Centres: objects (space separated, <= 4)'}),
        ('Ringcentre', 'XYZ', (0.0, 0.0, 0.0), {}),
        ('Ringnormal', 'XYZ', (0.0, 0.0, 1.0), {}),
        ('Ringattr', 'Menu', 'along', _m(ATTR)),
        ('Ringgain',) + F(1.0, 0, 10, 'Rings gain'),
    ]),
    ('Contour', [
        ('Contour', 'Toggle', False, {'label': 'Contour lines on'}),
        ('Ctmax',) + I(32768, 256, 262144, 'Segments (points sampled)'),
        ('Ctaxis', 'Menu', 'y', _m([('x', 'X'), ('y', 'Y'), ('z', 'Z'), ('view', 'Camera forward'), ('custom', 'Custom')])),
        ('Ctaxisv', 'XYZ', (0.0, 1.0, 0.0), {}),
        ('Ctorigin', 'XYZ', (0.0, 0.0, 0.0), {}),
        ('Ctspacing',) + F(0.05, 0.001, 5, 'Band spacing'),
        ('Ctband',) + F(0.01, 0.0001, 1, 'Band thickness'),
        ('Ctlen',) + F(0.03, 0.0001, 1, 'Segment length'),
        ('Ctsnap',) + F(1.0, 0, 1, 'Snap to band plane'),
        ('Ctspeed',) + F(0.0, -20, 20, 'Band scroll (bands/s)'),
        ('Ctwave',) + F(0.0, 0, 1, 'Wave amplitude'),
        ('Ctwavefreq',) + F(2.0, 0, 50, 'Wave frequency'),
        ('Ctwavespeed',) + F(0.5, -10, 10, 'Wave speed'),
        ('Cttangent', 'Menu', 'around', _m([('around', 'Around the axis (rings)'), ('view', 'Across the view')])),
        ('Ctfirst',) + I(0, 0, 4194304, 'First point id'),
        ('Ctcount',) + I(0, 0, 4194304, 'Point ids (0 = rest)'),
        ('Ctattr', 'Menu', 'index', _m(ATTR)),
        ('Ctgain',) + F(1.0, 0, 10, 'Contour gain'),
    ]),
    ('Trails', [
        ('Trails', 'Toggle', False, {'label': 'Trails on'}),
        ('Trtracks',) + I(2048, 1, 4096, 'Tracks'),
        ('Trsamples',) + I(32, 2, 128, 'Samples per track'),
        ('Trevery',) + I(1, 1, 30, 'Frames per sample'),
        ('Trmotion', 'Menu', 'flow', _m([('points', 'Follow the points (PX motion)'), ('flow', 'Own flow particles')])),
        ('Trfirst',) + I(0, 0, 4194304, 'First point id'),
        ('Trcount',) + I(0, 0, 4194304, 'Point ids (0 = rest)'),
        ('Trlife',) + F(3.0, 0.05, 60, 'Life s (flow)'),
        ('Trspeed',) + F(1.0, -20, 20, 'Flow speed'),
        ('Trdir', 'XYZ', (0.0, 0.0, -1.0), {}),
        ('Trcurl',) + F(0.5, 0, 20, 'Curl'),
        ('Trcurlscale',) + F(1.5, 0.01, 50, 'Curl scale'),
        ('Trswirl',) + F(0.0, -20, 20, 'Vortex swirl'),
        ('Trpull',) + F(0.0, -20, 20, 'Vortex pull'),
        ('Trvcam', 'Toggle', False, {'label': 'Vortex on the camera'}),
        ('Trvcentre', 'XYZ', (0.0, 0.0, 0.0), {}),
        ('Trvaxis', 'XYZ', (0.0, 0.0, 1.0), {}),
        ('Trjitter',) + F(0.0, 0, 1, 'Jitter (lightning)'),
        ('Trjitterhz',) + F(12.0, 0, 60, 'Jitter rate Hz'),
        ('Trmaxjump',) + F(0.5, 0, 100, 'Max jump (points)'),
        ('Trtaper',) + F(1.0, 0, 4, 'Width taper'),
        ('Trfade',) + F(1.0, 0, 4, 'Fade along'),
        ('Trattr', 'Menu', 'index', _m(ATTR)),
        ('Trgain',) + F(1.0, 0, 10, 'Trails gain'),
    ]),
    ('Connect', [
        ('Connect', 'Toggle', False, {'label': 'Connect lines on'}),
        ('Cnpoints',) + I(1024, 2, 4096, 'Points (brute <= 4096; grid: samples)'),
        ('Cnk',) + I(3, 1, 4, 'Neighbours per point'),
        ('Cnradius',) + F(0.2, 0.0001, 20, 'Max distance'),
        ('Cnsub',) + I(1, 1, 8, 'Pieces per link (lightning)'),
        ('Cnjitter',) + F(0.0, 0, 2, 'Jitter (lightning)'),
        ('Cnjitterhz',) + F(12.0, 0, 60, 'Jitter rate Hz'),
        ('Cnfirst',) + I(0, 0, 4194304, 'First point id'),
        ('Cncount',) + I(0, 0, 4194304, 'Point ids (0 = rest)'),
        ('Cnattr', 'Menu', 'along', _m(ATTR)),
        ('Cngain',) + F(1.0, 0, 10, 'Connect gain'),
        # wave 4 (SA33 on the full cloud): a voxel index of the whole point set (one representative point per voxel,
        # built by cn_index: one workgroup per 8^3 brick, shared atomics) -> each sample links to its k nearest
        # representatives in the 27 voxels around it. Any point count; cost = samples x 27, + the index when it cooks.
        ('Cnindex', 'Menu', 'brute', _m([('brute', 'Brute force (<= 4096 points)'),
                                         ('grid', 'Voxel index (whole cloud)')])),
        ('Cngrid',) + I(32, 8, 128, 'Index voxels per edge (x8)'),
        ('Cngridcentre', 'XYZ', (0.0, 0.0, 0.0), {'label': 'Index box centre'}),
        ('Cngridsize',) + F(4.0, 0.01, 1000, 'Index box edge'),
        ('Cnpick', 'Menu', 'random', _m([('random', 'Random point per voxel'), ('centre', 'Point nearest the voxel centre')])),
        ('Cnindextop', 'TOP', '', {'label': 'Index points TOP (rest: static = indexed once; empty = in_points)'}),
        ('Cnistride',) + I(0, 0, 16, 'Index TOP texels per point (0 = Ptstride)'),
    ]),
    ('Polyline', [
        ('Polyline', 'Toggle', False, {'label': 'Polyline on'}),
        ('Polychop', 'CHOP', '', {'label': 'Path CHOP (tx ty tz [w])'}),
        ('Polyop', 'COMP', '', {'label': 'Place by object'}),
        ('Pomax',) + I(4096, 2, 16384, 'Max path points'),
        ('Poclose', 'Toggle', False, {'label': 'Closed'}),
        ('Pomaxgap',) + F(0.0, 0, 100, 'Pen up above gap (0 off)'),
        ('Poattr', 'Menu', 'along', _m(ATTR)),
        ('Pogain',) + F(1.0, 0, 10, 'Polyline gain'),
    ]),
    ('Edges', [
        ('Edges', 'Toggle', False, {'label': 'Edge lines on'}),
        ('Edres', 'Menu', 'half', _m([('full', 'Full'), ('half', 'Half'), ('quarter', 'Quarter')])),
        ('Edluma',) + F(1.0, 0, 20, 'Luma edges'),
        ('Edalpha',) + F(1.0, 0, 20, 'Alpha (silhouette) edges'),
        ('Eddepth',) + F(0.0, 0, 50, 'Depth edges (Usedepth)'),
        ('Edthr',) + F(0.15, 0, 4, 'Threshold'),
        ('Edsoft',) + F(0.1, 0.001, 4, 'Softness'),
        ('Edwidth',) + F(1.5, 0.25, 16, 'Width px'),
        ('Edwipe',) + F(0.0, -180, 180, 'Wipe direction deg (reveal)'),
        ('Edattr', 'Menu', 'luma', _m(EDGE_ATTR)),
        ('Edgain',) + F(1.0, 0, 10, 'Edges gain'),
    ]),
]
PANEL_PAGES = ['Lines', 'Reveal', 'Colour', 'Rings', 'Contour', 'Trails', 'Connect', 'Polyline', 'Edges']


def par_specs():
    return dict((n, (st, d, o)) for _pg, ps in PAGES for n, st, d, o in ps)


def defaults():
    """par name -> default value (Menu = name, XYZ / RGB = tuple, OP pars = '')."""
    return dict((n, d) for n, (st, d, o) in par_specs().items() if st not in ('Pulse',))


def menu_index(name, val):
    names = par_specs()[name][2]['names']
    return names.index(val) if val in names else 0


# ------------------------------------------------------------------------------------------------------ GLSL header
def glsl_header():
    """#defines prepended to every stage (row indices, sizes)."""
    out = ['#define PL_NROWS %d' % NROWS, '#define SEG_W %d' % SEG_W]
    out += ['#define R_%s %d' % (n, i) for n, i in sorted(R.items(), key=lambda kv: kv[1])]
    return '\n'.join(out) + '\n'


def stage_text(stage, common, palette, body):
    """Full shader text of a stage: header + (palette when the stage colours) + common + body."""
    pal = palette if stage in ('seg', 'edges') else ''
    return glsl_header() + pal + '\n' + common + '\n' + body


# ------------------------------------------------------------------------------------------------------ camera maths
def mat_mul(a, b):
    return [[sum(a[r][k] * b[k][c] for k in range(4)) for c in range(4)] for r in range(4)]


def mat_inv(m):
    """4x4 inverse (Gauss-Jordan, partial pivot)."""
    n = 4
    a = [list(map(float, m[r])) + [1.0 if r == c else 0.0 for c in range(n)] for r in range(n)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(a[r][c]))
        if abs(a[p][c]) < 1e-15:
            raise ValueError('singular matrix')
        a[c], a[p] = a[p], a[c]
        d = a[c][c]
        a[c] = [v / d for v in a[c]]
        for r in range(n):
            if r != c and a[r][c] != 0.0:
                f = a[r][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return [row[n:] for row in a]


def perspective(fov_deg, resx, resy, near=0.01, far=1000.0, horizontal=True):
    """GL projection (TD Camera COMP, fov horizontal by default)."""
    t = math.tan(math.radians(max(float(fov_deg), 1e-3)) * 0.5)
    asp = float(resx) / max(float(resy), 1.0)
    fx, fy = (1.0 / t, asp / t) if horizontal else (1.0 / (t * asp), 1.0 / t)
    n, f = float(near), float(far)
    return [[fx, 0.0, 0.0, 0.0], [0.0, fy, 0.0, 0.0], [0.0, 0.0, -(f + n) / (f - n), -2.0 * f * n / (f - n)],
            [0.0, 0.0, -1.0, 0.0]]


def camera(world, proj):
    """world = camera's 4x4 world transform (rows), proj = 4x4 -> dict pos, fwd, vp, ivp."""
    w = [list(map(float, r)) for r in world]
    if len(w) == 3:
        w = w + [[0.0, 0.0, 0.0, 1.0]]
    view = mat_inv(w)
    vp = mat_mul(proj, view)
    fwd = [-w[0][2], -w[1][2], -w[2][2]]
    fl = math.sqrt(sum(v * v for v in fwd)) or 1.0
    return {'pos': [w[0][3], w[1][3], w[2][3]], 'fwd': [v / fl for v in fwd], 'vp': vp, 'ivp': mat_inv(vp)}


def default_camera(resx=1080, resy=1920):
    """The builder's own cam: at (0, 0, 5) looking down -z, fov 45 horizontal."""
    return camera([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 5], [0, 0, 0, 1]], perspective(45.0, resx, resy))


def _norm(v, fb=(0.0, 1.0, 0.0)):
    l = math.sqrt(sum(float(x) * float(x) for x in v))
    return [float(x) / l for x in v] if l > 1e-12 else list(fb)


def frame_from_world(world):
    """3x4 / 4x4 world rows -> (centre, y axis unit, mean axis scale)."""
    c = [float(world[r][3]) for r in range(3)]
    cols = [[float(world[r][k]) for r in range(3)] for k in range(3)]
    sc = sum(math.sqrt(sum(x * x for x in col)) for col in cols) / 3.0
    return c, _norm(cols[1]), sc


# ------------------------------------------------------------------------------------------------------ planning
def ring_centres(p, ctx):
    """[(centre, normal, scale)] (1..4): ctx['centres'] (objects from Ringops, as frame_from_world) else the pars;
    Ringface camera turns every normal toward the camera."""
    cs = list(ctx.get('centres') or [])[:MAX_CENTRES]
    if not cs:
        cs = [(list(p['Ringcentre']), _norm(p['Ringnormal']), 1.0)]
    cam = ctx.get('cam') or default_camera(p['Resx'], p['Resy'])
    out = []
    for c, n, s in cs:
        if p['Ringface'] == 'camera':
            n = _norm([cam['pos'][k] - c[k] for k in range(3)], n)
        out.append((list(c), list(n), float(s)))
    return out


BRUTE_MAX = 4096
IDX_ID_BITS = 22                                 # index key = priority (10 bits) << 22 | point id (< 4 194 304)


def index_layout(p):
    """Connect grid index: N^3 voxels over the cube Cngridcentre +- Cngridsize / 2 (N = Cngrid up to a multiple of 8,
    8..128), atlas = voxel (x, y, z) -> texel (x + (z % TX) N, y + (z // TX) N), TX = ceil(sqrt(N)); dispatch N / 8
    per axis (one workgroup per 8^3 brick)."""
    N = min(max((int(p.get('Cngrid', 32)) + 7) // 8 * 8, 8), 128)
    tx = int(math.ceil(math.sqrt(N)))
    size = max(float(p.get('Cngridsize', 4.0)), 1e-6)
    c = list(p.get('Cngridcentre', (0.0, 0.0, 0.0)))
    return {'N': N, 'TX': tx, 'cell': size / N, 'origin': [float(c[k]) - 0.5 * size for k in range(3)],
            'atlas': (N * tx, N * ((N + tx - 1) // tx)), 'dispatch': N // 8}


def plan(p, ctx=None):
    """Segment ranges per source -> {'ranges': {src: (start, count)}, 'total', 'maxseg', 'rows_tex', 'hist': (w, h),
    'clamped': [src...]}. Sources are packed in SOURCES order; each is clamped to what is left of Maxseg."""
    ctx = ctx or {}
    maxseg = max(int(p['Maxseg']), 1)
    want = {}
    if p['Rings']:
        want['rings'] = int(p['Ringcount']) * max(int(p['Ringsegs']), 3) * len(ring_centres(p, ctx))
    if p['Contour']:
        want['contour'] = int(p['Ctmax'])
    if p['Trails']:
        want['trails'] = int(p['Trtracks']) * max(int(p['Trsamples']), 2)
    if p['Connect']:
        npc = int(p['Cnpoints']) if p.get('Cnindex', 'brute') == 'grid' else min(int(p['Cnpoints']), BRUTE_MAX)
        want['connect'] = npc * min(max(int(p['Cnk']), 1), 4) * min(max(int(p['Cnsub']), 1), 8)
    if p['Polyline']:
        n = min(int(ctx.get('poly_n', 0)), int(p['Pomax']))
        want['polyline'] = max(n - 1 + (1 if (p['Poclose'] and n > 2) else 0), 0)
    ranges, at, clamped = {}, 0, []
    for s in SOURCES:
        if s not in want:
            continue
        c = want[s]
        if s == 'connect':                 # whole points only (one thread writes a point's k * sub segments)
            per = min(max(int(p['Cnk']), 1), 4) * min(max(int(p['Cnsub']), 1), 8)
            c = min(c, (maxseg - at) // per * per)
        else:
            c = min(c, maxseg - at)
        if c < want[s]:
            clamped.append(s)
        ranges[s] = (at, max(c, 0))
        at += max(c, 0)
    return {'ranges': ranges, 'total': at, 'maxseg': maxseg, 'rows_tex': (maxseg + SEG_W - 1) // SEG_W,
            'hist': (max(int(p['Trsamples']), 2) + 2, max(int(p['Trtracks']), 1)), 'clamped': clamped,
            'connect_points': (ranges.get('connect', (0, 0))[1] //
                               (min(max(int(p['Cnk']), 1), 4) * min(max(int(p['Cnsub']), 1), 8)))}


def _axis(p):
    a = p['Ctaxis']
    if a in ('x', 'y', 'z'):
        return [1.0 if a == k else 0.0 for k in 'xyz']
    return None


FOLLOW_ROWS = ['G2', 'G3', 'IV0', 'IV1', 'IV2', 'IV3', 'MK1', 'MK2', 'CT0', 'TR4', 'TR5', 'PM0', 'PM1', 'PM2'] + \
    ['RC%d' % i for i in range(2 * MAX_CENTRES)]


def follows(p):
    """Python twin of px_lines.FOLLOW: the rows move with objects / an outside camera (the `rows` CHOP cooks per
    frame). rows_static then reads no world transform (it would cook per frame too); rows_follow patches them."""
    cam_users = (p.get('Ringface') == 'camera' or p.get('Ctaxis') == 'view' or p.get('Cttangent') == 'view'
                 or bool(p.get('Trvcam')) or 'depth' in (p.get('Ringattr'), p.get('Ctattr'), p.get('Trattr'),
                                                        p.get('Cnattr'), p.get('Poattr'))
                 or (bool(p.get('Edges')) and bool(p.get('Usedepth')) and p.get('Maskmode') != 'off'))
    return bool(p.get('Ringops') or p.get('Polyop') or p.get('Maskop') or (p.get('Camera') and cam_users))


def rows_follow(p, ctx=None):
    """Wave 4 (PX owner): ONLY the rows that follow objects / the camera ({name: [4 floats]}), the same values as
    rows(p, ctx) gives for them. The `rows` CHOP runs this per frame over the par-driven `rows_static` (event cooks),
    instead of the whole rows() + every par read per frame (~2.3 ms CPU live)."""
    ctx = ctx or {}
    resx, resy = float(p['Resx']), float(p['Resy'])
    cam = ctx.get('cam') or default_camera(resx, resy)
    out = {}

    def put(name, v):
        v = [float(x) for x in v]
        out[name] = v + [0.0] * (4 - len(v))
    put('G2', cam['pos'] + [0.0])
    put('G3', cam['fwd'] + [0.0])
    for k in range(4):
        put('IV%d' % k, cam['ivp'][k])
    mc, ma = list(p['Maskcentre']), _norm(p['Maskaxis'], (1.0, 0.0, 0.0))
    if ctx.get('mask_world'):
        mc, ma, _s = frame_from_world(ctx['mask_world'])
    put('MK1', mc + [0.0])
    put('MK2', ma + [0.0])
    cents = ring_centres(p, ctx)
    for i in range(MAX_CENTRES):
        c, n, s = cents[i] if i < len(cents) else cents[-1]
        put('RC%d' % (2 * i), list(c) + [s])
        put('RC%d' % (2 * i + 1), list(n) + [0.0])
    ax = _axis(p)
    if ax is None:
        ax = list(cam['fwd']) if p['Ctaxis'] == 'view' else _norm(p['Ctaxisv'])
    put('CT0', ax + [p['Ctspacing']])
    vc, va = (list(cam['pos']), list(cam['fwd'])) if p['Trvcam'] else (list(p['Trvcentre']), _norm(p['Trvaxis']))
    put('TR4', vc + [p['Trjitterhz']])
    put('TR5', va + [p['Trmaxjump']])
    pw = ctx.get('poly_world') or [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]
    for k in range(3):
        put('PM%d' % k, pw[k][:4])
    return out


def rows(p, ctx=None):
    """Uniform rows uL[NROWS] (lists of 4 floats). ctx: cam (camera()), centres [(c, n, s)], poly_n, poly_world (3x4),
    mask_world (3x4 of Maskop)."""
    ctx = ctx or {}
    resx, resy = float(p['Resx']), float(p['Resy'])
    cam = ctx.get('cam') or default_camera(resx, resy)
    pl = plan(p, ctx)
    z = [[0.0] * 4 for _ in range(NROWS)]

    def put(name, v):
        v = [float(x) for x in v]
        z[R[name]] = v + [0.0] * (4 - len(v))
    put('G0', [resx, resy, pl['total'], pl['maxseg']])
    put('G1', [p['Ptcount'], p['Ptstride'], p['Seed'], p['Intensity']])
    put('G2', cam['pos'] + [0.0])
    put('G3', cam['fwd'] + [0.0])
    for k in range(4):
        put('IV%d' % k, cam['ivp'][k])
    rg = pl['ranges']
    g = lambda s: rg.get(s, (0, 0))
    put('RN0', list(g('rings')) + list(g('contour')))
    put('RN1', list(g('trails')) + list(g('connect')))
    put('RN2', list(g('polyline')) + [0, 0])
    mc, ma = list(p['Maskcentre']), _norm(p['Maskaxis'], (1.0, 0.0, 0.0))
    if ctx.get('mask_world'):
        mc, ma, _s = frame_from_world(ctx['mask_world'])
    put('MK0', [menu_index('Maskmode', p['Maskmode']), p['Maskradius'], p['Masksoft'], 1.0 if p['Maskinvert'] else 0.0])
    put('MK1', mc + [0.0])
    put('MK2', ma + [0.0])
    put('ST0', [p['Width'], p['Halo'], p['Halogain'], menu_index('Blend', p['Blend'])])
    put('ST1', [p['Dash'], p['Dashduty'], p['Dashspeed'], p['Flicker']])
    put('ST2', [p['Reveal'], p['Cut'], p['Revsoft'], p['Flickerhz']])
    put('ST3', [menu_index('Occlusion', p['Occlusion']), p['Occbias'], p['Occsoft'], 1.0 if p['Usedepth'] else 0.0])
    put('CL0', list(p['Linecol']) + [0.0])
    put('CL1', list(p['Edgecol']) + [0.0])
    put('CL2', [p['Depthnear'], p['Depthfar'], 0.0, 0.0])
    cents = ring_centres(p, ctx)
    put('RG0', [p['Ringcount'], p['Ringsegs'], p['Ringradius'], p['Ringspacing']])
    put('RG1', [p['Ringexpand'], math.radians(p['Ringspin']), math.radians(p['Ringtilt']), math.radians(p['Ringorbit'])])
    put('RG2', [menu_index('Ringattr', p['Ringattr']), p['Ringgain'], len(cents), 0.0])
    for i in range(MAX_CENTRES):
        c, n, s = cents[i] if i < len(cents) else cents[-1]
        put('RC%d' % (2 * i), list(c) + [s])
        put('RC%d' % (2 * i + 1), list(n) + [0.0])
    ax = _axis(p)
    if ax is None:
        ax = list(cam['fwd']) if p['Ctaxis'] == 'view' else _norm(p['Ctaxisv'])
    put('CT0', ax + [p['Ctspacing']])
    put('CT1', list(p['Ctorigin']) + [p['Ctband']])
    put('CT2', [p['Ctlen'], p['Ctsnap'], p['Ctspeed'], p['Ctwave']])
    put('CT3', [p['Ctwavefreq'], p['Ctwavespeed'], menu_index('Cttangent', p['Cttangent']),
                menu_index('Ctattr', p['Ctattr'])])
    put('CT4', [p['Ctgain'], p['Ctfirst'], p['Ctcount'], 0.0])
    put('TR0', [p['Trtracks'], p['Trsamples'], p['Trevery'], menu_index('Trmotion', p['Trmotion'])])
    put('TR1', [p['Trfirst'], p['Trcount'], p['Trlife'], p['Trspeed']])
    put('TR2', _norm(p['Trdir'], (0.0, 0.0, 0.0)) + [p['Trcurl']])
    put('TR3', [p['Trcurlscale'], p['Trswirl'], p['Trpull'], p['Trjitter']])
    vc, va = (list(cam['pos']), list(cam['fwd'])) if p['Trvcam'] else (list(p['Trvcentre']), _norm(p['Trvaxis']))
    put('TR4', vc + [p['Trjitterhz']])
    put('TR5', va + [p['Trmaxjump']])
    put('TR6', [menu_index('Trattr', p['Trattr']), p['Trgain'], p['Trtaper'], p['Trfade']])
    grid = p.get('Cnindex', 'brute') == 'grid'
    npts = pl['connect_points'] or p['Cnpoints']
    if not grid:
        npts = min(npts, BRUTE_MAX)                # the brute pass is n^2 per frame: never past 4096 (GPU hang)
    put('CN0', [npts, p['Cnk'], p['Cnradius'], p['Cnsub']])
    put('CN1', [p['Cnjitter'], p['Cnjitterhz'], p['Cnfirst'], p['Cncount']])
    put('CN2', [menu_index('Cnattr', p['Cnattr']), p['Cngain'], 1.0 if grid else 0.0, 0.0])
    gl = index_layout(p)
    put('CN3', list(gl['origin']) + [gl['cell']])
    put('CN4', [gl['N'], gl['TX'], int(p.get('Cnistride', 0) or 0) or p['Ptstride'], 0.0])
    n = min(int(ctx.get('poly_n', 0)), int(p['Pomax']))
    put('PO0', [n, 1.0 if p['Poclose'] else 0.0, p['Pomaxgap'], menu_index('Poattr', p['Poattr'])])
    put('PO1', [p['Pogain'], 0.0, 0.0, 0.0])
    pw = ctx.get('poly_world') or [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]
    for k in range(3):
        put('PM%d' % k, pw[k][:4])
    put('ED0', [p['Edluma'], p['Edalpha'], p['Eddepth'], p['Edthr']])
    put('ED1', [p['Edsoft'], p['Edwidth'], menu_index('Edattr', p['Edattr']), p['Edgain']])
    put('ED2', [0.0, math.radians(p['Edwipe']), 0.0, 0.0])
    put('OUT0', [p['Amount'], menu_index('Outmode', p['Outmode']), p['Bgdim'], 0.0])
    return z


def cs_vec(p, prefix):
    """W1-B colour source vec4 (mode index, pos, spread, keep) of 'Line' / 'Edge'."""
    names = [a for a, _b in COLSRC]
    m = p[prefix + 'colsrc']
    return [float(names.index(m) if m in names else 0), float(p[prefix + 'palpos']), float(p[prefix + 'palspread']),
            float(p[prefix + 'keep'])]


def pal_spec(p):
    """The COMP's palette spec for palette_map_logic.palette_stops (source / mode / reverse)."""
    return {'source': p['Palsource'], 'mode': p['Palmode'], 'reverse': bool(p['Palreverse'])}


def edges_res(p):
    k = {'full': 1, 'half': 2, 'quarter': 4}.get(p['Edres'], 2)
    return max(int(p['Resx']) // k, 1), max(int(p['Resy']) // k, 1)


def time_vec(seconds, frame, step, speed, resetn):
    """uT = (time s x speed, frame, dt x speed, reset count)."""
    return [float(seconds) * float(speed), float(frame), float(step) * float(speed), float(resetn)]


# ------------------------------------------------------------------------------------------------------ perf model
# GPU estimates for 1080x1920 on the M1 Max under Rosetta (T-84 262k instanced quads 3.0 ms GPU incl. fill; Render
# TOP CPU floor 0.7-1.9 ms, T-143); fill calibrated on the W1-C live run (docs/builds/px_lines.md "Verified live").
def perf_model(p, ctx=None, avg_len_px=12.0):
    pl = plan(p, ctx)
    segs = pl['total']
    ext = 2.0 * (0.5 * p['Width'] + 2.0 * p['Halo'] + 1.0)
    frags = segs * ext * (avg_len_px + ext)
    vert = 0.0035 * segs / 1000.0 * 4.0 / 4.0          # 4 texel fetches + 2 projections per vertex, 4 vertices
    fill = frags / 1e6 * 0.065                           # live 31550 (scratch, loaded GPU): 64k, Halo 4 = +2.6 ms
    seg = 0.02 + segs / 65536.0 * 0.03
    npts = pl['connect_points']
    conn = npts * npts / 1e6 * 0.03 if p['Connect'] else 0.0
    hist = (pl['hist'][0] * pl['hist'][1] / 1e5 * 0.02) if p['Trails'] else 0.0
    ew, eh = edges_res(p)
    edges = ew * eh / 518400.0 * 0.15 if p['Edges'] else 0.0
    comp = p['Resx'] * p['Resy'] / 2073600.0 * 0.08
    gpu = vert + fill + seg + conn + hist + edges + comp
    return {'segments': segs, 'vertex': round(vert, 3), 'fill': round(fill, 3), 'seg': round(seg, 3),
            'connect': round(conn, 3), 'hist': round(hist, 3), 'edges': round(edges, 3), 'comp': round(comp, 3),
            'gpu_ms': round(gpu, 3), 'render_cpu_ms': (0.7, 1.9)}


# ======================================================================================== numpy references (float64)
def _np():
    import numpy as np
    return np


def pcg(v):
    np = _np()
    v = np.asarray(v, dtype=np.uint64) & 0xFFFFFFFF
    s = (v * 747796405 + 2891336453) & 0xFFFFFFFF
    w = (((s >> ((s >> 28) + 4)) ^ s) * 277803737) & 0xFFFFFFFF
    return ((w >> 22) ^ w) & 0xFFFFFFFF


def h3(a, b, c):
    np = _np()
    a, b, c = [np.asarray(x, dtype=np.uint64) & 0xFFFFFFFF for x in (a, b, c)]
    return (pcg(a ^ pcg(b ^ pcg(c))) >> 8).astype(np.float64) / 16777215.0


def u_of(x):
    np = _np()
    return (np.floor(np.asarray(x, dtype=np.float64) + 0.5).astype(np.int64) + 65536) & 0xFFFFFFFF


def smoothstep(e0, e1, x):
    np = _np()
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def ref_mask(rows_, p3):
    np = _np()
    L = np.asarray(rows_, dtype=np.float64)
    p3 = np.asarray(p3, dtype=np.float64)
    m = int(L[R['MK0'], 0] + 0.5)
    if m == 0:
        return np.ones(p3.shape[:-1])
    soft = max(L[R['MK0'], 2], 1e-5)
    if m == 1:
        w = 1.0 - smoothstep(L[R['MK0'], 1], L[R['MK0'], 1] + soft, np.linalg.norm(p3 - L[R['MK1'], :3], axis=-1))
    else:
        w = 1.0 - smoothstep(0.0, soft, (p3 - L[R['MK1'], :3]) @ L[R['MK2'], :3])
    return 1.0 - w if L[R['MK0'], 3] > 0.5 else w


def ref_reveal(rows_, u):
    L = rows_
    rs = max(L[R['ST2']][2], 1e-4)
    Rv = L[R['ST2']][0] * (1.0 + rs)
    C = L[R['ST2']][1] * (1.0 + rs) - rs
    return (1.0 - smoothstep(Rv - rs, Rv, u)) * smoothstep(C, C + rs, u)


def _points_view(points, stride, ptcount):
    """points texture (H, W, 4) -> (N, 3) in id order (id -> ((id % side) * stride, id / side))."""
    np = _np()
    pts = np.asarray(points, dtype=np.float64)
    h, w = pts.shape[:2]
    stride = max(int(stride + 0.5), 1)
    side = max(w // stride, 1)
    sel = pts[:, : side * stride: stride, :3].reshape(-1, 3)
    n = side * h
    c = int(ptcount + 0.5)
    return sel[: (min(c, n) if c > 0 else n)]


def _range(n_av, first, count):
    f = min(max(int(first + 0.5), 0), n_av)
    c = int(count + 0.5)
    c = min(c, n_av - f) if c > 0 else n_av - f
    return f, max(c, 0)


def _basis(n):
    np = _np()
    n = np.asarray(n, dtype=np.float64)
    up = np.array([0.0, 1.0, 0.0]) if abs(n[1]) < 0.99 else np.array([1.0, 0.0, 0.0])
    e1 = np.cross(n, up)
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(n, e1)


def _rot(v, k, a):
    np = _np()
    return v * math.cos(a) + np.cross(k, v) * math.sin(a) + np.outer(v @ k, k) * (1.0 - math.cos(a)) \
        if v.ndim == 2 else v * math.cos(a) + np.cross(k, v) * math.sin(a) + k * (k @ v) * (1.0 - math.cos(a))


def ref_ring_segments(rows_, uT):
    """-> dict A, B (n, 3), ua, ub, lid, gain (before mask / flicker) for every ring segment, in segment order."""
    np = _np()
    L = np.asarray(rows_, dtype=np.float64)
    nr, ns = max(int(L[R['RG0'], 0] + 0.5), 1), max(int(L[R['RG0'], 1] + 0.5), 3)
    cnt = int(L[R['RN0'], 1] + 0.5)
    t = float(uT[0])
    out = {k: [] for k in ('A', 'B', 'ua', 'ub', 'lid', 'gain')}
    for l in range(cnt):
        ci, k, j = min(l // (nr * ns), 3), (l // ns) % nr, l % ns
        C, N = L[R['RC0'] + 2 * ci], L[R['RC0'] + 2 * ci + 1]
        n = N[:3] / np.linalg.norm(N[:3]) if np.linalg.norm(N[:3]) > 1e-6 else np.array([0.0, 1.0, 0.0])
        e1, e2 = _basis(n)
        if L[R['RG1'], 2] != 0.0:
            phi = L[R['RG1'], 3] * t + k * math.pi / nr
            q = math.cos(phi) * e1 + math.sin(phi) * e2
            e1, e2 = _rot(e1, q, L[R['RG1'], 2]), _rot(e2, q, L[R['RG1'], 2])
        al = 1.0
        if L[R['RG1'], 0] != 0.0:
            e = (k / nr + L[R['RG1'], 0] * t) % 1.0
            r = L[R['RG0'], 2] + e * nr * L[R['RG0'], 3]
            al = math.sin(math.pi * e)
        else:
            r = L[R['RG0'], 2] + k * L[R['RG0'], 3]
        r *= C[3]
        sp = L[R['RG1'], 1] * t
        a0, a1 = 2 * math.pi * j / ns + sp, 2 * math.pi * (j + 1) / ns + sp
        out['A'].append(C[:3] + r * (math.cos(a0) * e1 + math.sin(a0) * e2))
        out['B'].append(C[:3] + r * (math.cos(a1) * e1 + math.sin(a1) * e2))
        out['ua'].append(j / ns)
        out['ub'].append((j + 1) / ns)
        out['lid'].append(k + ci * nr)
        out['gain'].append(L[R['RG2'], 1] * al)
    return dict((k, np.asarray(v, dtype=np.float64)) for k, v in out.items())


def _ref_connect_grid(L, pts, index, index_points, s0, c, np_, K, sub, per, f, n, t, emit):
    np = _np()
    Rr = max(L[R['CN0'], 2], 1e-6)
    ist = max(int(L[R['CN4'], 2] + 0.5), 1)
    ip = np.asarray(index_points, dtype=np.float64)
    iside = max(ip.shape[1] // ist, 1)
    rest = lambda i: ip[i // iside, (i % iside) * ist, :3]
    N, tx = int(L[R['CN4'], 0] + 0.5), max(int(L[R['CN4'], 1] + 0.5), 1)
    org, cell = L[R['CN3'], :3], max(L[R['CN3'], 3], 1e-9)
    tick = int(max(math.floor(t * L[R['CN1'], 1]), 0.0))
    for pi in range(c // per):
        i = f + int(math.floor(pi * n / np_))
        Ri = rest(i)
        v0 = np.floor((Ri - org) / cell).astype(np.int64)
        cand = []
        for cc in range(27):
            v = v0 + np.array([cc % 3 - 1, (cc // 3) % 3 - 1, cc // 9 - 1])
            if np.any(v < 0) or np.any(v >= N):
                continue
            e = index[v[1] + (v[2] // tx) * N, v[0] + (v[2] % tx) * N]
            if e[3] < 0.5:
                continue
            q = int(e[3] + 0.5) - 1
            if q == i:
                continue
            d = float(np.linalg.norm(e[:3] - Ri))
            if d < Rr:
                cand.append((d, len(cand), q))
        cand.sort()
        for m, (dd, _o, q) in enumerate(cand[:K]):
            lo, hi = min(i, q), max(i, q)
            P0, P1 = pts[lo], pts[hi]
            key = int(pcg(lo)) ^ hi
            fall = (1.0 - dd / Rr) ** 2
            X0 = P0
            for k in range(sub):
                f1 = (k + 1) / sub
                X1 = P0 + (P1 - P0) * f1
                if k + 1 < sub:
                    X1 = X1 + L[R['CN1'], 0] * math.sin(math.pi * f1) * (np.array(
                        [h3(key, k + 1, tick), h3(key, k + 1, tick + 7919),
                         h3(key, k + 1, tick + 15838)]).ravel() * 2.0 - 1.0)
                emit([s0 + pi * per + m * sub + k], X0, k / sub, X1, f1, float(lo), L[R['CN2'], 0],
                     L[R['CN2'], 1] * fall, 1.0, 1, 3)
                X0 = X1


def ref_index(points, stride, count, lay, pick='random'):
    """Mirror of px_lines_index.glsl -> atlas (H, W, 4): per voxel the representative's xyz + id + 1 (0 = empty).
    points = the index TOP (H, W, 4); lay = index_layout(p)."""
    np = _np()
    pts = np.asarray(points, dtype=np.float32)
    h, w = pts.shape[:2]
    stride = max(int(stride), 1)
    side = max(w // stride, 1)
    P = min(side * h, 4194304)
    if int(count) > 0:
        P = min(P, int(count))
    ids = np.arange(P, dtype=np.int64)
    q = pts[ids // side, (ids % side) * stride, :3]
    N, tx = lay['N'], lay['TX']
    g = (q - np.asarray(lay['origin'], dtype=np.float32)) / np.float32(max(lay['cell'], 1e-9))
    v = np.floor(g).astype(np.int64)
    ok = np.all((v >= 0) & (v < N), axis=1)
    if pick == 'centre':
        d = np.linalg.norm(g - (v + 0.5), axis=1) * (1023.0 / 0.8660254) + 0.5
        pr = np.minimum(d, 1023.0).astype(np.uint64)
    else:
        pr = pcg(ids) >> 22
    key = (pr.astype(np.uint64) << np.uint64(IDX_ID_BITS)) | ids.astype(np.uint64)
    out = np.zeros((lay['atlas'][1], lay['atlas'][0], 4), dtype=np.float64)
    vi = v[ok]
    flat = vi[:, 0] + N * (vi[:, 1] + N * vi[:, 2])
    kk = key[ok]
    order = np.lexsort((kk, flat))
    flat_s, kk_s = flat[order], kk[order]
    first = np.ones(len(flat_s), dtype=bool)
    first[1:] = flat_s[1:] != flat_s[:-1]
    for f, k in zip(flat_s[first], kk_s[first]):
        x, y, z = int(f % N), int((f // N) % N), int(f // (N * N))
        i = int(k & ((1 << IDX_ID_BITS) - 1))
        out[y + (z // tx) * N, x + (z % tx) * N] = list(pts[i // side, (i % side) * stride, :3]) + [i + 1.0]
    return out


def ref_segments(rows_, uT, points=None, hist=None, path=None, colfn=None, index=None, index_points=None):
    """Mirror of px_lines_seg.glsl -> array (maxseg, 4, 4): per segment T0..T3. points (H, W, 4) texture, hist = the
    history texture after this frame's ref_hist_step (H = tracks, W = samples + 2, 4), path (1, N, 4).
    colfn(attr_t (n,), mid (n, 3)) -> rgb (n, 3) = pxColSrc(uLineCs, Linecol, Linecol, attrT) (palette_map_logic
    colsrc_eval); None = solid Linecol."""
    np = _np()
    L = np.asarray(rows_, dtype=np.float64)
    maxseg = int(L[R['G0'], 3] + 0.5)
    out = np.zeros((maxseg, 4, 4))
    seed = int(L[R['G1'], 2])
    pts = _points_view(points, L[R['G1'], 1], L[R['G1'], 0]) if points is not None else np.zeros((0, 3))
    t = float(uT[0])

    def attr_t(mode, u, lid, m):
        if mode == 1:
            return np.asarray(lid, dtype=np.float64)
        if mode == 2:
            d = np.linalg.norm(m - L[R['G2'], :3], axis=-1)
            return np.clip((d - L[R['CL2'], 0]) / max(L[R['CL2'], 1] - L[R['CL2'], 0], 1e-6), 0.0, 1.0)
        if mode == 3:
            return h3(u_of(lid), 7, seed)
        return np.asarray(u, dtype=np.float64)

    def emit(idx, A, ua, B, ub, lid, attr, gain, wm, caps, src):
        idx = np.asarray(idx, dtype=np.int64)
        if idx.size == 0:
            return
        A, B = np.atleast_2d(A), np.atleast_2d(B)
        lid = np.broadcast_to(np.asarray(lid, dtype=np.float64), idx.shape)
        m = 0.5 * (A + B)
        a = np.broadcast_to(np.asarray(gain, dtype=np.float64), idx.shape) * ref_mask(L, m)
        fl = L[R['ST1'], 3]
        if fl > 0.0:
            tick = max(math.floor(t * L[R['ST2'], 3]), 0.0)
            a = a * (1.0 - fl * h3(u_of(lid), int(tick), seed + 11))
        um = 0.5 * (np.asarray(ua, dtype=np.float64) + np.asarray(ub, dtype=np.float64))
        at = np.broadcast_to(attr_t(int(attr + 0.5), um, lid, m), idx.shape)
        col = colfn(at, m) if colfn is not None else np.broadcast_to(L[R['CL0'], :3], (idx.size, 3))
        out[idx, 0, :3], out[idx, 0, 3] = A, ua
        out[idx, 1, :3], out[idx, 1, 3] = B, ub
        out[idx, 2, :3], out[idx, 2, 3] = np.asarray(col) * L[R['G1'], 3], a
        out[idx, 3] = np.stack([np.broadcast_to(np.asarray(wm, dtype=np.float64), idx.shape),
                                np.full(idx.shape, float(caps)), lid, np.full(idx.shape, src + 1.0)], -1)

    st = lambda r, k: int(L[R[r], k] + 0.5)
    # rings
    s0, c = st('RN0', 0), st('RN0', 1)
    if c:
        rg = ref_ring_segments(L, uT)
        emit(np.arange(s0, s0 + c), rg['A'], rg['ua'], rg['B'], rg['ub'], rg['lid'], L[R['RG2'], 0], rg['gain'],
             1.0, 1, 0)
    # contour
    s0, c = st('RN0', 2), st('RN0', 3)
    if c:
        f, n = _range(len(pts), L[R['CT4'], 1], L[R['CT4'], 2])
        if n > 0:
            l = np.arange(c)
            P = pts[f + np.floor(l * n / c).astype(np.int64)]
            a, o = L[R['CT0'], :3], L[R['CT1'], :3]
            sp = max(L[R['CT0'], 3], 1e-6)
            e1, e2 = _basis(a)
            r = P - o
            T = np.cross(a, (P - L[R['G2'], :3]) if L[R['CT3'], 2] > 0.5 else r)
            tl = np.linalg.norm(T, axis=-1, keepdims=True)
            T = np.where(tl > 1e-9, T / np.maximum(tl, 1e-30), e1)
            q = (r @ e1) if L[R['CT3'], 2] > 0.5 else np.arctan2(r @ e2, r @ e1) / (2 * math.pi) + 0.5
            h = r @ a - L[R['CT2'], 3] * np.sin(2 * math.pi * (L[R['CT3'], 0] * q + L[R['CT3'], 1] * t))
            ph = h / sp - L[R['CT2'], 2] * t
            bi = np.floor(ph + 0.5)
            d = (ph - bi) * sp
            ok = np.abs(d) <= 0.5 * L[R['CT1'], 3]
            Cc = P - a[None, :] * (d * L[R['CT2'], 1])[:, None]
            hl = 0.5 * L[R['CT2'], 0]
            emit(s0 + l[ok], (Cc - T * hl)[ok], q[ok], (Cc + T * hl)[ok], q[ok], bi[ok], L[R['CT3'], 3],
                 L[R['CT4'], 0], 1.0, 3, 1)
    # trails
    s0, c = st('RN1', 0), st('RN1', 1)
    if c and hist is not None:
        H = np.asarray(hist, dtype=np.float64)
        ns = max(st('TR0', 1), 2)
        ev = max(st('TR0', 2), 1)
        hh = (int(uT[1] + 0.5) // ev) % ns
        J = L[R['TR3'], 3]
        tick = int(max(math.floor(t * L[R['TR4'], 3]), 0.0))

        def jit(tr, slot):
            if J == 0.0:
                return np.zeros(3)
            a_ = int(tr) * 977 + int(slot)
            return J * (np.array([h3(a_, tick, 1), h3(a_, tick, 2), h3(a_, tick, 3)]) * 2.0 - 1.0)
        for l in range(c):
            tr, j = l // ns, l % ns
            sa, sb = (hh - j + 1) % ns, (hh - j) % ns
            if j == 0:
                A = H[tr, 0].copy()
                A[3] = H[tr, 1, 0] + 1.0
            else:
                A = H[tr, 2 + sa].copy()
                A[:3] += jit(tr, sa)
            B = H[tr, 2 + sb].copy()
            B[:3] += jit(tr, sb)
            if A[3] < 0.5 or B[3] < 0.5 or abs(A[3] - B[3]) > 0.25:
                continue
            ua, ub = j / ns, (j + 1) / ns
            um = 0.5 * (ua + ub)
            wm = max(1.0 - um, 0.0) ** L[R['TR6'], 2]
            fd = max(1.0 - um, 0.0) ** L[R['TR6'], 3]
            emit([s0 + l], A[:3], ua, B[:3], ub, float(tr), L[R['TR6'], 0], L[R['TR6'], 1] * fd, wm, 1, 2)
    # connect
    s0, c = st('RN1', 2), st('RN1', 3)
    if c:
        np_ = max(st('CN0', 0), 1)
        K, sub = min(max(st('CN0', 1), 1), 4), min(max(st('CN0', 3), 1), 8)
        per = K * sub
        f, n = _range(len(pts), L[R['CN1'], 2], L[R['CN1'], 3])
        if n > 0 and L[R['CN2'], 2] > 0.5:
            if index is not None and index_points is not None:
                _ref_connect_grid(L, pts, index, index_points, s0, c, np_, K, sub, per, f, n, t, emit)
        elif n > 0:
            Rr = max(L[R['CN0'], 2], 1e-6)
            sel = pts[f + np.floor(np.arange(np_) * n / np_).astype(np.int64)]
            tick = int(max(math.floor(t * L[R['CN1'], 1]), 0.0))
            D = np.linalg.norm(sel[:, None, :] - sel[None, :, :], axis=-1)
            np.fill_diagonal(D, np.inf)
            for pi in range(c // per):
                cand = [(D[pi, q], q) for q in range(np_) if D[pi, q] < Rr]
                cand.sort(key=lambda dq: (dq[0], dq[1]))
                for m, (dd, q) in enumerate(cand[:K]):
                    lo, hi = min(pi, q), max(pi, q)
                    P0, P1 = sel[lo], sel[hi]
                    key = int(pcg(lo)) ^ hi
                    fall = (1.0 - dd / Rr) ** 2
                    X0 = P0
                    for k in range(sub):
                        f1 = (k + 1) / sub
                        X1 = P0 + (P1 - P0) * f1
                        if k + 1 < sub:
                            X1 = X1 + L[R['CN1'], 0] * math.sin(math.pi * f1) * (np.array(
                                [h3(key, k + 1, tick), h3(key, k + 1, tick + 7919),
                                 h3(key, k + 1, tick + 15838)]).ravel() * 2.0 - 1.0)
                        emit([s0 + pi * per + m * sub + k], X0, k / sub, X1, f1, float(lo), L[R['CN2'], 0],
                             L[R['CN2'], 1] * fall, 1.0, 1, 3)
                        X0 = X1
    # polyline
    s0, c = st('RN2', 0), st('RN2', 1)
    if c and path is not None:
        Pth = np.asarray(path, dtype=np.float64)[0]
        N = st('PO0', 0)
        cl = L[R['PO0'], 1] > 0.5 and N > 2
        M = L[[R['PM0'], R['PM1'], R['PM2']]]
        den = max(N if cl else N - 1, 1)
        for l in range(c):
            i0, i1 = l, l + 1
            if i1 >= N:
                if cl and i0 == N - 1:
                    i1 = 0
                else:
                    continue
            a, b = Pth[i0], Pth[i1]
            if a[3] < 0.0 or b[3] < 0.0:
                continue
            A, B = M @ np.append(a[:3], 1.0), M @ np.append(b[:3], 1.0)
            if L[R['PO0'], 2] > 0.0 and np.linalg.norm(B - A) > L[R['PO0'], 2]:
                continue
            emit([s0 + l], A, i0 / den, B, (i0 + 1) / den, 0.0, L[R['PO0'], 3], L[R['PO1'], 0], 1.0, 1, 4)
    return out


def ref_curl(rows_, p, t):
    np = _np()
    L = rows_
    a, b = L[R['TR3']][0], 1.31 * L[R['TR3']][0]
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    t1, t2, t3, t4, t5, t6 = 0.11 * t, 1.7 + 0.13 * t, 2.9 + 0.07 * t, 4.1 + 0.17 * t, 5.3 + 0.05 * t, 0.6 + 0.19 * t
    dAzdy = -b * np.sin(a * x + t5) * np.sin(b * y + t6)
    dAydz = a * np.cos(a * z + t3) * np.cos(b * x + t4)
    dAxdz = -b * np.sin(a * y + t1) * np.sin(b * z + t2)
    dAzdx = a * np.cos(a * x + t5) * np.cos(b * y + t6)
    dAydx = -b * np.sin(a * z + t3) * np.sin(b * x + t4)
    dAxdy = a * np.cos(a * y + t1) * np.cos(b * z + t2)
    return np.stack([dAzdy - dAydz, dAxdz - dAzdx, dAydx - dAxdy], -1) * (2.0 * L[R['TR2']][3] / max(a + b, 1e-6))


def ref_flow(rows_, p, t):
    np = _np()
    L = rows_
    v = np.asarray(L[R['TR2']][:3]) * L[R['TR1']][3] + ref_curl(L, p, t)
    r = p - np.asarray(L[R['TR4']][:3])
    sw = np.cross(np.asarray(L[R['TR5']][:3]), r)
    sl = np.linalg.norm(sw, axis=-1, keepdims=True)
    rl = np.linalg.norm(r, axis=-1, keepdims=True)
    v = v + np.where(sl > 1e-6, L[R['TR3']][1] * sw / np.maximum(sl, 1e-30), 0.0)
    v = v - np.where(rl > 1e-6, L[R['TR3']][2] * r / np.maximum(rl, 1e-30), 0.0)
    return v


def ref_hist_step(rows_, uT, prev, points):
    """Mirror of px_lines_hist.glsl: prev (tracks, samples + 2, 4) or None (size mismatch) -> next."""
    np = _np()
    L = [list(map(float, r)) for r in rows_]
    ns = max(int(L[R['TR0']][1] + 0.5), 2)
    tracks = max(int(L[R['TR0']][0] + 0.5), 1)
    W = ns + 2
    pts = _points_view(points, L[R['G1']][1], L[R['G1']][0]) if points is not None else np.zeros((0, 3))
    sizeok = prev is not None and np.asarray(prev).shape == (tracks, W, 4)
    prv = np.asarray(prev, dtype=np.float64) if sizeok else np.zeros((tracks, W, 4))
    out = np.zeros((tracks, W, 4))
    seed = int(L[R['G1']][2])
    f, cnt = _range(len(pts), L[R['TR1']][0], L[R['TR1']][1])
    dt, t = float(uT[2]), float(uT[0])
    fr = int(uT[1] + 0.5)
    ev = max(int(L[R['TR0']][2] + 0.5), 1)
    h = (fr // ev) % ns
    for tr in range(tracks):
        H0, H1 = prv[tr, 0], prv[tr, 1]
        init = (not sizeok) or abs(H1[2] - uT[3]) > 0.5
        lid = 0.0 if init else H1[0]
        life = 0.0 if init else H1[1]
        age = 0.0 if init else H0[3]
        P = H0[:3].copy()
        if L[R['TR0']][3] < 0.5:
            Pn = pts[f + int(math.floor(tr * cnt / tracks))] if cnt > 0 else np.zeros(3)
            if (not init) and L[R['TR5']][3] > 0.0 and np.linalg.norm(Pn - P) > L[R['TR5']][3]:
                lid += 1.0
            P = Pn.copy()
            age = 0.0 if init else age + dt
        elif init or age >= life:
            lid += 1.0
            Li = int(lid)
            if cnt > 0:
                P = pts[f + min(int(h3(tr, Li, seed) * cnt), cnt - 1)].copy()
            else:
                rnd = np.array([h3(tr, Li, seed + 3), h3(tr, Li, seed + 4), h3(tr, Li, seed + 5)]).ravel()
                P = np.asarray(L[R['TR4']][:3]) + (rnd * 2.0 - 1.0)
            age = 0.0
            life = L[R['TR1']][2] * (0.5 + float(h3(tr, Li, seed + 1)))
        else:
            P = P + ref_flow(L, P[None, :], t)[0] * dt
            age += dt
        out[tr, 0] = [P[0], P[1], P[2], age]
        out[tr, 1] = [lid, life, uT[3], 0.0]
        out[tr, 2:] = 0.0 if init else prv[tr, 2:]
        if fr % ev == 0:
            out[tr, 2 + h] = [P[0], P[1], P[2], lid + 1.0]
    return out


def ref_quad(A, B, vp, res, width, wm, halo):
    """Mirror of px_lines_vert.glsl (no near clip): -> (sa, sb, corners 4 x 2 px in P order (-x-y, +x-y, -x+y, +x+y),
    core half width px)."""
    np = _np()
    vp = np.asarray(vp, dtype=np.float64)
    res = np.asarray(res, dtype=np.float64)
    ca, cb = vp @ np.append(A, 1.0), vp @ np.append(B, 1.0)
    sa, sb = (ca[:2] / ca[3] * 0.5 + 0.5) * res, (cb[:2] / cb[3] * 0.5 + 0.5) * res
    d = sb - sa
    ln = np.linalg.norm(d)
    dr = d / ln if ln > 1e-4 else np.array([1.0, 0.0])
    nr = np.array([-dr[1], dr[0]])
    hw = 0.5 * width * wm
    ext = hw + 2.0 * halo + 1.0
    cs = []
    for py in (-0.5, 0.5):
        for px in (-0.5, 0.5):
            al = px + 0.5
            cs.append(sa + (sb - sa) * al + dr * ext * (-1.0 if al < 0.5 else 1.0) + nr * ext * (1.0 if py > 0 else -1.0))
    return sa, sb, np.asarray(cs), hw


def ref_coverage(dist, hw, halo, halogain):
    """Mirror of the pixel shader's intensity at distance dist px from the segment."""
    np = _np()
    dist = np.asarray(dist, dtype=np.float64)
    core = np.clip(hw + 0.5 - dist, 0.0, 1.0) * min(2.0 * hw, 1.0)
    ha = halogain * np.exp(-2.0 * (np.maximum(dist - hw, 0.0) / halo) ** 2) if halo > 0 else 0.0 * dist
    return core + (1.0 - core) * ha


def _bilinear(img, uv):
    """GL-style linear sampling with clamp-to-edge; img (H, W, C) row 0 = bottom (TD texture order), uv (..., 2)."""
    np = _np()
    img = np.asarray(img, dtype=np.float64)
    h, w = img.shape[:2]
    x = uv[..., 0] * w - 0.5
    y = uv[..., 1] * h - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    cx = lambda v: np.clip(v, 0, w - 1)
    cy = lambda v: np.clip(v, 0, h - 1)
    a = img[cy(y0), cx(x0)]
    b = img[cy(y0), cx(x0 + 1)]
    c = img[cy(y0 + 1), cx(x0)]
    d = img[cy(y0 + 1), cx(x0 + 1)]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def ref_edges(rows_, scene, out_wh, depth=None, colfn=None):
    """Mirror of px_lines_edges.glsl -> (H, W, 4). colfn(t (H, W), src (H, W, 3)) -> rgb (H, W, 3) =
    pxColSrc(uEdgeCs, Edgecol, src, t); None = solid Edgecol."""
    np = _np()
    L = np.asarray(rows_, dtype=np.float64)
    W, H = out_wh
    gx, gy = np.meshgrid(np.arange(W), np.arange(H))
    uv = np.stack([(gx + 0.5) / W, (gy + 0.5) / H], -1)
    o = 0.5 * L[R['ED1'], 1] / L[R['G0'], :2]
    dep = L[R['ST3'], 3] > 0.5 and depth is not None
    lum = np.array([0.2126, 0.7152, 0.0722])
    Ls, As, Zs, c0 = [], [], [], None
    for j in range(3):
        for i in range(3):
            q = uv + np.array([i - 1.0, j - 1.0]) * o
            c = _bilinear(scene, q)
            Ls.append(c[..., :3] @ lum)
            As.append(c[..., 3])
            Zs.append(_bilinear(np.asarray(depth)[..., :1], q)[..., 0] if dep else np.zeros(c.shape[:2]))
            if i == 1 and j == 1:
                c0 = c

    def sob(V):
        return np.hypot(V[2] + 2 * V[5] + V[8] - V[0] - 2 * V[3] - V[6], V[6] + 2 * V[7] + V[8] - V[0] - 2 * V[1] - V[2]) * 0.25
    gl, ga = sob(Ls), sob(As)
    gz = sob(Zs) / np.maximum(Zs[4], 1e-3)
    gm = np.maximum(L[R['ED0'], 0] * gl, np.maximum(L[R['ED0'], 1] * ga, L[R['ED0'], 2] * gz if dep else 0.0))
    e = smoothstep(L[R['ED0'], 3], L[R['ED0'], 3] + max(L[R['ED1'], 0], 1e-5), gm)
    wd = np.array([math.cos(L[R['ED2'], 1]), math.sin(L[R['ED2'], 1])])
    wu = ((uv - 0.5) @ wd) / (abs(wd[0]) * 0.5 + abs(wd[1]) * 0.5) * 0.5 + 0.5
    e = e * ref_reveal(L, wu)
    zt = np.zeros_like(e)
    if dep:
        ndc = np.concatenate([uv * 2.0 - 1.0, np.ones(uv.shape[:2] + (2,))], -1)
        wv = ndc @ L[[R['IV0'], R['IV1'], R['IV2'], R['IV3']]].T
        dr = wv[..., :3] / wv[..., 3:4] - L[R['G2'], :3]
        dr /= np.linalg.norm(dr, axis=-1, keepdims=True)
        Pw = L[R['G2'], :3] + dr * (Zs[4] / np.maximum(dr @ L[R['G3'], :3], 1e-4))[..., None]
        has = Zs[4] > 0.0
        e = np.where(has, e * ref_mask(L, Pw), (0.0 if int(L[R['MK0'], 0] + 0.5) != 0 else 1.0) * e)
        zt = np.where(has, np.clip((Zs[4] - L[R['CL2'], 0]) / max(L[R['CL2'], 1] - L[R['CL2'], 0], 1e-6), 0, 1), 0.0)
    at = int(L[R['ED1'], 2] + 0.5)
    t = [Ls[4], zt, wu, uv[..., 1]][min(at, 3)]
    src = c0[..., :3] / np.maximum(c0[..., :3].max(-1, keepdims=True), 1e-3)
    col = colfn(t, src) if colfn is not None else np.broadcast_to(L[R['CL1'], :3], src.shape)
    return np.concatenate([col * (L[R['ED1'], 3] * L[R['G1'], 3] * e)[..., None], e[..., None]], -1)


def ref_comp(rows_, scene, lines, edges):
    """Mirror of px_lines_comp.glsl for same-size inputs (H, W, 4)."""
    np = _np()
    L = np.asarray(rows_, dtype=np.float64)
    sc, ln, ed = [np.asarray(x, dtype=np.float64) for x in (scene, lines, edges)]
    am = L[R['OUT0'], 0]
    layer = (ln[..., :3] + ed[..., :3]) * am
    la = np.clip(np.maximum(ln[..., 3], ed[..., 3]) * am, 0.0, 1.0)
    if L[R['OUT0'], 1] > 0.5:
        return np.concatenate([layer, la[..., None]], -1)
    return np.concatenate([sc[..., :3] * (1.0 - L[R['OUT0'], 2]) + layer, np.maximum(sc[..., 3], la)[..., None]], -1)


def projected_px(vp, res, p):
    """World point -> pixel coords (same maths as the vertex shader)."""
    np = _np()
    c = np.asarray(vp, dtype=np.float64) @ np.append(np.asarray(p, dtype=np.float64), 1.0)
    return (c[:2] / c[3] * 0.5 + 0.5) * np.asarray(res, dtype=np.float64)
