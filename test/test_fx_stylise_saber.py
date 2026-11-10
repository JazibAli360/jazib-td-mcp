"""Offline tests for FX_stylise module 'saber' (builders/fx_stylise_saber.py, fx_stylise_saber_logic.py). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_stylise_saber.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_stylise_testkit as T  # noqa: E402
import fx_stylise_saber_logic as L  # noqa: E402
import fx_stylise_outline_logic as OL  # noqa: E402
import numpy as np  # noqa: E402

NS = T.load('saber')
JFA = {'jfa': open(os.path.join(T.K.BUILDERS, 'glsl', 'gen_sim_vor_jfa.glsl')).read()}


class Contract(unittest.TestCase):
    def test_module(self):
        pars = T.check_module(self, NS, 'saber', extra_texts=JFA)
        self.assertEqual(pars['Source'][2]['names'], NS['SOURCES'])
        self.assertEqual(NS['SEED'], T.load('outline')['SEED'])                 # reused, not copied
        self.assertIn('uniform vec4 uPts[64];', NS['FX'])

    def test_segs_callback_matches_mirror(self):
        ns = {}
        exec(NS['SEGS_CB'], ns)

        class Cell:
            def __init__(self, v):
                self.val = v

        class Tab:
            def __init__(self, rows):
                self.rows_ = rows
                self.numRows = len(rows)

            def row(self, i):
                return [Cell(v) for v in self.rows_[i]]

        class Par:
            def eval(self):
                return ''

        class M:
            def __init__(self, t):
                self.t = t
                self.par = type('p', (), {'Pathdat': Par()})()

            def op(self, n):
                return self.t
        rows = [r.split() for r in NS['DEFAULT_PATH']] + [['-'], ['0.1', '0.1'], ['0.2', '0.1']]
        got = ns['pts'](M(Tab(rows)))
        want = L.pts([(float(a), float(b)) for a, b in (r for r in rows if r[0] != '-')][:11] + [None] +
                     [(0.1, 0.1), (0.2, 0.1)])
        self.assertEqual(len(got), 13)
        self.assertLess(max(abs(a - b) for g, w in zip(got, want) for a, b in zip(g, w)), 1e-12)
        self.assertEqual(got[11][3], 0.0)                                       # pen up before the 12th point


@unittest.skipUnless(T.K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        T.compile_all(self, NS, extra_texts=JFA)


class Behaviour(unittest.TestCase):
    def setUp(self):
        self.P = T.pars_of(NS)
        self.W, self.H = 120, 100
        self.img = np.zeros((self.H, self.W, 4), np.float32)
        self.img[..., 3] = 1

    def test_path_distance_line(self):
        P = L.pts([(0.1, 0.5), (0.9, 0.5)])
        d, u, tipd = L.path_distance(self.W, self.H, P)
        self.assertAlmostEqual(float(d[50, 60]), 0.5, places=6)                  # pixel centre 0.5 px off the line
        self.assertAlmostEqual(float(u[50, 60]), (60.5 - 12) / 96, places=6)
        d2, _u, tip2 = L.path_distance(self.W, self.H, P, 0.0, 0.5)
        self.assertGreater(float(d2[50, 100]), 30)                              # beyond End: not drawn
        self.assertLess(float(tip2[50, 60]), 1.0)                               # tip at the half point (x = 60)

    def test_core_peak_and_add(self):
        P = L.pts([(0.1, 0.5), (0.9, 0.5)])
        d, u, tipd = L.path_distance(self.W, self.H, P)
        Q = dict(self.P, Back=2, Tip=0.0, Glowint=0.0)
        out = L.look(self.img, d, u, tipd, Q)
        self.assertGreater(float(out[50, 60, 0]), 0.9)                          # white core on the line
        self.assertLess(float(out[10, 60, 0]), 0.01)

    def test_amount_zero(self):
        P = L.pts([(0.1, 0.5), (0.9, 0.5)])
        d, u, tipd = L.path_distance(self.W, self.H, P)
        out = L.look(self.img, d, u, tipd, dict(self.P, Amount=0.0))
        self.assertEqual(float(np.abs(out - self.img).max()), 0.0)

    def test_mask_edge_distance(self):
        im = OL.disc_matte(self.W, self.H, 60.0, 50.0, 25.0)
        Q = dict(self.P, Source=1, Res=1)
        d, u = L.mask_distance(im, Q)
        px, py = np.mgrid[0:self.H, 0:self.W] + 0.5
        r = np.hypot(px - 50.0, py - 60.0)
        near = np.abs(r - 25) < 10
        self.assertLess(float(np.abs(d - np.abs(r - 25))[near].mean()), 0.3)
        Qs = dict(Q, Solid=1)
        ds, _u = L.mask_distance(im, Qs)
        self.assertEqual(float(ds[r < 20].max()), 0.0)                          # solid inside


if __name__ == '__main__':
    unittest.main()
