"""Offline tests for FX_glass module 'frost' (builders/fx_glass_frost.py + _logic). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_glass_frost.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_glass_frost_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('frost', 'fx_glass')


class Contract(unittest.TestCase):
    def test_module(self):
        T.check_module(self, NS, 'frost', 'fx_glass')


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        y, x = np.mgrid[0:96, 0:128]
        self.img = np.ones((96, 128, 4), np.float32)
        self.img[..., 0], self.img[..., 1] = x / 128.0, y / 96.0

    def test_amount_zero(self):
        out = L.look(self.img, self.img, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.img).max()), 0.0)

    def test_frost_scatter_bounded(self):
        P = dict(self.P, Mode=0, Radius=4.0, Blurmix=0.0)
        out = L.look(self.img, self.img, P)
        dx = np.abs(out[8:-8, 8:-8, 0] - self.img[8:-8, 8:-8, 0]) * 128
        self.assertLessEqual(float(dx.max()), 4.0 + 1e-6)                        # scatter within Radius px
        self.assertGreater(float(dx.mean()), 0.5)

    def test_reeded_mag_one_is_clear(self):
        P = dict(self.P, Mode=1, Mag=1.0, Blurmix=0.0, Rimlight=0.0)
        out = L.look(self.img, self.img, P)
        self.assertLess(float(np.abs(out[4:-4, 4:-4] - self.img[4:-4, 4:-4]).max()), 1e-5)

    def test_flyeye_flips_inside_cells(self):
        P = dict(self.P, Mode=2, Shape=0, Cell=32.0, Mag=-1.0, Gap=0.0, Vignette=0.0, Rimlight=0.0, Blurmix=0.0)
        out = L.look(self.img, self.img, P)
        cell = out[32:64, 32:64, 0]                                              # one square cell
        self.assertGreater(float(cell[:, 1].mean()), float(cell[:, -2].mean()))  # x ramp reversed in the cell


if __name__ == '__main__':
    unittest.main()
