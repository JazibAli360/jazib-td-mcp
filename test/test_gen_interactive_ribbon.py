"""Offline tests for GEN_interactive module 'ribbon' (builders/gen_interactive_ribbon.py, _logic.py,
glsl/gen_interactive_ribbon_*.glsl). cd jazib-td-mcp && python3 -I -m unittest discover -s test -p
'test_gen_interactive_ribbon.py'"""
import math
import os
import unittest

import numpy as np

import test_gen_interactive as K

M = K.module('ribbon')
L = {}
with open(os.path.join(K.B, 'gen_interactive_ribbon_logic.py')) as _fh:
    exec(_fh.read(), L)
W, H = 1080, 1920


def P(**over):
    d = L['defaults']()
    d.update(over)
    return d


def line_pts(k, n=1, speed=0.004):
    """n points moving right at `speed` frame-widths per frame, at heights 0.3, 0.5, ..."""
    return [(0.1 + speed * k, 0.3 + 0.2 * i, 0.0, 0.0) for i in range(n)]


class Defaults(unittest.TestCase):
    def test_logic_defaults_match_pages(self):
        pd = K.RACK['page_defaults'](M['PAGES'])
        d = L['defaults']()
        for k, v in pd.items():
            if k == 'Resetcount':
                continue
            base = k[:-1] if k not in d and k[:-1] in d else k
            if base != k:
                self.assertAlmostEqual(d[base]['rgb'.index(k[-1])], v, msg=k)
            else:
                self.assertIn(k, d)
                self.assertEqual(d[k], v, k)


class Hist(unittest.TestCase):
    def test_fresh_first_sample_and_same_frame(self):
        st = L['hist_step'](None, line_pts(0), 100.0, 1.0, 1.0, 0.0, 2, 8, 0, W, H)
        self.assertEqual(st.shape, (3, 8, 4))
        self.assertEqual(st[2, 0, 0], 0)                        # head 0 after the first sample
        self.assertAlmostEqual(st[0, 0, 0], 0.1 * W)
        self.assertAlmostEqual(st[0, 0, 1], 0.3 * H)
        self.assertEqual(st[0, 0, 3], 1.0)
        self.assertEqual(st[1, 0, 3], 0.0)                      # point 1 absent (only one point given)
        st2 = L['hist_step'](st, line_pts(5), 100.0, 1.0, 1.0, 0.0, 2, 8, 0, W, H)
        self.assertTrue(np.array_equal(st, st2))                # same absTime: hold

    def test_ring_wraps_and_counts(self):
        st = None
        for k in range(11):
            st = L['hist_step'](st, line_pts(k), 100.0 + k / 60.0, 1.0, 1.0, 0.0, 1, 4, 0, W, H)
        self.assertEqual(st[1, 0, 0], 10 % 4)
        self.assertEqual(st[1, 1, 1], 11)
        self.assertAlmostEqual(st[1, 0, 1], 10 / 60.0, places=9)  # T = sum of dt
        self.assertAlmostEqual(st[0, 10 % 4, 0], (0.1 + 0.004 * 10) * W)

    def test_speed_zero_freezes_and_reset_clears(self):
        st = None
        for k in range(5):
            st = L['hist_step'](st, line_pts(k), 100.0 + k / 60.0, 1.0, 1.0, 0.0, 1, 8, 0, W, H)
        fz = L['hist_step'](st, line_pts(9), 101.0, 0.0, 1.0, 0.0, 1, 8, 0, W, H)
        self.assertTrue(np.array_equal(fz[0], st[0]))
        self.assertEqual(fz[1, 1, 1], st[1, 1, 1])
        rs = L['hist_step'](st, line_pts(9), 101.0, 1.0, 2.0, 0.0, 1, 8, 0, W, H)
        self.assertEqual(rs[1, 1, 1], 1)                        # new epoch: cleared, one sample
        self.assertEqual(rs[0, :, 3].sum(), 1)

    def test_sampleevery(self):
        st = None
        for k in range(60):
            st = L['hist_step'](st, line_pts(k), 100.0 + k / 60.0, 1.0, 1.0, 0.1, 1, 64, 0, W, H)
        self.assertIn(st[1, 1, 1], (9, 10, 11))                 # one sample per 0.1 s over ~1 s


class Segments(unittest.TestCase):
    def test_straight_line_continuous_constant_width(self):
        p = P(Ribbons=1, Length=16, Subdiv=3, Widthlaw=0, Width=10.0, Fade=0.0, Taper=0.0)
        st = L['run'](p, 12, line_pts)
        segs = L['segments'](st, p)
        self.assertEqual(len(segs), 11 * 3)
        for a, b in zip(segs, segs[1:]):
            self.assertAlmostEqual(a['p1'][0], b['p0'][0], places=6)   # joined (newest -> oldest)
            self.assertAlmostEqual(a['p1'][1], b['p0'][1], places=6)
        for s in segs:
            self.assertAlmostEqual(s['w0'], 10.0)
            self.assertEqual(s['a0'], 1.0)
            self.assertAlmostEqual(s['p0'][1], 0.3 * H, places=6)       # a straight line stays straight

    def test_speed_law_and_fade(self):
        p = P(Ribbons=1, Length=16, Subdiv=1, Widthlaw=1, Width=10.0, Speedref=600.0, Fade=1.0, Taper=0.0,
              Fadecurve=1.0)
        st = L['run'](p, 10, line_pts)
        segs = L['segments'](st, p)
        sp = 0.004 * W * 60.0                                           # px / s
        self.assertAlmostEqual(segs[2]['w0'], 10.0 * sp / 600.0, places=6)
        self.assertAlmostEqual(segs[0]['a0'], 1.0)                      # newest sample age 0
        self.assertAlmostEqual(segs[3]['a0'], 1.0 - 3 / 60.0, places=6)
        p2 = dict(p, Widthlaw=2)
        self.assertAlmostEqual(L['segments'](st, p2)[2]['w0'], 10.0 / (1 + sp / 600.0), places=6)

    def test_strands_symmetric_and_pen_up(self):
        p = P(Ribbons=1, Length=8, Subdiv=1, Strands=3, Spread=5.0, Widthlaw=0, Width=10.0, Fade=0.0)
        st = L['run'](p, 6, line_pts)
        segs = L['segments'](st, p)
        ys = sorted(set(round(s['p0'][1], 6) for s in segs))
        self.assertEqual(len(ys), 3)
        self.assertAlmostEqual(ys[1], 0.3 * H)
        self.assertAlmostEqual(ys[2] - ys[1], 5.0)
        gap = L['run'](p, 6, lambda k: line_pts(k) if k != 3 else [(-10.0, -10.0, 0.0, 0.0)])
        self.assertEqual(len(L['segments'](gap, dict(p, Strands=1))), 3)  # samples 0-2 and 4-5: 2 + 1 segments

    def test_drive_boosts_width(self):
        p = P(Ribbons=1, Length=8, Subdiv=1, Widthlaw=0, Width=10.0, Fade=0.0, Audiogain=1.0, Manual=0.5)
        st = L['run'](p, 4, line_pts)
        s = L['segments'](st, p, drive=(0.0, 120.0, 0.5, 0.0))
        self.assertAlmostEqual(s[0]['w0'], 10.0 * 2.0)


class Draw(unittest.TestCase):
    def _area(self, segs, p, x0, x1, y0, y1):
        ys, xs = np.mgrid[y0:y1, x0:x1]
        _c, a = L['shade_grid'](xs + 0.5, ys + 0.5, segs, p)
        return float(a.sum())

    def test_capsule_area(self):
        p = P(Style=0, Glow=0.0)
        seg = {'p0': (100.0, 100.0), 'p1': (180.0, 100.0), 'w0': 12.0, 'w1': 12.0, 'a0': 1.0, 'a1': 1.0,
               'rgb': (1.0, 1.0, 1.0)}
        want = 80 * 12 + math.pi * 36
        self.assertAlmostEqual(self._area([seg], p, 80, 200, 80, 120), want, delta=0.01 * want)
        two = [dict(seg, p1=(140.0, 100.0)), dict(seg, p0=(140.0, 100.0))]
        self.assertAlmostEqual(self._area(two, p, 80, 200, 80, 120), want, delta=0.01 * want)  # solid: no seam
        ys, xs = np.mgrid[80:120, 80:200]
        cs, _a = L['shade_grid'](xs + 0.5, ys + 0.5, two, p)
        cl, _a = L['shade_grid'](xs + 0.5, ys + 0.5, two, dict(p, Style=1))
        self.assertAlmostEqual(float(cl.sum() - cs.sum()), 3 * math.pi * 36, delta=0.03 * 3 * math.pi * 36)  # caps add

    def test_scalar_and_grid_agree(self):
        p = P(Style=2, Glow=0.5, Edge=3.0)
        segs = [{'p0': (10.0, 10.0), 'p1': (40.0, 30.0), 'w0': 8.0, 'w1': 14.0, 'a0': 1.0, 'a1': 0.5,
                 'rgb': (0.2, 0.5, 1.0)}]
        for x, y in ((20.5, 17.5), (5.5, 9.5), (40.5, 37.5)):
            c1, a1 = L['shade'](x, y, segs, p)
            c2, a2 = L['shade_grid'](np.array([x]), np.array([y]), segs, p)
            self.assertAlmostEqual(a1, float(a2[0]))
            self.assertTrue(np.allclose(c1, c2[0]))

    def test_every_preset_draws(self):
        for slot, name, vals in M['PRESETS']:
            p = dict(L['defaults']())
            for k, v in vals.items():
                if k[:-1] in ('Colora', 'Colorb') and k not in p:
                    c = list(p[k[:-1]])
                    c['rgb'.index(k[-1])] = v
                    p[k[:-1]] = tuple(c)
                else:
                    p[k] = v
            p['Ribbons'] = min(int(p['Ribbons']), 2)
            p['Length'] = min(int(p['Length']), 24)
            st = L['run'](p, 20, lambda k: L['gi']()['demo_points'](k / 60.0 * 3, 2, 0, 1) and
                          [(x, y, 0.0, 0.0) for x, y in L['gi']()['demo_points'](k / 60.0 * 3, 2, 0, 1)],
                          W=270, H=480)
            src = np.full((480, 270, 4), 0.5)
            segs = L['segments'](st, p, src=src)
            self.assertGreater(len(segs), 0, name)
            ys, xs = np.mgrid[0:480:4, 0:270:4]
            _c, a = L['shade_grid'](xs + 0.5, ys + 0.5, segs, p)
            self.assertGreater(float(a.sum()), 1.0, name)


class Shader(unittest.TestCase):
    def test_uniform_lists(self):
        tx = M['shader_texts']()
        K.check_uniforms(self, tx['hist'], M['hist_uniforms'](), 'hist')
        K.check_uniforms(self, tx['segs'], M['segs_uniforms'](), 'segs')
        K.check_uniforms(self, tx['fx'], M['draw_uniforms'](), 'fx')
        K.check_uniforms(self, tx['cbox'], [], 'cbox')

    def test_sizes(self):
        self.assertEqual(K.ev(M['HIST_W'], M), 96)
        self.assertEqual(K.ev(M['HIST_H'], M), 9)
        self.assertEqual(K.ev(M['SEGS_W'], M), 3 * 95 * 3)
        self.assertEqual(K.ev(M['SEGS_H'], M), 8)
        self.assertEqual(K.ev(M['SEGS_W'], M, {'Length': 4, 'Subdiv': 1}), 9)

    def test_chunk_boxes(self):
        p = P(Ribbons=2, Length=40, Subdiv=4, Strands=2, Widthlaw=0, Width=10.0, Fade=0.0)
        st = L['run'](p, 40, lambda k: line_pts(k, 2))
        segs = L['segments'](st, p)
        total = 39 * 4 * 4
        self.assertEqual(K.ev(M['CBOX_W'], M, {'Ribbons': 2, 'Length': 40, 'Subdiv': 4, 'Strands': 2}), 3)
        bx = L['chunk_boxes'](segs, total)
        self.assertEqual(len(bx), 3)
        for s in segs:                                          # every segment inside its chunk's box
            b = bx[s['g'] // 256]
            for q in (s['p0'], s['p1']):
                self.assertTrue(b[0] <= q[0] - 5 + 1e-9 and q[0] + 5 <= b[2] + 1e-9 and b[1] <= q[1] - 5 + 1e-9)
        self.assertEqual(len(set(s['g'] for s in segs)), len(segs))
        self.assertTrue(all(0 <= s['g'] < total for s in segs))

    def test_draw_shared_memory(self):
        self.assertLess(K.shared_bytes(M['shader_texts']()['fx']), 16384)


if __name__ == '__main__':
    unittest.main()
