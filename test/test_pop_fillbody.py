"""Offline tests for builders/pop_fillbody.py + pop_fillbody_logic.py (lane H TC-15; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_fillbody.py'"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_fillbody_logic as L  # noqa: E402

for _c in ('renderselectTOP', 'switchCHOP'):
    if _c not in K.TD_CLASSES:
        K.TD_CLASSES.append(_c)


class Logic(unittest.TestCase):
    def test_dancer_shape(self):
        caps = L.dancer(0.0, 0.0)
        self.assertEqual(len(caps), L.DANCER_CAPS)
        A, B = L.caps_table(L.params(tb=0.3))
        self.assertTrue((B[:12, 3] == 1).all() and (B[12:, 3] == 0).all())
        lo, hi = L.bbox(A, B, 12)
        self.assertLess(hi[1] - lo[1], 1.0)                                   # fits the 1-unit-tall frame
        self.assertGreater(lo[1], -0.5)
        self.assertLess(hi[1], 0.5)
        a0, _ = L.caps_table(L.params(tb=0.3, pose=1.0))
        a1, _ = L.caps_table(L.params(tb=0.7, pose=1.0))
        self.assertGreater(np.abs(a0 - a1).max(), 0.01)                       # it moves
        b0, _ = L.caps_table(L.params(tb=0.3, pose=0.0))
        b1, _ = L.caps_table(L.params(tb=0.7, pose=0.0))
        self.assertTrue(np.allclose(b0, b1))                                  # pose 0 = standing still

    def test_capsule_sdf(self):
        A, B = np.zeros((16, 4)), np.zeros((16, 4))
        A[0] = [0, 0, 0, 0.1]
        B[0] = [0, 1, 0, 1]
        P = np.array([[0.0, 0.5, 0.0], [0.3, 0.5, 0.0], [0.0, -0.2, 0.0], [0.0, 1.3, 0.0]])
        self.assertTrue(np.allclose(L.sdf(P, A, B, 1), [-0.1, 0.2, 0.1, 0.2]))
        g = L.grad(np.array([[0.3, 0.5, 0.0]]), A, B, 1)
        self.assertTrue(np.allclose(g, [[1, 0, 0]], atol=1e-6))
        self.assertEqual(L.sdf(P, A, B, 0).min(), 1e9)                        # no capsules = empty body

    def test_chop_rows(self):
        rows = np.array([[0, 0, 0, 0.1], [0, 0.2, 0, 0], [0.1, 0, 0, 0.05], [0.1, 0.1, 0, 0]])
        A, B = L.caps_table(L.params(origin=(0.0, 0.0, 0.0), scale=2.0), rows)
        self.assertTrue(np.allclose(A[1], [0.2, 0, 0, 0.1]) and np.allclose(B[1], [0.2, 0.2, 0, 1]))
        self.assertEqual(B[2:, 3].sum(), 0)

    def test_spawn_inside_and_stays(self):
        p = L.params(count=1500)
        P, V, A, B, nc = L.run(p, 0)
        self.assertGreaterEqual(L.inside_fraction(P, A, B, nc, 1500), 0.99)
        P, V, A, B, nc = L.run(p, 45, dance=0.5)
        self.assertGreaterEqual(L.inside_fraction(P, A, B, nc, 1500), 0.99)
        self.assertTrue(np.isfinite(P).all() and np.isfinite(V).all())
        self.assertTrue((P[:1500, 3] > 0).all())                              # drawn
        self.assertGreater(np.abs(V[:1500, :3]).max(), 1e-4)                  # they move

    def test_bound_to_birth_capsule(self):
        # 27 Oct look finding: projecting onto the NEAREST capsule drained the swarm into the feet while dancing.
        # Now each particle keeps the capsule it was born in (P.w = k + phase): shares stay put, all inside.
        n = 1024
        p = L.params(count=n)
        P0, _V, A0, B0, nc = L.run(p, 0)
        k0 = np.floor(P0[:n, 3]).astype(int)
        self.assertGreater((k0 == L.owner(P0[:n, :3], A0, B0, nc)).mean(), 0.99)   # rest: fallback a of i % nc
        P, V, A, B, nc = L.run(p, 300, dance=0.5)
        k = np.floor(P[:n, 3]).astype(int)
        self.assertTrue(((k >= 0) & (k < nc)).all())
        s0, s1 = np.bincount(k0, minlength=nc) / n, np.bincount(k, minlength=nc) / n
        self.assertLess(np.abs(s1 - s0).max(), 0.03)
        d, _ = L.cap_sdf(P[:n, :3], A, B, k)
        self.assertLessEqual(d.max(), 1e-9)                                  # inside its own capsule
        self.assertEqual(L.inside_fraction(P, A, B, nc, n), 1.0)
        frac = P[:n, 3] - k
        self.assertTrue(((frac >= 0.5) & (frac < 1.0)).all())               # phase kept

    def test_reproducible(self):
        p = L.params(count=400)
        a = L.run(p, 10)[0]
        b = L.run(p, 10)[0]
        self.assertTrue(np.array_equal(a, b))

    def test_dead_slots(self):
        P, V, A, B, nc = L.run(L.params(count=10), 2)
        self.assertTrue((P[10:16, 3] == -1).all())


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_fillbody.py')
        o = c.ops
        for n in ('in1', 'clock', 'reset_exec', 'caps_in', 'caps_default', 'caps_sel', 'caps_chop', 'state', 'state_v', 'pts', 'mat', 'geo', 'cam', 'render', 'look', 'out_sel',
                  'out1'):
            self.assertIn(n, o)
        self.assertNotIn('caps', o)                                   # merged into state (perf wave 27 Oct)
        self.assertEqual([K.src(o['caps_sel'], 0), K.src(o['caps_sel'], 1)], ['caps_default', 'caps_in'])
        st = o['state']
        self.assertEqual((st.par.array0name.val, st.par.array0chop.val, st.par.array0arraytype.val),
                         ('uCaps', 'caps_chop', 'texturebuffer'))
        self.assertEqual((st.par.numcolorbufs.val, st.par.outputaccess.val, st.par.clearoutputs.val),
                         (2, 'readwrite', False))
        self.assertEqual(K.uniform_names(st), [u for u, _ in ns['STATE_SPEC']])
        self.assertEqual([K.src(o['out_sel'], 0), K.src(o['out_sel'], 1)], ['in1', 'look'])
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])

    def test_first(self):
        c, reply, ns = K.fake_build('pop_fillbody.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_fillbody.py')
        for text, spec in ((ns['STATE'], ns['STATE_SPEC']),):
            d = K.declared(text)
            for u, _ in spec:
                self.assertIn(u, d)
        self.assertIn('uniform samplerBuffer uCaps;', ns['STATE'])
        self.assertNotIn('sTD2DInputs', ns['STATE'])                  # no inputs since caps merged

    def test_ascii(self):
        for f in ('pop_fillbody.py', 'pop_fillbody_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_fillbody.py')
        for text in (ns['STATE'], ns['LOOK']):
            ok, err = K.glslc_compute(text)
            self.assertTrue(ok, err)
            self.assertEqual(K.bounded_loops(text), [])
        ok, err = K.glslc_vert(ns['POINTS_VERTEX'])
        self.assertTrue(ok, err)
        ok, err = K.glslc_pixel(ns['POINTS_PIXEL'])
        self.assertTrue(ok, err)


if __name__ == '__main__':
    unittest.main()
