"""Offline tests for builders/pop_tree.py + pop_tree_logic.py (lane H TC-18; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_tree.py'"""
import math
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_tree_logic as L  # noqa: E402


def walk(k, p):
    """Scalar ancestor walk exactly as the GLSL segs pass (independent of the level-by-level mirror)."""
    b = int(p['branches'])
    D = L.depth_eff(b, p['depth'])
    nodes = []
    kk = k
    while kk > 0:
        nodes.append(kk)
        kk = (kk - 1) // b
    Lv = len(nodes)
    pos = np.zeros(3)
    R = np.eye(3)
    ln = p['length']
    seed = int(p['seed'])
    for s in range(Lv):
        n = nodes[Lv - 1 - s]
        pos = pos + R[:, 1] * ln
        lev = s + 1
        slot = (n - 1) % b
        phi = slot * L.TAU / b + lev * math.radians(p['twist']) + math.radians(p['jitter']) * (2 * L.h1(n, seed) - 1)
        spr = math.radians(p['spread']) + math.radians(p['jitter']) * (2 * L.h1(n, seed + 1) - 1)
        sw = math.radians(p['sway']) * math.sin(p['time'] + lev * 0.7) * lev / max(D, 1)
        R = R @ L.ry(np.float64(phi)) @ L.rz(np.float64(sw)) @ L.rx(np.float64(spr))
        ln *= p['ratio'] * (1 + p['lenjitter'] * (2 * L.h1(n, seed + 2) - 1))
    g = min(max(p['progress'] * (D + 1) - Lv, 0.0), 1.0)
    return pos, pos + R[:, 1] * ln * g, Lv


class Logic(unittest.TestCase):
    def test_counts_and_caps(self):
        self.assertEqual(L.nseg(2, 10), 2047)
        self.assertEqual(L.nseg(3, 2), 13)
        for b in (2, 3, 4):
            d = L.max_depth(b)
            self.assertLessEqual(L.nseg(b, d), L.SEG_CAP)
            self.assertGreater((b ** (d + 2) - 1) // (b - 1), L.SEG_CAP)
            self.assertEqual(L.nseg(b, 99), L.nseg(b, d))
        self.assertEqual([L.max_depth(b) for b in (2, 3, 4)], [17, 10, 8])
        self.assertLessEqual(L.nseg(2, 17) * L.samples_eff(L.nseg(2, 17), 64), L.PTS_CAP)
        self.assertEqual(L.seg_side(2047), 46)

    def test_levels_bfs(self):
        lev = L.level_of(np.arange(15), 2)
        self.assertEqual(list(lev), [0, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3])
        _s, _e, lv, _w = L.segments(L.params(depth=3))
        self.assertTrue((lv == lev).all())

    def test_mirror_equals_walk(self):
        for kw in ({}, {'branches': 3, 'depth': 4, 'time': 1.3, 'progress': 0.6}, {'branches': 4, 'depth': 3}):
            p = L.params(**kw)
            s0, s1, lv, _ = L.segments(p)
            for k in list(range(0, len(lv), max(1, len(lv) // 40))) + [len(lv) - 1]:
                a, b, l = walk(k, p)
                self.assertLess(np.abs(a - s0[k]).max(), 1e-12)
                self.assertLess(np.abs(b - s1[k]).max(), 1e-12)
                self.assertEqual(l, lv[k])

    def test_children_start_at_parent_end(self):
        p = L.params(depth=6, progress=1.0)
        s0, s1, lv, _ = L.segments(p)
        k = np.arange(1, len(lv))
        self.assertLess(np.abs(s0[k] - s1[(k - 1) // 2]).max(), 1e-12)
        ln = np.linalg.norm(s1 - s0, axis=1)
        self.assertAlmostEqual(ln[0], p['length'])
        self.assertTrue((ln[lv == 3] < p['length'] * (p['ratio'] * 1.16) ** 3).all())

    def test_progress_grows_outward(self):
        p = L.params(depth=5, progress=0.5)            # levels 0..5, Progress x 6 = 3: levels 0-2 full, 3+ hidden
        s0, s1, lv, _ = L.segments(p)
        ln = np.linalg.norm(s1 - s0, axis=1)
        self.assertTrue((ln[lv <= 2] > 0).all() and (ln[lv >= 3] == 0).all())
        a, b, _l, _w = L.segments(L.params(depth=5, progress=0.0))
        self.assertTrue((a == b).all())                      # nothing drawn (zero-length segments are hidden)

    def test_no_sway_no_jitter_is_symmetric(self):
        p = L.params(depth=4, sway=0.0, jitter=0.0, lenjitter=0.0, twist=0.0, spread=40.0)
        s0, s1, lv, _ = L.segments(p)
        self.assertAlmostEqual(s1[1, 0], -s1[2, 0], 12)      # two children mirror each other in x
        self.assertAlmostEqual(s1[1, 1], s1[2, 1], 12)

    def test_texture_layout(self):
        p = L.params(depth=4)
        T = L.texture(p)
        s0, s1, lv, w = L.segments(p)
        side = L.seg_side(len(lv))
        self.assertEqual(T.shape, (side, 2 * side, 4))
        k = 9
        self.assertTrue(np.allclose(T[k // side, 2 * (k % side), :3], s0[k]))
        self.assertTrue(np.allclose(T[k // side, 2 * (k % side) + 1, :3], s1[k]))
        self.assertEqual(T[k // side, 2 * (k % side), 3], lv[k])
        self.assertAlmostEqual(T[k // side, 2 * (k % side) + 1, 3], w[k])
        self.assertEqual(T[-1, -2, 3], -1.0)                 # unused texel (31 segments in 6 x 6)

    def test_dust(self):
        p = L.params(depth=3)
        d = L.dust(p, 5)
        self.assertEqual(d.shape, (15 * 5, 3))
        self.assertTrue(np.isfinite(d).all())


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_tree.py')
        o = c.ops
        for n in ('in1', 'clock_rate', 'clock', 'dims', 'segs', 'segs_compute', 'out2', 'pts', 'mat', 'geo',
                  'lines_grid', 'lmat', 'geo_lines', 'cam', 'render', 'look', 'out_sel', 'out1'):
            self.assertIn(n, o)
        self.assertEqual(o['segs'].par.mode.val, 'compute')
        self.assertEqual(o['segs'].par.format.val, 'rgba32float')
        self.assertEqual(K.uniform_names(o['segs']), [u for u, _ in ns['SEG_UNIFORMS']])
        self.assertEqual(o['pts'].par.surftype.val, 'points')
        self.assertEqual((o['lines_grid'].par.surftype.val, o['lines_grid'].par.linex.val,
                          o['lines_grid'].par.liney.val), ('lines', False, True))
        self.assertEqual(o['geo'].op('sel').par.pop.val, '../pts')
        self.assertEqual(o['geo_lines'].op('sel').par.pop.val, '../lines_grid')
        for mn in ('mat', 'lmat'):
            m = o[mn]
            self.assertEqual((m.par.sampler0name.val, m.par.sampler0top.val), ('sSeg', 'segs'))
            self.assertEqual((m.par.srcblend.val, m.par.destblend.val), ('one', 'one'))
        self.assertIn('Lines', o['render'].par.geometry.expr)
        self.assertEqual([K.src(o['look'], 0), K.src(o['look'], 1)], ['render', 'in1'])
        self.assertEqual([K.src(o['out_sel'], 0), K.src(o['out_sel'], 1)], ['in1', 'look'])
        self.assertEqual(K.src(o['out2'], 0), 'segs')
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        self.assertEqual(c.par.Depth.max, 17)

    def test_dims_exprs_match_logic(self):
        _c, _r, ns = K.fake_build('pop_tree.py')
        self.assertEqual(ns['MAXDEPTH'], {b: L.max_depth(b) for b in (2, 3, 4)})
        dims = dict(ns['DIMS'])
        for b, d, s in ((2, 10, 8), (3, 12, 64), (4, 30, 1), (2, 17, 64), (2, 0, 3)):
            env = {'math': math, 'parent': lambda: type('P', (), {'par': type('Q', (), {
                'Branches': type('V', (), {'eval': lambda self: b})(),
                'Depth': type('V', (), {'eval': lambda self: d})(),
                'Samples': type('V', (), {'eval': lambda self: s})()})()})()}
            n = eval(dims['nseg'], env)
            self.assertEqual(n, L.nseg(b, d))
            self.assertEqual(eval(dims['side'], env), L.seg_side(n))
            self.assertEqual(eval(dims['samples'], env), L.samples_eff(n, s))
            self.assertLessEqual(eval(dims['npts'], env), L.PTS_CAP)

    def test_first(self):
        c, reply, ns = K.fake_build('pop_tree.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_tree.py')
        for u, _ in ns['SEG_UNIFORMS']:
            self.assertIn(u, K.declared(ns['SEGS']))
        for t in ('VERTEX', 'LVERTEX'):
            for u, _ in ns['MAT_UNIFORMS']:
                self.assertIn(u, K.declared(ns[t]))
            self.assertIn('TDPos()', ns[t])
        for u, _ in ns['LOOK_UNIFORMS']:
            self.assertIn(u, K.declared(ns['LOOK']))
        self.assertNotIn('#version', ns['SEGS'] + ns['VERTEX'] + ns['LVERTEX'] + ns['PIXEL'] + ns['LOOK'])

    def test_ascii(self):
        for f in ('pop_tree.py', 'pop_tree_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_tree.py')
        for fn, key in ((K.glslc_compute, 'SEGS'), (K.glslc_vert, 'VERTEX'), (K.glslc_vert, 'LVERTEX'),
                        (K.glslc_pixel, 'PIXEL'), (K.glslc_compute, 'LOOK')):
            ok, err = fn(ns[key])
            self.assertTrue(ok, key + '\n' + err)
            self.assertEqual(K.bounded_loops(ns[key]), [], key)


if __name__ == '__main__':
    unittest.main()
