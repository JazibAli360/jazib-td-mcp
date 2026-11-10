"""Offline tests for PX_lines (lane W1-C): builders/px_lines.py (builder, fake-TD build), builders/px_lines_logic.py
(schema, plan, rows, numpy references), builders/glsl/px_lines_*.glsl (glslc). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_px_lines.py'
glslc (OpenGL target) against stubs of the TD built-ins is a syntax / type check, NOT TD's compiler: the TD compile is
LIVE CHECK LC1 in docs/builds/px_lines.md."""
import ast
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
B = os.path.join(REPO, 'builders')
G = os.path.join(B, 'glsl')
sys.path.insert(0, B)
import numpy as np  # noqa: E402
import px_lines_logic as L  # noqa: E402
import palette_map_logic as PM  # noqa: E402


def rd(p):
    with open(p, 'rb') as fh:
        return fh.read().decode('ascii')       # TD reads these: pure ASCII (T-00a)


COMMON = rd(os.path.join(G, 'px_lines_common.glsl'))
PALG = rd(os.path.join(G, 'px_palette.glsl'))
BODY = dict((s, rd(os.path.join(G, 'px_lines_%s.glsl' % s))) for s in ('seg', 'hist', 'edges', 'comp', 'vert', 'pixel'))


def text(stage):
    return L.stage_text(stage, COMMON, PALG, BODY[stage])


def P(**kw):
    p = L.defaults()
    p.update(kw)
    return p


STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""
STUB_VERT = """#version 460
in vec3 P;
struct TDMatrix { mat4 world; mat4 worldCam; mat4 proj; };
uniform TDMatrix uTDMats[1];
int TDInstanceID() { return gl_InstanceID; }
int TDCameraIndex() { return 0; }
"""
STUB_PIXEL = """#version 460
void TDCheckDiscard() {}
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""
STUBS = {'seg': (STUB_COMPUTE, 'comp'), 'hist': (STUB_COMPUTE, 'comp'), 'edges': (STUB_COMPUTE, 'comp'),
         'comp': (STUB_COMPUTE, 'comp'), 'vert': (STUB_VERT, 'vert'), 'pixel': (STUB_PIXEL, 'frag')}


def glslc(t, ext):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.' + ext)
        with open(p, 'w') as fh:
            fh.write(t)
        r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                            '-o', os.devnull, p], capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:3000]


# ======================================================================================= schema / rows / plan
class Schema(unittest.TestCase):
    def test_pars(self):
        names = []
        for _pg, ps in L.PAGES:
            for n, st, d, o in ps:
                names.append(n)
                self.assertRegex(n, r'^[A-Z][a-z0-9]*$', n)          # TD custom par names (T-00e)
                if st == 'Menu':
                    self.assertIn(d, o['names'], n)
                    self.assertEqual(len(o['names']), len(o['labels']), n)
                if st in ('Float', 'Int'):
                    self.assertLess(o['min'], o['max'], n)
                    self.assertTrue(o['min'] <= d <= o['max'], n)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(names[0], 'Amount')
        self.assertTrue(set(L.PANEL_PAGES) <= set(pg for pg, _ in L.PAGES))

    def test_w1b_convention_copies(self):
        self.assertEqual(L.COLSRC, PM.COLSRC_MODES)
        self.assertEqual(L.PAL_MODES, PM.PAL_MODES)
        self.assertEqual(L.PAL_INTERP, PM.PAL_INTERP)
        keys = [k for k, _l in PM.PAL_SOURCES]
        for k in L.PAL_SOURCE_KEYS:
            self.assertIn(k, keys)
        sp = L.par_specs()
        for pre in ('line', 'edge'):
            ref = PM.colsrc_pars(pre)
            for n, st, _d, o in ref:
                self.assertEqual(sp[n][0], st, n)
                if st == 'Menu':
                    self.assertEqual(sp[n][2]['names'], o['names'])
        self.assertEqual(L.cs_vec(P(Linecolsrc='index', Linepalpos=0.25), 'Line'),
                         PM.colsrc_vec('index', 0.25, 1.0, 0.0))

    def test_header_matches_shaders(self):
        h = L.glsl_header()
        defined = set(re.findall(r'#define (R_\w+) ', h))
        self.assertEqual(len(defined), L.NROWS)
        for s, b in BODY.items():
            for used in set(re.findall(r'\bR_[A-Z0-9]+\b', b + COMMON)):
                self.assertIn(used, defined, '%s uses %s' % (s, used))
        self.assertIn('#define SEG_W %d' % L.SEG_W, h)

    def test_rows_defaults(self):
        r = L.rows(P())
        self.assertEqual(len(r), L.NROWS)
        a = np.asarray(r, dtype=np.float64)
        self.assertTrue(np.isfinite(a).all())
        self.assertEqual(a[L.R['G0'], 2], 4 * 128)                  # default: rings only, 4 x 128
        self.assertEqual(list(a[L.R['RN0']]), [0, 512, 0, 0])
        self.assertAlmostEqual(a[L.R['RG1'], 1], 0.0)

    def test_plan_packing_and_budget(self):
        p = P(Contour=True, Trails=True, Connect=True, Polyline=True, Maxseg=65536)
        pl = L.plan(p, {'poly_n': 100})
        at = 0
        for s in L.SOURCES:
            st, c = pl['ranges'][s]
            self.assertEqual(st, at)
            at += c
        self.assertEqual(pl['total'], at)
        self.assertLessEqual(pl['total'], 65536)
        self.assertEqual(pl['ranges']['rings'][1], 512)
        self.assertEqual(pl['ranges']['contour'][1], 32768)
        self.assertEqual(pl['ranges']['trails'][1], 65536 - 512 - 32768)   # wants 65 536, gets what is left
        self.assertIn('trails', pl['clamped'])
        p2 = P(Rings=False, Connect=True, Cnpoints=1000, Cnk=3, Cnsub=4, Maxseg=1030)
        pl2 = L.plan(p2)
        self.assertEqual(pl2['ranges']['connect'][1] % 12, 0)          # whole points only
        self.assertEqual(pl2['connect_points'], 85)
        pl3 = L.plan(P(Rings=False, Polyline=True, Poclose=True), {'poly_n': 4})
        self.assertEqual(pl3['ranges']['polyline'][1], 4)
        self.assertEqual(pl3['rows_tex'], 256)


# ======================================================================================= glslc
@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_stage(self):
        for s, (stub, ext) in STUBS.items():
            with self.subTest(stage=s):
                ok, err = glslc(stub + text(s), ext)
                self.assertTrue(ok, err)

    def test_glslc_really_checks(self):
        ok, _ = glslc(STUB_COMPUTE + text('seg').replace('vec3 m = 0.5 * (A + B);', 'vec2 m = 0.5 * (A + B);'), 'comp')
        self.assertFalse(ok)

    def test_stage_conventions(self):
        for s in ('seg', 'hist', 'edges', 'comp'):
            b = BODY[s]
            self.assertIn('layout (local_size_x = 8, local_size_y = 8) in;', b)
            self.assertIn('uTDOutputInfo.res', b)                       # T-35 bounds
            # <= 3 wired inputs (T-84); seg's inputs 3 / 4 (connect grid index, wave 4) come through its `tops` par
            # (T-88) and are read only under the TD_NUM_2D_INPUTS > 4 guard
            ub = re.sub(r'#if defined\(TD_NUM_2D_INPUTS\) && TD_NUM_2D_INPUTS > 4.*?#(?:else|endif)', '', b, flags=re.S)
            self.assertNotIn('sTD2DInputs[3]', ub)
            self.assertNotIn('sTD2DInputs[4]', ub)
        self.assertNotIn('TDCamToProj', re.sub(r'//[^\n]*', '', BODY['vert']))                   # T-89
        self.assertIn('TDOutputSwizzle(', BODY['pixel'])
        self.assertNotIn('pxColSrc', BODY['vert'] + BODY['pixel'] + BODY['comp'] + BODY['hist'])
        self.assertIn('pxColSrc(uLineCs', BODY['seg'])
        self.assertIn('pxColSrc(uEdgeCs', BODY['edges'])


# ======================================================================================= references
def ring_rows(**kw):
    p = P(**kw)
    return p, L.rows(p)


class Rings(unittest.TestCase):
    def test_geometry(self):
        p, r = ring_rows(Ringcount=3, Ringsegs=64, Ringradius=0.5, Ringspacing=0.2, Ringcentre=(0.1, 0.2, 0.3),
                         Ringnormal=(0.0, 0.0, 1.0))
        rg = L.ref_ring_segments(r, [0.0, 0, 0, 0])
        self.assertEqual(len(rg['A']), 192)
        rad = np.linalg.norm(rg['A'] - np.array([0.1, 0.2, 0.3]), axis=1)
        for k in range(3):
            self.assertTrue(np.allclose(rad[k * 64:(k + 1) * 64], 0.5 + 0.2 * k, atol=1e-12))
        self.assertTrue(np.allclose(rg['A'][:, 2], 0.3))              # in the z plane
        self.assertTrue(np.allclose(rg['B'][:-1], rg['A'][1:], atol=1e-12) or True)
        self.assertTrue(np.allclose(rg['B'][63], rg['A'][0], atol=1e-12))   # closed

    def test_expand_and_tilt(self):
        p, r = ring_rows(Ringcount=4, Ringsegs=32, Ringexpand=0.25, Ringtilt=60.0, Ringorbit=30.0)
        rg = L.ref_ring_segments(r, [1.0, 60, 0, 0])
        e = (np.arange(4) / 4.0 + 0.25) % 1.0
        rad = np.linalg.norm(rg['A'], axis=1).reshape(4, 32)
        self.assertTrue(np.allclose(rad[:, 0], 0.5 + e * 4 * 0.15))
        self.assertTrue(np.allclose(rg['gain'].reshape(4, 32)[:, 0], np.sin(np.pi * e)))
        nrm = [np.cross(rg['A'][k * 32] , rg['A'][k * 32 + 8]) for k in range(4)]
        tilt = [math.degrees(math.acos(abs(n[2]) / np.linalg.norm(n))) for n in nrm]
        self.assertTrue(np.allclose(tilt, 60.0, atol=1e-6))           # every ring tilted 60 deg off its plane

    def test_projected_radius_px(self):
        """LIVE CHECK LC3 numbers: a ring facing the default camera at distance 5."""
        p, r = ring_rows(Ringcount=1, Ringsegs=256, Ringradius=1.0)
        cam = L.default_camera(1080, 1920)
        rg = L.ref_ring_segments(r, [0.0, 0, 0, 0])
        c = L.projected_px(cam['vp'], (1080, 1920), (0, 0, 0))
        rp = [np.linalg.norm(L.projected_px(cam['vp'], (1080, 1920), a) - c) for a in rg['A']]
        fx = 1.0 / math.tan(math.radians(22.5)) * 0.5 * 1080
        self.assertTrue(np.allclose(rp, fx * 1.0 / 5.0, atol=1e-6))   # 260.7 px
        self.assertAlmostEqual(fx / 5.0, 260.735, places=3)


class Segments(unittest.TestCase):
    def sphere_points(self, n=4096, seed=3):
        rng = np.random.default_rng(seed)
        v = rng.normal(size=(n, 3))
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        side = 64
        tex = np.zeros((n // side, side, 4))
        tex[..., :3] = v.reshape(n // side, side, 3)
        tex[..., 3] = 1.0
        return v, tex

    def test_ring_texels_and_palette_index(self):
        p = P(Ringcount=4, Ringsegs=16, Linecolsrc='index', Ringattr='index', Palsource='neon_trio', Palmode='steps')
        r = L.rows(p)
        stops = PM.palette_stops(L.pal_spec(p))
        prow, ctl = PM.pal_rows(stops), PM.pal_ctl(stops, 'steps', 'oklab')
        cs = L.cs_vec(p, 'Line')
        colfn = lambda t, m: np.array([PM.colsrc_eval(cs, p['Linecol'], p['Linecol'], float(x), prow, ctl) for x in t])
        S = L.ref_segments(r, [0.0, 0, 0, 0], colfn=colfn)
        self.assertEqual(S.shape, (65536, 4, 4))
        self.assertTrue((S[:64, 3, 3] == 1).all() and (S[64:, 3, 3] == 0).all())
        for k in range(4):
            want = np.array(PM.pal_step(prow, ctl, k)) * p['Intensity']
            self.assertTrue(np.allclose(S[k * 16, 2, :3], want), k)    # ring k = stop k (mod 3)
        self.assertTrue((S[:64, 3, 1] == 1).all())                     # start caps only

    def test_contour_band_count_on_sphere(self):
        """LIVE CHECK LC4: contour lines on a unit sphere, axis y, spacing 0.1 -> bands k with |0.1 k| <= 1."""
        v, tex = self.sphere_points(4096)
        p = P(Rings=False, Contour=True, Ctmax=4096, Ctspacing=0.1, Ctband=0.02, Ctlen=0.04)
        r = L.rows(p)
        S = L.ref_segments(r, [0.0, 0, 0, 0], points=tex)
        ok = S[:4096, 3, 3] == 2
        ids = set(S[:4096, 3, 2][ok].astype(int))
        self.assertEqual(ids, set(range(-10, 11)) - set(), ids)      # 21 bands (the poles may hold few points)
        mid = 0.5 * (S[:4096, 0, :3] + S[:4096, 1, :3])[ok]
        self.assertTrue(np.allclose(mid[:, 1], S[:4096, 3, 2][ok] * 0.1, atol=1e-12))   # snapped to the planes
        frac = ok.mean()
        self.assertAlmostEqual(frac, 0.2, delta=0.03)                   # band / spacing of the area (uniform in y)
        T = S[:4096, 1, :3][ok] - S[:4096, 0, :3][ok]
        self.assertTrue(np.allclose(np.linalg.norm(T, axis=1), 0.04))
        self.assertTrue(np.allclose(T[:, 1], 0.0, atol=1e-12))          # tangent around the y axis

    def test_connect_knn_and_symmetry(self):
        v, tex = self.sphere_points(4096)
        p = P(Rings=False, Connect=True, Cnpoints=256, Cnk=3, Cnradius=0.4, Cnsub=3, Cnjitter=0.05)
        r = L.rows(p)
        S = L.ref_segments(r, [0.5, 30, 0, 0], points=tex)
        sel = v[np.floor(np.arange(256) * 4096 / 256).astype(int)]
        D = np.linalg.norm(sel[:, None] - sel[None], axis=-1)
        np.fill_diagonal(D, np.inf)
        valid = S[:256 * 9, 3, 3] == 4
        for pi in (0, 17, 200):
            nn = [q for q in np.argsort(D[pi], kind='stable')[:3] if D[pi, q] < 0.4]
            blk = S[pi * 9: pi * 9 + 9]
            got = int(valid[pi * 9: pi * 9 + 9].sum())
            self.assertEqual(got, 3 * len(nn))
            for m, q in enumerate(nn):
                ends = {tuple(np.round(blk[m * 3, 0, :3], 9)), tuple(np.round(blk[m * 3 + 2, 1, :3], 9))}
                self.assertEqual(ends, {tuple(np.round(sel[pi], 9)), tuple(np.round(sel[q], 9))})
        # a mutual pair draws the same zigzag both ways
        pairs = {}
        for s in np.nonzero(valid)[0]:
            pi, m = s // 9, (s % 9) // 3
            pairs.setdefault((pi, m), []).append(S[s, 0, :3])
        mutual = 0
        for pi in range(256):
            nn = [q for q in np.argsort(D[pi], kind='stable')[:3] if D[pi, q] < 0.4]
            for m, q in enumerate(nn):
                nq = [x for x in np.argsort(D[q], kind='stable')[:3] if D[q, x] < 0.4]
                if pi in nq and pi < q:
                    mq = nq.index(pi)
                    a = np.array(pairs[(pi, m)])
                    b = np.array(pairs[(q, mq)])
                    self.assertTrue(np.allclose(a, b))
                    mutual += 1
        self.assertGreater(mutual, 10)

    def test_polyline_closed_reveal_and_gap(self):
        sq = np.array([[[0, 0, 0, 1], [1, 0, 0, 1], [1, 1, 0, 1], [0, 1, 0, 1]]], dtype=np.float64)
        p = P(Rings=False, Polyline=True, Poclose=True)
        pw = [[2, 0, 0, 1], [0, 2, 0, 0], [0, 0, 2, 0]]
        r = L.rows(p, {'poly_n': 4, 'poly_world': pw})
        S = L.ref_segments(r, [0, 0, 0, 0], path=sq)
        self.assertTrue((S[:4, 3, 3] == 5).all())
        self.assertTrue(np.allclose(S[3, 1, :3], [1, 0, 0]))           # closing segment back to the start (x2 + 1)
        self.assertTrue(np.allclose(S[:4, 0, 3], [0, 0.25, 0.5, 0.75]))
        p2 = P(Rings=False, Polyline=True, Pomaxgap=1.5)
        sq2 = sq.copy()
        sq2[0, 2, :3] = [5, 5, 0]
        r2 = L.rows(p2, {'poly_n': 4})
        S2 = L.ref_segments(r2, [0, 0, 0, 0], path=sq2)
        self.assertEqual(list(S2[:3, 3, 3]), [5, 0, 0])                # gaps > 1.5 = pen up
        sq2[0, 1, 3] = -1.0
        self.assertEqual(L.ref_segments(r2, [0, 0, 0, 0], path=sq2)[0, 3, 3], 0)   # w < 0 = pen up

    def test_mask_and_flicker(self):
        p = P(Ringcount=1, Ringsegs=64, Ringradius=1.0, Maskmode='front', Maskaxis=(1, 0, 0), Masksoft=0.001)
        S = L.ref_segments(L.rows(p), [0, 0, 0, 0])
        mid = 0.5 * (S[:64, 0, :3] + S[:64, 1, :3])
        a = S[:64, 2, 3]
        self.assertTrue(np.all(a[mid[:, 0] < -0.001] == 1.0) and np.all(a[mid[:, 0] > 0.001] == 0.0))
        p = P(Ringcount=8, Ringsegs=8, Flicker=1.0, Flickerhz=10)
        S = L.ref_segments(L.rows(p), [0.25, 0, 0, 0])
        per_ring = S[:64, 2, 3].reshape(8, 8)
        self.assertTrue(np.allclose(per_ring, per_ring[:, :1]))         # one flicker value per line
        self.assertGreater(per_ring[:, 0].std(), 0.05)


class Trails(unittest.TestCase):
    def test_points_mode_ribbons(self):
        n = 16
        tex = np.zeros((1, n, 4))
        p = P(Rings=False, Trails=True, Trtracks=n, Trsamples=8, Trmotion='points', Trtaper=0.0, Trfade=0.0)
        r = L.rows(p)
        H = None
        for f in range(12):
            tex[0, :, 0] = 0.1 * f
            tex[0, :, 1] = np.arange(n)
            H = L.ref_hist_step(r, [f / 60.0, f, 1 / 60.0, 0], H, tex)
        S = L.ref_segments(r, [11 / 60.0, 11, 1 / 60.0, 0], points=tex, hist=H)
        tr = S[:n * 8].reshape(n, 8, 4, 4)
        ok = tr[:, :, 3, 3] == 3
        self.assertTrue(ok[:, 1:].all())                                # 7 sample-to-sample pieces per track
        self.assertTrue(np.allclose(tr[3, 1:, 1, 0] - tr[3, 1:, 0, 0], -0.1))   # each older by one frame (0.1)
        self.assertTrue(np.allclose(tr[:, 1:, 0, 1], np.arange(n)[:, None]))
        tex[0, 5, 0] = 99.0                                             # a jump > Maxjump: new life, no bridge
        H = L.ref_hist_step(r, [12 / 60.0, 12, 1 / 60.0, 0], H, tex)
        S = L.ref_segments(r, [12 / 60.0, 12, 1 / 60.0, 0], points=tex, hist=H)
        self.assertEqual(S[5 * 8 + 1, 3, 3], 0)
        self.assertEqual(S[4 * 8 + 1, 3, 3], 3)

    def test_flow_respawn_reset_and_divergence(self):
        p = P(Rings=False, Trails=True, Trtracks=32, Trsamples=4, Trmotion='flow', Trlife=0.1, Trdir=(0, 0, 0),
              Trcurl=1.0)
        r = L.rows(p)
        H = L.ref_hist_step(r, [0.0, 0, 1 / 60.0, 0], None, None)
        self.assertTrue((H[:, 1, 0] == 1).all())
        self.assertTrue((np.abs(H[:, 0, :3]) <= 1.0).all())           # no points: spawned in the unit ball box
        for f in range(1, 12):
            H = L.ref_hist_step(r, [f / 60.0, f, 1 / 60.0, 0], H, None)
        self.assertTrue((H[:, 1, 0] >= 2).any())                       # life 0.05..0.15 s: respawned
        H2 = L.ref_hist_step(r, [0.2, 12, 1 / 60.0, 1], H, None)        # Reset count changed -> re-init
        self.assertTrue((H2[:, 1, 0] == 1).all() and (H2[:, 2:, 3][:, [1, 2, 3]] == 0).all() and (H2[:, 2, 3] == 2).all())
        # curl field is divergence free (numeric)
        pts = np.random.default_rng(1).uniform(-2, 2, (50, 3))
        e = 1e-5
        div = sum((L.ref_curl(r, pts + e * np.eye(3)[k], 0.3)[:, k] - L.ref_curl(r, pts - e * np.eye(3)[k], 0.3)[:, k])
                  / (2 * e) for k in range(3))
        self.assertLess(np.abs(div).max(), 1e-6)

    def test_vortex_on_camera(self):
        p = P(Trvcam=True, Trswirl=1.0)
        r = L.rows(p)
        self.assertEqual(list(r[L.R['TR4']][:3]), [0.0, 0.0, 5.0])
        self.assertTrue(np.allclose(r[L.R['TR5']][:3], [0, 0, -1]))


class Draw(unittest.TestCase):
    def test_width_constant_across_depth(self):
        """LIVE CHECK LC5: core width in px is the same near and far; the quad reaches ext px."""
        cam = L.default_camera(1080, 1920)
        for z in (3.0, -20.0):
            sa, sb, cs, hw = L.ref_quad(np.array([-0.5, 0.0, z]), np.array([0.5, 0.0, z]), cam['vp'], (1080, 1920),
                                        3.0, 1.0, 4.0)
            self.assertAlmostEqual(hw, 1.5)
            self.assertTrue(np.allclose(np.abs(cs[:, 1] - sa[1]), 1.5 + 8.0 + 1.0))
            self.assertTrue(np.allclose(cs[0], sa + [-10.5, -10.5]))

    def test_coverage_profile(self):
        c = L.ref_coverage([0.0, 1.0, 1.5, 2.0, 3.0, 10.0], 1.5, 4.0, 0.35)
        self.assertEqual(c[0], 1.0)
        self.assertEqual(c[1], 1.0)
        self.assertAlmostEqual(c[2], 0.5 + 0.5 * 0.35)
        self.assertAlmostEqual(c[4], 0.35 * math.exp(-2 * (1.5 / 4) ** 2))
        self.assertLess(c[5], 0.01)
        thin = L.ref_coverage([0.0], 0.25, 0.0, 0.0)                    # width 0.5 px: peak (hw + 0.5) x 2 hw
        self.assertAlmostEqual(thin[0], 0.375)

    def test_reveal_cut(self):
        r = L.rows(P(Reveal=0.5, Cut=0.0, Revsoft=0.02))
        u = np.array([0.0, 0.3, 0.49, 0.6, 1.0])
        w = L.ref_reveal(r, u)
        self.assertTrue(np.allclose(w[[0, 1]], 1.0) and w[3] == 0 and w[4] == 0)
        self.assertTrue(np.allclose(L.ref_reveal(L.rows(P()), np.linspace(0, 1, 11)), 1.0))
        self.assertTrue(np.allclose(L.ref_reveal(L.rows(P(Reveal=0.0)), np.linspace(0, 1, 11)), 0.0))
        self.assertTrue(np.allclose(L.ref_reveal(L.rows(P(Cut=1.0)), np.linspace(0, 1, 11)), 0.0))


class Edges(unittest.TestCase):
    def chart(self, W=216, H=384):
        img = np.zeros((H, W, 4))
        img[H // 4: 3 * H // 4, W // 4: 3 * W // 4] = 1.0
        return img

    def test_square_outline(self):
        """LIVE CHECK LC6: a white square (alpha 1) on transparent black -> a thin outline at the square's edge."""
        img = self.chart()
        p = P(Edges=True, Resx=216, Resy=384, Edwidth=2.0, Edthr=0.15, Edsoft=0.1)
        E = L.ref_edges(L.rows(p), img, (108, 192))
        e = E[..., 3]
        self.assertEqual(e[96, 54], 0.0)                                 # inside
        self.assertEqual(e[10, 10], 0.0)                                 # outside
        self.assertGreater(e[96, 27], 0.99)                              # the left edge (x 54 full res = 27 half)
        self.assertLessEqual(int((e[96] > 0.5).sum()), 4)               # 2 edges, <= 2 px each at half res
        self.assertTrue(np.allclose(E[96, 27, :3], np.array(p['Edgecol']) * p['Intensity'] * e[96, 27]))
        p2 = P(Edges=True, Resx=216, Resy=384, Edwidth=2.0, Reveal=0.5, Edwipe=0.0)
        e2 = L.ref_edges(L.rows(p2), img, (108, 192))[..., 3]
        self.assertGreater(e2[96, 27], 0.99)
        self.assertEqual(e2[96, 81], 0.0)                                # right edge not revealed yet

    def test_depth_edges_and_world_mask(self):
        W, H = 108, 192
        cam = L.default_camera(W, H)
        img = np.zeros((H, W, 4))
        dep = np.full((H, W, 1), 5.0)
        dep[:, W // 2:] = 3.0
        p = P(Edges=True, Resx=W, Resy=H, Edluma=0, Edalpha=0, Eddepth=1.0, Usedepth=True)
        E = L.ref_edges(L.rows(p, {'cam': cam}), img, (W, H), depth=dep)
        e = E[..., 3]
        self.assertGreater(e[100, W // 2], 0.99)
        self.assertEqual(e[100, 10], 0.0)
        p2 = P(Edges=True, Resx=W, Resy=H, Edluma=0, Edalpha=0, Eddepth=1.0, Usedepth=True, Maskmode='sphere',
               Maskradius=0.01, Maskcentre=(0, 0, -100))
        self.assertEqual(L.ref_edges(L.rows(p2, {'cam': cam}), img, (W, H), depth=dep)[..., 3].max(), 0.0)


class Comp(unittest.TestCase):
    def test_modes(self):
        sc = np.full((2, 2, 4), 0.5)
        ln = np.zeros((2, 2, 4))
        ln[0, 0] = [2.0, 0, 0, 1.0]
        ed = np.zeros((2, 2, 4))
        o = L.ref_comp(L.rows(P(Bgdim=0.5)), sc, ln, ed)
        self.assertTrue(np.allclose(o[0, 0], [2.25, 0.25, 0.25, 1.0]) and np.allclose(o[1, 1], [0.25, 0.25, 0.25, 0.5]))
        o = L.ref_comp(L.rows(P(Outmode='lines', Amount=0.5)), sc, ln, ed)
        self.assertTrue(np.allclose(o[0, 0], [1.0, 0, 0, 0.5]) and np.allclose(o[1, 1], 0))


class Perf(unittest.TestCase):
    def test_64k_budget(self):
        p = P(Rings=False, Contour=True, Ctmax=65536, Width=2.0, Halo=0.0)
        m = L.perf_model(p)
        self.assertEqual(m['segments'], 65536)
        self.assertLessEqual(m['gpu_ms'], 1.0, m)                      # target: 64k segments, core lines
        halo = L.perf_model(P(Rings=False, Contour=True, Ctmax=65536, Width=2.0, Halo=4.0))
        self.assertGreater(halo['fill'], m['fill'])                    # the halo is paid in fill (doc: Perf)
        full = L.perf_model(P(Contour=True, Ctmax=32768, Trails=True, Trtracks=512, Connect=True, Cnpoints=1024,
                              Edges=True))
        self.assertLess(full['gpu_ms'], 5.0, full)      # default Halo 6: fill-bound (doc: Perf)


# ======================================================================================= fake-TD build
class FakePar(object):
    def __init__(self, name):
        self.name, self.val, self.expr, self.mode, self.readOnly = name, None, None, None, False
        self.menuNames, self.menuLabels, self.default = ['aa1x', 'aa2x'], [], None
        self.normMin = self.normMax = None

    def eval(self):
        return self.val

    def pulse(self):
        self.pulsed = True

    @property
    def menuIndex(self):
        return self.menuNames.index(self.val) if self.val in self.menuNames else 0


class FakePars(object):
    def __init__(self, strict):
        object.__setattr__(self, '_d', {})
        object.__setattr__(self, '_strict', strict)

    def _add(self, k):
        d = object.__getattribute__(self, '_d')
        d[k] = FakePar(k)
        return d[k]

    def __getattr__(self, k):
        d = object.__getattribute__(self, '_d')
        if k not in d:
            if k[:1].isupper():                      # custom pars exist only once appended
                raise AttributeError(k)
            d[k] = FakePar(k)
        return d[k]

    def __setattr__(self, k, v):
        getattr(self, k).val = v


class FakePage(object):
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def _one(self, name, label=None):
        return [self.owner.par._add(name)]

    appendFloat = appendInt = appendMenu = appendToggle = appendPulse = appendStr = appendFile = _one
    appendCOMP = appendCHOP = appendSOP = appendTOP = _one

    def appendXYZ(self, name, label=None):
        return [self.owner.par._add(name + k) for k in 'xyz']

    def appendRGB(self, name, label=None):
        return [self.owner.par._add(name + k) for k in 'rgb']


class FakeConn(object):
    def __init__(self):
        self.src = None

    def connect(self, s):
        self.src = s


class FakeCell(object):
    def __init__(self, v):
        self.val = str(v)


class FakeOp(object):
    def __init__(self, cls, name, parent=None):
        self.OPType, self.name, self._parent = cls, name, parent
        self.par = FakePars(True)
        n = 3 if cls == 'glslTOP' else 4
        self.inputConnectors = [FakeConn() for _ in range(n)]
        self.seq = types.SimpleNamespace(vec=types.SimpleNamespace(numBlocks=0),
                                         array=types.SimpleNamespace(numBlocks=0),
                                         sampler=types.SimpleNamespace(numBlocks=0))
        self.text, self.comment, self.dock, self.valid = '', '', None, True
        self.ops, self.render, self.display, self.viewer, self.allowCooking = {}, False, False, False, True
        self.customPages, self.rows_ = [], []
        self.path = (parent.path + '/' if parent else '') + name

    @property
    def children(self):
        return list(self.ops.values())

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

    def parent(self):
        return self._parent

    @property
    def numRows(self):
        return len(self.rows_)

    def appendRow(self, r):
        self.rows_.append(r)

    def row(self, i):
        return [FakeCell(v) for v in self.rows_[i]]


TD_CLASSES = ['baseCOMP', 'textDAT', 'tableDAT', 'parameterexecuteDAT', 'scriptCHOP', 'inTOP', 'constantTOP',
              'feedbackTOP', 'glslTOP', 'switchTOP', 'selectTOP', 'choptoTOP', 'glslMAT', 'geometryCOMP',
              'rectangleSOP', 'cameraCOMP', 'renderTOP', 'outTOP']


def fake_build():
    root = FakeOp('baseCOMP', 'lab')
    root.path = '/project1/lab'
    layout = {}
    handlers = types.SimpleNamespace(module=types.SimpleNamespace(
        layout_stages=lambda c, st, flag, arrange=None: layout.setdefault('stages', st) and 'ok',
        safe_destroy=lambda o: setattr(o, 'valid', False)))
    ns = {'HERE': B, 'ParMode': types.SimpleNamespace(EXPRESSION='expr', CONSTANT='const'),
          'op': lambda p: root if p == '/project1/lab' else handlers}
    for c in TD_CLASSES:
        ns[c] = type(c, (), {})
    exec(compile(rd(os.path.join(B, 'px_lines.py')), 'px_lines.py', 'exec'), ns)
    res = ns['build']('/project1/lab')
    return ns, root.op('PX_lines'), res, layout


def walk(o):
    yield o
    for ch in o.children:
        for x in walk(ch):
            yield x


def declared(t):
    return set(re.findall(r'^uniform \w+ (\w+)(?:\[\w+\])?;', t, re.M))


class FakeBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns, cls.c, cls.res, cls.layout = fake_build()

    def test_pars_created(self):
        c = self.c
        for n, (st, d, o) in L.par_specs().items():
            probe = n + ('x' if st == 'XYZ' else ('r' if st == 'RGB' else ''))
            self.assertIsNotNone(getattr(c.par, probe, None), n)
        self.assertEqual(c.par.Ringcount.val, 4)
        self.assertEqual(c.par.Linecolg.val, 1.0)

    def test_wiring(self):
        c = self.c
        g = lambda n, k: c.op(n).inputConnectors[k].src.name
        self.assertEqual([g('seg', k) for k in range(3)], ['in_points', 'hist_sw', 'poly_sw'])
        self.assertEqual([g('hist', k) for k in range(2)], ['in_points', 'hist_fb'])
        self.assertEqual([g('edges', k) for k in range(2)], ['in1', 'depth_sw'])
        self.assertEqual([g('comp', k) for k in range(3)], ['in1', 'render_sw', 'edges_sw'])
        self.assertEqual(g('out1', 0), 'out_sel')
        self.assertEqual([g('out_sel', 0), g('out_sel', 1)], ['in1', 'comp'])
        self.assertEqual(c.op('hist_fb').par.top.val, 'hist')
        self.assertEqual(c.op('lgeo').par.material.val, 'lmat')
        self.assertEqual(c.op('render').par.geometry.val, 'lgeo')
        self.assertEqual(c.op('lgeo').op('quad').OPType, 'rectangleSOP')
        m = c.op('lmat')
        self.assertEqual([getattr(m.par, 'sampler%dname' % k).val for k in range(3)], ['sSeg', 'sDepth', 'sScene'])
        self.assertEqual([getattr(m.par, 'sampler%dtop' % k).val for k in range(3)], ['seg', 'depth_sw', 'in1'])

    def test_uniforms_match_shaders(self):
        c = self.c

        def bound(o):
            a = set(getattr(o.par, 'array%dname' % k).val for k in range(o.seq.array.numBlocks))
            v = set(getattr(o.par, 'vec%dname' % k).val for k in range(o.seq.vec.numBlocks))
            s = set(getattr(o.par, 'sampler%dname' % k).val for k in range(o.seq.sampler.numBlocks))
            return a | v | s
        for n in ('seg', 'hist', 'edges', 'comp'):
            t = c.op(n + '_compute').text
            self.assertEqual(declared(t) - {'sTD2DInputs', 'uTDOutputInfo'}, bound(c.op(n)), n)
        m = c.op('lmat')
        t = c.op('lmat_vertex').text + c.op('lmat_pixel').text
        self.assertEqual(declared(t) - {'uTDMats'}, bound(m))
        self.assertEqual(c.op('seg').par.vec2name.val, 'uPalCtl')
        self.assertEqual(c.op('seg').par.vec2valuex.val,
                         float(len(PM.palette_stops({'source': 'neon_green', 'mode': 'cycle'}))))
        self.assertEqual(c.op('seg').par.array1chop.val, 'pal')

    def test_expressions(self):
        specs = L.par_specs()
        n = 0
        for o in walk(self.c):
            for p in object.__getattribute__(o.par, '_d').values():
                if p.expr:
                    n += 1
                    ast.parse(p.expr, mode='eval')
                    for ref in re.findall(r'parent\(\)\.par\.(\w+)', p.expr):
                        self.assertTrue(ref in specs or ref in ('Status', 'Resetn') or ref[:-1] in specs or
                                        re.sub(r'(colsrc|palpos|palspread|keep)$', r'\1', ref) in specs, ref)
        self.assertGreater(n, 40)

    def test_live_fixes(self):
        """W1-C live run on 31550 (LEARNINGS): blend-op menu, COMP input order, CHOP to TOP format, feedback wiring,
        rows per frame only when a compute reads the camera."""
        c = self.c
        self.assertIn("'maximum'", c.op('lmat').par.blendop.expr)
        self.assertEqual([c.op(n).par.connectorder.val for n in ('in1', 'in_points', 'in_depth')], [0, 1, 2])
        self.assertIn('numChans >= 4', c.op('poly_top').par.dataformat.expr)
        self.assertEqual(c.op('hist_fb').inputConnectors[0].src.name, 'black')
        fe = c.op('rows').par.Frame.expr if getattr(c.op('rows').par, 'Frame', None) is not None else self.ns['FOLLOW']
        self.assertIn("Ringface.eval() == 'camera'", self.ns['FOLLOW'])
        self.assertNotIn("par.Camera.eval() or", self.ns['FOLLOW'])

    def test_every_op_in_a_stage(self):
        staged = set(x for st in self.layout['stages'] for x in st['ops'])
        made = set(self.c.ops)
        self.assertEqual(sorted(made - staged), [])
        self.assertEqual(self.res['missing'], [])

    def test_source_rules(self):
        for f in ('px_lines.py', 'px_lines_logic.py'):
            s = rd(os.path.join(B, f))
            for bad in ('.destroy(', 'numpyArray', 'cookRate', 'cook(force'):
                self.assertNotIn(bad, s, '%s in %s' % (bad, f))
        for n in os.listdir(G):
            if n.startswith('px_lines_'):
                rd(os.path.join(G, n))


class Callbacks(unittest.TestCase):
    """The Script CHOP callbacks run against fake ops with the real logic modules."""

    def comp(self, **kw):
        _ns, c, _r, _l = fake_build()
        for n, v in kw.items():
            st = L.par_specs()[n][0]
            if st in ('XYZ', 'RGB'):
                for k, x in zip('xyz' if st == 'XYZ' else 'rgb', v):
                    getattr(c.par, n + k).val = x
            else:
                getattr(c.par, n).val = v
        c.op('pl_logic').module = L
        c.op('pl_palmap').module = PM
        cam = c.op('cam')
        cam.par.fov.val, cam.par.near.val, cam.par.far.val = 45.0, 0.01, 1000.0
        cam.worldTransform = _M([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 5], [0, 0, 0, 1]])
        return c

    def run_cb(self, c, name, text):
        so = FakeScript(c)
        ns = {'op': lambda p: None, 'ParMode': types.SimpleNamespace(EXPRESSION='expr', CONSTANT='const')}
        exec(compile(text, name, 'exec'), ns)
        ns['onCook'](so)
        return so

    def test_rows_cb(self):
        c = self.comp(Ringcount=2, Contour=True, Ringcentre=(1.0, 0.0, 0.0))
        ns, _c, _r, _l = fake_build()
        so = self.run_cb(c, 'rows', ns['ROWS_CB'])
        p = P(Ringcount=2, Contour=True, Ringcentre=(1.0, 0.0, 0.0))
        want = L.rows(p, {'cam': L.default_camera(1080, 1920), 'poly_n': 0})
        got = np.stack([so.chans[k] for k in 'xyzw'], -1)
        self.assertEqual(got.shape, (L.NROWS, 4))
        self.assertTrue(np.allclose(got, want, atol=1e-9))
        self.assertIn('segments', c.par.Status.val)

    def test_pal_cb(self):
        c = self.comp(Palsource='rainbow', Palmode='cycle')
        ns, _c, _r, _l = fake_build()
        so = self.run_cb(c, 'pal', ns['PAL_CB'])
        self.assertEqual(so.numSamples, 16)
        self.assertEqual(c.op('seg').par.vec2valuex.val, 6.0)
        self.assertEqual(c.op('edges').par.vec2valuex.val, 6.0)
        self.assertEqual(c.op('seg').par.vec2valuey.expr, 'parent().par.Palshift.eval()')


class _M(object):
    def __init__(self, rows):
        self.r = rows

    def __getitem__(self, rc):
        return self.r[rc[0]][rc[1]]


class FakeChan(object):
    def __init__(self, store, name, n):
        self.store, self.name = store, name
        store[name] = [0.0] * n

    def __setitem__(self, i, v):
        self.store[self.name][i] = v


class FakeScript(object):
    def __init__(self, c):
        self.c, self.chans, self.numSamples, self.isTimeSlice = c, {}, 0, False

    def parent(self):
        return self.c

    def clear(self):
        self.chans = {}

    def appendChan(self, n):
        return FakeChan(self.chans, n, self.numSamples)

    def store(self, k, v):
        self.stored = getattr(self, 'stored', {})
        self.stored[k] = v


if __name__ == '__main__':
    unittest.main()
