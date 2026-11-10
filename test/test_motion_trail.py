"""Offline tests for builders/motion_trail_logic.py (no TD).
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_motion_trail.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders'))
import motion_trail_logic as L  # noqa: E402

W, G, K = (1.0, 1.0, 1.0), (0.5, 0.5, 0.5), (0.0, 0.0, 0.0)


class TestLength(unittest.TestCase):
    def test_frames(self):
        self.assertEqual(L.length_frames(30), 30.0)
        self.assertAlmostEqual(L.step(30), 1 / 30.0)

    def test_min_one_frame(self):
        self.assertEqual(L.length_frames(0), 1.0)
        self.assertEqual(L.step(-5), 1.0)

    def test_beats(self):
        self.assertAlmostEqual(L.length_frames(0, 'beats', 1, 120, 60), 30.0)
        self.assertAlmostEqual(L.length_frames(0, 'beats', 2, 128, 60), 56.25)

    def test_no_upper_cap(self):
        self.assertEqual(L.length_frames(1000), 1000.0)


class TestGammaAndSizes(unittest.TestCase):
    def test_gamma(self):
        self.assertAlmostEqual(L.gamma(0), 0.25)
        self.assertAlmostEqual(L.gamma(0.5), 1.0)
        self.assertAlmostEqual(L.gamma(1), 4.0)

    def test_work_size(self):
        self.assertEqual(L.work_size(1920, 1080, 'full'), (1920, 1080))
        self.assertEqual(L.work_size(1920, 1080, 'half'), (960, 540))
        self.assertEqual(L.work_size(1080, 1920, 'quarter'), (270, 480))
        self.assertEqual(L.work_size(3, 3, 'quarter'), (2, 2))

    def test_menus(self):
        self.assertEqual(L.menu_index(L.AGECOLOR, 'white'), 1)
        self.assertEqual(L.menu_index(L.BLEND, 'nope', 0), 0)


class TestControl(unittest.TestCase):
    def test_mix_audio(self):
        self.assertEqual(L.mix_amount(0.8), 0.8)
        self.assertAlmostEqual(L.mix_amount(0.8, 1.0, 0.25), 0.2)
        self.assertAlmostEqual(L.mix_amount(0.8, 0.5, 0.0), 0.4)

    def test_reset(self):
        self.assertEqual(L.reset_now(100, 99), 1)
        self.assertEqual(L.reset_now(100, 90, 5.0), 0)
        self.assertEqual(L.reset_now(100, 90, 0.5), 1)
        self.assertEqual(L.reset_now(100, 90, 0.5, reset_on_loop=False), 0)
        self.assertEqual(L.reset_now(100, 90, 0.5, source='input'), 0)


class TestTrailModel(unittest.TestCase):
    def test_mask(self):
        self.assertEqual(L.mask(0.05, 0.1, 0.05), 0.0)
        self.assertEqual(L.mask(0.2, 0.1, 0.05), 1.0)
        self.assertAlmostEqual(L.mask(0.125, 0.1, 0.05), 0.5)

    def test_lives_exactly_length_frames(self):
        age, col = L.trail_update(0.0, K, 1.0, W, 0.1, 0.05, L.step(10))
        self.assertEqual(age, 1.0)
        n = 0
        while age > 1e-9:
            age, col = L.trail_update(age, col, 0.0, K, 0.1, 0.05, L.step(10))
            n += 1
        self.assertEqual(n, 10)
        self.assertEqual(col, W)  # colour captured at the motion frame is kept

    def test_static_scene_stays_empty(self):
        age = 0.0
        for _ in range(50):
            age, _c = L.trail_update(age, K, 0.04, G, 0.1, 0.05, 0.1)
        self.assertEqual(age, 0.0)

    def test_hold_and_reset(self):
        self.assertEqual(L.trail_update(0.6, W, 0.0, K, 0.1, 0.05, 0.1, hold=True)[0], 0.6)
        self.assertEqual(L.trail_update(0.6, W, 1.0, W, 0.1, 0.05, 0.1, reset=True), (0.0, K))

    def test_fresher_wins(self):
        age, col = L.trail_update(0.9, W, 0.125, G, 0.1, 0.05, 0.1)  # mask 0.5 < aged 0.8
        self.assertAlmostEqual(age, 0.8)
        self.assertEqual(col, W)


class TestShade(unittest.TestCase):
    def test_ramp_ends(self):
        self.assertEqual(L.ramp(1.0, W, G, K), W)
        self.assertEqual(L.ramp(0.5, W, G, K), G)
        self.assertEqual(L.ramp(0.0, W, G, K), K)

    def test_over_and_trail_only(self):
        src = (0.2, 0.2, 0.2, 1.0)
        self.assertEqual(L.shade(src, 0.0, K, 'ramp', 'over', 1.0, 1.0, W, G, K), src)
        o = L.shade(src, 1.0, K, 'white', 'over', 1.0, 1.0, W, G, K)
        self.assertEqual(o, (1.0, 1.0, 1.0, 1.0))
        t = L.shade(src, 0.5, K, 'white', 'trail', 1.0, 1.0, W, G, K)
        self.assertEqual(t, (0.5, 0.5, 0.5, 0.5))  # premultiplied

    def test_gamma_fades(self):
        lin = L.shade((0, 0, 0, 1), 0.5, K, 'white', 'trail', 1.0, L.gamma(0.5), W, G, K)[3]
        fast = L.shade((0, 0, 0, 1), 0.5, K, 'white', 'trail', 1.0, L.gamma(1.0), W, G, K)[3]
        self.assertAlmostEqual(lin, 0.5)
        self.assertAlmostEqual(fast, 0.0625)

    def test_add_screen_source(self):
        src = (0.5, 0.5, 0.5, 1.0)
        self.assertEqual(L.shade(src, 1.0, (0.2, 0.0, 0.0), 'source', 'add', 1.0, 1.0, W, G, K)[:3], (0.7, 0.5, 0.5))
        s = L.shade(src, 1.0, K, 'white', 'screen', 1.0, 1.0, W, G, K)
        self.assertEqual(s[:3], (1.0, 1.0, 1.0))


import palette_map_logic as PL  # noqa: E402


class TestPaletteAndRainbow(unittest.TestCase):
    def test_menu_order_kept(self):
        self.assertEqual([m[0] for m in L.AGECOLOR], ['ramp', 'white', 'source', 'palette', 'rainbow'])

    def test_palette_pos(self):
        self.assertEqual(L.palette_pos(1.0), 0.0)        # newest -> first colour
        self.assertEqual(L.palette_pos(0.0), 1.0)        # oldest -> last colour (clamped, no wrap)
        self.assertAlmostEqual(L.palette_pos(0.75, 2.0), 0.5)
        self.assertAlmostEqual(L.palette_pos(1.0, 1.0, 0.25), 0.25)
        self.assertAlmostEqual(L.palette_pos(0.0, 1.0, 0.25), 0.25)   # cycling wraps

    def test_cycle_phase(self):
        self.assertAlmostEqual(L.cycle_phase(2.5, 0.5), 0.25)
        self.assertAlmostEqual(L.cycle_phase(1.0, -0.25), 0.75)
        self.assertEqual(L.cycle_phase(9.0, 0.0), 0.0)

    def test_palette_color(self):
        cols = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        self.assertEqual(L.palette_color(0.0, cols), (1.0, 0.0, 0.0))
        self.assertEqual(L.palette_color(1.0, cols), (0.0, 0.0, 1.0))
        self.assertEqual(L.palette_color(0.25, cols), (0.5, 0.5, 0.0))
        self.assertEqual(L.palette_color(0.5, cols, smooth=False), (0.0, 1.0, 0.0))
        self.assertEqual(L.palette_color(0.99, cols, smooth=False), (0.0, 0.0, 1.0))
        self.assertEqual(L.palette_color(0.3, [(0.2, 0.3, 0.4)]), (0.2, 0.3, 0.4))
        self.assertEqual(L.palette_color(0.3, []), (0.0, 0.0, 0.0))

    def test_preset_through_shade(self):
        pal = [PL.hex_to_rgb(h) for h in PL.preset('gameboy')]
        o = L.shade((0, 0, 0, 1), 1.0, K, 'palette', 'trail', 1.0, 1.0, W, G, K, pal=pal)
        self.assertEqual(o[:3], pal[0])
        o = L.shade((0, 0, 0, 1), 0.5, K, 'palette', 'trail', 1.0, 1.0, W, G, K, pal=pal, smooth=False)
        self.assertEqual(o[:3], tuple(v * 0.5 for v in pal[2]))   # pos 0.5 of 4 bands -> index 2, premultiplied

    def test_hue(self):
        self.assertEqual(L.hue_rgb(0.0), (1.0, 0.0, 0.0))
        self.assertEqual(L.hue_rgb(1.0 / 6.0), (1.0, 1.0, 0.0))
        g = L.hue_rgb(1.0 / 3.0)
        self.assertAlmostEqual(g[1], 1.0)
        self.assertAlmostEqual(g[0] + g[2], 0.0)

    def test_rainbow_shade(self):
        o = L.shade((0, 0, 0, 1), 1.0, K, 'rainbow', 'trail', 1.0, 1.0, W, G, K)
        self.assertEqual(o, (1.0, 0.0, 0.0, 1.0))     # newest = red at phase 0
        o = L.shade((0, 0, 0, 1), 1.0, K, 'rainbow', 'trail', 1.0, 1.0, W, G, K, phase=1.0 / 6.0)
        self.assertEqual(o[:3], (1.0, 1.0, 0.0))      # time shifts the hue


if __name__ == '__main__':
    unittest.main()
