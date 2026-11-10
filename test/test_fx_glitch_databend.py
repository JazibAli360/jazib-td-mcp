"""Offline tests for FX_glitch module 'databend' (builders/fx_glitch_databend.py + fx_glitch_databend_logic.py).
Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_databend.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import numpy as np  # noqa: E402
import fx_glitch_databend_logic as L  # noqa: E402

NS = K.load_module('databend')
W, H = 40, 30


def pic(seed=0):
    a = np.floor(np.random.default_rng(seed).random((H, W, 4)) * 255) / 255
    a[..., 3] = 1
    return a


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'databend')
        self.assertEqual(pars['Effect'][2]['names'], L.EFFECTS)
        self.assertEqual(set(pars), set(L.DEFAULTS))
        K.check_uniforms(self, NS['uniforms'](), NS['SHADER'], pars)
        for _s, n, v in NS['PRESETS']:
            self.assertEqual(set(v), set(pars), n)

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_databend.py'))

    @unittest.skipUnless(K.HAVE_GLSLC, 'glslc')
    def test_glslc(self):
        ok, err = K.glslc(NS['SHADER'])
        self.assertTrue(ok, err)


class Stream(unittest.TestCase):
    def test_roundtrip_orders(self):
        img = pic()
        for o in range(3):
            s = L.to_stream(img, o)
            self.assertTrue(np.allclose(L.from_stream(s, H, W, o) / 255.0, img[..., :3]))

    def test_rows_order_is_top_row_first_interleaved(self):
        img = pic(1)
        s = L.to_stream(img, 0)
        self.assertEqual(s[0], np.floor(img[H - 1, 0, 0] * 255 + 0.5))
        self.assertEqual(s[4], np.floor(img[H - 1, 1, 1] * 255 + 0.5))

    def test_amount_zero_and_mix_zero(self):
        img = pic(2)
        self.assertTrue(np.array_equal(L.reference(img, {'Amount': 0.0}), img))
        for e in range(9):
            self.assertTrue(np.allclose(L.reference(img, {'Effect': e, 'Mix': 0.0}), img), e)

    def test_delay_shifts_stream(self):
        img = pic(3)
        out = L.reference(img, {'Effect': 1, 'Delay': 3 * W, 'Mix': 1.0})      # one row down (next row = later)
        self.assertTrue(np.allclose(out[:H - 1, :, :3], img[1:, :, :3]))
        self.assertTrue(np.all(out[H - 1, :, :3] == 0))                       # top row: silence

    def test_hold_and_reverse(self):
        x = np.arange(20, dtype=float)
        self.assertEqual(list(L.bend(x, L.pars_of({'Effect': 5, 'Hold': 4, 'Mix': 1.0}))[:8]), [0, 0, 0, 0, 4, 4, 4, 4])
        self.assertEqual(list(L.bend(x, L.pars_of({'Effect': 6, 'Chunk': 5, 'Mix': 1.0}))[:5]), [4, 3, 2, 1, 0])

    def test_crush_levels(self):
        y = L.bend(np.arange(256.0), L.pars_of({'Effect': 4, 'Bits': 3, 'Mix': 1.0}))
        self.assertEqual(len(np.unique(y)), 8)

    def test_lowpass_smooths_highpass_centres(self):
        x = np.tile([0.0, 255.0], 200)
        lp = L.bend(x, L.pars_of({'Effect': 2, 'Cutoff': 0.1, 'Taps': 32, 'Mix': 1.0}))
        self.assertLess(np.std(lp[100:]), 40)
        hp = L.bend(np.full(100, 77.0), L.pars_of({'Effect': 3, 'Cutoff': 0.2, 'Taps': 8, 'Mix': 1.0}))
        self.assertTrue(np.all(hp[10:] == 128))

    def test_presets_change_picture(self):
        img = pic(4)
        img = np.repeat(np.repeat(img, 3, 0), 3, 1)
        for _s, n, v in NS['PRESETS']:
            self.assertGreater(np.abs(L.reference(img, v) - img).mean(), 0.003, n)


if __name__ == '__main__':
    unittest.main()
