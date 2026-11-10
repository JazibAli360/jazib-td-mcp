"""Offline tests for FX_retro module 'stitch' (builders/fx_retro_stitch.py) + mirror fx_retro_stitch_logic.py (rack
wiring / glslc: test_fx_retro.py). Run: python3 -I -m unittest discover -s test -p 'test_fx_retro_stitch.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import fx_retro_stitch_logic as L  # noqa: E402
import test_fx_retro as T  # noqa: E402

M = T.module('stitch')
PA = T.module('pixelart')


class Spec(unittest.TestCase):
    def test_defaults_presets(self):
        pars = dict((n, (s, d, o)) for _pg, pl in M['PAGES'] for n, s, d, o in pl)
        for k, v in L.DEFAULTS.items():
            s, d, o = pars[k]
            self.assertAlmostEqual(float(o['names'].index(d) if s == 'Menu' else d), float(v), msg=k)
        for _s, pname, vals in M['PRESETS']:
            self.assertEqual(set(vals), set(pars), pname)

    def test_shares_pixelart_low(self):
        lib = T.lib
        self.assertEqual(M['shader_texts'](lib)['low'], PA['shader_texts'](lib)['low'])
        low, fx, _g = M['uniforms'](T.RACK['H'])
        self.assertEqual(low, PA['uniforms'](T.RACK['H'])[0])
        for un, _e in fx:
            self.assertIn('uniform vec4 %s;' % un, M['FX'])


class Mirror(unittest.TestCase):
    def setUp(self):
        self.cells = np.zeros((4, 3, 4))
        self.cells[..., 0] = 0.8
        self.cells[..., 3] = 1
        self.cells[0, 0, :3] = (0.93, 0.9, 0.82)                          # = fabric: skipped
        self.img = np.full((80, 60, 4), 0.5)
        self.img[..., 3] = 1

    def test_amount_zero(self):
        self.assertTrue(np.array_equal(L.render(self.img, self.cells, L.pars_of({'Amount': 0.0}), 20, 20), self.img))

    def test_skip_cell_is_bare_fabric(self):
        P = L.pars_of({'Jitter': 0.0})
        out = L.render(self.img, self.cells, P, 20, 20)
        bare = out[0:20, 0:20, :3]
        self.assertLess(np.abs(bare[..., 0] - bare[..., 2] * 0.93 / 0.82).max(), 0.05)    # fabric hue, no red
        red = out[20:40, 20:40]
        self.assertGreater((red[..., 0] - red[..., 1]).max(), 0.3)                       # thread visible

    def test_cross_covers_both_diagonals(self):
        P = L.pars_of({'Jitter': 0.0, 'Gloss': 0.0})
        out = L.render(self.img, self.cells, P, 20, 20)
        c = out[20:40, 20:40]
        thr = c[..., 0] - c[..., 1] > 0.2
        self.assertTrue(thr[3, 3] and thr[16, 16] and thr[3, 16] and thr[16, 3])       # 4 arm ends
        half = L.render(self.img, self.cells, dict(P, Style=1), 20, 20)[20:40, 20:40]
        th = half[..., 0] - half[..., 1] > 0.2
        self.assertTrue(th[3, 3] and th[16, 16] and not th[3, 16] and not th[16, 3])

    def test_satin_strands(self):
        P = L.pars_of({'Jitter': 0.0, 'Style': 2, 'Strands': 4, 'Thread': 0.8})
        out = L.render(self.img, self.cells, P, 20, 20)[20:40, 20:40]
        self.assertGreater((out[..., 0] - out[..., 1] > 0.2).mean(), 0.4)

    def test_hash_range(self):
        h = L.hc(np.arange(100), np.arange(100), 7)
        self.assertTrue(np.all((h >= 0) & (h < 1)))


if __name__ == '__main__':
    unittest.main()
