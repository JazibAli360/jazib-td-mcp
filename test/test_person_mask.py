"""Offline tests for builders/person_mask_logic.py and the builder text (no TD).
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_person_mask.py'"""
import ast
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'builders'))
import person_mask_logic as L  # noqa: E402

BUILDER = os.path.join(HERE, '..', 'builders', 'person_mask.py')


class TestSizes(unittest.TestCase):
    def test_half_is_960x540_fast_path(self):
        self.assertEqual(L.vision_size(1920, 1080, 'half'), (960, 540))

    def test_fixed_long_side(self):
        self.assertEqual(L.vision_size(1280, 720, 'fixed'), (960, 540))
        self.assertEqual(L.vision_size(1080, 1920, 'fixed'), (540, 960))

    def test_full_quarter_even_min(self):
        self.assertEqual(L.vision_size(1920, 1080, 'full'), (1920, 1080))
        self.assertEqual(L.vision_size(1920, 1080, 'quarter'), (480, 270))
        self.assertEqual(L.vision_size(10, 10, 'quarter'), (16, 16))


class TestEdge(unittest.TestCase):
    def test_zero_is_raw_mask(self):
        self.assertEqual(L.edge_params(0, 0), (0.0, 0.0, 1.0))
        for b in (0.0, 0.3, 0.77, 1.0):
            self.assertAlmostEqual(L.remap(b, 0.0, 1.0), b)

    def test_grow_moves_centre_down_choke_up(self):
        _, lo_g, hi_g = L.edge_params(2, 6)
        _, lo_c, hi_c = L.edge_params(2, -6)
        self.assertLess((lo_g + hi_g) / 2, 0.5)
        self.assertGreater((lo_c + hi_c) / 2, 0.5)

    def test_feather_widens_ramp(self):
        s1, lo1, hi1 = L.edge_params(1, 0)
        s8, lo8, hi8 = L.edge_params(8, 0)
        self.assertEqual((s1, s8), (2.0, 16.0))
        self.assertAlmostEqual(hi1 - lo1, 1.0)   # pure feather: blur does the softening, remap stays linear
        self.assertAlmostEqual(hi8 - lo8, 1.0)

    def test_pure_grow_is_hard_but_bounded(self):
        s, lo, hi = L.edge_params(0, 10)
        self.assertEqual(s, 20.0)
        self.assertAlmostEqual(hi - lo, 0.02)
        self.assertGreaterEqual(lo, 0.0)

    def test_no_upper_limit(self):
        s, lo, hi = L.edge_params(200, 500)
        self.assertEqual(s, 1400.0)
        self.assertLess(lo, hi)


class TestTemporalCacheComposite(unittest.TestCase):
    def test_temporal_step_response(self):
        m = 0.0
        out = []
        for _ in range(3):
            m = L.temporal(1.0, m, 0.7)
            out.append(round(m, 4))
        self.assertEqual(out, [0.3, 0.51, 0.657])   # live: 0.298 0.5098 0.6549 (8-bit view)

    def test_cache_index(self):
        self.assertEqual(L.cache_index(3), -3)
        self.assertEqual(L.cache_index(None), 0)
        self.assertEqual(L.cache_index(99), -(L.CACHE_SIZE - 1))
        self.assertEqual(L.cache_index(-2), 0)

    def test_composite_premultiplied(self):
        r = L.composite((0.8, 0.4, 0.2), 0.5)
        self.assertEqual(r, (0.4, 0.2, 0.1, 0.5))
        for c in r[:3]:
            self.assertLessEqual(c, r[3])

    def test_fill_and_bg_colour(self):
        r = L.composite((0.8, 0.4, 0.2), 1.0, person='fill', fill=(1, 0, 0.5))
        self.assertEqual(r, (1, 0, 0.5, 1.0))
        r = L.composite((0.8, 0.4, 0.2), 0.0, background='color', bgcolor=(0, 0, 1, 1))
        self.assertEqual(r, (0, 0, 1, 1))

    def test_bg_input_premultiplied_passthrough(self):
        r = L.composite((1, 1, 1), 0.25, background='input', bg=(0.2, 0.2, 0.2, 0.5))
        self.assertAlmostEqual(r[3], 0.25 + 0.5 * 0.75)

    def test_coverage(self):
        self.assertEqual(L.coverage([0, 0.6, 1, 0.4]), 0.5)
        self.assertEqual(L.coverage([]), 0.0)

    def test_menu_index(self):
        self.assertEqual(L.menu_index(L.RGBDELAY, 'none'), 2)
        self.assertEqual(L.menu_index(L.BACKGROUND, 'input'), 2)


class TestBuilderText(unittest.TestCase):
    def setUp(self):
        self.src = open(BUILDER).read()

    def test_ascii_and_parses(self):
        self.src.encode('ascii')
        ast.parse(self.src)

    def test_absolute_plugin_path_only(self):
        self.assertTrue(L.PLUGIN.startswith('/'))
        self.assertNotIn('Derivative/TouchDesigner099/Plugins', self.src)

    def test_never_unloads_plugin(self):
        # T-106: unload/reload cycles segfaulted the scratch TD; off = bypass only
        tree = ast.parse(self.src)
        fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'set_vision'][0]
        body = ast.get_source_segment(self.src, fn)
        self.assertNotIn('unloadplugin.pulse', body)
        self.assertIn('bypass = True', body)

    def test_render_select_bufferindex_1(self):
        self.assertIn('rgbp.par.bufferindex = 1', self.src)

    def test_compute_mode_and_three_inputs_max(self):
        self.assertIn("g.par.mode = 'compute'", self.src)
        self.assertNotIn('sTD2DInputs[3]', self.src)   # GLSL TOP: 3 connectors (T-84/T-88)


if __name__ == '__main__':
    unittest.main()
