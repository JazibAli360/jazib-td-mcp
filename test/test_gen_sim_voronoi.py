"""Offline tests for GEN_sim module 'voronoi' (builders/gen_sim_voronoi.py, glsl/gen_sim_vor_*.glsl, gen_sim_logic).
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sim_voronoi.py'"""
import math
import unittest

import numpy as np

import test_gen_sim as K

M = K.module('voronoi')
L = K.LOGIC


class Uniforms(unittest.TestCase):
    def test_match_shaders(self):
        T, U = M['shader_texts'](), M['uniforms']()
        for k in ('seed', 'jfa', 'look', 'worley'):
            K.check_uniforms(self, T[k], U[k], 'voronoi.' + k)
            for _u, ex in U[k]:
                for e in ex:
                    float(K.ev(e, M))

    def test_sizes(self):
        self.assertEqual((K.ev(M['JW'], M), K.ev(M['JH'], M)), (540, 960))
        self.assertEqual(K.ev(M['PM'], M), 10)
        self.assertEqual(K.ev(M['PM'], M), L['jfa_passes'](540, 960))
        self.assertEqual(K.ev(M['PM'], M, {'Res': 1.0}), 11)
        self.assertEqual(M['WORLEY0'], 5)
        self.assertEqual(L['VOR_MODES'][5:], ['worleyf1', 'worleyf2', 'worleyedge', 'worleycells'])


class Seeds(unittest.TestCase):
    def test_inside_frame_and_moving(self):
        for mode in (0, 1):
            s = L['seed_positions'](500, 135, 240, t=3.0, mode=mode, seed=2, wander=1.5)
            self.assertTrue((s >= 0).all() and (s[:, 0] <= 135).all() and (s[:, 1] <= 240).all())
        a = L['seed_positions'](50, 135, 240, t=0.0, wander=0.3)
        b = L['seed_positions'](50, 135, 240, t=0.5, wander=0.3)
        self.assertGreater(np.abs(a - b).max(), 0.1)
        self.assertTrue(np.array_equal(L['seed_positions'](50, 135, 240, t=1.0, wander=0.0),
                                       L['seed_positions'](50, 135, 240, t=9.0, wander=0.0)))

    def test_grid_is_even(self):
        s = L['seed_positions'](200, 200, 200, mode=1, jitter=0.0)
        d = np.sqrt(((s[:, None] - s[None]) ** 2).sum(-1)) + np.eye(200) * 1e9
        nn = d.min(1)
        self.assertLess(nn.std() / nn.mean(), 0.1)

    def test_input_weighting(self):
        img = np.zeros((100, 100, 4))
        img[:, 50:, :3] = 1.0                                                 # right half white
        s = L['seed_positions'](2000, 100, 100, mode=2, bias=1.0, inp=img)
        self.assertGreater((s[:, 0] >= 50).mean(), 0.97)


class Jfa(unittest.TestCase):
    def test_matches_brute_force(self):
        W, H, n = 135, 240, 300
        seeds = L['seed_positions'](n, W, H, seed=4)
        sm = L['scatter'](seeds, W, H)
        brute = L['voronoi_brute'](seeds, W, H)
        ids = sm[..., 2][sm[..., 2] > 0].astype(int)
        for extra, need in ((0, 0.99), (1, 0.997)):
            j = L['jfa'](sm, extra=extra)
            got = j[..., 2].astype(int)
            ok = (got == brute) | ~np.isin(brute, ids)                        # seeds lost to a shared texel
            self.assertGreaterEqual(ok.mean(), need, extra)

    def test_every_texel_has_a_seed(self):
        sm = L['scatter'](L['seed_positions'](20, 64, 64, seed=9), 64, 64)
        self.assertTrue((L['jfa'](sm)[..., 2] > 0).all())

    def test_gabriel_subset_of_adjacency(self):
        W = H = 120
        seeds = L['seed_positions'](40, W, H, seed=3)
        ids = L['voronoi_brute'](seeds, W, H)
        adj = set()
        for a, b in ((ids[:, 1:], ids[:, :-1]), (ids[1:, :], ids[:-1, :])):
            m = a != b
            for u, v in zip(a[m], b[m]):
                adj.add((min(u, v) - 1, max(u, v) - 1))
        g = L['gabriel_edges'](seeds)
        self.assertGreater(len(g), 40)
        inside = [e for e in g if e in adj]
        self.assertGreaterEqual(len(inside), len(g) - 2)                      # border cells may clip a pair


class Worley(unittest.TestCase):
    def test_f1_f2(self):
        f1, f2, i1 = L['worley'](200, 120, 40.0, jitter=1.0, wander=0.5, t=2.0)
        self.assertTrue((f1 <= f2).all())
        self.assertLess(f1.max(), math.sqrt(2) + 1e-9)
        self.assertGreater(len(np.unique(i1)), 10)
        g1, _g2, _ = L['worley'](200, 120, 40.0, jitter=0.0)
        self.assertLess(g1.min(), 0.02)                                      # jitter 0: points at cell centres


if __name__ == '__main__':
    unittest.main()
