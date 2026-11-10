"""Offline tests for builders/io_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_io_logic.py'"""
import math
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import io_logic as L  # noqa: E402


def premult_ramp():
    a = np.arange(256, dtype=np.uint8)
    rgb = np.stack([np.full(256, 255), np.full(256, 128), np.zeros(256)], -1).astype(np.float64)
    pre = np.floor(rgb * (a[:, None] / 255.0) + 0.5).astype(np.uint8)
    return np.concatenate([pre, a[:, None]], -1)


class Alpha(unittest.TestCase):
    def test_table(self):
        self.assertEqual(L.alpha_mode('premult', 'premult'), L.M_PASS)
        self.assertEqual(L.alpha_mode('straight', 'premult'), L.M_PREMULT)
        self.assertEqual(L.alpha_mode('premult', 'straight'), L.M_UNPREMULT)
        self.assertEqual(L.alpha_mode('premult', 'none'), L.M_DROP_PREMULT)
        self.assertEqual(L.alpha_mode('straight', 'none'), L.M_DROP_STRAIGHT)
        self.assertEqual(L.alpha_mode('none', 'straight'), L.M_PASS)
        with self.assertRaises(ValueError):
            L.alpha_mode('x', 'premult')

    def test_roundtrip_error_bound(self):
        r = premult_ramp()
        self.assertTrue((r[:, :3].max(1) <= r[:, 3]).all())          # premult: rgb <= a
        back = L.convert_alpha(L.convert_alpha(r, 'premult', 'straight'), 'straight', 'premult')
        for i in range(256):
            a = int(r[i, 3])
            err = int(np.abs(back[i, :3].astype(int) - r[i, :3].astype(int)).max())
            bound = 0 if a == 255 else (int(math.ceil(255.0 / (2 * a))) if a else 0)
            self.assertLessEqual(err, max(bound, 1) if a else 0, (i, err))
        self.assertTrue((back[:, 3] == r[:, 3]).all())

    def test_zero_alpha_no_nan(self):
        z = np.array([[10, 20, 30, 0]], dtype=np.uint8)
        self.assertEqual(L.convert_alpha(z, 'premult', 'straight').tolist(), [[0, 0, 0, 0]])

    def test_drop(self):
        px = np.array([[100, 50, 0, 128]], dtype=np.uint8)
        self.assertEqual(L.convert_alpha(px, 'premult', 'none').tolist(), [[100, 50, 0, 255]])
        self.assertEqual(L.convert_alpha(px, 'straight', 'none').tolist(), [[50, 25, 0, 255]])

    def test_composite_models_differ(self):
        px = np.array([[128, 128, 128, 128]], dtype=np.uint8)
        bg = np.array([[0, 0, 0]], dtype=np.uint8)
        self.assertEqual(L.composite(px, bg, 'premult').tolist(), [[128, 128, 128]])
        self.assertEqual(L.composite(px, bg, 'straight').tolist(), [[64, 64, 64]])


class Names(unittest.TestCase):
    def test_match(self):
        names = ['MAC-A (Cam)', 'MAC-B (Cam)', 'MAC-B (Other)']
        self.assertEqual(L.match_source(names, 'MAC-B (Cam)'), 'MAC-B (Cam)')
        self.assertEqual(L.match_source(names, r'\(Cam\)$', prefer_host='MAC-B'), 'MAC-B (Cam)')
        self.assertEqual(L.match_source(names, 'other'), 'MAC-B (Other)')
        self.assertIsNone(L.match_source(names, 'nope'))
        self.assertEqual(L.ndi_source_name('MAC-A', 'Cam'), 'MAC-A (Cam)')

    def test_plan_reports_only(self):
        srcs = [{'kind': 'syphon', 'name': 'TD_x'}, {'kind': 'off'}, {'kind': 'movie', 'file': ''}, {'kind': 'off'}]
        sinks = [{'kind': 'syphon', 'src': 's1', 'name': 'TD_x'}, {'kind': 'syphon', 'src': 'bus', 'name': 'TD_x'},
                 {'kind': 'off'}, {'kind': 'ndi', 'src': 's2', 'name': 'a'}]
        r = L.plan_routes(srcs, sinks)
        self.assertEqual(len(r['routes']), 4)
        txt = ' | '.join(r['issues'])
        self.assertIn('same syphon sender name', txt)
        self.assertIn('loopback', txt)
        self.assertIn('s3: movie kind without a file', txt)


class Sizes(unittest.TestCase):
    def test_bandwidth(self):
        self.assertEqual(L.estimate_bandwidth(1080, 1920, 30, 'rgba8'), 248832000)
        self.assertEqual(L.hap_frame_bytes(1080, 1920, 'hapq'), 2073600)
        self.assertEqual(L.hap_frame_bytes(1080, 1920, 'hapqa'), 3110400)
        self.assertEqual(L.hap_frame_bytes(7488, 2880, 'hapq'), 21565440)
        self.assertEqual(L.estimate_bandwidth(1080, 1920, 60, 'hapq'), 2 * L.estimate_bandwidth(1080, 1920, 30, 'hapq'))
        self.assertIsNone(L.estimate_bandwidth(1080, 1920, 30, 'prores'))

    def test_pump_and_presets(self):
        self.assertEqual(L.pump_cooks(30, 60, 30), 60)
        for k, v in L.RECORD_PRESETS.items():
            self.assertIn(v['videocodec'], L.CODECS_31550, k)

    def test_res(self):
        self.assertIsNone(L.parse_res('input'))
        self.assertEqual(L.parse_res('1080x1920'), (1080, 1920))
        self.assertEqual(L.parse_res('custom', 640, 0), (640, 1))


class Bus(unittest.TestCase):
    def test_boundary(self):
        self.assertAlmostEqual(L.next_boundary(0.1, 120, 1), 0.5)
        self.assertAlmostEqual(L.next_boundary(0.5, 120, 1), 1.0)
        self.assertAlmostEqual(L.next_boundary(0.1, 120, 4), 2.0)

    def test_manual(self):
        st, o = L.bus_step(None, 0.0, {'mode': 'manual', 'mix': 0.3})
        self.assertEqual(o['mix'], 0.3)

    def test_bpm_cut_quantised(self):
        p = {'mode': 'bpm', 'bpm': 120, 'div': 1, 'xfadetime': 0.0}
        st, o = L.bus_step(None, 0.0, p)
        dt = 1 / 60.0
        st, o = L.bus_step(st, 0.10, p, ('cut',))
        self.assertEqual(o['armed'], 1)
        t = 0.10
        landed = None
        while t < 1.0:
            t += dt
            st, o = L.bus_step(st, t, p)
            if o['mix'] == 1.0 and landed is None:
                landed = t
        self.assertLess(abs(landed - 0.5), dt + 1e-9)          # within one frame of the beat

    def test_bpm_fade_curve(self):
        p = {'mode': 'bpm', 'bpm': 120, 'div': 1, 'xfadetime': 1.0, 'curve': 'smooth'}
        st, _ = L.bus_step(None, 0.0, p)
        st, _ = L.bus_step(st, 0.0, p, ('cut',))
        st, o = L.bus_step(st, 1.0, p)
        self.assertAlmostEqual(o['mix'], 0.5)
        self.assertEqual(o['fading'], 1)
        st, o = L.bus_step(st, 1.6, p)
        self.assertEqual(o['mix'], 1.0)
        st, o = L.bus_step(st, 1.7, p, ('cut',))                  # next cut goes back
        self.assertEqual(o['target'], 0.0)

    def test_stale(self):
        self.assertEqual(L.frame_hash_stale(None, 1, 0.0, 1.0), 0.0)
        self.assertEqual(L.frame_hash_stale(1, 1, 2.0, 1.0), 3.0)
        self.assertEqual(L.frame_hash_stale(1, 2, 2.0, 1.0), 0.0)


if __name__ == '__main__':
    unittest.main()
