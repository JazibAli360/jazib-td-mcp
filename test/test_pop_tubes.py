"""Offline tests for builders/pop_tubes.py + pop_tubes_logic.py (lane H TC-08; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_tubes.py'"""
import math
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_tubes_logic as L  # noqa: E402

if 'constantMAT' not in K.TD_CLASSES:
    K.TD_CLASSES.append('constantMAT')


def run_hist(src, n, k, frames, dt=1 / 60.0, scale=0.6, seed=1):
    i = np.arange(n)
    t = 0.0
    s0 = 'lissajous' if src == 'flow' else src
    H = L.init_hist(n, k, L.head(s0, i, t, scale, seed), t)
    for _ in range(frames):
        t += dt
        H = L.shift(H, L.head(src, i, t, scale, seed, prev=H[:, 0, :3], dt=t - H[0, 0, 3]), t)
    return H, t


class Logic(unittest.TestCase):
    def test_shift_exact(self):
        H, t = run_hist('lissajous', 5, 8, 20)
        i = np.arange(5)
        for kk in range(8):                                 # column k = head of k frames ago
            tk = t - kk / 60.0
            self.assertTrue(np.allclose(H[:, kk, :3], L.head('lissajous', i, tk, 0.6, 1)), kk)
            self.assertTrue(np.allclose(H[:, kk, 3], tk))

    def test_reset_fills(self):
        H = L.init_hist(3, 6, np.ones((3, 3)), 2.0)
        self.assertTrue((H[..., :3] == 1).all() and (H[..., 3] == 2).all())

    def test_heads_bounded_finite(self):
        for src in L.SOURCES[:3]:
            H, _t = run_hist(src, 16, 16, 600)
            self.assertTrue(np.isfinite(H).all(), src)
            self.assertLess(np.abs(H[..., :3]).max(), 3.0, src)
        p = L.head('input', np.arange(4), 0.0, 2.0, 1, xyz=np.ones((4, 3)))
        self.assertTrue(np.allclose(p, 2.0))

    def test_flow_moves_smoothly(self):
        H, _t = run_hist('flow', 8, 32, 200)
        step = np.linalg.norm(np.diff(H[:, :, :3], axis=1), axis=-1)
        self.assertLess(step.max(), 0.05)
        self.assertGreater(step.mean(), 1e-5)

    def test_ring_radius_and_frame(self):
        H, _t = run_hist('vortex', 4, 24, 60)
        S, R, tap = 8, 0.02, 1.0
        rows = L.rows_for(4, S)
        for i in range(4):
            for k in (0, 5, 23):
                T, N, B = L.frame(H, i, k)
                self.assertAlmostEqual(T @ N, 0.0, 9)
                self.assertAlmostEqual(np.linalg.norm(B), 1.0, 9)
                for j in range(S + 1):
                    p, gap = L.vertex(H, k, i * (S + 3) + j, S, R, tap)
                    self.assertEqual(gap, 0.0)
                    self.assertAlmostEqual(np.linalg.norm(p - H[i, k, :3]), L.radius_at(k, 24, R, tap), 9)
        self.assertEqual(L.radius_at(23, 24, R, tap), 0.0)
        self.assertEqual(rows, 4 * 11)

    def test_seam_rows(self):
        H, _t = run_hist('lissajous', 3, 10, 30)
        S = 6
        per = S + 3
        for i in range(3):
            for k in range(10):
                a, _ = L.vertex(H, k, i * per + S, S, 0.02, 1.0)
                b, g1 = L.vertex(H, k, i * per + S + 1, S, 0.02, 1.0)
                c, g2 = L.vertex(H, k, i * per + S + 2, S, 0.02, 1.0)
                self.assertTrue(np.allclose(a, b) and g1 == 1.0 and g2 == 1.0)        # zero-area quad, then hidden
                if i < 2:
                    d, g0 = L.vertex(H, k, (i + 1) * per, S, 0.02, 1.0)
                    self.assertTrue(np.allclose(c, d) and g0 == 0.0)                  # zero-area into next track
        r0, _ = L.vertex(H, 4, 0, S, 0.02, 1.0)
        rS, _ = L.vertex(H, 4, S, S, 0.02, 1.0)
        self.assertTrue(np.allclose(r0, rS))                                          # ring closes

    def test_degenerate_tangent(self):
        H = L.init_hist(2, 5, np.zeros((2, 3)), 0.0)
        T, N, B = L.frame(H, 0, 2)
        self.assertTrue(np.allclose(T, [0, 0, 1]) and np.isfinite(N).all())
        H[0, :, :3] = np.array([[0, k, 0] for k in range(5)], dtype=float)         # along y: the up swap
        T, N, B = L.frame(H, 0, 2)
        self.assertTrue(np.isfinite(N).all() and abs(T @ N) < 1e-12)

    def test_index_recovery(self):
        cols, rows = 64, L.rows_for(64, 8)
        for col, row in ((0, 0), (63, rows - 1), (17, 333), (40, 701)):
            _u, _v, c2, r2 = L.grid_uv(col, row, cols, rows)
            self.assertEqual((c2, r2), (col, row))
        self.assertLessEqual(L.rows_for(256, 16) * 128, 700000)                       # hard caps -> < 0.7 M points


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_tubes.py')
        o = c.ops
        for n in ('in1', 'in2', 'pulses', 'clock', 'spin', 'blank', 'xyz_sel', 'hist_fb', 'hist', 'out2', 'tubes',
                  'mat', 'geo', 'cam', 'render', 'look', 'out_sel', 'out1'):
            self.assertIn(n, o)
        self.assertNotIn('native', o)
        self.assertEqual([K.src(o['hist'], 0), K.src(o['hist'], 1)], ['hist_fb', 'xyz_sel'])
        self.assertEqual(o['hist_fb'].par.top.val, 'hist')
        self.assertEqual([K.src(o['xyz_sel'], 0), K.src(o['xyz_sel'], 1)], ['xyz_blank', 'in2'])
        self.assertEqual(o['hist'].par.mode.val, 'compute')
        self.assertEqual(o['tubes'].par.surftype.val, 'quads')
        self.assertEqual(o['tubes'].par.rows.expr, ns['ROWS_E'])
        m = o['mat']
        self.assertEqual((m.par.sampler0name.val, m.par.sampler0top.val), ('sH', 'hist'))
        self.assertEqual(m.par.destblend.val, 'one')
        self.assertFalse(m.par.depthtest.val)
        self.assertEqual(K.uniform_names(m), [u for u, _ in ns['MAT_UNIFORMS']])
        self.assertEqual(K.uniform_names(o['hist']), ['uH', 'uH2', 'uH3'])
        self.assertEqual(K.src(o['look'], 0), 'render')
        self.assertEqual(o['look'].par.inputfiltertype.val, 'mipmap')
        self.assertEqual([K.src(o['out_sel'], 0), K.src(o['out_sel'], 1)], ['in1', 'look'])
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        self.assertEqual(c.par.Tracks.max, 256)

    def test_first(self):
        c, reply, ns = K.fake_build('pop_tubes.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_native(self):
        c, reply, ns = K.fake_build('pop_tubes.py', native=True)
        nc = c.ops['native']
        self.assertFalse(nc.allowCooking)
        chain = [n for _c, n, _p in ns['NATIVE_CHAIN']]
        for a, b in zip(chain, chain[1:]):
            self.assertEqual(K.src(nc.ops[b], 0), a)
        self.assertEqual(nc.ops['parts'].par.maxparticles.val, 32)
        self.assertEqual(nc.ops['trail'].par.length.val, 30.0)
        self.assertEqual(nc.ops['trail'].par.surftype.val, 'rows')
        self.assertEqual(nc.ops['geo'].op('sel').par.pop.val, '../skin')
        self.assertEqual(K.src(c.ops['out_sel'], 2), 'native_sel')
        self.assertEqual(c.ops['native_sel'].par.top.val, 'native/render')
        self.assertIn('native', c.ops['out_sel'].par.index.expr)
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_tubes.py')
        for u, _ in ns['HIST_UNIFORMS']:
            self.assertIn(u, K.declared(ns['HIST']))
        for u, _ in ns['MAT_UNIFORMS']:
            self.assertIn(u, K.declared(ns['VERTEX']))
        self.assertIn('uL', K.declared(ns['LOOK']))
        self.assertIn('TDPos()', ns['VERTEX'])
        self.assertEqual(ns['SOURCES'], L.SOURCES)

    def test_ascii(self):
        for f in ('pop_tubes.py', 'pop_tubes_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_tubes.py')
        for fn, t in ((K.glslc_compute, ns['HIST']), (K.glslc_compute, ns['LOOK']), (K.glslc_vert, ns['VERTEX']),
                      (K.glslc_pixel, ns['PIXEL']), (K.glslc_vert, ns['NATIVE_VERT']),
                      (K.glslc_pixel, ns['NATIVE_PIXEL'])):
            ok, err = fn(t)
            self.assertTrue(ok, err)
            self.assertEqual(K.bounded_loops(t), [])


if __name__ == '__main__':
    unittest.main()
