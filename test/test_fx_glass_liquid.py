"""Offline tests for FX_glass rack + module 'liquid' (builders/fx_glass.py, fx_glass_liquid.py + _logic). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_glass_liquid.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_glass_liquid_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('liquid', 'fx_glass')


class Rack(unittest.TestCase):
    def test_rack_reuses_stylise_rack(self):
        src = T.K.source('fx_glass.py')
        T.K.check_td_rules(self, src)
        self.assertIn("'fx_stylise.py'", src)
        self.assertNotIn('def rewire', src)
        ns = {}
        exec(compile(src.replace("with open(os.path.join(HERE, 'fx_stylise.py')) as _fh:\n    exec(_fh.read(), globals())",
                                 "H = {}"), 'fx_glass.py', 'exec'), ns)
        self.assertEqual(ns['NAME'], 'FX_glass')
        self.assertEqual(ns['BACKDROP_PAGE'], NS['BACKDROP_PAGE'])            # module copy == rack page


class Contract(unittest.TestCase):
    def test_module(self):
        T.check_module(self, NS, 'liquid', 'fx_glass')
        self.assertNotIn('uTDOutputInfo', NS['MATTE'])


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        self.W, self.H = 96, 80
        y, x = np.mgrid[0:self.H, 0:self.W]
        self.img = np.ones((self.H, self.W, 4), np.float32)
        self.img[..., 0] = ((x // 8 + y // 8) % 2).astype(np.float32)          # checker: refraction is visible
        self.img[..., 1] = x / self.W
        self.img[..., 2] = y / self.H
        self.bd = self.img.copy()
        self.shapes = L.shapes_from_rows([r.split() for r in ['0.5 0.5 50 40 12 0']])

    def test_sdf_box(self):
        P = dict(self.P, Smooth=0.001)
        d, idx = L.sdf(np.array([48.0, 48.0 + 40]), np.array([40.0, 40.0]), self.shapes, P, self.W, self.H)
        self.assertAlmostEqual(float(d[0]), -20.0, places=4)                    # centre: half the short side
        self.assertAlmostEqual(float(d[1]), 15.0, places=4)

    def test_amount_zero(self):
        out = L.look(self.img, self.bd, self.shapes, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.img).max()), 0.0)

    def test_flat_inside_is_unshifted_and_outside_untouched(self):
        P = dict(self.P, Frost=0.0, Tintamt=0.0, Bright=1.0, Rim=0.0, Spec=0.0, Edge=0.0, Shadow=0.0, Bevel=5.0)
        out = L.look(self.img, self.bd, self.shapes, P)
        self.assertLess(float(np.abs(out[40, 48] - self.img[40, 48]).max()), 1e-6)   # flat top: no shift
        self.assertEqual(float(np.abs(out[5, 5] - self.img[5, 5]).max()), 0.0)        # far outside
        Pb = dict(P, Bevel=30.0, Thickness=40.0)
        ob = L.look(self.img, self.bd, self.shapes, Pb)
        self.assertGreater(float(np.abs(ob[40, 26] - self.img[40, 26]).max()), 0.05)  # bevel refracts

    def test_dispersion_splits_channels(self):
        P = dict(self.P, Frost=0.0, Tintamt=0.0, Rim=0.0, Spec=0.0, Edge=0.0, Shadow=0.0, Bevel=30.0, Dispersion=0.2)
        a = L.look(self.img, self.bd, self.shapes, P)
        b = L.look(self.img, self.bd, self.shapes, dict(P, Dispersion=0.0))
        self.assertGreater(float(np.abs(a - b).max()), 0.02)


if __name__ == '__main__':
    unittest.main()
