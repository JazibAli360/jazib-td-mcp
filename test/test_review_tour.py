"""Offline tests for builders/review_tour_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_review_tour.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import review_tour_logic as L  # noqa: E402

STAGES = [{'title': 'Controls + tests', 'ops': ['ZK_controls_kit', 'QC_mcp_checks']},
          {'title': 'Looks + effects', 'ops': ['LK_spectrum_glass', 'FX_strobe', 'SR_send_trail']},
          {'title': 'Other', 'ops': ['BX_blender_scene']}]
KIDS = ['FX_strobe', 'ZK_controls_kit', 'LK_spectrum_glass', 'QC_mcp_checks', 'BX_blender_scene', 'GN_new']
LAB = '/project1/lab/'


class Items(unittest.TestCase):
    def test_stage_order_and_other(self):
        it = L.build_items(STAGES, KIDS)
        self.assertEqual([x['name'] for x in it], ['ZK_controls_kit', 'QC_mcp_checks', 'LK_spectrum_glass',
                                                   'FX_strobe', 'BX_blender_scene', 'GN_new'])
        self.assertEqual(it[-1]['group'], 'Other')          # unboxed COMP joins the existing Other group
        self.assertNotIn('SR_send_trail', [x['name'] for x in it])   # not a child COMP

    def test_no_stages(self):
        it = L.build_items(None, ['b', 'a'])
        self.assertEqual([(x['group'], x['name']) for x in it], [('Other', 'a'), ('Other', 'b')])


class Steps(unittest.TestCase):
    def test_wrap(self):
        self.assertEqual(L.step(0, 5, -1), 4)
        self.assertEqual(L.step(4, 5, 1), 0)
        self.assertEqual(L.step(2, 0, 1), 0)
        self.assertEqual(L.clamp_index(9, 3), 2)

    def test_keys(self):
        self.assertEqual(L.key_action('left'), 'prev')
        self.assertEqual(L.key_action('down'), 'next')
        self.assertEqual(L.key_action('x', ']'), 'next')
        self.assertEqual(L.key_action('enter'), 'ctl')
        self.assertEqual(L.key_action('esc'), 'close')
        self.assertIsNone(L.key_action('q', 'q'))


class Guard(unittest.TestCase):
    def test_wake_then_park_on_leave(self):
        a, b = LAB + 'A', LAB + 'B'
        cook = {a: False, b: False}
        wake, park, owned = L.cook_plan(a, cook, [], [], [])
        self.assertEqual((wake, park, owned), ([a], [], [a]))
        cook[a] = True
        wake, park, owned = L.cook_plan(b, cook, [], owned, [])
        self.assertEqual((wake, park, owned), ([b], [a], [b]))

    def test_never_park_cooking_before(self):
        a, b = LAB + 'A', LAB + 'B'
        cook = {a: True, b: False}
        wake, park, owned = L.cook_plan(a, cook, [a], [], [])
        self.assertEqual((wake, park, owned), ([], [], []))       # already cooking: not owned
        wake, park, owned = L.cook_plan(b, cook, [a], owned, [])
        self.assertEqual((wake, park), ([b], []))

    def test_lane_and_top_level_protected(self):
        a, b = LAB + 'A', LAB + 'B'
        cook = {a: True, b: False, '/project1': True}
        wake, park, owned = L.cook_plan(b, cook, [], [a, '/project1'], [a])
        self.assertEqual(park, [])
        self.assertEqual((wake, owned), ([b], [b]))          # the lane COMP and /project1 are dropped, not parked

    def test_close_parks_all_owned(self):
        a = LAB + 'A'
        wake, park, owned = L.cook_plan(None, {a: True}, [], [a], [])
        self.assertEqual((wake, park, owned), ([], [a], []))

    def test_parked_by_someone_else(self):
        a, b = LAB + 'A', LAB + 'B'
        wake, park, owned = L.cook_plan(b, {a: False, b: True}, [], [a], [])
        self.assertEqual((park, owned), ([], []))

    def test_five_steps_exact_set(self):
        names = [LAB + n for n in 'ABCDEFG']
        before = [names[6]]
        cook = dict((n, n in before) for n in names)
        owned = []
        for k in range(5):
            wake, park, owned = L.cook_plan(names[k], cook, before, owned, [])
            for p in wake:
                cook[p] = True
            for p in park:
                cook[p] = False
            self.assertEqual(sorted(p for p, on in cook.items() if on), sorted(set(before) | {names[k]}))
        _, park, owned = L.cook_plan(None, cook, before, owned, [])
        for p in park:
            cook[p] = False
        self.assertEqual([p for p, on in cook.items() if on], before)


class Drawing(unittest.TestCase):
    def setUp(self):
        self.items = L.build_items(STAGES, KIDS)

    def test_lines_and_click(self):
        lines = L.list_lines(self.items, 2, {'FX_strobe'}, {'GN_new': False})
        kinds = [k for k, _t, _i in lines]
        self.assertEqual(kinds[:3], ['head', 'dim', 'group'])
        self.assertEqual(kinds.count('sel'), 1)
        sel = [i for i, (k, _t, _x) in enumerate(lines) if k == 'sel'][0]
        self.assertIn('LK_spectrum_glass', lines[sel][1])
        self.assertTrue(any('* FX_strobe' in t for _k, t, _i in lines))
        self.assertTrue(any('(no out)' in t for _k, t, _i in lines))
        # click in the middle of the selected row's slot maps back to it
        v = 1.0 - (L.PAD_TOP + (sel + 0.5) * L.LINE_H) / L.VIEW_H
        self.assertEqual(L.item_at(lines, v), 2)
        self.assertIsNone(L.item_at(lines, 0.999))          # header pad

    def test_spec_rows_and_bar(self):
        lines = L.list_lines(self.items, 0, set(), {})
        rows = L.spec_rows(lines, 'sel')
        self.assertEqual(len(rows), 1)
        bar = L.sel_bar(lines)
        self.assertLess(bar[1], rows[0][1])                 # text baseline sits inside the bar
        self.assertLess(rows[0][1], bar[1] + bar[3])
        cx, cy = L.bar_center((0, 0, L.LIST_W, 10))
        self.assertEqual(cx, 0.0)
        self.assertEqual(cy, 5 - L.VIEW_H / 2.0)

    def test_scrolls_long_lists(self):
        kids = ['C%02d' % i for i in range(80)]
        items = L.build_items([], kids)
        lines = L.list_lines(items, 70, set(), {})
        self.assertLessEqual(len(lines), int((L.VIEW_H - 2 * L.PAD_TOP) // L.LINE_H))
        self.assertTrue(any(k == 'sel' and 'C70' in t for k, t, _i in lines))

    def test_title(self):
        a, b = L.view_title(self.items[0], 0, 6, True, True, True)
        self.assertIn('ZK_controls_kit', a)
        self.assertIn('controls', b)
        self.assertEqual(L.view_title(None, 0, 0, False, False, False)[1], '')


if __name__ == '__main__':
    unittest.main()
