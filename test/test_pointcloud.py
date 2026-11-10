"""Offline tests for BL_cloud_morph (builders/pointcloud_logic.py + builder/shader consistency; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pointcloud.py'"""
import gzip
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
B = os.path.join(REPO, 'builders')
sys.path.insert(0, B)
import pointcloud_logic as L  # noqa: E402
import pointcloud as PB       # noqa: E402  (plain module: td names are only used inside build())

TD_SAMPLES = '/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/'
BL = os.path.join(REPO, 'research_src', 'BL_gaussian_splats_pointclouds', 'samples')


class Tmp(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='pc_test_')

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def path(self, name, data, mode='wb'):
        p = os.path.join(self.d, name)
        with open(p, mode) as f:
            f.write(data)
        return p


def ply_binary(rows, props, endian='<', extra_before=None):
    head = ['ply', 'format {} 1.0'.format('binary_little_endian' if endian == '<' else 'binary_big_endian')]
    if extra_before:
        head += ['element meta {}'.format(len(extra_before)), 'property float m']
    head += ['element vertex {}'.format(len(rows))] + ['property {} {}'.format(t, n) for n, t in props] + \
        ['element face 0', 'property list uchar int vertex_indices', 'end_header']
    dt = np.dtype([(n, endian + L.PLY_TYPES[t]) for n, t in props])
    body = b''
    if extra_before:
        body += np.array(extra_before, endian + 'f4').tobytes()
    body += np.array([tuple(r) for r in rows], dtype=dt).tobytes()
    return ('\n'.join(head) + '\n').encode('ascii') + body


class Formats(Tmp):
    def test_ply_ascii_uchar_colour_and_faces(self):
        txt = ('ply\nformat ascii 1.0\ncomment x\nelement vertex 3\nproperty float x\nproperty float y\n'
               'property float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\n'
               'element face 1\nproperty list uchar int vertex_indices\nend_header\n'
               '0 0 0 255 0 0 \n1 2 3 0 255 0\n-1 -2 -3 0 0 51\n3 0 1 2\n')
        c = L.load_cloud(self.path('a.ply', txt.encode()))
        self.assertEqual(c['n'], 3)
        np.testing.assert_allclose(c['P'][1], [1, 2, 3])
        np.testing.assert_allclose(c['C'][0], [1, 0, 0, 1])
        np.testing.assert_allclose(c['C'][2], [0, 0, 0.2, 1], atol=1e-6)

    def test_ply_ascii_vertex_not_first(self):
        txt = ('ply\nformat ascii 1.0\nelement meta 2\nproperty float m\nelement vertex 2\nproperty float x\n'
               'property float y\nproperty float z\nend_header\n7\n8\n1 1 1\n2 2 2\n')
        c = L.load_cloud(self.path('b.ply', txt.encode()))
        np.testing.assert_allclose(c['P'], [[1, 1, 1], [2, 2, 2]])
        self.assertIsNone(c['C'])

    def test_ply_binary_le_be_and_sh0(self):
        props = [('x', 'float'), ('y', 'float'), ('z', 'float'), ('f_dc_0', 'float'), ('f_dc_1', 'float'),
                 ('f_dc_2', 'float'), ('opacity', 'float')]
        rows = [(1, 2, 3, 0, 1, -1, 0), (-1, -2, -3, 2, 0, 0, 10)]
        for e in ('<', '>'):
            c = L.load_cloud(self.path('s{}.ply'.format(e == '<'), ply_binary(rows, props, e, extra_before=[5, 6])))
            np.testing.assert_allclose(c['P'], [[1, 2, 3], [-1, -2, -3]])
            np.testing.assert_allclose(c['C'][0, :3], [0.5, 0.5 + L.SH_C0, 0.5 - L.SH_C0], atol=1e-6)
            self.assertAlmostEqual(float(c['C'][0, 3]), 0.5, places=6)
            self.assertAlmostEqual(float(c['C'][1, 3]), 1 / (1 + math.exp(-10)), places=6)

    def test_ply_errors(self):
        with self.assertRaises(ValueError):
            L.load_cloud(self.path('bad.ply', b'nope'))
        props = [('x', 'float'), ('y', 'float')]
        with self.assertRaises(ValueError):
            L.load_cloud(self.path('noz.ply', ply_binary([(1, 2)], props)))

    def test_text_header_names_no_colour(self):
        p = self.path('s.xyz', 'X Y Z U V Nx Ny Nz\n0 0.09 -0.99 0.5 0.8 0 0 -1\n1 2 3 0.1 0.2 0 0 1\n', 'w')
        c = L.load_cloud(p)
        self.assertEqual(c['n'], 2)
        self.assertIsNone(c['C'])                                  # U V Nx are not colours
        np.testing.assert_allclose(c['P'][1], [1, 2, 3])

    def test_text_no_header_rgb_csv_pts(self):
        c = L.load_cloud(self.path('a.txt', '1 2 3 255 0 0\n4 5 6 0 255 0\n', 'w'))
        np.testing.assert_allclose(c['C'][0], [1, 0, 0, 1])
        c = L.load_cloud(self.path('a.csv', 'x,y,z,r,g,b\n1,2,3,0.5,0.25,0\n', 'w'))
        np.testing.assert_allclose(c['C'][0], [0.5, 0.25, 0, 1])
        c = L.load_cloud(self.path('a.pts', '2\n1 2 3\n4 5 6\n', 'w'))
        self.assertEqual(c['n'], 2)

    def test_obj(self):
        c = L.load_cloud(self.path('a.obj', 'v 1 2 3 1 0 0\nv 4 5 6 0 1 0\nf 1 2 2\n', 'w'))
        np.testing.assert_allclose(c['P'], [[1, 2, 3], [4, 5, 6]])
        np.testing.assert_allclose(c['C'][1], [0, 1, 0, 1])

    def test_splat_centres(self):
        rec = b''
        for i in range(3):
            rec += struct.pack('<6f', i, -i, 2 * i, 0.1, 0.1, 0.1) + bytes([255, 128, 0, 64]) + bytes([255, 128, 128, 128])
        c = L.load_cloud(self.path('a.splat', rec))
        self.assertEqual(c['n'], 3)
        np.testing.assert_allclose(c['P'][2], [2, -2, 4])
        np.testing.assert_allclose(c['C'][0], [1, 128 / 255, 0, 64 / 255], atol=1e-6)
        with self.assertRaises(ValueError):
            L.load_cloud(self.path('b.splat', rec[:-1]))

    def spz(self, pos, alpha, rgb, version=2, frac=12):
        n = len(pos)
        out = struct.pack('<IIIBBBB', 0x5053474e, version, n, 0, frac, 0, 0)
        pb = b''
        for p in pos:
            for v in p:
                q = int(round(v * (1 << frac))) & 0xFFFFFF
                pb += bytes([q & 255, (q >> 8) & 255, (q >> 16) & 255])
        rot = 3 if version == 2 else 4
        out += pb + bytes(alpha) + bytes([x for c in rgb for x in c]) + bytes(n * 3) + bytes(n * rot)
        return gzip.compress(out)

    def test_spz_v2_v3_centres(self):
        pos = [(0.5, -1.25, 3.0), (-100.0, 0.0, 0.000244140625)]
        for v in (2, 3):
            c = L.load_cloud(self.path('a{}.spz'.format(v), self.spz(pos, [255, 0], [(255, 128, 0), (0, 0, 0)], v)))
            np.testing.assert_allclose(c['P'], pos, atol=1e-6)
            self.assertAlmostEqual(float(c['C'][0, 3]), 1.0)
            fdc = (1.0 - 0.5) / 0.15
            self.assertAlmostEqual(float(c['C'][0, 0]), 0.5 + L.SH_C0 * fdc, places=5)
            self.assertEqual(float(c['C'][1, 0]), max(0.0, 0.5 + L.SH_C0 * (-0.5 / 0.15)))

    def test_spz4_and_unknown_rejected(self):
        with self.assertRaises(ValueError):
            L.load_cloud(self.path('n.spz', b'NGSP' + bytes(40)))
        with self.assertRaises(ValueError):
            L.load_cloud(self.path('a.png', b'x'))
        with self.assertRaises(ValueError):
            L.detect_kind('a.foo')


@unittest.skipUnless(os.path.isdir(TD_SAMPLES), 'TD app samples not on this machine')
class RealSamplesTD(unittest.TestCase):
    def test_banana_ply(self):
        c = L.load_cloud(TD_SAMPLES + 'banana.ply')
        self.assertEqual(c['n'], 49106)
        self.assertEqual(c['C'].shape, (49106, 4))
        self.assertTrue(0.0 <= float(c['C'].min()) and float(c['C'].max()) <= 1.0)

    def test_sphere_xyz_and_pinata(self):
        self.assertEqual(L.load_cloud(TD_SAMPLES + 'sphere.xyz')['n'], 812)
        c = L.load_cloud(TD_SAMPLES + 'SmileyPinata.spz')
        self.assertEqual(c['n'], 228287)
        self.assertLess(float(np.abs(c['P']).max()), 1.0)


@unittest.skipUnless(os.path.isdir(BL), 'BL research samples not downloaded')
class RealSamplesBL(unittest.TestCase):
    def test_nike_and_lizard(self):
        self.assertEqual(L.load_cloud(os.path.join(BL, 'nike.splat'))['n'], 270491)
        c = L.load_cloud(os.path.join(BL, 'hornedlizard.spz'))
        self.assertEqual(c['n'], 786233)
        self.assertGreater(float(np.abs(c['P']).max()), 150)        # floaters at +-200 ...
        keep = L.outlier_keep(c['P'], 90.0)                         # ~7 % of it is a +-200 shell
        self.assertLess(float(np.abs(c['P'][keep]).max()), 20)      # ... gone at the 90th percentile


class Depth(Tmp):
    def test_depth_to_z_endpoints(self):
        z = L.depth_to_z(np.array([0.0, 1.0, 0.5]), 'inverse', 1.0, 10.0)
        np.testing.assert_allclose(z[:2], [10.0, 1.0])
        self.assertAlmostEqual(float(z[2]), 10.0 / 5.5)
        np.testing.assert_allclose(L.depth_to_z(np.array([0.0, 1.0]), 'depth', 1.0, 10.0), [1.0, 10.0])

    def test_unproject_plane_round_trip(self):
        h, w = 9, 16
        d = np.full((h, w), 0.25, np.float32)
        out = L.unproject_depth(d, 60.0, 2.0, 6.0, lo=0.0, hi=1.0, kind='depth')
        np.testing.assert_allclose(out['P'][:, 2], -3.0, atol=1e-5)          # z = 2 + 0.25 * 4
        t = math.tan(math.radians(30.0))
        self.assertAlmostEqual(float(out['P'][:, 1].max()), (1 - 0.5 / h - 0.5) * 2 * t * 3.0, places=5)
        self.assertAlmostEqual(float(out['P'][:, 0].max()), (1 - 0.5 / w - 0.5) * 2 * t * (w / h) * 3.0, places=5)
        top_row = out['UV'][:w, 1]
        np.testing.assert_allclose(top_row, 1 - 0.5 / h)                   # array row 0 = top = v near 1

    def test_unproject_sphere_relative_depth(self):
        # synthetic inverse depth of a sphere in front of a wall: nearer pixels have larger values -> smaller z
        h = w = 32
        yy, xx = np.mgrid[0:h, 0:w]
        r2 = ((xx - 15.5) ** 2 + (yy - 15.5) ** 2) / 100.0
        d = np.where(r2 < 1, 0.5 + 0.5 * np.sqrt(np.clip(1 - r2, 0, 1)), 0.1).astype(np.float32)
        out = L.unproject_depth(d, 50.0, 1.0, 8.0, kind='inverse', step=1)
        z = -out['P'][:, 2].reshape(h, w)
        self.assertLess(float(z[16, 16]), float(z[0, 0]))
        self.assertEqual(out['n'], h * w)

    def test_file_readers(self):
        a = np.arange(12, dtype=np.float32).reshape(3, 4)
        p = os.path.join(self.d, 'd.npy')
        np.save(p, a)
        np.testing.assert_allclose(L.read_depth_file(p), a)
        pfm = b'Pf\n4 3\n-1.0\n' + a[::-1].astype('<f4').tobytes()
        np.testing.assert_allclose(L.read_depth_file(self.path('d.pfm', pfm)), a)
        g = np.array([[0, 255], [128, 64]], np.uint8)
        pgm = b'P5\n# c\n2 2\n255\n' + g.tobytes()
        np.testing.assert_allclose(L.read_depth_file(self.path('d.pgm', pgm)), g / 255.0)

    def test_grid_uv_and_proxy(self):
        for n, asp in ((1, 1.0), (100000, 16 / 9.0), (777, 0.5625)):
            uv, (gw, gh) = L.grid_uv(n, asp)
            self.assertEqual(uv.shape, (n, 2))
            self.assertTrue((uv > 0).all() and (uv < 1).all())
            self.assertGreaterEqual(gw * gh, n)
        pr = L.depthtex_proxy(1000, 16 / 9.0, 60.0, 1.0, 10.0)
        np.testing.assert_allclose(pr['P'][:, 2], -10.0 / 5.5, atol=1e-5)


class Prepare(unittest.TestCase):
    def test_generators(self):
        for k in L.names(L.GENERATORS):
            g = L.generate(k, 5000, 3)
            self.assertEqual(g['P'].shape, (5000, 3), k)
            self.assertLess(float(np.abs(g['P']).max()), 3.0, k)
            self.assertTrue(np.isfinite(g['P']).all(), k)
        r = np.linalg.norm(L.generate('sphere', 2000)['P'], axis=1)
        np.testing.assert_allclose(r, 1.0, atol=1e-6)
        with self.assertRaises(ValueError):
            L.generate('nope', 3)

    def test_up_axis(self):
        P = np.array([[0, 0, 1], [0, 1, 0]], np.float32)
        np.testing.assert_allclose(L.up_axis_fix(P, 'z')[0], [0, 1, 0], atol=1e-7)
        np.testing.assert_allclose(L.up_axis_fix(P, '-y')[1], [0, -1, 0], atol=1e-7)
        np.testing.assert_allclose(L.up_axis_fix(P, '-z')[0], [0, -1, 0], atol=1e-7)
        self.assertIs(L.up_axis_fix(P, 'y'), P)

    def test_fit_and_outlier(self):
        P = np.random.default_rng(0).normal(0, 1, (1000, 3)).astype(np.float32) + 5
        Q, c, r = L.fit_unit(P)
        self.assertAlmostEqual(float(np.linalg.norm(Q, axis=1).max()), 1.0, places=5)
        np.testing.assert_allclose((Q.min(0) + Q.max(0)) / 2, 0, atol=1e-5)
        P2 = np.vstack([P, [[500, 500, 500]]]).astype(np.float32)
        self.assertFalse(L.outlier_keep(P2, 99.0)[-1])
        self.assertTrue(L.outlier_keep(P2, 100.0).all())

    def test_resample(self):
        self.assertEqual(list(L.resample_indices(10, 5)), [0, 2, 4, 6, 8])
        up = L.resample_indices(7, 20)
        self.assertEqual(len(up), 20)
        self.assertEqual(set(up), set(range(7)))
        r = L.resample_indices(100, 30, 1, 'random')
        self.assertEqual(len(set(r)), 30)
        self.assertEqual(len(L.resample_indices(5, 12, 1, 'random')), 12)
        with self.assertRaises(ValueError):
            L.resample_indices(0, 3)


class Matching(unittest.TestCase):
    def test_morton_codes(self):
        P = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1]], float)
        c = L.morton_codes(P, bits=1, lo=(0, 0, 0), hi=(1, 1, 1))
        self.assertEqual(list(c), [0, 1, 2, 4, 7])
        c2 = L.morton_codes(np.array([[3, 0, 0], [0, 0, 3]], float), bits=2, lo=(0, 0, 0), hi=(3, 3, 3))
        self.assertEqual(list(c2), [0b001001, 0b100100])

    def test_match_permutations_and_cost(self):
        rng = np.random.default_rng(1)
        A = rng.normal(0, 1, (4000, 3)).astype(np.float32)
        Bp = A[rng.permutation(len(A))] + np.float32(0.5)     # same shape shifted, shuffled
        for mode in L.names(L.MATCHES):
            pa, pb = L.match(A, Bp, mode, 6, 0)
            self.assertEqual(sorted(pa), list(range(len(A))), mode)
            self.assertEqual(sorted(pb), list(range(len(A))), mode)
        rnd = L.pair_cost(A, Bp, *L.match(A, Bp, 'random'))
        mor = L.pair_cost(A, Bp, *L.match(A, Bp, 'morton'))
        kd = L.pair_cost(A, Bp, *L.match(A, Bp, 'kd'))
        sli = L.pair_cost(A, Bp, *L.match(A, Bp, 'sliced', 8))
        exact = 0.5 * math.sqrt(3.0)                               # every point moves by the shift
        for c in (mor, kd, sli):
            self.assertAlmostEqual(c, exact, places=4)
        self.assertGreater(rnd, 2 * exact)
        with self.assertRaises(ValueError):
            L.match(A, Bp[:10])

    def test_kd_beats_morton_on_different_shapes(self):
        a = L.prepare_side(L.generate('blob', 20000, 1))
        b = L.prepare_side(L.generate('torus', 20000))
        costs = dict((m, L.build_pair(a, b, 0, m)['cost']) for m in ('random', 'morton', 'kd', 'sliced'))
        self.assertLess(costs['kd'], costs['morton'])
        self.assertLess(costs['sliced'], costs['morton'])
        self.assertLess(costs['morton'], costs['random'])

    def test_sliced_flow_energy_drops(self):
        rng = np.random.default_rng(2)
        A = rng.normal(0, 1, (3000, 3))
        Bc = L.generate('torus', 3000)['P'].astype(np.float64) * 2
        _, hist = L.sliced_flow(A, Bc, 12, 0, history=True)
        self.assertEqual(len(hist), 13)
        self.assertLess(hist[-1], hist[0] * 0.3)
        self.assertLessEqual(hist[-1], min(hist[:4]))

    def test_stagger(self):
        P = np.array([[0, 0, 0], [1, 0, 0], [0, 3, 0], [-0.5, -1, 0]], np.float32)
        for m in L.names(L.STAGGERS):
            d = L.stagger_delay(P, m)
            self.assertAlmostEqual(float(d.min()), 0.0)
            self.assertAlmostEqual(float(d.max()), 1.0)
        self.assertEqual(int(np.argmax(L.stagger_delay(P, 'axis'))), 2)
        self.assertEqual(len(L.stagger_delay(np.zeros((0, 3), np.float32))), 0)


class Pair(Tmp):
    def test_build_pair_channels(self):
        a = L.prepare_side(L.generate('sphere', 300))
        b = L.prepare_side(L.generate('grid', 500))
        pr = L.build_pair(a, b, 0, 'morton')
        self.assertEqual(pr['n'], 500)
        self.assertEqual(pr['M'].shape, (len(L.CHANNELS), 500))
        self.assertEqual(pr['M'].dtype, np.float32)
        np.testing.assert_allclose(pr['M'][0:3].T, a['P'][pr['ia']])
        np.testing.assert_allclose(pr['M'][4:7].T, b['P'][pr['ib']])
        np.testing.assert_allclose(pr['M'][12:16].T, b['C'][pr['ib']])
        self.assertTrue(0 <= pr['M'][3].min() and pr['M'][3].max() <= 1)
        self.assertEqual(L.build_pair(a, b, 1234)['n'], 1234)

    def test_load_pair_file_vs_generator_counts(self):
        txt = 'x y z\n' + '\n'.join('{} {} {}'.format(i, i % 7, -i) for i in range(321))
        p = self.path('c.xyz', txt, 'w')
        a, b, pr = L.load_pair({'source': 'file', 'file': p}, {'source': 'gen', 'gen': 'ring'})
        self.assertEqual((a['n'], b['n'], pr['n']), (321, 321, 321))
        self.assertAlmostEqual(float(np.linalg.norm(a['P'], axis=1).max()), 1.0, places=5)
        a, b, pr = L.load_pair({'source': 'gen'}, {'source': 'gen', 'gen': 'blob'}, count=0)
        self.assertEqual(pr['n'], 100000)

    def test_depthtex_side_matches_shader_formula(self):
        spec = {'source': 'depthtex', 'fov': 60.0, 'znear': 1.0, 'zfar': 10.0, 'aspect': 16 / 9.0, 'scale': 2.0,
                'offset': (0.1, 0.2, 0.3)}
        s = L.load_side(spec, 2000)
        t = s['tex']
        self.assertEqual(t['tex'][0], 1.0)
        # shader texSide at dn = 0.5 (proxy) must land on the prepared proxy positions
        uv = s['UV']
        z = 10.0 / (1 + 0.5 * (10.0 / 1.0 - 1))
        tt = math.tan(math.radians(30.0))
        p = np.stack([(uv[:, 0] - 0.5) * 2 * tt * t['off'][3] * z, (uv[:, 1] - 0.5) * 2 * tt * z,
                      np.full(len(uv), -z)], 1)
        q = (p - np.array(t['fit'][:3])) * t['fit'][3] + np.array(t['off'][:3])
        np.testing.assert_allclose(q, s['P'], atol=1e-5)
        f = L.load_side({'source': 'gen'}, 10)
        self.assertEqual(f['tex']['tex'][0], 0.0)

    def test_depthfile_side(self):
        a = np.linspace(0, 1, 64 * 48, dtype=np.float32).reshape(48, 64)
        p = os.path.join(self.d, 'd.npy')
        np.save(p, a)
        s = L.load_side({'source': 'depthfile', 'depthfile': p, 'step': 4, 'up': 'z'}, 0)
        self.assertEqual(s['n'], 16 * 12)                    # up axis ignored for depth (camera space)
        self.assertAlmostEqual(float(np.linalg.norm(s['P'], axis=1).max()), 1.0, places=5)


class Morph(unittest.TestCase):
    def test_ease(self):
        for k in L.names(L.EASES):
            self.assertAlmostEqual(L.ease(0.0, k), 0.0)
            self.assertAlmostEqual(L.ease(1.0, k), 1.0)
            xs = np.linspace(0, 1, 50)
            self.assertTrue((np.diff(L.ease(xs, k)) >= -1e-12).all(), k)
        self.assertEqual(L.ease(-3, 'in'), 0.0)
        self.assertEqual(L.ease(7, 'out'), 1.0)

    def test_point_morph_ends_and_stagger(self):
        d = np.linspace(0, 1, 11)
        for s in (0.0, 0.5, 3.0):
            for k in L.names(L.EASES):
                np.testing.assert_allclose(L.point_morph(0.0, d, s, k), 0.0, atol=1e-12)
                np.testing.assert_allclose(L.point_morph(1.0, d, s, k), 1.0, atol=1e-12)
        e = L.point_morph(0.4, d, 1.0)
        self.assertTrue((np.diff(e) <= 0).all())               # delay 0 goes first
        np.testing.assert_allclose(L.point_morph(0.3, d, 0.0, 'linear'), 0.3)

    def test_morph_positions_L2_L3(self):
        rng = np.random.default_rng(4)
        Pa, Pb = rng.normal(0, 1, (500, 3)), rng.normal(2, 1, (500, 3))
        off = rng.normal(0, 1, (500, 3))
        np.testing.assert_allclose(L.morph_positions(Pa, Pb, np.zeros(500), 0.7, off), Pa, atol=1e-5)
        np.testing.assert_allclose(L.morph_positions(Pa, Pb, np.ones(500), 0.7, off), Pb, atol=1e-5)
        mid = L.morph_positions(Pa, Pb, np.full(500, 0.5))
        np.testing.assert_allclose(mid.mean(0), (Pa.mean(0) + Pb.mean(0)) / 2, atol=1e-3)

    def test_morph_bpm(self):
        self.assertEqual(L.morph_bpm(0.0, 4, 1), 0.0)
        self.assertEqual(L.morph_bpm(2.9, 4, 1), 0.0)
        self.assertAlmostEqual(L.morph_bpm(3.5, 4, 1), 0.5)
        self.assertAlmostEqual(L.morph_bpm(4.0, 4, 1), 1.0)
        self.assertAlmostEqual(L.morph_bpm(6.0, 4, 1), 1.0)
        self.assertAlmostEqual(L.morph_bpm(7.5, 4, 1), 0.5)
        self.assertAlmostEqual(L.morph_bpm(8.0, 4, 1), 0.0)       # period = 2 x beats per swap
        self.assertAlmostEqual(L.morph_bpm(16.0 + 3.5, 4, 1), 0.5)
        self.assertEqual(L.morph_bpm(5.0, 4, 0), 1.0)              # 0 morph beats = cut
        self.assertAlmostEqual(L.morph_lfo(0, 1), 0.0)
        self.assertAlmostEqual(L.morph_lfo(0.5, 1), 1.0)

    def test_smooth(self):
        self.assertEqual(L.smooth(None, 0.7, 0.016), 0.7)
        up = L.smooth(0.0, 1.0, 1 / 60.0, 0.05, 0.3)
        dn = L.smooth(1.0, 0.0, 1 / 60.0, 0.05, 0.3)
        self.assertGreater(up, 1.0 - dn)                           # attack faster than release
        self.assertEqual(L.smooth(0.2, 0.9, 0.016, 0, 0), 0.9)

    def test_engine_step(self):
        st, o = L.engine_step(None, 10.0, {'mode': 'manual', 'morph': 0.42})
        self.assertAlmostEqual(o['morph'], 0.42)
        np.testing.assert_allclose([o['camx'], o['camy'], o['camz']],
                                   L.orbit_position(0, 10, 3.0), atol=1e-9)
        p = {'mode': 'bpm', 'tempo': 'manual', 'bpm': 120.0, 'beatsperswap': 4, 'morphbeats': 1, 'autorbit': 90.0}
        st = None
        for f in range(0, 121):
            st, o = L.engine_step(st, 10.0 + f / 60.0, p)
        self.assertAlmostEqual(o['beat'], 4.0, places=6)            # 2 s at 120 bpm
        self.assertAlmostEqual(o['morph'], 1.0)
        self.assertAlmostEqual(o['az'], 180.0, places=6)
        st, o = L.engine_step(None, 0.0, {'mode': 'audio', 'audiogain': 2.0}, 0.3)
        self.assertAlmostEqual(o['morph'], 0.6)
        self.assertEqual(set(o), set(L.ENGINE_CHANNELS))

    def test_orbit_and_sizes(self):
        np.testing.assert_allclose(L.orbit_position(0, 0, 5), (0, 0, 5), atol=1e-12)
        np.testing.assert_allclose(L.orbit_position(90, 0, 2, (1, 1, 1)), (3, 1, 1), atol=1e-12)
        np.testing.assert_allclose(L.orbit_position(0, 90, 2), (0, 2, 0), atol=1e-12)
        self.assertAlmostEqual(L.radius_px(3, 0, 5, 10), 3)
        self.assertAlmostEqual(L.radius_px(3, 1, 5, 10), 1.5)
        self.assertAlmostEqual(L.radius_px(3, 0, 5, 10, dof=2, focus=4), 15)
        self.assertAlmostEqual(L.focal_px(1920, 90), 960, places=6)
        self.assertGreater(L.frame_distance(1.0, 45), 1.0 / math.tan(math.radians(22.5)))

    def test_shapes_and_post(self):
        self.assertEqual(L.shape_alpha('disc', 0.5, 0.5), 1.0)
        self.assertEqual(L.shape_alpha('disc', 0.9, 0.9), 0.0)
        self.assertEqual(L.shape_alpha('ring', 0.1, 0), 0.0)
        self.assertAlmostEqual(L.shape_alpha('soft', 0, 0), 1.0)
        self.assertAlmostEqual(L.shape_alpha('streak', 1, 0), 1.0)
        self.assertAlmostEqual(L.shape_alpha('streak', -1, 0), 0.15)
        self.assertEqual(L.post_pixel((0.5, 0.5, 0.5, 0.5)), (0.5, 0.5, 0.5, 0.5))
        r = L.post_pixel((2.0, 0, 0, 1.0), tonemap=True)
        self.assertAlmostEqual(r[0], 2 / 3)
        r = L.post_pixel((0, 0, 0, 0), bg=(1, 0, 0, 1))
        self.assertEqual(r, (1, 0, 0, 1))
        r = L.post_pixel((0.25, 0, 0, 0.5), premult=False)
        self.assertAlmostEqual(r[0], 0.5)
        self.assertEqual(L.post_pixel((0.25, 0, 0, 0.5), outputalpha=False)[3], 1.0)

    def test_status_line(self):
        pr = {'n': 10, 'cost': 0.5}
        self.assertIn('N 10', L.status_line(pr, {'src': 'a'}, {'src': 'b'}, 12))
        self.assertTrue(L.status_line(pr, {}, {}, 0, 'boom').startswith('ERROR'))


class FakePage(object):
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def _add(self, name, comps):
        g = [FakePar(name + c if c else name) for c in comps]
        for p in g:
            self.owner.parnames.add(p.name)
        self.owner.groups[name] = g
        return g

    def __getattr__(self, attr):
        if not attr.startswith('append'):
            raise AttributeError(attr)
        style = attr[6:]

        def f(name, label='', size=1):
            comps = {'XYZ': 'xyz', 'RGB': 'rgb', 'RGBA': 'rgba'}.get(style)
            if comps is None:
                comps = [str(i + 1) for i in range(size)] if size > 1 else ['']
            return self._add(name, list(comps))
        return f


class FakePar(object):
    def __init__(self, name):
        self.name = name
        self.readOnly = False


class FakeGroups(object):
    def __init__(self, groups):
        self._g = groups

    def __getattr__(self, n):
        return self._g.get(n)


class FakeComp(object):
    def __init__(self):
        self.parnames, self.groups, self.customPages = set(), {}, []
        self.parGroup = FakeGroups(self.groups)

    def appendCustomPage(self, name):
        p = FakePage(self, name)
        self.customPages.append(p)
        return p

    @property
    def par(self):
        names = self.parnames

        class _P(object):
            def __getattr__(s, n):
                if n in names:
                    return FakePar(n)
                raise AttributeError(n)
        return _P()


class BuilderConsistency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comp = FakeComp()
        PB._pars(cls.comp, L)
        def rd(p):
            with open(p) as f:
                return f.read()
        cls.vert, cls.pix, cls.post = rd(PB.VERT_FILE), rd(PB.PIX_FILE), rd(PB.POST_FILE)
        cls.rt, cls.builder = rd(PB.RT_FILE), rd(os.path.join(B, 'pointcloud.py'))

    def test_ascii(self):
        for p in (PB.VERT_FILE, PB.PIX_FILE, PB.POST_FILE, PB.RT_FILE, PB.LOGIC_FILE, os.path.join(B, 'pointcloud.py')):
            with open(p, 'rb') as f:
                f.read().decode('ascii')

    def test_every_referenced_par_exists(self):
        names = self.comp.parnames
        refs = set(re.findall(r"parent\(\)\.par\.([A-Z][a-z0-9]*)", self.builder))
        refs |= set(re.findall(r"\bp\.([A-Z][a-z0-9]*)", self.rt)) | set(re.findall(r"comp\.par\.([A-Z][a-z0-9]*)",
                                                                                  self.rt))
        refs |= set(re.findall(r"P\.format\('([A-Z][a-z0-9]*)'\)", self.builder))
        missing = [r for r in refs if r not in names and not any(n.startswith(r) and len(n) <= len(r) + 1
                                                                  for n in names)]   # 'Target' + ax, 'Bgcolor' + ch
        self.assertFalse(sorted(missing), sorted(names))

    def test_load_pars_exist(self):
        src = self.rt.split('LOAD_PARS = ')[1].split(')')[0]
        for n in re.findall(r"'(\w+)'", src):
            self.assertIn(n, self.comp.groups, n)
        for n in re.findall(r"'(\w+)'", self.rt.split('RESET_LOOK = ')[1].split('}')[0]):
            if not n[0].isupper():
                continue
            self.assertIn(n, self.comp.parnames, n)
        self.assertIn('Frame', self.comp.parnames)

    def test_uniforms_declared(self):
        for row in PB.MAT_VECS:
            self.assertIn('uniform vec4 {};'.format(row[0]), self.vert, row[0])
        for un, pn in PB.SAMPLERS:
            self.assertIn('uniform sampler2D {};'.format(un), self.vert)
            self.assertIn(pn, self.comp.groups)
        for u in re.findall(r'uniform vec4 (\w+);', self.pix):
            self.assertIn('uniform vec4 {};'.format(u), self.vert)          # shared names, same type
        self.assertLessEqual(len(PB.MAT_VECS), 16)

    def test_instance_slots_and_channels(self):
        self.assertEqual([c for _, chans in L.SLOTS for c in chans], L.CHANNELS)
        for i in range(len(L.SLOTS)):
            self.assertIn('TDInstanceCustomAttrib{}('.format(i), self.vert)
        self.assertNotIn('TDInstanceCustomAttrib{}('.format(len(L.SLOTS)), self.vert)
        self.assertTrue(all(len(ch) <= 4 for _, ch in L.SLOTS))
        self.assertLessEqual(len(L.SLOTS), 8)

    def test_single_pass_and_compute(self):
        self.assertIn('layout (local_size_x = 8, local_size_y = 8) in;', self.post)
        self.assertIn('TDImageStoreOutput', self.post)
        self.assertNotIn('sTD2DInputs[1]', self.post)                          # one input, one pass
        self.assertIn('clamp(', self.vert)                                     # T-35 clamps on fetches
        self.assertIn('textureLod', self.vert)                                 # no derivatives in the vertex stage
        self.assertIn('out Vertex', self.vert)
        self.assertIn('in Vertex', self.pix)

    def test_menus_match_shader_indices(self):
        self.assertEqual(L.names(L.EASES), ['linear', 'in', 'out', 'inout', 'sine'])          # easeK 0..4
        self.assertEqual(L.names(L.SHAPES), ['disc', 'soft', 'square', 'ring', 'streak'])     # shape 0..4
        self.assertEqual(L.names(L.BLENDS), ['add', 'over', 'opaque'])                        # blend 0..2
        self.assertEqual(L.names(L.DEPTHKINDS)[1], 'depth')                                   # kind 1 = depth

    def test_stage_ops_unique(self):
        seen = [o for s in PB.STAGES for o in s['ops']]
        self.assertEqual(len(seen), len(set(seen)))


if __name__ == '__main__':
    unittest.main()
