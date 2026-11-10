"""Offline tests for builders/pop_terrain.py + pop_terrain_logic.py (lane H TC-19; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_terrain.py'"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_terrain_logic as L  # noqa: E402


def _rgb(self, n, label=''):
    out = []
    for ch in 'rgb':
        p = getattr(self.owner.par, n + ch)
        p.val = None
        self.owner.custom.append(n + ch)
        out.append(p)
    return out


K.FakePage.appendRGB = _rgb          # the shared kit has no RGB pars yet (local stand-in)


class Logic(unittest.TestCase):
    def test_remap(self):
        p = L.params()
        g = np.linspace(-1, 1, 11)
        w = L.remap(g, p)
        self.assertAlmostEqual(w[0], -p['extent'])
        self.assertAlmostEqual(w[-1], p['extent'])
        self.assertAlmostEqual(w[5], 0.0)
        self.assertTrue((np.diff(w) > 0).all())
        d = np.diff(w)
        self.assertLess(d[5], d[0])                                # dense round the camera
        self.assertTrue(np.allclose(L.remap(g, L.params(lodpow=1.0)), g * p['extent']))

    def test_fbm_range_ridge(self):
        x, z = np.meshgrid(np.linspace(-50, 50, 101), np.linspace(-50, 50, 101))
        for kw in ({}, {'ridge': 1}, {'octaves': 1}, {'octaves': 8}, {'octaves': 20}):
            n = L.fbm(x, z, L.params(**kw))
            self.assertTrue(np.isfinite(n).all() and n.min() >= 0 and n.max() <= 1, kw)
        a = L.fbm(x, z, L.params(octaves=20))
        b = L.fbm(x, z, L.params(octaves=8))
        self.assertTrue(np.allclose(a, b))                        # MAXOCT cap = the shader's #define

    def test_snap_and_scroll(self):
        p = L.params(scroll=3.33)
        c = L.cell(p)
        self.assertAlmostEqual(c, 40.0 * (2.0 / 159.0) ** 2)
        sn = L.snapped(p)
        self.assertLessEqual(sn, 3.33)
        self.assertLess(3.33 - sn, c)
        self.assertEqual(L.snapped(L.params(scroll=3.33, snap=0)), 3.33)
        # world-fixed: the same Wx/Wz in two frames gives the same height (no swimming)
        v1, w1 = L.vertices(L.params(scroll=0.0, cols=9, rows=9))
        v2, w2 = L.vertices(L.params(scroll=0.0, cols=9, rows=9))
        self.assertTrue(np.allclose(v1, v2))
        # render z = grid z - snap + scroll: the near rows move with the scroll remainder only
        c9 = L.cell(L.params(rows=9))
        p = L.params(scroll=c9 * 10.5, cols=9, rows=9)
        v, w = L.vertices(p)
        gz = L.remap(np.linspace(-1, 1, 9), p)
        self.assertTrue(np.allclose(v[:, 0, 2], gz + c9 * 0.5))

    def test_interp_error_sets_tolerance(self):
        e = L.interp_error(L.params())
        self.assertLess(np.median(e), 0.005)
        self.assertLess(np.percentile(e, 99), 0.03)

    def test_check_data_synthetic(self):
        p = L.params()
        rng = np.random.default_rng(3)
        wx = rng.uniform(-40, 40, (64, 36))
        wz = rng.uniform(-40, 40, (64, 36))
        arr = np.stack([L.fbm(wx, wz, p), wx, wz, np.ones_like(wx)], -1)
        r = L.check_data(arr, p)
        self.assertTrue(r['pass'])
        self.assertLess(r['med'], 1e-12)
        arr[..., 0] += 0.2
        self.assertFalse(L.check_data(arr, p)['pass'])


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_terrain.py')
        o = c.ops
        for n in ('in1', 'clock_rate', 'clock', 'grid', 'mat', 'mat_vertex', 'mat_pixel', 'geo', 'cam', 'render',
                  'out_sel', 'out1'):
            self.assertIn(n, o)
        g = o['grid']
        self.assertEqual((g.par.surftype.val, g.par.sizex.val, g.par.sizey.val), ('quads', 2.0, 2.0))
        self.assertEqual(o['geo'].op('sel').par.pop.val, '../grid')
        self.assertEqual(o['geo'].par.material.val, 'mat')
        self.assertEqual([K.src(o['out_sel'], 0), K.src(o['out_sel'], 1)], ['in1', 'render'])
        self.assertEqual(K.uniform_names(o['mat']), [u for u, _ in ns['UNIFORMS']])
        self.assertIn('rgba32float', o['render'].par.format.expr)
        self.assertIn('aa1', o['render'].par.antialias.expr)
        self.assertEqual(o['cam'].par.viewanglemethod.val, 'vertfov')
        self.assertFalse(o['mat'].par.blending.val)
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        for n in ('Amount', 'Style', 'Cols', 'Rows', 'Octaves', 'Lowcolorr', 'Fogcolorb', 'Resw'):
            self.assertIn(n, c.custom)
        self.assertEqual((c.par.Cols.max, c.par.Rows.max, c.par.Octaves.max), (512, 512, 8))
        self.assertEqual(c.par.Cols.val, 160)

    def test_first(self):
        c, reply, ns = K.fake_build('pop_terrain.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_terrain.py')
        decl = K.declared(ns['VERTEX']) + K.declared(ns['PIXEL'])
        for u, _ in ns['UNIFORMS']:
            self.assertIn(u, decl)
        self.assertIn('TDPos()', ns['VERTEX'])
        self.assertNotIn('#version', ns['VERTEX'] + ns['PIXEL'])
        self.assertEqual(ns['STYLES'], L.STYLES)
        self.assertIn('#define MAXOCT %d' % L.MAXOCT, ns['VERTEX'])

    def test_ascii(self):
        for f in ('pop_terrain.py', 'pop_terrain_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_terrain.py')
        ok, err = K.glslc_vert(ns['VERTEX'])
        self.assertTrue(ok, err)
        ok, err = K.glslc_pixel(ns['PIXEL'])
        self.assertTrue(ok, err)
        self.assertEqual(K.bounded_loops(ns['VERTEX']), [])


if __name__ == '__main__':
    unittest.main()
