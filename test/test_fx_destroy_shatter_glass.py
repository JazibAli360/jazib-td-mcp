"""Offline tests for FX_destroy shatter's Look glass (FX4 D11): builders/fx_destroy_shatter.py (shaders, uniforms,
pars, presets) + builders/fx_destroy_shatter_glass_logic.py (numpy mirror). No TD. GLSL checks are glslc compiles
against TD compute stubs (syntax/type check, not a TD compile: LIVE CHECK 1 in docs/builds/fx_destroy.md).
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_destroy_shatter_glass.py'"""
import ast
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
sys.path.insert(0, B)
import fx_destroy_shatter_glass_logic as G  # noqa: E402

NS = {}
exec(open(os.path.join(B, 'fx_destroy.py')).read(), NS)
M = dict(NS)
exec(open(os.path.join(B, 'fx_destroy_shatter.py')).read(), M)

HAVE_GLSLC = bool(shutil.which('glslc'))
STUB = """#version 460
uniform sampler2D sTD2DInputs[3];
layout(rgba32f) uniform image2DArray mTDComputeOutputs[3];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""


def glslc(text):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.comp')
        with open(p, 'w') as fh:
            fh.write(STUB + text)
        r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                            '-o', os.devnull, p], capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:3000]


def pars():
    out = {}
    for _page, plist in M['PAGES']:
        for name, style, default, o in plist:
            if style == 'RGB':
                for k in 'rgb':
                    out[name + k] = ('Float', None, {})
            out[name] = (style, default, o)
    return out


def declared(text):
    return re.findall(r'^uniform vec4 (\w+);', text, re.M)


def shader(name):
    return M[name].replace('%LIB%', NS['GLSL_LIB'])


@unittest.skipUnless(HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_state(self):
        ok, err = glslc(shader('STATE'))
        self.assertTrue(ok, err)

    def test_fx(self):
        ok, err = glslc(shader('FX'))
        self.assertTrue(ok, err)


class Wiring(unittest.TestCase):
    def check(self, U, text):
        self.assertEqual(sorted(u for u, _ in U), sorted(declared(text)))
        P = pars()
        for _u, ex in U:
            self.assertEqual(len(ex), 4)
            for e in ex:
                ast.parse(e, mode='eval')
                for ref in re.findall(r'parent\(\)\.par\.(\w+)', e):
                    self.assertIn(ref, P, ref)

    def test_fx_uniforms(self):
        self.check(M['fx_uniforms'](), shader('FX'))

    def test_state_uniforms(self):
        self.check(M['state_uniforms'](NS['pt_expr']), shader('STATE'))

    def test_inputs_and_shared_unchanged(self):
        fx = M['FX']
        self.assertLessEqual(max(int(i) for i in re.findall(r'sTD2DInputs\[(\d)\]', fx)), 2)   # 3 inputs (T-88)
        self.assertIn('shared vec2 sNb[MAXL * 9]', fx)
        self.assertIn('#define MAXL 96', fx)

    def test_state_voids_future_stamps(self):
        # T-155: Hittime / Resettime from another clock (TD relaunch, tox moved between TDs) must not block hits
        st = M['STATE']
        self.assertIn('float hv = uA.y <= now + 0.05 ? uA.y : -1.0;', st)
        self.assertIn('float rv = uA.z <= now + 0.05 ? uA.z : -1.0;', st)
        self.assertIn('b2.x <= now + 0.05', st)
        self.assertIn('rv >= b2.w', st)
        self.assertIn('if (!(b2.x <= now + 0.05)) b2.x = -1.0;', st)
        body = st.split('float rv = uA.z <= now + 0.05 ? uA.z : -1.0;', 1)[1]
        self.assertNotIn('uA.y', body)
        self.assertNotIn('uA.z', body)

    def test_rules(self):
        src = open(os.path.join(B, 'fx_destroy_shatter.py')).read()
        for bad in ('.destroy()', 'numpyArray', 'cookRate', "'vertexpixel'"):
            self.assertNotIn(bad, src)
        src.encode('ascii')
        open(os.path.join(B, 'fx_destroy_shatter_glass_logic.py')).read().encode('ascii')


class Presets(unittest.TestCase):
    def test_look_set_everywhere(self):
        P = pars()
        self.assertEqual(P['Look'][2]['names'], ['flat', 'glass'])
        self.assertEqual(P['Look'][1], 'flat')
        self.assertIn('Glass', M['PANEL_PAGES'])
        looks = {}
        for _s, name, v in M['PRESETS']:
            self.assertIn('Look', v, name)                # partial presets inherit (T-124 (1))
            looks[name] = v['Look']
            for k in v:
                self.assertIn(k, P, k)
        self.assertEqual(looks['slow-mo glass'], 1)
        self.assertEqual(sum(looks.values()), 1)
        self.assertLessEqual(len(M['PRESETS']), 5)


class Maths(unittest.TestCase):
    def setUp(self):
        self.p = G.defaults()

    def test_hash_matches_known_lowbias32(self):
        self.assertEqual(G.lb32(0), 0)
        v = [G.hsh(i, 7, 912) for i in range(200)]
        self.assertTrue(all(0.0 <= x < 1.0 for x in v))
        self.assertTrue(0.4 < float(np.mean(v)) < 0.6)

    def test_no_dispersion_equal_offsets(self):
        self.p['Dispersion'] = 0.0
        r, g, b = G.offsets(np.array([0.3, -0.2]), self.p)
        self.assertTrue(np.allclose(r, g) and np.allclose(g, b))

    def test_dispersion_orders_channels(self):
        r, g, b = G.offsets(np.array([0.3, -0.2]), self.p)
        self.assertLess(np.linalg.norm(r), np.linalg.norm(g))
        self.assertLess(np.linalg.norm(g), np.linalg.norm(b))

    def test_ior_one_or_thickness_zero_no_offset(self):
        for k, v in (('Ior', 1.0), ('Thickness', 0.0)):
            p = dict(self.p, **{k: v})
            for o in G.offsets(np.array([0.7, 0.4]), p):
                self.assertTrue(np.allclose(o, 0.0), k)

    def test_flat_pane_exact_picture(self):
        rnd = np.random.default_rng(3)
        img = rnd.random((40, 30, 4)).astype(np.float32)
        p = dict(self.p, Tilt=0.0, Bevel=0.0, Specular=0.0, Glasstint=(1.0, 1.0, 1.0))
        s = G.glass_slope(5, 0.7, 1.3, 3.0, (0.0, 1.0), p)
        self.assertTrue(np.allclose(s, 0.0))
        self.assertAlmostEqual(G.fresnel_rim(s, p), 0.0)
        out = G.glass_shade(img, (12.5, 20.5), s, p)
        self.assertTrue(np.allclose(out, img[20, 12]))

    def test_fresnel_grows_toward_grazing(self):
        rims = [G.fresnel_rim(np.array([t, 0.0]), self.p) for t in (0.0, 0.3, 0.8, 2.0, 6.0)]
        self.assertEqual(rims[0], 0.0)
        self.assertTrue(all(b > a for a, b in zip(rims, rims[1:])), rims)

    def test_bevel_only_near_edge(self):
        p = dict(self.p, Tilt=0.0)
        self.assertTrue(np.allclose(G.glass_slope(1, 0.0, 1.0, 20.0, (0.0, 1.0), p), 0.0))
        s = G.glass_slope(1, 0.0, 1.0, 0.0, (0.0, 1.0), p)
        self.assertTrue(np.allclose(s, [0.0, -1.0]))

    def test_tilt_turns_with_angle_and_grows_with_z(self):
        p = dict(self.p, Bevel=0.0)
        a = G.glass_slope(9, 0.0, 1.0, 50.0, (0, 1), p)
        b = G.glass_slope(9, math.pi / 2, 1.0, 50.0, (0, 1), p)
        c = G.glass_slope(9, 0.0, 2.0, 50.0, (0, 1), p)
        self.assertTrue(np.allclose(b, [-a[1], a[0]]))
        self.assertTrue(np.allclose(c, 2.0 * a))

    def test_sample_bilinear_hold(self):
        img = np.zeros((4, 4, 4), np.float32)
        img[:, 2:] = 1.0
        self.assertAlmostEqual(G.sample(img, 2.0, 1.5)[0], 0.5)
        self.assertAlmostEqual(G.sample(img, -10.0, 1.5)[0], 0.0)
        self.assertAlmostEqual(G.sample(img, 99.0, 1.5)[0], 1.0)

    def test_dispersion_splits_an_edge(self):
        img = np.zeros((20, 60, 4), np.float32)
        img[:, 30:] = 1.0                                  # white right half
        p = dict(self.p, Specular=0.0, Fresnel=0.0, Glasstint=(1.0, 1.0, 1.0), Dispersion=0.5, Thickness=60.0)
        out = G.glass_shade(img, (25.5, 10.5), np.array([0.25, 0.0]), p)   # offset G = 5 px -> right at 30.5
        self.assertGreater(out[2], out[0])                 # B reaches further into the white than R
        self.assertAlmostEqual(out[0], 0.0)


if __name__ == '__main__':
    unittest.main()
