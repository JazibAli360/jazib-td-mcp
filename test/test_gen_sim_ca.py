"""Offline tests for GEN_sim module 'ca' (builders/gen_sim_ca.py, glsl/gen_sim_ca_*.glsl, gen_sim_logic ca_*).
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sim_ca.py'"""
import unittest

import numpy as np

import test_gen_sim as K

M = K.module('ca')
L = K.LOGIC


def st_of(s):
    s = np.asarray(s, dtype=float)
    return np.stack([s, np.zeros_like(s), np.zeros_like(s), np.ones_like(s)], -1)


def run(s, fam, P, n):
    st = st_of(s)
    for k in range(n):
        st = L['ca_step'](st, fam, P, 10, k)
    return st[..., 0]


class Uniforms(unittest.TestCase):
    def test_step_and_look_match_shaders(self):
        T = M['shader_texts']()
        K.check_uniforms(self, T['step'], M['step_uniforms'](), 'ca.step')
        K.check_uniforms(self, T['look'], M['look_uniforms'](), 'ca.look')

    def test_expressions_evaluate(self):
        for name, U in (('step', M['step_uniforms']()), ('look', M['look_uniforms']())):
            for u, ex in U:
                for e in ex:
                    v = K.ev(e, M)
                    self.assertIsInstance(float(v), float, (name, u, e))

    def test_sizes_and_steps(self):
        self.assertEqual(K.ev(M['SIMW'], M), 270)
        self.assertEqual(K.ev(M['SIMH'], M), 480)
        self.assertEqual(K.ev(M['SIMW'], M, {'Cell': 1.0}), 1080)
        self.assertEqual([K.ev(M['NSTEPS'], M, {'Steps': 3.0}, frame=f) for f in (5, 6)], [3, 3])
        self.assertEqual([K.ev(M['NSTEPS'], M, {'Steps': 0.5}, frame=f) for f in (4, 5, 6, 7)], [1, 0, 1, 0])
        self.assertEqual(K.ev(M['NSTEPS'], M, {'Run': False}), 0)
        self.assertEqual(K.ev(M['EPOCH'], M), 1.0)                          # Resetcount 0 -> epoch 1 (blank = 0)

    def test_rulesets(self):
        want = {'life': (8, 12, 2), 'highlife': (72, 12, 2), 'seeds': (4, 0, 2), 'brian': (4, 0, 3),
                'starwars': (4, 8 + 16 + 32, 4), 'daynight': (8 + 64 + 128 + 256, 8 + 16 + 64 + 128 + 256, 2)}
        names = [r[0] for r in M['RULESETS']]
        for nm, (b, s, c) in want.items():
            i = names.index(nm)
            got = tuple(K.ev(L['rule_expr'](k, M['RULE_SRC']), M, {'Ruleset': i}) for k in 'bsc')
            self.assertEqual(got, (b, s, c), nm)
            self.assertEqual(L['parse_rule'](M['RULESETS'][i][2]), (b, s, c), nm)
        custom = names.index('custom')
        self.assertEqual(K.ev(L['rule_expr']('b', M['RULE_SRC']), M, {'Ruleset': custom, 'Rule': 'b36 / s23'}), 72)
        self.assertEqual(L['parse_rule']('B33/S9x/C'), (8, 0, 2))           # duplicates, digit 9, bad C ignored
        self.assertEqual(L['ruleset_rule']('brian', 'B1/S1'), 'B2/S/C3')
        self.assertEqual(L['ruleset_rule']('custom', 'B1/S1'), 'B1/S1')

    def test_radius_and_lenia_norm(self):
        self.assertEqual([K.ev(M['RADIUS'], M, {'Family': f}) for f in range(5)], [1, 1, 1, 5, 10])
        for R in (1, 5, 13, 16):
            n = K.ev(L['lenia_norm_expr'](), M, {'Leniar': R})
            self.assertAlmostEqual(n, float(L['lenia_kernel'](R).sum()), places=9)
        self.assertEqual(K.ev(L['lenia_norm_expr'](), M, {'Leniar': 40}), L['lenia_norm'](16))   # shader clamp
        self.assertEqual(K.ev(M['C_OR_N'], M, {'Family': 0, 'Ruleset': 6}), 3)
        self.assertEqual(K.ev(M['C_OR_N'], M, {'Family': 2}), 12)


class Rules(unittest.TestCase):
    P = {'Rule': 'B3/S23', 'Wrap': 1, 'Decay': 0.5}

    def test_glider_moves(self):
        s = np.zeros((12, 12))
        for y, x in ((5, 4), (4, 5), (3, 3), (3, 4), (3, 5)):                 # y = 0 bottom
            s[y, x] = 1
        out = run(s, 0, self.P, 4)
        self.assertEqual(out.sum(), 5)
        self.assertTrue(np.array_equal(out, np.roll(s, (-1, 1), axis=(0, 1))))  # one cell right and down

    def test_blinker_and_block(self):
        s = np.zeros((8, 8))
        s[4, 3:6] = 1
        self.assertTrue(np.array_equal(run(s, 0, self.P, 2), s))
        self.assertFalse(np.array_equal(run(s, 0, self.P, 1), s))
        b = np.zeros((8, 8))
        b[2:4, 2:4] = 1
        self.assertTrue(np.array_equal(run(b, 0, self.P, 5), b))

    def test_glow_and_age(self):
        s = np.zeros((8, 8))
        s[4, 3:6] = 1
        st = L['ca_step'](st_of(s), 0, self.P)
        self.assertEqual(st[4, 4, 1], 1.0)                                     # centre stays alive
        self.assertEqual(st[4, 3, 1], 0.0)                                     # died: glow 0 * decay
        self.assertEqual(st[4, 4, 2], 1.0)                                     # age + 1
        st2 = L['ca_step'](st, 0, self.P)
        self.assertEqual(st2[3, 4, 1], 0.5)                                    # alive last step, dead now: decay

    def test_brians_brain(self):
        P = dict(self.P, Rule='B2/S/C3')
        s = np.zeros((6, 6))
        s[2, 2] = s[2, 3] = 1
        out = run(s, 0, P, 1)
        self.assertEqual(out[2, 2], 2)                                         # alive -> dying (no survival)
        self.assertEqual(out[1, 2], 1)                                         # 2 live neighbours -> born
        self.assertEqual(run(s, 0, P, 2)[2, 2], 0)                             # dying -> dead (C = 3)

    def test_wireworld_electron_travels(self):
        s = np.zeros((5, 12))
        s[2, 1:11] = 3
        s[2, 3], s[2, 2] = 1, 2                                                # head at 3, tail at 2 -> moving right
        out = run(s, 1, self.P, 4)
        self.assertEqual(out[2, 7], 1)
        self.assertEqual(out[2, 6], 2)
        self.assertEqual(int((out == 1).sum()), 1)

    def test_cyclic(self):
        P = {'States': 3, 'Cycthresh': 1, 'Cycrange': 1, 'Wrap': 1}
        s = np.zeros((4, 4))
        s[1, 1] = 1
        out = run(s, 2, P, 1)
        self.assertEqual(out[1, 2], 1)                                         # 0 sees a 1 -> 1
        self.assertEqual(out[1, 1], 1)                                         # 1 needs a 2 -> stays
        self.assertEqual(out[3, 3], 0)

    def test_ltl_radius1_equals_life(self):
        rng = np.random.default_rng(3)
        s = (rng.random((40, 50)) < 0.35).astype(float)
        P = dict(self.P, Ltlr=1, Ltlb1=3, Ltlb2=3, Ltls1=2, Ltls2=3)
        self.assertTrue(np.array_equal(run(s, 3, P, 6), run(s, 0, self.P, 6)))

    def test_dead_border_vs_wrap(self):
        s = np.zeros((6, 6))
        s[0, 2:5] = 1                                                          # blinker on the bottom row
        w = run(s, 0, dict(self.P, Wrap=1), 1)
        d = run(s, 0, dict(self.P, Wrap=0), 1)
        self.assertEqual(w[5, 3], 1)                                           # wraps to the top row
        self.assertEqual(d[5, 3], 0)
        self.assertEqual(d.sum(), 2)                                           # half a blinker survives


class Lenia(unittest.TestCase):
    def test_uniform_field_growth(self):
        P = {'Leniar': 5, 'Leniamu': 0.15, 'Leniasigma': 0.015, 'Leniadt': 0.1, 'Wrap': 1}
        for c in (0.15, 0.3):
            out = run(np.full((20, 20), c), 4, P, 1)
            g = 2 * np.exp(-0.5 * ((c - 0.15) / 0.015) ** 2) - 1                 # U = c (normalised kernel)
            self.assertTrue(np.allclose(out, np.clip(c + 0.1 * g, 0, 1)))

    def test_kernel_shape(self):
        k = L['lenia_kernel'](13)
        self.assertEqual(k.shape, (27, 27))
        self.assertEqual(k[13, 13], 0.0)                                       # r = 0 excluded
        self.assertAlmostEqual(k.max(), 1.0, delta=0.02)                       # peak near r = 0.5
        self.assertTrue(np.allclose(k, k.T))

    def test_worms_survive(self):                                              # the 'lenia worms' preset numbers
        P = {'Leniar': 10, 'Leniamu': 0.15, 'Leniasigma': 0.015, 'Leniadt': 0.1, 'Density': 0.5, 'Seed': 1,
             'Seedmode': 0, 'Wrap': 1}
        s = L['ca_init'](64, 64, 4, P)
        out = run(s, 4, P, 120)
        self.assertGreater((out > 0.1).mean(), 0.1)


class Init(unittest.TestCase):
    def test_noise_density_and_determinism(self):
        P = {'Seedmode': 0, 'Density': 0.3, 'Seed': 5}
        a = L['ca_init'](200, 100, 0, P)
        self.assertAlmostEqual(a.mean(), 0.3, delta=0.01)
        self.assertTrue(np.array_equal(a, L['ca_init'](200, 100, 0, P)))
        self.assertFalse(np.array_equal(a, L['ca_init'](200, 100, 0, dict(P, Seed=6))))

    def test_blob_wires_input_empty(self):
        b = L['ca_init'](100, 100, 0, {'Seedmode': 1, 'Density': 1.0})
        self.assertEqual(b[50, 50], 1)
        self.assertEqual(b[5, 5], 0)
        w = L['ca_init'](48, 48, 1, {'Seedmode': 3, 'Wirespacing': 12, 'Density': 0.0, 'Sparks': 0.0})
        self.assertEqual(set(np.unique(w)), {0.0, 3.0})
        self.assertTrue((w[:, 12] == 3).all() and w[5, 5] == 0)
        img = np.zeros((40, 40, 4))
        img[20:, :, :3] = 1.0                                                  # top half white (row 0 = bottom)
        i = L['ca_init'](20, 20, 0, {'Seedmode': 2, 'Threshold': 0.5}, inp=img)
        self.assertEqual(i[:10].sum(), 0)
        self.assertEqual(i[10:].sum(), 200)
        self.assertEqual(L['ca_init'](10, 10, 0, {'Seedmode': 4}).sum(), 0)

    def test_step_seed_wraps_like_uint(self):
        f = 10 ** 6
        v = L['step_seed'](f, 3, 7)
        self.assertEqual(v & 0xFFFFFFFF, ((f * 8 + 3) * 7919 + 7) & 0xFFFFFFFF)
        self.assertTrue(-(1 << 31) <= v < (1 << 31))

    def test_mutate_inject(self):
        P = {'Rule': 'B3/S23', 'Mutate': 0.5, 'Seed': 1}
        out = run(np.zeros((50, 50)), 0, P, 1)
        self.assertAlmostEqual(out.mean(), 0.5, delta=0.03)
        img = np.ones((50, 50, 4))
        out = L['ca_step'](st_of(np.zeros((25, 25))), 0, {'Rule': 'B3/S23', 'Inject': 1, 'Threshold': 0.5}, inp=img)
        self.assertEqual(out[..., 0].sum(), 625)


class Value(unittest.TestCase):
    def test_state_values(self):
        st = st_of([[0, 1, 2, 3]])
        t, v = L['ca_value'](st, 1, 2)
        self.assertTrue(np.allclose(v, [[0, 1, 0.6, 0.25]]))
        t, v = L['ca_value'](st_of([[0, 1, 2]]), 0, 3)
        self.assertTrue(np.allclose(v, [[0, 1, 0.5]]))


if __name__ == '__main__':
    unittest.main()


class LiveCheckTool(unittest.TestCase):
    def test_check_ca_on_a_synthetic_dump(self):                               # the CLI path of LIVE CHECK C2
        import json
        import os
        import tempfile
        P = {'Seedmode': 0, 'Density': 0.3, 'Seed': 1}
        s = L['ca_init'](60, 40, 0, P)
        before = st_of(s).astype(np.float32)
        pars = {'Family': 'life', 'Ruleset': 'brian', 'Rule': 'B3/S23', 'Seed': 1, 'Wrap': 1, 'Decay': 0.85,
                'Mutate': 0.0, 'Inject': 0}
        after = L['ca_step'](before.astype(float), 0, dict(pars, Rule='B2/S/C3'), 77, 0)
        with tempfile.TemporaryDirectory() as d:
            np.save(os.path.join(d, 'state_fb.npy'), before)
            np.save(os.path.join(d, 'step.npy'), after.astype(np.float32))
            with open(os.path.join(d, 'uniforms.json'), 'w') as fh:
                json.dump({'step.uRun': [1, 77, 0, 0], '_pars': pars}, fh)
            r = L['check']('ca', d)
        self.assertEqual(r['state_mismatch'], 0)
