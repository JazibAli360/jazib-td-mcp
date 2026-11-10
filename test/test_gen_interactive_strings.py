"""Offline tests of GEN_interactive 'strings' (FX7b TC-28; lane F): pages / full-state presets, uniforms vs shaders,
glslc of step + draw, physics reference properties (rest stays at rest, push bends away, pinned ends, springs back,
same-frame hold, beat kick once), draw reference (rest strings drawn at their rest x).
Run: python3 -I -m unittest discover -s test -p 'test_gen_interactive_strings.py'"""
import math
import os
import shutil
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_gen_interactive as K  # noqa: E402

M = K.module('strings')
B = K.B
LG = {}
exec(open(os.path.join(B, 'gen_interactive_strings_logic.py')).read(), LG)
W, H = 270.0, 480.0


def P(**over):
    d = dict(K.RACK['page_defaults'](M['PAGES']))
    d.update(over)
    return d


def U(now, epoch=1.0, beats=0.0):
    return {'now': now, 'epoch': epoch, 'beats': beats, 'bpm': 120.0, 'level': 0.0}


def run(p, pts, steps, t0=10.0, dt=1 / 60.0, beats=None):
    st = LG['step'](None, pts, None, p, U(t0), W, H)
    for i in range(steps):
        st = LG['step'](st, pts, None, p, U(t0 + (i + 1) * dt, beats=(beats or (lambda j: 0.0))(i)), W, H)
    return st


class Strings(unittest.TestCase):
    def test_pages_presets(self):
        names = [n for _pg, pl in M['PAGES'] for n, _s, _d, _o in pl]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(M['PAGES'][0][1][0][0], 'Amount')
        for _s, _n, vals in M['PRESETS']:
            self.assertIn('Tension', vals)                         # full state
        self.assertIn('strings', K.RACK['MODULES'])

    def test_uniforms_and_glslc(self):
        tx = M['shader_texts']()
        K.check_uniforms(self, tx['step'], M['step_uniforms'](), 'strings.step')
        K.check_uniforms(self, tx['draw'], M['draw_uniforms'](), 'strings.draw')
        K.check_uniforms(self, tx['cbox'], M['cbox_uniforms'](), 'strings.cbox')
        if shutil.which('glslc'):
            K.glslc(self, tx['cbox'], 'strings.cbox')
            K.glslc(self, tx['step'], 'strings.step')
            K.glslc(self, tx['draw'], 'strings.draw')
        for _u, ex in M['step_uniforms']() + M['draw_uniforms']() + M['cbox_uniforms']():
            for e in ex:
                K.ev(e, M)

    def test_rest_stays(self):
        st = run(P(Strings=4, Nodes=16), np.full((4, 4), -10.0), 30)
        self.assertEqual(float(np.abs(st[:4]).max()), 0.0)
        self.assertAlmostEqual(st[4, 0, 1], 30 / 60.0, places=9)    # module time T

    def test_push_bends_away_and_pins(self):
        p = P(Strings=4, Nodes=32, Radius=80.0)
        s1x = LG['rest'](1, 16, 4, 32, p, W, H)[0]
        pts = np.array([[(s1x + 20.0) / W, 0.5, 0, 0]] + [[-10.0, -10.0, 0, 0]] * 3)
        st = run(p, pts, 40)
        self.assertLess(st[1, 16, 0], -5.0)                         # string 1 pushed left, away from the point
        self.assertEqual(float(np.abs(st[1, 0]).max()), 0.0)        # pinned ends
        self.assertEqual(float(np.abs(st[1, 31]).max()), 0.0)
        free = run(p, np.full((4, 4), -10.0), 0)
        st2 = st
        for i in range(600):                                        # point gone: springs back
            st2 = LG['step'](st2, np.full((4, 4), -10.0), None, p, U(10.0 + 41 / 60.0 + i / 60.0), W, H)
        self.assertLess(float(np.abs(st2[:4, :, :2]).max()), 0.5)
        self.assertEqual(free.shape, (5, 32, 4))

    def test_same_frame_holds_and_kick_once(self):
        p = P(Strings=2, Nodes=8, Kick=500.0)
        st = LG['step'](None, None, None, p, U(5.0, beats=0.0), W, H)
        st1 = LG['step'](st, None, None, p, U(5.0 + 1 / 60.0, beats=1.0), W, H)
        self.assertGreater(abs(st1[0, 4, 2]), 100.0)                # kicked
        again = LG['step'](st1, None, None, p, U(5.0 + 1 / 60.0, beats=1.0), W, H)
        self.assertEqual(float(np.abs(again - st1).max()), 0.0)      # same frame: hold
        st2 = LG['step'](st1, None, None, p, U(5.0 + 2 / 60.0, beats=1.0), W, H)
        self.assertLess(abs(st2[0, 4, 2]), abs(st1[0, 4, 2]))       # no second kick in the same beat

    def test_draw_rest(self):
        p = P(Strings=4, Nodes=16, Glow=0.0, Linewidth=2.0)
        st = run(p, np.full((4, 4), -10.0), 1)
        x = LG['rest'](2, 5, 4, 16, p, W, H)[0]
        core, glow, t = LG['pixel'](int(x), 200, st, p, W, H)
        self.assertGreater(core, 0.9)
        core2, _g, _t = LG['pixel'](int(x) + 10, 200, st, p, W, H)
        self.assertEqual(core2, 0.0)


if __name__ == '__main__':
    unittest.main()
