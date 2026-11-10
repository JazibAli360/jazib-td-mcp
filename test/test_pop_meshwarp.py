"""Offline tests for builders/pop_meshwarp.py + pop_meshwarp_logic.py (lane H TC-07; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_meshwarp.py'"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_meshwarp_logic as L  # noqa: E402


class Logic(unittest.TestCase):
    def test_identity_when_off(self):
        u, v = np.meshgrid(np.linspace(0, 1, 33), np.linspace(0, 1, 57))
        for m in L.MODES:
            for kw in ({'strength': 0.0}, {'amount': 0.0}):
                uu, vv, dz = L.warp(u, v, L.params(mode=m, time=0.37, **kw))
                self.assertTrue(np.allclose(uu, u) and np.allclose(vv, v) and np.allclose(dz, 0), (m, kw))

    def test_depth_only_moves_z(self):
        u, v = np.meshgrid(np.linspace(0, 1, 17), np.linspace(0, 1, 29))
        for m in L.MODES:
            a = L.warp(u, v, L.params(mode=m, time=1.3, depth=0.0))
            b = L.warp(u, v, L.params(mode=m, time=1.3, depth=1.0))
            self.assertTrue(np.allclose(a[0], b[0]) and np.allclose(a[1], b[1]), m)
            self.assertTrue(np.allclose(a[2], 0.0), m)

    def test_bounded_and_finite(self):
        u, v = np.meshgrid(np.linspace(0, 1, 65), np.linspace(0, 1, 115))
        for m in L.MODES:
            for t in (0.0, 0.5, 3.7):
                uu, vv, dz = L.warp(u, v, L.params(mode=m, time=t, strength=2.0))
                for a in (uu, vv, dz):
                    self.assertTrue(np.isfinite(a).all(), m)
                lim = 2.0 / L.DEFAULTS['aspect'] if m == 'swirl' else 0.75   # swirl: 2 pi turn at Strength 2
                self.assertLess(np.abs(uu - u).max(), lim, m)
                self.assertLess(np.abs(vv - v).max(), max(lim, 0.75), m)
                self.assertLess(np.abs(dz).max(), 1.01 * 0.3 * 2.0 + 1e-9, m)

    def test_hash_ranges_and_known(self):
        h = L.h1(np.arange(-500, 500), 3)
        self.assertTrue((h >= 0).all() and (h < 1).all())
        self.assertLess(abs(h.mean() - 0.5), 0.05)
        self.assertEqual(int(L.lowbias(0)), 0)                     # lowbias32(0) = 0
        n = L.vnoise(np.linspace(-3, 3, 200), np.linspace(-2, 2, 200), 5)
        self.assertTrue((n >= 0).all() and (n <= 1).all())

    def test_vnoise_continuous(self):
        x = np.linspace(-2, 2, 4001)
        n = L.vnoise(x, np.full_like(x, 0.3), 9)
        self.assertLess(np.abs(np.diff(n)).max(), 0.01)

    def test_swirl_keeps_radius(self):
        u, v = np.meshgrid(np.linspace(0, 1, 21), np.linspace(0, 1, 31))
        p = L.params(mode='swirl', strength=1.0, time=0.0)
        uu, vv, _ = L.warp(u, v, p)
        r0 = np.hypot((u - 0.5) * p['aspect'], v - 0.5)
        r1 = np.hypot((uu - 0.5) * p['aspect'], vv - 0.5)
        self.assertTrue(np.allclose(r0, r1, atol=1e-12))

    def test_normals_flat_and_unit(self):
        u, v = np.meshgrid(np.linspace(0, 1, 9), np.linspace(0, 1, 9))
        n = L.normal(u, v, L.params(depth=0.0), 1 / 127.0, 1 / 227.0)
        self.assertTrue(np.allclose(n, [0, 0, 1]))
        n = L.normal(u, v, L.params(mode='wave', depth=1.0, time=0.2), 1 / 127.0, 1 / 227.0)
        self.assertTrue(np.allclose(np.linalg.norm(n, axis=-1), 1.0))
        self.assertTrue(np.allclose(L.shade(np.array([[0, 0, 1.0]]), 0.0), 1.0))

    def test_reference_identity_and_mesh_error(self):
        W, H = 108, 192
        img = L.test_card(W, H)
        out = L.reference_flat(img, L.params(strength=0.0), W, H)
        self.assertLess(np.abs(out - img).max(), 1e-12)
        for m in L.MODES:
            p = L.params(mode=m, time=0.4, strength=0.6)
            a = L.reference_flat(img, p, W, H)
            b = L.reference_mesh_flat(img, p, W, H, 128, 228)
            self.assertLess(np.abs(a - b).mean(), 0.02, m)        # piecewise-linear error at default detail

    def test_vfov_fill(self):
        self.assertAlmostEqual(L.vfov_deg(0.5, 1.0), 90.0)
        self.assertAlmostEqual(L.vfov_deg(1.2, 2.0), L.vfov_deg(1.2, 1.0) / 2)


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_meshwarp.py')
        o = c.ops
        for n in ('in1', 'clock_rate', 'clock', 'sheet', 'mat', 'mat_vertex', 'mat_pixel', 'geo', 'cam', 'render',
                  'out_sel', 'out1'):
            self.assertIn(n, o)
        self.assertEqual(o['sheet'].par.surftype.val, 'quads')
        self.assertEqual(o['sheet'].par.texture.val, 'point')
        self.assertEqual((o['sheet'].par.sizex.val, o['sheet'].par.sizey.val), (1.0, 1.0))
        self.assertEqual(o['geo'].op('sel').par.pop.val, '../sheet')
        self.assertEqual(o['geo'].par.material.val, 'mat')
        self.assertEqual(o['render'].par.camera.val, 'cam')
        self.assertEqual([K.src(o['out_sel'], 0), K.src(o['out_sel'], 1)], ['img_src', 'render'])
        self.assertEqual([K.src(o['img_src'], 0), K.src(o['img_src'], 1)], ['test_clip', 'in1'])   # drop-in demo input
        self.assertEqual(K.src(o['out1'], 0), 'out_sel')
        self.assertEqual(K.src(o['clock'], 0), 'clock_rate')
        m = o['mat']
        self.assertEqual((m.par.sampler0name.val, m.par.sampler0top.val), ('sIn', 'img_src'))
        self.assertEqual(K.uniform_names(m), [u for u, _ in ns['UNIFORMS']])
        self.assertEqual(o['cam'].par.viewanglemethod.val, 'vertfov')
        self.assertEqual(o['mat_vertex'].dock, m)
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        for n in ('Amount', 'Mode', 'Cols', 'Rows', 'Resw', 'Resh'):
            self.assertIn(n, c.custom)
        self.assertEqual(c.par.Cols.max, 512)                     # hard cap (T-124 / T-193)

    def test_first_frame(self):
        c, reply, ns = K.fake_build('pop_meshwarp.py', first=True)
        self.assertEqual((c.par.Cols.val, c.par.Rows.val), (64, 114))
        self.assertEqual(reply['notes'], [])

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_meshwarp.py')
        decl = K.declared(ns['VERTEX'])
        for u, _ in ns['UNIFORMS']:
            self.assertIn(u, decl)
        self.assertIn('TDPos()', ns['VERTEX'])
        self.assertNotIn('#version', ns['VERTEX'] + ns['PIXEL'])

    def test_ascii(self):
        for f in ('pop_common.py', 'pop_meshwarp.py', 'pop_meshwarp_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_meshwarp.py')
        ok, err = K.glslc_vert(ns['VERTEX'])
        self.assertTrue(ok, err)
        ok, err = K.glslc_pixel(ns['PIXEL'])
        self.assertTrue(ok, err)
        self.assertEqual(K.bounded_loops(ns['VERTEX']), [])


if __name__ == '__main__':
    unittest.main()
