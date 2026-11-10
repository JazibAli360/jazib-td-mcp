"""Offline tests for builders/laser_path_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_laser_path.py'"""
import math
import os
import struct
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import laser_path_logic as L  # noqa: E402


def square_shape():
    return L.build_shapes(L.pattern_rows('square', size=0.5))


class Angles(unittest.TestCase):
    def test_corner_angle(self):
        self.assertAlmostEqual(L.corner_angle((-1, 0), (0, 0), (1, 0)), 180.0)
        self.assertAlmostEqual(L.corner_angle((-1, 0), (0, 0), (0, 1)), 90.0)
        self.assertAlmostEqual(L.corner_angle((1, 0), (0, 0), (1, 0)), 0.0)
        self.assertAlmostEqual(L.corner_angle((0, 0), (0, 0), (1, 0)), 180.0)

    def test_hold_count(self):
        self.assertEqual(L.hold_count(180, 1, 9, 0, 1), 1)
        self.assertEqual(L.hold_count(0, 1, 9, 0, 1), 9)
        self.assertEqual(L.hold_count(90, 1, 9, 0, 1), 5)
        self.assertEqual(L.hold_count(90, 1, 9, 2, 1), 7)
        prev = None
        for a in range(0, 181, 5):
            h = L.hold_count(a, 1, 30, 0, 1)
            if prev is not None:
                self.assertLessEqual(h, prev)
            prev = h
        # snippet default min = max = 0.1 ms at 48000 pps -> 4.8 -> 5 samples at any angle
        self.assertEqual(L.hold_count(90, 0.1, 0.1, 0, 48.0), 5)


class Resample(unittest.TestCase):
    def test_edge(self):
        a, b = (0.0, 0.0), (1.0, 0.0)
        s = L.resample_edge(a, b, 0.3)
        self.assertEqual(len(s), 4)
        self.assertTrue(np.all(s[-1] == np.array(b)))
        steps = np.hypot(*np.diff(np.vstack([a, s]), axis=0).T)
        self.assertTrue(np.all(steps <= 0.3 + 1e-12))
        self.assertEqual(len(L.resample_edge(a, a, 0.1)), 1)
        self.assertEqual(len(L.resample_edge(a, (0.3, 0), 0.1)), 3)

    def test_no_duplicates_between_edges(self):
        p = L.params(stepsize=0.1, minhold=0, maxhold=0, pps=1000)
        b = L.shape_samples(L.build_shapes(L.pattern_rows('square', size=0.5))[0], p)
        xy = np.asarray(b.xy)
        d = np.hypot(*np.diff(xy, axis=0).T)
        self.assertEqual(int((d < 1e-12).sum()), 0)
        self.assertEqual(len(xy), 1 + 4 * 10)        # start + 4 edges of length 1 at step 0.1


class Shapes(unittest.TestCase):
    def test_square_closed_corners(self):
        s = square_shape()
        self.assertEqual(len(s), 1)
        self.assertTrue(s[0]['closed'])
        self.assertEqual(len(s[0]['pts']), 4)
        self.assertEqual(int(s[0]['corner'].sum()), 4)

    def test_auto_corners(self):
        rows = [(0, 0, 1, 1, 1, 0, -1), (1, 0, 1, 1, 1, 0, -1), (2, 0.1, 1, 1, 1, 0, -1), (2, 1, 1, 1, 1, 0, -1)]
        s = L.build_shapes(rows, cornertol=25)[0]
        self.assertFalse(s['closed'])
        self.assertEqual(list(s['corner']), [False, False, True, False])

    def test_ids_split(self):
        s = L.build_shapes(L.pattern_rows('dashed', count=5))
        self.assertEqual(len(s), 5)

    def test_xform(self):
        s = L.apply_xform(square_shape(), rotate=90, offx=0.1)
        self.assertTrue(np.allclose(s[0]['pts'][0], (0.5 + 0.1, -0.5)))
        s = L.apply_xform(square_shape(), swap=True, flipx=True)
        self.assertTrue(np.allclose(s[0]['pts'][0], (-0.5, 0.5)))
        w = L.apply_xform(square_shape(), warp=L.IDENTITY_WARP)
        self.assertTrue(np.allclose(w[0]['pts'], square_shape()[0]['pts']))
        g = [(x * 2, y * 2) for x, y in L.IDENTITY_WARP]
        w = L.apply_xform(square_shape(), warp=g)
        self.assertTrue(np.allclose(w[0]['pts'], square_shape()[0]['pts'] * 2))


class Order(unittest.TestCase):
    def scattered(self, n=50, seed=3):
        return L.build_shapes(L.pattern_rows('dashed', count=n, seed=seed))

    def test_permutation_and_shorter(self):
        for seed in (1, 3, 7, 11):
            sh = self.scattered(seed=seed)
            seq, t0, t1 = L.order_shapes(sh, 'twoopt')
            self.assertEqual(len(seq), 50)
            ins = sorted(tuple(np.round(np.sort(s['pts'], 0).ravel(), 9)) for s in sh)
            outs = sorted(tuple(np.round(np.sort(s['pts'], 0).ravel(), 9)) for s in seq)
            self.assertEqual(ins, outs)
            self.assertLessEqual(t1, t0)
            self.assertLessEqual(t1, 0.8 * t0)
            self.assertAlmostEqual(L.blank_travel(seq), t1)

    def test_twoopt_not_worse_than_greedy(self):
        sh = self.scattered()
        _, _, tg = L.order_shapes(sh, 'nearest')
        _, _, tt = L.order_shapes(sh, 'twoopt')
        self.assertLessEqual(tt, tg + 1e-9)

    def test_deterministic(self):
        sh = self.scattered()
        a = L.order_shapes(sh, 'twoopt')[0]
        b = L.order_shapes(sh, 'twoopt')[0]
        self.assertTrue(all(np.array_equal(x['pts'], y['pts']) for x, y in zip(a, b)))

    def test_closed_rotation(self):
        sq = L.build_shapes(L.pattern_rows('square', size=0.5))[0]
        dot = L.make_shape([(0.6, 0.6)], [(1, 1, 1)], False)
        plan = L.greedy_order([dot, sq], start=(0.6, 0.6))
        self.assertEqual(plan[0][0], 0)
        i, rev, rot = plan[1]
        self.assertTrue(np.allclose(sq['pts'][rot], (0.5, 0.5)))

    def test_open_reversal(self):
        a = L.make_shape([(0, 0), (0.5, 0)], [(1, 1, 1)] * 2, False)
        b = L.make_shape([(1.5, 0), (0.6, 0)], [(1, 1, 1)] * 2, False)
        seq, t0, t1 = L.order_shapes([a, b], 'nearest', start=(0, 0))
        self.assertTrue(np.allclose(seq[1]['pts'][0], (0.6, 0)))
        self.assertLessEqual(t1, t0)

    def test_none_keeps(self):
        sh = self.scattered()
        seq, t0, t1 = L.order_shapes(sh, 'none')
        self.assertEqual(t0, t1)


class Blanks(unittest.TestCase):
    def test_phase_counts(self):
        p = L.params(pps=10000, preblankon=0.3, postblankon=0.5, preblankoff=0.2, postblankoff=0.4, bstepsize=0.25)
        b = L.insert_blanks((0, 0), (1, 1, 1), (1, 0), (1, 0, 0), p)
        f = b.flag
        self.assertEqual(f.count(3), 3)
        self.assertEqual(f.count(4), 5)
        self.assertEqual(f.count(5), 4)
        self.assertEqual(f.count(6), 2)
        self.assertEqual(f.count(7), 4)
        # phases appear in order 3, 4, 5, 6, 7
        seen = [f[0]] + [f[k] for k in range(1, len(f)) if f[k] != f[k - 1]]
        self.assertEqual(seen, [3, 4, 5, 6, 7])
        dark = [c for c, fl in zip(b.rgb, f) if fl in (4, 5, 6)]
        self.assertTrue(all(c == (0, 0, 0) for c in dark))
        self.assertEqual(b.rgb[-1], (1, 0, 0))

    def test_single_closed_has_no_blanks(self):
        r = L.run_engine(L.pattern_rows('square'), L.params())
        self.assertEqual(r['stats']['points_blank'], 0)

    def test_two_shapes_blank_twice(self):
        rows = L.pattern_rows('grid')
        r = L.run_engine(rows, L.params(postblankon=0.1, preblankoff=0.1))
        self.assertEqual(L.count_runs(r['flag'], 5), 9)    # 9 dots, looping image -> 9 moves


class Delay(unittest.TestCase):
    def test_delay(self):
        c = np.random.default_rng(1).uniform(size=(20, 3))
        d = L.delay_colour(c, 3)
        for i in range(3, 20):
            self.assertTrue(np.array_equal(d[i], c[i - 3]))
        self.assertTrue(np.array_equal(L.delay_colour(c, 0), c))

    def test_engine_xy_unchanged(self):
        a = L.run_engine(L.pattern_rows('star'), L.params(colordelay=0))
        b = L.run_engine(L.pattern_rows('star'), L.params(colordelay=0.5))
        self.assertTrue(np.array_equal(a['x'], b['x']))
        self.assertTrue(np.array_equal(np.roll(a['r'], L.ms_to_samples(0.5, 30000)), b['r']))


class Budget(unittest.TestCase):
    def test_budget(self):
        self.assertEqual(L.frame_budget(30000, 30), 1000)
        self.assertEqual(L.frame_budget(48000, 60), 800)
        self.assertAlmostEqual(L.overflow_ratio(1600, 800), 2.0)
        self.assertEqual(L.frames_per_image(801, 800), 2)
        self.assertEqual(L.frames_per_image(800, 800), 1)
        w = L.frame_window(10, 4, 2)
        self.assertEqual(list(w), [8, 9, 0, 1])

    def test_thin_fits(self):
        rows = L.pattern_rows('dashed', count=20)   # fixed blank phases cost ~5 samples per shape: 20 fit in 200
        p = L.params(pps=12000, fps=60, overflow='thin', stepsize=0.005, bstepsize=0.01)
        r = L.run_engine(rows, p)
        self.assertLessEqual(r['stats']['points_total'], 200)

    def test_drop_fits(self):
        rows = L.pattern_rows('dashed', count=50)
        r = L.run_engine(rows, L.params(pps=12000, fps=60, overflow='drop'))
        self.assertLessEqual(r['stats']['points_total'], 200)
        self.assertLess(r['stats']['shapes'], 50)

    def test_frames_policy_reports(self):
        r = L.run_engine(L.pattern_rows('dashed', count=50), L.params(pps=12000, fps=60))
        self.assertGreater(r['stats']['frames_per_image'], 1)
        self.assertGreater(r['stats']['overflow'], 1.0)


class Engine(unittest.TestCase):
    def test_square_numbers(self):
        p = L.params(pps=48000, fps=60, stepsize=0.02, minhold=0.1, maxhold=0.1)
        r = L.run_engine(L.pattern_rows('square', size=0.8), p)
        # 4 edges of 1.6 at 0.02 = 80 each, + start, + 4 corners x 5 samples
        self.assertEqual(r['stats']['points_total'], 1 + 320 + 20)
        self.assertEqual(L.count_runs(r['flag'], 1), 4)
        self.assertEqual(int((r['flag'] == 1).sum()), 20)
        self.assertEqual(r['stats']['corners'], 4)

    def test_square_numbers_float32_rows(self):
        # TD CHOPs hold float32: the same square read back from the rows CHOP must give the same 341 (live 26 Oct)
        rows = [[float(np.float32(v)) for v in r] for r in L.pattern_rows('square', size=0.8)]
        p = L.params(pps=48000, fps=60, stepsize=0.02, minhold=0.1, maxhold=0.1)
        self.assertEqual(L.run_engine(rows, p)['stats']['points_total'], 341)

    def test_export_check_square_and_dashes(self):
        for rows, p in ((L.pattern_rows('square', size=0.8), L.params(pps=48000, fps=60, stepsize=0.02)),
                        (L.pattern_rows('dashed', count=50), L.params(order='twoopt'))):
            r = L.run_engine(rows, p)
            data, rep = L.export_check(r['x'], r['y'], r['r'], r['g'], r['b'], r['i'])
            self.assertTrue(rep['ok'], rep)
            self.assertEqual(len(data), 64 + 8 * len(r['x']))
        self.assertGreater(rep['blank'], 0)              # dashes: blanked travel survives the round trip
        self.assertEqual(rep['blank'], rep['blank_back'])

    def test_order_in_engine(self):
        rows = L.pattern_rows('dashed', count=50)
        a = L.run_engine(rows, L.params(order='none'))['stats']['blank_travel']
        b = L.run_engine(rows, L.params(order='twoopt'))['stats']['blank_travel']
        self.assertLessEqual(b, 0.8 * a)

    def test_all_patterns(self):
        for n in L.PATTERNS:
            r = L.run_engine(L.pattern_rows(n, count=6, t=1.3), L.params())
            if n != 'text':
                self.assertGreater(r['stats']['points_total'], 0, n)

    def test_empty(self):
        r = L.run_engine([], L.params())
        self.assertEqual(r['stats']['points_total'], 0)

    def test_tint(self):
        r = L.run_engine(L.pattern_rows('square'), L.params(rgb=(1, 0, 0.5), gain=0.5))
        self.assertAlmostEqual(float(r['r'].max()), 0.5)
        self.assertAlmostEqual(float(r['g'].max()), 0.0)
        self.assertAlmostEqual(float(r['b'].max()), 0.25)


class Drive(unittest.TestCase):
    def test_bpm_2hz(self):
        t = np.arange(0, 2, 1 / 600.0)
        v = np.array([L.drive_level('bpm', x, bpm=120) for x in t])
        edges = int(np.sum(np.abs(np.diff(v)) > 0.5))
        self.assertEqual(edges, 7)                 # 2 Hz square over 2 s: on/off 4 periods = 7 inner edges
        self.assertEqual(L.drive_level('manual', 3.3, manual=0.4), 0.4)
        self.assertAlmostEqual(L.drive_level('audio', 0, audio=0.5, audioamt=1.0), 0.5)
        self.assertEqual(L.strobe_gate('off', 1.0), 1.0)
        self.assertEqual(L.strobe_gate('audio', 1.0, audio=0.1), 0.0)


class Galvo(unittest.TestCase):
    def test_overshoot(self):
        x = np.r_[np.zeros(10), np.ones(4000)]
        y = L.biquad(x, L.galvo_coeffs(48000, 500, 0.7))
        ov = (y.max() - 1.0) * 100
        self.assertAlmostEqual(L.step_overshoot(0.7), 4.6, places=1)
        self.assertAlmostEqual(ov, L.step_overshoot(0.7), delta=0.3)
        self.assertAlmostEqual(float(y[-1]), 1.0, places=4)    # DC gain 1

    def test_stable_to_nyquist(self):
        for bw in (100, 6000, 20000, 23999):
            y = L.biquad(np.r_[np.zeros(4), np.ones(3000)], L.galvo_coeffs(48000, bw, 0.7))
            self.assertTrue(np.all(np.isfinite(y)))
            self.assertLess(abs(y[-1] - 1.0), 1e-3, bw)

    def test_impulse_area(self):
        x = np.zeros(6000)
        x[5] = 1.0
        c = L.galvo_coeffs(48000, 1000, 0.7)
        y = L.biquad(x, c, y1=0.0)
        self.assertAlmostEqual(float(y.sum()), 1.0, places=3)

    def test_loop_primed(self):
        r = L.run_engine(L.pattern_rows('square'), L.params(pps=48000))
        fx, fy = L.galvo_filter(r['x'], r['y'], 48000, 1500, 0.7)
        self.assertEqual(len(fx), len(r['x']))
        self.assertGreater(float(np.abs(fx).max()), 0.8)      # overshoot outside the 0.8 square
        fx2, _ = L.galvo_filter(r['x'], r['y'], 48000, 200000, 0.7)
        self.assertLess(float(np.abs(fx2 - r['x']).max()), 0.02)

    def test_dwell(self):
        r = L.run_engine(L.pattern_rows('square'), L.params(pps=48000))
        w = L.dwell_weights(r['x'], r['y'], 0.02)
        on_corner = w[r['flag'] == 1].mean()
        on_edge = w[r['flag'] == 0].mean()
        self.assertGreater(on_corner, 3 * on_edge)


class Ilda(unittest.TestCase):
    def test_round_trip(self):
        rng = np.random.default_rng(5)
        n = 50
        f = {'x': rng.uniform(-1, 1, n), 'y': rng.uniform(-1, 1, n), 'r': rng.uniform(0, 1, n),
             'g': rng.uniform(0, 1, n), 'b': rng.uniform(0, 1, n)}
        f['r'][3] = f['g'][3] = f['b'][3] = 0.0
        data = L.to_ilda_f5([f, f], name='TEST')
        self.assertEqual(len(data), 3 * 32 + 2 * n * 8)
        h = data[:32]
        self.assertEqual(h[:4], b'ILDA')
        self.assertEqual(h[4:7], b'\x00\x00\x00')
        self.assertEqual(h[7], 5)
        self.assertEqual(h[8:16], b'TEST    ')
        self.assertEqual(struct.unpack('>HHH', h[24:30]), (n, 0, 2))
        self.assertEqual(h[31], 0)
        self.assertEqual(struct.unpack('>H', data[-8:-6])[0], 0)       # null header at the end
        rec3 = data[32 + 3 * 8:32 + 4 * 8]
        self.assertEqual(rec3[4] & 0x40, 0x40)
        last = data[32 + (n - 1) * 8:32 + n * 8]
        self.assertEqual(last[4] & 0x80, 0x80)
        rec0 = data[32:40]                                                 # BGR order
        self.assertEqual(rec0[5], int(round(f['b'][0] * 255)))
        self.assertEqual(rec0[7], int(round(f['r'][0] * 255)))
        back = L.from_ilda(data)
        self.assertEqual(len(back), 2)
        self.assertTrue(np.allclose(back[0]['x'], f['x'], atol=1 / 32768.0))
        self.assertTrue(np.allclose(back[0]['y'], f['y'], atol=1 / 32768.0))
        self.assertTrue(back[0]['blank'][3])
        self.assertTrue(back[0]['last'][-1])


class Wire(unittest.TestCase):
    def test_etherdream(self):
        self.assertEqual(L.ED_POINT.size, 18)
        self.assertEqual(L.ED_STATUS.size, 20)
        b = L.etherdream_pack_points([0, 1], [0, -1], [1, 0], [0, 0], [0, 1])
        self.assertEqual(len(b), 36)
        v = L.ED_POINT.unpack(b[18:])
        self.assertEqual(v[1:4], (32767, -32767, 0))
        st = L.etherdream_parse_status(L.ED_STATUS.pack(0, 0, 2, 0, 0, 0, 0, 1234, 30000, 99))
        self.assertEqual(st['playback_state'], 2)
        self.assertEqual(st['buffer_fullness'], 1234)
        self.assertEqual(st['point_rate'], 30000)

    def test_lasercube(self):
        n = 300
        x = np.linspace(-1, 1, n)
        dg, nxt = L.lasercube_pack(x, x, np.ones(n), np.zeros(n), np.zeros(n), msg=254, frame=7)
        self.assertEqual(len(dg), 3)
        self.assertEqual(nxt, (254 + 3) & 0xff)
        self.assertEqual(dg[0][:4], bytes([0xa9, 0, 254, 7]))
        self.assertEqual(dg[1][2], 255)
        self.assertEqual(dg[2][2], 0)
        self.assertTrue(all(len(d) <= 4 + 140 * 10 for d in dg))
        self.assertEqual(struct.unpack_from('<H', dg[0], 4)[0], 0)
        self.assertEqual(L.lc12(0.0), 2048)
        self.assertEqual(L.lc12(5.0), 4095)

    def test_lasercube_info(self):
        buf = bytearray(64)
        buf[0] = 0x77
        buf[2], buf[3] = 0, 25
        buf[5] = 1
        struct.pack_into('<I', buf, 10, 30000)
        struct.pack_into('<I', buf, 14, 35000)
        struct.pack_into('<H', buf, 19, 5800)
        struct.pack_into('<H', buf, 21, 6000)
        i = L.lasercube_parse_info(bytes(buf))
        self.assertEqual((i['dac_rate'], i['max_dac_rate'], i['rx_free'], i['rx_size']), (30000, 35000, 5800, 6000))
        self.assertTrue(i['output_enabled'])


B = os.path.join(os.path.dirname(HERE), 'builders')
FILES = ['laser_path_logic.py', 'laser_path_rt.py', 'laser_path.py', os.path.join('glsl', 'laser_path_sprite.glsl')]


def _src(name):
    with open(os.path.join(B, name), 'rb') as f:
        return f.read().decode('ascii')     # TD reads these files: pure ASCII (T-00a)


class Ascii(unittest.TestCase):
    def test_ascii(self):
        for n in FILES:
            _src(n)

    def test_python_compiles(self):
        for n in FILES[:3]:
            compile(_src(n), n, 'exec')


class BuilderSafety(unittest.TestCase):
    """Static checks of the TD-side files for the crash rules (T-67, T-70, T-74, T-76) and the house pattern."""

    def test_no_crash_patterns(self):
        for n in ('laser_path_rt.py', 'laser_path.py'):
            s = _src(n)
            if n == 'laser_path_rt.py':        # CHOP channel reads (perf lane 2) are not TOP reads (T-74): one place only
                self.assertEqual(s.count('numpyArray('), 1)
                self.assertIn('return np.asarray(c.numpyArray(), dtype=np.float64) if c is not None', s)
                s = s.replace('c.numpyArray()', 'c.CHANNEL()')
            for bad in ('numpyArray(', 'evalTextSize(', 'cook(force', '.destroy(', 'cookRate =', 'op.store(',
                        '.store(\'', 'pane.owner'):
                if bad == ".store('" and n == 'laser_path.py':
                    continue                 # plain bool flag only (lp_fps_bound), checked below
                self.assertNotIn(bad, s, '%s in %s' % (bad, n))
        self.assertIn("c.store('lp_fps_bound', True)", _src('laser_path.py'))

    def test_glsl_single_pass_conventions(self):
        g = _src(os.path.join('glsl', 'laser_path_sprite.glsl'))
        self.assertIn('TDOutputSwizzle(', g)
        self.assertIn('out vec4 fragColor;', g)
        self.assertIn('void main()', g)
        self.assertNotIn('sTD2DInputs', g)   # no inputs: nothing to race (T-46)
        self.assertIn("SPRITE_FILE = os.path.join(HERE, 'glsl', 'laser_path_sprite.glsl')", _src('laser_path.py'))

    def _builder_ns(self):
        ns = {'__name__': 'lp_builder_test'}
        exec(compile(_src('laser_path.py'), 'laser_path.py', 'exec'), ns)   # module level touches no td names
        return ns

    def test_script_callbacks_render(self):
        ns = self._builder_ns()
        for name in ('rows', 'native_in', 'own', 'native_fix', 'drive', 'preview_pts'):
            code = ns['SCRIPT_CB'].format(name=name, what='x', fn='cook_' + name, clock=ns['CLOCK'].get(name, '0'))
            compile(code, name, 'exec')
            self.assertIn('def onCook(scriptOp)', code)
        compile(ns['STATS_CB'], 'stats', 'exec')
        compile(ns['PEXEC'], 'pexec', 'exec')

    def test_rt_functions_named_by_builder_exist(self):
        import re
        rt = _src('laser_path_rt.py')
        b = _src('laser_path.py')
        for fn in set(re.findall(r"'(cook_[a-z_]+)'", b)) | {'cook_stats', 'savesnap', 'drive_animated',
                                                              'preview_animated', 'decay_factor'}:
            self.assertIn('def %s(' % fn, rt, fn)

    def test_every_op_is_in_a_stage(self):
        import re
        b = _src('laser_path.py')
        made = set(re.findall(r"_mk\((?:c|geo), *[A-Za-z]+, *'([a-z0-9_]+)'\)", b))
        made |= set(re.findall(r"_script\(c, *scriptCHOP, *'([a-z0-9_]+)'", b))
        made |= {m + '_callbacks' for m in re.findall(r"_script\(c, *scriptCHOP, *'([a-z0-9_]+)'", b)}
        made.discard('spot')                 # inside beam_geo
        ns = self._builder_ns()
        self.assertTrue(made)
        staged = set()
        src_stages = b[b.index('stages = ['):]
        staged = set(re.findall(r"'([a-z0-9_]+)'", src_stages))
        missing = sorted(m for m in made if m not in staged)
        self.assertEqual(missing, [], 'ops without a stage box: %s' % missing)
        self.assertEqual(ns['KIT_PAGES'], ['Source', 'Path', 'Shape', 'Drive', 'Preview'])

    def test_par_names_house_rule(self):
        ns = self._builder_ns()
        for page, pars in ns['PAGES']:
            for name, style, default, o in pars:
                self.assertRegex(name, r'^[A-Z][a-z0-9]*$', name)   # one capital then lowercase/digits (T-00e)
                if style == 'Menu':
                    self.assertIn(default, o['names'], name)
                    self.assertEqual(len(o['names']), len(o['labels']), name)


class Perf(unittest.TestCase):
    def test_own_engine_1000_points_fast(self):
        """Spec 4.10: Own engine on a ~1000-point frame well under a frame (offline CPU, generous bound)."""
        import time
        rows = L.pattern_rows('star', count=5, size=0.8)
        p = L.params(pps=30000, fps=30, stepsize=0.01)
        L.run_engine(rows, p)
        t0 = time.perf_counter()
        for _ in range(5):
            r = L.run_engine(rows, p)
        ms = (time.perf_counter() - t0) * 1000 / 5
        self.assertGreater(r['stats']['points_total'], 500)
        self.assertLess(ms, 15.0, 'own engine %.2f ms' % ms)


class _FChan(object):
    def __init__(self, v):
        self.a = np.asarray(v, dtype=np.float32)
        self.vals = [float(x) for x in self.a]

    def numpyArray(self):
        return self.a.copy()

    def __getitem__(self, k):
        return float(self.a[k])


class _FChop(object):
    def __init__(self, chans):
        self.c = dict((k, _FChan(v)) for k, v in chans.items())
        self.numSamples = len(next(iter(self.c.values())).a) if self.c else 0
        self.numChans = len(self.c)

    def __getitem__(self, k):
        return self.c.get(k)


class _FScript(object):
    """Script CHOP stand-in that stores what TD would store: float32 samples."""
    def __init__(self, inp):
        self.inputs = [inp]
        self.out = {}

    def clear(self):
        self.out = {}

    def appendChan(self, nm):
        so = self

        class Ch(object):
            def __setattr__(self, k, v):
                if k == 'vals':
                    so.out[nm] = np.asarray(v, dtype=np.float32)

            def copyNumpyArray(self, a):
                so.out[nm] = np.asarray(a, dtype=np.float32).copy()
        so.out[nm] = np.zeros(max(1, getattr(self, 'numSamples', 1)), np.float32)
        return Ch()


class RtChannelIO(unittest.TestCase):
    """perf lane 2: laser_path_rt reads channels with numpyArray and writes with copyNumpyArray; the stored float32
    samples must equal the old .vals list path exactly (native_fix, drive at k != 1, preview_pts)."""
    def _rt(self, path, pars):
        class P(object):
            pass
        par = P()
        for k, v in pars.items():
            o = P()
            o.eval = (lambda v=v: v)
            setattr(par, k, o)
        comp = P()
        comp.par = par
        comp.op = lambda name: (type('M', (), {'module': L}) if name == 'lp_logic' else None)
        me = P()
        me.parent = lambda: comp
        T = type('T', (), {'seconds': 1.25, 'frame': 75})
        ns = {'me': me, 'absTime': T, 'op': comp.op}
        with open(path) as fh:
            exec(fh.read(), ns)
        return ns

    def test_old_equals_new(self):
        new = os.path.join(os.path.dirname(HERE), 'builders', 'laser_path_rt.py')
        old = os.environ.get('LP_RT_OLD')
        if not old or not os.path.exists(old):
            self.skipTest('set LP_RT_OLD to the previous laser_path_rt.py to compare')
        rng = np.random.default_rng(3)
        n = 517
        base = {'x': rng.uniform(-1, 1, n), 'y': rng.uniform(-1, 1, n), 'r': rng.uniform(0, 1, n) * (rng.uniform(0, 1, n) > 0.3),
                'g': rng.uniform(0, 1, n), 'b': rng.uniform(0, 1, n), 'flag': rng.integers(0, 6, n)}
        base['g'][:40] = 0.0
        base['b'][:40] = 0.0
        pars = {'Pps': 30000.0, 'Fps': 60.0, 'Intensitysrc': 'manual', 'Strobe': 'off', 'Source': 'pattern',
                'Pattern': 'square', 'Hold': False, 'Drivechop': None, 'Bpm': 120.0, 'Beatdiv': 1.0, 'Audioamt': 1.0,
                'Blackout': False, 'Strobeon': False, 'Showlag': False, 'Showblank': True, 'Stepsize': 0.02,
                'Spotgain': 1.3, 'Intensity': 0.7, 'Gain': 1.0}
        for fn, inp in (('cook_native_fix', {k: base[k] for k in 'xyrgb'}),
                        ('cook_native_fix', dict(base, i=base['r'] > 0.5, debug=base['flag'])),
                        ('cook_drive', dict(base, i=np.ones(n))),
                        ('cook_preview_pts', dict(base))):
            outs = []
            for path in (old, new):
                ns = self._rt(path, pars)
                ns['L'] = lambda: L
                if fn == 'cook_drive':
                    ns['L'] = lambda: type('LL', (), {'drive_level': staticmethod(lambda *a: 0.37),
                                                      'strobe_gate': staticmethod(lambda *a: 1.0)})
                s = _FScript(_FChop(inp))
                ns[fn](s)
                outs.append(s.out)
            self.assertEqual(sorted(outs[0]), sorted(outs[1]), fn)
            for k in outs[0]:
                self.assertTrue(np.array_equal(outs[0][k], outs[1][k]), (fn, k))



class PreviewCompute(unittest.TestCase):
    """Perf wave 3: the persistence (pixel) and look (compute, T-47) passes compile, and the replaced
    Level / Constant ops are gone from the builder."""

    def test_builder_chain(self):
        s = _src('laser_path.py')
        self.assertNotIn("levelTOP, 'persist_decay'", s)
        self.assertNotIn("constantTOP, 'bg'", s)
        self.assertIn("_compute(c, 'persist_add', PERSIST_FILE", s)
        self.assertIn('pixel=True)', s)
        self.assertIn("_compute(c, 'preview_comp', LOOK_FILE", s)

    def test_compute_shaders_compile(self):
        import shutil
        import subprocess
        import tempfile
        if shutil.which('glslc') is None:
            self.skipTest('no glslc')
        stub = ('#version 460\nuniform sampler2D sTD2DInputs[2];\nstruct TDTexInfo { vec4 res; vec4 depth; };\n'
                'uniform TDTexInfo uTDOutputInfo;\nlayout(rgba16f) uniform image2DArray mTDComputeOutputs[1];\n'
                'void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }\n')
        for n, ext in (('laser_path_persist.glsl', 'frag'), ('laser_path_look.glsl', 'comp')):
            g = _src(os.path.join('glsl', n))
            self.assertEqual('local_size_x' in g, ext == 'comp')
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, 's.' + ext)
                with open(p, 'w') as fh:
                    fh.write(stub + g)
                r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                    '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, n + r.stderr[:2000])

if __name__ == '__main__':
    unittest.main()
