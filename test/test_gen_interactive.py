"""Offline tests for GEN_interactive (builders/gen_interactive.py rack + gen_interactive_logic.py + the shared GLSL),
and helpers the per-module tests (test_gen_interactive_<module>.py) import: a fake TD for builder dry runs, the
expression evaluator, glslc. Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_interactive*.py'
GLSL checks compile with glslc (OpenGL target) against stubs of the TD compute built-ins: a syntax / type check, NOT a
TD compile (that is LIVE CHECK I1 in docs/builds/gen_interactive.md)."""
import math
import os
import re
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
G = os.path.join(B, 'glsl')
MODULES = ['ribbon', 'flowers', 'pigment', 'linevolume', 'strings', 'parallax', 'skinner']
TD_STUB = """#version 460
uniform sampler2D sTD2DInputs[3];
uniform int uTDPass;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""


def built_modules():
    """Modules whose file exists (the rack lists all four; a module lands with its file + tests)."""
    return [m for m in MODULES if os.path.exists(os.path.join(B, 'gen_interactive_%s.py' % m))]


def rack(extra=None):
    ns = dict(extra or {})
    with open(os.path.join(B, 'gen_interactive.py')) as fh:
        exec(compile(fh.read(), 'gen_interactive.py', 'exec'), ns)
    return ns


RACK = rack()
LOGIC = RACK['LGI']


def module(name, ns=None):
    m = dict(ns or RACK)
    with open(os.path.join(B, 'gen_interactive_%s.py' % name)) as fh:
        exec(compile(fh.read(), 'gen_interactive_%s.py' % name, 'exec'), m)
    return m


def pars(M):
    """{name: (style, default, opts)} of every page."""
    return dict((n, (s, d, o)) for _pg, ps in M['PAGES'] for n, s, d, o in ps)


# ------------------------------------------------------------------ fake parent()/op() for expressions
class _EvPar(object):
    def __init__(self, style, val, opts):
        self.style, self.val, self.o = style, val, opts

    def eval(self):
        return None if self.style in ('TOP', 'CHOP') else self.val

    @property
    def menuIndex(self):
        return self.o['names'].index(self.val)


class _EvPars(object):
    def __init__(self, M, over=None):
        self._p = {}
        for n, (s, d, o) in pars(M).items():
            if s == 'RGB':
                for ch, v in zip('rgb', d):
                    self._p[n + ch] = _EvPar('Float', v, o)
            else:
                self._p[n] = _EvPar(s, d, o)
        for k, v in (over or {}).items():
            p = self._p[k]
            p.val = p.o['names'][v] if p.style == 'Menu' and isinstance(v, int) else v

    def __getattr__(self, k):
        return self._p[k]


class _EvVal(float):
    """A channel value that also answers chan[0] (sample 0), like a TD Channel in expressions."""
    def __getitem__(self, i):
        return float(self)


class _EvChop(object):
    def __init__(self, vals):
        self.vals = vals

    def __getitem__(self, k):
        return _EvVal(self.vals.get(k, 0.0))


class _EvTime(object):
    frame = 1000
    seconds = 1000 / 60.0


def ev(expr, M, over=None, in_w=1080, in_h=1920, drive=None):
    """Evaluate a module par expression with its defaults (+ over), an in1 of in_w x in_h and a rack drive CHOP."""
    pp = _EvPars(M, over)
    drv = _EvChop(drive or {'beats': 3.25, 'bpm': 120.0, 'level': 0.5})

    class _Parent(object):
        par = pp

        @staticmethod
        def op(name):
            return drv

    class _Op(_EvChop):                                     # op('in1').width / op('clock_int')[0]
        width, height = in_w, in_h

    env = {'parent': lambda *a: _Parent(), 'op': lambda name: _Op({0: 1.25, 'x': 0.0}),
           'absTime': _EvTime(), 'math': math, 'me': None, 'float': float, 'int': int, 'max': max, 'min': min}
    return eval(expr, env)


# ------------------------------------------------------------------ GLSL
def declared_uniforms(text):
    return set(re.findall(r'^uniform\s+vec4\s+(\w+)\s*;', text, re.M))


def glslc(test, text, what):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.comp')
        with open(p, 'w') as fh:
            fh.write(TD_STUB + text)
        r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                            '-o', os.devnull, p], capture_output=True, text=True)
        test.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))


def check_uniforms(test, text, U, what):
    """Every uniform the build sets is declared and every declared non-look uniform is set (4 exprs each)."""
    names = [u for u, _e in U]
    test.assertEqual(len(names), len(set(names)), what)
    decl = declared_uniforms(text)
    for u in names:
        test.assertIn(u, decl, '%s sets %s, the shader does not declare it' % (what, u))
    for u in decl - {'uLook', 'uCa', 'uCb'}:
        test.assertIn(u, names, '%s declares %s, the build never sets it' % (what, u))
    for _u, ex in U:
        test.assertEqual(len(ex), 4, what)


def shared_bytes(text):
    """Rough shared-memory size of a compute shader (vec4 16, float / uint / int 4 bytes; [N] arrays)."""
    size = {'vec4': 16, 'vec3': 12, 'vec2': 8, 'float': 4, 'uint': 4, 'int': 4, 'ivec2': 8, 'uvec2': 8}
    defs = dict((k, int(v)) for k, v in re.findall(r'#define\s+(\w+)\s+(\d+)', text))
    tot = 0
    for ty, _n, dim in re.findall(r'^shared\s+(\w+)\s+(\w+)\s*(?:\[([^\]]+)\])?\s*;', text, re.M):
        k = 1
        if dim:
            k = eval(dim, {}, defs)
        tot += size[ty] * k
    return tot


# ------------------------------------------------------------------ fake TD (builder dry runs)
class FPar(object):
    def __init__(self, name, val=None):
        self.name, self.val, self.expr, self.mode, self.default = name, val, None, None, None
        self.menuNames, self.menuLabels, self.pulses, self.normMin, self.normMax = [], [], 0, None, None
        self.isMenu = False

    def eval(self):
        return self.val

    def pulse(self):
        self.pulses += 1

    @property
    def menuIndex(self):
        return self.menuNames.index(self.val) if self.val in self.menuNames else 0

    @menuIndex.setter
    def menuIndex(self, i):
        self.val = self.menuNames[i]


class FPars(object):
    def __init__(self):
        object.__setattr__(self, '_d', {})

    def _get(self, name, create):
        d = object.__getattribute__(self, '_d')
        if name not in d and create:
            d[name] = FPar(name)
        return d.get(name)

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return self._get(name, not name[:1].isupper())     # custom (Capitalised) pars exist only once appended

    def __setattr__(self, name, v):
        self._get(name, True).val = v


class FPage(object):
    def __init__(self, o, name):
        self.o, self.name = o, name

    def _add(self, names, menu=False):
        ps = []
        for n in names:
            p = FPar(n)
            p.isMenu = menu
            object.__getattribute__(self.o.par, '_d')[n] = p
            ps.append(p)
        return ps

    def appendFloat(self, n, label=None):
        return self._add([n])
    appendInt = appendToggle = appendPulse = appendCHOP = appendTOP = appendStr = appendCOMP = appendFloat

    def appendMenu(self, n, label=None):
        return self._add([n], True)

    def appendRGB(self, n, label=None):
        return self._add([n + 'r', n + 'g', n + 'b'])


class FOutConn(object):
    def __init__(self, o):
        self.owner = o


class FConnRef(object):
    def __init__(self, owner):
        self.owner = owner


class FConn(object):
    def __init__(self, o, i):
        self.o, self.i = o, i
        self.inOP = None

    @property
    def connections(self):
        src = self.o.inputs[self.i] if self.i < len(self.o.inputs) else None
        return [FConnRef(src)] if src is not None else []

    def connect(self, src):
        if isinstance(src, FOutConn):
            src = src.owner
        ins = self.o.inputs
        while len(ins) <= self.i:
            ins.append(None)
        ins[self.i] = src


class FCell(object):
    def __init__(self, v):
        self.val = str(v)


class FOP(object):
    isCOMP = False

    def __init__(self, parent, name):
        self.parent_, self.name, self.children, self.inputs = parent, name, [], []
        self.par, self.valid, self.viewer, self.comment = FPars(), True, False, ''
        self.text, self.customPages, self.allowCooking, self.dock = '', [], False, None
        self.seq = type('S', (), {})()
        self.seq.vec, self.seq.array, self.seq.const = (type('Q', (), {'numBlocks': 1})() for _ in range(3))
        self.inputConnectors = [FConn(self, i) for i in range(8)]
        self.outputConnectors = [FOutConn(self)]
        self.rows_ = []
        self.storage = {}

    @property
    def docked(self):
        return [o for o in (self.parent_.children if self.parent_ else []) if o.dock is self]

    @property
    def OPType(self):
        return type(self).__name__

    @property
    def path(self):
        return (self.parent_.path if self.parent_ else '') + '/' + self.name

    def parent(self, k=1):
        o = self
        for _ in range(k):
            o = o.parent_
        return o

    def op(self, name):
        return next((o for o in self.children if o.name == name), None)

    def create(self, cls, name):
        o = cls(self, name)
        self.children.append(o)
        if cls.__name__ in ('glslTOP', 'scriptCHOP'):    # TD docks template DATs to new GLSL / Script ops
            d = FAKE['textDAT'](self, name + ('_pixel' if cls.__name__ == 'glslTOP' else '_callbacks'))
            d.dock = o
            self.children.append(d)
            if cls.__name__ == 'scriptCHOP':
                o.par.callbacks = d
        return o

    def appendCustomPage(self, name):
        pg = FPage(self, name)
        self.customPages.append(pg)
        return pg

    def store(self, k, v):
        self.storage[k] = v

    def fetch(self, k, default=None, search=False):
        return self.storage.get(k, default)

    # table DAT
    def clear(self):
        self.rows_ = []

    def appendRow(self, r):
        self.rows_.append([str(x) for x in r])

    @property
    def numRows(self):
        return len(self.rows_)

    def row(self, name):
        return next((r for r in self.rows_[1:] if r[0] == name), None)

    def deleteRow(self, name):
        self.rows_ = [r for r in self.rows_ if r is self.rows_[0] or r[0] != name]

    def __getitem__(self, rc):
        r, c = rc
        hdr = self.rows_[0]
        row = self.rows_[r] if isinstance(r, int) else self.row(r)
        ci = c if isinstance(c, int) else hdr.index(c)
        return FCell(row[ci])


class FCOMP(FOP):
    isCOMP = True


_NAMES = ('textDAT', 'tableDAT', 'parameterexecuteDAT', 'constantTOP', 'inTOP', 'switchTOP', 'crossTOP', 'outTOP',
          'moviefileinTOP', 'glslTOP', 'feedbackTOP', 'selectTOP', 'resolutionTOP', 'choptoTOP', 'constantCHOP',
          'speedCHOP', 'scriptCHOP', 'mouseinCHOP', 'inCHOP', 'nullTOP', 'levelTOP', 'blurTOP', 'compositeTOP',
          'transformTOP', 'renderselectTOP', 'glslmultiTOP', 'nullCHOP', 'mathCHOP', 'lagCHOP', 'selectCHOP')
FAKE = dict((n, type(n, (FOP,), {})) for n in _NAMES)
FAKE.update((n, type(n, (FCOMP,), {})) for n in ('baseCOMP', 'nullCOMP', 'containerCOMP', 'windowCOMP'))


def fake_td():
    """(namespace with the fake TD globals, lab COMP, record dict {destroyed, layouts})."""
    root = FAKE['baseCOMP'](None, 'project1')
    lab = root.create(FAKE['baseCOMP'], 'lab')
    rec = {'destroyed': [], 'layouts': []}

    def safe_destroy(o):
        o.valid = False
        o.parent_.children.remove(o)
        rec['destroyed'].append(o.name)

    def layout_stages(c, stages, colors=True, arrange='mixed'):
        for s in stages:
            for n in s['ops']:
                assert c.op(n) is not None, (c.path, n)
        rec['layouts'].append((c.path, stages))
        return 'ok'

    handlers = type('H', (), {'module': type('M', (), {'safe_destroy': staticmethod(safe_destroy),
                                                        'layout_stages': staticmethod(layout_stages)})})

    def op(path):
        if path == '/jazib_mcp/handlers':
            return handlers
        if not isinstance(path, str) or not path.startswith('/project1'):
            return None
        o = root
        for part in path.split('/')[2:]:
            o = o.op(part) if o is not None else None
        return o

    ns = dict(FAKE)
    ns.update({'op': op, 'ParMode': type('PM', (), {'EXPRESSION': 'expr', 'CONSTANT': 'const'}),
               'safe_destroy': safe_destroy})
    return ns, lab, rec


# ------------------------------------------------------------------ tests
class Files(unittest.TestCase):
    def test_ascii_and_no_version(self):
        fs = [f for f in os.listdir(B) if f.startswith('gen_interactive')]
        fs += [os.path.join('glsl', f) for f in os.listdir(G) if f.startswith('gen_interactive')]
        self.assertGreaterEqual(len(fs), 6)
        for f in fs:
            with open(os.path.join(B, f), 'rb') as fh:
                t = fh.read().decode('ascii')
            if f.endswith('.glsl'):
                self.assertNotIn('#version', t, f)
            self.assertNotIn('numpyArray(delayed', t, f)          # no TOP pixel reads in builders (T-74)


class Rack(unittest.TestCase):
    def test_reuses_gen_sim_rack(self):
        for k in ('plan_chain', 'chain_edges', 'rewire', 'remove', '_instance', 'colour_page', 'LOOK_UNIFORMS'):
            self.assertIn(k, RACK)
        self.assertEqual(RACK['NAME'], 'GEN_interactive')
        self.assertEqual(RACK['FIRST'], ('ribbon1', 'ribbon'))
        self.assertEqual(RACK['MODULES'], MODULES)
        self.assertTrue(RACK['module_file']('ribbon').endswith('builders/gen_interactive_ribbon.py'))
        self.assertIn('_drive', RACK['_GP'])                       # GEN_pattern's drive, imported, not copied

    def test_helpers_in_H(self):
        for k in ('mk', 'expr', 'sd', 'uniforms', 'glsl', 'pas', 'state', 'clock', 'pulses', 'out_sel', 'pts_in',
                  'mask_in', 'drive_uniforms', 'time_expr'):
            self.assertIn(k, RACK['H'])

    def test_glsl_text_prefixes(self):
        t = RACK['glsl_text']('gen_interactive_mask')
        self.assertTrue(t.startswith('// gen_sim_common'))
        self.assertIn('gi_env', t)
        self.assertLess(t.index('gs_blend'), t.index('gi_env'))

    def test_rack_pages_unique(self):
        names = [n for _pg, ps in RACK['RACK_PAGES'] for n, *_ in ps]
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            self.assertRegex(n, r'^[A-Z][a-z0-9]*$')

    def test_full_presets(self):
        pages = [('A', [('X', 'Float', 1.0, {}), ('M', 'Menu', 'b', {'names': ['a', 'b'], 'labels': ['a', 'b']}),
                        ('C', 'RGB', (0.1, 0.2, 0.3), {}), ('Go', 'Pulse', None, {})])]
        out = RACK['full_presets'](pages, [(1, 'p', {'X': 2.0, 'C': (1, 0, 0)}), (2, 'q', {})])
        self.assertEqual(out[0][2], {'X': 2.0, 'M': 1, 'Cr': 1, 'Cg': 0, 'Cb': 0})
        self.assertEqual(out[1][2], {'X': 1.0, 'M': 1, 'Cr': 0.1, 'Cg': 0.2, 'Cb': 0.3})


class PointsLogic(unittest.TestCase):
    def test_demo_points_in_frame_and_moving(self):
        for shape in range(4):
            a = LOGIC['demo_points'](1.0, 6, shape, 1)
            b = LOGIC['demo_points'](1.5, 6, shape, 1)
            self.assertEqual(len(a), 6)
            for (x, y) in a:
                self.assertTrue(-0.05 < x < 1.05 and -0.05 < y < 1.05, (shape, x, y))
            self.assertGreater(max(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in zip(a, b)), 1e-3, shape)

    def test_demo_points_vectorised_equals_scalar(self):
        """perf lane 2: cached / vectorised hashes + wander noise give the old per-point scalar values exactly."""
        G = LOGIC['gs']()
        h = LOGIC['_hash01']
        for n, seed, t in ((16, 1, 3.25), (5, 7, 0.0), (40, 2, 123.4)):
            for shape in range(4):
                got = LOGIC['demo_points'](t, n, shape, seed)
                for i in range(n):
                    h1, h2, h3, h4 = (h(i * 4 + k, seed) for k in range(4))
                    self.assertEqual(LOGIC['_demo_hashes'](n, seed)[4 * i:4 * i + 4], [h1, h2, h3, h4])
                    if shape == 2:
                        x = 0.1 + 0.8 * float(G['vnoise'](t * 0.35 + 13.1 * i, 3.7 * i, seed + 1))
                        y = 0.1 + 0.8 * float(G['vnoise'](t * 0.35 + 7.3 * i, 5.1 * i + 2.0, seed + 2))
                        self.assertEqual(got[i], (x, y))

    def test_face_points(self):
        names, vals = [], []
        for reg, cnt in (('nose', 3), ('jaw', 2)):
            for k in range(cnt):
                names += ['f1_%s_%02dx' % (reg, k), 'f1_%s_%02dy' % (reg, k)]
                vals += [0.1 * (k + 1), 0.2]
        vals[2:4] = [0.0, 0.0]                                     # nose_01 absent
        pts = LOGIC['face_points'](names, vals, 'f1_nose_*', 1, None)
        self.assertEqual(len(pts), 3)
        self.assertAlmostEqual(pts[0][0], 0.1)
        self.assertAlmostEqual(pts[0][1], 0.8)                     # top-left origin -> y up
        self.assertIsNone(pts[1])
        self.assertEqual(len(LOGIC['face_points'](names, vals, '', 2, None)), 3)   # all 5, stride 2
        self.assertAlmostEqual(LOGIC['face_points'](names, vals, 'f1_jaw_00', 1, None, mirror=True)[0][0], 0.9)

    def test_effector_points_decode_pack_buffer(self):
        E = {}
        with open(os.path.join(B, 'effectors_logic.py')) as fh:
            exec(fh.read(), E)
        import numpy as np
        w = E['identity']()
        w = [list(r) for r in w]
        w[0][3], w[1][3] = 0.5625, -1.0                            # right edge, bottom
        rows = [{'name': 'a', 'kind': 'null', 'enabled': '1'}, {'name': 'b', 'kind': 'pts', 'enabled': '1'},
                {'name': 'c', 'kind': 'sphere', 'enabled': '0'}]
        pts = np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        effs = [E['effector'](rows[0], w), E['effector'](rows[1], None, points=pts), E['effector'](rows[2])]
        tex = E['pack_buffer'](effs)
        plane = (0.0, 0.0, 1.125, 2.0)
        out = LOGIC['effector_points'](tex, [0, 1, 2], plane)
        self.assertEqual(len(out), 3)                              # a centre + b's two points, c disabled
        self.assertAlmostEqual(out[0][0], 1.0)
        self.assertAlmostEqual(out[0][1], 0.0)
        self.assertAlmostEqual(out[1][0], 0.5)
        self.assertAlmostEqual(out[1][1], 0.5)
        self.assertAlmostEqual(out[2][1], 1.0)
        self.assertEqual(len(LOGIC['effector_points'](tex, [0, 1], plane, sets=False)), 1)
        self.assertEqual(LOGIC['effector_points'](np.array(tex), [1], plane, n=1), [out[1]])

    def test_chop_points_units(self):
        plane = (0.0, 0.0, 1.125, 2.0)
        self.assertEqual(LOGIC['chop_points']({'x': [0.25], 'y': [0.75]}, 0, plane), [(0.25, 0.75)])
        self.assertEqual(LOGIC['chop_points']({'tx': [0.0], 'ty': [-1.0]}, 1, plane), [(0.5, 0.0)])
        self.assertEqual(LOGIC['chop_points']({'tx': [0.0], 'ty': [1.0]}, 2, plane), [(0.5, 1.0)])

    def test_smoothing_and_velocity(self):
        st = LOGIC['step_points']({}, [(0.5, 0.5)], 0.0, 0.5, 2)
        self.assertEqual(st['p'], [(0.5, 0.5), None])
        st = LOGIC['step_points'](st, [(0.6, 0.5)], 1 / 60.0, 0.0, 2)  # Smooth 0 = raw
        self.assertAlmostEqual(st['p'][0][0], 0.6)
        self.assertAlmostEqual(st['v'][0][0], 6.0)
        st2 = LOGIC['step_points'](st, [(0.7, 0.5)], 1 / 60.0, 0.5, 2)
        self.assertAlmostEqual(st2['p'][0][0], 0.65)                    # half kept per 1/60 s
        st3 = LOGIC['step_points'](st, [(0.7, 0.5)], 2 / 60.0, 0.5, 2)
        self.assertAlmostEqual(st3['p'][0][0], 0.6 + 0.1 * 0.75)        # frame-rate independent
        ch = LOGIC['pack'](st3, 2)
        self.assertEqual(ch[0][1], LOGIC['ABSENT'])
        self.assertEqual(LOGIC['present_count'](ch), 1)

    def test_env_level(self):
        self.assertAlmostEqual(LOGIC['env'](4.0, 120, 1.0, 0.25), 1.0)
        self.assertAlmostEqual(LOGIC['env'](4.5, 120, 1.0, 0.25), math.exp(-1.0))
        self.assertAlmostEqual(LOGIC['level'](0.5, 2.0, 0.25), 1.25)


class MaskLogic(unittest.TestCase):
    def test_presence_and_motion(self):
        import numpy as np
        a = np.zeros((4, 4, 4))
        a[1:3, 1:3, :] = 1.0
        o = LOGIC['mask_step'](a, None, mode=1, channel=0)
        self.assertEqual(o[..., 0].sum(), 4.0)
        self.assertEqual(o[..., 1].max(), 0.0)                       # no history: no motion
        b = np.zeros((4, 4, 4))
        o2 = LOGIC['mask_step'](b, o, mode=1, motiongain=4.0, motionsmooth=0.5)
        self.assertAlmostEqual(o2[1, 1, 1], 2.0)                     # |0 - 1| x 4 x (1 - 0.5)
        self.assertEqual(o2[0, 0, 1], 0.0)
        self.assertTrue((LOGIC['mask_step'](b, None, mode=0)[..., 0] == 1).all())
        l = LOGIC['mask_step'](a, None, mode=2, thresh=0.5, soft=0.1)
        self.assertEqual(l[1, 1, 0], 1.0)
        self.assertEqual(l[0, 0, 0], 0.0)
        self.assertEqual(LOGIC['mask_step'](a, None, mode=1, invert=True)[1, 1, 0], 0.0)


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def test_rack_and_every_module_pass(self):
        glslc(self, RACK['glsl_text']('gen_interactive_mask'), 'mask')
        check_uniforms(self, RACK['glsl_text']('gen_interactive_mask'), RACK['MASK_UNIFORMS'], 'mask')
        for mname in built_modules():
            M = module(mname)
            for k, t in M['shader_texts']().items():
                t.encode('ascii')
                glslc(self, t, '%s.%s' % (mname, k))

    def test_local_sizes_and_shared(self):
        for f in os.listdir(G):
            if f.startswith('gen_interactive_') and f != 'gen_interactive_common.glsl':
                with open(os.path.join(G, f)) as fh:
                    t = fh.read()
                m = re.search(r'local_size_x\s*=\s*(\d+),\s*local_size_y\s*=\s*(\d+)', t)
                self.assertIsNotNone(m, f)
                self.assertLessEqual(int(m.group(1)) * int(m.group(2)), 1024, f)
                self.assertLess(shared_bytes(t), 32768, f)            # Metal threadgroup memory 32 KB


class ModuleApi(unittest.TestCase):
    def test_template(self):
        for mname in built_modules():
            M = module(mname)
            self.assertEqual(M['MODULE'], mname)
            for k in ('PAGES', 'PANEL_PAGES', 'PRESETS', 'build', 'shader_texts', 'RESEED'):
                self.assertIn(k, M, mname)
            names = [n for _pg, ps in M['PAGES'] for n, *_ in ps]
            self.assertEqual(names[0], 'Amount', mname)
            self.assertEqual(len(names), len(set(names)), mname)
            for n in names:
                self.assertRegex(n, r'^[A-Z][a-z0-9]*$', '%s.%s' % (mname, n))
            pgs = [p for p, _ in M['PAGES']]
            for pg in M['PANEL_PAGES']:
                self.assertIn(pg, pgs)
            for pg in ('Colour', 'Drive', 'State'):
                self.assertIn(pg, pgs, mname)

    def test_presets_full_and_valid(self):
        for mname in built_modules():
            M = module(mname)
            P = pars(M)
            full = RACK['page_defaults'](M['PAGES'])
            self.assertGreaterEqual(len(M['PRESETS']), 4, mname)
            slots = [s for s, _n, _v in M['PRESETS']]
            self.assertEqual(len(slots), len(set(slots)), mname)
            for _s, pname, vals in M['PRESETS']:
                self.assertEqual(set(vals), set(full), '%s %s: not a full state' % (mname, pname))
                for k, v in vals.items():
                    base = k[:-1] if k not in P else k
                    self.assertIn(base, P, (mname, pname, k))
                    if P[base][0] == 'Menu':
                        self.assertTrue(0 <= v < len(P[base][2]['names']), (mname, pname, k, v))
            self.assertGreater(len(set(tuple(sorted(v.items())) for _s, _n, v in M['PRESETS'])), 3, mname)


class FakeBuild(unittest.TestCase):
    def _build(self):
        ns, lab, rec = fake_td()
        R = rack(ns)
        r = R['build']('/project1/lab', panel=False)
        return R, lab, rec, r

    def test_rack_build_idempotent(self):
        R, lab, rec, r = self._build()
        c = lab.op('GEN_interactive')
        self.assertIsNotNone(c)
        for n in ('slots', 'drive', 'drive_beats', 'drive_pexec', 'gi_logic', 'pts', 'pts_callbacks', 'pts_tex',
                  'mouse', 'pen1', 'mask_src', 'mask_small', 'mask_fb', 'gi_mask', 'img_src', 'bg', 'test_clip',
                  'panic', 'out1', 'ribbon1', 'ribbon1_mix', 'ribbon1_slot'):
            self.assertIsNotNone(c.op(n), n)
        self.assertEqual(c.op('pts_tex').par.chop.val, 'pts')
        self.assertEqual(c.op('pts_tex').par.format.val, 'rgba32float')
        self.assertIn('def onCook', c.op('pts_callbacks').text)
        self.assertEqual(c.op('pts').par.callbacks.val, 'pts_callbacks')
        self.assertEqual([o.name for o in c.op('gi_mask').inputs], ['mask_small', 'mask_fb'])
        self.assertEqual(c.op('mask_fb').par.top.val, 'gi_mask')
        self.assertEqual(c.op('slots').rows_[1][:2], ['ribbon1', 'ribbon'])
        self.assertGreater(r['refreshed'], 3)
        n = len(c.children)
        nm = len(c.op('ribbon1').children)
        R['build']('/project1/lab', panel=False)
        self.assertEqual(len(c.children), n)
        self.assertEqual(len(c.op('ribbon1').children), nm)
        for o in c.children + c.op('ribbon1').children:
            if o.OPType == 'glslTOP':
                self.assertLessEqual(len([i for i in o.inputs if i is not None]), 3, o.path)   # T-88
                self.assertEqual(o.par.mode.val, 'compute', o.path)
                self.assertIsNone(o.op('x'))
        self.assertFalse([d for d in rec['destroyed'] if not d.endswith(('_pixel', '_compute1'))], rec['destroyed'])

    def test_add_every_module_and_remove(self):
        R, lab, rec, _r = self._build()
        c = lab.op('GEN_interactive')
        for mname in built_modules():
            if mname == 'ribbon':
                continue
            a = R['add'](c.path, mname, panel=False)
            self.assertEqual(a['added'], mname + '1')
            self.assertIsNotNone(c.op(mname + '1').op('out1'))
        a = R['add'](c.path, 'ribbon', panel=False)
        self.assertEqual(a['added'], 'ribbon2')
        R['remove'](c.path, 'ribbon2')
        self.assertIsNone(c.op('ribbon2'))
        with self.assertRaises(ValueError):
            R['add'](c.path, 'nope', panel=False)

    def test_module_selects_and_uniform_exprs(self):
        R, lab, rec, _r = self._build()
        c = lab.op('GEN_interactive')
        for mname in built_modules():
            m = c.op(mname + '1') or c.op(R['add'](c.path, mname, panel=False)['added'])
            M = module(mname)
            for o in m.children:
                if o.OPType == 'selectTOP' and o.name in ('pts', 'mask'):
                    self.assertIn("parent(2).op('%s')" % ('pts_tex' if o.name == 'pts' else 'gi_mask'), o.par.top.expr)
                if o.OPType == 'glslTOP':
                    text = m.op(o.name + '_compute').text
                    U = []
                    for k in range(o.seq.vec.numBlocks):
                        nm = getattr(o.par, 'vec%dname' % k).val
                        if nm:
                            U.append((nm, [getattr(o.par, 'vec%dvalue%s' % (k, ch)).expr for ch in 'xyzw']))
                    check_uniforms(self, text, U, '%s.%s' % (mname, o.name))
                    for _u, ex in U:
                        for e in ex:
                            if e in ('0', None):
                                continue
                            v = ev(e, M)
                            self.assertTrue(math.isfinite(float(v)), (mname, o.name, e))
                    for p in ('resolutionw', 'resolutionh'):
                        e = getattr(o.par, p).expr
                        if e and 'me.inputs' not in e:
                            self.assertGreaterEqual(int(ev(e, M)), 1, (mname, o.name, p, e))


class PtsCallbacks(unittest.TestCase):
    def test_demo_cook(self):
        import numpy as np
        L = dict(LOGIC)

        class Chan(object):
            def __init__(self, name):
                self.name, self.v = name, None

            def copyNumpyArray(self, a):
                self.v = np.array(a)

        class SOp(object):
            path = '/x/pts'

            def __init__(self, parent):
                self._p = parent
                self.chans = []
                self.par = type('p', (), {'Frame': type('f', (), {'eval': staticmethod(lambda: 1)})()})()

            def parent(self):
                return self._p

            def clear(self):
                self.chans = []

            def appendChan(self, n):
                ch = Chan(n)
                self.chans.append(ch)
                return ch

        M = {'PAGES': RACK['RACK_PAGES']}
        pp = _EvPars(M)
        parent = type('C', (), {'par': pp, 'op': staticmethod(lambda n: None)})()
        logic_mod = type('LM', (), dict((k, v) for k, v in L.items() if not k.startswith('__')))
        t = {'s': 10.0}
        env = {'op': lambda p: type('D', (), {'module': logic_mod})() if p == 'gi_logic' else None,
               'absTime': type('T', (), {'seconds': property(lambda self: t['s'])})(),
               'ParMode': type('PM', (), {'EXPRESSION': 'e'})}
        exec(RACK['PTS_CB'], env)
        s = SOp(parent)
        env['onCook'](s)
        t['s'] += 1 / 60.0
        env['onCook'](s)
        self.assertEqual([c.name for c in s.chans], ['x', 'y', 'vx', 'vy'])
        self.assertEqual(len(s.chans[0].v), 16)
        self.assertTrue((s.chans[0].v > -1).all())
        self.assertGreater(np.abs(s.chans[2].v).max(), 0.0)          # velocities after the second frame


if __name__ == '__main__':
    unittest.main()
