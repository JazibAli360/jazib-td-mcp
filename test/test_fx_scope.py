"""Offline tests for FX_scope (builders/fx_scope*.py, builders/glsl/fx_scope_*.glsl): module specs, presets, every
par expression evaluated against a fake TD, numpy references (beam energy / dwell / circle numbers, phosphor, path
figures, scope counts, HUD maths, font), glslc compile of every shader in every build switch, dry builds on a fake
TD. Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_scope*.py'
glslc = an OpenGL-target syntax/type check against stubs of TD's compute built-ins, NOT a TD compile (LIVE CHECK R1
in docs/builds/fx_scope.md)."""
import math
import os
import shutil
import subprocess
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
L = {}
with open(os.path.join(B, 'fx_scope_logic.py')) as fh:
    exec(fh.read(), L)
MODS = ['xy', 'vector', 'lissajous', 'scopes', 'hud']

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None


def _mod(name, **extra):
    ns = {'HERE': B}
    ns.update(extra)
    with open(os.path.join(B, 'fx_scope_%s.py' % name)) as fh:
        exec(fh.read(), ns)
    return ns


M = dict((n, _mod(n)) for n in MODS)


def pars(Mx):
    return dict((n, (s, d, o)) for _pg, ps in Mx['PAGES'] for n, s, d, o in ps)


# ------------------------------------------------------------------ fake TD for expressions
class _FP:
    def __init__(self, v, menu=None):
        self.v, self.menuIndex = v, menu

    def eval(self):
        return self.v


class _FakeOp:
    def __init__(self, name='x', w=1080, h=1920, res=(486, 486), arr=None):
        self.name, self.width, self.height, self.path = name, w, h, '/fake/' + name
        self.par = types.SimpleNamespace(resolutionw=_FP(res[0]), resolutionh=_FP(res[1]))
        self.inputs = [self]
        self._arr = arr
        self.numChans = 0 if arr is None else len(arr)

    def numpyArray(self):
        return self._arr


def env_for(Mx, over=None, audio=None):
    vals = {}
    for n, (s, d, o) in pars(Mx).items():
        if s == 'Menu':
            vals[n] = _FP(d, o['names'].index(d))
        elif s == 'Pulse':
            continue
        elif s == 'CHOP':
            vals[n] = _FP(None)
        else:
            vals[n] = _FP(d)
    for k, v in (over or {}).items():
        if pars(Mx)[k][0] == 'Menu':
            vals[k] = _FP(v, pars(Mx)[k][2]['names'].index(v))
        else:
            vals[k] = _FP(v)
    vals.setdefault('Tcstart', _FP(0.0))
    parent = types.SimpleNamespace(par=types.SimpleNamespace(**vals))
    ops = {'in1': _FakeOp('in1'), 'beam': _FakeOp('beam'), 'src_xy': _FakeOp('src_xy', arr=audio)}
    return {'parent': lambda: parent, 'op': lambda n: ops.get(n, _FakeOp(n)), 'me': _FakeOp('me'),
            'absTime': types.SimpleNamespace(seconds=12.345, frame=740.0),
            'project': types.SimpleNamespace(cookRate=60.0), 'math': math}


def all_uniforms(name):
    Mx = M[name]
    if name in ('xy', 'vector', 'lissajous'):
        U = Mx['BE']['path_uniforms']() + Mx['src_uniforms']() + Mx['BE']['beam_uniforms']()
        U += Mx['BE']['look_uniforms'](Mx['look_over']() if 'look_over' in Mx else None)
        return U
    if name == 'hud':
        return Mx['uniforms']()
    return []


class Specs(unittest.TestCase):
    def test_files_ascii(self):
        files = ['fx_scope.py', 'fx_scope_beam.py', 'fx_scope_logic.py'] + ['fx_scope_%s.py' % n for n in MODS]
        files += [os.path.join('glsl', f) for f in os.listdir(os.path.join(B, 'glsl')) if f.startswith('fx_scope_')]
        self.assertGreaterEqual(len(files), 20)
        for f in files:
            with open(os.path.join(B, f), 'rb') as fh:
                fh.read().decode('ascii')

    def test_module_api(self):
        for name, Mx in M.items():
            self.assertEqual(Mx['MODULE'], name)
            for k in ('PAGES', 'PANEL_PAGES', 'PRESETS', 'build', 'shader_texts'):
                self.assertIn(k, Mx)
            names = [n for _pg, ps in Mx['PAGES'] for n, *_ in ps]
            self.assertEqual(names[0], 'Amount')
            self.assertEqual(len(names), len(set(names)), name)
            for n in names:
                self.assertRegex(n, r'^[A-Z][a-z0-9]*$')
            for pg in Mx['PANEL_PAGES']:
                self.assertIn(pg, [p for p, _ in Mx['PAGES']])
            for _pg, ps in Mx['PAGES']:
                for n, s, d, o in ps:
                    self.assertIn(s, ('Float', 'Int', 'Menu', 'Toggle', 'Str', 'Pulse', 'CHOP', 'TOP'), n)
                    if s == 'Menu':
                        self.assertIn(d, o['names'], n)
                        self.assertEqual(len(o['names']), len(o['labels']), n)
                    if s in ('Float', 'Int'):
                        self.assertLessEqual(o['min'], o['max'], n)

    def test_presets(self):
        for name, Mx in M.items():
            P = pars(Mx)
            slots = [s for s, _n, _v in Mx['PRESETS']]
            self.assertEqual(len(slots), len(set(slots)))
            self.assertTrue(3 <= len(slots) <= 8)
            for _s, _n, vals in Mx['PRESETS']:
                for k, v in vals.items():
                    self.assertIn(k, P, (name, k))
                    self.assertNotEqual(P[k][0], 'Pulse')
                    if P[k][0] == 'Menu':
                        self.assertTrue(isinstance(v, int) and 0 <= v < len(P[k][2]['names']), (name, k, v))

    def test_rack_file(self):
        ns = {}
        src = open(os.path.join(B, 'fx_scope.py')).read()
        self.assertIn("NAME = 'FX_scope'", src)
        self.assertIn("exec(_fh.read(), globals())", src)          # the FX_glitch rack, no copy
        self.assertNotIn('def rewire', src)
        compile(src, 'fx_scope.py', 'exec')
        del ns


class Expressions(unittest.TestCase):
    def test_every_uniform_evaluates_finite(self):
        for name in ('xy', 'vector', 'lissajous', 'hud'):
            env = env_for(M[name])
            for un, ex in all_uniforms(name):
                self.assertRegex(un, r'^u[A-Za-z0-9]+$')
                self.assertEqual(len(ex), 4, un)
                for e in ex:
                    v = eval(e, env)
                    self.assertTrue(math.isfinite(float(v)), (name, un, e, v))

    def test_scopes_expressions(self):
        S = M['scopes']
        for mode in L['SCOPES']:
            env = env_for(S, {'Scope': mode})
            g = L['hist_geom'](mode, 1080, 1920, 4, 256, 256)
            for k in L['GEOM_KEYS']:
                self.assertEqual(eval(S['geom_expr'](k), env), g[k], (mode, k))
            for k in range(4):
                self.assertTrue(math.isfinite(eval(S['panel_expr'](k), env)))

    def test_panel_and_beam_size(self):
        self.assertEqual(L['panel'](1080, 1920, 0.9, 0, 0.5, 0.5), (540 - 486.0, 960 - 486.0, 972.0, 972.0))
        self.assertEqual(L['beam_wh'](972.0, 972.0, 0.5), (486, 486))
        self.assertEqual(L['beam_wh'](10.0, 10.0, 0.25), (32, 32))
        x0, y0, pw, ph = L['panel'](1080, 1920, 1.0, 1, 0.5, 0.5)
        self.assertEqual((x0, y0, pw, ph), (0.0, 0.0, 1080.0, 1920.0))
        BE = M['xy']['BE']
        env = env_for(M['xy'])
        self.assertEqual([eval(BE['beam_wh_expr'](k), env) for k in (0, 1)], [486, 486])
        env = env_for(M['xy'], {'Aspect': 'fill', 'Quality': 'full', 'Size': 1.0})
        self.assertEqual([eval(BE['beam_wh_expr'](k), env) for k in (0, 1)], [1080, 1920])

    def test_phosphor_lists(self):
        BE = M['xy']['BE']
        for key in L['PHOSPHOR_NAMES']:
            env = env_for(M['xy'], {'Phosphor': key})
            A, F, mul, mono = L['phosphor_tints'](key, (0.3, 0.8, 1.0))
            for i in range(3):
                self.assertAlmostEqual(eval(BE['ph_list'](i, 'A'), env), A[i])
                self.assertAlmostEqual(eval(BE['ph_list'](i, 'F'), env), F[i])
                self.assertAlmostEqual(eval(BE['ph_list'](i, 'M'), env), mul[i])
            self.assertEqual(eval(BE['ph_list'](0, 'mono'), env), float(mono))

    def test_spiro_rose_window_lambdas(self):
        LJ = M['lissajous']
        for R, r, t in ((5, 3, 1), (7, 4, 1), (8, 2, 2), (5.5, 3, 1), (96, 36, 1)):
            self.assertAlmostEqual(eval(LJ['SPIRO_LAMBDA'], {'math': math})(R, r, t), L['spiro_period'](R, r, t))
        for n, d in ((5, 4), (3, 1), (2, 1), (7, 3), (4, 2)):
            self.assertAlmostEqual(eval(LJ['ROSE_LAMBDA'], {'math': math})(n, d, 1.0), L['rose_period'](n, d))
        w = eval(LJ['WINDOW_LAMBDA'])
        self.assertEqual(w(False, 4.0, 2.0, 60.0, 100.0), (0.0, 60.0))
        s, ln = w(True, 4.0, 2.0, 60.0, 100.0)                     # tau = 400 % 60 = 40
        self.assertAlmostEqual(s, 38.0)
        self.assertAlmostEqual(ln, 2.0)
        self.assertEqual(w(True, 4.0, 2.0, 60.0, 15.1)[0], 0.0)       # tau 0.4 < span: from 0

    def test_correlation_expr(self):
        LJ = M['lissajous']
        a = np.array([[0.1, 0.5, -0.3], [0.1, 0.5, -0.3]]) if np else None
        if np is None:
            self.skipTest('numpy')
        env = env_for(LJ, {'Figure': 'goniometer'}, audio=a)
        self.assertAlmostEqual(eval(LJ['look_over']()['uO'][3], env), 1.0)
        env = env_for(LJ, {'Figure': 'goniometer'}, audio=np.array([a[0], -a[0]]))
        self.assertAlmostEqual(eval(LJ['look_over']()['uO'][3], env), -1.0)
        self.assertEqual(eval(LJ['look_over']()['uO'][2], env_for(LJ)), 0)   # meter only on the goniometer

    def test_timecode_and_label(self):
        self.assertEqual(L['timecode'](3723.75, 25), (1, 2, 3, 18))
        env = env_for(M['hud'], {'Tcoffset': 3600.0})
        h, mi, s, f = (eval(L['TC_EXPR'] + '[%d]' % k, env) for k in range(4))
        self.assertEqual((h, mi, s, f), L['timecode'](12.345 + 3600.0, 25))
        env = env_for(M['hud'], {'Label': 'ISO 8é'})
        codes = [eval(L['label_expr'](k), env) for k in range(7)]
        self.assertEqual(codes, [73, 83, 79, 32, 56, 63, 32])

    def test_test_tone_uniforms_match_logic(self):
        env = env_for(M['xy'])
        U = dict(M['xy']['src_uniforms']())
        got = [eval(e, env) for e in U['uS0'] + U['uS1']]
        fx, fy, phx, phy, n = L['test_tone_uniforms'](110.0, 1.5, 90.0, 0.8, 48000.0, 740.0, 60.0)
        self.assertEqual(got[0], 0)
        for a, b in zip(got[1:7], [fx, fy, 0.8, phx, phy, n]):
            self.assertAlmostEqual(a, b, places=12)


@unittest.skipIf(np is None, 'numpy')
class Beam(unittest.TestCase):
    def test_erf(self):
        for x in np.linspace(-4, 4, 161):
            self.assertLess(abs(L['erf_as'](float(x)) - math.erf(float(x))), 1.6e-7)
        a = np.linspace(-3, 3, 7)
        self.assertTrue(np.allclose(L['erf_as'](a), [math.erf(v) for v in a], atol=1.6e-7))

    def _line(self, n, length, bw=200, bh=200, y=100.5):
        P = np.stack([np.linspace(100 - length / 2, 100 + length / 2, n), np.full(n, y)], 1)
        return P, np.ones(n), np.ones((n, 3))

    def test_energy_is_kn_and_peak_is_one(self):
        bw = bh = 200
        sigma, kn, lref, _sx, _sy = L['beam_consts'](bw, bh, 1.5, 1.0)
        P, w, c = self._line(201, 150.0)
        for dwell in (1.0, 0.0, 0.5):
            E = L['splat_ref'](P, w, c, bw, bh, sigma, kn, dwell, lref)[..., 0]
            expect = kn * (dwell + (1 - dwell) * 150.0 / lref)
            self.assertAlmostEqual(E.sum() / expect, 1.0, places=4)
        P, w, c = self._line(101, lref)                      # a line one Lref long, once per frame
        E = L['splat_ref'](P, w, c, bw, bh, sigma, kn, 1.0, lref)[..., 0]
        self.assertAlmostEqual(E[100, 100], 1.0, places=4)   # px centre (100.5, 100.5) on the line

    def test_dwell_makes_slow_beam_bright(self):
        bw = bh = 160
        sigma, kn, lref, _a, _b = L['beam_consts'](bw, bh, 1.0, 1.0)
        P = np.array([[20.0, 80.5]] * 50 + [[140.0, 80.5]] * 50)   # 49 zero-length dwell segments at each end
        E = L['splat_ref'](P, np.ones(100), np.ones((100, 3)), bw, bh, sigma, kn, 1.0, lref)[..., 0]
        self.assertGreater(E[80, 19], 20 * E[80, 79])               # end blobs vs mid line
        self.assertAlmostEqual(E.sum() / kn, 1.0, places=3)

    def test_point_limit_is_continuous(self):
        bw = bh = 64
        sigma, kn, lref, _a, _b = L['beam_consts'](bw, bh, 1.5, 1.0)
        out = []
        for d in (0.0199, 0.0201):
            P = np.array([[32.0, 32.0], [32.0 + d, 32.0]])
            out.append(L['splat_ref'](P, np.ones(2), np.ones((2, 3)), bw, bh, sigma, kn, 1.0, lref)[..., 0])
        self.assertLess(np.abs(out[0] - out[1]).max() / out[0].max(), 1e-4)

    def test_circle_expected_numbers(self):
        """docs/builds/fx_scope.md B2: test tones ratio 1, phase 90, amp 0.8 -> circle radius 0.8 Lref/2, 1.831
        turns per frame at 110 Hz / 60 fps: one pass peaks at Lref / traced length = 0.2172; 83 % of the ring is
        traced twice (0.434), the rest once."""
        bw = bh = 486
        sigma, kn, lref, sx, sy = L['beam_consts'](bw, bh, 1.5, 0.5)
        fx, fy, phx, phy, n = L['test_tone_uniforms'](110.0, 1.0, 90.0, 0.8, 48000.0, 0.0, 60.0)
        S = L['test_tone'](n, fx, fy, phx, phy, 0.8)
        U = L['audio_points'](S, 4)
        self.assertEqual(len(U), 3197)
        Pp = L['place'](U, bw, bh, sx, sy)
        r = np.hypot(Pp[:, 0] - 243, Pp[:, 1] - 243)
        self.assertLess(np.abs(r - 194.4).max(), 0.01)
        E = L['splat_ref'](Pp, np.ones(len(Pp)), np.ones((len(Pp), 3)), bw, bh, sigma, kn, 1.0, lref)[..., 0]
        self.assertAlmostEqual(E.sum() / kn, 1.0, places=3)
        arc = 799 / 48000.0 * 110.0 * 2 * math.pi * 194.4             # traced length per frame
        self.assertAlmostEqual(lref / arc, 0.2171, places=3)
        yy, xx = np.mgrid[0:bh, 0:bw] + 0.5 - 243.0
        ang = np.degrees(np.arctan2(yy, xx)) % 360
        rr = np.hypot(xx, yy)
        ring = E * (np.abs(rr - 194.4) < 3)
        peaks = np.array([ring[(ang >= a) & (ang < a + 5)].max() for a in range(0, 360, 5)])
        once = lref / arc
        self.assertAlmostEqual(peaks.min() / once, 1.0, delta=0.08)
        self.assertAlmostEqual(peaks.max() / (2 * once), 1.0, delta=0.08)

    def test_capsule_inside_grown_bbox(self):
        rs = np.random.RandomState(5)
        for _ in range(400):
            a, b = rs.rand(2) * 50, rs.rand(2) * 50
            p = rs.rand(2) * 70 - 10
            R = 5.0 * 1.3
            if L['capsule_in_bbox'](a, b, R, p):
                lo, hi = np.minimum(a, b) - R, np.maximum(a, b) + R
                self.assertTrue((p >= lo).all() and (p <= hi).all())

    def test_mono_and_blank(self):
        bw = bh = 64
        sigma, kn, lref, _a, _b = L['beam_consts'](bw, bh, 1.0, 1.0)
        P = np.array([[10.0, 32.0], [30.0, 32.0], [54.0, 32.0]])
        E = L['splat_ref'](P, np.array([1.0, 0.0, 0.0]), np.array([[1, 0, 0], [1, 0, 0], [1, 0, 0.0]]), bw, bh,
                           sigma, kn, 1.0, lref, mono=False)
        self.assertEqual(E[..., 1].max(), 0.0)
        self.assertEqual(E[31, 45, 0], 0.0)                       # blanked segment 1 -> 2 draws nothing
        Em = L['splat_ref'](P, np.array([1.0, 0.0, 0.0]), np.array([[1, 0, 0]] * 3, float), bw, bh, sigma, kn, 1.0,
                            lref, mono=True)
        self.assertAlmostEqual(Em[31, 20, 1] / E[31, 20, 0], 0.2126, places=6)

    def test_phosphor_step(self):
        E = np.ones((2, 2, 3))
        S, a = L['phosphor_step'](None, E, (0.2, 1.0, 0.25), (0.1, 0.1, 0.0), 1 / 60.0)
        self.assertTrue(np.allclose(S[0, 0], [0.2, 1.0, 0.25]))
        self.assertTrue(np.allclose(a, 1.0))
        S2, _ = L['phosphor_step'](S, E * 0, (0.2, 1.0, 0.25), (0.1, 0.1, 0.0), 1 / 60.0)
        self.assertAlmostEqual(S2[0, 0, 1], math.exp(-1 / 6.0))
        self.assertEqual(S2[0, 0, 2], 0.0)
        S3, _ = L['phosphor_step'](S, E, (1, 1, 1), (1, 1, 1), 1.0, reset=True)
        self.assertTrue(np.allclose(S3, 1.0))

    def test_check_dir_round_trip(self):
        import json
        bw = bh = 96
        sigma, kn, lref, sx, sy = L['beam_consts'](bw, bh, 1.5, 1.0)
        U, col = L['figure_points']('lissajous', 300, a=3, b=2, rainbow=True)
        Pp = L['place'](U * 0.9, bw, bh, sx, sy, 20.0)
        pts = np.zeros((L['CAP'], 4))
        pts[:300, :2] = Pp
        pts[:299, 2] = 1.0
        pts[:300, 3] = [L['pack_rgb'](c) for c in col]
        E = L['splat_ref'](Pp, pts[:300, 2], np.array([L['unpack_rgb'](v) for v in pts[:300, 3]]), bw, bh, sigma,
                           kn, 1.0, lref, 1.0, True)
        gpu = np.zeros((bh, bw, 4))
        gpu[..., 3] = E @ np.asarray(L['LUMA709'])
        with tempfile.TemporaryDirectory() as d:
            np.save(os.path.join(d, 'gpu.npy'), gpu.astype(np.float32))
            np.save(os.path.join(d, 'points.npy'), pts.astype(np.float32))
            json.dump({'kind': 'beam', 'np': 300, 'sigma': sigma, 'kn': kn, 'dwell': 1.0, 'lref': lref,
                       'intensity': 1.0, 'mono': 1.0}, open(os.path.join(d, 'meta.json'), 'w'))
            r = L['check_dir'](d)
        self.assertLess(r['rel'], 1e-4)                       # float32 points vs float64
        self.assertAlmostEqual(r['sum_gpu'] / r['sum_ref'], 1.0, places=5)   # mono: energy x luma of the rainbow
        src = np.random.RandomState(4).rand(40, 30, 4)
        with tempfile.TemporaryDirectory() as d:
            np.save(os.path.join(d, 'src.npy'), src)
            h = L['hist_ref'](src, 'vectorscope', 2, 256, 128, 1)
            np.save(os.path.join(d, 'gpu.npy'), np.stack([h, h * 0, h * 0, h * 0 + 1], -1).astype(np.float32))
            json.dump({'kind': 'hist', 'mode': 'vectorscope', 'step': 2, 'lv': 256, 'B': 128, 'matrix': 1},
                      open(os.path.join(d, 'meta.json'), 'w'))
            r = L['check_dir'](d)
        self.assertEqual(r['equal_bins'], 1.0)
        self.assertEqual(r['total_gpu'], 15 * 20)
        for s in (L['beam_snippet']('/project1/lab/FX_scope/xy1', '/tmp/a'), L['hist_snippet']('/a', '/b')):
            self.assertTrue(s.startswith('# allow-readback'))
            compile(s, 'snippet', 'exec')

    def test_pack_rgb_round_trip(self):
        for c in ((1, 0, 0), (0.2, 0.5, 0.9), (0, 0, 0), (1, 1, 1)):
            self.assertTrue(np.allclose(L['unpack_rgb'](L['pack_rgb'](c)), c, atol=0.5 / 255))
        self.assertLess(L['pack_rgb']((1, 1, 1)), 2 ** 24)          # exact in float32
        # live bug (31550): GLSL uint(f + 0.5) on white 16777215 rounds to 2^24 in float32 -> black beam
        self.assertEqual(float(np.float32(16777215.0) + np.float32(0.5)), 2.0 ** 24)
        with open(os.path.join(B, 'glsl', 'fx_scope_lib.glsl')) as fh:
            lib = fh.read()
        self.assertIn('uint(round(f))', lib)


@unittest.skipIf(np is None, 'numpy')
class Paths(unittest.TestCase):
    def test_audio_points_hit_samples_and_cap(self):
        S = np.random.RandomState(1).rand(50, 2)
        U = L['audio_points'](S, 4)
        self.assertEqual(len(U), 197)
        self.assertTrue(np.allclose(U[::4], S, atol=1e-12))       # oversampling passes through every sample
        big = np.random.RandomState(2).rand(20000, 2)
        self.assertEqual(len(L['audio_points'](big, 1)), L['CAP'])
        self.assertEqual(L['audio_count'](1, 4), 0)

    def test_test_tone_runs_on_between_frames(self):
        a = L['test_tone_uniforms'](110.0, 1.5, 90.0, 0.8, 48000.0, 100, 60.0)
        b = L['test_tone_uniforms'](110.0, 1.5, 90.0, 0.8, 48000.0, 101, 60.0)
        s0 = L['test_tone'](a[4] + 1, *a[:4], 0.8)
        s1 = L['test_tone'](1, *b[:4], 0.8)
        self.assertTrue(np.allclose(s0[-1], s1[0], atol=1e-9))       # sample n of frame k = sample 0 of frame k+1

    def test_figures_close(self):
        p, _c = L['figure_points']('lissajous', 4001, a=3, b=2, phase=0.25)
        self.assertLess(np.abs(p[0] - p[-1]).max(), 1e-9)
        p, _c = L['figure_points']('spirograph', 4001, R=7, r=4, pen=6)
        self.assertLess(np.abs(p[0] - p[-1]).max(), 1e-9)
        self.assertLessEqual(np.abs(p).max(), 1.0 + 1e-9)
        p, _c = L['figure_points']('rose', 4001, rosek=5 / 4.0, period=L['rose_period'](5, 4))
        self.assertLess(np.abs(p[0] - p[-1]).max(), 1e-9)
        p, _c = L['figure_points']('harmonograph', 2000, damping=0.05, length=60.0)
        self.assertLess(np.abs(p[-200:]).max(), np.abs(p[:200]).max() * 0.2)
        _p, c = L['figure_points']('lissajous', 7, rainbow=True)
        self.assertTrue(np.allclose(c[0], [1, 0, 0]))

    def test_goniometer(self):
        x, y = L['goniometer'](0.5, 0.5)
        self.assertEqual(x, 0.0)
        self.assertAlmostEqual(y, 0.5 * math.sqrt(2))
        x, y = L['goniometer'](0.5, -0.5)
        self.assertEqual(y, 0.0)
        self.assertAlmostEqual(L['correlation']([1, 2, 3], [1, 2, 3]), 1.0)
        self.assertAlmostEqual(L['correlation']([1, -2], [-1, 2]), -1.0)

    def test_vector_path(self):
        xy = np.array([[0, 0], [1, 0], [1, 1], [0, 1.0]])
        rgb = np.array([[1, 1, 1], [1, 1, 1], [0, 0, 0], [0, 0.5, 0.0]])
        p, w, c = L['vector_path'](xy, rgb)
        self.assertEqual(list(w), [1.0, 0.0, 0.5, 0.5])            # segment 1 -> 2 lands on a blank sample
        self.assertTrue(np.allclose(c[2], [0, 1, 0]))               # colour normalised, brightness in the weight
        p, _w, _c = L['vector_path'](xy, rgb, overshoot=0.5)
        self.assertTrue(np.allclose(p[1], [1.5, -0.5]))             # corner pushed outward
        p, w, _c = L['vector_path'](xy, rgb, colour=False, flick=0.7)
        self.assertTrue(np.allclose(w, 0.7))


@unittest.skipIf(np is None, 'numpy')
class Scopes(unittest.TestCase):
    def img(self, W=64, H=48):
        a = np.zeros((H, W, 4))
        a[..., 3] = 1
        return a

    def test_geom(self):
        g = L['hist_geom']('waveform', 1080, 1920, 4, 256, 256)
        self.assertEqual((g['Sx'], g['Sy'], g['w'], g['h'], g['gx'], g['gy'], g['cpt']), (270, 480, 270, 256, 68, 1, 4))
        g = L['hist_geom']('parade', 1080, 1920, 4, 256, 256)
        self.assertEqual((g['w'], g['gx']), (810, 204))
        g = L['hist_geom']('vectorscope', 1080, 1920, 4, 256, 256)
        self.assertEqual((g['w'], g['h'], g['gx'], g['gy']), (256, 256, 8, 8))
        g = L['hist_geom']('histogram', 1080, 1920, 4, 512, 256)
        self.assertEqual((g['w'], g['h'], g['gx'], g['gy'], g['cpt']), (512, 4, 1, 4, 512))

    def test_ramp_waveform(self):
        a = self.img()
        a[..., :3] = (np.arange(64)[None, :, None] + 0.5) / 64.0
        h = L['hist_ref'](a, 'waveform', step=2, lv=256)
        self.assertEqual(h.shape, (256, 32))
        self.assertTrue(((h > 0).sum(0) == 1).all())               # one lit level per column
        self.assertTrue((h.sum(0) == 24).all())                    # Sy samples each
        self.assertEqual(L['hist_ref'](a, 'parade', 2).sum(), 3 * 32 * 24)
        self.assertEqual(L['hist_ref'](a, 'histogram', 2).sum(), 4 * 32 * 24)

    def test_vectorscope_pure_colour(self):
        a = self.img()
        a[..., 0] = 0.75
        h = L['hist_ref'](a, 'vectorscope', step=4, B=256)
        cb, cr = L['bar_targets'](0, 0.75)['R']
        iy, ix = np.unravel_index(np.argmax(h), h.shape)
        self.assertEqual(h.max(), 16 * 12)
        self.assertEqual((ix, iy), (int(math.floor((cb + 0.5) * 256)), int(math.floor((cr + 0.5) * 256))))

    def test_grey_histogram_bin(self):
        a = self.img()
        a[..., :3] = 128 / 255.0
        h = L['hist_ref'](a, 'histogram', step=1, lv=256)
        self.assertTrue((h[:, 128] == 64 * 48).all())

    def test_bar_targets(self):
        t = L['bar_targets'](0, 1.0)
        self.assertAlmostEqual(t['B'][0], 0.5)
        self.assertAlmostEqual(t['R'][1], 0.5)
        for k, o in (('R', 'Cy'), ('G', 'Mg'), ('B', 'Yl')):
            self.assertAlmostEqual(t[k][0], -t[o][0])


@unittest.skipIf(np is None, 'numpy')
class Hud(unittest.TestCase):
    def test_falsecolour(self):
        fc = L['falsecolour'](np.array([0.01, 0.03, 0.2, 0.40, 0.54, 0.98, 1.0]))
        self.assertTrue(np.allclose(fc[0], [0.5, 0, 0.6]))
        self.assertTrue(np.allclose(fc[2], 0.2))
        self.assertTrue(np.allclose(fc[3], [0.1, 0.85, 0.2]))
        self.assertTrue(np.allclose(fc[6], [1, 0, 0]))
        z = L['falsecolour'](np.array([0.33]), 'zones')
        self.assertTrue(np.allclose(z, 0.3))

    def test_zebra_half_the_band(self):
        y = np.tile(np.linspace(0, 1, 400)[None, :], (300, 1))
        m = L['zebra_mask'](y, 0.95, 1.0, 8.0, 45.0)
        band = y >= 0.95
        self.assertAlmostEqual(m.sum() / band.sum(), 0.5, delta=0.03)
        self.assertFalse(m[~band].any())

    def test_sobel_step(self):
        y = np.zeros((10, 10))
        y[:, 5:] = 1.0
        s = L['sobel_mag'](y)
        self.assertAlmostEqual(s[5, 4], 1.0)
        self.assertEqual(s[5, 1], 0.0)

    def test_guides_and_font(self):
        self.assertEqual(L['guide_frame'](1080, 1920, 2.39), (0.0, (1920 - 1080 / 2.39) / 2, 1080.0, 1080 / 2.39))
        self.assertEqual(L['guide_frame'](1920, 1080, 1.0), (420.0, 0.0, 1080.0, 1080.0))
        w = L['font_words']()
        self.assertEqual(len(w), 190)
        self.assertEqual([L['glyph_bit'](ord('A'), 0, c) for c in range(8)], [0, 0, 1, 1, 0, 0, 0, 0])
        self.assertEqual(sum(L['glyph_bit'](32, r, c) for r in range(8) for c in range(8)), 0)
        hud = M['hud']['font_glsl']()
        self.assertTrue(hud.startswith('const uint FONT[190]'))


STUB = """#version 460
layout(binding = 0) uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f, binding = 0) uniform image2DArray mTDComputeOutputs[2];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, name, text):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, name + '.comp')
            with open(p, 'w') as fh:
                fh.write(STUB + text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, name + ': ' + r.stderr[:3000])

    def test_all_shaders_all_switches(self):
        n = 0
        for bufs in ('packed', 'split'):
            for atom in (True, False):
                for name in MODS:
                    Mx = _mod(name)
                    Mx['BE']['BUFFERS'], Mx['BE']['ATOMICS'] = bufs, atom
                    for k, t in Mx['shader_texts']().items():
                        self.assertNotIn('//@', t, (name, k))
                        self.assertTrue(all(ord(ch) < 128 for ch in t))
                        self._ok('%s_%s_%s_%d' % (name, k, bufs, atom), t)
                        n += 1
        self.assertGreaterEqual(n, 4 * 14)


# ------------------------------------------------------------------ dry build on a fake TD
class _Par:
    def __init__(self):
        self.val, self.expr, self.mode = None, '', None


class _Pars:
    def __getattr__(self, k):
        if k.startswith('__'):
            raise AttributeError(k)
        p = _Par()
        object.__setattr__(self, k, p)
        return p

    def __setattr__(self, k, v):
        getattr(self, k).val = v


class _Conn:
    def __init__(self):
        self.connections = []

    def connect(self, src):
        self.connections = [types.SimpleNamespace(owner=src)]


class _Op:
    def __init__(self, cls, name):
        self.OPType, self.name, self.par, self.text, self.comment = cls, name, _Pars(), '', ''
        self.inputConnectors = [_Conn() for _ in range(8)]
        self.seq = types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=1),
                                         array=types.SimpleNamespace(numBlocks=0),
                                         const=types.SimpleNamespace(numBlocks=1))
        self.children = {}
        self.path = '/fake/' + name
        self.stored = {}

    def op(self, n):
        return self.children.get(n)

    def create(self, cls, n):
        o = _Op(cls.__name__, n)
        self.children[n] = o
        return o

    def store(self, k, v):
        self.stored[k] = v


class DryBuild(unittest.TestCase):
    """build(m, H) against a fake TD: every op / par / wire the module makes. Catches name typos only."""

    def run_build(self, name):
        cls = dict((c, type(c, (), {})) for c in ('inTOP', 'outTOP', 'glslTOP', 'textDAT', 'switchTOP', 'constantTOP',
                                                    'constantCHOP', 'selectCHOP', 'mergeCHOP', 'scriptCHOP',
                                                    'parameterexecuteDAT'))
        Mx = _mod(name, ParMode=types.SimpleNamespace(EXPRESSION='e', CONSTANT='c'), **cls)
        Mx['BE'].update(cls)

        def mk(c, k, n):
            o = c.op(n)
            return o if o is not None and o.OPType == k.__name__ else c.create(k, n)

        def expr(par, e):
            par.expr, par.mode = e, 'e'
            compile(e, 'expr', 'eval')

        def compute(m, n, text, ins, res=None, fmt='useinput'):
            g = mk(m, cls['glslTOP'], n)
            g.text = text
            g.par.format = fmt
            for i, s in enumerate(ins):
                g.inputConnectors[i].connect(s)
            return g

        def uniforms(g, U):
            for k, (un, ex) in enumerate(U):
                getattr(g.par, 'vec%dname' % k).val = un
                for e in ex:
                    compile(e, un, 'eval')

        H = {'mk': mk, 'expr': expr, 'sd': lambda o: None, 'compute': compute, 'uniforms': uniforms}
        m = _Op('baseCOMP', name + '1')
        stages = Mx['build'](m, H)
        for s in stages:
            for n in s['ops']:
                if not n.endswith('_compute'):
                    self.assertIn(n, m.children, (name, n))
        self.assertEqual(m.op('out1').inputConnectors[0].connections[0].owner.name, 'out_sel')
        self.assertEqual(m.stored.get('fx_scope_missing'), '')
        return m

    def ins(self, o, n):
        return [o.inputConnectors[i].connections[0].owner.name for i in range(n)]

    def test_beam_modules(self):
        for name, extra in (('xy', []), ('vector', ['sop_path', 'src_rgb']), ('lissajous', [])):
            m = self.run_build(name)
            self.assertEqual(self.ins(m.op('look'), 3), ['in1', 'beam', 'glow_src'])
            self.assertEqual(self.ins(m.op('beam'), 1), ['path'])
            self.assertEqual(self.ins(m.op('src_xy'), 2), ['sel_x', 'sel_y'])
            self.assertEqual(m.op('beam').par.numcolorbufs.val, 2)
            self.assertEqual(m.op('beam').par.outputaccess.val, 'readwrite')
            self.assertEqual(m.op('path').par.array0chop.val, 'src_xy')
            for e in extra:
                self.assertIn(e, m.children)
        m = self.run_build('vector')
        self.assertEqual(m.op('path').par.array1chop.val, 'src_rgb')
        self.assertEqual(m.op('sop_path').par.callbacks.val, 'sop_path_cb')
        compile(m.op('sop_path_cb').text, 'cb', 'exec')

    def test_scopes_and_hud(self):
        m = self.run_build('scopes')
        self.assertEqual(self.ins(m.op('fx'), 2), ['in1', 'hist'])
        self.assertFalse(m.op('hist').par.autodispatchsize.val)
        m = self.run_build('hud')
        self.assertEqual(self.ins(m.op('fx'), 1), ['in1'])
        self.assertIn('Tcreset', m.op('pulses').text)
        compile(m.op('pulses').text, 'pulses', 'exec')


if __name__ == '__main__':
    unittest.main()
