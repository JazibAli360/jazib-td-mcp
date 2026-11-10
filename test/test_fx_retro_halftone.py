"""Offline tests for FX_retro module 'halftone' (builders/fx_retro_halftone.py) + mirror (rack wiring / glslc:
test_fx_retro.py). Run: python3 -I -m unittest discover -s test -p 'test_fx_retro_halftone.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import fx_retro_halftone_logic as L  # noqa: E402
import test_fx_retro as T  # noqa: E402

M = T.module('halftone')


def flat(v, h=96, w=96):
    a = np.zeros((h, w, 4))
    a[..., :3] = v
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
        img = flat(0.3)
        self.assertTrue(np.array_equal(L.reference(img, {'Amount': 0.0}), img))

    def test_mono_coverage_tracks_darkness(self):
        P = {'Mode': 0, 'Cellsize': 12.0, 'Paperr': 1.0, 'Paperg': 1.0, 'Paperb': 1.0, 'Inkr': 0.0, 'Inkg': 0.0,
             'Inkb': 0.0}
        for v in (0.2, 0.5, 0.8):
            out = L.reference(flat(v), P)
            self.assertAlmostEqual(out[..., 0].mean(), v, delta=0.08)

    def test_white_is_paper_black_is_ink(self):
        P = {'Mode': 2}
        w = L.reference(flat(1.0), P)
        self.assertTrue(np.allclose(w[..., :3], [0.96, 0.94, 0.88]))
        b = L.reference(flat(0.0), P)
        self.assertTrue(np.allclose(b[..., :3], [0.08, 0.07, 0.1]))

    def test_cell_sampling_gives_round_dots(self):
        img = flat(0.5)
        y, x = np.mgrid[0:96, 0:96]
        img[..., 0] = img[..., 1] = img[..., 2] = x / 96.0
        out = L.reference(img, {'Mode': 0, 'Cellsize': 16.0, 'Sampling': 0})
        self.assertGreater(len(np.unique(np.round(out[..., 0], 3))), 2)


if __name__ == '__main__':
    unittest.main()
