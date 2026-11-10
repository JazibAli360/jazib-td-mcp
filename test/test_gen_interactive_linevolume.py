"""Offline tests for GEN_interactive module 'linevolume' (builders/gen_interactive_linevolume.py, _logic.py,
glsl/gen_interactive_linevolume.glsl). cd jazib-td-mcp && python3 -I -m unittest discover -s test -p
'test_gen_interactive_linevolume.py'"""
import math
import os
import re
import shutil
import unittest

import numpy as np

import test_gen_interactive as K

M = K.module('linevolume')
L = {}
with open(os.path.join(K.B, 'gen_interactive_linevolume_logic.py')) as _fh:
    exec(_fh.read(), L)
W, H = 270, 480


def P(**over):
    d = L['defaults']()
    d.update(over)
    return d


def U(T=0.0, drive=(0.0, 120.0, 0.0, 0.0), **over):
    return L['uniforms'](P(**over), T, drive)


def cov(x, y, u, pts=None, mask=None, src=None, w=W, h=H):
    return L['shade'](x + 0.5, y + 0.5, u, w, h, pts, mask, src)[1]


def full_preset(vals):
    p = dict(L['defaults']())
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
        pd = K.RACK['page_defaults'](M['PAGES'])
        d = L['defaults']()
        for k, v in pd.items():
            if k == 'Resetcount':
                continue
            if k not in d and k[:-1] in d:
                self.assertAlmostEqual(d[k[:-1]]['rgb'.index(k[-1])], v, msg=k)
            else:
                self.assertEqual(d[k], v, k)

    def test_uniform_exprs_match_logic(self):
        T = 1.25 + 0.0                                          # ev's clock_int = 1.25, Phase 0
        want = L['uniforms'](L['defaults'](), T, (3.25, 120.0, 0.5, 0.0))
        for name, ex in M['uniforms']():
            if name in ('uLook', 'uCa', 'uCb'):
                continue
            got = [float(K.ev(e, M)) for e in ex]
            self.assertTrue(np.allclose(got, want[name], atol=1e-9), (name, got, want[name]))


class Solids(unittest.TestCase):
    def test_edge_counts_and_unit_radius(self):
        V, E, R = L['solid_table']()
        for s, (v0, nv, e0, ne) in zip(L['SOLIDS'], R):
            self.assertEqual(ne, L['EDGE_COUNTS'][s], s)
            self.assertEqual(nv, {'tetra': 4, 'cube': 8, 'octa': 6, 'icosa': 12, 'dodeca': 20}[s])
            self.assertEqual(nv - ne + {'tetra': 4, 'cube': 6, 'octa': 8, 'icosa': 20, 'dodeca': 12}[s], 2)  # Euler
            for v in V[v0:v0 + nv]:
                self.assertAlmostEqual(math.sqrt(sum(c * c for c in v)), 1.0)
            for a, b in E[e0:e0 + ne]:
                self.assertTrue(v0 <= a < v0 + nv and v0 <= b < v0 + nv)

    def test_glsl_table_matches(self):
        t = M['shader_texts']()['fx']
        self.assertNotIn('%SOLIDS%', t)
        V, E, R = L['solid_table']()
        self.assertIn('const vec3 LV_V[%d]' % len(V), t)
        self.assertIn('const ivec2 LV_E[%d]' % len(E), t)
        self.assertLessEqual(max(r[1] for r in R), 20)                # pv[20] in the shader
        self.assertLessEqual(max(r[3] for r in R), 30)                # edge loop bound 30


class Projection(unittest.TestCase):
    def test_project_centre_and_scale(self):
        f = 0.5 / math.tan(math.radians(20))
        x, y, z = L['project']((0.0, 0.0, 0.0), 3.0, f, (0.0, 0.0), W, H)
        self.assertEqual((x, y), (W / 2, H / 2))
        x, y, _ = L['project']((0.6, 0.0, 0.0), 3.0, f, (0.0, 0.1), W, H)
        self.assertAlmostEqual(x - W / 2, 0.6 * f / 3.0 * H)
        self.assertAlmostEqual(y - H / 2, 0.1 * H)
        xn, _, _ = L['project']((0.6, 0.0, 1.0), 3.0, f, (0.0, 0.0), W, H)
        self.assertGreater(xn, x)                                     # nearer = bigger

    def test_rotation_orthonormal(self):
        Rm = np.array(L['rot_matrix'](0.3, -1.1, 2.0))
        self.assertTrue(np.allclose(Rm @ Rm.T, np.eye(3)))
        self.assertAlmostEqual(np.linalg.det(Rm), 1.0)
        self.assertTrue(np.allclose(L['rot_matrix'](0, 0, math.pi / 2) @ np.array([1, 0, 0]), [0, 1, 0]))


class Wire(unittest.TestCase):
    def test_line_width_profile(self):
        # octa seen straight: the edge (0,1,0)-(1,0,0) at z 0, no fade; walk across it
        u = U(Scene=0, Solid=2, Rotx=0.0, Spiny=0.0, Depthfade=0.0, Linewidth=3.0, Glow=0.0, Size=0.6)
        f = u['uB'][2]
        a = L['project']((0.0, 0.6, 0.0), 3.0, f, (0, 0), W, H)
        b = L['project']((0.6, 0.0, 0.0), 3.0, f, (0, 0), W, H)
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        n = np.array([a[1] - b[1], b[0] - a[0]])
        n /= np.linalg.norm(n)
        tot = 0.0
        for s in np.arange(-6, 6, 0.05):
            tot += L['shade'](mx + n[0] * s, my + n[1] * s, u, W, H)[1] * 0.05
        self.assertAlmostEqual(tot, 3.0, delta=0.02)                  # integral across = Linewidth
        self.assertAlmostEqual(L['shade'](mx, my, u, W, H)[1], 1.0)

    def test_depth_fade_and_nest(self):
        u = U(Scene=0, Solid=1, Rotx=0.0, Spiny=0.0, Depthfade=1.0, Glow=0.0)
        f = u['uB'][2]
        r = 0.6 / math.sqrt(3)
        far = L['project']((r, r, -r), 3.0, f, (0, 0), W, H)
        near = L['project']((r, r, r), 3.0, f, (0, 0), W, H)
        self.assertGreater(L['shade'](near[0], near[1], u, W, H)[1], L['shade'](far[0], far[1], u, W, H)[1] + 0.2)
        n1 = sum(cov(x, y, U(Scene=0, Nest=1)) for x, y in L['sample_points'](W, H, 1500))
        n3 = sum(cov(x, y, U(Scene=0, Nest=3)) for x, y in L['sample_points'](W, H, 1500))
        self.assertGreater(n3, n1)


class Hatch(unittest.TestCase):
    def test_density_follows_light(self):
        u = U(Scene=1, Spiny=0.0, Rotx=0.0, Rim=0, Glow=0.0, Hatchdensity=40.0, Lightaz=0.0, Lightel=0.0,
              Hatchangle=90.0)
        f, sz = u['uB'][2], 0.6
        rpx = sz * f / 3.0 * H
        means = []
        for fr in (-0.5, 0.0, 0.5):                                   # lit (z toward the light) at centre
            xs = W / 2 + fr * rpx
            col = [cov(int(xs), int(H / 2 + dy), u) for dy in range(-60, 60)]
            means.append(sum(col) / len(col))
        self.assertGreater(means[1], 0.6)                            # facing the light: wide light lines
        self.assertLess(means[0], means[1])
        sh_side = L['shade'](W / 2 + 0.9 * rpx, H / 2, u, W, H)
        self.assertGreaterEqual(sh_side[0], 0.0)

    def test_rim_and_outside(self):
        u = U(Scene=1, Rim=1, Glow=0.0, Linewidth=2.0)
        f = u['uB'][2]
        self.assertEqual(cov(2, 2, u), 0.0)
        r = 0.6 * f / math.sqrt(9.0 - 0.36)                           # screen radius where the ray grazes
        self.assertAlmostEqual(L['shade'](W / 2 + r * H, H / 2, u, W, H)[1], 1.0, delta=0.02)
        self.assertEqual(L['shade'](W / 2 + r * H + 4, H / 2, u, W, H)[1], 0.0)


class Relief(unittest.TestCase):
    def _rows_on(self, u, x, mask=None, src=None):
        return [cov(x, y, u, mask=mask, src=src) for y in range(H)]

    def test_flat_rows_counted(self):
        u = U(Scene=2, Rows=12, Height=0.0, Occlude=0, Glow=0.0, Depthfade=0.0, Linewidth=1.5)
        col = np.array(self._rows_on(u, W // 2))
        lines = int(((col[1:] > 0.5) & (col[:-1] <= 0.5)).sum())
        self.assertIn(lines, (11, 12))                                # adjacent near rows may touch

    def test_height_follows_mask(self):
        mask = np.zeros((48, 27, 4))
        mask[:, 13:, 0] = 1.0                                          # right half = person
        u = U(Scene=2, Rows=8, Height=0.3, Heightsource=0, Occlude=0, Glow=0.0, Depthfade=0.0)
        flat = U(Scene=2, Rows=8, Height=0.0, Heightsource=0, Occlude=0, Glow=0.0, Depthfade=0.0)
        top = lambda c: max(i for i, v in enumerate(c) if v > 0.5)
        left, right = self._rows_on(u, W // 4, mask), self._rows_on(u, 3 * W // 4, mask)
        fl = self._rows_on(flat, 3 * W // 4, mask)
        self.assertEqual(top(self._rows_on(u, W // 4, mask)), top(self._rows_on(flat, W // 4, mask)))  # no person
        self.assertGreater(top(right), top(fl) + 5)                    # raised where the mask is

    def test_occlusion_hides(self):
        n_on = sum(cov(x, y, U(Scene=2, Occlude=1, Height=0.6, Glow=0.0)) for x, y in L['sample_points'](W, H, 1500))
        n_off = sum(cov(x, y, U(Scene=2, Occlude=0, Height=0.6, Glow=0.0)) for x, y in L['sample_points'](W, H, 1500))
        self.assertLess(n_on, n_off)


class Moire(unittest.TestCase):
    def test_single_grating_mean_and_period(self):
        u = U(Scene=3, Spacing=10.0, Linewidth=2.0, Moireangle=90.0, Moirescale=0.0, Drift=0.0, Glow=0.0,
              Rotz=0.0)
        row = [L['shade'](x + 0.5, 17.3, u, W, H)[1] for x in range(200)]  # set 2 lines are horizontal
        # set 2 (vertical normal) contributes a constant along the row; set 1 is periodic with 10 px
        self.assertTrue(np.allclose(row[:-10], row[10:], atol=1e-9))
        u1 = U(Scene=3, Spacing=10.0, Linewidth=2.0, Moireangle=0.0, Moirescale=0.0, Drift=0.0, Glow=0.0)
        mean = np.mean([L['shade'](x / 4.0, 3.3, u1, W, H)[1] for x in range(4000)])
        self.assertAlmostEqual(mean, 2.0 / 10.0, delta=0.005)         # duty = Linewidth / Spacing

    def test_moire_beat_period(self):
        sp, th = 8.0, math.radians(3.0)
        u = U(Scene=3, Spacing=sp, Linewidth=2.0, Moireangle=3.0, Moirescale=0.0, Drift=0.0, Glow=0.0)
        per = sp / (2 * math.sin(th / 2))                              # beat period, along the bisector normal
        # coverage averaged over a line-spacing window, sampled along the beat direction (perpendicular to the
        # bisector's normal): the union of two gratings is darkest where lines coincide (beat maxima)
        a = th / 2
        d = np.array([-math.sin(a), math.cos(a)])
        def env(s):
            c = np.array([W / 2, H / 2]) + d * s
            return np.mean([L['shade'](c[0] + math.cos(a) * k * 0.5, c[1] + math.sin(a) * k * 0.5, u, 4096, 4096)[1]
                            for k in range(int(2 * sp))])
        e0, eh, e1 = env(0.0), env(per / 2), env(per)
        self.assertAlmostEqual(e0, e1, delta=0.02)
        self.assertGreater(abs(e0 - eh), 0.05)


class Interaction(unittest.TestCase):
    def test_follow_moves_solid(self):
        pts = [(-10.0, -10.0, 0, 0), (0.8, 0.5, 0, 0)]
        off, rx, ry = L['follow'](U(Follow=1.0, Followrot=0.5), pts, W, H)
        self.assertAlmostEqual(off[0], (0.8 * W - 0.5 * W) / H)
        self.assertAlmostEqual(ry, 0.5 * math.pi * 0.3)
        off2, _, _ = L['follow'](U(Follow=1.0), [], W, H)
        self.assertEqual(off2, [0.0, 0.0])
        offc, _, _ = L['follow'](U(Follow=1.0, Followmode=1), [(0.2, 0.5, 0, 0), (0.8, 0.5, 0, 0)], W, H)
        self.assertAlmostEqual(offc[0], 0.0)

    def test_reveal_and_drive(self):
        mask = np.zeros((48, 27, 4))
        u = U(Scene=3, Reveal=1.0, Glow=0.0)
        self.assertEqual(sum(cov(x, y, u, mask=mask) for x, y in L['sample_points'](W, H, 300)), 0.0)
        ui = U(Scene=3, Reveal=1.0, Revealinvert=1, Glow=0.0)
        self.assertGreater(sum(cov(x, y, ui, mask=mask) for x, y in L['sample_points'](W, H, 300)), 10.0)
        a = L['shade'](100.5, 100.5, U(Scene=3, Glow=0.5), W, H)[2]
        b = L['shade'](100.5, 100.5, U(Scene=3, Glow=0.5, Audiogain=1.0, drive=(0.0, 120.0, 1.0, 0.0)), W, H)[2]
        self.assertAlmostEqual(b, 2.0 * a)
        k0 = L['uniforms'](P(Kick=30.0, Beatgain=1.0), 0.0, (4.0, 120.0, 0.0, 0.0))
        self.assertAlmostEqual(k0['uRot'][3], math.radians(30.0))


class Presets(unittest.TestCase):
    def test_every_preset_non_flat(self):
        mask = np.zeros((48, 27, 4))
        mask[10:40, 8:20, 0] = 1.0
        src = np.full((H, W, 4), 0.5)
        for slot, name, vals in M['PRESETS']:
            u = L['uniforms'](full_preset(vals), 1.0)
            base = np.zeros((H, W, 4))
            px = [L['pixel'](x, y, u, W, H, base, [(0.6, 0.6, 0, 0)], mask, src) for x, y in
                  L['sample_points'](W, H, 300)]
            lum = [0.2126 * q[0] + 0.7152 * q[1] + 0.0722 * q[2] for q in px]
            self.assertGreater(np.mean(lum), 0.005, name)
            self.assertGreater(np.std(lum), 0.01, name)


class Shader(unittest.TestCase):
    def test_uniform_list(self):
        K.check_uniforms(self, M['shader_texts']()['fx'], M['uniforms'](), 'linevolume.fx')

    def test_bounded_loops(self):
        t = M['shader_texts']()['fx']
        for m in re.finditer(r'for \(int \w+ = 0; \w+ < (\w+);', t):
            self.assertIn(m.group(1), ('MAXPTS', 'MAXNEST', 'MAXROWS', '20', '30', '2'), m.group(0))

    @unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
    def test_compiles(self):
        K.glslc(self, M['shader_texts']()['fx'], 'linevolume.fx')


if __name__ == '__main__':
    unittest.main()
