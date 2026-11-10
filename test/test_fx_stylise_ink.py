"""Offline tests for FX_stylise module 'ink' (builders/fx_stylise_ink.py, fx_stylise_ink_logic.py). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_stylise_ink.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_stylise_ink_logic as L  # noqa: E402
import fx_stylise_outline_logic as OL  # noqa: E402
import fx_stylise_lib as X  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('ink')


class Contract(unittest.TestCase):
    def test_module(self):
        pars = T.check_module(self, NS, 'ink')
        self.assertEqual(pars['Mode'][2]['names'], L.__dict__.get('MODES', NS['MODES']))
        self.assertEqual(NS['RMAX'], L.RMAX)
        self.assertIn('for (int i = 0; i <= 48; i++)', NS['BLUR'])            # constant loop bound (T-124)

    def test_incremental_weights(self):
        import math
        for s in (0.3, 1.2, 3.0, 12.0):
            e, r, q = 1.0, math.exp(-0.5 / (s * s)), math.exp(-1 / (s * s))
            for i in range(0, 49):
                self.assertAlmostEqual(e, math.exp(-i * i / (2 * s * s)), delta=1e-9)
                e *= r
                r *= q


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.im = OL.disc_matte(96, 80, 44.2, 39.1, 22.0)
        self.im[..., :3] = 0.15 + 0.7 * self.im[..., :3]
        self.P = T.pars_of(NS)

    def test_blur_is_normalised(self):
        flat = np.full((20, 24, 4), 0.4, np.float32)
        g = L.blur2(flat, 1.5, 1.6)
        self.assertLess(float(np.abs(g - 0.4).max()), 1e-6)
        self.assertEqual(L.radius(1.2, 1.6), 6)
        self.assertEqual(L.radius(20, 4), 48)

    def test_amount_zero(self):
        g = L.blur2(self.im, 1.2, 1.6)
        out = L.look(self.im, g, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.im).max()), 0.0)

    def test_xdog_draws_the_edge_only(self):
        g = L.blur2(self.im, 1.2, 1.6)
        out = L.look(self.im, g, dict(self.P, Eps=0.1))
        px, py = X.grid(80, 96)
        r = np.hypot(px + 0.5 - 44.2, py + 0.5 - 39.1)
        dark = X.luma(out) < 0.5
        self.assertGreater(int(dark.sum()), 60)
        self.assertTrue(np.all(np.abs(r[dark] - 22.0) < 6.0))                # XDoG lines are a few px wide
        self.assertFalse(np.any(dark[r < 14]) or np.any(dark[r > 30]))

    def test_toon_band_count(self):
        ramp = np.ones((8, 256, 4), np.float32)
        ramp[..., :3] = (np.arange(256) / 255.0)[None, :, None]
        g = L.blur2(ramp, 1.2, 1.6)
        P = dict(self.P, Mode=1, Bands=4, Bandsoft=0.0, Inkamount=0.0, Saturation=1.0)
        out = L.look(ramp, g, P)
        self.assertEqual(len(np.unique(np.round(out[4, 8:-8, 0], 4))), 5)       # 0, 1/4 .. 1 levels

    def test_comic_dots_in_shadow(self):
        dark = np.full((64, 64, 4), 0.3, np.float32)
        dark[..., 3] = 1
        g = L.blur2(dark, 1.2, 1.6)
        P = dict(self.P, Mode=2, Inkamount=1.0, Dotthr=0.45, Dotsize=8.0)
        out = L.look(dark, g, P)
        share = float((X.luma(out) < 0.05).mean())
        self.assertGreater(share, 0.2)
        self.assertLess(share, 0.8)


if __name__ == '__main__':
    unittest.main()
