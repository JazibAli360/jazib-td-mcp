"""Offline tests: TL_timeline phase 3 (builders/timeline_record_logic.py, builders/timeline_record.py generated code,
tools/timeline_render.py with ffmpeg when present). Run: python3 -I -m unittest discover -s test -p 'test_timeline*.py'"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'builders'))
import timeline_record_logic as RL  # noqa: E402
import timeline_logic as TL  # noqa: E402

FF = shutil.which('ffmpeg')


def clip(i, start, dur, src='a.mov', fade=0.0, track=0, speed=1.0, cin=0.0):
    return {'id': i, 'track': track, 'start': start, 'dur': dur, 'src': src, 'in': cin, 'speed': speed, 'fade': fade,
            'enabled': True}


class Plan(unittest.TestCase):
    def test_frames_exact(self):
        self.assertEqual(RL.record_frames(0, 5, 60), 300)
        self.assertEqual(RL.record_frames(1.1, 3.1, 30), 60)
        self.assertEqual(RL.record_frames(0, 0.1, 30), 3)
        self.assertEqual(RL.record_frames(0, 0.101, 30), 4)
        self.assertEqual(RL.record_frames(2, 2, 30), 0)

    def test_cooks(self):
        self.assertEqual(RL.record_plan(0, 5, 60, 60)['cooks'], 300)
        self.assertEqual(RL.record_plan(0, 2, 30, 60)['cooks'], 120)     # T-64: frames * rate / fps
        with self.assertRaises(ValueError):
            RL.record_plan(3, 3, 30, 60)

    def test_take_time_no_drift(self):
        p = RL.record_plan(1.0, 6.0, 60, 60)
        self.assertEqual(TL.frame_of(RL.take_time(p, 299), 60), 60 + 299)
        for k in range(0, 300, 7):
            self.assertEqual(TL.frame_of(RL.take_time(p, k), 60) - 60, k)


class Mix(unittest.TestCase):
    def test_segments_range_and_master(self):
        cl = [clip('a', 0, 6), clip('b', 4, 4, src='b.mov'), clip('c', 1, 1, speed=2.0)]
        segs, sk = RL.audio_segments(cl, lambda s: True, 2, 7, master='m.wav', master_offset=1.0)
        by = dict((s['id'], s) for s in segs)
        self.assertEqual(sk, ['c'])
        self.assertAlmostEqual(by['a']['src_start'], 2.0)
        self.assertAlmostEqual(by['a']['dur'], 4.0)
        self.assertAlmostEqual(by['b']['at'], 2.0)
        self.assertAlmostEqual(by['b']['dur'], 3.0)
        self.assertAlmostEqual(by['b']['fade_in'], 2.0)        # crossfade over the overlap 4..6, like the picture
        self.assertAlmostEqual(by['a']['fade_out'], 0.0)
        self.assertAlmostEqual(by['__master__']['src_start'], 1.0)
        self.assertAlmostEqual(by['__master__']['dur'], 5.0)

    def test_no_audio_skipped(self):
        segs, _ = RL.audio_segments([clip('a', 0, 2)], lambda s: False, 0, 2)
        self.assertEqual(segs, [])

    def test_envelope_matches_clip_weight(self):
        sys.path.insert(0, os.path.join(ROOT, 'builders'))
        import timeline_clips_logic as CL
        cl = [clip('a', 0, 6), clip('b', 4, 4, fade=0.5)]
        segs, _ = RL.audio_segments(cl, lambda s: True, 0, 8)
        b = [s for s in segs if s['id'] == 'b'][0]
        expr = RL._env_expr(b)
        for t in (4.0, 5.0, 6.5, 7.75, 7.99):
            v = eval(expr.replace('clip(', '_clip(').replace('min(', '_min('),
                     {'t': t - 4.0, '_clip': lambda x, a, c: max(a, min(c, x)), '_min': min})
            self.assertAlmostEqual(v, CL.clip_weight(CL.parse_clips(CL.clips_to_rows(cl))[1], t,
                                                     CL.parse_clips(CL.clips_to_rows(cl))), places=6)

    def test_mix_cmd_shape(self):
        segs, _ = RL.audio_segments([clip('a', 0, 2)], lambda s: True, 0, 2, master='m.wav')
        argv = RL.mix_cmd(segs, 2.0, 'o.wav')
        fc = argv[argv.index('-filter_complex') + 1]
        self.assertIn('amix=inputs=3', fc)
        self.assertIn('whole_len=96000', fc)
        self.assertIn('adelay=delays=0S', fc)


class Export(unittest.TestCase):
    def test_markers_round_trip(self):
        ms = [(8.0, 'Drop'), (0.0, 'Intro'), (12.5, 'Say "hi", go')]
        for fmt in RL.EXPORT_FORMATS:
            back = RL.parse_markers_text(RL.markers_text(ms, fmt, 30.0), fmt)
            self.assertEqual([t for t, _ in back], [0.0, 8.0, 12.5])
            self.assertEqual(back[0][1], 'Intro')
        js = json.loads(RL.markers_text(ms, 'ae', 30.0))
        self.assertEqual(js['markers'][1], {'time': 8.0, 'comment': 'Drop', 'duration': 0.0, 'frame': 240})
        with self.assertRaises(ValueError):
            RL.markers_text(ms, 'xml')

    def test_lanes_csv(self):
        txt = RL.lanes_csv(['x'], lambda n, t: t * 2, 0, 1, 30)
        rows = txt.strip().splitlines()
        self.assertEqual(len(rows), 31)
        self.assertEqual(rows[16].split(',')[2], repr(round(2 * 15 / 30.0, 7)))


class SyncHelpers(unittest.TestCase):
    def test_onsets_flash_pairs(self):
        x = [0.0] * 4800
        x[1200] = 0.5
        x[1201] = 0.5
        x[3600] = -0.6
        self.assertEqual(RL.onsets(x, 4800), [0.25, 0.75])
        self.assertEqual(RL.flash_frames([0, 0.9, 0.9, 0, 0.8]), [1, 4])
        self.assertEqual([round(v, 6) for v in RL.pair_offsets([0.25, 2.0], [0.26, 0.75])], [0.01])


class Generated(unittest.TestCase):
    def test_runtime_compiles_ascii(self):
        src = open(os.path.join(ROOT, 'builders', 'timeline_record.py')).read()
        self.assertTrue(all(ord(c) < 128 for c in src))
        ns = {'TL_ROOT': os.path.join(ROOT, 'builders')}
        exec(src, ns)
        for k in ('REC_RT', 'PUMP', 'REC_PARS_CB'):
            compile(ns[k], k, 'exec')
        ops_ = [o for s in ns['STAGES_RECORD'] for o in s['ops']]
        self.assertEqual(len(ops_), len(set(ops_)))


@unittest.skipUnless(FF, 'ffmpeg not installed')
class RenderTool(unittest.TestCase):
    def test_mux_and_check_synthetic(self):
        d = tempfile.mkdtemp()
        try:
            src = os.path.join(d, 'cf.mov')
            subprocess.run([FF, '-v', 'error', '-y', '-f', 'lavfi', '-i',
                            "color=black:s=64x64:r=60:d=2,format=gray,geq=lum='if(eq(mod(N\\,30)\\,0)\\,235\\,16)'",
                            '-f', 'lavfi', '-i',
                            "aevalsrc='if(lt(mod(t\\,0.5)\\,0.004)\\,0.8*sin(2*PI*2000*t)\\,0)':s=48000:d=2",
                            '-c:v', 'mpeg4', '-q:v', '2', '-c:a', 'pcm_s16le', '-shortest', src], check=True)
            vid = os.path.join(d, 'take_video.mov')
            subprocess.run([FF, '-v', 'error', '-y', '-i', src, '-frames:v', '90', '-an', '-c:v', 'mpeg4', '-q:v',
                            '2', vid], check=True)
            p = RL.record_plan(0, 1.5, 60, 60)
            segs, _ = RL.audio_segments([clip('cf', 0, 2, src=src)], lambda s: True, 0, 1.5)
            pl = dict(p, video=vid, out=os.path.join(d, 'take.mov'), segments=segs)
            pf = os.path.join(d, 'plan.json')
            json.dump(pl, open(pf, 'w'))
            tool = os.path.join(ROOT, 'tools', 'timeline_render.py')
            r = subprocess.run([sys.executable, '-I', tool, 'mux', pf], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            rep = json.loads(r.stdout)
            self.assertEqual(rep['frames_counted'], 90)
            r = subprocess.run([sys.executable, '-I', tool, 'check', pl['out'], '--fps', '60', '--master-phase',
                                '99'], capture_output=True, text=True)
            rep = json.loads(r.stdout)
            self.assertEqual(rep['flash_frames'], [0, 30, 60])
            self.assertLess(rep['clip_offset_max_frames'], 0.1)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
