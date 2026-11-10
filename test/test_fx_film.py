"""Offline tests for the FX_film rack (builders/fx_film.py), its 10 modules (builders/fx_film_<m>.py) and the maths
(builders/fx_film_logic.py). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_film.py'
The build test runs every module's build() against fake TD ops: wiring, uniform names (set == declared), every
expression compiles, every parent().par.X exists. GLSL compiles with glslc (OpenGL target) against stubs of the TD
names used: a syntax/type check, NOT a TD compile (that is LIVE CHECK step 1 in docs/builds/fx_film.md)."""
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
DOC = os.path.join(REPO, 'docs', 'builds', 'fx_film.md')
sys.path.insert(0, BUILDERS)
import fx_film_logic as L  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None

RACK = {}
with open(os.path.join(BUILDERS, 'fx_film.py')) as _fh:
    exec(_fh.read(), RACK)
MODS = RACK['MODULES']


# ------------------------------------------------------------------ fake TD
class FakePar(object):
    def __init__(self):
        self.val, self.expr, self.mode = None, None, None


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
    def __init__(self, cls, name):
        self.OPType, self.name = cls, name
        self.par = FakePars()
        self.inputConnectors = [FakeConn() for _ in range(12)]
        self.seq = types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=0))
        self.text, self.comment, self.dock, self.U = '', '', None, []


class FakeComp(object):
    def __init__(self):
        self.ops = {}

    def op(self, n):
        return self.ops.get(n)


TD_CLASSES = ['inTOP', 'outTOP', 'glslTOP', 'glslmultiTOP', 'textDAT', 'switchTOP', 'crossTOP', 'parameterexecuteDAT',
              'moviefileinTOP', 'tableDAT', 'baseCOMP', 'scriptTOP', 'selectTOP', 'constantTOP']


def run_build(module):
    """exec the module with the rack globals, run build(m, H) on fakes; returns (ns, comp, record)."""
    rec = {'compute': [], 'exprs': [], 'outsel': None}
    ns = dict(RACK)
    for c in TD_CLASSES:
        ns[c] = type(c, (), {})
    with open(os.path.join(BUILDERS, 'fx_film_%s.py' % module)) as fh:
        exec(compile(fh.read(), 'fx_film_%s.py' % module, 'exec'), ns)
    m = FakeComp()

    def mk(comp, cls, name):
        if name not in comp.ops:
            comp.ops[name] = FakeOp(cls.__name__, name)
        return comp.ops[name]

    def compute(comp, name, text, ins, res=None, fmt='useinput', extend=None, filt=None, dispatch=None):
        g = mk(comp, ns['glslTOP'], name)
        g.text = text
        for k, s in enumerate(ins):
            g.inputConnectors[k].connect(s)
        rec['compute'].append({'name': name, 'text': text, 'ins': [s.name for s in ins], 'res': res, 'fmt': fmt,
                               'extend': extend, 'filt': filt, 'dispatch': dispatch, 'op': g})
        for e in list(res or ()) + list(dispatch or ()):
            if isinstance(e, str):
                rec['exprs'].append(e)
        return g

    def uniforms(g, U):
        g.U = list(U)
        for _n, ex in U:
            rec['exprs'].extend(e for e in ex if isinstance(e, str))

    def outsel(comp, in1, wet, cond=None):
        rec['outsel'] = (in1.name, wet.name, cond)
        sw = mk(comp, ns['switchTOP'], 'out_sel')
        sw.inputConnectors[0].connect(in1)
        sw.inputConnectors[1].connect(wet)
        return sw

    rns = dict(RACK)
    rns['_compute'], rns['_uniforms'] = compute, uniforms
    with open(os.path.join(BUILDERS, 'fx_film.py')) as fh:
        exec(compile(fh.read(), 'fx_film.py', 'exec'), rns)
    rns['_compute'], rns['_uniforms'] = compute, uniforms          # _ext looks these up at call time
    H = dict(RACK['H'])
    H.update({'mk': mk, 'expr': lambda p, e: rec['exprs'].append(e), 'compute': compute, 'uniforms': uniforms,
              'outsel': outsel, 'ext': rns['_ext'], 'pyr': rns['_pyr'], 'L': L})
    stages = ns['build'](m, H)
    return ns, m, rec, stages


def par_names(pages):
    out = set()
    for _pg, pars in pages:
        for name, style, _d, _o in pars:
            out |= {name + k for k in 'rgb'} if style == 'RGB' else {name}
    return out


TD_STUB = """#version 460
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
uniform sampler2D sTD2DInputs[9];
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[0], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[0], c); }
"""


# ------------------------------------------------------------------ rack
class Rack(unittest.TestCase):
    def test_chain(self):
        rows = [{'name': 'a', 'order': '2'}, {'name': 'b', 'order': '1'}, {'name': 'c', 'order': '2'}]
        self.assertEqual(RACK['plan_chain'](rows), ['b', 'a', 'c'])
        self.assertEqual(len(set(RACK['chain_edges'](['s1', 's2'])) - set(RACK['chain_edges'](['s1']))), 7)
        self.assertEqual(RACK['next_name']('grain', {'grain1', 'grain3'}), 'grain2')

    def test_default_rows(self):
        rows = RACK['DEFAULT_ROWS']
        self.assertEqual([r[1] for r in rows], MODS)
        self.assertEqual(len(MODS), 14)
        self.assertTrue(all(r[2] == 0 for r in rows), 'every slot starts bypassed (cost 0)')
        self.assertEqual(MODS[-1], 'tonecurve', 'display dither must be last in the chain')
        for m in MODS:
            self.assertTrue(os.path.exists(os.path.join(BUILDERS, 'fx_film_%s.py' % m)), m)

    def test_ext_exprs(self):
        X = RACK['ext_exprs']('2', 128)
        env = {'op': lambda n: types.SimpleNamespace(width=1080, height=1920), 'math': math}
        vals = [eval(X[k], env) for k in ('vw', 'vh', 'pw', 'ph')]
        self.assertEqual(vals, list(L.pad_dims(1080, 1920, 2, 128)))
        self.assertEqual(vals, [540, 960, 640, 1024])
        X4 = RACK['ext_exprs']('4', 64)
        self.assertEqual([eval(X4[k], env) for k in ('vw', 'vh', 'pw', 'ph')], [270, 480, 320, 512])

    def test_slot_gate(self):
        # perf lane 3: the T-198 slot_gate in this copied rack (same test as <name>_slot; no row = on)
        so = RACK['slot_off']
        self.assertEqual([so('1', '1'), so('0', '1'), so('1', '0'), so(None, None), so('1', '0.5')],
                         [False, True, True, False, False])
        compile(RACK['SLOT_GATE_E'], '<gate>', 'eval')
        st = RACK['gate_stages']([{'ops': ['fx']}, {'ops': ['out_sel', 'out1']}])
        self.assertEqual(st[-1]['ops'], ['out_sel', 'slot_gate', 'out1'])

    def test_ascii(self):
        for f in ['fx_film.py', 'fx_film_logic.py'] + ['fx_film_%s.py' % m for m in MODS]:
            with open(os.path.join(BUILDERS, f), encoding='ascii') as fh:
                fh.read()


# ------------------------------------------------------------------ modules (templates + fake build)
class Modules(unittest.TestCase):
    def test_templates(self):
        for mod in MODS:
            ns, _m, _r, _s = run_build(mod)
            self.assertEqual(ns['MODULE'], mod)
            self.assertEqual(ns['PAGES'][0][1][0][0], 'Amount', mod)
            pages = [pg for pg, _ in ns['PAGES']]
            for pg in ns['PANEL_PAGES']:
                self.assertIn(pg, pages, mod)
            names = [n for _pg, pars in ns['PAGES'] for n, *_r in pars]
            self.assertEqual(len(names), len(set(names)), mod + ' duplicate par names')
            self.assertTrue(3 <= len(ns['PRESETS']) <= 5, mod)

    def test_presets_use_real_pars(self):
        for mod in MODS:
            ns, _m, _r, _s = run_build(mod)
            names = par_names(ns['PAGES'])
            menus = dict((n, o['names']) for _pg, pars in ns['PAGES'] for n, st, _d, o in pars if st == 'Menu')
            for _slot, pname, vals in ns['PRESETS']:
                for k, v in vals.items():
                    self.assertIn(k, names, '%s preset %s: %s' % (mod, pname, k))
                    if k in menus:
                        self.assertTrue(0 <= v < len(menus[k]), '%s preset %s: %s=%r' % (mod, pname, k, v))

    def test_build_wiring_and_uniforms(self):
        for mod in MODS:
            ns, m, rec, stages = run_build(mod)
            names = par_names(ns['PAGES'])
            self.assertIn('in1', m.ops, mod)
            self.assertIn('out1', m.ops, mod)
            out_src = m.ops['out1'].inputConnectors[0].src
            self.assertIsNotNone(out_src, mod)
            if len(rec['compute']) > 1:
                self.assertEqual(out_src.name, 'out_sel', mod + ': multi-pass modules end in out_sel')
                self.assertEqual(rec['outsel'][0], 'in1')
            for c in rec['compute']:
                declared = set(re.findall(r'uniform\s+vec4\s+(\w+)\s*;', c['text']))
                setn = [n for n, _e in c['op'].U]
                self.assertEqual(set(setn), declared, '%s.%s uniforms' % (mod, c['name']))
                self.assertEqual(len(setn), len(set(setn)))
                for n, ex in c['op'].U:
                    self.assertEqual(len(ex), 4, '%s.%s %s' % (mod, c['name'], n))
                self.assertGreaterEqual(len(c['ins']), 1, mod)
                if 'mipTap' in c['text']:                 # pyramid gather: EXT (level 0), pyra (1..4), pyrb (5..7)
                    self.assertEqual(c['ins'], ['ext', 'pyra', 'pyrb'], '%s.%s gather inputs' % (mod, c['name']))
                    self.assertEqual(c['res'], RACK['GQ']['res'], 'gather at the Quality res')
                if c['name'] in ('pyra', 'pyrb'):
                    self.assertEqual(c['ins'], ['ext' if c['name'] == 'pyra' else 'pyra'])
                    self.assertEqual(c['extend'], 'hold', 'edge held = the reference index clamp')
                    self.assertIsNotNone(c['dispatch'], 'one workgroup per core tile (manual dispatch)')
                if 'textureLod' in c['text'].replace(RACK['MIPG'], '') and c['name'] != 'ext':
                    self.assertEqual(c['filt'], 'mipmap', '%s.%s textureLod needs mipmap' % (mod, c['name']))
            for e in rec['exprs']:
                compile(e, '<%s expr>' % mod, 'eval')
                for p in re.findall(r"parent\(\)\.par\.(\w+)", e):
                    self.assertIn(p, names, '%s: expression uses missing par %s' % (mod, p))
            for s in stages:
                self.assertTrue(s['ops'], mod)

    def test_streak_scan_dispatch(self):
        _ns, _m, rec, _s = run_build('streak')
        run = [c for c in rec['compute'] if c['name'] == 'run'][0]
        self.assertEqual(run['dispatch'], ('1', 'me.inputs[0].height'))
        self.assertIn('local_size_x = 64', run['text'])
        shared = re.findall(r'shared\s+vec4\s+\w+\[(\d+)\]', run['text'])
        self.assertLessEqual(sum(int(k) for k in shared) * 16, 32768, 'Apple GPU: <= 32 KB shared per workgroup')

    def test_grain_constants_from_logic(self):
        ns, _m, rec, _s = run_build('grain')
        t = rec['compute'][0]['text']
        self.assertIn('HASHN = %r' % L.HASH_NORM, t)
        self.assertIn('VN2 = %r' % L.vn_norm(2), t)

    def test_chart_shader(self):
        t = RACK['chart_shader'](L)
        self.assertEqual(t.count('vec2('), 5 + 3)       # 5 lights + 3 vec2 uses in the body
        self.assertIn('%.1f' % (L.LIGHT_R ** 2), t)


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.comp')
            with open(p, 'w') as fh:
                fh.write(text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def test_rack_shaders(self):
        self._ok(TD_STUB + RACK['EXT'], 'EXT')
        self._ok(TD_STUB + RACK['PYRA'], 'PYRA')
        self._ok(TD_STUB + RACK['PYRB'], 'PYRB')
        for t in (RACK['PYRA'], RACK['PYRB']):
            shared = re.findall(r'shared\s+uvec2\s+\w+\[(\d+)\]', t)
            self.assertLessEqual(sum(int(k) for k in shared) * 8, 32768, 'Apple GPU: <= 32 KB shared per workgroup')
        self._ok(TD_STUB + RACK['chart_shader'](L), 'chart')

    def test_module_shaders(self):
        for mod in MODS:
            _ns, _m, rec, _s = run_build(mod)
            for c in rec['compute']:
                self._ok(TD_STUB + c['text'], '%s.%s' % (mod, c['name']))


# ------------------------------------------------------------------ maths
class Logic(unittest.TestCase):
    def test_hash_range_and_bits(self):
        self.assertEqual(L.lb32(0), 0)
        vals = [L.hsh(x, y, 7) for x in range(-3, 4) for y in range(-3, 4)]
        self.assertTrue(all(0.0 <= v < 1.0 for v in vals))
        self.assertEqual(len(set(vals)), len(vals))

    def test_value_noise_variance(self):
        rnd = random.Random(5)
        for dims in (2,):
            vs = [L.vnoise(rnd.uniform(0, 400), rnd.uniform(0, 400), 11) - 0.5 for _ in range(30000)]
            var = sum(v * v for v in vs) / len(vs)
            self.assertAlmostEqual(var * L.vn_norm(dims) ** 2, 1.0, delta=0.06)
        self.assertAlmostEqual(L.VN_AXIS, 26.0 / 35.0)
        # z factor at fract(z) (grain noise 3D): (1-s)^2 + s^2 integrates to 26/35
        n = 20000
        self.assertAlmostEqual(sum((1 - L.smooth((k + 0.5) / n)) ** 2 + L.smooth((k + 0.5) / n) ** 2
                                   for k in range(n)) / n, L.VN_AXIS, places=6)

    def test_chroma_norm(self):
        rnd = random.Random(1)
        for ch in (0.0, 0.3, 1.0):
            acc = 0.0
            for _ in range(20000):
                nr, ng, nb = rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1)
                nl = (nr + ng + nb) / math.sqrt(3)
                v = ((1 - ch) * nl + ch * nr) / math.sqrt((1 - ch) ** 2 + ch * ch + 2 * ch * (1 - ch) / math.sqrt(3))
                acc += v * v
            self.assertAlmostEqual(acc / 20000, 1.0, delta=0.04)
            self.assertAlmostEqual(L.chroma_norm(ch), 1 / math.sqrt((1 - ch) ** 2 + ch * ch
                                                                    + 2 * ch * (1 - ch) / math.sqrt(3)))
        self.assertAlmostEqual(L.grain_corr(0.0), 1.0)
        self.assertAlmostEqual(L.grain_corr(1.0), 0.0)

    def test_clump_weights_unit(self):
        for c in (0.0, 0.5, 1.0):
            self.assertAlmostEqual(sum(w * w for w in L.clump_weights(c)), 1.0)

    def test_knee(self):
        self.assertEqual(L.knee_w(0.5, 0.8, 0.2), 0.0)
        self.assertAlmostEqual(L.knee_excess([4.0, 4.0, 4.0], 0.8, 0.2)[0], 3.2)
        a, b = L.knee_w(0.8 - 1e-6, 0.8, 0.2), L.knee_w(0.8 + 1e-6, 0.8, 0.2)
        self.assertAlmostEqual(a, b, places=4)

    def test_level_weights(self):
        w = L.level_weights(40, 1.0)
        self.assertAlmostEqual(sum(w), 1.0)
        self.assertEqual(w.index(max(w)), round(math.log2(40 / 2)))
        self.assertEqual(L.pad_dims(1080, 1920, 2, 128), (540, 960, 640, 1024))

    def test_curves(self):
        self.assertAlmostEqual(L.hable(11.2, 11.2), 1.0)
        self.assertAlmostEqual(L.lottes(0.18, 1.6, 0.977, 8.0), 0.18, places=6)
        self.assertAlmostEqual(L.lottes(8.0, 1.6, 0.977, 8.0), 1.0, places=6)
        self.assertAlmostEqual(L.reinhard(4.0, 4.0), 1.0)
        self.assertTrue(0.0 < L.aces_fit(0.18) < L.aces_fit(1.0) <= 1.0)
        h = L.aces_hill([0.18, 0.18, 0.18])
        self.assertAlmostEqual(h[0], h[2], places=2)
        self.assertAlmostEqual(L.contrast(0.18, 1.7), 0.18)
        P = {'Exposure': 0.0, 'Contrast': 1.0, 'Curve': 'off'}
        self.assertEqual(L.tone_rgb([0.3, 0.2, 0.1], P), [0.3, 0.2, 0.1])

    def test_srgb_roundtrip(self):
        for v in (0.0, 0.002, 0.04, 0.2, 0.5, 1.0):
            self.assertAlmostEqual(L.lin2srgb(L.srgb2lin(v)), v, places=9)

    def test_bayer_and_dither(self):
        m = L.bayer8()
        self.assertEqual(sorted(v for row in m for v in row), list(range(64)))
        self.assertEqual(m[3][5], L.bayer_index(5, 3))
        self.assertEqual(L.bayer_index(13, 11), m[11 & 7][13 & 7])
        # 2x2 sub-blocks spread over the whole range (ordered dither property)
        self.assertEqual(sorted([m[0][0], m[0][1], m[1][0], m[1][1]]), [0, 16, 32, 48])
        v = (127 + 0.3) / 255.0
        self.assertAlmostEqual(L.tile_mean_bayer(v, 8) * 255, 127 + 19 / 64.0)
        self.assertEqual(L.quantize(v, 8, 0.5, 0.0) * 255, 127.0)
        for t in (0.0, 0.3, 0.99):
            q = L.quantize(0.4321, 4, t) * 15
            self.assertAlmostEqual(q, round(q))
        self.assertTrue(0.0 <= L.ign(17, 33) < 1.0)

    def test_stock(self):
        self.assertAlmostEqual(L.stock_curve(0.18, 1.0, 0.0, 1.4, 1.4, 1.6), 0.18)
        ys = [L.stock_curve(x / 100.0, 1.0, 0.0, 1.4, 1.4, 1.6) for x in range(1, 400)]
        self.assertTrue(all(b > a for a, b in zip(ys, ys[1:])))
        self.assertLess(ys[-1], 1.6)
        self.assertEqual([round(c, 9) for c in L.tech2([1, 1, 1], [1.0, 0.42, 0.16])], [1, 1, 1])
        self.assertEqual([round(c, 9) for c in L.tech3([0.5, 0.5, 0.5], 0.2)], [0.5, 0.5, 0.5])
        b = L.bleach([0.18, 0.18, 0.18], 1.0)
        self.assertAlmostEqual(b[0], b[2])
        self.assertAlmostEqual(L.cross_d([0.5, 0.5, 0.5], 1.0)[2], 0.5)

    def test_envelope(self):
        self.assertEqual(L.envelope(-1, 0.1, 0.5, 0.8), 0.0)
        self.assertAlmostEqual(L.envelope(0.05, 0.1, 0.5, 0.8), 0.5)
        self.assertEqual(L.envelope(0.3, 0.1, 0.5, 0.8), 1.0)
        self.assertAlmostEqual(L.envelope(1.0, 0.1, 0.5, 0.8), 0.5)
        self.assertEqual(L.envelope(5.0, 0.1, 0.5, 0.8), 0.0)

    def test_burn_fraction_monotone(self):
        base = {'Burnwidth': 0.06, 'Warp': 0.25, 'Posx': 0.0, 'Posy': 0.0, 'Noisescale': 3.0, 'Seed': 7}
        fr = [L.burn_fraction(dict(base, Level=lv), step=60) for lv in (0.0, 0.3, 0.6, 1.0)]
        self.assertEqual(fr[0], 0.0)
        self.assertTrue(fr[1] < fr[2] < fr[3])
        self.assertEqual(fr[3], 1.0)

    def test_spectral(self):
        ts, ws = L.spectral_weights(8)
        for c in range(3):
            self.assertAlmostEqual(sum(w[c] for w in ws), 1.0)
        self.assertEqual(L.cauchy_delta(1.0, 1.0), 1.0)
        self.assertEqual(L.cauchy_delta(0.0, 1.0), 0.0)
        self.assertAlmostEqual(L.cauchy_delta(-1.0, 1.0), -2.3275, places=4)
        self.assertEqual(L.cauchy_delta(-1.0, 0.0), -1.0)
        self.assertAlmostEqual(L.ca_shift_px(539, 959, 1080, 1920, 12, 0), 0.0, places=3)

    def test_scan(self):
        rnd = random.Random(3)
        for n, r in ((7, 0.5), (135, 0.97), (512, 0.99), (300, 1e-6)):
            e = [rnd.random() if rnd.random() < 0.2 else 0.0 for _ in range(n)]
            a, b = L.scan_brute(e, r), L.scan_chunked(e, r)
            self.assertEqual(len(a), len(b))
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y, places=7)

    def test_streak_dims(self):
        for a in (0, 30, 45, 90, -60):
            lx, ly, ds1, ds2, nx, ny = L.streak_dims(1080, 1920, a, 8, 2)
            self.assertLessEqual(nx, 512)
            self.assertGreaterEqual(nx * ds1, lx - 1e-6)
            self.assertGreaterEqual(ny * ds2, ly - 1e-6)
        self.assertEqual(L.streak_dims(1080, 1920, 0, 8, 2)[4:], (135, 960))
        self.assertEqual(L.streak_dims(1080, 1920, 90, 8, 2)[4:], (240, 540))

    def test_ghosts_forward(self):
        Lp, C, d = (0.815, 0.833), (0.5, 0.5), 0.35
        for i, u, v in L.ghost_positions(Lp, C, d, 6):
            uvf = (2 * C[0] - u, 2 * C[1] - v)
            s = (uvf[0] + (C[0] - uvf[0]) * d * i, uvf[1] + (C[1] - uvf[1]) * d * i)
            self.assertAlmostEqual(s[0], Lp[0])
            self.assertAlmostEqual(s[1], Lp[1])

    def test_star_angles(self):
        self.assertEqual(L.star_angles(6, 15.0), [15.0, 75.0, 135.0, 195.0, 255.0, 315.0])
        self.assertEqual(len(L.star_angles(4, 0.0)), 4)

    def test_chart(self):
        self.assertEqual(L.chart_pixel(540, 960, 'lights'), (4.0, 4.0, 4.0))
        self.assertEqual(L.chart_pixel(10, 10, 'lights'), (0.0, 0.0, 0.0))
        self.assertEqual(L.chart_pixel(0, 0, 'patches'), L.PATCHES[0][0])


@unittest.skipUnless(np is not None, 'numpy missing')
class Analysers(unittest.TestCase):
    def test_chart_np_matches_scalar(self):
        a = L.chart_np('lights')
        for x, y in ((540, 960), (545, 960), (547, 960), (10, 10), (200, 300)):
            self.assertEqual(tuple(float(v) for v in a[y, x]), L.chart_pixel(x, y, 'lights'))
        p = L.chart_np('patches')
        self.assertEqual(tuple(round(float(v), 6) for v in p[1900, 1070]), L.PATCHES[3][5])

    def test_pyramid_centroid(self):
        # T-129: a box mip pins a light to its coarse texel's centre; the PYR [1 3 3 1] chain keeps the centroid exact
        img = np.zeros((512, 512, 1))
        img[91, 37, 0] = 1.0
        for k, a in enumerate(L.mips_np(img, 6)):
            f = 2.0 ** k
            ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
            s_ = a[..., 0].sum()
            self.assertAlmostEqual(s_ * f * f, 1.0, places=9)                       # energy (mean-preserving)
            self.assertAlmostEqual(float((a[..., 0] * (xs + 0.5) * f).sum() / s_), 37.5, places=9)
            self.assertAlmostEqual(float((a[..., 0] * (ys + 0.5) * f).sum() / s_), 91.5, places=9)

    def test_pyr_atlas_matches_shaders(self):
        # perf lane 3: pyra / pyrb atlases; the MIPG lvlTex / _pyr resolution constants are these sizes
        for pw, ph in ((640, 1024), (384, 512), (1024, 640), (1920, 1152)):
            A = L.pyr_atlas(pw, ph)
            self.assertEqual(A['size']['pyra'], (pw // 2, ph * 15 // 16))
            self.assertEqual(A['size']['pyrb'], (pw // 16 // 2, (ph * 15 // 16) * 7 // 120))
            self.assertAlmostEqual(A['size']['pyra'][1] / ph, 0.9375)
            self.assertAlmostEqual(A['size']['pyrb'][0] / pw, 0.03125)
            self.assertAlmostEqual(A['size']['pyrb'][1] / ph, 0.0546875)
            for k in range(1, 8):                     # lvlTex y offset formulas, rows do not overlap
                o, _x, y, w, h = A[k]
                self.assertEqual(y, ph * (1 - 2.0 ** (1 - k)) if k <= 4 else ph * (0.0625 - 2.0 ** (1 - k)))
                self.assertLessEqual(y + h, A['size'][o][1])
        for t in ('0.9375', '0.03125', '0.0546875', '(1.0 - exp2(1.0 - float(k)))', '(0.0625 - exp2(1.0 - float(k)))'):
            self.assertIn(t, RACK['MIPG'])

    def test_half_gather_keeps_energy(self):
        # perf lane 3: Quality half gathers at the EXT res; energy kept, HA1 profile within its +-10 %
        ex = L.expected_numbers()
        self.assertLess(abs(ex['hal_gq_half_energy_r'] - ex['hal_energy'][0]) / ex['hal_energy'][0], 1e-3)
        self.assertLess(abs(ex['hal_gq_half_r_at_570_960'] / ex['hal_r_at_570_960'] - 1.0), 0.03)
        self.assertGreater(ex['hal_gq_half_peak_ratio'], 0.93)

    def test_ext_energy(self):
        img = L.chart_np('lights', 4.0)
        e = L.ext_np(img, 2, 0.8, 0.2)
        self.assertEqual(e.shape, (960, 540, 3))
        full = L.knee_excess([4.0] * 3, 0.8, 0.2)[0] * float((img[..., 0] > 0).sum())
        self.assertLess(abs(e[..., 0].sum() * 4 - full) / full, 0.15)       # edge texels are knee'd averages

    def test_profile_and_ring(self):
        h, w = 400, 400
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
        img = np.zeros((h, w, 3))
        img[200, :, :] = np.exp(-np.abs(xs[200] - 200) / 50.0)[:, None]
        pr = L.an_profile(img, 200, 200, 0.0, [50, 100])
        self.assertAlmostEqual(pr[1] / pr[0], math.exp(-1.0), places=6)
        ang = np.degrees(np.arctan2(ys - 200, xs - 200)) % 360
        star = np.zeros((h, w))
        for a in L.star_angles(6, 15.0):
            star += np.exp(-((((ang - a) + 180) % 360 - 180) / 2.0) ** 2)
        img2 = np.repeat(star[..., None], 3, axis=2)
        pk, _mx, _md = L.an_ring_peaks(img2, 200, 200, 60)
        self.assertEqual(len(pk), 6)
        for p_, a in zip(sorted(pk), L.star_angles(6, 15.0)):
            self.assertLess(abs(p_ - a), 1.0)

    def test_dither_analysers(self):
        v = (127 + 0.3) / 255.0
        a = np.zeros((16, 64, 3))
        for y in range(16):
            for x in range(64):
                a[y, x] = L.quantize(v, 8, (L.bayer_index(x, y) + 0.5) / 64.0)
        self.assertEqual(L.an_levels(a, 0, 0, 64, 16), 0.0)
        for t in L.an_tile_means(a, 0, 0, 8, 8):
            self.assertAlmostEqual(t * 255, 127 + 19 / 64.0, places=9)


class Doc(unittest.TestCase):
    def test_doc_numbers(self):
        if not os.path.exists(DOC):
            self.fail('docs/builds/fx_film.md missing')
        doc = open(DOC).read()
        for k, v in L.expected_numbers().items():
            self.assertIn('%s %s' % (k, v), doc, k)


if __name__ == '__main__':
    unittest.main()
