"""Offline tests for FX_analog modules 'vhs' and 'signalloss' (builders/fx_analog_vhs.py, fx_analog_signalloss.py,
fx_analog_signal_logic.py). No TD needed. Run:
    cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_analog_vhs.py'
StageLab parity reads ../stagelab (read-only; skipped when absent). The GLSL check compiles every pass with glslc
(OpenGL target) against stubs of TD's compute globals: a syntax/type check, NOT a TD compile and NOT a parity proof
(that is LIVE CHECK V3 / S2-S5 in docs/builds/fx_analog_vhs.md / fx_analog_signalloss.md)."""
import math
import os
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
STAGELAB = os.path.join(os.path.dirname(REPO), 'stagelab')
sys.path.insert(0, BUILDERS)
import fx_analog_signal_logic as L  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None


def module_ns(name):
    ns = {'HERE': BUILDERS}
    with open(os.path.join(BUILDERS, 'fx_analog_%s.py' % name)) as fh:
        exec(compile(fh.read(), 'fx_analog_%s.py' % name, 'exec'), ns)
    return ns


VHS = module_ns('vhs')
SL = module_ns('signalloss')
PAR_NAME = re.compile(r'^[A-Z][a-z0-9]*$')


def pars_of(M):
    return dict((p[0], p) for _page, pars in M['PAGES'] for p in pars)


class Spec(unittest.TestCase):
    def check(self, M):
        names = [p[0] for _pg, pars in M['PAGES'] for p in pars]
        self.assertEqual(len(names), len(set(names)), 'duplicate par')
        for n in names:
            self.assertRegex(n, PAR_NAME)
        self.assertEqual(M['PAGES'][0][1][0][0], 'Amount')
        P = pars_of(M)
        pages = [pg for pg, _ in M['PAGES']]
        for pg in M['PANEL_PAGES']:
            self.assertIn(pg, pages)
        slots = [s for s, _n, _v in M['PRESETS']]
        self.assertEqual(len(slots), len(set(slots)))
        for _s, _n, vals in M['PRESETS']:
            for k, v in vals.items():
                self.assertIn(k, P, k)
                style, o = P[k][1], P[k][3]
                if style == 'Menu':
                    self.assertTrue(isinstance(v, int) and 0 <= v < len(o['names']), (k, v))
                elif style in ('Int', 'Toggle'):
                    self.assertIsInstance(v, int, k)
                else:
                    self.assertIsInstance(v, float, k)
        for st, pars in [(s, p) for s, p in M['PAGES']]:
            for p in pars:
                if p[1] == 'Menu':
                    self.assertIn(p[2], p[3]['names'])
                    self.assertEqual(len(p[3]['names']), len(p[3]['labels']))

    def test_vhs(self):
        self.check(VHS)

    def test_signalloss(self):
        self.check(SL)

    def test_uniform_expressions_parse(self):
        for M in (VHS, SL):
            for _g, us in M['UNIFORMS'].items():
                self.assertLessEqual(len(us), 9)
                for un, ex in us:
                    self.assertRegex(un, r'^u[A-Z]$')
                    self.assertEqual(len(ex), 4)
                    for e in ex:
                        compile(e, un, 'eval')
        for e in (L.vhs_active_expr(), L.signalloss_active_expr(), L.NOISE_STEP_EXPR, L.raster_expr('vw')):
            compile(e, 'x', 'eval')

    def test_state_pars_cover_pulses(self):
        for M, tg in ((VHS, ['Glitchtime', 'Glitchcount']), (SL, ['Hittime', 'Offtime', 'Ontime'])):
            P = pars_of(M)
            for n in tg:
                self.assertIn(n, P)


def _fake_parent(vals):
    class Par:
        def __init__(self, v, menu=None):
            self.v, self.menuIndex = v, menu

        def eval(self):
            return self.v
    ns = types.SimpleNamespace(**dict((k, Par(v)) for k, v in vals.items()))
    return lambda: types.SimpleNamespace(par=ns)


class Expressions(unittest.TestCase):
    def ev(self, e, vals, now):
        return eval(e, {'parent': _fake_parent(vals), 'absTime': types.SimpleNamespace(seconds=now)})

    def test_vhs_active(self):
        e = L.vhs_active_expr()
        self.assertEqual(self.ev(e, {'Amount': 0.0, 'Glitchtime': -1000.0}, 50.0), 0)
        self.assertEqual(self.ev(e, {'Amount': 0.3, 'Glitchtime': -1000.0}, 50.0), 1)
        self.assertEqual(self.ev(e, {'Amount': 0.0, 'Glitchtime': 49.0}, 50.0), 1)      # 1.0 s into the burst
        self.assertEqual(self.ev(e, {'Amount': 0.0, 'Glitchtime': 48.0}, 50.0), 0)      # 2.0 s > 1.842 s

    def test_signalloss_active(self):
        e = L.signalloss_active_expr()
        base = {'Amount': 0.0, 'Powerphase': -1.0, 'Hittime': -1000.0, 'Hitdecay': 0.6, 'Offtime': -1000.0,
                'Ontime': -1000.0, 'Warmup': 1.2}
        self.assertEqual(self.ev(e, base, 100.0), 0)
        self.assertEqual(self.ev(e, dict(base, Hittime=99.0), 100.0), 1)               # 1 s < 0.6 ln 100 = 2.76
        self.assertEqual(self.ev(e, dict(base, Hittime=97.0), 100.0), 0)
        self.assertEqual(self.ev(e, dict(base, Offtime=10.0), 100.0), 1)               # off (held black)
        self.assertEqual(self.ev(e, dict(base, Offtime=10.0, Ontime=99.5), 100.0), 1)  # warming up
        self.assertEqual(self.ev(e, dict(base, Offtime=10.0, Ontime=90.0), 100.0), 0)
        self.assertEqual(self.ev(e, dict(base, Powerphase=0.3), 100.0), 1)

    def test_raster_lambda_matches_raster(self):
        for w, h in ((1080, 1920), (1920, 1080), (4537, 1745), (474, 160), (7488, 2880), (100, 37), (3, 3)):
            for lines in L.VHS_LINES:
                for axis in (0, 1):
                    R = L.raster(w, h, lines, axis)
                    tup = eval(L.RASTER_LAMBDA + '(%d, %d, %d, %d)' % (w, h, int(lines), axis))
                    self.assertEqual(tup, (R['pitch'], R['vw'], R['vh'], R['tx'], R['ty']), (w, h, lines, axis))


class VhsLogic(unittest.TestCase):
    def test_stagelab_raster_numbers(self):
        # stagelab effects/vhs/manifest.yaml limits: at 4537x1745 Lines 240/480/576 = 488x250, 852x437, 1135x582
        got = [(L.raster(4537, 1745, n)['vw'], L.raster(4537, 1745, n)['vh']) for n in L.VHS_LINES]
        self.assertEqual(got, [(488, 250), (852, 437), (1135, 582)])

    def test_build_size_numbers(self):     # docs/builds/fx_analog_vhs.md V2
        R = dict((n, L.raster(1080, 1920, n)) for n in L.VHS_LINES)
        self.assertEqual([(R[n]['vw'], R[n]['vh'], R[n]['pitch']) for n in L.VHS_LINES],
                         [(101, 240, 8), (203, 480, 4), (270, 640, 3)])
        Ry = dict((n, L.raster(1080, 1920, n, 1)) for n in L.VHS_LINES)
        self.assertEqual([(Ry[n]['vw'], Ry[n]['vh'], Ry[n]['pitch']) for n in L.VHS_LINES],
                         [(288, 216, 5), (480, 360, 3), (480, 360, 3)])

    def test_noise_frames(self):
        self.assertEqual([L.noise_frames(f) for f in (24, 25, 30, 50, 60)], [1, 2, 2, 3, 3])

    def test_dropout_loop(self):
        a = [L.dropout_index(s, 7, 0.0) for s in range(96)]
        self.assertEqual(a[:48], a[48:])
        b = [L.dropout_index(s, 7, 1.0) for s in range(96)]
        self.assertEqual(len(set(b)), 96)

    def test_glitch(self):
        self.assertAlmostEqual(L.GLITCH_END, 1.8421, places=3)
        self.assertEqual(L.glitch_envelope(-0.1), 0.0)
        self.assertEqual(L.glitch_envelope(1.9), 0.0)
        self.assertAlmostEqual(L.glitch_envelope(0.4), math.exp(-1), places=9)
        for n in range(20):
            self.assertTrue(0.1 <= L.glitch_pos(n, 3, 0.0) <= 0.9)
        self.assertNotEqual(L.glitch_pos(1, 3, 0.0), L.glitch_pos(1, 4, 0.0))

    def test_band_loop_period(self):
        self.assertAlmostEqual(L.band_loop(1.0, 5), L.band_loop(10.0, 5), places=9)
        self.assertTrue(0.08 <= L.band_loop(2.2, 5) <= 0.92)

    def test_pcg_is_32bit_and_spread(self):
        vals = [L.pcg(i) for i in range(1000)]
        self.assertTrue(all(0 <= v <= L.U32 for v in vals))
        self.assertEqual(len(set(vals)), 1000)
        hs = [L.hh(i, -i, 9) for i in range(2000)]
        self.assertTrue(0.45 < sum(hs) / len(hs) < 0.55)

    def test_luma_weights_are_repeated_121(self):
        for n in range(1, 8):
            k = [1.0]
            for _ in range(n):
                k = _conv(k, [0.25, 0.5, 0.25])
            self.assertEqual(len(k), 2 * n + 1)
            for a, b in zip(k, L.luma_weights(n)):
                self.assertAlmostEqual(a, b, places=12)

    def test_chroma_weights_are_cascaded_exponentials(self):
        for tau in (0.3, 1.5, 5.0, 8.5):
            r = math.exp(-1.0 / tau)
            e = [(1 - r) * r ** k for k in range(600)]
            for g in range(1, 6):
                k = [1.0]
                for _ in range(g):
                    k = _conv(k, e)[:600]
                k = k[:L.VHS_CHROMA_TAPS]
                s = sum(k)
                for a, b in zip([x / s for x in k], L.chroma_weights(tau, g)):
                    self.assertAlmostEqual(a, b, places=10)

    def test_tape_coords_roundtrip(self):
        w, h = 7, 5
        for axis in (0, 1):
            seen = set()
            for x in range(w):
                for y in range(h):
                    s, l = L.to_tape(x, y, w, h, axis)
                    S, Ln = L.tape_dims(w, h, axis)
                    self.assertTrue(0 <= s < S and 0 <= l < Ln)
                    self.assertEqual(L.to_pix(s, l, w, h, axis), (x, y))
                    seen.add((s, l))
            self.assertEqual(len(seen), w * h)


def _conv(a, b):
    out = [0.0] * (len(a) + len(b) - 1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            out[i + j] += x * y
    return out


class SignallossLogic(unittest.TestCase):
    def test_power_state(self):
        ps = L.power_state
        self.assertEqual(ps(100, -1000, -1000, 0.45, 1.2, True), (0, 0.0))
        m, k = ps(100.2, 100.0, -1000, 0.45, 1.2, True)
        self.assertEqual(m, 1)
        self.assertAlmostEqual(k, 0.2 / 0.45)
        self.assertEqual(ps(101, 100.0, -1000, 0.45, 1.2, True), (2, 1.0))
        self.assertEqual(ps(101, 100.0, -1000, 0.45, 1.2, False), (0, 0.0))
        self.assertEqual(ps(101, 100.0, 100.5, 0.45, 1.2, True)[0], 3)
        self.assertEqual(ps(102, 100.0, 100.5, 0.45, 1.2, True), (0, 0.0))
        self.assertEqual(ps(5, -1000, -1000, 0.45, 1.2, True, 0.3), (1, 0.3))
        self.assertEqual(ps(5, -1000, -1000, 0.45, 1.2, True, 1.0), (2, 1.0))

    def test_collapse_numbers(self):       # docs/builds/fx_analog_signalloss.md S6
        sx, sy, g, wh = L.collapse(0.25, 1080, 1920, 1.5)
        self.assertEqual(sx, 1.0)
        self.assertAlmostEqual(sy, 0.5 * (1 + 4.0 / 1920), places=9)
        self.assertAlmostEqual(g, 1.25)
        self.assertEqual(L.collapse_lit(1920, sy), 962)
        sx, sy, g, wh = L.collapse(0.65, 1080, 1920, 1.5)
        self.assertEqual(L.collapse_lit(1920, sy), 4)
        self.assertEqual(L.collapse_lit(1080, sx), 544)
        sx, sy, g, wh = L.collapse(0.9, 1080, 1920, 1.5)
        self.assertEqual((L.collapse_lit(1080, sx), L.collapse_lit(1920, sy)), (8, 4))
        self.assertAlmostEqual(g, 0.75)
        self.assertEqual(L.collapse(1.0, 1080, 1920, 1.5)[2], 0.0)
        self.assertEqual(L.warmup(0.0), (0.55, 0.0))
        self.assertEqual(L.warmup(1.0), (1.0, 1.0))

    def test_vroll_numbers(self):          # S4: Vpos 0.25, Vbar 0.1 at 1920 lines
        rows = [L.vroll_line(l, 1920, 0.25, 0.1) for l in range(1920)]
        bar = [l for l, r in enumerate(rows) if r is None]
        self.assertEqual((bar[0], bar[-1], len(bar)), (1440, 1631, 192))
        self.assertEqual(rows[0], 480)
        self.assertEqual(rows[1439], 1919)
        self.assertEqual(rows[1632], 0)
        self.assertEqual(L.vroll_line(7, 1920, 0.0, 0.1), 7)

    def test_slant(self):
        self.assertEqual(L.slant_src(10, 0, 1080, 0.25), 10)
        self.assertEqual(L.slant_src(10, 4, 1080, 0.25), 9)
        self.assertEqual(L.slant_src(0, 8, 1080, 0.25), 1078)
        self.assertEqual(L.slant_src(5, 2, 1080, 0.25), 5)       # 5.0 exactly: floor keeps 5

    def test_hit(self):
        self.assertAlmostEqual(L.envelope_end(0.6), 0.6 * math.log(100))
        self.assertEqual(L.hit_envelope(3.0, 0.6), 0.0)


@unittest.skipIf(np is None, 'numpy missing')
class Reference(unittest.TestCase):
    def img(self, h=96, w=64, seed=3):
        rng = np.random.default_rng(seed)
        a = rng.random((h, w, 4)).astype(np.float32)
        a[..., 3] = 1.0
        return a

    def test_tape_of_matches_to_tape(self):
        a = self.img(5, 7)
        for axis in (0, 1):
            T = L.tape_of(a, axis)
            for x in range(7):
                for y in range(5):
                    s, l = L.to_tape(x, y, 7, 5, axis)
                    self.assertTrue(np.array_equal(T[l, s], a[y, x]))
            self.assertTrue(np.array_equal(L.pix_of(T, axis), a))

    def test_encode_constant_is_yiq(self):
        a = np.zeros((60, 40, 4), np.float32)
        a[...] = (0.8, 0.2, 0.1, 1.0)
        e = L.ref_vhs_encode(a, '240').astype(np.float64)
        M = np.array(L.RGB2YIQ)
        self.assertLess(np.abs(e[..., :3] - M @ np.array([0.8, 0.2, 0.1])).max(), 1e-3)

    def test_chroma_is_causal(self):
        enc = np.zeros((4, 120, 4), np.float16)
        enc[..., 1] = 0.0
        enc[:, 40:60, 1] = 0.5                           # an I (orange) bar at samples 40..59
        s = L.ref_vhs_signal(enc, sharpen=0.0, shift=1.5, bleed=0.6).astype(np.float64)
        self.assertEqual(np.abs(s[:, :41, 1]).max(), 0.0)    # nothing left of the bar (+ shift)
        self.assertGreater(s[0, 41, 1], 0.0)
        self.assertGreater(s[0, 70, 1], 0.0)                  # trails right past the bar end

    def test_clean_amount0_is_input(self):
        a = self.img()
        o = L.ref_vhs_clean(a, amount=0.0)
        self.assertEqual(np.abs(o - a).max(), 0.0)

    def test_clean_changes_and_axis(self):
        a = self.img()
        for axis in (0, 1):
            o = L.ref_vhs_clean(a, amount=1.0, axis=axis)
            self.assertEqual(o.shape, a.shape)
            self.assertGreater(np.abs(o - a).mean(), 0.02)
            self.assertTrue(np.isfinite(o).all())

    def test_sl_vhold_and_slant(self):
        a = self.img(40, 30)
        o = L.ref_sl_vhold(a, 0.0, 0.1)
        self.assertEqual(np.abs(o - a).max(), 0.0)
        o = L.ref_sl_vhold(a, 0.25, 0.1)
        self.assertTrue(np.array_equal(o[0, :, :3], a[10, :, :3]))
        self.assertTrue(np.allclose(o[30:34, :, :3], L.SL_BAR_LEVEL))
        self.assertEqual(np.abs(L.ref_sl_slant(a, 0.0) - a).max(), 0.0)
        o = L.ref_sl_slant(a, 1.0)
        self.assertTrue(np.array_equal(o[3, 5, :3], a[3, 2, :3]))


@unittest.skipUnless(os.path.isdir(STAGELAB), 'stagelab repo not present')
class StageLabParity(unittest.TestCase):
    """Same control names / ranges / defaults / recipes as JZB_Lofi_VHS (read-only)."""

    def manifest(self):
        rows = []
        with open(os.path.join(STAGELAB, 'effects', 'vhs', 'manifest.yaml')) as fh:
            for line in fh:
                m = re.match(r'\s*- \{name: ([^,]+), type: (\w+)(.*)\}', line)
                if m:
                    d = dict(kv.split(': ', 1) for kv in re.findall(r'(\w+: [^,]+)', m.group(3)))
                    rows.append((m.group(1).strip(), m.group(2), d))
        return rows

    def test_controls(self):
        P = pars_of(VHS)
        rows = self.manifest()
        self.assertGreaterEqual(len(rows), 17)
        for name, typ, d in rows:
            td = name.replace(' ', '').capitalize()
            self.assertIn(td, P, name)
            style, default, o = P[td][1], P[td][2], P[td][3]
            if style != 'Pulse':
                self.assertEqual(o.get('label', td), name)
            want = {'float': 'Float', 'event': 'Pulse', 'option': 'Menu', 'bool': 'Toggle', 'integer': 'Int'}[typ]
            self.assertEqual(style, want, name)
            if typ in ('float', 'integer'):
                self.assertEqual((float(o['min']), float(o['max'])), (float(d['min']), float(d['max'])), name)
                if name != 'Amount':                  # TD modules default to Amount 1 (template); Arena 0
                    self.assertEqual(float(default), float(d['default']), name)
            if typ == 'bool':
                self.assertEqual(bool(default), d['default'].strip() == 'true', name)
            if typ == 'option':
                self.assertEqual(default, d['default'].strip().strip('"'))

    def test_recipes(self):
        with open(os.path.join(STAGELAB, 'presets', 'JZB_Lofi_VHS.yaml')) as fh:
            text = fh.read()
        recipes = {}
        cur = None
        for line in text.splitlines():
            m = re.match(r'\s*- name: "(.+)"', line)
            if m:
                cur = recipes.setdefault(m.group(1).lower(), {})
                continue
            m = re.match(r'\s*"(.+)": (.+)', line)
            if m and cur is not None:
                cur[m.group(1)] = m.group(2).strip().strip('"')
        ours = dict((n, v) for _s, n, v in VHS['PRESETS'])
        P = pars_of(VHS)
        self.assertEqual(len(recipes), 4)
        for rname, vals in recipes.items():
            self.assertIn(rname, ours)
            for k, v in vals.items():
                td = k.replace(' ', '').capitalize()
                got = ours[rname][td]
                if P[td][1] == 'Menu':
                    got = P[td][3]['names'][got]
                    self.assertEqual(got, v, (rname, k))
                elif P[td][1] == 'Toggle':
                    self.assertEqual(bool(got), v == 'true', (rname, k))
                else:
                    self.assertAlmostEqual(float(got), float(v), msg=(rname, k))


STUB = """#version 460
layout(binding = 0) uniform sampler2D sTD2DInputs[4];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f, binding = 0) uniform image2DArray mTDComputeOutputs[1];
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
            self.assertEqual(r.returncode, 0, name + ': ' + r.stderr)

    def test_all(self):
        for M, tag in ((VHS, 'vhs'), (SL, 'signalloss')):
            for n, text in M['SHADERS'].items():
                self.assertTrue(all(ord(ch) < 128 for ch in text), n)
                self._ok('%s_%s' % (tag, n), text)


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
        self.seq = types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=1))
        self.children = {}
        self.path = '/fake/' + name

    def op(self, n):
        return self.children.get(n)

    def create(self, cls, n):
        o = _Op(cls.__name__, n)
        self.children[n] = o
        return o


class DryBuild(unittest.TestCase):
    """build(m, H) against a fake TD: every op / par / wire the module makes, no TD. Catches name typos only."""

    def run_build(self, name):
        cls = dict((c, type(c, (), {})) for c in ('inTOP', 'outTOP', 'glslTOP', 'textDAT', 'cacheTOP', 'switchTOP',
                                                    'constantTOP', 'textTOP', 'parameterexecuteDAT'))
        ns = {'HERE': BUILDERS, 'ParMode': types.SimpleNamespace(EXPRESSION='e', CONSTANT='c')}
        ns.update(cls)
        with open(os.path.join(BUILDERS, 'fx_analog_%s.py' % name)) as fh:
            exec(fh.read(), ns)

        def mk(c, k, n):
            o = c.op(n)
            return o if o is not None and o.OPType == k.__name__ else c.create(k, n)

        def expr(par, e):
            par.expr, par.mode = e, 'e'

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

        H = {'mk': mk, 'expr': expr, 'sd': lambda o: None, 'compute': compute, 'uniforms': uniforms}
        m = _Op('baseCOMP', name + '1')
        stages = ns['build'](m, H)
        for s in stages:
            for n in s['ops']:
                if not n.endswith('_compute'):
                    self.assertIn(n, m.children, n)
        out = m.op('out1')
        self.assertEqual(out.inputConnectors[0].connections[0].owner.name, 'out_sel')
        return m

    def test_vhs(self):
        m = self.run_build('vhs')
        fx = m.op('fx')
        self.assertEqual([fx.inputConnectors[i].connections[0].owner.name for i in range(4)],
                         ['in1', 'sig', 'prev_src', 'stamp'])
        self.assertIn('Glitch', m.op('pulses').text)

    def test_signalloss(self):
        m = self.run_build('signalloss')
        fx = m.op('fx')
        self.assertEqual([fx.inputConnectors[i].connections[0].owner.name for i in range(4)],
                         ['in1', 'prev_src', 'stamp', 'osd_src'])


class Ascii(unittest.TestCase):
    def test_files_ascii(self):
        for f in ('fx_analog_vhs.py', 'fx_analog_signalloss.py', 'fx_analog_signal_logic.py'):
            with open(os.path.join(BUILDERS, f), 'rb') as fh:
                self.assertTrue(all(b < 128 for b in fh.read()), f)


if __name__ == '__main__':
    unittest.main()
