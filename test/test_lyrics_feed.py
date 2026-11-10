"""Offline tests for builders/lyrics_feed_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_lyrics_feed.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import lyrics_feed_logic as L  # noqa: E402

DEMO = os.path.join(HERE, 'fixtures', 'lyrics', 'Jazib Test - Lyrics Feed Demo.lrc')


class Parse(unittest.TestCase):
    def setUp(self):
        with open(DEMO, 'rb') as f:
            self.doc = L.parse_lrc(f.read())

    def test_tags_and_count(self):
        t = self.doc['tags']
        self.assertEqual(t['ti'], 'Lyrics Feed Demo')
        self.assertEqual(t['ar'], 'Jazib Test')
        self.assertEqual(L.song_length(self.doc), 40.0)
        self.assertEqual(len(self.doc['lines']), 13)          # 12 stamped rows, one with two stamps

    def test_urdu_kept(self):
        lines = dict(self.doc['lines'])
        self.assertEqual(lines[5.5], 'یہ ایک آزمائشی سطر ہے')
        self.assertTrue(L.is_rtl(lines[5.5]))
        self.assertFalse(L.is_rtl(lines[9.0]))

    def test_multi_stamp_and_sorted(self):
        times = [t for t, _ in self.doc['lines']]
        self.assertEqual(times, sorted(times))
        chorus = [t for t, s in self.doc['lines'] if s.startswith('A chorus')]
        self.assertEqual(chorus, [23.0, 33.0])

    def test_word_stamps_dropped(self):
        self.assertEqual(dict(self.doc['lines'])[19.5], 'Word stamps are dropped')

    def test_bom_crlf_formats(self):
        d = L.parse_lrc(b'\xef\xbb\xbf[00:01.00]bom\r\n[01:03]no frac\r\n[00:02:50]colon\r\n[00:04.123]ms\r\n')
        self.assertEqual(d['lines'], [(1.0, 'bom'), (2.5, 'colon'), (4.123, 'ms'), (63.0, 'no frac')])

    def test_offset_tag(self):
        d = L.parse_lrc('[offset:+500]\n[00:02.00]a\n[00:00.20]b')
        self.assertEqual(d['lines'], [(0.0, 'b'), (1.5, 'a')])

    def test_junk_lines(self):
        d = L.parse_lrc('random text\n\n[ti:x]\n[00:01.00]ok')
        self.assertEqual(d['lines'], [(1.0, 'ok')])
        self.assertEqual(L.song_length(d), 6.0)
        self.assertEqual(L.song_length({'lines': [], 'tags': {}}), 0.0)


class Lookup(unittest.TestCase):
    LINES = [(0.0, ''), (2.0, 'a'), (5.0, 'b'), (9.0, 'c')]

    def test_before_first(self):
        s = L.line_state([(2.0, 'a')], 1.0, 10)
        self.assertEqual((s['idx'], s['cur'], s['next'], s['line_progress']), (-1, '', 'a', 0.0))

    def test_middle(self):
        s = L.line_state(self.LINES, 3.5, 12)
        self.assertEqual((s['idx'], s['cur'], s['next'], s['prev']), (1, 'a', 'b', ''))
        self.assertAlmostEqual(s['line_progress'], 0.5)
        self.assertAlmostEqual(s['next_in'], 1.5)
        self.assertAlmostEqual(s['song_progress'], 3.5 / 12)

    def test_exact_boundary(self):
        self.assertEqual(L.line_state(self.LINES, 5.0, 12)['cur'], 'b')
        self.assertEqual(L.line_state(self.LINES, 4.999, 12)['cur'], 'a')

    def test_last_line(self):
        s = L.line_state(self.LINES, 10.5, 12)
        self.assertEqual((s['cur'], s['next'], s['next_in']), ('c', '', -1.0))
        self.assertAlmostEqual(s['line_progress'], 0.5)

    def test_empty(self):
        s = L.line_state([], 3, 0)
        self.assertEqual((s['idx'], s['count'], s['cur']), (-1, 0, ''))


class NowPlaying(unittest.TestCase):
    def test_playing(self):
        out = L.SEP.join(['playing', 'Song | Name', 'Artist', '12,5', '201000', 'spotify:track:ABC']) + '\n'
        d = L.parse_now_playing(0, out, '')
        self.assertTrue(d['ok'])
        self.assertEqual((d['state'], d['title'], d['pos'], d['dur'], d['id']),
                         ('playing', 'Song | Name', 12.5, 201.0, 'spotify:track:ABC'))

    def test_states(self):
        self.assertEqual(L.parse_now_playing(0, 'notrunning\n', '')['state'], 'notrunning')
        self.assertEqual(L.parse_now_playing(0, 'stopped', '')['state'], 'stopped')
        d = L.parse_now_playing(1, '', 'execution error: Not authorized to send Apple events to Spotify. (-1743)')
        self.assertEqual((d['ok'], d['state']), (False, 'noperm'))
        self.assertEqual(L.parse_now_playing(1, '', 'boom')['state'], 'error')
        self.assertEqual(L.parse_now_playing(0, 'garbage', '')['state'], 'error')

    def test_script_has_no_launch(self):
        self.assertIn('is running', L.APPLESCRIPT)           # never launches Spotify by itself


class Clock(unittest.TestCase):
    def poll(self, pos, stamp, state='playing', tid='x'):
        return {'ok': True, 'state': state, 'pos': pos, 'stamp': stamp, 'id': tid}

    def test_interpolates_between_polls(self):
        st, p, r = L.clock_spotify(None, 10.0, self.poll(30.0, 9.9))
        self.assertTrue(r)
        self.assertAlmostEqual(p, 30.1)
        st, p, r = L.clock_spotify(st, 10.5, None)
        self.assertAlmostEqual(p, 30.6)
        self.assertFalse(r)

    def test_small_drift_runs_free_big_drift_resyncs(self):
        st, _, _ = L.clock_spotify(None, 0.0, self.poll(10.0, 0.0))
        st, p, r = L.clock_spotify(st, 1.0, self.poll(11.2, 1.0))     # 0.2 off: keep running
        self.assertFalse(r)
        self.assertAlmostEqual(p, 11.0)
        st, p, r = L.clock_spotify(st, 2.0, self.poll(40.0, 2.0))     # seek: resync
        self.assertTrue(r)
        self.assertAlmostEqual(p, 40.0)

    def test_pause_and_track_change(self):
        st, _, _ = L.clock_spotify(None, 0.0, self.poll(10.0, 0.0))
        st, p, r = L.clock_spotify(st, 1.0, self.poll(10.9, 1.0, 'paused'))
        self.assertTrue(r)
        st, p, _ = L.clock_spotify(st, 3.0, None)
        self.assertAlmostEqual(p, 10.9)                                   # paused = holds
        st, p, r = L.clock_spotify(st, 3.0, self.poll(0.5, 3.0, 'playing', 'y'))
        self.assertTrue(r)
        self.assertEqual(st['id'], 'y')
        st, p, r = L.clock_spotify(st, 4.0, {'ok': True, 'state': 'stopped'})
        self.assertEqual((p, st['playing']), (0.0, False))

    def test_failed_poll_keeps_running(self):
        st, _, _ = L.clock_spotify(None, 0.0, self.poll(10.0, 0.0))
        st, p, r = L.clock_spotify(st, 1.0, {'ok': False, 'state': 'error'})
        self.assertAlmostEqual(p, 11.0)

    def test_manual(self):
        st, p = L.clock_manual(None, 0.0, True, 1.0, 40, True)
        st, p = L.clock_manual(st, 2.0, True, 1.0, 40, True)
        self.assertAlmostEqual(p, 2.0)
        st, p = L.clock_manual(st, 3.0, True, 2.0, 40, True)
        self.assertAlmostEqual(p, 4.0)
        st, p = L.clock_manual(st, 4.0, False, 1.0, 40, True)
        self.assertAlmostEqual(p, 4.0)
        st, p = L.clock_manual(st, 4.0, True, 1.0, 40, True, [('seek', 39.5)])
        st, p = L.clock_manual(st, 5.0, True, 1.0, 40, True)
        self.assertAlmostEqual(p, 0.5)                                    # looped
        st, p = L.clock_manual(st, 5.0, True, 1.0, 40, False, [('seek', 39.5)])
        st, p = L.clock_manual(st, 7.0, True, 1.0, 40, False)
        self.assertAlmostEqual(p, 40.0)                                   # holds at the end
        st, p = L.clock_manual(st, 7.0, True, 1.0, 40, False, [('restart',)])
        self.assertEqual(p, 0.0)
        st, p = L.clock_manual(st, 8.0, True, -1.0, 40, False)
        self.assertEqual(p, 0.0)                                          # backwards stops at 0


class Matching(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(L.norm('Bohemian Rhapsody - Remastered 2011'), 'bohemian rhapsody')
        self.assertEqual(L.norm('Song (feat. X) [Live]'), 'song')
        self.assertEqual(L.norm("Don't  Stop!"), 'don t stop')
        self.assertEqual(L.norm('پسرور'), 'پسرور')

    def test_find(self):
        idx = L.build_index([('/l/Queen - Bohemian Rhapsody.lrc', {}),
                             ('/l/4uLU6hMCjMI75M1A2tKUQC.lrc', {}),
                             ('/l/whatever.lrc', {'ti': 'Tagged Song', 'ar': 'Some Band'})])
        self.assertEqual(L.find_lrc(idx, 'spotify:track:4uLU6hMCjMI75M1A2tKUQC', 'A', 'B'), '/l/4uLU6hMCjMI75M1A2tKUQC.lrc')
        self.assertEqual(L.find_lrc(idx, 'spotify:track:zzz', 'Queen', 'Bohemian Rhapsody - Remastered 2011'),
                         '/l/Queen - Bohemian Rhapsody.lrc')
        self.assertEqual(L.find_lrc(idx, '', 'Some Band, Guest', 'Tagged Song'), '/l/whatever.lrc')
        self.assertEqual(L.find_lrc(idx, '', 'Other', 'Bohemian Rhapsody'), '/l/Queen - Bohemian Rhapsody.lrc')  # title only
        self.assertIsNone(L.find_lrc(idx, '', 'No', 'Match'))

    def test_pick_source(self):
        play = {'ok': True, 'state': 'playing'}
        self.assertEqual(L.pick_source('auto', play, False), 'spotify')
        self.assertEqual(L.pick_source('auto', {'ok': True, 'state': 'notrunning'}, False), 'manual')
        self.assertEqual(L.pick_source('auto', None, True), 'chop')
        self.assertEqual(L.pick_source('manual', play, True), 'manual')


if __name__ == '__main__':
    unittest.main()
