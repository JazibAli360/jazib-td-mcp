"""Offline tests of GEN_interactive 'parallax' (SX-30 / 7C-31 / TC-05; lane F): pages / presets, uniforms vs shader,
glslc, expressions evaluate, reference: zero offset = the colour, a near square slides over a far background
(occlusion order), the march never samples behind a nearer surface.
Run: python3 -I -m unittest discover -s test -p 'test_gen_interactive_parallax.py'"""
import os
import shutil
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_gen_interactive as K  # noqa: E402

M = K.module('parallax')
LG = {}
exec(open(os.path.join(K.B, 'gen_interactive_parallax_logic.py')).read(), LG)
sys.path.insert(0, K.B)
import gen_sim_logic as GL  # noqa: E402


def P(**over):
    d = dict(K.RACK['page_defaults'](M['PAGES']))
    d.update(over)
    return d


def scene(W=64, H=64):
    """Far background: red left / blue right, depth 0; a near (depth 1) green square in the middle."""
    col = np.zeros((H, W, 4))
    col[..., 3] = 1
    col[:, :W // 2, 0] = 1
    col[:, W // 2:, 2] = 1
    dep = np.zeros((H, W, 4))
    col[24:40, 24:40, :3] = (0, 1, 0)
    dep[24:40, 24:40, 0] = 1
    return col, dep


class Parallax(unittest.TestCase):
    def test_pages_uniforms_glslc(self):
        tx = M['shader_texts']()
        K.check_uniforms(self, tx['fx'], M['uniforms'](), 'parallax.fx')
        if shutil.which('glslc'):
            K.glslc(self, tx['fx'], 'parallax.fx')
        self.assertIn('parallax', K.RACK['MODULES'])
        for _u, ex in M['uniforms']():
            for e in ex:
                if "op('pts')" not in e:
                    K.ev(e, M)

    def test_zero_offset_is_colour(self):
        col, dep = scene()
        p = P(Blend=0)
        for (x, y) in ((3, 3), (30, 30), (50, 10)):
            o = LG['pixel'](x, y, col, col, dep, p, (0.0, 0.0), GL.palette, GL.blend)
            np.testing.assert_allclose(o, col[y, x])

    def test_near_square_slides_over_far(self):
        col, dep = scene()
        p = P(Blend=0, Steps=64, Refine=8)
        O = (0.1, 0.0)                                   # near layer (t = 1) moves +0.1 uv = +6.4 px to the right
        g = LG['pixel'](42, 32, col, col, dep, p, O, GL.palette, GL.blend)
        self.assertAlmostEqual(g[1], 1.0)                 # x 42 was blue background: now the green square covers it
        b = LG['pixel'](26, 32, col, col, dep, p, O, GL.palette, GL.blend)
        self.assertLess(b[1], 0.5)                        # the square's old left edge now shows background
        q, t = LG['march']((42.5 / 64, 32.5 / 64), O, 0.0, 64, 8, dep, 0.0, 1.0, False)
        self.assertGreater(t, 0.9)                        # hit on the near layer


if __name__ == '__main__':
    unittest.main()
