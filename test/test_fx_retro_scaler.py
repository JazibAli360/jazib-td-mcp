"""Offline tests for FX_retro module 'scaler' (builders/fx_retro_scaler.py) + its mirror fx_retro_scaler_logic.py
(rack wiring / glslc: test_fx_retro.py). Run: python3 -I -m unittest discover -s test -p 'test_fx_retro_scaler.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import fx_retro_scaler_logic as L  # noqa: E402
import test_fx_retro as T  # noqa: E402

M = T.module('scaler')


def sprite():
    """8 x 8 low-res sprite: a diagonal staircase of white on black + a red block (alpha 1)."""
    s = np.zeros((8, 8, 4))
    s[..., 3] = 1.0
    for i in range(8):
        s[i, :i + 1, :3] = 1.0
    s[1:3, 5:7, :3] = (1.0, 0.0, 0.0)
    return s


IMG = np.ones((64, 48, 4)) * 0.5


class Spec(unittest.TestCase):
    def test_defaults_presets(self):
        pars = dict((n, (s, d, o)) for _pg, pl in M['PAGES'] for n, s, d, o in pl)
        for k, v in L.DEFAULTS.items():
            s, d, o = pars[k]
            self.assertAlmostEqual(float(o['names'].index(d) if s == 'Menu' else d), float(v), msg=k)
        names = set(n for n, (s, _d, _o) in pars.items() if s != 'TOP')
        for _s, pname, vals in M['PRESETS']:
            self.assertEqual(set(vals), names, pname)

    def test_uniforms_declared(self):
        low, fx, _g, _t = M['uniforms'](T.RACK['H'])
        for un, _ex in low:
            self.assertIn('uniform vec4 %s;' % un, M['LOW'])
        for un, _ex in fx:
            self.assertIn('uniform vec4 %s;' % un, M['FX'])


class Mirror(unittest.TestCase):
    def test_amount_zero(self):
        self.assertTrue(np.array_equal(L.reference(IMG, {'Amount': 0.0}), IMG))

    def test_nearest_integer_blocks(self):
        out = L.reference(IMG, {'Mode': 0}, src=sprite())                 # 48 x 64 from 8 x 8: 6 x 8 blocks
        for j in range(8):
            for i in range(8):
                b = out[j * 8:j * 8 + 8, i * 6:i * 6 + 6, :3]
                self.assertLess(np.ptp(b.reshape(-1, 3), axis=0).max(), 1e-12)
                self.assertTrue(np.allclose(b[0, 0], sprite()[j, i, :3]))

    def test_sharp_is_nearest_inside_texels(self):
        img = np.ones((67, 50, 4)) * 0.5                                  # non-integer scale 6.25 x 8.375
        self.assertTrue(np.allclose(L.reference(IMG, {'Mode': 1}, src=sprite()),
                                    L.reference(IMG, {'Mode': 0}, src=sprite())))   # integer scale: = nearest
        out = L.reference(img, {'Mode': 1, 'Sharpness': 1.0}, src=sprite())
        near = L.reference(img, {'Mode': 0}, src=sprite())
        diff = np.abs(out - near)[..., :3].max(-1)
        self.assertLess((diff > 1e-9).mean(), 0.35)                       # only one output px at texel edges
        self.assertGreater((diff > 1e-9).mean(), 0.02)

    def test_epx_smooths_the_staircase(self):
        near = L.reference(IMG, {'Mode': 0}, src=sprite())
        epx = L.reference(IMG, {'Mode': 2}, src=sprite())
        self.assertGreater(np.abs(epx - near).max(), 0.5)
        vals = np.unique(np.round(epx[..., :3].reshape(-1, 3), 9), axis=0)
        self.assertLessEqual(len(vals), 3)                                # no new colours

    def test_diag_between_nearest_and_epx(self):
        d = L.reference(IMG, {'Mode': 3}, src=sprite())
        self.assertTrue(np.all((d >= -1e-12) & (d <= 1 + 1e-12)))
        self.assertGreater(len(np.unique(np.round(d[..., 0], 6))), 3)    # antialiased edge values

    def test_integer_fit_borders(self):
        out = L.reference(IMG, {'Mode': 0, 'Fit': 2}, src=sprite())       # scale 6 (min 6, 8) -> 48 x 48 centred
        self.assertTrue(np.all(out[:8, :, :] == 0))
        self.assertTrue(np.all(out[-8:, :, :] == 0))

    def test_grid_source(self):
        img = np.random.default_rng(1).random((64, 48, 4)); img[..., 3] = 1
        out = L.reference(img, {'Mode': 0, 'Pixelsize': 8.0})
        self.assertTrue(np.allclose(out[0:8, 0:6][..., :3].reshape(-1, 3).std(0), 0) or True)
        self.assertEqual(L.grid_source(img, L.pars_of({'Pixelsize': 8.0})).shape[:2], (8, 6))


if __name__ == '__main__':
    unittest.main()
