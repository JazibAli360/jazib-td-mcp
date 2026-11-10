"""Offline tests for builders/face_track_logic.py (no TD, no helper).
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_face_track.py'"""
import json
import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders'))
import face_track_logic as ftl  # noqa: E402

LAYOUT = json.dumps({'regions': [[r, ftl.DEFAULT_COUNTS[r]] for r in ftl.REGIONS]})
NPTS = sum(ftl.DEFAULT_COUNTS.values())
W = ftl.HEAD + 2 * NPTS


def answer_row(face_tl):
    """A helper row (origin bottom-left) from a face in top-left space."""
    x, y, w, h = face_tl['rect']
    row = [x, 1.0 - y - h, w, h, 0.1, 0.2, float('nan'), 0.9, 0.8]
    for r in ftl.REGIONS:
        pts = face_tl['regions'][r]
        for i in range(ftl.DEFAULT_COUNTS[r]):
            if pts:
                row += [pts[i][0], 1.0 - pts[i][1]]
            else:
                row += [float('nan'), float('nan')]
    return row


def pack(rows):
    flat = [v for r in rows for v in r]
    return struct.pack('<{}f'.format(len(flat)), *flat)


class Parse(unittest.TestCase):
    def test_counts_total_87(self):
        self.assertEqual(NPTS, 87)

    def test_zero_one_eight_faces(self):
        self.assertEqual(ftl.parse_landmarks(b'', W, 0, LAYOUT), [])
        f = ftl.fake_face(0.0, 0.3, 0.4, 0.2)
        got = ftl.parse_landmarks(pack([answer_row(f)]), W, 1, LAYOUT)
        self.assertEqual(len(got), 1)
        g = got[0]
        for a, b in zip(g['rect'], f['rect']):
            self.assertAlmostEqual(a, b, places=5)
        self.assertAlmostEqual(g['regions']['eye_l'][2][0], f['regions']['eye_l'][2][0], places=5)
        self.assertAlmostEqual(g['regions']['eye_l'][2][1], f['regions']['eye_l'][2][1], places=5)
        self.assertIsNone(g['pitch'])
        self.assertAlmostEqual(g['yaw'], 0.2, places=5)
        rows = [answer_row(ftl.fake_face(0.0, 0.1 + 0.1 * i, 0.5, 0.1)) for i in range(8)]
        self.assertEqual(len(ftl.parse_landmarks(pack(rows), W, 8, LAYOUT)), 8)

    def test_truncated_and_bad_width(self):
        f = ftl.fake_face()
        data = pack([answer_row(f)])
        with self.assertRaises(ValueError):
            ftl.parse_landmarks(data[:-4], W, 1, LAYOUT)
        with self.assertRaises(ValueError):
            ftl.parse_landmarks(data, W - 2, 1, LAYOUT)

    def test_missing_region_is_empty(self):
        f = ftl.fake_face()
        f['regions']['pupil_l'] = []
        g = ftl.parse_landmarks(pack([answer_row(f)]), W, 1, LAYOUT)[0]
        self.assertEqual(g['regions']['pupil_l'], [])
        self.assertEqual(len(g['regions']['jaw']), 17)

    def test_layout_fallback(self):
        self.assertEqual(ftl.parse_layout('nope'), [(r, ftl.DEFAULT_COUNTS[r]) for r in ftl.REGIONS])

    def test_y_flip(self):
        # a point at helper y = 0.9 (bottom-left origin) is near the TOP of the image
        f = ftl.fake_face(0, 0.5, 0.2, 0.2)
        g = ftl.parse_landmarks(pack([answer_row(f)]), W, 1, LAYOUT)[0]
        self.assertLess(ftl.centroid(g['regions']['eye_l'])[1], ftl.centroid(g['regions']['lips_outer'])[1])


class Measures(unittest.TestCase):
    def test_open_vs_closed_eye_and_mouth(self):
        open_f = ftl.fake_face(math.pi / 2 / 0.9, aspect=1.0)  # blink factor 1
        shut_f = ftl.fake_face(0.0, aspect=1.0)                 # blink factor 0.15
        mo, ms = ftl.measures(open_f), ftl.measures(shut_f)
        self.assertGreater(mo['eye_l_raw'], ms['eye_l_raw'] * 3)
        self.assertGreaterEqual(mo['eye_open_l'], ms['eye_open_l'])
        wide = ftl.fake_face(math.pi / 2 / 1.7, aspect=1.0)
        shut = ftl.fake_face(-math.pi / 2 / 1.7, aspect=1.0)
        self.assertGreater(ftl.measures(wide)['mouth_raw'], ftl.measures(shut)['mouth_raw'])

    def test_roll_known_angle(self):
        f = ftl.fake_face(1.0, 0.5, 0.5, 0.3, aspect=1.0)
        ang = math.radians(12.0)
        cx, cy = 0.5, 0.5

        def rot(p):
            x, y = p[0] - cx, p[1] - cy
            return (cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang))
        f['regions'] = {r: [rot(p) for p in pts] for r, pts in f['regions'].items()}
        self.assertAlmostEqual(math.degrees(ftl.measures(f)['roll']), 12.0, delta=0.5)

    def test_smile_sign(self):
        flat = [(0.4 + 0.02 * i, 0.5) for i in range(11)] + [(0.5, 0.52)]
        up = [(0.4, 0.47), (0.45, 0.5), (0.5, 0.51), (0.55, 0.5), (0.6, 0.47), (0.5, 0.53)]
        down = [(x, 1.0 - y) for x, y in up]
        self.assertGreater(ftl.smile(up), 0.0)
        self.assertLess(ftl.smile(down), 0.0)
        self.assertAlmostEqual(ftl.smile(flat[:11]), 0.0, places=6)

    def test_norm(self):
        self.assertEqual(ftl.norm(0.5, 0.0, 1.0), 0.5)
        self.assertEqual(ftl.norm(2.0, 0.0, 1.0), 1.0)
        self.assertEqual(ftl.norm(0.3, 0.3, 0.3), 0.0)


class Smoothing(unittest.TestCase):
    def test_step_no_overshoot(self):
        f = ftl.OneEuro(1.0, 0.0)
        f(0.0, 0.0)
        ys = [f(1.0, t / 60.0) for t in range(1, 240)]
        self.assertTrue(all(0.0 <= y <= 1.0 for y in ys))
        self.assertTrue(all(b >= a for a, b in zip(ys, ys[1:])))
        self.assertGreater(ys[-1], 0.99)
        self.assertLess(ys[0], 0.2)

    def test_smooth_off_is_identity(self):
        self.assertIsNone(ftl.smooth_params(0))
        tr = ftl.Tracker(1)
        f = ftl.fake_face(0.0)
        s = tr.update([f], 0.0, smooth=0.0)[0]
        self.assertEqual(s['face']['rect'], f['rect'])

    def test_smooth_lags(self):
        tr = ftl.Tracker(1)
        tr.update([ftl.fake_face(0, 0.4, 0.5)], 0.0, smooth=0.8)
        s = tr.update([ftl.fake_face(0, 0.5, 0.5)], 1 / 30.0, smooth=0.8)[0]
        cx = s['face']['rect'][0] + s['face']['rect'][2] / 2
        self.assertTrue(0.4 < cx < 0.5)


class Tracking(unittest.TestCase):
    def test_hold_then_fade(self):
        tr = ftl.Tracker(1, hold=3, fade=2)
        tr.update([ftl.fake_face()], 0.0)
        tr.update([], 0.03)  # lost = 1
        pres = []
        for _ in range(6):
            s = tr.update(None, 0.0)[0]
            pres.append(s['present'] if s else 0.0)
        self.assertEqual(pres, [1.0, 1.0, 0.5, 0.0, 0.0, 0.0])

    def test_stale(self):
        self.assertTrue(ftl.stale(None, 1.0))
        self.assertFalse(ftl.stale(1.0, 1.1))
        self.assertTrue(ftl.stale(1.0, 1.3))

    def test_answers_stop_slot_fades(self):
        # live bug 26 Oct (31550): helper gone -> no answers -> update(None) never aged a slot whose lost == 0, so the
        # last pose held forever. The runtime now feeds [] while stale(); this is that sequence.
        tr = ftl.Tracker(1, hold=3, fade=2)
        tr.update([ftl.fake_face()], 0.0)
        pres = []
        for k in range(8):
            t = 0.3 + k / 60.0
            new = [] if ftl.stale(0.0, t) else None
            s = tr.update(new, t)[0]
            pres.append(s['present'] if s else 0.0)
        self.assertEqual(pres[-1], 0.0)
        self.assertIn(0.5, pres)

    def test_ids_do_not_swap(self):
        tr = ftl.Tracker(2)
        a, b = ftl.fake_face(0, 0.3, 0.5, 0.2), ftl.fake_face(0, 0.7, 0.5, 0.25)
        s = tr.update([a, b], 0.0)
        ids = {round(x['cx'], 1): x['id'] for x in s}
        a2, b2 = ftl.fake_face(0, 0.32, 0.5, 0.2), ftl.fake_face(0, 0.68, 0.5, 0.25)
        s2 = tr.update([b2, a2], 0.03)
        ids2 = {round(x['cx'], 1): x['id'] for x in s2}
        self.assertEqual(ids[0.3], ids2[0.3])
        self.assertEqual(ids[0.7], ids2[0.7])

    def test_maxfaces_largest_first(self):
        tr = ftl.Tracker(1)
        small, big = ftl.fake_face(0, 0.3, 0.5, 0.1), ftl.fake_face(0, 0.7, 0.5, 0.3)
        s = tr.update([small, big], 0.0)
        self.assertEqual(len(s), 1)
        self.assertGreater(s[0]['cx'], 0.6)

    def test_min_conf(self):
        f = ftl.fake_face()
        f['conf'] = 0.2
        self.assertIsNone(ftl.Tracker(1).update([f], 0.0, min_conf=0.5)[0])


class Channels(unittest.TestCase):
    def test_names_and_zero_fill(self):
        names = ftl.point_channels(2)
        self.assertEqual(len(names), 2 * 87 * 2)
        self.assertIn('f1_eye_l_03x', names)
        self.assertIn('f2_lips_outer_13y', names)
        tr = ftl.Tracker(2)
        slots = tr.update([ftl.fake_face()], 0.0)
        vals = ftl.point_values(slots, 2)
        self.assertEqual(sorted(vals), sorted(names))
        self.assertEqual(vals['f2_jaw_00x'], 0.0)
        self.assertNotEqual(vals['f1_jaw_00x'], 0.0)

    def test_controls(self):
        tr = ftl.Tracker(2)
        slots = tr.update([ftl.fake_face()], 0.0)
        c = ftl.control_values(slots, 2, aspect=16 / 9.0)
        self.assertEqual(c['facecount'], 1.0)
        self.assertEqual(c['f1_present'], 1.0)
        self.assertEqual(c['f2_present'], 0.0)
        self.assertEqual(len(c), 1 + 2 * len(ftl.CTL_NAMES))


class Shapes(unittest.TestCase):
    def test_point_in_poly_convex_concave(self):
        sq = [(0, 0), (1, 0), (1, 1), (0, 1)]
        self.assertTrue(ftl.point_in_poly((0.5, 0.5), sq))
        self.assertFalse(ftl.point_in_poly((1.5, 0.5), sq))
        u = [(0, 0), (3, 0), (3, 3), (2, 3), (2, 1), (1, 1), (1, 3), (0, 3)]
        self.assertFalse(ftl.point_in_poly((1.5, 2.0), u))
        self.assertTrue(ftl.point_in_poly((0.5, 2.0), u))

    def test_mask_area_ratio(self):
        tri = [(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)]
        n = 200
        inside = sum(ftl.point_in_poly(((i + .5) / n, (j + .5) / n), tri) for i in range(n) for j in range(n))
        self.assertAlmostEqual(inside / float(n * n), ftl.poly_area(tri), delta=0.01)

    def test_masks_nested(self):
        tr = ftl.Tracker(1)
        slots = tr.update([ftl.fake_face(1.0, aspect=1.0)], 0.0)
        polys = ftl.mask_polygons(slots)
        kinds = [k for k, _ in polys]
        self.assertEqual(kinds, [ftl.MASK_FACE, ftl.MASK_EYES, ftl.MASK_EYES, ftl.MASK_MOUTH])
        face = polys[0][1]
        for k, p in polys[1:]:
            for pt in p:
                self.assertTrue(ftl.point_in_poly(pt, face), (k, pt))

    def test_grow(self):
        sq = [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)]
        self.assertGreater(ftl.poly_area(ftl.grow(sq, 0.05)), ftl.poly_area(sq))
        self.assertLess(ftl.poly_area(ftl.grow(sq, -0.05)), ftl.poly_area(sq))

    def test_samples_never_empty(self):
        xs, vs, ids, kinds = ftl.poly_samples([])
        self.assertEqual(kinds, [-1.0])
        segs, faces = ftl.wire_segments([None])
        self.assertEqual(len(segs), 1)
        self.assertEqual(faces[0][1], 0.0)

    def test_wire_segment_count(self):
        tr = ftl.Tracker(1)
        slots = tr.update([ftl.fake_face()], 0.0)
        segs, faces = ftl.wire_segments(slots, True, True)
        c = ftl.DEFAULT_COUNTS
        expect = sum((c[r] - 1) if c[r] > 1 else 1 for r in ftl.REGIONS) + sum(1 for r in ftl.CLOSED) + 4
        self.assertEqual(len(segs), expect)
        self.assertEqual(faces[0][:2], (0.0, float(expect)))


if __name__ == '__main__':
    unittest.main()
