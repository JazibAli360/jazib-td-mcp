"""Offline tests for FX_film wave C (camera, colour, gate, dof): the maths in builders/fx_film_<m>_logic.py, the
.cube parser + LUT reference, shader constants taken from the logic, Apple shared-memory limit, <= 3 GLSL TOP inputs,
and the doc's numbers. The fake-TD build + glslc compile of these modules run in test_fx_film.py (MODULES). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_film_wavec.py'"""
import math
import os
import random
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
DOC = os.path.join(REPO, 'docs', 'builds', 'fx_film.md')
sys.path.insert(0, HERE)
sys.path.insert(0, BUILDERS)
import fx_film_logic as RL            # noqa: E402
import fx_film_camera_logic as CL     # noqa: E402
import fx_film_colour_logic as KL     # noqa: E402
import fx_film_gate_logic as GL       # noqa: E402
import fx_film_dof_logic as DL        # noqa: E402
import test_fx_film as TF             # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None

WAVEC = ['camera', 'colour', 'gate', 'dof']


class Camera(unittest.TestCase):
    def test_trail_mean_age(self):
        for ang, fps in ((360, 24), (720, 24), (540, 30)):
            s = CL.shutter_frames(ang, fps)
            a = CL.trail_a(ang, fps, 1.0)
            self.assertAlmostEqual(a / (1 - a), (s - 1) / 2.0)            # exponential mean age = box mean age
        self.assertEqual(CL.trail_a(180, 24, 1.0) > 0, True)
        self.assertEqual(CL.trail_a(90, 24, 1.0), 0.0)                    # shutter shorter than a cook: no trail
        self.assertEqual(CL.trail_a(720, 24, 0.0), 0.0)

    def test_rolling_rows(self):
        self.assertAlmostEqual(CL.row_frac(0, 1919, 1080, 1920, 'topdown'), 0.5 / 1920)
        self.assertAlmostEqual(CL.row_frac(0, 0, 1080, 1920, 'bottomup'), 0.5 / 1920)
        top, bot = CL.pan_shift(0, 1919, 1080, 1920, 1, 24, 600), CL.pan_shift(0, 0, 1080, 1920, 1, 24, 600)
        self.assertAlmostEqual(top, -bot)
        self.assertAlmostEqual(bot - top, 600.0 / 24 * (1919.0 / 1920))  # whole readout = one camera frame of pan

    def test_flicker_and_flash(self):
        self.assertAlmostEqual(CL.sinc(math.pi * 100 * 0.01), 0.0, places=9)   # 1/100 s shutter hides 50 Hz bands
        self.assertEqual(CL.flicker_gain(0.0, 100.0, 0.0, 0.3, 0.0), 1.3)
        rows = CL.flash_rows(1920, 1.0, 24, CL.shutter_seconds(45, 24), 0.002, 0.0)
        self.assertLess(abs(rows - 1920 * (1 / 192.0) / (1 / 24.0)), 20)     # band = shutter / readout of the frame
        self.assertEqual(CL.flash_cov(1.0, 0.01, 0.002), 0.0)
        self.assertAlmostEqual(CL.flash_cov(0.0, 0.01, 0.002), 1.0)

    def test_footstep_zero_mean_and_path(self):
        n = 20000
        self.assertAlmostEqual(sum(CL.footstep((k + 0.5) / n) for k in range(n)) / n, 0.0, places=6)
        P = dict(n0=10.0, freq=0.6, oct=3, seed=3, shake=0.0, rot=0.0, zoomshake=0.0, steps=0.0, stepsroll=0.0,
                 ph0=0.3, rate=1.8, wobble=0.0, wph0=0.0, wfreq=12.0, panx=0.0, pany=0.0, zoom=0.0)
        self.assertEqual(CL.path_at(0.01, P), (0.0, 0.0, 0.0, 0.0))
        P['panx'] = 600.0
        self.assertAlmostEqual(CL.path_at(0.01, P)[0], 6.0)
        self.assertEqual(CL.src_point(100.5, 200.5, (0, 0, 0, 0), (540, 960)), (100.5, 200.5))

    def test_ae_and_iso(self):
        self.assertAlmostEqual(CL.ae_target_ev(0.09, 0.18, 4), 1.0)
        self.assertEqual(CL.ae_target_ev(1e-9, 0.18, 4), 4)
        v = 0.0
        for _ in range(600):
            v = CL.ae_step(v, 1.0, 1 / 60.0, 0.08, 0.6)
        self.assertAlmostEqual(v, 1.0, places=6)
        self.assertAlmostEqual(CL.iso_sigma(0.0, 100, 0.0004, 0.002), 0.002)
        g = [CL.box_muller(x, 7, 99) for x in range(20000)]
        m = sum(g) / len(g)
        self.assertLess(abs(m), 0.03)
        self.assertAlmostEqual(sum((x - m) ** 2 for x in g) / len(g), 1.0, delta=0.04)

    def test_shader_constants(self):
        _ns, _m, rec, _s = TF.run_build('camera')
        fx = [c for c in rec['compute'] if c['name'] == 'fx'][0]
        self.assertIn('VN2 = %r' % RL.vn_norm(2), fx['text'])
        path = [c for c in rec['compute'] if c['name'] == 'path'][0]
        self.assertEqual(path['res'], (CL.PATH_N, 1))
        self.assertIn('256.0', path['text'])


class Colour(unittest.TestCase):
    def test_matrices(self):
        m = KL.TO_AP1['rec709']                    # published sRGB -> ACEScg (Bradford)
        ref = [[0.6131, 0.3395, 0.0474], [0.0702, 0.9164, 0.0134], [0.0206, 0.1096, 0.8698]]
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(m[i][j], ref[i][j], delta=3e-4)
        for p in KL.PRIM_ORDER:
            I = KL.mmul(KL.FROM_AP1[p], KL.TO_AP1[p])
            for i in range(3):
                for j in range(3):
                    self.assertAlmostEqual(I[i][j], 1.0 if i == j else 0.0, places=9)
            w = KL.mvec(KL.TO_AP1[p], [1.0, 1.0, 1.0])        # white maps to white (adapted)
            for v in w:
                self.assertAlmostEqual(v, 1.0, places=6)

    def test_curves(self):
        self.assertAlmostEqual(KL.encode(0.18, 3), 0.3910, places=3)       # ARRI LogC3 EI800 mid grey
        self.assertAlmostEqual(KL.encode(0.18, 4), 420.0 / 1023.0, places=6)  # S-Log3 mid grey
        self.assertAlmostEqual(KL.encode(0.18, 5), 0.4135884, places=6)       # ACEScct mid grey
        for c in range(6):
            for x in (0.0, 0.001, 0.01, 0.18, 0.9, 4.0):
                if c in (0, 1) and x > 1:
                    continue
                self.assertAlmostEqual(KL.decode(KL.encode(x, c), c), x, places=7)

    def test_identity_pass(self):
        rnd = random.Random(2)
        for _ in range(50):
            rgb = [rnd.random() for _ in range(3)]
            for sp in ('srgb', 'linear', 'logc3', 'acescct'):
                o = KL.colour_px(rgb, {'Inspace': sp})
                for a, b in zip(o, rgb):
                    self.assertAlmostEqual(a, b, places=7)
        self.assertEqual(KL.colour_px([0.3, 0.2, 0.1], {'Amount': 0.0, 'Exposure': 3.0}), [0.3, 0.2, 0.1])

    def test_grade_ops(self):
        P = {'Inspace': 'linear'}
        self.assertAlmostEqual(KL.colour_px([0.18] * 3, dict(P, Exposure=1.0))[0], 0.36, places=7)
        w = KL.colour_px([0.18] * 3, dict(P, Temperature=1.0))
        self.assertGreater(w[0], w[2])
        y = sum(a * b for a, b in zip(KL.mvec(KL.TO_AP1['rec709'], w), KL.AP1_Y))
        self.assertAlmostEqual(y, 0.18, places=6)                           # WB keeps the luminance of grey
        self.assertAlmostEqual(KL.lgg(0.0, 0.1, 1.0, 1.0), 0.1)
        self.assertAlmostEqual(KL.lgg(1.0, 0.1, 1.0, 1.2), 1.2)
        self.assertAlmostEqual(KL.cdl(0.1, 2.0, 0.05, 1.0), 0.25)
        for sp in ('linear', 'log'):
            g = KL.colour_px([0.18] * 3, dict(P, Gradespace=sp, Contrast=1.7))
            for v in g:
                self.assertAlmostEqual(v, 0.18, places=6)                   # pivot is a fixed point

    @unittest.skipUnless(np is not None, 'numpy missing')
    def test_cube_parse_and_lut(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.cube')
            KL.write_cube(p, lambda r, g, b: (r, g, b), n=17)
            ident = KL.cube_strip(KL.parse_cube(open(p).read()))
            self.assertEqual(ident.shape, (18, 289, 4))
            p2 = os.path.join(d, 'f.cube')
            fn = lambda r, g, b: (g ** 0.8, 0.3 * r + 0.7 * b, (r * g) ** 0.5)   # noqa: E731
            KL.write_cube(p2, fn, n=9)
            lut = KL.cube_strip(KL.parse_cube(open(p2).read()))
        rnd = random.Random(4)
        for _ in range(200):
            v = [rnd.random() for _ in range(3)]
            for it in ('tetrahedral', 'trilinear'):
                o = KL.lut_apply(ident, v, it)
                for a, b in zip(o, v):
                    self.assertAlmostEqual(a, b, places=5)                   # file rounding 1e-6
        for r in range(9):                                                   # grid points exact
            for b in (0, 4, 8):
                v = (r / 8.0, 0.5, b / 8.0)
                o = KL.lut_apply(lut, v)
                for a, e in zip(o, fn(*v)):
                    self.assertAlmostEqual(a, e, places=5)
        empty = KL.cube_strip(None)
        self.assertEqual(KL.lut_apply(empty, [2.0, 0.5, -1.0]), [2.0, 0.5, -1.0])
        one = KL.parse_cube('LUT_1D_SIZE 3\n0 0 0\n0.25 0.5 0.75\n1 1 1\n')
        s1 = KL.cube_strip(one)
        self.assertEqual(s1.shape, (34, 33 * 33, 4))
        o = KL.lut_apply(s1, [0.5, 0.5, 0.5])
        self.assertAlmostEqual(o[0], 0.25, places=6)
        self.assertAlmostEqual(o[2], 0.75, places=6)
        with self.assertRaises(ValueError):
            KL.parse_cube('LUT_3D_SIZE 2\n0 0 0\n')

    def test_shader_constants(self):
        _ns, _m, rec, _s = TF.run_build('colour')
        t = rec['compute'][0]['text']
        self.assertIn('vec3(%r, %r, %r)' % tuple(KL.TO_AP1['rec709'][0]), t)
        self.assertIn('int[7](%s)' % ', '.join(str(KL.CURVE[s]) for s in KL.SPACES), t)
        self.assertEqual(rec['compute'][0]['ins'], ['in1', 'lut_a', 'lut_b'])


class Gate(unittest.TestCase):
    def test_aperture(self):
        self.assertEqual(GL.aperture(1080, 1920, 0), (540.0, 960.0))
        hx, hy = GL.aperture(1080, 1920, 2.39)
        self.assertAlmostEqual(hy * 2, 1080 / 2.39)
        hx, hy = GL.aperture(1080, 1920, 2.39, rotate=True)
        self.assertAlmostEqual(hx * 2, 1920 / 2.39)
        self.assertEqual(GL.picture_rows(1080, 1920, 2.39), 452)
        self.assertEqual(GL.aspect_value('custom', 1.5), 1.5)
        self.assertEqual(GL.aspect_value('a185', 1.5), 1.85)

    def test_rbox_vignette(self):
        self.assertAlmostEqual(GL.rbox(0, 0, 0, 0, 10, 5, 0), -5.0)
        self.assertAlmostEqual(GL.rbox(15, 0, 0, 0, 10, 5, 0), 5.0)
        self.assertAlmostEqual(GL.rbox(10, 5, 0, 0, 10, 5, 2), 2 * math.sqrt(2) - 2)
        self.assertEqual(GL.vignette(0.0, 2.0), 1.0)
        self.assertAlmostEqual(GL.vignette(1.0, 1.0), 0.25)
        self.assertAlmostEqual(GL.rnorm(1080, 1920, 1080, 1920), 1.0)
        n = 64
        pts = [GL.vogel(k, n) for k in range(n)]
        self.assertTrue(all(math.hypot(*q) <= 1.0 for q in pts))

    def test_aspect_table_matches_menu(self):
        ns, _m, _r, _s = TF.run_build('gate')
        menu = [o['names'] for _pg, pars in ns['PAGES'] for n, st, _d, o in pars if n == 'Aspect'][0]
        self.assertEqual(menu, GL.ASPECTS)
        self.assertEqual(len(GL.ASPECT_VALUES), len(GL.ASPECTS))


class Dof(unittest.TestCase):
    def test_coc(self):
        self.assertEqual(DL.coc_px(0.5, 0.5, 0.05, 2.8, 24), 0.0)
        self.assertEqual(DL.coc_px(0.52, 0.5, 0.05, 2.8, 24), 0.0)          # inside the Range zone
        self.assertGreater(DL.coc_px(0.8, 0.5, 0.05, 2.8, 24), 0)
        self.assertLess(DL.coc_px(0.2, 0.5, 0.05, 2.8, 24), 0)
        self.assertEqual(DL.coc_px(1.0, 0.0, 0.0, 1.4, 24), 24.0)           # clamped at Maxblur
        self.assertEqual(DL.coc_px(0.0, 1.0, 0.0, 1.4, 24, 2.0), -48.0)     # near scale after the clamp
        a = [DL.coc_px(d / 100.0, 0.5, 0.05, 2.8, 24) for d in range(101)]
        self.assertTrue(all(y >= x for x, y in zip(a, a[1:])))

    def test_shapes(self):
        for b in (3, 5, 6, 8):
            vals = [DL.poly_scale(t * 2 * math.pi / 720, b, 0.3) for t in range(720)]
            self.assertAlmostEqual(min(vals), math.cos(math.pi / b), places=3)
            self.assertAlmostEqual(max(vals), 1.0, delta=0.01)
        self.assertAlmostEqual(DL.plane_depth(0.5, 0.75), 0.75)
        self.assertAlmostEqual(DL.map_depth(1.0), 0.0)
        self.assertAlmostEqual(DL.gather_radius(2.0, 12.0, 0.35), 4.2)

    def test_camera_acc_fused(self):
        # Trail on = one fused pass (geo maths + trail, one rgba32float buffer); geo is not an input of acc
        _ns, m, rec, _s = TF.run_build('camera')
        c = dict((x['name'], x) for x in rec['compute'])
        self.assertEqual(c['acc']['ins'], ['in1', 'path', 'ae'])
        self.assertEqual(c['geo']['ins'], ['in1', 'path', 'ae'])
        self.assertNotIn('TDImageLoadOutput(1', c['acc']['text'])
        self.assertEqual(c['acc']['op'].par.numcolorbufs.val, 1)
        self.assertIn('vec3 geoAt(', c['acc']['text'])
        self.assertEqual(c['acc']['text'].split('void main')[0].count('vec3 geoAt('), 1)

    def test_dof_inputs(self):
        _ns, m, rec, _s = TF.run_build('dof')
        ins = dict((c['name'], c['ins']) for c in rec['compute'])
        self.assertEqual(ins['coc'], ['in1', 'depth_sel', 'af'])
        self.assertEqual(ins['gather'], ['coc', 'hl'])
        self.assertEqual(ins['hl'], ['coc', 'in1'])
        self.assertEqual(ins['fx'], ['in1', 'gather', 'coc'])

    @unittest.skipIf(np is None, 'numpy')
    def test_sprites(self):
        # excess: sharp texels keep everything, blurred ones lose (col - thr) x amount; tile reach 9 x 9
        self.assertEqual(DL.sprite_excess([4.0, 0.5, 1.0], 1.0, 1.0, 0.8, 2.0), [0.0, 0.0, 0.0])
        for x, y in zip(DL.sprite_excess([4.0, 0.5, 1.0], 30.0, 0.5, 0.8, 2.0), [1.6, 0.0, 0.1]):
            self.assertAlmostEqual(x, y)
        for r in (0.5, 3.0, 15.0, 40.0, 112.0):
            T = DL.tile_size(r)
            self.assertLessEqual(r, 3.5 * T)
            self.assertIn(T, (4, 8, 16, 32))
        self.assertEqual(DL.tile_size(15.0), 8)
        # one sprite (energy 1, rad 15 texels, 6 blades) drawn the GLSL way: energy kept, blades show on a 3-texel
        # light (DF3: vertex / edge half-max > 1.05; ideal 1 / cos(30) = 1.155)
        rad, n = 15.0, 64
        yy, xx = np.mgrid[0:n, 0:n] + 0.5
        cov = np.vectorize(lambda x, y: DL.aperture_cov((32.0 - x) / rad, (32.0 - y) / rad, rad))(xx, yy)
        spr = cov / (DL.aperture_area(6) * rad * rad)
        self.assertAlmostEqual(spr.sum(), 1.0, delta=0.02)
        disc = ((xx - 32.0) ** 2 + (yy - 32.0) ** 2 <= 9.0).astype(float)
        img = np.real(np.fft.ifft2(np.fft.fft2(spr) * np.fft.fft2(np.fft.ifftshift(disc))))
        half = img.max() / 2.0

        def hm(ang):
            for k in range(400):
                r = k * 0.1
                x, y = 32.0 + r * math.cos(ang), 32.0 + r * math.sin(ang)
                if img[int(y), int(x)] < half:
                    return r
            return 40.0
        vert = np.mean([hm(k * math.pi / 3) for k in range(6)])
        edge = np.mean([hm(k * math.pi / 3 + math.pi / 6) for k in range(6)])
        self.assertGreater(vert / edge, 1.05)


class Shared(unittest.TestCase):
    def test_limits(self):
        for mod in WAVEC:
            _ns, _m, rec, _s = TF.run_build(mod)
            for c in rec['compute']:
                self.assertLessEqual(len(c['ins']), 3, '%s.%s: T-88 / T-123 <= 3 GLSL TOP inputs' % (mod, c['name']))
                sh = 0
                for typ, n in re.findall(r'shared\s+(float|vec4|vec3|vec2|int|uint)\s+\w+\[(\d+)\]', c['text']):
                    sh += int(n) * {'float': 4, 'int': 4, 'uint': 4, 'vec2': 8, 'vec3': 16, 'vec4': 16}[typ]
                self.assertLessEqual(sh, 32768, '%s.%s: Apple <= 32 KB shared' % (mod, c['name']))
                for loop in re.findall(r'for \(int \w+ = 0; \w+ < (\w+);', c['text']):
                    self.assertTrue(loop.isdigit(), '%s.%s: loop bound must be a constant (T-124)' % (mod, c['name']))

    def test_ascii(self):
        for m in WAVEC:
            for f in ('fx_film_%s.py' % m, 'fx_film_%s_logic.py' % m):
                with open(os.path.join(BUILDERS, f), encoding='ascii') as fh:
                    fh.read()

    def test_doc_numbers(self):
        with open(DOC) as fh:
            doc = fh.read()
        for L in (CL, KL, GL, DL):
            for k, v in L.expected_numbers().items():
                self.assertIn('%s %s' % (k, v), doc, k)


if __name__ == '__main__':
    unittest.main()
