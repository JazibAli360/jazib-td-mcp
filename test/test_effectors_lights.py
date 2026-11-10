"""Offline tests for effector kind `light` (lane W1-A): packing (header version 2, light region), the numpy references
(effectors_logic.ref_light_factor / ref_light / ref_lights / splat_normal) against closed forms, the shared palette on
light colours (palette_map_logic, W1-B), the Render TOP lights expression, the runtime / builder text, and glslc
compiles of the light GLSL (px_common packed section) in a consumer. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_effectors_lights.py'
glslc = a syntax / type check against TD stubs, NOT a TD compile (LIVE CHECKS L-a..L-f in docs/builds/effectors.md)."""
import ast
import math
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
import numpy as np  # noqa: E402
import effectors_logic as L  # noqa: E402
import palette_map_logic as PML  # noqa: E402
import splat_render_logic as SRL  # noqa: E402


def rd(path):
    with open(path) as fh:
        return fh.read()


def world(t=(0.0, 0.0, 0.0), rx=0.0, s=1.0):
    """Translate t, rotate rx degrees about x, uniform scale s (3x4 row-major)."""
    c, n = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    return [[s, 0.0, 0.0, t[0]], [0.0, c * s, -n * s, t[1]], [0.0, n * s, c * s, t[2]]]


def rows_of(*specs):
    rs = []
    for kind, name, kw in specs:
        rs, _ = L.add_row(rs, kind, name, **kw)
    return rs


def one_light(lv, w=None, extra=()):
    rs = rows_of(('sphere', 's', {}), ('light', 'l', {'tags': 'light key'}), *extra)
    effs = [L.effector(rs[0])] + [L.effector(rs[1], w or world((0.0, 1.0, 0.0)), light=lv)] + \
        [L.effector(r) for r in rs[2:]]
    return rs, L.pack_buffer(effs)


UP = np.array([0.0, 1.0, 0.0])


class Layout(unittest.TestCase):
    def test_kind_appended(self):
        ns = L.names(L.KINDS)
        self.assertEqual(ns[:10], ['sphere', 'box', 'plane', 'capsule', 'torus', 'null', 'pts', 'path', 'camera',
                                   'actor'])          # indices of the older kinds unchanged (packed kind index)
        self.assertEqual(ns.index('light'), 10)
        self.assertGreaterEqual(L.VERSION, 2)                            # 3: env + grid regions (lane E)
        self.assertEqual(L.sdf_of('light'), (0, (0.0, 0.0, 0.0)))

    def test_region(self):
        rs = rows_of(('sphere', 's', {}), ('light', 'a', {}), ('pts', 'p', {}), ('light', 'b', {'enabled': 0}),
                     ('light', 'c', {}))
        lv = {'type': 'spot', 'colour': (1.0, 0.5, 0.25), 'intensity': 2.0, 'cone_angle': 60.0, 'cone_delta': 10.0,
              'area_w': 2.0, 'area_h': 0.5}
        effs = [L.effector(rs[0]), L.effector(rs[1], world((1.0, 2.0, 3.0), -90.0, 2.0), light=lv),
                L.effector(rs[2], points=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]), L.effector(rs[3], light=lv),
                L.effector(rs[4], light={'type': 'directional'})]
        tex = L.pack_buffer(effs)
        n = 5
        b = 1 + n * L.W
        self.assertEqual(L.light_start(tex), b)
        self.assertEqual(tex[b], [2.0, float(L.LW), 0.0, 0.0])          # 2 enabled lights (b is off)
        self.assertEqual(L.light_count(tex), 2)
        self.assertEqual(tex[0][2], float(b + 1 + 2 * L.LW))            # points after the lights
        self.assertEqual(L.read_row(tex, 2)[8][2], float(b + 1 + 2 * L.LW))
        self.assertEqual(len(tex), b + 1 + 2 * L.LW + 4)
        k0 = L.read_light(tex, 0)
        self.assertEqual(k0[0], [1.0, 0.5, 0.25, 2.0])
        self.assertEqual(k0[1], [1.0, 2.0, 3.0, 1.0])                    # position, type spot
        for a, e in zip(k0[2], [0.0, -1.0, 0.0, 1.0]):                   # rx -90: shines down (-Z -> -Y); row 1
            self.assertAlmostEqual(a, e, places=12)
        self.assertEqual(k0[3], [0.0, 4.0, 1.0, 1.0])                    # attenuation defaults (on, 0..4, exp 1)
        self.assertAlmostEqual(k0[4][0], math.cos(math.radians(30.0)))
        self.assertAlmostEqual(k0[4][1], math.cos(math.radians(40.0)))
        for a, e in zip(k0[5], [2.0, 0.0, 0.0, 0.0]):                    # half w (1) x scale 2 along world x
            self.assertAlmostEqual(a, e, places=12)
        for a, e in zip(k0[6], [0.0, 0.0, -0.5, 0.0]):                   # half h (0.25) x 2 along local y = world -z
            self.assertAlmostEqual(a, e, places=12)
        self.assertEqual(L.read_light(tex, 1)[2][3], 4.0)                # second enabled light = row 4
        self.assertEqual(L.read_light(tex, 1)[1][3], 3.0)                # directional

    def test_light_rows_are_not_proximity(self):
        """Light rows carry enabled 0 in texel 6.w: every proximity consumer (old W = 10 shaders too) skips them;
        the other rows' texels are the same as without the light."""
        rs = rows_of(('sphere', 's', {'radius': 1.0}), ('light', 'l', {}))
        tex = L.pack_buffer([L.effector(rs[0]), L.effector(rs[1], world((0.2, 0.0, 0.0)), light={})])
        self.assertEqual(L.read_row(tex, 1)[6][3], 0.0)
        self.assertEqual(L.read_row(tex, 1)[8][1], 10.0)
        tex0 = L.pack_buffer([L.effector(rs[0])])
        self.assertEqual(L.read_row(tex, 0)[:9], L.read_row(tex0, 0)[:9])
        for p in ((0.75, 0.0, 0.0), (0.2, 0.0, 0.0), (3.0, 0.0, 0.0)):
            for sel in ('all', 'l', '#light'):
                self.assertEqual(L.ref_weight(tex, p, L.sel_vec(sel, rs)[0])[0],
                                 L.ref_weight(tex0, p, L.sel_vec(sel, rs[:1])[0])[0] if sel == 'all' else 0.0)
        self.assertEqual(L.colliders(tex, L.sel_vec('all', rs)[0]), [(0.0, 0.0, 0.0, 0.5)])

    def test_v1_reader_still_works(self):
        """A W = 10 reader (count_of / read_row / point sets by absolute texel) reads a v2 buffer correctly."""
        rs = rows_of(('light', 'l', {}), ('pts', 'p', {'radius': 1.0, 'falloff': 'linear'}))
        tex = L.pack_buffer([L.effector(rs[0], light={}), L.effector(rs[1], points=[(0.0, 0.0, 0.0)])])
        self.assertEqual(L.count_of(tex), 2)
        o, m = int(L.read_row(tex, 1)[8][2]), int(L.read_row(tex, 1)[8][3])
        self.assertEqual((tex[o], m), ([0.0, 0.0, 0.0, 1.0], 1))
        self.assertAlmostEqual(L.ref_weight(tex, (0.5, 0.0, 0.0), L.sel_vec('all', rs)[0])[0], 0.5)

    def test_v1_buffer_has_no_lights(self):
        self.assertEqual(L.light_count([[2.0, 10.0, 21.0, 1.0]] + [[0.0] * 4] * 20), 0)
        self.assertEqual(L.light_start([[0.0, 0.0, 0.0, 0.0]]), -1)      # eff_none (Constant CHOP zeros)

    def test_cache_follows_light_edits(self):
        rs = rows_of(('light', 'l', {}), ('box', 'b', {}))
        cache = {}
        for lv in ({'intensity': 1.0}, {'intensity': 3.0}, {'colour': (0.0, 1.0, 0.0)}, {'type': 'area'}):
            effs = [L.effector(rs[0], world((0.0, 2.0, 0.0)), light=lv), L.effector(rs[1])]
            self.assertEqual(L.pack_buffer(effs, cache=cache, list_key=(0, 2), as_array=True).tolist(),
                             L.pack_buffer(effs))

    def test_light_values(self):
        v = L.light_values({'type': 'cone', 'colour': (0.1, 0.2, 0.3, 1.0), 'att_on': '0', 'intensity': 'x'})
        self.assertEqual((v['type'], v['colour'], v['att_on'], v['intensity']), ('spot', (0.1, 0.2, 0.3), False, 1.0))
        self.assertEqual(L.light_values({'type': 'distant'})['type'], 'directional')
        self.assertEqual(L.TD_LIGHTTYPE['area'], 'point')                # TD 31550 has point / cone / distant only


class Reference(unittest.TestCase):
    """The numpy reference vs closed forms (the GPU check L-a / L-b compares the shader to these)."""

    def test_point_plane_la(self):
        """L-a: point light at (0, 1, 0), intensity 2, range 3 over a +y plane of points (normal +y)."""
        _, tex = one_light({'intensity': 2.0, 'att_start': 0.0, 'att_end': 3.0, 'att_exp': 1.0})
        xs = np.linspace(-4.0, 4.0, 33)
        P = np.array([(x, 0.0, z) for x in xs for z in xs])
        N = np.tile(UP, (len(P), 1))
        d = np.sqrt((P[:, 0]) ** 2 + 1.0 + P[:, 2] ** 2)
        att = np.sin(np.clip((3.0 - d) / 3.0, 0.0, 1.0) * math.pi / 2.0)
        ndl = 1.0 / d
        for model, dif in ((0, (ndl * 0.5 + 0.5) ** 2), (1, ndl), (2, (ndl + 0.5) / 1.5), (3, np.ones(len(P)))):
            got = L.ref_light(tex, 0, P, N, N, (model, 0.5, 0.0, 0.5))
            np.testing.assert_allclose(got[:, 0], 2.0 * att * dif, atol=1e-12)
            np.testing.assert_allclose(got[:, 1], got[:, 0])
        self.assertEqual(float(L.ref_light(tex, 0, [(3.5, 0.0, 0.0)], [UP], [UP])[0, 0]), 0.0)   # beyond range
        _, t2 = one_light({'att_on': False})
        self.assertAlmostEqual(float(L.ref_light_factor(t2, 0, [(50.0, 0.0, 0.0)])[0][0]), 1.0)  # no attenuation
        _, t3 = one_light({'att_start': 1.0, 'att_end': 3.0, 'att_exp': 2.0})
        a = L.ref_light_factor(t3, 0, [(0.0, 0.5, 0.0), (0.0, -1.0, 0.0)])[0]
        self.assertAlmostEqual(a[0], 1.0)                                # inside start
        self.assertAlmostEqual(a[1], math.sin(0.5 * math.pi / 2.0) ** 2)  # d 2: half way, exp 2

    def test_spot_cone_lb(self):
        """L-b: spot at (0, 1, 0) shining down, cone 60 (half 30), delta 10: full inside 30 deg, 0 beyond 40 deg,
        linear in cos between (roll 1)."""
        lv = {'type': 'spot', 'cone_angle': 60.0, 'cone_delta': 10.0, 'att_on': False}
        _, tex = one_light(lv, world((0.0, 1.0, 0.0), -90.0))

        def at(deg):
            return float(L.ref_light_factor(tex, 0, [(math.tan(math.radians(deg)), 0.0, 0.0)])[0][0])
        self.assertAlmostEqual(at(0.0), 1.0)
        self.assertAlmostEqual(at(29.9), 1.0)
        self.assertAlmostEqual(at(40.1), 0.0)
        self.assertAlmostEqual(at(35.0), 0.5, places=9)                 # smoothstep in angle: mid angle = 0.5
        self.assertAlmostEqual(at(32.0), 0.896, places=9)                # TD native measured 0.913 (b4)
        _, t2 = one_light(dict(lv, cone_roll=2.0), world((0.0, 1.0, 0.0), -90.0))
        self.assertAlmostEqual(float(L.ref_light_factor(t2, 0, [(math.tan(math.radians(35.0)), 0.0, 0.0)])[0][0]),
                               0.25, places=9)

    def test_area_nearest_point(self):
        """Area 2 x 0.5 at (0, 1, 0), pointing down (rect in the xz plane): below the rect d = 1; beyond it the
        distance to the rect's edge; two-sided."""
        lv = {'type': 'area', 'area_w': 2.0, 'area_h': 0.5, 'att_start': 0.0, 'att_end': 4.0}
        _, tex = one_light(lv, world((0.0, 1.0, 0.0), -90.0))
        P = [(0.9, 0.0, 0.2), (3.0, 0.0, 0.0), (0.0, 0.0, 2.25), (0.5, 2.0, 0.0)]
        a, Lv = L.ref_light_factor(tex, 0, P)
        exp = [1.0, math.hypot(2.0, 1.0), math.hypot(2.0, 1.0), 1.0]
        for ai, d in zip(a, exp):
            self.assertAlmostEqual(ai, math.sin((4.0 - d) / 4.0 * math.pi / 2.0), places=12)
        np.testing.assert_allclose(Lv[0], [0.0, 1.0, 0.0], atol=1e-12)   # straight up to the rect
        np.testing.assert_allclose(Lv[3], [0.0, -1.0, 0.0], atol=1e-12)  # from above: down (two-sided)

    def test_directional(self):
        _, tex = one_light({'type': 'directional', 'intensity': 0.5}, world((5.0, 5.0, 5.0), -90.0))
        a, Lv = L.ref_light_factor(tex, 0, [(0.0, 0.0, 0.0), (100.0, -3.0, 7.0)])
        np.testing.assert_allclose(a, [1.0, 1.0])
        np.testing.assert_allclose(Lv, [[0.0, 1.0, 0.0]] * 2, atol=1e-12)
        got = L.ref_light(tex, 0, [(0.0, 0.0, 0.0)], [UP], [UP], (1, 0, 0, 0))
        np.testing.assert_allclose(got, [[0.5, 0.5, 0.5]], atol=1e-12)

    def test_spec_blinn(self):
        _, tex = one_light({'att_on': False})
        P = [(0.0, 0.0, 0.0)]
        base = L.ref_light(tex, 0, P, [UP], [UP], (1, 0, 0.0, 0.5))[0, 0]
        got = L.ref_light(tex, 0, P, [UP], [UP], (1, 0, 0.7, 0.5))[0, 0]
        self.assertAlmostEqual(got - base, 0.7)                          # H = N: pow(1, sh) = 1
        v = np.array([1.0, 1.0, 0.0]) / math.sqrt(2.0)
        h = (UP + v) / np.linalg.norm(UP + v)
        sh = 2.0 / 0.5 ** 4 - 2.0
        got = L.ref_light(tex, 0, P, [UP], [v], (1, 0, 1.0, 0.5))[0, 0]
        self.assertAlmostEqual(got, 1.0 + float(h @ UP) ** sh, places=12)
        self.assertEqual(L.ref_light(tex, 0, P, [-UP], [UP], (1, 0, 1.0, 0.5))[0, 0], 0.0)  # back side: no spec

    def test_selection(self):
        rs = rows_of(('light', 'a', {'tags': 'key'}), ('light', 'b', {'tags': 'fill'}), ('light', 'c', {}),
                     ('box', 'x', {'tags': 'key'}))
        effs = [L.effector(rs[0], world((0.0, 1.0, 0.0)), light={'intensity': 1.0, 'att_on': False}),
                L.effector(rs[1], world((0.0, 1.0, 0.0)), light={'intensity': 10.0, 'att_on': False}),
                L.effector(rs[2], world((0.0, 1.0, 0.0)), light={'intensity': 100.0, 'att_on': False}),
                L.effector(rs[3])]
        tex = L.pack_buffer(effs)
        P, N = [(0.0, 0.0, 0.0)], [UP]
        val = lambda s: float(L.ref_lights(tex, P, N, N, L.sel_vec(s, rs)[0], (1, 0, 0, 0))[0, 0])
        self.assertAlmostEqual(val('all'), 111.0)
        self.assertAlmostEqual(val('#key'), 1.0)
        self.assertAlmostEqual(val('b c'), 110.0)
        self.assertAlmostEqual(val('x'), 0.0)
        rs2 = L.set_value(rs, 'b', 'enabled', '0')
        effs[1] = L.effector(rs2[1], world((0.0, 1.0, 0.0)), light={'intensity': 10.0, 'att_on': False})
        tex2 = L.pack_buffer(effs)
        self.assertAlmostEqual(float(L.ref_lights(tex2, P, N, N, L.sel_vec('all', rs2)[0], (1, 0, 0, 0))[0, 0]), 101.0)

    def test_splat_normal(self):
        rng = np.random.default_rng(3)
        for _ in range(50):
            q = rng.normal(size=4)
            s = rng.uniform(0.01, 1.0, size=3)
            R = SRL.quat_to_mat3(q)
            n = L.splat_normal(q, s)
            np.testing.assert_allclose(n, R[:, int(np.argmin(s))], atol=1e-12)
            v = rng.normal(size=3)
            self.assertGreaterEqual(float(L.splat_normal(q, s, v) @ v), 0.0)
        np.testing.assert_allclose(L.splat_normal((1, 0, 0, 0), (0.5, 0.01, 0.5)), [0.0, 1.0, 0.0])


class Palette(unittest.TestCase):
    """Light colours through the shared palette (palette_convention.md: light k = stop k in mode index)."""

    def test_index_mode(self):
        rows, ctl = L.light_palette('neon_trio', mode='steps', interp='rgb')
        cs = L.light_cs('index', 0.0, 1.0, 0.0)
        own = [(1.0, 1.0, 1.0)] * 4
        cols = L.light_colours(own, cs, (rows, ctl))
        n = int(ctl[0])
        for k, c in enumerate(cols):
            np.testing.assert_allclose(c, rows[k % n][:3], atol=1e-9)
        ctl1 = list(ctl)
        ctl1[1] = 1.0 / n                                                   # a beat step = every light one stop on
        cols1 = L.light_colours(own, cs, (rows, ctl1))
        for k in range(3):
            np.testing.assert_allclose(cols1[k], cols[k + 1], atol=1e-9)

    def test_solid_keep_and_pack(self):
        rows, ctl = L.light_palette('custom', '#ff0000 0, #0000ff 1', mode='gradient', interp='rgb')
        own = [(0.2, 0.4, 0.6)]
        self.assertEqual(L.light_colours(own, L.light_cs('solid'), (rows, ctl)), own)
        self.assertEqual(L.light_colours(own, None, None), own)
        c = L.light_colours(own, L.light_cs('palette', 1.0, 1.0, 0.5), (rows, ctl))[0]
        np.testing.assert_allclose(c, [0.1, 0.2, 0.8], atol=1e-9)             # half way back to its own colour
        rs = rows_of(('light', 'a', {}), ('light', 'b', {}))
        effs = [L.effector(r, world((0.0, 1.0, 0.0)), light={'colour': (0.2, 0.4, 0.6), 'intensity': 3.0}) for r in rs]
        tex = L.pack_buffer(effs, light_cs=L.light_cs('index'), light_pal=(rows, ctl))
        self.assertEqual(L.read_light(tex, 0)[0], [1.0, 0.0, 0.0, 3.0])        # stop 0, intensity kept
        self.assertEqual(L.read_light(tex, 1)[0], [0.0, 0.0, 1.0, 3.0])        # stop 1
        self.assertEqual(L.read_light(L.pack_buffer(effs), 0)[0], [0.2, 0.4, 0.6, 3.0])

    def test_page_pars(self):
        ps = L.light_palette_pars()
        names = [p[0] for p in ps]
        for n in ('Palsource', 'Palstops', 'Palmode', 'Palinterp', 'Palshift', 'Palreverse', 'Lightcolsrc',
                  'Lightpalpos', 'Lightpalspread', 'Lightkeep'):
            self.assertIn(n, names)
        self.assertNotIn('Lightcol', names)                                    # solid = each Light COMP's colour
        for n, style, d, o in ps:
            self.assertIn(style, ('Menu', 'Str', 'Float', 'Toggle'))
            if style == 'Menu':
                self.assertIn(d, o['names'])
        src = dict((p[0], p) for p in ps)['Palsource'][3]['names']
        self.assertNotIn('file', src)
        self.assertNotIn('image', src)
        for s in src:                                                          # every source gives a palette
            rows, ctl = L.light_palette(s, '#ffffff')
            self.assertEqual(len(rows), PML.PAL_MAX)
            self.assertGreater(ctl[0], 0)


class TDText(unittest.TestCase):
    def setUp(self):
        self.src = rd(os.path.join(BUILDERS, 'effectors.py'))
        self.rt = rd(os.path.join(BUILDERS, 'effectors_rt.py'))

    def test_runtime_api(self):
        fr = set(n.name for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef))
        for f in ('light_paths', 'light_of', 'set_light', 'giz_val', '_light_giz', '_light_pars', 'light_palette'):
            self.assertIn(f, fr)
        fb = set(n.name for n in ast.parse(self.src).body if isinstance(n, ast.FunctionDef))
        self.assertIn('light_render', fb)
        self.assertIn("_pars(c, 'Lights', Lg['light_palette_pars']())", self.src)
        for s in (self.src, self.rt):
            s.encode('ascii')
            self.assertNotIn('.destroy()', s.replace('nomcp.destroy()', ''))   # T-70 exception: no MCP here
        self.assertIn("%r.get(me.par.Ltype.eval(), 'point')", self.rt)
        self.assertEqual(eval("%r.get('area', 'point')" % (L.TD_LIGHTTYPE,)), 'point')

    def test_light_par_keys_cover_values(self):
        ns = {'boxSOP': 0, 'sphereSOP': 0, 'gridSOP': 0, 'tubeSOP': 0, 'torusSOP': 0}
        exec(compile(self.rt, 'effectors_rt.py', 'exec'), ns)
        self.assertEqual(set(ns['LIGHT_PAR_KEYS']) | {'colour'}, set(L.LIGHT_DEFAULTS))

    def test_set_light_and_light_of(self):
        """set_light writes the TD pars light_of reads back (fake Light COMP)."""
        ns = {'boxSOP': 0, 'sphereSOP': 0, 'gridSOP': 0, 'tubeSOP': 0, 'torusSOP': 0}
        exec(compile(self.rt, 'effectors_rt.py', 'exec'), ns)
        ns['L'] = lambda: L

        class P:
            def __init__(self, v):
                self.val = v

            def eval(self):
                return self.val
        pars = types.SimpleNamespace(**dict((n, P(0.0)) for n in (
            'cr', 'cg', 'cb', 'dimmer', 'attenuated', 'attenuationstart', 'attenuationend', 'attenuationexp',
            'coneangle', 'conedelta', 'coneroll', 'Lareaw', 'Lareah')))
        pars.Ltype = P('point')
        pars.lighttype = P('point')
        o = types.SimpleNamespace(par=pars, valid=True, OPType='lightCOMP')
        want = {'type': 'area', 'colour': (0.5, 0.25, 1.0), 'intensity': 3.0, 'att_on': True, 'att_start': 0.5,
                'att_end': 6.0, 'att_exp': 2.0, 'cone_angle': 30.0, 'cone_delta': 5.0, 'cone_roll': 1.5,
                'area_w': 2.0, 'area_h': 0.25}
        self.assertEqual(ns['set_light'](o, **want), [])
        self.assertEqual(ns['light_of'](o), L.light_values(want))
        self.assertEqual(ns['set_light'](o, nope=1), ['nope'])
        del pars.Ltype                                                        # a foreign Light COMP (ref)
        pars.lighttype = P('distant')
        self.assertEqual(ns['light_of'](o)['type'], 'directional')
        self.assertEqual(ns['light_of'](o)['area_w'], 2.0)

    def test_lights_expr(self):
        e = L.lights_expr('#key', 'light1 env1')
        rt = types.SimpleNamespace(module=types.SimpleNamespace(
            light_paths=lambda s: ['/project1/effectors/l1'] if s == '#key' else []))
        self.assertEqual(eval(e, {'op': lambda p: rt}), 'light1 env1 /project1/effectors/l1')
        self.assertEqual(eval(e, {'op': lambda p: None}), 'light1 env1')
        self.assertEqual(eval(L.lights_expr(), {'op': lambda p: None}), '')
        self.assertIn("op('/project1/effectors/eff_rt')", e)

    def test_refresh_render_lights(self):
        mode = types.SimpleNamespace(EXPRESSION='e', CONSTANT='c')

        class Par:
            def __init__(self, expr, m='e'):
                self.mode, self._e, self.sets = m, expr, []

            @property
            def expr(self):
                return self._e

            @expr.setter
            def expr(self, v):
                self.sets.append(v)
                self._e = v
        lit = Par(L.lights_expr('all', 'light1'))
        other = Par("'light1'")
        rtop = type('renderTOP', (), {})
        rends = [types.SimpleNamespace(par=types.SimpleNamespace(lights=lit)),
                 types.SimpleNamespace(par=types.SimpleNamespace(lights=other))]
        root = types.SimpleNamespace(findChildren=lambda **kw: rends if kw.get('type') is rtop else [])
        ns = {'ParMode': mode, 'selectCHOP': type('selectCHOP', (), {}), 'renderTOP': rtop, 'op': lambda p: root}
        exec(compile(self.src, 'effectors.py', 'exec'), ns)
        self.assertEqual(ns['refresh_consumers'](), 1)
        self.assertEqual(lit.sets, ["''", L.lights_expr('all', 'light1')])
        self.assertEqual(other.sets, [])


STUB_COMPUTE = """#version 460
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
"""


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, ext, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.' + ext)
            with open(p, 'w') as fh:
                fh.write(text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:3000]))

    def pre(self, *defines):
        return L.consumer_prefix(rd(os.path.join(GLSL, 'px_common.glsl')), rd(os.path.join(GLSL, 'eff_consumer.glsl')),
                                 defines)

    def test_light_api_compute(self):
        body = """
layout(local_size_x = 8, local_size_y = 8) in;
void main()
{
	vec3 p = vec3(gl_GlobalInvocationID.xy, 0.0) * 0.01;
	vec3 n = vec3(0.0, 1.0, 0.0), v = vec3(0.0, 0.0, 1.0);
	vec3 c = pxeLights(p, n, v, uEffSel, uEffIds, vec4(0.0, 0.5, 0.3, 0.4));
	int K = pxeLightCount();
	if (K > 0) {
		vec3 L;
		float a = pxeLightFactor(0, p, L);
		c += pxeLight(0, p, pxeSplatNormal(vec4(1.0, 0.0, 0.0, 0.0), vec3(0.5, 0.01, 0.5), v), v, vec4(3.0))
		     * a + pxeLightCol(0) + pxeLightPos(0) + pxeLightDir(0) * float(pxeLightType(0) + pxeLightRow(0));
	}
	imageStore(mTDComputeOutputs[0], ivec3(gl_GlobalInvocationID.xy, 0), vec4(c, 1.0));
}
"""
        self._ok(STUB_COMPUTE + self.pre() + body, 'comp', 'light API in a consumer compute')

    def test_constants_match(self):
        g = rd(os.path.join(GLSL, 'px_common.glsl'))
        self.assertIn('const int PXE_LIGHT_MAX = %d;' % L.LIGHT_MAX, g)
        self.assertIn('max(pxI(lh.y), %d)' % L.LW, g)
        self.assertIn('max(pxI(texelFetch(PXE_ROWS, b).y), %d)' % L.LW, g)
        self.assertIn('const int PXE_W = %d;' % L.W, g)
        g.encode('ascii')


if __name__ == '__main__':
    unittest.main()
