"""Offline tests for MX_prox_material (builders/prox_mat_logic.py, prox_mat.py, glsl/prox_mat_*.glsl). No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_prox_mat.py'
GLSL checks compile with glslc (OpenGL target) against stubs of the TD functions used: a syntax/type check, NOT a TD
compile (that is LIVE CHECK M1 in docs/builds/prox_mat.md)."""
import ast
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
import prox_mat_logic as L  # noqa: E402
import px_logic as PXL  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None


def rd(name):
    with open(os.path.join(GLSL, name)) as fh:
        return fh.read()


def D(**over):
    v = L.defaults()
    v.update(over)
    return lambda n: v[n]


def sphere_eff(c=(0.0, 0.0, 0.0), s=1.0):
    return {'kind': 'sphere', 'world': [[s, 0, 0, c[0]], [0, s, 0, c[1]], [0, 0, s, c[2]]]}


class Schema(unittest.TestCase):
    def test_rows_reference_real_pars(self):
        specs = L.par_specs()
        flat = set(L.defaults())
        for name, items in L.ROWS:
            self.assertEqual(len(items), 4, name)
            for it in items:
                if isinstance(it, str) and not it.startswith('@'):
                    self.assertIn(it, flat, (name, it))
        self.assertEqual(L.MX_ROWS, L.E_ROWS + len(L.ROWS))
        self.assertTrue(set(L.PANEL_PAGES) <= set(pg for pg, _ in L.PAGES))
        for n, (st, d, o) in specs.items():
            if st == 'Menu':
                self.assertIn(d, o['names'], n)
                self.assertEqual(len(o['names']), len(o['labels']), n)
            if st in ('Float', 'Int'):
                self.assertLessEqual(o['min'], d, n)
                self.assertGreaterEqual(o['max'], d, n)
            self.assertRegex(n, r'^[A-Z][a-z0-9]*$')

    def test_derived_items_are_produced(self):
        der = L.derived_values(D(), 3, 10, 10, 1)
        for _, items in L.ROWS:
            for it in items:
                if isinstance(it, str) and it.startswith('@'):
                    self.assertIn(it[1:], der, it)

    def test_header_defines_every_row_once(self):
        h = L.glsl_header()
        for k, (n, _) in enumerate(L.ROWS):
            self.assertIn('#define MX_%s uMX[%d]' % (n, k), h)
        self.assertIn('uniform vec4 uMX[%d];' % L.MAT_ROWS, h)
        self.assertIn('uniform vec4 uE[%d];' % L.E_ROWS, h)
        self.assertIn('#define PX_NO_TEX_INPUTS', h)
        self.assertIn('vec4 uG[%d];' % PXL.G_ROWS, h)

    def test_shaders_use_only_defined_rows(self):
        defined = set(n for n, _ in L.ROWS)
        for f in ('prox_mat_common.glsl', 'prox_mat_vert.glsl', 'prox_mat_pixel.glsl', 'prox_mat_pts.glsl',
                  'prox_mat_field.glsl'):
            for m in re.findall(r'\bMX_([A-Z0-9]+)\b', rd(f)):
                self.assertIn(m, defined, (f, m))

    def test_menu_orders_match_shader_constants(self):
        # menus the shaders switch on by index
        self.assertEqual(L.names(L.COLOURMODES), ['off', 'tint', 'replace', 'ramp', 'hue', 'add'])
        self.assertEqual(L.names(L.DISSOLVEMODES), ['off', 'near', 'far'])
        self.assertEqual(L.names(L.DISPMODES), ['off', 'push', 'attract', 'swell', 'ripple', 'noise', 'wake'])
        self.assertEqual(L.names(L.DISPDIRS), ['normal', 'outward', 'axis', 'worldy'])
        self.assertEqual(L.names(L.POINTMODE), ['nearest', 'density'])
        self.assertEqual(L.FALLOFFS, PXL.FALLOFFS)       # shared with PX: same indices as pxFall
        self.assertEqual(L.COMBINES, PXL.COMBINES)

    def test_ascii_files(self):
        for f in ('prox_mat_logic.py', 'prox_mat.py'):
            with open(os.path.join(BUILDERS, f), 'rb') as fh:
                fh.read().decode('ascii')
        for f in ('prox_mat_common.glsl', 'prox_mat_vert.glsl', 'prox_mat_pixel.glsl', 'prox_mat_pts.glsl',
                  'prox_mat_field.glsl', 'px_common.glsl'):
            rd(f).encode('ascii')


class Packing(unittest.TestCase):
    def test_pack_shape_and_values(self):
        rows = L.pack_rows(D(Radius=0.7, Shape='gaussian', Combine='sum', Flip=True), [sphere_eff()])
        self.assertEqual(len(rows), L.MX_ROWS)
        g0, prox = rows[L.row_index('G0')], rows[L.row_index('PROX')]
        self.assertEqual(g0[0], 1.0)
        self.assertEqual(g0[3], 1.0)
        self.assertEqual(prox, [0.7, 1.0, 2.0, 1.0])
        base = rows[L.row_index('BASE')]
        self.assertAlmostEqual(base[0], 0.55)
        ch = L.rows_to_chans(rows)
        self.assertEqual(len(ch), 4)
        self.assertEqual(len(ch[0]), L.MX_ROWS)
        self.assertEqual(rows[L.E_ROWS:], L.pack_mat(D(Radius=0.7, Shape='gaussian', Combine='sum', Flip=True), 1))
        self.assertEqual(L.mat_index('G0'), 0)
        self.assertEqual(L.row_index('G0'), L.E_ROWS)

    def test_effector_rows_are_px_rows(self):
        e = sphere_eff((1.0, 2.0, 3.0), 2.0)
        self.assertEqual(L.effector_rows([e]), PXL.effector_rows([dict(e, speed=0.0)]))

    def test_point_paths(self):
        self.assertEqual(L.pts_path('none', 'auto', 10, 64), 0)
        self.assertEqual(L.pts_path('chop', 'auto', 10, 64), 1)
        self.assertEqual(L.pts_path('chop', 'auto', 478, 64), 2)
        self.assertEqual(L.pts_path('top', 'direct', 5000, 64), 1)
        self.assertEqual(L.pts_path('top', 'field', 3, 64), 2)
        self.assertEqual(L.pts_path('chop', 'auto', 0, 64), 0)
        rows = L.pack_rows(D(Pointsource='chop', Pointmax=100), [], n_src=478)
        g0, pts = rows[L.row_index('G0')], rows[L.row_index('PTS')]
        self.assertEqual(g0[1], 2.0)
        self.assertEqual(pts[:3], [100.0, 100.0, 1.0])

    def test_pts_size(self):
        self.assertEqual(L.pts_size(0, 4096), (0, 1, 1))
        self.assertEqual(L.pts_size(478, 4096), (478, 478, 1))
        self.assertEqual(L.pts_size(50000, 4096), (4096, 1024, 4))
        self.assertEqual(L.pts_size(50000, 10000), (4096, 1024, 4))     # PTS_MAX cap = PX_PTS_MAX
        self.assertIn('const int PX_PTS_MAX = %d;' % L.PTS_MAX, rd('px_common.glsl'))

    def test_field_size(self):
        self.assertEqual(L.field_tiles(48), 7)
        self.assertEqual(L.field_size(48), (336, 672))
        self.assertEqual(L.field_size(16), (64, 128))

    def test_count_chop_points(self):
        self.assertEqual(L.count_chop_points(['tx', 'ty', 'tz'], 50), 50)
        names = ['f0_a_00x', 'f0_a_00y', 'f0_b_01x', 'f0_b_01y', 'conf']
        self.assertEqual(L.count_chop_points(names, 1), 2)
        self.assertEqual(len(L.points_from_chans([(n, [0.1]) for n in names])), 2)
        self.assertEqual(L.tex_dims(1500), (1024, 2))
        self.assertEqual(L.tex_dims(0), (1, 1))

    def test_count_points(self):
        self.assertEqual(L.count_points('top', top_w=10, top_h=10, stride=3, offset=1), 33)
        self.assertEqual(L.count_points('chop', 478), 478)
        self.assertEqual(L.count_points('none', 478), 0)

    def test_stride_only_for_top(self):
        der = L.derived_values(D(Pointsource='chop', Topstride=3, Topoffset=2), 0, 10, 10, 1)
        self.assertEqual((der['stride'], der['toff']), (1, 0))
        der = L.derived_values(D(Pointsource='top', Topstride=3, Topoffset=2), 0, 10, 30, 1)
        self.assertEqual((der['stride'], der['toff']), (3, 2))

    def test_point_affine_with_space(self):
        A = L.point_affine((2, 2, 2), (1, 0, 0), [[1, 0, 0, 5], [0, 1, 0, 0], [0, 0, 1, 0]])
        p = (1.0, 1.0, 1.0)
        q = [sum(A[r][c] * p[c] for c in range(3)) + A[r][3] for r in range(3)]
        self.assertEqual(q, [8.0, 2.0, 2.0])

    def test_presets_use_real_pars(self):
        flat = set(L.defaults())
        specs = L.par_specs()
        self.assertEqual(sorted(L.PRESETS), sorted(L.PRESET_NAMES))
        for name in L.PRESET_NAMES:
            for k, v in L.preset_values(name).items():
                self.assertIn(k, flat, (name, k))
                base = k if k in specs else k[:-1]
                st, d, o = specs[base]
                if st == 'Menu':
                    self.assertIn(v, o['names'], (name, k))


@unittest.skipIf(np is None, 'numpy missing')
class Points(unittest.TestCase):
    def test_samples_layout(self):
        pts = L.points_from_chans([('tx', [0, 1, 2]), ('ty', [3, 4, 5]), ('tz', [6, 7, 8]), ('r', [1, 1, 1])])
        self.assertEqual(pts.tolist(), [[0, 3, 6], [1, 4, 7], [2, 5, 8]])

    def test_samples_aliases_and_missing_z(self):
        pts = L.points_from_chans([('x', [0, 1]), ('y', [2, 3])], z=0.5)
        self.assertEqual(pts.tolist(), [[0, 2, 0.5], [1, 3, 0.5]])
        pts = L.points_from_chans([('P0', [1, 2]), ('P1', [3, 4]), ('P2', [5, 6])])
        self.assertEqual(pts.tolist(), [[1, 3, 5], [2, 4, 6]])

    def test_channels_layout_face_track_style(self):
        ch = [('f0_nose_00x', [0.5]), ('f0_nose_00y', [0.25]), ('f0_lips_01x', [0.4]), ('f0_lips_01y', [0.75])]
        pts = L.points_from_chans(ch)
        self.assertTrue(np.allclose(pts, [[0.5, 0.25, 0.0], [0.4, 0.75, 0.0]]))

    def test_points_image(self):
        img = L.points_image(np.arange(3 * 1500, dtype=np.float32).reshape(-1, 3))
        self.assertEqual(img.shape, (2, 1024, 4))
        flat = img.reshape(-1, 4)
        self.assertEqual(flat[1499, :3].tolist(), [4497.0, 4498.0, 4499.0])
        self.assertEqual(flat[1499, 3], 1.0)
        self.assertEqual(flat[1500, 3], 0.0)
        self.assertEqual(L.points_image(np.zeros((0, 3))).shape, (1, 1, 4))

    def test_density_and_eq_dist(self):
        P = [(0.0, 0.0, 0.0)]
        self.assertAlmostEqual(float(L.ref_pts_density(np.array([0.0, 0.0, 0.0]), P, 0.1)), 1.0)
        self.assertAlmostEqual(float(L.ref_pts_density(np.array([0.1, 0.0, 0.0]), P, 0.1)), math.exp(-4.0))
        self.assertAlmostEqual(float(L.ref_eq_dist(1, 0, 1.0, 0.0, 0.5, 2.0)), 0.25)
        self.assertAlmostEqual(float(L.ref_eq_dist(0, 1.0, 0, 0.1, 0.5, 2.0)), 0.9)

    def test_field_matches_brute_force(self):
        rng = np.random.default_rng(3)
        P = rng.uniform(-1, 1, (200, 3))
        lo, size, R = (-2.0, -2.0, -2.0), (4.0, 4.0, 4.0), 32
        F = L.ref_field(P, lo, size, R)
        q = rng.uniform(-1.8, 1.8, (500, 3))
        d_true, _ = L.ref_pts_nearest(q, P)
        d_f = L.ref_field_sample(F, q, lo, size)[..., 0]
        cell = 4.0 / R
        self.assertLess(np.max(np.abs(d_f - d_true)), 0.9 * cell)       # trilinear of a 1-Lipschitz field
        self.assertLess(np.mean(np.abs(d_f - d_true)), 0.1 * cell)
        out = np.array([[3.0, 0.0, 0.0]])                                # outside the box: + box distance
        self.assertGreater(float(L.ref_field_sample(F, out, lo, size)[0, 0]), 1.0)


@unittest.skipIf(np is None, 'numpy missing')
class Maths(unittest.TestCase):
    def test_drive(self):
        self.assertAlmostEqual(float(L.drive(1.0, 0.2, 0.8, 1.0)), 0.2)
        self.assertAlmostEqual(float(L.drive(0.0, 0.2, 0.8, 1.0)), 0.8)
        self.assertAlmostEqual(float(L.drive(0.5, 1.0, 0.0, 2.0)), 0.25)
        self.assertAlmostEqual(float(L.drive(3.0, 1.0, 0.0, 1.0)), 1.0)

    def test_weight_sphere_smooth(self):
        # unit-scale sphere effector (r 0.5) at origin, Radius 1, smooth, k 1
        rows = L.pack_rows(D(Radius=1.0, Falloffexp=1.0, Shape='smooth'), [sphere_eff()])
        p = np.array([[0.0, 0.0, 0.0], [0.5, 0, 0], [1.0, 0, 0], [1.5, 0, 0], [2.0, 0, 0]])
        w = L.ref_weight(p, rows)
        ss = lambda x: 1 - (3 * x * x - 2 * x ** 3)
        self.assertTrue(np.allclose(w, [1.0, 1.0, ss(0.5), 0.0, 0.0]))

    def test_push_displacement_at_known_distances(self):
        # the live check M4 numbers: plane points at distance x from the sphere centre
        rows = L.pack_rows(D(Radius=1.0, Shape='smooth', Dispmode='push', Dispnear=0.2, Dispfar=0.0, Dispcurve=1.0),
                           [sphere_eff()])
        p = np.array([[0.75, 0.0, 0.0], [1.0, 0.0, 0.0], [1.25, 0.0, 0.0]])
        q, a = L.ref_push(p, rows, np.tile([0.0, 1.0, 0.0], (3, 1)))
        self.assertTrue(np.allclose(a, [0.2 * 0.84375, 0.1, 0.2 * 0.15625]))
        self.assertTrue(np.allclose(q[:, 1], a))

    def test_combine_points_and_effectors(self):
        pts = [(3.0, 0.0, 0.0)]
        rows = L.pack_rows(D(Radius=1.0, Shape='linear', Pointsource='chop', Pointradius=0.0), [sphere_eff()],
                           n_src=1)
        w = L.ref_weight(np.array([[0.0, 0, 0], [3.0, 0, 0], [2.5, 0, 0], [1.5, 0, 0]]), rows, pts)
        self.assertTrue(np.allclose(w, [1.0, 1.0, 0.5, 0.0]))

    def test_flip_and_gain(self):
        rows = L.pack_rows(D(Radius=1.0, Shape='linear', Gain=0.5, Flip=True), [sphere_eff()])
        w = L.ref_weight(np.array([[0.0, 0, 0], [5.0, 0, 0]]), rows)
        self.assertTrue(np.allclose(w, [0.5, 1.0]))

    def test_no_sources_is_zero(self):
        rows = L.pack_rows(D(), [])
        self.assertTrue(np.allclose(L.ref_weight(np.zeros((2, 3)), rows), 0.0))

    def test_effector_world_shapes(self):
        I = [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0]]
        w, size = L.effector_world(I, 'box', (-1.0, 0.0, -0.5), (2.0, 1.0, 1.0))
        self.assertEqual(size, (1.0, 0.5, 0.5))
        self.assertEqual([r[3] for r in w], [0.0, 0.5, 0.0])
        w, size = L.effector_world(I, 'sphere', (-0.5, -0.5, -0.5), (1.0, 1.0, 1.0))
        self.assertEqual(size, (0.5, 0.0, 0.0))
        w, size = L.effector_world(I, 'plane', (-1.0, -1.0, 0.0), (2.0, 2.0, 0.0))   # XY grid: normal z -> local y
        self.assertEqual([w[r][1] for r in range(3)], [0.0, 0.0, 1.0])
        rows = L.effector_rows([{'kind': 'plane', 'world': w}])
        self.assertAlmostEqual(float(PXL.ref_effector_sd(rows, 0, np.array([0.3, 0.2, 0.7]))), 0.7)
        self.assertEqual(L.kind_of('boxSOP'), 'box')
        self.assertEqual(L.kind_of('spherePOP'), 'sphere')
        self.assertEqual(L.kind_of('gridSOP'), 'plane')
        self.assertEqual(L.kind_of('boxSOP', 'nullCOMP'), 'null')


class VertexCache(unittest.TestCase):
    """perf-b2-w4: vc_cache slot table + point image (prox_mat_logic.vc_*)."""
    def test_layout(self):
        self.assertEqual(L.vc_layout([40000, 7200, 6242]), ([0, 40000, 47200], 53442, (53442 + 255) // 256))
        self.assertEqual(L.vc_layout([]), ([], 0, 1))
        self.assertEqual(L.vc_layout([0, 5], w=4), ([0, 0], 5, 2))

    def test_rows(self):
        import math
        c, s = math.cos(math.radians(70)), math.sin(math.radians(70))
        rx = [[1, 0, 0, 0], [0, c, -s, 0.2], [0, s, c, 0], [0, 0, 0, 1]]
        sc = [[2, 0, 0, 1], [0, 1, 0, 0], [0, 0, 4, 0], [0, 0, 0, 1]]
        r = L.vc_rows([(rx, 7200), (sc, 10), (sc, 0)])
        self.assertEqual(len(r), 1 + 3 * L.VC_SLOT_ROWS)
        self.assertEqual(r[0], (1.0, 256.0, 29.0, 3.0))   # 7210 points / 256
        self.assertEqual(r[1:4], [tuple(float(x) for x in row) for row in rx[:3]])
        for a, b in zip(r[4:7], [(1, 0, 0, 0), (0, c, -s, 0), (0, s, c, 0)]):   # rotation: normal matrix = itself
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y, places=12)
        self.assertEqual(r[7], (0.0, 7200.0, 0.0, 0.0))
        self.assertEqual(r[8 + 3:8 + 6], [(0.5, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 0.25, 0.0)])
        self.assertEqual(r[14], (7200.0, 10.0, 0.0, 0.0))
        self.assertEqual(r[21], (7210.0, 0.0, 0.0, 0.0))
        self.assertEqual(L.vc_rows([(rx, 5)], on=False)[0][0], 0.0)
        self.assertEqual(L.vc_rows([(rx, 0)])[0][0], 0.0)              # nothing to cache: off

    def test_image(self):
        a = L.vc_image([([(1, 2, 3), (4, 5, 6)], [(0, 1, 0), (1, 0, 0)]), ([(7, 8, 9)], [(0, 0, 1)])], w=2)
        self.assertEqual(a.shape, (4, 2, 4))
        self.assertEqual(a[0, 0].tolist(), [1, 2, 3, 1])
        self.assertEqual(a[1, 0].tolist(), [7, 8, 9, 1])
        self.assertEqual(a[1, 1].tolist(), [0, 0, 0, 0])
        self.assertEqual(a[2, 1].tolist(), [1, 0, 0, 0])
        self.assertEqual(a[3, 0].tolist(), [0, 0, 1, 0])

    def test_dispcache_par_and_row(self):
        self.assertIn('Dispcache', L.par_specs())
        self.assertEqual(L.ROWS[L.mat_index('DSP3')][1][3], 'Dispcache')


TD_STUB_COMMON = """#version 460
#define TD_NUM_LIGHTS 2
#define TD_NUM_ENV_LIGHTS 1
#define TD_NUM_COLOR_BUFFERS 1
struct TDMatrix { mat4 world; mat4 worldCam; mat4 cam; mat4 camInverse; mat4 proj; };
uniform TDMatrix uTDMats[1];
int TDCameraIndex() { return 0; }
"""
TD_STUB_VERT = TD_STUB_COMMON + """#define gl_VertexIndex gl_VertexID
in vec3 P;
in vec3 N;
in vec4 Cd;
vec3 TDPos() { return P; }
vec3 TDNormal() { return N; }
vec4 TDColor() { return Cd; }
vec3 TDUVUnwrapCoord() { return vec3(0.0); }
vec3 TDInstanceTexCoord(vec3 t) { return t; }
vec4 TDDeform(vec3 p) { return vec4(p, 1.0); }
vec3 TDDeformNorm(vec3 n) { return n; }
vec4 TDWorldToProj(vec4 v, vec3 uv) { return uTDMats[0].proj * v; }
vec4 TDInstanceColor(vec4 c) { return c; }
void TDWritePickingValues() {}
"""
TD_STUB_PIXEL = TD_STUB_COMMON + """struct TDPBRResult { vec3 diffuse; vec3 specular; float shadowStrength; };
TDPBRResult TDLightingPBR(int i, vec3 dc, vec3 sc, vec3 p, vec3 n, float ss, vec3 shc, vec3 v, float r)
{ TDPBRResult o; o.diffuse = dc; o.specular = sc; o.shadowStrength = 0.0; return o; }
TDPBRResult TDEnvLightingPBR(int i, vec3 dc, vec3 sc, vec3 n, vec3 v, float r, float ao)
{ TDPBRResult o; o.diffuse = dc; o.specular = sc; o.shadowStrength = 0.0; return o; }
bool TDFrontFacing(vec3 p, vec3 n) { return gl_FrontFacing; }
void TDCheckDiscard() {}
void TDAlphaTest(float a) {}
vec4 TDFog(vec4 c, vec3 p, int i) { return c; }
vec4 TDDither(vec4 c) { return c; }
vec4 TDOutputSwizzle(vec4 c) { return c; }
vec4 TDPixelColor(vec4 c) { return c; }
vec4 TDConvertColorSpace(vec4 c) { return c; }
"""
TD_STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[2];
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
"""


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, ext, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.' + ext)
            with open(p, 'w') as fh:
                fh.write(text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def test_stages_via_builder_assembly(self):
        ns = {}
        with open(os.path.join(BUILDERS, 'prox_mat.py')) as fh:
            exec(compile(fh.read(), 'prox_mat.py', 'exec'), ns)
        texts = ns['shader_texts']()
        self._ok(TD_STUB_VERT + texts['vert'], 'vert', 'vertex')
        pix = texts['pixel'].replace('#include <TDColorSpace>', '')      # TD's own include (stubbed above)
        self.assertEqual(texts['pixel'].count('#include <TDColorSpace>'), 1)
        self._ok(TD_STUB_PIXEL + pix, 'frag', 'pixel')
        solid = texts['pixel_solid'].replace('#include <TDColorSpace>', '')
        self._ok(TD_STUB_PIXEL.replace('#version 460\n', '#version 460\n#define MX_NO_DISSOLVE\n')
                 + solid.replace('#define MX_NO_DISSOLVE\n', ''), 'frag', 'pixel_solid')
        self.assertTrue(texts['pixel_solid'].startswith('#define MX_NO_DISSOLVE\n'))
        body = pix.split('void main()')[1]
        self.assertEqual(body.count('discard;'), 1)                     # the dissolve one, inside #ifndef
        self.assertLess(body.index('#ifndef MX_NO_DISSOLVE'), body.index('discard;'))
        self.assertLess(body.index('discard;'), body.index('#endif'))
        self._ok(TD_STUB_COMPUTE + texts['pts'], 'comp', 'pts')
        self._ok(TD_STUB_COMPUTE + texts['field'], 'comp', 'field')
        self._ok(TD_STUB_COMPUTE.replace('sTD2DInputs[2]', 'sTD2DInputs[3]') + texts['vcache'], 'comp', 'vcache')
        self.assertIn('#define MX_VC_PASS', texts['vcache'])
        self.assertNotIn('uniform sampler2D sPts;', texts['vcache'].split('#define MX_VC_PASS')[1].split('#else')[0])


class Builder(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(BUILDERS, 'prox_mat.py')) as fh:
            self.src = fh.read()
        self.tree = ast.parse(self.src)

    def test_api(self):
        fns = set(n.name for n in self.tree.body if isinstance(n, ast.FunctionDef))
        for f in ('build', 'build_unit', 'apply_prox_material', 'revert_prox_material', 'shader_texts', 'park'):
            self.assertIn(f, fns)

    def test_default_torus_dropped_any_family(self):  # T-163: on 31550 the default torus1 is a torusPOP
        from types import SimpleNamespace as S
        ns = {}
        exec(compile(self.src, 'prox_mat.py', 'exec'), ns)
        gone = []
        ns['safe_destroy'] = lambda o: gone.append(o.name)
        kids = [S(name='torus1', OPType='torusPOP', valid=True), S(name='shape', OPType='sphereSOP', valid=True),
                S(name='normals', OPType='attributecreateSOP', valid=True)]
        ns['_drop_default'](S(children=kids), ('shape', 'normals'))
        self.assertEqual(gone, ['torus1'])
        del gone[:]
        ns['_drop_default'](S(children=[S(name='torus1', OPType='torusSOP', valid=True)]))
        self.assertEqual(gone, ['torus1'])
        self.assertNotIn("'torusSOP' and", self.src)
        self.assertNotIn('ch.render = ch.display = False', self.src)

    def test_callback_texts_parse(self):
        ns = {}
        exec(compile(self.src, 'prox_mat.py', 'exec'), ns)
        for k in ('ROWS_CB', 'EFF_CB', 'PTS_CB', 'PEXEC', 'VC_ROWS_CB', 'VC_SRC_CB'):
            ast.parse(ns[k])

    def test_row_exprs_guard_parked(self):
        """T-165: mx_rows expressions give defaults while mx_rows has not cooked (channel None), values after."""
        ns = {}
        exec(compile(self.src, 'prox_mat.py', 'exec'), ns)
        Lg = ns['_logic']()
        pi, g0 = Lg['mat_index']('PTS'), Lg['mat_index']('G0')
        exprs = ns['row_exprs'](Lg)

        class Chop:
            def __init__(self, chans):
                self.chans = chans

            def __getitem__(self, k):
                return self.chans.get(k)
        parked = {'op': lambda p: Chop({})}
        self.assertEqual([eval(e, parked) for e in exprs], [1, 2, 'blank4', 'blank4'])
        y, z = [0.0] * 64, [0.0] * 64
        y[pi], z[pi], y[g0] = 7, 3, 2
        live = {'op': lambda p: Chop({'y': y, 'z': z})}
        self.assertEqual([eval(e, live) for e in exprs], [7, 6, 'pts', 'field'])
        self.assertNotIn("op('mx_rows')['y'][", self.src)         # no unguarded reads left

    def test_t70_t74_rules(self):
        self.assertNotIn('.destroy()', self.src)            # only safe_destroy
        self.assertNotIn('numpyArray(delayed', self.src)    # no TOP readback (CHOP channel arrays are fine)
        self.assertNotIn('top.numpyArray', self.src.lower())
        self.assertNotIn('evalTextSize', self.src)
        self.assertNotIn('cookRate =', self.src)


if __name__ == '__main__':
    unittest.main()
