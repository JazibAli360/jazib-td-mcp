"""Offline tests for builders/pop_linegrowth.py + pop_linegrowth_logic.py + pop_scan.py (lane H TC-09; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_linegrowth.py'"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_scan as S  # noqa: E402
import pop_linegrowth_logic as L  # noqa: E402


class Scan(unittest.TestCase):
    def test_scan_exact(self):
        rng = np.random.default_rng(3)
        for n in (1, 7, 1000, 1024):
            v = rng.integers(0, 9, n)
            a, ta = S.exclusive_scan(v)
            b, tb = S.hillis_steele_excl(v)
            ref = np.concatenate([[0], np.cumsum(v)[:-1]])
            self.assertTrue((a == ref).all() and (b == ref).all())
            self.assertEqual(ta, int(v.sum()))
            self.assertEqual(tb, int(v.sum()))


class Logic(unittest.TestCase):
    def test_seed_shapes(self):
        for sh in L.SHAPES:
            P, n = L.seed_nodes(L.params(shape=sh))
            self.assertEqual(P.shape, (64, 2))
            self.assertLessEqual(np.linalg.norm(P, axis=-1).max(), 0.1 + 1e-12)
        P, _ = L.seed_nodes(L.params())
        self.assertTrue(np.allclose(np.linalg.norm(P, axis=-1), 0.1))

    def test_insert_order_exact(self):
        p = L.params(maxedge=0.5)
        P = np.array([[0, 0], [1, 0], [1.2, 0], [1.2, 1]], float)
        out, n = L.insert(P, 4, p)                     # edges 1.0, 0.2, 1.0, 1.56 (closed) -> 3 splits
        self.assertEqual(n, 7)
        ref = np.array([[0, 0], [0.5, 0], [1, 0], [1.2, 0], [1.2, 0.5], [1.2, 1], [0.6, 0.5]])
        self.assertTrue(np.allclose(out, ref))
        out, n = L.insert(P, 4, L.params(maxedge=0.5, shape='line'))   # open: no wrap edge
        self.assertEqual(n, 6)
        out, n = L.insert(P, 4, L.params(maxedge=0.5, maxnodes=5))     # budget 1: the first flag only
        self.assertEqual(n, 5)
        self.assertTrue(np.allclose(out, [[0, 0], [0.5, 0], [1, 0], [1.2, 0], [1.2, 1]]))

    def test_insert_chunks_cross_threads(self):
        n = 3000
        a = np.linspace(0, L.TAU, n, endpoint=False)
        P = np.stack([np.cos(a), np.sin(a)], -1)
        P[::3] *= 1.01                                 # every third edge pair longer
        p = L.params(maxedge=np.linalg.norm(P[1] - P[2]) * 1.001, maxnodes=8192)
        out, cnt = L.insert(P, n, p)
        fl = L.split_flags(P, n, p)
        self.assertEqual(cnt, n + fl.sum())
        keep = np.arange(n) + np.concatenate([[0], np.cumsum(fl)[:-1]])
        self.assertTrue(np.allclose(out[keep], P))

    def test_first_frame_count(self):
        P, counts = L.run(1, L.params())
        self.assertEqual(counts, [128])                # 64 seed edges of 0.0098 > Maxedge 0.009 all split
        self.assertTrue(np.isfinite(P).all())

    def test_forces_no_play_and_seed_rest(self):
        P, n = L.seed_nodes(L.params())
        self.assertTrue(np.array_equal(L.forces(P, n, 3, L.params(play=0)), P))
        Q = L.forces(P, n, 1, L.params())
        self.assertLessEqual(np.linalg.norm(Q - P, axis=-1).max(), 0.003 + 1e-12)

    def test_forces_symmetry_without_jitter(self):
        P, n = L.seed_nodes(L.params(seedcount=32))
        Q = L.forces(P, n, 1, L.params(jitter=0.0))
        r = np.linalg.norm(Q, axis=-1)
        self.assertLess(r.max() - r.min(), 1e-12)      # a circle stays a circle

    def test_growth_deterministic_and_capped(self):
        p = L.params(maxnodes=512)
        P1, c1 = L.run(40, p)
        P2, c2 = L.run(40, p)
        self.assertEqual(c1, c2)
        self.assertTrue(np.array_equal(P1, P2))
        self.assertEqual(c1[-1], 512)
        self.assertTrue(all(b >= a for a, b in zip(c1, c1[1:])))
        P32, c32 = L.run(40, p, np.float32)
        self.assertTrue(np.isfinite(P32).all())
        self.assertLess(abs(c32[-1] - c1[-1]), 0.02 * c1[-1] + 1)


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_linegrowth.py')
        o = c.ops
        for n in ('in1', 'lg_pulses', 'state_blank', 'state_fb', 'forces', 'insert', 'pts', 'strip', 'mat',
                  'mat_lines', 'geo', 'geo_lines', 'cam', 'render', 'render_lines', 'view_sel', 'look',
                  'out_sel', 'out1'):
            self.assertIn(n, o)
        self.assertEqual(K.src(o['forces'], 0), 'state_fb')
        self.assertEqual(K.src(o['insert'], 0), 'forces')
        self.assertEqual(o['state_fb'].par.top.val, 'insert')
        self.assertEqual(K.src(o['state_fb'], 0), 'state_blank')
        ins = o['insert']
        self.assertFalse(ins.par.autodispatchsize.val)
        self.assertEqual((ins.par.dispatchsizex.val, ins.par.dispatchsizey.val, ins.par.dispatchsizez.val), (1, 1, 1))
        for g in ('forces', 'insert'):
            self.assertEqual(o[g].par.mode.val, 'compute')
            self.assertEqual(o[g].par.format.val, 'rgba32float')
            self.assertEqual((o[g].par.resolutionw.expr, o[g].par.resolutionh.expr), ('128', '65'))
        self.assertEqual(o['pts'].par.surftype.val, 'points')
        self.assertEqual(o['strip'].par.surftype.val, 'linestrips')
        self.assertEqual(o['mat'].par.sampler0top.val, 'insert')
        self.assertEqual(o['mat'].par.destblend.val, 'one')
        self.assertEqual([K.src(o['view_sel'], 0), K.src(o['view_sel'], 1)], ['render', 'render_lines'])
        self.assertEqual(o['render'].par.render.expr,
                         "not parent().par.Lines.eval() and parent().par.Raster.eval() == 'render'")  # Render par gate:
        self.assertEqual(o['render_lines'].par.render.expr, 'bool(parent().par.Lines.eval())')   # pane-proof
        self.assertEqual([K.src(o['look'], 0), K.src(o['look'], 1)], ['view_sel', 'in1'])
        self.assertEqual([K.src(o['out_sel'], 0), K.src(o['out_sel'], 1)], ['in1', 'look_sel'])
        self.assertEqual([K.src(o['look_sel'], k) for k in range(2)], ['look', 'glook'])
        self.assertEqual(o['look_sel'].par.index.expr, ns['GLOOK_ON_E'])
        self.assertEqual([K.src(o['glook'], k) for k in range(2)], ['insert', 'in1'])
        self.assertEqual(K.uniform_names(o['glook']), [u for u, _ in ns['MAT_U'] + ns['LOOK_U']])
        self.assertEqual(c.par.Raster.val, 'compute')
        self.assertEqual(K.uniform_names(o['forces']), [u for u, _ in ns['SIM_U']])
        compile(o['lg_pulses'].text, 'pulses', 'exec')
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        self.assertEqual(c.par.Maxnodes.max, 8192)

    def test_first(self):
        c, reply, ns = K.fake_build('pop_linegrowth.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_linegrowth.py')
        for t in (ns['FORCES'], ns['INSERT']):
            for u, _ in ns['SIM_U']:
                self.assertIn(u, K.declared(t))
        for t in (ns['VERT_POINTS'], ns['VERT_LINES']):
            self.assertIn('TDPos()', t)
            for u, _ in ns['MAT_U']:
                self.assertIn(u, K.declared(t))

    def test_glook_tile_cull_keeps_every_covered_pixel(self):
        # GLOOK culls a node to a 16 x 16 tile when its [w - S/2, w + S/2) box can hold a tile pixel centre.
        rng = np.random.default_rng(7)
        Wd, Ht = 70, 50
        for S in (1.0, 2.0, 3.5, 8.0):
            hs = 0.5 * S
            for w in rng.uniform(-6, 76, (400, 2)):
                for y in range(Ht):
                    for x in range(Wd):
                        cx, cy = x + 0.5, y + 0.5
                        qx, qy = cx - (w[0] - hs), cy - (w[1] - hs)
                        if not (0 <= qx < S and 0 <= qy < S):
                            continue
                        t0x, t0y = (x // 16) * 16 + 0.5, (y // 16) * 16 + 0.5
                        t1x, t1y = t0x + 15.0, t0y + 15.0
                        self.assertTrue(w[0] + hs > t0x and w[0] - hs <= t1x and w[1] + hs > t0y and w[1] - hs <= t1y)

    def test_ascii(self):
        for f in ('pop_scan.py', 'pop_linegrowth.py', 'pop_linegrowth_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_linegrowth.py')
        for n in ('FORCES', 'INSERT', 'LOOK', 'GLOOK'):
            ok, err = K.glslc_compute(ns[n])
            self.assertTrue(ok, n + '\n' + err)
            self.assertEqual(K.bounded_loops(ns[n]), [], n)
        for n in ('VERT_POINTS', 'VERT_LINES'):
            ok, err = K.glslc_vert(ns[n])
            self.assertTrue(ok, n + '\n' + err)
        ok, err = K.glslc_pixel(ns['PIXEL'])
        self.assertTrue(ok, err)

    def test_shared_memory_budget(self):
        _c, _r, ns = K.fake_build('pop_linegrowth.py')
        self.assertLessEqual(256 * 8, 32768)            # forces: vec2 sP[256] = 2 KB
        self.assertIn('shared uint sScan[SCAN_T]', ns['INSERT'])   # 4 KB


if __name__ == '__main__':
    unittest.main()
