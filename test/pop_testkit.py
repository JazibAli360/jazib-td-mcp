"""Shared helpers for test/test_pop_*.py (lane H, docs/builds/pop_lane_h.md). Not a test file itself.
- fake_build(builder_file): exec builders/<file> against fake TD classes and run build() -> (comp, reply).
- glslc_*: syntax/type checks of compute / GLSL MAT vertex / pixel shaders against stubs of TD's declarations.
  A glslc pass is NOT a TD compile (that is LIVE CHECK 1 in each item of pop_lane_h.md)."""
import os
import re
import shutil
import subprocess
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
HAVE_GLSLC = bool(shutil.which('glslc'))

STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[4];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
uniform TDTexInfo uTD2DInfos[4];
layout(rgba32f) uniform image2DArray mTDComputeOutputs[4];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""

STUB_VERT = """#version 460
in vec3 P;
in vec3 N;
in vec3 uv[8];
in vec4 Cd;
uniform mat4 uStubMVP;
vec3 TDPos() { return P; }
vec3 TDNormal() { return N; }
vec4 TDDeform(vec3 p) { return vec4(p, 1.0); }
vec4 TDDeform(vec4 p) { return p; }
vec3 TDDeformNorm(vec3 n) { return n; }
vec4 TDWorldToProj(vec4 w) { return uStubMVP * w; }
vec4 TDWorldToProj(vec3 w) { return uStubMVP * vec4(w, 1.0); }
void TDWritePickingValues() {}
"""

STUB_PIXEL = """#version 460
vec4 TDOutputSwizzle(vec4 c) { return c; }
void TDCheckDiscard() {}
"""


def _glslc(text, ext):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.' + ext)
        with open(p, 'w') as fh:
            fh.write(text)
        r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                            '-o', os.devnull, p], capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:3000]


def glslc_compute(body):
    return _glslc(STUB_COMPUTE + body, 'comp')


def glslc_vert(body):
    return _glslc(STUB_VERT + body, 'vert')


def glslc_pixel(body):
    return _glslc(STUB_PIXEL + body, 'frag')


def bounded_loops(text):
    """Every `for (int k = 0; k < X; ...)` bound must be a literal or a #define / const (T-35: no runaway loops)."""
    bad = []
    consts = set(re.findall(r'#define\s+(\w+)\s+\d+', text)) | set(re.findall(r'const\s+int\s+(\w+)\s*=', text))
    for b in re.findall(r'for\s*\(\s*(?:int|uint)\s+\w+\s*=\s*[^;]+;\s*\w+\s*<=?\s*([\w.]+)\s*;', text):
        if not (b.isdigit() or b in consts):
            bad.append(b)
    return bad


# ------------------------------------------------------------------------------------------------- fake TD
class FakePar(object):
    def __init__(self, name=''):
        self.name = name
        self.val, self.expr, self.mode = None, None, None
        self.default = None
        self.menuNames, self.menuLabels = [], []
        self.normMin = self.normMax = self.min = self.max = None
        self.clampMin = self.clampMax = False

    def eval(self):
        return self.val

    def pulse(self):
        pass


class FakePars(object):
    def __init__(self):
        object.__setattr__(self, '_d', {})

    def __getattr__(self, k):
        if k.startswith('__'):
            raise AttributeError(k)
        d = object.__getattribute__(self, '_d')
        if k not in d:
            d[k] = FakePar(k)
        return d[k]

    def __setattr__(self, k, v):
        getattr(self, k).val = v

    def names(self):
        return list(object.__getattribute__(self, '_d'))


class FakeConn(object):
    def __init__(self):
        self.src = None

    def connect(self, s):
        self.src = s


class FakeSeq(object):
    def __init__(self):
        self.numBlocks = 0


class FakePage(object):
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def _add(self, n):
        p = getattr(self.owner.par, n)
        p.val = None
        self.owner.custom.append(n)
        return [p]

    appendFloat = appendInt = appendMenu = appendToggle = appendStr = appendTOP = appendPulse = (
        lambda self, n, label='': self._add(n))


class FakeOp(object):
    def __init__(self, cls, name, parent=None):
        self.OPType, self.name = cls, name
        self.path = (parent.path if parent else '/fake') + '/' + name
        self.par = FakePars()
        self.inputConnectors = [FakeConn() for _ in range(8)]
        self.seq = types.SimpleNamespace(vec=FakeSeq(), sampler=FakeSeq(), const=FakeSeq(), array=FakeSeq())
        self.text, self.comment, self.dock = '', '', None
        self.valid, self.viewer, self.render, self.display, self.allowCooking = True, False, False, False, True
        self.ops, self.custom, self.customPages = {}, [], []
        self.isCOMP = cls.endswith('COMP')

    @property
    def children(self):
        return list(self.ops.values())

    @property
    def inputs(self):
        return [c.src for c in self.inputConnectors if c.src is not None]

    def op(self, n):
        return self.ops.get(n)

    def create(self, cls, name):
        o = FakeOp(cls.__name__, name, self)
        self.ops[name] = o
        return o

    def appendCustomPage(self, name):
        pg = FakePage(self, name)
        self.customPages.append(pg)
        return pg


TD_CLASSES = ['inTOP', 'moviefileinTOP', 'outTOP', 'glslTOP', 'textDAT', 'switchTOP', 'constantTOP', 'feedbackTOP', 'constantCHOP',
              'speedCHOP', 'parameterexecuteDAT', 'gridPOP', 'glslMAT', 'geometryCOMP', 'selectPOP', 'cameraCOMP',
              'renderTOP', 'scriptTOP', 'scriptCHOP', 'baseCOMP', 'nullTOP', 'selectTOP', 'rampTOP', 'levelTOP',
              'compositeTOP', 'blurTOP', 'nullCHOP', 'inCHOP', 'spherePOP', 'torusPOP', 'boxPOP', 'nullPOP',
              'tableDAT', 'lfoCHOP', 'mathTOP', 'resolutionTOP', 'analyzeTOP', 'toptoCHOP', 'particlePOP',
              'trailPOP', 'skinPOP', 'pointgeneratorPOP', 'noisePOP', 'mathCHOP', 'textTOP', 'nullCOMP']


def fake_namespace():
    root = FakeOp('baseCOMP', 'lab')
    ns = {}
    for c in TD_CLASSES:
        ns[c] = type(c, (), {})
    ns['ParMode'] = types.SimpleNamespace(EXPRESSION='expr', CONSTANT='const')
    ns['safe_destroy'] = lambda o: o.__dict__.update(valid=False)

    def op_(path):
        if path in ('/project1/lab', root.path):
            return root
        return None
    ns['op'] = op_
    ns['absTime'] = types.SimpleNamespace(seconds=0.0, frame=0)
    return ns, root


def fake_build(builder_file, **kw):
    """exec builders/<builder_file> with fake TD classes and call build('/project1/lab', panel=False, **kw)."""
    ns, root = fake_namespace()
    path = os.path.join(BUILDERS, builder_file)
    with open(path) as fh:
        exec(compile(fh.read(), path, 'exec'), ns)
    reply = ns['build']('/project1/lab', panel=False, **kw)
    comp = root.op(ns['NAME'])
    return comp, reply, ns


def src(o, k):
    s = o.inputConnectors[k].src
    return s.name if s is not None else None


def check_exprs(tc, comp):
    """Every expression string set on any op compiles as Python."""
    for o in comp.children:
        for n in o.par.names():
            e = getattr(o.par, n).expr
            if e is not None:
                compile(e, '%s.%s' % (o.name, n), 'eval')


def uniform_names(o):
    return [getattr(o.par, 'vec%dname' % k).val for k in range(o.seq.vec.numBlocks)]


def declared(text):
    return re.findall(r'^uniform\s+vec4\s+(\w+)\s*;', text, re.M)


def ascii_ok(path):
    with open(path, encoding='ascii') as fh:
        fh.read()
    return True
