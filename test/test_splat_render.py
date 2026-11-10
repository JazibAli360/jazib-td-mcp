"""Offline tests for builders/splat_render_logic.py (BL_splat_render). Run:
python3 -I -m unittest discover -s test -p 'test_splat_render.py'
"""
import gzip
import math
import os
import struct
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'builders'))
import splat_render_logic as L  # noqa: E402

SAMPLES = os.path.join(REPO, 'research_src', 'BL_gaussian_splats_pointclouds', 'samples')
PINATA = '/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/SmileyPinata.spz'
BANANA = '/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/banana.ply'


def write_inria_ply(path, P, dc, op, sc, rot, rest=None):
    n = len(P)
    props = ['x', 'y', 'z', 'f_dc_0', 'f_dc_1', 'f_dc_2']
    nrest = 0 if rest is None else rest.shape[1]
    props += ['f_rest_{}'.format(i) for i in range(nrest)]
    props += ['opacity', 'scale_0', 'scale_1', 'scale_2', 'rot_0', 'rot_1', 'rot_2', 'rot_3']
    head = 'ply\nformat binary_little_endian 1.0\nelement vertex {}\n'.format(n)
    head += ''.join('property float {}\n'.format(p) for p in props) + 'end_header\n'
    cols = [P, dc] + ([rest] if nrest else []) + [op[:, None], sc, rot]
    M = np.concatenate(cols, 1).astype('<f4')
    with open(path, 'wb') as f:
        f.write(head.encode('ascii'))
        f.write(M.tobytes())


def write_spz_v2(path, P, alpha, dc, logscale, quat_xyz, frac=12, shdeg=0):
    n = len(P)
    fixed = np.round(P * (1 << frac)).astype(np.int64) & 0xFFFFFF
    pos = np.stack([fixed & 255, (fixed >> 8) & 255, (fixed >> 16) & 255], 2).astype(np.uint8)
    out = struct.pack('<IIIBBBB', 0x5053474E, 2, n, shdeg, frac, 0, 0)
    out += pos.tobytes()
    out += np.round(alpha * 255).astype(np.uint8).tobytes()
    out += np.clip(np.round((dc * 0.15 + 0.5) * 255), 0, 255).astype(np.uint8).tobytes()
    out += np.clip(np.round((logscale + 10) * 16), 0, 255).astype(np.uint8).tobytes()
    out += np.clip(np.round((quat_xyz + 1) * 127.5), 0, 255).astype(np.uint8).tobytes()
    dim = {0: 0, 1: 3, 2: 8, 3: 15}[shdeg]
    out += np.full(n * dim * 3, 128, np.uint8).tobytes()
    with gzip.open(path, 'wb') as f:
        f.write(out)


class Formats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_ply_header_and_load(self):
        P = np.array([[0, 0, 0], [1, 2, 3], [-1, 0.5, 2]], np.float32)
        dc = np.array([[0, 0, 0], [1, 0, -1], [2, 2, 2]], np.float32)
        op = np.array([0.0, 2.0, -2.0], np.float32)
        sc = np.log(np.array([[0.1, 0.2, 0.3]] * 3, np.float32))
        rot = np.array([[1, 0, 0, 0], [2, 0, 0, 0], [0, 1, 0, 0]], np.float32)
        rest = np.arange(3 * 45, dtype=np.float32).reshape(3, 45)
        p = os.path.join(self.tmp, 'a.ply')
        write_inria_ply(p, P, dc, op, sc, rot, rest)
        fmt, n, props, hl = L.parse_ply_header(open(p, 'rb').read())
        self.assertEqual((fmt, n, len(props)), ('binary_little_endian', 3, 59))
        f, raw = L.load_any(p)
        self.assertEqual(f, 'ply')
        np.testing.assert_allclose(raw['P'], P)
        np.testing.assert_allclose(raw['S'], [[0.1, 0.2, 0.3]] * 3, rtol=1e-5)
        np.testing.assert_allclose(raw['A'], [0.5, L.sigmoid(2), L.sigmoid(-2)], rtol=1e-5)
        self.assertEqual(raw['sh_degree'], 3)
        # channel-major: R coeffs 0..14, G 15..29, B 30..44; we keep coeffs 0..2 of each
        np.testing.assert_allclose(raw['sh1'][0], [[0, 15, 30], [1, 16, 31], [2, 17, 32]])

    def test_point_cloud_ply_ascii(self):
        p = os.path.join(self.tmp, 'pc.ply')
        with open(p, 'w') as f:
            f.write('ply\nformat ascii 1.0\nelement vertex 2\nproperty float x\nproperty float y\nproperty float z\n'
                    'property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n1 2 3 255 0 128\n'
                    '4 5 6 0 255 0\n')
        f, raw = L.load_any(p)
        self.assertEqual(raw['kind'], 'points')
        np.testing.assert_allclose(raw['P'], [[1, 2, 3], [4, 5, 6]])
        np.testing.assert_allclose(raw['rgb'][0], [1, 0, 128 / 255], rtol=1e-5)
        prep = L.prepare(raw, f, coordfix='none', point_scale=0.05)
        np.testing.assert_allclose(prep['S'], 0.05)
        np.testing.assert_allclose(prep['Q'][:, 0], 1)

    def test_splat_format(self):
        n = 4
        rec = np.zeros((n, 32), np.uint8)
        f = np.array([[1, 2, 3, 0.1, 0.2, 0.3]] * n, '<f4')
        rec[:, :24] = f.view(np.uint8).reshape(n, 24)
        rec[:, 24:28] = [255, 128, 0, 204]
        rec[:, 28:32] = [255, 128, 128, 128]
        p = os.path.join(self.tmp, 'a.splat')
        rec.tofile(p)
        _, raw = L.load_any(p)
        np.testing.assert_allclose(raw['P'][0], [1, 2, 3])
        np.testing.assert_allclose(raw['S'][0], [0.1, 0.2, 0.3], rtol=1e-6)
        np.testing.assert_allclose(raw['A'], 0.8)
        np.testing.assert_allclose(raw['Q'][0], [127 / 128, 0, 0, 0])

    def test_spz_v2_roundtrip(self):
        rng = np.random.default_rng(1)
        n = 50
        P = rng.uniform(-100, 100, (n, 3)).astype(np.float32)
        alpha = rng.uniform(0, 1, n)
        dc = rng.uniform(-2, 2, (n, 3))
        ls = rng.uniform(-8, 1, (n, 3))
        q = rng.normal(size=(n, 4))
        q /= np.linalg.norm(q, axis=1, keepdims=True)
        q[q[:, 0] < 0] *= -1                       # w >= 0 as spz v2 stores it
        p = os.path.join(self.tmp, 'a.spz')
        write_spz_v2(p, P, alpha, dc, ls, q[:, 1:], shdeg=1)
        _, raw = L.load_any(p)
        np.testing.assert_allclose(raw['P'], P, atol=1.0 / 4096 + 1e-6)
        np.testing.assert_allclose(raw['A'], alpha, atol=0.5 / 255 + 1e-6)
        np.testing.assert_allclose(raw['dc'], dc, atol=0.5 / 255 / 0.15 + 1e-5)
        np.testing.assert_allclose(np.log(raw['S']), ls, atol=1 / 32 + 1e-5)
        dots = np.abs((L.normalize_quats(raw['Q']) * q).sum(1))
        self.assertGreater(dots.min(), 0.98)
        self.assertEqual(raw['tail_bytes'], 0)
        np.testing.assert_allclose(raw['sh1'], 0)

    def test_spz_v3_quat(self):
        # pack q = (w,x,y,z) = (0.8, 0.6*... ) by hand: largest = w (index 3 in xyzw)
        x, y, z = 0.1, -0.3, 0.2
        w = math.sqrt(1 - x * x - y * y - z * z)
        comp = 3 << 30
        bits = 0
        for i, v in enumerate((z, y, x)):              # reference packing: last component in the low bits
            mag = int(round(abs(v) / math.sqrt(0.5) * 511))
            bits |= (mag | ((1 if v < 0 else 0) << 9)) << (10 * i)
        comp |= bits
        r = np.array([[comp & 255, (comp >> 8) & 255, (comp >> 16) & 255, (comp >> 24) & 255]], np.uint8)
        q = L._spz_quat_v3(r)[0]
        np.testing.assert_allclose(q, [w, x, y, z], atol=2e-3)

    @unittest.skipUnless(os.path.exists(PINATA), 'TD sample not installed')
    def test_real_pinata_spz(self):
        h = L.spz_header(gzip.open(PINATA).read(16))
        self.assertEqual((h['version'], h['count'], h['sh_degree']), (2, 228287, 3))
        _, raw = L.load_any(PINATA)
        self.assertEqual(raw['tail_bytes'], 0)
        self.assertEqual(raw['P'].shape, (228287, 3))

    @unittest.skipUnless(os.path.exists(os.path.join(SAMPLES, 'nike.splat')), 'research sample missing')
    def test_real_nike_splat(self):
        _, raw = L.load_any(os.path.join(SAMPLES, 'nike.splat'))
        self.assertEqual(raw['P'].shape[0], 270491)

    @unittest.skipUnless(os.path.exists(BANANA), 'TD sample not installed')
    def test_real_banana_ply(self):
        _, raw = L.load_any(BANANA)
        self.assertEqual((raw['kind'], raw['P'].shape[0]), ('points', 49106))


class Prep(unittest.TestCase):
    def raw(self, n=1000, seed=0):
        rng = np.random.default_rng(seed)
        return {'P': rng.normal(size=(n, 3)).astype(np.float32), 'S': np.full((n, 3), 0.1, np.float32),
                'Q': rng.normal(size=(n, 4)).astype(np.float32), 'dc': np.zeros((n, 3), np.float32),
                'A': rng.uniform(0, 1, n).astype(np.float32), 'sh1': rng.normal(size=(n, 3, 3)).astype(np.float32),
                'kind': 'gaussian'}

    def test_coordfix_rotation_conjugation(self):
        rng = np.random.default_rng(3)
        q = rng.normal(size=(20, 4)).astype(np.float32)
        q = L.normalize_quats(q)
        for sign in [(1, -1, -1), (1, -1, 1), (1, 1, -1)]:
            F = np.diag(sign).astype(np.float64)
            _, q2, _ = L.apply_coordfix(np.zeros((20, 3), np.float32), q, None, sign)
            for a, b in zip(q, q2):
                np.testing.assert_allclose(L.quat_to_mat3(b), F @ L.quat_to_mat3(a) @ F, atol=1e-5)

    def test_coordfix_sh1(self):
        dc = np.array([0.2, 0.3, 0.4])
        sh = np.random.default_rng(5).normal(size=(3, 3))
        d = np.array([0.3, -0.5, 0.8])
        for sign in [(1, -1, -1), (1, -1, 1)]:
            _, _, sh2 = L.apply_coordfix(np.zeros((1, 3), np.float32), np.array([[1, 0, 0, 0]], np.float32),
                                         sh[None].astype(np.float32), sign)
            F = np.array(sign, float)
            np.testing.assert_allclose(L.sh_eval_deg1(dc, sh2[0], F * d), L.sh_eval_deg1(dc, sh, d), atol=1e-5)

    def test_auto_coordfix(self):
        self.assertEqual(L.coordfix_matrix('auto', 'spz'), (1, 1, 1))
        self.assertEqual(L.coordfix_matrix('auto', 'ply'), (1, -1, -1))

    def test_prepare_pipeline(self):
        raw = self.raw()
        p = L.prepare(raw, 'spz', coordfix='none', opacitycull=0.5)
        self.assertTrue((p['C'][:, 3] >= 0.5).all())
        np.testing.assert_allclose(p['C'][:, :3], 0.5)
        np.testing.assert_allclose(np.linalg.norm(p['Q'], axis=1), 1, atol=1e-5)
        p2 = L.prepare(raw, 'spz', coordfix='none', maxsplats=100)
        self.assertEqual(p2['count'], 100)
        p3 = L.prepare(raw, 'spz', coordfix='none', shdegree=0)
        self.assertIsNone(p3['SH1'])
        p4 = L.prepare(raw, 'spz', coordfix='none', crop_radius=1.0)
        self.assertTrue(((p4['P'] ** 2).sum(1) <= 1.0001).all())
        self.assertEqual(p4['file_count'], 1000)

    def test_thin_crop_budget(self):
        self.assertEqual(L.thin_indices(10, 3).tolist(), [0, 3, 6, 9])
        self.assertLess(L.thin_indices(10000, 1, 0.5, 1).size, 5500)
        P = np.array([[0, 0, 0], [2, 0, 0], [0, 0.4, 0]], np.float32)
        self.assertEqual(L.crop_mask(P, size=(1, 1, 1)).tolist(), [True, False, True])
        A = np.array([1.0, 0.1, 1.0, 0.5], np.float32)
        S = np.array([[1, 1, 1], [9, 9, 9], [0.1, 0.1, 0.1], [2, 2, 2]], np.float32)
        self.assertEqual(L.importance_budget(A, S, 2).tolist(), [1, 3])

    def test_channel_matrix(self):
        p = L.prepare(self.raw(10), 'spz', coordfix='none')
        names, M = L.channel_matrix(p, order=np.arange(10)[::-1])
        self.assertEqual(M.shape, (24, 10))
        np.testing.assert_allclose(M[6], np.arange(10)[::-1])
        self.assertEqual(names[:3], ['tx', 'ty', 'tz'])
        np.testing.assert_allclose(M[0], p['P'][::-1, 0])
        np.testing.assert_allclose(M[15:18, 0], p['SH1'][-1, :, 0])    # shr0..2 = coeffs of red


class Maths(unittest.TestCase):
    def test_quat(self):
        np.testing.assert_allclose(L.quat_to_mat3([1, 0, 0, 0]), np.eye(3), atol=1e-12)
        R = L.quat_to_mat3([math.cos(math.pi / 4), 0, 0, math.sin(math.pi / 4)])    # 90 deg about z
        np.testing.assert_allclose(R @ [1, 0, 0], [0, 1, 0], atol=1e-12)
        Rs = L.quat_to_mat3(np.random.default_rng(0).normal(size=(5, 4)))
        for R in Rs:
            np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-12)
            self.assertAlmostEqual(np.linalg.det(R), 1.0)

    def test_orbit_camera(self):
        c = L.orbit_camera(30, 20, 5, (1, 2, 3))
        np.testing.assert_allclose(np.linalg.norm(c['pos'] - [1, 2, 3]), 5)
        # target is straight ahead (camera space x = y = 0, z = -5)
        t = c['view'] @ [1, 2, 3, 1]
        np.testing.assert_allclose(t[:3], [0, 0, -5], atol=1e-9)
        np.testing.assert_allclose(-c['world'][:3, 2], c['forward'], atol=1e-12)

    def test_project_cov_vs_monte_carlo(self):
        rng = np.random.default_rng(7)
        cam = L.orbit_camera(15, 10, 20)
        fx = L.focal_px(512, 40)
        sig = L.cov3d([0.3, 0.1, 0.05], [0.9, 0.2, 0.3, 0.1])
        mu = np.array([0.5, -0.2, 0.3])
        mean, cov, _ = L.project_cov2d(mu, sig, cam['view'], fx, fx, 512, 512, lowpass=0.0)
        X = rng.multivariate_normal(mu, sig, 200000)
        pc = (cam['view'][:3, :3] @ X.T).T + cam['view'][:3, 3]
        u = 256 + fx * pc[:, 0] / -pc[:, 2]
        v = 256 + fx * pc[:, 1] / -pc[:, 2]
        np.testing.assert_allclose([u.mean(), v.mean()], mean, atol=0.05)
        np.testing.assert_allclose(np.cov(np.stack([u, v])), cov, rtol=0.03, atol=0.02)

    def test_conic_eigen_extent(self):
        cov = np.array([[4.0, 1.0], [1.0, 2.0]])
        con = L.conic_from_cov(cov)
        np.testing.assert_allclose(np.array([[con[0], con[1]], [con[1], con[2]]]) @ cov, np.eye(2), atol=1e-12)
        l1, l2, v = L.eigen2(cov)
        np.testing.assert_allclose(cov @ v, l1 * np.array(v), atol=1e-9)
        self.assertAlmostEqual(l1 + l2, 6)
        self.assertEqual(L.quad_sigma_extent(1.0, 0.0), 3.0)
        k = L.quad_sigma_extent(0.5, 0.1)
        self.assertAlmostEqual(0.5 * math.exp(-k * k / 2), 0.1)
        self.assertEqual(L.quad_sigma_extent(0.01, 0.015), 0.0)

    def test_sh_deg1(self):
        dc = [0.5, 0.5, 0.5]
        sh = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], float)  # c1 -> r, c2 -> g, c3 -> b
        c = L.sh_eval_deg1(dc, sh, [0, -1, 0])                   # -y = 1
        np.testing.assert_allclose(c, [0.5 + L.SH_C1, 0.5, 0.5])
        c = L.sh_eval_deg1(dc, sh, [0, 0, 2])
        np.testing.assert_allclose(c, [0.5, 0.5 + L.SH_C1, 0.5])
        c = L.sh_eval_deg1(dc, sh, [1, 0, 0])
        np.testing.assert_allclose(c, [0.5, 0.5, 0.5 - L.SH_C1])


class Sort(unittest.TestCase):
    def test_radix_back_to_front(self):
        rng = np.random.default_rng(2)
        P = rng.normal(size=(20000, 3)).astype(np.float32)
        cam = L.orbit_camera(40, 25, 8)
        order = L.back_to_front(P, cam['pos'], cam['forward'])
        self.assertEqual(sorted(order.tolist()), list(range(20000)))
        d = L.view_depth(P, cam['pos'], cam['forward'])[order]
        span = d.max() - d.min()
        self.assertLessEqual(np.diff(d).max(), span / 65535 * 1.01)   # increases only inside one bin
        exact = np.argsort(-d, kind='stable')
        self.assertLess(np.abs(d - d[exact]).max(), span / 65535 * 1.01)

    def test_stable_ties(self):
        keys = np.array([5, 1, 5, 1, 0], np.uint16)
        self.assertEqual(L.radix_order(keys).tolist(), [4, 1, 3, 0, 2])

    def test_inversion_fraction(self):
        self.assertEqual(L.inversion_fraction([5, 4, 3]), 0.0)
        self.assertEqual(L.inversion_fraction([3, 4, 5]), 1.0)

    def test_need_sort(self):
        f = (0, 0, -1)
        args = dict(every_n=0, move_deg=1.0, scene_radius=1.0)
        self.assertTrue(L.need_sort('sortpop', 1, 0, fwd=f, last_fwd=None, pos=(0, 0, 0), last_pos=(0, 0, 0), **args))
        self.assertFalse(L.need_sort('sortpop', 1, 0, fwd=f, last_fwd=f, pos=(0, 0, 0), last_pos=(0, 0, 0), **args))
        f2 = (math.sin(math.radians(2)), 0, -math.cos(math.radians(2)))
        self.assertTrue(L.need_sort('cpu', 1, 0, fwd=f2, last_fwd=f, pos=(0, 0, 0), last_pos=(0, 0, 0), **args))
        self.assertFalse(L.need_sort('frozen', 1, 0, fwd=f2, last_fwd=f, pos=(0, 0, 0), last_pos=(0, 0, 0), **args))
        self.assertTrue(L.need_sort('frozen', 1, 0, fwd=f2, last_fwd=f, pos=(0, 0, 0), last_pos=(0, 0, 0),
                                    pulse=True, **args))
        self.assertTrue(L.need_sort('cpu', 1, 0, fwd=f, last_fwd=f, pos=(0.1, 0, 0), last_pos=(0, 0, 0), **args))
        a2 = dict(args, every_n=5)
        self.assertTrue(L.need_sort('cpu', 5, 0, fwd=f, last_fwd=f, pos=(0, 0, 0), last_pos=(0, 0, 0), **a2))


class Motion(unittest.TestCase):
    def test_orbit_rate(self):
        self.assertEqual(L.orbit_rate_deg_s(10, 'none', 120, 16), 10)
        self.assertAlmostEqual(L.orbit_rate_deg_s(10, 'bpm', 120, 16), 45.0)
        self.assertAlmostEqual(L.orbit_rate_deg_s(10, 'audio', 120, 16, 0.5), 5.0)

    def test_beat_and_audio(self):
        self.assertAlmostEqual(L.beat_env(0.0, 120), 1.0)
        self.assertAlmostEqual(L.beat_env(0.25, 120), math.exp(-3))
        m = L.audio_mods([('low', 'scale', 0.5), ('high', 'noise', 2), ('x', 'bogus', 1)], {'low': 1.0, 'high': 0.1})
        self.assertAlmostEqual(m['scale'], 0.5)
        self.assertAlmostEqual(m['noise'], 0.2)
        u = L.uniform_mods(1.0, 1.0, 0.0, 0.0, 0.5, 1.0, m)
        self.assertAlmostEqual(u[0], 1.5 * 1.5)


class Raster(unittest.TestCase):
    def single(self, q=(1, 0, 0, 0), s=(1, 1, 1)):
        return {'P': np.zeros((1, 3), np.float32), 'S': np.array([s], np.float32), 'Q': np.array([q], np.float32),
                'C': np.array([[1, 1, 1, 0.8]], np.float32), 'SH1': None, 'count': 1}

    def test_r3_single_splat(self):
        """R3 reference: splat at origin, scale 1, opacity 0.8, camera at z = 5."""
        w = h = 257
        cam = L.orbit_camera(0, 0, 5)
        fx = L.focal_px(h, 90)
        img = L.cpu_reference_raster(self.single(), cam['view'], fx, fx, w, h, alpha_thr=0.0, lowpass=0.0)
        a = img[..., 3]
        self.assertAlmostEqual(a[128, 128], 0.8, delta=1 / 255)
        sig_px = fx / 5.0                                  # 25.7 px; pixel centres sit at +0.5
        x1 = 128 + int(round(sig_px))
        expect = 0.8 * math.exp(-0.5 * ((x1 + 0.5 - 128.5) ** 2) / sig_px ** 2)
        self.assertAlmostEqual(a[128, x1], expect, delta=2 / 255)
        self.assertEqual(a[128, 128 + int(math.ceil(3 * sig_px)) + 2], 0.0)

    def test_r3_rotation_swaps_axes(self):
        w = h = 129
        cam = L.orbit_camera(0, 0, 5)
        fx = L.focal_px(h, 40)
        a1 = L.cpu_reference_raster(self.single(s=(1, 0.3, 0.3)), cam['view'], fx, fx, w, h, alpha_thr=0.0)[..., 3]
        q90 = (math.cos(math.pi / 4), 0, 0, math.sin(math.pi / 4))
        a2 = L.cpu_reference_raster(self.single(q=q90, s=(1, 0.3, 0.3)), cam['view'], fx, fx, w, h,
                                    alpha_thr=0.0)[..., 3]
        self.assertGreater((a1[64] > 0.1).sum(), 2 * (a1[:, 64] > 0.1).sum())
        self.assertGreater((a2[:, 64] > 0.1).sum(), 2 * (a2[64] > 0.1).sum())

    def test_psnr(self):
        self.assertEqual(L.psnr(np.zeros(4), np.zeros(4)), float('inf'))
        self.assertAlmostEqual(L.psnr(np.zeros(4), np.full(4, 0.1)), 20.0)


if __name__ == '__main__':
    unittest.main()


class Pointer(unittest.TestCase):
    """27 Oct (splat lane): BL_splat_render points at PX_pointfx for the splat effect modules (MAIN_AUDIT D4);
    29 Oct (drop-in): no hard path, Splatfx is an optional COMP par (empty = off)."""
    def test_comment_names_px(self):
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders', 'splat_render.py')).read()
        self.assertIn("SPLAT_FX_POINTER = ('Splat effect modules", src)
        self.assertNotIn('/project1/lab/PX_pointfx', src)
        self.assertIn('+ SPLAT_FX_POINTER)', src)
        self.assertIn("appendCOMP('Splatfx'", src)
        self.assertIn('splatfx_par(c)                               # optional PX pointer', src)
        px = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'builders', 'px.py')).read()
        self.assertNotIn("p.val = '/project1/lab/PX_pointfx", px)


class Renderscale(unittest.TestCase):
    """Perf wave 27 Oct: render size per Renderscale, post skipped only when it would copy."""
    def test_sizes(self):
        self.assertEqual(L.render_size(1080, 1920, 'full'), (1080, 1920))
        self.assertEqual(L.render_size(1080, 1920, 's75'), (810, 1440))
        self.assertEqual(L.render_size(1080, 1920, 's50'), (540, 960))
        self.assertEqual(L.render_size(1, 1, 's50'), (1, 1))
        self.assertEqual(L.render_size(1080, 1920, 'bogus'), (1080, 1920))
        self.assertEqual([m[0] for m in L.RENDERSCALE][0], 'full')

    def test_post_identity(self):
        self.assertTrue(L.post_identity('sortpop', False, 0.0, True, True, 'full'))
        self.assertFalse(L.post_identity('sortpop', False, 0.0, True, True, 's75'))   # upscale needed
        self.assertFalse(L.post_identity('sortfree', False, 0.0, True, True, 'full'))
        self.assertFalse(L.post_identity('sortpop', True, 0.0, True, True, 'full'))
        self.assertFalse(L.post_identity('sortpop', False, 0.5, True, True, 'full'))
        self.assertFalse(L.post_identity('sortpop', False, 0.0, False, True, 'full'))
        self.assertFalse(L.post_identity('sortpop', False, 0.0, True, False, 'full'))

    def test_post_glsl_compiles(self):
        import shutil
        if shutil.which('glslc') is None:
            self.skipTest('no glslc')
        sys.path.insert(0, HERE)
        import fx_stylise_testkit as K
        src = open(os.path.join(REPO, 'builders', 'splat_render.py')).read()
        tq = "'" * 3
        start = src.index('POST_GLSL = ' + tq)
        ns = {}
        exec(src[start:src.index(tq, start + 15) + 3], ns)
        pre = ('struct TDOutInfo { vec4 res; }; uniform TDOutInfo uTDOutputInfo;\n'
               'vec4 TDOutputSwizzle(vec4 c) { return c; }\n')  # TD's compute globals the kit stub lacks
        ok, err = K.glslc_n(pre + ns['POST_GLSL'], 2)
        self.assertTrue(ok, err)
