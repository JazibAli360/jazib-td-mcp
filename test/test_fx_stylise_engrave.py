"""Offline tests for FX_stylise module 'engrave' (builders/fx_stylise_engrave.py + _logic). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_stylise_engrave.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_stylise_engrave_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('engrave')


class Contract(unittest.TestCase):
    def test_module(self):
        T.check_module(self, NS, 'engrave')


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        self.ramp = np.ones((64, 256, 4), np.float32)
        self.ramp[..., :3] = (np.arange(256) / 255.0)[None, :, None]

    def test_amount_zero(self):
        out = L.look(self.ramp, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.ramp).max()), 0.0)

    def test_ink_follows_darkness(self):
        P = dict(self.P, Cross=0.0, Bend=0.0, Angle=0.0)
        out = L.look(self.ramp, P)
        ink = 1 - (out[..., 0] - P['Inkr']) / (P['Paperr'] - P['Inkr'])
        dark, light = ink[:, 20:60].mean(), ink[:, 200:240].mean()
        self.assertGreater(dark, light + 0.3)
        self.assertLess(float(ink[:, 250:].mean()), 0.05)                       # white = paper

    def test_lines_are_parallel_at_angle_0(self):
        flat = np.full((64, 64, 4), 0.5, np.float32)
        flat[..., 3] = 1
        P = dict(self.P, Cross=0.0, Bend=0.0, Angle=0.0, Wave=0.0)
        out = L.look(flat, P)
        self.assertLess(float(np.abs(out - out[:, :1]).max()), 1e-9)            # constant along x (horizontal lines)
        self.assertGreater(float(out[:, 0, 0].std()), 0.1)


if __name__ == '__main__':
    unittest.main()
