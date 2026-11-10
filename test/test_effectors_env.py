"""Offline tests for effector kind `env` (SA6 screen-as-light, lane E): packed v3 layout (env region after the lights,
v2 readers unchanged), SH9 projection + irradiance (effectors_logic.env_coeffs / ref_env / ref_envs) against closed
forms and the brute-force integral, maps screen / equirect / ambient, selection, the runtime text and glslc compiles
of the GLSL accessors (px_common packed section). No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_effectors_env.py'
glslc = a syntax / type check against TD stubs, NOT a TD compile (LIVE CHECKS EV1-EV6 in docs/builds/effectors.md)."""
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
import numpy as np  # noqa: E402
import effectors_logic as L  # noqa: E402


def rd(path):
    with open(path) as fh:
        return fh.read()


def world(t=(0.0, 0.0, 0.0), ry=0.0, s=1.0):
    c, n = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    return [[c * s, 0.0, n * s, t[0]], [0.0, s, 0.0, t[1]], [-n * s, 0.0, c * s, t[2]]]


def rows_of(*specs):
    rs = []
    for kind, name, kw in specs:
        rs, _ = L.add_row(rs, kind, name, **kw)
    return rs


def equirect(fn, w=64, h=32):
    """Pixels (h, w, 3) of radiance fn(direction (n, 3)) -> (n, 3) on the env_samples equirect convention."""
    D, _ = L.env_samples({'map': 'equirect'}, None, w, h)
    return fn(D).reshape(h, w, 3)


def fib_normals(n=200):
    k = np.arange(n) + 0.5
    phi = np.arccos(1.0 - 2.0 * k / n)
    th = math.pi * (1.0 + 5 ** 0.5) * k
    return np.stack([np.cos(th) * np.sin(phi), np.cos(phi), np.sin(th) * np.sin(phi)], axis=1)


UP = np.array([0.0, 1.0, 0.0])


class Layout(unittest.TestCase):
    def test_kind_and_version(self):
        ns = L.names(L.KINDS)
        self.assertEqual(ns.index('light'), 10)
        self.assertEqual(ns.index('env'), 11)
        self.assertEqual(L.VERSION, 3)
        self.assertIn('env', L.NON_PROX)

    def test_region_after_lights_points_after(self):
        rs = rows_of(('sphere', 's', {}), ('env', 'e', {'tags': 'wall'}), ('light', 'l', {}),
                     ('pts', 'p', {}), ('env', 'off', {'enabled': 0}))
        px = np.ones((4, 8, 3))
        effs = [L.effector(rs[0]), L.effector(rs[1], world((0, 1, -3)), env={'map': 'ambient', 'pixels': px}),
                L.effector(rs[2], world((0, 2, 0)), light={}),
                L.effector(rs[3], points=[(0, 0, 0), (1, 0, 0)]),
                L.effector(rs[4], env={'map': 'ambient', 'pixels': px})]
        tex = L.pack_buffer(effs)
        n = 5
        l0 = 1 + n * L.W
        e0 = l0 + 1 + L.LW
        self.assertEqual(tex[0][3], 3.0)
        self.assertEqual(tex[l0], [1.0, float(L.LW), float(e0), 0.0])           # z = env base, w = grid (none)
        self.assertEqual(L.env_start(tex), e0)
        self.assertEqual(tex[e0][:2], [1.0, float(L.EW)])                       # one enabled env
        self.assertEqual(L.env_count(tex), 1)
        pstart = e0 + 1 + L.EW
        self.assertEqual(tex[0][2], float(pstart))
        self.assertEqual(L.read_row(tex, 3)[8][2], float(pstart))
        self.assertEqual(tex[pstart], [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(len(tex), pstart + 4)
        blk = L.read_env(tex, 0)
        self.assertEqual(blk[0], [1.0, 1.0, 2.0, 0.0])                          # gain, row 1, map ambient
        self.assertEqual(L.read_light(tex, 0)[2][3], 2.0)                       # lights unchanged
        self.assertEqual(L.read_row(tex, 1)[6][3], 0.0)                         # env row: not proximity
        self.assertEqual(L.read_row(tex, 1)[8][1], 11.0)

    def test_no_env_is_v2_layout(self):
        """Without envs / grid the buffer is the v2 one apart from the version number: a v2 reader sees no change."""
        rs = rows_of(('sphere', 's', {}), ('light', 'l', {}), ('pts', 'p', {}))
        effs = [L.effector(rs[0]), L.effector(rs[1], world((0, 1, 0)), light={}),
                L.effector(rs[2], points=[(0, 0, 0)])]
        tex = L.pack_buffer(effs)
        self.assertEqual(tex[1 + 3 * L.W], [1.0, float(L.LW), 0.0, 0.0])
        self.assertEqual(L.env_start(tex), -1)
        self.assertEqual(L.grid_start(tex), -1)
        self.assertEqual(tex[0][2], float(1 + 3 * L.W + 1 + L.LW))

    def test_v2_reader_unchanged(self):
        """A v2 consumer (W = 10 rows, light header x / y, point sets by absolute texel) reads a v3 buffer with envs
        exactly as before: weights, colliders, lights."""
        rs = rows_of(('sphere', 's', {'radius': 1.0}), ('env', 'e', {}), ('pts', 'p', {'radius': 1.0}),
                     ('light', 'l', {}))
        lv = {'intensity': 2.0, 'att_on': False}
        effs = [L.effector(rs[0]), L.effector(rs[1], env={'map': 'ambient', 'pixels': np.ones((2, 2, 3))}),
                L.effector(rs[2], points=[(2.0, 0.0, 0.0)]), L.effector(rs[3], world((0, 1, 0)), light=lv)]
        tex = L.pack_buffer(effs)
        rs0 = [rs[0], rs[2], rs[3]]
        tex0 = L.pack_buffer([effs[0], effs[2], effs[3]])
        for p in ((0.75, 0.0, 0.0), (2.2, 0.0, 0.0), (5.0, 0.0, 0.0)):
            self.assertAlmostEqual(L.ref_weight(tex, p, L.sel_vec('all', rs)[0])[0],
                                   L.ref_weight(tex0, p, L.sel_vec('all', rs0)[0])[0])
        self.assertEqual(L.colliders(tex, L.sel_vec('all', rs)[0]), L.colliders(tex0, L.sel_vec('all', rs0)[0]))
        P = [(0.0, 0.0, 0.0)]
        np.testing.assert_allclose(L.ref_lights(tex, P, [UP], [UP], L.sel_vec('all', rs)[0]),
                                   L.ref_lights(tex0, P, [UP], [UP], L.sel_vec('all', rs0)[0]))

    def test_cache_same_output(self):
        rs = rows_of(('env', 'e', {}), ('box', 'b', {}))
        cache, ec = {}, {}
        for gain in (1.0, 2.0):
            px = np.random.default_rng(1).uniform(0, 1, (9, 16, 3))
            effs = [L.effector(rs[0], world((0, 1, -3)), env={'map': 'screen', 'gain': gain, 'pixels': px}),
                    L.effector(rs[1])]
            a = L.pack_buffer(effs, cache=cache, list_key=(0, 2), as_array=True, env_cache=ec).tolist()
            self.assertEqual(a, L.pack_buffer(effs))
        self.assertEqual(len(ec), 1)                                            # one sample basis kept


class SH(unittest.TestCase):
    def test_uniform_white_sky_is_one(self):
        ev = {'map': 'equirect', 'pixels': np.ones((16, 32, 3))}
        c = L.env_coeffs(ev)
        np.testing.assert_allclose(c[0], [4.0 * math.pi * L.SH_K[0]] * 3, rtol=1e-12)
        np.testing.assert_allclose(c[1:], 0.0, atol=3e-3)              # midpoint quadrature of l = 2 at 32 x 16
        rs = rows_of(('env', 'e', {}))
        tex = L.pack_buffer([L.effector(rs[0], env=ev)])
        np.testing.assert_allclose(L.ref_env(tex, 0, fib_normals()), 1.0, atol=5e-3)    # 32 x 16: <= 0.5 %
        np.testing.assert_allclose(L.env_irradiance_brute(L.effector(rs[0], env=ev)['env'], None, fib_normals()),
                                   1.0, atol=1e-2)                              # the integral itself (quadrature)

    def test_basis_orthonormal(self):
        D, w = L.env_samples({'map': 'equirect'}, None, 512, 256)
        B = L.sh_basis(D)
        G = (B * w[:, None]).T @ B
        np.testing.assert_allclose(G, np.eye(9), atol=2e-4)

    def test_linear_sky_exact(self):
        """L(w) = a + b (d . w) is l <= 1: SH9 irradiance = a + (2/3) b (d . n) exactly (up to quadrature)."""
        d = np.array([0.3, 0.8, -0.52])
        d /= np.linalg.norm(d)
        a, b = np.array([0.5, 0.2, 0.1]), np.array([0.4, 0.1, 0.05])
        px = equirect(lambda D: a[None, :] + (D @ d)[:, None] * b[None, :], 256, 128)
        rs = rows_of(('env', 'e', {}))
        tex = L.pack_buffer([L.effector(rs[0], env={'map': 'equirect', 'pixels': px})])
        N = fib_normals()
        want = a[None, :] + (2.0 / 3.0) * (N @ d)[:, None] * b[None, :]
        np.testing.assert_allclose(L.ref_env(tex, 0, N), np.maximum(want, 0.0), atol=1e-4)

    def test_quadratic_sky_vs_brute(self):
        """l = 2 content: SH9 = the brute-force clamped-cosine integral within 1e-3 (both at 256 x 128)."""
        f = lambda D: np.stack([0.6 + 0.3 * D[:, 0] * D[:, 2], 0.4 + 0.2 * (3 * D[:, 1] ** 2 - 1),
                                0.5 + 0.25 * (D[:, 0] ** 2 - D[:, 2] ** 2)], axis=1)
        px = equirect(f, 256, 128)
        ev = {'map': 'equirect', 'pixels': px}
        rs = rows_of(('env', 'e', {}))
        e = L.effector(rs[0], env=ev)
        tex = L.pack_buffer([e])
        N = fib_normals()
        np.testing.assert_allclose(L.ref_env(tex, 0, N), L.env_irradiance_brute(e['env'], None, N), atol=1e-3)

    def test_delta_light_constants(self):
        """A single bright pixel (power Phi along w0): SH9 irradiance at n = w0 is Phi x 4.25 / (4 pi) (sum over l of
        A^_l (2l + 1) / 4pi), 6.25 % over the exact Phi / pi; the basis constants and A^_l are checked by this."""
        w, h = 64, 32
        px = np.zeros((h, w, 3))
        px[20, 40] = 1.0
        D, wgt = L.env_samples({'map': 'equirect'}, None, w, h)
        k = 20 * w + 40
        phi = wgt[k]
        rs = rows_of(('env', 'e', {}))
        tex = L.pack_buffer([L.effector(rs[0], env={'map': 'equirect', 'pixels': px})])
        got = L.ref_env(tex, 0, D[k:k + 1])[0, 0]
        self.assertAlmostEqual(got, phi * 4.25 / (4.0 * math.pi), places=12)
        e = L.effector(rs[0], env={'map': 'equirect', 'pixels': px})
        self.assertAlmostEqual(L.env_irradiance_brute(e['env'], None, D[k:k + 1])[0, 0], phi / math.pi, places=12)

    def test_equirect_convention_and_rotation(self):
        """TD Projection TOP equirect (live b2 31550, cube -> equirect of red -Z / green +X / blue +Y spheres): u 0 =
        +X, 0.25 = +Z, 0.5 = -X, 0.75 = -Z, v top = +Y; the env object's rotation turns the map (ry 90: -Z -> -X)."""
        Dc, _ = L.env_samples({'map': 'equirect'}, None, 2, 1)                  # u 0.25, 0.75 at el 0
        np.testing.assert_allclose(Dc, [[0.0, 0.0, 1.0], [0.0, 0.0, -1.0]], atol=1e-12)
        Dv, _ = L.env_samples({'map': 'equirect'}, None, 1, 3)                  # u 0.5; v rows: bottom, middle, top
        np.testing.assert_allclose(Dv[1], [-1.0, 0.0, 0.0], atol=1e-12)
        self.assertLess(Dv[0][1], -0.8)
        self.assertGreater(Dv[2][1], 0.8)
        sky = lambda Dd: np.maximum(-Dd[:, 2:3], 0.0) * np.ones((1, 3))         # light from -Z only
        px = equirect(sky, 128, 64)
        rs = rows_of(('env', 'e', {}))
        t0 = L.pack_buffer([L.effector(rs[0], env={'map': 'equirect', 'pixels': px})])
        t1 = L.pack_buffer([L.effector(rs[0], world(ry=90.0), env={'map': 'equirect', 'pixels': px})])
        nz, nx = np.array([[0.0, 0.0, -1.0]]), np.array([[-1.0, 0.0, 0.0]])
        self.assertAlmostEqual(L.ref_env(t0, 0, nz)[0, 0], L.ref_env(t1, 0, nx)[0, 0], places=9)
        self.assertGreater(L.ref_env(t0, 0, nz)[0, 0], 5.0 * L.ref_env(t0, 0, -nz)[0, 0] + 1e-6)

    def test_screen_small_far_is_directional(self):
        """A small panel (0.2 x 0.2) 10 units away along -Z, facing the probe: brute = c Omega cos / pi (Omega = A /
        r^2); behind the panel (front only) = 0; twosided lights the back too."""
        c = np.array([1.0, 0.5, 0.25])
        px = np.ones((8, 8, 3)) * c
        ev = {'map': 'screen', 'w': 0.2, 'h': 0.2, 'probe': (0.0, 0.0, 0.0), 'pixels': px}
        wm = world((0.0, 0.0, -10.0))
        e = L.effector(rows_of(('env', 'e', {}))[0], wm, env=ev)
        om = 0.04 / 100.0
        n = np.array([[0.0, 0.0, -1.0], [math.sin(0.5), 0.0, -math.cos(0.5)], [0.0, 0.0, 1.0]])
        got = L.env_irradiance_brute(e['env'], wm, n)
        want = np.outer(np.maximum(-n[:, 2], 0.0), c) * om / math.pi
        np.testing.assert_allclose(got, want, rtol=2e-3, atol=1e-12)
        back = dict(ev, probe=(0.0, 0.0, -20.0))
        self.assertTrue(np.all(L.env_coeffs(back, wm) == 0.0))
        self.assertGreater(np.abs(L.env_coeffs(dict(back, twosided=True), wm)).sum(), 0.0)

    def test_screen_vs_brute_large_wall(self):
        """A big LED wall close to the probe (smooth over the hemisphere): SH9 within 5 % of the panel's peak
        brute-force irradiance (SH9's known ringing for one-sided lights) and > 0 everywhere it is lit."""
        rng = np.random.default_rng(5)
        px = 0.5 + 0.5 * rng.uniform(0, 1, (18, 32, 3))
        ev = {'map': 'screen', 'w': 8.0, 'h': 4.5, 'probe': (0.0, 1.0, 0.0), 'pixels': px}
        wm = world((0.0, 2.0, -3.0))
        e = L.effector(rows_of(('env', 'e', {}))[0], wm, env=ev)
        tex = L.pack_buffer([e])
        N = fib_normals(300)
        sh, br = L.ref_env(tex, 0, N), L.env_irradiance_brute(e['env'], wm, N)
        self.assertLess(np.abs(sh - br).max(), 0.05 * br.max())
        lit = br[:, 0] > 0.2 * br.max()
        self.assertTrue(np.all(sh[lit] > 0.0))

    def test_ambient_and_gain(self):
        px = np.zeros((4, 4, 3))
        px[..., 0] = 1.0
        px[0, 0] = [0.0, 0.0, 16.0]
        rs = rows_of(('env', 'e', {}))
        tex = L.pack_buffer([L.effector(rs[0], env={'map': 'ambient', 'gain': 2.0, 'pixels': px})])
        np.testing.assert_allclose(L.ref_env(tex, 0, fib_normals(20)), [[2.0 * 15 / 16, 0.0, 2.0]] * 20, atol=1e-12)

    def test_selection_and_disabled(self):
        rs = rows_of(('env', 'a', {'tags': 'wall'}), ('env', 'b', {'tags': 'floor'}), ('env', 'c', {'enabled': 0}))
        one = np.ones((2, 2, 3))
        effs = [L.effector(rs[0], env={'map': 'ambient', 'gain': 1.0, 'pixels': one}),
                L.effector(rs[1], env={'map': 'ambient', 'gain': 10.0, 'pixels': one}),
                L.effector(rs[2], env={'map': 'ambient', 'gain': 100.0, 'pixels': one})]
        tex = L.pack_buffer(effs)
        v = lambda s: float(L.ref_envs(tex, [UP], L.sel_vec(s, rs)[0])[0, 0])
        self.assertAlmostEqual(v('all'), 11.0)
        self.assertAlmostEqual(v('#wall'), 1.0)
        self.assertAlmostEqual(v('b'), 10.0)
        self.assertAlmostEqual(v('c'), 0.0)
        self.assertEqual(L.env_count(tex), 2)

    def test_no_pixels_is_dark(self):
        rs = rows_of(('env', 'e', {}))
        tex = L.pack_buffer([L.effector(rs[0], env={'map': 'screen', 'pixels': None})])
        np.testing.assert_allclose(L.ref_env(tex, 0, [UP]), 0.0)
        self.assertEqual(L.env_count(L.pack_buffer([L.effector(rs[0])])), 0)    # no env values: not packed

    def test_values_fit_and_chop(self):
        v = L.env_values({'map': 'nope', 'twosided': '1', 'samples': '1000', 'probe': (1, 2, 3, 4)})
        self.assertEqual((v['map'], v['twosided'], v['samples'], v['probe']), ('screen', True, 256, (1.0, 2.0, 3.0)))
        self.assertEqual(L.env_fit_size({'map': 'equirect', 'samples': 32}), (32, 16))
        self.assertEqual(L.env_fit_size({'map': 'screen', 'samples': 32, 'w': 16, 'h': 9}), (32, 18))
        names = ['r0', 'g0', 'b0', 'a0', 'r1', 'g1', 'b1', 'a1']
        arr = np.arange(8 * 3, dtype=float).reshape(8, 3)
        px = L.env_pixels_from_chop(names, arr)
        self.assertEqual(px.shape, (2, 3, 4))
        np.testing.assert_allclose(px[1, :, 0], arr[4])
        np.testing.assert_allclose(px[0, :, 2], arr[2])
        px1 = L.env_pixels_from_chop(['r', 'g', 'b', 'a'], np.ones((4, 5)))
        self.assertEqual(px1.shape, (1, 5, 4))


class TDText(unittest.TestCase):
    def setUp(self):
        self.rt = rd(os.path.join(BUILDERS, 'effectors_rt.py'))

    def _ns(self):
        ns = {'boxSOP': 0, 'sphereSOP': 0, 'gridSOP': 0, 'tubeSOP': 0, 'torusSOP': 0}
        exec(compile(self.rt, 'effectors_rt.py', 'exec'), ns)
        ns['L'] = lambda: L
        return ns

    def test_env_of_and_set_env(self):
        ns = self._ns()

        class P:
            def __init__(self, v):
                self.val = v

            def eval(self):
                return self.val
        pars = types.SimpleNamespace(**dict((n, P(0.0)) for n in (
            'Envmap', 'Envgain', 'Envw', 'Envh', 'Envtwosided', 'Envsamples', 'Envprobex', 'Envprobey',
            'Envprobez')))
        names = ['r0', 'g0', 'b0', 'a0']
        chop = types.SimpleNamespace(family='CHOP', numChans=4, chans=lambda: [types.SimpleNamespace(name=n)
                                                                                for n in names],
                                     numpyArray=lambda: np.ones((4, 6)))
        o = types.SimpleNamespace(par=pars, valid=True, op=lambda n: chop if n == 'env_px' else None)
        want = {'map': 'equirect', 'gain': 2.0, 'w': 3.0, 'h': 1.0, 'probe': (1.0, 2.0, 3.0), 'twosided': True,
                'samples': 16}
        self.assertEqual(ns['set_env'](o, **want), [])
        ev = ns['env_of'](o)
        self.assertEqual(dict((k, ev[k]) for k in want), L.env_values(want))
        self.assertEqual(ev['pixels'].shape, (1, 6, 4))
        self.assertEqual(ns['set_env'](o, nope=1), ['nope'])
        self.assertEqual(ns['env_fit'](o, 0), 16)

    def test_runtime_wiring(self):
        for s in ("ev = env_of(o) if r['kind'] == Lg.ENV_KIND else None",
                  "effs.append(Lg.effector(r, w, vel, pts, ppv, lv, ev))", "grid=grid_texels(), env_cache=st['envc']",
                  "if not Lg._on(r['enabled']) or (not full and Lg.is_pub(r)):",
                  "tr(px, 'downloadtype', 'nextframe')", "_env_ops(o, r)",
                  "Lg.OBJECT_KINDS + Lg.POINT_KINDS + Lg.NON_PROX"):
            self.assertIn(s, self.rt)
        self.rt.encode('ascii')
        self.assertNotIn('.destroy()', self.rt.replace('nomcp.destroy()', ''))   # T-70 exception: no MCP here


STUB_COMPUTE = """#version 460
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
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

    def test_env_api_compute(self):
        pre = L.consumer_prefix(rd(os.path.join(GLSL, 'px_common.glsl')), rd(os.path.join(GLSL, 'eff_consumer.glsl')))
        body = """
layout(local_size_x = 8, local_size_y = 8) in;
void main()
{
	vec3 n = normalize(vec3(gl_GlobalInvocationID.xy, 1.0));
	vec3 c = pxeEnvs(n, uEffSel, uEffIds);
	if (pxeEnvCount() > 0) c += pxeEnvIrr(0, n) * float(pxeEnvRow(0));
	imageStore(mTDComputeOutputs[0], ivec3(gl_GlobalInvocationID.xy, 0), vec4(c, 1.0));
}
"""
        self._ok(STUB_COMPUTE + pre + body, 'comp', 'env API in a consumer compute')

    def test_glsl_matches_reference(self):
        """The GLSL SH9 sum pairs each block texel with ref's basis term (sh_basis order) and constant."""
        g = rd(os.path.join(GLSL, 'px_common.glsl'))
        body = g[g.index('vec3 pxeEnvIrrB('):g.index('vec3 pxeEnvIrr(int m')]
        for t, term in ((2, 'y'), (3, 'z'), (4, 'x'), (5, '(x * y)'), (6, '(y * z)'), (8, '(x * z)'),
                        (7, '((3.0 * z * z - 1.0)'), (9, '((x * x - y * y)')):
            self.assertIn('pxeETb(e, m, %d).rgb * %s' % (t, term), body)
        consts = [float(x) for x in re.findall(r'\d\.\d{10,}', body)]
        for k in L.SH_K:
            self.assertTrue(any(abs(k - c) < 1e-15 for c in consts), k)
        self.assertIn('const int PXE_EW = %d;' % L.EW, g)
        self.assertIn('const int PXE_ENV_MAX = %d;' % L.ENV_MAX, g)
        g.encode('ascii')
        # a numpy transcription of the GLSL lines equals ref_env
        rs = rows_of(('env', 'e', {}))
        px = np.random.default_rng(2).uniform(0, 1, (16, 32, 3))
        tex = L.pack_buffer([L.effector(rs[0], env={'map': 'equirect', 'gain': 1.5, 'pixels': px})])
        T = lambda t: np.array(L.read_env(tex, 0)[t][:3])
        for n in fib_normals(30):
            x, y, z = n
            s = (T(1) * L.SH_K[0] + (T(2) * y + T(3) * z + T(4) * x) * L.SH_K[1] +
                 (T(5) * (x * y) + T(6) * (y * z) + T(8) * (x * z)) * L.SH_K[2] +
                 T(7) * ((3 * z * z - 1) * L.SH_K[3]) + T(9) * ((x * x - y * y) * L.SH_K[4]))
            np.testing.assert_allclose(np.maximum(s, 0.0) * 1.5, L.ref_env(tex, 0, [n])[0], atol=1e-12)


if __name__ == '__main__':
    unittest.main()
