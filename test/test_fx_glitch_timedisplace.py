"""Offline tests for FX_glitch module 'timedisplace' (builders/fx_glitch_timedisplace.py, fx_time_ring.py,
fx_time_logic.py). No TD. Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_timedisplace.py'"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import fx_time_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = K.load_module('timedisplace')


def P(**over):
    d = L.td_defaults()
    d.update(over)
    return d


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'timedisplace')
        self.assertEqual(pars['Mode'][2]['names'], L.TD_MODES)
        for k in L.td_defaults():
            self.assertIn(k, pars, k)
        K.check_uniforms(self, NS['uniforms'](), NS['MAP'], pars)

    def test_rules(self):
        for f in ('fx_glitch_timedisplace.py', 'fx_time_ring.py', 'fx_time_logic.py'):
            K.check_td_rules(self, K.source(f))

    def test_ring_exprs_parse(self):
        import ast
        for e in (NS['DEPTH'], NS['HALF'], NS['SCALE']) + NS['map_size_exprs'](NS['SCALE']):
            ast.parse(e, mode='eval')


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_map(self):
        ok, err = K.glslc(NS['MAP'])
        self.assertTrue(ok, err)

    def test_stamp(self):
        ok, err = K.glslc(NS['STAMP_RING'])
        self.assertTrue(ok, err)


class Map(unittest.TestCase):
    W, H = 54, 96                                   # 1080x1920 / 20

    def test_ramp_angle0_bottom_now_top_oldest(self):
        off = L.td_offsets(P(), self.W, self.H)
        rows = (np.arange(self.H) + 0.5) / self.H * 31.0
        self.assertTrue(np.allclose(off, rows[:, None]))
        self.assertTrue(np.all(np.diff(off[:, 0]) > 0))

    def test_ramp_angle90_columns(self):
        off = L.td_offsets(P(Angle=90.0), self.W, self.H)
        self.assertTrue(np.allclose(off, ((np.arange(self.W) + 0.5) / self.W * 31.0)[None, :]))

    def test_full_res_numbers_for_live_check(self):
        off = L.td_offsets(P(), 1080, 1920)          # doc: row 0 = 0.0081, row 960 = 15.508, row 1919 = 30.992
        self.assertAlmostEqual(off[0, 0], 31 * 0.5 / 1920, 6)
        self.assertAlmostEqual(off[960, 0], 31 * 960.5 / 1920, 6)
        self.assertAlmostEqual(off[1919, 500], 31 * 1919.5 / 1920, 6)

    def test_radial_zero_at_centre_max_at_corner(self):
        off = L.td_offsets(P(Mode=1), 1080, 1920)
        self.assertLess(off[960, 540], 0.03)
        self.assertGreater(off[0, 0], 30.9)

    def test_spiral_in_range(self):
        off = L.td_offsets(P(Mode=2, Twist=1.5), self.W, self.H)
        self.assertGreaterEqual(off.min(), 0.0)
        self.assertLessEqual(off.max(), 31.0)

    def test_luma_and_curve(self):
        lu = np.full((self.H, self.W), 0.25)
        self.assertTrue(np.allclose(L.td_offsets(P(Mode=3), self.W, self.H, luma=lu), 7.75))
        self.assertTrue(np.allclose(L.td_offsets(P(Mode=3, Curve=0.5), self.W, self.H, luma=lu), 15.5))

    def test_noise_deterministic_and_bounded(self):
        a = L.td_offsets(P(Mode=4), self.W, self.H, t=1.0)
        b = L.td_offsets(P(Mode=4), self.W, self.H, t=1.0)
        c = L.td_offsets(P(Mode=4, Seed=2), self.W, self.H, t=1.0)
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.allclose(a, c))
        self.assertGreater(a.std(), 1.0)
        self.assertTrue(0.0 <= a.min() and a.max() <= 31.0)

    def test_steps_make_bands(self):
        off = L.td_offsets(P(Steps=4), self.W, self.H)
        self.assertEqual(sorted(set(np.round(off.ravel(), 6))), [0.0, round(31 / 3, 6), round(62 / 3, 6), 31.0])

    def test_invert_amount_delay(self):
        a = L.td_offsets(P(), self.W, self.H)
        self.assertTrue(np.allclose(L.td_offsets(P(Invert=1), self.W, self.H), 31.0 - a))
        self.assertTrue(np.allclose(L.td_offsets(P(Amount=0.5), self.W, self.H), a / 2))
        d = L.td_offsets(P(Amount=0.5, Delay=10.0), self.W, self.H)
        self.assertTrue(np.allclose(d, np.minimum(a / 2 + 10.0, 31.0)))

    def test_clamped_to_ring_fill(self):
        off = L.td_offsets(P(), self.W, self.H, n=5)
        self.assertAlmostEqual(off.max(), 5.0)
        self.assertTrue(np.all(L.td_offsets(P(), self.W, self.H, n=0) == 0.0))

    def test_repeat_saw_and_mirror(self):
        saw = L.td_offsets(P(Repeat=2.0), self.W, self.H)
        self.assertGreater(np.abs(np.diff(saw[:, 0])).max(), 25.0)      # one hard reset in the middle
        tri = L.td_offsets(P(Repeat=2.0, Mirror=1), self.W, self.H)
        self.assertLess(np.abs(np.diff(tri[:, 0])).max(), 1.5)          # continuous
        self.assertTrue(np.allclose(L.td_offsets(P(Mirror=1), self.W, self.H), L.td_offsets(P(), self.W, self.H)))

    def test_phase_scrolls(self):
        a = L.td_offsets(P(Phase=0.5), self.W, self.H, t=0.0)
        b = L.td_offsets(P(Phase=0.5), self.W, self.H, t=1.0)          # half a cycle later
        self.assertFalse(np.allclose(a, b))
        c = L.td_offsets(P(Phase=0.5), self.W, self.H, t=2.0)          # a whole cycle: back
        self.assertTrue(np.allclose(a, c, atol=1e-6))

    def test_jitter_rows(self):
        off = L.td_offsets(P(Jitter=0.5, Jittersize=8.0), self.W, 1920 // 20, pic_h=1920)
        self.assertTrue(np.allclose(off, off[:, :1]))                   # rows only
        self.assertFalse(np.allclose(off, L.td_offsets(P(), self.W, self.H)))

    def test_smooth_mixes_previous(self):
        prev = np.zeros((self.H, self.W))
        a = L.td_offsets(P(Smooth=0.75), self.W, self.H, prev_off=prev)
        self.assertTrue(np.allclose(a, L.td_offsets(P(), self.W, self.H) * 0.25))


class Ring(unittest.TestCase):
    def test_depth_key_vram(self):
        self.assertEqual(L.ring_depth(1), 2)
        self.assertNotEqual(L.ring_key(32, 'full'), L.ring_key(32, 'half'))
        self.assertNotEqual(L.ring_key(32, 'full'), L.ring_key(33, 'full'))
        self.assertAlmostEqual(L.vram_mb(1080, 1920, 32), 265.42, 2)
        self.assertAlmostEqual(L.vram_mb(1080, 1920, 32, 'half'), 66.36, 2)
        self.assertAlmostEqual(L.vram_mb(1080, 1920, 120), 995.33, 2)

    def test_encode(self):
        self.assertEqual(L.encode(0, 32), 1.0 - 1.0 / 32)    # T-122: Time Machine reads (1-m)*D - 1 slices
        self.assertEqual(L.encode(31, 32), 0.0)
        self.assertEqual(L.encode(16, 32), 1.0 - 17.0 / 32)

    def test_timemachine_ref_and_frame_code(self):
        ring = [np.full((2, 2), (100 - i) / 255.0) for i in range(32)]   # code of frame f = f/255
        off = np.array([[0.0, 1.0], [2.5, 31.0]])
        out = L.ref_timemachine(ring, off)
        got = L.decode_frame_code(np.full((2, 2), 100 / 255.0), out)
        self.assertTrue(np.allclose(got, [[0, 1], [2, 31]]) or np.allclose(got, [[0, 1], [3, 31]]))
        self.assertTrue(np.allclose(L.decode_frame_code(np.full(1, 2 / 255.0), np.full(1, 250 / 255.0)), 8))


class Hash(unittest.TestCase):
    def test_np_matches_scalar(self):
        a = np.arange(-5, 50)
        v = L.np_h(a, 7, 3, 9)
        for i, x in enumerate(a.tolist()):
            self.assertAlmostEqual(float(v[i]), L.h(x, 7, 3, 9), 6)

    def test_known_value(self):
        self.assertEqual(L.pcg(0), 129708002)            # pins the hash (= the GLSL pcg)
        self.assertTrue(0.0 <= L.h(1, 2, 3, 4) <= 1.0)


if __name__ == '__main__':
    unittest.main()
