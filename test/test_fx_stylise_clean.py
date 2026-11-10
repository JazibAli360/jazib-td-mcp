"""Offline tests for FX_stylise module 'clean' (builders/fx_stylise_clean.py, fx_stylise_clean_logic.py). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_stylise_clean.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_stylise_clean_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('clean')


class Contract(unittest.TestCase):
    def test_module(self):
        T.check_module(self, NS, 'clean')
        self.assertIn('for (int i = 1; i <= 24; i++)', NS['BIL'])


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        rng = np.random.default_rng(5)
        self.clean_img = np.zeros((48, 64, 4))
        self.clean_img[..., :3] = 0.2
        self.clean_img[:, 32:, :3] = 0.8                                       # one hard edge
        self.clean_img[..., 3] = 1
        self.noisy = self.clean_img.copy()
        self.noisy[..., :3] += rng.normal(0, 0.03, (48, 64, 3))

    def test_network_is_a_median(self):
        v = np.random.default_rng(2).random((9, 2000))
        self.assertTrue(np.array_equal(L.median_net(list(v)), np.median(v, axis=0)))

    def test_amount_zero(self):
        out = L.clean(self.noisy, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.noisy).max()), 0.0)

    def test_denoise_keeps_the_edge(self):
        out = L.clean(self.noisy, dict(self.P, Median=0, Radius=6, Sigma=3.0, Edge=0.08))
        self.assertLess(L.noise_std(out, self.clean_img), 0.5 * L.noise_std(self.noisy, self.clean_img))
        step = out[:, 33, 0].mean() - out[:, 30, 0].mean()                    # edge still ~0.6 tall
        self.assertGreater(step, 0.55)

    def test_median_kills_speckles(self):
        sp = self.clean_img.copy()
        sp[10, 10, :3] = 1.0
        sp[20, 40, :3] = 0.0
        out = L.median3(sp)
        self.assertAlmostEqual(float(out[10, 10, 0]), 0.2)
        self.assertAlmostEqual(float(out[20, 40, 0]), 0.8)


if __name__ == '__main__':
    unittest.main()
