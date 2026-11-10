"""Offline tests for td_metavido: tools/metavido_logic.py (reference decoder) and td/metavido.py (GLSL strings, pose
order). The demo clip check runs when media/demo/metavido/TaiwanStreet1-H264.mp4 and ffmpeg are present. No TD.

Run from jazib-td-mcp/:  python3 -I -m unittest discover -s test -p 'test_metavido.py'
"""
import importlib.util
import math
import os
import shutil
import struct
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import metavido_logic as M  # noqa: E402

CLIP = os.path.join(ROOT, 'media', 'demo', 'metavido', 'TaiwanStreet1-H264.mp4')


def load_td():
    spec = importlib.util.spec_from_file_location('jazib_mv_test', os.path.join(ROOT, 'td', 'metavido.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TM = load_td()


def encode_frame(values):
    """Synthetic frame (bottom-first) with the 12 floats burnt into the blue barcode."""
    f = np.zeros((M.H, M.W, 3))
    for k, v in enumerate(values):
        w = struct.unpack('<I', struct.pack('<f', v))[0]
        for i in range(32):
            if (w >> i) & 1:
                f[i * 8:i * 8 + 8, k * 8:k * 8 + 8, 2] = 1.0
    return f


class Barcode(unittest.TestCase):
    def test_roundtrip(self):
        q = (0.1, -0.7, 0.05)
        vals = [1.5, 0.2, -3.0, q[0], q[1], q[2], -0.002, 0.01, 0.72, 0.1, 4.9, 0.25]
        m = M.decode_meta(encode_frame(vals))
        got = [m[k] for k in M.NAMES]
        self.assertEqual(np.float32(got).tolist(), np.float32(vals).tolist())
        self.assertTrue(m['valid'])
        self.assertAlmostEqual(m['rw'], math.sqrt(1 - sum(x * x for x in q)), 6)

    def test_invalid_when_empty(self):
        self.assertFalse(M.decode_meta(np.zeros((M.H, M.W, 3)))['valid'])


class Depth(unittest.TestCase):
    def test_hue_roundtrip(self):
        for d in (0.2, 1.0, 2.5, 4.0, 4.8):
            rgb = M.hue_encode(d, 0.1, 4.9)
            self.assertAlmostEqual(M.depth_from_rgb(rgb, 0.1, 4.9), d, 4)

    def test_depth_image_matches_scalar(self):
        f = np.zeros((M.H, M.W, 3))
        f[M.HH:, :M.HW] = M.hue_encode(2.0, 0.1, 4.9)
        f[M.HH + 10, 20] = M.hue_encode(3.3, 0.1, 4.9)
        d = M.depth_image(f, 0.1, 4.9, margin=1)
        self.assertEqual(d.shape, (M.HH, M.HW))
        self.assertAlmostEqual(float(d[10, 20]), 3.3, 4)
        self.assertAlmostEqual(float(d[0, 0]), 2.0, 4)


class Pose(unittest.TestCase):
    def test_euler_zxy_roundtrip(self):
        for q in ((0.0, 0.0, 0.0, 1.0), (0.1, 0.9, -0.05, 0.42), (0.3, -0.2, 0.6, 0.71)):
            n = math.sqrt(sum(x * x for x in q))
            q = tuple(x / n for x in q)
            R = M.quat_matrix(q)
            R2 = M.euler_matrix_zxy(*M.euler_zxy_deg(R))
            self.assertLess(max(abs(R[i][j] - R2[i][j]) for i in range(3) for j in range(3)), 1e-9)

    def test_identity_camera_unprojects_down_minus_z(self):
        m = {'px': 0, 'py': 0, 'pz': 0, 'rx': 0, 'ry': 0, 'rz': 0, 'rw': 1, 'sx': 0, 'sy': 0,
             'fov': math.radians(60), 'near': 0.1, 'far': 5, 'hash': 0, 'valid': True}
        p = M.unproject(m, 0.5, 0.5, 2.0)
        self.assertTrue(np.allclose(p, (0, 0, -2)))
        p = M.unproject(m, 0.5, 1.0, 1.0)  # top edge: y = tan(30 deg)
        self.assertAlmostEqual(p[1], math.tan(math.radians(30)), 9)
        m['pz'] = 3.0  # Unity +z = TD -z
        self.assertAlmostEqual(M.unproject(m, 0.5, 0.5, 1.0)[2], -4.0, 9)

    def test_pose_names_match_td(self):
        m = M.decode_meta(encode_frame([0, 0, 0, 0, 0, 0, 0, 0, 0.7, 0.1, 5, 0.5]))
        self.assertEqual(tuple(M.pose_td(m).keys()), TM.POSE_NAMES)


class TdModule(unittest.TestCase):
    def test_glsl(self):
        self.assertIn('uintBitsToFloat', TM.META_DECODE)
        self.assertIn('k * 8 + 3', TM.META_DECODE)
        for code in (TM.POSE, TM.DEPTH, TM.POINTS):
            self.assertIn('mat3 mvRot(', code)
        self.assertIn('float v[14]', TM.POSE)
        self.assertEqual([s[0] for s in TM.STAGES], ['meta_decode', 'pose', 'colour', 'depth', 'points'])
        for code in (TM.META_DECODE, TM.POSE, TM.COLOUR, TM.DEPTH, TM.POINTS):
            code.encode('ascii')

    def test_missing_file(self):
        with self.assertRaises(ValueError):
            TM.cmd_metavido('/nope/x.mp4')


@unittest.skipUnless(os.path.isfile(CLIP) and shutil.which('ffmpeg'), 'demo clip or ffmpeg missing')
class DemoClip(unittest.TestCase):
    def test_frame_299(self):
        f = M.read_frame_ffmpeg(CLIP, 299)
        m = M.decode_meta(f)
        self.assertTrue(m['valid'])
        self.assertAlmostEqual(m['hash'], 0.7405652403831482, 6)  # = TD index 300 on b4 (27 Oct, bit-exact)
        self.assertAlmostEqual(math.degrees(m['fov']), 41.5, 0)
        d = M.depth_image(f, m['near'], m['far'])
        self.assertTrue(m['near'] <= float(np.median(d)) <= m['far'])


if __name__ == '__main__':
    unittest.main()
