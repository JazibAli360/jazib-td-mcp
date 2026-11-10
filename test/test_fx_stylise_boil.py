"""Offline tests for FX_stylise module 'boil' (builders/fx_stylise_boil.py, fx_stylise_boil_logic.py). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_stylise_boil.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_stylise_boil_logic as L  # noqa: E402
import fx_stylise_lib as X  # noqa: E402
import fx_stylise_outline_logic as OL  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('boil')


class Contract(unittest.TestCase):
    def test_module(self):
        pars = T.check_module(self, NS, 'boil')
        self.assertEqual(pars['Fill'][2]['names'], NS['FILLS'])


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Lib(unittest.TestCase):
    def test_hash_range_and_determinism(self):
        h = X.hsh(np.arange(-50, 50), np.arange(100), 3)
        self.assertTrue(np.all((h >= 0) & (h < 1)))
        self.assertTrue(np.array_equal(h, X.hsh(np.arange(-50, 50), np.arange(100), 3)))
        self.assertGreater(float(np.abs(h - X.hsh(np.arange(-50, 50), np.arange(100), 4)).mean()), 0.1)

    def test_vnoise_continuous(self):
        x = np.linspace(0, 5, 2001)
        v = X.vnoise(x, 0.3 + 0 * x, 9)
        self.assertLess(float(np.abs(np.diff(v)).max()), 0.01)

    def test_bilinear_centres(self):
        im = np.random.default_rng(1).random((8, 9, 4)).astype(np.float32)
        px, py = X.grid(8, 9)
        self.assertLess(float(np.abs(X.bilinear(im, px + 0.5, py + 0.5) - im).max()), 1e-6)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.im = OL.disc_matte(96, 80, 44.2, 39.1, 22.0)
        self.P = T.pars_of(NS)

    def test_amount_zero(self):
        out = L.look(self.im, self.im, dict(self.P, Amount=0.0), 5)
        self.assertEqual(float(np.abs(out - self.im).max()), 0.0)

    def test_lines_only_at_the_edge(self):
        P = dict(self.P, Fill=1, Boil=0.0, Paper=0.0, Inkamount=1.0)
        out = L.look(self.im, self.im, P, 1)
        px, py = X.grid(80, 96)
        r = np.hypot(px + 0.5 - 44.2, py + 0.5 - 39.1)
        dark = X.luma(out) < 0.5
        self.assertTrue(np.all(np.abs(r[dark] - 22.0) < 3.5))
        self.assertGreater(int(dark.sum()), 80)                  # a closed ring of ink

    def test_boil_moves_lines_per_seed(self):
        P = dict(self.P, Fill=1, Paper=0.0, Boil=4.0)
        a = L.look(self.im, self.im, P, 1000)
        b = L.look(self.im, self.im, P, 1001)
        self.assertGreater(float(np.abs(a - b).max()), 0.3)
        c = L.look(self.im, self.im, P, 1000)
        self.assertEqual(float(np.abs(a - c).max()), 0.0)        # same drawing for the same seed

    def test_posterise_levels(self):
        ramp = np.ones((4, 256, 4), np.float32)
        ramp[..., :3] = (np.arange(256) / 255.0)[None, :, None]
        P = dict(self.P, Fill=0, Levels=5, Boil=0.0, Paper=0.0, Inkamount=0.0)
        out = L.look(ramp, ramp, P, 1)
        self.assertEqual(len(np.unique(np.round(out[..., 0], 5))), 5)

    def test_hold_clock(self):
        times = [k / 60.0 for k in range(120)]
        self.assertEqual(L.hold_ticks(times, 12.0), 24)          # 2 s at 12 fps
        self.assertEqual(L.hold_ticks(times, 8.0), 16)
        self.assertEqual(L.boil_seed(0.0, dict(self.P, Seed=2)), 2000)
        seeds = set(L.boil_seed(k / 60.0, dict(self.P, Boilframes=3)) for k in range(120))
        self.assertEqual(len(seeds), 3)


if __name__ == '__main__':
    unittest.main()
