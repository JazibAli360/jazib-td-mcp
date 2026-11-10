"""Offline tests of the CV_person_mask light wrap + despill pass (FX7c 7C-08, lane F; docs/builds/person_mask.md
"Light wrap"): glslc of the wrap pass (3 inputs), the numpy reference's properties.
Run: python3 -I -m unittest discover -s test -p 'test_person_mask_wrap.py'"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_fx_track as T  # noqa: E402  (glslc stub with uTDOutputInfo)

B = os.path.join(os.path.dirname(HERE), 'builders')
sys.path.insert(0, B)
import person_mask_logic as L  # noqa: E402


def pm_ns():
    src = open(os.path.join(B, 'person_mask.py')).read()
    ns = {}
    exec(compile(src, 'person_mask.py', 'exec'), ns)
    return ns


def disc(H=64, W=64, r=20):
    py, px = np.mgrid[0:H, 0:W]
    m = ((px - W / 2 + 0.5) ** 2 + (py - H / 2 + 0.5) ** 2 <= r * r).astype(np.float64)
    comp = np.zeros((H, W, 4))
    comp[..., 0], comp[..., 1], comp[..., 2] = 0.2 * m, 0.6 * m, 0.1 * m      # green-ish person, premultiplied
    comp[..., 3] = m
    return comp, m


class Wrap(unittest.TestCase):
    @unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc')
    def test_glslc(self):
        ok, err = T.glslc_n(pm_ns()['WRAP_GLSL'], 3)
        self.assertTrue(ok, err)

    def test_identity_when_off(self):
        comp, m = disc()
        out = L.wrap_ref(comp, m, np.ones(comp.shape[:2] + (3,)), {'Lightwrap': 0.0, 'Wrapwidth': 8.0,
                                                                   'Wrapgamma': 1.0, 'Despill': 0.0})
        self.assertEqual(float(np.abs(out - comp).max()), 0.0)

    def test_band_and_premultiplied(self):
        comp, m = disc()
        light = np.zeros(comp.shape[:2] + (3,))
        light[..., 0] = 1.0                                                     # red light behind
        out = L.wrap_ref(comp, m, light, {'Lightwrap': 2.0, 'Wrapwidth': 6.0, 'Wrapgamma': 1.0, 'Despill': 0.0})
        d = out[..., 0] - comp[..., 0]
        self.assertEqual(float(d[32, 32]), 0.0)                                 # deep inside: no wrap
        self.assertEqual(float(np.abs(out[m == 0] - comp[m == 0]).max()), 0.0)  # outside the person: untouched
        self.assertGreater(float(d[32, 13]), 0.2)                               # on the edge: red bleeds in
        self.assertTrue(bool((out[..., :3] <= out[..., 3:4] + 1e-9).all()))     # still premultiplied

    def test_despill(self):
        comp, m = disc()
        out = L.wrap_ref(comp, m, np.zeros(comp.shape[:2] + (3,)), {'Lightwrap': 0.0, 'Wrapwidth': 6.0,
                                                                    'Wrapgamma': 1.0, 'Despill': 1.0})
        self.assertAlmostEqual(float(out[32, 32, 1]), 0.2)                      # g -> max(r, b)
        self.assertEqual(len(L.wrap_taps(10.0)), 16)


if __name__ == '__main__':
    unittest.main()
