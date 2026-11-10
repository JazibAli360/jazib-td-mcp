"""Offline tests for builders/test_pattern_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_test_pattern.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import test_pattern_logic as L  # noqa: E402

R02 = [['name', 'x', 'y', 'w', 'h'], ['L1', '0', '0', '1536', '3840'], ['L2', '1536', '0', '768', '3840'],
       ['C', '2304', '0', '2304', '3840']]


def setup(**kw):
    p = dict(pattern='cabinets', channel='white', level=255, area='slices', walk='across', step=0, linewidth=2,
             cell=0, steps=16, showfaces=False, resx=1920, resy=1080, nativewidth=0, cabw=128, cabh=128,
             frame=0, fps=60, seconds=0.0)
    rows = kw.pop('rows', L.DEFAULT_FACES)
    p.update(kw)
    faces = L.parse_faces(rows)
    rects = L.face_rects(faces, p['resx'], p['resy'], p['nativewidth'])
    return dict(L.uniforms(p, rects)), rects, faces


class Faces(unittest.TestCase):
    def test_default_one_wall(self):
        U, rects, faces = setup()
        self.assertEqual(rects, [(0, 0, 1920, 1080)])
        self.assertEqual(U['uRes'], [1920, 1080, 1, 0])

    def test_parse_skips_bad_rows(self):
        f = L.parse_faces([['name', 'x', 'y', 'w', 'h'], ['A', '0', '0', '10', '10'], ['B', 'x', '0', '1', '1'],
                           ['C', '0', '0', '0', '5'], [], ['', '1', '1', '2', '2']])
        self.assertEqual([x['name'] for x in f], ['A', 'Face2'])

    def test_max_faces(self):
        rows = [['F%d' % k, str(k * 10), '0', '10', '10'] for k in range(30)]
        self.assertEqual(len(L.parse_faces(rows)), L.MAX_FACES)

    def test_native_width_scale(self):
        # R02 slice of 4608 LED px shown at 7488 wide comp = 96 px cabinets (native 9984)
        self.assertAlmostEqual(L.scale(7488, 9984) * 128, 96.0)
        f = L.parse_faces(R02)
        r = L.face_rects(f, 3456, 2880, 4608)        # 0.75 scale
        self.assertEqual(r[0], (0, 0, 1152, 2880))
        self.assertEqual(r[1], (1152, 0, 576, 2880))

    def test_clip(self):
        f = L.parse_faces([['A', '1900', '1000', '100', '100'], ['B', '5000', '0', '10', '10']])
        self.assertEqual(L.face_rects(f, 1920, 1080, 0), [(1900, 1000, 20, 80), None])


class Grid(unittest.TestCase):
    def test_cell_index_integer(self):
        self.assertEqual([L.cell_index(x, 128) for x in (0, 127, 128, 255, 256)], [0, 0, 1, 1, 2])

    def test_cell_index_fractional_bounds(self):
        c = 128 * 4537 / 9984.0                         # 58.17 px
        for k in range(60):
            b0, b1 = L.cell_bound(k, c), L.cell_bound(k + 1, c)
            for x in (b0, b1 - 1):
                self.assertEqual(L.cell_index(x, c), k)

    def test_counts(self):
        self.assertEqual(L.count_cells(1920, 128), 15)
        self.assertEqual(L.count_cells(1080, 128), 9)    # 8 full + one partial row


class Patterns(unittest.TestCase):
    def px(self, x, y, **kw):
        U, rects, _ = setup(**kw)
        return L.pixel(x, y, U, rects)

    def test_cabinet_rings(self):
        self.assertEqual(self.px(0, 50), (255, 255, 255, 255))
        self.assertEqual(self.px(127, 50), (255, 255, 255, 255))
        self.assertEqual(self.px(128, 50), (255, 255, 255, 255))
        self.assertEqual(self.px(64, 64), (0, 0, 0, 255))
        self.assertEqual(self.px(126, 64), (255, 255, 255, 255))   # lw 2: 126, 127
        self.assertEqual(self.px(125, 64), (0, 0, 0, 255))
        self.assertEqual(self.px(64, 1079), (255, 255, 255, 255))  # partial last row closes at the area edge

    def test_channel_level_exact(self):
        self.assertEqual(self.px(0, 0, channel='red', level=191), (191, 0, 0, 255))
        self.assertEqual(self.px(0, 0, channel='cyan', level=7, pattern='solid'), (0, 7, 7, 255))
        self.assertEqual(self.px(5, 5, channel='black', pattern='solid'), (0, 0, 0, 255))

    def test_bars(self):
        cols = [self.px(x * 240 + 100, 500, pattern='bars', level=191)[:3] for x in range(8)]
        self.assertEqual(cols, [(191, 191, 191), (191, 191, 0), (0, 191, 191), (0, 191, 0), (191, 0, 191),
                                (191, 0, 0), (0, 0, 191), (0, 0, 0)])

    def test_ramp_256_every_code(self):
        U, rects, _ = setup(pattern='ramp', steps=256, resx=2560, resy=100,
                            rows=[['W', '0', '0', '2560', '100']])
        codes = sorted(set(L.pixel(x, 5, U, rects)[0] for x in range(2560)))
        self.assertEqual(codes, list(range(256)))

    def test_ramp_16(self):
        U, rects, _ = setup(pattern='ramp', steps=16)
        codes = sorted(set(L.pixel(x, 5, U, rects)[0] for x in range(1920)))
        self.assertEqual(codes, [L.rnd(k * 255 / 15.0) for k in range(16)])

    def test_ramp_portrait_runs_down(self):
        U, rects, _ = setup(pattern='ramp', resx=100, resy=1000, rows=[['P', '0', '0', '100', '1000']])
        self.assertEqual(L.pixel(0, 0, U, rects)[0], 0)
        self.assertEqual(L.pixel(0, 999, U, rects)[0], 255)
        self.assertEqual(L.pixel(99, 0, U, rects)[0], 0)

    def test_checker_cabinets(self):
        self.assertEqual(self.px(10, 10, pattern='checker')[0], 255)
        self.assertEqual(self.px(130, 10, pattern='checker')[0], 0)
        self.assertEqual(self.px(130, 130, pattern='checker')[0], 255)

    def test_crosshatch_centre_lines(self):
        self.assertEqual(self.px(960, 300, pattern='crosshatch')[0], 255)
        self.assertEqual(self.px(960 + 128, 300, pattern='crosshatch')[0], 255)
        self.assertEqual(self.px(960 + 64, 300, pattern='crosshatch')[0], 0)
        self.assertEqual(self.px(300, 540, pattern='crosshatch')[0], 255)

    def test_pixelcheck(self):
        self.assertEqual([self.px(x, 10, pattern='pixelcheck')[0] for x in range(4)], [255, 0, 255, 0])
        self.assertEqual([self.px(x, 800, pattern='pixelcheck')[0] for x in range(4)], [255, 0, 255, 0])
        self.assertEqual([self.px(1500, y, pattern='pixelcheck')[0] for y in range(800, 804)], [255, 0, 255, 0])

    def test_circles(self):
        self.assertEqual(self.px(960, 0, pattern='circles')[0], 255)    # edge
        self.assertEqual(self.px(960, 539 - 538, pattern='circles')[0], 255)
        self.assertEqual(self.px(960, 540, pattern='circles')[0], 255)  # centre ring (d < lw)

    def test_slices_outline_diagonal(self):
        self.assertEqual(self.px(0, 500, pattern='slices')[0], 255)
        self.assertEqual(self.px(960, 540, pattern='slices')[0], 255)   # both diagonals cross at the centre
        self.assertEqual(self.px(960, 100, pattern='slices')[0], 0)

    def test_outside_faces_transparent(self):
        U, rects, _ = setup(rows=[['A', '0', '0', '100', '100']])
        self.assertEqual(L.pixel(500, 500, U, rects), (0, 0, 0, 0))
        U, rects, _ = setup(rows=[['A', '0', '0', '100', '100']], area='canvas')
        self.assertEqual(L.pixel(500, 500, U, rects)[3], 255)

    def test_showfaces_xor(self):
        self.assertEqual(self.px(0, 500, pattern='solid', showfaces=True)[0], 0)
        self.assertEqual(self.px(500, 0, pattern='checker', showfaces=True, cell=0)[0], 255)

    def test_per_face_origin(self):
        rows = [['A', '0', '0', '100', '100'], ['B', '100', '0', '100', '100']]
        U, rects, _ = setup(rows=rows, cabw=50, cabh=50, pattern='checker')
        self.assertEqual(L.pixel(10, 10, U, rects)[0], 255)
        self.assertEqual(L.pixel(110, 10, U, rects)[0], 255)            # B restarts at its own corner
        U, rects, _ = setup(rows=[['A', '0', '0', '100', '100'], ['B', '100', '0', '50', '100']], cabw=60, cabh=60,
                            pattern='checker', area='canvas')
        self.assertEqual(L.pixel(110, 10, U, rects)[0], 0)


class Walk(unittest.TestCase):
    def lit(self, walk, step, **kw):
        U, rects, _ = setup(pattern='walk', walk=walk, step=step, **kw)
        W, H = int(U['uRes'][0]), int(U['uRes'][1])
        return [(x, y) for y in range(H) for x in range(W) if L.pixel(x, y, U, rects)[0]]

    def test_across(self):
        pts = self.lit('across', 3, resx=64, resy=8, rows=[['A', '0', '0', '64', '8']])
        self.assertEqual(sorted(set(x for x, _ in pts)), [6, 7])

    def test_down_wraps(self):
        pts = self.lit('down', 4 + 5, resx=8, resy=8, rows=[['A', '0', '0', '8', '8']])   # span 4
        self.assertEqual(sorted(set(y for _, y in pts)), [2, 3])

    def test_dot_covers_every_pixel_once(self):
        kw = dict(resx=16, resy=8, rows=[['A', '0', '0', '16', '8']], cabw=8, cabh=8)
        span = L.walk_span('dot', 16, 8, 2, 8, 8)
        self.assertEqual(span, 16)
        seen = {}
        for s in range(span):
            for p in self.lit('dot', s, **kw):
                seen[p] = seen.get(p, 0) + 1
        self.assertEqual(len(seen), 128)
        self.assertEqual(set(seen.values()), {1})

    def test_cabinet_reading_order(self):
        kw = dict(resx=32, resy=16, rows=[['A', '0', '0', '32', '16']], cabw=8, cabh=8)
        pts = self.lit('cabinet', 5, **kw)                   # 4 x 2 cabinets: step 5 = col 1 row 1
        self.assertEqual(min(pts), (8, 8))
        self.assertEqual(len(pts), 64)

    def test_diagonal(self):
        pts = self.lit('diagonal', 0, resx=8, resy=8, rows=[['A', '0', '0', '8', '8']])
        self.assertEqual(sorted(pts), [(0, 0), (0, 1), (1, 0)])


class Labels(unittest.TestCase):
    def test_cabinet_labels(self):
        rows = L.cabinet_labels([(0, 0, 1920, 1080)], 128, 128, 1080)
        self.assertEqual(len(rows), 15 * 9)
        self.assertEqual(rows[0], (64.0, 1016.0, '1-1'))
        self.assertEqual(rows[-1][2], '15-9')

    def test_centre_rows(self):
        rows = L.centre_rows([(100.0, 50.0, 'ab')], 20, measure=lambda t: 30.0)
        self.assertEqual(rows, [(85.0, 42.8, 'ab')])
        self.assertEqual(L.centre_rows([(100.0, 50.0, 'ab')], 20)[0][0], 89.0)

    def test_cabinet_labels_too_small(self):
        self.assertEqual(L.cabinet_labels([(0, 0, 100, 100)], 10, 10, 100), [])

    def test_slice_labels(self):
        f = L.parse_faces(R02)
        r = L.face_rects(f, 4608, 3840, 0)
        rows = L.slice_labels(f, r, 128, 128, 3840, 40)
        self.assertEqual([t for _, _, t in rows[:3]], ['L1', '1536x3840', '12x30 cab'])
        self.assertEqual(rows[5][2], '6x30 cab')
        self.assertEqual(rows[8][2], '18x30 cab')


class Sync(unittest.TestCase):
    def test_timecode(self):
        self.assertEqual(L.timecode(0, 60), '00:00:00:00')
        self.assertEqual(L.timecode(60 * 3661 + 59, 60), '01:01:01:59')
        self.assertEqual(L.timecode(29, 29.97), '00:00:00:29')

    def test_counter_text(self):
        self.assertEqual(L.counter_text(161696, 60), 'F 0161696  00:44:54:56  60 fps')

    def test_bits_roundtrip(self):
        for f in (0, 1, 161696, 2 ** 24 - 1):
            b = L.frame_bits(f)
            self.assertEqual(len(b), 24)
            self.assertEqual(L.decode_bits(b), f)

    def test_flash_and_blip_same_frame(self):
        for f in range(0, 300):
            fl = L.flash_now(f, 60)
            bl = L.blip_gate(f, 60, 1, True)
            self.assertEqual(fl, bool(bl))
        self.assertEqual(L.blip_gate(61, 60, 2, True), 1.0)
        self.assertEqual(L.blip_gate(0, 60, 1, False), 0.0)

    def test_wheel_segment(self):
        self.assertEqual(L.wheel_segment(0.5, 24), 12)
        self.assertEqual(L.wheel_segment(1.0 / 120 * 7, 120), 7)
        self.assertEqual(L.wheel_segment(2.0, 30), 0)

    def test_needs_clock(self):
        self.assertFalse(L.needs_clock({'pattern': 'cabinets'}))
        self.assertTrue(L.needs_clock({'pattern': 'walk'}))
        self.assertTrue(L.needs_clock({'pattern': 'solid', 'counter': True}))

    def test_counter_layout_fits_bits(self):
        tw, th, bw, bh, pad = L.counter_layout(24)
        self.assertGreaterEqual(bw, 26 * 24 + 2 * pad)
        self.assertEqual(bh, th + 24 + 3 * pad)

    def test_presets(self):
        self.assertEqual(L.preset_res('7488x2880'), (7488, 2880))
        self.assertIsNone(L.preset_res('custom'))


if __name__ == '__main__':
    unittest.main()
