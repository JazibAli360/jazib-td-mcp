"""Offline tests for W1-E: geometry in the splat scene (docs/builds/px_geo.md). Run:
python3 -I -m unittest discover -s test -p 'test_px_geo.py'

- BL_splat_render with the geo hooks empty compiles to the SAME token stream as before (preprocessed by glslc -E), for
  BL alone, BL + the effectors block, and PX's two adapters on the same text; geo_patch(off) is byte-identical.
- geo adapter compiles (BL alone, with the effectors block, with W1-A's light functions when present, under PX's
  adapter); text patching is order-independent with the effectors block and reversible.
- numpy references: occlusion both ways (cpu_reference_raster base / depth), splat normal, relight; Geo helpers;
  MX environment page / chrome preset; builder text rules.
"""
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
import splat_render_logic as L  # noqa: E402
import effectors_logic as EL  # noqa: E402
import prox_mat_logic as MXL  # noqa: E402


def rd(p):
    with open(p, encoding='ascii') as fh:
        return fh.read()


SPLAT = rd(os.path.join(BUILDERS, 'splat_render.glsl'))
ADAPTER = rd(os.path.join(GLSL, 'splat_geo_adapter.glsl'))

STUB_VERT = """#version 460
#define TD_VERTEX_SHADER 1
struct TDMatrix { mat4 world; mat4 worldCam; mat4 cam; mat4 camInverse; mat4 proj; };
uniform TDMatrix uTDMats[1];
int TDInstanceID() { return gl_InstanceID; }
int TDCameraIndex() { return 0; }
in vec3 P;
vec4 TDPos() { return vec4(P, 1.0); }
float TDSimplexNoise(vec4 v) { return 0.0; }
vec4 TDOutputSwizzle(vec4 c) { return c; }
""" + ''.join('vec4 TDInstanceCustomAttrib%d(int i) { return vec4(float(i)); }\n' % k for k in range(7))
STUB_PIXEL = """#version 460
#define TD_PIXEL_SHADER 1
struct TDMatrix { mat4 world; mat4 worldCam; mat4 cam; mat4 camInverse; mat4 proj; };
uniform TDMatrix uTDMats[1];
int TDCameraIndex() { return 0; }
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""
HOOK_LINES = ('\tSPLAT_HOOK_CLIP(clip, vc, z)\n', '\tSPLAT_HOOK_LIGHT(rgb, p, q, s, idx)\n')


def without_new_hooks(text):
    """The shader as it was before W1-E: the two hook calls and their empty default blocks removed."""
    t = text
    for h in HOOK_LINES:
        assert t.count(h) == 1, h
        t = t.replace(h, '')
    t = re.sub(r'// Geometry-in-the-scene hooks.*?\n(?=#ifdef TD_VERTEX_SHADER)', '', t, flags=re.S)
    return t


def eff_prefix(*defines):
    return EL.consumer_prefix(rd(os.path.join(GLSL, 'px_common.glsl')), rd(os.path.join(GLSL, 'eff_consumer.glsl')),
                              defines)


HAS_GLSLC = shutil.which('glslc') is not None


def _run(args, text, ext):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.' + ext)
        with open(p, 'w') as fh:
            fh.write(text)
        return subprocess.run(['glslc'] + args + [p], capture_output=True, text=True)


def preprocessed_tokens(text, ext):
    r = _run(['-E'], text, ext)
    assert r.returncode == 0, r.stderr[:2000]
    body = '\n'.join(x for x in r.stdout.split('\n') if not x.startswith('#line') and not x.startswith('#extension'))
    return body.split()


@unittest.skipUnless(HAS_GLSLC, 'glslc not installed')
class Identity(unittest.TestCase):
    """Hooks empty = the same code BL / PX compiled before W1-E (token streams after the preprocessor)."""

    def _same(self, pre, what):
        for stub, ext in ((STUB_VERT, 'vert'), (STUB_PIXEL, 'frag')):
            a = preprocessed_tokens(stub + pre(SPLAT), ext)
            b = preprocessed_tokens(stub + pre(without_new_hooks(SPLAT)), ext)
            self.assertEqual(a, b, '%s %s' % (what, ext))

    def test_bl_alone(self):
        self._same(lambda t: t, 'BL')

    def test_bl_spirv_bytes(self):
        for stub, ext in ((STUB_VERT, 'vert'), (STUB_PIXEL, 'frag')):
            outs = []
            for t in (SPLAT, without_new_hooks(SPLAT)):
                with tempfile.TemporaryDirectory() as d:
                    o = os.path.join(d, 'o.spv')
                    p = os.path.join(d, 's.' + ext)
                    with open(p, 'w') as fh:
                        fh.write(stub + t)
                    r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms',
                                        '-fauto-map-locations', '-o', o, p], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, r.stderr[:2000])
                    with open(o, 'rb') as fh:
                        outs.append(fh.read())
            self.assertEqual(outs[0], outs[1], ext)

    def test_bl_with_effectors_block(self):
        self._same(lambda t: EL.with_prefix(t, eff_prefix('PXE_POINTS')), 'BL + effectors')

    def test_px_adapters(self):
        for ad in ('px_splat_adapter.glsl', 'px_glow_adapter.glsl'):
            text = rd(os.path.join(GLSL, ad))
            self._same(lambda t, a=text: a + t, ad)

    def test_patch_off_is_byte_identical(self):
        for t in (SPLAT, EL.with_prefix(SPLAT, eff_prefix('PXE_POINTS'))):
            self.assertEqual(L.geo_patch(t, ADAPTER, False), t)
            self.assertEqual(L.geo_patch(L.geo_patch(t, ADAPTER, True), ADAPTER, False), t)

    def test_hooks_have_empty_defaults_and_no_semicolon(self):
        for h in ('SPLAT_HOOK_CLIP', 'SPLAT_HOOK_LIGHT'):
            self.assertIn('#ifndef %s\n#define %s(' % (h, h), SPLAT)
            self.assertIn('#define %s(' % h, ADAPTER)
        for h in HOOK_LINES:
            self.assertEqual(SPLAT.count(h), 1)                 # called without ';' (empty default = no token)
        for m in re.finditer(r'#define (SPLAT_HOOK_(CLIP|LIGHT))\(.*', ADAPTER):
            self.assertTrue(m.group(0).rstrip().endswith(';'), m.group(0))   # adapter macros end the statement


class Patch(unittest.TestCase):
    def test_marker_matches_effectors(self):
        self.assertEqual(L.EFF_MARK_B, EL.MARK_B)

    def test_order_independent_with_effectors(self):
        pre = eff_prefix('PXE_POINTS')
        a = L.geo_patch(EL.with_prefix(SPLAT, pre), ADAPTER, True)          # effectors first, then geo
        b = EL.with_prefix(L.geo_patch(SPLAT, ADAPTER, True), pre)          # geo first, then effectors re-attach
        self.assertEqual(L.geo_patch(b, ADAPTER, True), a)                  # + geo_sync (build order) = same text
        self.assertEqual(L.geo_strip(b), L.geo_strip(a))
        self.assertLess(a.index(EL.MARK_B), a.index(L.GEO_MARK_A))         # geo block behind the effectors block
        self.assertEqual(L.geo_patch(a, ADAPTER, True), a)                  # idempotent
        self.assertEqual(EL.strip_prefix(L.geo_strip(a)), SPLAT)

    def test_lights_define_only_with_w1a_functions(self):
        on = L.geo_patch(SPLAT, ADAPTER, True)
        self.assertNotIn('#define SGEO_LIGHTS', on)
        fake = '// <<< effectors adapter\nvec3 pxeLights(\nvec3 pxeSplatNormal(\n'
        self.assertIn('#define SGEO_LIGHTS 1', L.geo_patch(fake + SPLAT, ADAPTER, True))

    def test_leading_defines_kept_first(self):
        t = '#define STATE_X 1\n' + SPLAT
        on = L.geo_patch(t, ADAPTER, True)
        self.assertTrue(on.startswith('#define STATE_X 1\n' + L.GEO_MARK_A))
        self.assertEqual(L.geo_patch(on, ADAPTER, False), t)


@unittest.skipUnless(HAS_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, ext, what):
        r = _run(['--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations', '-o', os.devnull], text, ext)
        self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def _both(self, text, what):
        self._ok(STUB_VERT + text, 'vert', what + ' vertex')
        self._ok(STUB_PIXEL + text, 'frag', what + ' pixel')

    def test_bl_with_geo(self):
        self._both(L.geo_patch(SPLAT, ADAPTER, True), 'BL + geo')

    def test_bl_effectors_geo(self):
        t = L.geo_patch(EL.with_prefix(SPLAT, eff_prefix('PXE_POINTS')), ADAPTER, True)
        self._both(t, 'BL + effectors + geo (lights %s)' % L.geo_has_lights(t))

    def test_light_path_compiles(self):
        """The SGEO_LIGHTS branch against W1-A's functions: the real ones when px_common has them, else stubs with
        W1-A's signatures (px_common.glsl lights section)."""
        pre = eff_prefix('PXE_POINTS')
        t = EL.with_prefix(SPLAT, pre)
        if not L.geo_has_lights(t):
            stub = ('vec3 pxeLights(vec3 p, vec3 n, vec3 v, vec4 sel, vec4 ids, vec4 mode) { return n * 0.0 + 1.0; }\n'
                    'vec3 pxeSplatNormal(vec4 q, vec3 scale, vec3 v) { return vec3(0.0, 0.0, 1.0); }\n')
            t = t.replace(EL.MARK_B + '\n', stub + EL.MARK_B + '\n')
        t = L.geo_patch(t, ADAPTER, True)
        self.assertIn('#define SGEO_LIGHTS 1', t)
        self._both(t, 'BL + effectors + geo lights')

    def test_px_adapter_with_geo(self):
        t = rd(os.path.join(GLSL, 'px_splat_adapter.glsl')) + SPLAT
        self._both(L.geo_patch(t, ADAPTER, True), 'PX splat adapter + geo')


def _scene():
    """Two splats on the axis in front of a camera at z = 5 looking down -z: a dense near one (z = 1, alpha 0.98)
    and a far one (z = -1)."""
    P = np.array([[0.0, 0.0, 1.0], [0.0, 0.0, -1.0]])
    S = np.full((2, 3), 0.25)
    Q = np.array([[1.0, 0, 0, 0], [1.0, 0, 0, 0]])
    C = np.array([[1.0, 0.2, 0.1, 0.98], [0.1, 0.3, 1.0, 0.98]])
    prep = {'P': P, 'S': S, 'Q': Q, 'C': C}
    view = np.eye(4)
    view[2, 3] = -5.0                                    # world -> camera (camera at z = 5)
    return prep, view


class Occlusion(unittest.TestCase):
    W = H = 64

    def _ref(self, geo_z, geo_rgb=(0.2, 0.8, 0.3), bias=0.0):
        prep, view = _scene()
        f = L.focal_px(self.H, 45.0)
        base = np.zeros((self.H, self.W, 4))
        base[..., :3], base[..., 3] = geo_rgb, 1.0       # geometry covers the frame (a plane facing the camera)
        depth = np.full((self.H, self.W), float(geo_z))
        return L.cpu_reference_raster(prep, view, f, f, self.W, self.H, base=base, depth=depth, bias=bias), base

    def test_no_geo_is_unchanged(self):
        prep, view = _scene()
        f = L.focal_px(self.H, 45.0)
        a = L.cpu_reference_raster(prep, view, f, f, self.W, self.H)
        b = L.cpu_reference_raster(prep, view, f, f, self.W, self.H, base=np.zeros((self.H, self.W, 4)),
                                   depth=np.full((self.H, self.W), np.inf))
        self.assertTrue(np.array_equal(a, b))

    def test_geometry_in_front_covers_splats(self):
        img, base = self._ref(geo_z=2.0)                  # plane at view depth 2 (world z 3): in front of both
        self.assertLess(np.abs(img - base).max(), 1e-12)

    def test_geometry_between(self):
        img, base = self._ref(geo_z=5.0)                  # plane at world z 0: hides the far splat only
        c = img[self.H // 2, self.W // 2]
        self.assertGreater(c[0], 0.9)                     # near splat (red) over the plane, alpha 0.98
        self.assertLess(abs(c[3] - 1.0), 1e-9)
        self.assertLess(c[2], 0.2)                        # no blue from the far splat

    def test_geometry_behind_dense_splats_hidden(self):
        prep, view = _scene()
        img, base = self._ref(geo_z=50.0)
        c = img[self.H // 2, self.W // 2]
        f = L.focal_px(self.H, 45.0)
        sp = L.cpu_reference_raster(prep, view, f, f, self.W, self.H)[self.H // 2, self.W // 2]
        self.assertGreater(sp[3], 0.95)                   # splat coverage at the centre
        np.testing.assert_allclose(c[:3], sp[:3] + np.array([0.2, 0.8, 0.3]) * (1 - sp[3]), atol=1e-9)

    def test_depth_bias_lets_coincident_splat_win(self):
        img0, base = self._ref(geo_z=3.98)                # plane 0.02 in front of the near splat's centre (depth 4)
        img1, _ = self._ref(geo_z=3.98, bias=0.05)
        self.assertLess(np.abs(img0 - base).max(), 1e-12)  # hidden without bias
        self.assertGreater(img1[self.H // 2, self.W // 2, 0], 0.9)   # bias 0.05 pulls it in front
        img2, _ = self._ref(geo_z=4.0)                    # equal depth passes (TD depth func less-or-equal: LIVE G2)
        self.assertGreater(img2[self.H // 2, self.W // 2, 0], 0.9)


class Lights(unittest.TestCase):
    def test_splat_normal_smallest_axis(self):
        np.testing.assert_allclose(L.splat_normal([1, 0, 0, 0], [0.3, 0.2, 0.01]), [0, 0, 1], atol=1e-12)
        q = [np.cos(np.pi / 4), np.sin(np.pi / 4), 0, 0]  # 90 deg about x: local z -> world -y
        np.testing.assert_allclose(L.splat_normal(q, [0.3, 0.2, 0.01]), [0, -1, 0], atol=1e-12)
        n = L.splat_normal(np.array([[1, 0, 0, 0], q]), np.array([[0.01, 1, 1], [1, 1, 0.01]]))
        np.testing.assert_allclose(n, [[1, 0, 0], [0, -1, 0]], atol=1e-12)

    def test_w1a_normal_twin_agrees(self):
        f = getattr(EL, 'splat_normal', None)
        if f is None:
            self.skipTest('effectors_logic.splat_normal not landed (W1-A)')
        rng = np.random.default_rng(3)
        for _ in range(20):
            q = rng.normal(size=4)
            s = rng.uniform(0.01, 1, 3)
            v = rng.normal(size=3)
            try:
                a = np.asarray(f(q, s, v), float)
            except TypeError:
                a = np.asarray(f(q, s), float)
            b = L.splat_normal(q, s)
            self.assertAlmostEqual(abs(float(np.dot(a, b))), 1.0, places=9)

    def test_relight(self):
        rgb, p = [0.5, 0.4, 0.2], [0.0, 0.0, 0.0]
        q, s = [1, 0, 0, 0], [0.3, 0.3, 0.01]             # normal +-z
        cam = [0.0, 0.0, 3.0]
        self.assertEqual(list(L.geo_relight_ref(rgb, p, q, s, cam, [], 0.0, 0.25)), rgb)
        seen = []
        lit = L.geo_relight_ref(rgb, p, q, s, cam, [lambda p_, n, v: seen.append(n) or np.array([1.0, 0.5, 0.0])],
                                1.0, 0.25)
        np.testing.assert_allclose(seen[0], [0, 0, 1])    # faces the camera
        np.testing.assert_allclose(lit, np.array(rgb) * np.array([1.25, 0.75, 0.25]))
        half = L.geo_relight_ref(rgb, p, q, s, cam, [], 0.5, 0.0)
        np.testing.assert_allclose(half, np.array(rgb) * 0.5)


class Helpers(unittest.TestCase):
    def test_resolve_lights(self):
        cands = [('/project1/effectors/key', ['light', 'warm']), ('/project1/effectors/rim', ['light', 'cool'])]
        self.assertEqual(L.resolve_lights('#light', cands), '/project1/effectors/key /project1/effectors/rim')
        self.assertEqual(L.resolve_lights('#cool /x/l1, #cool', cands), '/project1/effectors/rim /x/l1')
        self.assertEqual(L.resolve_lights('', cands), '')

    def test_geometry_excludes_splats(self):
        self.assertEqual(L.geo_geometry('/a/box, draw /b/text'), '/a/box /b/text')
        self.assertEqual(L.geo_geometry(''), '')

    def test_uniform_and_menu(self):
        self.assertEqual(L.geo_uniform(1, 0.25, 'wrap', 0.01), (1.0, 0.25, 2.0, 0.01))
        self.assertEqual([m[0] for m in L.LIGHTMODES], ['halflambert', 'lambert', 'wrap', 'glow'])

    def test_warning_and_env_gate(self):
        self.assertTrue(L.geo_warning(True, 'sortfree'))
        self.assertEqual(L.geo_warning(True, 'sortpop'), '')
        self.assertEqual(L.geo_warning(False, 'sortfree'), '')
        self.assertEqual([L.env_render_now(f, 4) for f in range(6)], [True, False, False, False, True, False])
        self.assertTrue(all(L.env_render_now(f, 1) for f in range(5)))


class Mx(unittest.TestCase):
    def test_environment_page_demo_only(self):
        specs = MXL.par_specs()
        for n in ('Envmode', 'Envtop', 'Envgeo', 'Envcentre', 'Envres', 'Enveveryn', 'Envdimmer'):
            self.assertIn(n, specs)
            self.assertIn(n, MXL.DEMO_ONLY)                    # material units never get them
        self.assertEqual(specs['Envmode'][1], 'gradient')      # default = the v1 env_map
        self.assertIn('Environment', MXL.PANEL_PAGES)

    def test_chrome_preset(self):
        v = MXL.PRESETS['chrome_mirror']
        self.assertEqual((v['Metalnear'], v['Metalfar']), (1.0, 1.0))
        self.assertIn('chrome_mirror', MXL.PRESET_NAMES)
        self.assertEqual(len(MXL.PRESET_NAMES), len(MXL.PRESET_LABELS))


class Builder(unittest.TestCase):
    def setUp(self):
        self.bl = rd(os.path.join(BUILDERS, 'splat_render.py'))
        self.rt = rd(os.path.join(BUILDERS, 'splat_render_rt.py'))
        self.mx = rd(os.path.join(BUILDERS, 'prox_mat.py'))

    def test_api(self):
        fns = set(n.name for n in ast.parse(self.bl).body if isinstance(n, ast.FunctionDef))
        self.assertTrue({'geo_pars', 'geo_stage', 'geo_env', 'geo_sync', 'geo_upgrade', 'geo_panel',
                         'splat_text_refresh'} <= fns)
        rfns = set(n.name for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef))
        self.assertTrue({'geo_sync', 'geo_lights', '_geo_uniform'} <= rfns)
        mfns = set(n.name for n in ast.parse(self.mx).body if isinstance(n, ast.FunctionDef))
        self.assertTrue({'env_capture', 'env_upgrade', 'panel_only'} <= mfns)

    def test_env_capture_holds_without_pulling(self):
        """Live b3 (27 Oct): Render TOP `render` off gives black (no hold) and a Cache TOP alone pulls its input every
        frame, so env_capture = cube -> equirect -> Switch (1 px idle on other frames) -> Cache (active on capture
        frames); the cube render gets lights (MX meshes render black into it without them)."""
        tree = ast.parse(self.mx)
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'env_capture')
        seg = ast.get_source_segment(self.mx, fn)
        for s in ('projectionTOP', 'switchTOP', 'cacheTOP', "'cachesize', 1", 'r.par.lights = lights'):
            self.assertIn(s, seg)
        self.assertNotIn("_try(r, 'render', expr", seg)
        self.assertEqual(self.mx.count("lights='light1',"), 2)      # demo build + env_upgrade
        self.assertIn('ENV_PULL % (prefix, use_cond, prefix)', seg)   # the env light never pulls its map (main)

    def test_off_path_keeps_bl(self):
        self.assertIn("m.par.depthtest.expr = 'bool(%sGeoon.eval())' % P", self.bl)
        self.assertIn("m.par.depthwriting = False", self.bl)
        self.assertIn("sw.par.index.expr = '1 if %sGeoon.eval() else 0' % P", self.bl)
        self.assertIn("_par(c, GE, 'Toggle', 'Geoon', 'Geometry in the scene', False)", self.bl)
        self.assertIn('geo_sync(c)', self.bl)
        self.assertIn("'Geo'], d=56", self.bl)

    def test_crash_rules(self):
        """The W1-E functions: no pixel readback (T-74), no direct destroy (T-70), ASCII."""
        for src, names in ((self.bl, ('geo_pars', 'geo_stage', 'geo_env', 'geo_sync', '_try', 'geo_upgrade', 'geo_panel',
                                      'splat_text_refresh')),
                           (self.rt, ('geo_sync', 'geo_lights', '_geo_uniform', '_slot')),
                           (self.mx, ('env_capture', 'env_upgrade', 'panel_only'))):
            tree = ast.parse(src)
            for n in tree.body:
                if isinstance(n, ast.FunctionDef) and n.name in names:
                    seg = ast.get_source_segment(src, n)
                    self.assertNotIn('numpyArray', seg, n.name)
                    self.assertNotIn('.destroy(', seg, n.name)
            src.encode('ascii')
        ADAPTER.encode('ascii')


if __name__ == '__main__':
    unittest.main()
