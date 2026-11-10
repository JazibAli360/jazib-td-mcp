"""Offline tests for FX_stylise module 'kuwahara' (builders/fx_stylise_kuwahara.py + _logic). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_stylise_kuwahara.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_stylise_kuwahara_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('kuwahara')


class Contract(unittest.TestCase):
    def test_module(self):
        T.check_module(self, NS, 'kuwahara')
        self.assertIn('yi <= 2 * 24', NS['KUW'])                                # constant bound, runtime break


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        rng = np.random.default_rng(4)
        self.img = np.ones((48, 64, 4), np.float32)
        self.img[..., :3] = 0.25
        self.img[:, 32:, :3] = 0.75
        self.noisy = self.img.copy()
        self.noisy[..., :3] += rng.normal(0, 0.05, (48, 64, 3)).astype(np.float32)

    def test_amount_zero(self):
        out, _k, _t = L.module(self.noisy, dict(self.P, Amount=0.0, Res=0, Radius=3))
        self.assertEqual(float(np.abs(out - self.noisy).max()), 0.0)

    def test_flattens_noise_keeps_edge(self):
        P = dict(self.P, Res=0, Radius=4)
        out, _k, _t = L.module(self.noisy, P)
        inner = out[8:40, 6:24, 0]
        self.assertLess(float(inner.std()), 0.5 * float(self.noisy[8:40, 6:24, 0].std()))
        self.assertGreater(float(out[:, 36, 0].mean() - out[:, 28, 0].mean()), 0.4)   # edge kept

    def test_tensor_orientation(self):
        t = L.tblur(L.tensor(self.img, 1))
        E, F, G = t[24, 32, 0], t[24, 32, 1], t[24, 32, 2]
        self.assertGreater(E, 10 * max(G, 1e-9))                                # vertical edge: x gradient only
        self.assertLess(abs(F), 1e-9)


if __name__ == '__main__':
    unittest.main()
