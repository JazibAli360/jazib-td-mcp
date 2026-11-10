"""Offline tests of FX_track (lane F; docs/builds/fx_track.md): module contracts, full-state presets, uniforms vs
shaders, glslc of every pass sized to its wired inputs (a syntax / type check, not a TD compile), font + text mirror,
tracker mirrors (det / cells / pts), candidate culling is conservative, label culling reach.
Run: python3 -I -m unittest discover -s test -p 'test_fx_track.py'"""
import math
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fx_time_testkit as K  # noqa: E402
import fx_stylise_testkit as S  # noqa: E402

B = K.BUILDERS
STUB = """#version 460
%s
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""


def glslc_n(text, n):
    decl = 'uniform sampler2D sTD2DInputs[%d];' % n if n > 0 else ''
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, 's.comp')
        with open(p, 'w') as fh:
            fh.write(STUB % decl + text)
        r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                            '-o', os.devnull, p], capture_output=True, text=True)
        return r.returncode == 0, r.stderr[:3000]


def lib():
    ns = {'HERE': B}
    with open(os.path.join(B, 'fx_track_lib.py')) as fh:
        exec(compile(fh.read(), 'fx_track_lib.py', 'exec'), ns)
    return ns


def rack():
    """fx_track.py without TD: the fx_glitch rack exec is replaced by stand-ins."""
    src = open(os.path.join(B, 'fx_track.py')).read()
    src = src.replace("with open(os.path.join(HERE, 'fx_glitch.py')) as _fh:\n    exec(_fh.read(), globals())",
                      "COLS = []\nH = {}\nbuild = add = _layout = None")
    ns = {}
    exec(compile(src, 'fx_track.py', 'exec'), ns)
    return ns


L = lib()


class Contract(unittest.TestCase):
    def test_modules(self):
        for mod in ('plexus', 'hud', 'analytics'):
            ns = S.load(mod, rack='fx_track')
            S.check_module(self, ns, mod, rack='fx_track')
            if K.HAVE_GLSLC:
                for name, text in ns['SHADERS'].items():
                    ok, err = glslc_n(text, ns['NIN'][name])
                    self.assertTrue(ok, '%s %s: %s' % (mod, name, err))
                    self.assertNotIn('sTD2DInputs[%d]' % ns['NIN'][name], text)

    @unittest.skipUnless(K.HAVE_GLSLC, 'glslc')
    def test_tracker_glslc(self):
        R = rack()
        for name, text in R['TRACK_SHADERS'].items():
            ok, err = glslc_n(text, R['TRACK_NIN'][name])
            self.assertTrue(ok, name + ': ' + err)
        U = R['track_uniforms']()
        for name, text in R['TRACK_SHADERS'].items():
            self.assertEqual([u for u, _ in U[name]], K.declared_uniforms(text), name)

    def test_td_rules(self):
        for f in ('fx_track.py', 'fx_track_lib.py', 'fx_track_plexus.py', 'fx_track_hud.py', 'fx_track_analytics.py',
                  'fx_track_logic.py', 'fx_track_checks.py'):
            src = K.source(f)
            src.encode('ascii')
            self.assertNotIn('.destroy()', src)
            self.assertNotIn('cookRate', src)
            if f == 'fx_track.py':                               # the one CHOP read (out_pts), never a TOP readback
                src = src.replace('src.numpyArray()', '')
            if f != 'fx_track_checks.py':
                self.assertNotIn('numpyArray', src)

    def test_plexus_bindings(self):
        ns = S.load('plexus', rack='fx_track')
        sys.path.insert(0, B)
        import px_lines_logic as PL
        names = set()
        for _pg, pl in PL.PAGES:
            for n, s, _d, _o in pl:
                names |= ({n + c for c in 'rgb'} if s == 'RGB' else {n + c for c in 'xyz'} if s == 'XYZ' else {n})
        b, const = ns['line_bindings']()
        for k in list(b) + list(const):
            self.assertIn(k, names, k)
        mod_pars = set(n for _pg, pl in ns['PAGES'] for n, _s, _d, _o in pl)
        import re
        for e in b.values():
            for ref in re.findall(r'parent\(\)\.par\.(\w+)', e):
                self.assertIn(ref, mod_pars, ref)
        for k, _l in ns['LINEATTR']:
            self.assertIn(k, [a for a, _b in PL.ATTR])
        self.assertEqual([k for k, _l in ns['LINECOLSRC']], [a for a, _b in PL.COLSRC])


class Font(unittest.TestCase):
    def test_glyph_A(self):
        # 'A' = 0C1E33333F333300: row 0 bits 2,3 set (bit 0 = leftmost)
        self.assertEqual([L['glyph'](65, x, 0) for x in range(8)], [0, 0, 1, 1, 0, 0, 0, 0])
        self.assertEqual(L['glyph'](32, 3, 3), 0.0)

    def test_strings(self):
        t = L['text_string']
        self.assertEqual(t(1, (17, 0, 0, 0)), 'ID 017')
        self.assertEqual(t(2, (0, 512.7, 960.2, 0)), 'X0512 Y0960')
        self.assertEqual(t(3, (0, 0, 0, 123.9)), 'V 0123')
        self.assertEqual(t(4, (0, 0, 0, 12.34)), 'T 012.3')
        self.assertEqual(t(5, (7, 0, 0, 0)), '#007')
        self.assertEqual(t(6, (12, 0, 0, 0)), 'COUNT 012')
        self.assertEqual(t(7, (4, 0, 0, 0)), 'MOVING 004')
        self.assertEqual(t(8, (3723.5, 0, 0, 0)), 'REC 01:02:03')
        self.assertEqual(t(9, (1, 0, 0, 0)), 'CAM 01')
        self.assertEqual(t(10, (3, 45, 0, 0)), 'Z03 045%')
        for k, n in L['LINE_LEN'].items():
            self.assertEqual(len(t(k, (1, 2, 3, 4))), n)

    def test_text_at(self):
        # 'I' of "ID 017" at scale 1: glyph 1E0C0C0C0C0C1E00 row 0 = 0x1E -> bits 1..4
        org = (10.0, 20.0)
        top = 20.0 + 7.5                    # glyph row 0 (top) is the pixel row 7 above the origin
        got = [L['text_at']((10.5 + x, top), org, 1.0, 1, (17, 0, 0, 0)) for x in range(8)]
        self.assertEqual(got, [0, 1, 1, 1, 1, 0, 0, 0])


class Tracker(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.src = np.zeros((96, 54, 4))
        self.src[..., 3] = 1
        self.src[60:70, 10:18, :3] = 0.9                 # a bright block
        self.src[20:24, 40:44, :3] = 0.7
        self.src[..., :3] += rng.random((96, 54, 3)) * 0.05

    def test_det_and_cells(self):
        det = L['det_ref'](self.src, None, 27, 48, 0, 1.0, 4.0)
        self.assertEqual(det.shape, (48, 27, 4))
        self.assertTrue(np.allclose(det[..., 0], det[..., 1]))
        cells = L['cells_ref'](det, 3, 4, 0.5, 1)
        self.assertEqual(cells.shape, (4, 6, 4))
        valid = cells[..., 0::2, 2] > 0
        self.assertEqual(int(valid.sum()), 2)
        # the big block (rows 60-70, cols 10-18 -> det rows 30-35, cols 5-9) sits in cell (0, 2)
        c0, c1 = cells[2, 0], cells[2, 1]
        self.assertGreater(c0[2], 0)
        self.assertTrue(c1[0] <= c0[0] <= c1[2] and c1[1] <= c0[1] <= c1[3])
        self.assertAlmostEqual(c0[0], 7.0 / 27, delta=0.02)

    def test_pts(self):
        det = L['det_ref'](self.src, None, 27, 48, 0, 1.0, 4.0)
        cells = L['cells_ref'](det, 3, 4, 0.5)
        pts = L['pts_ref'](0, cells, None, None, 12, 3, L['WX'], L['WX'] * 1920 / 1080, 10.0, 0.5, 0.01)
        self.assertEqual(pts.shape, (2, 256, 4))
        fb = pts[-1].reshape(-1)
        self.assertEqual(fb[(65 - 32) * 8], 0x0C)          # 'A' row 0 in the font row
        v = [i for i in range(12) if L['pt'](pts, i, 0)[3] > 0.5]
        self.assertEqual(v, [2, 6])
        T0, T1 = L['pt'](pts, 6, 0), L['pt'](pts, 6, 1)
        self.assertAlmostEqual(T0[0], (T1[0] - 0.5) * 2 * L['WX'])
        self.assertEqual(L['pt'](pts, 20, 0)[0], 1e4 + 200)
        # smoothing / velocity against the previous frame with the same id
        prev = pts.copy()
        prev[0, 6 * 4 + 1, 0] -= 0.01
        nxt = L['pts_ref'](0, cells, None, prev, 12, 3, L['WX'], L['WX'] * 1920 / 1080, 10.2, 0.5, 0.01)
        self.assertAlmostEqual(L['pt'](nxt, 6, 1)[0], T1[0] - 0.005)
        self.assertAlmostEqual(L['pt'](nxt, 6, 3)[2], 0.005 / 0.2)
        stale = L['pts_ref'](0, cells, None, prev, 12, 3, L['WX'], L['WX'] * 1920 / 1080, 11.0, 0.5, 0.01)
        self.assertEqual(L['pt'](stale, 6, 3)[2], 0.0)                # > 0.25 s gap: no velocity, no smoothing
        self.assertAlmostEqual(L['pt'](nxt, 6, 3)[1], 0.2)

    def test_blob_rows(self):
        a = L['blob_rows']([{'id': 4, 'u': 0.5, 'v': 0.25, 'width': 0.1, 'height': 0.05, 'age': 2.0}], 3)
        pts = L['pts_ref'](1, None, a, None, 3, 1, 1.0, 2.0, 1 / 60., 0.0, 0.0)
        self.assertEqual(list(L['pt'](pts, 0, 0)), [0.0, -1.0, 0.0, 1.0])
        np.testing.assert_allclose(L['pt'](pts, 0, 2), [0.45, 0.225, 0.55, 0.275], atol=1e-6)
        self.assertEqual(L['pt'](pts, 1, 0)[3], 0.0)

    def test_candidates_conservative(self):
        """A point drawn with reach r (px) around its centroid: every pixel it can touch looks at its cell."""
        rng = np.random.default_rng(3)
        W, Hh, cx, cy = 1080, 1920, 18, 32
        for _ in range(3000):
            i = int(rng.integers(cx * cy))
            x, y = i % cx, i // cx
            u = (x + rng.random()) / cx
            v = (y + rng.random()) / cy
            r = rng.random() * 3 * W / cx
            ang = rng.random() * 2 * math.pi
            pu = min(max(u + r * math.cos(ang) / W, 0), 0.9999)
            pv = min(max(v + r * math.sin(ang) / Hh, 0), 0.9999)
            cand = L['candidates']((pu, pv), ((r + 1) / W, (r + 1) / Hh), 0, cx, cy, cx * cy)
            self.assertIn(i, cand)


class Outputs(unittest.TestCase):
    """out_pts (OUT_PTS_CB): TOP to CHOP channels -> points texture -> valid points as samples; link_fx present."""
    @classmethod
    def setUpClass(cls):
        cls.R = rack()
        cls.CB = {}
        exec(compile(cls.R['OUT_PTS_CB'], 'out_pts_cb', 'exec'), cls.CB)

    def tex(self, n=130):
        rng = np.random.RandomState(4)
        rows, w = L['pts_shape'](n)
        t = np.zeros((rows, w, 4))
        for i in range(n):
            y, x = i // 64, (i % 64) * 4
            ok = float(i % 3 == 0)
            t[y, x] = [rng.uniform(-2, 2), rng.uniform(-3, 3), 0, ok] if ok else [1e4 + 10 * i, 1e4, 0, 0]
            t[y, x + 1] = [rng.uniform(), rng.uniform(), rng.uniform(), 0.5]
            t[y, x + 3] = [i, 1.0, 0.0, 0]
        t[rows - 1] = 7.0                                         # font row: never read as points
        return t

    def chop(self, t):
        """As a TOP to CHOP with crop full gives it: channel <c><row>, samples = columns."""
        names, vals = [], []
        for y in range(t.shape[0]):
            for k, c in enumerate('rgba'):
                names.append('%s%d' % (c, y))
                vals.append(list(t[y, :, k]))
        return names, vals

    def test_unpack_roundtrip(self):
        t = self.tex()
        np.testing.assert_array_equal(self.CB['unpack'](*self.chop(t)), t)
        one = self.CB['unpack'](['r', 'g', 'b', 'a'], [[1.0, 2.0]] * 4)
        self.assertEqual(one.shape, (1, 2, 4))

    def test_points_valid_cap_order(self):
        t = self.tex()
        P = self.CB['points'](t, 130, 0)
        want = [i for i in range(130) if i % 3 == 0]
        self.assertEqual([int(v) for v in P['id']], want)
        self.assertEqual(sorted(P), sorted(self.CB['CHANS']))
        i = want[5]
        self.assertEqual(P['tx'][5], t[i // 64, (i % 64) * 4, 0])
        self.assertEqual(P['u'][5], t[i // 64, (i % 64) * 4 + 1, 0])
        self.assertEqual(P['strength'][5], t[i // 64, (i % 64) * 4 + 1, 2])
        C = self.CB['points'](t, 130, 10)                          # strongest 10, still in index order
        self.assertEqual(len(C['id']), 10)
        self.assertEqual(list(C['id']), sorted(C['id']))
        self.assertTrue(min(C['strength']) >= sorted(P['strength'])[-10])
        self.assertEqual(len(self.CB['points'](t, 40, 0)['id']), 14)   # n from the rack pars bounds the read
        self.assertEqual(len(self.CB['points'](np.zeros((1, 256, 4)), 130, 0)['id']), 0)

    def test_points_from_pts_ref(self):
        T = Tracker('test_pts')
        T.setUp()
        det = L['det_ref'](T.src, None, 27, 48, 0, 1.0, 4.0)
        cells = L['cells_ref'](det, 3, 4, 0.5)
        pts = L['pts_ref'](0, cells, None, None, 12, 3, L['WX'], L['WX'] * 1920 / 1080, 10.0, 0.5, 0.01)
        P = self.CB['points'](pts, 12, 64)
        v = [i for i in range(12) if L['pt'](pts, i, 0)[3] > 0.5]
        self.assertEqual([int(x) for x in P['id']], [int(L['pt'](pts, i, 3)[0]) for i in v])

    def test_builder_bits(self):
        compile(self.R['OUT_PTS_CB'], 'cb', 'exec')
        self.R['OUT_PTS_CB'].encode('ascii')
        self.assertIn('def link_fx(', K.source('fx_track.py'))
        self.assertIn(('Outpts', 'Int', 64), [p[:3] for p in self.R['TRACK_PAGES'][0][1]])
        self.assertEqual(self.R['ARCS_PRESET'], 'tracked arcs')
        M = K.load_module('misc')
        d = dict(M['_D'], **self.R['ARCS_LOOK'])
        self.assertEqual(set(d), set(M['_D']))                      # full state, only misc's own pars
        self.assertEqual((d['Type'], d['Pointspace'], d['Arcmode']), (M['TYPES'].index('arcs'), 0, 1))



class Mirrors(unittest.TestCase):
    """The per-pixel references run and draw what they should on a synthetic points texture."""

    def setUp(self):
        sys.path.insert(0, B)
        import fx_track_logic as FG
        self.FG = FG
        self.rk = {'Detector': 1, 'Cellsx': 1, 'Cellsy': 1, 'N': 2, 'Threshold': 0.5, 'Resw': 200.0, 'Resh': 100.0}
        a = L['blob_rows']([{'id': 7, 'u': 0.5, 'v': 0.5, 'width': 0.2, 'height': 0.2, 'age': 1.0}], 2)
        self.pts = L['pts_ref'](1, None, a, None, 2, 1, L['WX'], L['WX'] / 2, 1 / 60., 0.0, 0.0)
        self.pal = lambda t: (t, 1 - t, 0.5)

    def defaults(self, mod):
        ns = S.load(mod, rack='fx_track')
        return S.pars_of(ns)

    def test_hud_box_and_label(self):
        P = self.defaults('hud')
        P.update(Boxstyle=1, Boxpad=0.0, Boxmin=0.0, Cross=0.0, Labelbg=0.0, Share=1.0)
        src = np.array([0.0, 0.0, 0.0, 1.0])
        # box of the blob: x 80..120, y 40..60 (200 x 100); left edge pixel x = 80 -> pc 80.5 on the line (w 1.5)
        on = self.FG.hud_pixel((79, 50), src, self.pts, P, self.rk, (200.0, 100.0), self.pal, 0.0)
        off = self.FG.hud_pixel((100, 50), src, self.pts, P, self.rk, (200.0, 100.0), self.pal, 0.0)
        self.assertGreater(on[1], 0.5)
        self.assertEqual(off[1], 0.0)
        # label line 0 "ID 007" sits above the box: some pixel of it is lit
        lit = max(self.FG.hud_pixel((x, y), src, self.pts, P, self.rk, (200.0, 100.0), self.pal, 0.0)[1]
                  for x in range(80, 100) for y in range(80, 100))
        self.assertGreater(lit, 0.5)

    def test_plexus_dot(self):
        P = self.defaults('plexus')
        P.update(Dotstyle=1, Dotradius=5.0)
        base = np.array([0.1, 0.1, 0.1, 1.0])
        c = self.FG.plexus_pixel((99, 49), base, base, self.pts, P, self.rk, (200.0, 100.0), self.pal)
        self.assertAlmostEqual(c[0], 1.0)

    def test_analytics(self):
        P = self.defaults('analytics')
        det = np.zeros((10, 20, 4))
        det[..., 0] = 0.9
        hs = self.FG.hs_step(det, self.pts, None, P, self.rk, 5.0)
        self.assertEqual(hs.shape, (11, 20, 4))
        self.assertEqual(hs[10, 0, 0], 1.0)
        hs2 = self.FG.hs_step(det, self.pts, hs, P, self.rk, 5.05)
        self.assertAlmostEqual(hs2[0, 0, 0], 0.4 * P['Heatgain'] * 0.05, places=9)
        img = np.zeros((100, 200, 4))
        img[..., 3] = 1
        P.update(Redact=1, Redacton=0)
        o = self.FG.analytics_pixel((100, 50), img, self.pts, hs2, P, self.rk, (200.0, 100.0), self.pal, 0.2)
        self.assertEqual(o.shape, (4,))


if __name__ == '__main__':
    unittest.main()
