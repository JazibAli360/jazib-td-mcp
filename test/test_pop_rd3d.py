"""Offline tests for builders/pop_rd3d.py + pop_rd3d_logic.py (lane H TC-11; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_rd3d.py'"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_rd3d_logic as L  # noqa: E402


class Logic(unittest.TestCase):
    def test_conserves_sum_without_reaction_terms(self):
        rng = np.random.default_rng(3)
        s = np.zeros((40, 56, 4))
        s[..., 0] = rng.random((40, 56))
        s[..., 1] = rng.random((40, 56))
        o = L.gs_step(s, 0.0, 0.0, du=0.5, dv=0.5)
        # F = k = 0, equal D: dU + dV = D lap(U + V) and the 3x3 kernel sums to 0 on a wrap grid
        self.assertAlmostEqual((o[..., 0] + o[..., 1]).sum(), (s[..., 0] + s[..., 1]).sum(), 9)
        o = L.gs_step(s, 0.0, 0.0, du=0.0, dv=0.0)                        # no diffusion: U+V per cell
        self.assertTrue(np.allclose(o[..., 0] + o[..., 1], s[..., 0] + s[..., 1]))

    def test_fixed_point(self):
        s = np.zeros((16, 16, 4), dtype=np.float32)
        s[..., 0] = 1.0
        s[..., 3] = 1.0
        for f, k in [(p[1], p[2]) for p in L.PRESETS]:
            o = L.gs_step(s, f, k)
            self.assertTrue(np.array_equal(o[..., :2], s[..., :2]))
            self.assertTrue((o[..., 2] == 1).all())

    def test_one_cell_by_hand(self):
        s = np.zeros((5, 5, 4))
        s[..., 0] = 1.0
        s[2, 2, 1] = 1.0                                                    # one V spot
        f, k = 0.0545, 0.062
        o = L.gs_step(s, f, k)
        # centre: lapU = 0 (U = 1 everywhere), lapV = -1; uvv = 1
        self.assertAlmostEqual(o[2, 2, 0], 1.0 + (0.0 - 1.0 + f * 0.0))
        self.assertAlmostEqual(o[2, 2, 1], 1.0 + (0.5 * -1.0 + 1.0 - (f + k)))
        # edge neighbour: lapV = 0.2, U = 1, V = 0
        self.assertAlmostEqual(o[2, 3, 1], 0.5 * 0.2)
        self.assertAlmostEqual(o[3, 3, 1], 0.5 * 0.05)
        self.assertAlmostEqual(o[0, 0, 1], 0.0)

    def test_wrap(self):
        s = np.zeros((6, 6, 4))
        s[..., 0] = 1.0
        s[0, 0, 1] = 1.0
        o = L.gs_step(s, 0.03, 0.06)
        self.assertAlmostEqual(o[5, 0, 1], 0.1)                            # wraps to the top row
        self.assertAlmostEqual(o[5, 5, 1], 0.025)

    def test_stopat(self):
        a = L.run(32, 32, 1, 0.0545, 0.062, 30, stopat=10)
        b = L.run(32, 32, 1, 0.0545, 0.062, 10)
        self.assertTrue(np.array_equal(a, b))
        self.assertEqual(a[0, 0, 2], 10)

    def test_seed(self):
        s = L.seed_state(128, 128, 1)
        self.assertTrue(set(np.unique(s[..., 1])) <= {0.0, 1.0})
        self.assertTrue((s[..., 0] == 1).all())
        frac = s[..., 1].mean()
        self.assertGreater(frac, 0.02)
        self.assertLess(frac, 0.2)
        self.assertFalse(np.array_equal(s, L.seed_state(128, 128, 2)))

    def test_grows_and_finite(self):
        for n in L.PRESET_NAMES[:-1]:
            f, k = L.fk(n)
            s = L.run(64, 64, 1, f, k, 200)
            self.assertTrue(np.isfinite(s).all(), n)
            self.assertTrue((s[..., :2] > -0.5).all() and (s[..., :2] < 1.5).all(), n)

    def test_surface(self):
        u, v = np.meshgrid(np.linspace(0, 1, 9), np.linspace(0, 1, 7))
        p, n = L.base('torus', u, v)
        ring = np.hypot(p[..., 0], p[..., 1])
        self.assertTrue(np.allclose((ring - L.TORUS_R) ** 2 + p[..., 2] ** 2, L.TORUS_r ** 2))
        self.assertTrue(np.allclose(np.linalg.norm(n, axis=-1), 1))
        p, n = L.base('sphere', u, v)
        self.assertTrue(np.allclose(np.linalg.norm(p, axis=-1), L.SPHERE_R))
        vt = np.full((8, 8, 4), 0.5)
        q = L.surface('torus', u, v, vt[..., 1], 0.2)
        p, n = L.base('torus', u, v)
        self.assertTrue(np.allclose(q, p + 0.1 * n))
        self.assertTrue(np.allclose(L.surface('plane', u, v, vt[..., 1], 0.0), L.base('plane', u, v)[0]))


class Fused(unittest.TestCase):
    def test_fused_equals_chain(self):
        for (w, h), steps, stopat in (((64, 64), 4, -1), ((40, 56), 2, -1), ((48, 48), 4, 6), ((256, 256), 1, -1)):
            s = L.run(w, h, 3, 0.0545, 0.062, 5)
            a = s
            for _ in range(steps):
                a = L.gs_step(a, 0.0545, 0.062, stopat)
            b = L.fused(s, 0.0545, 0.062, steps, stopat)
            self.assertTrue(np.array_equal(a, b), (w, h, steps, stopat, float(np.abs(a - b).max())))


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_rd3d.py')
        o = c.ops
        for n in ('in1', 'pulses', 'blank', 'state_fb', 'gs', 'state', 'out2',
                  'clock', 'surf', 'mat', 'geo', 'cam', 'render', 'out_sel', 'out1'):
            self.assertIn(n, o)
        for n in ('gs1', 'gs2', 'gs3', 'gs4', 'step_sel'):
            self.assertNotIn(n, o)
        self.assertEqual(K.src(o['gs'], 0), 'state_fb')
        self.assertEqual(o['state_fb'].par.top.val, 'state')
        self.assertEqual(K.src(o['state'], 0), 'gs')
        g = o['gs']
        self.assertEqual((g.par.mode.val, g.par.format.val), ('compute', 'rgba32float'))
        self.assertEqual(K.uniform_names(g), ['uP', 'uP2', 'uP3'])
        self.assertEqual(o['surf'].par.surftype.val, 'quads')
        m = o['mat']
        self.assertEqual((m.par.sampler0name.val, m.par.sampler0top.val), ('sSt', 'state'))
        self.assertEqual((m.par.sampler0extendu.val, m.par.sampler0extendv.val), ('repeat', 'repeat'))
        self.assertEqual(K.uniform_names(m), [u for u, _ in ns['MAT_UNIFORMS']])
        self.assertEqual(o['geo'].op('sel').par.pop.val, '../surf')
        self.assertEqual(o['pulses'].par.pars.val, 'Reseed')
        compile(o['pulses'].text, 'pulses', 'exec')
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        self.assertEqual(c.par.Simres.max, 1024)
        self.assertEqual(c.par.Simres.val, 256)

    def test_first(self):
        c, reply, ns = K.fake_build('pop_rd3d.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_preset_table_matches_logic(self):
        _c, _r, ns = K.fake_build('pop_rd3d.py')
        for i, n in enumerate(ns['PRESETS'][:-1]):
            self.assertEqual(ns['PRESET_FK'][i], L.fk(n))
        self.assertEqual(ns['PRESETS'], L.PRESET_NAMES)

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_rd3d.py')
        for u, _ in ns['SIM_UNIFORMS']:
            self.assertIn(u, K.declared(ns['GSF']))
        for u, _ in ns['MAT_UNIFORMS']:
            self.assertIn(u, K.declared(ns['VERTEX']) + K.declared(ns['PIXEL']))
        self.assertIn('TDPos()', ns['VERTEX'])

    def test_ascii(self):
        for f in ('pop_rd3d.py', 'pop_rd3d_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_rd3d.py')
        for fn, t in ((K.glslc_compute, ns['GS']), (K.glslc_compute, ns['GSF']), (K.glslc_vert, ns['VERTEX']), (K.glslc_pixel, ns['PIXEL'])):
            ok, err = fn(t)
            self.assertTrue(ok, err)
            self.assertEqual(K.bounded_loops(t), [])


if __name__ == '__main__':
    unittest.main()
