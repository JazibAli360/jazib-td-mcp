"""Offline tests for FX_glitch module 'mosaic' (builders/fx_glitch_mosaic.py), Shape hex / tri / square mirror
builders/fx_glitch_mosaic_logic.py. Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_mosaic.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import numpy as np  # noqa: E402
import fx_glitch_mosaic_logic as L  # noqa: E402

NS = K.load_module('mosaic')
W, H = 160, 200


def pic(seed=0):
    rng = np.random.default_rng(seed)
    a = rng.random((H, W, 4))
    a[..., 3] = 1.0
    return a


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'mosaic')
        self.assertEqual(pars['Shape'][2]['names'], L.SHAPES)
        for k, v in L.DEFAULTS.items():
            if k == 'Shape':
                continue
            d = pars[k][1]
            if pars[k][0] == 'Menu':
                d = pars[k][2]['names'].index(d)
            self.assertEqual(float(d), float(v), k)
        self.assertEqual(pars['Shape'][1], 'quad')                       # old instances keep the quadtree
        K.check_uniforms(self, NS['uniforms'](), NS['SHADER'], pars)

    def test_presets_full_state(self):
        names = set(n for _pg, pl in NS['PAGES'] for n, _s, _d, _o in pl)
        for _slot, pname, vals in NS['PRESETS']:
            self.assertEqual(set(vals), names, pname)

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_mosaic.py'))
        K.check_td_rules(self, K.source('fx_glitch_mosaic_logic.py'))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_all(self):
        for n in ('SHADER', 'STATS', 'STAMP'):
            ok, err = K.glslc(NS[n])
            self.assertTrue(ok, n + err)


class Lattice(unittest.TestCase):
    def test_cells_partition_and_edges(self):
        rng = np.random.default_rng(1)
        q = rng.uniform(-20, 20, (2, 5000))
        for shp, area in ((1, 0.8660254), (2, 0.4330127), (3, 1.0)):
            cx, cy, e, ix, iy = L.lattice(q[0], q[1], shp)
            self.assertTrue(np.all(e >= -1e-9), shp)
            self.assertTrue(np.all(e <= 0.5 + 1e-9), shp)
            # the centre of a cell maps back to the same cell
            c2 = L.lattice(cx, cy, shp)
            self.assertTrue(np.all((c2[3] == ix) & (c2[4] == iy)), shp)
            # cell area: unique ids per unit area ~ 1 / area
            g = np.mgrid[0:200, 0:200] / 10.0
            ids = L.lattice(g[1].ravel(), g[0].ravel(), shp)
            n = len(set(zip(ids[3].tolist(), ids[4].tolist())))
            self.assertAlmostEqual(n * area / 400.0, 1.0, delta=0.15, msg=shp)

    def test_hex_centres_on_lattice(self):
        cx, cy, _e, ix, iy = L.lattice(np.array([0.1, 0.6, 3.3]), np.array([0.2, 1.1, -2.0]), 1)
        self.assertTrue(np.allclose(cx * 2, np.round(cx * 2)))
        self.assertTrue(np.allclose(cy / 0.8660254, np.round(cy / 0.8660254)))


class Cells(unittest.TestCase):
    def test_amount_zero(self):
        img = pic()
        self.assertTrue(np.array_equal(L.reference(img, L.pars_of({'Amount': 0.0})), img))

    def test_flat_cells_uniform(self):
        img = pic(2)
        for shp in (1, 2, 3):
            P = L.pars_of({'Shape': shp, 'Gap': 0.0, 'Cellsize': 20.0})
            out = L.reference(img, P)
            y, x = np.mgrid[0:H, 0:W]
            _cx, _cy, _e, ix, iy = L.lattice((x + 0.5 - W / 2) / 20.0, (y + 0.5 - H / 2) / 20.0, shp)
            key = ix * 100000 + iy
            for v in np.unique(key)[:50]:
                self.assertLess(np.ptp(out[key == v][:, :3], axis=0).max(), 1e-12)

    def test_gap_colour(self):
        img = pic(3)
        out = L.reference(img, L.pars_of({'Shape': 3, 'Gap': 6.0, 'Cellsize': 40.0, 'Gapr': 1.0}))
        # square cells 40 px, frame centred: the line x = W/2 is a cell border -> gap
        self.assertTrue(np.allclose(out[:, W // 2, 0], 1.0))
        self.assertTrue(np.allclose(out[:, W // 2, 1:3], 0.0))

    def test_image_fill_without_flip_is_identity_inside(self):
        img = pic(4)
        out = L.reference(img, L.pars_of({'Shape': 1, 'Gap': 0.0, 'Cellfill': 2}))
        self.assertTrue(np.allclose(out, img))

    def test_flip_squashes_cells(self):
        img = pic(5)
        P = L.pars_of({'Shape': 3, 'Gap': 0.0, 'Cellsize': 40.0, 'Flip': 1.0, 'Fliptime': 1.0, 'Cellfill': 2})
        mid = L.reference(img, P, t=0.25, last=0.0)           # cos(pi/4): rows beyond 0.707 of the half cell -> gap
        black = (mid[..., :3].sum(-1) == 0).mean()
        self.assertGreater(black, 0.2)
        done = L.reference(img, P, t=2.0, last=0.0)           # flip over: picture back
        self.assertTrue(np.allclose(done, img))

    def test_flip_share(self):
        img = pic(6)
        P = L.pars_of({'Shape': 3, 'Gap': 0.0, 'Cellsize': 10.0, 'Flip': 0.3, 'Fliptime': 1.0, 'Flipmode': 2})
        out = L.reference(img, P, t=0.5, last=0.0)            # shrink at max: flipping cells fully gap
        g = (out[..., :3].sum(-1) == 0).mean()
        self.assertTrue(0.2 < g < 0.4, g)

    def test_back_side_recolours(self):
        img = pic(7)
        P = L.pars_of({'Shape': 3, 'Gap': 0.0, 'Cellsize': 40.0, 'Flip': 1.0, 'Fliptime': 1.0, 'Recolour': 0.5,
                       'Flipmode': 3})
        a = L.reference(img, P, t=0.9, last=0.0)
        b = L.reference(img, dict(P, Recolour=0.0), t=0.9, last=0.0)
        self.assertGreater(np.abs(a - b).mean(), 0.01)


if __name__ == '__main__':
    unittest.main()
