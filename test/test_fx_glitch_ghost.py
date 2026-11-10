"""Offline tests for FX_glitch module 'ghost' (builders/fx_glitch_ghost.py + fx_glitch_ghost_logic.py). No TD.
Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_ghost.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import numpy as np  # noqa: E402
import fx_glitch_ghost_logic as L  # noqa: E402

NS = K.load_module('ghost')
W, H = 64, 96


def pic(seed=0):
    rng = np.random.default_rng(seed)
    a = rng.random((H, W, 4))
    a[..., 3] = 1.0
    return a


def moved(a, dx=6):
    b = a.copy()
    b[20:50, 10:40] = a[20:50, 10 + dx:40 + dx]           # a moving block
    return b


class Contract(unittest.TestCase):
    def test_template(self):
        pars = {}
        for _page, plist in NS['PAGES']:
            for name, style, default, o in plist:
                self.assertNotIn(name, pars)
                self.assertTrue(name[0].isupper() and name[1:] == name[1:].lower(), name)
                pars[name] = (style, default, o)
        self.assertEqual(NS['MODULE'], 'ghost')
        self.assertEqual(NS['PAGES'][0][1][0][0], 'Amount')
        self.assertTrue(set(NS['PANEL_PAGES']) <= set(p for p, _ in NS['PAGES']))
        self.assertTrue(3 <= len(NS['PRESETS']) <= 5)
        for _slot, pname, vals in NS['PRESETS']:
            self.assertEqual(vals.get('Amount'), 1.0)
            for k, v in vals.items():
                self.assertIn(k, pars, pname + ' ' + k)
                if pars[k][0] == 'Menu':
                    self.assertTrue(0 <= v < len(pars[k][2]['names']))
        for name, (style, default, o) in pars.items():
            if style == 'Menu':
                self.assertIn(default, o['names'])
                self.assertEqual(len(o['names']), len(o['labels']))
                default = o['names'].index(default)
            if style in ('Float', 'Int'):
                self.assertLess(o['min'], o['max'])
            self.assertEqual(float(default), float(L.DEFAULTS[name]), name)
        self.assertEqual(set(pars), set(L.DEFAULTS))
        self.assertEqual(pars['Mode'][2]['names'], NS['MODES'])
        st, sv = NS['uniforms']()
        K.check_uniforms(self, st, NS['STAMP'], pars)
        K.check_uniforms(self, sv, NS['STATE'], pars)

    def test_presets_full_state(self):
        names = set(n for _pg, pl in NS['PAGES'] for n, _s, _d, _o in pl) - {'Capture'}
        for _slot, pname, vals in NS['PRESETS']:
            self.assertEqual(set(vals), names, pname)                      # T-124 (1): no inheritance

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_ghost.py'))
        self.assertIn('numcolorbufs = 4', K.source('fx_glitch_ghost.py'))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_state(self):
        ok, err = K.glslc(NS['STATE'])
        self.assertTrue(ok, err)

    def test_stamp(self):
        ok, err = K.glslc(NS['STAMP'])
        self.assertTrue(ok, err)

    def test_four_buffers(self):
        # the stub declares one output image; the shader writes buffers 0..3
        import re
        idx = set(int(i) for i in re.findall(r'TDImageStoreOutput\((\d)', NS['STATE']))
        self.assertEqual(idx, {0, 1, 2, 3})


class Behaviour(unittest.TestCase):
    def test_fresh_static_no_motion(self):
        a = pic()
        out, s = L.step(a, None, {'Mode': 0}, stamp=(1.0, 0.0, 1.0))
        self.assertTrue(np.all(out[..., :3] == 0.0))                # ghost: nothing moves -> black back
        out2, _ = L.step(a, s, {'Mode': 0}, stamp=(1.016, 1.0, 1.0))
        self.assertTrue(np.all(out2[..., :3] == 0.0))

    def test_ghost_shows_only_motion(self):
        a = pic(1)
        b = moved(a)
        _o, s = L.step(a, None, {'Mode': 0}, stamp=(1.0, 0.0, 1.0))
        out, _ = L.step(b, s, {'Mode': 0, 'Threshold': 0.05}, stamp=(1.016, 1.0, 1.0))
        moving = np.abs(b - a)[..., :3].max(-1) > 0.15
        self.assertTrue(np.allclose(out[moving], b[moving]))
        still = np.abs(b - a)[..., :3].max(-1) == 0
        self.assertTrue(np.all(out[still][:, :3] == 0.0))

    def test_stale_gap_restarts(self):
        a = pic(2)
        b = moved(a)
        _o, s = L.step(a, None, {'Mode': 0}, stamp=(1.0, 0.0, 1.0))
        out, _ = L.step(b, s, {'Mode': 0}, stamp=(2.0, 1.0, 1.0))      # 1 s gap: fresh
        self.assertTrue(np.all(out[..., :3] == 0.0))

    def test_trails_decay(self):
        a = pic(3)
        b = moved(a)
        pr = {'Mode': 2, 'Decay': 0.5, 'Back': 0}
        _o, s = L.step(a, None, pr, stamp=(1.0, 0.0, 1.0))
        o1, s = L.step(b, s, pr, stamp=(1.0 + 1 / 60.0, 1.0, 1.0))
        o2, s = L.step(b, s, pr, stamp=(1.0 + 2 / 60.0, 1.0 + 1 / 60.0, 1.0))
        moving = np.abs(b - a)[..., :3].max(-1) > 0.15
        self.assertTrue(np.allclose(o2[moving][:, :3], o1[moving][:, :3] * 0.5))

    def test_plate_subtract(self):
        bg = pic(4)
        fg = bg.copy()
        fg[30:60, 20:40, :3] = 0.95 - bg[30:60, 20:40, :3] * 0.0
        _o, s = L.step(bg, None, {'Mode': 3}, stamp=(1.0, 0.0, 1.0))           # first cook grabs the plate
        for i in range(1, 4):
            out, s = L.step(fg, s, {'Mode': 3, 'Back': 2, 'Threshold': 0.1},
                            stamp=(1.0 + i / 60.0, 1.0 + (i - 1) / 60.0, 1.0))
        diff = np.abs(fg - bg)[..., :3].max(-1)
        self.assertTrue(np.allclose(out[diff > 0.3], fg[diff > 0.3]))
        self.assertTrue(np.all(out[diff == 0] == 0.0))

    def test_glow_only_adds(self):
        a = pic(5)
        b = moved(a)
        _o, s = L.step(a, None, {'Mode': 1}, stamp=(1.0, 0.0, 1.0))
        out, _ = L.step(b, s, {'Mode': 1}, stamp=(1.016, 1.0, 1.0))
        self.assertTrue(np.all(out[..., :3] >= b[..., :3] - 1e-12))
        self.assertGreater(float((out - b)[..., :3].max()), 0.5)

    def test_mask_view(self):
        a = pic(6)
        b = moved(a)
        _o, s = L.step(a, None, {'Mode': 0, 'View': 1}, stamp=(1.0, 0.0, 1.0))
        out, _ = L.step(b, s, {'Mode': 0, 'View': 1}, stamp=(1.016, 1.0, 1.0))
        self.assertTrue(np.all((out[..., 0] >= 0) & (out[..., 0] <= 1)))
        self.assertTrue(np.all(out[..., 3] == 1.0))
        self.assertGreater(float(out[..., 0].mean()), 0.01)

    def test_amount_mix(self):
        a = pic(7)
        out, _ = L.step(a, None, {'Amount': 0.0}, stamp=(1.0, 0.0, 1.0))
        self.assertTrue(np.array_equal(out, a))

    def test_f16_static_noise_below_threshold(self):
        a = pic(8)
        d = np.abs(L.f16(a) - a).max()
        self.assertLess(d, 5e-4)
        self.assertLess(d, L.DEFAULTS['Threshold'])


if __name__ == '__main__':
    unittest.main()
