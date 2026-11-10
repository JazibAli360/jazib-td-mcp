"""Offline tests for builders/pop_crack3d.py + pop_crack3d_logic.py (lane H TC-12; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_crack3d.py'"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_crack3d_logic as L  # noqa: E402


def _rgb(self, n, label=''):
    out = []
    for ch in 'rgb':
        p = getattr(self.owner.par, n + ch)
        p.val = None
        self.owner.custom.append(n + ch)
        out.append(p)
    return out


K.FakePage.appendRGB = _rgb          # the shared kit has no RGB pars yet (local stand-in)


class Logic(unittest.TestCase):
    def test_worley_vs_bruteforce(self):
        p = L.params(cellscale=3.0, seed=7)
        rng = np.random.default_rng(1)
        pts = rng.uniform(-1.2, 1.2, (300, 3))
        F1, F2, cid, _ = L.worley(pts, p)
        # brute force over every site in a padded cube
        r = np.arange(-6, 6)
        C = np.stack(np.meshgrid(r, r, r, indexing='ij'), -1).reshape(-1, 3)
        S, _ = L.site(C, 7)
        d = np.linalg.norm(S[None] - (pts * 3.0)[:, None], axis=-1)
        d.sort(axis=1)
        self.assertTrue(np.allclose(F1, d[:, 0]))
        self.assertTrue(np.allclose(F2, d[:, 1]))
        self.assertTrue((F2 >= F1).all())

    def test_pruned_search_is_exact(self):
        for cs, seed in ((4.0, 1), (3.0, 7), (11.0, 3)):
            p = L.params(cellscale=cs, seed=seed)
            pts = np.random.default_rng(seed).uniform(-1.3, 1.3, (5000, 3))
            F1, F2, cid, hid = L.worley(pts, p)
            G1, G2, gid, ghid, visits = L.worley_pruned(pts, p)
            self.assertTrue(np.allclose(F1, G1, rtol=0, atol=1e-12))
            self.assertTrue(np.allclose(F2, G2, rtol=0, atol=1e-12))
            self.assertTrue((cid == gid).all() and (hid == ghid).all())
            self.assertLess(visits, 14.0)                 # vs 27 hashed cells per pixel before

    def test_hash_ranges(self):
        h = L.hcell(np.arange(-50, 50), np.arange(100), -np.arange(100), 3)
        for k in range(4):
            v = L.hcomp(h, k)
            self.assertTrue((v >= 0).all() and (v < 1).all())
        S, _ = L.site(np.array([[0, 0, 0], [-3, 2, 5]]), 1)
        self.assertTrue(((S - np.array([[0, 0, 0], [-3, 2, 5]])) < 1).all())

    def test_front(self):
        p = L.params(impact=(0, 0, 1), reach=2.0, progress=0.5, soft=0.0001)
        f = L.front(np.array([[0, 0, 1.0], [0, 0, 0.1], [0, 0, -1.0]]), p)
        self.assertEqual(list(f), [1.0, 1.0, 0.0])
        self.assertEqual(float(L.front(np.array([[0, 0, 1.0]]), L.params(progress=0.0))[0]), 0.5)

    def test_crack_fraction_grows_with_width_and_progress(self):
        pts = L.sphere_points(20000)
        fr = [L.crack_mask(pts, L.params(width=w)).mean() for w in (0.02, 0.05, 0.1, 0.2)]
        self.assertTrue(all(a < b for a, b in zip(fr, fr[1:])), fr)
        self.assertGreater(fr[1], 0.01)
        self.assertLess(fr[1], 0.3)
        pr = [L.crack_mask(pts, L.params(progress=q)).mean() for q in (0.0, 0.3, 0.6, 1.0)]
        self.assertEqual(pr[0], 0.0)
        self.assertTrue(all(a <= b for a, b in zip(pr, pr[1:])), pr)

    def test_erosion_fraction(self):
        pts = L.sphere_points(40000)
        p = L.params(erode=0.5)
        F1, F2, cid, hid = L.worley(pts, p)
        cells = {tuple(c): h for c, h in zip(cid, hid)}
        hs = np.array(list(cells.values()), dtype=np.uint64)
        frac_cells = (L.hcomp(hs, 3) < 0.5).mean()
        self.assertGreater(frac_cells, 0.3)
        self.assertLess(frac_cells, 0.7)
        self.assertEqual(L.eroded(pts, L.params(erode=0.0)).sum(), 0)
        self.assertEqual(L.eroded(pts, L.params(erode=1.0, progress=0.0)).sum(), 0)
        self.assertEqual(L.eroded(pts, L.params(erode=1.0)).mean(), 1.0)   # reach 2.5 covers the unit sphere

    def test_check_data_synthetic(self):
        p = L.params()
        pts = L.sphere_points(5000)
        F1, F2, _, _ = L.worley(pts, p)
        hard = ((F2 - F1) < p['width']) & (L.front(pts, p) > 0.5)
        pos = np.concatenate([pts, np.ones((len(pts), 1))], 1)
        dat = np.stack([F1, F2 - F1, hard.astype(float), np.ones(len(pts))], 1)
        r = L.check_data(pos, dat, p)
        self.assertTrue(r['pass'], r)
        dat[:, 2] = 1.0 - dat[:, 2]
        self.assertFalse(L.check_data(pos, dat, p)['pass'])


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_crack3d.py')
        o = c.ops
        for n in ('in1', 'clock', 'spin', 'sphere', 'torus', 'box', 'mat', 'mat_vertex', 'mat_pixel', 'geo', 'cam',
                  'render', 'out_sel', 'out1'):
            self.assertIn(n, o)
        sel = o['geo'].op('sel')
        self.assertIn("'../torus'", sel.par.pop.expr)
        self.assertEqual(o['geo'].par.material.val, 'mat')
        self.assertEqual(o['sphere'].par.type.val, 'geodesic')
        self.assertEqual([K.src(o['out_sel'], 0), K.src(o['out_sel'], 1)], ['in1', 'render'])
        m = o['mat']
        self.assertEqual((m.par.sampler0name.val, m.par.sampler0top.val), ('sIn', 'in1'))
        self.assertEqual(K.uniform_names(m), [u for u, _ in ns['UNIFORMS']])
        self.assertIn('aa1', o['render'].par.antialias.expr)
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        for n in ('Amount', 'Style', 'Shape', 'Cellscale', 'Erode', 'Glowcolorr', 'Basecolorb', 'Resw'):
            self.assertIn(n, c.custom)
        self.assertEqual(c.par.Detail.max, 96)

    def test_first(self):
        c, reply, ns = K.fake_build('pop_crack3d.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_contract(self):
        _c, _r, ns = K.fake_build('pop_crack3d.py')
        decl = K.declared(ns['PIXEL'])
        for u, _ in ns['UNIFORMS']:
            self.assertIn(u, decl)
        self.assertIn('TDPos()', ns['VERTEX'])
        self.assertNotIn('#version', ns['VERTEX'] + ns['PIXEL'])
        self.assertEqual(ns['STYLES'], L.STYLES)
        px = ns['PIXEL']
        self.assertLess(px.index('fwidth'), px.index('discard;\n    if (st == 2)'))   # derivatives before discard

    def test_ascii(self):
        for f in ('pop_crack3d.py', 'pop_crack3d_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_crack3d.py')
        ok, err = K.glslc_vert(ns['VERTEX'])
        self.assertTrue(ok, err)
        ok, err = K.glslc_pixel(ns['PIXEL'])
        self.assertTrue(ok, err)
        self.assertEqual(K.bounded_loops(ns['PIXEL']), [])


if __name__ == '__main__':
    unittest.main()
