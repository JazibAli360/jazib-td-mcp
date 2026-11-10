"""Offline tests for FX_retro module 'cycle' (builders/fx_retro_cycle.py) + mirror (rack wiring / glslc:
test_fx_retro.py). Run: python3 -I -m unittest discover -s test -p 'test_fx_retro_cycle.py'"""
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import fx_retro_cycle_logic as L  # noqa: E402
import test_fx_retro as T  # noqa: E402

M = T.module('cycle')


def ramp_img():
    x = np.linspace(0, 1, 256)
    a = np.zeros((4, 256, 4))
    a[..., :3] = x[None, :, None]
    a[..., 3] = 1
    return a


class Spec(unittest.TestCase):
    def test_defaults_presets_uniforms(self):
        pars = dict((n, (s, d, o)) for _pg, pl in M['PAGES'] for n, s, d, o in pl)
        for k, v in L.DEFAULTS.items():
            s, d, o = pars[k]
            self.assertAlmostEqual(float(o['names'].index(d) if s == 'Menu' else d), float(v), msg=k)
        for _s, n, vals in M['PRESETS']:
            self.assertEqual(set(vals), set(pars), n)
        U = M['uniforms'](T.RACK['H'])
        for un, ex in U:
            self.assertIn('uniform vec4 %s;' % un, M['FX'])
            for e in ex:
                compile(e, 'u', 'eval')

    def test_shift_expression_wraps(self):
        U = dict(M['uniforms'](T.RACK['H']))
        e = U['uS0'][2]
        class Par:
            def __init__(s, v): s.v = v
            def eval(s): return s.v
        par = type('P', (), {'Indices': Par(32), 'R1start': Par(0.0), 'R1end': Par(1.0), 'R1speed': Par(-8.0)})()
        env = {'math': math, 'absTime': type('A', (), {'seconds': 3.3})(), 'parent': lambda: type('X', (), {'par': par})()}
        v = eval(e, env)
        self.assertTrue(0 <= v < 32)
        self.assertAlmostEqual(v, (-8 * 3.3) % 32)


class Mirror(unittest.TestCase):
    def test_amount_zero(self):
        img = ramp_img()
        self.assertTrue(np.array_equal(L.reference(img, {'Amount': 0.0}), img))

    def test_no_shift_is_quantised_ramp(self):
        out = L.reference(ramp_img(), {'Ramp': 3, 'R1speed': 0.0, 'Blend': 0, 'Indices': 8}, shifts=[0, 0, 0, 0])
        self.assertEqual(len(np.unique(np.round(out[0, :, 0], 6))), 8)

    def test_full_cycle_returns(self):
        img = ramp_img()
        a = L.reference(img, {'Ramp': 0, 'Indices': 16}, shifts=[0, 0, 0, 0])
        b = L.reference(img, {'Ramp': 0, 'Indices': 16}, shifts=[16 % 16, 0, 0, 0])
        c = L.reference(img, {'Ramp': 0, 'Indices': 16}, shifts=[5, 0, 0, 0])
        self.assertTrue(np.allclose(a, b))
        self.assertGreater(np.abs(a - c).mean(), 0.05)

    def test_range_only_moves_its_indices(self):
        img = ramp_img()
        P = {'Ramp': 3, 'Indices': 10, 'Blend': 0, 'R1start': 0.5, 'R1end': 1.0}
        a = L.reference(img, P, shifts=[0, 0, 0, 0])
        b = L.reference(img, P, shifts=[2, 0, 0, 0])
        self.assertTrue(np.allclose(a[:, :128], b[:, :128]))
        self.assertGreater(np.abs(a[:, 128:] - b[:, 128:]).max(), 0.05)

    def test_blend_is_between_steps(self):
        img = ramp_img()
        P = {'Ramp': 3, 'Indices': 8, 'Blend': 1}
        a = L.reference(img, P, shifts=[0, 0, 0, 0])
        h = L.reference(img, P, shifts=[0.5, 0, 0, 0])
        b = L.reference(img, P, shifts=[1, 0, 0, 0])
        self.assertTrue(np.allclose(h[:, :200], 0.5 * (a[:, :200] + b[:, :200])))     # no wrap there: the midpoint


if __name__ == '__main__':
    unittest.main()
