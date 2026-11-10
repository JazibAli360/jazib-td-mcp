"""Offline tests for FX_glass module 'floor' (builders/fx_glass_floor.py + _logic). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_glass_floor.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_glass_floor_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('floor', 'fx_glass')


class Contract(unittest.TestCase):
    def test_module(self):
        T.check_module(self, NS, 'floor', 'fx_glass')


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        y, x = np.mgrid[0:100, 0:60]
        self.img = np.ones((100, 60, 4), np.float32)
        self.img[..., 0] = y / 100.0                                              # vertical ramp

    def test_amount_zero(self):
        out = L.look(self.img, self.img, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.img).max()), 0.0)

    def test_overlay_keeps_top_and_mirrors(self):
        P = dict(self.P, Layout=1, Horizon=0.3, Ripple=0.0, Blurdist=1.0, Reflect=1.0, Fade=1.0, Fadepow=1.0,
                 Fresnel=0.0, Stretch=1.0, Floorr=0.0, Floorg=0.0, Floorb=0.0, Tiles=0.0)
        out = L.look(self.img, self.img, P)
        self.assertEqual(float(np.abs(out[40:] - self.img[40:]).max()), 0.0)     # above the line untouched
        # just below the line the reflection ~ the picture just above it (dimmed by the fade)
        self.assertAlmostEqual(float(out[29, 30, 0] / (1 - (0.3 - 0.295) / 1.0)), float(self.img[30, 30, 0]), delta=0.02)

    def test_fit_squeezes_picture_above(self):
        P = dict(self.P, Layout=0, Horizon=0.5, Ripple=0.0)
        out = L.look(self.img, self.img, P)
        self.assertAlmostEqual(float(out[99, 30, 0]), float(self.img[99, 30, 0]), delta=0.02)   # top row stays top
        self.assertAlmostEqual(float(out[50, 30, 0]), float(self.img[0, 30, 0]), delta=0.02)    # bottom row at the line


if __name__ == '__main__':
    unittest.main()
