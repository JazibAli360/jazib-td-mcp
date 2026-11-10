"""Offline tests for FX_retro module 'pixelart' (builders/fx_retro_pixelart.py) and its numpy mirror
builders/fx_retro_pixelart_logic.py (rack wiring / glslc: test_fx_retro.py). Run:
python3 -I -m unittest discover -s test -p 'test_fx_retro_pixelart.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import fx_retro_pixelart_logic as L  # noqa: E402
import test_fx_retro as T  # noqa: E402

M = T.module('pixelart')
W, H = 60, 96


def pic():
    y, x = np.mgrid[0:H, 0:W].astype(float)
    a = np.zeros((H, W, 4))
    a[..., 0], a[..., 1], a[..., 2] = x / W, y / H, 0.3
    a[30:60, 20:40, :3] = 0.75                                   # bright block
    a[..., 3] = 1.0
    return a


class Spec(unittest.TestCase):
    def test_defaults_match(self):
        pars = dict((n, (s, d, o)) for _pg, pl in M['PAGES'] for n, s, d, o in pl)
        for k, v in L.DEFAULTS.items():
            s, d, o = pars[k]
            if s == 'Menu':
                d = o['names'].index(d)
            self.assertAlmostEqual(float(d), float(v), msg=k)

    def test_presets_full_state(self):
        names = set(n for _pg, pl in M['PAGES'] for n, _s, _d, _o in pl)
        for _s, pname, vals in M['PRESETS']:
            self.assertEqual(set(vals), names, pname)

    def test_uniforms_declared(self):
        low, fx, _g = M['uniforms'](T.RACK['H'])
        sh = M['shader_texts'](T.lib)
        for un, ex in low:
            self.assertIn('uniform vec4 %s;' % un, sh['low'])
        for un, ex in fx:
            self.assertIn('uniform vec4 %s;' % un, sh['fx'])


class Mirror(unittest.TestCase):
    def test_amount_zero(self):
        img = pic()
        self.assertTrue(np.array_equal(L.reference(img, {'Amount': 0.0}), img))

    def test_blocks_uniform_without_edges(self):
        img = pic()
        out = L.reference(img, {'Edge': 2.0, 'Highlight': 0.0, 'Pixelsize': 6.0})
        for vy in range(0, H // 6):
            for vx in range(0, W // 6):
                b = out[vy * 6:vy * 6 + 6, vx * 6:vx * 6 + 6, :3]
                self.assertLess(np.ptp(b.reshape(-1, 3), axis=0).max(), 1e-12)

    def test_levels(self):
        out = L.reference(pic(), {'Edge': 2.0, 'Highlight': 0.0, 'Levels': 4, 'Contrast': 1.0, 'Saturation': 1.0})
        v = np.unique(np.round(out[..., :3] * 3, 9))
        self.assertTrue(np.allclose(v, np.round(v)))

    def test_outline_on_dark_side_only(self):
        img = pic()
        P = {'Pixelsize': 6.0, 'Levels': 32, 'Edge': 0.3, 'Outline': 1.0, 'Highlight': 0.0, 'Outliner': 0.0,
             'Outlineg': 0.0, 'Outlineb': 0.0, 'Contrast': 1.0, 'Saturation': 1.0}
        out = L.reference(img, P)
        black = out[..., :3].sum(-1) == 0
        self.assertTrue(black.any())
        self.assertFalse(black[30:60, 20:40][6:-6, 6:-6].any())      # inside the bright block: no outline
        self.assertTrue(black[:, 14:20].any() or black[24:30, :].any())

    def test_highlight_lightens(self):
        img = pic()
        a = L.reference(img, {'Highlight': 0.0, 'Edge': 0.3})
        b = L.reference(img, {'Highlight': 0.6, 'Edge': 0.3})
        self.assertTrue(np.all(b[..., :3] >= a[..., :3] - 1e-12))
        self.assertGreater((b - a).max(), 0.1)

    def test_grid(self):
        out = L.reference(pic(), {'Grid': 1.0, 'Edge': 2.0, 'Highlight': 0.0})
        self.assertTrue(np.all(out[:, 0, :3] == 0))
        self.assertTrue(np.all(out[5, :, :3] == 0))


if __name__ == '__main__':
    unittest.main()
