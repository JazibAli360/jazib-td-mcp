"""Offline tests for GEN_clone (G-CLONE): builders/gen_clone_logic.py, builders/gen_clone.py,
builders/glsl/gen_clone_layout.glsl / gen_clone_vert.glsl / gen_clone_pixel.glsl.
Run: python3 -I -m unittest discover -s test -p 'test_gen_clone.py'
GLSL: compiled with glslc (OpenGL target) against stubs of the TD functions (compute with and without the shared
effectors block, MAT vertex + pixel): a syntax / type check, NOT a TD compile (LIVE CHECK C1)."""
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
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
import gen_clone_logic as L  # noqa: E402
import effectors_logic as EL  # noqa: E402


def rd(p):
    with open(p) as fh:
        return fh.read()


def P(**kw):
    d = dict(L.DEFAULTS)
    d.update(kw)
    return d


def U(n=None, t=0.0, **kw):
    p = P(**kw)
    if n is None:
        n = L.count_for(p['Mode'], p['Count'], p['Countx'], p['County'], p['Countz'])
    return L.uniform_values(p, n, t), n


def close(a, b, eps=1e-6):
    return all(abs(x - y) <= eps for x, y in zip(a, b))


class Files(unittest.TestCase):
    def test_ascii(self):
        for f in [os.path.join(BUILDERS, x) for x in ('gen_clone.py', 'gen_clone_logic.py')] + \
                [os.path.join(GLSL, x) for x in ('gen_clone_layout.glsl', 'gen_clone_vert.glsl',
                                                 'gen_clone_pixel.glsl')]:
            with open(f, 'rb') as fh:
                self.assertTrue(all(b < 128 for b in fh.read()), f)

    def test_uniform_spec_matches_glsl(self):
        g = rd(os.path.join(GLSL, 'gen_clone_layout.glsl'))
        declared = re.findall(r'^uniform vec4 (\w+);', g, flags=re.M)
        self.assertEqual(declared, [n for n, _ in L.U])
        for n, toks in L.U:
            self.assertEqual(len(toks), 4, n)

    def test_mirror_constants_in_glsl(self):
        g = rd(os.path.join(GLSL, 'gen_clone_layout.glsl'))
        for frag in ('747796405u', '2891336453u', '277803737u', '1664525u', '7919u', '73856093u', '19349663u',
                     '83492791u', 'seed + 11u', 'seed + 21u', 'seed + 23u', 'seed + 10u', 'uM4.z * float(n)',
                     'uC7.w - toff / 60.0', 'T.x / 5'):
            self.assertIn(frag, g)
        v = rd(os.path.join(GLSL, 'gen_clone_vert.glsl'))
        self.assertIn('ivec2(5 * (i % cw), i / cw)', v)
        self.assertEqual(L.TEXELS, 5)

    def test_loops_bounded(self):
        for f in ('gen_clone_layout.glsl', 'gen_clone_vert.glsl', 'gen_clone_pixel.glsl'):
            for m in re.finditer(r'for\s*\(([^;]*);([^;]*);', rd(os.path.join(GLSL, f))):
                self.assertRegex(m.group(2).strip(), r'<\s*[0-9]+$', (f, m.group(2)))


class Counts(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(L.count_for('grid', 0, 5, 9, 1), 45)
        self.assertEqual(L.count_for('grid', 0, 0, 3, 2), 6)
        self.assertEqual(L.count_for('radial', 16, 5, 9, 1), 16)
        self.assertEqual(L.count_for('points', 0, 1, 1, 1, npts=100, step=3), 34)
        self.assertEqual(L.tex_size(45), (225, 1))
        self.assertEqual(L.tex_size(1024), (5120, 1))
        self.assertEqual(L.tex_size(5000), (5120, 5))
        self.assertEqual(L.tex_size(0), (5, 1))

    def test_count_of_runtime(self):
        par = lambda v: types.SimpleNamespace(eval=lambda: v)          # noqa: E731
        c = types.SimpleNamespace(par=types.SimpleNamespace(**dict((k, par(v)) for k, v in dict(
            Mode='points', Count=1, Countx=1, County=1, Countz=1, Pointstep=2).items())),
            op=lambda n: types.SimpleNamespace(width=10, height=3))
        self.assertEqual(L.count_of(c), 15)


class Layout(unittest.TestCase):
    def test_grid(self):
        u, n = U()
        t0 = L.clone_ref(0, u)[0]
        self.assertTrue(close(t0[:3], (-2 * 0.42, -4 * 0.42, 0.0)))
        self.assertTrue(close(L.clone_ref(22, u)[0][:3], (0.0, 0.0, 0.0)))
        self.assertEqual(t0[3], 0.35)
        self.assertEqual(L.clone_ref(n, u)[0], (0.0,) * 4)              # past the count: zero (hidden)

    def test_radial_full_ring_and_align(self):
        u, n = U(Mode='radial', Count=16, Radius=1.3, Align=1)
        for i in range(n):
            p = L.clone_ref(i, u)[0]
            self.assertAlmostEqual(math.hypot(p[0], p[1]), 1.3, 6)
            self.assertAlmostEqual(math.degrees(math.atan2(p[1], p[0])) % 360, (22.5 * i) % 360, 4)
        tex = L.clone_ref(4, u)                                         # at 90 deg: card up (+y) points outward (+y)
        tip = L.vertex_ref(tex, (0.0, 0.5, 0.0))
        self.assertTrue(close(tip, (0.0, 1.3 + 0.5 * 0.35, 0.0), 1e-6))
        tex = L.clone_ref(0, u)                                         # at 0 deg: card up -> +x
        tip = L.vertex_ref(tex, (0.0, 0.5, 0.0))
        self.assertTrue(close(tip, (1.3 + 0.5 * 0.35, 0.0, 0.0), 1e-6))

    def test_radial_arc_ends_inclusive(self):
        u, n = U(Mode='radial', Count=5, Arcstart=0.0, Arcend=180.0, Radius=1.0)
        self.assertTrue(close(L.clone_ref(4, u)[0][:3], (-1.0, 0.0, 0.0), 1e-6))

    def test_linear_centred(self):
        u, n = U(Mode='linear', Count=5, Liny=0.25)
        self.assertTrue(close(L.clone_ref(0, u)[0][:3], (0.0, -0.5, 0.0)))
        self.assertTrue(close(L.clone_ref(4, u)[0][:3], (0.0, 0.5, 0.0)))
        u, n = U(Mode='linear', Count=5, Liny=0.25, Centre=0)
        self.assertTrue(close(L.clone_ref(0, u)[0][:3], (0.0, 0.0, 0.0)))

    def test_path_circle_and_helix(self):
        u, n = U(Mode='path', Count=8, Pathshape='circle', Pathsize=1.0)
        for i in range(n):
            p = L.clone_ref(i, u)[0]
            self.assertAlmostEqual(math.hypot(p[0], p[1]), 1.0, 6)
        u, n = U(Mode='path', Count=11, Pathshape='helix', Pathsize=0.9, Pathturns=2.0, Helixheight=4.0)
        self.assertAlmostEqual(L.clone_ref(0, u)[0][1], -2.0, 6)
        self.assertAlmostEqual(L.clone_ref(10, u)[0][1], 2.0, 6)

    def test_path_speed_moves(self):
        a, _ = U(Mode='path', Count=4, Pathshape='circle', Pathspeed=0.25, t=0.0)
        b, _ = U(Mode='path', Count=4, Pathshape='circle', Pathspeed=0.25, t=1.0)
        pa, pb = L.clone_ref(0, a)[0], L.clone_ref(0, b)[0]
        self.assertTrue(close(pb[:3], (0.0, 1.2, 0.0), 1e-6))           # quarter turn
        self.assertTrue(close(pa[:3], (1.2, 0.0, 0.0), 1e-6))

    def test_path_tangent_align_x(self):
        u, n = U(Mode='path', Count=4, Pathshape='circle', Pathsize=1.0, Align=1, Alignaxis='x')
        tex = L.clone_ref(0, u)                                         # at (1, 0): tangent +y
        tip = L.vertex_ref(tex, (1.0, 0.0, 0.0))
        self.assertTrue(close(tip, (1.0, 0.35, 0.0), 1e-4))

    def test_points(self):
        pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 1.0, 0.0), (3.0, 1.0, 1.0)]
        u, _ = U(Mode='points', Pointstep=2, n=2)
        self.assertTrue(close(L.clone_ref(1, u, pts=pts)[0][:3], (2.0, 1.0, 0.0)))

    def test_random_box_and_seed(self):
        u, n = U(Mode='random', Count=200, Boxx=2.0, Boxy=4.0, Boxz=1.0, Seed=3)
        ps = [L.clone_ref(i, u)[0][:3] for i in range(n)]
        for p in ps:
            self.assertTrue(abs(p[0]) <= 1.0 and abs(p[1]) <= 2.0 and abs(p[2]) <= 0.5)
        self.assertAlmostEqual(sum(p[0] for p in ps) / n, 0.0, delta=0.15)
        u2, _ = U(Mode='random', Count=200, Seed=4)
        self.assertNotEqual(L.clone_ref(0, u2)[0][:3], ps[0])


class Modifiers(unittest.TestCase):
    def test_step(self):
        u, _ = U(Steprz=10.0, Stepscale=0.1, Stephue=0.0)
        tex = L.clone_ref(3, u)
        w, x, y, z = tex[1]
        self.assertAlmostEqual(2 * math.degrees(math.atan2(z, w)), 30.0, 6)
        self.assertAlmostEqual(tex[0][3], 0.35 * 1.3, 9)

    def test_random_bounded(self):
        u, n = U(Randpx=0.2, Randscale=0.5, Randhue=0.3, Seed=9)
        base, _ = U(Seed=9)
        for i in range(n):
            a, b = L.clone_ref(i, u)[0], L.clone_ref(i, base)[0]
            self.assertLessEqual(abs(a[0] - b[0]), 0.2 + 1e-9)
            self.assertTrue(0.35 * 0.5 - 1e-9 <= a[3] <= 0.35 * 1.5 + 1e-9)

    def test_noise_animates(self):
        a, _ = U(Noisepos=0.3, Noisespeed=1.0, t=0.0)
        b, _ = U(Noisepos=0.3, Noisespeed=1.0, t=0.5)
        self.assertNotEqual(L.clone_ref(5, a)[0], L.clone_ref(5, b)[0])
        for i in range(45):
            d = [abs(x - y) for x, y in zip(L.clone_ref(i, a)[0][:3], L.clone_ref(i, U()[0])[0][:3])]
            self.assertLessEqual(max(d), 0.3 + 1e-9)

    def test_time_offset(self):
        u, _ = U(Timeoffset=2.0)
        self.assertEqual(L.clone_ref(7, u)[3][3], 14.0)
        u, _ = U(Timeoffset=10.0, Timemode='distance')
        self.assertAlmostEqual(L.clone_ref(0, u)[3][3], 10.0 * math.hypot(2 * 0.42, 4 * 0.42), 6)
        a, _ = U(Noisepos=0.3, Noisespeed=1.0, Timeoffset=30.0, t=1.0)   # 30 frames late = 0.5 s
        b, _ = U(Noisepos=0.3, Noisespeed=1.0, t=0.5)
        self.assertTrue(close(L.clone_ref(1, a)[0], L.clone_ref(1, b)[0], 1e-9))

    def test_hue(self):
        self.assertTrue(close(L.hue_rot((1.0, 0.0, 0.0), 1.0 / 3.0), (0.0, 1.0, 0.0), 1e-6))
        u, _ = U(Colourr=1.0, Colourg=0.0, Colourb=0.0, Stephue=1.0 / 3.0)
        self.assertTrue(close(L.clone_ref(1, u)[2][:3], (0.0, 1.0, 0.0), 1e-6))

    def test_map(self):
        u, _ = U(Mapmode='both', Mapamount=1.0)
        tex = L.clone_ref(0, u, map_rgb=(0.5, 0.5, 0.5))
        self.assertAlmostEqual(tex[0][3], 0.35 * 0.5, 9)
        self.assertTrue(close(tex[2][:3], (0.5, 0.5, 0.5)))

    def test_hash_range(self):
        v = [L.h01(i, 7) for i in range(2000)]
        self.assertTrue(all(0.0 <= x < 1.0 for x in v))
        self.assertAlmostEqual(sum(v) / len(v), 0.5, delta=0.03)
        self.assertTrue(all(0.0 <= L.vnoise((x * 0.37, x * 0.11, 0.5), 3) <= 1.0 for x in range(200)))


class Effectors(unittest.TestCase):
    def test_actions(self):
        u, _ = U(Effoffx=0.5, Effpush=0.2, Effrotz=90.0, Effscale=-0.5, Effcolourmix=1.0, Efftime=10.0)
        base = L.clone_ref(0, U()[0])
        tex = L.clone_ref(0, u, w=0.5, grad=(0.0, 1.0, 0.0))
        self.assertTrue(close(tex[0][:3], (base[0][0] + 0.25, base[0][1] + 0.1, 0.0), 1e-9))
        self.assertAlmostEqual(tex[0][3], 0.35 * 0.75, 9)
        self.assertAlmostEqual(2 * math.degrees(math.atan2(tex[1][3], tex[1][0])), 45.0, 6)
        self.assertTrue(close(tex[2][:3], (1.0, 0.65, 0.55), 1e-9))       # half way to (1, 0.3, 0.1)
        self.assertEqual(tex[3][3], 5.0)
        self.assertEqual(tex[4][0], 0.5)

    def test_hide_and_vanish(self):
        u, _ = U(Effhide=0.4)
        self.assertEqual(L.clone_ref(0, u, w=0.5)[0][3], 0.0)
        self.assertEqual(L.clone_ref(0, u, w=0.5)[4][2], 1.0)
        u, _ = U(Effscale=-1.0)
        self.assertEqual(L.clone_ref(0, u, w=1.0)[0][3], 0.0)

    def test_weight_reference_exists(self):
        """The clone weight is effectors_logic's pxeW (shared code, tested in test_effectors)."""
        self.assertTrue(callable(EL.ref_weight))
        self.assertIn('pxeConsumerW(pos, b)', rd(os.path.join(GLSL, 'gen_clone_layout.glsl')))


class LiveHelper(unittest.TestCase):
    def test_compare_on_a_fake_top(self):
        try:
            import numpy as np
        except ImportError:                                            # pragma: no cover
            self.skipTest('numpy missing')
        u, n = U(Mode='radial', Count=7, Align=1, Randpx=0.1, Steprz=5.0)
        w, h = L.tex_size(n)
        a = np.zeros((h, w, 4), dtype=np.float32)
        for i in range(n):
            for k, t in enumerate(L.clone_ref(i, u)):
                a[i // L.cw(n), L.TEXELS * (i % L.cw(n)) + k] = t
        a[0, 6] *= -1.0                                                # clone 1 quaternion negated: same rotation
        pars = {}
        for k, (nm, v) in enumerate(u.items()):
            pars['vec%dname' % k] = types.SimpleNamespace(eval=lambda nm=nm: nm)
            for j, ax in enumerate('xyzw'):
                pars['vec%dvalue%s' % (k, ax)] = types.SimpleNamespace(eval=lambda v=v, j=j: v[j])
        g = types.SimpleNamespace(seq=types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=len(u))),
                                  par=types.SimpleNamespace(**pars), numpyArray=lambda: a)
        c = types.SimpleNamespace(op=lambda nm: g)
        d, _i, _k, cnt = L.compare(c)
        self.assertEqual(cnt, 7)
        self.assertLess(d, 1e-5)


class RingAndPath(unittest.TestCase):
    def test_ring_slice(self):
        self.assertEqual(L.ring_slice(0, 30), 29)
        self.assertEqual(L.ring_slice(5.4, 30), 24)
        self.assertEqual(L.ring_slice(99, 30), 0)
        self.assertEqual(L.ring_slice(5, 30, 'newestfirst'), 5)

    def test_resample_even(self):
        pts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 3.0, 0.0)]
        r = L.pts_resample(pts, 5)
        self.assertEqual(len(r), 5)
        self.assertTrue(close(r[0], (0.0, 0.0, 0.0)) and close(r[-1], (1.0, 3.0, 0.0)))
        d = [math.dist(a, b) for a, b in zip(r, r[1:])]
        self.assertTrue(all(abs(x - 1.0) < 1e-9 for x in d[1:]))           # 4 units / 4 steps
        self.assertEqual(L.pts_resample([(1.0, 2.0, 3.0)], 10), [(1.0, 2.0, 3.0)])


# ------------------------------------------------------------------------------------------------ GLSL
STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[2];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""
STUB_MAT = """#version 460
struct TDMatrix { mat4 world; mat4 cam; mat4 camInverse; mat4 proj; };
uniform TDMatrix uTDMats[1];
int TDCameraIndex() { return 0; }
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""
STUB_VERT = STUB_MAT + """in vec3 P;
in vec3 N;
in vec3 uv[1];
int TDInstanceID() { return gl_InstanceID; }
vec3 TDPos() { return P; }
vec3 TDNormal() { return N; }
vec4 TDDeform(vec3 p) { return uTDMats[0].world * vec4(p, 1.0); }
vec3 TDDeformNorm(vec3 n) { return mat3(uTDMats[0].world) * n; }
vec4 TDWorldToProj(vec4 p) { return uTDMats[0].proj * uTDMats[0].cam * p; }
void TDWritePickingValues() {}
"""
STUB_PIX = STUB_MAT + """void TDCheckDiscard() {}
"""


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, ext, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.' + ext)
            with open(p, 'w') as fh:
                fh.write(text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def test_compute_with_and_without_effectors(self):
        code = rd(os.path.join(GLSL, 'gen_clone_layout.glsl'))
        pre = EL.consumer_prefix(rd(os.path.join(GLSL, 'px_common.glsl')), rd(os.path.join(GLSL, 'eff_consumer.glsl')))
        self._ok(STUB_COMPUTE + EL.with_prefix(code, pre), 'comp', 'clones + effectors')
        self._ok(STUB_COMPUTE + code, 'comp', 'clones alone')

    def test_mat(self):
        self._ok(STUB_VERT + rd(os.path.join(GLSL, 'gen_clone_vert.glsl')), 'vert', 'vertex')
        self._ok(STUB_PIX + rd(os.path.join(GLSL, 'gen_clone_pixel.glsl')), 'frag', 'pixel')


# ------------------------------------------------------------------------------------------------ dry build
class _Par:
    def __init__(self):
        self.val, self.expr, self.mode, self.label = None, '', 'c', ''
        self.normMin = self.normMax = self.default = 0
        self.menuNames = []

    def eval(self):
        return self.val


class _Pars:
    def __getattr__(self, k):
        if k.startswith('__') or k[:1].isupper():
            raise AttributeError(k)
        p = _Par()
        object.__setattr__(self, k, p)
        return p

    def __setattr__(self, k, v):
        getattr(self, k).val = v


class _Conn:
    def __init__(self):
        self.connections, self.inOP = [], None

    def connect(self, src):
        self.connections = [types.SimpleNamespace(owner=getattr(src, 'owner', src))]


class _Out:
    def __init__(self, owner):
        self.owner = owner

    def connect(self, conn):
        conn.connections = [types.SimpleNamespace(owner=self.owner)]


class _Page:
    def __init__(self, comp, name):
        self.comp, self.name = comp, name

    def _p(self, nm, label='', n=1, suffix=''):
        out = []
        for s in (suffix or [''] * n):
            p = _Par()
            p.label = label
            object.__setattr__(self.comp.par, nm + s, p)
            self.comp.custom.append(nm + s)
            out.append(p)
        return out

    def appendFloat(self, nm, label=''):
        return self._p(nm, label)
    appendInt = appendToggle = appendStr = appendPulse = appendMenu = appendFloat

    def appendRGB(self, nm, label=''):
        return self._p(nm, label, suffix=['r', 'g', 'b'])

    def appendXYZ(self, nm, label=''):
        return self._p(nm, label, suffix=['x', 'y', 'z'])


class _Op:
    def __init__(self, cls, name, parent=None):
        self.OPType, self.name, self.par, self.text, self.comment = cls, name, _Pars(), '', ''
        self.inputConnectors = [_Conn() for _ in range(3 if cls == 'glslTOP' else 6)]
        self.outputConnectors = [_Out(self)]
        ns = types.SimpleNamespace
        self.seq = ns(vec=ns(numBlocks=1), sampler=ns(numBlocks=1), array=ns(numBlocks=0))
        self.children, self.customPages, self.custom = {}, [], []
        self.path = (parent.path if parent else '') + '/' + name
        self.dock, self.valid, self.viewer, self.allowCooking = None, True, False, True
        self.render = self.display = False
        self.isCOMP = cls.endswith('COMP')

    def op(self, n):
        return self.children.get(n)

    def create(self, cls, n):
        o = _Op(cls.__name__, n, self)
        self.children[n] = o
        return o

    def appendCustomPage(self, n):
        pg = _Page(self, n)
        self.customPages.append(pg)
        return pg


CLASSES = ('inTOP', 'outTOP', 'glslTOP', 'textDAT', 'switchTOP', 'selectTOP', 'moviefileinTOP', 'texture3dTOP',
           'scriptCHOP', 'choptoTOP', 'constantTOP', 'constantCHOP', 'selectCHOP', 'geometryCOMP', 'cameraCOMP',
           'nullCOMP', 'renderTOP', 'glslMAT', 'gridSOP', 'boxSOP', 'sphereSOP', 'torusSOP', 'selectSOP', 'switchSOP',
           'transformSOP', 'nullSOP', 'baseCOMP')


class DryBuild(unittest.TestCase):
    def build(self):
        root = _Op('baseCOMP', 'lab')
        lay = types.SimpleNamespace(module=types.SimpleNamespace(layout_stages=lambda *a, **k: 'ok',
                                                                 safe_destroy=lambda o: None))
        ns = dict((c, type(c, (), {})) for c in CLASSES)
        ns['ParMode'] = types.SimpleNamespace(EXPRESSION='e', CONSTANT='c')
        ns['safe_destroy'] = lambda o: None
        ns['op'] = lambda p: lay if p == '/jazib_mcp/handlers' else root
        ns['__name__'] = 'gen_clone_dry'
        exec(rd(os.path.join(BUILDERS, 'gen_clone.py')), ns)
        ns['build']('/project1/lab', panel=False)
        return root.op('GEN_clone'), ns

    def test_build(self):
        c, ns = self.build()
        for n in ('clone_logic', 'in1', 'tex_src', 'ring', 'pts_chop', 'pts_src', 'map_src', 'clones',
                  'clones_compute', 'geo', 'clonemat', 'clone_vert', 'clone_pixel', 'cam', 'render', 'out1',
                  'eff_in', 'eff_none'):
            self.assertIn(n, c.children, n)
        g = c.op('clones')
        self.assertEqual([cn.connections[0].owner.name for cn in g.inputConnectors if cn.connections],
                         ['pts_src', 'map_src'])
        txt = c.op('clones_compute').text
        self.assertIn('uniform samplerBuffer uEffRows;', txt)
        names = []
        for k in range(40):
            nm = getattr(g.par, 'vec%dname' % k).val
            if not nm:
                continue
            names.append(nm)
            self.assertIn('uniform vec4 %s;' % nm, txt, nm)
            for comp in 'xyzw':
                p = getattr(g.par, 'vec%dvalue%s' % (k, comp))
                if p.mode == 'e':
                    compile(p.expr, '<expr>', 'eval')
        for nm in [n for n, _ in L.U] + ['uEffSel', 'uEffIds', 'uEffMix', 'uEffFall']:
            self.assertIn(nm, names)
        self.assertEqual(g.par.array0name.val, 'uEffRows')
        geo = c.op('geo')
        self.assertTrue(geo.par.instancing.val)
        self.assertEqual(geo.par.material.val, 'clonemat')
        self.assertTrue(geo.op('s_out').render)
        sw = geo.op('s_sw')
        self.assertEqual([cn.connections[0].owner.name for cn in sw.inputConnectors if cn.connections],
                         ['s_card', 's_box', 's_sphere', 's_torus', 's_sop'])
        self.assertIn('Source.menuIndex', sw.par.input.expr)          # Switch SOP's par is `input` (live 31550)
        mat = c.op('clonemat')
        self.assertEqual([getattr(mat.par, 'sampler%dname' % k).val for k in range(3)], ['sClones', 'sTex', 'sRing'])
        vt = c.op('clone_vert').text + c.op('clone_pixel').text
        for k in range(4):
            nm = getattr(mat.par, 'vec%dname' % k).val
            self.assertIn('uniform vec4 %s;' % nm, vt)
        for o in list(c.children.values()) + list(geo.children.values()):
            for pn in ('index', 'input', 'play', 'cachesize', 'resolutionw', 'top', 'sop', 'scale', 'numinstances'):
                e = getattr(o.par, pn).expr
                if e:
                    compile(e, '<expr>', 'eval')

    def test_pages_and_presets(self):
        _c, ns = self.build()
        Lg = ns['load_logic']()
        names = []
        for _pg, pars in ns['pages'](Lg) + [('Effectors', ns['eff_page'](ns['_eff_ns']()))]:
            for n, style, *_ in pars:
                names += [n + s for s in ('xyz' if style == 'XYZ' else ('rgb' if style == 'RGB' else ['']))]
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            self.assertRegex(n, r'^[A-Z][a-z0-9]*$')
        for _n, toks in L.U:
            for t in toks:
                if isinstance(t, str) and not t.startswith('@'):
                    self.assertIn(t.rstrip('#'), names, t)
        for _s, _nm, vals in ns['presets'](Lg):
            for k in vals:
                self.assertIn(k, names, k)
            for k in L.DEFAULTS:
                self.assertIn(k, vals)

    def test_script_callbacks_parse(self):
        _c, ns = self.build()
        compile(ns['SCRIPT_PTS'], 'pts_chop', 'exec')


if __name__ == '__main__':
    unittest.main()
