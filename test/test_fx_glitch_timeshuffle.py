"""Offline tests for FX_glitch module 'timeshuffle' (builders/fx_glitch_timeshuffle.py, fx_time_ring.py,
fx_time_logic.py). No TD. Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_timeshuffle.py'"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import fx_time_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = K.load_module('timeshuffle')
W, H = 108, 192                                     # 1080x1920 / 10


def P(**over):
    d = L.ts_defaults()
    d.update(over)
    return d


def blocks_constant(off, bs):
    for y0 in range(0, off.shape[0], bs):
        for x0 in range(0, off.shape[1], bs):
            b = off[y0:y0 + bs, x0:x0 + bs]
            if not np.all(b == b.flat[0]):
                return False
    return True


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'timeshuffle')
        self.assertEqual(pars['Mode'][2]['names'], L.TS_MODES)
        self.assertEqual(pars['Shape'][2]['names'], L.TS_SHAPES)
        for k in L.ts_defaults():
            self.assertIn(k, pars, k)
        K.check_uniforms(self, NS['uniforms'](), NS['MAP'], pars)

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_timeshuffle.py'))

    def test_reverse_preset_fits_ring(self):
        for _s, name, v in NS['PRESETS']:
            if v['Mode'] == 2:
                self.assertGreaterEqual(v['Depth'], 2 * v['Length'] - 1, name)
            if v['Mode'] == 1:
                self.assertGreaterEqual(v['Depth'], 2 * v['Length'], name)


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_map(self):
        ok, err = K.glslc(NS['MAP'])
        self.assertTrue(ok, err)


class Perm(unittest.TestCase):
    def test_bijection(self):
        rnd = random.Random(7)
        for Ln in list(range(1, 70)) + [100, 120, 128, 129]:
            for _ in range(4):
                key = rnd.getrandbits(32)
                self.assertEqual(sorted(L.perm(i, Ln, key) for i in range(Ln)), list(range(Ln)), (Ln, key))

    def test_not_identity(self):
        moved = sum(L.perm(i, 16, L.pcg(3)) != i for i in range(16))
        self.assertGreater(moved, 8)


class Modes(unittest.TestCase):
    def test_random_blocks(self):
        off = L.ts_offsets(P(Blocksize=16.0), W, H)
        self.assertTrue(blocks_constant(off, 16))
        self.assertEqual(off.min(), 0.0)
        self.assertEqual(off.max(), 15.0)
        self.assertTrue(np.all(off == np.floor(off)))
        self.assertGreater(len(set(off.ravel().tolist())), 12)

    def test_random_new_draw_per_epoch(self):
        a = L.ts_offsets(P(Blocksize=16.0, Rate=4.0), W, H, t=0.0)
        b = L.ts_offsets(P(Blocksize=16.0, Rate=4.0), W, H, t=0.2)    # same epoch (floor(0.8) = 0)
        c = L.ts_offsets(P(Blocksize=16.0, Rate=4.0), W, H, t=0.3)    # next epoch
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))

    def test_chance_and_amount(self):
        self.assertTrue(np.all(L.ts_offsets(P(Chance=0.0), W, H) == 0))
        self.assertTrue(np.all(L.ts_offsets(P(Amount=0.0), W, H) == 0))
        full = (L.ts_offsets(P(Blocksize=8.0, Length=60, Depth=64), W, H) > 0).mean()
        half = (L.ts_offsets(P(Blocksize=8.0, Length=60, Depth=64, Chance=0.5), W, H) > 0).mean()
        self.assertGreater(full, 0.95)
        self.assertTrue(0.38 < half < 0.62, half)

    def test_hold_and_reverse_whole_frame(self):
        for n in range(0, 40):
            hold = L.ts_offsets(P(Mode=3, Length=8), W, H, n=n)
            rev = L.ts_offsets(P(Mode=2, Length=8), W, H, n=n)
            self.assertTrue(np.all(hold == min(n % 8, n)))
            self.assertTrue(np.all(rev == min(2 * (n % 8), n, 31)))

    def test_hold_shows_chunk_start_frame(self):
        shown = [n - L.ts_offsets(P(Mode=3, Length=8), 8, 8, n=n)[0, 0] for n in range(8, 24)]
        self.assertEqual(shown, [8] * 8 + [16] * 8)

    def test_reverse_plays_backwards(self):
        shown = [n - L.ts_offsets(P(Mode=2, Length=8), 8, 8, n=n)[0, 0] for n in range(16, 24)]
        self.assertEqual(shown, list(range(16, 8, -1)))

    def test_permute_plays_previous_chunk_shuffled(self):
        for seed in (1, 2, 3):
            shown = [n - L.ts_offsets(P(Mode=1, Length=8, Seed=seed), 8, 8, n=n)[0, 0] for n in range(16, 24)]
            self.assertEqual(sorted(shown), list(range(8, 16)), seed)
            self.assertNotEqual(shown, list(range(8, 16)))

    def test_perblock_staggers(self):
        off = L.ts_offsets(P(Mode=3, Length=8, Blocksize=16.0, Perblock=1), W, H, n=100)
        self.assertTrue(blocks_constant(off, 16))
        self.assertGreater(len(set(off.ravel().tolist())), 4)

    def test_rows_and_columns(self):
        rows = L.ts_offsets(P(Shape=1, Blocksize=12.0), W, H)
        self.assertTrue(np.all(rows == rows[:, :1]))
        cols = L.ts_offsets(P(Shape=2, Blocksize=12.0), W, H)
        self.assertTrue(np.all(cols == cols[:1, :]))

    def test_wave_steps_up_the_picture(self):
        off = L.ts_offsets(P(Mode=5, Shape=1, Blocksize=12.0, Length=16), W, H)
        col = off[:, 0]
        self.assertTrue(np.all(np.diff(col) >= 0))                    # angle 0: bottom now, top late
        self.assertEqual(col[0], 0.0)
        self.assertEqual(col[-1], 15.0)

    def test_luma_lag(self):
        lu = np.tile(np.linspace(0, 1, W), (H, 1))
        off = L.ts_offsets(P(Mode=4, Blocksize=12.0, Length=9), W, H, picture_luma=lu)
        self.assertTrue(np.all(np.diff(off[0]) >= 0))
        inv = L.ts_offsets(P(Mode=4, Blocksize=12.0, Length=9, Invert=1), W, H, picture_luma=lu)
        self.assertTrue(np.all(np.diff(inv[0]) <= 0))

    def test_clamp_to_ring(self):
        self.assertTrue(np.all(L.ts_offsets(P(Length=60, Depth=32), W, H) <= 31))
        self.assertTrue(np.all(L.ts_offsets(P(Length=60), W, H, n=3) <= 3))
        self.assertTrue(np.all(L.ts_offsets(P(), W, H, n=0) == 0))

    def test_gridshift_moves_grid(self):
        a = L.ts_offsets(P(Blocksize=16.0), W, H, t=0.0)
        b = L.ts_offsets(P(Blocksize=16.0, Gridshift=1.0), W, H, t=0.0)
        self.assertFalse(np.array_equal(a, b))


CAD = {}
exec(NS['CADENCE_PY'] % (NS['BANK'],), CAD)


class Cadence(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(CAD['parse']('p4 h4 r4 b1 p3', 8), [(0, 4), (1, 4), (2, 4), (4, 1), (0, 3)])
        self.assertEqual(CAD['parse']('p, hx w2 q9 v', 5), [(0, 5), (1, 5), (5, 2), (3, 5)])
        self.assertEqual(CAD['parse']('', 5), [(0, 1)])
        self.assertEqual(len(CAD['parse']('p1 ' * 30, 1)), 16)

    def test_bank_patterns_parse(self):
        for name, pat in NS['BANK']:
            st = CAD['parse'](pat, 4)
            self.assertTrue(all(0 <= c <= 5 for c, _n in st), name)

    def test_uniform_vector(self):
        class Par:
            def __init__(s, v, mi=0): s.v, s.menuIndex = v, mi
            def eval(s): return s.v
        class M: pass
        m = M(); m.par = M(); m.par.Pattern = Par('p2 h3 b1'); m.par.Length = Par(4); m.par.Cadence = Par('custom', 0)
        u = CAD['U'](m)
        self.assertEqual(len(u), 34)
        self.assertEqual(u[:3], [0.0, 1.0, 4.0]); self.assertEqual(u[16:19], [2.0, 3.0, 1.0])
        self.assertEqual(u[32:], [6.0, 3.0])
        m.par.Cadence = Par('strobe', 2)
        self.assertEqual(CAD['pattern'](m), dict(NS['BANK'])['strobe'])

    def test_cadence_frames(self):
        st = CAD['parse']('p4 h4 r4 b1 v3', 4)
        fr = L.cadence_frames(st, 96, 16, 32)                           # 96 % 16 = 0: cycle start
        shown = [f for f, _k in fr]
        self.assertEqual(shown[:4], [96, 97, 98, 99])                   # play
        self.assertEqual(shown[4:8], [100, 100, 100, 100])              # hold the step's first frame
        self.assertEqual(shown[8:12], [100, 101, 102, 103])             # repeat the previous step (4 back)
        self.assertEqual(fr[12], (None, 0.0))                           # fill frame
        self.assertEqual(shown[13:16], [109, 108, 107])                 # reverse

    def test_ring_clamp(self):
        st = CAD['parse']('p4 r4', 4)
        fr = L.cadence_frames(st, 4, 4, 32)                             # repeat at n 4..7 wants 4 back, n caps it
        self.assertEqual([f for f, _k in fr], [0, 1, 2, 3])
        fr = L.cadence_frames(st, 4, 4, 3)                              # depth 3: at most 2 back
        self.assertEqual([f for f, _k in fr], [2, 3, 4, 5])

    def test_cad_pass_and_switch(self):
        src = K.source('fx_glitch_timeshuffle.py')
        self.assertIn("(2 if parent().par.Mode.eval() == 'cadence'", src)
        self.assertIn("sw.inputConnectors[2].connect(cf)", src)


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class CompileCad(unittest.TestCase):
    def test_cad(self):
        ok, err = K.glslc(NS['CAD_FX'])
        self.assertTrue(ok, err)


if __name__ == '__main__':
    unittest.main()
