"""Offline tests for FX_retro module 'ps1' (builders/fx_retro_ps1.py) + mirror fx_retro_ps1_logic.py (rack wiring /
glslc of the rack pass: test_fx_retro.py; the MAT shaders here against GLSL MAT stubs). Run:
python3 -I -m unittest discover -s test -p 'test_fx_retro_ps1.py'"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import fx_retro_ps1_logic as L  # noqa: E402
import test_fx_retro as T  # noqa: E402

M = T.module('ps1')
VSTUB = """#version 460
in vec3 P; in vec3 N; in vec3 uv[1];
vec4 TDDeform(vec3 p) { return vec4(p, 1.0); }
vec3 TDDeformNorm(vec3 n) { return n; }
uniform mat4 uMVP;
vec4 TDWorldToProj(vec4 w) { return uMVP * w; }
void TDWritePickingValues() {}
"""
PSTUB = """#version 460
void TDCheckDiscard() {}
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""


def glslc(stub, text, stage):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.' + stage)
        with open(p, 'w') as fh:
            fh.write(stub + text)
        r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations', '-o',
                            os.devnull, p], capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:2000]


def pic(seed=0):
    a = np.random.default_rng(seed).random((96, 64, 4))
    a[..., 3] = 1
    return a


class Spec(unittest.TestCase):
    def test_defaults_presets(self):
        pars = dict((n, (s, d, o)) for _pg, pl in M['PAGES'] for n, s, d, o in pl)
        for k, v in L.DEFAULTS.items():
            s, d, o = pars[k]
            self.assertAlmostEqual(float(o['names'].index(d) if s == 'Menu' else d), float(v), msg=k)
        for _s, pname, vals in M['PRESETS']:
            self.assertEqual(set(vals), set(pars), pname)

    def test_uniforms(self):
        for un, _e in M['uniforms'](T.RACK['H']):
            self.assertIn('uniform vec4 %s;' % un, M['FX'])

    @unittest.skipUnless(shutil.which('glslc'), 'glslc')
    def test_mat_shaders_compile(self):
        ok, err = glslc(VSTUB, M['MAT_VERT'], 'vert')
        self.assertTrue(ok, err)
        ok, err = glslc(PSTUB, M['MAT_PIXEL'], 'frag')
        self.assertTrue(ok, err)
        self.assertIn('noperspective', M['MAT_VERT'])


class Mirror(unittest.TestCase):
    def test_amount_zero(self):
        img = pic()
        self.assertTrue(np.array_equal(L.reference(img, {'Amount': 0.0}), img))

    def test_15bit_levels(self):
        out = L.reference(pic(1), {'Dither': 1})
        v = np.unique(np.round(out[..., :3] * 31, 6))
        self.assertTrue(np.allclose(v, np.round(v)))
        self.assertLessEqual(len(v), 32)

    def test_blocks(self):
        out = L.reference(pic(2), {'Dither': 1, 'Downscale': 4.0})
        for j in range(0, 96, 4):
            for i in range(0, 64, 4):
                self.assertLess(np.ptp(out[j:j + 4, i:i + 4, :3].reshape(-1, 3), axis=0).max(), 1e-12)

    def test_psx_dither_mean_preserved(self):
        img = np.full((64, 64, 4), 0.5)
        img[..., 3] = 1
        out = L.reference(img, {'Downscale': 1.0, 'Bits': 5})
        self.assertLess(abs(out[..., 0].mean() - 0.5), 0.03)
        self.assertGreater(len(np.unique(out[..., 0])), 1)                 # dither makes a pattern

    def test_wobble_warps_and_epochs_differ(self):
        img = pic(3)
        a = L.render(img, L.pars_of({'Wobble': 6.0, 'Wobblesize': 32.0}), epoch=1)
        b = L.render(img, L.pars_of({'Wobble': 6.0, 'Wobblesize': 32.0}), epoch=2)
        n = L.render(img, L.pars_of({}), epoch=1)
        self.assertGreater(np.abs(a - n).mean(), 0.01)
        self.assertGreater(np.abs(a - b).mean(), 0.01)

    def test_wobble_continuous_across_triangles(self):
        # piecewise-affine displacement: adjacent pixels move by < 2 x Wobble / Wobblesize px per px
        P = L.pars_of({'Wobble': 4.0, 'Wobblesize': 40.0, 'Downscale': 1.0, 'Dither': 1, 'Bits': 8})
        y, x = np.mgrid[0:96, 0:64]
        img = np.stack([x / 64.0, y / 96.0, np.zeros_like(x, float), np.ones_like(x, float)], -1)
        out = L.render(img, P, epoch=3)
        self.assertLess(np.abs(np.diff(out[..., 0], axis=1)).max(), 0.05)


if __name__ == '__main__':
    unittest.main()
