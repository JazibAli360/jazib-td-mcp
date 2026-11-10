"""Offline tests for FX_glitch module 'slash' (builders/fx_glitch_slash.py + fx_glitch_slash_logic.py). No TD.
Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_slash.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import numpy as np  # noqa: E402
import fx_glitch_slash_logic as L  # noqa: E402

NS = K.load_module('slash')
W, H = 108, 192


def pic(seed=0):
    rng = np.random.default_rng(seed)
    a = rng.random((H, W, 4)).astype(np.float64)
    a[..., 3] = 1.0
    return a


def P(**over):
    return L.pars_of(dict({'Drive': 0, 'Open': 1.0, 'Glow': 0.0, 'Sparks': 0.0, 'Jag': 0.0, 'Randomdir': 0}, **over))


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'slash')
        self.assertEqual(pars['Placement'][2]['names'], NS['PLACEMENTS'])
        for k, v in L.DEFAULTS.items():
            self.assertIn(k, pars, k)
            d = pars[k][1]
            if pars[k][0] == 'Menu':
                d = pars[k][2]['names'].index(d)
            self.assertEqual(float(d), float(v), k)
        self.assertEqual(set(pars), set(L.DEFAULTS))
        st, fx = NS['uniforms']()
        K.check_uniforms(self, st, NS['STAMP'], pars)
        K.check_uniforms(self, fx, NS['SHADER'], pars)

    def test_presets_full_state(self):
        names = set(n for _pg, pl in NS['PAGES'] for n, _s, _d, _o in pl) - {'Hit'}
        for _slot, pname, vals in NS['PRESETS']:
            self.assertEqual(set(vals), names, pname)                      # T-124 (1): no inheritance

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_slash.py'))
        K.check_td_rules(self, K.source('fx_glitch_slash_logic.py'))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_fx(self):
        ok, err = K.glslc(NS['SHADER'])
        self.assertTrue(ok, err)

    def test_stamp(self):
        ok, err = K.glslc(NS['STAMP'])
        self.assertTrue(ok, err)


class Hash(unittest.TestCase):
    def test_lowbias32_known(self):
        v = int(L.lb32(1))
        self.assertEqual(v, int(L.lb32(np.uint64(1))))
        self.assertTrue(0 <= v < 2 ** 32)
        self.assertNotEqual(int(L.lb32(1)), int(L.lb32(2)))

    def test_h3_range_and_spread(self):
        h = L.h3(np.arange(4096), 7, 3)
        self.assertTrue(np.all((h >= 0) & (h < 1)))
        self.assertTrue(0.45 < h.mean() < 0.55)


class Behaviour(unittest.TestCase):
    def test_amount_zero_exact(self):
        img = pic()
        self.assertTrue(np.array_equal(L.reference(img, P(Amount=0.0)), img))

    def test_open_zero_is_identity(self):
        img = pic()
        out = L.reference(img, P(Open=0.0))
        self.assertTrue(np.allclose(out, img))

    def test_hit_drive_closed_before_first_hit(self):
        img = pic()
        out = L.reference(img, L.pars_of({'Drive': 1}), now=5.0, hittime=-1000.0)
        self.assertTrue(np.allclose(out, img))

    def test_horizontal_cut_integer_shift(self):
        # Angle 0 = horizontal cut through the point; + side (above) moves up gap/2 and right slide/2, - side mirrors
        img = pic(1)
        pr = P(Placement=1, Count=1, Angle=0.0, Anglejitter=0.0, Gap=20.0, Slide=8.0, Back=0)
        out = L.reference(img, pr)
        cy = H // 2
        top = out[cy + 10 + 5:, 4:]
        self.assertTrue(np.allclose(top, img[cy + 5:H - 10, 0:W - 4]))
        bot = out[:cy - 10 - 5, :W - 4]
        self.assertTrue(np.allclose(bot, img[10:cy - 5, 4:]))
        gap = out[cy - 9:cy + 9, :, :3]
        self.assertTrue(np.all(gap == 0.0))

    def test_gap_area_matches_gap(self):
        reg = L.regions(P(Placement=1, Count=1, Angle=0.0, Anglejitter=0.0, Gap=20.0, Slide=0.0), W, H)
        # only the gap rows show Back (the parted pieces push their outer rows out of the frame)
        self.assertEqual(int(reg[:, 50].sum()), 20)

    def test_sequential_cuts_conserve_pixels(self):
        # with Slide 0 and no gap, nothing changes; with a gap, every visible piece pixel comes from the picture
        img = pic(2)
        pr = P(Count=4, Placement=0, Gap=0.0, Slide=0.0)
        self.assertTrue(np.allclose(L.reference(img, pr), img))

    def test_parallel_cuts_count(self):
        reg = L.regions(P(Count=4, Placement=2, Angle=0.0, Anglejitter=0.0, Spread=0.8, Gap=6.0, Slide=0.0), W, H)
        col = reg[:, 40]
        runs = np.count_nonzero(np.diff(col) == 1) + int(col[0] == 1)
        self.assertGreaterEqual(runs, 4)

    def test_jag_moves_the_boundary(self):
        a = L.regions(P(Placement=1, Count=1, Angle=0.0, Anglejitter=0.0, Gap=8.0, Slide=0.0), W, H)
        b = L.regions(P(Placement=1, Count=1, Angle=0.0, Anglejitter=0.0, Gap=8.0, Slide=0.0, Jag=12.0,
                        Jagsize=20.0), W, H)
        rows_a = [int(np.argmax(a[:, x])) for x in range(W)]
        rows_b = [int(np.argmax(b[:, x])) for x in range(W)]
        self.assertEqual(len(set(rows_a)), 1)
        self.assertGreater(len(set(rows_b)), 5)

    def test_envelope(self):
        pr = L.pars_of({'Drive': 1, 'Attack': 0.1, 'Hold': 0.5, 'Release': 0.4, 'Stagger': 0.05})
        self.assertEqual(L.open_amount(pr, 0, 0.0, 1.0), 0.0)
        self.assertAlmostEqual(L.open_amount(pr, 0, 1.05, 1.0), 0.5)
        self.assertEqual(L.open_amount(pr, 0, 1.3, 1.0), 1.0)
        self.assertEqual(L.open_amount(pr, 0, 2.1, 1.0), 0.0)
        self.assertEqual(L.open_amount(pr, 2, 1.05, 1.0), 0.0)            # staggered: cut 2 starts at 1.1
        stay = dict(pr, Release=0.0)
        self.assertEqual(L.open_amount(stay, 0, 50.0, 1.0), 1.0)

    def test_each_hit_rerolls_random_cuts(self):
        a = L.cuts(P(Count=3), W, H, cnt=1)
        b = L.cuts(P(Count=3), W, H, cnt=2)
        self.assertFalse(np.allclose(a[0][2], b[0][2]))

    def test_glow_and_sparks_only_add(self):
        img = pic(3) * 0.5
        base = L.reference(img, P(Count=3, Gap=12.0, Slide=30.0), now=1.0)
        lit = L.reference(img, P(Count=3, Gap=12.0, Slide=30.0, Glow=1.5, Sparks=1.0), now=1.0)
        self.assertTrue(np.all(lit[..., :3] >= base[..., :3] - 1e-12))
        self.assertGreater(float((lit - base)[..., :3].max()), 0.1)

    def test_back_modes(self):
        img = pic(4)
        pr = P(Placement=1, Count=1, Angle=0.0, Anglejitter=0.0, Gap=20.0, Slide=0.0)
        cy = H // 2
        dim = L.reference(img, dict(pr, Back=1, Backdim=0.5))
        self.assertTrue(np.allclose(dim[cy, :, :3], img[cy, :, :3] * 0.5))
        tr = L.reference(img, dict(pr, Back=2))
        self.assertTrue(np.all(tr[cy] == 0.0))

    def test_presets_cut_something(self):
        img = pic(5)
        for _s, name, v in NS['PRESETS']:
            pr = L.pars_of(v)
            hit = 0.0 if pr['Drive'] == 1 else -1000.0
            out = L.reference(img, pr, now=0.4, hittime=hit, cnt=1)
            self.assertGreater(float(np.abs(out - img).mean()), 0.01, name)


if __name__ == '__main__':
    unittest.main()
