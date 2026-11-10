"""Offline tests, drop-in round 29 Oct 2026 (lane A): published (#pub) rows in the shared effector list, the PX hot
row that follows the grid modules, the PX sorter prime, BL_splat_render's optional Splatfx. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_effectors_pub.py'
Live proofs (b2 / scratch, TD 2025.31550): docs/builds/effectors.md "Published rows (29 Oct)"."""
import ast
import os
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
sys.path.insert(0, BUILDERS)
import effectors_logic as L  # noqa: E402
import px_logic as PXL  # noqa: E402


def rd(path):
    with open(path) as fh:
        return fh.read()


def rows_of(*specs):
    rs = []
    for kind, name, kw in specs:
        rs, _ = L.add_row(rs, kind, name, **kw)
    return rs


def own_and_pub():
    return rows_of(('sphere', 's', {'tags': 'demo'}), ('null', 'n', {}),
                   ('cloud', 'px_hot_a', {'tags': 'pxhot pub', 'ref': '/project1/lab/PX_a/hot_pts'}),
                   ('pts', 'track', {'tags': 'track pub', 'ref': '/project1/lab/FX_track/out_pts'}))


class Selection(unittest.TestCase):
    def test_all_is_own_only(self):
        rs = own_and_pub()
        self.assertTrue(L.is_pub(rs[2]) and L.is_pub(rs[3]) and not L.is_pub(rs[0]))
        for txt in ('', 'all', '*'):
            v, _ = L.sel_vec(txt, rs)
            self.assertEqual((int(v[0]), v[1]), (L.OWN_BIT, 0.0))
            self.assertEqual(L.selected(rs, txt), [0, 1])
        self.assertEqual(L.selected(rs, 'all #track'), [0, 1, 3])
        self.assertEqual(L.selected(rs, 'track'), [3])                 # by name
        self.assertEqual(L.selected(rs, '#pub'), [2, 3])
        self.assertEqual(L.selected(rs, 'pxhot'), [2])                 # bare tag word

    def test_no_pub_rows_unchanged(self):
        rs = rows_of(('sphere', 's', {'tags': 'demo'}), ('null', 'n', {}))
        self.assertEqual(L.sel_vec('all', rs)[0][:2], [0.0, 1.0])     # the old 'all' flag: identical uniforms
        self.assertEqual(L.sel_vec('', rs)[0][:2], [0.0, 1.0])

    def test_wants_pub(self):
        rs = own_and_pub()
        for txt, want in (('all', False), ('', False), ('s #demo', False), ('track', True), ('#track', True),
                          ('all pxhot', True), ('#pub', True), ('nope', False)):
            self.assertEqual(L.wants_pub(txt, rs), want, txt)

    def test_bits_exact_in_float32(self):
        self.assertEqual(L.OWN_BIT, 1 << L.MAX_TAGS)
        self.assertLess(L.OWN_BIT | (L.OWN_BIT - 1), 2 ** 24)
        rs = own_and_pub()
        tags = L.tag_list(rs)
        self.assertTrue(L.tag_bits(rs[0], tags) & L.OWN_BIT)
        self.assertFalse(L.tag_bits(rs[2], tags) & L.OWN_BIT)


class Packing(unittest.TestCase):
    def test_placeholder_is_inert(self):
        rs = own_and_pub()
        effs = [L.effector(L.placeholder(r)) if L.is_pub(r) else L.effector(r) for r in rs]
        tex = L.pack_buffer(effs)
        sel_all = L.sel_vec('all', rs)[0]
        sel_trk = L.sel_vec('track', rs)[0]
        r3 = L.read_row(tex, 3)
        self.assertEqual(r3[6][3], 0.0)                               # enabled 0 in eff_rows
        self.assertEqual(r3[8][3], 0.0)                               # no points packed
        self.assertEqual(L.ref_weight(tex, (0.0, 0.0, 0.0), sel_trk)[0], 0.0)
        self.assertGreater(L.ref_weight(tex, (0.0, 0.0, 0.0), sel_all)[0], 0.0)   # own sphere still answers
        full = L.pack_buffer([L.effector(r, points=[(0.0, 0.0, 0.0)] if r['kind'] == 'pts' else None) for r in rs])
        self.assertEqual(L.read_row(full, 3)[6][3], 1.0)
        self.assertGreater(L.ref_weight(full, (0.0, 0.0, 0.0), sel_trk)[0], 0.0)
        self.assertEqual(int(tex[0][0]), int(full[0][0]))             # same rows, same ids in both buffers


class Runtime(unittest.TestCase):
    def setUp(self):
        self.rt = rd(os.path.join(BUILDERS, 'effectors_rt.py'))
        self.src = rd(os.path.join(BUILDERS, 'effectors.py'))

    def test_cook_rows_reads_nothing_of_inert_rows(self):
        fn = [n for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef) and n.name == 'cook_rows'][0]
        body = ast.get_source_segment(self.rt, fn)
        a = body.index("if not Lg._on(r['enabled']) or (not full and Lg.is_pub(r)):")
        self.assertLess(a, body.index('o = source_of(r)'))           # skip BEFORE any op is looked up
        self.assertIn('effs.append(Lg.effector(Lg.placeholder(r)))', body)
        self.assertIn("full = scriptOp.name == PUB_ROWS", body)
        self.rt.encode('ascii')
        self.src.encode('ascii')

    def test_eff_in_expr(self):
        ns = {}
        exec(compile(self.src, 'effectors.py', 'exec'), ns)
        reads = []

        class Par:
            def eval(self):
                reads.append(1)
                return 'all track'
        P = types.SimpleNamespace(par=types.SimpleNamespace(Effselect=Par()),
                                  op=lambda n: types.SimpleNamespace(path='/x/' + n))
        new = types.SimpleNamespace(module=types.SimpleNamespace(rows_for=lambda s: '/fx/eff_rows_pub' if 'track' in s
                                                                  else '/fx/eff_rows'))
        old = types.SimpleNamespace(module=types.SimpleNamespace(),
                                    parent=lambda: types.SimpleNamespace(op=lambda n: types.SimpleNamespace(
                                        path='/fx/' + n)))
        for rt, want in ((new, '/fx/eff_rows_pub'), (old, '/fx/eff_rows'), (None, '/x/eff_none')):
            env = {'me': types.SimpleNamespace(parent=lambda: P), 'op': lambda p, rt=rt: rt}
            del reads[:]
            self.assertEqual(eval(ns['EFF_IN_EXPR'], env), want)
            self.assertEqual(len(reads), 1)                           # T-159: Effselect read in every branch

    def test_pub_candidates(self):
        ns = {}
        exec(compile(self.src, 'effectors.py', 'exec'), ns)
        rs = rows_of(('cloud', 'px_hot_px_pointfx1', {'tags': 'pxhot'}), ('pts', 'track', {'tags': 'track',
                                                                                          'ref': '/p/FX_track/out_pts'}),
                     ('pts', 'mine', {'ref': '/project1/rig/hand_chop'}), ('cloud', 'scan', {'ref': '/p/MOD/out1'}),
                     ('sphere', 's', {}), ('cloud', 'done', {'tags': 'pub'}))
        res = lambda ref, kind: (True, ref.startswith('/p/MOD'))
        self.assertEqual(ns['pub_candidates'](rs, res), ['px_hot_px_pointfx1', 'track', 'scan'])
        self.assertEqual(ns['PUB_STEPS'][-1], 'done')
        self.assertIn("ch += [p_[len(PARENT) + 1:] for p_ in pub_consumer(PARENT)]", self.src)

    def test_grid_reads_full_buffer_relative(self):
        g = rd(os.path.join(BUILDERS, 'effectors_grid.py'))
        self.assertIn("full = C().op('eff_rows_pub') or C().op('eff_rows')", g)
        self.assertIn("p.val = '../' + full.name", g)


class PX(unittest.TestCase):
    def setUp(self):
        self.rt = rd(os.path.join(BUILDERS, 'px_rt.py'))
        self.px = rd(os.path.join(BUILDERS, 'px.py'))

    def test_stack_cloud_all_skips_pub(self):
        st = [{'type': 'prox_push', 'uid': 1, 'enabled': True, 'values': {'effectors': 'all'}}]
        pub = rows_of(('cloud', 'scan', {'tags': 'pub'}))
        own = rows_of(('cloud', 'scan', {}))
        self.assertFalse(PXL.stack_cloud(st, [], pub))
        self.assertTrue(PXL.stack_cloud(st, [], own))
        st[0]['values']['effectors'] = 'scan'
        self.assertTrue(PXL.stack_cloud(st, [], pub))

    def test_hot_row_events_only(self):
        self.assertIn("HOT_TAGS = 'pxhot pub'", self.rt)
        self.assertIn("ert.add('cloud', hn, tags=HOT_TAGS, ref=ref)", self.rt)
        self.assertIn("ert.enable(hn, False)", self.rt)
        self.assertNotIn("ert.add('cloud', hn, tags='pxhot',", self.rt)
        frame = [n for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef) and n.name == 'frame'][0]
        self.assertNotIn('_hot_sync', ast.get_source_segment(self.rt, frame))    # never per frame
        tick = [n for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef) and n.name == 'tick'][0]
        t = ast.get_source_segment(self.rt, tick)
        self.assertLess(t.index("if not s.get('inst_checked'):"), t.index('_hot_sync(c, hot_want(c))'))
        sc = [n for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef) and n.name == 'stack_changed'][0]
        s = ast.get_source_segment(self.rt, sc)
        a = s.index("if cg['hash'] == c.fetch('px_hash', '', search=False):")
        self.assertLess(a, s.index('_grid_wire(c,'))                  # hot row follows on the unchanged-hash path too
        hs = [n for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef) and n.name == '_hot_sync'][0]
        h = ast.get_source_segment(self.rt, hs)
        self.assertLess(h.index('if ert is None:'), h.index('hot_name(c)'))   # no shared list: nothing, no error

    def test_px_eff_in_expr(self):
        ns = {}
        exec(compile(self.px, 'px.py', 'exec'), ns)

        class U(dict):
            pass
        P = types.SimpleNamespace(op=lambda n: types.SimpleNamespace(path='/px/' + n))
        R = types.SimpleNamespace(path='/fx/eff_rows')
        Q = types.SimpleNamespace(path='/fx/eff_rows_pub')
        for use, have_q, want in ((1, True, '/fx/eff_rows'), (2, True, '/fx/eff_rows_pub'), (2, False, '/fx/eff_rows'),
                                  (0, True, '/px/eff_none')):
            u = {'use': [float(use)]}
            P2 = types.SimpleNamespace(op=lambda n, u=u: u if n == 'eff_use' else types.SimpleNamespace(
                path='/px/' + n))
            env = {'me': types.SimpleNamespace(parent=lambda P2=P2: P2),
                   'op': lambda p, have_q=have_q: (R if p.endswith('eff_rows') else (Q if have_q else None))}
            self.assertEqual(eval(ns['EFF_IN_EXPR'], env), want, (use, have_q))
        self.assertIn("e.par.chops.expr == EFF_IN_OLD", self.px)
        self.assertEqual(ns['UPGI_STEPS'], ('i_texts', 'i_exprs', 'i_hot', 'done'))

    def test_instance_two_loads_of_one_tox(self):
        self.assertIn("is_copy = is_copy or rec['key'] in keys", self.rt)

    def test_sort_prime_once(self):
        g = [n for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef) and n.name == '_sort_gate'][0]
        s = ast.get_source_segment(self.rt, g)
        self.assertIn("elif not s.get('sort_primed'):", s)
        self.assertIn("s['sort_primed'] = True", s)
        p = [n for n in ast.parse(self.rt).body if isinstance(n, ast.FunctionDef) and n.name == '_sort_prime'][0]
        ps = ast.get_source_segment(self.rt, p)
        self.assertNotIn('numPoints', ps)                             # no POP readback (T-74 / main guard)
        self.assertNotIn('.par.', ps)                                 # never reconfigures the sorter (T-124)


class Splat(unittest.TestCase):
    def test_splatfx_optional(self):
        s = rd(os.path.join(BUILDERS, 'splat_render.py'))
        self.assertIn("pg.appendCOMP('Splatfx', label=SPLATFX_LABEL)[0]", s)
        self.assertIn("p.default = ''", s)
        self.assertNotIn('/project1/lab/PX_pointfx', s)
        self.assertIn("def indep_upgrade(comp_path='/project1/lab/' + NAME):", s)


if __name__ == '__main__':
    unittest.main()
