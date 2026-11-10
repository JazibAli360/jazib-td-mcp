"""Offline tests for builders/dmx_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_dmx.py'"""
import json
import math
import os
import random
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import dmx_logic as L  # noqa: E402

PROFILES = L.builtin_profiles()


def patch_rows(rows):
    return [dict(zip(L.PATCH_COLS, r)) for r in rows]


class Addressing(unittest.TestCase):
    def test_port_address_round_trip(self):
        for u in range(32768):
            self.assertEqual(L.flat_universe(*L.port_address(u)), u)
        self.assertEqual(L.port_address(0x1234), (0x12, 0x3, 0x4))

    def test_split16(self):
        self.assertEqual(L.split16(0), (0, 0))
        self.assertEqual(L.split16(1), (255, 255))
        self.assertEqual(L.split16(0.5), (128, 0))
        self.assertEqual(L.split16(-3), (0, 0))
        prev = -1
        for i in range(1001):
            c, f = L.split16(i / 1000)
            v = c * 256 + f
            self.assertGreaterEqual(v, prev)
            prev = v
        self.assertAlmostEqual(L.join16(*L.split16(0.3)), 0.3, places=4)

    def test_place_spill(self):
        buf = np.zeros((2, 512), dtype=np.uint8)
        L.place(buf, 0, 511, [1, 2, 3, 4])
        self.assertEqual(list(buf[0, 510:]), [1, 2])
        self.assertEqual(list(buf[1, :2]), [3, 4])

    def test_univfilter(self):
        self.assertIsNone(L.parse_univfilter(''))
        self.assertEqual(L.parse_univfilter('0-2, 7'), {0, 1, 2, 7})


class Pixels(unittest.TestCase):
    def test_layout_170(self):
        a = L.layout_pixels(28900, 170)
        self.assertEqual(len({u for u, _ in a}), 170)
        self.assertEqual(a[169], (0, 1 + 169 * 3))
        self.assertEqual(a[170], (1, 1))

    def test_layout_span(self):
        a = L.layout_pixels(171, chans=3, span=True)
        self.assertEqual(a[170], (0, 511))           # straddles: slots 511, 512, then 1 of univ 1
        b = L.layout_pixels(3, univ0=2, addr0=508, chans=3, span=False)
        self.assertEqual(b, [(2, 508), (3, 1), (3, 4)])

    def test_layout_rgbw(self):
        a = L.layout_pixels(129, per_univ=128, chans=4)
        self.assertEqual(a[128], (1, 1))

    def test_pixel_slots_orders(self):
        c = [[1.0, 0.5, 0.0]]
        self.assertEqual(L.pixel_slots(c, 'rgb').tolist(), [[255, 128, 0]])
        self.assertEqual(L.pixel_slots(c, 'grb').tolist(), [[128, 255, 0]])
        self.assertEqual(L.pixel_slots(c, 'bgr').tolist(), [[0, 128, 255]])
        self.assertEqual(L.pixel_slots(c, 'rgbw').tolist(), [[255, 128, 0, 0]])

    def test_gamma_and_white(self):
        self.assertEqual(L.pixel_slots([[0.5, 0.5, 0.5]], 'rgb', gamma=2.2).tolist(), [[55, 55, 55]])
        self.assertEqual(L.pixel_slots([[0.8, 0.5, 0.3]], 'rgbw', 'extract-min').tolist(), [[128, 51, 0, 76]])
        self.assertEqual(L.pixel_slots([[0.8, 0.5, 0.3]], 'grbw', 'zero-w').tolist(), [[128, 204, 76, 0]])

    def test_gen_pixels(self):
        g = L.gen_pixels('grid', 4, 2, serpentine=True)
        self.assertEqual(len(g), 8)
        self.assertGreater(g[4][1], g[5][1])           # second row runs right to left
        r = L.gen_pixels('ring', 50)
        self.assertTrue(all(0 <= p[1] <= 1 and 0 <= p[2] <= 1 for p in r))
        self.assertEqual(r[-1][4], 1 + 49 * 3)

    def test_csv(self):
        txt = 'x,y,z\n0,0,0\n10,5,0\n5,10,1\n'
        p = L.parse_pixel_csv(txt)
        self.assertEqual([(q[1], q[2]) for q in p], [(0.0, 0.0), (1.0, 0.5), (0.5, 1.0)])
        p2 = L.parse_pixel_csv('x,y,univ,addr\n0,0,3,10\n1,1,3,13\n')
        self.assertEqual((p2[1][3], p2[1][4]), (3, 13))


class Aim(unittest.TestCase):
    def _check(self, pos, tgt, rot, prev=None):
        r = L.aim(pos, tgt, rot, prev_pan=prev)
        d = np.asarray(tgt, float) - np.asarray(pos, float)
        d /= np.linalg.norm(d)
        err = math.acos(max(-1.0, min(1.0, float(np.dot(L.aim_world_dir(r, rot), d)))))
        return r, err

    def test_round_trip_random(self):
        rnd = random.Random(7)
        bad = 0
        for _ in range(10000):
            pos = [rnd.uniform(-5, 5) for _ in range(3)]
            tgt = [rnd.uniform(-5, 5) for _ in range(3)]
            rot = [rnd.choice([0, 180, 90]), rnd.uniform(-180, 180), rnd.choice([0, 180])]
            r, err = self._check(pos, tgt, rot)
            self.assertLess(err, 1e-6)
            # 270 deg tilt cannot reach more than 135 deg away from the mount axis: only those are flagged
            self.assertEqual(r['ok'], abs(r['theta']) <= 135.0 + 1e-9)
            bad += 0 if r['ok'] else 1
        self.assertLess(bad, 2000)

    def test_known_target(self):
        r = L.aim((0, 3, 0), (0, 0, -5), (0, 0, 180))   # hanging head, target in front and below
        self.assertTrue(r['ok'])
        self.assertAlmostEqual(abs(r['theta']), math.degrees(math.atan2(5, 3)), places=6)

    def test_zenith_keeps_prev(self):
        r = L.aim((0, 0, 0), (0, 5, 0), prev_pan=37.0)
        self.assertAlmostEqual(r['pan'], 37.0)
        self.assertAlmostEqual(r['theta'], 0.0)

    def test_hysteresis(self):
        prev = -260.0                            # start where the orbit starts (else the centre-nearest pan wins)
        for i in range(-260, 261):               # inside the 540 range: never a jump
            a = math.radians(i)
            r = L.aim((0, 0, 0), (math.sin(a), 0.3, -math.cos(a)), prev_pan=prev)
            if prev is not None:
                self.assertLess(abs(r['pan'] - prev), 5.0)
            prev = r['pan']
        jumps = 0
        for i in range(261, 261 + 720):          # two more turns: flips are needed, but rare
            a = math.radians(i)
            r = L.aim((0, 0, 0), (math.sin(a), 0.3, -math.cos(a)), prev_pan=prev)
            jumps += abs(r['pan'] - prev) > 5.0
            prev = r['pan']
        self.assertLessEqual(jumps, 4)            # one flip per ~180 deg past the limit

    def test_beam_dir(self):
        v = L.beam_dir(0, 90)
        self.assertTrue(np.allclose(v, [0, 0, -1]))
        self.assertTrue(np.allclose(L.beam_dir(90, 90), [1, 0, 0]))


class Packets(unittest.TestCase):
    def test_artdmx(self):
        data = list(range(256)) + list(range(255))       # 511 -> padded to 512
        pkt = L.encode_artdmx(3, 0x123, data)
        self.assertEqual(len(pkt), 18 + 512)
        self.assertEqual(pkt[:8], b'Art-Net\x00')
        self.assertEqual(pkt[8:10], b'\x00\x50')
        self.assertEqual((pkt[14], pkt[15]), (0x23, 0x01))
        p = L.parse_artdmx(pkt)
        self.assertEqual((p['seq'], p['univ'], p['length'], p['version']), (3, 0x123, 512, 14))
        self.assertEqual(list(p['data'][:511]), data)
        self.assertEqual(L.parse_artdmx(L.encode_artdmx(0, 0, [7]))['length'], 2)

    def test_sacn(self):
        data = [i % 256 for i in range(512)]
        pkt = L.encode_sacn(9, 1, data, prio=150, name='BK test', cid=b'0123456789abcdef')
        self.assertEqual(len(pkt), 638)
        p = L.parse_sacn(pkt)
        self.assertEqual((p['seq'], p['univ'], p['priority'], p['name'], p['length'], p['startcode']),
                         (9, 1, 150, 'BK test', 512, 0))
        self.assertEqual(list(p['data']), data)
        self.assertEqual(p['cid'], b'0123456789abcdef')
        self.assertEqual(pkt[16] & 0xF0, 0x70)
        self.assertEqual(((pkt[16] & 0x0F) << 8) | pkt[17], 638 - 16)


class Profiles(unittest.TestCase):
    def test_ofl(self):
        d = json.load(open(os.path.join(HERE, 'fixtures', 'ofl_sample_mh.json')))
        p = L.ofl_to_profile(d)
        std = L.find_mode(p, 'std16')
        self.assertEqual(L.footprint(std), 11)
        pan = std['channels'][0]
        self.assertEqual((pan['attr'], pan['bits'], pan['fine'], pan['range_deg']), ('pan', 16, 1, 540.0))
        attrs = [c['attr'] for c in std['channels']]
        self.assertEqual(attrs, ['pan', 'tilt', 'dimmer', 'shutter', 'red', 'green', 'blue', 'raw', 'raw'])
        self.assertEqual(std['channels'][7]['name'], 'unused')
        self.assertAlmostEqual(std['channels'][3]['default'], 1.0)
        self.assertEqual(L.footprint(L.find_mode(p, 'red8')), 6)
        self.assertEqual(p['pan_range'], 540.0)

    def test_builtins(self):
        ids = [p['id'] for p in PROFILES]
        for want in ('generic_dimmer_1ch', 'generic_rgb_3ch', 'generic_rgbw_4ch', 'generic_rgbaw_uv_6ch',
                     'generic_mh_16bit_16ch'):
            self.assertIn(want, ids)
        self.assertEqual(L.footprint(L.find_mode(L.profile_index(PROFILES)['generic_mh_16bit_16ch'], '')), 16)


class Patch(unittest.TestCase):
    def test_add_autonext_quantize(self):
        rows = L.add_fixtures([], PROFILES, 'generic_mh_16bit_16ch', count=40, name='mh', autonext=True)
        self.assertEqual(rows[0]['addr'], '1')
        self.assertEqual(rows[31]['addr'], str(1 + 31 * 16))     # 32 x 16 = 512 fit exactly
        self.assertEqual((rows[32]['univ'], rows[32]['addr']), ('1', '1'))
        rows2 = L.add_fixtures(rows, PROFILES, 'generic_rgb_3ch', count=2, name='par', autonext=True)
        self.assertEqual((rows2[0]['univ'], rows2[0]['addr']), ('1', str(1 + 8 * 16)))
        self.assertEqual(L.check_patch(rows + rows2, PROFILES), [])

    def test_quantize_straddle(self):
        rows = L.add_fixtures([], PROFILES, 'generic_rgbaw_uv_6ch', count=86, name='p', quantize='fixture')
        self.assertEqual((rows[85]['univ'], rows[85]['addr']), ('1', '1'))      # 85 * 6 = 510, next would straddle
        rows = L.add_fixtures([], PROFILES, 'generic_rgbaw_uv_6ch', count=86, name='p', quantize='off')
        self.assertEqual((rows[85]['univ'], rows[85]['addr']), ('0', '511'))
        kinds = [i[0] for i in L.check_patch(rows, PROFILES)]
        self.assertIn('straddle', kinds)

    def test_check(self):
        p = patch_rows([['a', 'generic_rgb_3ch', '', '0', '1', '1', '0', '', 'fixture'],
                        ['b', 'generic_rgb_3ch', '', '0', '3', '1', '0', '', 'fixture'],
                        ['c', 'nope', '', '0', '9', '1', '0', '', 'fixture'],
                        ['d', 'generic_dimmer_1ch', '', '3', '1', '1', '0', '', 'fixture']])
        kinds = sorted(i[0] for i in L.check_patch(p, PROFILES))
        self.assertEqual(kinds, ['holes', 'overlap', 'unknown_profile'])

    def test_count_expands(self):
        p = patch_rows([['par', 'generic_rgb_3ch', '', '0', '1', '3', '2', '', 'fixture']])
        f = L.expand_patch(p, PROFILES)
        self.assertEqual([(x['name'], x['addr']) for x in f], [('par1', 1), ('par2', 6), ('par3', 11)])


def mixed_plan(univfilter=None):
    p = patch_rows([['mh', 'generic_mh_16bit_16ch', '', '0', '1', '1', '0', '10.0.0.5', 'fixture'],
                    ['par', 'generic_rgb_3ch', '', '0', '17', '2', '0', '', 'fixture']])
    px = [dict(zip(L.PIXEL_COLS, r)) for r in L.gen_pixels('strip', 200, univ0=1)]
    return L.build_plan(p, PROFILES, px, 'rgb', univfilter)


class Compose(unittest.TestCase):
    def test_plan(self):
        pl = mixed_plan()
        self.assertEqual(pl['univs'], [0, 1, 2])
        self.assertEqual(pl['npix'], 200)
        self.assertEqual(pl['fixtures'], ['mh', 'par1', 'par2'])
        rt = L.routing_rows(pl)
        self.assertEqual(rt[0], L.ROUTING_COLS)
        self.assertEqual(rt[1], ['u0', '0', '0', '0', '10.0.0.5'])
        self.assertEqual(rt[2][4], '127.0.0.1')
        self.assertEqual(L.routing_rows(pl, loopback=True)[1][4], '127.0.0.1')
        self.assertEqual(L.routing_rows(pl, targetmode='broadcast')[1][4], '255.255.255.255')
        self.assertEqual(mixed_plan({1})['send_univs'], [1])
        self.assertEqual(L.routing_rows(pl, first=17)[1][1:4], ['0', '1', '1'])
        self.assertEqual(L.wire_names(pl, 1), ['u1', 'u2', 'u3'])

    def test_fixture_values_and_defaults(self):
        pl = mixed_plan()
        b = L.compose(pl, {'mh.pan': 1.0, 'mh.tilt_deg': 0.0, 'mh.dimmer': 0.5, 'par*.red': 1.0})
        self.assertEqual(list(b[0, 0:4]), [255, 255, 128, 0])   # pan 16 bit full, tilt centre 0.5
        self.assertEqual(list(b[0, 5:7]), [128, 0])              # dimmer 16 bit 0.5
        self.assertEqual(b[0, 7], 255)                            # shutter default open
        self.assertEqual(list(b[0, 16:22]), [255, 0, 0, 255, 0, 0])

    def test_underscore_names(self):  # T-90: TD CHOPs turn 'mh.pan' into 'mh_pan'
        pl = mixed_plan()
        a = L.compose(pl, {'mh.pan': 1.0, 'mh.tilt_deg': 0.0, 'mh.dimmer': 0.5, 'par*.red': 1.0})
        b = L.compose(mixed_plan(), {'mh_pan': 1.0, 'mh_tilt_deg': 0.0, 'mh_dimmer': 0.5, 'par*_red': 1.0})
        self.assertEqual(a.tolist(), b.tolist())

    def test_pixels(self):
        pl = mixed_plan()
        pix = np.zeros((200, 3))
        pix[:, 0] = 1.0
        b = L.compose(pl, None, pix)
        self.assertEqual(list(b[1, 0:6]), [255, 0, 0, 255, 0, 0])
        self.assertEqual(b[2, 0], 255)                            # pixel 170 starts universe 2

    def test_master_only_intensity(self):
        pl = mixed_plan()
        fix = {'mh.pan': 0.25, 'mh.dimmer': 1.0, 'par1.red': 1.0}
        b = L.compose(pl, fix, None, prm={'master_eff': 0.5})
        self.assertEqual(L.split16(0.25), tuple(b[0, 0:2]))       # pan untouched
        self.assertEqual(int(b[0, 5]) * 256 + int(b[0, 6]), 32768)  # 16-bit dimmer halved (65535 * 0.5)
        self.assertEqual(b[0, 16], 128)
        bo = L.compose(pl, fix, None, prm={'blackout': True})
        self.assertEqual((bo[0, 5], bo[0, 16]), (0, 0))
        self.assertEqual(tuple(bo[0, 0:2]), L.split16(0.25))
        ba = L.compose(pl, fix, None, prm={'blackout': True, 'blackoutmode': 'all'})
        self.assertEqual(int(ba.max()), 0)

    def test_freeze(self):
        pl = mixed_plan()
        a = L.compose(pl, {'par1.red': 1.0})
        b = L.compose(pl, {'par1.red': 0.0}, prm={'freeze': True}, prev=a)
        self.assertIs(b, a)

    def test_patterns(self):
        pl = mixed_plan()
        for k in L.PATTERNS[1:]:
            a = L.compose(pl, prm={'pattern': k}, t=1.25)
            b = L.compose(pl, prm={'pattern': k}, t=1.25)
            self.assertTrue(np.array_equal(a, b), k)
        cid = L.compose(pl, prm={'pattern': 'channelid'})
        self.assertEqual((cid[0, 0], cid[1, 0], cid[0, 255]), (1, 2, 0))
        full = L.compose(pl, prm={'pattern': 'full', 'level': 0.5})
        self.assertEqual(int(full.min()), 128)
        z = L.compose(pl, {'par1.red': 1.0}, prm={'pattern': 'zero', 'patternmix': 'max'})
        self.assertEqual(z[0, 16], 255)
        ramp = L.compose(pl, prm={'pattern': 'ramp'})
        self.assertEqual((ramp[0, 0], ramp[0, 511]), (0, 255))
        rc = L.compose(pl, prm={'pattern': 'rgbcycle'}, t=0.0)
        self.assertEqual((rc[0, 16], rc[0, 17], rc[1, 0], rc[1, 1]), (255, 0, 255, 0))
        wp = L.compose(pl, prm={'pattern': 'walkpixel', 'speed': 1.0}, t=2.0)
        self.assertEqual(list(wp[1, 6:9]), [255, 255, 255])
        self.assertEqual(int(np.count_nonzero(wp)), 3)
        st_on = L.compose(pl, prm={'pattern': 'strobe', 'speed': 2.0}, t=0.1)
        st_off = L.compose(pl, prm={'pattern': 'strobe', 'speed': 2.0}, t=0.3)
        self.assertGreater(np.count_nonzero(st_on), 0)
        self.assertEqual(np.count_nonzero(st_off), 0)

    def test_solo(self):
        pl = mixed_plan()
        b = L.compose(pl, prm={'pattern': 'full', 'solofixture': 'par2'})
        self.assertEqual(list(b[0, 19:22]), [255, 255, 255])
        self.assertEqual(int(b[0, 16]), 0)
        self.assertEqual(int(b[1].max()), 0)
        c = L.compose(pl, prm={'pattern': 'full', 'solochan': 5})
        self.assertEqual(int(np.count_nonzero(c)), 3)

    def test_big_grid_speed(self):
        import time
        px = [dict(zip(L.PIXEL_COLS, r)) for r in L.gen_pixels('grid', 170, 170)]
        pl = L.build_plan([], PROFILES, px)
        self.assertEqual(len(pl['univs']), 170)
        pix = np.random.default_rng(1).random((28900, 3))
        L.compose(pl, None, pix)
        t0 = time.perf_counter()
        for _ in range(20):
            L.compose(pl, None, pix, prm={'master_eff': 0.7})
        ms = (time.perf_counter() - t0) / 20 * 1000
        self.assertLess(ms, 40.0)       # offline sanity only; the live budget is measured in TD

    def test_loop_diff(self):
        a = np.arange(1024).reshape(2, 512) % 256
        self.assertEqual(L.loop_diff(a, a.copy()), 0.0)
        self.assertEqual(L.loop_diff(a, None), -1.0)


class MasterTempo(unittest.TestCase):
    def test_master(self):
        self.assertEqual(L.master_value('manual', 0.3, 0.7), 0.7)
        self.assertAlmostEqual(L.master_value('bpm', 0.0, 1.0, 120, 'pulse'), 1.0)
        self.assertAlmostEqual(L.master_value('bpm', 0.25, 1.0, 120, 'pulse'), 0.0)   # half a beat
        self.assertAlmostEqual(L.master_value('bpm', 0.25, 1.0, 120, 'square', depth=0.5), 0.5)
        self.assertAlmostEqual(L.master_value('audio', 0, 1.0, audio=0.4, audioamt=2.0), 0.8)
        self.assertAlmostEqual(L.master_value('bpm-x-audio', 0, 1.0, 120, 'saw', audio=0.5), 0.5)

    def test_tap(self):
        taps = []
        bpm = None
        for i in range(4):
            taps, bpm = L.tap_bpm(taps, 10 + i * 0.5)
        self.assertAlmostEqual(bpm, 120.0)
        taps, bpm = L.tap_bpm(taps, 30)
        self.assertIsNone(bpm)

    def test_monitor_layout(self):
        self.assertEqual(L.monitor_layout(1024, 768, 6, 16), (5, 7, 16))

    def test_pixchop_multirow(self):
        # 3 rows x 4 cols texture, 10 pixels; chans r0 g0 b0 a0 r1 ... ; pixel i = row i//4, col i%4
        w, h, n = 4, 3, 10
        a = np.zeros((4 * h, w))
        for i in range(w * h):
            r, col = divmod(i, w)
            a[4 * r:4 * r + 4, col] = [i, i + 100, i + 200, 1]
        px = L.pixchop_to_pixels(a, n)
        self.assertEqual(px.shape, (10, 3))
        self.assertEqual(px[0].tolist(), [0, 100, 200])
        self.assertEqual(px[9].tolist(), [9, 109, 209])
        self.assertEqual(L.pixchop_to_pixels(a, n, k4=True).shape, (10, 4))
        self.assertEqual(L.pixchop_to_pixels(a[:4, :3], 3)[2].tolist(), [2, 102, 202])   # single row
        self.assertIsNone(L.pixchop_to_pixels(a, 0))

    def test_popchop_layout(self):
        # TC-38 POP source: POP to CHOP of Color = 4 channels (r g b a) x npoints samples -> pixel i = point i
        pts = np.array([[0.1, 0.2, 0.3, 1.0], [0.4, 0.5, 0.6, 1.0], [0.7, 0.8, 0.9, 1.0]])
        px = L.pixchop_to_pixels(pts.T, 2)
        self.assertEqual(px.tolist(), [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        self.assertEqual(L.pixchop_to_pixels(pts.T, 5).shape, (3, 3))   # fewer points than pixels: the rest keep 0


if __name__ == '__main__':
    unittest.main()
