"""Offline tests for builders/dmx_patch_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_dmx_patch.py'
Uses builders/dmx_logic.py (BK_dmx_out's logic) read-only, the same way the COMP does."""
import math
import os
import random
import sys
import time
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import dmx_logic as D  # noqa: E402
import dmx_patch_logic as L  # noqa: E402

PROFILES = D.builtin_profiles()


def patch_rows(*rows):
    """(name, profile, univ, addr[, count]) -> patch dicts."""
    out = []
    for r in rows:
        name, prof, u, a = r[:4]
        cnt = r[4] if len(r) > 4 else 1
        out.append({'name': name, 'profile': prof, 'mode': '', 'univ': str(u), 'addr': str(a), 'count': str(cnt),
                    'gapslots': '0', 'node': '', 'kind': 'fixture'})
    return out


def setup(patch, stage=None, pixels=(), order='rgb', univfilter=None):
    plan = D.build_plan(patch, PROFILES, list(pixels), order, univfilter)
    if stage is None:
        names = plan['fixtures']
        stage, _, _ = L.sync_stage([], names, layout='line', span=10.0, height=6.0, depth=0.0, hang=True)
    dec = L.build_decode(D, plan, stage)
    return plan, dec, stage


def flat_of(buf):
    return np.asarray(buf, dtype=np.float64).reshape(-1)


def unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


class Rotations(unittest.TestCase):
    def test_rot_matches_dmx_logic(self):
        rnd = random.Random(1)
        for _ in range(200):
            a = [rnd.uniform(-360, 360) for _ in range(3)]
            self.assertTrue(np.allclose(L.rot_matrix(*a), D._rot(a), atol=1e-12))
        rots = np.array([[rnd.uniform(-180, 180) for _ in range(3)] for _ in range(50)])
        Rs = L.rot_matrices(rots)
        for r, R in zip(rots, Rs):
            self.assertTrue(np.allclose(R, D._rot(r), atol=1e-12))

    def test_dirs_to_euler_turns_plus_y_onto_dir(self):
        rnd = np.random.default_rng(2)
        d = rnd.normal(size=(500, 3))
        d = np.vstack([d, [[0, 1, 0], [0, -1, 0], [1e-9, -1, 0], [0, 0, 1]]])
        e = L.dirs_to_euler(d)
        for di, (rx, ry) in zip(d, e):
            got = L.rot_matrix(rx, ry, 0.0) @ np.array([0.0, 1.0, 0.0])
            self.assertTrue(np.allclose(got, unit(di), atol=1e-9), (di, got))

    def test_beam_dirs_local_matches(self):
        rnd = random.Random(3)
        p = np.array([rnd.uniform(-540, 540) for _ in range(100)])
        t = np.array([rnd.uniform(-135, 135) for _ in range(100)])
        v = L.beam_dirs_local(p, t)
        for k in range(100):
            self.assertTrue(np.allclose(v[k], D.beam_dir(p[k], t[k]), atol=1e-12))


class StagePlot(unittest.TestCase):
    def test_line(self):
        pos = L.arrange(['a', 'b', 'c', 'd', 'e'], 'line', span=10, height=6, depth=-2, hang=True)
        xs = [pos[n][0] for n in 'abcde']
        self.assertAlmostEqual(xs[0], -5)
        self.assertAlmostEqual(xs[-1], 5)
        self.assertAlmostEqual(xs[1] - xs[0], 2.5)
        self.assertTrue(all(pos[n][1] == 6 and pos[n][2] == -2 and pos[n][3] == 180 for n in 'abcde'))
        self.assertEqual(L.arrange(['solo'], 'line')['solo'][0], 0.0)
        self.assertEqual(L.arrange(['a'], 'line', hang=False)['a'][3], 0.0)

    def test_arc_chord_and_bulge(self):
        n = [str(i) for i in range(7)]
        pos = L.arrange(n, 'arc', span=10, height=5, depth=0, curve=90)
        self.assertAlmostEqual(pos['0'][0], -5, places=9)
        self.assertAlmostEqual(pos['6'][0], 5, places=9)
        self.assertAlmostEqual(pos['0'][2], 0.0, places=9)        # chord ends on the depth line
        self.assertAlmostEqual(pos['6'][2], 0.0, places=9)
        self.assertGreater(pos['3'][2], 0.5)                       # middle bulges toward the audience
        self.assertAlmostEqual(pos['3'][0], 0.0, places=9)

    def test_grid_and_ring(self):
        pos = L.arrange([str(i) for i in range(10)], 'grid', span=8, height=6, cols=4, rowgap=1.5)
        self.assertEqual(sorted({p[1] for p in pos.values()}), [3.0, 4.5, 6.0])
        self.assertAlmostEqual(pos['4'][0], pos['0'][0])            # same column spacing on every row
        self.assertAlmostEqual(pos['9'][0], pos['1'][0])
        ring = L.arrange([str(i) for i in range(12)], 'ring', span=10, height=4, depth=-3)
        for p in ring.values():
            self.assertAlmostEqual(math.hypot(p[0], p[2] + 3), 5.0, places=9)
        with self.assertRaises(ValueError):
            L.arrange(['a'], 'spiral')

    def test_sync_keeps_positions_adds_and_reports_stale(self):
        st, added, stale = L.sync_stage([], ['p1', 'p2', 'p3'], layout='line', span=4)
        self.assertEqual(added, ['p1', 'p2', 'p3'])
        st[1]['x'], st[1]['pan_zero'] = 99.0, 0.42
        st2, added2, stale2 = L.sync_stage(st, ['p1', 'p2', 'p3', 'p4'], layout='line', span=4)
        self.assertEqual(added2, ['p4'])
        self.assertEqual(st2[1]['x'], 99.0)
        self.assertEqual(st2[1]['pan_zero'], 0.42)
        self.assertGreater(st2[3]['x'], 99.0)                     # appended after the right-most patched unit
        st3, _, stale3 = L.sync_stage(st2, ['p1', 'p4'])
        self.assertEqual(stale3, ['p2', 'p3'])
        self.assertEqual(len(st3), 4)
        st4, _, stale4 = L.sync_stage(st2, ['p1', 'p4'], prune=True)
        self.assertEqual([r['name'] for r in st4], ['p1', 'p4'])
        self.assertEqual(stale4, [])

    def test_apply_arrange_pattern_and_issues(self):
        st, _, _ = L.sync_stage([], ['par1', 'par2', 'mh1', 'mh2'])
        st[2]['tilt_off'] = 7.0
        st2, n = L.apply_arrange(st, 'mh*', layout='line', span=2, height=9, depth=1)
        self.assertEqual(n, 2)
        self.assertEqual((st2[2]['x'], st2[2]['y'], st2[2]['z']), (-1.0, 9.0, 1.0))
        self.assertEqual(st2[2]['tilt_off'], 7.0)
        self.assertEqual(st2[0], st[0])
        iss = L.stage_issues(['par1', 'new1'], st + [dict(st[0])])
        kinds = sorted(i[0] for i in iss)
        self.assertEqual(kinds, ['duplicate_stage_row', 'no_position', 'stale_stage_row', 'stale_stage_row',
                                 'stale_stage_row'])
        self.assertEqual(L.default_group('par12'), 'par')
        self.assertEqual(L.default_group('wash'), 'wash')

    def test_table_round_trip(self):
        st, _, _ = L.sync_stage([], ['a1', 'a2'])
        rows = L.dicts_to_rows(st, L.STAGE_COLS)
        back = L.rows_to_dicts(rows, L.STAGE_COLS)
        idx = L.stage_index(back)
        self.assertEqual(idx['a2']['pos'], (st[1]['x'], 6.0, 0.0))
        self.assertEqual(idx['a1']['rot'], (180.0, 0.0, 0.0))


class Decode(unittest.TestCase):
    def test_colour_fixtures(self):
        patch = patch_rows(('rgb1', 'generic_rgb_3ch', 0, 1), ('dim1', 'generic_dimmer_1ch', 0, 10),
                           ('w1', 'generic_rgbw_4ch', 0, 20), ('six1', 'generic_rgbaw_uv_6ch', 0, 30))
        plan, dec, _ = setup(patch)
        buf = D.compose(plan, {'rgb1.red': 1.0, 'rgb1.blue': 0.5, 'dim1.dimmer': 0.25, 'w1.white': 1.0,
                               'six1.amber': 1.0})
        s = L.decode(dec, flat_of(buf))
        i = {n: k for k, n in enumerate(dec['names'])}
        self.assertTrue(np.allclose(s['light'][i['rgb1']], [1.0, 0.0, 128 / 255.0], atol=1e-9))
        self.assertAlmostEqual(s['inten'][i['dim1']], 64 / 255.0)
        self.assertTrue(np.allclose(s['rgb'][i['dim1']], L.DIMMER_ONLY_RGB))
        self.assertTrue(np.allclose(s['light'][i['w1']], [1, 1, 1]))
        self.assertTrue(np.allclose(s['light'][i['six1']], [1, 0.75, 0]))
        dark = L.decode(dec, flat_of(D.compose(plan, {})))
        self.assertEqual(float(dark['light'].max()), 0.0)

    def test_moving_head_16bit_intensity_and_colour(self):
        plan, dec, _ = setup(patch_rows(('mh1', 'generic_mh_16bit_16ch', 0, 1)))
        buf = D.compose(plan, {'mh1.dimmer': 0.5, 'mh1.green': 1.0})
        s = L.decode(dec, flat_of(buf))
        self.assertAlmostEqual(s['inten'][0], round(0.5 * 65535) / 65535.0, places=9)
        self.assertTrue(np.allclose(s['rgb'][0], [0, 1, 0]))
        self.assertTrue(dec['has_pt'][0])
        self.assertAlmostEqual(s['pan01'][0], round(0.5 * 65535) / 65535.0)      # defaults 0.5 = centre
        # hanging, pan/tilt centre: beam straight down
        self.assertTrue(np.allclose(s['dir'][0], [0, -1, 0], atol=1e-3))

    def test_aim_compose_decode_round_trip(self):
        """aim() -> BK_dmx_out compose (16-bit bytes) -> decode() -> world beam hits the target (< 0.05 deg)."""
        names = ['mh%d' % i for i in range(1, 7)]
        patch = patch_rows(('mh', 'generic_mh_16bit_16ch', 0, 1, 6))
        plan = D.build_plan(patch, PROFILES, [])
        st, _, _ = L.sync_stage([], names, layout='arc', span=10, height=7, depth=-2, curve=80, hang=True)
        st[2]['rz'] = 15.0                                        # a tilted mount
        st[4]['hang'] = ''
        st[4]['rx'] = 0.0                                         # one floor unit
        st[4]['y'] = 0.5
        st[1]['pan_zero'], st[1]['tilt_off'], st[1]['pan_dir'] = 0.47, 4.0, -1   # calibrated unit
        dec = L.build_decode(D, plan, st)
        rnd = random.Random(5)
        prev = {}
        for _ in range(150):
            tgt = (rnd.uniform(-8, 8), rnd.uniform(0, 3), rnd.uniform(-4, 10))
            n_, v_, prev, missed = L.aim_all(D, dec, tgt, '*', prev)
            buf = D.compose(plan, dict(zip(n_, v_)))
            s = L.decode(dec, flat_of(buf))
            for k, nm in enumerate(dec['names']):
                if nm in missed:
                    continue
                want = unit(np.asarray(tgt) - dec['pos'][k])
                ang = math.degrees(math.acos(min(1.0, float(np.dot(want, s['dir'][k])))))
                self.assertLess(ang, 0.05, (nm, tgt, ang))

    def test_aim_pattern_and_names(self):
        patch = patch_rows(('mh', 'generic_mh_16bit_16ch', 0, 1, 3), ('par1', 'generic_rgb_3ch', 1, 1))
        plan, dec, _ = setup(patch)
        n_, v_, prev, _ = L.aim_all(D, dec, (0, 0, 3), 'mh2')
        self.assertEqual(n_, ['mh2.pan', 'mh2.tilt'])
        self.assertTrue(all(0 <= x <= 1 for x in v_))
        n2, _, _, _ = L.aim_all(D, dec, (0, 0, 3))
        self.assertEqual(len(n2), 6)                               # par1 has no pan/tilt

    def test_calibrate_recovers_offsets(self):
        rnd = random.Random(8)
        for _ in range(100):
            pos = (rnd.uniform(-5, 5), rnd.uniform(3, 8), rnd.uniform(-3, 3))
            rot = (180.0, rnd.uniform(-30, 30), 0.0)
            tgt = (rnd.uniform(-6, 6), 0.0, rnd.uniform(-2, 8))
            pz, to = rnd.uniform(0.45, 0.55), rnd.uniform(-5, 5)
            m = D.aim(pos, tgt, rot, 540.0, 270.0, pz, to)
            if not m['ok']:
                continue
            gpz, gto = L.calibrate(D, pos, rot, tgt, m['pan01'], m['tilt01'], 540.0, 270.0, 1, 1, 0.5)
            again = D.aim(pos, tgt, rot, 540.0, 270.0, gpz, gto)
            self.assertAlmostEqual(again['pan01'], m['pan01'], places=6)
            self.assertAlmostEqual(again['tilt01'], m['tilt01'], places=6)

    def test_chan_rows_assemble_firstuniv_and_filter(self):
        patch = patch_rows(('a', 'generic_rgb_3ch', 0, 1), ('b', 'generic_rgb_3ch', 2, 1))
        plan = D.build_plan(patch, PROFILES, [], 'rgb', {2})
        self.assertEqual(plan['univs'], [0, 2])
        names = D.wire_names(plan, 1)                              # Firstuniv 1: only u3 is sent
        self.assertEqual(names, ['u3'])
        pairs = L.chan_rows(plan, names, first=1)
        self.assertEqual(pairs, [(0, 1)])
        data = np.zeros((1, 512))
        data[0, 0] = 255
        flat = L.assemble(plan, data, pairs)
        self.assertEqual(flat[512], 255)
        self.assertEqual(flat[0], 0)                               # universe 0 not on the wire: 0
        self.assertEqual(L.chan_rows(plan, ['dmx_3', 'x'], first=1, fmt='dmx_{u}'), [(0, 1)])
        self.assertEqual(L.chan_rows(plan, ['u3'], fmt='{bad}'), [])
        self.assertEqual(float(L.assemble(plan, None, []).sum()), 0.0)

    def test_instances(self):
        patch = patch_rows(('a', 'generic_rgb_3ch', 0, 1), ('b', 'generic_rgb_3ch', 0, 4))
        plan, dec, _ = setup(patch)
        s = L.decode(dec, flat_of(D.compose(plan, {'a.red': 1.0})))
        ins = L.fixture_instances(dec, s, size=0.3, beamlen=10, beamangle=20, beamgain=0.5, mingrey=0.1,
                                  highlight=[1])
        self.assertEqual(list(ins['body']['cr']), [1.0, 1.0])     # b highlighted white
        self.assertEqual(ins['beam']['sl'][1], 0.0)                # dark: no beam
        self.assertAlmostEqual(ins['beam']['sl'][0], 10.0)
        self.assertAlmostEqual(ins['beam']['sr'][0], 10 * math.tan(math.radians(10)))
        self.assertAlmostEqual(ins['beam']['br'][0], 0.5)
        self.assertAlmostEqual(ins['beam']['rx'][0], 180.0)        # hanging par: cone turned to point down
        off = L.fixture_instances(dec, s, beams=False)
        self.assertEqual(float(off['beam']['sl'].max()), 0.0)
        ins2 = L.fixture_instances(dec, s, mingrey=0.1)
        self.assertAlmostEqual(ins2['body']['cg'][1], 0.1)
        self.assertEqual(L.highlight_index(['a', 'b', 'ab'], 'a*'), [0, 2])
        self.assertEqual(L.highlight_index(['a'], ''), [])


class Pixels(unittest.TestCase):
    def test_layout_and_stride(self):
        px = D.gen_pixels('grid', 10, 4, serpentine=True)
        pix = [dict(zip(D.PIXEL_COLS, r)) for r in px]
        sel, pos = L.pixel_layout(pix, (1.0, 3.0, -2.0, 8.0, 4.0), pixmax=4096)
        self.assertEqual(len(sel), 40)
        self.assertAlmostEqual(pos[0][0], 1.0 + (0.05 - 0.5) * 8.0)
        self.assertTrue(np.all(pos[:, 2] == -2.0))
        self.assertTrue(pos[:, 1].min() >= 1.0 and pos[:, 1].max() <= 5.0)
        sel2, _ = L.pixel_layout(pix, pixmax=7)
        self.assertEqual(list(sel2), list(range(0, 40, 6)))
        self.assertEqual(len(L.pixel_layout([], pixmax=10)[0]), 0)

    def test_colours_in_wire_order(self):
        for order, want in (('rgb', [0.2, 0.6, 1.0]), ('grb', [0.2, 0.6, 1.0]), ('bgr', [0.2, 0.6, 1.0])):
            px = D.gen_pixels('strip', 5, chans=len(order))
            pix = [dict(zip(D.PIXEL_COLS, r)) for r in px]
            plan = D.build_plan([], PROFILES, pix, order)
            rgb = np.tile(np.array([[0.2, 0.6, 1.0]]), (5, 1))
            buf = D.compose(plan, None, rgb)
            got = L.pixel_colours(plan, np.arange(5), flat_of(buf), order)
            self.assertTrue(np.allclose(got, np.rint(np.array(want) * 255) / 255.0), order)
        px = D.gen_pixels('strip', 3, chans=4)
        pix = [dict(zip(D.PIXEL_COLS, r)) for r in px]
        plan = D.build_plan([], PROFILES, pix, 'rgbw')
        buf = D.compose(plan, None, np.tile([[0.5, 0.5, 0.5]], (3, 1)), prm={'whitemode': 'extract-min'})
        got = L.pixel_colours(plan, np.arange(3), flat_of(buf), 'rgbw')
        self.assertTrue(np.allclose(got, 128 / 255.0))             # w carries it all, shows as grey


class AddressMap(unittest.TestCase):
    def test_owner_grid(self):
        patch = patch_rows(('a', 'generic_rgb_3ch', 0, 1), ('b', 'generic_rgb_3ch', 0, 3),
                           ('c', 'generic_dimmer_1ch', 1, 10))
        px = [dict(zip(D.PIXEL_COLS, r)) for r in D.gen_pixels('strip', 4, univ0=2, group='wall')]
        plan = D.build_plan(patch, PROFILES, px, 'rgb')
        grid, labels, conflicts = L.owner_grid(D, plan, patch, PROFILES, px)
        self.assertEqual(grid.shape, (3, 512))
        self.assertEqual(list(grid[0, :6]), [1, 1, L.CONFLICT, 2, 2, 0])
        self.assertEqual(conflicts, 1)
        self.assertEqual(grid[1, 9], 3)
        self.assertEqual(labels[-1], 'pixels:wall')
        self.assertEqual(int(grid[2, 0]), len(plan['fixtures']) + 1)
        self.assertEqual(int((grid[2] != 0).sum()), 12)
        g2, _, _ = L.owner_grid(D, plan, patch, PROFILES, px, rows=[1])   # only universe 1
        self.assertEqual(g2.shape, (1, 512))
        self.assertEqual(g2[0, 9], 3)


class Camera(unittest.TestCase):
    def fwd(self, c):
        return L.rot_matrix(c['rx'], c['ry'], c['rz']) @ np.array([0, 0, -1.0])

    def test_views_look_at_centre(self):
        ctr = (1.0, 3.0, -2.0)
        for v in L.VIEWS:
            c = L.camera(v, ctr, 12.0, 40.0, 35.0, 25.0)
            to = unit(np.asarray(ctr) - np.array([c['tx'], c['ty'], c['tz']]))
            self.assertTrue(np.allclose(self.fwd(c), to, atol=1e-9), v)
        self.assertEqual(L.camera('front')['projection'], 'ortho')
        self.assertEqual(L.camera('persp')['projection'], 'perspective')
        up = L.rot_matrix(-90, 0, 0) @ np.array([0, 1.0, 0])
        self.assertTrue(np.allclose(up, [0, 0, -1], atol=1e-12))    # top view: upstage at the top of the image
        with self.assertRaises(ValueError):
            L.camera('fish')

    def test_persp_distance_fills_width(self):
        c = L.camera('persp', (0, 0, 0), 10.0, 60.0, 0.0, 0.0)
        self.assertAlmostEqual(c['tz'], 5.0 / math.tan(math.radians(30)))

    def test_fit(self):
        pts = [(-6, 6, 0), (6, 6, 0), (0, 1, -3), (0, 8, 2)]
        for v in ('front', 'top', 'side', 'persp'):
            ctr, size = L.fit_view(pts, v, aspect=0.5625, margin=1.0)
            rgt, up = L.view_axes(v)
            P = np.asarray(pts, dtype=float)
            a, b = P @ rgt, P @ up
            self.assertGreaterEqual(size + 1e-9, a.max() - a.min())
            self.assertGreaterEqual(size / 0.5625 + 1e-9, b.max() - b.min())
        self.assertEqual(L.fit_view([], 'front'), ((0.0, 3.0, 0.0), 16.0))


class Sheet(unittest.TestCase):
    def test_sheet_rows_csv_md(self):
        patch = patch_rows(('mh', 'generic_mh_16bit_16ch', 1, 1, 2), ('par, front', 'generic_rgb_3ch', 0, 5))
        st, _, _ = L.sync_stage([], ['mh1', 'mh2'], layout='line', span=4)
        rows = L.patch_sheet(D, patch, PROFILES, st, first=16)
        self.assertEqual([r['name'] for r in rows], ['par, front', 'mh1', 'mh2'])
        self.assertEqual(rows[1]['dmx'], '17.001')
        self.assertEqual((rows[1]['net'], rows[1]['subnet'], rows[1]['universe']), (0, 1, 1))
        self.assertEqual(rows[2]['addr'], 17)
        self.assertEqual(rows[2]['end'], 32)
        self.assertEqual(rows[0]['x'], '')                         # not placed
        csv = L.sheet_csv(rows)
        self.assertTrue(csv.startswith(','.join(L.SHEET_COLS)))
        self.assertIn('"par, front"', csv)
        md = L.sheet_md(rows, [('overlap', 'a', 'b at 0.1')], 'Test rig', 'sacn', 0)
        self.assertIn('## Universe 17 (net 0, subnet 1, universe 1) - 32 / 512 slots', md)
        self.assertIn('| mh2 | generic_mh_16bit_16ch | 16ch | 17-32 | 16 | mh |', md)
        self.assertIn('- overlap: a (b at 0.1)', md)
        self.assertEqual(L.issue_text([]), 'patch + stage ok')


class Perf(unittest.TestCase):
    def test_decode_and_pixels_fast(self):
        patch = patch_rows(('mh', 'generic_mh_16bit_16ch', 0, 1, 256), ('par', 'generic_rgbaw_uv_6ch', 20, 1, 256))
        px = [dict(zip(D.PIXEL_COLS, r)) for r in D.gen_pixels('grid', 170, 170, univ0=40)]
        plan = D.build_plan(patch, PROFILES, px, 'rgb')
        st, _, _ = L.sync_stage([], plan['fixtures'], layout='grid', cols=32)
        dec = L.build_decode(D, plan, st)
        flat = np.random.default_rng(0).integers(0, 256, plan['nrows'] * 512).astype(np.float64)
        sel, _ = L.pixel_layout(px, pixmax=4096)
        t0 = time.perf_counter()
        for _ in range(20):
            s = L.decode(dec, flat)
            L.fixture_instances(dec, s)
            L.pixel_colours(plan, sel, flat)
        ms = (time.perf_counter() - t0) * 1000 / 20
        # 512 fixtures + 4096 of 28,900 pixels; the TD budget for the whole COMP is 3 ms (CPython here, Rosetta there)
        self.assertLess(ms, 6.0, ms)


if __name__ == '__main__':
    unittest.main()
