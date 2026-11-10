"""Offline tests of GEN_interactive 'skinner' (FX7c 7C-25; lane F): uniforms vs shaders, glslc of slots / tris / draw,
references: slots land inside the mask and stay (respawn 0), hold on a second cook in the same frame, shards use
valid slots with the longest edge in range, a shard is drawn (fill inside, edge on its border).
Run: python3 -I -m unittest discover -s test -p 'test_gen_interactive_skinner.py'"""
import math
import os
import shutil
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_gen_interactive as K  # noqa: E402

M = K.module('skinner')
LG = {'HERE': K.B}
exec(open(os.path.join(K.B, 'gen_interactive_skinner_logic.py')).read(), LG)
W, H = 270.0, 480.0


def P(**over):
    d = dict(K.RACK['page_defaults'](M['PAGES']))
    d.update(over)
    return d


def mask():
    m = np.zeros((120, 68, 4))
    m[30:90, 20:48, 0] = 1.0                                 # a body in the middle
    m[30:90, 20:48, 1] = 0.5
    return m


class Skinner(unittest.TestCase):
    def test_uniforms_glslc(self):
        tx = M['shader_texts']()
        for k, U in (('slots', M['slots_uniforms']()), ('tris', M['tris_uniforms']()), ('draw', M['draw_uniforms']())):
            K.check_uniforms(self, tx[k], U, 'skinner.' + k)
            if shutil.which('glslc'):
                K.glslc(self, tx[k], 'skinner.' + k)
            for _u, ex in U:
                for e in ex:
                    K.ev(e, M)
        self.assertIn('skinner', K.RACK['MODULES'])

    def test_slots_inside_and_hold(self):
        p = P(Slots=100, Respawn=0.0)
        mk = mask()
        s0 = LG['slots_step'](None, mk, p, {'now': 1.0, 'epoch': 1.0}, W, H)
        s1 = LG['slots_step'](s0, mk, p, {'now': 1.0 + 1 / 60., 'epoch': 1.0}, W, H)
        v = s1[:2].reshape(-1, 4)[:100]
        ok = v[v[:, 2] > 0.5]
        self.assertGreater(len(ok), 90)
        for x, y, _a, _m in ok:
            self.assertGreater(LG['sample'](mk, x / W, y / H, 0), 0.5)
        s2 = LG['slots_step'](s1, mk, p, {'now': 1.0 + 2 / 60., 'epoch': 1.0}, W, H)
        kept = s1[:2, :, 2] > 0.5
        np.testing.assert_allclose(s2[:2][kept][:, :2], s1[:2][kept][:, :2])   # respawn 0: valid points stay
        same = LG['slots_step'](s2, mk, p, {'now': 1.0 + 2 / 60., 'epoch': 1.0}, W, H)
        self.assertEqual(float(np.abs(same - s2).max()), 0.0)

    def test_tris_and_draw(self):
        p = P(Slots=200, Shards=64, Minlen=20.0, Maxlen=400.0, Density=1.0)
        mk = mask()
        s = LG['slots_step'](None, mk, p, {'now': 1.0, 'epoch': 1.0}, W, H)
        s = LG['slots_step'](s, mk, p, {'now': 1.0 + 1 / 60., 'epoch': 1.0}, W, H)
        tr = LG['tris'](s, p)
        self.assertEqual(tr.shape, (1, 128, 4))
        shown = [j for j in range(64) if tr[0, 2 * j + 1, 2] > 0]
        self.assertGreater(len(shown), 10)
        j = shown[0]
        a, b = tr[0, 2 * j], tr[0, 2 * j + 1]
        L = max(math.hypot(a[2] - a[0], a[3] - a[1]), math.hypot(b[0] - a[2], b[1] - a[3]), math.hypot(a[0] - b[0], a[1] - b[1]))
        self.assertTrue(20.0 <= L <= 400.0)
        cx, cy = (a[0] + a[2] + b[0]) / 3, (a[1] + a[3] + b[1]) / 3
        tot, _t = LG['pixel'](int(cx), int(cy), tr, p)
        self.assertGreater(tot, 0.0)


if __name__ == '__main__':
    unittest.main()
