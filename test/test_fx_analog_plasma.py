"""Offline tests for FX_analog module 'plasma' (builders/fx_analog_plasma.py, fx_analog_plasma_logic.py). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_analog_plasma.py'
glslc compiles every pass against stubs of TD's compute globals (syntax/type check, NOT a TD compile: LIVE CHECK 1 in
docs/builds/fx_analog_plasma.md)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import fx_analog_plasma_logic as L  # noqa: E402
import numpy as np  # noqa: E402


def module_ns():
    ns = {'HERE': K.BUILDERS}
    path = os.path.join(K.BUILDERS, 'fx_analog_plasma.py')
    with open(path) as fh:
        exec(compile(fh.read(), path, 'exec'), ns)
    return ns


NS = module_ns()
W, H = 96, 64


def ramp(w=W, h=H, lo=0.0, hi=1.0, axis=1):
    """Horizontal (axis 1) grey ramp, 8-bit exact values, alpha 1."""
    n = w if axis == 1 else h
    v = np.round(np.linspace(lo, hi, n) * 255.0) / 255.0
    img = np.ones((h, w, 4), np.float32)
    g = np.tile(v[None, :], (h, 1)) if axis == 1 else np.tile(v[:, None], (1, w))
    img[..., 0] = img[..., 1] = img[..., 2] = g
    return img


def q8(x):
    return np.round(np.clip(x, 0, 1) * 255.0)


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'plasma')
        self.assertEqual(pars['Subfields'][2]['names'], L.TABLE_NAMES)
        self.assertEqual(pars['Motion'][2]['names'], L.MOTIONS)
        for k in L.DEFAULTS:
            self.assertIn(k, pars, k)
        for k, (style, default, o) in pars.items():
            if style == 'Menu':
                self.assertEqual(L.DEFAULTS[k], o['names'].index(default), k)
            else:
                self.assertAlmostEqual(float(L.DEFAULTS[k]), float(default), msg=k)

    def test_uniforms_match_shaders(self):
        pars = K.check_module_contract(self, NS, 'plasma')
        U = NS['uniforms']()
        self.assertEqual(set(U), set(NS['SHADERS']))
        for name, text in NS['SHADERS'].items():
            K.check_uniforms(self, U[name], text, pars)

    def test_rules(self):
        src = K.source('fx_analog_plasma.py')
        K.check_td_rules(self, src)
        K.source('fx_analog_plasma_logic.py').encode('ascii')

    def test_preset_types(self):
        pars = K.check_module_contract(self, NS, 'plasma')
        for _s, name, vals in NS['PRESETS']:
            for k, v in vals.items():
                style = pars[k][0]
                if style in ('Menu', 'Int'):
                    self.assertIsInstance(v, int, (name, k))
                else:
                    self.assertIsInstance(v, float, (name, k))

    def test_max_three_inputs(self):
        self.assertNotIn('sTD2DInputs[3]', NS['FX'])          # in1, mv_src, codes (T-84: 3 connectors)
        self.assertNotIn('sTD2DInputs[1]', NS['EST'])
        self.assertNotIn('sTD2DInputs[1]', NS['CODES'])


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        for name, text in NS['SHADERS'].items():
            self.assertTrue(all(ord(ch) < 128 for ch in text), name)
            ok, err = K.glslc(text)
            self.assertTrue(ok, name + ': ' + err)


class Tables(unittest.TestCase):
    def test_sum_255_and_ascending(self):
        for t in L.TABLES:
            self.assertEqual(sum(t), 255)
            self.assertEqual(t, sorted(t))
            self.assertLessEqual(len(t), 12)

    def test_greedy_is_exact_for_every_code(self):
        c = np.arange(256, dtype=np.float32)
        for tb in range(3):
            self.assertTrue(np.array_equal(L.decode(L.lit_masks(c, tb), tb), c), tb)

    def test_shader_closed_form_matches_greedy(self):
        # the fx shader's lit() is a closed form of the greedy loop (perf lane 2, 27 Oct): mirror it line for line
        def lit(c, tb):
            if tb == 0:
                return c
            if tb == 1:
                h = min(c // 48, 4)
                return (((1 << h) - 1) << (10 - h)) | (c - 48 * h)
            m = 0
            if c >= 40:
                m, c = 1 << 11, c - 40
            h = min(c // 32, 5)
            m |= ((1 << h) - 1) << (11 - h)
            c -= 32 * h
            if c >= 24:
                m, c = m | (1 << 5), c - 24
            return m | c
        for tb in range(3):
            ref = L.lit_masks(np.arange(256, dtype=np.float32), tb)
            self.assertEqual([lit(c, tb) for c in range(256)], [int(x) for x in ref], tb)
        self.assertIn('uint h = min(c / 48u, 4u);', NS['FX'])
        self.assertNotIn('tk[', NS['FX'])

    def test_binary_masks_are_bits(self):
        c = np.arange(256)
        self.assertTrue(np.array_equal(L.lit_masks(c.astype(np.float32), 0), c))

    def test_time_centres(self):
        for tb in range(3):
            for order in (0, 1):
                t = L.time_centres(tb, order, 6.0)
                self.assertTrue(np.all((t > 0) & (t < 1)))
                self.assertEqual(len(set(t.tolist())), len(t))
            a = L.time_centres(tb, 0, 0.0)
            self.assertTrue(np.all(np.diff(a) > 0))                       # ascending in time
            d = L.time_centres(tb, 1, 0.0)
            self.assertTrue(np.all(np.diff(d) < 0))
        t = L.time_centres(0, 0, 0.0)
        self.assertAlmostEqual(float(t[7]), (127 + 64) / 255.0, places=6)


class Behaviour(unittest.TestCase):
    def test_amount_zero_exact(self):
        img = ramp()
        img[..., 3] = 0.5
        out = L.reference(img, {'Amount': 0.0, 'Motionx': 9.0})
        self.assertTrue(np.array_equal(out, img))

    def test_static_linear_is_identity(self):
        img = np.random.RandomState(1).randint(0, 256, (H, W, 4)).astype(np.float32) / 255.0
        for tb in range(3):
            out = L.reference(img, {'Motionx': 0.0, 'Gamma': 1.0, 'Subfields': tb})
            self.assertEqual(np.abs(q8(out[..., :3]) - q8(img[..., :3])).max(), 0.0, tb)
            self.assertTrue(np.array_equal(out[..., 3], img[..., 3]))

    def test_static_gamma_is_monotonic_requantise(self):
        img = ramp()
        out = L.reference(img, {'Motionx': 0.0, 'Gamma': 2.2})
        row = out[0, :, 0]
        self.assertTrue(np.all(np.diff(row) >= 0))                        # no contour: monotonic
        self.assertLess(np.abs(out[..., :3] - img[..., :3]).max(), 0.06)  # only dark-level requantising

    def test_motion_makes_contours_on_gradient(self):
        img = ramp(lo=0.3, hi=0.7)                                        # crosses 127 -> 128
        out = L.reference(img, {'Motionx': 8.0, 'Gamma': 1.0})
        row = q8(out[0, :, 0])
        jumps = np.abs(np.diff(row))
        self.assertGreater(jumps.max(), 20)                               # the 127/128 false contour
        self.assertFalse(np.all(np.diff(row) >= 0))                       # no longer monotonic
        # flat areas stay exact: contours only where the code changes along the motion
        flat = np.full((H, W, 4), 0.5, np.float32)
        fo = L.reference(flat, {'Motionx': 8.0, 'Gamma': 1.0})
        self.assertEqual(np.abs(q8(fo[..., :3]) - q8(flat[..., :3])).max(), 0.0)

    def test_more_subfields_less_contour(self):
        img = ramp(lo=0.2, hi=0.8)
        err = []
        for tb in range(3):
            out = L.reference(img, {'Motionx': 8.0, 'Gamma': 1.0, 'Subfields': tb, 'Address': 0.0})
            err.append(float(np.abs(out[..., :3] - img[..., :3]).mean()))
        self.assertGreater(err[0], err[1])
        self.assertGreater(err[0], err[2])

    def test_motion_direction_matters(self):
        img = ramp(lo=0.3, hi=0.7)                                        # horizontal gradient
        across = L.reference(img, {'Motionx': 8.0, 'Gamma': 1.0})
        along = L.reference(img, {'Motionx': 0.0, 'Motiony': 8.0, 'Gamma': 1.0})
        self.assertGreater(np.abs(across - img).mean(), 0.003)
        self.assertEqual(np.abs(q8(along[..., :3]) - q8(img[..., :3])).max(), 0.0)

    def test_sweep_zero_at_t0(self):
        img = ramp(lo=0.3, hi=0.7)
        out = L.reference(img, {'Motion': 1, 'Motionx': 8.0, 'Gamma': 1.0}, t=0.0)
        self.assertEqual(np.abs(q8(out[..., :3]) - q8(img[..., :3])).max(), 0.0)
        out = L.reference(img, {'Motion': 1, 'Motionx': 8.0, 'Gamma': 1.0, 'Period': 2.0}, t=0.5)
        self.assertGreater(np.abs(out - img).max(), 0.05)

    def test_greenlag_colours_edges(self):
        img = ramp(lo=0.3, hi=0.7)
        out = L.reference(img, {'Motionx': 8.0, 'Gamma': 1.0, 'Greenlag': 0.3})
        self.assertGreater(np.abs(out[..., 1] - out[..., 0]).max(), 0.05)
        still = L.reference(img, {'Motionx': 0.0, 'Gamma': 1.0, 'Greenlag': 0.3})
        self.assertEqual(np.abs(still[..., 1] - still[..., 0]).max(), 0.0)

    def test_dither_changes_with_frame_and_seed(self):
        img = ramp(lo=0.0, hi=0.2)
        a = L.reference(img, {'Motionx': 0.0, 'Dither': 1.0}, frame=0)
        b = L.reference(img, {'Motionx': 0.0, 'Dither': 1.0}, frame=1)
        c = L.reference(img, {'Motionx': 0.0, 'Dither': 1.0, 'Seed': 2}, frame=0)
        self.assertFalse(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))

    def test_cells_mask(self):
        img = np.full((H, W, 4), 1.0, np.float32)
        out = L.reference(img, {'Motionx': 0.0, 'Gamma': 1.0, 'Cells': 1.0, 'Cellsize': 6.0})
        self.assertTrue(np.array_equal(out[2, 0, :3], [1, 0, 0]))          # x 0..1 = red stripe
        self.assertTrue(np.array_equal(out[2, 2, :3], [0, 1, 0]))
        self.assertTrue(np.array_equal(out[2, 4, :3], [0, 0, 1]))
        self.assertTrue(np.all(out[0, :, :3] == 0))                        # rib row

    def test_presets_run(self):
        img = ramp(lo=0.1, hi=0.9)
        for _s, name, vals in NS['PRESETS']:
            est = np.zeros(((H + 7) // 8, (W + 7) // 8, 4), np.float32)
            est[..., 0] = 4.0
            out = L.reference(img, vals, t=0.5, est=est)
            self.assertTrue(np.all(np.isfinite(out)), name)
            self.assertGreater(np.abs(out - img).mean(), 1e-4, name)


class Estimate(unittest.TestCase):
    def pic(self, shift):
        x = np.arange(W)[None, :] - shift
        v = 0.5 + 0.4 * np.sin(x * 2 * np.pi / 48.0)
        img = np.ones((H, W, 4), np.float32)
        img[..., 0] = img[..., 1] = img[..., 2] = np.tile(v, (H, 1))
        return img

    def test_first_cook_and_stale_reset(self):
        s = L.est_step(self.pic(0), None, now=1.0)
        self.assertTrue(np.all(s[..., :2] == 0))
        s2 = L.est_step(self.pic(3), s, now=2.0)                          # gap 1 s = stale
        self.assertTrue(np.all(s2[..., :2] == 0))

    def test_same_frame_unchanged(self):
        s = L.est_step(self.pic(0), None, now=1.0)
        s2 = L.est_step(self.pic(5), s, now=1.0)
        self.assertTrue(np.array_equal(s, s2))

    def test_static_zero_and_motion_sign(self):
        p = {'Smooth': 0.0, 'Eps': 1e-4, 'Minmotion': 0.0}
        s = L.est_step(self.pic(0), None, p, now=1.0)
        st = L.est_step(self.pic(0), s, p, now=1.0 + 1 / 60.0)
        self.assertTrue(np.all(st[..., :2] == 0))
        mv = L.est_step(self.pic(2), s, p, now=1.0 + 1 / 60.0)
        vx = mv[2:-2, 2:-2, 0]
        strong = np.abs(vx) > 0.5
        self.assertGreater(strong.mean(), 0.3)
        self.assertGreater(np.median(vx[strong]), 0.5)                     # moves +x
        self.assertLess(np.abs(np.median(vx[strong]) - 2.0), 1.2)
        self.assertLess(np.abs(mv[..., 1]).max(), 1e-3)

    def test_field_sample_shape(self):
        est = np.zeros((8, 12, 4), np.float32)
        est[..., 0] = 3.0
        f = L.sample_field(est, W, H)
        self.assertEqual(f.shape, (H, W, 2))
        self.assertTrue(np.allclose(f[..., 0], 3.0))


class Compare(unittest.TestCase):
    def test_compare(self):
        a = ramp()
        r = L.compare(a, a)
        self.assertEqual(r['max_codes'], 0.0)
        b = a.copy()
        b[0, 0, 0] += 2 / 255.0
        self.assertEqual(L.compare(b, a)['max_codes'], 2.0)


if __name__ == '__main__':
    unittest.main()
