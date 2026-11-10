"""Offline tests for FX_analog module 'ntsc' (builders/fx_analog_ntsc.py, fx_analog_ntsc_logic.py, fx_analog.py).
No TD needed. Run: python3 -I -m unittest discover -s test -p 'test_fx_analog_ntsc.py'
The numpy reference is the composite maths the four compute shaders implement; the GLSL check compiles each pass with
glslc (OpenGL target) against stubs of TD's compute globals: a syntax/type check, NOT a TD compile and NOT a parity
proof (that is LIVE CHECK N2/N3 in docs/builds/fx_analog_ntsc.md)."""
import ast
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
sys.path.insert(0, BUILDERS)
import fx_analog_ntsc_logic as L  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None


def module_ns():
    ns = {'HERE': BUILDERS}
    with open(os.path.join(BUILDERS, 'fx_analog_ntsc.py')) as fh:
        exec(compile(fh.read(), 'fx_analog_ntsc.py', 'exec'), ns)
    return ns


M = module_ns()
SMALL = {'Lines': 64}                      # decoding is per line (combs use 1-2 neighbours): fewer lines = fast tests
W, H = 540, 256


def chroma(rgb, pal=False):
    yuv = L._mat(rgb, L.YUV if pal else L.YIQ)
    return yuv[..., 1], yuv[..., 2]


class Derive(unittest.TestCase):
    def test_ntsc_defaults_are_4fsc(self):
        d = L.derive({})
        self.assertAlmostEqual(d['cps'], 0.25, places=9)          # 754 active samples = 4 x fsc
        self.assertAlmostEqual(d['fs'], 4 * 3.579545, places=6)
        self.assertEqual((d['lineadv'], d['combd'], d['pal']), (0.5, 1, 0))
        self.assertEqual(d['sep'], 2)                              # comb1

    def test_pal_at_922_is_4fsc(self):
        d = L.derive({'Standard': 'pald', 'Samples': 922})
        self.assertAlmostEqual(d['cps'], 0.25, places=9)
        self.assertEqual((d['lineadv'], d['combd'], d['pal'], d['pald']), (0.75, 2, 1, 1))
        self.assertEqual(L.derive({'Standard': 2})['pald'], 0)      # menu index works too

    def test_bandwidths_to_cycles_per_sample(self):
        d = L.derive({'Ibw': 1.3, 'Qbw': 0.5, 'Ybw': 4.2})
        self.assertAlmostEqual(d['fcI'], 1.3 / d['fs'], places=9)
        self.assertAlmostEqual(d['fcYw'], d['fcY'] / 2, places=9)
        self.assertEqual(d['rQ'], L.RMAX)                           # 0.5 MHz needs more than 24 taps: capped
        self.assertEqual(d['R'], max(d['rY'], d['rYw'], d['rI'], d['rQ']))
        self.assertLessEqual(d['R'], 24)                           # the decode shader loops -24..24

    def test_fewer_samples_raise_cps(self):
        self.assertAlmostEqual(L.derive({'Samples': 377})['cps'], 0.5, places=6)

    def test_frame_phase_repeats(self):
        d = L.derive({})
        self.assertEqual([L.frame_phase_of(d, f) for f in range(4)], [0.0, 0.5, 0.0, 0.5])   # NTSC: 2-frame repeat
        p = L.derive({'Standard': 'pald'})
        self.assertEqual([L.frame_phase_of(p, f) for f in range(5)], [0.0, 0.75, 0.5, 0.25, 0.0])  # PAL: 4 frames
        self.assertEqual(L.frame_phase_of(L.derive({'Crawl': 0}), 7), 0.0)

    def test_uniforms_cover_every_pass(self):
        u = L.uniforms(L.derive({}))
        for name, us in M['PASS_UNIFORMS'].items():
            for un in us:
                self.assertEqual(len(u[un]), 4)
                self.assertIn('uniform vec4 %s;' % un, M['SHADERS'][name])

    def test_matrices_are_inverses(self):
        for F, I in ((L.YIQ, L.YIQ_INV), (L.YUV, L.YUV_INV)):
            for i in range(3):
                for j in range(3):
                    v = sum(I[i][k] * F[k][j] for k in range(3))
                    self.assertAlmostEqual(v, 1.0 if i == j else 0.0, delta=2e-4)

    def test_kernel(self):
        self.assertEqual(L.kern(10, 0.1, 9, 0.0), 0.0)
        self.assertAlmostEqual(L.kern(0, 0.1, 9, 0.0), 1.0)
        for ring in (0.0, 0.5, 1.0):
            ws = [L.kern(j, 0.1, 12, ring) for j in range(-12, 13)]
            self.assertEqual(ws, ws[::-1])

        def resp(f, fc, R, ring):
            w = [L.kern(j, fc, R, ring) for j in range(-R, R + 1)]
            return sum(v * math.cos(2 * math.pi * f * j) for v, j in zip(w, range(-R, R + 1))) / sum(w)
        fc = 0.0908                                                 # I at 1.3 MHz
        R = L.radius(fc)
        self.assertAlmostEqual(resp(fc, fc, R, 0.0), 0.5, delta=0.01)   # Gaussian: -6 dB at fc
        self.assertLess(abs(resp(0.25, fc, R, 0.0)), 0.01)          # subcarrier gone from I
        self.assertLess(abs(resp(0.25, fc, R, 0.5)), 0.01)

    def test_raw_and_cache(self):
        class P:
            def __init__(self, v): self.v = v
            def eval(self): return self.v

        class Pars:
            pass

        class Comp:
            par = Pars()
        for n, v in L.DEFAULTS.items():
            setattr(Comp.par, n, P(v))
        u1 = L.UNI(Comp)
        self.assertIs(L.UNI(Comp), u1)                              # cached while pars are unchanged
        Comp.par.Samples = P(377)
        self.assertAlmostEqual(L.UNI(Comp)['uS'][2], 0.5, places=6)
        self.assertEqual(L.frame_phase(Comp, 3), 0.5)


@unittest.skipIf(np is None, 'numpy missing')
class Reference(unittest.TestCase):
    """Properties of the composite chain the shaders implement (expected numbers for the live lane come from here)."""

    def run_ref(self, img, **p):
        q = dict(SMALL)
        q.update(p)
        return L.reference(img, q)

    def run_grid(self, grid, **p):
        """encode -> separate -> decode on a signal-res grid (no resample: exact test signals)."""
        q = dict(SMALL)
        q.update(p)
        d = L.derive(q)
        return L.decode(L.separate(L.encode(grid, d), d), d), d

    def test_grey_is_untouched_in_every_mode(self):
        img = np.full((H, W, 4), 0.5)
        for sep in L.SEPS:
            for std in L.STANDARDS:
                R = self.run_ref(img, Separation=sep, Standard=std)
                e = np.abs(R['dec'] - 0.5)
                if sep == 'none':                                   # luma demodulated as chroma: the I/Q FIR
                    self.assertLess(e[:, 30:-30].max(), 1e-2, std)  # stopband leaves ~0.6 % colour dots
                else:
                    self.assertLess(e.max(), 2e-5, (sep, std))     # YUV rows sum to 5e-6, not 0

    def test_resample_box(self):
        img = np.zeros((8, 8, 3))
        img[:, 4:] = 1.0
        g = L.resample(img, 4, 2)
        self.assertEqual(g.shape, (2, 4, 3))
        self.assertEqual(list(g[0, :, 0]), [0.0, 0.0, 1.0, 1.0])
        g = L.resample(img, 1, 1)                                   # 4 of 8 columns picked: 0 2 4 6 -> mean 0.5
        self.assertAlmostEqual(g[0, 0, 0], 0.5)

    def test_bars_survive_comb_notch_svideo(self):
        bars = L.colour_bars(W, H)
        for sep in ('notch', 'comb1', 'comb2', 'svideo'):
            R = self.run_ref(bars, Separation=sep)
            ws = R['d']['ws']
            for b in range(7):
                k = int((b + 0.5) * ws / 7)
                e = np.abs(R['dec'][20:40, k - 10:k + 10] - R['grid'][20:40, k - 10:k + 10]).max()
                self.assertLess(e, 1e-3, (sep, b))

    def test_none_puts_dots_in_luma(self):
        R = self.run_ref(L.colour_bars(W, H), Separation='none')
        y = L._mat(R['dec'], L.YIQ)[..., 0]
        yg = L._mat(R['grid'], L.YIQ)[..., 0]
        k = int(5.5 * R['d']['ws'] / 7)                             # red bar: |C| ~ 0.33
        self.assertGreater(np.abs(y[30, k - 20:k + 20] - yg[30, k - 20:k + 20]).max(), 0.2)

    def test_dot_crawl_flips_each_frame_and_repeats_every_two(self):
        bars = L.colour_bars(W, H)
        d = L.derive(dict(SMALL, Separation='none'))
        g = L.resample(bars, d['ws'], d['lines'])
        dots = []
        for f in range(3):
            fph = L.frame_phase_of(d, f)
            y = L._mat(L.decode(L.separate(L.encode(g, d, fph, f), d), d, fph), L.YIQ)[..., 0]
            dots.append(y - L._mat(g, L.YIQ)[..., 0])
        k = int(5.5 * d['ws'] / 7)
        a, b, c = (x[30, k - 20:k + 20] for x in dots)
        self.assertLess(np.abs(a + b).max(), 1e-6)                  # frame 1 = frame 0 inverted (dot crawl)
        self.assertLess(np.abs(a - c).max(), 1e-6)                  # frame 2 = frame 0 (2-frame repeat)
        self.assertLess(np.abs(dots[0][30, k - 20:k + 20] + dots[0][31, k - 20:k + 20]).max(), 1e-6)  # line flip

    def test_cross_colour_on_fsc_stripes(self):
        d = L.derive(SMALL)
        st = L.luma_stripes(d['ws'], d['lines'], d['ws'], d['cps'])[..., :3]   # stripes on the signal grid
        fc = {}
        for sep in L.SEPS:
            dec, _d = self.run_grid(st, Separation=sep)
            i, q = chroma(dec)
            fc[sep] = float(np.abs(np.stack([i, q])[:, 10:54, 50:700]).mean())
        self.assertGreater(fc['none'], 0.1)                         # luma detail at fsc decoded as colour
        self.assertGreater(fc['notch'], 0.1)
        for sep in ('comb1', 'comb2', 'svideo'):                   # vertically constant: the comb cancels it
            self.assertLess(fc[sep], 1e-6, sep)

    def test_notch_removes_fsc_luma_detail(self):
        d = L.derive(SMALL)
        st = L.luma_stripes(d['ws'], d['lines'], d['ws'], d['cps'])[..., :3]
        y = L._mat(self.run_grid(st, Separation='notch')[0], L.YIQ)[..., 0]
        self.assertLess(float(y[30, 100:600].std()), 0.01)          # stripes (amp 0.3) gone from luma
        y = L._mat(self.run_grid(st, Separation='comb1')[0], L.YIQ)[..., 0]
        self.assertGreater(float(y[30, 100:600].std()), 0.1)        # comb keeps them

    def test_phase_error_ntsc_hue_pal_d_desaturates_pal_s_hanover(self):
        bars = L.colour_bars(W, H)
        k = None
        out = {}
        for std, ws in (('ntsc', 754), ('pald', 922), ('pals', 922)):
            R = self.run_ref(bars, Standard=std, Samples=ws, Qbw=1.3, Phaseerr=20.0)
            pal = std != 'ntsc'
            k = int(5.5 * ws / 7)
            a1, b1 = chroma(R['dec'], pal)
            a0, b0 = chroma(R['grid'], pal)
            rows = []
            for r in (30, 31):
                ang = math.degrees(math.atan2(b1[r, k], a1[r, k]) - math.atan2(b0[r, k], a0[r, k]))
                rows.append((round(ang, 2), round(math.hypot(a1[r, k], b1[r, k]) / math.hypot(a0[r, k], b0[r, k]), 4)))
            out[std] = rows
        self.assertEqual(out['ntsc'], [(20.0, 1.0), (20.0, 1.0)])     # NTSC: tint error on every line
        self.assertEqual(out['pald'], [(0.0, 0.9397), (0.0, 0.9397)])  # PAL-D: cancels to cos(20) desaturation
        self.assertEqual(sorted(a for a, _s in out['pals']), [-20.0, 20.0])  # PAL-S: +-20 alternating (Hanover)

    def step_overshoot(self, **p):
        img = np.zeros((H, W, 4))
        img[:, W // 2:, :3] = 0.8
        y = L._mat(self.run_ref(img, Separation='svideo', **p)['dec'], L.YIQ)[..., 0][30]
        return float(y.max() - 0.8), float(-y.min())

    def test_peaking_and_ringing_overshoot(self):
        self.assertLess(max(self.step_overshoot()), 1e-6)           # Ringing 0: Blackman kernel, no overshoot
        self.assertGreater(self.step_overshoot(Peaking=1.0)[0], 0.08)
        self.assertGreater(self.step_overshoot(Ringing=0.5)[0], 0.02)   # windowed sinc
        self.assertGreater(self.step_overshoot(Ringing=1.0)[0], self.step_overshoot(Ringing=0.5)[0])  # bare sinc

    def test_q_bandwidth_softer_than_i(self):
        d = L.derive(SMALL)
        img = np.zeros((H, W, 4))
        img[..., :3] = 0.5
        img[:, W // 2:, :3] = [0.5 + 0.2, 0.5 - 0.1, 0.5 - 0.15]
        R = self.run_ref(img, Separation='svideo')
        i, q = chroma(R['dec'])
        i0, q0 = chroma(R['grid'])

        def width(v, v0):
            lo, hi = v0[30].min(), v0[30].max()
            t = (v[30] - lo) / (hi - lo) if hi != lo else v[30] * 0
            if t[-1] < t[0]:
                t = 1 - t
            return int(((t > 0.1) & (t < 0.9)).sum())
        self.assertGreater(width(q, q0), width(i, i0))              # Q 0.5 MHz vs I 1.3 MHz
        self.assertIsNotNone(d)

    def test_noise_deterministic_and_seeded(self):
        img = np.full((H, W, 4), 0.5)
        a = self.run_ref(img, Noise=0.05)['enc']
        b = self.run_ref(img, Noise=0.05)['enc']
        c = self.run_ref(img, Noise=0.05, Seed=2)['enc']
        self.assertEqual(np.abs(a - b).max(), 0.0)
        self.assertGreater(np.abs(a - c).max(), 0.01)
        self.assertLess(np.abs(a[..., 0] - 0.5).max(), 0.05 + 1e-9)  # triangular noise in +-Noise
        self.assertGreater(float(np.abs(a[..., 0] - 0.5).std()), 0.005)

    def test_pcg_known_values(self):                              # the GLSL pcg on uint32 (wraps)
        self.assertEqual(int(L.pcg(0)), 129708002)
        self.assertEqual(int(L.pcg(1)), 2831084092)

    def test_amount_and_lineblend(self):
        img = L.colour_bars(W, H)
        R0 = self.run_ref(img, Amount=0.0)
        self.assertEqual(np.abs(R0['out'] - img).max(), 0.0)
        R = self.run_ref(img, Separation='none', Lineblend=0.0)
        per = H // SMALL['Lines']                                   # 4 px per line: hard line steps
        o = R['out'][..., 0]
        self.assertEqual(np.abs(o[0:per] - o[0]).max(), 0.0)


@unittest.skipIf(np is None, 'numpy missing')
class ParityHelper(unittest.TestCase):
    def test_parity_on_a_fake_instance_is_zero(self):
        img = L.colour_bars(64, 48)
        pars = dict(L.DEFAULTS, Lines=12, Samples=96, Crawl=0.0)
        R = L.reference(img, pars, frame=5)

        class V:
            def __init__(self, v): self.v = v
            def eval(self): return self.v

        class Op:
            def __init__(self, arr): self.arr = arr
            def numpyArray(self, delayed=False): return self.arr.astype(np.float32)

        class Comp:
            class par:
                pass
            def __init__(self): self.ops = {}
            def op(self, n): return self.ops[n]
        m = Comp()
        for n, v in pars.items():
            setattr(Comp.par, n, V(v))
        m.ops = {'in1': Op(img), 'enc': Op(R['enc']), 'sep': Op(R['sep']), 'dec': Op(R['dec']), 'up': Op(R['out'])}
        enc = m.ops['enc']
        enc.seq = type('S', (), {'vec': type('B', (), {'numBlocks': 3})})
        enc.par = type('P', (), {})()
        for i, (un, ex) in enumerate(M['uniform_exprs']('enc')):
            setattr(enc.par, 'vec%dname' % i, V(un))
            for c in 'xyzw':
                setattr(enc.par, 'vec%dvalue%s' % (i, c), V(0.0 if un != 'uF' or c != 'y' else 5))
        got = L.parity(m)
        for name, _ch in L.PASS_CH:
            self.assertLess(got[name], 1e-6, name)
        self.assertEqual((got['fph'], got['frame']), (0.0, 5))


class Shaders(unittest.TestCase):
    def test_ascii(self):
        for name in ('fx_analog_ntsc.py', 'fx_analog_ntsc_logic.py', 'fx_analog.py'):
            with open(os.path.join(BUILDERS, name), 'rb') as fh:
                fh.read().decode('ascii')

    def test_compute_only(self):
        for name, s in M['SHADERS'].items():
            self.assertIn('layout (local_size_x = 8, local_size_y = 8) in;', s)
            self.assertIn('TDImageStoreOutput(0,', s)
            self.assertNotIn('fragColor', s)
            self.assertNotIn('#version', s)                          # TD adds it

    def test_decode_loop_bound_matches_rmax(self):
        self.assertIn('for (int j = -%d; j <= %d; j++)' % (L.RMAX, L.RMAX), M['DEC'])

    def test_constants_match_logic(self):
        for row in L.YIQ[1:] + L.YUV[1:]:
            self.assertIn('vec3(%s, %s, %s)' % tuple(repr(v) for v in row), M['ENC'])
        for v in (0.956296, 0.621024, 0.272122, 0.647381, 1.106989, 1.704615, 1.139835, 0.394646, 0.580594, 2.032112):
            self.assertIn(repr(v), M['DEC'])


TD_STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[2];
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
"""


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass_compiles(self):
        for name, s in M['SHADERS'].items():
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, name + '.comp')
                with open(p, 'w') as fh:
                    fh.write(TD_STUB_COMPUTE + s)
                r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                    '-o', os.devnull, p], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, '%s\n%s' % (name, r.stderr[:3000]))


class Builder(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(BUILDERS, 'fx_analog_ntsc.py')) as fh:
            self.src = fh.read()

    def test_template_names(self):
        self.assertEqual(M['MODULE'], 'ntsc')
        names = [p[0] for _pg, ps in M['PAGES'] for p in ps]
        self.assertEqual(names[0], 'Amount')
        self.assertIn('Seed', names)
        self.assertEqual(sorted(names), sorted(L.PARS))             # logic reads exactly the module's pars
        self.assertEqual(M['PANEL_PAGES'], [pg for pg, _ in M['PAGES']])
        for _pg, ps in M['PAGES']:
            for n, style, default, o in ps:
                self.assertEqual(L.DEFAULTS[n], default, n)
                if style == 'Menu':
                    self.assertIn(default, o['names'])
                    self.assertEqual(len(o['names']), len(o['labels']))
        menus = {n: o['names'] for _pg, ps in M['PAGES'] for n, st, _d, o in ps if st == 'Menu'}
        self.assertEqual(menus['Standard'], L.STANDARDS)
        self.assertEqual(menus['Separation'], L.SEPS)

    def test_presets(self):
        names = set(L.PARS)
        menus = {n: len(o['names']) for _pg, ps in M['PAGES'] for n, st, _d, o in ps if st == 'Menu'}
        self.assertTrue(3 <= len(M['PRESETS']) <= 5)
        self.assertEqual([s for s, _n, _v in M['PRESETS']], list(range(1, len(M['PRESETS']) + 1)))
        for _s, _n, vals in M['PRESETS']:
            self.assertLessEqual(set(vals), names)
            for k, n in menus.items():
                self.assertTrue(0 <= vals[k] < n)
            self.assertLessEqual(L.derive(vals)['R'], L.RMAX)

    def test_uniform_exprs(self):
        ex = dict(M['uniform_exprs']('dec'))
        self.assertEqual(list(ex), ['uS', 'uF', 'uK', 'uR', 'uP', 'uQ'])
        self.assertEqual(ex['uF'][0], M['FPH_EXPR'])
        self.assertEqual(ex['uK'][2], "op('ntsc_logic').module.UNI(parent())['uK'][2]")
        for name in M['SHADERS']:
            for _u, e4 in M['uniform_exprs'](name):
                for e in e4:
                    ast.parse(e, mode='eval')

    def test_build_api_and_safety(self):
        tree = ast.parse(self.src)
        fns = set(n.name for n in tree.body if isinstance(n, ast.FunctionDef))
        self.assertIn('build', fns)
        self.assertNotIn('.destroy()', self.src)
        for k in ("'wet'", "'out1'", "'in1'", "'ntsc_logic'"):
            self.assertIn(k, self.src)


class Rack(unittest.TestCase):
    def test_rack_reuses_fx_glitch(self):
        ns = {}
        with open(os.path.join(BUILDERS, 'fx_analog.py')) as fh:
            exec(compile(fh.read(), 'fx_analog.py', 'exec'), ns)
        self.assertEqual(ns['NAME'], 'FX_analog')
        self.assertTrue(ns['module_file']('ntsc').endswith('builders/fx_analog_ntsc.py'))
        m = ns['_module']('ntsc')
        self.assertEqual(m['MODULE'], 'ntsc')
        self.assertEqual(ns['plan_chain']([{'name': 'b', 'order': 2}, {'name': 'a', 'order': 1}]), ['a', 'b'])
        self.assertEqual(ns['next_name']('ntsc', {'ntsc1'}), 'ntsc2')
        self.assertIs(ns['build'].__globals__, ns)                  # rack functions see the overridden NAME/_module
        self.assertIs(ns['rewire'].__globals__, ns)


if __name__ == '__main__':
    unittest.main()
