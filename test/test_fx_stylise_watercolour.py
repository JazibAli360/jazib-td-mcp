"""Offline tests for FX_stylise module 'watercolour' (builders/fx_stylise_watercolour.py + _logic). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_stylise_watercolour.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_stylise_watercolour_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('watercolour')


class Contract(unittest.TestCase):
    def test_module(self):
        T.check_module(self, NS, 'watercolour')
        self.assertEqual(NS['TAPS'], L.TAPS)


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        self.img = np.ones((64, 96, 4), np.float32)
        self.img[..., 0], self.img[..., 1], self.img[..., 2] = 0.8, 0.2, 0.2
        self.img[:, 48:, :3] = (0.1, 0.3, 0.8)

    def test_amount_zero(self):
        wa = L.wash(self.img, self.P)
        out = L.look(self.img, wa, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.img).max()), 0.0)

    def test_bleed_mixes_across_the_edge(self):
        P = dict(self.P, Wobble=0.0, Spread=10.0)
        wa = L.wash(self.img, P)                            # half res: x = 24 is the edge (48 / 2)
        self.assertGreater(float(wa[16, 23, 2]), 0.25)       # blue bled into the red side
        self.assertAlmostEqual(float(wa[16, 5, 2]), 0.2, places=5)
        Pf = dict(P, Flow=1)
        wf = L.wash(self.img, Pf)                            # flow along the edge: no bleed across
        self.assertLess(float(abs(wf[16, 23, 2] - 0.2)), 0.05)

    def test_whites_go_to_paper(self):
        white = np.ones((32, 32, 4), np.float32)
        P = dict(self.P, Pigment=0.0, Granulation=0.0)
        out = L.look(white, L.wash(white, P), P)
        self.assertLess(float(np.abs(out[..., :3] - np.array([P['Paperr'], P['Paperg'], P['Paperb']])).max()), 1e-6)


if __name__ == '__main__':
    unittest.main()
