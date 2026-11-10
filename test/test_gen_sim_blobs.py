"""Offline tests for GEN_sim module 'blobs' (builders/gen_sim_blobs.py, glsl/gen_sim_blobs.glsl, gen_sim_logic blob_*).
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sim_blobs.py'"""
import math
import re
import unittest

import numpy as np

import test_gen_sim as K

M = K.module('blobs')
L = K.LOGIC


class Uniforms(unittest.TestCase):
    def test_match_shader(self):
        T = M['shader_texts']()['fx']
        K.check_uniforms(self, T, M['uniforms'](), 'blobs.fx')
        for _u, ex in M['uniforms']():
            for e in ex:
                float(K.ev(e, M))

    def test_shared_memory_fits(self):                     # Metal threadgroup memory 32 KB
        T = M['shader_texts']()['fx']
        maxb = int(re.search(r'#define MAXB (\d+)', T).group(1))
        self.assertEqual(maxb, L['MAXB'])
        nbytes = maxb * 16 + maxb * 4 + 2 * 256 * 4 + 4
        self.assertLess(nbytes, 32768)
        self.assertEqual(int(re.search(r'#define PER (\d+)', T).group(1)) * 256, maxb)


class Field(unittest.TestCase):
    def test_lone_metaball_surface_is_radius(self):
        for T in (0.2, 0.5, 0.8):
            P = {'Field': 0, 'Threshold': T}
            r = 50.0
            S = r / math.sqrt(1 - T ** (1 / 3.0))
            a = np.linspace(0, 2 * math.pi, 16)
            sd, cov = L['blob_field'](100 + r * np.cos(a), 100 + r * np.sin(a), [(100, 100, r, S)], P)
            self.assertLess(np.abs(sd).max(), 1e-9)
            sd_in, _ = L['blob_field']([100 + 0.8 * r], [100], [(100, 100, r, S)], P)
            sd_out, _ = L['blob_field']([100 + 1.2 * r], [100], [(100, 100, r, S)], P)
            self.assertLess(sd_in[0], 0)
            self.assertGreater(sd_out[0], 0)
            self.assertAlmostEqual(sd_out[0], 0.2 * r, delta=0.1 * r)          # ~ px outside near the rim

    def test_compact_support(self):
        P = {'Field': 0, 'Threshold': 0.5}
        sd, cov = L['blob_field']([500.0], [500.0], [(0, 0, 50, 110)], P)
        self.assertEqual(cov[0], 0.0)

    def test_metaballs_merge(self):
        P = {'Field': 0, 'Threshold': 0.5}
        r = 40.0
        S = r / math.sqrt(1 - 0.5 ** (1 / 3.0))
        blobs = [(100 - 45, 100, r, S), (100 + 45, 100, r, S)]                 # 10 px gap between the circles
        sd, _ = L['blob_field']([100.0], [100.0], blobs, P)
        self.assertLess(sd[0], 0)                                              # the gap is bridged

    def test_sdf_smooth_min(self):
        P = {'Field': 1, 'Softness': 1e-6}
        blobs = [(0, 0, 10, 10), (30, 0, 10, 10)]
        sd, _ = L['blob_field']([15.0], [0.0], blobs, P)
        self.assertAlmostEqual(sd[0], 5.0, delta=1e-3)                         # k -> 0 (floor 1e-3): plain min
        P2 = {'Field': 1, 'Softness': 20.0}
        sd2, _ = L['blob_field']([15.0], [0.0], blobs, P2)
        self.assertLess(sd2[0], 5.0)                                           # smooth union bulges out
        self.assertAlmostEqual(sd2[0], 5.0 - 20 * 0.25, places=6)              # h = 1: min - k / 4


class Params(unittest.TestCase):
    def test_motion_and_radius(self):
        for motion in range(4):
            b, hue = L['blob_params'](40, 1080, 1920, 3.7, {'Motion': motion, 'Radius': 90, 'Rvar': 0.4})
            self.assertEqual(b.shape, (40, 4))
            self.assertTrue((b[:, 0] > -200).all() and (b[:, 0] < 1280).all(), motion)
            self.assertTrue((b[:, 2] >= 90 * 0.6 - 1e-9).all() and (b[:, 2] <= 90 * 1.4 + 1e-9).all())
            self.assertTrue((hue >= 0).all() and (hue < 1).all())
        b0, _ = L['blob_params'](5, 1080, 1920, 0.0, {})
        b1, _ = L['blob_params'](5, 1080, 1920, 1.0, {})
        self.assertGreater(np.abs(b0[:, :2] - b1[:, :2]).max(), 1.0)
        big, _ = L['blob_params'](5000, 100, 100, 0.0, {})
        self.assertEqual(len(big), L['MAXB'])

    def test_support_radius(self):
        b, _ = L['blob_params'](3, 500, 500, 0.0, {'Field': 0, 'Threshold': 0.5, 'Radius': 50, 'Rvar': 0})
        self.assertTrue(np.allclose(b[:, 3], 50 / math.sqrt(1 - 0.5 ** (1 / 3.0))))
        b, _ = L['blob_params'](3, 500, 500, 0.0, {'Field': 1, 'Softness': 30, 'Radius': 50, 'Rvar': 0})
        self.assertTrue(np.allclose(b[:, 3], 80))


if __name__ == '__main__':
    unittest.main()
