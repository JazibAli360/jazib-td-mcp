"""Offline tests for FX_glitch module 'misc' (builders/fx_glitch_misc.py + fx_glitch_misc_logic.py). No TD.
Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_misc.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import fx_glitch_misc_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = K.load_module('misc')
W, H = 96, 160


def picture(seed=3):
    """Smooth gradients + a bright disc + a dark bar (row 0 = bottom), alpha 1."""
    y, x = np.mgrid[0:H, 0:W].astype(np.float64)
    img = np.zeros((H, W, 4))
    img[..., 0] = x / W
    img[..., 1] = y / H
    img[..., 2] = 0.5 + 0.4 * np.sin(x * 0.2) * np.cos(y * 0.13)
    disc = (x - 48) ** 2 + (y - 100) ** 2 < 15 ** 2
    img[disc, :3] = 0.95
    img[40:48, 10:80, :3] = 0.05
    img[..., 3] = 1.0
    rnd = np.random.RandomState(seed)
    img[..., :3] = np.clip(img[..., :3] + rnd.uniform(-0.01, 0.01, (H, W, 3)), 0, 1)
    return img


def P(t, **over):
    d = dict(L.DEFAULTS, Type=L.TYPES.index(t))
    d.update(over)
    return d


IMG = picture()


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'misc')
        self.assertEqual(pars['Type'][2]['names'], L.TYPES)
        self.assertEqual(NS['TYPES'], L.TYPES)
        for k, v in L.DEFAULTS.items():                     # logic defaults = page defaults
            self.assertIn(k, pars, k)
            style, default, o = pars[k]
            if style == 'Menu':
                self.assertEqual(o['names'].index(default), v, k)
            else:
                self.assertEqual(float(default), float(v), k)
        K.check_uniforms(self, NS['uniforms'](), NS['SHADER'], pars)
        K.check_uniforms(self, NS['stats_uniforms'](), NS['STATS'], pars)

    def test_presets_full_state(self):
        keys = set(L.DEFAULTS)
        for _s, name, vals in NS['PRESETS']:
            self.assertEqual(set(vals), keys, name)          # T-124 (1): full state, no inherit

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_misc.py'))
        K.source('fx_glitch_misc_logic.py').encode('ascii')

    def test_three_inputs_max(self):
        src = K.source('fx_glitch_misc.py')
        self.assertNotIn('sTD2DInputs[3]', src)              # GLSL TOP = 3 inputs (T-88)


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_fx(self):
        ok, err = K.glslc(NS['SHADER'])
        self.assertTrue(ok, err)

    def test_stats(self):
        ok, err = K.glslc(NS['STATS'])
        self.assertTrue(ok, err)


class Hash(unittest.TestCase):
    def test_lowbias32_known(self):
        # lowbias32(0) = 0, lowbias32(1) = 0x9f4f8a3b? -> check against a pure-Python version instead
        def lb(x):
            x &= 0xFFFFFFFF
            x ^= x >> 16
            x = (x * 0x7feb352d) & 0xFFFFFFFF
            x ^= x >> 15
            x = (x * 0x846ca68b) & 0xFFFFFFFF
            x ^= x >> 16
            return x
        for v in (0, 1, 2, 12345, 0xFFFFFFFF, -1, -7):
            self.assertEqual(int(L.lb32(v)), lb(v))

    def test_hsh_range_and_negative(self):
        h = L.hsh(np.arange(-50, 50), 3, 7)
        self.assertTrue(np.all((h >= 0) & (h < 1)))
        self.assertGreater(len(set(np.round(h, 6))), 95)


class Types(unittest.TestCase):
    def test_amount_zero_exact(self):
        for t in L.TYPES:
            out = L.reference(IMG, P(t, Amount=0.0))
            self.assertTrue(np.array_equal(out, IMG), t)

    def test_every_type_changes_picture(self):
        for t in L.TYPES:
            pars = P(t)
            if t == 'zap':
                pars.update(Pointv=0.1, Point2v=0.9)
            arcs = [(10.0, 20.0, 80.0, 140.0, 1.0, 3.0)] if t == 'arcs' else None
            out = L.reference(IMG, pars, arcs=arcs)
            self.assertGreater(np.abs(out - IMG).max(), 0.05, t)
            self.assertTrue(np.all(np.isfinite(out)), t)

    def test_bend_strength_zero_is_identity(self):
        out = L.reference(IMG, P('bend', Strength=0.0))
        self.assertLess(np.abs(out - IMG).max(), 1e-9)

    def test_suck_hole_black_at_centre(self):
        out = L.reference(IMG, P('suck', Size=10.0, Softness=0.0))
        self.assertLess(out[80, 48, :3].max(), 1e-9)          # the Point (0.5, 0.5) = pixel (48, 80)
        self.assertGreater(out[5, 5, :3].max(), 0.0)

    def test_suck_strength_zero_no_swirl_only_hole(self):
        out = L.reference(IMG, P('suck', Strength=0.0, Angle=0.0, Size=0.0, Softness=0.0))
        far = np.hypot(*np.mgrid[0:H, 0:W][::-1] - np.array([47.5, 79.5])[:, None, None]) > 3
        self.assertLess(np.abs(out - IMG)[far].max(), 1e-9)

    def test_tri_cells_constant(self):
        flat = L.reference(IMG, P('tri', Size=24.0, Levels=0, Edges=0.0))
        # lower triangle (0, 0): corners (0, 0) (24, 0) (12, 20.8) from the picture centre (48, 80) -> its
        # centroid is pixel (60, 87); the 2x2 pixels there are well inside and share one colour
        cols = flat[86:88, 59:61, :3].reshape(-1, 3)
        self.assertLess(np.ptp(cols, axis=0).max(), 1e-12)
        self.assertLess(len(np.unique(np.round(flat[..., :3].reshape(-1, 3), 9), axis=0)), W * H / 50)

    def test_tri_subdivision_adds_detail(self):
        a = L.reference(IMG, P('tri', Size=48.0, Levels=0, Edges=0.0))
        b = L.reference(IMG, P('tri', Size=48.0, Levels=3, Detail=0.02, Edges=0.0))
        na = len(np.unique(np.round(a[..., :3].reshape(-1, 3), 9), axis=0))
        nb = len(np.unique(np.round(b[..., :3].reshape(-1, 3), 9), axis=0))
        self.assertGreater(nb, 2 * na)
        err_a, err_b = np.abs(a - IMG).mean(), np.abs(b - IMG).mean()
        self.assertLess(err_b, err_a)

    def test_tri_edges_darken_only(self):
        a = L.reference(IMG, P('tri', Size=24.0, Levels=0, Edges=0.0))
        b = L.reference(IMG, P('tri', Size=24.0, Levels=0, Edges=1.0))
        self.assertTrue(np.all(b[..., :3] <= a[..., :3] + 1e-12))
        self.assertGreater((b[..., :3] < a[..., :3] - 1e-6).mean(), 0.05)

    def test_longshadow_only_darkens_black(self):
        out = L.reference(IMG, P('longshadow', Colr=0.0, Colg=0.0, Colb=0.0, Strength=1.0, Angle=0.0,
                                 Length=40.0))
        self.assertTrue(np.all(out[..., :3] <= IMG[..., :3] + 1e-12))
        below = out[70:84, 44:52, :3].mean()                  # under the disc (y 85..115), angle 0 = down
        self.assertLess(below, IMG[70:84, 44:52, :3].mean() - 0.2)
        above = np.abs(out[120:150, 44:52] - IMG[120:150, 44:52]).max()
        self.assertLess(above, 0.2)

    def test_longshadow_caster_untouched(self):
        out = L.reference(IMG, P('longshadow', Colr=0.0, Colg=0.0, Colb=0.0, Threshold=0.5, Softness=0.0))
        self.assertLess(np.abs(out[100, 48] - IMG[100, 48]).max(), 1e-9)   # disc centre casts, is not shaded

    def test_electrify_only_adds_on_edges(self):
        out = L.reference(IMG, P('electrify', Length=0.0, Threshold=0.2, Softness=0.1))
        self.assertTrue(np.all(out[..., :3] >= IMG[..., :3] - 1e-12))
        d = (out - IMG)[..., :3].max(-1)
        self.assertGreater(d[100, 33], 0.3)                    # disc edge (x 33 = 48 - 15)
        self.assertLess(d[20, 20], 1e-6)                       # smooth area

    def test_electrify_rate_rerolls(self):
        a = L.reference(IMG, P('electrify', Rate=10.0, Length=4.0), t=0.0)
        b = L.reference(IMG, P('electrify', Rate=10.0, Length=4.0), t=0.05)
        c = L.reference(IMG, P('electrify', Rate=10.0, Length=4.0), t=0.15)
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))

    def test_autolevel_maps_lo_hi(self):
        dim = IMG.copy()
        dim[..., :3] = 0.2 + 0.5 * IMG[..., :3]
        lo, hi, mean = L.ref_stats(dim, 0)
        out = L.reference(dim, P('autolevel', Level=0), stats=(lo, hi, mean))
        for ch in range(3):
            self.assertAlmostEqual(out[..., ch].min(), 0.0, places=9)
            self.assertAlmostEqual(out[..., ch].max(), 1.0, places=9)
        linked = L.reference(dim, P('autolevel', Linked=1), stats=(lo, hi, mean))
        self.assertAlmostEqual(linked[..., :3].min(), 0.0, places=9)
        self.assertAlmostEqual(linked[..., :3].max(), 1.0, places=9)

    def test_ref_stats_mip(self):
        lo, hi, mean = L.ref_stats(IMG, 4)
        self.assertTrue(np.all(lo >= IMG[..., :3].reshape(-1, 3).min(0) - 1e-12))
        self.assertTrue(np.all(hi <= IMG[..., :3].reshape(-1, 3).max(0) + 1e-12))
        self.assertTrue(0 < mean < 1)

    def test_displace_flat_is_identity(self):
        flat = np.full((H, W, 4), 0.4)
        flat[..., 3] = 1.0
        out = L.reference(flat, P('displace', Strength=2.0, Length=500.0, Prism=0.5))
        self.assertLess(np.abs(out - flat).max(), 1e-12)

    def test_displace_map_and_prism(self):
        ramp = np.zeros((40, 30, 4))                           # map of another size: uv-mapped
        ramp[..., 0] = ramp[..., 1] = ramp[..., 2] = np.linspace(0, 1, 30)[None, :]
        ramp[..., 3] = 1
        a = L.reference(IMG, P('displace', Length=200.0, Prism=0.0), map_img=ramp)
        b = L.reference(IMG, P('displace', Length=200.0, Prism=0.8), map_img=ramp)
        self.assertGreater(np.abs(a - IMG).max(), 0.05)
        self.assertLess(np.abs(a[..., 1] - b[..., 1]).max(), 1e-12)    # green = the un-prismed offset
        self.assertGreater(np.abs(a[..., 0] - b[..., 0]).max(), 0.01)

    def test_zap_only_adds_and_hits_the_line(self):
        pars = P('zap', Pointu=0.5, Pointv=0.1, Point2u=0.5, Point2v=0.9, Jag=0.0, Branches=0, Width=2.0)
        out = L.reference(IMG, pars)
        d = (out - IMG)[..., :3].max(-1)
        self.assertTrue(np.all(d >= -1e-12))
        self.assertGreater(d[80, 47], 0.5)                     # on the straight bolt (x 48, Jag 0)
        self.assertLess(d[80, 5], 1e-3)

    def test_zap_branches_and_rate(self):
        pars = P('zap', Pointv=0.1, Point2v=0.9, Branches=6, Rate=5.0)
        _a, _b, _s, br = L.zap_branches(L.full_pars(pars), W, H, 0)
        self.assertEqual(len(br), 6)
        a = L.reference(IMG, pars, t=0.0)
        b = L.reference(IMG, pars, t=0.25)
        self.assertFalse(np.array_equal(a, b))

    def test_region_equals_full_crop(self):
        for ty in L.TYPES:
            pars = P(ty, Pointv=0.1 if ty == 'zap' else 0.5)
            full = L.reference(IMG, pars)
            part = L.reference(IMG, pars, region=(30, 50, 20, 40))
            self.assertLess(np.abs(full[50:90, 30:50] - part).max(), 1e-12, ty)

    def test_compare(self):
        ref = L.reference(IMG, P('suck'))
        q = np.round(np.clip(ref, 0, 1) * 255) / 255
        r = L.compare(q, ref)
        self.assertEqual(r['within'], 1.0)
        self.assertLessEqual(r['max'], 0.5 / 255 + 1e-9)


class TriLattice(unittest.TestCase):
    def test_equilateral_contains_pixel_classic_kept(self):
        # Levels 0: one triangle per pixel; its edge darkening (Edges 1) is 0 only on the triangle border. With the
        # equilateral basis every pixel lies inside its own triangle, so the darkened share is the border share.
        eq = L.reference(IMG, P('tri', Levels=0, Edges=1.0, Size=24.0, Lattice=1))
        cl = L.reference(IMG, P('tri', Levels=0, Edges=1.0, Size=24.0, Lattice=0))
        dark_eq = (eq[..., :3].sum(-1) < 1e-9).mean()
        dark_cl = (cl[..., :3].sum(-1) < 1e-9).mean()
        self.assertLess(dark_eq, 0.12)
        self.assertGreater(dark_cl, dark_eq)                     # the classic look keeps its outside-triangle pixels
        self.assertEqual(dict(NS['PRESETS'][2][2])['Lattice'], 0)  # 'triangulate' preset keeps the 26 Oct look


ARCS = {}
exec(NS['ARCS_PY'], ARCS)


class Arcs(unittest.TestCase):
    def test_read_points_layouts(self):
        pts = ARCS['read_points']([('tx', [0.1, 0.5]), ('ty', [0.2, 0.6])], 2, 0, 100, 200)
        self.assertEqual(pts, [(10.0, 40.0), (50.0, 120.0)])
        pts = ARCS['read_points']([('p0x', [0.0]), ('p0y', [0.0]), ('p1x', [1.0]), ('p1y', [1.0])], 1, 1, 100, 200)
        self.assertEqual(pts, [(50.0, 100.0), (100.0, 200.0)])                       # ndc
        pts = ARCS['read_points']([('u', [5.0, 6.0]), ('v', [7.0, 8.0])], 2, 2, 100, 200)
        self.assertEqual(pts, [(5.0, 7.0), (6.0, 8.0)])                             # pixels

    def test_empty_and_single_point_chops(self):
        self.assertEqual(ARCS['read_points']([('u', []), ('v', [])], 0, 0, 100, 200), [])
        self.assertEqual(ARCS['read_points']([('u', [0.5]), ('v', [0.25])], 1, 0, 100, 200), [(50.0, 50.0)])
        self.assertEqual(ARCS['arc_list']([(1.0, 2.0)], 1, 0.3, 1.0, 16, 200), [])
        self.assertIn('Pointchop.eval() is None', NS['ARCS_CB'])         # a set Points CHOP never falls back

    def test_numpy_path_equals_loop(self):
        rnd = np.random.RandomState(7)
        for n in (12, 40, 64, 150):
            pts = [tuple(p) for p in rnd.uniform(0, 1000, (n, 2))]
            for mode, reach, fo, mx in ((1, 0.22, 1.2, 24), (1, 0.0, 1.0, 32), (2, 0.3, 0.7, 32), (2, 0.0, 1.0, 8)):
                a = ARCS['arc_list_np'](pts, mode, reach, fo, mx, 1000)
                b = ARCS['arc_list_py'](pts, mode, reach, fo, mx, 1000)
                self.assertEqual(len(a), len(b), (n, mode))
                np.testing.assert_allclose(np.array(a), np.array(b), atol=1e-9)
        self.assertEqual(ARCS['arc_list'](pts, 1, 0.22, 1.2, 24, 1000), ARCS['arc_list_np'](pts, 1, 0.22, 1.2, 24, 1000))

    def test_modes_and_power(self):
        pts = [(0, 0), (0, 100), (0, 300), (0, 1000)]
        chain = ARCS['arc_list'](pts, 0, 0.0, 1.0, 16, 1000)
        self.assertEqual(len(chain), 3)
        self.assertTrue(all(a[4] == 1.0 for a in chain))
        pairs = ARCS['arc_list'](pts, 1, 0.35, 1.0, 16, 1000)
        self.assertEqual(len(pairs), 3)                         # (0,1) .1, (0,2) .3, (1,2) .2 within .35
        self.assertGreater(pairs[0][4], pairs[-1][4])           # closer = stronger, sorted
        self.assertAlmostEqual(pairs[0][4], 1.0 - 0.1 / 0.35)
        near = ARCS['arc_list'](pts, 2, 0.0, 1.0, 16, 1000)
        self.assertEqual(sorted((a[1], a[3]) for a in near), [(0, 100), (100, 300), (300, 1000)])
        self.assertEqual(len(ARCS['arc_list'](pts, 1, 0.0, 1.0, 2, 1000)), 2)       # Maxarcs cap

    def test_arcs_glow_only_adds_and_cull_is_conservative(self):
        p = P('arcs', Width=2.0, Jag=0.2)
        arcs = [(10.0, 20.0, 80.0, 140.0, 0.8, 3.0), (90.0, 10.0, 20.0, 150.0, 0.5, 9.0)]
        out = L.reference(IMG, p, arcs=arcs)
        self.assertTrue(np.all(out[..., :3] >= IMG[..., :3] - 1e-12))
        # brute force without the cull: differences only where the glow is < exp(-14) x gain
        h, w = IMG.shape[:2]
        px, py = L.grid(h, w)
        sd = L.seed_mix(p['Seed'], 0)
        v = sum(pw * np.exp(-L._bolt(px, py, (a, b), (c_, d), (sd + int(sk) * 7 + 1000) & L.M32, p['Jag']) / 2.0)
                for a, b, c_, d, pw, sk in arcs)
        full = IMG[..., :3] + np.array([p['Colr'], p['Colg'], p['Colb']]) * (p['Glow'] * (0.6 + 0.4 * float(
            L.hsh(5, 9, sd))) * p['Strength']) * v[..., None]
        self.assertLess(np.abs(full - out[..., :3]).max(), 1e-5)

    def test_zero_power_draws_nothing(self):
        out = L.reference(IMG, P('arcs'), arcs=[(10.0, 20.0, 80.0, 140.0, 0.0, 3.0)])
        self.assertTrue(np.allclose(out, IMG))

    def test_builder_bits(self):
        self.assertIn('uniform samplerBuffer uArcs;', NS['SHADER'])
        self.assertIn("A = op('arcs_logic').module", NS['ARCS_CB'])
        compile(NS['ARCS_CB'], 'cb', 'exec')


if __name__ == '__main__':
    unittest.main()
