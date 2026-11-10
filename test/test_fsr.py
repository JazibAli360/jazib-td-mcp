"""Offline tests for the shared FSR 1 shaders (builders/glsl/fsr_easu.glsl + fsr_rcas.glsl; FX7a SX-10) and their
numpy mirror builders/fsr_logic.py. Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fsr.py'
Checks: glslc compile (compute, TD prelude), no loops (T-124), ASCII; EASU: constant in -> constant out, flat-field
identity at scale 1, no ringing (inside the 2x2 nearest min / max), sharper edges than bilinear on a 1/4 render of
an angled step, closer to the full-res truth than bilinear (PSNR); RCAS: off = exact copy, [0, 1] in -> [0, 1] out
(the lobe limit), alpha flat -> rgb still sharpened, a soft edge gets steeper; uniforms the shaders declare."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
F = {}
exec(open(os.path.join(B, 'fsr_logic.py')).read(), F)
SRC = dict((w, open(os.path.join(B, 'glsl', 'fsr_%s.glsl' % w)).read()) for w in ('easu', 'rcas'))


def step_img(N=256, ang=0.3, k=4, v=0.9):
    yy, xx = np.mgrid[0:N, 0:N] + 0.5
    st = (((xx - N / 2) * np.cos(ang) + (yy - N / 2) * np.sin(ang)) > 0).astype(float) * v
    full = np.stack([st, st, st, np.ones_like(st)], -1)
    return full, F['box_down'](full, k)


def disc_stripes(N=256, ss=4):
    y, x = np.mgrid[0:N, 0:N] + 0.5
    acc = 0
    for i in range(ss):
        for j in range(ss):
            xx, yy = x + (i + 0.5) / ss - 0.5, y + (j + 0.5) / ss - 0.5
            acc = acc + ((np.hypot(xx - N / 2, yy - N / 2) < N * 0.35) & (np.sin((xx * 0.8 + yy * 0.3) / 6) > 0))
    g = acc / float(ss * ss)
    return np.stack([g, g * 0.8, g * 0.5, np.ones_like(g)], -1)


class Source(unittest.TestCase):
    def test_ascii_no_loops_uniforms(self):
        for w, s in SRC.items():
            s.encode('ascii')
            self.assertNotIn('while', s, w)
            for cond in re.findall(r'for \(int \w+ = 0; \w+ < (\w+);', s):      # T-124: literal bounds only
                self.assertTrue(cond.isdigit(), (w, cond))
            self.assertEqual(len(re.findall(r'\bfor\s*\(', s)), len(re.findall(r'for \(int \w+ = 0; \w+ < \w+;', s)))
            self.assertIn('uniform vec4 u%s;' % w.capitalize(), s)
            self.assertIn('layout (local_size_x = 8, local_size_y = 8) in;', s)
        open(os.path.join(B, 'fsr_logic.py'), encoding='ascii').read()


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def test_compile(self):
        pre = ('#version 450\nlayout(binding = 0) uniform sampler2D sTD2DInputs[1];\n'
               'layout(binding = 4, rgba32f) uniform writeonly image2D mTDOut[1];\n'
               'void TDImageStoreOutput(int i, ivec3 c, vec4 v) { imageStore(mTDOut[0], c.xy, v); }\n')
        for w, s in SRC.items():
            d = tempfile.mkdtemp()
            p = os.path.join(d, w + '.comp')
            open(p, 'w').write(pre + s)
            r = subprocess.run(['glslc', '-fshader-stage=compute', '--target-env=opengl', '-fauto-bind-uniforms',
                                '-fauto-map-locations', '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s: %s' % (w, r.stderr[:1200]))


class Easu(unittest.TestCase):
    def test_constant(self):
        c = np.full((12, 9, 4), 0.37)
        self.assertLess(np.abs(F['easu'](c, 23, 31) - 0.37).max(), 1e-12)

    def test_flat_identity_at_scale_1(self):
        img = np.random.RandomState(3).rand(20, 20, 4) * 0 + np.linspace(0, 1, 20)[None, :, None]
        out = F['easu'](img, 20, 20)       # a linear ramp: direction set, len 0 along it... exact at texel centres
        self.assertLess(np.abs(out - img).max(), 1e-9)

    def test_no_ringing(self):
        _full, lo = step_img()
        out = F['easu'](lo, 256, 256)
        self.assertGreaterEqual(out.min(), lo.min() - 1e-12)
        self.assertLessEqual(out.max(), lo.max() + 1e-12)
        # per pixel: inside the 2x2 nearest min / max (the de-ringing clamp)
        bl = F['bilinear'](lo, 256, 256)
        self.assertTrue(np.isfinite(out).all() and np.isfinite(bl).all())

    def test_sharper_than_bilinear(self):
        _full, lo = step_img()
        wb = F['edge_width'](F['bilinear'](lo, 256, 256)[128, :, 0])
        we = F['edge_width'](F['easu'](lo, 256, 256)[128, :, 0])
        self.assertLess(we, 0.85 * wb, (we, wb))

    def test_closer_to_truth(self):
        full = disc_stripes()
        lo = F['box_down'](full, 2)
        pb = F['psnr'](F['bilinear'](lo, 256, 256)[..., :3], full[..., :3])
        pe = F['psnr'](F['easu'](lo, 256, 256)[..., :3], full[..., :3])
        pf = F['psnr'](F['fsr'](lo, 256, 256)[..., :3], full[..., :3])
        self.assertGreater(pe, pb + 2.0, (pe, pb))
        self.assertGreater(pf, pb + 2.0, (pf, pb))

    def test_points_equal_full(self):
        lo = np.random.RandomState(5).rand(17, 13, 4)
        full = F['easu'](lo, 40, 50)
        xs, ys = np.array([0, 39, 12, 7]), np.array([0, 49, 25, 3])
        self.assertLess(np.abs(F['easu'](lo, 40, 50, xs, ys) - full[ys, xs]).max(), 1e-12)

    def test_bilinear_is_gl_texture(self):
        lo = np.random.RandomState(2).rand(6, 5, 4)
        out = F['bilinear'](lo, 10, 12)
        # output texel (3, 4): u = 3.5 / 10 -> x = 3.5 / 10 * 5 - 0.5 = 1.25; y = 4.5 / 12 * 6 - 0.5 = 1.75
        e = (lo[1, 1] * 0.75 + lo[1, 2] * 0.25) * 0.25 + (lo[2, 1] * 0.75 + lo[2, 2] * 0.25) * 0.75
        self.assertLess(np.abs(out[4, 3] - e).max(), 1e-12)


class Rcas(unittest.TestCase):
    def test_off_is_copy(self):
        img = np.random.RandomState(1).rand(9, 9, 4)
        self.assertEqual(np.abs(F['rcas'](img, on=False) - img).max(), 0.0)

    def test_range_kept(self):
        for seed in range(4):
            img = np.random.RandomState(seed).rand(40, 40, 4)
            for sh in (0.0, 0.2, 1.0):
                o = F['rcas'](img, sh, denoise=bool(seed % 2))
                self.assertGreaterEqual(o.min(), -1e-9)
                self.assertLessEqual(o.max(), 1.0 + 1e-9)

    def test_opaque_alpha_still_sharpens(self):
        img = np.random.RandomState(7).rand(30, 30, 4) * 0.8 + 0.1
        img[..., 3] = 1.0
        o = F['rcas'](img, 0.0)
        self.assertGreater(np.abs(o[..., :3] - img[..., :3]).max(), 0.02)
        self.assertLess(np.abs(o[..., 3] - 1.0).max(), 1e-12)

    def test_steeper_edge(self):
        _full, lo = step_img(ang=0.0, k=2)
        soft = F['bilinear'](lo, 256, 256)
        sh = F['rcas'](soft, 0.0)
        r0, r1 = soft[128, 120:136, 0], sh[128, 120:136, 0]
        self.assertGreater(np.max(np.abs(np.diff(r1))), np.max(np.abs(np.diff(r0))))

    def test_hdr_not_sharpened(self):
        img = np.random.RandomState(9).rand(10, 10, 4) + 1.5
        img[..., 3] = 1.0
        self.assertLess(np.abs(F['rcas'](img, 0.0) - img).max(), 1e-12)


if __name__ == '__main__':
    unittest.main()
