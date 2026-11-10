"""Offline tests for td/midi_core.py (stdlib only)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'td'))
import midi_core as M  # noqa: E402

ALL_CURVES = list(M.CURVES) + ['steps:4']


def mp(**kw):
    kw.setdefault('id', 'a')
    return M.new_mapping(**kw)


def cc(n, v, ch=1):
    return M.parse_event('cc', ch, n, v)


class Mapping(unittest.TestCase):
    def test_defaults_and_fields(self):
        m = M.new_mapping()
        self.assertEqual(list(M.FIELDS), list(M.DEFAULTS))
        self.assertEqual(set(m), set(M.FIELDS))
        self.assertAlmostEqual(m['step'], 1 / 127)

    def test_unknown_key(self):
        with self.assertRaises(KeyError):
            M.new_mapping(bogus=1)

    def test_coercion(self):
        m = mp(channel='3', min='2', invert='1')
        self.assertEqual((m['channel'], m['min'], m['invert']), (3, 2.0, True))

    def test_valid(self):
        self.assertEqual(M.validate(mp(target='/a', par='Size')), [])
        self.assertEqual(M.validate(mp(kind='cc14', number=31)), [])
        self.assertEqual(M.validate(mp(kind='aftertouch', number=-1)), [])
        self.assertEqual(M.validate(mp(curve='steps:2')), [])

    def test_errors(self):
        cases = [
            (dict(id=''), 'id'), (dict(kind='sysex'), 'kind'), (dict(channel=17), 'channel'),
            (dict(number=128), 'number'), (dict(kind='cc14', number=32), 'number'), (dict(min=1.0, max=1.0), 'min'),
            (dict(curve='wobble'), 'curve'), (dict(curve='steps:1'), 'curve'), (dict(mode='spin'), 'mode'),
            (dict(kind='note', mode='relative_2c'), 'relative'), (dict(takeover='grab'), 'takeover'),
            (dict(smooth=-1.0), 'smooth'), (dict(step=0.0), 'step'), (dict(bank=-1), 'bank'),
        ]
        for kw, word in cases:
            errs = M.validate(mp(**kw))
            self.assertTrue(errs and any(word in e for e in errs), (kw, errs))

    def test_type_and_unknown_errors(self):
        m = mp()
        m['min'] = 'x'
        m['zzz'] = 1
        errs = M.validate(m)
        self.assertTrue(any('min' in e for e in errs) and any('zzz' in e for e in errs))
        m = mp()
        del m['par']
        self.assertTrue(any('missing' in e for e in M.validate(m)))
        m = mp()
        m['invert'] = 1
        self.assertTrue(M.validate(m))


class Events(unittest.TestCase):
    def test_cc_note(self):
        e = cc(7, 127)
        self.assertEqual((e['kind'], e['value'], e['raw']), ('cc', 1.0, 127))
        n = M.parse_event('noteon', 2, 60, 64)
        self.assertTrue(n['on'])
        self.assertEqual(n['kind'], 'note')
        off = M.parse_event('noteoff', 2, 60, 64)
        self.assertFalse(off['on'])
        self.assertEqual(off['value'], 0.0)

    def test_cc14_pitchbend_program_aftertouch(self):
        self.assertEqual(M.parse_event('cc14', 1, 1, 127, 127)['raw'], 16383)
        self.assertEqual(M.parse_event('cc14', 1, 1, 8192)['value'], 8192 / 16383)
        pb = M.parse_event('pitchbend', 1, 99, 0, 64)  # LSB, MSB
        self.assertEqual((pb['raw'], pb['number']), (8192, 0))
        self.assertEqual(M.parse_event('pitchbend', 1, 0, -8192)['raw'], 0)
        self.assertEqual(M.parse_event('program', 1, 5, 0)['raw'], 5)
        self.assertEqual(M.parse_event('aftertouch', 1, None, 64)['number'], -1)
        with self.assertRaises(ValueError):
            M.parse_event('sysex', 1, 0, 0)

    def test_midiin_rows(self):
        e = M.parse_midiin_row({'message': 'Control Change', 'channel': '3', 'index': '21', 'value': '64'})
        self.assertEqual((e['kind'], e['channel'], e['number'], e['raw']), ('cc', 3, 21, 64))
        e = M.parse_midiin_row({'Type': 'note_on', 'Channel': '1', 'Note': '60', 'Velocity': '100'})
        self.assertEqual((e['kind'], e['number'], e['on']), ('note', 60, True))
        e = M.parse_midiin_row({'message': 'Note Off', 'channel': '1', 'index': '60', 'value': '64'})
        self.assertFalse(e['on'])
        e = M.parse_midiin_row({'message': 'Pitch Bend', 'channel': '1', 'index': '0', 'value': '16383'})
        self.assertEqual(e['raw'], 16383)
        e = M.parse_midiin_row({'message': 'pitchbend', 'channel': '1', 'value': '64'})
        self.assertEqual(e['raw'], 8192)
        e = M.parse_midiin_row({'message': 'Channel Pressure', 'channel': '1', 'index': '0', 'value': '10'})
        self.assertEqual((e['kind'], e['number']), ('aftertouch', -1))
        e = M.parse_midiin_row({'message': 'Program Change', 'channel': '1', 'index': '7', 'value': ''})
        self.assertEqual((e['kind'], e['number']), ('program', 7))
        self.assertIsNone(M.parse_midiin_row({'message': 'SysEx', 'value': 'F0'}))
        self.assertIsNone(M.parse_midiin_row({}))
        e = M.parse_midiin_row({'message': 'cc', 'channel': '', 'index': '1.0', 'value': 'junk'})
        self.assertEqual((e['channel'], e['number'], e['raw']), (1, 1, 0))


class Joiner(unittest.TestCase):
    def test_msb_then_lsb(self):
        j = M.Cc14Joiner()
        self.assertIsNone(j.feed(1, 1, 64))
        self.assertEqual(j.feed(1, 33, 1), (1, 64 * 128 + 1))
        self.assertEqual(j.feed(1, 33, 5), (1, 64 * 128 + 5))  # fine-only change
        self.assertIsNone(j.feed(1, 1, 65))
        self.assertEqual(j.feed(1, 33, 0), (1, 65 * 128))

    def test_lsb_first(self):
        j = M.Cc14Joiner()
        self.assertIsNone(j.feed(1, 34, 3))
        self.assertEqual(j.feed(1, 2, 10), (2, 10 * 128 + 3))
        self.assertIsNone(j.feed(1, 34, 4))
        self.assertEqual(j.feed(1, 2, 11), (2, 11 * 128 + 4))

    def test_separate_keys_and_filter(self):
        j = M.Cc14Joiner(numbers=[1])
        self.assertFalse(j.wants(2))
        self.assertFalse(j.wants(34))
        self.assertTrue(j.wants(33))
        self.assertFalse(j.wants(70))
        self.assertIsNone(j.feed(1, 1, 1))
        self.assertIsNone(j.feed(2, 33, 9))  # other channel, lsb held
        self.assertEqual(j.feed(1, 33, 2), (1, 130))
        ev = j.feed_event(cc(1, 127, ch=2))
        self.assertEqual((ev['kind'], ev['channel'], ev['raw']), ('cc14', 2, 127 * 128 + 9))
        j.reset()
        self.assertIsNone(j.feed(1, 33, 2))


class Matching(unittest.TestCase):
    def test_bank_kind_channel_number(self):
        m = mp(kind='cc', channel=0, number=7, bank=2)
        self.assertTrue(M.matches(m, cc(7, 1, ch=5), 2))
        self.assertFalse(M.matches(m, cc(7, 1), 1))
        self.assertFalse(M.matches(m, cc(8, 1), 2))
        self.assertFalse(M.matches(m, M.parse_event('note', 1, 7, 1), 2))
        m0 = mp(number=7, bank=0, channel=3)
        self.assertTrue(M.matches(m0, cc(7, 1, ch=3), 9))
        self.assertFalse(M.matches(m0, cc(7, 1, ch=4), 9))

    def test_pitchbend_aftertouch(self):
        self.assertTrue(M.matches(mp(kind='pitchbend', number=0), M.parse_event('pitchbend', 1, 0, 0), 1))
        self.assertTrue(M.matches(mp(kind='program'), M.parse_event('program', 1, 9, 0), 1))
        at = mp(kind='aftertouch', number=-1)
        self.assertTrue(M.matches(at, M.parse_event('aftertouch', 1, None, 3), 1))
        self.assertFalse(M.matches(at, M.parse_event('aftertouch', 1, 60, 3), 1))

    def test_bank_helpers(self):
        ms = [mp(id='a', bank=0), mp(id='b', bank=1), mp(id='c', bank=2)]
        self.assertEqual([m['id'] for m in M.select_bank(ms, 2)], ['a', 'c'])
        self.assertEqual(M.banks_in(ms), [1, 2])
        self.assertEqual(M.next_id(ms, 'm'), 'm1')
        self.assertEqual(M.next_id([mp(id='m1')], 'm'), 'm2')

    def test_retarget(self):
        ms = [mp(target='/project1/fx'), mp(target='/project1/fx/sub'), mp(target='/project1/fxx')]
        self.assertEqual(M.retarget(ms, '/project1/fx', '/show/fx'), 2)
        self.assertEqual([m['target'] for m in ms], ['/show/fx', '/show/fx/sub', '/project1/fxx'])


class Curves(unittest.TestCase):
    def test_endpoints_monotonic_inverse(self):
        xs = [i / 1000 for i in range(1001)]
        for c in ALL_CURVES:
            ys = [M.apply_curve(x, c) for x in xs]
            self.assertAlmostEqual(ys[0], 0.0, places=9, msg=c)
            self.assertAlmostEqual(ys[-1], 1.0, places=9, msg=c)
            for a, b in zip(ys, ys[1:]):
                self.assertLessEqual(a, b + 1e-12, c)
            if c.startswith('steps'):
                continue
            for a, b in zip(ys, ys[1:]):
                self.assertLess(a, b, c)  # strictly monotonic
            for x, y in zip(xs, ys):
                self.assertAlmostEqual(M.invert_curve(y, c), x, delta=1e-6, msg=c)

    def test_steps(self):
        self.assertEqual([M.apply_curve(x, 'steps:3') for x in (0, 0.2, 0.3, 0.8, 1)], [0, 0, 0.5, 1, 1])
        for lv in (0.0, 1 / 3, 2 / 3, 1.0):
            self.assertAlmostEqual(M.invert_curve(lv, 'steps:4'), lv, delta=1e-6)

    def test_clamp_and_unknown(self):
        self.assertEqual(M.apply_curve(2.0, 'log'), 1.0)
        self.assertEqual(M.apply_curve(-1, 'exp'), 0.0)
        with self.assertRaises(ValueError):
            M.apply_curve(0.5, 'nope')
        with self.assertRaises(ValueError):
            M.invert_curve(0.5, 'nope')

    def test_shapes(self):
        self.assertLess(M.apply_curve(0.5, 'ease_in'), 0.5)
        self.assertGreater(M.apply_curve(0.5, 'ease_out'), 0.5)
        self.assertGreater(M.apply_curve(0.5, 'log'), 0.5)
        self.assertLess(M.apply_curve(0.5, 'exp'), 0.5)
        self.assertAlmostEqual(M.apply_curve(0.5, 'smoothstep'), 0.5)
        self.assertAlmostEqual(M.apply_curve(0.5, 'ease_in_out'), 0.5)


class Stepping(unittest.TestCase):
    def test_absolute(self):
        self.assertEqual(M.step_value(mp(), cc(1, 127), 0.2), 1.0)
        self.assertEqual(M.step_value(mp(invert=True), cc(1, 127), 0.2), 0.0)
        self.assertAlmostEqual(M.step_value(mp(curve='ease_in'), cc(1, 127), 0), 1.0)
        self.assertAlmostEqual(M.step_value(mp(curve='ease_in'), M.parse_event('cc14', 1, 1, 8192), 0),
                               (8192 / 16383) ** 2)

    def test_relative_deltas(self):
        self.assertEqual([M.relative_delta(v, 'relative_2c') for v in (1, 3, 127, 125, 64)], [1, 3, -1, -3, -64])
        self.assertEqual([M.relative_delta(v, 'relative_bin') for v in (65, 63, 64, 70)], [1, -1, 0, 6])
        self.assertEqual([M.relative_delta(v, 'relative_sign') for v in (1, 65, 67, 0)], [1, -1, -3, 0])
        with self.assertRaises(ValueError):
            M.relative_delta(1, 'absolute')

    def test_relative_steps_and_clamp(self):
        m = mp(mode='relative_2c', step=0.1)
        self.assertAlmostEqual(M.step_value(m, cc(1, 1), 0.5), 0.6)
        self.assertAlmostEqual(M.step_value(m, cc(1, 127), 0.5), 0.4)
        self.assertEqual(M.step_value(m, cc(1, 10), 0.5), 1.0)
        self.assertEqual(M.step_value(mp(mode='relative_bin', step=0.1), cc(1, 54), 0.5), 0.0)
        self.assertAlmostEqual(M.step_value(mp(mode='relative_sign', step=0.1, invert=True), cc(1, 1), 0.5), 0.4)
        # relative with a curve moves in control space
        mc = mp(mode='relative_2c', step=0.25, curve='ease_in')
        self.assertAlmostEqual(M.step_value(mc, cc(1, 1), 0.25), 0.5625)

    def test_relative_accumulates_on_quantised_par(self):
        m = mp(mode='relative_2c', step=1 / 127, min=0, max=10)  # Int par 0..10: quantum 0.1
        st = {}
        par_norm = 0.0
        for _ in range(13):  # 13 small ticks must move an Int par
            n = M.step_value(m, cc(1, 1), par_norm, state=st, quantum=0.1)
            par_norm = M.from_par_value(m, M.to_par_value(m, n, 'Int'), 'Int')
        self.assertAlmostEqual(par_norm, 0.1)
        # without state the rounding would swallow every tick
        n = M.step_value(m, cc(1, 1), 0.0)
        self.assertEqual(M.to_par_value(m, n, 'Int'), 0)
        # external change resyncs the accumulator
        n = M.step_value(m, cc(1, 1), 0.8, state=st, quantum=0.1)
        self.assertAlmostEqual(n, 0.8 + 1 / 127)

    def test_buttons(self):
        on, off = M.parse_event('note', 1, 1, 127), M.parse_event('note', 1, 1, 0)
        t = mp(kind='note', mode='toggle')
        self.assertEqual(M.step_value(t, on, 0.0), 1.0)
        self.assertEqual(M.step_value(t, on, 1.0), 0.0)
        self.assertIsNone(M.step_value(t, off, 1.0))
        mo = mp(kind='note', mode='momentary')
        self.assertEqual((M.step_value(mo, on, 0), M.step_value(mo, off, 1)), (1.0, 0.0))
        moi = mp(kind='note', mode='momentary', invert=True)
        self.assertEqual((M.step_value(moi, on, 0), M.step_value(moi, off, 1)), (0.0, 1.0))
        tr = mp(kind='cc', mode='trigger')
        self.assertEqual(M.step_value(tr, cc(1, 127), 0), 1.0)
        self.assertIsNone(M.step_value(tr, cc(1, 0), 0))
        ti = mp(mode='toggle', invert=True)
        self.assertEqual(M.step_value(ti, cc(1, 127), 1.0), 0.0)  # toggle ignores invert
        self.assertEqual(M.step_value(ti, cc(1, 127), 0.0), 1.0)


class Takeover(unittest.TestCase):
    def test_none_and_relative_pass(self):
        st = M.TakeoverState()
        self.assertEqual(M.takeover_gate(mp(), st, 0.9, 0.1), (True, 0.9))
        self.assertEqual(M.takeover_gate(mp(takeover='pickup', mode='relative_2c'), st, 0.9, 0.1), (True, 0.9))

    def test_pickup_crossing_up(self):
        m, st = mp(takeover='pickup'), M.TakeoverState()
        self.assertEqual(M.takeover_gate(m, st, 0.1, 0.5), (False, 0.5))
        self.assertEqual(M.takeover_gate(m, st, 0.3, 0.5), (False, 0.5))
        self.assertEqual(M.takeover_gate(m, st, 0.7, 0.5), (True, 0.7))  # crossed
        self.assertTrue(st.picked('a'))
        self.assertEqual(M.takeover_gate(m, st, 0.2, 0.7), (True, 0.2))

    def test_pickup_crossing_down_and_meet(self):
        m, st = mp(takeover='pickup'), M.TakeoverState()
        self.assertFalse(M.takeover_gate(m, st, 0.9, 0.4)[0])
        self.assertEqual(M.takeover_gate(m, st, 0.3, 0.4), (True, 0.3))
        M.takeover_reset(st, 'a')
        self.assertFalse(st.picked('a'))
        self.assertEqual(M.takeover_gate(m, st, 0.41, 0.4), (True, 0.41))  # meets within tol
        M.takeover_reset(st)
        self.assertFalse(st.picked('a'))
        self.assertFalse(M.takeover_gate(m, st, 0.9, 0.4, tol=0.0)[0])

    def test_scale_converges(self):
        m, st = mp(takeover='scale'), M.TakeoverState()
        cur = 0.5
        self.assertEqual(M.takeover_gate(m, st, 0.0, cur), (False, cur))  # first move only arms
        outs = []
        for i in range(1, 11):
            ok, cur = M.takeover_gate(m, st, i / 10, cur)
            self.assertTrue(ok)
            outs.append(cur)
        self.assertEqual(outs, sorted(outs))
        self.assertAlmostEqual(outs[-1], 1.0)
        self.assertTrue(st.picked('a'))
        # downwards
        m2, st2 = mp(id='b', takeover='scale'), M.TakeoverState()
        cur = 0.6
        M.takeover_gate(m2, st2, 1.0, cur)
        ok, cur = M.takeover_gate(m2, st2, 0.5, cur)
        self.assertAlmostEqual(cur, 0.3)
        ok, cur = M.takeover_gate(m2, st2, 0.0, cur)
        self.assertEqual(cur, 0.0)
        self.assertEqual(M.takeover_gate(m2, st2, 0.0, cur), (True, 0.0))


class ParValues(unittest.TestCase):
    def test_float_int(self):
        m = mp(min=0, max=255)
        self.assertEqual(M.to_par_value(m, 0.5, 'Float'), 127.5)
        self.assertEqual(M.to_par_value(m, 0.5, 'Int'), 128)
        self.assertEqual(M.to_par_value(m, 2.0, 'Float'), 255.0)
        self.assertEqual(M.from_par_value(m, 127.5, 'Float'), 0.5)
        self.assertEqual(M.from_par_value(m, 999, 'Float'), 1.0)
        self.assertEqual(M.from_par_value(m, 'x', 'Float'), 0.0)
        r = mp(min=10, max=-10)
        self.assertEqual(M.to_par_value(r, 0.25, 'Float'), 5.0)
        self.assertEqual(M.from_par_value(r, 5.0, 'Float'), 0.25)
        nc = mp(min=0, max=1, clamp=False)
        self.assertEqual(M.to_par_value(nc, 1.5, 'Float'), 1.5)

    def test_toggle_menu(self):
        m = mp()
        self.assertIs(M.to_par_value(m, 0.5, 'Toggle'), True)
        self.assertIs(M.to_par_value(m, 0.49, 'Momentary'), False)
        self.assertIs(M.to_par_value(m, 1.0, 'Pulse'), True)
        self.assertEqual(M.from_par_value(m, True, 'Toggle'), 1.0)
        self.assertEqual(M.from_par_value(m, '0', 'Toggle'), 0.0)
        self.assertEqual([M.to_par_value(m, x, 'Menu', 4) for x in (0, 0.3, 0.5, 1)], [0, 1, 2, 3])
        self.assertEqual(M.from_par_value(m, 2, 'StrMenu', 5), 0.5)
        self.assertEqual(M.from_par_value(m, 0, 'Menu', 1), 0.0)
        self.assertEqual(M.to_par_value(mp(min=0, max=3), 0.5, 'Menu'), 2)  # no menu_count: min..max
        for i in range(6):
            self.assertEqual(M.to_par_value(m, M.from_par_value(m, i, 'Menu', 6), 'Menu', 6), i)


class SmoothFeedback(unittest.TestCase):
    def test_smooth(self):
        self.assertEqual(M.smooth(None, 1.0, 0.1, 0.5), 1.0)
        self.assertEqual(M.smooth(0.0, 1.0, 0.1, 0), 1.0)
        self.assertEqual(M.smooth(0.3, 1.0, 0, 1), 0.3)
        self.assertAlmostEqual(M.smooth(0.0, 1.0, 1.0, 1.0), 1 - 2.718281828459045 ** -1)

    def test_smoother(self):
        s = M.Smoother()
        s.set_target('a', 1.0, current=0.0)
        v = 0.0
        for _ in range(200):
            if 'a' not in s.active():
                break
            v = s.step('a', 1 / 60, 0.1)
        self.assertEqual(v, 1.0)
        self.assertEqual(s.active(), [])
        s.reset()
        self.assertEqual(s.values, {})

    def test_feedback(self):
        self.assertEqual(M.feedback_messages(mp(), 1.0), [])
        self.assertEqual(M.feedback_messages(mp(feedback=True, number=7), 1.0), [('cc', 1, 7, 127)])
        self.assertEqual(M.feedback_messages(mp(feedback=True, channel=2, invert=True, number=7), 1.0),
                         [('cc', 2, 7, 0)])
        m14 = mp(feedback=True, kind='cc14', number=1)
        self.assertEqual(M.feedback_messages(m14, 1.0), [('cc', 1, 1, 127), ('cc', 1, 33, 127)])
        self.assertEqual(M.feedback_messages(m14, 0.5), [('cc', 1, 1, 64), ('cc', 1, 33, 0)])
        self.assertEqual(M.feedback_messages(mp(feedback=True, kind='note', mode='toggle', number=36), 1.0),
                         [('note', 1, 36, 127)])
        self.assertEqual(M.feedback_messages(mp(feedback=True, kind='pitchbend'), 0.0), [('pitchbend', 1, 0, 0)])
        self.assertEqual(M.feedback_messages(mp(feedback=True, kind='program'), 1.0), [])
        mc = mp(feedback=True, curve='ease_in', number=3)
        n = M.step_value(mc, cc(3, 90), 0)
        self.assertEqual(M.feedback_messages(mc, n), [('cc', 1, 3, 90)])  # inverse curve round trip


class Learn(unittest.TestCase):
    def cls(self, vals, n=10, ch=1):
        return M.classify_learn([cc(n, v, ch) for v in vals])

    def test_absolute(self):
        r = self.cls([10, 11, 12, 14, 17])
        self.assertEqual((r['kind'], r['mode'], r['number'], r['control']), ('cc', 'absolute', 10, 'absolute'))
        self.assertEqual(self.cls([1, 2, 3])['mode'], 'absolute')
        self.assertEqual(self.cls([3, 2, 1, 0])['mode'], 'absolute')
        self.assertEqual(self.cls([62, 63, 64, 65, 66])['mode'], 'absolute')

    def test_relative(self):
        self.assertEqual(self.cls([1, 1, 1, 2])['mode'], 'relative_2c')
        self.assertEqual(self.cls([127, 127, 126])['mode'], 'relative_2c')
        self.assertEqual(self.cls([65, 65, 66])['mode'], 'relative_bin')
        self.assertEqual(self.cls([63, 63, 62])['mode'], 'relative_bin')
        self.assertEqual(self.cls([1, 1, 66, 65])['mode'], 'relative_sign')
        self.assertEqual(self.cls([1, 1])['control'], 'encoder')

    def test_button_14bit_pitchbend_note(self):
        self.assertEqual(self.cls([127, 0])['control'], 'button')
        r = M.classify_learn([cc(1, 64), cc(33, 3), cc(1, 65), cc(33, 0)])
        self.assertEqual((r['kind'], r['number'], r['control']), ('cc14', 1, '14bit'))
        r = M.classify_learn([M.parse_event('pitchbend', 4, 0, 9000)])
        self.assertEqual((r['kind'], r['channel']), ('pitchbend', 4))
        r = M.classify_learn([M.parse_event('note', 2, 36, 127), M.parse_event('note', 2, 36, 0)])
        self.assertEqual((r['kind'], r['number'], r['mode']), ('note', 36, 'toggle'))
        r = M.classify_learn([M.parse_event('cc14', 1, 2, 9000)])
        self.assertEqual(r['kind'], 'cc14')
        self.assertIsNone(M.classify_learn([]))
        r = M.classify_learn([M.parse_event('aftertouch', 1, None, 5)])
        self.assertEqual(r['kind'], 'aftertouch')

    def test_dominant_number(self):
        r = M.classify_learn([cc(5, 10), cc(9, 11), cc(9, 12), cc(9, 13)])
        self.assertEqual(r['number'], 9)


class IO(unittest.TestCase):
    def sample(self):
        return [mp(id='a', target='/p/fx', par='Size', min=-2.5, max=1e3, default=0.1, curve='steps:5',
                   invert=True, mode='absolute', takeover='pickup', smooth=0.25, feedback=True, label='a, "b"'),
                mp(id='b', bank=3, kind='cc14', number=1, step=1 / 3),
                mp(id='c', kind='note', mode='toggle', clamp=False)]

    def test_rows_round_trip(self):
        ms = self.sample()
        rows = M.to_rows(ms)
        self.assertEqual(rows[0], M.FIELDS)
        self.assertTrue(all(isinstance(c, str) for r in rows for c in r))
        self.assertEqual(M.from_rows(rows), ms)
        self.assertEqual(M.from_rows([]), [])

    def test_rows_tolerant(self):
        rows = [['par', 'id', 'extra', 'channel'], ['Size', 'z', 'q', '4'], ['', '', '', '']]
        out = M.from_rows(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]['id'], out[0]['par'], out[0]['channel'], out[0]['kind']), ('z', 'Size', 4, 'cc'))
        self.assertIsNone(M.from_rows([['id', 'default', 'min'], ['q', '', '']])[0]['default'])

    def test_json_round_trip(self):
        ms = self.sample()
        txt = M.to_json(ms, active_bank=3, presets={'x': 1})
        cfg = M.from_json(txt)
        self.assertEqual((cfg['version'], cfg['active_bank'], cfg['presets']), (1, 3, {'x': 1}))
        self.assertEqual(cfg['mappings'], ms)
        self.assertEqual(M.from_json(json.dumps([{'id': 'q'}]))['mappings'][0]['id'], 'q')
        with self.assertRaises(ValueError):
            M.from_json(json.dumps({'version': 99, 'mappings': []}))


class Presets(unittest.TestCase):
    def test_presets_shape(self):
        self.assertIn('generic_8x8', M.CONTROLLER_PRESETS)
        for name, p in M.CONTROLLER_PRESETS.items():
            self.assertIn('source', p)
            if not p['source']:
                self.assertIs(p.get('verified'), False, name)
            for c in p['controls']:
                self.assertEqual(set(c), {'label', 'kind', 'channel', 'number', 'mode'})

    def test_mappings_from_preset(self):
        ms = M.mappings_from_preset('generic_8x8', bank=2)
        self.assertEqual(len(ms), 16)
        self.assertEqual(len({m['id'] for m in ms}), 16)
        for m in ms:
            self.assertEqual(M.validate(m), [])
            self.assertEqual(m['bank'], 2)
        self.assertEqual(sorted(m['number'] for m in ms), list(range(8)) + list(range(16, 24)))


class Ascii(unittest.TestCase):
    def test_module_is_ascii(self):
        with open(M.__file__, 'rb') as f:
            f.read().decode('ascii')


if __name__ == '__main__':
    unittest.main()
