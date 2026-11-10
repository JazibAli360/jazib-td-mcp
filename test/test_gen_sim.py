"""Offline tests for GEN_sim (builders/gen_sim.py rack variant + shared GLSL / logic), and helpers the per-module
tests (test_gen_sim_<module>.py) import. Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sim*.py'
GLSL checks compile with glslc (OpenGL target) against stubs of the TD compute built-ins: a syntax/type check, NOT a TD
compile (LIVE CHECK G1 in docs/builds/gen_sim.md). Expressions are evaluated against a fake parent()/op()/absTime."""
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
MODULES = ['ca', 'voronoi', 'dla', 'blobs', 'lic', 'ripple', 'lavalamp', 'sand']
TD_STUB = """#version 460
uniform sampler2D sTD2DInputs[3];
uniform int uTDPass;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""


def rack():
    ns = {}
    with open(os.path.join(B, 'gen_sim.py')) as fh:
        exec(fh.read(), ns)
    return ns


RACK = rack()
LOGIC = {}
with open(os.path.join(B, 'gen_sim_logic.py')) as _fh:
    exec(_fh.read(), LOGIC)


def module(name):
    ns = dict(RACK)
    with open(os.path.join(B, 'gen_sim_%s.py' % name)) as fh:
        exec(fh.read(), ns)
    return ns


def pars(M):
    """{name: (style, default, opts)} of every page."""
    return dict((n, (s, d, o)) for _pg, ps in M['PAGES'] for n, s, d, o in ps)


# ------------------------------------------------------------------ fake TD for expressions
class _Par(object):
    def __init__(self, name, style, val, opts):
        self.name, self.style, self.val, self.o = name, style, val, opts

    def eval(self):
        if self.style == 'Menu':
            return self.val
        if self.style in ('TOP', 'CHOP'):
            return None
        return self.val

    @property
    def menuIndex(self):
        return self.o['names'].index(self.val)


class _Pars(object):
    def __init__(self, M, over=None):
        self._p = {}
        for n, (s, d, o) in pars(M).items():
            if s == 'RGB':
                for ch, v in zip('rgb', d):
                    self._p[n + ch] = _Par(n + ch, 'Float', v, o)
            else:
                self._p[n] = _Par(n, s, d, o)
        for k, v in (over or {}).items():
            p = self._p[k]
            p.val = p.o['names'][v] if p.style == 'Menu' and isinstance(v, int) else v

    def __getattr__(self, k):
        return self._p[k]


class _Op(object):
    def __init__(self, w, h):
        self.width, self.height = w, h


class _Time(object):
    frame = 1000
    seconds = 1000 / 60.0


def ev(expr, M, over=None, in_w=1080, in_h=1920, frame=1000):
    """Evaluate a TD par expression of module M with its defaults (+ over) and an in1 of in_w x in_h."""
    pp = _Pars(M, over)

    class _Parent(object):
        par = pp
    t = _Time()
    t.frame, t.seconds = frame, frame / 60.0
    env = {'parent': lambda *a: _Parent(), 'op': lambda name: _Op(in_w, in_h), 'absTime': t, 'math': math, 'me': None}
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
    """Every uniform the build sets is declared in the shader and every non-look declared uniform is set."""
    names = [u for u, _e in U]
    test.assertEqual(len(names), len(set(names)), what)
    decl = declared_uniforms(text)
    for u in names:
        test.assertIn(u, decl, '%s sets %s, the shader does not declare it' % (what, u))
    for u in decl - {'uLook', 'uCa', 'uCb'}:
        test.assertIn(u, names, '%s declares %s, the build never sets it' % (what, u))
    for _u, ex in U:
        test.assertEqual(len(ex), 4, what)


class Files(unittest.TestCase):
    def test_ascii(self):
        fs = ['gen_sim.py', 'gen_sim_logic.py'] + ['gen_sim_%s.py' % m for m in MODULES]
        fs += [os.path.join('glsl', f) for f in os.listdir(G) if f.startswith('gen_sim_')]
        for f in fs:
            with open(os.path.join(B, f), 'rb') as fh:
                fh.read().decode('ascii')

    def test_no_version_line(self):                       # TD adds the version line itself
        for f in os.listdir(G):
            if f.startswith('gen_sim_'):
                with open(os.path.join(G, f)) as fh:
                    self.assertNotIn('#version', fh.read(), f)


class Rack(unittest.TestCase):
    def test_reuses_fx_glitch_rack(self):
        for k in ('plan_chain', 'chain_edges', 'rewire', 'remove', '_instance'):
            self.assertIn(k, RACK)
        self.assertEqual(RACK['NAME'], 'GEN_sim')
        self.assertEqual(RACK['FIRST'], ('ca1', 'ca'))
        self.assertEqual(RACK['MODULES'], MODULES)
        self.assertTrue(RACK['module_file']('ca').endswith('builders/gen_sim_ca.py'))

    def test_chain_and_panic(self):
        e = RACK['chain_edges'](['ca1', 'blobs1'])
        self.assertIn(('blobs1', 0, 'ca1_slot'), e)
        self.assertEqual(e[-3:], [('panic', 0, 'blobs1_slot'), ('panic', 1, 'img_src'), ('out1', 0, 'panic')])

    def test_helpers_in_H(self):
        for k in ('mk', 'expr', 'sd', 'uniforms', 'glsl', 'pas', 'state', 'clock', 'pulses', 'out_sel'):
            self.assertIn(k, RACK['H'])

    def test_img_index_expression(self):
        class Cn(object):
            def __init__(self, n, wired):
                self.inOP = type('o', (), {'name': n})()
                self.connections = [1] if wired else []

        for mode, wired, want in (('auto', False, 0), ('auto', True, 1), ('black', True, 0), ('live', False, 1),
                                  ('test', True, 2)):
            par = type('p', (), {'Input': type('q', (), {'eval': staticmethod(lambda m=mode: m)})()})()
            parent = type('P', (), {'par': par, 'inputConnectors': [Cn('in1', wired)]})()
            self.assertEqual(eval(RACK['IMG_INDEX'], {'parent': lambda: parent}), want, (mode, wired))

    def test_colour_page_names(self):
        self.assertEqual(RACK['PALETTES'], LOGIC['PALETTES'])
        self.assertEqual(RACK['BLENDS'], LOGIC['BLENDS'])
        names = [n for n, *_ in RACK['colour_page']()[1]]
        self.assertEqual(names, ['Palette', 'Palshift', 'Blend', 'Colora', 'Colorb'])

    def test_glsl_text_prefixes_common(self):
        t = RACK['glsl_text']('gen_sim_clock')
        self.assertTrue(t.startswith('// gen_sim_common'))
        self.assertIn('gs_hash3', t)


class Logic(unittest.TestCase):
    def test_hash_matches_reaction_diffusion(self):         # the same lowbias32 hash3 as GN_reaction_diffusion
        R = {}
        with open(os.path.join(B, 'reaction_diffusion_logic.py')) as fh:
            exec(fh.read(), R)
        import numpy as np
        i = np.arange(-50, 50)
        self.assertTrue(np.array_equal(LOGIC['hash3'](i, i * 7 - 3, 11), R['hash3'](i, i * 7 - 3, 11)))
        h = LOGIC['hash3'](np.arange(100000), 3, 1)
        self.assertTrue(0 <= h.min() and h.max() < 1)
        self.assertAlmostEqual(float(h.mean()), 0.5, delta=0.005)

    def test_palette_and_blend(self):
        import numpy as np
        pal = LOGIC['palette']
        self.assertTrue(np.allclose(pal(np.array([0.0, 1.0]), 0, (0, 0, 0), (1, 0.5, 0)), [[0, 0, 0], [1, 0.5, 0]]))
        self.assertTrue(np.allclose(pal(np.array([1.0]), 1), [[1, 1, 1]]))           # fire tops out white
        base = np.array([[0.2, 0.4, 0.6, 1.0]])
        col, a = np.array([[0.5, 0.5, 0.5]]), np.array([0.5])
        self.assertTrue(np.allclose(LOGIC['blend'](base, col, a, 1, 1.0), [[0.6, 0.7, 0.8, 1.0]]))   # over
        self.assertTrue(np.allclose(LOGIC['blend'](base, col, a, 2, 0.0), base))                     # amount 0
        self.assertTrue(np.allclose(LOGIC['blend'](base, col, a, 7, 1.0), [[0.5, 0.5, 0.5, 0.5]]))   # alpha out


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        for mname in MODULES:
            M = module(mname)
            for k, t in M['shader_texts']().items():
                t.encode('ascii')
                glslc(self, t, '%s.%s' % (mname, k))
        glslc(self, RACK['glsl_text']('gen_sim_clock'), 'clock')

    def test_local_sizes_fit(self):                        # <= 1024 threads per group (T-110 (1))
        for f in os.listdir(G):
            if f.startswith('gen_sim_') and f != 'gen_sim_common.glsl':
                with open(os.path.join(G, f)) as fh:
                    m = re.search(r'local_size_x\s*=\s*(\d+),\s*local_size_y\s*=\s*(\d+)', fh.read())
                self.assertIsNotNone(m, f)
                self.assertLessEqual(int(m.group(1)) * int(m.group(2)), 1024, f)


class ModuleApi(unittest.TestCase):
    def test_template(self):
        for mname in MODULES:
            M = module(mname)
            self.assertEqual(M['MODULE'], mname)
            for k in ('PAGES', 'PANEL_PAGES', 'PRESETS', 'build', 'shader_texts'):
                self.assertIn(k, M, mname)
            names = [n for _pg, ps in M['PAGES'] for n, *_ in ps]
            self.assertEqual(names[0], 'Amount', mname)
            self.assertEqual(len(names), len(set(names)), mname)
            for n in names:
                self.assertRegex(n, r'^[A-Z][a-z0-9]*$', '%s.%s' % (mname, n))
            for pg in M['PANEL_PAGES']:
                self.assertIn(pg, [p for p, _ in M['PAGES']])
            self.assertIn('Colour', [p for p, _ in M['PAGES']])

    def test_presets_valid(self):
        for mname in MODULES:
            M = module(mname)
            P = pars(M)
            self.assertGreaterEqual(len(M['PRESETS']), 4, mname)
            slots = [s for s, _n, _v in M['PRESETS']]
            self.assertEqual(len(slots), len(set(slots)), mname)
            for _s, pname, vals in M['PRESETS']:
                for k, v in vals.items():
                    if k not in P and k[:-1] in P and P[k[:-1]][0] == 'RGB':   # full-state presets: RGB channels
                        continue
                    self.assertIn(k, P, '%s preset %s: %s' % (mname, pname, k))
                    if P[k][0] == 'Menu':
                        self.assertTrue(0 <= v < len(P[k][2]['names']), (mname, pname, k, v))

    def test_state_modules_reset(self):
        for mname in ('ca', 'dla'):
            M = module(mname)
            P = pars(M)
            self.assertEqual(P['Reset'][0], 'Pulse')
            self.assertIn('Resetcount', P)
            for k in M['RESEED']:
                self.assertIn(k, P)
            self.assertIn("RESEED = %r" % list(M['RESEED']), RACK['PULSE_EXEC'] % list(M['RESEED']))


if __name__ == '__main__':
    unittest.main()
