"""Offline tests for FX_destroy module 'explode' (builders/fx_destroy_explode.py + fx_destroy_explode_logic.py). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_destroy_explode.py'
GLSL is compiled with glslc (OpenGL target) against TD stubs: a syntax/type check, not a TD compile (that is live)."""
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
sys.path.insert(0, B)
import fx_destroy_explode_logic as L  # noqa: E402

RACK = {}
exec(open(os.path.join(B, 'fx_destroy.py')).read(), RACK)
NS = dict(RACK)
exec(open(os.path.join(B, 'fx_destroy_explode.py')).read(), NS)


def defaults():
    d = {}
    for _page, pars in NS['PAGES']:
        for name, style, default, _o in pars:
            if style == 'RGB':
                for k, v in zip('rgb', default):
                    d[name + k] = v
            elif style == 'Menu':
                d[name] = 0
            elif style not in ('Pulse', 'TOP', 'COMP', 'CHOP'):
                d[name] = float(default) if style == 'Float' else int(default)
    return d


class Spec(unittest.TestCase):
    def test_pages_presets(self):
        names = {}
        for _p, pars in NS['PAGES']:
            for name, style, default, o in pars:
                names[name if style != 'RGB' else name + 'r'] = (style, o)
        self.assertEqual(NS['PAGES'][0][1][0][0], 'Amount')
        for k in ('Trigger', 'Reset', 'Beatchop', 'Effector', 'Hittime', 'Resettime', 'Tilt', 'Return'):
            self.assertIn(k, names)
        self.assertTrue(3 <= len(NS['PRESETS']) <= 5)
        for _s, _n, vals in NS['PRESETS']:
            for k, v in vals.items():
                self.assertIn(k, names, k)
                if names[k][0] == 'Menu':
                    self.assertTrue(0 <= v < len(names[k][1]['names']))
        for pg in NS['PANEL_PAGES']:
            self.assertIn(pg, [p for p, _ in NS['PAGES']])

    def test_grid_fits(self):
        for cells in (2, 24, 48):
            for asp in (0.5, 1.0, 2.0):
                st, rows, cw, ch = L.grid(1080, 1920, cells, asp)
                self.assertLessEqual(st * rows, L.NMAX, (cells, asp))
                self.assertGreaterEqual(rows * ch, 1920 - 1e-6)


class Motion(unittest.TestCase):
    W, H = 1080, 1920

    def test_rest_without_hit_and_after_return(self):
        P = defaults()
        g = L.grid(self.W, self.H, P['Cells'], P['Aspect'])
        n = g[0] * g[1]
        for i in range(0, n, 7):
            r = L.tile(i, P, self.W, self.H, 10.0, hit=None)
            self.assertTrue(r is None or r[0][3] == -1.0)
        end = P['Stagger'] * 1.7 + P['Hold'] + P['Return'] + 0.01
        moving = 0
        for i in range(0, n, 3):
            r = L.tile(i, P, self.W, self.H, 5.0 + end, hit=(5.0, 540.0, 960.0))
            self.assertTrue(r is None or r[0][3] == -1.0, i)
            r = L.tile(i, P, self.W, self.H, 5.4, hit=(5.0, 540.0, 960.0))
            moving += r is not None and r[0][3] >= 0
        self.assertGreater(moving, 0)

    def test_assemble_lands(self):
        P = defaults()
        P.update(Mode=2, Duration=1.5)
        g = L.grid(self.W, self.H, P['Cells'], P['Aspect'])
        for i in range(0, g[0] * g[1], 5):
            r = L.tile(i, P, self.W, self.H, 2.0 + 1.5 + P['Stagger'] * 1.7, hit=(2.0, 100.0, 100.0))
            self.assertTrue(r is None or r[0][3] == -1.0)

    def test_explode_moves_outward(self):
        P = defaults()
        P.update(Scatter=0.0, Swirl=0.0, Gravity=0.0, Stagger=0.0, Return=0.0)
        g = L.grid(self.W, self.H, P['Cells'], P['Aspect'])
        c = (540.0, 960.0)
        for i in range(0, g[0] * g[1], 11):
            r = L.tile(i, P, self.W, self.H, 1.5, hit=(1.0,) + c)
            if r is None:
                continue
            rc = L.rest_centre(i, g, self.W, 0)
            self.assertGreater(math.hypot(r[0][0] - c[0], r[0][1] - c[1]), math.hypot(rc[0] - c[0], rc[1] - c[1]))

    def test_ray_identity(self):
        b0, b1 = (300.0, 500.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)
        t, lx, ly = L.ray_local(310.5, 480.5, b0, b1, self.W, self.H, 1.2 * self.H)
        self.assertAlmostEqual(t, 1.0)
        self.assertAlmostEqual(lx, 10.5)
        self.assertAlmostEqual(ly, -19.5)

    def test_tile_at_inverts_rest_centre(self):
        for brick in (0, 1):
            g = L.grid(self.W, self.H, 24, 1.0)
            for i in range(0, g[0] * g[1], 13):
                rc = L.rest_centre(i, g, self.W, brick)
                if rc is not None:
                    self.assertEqual(L.tile_at(rc[0], rc[1], g, brick), i)


TD_STUB = """#version 460
uniform sampler2D sTD2DInputs[3];
layout(rgba32f) uniform image2DArray mTDComputeOutputs[2];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""


class HitLatch(unittest.TestCase):
    """T-155/T-160: the HIT latch (explode + disintegrate) with stamps from another clock."""
    C = (540.0, 960.0)

    def test_stale_seen_stamp_is_void(self):
        h, s = L.hit_step(None, None, 99.0, -1.0, -1.0, self.C)
        s[0] = 10554.7                                      # stored by an older shader from main's clock
        h, s = L.hit_step(h, s, 100.0, -1.0, -1.0, self.C)
        self.assertEqual((h[0], s[0]), (-1.0, -1.0))         # intact, nothing replayed
        h, s = L.hit_step(h, s, 100.5, 100.5, -1.0, self.C)
        self.assertEqual(h[0], 100.5)                       # a normal hit fires right after

    def test_normal_hit_and_reset(self):
        h, s = L.hit_step(None, None, 1.0, 0.5, -1.0, self.C)
        self.assertEqual(h[0], -1.0)                        # fresh: an old hit is not replayed
        h, s = L.hit_step(h, s, 2.0, 2.0, -1.0, self.C)
        self.assertEqual(h[0], 2.0)
        h, s = L.hit_step(h, s, 3.0, 2.0, 3.0, self.C)
        self.assertEqual(h[0], -1.0)
        h, s = L.hit_step(h, s, 3.1, 3.05, 3.0, self.C)
        self.assertEqual(h[0], 3.05)

    def test_shader_matches_mirror_rules(self):
        self.assertIn('!(s.x <= now + 0.05)', NS['HIT'])
        src = open(os.path.join(B, 'fx_destroy_explode.py')).read()
        self.assertIn("H['hit'](), H['stamp']('Resettime')", src)


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        tx = NS['shader_texts'](RACK['GLSL_LIB'])
        for k in ('hit', 'tiles', 'fx'):
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, 's.comp')
                with open(p, 'w') as fh:
                    fh.write(TD_STUB + tx[k])
                r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                    '-o', os.devnull, p], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, '%s\n%s' % (k, r.stderr[:3000]))


if __name__ == '__main__':
    unittest.main()
