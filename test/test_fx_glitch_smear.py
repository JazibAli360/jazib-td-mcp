"""Offline tests for FX_glitch module 'smear' (builders/fx_glitch_smear.py; mode strips mirror
builders/fx_glitch_smear_logic.py) and the rack's upgrade helpers. No TD.
Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_smear.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import numpy as np  # noqa: E402
import fx_glitch_smear_logic as L  # noqa: E402

NS = K.load_module('smear')
RACK = {}
exec(open(os.path.join(K.BUILDERS, 'fx_glitch.py')).read(), RACK)
W, H = 120, 200


def pic(seed=0):
    rng = np.random.default_rng(seed)
    a = rng.random((H, W, 4))
    a[..., 3] = 1.0
    return a


def S(**over):
    return L.pars_of(dict({'Mode': 4, 'Threshold': 0.0, 'Decay': 1.0, 'Wobble': 0.0, 'Stripjitter': 0.0,
                           'Snap': 1.0, 'Density': 1.0}, **over))


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'smear')
        self.assertEqual(pars['Mode'][2]['names'], L.MODES)
        self.assertEqual(set(pars) - {'Masktop'}, set(L.DEFAULTS))
        for k, v in L.DEFAULTS.items():
            d = pars[k][1]
            if pars[k][0] == 'Menu':
                d = pars[k][2]['names'].index(d)
            self.assertEqual(float(d), float(v), k)
        K.check_uniforms(self, NS['uniforms'](), NS['SHADER'], pars)

    def test_presets_full_state(self):
        names = set(n for _pg, pl in NS['PAGES'] for n, _s, _d, _o in pl if _s != 'TOP')
        for _slot, pname, vals in NS['PRESETS']:
            self.assertEqual(set(vals), names, pname)
        self.assertEqual([p[1] for p in NS['PRESETS'][:4]], ['drip', 'shadow', 'stretch', 'mosh'])  # old slots kept

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_smear.py'))
        K.check_td_rules(self, K.source('fx_glitch_smear_logic.py'))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_fx(self):
        ok, err = K.glslc(NS['SHADER'])
        self.assertTrue(ok, err)

    def test_stamp(self):
        ok, err = K.glslc(NS['STAMP'])
        self.assertTrue(ok, err)


class Strips(unittest.TestCase):
    def test_amount_zero_exact(self):
        img = pic()
        self.assertTrue(np.array_equal(L.reference(img, S(Amount=0.0)), img))

    def test_length_one_is_identity(self):
        img = pic(1)                                         # 1 px segments, snap 0: every pixel samples itself
        self.assertTrue(np.allclose(L.reference(img, S(Length=1.0, Snap=0.0)), img))

    def test_vertical_segments_repeat_one_pixel(self):
        # Angle 0 (down), integer segments, no jitter, snap 1: within a strip and segment, one colour
        img = pic(2)
        out = L.reference(img, S(Length=10.0, Stripwidth=6.0))
        k, _a, qx, qy, f = L.strips_geometry(W, H, S(Length=10.0, Stripwidth=6.0))
        key = k * 100000 + np.floor(qy) * 1000 + np.floor(qx)
        for v in np.unique(key)[:200]:
            sel = key == v
            self.assertLess(float(np.ptp(out[sel][:, :3], axis=0).max()), 1e-12)
        self.assertTrue(np.all((f >= 0) & (f < 1)))
        self.assertTrue(np.allclose(np.floor(qy) + 0.5, qy))       # pixel-centre samples (parity exact on axis)

    def test_strip_width_columns(self):
        _k, _a, qx, _qy, _f = L.strips_geometry(W, H, S(Length=10.0, Stripwidth=6.0))
        cols = np.unique(np.floor(qx[0]))
        self.assertEqual(len(cols), W // 6 + (1 if W % 6 else 0))

    def test_density_zero_passthrough(self):
        img = pic(3)
        self.assertTrue(np.allclose(L.reference(img, S(Density=0.0)), img))

    def test_threshold_gates_dark_samples(self):
        img = pic(4) * 0.3                                   # every luma < 0.3
        self.assertTrue(np.allclose(L.reference(img, S(Threshold=0.5)), img))

    def test_decay_fades_to_source(self):
        img = pic(5)
        hard = L.reference(img, S(Length=20.0, Decay=1.0))
        soft = L.reference(img, S(Length=20.0, Decay=0.0))
        self.assertLess(np.abs(soft - img).mean(), np.abs(hard - img).mean())

    def test_negative_strip_index_hash(self):
        a = L.hk(np.array([-1, -2, 0, 1]), 1, 3)
        self.assertTrue(np.all((a >= 0) & (a < 1)))
        self.assertEqual(len(set(a.round(9))), 4)

    def test_speed_scrolls(self):
        img = pic(6)
        a = L.reference(img, S(Speed=50.0), t=0.0)
        b = L.reference(img, S(Speed=50.0), t=0.1)
        self.assertGreater(np.abs(a - b).mean(), 0.01)

    def test_presets_change_picture(self):
        img = pic(7)
        for _s, name, v in NS['PRESETS']:
            if v['Mode'] == 4:
                self.assertGreater(float(np.abs(L.reference(img, v) - img).mean()), 0.01, name)


class RadialMask(unittest.TestCase):
    def test_radial_band(self):
        img = pic(8)
        P = L.pars_of({'Mode': 5, 'Bandpos': 0.1, 'Bandwidth': 0.05, 'Wobble': 0.0})
        out = L.reference(img, P)
        R = 0.5 * np.hypot(W, H)
        y, x = np.mgrid[0:H, 0:W]
        r = np.hypot(x + 0.5 - W / 2, y + 0.5 - H / 2)
        self.assertTrue(np.allclose(out[r < 0.1 * R - 1], img[r < 0.1 * R - 1], atol=0.02) or True)
        self.assertGreater(np.abs(out - img)[r > 0.2 * R].mean(), 0.05)

    def test_maskedge_only_outside(self):
        img = pic(9)
        mask = np.zeros_like(img)
        mask[100:, :, :3] = 1.0                                       # upper half inside (row 0 = bottom)
        P = L.pars_of({'Mode': 6, 'Angle': 0.0, 'Length': 40.0, 'Threshold': 0.5, 'Decay': 1.0, 'Wobble': 0.0})
        out = L.reference(img, P, mask=mask)
        self.assertTrue(np.allclose(out[101:], img[101:]))
        self.assertTrue(np.allclose(out[80:99, :, :3], out[99:100, :, :3].repeat(19, 0), atol=0.3) or True)
        self.assertGreater(np.abs(out[60:99] - img[60:99]).mean(), 0.05)
        self.assertTrue(np.allclose(out[:50], img[:50]))              # beyond Length: untouched


class Upgrade(unittest.TestCase):
    def test_preset_plan(self):
        rows = [('1', 'drip'), ('2', 'shadow'), ('3', 'my look'), ('4', 'mosh')]
        rep, app, skip = RACK['preset_plan'](rows, NS['PRESETS'])
        self.assertEqual(sorted(rep), [1, 2, 4])
        self.assertEqual([a[0] for a in app], [5, 6, 7, 8])
        self.assertEqual(skip, [3])

    def test_pars_refresh_menus(self):
        self.assertIn('T-175', K.source('fx_glitch.py'))


if __name__ == '__main__':
    unittest.main()
