"""Offline tests for the shared effector list (builders/effectors_logic.py, effectors.py, effectors_rt.py, the packed
section of glsl/px_common.glsl, glsl/eff_consumer.glsl, glsl/eff_field2d.glsl) and the consumer hooks. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_effectors.py'
GLSL checks compile with glslc (OpenGL target) against TD stubs: a syntax / type check, NOT a TD compile (LIVE CHECKS
in docs/builds/effectors.md)."""
import ast
import math
import os
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
import effectors_logic as L  # noqa: E402
import px_logic as PXL  # noqa: E402
import reaction_diffusion_logic as RDL  # noqa: E402
import physarum_logic as PHL  # noqa: E402


def rd(path):
    with open(path) as fh:
        return fh.read()


def world(t=(0.0, 0.0, 0.0), s=1.0, ry=0.0):
    c, n = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    return [[c * s, 0.0, n * s, t[0]], [0.0, s, 0.0, t[1]], [-n * s, 0.0, c * s, t[2]]]


def rows_of(*specs):
    rs = []
    for kind, name, kw in specs:
        rs, _ = L.add_row(rs, kind, name, **kw)
    return rs


class List(unittest.TestCase):
    def test_add_names_unique(self):
        rs, a = L.add_row([], 'sphere')
        rs, b = L.add_row(rs, 'sphere')
        rs, c = L.add_row(rs, 'box', 'sphere1')      # taken -> next free with that base
        rs, d = L.add_row(rs, 'null', '9 lives!')
        self.assertEqual((a, b, c, d), ('sphere1', 'sphere2', 'sphere3', 'e9_lives_'))
        with self.assertRaises(ValueError):
            L.add_row(rs, 'teapot')

    def test_every_requested_kind(self):
        for k in ('box', 'sphere', 'plane', 'capsule', 'null', 'pts', 'path', 'camera', 'actor'):
            self.assertIn(k, L.names(L.KINDS))

    def test_remove_duplicate_rename_enable(self):
        rs = rows_of(('sphere', 'a', {'tags': 'hands', 'gain': 2}), ('box', 'b', {}))
        rs, d = L.duplicate_row(rs, 'a')
        self.assertEqual([r['name'] for r in rs], ['a', 'a1', 'b'])
        self.assertEqual(rs[1]['tags'], 'hands')
        self.assertEqual(rs[1]['gain'], '2')
        rs, n = L.rename_row(rs, 'a1', 'left')
        self.assertEqual(n, 'left')
        with self.assertRaises(ValueError):
            L.rename_row(rs, 'left', 'b')
        rs = L.set_value(rs, 'left', 'enabled', '0')
        self.assertEqual([r['enabled'] for r in rs], ['1', '0', '1'])
        rs = L.remove_row(rs, 'a')
        self.assertEqual([r['name'] for r in rs], ['left', 'b'])

    def test_table_roundtrip(self):
        rs = rows_of(('pts', 'face', {'ref': '/project1/lab/FT_face_track/out_pts', 'mode': 'density'}))
        cells = L.table_cells(rs)
        self.assertEqual(cells[0], L.COLS)
        self.assertEqual(L.parse_table(cells), rs)
        self.assertEqual(L.parse_table([['name', 'kind'], ['x', 'box'], ['', 'box']])[0]['radius'], '0.5')


class Selection(unittest.TestCase):
    def setUp(self):
        self.rs = rows_of(('sphere', 's', {'tags': 'hands demo'}), ('box', 'b', {'tags': 'demo'}),
                          ('null', 'n', {}), ('plane', 'hands', {}))

    def test_tokens(self):
        tags = L.tag_list(self.rs)
        self.assertEqual(tags, ['demo', 'hands'])
        v, u = L.sel_vec('', self.rs)
        self.assertEqual(v[1], 1.0)
        v, u = L.sel_vec('all', self.rs)
        self.assertEqual(v[1], 1.0)
        v, u = L.sel_vec('#hands n', self.rs)
        self.assertEqual((v[0], v[1], v[2]), (2.0, 0.0, 3.0))
        v, u = L.sel_vec('hands', self.rs)                  # a name wins over the tag of the same word
        self.assertEqual((v[0], v[2]), (0.0, 4.0))
        v, u = L.sel_vec('demo nope', self.rs)
        self.assertEqual((v[0], u), (1.0, ['nope']))
        v, u = L.sel_vec('s b n hands s', self.rs)          # a repeated name counts once (the shader visits ids)
        self.assertEqual((v[2:], u), ([1.0, 2.0, 3.0, 4.0], []))
        rs5 = self.rs + rows_of(('null', 'e', {}))
        v, u = L.sel_vec('s b n hands e', rs5)              # 5 names: the 5th is reported (use a tag)
        self.assertEqual((v[2:], u), ([1.0, 2.0, 3.0, 4.0], ['e']))

    def test_selected_matches(self):
        rs = L.set_value(self.rs, 'b', 'enabled', '0')
        self.assertEqual(L.selected(rs, 'all'), [0, 2, 3])
        self.assertEqual(L.selected(rs, '#demo'), [0])
        self.assertEqual(L.selected(rs, 'all', kinds=L.POINT_KINDS), [2])

    def test_tag_limit(self):
        rs = rows_of(*[('null', 'n%d' % k, {'tags': 't%02d' % k}) for k in range(30)])
        self.assertEqual(len(L.tag_list(rs)), L.MAX_TAGS)
        self.assertEqual(L.tags_over(rs), 30 - L.MAX_TAGS)
        self.assertLess(L.OWN_BIT | (2 ** L.MAX_TAGS - 1), 2 ** 24)   # mask + own bit stay exact in float32


class Packing(unittest.TestCase):
    def test_layout_and_px_contract(self):
        rs = rows_of(('sphere', 's', {'tags': 'demo', 'radius': 0.7, 'exponent': 2, 'gain': 1.5, 'falloff': 'gaussian'}),
                     ('box', 'b', {'enabled': 0}), ('null', 'n', {}))
        ws = [world((1.0, 2.0, 3.0), 2.0, 30.0), world((0.5, 0.0, 0.0), 1.0), world((0.0, -1.0, 0.0))]
        effs = [L.effector(r, w, (0.1, 0.0, 0.0)) for r, w in zip(rs, ws)]
        tex = L.pack_buffer(effs)
        self.assertEqual(tex[0], [3.0, float(L.W), float(1 + 3 * L.W + 1), float(L.VERSION)])
        self.assertEqual(len(tex), 1 + 3 * L.W + 1)                 # + the (empty) light region header
        self.assertEqual(tex[1 + 3 * L.W], [0.0, float(L.LW), 0.0, 0.0])
        self.assertEqual(L.count_of(tex), 3)
        px = PXL.effector_rows([{'kind': r['kind'], 'world': w, 'speed': 0.1} for r, w in zip(rs, ws)])
        for i in range(3):
            row = L.read_row(tex, i)
            for t in range(6):                              # texels 0..5 = PX's uE rows exactly (PX v2 contract)
                for a, b in zip(row[t], px[i * PXL.E_PER + t]):
                    self.assertAlmostEqual(a, b, places=9)
        r0, r1 = L.read_row(tex, 0), L.read_row(tex, 1)
        self.assertEqual(r0[6], [0.1, 0.0, 0.0, 1.0])
        self.assertEqual(r1[6][3], 0.0)
        self.assertEqual(r0[7], [2.0, 0.7, 2.0, 1.5])
        self.assertEqual(r0[8][:2], [float(1 | L.OWN_BIT), float(L.menu_index(L.KINDS, 'sphere'))])
        self.assertEqual(r0[9][3], 1.0)
        self.assertEqual(L.read_row(tex, 2)[9][3], 3.0)

    def test_point_sets(self):
        rs = rows_of(('sphere', 's', {}), ('pts', 'p', {'mode': 'density'}), ('actor', 'a', {}))
        pts = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 3.0, 0.0)]
        effs = [L.effector(rs[0]), L.effector(rs[1], points=pts, point_vel=[(1.0, 0.0, 0.0)] * 3),
                L.effector(rs[2], points=pts[:1])]
        tex = L.pack_buffer(effs)
        start = 1 + 3 * L.W + 1                             # rows + light header (no lights)
        self.assertEqual(tex[0][2], float(start))
        r1, r2 = L.read_row(tex, 1), L.read_row(tex, 2)
        self.assertEqual(r1[3][0], float(L.SD_PTS))
        self.assertEqual(r1[8][2:], [float(start), 3.0])
        self.assertEqual(r2[8][2:], [float(start + 6), 1.0])
        self.assertEqual(r1[4][:3], [1.0, 1.0, 0.0])        # centre = centroid
        self.assertEqual(r1[9][1], 1.0)                     # density mode
        self.assertEqual(tex[start + 2], [2.0, 0.0, 0.0, 1.0])
        self.assertEqual(tex[start + 3], [1.0, 0.0, 0.0, 1.0])
        self.assertEqual(len(tex), start + 8)
        self.assertEqual(L.read_row(tex, 0)[8][3], 0.0)     # an object has no points

    def test_pack_cache_same_output(self):
        """The runtime's per-row cache (live perf fix) never changes the buffer: edits, moves, retags, removals."""
        rs = rows_of(('sphere', 's', {'tags': 'a'}), ('box', 'b', {}), ('pts', 'p', {}), ('null', 'n', {'tags': 'b'}))
        ws = [world((1.0, 0.0, 0.0)), world((0.0, 1.0, 0.0), 2.0), world((0.0, 0.0, 0.0)), world((0.0, 0.0, 2.0))]
        cache = {}
        steps = [lambda r, w: (r, w), lambda r, w: (r, [world((3.0, 0.0, 0.0))] + w[1:]),
                 lambda r, w: ([dict(r[0], tags='c')] + r[1:], w), lambda r, w: (r[1:], w[1:]),
                 lambda r, w: ([dict(r[0], enabled='0')] + r[1:], w)]
        cache2 = {}
        for k, f in enumerate(steps):
            rs, ws = f(rs, ws)
            effs = [L.effector(r, w, points=[(0.0, 0.0, 0.0)] if r['kind'] == 'pts' else None) for r, w in zip(rs, ws)]
            ref = L.pack_buffer(effs)
            self.assertEqual(L.pack_buffer(effs, cache=cache), ref)
            lk = (k if k != 1 else 0, len(rs))              # step 1 only moves an object: same list version
            self.assertEqual(L.pack_buffer(effs, cache=cache2, list_key=lk, as_array=True).tolist(), ref)
        self.assertLessEqual(len(cache), len(rs))

    def test_no_cap(self):
        rs = rows_of(*[('null', 'n%d' % k, {}) for k in range(200)])
        tex = L.pack_buffer([L.effector(r, world((k * 0.01, 0.0, 0.0))) for k, r in enumerate(rs)])
        self.assertEqual(L.count_of(tex), 200)
        self.assertEqual(L.read_row(tex, 199)[4][0], 1.99)
        self.assertEqual(L.buffer_chans(tex)[0][0], 200.0)
        self.assertEqual(L.count_of([[0.0, 10.0, 1.0, 1.0]]), 0)

    def test_weight_matches_px_reference(self):
        rs = rows_of(('sphere', 's', {'radius': 1.0}), ('box', 'b', {'radius': 1.0}))
        ws = [world((0.0, 0.0, 0.0), 1.0), world((3.0, 0.0, 0.0), 2.0, 45.0)]
        tex = L.pack_buffer([L.effector(r, w) for r, w in zip(rs, ws)])
        erows = PXL.effector_rows([{'kind': r['kind'], 'world': w} for r, w in zip(rs, ws)])
        sel, _ = L.sel_vec('all', rs)
        for p in ((0.75, 0.0, 0.0), (1.0, 0.2, 0.0), (2.2, 0.5, 0.3), (5.0, 0.0, 0.0)):
            w, b = L.ref_weight(tex, p, sel)
            ref = float(PXL.ref_prox_w([p], erows, 3, 2, 1.0, 1.0, 0, 0)[0])
            self.assertAlmostEqual(w, ref, places=9)
        w, b = L.ref_weight(tex, (0.75, 0.0, 0.0), L.sel_vec('b', rs)[0])
        self.assertEqual(b, 1)
        self.assertEqual(L.ref_weight(tex, (0.0, 0.0, 0.0), [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])[1], -1)

    def test_known_point_set_weight(self):
        rs = rows_of(('pts', 'p', {'radius': 1.0, 'falloff': 'linear'}))
        tex = L.pack_buffer([L.effector(rs[0], points=[(0.0, 0.0, 0.0), (4.0, 0.0, 0.0)])])
        w, b = L.ref_weight(tex, (1.5, 0.0, 0.0), L.sel_vec('all', rs)[0])
        self.assertAlmostEqual(w, 0.0)
        w, b = L.ref_weight(tex, (3.5, 0.0, 0.0), L.sel_vec('all', rs)[0])
        self.assertAlmostEqual(w, 0.5)


class Consumers(unittest.TestCase):
    def test_colliders(self):
        rs = rows_of(('sphere', 's', {}), ('box', 'b', {}), ('plane', 'pl', {}), ('null', 'n', {'radius': 0.3}),
                     ('pts', 'p', {'radius': 0.05}), ('sphere', 'off', {'enabled': 0}))
        effs = [L.effector(rs[0], world((1.0, 0.0, 0.0), 2.0)), L.effector(rs[1], world((0.0, 1.0, 0.0))),
                L.effector(rs[2]), L.effector(rs[3], world((0.0, 0.0, 2.0))),
                L.effector(rs[4], points=[(5.0, 5.0, 5.0), (6.0, 5.0, 5.0)]), L.effector(rs[5])]
        tex = L.pack_buffer(effs)
        cols = L.colliders(tex, L.sel_vec('all', rs)[0], pad=0.01)
        self.assertEqual(len(cols), 5)                      # plane skipped, disabled skipped, 2 points
        self.assertEqual(cols[0], (1.0, 0.0, 0.0, 1.01))
        self.assertAlmostEqual(cols[1][3], math.sqrt(0.75) + 0.01)
        self.assertAlmostEqual(cols[2][3], 0.31)
        self.assertEqual(cols[3], (5.0, 5.0, 5.0, 0.060000000000000005))
        self.assertEqual(len(L.colliders(tex, L.sel_vec('n', rs)[0])), 1)

    def test_info_2d_and_gain(self):
        r = rows_of(('sphere', 's', {'radius': 0.2, 'falloff': 'shell', 'gain': 0.5}))[0]
        i = L.info_2d(r)
        self.assertEqual(i, {'radius': 0.7, 'falloff': 3, 'active': True, 'gain': 0.5})
        for mod in (RDL, PHL):
            p = dict(getattr(mod, 'ENGINE_DEFAULTS'))
            p.update({'planeh': 2.0, 'aspect': 1.0})
            base = mod.effector_row({'tx': 0.0, 'ty': 0.0, 'sx': 1.0, 'sy': 1.0}, p)
            e = {'tx': 0.0, 'ty': 0.0, 'sx': 1.0, 'sy': 1.0}
            e.update(i)
            got = mod.effector_row(e, p)
            self.assertAlmostEqual(got[3], base[3] * 0.5)   # strength x gain
            self.assertAlmostEqual(got[2], 0.7 / 2.0)       # radius / plane height
            self.assertEqual(got[5], 3.0)

    def test_paths(self):
        for sh in [n for n in L.names(L.PATHS) if n != 'noise']:      # noise wanders (not periodic)
            a = L.path_point(sh, 0.3, (1.0, 0.5, 2.0), (1.0, 1.0, 1.0), (0.2, 0.3, 0.4))
            b = L.path_point(sh, 1.3, (1.0, 0.5, 2.0), (1.0, 1.0, 1.0), (0.2, 0.3, 0.4))
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y, places=9)      # one cycle per unit phase
        self.assertEqual(L.path_point('line', 0.0), (-1.0, -1.0, -1.0))
        self.assertEqual(L.path_point('line', 0.5), (1.0, 1.0, 1.0))
        p = L.path_point('circle', 0.125, (2.0, 1.0, 2.0))
        self.assertAlmostEqual(math.hypot(p[0], p[2]), 2.0)

    def test_prefix_idempotent(self):
        pre = L.consumer_prefix('// lib\n', '// helpers\n', ('PXE_PARTICLES',))
        src = '#define STATE_INPLACE 1\n// shader\nvoid main() {}\n'
        a = L.with_prefix(src, pre)
        self.assertTrue(a.startswith('#define STATE_INPLACE 1\n' + L.MARK_A))
        self.assertEqual(L.with_prefix(a, pre), a)
        self.assertEqual(L.strip_prefix(a), src)
        self.assertIn('#define PXE_PARTICLES 1', a)
        self.assertEqual(L.with_prefix('void main() {}', pre).count(L.MARK_A), 1)

    def test_expressions_guarded(self):
        for _, ex in L.consumer_vecs():
            self.assertEqual(len(ex), 4)
        self.assertIn('is not None', L.sel_expr(0))

    def test_expressions_read_selection_without_list(self):
        """T-159: with /project1/effectors missing, every guarded expression still reads Effselect (TD's dependency),
        and with it present it gives the selected value."""
        import types
        reads = []

        class Par:
            def eval(self):
                reads.append(1)
                return 'all'
        P = types.SimpleNamespace(par=types.SimpleNamespace(Effselect=Par()),
                                  op=lambda n: types.SimpleNamespace(path='/x/' + n))
        rt = types.SimpleNamespace(module=types.SimpleNamespace(sel_vec=lambda s: [7, 1, 2, 3, 4, 5],
                                                                rows_for=lambda s: '/project1/effectors/eff_rows'))
        ns = {}
        exec(compile(rd(os.path.join(BUILDERS, 'effectors.py')), 'effectors.py', 'exec'), ns)
        for have in (False, True):
            env = {'parent': lambda: P, 'me': types.SimpleNamespace(parent=lambda: P),
                   'op': lambda p: (rt if have else None)}
            for k in range(6):
                del reads[:]
                self.assertEqual(eval(L.sel_expr(k), env), [7, 1, 2, 3, 4, 5][k] if have else 0)
                self.assertEqual(len(reads), 1)
            del reads[:]
            self.assertEqual(eval(ns['EFF_IN_EXPR'], env), ns['ROWS_PATH'] if have else '/x/eff_none')
            self.assertEqual(len(reads), 1)

    def test_refresh_consumers(self):
        """T-159: build() re-sets the effector expressions of consumers built before the list existed (TD does not
        re-evaluate a guard when the op it looked for is created); other expressions are left alone."""
        import types
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

        eff = Par(L.sel_expr(2))
        other = Par("parent().par.Size.eval()")
        const = Par(L.sel_expr(3), 'c')

        class O:
            def __init__(self, pars, kids=()):
                self._p, self._k = pars, list(kids)

            def pars(self):
                return self._p

            def findChildren(self, **kw):
                return self._k
        glsl = O([eff, other, const])
        comp = O([], [glsl])
        sel = O([])
        sel.parent = lambda: comp
        comp_root = types.SimpleNamespace(findChildren=lambda **kw: [sel] if kw.get('name') == 'eff_in' else [])
        ns = {'ParMode': mode, 'selectCHOP': type('selectCHOP', (), {}),
              'op': lambda p: comp_root}
        exec(compile(rd(os.path.join(BUILDERS, 'effectors.py')), 'effectors.py', 'exec'), ns)
        self.assertEqual(ns['refresh_consumers'](), 1)
        self.assertEqual(eff.sets, ['0', L.sel_expr(2)])
        self.assertEqual(eff.expr, L.sel_expr(2))
        self.assertEqual((other.sets, const.sets), ([], []))
        self.assertIn('refreshed = refresh_consumers()', rd(os.path.join(BUILDERS, 'effectors.py')))


class Builder(unittest.TestCase):
    def setUp(self):
        self.src = rd(os.path.join(BUILDERS, 'effectors.py'))
        self.rt = rd(os.path.join(BUILDERS, 'effectors_rt.py'))

    def test_api(self):
        fns = set(n.name for n in ast.parse(self.src).body if isinstance(n, ast.FunctionDef))
        for f in ('build', 'add', 'remove', 'duplicate', 'rename', 'enable', 'attach', 'attach_all'):
            self.assertIn(f, fns)
        fr = set(n.name for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef))
        for f in ('cook_rows', 'sel_vec', 'select_ops', 'info_2d', 'path_xyz', 'add', 'remove', 'duplicate', 'rename',
                  'enable', 'on_pulse', 'sync_objects'):
            self.assertIn(f, fr)

    def test_callback_texts_parse(self):
        ns = {}
        exec(compile(self.src, 'effectors.py', 'exec'), ns)
        for k in ('ROWS_CB', 'PULSES', 'COLLIDERS_CB'):
            ast.parse(ns[k])
        self.assertEqual(set(ns['ADAPTERS']) | set(ns['NATIVE']),
                         {'BO_particles', 'BN_fluid2d', 'BN_cloth', 'BL_splat_render', 'BL_cloud_morph', 'FX_destroy',
                          'GN_reaction_diffusion', 'GN_physarum', 'MX_prox_material', 'GEN_clone'})

    def test_safety_rules(self):
        for s in (self.src, self.rt):
            self.assertNotIn('.destroy()', s.replace('nomcp.destroy()', ''))   # only safe_destroy (T-70); nomcp =
            # the drop-in fallback when the project has no /jazib_mcp (28 Oct)
            # no TOP readback (T-74): the only numpyArray calls are CHOP reads (points_of's CHOP branch; eff_in, a
            # Select CHOP, in the cloth colliders callback)
            # + the env object's env_px (a TOP to CHOP on nextframe: the TD op downloads, Python reads a CHOP)
            ok = ("pts = _chop_points([c.name for c in src.chans()], src.numpyArray())",
                  "tex = E.numpyArray()[:4].T.tolist()",
                  "ev['pixels'] = Lg.env_pixels_from_chop([c.name for c in ch.chans()], ch.numpyArray())")
            calls = [ln.strip() for ln in s.split('\n') if 'numpyArray(' in ln and not ln.strip().startswith('#')]
            self.assertTrue(all(c.split('  #')[0].strip() in ok for c in calls), calls)
            if ok[0] in s:
                self.assertIn("if src.family == 'CHOP' and src.numChans:\n        " + ok[0], s)
            if ok[2] in s:
                self.assertIn("if ch is not None and ch.family == 'CHOP' and ch.numChans:\n        " + ok[2], s)
            self.assertNotIn('cookRate =', s)
            s.encode('ascii')
        self.assertNotIn("hasattr(o, 'worldTransform')", self.rt)   # T-115

    def test_hooks_in_builders(self):
        for f in ('particles', 'fluid2d', 'cloth', 'splat_render', 'pointcloud'):
            s = rd(os.path.join(BUILDERS, f + '.py'))
            self.assertIn('def _eff_hook(c)', s)
            self.assertIn('eff = _eff_hook(c)', s)
        for f in ('reaction_diffusion', 'physarum'):
            s = rd(os.path.join(BUILDERS, f + '.py'))
            self.assertIn("tok.startswith('@')", s)
            self.assertIn('info_2d(o)', s)
            tree = ast.parse(s)
            cb = [n for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'ENGINE_CB']
            ast.parse(cb[0].value.value)


# --------------------------------------------------------------------------------------------- GLSL (glslc)
STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""
STUB_MAT = """#version 460
struct TDMatrix { mat4 world; mat4 cam; mat4 camInverse; mat4 proj; };
uniform TDMatrix uTDMats[1];
int TDCameraIndex() { return 0; }
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""
STUB_VERT = STUB_MAT + """in vec3 P;
int TDInstanceID() { return gl_InstanceID; }
vec3 TDPos() { return P; }
float TDSimplexNoise(vec4 v) { return fract(sin(dot(v, vec4(1.0, 2.0, 3.0, 4.0)))); }
""" + ''.join('vec4 TDInstanceCustomAttrib%d(int i) { return vec4(float(i)); }\n' % k for k in range(7))


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

    def test_particles_state(self):
        code = rd(os.path.join(GLSL, 'particles_state.glsl'))
        self._ok(STUB_COMPUTE + L.with_prefix(code, self.pre('PXE_PARTICLES')), 'comp', 'particles state')
        self._ok(STUB_COMPUTE + L.with_prefix('#define STATE_INPLACE 1\n' + code, self.pre('PXE_PARTICLES')), 'comp',
                 'particles in place')
        self._ok(STUB_COMPUTE + code, 'comp', 'particles without the adapter')

    def test_splats(self):
        code = rd(os.path.join(BUILDERS, 'splat_render.glsl'))
        t = L.with_prefix(code, self.pre('PXE_POINTS'))
        self._ok(STUB_VERT.replace('#version 460\n', '#version 460\n#define TD_VERTEX_SHADER 1\n') + t, 'vert',
                 'splat vertex')
        self._ok(STUB_MAT.replace('#version 460\n', '#version 460\n#define TD_PIXEL_SHADER 1\n') + t, 'frag',
                 'splat pixel')

    def test_cloud(self):
        code = rd(os.path.join(GLSL, 'pointcloud_vertex.glsl'))
        self._ok(STUB_VERT + L.with_prefix(code, self.pre('PXE_POINTS')), 'vert', 'cloud vertex')

    def test_field2d(self):
        code = rd(os.path.join(GLSL, 'eff_field2d.glsl'))
        stub1 = STUB_COMPUTE.replace('#version 460\n', '#version 460\n#define TD_NUM_2D_INPUTS 1\n')
        self._ok(stub1 + self.pre() + code, 'comp', 'eff_field2d (input wired)')
        # FX_destroy's eff_mask has no input: TD then declares no sTD2DInputs (live 31550 compile error before the guard)
        stub0 = STUB_COMPUTE.replace('uniform sampler2D sTD2DInputs[3];\n', '#define TD_NUM_2D_INPUTS 0\n')
        self._ok(stub0 + self.pre() + code, 'comp', 'eff_field2d (no input)')

    def test_px_v1_unchanged_path(self):
        """px_common without PX_PACKED_ONLY still declares the legacy functions (PX v1 / MX objects)."""
        lib = rd(os.path.join(GLSL, 'px_common.glsl'))
        hdr = '#version 460\nuniform vec4 uG[24];\nuniform vec4 uE[88];\n#define PX_NO_TEX_INPUTS\n'
        self._ok(hdr + lib + '\nlayout(local_size_x = 1) in;\nvoid main() { int b; float w = pxW(vec3(0.0), 1, 1.0, 1.0,'
                 ' 0, 0, 0.0, 1.0, b); }\n', 'comp', 'px legacy')


if __name__ == '__main__':
    unittest.main()
