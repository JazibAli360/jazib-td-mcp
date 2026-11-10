"""Offline tests for FX_glass module 'rain' (builders/fx_glass_rain.py + _logic). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_glass_rain.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_glass_rain_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('rain', 'fx_glass')


class Contract(unittest.TestCase):
    def test_module(self):
        T.check_module(self, NS, 'rain', 'fx_glass')


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        y, x = np.mgrid[0:160, 0:120]
        self.img = np.ones((160, 120, 4), np.float32)
        self.img[..., 0], self.img[..., 1] = x / 120.0, y / 160.0

    def test_amount_zero(self):
        out = L.look(self.img, self.img, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.img).max()), 0.0)

    def test_drops_and_density(self):
        P = dict(self.P, Size=40.0, Layers=1, Static=0.0, Trails=0.0)
        _o, clear0, _r = L.field(120, 160, dict(P, Rain=0.0))
        _o, clear1, _r = L.field(120, 160, dict(P, Rain=1.0))
        self.assertEqual(float(clear0.max()), 0.0)
        self.assertGreater(float((clear1 > 0.5).mean()), 0.03)

    def test_drops_slide_down(self):
        P = dict(self.P, Size=40.0, Layers=1, Static=0.0, Trails=0.0, Rain=1.0)
        _o, a, _r = L.field(120, 160, P, 0.0)
        _o, b, _r = L.field(120, 160, P, 0.004)
        ya = (np.arange(160)[:, None] * (a > 0.5)).sum() / max((a > 0.5).sum(), 1)
        yb = (np.arange(160)[:, None] * (b > 0.5)).sum() / max((b > 0.5).sum(), 1)
        self.assertLess(yb, ya)                                                 # mean drop row went down (y up)

    def test_lens_flips(self):
        P = dict(self.P, Size=60.0, Layers=1, Static=0.0, Trails=0.0, Rain=1.0, Fog=0.0, Rimdark=0.0, Tintamt=0.0,
                 Refract=1.0)
        off, clear, _r = L.field(120, 160, P)
        m = clear > 0.99
        self.assertTrue(np.any(m))
        out = L.look(self.img, self.img, P)
        self.assertGreater(float(np.abs(out[m] - self.img[m]).max()), 0.05)     # inside drops the picture moves
        self.assertLess(float(np.abs(out[clear == 0] - self.img[clear == 0]).max()), 1e-6)


if __name__ == '__main__':
    unittest.main()
