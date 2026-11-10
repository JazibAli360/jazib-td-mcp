"""Offline tests for builders/pop_collide.py + pop_collide_logic.py (lane H TC-14; no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_pop_collide.py'"""
import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import pop_testkit as K  # noqa: E402
import pop_collide_logic as L  # noqa: E402

for _c in ('renderselectTOP',):
    if _c not in K.TD_CLASSES:
        K.TD_CLASSES.append(_c)

OPEN = dict(spheres=[(0.0, 0.0, 0.0, 0.0)] * 4, boxes=[((0.0, 0.0, 0.0), (0.1, 0.1, 0.1), 0)] * 2)


def run(p, frames, count=None):
    P, V = L.blank_state(count or p['count'])
    P, V = L.step(P, V, dict(p, reset=1))
    for f in range(frames):
        P, V = L.step(P, V, dict(p, reset=0, time=f / 60.0))
    return P, V


class Logic(unittest.TestCase):
    def test_bounce_apex(self):
        p = L.params(substeps=4, friction=0.0, **OPEN)
        s = L.test_series(p, 400)
        self.assertEqual([k for k, _, _ in s[:5]], [1, 2, 3, 4, 5])          # V.w = steps since reset
        h = p['testh'] - p['floory']
        a = [y - p['floory'] for y in L.apexes(s)]
        e2 = p['restitution'] ** 2
        self.assertLess(abs(a[0] - e2 * h) / (e2 * h), 0.03)
        self.assertLess(abs(a[1] - e2 * e2 * h) / (e2 * e2 * h), 0.05)
        self.assertGreaterEqual(min(y for _, y, _ in s), p['floory'] - 1e-12)

    def test_resting_on_sphere(self):
        p = L.params(substeps=2, spheres=[(0.0, -0.1, 0.0, 0.12)] + [(0, 0, 0, 0)] * 3,
                     boxes=OPEN['boxes'], restitution=0.0)
        s = L.test_series(p, 300)
        self.assertAlmostEqual(s[-1][1], 0.02, 3)                             # top of the sphere

    def test_floor_and_finite(self):
        p = L.params(count=2000)
        P, V = run(p, 240)
        live = P[:, 3] > 0
        self.assertTrue(np.isfinite(P).all() and np.isfinite(V).all())
        self.assertGreater(live.sum(), 1900)
        self.assertGreaterEqual(P[live, 1].min(), p['floory'] - 1e-9)
        for (cx, cy, cz, r) in p['spheres']:
            if r > 0:
                d = np.linalg.norm(P[live, :3] - [cx, cy, cz], axis=-1)
                self.assertGreaterEqual(d.min(), r - 1e-9)
        (c, hb, on) = p['boxes'][0]
        q = np.abs(P[live, :3] - c) - hb
        self.assertFalse((q < -1e-9).all(-1).any())

    def test_dead_and_count(self):
        P, V = run(L.params(count=10), 3, count=10)
        self.assertEqual(P.shape[0], 16)                                     # side 4
        self.assertTrue((P[10:, 3] == -1).all() and (P[10:, 1] == -1000).all())
        self.assertTrue((P[:10, 3] > 0).all())

    def test_reset_reproducible(self):
        p = L.params(count=300)
        a = run(p, 50)
        b = run(p, 50)
        self.assertTrue(np.array_equal(a[0], b[0]))
        P, V = L.step(a[0], a[1], dict(p, reset=1))                          # reset = spawn generation 1 again
        P0, V0 = L.step(*L.blank_state(300), dict(p, reset=1))
        self.assertTrue(np.allclose(P, P0) and np.allclose(V, V0))

    def test_respawn_after_life(self):
        p = L.params(count=50, life=0.2)
        P, V = run(p, 40)
        self.assertGreater(V[:50, 3].min(), 1.5)                             # every particle respawned

    def test_spawn_shapes(self):
        for sh in L.EMIT_SHAPES:
            pos, vel, life = L.spawn(np.arange(1000), np.ones(1000), L.params(emitshape=sh))
            off = pos - np.array(L.DEFAULTS['emit'])
            self.assertLessEqual(np.abs(off).max(), L.DEFAULTS['emitsize'] + 1e-12)
            self.assertTrue((life >= 3.0).all() and (life <= 9.0).all())

    def test_side(self):
        self.assertEqual(L.side_of(16384), 128)
        self.assertEqual(L.side_of(16385), 129)
        self.assertEqual(L.side_of(10 ** 9), 512)


class Builder(unittest.TestCase):
    def test_fake_build(self):
        c, reply, ns = K.fake_build('pop_collide.py')
        o = c.ops
        for n in ('in1', 'clock', 'reset_exec', 'state', 'state_compute', 'state_v', 'pts', 'mat', 'geo', 'cam',
                  'render', 'look', 'look_compute', 'out_sel', 'out1'):
            self.assertIn(n, o)
        self.assertEqual(o['reset_exec'].OPType, 'parameterexecuteDAT')
        st = o['state']
        self.assertEqual((st.par.mode.val, st.par.format.val, st.par.numcolorbufs.val, st.par.outputaccess.val,
                          st.par.clearoutputs.val), ('compute', 'rgba32float', 2, 'readwrite', False))
        self.assertEqual(st.inputs, [])
        self.assertEqual(K.uniform_names(st), [u for u, _ in ns['STATE_SPEC']])
        self.assertEqual((o['state_v'].par.top.val, o['state_v'].par.bufferindex.val), ('state', 1))
        self.assertEqual(o['pts'].par.surftype.val, 'points')
        m = o['mat']
        self.assertEqual([m.par.sampler0top.val, m.par.sampler1top.val], ['state', 'state_v'])
        self.assertEqual((m.par.srcblend.val, m.par.destblend.val, m.par.depthtest.val), ('one', 'one', False))
        self.assertEqual([K.src(o['look'], 0), K.src(o['look'], 1)], ['acc_sel', 'in1'])
        self.assertEqual([K.src(o['acc_sel'], k) for k in range(2)], ['render', 'acc'])
        self.assertEqual([K.src(o['acc'], k) for k in range(2)], ['render', 'acc_fb'])
        self.assertEqual(K.src(o['acc_fb'], 0), 'acc_blank')
        self.assertIn("'acc' if parent().par.Persist.eval() > 0", o['acc_fb'].par.top.expr)
        lk = o['look']
        self.assertEqual((lk.par.numcolorbufs.val, lk.par.outputaccess.val, lk.par.clearoutputs.val),
                         (1, 'writeonly', True))
        self.assertEqual((o['acc'].par.format.val, o['acc_blank'].par.format.val), ('rgba16float', 'rgba16float'))
        for k in ('LOOK', 'ACC'):
            self.assertNotIn('TDImageLoadOutput', ns[k])
        self.assertEqual(o['persist_exec'].par.pars.val, 'Persist')
        self.assertEqual([K.src(o['out_sel'], 0), K.src(o['out_sel'], 1)], ['in1', 'look'])
        K.check_exprs(self, c)
        self.assertEqual(reply['notes'], [])
        self.assertEqual(c.par.Count.max, L.COUNT_CAP)
        self.assertEqual(c.par.Count.val, 16384)

    def test_first(self):
        c, reply, ns = K.fake_build('pop_collide.py', first=True)
        for k, v in ns['FIRST'].items():
            self.assertEqual(getattr(c.par, k).val, v)
        self.assertEqual(reply['notes'], [])

    def test_uniforms_declared(self):
        _c, _r, ns = K.fake_build('pop_collide.py')
        for text, spec in ((ns['STATE'], ns['STATE_SPEC']), (ns['POINTS_VERTEX'], L.POINT_SPEC),
                           (ns['LOOK'], ns['LOOK_U']), (ns['ACC'], ns['ACC_U'])):
            d = K.declared(text)
            for u, _ in spec:
                self.assertIn(u, d)
        self.assertIn('TDPos()', ns['POINTS_VERTEX'])

    def test_ascii(self):
        for f in ('pop_collide.py', 'pop_collide_logic.py'):
            K.ascii_ok(os.path.join(K.BUILDERS, f))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        _c, _r, ns = K.fake_build('pop_collide.py')
        for text in (ns['STATE'], ns['LOOK'], ns['ACC']):
            ok, err = K.glslc_compute(text)
            self.assertTrue(ok, err)
            self.assertEqual(K.bounded_loops(text), [])
        ok, err = K.glslc_vert(ns['POINTS_VERTEX'])
        self.assertTrue(ok, err)
        ok, err = K.glslc_pixel(ns['POINTS_PIXEL'])
        self.assertTrue(ok, err)


if __name__ == '__main__':
    unittest.main()
