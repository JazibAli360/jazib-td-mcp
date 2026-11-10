"""Offline tests for builders/previz_stage_logic.py (no TD)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders'))
import previz_stage_logic as L  # noqa: E402


class Wall(unittest.TestCase):
    def test_flat_default_16x9(self):
        lay = L.face_layout(L.preset_faces('flat'), gap=1.0, elev=1.5)
        self.assertEqual(len(lay['faces']), 1)
        f = lay['faces'][0]
        self.assertAlmostEqual(f['cols'][0][0], -6.0)
        self.assertAlmostEqual(f['cols'][-1][0], 6.0)
        self.assertAlmostEqual(lay['aspect'], 16 / 9.0, places=6)
        self.assertEqual((f['u0'], f['u1'], f['v0'], f['v1']), (0.0, 1.0, 0.0, 1.0))
        self.assertAlmostEqual(f['y0'], 1.5)

    def test_sides_symmetric_folded_forward(self):
        lay = L.face_layout(L.preset_faces('sides', sidefold=30), gap=1.5)
        left, main, right = lay['faces']
        self.assertAlmostEqual(left['cols'][0][0], -right['cols'][-1][0], places=6)
        self.assertAlmostEqual(left['cols'][0][1], right['cols'][-1][1], places=6)
        self.assertGreater(right['cols'][-1][1], 0.5)  # folded toward the audience
        for fc in lay['faces']:
            self.assertAlmostEqual(L.length2d(fc['cols']), {'main': 12.0}.get(fc['name'], 4.0), places=6)

    def test_span_uv_windows_tile(self):
        faces = L.preset_faces('custom', custom_rows=[(6, 3, 10, 0, 0), (10, 4, 0, 30, 0), (6, 3, 10, 0, 0)])
        lay = L.face_layout(faces, gap=0.5, uvmode='span')
        us = [(f['u0'], f['u1']) for f in lay['faces']]
        self.assertAlmostEqual(us[0][0], 0.0)
        self.assertAlmostEqual(us[-1][1], 1.0)
        for a, b in zip(us, us[1:]):
            self.assertAlmostEqual(a[1], b[0])
        self.assertAlmostEqual(lay['span_w'], 22.0)
        self.assertAlmostEqual(lay['aspect'], 22.0 / 4.0)

    def test_curve_keeps_arc_length_and_bends_forward(self):
        lay = L.face_layout(L.preset_faces('flat', curve=40))
        f = lay['faces'][0]
        self.assertAlmostEqual(L.length2d(f['cols']), 12.0, places=6)
        self.assertGreater(f['cols'][0][1], 0.3)
        self.assertGreater(f['cols'][-1][1], 0.3)
        self.assertAlmostEqual(f['cols'][len(f['cols']) // 2][1], 0.0, places=6)

    def test_repeat_uv(self):
        lay = L.face_layout(L.preset_faces('sides'), uvmode='repeat')
        for f in lay['faces']:
            self.assertEqual((f['u0'], f['u1']), (0.0, 1.0))

    def test_mesh_counts(self):
        lay = L.face_layout(L.preset_faces('flat', curve=20))
        pts, quads = L.wall_mesh(lay)
        n = len(lay['faces'][0]['cols'])
        self.assertEqual(len(pts), 2 * n)
        self.assertEqual(len(quads), n - 1)
        self.assertTrue(all(0 <= i < len(pts) for q in quads for i in q))

    def test_custom_empty_falls_back(self):
        self.assertEqual(len(L.preset_faces('custom', custom_rows=[])), 1)


class Crowd(unittest.TestCase):
    def test_seeded_and_counted(self):
        a = L.crowd_rows(500, 10, 0.6, 0.1, 7, 14.0, hands=0.2)
        b = L.crowd_rows(500, 10, 0.6, 0.1, 7, 14.0, hands=0.2)
        c = L.crowd_rows(500, 10, 0.6, 0.1, 8, 14.0, hands=0.2)
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(len(a), 500)
        self.assertTrue(all(z >= 14.0 - 0.6 for _x, z, *_ in a))
        self.assertTrue(all(0.9 - 1e-9 <= s <= 1.1 + 1e-9 for _x, _z, s, *_ in a))
        frac = sum(r[5] for r in a) / 500.0
        self.assertTrue(0.12 < frac < 0.28)

    def test_zero(self):
        self.assertEqual(L.crowd_rows(0, 10, 0.6, 0.1, 1, 10), [])


class Analysis(unittest.TestCase):
    def grid(self):
        # 4 cols x 2 rows: left half red, right half blue
        g = []
        for _r in range(2):
            g += [(1, 0, 0), (1, 0, 0), (0, 0, 1), (0, 0, 1)]
        return g

    def test_regions(self):
        a = L.analyse(self.grid(), 4, 2, [(0.0, 0.5), (0.5, 1.0)])
        self.assertEqual(a['left'], (1, 0, 0))
        self.assertEqual(a['right'], (0, 0, 1))
        self.assertEqual(a['avg'], (0.5, 0, 0.5))
        self.assertEqual(a['faces'], [(1, 0, 0), (0, 0, 1)])

    def test_dominant_prefers_saturated(self):
        g = [(0.5, 0.5, 0.5)] * 7 + [(0, 1, 0)]
        d = L.dominant(g)
        self.assertGreater(d[1], 0.9)
        self.assertEqual(L.dominant([(0.3, 0.3, 0.3)] * 4), (0.3, 0.3, 0.3))

    def test_beam_colour_modes(self):
        a = L.analyse(self.grid(), 4, 2, [(0.0, 0.5), (0.5, 1.0)])
        self.assertEqual(L.beam_colour('leftright', 0.1, a), (1, 0, 0))
        self.assertEqual(L.beam_colour('leftright', 0.9, a), (0, 0, 1))
        self.assertEqual(L.beam_colour('perface', 0.8, a, [(0.0, 0.5), (0.5, 1.0)]), (0, 0, 1))
        self.assertEqual(L.beam_colour('average', 0.8, a), (0.5, 0, 0.5))

    def test_lag(self):
        self.assertEqual(L.lag_alpha(1 / 60, 0), 1.0)
        a = L.lag_alpha(1 / 60.0, 0.5)
        v = 0.0
        for _ in range(30):  # 0.5 s = one time constant
            v += (1.0 - v) * a
        self.assertAlmostEqual(v, 1 - math.exp(-1), places=3)
        self.assertEqual(L.lerp_follow((1, 1, 1), (1, 0, 0), 0), (1, 1, 1))
        self.assertEqual(L.lerp_follow((1, 1, 1), (1, 0, 0), 1), (1, 0, 0))


class Beams(unittest.TestCase):
    def test_euler_roundtrip(self):
        for pan in (-60, -10, 0, 25, 70):
            for tilt in (0, 20, 45, 80):
                d = L.dir_from_angles(pan, tilt)
                rx, rz = L.aim_to_euler(d)
                e = L.euler_to_dir(rx, rz)
                for a, b in zip(d, e):
                    self.assertAlmostEqual(a, b, places=6)

    def test_rig_fan(self):
        rig = L.beam_rig(5, 10, 9, 2, 60, 30, 0, 0, 0)
        self.assertAlmostEqual(rig[0][0], -5)
        self.assertAlmostEqual(rig[-1][0], 5)
        self.assertAlmostEqual(rig[0][3], -30)
        self.assertAlmostEqual(rig[2][3], 0)
        self.assertEqual(len(L.beam_rig(1, 10, 9, 2, 60, 30, 0, 0, 0)), 1)

    def test_strobe(self):
        self.assertEqual(L.strobe_gate(0.3, 4, 0), 1.0)
        self.assertEqual(L.strobe_gate(0.0, 2, 1.0), 1.0)
        self.assertEqual(L.strobe_gate(0.3, 2, 1.0), 0.0)


class Camera(unittest.TestCase):
    def test_presets_look_at_stage(self):
        for p in L.CAM_ORDER:
            eye, tgt = L.cam_pose(p)
            self.assertGreater(eye[2], tgt[2])  # all in front of the wall
        eye, _ = L.cam_pose('foh')
        self.assertAlmostEqual(eye[2], 30.0, places=6)

    def test_orbit_keeps_distance(self):
        e0, t = L.cam_pose('orbit')
        e1, _ = L.cam_pose('orbit', yaw=90)
        d0 = math.dist(e0, t)
        d1 = math.dist(e1, t)
        self.assertAlmostEqual(d0, d1, places=6)
        self.assertGreater(e1[0], 10)
        e2, _ = L.cam_pose('orbit', dist=2)
        self.assertAlmostEqual(math.dist(e2, t), 2 * d0, places=6)

    def test_scale(self):
        self.assertEqual(L.wall_scale(12, 6.75), 1.0)
        self.assertAlmostEqual(L.wall_scale(24, 6.75), 2.0)




class Quality(unittest.TestCase):
    def test_levels(self):
        self.assertEqual(L.quality_settings('high', 1920, 1080, 'aa4'), (1920, 1080, 'aa4'))
        self.assertEqual(L.quality_settings('medium', 1920, 1080, 'aa4'), (1440, 810, 'aa2'))
        self.assertEqual(L.quality_settings('medium', 1920, 1080, 'aa1'), (1440, 810, 'aa1'))
        self.assertEqual(L.quality_settings('draft', 1920, 1080, 'aa8mid'), (960, 540, 'aa1'))
        self.assertEqual(L.quality_settings('bogus', 64, 20, 'aa2'), (64, 20, 'aa2'))
        self.assertEqual(L.quality_settings('draft', 20, 20, 'aa2')[:2], (16, 16))


class CrowdSway(unittest.TestCase):
    """Perf wave 2: the GPU sway (crowd_xf) keeps the Noise CHOPs' statistics (std 0.27 x amp, temporal correlation
    0.84 / 0.53 / 0.27 / 0.10 at 0.5 / 1 / 1.5 / 2 s at Swayspeed 0.5, measured live on b2) and is off at Sway 0."""

    def _series(self, people=200, seconds=30.0, speed=0.5):
        ts = [500.0 + k / 30.0 for k in range(int(seconds * 30))]
        return [[L.crowd_sway(t, speed, 1.0, p)[0] for p in range(people)] for t in ts]

    def test_zero_sway_is_still(self):
        self.assertEqual(L.crowd_sway(123.4, 0.5, 0.0, 7), (0.0, 0.0))

    def test_std_and_correlation(self):
        import numpy as np
        a = np.array(self._series())
        self.assertAlmostEqual(a.std() / 6.0, 0.27, delta=0.03)          # rz amp = Sway x 6
        for lag, ref in ((15, 0.84), (30, 0.53), (45, 0.27), (60, 0.10)):   # 30 samples / s
            c = np.corrcoef(a[:-lag].ravel(), a[lag:].ravel())[0, 1]
            self.assertAlmostEqual(c, ref, delta=0.08, msg=lag)
        nb = np.corrcoef(a[:, :-1].ravel(), a[:, 1:].ravel())[0, 1]
        self.assertLess(abs(nb), 0.15)                                    # neighbours independent (CHOP 0.11)

    def test_continuous_across_cells(self):
        for u in (0.0, 1.0, 7.0):
            a = L.sway_noise(u - 1e-7, 3, 1)
            b = L.sway_noise(u + 1e-7, 3, 1)
            self.assertAlmostEqual(a, b, places=5)


class Builder(unittest.TestCase):
    SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders', 'previz_stage.py')).read()

    def test_no_noise_chops(self):
        self.assertNotIn('noiseCHOP', self.SRC)
        self.assertIn("'crowd_xf'", self.SRC)

    def test_crowd_glsl_compiles(self):
        import re
        import shutil
        import subprocess
        import tempfile
        if shutil.which('glslc') is None:
            self.skipTest('no glslc')
        g = re.search(r"CROWD_GLSL = r\'\'\'(.*?)\'\'\'", self.SRC, re.S).group(1)
        g = g % {'gain': L.SWAY_GAIN, 's0': L.SWAY_SALTS[0], 's1': L.SWAY_SALTS[1]}
        stub = ('#version 460\nuniform sampler2D sTD2DInputs[1];\nstruct TDTexInfo { vec4 res; vec4 depth; };\n'
                'uniform TDTexInfo uTDOutputInfo;\nlayout(rgba32f) uniform image2DArray mTDComputeOutputs[2];\n'
                'void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }\n')
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.comp')
            with open(p, 'w') as fh:
                fh.write(stub + g)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[:2000])

    def test_scripts_keep_channels(self):
        self.assertIn('def out_chans', self.SRC)
        self.assertEqual(self.SRC.count('m.out_chans(scriptOp'), 2)       # react + beams


if __name__ == '__main__':
    unittest.main()
