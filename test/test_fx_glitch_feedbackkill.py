"""Offline tests for FX_glitch module 'feedbackkill' (builders/fx_glitch_feedbackkill.py, fx_time_logic.py). No TD.
Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_feedbackkill.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import fx_time_logic as L  # noqa: E402
import numpy as np  # noqa: E402

NS = K.load_module('feedbackkill')
RNG = np.random.default_rng(5)


def P(**over):
    d = L.fk_defaults()
    d.update(over)
    return d


def simulate(Pd, live, gens=300):
    """Point-wise + integer-shift model of the loop (no zoom/rotate/filters): mean luma per generation."""
    s = live.copy()
    means = []
    sx, sy = int(round(Pd['Shiftx'])), int(round(Pd['Shifty']))
    for g in range(gens):
        mean = float(L.lum(s).mean())
        nz = RNG.random(s.shape) if Pd['Noise'] > 0 else None
        s = L.fk_colour(L.fk_shift(s, sx, sy, Pd['Edge']), live, Pd, mean=mean, nz=nz)
        means.append(float(L.lum(s).mean()))
    return s, means


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'feedbackkill')
        self.assertEqual(pars['Feed'][2]['names'], L.FK_FEEDS)
        self.assertEqual(pars['Edge'][2]['names'], L.FK_EDGES)
        for k in L.fk_defaults():
            self.assertIn(k, pars, k)
        K.check_uniforms(self, NS['uniforms'](), NS['SHADER'], pars)

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_feedbackkill.py'))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_fx(self):
        ok, err = K.glslc(NS['SHADER'])
        self.assertTrue(ok, err)

    def test_meter(self):
        ok, err = K.glslc(NS['METER'])
        self.assertTrue(ok, err)

    def test_outc(self):
        ok, err = K.glslc(NS['OUTC'])
        self.assertTrue(ok, err)

    def test_glslc_really_checks(self):
        ok, _err = K.glslc(NS['OUTC'].replace('vec4 a =', 'vec3 a ='))
        self.assertFalse(ok)


class Colour(unittest.TestCase):
    def setUp(self):
        self.c = RNG.random((32, 32, 3))
        self.live = RNG.random((32, 32, 3))

    def test_identity(self):
        out = L.fk_colour(self.c, self.live, P(Leak=0.0))
        self.assertTrue(np.allclose(out, self.c, atol=1e-12))

    def test_hue_rotation(self):
        r = np.array([1.0, 0.0, 0.0])
        self.assertTrue(np.allclose(L.hue_rotate(r, 120.0), [0, 1, 0], atol=1e-12))
        self.assertTrue(np.allclose(L.hue_rotate(self.c, 360.0), self.c, atol=1e-12))
        self.assertTrue(np.allclose(L.hue_rotate(self.c, 37.0).sum(-1), self.c.sum(-1)))
        g = np.full(3, 0.4)
        self.assertTrue(np.allclose(L.hue_rotate(g, 50.0), g))

    def test_crush_levels(self):
        out = L.fk_colour(self.c, self.live, P(Leak=0.0, Crush=2))
        self.assertEqual(sorted(set(np.round(out.ravel() * 3, 9))), [0, 1, 2, 3])

    def test_fold(self):
        x = np.array([[0.2, 0.6, 0.9]])
        self.assertTrue(np.allclose(L.fk_colour(x, x, P(Leak=0.0, Fold=1.0)), [[0.4, 0.8, 0.2]]))

    def test_feeds(self):
        c, lv = self.c, self.live
        self.assertTrue(np.allclose(L.fk_colour(c, lv, P(Leak=1.0)), lv))
        self.assertTrue(np.allclose(L.fk_colour(c, lv, P(Leak=0.25)), c + (lv - c) * 0.25))
        self.assertTrue(np.allclose(L.fk_colour(c, lv, P(Feed=1, Leak=1.0)), np.maximum(c, lv)))
        self.assertTrue(np.allclose(L.fk_colour(c, lv, P(Feed=2, Leak=1.0)), np.minimum(c, lv)))
        self.assertTrue(np.allclose(L.fk_colour(c, lv, P(Feed=3, Leak=1.0)), np.abs(c - lv)))
        self.assertTrue(np.allclose(L.fk_colour(c, lv, P(Feed=4, Leak=0.5)), np.clip(c + lv * 0.5, 0, 1)))

    def test_key(self):
        dark = np.full((1, 1, 3), 0.1)
        bright = np.full((1, 1, 3), 0.9)
        s = np.full((1, 1, 3), 0.5)
        self.assertTrue(np.allclose(L.fk_colour(s, dark, P(Leak=1.0, Key=0.5)), s))
        self.assertTrue(np.allclose(L.fk_colour(s, bright, P(Leak=1.0, Key=0.5)), bright))

    def test_autogain_pulls_to_target(self):
        live = np.full((8, 8, 3), 0.05)
        _s, means = simulate(P(Leak=0.0, Autogain=1.0, Target=0.45), live, 120)
        self.assertAlmostEqual(means[-1], 0.45, delta=0.02)
        _s, means = simulate(P(Leak=0.0, Autogain=1.0, Target=0.45), np.zeros((8, 8, 3)), 200)
        self.assertGreater(means[-1], 0.3)                             # lifts pure black too

    def test_presets_never_lock(self):
        live = RNG.random((24, 24, 3)) * 0.8
        for _slot, name, vals in NS['PRESETS']:
            Pd = P(**vals)
            s, means = simulate(Pd, live, 300)
            self.assertTrue(0.03 < means[-1] < 0.97, (name, means[-1]))
            self.assertGreater(float(s.std()), 0.01, name)


class Geometry(unittest.TestCase):
    def test_integer_shift_repeat_is_roll(self):
        img = RNG.random((20, 30, 3))
        self.assertTrue(np.array_equal(L.fk_shift(img, 3, -2, edge=1), np.roll(img, (-2, 3), axis=(0, 1))))

    def test_mirror_and_black_edges(self):
        img = np.arange(6, dtype=float).reshape(1, 6)
        self.assertEqual(L.fk_shift(img, 2, 0, edge=0).tolist(), [[1, 0, 0, 1, 2, 3]])
        self.assertEqual(L.fk_shift(img, 2, 0, edge=2).tolist(), [[0, 0, 0, 1, 2, 3]])
        self.assertEqual(L.fk_shift(img, 2, 0, edge=3).tolist(), [[0, 0, 0, 1, 2, 3]])
        self.assertEqual(L.fk_shift(img, -2, 0, edge=3).tolist(), [[2, 3, 4, 5, 0, 0]])

    def test_n_generations_of_shift(self):
        img = RNG.random((10, 10))
        s = img
        for _ in range(7):
            s = L.fk_shift(s, 1, 0, edge=1)
        self.assertTrue(np.array_equal(s, np.roll(img, 7, axis=1)))

    def test_meter_grid(self):
        g = L.fk_mean_grid(1080, 1920)
        self.assertEqual(len(g), 4096)
        self.assertEqual(g[0], (8, 15))
        self.assertTrue(all(0 <= x < 1080 and 0 <= y < 1920 for x, y in g))

    def test_ticks(self):
        t = [i / 60.0 for i in range(121)]
        self.assertTrue(all(L.fk_ticks(t, 0)))
        self.assertEqual(sum(L.fk_ticks(t, 2.0)), 4)                  # 0.5, 1.0, 1.5, 2.0 s


if __name__ == '__main__':
    unittest.main()
