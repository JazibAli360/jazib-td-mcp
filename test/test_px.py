"""Offline tests for PX_pointfx (builders/px_logic.py, px_rt.py, px.py, glsl/px_*.glsl). No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_px.py'
GLSL checks compile with glslc (OpenGL target) against stubs of the TD functions used: a syntax/type check, NOT a TD
compile (that is a LIVE CHECK in docs/builds/px.md)."""
import ast
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
import px_logic as L  # noqa: E402

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None


def _read(path, **kw):
    with open(path, **kw) as fh:
        return fh.read()


def rd(name):
    return _read(os.path.join(GLSL, name))


LIB, TU, TC, TS, MODS = (rd('px_common.glsl'), rd('px_update.glsl'), rd('px_colour.glsl'), rd('px_source.glsl'),
                         rd('px_modules.glsl'))
PAL = rd('px_palette.glsl')
SNIPS = L.parse_snippets(MODS)


def full_stack():
    st = []
    for t in L.module_types():
        st, _ = L.add_module(st, t)
    return st


class Schema(unittest.TestCase):
    def test_snippets_match_schema(self):
        self.assertEqual(L.check_snippets(SNIPS), [])

    def test_every_module_has_its_stages(self):
        for t, m in L.MODULES.items():
            self.assertTrue(set(m['stages']) <= set(L.STAGES), t)
            for st in m['stages']:
                self.assertIn((t, st), SNIPS)

    def test_at_least_the_required_modules(self):
        need = ['prox_push', 'prox_scale', 'prox_colour', 'prox_dissolve', 'curl', 'wind', 'attractor', 'orbit',
                'twist', 'explode', 'wave', 'mask_region', 'dissolve_noise', 'dissolve_gradient', 'dissolve_time',
                'lifetime', 'velocity_streak', 'audio_displace', 'shockwave']
        for n in need:
            self.assertIn(n, L.MODULES)
        self.assertGreaterEqual(len(L.MODULES), 25)

    def test_param_defaults_and_menus(self):
        for t, m in L.MODULES.items():
            names = [p['name'] for p in m['params']]
            self.assertEqual(len(names), len(set(names)), t)
            for p in m['params']:
                self.assertRegex(p['name'], r'^[a-z][a-z0-9]*$')
                if p['kind'] == 'menu':
                    self.assertIn(p['default'], L.names(p['menu']), (t, p['name']))
                elif p['kind'] in ('float', 'int'):
                    self.assertLessEqual(p['lo'], p['default'], (t, p['name']))
                    self.assertGreaterEqual(p['hi'], p['default'], (t, p['name']))
                elif p['kind'] in ('xyz', 'rgb'):
                    self.assertEqual(len(p['default']), 3)
                self.assertNotIn(p['name'], ('amount', 'maskin', 'invert', 'effectors', 'drive'), t)

    def test_td_par_names(self):
        rx = re.compile(r'^[A-Z][a-z0-9]*$')
        core = []
        for _pg, pars in L.CORE_PAGES:
            for name, style, _d, o in pars:
                self.assertRegex(name, rx)
                core.append(name)
                if style == 'Menu':
                    self.assertIn(_d, o['names'], name)
        self.assertEqual(len(core), len(set(core)))
        self.assertFalse([n for n in core if re.match(r'^M\d', n)])            # never collides with module pars
        for inst in full_stack():
            for name, _s, _d, _o in L.instance_par_specs(inst):
                self.assertRegex(name, rx)
            self.assertNotIn(' ', L.page_name(inst))                            # zkit joins page names with spaces

    def test_addtype_menu_lists_every_module(self):
        page = dict(L.CORE_PAGES)['Stack']
        add = next(p for p in page if p[0] == 'Addtype')
        self.assertTrue(add[3].get('menu'))                                 # phase B: a live browser dropdown
        self.assertEqual(sorted(L.module_browser()[0]), sorted(L.MODULES))

    def test_logic_imports(self):
        tree = ast.parse(_read(os.path.join(BUILDERS, 'px_logic.py')))
        top = set()
        for n in tree.body:
            if isinstance(n, ast.Import):
                top |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                top.add(n.module)
        self.assertEqual(top, {'hashlib', 'json', 'math', 're'})               # numpy only inside functions


class Stack(unittest.TestCase):
    def test_add_remove_move_duplicate(self):
        st, a = L.add_module([], 'curl')
        st, b = L.add_module(st, 'prox_push')
        st, c = L.add_module(st, 'wave', at=0)
        self.assertEqual([i['type'] for i in st], ['wave', 'curl', 'prox_push'])
        st = L.move_module(st, b, -5)
        self.assertEqual(st[0]['uid'], b)
        st, d = L.duplicate_module(st, b)
        self.assertEqual([i['uid'] for i in st][:2], [b, d])
        self.assertEqual(st[1]['type'], 'prox_push')
        self.assertEqual(len({i['uid'] for i in st}), 4)
        st = L.remove_module(st, a)
        self.assertEqual(L.find(st, a), -1)
        st = L.set_enabled(st, d, False)
        self.assertFalse(st[L.find(st, d)]['enabled'])
        _, e = L.add_module(st, 'curl')
        self.assertEqual(e, max(i['uid'] for i in st) + 1)

    def test_rows_roundtrip_and_junk(self):
        st = full_stack()
        st = L.set_enabled(st, 3, False)
        self.assertEqual(L.stack_from_rows(L.stack_rows(st)), st)
        rows = L.stack_rows(st) + [['x', 'curl', '1', ''], ['99', 'nope', '1', ''], ['1', 'curl', '1', 'dup uid']]
        self.assertEqual(L.stack_from_rows(rows), st)

    def test_copy_values(self):
        flat = {'M3strength': 2.0, 'M3gravityx': 1.0, 'M31strength': 9.0, 'Size': 1}
        self.assertEqual(L.copy_values(flat, 3, 7), {'M7strength': 2.0, 'M7gravityx': 1.0})


class Codegen(unittest.TestCase):
    def test_layout_slots(self):
        st, u = L.add_module([], 'wind')
        lay, n = L.layout(st)
        s = lay[0]['slots']
        self.assertEqual(lay[0]['base'], 0)
        self.assertEqual(L.HEADER_ROWS, 3)                    # (amount..), (chunk, shared sel), (shared ids)
        self.assertEqual(s['gravity'], (3, 'xyz'))
        self.assertEqual(s['wind'], (4, 'xyz'))
        self.assertEqual(s['gust'], (5, 0))
        self.assertEqual(s['bounce'], (6, 1))
        self.assertEqual(n, 7)
        st, _ = L.add_module([], 'curl')
        lay, n = L.layout(st)
        self.assertEqual(lay[0]['slots']['speed'], (3, 2))
        self.assertEqual(lay[0]['slots']['speedph'], (3, 3))

    def test_order_disable_duplicate(self):
        st = []
        for t in ('curl', 'prox_push', 'wave', 'prox_push'):
            st, _ = L.add_module(st, t)
        st = L.set_enabled(st, 3, False)
        cg = L.codegen(st, LIB, TU, TC, MODS, PAL)
        marks = re.findall(r'// \[(\d+)\] (\w+)', cg['update'])
        self.assertEqual(marks, [('1', 'curl'), ('2', 'prox_push'), ('4', 'prox_push')])
        b2 = next(il['base'] for il in cg['layout'] if il['uid'] == 2)
        b4 = next(il['base'] for il in cg['layout'] if il['uid'] == 4)
        self.assertNotEqual(b2, b4)
        self.assertIn('uM[%d].y' % b2, cg['update'])
        self.assertIn('uM[%d].y' % b4, cg['update'])
        self.assertIn('uniform vec4 uM[%d];' % cg['rows'], cg['update'])
        self.assertNotIn('$', cg['update'] + cg['colour'])
        self.assertIn('// (no modules in this stage)', cg['colour'])
        self.assertTrue(cg['update_inplace'].startswith('#define PX_INPLACE 1\n'))
        self.assertEqual(cg['update'].count('void main()'), 1)

    def test_hash_only_on_structure(self):
        st = full_stack()
        h = L.structure_hash(st, LIB, [TU, TC], MODS)
        st2 = [dict(i, label='renamed') for i in st]
        self.assertEqual(L.structure_hash(st2, LIB, [TU, TC], MODS), h)       # labels only change a comment line
        self.assertNotEqual(L.structure_hash(L.move_module(st, 2, 1), LIB, [TU, TC], MODS), h)
        self.assertNotEqual(L.structure_hash(L.set_enabled(st, 2, False), LIB, [TU, TC], MODS), h)
        self.assertNotEqual(L.structure_hash(st, LIB + ' ', [TU, TC], MODS), h)
        self.assertEqual(L.codegen(st, LIB, TU, TC, MODS)['hash'], h)
        self.assertNotEqual(L.codegen(st, LIB, TU, TC, MODS, PAL)['hash'], h)        # the palette text is part of it

    def test_unknown_token(self):
        with self.assertRaises(ValueError):
            L.substitute('x = $nope;', {'a': (0, 0)})

    def test_template_markers_exact(self):
        with self.assertRaises(ValueError):
            L._marker('//@DECL\n//@DECL\n', 'DECL', 'x')
        out = L._marker('// mentions //@DECL in a comment\n//@DECL\nend\n', 'DECL', 'X')
        self.assertEqual(out, '// mentions //@DECL in a comment\nX\nend\n')


class Packing(unittest.TestCase):
    def test_pack_module_rows(self):
        st, u = L.add_module([], 'prox_colour')
        st, w = L.add_module(st, 'wind')
        lay, n = L.layout(st)
        vals = {u: dict(L.instance_defaults(st[0]), amount=0.5, effectors='E2 E9 E1', maskin='m1', invert=1,
                        mode='ramp', colour=(0.1, 0.2, 0.3), flip=True),
                w: dict(L.instance_defaults(st[1]), gravity=(0, -9.8, 0), floor=0)}
        rows = L.pack_module_rows(lay, n, vals, ['E1', 'E2', 'E3'])
        self.assertEqual(len(rows), n)
        self.assertEqual(rows[0], [0.5, 3.0, 2.0, 1.0])                         # E1 | E2 bits, E9 unknown
        s = lay[0]['slots']
        self.assertEqual(rows[s['mode'][0]][s['mode'][1]], 2.0)
        self.assertEqual(rows[s['colour'][0]][:3], [0.1, 0.2, 0.3])
        self.assertEqual(rows[s['flip'][0]][s['flip'][1]], 1.0)
        g = lay[1]['slots']['gravity']
        self.assertEqual(rows[g[0]][:3], [0.0, -9.8, 0.0])

    def test_phases_integrate(self):
        st, u = L.add_module([], 'orbit')
        lay, n = L.layout(st)
        ph = {}
        for _ in range(60):
            ph = L.integrate_phases(ph, lay, {u: {'speed': 0.5}}, 1.0 / 60)
        self.assertAlmostEqual(ph[u]['speed'], 0.5, 9)
        rows = L.pack_module_rows(lay, n, {u: {'speed': 0.5}}, [], ph)
        r, c = lay[0]['slots']['speedph']
        self.assertAlmostEqual(rows[r][c], 0.5, 9)

    def test_drives(self):
        d, bad = L.parse_drives('strength:low*2 radius:beat*-0.5+0.1 gravity.y:trig1*-3 junk amount:lfo1')
        self.assertEqual(bad, ['junk'])
        self.assertEqual(d[0], ('strength', None, 'low', 2.0, 0.0))
        self.assertEqual(d[1], ('radius', None, 'beat', -0.5, 0.1))
        v = L.apply_drives({'strength': 1.0, 'radius': 1.0, 'amount': 1.0}, 'prox_push', d[:2] + d[3:],
                           {'low': 0.5, 'beat': 1.0, 'lfo1': 0.25})
        self.assertAlmostEqual(v['strength'], 2.0)
        self.assertAlmostEqual(v['radius'], 0.6)
        self.assertAlmostEqual(v['amount'], 1.25)
        w = L.apply_drives({'gravity': (0.0, 0.0, 0.0)}, 'wind', [d[2]], {'trig1': 1.0})
        self.assertEqual(w['gravity'], (0.0, -3.0, 0.0))

    def test_global_and_other_rows(self):
        g = L.global_rows({'dt': 1 / 60.0, 'spec': [0.1] * 16})
        self.assertEqual(len(g), L.G_ROWS)
        self.assertTrue(all(len(r) == 4 for r in g))
        self.assertAlmostEqual(g[12][0], 0.1)
        raw = L.flat_core_defaults()
        self.assertEqual(len(L.render_rows(raw, 10, 100)), L.R_ROWS)
        q = L.post_rows(dict(raw, Tealorange=1.0))
        self.assertEqual(len(q), L.Q_ROWS)
        self.assertEqual(q[1][:3], list(L.TEAL))
        self.assertEqual(q[2][:3], list(L.ORANGE))
        self.assertEqual(len(L.source_rows(raw, 10, 100)), L.SRC_ROWS)
        self.assertEqual(L.quality_count(raw), 131072)
        self.assertEqual(L.side_from_pars('custom', 1000), 32)
        self.assertEqual(L.side_from_pars('ultra', 5), 1024)

    def test_beat_and_triggers(self):
        env, ph, bar = L.beat_state(0.5, 120.0)
        self.assertAlmostEqual(ph, 0.0, 9)
        self.assertAlmostEqual(env, 1.0, 9)
        env, ph, bar = L.beat_state(0.75, 120.0, 6.0)
        self.assertAlmostEqual(ph, 0.5)
        self.assertAlmostEqual(env, math.exp(-6 * 0.25))
        self.assertEqual(L.trig_env(1e6, 2.0), 0.0)
        self.assertAlmostEqual(L.trig_env(0.5, 2.0), math.exp(-1.0))


class Effectors(unittest.TestCase):
    def test_affine_inverse(self):
        rnd = random.Random(3)
        for _ in range(20):
            m = [[rnd.uniform(-2, 2) for _ in range(4)] for _ in range(3)]
            inv = L.affine_inverse(m)
            p = [rnd.uniform(-3, 3) for _ in range(3)]
            w = [sum(m[r][k] * p[k] for k in range(3)) + m[r][3] for r in range(3)]
            back = [sum(inv[r][k] * w[k] for k in range(3)) + inv[r][3] for r in range(3)]
            for a, b in zip(p, back):
                self.assertAlmostEqual(a, b, 7)

    def test_affine_from_points(self):
        m = L.affine_from_points((1, 2, 3), (3, 2, 3), (1, 2, 5), (1, 0, 3))        # x2 scale, y->z, z->-y
        self.assertEqual(m, [[2, 0, 0, 1], [0, 0, -2, 2], [0, 2, 0, 3]])

    @unittest.skipIf(np is None, 'numpy')
    def test_box_sdf_rotated_scaled(self):
        a = math.radians(30.0)
        R = [[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]]
        s = 2.0
        world = [[R[r][0] * s, R[r][1] * s, R[r][2] * s, [1.0, 0.5, -1.0][r]] for r in range(3)]
        rows = L.effector_rows([{'kind': 'box', 'world': world, 'speed': 0.0}])
        self.assertAlmostEqual(rows[4][3], 2.0, 9)                              # world scale
        self.assertEqual(rows[3][:1], [2.0])
        # a point 0.3 outside the face along local +x (box half extent 0.5 local = 1.0 world)
        d = np.array([math.cos(a), 0, -math.sin(a)])
        p = np.array([1.0, 0.5, -1.0]) + d * 1.3
        self.assertAlmostEqual(float(L.ref_effector_sd(rows, 0, p[None])[0]), 0.3, 6)
        self.assertAlmostEqual(float(L.ref_effector_sd(rows, 0, np.array([[1.0, 0.5, -1.0]]))[0]), -1.0, 6)

    @unittest.skipIf(np is None, 'numpy')
    def test_sdf_shapes(self):
        q = np.array([[0.0, 2.0, 0.0], [1.0, 0.0, 0.0]])
        self.assertTrue(np.allclose(L.ref_sd_shape(1, q, (0.5, 0, 0)), [1.5, 0.5]))
        self.assertTrue(np.allclose(L.ref_sd_shape(3, q, (0, 0, 0)), [2.0, 0.0]))
        self.assertTrue(np.allclose(L.ref_sd_shape(4, q, (0.25, 0.5, 0)), [1.25, 0.75]))
        self.assertTrue(np.allclose(L.ref_sd_shape(5, np.array([[0.5, 0.0, 0.0]]), (0.5, 0.15, 0)), [-0.15]))
        self.assertTrue(np.allclose(L.ref_sd_shape(0, q, (0, 0, 0)), [2.0, 1.0]))

    @unittest.skipIf(np is None, 'numpy')
    def test_falloff_and_weight(self):
        self.assertTrue(np.allclose(L.ref_fall(np.array([-1.0, 0.0, 0.5, 1.0, 2.0]), 1.0, 1.0, 0), [1, 1, 0.5, 0, 0]))
        self.assertTrue(np.allclose(L.ref_fall(np.array([0.5]), 1.0, 2.0, 1), [0.25]))
        self.assertTrue(np.allclose(L.ref_fall(np.array([0.5, 1.5]), 1.0, 1.0, 3), [1.0, 0.0]))
        self.assertTrue(np.allclose(L.ref_fall(np.array([-0.5]), 1.0, 1.0, 5), [0.5]))
        e = L.effector_rows([{'kind': 'sphere', 'world': L.chop_affine((0, 0, 0), 1.0)},
                             {'kind': 'null', 'world': L.chop_affine((3, 0, 0), 1.0)}])
        p = np.array([[1.0, 0.0, 0.0], [3.5, 0, 0], [10, 0, 0]])
        w = L.ref_prox_w(p, e, 0b11, 2, 1.0, 1.0)
        self.assertTrue(np.allclose(w, [0.5, 0.5, 0.0]))
        self.assertTrue(np.allclose(L.ref_prox_w(p, e, 0b01, 2, 1.0, 1.0), [0.5, 0.0, 0.0]))
        self.assertTrue(np.allclose(L.ref_prox_w(p, e, 0, 2, 1.0, 1.0), [0, 0, 0]))   # nothing linked -> 0
        self.assertTrue(np.allclose(L.ref_prox_w(p, e, 0b11, 2, 1.0, 1.0, comb=1), [0.5, 0.5, 0.0]))

    @unittest.skipIf(np is None, 'numpy')
    def test_push_displacement(self):
        e = L.effector_rows([{'kind': 'sphere', 'world': L.chop_affine((0, 0, 0), 1.0)}])
        p = np.array([[1.0, 0.0, 0.0], [0.0, 0.75, 0.0], [5.0, 0.0, 0.0]])
        out = L.ref_push_displace(p, e, 1, 1, 1.0, 1.0, 0.4)
        self.assertTrue(np.allclose(out[0], [1.2, 0, 0]))                      # w 0.5 -> +0.2 outward
        self.assertTrue(np.allclose(out[2], p[2]))                              # beyond R: untouched
        self.assertGreater(out[1][1], 0.75)


@unittest.skipIf(np is None, 'numpy')
class ReferenceMaths(unittest.TestCase):
    def test_hash_noise_ranges(self):
        r = L.np_rnd(np.arange(100000), 1)
        self.assertTrue(0.0 <= r.min() and r.max() < 1.0)
        self.assertAlmostEqual(float(r.mean()), 0.5, 2)
        p = np.random.default_rng(1).uniform(-20, 20, (5000, 3))
        n = L.np_noise(p, 7)
        self.assertTrue(0.0 <= n.min() and n.max() <= 1.0)
        f = L.np_fbm(p, 3, 13)
        self.assertTrue(0.0 <= f.min() and f.max() <= 1.0)
        c = np.array([[2, 3, 4]])
        self.assertAlmostEqual(float(L.np_noise(c.astype(float), 7)[0]), float(L.np_lattice(c, 7)[0]), 12)

    def test_hash_known_values(self):
        # pinned outputs (also the GLSL constants): a change here changes every look
        self.assertEqual(int(L.np_hash(0)), 0)
        self.assertEqual(int(L.np_hash(1)), int(L.np_hash(np.array([1]))[0]))
        self.assertEqual(int(L.np_weyl(1, 2654435769) * 16777216), 2654435769 >> 8)

    def test_curl_divergence_free(self):
        p = np.random.default_rng(2).uniform(-3, 3, (300, 3))
        h = 1e-4
        for oct_ in (1, 3):
            div = 0.0
            for k in range(3):
                e = np.zeros(3)
                e[k] = h
                div = div + (L.np_curl(p + e, 0.7, oct_)[:, k] - L.np_curl(p - e, 0.7, oct_)[:, k]) / (2 * h)
            mag = np.abs(L.np_curl(p, 0.7, oct_)).mean()
            self.assertLess(float(np.abs(div).max()), 1e-5 * max(1.0, mag) * 100)

    def test_curl_is_curl_of_psi(self):
        p = np.random.default_rng(3).uniform(-2, 2, (50, 3))
        h = 1e-5
        J = np.zeros((50, 3, 3))
        for k in range(3):
            e = np.zeros(3)
            e[k] = h
            J[:, :, k] = (L.np_psi(p + e, 0.3) - L.np_psi(p - e, 0.3)) / (2 * h)
        curl = 0.25 * np.stack([J[:, 2, 1] - J[:, 1, 2], J[:, 0, 2] - J[:, 2, 0], J[:, 1, 0] - J[:, 0, 1]], -1)
        self.assertTrue(np.allclose(curl, L.np_curl1(p, 0.3), atol=1e-6))

    def test_dissolve_noise(self):
        p = np.random.default_rng(4).uniform(-1, 1, (4000, 3))
        prev = None
        for pr in np.linspace(0, 1, 11):
            d = L.ref_dissolve_noise(p, pr)
            if prev is not None:
                self.assertTrue(np.all(d >= prev - 1e-12))
            prev = d
        self.assertEqual(float(L.ref_dissolve_noise(p, 0.0).max()), 0.0)
        self.assertEqual(float(L.ref_dissolve_noise(p, 1.0).min()), 1.0)
        mid = float(L.ref_dissolve_noise(p, 0.5).mean())
        self.assertTrue(0.2 < mid < 0.8, mid)

    def test_twist_wave_explode(self):
        p = np.random.default_rng(5).uniform(-1, 1, (500, 3))
        t = L.ref_twist(p, (0, 0, 0), (0, 1, 0), 1.3)
        self.assertTrue(np.allclose(np.linalg.norm(t[:, [0, 2]], axis=1), np.linalg.norm(p[:, [0, 2]], axis=1)))
        self.assertTrue(np.allclose(t[:, 1], p[:, 1]))
        w = L.ref_wave_sine(p, (1, 0, 0), 3.0, 0.0, 0.1)
        self.assertTrue(np.allclose(w[:, 1] - p[:, 1], 0.1 * np.sin(3.0 * p[:, 0])))
        seed = L.np_rnd(np.arange(500), 1)
        self.assertTrue(np.allclose(L.ref_explode(p, (0, 0, 0), None, seed, 0.0, 3.0), p))
        e = L.ref_explode(p, (0, 0, 0), None, seed, 1.0, 3.0, random=0.0)
        self.assertTrue(np.allclose(np.linalg.norm(e, axis=1) - np.linalg.norm(p, axis=1), 3.0))

    def test_integrate_spring_returns(self):
        o = np.array([[1.0, 0.0, 0.0]])
        v = np.zeros((1, 3))
        for _ in range(600):                                                   # 10 s at 60 fps, defaults
            o, v = L.ref_integrate(o, v, np.zeros((1, 3)), 1 / 60.0)
        self.assertLess(float(np.abs(o).max()), 1e-3)
        o2, v2 = L.ref_integrate(np.array([[1.0, 0, 0]]), np.zeros((1, 3)), np.zeros((1, 3)), 1 / 60.0, dis=1.0)
        self.assertTrue(np.allclose(o2, [[1.0, 0, 0]]))                         # dissolved: not pulled home
        _, v3 = L.ref_integrate(np.zeros((1, 3)), np.array([[100.0, 0, 0]]), np.zeros((1, 3)), 0.0, maxspeed=5.0)
        self.assertAlmostEqual(float(np.linalg.norm(v3)), 5.0)

    def test_generators(self):
        ids = np.arange(4096)
        s = L.ref_gen('sphere', ids, 4096, 1.5)
        self.assertTrue(np.allclose(np.linalg.norm(s, axis=1), 1.5))
        t = L.ref_gen('torus', ids, 4096, 1.0, 0.3)
        ring = np.linalg.norm(t[:, [0, 2]], axis=1) - 1.0
        self.assertTrue(np.allclose(np.sqrt(ring ** 2 + t[:, 1] ** 2), 0.3))
        g = L.ref_gen('grid', ids[:1000], 1000, 1.0)
        self.assertEqual(len(np.unique(np.round(g, 6), axis=0)), 1000)
        self.assertAlmostEqual(float(g.max()), 0.9, 6)
        pl = L.ref_gen('plane', ids[:100], 100, 2.0)
        self.assertAlmostEqual(float(pl[:, 0].max()), 1.8, 6)
        self.assertTrue(np.allclose(pl[:, 2], 0.0))
        r = L.ref_gen('sphere', ids[:10], 10, 1.0, spin=math.pi / 2)
        r0 = L.ref_gen('sphere', ids[:10], 10, 1.0)
        self.assertTrue(np.allclose(r[:, 0], r0[:, 2]))

    def test_unproject(self):
        P = L.ref_unproject(lambda u, v: np.full_like(u, 0.5), 4, fov=90.0, near=1.0, far=3.0, mirror=False)
        self.assertTrue(np.allclose(P[:, 2], 0.0))                              # z mid -> centred at 0
        self.assertAlmostEqual(float(P[:, 0].max()), 0.75 * 2.0, 6)             # u=7/8 -> 0.75 * tan45 * z(2)
        Pm = L.ref_unproject(lambda u, v: np.full_like(u, 0.5), 4, fov=90.0, near=1.0, far=3.0, mirror=True)
        self.assertTrue(np.allclose(Pm[:, 0], -P[:, 0]))

    def test_sprite_radius(self):
        r, a = L.ref_sprite_radius(0.01, 2.0, 1000.0)
        self.assertAlmostEqual(r, 5.0)
        self.assertEqual(a, 1.0)
        r, a = L.ref_sprite_radius(0.01, 2.0, 1000.0, aperture=20.0, focus=1.0)
        self.assertAlmostEqual(r, 10.0)
        self.assertAlmostEqual(a, 0.25)
        r, _ = L.ref_sprite_radius(0.0001, 100.0, 1000.0)
        self.assertAlmostEqual(r, 0.7)

    def test_pack_rest_and_morton(self):
        P = np.random.default_rng(6).uniform(-1, 1, (10, 3)).astype(np.float32)
        img = L.pack_rest(P, side=4)
        self.assertEqual(img.shape, (4, 16, 4))
        self.assertTrue(np.allclose(img[1, 4 * 2:4 * 2 + 1, :3], P[6]))         # id 6 -> y 1, x 2
        self.assertEqual(float(img[3, 4 * 3, 3]), 0.0)                          # past count: invalid
        self.assertEqual(float(img[0, 3, 0]), 1.0)                              # identity quat w
        o = L.morton_order(P)
        self.assertEqual(sorted(o.tolist()), list(range(10)))
        self.assertEqual(len(L.resample_to(P, 25)), 25)
        self.assertEqual(L.resample_to(P, 5).tolist(), [0, 2, 4, 7, 9])


class Presets(unittest.TestCase):
    def test_roundtrip_and_morph(self):
        st = full_stack()[:3]
        a = L.snapshot(st, {'Size': 0.01, 'Sprite': 'soft', 'M1strength': 1.0, 'Play': True}, {'E1': [0] * 9}, 'a')
        b = L.snapshot(st, {'Size': 0.03, 'Sprite': 'ring', 'M1strength': 3.0, 'Play': False, 'M1effectors': 'E2'},
                       {'E1': [1] * 9}, 'b')
        self.assertEqual(L.preset_loads(L.preset_dumps(a)), a)
        self.assertEqual(L.morph_plan(a, b), 'lerp')
        disc = L.discrete_keys(st)
        m = L.morph_flat(a['values'], b['values'], 0.25, 'linear', disc)
        self.assertAlmostEqual(m['Size'], 0.015)
        self.assertEqual(m['Sprite'], 'soft')
        self.assertEqual(m['Play'], True)
        self.assertEqual(m['M1effectors'], 'E2')                                # only in b: jumps
        m = L.morph_flat(a['values'], b['values'], 0.75, 'linear', disc)
        self.assertEqual(m['Sprite'], 'ring')
        self.assertAlmostEqual(L.morph_flat(a['values'], b['values'], 0.5, 'smooth', disc)['M1strength'], 2.0)
        c = L.snapshot(L.move_module(st, 2, 1), {}, {}, 'c')
        self.assertEqual(L.morph_plan(a, c), 'switch')

    def test_bad_preset(self):
        with self.assertRaises(ValueError):
            L.preset_loads('{"x": 1}')


class Perf(unittest.TestCase):
    def test_model(self):
        m = L.perf_model(1048576)
        self.assertEqual(m['side'], 1024)
        self.assertGreater(m['total_ms'], 3.0)                                 # 1M does not fit 3 ms (stated in doc)
        n = L.max_count_for(3.0)
        self.assertTrue(65536 <= n <= 262144, n)
        self.assertEqual(L.tex_sizes(131072)['state'], (5 * 363, 363))
        self.assertEqual(L.tex_sizes(131072)['look'], (3 * 363, 363))

    def test_perf_targets(self):
        # the two user targets (docs/builds/px.md): 250k sprites and the 228k-splat SmileyPinata scene
        sp = L.perf_model(250000)
        self.assertLess(sp['total_ms'], 7.0)
        sm = L.perf_model(L.BL_SPLATS, render='splats', sort_every=2)
        self.assertAlmostEqual(sm['render_gpu_ms'], 4.2, 2)                     # BL_splat_render live number
        self.assertAlmostEqual(sm['sort_spike_ms'], 3.0, 2)
        self.assertAlmostEqual(sm['sort_avg_ms'], 1.5, 2)
        self.assertLess(sm['total_ms'], 16.6)                                  # fits a 60 fps frame alone
        one = L.perf_model(L.BL_SPLATS, render='splats', sort_every=1)
        self.assertGreater(one['total_ms'], sm['total_ms'])
        self.assertGreater(L.perf_model(250000, pts=512)['update_ms'], sp['update_ms'])


SNIP_U = lambda t: SNIPS[(t, 'update')]                                    # noqa: E731
SNIP_C = lambda t: SNIPS[(t, 'colour')]                                    # noqa: E731
try:
    import splat_render_logic as SRL                                       # BL_splat_render's logic (reused)
except ImportError:                                                        # pragma: no cover
    SRL = None


class MenusMatchGlsl(unittest.TestCase):
    """Menu indices the GLSL hard-codes (shape 6..8, mask 7..9, axis 4 view, wave / gradient radial shift)."""

    def test_falloff_shape_indices(self):
        self.assertEqual(L.names(L.FALLOFFS)[6:], ['behind', 'ahead', 'wake'])
        self.assertIn('if (shape == 8) return pxWake', LIB)
        self.assertIn('if (shape >= 6) return pxFront', LIB)
        self.assertIn('if (shape == 7) s = -s;', LIB)

    def test_mask_layers(self):
        for k, n in ((7, 'scene'), (8, 'actor'), (9, 'pool')):
            self.assertEqual(L.menu_index(L.MASKSEL, n), k)
            self.assertIn('if (sel == %d) return lay == %d' % (k, k - 7), LIB)

    def test_axes_view_and_shifted_menus(self):
        self.assertEqual(L.menu_index(L.AXES, 'view'), 4)
        self.assertIn('if (sel == 4) return pxSafeN(CAMFWD', LIB)
        wave = L.param('wave', 'axis')
        self.assertEqual(L.menu_index(wave['menu'], 'radial'), 5)
        self.assertIn('axs == 5 ?', SNIP_U('wave'))
        dg = L.param('dissolve_gradient', 'axis')
        self.assertEqual((L.menu_index(dg['menu'], 'radial'), L.menu_index(dg['menu'], 'custom')), (5, 6))
        self.assertIn('if (am == 5)', SNIP_U('dissolve_gradient'))
        self.assertIn('am == 6 ?', SNIP_U('dissolve_gradient'))

    def test_stretch_axes_and_modes(self):
        self.assertEqual(len(L.STRETCH_AXES), 8)
        for k in range(1, 8):
            self.assertIn('if (sel == %d)' % k, LIB.split('vec3 pxStretchAxis')[1].split('}')[0])
        md = L.param('prox_stretch', 'mode')
        self.assertEqual(L.names(md['menu']), ['stretch', 'lattice', 'slices'])
        self.assertIn('smd == 2', SNIP_U('prox_stretch'))
        self.assertIn('smd == 1', SNIP_C('prox_stretch'))
        self.assertEqual(L.names(L.param('twist', 'mode')['menu']), ['twist', 'bend'])
        self.assertEqual(L.menu_index(L.param('prox_push', 'dir')['menu'], 'velocity'), 4)
        self.assertIn('if (sel == 4) return pxEVel(i, q);', LIB)
        self.assertEqual(L.names(L.param('prox_burn', 'source')['menu']), ['scan', 'volume', 'surface'])

    def test_sprites_and_renders(self):
        self.assertEqual(L.menu_index(L.SPRITES, 'cube'), 6)
        self.assertEqual(L.menu_index(L.SPRITES, 'quad'), 7)
        pix = rd('px_pixel.glsl')
        self.assertIn('if (shape == 6)', pix)
        self.assertIn('else if (shape == 7)', pix)
        self.assertEqual(L.names(L.RENDERS), ['auto', 'sprites', 'splats'])

    def test_every_prox_module_has_edge(self):
        for t, m in L.MODULES.items():
            if 'radius' in [p['name'] for p in m['params']] and m['eff'] and t.startswith(('prox_', 'mask_region')):
                self.assertIsNotNone(L.param(t, 'edge'), t)
        self.assertNotIn('$noisefreq, bi)', MODS)                               # every pxW call passes $edge


class Chunk(unittest.TestCase):
    def test_block_shadows_and_moves_home(self):
        st, u = L.add_module([], 'explode')
        cg = L.codegen(st, LIB, TU, TC, MODS, PAL)
        b = cg['layout'][0]['base']
        self.assertIn('float CH = uM[%d].x;' % (b + 1), cg['update'])
        self.assertIn('uint id = _ci; float seed = _cs; vec3 p0 = _cc; vec3 P = _cP;', cg['update'])
        self.assertIn('home += _dp;', cg['update'])
        self.assertIn('home -= _dp;', cg['update'])
        st, _ = L.add_module([], 'prox_colour')
        cgc = L.codegen(st, LIB, TU, TC, MODS, PAL)
        self.assertNotIn('home += _dp;', cgc['colour'])                         # colour stage: shadows only
        self.assertIn('vec3 p0 = _cc;', cgc['colour'])

    def test_chunk_packed_in_header_row_1(self):
        st, u = L.add_module([], 'jitter')
        lay, n = L.layout(st)
        rows = L.pack_module_rows(lay, n, {u: {'chunk': 0.25, 'amount': 2.0}}, [])
        self.assertEqual(rows[0][0], 2.0)
        self.assertEqual(rows[1], [0.25, 0.0, 0.0, 0.0])
        rows = L.pack_module_rows(lay, n, {u: {'chunk': -1.0}}, [])
        self.assertEqual(rows[1][0], 0.0)                                       # negative = off

    def test_slots_for_pool_sharing(self):
        st = []
        for t in ('prox_burn', 'curl', 'prox_burn', 'prox_burn'):
            st, _ = L.add_module(st, t)
        st = L.set_enabled(st, 4, False)
        cg = L.codegen(st, LIB, TU, TC, MODS, PAL)
        self.assertEqual([(il['type'], il['slot'], il['nslot']) for il in cg['layout']],
                         [('prox_burn', 0, 2), ('curl', 0, 1), ('prox_burn', 1, 2)])
        self.assertIn('const int SLOT = 1, NSLOT = 2;', cg['update'])

    @unittest.skipIf(np is None, 'numpy')
    def test_chunk_moves_cells_rigidly(self):
        # the wrapper's rule on a kinematic displacement d(p): every point of a cell moves by d(cell centre)
        rng = np.random.default_rng(9)
        p0 = rng.uniform(-1, 1, (500, 3))
        ch = 0.25
        cc = (np.floor(p0 / ch) + 0.5) * ch
        d = lambda q: np.stack([np.sin(3 * q[:, 1]), q[:, 0] ** 2, np.cos(q[:, 2])], -1) * 0.1   # noqa: E731
        home = p0 + (cc - p0)
        home = home + d(home) - (cc - p0)
        moved = home - p0
        keys = [tuple(k) for k in np.floor(p0 / ch).astype(int)]
        groups = {}
        for k, m in zip(keys, moved):
            groups.setdefault(k, []).append(m)
        for ms in groups.values():
            self.assertTrue(np.allclose(ms, ms[0]))


class EffectorSystem(unittest.TestCase):
    def test_rows_layout(self):
        w = [[2.0, 0, 0, 1.0], [0, 2.0, 0, 2.0], [0, 0, 2.0, 3.0]]
        rows = L.effector_rows([{'kind': 'pts', 'world': w, 'speed': 1.5, 'vel': (0.0, 0.0, -1.5), 'pts': (10, 20, 1),
                                 'trail': (4, 8), 'size': (0.05, 0, 0)}])
        self.assertEqual(L.E_ROWS, 88)
        self.assertEqual(rows[3][:2], [6.0, 0.05])
        self.assertEqual(rows[6], [0.0, 0.0, -1.5, 10.0])
        self.assertEqual(rows[7], [20.0, 1.0, 4.0, 8.0])
        self.assertEqual(rows[8], [2.0, 0, 0, 1.0])
        # world rows (8..10) undo the inverse rows (0..2)
        p = [0.3, -0.7, 1.1]
        loc = [sum(rows[r][k] * p[k] for k in range(3)) + rows[r][3] for r in range(3)]
        back = [sum(rows[8 + r][k] * loc[k] for k in range(3)) + rows[8 + r][3] for r in range(3)]
        for a, b in zip(p, back):
            self.assertAlmostEqual(a, b, 9)
        cam = L.effector_rows([{'kind': 'camera', 'world': L.chop_affine((0, 0, 5)), 'axis': (0.0, 0.0, -1.0)}])
        self.assertEqual(cam[5][:3], [0.0, 0.0, -1.0])                          # camera: forward is the axis

    def test_eff_pars_td_names(self):
        rx = re.compile(r'^[A-Z][a-z0-9]*$')
        core = set(n for _pg, pars in L.CORE_PAGES for n, *_ in pars)
        for name, style, d, o in L.EFF_PARS:
            self.assertRegex(name, rx)
            if style == 'Menu':
                self.assertIn(d, o['names'])
        self.assertEqual(len(L.EFF_PAR_NAMES), len(set(L.EFF_PAR_NAMES)))
        s = L.eff_settings({'Motion': 'line', 'Max': 5.0})
        self.assertEqual(s['Ma'], (5.0, 0.0, 0.0))
        self.assertEqual(s['Mperiod'], 18.0)
        self.assertFalse(core & set(L.EFF_PAR_NAMES))

    def test_motion_paths(self):
        s = L.eff_settings({'Mease': 'linear', 'Mperiod': 18.0})
        self.assertEqual(L.motion_pos('line', 0.0, s), (-2.0, 0.0, 0.0))
        self.assertAlmostEqual(L.motion_pos('line', 9.0, s)[0], 0.0, 9)         # half way at 9 s
        sp = dict(s, Mloop='pingpong')
        self.assertAlmostEqual(L.motion_pos('line', 9.0, sp)[0], 2.0, 9)        # ping-pong: B at half period
        self.assertAlmostEqual(L.motion_pos('line', 18.0, sp)[0], -2.0, 9)
        so = dict(s, Mloop='once')
        self.assertEqual(L.motion_pos('line', 50.0, so), (2.0, 0.0, 0.0))
        c = L.eff_settings({'Motion': 'circle', 'Max': 0, 'Mbx': 1.5, 'Mby': 0, 'Mbz': 1.5, 'Mperiod': 4.0})
        for t in (0.0, 0.7, 2.3):
            x, y, z = L.motion_pos('circle', t, c)
            self.assertAlmostEqual(math.hypot(x, z), 1.5, 9)
        li = L.eff_settings({'Mperiod': 2.0})
        x, y, z = L.motion_pos('lissajous', 0.0, li)
        self.assertAlmostEqual(y, li['Ma'][1] + li['Mb'][1], 9)                 # y runs a quarter turn ahead
        self.assertAlmostEqual(x, li['Ma'][0], 9)
        pts = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
        ch = L.eff_settings({'Mease': 'linear', 'Mloop': 'once', 'Mperiod': 2.0})
        self.assertEqual(L.motion_pos('chop', 1.0, ch, chop_pts=pts), (1.0, 0.0, 0.0))
        self.assertEqual(L.motion_pos('chop', 2.0, ch, chop_pts=pts), (1.0, 1.0, 0.0))
        self.assertIsNone(L.motion_pos('chop', 1.0, ch, chop_pts=[]))
        wa = L.eff_settings({'Max': 1, 'May': 2, 'Maz': 3, 'Mbx': 0.5, 'Mby': 0.5, 'Mbz': 0.5})
        for t in np.linspace(0, 60, 200) if np is not None else (0.0, 7.0):
            p = L.motion_pos('wander', float(t), wa)
            self.assertTrue(all(abs(p[k] - (1, 2, 3)[k]) <= 0.5 + 1e-9 for k in range(3)))
        fo = L.eff_settings({'Max': 0, 'May': 1, 'Maz': 0, 'Mlag': 0.3})
        p = (0.0, 0.0, 0.0)
        for _ in range(300):
            p = L.motion_pos('follow', 0.0, fo, follow=(2.0, 0.0, 0.0), prev=p, dt=1 / 60.0)
        self.assertAlmostEqual(p[0], 2.0, 4)
        self.assertAlmostEqual(p[1], 1.0, 4)                                    # + A offset
        self.assertIsNone(L.motion_pos('none', 1.0, s))

    def test_trail_ring(self):
        b = []
        for k in range(20):
            b = L.trail_push(b, (k, 0, 0), k * 0.02, 8, 0.05)
        self.assertLessEqual(len(b), 8)
        self.assertEqual(b[0][0], (19, 0, 0))                                   # head follows the effector
        self.assertGreaterEqual(b[0][1] - b[1][1], 0.05 - 1e-9)
        self.assertEqual(L.trail_push(b, (0, 0, 0), 1.0, 0, 0.05), [])
        rows, spans = L.trail_rows([b, [], b[:2]], 1.0)
        self.assertEqual(spans, [(0, len(b)), (len(b), 0), (len(b), 2)])
        self.assertAlmostEqual(rows[0][3], 1.0 - b[0][1])

    def test_load_keep(self):
        import numpy as np
        P = np.array([[0, 0, 0], [0.1, 0, 0], [0, 0.1, 0], [50, 0, 0]], float)
        C = np.array([[1, 1, 1, 1], [1, 1, 1, 0.01], [1, 1, 1, 0.5], [1, 1, 1, 1]], float)
        self.assertEqual(L.load_keep(P, C, 5.0, 0.0).tolist(), [0, 1, 2])
        self.assertEqual(L.load_keep(P, C, 5.0, 0.1).tolist(), [0, 2])
        self.assertEqual(L.load_keep(P, C, 0.0, 0.0).tolist(), [0, 1, 2, 3])
        self.assertEqual(L.load_keep(P, C, 1e-9, 2.0).tolist(), [0, 1, 2, 3])      # never empty

    def test_point_sets(self):
        a = L.pts_from_chans({'tx': [0, 1, 2], 'ty': [0, 0, 0], 'tz': [5, 5, 5]})
        self.assertEqual(a, [(0.0, 0.0, 5.0), (1.0, 0.0, 5.0), (2.0, 0.0, 5.0)])
        b = L.pts_from_chans({'lm0tx': [1], 'lm0ty': [2], 'lm0tz': [3], 'lm1x': [4], 'lm1y': [5], 'lm1z': [6]})
        self.assertEqual(b, [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)])
        f = L.pts_from_chans({'f1_jaw_00x': [0.25], 'f1_jaw_00y': [0.5], 'f1_jaw_01x': [0.3], 'f1_jaw_01y': [0.6]})
        self.assertEqual(f, [(0.25, 0.5, 0.0), (0.3, 0.6, 0.0)])         # 2D landmarks (FT_face_track out_pts)
        self.assertEqual(L.pts_from_chans({'r': [1], 'g': [2], 'b': [3], 'a': [1]}), [(1.0, 2.0, 3.0)])  # TOP to CHOP
        self.assertEqual(L.pts_from_chans({'P_0': [1], 'P_1': [2], 'P_2': [3]}), [(1.0, 2.0, 3.0)])     # POP to CHOP
        self.assertEqual(L.pts_subsample(list(range(10)), 4), [0, 2, 5, 7])
        self.assertEqual(L.xform_pts(L.chop_affine((1, 0, 0), 2.0), [(1, 1, 1)]), [(3.0, 2.0, 2.0)])
        v = L.pts_velocity([(1, 0, 0)], [(0, 0, 0)], 0.5)
        self.assertEqual(v, [(2.0, 0.0, 0.0)])
        self.assertEqual(L.pts_velocity([(1, 0, 0)], None, 0.5), [(0.0, 0.0, 0.0)])
        big = [(float(k), 0.0, 0.0) for k in range(3000)]
        rows, vrows, spans = L.pack_pts([(big, big), (big, big)])
        self.assertEqual(len(rows), L.PTS_MAX)
        self.assertEqual(spans, [(0, 3000), (3000, L.PTS_MAX - 3000)])

    def test_quaternions(self):
        rng = random.Random(4)
        for _ in range(20):
            ax = [rng.uniform(-1, 1) for _ in range(3)]
            a = rng.uniform(-3, 3)
            q = L.quat_axis(ax, a)
            if SRL is not None and np is not None:
                R = SRL.quat_to_mat3(np.array(q)).tolist()
                q2 = L.quat_from_mat3(R)
                self.assertTrue(all(abs(x - y) < 1e-9 for x, y in zip(q2, q if q[0] >= 0 else [-c for c in q])))
        q1, q2 = L.quat_axis((0, 1, 0), 0.5), L.quat_axis((0, 1, 0), 0.25)
        q3 = L.quat_mul(q1, q2)
        self.assertTrue(all(abs(a - b) < 1e-12 for a, b in zip(q3, L.quat_axis((0, 1, 0), 0.75))))
        a = math.radians(40.0)
        w = [[2 * math.cos(a), 0, 3 * math.sin(a), 1], [0, 0.5, 0, 2], [-2 * math.sin(a), 0, 3 * math.cos(a), 3]]
        sc, q = L.affine_scale_quat(w)
        self.assertTrue(all(abs(x - y) < 1e-9 for x, y in zip(sc, (2.0, 0.5, 3.0))))
        self.assertTrue(all(abs(x - y) < 1e-9 for x, y in zip(q, L.quat_axis((0, 1, 0), a))))

    def test_glow_rows(self):
        st = L.eff_settings({'Glow': True, 'Glowintensity': 3.0, 'Glowsize': 2.0, 'Glowtrail': True})
        w = [[4.0, 0, 0, 0], [0, 1.0, 0, 1.0], [0, 0, 4.0, 0]]
        trail = [((0, 1, -k * 0.1), k * 0.05) for k in range(16)]
        rows, n = L.glow_rows([{'kind': 'plane', 'world': w, 'settings': st, 'trail': trail},
                               {'kind': 'sphere', 'world': w, 'settings': L.eff_settings({})}])
        self.assertEqual(n, 1 + 8)                                              # glow off on the second, 8 trail
        self.assertEqual(len(rows), n * L.GLOW_PER)
        self.assertEqual(rows[0][:3], [0.0, 1.0, 0.0])
        self.assertAlmostEqual(rows[1][0], 0.5 * 4.0 * 2.0 * 0.5)               # half size x scale x size / 2
        self.assertAlmostEqual(rows[1][1], 0.02 * 1.0 * 2.0 * 0.5)              # a plane glows as a thin slab
        self.assertAlmostEqual(rows[3][0], 3.0)                                 # colour x intensity
        self.assertLess(rows[7][0], rows[3][0])                                 # trail glows fade
        _r, n0 = L.glow_rows([])
        self.assertEqual(n0, 0)


@unittest.skipIf(np is None, 'numpy')
class EffectorMaths(unittest.TestCase):
    def _rows(self, kind='plane', vel=(0.0, 0.0, 0.0), centre=(0.0, 0.0, 0.0)):
        return L.effector_rows([{'kind': kind, 'world': L.chop_affine(centre), 'vel': vel,
                                 'speed': float(np.linalg.norm(vel))}])

    def test_front_behind_ahead(self):
        e = self._rows(vel=(1.0, 0.0, 0.0))                                     # front moving +x through 0
        p = np.array([[-0.5, 0, 0], [-1.0, 0, 0], [-2.0, 0, 0], [0.01, 0, 0], [0.5, 0, 0], [0.0, 3.0, 7.0]])
        w = L.ref_front(p, e, 0, 1.0, 1.0, 6, edge=0.02)
        self.assertTrue(np.allclose(w[[0, 1, 2]], [0.5, 0.0, 0.0]))              # tail behind: 1 + s / R
        self.assertAlmostEqual(float(w[3]), 1.0 - 0.5 ** 2 * (3 - 2 * 0.5) * 1.0, 6)  # inside the 0.02 edge
        self.assertEqual(float(w[4]), 0.0)                                      # ahead: nothing
        self.assertEqual(float(w[5]), 1.0)                                      # the front is infinite sideways
        wa = L.ref_front(-p, e, 0, 1.0, 1.0, 7, edge=0.02)
        self.assertTrue(np.allclose(wa, w))                                     # ahead mirrors behind
        still = L.effector_rows([{'kind': 'plane', 'world': [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]}])
        self.assertTrue(np.allclose(L.ref_move_dir(still, 0), [0, 1, 0]))       # still: up axis (plane normal)

    def test_wake_tube(self):
        trail = [((-1.0, 0.0, 0.0), 0.5), ((-2.0, 0.0, 0.0), 1.0)]
        p = np.array([[-1.0, 0.0, 0.0], [-1.5, 0.2, 0.0], [-2.0, 0.0, 0.0], [-1.0, 2.0, 0.0], [1.0, 0.0, 0.0]])
        w = L.ref_wake(p, (0, 0, 0), trail, 0.5, 1.0)
        self.assertAlmostEqual(float(w[0]), 0.5, 9)                              # on the path, half the age
        self.assertEqual(float(w[2]), 0.0)                                       # oldest = faded
        self.assertEqual(float(w[3]), 0.0)                                       # outside the tube
        self.assertEqual(float(w[4]), 0.0)                                       # ahead of the head
        self.assertGreater(float(w[1]), 0.0)

    def test_pts_nearest_density(self):
        Q = np.array([[0.0, 0, 0], [1.0, 0, 0]])
        V = np.array([[0.0, 1.0, 0], [0.0, -1.0, 0]])
        p = np.array([[0.2, 0, 0], [0.9, 0.1, 0], [5.0, 0, 0]])
        d, v = L.ref_pts_nearest(p, Q, V, radius=0.05)
        self.assertTrue(np.allclose(d, [0.15, math.hypot(0.1, 0.1) - 0.05, 3.95]))
        self.assertTrue(np.allclose(v, [[0, 1, 0], [0, -1, 0], [0, -1, 0]]))
        dd, _ = L.ref_pts_nearest(np.array([[0.0, 0, 0]]), Q, radius=1.0, mode=1)
        self.assertAlmostEqual(float(dd[0]), -math.log(1.0 + math.exp(-0.5)), 9)  # two kernels overlap: inside
        dfar, _ = L.ref_pts_nearest(np.array([[0.5, 0, 0]]), Q, radius=0.1, mode=1)
        self.assertAlmostEqual(float(dfar[0]), -0.1 * math.log(2 * math.exp(-0.25 / 0.02)), 9)

    def test_bend(self):
        a = np.array([0.0, 1.0, 0.0])
        k = 0.8
        s = np.linspace(-2, 2, 41)
        r = s[:, None] * a
        b = L.ref_bend(r, a, k)
        _a, bd, _n = L.ref_bend_frame(a)
        ctr = bd / k
        self.assertTrue(np.allclose(np.linalg.norm(b - ctr, axis=1), 1.0 / k))  # the axis becomes a circle arc
        seg = np.linalg.norm(np.diff(b, axis=0), axis=1)
        self.assertTrue(np.allclose(seg.sum(), 4.0, atol=2e-3))                 # arc length kept
        self.assertTrue(np.allclose(L.ref_bend(r, a, 0.0), r))
        p = np.random.default_rng(3).uniform(-1, 1, (50, 3))
        self.assertTrue(np.allclose(L.ref_bend(p, a, 1e-9), p))

    def test_stretch_covariance(self):
        a = np.array([1.0, 2.0, 0.5])
        a /= np.linalg.norm(a)
        M = L.ref_stretch_matrix(a, 4.0, 0.6)
        self.assertTrue(np.allclose(M @ a, 5.0 * a))
        u = np.cross(a, [0, 0, 1.0])
        u /= np.linalg.norm(u)
        self.assertTrue(np.allclose(M @ u, (1 - 0.75 * 0.6) * u))
        self.assertTrue(np.allclose(M, M.T))
        # the shader's hook form t -> th t + (1 + st - th) a (a.t) is M t
        t = np.array([0.3, -1.2, 2.0])
        th = 1 - 0.75 * 0.6
        self.assertTrue(np.allclose(th * t + (1 + 4.0 - th) * a * (a @ t), M @ t))
        if SRL is not None:
            Sg = SRL.cov3d(np.array([0.1, 0.05, 0.02]), np.array(L.quat_axis((0, 1, 0), 0.7)))
            view = np.eye(4)
            view[2, 3] = -4.0
            _m, c0, _z = SRL.project_cov2d([0, 0, 0], M @ Sg @ M, view, 1000.0, 1000.0, 1080, 1920, 0.0)
            T = np.array([[1000.0 / 4, 0, 0], [0, 1000.0 / 4, 0]])
            self.assertTrue(np.allclose(c0, (T @ M) @ Sg @ (T @ M).T))
        sq = L.ref_stretch_matrix(a, -0.9, 0.0)
        self.assertTrue(np.allclose(sq @ a, 0.1 * a))                           # shards: flatten along the axis

    def test_splat_dof_energy(self):
        C = np.array([[9.0, 2.0], [2.0, 4.0]])
        C2, f = L.ref_splat_dof(C, 6.0, 0.0)
        self.assertTrue(np.allclose(C2, C + 9.0 * np.eye(2)))
        self.assertAlmostEqual(f * math.sqrt(np.linalg.det(C2)), math.sqrt(np.linalg.det(C)), 9)
        _c, f2 = L.ref_splat_dof(C, 200.0, 0.02)
        self.assertEqual(f2, 0.02)
        self.assertEqual(L.ref_splat_dof(C, 0.0)[1], 1.0)

    def test_slices(self):
        p = np.random.default_rng(5).uniform(-1, 1, (20000, 3))
        gap, snapped = L.ref_slices(p, (0, 0, 0), (0, 1, 0), 0.1, 0.45)
        self.assertAlmostEqual(float(gap.mean()), 0.45, 1)
        f = snapped[:, 1] / 0.1 - 0.5
        self.assertTrue(np.allclose(f, np.round(f), atol=1e-9))                 # band centre planes

    def test_cone(self):
        ids = np.arange(5000)
        ax = np.array([0.0, 1.0, 0.0])
        d = L.ref_cone_dirs(ids, 7, ax, 25.0)
        self.assertTrue(np.allclose(np.linalg.norm(d, axis=1), 1.0))
        ang = np.degrees(np.arccos(np.clip(d @ ax, -1, 1)))
        self.assertLessEqual(float(ang.max()), 25.0 + 1e-6)
        self.assertGreater(float((d.mean(0) @ ax)), 0.95)


class LayersSortSplats(unittest.TestCase):
    def test_layers(self):
        raw = dict(L.flat_core_defaults(), Quality='custom', Count=10000)
        self.assertEqual(L.layers(raw), (10000, 0, 0))
        raw.update(Actormode='gen', Actorcount=2000, Pool=15.0)
        self.assertEqual(L.layers(raw), (6500, 2000, 1500))
        self.assertEqual(L.layers(dict(raw, Actorcount=50000)), (1, 9999, 0))
        self.assertEqual(L.sprite_range('sprites', 6500, 2000, 1500), (0, 10000))
        self.assertEqual(L.sprite_range('splats', 6500, 2000, 1500), (8500, 1500))
        self.assertEqual(L.render_mode({'Render': 'auto'}, True), 'splats')
        self.assertEqual(L.render_mode({'Render': 'auto'}, False), 'sprites')
        self.assertEqual(L.render_mode({'Render': 'sprites'}, True), 'sprites')

    def test_rows_shapes(self):
        raw = L.flat_core_defaults()
        self.assertEqual(len(L.source_rows(raw, 10, 100)), L.SRC_ROWS)
        self.assertIn('uniform vec4 uSrc[%d];' % L.SRC_ROWS, TS)
        vec, sp = L.splat_rows(raw, 228287, ns=200000, na=8000)
        self.assertEqual((len(vec), len(sp)), (7, L.SP_ROWS))
        self.assertEqual(vec[0][2], 0.0)                                        # no order texture (POP order)
        self.assertEqual(sp[0][:3], [float(L.side_for(228287)), 228287.0, 208000.0])
        q = L.post_rows(dict(raw, Flare=1.5, Flareghosts=4))
        self.assertEqual(len(q), L.Q_ROWS)
        self.assertEqual(q[6][1], 1.5)
        self.assertEqual(q[7][0], 4.0)
        self.assertIn('uniform vec4 uQ[%d];' % L.Q_ROWS, rd('px_post.glsl'))
        g = L.global_rows({'count': 100, 'nscene': 80, 'nactor': 15, 'npool': 5, 'camfwd': (0, 0, -1),
                           'actorvel': (1, 2, 3)})
        self.assertEqual(g[20][:3], [0.0, 0.0, -1.0])
        self.assertEqual(g[21][:3], [80.0, 15.0, 5.0])
        self.assertEqual(g[22][:3], [1.0, 2.0, 3.0])
        self.assertEqual(L.global_rows({'count': 77})[21][0], 77.0)            # no layers given: all scene
        r = L.render_rows(raw, 10, 100, first=60, end=100)
        self.assertEqual(r[7][:2], [60.0, 100.0])

    @unittest.skipIf(SRL is None, 'splat_render_logic')
    def test_sort_gate(self):
        f = lambda mode, frame, last, moving, cam, **kw: L.sort_due(mode, frame, last, 2, moving, cam, **kw)  # noqa
        self.assertTrue(f('auto', 0, None, False, False))                       # first frame
        self.assertFalse(f('auto', 10, 9, True, False))                         # moving, 1 frame since
        self.assertTrue(f('auto', 11, 9, True, False))                          # moving, every 2
        self.assertFalse(f('auto', 30, 9, False, False))                        # still scene, still camera
        cam = SRL.need_sort('sortpop', 30, 9, 0, (0, 0, -1), (0.0, 0.2, -1.0), (0, 0, 5), (0, 0, 5), 1.0, 1.0)
        self.assertTrue(f('auto', 30, 9, False, cam))                           # BL camera gate: turned > 1 deg
        self.assertTrue(f('always', 10, 9, False, False))
        self.assertFalse(f('frozen', 99, 9, True, True))
        self.assertTrue(f('frozen', 99, 9, True, True, pulse=True))
        self.assertFalse(f('off', 0, None, True, True, data_changed=True))
        # T-143 cap: at most max_hz sorts per second in auto (pulse / data change ignore it)
        self.assertFalse(f('auto', 11, 9, True, False, since_s=0.03, max_hz=20.0))
        self.assertTrue(f('auto', 11, 9, True, False, since_s=0.06, max_hz=20.0))
        self.assertTrue(f('auto', 11, 9, True, False, since_s=0.01, max_hz=0.0))  # 0 = no cap
        self.assertTrue(f('auto', 11, 9, True, False, since_s=0.01, max_hz=20.0, pulse=True))
        self.assertTrue(f('always', 10, 9, False, False, since_s=0.001, max_hz=20.0))
        st, _ = L.add_module([], 'mask_region')
        self.assertFalse(L.stack_moves(st))
        st, _ = L.add_module(st, 'twist')
        self.assertTrue(L.stack_moves(st))
        self.assertFalse(L.stack_moves(L.set_enabled(st, 2, False)))

    @unittest.skipIf(np is None, 'numpy')
    def test_rest_files_and_actor_frames(self):
        side = 4
        a = L.pack_rest(np.ones((5, 3)), side=side)
        b = L.pack_rest(np.full((7, 3), 2.0), side=side)
        f = L.stack_files(a, b, side)
        self.assertEqual(f.shape, (2 * side, 4 * side, 4))
        self.assertEqual(float(f[side, 0, 0]), 2.0)                             # B starts at row side
        self.assertEqual(L.stack_files(None, b, side).shape, (2 * side, 4 * side, 4))
        self.assertEqual(float(L.stack_files(None, b, side)[0, 0, 3]), 0.0)      # empty A = invalid
        self.assertEqual(float(a[0, 2, 0]), 0.0)                                # no scale = 0 (no splat scale)
        self.assertEqual(L.actor_frame(1.0, 24, 10), 4)
        self.assertEqual(L.actor_frame(1.0, 24, 10, loop=False), 9)
        self.assertEqual(L.actor_frame(1.0, 24, 0), -1)


class BuiltinPresets(unittest.TestCase):
    def test_all_six(self):
        self.assertTrue({'KANDA swipe', 'Hanging streaks', 'Alley people fire', 'Radial blast', 'Slice bike',
                         'Tile city'} <= set(L.BUILTIN))                     # + the wave-2 looks (test_px_wave2)

    def test_snapshots_are_valid(self):
        core = set(L.flat_core_defaults())
        for name in L.BUILTIN:
            snap = L.builtin_preset(name)
            self.assertEqual(L.preset_loads(L.preset_dumps(snap))['stack'], snap['stack'], name)
            flat_names = set()
            for inst in snap['stack']:
                flat_names |= set(L.flat_par_names(inst))
            makes = [m[0] for m in snap['make']]
            for k, v in snap['values'].items():
                self.assertTrue(k in flat_names or k in core, (name, k))
                if k.endswith('effectors') and k.startswith('M'):
                    lights = [l[0] for l in snap.get('lights', [])]
                    for en in str(v).split():           # own names are made; shared ones are #tags / all / lights
                        self.assertTrue(en in makes or en in lights or en.startswith('#') or en == 'all', (name, k))
                if k.endswith('drive') and k.startswith('M'):
                    self.assertEqual(L.parse_drives(v)[1], [], (name, v))
            for kind in (m[1] for m in snap['make']):
                self.assertIn(kind, L.names(L.EFF_KINDS))
            for en, vals in snap['effpars'].items():
                self.assertTrue(set(vals) <= set(L.EFF_PAR_NAMES), (name, en))
            for en, xf in snap['effectors'].items():
                self.assertEqual(len(xf), 9)
            self.assertFalse(L.check_snippets(SNIPS))

    def test_pool_and_actor_presets(self):
        s = L.builtin_preset('Alley people fire')
        self.assertEqual(s['values']['Pool'], 15.0)
        self.assertEqual(s['values']['Actormode'], 'gen')
        self.assertIn(['Eact', 'actor'], s['make'])
        r = L.builtin_preset('Radial blast')
        self.assertIn(['Ecam', 'camera'], r['make'])
        self.assertNotIn('Ecam', r['effectors'])                                # the camera is not moved by presets
        k = L.builtin_preset('KANDA swipe')
        self.assertEqual(k['effpars']['Esw']['Motion'], 'line')
        self.assertEqual(k['effpars']['Esw']['Mperiod'], 18.0)                  # a front crossing in 18 s
        self.assertEqual(k['values']['M1colour2r'], 1.0)                        # rgb split into components


class SplatLooks(unittest.TestCase):
    """27 Oct splat lane: every look has a splat version (Render splats + a splat source) + splat_showcase."""
    def setUp(self):
        self.ember = L.snapshot([], {'Amode': 'file', 'Afile': '/x/hornedlizard.spz', 'Quality': 'std'}, {},
                                'ember_splat')
        self.ps = dict(L.splat_presets(lambda nm: self.ember if nm == 'ember_splat' else None))

    def test_every_look_has_a_splat_version(self):
        older = [n for n in L.BUILTIN if not L.BUILTIN[n].get('scene')       # wave-2 looks are splat scenes already
                 and not L.BUILTIN[n].get('nosplat')]                          # wave 4: an image source stays sprites
        want = [n + L.SPLAT_SUFFIX for n in older + ['ember_splat']] + ['splat_showcase']
        self.assertEqual(sorted(self.ps), sorted(want))
        self.assertEqual(len(L.splat_presets()), 7)                              # ember missing -> skipped

    def test_render_and_source(self):
        core = set(L.flat_core_defaults())
        for name, s in self.ps.items():
            v = s['values']
            self.assertEqual(v['Render'], 'splats', name)
            self.assertEqual(v['Amode'], 'file', name)
            self.assertTrue(str(v['Afile']).endswith(('.splat', '.spz', '.ply')), name)
            self.assertEqual(s['name'], name)
            for sc in L.SPLAT_SCENES.values():
                self.assertTrue(set(sc) <= core)
            self.assertEqual(L.preset_loads(L.preset_dumps(s))['stack'], s['stack'], name)
        self.assertEqual(self.ps['ember_splat (splats)']['values']['Afile'], '/x/hornedlizard.spz')   # own source kept

    def test_look_wins_over_scene_and_auto_picks_splats(self):
        a = self.ps['Alley people fire (splats)']['values']
        self.assertEqual(a['Actormode'], 'gen')                                  # look's actor, not the scene's off
        self.assertEqual(a['Pool'], 15.0)
        self.assertEqual(self.ps['KANDA swipe (splats)']['values']['Actormode'], 'off')
        self.assertEqual(L.render_mode({'Render': 'auto'}, True), 'splats')
        self.assertEqual(L.render_mode({'Render': 'auto'}, False), 'sprites')

    def test_full_scene_no_holes(self):
        tv = L.SPLAT_SCENES['truck']
        self.assertEqual((tv['Quality'], tv['Count']), ('custom', 524288))       # keeps 20 % of truck, the splat cap
        self.assertGreater(tv['Splatmaxpx'], 0.0)
        for name, s in self.ps.items():
            if s['values'].get('Afile', '').endswith('truck.splat'):
                for k in ('Camdist', 'Camheight', 'Focus', 'Aperture', 'Clip', 'Count'):
                    self.assertIn(k, s['values'], (name, k))                     # full scene: nothing inherited

    def test_footprint_cap_and_ascale_rows(self):
        raw = dict(L.flat_core_defaults(), Splatmaxpx=48.0, Ascale=0.5)
        _vec, sp = L.splat_rows(raw, 1000)
        self.assertEqual(sp[3][2:], [48.0, 0.5])
        self.assertEqual(L.splat_rows(L.flat_core_defaults(), 1000)[1][3][2:], [0.0, 1.0])   # off + 1: BL parity
        a, b, c, k = L.ref_splat_clamp((100.0 ** 2, 0.0, 10.0 ** 2), 50.0)
        self.assertAlmostEqual(math.sqrt(a), 50.0, 6)                              # larger sigma capped at 50 px
        self.assertAlmostEqual(math.sqrt(c), 5.0, 6)                               # shape kept (ratio 10:1)
        self.assertAlmostEqual(k, 0.25, 9)                                        # alpha x k: energy kept
        self.assertEqual(L.ref_splat_clamp((9.0, 1.0, 4.0), 50.0)[3], 1.0)
        self.assertEqual(L.ref_splat_clamp((1e6, 0.0, 1e6), 0.0)[3], 1.0)
        ad = open(os.path.join(BUILDERS, 'glsl', 'px_splat_adapter.glsl')).read()
        self.assertIn('pxsClamp(a, b, c, alpha)', ad)
        self.assertIn('uSp[3].w', ad)

    def test_showcase(self):
        s = self.ps['splat_showcase']
        self.assertEqual(s['values']['Render'], 'splats')
        self.assertTrue(s['effpars']['Esw']['Glow'])
        self.assertTrue(set(s['effpars']['Esw']) <= set(L.EFF_PAR_NAMES))
        self.assertFalse(L.builtin_preset('KANDA swipe')['effpars']['Esw']['Glow'])   # built-in: glow off, whole page
        self.assertEqual(L.builtin_preset('KANDA swipe')['effpars']['Esw']['Trail'], 0)


STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""
STUB_VERT = """#version 460
in vec3 P;
struct TDMatrix { mat4 world; mat4 worldCam; mat4 proj; };
uniform TDMatrix uTDMats[1];
int TDInstanceID() { return gl_InstanceID; }
int TDCameraIndex() { return 0; }
"""
STUB_PIXEL = """#version 460
void TDCheckDiscard() {}
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""
# GLSL MAT stubs for the reused BL splat shader (one DAT for both stages, TD_VERTEX_SHADER / TD_PIXEL_SHADER)
STUB_SPLAT_VERT = """#version 460
#define TD_VERTEX_SHADER 1
struct TDMatrix { mat4 world; mat4 worldCam; mat4 cam; mat4 camInverse; mat4 proj; };
uniform TDMatrix uTDMats[1];
int TDInstanceID() { return gl_InstanceID; }
int TDCameraIndex() { return 0; }
in vec3 P;
vec4 TDPos() { return vec4(P, 1.0); }
float TDSimplexNoise(vec4 v) { return 0.0; }
vec4 TDInstanceCustomAttrib0(int i) { return vec4(float(i)); }
vec4 TDInstanceCustomAttrib1(int i) { return vec4(1.0); }
vec4 TDInstanceCustomAttrib2(int i) { return vec4(1.0, 0.0, 0.0, 0.0); }
vec4 TDInstanceCustomAttrib3(int i) { return vec4(1.0); }
vec4 TDInstanceCustomAttrib4(int i) { return vec4(0.0); }
vec4 TDInstanceCustomAttrib5(int i) { return vec4(0.0); }
vec4 TDInstanceCustomAttrib6(int i) { return vec4(0.0); }
"""
STUB_SPLAT_PIXEL = """#version 460
#define TD_PIXEL_SHADER 1
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""
SPLAT_GLSL = _read(os.path.join(BUILDERS, 'splat_render.glsl'))


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def _ok(self, text, ext, what):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.' + ext)
            with open(p, 'w') as fh:
                fh.write(text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, '%s\n%s' % (what, r.stderr[:2000]))

    def test_empty_stack(self):
        cg = L.codegen([], LIB, TU, TC, MODS, PAL)
        self._ok(STUB_COMPUTE + cg['update'], 'comp', 'update empty')
        self._ok(STUB_COMPUTE + cg['update_inplace'], 'comp', 'update inplace empty')
        self._ok(STUB_COMPUTE + cg['colour'], 'comp', 'colour empty')

    def test_each_module_alone(self):
        for t in L.MODULES:
            st, _ = L.add_module([], t)
            cg = L.codegen(st, LIB, TU, TC, MODS, PAL)
            self._ok(STUB_COMPUTE + cg['update'], 'comp', 'update ' + t)
            self._ok(STUB_COMPUTE + cg['colour'], 'comp', 'colour ' + t)

    def test_everything_with_duplicates(self):
        st = full_stack()
        for u in (1, 5, 9):
            st, _ = L.duplicate_module(st, u)
        cg = L.codegen(st, LIB, TU, TC, MODS, PAL)
        self._ok(STUB_COMPUTE + cg['update'], 'comp', 'update all')
        self._ok(STUB_COMPUTE + cg['update_inplace'], 'comp', 'update all inplace')
        self._ok(STUB_COMPUTE + cg['colour'], 'comp', 'colour all')

    def test_fixed_shaders(self):
        self._ok(STUB_COMPUTE + L.source_text(LIB, TS), 'comp', 'source')
        self._ok(STUB_COMPUTE + rd('px_post.glsl'), 'comp', 'post')
        self._ok(STUB_COMPUTE + rd('px_glow.glsl'), 'comp', 'glow')
        self._ok(STUB_COMPUTE + rd('px_trail.glsl'), 'comp', 'trail')
        self._ok(STUB_VERT + rd('px_vert.glsl'), 'vert', 'vertex')
        self._ok(STUB_PIXEL + rd('px_pixel.glsl'), 'frag', 'pixel')
        tree = ast.parse(_read(os.path.join(BUILDERS, 'px.py')))
        dp = next(n.value.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == 'DEPTH_PACK')
        self._ok(STUB_COMPUTE + dp, 'comp', 'depth_pack')
        self._ok(STUB_COMPUTE + rd('px_sortkey.glsl'), 'comp', 'sort keys')
        self._ok(STUB_COMPUTE + rd('px_layers.glsl'), 'comp', 'layers')

    def test_reused_splat_shader(self):
        # BL_splat_render alone (hooks empty) and the two PX adapters on top of the same text (S1, A5)
        self._ok(STUB_SPLAT_VERT + SPLAT_GLSL, 'vert', 'splat_render vertex (BL)')
        self._ok(STUB_SPLAT_PIXEL + SPLAT_GLSL, 'frag', 'splat_render pixel (BL)')
        for ad in ('px_splat_adapter.glsl', 'px_glow_adapter.glsl'):
            self._ok(STUB_SPLAT_VERT + rd(ad) + SPLAT_GLSL, 'vert', ad + ' vertex')
            self._ok(STUB_SPLAT_PIXEL + rd(ad) + SPLAT_GLSL, 'frag', ad + ' pixel')

    def test_builtin_presets_compile(self):
        for name in L.BUILTIN:
            cg = L.codegen(L.builtin_preset(name)['stack'], LIB, TU, TC, MODS, PAL)
            self._ok(STUB_COMPUTE + cg['update'], 'comp', 'update ' + name)
            self._ok(STUB_COMPUTE + cg['colour'], 'comp', 'colour ' + name)

    def test_chunk_on_everything_inplace(self):
        st = full_stack()
        cg = L.codegen(st, LIB, TU, TC, MODS, PAL)
        self._ok(STUB_COMPUTE + cg['update_inplace'], 'comp', 'update all inplace (pxStateT via TDImageLoadOutput)')


def _code_only(src):
    """Source without comments and docstrings (ast round trip); string constants used as code stay."""
    tree = ast.parse(src)
    for n in ast.walk(tree):
        body = getattr(n, 'body', None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                and isinstance(body[0].value.value, str):
            body[0] = ast.Pass()
    return ast.unparse(tree)


class Builder(unittest.TestCase):
    FILES = ['px.py', 'px_rt.py', 'px_logic.py']

    def test_ascii(self):
        for f in self.FILES:
            _read(os.path.join(BUILDERS, f), encoding='ascii')
        for f in os.listdir(GLSL):
            if f.startswith('px_'):
                _read(os.path.join(GLSL, f), encoding='ascii')
        _read(os.path.join(BUILDERS, 'splat_render.glsl'), encoding='ascii')

    def test_every_px_shader_is_used(self):
        src = _read(os.path.join(BUILDERS, 'px.py'))
        for f in os.listdir(GLSL):
            # wave 2: px_glow.glsl stays as bloom v2's legacy reference (test_px_haze G-a); px_haze_comp is folded
            # into px_post; px_lines_* are read by builders/px_lines.py (built inside PX)
            if f.startswith('px_lines_') or f in ('px_glow.glsl', 'px_haze_comp.glsl'):
                continue
            if f.startswith('px_') and f not in ('px_common.glsl', 'px_modules.glsl', 'px_update.glsl',
                                                 'px_colour.glsl', 'px_source.glsl', 'px_vert.glsl', 'px_pixel.glsl'):
                self.assertIn("'%s'" % f, src, f)
        self.assertIn('SPLAT_GLSL', src)                                        # the BL shader is read, not copied
        # no copy of BL's shader in glsl/ (other COMPs' own splat shaders, e.g. gen_interactive_*, are not copies)
        self.assertFalse(any(f.startswith('splat_render') for f in os.listdir(GLSL)))

    def test_engine_keys_exist(self):
        src = _read(os.path.join(BUILDERS, 'px.py'))
        keys = re.findall(r"\('eng_\w+', '(\w+)', ", src)
        rt = _read(os.path.join(BUILDERS, 'px_rt.py'))
        body = rt.split('    rows = {')[1].split('}\n')[0]
        for k in keys:
            self.assertIn("'%s':" % k, body, k)

    def test_hooks_are_noops_for_bl(self):
        # every hook in splat_render.glsl has an empty default (BL_splat_render compiles to the same code)
        for h in ('SPLAT_VERTEX_EXTRA', 'SPLAT_HOOK_T', 'SPLAT_HOOK_COV', 'SPLAT_HOOK_OUT', 'SPLAT_HOOK_PIX'):
            self.assertIn('#ifndef %s\n#define %s' % (h, h), SPLAT_GLSL)
            self.assertIn('#define %s' % h, rd('px_splat_adapter.glsl'))

    def test_crash_rules(self):
        for f in ('px.py', 'px_rt.py'):
            code = _code_only(_read(os.path.join(BUILDERS, f)))
            self.assertNotIn('numpyArray', code, f)                              # T-74
            self.assertNotIn('evalTextSize', code, f)                            # T-76
            self.assertNotIn('cookRate', code, f)                                # T-64
            for m in re.finditer(r'(\w+)\.destroy\(', code):                     # T-70: only via safe_destroy
                self.assertIn(m.group(1), ('pg', 'mpar', 'nomcp'), f)           # (custom pages / pars, not ops;
                # nomcp = the drop-in fallback when the project has no /jazib_mcp, 28 Oct)
            for m in re.finditer(r'(\w+)\.store\(([^,]+),', code):                 # T-67: own plain-data keys only
                if m.group(1) == 'rt':                                          # px_rt.store(c, name) = save a preset
                    continue
                self.assertTrue(m.group(2).strip().startswith("'px_"), (f, m.group(0)))

    def test_stage_ops_are_created(self):
        src = _read(os.path.join(BUILDERS, 'px.py'))
        tree = ast.parse(src)
        stages = next(n.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == 'STAGES')
        names = [e.value for d in stages.elts for k, v in zip(d.keys, d.values) if k.value == 'ops' for e in v.elts]
        made_by_zkit = {'controls', 'controls_window'}
        for n in names:
            if n in made_by_zkit:
                continue
            self.assertIn("'%s'" % n, src.split('STAGES = [')[0] + src.split("def build(")[1], n)

    def test_compute_tops_max_three_inputs(self):
        src = _read(os.path.join(BUILDERS, 'px.py'))
        for k in re.findall(r'_wire\([^,]+, \w+, (\d)\)', src):
            self.assertLessEqual(int(k), 2)                                      # T-84/T-88

    def test_runtime_parses(self):
        for f in self.FILES:
            ast.parse(_read(os.path.join(BUILDERS, f)))


class CameraMaths(unittest.TestCase):
    def test_cam_viewproj_centre_and_edge(self):
        # camera on +z at distance 4 looking at the origin: origin -> NDC centre; a point at the horizontal FOV edge
        # (x = z_dist * tan(hfov/2)) -> NDC x = 1. Orbit 90 deg: camera on +x, ry 90, origin still centred.
        vp = L.cam_viewproj([0.0, 0.0, 4.0, 0.0], 45.0, 1080, 1920)
        ndc = lambda m, p: [sum(m[r][k] * (list(p) + [1.0])[k] for k in range(4)) for r in range(4)]
        c = ndc(vp, (0.0, 0.0, 0.0))
        self.assertAlmostEqual(c[0] / c[3], 0.0, places=9)
        self.assertAlmostEqual(c[1] / c[3], 0.0, places=9)
        e = ndc(vp, (4.0 * math.tan(math.radians(22.5)), 0.0, 0.0))
        self.assertAlmostEqual(e[0] / e[3], 1.0, places=9)
        vp2 = L.cam_viewproj([4.0, 0.0, 0.0, 90.0], 45.0, 1080, 1920)
        c2 = ndc(vp2, (0.0, 0.0, 0.0))
        self.assertAlmostEqual(c2[0] / c2[3], 0.0, places=9)
        self.assertGreater(c2[3], 0.0)

    def test_place_bounds_follows_source_transform(self):
        # px_source.glsl: p * scale, rotate about y by rot, + offset
        c, r = L.place_bounds(((1.0, 2.0, 0.0), 3.0), 2.0, 90.0, (0.5, 0.0, -1.0))
        self.assertAlmostEqual(r, 6.0)
        x, y, z = 2.0, 4.0, 0.0
        a = math.radians(90.0)
        want = (math.cos(a) * x + math.sin(a) * z + 0.5, y, -math.sin(a) * x + math.cos(a) * z - 1.0)
        for u, v in zip(c, want):
            self.assertAlmostEqual(u, v, places=9)


if __name__ == '__main__':
    unittest.main()
