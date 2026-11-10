"""Offline tests for GEN_sim module 'lavalamp' (builders/gen_sim_lavalamp.py, glsl/gen_sim_lava_*.glsl,
gen_sim_logic lava_step / lava_mass). cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_gen_sim_lavalamp.py'"""
import unittest

import numpy as np

import test_gen_sim as K

M = K.module('lavalamp')
L = K.LOGIC


def U(over=None, W=48, H=80, frame=100):
    out = {}
    for name, ex in M['step_uniforms']():
        out[name] = [float(K.ev(e, M, over, in_w=W / 0.4, in_h=H / 0.4, frame=frame)) for e in ex]
    return out


def run(Uu, n, conserve_book=True):
    """Frames of the module: step (npasses) + avg + mass book, like the TD network. Returns states and means."""
    st = np.zeros((1, 1, 4))
    mass = (0.0, 0.0, 0.0, 0.0)
    means = []
    for f in range(n):
        Uu['uRun'][1], Uu['uRun'][3] = float(f), f / 60.0
        for k in range(max(1, int(Uu['uRun'][0]))):
            st = L['lava_step'](st, Uu, mass, k)
        avg = st.mean(axis=(0, 1))
        mass = L['lava_mass'](avg, mass, Uu['uSim'][3])
        means.append(float(avg[2]))
    return st, means


class Uniforms(unittest.TestCase):
    def test_match_shaders(self):
        T = M['shader_texts']()
        K.check_uniforms(self, T['step'], M['step_uniforms'](), 'lava.step')
        K.check_uniforms(self, T['mass'], M['mass_uniforms'](), 'lava.mass')
        K.check_uniforms(self, T['look'], M['look_uniforms'](), 'lava.look')

    def test_presets_full_state(self):
        keys = [set(v) for _s, _n, v in M['PRESETS']]
        self.assertTrue(all(k == keys[0] for k in keys))
        self.assertIn('Heat', keys[0])


class Fluid(unittest.TestCase):
    def test_seeds(self):
        Uu = U({'Fill': 0.3})
        st, _ = run(Uu, 1)
        self.assertEqual(st.shape, (80, 48, 4))
        self.assertAlmostEqual(float(st[..., 2].mean()), 0.3, delta=0.05)     # heavy layer on top
        self.assertGreater(float(st[-5:, :, 2].mean()), 0.9)
        self.assertLess(float(st[:5, :, 2].mean()), 0.1)
        Ub = U({'Seedmode': 'blobs'})
        sb, _ = run(Ub, 1)
        self.assertTrue(0.02 < float(sb[..., 2].mean()) < 0.8)

    def test_density_conserved(self):
        # Conserve on: the mean stays the seeded mean within 1 % (pure mixing and the heated lamp); off: it drifts
        # (sim 108 x 192; the live sim is 432 x 768: the per-frame drift the book removes next frame shrinks with size)
        for heat in (0.0, 0.05):
            Uu = U({'Heat': heat, 'Buoyancy': 0.05}, W=108, H=192)
            st, means = run(Uu, 200)
            self.assertLess(max(abs(m / means[0] - 1.0) for m in means), 0.01, heat)
            self.assertTrue(np.isfinite(st).all())
        Uo = U({'Heat': 0.05, 'Buoyancy': 0.05, 'Conserve': False}, W=108, H=192)
        _st, means = run(Uo, 200)
        self.assertGreater(max(abs(m / means[0] - 1.0) for m in means), 0.01)    # why the book exists

    def test_heavy_sinks(self):
        Uu = U({'Heat': 0.0, 'Buoyancy': 0.05})
        st0, _ = run(Uu, 1)
        st, _ = run(Uu, 150)
        ys = np.arange(80)[:, None]
        com = lambda s: float((s[..., 2] * ys).sum() / s[..., 2].sum())
        self.assertLess(com(st), com(st0) - 3.0)                                 # the heavy fluid moved down

    def test_mass_book(self):
        self.assertEqual(L['lava_mass']((0, 0, 0.4, 0), (0.7, 0.6, 0, 1.0), 2.0), (0.4, 0.4, 0.0, 2.0))   # new epoch
        self.assertEqual(L['lava_mass']((0, 0, 0.41, 0), (0.4, 0.4, 0, 2.0), 2.0), (0.4, 0.41, 0.0, 2.0))


if __name__ == '__main__':
    unittest.main()
