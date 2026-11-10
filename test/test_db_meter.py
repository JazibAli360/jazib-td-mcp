"""Offline tests for builders/db_meter_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_db_meter.py'"""
import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import db_meter_logic as L  # noqa: E402


class AmpDb(unittest.TestCase):
    def test_values(self):
        self.assertEqual(L.amp_to_db(0, -60), -60)
        self.assertAlmostEqual(L.amp_to_db(1.0), 0.0, places=9)
        self.assertAlmostEqual(L.amp_to_db(0.5), -6.0206, places=3)
        self.assertAlmostEqual(L.amp_to_db(0.1), -20.0, places=9)
        self.assertAlmostEqual(L.amp_to_db(0.01), -40.0, places=9)
        self.assertEqual(L.amp_to_db(1e-5, -60), -60)  # clamp
        self.assertAlmostEqual(L.amp_to_db(-0.5), -6.0206, places=3)

    def test_frac_roundtrip(self):
        for db in (-60, -18, -6, 0, 3, -33.3):
            f = L.db_to_frac(db, -60, 3)
            self.assertAlmostEqual(L.frac_to_db(f, -60, 3), db, places=9)
        self.assertEqual(L.db_to_frac(-90, -60, 3), 0.0)
        self.assertEqual(L.db_to_frac(9, -60, 3), 1.0)
        self.assertAlmostEqual(L.db_to_frac(0, -60, 3), 60 / 63.0)


class Labels(unittest.TestCase):
    def test_default_rows(self):
        rows = L.label_rows(-60, 3, 6)
        self.assertEqual(rows, [3, 0, -6, -12, -18, -24, -30, -36, -42, -48, -54, -60])
        self.assertEqual([L.label_text(r) for r in rows[:3]], ['3', '0', '-6'])

    def test_min_gap(self):
        rows = L.label_rows(-60, 1, 1)  # 1 dB grid over 61 dB: too dense, thinned
        fr = [L.db_to_frac(r, -60, 1) for r in rows]
        for a, b in zip(fr, fr[1:]):
            self.assertGreaterEqual(a - b, 1 / 30.0 - 1e-9)
        self.assertNotIn(1, rows)  # ceil 1 dB is too close to 0: 0 wins
        self.assertIn(0, rows)
        self.assertEqual(rows[1] - rows[2], 3.0)  # 1 dB grid widened to 3 dB

    def test_off_grid_ceil_and_floor(self):
        rows = L.label_rows(-50, 4.5, 12)
        self.assertEqual(rows[0], 4.5)
        self.assertIn(0, rows)
        self.assertIn(-50, rows)
        self.assertEqual(L.label_text(4.5), '4.5')

    def test_empty(self):
        self.assertEqual(L.label_rows(3, -60, 6), [])


class Geometry(unittest.TestCase):
    def test_vertical(self):
        g = L.geometry(256, 1024, 'vertical', 4, 0.4, True)
        self.assertEqual((g['L'], g['C']), (1024, 256))
        self.assertTrue(0 < g['a0'] < g['a1'] < g['l0'] < g['l1'] <= g['L'])
        self.assertTrue(0 < g['b0'] < g['b1'] < g['s0'] < g['s1'] == g['C'])
        self.assertAlmostEqual(2 * g['bw'] + g['gap'], g['b1'] - g['b0'])

    def test_horizontal_and_hidden_scale(self):
        g = L.geometry(1024, 200, 'horizontal', 6, 0.4, False)
        self.assertEqual((g['L'], g['C'], g['vert']), (1024, 200, 0.0))
        self.assertEqual(g['s0'], g['s1'])

    def test_axis_pos_alignment(self):
        g = L.geometry(256, 1024)
        self.assertEqual(L.axis_pos(-60, g, -60, 3), g['a0'])
        self.assertEqual(L.axis_pos(3, g, -60, 3), g['a1'])
        mid = L.axis_pos(0, g, -60, 3)
        self.assertAlmostEqual(mid, g['a0'] + 60 / 63.0 * (g['a1'] - g['a0']))

    def test_font(self):
        g = L.geometry(256, 1024)
        self.assertEqual(L.auto_font_px(g, 14), 14)
        self.assertGreaterEqual(L.auto_font_px(L.geometry(32, 128)), 6)


class Blocks(unittest.TestCase):
    def test_sine(self):
        n, sr, f = 4410, 44100.0, 441.0  # exactly 44.1 cycles... use whole cycles: 441 Hz over 4410 samples = 44.1
        s = [math.sin(2 * math.pi * f * i / sr) for i in range(4400)]  # 44 whole cycles
        self.assertAlmostEqual(L.block_peak(s), 1.0, places=3)
        self.assertAlmostEqual(L.amp_to_db(L.block_rms(s)), -3.0103, places=3)
        self.assertEqual(L.block_peak([]), 0.0)
        self.assertEqual(n, 4410)


class Ballistics(unittest.TestCase):
    def test_instant_rise_linear_fall(self):
        c = L.ballistics_step(None, -20, 0.1, 0, 24)
        self.assertEqual(c, -20)
        c = L.ballistics_step(-20, 0, 0.1, 0, 24)
        self.assertEqual(c, 0)
        c = L.ballistics_step(0, -60, 0.5, 0, 24)
        self.assertAlmostEqual(c, -12)
        c = L.ballistics_step(-12, -60, 10, 0, 24)
        self.assertEqual(c, -60)

    def test_attack_closed_form(self):
        tau, dt, cur = 0.3, 1 / 60.0, -60.0
        for k in range(1, 61):
            cur = L.ballistics_step(cur, 0.0, dt, tau, 24)
            self.assertAlmostEqual(cur, -60.0 * math.exp(-k * dt / tau), places=9)


class PeakHoldT(unittest.TestCase):
    def test_hold_then_fall(self):
        ph = L.PeakHold(hold=1.5, release=24)
        self.assertEqual(ph.update(0.0, 0.0), 0.0)
        self.assertEqual(ph.update(-60, 1.0), 0.0)
        self.assertEqual(ph.update(-60, 1.5), 0.0)
        self.assertAlmostEqual(ph.update(-60, 2.0), -12.0)
        self.assertAlmostEqual(ph.update(-60, 2.5), -24.0)
        self.assertAlmostEqual(ph.update(-30, 3.0), -30.0)  # level catches the falling line -> re-armed
        ph.reset()
        self.assertEqual(ph.update(-40, 4.0), -40)

    def test_zero_release_holds(self):
        st, shown = L.peak_hold_step(None, -3, 0, 1, 0)
        st, shown = L.peak_hold_step(st, -50, 100, 1, 0)
        self.assertEqual(shown, -3)


class Clip(unittest.TestCase):
    def test_clip_hold(self):
        cu, lamp = L.clip_step(None, -1, 0, 0, 1.5)
        self.assertEqual(lamp, 0)
        cu, lamp = L.clip_step(cu, 1.58, 1, 0, 1.5)
        self.assertEqual(lamp, 1)
        cu, lamp = L.clip_step(cu, -20, 2.4, 0, 1.5)
        self.assertEqual(lamp, 1)
        cu, lamp = L.clip_step(cu, -20, 2.6, 0, 1.5)
        self.assertEqual(lamp, 0)


class MeterStep(unittest.TestCase):
    P = {'floor': -60.0, 'ceil': 3.0, 'attack': 0.0, 'release': 24.0, 'hold': 1.5, 'clipdb': 0.0}

    def test_frame_and_storable(self):
        import json
        st, o = L.meter_step(None, 0.0, -200.0, 0.0, self.P)
        self.assertEqual((o['l'], o['r'], o['lpeak'], o['rpeak']), (0.0, -60.0, 0.0, -60.0))
        self.assertEqual((o['lclip'], o['rclip']), (1, 0))
        json.dumps(st)  # plain data only (T-67)
        st, o = L.meter_step(st, -200.0, -200.0, 0.5, self.P)
        self.assertAlmostEqual(o['l'], -12.0)
        self.assertEqual(o['lpeak'], 0.0)
        st, o = L.meter_step(st, 1.58, -200, 1.0, self.P)
        self.assertEqual(o['l'], 3.0 if 1.58 > 3 else 1.58)
        self.assertEqual(o['lclip'], 1)

    def test_clock_back_resets(self):
        st, o = L.meter_step(None, 0.0, 0.0, 100.0, self.P)
        st, o = L.meter_step(st, -200.0, -200.0, 1.0, self.P)  # time went backwards
        self.assertEqual((o['l'], o['lpeak'], o['lclip']), (-60.0, -60.0, 0))


class AsciiOnly(unittest.TestCase):
    def test_ascii(self):
        p = os.path.join(os.path.dirname(HERE), 'builders')
        for n in ('db_meter_logic.py', 'db_meter.py'):
            fp = os.path.join(p, n)
            if os.path.exists(fp):
                with open(fp, 'rb') as f:
                    f.read().decode('ascii')

    def test_shader_contract(self):
        # the builder's shader reads geometry by these keys; they must exist in geometry()
        fp = os.path.join(os.path.dirname(HERE), 'builders', 'db_meter.py')
        if not os.path.exists(fp):
            self.skipTest('builder not written')
        with open(fp) as f:
            txt = f.read()
        keys = set(re.findall(r"geo\('([a-z0-9]+)'\)", txt))
        g = L.geometry(256, 1024)
        self.assertTrue(keys, 'builder references no geometry keys')
        for k in keys:
            self.assertIn(k, g)


if __name__ == '__main__':
    unittest.main()
