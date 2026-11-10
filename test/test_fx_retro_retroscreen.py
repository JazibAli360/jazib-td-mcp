"""Offline tests for FX_retro module 'retroscreen' (builders/fx_retro_retroscreen.py) + mirror (rack wiring / glslc:
test_fx_retro.py). Run: python3 -I -m unittest discover -s test -p 'test_fx_retro_retroscreen.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import fx_retro_retroscreen_logic as L  # noqa: E402
import test_fx_retro as T  # noqa: E402

M = T.module('retroscreen')
W, H = 108, 192


def pic(seed=0):
    a = np.random.default_rng(seed).random((H, W, 4))
    a[..., 3] = 1
    return a


class Spec(unittest.TestCase):
    def test_defaults_presets_uniforms(self):
        pars = dict((n, (s, d, o)) for _pg, pl in M['PAGES'] for n, s, d, o in pl)
        for k, v in L.DEFAULTS.items():
            s, d, o = pars[k]
            self.assertAlmostEqual(float(o['names'].index(d) if s == 'Menu' else d), float(v), msg=k)
        for _s, n, vals in M['PRESETS']:
            self.assertEqual(set(vals), set(pars), n)
        for un, _e in M['uniforms'](T.RACK['H']):
            self.assertIn('uniform vec4 %s;' % un, M['FX'])


class Mirror(unittest.TestCase):
    def test_amount_zero(self):
        img = pic()
        self.assertTrue(np.array_equal(L.reference(img, {'Amount': 0.0}), img))

    def test_border_and_43_screen(self):
        out = L.reference(pic(1), {})
        self.assertTrue(np.allclose(out[0, 0, :3], [0.42, 0.35, 0.8]))
        inside = ~np.all(np.isclose(out[..., :3], [0.42, 0.35, 0.8]), -1)
        ys, xs = np.where(inside)
        w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        self.assertAlmostEqual(w / h, 4 / 3, delta=0.05)

    def test_full_frame_pixels(self):
        out = L.reference(pic(2), {'Aspect': 0, 'Margin': 0.0, 'Pixelsize': 4.0})
        for j in range(0, 40, 4):
            for i in range(0, 40, 4):
                self.assertLess(np.ptp(out[j:j + 4, i:i + 4, :3].reshape(-1, 3), axis=0).max(), 1e-12)

    def test_bars_only_in_border(self):
        img = pic(3)
        a = L.reference(img, {'Bars': 6, 'Barheight': 60.0}, t=0.3)
        b = L.reference(img, {'Bars': 0}, t=0.3)
        d = np.abs(a - b)[..., :3].max(-1) > 1e-9
        self.assertTrue(d.any())
        border = np.all(np.isclose(b[..., :3], [0.42, 0.35, 0.8]), -1)
        self.assertFalse((d & ~border).any())

    def test_flicker_and_fade(self):
        img = pic(4)
        f0 = L.reference(img, {'Flicker': 1.0, 'Aspect': 0, 'Margin': 0.0, 'Pixelsize': 1.0}, parity=0)
        self.assertTrue(np.all(f0[1::2, :, :3] == 0) or np.all(f0[0::2, :, :3] == 0))
        w = L.reference(img, {'Fade': 1.0})
        self.assertTrue(np.allclose(w[..., :3], 1.0))

    def test_shake_moves_screen(self):
        img = pic(5)
        a = L.reference(img, {'Shake': 10.0}, epoch=1)
        b = L.reference(img, {'Shake': 10.0}, epoch=2)
        self.assertGreater(np.abs(a - b).mean(), 0.01)


if __name__ == '__main__':
    unittest.main()
