"""Offline tests for FX_destroy module 'crack' (builders/fx_destroy_crack.py + fx_destroy_crack_logic.py). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_destroy_crack.py'
GLSL checks compile with glslc (OpenGL target) against stubs of the TD functions used: a syntax/type check, NOT a TD
compile (that is LIVE CHECK C1 in docs/builds/fx_destroy_crack.md)."""
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
sys.path.insert(0, BUILDERS)
import fx_destroy_crack_logic as L  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None



def rd(name):
    with open(os.path.join(BUILDERS, name)) as fh:
        return fh.read()


RACK = {}
exec(rd('fx_destroy.py'), RACK)
NS = dict(RACK)
SRC = rd('fx_destroy_crack.py')
exec(compile(SRC, 'fx_destroy_crack.py', 'exec'), NS)
P0 = L.defaults(NS['PAGES'])
DOC = os.path.join(REPO, 'docs', 'builds', 'fx_destroy_crack.md')


def par_names():
    out = set()
    for _pg, pars in NS['PAGES']:
        for name, style, _d, _o in pars:
            out |= {name + k for k in 'rgb'} if style == 'RGB' else {name}
    return out


def P(**over):
    d = dict(P0)
    d.update(over)
    return d


class Module(unittest.TestCase):
    def test_template_names(self):
        self.assertEqual(NS['MODULE'], 'crack')
        self.assertEqual(NS['PAGES'][0][1][0][0], 'Amount')
        pages = [pg for pg, _ in NS['PAGES']]
        for pg in NS['PANEL_PAGES']:
            self.assertIn(pg, pages)
        names = [n for _pg, pars in NS['PAGES'] for n, *_r in pars]
        self.assertEqual(len(names), len(set(names)), 'duplicate par names')

    def test_presets_use_real_pars_and_menu_indexes(self):
        names = par_names()
        menus = dict((n, o['names']) for _pg, pars in NS['PAGES'] for n, st, _d, o in pars if st == 'Menu')
        self.assertTrue(3 <= len(NS['PRESETS']) <= 5)
        for slot, pname, vals in NS['PRESETS']:
            for k, v in vals.items():
                self.assertIn(k, names, '%s: %s' % (pname, k))
                if k in menus:
                    self.assertTrue(isinstance(v, int) and 0 <= v < len(menus[k]), '%s: %s=%r' % (pname, k, v))

    def test_expressions_reference_real_pars(self):
        names = par_names()
        for n in set(re.findall(r"parent\(\)\.par\.(\w+)", SRC)) | set(re.findall(r"P\.format\('(\w+)'\)", SRC)):
            self.assertIn(n, names, n)

    def test_uniforms_declared_match_build(self):
        for top, shader in (('hits', NS['HITS']), ('fx', NS['FX'])):
            decl = set(re.findall(r'uniform vec4 (u\w+);', shader))
            call = SRC.split("compute(m, '%s'" % top, 1)[1].split('.comment', 1)[0]
            passed = set(re.findall(r"\('(u\w)', \[", call))
            self.assertEqual(decl, passed, top)

    def test_rules(self):
        self.assertNotIn('.destroy()', SRC)
        self.assertNotIn('numpyArray', SRC)
        self.assertNotIn('cookRate', SRC)
        SRC.encode('ascii')
        with open(os.path.join(BUILDERS, 'fx_destroy_crack_logic.py')) as fh:
            fh.read().encode('ascii')
        self.assertIn("mode = 'compute'", RACK_SRC)             # the rack helper makes compute TOPs (T-47)


RACK_SRC = rd('fx_destroy.py')


class Hits(unittest.TestCase):
    W, H = 1080, 1920

    def step(self, st, now, hit, reset=-1.0, mx=4, pt=(100.0, 200.0), sc=0.0, seed=1):
        return L.hits_step(st, now, hit, reset, mx, pt, sc, seed, self.W, self.H)

    def test_fresh_texture_inits_without_replay(self):
        st = self.step(None, 10.0, 9.0)
        self.assertEqual(st['hd'], [9.0, 0.0, 7.0, 10.0])
        st = self.step(st, 10.1, 9.0)
        self.assertTrue(all(h[2] < 0 for h in st['hits']))

    def test_hit_at_point_then_ring(self):
        st = self.step(None, 1.0, -1.0)
        t = 1.0
        for n in range(6):
            t += 0.5
            st = self.step(st, t, t)
        self.assertEqual(st['hd'][1], 6.0)
        self.assertEqual([h[3] for h in st['hits'][:4]], [5.0, 6.0, 3.0, 4.0])   # ring of Maxhits 4
        self.assertEqual(st['hits'][0][:2], [100.0, 200.0])
        self.assertEqual(st['hits'][4][2], -1.0)

    def test_scatter_moves_inside_frame(self):
        st = self.step(None, 1.0, -1.0)
        st = self.step(st, 2.0, 2.0, sc=1.0)
        x, y = st['hits'][0][:2]
        self.assertTrue(0 <= x < self.W and 0 <= y < self.H)
        self.assertNotEqual((x, y), (100.0, 200.0))

    def test_reset_and_future_hits(self):
        st = self.step(None, 1.0, -1.0)
        st = self.step(st, 2.0, 5.0)                        # a stamp in the future is not a hit yet
        self.assertEqual(st['hd'][1], 0.0)
        st = self.step(st, 5.0, 5.0)
        self.assertEqual(st['hd'][1], 1.0)
        st = self.step(st, 6.0, 5.0, reset=5.5)
        self.assertEqual(st['hd'][1], 0.0)
        self.assertTrue(all(h[2] < 0 for h in st['hits']))

    def test_stale_seen_hit_is_void(self):
        # T-155/T-160: a seen hit stored by an older shader from another clock (main's 10554.7 while now = 100)
        st = self.step(None, 99.0, -1.0)
        st['hd'][0] = 10554.7
        st = self.step(st, 100.0, -1.0)                     # voided, nothing replayed
        self.assertEqual(st['hd'][0], -1.0)
        self.assertEqual(st['hd'][1], 0.0)
        st = self.step(st, 100.5, 100.5)                    # a normal hit right after still fires
        self.assertEqual(st['hd'][1], 1.0)
        self.assertEqual(st['hits'][0][2], 100.5)

    def test_reset_equal_to_last_cook_and_hit_after(self):
        st = self.step(None, 1.0, -1.0)
        st = self.step(st, 2.0, 2.0)
        self.assertEqual(st['hd'][1], 1.0)
        st = self.step(st, 3.0, 2.0, reset=3.0)             # state cooked before the pulse: stamp == last cook
        self.assertEqual(st['hd'][1], 0.0)
        st = self.step(st, 3.02, 3.02, reset=3.0)           # second reset (>=) next frame; Trigger after the Reset
        self.assertEqual(st['hd'][1], 0.0)
        st = self.step(st, 3.04, 3.02, reset=3.0)           # ... still lands
        self.assertEqual(st['hd'][1], 1.0)
        st = self.step(st, 3.06, 3.02, reset=3.0)
        self.assertEqual(st['hd'][1], 1.0)                  # no replay

    def test_hits_shader_voids_stamps(self):
        h = NS['HITS']
        self.assertIn('if (!(hd.x <= now + 0.05)) hd.x = uA.y;', h)
        self.assertIn('uA.z >= hd.w', h)
        self.assertIn('float seen = (hd.z == 7.0 && uA.y > uA.z) ? uA.z : uA.y;', h)
        call = SRC.split("compute(m, 'hits'", 1)[1].split('.comment', 1)[0]
        self.assertIn("H['hit'](), H['stamp']('Resettime')", call)

    def test_growth_and_fade(self):
        st = {'hits': [[10.0, 20.0, 1.0, 1.0]] + [[0.0, 0.0, -1.0, 0.0]] * 7, 'hd': [1.0, 1.0, 7.0, 1.0]}
        a = L.active_hits(st, 1.125, P(Source='hits', Speed=4.0, Fade=2.0, Radius=0.5), self.H)
        self.assertAlmostEqual(a[0][2], 0.5 * self.H * (1 - 0.5 ** 3))    # ease3(0.5)
        self.assertAlmostEqual(a[0][3], 1 - 0.125 / 2.0)
        self.assertEqual(L.active_hits(st, 3.5, P(Fade=2.0), self.H), [])


@unittest.skipUnless(np is not None, 'numpy needed')
class Hash(unittest.TestCase):
    def test_scalar_equals_numpy(self):
        cx = np.array([0, 1, -1, 1079, 123456, -7], np.int64)
        cy = np.array([0, 7, 3, -2, 9, 1919], np.int64)
        v = L.hsh_np(cx, cy, 977 * 3 + 1)
        for i in range(len(cx)):
            self.assertEqual(float(v[i]), L.hsh(int(cx[i]), int(cy[i]), 977 * 3 + 1))
        self.assertTrue(((v >= 0) & (v < 1)).all())


@unittest.skipUnless(np is not None, 'numpy needed')
class Glass(unittest.TestCase):
    W, H = 270, 480

    def imp(self, R):
        return [(self.W * 0.5, self.H * 0.5, R, 1.0, 0.0, 1.0, 0.0)]

    def test_lines_inside_reach_only(self):
        R = 0.6 * self.H
        line, chip, cmap = L.crack_map(self.W, self.H, self.imp(R), P(Wobble=0.0))
        ys, xs = np.mgrid[0:self.H, 0:self.W]
        r = np.hypot(xs + 0.5 - self.W * 0.5, ys + 0.5 - self.H * 0.5)
        self.assertEqual(float(line[r > R * 1.15 + 2].max(initial=0)), 0.0)
        frac = float((line > 0.5).mean())
        self.assertTrue(0.02 < frac < 0.35, frac)
        self.assertTrue(((line >= 0) & (line <= 1)).all())
        self.assertTrue(chip.max() <= 1.0 and cmap.max() < 1.0)

    def test_no_width_no_core_no_lines(self):
        line, _c, _m = L.crack_map(self.W, self.H, self.imp(200.0), P(Crackwidth=0.0, Core=0.0, Wobble=0.0))
        self.assertEqual(float(line.max()), 0.0)

    def test_radius_zero_is_untouched(self):
        line, chip, cmap = L.crack_map(self.W, self.H, self.imp(0.0), P())
        self.assertEqual(float(line.max() + chip.max() + cmap.max()), 0.0)

    def test_angle_seam_is_continuous(self):
        # pixels just above / below the -pi / pi seam (left of the impact) fall in the same cell
        dx = np.array([-60.0, -60.0, -180.0, -180.0], np.float32)
        dy = np.array([0.01, -0.01, 0.01, -0.01], np.float32)
        _k, bid, _rc = L.glass_layer(dx, dy, 400.0, 14, 1.6, 2.5, 7, 0.8, 0.35)
        self.assertEqual(bid[0], bid[1])
        self.assertEqual(bid[2], bid[3])

    def test_line_width_in_screen_px(self):
        # Ringcracks 0: only radial edges cross a circle; the crossing runs should be ~2 * width * taper px long
        R, r0, w = 2000.0, 150.0, 3.0
        n = 20000
        th = np.linspace(-math.pi, math.pi, n, endpoint=False).astype(np.float32)
        dx, dy = (r0 * np.cos(th)).astype(np.float32), (r0 * np.sin(th)).astype(np.float32)
        k, _b, _r = L.glass_layer(dx, dy, R, 14, 1.6, w, 3, 0.8, 0.0)
        on = k > 0
        runs, cur = [], 0
        for v in np.concatenate([on, on[:1]]):
            if v:
                cur += 1
            elif cur:
                runs.append(cur)
                cur = 0
        arc = 2 * math.pi * r0 / n
        mean = float(np.mean(runs)) * arc
        taper = 1 - 0.6 * r0 / R
        self.assertTrue(2 * w * taper * 0.9 <= mean <= 2 * w * taper * 2.5, (mean, len(runs)))
        self.assertTrue(8 <= len(runs) <= 30, len(runs))      # about one crossing per radial cell

    def test_seed_changes_pattern(self):
        a = L.crack_map(self.W, self.H, self.imp(300.0), P(Seed=1, Wobble=0.0))[0]
        b = L.crack_map(self.W, self.H, self.imp(300.0), P(Seed=2, Wobble=0.0))[0]
        self.assertGreater(float(np.abs(a - b).mean()), 0.01)


@unittest.skipUnless(np is not None, 'numpy needed')
class LCD(unittest.TestCase):
    def test_stuck_lines_exact(self):
        Pd = P(Lines=8, Linedir='both', Linewidth=2, Seed=4)
        ln = L.stuck_lines(1080, 1920, Pd)
        self.assertEqual(len(ln), 8)
        self.assertEqual([a for a, *_ in ln], [0, 1] * 4)
        for ax, pos, w, kind, sp in ln:
            self.assertTrue(0 <= pos < (1080 if ax == 0 else 1920) and w == 2 and 0 <= kind <= 8 and 0 <= sp < 1)

    def test_lcd_apply_changes_only_masked(self):
        H, W = 192, 108
        img = np.zeros((H, W, 4), np.float32)
        img[..., 0] = np.linspace(0, 1, W)[None, :]
        img[..., 1] = np.linspace(0, 1, H)[:, None]
        img[..., 3] = 1
        Pd = P(Lines=5, Linedir='both', Dead=0.02, Cluster=3, Clusterfill=0.7, Deadlit=0.5, Seed=4)
        o = L.lcd_apply(img, Pd)
        dead, _c = L.dead_mask(W, H, Pd)
        ys, xs = np.mgrid[0:H, 0:W]
        lm = np.zeros((H, W), bool)
        for ax, pos, w, _k, _s in L.stuck_lines(W, H, Pd):
            lm |= ((xs if ax == 0 else ys) >= pos) & ((xs if ax == 0 else ys) < pos + w)
        changed = np.abs(o - img).max(axis=2) > 0
        self.assertFalse((changed & ~(dead | lm)).any())
        self.assertTrue(dead.sum() > 0)
        self.assertTrue((o[..., 3] == 1).all())

    def test_doc_numbers(self):
        ex = L.expected_numbers(pages=NS['PAGES'], presets=NS['PRESETS'])
        with open(DOC) as fh:
            doc = fh.read()
        for k in ('dead_px', 'line_px', 'lcd_px'):
            self.assertIn('%s %d' % (k, ex[k]), doc, k)


TD_STUB = """#version 460
uniform sampler2D sTD2DInputs[2];
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[0], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[0], c); }
"""


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.comp')
            with open(p, 'w') as fh:
                fh.write(text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def test_shaders(self):
        tx = NS['shader_texts'](RACK['GLSL_LIB'])
        self._ok(TD_STUB + tx['hits'], 'hits')
        self._ok(TD_STUB + tx['fx'], 'fx')


if __name__ == '__main__':
    unittest.main()
