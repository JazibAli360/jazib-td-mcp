"""Offline tests for builders/timeline_logic.py (TL_timeline phase 1). No TD needed.

Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_timeline.py'
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders'))
import timeline_logic as L  # noqa: E402


class Clock(unittest.TestCase):
    def test_wrap(self):
        self.assertAlmostEqual(L.wrap(5.5, 1, 3, True), 1.5)
        self.assertAlmostEqual(L.wrap(0.5, 1, 3, True), 2.5)
        self.assertEqual(L.wrap(5.5, 1, 3, False), 3)
        self.assertEqual(L.wrap(-1, 1, 3, False), 1)
        self.assertEqual(L.wrap(2, 2, 2, True), 2)  # in == out

    def test_advance_paused(self):
        self.assertEqual(L.advance(1.0, 0.5, 1, False, True, 0, 4), (1.0, False, 0))

    def test_advance_loop_wraps(self):
        t, p, w = L.advance(3.9, 0.2, 1, True, True, 0, 4)
        self.assertAlmostEqual(t, 0.1)
        self.assertTrue(p)
        self.assertEqual(w, 1)
        t, p, w = L.advance(0.1, 0.2, -1, True, True, 0, 4)
        self.assertAlmostEqual(t, 3.9)
        self.assertEqual(w, -1)

    def test_advance_stops_without_loop(self):
        self.assertEqual(L.advance(3.9, 0.2, 1, True, False, 0, 4), (4, False, 0))
        self.assertEqual(L.advance(0.1, 0.2, -1, True, False, 0, 4), (0, False, 0))

    def test_rate_two_halves_duration(self):
        def frames_to_end(rate):
            t, p, n = 0.0, True, 0
            while p:
                t, p, _ = L.advance(t, 1 / 60.0, rate, p, False, 0, 2)
                n += 1
            return n
        self.assertEqual(frames_to_end(1), 120)
        self.assertEqual(frames_to_end(2), 60)

    def test_outside_range_enters(self):
        t, p, _ = L.advance(10.0, 0.1, 1, True, True, 0, 4)
        self.assertAlmostEqual(t, 2.1)

    def test_empty_range(self):
        self.assertEqual(L.advance(1, 0.1, 1, True, True, 2, 2), (2, False, 0))

    def test_frames(self):
        self.assertEqual(L.frame_of(1.0, 30), 30)
        self.assertEqual(L.frame_of(0.9999999, 30), 30)  # float noise
        self.assertAlmostEqual(L.step_frame(1.01, 30, 1), 31 / 30)
        self.assertAlmostEqual(L.step_frame(1.0, 30, -1), 29 / 30)
        self.assertAlmostEqual(L.quantize_frame(1.05, 30), 31 / 30)


class Timecode(unittest.TestCase):
    def test_smpte(self):
        self.assertEqual(L.format_tc(3723.5, 30, 'smpte'), '01:02:03:15')
        self.assertEqual(L.format_tc(0, 30, 'smpte'), '00:00:00:00')
        self.assertEqual(L.format_tc(-1.0, 25, 'smpte'), '-00:00:01:00')

    def test_seconds_frames(self):
        self.assertEqual(L.format_tc(61.25, 30, 'seconds'), '01:01.250')
        self.assertEqual(L.format_tc(2.0, 30, 'frames'), '60')

    def test_bars(self):
        self.assertEqual(L.format_tc(0, 30, 'bars', 120, 4), '1.1.1')
        self.assertEqual(L.format_tc(2.0, 30, 'bars', 120, 4), '2.1.1')     # 4 beats = 1 bar at 120
        self.assertEqual(L.format_tc(2.625, 30, 'bars', 120, 4), '2.2.2')   # beat 5.25
        self.assertEqual(L.bar_beat(1.5, 120, 3), (2, 1, 1))

    def test_snap(self):
        step = L.grid_step(120, 1, 30)
        self.assertAlmostEqual(step, 0.5)
        self.assertAlmostEqual(L.snap(1.26, step), 1.5)
        self.assertAlmostEqual(L.snap(1.24, L.grid_step(120, 4, 30)), 1.25)
        self.assertAlmostEqual(L.snap(0.51, L.grid_step(0, 1, 30, 'frame')), 15 / 30)
        self.assertEqual(L.snap(0.3, 0), 0.3)


class Lanes(unittest.TestCase):
    K = [(0.0, 0.0, 'linear'), (2.0, 1.0, 'ease'), (4.0, 0.0, 'hold'), (6.0, 1.0, 'bezier'), (8.0, 0.0, 'linear')]

    def test_edges(self):
        self.assertEqual(L.lane_value([], 1), 0.0)
        self.assertEqual(L.lane_value(self.K, -1), 0.0)
        self.assertEqual(L.lane_value(self.K, 9), 0.0)
        self.assertEqual(L.lane_value([(1, 5, 'linear')], 0), 5)

    def test_linear(self):
        self.assertAlmostEqual(L.lane_value(self.K, 0.5), 0.25)
        self.assertAlmostEqual(L.lane_value(self.K, 1.0), 0.5)

    def test_ease(self):
        u = 0.25
        self.assertAlmostEqual(L.lane_value(self.K, 2.5), 1 - (u * u * (3 - 2 * u)))

    def test_hold(self):
        self.assertEqual(L.lane_value(self.K, 5.9), 0.0)
        self.assertEqual(L.lane_value(self.K, 6.0), 1.0)

    def test_bezier_hermite(self):
        # segment 6..8: v0=1, v1=0, m0=(0-0)/(8-4)=0, m1=0 (end) -> smoothstep shape
        u = 0.5
        self.assertAlmostEqual(L.lane_value(self.K, 7.0), 1 - u * u * (3 - 2 * u))
        k = [(0, 0, 'bezier'), (1, 1, 'bezier'), (2, 3, 'linear')]
        # segment 0..1: m0=0 (end), m1=(3-0)/2=1.5, h=1 at u=0.5:
        exp = (-2 * .125 + 3 * .25) * 1 + (.125 - .25) * 1.5
        self.assertAlmostEqual(L.lane_value(k, 0.5), exp)

    def test_duplicate_times_jump(self):
        k = L.parse_keys([['time', 'value', 'interp'], ['1', '0', 'linear'], ['1', '5', 'linear'], ['2', '5', 'linear']])
        self.assertEqual(L.lane_value(k, 1.0), 5)
        self.assertEqual(L.lane_value(k, 0.5), 0)

    def test_parse_sorts_and_skips(self):
        k = L.parse_keys([['value', 'time', 'interp'], ['1', '2', 'ease'], ['x', '1', 'linear'], ['0', '0', 'weird']])
        self.assertEqual(k, [(0.0, 0.0, 'linear'), (2.0, 1.0, 'ease')])
        self.assertEqual(L.parse_keys([]), [])

    def test_rows_roundtrip(self):
        rows = L.keys_to_rows(self.K)
        self.assertEqual(rows[0], ['time', 'value', 'interp'])
        self.assertEqual(L.parse_keys(rows), self.K)
        self.assertEqual(L.keys_to_rows([(0.1 + 0.2, -0.0, 'hold')])[1], ['0.3', '0', 'hold'])

    def test_edit(self):
        k, i = L.add_key(self.K, 3.0, 0.5, 'linear')
        self.assertEqual(i, 2)
        self.assertEqual(len(k), 6)
        k2, i2 = L.add_key(k, 3.00001, 0.7, 'hold')  # replaces
        self.assertEqual(len(k2), 6)
        self.assertEqual(k2[i2], (3.00001, 0.7, 'hold'))
        self.assertEqual(len(L.delete_key(k2, i2)), 5)
        self.assertEqual(L.delete_key(k2, 99), k2)
        k3, i3 = L.move_key(self.K, 0, 5.0, 2.0)
        self.assertEqual(k3[i3], (5.0, 2.0, 'linear'))
        self.assertEqual(L.nearest_key(self.K, 3.1), 2)

    def test_next_prev(self):
        ts = [0, 2, 4]
        self.assertEqual(L.next_time(ts, 2), 4)
        self.assertEqual(L.prev_time(ts, 2), 0)
        self.assertIsNone(L.next_time(ts, 4))
        self.assertIsNone(L.prev_time(ts, 0))

    def test_markers(self):
        m = L.parse_markers([['time', 'name'], ['4', 'B'], ['0', 'A'], ['bad', 'x']])
        self.assertEqual(m, [(0.0, 'A'), (4.0, 'B')])
        self.assertEqual(L.marker_at(m, 3.9), 'A')
        self.assertEqual(L.marker_at(m, 4), 'B')
        self.assertEqual(L.marker_at([], 1), '')

    def test_parse_lanes(self):
        ln = L.parse_lanes([['name', 'op', 'par', 'min', 'max', 'enabled'],
                            ['level', 'demo_level', 'value0', '0', '1', '1'],
                            ['', 'x', 'y', '', '', ''],
                            ['flat', 'a', 'b', '2', '2', 'off']])
        self.assertEqual(len(ln), 2)
        self.assertEqual(ln[1]['max'], 3.0)
        self.assertFalse(ln[1]['enabled'])

    def test_sample_curve(self):
        s = L.sample_curve([(0, 0, 'linear'), (10, 2, 'linear')], 10, 3, 0, 2)
        self.assertEqual([round(x, 6) for x in s], [0, 0.5, 1])


class Ruler(unittest.TestCase):
    def test_lane_at(self):
        self.assertEqual(L.lane_at(0.95, 2), -1)
        self.assertEqual(L.lane_at(0.79, 2), 0)
        self.assertEqual(L.lane_at(0.01, 2), 1)
        self.assertIsNone(L.lane_at(-0.1, 2))
        self.assertIsNone(L.lane_at(0.5, 0))

    def test_value_roundtrip(self):
        for v in (0.0, 0.3, 1.0):
            vv = L.value_to_v(v, 1, 3, 0, 1)
            self.assertEqual(L.lane_at(vv, 3), 1)
            self.assertAlmostEqual(L.v_to_value(vv, 1, 3, 0, 1), v)

    def test_hit_key(self):
        k = [(0.0, 0.0, 'linear'), (5.0, 1.0, 'linear')]
        v = L.value_to_v(1.0, 0, 2, 0, 1)
        self.assertEqual(L.hit_key(k, 0.5 + 3 / 1000.0, v, 0, 2, 10, 0, 1, 1000, 400), 1)
        self.assertEqual(L.hit_key(k, 0.7, v, 0, 2, 10, 0, 1, 1000, 400), -1)
        self.assertAlmostEqual(L.u_to_time(1.5, 10), 10)


class PanelAnnotates(unittest.TestCase):
    """T-165: the panel's widget loop must not blank the clone of layout stage boxes (annotateCOMPs)."""

    def test_repair_and_skip(self):
        class Par:
            def __init__(self, expr):
                self.expr, self.mode = expr, 'EXPRESSION' if expr else 'CONSTANT'

            def eval(self):
                return 'annotate' if self.expr else None

        class Pars:
            def __init__(self, expr):
                self.clone = Par(expr)

        class Ann:
            def __init__(self, path, expr):
                self.path, self.par, self.inits = path, Pars(expr), 0

            def initializeExtensions(self):
                self.inits += 1

        broken, ok = Ann('/p/stage_1', ''), Ann('/p/stage_2', 'x')

        class Parent:
            def findChildren(self, type=None, maxDepth=None):
                return [broken, ok]

        class PM:
            EXPRESSION, CONSTANT = 'EXPRESSION', 'CONSTANT'
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders', 'timeline.py')
        with open(path) as fh:
            src = fh.read()
        ns = {'annotateCOMP': object, 'ParMode': PM}
        exec(compile(src, 'timeline.py', 'exec'), ns)
        self.assertEqual(ns['repair_annotates'](Parent()), ['/p/stage_1'])
        self.assertEqual((broken.par.clone.expr, broken.par.clone.mode, broken.inits),
                         (ns['ANNOTATE_CLONE'], 'EXPRESSION', 1))
        self.assertEqual(ok.inits, 0)
        loop = src[src.index('    for w in params.children:'):]
        self.assertLess(loop.index("annotateCOMP"), loop.index("w.par.clone = ''"))


if __name__ == '__main__':
    unittest.main()
