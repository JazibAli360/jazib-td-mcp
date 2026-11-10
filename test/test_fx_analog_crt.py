"""Offline tests for FX_analog modules 'crt' (+ 'monitor' presets) and 'crtfault':
builders/fx_analog_crt.py, builders/fx_analog_crtfault.py, builders/fx_analog_crt_logic.py. Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_analog_crt.py'
GLSL checks compile with glslc (OpenGL target) against stubs of the TD compute built-ins: a syntax/type check, NOT a TD
compile (LIVE CHECK R1 in docs/builds/fx_analog_crt.md)."""
import math
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
L = {}
with open(os.path.join(B, 'fx_analog_crt_logic.py')) as fh:
    exec(fh.read(), L)


def _mod(name):
    ns = {'HERE': B}
    with open(os.path.join(B, 'fx_analog_%s.py' % name)) as fh:
        exec(fh.read(), ns)
    return ns


CRT, FAULT = _mod('crt'), _mod('crtfault')
JZB_LABELS = ['Amount', 'Curvature', 'Scanlines', 'Mask', 'Halation', 'Degauss', 'Lines', 'Sharpness', 'Mask Size',
              'Mask Strength', 'Corner', 'Vignette', 'Brightness', 'Border', 'Roll', 'Flicker', 'Hum Bar', 'Seed',
              'Randomness']
TD_STUB = """#version 460
uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
"""

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None


def pars(M):
    return dict((n, (s, d, o)) for _pg, ps in M['PAGES'] for n, s, d, o in ps)


class Files(unittest.TestCase):
    def test_ascii(self):
        for f in ('fx_analog_crt.py', 'fx_analog_crtfault.py', 'fx_analog_crt_logic.py'):
            with open(os.path.join(B, f), 'rb') as fh:
                fh.read().decode('ascii')

    def test_module_api(self):
        for M, name in ((CRT, 'crt'), (FAULT, 'crtfault')):
            self.assertEqual(M['MODULE'], name)
            for k in ('PAGES', 'PANEL_PAGES', 'PRESETS', 'build', 'shader_texts'):
                self.assertIn(k, M)
            names = [n for _pg, ps in M['PAGES'] for n, *_ in ps]
            self.assertEqual(names[0], 'Amount')
            self.assertEqual(len(names), len(set(names)))
            for n in names:                                   # TD custom par names: one capital then lower/digits
                self.assertRegex(n, r'^[A-Z][a-z0-9]*$')
            for pg in M['PANEL_PAGES']:
                self.assertIn(pg, [p for p, _ in M['PAGES']])


class Parity(unittest.TestCase):
    def test_jzb_control_labels(self):
        labels = set(o.get('label', n) for n, (s, d, o) in pars(CRT).items())
        for lb in JZB_LABELS:
            self.assertIn(lb, labels)

    def test_defaults_match_logic(self):
        P = pars(CRT)
        for k, v in L['CRT_DEFAULTS'].items():
            self.assertIn(k, P)
            self.assertEqual(P[k][1], v, k)

    def test_jzb_ranges(self):
        P = pars(CRT)
        for n, lo, hi in (('Lines', 120, 1080), ('Masksize', 3, 12), ('Brightness', 0, 2), ('Roll', -1, 1),
                          ('Seed', 0, 99)):
            self.assertEqual((P[n][2]['min'], P[n][2]['max']), (lo, hi), n)
        self.assertEqual(P['Mask'][2]['names'][:4], ['off', 'aperture', 'slot', 'shadow'])


class Raster(unittest.TestCase):
    def test_vertical_canvas(self):
        self.assertEqual(L['raster_for'](1080, 1920, 480), (4, 270, 480))
        self.assertEqual(L['raster_for'](1080, 1920, 120), (16, 68, 120))   # 67.5 rounds up like lround
        self.assertEqual(L['raster_for'](1080, 1920, 1080), (3, 360, 640))  # 3 px floor
        self.assertEqual(L['raster_for'](1080, 1920, 480, 1), (3, 640, 360))
        self.assertEqual(L['glow_wh'](1080, 1920), (135, 240))
        self.assertEqual(L['raster_taps'](4), 2)

    def test_sharp(self):
        self.assertAlmostEqual(L['sharp_slope'](0), 1.0)
        self.assertAlmostEqual(L['sharp_slope'](0.5), 1 / 0.54)


class Mask(unittest.TestCase):
    def test_balance_every_type_and_size(self):
        for kind in (1, 2, 3, 4):
            for size in range(3, 13):
                rows = L['mask_rows'](kind, size)
                n = [0, 0, 0]
                for y in range(rows * 2):
                    for x in range(size * 4):
                        c = L['mask_channel'](kind, size, x, y)
                        if c >= 0:
                            n[c] += 1
                self.assertEqual(n[0], n[1], (kind, size))
                self.assertEqual(n[1], n[2], (kind, size))
                self.assertGreater(n[0], 0)

    def test_off(self):
        self.assertEqual(L['mask_channel'](0, 6, 3, 3), -2)

    @unittest.skipIf(np is None, 'numpy')
    def test_np_twin(self):
        y, x = np.mgrid[0:40, 0:40]
        for kind in range(5):
            for size in (3, 6, 7, 9, 12):
                a = L['mask_channel_np'](kind, size, x, y)
                b = np.vectorize(lambda u, v: L['mask_channel'](kind, size, u, v))(x, y)
                self.assertTrue((a == b).all(), (kind, size))


class Motion(unittest.TestCase):
    def test_flicker_frames(self):
        self.assertEqual([L['flicker_frames'](f) for f in (24, 25, 30, 50, 60)], [1, 2, 2, 3, 3])

    def test_roll_locks_exactly(self):
        ph, last = 0.0, 0.0
        for _ in range(30):
            ph, last = L['roll_step'](ph, last, 1 / 60.0, 0.4 * 1.5)
        self.assertGreater(ph, 0)
        n = 0
        while ph != 0.0:
            ph, last = L['roll_step'](ph, last, 1 / 60.0, 0.0)
            n += 1
        self.assertLessEqual(n, 101)                       # <= 1/0.6 s at 60 fps
        self.assertEqual(L['roll_step'](0.0, last, 1 / 60.0, 0.0)[0], 0.0)

    def test_degauss_envelope(self):
        self.assertEqual(L['degauss_env'](-1), 0.0)
        self.assertEqual(L['degauss_env'](0), 1.0)
        self.assertGreater(L['degauss_env'](2.0), 0.0)
        self.assertEqual(L['degauss_env'](2.1), 0.0)

    def test_power_shape(self):
        self.assertEqual(L['power_shape'](True, 1e9, 0.6), (1.0, 1.0, 1.0, 0.0))
        self.assertEqual(L['power_shape'](False, 1.0, 0.6), (0.0, 0.0, 0.0, 0.0))
        sy, sx, g, d = L['power_shape'](False, 0.25, 0.6)    # 42 %: the line phase
        self.assertAlmostEqual(sy, L['LINE_H'])
        self.assertGreater(g, 1.0)
        self.assertGreater(L['power_shape'](False, 0.45, 0.6)[3], 0.0)
        self.assertLess(L['power_shape'](True, 0.0, 0.6)[2], 0.01)

    def test_clock_rows(self):
        st = L['clock_init']()
        r0 = L['clock_step'](st, {'Scanlines': 0.6}, 10.0, 60.0)
        self.assertEqual(len(r0), L['CLOCK_ROWS'])
        self.assertTrue(all(len(r) == 4 and all(math.isfinite(v) for v in r) for r in r0))
        self.assertEqual(r0[8][3], 1.0)                    # first cook: history reset
        r1 = L['clock_step'](st, {'Scanlines': 0.6}, 10.0 + 1 / 60.0, 60.0)
        self.assertEqual(r1[8][3], 0.0)
        self.assertNotEqual(r0[7][3], r1[7][3])            # field alternates
        self.assertEqual(r1[11], [1.0, 1.0, 1.0, 0.0])     # power steady
        self.assertEqual(r1[0][2], 1.0)                    # no flicker
        self.assertEqual(r1[2][0], 0.0)                    # Randomness 0: no purity
        r2 = L['clock_step'](st, {}, 11.0, 60.0)
        self.assertEqual(r2[8][3], 1.0)                    # gap > 0.25 s: reset

    def test_clock_flicker_steps_at_20hz(self):
        st = L['clock_init']()
        steps = [L['clock_step'](st, {'Flicker': 1.0}, k / 60.0, 60.0)[1][0] for k in range(60)]
        self.assertEqual(max(steps) - min(steps), 20)          # 60 frames at 60 fps = 20 steps

    def test_clock_degauss(self):
        st = L['clock_init']()
        P = {'Degausstime': 5.0, 'Degausscount': 1, 'Scanlines': 0.6}
        r = L['clock_step'](st, P, 5.0, 60.0)
        self.assertAlmostEqual(r[3][3], 1.0)
        self.assertAlmostEqual(r[2][0], L['PURITY_DEGAUSS'])
        self.assertEqual(L['clock_step'](st, P, 8.0, 60.0)[3][3], 0.0)


class Presets(unittest.TestCase):
    def test_monitors(self):
        self.assertGreaterEqual(len(L['MONITORS']), 12)
        P = pars(CRT)
        self.assertEqual(P['Monitor'][2]['names'], L['monitor_names']())
        for key, _label, over in L['MONITORS']:
            for k, v in over.items():
                self.assertIn(k, P, (key, k))
                if P[k][0] == 'Menu':
                    self.assertIn(v, P[k][2]['names'], (key, k))
            self.assertEqual(set(L['monitor_values'](key)), set(L['CRT_DEFAULTS']))
        self.assertEqual(L['monitor_values']('custom'), {})

    def test_zkit_presets(self):
        for M in (CRT, FAULT):
            P = pars(M)
            slots = [s for s, _n, _v in M['PRESETS']]
            self.assertEqual(len(slots), len(set(slots)))
            self.assertLessEqual(max(slots), 8)            # zkit_rt.SLOTS
            for _s, _n, vals in M['PRESETS']:
                for k, v in vals.items():
                    self.assertIn(k, P, k)
                    self.assertNotIn(P[k][0], ('Pulse',), k)
                    if P[k][0] == 'Menu':
                        self.assertTrue(0 <= v < len(P[k][2]['names']), (k, v))
        names = [n for _s, n, _v in CRT['PRESETS']]
        for r in ('Broadcast Monitor', 'Arcade', 'Old Television', 'Lost Sync', 'Flat Scanlines'):
            self.assertIn(r, names)                        # same names as JZB_Lofi_CRT.yaml


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.comp')
            with open(p, 'w') as fh:
                fh.write(TD_STUB + text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def test_all_passes(self):
        for M, name in ((CRT, 'crt'), (FAULT, 'crtfault')):
            for k, t in M['shader_texts']().items():
                self.assertNotIn('%(LIB)s', t)
                self.assertIn('uK[%d]' % L['CLOCK_ROWS'], t if k != 'glow' else L['GLSL_LIB'])
                t.encode('ascii')
                self._ok(t, '%s.%s' % (name, k))


@unittest.skipIf(np is None, 'numpy')
class Reference(unittest.TestCase):
    W, H = 216, 384                                         # 1/5 of 1080x1920, same aspect

    def img(self, v=0.5):
        a = np.zeros((self.H, self.W, 4))
        a[..., :3] = v
        a[..., 3] = 1
        return a

    FLAT = dict(Curvature=0, Corner=0, Vignette=0, Mask='off', Halation=0, Scanlines=1.0, Lines=96, Brightness=1.0)

    def test_amount0_exact(self):
        im = np.random.RandomState(1).rand(self.H, self.W, 4)
        self.assertEqual(np.abs(L['crt_ref'](im, {'Amount': 0}) - im).max(), 0.0)

    def test_scanlines_periodic_and_dark_deeper(self):
        depth = {}
        for v in (0.2, 1.0):
            o = L['crt_ref'](self.img(v), self.FLAT)[:, 100, 0]
            self.assertTrue(np.allclose(o[40:44], o[44:48], atol=1e-9))    # period = pitch 4
            seg = o[40:44]
            depth[v] = 1 - seg.min() / seg.max()
        self.assertGreater(depth[0.2], 0.5)
        self.assertLess(depth[1.0], 0.15)

    def test_aperture_on_white(self):
        o = L['crt_ref'](self.img(1.0), dict(self.FLAT, Scanlines=0, Mask='aperture', Masksize=6, Maskstrength=0.5))
        row = o[100, 0:6, :3]
        self.assertTrue(np.allclose(row[0], [1.0, math.sqrt(0.5), math.sqrt(0.5)], atol=1e-6))
        self.assertTrue(np.allclose(row[2], [math.sqrt(0.5), 1.0, math.sqrt(0.5)], atol=1e-6))

    def test_curvature_corner_black(self):
        o = L['crt_ref'](self.img(), dict(Curvature=1, Corner=0.3, Mask='off', Halation=0))
        self.assertTrue(np.allclose(o[0, 0], [0, 0, 0, 1]))
        t = L['crt_ref'](self.img(), dict(Curvature=1, Corner=0.3, Mask='off', Halation=0, Border='transparent'))
        self.assertTrue(np.allclose(t[0, 0], [0, 0, 0, 0]))

    def test_roll_bar(self):
        st = L['clock_init']()
        rows = None
        for k in range(20):
            rows = L['clock_step'](st, {'Roll': 0.5, 'Scanlines': 0.6}, k / 60.0, 60.0)
        o = L['crt_ref'](self.img(), dict(self.FLAT, Roll=0.5), rows)
        blank_rows = int((o[:, 100, :3].max(axis=1) == 0).sum())
        self.assertTrue(abs(blank_rows - 0.08 * self.H) <= 2, blank_rows)

    def test_fault_amount0_exact_and_power_off_black(self):
        im = np.random.RandomState(2).rand(self.H, self.W, 4)
        st = L['clock_init']()
        rows = L['clock_step'](st, {'Amount': 0.0}, 1.0, 60.0)
        self.assertEqual(np.abs(L['fault_ref'](im, {'Amount': 0.0}, rows) - im).max(), 0.0)
        rows = L['clock_step'](st, {'Amount': 0.0, 'Power': 0.0, 'Powertime': 0.0}, 2.0, 60.0)
        o = L['fault_ref'](im, {'Amount': 0.0}, rows)
        self.assertTrue(np.allclose(o[..., :3], 0) and np.allclose(o[..., 3], 1))

    def test_fault_tear_moves_rows(self):
        im = np.zeros((self.H, self.W, 4))
        im[..., 0] = np.linspace(0, 1, self.W)[None, :]
        im[..., 3] = 1
        rows = L['clock_step'](L['clock_init'](), {}, 1.0, 60.0)
        o = L['fault_ref'](im, {'Tear': 0.5, 'Tearbands': 2.0}, rows)
        self.assertGreater(np.abs(o - im).mean(), 0.05)
        self.assertTrue((o[..., :3].max(axis=-1) == 0).any())    # H blanking appears

    def test_check_dir_round_trip(self):
        import json
        im = np.random.RandomState(3).rand(self.H, self.W, 4)
        im[..., :3] *= im[..., 3:4]
        P = dict(self.FLAT, Mask='slot', Convx=1.0)
        rows = L['clock_step'](L['clock_init'](), dict(P), 0.0, 60.0)
        with tempfile.TemporaryDirectory() as d:
            np.save(os.path.join(d, 'src.npy'), im.astype(np.float32))
            np.save(os.path.join(d, 'out.npy'), L['crt_ref'](im, P, rows).astype(np.float32))
            json.dump({'module': 'crt', 'P': P, 'rows': rows}, open(os.path.join(d, 'meta.json'), 'w'))
            r = L['check_dir'](d)
        self.assertLess(r['max'], 1e-5)
        compile(L['save_snippet']('/project1/lab/FX_analog/crt1', '/tmp/x', 'crt'), 'snippet', 'exec')
        self.assertTrue(L['save_snippet']('/a', '/b', 'crt').startswith('# allow-readback'))


if __name__ == '__main__':
    unittest.main()
