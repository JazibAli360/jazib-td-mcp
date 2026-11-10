"""Offline tests for GEN_interactive module 'pigment' (builders/gen_interactive_pigment.py, _logic.py,
glsl/gen_interactive_pigment_*.glsl). cd jazib-td-mcp && python3 -I -m unittest discover -s test -p
'test_gen_interactive_pigment.py'"""
import math
import os
import unittest

import numpy as np

import test_gen_interactive as K

M = K.module('pigment')
L = {}
with open(os.path.join(K.B, 'gen_interactive_pigment_logic.py')) as _fh:
    exec(_fh.read(), L)
W, H = 270, 480


def P(**over):
    d = L['defaults']()
    d.update(over)
    return d


def preset_pars(vals):
    p = L['defaults']()
    for k, v in vals.items():
        if k[:-1] in ('Colora', 'Colorb') and k not in p:
            c = list(p[k[:-1]])
            c['rgb'.index(k[-1])] = v
            p[k[:-1]] = tuple(c)
        else:
            p[k] = v
    return p


class Defaults(unittest.TestCase):
    def test_logic_defaults_match_pages(self):
        d = L['defaults']()
        for k, v in K.RACK['page_defaults'](M['PAGES']).items():
            if k == 'Resetcount':
                continue
            if k not in d:
                self.assertAlmostEqual(d[k[:-1]]['rgb'.index(k[-1])], v, msg=k)
            else:
                self.assertEqual(d[k], v, k)


class Field(unittest.TestCase):
    def test_curl_divergence_free(self):
        p = P(Flowscale=100.0, Octaves=3)
        ys, xs = np.mgrid[100:140, 100:140].astype(float)
        e = 0.01 * 100.0                                                 # the curl's own step (0.01 noise units)
        ux = L['curl'](xs + e, ys, 0.0, p)[0] - L['curl'](xs - e, ys, 0.0, p)[0]
        vy = L['curl'](xs, ys + e, 0.0, p)[1] - L['curl'](xs, ys - e, 0.0, p)[1]
        div = (ux + vy) / (2 * e)                                        # discrete divergence on the same stencil
        mag = np.hypot(*L['curl'](xs, ys, 0.0, p)).mean() / 100.0       # per px
        self.assertGreater(mag, 1e-4)
        self.assertLess(np.abs(div).max(), 1e-9 * max(mag, 1.0))

    def test_evolve_changes_field(self):
        p = P(Evolve=0.5)
        a = np.array(L['curl'](50.0, 60.0, 0.0, p))
        b = np.array(L['curl'](50.0, 60.0, 2.0, p))
        self.assertGreater(np.abs(a - b).max(), 1e-3)
        self.assertTrue(np.allclose(L['curl'](50.0, 60.0, 2.0, dict(p, Evolve=0.0)), L['curl'](50.0, 60.0, 0.0, p)))

    def test_points_push_attract_swirl(self):
        pts = [(0.5, 0.5, 0.0, 0.0)]
        base = P(Flowstrength=0.0, Pointforce=100.0, Radius=50.0, Pointvel=0.0)
        x, y = 0.5 * W + 10.0, 0.5 * H
        vx, vy = L['velocity'](x, y, 0.0, dict(base, Pointmode=0), pts, None, W, H)
        self.assertAlmostEqual(float(vx), 100.0 * 0.8 ** 2)
        self.assertAlmostEqual(float(vy), 0.0)
        vx, _ = L['velocity'](x, y, 0.0, dict(base, Pointmode=1), pts, None, W, H)
        self.assertLess(float(vx), 0)
        vx, vy = L['velocity'](x, y, 0.0, dict(base, Pointmode=2), pts, None, W, H)
        self.assertAlmostEqual(float(vx), 0.0)
        self.assertGreater(float(vy), 0)
        far = L['velocity'](x + 100, y, 0.0, base, pts, None, W, H)
        self.assertEqual(float(far[0]), 0.0)
        absent = L['velocity'](x, y, 0.0, base, [(-10.0, -10.0, 0.0, 0.0)], None, W, H)
        self.assertEqual(float(absent[0]), 0.0)
        drag = L['velocity'](x, y, 0.0, dict(base, Pointforce=0.0, Pointvel=1.0), [(0.5, 0.5, 0.1, 0.0)], None, W, H)
        self.assertAlmostEqual(float(drag[0]), 0.64 * 0.1 * W)

    def test_mask_attract_and_flowtop(self):
        field = np.zeros((48, 27, 4))
        field[:, 14:, 0] = 1.0                                           # presence on the right half
        p = P(Flowstrength=0.0, Pointforce=0.0, Fieldsource=0, Maskforce=50.0)
        vx, _ = L['velocity'](0.5 * W + 0.5, 0.5 * H, 0.0, p, (), field, W, H)
        self.assertGreater(float(vx), 0)                                 # toward the presence
        vx2, _ = L['velocity'](0.5 * W + 0.5, 0.5 * H, 0.0, dict(p, Maskforce=-50.0), (), field, W, H)
        self.assertAlmostEqual(float(vx2), -float(vx))
        flow = np.zeros((48, 27, 4))
        flow[..., 0] = 2.0                                               # 2 cells/s at 48 rows
        vx, vy = L['velocity'](100.0, 100.0, 0.0, dict(p, Fieldsource=1, Flowgain=1.0), (), flow, W, H)
        self.assertAlmostEqual(float(vx), 2.0 * H / 48.0)
        self.assertAlmostEqual(float(vy), 0.0)


class State(unittest.TestCase):
    def test_fresh_staggered_and_hold(self):
        p = P(Side=16)
        st = L['state_step'](None, p, 100.0, 1.0, W, H)
        self.assertEqual(st.shape, (17, 32, 4))
        A = st[:16, 0::2]
        self.assertTrue(((A[..., 2] >= 0) & (A[..., 2] < A[..., 3])).all())
        self.assertGreater(A[..., 2].std(), 0.1)                          # ages spread
        self.assertTrue((A[..., 0] >= 0).all() and (A[..., 0] <= W).all())
        self.assertTrue(np.array_equal(L['state_step'](st, p, 100.0, 1.0, W, H), st))
        fz = L['state_step'](st, dict(p, Speed=0.0), 101.0, 1.0, W, H)
        self.assertTrue(np.array_equal(fz[:16], st[:16]))
        self.assertEqual(fz[16, 1, 0], 0.0)

    def test_advection_step(self):
        p = P(Side=8, Pointforce=0.0, Life=100.0, Lifevar=0.0)
        st = L['state_step'](None, p, 100.0, 1.0, W, H)
        st2 = L['state_step'](st, p, 100.0 + 1 / 60.0, 1.0, W, H)
        A, A2 = st[:8, 0::2], st2[:8, 0::2]
        vx, vy = L['velocity'](A[..., 0], A[..., 1], 1 / 60.0, p, (), None, W, H)
        self.assertTrue(np.allclose(A2[..., 0], A[..., 0] + vx / 60.0))
        self.assertTrue(np.allclose(A2[..., 2], A[..., 2] + 1 / 60.0))
        self.assertTrue(np.allclose(st2[:8, 1::2][..., 3], np.hypot(vx, vy)))
        self.assertAlmostEqual(st2[8, 0, 1], 1 / 60.0)

    def test_respawn_new_seed_and_morph(self):
        p = P(Side=8, Life=0.05, Lifevar=0.0, Flowstrength=0.0, Pointforce=0.0)
        st = L['state_step'](None, p, 100.0, 1.0, W, H)
        seeds = st[:8, 1::2][..., 2].copy()
        for k in range(1, 5):
            st = L['state_step'](st, p, 100.0 + k / 60.0, 1.0, W, H)
        self.assertGreater((st[:8, 1::2][..., 2] != seeds).mean(), 0.9)
        self.assertTrue((st[:8, 0::2][..., 2] < 0.05 + 1e-9).all())
        pm = P(Side=8, Life=100.0, Flowstrength=200.0, Pointforce=0.0, Morph=60.0)
        st = L['state_step'](None, pm, 100.0, 1.0, W, H)
        st = L['state_step'](st, pm, 100.0 + 1 / 60.0, 1.0, W, H)
        self.assertTrue(np.allclose(st[:8, 1::2][..., :2], st[:8, 0::2][..., :2]))   # Morph x dts = 1: follows

    def test_spawn_modes(self):
        s = np.linspace(0.01, 0.99, 64)
        x, y, life = L['spawn'](s, P(Spawnmode=3), W, H)
        self.assertTrue((y <= 0.02 * H).all())
        x, y, _ = L['spawn'](s, P(Spawnmode=1, Radius=10.0), W, H, [(0.25, 0.75, 0, 0)])
        self.assertTrue((np.hypot(x - 0.25 * W, y - 0.75 * H) <= 10.0 + 1e-9).all())
        field = np.zeros((48, 27, 4))
        field[:24, :, 0] = 1.0                                           # presence in the bottom half
        x, y, _ = L['spawn'](s, P(Spawnmode=2, Fieldsource=0), W, H, (), field)
        self.assertGreater((y < 0.5 * H).mean(), 0.85)
        self.assertTrue((life >= 0.05).all())

    def test_edge_wrap(self):
        p = P(Side=8, Flowstrength=0.0, Pointforce=0.0, Edge=1, Life=100.0)
        st = L['state_step'](None, p, 100.0, 1.0, W, H)
        st[:8, 0::2][..., 0] = W + 100.0
        st2 = L['state_step'](st, p, 100.0 + 1 / 60.0, 1.0, W, H)
        self.assertTrue((st2[:8, 0::2][..., 0] < W).all())


class Render(unittest.TestCase):
    def test_splat_coverage_and_colour(self):
        p = P(Side=8, Size=2.0, Quality=1.0, Agefade=0.0, Colormode=0)
        st = L['state_step'](None, p, 100.0, 1.0, W, H)
        src = np.zeros((H, W, 4))
        src[..., 1] = 0.75
        sp = L['splat'](st, p, src, W, H)
        self.assertEqual(sp.shape, (H, W, 4))
        A = st[:8, 0::2].reshape(-1, 4)
        cx = np.floor(A[:, 0]).astype(int)
        cy = np.floor(A[:, 1]).astype(int)
        ok = (cx >= 0) & (cy >= 0) & (cx < W) & (cy < H)
        self.assertTrue((sp[cy[ok], cx[ok], 3] == 1.0).all())
        self.assertTrue(np.allclose(sp[cy[ok], cx[ok], 1], 0.75))
        self.assertLessEqual(int((sp[..., 3] > 0).sum()), 64 * 4)
        q = L['splat'](st, dict(p, Quality=0.5), src, W, H)
        self.assertEqual(q.shape, (240, 135, 4))

    def test_atlas_cells(self):
        p = P(Side=8, Colormode=1, Atlascells=2, Atlasrate=0.0, Quality=1.0, Agefade=0.0)
        atlas = np.zeros((40, 40, 4))
        atlas[:20, :20, 0] = 1.0                                         # cell 0 red, others black
        st = L['state_step'](None, p, 100.0, 1.0, W, H)
        st[:8, 1::2][..., 2] = 0.1                                       # seed -> cell floor(0.4) = 0, f = 0.4
        sp = L['splat'](st, p, atlas, W, H)
        lit = sp[..., 3] > 0
        f = 0.4 * 0.4 * (3 - 0.8)
        self.assertAlmostEqual(float(np.median(sp[lit][:, 0])), 1 - f, places=6)   # interior of cell 0 (edges blend)

    def test_trail(self):
        sp = np.zeros((4, 4, 4))
        sp[1, 1] = [1.0, 0.5, 0.0, 1.0]
        p = P(Trail=1.0, Trailmode=0)
        t1 = L['trail_step'](sp, None, 0.5, p)
        t2 = L['trail_step'](np.zeros(sp.shape), t1, 0.5, p)
        self.assertTrue(np.allclose(t2[1, 1], sp[1, 1] * math.exp(-0.5)))
        self.assertTrue(np.array_equal(L['trail_step'](np.zeros(sp.shape), t1, 0.0, p), t1))   # frozen holds
        self.assertTrue(np.allclose(L['trail_step'](sp, t1, 0.5, dict(p, Trailmode=1))[1, 1],
                                    sp[1, 1] * (1 + math.exp(-0.5))))
        self.assertEqual(L['trail_step'](sp, t1, 0.5, dict(p, Trail=0.0))[0, 0, 3], 0.0)

    def test_look_over_black(self):
        base = np.zeros((8, 8, 4))
        base[..., 3] = 1
        tr = np.zeros((4, 4, 4))
        tr[...] = [0.5, 0.25, 0.0, 1.0]
        o = L['look'](base, tr, P(Glow=0.0, Exposure=2.0, Blend=0), [(3, 3)])
        self.assertTrue(np.allclose(o[0], [1.0, 0.5, 0.0, 1.0]))

    def test_every_preset_draws(self):
        field = np.zeros((48, 27, 4))
        field[10:40, 5:22, 0] = 1.0
        field[..., 1] = 1.0
        for slot, name, vals in M['PRESETS']:
            p = preset_pars(vals)
            p['Side'] = 32
            pts_fn = lambda k: [(0.5 + 0.2 * math.sin(k / 10.0), 0.5, 0.2, 0.0)]
            st, tr = L['run'](p, 12, W, H, pts_fn=pts_fn, field=field,
                              colsrc=np.random.RandomState(1).rand(H, W, 4))
            self.assertGreater(float(tr[..., 3].sum()), 10.0, name)
            self.assertTrue(np.isfinite(st).all(), name)


class Shader(unittest.TestCase):
    def test_uniform_lists(self):
        tx = M['shader_texts']()
        K.check_uniforms(self, tx['state'], M['state_uniforms'](), 'state')
        K.check_uniforms(self, tx['splat'], M['splat_uniforms'](), 'splat')
        K.check_uniforms(self, tx['trail'], M['trail_uniforms'](), 'trail')
        K.check_uniforms(self, tx['fx'], M['look_uniforms'](), 'fx')

    def test_sizes_and_dispatch(self):
        self.assertEqual(K.ev(M['STATE_W'], M), 512)
        self.assertEqual(K.ev(M['STATE_H'], M), 257)
        self.assertEqual(K.ev(M['TRAIL_W'], M), 540)
        self.assertEqual(K.ev(M['TRAIL_H'], M), 960)
        self.assertEqual(K.ev(M['DISPATCH'], M), 32)
        self.assertEqual(K.ev(M['DISPATCH'], M, {'Side': 100}), 13)

    def test_constants_match(self):
        t = M['shader_texts']()['state']
        self.assertIn('#define MAXPTS %d' % L['MAXPTS'], t)
        self.assertIn('#define SB 16777216.0', t)


if __name__ == '__main__':
    unittest.main()
