"""Offline tests for GEN_sim module 'sand' (builders/gen_sim_sand.py, glsl/gen_sim_sand_*.glsl, gen_sim_logic
sand_step). cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sim_sand.py'"""
import unittest

import numpy as np

import test_gen_sim as K

M = K.module('sand')
L = K.LOGIC


def U(over=None, W=60, H=90, frame=100):
    out = {}
    for name, ex in M['step_uniforms']():
        out[name] = [float(K.ev(e, M, over, in_w=W * 2, in_h=H * 2, frame=frame)) for e in ex]
    return out


def frames(Uu, n, st=None, inp=None, hits_at=()):
    st = L['sand_step'](np.zeros((1, 1, 4)), Uu, 0, inp) if st is None else st
    for f in range(n):
        Uu['uRun'][0] = float(f)
        if f in hits_at:
            Uu['uHit'][0] += 1
        for k in range(max(1, int(Uu['uIn'][3]))):
            st = L['sand_step'](st, Uu, k, inp)
    return st


class Uniforms(unittest.TestCase):
    def test_match_shaders(self):
        T = M['shader_texts']()
        K.check_uniforms(self, T['step'], M['step_uniforms'](), 'sand.step')
        K.check_uniforms(self, T['look'], M['look_uniforms'](), 'sand.look')

    def test_presets_full_state(self):
        keys = [set(v) for _s, _n, v in M['PRESETS']]
        self.assertTrue(all(k == keys[0] for k in keys))


class Sand(unittest.TestCase):
    def test_mass_conserved_exactly(self):
        for seed in ('pile', 'layers'):
            Uu = U({'Seedmode': seed})
            st0 = frames(Uu, 0)
            c0 = L['sand_counts'](st0)
            st = frames(Uu, 120, st0)
            c = L['sand_counts'](st)
            self.assertEqual(c['sand'], c0['sand'], seed)
            self.assertEqual(c['water'], c0['water'], seed)
            self.assertGreater(c0['sand'], 100)

    def test_sand_falls_and_piles(self):
        Uu = U({'Seedmode': 'pile'})
        st0 = frames(Uu, 0)
        st = frames(Uu, 200, st0)
        m0 = np.floor(st0[..., 0] * 3 + 0.5) == 1
        m = np.floor(st[..., 0] * 3 + 0.5) == 1
        ys = np.arange(90)[:, None]
        self.assertLess(float((m * ys).sum() / m.sum()), float((m0 * ys).sum() / m0.sum()) - 15)
        self.assertGreater(float(m[0].mean()), 0.9)                       # the floor row is full
        # a pile has a slope: columns differ in height (topple moved grains sideways but not flat as water)
        h = m.sum(0)
        self.assertGreater(int(h.max() - h.min()), 0)

    def test_water_spreads_flat(self):
        Uu = U({'Seedmode': 'empty', 'Hitmat': 'water', 'Hitsize': 8.0})
        st = frames(Uu, 1)
        st = frames(Uu, 300, st, hits_at=(0,))
        m = np.floor(st[..., 0] * 3 + 0.5)
        w = (m == 2)
        self.assertGreater(int(w.sum()), 100)
        cols = w.sum(0)
        self.assertLessEqual(int(cols.max() - cols.min()), 3)              # water level nearly flat

    def test_one_disc_per_hit(self):
        Uu = U({'Seedmode': 'empty', 'Fall': 0.0, 'Topple': 0.0, 'Flow': 0.0, 'Hitsize': 5.0})
        st = frames(Uu, 1)
        Uu['uHit'][0] = 1.0
        st1 = L['sand_step'](st, Uu, 0)
        n1 = L['sand_counts'](st1)['sand']
        self.assertTrue(60 < n1 < 100)                                     # pi 5^2 = 79 cells
        st2 = L['sand_step'](st1, Uu, 0)
        self.assertEqual(L['sand_counts'](st2)['sand'], n1)                # never replayed
        Uu['uHit'][0] = 3.0
        st3 = L['sand_step'](st2, Uu, 0)
        self.assertGreater(L['sand_counts'](st3)['sand'], n1 + 100)        # two more discs

    def test_walls_from_input_hold_sand(self):
        inp = np.zeros((180, 120, 4))
        inp[40:50, 20:100, :3] = 1.0                                       # a bright shelf (sim rows 20-24)
        Uu = U({'Seedmode': 'pile', 'Walls': True})
        st = frames(Uu, 200, None, inp)
        m = np.floor(st[..., 0] * 3 + 0.5)
        self.assertGreater(int((m[25:30, 12:48] == 1).sum()), 20)          # sand rests on the shelf
        self.assertEqual(int((m[20:25, 10:50] == 3).sum()), 5 * 40)

    def test_rgba8_round_trip(self):
        for k in range(4):
            v = round(k / 3.0 * 255) / 255.0
            self.assertEqual(int(np.floor(v * 3 + 0.5)), k)


if __name__ == '__main__':
    unittest.main()
