"""Offline tests for GEN_interactive module 'flowers' (builders/gen_interactive_flowers.py, _logic.py,
glsl/gen_interactive_flowers_*.glsl). cd jazib-td-mcp && python3 -I -m unittest discover -s test -p
'test_gen_interactive_flowers.py'"""
import math
import os
import unittest

import numpy as np

import test_gen_interactive as K

M = K.module('flowers')
L = {}
with open(os.path.join(K.B, 'gen_interactive_flowers_logic.py')) as _fh:
    exec(_fh.read(), L)
W, H = 270, 480
BOX = (0.3, 0.7, 0.0, 0.6)


def P(**over):
    d = L['defaults']()
    d.update(over)
    return d


def preset_pars(vals):
    p = L['defaults']()
    for k, v in vals.items():
        if k not in p and k[:-1] in p:
            c = list(p[k[:-1]])
            c['rgb'.index(k[-1])] = v
            p[k[:-1]] = tuple(c)
        else:
            p[k] = v
    return p


def living(st):
    rows = st.shape[0] - 1
    A = st[:rows, 0::2].reshape(-1, 4)
    B = st[:rows, 1::2].reshape(-1, 4)
    return A[A[:, 3] > 0], B[A[:, 3] > 0]


class Defaults(unittest.TestCase):
    def test_logic_defaults_match_pages(self):
        pd = K.RACK['page_defaults'](M['PAGES'])
        d = L['defaults']()
        for k, v in pd.items():
            if k == 'Resetcount':
                continue
            if k not in d and k[:-1] in d:
                self.assertAlmostEqual(d[k[:-1]]['rgb'.index(k[-1])], v, msg=k)
            else:
                self.assertEqual(d[k], v, k)


class State(unittest.TestCase):
    def test_fresh_hold_and_freeze(self):
        mask = L['synthetic_mask'](box=(0, 1, 0, 1))
        p = P(Count=64, Spawnrate=30.0)
        st = L['state_step'](None, mask, [], 100.0, p, W=W, H=H)
        self.assertEqual(st.shape, (2, 128, 4))
        self.assertEqual(len(living(st)[0]), 0)                       # dt 0 on a fresh state: no births
        self.assertEqual(list(st[1, 0]), [1.0, 0.0, 100.0, 1.0])
        self.assertTrue(np.array_equal(L['state_step'](st, mask, [], 100.0, p, W=W, H=H), st))   # same frame
        st, _ = L['run'](p, 30, lambda k: mask, W=W, H=H)
        n = len(living(st)[0])
        self.assertGreater(n, 20)
        fz = L['state_step'](st, mask, [], 200.0, dict(p, Speed=0.0), W=W, H=H)
        self.assertTrue(np.array_equal(fz[:1], st[:1]))                # Speed 0: nothing changes but the clock
        self.assertEqual(fz[1, 0, 1], st[1, 0, 1])
        rs = L['state_step'](st, mask, [], 200.0, p, epoch=2.0, W=W, H=H)
        self.assertEqual(len(living(rs)[0]), 0)                       # new epoch: all empty

    def test_spawn_only_where_present(self):
        mask = L['synthetic_mask'](box=BOX)
        st, _ = L['run'](P(Count=128, Spawnrate=4.0), 60, lambda k: mask, W=W, H=H)
        A, _B = living(st)
        self.assertGreater(len(A), 30)
        mh, mw = mask.shape[:2]
        for x, y in A[:, :2]:
            self.assertEqual(mask[min(int(y / H * mh), mh - 1), min(int(x / W * mw), mw - 1), 0], 1.0)

    def test_stillness_blooms_more(self):
        p = P(Count=256, Spawnrate=2.0, Scatterthresh=0.15, Stillness=1.0)
        still, _ = L['run'](p, 40, lambda k: L['synthetic_mask'](box=BOX, motion=0.0), W=W, H=H)
        moving, _ = L['run'](p, 40, lambda k: L['synthetic_mask'](box=BOX, motion=0.12), W=W, H=H)
        a, b = len(living(still)[0]), len(living(moving)[0])
        self.assertGreater(a, 2.5 * b)                                # still^1 = 0.2: ~1/5 of the births
        self.assertGreater(b, 0)

    def test_scatter_on_motion_then_empty(self):
        p = P(Count=64, Spawnrate=6.0, Falltime=0.5, Bloomtime=0.2)
        quiet = L['synthetic_mask'](box=BOX)
        loud = L['synthetic_mask'](box=BOX, motion=1.0)
        st, _ = L['run'](p, 30, lambda k: quiet, W=W, H=H)
        n0 = len(living(st)[0])
        self.assertGreater(n0, 10)
        now = 100.0 + 30 / 60.0
        st = L['state_step'](st, loud, [], now, p, W=W, H=H)
        _A, B = living(st)
        self.assertTrue((B[:, 2] >= 0).all())                         # every flower scattering
        for k in range(1, 40):
            st = L['state_step'](st, loud, [], now + k / 60.0, p, W=W, H=H)
        self.assertEqual(len(living(st)[0]), 0)                       # gone after Falltime, none reborn (not still)

    def test_life_cycle_timing(self):
        p = P(Count=1, Spawnrate=1000.0, Lifevar=0.0, Life=2.0, Falltime=0.5)
        mask = L['synthetic_mask'](box=(0, 1, 0, 1))
        st = None
        born = died = None
        for k in range(240):
            st = L['state_step'](st, mask, [], 100.0 + k / 60.0, p, W=W, H=H)
            on = st[0, 0, 3] > 0
            if on and born is None:
                born = st[1, 0, 1]
            if born is not None and not on and died is None:
                died = st[1, 0, 1]
        self.assertIsNotNone(died)
        self.assertAlmostEqual(died - born, 2.5, delta=1.5 / 60.0)

    def test_near_points(self):
        p = P(Count=64, Spawnrate=6.0, Nearshare=1.0, Spawnnear=20.0)
        empty = L['synthetic_mask'](box=(0, 0, 0, 0))                 # no presence anywhere
        st, _ = L['run'](p, 30, lambda k: empty, lambda k: [(0.5, 0.5, 0.0, 0.0)], W=W, H=H)
        A, _B = living(st)
        self.assertGreater(len(A), 10)
        self.assertLessEqual(np.abs(A[:, 0] - 0.5 * W).max(), 20.0 + 1e-9)
        self.assertLessEqual(np.abs(A[:, 1] - 0.5 * H).max(), 20.0 + 1e-9)
        st2, _ = L['run'](dict(p, Nearshare=0.0), 30, lambda k: empty, lambda k: [(0.5, 0.5, 0.0, 0.0)], W=W, H=H)
        self.assertEqual(len(living(st2)[0]), 0)

    def test_waterfall_mode_has_no_flowers(self):
        st, _ = L['run'](P(Count=64, Spawnrate=30.0, Mode=1), 10, lambda k: L['synthetic_mask'](box=(0, 1, 0, 1)),
                         W=W, H=H)
        self.assertEqual(len(living(st)[0]), 0)


class Water(unittest.TestCase):
    def test_free_fall(self):
        p = P(Mode=1, Drops=64, Topspread=0.0, Dropvar=0.0, Gravity=0.0, Fallspeed=600.0)
        none = L['synthetic_mask'](box=(0, 0, 0, 0))
        _s, wa = L['run'](p, 10, lambda k: none, W=W, H=H, water=True)
        A = wa[0, 0::2]
        self.assertTrue(np.allclose(A[:, 2], 0.0))
        self.assertTrue(np.allclose(A[:, 3], -600.0))
        self.assertTrue(np.allclose(A[:, 1], H - 600.0 * 9 / 60.0))   # 9 steps after the spawn
        _s, w0 = L['run'](P(Mode=0, Drops=64), 3, lambda k: none, W=W, H=H, water=True)
        self.assertEqual(w0[0, 1::2, 2].sum(), 0.0)                   # Mode flowers: no drops

    def test_parts_around_a_person(self):
        p = P(Mode=1, Drops=512, Topspread=1.0, Fallspeed=500.0, Gravity=600.0, Part=4000.0)
        box = (0.35, 0.65, 0.0, 0.5)
        person = L['synthetic_mask'](box=box)
        none = L['synthetic_mask'](box=(0, 0, 0, 0))
        def inside(wa):
            A, B = wa[:-1, 0::2].reshape(-1, 4), wa[:-1, 1::2].reshape(-1, 4)
            ok = B[:, 2] > 0.5
            x, y = A[ok, 0] / W, A[ok, 1] / H
            core = (x > box[0] + 0.05) & (x < box[1] - 0.05) & (y < box[3] - 0.08)
            return int(core.sum()), np.abs(A[ok, 2]).max(), B[ok, 0].max()

        def sample(mask):
            wa, n, vx, sp = None, 0, 0.0, 0.0
            for k in range(150):
                wa = L['water_step'](wa, mask, 100.0 + k / 60.0, p, W=W, H=H)
                if k >= 100:
                    a, b, c = inside(wa)
                    n, vx, sp = n + a, max(vx, b), max(sp, c)
            return n, vx, sp

        n_p, vx_p, splash = sample(person)
        n_n, vx_n, _ = sample(none)
        self.assertGreater(n_n, 200)
        self.assertLess(n_p, 0.25 * n_n)                              # water parts around the body
        self.assertGreater(vx_p, 50.0)                                # pushed sideways
        self.assertEqual(vx_n, 0.0)
        self.assertGreater(splash, 0.0)


class Draw(unittest.TestCase):
    def _one(self, **over):
        p = P(Count=1, Lifevar=0.0, Life=30.0, Bloomtime=1.0, Species=2, Size=40.0, Sizevar=0.0, **over)
        st = np.zeros((2, 128, 4))
        st[0, 0] = [135.0, 240.0, 0.0, 30.0]                          # x y birth life
        st[0, 1] = [0.25, 40.0, -1.0, 1.0]                            # seed size scatter species (blossom)
        st[1, 0] = [10, 5.0, 100.0, 1.0]                              # T = 5 s: fully open
        return p, st

    def test_open_flower_area_and_centre(self):
        p, st = self._one()
        its = L['items'](st, None, p)
        self.assertEqual(len(its), 1)
        g = its[0][1]
        self.assertAlmostEqual(g['open'], 1.0)
        self.assertAlmostEqual(g['Lp'], 40.0)
        ys, xs = np.mgrid[180:300, 75:195]
        col, a = L['shade_grid'](xs + 0.5, ys + 0.5, its, p)
        area = float(a.sum())
        self.assertGreater(area, 0.15 * math.pi * 40 ** 2)
        self.assertLess(area, math.pi * 41 ** 2)
        self.assertTrue(np.allclose(col[60, 60], p['Centrecolor'], atol=1e-6))   # pixel (135, 240): the centre
        self.assertEqual(float(a[0, 0]), 0.0)

    def test_scatter_moves_petals_down(self):
        p, st = self._one(Scatterspeed=50.0, Petalgravity=400.0, Falltime=3.0)
        st[0, 1, 2] = 4.0                                             # scattering since T 4 (ts 1 s)
        ys, xs = np.mgrid[0:480:2, 0:270:2]
        _c, a = L['shade_grid'](xs + 0.5, ys + 0.5, L['items'](st, None, p), p)
        cy = float((a * (ys + 0.5)).sum() / a.sum())
        self.assertLess(cy, 240.0 - 100.0)                            # fell ~0.5 g ts^2 = 200 px minus kick
        st[1, 0, 1] = 8.0                                             # ts 4 > Falltime: gone
        self.assertEqual(L['items'](st, None, p), [])

    def test_every_preset_draws(self):
        mask = L['synthetic_mask'](box=BOX)
        for slot, name, vals in M['PRESETS']:
            p = preset_pars(vals)
            p['Count'] = min(int(p['Count']), 128)
            p['Drops'] = min(int(p['Drops']), 256)
            p['Spawnrate'] = max(p['Spawnrate'], 2.0)
            st, wa = L['run'](p, 60, lambda k: mask, W=W, H=H, water=True)
            its = L['items'](st, wa, p)
            self.assertGreater(len(its), 5, name)
            ys, xs = np.mgrid[0:480:6, 0:270:6]
            _c, a = L['shade_grid'](xs + 0.5, ys + 0.5, its, p)
            self.assertGreater(float(a.sum()), 2.0, name)


class Shader(unittest.TestCase):
    def test_uniform_lists(self):
        tx = M['shader_texts']()
        K.check_uniforms(self, tx['state'], M['state_uniforms'](), 'state')
        K.check_uniforms(self, tx['water'], M['water_uniforms'](), 'water')
        K.check_uniforms(self, tx['fx'], M['draw_uniforms'](), 'fx')

    def test_sizes(self):
        self.assertEqual(K.ev(M['STATE_H'], M), (400 + 63) // 64 + 1)
        self.assertEqual(K.ev(M['WATER_H'], M), (1200 + 63) // 64 + 1)
        self.assertEqual(K.ev(M['STATE_H'], M, {'Count': 64}), 2)
        self.assertLess(K.shared_bytes(M['shader_texts']()['fx']), 24576)   # per-item geometry cache (live, b4); Metal 32 KB

    def test_species_tables_match(self):
        t = M['shader_texts']()['fx']
        for name in ('SPN', 'SPA', 'SPB', 'SPW'):
            line = [ln for ln in t.splitlines() if ln.startswith('const float %s[6]' % name)][0]
            vals = [float(v) for v in line.split('(', 1)[1].rstrip(');').split(',')]
            self.assertEqual(vals, [float(v) for v in L[name]], name)


if __name__ == '__main__':
    unittest.main()
