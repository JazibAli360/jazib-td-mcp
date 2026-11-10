"""Offline tests for GEN_sim module 'ripple' (builders/gen_sim_ripple.py, glsl/gen_sim_ripple_*.glsl,
gen_sim_logic ripple_step). cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sim_ripple.py'"""
import math
import unittest

import numpy as np

import test_gen_sim as K

M = K.module('ripple')
L = K.LOGIC


def U(over=None, W=64, H=48, frame=100):
    """The step uniforms evaluated like TD would (defaults + over), sim W x H."""
    out = {}
    for name, ex in M['step_uniforms']():
        out[name] = [float(K.ev(e, M, over, in_w=W * 2, in_h=H * 2, frame=frame)) for e in ex]
    return out


def flat(Uu):
    st = L['ripple_step'](np.zeros((1, 1, 4)), Uu)          # epoch mismatch -> seeds flat water at sim size
    return st


class Uniforms(unittest.TestCase):
    def test_match_shaders(self):
        T = M['shader_texts']()
        K.check_uniforms(self, T['step'], M['step_uniforms'](), 'ripple.step')
        K.check_uniforms(self, T['look'], M['look_uniforms'](), 'ripple.look')
        for fn in (M['step_uniforms'], M['look_uniforms']):
            for _u, ex in fn():
                for e in ex:
                    if 'op(' in e and 'pal_callbacks' in e:
                        continue                                  # the palette count needs the TD palmap DAT
                    float(K.ev(e, M))

    def test_shared_palette_hook(self):
        t = M['shader_texts']()['look']
        self.assertIn('if (m == 7) return pxPal(u);', t)
        self.assertIn('uniform vec4 uPal[PX_PAL_MAX];', t)

    def test_presets_full_state(self):
        P = K.pars(M)
        keys = None
        for _s, _n, vals in M['PRESETS']:
            ks = set(vals)
            keys = ks if keys is None else keys
            self.assertEqual(ks, keys)                            # every preset sets the same full set
        self.assertIn('Rain', keys)
        self.assertNotIn('Resetcount', keys)
        self.assertNotIn('Hitn', keys)


class Water(unittest.TestCase):
    def test_seed_is_flat_and_records_hits(self):
        Uu = U({'Hitn': 5})
        st = flat(Uu)
        self.assertEqual(st.shape, (48, 64, 4))
        self.assertEqual(float(np.abs(st[..., :2]).max()), 0.0)
        self.assertEqual(float(st[0, 0, 2]), 5.0)                # old hits are never replayed

    def test_one_drop_per_hit(self):
        Uu = U({'Rain': 0.0, 'Hitpos': 'centre', 'Hitn': 0})
        st = flat(Uu)
        Uu['uHit'][0] = 1.0                                       # one Hit pulse
        a = L['ripple_step'](st, Uu, 0)
        self.assertEqual(float(a[0, 0, 2]), 1.0)
        self.assertLess(float(a[24, 32, 0]), -1.0)               # dent at the centre
        b = L['ripple_step'](a, Uu, 0)                            # next frame: not applied again
        Un = dict(Uu, uHit=[1.0, 0.0] + Uu['uHit'][2:])          # = the same step with a zero-strength hit
        self.assertEqual(float(np.abs(b - L['ripple_step'](a, Un, 0)).max()), 0.0)
        Uu['uHit'][0] = 3.0
        c = L['ripple_step'](b, Uu, 0)
        self.assertEqual(float(c[0, 0, 2]), 3.0)

    def test_energy_decays_at_the_damping_rate(self):
        # free waves (no rain / hits), wrap: energy x Damp per step (|root|^2 = Damp), numpy 1e-3
        for d in (0.99, 0.995):
            Uu = U({'Rain': 0.0, 'Edges': 'wrap', 'Damp': d, 'Steps': 1}, W=64, H=64)
            st = flat(Uu)
            ys, xs = np.mgrid[0:64, 0:64]
            st[..., 0] = np.sin(2 * math.pi * 3 * xs / 64.0) * np.cos(2 * math.pi * 2 * ys / 64.0)
            st[..., 1] = st[..., 0]
            e = []
            for _k in range(400):
                st = L['ripple_step'](st, Uu, 0)
                e.append(L['ripple_energy'](st))
            # one mode: E oscillates with the phase; 100-step window means 200 steps apart -> the decay per step
            avg = lambda a, b: sum(e[a:b]) / (b - a)
            per2 = (math.log(avg(300, 400)) - math.log(avg(100, 200))) / 200.0
            self.assertLess(abs(per2 - math.log(d)), 1e-3)

    def test_stable_at_max_speed(self):
        # (Damp 1 never damps the mean level: constant rain then sinks the whole pond, by design, no limiter)
        Uu = U({'Rain': 30.0, 'Wavespeed': 1.0, 'Damp': 0.995, 'Edges': 'reflect'}, W=40, H=40)
        st = flat(Uu)
        for f in range(300):
            Uu['uWave'][3] = float(f)
            st = L['ripple_step'](st, Uu, 0)
        self.assertLess(float(np.abs(st[..., 0]).max()), 50.0)   # no blow-up (c2 = 0.5 is the CFL limit)

    def test_rain_rate(self):
        Uu = U({'Rain': 120.0, 'Steps': 1})                     # 2 drops per step
        self.assertAlmostEqual(Uu['uRain'][0], 2.0)
        st = flat(Uu)
        n = 0
        for f in range(50):
            Uu['uWave'][3] = float(f)
            for j in range(4):
                n += float(L['hash3'](f * 8, j, 1)) < 2.0 - j
        self.assertEqual(n, 100)


if __name__ == '__main__':
    unittest.main()
