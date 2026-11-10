"""Offline tests for FX_glitch module 'pixelsort' (builders/fx_glitch_pixelsort.py), Method Lite mirror
builders/fx_glitch_pixelsort_logic.py. No TD. Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_pixelsort.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import numpy as np  # noqa: E402
import fx_glitch_pixelsort_logic as L  # noqa: E402

NS = K.load_module('pixelsort')
W, H = 64, 96


def pic(seed=0):
    rng = np.random.default_rng(seed)
    a = rng.random((H, W, 4))
    a[..., 3] = 1.0
    return a


def P(**o):
    return L.pars_of(dict({'Method': 1, 'Litejitter': 0.0, 'Litenoise': 0.0}, **o))


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'pixelsort')
        self.assertEqual(pars['Method'][2]['names'], ['sort', 'lite'])
        for k, v in L.DEFAULTS.items():
            d = pars[k][1]
            if pars[k][0] == 'Menu':
                d = pars[k][2]['names'].index(d)
            self.assertEqual(float(d), float(v), k)
        lite, fx = NS['lite_uniforms']()
        K.check_uniforms(self, lite, NS['LITE'], pars)
        K.check_uniforms(self, fx, NS['LITE_FX'], pars)

    def test_presets_full_state(self):
        names = set(n for _pg, pl in NS['PAGES'] for n, s, _d, _o in pl if s != 'TOP')
        for _slot, pname, vals in NS['PRESETS']:
            self.assertEqual(set(vals), names, pname)
        self.assertEqual([p[1] for p in NS['PRESETS'][:5]], ['asendorf', 'comet', 'hue rainbow', 'shards', 'breathe'])

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_pixelsort.py'))
        K.check_td_rules(self, K.source('fx_glitch_pixelsort_logic.py'))

    def test_direction_expressions_match_logic(self):
        import math  # noqa: F401
        lite, _fx = NS['lite_uniforms']()
        dx, dy = lite[1][1][0], lite[1][1][1]
        for d, ang, rv in [(0, 30.0, 0), (1, 30.0, 0), (2, 30.0, 0), (1, 0.0, 1), (2, -60.0, 1)]:
            class Par:
                def __init__(s, v): s.v = v; s.menuIndex = v
                def eval(s): return s.v
            class PP: pass
            pp = PP(); pp.Direction = Par(d); pp.Angle = Par(ang); pp.Reverse = Par(rv)
            env = {'math': __import__('math'), 'parent': lambda: type('X', (), {'par': pp})()}
            got = (eval(dx, env), eval(dy, env))
            exp = L.direction(L.pars_of({'Direction': d, 'Angle': ang, 'Reverse': rv}))
            self.assertAlmostEqual(got[0], exp[0]); self.assertAlmostEqual(got[1], exp[1])


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_all(self):
        for n in ('SORT', 'APPLY', 'LITE', 'LITE_FX'):
            ok, err = K.glslc(NS[n])
            self.assertTrue(ok, n + err)


class Lite(unittest.TestCase):
    def test_fresh_is_seed_only(self):
        img = pic()
        T = L.lite_step(img, None, P(Lower=0.5, Upper=1.0), fresh=True)
        m = L.inside(img, P(Lower=0.5, Upper=1.0))
        self.assertTrue(np.all(T[~m] == 0))
        self.assertTrue(np.allclose(T[m][:, :3], img[m][:, :3]))

    def test_down_integer_shift(self):
        # columns, Length 3 px, no jitter: trail at row y = decay * trail at y + 3 (TD y up: down = content falls)
        img = pic(1)
        Pp = P(Direction=1, Lower=0.9, Upper=1.0, Litelength=3.0, Litedecay=0.5)
        T0 = L.lite_step(img, None, Pp, fresh=True)
        T1 = L.lite_step(img, T0, Pp)
        m = L.inside(img, Pp)
        y, x = 40, 10
        if not m[y, x]:
            self.assertTrue(np.allclose(T1[y, x], 0.5 * T0[y + 3, x]))
        self.assertTrue(np.all(T1[H - 3:][~m[H - 3:]] == 0))          # from outside the frame: zero

    def test_over_keeps_seed_pixels(self):
        img = pic(2)
        Pp = P(Lower=0.6, Upper=1.0)
        out = L.reference(img, Pp, iters=40)
        m = L.inside(img, Pp)
        self.assertTrue(np.allclose(out[m], img[m]))
        self.assertGreater(np.abs(out - img)[~m].mean(), 0.01)

    def test_amount_zero(self):
        img = pic(3)
        self.assertTrue(np.array_equal(L.reference(img, P(Amount=0.0)), img))

    def test_lighten_only_raises(self):
        img = pic(4)
        out = L.reference(img, P(Liteblend=1, Lower=0.5, Upper=1.0), iters=30)
        self.assertTrue(np.all(out[..., :3] >= img[..., :3] - 1e-12))

    def test_steady_converges(self):
        img = pic(5)
        Pp = P(Litedecay=0.8, Lower=0.5, Upper=1.0, Litelength=4.0)
        a = L.lite_steady(img, Pp, 60)
        b = L.lite_steady(img, Pp, 61)
        self.assertLess(np.abs(a - b).max(), 1e-4)


if __name__ == '__main__':
    unittest.main()
