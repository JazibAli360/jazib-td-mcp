"""Offline tests for builders/pop_branching.py + pop_branching_logic.py (lane H TC-10; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_branching.py'"""
import math
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_branching_logic as L  # noqa: E402

SMALL = dict(simw=120, simh=200)


class Logic(unittest.TestCase):
    def test_seed(self):
        T, n = L.seed_tips(L.params(**SMALL))
        self.assertEqual(n, 8)
        self.assertTrue(np.allclose(T[:, :2], [60, 100]))
        T, n = L.seed_tips(L.params(seedmode='bottom', seedcount=4, **SMALL))
        self.assertTrue(np.allclose(T[:, 0], [15, 45, 75, 105]) and np.allclose(T[:, 2], math.pi / 2))

    def test_alloc_exact(self):
        p = L.params(maxtips=10, splitangle=10.0)
        T = np.array([[1, 1, 0.0, 3.25], [2, 2, 0.0, -1.0], [3, 3, 0.0, 5.0], [4, 4, 1.0, 0.25]])
        out, n = L.alloc(T, 4, p)
        sa = math.radians(10)
        ref = np.array([[1, 1, sa, 3], [3, 3, 0, 5], [4, 4, 1 + sa, 0], [1, 1, -sa, 0], [4, 4, 1 - sa, 0]])
        self.assertEqual(n, 5)
        self.assertTrue(np.allclose(out, ref))
        out, n = L.alloc(T, 4, L.params(maxtips=4, splitangle=10.0))      # cap: survivors first, 1 child fits
        self.assertEqual(n, 4)
        self.assertTrue(np.allclose(out, ref[:4]))

    def test_alloc_many_chunks(self):
        rng = np.random.default_rng(2)
        n = 3500
        T = np.zeros((n, 4))
        T[:, 3] = rng.choice([-1.0, 4.0, 4.25], n)
        out, cnt = L.alloc(T, n, L.params(maxtips=4096))
        alive = T[:, 3] >= 0
        split = T[:, 3] == 4.25
        self.assertEqual(cnt, min(alive.sum() + split.sum(), 4096))

    def test_tips_steer_and_die(self):
        p = L.params(wander=0.0, splitrate=0.0, **SMALL)
        Tr = np.zeros((200, 120, 4))
        T = np.array([[60.5, 100.5, 0.0, 0.0]])
        Tr[100, 66, 0] = 1.0                          # trail straight ahead: turn (left = right = 0 -> right)
        o = L.tips(T, 1, 1, Tr, p)
        self.assertAlmostEqual(o[0, 2], -math.radians(20))
        Tr[100, 66, 0] = 5.0                          # above Killthresh: dies
        self.assertEqual(L.tips(T, 1, 1, Tr, p)[0, 3], -1.0)
        o = L.tips(np.array([[0.2, 100.5, math.pi, 0.0]]), 1, 1, np.zeros((200, 120, 4)), p)
        self.assertEqual(o[0, 3], -1.0)               # walks off the left edge (sensor ahead is the wall too)

    def test_trail_closed_form(self):
        for diffuse in (0.0, 0.5):
            p = L.params(diffuse=diffuse, splitrate=0.05, maxtips=512, **SMALL)
            T, cnt, Tr, counts, sums = L.run(80, p)
            cf = L.closed_form_sums(counts, p)
            self.assertTrue(np.allclose(sums, cf, rtol=1e-9), diffuse)
            self.assertTrue(np.isfinite(Tr).all())
            self.assertGreater(max(counts), 8)

    def test_deterministic_and_capped(self):
        p = L.params(splitrate=0.2, maxtips=64, **SMALL)
        a = L.run(60, p)
        b = L.run(60, p)
        self.assertEqual(a[3], b[3])
        self.assertLessEqual(max(a[3]), 64)
        c = L.run(60, p, np.float32)
        self.assertTrue(np.isfinite(c[0]).all())

    def test_play_off_holds(self):
        T, n = L.seed_tips(L.params(**SMALL))
        self.assertTrue(np.array_equal(L.tips(T, n, 3, np.zeros((200, 120, 4)), L.params(play=0, **SMALL)), T))


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_branching.py')
        o = c.ops
        for n in ('in1', 'br_pulses', 'state_blank', 'trail_blank', 'state_fb', 'trail_fb', 'tips', 'alloc',
                  'trail', 'look', 'out_sel', 'out1'):
            self.assertIn(n, o)
        for n in ('pts', 'dep_mat', 'dep_geo', 'dep_cam', 'deposit'):                # gathered in trail (27 Oct)
            self.assertNotIn(n, o)
        self.assertEqual([K.src(o['tips'], 0), K.src(o['tips'], 1)], ['state_fb', 'trail_fb'])
        self.assertEqual(K.src(o['alloc'], 0), 'tips')
        self.assertEqual(o['state_fb'].par.top.val, 'alloc')
        self.assertEqual(o['trail_fb'].par.top.val, 'trail')
        self.assertEqual([K.src(o['trail'], 0), K.src(o['trail'], 1)], ['trail_fb', 'alloc'])
        self.assertEqual(K.uniform_names(o['trail']), [u for u, _ in ns['TRAIL_U'] + ns['DEP_U']])
        self.assertEqual([K.src(o['look'], 0), K.src(o['look'], 1)], ['trail', 'in1'])
        al = o['alloc']
        self.assertFalse(al.par.autodispatchsize.val)
        self.assertEqual((al.par.dispatchsizex.val, al.par.dispatchsizey.val, al.par.dispatchsizez.val), (1, 1, 1))
        self.assertEqual(o['trail'].par.format.val, 'rgba32float')
        self.assertEqual((o['tips'].par.resolutionw.expr, o['tips'].par.resolutionh.expr), ('64', '65'))
        compile(o['br_pulses'].text, 'pulses', 'exec')
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        self.assertEqual(c.par.Maxtips.max, 4096)

    def test_first(self):
        c, reply, ns = K.fake_build('pop_branching.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_branching.py')
        for t in (ns['TIPS'], ns['ALLOC']):
            for u, _ in ns['SIM_U']:
                self.assertIn(u, K.declared(t))
        for u, _ in ns['TRAIL_U'] + ns['DEP_U']:
            self.assertIn(u, K.declared(ns['TRAIL']))

    def test_ascii(self):
        for f in ('pop_branching.py', 'pop_branching_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_branching.py')
        for n in ('TIPS', 'ALLOC', 'TRAIL', 'LOOK'):
            ok, err = K.glslc_compute(ns[n])
            self.assertTrue(ok, n + '\n' + err)
            self.assertEqual(K.bounded_loops(ns[n]), [], n)


if __name__ == '__main__':
    unittest.main()
