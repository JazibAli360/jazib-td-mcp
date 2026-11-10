"""Offline tests for FX_glass module 'foil' (builders/fx_glass_foil.py + _logic). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_glass_foil.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_glass_foil_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('foil', 'fx_glass')


class Contract(unittest.TestCase):
    def test_module(self):
        T.check_module(self, NS, 'foil', 'fx_glass')


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        self.ramp = np.ones((16, 256, 4), np.float32)
        self.ramp[..., :3] = (np.arange(256) / 255.0)[None, :, None]

    def test_amount_zero(self):
        out = L.look(self.ramp, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.ramp).max()), 0.0)

    def test_thinfilm_physics(self):
        # zero thickness: all channels in phase (white); a half-wave of 532 nm in the film -> green dark
        self.assertTrue(np.allclose(L.thinfilm(0.0, 1.0, 1.4, 0.0), 1.0))
        d = 532.0 / (4 * 1.4)
        self.assertAlmostEqual(float(L.thinfilm(d, 1.0, 1.4, 0.0)[1]), 0.0, places=9)

    def test_colour_varies_with_luma(self):
        P = dict(self.P, Blend=0, Noise=0.0, Tilt=0.0, Keepluma=0.0, Saturation=1.0)
        out = L.look(self.ramp, P)
        hue_spread = float(np.std(out[8, :, 0] - out[8, :, 2]))
        self.assertGreater(hue_spread, 0.2)                                       # rainbow bands along the ramp


if __name__ == '__main__':
    unittest.main()
