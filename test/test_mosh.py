"""tools/mosh.py: offline, needs only ffmpeg. Generated lavfi clips; checks frame counts + decodability."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import mosh  # noqa: E402

HAVE = bool(shutil.which('ffmpeg') or os.path.exists('/opt/homebrew/bin/ffmpeg'))


def gen(path, src='testsrc2', secs=3, fps=30):
    subprocess.run([mosh.FFMPEG, '-v', 'error', '-y', '-f', 'lavfi', '-i', '%s=size=320x240:rate=%d' % (src, fps),
                    '-t', str(secs), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', path], check=True)


def decodes(path):
    p = subprocess.run([mosh.FFMPEG, '-v', 'error', '-i', path, '-f', 'null', '-'], capture_output=True, text=True)
    return p.returncode == 0


class PureTests(unittest.TestCase):
    def mk(self, s):
        return [b'\x00\x00\x01\xb6' + bytes([{'I': 0, 'P': 0x40}[c]]) + bytes([i]) for i, c in enumerate(s)]

    def test_drop_keeps_first(self):
        v = self.mk('IPPIPPI')
        out = mosh.drop_iframes(v)
        self.assertEqual(''.join(mosh.vop_type(x) for x in out), 'IPPPP')

    def test_bloom_repeats_p(self):
        v = self.mk('IPPP')
        out = mosh.bloom(v, 0, 5)
        self.assertEqual(len(out), 4 + 5)
        self.assertEqual(mosh.vop_type(out[1]), 'P')

    def test_transition_no_b_iframe(self):
        out = mosh.transition_vops(self.mk('IPP'), self.mk('IPP'))
        self.assertEqual(''.join(mosh.vop_type(x) for x in out), 'IPPPP')

    def test_noise_keeps_header_and_len(self):
        d = bytes(range(256)) * 20
        o = mosh.noise_bytes(d, 10, 100, 1)
        self.assertEqual(len(o), len(d))
        self.assertEqual(o[:74], d[:74])
        self.assertNotEqual(o, d)


@unittest.skipUnless(HAVE, 'ffmpeg missing')
class FfmpegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.mkdtemp()
        cls.a = os.path.join(cls.td, 'a.mp4')
        cls.b = os.path.join(cls.td, 'b.mp4')
        gen(cls.a, 'testsrc2')
        gen(cls.b, 'mandelbrot')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.td, ignore_errors=True)

    def out(self, n):
        return os.path.join(self.td, n)

    def test_ifdrop_python(self):
        o = self.out('d.mov')
        mosh.job_ifdrop(self.a, o, size=320, cuts=[1.0, 2.0])
        info = mosh.probe(o)
        self.assertTrue(decodes(o))
        self.assertEqual(info['frames'], 88)  # 90 minus the 2 dropped keyframes
        self.assertEqual(info['w'], 320)

    def test_ifdrop_bsf_decodes(self):
        o = self.out('dbsf.mov')
        mosh.job_ifdrop(self.a, o, size=320, cuts=[1.5], use_bsf=True)
        self.assertTrue(decodes(o))
        self.assertGreaterEqual(mosh.probe(o)['frames'], 85)

    def test_stream_has_one_iframe_after_drop(self):
        m4v = self.out('s.m4v')
        mosh.encode_m4v(self.a, m4v, 320, 30, cuts=[1.0, 2.0])
        _, v = mosh.split_vops(mosh.read_bytes(m4v))
        self.assertEqual(sum(mosh.vop_type(x) == 'I' for x in v), 3)
        self.assertEqual(sum(mosh.vop_type(x) == 'I' for x in mosh.drop_iframes(v)), 1)

    def test_bloom_adds_frames(self):
        o = self.out('bl.mov')
        mosh.job_bloom(self.a, o, at=1.0, repeat=30, size=320)
        self.assertTrue(decodes(o))
        self.assertEqual(mosh.probe(o)['frames'], 90 + 30)

    def test_noise_decodes(self):
        o = self.out('n.mov')
        mosh.job_noise(self.a, o, amount=30000, seed=3, size=320)
        self.assertTrue(decodes(o))
        self.assertGreater(mosh.probe(o)['frames'], 60)

    def test_transition(self):
        o = self.out('t.mov')
        mosh.job_transition(self.a, self.b, o, dur=2.0, size=320)
        self.assertTrue(decodes(o))
        n = mosh.probe(o)['frames']
        self.assertTrue(90 + 58 <= n <= 90 + 60, n)

    def test_h264_and_exists_guard(self):
        o = self.out('h.mp4')
        self.assertEqual(mosh.job_ifdrop(self.a, o, size=320, codec='h264'), 'h264')
        self.assertTrue(decodes(o))
        with self.assertRaises(mosh.MoshError):
            mosh.job_ifdrop(self.a, o, size=320, codec='h264')

    def test_preset_and_cli(self):
        o = self.out('p.mov')
        self.assertEqual(mosh.main(['preset', 'bloom_burst', self.a, o, '--size', '320']), 0)
        self.assertTrue(decodes(o))
        self.assertEqual(mosh.main(['presets']), 0)
        self.assertEqual(mosh.main(['preset', 'nope', self.a, self.out('x.mov')]), 1)


if __name__ == '__main__':
    unittest.main()
