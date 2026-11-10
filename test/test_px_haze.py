"""Offline tests for the W1-D haze + bloom passes (builders/px_haze_logic.py, px_haze.py, glsl/px_haze*.glsl,
glsl/px_bloom.glsl). No TD needed. Run: python3 -I -m unittest discover -s test -p 'test_px_haze.py'
GLSL: glslc (OpenGL target) against stubs of TD's compute declarations = a syntax/type check, NOT a TD compile (LIVE
CHECK in docs/builds/px_haze.md). Numbers vs references: numpy mirrors of the shaders (float64)."""
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
import px_haze_logic as H  # noqa: E402
import palette_map_logic as P  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None

STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[2];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
"""


def cam0():
    return H.camera_lookat((0.0, 1.0, 8.0), (0.0, 1.0, 0.0), 50.0, 9.0 / 16.0)


def one_ray(dv=(0.05, 0.02, -1.0)):
    d = np.array([dv], float)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def brute(o, d, te, P_, I, D, y0, Hf, g, ext, r0, cone=None, rng=0.0, n=400001):
    """Dense trapezoid integral of the single-scattering integrand (independent of the equiangular code)."""
    t = np.linspace(0.0, te, n)
    pts = o + d * t[:, None]
    sg = H.sigma(pts[:, 1], D, y0, Hf)
    T = np.exp(-ext * H.opt_depth(o[1], d[1], t, D, y0, Hf))
    lv = pts - np.asarray(P_, float)
    dist = np.sqrt((lv ** 2).sum(1))
    d2 = dist ** 2 + r0 ** 2
    wi = lv / dist[:, None]
    f = sg * T * H.hg(-(wi @ d), g) * I / d2
    if cone is not None:
        ax, c0, c1 = cone
        x = np.clip((wi @ np.asarray(ax, float) - c0) / (c1 - c0), 0, 1)
        f = f * x * x * (3 - 2 * x)
    if rng > 0:
        f = f * np.clip(1 - (dist / rng) ** 4, 0, 1) ** 2
    return np.trapezoid(f, t) if hasattr(np, 'trapezoid') else np.trapz(f, t)


@unittest.skipIf(np is None, 'numpy missing')
class InScatter(unittest.TestCase):
    def setUp(self):
        self.cam = cam0()
        self.o = np.array(self.cam['pos'])
        self.L, self.n = H.light_rows([{'type': 'point', 'pos': (0.5, 1.5, 0.0), 'intensity': 2.0}])

    def _ins(self, p, d, te=20.0, L=None, n=None):
        U = H.haze_rows(p, self.cam, n if n is not None else self.n)
        return H.inscatter(self.o, d, np.array([te]), U, L or self.L, n if n is not None else self.n)[0][0, 0]

    def test_closed_form_airlight(self):
        # homogeneous, no extinction, isotropic: equiangular + normalised smoothstep weights = exact for any N
        d = one_ray()
        cf = H.airlight_point(list(self.o), list(d[0]), 20.0, (0.5, 1.5, 0.0), 2.0, 0.1, 0.05)
        for st in (1, 4, 8, 16, 32):
            p = {'density': 0.1, 'falloff': 0, 'noise': 0, 'extinction': 0, 'g': 0, 'steps': st,
                 'softradius': 0.05}
            self.assertLess(abs(self._ins(p, d) / cf - 1), 1e-9, st)

    def test_closed_form_vs_brute(self):
        d = one_ray()
        cf = H.airlight_point(list(self.o), list(d[0]), 20.0, (0.5, 1.5, 0.0), 2.0, 0.1, 0.05)
        b = brute(self.o, d[0], 20.0, (0.5, 1.5, 0), 2.0, 0.1, 0, 0, 0, 0, 0.05)
        self.assertLess(abs(cf / b - 1), 1e-4)

    def test_extinction_height_phase_vs_brute(self):
        # dense fog (tau ~ 2.4 to the light), height falloff, forward scatter: the hard case for 16 samples
        errs = {}
        for dv in ((0.05, 0.02, -1.0), (0.3, 0.1, -1.0), (0.06, 0.06, -1.0)):
            d = one_ray(dv)
            b = brute(self.o, d[0], 20.0, (0.5, 1.5, 0), 2.0, 0.3, 0.0, 0.3, 0.4, 1.0, 0.05)
            for st in (16, 32):
                p = {'density': 0.3, 'falloff': 0.3, 'noise': 0, 'extinction': 1, 'g': 0.4, 'steps': st,
                     'softradius': 0.05}
                errs.setdefault(st, []).append(abs(self._ins(p, d) / b - 1))
        self.assertLess(max(errs[16]), 0.03, errs)
        self.assertLess(max(errs[32]), 0.01, errs)

    def test_light_fog_default_case_under_1pct(self):
        # default look values (density 0.08, falloff 0.35, g 0.35, 8 steps), light 3 units off the ray
        d = one_ray((0.0, 0.0, -1.0))
        L, n = H.light_rows([{'type': 'point', 'pos': (3.0, 2.0, 0.0), 'intensity': 4.0}])
        p = dict(H.HAZE_DEFAULTS, noise=0)
        U = H.haze_rows(p, self.cam, n)
        v = H.inscatter(self.o, d, np.array([40.0]), U, L, n)[0][0, 0]
        b = brute(self.o, d[0], 40.0, (3, 2, 0), 4.0, 0.08, 0.0, 0.35, 0.35, 1.0, 0.05)
        self.assertLess(abs(v / b - 1), 0.01, (v, b))

    def test_spot_cone(self):
        d = one_ray((0.0, 0.0, -1.0))
        L, n = H.light_rows([{'type': 'spot', 'pos': (0.0, 4.0, 0.0), 'dir': (0, -1, 0), 'cone': 40, 'delta': 10,
                              'intensity': 3.0}])
        c0, c1 = L[3][0], L[3][1]
        self.assertAlmostEqual(c0, math.cos(math.radians(30)), 9)    # TD: full inside cone/2, 0 at cone/2 + delta
        self.assertAlmostEqual(c1, math.cos(math.radians(20)), 9)
        p = {'density': 0.1, 'falloff': 0, 'noise': 0, 'extinction': 1, 'g': 0, 'steps': 32, 'softradius': 0.05}
        U = H.haze_rows(p, self.cam, n)
        v = H.inscatter(self.o, d, np.array([20.0]), U, L, n)[0][0, 0]
        b = brute(self.o, d[0], 20.0, (0, 4, 0), 3.0, 0.1, 0, 0, 0, 1.0, 0.05, cone=((0, -1, 0), c0, c1))
        self.assertGreater(b, 0)
        self.assertLess(abs(v / b - 1), 0.05, (v, b))
        # pointing away from the ray: nothing
        L2, _ = H.light_rows([{'type': 'spot', 'pos': (0.0, 4.0, 0.0), 'dir': (0, 1, 0), 'cone': 40,
                               'intensity': 3.0}])
        self.assertEqual(H.inscatter(self.o, d, np.array([20.0]), U, L2, 1)[0][0, 0], 0.0)

    def test_range(self):
        d = one_ray((0.0, 0.0, -1.0))
        L, n = H.light_rows([{'type': 'point', 'pos': (0.0, 4.0, 0.0), 'intensity': 3.0, 'range': 2.5}])
        p = {'density': 0.1, 'falloff': 0, 'noise': 0, 'extinction': 0, 'g': 0, 'steps': 8}
        U = H.haze_rows(p, self.cam, n)
        self.assertEqual(H.inscatter(self.o, d, np.array([20.0]), U, L, n)[0][0, 0], 0.0)   # ray 3 units away
        L, n = H.light_rows([{'type': 'point', 'pos': (0.0, 2.0, 0.0), 'intensity': 3.0, 'range': 2.5}])
        v = H.inscatter(self.o, d, np.array([20.0]), U, L, n)[0][0, 0]
        b = brute(self.o, d[0], 20.0, (0, 2, 0), 3.0, 0.1, 0, 0, 0, 0, 0.05, rng=2.5)
        p['steps'] = 32
        U = H.haze_rows(p, self.cam, n)
        v32 = H.inscatter(self.o, d, np.array([20.0]), U, L, n)[0][0, 0]
        self.assertLess(abs(v32 / b - 1), 0.01, (v, v32, b))

    def test_area_and_directional(self):
        d = one_ray((0.0, 0.0, -1.0))
        La, n = H.light_rows([{'type': 'area', 'pos': (0.0, 3.0, 0.0), 'dir': (0, -1, 0), 'size': (2, 2),
                               'intensity': 2.0}])
        self.assertEqual(La[3][2:], [1.0, 1.0])
        p = {'density': 0.1, 'falloff': 0, 'noise': 0, 'extinction': 1, 'g': 0, 'steps': 16}
        U = H.haze_rows(p, self.cam, n)
        v = H.inscatter(self.o, d, np.array([20.0]), U, La, n)[0][0, 0]
        self.assertGreater(v, 0.0)
        Lb, _ = H.light_rows([{'type': 'area', 'pos': (0.0, 3.0, 0.0), 'dir': (0, 1, 0), 'size': (2, 2),
                               'intensity': 2.0}])       # emits upward, the ray is below: dark
        self.assertEqual(H.inscatter(self.o, d, np.array([20.0]), U, Lb, 1)[0][0, 0], 0.0)
        # directional: colour x phase x integral(sigma T) = (1 - T) / ext; vs a numeric integral
        Ld, _ = H.light_rows([{'type': 'directional', 'dir': (0, -1, 0), 'intensity': 1.0}])
        p = {'density': 0.2, 'falloff': 0.5, 'noise': 0, 'extinction': 0.7, 'g': 0.0, 'steps': 4}
        U = H.haze_rows(p, self.cam, 1)
        dd = one_ray((0.0, 0.3, -1.0))
        v = H.inscatter(self.o, dd, np.array([30.0]), U, Ld, 1)[0][0, 0]
        t = np.linspace(0, 30, 300001)
        pts = self.o + dd[0] * t[:, None]
        f = H.sigma(pts[:, 1], 0.2, 0, 0.5) * np.exp(-0.7 * H.opt_depth(self.o[1], dd[0, 1], t, 0.2, 0, 0.5))
        self.assertLess(abs(v / np.trapezoid(f, t) - 1), 1e-4)

    def test_optical_depth(self):
        for oy, dy, D, Hf in ((1.0, 0.3, 0.2, 0.5), (3.0, -0.4, 0.2, 0.5), (-1.0, 0.2, 0.3, 1.0), (1.0, 0.0, 0.2, 0.5),
                              (0.5, 0.00005, 0.1, 0.2), (2.0, 0.1, 0.1, 0.0)):
            t = np.linspace(0, 25, 250001)
            num = np.trapezoid(H.sigma(oy + dy * t, D, 0.0, Hf), t)
            self.assertLess(abs(float(H.opt_depth(oy, dy, 25.0, D, 0.0, Hf)) / num - 1), 1e-5, (oy, dy))

    def test_noise(self):
        U = H.haze_rows({'noise': 0.0}, self.cam)
        p = np.random.RandomState(1).rand(500, 3) * 10
        self.assertTrue(np.all(H.noise_factor(p, U) == 1.0))
        U = H.haze_rows({'noise': 1.0, 'noisescale': 0.5}, self.cam)
        nf = H.noise_factor(p, U)
        self.assertTrue(np.all(nf >= 0) and np.all(nf <= 2.0))
        self.assertGreater(nf.std(), 0.1)
        a = H.noise_factor(p, U, time=0.0)
        b = H.noise_factor(p + np.array(U[6][:3]) * 2.0, U, time=2.0)   # drift = moving with the wind
        self.assertLess(np.abs(a - b).max(), 1e-9)


@unittest.skipIf(np is None, 'numpy missing')
class Shafts(unittest.TestCase):
    def test_direction_and_occlusion(self):
        cam = cam0()
        L, n = H.light_rows([{'type': 'point', 'pos': (0.0, 3.0, 0.0), 'intensity': 1.0}])
        U = H.haze_rows({'shafts': 1.0, 'taps': 48, 'length': 1.0, 'decay': 1.0, 'disc': 0.08, 'density': 0.0,
                         'ambient': 0.0}, cam, n)
        suv, dist, ok = H.light_screen(U, L, 0)
        self.assertTrue(ok)
        w, h = 72, 128
        scene = np.zeros((h, w, 4))
        # an occluder disc just below the light on screen, inside the bright source disc
        oc = suv + np.array([0.0, -0.06])
        yy, xx = np.mgrid[0:h, 0:w]
        q = np.stack([((xx + 0.5) / w - oc[0]) * (w / h), (yy + 0.5) / h - oc[1]], -1)   # screen-height units
        scene[..., 3] = (np.sqrt((q ** 2).sum(-1)) < 0.03).astype(float)
        s = H.shafts(U, L, n, scene, w, h)[..., 0]
        s0 = H.shafts(U, L, n, np.zeros((h, w, 4)), w, h)[..., 0]

        def px(uv):
            return int(uv[1] * h), int(uv[0] * w)
        r = oc - suv
        behind = suv + r * 3.0                       # on the line light -> occluder, beyond it
        side = suv + np.array([np.linalg.norm(r) * 3.0 * h / w, 0.0])   # same screen distance, 90 degrees off
        self.assertLess(s[px(behind)], 0.6 * s0[px(behind)], (s[px(behind)], s0[px(behind)]))   # shadow streak
        self.assertGreater(s[px(side)], 0.95 * s0[px(side)], (s[px(side)], s0[px(side)]))      # not off-axis
        # the streak continues outward along the same line (direction = away from the light's screen position)
        far = suv + r * 5.0
        self.assertLess(s[px(far)], 0.8 * s0[px(far)])
        # light behind the camera: no shafts
        Lb, _ = H.light_rows([{'type': 'point', 'pos': (0.0, 1.0, 12.0), 'intensity': 1.0}])
        self.assertEqual(H.shafts(U, Lb, 1, scene, w, h).max(), 0.0)

    def test_screen_matches_px_camera(self):
        import px_logic as PXL
        cam_row = (1.0, 2.0, 7.0, 20.0)
        vp = PXL.cam_viewproj(cam_row, 60.0, 1080, 1920, 0.01, 1000.0)
        cam = H.camera_from_px(cam_row, 60.0, 1080, 1920, 0.01, 1000.0)
        for p in ((0, 0, 0), (1.5, 2.5, -2), (-2, 0.5, 1)):
            c = [sum(vp[r][k] * (list(p) + [1.0])[k] for k in range(4)) for r in range(4)]
            u, v, _z = H.project(cam, p)
            self.assertAlmostEqual(u, 0.5 + 0.5 * c[0] / c[3], 9)
            self.assertAlmostEqual(v, 0.5 + 0.5 * c[1] / c[3], 9)

    def test_camera_from_world(self):
        a = H.camera_lookat((1, 2, 5), (0, 0, 0), 40.0, 0.5625)
        world = [[a['right'][r], a['up'][r], -a['fwd'][r], a['pos'][r]] for r in range(3)] + [[0, 0, 0, 1]]
        fovx = math.degrees(2 * math.atan(math.tan(math.radians(20.0)) * 0.5625))
        b = H.camera_from_world(world, fovx, 0.5625, 'x')
        for k in ('pos', 'right', 'up', 'fwd'):
            for i in range(3):
                self.assertAlmostEqual(a[k][i], b[k][i], 9)
        self.assertAlmostEqual(a['tany'], b['tany'], 9)


@unittest.skipIf(np is None, 'numpy missing')
class Composite(unittest.TestCase):
    def test_off_is_identical(self):
        rs = np.random.RandomState(3)
        src = rs.rand(40, 24, 4)
        self.assertTrue(np.array_equal(H.ref_composite(src, rs.rand(20, 12, 4), amount=0.0), src))
        self.assertTrue(np.array_equal(H.ref_composite(src, np.zeros((20, 12, 4))), src))
        # haze pass with nothing on = zeros (then the composite is identical)
        U = H.haze_rows({'density': 0.0, 'shafts': 0.0, 'ambient': 0.0}, cam0(), 0)
        hz = H.ref_haze(U, H.light_rows([])[0], 0, src, 12, 20)
        self.assertEqual(np.abs(hz).max(), 0.0)

    def test_over(self):
        src = np.zeros((4, 4, 4))
        src[..., :] = (0.4, 0.2, 0.1, 1.0)
        hz = np.zeros((2, 2, 4))
        hz[..., :] = (0.3, 0.3, 0.3, 0.25)
        o = H.ref_composite(src, hz)
        self.assertTrue(np.allclose(o[0, 0], (0.4 * 0.75 + 0.3, 0.2 * 0.75 + 0.3, 0.1 * 0.75 + 0.3, 1.0)))
        e = H.ref_composite(np.zeros((4, 4, 4)), hz)
        self.assertTrue(np.allclose(e[0, 0], (0.3, 0.3, 0.3, 0.25)))

    def test_full_pass_and_depth(self):
        cam = cam0()
        L, n = H.light_rows([{'type': 'point', 'pos': (0.5, 2.0, 0.0), 'intensity': 3.0, 'colour': (1, 0.4, 0.1)},
                             {'type': 'spot', 'pos': (-1, 4, 0), 'dir': (0, -1, 0), 'intensity': 5.0}])
        U = H.haze_rows({'noise': 0.4}, cam, n)
        sc = np.zeros((20, 12, 4))
        sc[8:12, 4:8, 3] = 1.0
        a = H.ref_haze(U, L, n, sc, 12, 20)
        self.assertTrue(np.all(np.isfinite(a)) and a[..., 3].max() <= 1.0 and a.min() >= 0)
        # covered pixels march only to objdist: less fog than the sky next to them
        self.assertLess(a[9, 5, 3], a[2, 5, 3])
        # depth mode viewz: depth 3 everywhere = less haze alpha than no depth (sky to 60)
        U2 = H.haze_rows({'noise': 0.0, 'depthmode': 'viewz'}, cam, n)
        U0 = H.haze_rows({'noise': 0.0}, cam, n)
        b = H.ref_haze(U2, L, n, np.zeros((20, 12, 4)), 12, 20, depth=np.full((20, 12), 3.0))
        c = H.ref_haze(U0, L, n, np.zeros((20, 12, 4)), 12, 20)
        self.assertTrue(np.all(b[..., 3] < c[..., 3]))


@unittest.skipIf(np is None, 'numpy missing')
class Colour(unittest.TestCase):
    def test_light_colour_sources(self):
        cam = cam0()
        L, n = H.light_rows([{'type': 'point', 'pos': (0, 2, 0), 'colour': (1.0, 0.2, 0.1), 'intensity': 2.0},
                             {'type': 'point', 'pos': (1, 2, 0), 'colour': (0.1, 0.2, 1.0), 'intensity': 1.0}])
        U = H.haze_rows({'colour': (0.3, 0.6, 0.9)}, cam, n)
        src = H.light_cols(U, L, n)                                       # default cs = source: the light's colour
        self.assertTrue(np.allclose(src[0], (2.0, 0.4, 0.2)) and np.allclose(src[1], (0.1, 0.2, 1.0)))
        solid = H.light_cols(U, L, n, P.colsrc_vec('solid'))
        self.assertTrue(np.allclose(solid[0], (0.6, 1.2, 1.8)))
        stops = P.palette_stops({'source': 'neon_trio'})
        rows, ctl = P.pal_rows(stops), P.pal_ctl(stops, 'gradient')
        idx = H.light_cols(U, L, n, P.colsrc_vec('index', 0.0, 1.0), rows, ctl)
        self.assertTrue(np.allclose(idx[1], [c * 1.0 for c in P.pal_step(rows, ctl, 1)]))
        self.assertEqual(H.haze_cs({}), [3.0, 0.0, 1.0, 0.0])

    def test_light_rows(self):
        ls = [{'type': 'point', 'intensity': float(i + 1)} for i in range(10)] + [{'type': 'spot', 'enabled': False}]
        rows, n = H.light_rows(ls)
        self.assertEqual(n, H.HZ_LMAX)
        self.assertEqual(len(rows), H.HZ_LMAX * H.HZ_LROWS)
        self.assertEqual(rows[4][0], 10.0)                   # brightest first
        r, _ = H.light_rows([{'type': 'spot', 'cone': 30, 'delta': 0}])
        self.assertLess(r[3][0], r[3][1])                     # smoothstep edges strictly ordered
        r, _ = H.light_rows([{'type': 'directional', 'dir': (0, -3, 0)}])
        self.assertEqual(r[1][:3], [0.0, -1.0, 0.0])
        self.assertEqual(r[0][3], 3.0)

    def test_lights_from_real_w1a_light_block(self):
        import effectors_logic as EL
        world = [[0.0, 0.0, 2.0, 1.0], [0.0, 1.0, 0.0, 2.0], [-2.0, 0.0, 0.0, 3.0]]   # scaled, turned 90 deg about y
        b_spot = EL.light_block(world, {'type': 'spot', 'colour': (1, 0.5, 0.2), 'intensity': 3.0, 'cone_angle': 40,
                                        'cone_delta': 10, 'att_on': True, 'att_end': 6.0}, 0)
        b_area = EL.light_block(world, {'type': 'area', 'area_w': 1.0, 'area_h': 0.5, 'intensity': 1.0}, 1)
        ls = H.lights_from_block([b_spot, b_area])
        rows, n = H.light_rows(ls)
        self.assertEqual(n, 2)
        sp, ar = rows[0:5], rows[5:10]
        self.assertEqual(sp[0][:3], [1.0, 2.0, 3.0])
        self.assertEqual(sp[0][3], 1.0)
        for k in range(3):
            self.assertAlmostEqual(sp[1][k], (-1.0, 0.0, 0.0)[k], 9)      # shines along world -Z of the object
        self.assertEqual(sp[1][3], 6.0)
        self.assertAlmostEqual(sp[3][1], math.cos(math.radians(20)), 9)
        self.assertAlmostEqual(sp[3][0], math.cos(math.radians(30)), 9)
        self.assertEqual(sp[4][0], 3.0)
        self.assertEqual(ar[0][3], 2.0)
        self.assertAlmostEqual(ar[3][2], 1.0, 9)                         # half-U |(0,0,-2) x 0.5| = 1
        self.assertAlmostEqual(ar[3][3], 0.25, 9)
        for k in range(3):
            self.assertAlmostEqual(ar[4][1 + k], (0.0, 0.0, -1.0)[k], 9)

    def test_lights_from_w1a_block(self):
        blk = [[1.0, 0.2, 0.8, 2.0], [0.0, 1.5, 0.0, 1.0], [0.0, -1.0, 0.0, 3.0], [0.0, 4.0, 1.0, 1.0],
               [math.cos(math.radians(22.5)), math.cos(math.radians(32.5)), 0.0, 0.0], [0.0] * 4, [0.0] * 4]
        area = [[1, 1, 1, 1.0], [0, 3, 0, 2.0], [0, -1, 0, 0.0], [0, 0, 1, 0.0], [1, 1, 0, 0], [0, 0, 0.5, 0],
                [0.25, 0, 0, 0]]
        ls = H.lights_from_block([blk, area])
        rows, n = H.light_rows(ls)
        self.assertEqual(n, 2)
        k = 0 if rows[0][3] == 1.0 else 5
        sp, ar = rows[k:k + 5], rows[5 - k:10 - k]
        self.assertEqual(sp[2][:3], [1.0, 0.2, 0.8])
        self.assertEqual(sp[4][0], 2.0)
        self.assertEqual(sp[1][3], 4.0)
        self.assertAlmostEqual(sp[3][1], math.cos(math.radians(22.5)), 12)
        self.assertAlmostEqual(sp[3][0], math.cos(math.radians(32.5)), 12)
        self.assertEqual(ar[3][2:], [0.5, 0.25])
        self.assertEqual(ar[4][1:], [0.0, 0.0, 1.0])
        self.assertEqual(ar[1][3], 0.0)                       # attenuation off = unbounded

@unittest.skipIf(np is None, 'numpy missing')
class Bloom(unittest.TestCase):
    def setUp(self):
        rs = np.random.RandomState(7)
        self.s8 = rs.rand(24, 14, 4) * 2.0
        self.s4 = rs.rand(48, 27, 4) * 2.0

    def test_legacy_identical(self):
        rows = H.bloom_rows({'threshold': 0.8, 'intensity': 1.3})
        self.assertTrue(H.bloom_is_legacy(rows))
        a = H.ref_bloom(self.s8, self.s4, (14, 24), rows)
        b = H.ref_glow_legacy(self.s8, (14, 24), 0.8, 1.3, 1.5)
        self.assertTrue(np.array_equal(a, b))

    def test_tint_and_cs(self):
        a = H.ref_bloom(self.s8, self.s4, (14, 24), H.bloom_rows({'tint': (1.0, 0.0, 0.5)}))
        b = H.ref_glow_legacy(self.s8, (14, 24), 0.8, 1.0, 1.5)
        self.assertTrue(np.array_equal(a[..., 0], b[..., 0]) and a[..., 1].max() == 0.0)
        self.assertTrue(np.allclose(a[..., 2], b[..., 2] * 0.5))
        stops = P.palette_stops({'source': 'neon_trio'})
        rows, ctl = P.pal_rows(stops), P.pal_ctl(stops, 'gradient')
        c = H.ref_bloom(self.s8, self.s4, (14, 24), H.bloom_rows({'cs': P.colsrc_vec('palette', 0.0)}), pal_rows=rows,
                        pal_ctl=ctl)
        col = P.pal_eval(rows, ctl, 0.0)
        self.assertTrue(np.allclose(c[..., :3], b[..., :3] * np.array(col)))
        g = H.ref_bloom(self.s8, self.s4, (14, 24), H.bloom_rows({'saturation': 0.0}))
        self.assertTrue(np.allclose(g[..., 0], g[..., 1]) and np.allclose(g[..., 1], g[..., 2]))

    def test_two_scale_linear(self):
        w = H.ref_bloom(self.s8, self.s4, (27, 48), H.bloom_rows({'wide': 1.0, 'tight': 0.0}))
        t = H.ref_bloom(self.s8, self.s4, (27, 48), H.bloom_rows({'wide': 0.0, 'tight': 1.0}))
        m = H.ref_bloom(self.s8, self.s4, (27, 48), H.bloom_rows({'wide': 0.7, 'tight': 0.4}))
        self.assertTrue(np.allclose(m, 0.7 * w + 0.4 * t))
        self.assertFalse(np.allclose(w, t))

    def test_knee_clamp(self):
        k = H.ref_bloom(self.s8, self.s4, (14, 24), H.bloom_rows({'knee': 0.3}))
        self.assertTrue(np.all(np.isfinite(k)))
        hot = np.zeros((24, 14, 4))
        hot[12, 7, :3] = 50.0
        a = H.ref_bloom(hot, hot, (14, 24), H.bloom_rows({}))
        c = H.ref_bloom(hot, hot, (14, 24), H.bloom_rows({'clamp': 2.0}))
        self.assertLess(c.max(), a.max() * 0.1)

    def test_ring_radius(self):
        w, h = 90, 160
        src = np.zeros((h, w, 4))
        src[80, 45, :3] = 40.0
        rows = H.bloom_rows({'wide': 0.0, 'ring': 1.0, 'ringradius': 0.2, 'ringwidth': 0.0, 'threshold': 0.5})
        r = H.ref_bloom(src, src, (w, h), rows)[..., 1]
        ys, xs = np.nonzero(r > r.max() * 0.25)
        dy = (ys + 0.5) / h - (80.5 / h)
        dx = ((xs + 0.5) / w - (45.5 / w)) * (w / h)
        rad = np.sqrt(dx * dx + dy * dy)
        self.assertLess(abs(np.median(rad) - 0.2), 0.02, np.median(rad))
        self.assertEqual(r[80, 45], 0.0)


SHADERS = ('px_haze.glsl', 'px_haze_comp.glsl', 'px_bloom.glsl')


class ShaderText(unittest.TestCase):
    def test_ascii_and_sizes(self):
        for n in SHADERS + ('px_haze_logic.py', 'px_haze.py'):
            path = os.path.join(GLSL if n.endswith('.glsl') else BUILDERS, n)
            with open(path, 'rb') as fh:
                fh.read().decode('ascii')
        t = H.shader_text('px_haze.glsl')
        self.assertIn('uniform vec4 uH[%d];' % H.HZ_ROWS, t)
        self.assertIn('uniform vec4 uHL[%d];' % (H.HZ_LMAX * H.HZ_LROWS), t)
        self.assertIn('pxColSrc', t)
        self.assertIn('uniform vec4 uPal[PX_PAL_MAX]', t)
        b = H.shader_text('px_bloom.glsl')
        for u in H.BR_ROWS + ('uGlowCs',):
            self.assertIn('uniform vec4 %s;' % u, b)
        for n in SHADERS:                                # at most 2 wired inputs (T-84 / T-88)
            idx = [int(x) for x in re.findall(r'sTD2DInputs\[(\d+)\]', H.shader_text(n))]
            self.assertLessEqual(max(idx), 1, n)

    def test_loop_bounds_match_logic(self):
        t = H.shader_text('px_haze.glsl')
        self.assertIn('k < %d' % H.HZ_STEPS_MAX, t)
        self.assertIn('k < %d' % H.HZ_TAPS_MAX, t)
        self.assertIn('i < %d' % H.HZ_LMAX, t)

    @unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
    def test_glslc(self):
        for n in SHADERS:
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, 's.comp')
                with open(p, 'w') as fh:
                    fh.write(STUB_COMPUTE + H.shader_text(n))
                r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                    '-o', os.devnull, p], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, '%s\n%s' % (n, r.stderr[:2000]))

    def test_cost_model(self):
        c = H.haze_cost_ms()
        self.assertLessEqual(c['haze'], 0.8, c)
        b = H.bloom_cost_ms()
        self.assertLessEqual(b['delta'], 0.3, b)


# ------------------------------------------------------------------ fake TD for the standalone builder
class FakePar(object):
    def __init__(self, name):
        self.name, self.val, self.expr, self.mode, self.default = name, None, None, None, None
        self.menuNames = self.menuLabels = None
        self.normMin = self.normMax = None

    def eval(self):
        return self.val


class FakePars(object):
    def __init__(self, auto=True):
        object.__setattr__(self, '_d', {})
        object.__setattr__(self, '_auto', auto)

    def __getattr__(self, k):
        d = object.__getattribute__(self, '_d')
        if k not in d:
            if not object.__getattribute__(self, '_auto'):
                return None
            d[k] = FakePar(k)
        return d[k]

    def __setattr__(self, k, v):
        getattr(self, k).val = v

    def add(self, k):
        d = object.__getattribute__(self, '_d')
        d[k] = FakePar(k)
        return d[k]


class FakeConn(object):
    def __init__(self, owner, i):
        self.owner, self.i = owner, i

    def connect(self, s):
        while len(self.owner.inputs) <= self.i:
            self.owner.inputs.append(None)
        self.owner.inputs[self.i] = s


class FakePage(object):
    def __init__(self, comp, name):
        self.comp, self.name = comp, name

    def _one(self, n, label=None):
        return [self.comp.par.add(n)]

    appendFloat = appendInt = appendToggle = appendStr = appendMenu = _one

    def appendRGB(self, n, label=None):
        return [self.comp.par.add(n + k) for k in 'rgb']

    def appendXYZ(self, n, label=None):
        return [self.comp.par.add(n + k) for k in 'xyz']


class FakeOp(object):
    def __init__(self, cls, name, comp=False):
        self.OPType, self.name, self.valid = cls, name, True
        self.par = FakePars(auto=not comp)
        self.inputs = []
        self.inputConnectors = [FakeConn(self, i) for i in range(3)]   # GLSL TOP: 3 connectors (T-84)
        blk = lambda: types.SimpleNamespace(numBlocks=0)
        self.seq = types.SimpleNamespace(vec=blk(), array=blk())
        self.text, self.comment, self.dock, self.viewer = '', '', None, True
        self.ops_, self.customPages, self.allowCooking = {}, [], False

    def op(self, n):
        return self.ops_.get(n)

    def create(self, cls, name):
        o = FakeOp(cls.__name__, name, comp=(cls.__name__ == 'baseCOMP'))
        self.ops_[name] = o
        return o

    def appendCustomPage(self, n):
        pg = FakePage(self, n)
        self.customPages.append(pg)
        return pg


class StandaloneBuilder(unittest.TestCase):
    def test_build_on_fakes(self):
        ns = {'__name__': 'px_haze_fake'}
        for c in ('baseCOMP', 'inTOP', 'outTOP', 'glslTOP', 'textDAT', 'scriptCHOP', 'resolutionTOP', 'compositeTOP',
                  'switchTOP'):
            ns[c] = type(c, (), {})
        ns['ParMode'] = types.SimpleNamespace(EXPRESSION='expr', CONSTANT='const')
        root = FakeOp('containerCOMP', 'lab', comp=True)
        ns['op'] = lambda p: root if p == '/project1/lab' else None
        ns['safe_destroy'] = lambda o: None
        with open(os.path.join(BUILDERS, 'px_haze.py')) as fh:
            exec(compile(fh.read(), 'px_haze.py', 'exec'), ns)
        ns['HERE'] = BUILDERS
        c = ns['build']('/project1/lab', 'FX_haze', src_dir=BUILDERS)
        c2 = ns['build']('/project1/lab', 'FX_haze', src_dir=BUILDERS)        # idempotent
        self.assertIs(c, c2)
        pars = set(object.__getattribute__(c.par, '_d'))
        glsl = [o for o in c.ops_.values() if o.OPType == 'glslTOP']
        self.assertEqual(sorted(o.name for o in glsl), ['bloom', 'comp', 'haze'])
        for g in glsl:
            wired = [s for s in g.inputs if s is not None]
            self.assertLessEqual(len(g.inputs), 3, g.name)
            text = c.op(g.par.computedat.val).text
            idx = [int(x) for x in re.findall(r'sTD2DInputs\[(\d+)\]', text)]
            self.assertLess(max(idx), len(wired), g.name)
            declared = set(re.findall(r'uniform vec4 (u\w+)', text))
            bound = set()
            for k in range(int(g.seq.vec.numBlocks)):
                bound.add(getattr(g.par, 'vec%dname' % k).val)
            for k in range(int(g.seq.array.numBlocks)):
                bound.add(getattr(g.par, 'array%dname' % k).val)
                self.assertIn(getattr(g.par, 'array%dchop' % k).val, c.ops_)
            self.assertEqual(declared, bound, g.name)
            # every parent par an expression names exists
            for k in range(int(g.seq.vec.numBlocks)):
                for comp in 'xyzw':
                    e = getattr(g.par, 'vec%dvalue%s' % (k, comp)).expr or ''
                    for m in re.findall(r"parent\(\)\.par\.(\w+)", e):
                        self.assertIn(m, pars, (g.name, e))
        self.assertEqual(c.op('haze').inputs[0].name, 'haze_src')
        self.assertEqual(c.op('comp').inputs[1].name, 'haze')
        self.assertEqual([s.name for s in c.op('bloom').inputs], ['glow_e', 'glow_q'])
        self.assertEqual(c.op('out1').inputs[0].name, 'sw_bloom')
        for s in ('haze_rows', 'light_rows', 'pal_chop'):        # event-driven: no per-frame clock
            self.assertIsNone(c.op(s).par.Frame.expr)
        self.assertEqual(c.op('haze').par.inputfiltertype.val, 'mipmap')
        self.assertNotIn('width', c.op('haze_rt').text.split('def cook')[1])  # no TOP size read in the row cooks
        # runtime module compiles and its par reads exist
        compile(c.op('haze_rt').text, 'haze_rt', 'exec')
        for m in re.findall(r"p(?:ar)?\.([A-Z]\w+)", c.op('haze_rt').text):
            if m in ('Lights', 'Camera', 'Palsource', 'Palstops') or m in pars:
                continue
            self.assertIn(m, pars, m)


if __name__ == '__main__':
    unittest.main()
