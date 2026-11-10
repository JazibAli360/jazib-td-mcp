"""Offline tests for builders/strobe_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_strobe.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import strobe_logic as L  # noqa: E402

FPS = 60.0


def run(p, frames, inp_fn=None, events_fn=None, st=None):
    """Step `frames` frames at 60 fps; returns (state, list of outs)."""
    outs = []
    for f in range(frames):
        t = f / FPS
        inp = inp_fn(f) if inp_fn else {}
        ev = events_fn(f) if events_fn else ()
        st, o = L.step(st, t, inp, p, ev)
        outs.append(o)
    return st, outs


def pulse_train(period_frames, on_frames=2):
    return lambda f: {'value': 1.0 if (f % period_frames) < on_frames else 0.0}


class AudioTrigger(unittest.TestCase):
    def test_every_trigger(self):
        _, o = run({'source': 'kick'}, 300, pulse_train(30))
        self.assertEqual(sum(x['hit'] for x in o), 10)
        self.assertEqual(o[0]['hit'], 1.0)

    def test_division(self):
        for div, want in ((1, 16), (2, 8), (4, 4), (8, 2), (16, 1)):
            _, o = run({'source': 'kick', 'division': div}, 480, pulse_train(30))
            hits = [k for k, x in enumerate(o) if x['hit']]
            self.assertEqual(len(hits), want, div)
            self.assertEqual(hits[0], 0)                       # first trigger fires
            if len(hits) > 1:
                self.assertEqual(hits[1] - hits[0], 30 * div)

    def test_hysteresis(self):
        # wobble 0.62 / 0.5 around threshold 0.6 never re-arms (needs < 0.45)
        seq = [0.0, 0.7, 0.5, 0.62, 0.5, 0.62, 0.4, 0.7]
        _, o = run({'source': 'kick', 'threshold': 0.6}, len(seq), lambda f: {'value': seq[f]})
        self.assertEqual([k for k, x in enumerate(o) if x['hit']], [1, 7])

    def test_hold_gap(self):
        _, o = run({'source': 'kick', 'hold': 0.75}, 300, pulse_train(15))   # triggers every 0.25 s
        hits = [k for k, x in enumerate(o) if x['hit']]
        self.assertEqual(hits[:3], [0, 45, 90])
        _, o = run({'source': 'kick', 'hold': 0.0}, 300, pulse_train(15))
        self.assertEqual(sum(x['hit'] for x in o), 20)

    def test_no_limit_every_frame(self):
        seq = lambda f: {'value': float(f % 2)}            # 30 triggers per second, no cap
        _, o = run({'source': 'kick', 'threshold': 0.5}, 60, seq)
        self.assertEqual(sum(x['hit'] for x in o), 30)


class Bpm(unittest.TestCase):
    def test_quarter_notes_120(self):
        _, o = run({'source': 'bpm', 'tempo': 'manual', 'bpm': 120.0, 'note': 'n4'}, 600)
        hits = [k for k, x in enumerate(o) if x['hit']]
        self.assertEqual(len(hits), 19)                    # 10 s at 2 Hz, the hit at t=0 is not crossed
        self.assertEqual(hits[1] - hits[0], 30)

    def test_note_values(self):
        for note, mod, want in (('n8', 'straight', 4), ('n16', 'straight', 8), ('bar1', 'straight', 0),
                                ('n8', 'triplet', 6), ('n4', 'dotted', 1)):
            _, o = run({'source': 'bpm', 'tempo': 'manual', 'bpm': 120.0, 'note': note, 'notemod': mod}, 61)
            self.assertEqual(sum(x['hit'] for x in o), want, (note, mod))

    def test_project_and_link_tempo(self):
        self.assertEqual(L.resolve_bpm({'tempo': 'project', 'project_bpm': 128.0}), 128.0)
        self.assertEqual(L.resolve_bpm({'tempo': 'manual', 'bpm': 90.0, 'project_bpm': 128.0}), 90.0)
        self.assertEqual(L.resolve_bpm({'tempo': 'link', 'project_bpm': 128.0}, 140.0), 140.0)
        self.assertEqual(L.resolve_bpm({'tempo': 'link', 'project_bpm': 128.0}, None), 128.0)

    def test_swing(self):
        self.assertEqual(L.bpm_hits(0.0, 4.0, 1.0, 0.0, 0.0), 4)
        # swing 0.25: hits at 1.25, 2, 3.25, 4 -> in (0.5, 1.2] none, (1.2, 1.3] one
        self.assertEqual(L.bpm_hits(0.5, 1.2, 1.0, 0.0, 0.25), 0)
        self.assertEqual(L.bpm_hits(1.2, 1.3, 1.0, 0.0, 0.25), 1)
        self.assertEqual(L.bpm_hits(1.9, 2.0, 1.0, 0.0, 0.25), 1)

    def test_phase(self):
        self.assertEqual(L.bpm_hits(0.0, 0.4, 1.0, 0.5), 0)
        self.assertEqual(L.bpm_hits(0.4, 0.6, 1.0, 0.5), 1)

    def test_resync_fires_now(self):
        ev = lambda f: ('resync',) if f == 10 else ()
        _, o = run({'source': 'bpm', 'tempo': 'manual', 'bpm': 120.0}, 41, events_fn=ev)
        hits = [k for k, x in enumerate(o) if x['hit']]
        self.assertEqual(hits[:2], [10, 40])

    def test_tap(self):
        taps, bpm = L.tap_bpm([], 10.0)
        self.assertIsNone(bpm)
        for k in range(1, 6):
            taps, bpm = L.tap_bpm(taps, 10.0 + 0.5 * k)
        self.assertAlmostEqual(bpm, 120.0)
        self.assertEqual(len(taps), 5)
        taps, bpm = L.tap_bpm(taps, 20.0)                  # long gap starts over
        self.assertEqual(taps, [20.0])
        self.assertIsNone(bpm)


class LfoManual(unittest.TestCase):
    def test_lfo_rate(self):
        _, o = run({'source': 'lfo', 'rate': 4.0}, 601)
        self.assertEqual(sum(x['hit'] for x in o), 40)
        _, o = run({'source': 'lfo', 'rate': 60.0}, 60)    # open range: one per frame
        self.assertEqual(sum(x['hit'] for x in o), 59)

    def test_manual_fire_and_key(self):
        ev = lambda f: ('fire',) if f in (5, 20) else ()
        key = lambda f: {'key': 1 if 30 <= f < 40 else 0}
        _, o = run({'source': 'manual'}, 60, key, ev)
        self.assertEqual([k for k, x in enumerate(o) if x['hit']], [5, 20, 30])

    def test_fire_ignores_hold_and_works_in_any_mode(self):
        ev = lambda f: ('fire',) if f in (1, 2) else ()
        _, o = run({'source': 'kick', 'hold': 10.0}, 4, events_fn=ev)
        self.assertEqual([k for k, x in enumerate(o) if x['hit']], [1, 2])

    def test_burst(self):
        ev = lambda f: ('burst',) if f == 0 else ()
        _, o = run({'source': 'manual', 'tempo': 'manual', 'bpm': 120.0, 'note': 'n8', 'burstcount': 4}, 120,
                   events_fn=ev)
        self.assertEqual([k for k, x in enumerate(o) if x['hit']], [0, 15, 30, 45])
        _, o = run({'source': 'lfo', 'rate': 0.001, 'burstcount': 3}, 120, events_fn=ev)
        self.assertEqual(sum(x['hit'] for x in o), 1)       # 1000 s spacing

    def test_flash_hold(self):
        fl = lambda f: {'flash': 5 <= f < 20}
        _, o = run({'source': 'manual', 'attack': 0.0, 'release': 0.1}, 40, fl)
        self.assertEqual(o[4]['env'], 0.0)
        self.assertTrue(all(o[k]['env'] == 1.0 for k in range(5, 20)))
        self.assertEqual(o[20]['lin'], 1.0)                 # release starts on the frame the hold ends
        self.assertAlmostEqual(o[21]['lin'], 1.0 - (1 / 60.0) / 0.1, places=6)
        self.assertEqual(o[30]['env'], 0.0)


class Envelope(unittest.TestCase):
    def test_shape(self):
        self.assertEqual(L.envelope(None, 0.01, 0.15), 0.0)
        self.assertAlmostEqual(L.envelope(0.005, 0.01, 0.15), 0.5)
        self.assertAlmostEqual(L.envelope(0.01, 0.01, 0.15), 1.0)
        self.assertAlmostEqual(L.envelope(0.085, 0.01, 0.15), 0.5)
        self.assertEqual(L.envelope(0.5, 0.01, 0.15), 0.0)
        self.assertEqual(L.envelope(0.0, 0.0, 0.0), 1.0)    # one-frame flash
        self.assertEqual(L.envelope(0.016, 0.0, 0.0), 0.0)

    def test_peak_on_hit_frame(self):
        ev = lambda f: ('fire',) if f == 3 else ()
        _, o = run({'source': 'manual', 'attack': 0.01, 'release': 0.15}, 20, events_fn=ev)
        self.assertEqual(o[3]['env'], 1.0)
        self.assertAlmostEqual(o[4]['env'], 1.0 - (1 / 60.0) / 0.15, places=6)
        _, o = run({'source': 'manual', 'attack': 0.1, 'release': 0.15}, 20, events_fn=ev)
        self.assertAlmostEqual(o[3]['env'], (1 / 60.0) / 0.1, places=6)   # slow attack ramps from the hit frame

    def test_ease_depth(self):
        self.assertAlmostEqual(L.ease(0.5, 'in'), 0.25)
        self.assertAlmostEqual(L.ease(0.5, 'out'), 0.75)
        self.assertAlmostEqual(L.ease(0.5, 'inout'), 0.5)
        _, o = run({'source': 'manual', 'depth': 0.4, 'attack': 0.0}, 2, events_fn=lambda f: ('fire',) if f == 0 else ())
        self.assertAlmostEqual(o[0]['env'], 0.4)

    def test_menus_consistent(self):
        self.assertEqual(len(L.NOTES), len(L.NOTE_LABELS))
        self.assertTrue(all(n in L.NOTE_BEATS for n in L.NOTES))
        self.assertEqual(L.note_beats('n8', 'triplet'), 0.5 * 2 / 3)

    def test_ascii(self):
        with open(os.path.join(os.path.dirname(HERE), 'builders', 'strobe_logic.py'), 'rb') as fh:
            fh.read().decode('ascii')


if __name__ == '__main__':
    unittest.main()
