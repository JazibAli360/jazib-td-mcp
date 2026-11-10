"""Offline tests for the FX_synth rack + modules: builders/fx_synth.py, builders/fx_synth_<module>.py,
builders/fx_synth_logic.py (numpy references), builders/glsl/fx_synth_*.glsl. No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_synth.py'
GLSL checks compile with glslc (OpenGL target) against stubs of the TD built-ins: a syntax/type check, NOT a TD compile
(LIVE CHECK 1 in docs/builds/fx_synth.md). The fake-TD build runs each module's build(m, H) on stand-in ops and checks
wiring, uniform names vs shader declarations and that every expression parses and names existing pars."""
import ast
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
B = os.path.join(REPO, 'builders')
GLSL = os.path.join(B, 'glsl')
sys.path.insert(0, B)
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import fx_synth_logic as L  # noqa: E402
import fx_time_testkit as K  # noqa: E402

RACK = {}
with open(os.path.join(B, 'fx_synth.py')) as _fh:
    exec(compile(_fh.read(), 'fx_synth.py', 'exec'), RACK)
MODULES = RACK['MODULES']
RNG = np.random.default_rng(7)


def load(module):
    ns = {'HERE': B}
    with open(os.path.join(B, 'fx_synth_%s.py' % module)) as fh:
        exec(compile(fh.read(), 'fx_synth_%s.py' % module, 'exec'), ns)
    return ns


MODS = dict((m, load(m)) for m in MODULES)


def glsl(stem):
    with open(os.path.join(GLSL, 'fx_synth_%s.glsl' % stem)) as fh:
        return fh.read()


def pars(M):
    return dict((n, (s, d, o)) for _pg, ps in M['PAGES'] for n, s, d, o in ps)


def declared(text):
    return re.findall(r'^uniform vec4 (\w+);', text, re.M)


STUB_VERT = """#version 460
in vec3 P;
int TDInstanceID() { return gl_InstanceID; }
"""
STUB_PIXEL = """#version 460
void TDCheckDiscard() {}
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""


def compile_stage(text, ext):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.' + ext)
        with open(p, 'w') as fh:
            fh.write(text)
        r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                            '-o', os.devnull, p], capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:3000]


# ------------------------------------------------------------------ fake TD (module build on stand-ins)
class FakePar(object):
    def __init__(self):
        self.val, self.expr, self.mode = None, None, None
        self.menuNames = ['aa1x', 'aa2x']


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
        self.par = FakePars()
        self.inputConnectors = [FakeConn() for _ in range(3)]
        self.seq = types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=0),
                                         sampler=types.SimpleNamespace(numBlocks=0))
        self.text, self.comment, self.dock, self.U = '', '', None, []
        self.ops, self.render, self.display = {}, False, False

    @property
    def children(self):
        return list(self.ops.values())

    def op(self, n):
        return self.ops.get(n)

    def create(self, cls, name):
        o = FakeOp(cls.__name__, name, self)
        self.ops[name] = o
        return o


TD_CLASSES = ['inTOP', 'outTOP', 'glslTOP', 'textDAT', 'switchTOP', 'feedbackTOP', 'selectTOP', 'transformTOP', 'textTOP',
              'cacheTOP', 'glslMAT', 'geometryCOMP', 'gridSOP', 'cameraCOMP', 'renderTOP', 'noiseTOP']


def run_build(module):
    rec = {'compute': {}, 'exprs': []}
    ns = {'HERE': B}
    for c in TD_CLASSES:
        ns[c] = type(c, (), {})
    with open(os.path.join(B, 'fx_synth_%s.py' % module)) as fh:
        exec(compile(fh.read(), 'fx_synth_%s.py' % module, 'exec'), ns)
    m = FakeOp('baseCOMP', module)

    def mk(comp, cls, name):
        if name not in comp.ops:
            comp.ops[name] = FakeOp(cls.__name__, name, comp)
        return comp.ops[name]

    def expr(par, e):
        par.expr = e
        rec['exprs'].append(e)

    def compute(comp, name, text, ins, res=None, fmt='useinput'):
        assert len(ins) <= 3, 'GLSL TOP has 3 input connectors (T-84): %s' % name
        g = mk(comp, ns['glslTOP'], name)
        g.text = text
        mk(comp, ns['textDAT'], name + '_compute')
        for k, s in enumerate(ins):
            g.inputConnectors[k].connect(s)
        rec['compute'][name] = {'text': text, 'ins': [s.name for s in ins], 'fmt': fmt, 'op': g}
        return g

    def uniforms(g, U):
        g.U = list(U)
        rec['exprs'].extend(e for _n, ex in U for e in ex)

    H = {'mk': mk, 'expr': expr, 'sd': lambda o: None, 'compute': compute, 'uniforms': uniforms}
    stages = ns['build'](m, H)
    return ns, m, rec, stages


class Rack(unittest.TestCase):
    def test_rack(self):
        self.assertEqual(RACK['NAME'], 'FX_synth')
        self.assertEqual(RACK['FIRST'], ('colorize1', 'colorize'))
        for m in MODULES:
            self.assertTrue(os.path.isfile(RACK['module_file'](m)), m)
        self.assertEqual(RACK['plan_chain']([{'name': 'b', 'order': 2}, {'name': 'a', 'order': 1}]), ['a', 'b'])
        self.assertEqual(RACK['COLS'], ['name', 'module', 'enabled', 'order', 'mix'])

    def test_files_ascii_and_td_rules(self):
        names = ['fx_synth.py', 'fx_synth_logic.py'] + ['fx_synth_%s.py' % m for m in MODULES]
        for n in names:
            K.check_td_rules(self, K.source(n))
        for n in os.listdir(GLSL):
            if n.startswith('fx_synth_'):
                with open(os.path.join(GLSL, n), 'rb') as fh:
                    fh.read().decode('ascii')


class Contract(unittest.TestCase):
    def test_modules(self):
        for name, M in MODS.items():
            with self.subTest(module=name):
                self.assertEqual(M['MODULE'], name)
                names = [n for _pg, ps in M['PAGES'] for n, *_ in ps]
                self.assertEqual(names[0], 'Amount')
                self.assertEqual(len(names), len(set(names)))
                for n in names:
                    self.assertRegex(n, r'^[A-Z][a-z0-9]*$')
                self.assertTrue(set(M['PANEL_PAGES']) <= set(p for p, _ in M['PAGES']))
                P = pars(M)
                for n, (style, default, o) in P.items():
                    if style == 'Menu':
                        self.assertIn(default, o['names'], n)
                        self.assertEqual(len(o['names']), len(o['labels']), n)
                    if style in ('Float', 'Int'):
                        self.assertLess(o['min'], o['max'], n)
                self.assertTrue(3 <= len(M['PRESETS']) <= 5)
                slots = set()
                for slot, pname, vals in M['PRESETS']:
                    self.assertNotIn(slot, slots)
                    slots.add(slot)
                    self.assertEqual(vals.get('Amount'), 1.0, pname)
                    for k, v in vals.items():
                        self.assertIn(k, P, '%s preset %s: unknown par %s' % (name, pname, k))
                        if P[k][0] == 'Menu':
                            self.assertTrue(0 <= v < len(P[k][2]['names']), (pname, k, v))

    def test_uniforms_match_shaders(self):
        for name, M in MODS.items():
            for pas, stem in M['SHADERS'].items():
                if pas == 'mat_pixel':
                    self.assertTrue(set(declared(glsl(stem))) <= set(u for u, _ in M['uniforms']('mat')))
                    continue
                with self.subTest(module=name, pas=pas):
                    U = M['uniforms'](pas)
                    self.assertEqual([u for u, _ in U], declared(glsl(stem)))
                    for _u, ex in U:
                        self.assertEqual(len(ex), 4)

    def test_logic_defaults_match_pars(self):
        D = {'colorize': L.CZ_DEFAULTS, 'bands': L.BD_DEFAULTS, 'keyer': L.KY_DEFAULTS, 'ruttetra': L.RT_DEFAULTS,
             'scanimate': L.SC_DEFAULTS, 'vfeedback': L.VF_DEFAULTS, 'modulate': L.MD_DEFAULTS}
        for name, M in MODS.items():
            P = pars(M)
            for k, v in D[name].items():
                with self.subTest(module=name, par=k):
                    self.assertIn(k, P)
                    style, default, o = P[k]
                    if style == 'Menu':
                        default = o['names'].index(default)
                    if style == 'Toggle':
                        default = int(default)
                    self.assertEqual(default, v)


class FakeBuild(unittest.TestCase):
    def test_build_all(self):
        for name in MODULES:
            with self.subTest(module=name):
                ns, m, rec, stages = run_build(name)
                P = pars(MODS[name])
                for e in rec['exprs']:
                    ast.parse(e, mode='eval')
                    for ref in re.findall(r'parent\(\d?\)\.par\.(\w+)', e):
                        self.assertIn(ref, P, 'expression references unknown par %s: %s' % (ref, e))
                for pas, c in rec['compute'].items():
                    self.assertIn(pas, ns['SHADERS'], pas)
                    self.assertEqual([u for u, _ in c['op'].U], declared(c['text']), pas)
                sel, out1 = m.op('out_sel'), m.op('out1')
                self.assertEqual(out1.inputConnectors[0].src, sel)
                self.assertEqual(sel.inputConnectors[0].src.name, 'in1')
                self.assertIn('Amount', sel.par.index.expr)
                for st in stages:
                    for o in st['ops']:
                        self.assertIsNotNone(m.op(o), '%s stage op %s missing' % (name, o))
                fb = m.op('fb')
                if fb is not None and fb.par.top.val is not None:
                    self.assertIsNotNone(m.op(fb.par.top.val))

    def test_ruttetra_render_wiring(self):
        _ns, m, rec, _st = run_build('ruttetra')
        geo, mat = m.op('geo'), m.op('mat')
        self.assertEqual(geo.op('ribbon').OPType, 'gridSOP')
        self.assertEqual(geo.op('ribbon').par.rows.val, 2)
        self.assertIn('parent(2).par.Samples', geo.op('ribbon').par.cols.expr)
        self.assertEqual(mat.par.vec0name.val, 'uA')
        self.assertEqual(mat.par.sampler0top.val, 'in1')
        self.assertEqual(rec['compute']['post']['ins'], ['render', 'fb'])
        self.assertEqual(rec['compute']['outc']['ins'], ['in1', 'post'])
        self.assertEqual(m.op('render').par.geometry.val, 'geo')

    def test_state_formats(self):
        _ns, _m, rec, _st = run_build('vfeedback')
        self.assertEqual(rec['compute']['loop']['fmt'], 'rgba16float')
        self.assertEqual(rec['compute']['loop']['ins'], ['in1', 'fb', 'stamp'])
        self.assertEqual(rec['compute']['mix']['fmt'], 'useinput')
        _ns, _m, rec, _st = run_build('scanimate')
        self.assertEqual(rec['compute']['trail']['ins'], ['warp', 'fb', 'stamp'])
        self.assertEqual(rec['compute']['look']['ins'], ['in1', 'trail'])


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    COMPUTE = ['colorize', 'bands', 'keyer', 'rutt_post', 'rutt_outc', 'stamp', 'scan_warp', 'scan_trail',
               'scan_look', 'vf_loop', 'mix', 'modulate']

    def test_compute(self):
        for stem in self.COMPUTE:
            with self.subTest(shader=stem):
                ok, err = K.glslc(glsl(stem))
                self.assertTrue(ok, err)

    def test_mat(self):
        ok, err = compile_stage(STUB_VERT + glsl('rutt_vert'), 'vert')
        self.assertTrue(ok, err)
        ok, err = compile_stage(STUB_PIXEL + glsl('rutt_pixel'), 'frag')
        self.assertTrue(ok, err)

    def test_glslc_really_checks(self):
        ok, _err = K.glslc(glsl('mix').replace('vec4 a =', 'vec3 a ='))
        self.assertFalse(ok)


# ------------------------------------------------------------------ maths
def ramp_img(W=64, H=8):
    x = (np.arange(W) + 0.5) / W
    g = np.broadcast_to(x[None, :, None], (H, W, 3))
    return L.to4(np.array(g))


class Colorize(unittest.TestCase):
    def test_identity_and_amount0(self):
        img = L.to4(RNG.random((12, 10, 3)))
        P = dict(Source=1, Function=3, Phaser=0.0, Phaseg=0.0, Phaseb=0.0)
        self.assertTrue(np.allclose(L.colorize(img, P), img, atol=1e-12))
        self.assertTrue(np.array_equal(L.colorize(img, dict(P, Amount=0.0, Drive=3.0)), img))

    def test_functions(self):
        v = np.array([0.0, 0.25, 0.5, 1.0])
        self.assertTrue(np.allclose(L.cz_function(v, 0), [0, 0.5, 1, 0], atol=1e-12))
        self.assertTrue(np.allclose(L.cz_function(v, 1), [0, 0.5, 1, 0]))
        self.assertTrue(np.allclose(L.cz_function(v, 2), [0, 0.25, 0.5, 0]))

    def test_overflow(self):
        y = np.array([-0.3, 0.4, 1.25, 2.3])
        self.assertTrue(np.allclose(L.cz_overflow(y, 0, 0.5), [0, 0.4, 1, 1]))
        self.assertTrue(np.allclose(L.cz_overflow(y, 1, 0.5), [0.7, 0.4, 0.25, 0.3]))
        self.assertTrue(np.allclose(L.cz_overflow(y, 2, 0.5), [0.3, 0.4, 0.75, 0.3]))
        self.assertTrue(np.allclose(L.cz_overflow(np.array([0.4, 0.7, 1.0]), 3, 0.5), [0.4, 0.3, 0.0]))

    def test_paik_phase_is_a_cyclic_shift(self):
        img = ramp_img()
        out = L.colorize(img, dict(Phaser=0.0, Phaseg=1 / 3, Phaseb=2 / 3))
        x = L.lum(img)
        self.assertTrue(np.allclose(out[..., 1], L.cz_function(x + 1 / 3, 0)))
        self.assertTrue(np.allclose(out[..., 2], L.cz_function(x + 2 / 3, 0)))

    def test_hue_mode_and_drift(self):
        px = L.to4(np.array([[[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]]))
        out = L.colorize(px, dict(Mode=1, Huegain=1 / 3))
        self.assertTrue(np.allclose(out[0, 0, :3], [1, 0, 0]))
        self.assertTrue(np.allclose(out[0, 1, :3], [0, 1, 0]))
        img = ramp_img()
        a = L.colorize(img, dict(Drift=0.25), t=1.0)
        b = L.colorize(img, dict(Phaser=0.25, Phaseg=0.58, Phaseb=0.92))
        self.assertTrue(np.allclose(a, b))


class Bands(unittest.TestCase):
    def test_grey_levels_count(self):
        out = L.bands(ramp_img(256, 2), dict(Fill=1, Bands=8))
        self.assertEqual(len(np.unique(np.round(out[..., 0], 9))), 8)

    def test_integer_offset_invariant_grey_rotates_rainbow(self):
        img = ramp_img(64, 2)
        g0 = L.bands(img, dict(Fill=1, Bands=6))
        g1 = L.bands(img, dict(Fill=1, Bands=6, Offset=1.0))
        r0 = L.bands(img, dict(Fill=2, Bands=6))
        r1 = L.bands(img, dict(Fill=2, Bands=6, Offset=1.0))
        self.assertFalse(np.allclose(r0, r1))
        q0 = np.clip((np.floor(L.lum(img) * 6) + 0.5) / 6, 0, 1)
        self.assertTrue(np.allclose(g0[..., 0], q0))
        self.assertTrue(np.allclose(g1[..., 0], q0))

    def test_contour_columns(self):
        W = 200
        out = L.bands(ramp_img(W, 3), dict(Bands=10, Fillamt=0.0, Background=1, Linewidth=2.0))
        cols = np.where(out[1, :, 0] > 0.5)[0].tolist()
        expect = sorted([20 * k - 1 for k in range(1, 10)] + [20 * k for k in range(1, 10)])
        self.assertEqual(cols, expect)

    def test_major_lines_wider(self):
        W = 400
        out = L.bands(ramp_img(W, 3), dict(Bands=10, Fillamt=0.0, Background=1, Linewidth=2.0, Major=5,
                                           Majorwidth=3.0))
        lit = out[1, :, 0] > 0.01
        self.assertGreater(lit[190:210].sum(), lit[70:90].sum())

    def test_softness_blends(self):
        img = ramp_img(256, 2)
        hard = L.bands(img, dict(Fill=1, Bands=4))
        soft = L.bands(img, dict(Fill=1, Bands=4, Softness=0.5))
        self.assertGreater(len(np.unique(np.round(soft[..., 0], 6))), 4)
        self.assertTrue(np.allclose(hard[0, 32], soft[0, 32]))          # band centres untouched


class Keyer(unittest.TestCase):
    def setUp(self):
        self.A = L.to4(RNG.random((20, 30, 3)))

    def test_amount0(self):
        self.assertTrue(np.array_equal(L.keyer(self.A, dict(Amount=0.0, Op=8)), self.A))

    def test_luma_window(self):
        px = L.to4(np.array([[[0.2] * 3, [0.5] * 3, [0.8] * 3]]))
        k = L.keyer(px, dict(Op=1, Low=0.3, High=0.7, Soft=0.0))[0, :, 0]
        self.assertTrue(np.allclose(k, [0, 1, 0]))

    def test_logic_truth_table(self):
        a = np.array([0.0, 0.0, 1.0, 1.0])
        b = np.array([0.0, 1.0, 0.0, 1.0])
        self.assertEqual(L.ky_logic(a, b, 1).tolist(), [0, 0, 0, 1])
        self.assertEqual(L.ky_logic(a, b, 2).tolist(), [0, 1, 1, 1])
        self.assertEqual(L.ky_logic(a, b, 3).tolist(), [0, 1, 1, 0])
        self.assertEqual(L.ky_logic(a, b, 4).tolist(), [0, 0, 1, 0])
        self.assertEqual(L.ky_logic(a, b, 6).tolist(), [0, 0, 1, 0])

    def test_wipe_and_iris(self):
        out = L.keyer(self.A, dict(Keya=2, Shape=0, Position=0.5, Shapesoft=0.0, Br=1.0, Bg=0.0, Bb=0.0))
        self.assertTrue(np.allclose(out[:, :15], self.A[:, :15]))
        self.assertTrue(np.allclose(out[:, 15:, :3], [1, 0, 0]))
        k0 = L.keyer(self.A, dict(Keya=2, Shape=2, Position=0.0, Shapesoft=0.0, Op=1))[..., 0]
        k1 = L.keyer(self.A, dict(Keya=2, Shape=2, Position=1.0, Shapesoft=0.0, Op=1))[..., 0]
        self.assertEqual(k0.sum(), 0)
        self.assertEqual(k1.mean(), 1.0)
        for sh in (3, 4, 5):
            f = L.ky_shape_field(30, 20, dict(L.KY_DEFAULTS, Shape=sh, Angle=20.0))
            self.assertTrue(0.0 <= f.min() and f.max() <= 1.0 + 1e-9, sh)

    def test_chroma_and_spill(self):
        px = L.to4(np.array([[[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.4, 0.6, 0.4]]]))
        k = L.keyer(px, dict(Keya=1, Op=1, Tolerance=0.1, Chromasoft=0.0))[0, :, 0]
        self.assertEqual(k[:2].tolist(), [0.0, 1.0])
        sp = L.ky_spill(px, dict(L.KY_DEFAULTS, Spill=1.0))
        self.assertLess(sp[0, 2, 1] - sp[0, 2, 0], px[0, 2, 1] - px[0, 2, 0])
        g = L.to4(np.full((1, 1, 3), 0.5))
        self.assertTrue(np.allclose(L.ky_spill(g, dict(L.KY_DEFAULTS, Spill=1.0)), g))

    def test_bits(self):
        out = L.keyer(L.to4(np.full((1, 1, 3), 128 / 255)), dict(Keya=5, Op=8, Br=64 / 255, Bg=64 / 255,
                                                                 Bb=64 / 255))
        self.assertTrue(np.allclose(out[0, 0, :3], 192 / 255))


class Ruttetra(unittest.TestCase):
    def test_undeflected_grid(self):
        img = L.to4(RNG.random((48, 27, 3)))
        pos, _c = L.rt_lines(img, dict(Defy=0.0, Lines=16, Samples=10))
        W, H = 27, 48
        self.assertTrue(np.allclose(pos[..., 0], np.linspace(0, W, 10)[None, :]))
        self.assertTrue(np.allclose(pos[:, 0, 1], L.rt_expected_rows(H, 16)))

    def test_constant_deflection(self):
        img = L.to4(np.full((40, 30, 3), 0.5))
        a, _ = L.rt_lines(img, dict(Defy=0.0, Lines=8))
        b, _ = L.rt_lines(img, dict(Defy=0.1, Lines=8))
        self.assertTrue(np.allclose(b[..., 1] - a[..., 1], 0.05 * 40))
        c, _ = L.rt_lines(img, dict(Defy=0.0, Defx=0.2, Defxsrc=4, Lines=8))
        self.assertTrue(np.allclose(c[..., 0] - a[..., 0], 0.1 * 40))         # inverse luma 0.5, heights -> px

    def test_vertical_scan_and_rotate(self):
        img = L.to4(RNG.random((40, 40, 3)))
        v, _ = L.rt_lines(img, dict(Defy=0.0, Scan=1, Lines=4, Samples=5))
        self.assertTrue(np.allclose(v[:, 0, 0], L.rt_expected_rows(40, 4)))
        h, _ = L.rt_lines(img, dict(Defy=0.0, Lines=4, Samples=5))
        r, _ = L.rt_lines(img, dict(Defy=0.0, Lines=4, Samples=5, Rotate=90.0))
        c = np.array([20.0, 20.0])
        d = h - c
        self.assertTrue(np.allclose(r - c, np.stack([-d[..., 1], d[..., 0]], -1), atol=1e-9))

    def test_relief_pitch_lifts_bright(self):
        img = L.to4(np.zeros((40, 40, 3)))
        img[:, 20:] = 1.0
        a, _ = L.rt_lines(img, dict(Defy=0.0, Lines=4, Samples=41, Z=0.3, Pitch=35.0))
        self.assertGreater(a[2, 35, 1] - a[2, 5, 1], 0.3 * 40 * 0.5)

    def test_jitter_bounded_and_deterministic(self):
        img = L.to4(np.zeros((40, 40, 3)))
        a, _ = L.rt_lines(img, dict(Defy=0.0, Lines=32, Jitter=0.02, Jitterrate=10.0), t=0.31)
        b, _ = L.rt_lines(img, dict(Defy=0.0, Lines=32, Jitter=0.02, Jitterrate=10.0), t=0.39)
        c, _ = L.rt_lines(img, dict(Defy=0.0, Lines=32, Jitter=0.02, Jitterrate=10.0), t=0.41)
        z, _ = L.rt_lines(img, dict(Defy=0.0, Lines=32))
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))
        self.assertLessEqual(np.abs(a[..., 1] - z[..., 1]).max(), 0.01 * 40 + 1e-9)


class Scanimate(unittest.TestCase):
    def test_settle_is_clean_source(self):
        src = L.to4(RNG.random((24, 16, 3)))
        out = L.sc_warp(src, dict(Settle=1.0, Key=0.0, Keysoft=0.0), t=3.7)
        self.assertTrue(np.allclose(out, src, atol=1e-12))

    def test_bend_row_shift(self):
        W, H = 64, 32
        x, y, ok = L.sc_warp_coords(W, H, dict(L.SC_DEFAULTS, Fly=0.0, Taper=0.0, Bend=0.1, Bendspeed=0.0,
                                                 Bendfreq=1.0), 0.0)
        a = W / H
        X, Y = L.pixel_grid(W, H)
        qy = Y / H - 0.5
        expect = X - 0.1 * a * np.sin(2 * np.pi * qy) * H
        self.assertTrue(np.allclose(x, expect))
        self.assertTrue(np.allclose(y, Y))

    def test_trail_decay_and_settle(self):
        w0 = np.zeros((2, 2, 4))
        s = np.ones((2, 2, 4))
        for _ in range(5):
            s = L.sc_trail_step(w0, s, dict(Decay=0.9))
        self.assertTrue(np.allclose(s[..., 3], 0.9 ** 5))
        self.assertTrue(np.allclose(L.sc_trail_step(w0, np.ones((2, 2, 4)), dict(Settle=1.0)), 0))

    def test_colourise(self):
        tr = np.array([[[0.2, 0.4, 0.6, 1.0], [0.0, 0.0, 0.0, 0.6], [0.0, 0.0, 0.0, 0.0]]])
        c = L.sc_colourise(tr, dict(Palette=0))
        self.assertTrue(np.allclose(c[0, 0], L.PALETTES['gold'][0]))
        self.assertTrue(np.allclose(c[0, 2], 0))
        cb = L.sc_colourise(tr, dict(Palette=4, Bands=4))
        self.assertTrue(np.allclose(cb[0, 1], L.palette(4, 0.4) * 0.75))
        cl = L.sc_colourise(tr, dict(Colour=1))
        self.assertTrue(np.allclose(cl[0, 0], [0.2, 0.4, 0.6]))
        self.assertTrue(np.allclose(L.palette(2, 1.0), L.PALETTES['electric'][3]))


class Vfeedback(unittest.TestCase):
    def test_identity_holds(self):
        s = L.to4(RNG.random((16, 12, 3)))
        out = L.vf_step(s, s, L.VF_IDENTITY)
        self.assertTrue(np.allclose(out, s, atol=1e-12))

    def test_integer_shift_repeat_is_roll(self):
        s = L.to4(RNG.random((10, 14, 3)))
        out = L.vf_step(s, s, dict(L.VF_IDENTITY, Shiftx=1.0, Edge=2))
        self.assertTrue(np.allclose(out, np.roll(s, 1, axis=1), atol=1e-12))

    def test_black_edge_and_mirror(self):
        s = L.to4(np.ones((10, 10, 3)))
        out = L.vf_step(s, s, dict(L.VF_IDENTITY, Shiftx=3.0, Edge=0))
        self.assertTrue(np.allclose(out[:, :3, :3], 0) and np.allclose(out[:, 3:, :3], 1))
        r = L.to4(RNG.random((8, 12, 3)))
        m = L.vf_step(r, r, dict(L.VF_IDENTITY, Mirror=1))
        self.assertTrue(np.allclose(m[:, :6], m[:, 6:][:, ::-1]))

    def test_hue_three_steps(self):
        s = L.to4(RNG.random((6, 6, 3)) * 0.8 + 0.1)
        x = s
        for _ in range(3):
            x = L.vf_step(x, s, dict(L.VF_IDENTITY, Huestep=120.0))
        self.assertTrue(np.allclose(x, s, atol=1e-9))

    def test_autogain_target(self):
        c = np.full((8, 8, 3), 0.05)
        live = L.to4(c)
        p = dict(L.VF_IDENTITY, Autogain=1.0, Target=0.45)
        for _ in range(150):
            c = L.vf_colour(c, live, p, float(L.lum(c).mean()))
        self.assertAlmostEqual(float(L.lum(c).mean()), 0.45, delta=0.02)

    def test_presets_never_lock(self):
        live = L.to4(RNG.random((24, 32, 3)) * 0.8)
        for _slot, name, vals in MODS['vfeedback']['PRESETS']:
            s = live
            for _ in range(120):
                s = L.vf_step(s, live, vals)
            m = float(L.lum(s).mean())
            self.assertTrue(0.03 < m < 0.97, (name, m))
            self.assertGreater(float(s[..., :3].std()), 0.01, name)
            self.assertFalse(np.isnan(s).any(), name)

    def test_meter_grid(self):
        g = L.mean_grid(1080, 1920)
        self.assertEqual(len(g), 4096)
        self.assertEqual(g[0], (8, 15))


if __name__ == '__main__':
    unittest.main()


class Modulate(unittest.TestCase):
    def img(self, W=48, H=64):
        X, Y = L.pixel_grid(W, H)
        return L.to4(np.stack([X / W, Y / H, 0.5 + 0.5 * np.sin(X / 5.0)], -1))

    def test_amount0_and_zero_multiple(self):
        A = self.img()
        self.assertEqual(float(np.abs(L.modulate(A, {'Amount': 0.0}) - A).max()), 0.0)
        for mode in (0, 2, 3, 7, 8):                        # multiple 0 (+ offset 0) = identity at texel centres
            o = L.modulate(A, {'Mode': mode, 'Multiple': 0.0, 'Wrap': 2})
            self.assertLess(float(np.abs(o - A).max()), 1e-12, mode)
        o = L.modulate(A, {'Mode': 1, 'Multiple': 0.0, 'Offset': 0.0, 'Wrap': 2})     # scale factor 1
        self.assertLess(float(np.abs(o - A).max()), 1e-12)

    def test_modulate_constant_b_is_a_shift(self):
        W, H = 40, 30
        A = self.img(W, H)
        B = np.zeros((4, 4, 4))
        B[..., 0], B[..., 1] = 0.75, 0.5                     # B.rg - 0.5 = (0.25, 0) x Multiple 0.2 -> +2 px in x
        o = L.modulate(A, {'Mode': 0, 'Multiple': 0.2, 'Offset': 0.5, 'Wrap': 0}, bimg=B)
        self.assertLess(float(np.abs(o - np.roll(A, -2, axis=1)).max()), 1e-9)

    def test_rotate_half_turn(self):
        W, H = 32, 32
        A = self.img(W, H)
        B = np.full((2, 2, 4), 0.0)
        o = L.modulate(A, {'Mode': 2, 'Multiple': 0.0, 'Offset': np.pi, "Wrap": 2}, bimg=B)
        self.assertLess(float(np.abs(o - A[::-1, ::-1]).max()), 1e-9)

    def test_pixelate_cells(self):
        A = self.img(64, 64)
        B = np.full((2, 2, 4), 0.0)
        o = L.modulate(A, {'Mode': 4, 'Multiple': 0.0, 'Offset': 8.0, 'Wrap': 2}, bimg=B)
        self.assertEqual(len(np.unique(np.round(o[..., 0], 9))), 8)     # 8 x 8 cells -> 8 distinct x values

    def test_kaleid_symmetry_and_wraps(self):
        A = self.img(64, 64)
        B = np.zeros((2, 2, 4))
        o = L.modulate(A, {'Mode': 6, 'Multiple': 0.0, 'Sides': 4.0, 'Wrap': 1}, bimg=B)
        self.assertLess(float(np.abs(o - o.transpose(1, 0, 2)).max()), 1e-6)   # 4-fold fold is symmetric in x = y
        for w in range(4):
            o = L.modulate(A, {'Mode': 0, 'Multiple': 1.5, 'Wrap': w})
            self.assertTrue(np.isfinite(o).all())
            self.assertLessEqual(float(o.max()), 1.0 + 1e-9)
        o = L.modulate(A, {'Mode': 0, 'Multiple': 1.5, 'Wrap': 3})
        self.assertGreater(float((o[..., 3] == 0).mean()), 0.05)

    def test_scroll_time(self):
        W, H = 40, 20
        A = self.img(W, H)
        B = np.zeros((2, 2, 4))
        o = L.modulate(A, {'Mode': 7, 'Multiple': 0.0, 'Speed': 0.25, 'Wrap': 0}, bimg=B, t=0.5)   # +0.125 = 5 px
        self.assertLess(float(np.abs(o - np.roll(A, -5, axis=1)).max()), 1e-9)

