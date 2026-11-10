"""Offline tests for GEN_sdf (builders/gen_sdf.py + gen_sdf_<module>.py + gen_sdf_logic.py). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sdf.py'
Checks: module specs (pages / presets / uniforms declared + used), a fake-TD build of every module network (wiring,
<= 3 GLSL inputs, expressions parse and name real pars), glslc compile of every shader (ray modules with NO input
sampler declared, T-125 (4)), the numpy mirror's maths (analytic sphere hit, SDF identities, escape counts,
perturbation deep zoom vs Decimal direct iteration, composite modes) and that every preset renders a picture."""
import ast
import math
import os
import re
import shutil
import subprocess
import tempfile
import types
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
NS = {}
exec(open(os.path.join(B, 'gen_sdf.py')).read(), NS)
L = {}
exec(open(os.path.join(B, 'gen_sdf_logic.py')).read(), L)
MODS = dict((m, NS['module_ns'](m)) for m in NS['MODULES'])
REF = L['ref_orbit_ns']()


def U_for(module, preset=None, t=1.0, W=54, H=96, extra=None, beats=0.0, level=0.0):
    M = MODS[module]
    vals = dict(next(v for s, _n, v in M['PRESETS'] if s == preset)) if preset else {}
    vals.update(extra or {})
    pars = NS['module_pars'](M, vals)
    return L['uniforms'](NS['uniform_spec'](M), pars, W=W, H=H, t=t, beats=beats, level=level), pars


def ref_for(pars, t=1.0):
    if pars.get('Precision', 0) != 1 or pars['Type'] > 1:
        return None
    jx, jy = pars['Juliacx'], pars['Juliacy']
    if pars['Type'] == 1 and pars['Juliaorbit']:
        w = pars['Juliaspeed'] * t
        jx += pars['Juliaorbit'] * math.cos(w)
        jy += pars['Juliaorbit'] * math.sin(w)
    sx, sy = str(pars.get('Deepx', '')).strip(), str(pars.get('Deepy', '')).strip()
    digits = max(len(sx), len(sy)) + 10 if (sx or sy) else 0
    orb = REF['ref_orbit'](pars['Type'], sx or pars['Centerx'], sy or pars['Centery'], jx, jy,
                           min(int(pars['Iterations']), 16383), digits)
    return REF['ref_array'](orb)


class Specs(unittest.TestCase):
    def test_modules_complete(self):
        self.assertEqual(sorted(MODS), sorted(['scene', 'fractal', 'fractal2d', 'aurora', 'sky', 'planet', 'ocean', 'cloud', 'blackhole', 'terrain']))
        for m, M in MODS.items():
            self.assertEqual(M['MODULE'], m)
            self.assertIn(M['KIND'], ('ray', 'flat'))
            self.assertEqual(M['PAGES'][0][1][0][0], 'Amount', m)
            pages = M['PAGES'] + NS['shared_pages'](M['KIND'])
            names = [p[0] for _pg, ps in pages for p in ps]
            self.assertEqual(len(names), len(set(names)), m)
            for n in names:
                self.assertRegex(n, r'^[A-Z][a-z0-9]*$')
            for pg in M['PANEL_PAGES']:
                self.assertIn(pg, [p for p, _ in pages], m)
            allpars = NS['module_pars'](M)
            menus = dict((p[0], p[3]['names']) for _pg, ps in pages for p in ps if p[1] == 'Menu')
            self.assertGreaterEqual(len(M['PRESETS']), 5, m)
            for slot, _n, vals in M['PRESETS']:
                for k, v in vals.items():
                    self.assertIn(k, allpars, '%s preset %s: %s' % (m, slot, k))
                    if k in menus:
                        self.assertTrue(0 <= v < len(menus[k]), '%s %s %s' % (m, k, v))
            for k in M.get('DEFAULTS', {}):
                self.assertIn(k, allpars, '%s default %s' % (m, k))

    def test_uniforms_declared_and_used(self):
        for m, M in MODS.items():
            spec = NS['uniform_spec'](M)
            self.assertEqual(len(set(n for n, _e in spec)), len(spec), m)
            src = NS['shader'](M)
            for n, ex in spec:
                self.assertEqual(len(ex), 4, (m, n))
                self.assertGreaterEqual(src.count(n), 2, '%s: uniform %s declared but unused' % (m, n))
            U, _p = U_for(m)
            self.assertEqual(set(U), set(n for n, _e in spec))
        fx = NS['fx_shader']()
        for n, _e in NS['FX_UNIFORMS']:
            self.assertGreaterEqual(fx.count(n), 2, n)

    def test_loops_bounded(self):
        # T-124: every for-loop runs to a compile-time cap (a literal or a CAPS define), never a uniform
        for m, M in MODS.items():
            for cond in re.findall(r'for \(int \w+ = 0; \w+ < (\w+);', NS['shader'](M)):
                self.assertTrue(cond.isdigit() or cond in NS['CAPS'], '%s: unbounded loop to %s' % (m, cond))
            self.assertNotIn('while', NS['shader'](M))

    def test_files_ascii_and_td_rules(self):
        for n in ['gen_sdf.py', 'gen_sdf_logic.py'] + ['gen_sdf_%s.py' % m for m in MODS]:
            src = open(os.path.join(B, n), encoding='ascii').read()
            self.assertNotIn('.destroy()', src)
            self.assertNotIn('cookRate', src)


# ------------------------------------------------------------------ fake TD build of a module network
class FakePar(object):
    def __init__(self):
        self.val, self.expr, self.mode = None, None, None

    def __setattr__(self, k, v):
        object.__setattr__(self, k, v)


class FakePars(object):
    def __init__(self):
        object.__setattr__(self, '_d', {})

    def __getattr__(self, k):
        d = object.__getattribute__(self, '_d')
        if k not in d:
            d[k] = FakePar()
        return d[k]

    def __setattr__(self, k, v):
        getattr(self, k).val = v


class FakeConn(object):
    def __init__(self):
        self.src = None

    def connect(self, s):
        self.src = s


class FakeOp(object):
    def __init__(self, cls, name, parent=None):
        self.OPType, self.name, self.parent_ = cls, name, parent
        self.path = (parent.path if parent is not None else '/project1/lab/GEN_sdf') + '/' + name
        self.par = FakePars()
        self.inputConnectors = [FakeConn() for _ in range(3)]
        self.seq = types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=0),
                                         const=types.SimpleNamespace(numBlocks=0))
        self.text, self.comment, self.dock, self.viewer, self.valid = '', '', None, False, True
        self.ops = {}

    def op(self, n):
        return self.ops.get(n)

    def create(self, cls, name):
        o = FakeOp(cls.__name__, name, self)
        self.ops[name] = o
        return o


def fake_build(module):
    ns = dict(NS)
    for c in ('inTOP', 'outTOP', 'glslTOP', 'textDAT', 'scriptTOP', 'constantCHOP', 'speedCHOP', 'parameterexecuteDAT',
              'switchTOP'):
        ns[c] = type(c, (), {})
    ns['ParMode'] = types.SimpleNamespace(EXPRESSION='expr')
    ns['safe_destroy'] = lambda o: None
    code = compile(open(os.path.join(B, 'gen_sdf.py')).read(), 'gen_sdf.py', 'exec')
    exec(code, ns)
    for c in ('inTOP', 'outTOP', 'glslTOP', 'textDAT', 'scriptTOP', 'constantCHOP', 'speedCHOP', 'parameterexecuteDAT',
              'switchTOP'):
        ns[c] = type(c, (), {})
    ns['safe_destroy'] = lambda o: None
    m = FakeOp('baseCOMP', module + '1')
    stages = ns['_module_network'](m, MODS[module])
    return m, stages


class FakeBuild(unittest.TestCase):
    def test_networks(self):
        for module, M in MODS.items():
            with self.subTest(module=module):
                m, stages = fake_build(module)
                rm, fx, out1, in1 = m.op('rm'), m.op('fx'), m.op('out1'), m.op('in1')
                self.assertEqual(fx.inputConnectors[0].src, in1)
                up, easu, rcas = m.op('up'), m.op('easu'), m.op('rcas')
                self.assertEqual(fx.inputConnectors[1].src, up)           # FSR branch (SX-10)
                self.assertEqual(up.inputConnectors[0].src, rm)
                self.assertEqual(up.inputConnectors[1].src, rcas)
                self.assertEqual(rcas.inputConnectors[0].src, easu)
                self.assertEqual(easu.inputConnectors[0].src, rm)
                self.assertEqual(up.par.index.expr, 'parent().par.Upscale.menuIndex')
                self.assertEqual(m.op('easu_compute').text, NS['fsr_shader']('easu'))
                self.assertEqual(m.op('rcas_compute').text, NS['fsr_shader']('rcas'))
                self.assertEqual(out1.inputConnectors[0].src, fx)
                if M.get('REF_PY'):
                    self.assertEqual(rm.inputConnectors[0].src, m.op('ref'))
                    self.assertIn('def onCook', m.op('ref_callbacks').text)
                else:
                    self.assertIsNone(rm.inputConnectors[0].src)
                self.assertEqual(rm.par.format.val, 'rgba32float')
                self.assertEqual(m.op('rm_compute').text, NS['shader'](M))
                pars = set(NS['module_pars'](M)) | set(n for _pg, ps in M['PAGES'] + NS['shared_pages'](M['KIND'])
                                                         for n, *_r in ps)
                for g, spec in ((rm, NS['uniform_spec'](M)), (fx, NS['FX_UNIFORMS']), (easu, NS['EASU_UNIFORMS']),
                                (rcas, NS['RCAS_UNIFORMS'])):
                    self.assertEqual(g.seq.vec.numBlocks, len(spec))
                    for k, (un, _ex) in enumerate(spec):
                        self.assertEqual(getattr(g.par, 'vec%dname' % k).val, un)
                        for comp in 'xyzw':
                            e = getattr(g.par, 'vec%dvalue%s' % (k, comp)).expr
                            ast.parse(e, mode='eval')
                            for ref in re.findall(r'parent\(\)\.par\.(\w+)', e):
                                self.assertIn(ref, pars, e)
                for s in stages:
                    for n in s['ops']:
                        self.assertIsNotNone(m.op(n), (module, n))
                if M.get('REF_PY'):                       # the callback text is valid Python
                    compile(m.op('ref_callbacks').text, 'ref_callbacks', 'exec')


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _cc(self, src, name):
        d = tempfile.mkdtemp()
        p = os.path.join(d, name + '.comp')
        open(p, 'w').write(src)
        r = subprocess.run(['glslc', '-fshader-stage=compute', '--target-env=opengl', '-fauto-bind-uniforms',
                            '-fauto-map-locations', '-o', os.devnull, p], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, '%s: %s' % (name, r.stderr[:1200]))

    @staticmethod
    def prelude(n):
        s = '#version 450\n'
        if n:
            s += 'layout(binding = 0) uniform sampler2D sTD2DInputs[%d];\n' % n
        return s + ('layout(binding = 4, rgba32f) uniform writeonly image2D mTDOut[1];\n'
                    'void TDImageStoreOutput(int i, ivec3 c, vec4 v) { imageStore(mTDOut[0], c.xy, v); }\n')

    def test_every_shader_compiles(self):
        for m, M in MODS.items():
            # ray modules have nothing wired: TD declares no sTD2DInputs (T-125 (4)), so compile without it
            self._cc(self.prelude(1 if M.get('REF_PY') else 0) + NS['shader'](M), m)
        self._cc(self.prelude(2) + NS['fx_shader'](), 'fx')
        for w in ('easu', 'rcas'):
            self._cc(self.prelude(1) + NS['fsr_shader'](w), w)


class Mirror(unittest.TestCase):
    def test_sphere_hit_distance(self):
        # one blob, no smoothing, camera aimed at its centre: the centre ray hits at |ro - c| - r
        U, _p = U_for('scene', extra={'Scenea': 4, 'Blobs': 1, 'Smooth': 0.0, 'Orbitspeed': 0.0, 'Camdist': 5.0,
                                      'View': 1, 'Epsilon': 0.05, 'Steps': 256}, W=55, H=97)
        R = L['Ray']('scene', U, 55, 97)
        c = R.M.BC[0]
        U2, _p = U_for('scene', extra={'Scenea': 4, 'Blobs': 1, 'Smooth': 0.0, 'Orbitspeed': 0.0, 'Camdist': 5.0,
                                       'View': 1, 'Epsilon': 0.05, 'Steps': 256, 'Targetx': float(c[0]),
                                       'Targety': float(c[1]), 'Targetz': float(c[2])}, W=55, H=97)
        R2 = L['Ray']('scene', U2, 55, 97)
        o = R2.render([27], [48])[0]
        self.assertEqual(o[1], 1.0)
        self.assertAlmostEqual(float(o[0]), 5.0 - float(R2.M.BR[0]), 2)

    def test_sdf_identities(self):
        U, _p = U_for('scene', extra={'Detail': 0})
        S = L['Scene'](L['Ctx'](U, 54, 96))
        p = np.array([[1.5, 0.2, -0.3], [0.1, 0.2, 0.3], [3.0, 3.0, 3.0]], dtype=np.float32)
        np.testing.assert_allclose(S.sponge(p), L['sdBox'](p, (1, 1, 1)), atol=1e-6)    # 0 iterations = box
        np.testing.assert_allclose(L['sdBox'](p[:1], (1, 1, 1)), [0.5], atol=1e-6)
        a, b = np.float32([0.3, 1.0]), np.float32([0.35, -1.0])
        self.assertTrue(np.all(L['smin'](a, b, 0.5) <= np.minimum(a, b) + 1e-7))     # smooth min never above min
        U, _p = U_for('scene', extra={'Thickness': 0.1})
        S = L['Scene'](L['Ctx'](U, 54, 96))
        q = np.array([[0.5, 0.5, 0.0]], dtype=np.float32)                            # lattice: rod along z 0.5*sqrt2
        self.assertAlmostEqual(float(S.lattice(q)[0]), 0.5 - 0.05, 5)
        self.assertAlmostEqual(float(S.tunnel(np.array([[0.0, 0.0, 0.0]], dtype=np.float32))[0]), 0.95 - 0.0, 5)

    def test_city_hash_matches_gen_pattern(self):
        G = {}
        exec(open(os.path.join(B, 'gen_pattern_logic.py')).read(), G)
        for cx, cy, s in ((0, 0, 1), (-3, 5, 7), (12, -9, 100)):
            self.assertAlmostEqual(float(L['h2']([cx], [cy], s)[0]), G['h2'](cx, cy, s), 6)

    def test_fractal_de_signs(self):
        for ty in range(4):
            U, _p = U_for('fractal', extra={'Type': ty, 'Iterations': 10})
            Fr = L['Fractal'](L['Ctx'](U, 54, 96))
            far = Fr.map(np.array([[0.0, 0.0, 20.0]], dtype=np.float32))[0]
            self.assertGreater(float(far), 1.0, ty)                                   # far away = far

    def test_bulb_whole_power_equals_trig(self):
        # the trig-free whole-power path (complex powers) = the spherical-angle formula in float64
        p = np.random.RandomState(3).uniform(-1.3, 1.3, (4000, 3)).astype(np.float32)
        for pw in (2.0, 5.0, 8.0, 16.0):
            U, _p = U_for('fractal', extra={'Type': 0, 'Power': pw, 'Iterations': 6})
            Fr = L['Fractal'](L['Ctx'](U, 54, 96))
            d, _t = Fr.bulb(p)
            z, c = p.astype(np.float64), p.astype(np.float64)
            dr, r = np.ones(len(p)), np.zeros(len(p))
            live = np.ones(len(p), bool)
            for _i in range(6):
                rr = np.linalg.norm(z, axis=1)
                r = np.where(live, rr, r)
                live &= rr <= 2.0
                th = np.arccos(np.clip(z[:, 2] / np.maximum(r, 1e-9), -1, 1)) * pw
                ph = np.arctan2(z[:, 1], z[:, 0]) * pw
                zn = (r ** pw)[:, None] * np.stack([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)], 1) + c
                dr = np.where(live, r ** (pw - 1) * pw * dr + 1.0, dr)
                z = np.where(live[:, None], zn, z)
            ref = 0.5 * np.log(np.maximum(r, 1e-9)) * r / np.maximum(dr, 1e-9)
            rel = np.abs(d - ref) / np.maximum(np.abs(ref), 1e-2)
            self.assertLess(float(np.median(rel)), 1e-4, pw)
            self.assertGreater(float((rel < 1e-2).mean()), 0.99, pw)

    def test_overrelax_one_is_classic(self):
        # Overrelax 1 = classic sphere tracing; 1.2 keeps hits and t (2 % rel) on almost every pixel
        out = {}
        for om in (1.0, 1.2):
            U, _p = U_for('scene', 2, W=54, H=96, extra={'View': 1, 'Overrelax': om})
            ys, xs = np.mgrid[0:96, 0:54]
            out[om] = L['Ray']('scene', U, 54, 96).render(xs.ravel(), ys.ravel())
        a, b = out[1.0], out[1.2]
        both = (a[:, 1] > 0.5) & (b[:, 1] > 0.5)
        self.assertGreater(float((a[:, 1] == b[:, 1]).mean()), 0.98)
        self.assertGreater(float((np.abs(a[both, 0] - b[both, 0]) / a[both, 0] < 0.02).mean()), 0.98)
        self.assertLess(float(b[:, 2].sum()), float(a[:, 2].sum()))                # fewer steps

    def test_mandelbrot_escape_counts(self):
        # c = 1 (pixel at the centre with centre 1): 0 -> 1 -> 2 -> 5 -> 26 -> 677: |z|^2 > 256^2 at iteration 5
        U, _p = U_for('fractal2d', extra={'Type': 0, 'Centerx': 1.0, 'Centery': 0.0, 'View': 1}, W=55, H=97)
        o = L['expect_rm']('fractal2d', U, [27], [48], 55, 97)[0]
        self.assertEqual(o[1], 1.0)
        mu = 5 + 1 - math.log(0.5 * math.log(677.0 ** 2)) / math.log(2.0)
        self.assertAlmostEqual(o[0], mu, 3)
        U, _p = U_for('fractal2d', extra={'Type': 0, 'Centerx': -1.0, 'Centery': 0.0, 'View': 1}, W=55, H=97)
        self.assertEqual(L['expect_rm']('fractal2d', U, [27], [48], 55, 97)[0][1], 0.0)   # -1: period 2, inside

    def test_perturbation_matches_direct_deep(self):
        # zoom 1e10 at the seahorse point: float32 deltas + float64 reference (rebasing) vs exact Decimal iteration
        from decimal import Decimal, getcontext
        W, H, it = 31, 55, 1500
        cx, cy = -0.743643887037151, 0.131825904205330
        U, pars = U_for('fractal2d', extra={'Type': 0, 'Centerx': cx, 'Centery': cy, 'Zoom': 1e10, 'Iterations': it,
                                            'Precision': 1, 'View': 1}, W=W, H=H)
        ref = ref_for(pars)
        pts = [(x, y) for x in range(0, W, 3) for y in range(0, H, 5)]
        got = L['expect_rm']('fractal2d', U, [p[0] for p in pts], [p[1] for p in pts], W, H, ref)
        getcontext().prec = 40
        sc = Decimal(3) / Decimal(10) ** 10
        same, n, gross = 0, 0, 0
        for (x, y), g in zip(pts, got):
            ccx = Decimal(repr(cx)) + (Decimal(x) + Decimal('0.5') - Decimal(W) / 2) / H * sc
            ccy = Decimal(repr(cy)) + (Decimal(y) + Decimal('0.5') - Decimal(H) / 2) / H * sc
            zx = zy = Decimal(0)
            mu, esc = 0.0, False
            for i in range(it):
                zx, zy = zx * zx - zy * zy + ccx, 2 * zx * zy + ccy
                r2 = zx * zx + zy * zy
                if r2 > 65536:
                    mu, esc = i + 2 - math.log(0.5 * math.log(float(r2))) / math.log(2.0), True
                    break
            n += 1
            if esc == (g[1] > 0.5) and (not esc or abs(g[0] - mu) < 0.05):
                same += 1
            if esc != (g[1] > 0.5) or abs(g[0] - mu) > 1.0:
                gross += 1
        # this spot is chaotic (counts 1000-1500): a float64 perturbation of the same code scores 0.93 / 5 % gross,
        # float32 0.85 / 9 %, so the gate is the float32 level (measured 26 Oct)
        self.assertGreaterEqual(same / float(n), 0.82, (same, n))
        self.assertLessEqual(gross / float(n), 0.12, (gross, n))

    def test_perturbation_equals_float_at_zoom_1(self):
        W, H = 27, 48
        a, _p = U_for('fractal2d', 1, W=W, H=H, extra={'View': 1})
        b, pb = U_for('fractal2d', 1, W=W, H=H, extra={'View': 1, 'Precision': 1})
        pts = [(x, y) for x in range(W) for y in range(0, H, 3)]
        ga = L['expect_rm']('fractal2d', a, [p[0] for p in pts], [p[1] for p in pts], W, H)
        gb = L['expect_rm']('fractal2d', b, [p[0] for p in pts], [p[1] for p in pts], W, H, ref_for(pb))
        agree = sum((x[1] == y[1]) and (x[1] == 0 or abs(x[0] - y[0]) < 0.05) for x, y in zip(ga, gb))
        self.assertGreaterEqual(agree / float(len(pts)), 0.97)

    def test_cycle_check_keeps_escapes(self):
        # Brent periodicity only stops interior orbits: escaped pixels and their mu are unchanged
        W, H = 27, 48
        pts = [(x, y) for x in range(W) for y in range(0, H, 2)]
        for slot in (1, 3, 5):
            a, _p = U_for('fractal2d', slot, W=W, H=H, extra={'View': 1, 'Cyclecheck': 0})
            b, _p = U_for('fractal2d', slot, W=W, H=H, extra={'View': 1, 'Cyclecheck': 1})
            ga = L['expect_rm']('fractal2d', a, [p[0] for p in pts], [p[1] for p in pts], W, H)
            gb = L['expect_rm']('fractal2d', b, [p[0] for p in pts], [p[1] for p in pts], W, H)
            for x, y in zip(ga, gb):
                self.assertEqual(x[1], y[1], slot)
                if x[1]:
                    self.assertAlmostEqual(x[0], y[0], 5)

    def test_composite(self):
        c = [0.2, 0.4, 0.6, 1.0]
        s = [0.3, 0.1, 0.0, 0.5]
        U = {'uAmt': (0.0, 0, 0, 0), 'uBg': (0.1, 0.1, 0.1, 0)}
        self.assertEqual(L['compose'](U, s, c), c)                                    # Amount 0 = passthrough
        for mode, want in ((0, [0.35, 0.15, 0.05, 1.0]), (1, [0.4, 0.3, 0.3, 1.0]), (2, [0.5, 0.5, 0.6, 1.0]),
                           (6, s)):
            got = L['compose']({'uAmt': (1.0, mode, 0, 0), 'uBg': (0.1, 0.1, 0.1, 0)}, s, c)
            for g, w in zip(got, want):
                self.assertAlmostEqual(g, w, 6, (mode, got))

    def test_ref_orbit_decimal_equals_float_shallow(self):
        a = REF['ref_orbit'](0, -0.5, 0.1, 0, 0, 50)
        b = REF['ref_orbit'](0, '-0.5', '0.1', 0, 0, 50, digits=30)
        self.assertEqual(len(a), len(b))
        for (x1, y1), (x2, y2) in zip(a, b):
            self.assertAlmostEqual(x1, x2, 9)
            self.assertAlmostEqual(y1, y2, 9)


class TailMirror(unittest.TestCase):
    """GEN_sdf tail modules (lane C2, 27 Oct): the mirror's own maths."""

    def test_ocean_hit_lies_on_the_surface(self):
        # regula falsi: at the returned t the ray point sits on the height field (|y - h| small vs the wave height)
        W, H = 27, 48
        U, pars = U_for('ocean', 1, W=W, H=H, extra={'View': 1, 'Steps': 24})
        ys, xs = np.mgrid[0:H, 0:W]
        o = np.asarray(L['expect_rm']('ocean', U, xs.ravel().tolist(), ys.ravel().tolist(), W, H))
        hit = o[:, 1] > 0.5
        self.assertGreater(hit.mean(), 0.4)                          # pitch -12: the lower part is sea
        self.assertTrue((o[~hit, 0] == pars['Far']).all())          # misses report Far (sky)
        C = L['Ctx'](U, W, H)
        rd = L['flat_cam'](C, xs.ravel(), ys.ravel(), math.radians(pars['Yaw']), math.radians(pars['Pitch']),
                           math.radians(pars['Fov']))
        ro = np.array([0.0, pars['Camheight'], pars['Flyspeed'] * 1.0], np.float32)
        p = ro[None, :] + rd[hit] * o[hit, 0:1].astype(np.float32)
        h = L['ocean_h'](C, p[:, 0], p[:, 2], pars['Octaves'], 1.0)
        self.assertLess(float(np.median(np.abs(p[:, 1] - h))), 0.01 * pars['Height'])
        # straight down from the camera: t = camheight - h(camera xz)
        U2, p2 = U_for('ocean', 1, W=W, H=H, extra={'View': 1, 'Steps': 24, 'Pitch': -89.0, 'Fov': 20.0})
        oc = L['expect_rm']('ocean', U2, [13], [24], W, H)[0]
        h0 = L['ocean_h'](L['Ctx'](U2, W, H), np.float32([0.0]), np.float32([1.5]), p2['Octaves'], 1.0)[0]
        self.assertAlmostEqual(oc[0], p2['Camheight'] - float(h0), 1)

    def test_ocean_rising_horizon_is_sky(self):
        U, _p = U_for('ocean', 1, W=27, H=48, extra={'View': 1, 'Pitch': 30.0})
        o = L['expect_rm']('ocean', U, [13], [47], 27, 48)[0]        # top row looks up: no sea
        self.assertEqual(o[1], 0.0)


class TailCloud(unittest.TestCase):
    def test_cloud_noise_hash_and_range(self):
        U, _p = U_for('cloud', 1)
        C = L['Ctx'](U, 54, 96)
        # one corner hash by hand (32-bit wrap, the GLSL uint maths)
        ix, iy, iz = -3, 5, 7
        v = ((ix & 0xffffffff) * 73856093 & 0xffffffff) ^ (iy * 19349663 & 0xffffffff) ^ (iz * 83492791 & 0xffffffff) ^ \
            ((C.SEED * 2654435761) & 0xffffffff)
        want = int(L['lb32'](np.uint64(v))) / 4294967296.0
        self.assertAlmostEqual(float(L['cn_hash'](C, [ix], [iy], [iz])[0]), want, 6)
        p = np.random.RandomState(1).uniform(-20, 20, (5000, 3)).astype(np.float32)
        n = L['cn_noise'](C, p)
        self.assertTrue(((n >= 0) & (n <= 1)).all())
        # lattice points return the corner hash exactly
        q = np.float32([[2.0, -1.0, 4.0]])
        self.assertAlmostEqual(float(L['cn_noise'](C, q)[0]), float(L['cn_hash'](C, [2], [-1], [4])[0]), 6)

    def test_cloud_transmittance(self):
        W, H = 27, 48
        ys, xs = np.mgrid[0:H, 0:W]
        U, _p = U_for('cloud', 1, W=W, H=H, extra={'View': 1, 'Density': 0.0})
        o = np.asarray(L['expect_rm']('cloud', U, xs.ravel().tolist(), ys.ravel().tolist(), W, H))
        self.assertTrue(np.allclose(o[:, 2], 1.0))                   # no density: nothing absorbs
        U, _p = U_for('cloud', 4, W=W, H=H, extra={'View': 1})
        o = np.asarray(L['expect_rm']('cloud', U, xs.ravel().tolist(), ys.ravel().tolist(), W, H))
        self.assertTrue(((o[:, 2] >= 0) & (o[:, 2] <= 1)).all())
        self.assertLess(float(o[:, 2].min()), 0.2)                     # the storm deck is opaque somewhere
        hit = o[:, 1] > 0.5
        self.assertTrue((o[~hit, 2] == 1.0).all())                     # rays that miss the slab keep 1


class TailBlackhole(unittest.TestCase):
    def test_shadow_is_larger_than_the_horizon(self):
        # Schwarzschild: the shadow radius is sqrt(27)/2 = 2.6 horizons; without bending it is the horizon itself
        W, H = 41, 41
        ys, xs = np.mgrid[0:H, 0:W]
        frac = {}
        for bend in (0.0, 1.0):
            U, _p = U_for('blackhole', 1, W=W, H=H, extra={'View': 1, 'Bend': bend, 'Orbitspeed': 0.0, 'Campitch': 0.0,
                                                           'Diskopacity': 0.0, 'Steps': 256, 'Stepsize': 0.05})
            o = np.asarray(L['expect_rm']('blackhole', U, xs.ravel().tolist(), ys.ravel().tolist(), W, H))
            frac[bend] = o[:, 1].mean()
            self.assertEqual(o[(H // 2) * W + W // 2, 1], 1.0, bend)              # the centre ray is captured
        ratio = math.sqrt(frac[1.0] / frac[0.0])                                    # disc areas -> radius ratio
        self.assertGreater(ratio, 2.2)
        self.assertLess(ratio, 3.0)


class TailTerrain(unittest.TestCase):
    def test_noise_derivative_is_the_gradient(self):
        U, _p = U_for('terrain', 1)
        C = L['Ctx'](U, 54, 96)
        rs = np.random.RandomState(4)
        x, y = rs.uniform(-30, 30, 2000).astype(np.float32), rs.uniform(-30, 30, 2000).astype(np.float32)
        v, gx, gy = L['th_noised'](C, x, y)
        e = np.float32(1e-3)
        fx = (L['th_noised'](C, x + e, y)[0] - L['th_noised'](C, x - e, y)[0]) / (2 * e)
        fy = (L['th_noised'](C, x, y + e)[0] - L['th_noised'](C, x, y - e)[0]) / (2 * e)
        self.assertTrue(((v >= -1) & (v <= 1)).all())
        self.assertLess(float(np.median(np.abs(fx - gx))), 0.01)
        self.assertLess(float(np.median(np.abs(fy - gy))), 0.01)

    def test_hits_lie_on_the_ground(self):
        W, H = 27, 48
        U, pars = U_for('terrain', 1, W=W, H=H, extra={'View': 1, 'Steps': 200, 'Relax': 0.3})
        ys, xs = np.mgrid[0:H, 0:W]
        o = np.asarray(L['expect_rm']('terrain', U, xs.ravel().tolist(), ys.ravel().tolist(), W, H))
        hit = o[:, 1] > 0.5
        self.assertGreater(hit.mean(), 0.3)
        C = L['Ctx'](U, W, H)
        rd = L['flat_cam'](C, xs.ravel(), ys.ravel(), math.radians(pars['Yaw']), math.radians(pars['Pitch']),
                           math.radians(pars['Fov']))
        ro = np.array([0.0, 0.0, pars['Flyspeed'] * 1.0], np.float32)
        ro[1] = L['terrain_h'](C, ro[:1], ro[2:], 3, np.float32(pars['Theight']))[0] + pars['Camheight']
        p = ro[None, :] + rd[hit] * o[hit, 0:1].astype(np.float32)
        g = L['terrain_h'](C, p[:, 0], p[:, 2], pars['Octaves'], np.float32(pars['Theight']))
        gap = p[:, 1] - g
        self.assertTrue((gap < 0.002 * o[hit, 0] + 1e-6).all())          # stopped within the hit threshold
        self.assertGreater(float(np.median(gap)), -0.05)                  # and not deep below the ground


class Presets(unittest.TestCase):
    def test_every_preset_renders_a_picture(self):
        W, H = 27, 48
        for m, M in MODS.items():
            for slot, name, _v in M['PRESETS']:
                U, pars = U_for(m, slot, W=W, H=H)
                img = L['render_img'](m, U, W, H, ref_for(pars) if m == 'fractal2d' else None)
                self.assertFalse(np.isnan(img).any(), (m, name))
                lum = 0.2126 * img[:, :, 0] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 2]
                self.assertGreater(float(lum.max() - lum.min()), 0.1, '%s preset %d %s is flat' % (m, slot, name))


if __name__ == '__main__':
    unittest.main()
