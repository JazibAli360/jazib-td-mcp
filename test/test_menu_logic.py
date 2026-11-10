"""Offline tests: builders/menu_logic.py (live dropdowns, T-233) + the PX helpers (px_logic menu_source / sel_label /
sel_uid / menu specs) and the dropdown spec options of the other builders."""
import os
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')


def _load(name):
    ns = {'__name__': name}
    with open(os.path.join(B, name + '.py')) as f:
        exec(compile(f.read(), name + '.py', 'exec'), ns)
    return ns


ML = _load('menu_logic')


class FakePar(object):
    def __init__(self, page, name, style, val='', label=None):
        self.page, self.name, self.style, self.val, self.default = page, name, style, val, val
        self.label = label or name
        self.mode = types.SimpleNamespace(name='CONSTANT')
        self.expr = self.bindExpr = self.help = self.enableExpr = ''
        self.readOnly = self.startSection = False
        self.tupletName = name
        self.menuSource = ''
        self.destroyed = False

    def destroy(self):
        self.destroyed = True
        self.page.pars.remove(self)
        delattr(self.page.comp.par, self.name)


class FakePage(object):
    def __init__(self, comp):
        self.comp, self.pars = comp, []

    def add(self, name, style, val=''):
        p = FakePar(self, name, style, val)
        self.pars.append(p)
        setattr(self.comp.par, name, p)
        return p

    @property
    def parTuplets(self):
        return [(p,) for p in self.pars]

    def appendStrMenu(self, name, label=None):
        p = self.add(name, 'StrMenu')
        p.label = label or name
        return [p]

    def sort(self, *names):
        self.pars.sort(key=lambda p: names.index(p.name) if p.name in names else len(names))


class TestMenus(unittest.TestCase):
    def test_name_menu(self):
        m = ML['name_menu'](['E1', 'E2'], ['E1 (box)', 'E2 (null)'], none=True)
        self.assertEqual(m.menuNames, [' ', 'E1', 'E2'])          # '' is an invalid TD menu name
        self.assertEqual(m.menuLabels, ['(none)', 'E1 (box)', 'E2 (null)'])
        self.assertEqual(ML['name_menu'](['a', 'a', 'b']).menuNames, ['a', 'b'])     # unique names

    def test_select_menu_items_are_whole_values(self):
        m = ML['select_menu']('E1', ['E1', 'E2'], ['light'])
        d = dict(zip(m.menuLabels, m.menuNames))
        self.assertEqual(d['all (every one)'], 'all')
        self.assertEqual(d['+ E2'], 'E1 E2')
        self.assertEqual(d['+ #light'], 'E1 #light')
        self.assertEqual(d['- E1'], ' ')
        self.assertNotIn('+ E1', d)
        self.assertNotIn('(clear)', d)                  # one word: '- E1' already empties it

    def test_select_menu_from_all_and_unknown_words(self):
        m = ML['select_menu']('all', ['E1'], [])
        self.assertIn('E1', m.menuNames)                 # 'all' is replaced, not extended
        m = ML['select_menu']('E1 ghost', ['E1'], [], all_word=None)
        d = dict(zip(m.menuLabels, m.menuNames))
        self.assertEqual(d['- ghost'], 'E1')             # typed words can be removed too
        self.assertEqual(d['(clear)'], ' ')
        self.assertNotIn('all (every one)', d)
        self.assertEqual(len(m.menuNames), len(set(m.menuNames)))
        self.assertNotIn('', m.menuNames)
        m = ML['select_menu'](' ', ['E1'], [], all_word=None)          # the ' ' empty value starts fresh
        self.assertEqual(m.menuNames, ['E1'])

    def test_select_menu_extra_and_kinds(self):
        m = ML['select_menu']('', ['eff1'], [], all_word=None, extra=[('eff*', 'eff* (pattern)')], kinds={'eff1': 'null'})
        self.assertEqual(m.menuNames, ['eff*', 'eff1'])
        self.assertEqual(m.menuLabels, ['+ eff* (pattern)', '+ eff1 (null)'])

    def test_sources(self):
        s = ML['shared_source']('Effselect', 'select')
        self.assertIn("r.module.menu(m, 'Effselect', 'select')", s)
        self.assertTrue(s.endswith(", me)"))              # me passed in: not visible inside a lambda (T-159)
        self.assertIn("op('/project1/effectors/eff_rt')", s)
        self.assertIn("'menuNames': []", s)              # empty menu while the list is missing, never an error
        self.assertEqual(ML['local_source']('Target', 'eff_rt'), "me.op('eff_rt').module.menu(me, 'Target')")

    def test_to_strmenu_keeps_value_order_label(self):
        comp = types.SimpleNamespace(par=types.SimpleNamespace())
        pg = FakePage(comp)
        pg.add('Add', 'Pulse')
        old = pg.add('Sel', 'Int', 5)
        old.label = 'Selected uid'
        pg.add('Remove', 'Pulse')
        self.assertEqual(ML['to_strmenu'](comp, 'Sel', 'SRC'), 'converted')
        self.assertTrue(old.destroyed)
        q = comp.par.Sel
        self.assertEqual((q.style, q.val, q.label, q.menuSource), ('StrMenu', '5', 'Selected uid', 'SRC'))
        self.assertEqual([p.name for p in pg.pars], ['Add', 'Sel', 'Remove'])
        self.assertEqual(ML['to_strmenu'](comp, 'Sel', 'SRC'), 'same')
        self.assertEqual(ML['to_strmenu'](comp, 'Sel', 'SRC2'), 'source')
        self.assertIsNone(ML['to_strmenu'](comp, 'Add', 'SRC'))          # pulses are never touched
        self.assertIsNone(ML['to_strmenu'](comp, 'Nope', 'SRC'))

    def test_to_strmenu_keeps_expression(self):
        comp = types.SimpleNamespace(par=types.SimpleNamespace())
        pg = FakePage(comp)
        p = pg.add('Effselect', 'Str', 'all')
        p.mode = types.SimpleNamespace(name='EXPRESSION')
        p.expr = "'#light'"
        ML['to_strmenu'](comp, 'Effselect', 'SRC')
        q = comp.par.Effselect
        self.assertEqual((q.expr, q.mode.name), ("'#light'", 'EXPRESSION'))


class TestPxSpecs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.L = _load('px_logic')

    def test_menu_fields(self):
        L = self.L
        names = [n for _pg, pars in L['CORE_PAGES'] for n in L['menu_specs'](pars)]
        for n in ('Presetname', 'Sel', 'Effname', 'Actorfollow', 'Camfollow', 'Vhlights', 'Geolights'):
            self.assertIn(n, names)
        inst = L['new_instance']('prox_push', 3)
        self.assertEqual(L['menu_specs'](L['instance_par_specs'](inst)), ['M3effectors'])
        self.assertEqual(L['menu_source']('Sel'), "me.op('px_rt').module.menu(me, 'Sel')")

    def test_sel(self):
        L = self.L
        self.assertEqual(L['sel_uid']('4'), 4)
        self.assertEqual(L['sel_uid'](4), 4)
        self.assertEqual(L['sel_uid']('4 Dissolve'), 4)
        self.assertEqual(L['sel_uid']('', 1), 1)
        self.assertEqual(L['sel_uid']('look', 0), 0)
        inst = L['new_instance']('dissolve_noise', 4, enabled=False, label='Dissolve: noise')
        self.assertEqual(L['sel_label'](inst), '4 Dissolve: noise (off)')


class TestResolution(unittest.TestCase):
    def test_items(self):
        L = _load('px_logic')
        names = [n for n, _l in L['RESOLUTIONS']]
        self.assertEqual(names[0], '1080x1920')
        self.assertEqual(names[-1], 'custom')
        for n in names[:-1]:
            w, h = L['res_size'](n)
            self.assertLessEqual(max(w, h), 3840)          # Metal texture limit 16384 (T-231)
            self.assertEqual(L['res_name'](w, h), n)
        self.assertIsNone(L['res_size']('custom'))
        self.assertEqual(L['res_name'](1000, 1920), 'custom')
        look = dict((pg, [p[0] for p in pars]) for pg, pars in L['CORE_PAGES'])
        page = next(v for v in look.values() if 'Resx' in v)
        self.assertEqual(page.index('Resolution') + 1, page.index('Resx'))

    def test_px_builder_stages(self):
        src = open(os.path.join(B, 'px.py')).read()
        for t in ('3 Source (GPU)', '4 State + update', '5 Sort (splat order)', '6 Look / colour', '7a Render',
                  '8a Lines', '8b Trails + glow + haze', '8c Post (grade)', '9 Out'):
            self.assertIn(t, src)
        self.assertIn("_expr(rp.par.resolutionw, PREVIEW_W)", src)       # preview follows Resx / Resy


class TestOtherSpecs(unittest.TestCase):
    def test_consumer_and_builder_specs(self):
        EL = _load('effectors_logic')
        eff = dict((n, o) for n, _s, _d, o in EL['CONSUMER_PAGE'])
        self.assertEqual(eff['Effselect'].get('menu'), 'select')
        for name, par, kind in (('physarum_logic', 'Effectors', 'objects@'),
                                ('reaction_diffusion_logic', 'Effectors', 'objects@')):
            L = _load(name)
            found = [o for _pg, pars in L['PAGES'] for n, _s, _d, o in pars if n == par] if 'PAGES' in L else None
            if found is None:
                src = open(os.path.join(B, name + '.py')).read()
                self.assertIn("'menu': %r" % kind, src)
            else:
                self.assertEqual(found[0].get('menu'), kind)


class _Op(object):
    worldTransform = None            # class-level, like TD's object COMPs (T-115)

    def __init__(self, path, optype, store=None):
        self.path, self.OPType, self.isCOMP, self.valid = path, optype, True, True
        self.name = path.rsplit('/', 1)[-1]
        self._store = store or {}

    def fetch(self, k, d=None, search=False):
        return self._store.get(k, d)


class RefPicker(unittest.TestCase):
    """Effector ref picker (28 Oct): Refto / Addref items, check_ref, the Effectors page spec."""

    def setUp(self):
        class geometryCOMP(_Op):
            pass

        class nullCOMP(geometryCOMP):
            pass

        class lightCOMP(geometryCOMP):        # TD: Null and Light COMPs are found by type=geometryCOMP too
            pass
        self.cls = {'nullCOMP': nullCOMP, 'geometryCOMP': geometryCOMP, 'lightCOMP': lightCOMP}
        ops = [nullCOMP('/project1/rig/hand_l', 'nullCOMP'), nullCOMP('/project1/rig/hand_r', 'nullCOMP'),
               geometryCOMP('/project1/lab/MX/geo1', 'geometryCOMP'), lightCOMP('/project1/lab/MX/light1', 'lightCOMP'),
               geometryCOMP('/project1/effectors/sphere1', 'geometryCOMP'),
               lightCOMP('/project1/effectors/key1', 'lightCOMP')]
        self.ops = dict((o.path, o) for o in ops)
        EL = _load('effectors_logic')
        test = self
        rows = [{'name': 'sphere1', 'kind': 'sphere', 'ref': ''}, {'name': 'n1', 'kind': 'null', 'ref': ''},
                {'name': 'key1', 'kind': 'light', 'ref': ''}, {'name': 'p1', 'kind': 'pts', 'ref': ''}]
        self.rows = rows

        class Root(object):
            path = '/project1'
            calls = [0]

            def findChildren(self, type=None, **k):
                self.calls[0] += 1
                return [o for o in test.ops.values() if isinstance(o, type)]

        self.root = Root()

        class Eff(object):
            path = '/project1/effectors'

            def op(self, n):
                return {'eff_logic': types.SimpleNamespace(module=types.SimpleNamespace(**EL)),
                        'menu_logic': types.SimpleNamespace(module=types.SimpleNamespace(**ML))}.get(n)

            def parent(self):
                return test.root
        self.eff = Eff()

        def op(path):
            return test.root if path == '/project1' else test.ops.get(path)
        ns = {'__name__': 'eff_rt', 'me': types.SimpleNamespace(parent=lambda: self.eff), 'op': op,
              'boxSOP': 1, 'sphereSOP': 1, 'gridSOP': 1, 'tubeSOP': 1, 'torusSOP': 1}
        import builtins
        self._bk = dict((k, getattr(builtins, k, None)) for k in self.cls)
        for k, v in self.cls.items():         # in TD the op classes are builtins of a DAT module, not its globals
            setattr(builtins, k, v)
        with open(os.path.join(B, 'effectors_rt.py')) as f:
            exec(compile(f.read(), 'effectors_rt.py', 'exec'), ns)
        ns['rows'] = lambda: rows
        self.R = ns

    def tearDown(self):
        import builtins
        for k, v in self._bk.items():
            if v is None:
                delattr(builtins, k)
            else:
                setattr(builtins, k, v)

    def comp(self, target='sphere1'):
        return types.SimpleNamespace(par=types.SimpleNamespace(Target=types.SimpleNamespace(eval=lambda: target)))

    def test_items_by_path_own_objects_out_none_first(self):
        m = self.R['ref_menu'](types.SimpleNamespace(**ML), self.comp())
        self.assertEqual(m.menuNames[0], ML['NONE'])
        self.assertEqual(m.menuLabels[0], '(none)')
        self.assertEqual(m.menuNames[1:], ['/project1/lab/MX/geo1', '/project1/lab/MX/light1', '/project1/rig/hand_l',
                                           '/project1/rig/hand_r'])
        self.assertEqual(m.menuLabels[3], 'rig/hand_l (null)')
        self.assertNotIn('', m.menuNames)                                   # '' is an invalid menu name (T-233)
        self.rows[0]['ref'] = '/project1/rig/hand_r'
        self.R['STATE'].pop('refmenu', None)
        m = self.R['ref_menu'](types.SimpleNamespace(**ML), self.comp())
        self.assertEqual(m.menuLabels[4], 'rig/hand_r (null) = Target now')

    def test_memo_one_scan_for_names_and_labels(self):
        n0 = self.root.calls[0]
        a = self.R['ref_menu'](types.SimpleNamespace(**ML), self.comp())
        b = self.R['ref_menu'](types.SimpleNamespace(**ML), self.comp())
        self.assertIs(a, b)
        self.assertEqual(self.root.calls[0] - n0, 3)                        # null + geo + light, once
        self.assertEqual(a.menuLabels[2], 'lab/MX/light1 (light)')          # tag from OPType, not the search type

    def test_check_ref(self):
        ck = self.R['check_ref']
        self.assertIsNone(ck('sphere', '/project1/rig/hand_l'))
        self.assertIsNone(ck('null', '/project1/rig/hand_l'))
        self.assertIsNone(ck('sphere', ''))                                 # untie
        self.assertIsNone(ck('pts', '/project1/lab/FT/out_pts'))            # point sets: their own ref meaning
        self.assertIn('Light COMP', ck('light', '/project1/rig/hand_l'))
        self.assertIsNone(ck('light', '/project1/lab/MX/light1'))
        self.assertIn('inside', ck('sphere', '/project1/effectors/sphere1'))
        self.assertIn('no op', ck('sphere', '/project1/nope'))
        self.assertTrue(self.R['follows_ref']('null') and not self.R['follows_ref']('pts'))

    def test_page_spec(self):
        src = open(os.path.join(B, 'effectors.py')).read()
        ns = {'__name__': 'effectors_t', 'op': None}
        exec(compile(src.split('\ndef _sd(o):')[0], 'effectors.py', 'exec'), ns)
        self.assertIn("('Addref', 'Str', '', {'label': 'Tie new one to (Null / Geo / Light)', 'menu': 'refs'})", src)
        self.assertIn("'menu': 'refs'})", src.split("('Refto'")[1][:120])
        order = src.split('EFF_ORDER = [')[1].split(']')[0]
        for n in ('Addref', 'Refto', 'Setref', 'Target', 'Add'):
            self.assertIn("'%s'" % n, order)
        self.assertIn('Setref', src.split("PULSE_PARS = '")[1].split("'")[0])
        self.assertEqual(self.R['OWN_KINDS']['Refto'], 'refs')
        for f in ('effectors.py', 'effectors_rt.py'):
            open(os.path.join(B, f), 'rb').read().decode('ascii')       # ASCII only


if __name__ == '__main__':
    unittest.main()
