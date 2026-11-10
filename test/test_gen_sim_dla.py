"""Offline tests for GEN_sim module 'dla' (builders/gen_sim_dla.py, glsl/gen_sim_dla_*.glsl, gen_sim_logic dla_*).
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sim_dla.py'"""
import unittest

import numpy as np

import test_gen_sim as K

M = K.module('dla')
L = K.LOGIC


class Uniforms(unittest.TestCase):
    def test_match_shaders(self):
        T, U = M['shader_texts'](), M['uniforms']()
        for k in ('touch', 'field', 'grow', 'look'):
            K.check_uniforms(self, T[k], U[k], 'dla.' + k)
            for _u, ex in U[k]:
                for e in ex:
                    float(K.ev(e, M))

    def test_sizes_bc_electrode(self):
        self.assertEqual((K.ev(M['SIMW'], M), K.ev(M['SIMH'], M)), (270, 480))
        self.assertEqual((K.ev(M['FW'], M, {'Fieldscale': 0.5}), K.ev(M['FH'], M, {'Fieldscale': 0.5})), (135, 240))
        for shape in range(len(L['DLA_SHAPES'])):
            bc = [K.ev(e, M, {'Shape': shape}) for e in dict(M['BC'])['uBC']]
            self.assertEqual(tuple(bc), L['DLA_BC'][shape])
        self.assertEqual(K.ev(M['EL_R'], M, {'Shape': 3}), L['dla_electrode'](3, 270, 480)[2])
        self.assertEqual(K.ev(M['EL_R'], M, {'Shape': 0}), 0.0)
        self.assertEqual(K.ev(M['NSTEPS'], M, {'Run': False}), 0)


class Field(unittest.TestCase):
    def test_jacobi_linear_profile(self):
        H, W = 16, 6
        fixed = np.full((H, W), -1.0)
        fixed[0, :] = 0.0                                                     # grounded bottom row
        phi = L['jacobi'](np.ones((H, W)), fixed, (-1, -1, -1, 1), 4000)      # top side electrode 1, sides mirror
        want = (np.arange(H) / H)[:, None]                                    # phi(y) = y / H (1 at y = H)
        self.assertLess(np.abs(phi - want).max(), 2e-3)

    def test_jacobi_dirichlet_and_fixed_kept(self):
        fixed = np.full((8, 8), -1.0)
        fixed[4, 4] = 0.0
        fixed[1, 1] = 1.0
        phi = L['jacobi'](np.full((8, 8), 0.5), fixed, (1, 1, 1, 1), 50)
        self.assertEqual(phi[4, 4], 0.0)
        self.assertEqual(phi[1, 1], 1.0)
        self.assertTrue((phi >= 0).all() and (phi <= 1).all())

    def test_fixed_from_cluster(self):
        occ = np.zeros((40, 40))
        occ[10, 10] = 1
        f = L['dla_fixed'](occ, 10, 10)                                       # 4 sim cells per field cell
        self.assertEqual(f[2, 2], 0.0)
        self.assertEqual((f == 0).sum(), 1)
        e = L['dla_fixed'](np.zeros((40, 40)), 20, 20, L['dla_electrode'](3, 20, 20))
        self.assertGreater((e == 1).sum(), 4)

    def test_phimax(self):
        phi = np.full((5, 5), 0.5)
        phi[2, 2] = 0.0
        phi[2, 3] = 0.7
        self.assertEqual(L['dla_phimax'](phi), 0.7)
        self.assertEqual(L['dla_phimax'](np.ones((4, 4))), 1.0)


class Growth(unittest.TestCase):
    def test_frontier_only_and_rate(self):
        occ = np.zeros((101, 101))
        occ[50, :] = 1
        field = np.full((101, 101), 0.5)
        P = {'Growth': 0.5, 'Eta': 1.0, 'Phiref': 1.0, 'Seed': 3}
        o2, st = L['dla_grow'](occ, np.zeros_like(occ), field, P, frame=7, tdpass=1, phimax=0.5)
        new = (o2 > 0) & (occ < 1)
        self.assertTrue(((np.argwhere(new)[:, 0] == 49) | (np.argwhere(new)[:, 0] == 51)).all())
        self.assertAlmostEqual(new.sum() / 202.0, 0.5, delta=0.08)            # p = 0.5 (0.5 / (0.5 x 1))^1
        self.assertTrue((st[new] == 7 * 8 + 1).all())
        o3, _ = L['dla_grow'](occ, np.zeros_like(occ), field, P, 7, 1, field_iters=10, phimax=0.5)
        self.assertTrue(np.array_equal(o3, occ))                              # warm-up gate (Warmup 256)

    def test_eta_sharpens(self):
        occ = np.zeros((3, 200))
        occ[0, :] = 1
        field = np.tile(np.linspace(0.01, 1.0, 200), (3, 1))
        P = {'Growth': 1.0, 'Phiref': 1.0, 'Seed': 1}
        lo, _ = L['dla_grow'](occ, 0 * occ, field, dict(P, Eta=0.5))
        hi, _ = L['dla_grow'](occ, 0 * occ, field, dict(P, Eta=4.0))
        self.assertGreater(lo[1].sum(), hi[1].sum() * 2)
        self.assertGreater(np.argwhere(hi[1] > 0)[:, 0].mean(), 120)            # high Eta: only the high-phi end

    def test_touch(self):
        occ = np.zeros((20, 10))
        occ[19, 5] = 1                                                        # top row
        self.assertTrue(L['dla_touched'](occ, 0))                             # centre: all sides are electrodes
        self.assertFalse(L['dla_touched'](occ, 2))                            # lightning: only the bottom side
        occ2 = np.zeros((20, 10))
        occ2[0, 3] = 1
        self.assertTrue(L['dla_touched'](occ2, 2))

    def test_run_presets(self):
        W, H = 68, 120
        for shape, P in ((0, {'Growth': 0.3, 'Eta': 1.0}), (2, {'Growth': 0.2, 'Eta': 4.0}),
                         (1, {'Growth': 0.3, 'Eta': 1.5})):
            P = dict(P, Shape=shape, Phiref=1.0, Seed=1, Warmup=256, Hold=1.0, Autoregrow=1)
            occ, st, phi, rg = L['dla_run'](W, H, W, H, P, frames=240, steps=4, iters=32, return_field=True)
            self.assertGreater(occ.sum() + rg * 50, 60, shape)                 # it grows (or regrew)
            self.assertLess(occ.mean(), 0.5, shape)                            # branches, not a filled blob


if __name__ == '__main__':
    unittest.main()
