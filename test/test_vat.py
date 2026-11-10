"""Offline tests for VAT (td_vat_load): tools/vat_logic.py (layout, frame logic, EXR, OBJ, sidecar), td/vat.py (pure
parts + registration in td/handlers.py) and, when Blender is installed, a real headless bake (tools/blender_vat.py
--make-demo wave, short range). No TouchDesigner.

Run from jazib-td-mcp/:  python3 -I -m unittest discover -s test -p 'test_vat.py'
"""
import importlib.util
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, HERE)
import vat_logic as V  # noqa: E402
import test_handlers as TH  # noqa: E402  (td stub + handlers)

handlers = TH.handlers
BLENDER = os.environ.get('BLENDER_PATH', '/Applications/Blender.app/Contents/MacOS/Blender')


def load_td_vat():
    spec = importlib.util.spec_from_file_location('jazib_vat_test', os.path.join(ROOT, 'td', 'vat.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


TV = load_td_vat()


class Layout(unittest.TestCase):
    def test_small_and_wrapped(self):
        self.assertEqual(V.layout(100, 10), {'width': 100, 'rows_per_frame': 1, 'height': 10})
        self.assertEqual(V.layout(10000, 3, max_w=4096), {'width': 4096, 'rows_per_frame': 3, 'height': 9})
        self.assertEqual(V.texel(4097, 2, 4096, 3), (1, 7))
        with self.assertRaises(ValueError):
            V.layout(10, 20000)
        with self.assertRaises(ValueError):
            V.layout(0, 1)

    def test_axis(self):
        self.assertEqual(V.to_td((1, 2, 3)), (1, 3, -2))
        self.assertTrue(np.allclose(V.to_td_np([[1, 2, 3]], 2.0), [[2, 6, -4]]))


class FramePick(unittest.TestCase):
    def test_loop_wraps(self):
        self.assertEqual(V.frame_pick(9.5, 10, 'loop'), (9, 0, 0.5))
        self.assertEqual(V.frame_pick(-0.5, 10, 'loop'), (9, 0, 0.5))
        self.assertEqual(V.frame_pick(23.0, 10, 'loop'), (3, 4, 0.0))

    def test_once_clamps(self):
        self.assertEqual(V.frame_pick(50, 10, 'once'), (9, 9, 0.0))
        self.assertEqual(V.frame_pick(-3, 10, 'once'), (0, 1, 0.0))

    def test_pingpong(self):
        self.assertEqual(V.frame_pick(130.25, 90, 'pingpong'), (47, 48, 0.75))  # live-checked on b4 (27 Oct)
        self.assertEqual(V.frame_pick(9, 10, 'pingpong'), (9, 9, 0.0))
        self.assertEqual(V.frame_pick(10, 10, 'pingpong')[0], 8)

    def test_no_interp_and_single(self):
        self.assertEqual(V.frame_pick(2.7, 10, 'loop', interp=False), (2, 3, 0.0))
        self.assertEqual(V.frame_pick(5, 1), (0, 0, 0.0))
        with self.assertRaises(ValueError):
            V.frame_pick(1, 5, 'bounce')


class Exr(unittest.TestCase):
    def test_roundtrip_and_orientation(self):
        rng = np.random.default_rng(1)
        fr = rng.normal(size=(5, 7, 3)).astype(np.float32)
        img = V.pack(fr, 3, 3)
        self.assertEqual(img.shape, (15, 3, 4))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.exr')
            V.write_exr(p, img)
            back = V.read_exr(p)
            self.assertTrue(np.array_equal(back, img))
            with open(p, 'rb') as f:
                data = f.read()
            self.assertEqual(data[:4], b'\x76\x2f\x31\x01')
            self.assertIn(b'channels\0chlist\0', data)
            # first chunk = EXR y 0 = the TOP row = our last row (bottom-first image)
            hdr_end = data.index(b'screenWindowWidth') + len(b'screenWindowWidth\0float\0') + 8 + 1
            first = struct.unpack('<Q', data[hdr_end:hdr_end + 8])[0]
            y, size = struct.unpack('<ii', data[first:first + 8])
            self.assertEqual((y, size), (0, 3 * 4 * 4))
            a_row = np.frombuffer(data, '<f4', 3, first + 8)  # channel A first (sorted ABGR)
            self.assertTrue(np.array_equal(a_row, img[-1, :, 3]))
        for f in range(5):
            self.assertTrue(np.allclose(V.unpack(img, f, 7, 3, 3), fr[f]))

    def test_sample_matches_lerp(self):
        fr = np.arange(4 * 2 * 3, dtype=np.float32).reshape(4, 2, 3)
        img = V.pack(fr, 2, 1)
        s = V.sample(img, 3.5, 4, 2, 2, 1, 'loop')
        self.assertTrue(np.allclose(s, (fr[3] + fr[0]) / 2))


class Obj(unittest.TestCase):
    def test_ids_in_uv_w(self):
        rest = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
        polys = [[0, 1, 2, 3]]
        uvs = [[(0, 0), (1, 0), (1, 1), (0, 1)]]
        txt = V.obj_text(rest, polys, uvs, 'hdr')
        nv, corners = V.read_obj_ids(txt)
        self.assertEqual(nv, 4)
        self.assertEqual(corners, [(0, 0.0), (1, 1.0), (2, 2.0), (3, 3.0)])
        self.assertTrue(txt.startswith('# hdr'))
        txt.encode('ascii')

    def test_shared_uv_split_per_point(self):
        rest = np.zeros((3, 3))
        txt = V.obj_text(rest, [[0, 1, 2]], [[(0.5, 0.5)] * 3])
        self.assertEqual(sum(1 for ln in txt.splitlines() if ln.startswith('vt ')), 3)


class Sidecar(unittest.TestCase):
    def good(self):
        lay = V.layout(10, 4)
        return V.sidecar('x', 4, 10, lay, 30, 1, 4, 1, {'mesh': 'x.obj', 'pos': 'x_pos.exr', 'nrm': None},
                         {'min': [0, 0, 0], 'max': [1, 1, 1]}, {'min': [0, 0, 0], 'max': [1, 1, 1]}, [])

    def test_checks_agree(self):
        s = self.good()
        self.assertEqual(V.check_sidecar(s), [])
        self.assertEqual(TV.check_sidecar(s), [])
        s2 = dict(s, height=5)
        self.assertTrue(V.check_sidecar(s2) and TV.check_sidecar(s2))
        self.assertTrue(TV.check_sidecar(dict(s, schema='x')))
        self.assertEqual(json.loads(V.dumps(s))['schema'], V.SCHEMA)

    def test_fps_with_step(self):
        s = V.sidecar('x', 2, 1, V.layout(1, 2), 30, 1, 3, 2, {}, {}, {}, [])
        self.assertEqual(s['fps'], 15.0)


class TdModule(unittest.TestCase):
    def test_glsl_shares_frame_logic(self):
        for src in (TV.VAT_VERTEX, TV.FRAME_POS_PIXEL):
            self.assertIn('void vatPick(', src)
            self.assertIn('ivec2 vatTexel(', src)
        self.assertIn('uv[0].z', TV.VAT_VERTEX)
        self.assertIn('TDOutputSwizzle', TV.VAT_PIXEL)

    def test_uniform_rows(self):
        vat, tim = TV.uniform_rows()
        self.assertEqual(len(vat), 4)
        self.assertEqual(len(tim), 4)
        self.assertIn("op('clock')['frames']", tim[0])
        self.assertIn('Loop.menuIndex', tim[1])

    def test_camera_defaults_fit(self):
        c = TV.camera_defaults({'bounds': {'min': [-1, 0, -1], 'max': [1, 2, 1]}}, 45.0, 1080 / 1920.)
        self.assertEqual(c['target'], [0.0, 1.0, 0.0])
        self.assertGreater(c['dist'], 3.0)

    def test_registered(self):
        for c in ('vat_load', 'metavido'):
            self.assertIn(c, handlers.COMMANDS)
            self.assertIn(c, handlers.MUTATING)
            self.assertIn(c, handlers.PRESAVE_CMDS)

    def test_bad_sidecar_refused(self):
        with self.assertRaises(ValueError):
            TV.cmd_vat_load({'schema': 'nope'}, '/x.obj', '/x.exr')


@unittest.skipUnless(os.path.isfile(BLENDER), 'Blender not installed')
class BlenderBake(unittest.TestCase):
    def test_wave_demo_bake(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([BLENDER, '-b', '--factory-startup', '--disable-autoexec', '--python',
                                os.path.join(ROOT, 'tools', 'blender_vat.py'), '--', '--out', d, '--make-demo', 'wave',
                                '--name', 'w', '--end', '8', '--step', '2'],
                               capture_output=True, text=True, timeout=240)
            line = next((ln for ln in r.stdout.splitlines() if ln.startswith('JZB_VAT ')), None)
            self.assertIsNotNone(line, r.stdout[-1500:] + r.stderr[-1500:])
            res = json.loads(line[8:])
            self.assertEqual(res['frames'], 4)  # 1, 3, 5, 7
            with open(res['sidecar']) as f:
                s = json.load(f)
            self.assertEqual(V.check_sidecar(s), [])
            self.assertEqual(s['fps'], 15.0)
            img = V.read_exr(os.path.join(d, s['files']['pos']))
            self.assertEqual(img.shape, (s['height'], s['width'], 4))
            a, b = V.unpack(img, 0, s['points'], s['width'], 1), V.unpack(img, 3, s['points'], s['width'], 1)
            self.assertGreater(float(np.abs(a - b).max()), 1e-3, 'the wave moves')
            self.assertLess(float(np.abs(a[:, 1]).max()), 0.6, 'Y-up: the wave height is on TD y')
            with open(os.path.join(d, s['files']['mesh'])) as f:
                nv, corners = V.read_obj_ids(f.read())
            self.assertEqual(nv, s['points'])
            self.assertTrue(all(pi == w for pi, w in corners))
            n = V.read_exr(os.path.join(d, s['files']['nrm']))[:, :, :3]
            self.assertTrue(np.allclose(np.linalg.norm(n[0], axis=1), 1.0, atol=1e-4))


if __name__ == '__main__':
    unittest.main()
