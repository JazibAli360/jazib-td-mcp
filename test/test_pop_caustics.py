"""Offline tests for builders/pop_caustics.py + pop_caustics_logic.py (lane H TC-30; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_caustics.py'"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_caustics_logic as L  # noqa: E402

for _c in ('renderselectTOP',):
    if _c not in K.TD_CLASSES:
        K.TD_CLASSES.append(_c)


class Logic(unittest.TestCase):
    def test_flat_water_exact_one(self):
        for side in (16, 128):
            D = L.deposit(L.params(amp=0.0, side=side, simres=side))
            self.assertEqual(D.sum(), side * side)
            self.assertTrue((D == 1.0).all())

    def test_jitter_keeps_sums(self):
        for side in (16, 128):                        # |jitter| < half a cell: flat still lands one ray per texel
            D = L.deposit(L.params(amp=0.0, side=side, simres=side, jitter=1.0, salt=12345))
            self.assertTrue((D == 1.0).all())
        side = 96
        p = L.params(amp=0.03, freq=5.0, side=side, simres=side, floorsize=4.0, time=0.7, jitter=1.0)
        D0, D1 = L.deposit(dict(p, salt=7)), L.deposit(dict(p, salt=8))
        self.assertEqual(D0.sum(), side * side)
        self.assertEqual(D1.sum(), side * side)
        self.assertGreater(np.abs(D0 - D1).sum(), 0.0)     # the salt (frame) moves the rays
        i, j = np.mgrid[0:64, 0:64]
        jx, jy = L.ray_jitter(i, j, 3, 1.0)
        self.assertLess(max(np.abs(jx).max(), np.abs(jy).max()), 0.5)
        self.assertLess(abs(jx.mean()) + abs(jy.mean()), 0.02)
        self.assertTrue((L.ray_jitter(i, j, 3, 0.0)[0] == 0).all())

    def test_jitter_breaks_lattice(self):
        # Rays sparser than texels (Simres 160 > Rays 64): the grid deposit is a periodic dot lattice (one sharp
        # spectral peak, ratio ~3200); jittered it is grain (ratio ~10), same ray count.
        def peak(D):
            F = np.abs(np.fft.fft2(D - D.mean())) ** 2
            F[0, 0] = 0.0
            return F.max() / F.mean()
        p = L.params(amp=0.0, side=64, simres=160, floorsize=2.0)
        grid, jit = L.deposit(p), L.deposit(dict(p, jitter=1.0, salt=5))
        self.assertEqual(grid.sum(), jit.sum())
        self.assertGreater(peak(grid), 1000.0)
        self.assertLess(peak(jit), 50.0)

    def test_refract_matches_snell(self):
        I = L.norm(np.array([[0.3, 0.0, -1.0]]))
        N = np.array([[0.0, 0.0, 1.0]])
        t = L.refract(I, N, 1 / 1.5)
        s1 = np.hypot(I[0, 0], I[0, 1])
        s2 = np.hypot(t[0, 0], t[0, 1])
        self.assertAlmostEqual(s1, 1.5 * s2, 12)
        self.assertAlmostEqual(np.linalg.norm(t), 1.0, 12)
        tir = L.refract(L.norm(np.array([[0.9, 0.0, -0.3]])), N, 1.5)   # glass -> air, steep: TIR
        self.assertTrue((tir == 0).all())

    def test_water_conserves_rays(self):
        side = 96
        p = L.params(amp=0.03, freq=5.0, side=side, simres=side, floorsize=4.0, time=0.7)
        D = L.deposit(p)
        self.assertEqual(D.sum(), side * side)
        self.assertGreater(D.max(), 1.0)          # focusing makes bright lines
        self.assertGreater((D == 0).mean(), 0.0)

    def test_water_gradient_analytic(self):
        p = L.params(amp=0.05, freq=4.0, time=0.3)
        x = np.linspace(-1, 1, 51)
        y = np.full_like(x, 0.2)
        h, gx, gy = L.water_h(x, y, p)
        e = 1e-6
        hx = (L.water_h(x + e, y, p)[0] - L.water_h(x - e, y, p)[0]) / (2 * e)
        hy = (L.water_h(x, y + e, p)[0] - L.water_h(x, y - e, p)[0]) / (2 * e)
        self.assertLess(np.abs(hx - gx).max(), 1e-6)
        self.assertLess(np.abs(hy - gy).max(), 1e-6)

    def test_sphere_focus_and_count(self):
        side, R, n = 256, 0.5, 1.5
        f = L.ball_focus(n, R)
        self.assertAlmostEqual(f, 0.75)
        p = L.params(refractor='sphere', ior=n, radius=R, side=side, simres=side, floordepth=f, lightsize=2.0,
                     floorsize=2.0)
        D = L.deposit(p)
        qx, qy, ok = L.hits(p)
        self.assertGreater(ok.mean(), 0.99)       # no TIR out of a sphere; only grazing rays bend upward (dropped)
        inside = (ok & (np.abs(qx) < 1.0) & (np.abs(qy) < 1.0)).sum()
        self.assertEqual(D.sum(), inside)         # edge rays bend off the 2 x 2 floor: exact count from numpy
        self.assertGreater(D.sum(), 0.99 * side * side)
        j, i = np.unravel_index(np.argmax(D), D.shape)
        self.assertLessEqual(abs(i - side / 2 + 0.5), 1.5)
        self.assertLessEqual(abs(j - side / 2 + 0.5), 1.5)
        self.assertGreater(D.max(), 20.0)
        p2 = dict(p, direct=0.0)
        qx, qy, ok = L.hits(p2)
        self.assertLessEqual(ok.sum(), (np.hypot(*L.ray_origins(p2)) < R).sum())   # only rays through the ball
        self.assertEqual(L.deposit(p2).sum(), (ok & (np.abs(qx) < 1.0) & (np.abs(qy) < 1.0)).sum())

    def test_paraxial_focus_converges(self):
        R, n = 0.5, 1.5
        p = L.params(refractor='sphere', ior=n, radius=R, side=64, lightsize=0.02, floordepth=L.ball_focus(n, R))
        qx, qy, ok = L.hits(p)
        self.assertTrue(ok.all())
        self.assertLess(np.hypot(qx, qy).max(), 1e-4)

    def test_slab_flat_is_identity(self):
        img = np.ones((40, 30, 4)) * 0.5
        side = 32
        D = L.deposit(L.params(refractor='slab', thickness=0.3, side=side, simres=side), img)
        self.assertTrue((D == 1.0).all())
        y, x = np.mgrid[0:40, 0:30]
        img2 = np.stack([np.exp(-((x - 15) ** 2 + (y - 20) ** 2) / 40.0)] * 3 + [np.ones((40, 30))], -1)
        D2 = L.deposit(L.params(refractor='slab', thickness=0.3, side=64, simres=64, floorsize=3.0), img2)
        self.assertEqual(D2.sum(), 64 * 64)

    def test_tone(self):
        self.assertTrue(np.allclose(L.tone(np.zeros(3), 1.0), 0.0))
        self.assertAlmostEqual(float(L.tone(np.array([1.0]), 1.0)[0]), 1 - np.exp(-1))
        self.assertAlmostEqual(float(L.tone(np.array([1.0]), 1.0, 200, 0.5)[0]), 1 - np.exp(-2.0), 9)


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_caustics.py')
        o = c.ops
        for n in ('in1', 'clock_rate', 'clock', 'rays', 'mat', 'mat_vertex', 'mat_pixel', 'geo', 'cam', 'deposit',
                  'look', 'look_compute', 'out2', 'out_sel', 'out1'):
            self.assertIn(n, o)
        self.assertEqual(o['rays'].par.surftype.val, 'points')
        self.assertEqual(o['geo'].op('sel').par.pop.val, '../rays')
        m = o['mat']
        self.assertEqual((m.par.srcblend.val, m.par.destblend.val), ('one', 'one'))
        self.assertFalse(m.par.depthtest.val)
        self.assertEqual(K.uniform_names(m), [u for u, _ in ns['MAT_UNIFORMS']])
        self.assertEqual((o['deposit'].par.format.val, o['deposit'].par.antialias.val), ('rgba32float', 'aa1'))
        self.assertEqual([K.src(o['look'], k) for k in range(2)], ['acc_sel', 'in1'])
        self.assertEqual([K.src(o['acc_sel'], k) for k in range(2)], ['deposit', 'acc'])
        self.assertEqual([K.src(o['acc'], k) for k in range(2)], ['deposit', 'acc_fb'])
        lk = o['look']
        self.assertEqual((lk.par.mode.val, lk.par.numcolorbufs.val, lk.par.outputaccess.val, lk.par.clearoutputs.val),
                         ('compute', 1, 'writeonly', True))
        self.assertEqual(K.src(o['acc_fb'], 0), 'acc_blank')
        self.assertIn("'acc' if parent().par.Persist.eval() > 0", o['acc_fb'].par.top.expr)
        self.assertEqual(o['acc'].par.format.val, 'rgba32float')
        for k in ('LOOK', 'ACC'):
            self.assertNotIn('TDImageLoadOutput', ns[k])
        self.assertEqual(K.uniform_names(lk), [u for u, _ in ns['LOOK_UNIFORMS']])
        self.assertEqual([K.src(o['out_sel'], 0), K.src(o['out_sel'], 1)], ['in1', 'look'])
        self.assertEqual(K.src(o['out2'], 0), 'deposit')
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        self.assertEqual(c.par.Rays.max, 1024)
        self.assertEqual(c.par.Rays.val, 256)

    def test_first(self):
        c, reply, ns = K.fake_build('pop_caustics.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_caustics.py')
        for u, _ in ns['MAT_UNIFORMS']:
            self.assertIn(u, K.declared(ns['VERTEX']))
        for u, _ in ns['LOOK_UNIFORMS']:
            self.assertIn(u, K.declared(ns['LOOK']))
        self.assertIn('TDPos()', ns['VERTEX'])
        self.assertNotIn('#version', ns['VERTEX'] + ns['PIXEL'] + ns['LOOK'])
        self.assertEqual(ns['REFRACTORS'], L.REFRACTORS)

    def test_ascii(self):
        for f in ('pop_caustics.py', 'pop_caustics_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_caustics.py')
        for fn, key in ((K.glslc_vert, 'VERTEX'), (K.glslc_pixel, 'PIXEL'), (K.glslc_compute, 'LOOK'), (K.glslc_compute, 'ACC')):
            ok, err = fn(ns[key])
            self.assertTrue(ok, key + '\n' + err)
            self.assertEqual(K.bounded_loops(ns[key]), [])


if __name__ == '__main__':
    unittest.main()
