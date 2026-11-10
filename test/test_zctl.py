"""Offline tests for builders/zctl_logic.py (stdlib only, no TD)."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'builders'))
import zctl_logic as Z  # noqa: E402


class Mapping(unittest.TestCase):
    def test_normalize_roundtrip(self):
        for v in (-2.0, 0.0, 3.3, 8.0):
            u = Z.normalize(v, -2, 8)
            self.assertAlmostEqual(Z.denormalize(u, -2, 8), v)

    def test_normalize_clamps_and_flat_range(self):
        self.assertEqual(Z.normalize(20, 0, 10), 1.0)
        self.assertEqual(Z.normalize(-5, 0, 10), 0.0)
        self.assertEqual(Z.normalize(3, 2, 2), 0.0)

    def test_kinds(self):
        self.assertEqual(Z.to_target(0.5, 0, 10, 'int'), 5)
        self.assertIs(Z.to_target(0.49, 0, 1, 'toggle'), False)
        self.assertIs(Z.to_target(0.5, 0, 1, 'toggle'), True)
        self.assertEqual(Z.to_target(1.0, 0, 0, 'menu', 4), 3)
        self.assertEqual(Z.to_target(0.4, 0, 0, 'menu', 4), 1)
        self.assertEqual(Z.to_target(0.7, 0, 0, 'menu', 1), 0)
        self.assertAlmostEqual(Z.from_target(2, 0, 0, 'menu', 5), 0.5)
        self.assertEqual(Z.from_target(True, 0, 1, 'toggle'), 1.0)
        self.assertAlmostEqual(Z.to_target(0.25, 1, 5, 'float'), 2.0)

    def test_menu_roundtrip(self):
        for i in range(6):
            self.assertEqual(Z.to_target(Z.from_target(i, 0, 0, 'menu', 6), 0, 0, 'menu', 6), i)

    def test_midi(self):
        self.assertEqual(Z.cc_to_unit(127), 1.0)
        self.assertEqual(Z.unit_to_cc(0.5), 64)
        self.assertEqual(Z.unit_to_cc(Z.cc_to_unit(37)), 37)


class Curves(unittest.TestCase):
    def test_ends_and_mid(self):
        for c in Z.CURVES:
            self.assertAlmostEqual(Z.curve(0, c), 0.0)
            self.assertAlmostEqual(Z.curve(1, c), 1.0)
            self.assertAlmostEqual(Z.curve(0.5, c), 0.5)
        self.assertAlmostEqual(Z.curve(0.25, 'linear'), 0.25)
        self.assertLess(Z.curve(0.25, 'ease'), 0.25)
        self.assertLess(Z.curve(0.25, 'smooth'), Z.curve(0.25, 'ease'))

    def test_clamped(self):
        self.assertEqual(Z.curve(-1), 0.0)
        self.assertEqual(Z.curve(3, 'ease'), 1.0)

    def test_morph_dict(self):
        m = Z.morph({'a': 0.0, 'b': 1.0, 'only_a': 0.3}, {'a': 1.0, 'b': 0.0, 'only_b': 0.9}, 0.5)
        self.assertAlmostEqual(m['a'], 0.5)
        self.assertAlmostEqual(m['b'], 0.5)
        self.assertEqual(m['only_a'], 0.3)
        self.assertEqual(m['only_b'], 0.9)


class MorphRun(unittest.TestCase):
    def test_linear_timing(self):
        m = Z.Morph({'Knob1': 0.0}, {'Knob1': 1.0}, 2.0, 'linear', t0=10.0)
        self.assertAlmostEqual(m.step(10.0)[0]['Knob1'], 0.0)
        v, done = m.step(11.0)
        self.assertAlmostEqual(v['Knob1'], 0.5)
        self.assertFalse(done)
        v, done = m.step(12.2)
        self.assertEqual(v['Knob1'], 1.0)
        self.assertTrue(done)

    def test_zero_time_jumps(self):
        v, done = Z.Morph({'K': 0.2}, {'K': 0.8}, 0, t0=5).step(5)
        self.assertEqual(v['K'], 0.8)
        self.assertTrue(done)

    def test_touched_knob_drops_out(self):
        m = Z.Morph({'A': 0.0, 'B': 0.0}, {'A': 1.0, 'B': 1.0}, 1.0, t0=0)
        v, _ = m.step(0.25, {'A': 0.0, 'B': 0.0})
        v, _ = m.step(0.5, {'A': v['A'], 'B': 0.9})  # B moved by hand
        self.assertIn('A', v)
        self.assertNotIn('B', v)
        v, done = m.step(1.0, {'A': v['A'], 'B': 0.9})
        self.assertEqual(v, {'A': 1.0})
        self.assertTrue(done)


class Randomize(unittest.TestCase):
    vals = {'Knob1': 0.2, 'Knob2': 0.7, 'Knob3': 0.5}

    def test_amount_zero_unchanged(self):
        self.assertEqual(Z.randomize(self.vals, 0, random.Random(1)), self.vals)

    def test_amount_one_in_range_and_moves(self):
        out = Z.randomize(self.vals, 1, random.Random(2))
        self.assertTrue(all(0.0 <= v <= 1.0 for v in out.values()))
        self.assertNotEqual(out, self.vals)

    def test_locks_and_stable_draws(self):
        a = Z.randomize(self.vals, 1, random.Random(3))
        b = Z.randomize(self.vals, 1, random.Random(3), {'Knob2': True})
        self.assertEqual(b['Knob2'], 0.7)
        self.assertEqual(a['Knob1'], b['Knob1'])
        self.assertEqual(a['Knob3'], b['Knob3'])

    def test_half_amount_bounded(self):
        out = Z.randomize(self.vals, 0.5, random.Random(4))
        for k, v in out.items():
            self.assertLessEqual(abs(v - self.vals[k]), 0.5 + 1e-9)


class Data(unittest.TestCase):
    def test_preset_roundtrip(self):
        d = {'Knob2': 0.25, 'Knob1': 0.123456789}
        back = Z.preset_loads(Z.preset_dumps(d))
        self.assertEqual(set(back), set(d))
        self.assertAlmostEqual(back['Knob1'], 0.123457)
        self.assertEqual(Z.preset_loads(''), {})
        with self.assertRaises(ValueError):
            Z.preset_loads('[1,2]')

    def test_rows(self):
        items = [{'id': '1', 'knob': 'Knob1', 'path': '/a', 'par': 'tx'}]
        rows = Z.dicts_to_rows(items, Z.BIND_COLS)
        self.assertEqual(rows[0], Z.BIND_COLS)
        back = Z.rows_to_dicts(rows)
        self.assertEqual(back[0]['par'], 'tx')
        self.assertEqual(back[0]['lock'], '')
        self.assertEqual(Z.rows_to_dicts([]), [])

    def test_ids_and_names(self):
        self.assertEqual(Z.next_id([]), 1)
        self.assertEqual(Z.next_id(['1', '4', 'x']), 5)
        self.assertEqual(Z.knob_name(3), 'Knob3')
        self.assertEqual(Z.split_names('tx, ty  period'), ['tx', 'ty', 'period'])
        self.assertEqual(Z.split_names(None), [])

    def test_ctrl_target(self):
        binds = [{'knob': 'Knob1', 'src': ''}, {'knob': 'Knob2', 'src': 'ch1c21'}]
        self.assertEqual(Z.ctrl_target('Knob1', binds), 'Knob1')
        self.assertEqual(Z.ctrl_target('ch1c21', binds), 'Knob2')
        self.assertEqual(Z.ctrl_target('k2', binds), 'Knob2')
        self.assertEqual(Z.ctrl_target('1', binds), 'Knob1')
        self.assertIsNone(Z.ctrl_target('k9', binds))
        self.assertIsNone(Z.ctrl_target('chan1', binds))


if __name__ == '__main__':
    unittest.main()
