"""Offline tests for builders/au_features_logic.py and the builder text (no TD).
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_au_features.py'"""
import ast
import os
import sys
import tempfile
import unittest
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'builders'))
import au_features_logic as L  # noqa: E402

BUILDER = os.path.join(HERE, '..', 'builders', 'au_features.py')


class TestRanges(unittest.TestCase):
    def test_named_ranges(self):
        self.assertEqual(L.bpm_range('wide'), (60.0, 180.0))
        self.assertEqual(L.bpm_range('mid'), (70.0, 110.0))   # T-99: Bhula Dena 88 BPM needs 70-110

    def test_custom_ordered_and_min_gap(self):
        self.assertEqual(L.bpm_range('custom', 140, 90), (90.0, 140.0))
        self.assertEqual(L.bpm_range('custom', 120, 122), (120.0, 130.0))
        self.assertEqual(L.bpm_range('nope', 10, 50), (30.0, 50.0))


class TestNormalise(unittest.TestCase):
    def test_loud(self):
        self.assertEqual(L.loud_norm(-144), 0.0)
        self.assertEqual(L.loud_norm(0), 1.0)
        self.assertAlmostEqual(L.loud_norm(-30), 0.5)
        self.assertEqual(L.loud_norm(float('nan')), 0.0)

    def test_centroid_log(self):
        self.assertEqual(L.centroid_norm(0), 0.0)
        self.assertEqual(L.centroid_norm(L.CENTROID_HI * 2), 1.0)
        mid = (L.CENTROID_LO * L.CENTROID_HI) ** 0.5
        self.assertAlmostEqual(L.centroid_norm(mid), 0.5)


class TestKey(unittest.TestCase):
    def test_raw_live_encoding(self):
        # live 31550: C major tone -> key 0, G major -> 7, A minor -> 9 + major_minor 1
        self.assertEqual(L.key_index_from_raw(0), 0)
        self.assertEqual(L.key_index_from_raw(7.0), 7)
        self.assertEqual(L.key_index_from_raw(9.4), 9)
        self.assertEqual(L.key_index_from_raw(-1), -1)
        self.assertEqual(L.key_index_from_raw(float('nan')), -1)

    def test_labels(self):
        self.assertEqual(L.key_index_from_label('C'), 0)
        self.assertEqual(L.key_index_from_label('Bb minor'), 10)
        self.assertEqual(L.key_index_from_label('f#'), 6)
        self.assertIsNone(L.key_index_from_label('H'))
        self.assertEqual(L.key_name(9, 1), 'A minor')
        self.assertEqual(L.key_name(-1), '-')

    def test_chroma_argmax(self):
        self.assertEqual(L.chroma_argmax([0] * 12), -1)
        self.assertEqual(L.chroma_argmax([0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0.5]), 7)


class TestPulseAndCounts(unittest.TestCase):
    def test_pulse(self):
        self.assertEqual(L.pulse_decay(0, 0.25), 1.0)
        self.assertAlmostEqual(L.pulse_decay(15, 0.25, 60), 0.0498, places=3)
        self.assertEqual(L.pulse_decay(-1, 0.25), 0.0)
        self.assertEqual(L.pulse_decay(1, 0), 0.0)

    def test_rising_edges(self):
        self.assertEqual(L.rising_edges([0, 1, 1, 0, 1, 0, 0, 1]), 3)
        self.assertEqual(L.rising_edges([1, 1, 0]), 0)


class TestBeatClockBpm(unittest.TestCase):
    def test_frame_quantised_beats_within_half_bpm(self):
        for true in (88.0, 100.0, 120.0, 128.0, 174.0):
            times = [round(k * 60.0 / true * 60) / 60.0 for k in range(16)]   # quantised to 60 fps frames
            self.assertLess(abs(L.bpm_from_beats(times, 60, 180) - true), 0.5, true)

    def test_dropped_and_extra_beat_rejected(self):
        t = [k * 0.5 for k in range(16)]
        del t[7]                       # one missed beat -> a 1.0 s interval
        t2 = sorted(t + [3.27])        # one false beat
        self.assertAlmostEqual(L.bpm_from_beats(t2, 60, 180), 120.0, places=6)

    def test_folding_and_too_few(self):
        t = [k * 1.0 for k in range(10)]          # 60 BPM
        self.assertAlmostEqual(L.bpm_from_beats(t, 90, 130), 120.0)
        self.assertEqual(L.bpm_from_beats([0, 0.5, 1.0], 60, 180), 0.0)
        self.assertEqual(L.fold_bpm(0, 60, 180), 0.0)


class TestTracks(unittest.TestCase):
    def test_click_times_exact(self):
        t = L.click_times(120, 30)
        self.assertEqual(len(t), 60)
        self.assertAlmostEqual(t[1] - t[0], 0.5)

    def test_wav_written(self):
        d = tempfile.mkdtemp()
        p = L._write(os.path.join(d, 'x.wav'), L.click_track(120, 2, 8000)[0], 8000)
        w = wave.open(p)
        self.assertEqual((w.getnchannels(), w.getframerate(), w.getnframes()), (1, 8000, 16000))
        w.close()

    def test_tone_pitch_classes(self):
        self.assertEqual({round(L.midi_hz(m)) for m in (69,)}, {440})
        self.assertEqual(len(L.C_MAJOR), 7)


class TestChannels(unittest.TestCase):
    def test_unique_names_no_dots(self):
        names = [c[0] for c in L.CHANNELS] + list(L.DERIVED)
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            self.assertNotIn('.', n)    # T-90: CHOP names cannot hold '.'

    def test_chroma_c_first(self):
        chroma = [c for c in L.CHANNELS if c[0].startswith('chroma_')]
        self.assertEqual(chroma[0], ('chroma_c', 'tonal', 'note_c'))
        self.assertEqual(len(chroma), 12)


class TestBuilderText(unittest.TestCase):
    def setUp(self):
        self.src = open(BUILDER).read()

    def test_parses_and_ascii(self):
        ast.parse(self.src)
        self.src.encode('ascii')
        open(os.path.join(HERE, '..', 'builders', 'au_features_logic.py')).read().encode('ascii')

    def test_never_unloads_plugins(self):
        self.assertNotIn('unloadplugin', self.src)   # T-106

    def test_callback_parses(self):
        ns = {}
        exec(compile(self.src, BUILDER, 'exec'), {'__name__': 'x', 'op': None}, ns)
        ast.parse(ns['FEATURES_CB'])
        for k in ('LOAD_CODE', 'SET_PLUGIN'):
            ast.parse(ns[k])

    def test_plugin_binds_use_live_par_names(self):
        ns = {}
        exec(compile(self.src, BUILDER, 'exec'), {'__name__': 'x'}, ns)
        self.assertEqual(set(ns['BINDS']), set(ns['PLUG']))
        rh = dict(ns['BINDS']['rhythm'])
        for k in ('Bpmmin', 'Bpmmax', 'Onsetsensitivity', 'Onsetmethod', 'Rtwindowsize'):
            self.assertIn(k, rh)


if __name__ == '__main__':
    unittest.main()
