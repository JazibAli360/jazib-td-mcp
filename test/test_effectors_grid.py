"""Offline tests of the shared voxel grid (lane E): atlas layout, packed grid region (v3, v2 readers unchanged), the
numpy twins of the compute passes (scatter -> seed -> JFA -> query) against brute force (K36 distance field: max error
< 1 cell), cloud rows in the CPU weight reference, the SA23 paint step, trilinear sampling, the TD runtime text and
glslc compiles of eff_grid_*.glsl + the px_common grid accessors. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_effectors_grid.py'
glslc = a syntax / type check against TD stubs, NOT a TD compile (LIVE CHECKS VG1-VG8 in docs/builds/effectors.md)."""
import ast
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
import numpy as np  # noqa: E402
import effectors_logic as L  # noqa: E402
import effectors_grid_logic as GL  # noqa: E402


def rd(path):
    with open(path) as fh:
        return fh.read()


def rows_of(*specs):
    rs = []
    for kind, name, kw in specs:
        rs, _ = L.add_row(rs, kind, name, **kw)
    return rs


def sphere_surface(n, r=1.0, c=(0.0, 1.0, 0.0), seed=1):
    rng = np.random.default_rng(seed)
    v = rng.normal(size=(n, 3))
    return np.asarray(c) + r * v / np.linalg.norm(v, axis=1)[:, None]


class Layout(unittest.TestCase):
    def test_tiles_and_atlas(self):
        self.assertEqual(GL.tiles(32), (6, 6))
        self.assertEqual(GL.atlas_size(32), (192, 192))
        self.assertEqual(GL.atlas_size(64), (512, 512))
        self.assertEqual(GL.atlas_size(128), (1536, 1408))
        self.assertEqual(GL.atlas_size(96), (960, 960))
        self.assertEqual([GL.snap_res(x) for x in (5, 16, 30, '64', 1000)], [8, 16, 32, 64, 256])

    def test_atlas_round_trip(self):
        for N in (16, 32, 96):
            tx = GL.tiles(N)[0]
            seen = set()
            for v in [(0, 0, 0), (N - 1, N - 1, N - 1), (3, 5, 7), (N - 1, 0, N // 2)]:
                a = GL.atlas_xy(v, N, tx)
                self.assertEqual(GL.voxel_of_atlas(a, N, tx), v)
                seen.add(a)
            aw, ah = GL.atlas_size(N)
            if GL.tiles(N)[0] * GL.tiles(N)[1] > N:                              # last tile unused
                self.assertIsNone(GL.voxel_of_atlas((aw - 1, ah - 1), N, tx))
            vol = np.random.default_rng(N).uniform(size=(N, N, N, 2))
            img = GL.to_atlas(vol, N, tx)
            self.assertEqual(img.shape[:2], (ah, aw))
            np.testing.assert_array_equal(GL.from_atlas(img, N, tx), vol)
            x, y, z = 3, 5, 7
            ax, ay = GL.atlas_xy((x, y, z), N, tx)
            np.testing.assert_array_equal(img[ay, ax], vol[z, y, x])

    def test_jfa_steps_and_dispatch(self):
        self.assertEqual(GL.jfa_steps(32), [16, 8, 4, 2, 1, 1, 0, 0])
        self.assertEqual(GL.jfa_steps(128), [64, 32, 16, 8, 4, 2, 1, 1])
        self.assertEqual(GL.jfa_steps(16), [8, 4, 2, 1, 1, 0, 0, 0])
        self.assertEqual(GL.dispatch(64), (8, 8, 8))

    def test_grid_region_packed(self):
        tx = GL.grid_texels({'on': True, 'paint_on': True, 'centre': (0, 1, 0), 'size': 4.0, 'res': 32,
                             'paint_res': 64})
        self.assertEqual(tx[0], [2.0, 2.0, 0.0, 0.0])
        self.assertEqual(tx[1], [-2.0, -1.0, -2.0, 0.125])
        self.assertEqual(tx[2], [32.0, 6.0, 1.0, 1.0])
        self.assertEqual(tx[4], [64.0, 8.0, 2.0, 1.0])
        self.assertEqual(GL.grid_texels({}), [])
        rs = rows_of(('sphere', 's', {}), ('light', 'l', {}), ('pts', 'p', {}))
        effs = [L.effector(rs[0]), L.effector(rs[1], light={}), L.effector(rs[2], points=[(0, 0, 0)])]
        tex = L.pack_buffer(effs, grid=tx)
        l0 = 1 + 3 * L.W
        g0 = l0 + 1 + L.LW
        self.assertEqual(tex[l0], [1.0, float(L.LW), 0.0, float(g0)])
        self.assertEqual(L.grid_start(tex), g0)
        self.assertEqual(tex[0][2], float(g0 + len(tx)))                        # points after the grid region
        self.assertEqual(L.read_row(tex, 2)[8][2], float(g0 + len(tx)))
        f = GL.read_layer(tex, GL.LAYER_FIELD)
        self.assertEqual((f['N'], f['TX'], f['cell'], f['origin']), (32, 6, 0.125, (-2.0, -1.0, -2.0)))
        self.assertEqual(GL.read_layer(tex, GL.LAYER_PAINT)['N'], 64)
        tex0 = L.pack_buffer(effs)
        sel = L.sel_vec('all', rs)[0]
        for p in ((0.3, 0, 0), (0.0, 0.0, 0.1), (3, 0, 0)):                    # v2 readers unchanged
            self.assertEqual(L.ref_weight(tex, p, sel), L.ref_weight(tex0, p, sel))
        self.assertIsNone(GL.read_layer(tex0, GL.LAYER_FIELD))

    def test_cloud_row(self):
        rs = rows_of(('cloud', 'c', {'radius': 0.25}), ('cloud', 'off', {'enabled': 0}))
        tex = L.pack_buffer([L.effector(rs[0]), L.effector(rs[1])])
        r = L.read_row(tex, 0)
        self.assertEqual(L.names(L.KINDS).index('cloud'), 12)
        self.assertEqual((r[3][0], r[3][1], r[6][3], r[8][1]), (7.0, 1.0, 0.0, 12.0))
        self.assertEqual(L.read_row(tex, 1)[3][1], 0.0)
        self.assertEqual(L.colliders(tex, L.sel_vec('all', rs)[0]), [])             # never a collider / v2 effector
        self.assertEqual(L.ref_weight(tex, (0, 0, 0), L.sel_vec('all', rs)[0])[0], 0.0)


class Field(unittest.TestCase):
    def test_scatter_counts_and_centroids(self):
        g = GL.geometry((0.0, 0.0, 0.0), 2.0, 16)
        rng = np.random.default_rng(3)
        P = rng.uniform(-1.2, 1.2, size=(5000, 3))                              # some outside the grid
        vol = GL.scatter_ref(P, g)
        V = np.floor((P - np.asarray(g['origin'])) / g['cell']).astype(int)
        inside = np.all((V >= 0) & (V < 16), axis=1)
        H = np.zeros((16, 16, 16))
        np.add.at(H, (V[inside, 2], V[inside, 1], V[inside, 0]), 1)
        np.testing.assert_array_equal(vol[..., 3], H)
        self.assertEqual(vol[..., 3].sum(), inside.sum())
        valid = np.where(np.arange(5000) % 2 == 0, 1.0, 0.0)                     # alpha test
        self.assertEqual(GL.scatter_ref(P, g, valid=valid)[..., 3].sum(), inside[::2].sum())
        seeds = GL.seeds_ref(vol, g)
        z, y, x = np.argwhere(H > 0)[0]
        m = (V[:, 0] == x) & (V[:, 1] == y) & (V[:, 2] == z) & inside
        np.testing.assert_allclose(seeds[z, y, x, :3], P[m].mean(axis=0), atol=g['cell'] / 1024.0)
        self.assertTrue(np.all(seeds[H == 0][:, 3] == 0.0))
        prev = GL.scatter_ref(P[:100], g)
        np.testing.assert_allclose(GL.scatter_ref(P[100:], g, prev=prev), vol)  # chained passes add up

    def test_jfa_finds_nearest_seed(self):
        """After the JFA passes each voxel holds (almost always) the seed nearest to its centre (brute force)."""
        g = GL.geometry((0.0, 0.0, 0.0), 2.0, 16)
        P = sphere_surface(800, 0.6, (0.1, -0.2, 0.0))
        seeds = GL.seeds_ref(GL.scatter_ref(P, g), g)
        fld = GL.field_ref(P, g)
        S = seeds[seeds[..., 3] > 0.5][:, :3]
        C = GL.voxel_centres(g).reshape(-1, 3)
        bd = GL.brute_nearest(S, C)
        jd = np.sqrt(((fld.reshape(-1, 4)[:, :3] - C) ** 2).sum(-1))
        self.assertTrue(np.all(fld[..., 3] > 0.5))                               # flooded everywhere
        self.assertGreater(np.mean(np.abs(jd - bd) < 1e-9), 0.99)
        self.assertLess(np.max(jd - bd), 0.5 * g['cell'])

    def _err(self, P, g, Q):
        fld = GL.field_ref(P, g)
        return np.abs(GL.query_ref(fld, g, Q) - GL.brute_nearest(P, Q)) / g['cell']

    def test_k36_error_below_one_cell(self):
        """K36 check: field distance vs brute force over many query points, max error < 1 cell, for a dense surface
        (20 000 points > 4096), a sparse random set and a clustered set."""
        rng = np.random.default_rng(9)
        g = GL.geometry((0.0, 1.0, 0.0), 4.0, 32)
        Q = rng.uniform(-2.0, 2.0, size=(2000, 3)) + np.array([0.0, 1.0, 0.0])
        for P in (sphere_surface(20000, 1.0), rng.uniform(-1.5, 1.5, size=(300, 3)) + [0, 1, 0],
                  np.concatenate([rng.normal(c, 0.15, size=(3000, 3)) for c in ((0.5, 1.0, 0.0), (-0.8, 1.6, 0.4))])):
            e = self._err(P, g, Q)
            self.assertLess(e.max(), 1.0)
            self.assertLess(np.median(e), 0.3)

    def test_query_outside_grid_and_empty(self):
        g = GL.geometry((0.0, 0.0, 0.0), 2.0, 16)
        P = np.array([[0.0, 0.0, 0.0]])
        fld = GL.field_ref(P, g)
        d = GL.query_ref(fld, g, [(5.0, 0.0, 0.0)])[0]
        self.assertAlmostEqual(d, 5.0, delta=g['cell'])                          # clamped voxel, true distance
        empty = GL.field_ref(np.zeros((0, 3)), g)
        self.assertEqual(GL.query_ref(empty, g, [(0.0, 0.0, 0.0)])[0], 1e9)

    def test_weight_with_cloud(self):
        """ref_weight(field=...) = a consumer compiled with PXE_GRID: the cloud acts like a point set with its row
        radius / falloff; without the field (older consumers) it is ignored."""
        g = GL.geometry((0.0, 1.0, 0.0), 4.0, 32)
        P = sphere_surface(6000, 1.0)
        fld = GL.field_ref(P, g)
        rs = rows_of(('cloud', 'c', {'radius': 0.5, 'falloff': 'linear', 'tags': 'body'}), ('sphere', 's', {}))
        tex = L.pack_buffer([L.effector(rs[0]), L.effector(rs[1], [[1, 0, 0, 9], [0, 1, 0, 9], [0, 0, 1, 9]])])
        sel = L.sel_vec('#body', rs)[0]
        for p in ((0.0, 1.0, 0.0), (0.0, 2.2, 0.0), (0.0, 3.0, 0.0)):
            d = GL.brute_nearest(P, [p])[0]
            w, b = L.ref_weight(tex, p, sel, field=(fld, g))
            self.assertAlmostEqual(w, max(0.0, 1.0 - d / 0.5), delta=g['cell'] / 0.5)
            self.assertEqual(L.ref_weight(tex, p, sel)[0], 0.0)
        self.assertEqual(L.ref_weight(tex, (0.0, 2.0, 0.0), sel, field=(fld, g))[1], 0)

    def test_cost_65k_numpy(self):
        """65 536 points through the numpy twin at N = 32 (CPU reference only; the GPU cost is LIVE CHECK VG6)."""
        P = sphere_surface(65536, 1.2)
        g = GL.geometry((0.0, 1.0, 0.0), 4.0, 32)
        t = time.time()
        vol = GL.scatter_ref(P, g)
        self.assertEqual(vol[..., 3].sum(), 65536)
        self.assertLess(time.time() - t, 5.0)


class PaintAndSample(unittest.TestCase):
    def test_paint_step(self):
        prev = np.array([0.0, 0.5, 1.0, 0.2])
        out = GL.paint_step_ref(prev, np.array([1.0, 0.0, 1.0, 0.0]), np.array([0.0, 0.0, 0.0, 1.0]), 2.0, 0.5, 0.1)
        np.testing.assert_allclose(out[:, 0], [0.2, 0.475, 1.0, 0.0])
        np.testing.assert_allclose(GL.paint_step_ref(prev, 1.0, 0.0, 2.0, 0.0, 0.1, clear=True)[:, 0], 0.0)
        np.testing.assert_allclose(out[:, 3], 1.0)

    def test_paint_stays_after_the_brush_leaves(self):
        """SA23: a #paint sphere sweeps through the volume; painted voxels keep 1 after it has gone (decay 0); an
        #erase effector clears where it passes."""
        g = GL.geometry((0.0, 0.0, 0.0), 2.0, 8)
        Cc = GL.voxel_centres(g).reshape(-1, 3)
        rs = rows_of(('null', 'brush', {'tags': 'paint', 'radius': 0.4, 'falloff': 'step'}),
                     ('null', 'eraser', {'tags': 'erase', 'radius': 0.3, 'falloff': 'step', 'enabled': 0}))
        sp, se = L.sel_vec('#paint', rs)[0], L.sel_vec('#erase', rs)[0]
        paint = np.zeros(len(Cc))
        far = [[1, 0, 0, 50], [0, 1, 0, 50], [0, 0, 1, 50]]

        def frame(bx, rows_, ex=None):
            effs = [L.effector(rows_[0], [[1, 0, 0, bx], [0, 1, 0, 0], [0, 0, 1, 0]]),
                    L.effector(rows_[1], far if ex is None else [[1, 0, 0, ex], [0, 1, 0, 0], [0, 0, 1, 0]])]
            tex = L.pack_buffer(effs)
            wa = np.array([L.ref_weight(tex, c, sp)[0] for c in Cc])
            we = np.array([L.ref_weight(tex, c, se)[0] for c in Cc])
            return wa, we
        for bx in np.linspace(-0.8, 0.8, 9):
            wa, we = frame(bx, rs)
            paint = GL.paint_step_ref(paint, wa, we, 20.0, 0.0, 0.1)[:, 0]
        trail = (np.hypot(Cc[:, 1], Cc[:, 2]) < 0.35) & (np.abs(Cc[:, 0]) < 0.8)  # within reach of a brush stop
        wa, we = frame(50.0, rs)                                                  # brush gone
        paint = GL.paint_step_ref(paint, wa, we, 20.0, 0.0, 0.1)[:, 0]
        self.assertTrue(np.all(paint[trail] == 1.0))
        self.assertTrue(np.all(paint[np.abs(Cc[:, 1]) > 0.6] == 0.0))
        rs2 = L.set_value(rs, 'eraser', 'enabled', '1')
        wa, we = frame(50.0, rs2, ex=0.0)
        paint2 = GL.paint_step_ref(paint, wa, we, 20.0, 0.0, 0.1)[:, 0]
        self.assertTrue(np.all(paint2[np.linalg.norm(Cc, axis=1) < 0.3] == 0.0))
        self.assertEqual(paint2[trail].max(), 1.0)

    def test_sample_trilinear(self):
        g = GL.geometry((0.0, 0.0, 0.0), 2.0, 8)
        Cc = GL.voxel_centres(g)
        vol = np.zeros((8, 8, 8, 1))
        vol[..., 0] = Cc[..., 0] * 2.0 + Cc[..., 1] - Cc[..., 2]                  # linear: trilinear is exact
        Q = np.random.default_rng(1).uniform(-0.8, 0.8, size=(100, 3))
        np.testing.assert_allclose(GL.sample_ref(vol, g, Q), Q[:, 0] * 2 + Q[:, 1] - Q[:, 2], atol=1e-12)
        np.testing.assert_allclose(GL.sample_ref(vol, g, Cc.reshape(-1, 3)[:5]), vol.reshape(-1)[:5], atol=1e-12)


class TDText(unittest.TestCase):
    def test_grid_module(self):
        src = rd(os.path.join(BUILDERS, 'effectors_grid.py'))
        src.encode('ascii')
        self.assertNotIn('.destroy()', src)
        fs = set(n.name for n in ast.parse(src).body if isinstance(n, ast.FunctionDef))
        for f in ('build', 'sync', 'park', 'on_pulse', 'texels', 'u', 'vals'):
            self.assertIn(f, fs)
        ns = {}
        exec(compile(src, 'effectors_grid.py', 'exec'), ns)
        ns['GL'] = lambda: GL
        ns['vals'] = lambda: GL.grid_values({'on': True, 'res': 64, 'paint_res': 32, 'size': 8.0})
        self.assertEqual(ns['u']('field', 'atlas', 0), 512)
        self.assertEqual(ns['u']('field', 'dispatch', 0), 8)
        self.assertEqual(ns['u']('paint', 'uGridN', 0), 32.0)
        self.assertEqual(ns['u']('field', 'uGrid', 3), 0.125)
        self.assertEqual(ns['u']('field', 'jfa', 0), 32.0)
        self.assertEqual(ns['texels']()[2][:3], [64.0, 8.0, 1.0])

    def test_builder_and_runtime_wiring(self):
        b = rd(os.path.join(BUILDERS, 'effectors.py'))
        rt = rd(os.path.join(BUILDERS, 'effectors_rt.py'))
        for s in ("_pars(c, 'Grid', _grid_logic()['grid_pars']())", "gr.module.build(grid_texts(Lg))",
                  "gx.par.pars = 'Gridon Painton Paintclear Paintsave Paintload'"):
            self.assertIn(s, b)
        for s in ("def row_index(name):", "def _grid_sync():", "o.create(selectTOP, 'cloud_src')",
                  "return m.module.texels() if m is not None else None"):
            self.assertIn(s, rt)
        ns = {}
        exec(compile(b, 'effectors.py', 'exec'), ns)
        ast.parse(ns['GRID_PARS'])
        for n, style, d, o in GL.grid_pars():
            self.assertIn(style, ('Menu', 'Str', 'Float', 'Toggle', 'Pulse', 'XYZ'))
            if style == 'Menu':
                self.assertIn(d, o['names'])


STUB = """#version 460
#define TD_NUM_2D_INPUTS %d
uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
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

    def pre(self, *defines):
        return L.consumer_prefix(rd(os.path.join(GLSL, 'px_common.glsl')), rd(os.path.join(GLSL, 'eff_consumer.glsl')),
                                 defines)

    def test_passes(self):
        self._ok(STUB % 2 + rd(os.path.join(GLSL, 'eff_grid_scatter.glsl')), 'comp', 'scatter')
        self._ok(STUB % 0 + rd(os.path.join(GLSL, 'eff_grid_scatter.glsl')), 'comp', 'scatter (inputs unwired)')
        for n in ('seed', 'jfa'):
            self._ok(STUB % 1 + rd(os.path.join(GLSL, 'eff_grid_%s.glsl' % n)), 'comp', n)
        self._ok(STUB % 1 + self.pre() + rd(os.path.join(GLSL, 'eff_grid_paint.glsl')), 'comp', 'paint')

    def test_consumer_with_grid(self):
        """A consumer compiled with PXE_GRID + PXE_PAINT (cloud rows in pxeW, pxgSample, pxePaint) and the same
        consumer without them (the default: unchanged code path)."""
        body = """
layout(local_size_x = 8, local_size_y = 8) in;
void main()
{
	vec3 p = vec3(gl_GlobalInvocationID.xy, 0.0) * 0.01;
	int b;
	float w = pxeW(p, uEffSel, uEffIds, uEffMix, uEffFall, b);
	vec3 g = b >= 0 ? pxeGrad(b, p) : vec3(0.0);
#ifdef PXE_PAINT
	w += pxePaint(p);
	int L = pxgLayer(PXG_PAINT);
	if (L >= 0) w += pxgSample(PXE_PAINT, L, p).g;
#endif
	TDImageStoreOutput(0, ivec3(gl_GlobalInvocationID.xy, 0), vec4(g, w));
}
"""
        grid = '#define PXE_GRID sTD2DInputs[1]\n#define PXE_PAINT sTD2DInputs[2]\n'
        pre = self.pre()
        self._ok(STUB % 3 + pre.replace('#define PX_PACKED_ONLY', grid + '#define PX_PACKED_ONLY', 1) + body, 'comp',
                 'consumer with the grid')
        self._ok(STUB % 1 + pre + body, 'comp', 'consumer without the grid')
        mat = ('#version 460\nuniform sampler2D sEffGrid;\nuniform sampler2D sEffPaint;\nout vec4 fragColor;\n' +
               GL.consumer_defines('sEffGrid', 'sEffPaint') + pre +
               'void main() { int b; fragColor = vec4(pxeW(vec3(0.0), uEffSel, uEffIds, uEffMix, uEffFall, b) + '
               'pxePaint(vec3(0.0))); }\n')
        self._ok(mat, 'frag', 'GLSL MAT style (Samplers page names)')

    def test_query_corner_order_matches_ref(self):
        """pxgFieldNearest visits the 8 corners (c & 1, c >> 1 & 1, c >> 2 & 1) from floor((p - origin) / cell - 0.5),
        as query_ref; the atlas mapping in the shaders matches atlas_xy."""
        g = rd(os.path.join(GLSL, 'px_common.glsl'))
        e = rd(os.path.join(GLSL, 'eff_consumer.glsl'))
        self.assertIn('ivec3 b = ivec3(floor((p - a.xyz) / a.w - 0.5));', e)
        self.assertIn('b + ivec3(c & 1, (c >> 1) & 1, (c >> 2) & 1)', e)
        for f in ('eff_consumer.glsl', 'eff_grid_scatter.glsl', 'eff_grid_jfa.glsl'):
            self.assertIn('v.x + (v.z % tx) * N, v.y + (v.z / tx) * N', rd(os.path.join(GLSL, f)), f)
        self.assertIn('const int PXE_SD_GRID = %d;' % L.SD_GRID, g)
        self.assertIn('const float GRID_FX = %.1f;' % GL.FX, rd(os.path.join(GLSL, 'eff_grid_scatter.glsl')))
        for f in ('eff_grid_scatter.glsl', 'eff_grid_seed.glsl', 'eff_grid_jfa.glsl', 'eff_grid_paint.glsl'):
            rd(os.path.join(GLSL, f)).encode('ascii')


if __name__ == '__main__':
    unittest.main()
