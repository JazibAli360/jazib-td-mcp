"""Offline tests for PX phase A (28 Oct): beat sync (audio drive sources from AU_features, beat / onset triggers) and
the setlist (presets as scenes, Next / Prev / Go, transitions). docs/builds/px.md "28 Oct: beat sync + setlist".
No TD needed. Run: python3 -I -m unittest discover -s test -p 'test_px_phaseA.py'"""
import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
sys.path.insert(0, BUILDERS)
import px_logic as L  # noqa: E402
import au_features_logic as A  # noqa: E402


def _rd(*p):
    with open(os.path.join(BUILDERS, *p)) as fh:
        return fh.read()


def _spec(page, name):
    for pg, pars in L.CORE_PAGES:
        if pg == page:
            for s in pars:
                if s[0] == name:
                    return s
    return None


CH = {'beat_count': 10, 'onset_count': 20, 'bpm': 120.0, 'live': 1.0, 'bass': 0.7, 'mid': 0.4, 'high': 0.1,
      'band_level': 0.6, 'loud': 0.8}


class AudioClock(unittest.TestCase):
    def test_off_reads_zero(self):
        src, st, ev, bpm, bi = L.audio_tick({'bn': 3, 'bt': 1.0}, None, 5.0, 6.0)
        self.assertEqual(set(src), set(L.AUDIO_SRCS))
        self.assertTrue(all(v == 0.0 for v in src.values()))
        self.assertEqual((st, ev, bpm, bi), ({}, {'beat': False, 'onset': False}, 0.0, None))

    def test_first_read_no_event_then_edges(self):
        src, st, ev, bpm, bi = L.audio_tick({}, CH, 1.0, 6.0)
        self.assertFalse(ev['beat'] or ev['onset'])
        self.assertEqual(src['beat'], 0.0)                     # no beat seen yet
        self.assertEqual((bpm, bi), (120.0, 10))
        ch = dict(CH, beat_count=11, onset_count=21)
        src, st, ev, bpm, bi = L.audio_tick(st, ch, 2.0, 6.0)
        self.assertTrue(ev['beat'] and ev['onset'])
        self.assertEqual((src['beat'], src['onset'], src['tempo'], bi), (1.0, 1.0, 0.0, 11))
        src, st, ev, _b, _i = L.audio_tick(st, ch, 2.25, 6.0)  # a quarter second later, no new beat
        self.assertFalse(ev['beat'])
        self.assertAlmostEqual(src['beat'], math.exp(-1.5))
        self.assertAlmostEqual(src['tempo'], 0.5)              # 0.25 s at 120 bpm = half a beat
        src, st, ev, _b, _i = L.audio_tick(st, ch, 2.75, 6.0)
        self.assertAlmostEqual(src['tempo'], 0.5)              # 1.5 beats: the phase wraps

    def test_counter_reset_is_not_a_beat(self):
        _s, st, _e, _b, _i = L.audio_tick({}, CH, 1.0, 6.0)
        _s, st, ev, _b, bi = L.audio_tick(st, dict(CH, beat_count=0), 1.1, 6.0)
        self.assertFalse(ev['beat'])
        self.assertEqual(bi, 0)
        _s, st, ev, _b, _i = L.audio_tick(st, dict(CH, beat_count=1), 1.2, 6.0)
        self.assertTrue(ev['beat'])

    def test_bands_and_level(self):
        src, *_ = L.audio_tick({}, CH, 1.0, 6.0)
        self.assertEqual((src['bass'], src['mid'], src['high'], src['level']), (0.7, 0.4, 0.1, 0.8))   # live: loud
        src, st, ev, bpm, _i = L.audio_tick({}, dict(CH, live=0.0), 1.0, 6.0)
        self.assertEqual(src['level'], 0.6)                    # no analysis: the FFT band level
        self.assertEqual((src['beat'], src['onset'], src['tempo'], bpm), (0.0, 0.0, 0.0, 0.0))
        src, *_ = L.audio_tick({}, {}, 1.0, 6.0)               # a COMP with none of the channels: zeros, no error
        self.assertTrue(all(v == 0.0 for v in src.values()))

    def test_not_live_keeps_beats_silent(self):
        _s, st, *_ = L.audio_tick({}, CH, 1.0, 6.0)
        src, st, ev, _b, _i = L.audio_tick(st, dict(CH, beat_count=11), 1.5, 6.0)
        src, st, ev, _b, _i = L.audio_tick(st, dict(CH, beat_count=11, live=0.0), 1.6, 6.0)
        self.assertEqual(src['beat'], 0.0)


class Triggers(unittest.TestCase):
    def test_clock_beat(self):
        self.assertEqual(L.clock_beat(0.49, 120, None), (False, 0))
        self.assertEqual(L.clock_beat(0.51, 120, 0), (True, 1))
        self.assertEqual(L.clock_beat(0.6, 120, 1), (False, 1))

    def test_trig_fire(self):
        self.assertFalse(L.trig_fire('manual', 4, True, 4, True))
        self.assertTrue(L.trig_fire('beat', 4, True, 3, False))
        self.assertFalse(L.trig_fire('beat', 4, False, 3, True))
        self.assertTrue(L.trig_fire('onset', 4, False, 3, True))
        self.assertTrue(L.trig_fire('nbeats', 4, True, 8, False))
        self.assertFalse(L.trig_fire('nbeats', 4, True, 9, False))
        self.assertFalse(L.trig_fire('nbeats', 4, True, None, False))
        self.assertTrue(L.trig_fire('nbeats', 0, True, 9, False))   # N < 1 = every beat
        fired = sum(L.trig_fire('nbeats', 4, True, k, False) for k in range(1, 17))
        self.assertEqual(fired, 4)

    def test_trig_which_and_auto_unchanged(self):
        self.assertEqual(L.trig_which('all'), [0, 1, 2, 3])
        self.assertEqual(L.trig_which('trig3'), [2])
        self.assertEqual(L.trig_auto(5.0, None, 2.0, 'trig2'), ([1], 5.0))
        self.assertEqual(L.trig_auto(5.5, 5.0, 2.0, 'trig2'), ([], 5.0))

    def test_drives_need_audio(self):
        self.assertTrue(L.drives_need_audio(L.parse_drives('strength:bass*2')[0]))
        self.assertTrue(L.drives_need_audio(L.parse_drives('radius:lfo1 amount:onset*0.5')[0]))
        self.assertFalse(L.drives_need_audio(L.parse_drives('progress:beat*1 x:tempo')[0]))   # Beatsync decides
        self.assertFalse(L.drives_need_audio(L.parse_drives('strength:low*2')[0]))           # in_ctl only

    def test_beat_drive_maths(self):
        d, bad = L.parse_drives('progress:beat*1')
        self.assertEqual(bad, [])
        v = L.apply_drives({'progress': 0.0}, 'explode', d, {'beat': 0.6})
        self.assertAlmostEqual(v['progress'], 0.6)


class Setlist(unittest.TestCase):
    P = ['A', 'B', 'C', 'D']

    def test_names_default_presets_order(self):
        self.assertEqual(L.setlist_names([], self.P), self.P)
        self.assertEqual(L.setlist_names(['', '  '], self.P), self.P)
        self.assertEqual(L.setlist_names([' C ', 'A', 'X'], self.P), ['C', 'A', 'X'])

    def test_labels_missing(self):
        n = ['C', 'X', 'A', 'C']
        self.assertEqual(L.setlist_labels(n, self.P), ['1 C', '2 X (missing)', '3 A', '4 C'])
        self.assertEqual(L.setlist_missing(n, self.P), ['X'])

    def test_step_wraps_and_skips(self):
        n = ['C', 'X', 'A']
        self.assertEqual(L.setlist_step(n, self.P, None, 1), (0, []))
        self.assertEqual(L.setlist_step(n, self.P, 0, 1), (2, ['X']))
        self.assertEqual(L.setlist_step(n, self.P, 2, 1), (0, []))           # wraps
        self.assertEqual(L.setlist_step(n, self.P, None, -1), (2, []))       # Prev first = the last scene
        self.assertEqual(L.setlist_step(n, self.P, 2, -1), (0, ['X']))
        self.assertEqual(L.setlist_step(['X', 'Y'], self.P, None, 1), (None, ['X', 'Y']))
        self.assertEqual(L.setlist_step([], self.P, None, 1), (None, []))

    def test_cue_index(self):
        n = ['C', 'X', 'A', 'C']
        self.assertEqual(L.cue_index(n, 'A'), 2)
        self.assertEqual(L.cue_index(n, '4 C'), 3)                           # a menu label (duplicates kept apart)
        self.assertEqual(L.cue_index(n, '2 X (missing)'), 1)
        self.assertEqual(L.cue_index(n, '3'), 2)
        self.assertIsNone(L.cue_index(n, '9'))
        self.assertIsNone(L.cue_index(n, '3 C'))                             # label and name disagree
        self.assertIsNone(L.cue_index(n, ''))

    def test_transition_and_curve(self):
        self.assertEqual(L.transition_seconds(2.0, False, 128), 2.0)
        self.assertAlmostEqual(L.transition_seconds(4, True, 128), 1.875)
        self.assertEqual(L.transition_seconds(4, True, 0), 4.0)              # no bpm: seconds
        self.assertEqual(L.transition_seconds(-1, False, 0), 0.0)
        self.assertEqual(L.trans_curve('ease'), 'smooth')
        self.assertEqual(L.trans_curve('linear'), 'linear')
        self.assertAlmostEqual(L.curve(0.25, L.trans_curve('ease')), 0.15625)

    def test_current_text(self):
        self.assertEqual(L.current_text(['A', 'B'], 1), '2/2 B')
        self.assertEqual(L.current_text(['A'], None), '-')
        self.assertEqual(L.current_text(['A'], 5), '-')

    def test_hand_moved(self):
        self.assertFalse(L.hand_moved(0.5, None))
        self.assertFalse(L.hand_moved(0.5, 0.5))
        self.assertFalse(L.hand_moved(0.50000001, 0.5))                     # float32 round trip
        self.assertTrue(L.hand_moved(0.2, 0.5))
        self.assertTrue(L.hand_moved('alpha', 'add'))
        self.assertFalse(L.hand_moved(True, 1.0))


class Pars(unittest.TestCase):
    def test_drive_page(self):
        self.assertEqual(_spec('Drive', 'Trigsource')[2], 'manual')
        self.assertEqual(_spec('Drive', 'Trigsource')[3]['names'], ['manual', 'beat', 'onset', 'nbeats'])
        self.assertEqual(_spec('Drive', 'Trigbeats')[1:3], ('Int', 4))
        self.assertEqual(_spec('Drive', 'Audiosrc')[1:3], ('COMP', '/project1/lab/AU_features'))
        self.assertEqual(_spec('Drive', 'Beatsync')[1:3], ('Toggle', False))

    def test_presets_page(self):
        for n, st in (('Next', 'Pulse'), ('Prev', 'Pulse'), ('Go', 'Pulse'), ('Setlistfill', 'Pulse'),
                      ('Cue', 'Str'), ('Transition', 'Float'), ('Transcurve', 'Menu'), ('Current', 'Str'),
                      ('Cueindex', 'Int'), ('Setlist', 'DAT')):
            self.assertEqual(_spec('Presets', n)[1], st, n)
        self.assertEqual(_spec('Presets', 'Setlist')[2], './px_setlist')      # T-244: a bare name = a sibling
        self.assertTrue(_spec('Presets', 'Current')[3].get('readonly'))
        self.assertIn('Cue', L.menu_specs(dict(L.CORE_PAGES)['Presets']))
        self.assertEqual(L.menu_source('Cue'), "me.op('px_rt').module.menu(me, 'Cue')")

    def test_never_in_a_preset(self):
        for n in ('Status', 'Presetname', 'Newname', 'Audiosrc', 'Beatsync', 'Current', 'Cue', 'Cueindex',
                  'Setlist', 'Transition', 'Transcurve'):
            self.assertIn(n, L.NOSNAP)
        self.assertNotIn('Trigsource', L.NOSNAP)                              # a look may trigger on the beat
        self.assertIn('Cue', L.discrete_keys([]))
        self.assertIn('Audiosrc', L.discrete_keys([]))


class Wiring(unittest.TestCase):
    def test_runtime(self):
        rt = _rd('px_rt.py')
        for s in ("_nosnap()", "def _beat_sync(", "def _audio_chans(", "def setlist_go(", "def setlist_step(",
                  "def setlist_fill(", "elif n in ('Next', 'Prev'):", "elif n == 'Go':", "if par.name == 'Cueindex':",
                  "if name == 'Cue':", "hold.append(k)", "def morph_to(c, name, dur=None, curve=None):"):
            self.assertIn(s, rt)
        self.assertIn("'Current', 'Cue'", rt)                                 # SKIP_DIRTY: no core recompute

    def test_builder(self):
        px = _rd('px.py')
        self.assertIn("Cueindex'  # px_values", px)
        self.assertIn("'px_presets', 'px_setlist'", px)                      # STAGES 0 Code + tables
        self.assertIn("def beatsync28_upgrade(parent_path='/project1/lab', name=NAME):", px)
        self.assertIn("_table(c, 'px_setlist', ['name'], SETLIST_NOTE)", px)
        self.assertIn("appendCOMP if style == 'COMP' else page.appendDAT", px)

    def test_main_tab(self):
        d = json.loads(_rd('zk_essentials.json'))['PX_pointfx']['main']
        self.assertLessEqual(len(d), 16)
        for n in ('Prev', 'Next', 'Transition'):
            self.assertIn(n, d)
        names = set(s[0] for _pg, pars in L.CORE_PAGES for s in pars)
        self.assertEqual([n for n in d if not n.startswith('M') and n not in names], [])


class Bands(unittest.TestCase):
    def _sine(self, hz, amp, n=A.BAND_N, rate=48000.0):
        return [amp * math.sin(2 * math.pi * hz * k / rate) for k in range(n)]

    def test_sine_lands_in_its_band(self):
        want = A.db_norm(0.5 / math.sqrt(2.0))
        self.assertAlmostEqual(want, (20 * math.log10(0.5) + 60) / 60)
        for hz, band in ((70.0, 'bass'), (1000.0, 'mid'), (6000.0, 'high')):
            v = A.band_levels(self._sine(hz, 0.5), 48000.0)
            self.assertAlmostEqual(v[band], want, delta=0.01, msg=hz)
            for other in ('bass', 'mid', 'high'):
                if other != band:
                    self.assertLess(v[other], want - 0.2, '%s leaks into %s' % (hz, other))
            self.assertAlmostEqual(v['band_level'], want, delta=0.01)

    def test_silence_short_and_cache(self):
        self.assertEqual(A.band_levels([0.0] * 2048, 48000.0)['bass'], 0.0)
        self.assertEqual(A.band_levels([0.1] * 8, 48000.0)['mid'], 0.0)
        self.assertEqual(A.band_levels(self._sine(70, 0.5), 0)['bass'], 0.0)
        cache = {}
        a = A.band_levels(self._sine(1000.0, 0.3), 48000.0, cache=cache)
        b = A.band_levels(self._sine(1000.0, 0.3), 48000.0, cache=cache)
        self.assertEqual(a, b)
        self.assertEqual(cache['key'][0], A.BAND_N)

    def test_smooth(self):
        self.assertEqual(A.band_smooth(None, 0.4, 0.016), 0.4)
        self.assertEqual(A.band_smooth(0.2, 0.4, 0.016), 0.4)                 # fast attack
        self.assertAlmostEqual(A.band_smooth(0.8, 0.0, A.BAND_RELEASE), 0.8 * math.exp(-1.0))

    def test_callback_and_upgrade(self):
        au = _rd('au_features.py')
        for s in ('_wire(nin, fe, 4)', 'scriptOp.isTimeSlice = False', "def bands_upgrade(parent_path='/project1/lab', name=NAME):",
                  "'Bandfloor'", 'L.band_levels(st['):
            self.assertIn(s, au)
        self.assertEqual(A.BAND_CHANNELS, ('bass', 'mid', 'high', 'band_level'))


if __name__ == '__main__':
    unittest.main()
