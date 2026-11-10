"""Offline tests for GEN_sim module 'lic' (builders/gen_sim_lic.py, glsl/gen_sim_lic*.glsl, gen_sim_logic lic*).
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sim_lic.py'"""
import unittest

import numpy as np

import test_gen_sim as K

M = K.module('lic')
L = K.LOGIC


class Uniforms(unittest.TestCase):
    def test_match_shaders(self):
        T, U = M['shader_texts'](), M['uniforms']()
        K.check_uniforms(self, T['field'], U['field'], 'lic.field')
        K.check_uniforms(self, T['fx'], U['lic'], 'lic.fx')
        for k in U:
            for _u, ex in U[k]:
                for e in ex:
                    float(K.ev(e, M))
        self.assertEqual((K.ev(M['FW'], M), K.ev(M['FH'], M)), (270, 480))


class FieldRef(unittest.TestCase):
    def test_curl_unit_and_divergence_free(self):
        f = L['lic_curl_field'](90, 160, 360, 640, 120.0, octaves=2, seed=3)
        m = f[..., 2] > 1e-6
        self.assertTrue(np.allclose(np.hypot(f[..., 0], f[..., 1])[m], 1.0))
        vx, vy = f[..., 0] * f[..., 2], f[..., 1] * f[..., 2]
        div = np.gradient(vx, axis=1) + np.gradient(vy, axis=0)
        curl = np.gradient(vy, axis=1) - np.gradient(vx, axis=0)
        self.assertLess(np.abs(div).mean(), 0.3 * np.abs(curl).mean())          # discrete: not exactly 0

    def test_snap_and_rotate(self):
        f = L['lic_curl_field'](40, 40, 400, 400, 100.0, snap=4)
        ang = np.degrees(np.arctan2(f[..., 1], f[..., 0]))[f[..., 2] > 1e-6]
        self.assertLess(np.abs(((ang + 45) % 90) - 45).max(), 1e-6)            # 0 / 90 / 180 / 270 only
        a = L['lic_curl_field'](20, 20, 200, 200, 100.0)
        b = L['lic_curl_field'](20, 20, 200, 200, 100.0, rotate=np.pi / 2)
        self.assertTrue(np.allclose(b[..., 0], -a[..., 1]) and np.allclose(b[..., 1], a[..., 0]))


class Lic(unittest.TestCase):
    P = {'Taps': 16, 'Step': 1.0, 'Grain': 1.5, 'Contrast': 3.0, 'Flow': 0.5, 'Ripples': 2.0, 'Seed': 1}

    def flat_field(self, W, H):
        f = np.zeros((H // 4, W // 4, 4))
        f[..., 0], f[..., 2], f[..., 3] = 1.0, 1.0, 1.0                       # all along +x
        return f

    def test_streaks_follow_the_field(self):
        W, H = 200, 120
        f = self.flat_field(W, H)
        ys, xs = np.mgrid[20:100, 40:160]
        v = L['lic'](f, W, H, xs.ravel(), ys.ravel(), self.P).reshape(xs.shape)
        along = np.corrcoef(v[:, :-1].ravel(), v[:, 1:].ravel())[0, 1]
        across = np.corrcoef(v[:-2, :].ravel(), v[2:, :].ravel())[0, 1]        # 2 px apart: past the grain
        self.assertGreater(along, 0.8)
        self.assertLess(abs(across), 0.2)

    def test_phase_is_periodic_and_moves(self):
        W, H = 120, 80
        f = self.flat_field(W, H)
        xs, ys = np.arange(30, 90), np.full(60, 40)
        a = L['lic'](f, W, H, xs, ys, self.P, phase=0.3)
        self.assertTrue(np.allclose(a, L['lic'](f, W, H, xs, ys, self.P, phase=1.3)))
        self.assertFalse(np.allclose(a, L['lic'](f, W, H, xs, ys, self.P, phase=0.55)))

    def test_hardware_filter_error_is_small(self):         # expected live parity numbers (LIVE CHECK L3)
        W, H = 270, 480
        f = L['lic_curl_field'](W // 4, H // 4, W, H, 80.0, octaves=3, seed=2)
        rng = np.random.default_rng(1)
        xs, ys = rng.integers(0, W, 1500), rng.integers(0, H, 1500)
        e = np.abs(L['lic'](f, W, H, xs, ys, self.P) - L['lic'](f, W, H, xs, ys, self.P, quant=8))
        self.assertLess(np.median(e), 0.02)
        self.assertLess(np.percentile(e, 99), 0.25)

    def test_half_float_field_error_below_filter(self):     # field is rgba16float (perf pass, 26 Oct)
        W, H = 270, 480
        f = L['lic_curl_field'](W // 4, H // 4, W, H, 80.0, octaves=3, seed=2).astype(np.float32)
        rng = np.random.default_rng(1)
        xs, ys = rng.integers(0, W, 1500), rng.integers(0, H, 1500)
        a = L['lic'](f, W, H, xs, ys, self.P, quant=8)
        half = np.abs(a - L['lic'](f.astype(np.float16).astype(np.float32), W, H, xs, ys, self.P, quant=8))
        filt = np.abs(a - L['lic'](f, W, H, xs, ys, self.P))
        self.assertEqual(float(np.median(half)), 0.0)
        self.assertLessEqual(np.percentile(half, 99), np.percentile(filt, 99))


if __name__ == '__main__':
    unittest.main()
