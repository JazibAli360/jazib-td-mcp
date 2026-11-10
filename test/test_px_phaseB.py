"""Offline tests for PX phase B (28 Oct): module browser + Addafter, Solo / Unsolo, hard size limits (T-231), preset
checks on recall, one shared-list row per PX instance (copy-safe). docs/builds/px.md "28 Oct: phase B".
No TD needed. Run: python3 -I -m unittest discover -s test -p 'test_px_phaseB.py'"""
import json
import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
sys.path.insert(0, BUILDERS)
import px_logic as L  # noqa: E402


def _rd(*p):
    with open(os.path.join(BUILDERS, *p)) as fh:
        return fh.read()


def _spec(page, name):
    for pg, pars in L.CORE_PAGES:
        if pg == page:
            for s in pars:
                if s[0] == name:
                    return s
    return None


def stack(*types_on):
    st = []
    for t, on in types_on:
        st, _u = L.add_module(st, t)
        st[-1]['enabled'] = on
    return st


# ---- a fake TD parent for evaluating PX's size expressions -------------------------------------------------------
class _Par(object):
    def __init__(self, v):
        self.v = v

    def eval(self):
        return self.v

    def __int__(self):
        return int(self.v)

    def __float__(self):
        return float(self.v)

    def __mul__(self, o):
        return self.v * o

    def __floordiv__(self, o):
        return self.v // o


class _Pars(object):
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, _Par(v))


class _Comp(object):
    def __init__(self, **kw):
        self.par = _Pars(**kw)


class _Me(object):
    def __init__(self, comp):
        self._c = comp

    def parent(self):
        return self._c


def ev(expr, **pars):
    comp = _Comp(**pars)
    return eval(expr, {'me': _Me(comp), 'parent': lambda: comp, 'math': math, 'int': int, 'min': min, 'max': max})


class Browser(unittest.TestCase):
    def test_every_module_once_grouped_by_category(self):
        names, labels = L.module_browser()
        self.assertEqual(sorted(names), sorted(L.MODULES))
        self.assertEqual(len(names), len(set(names)))
        cats = [L.MODULES[t]['cat'] for t in names]
        order = [k for k, _l in L.CATEGORIES]
        self.assertEqual(cats, sorted(cats, key=order.index))            # one block per category, in order

    def test_label_format(self):
        self.assertEqual(L.module_label('explode'),
                         'Motion › Explode / reassemble — points fly out and back')
        for t, m in L.MODULES.items():
            self.assertTrue(m.get('desc'), t)
            self.assertLessEqual(len(m['desc']), 64, t)                   # short and plain
            m['desc'].encode('ascii')
            self.assertTrue(L.module_label(t).startswith(dict(L.CATEGORIES)[m['cat']] + ' › '), t)

    def test_addtype_spec_is_a_live_dropdown(self):
        s = _spec('Stack', 'Addtype')
        self.assertEqual((s[1], s[2], s[3].get('menu')), ('Str', 'prox_push', True))
        self.assertIn("'Addtype'", L.menu_source('Addtype'))

    def test_addtype_of(self):
        self.assertEqual(L.addtype_of('explode'), 'explode')
        self.assertEqual(L.addtype_of(L.module_label('wave')), 'wave')
        self.assertEqual(L.addtype_of(' Curl noise '), 'curl')
        self.assertIsNone(L.addtype_of('zap'))
        self.assertIsNone(L.addtype_of(''))

    def test_add_after(self):
        st = stack(('prox_push', True), ('curl', True), ('wave', True))
        self.assertIsNone(L.add_index(st, 2, False))
        self.assertEqual(L.add_index(st, 2, True), 2)                     # right after uid 2 (index 1)
        self.assertEqual(L.add_index(st, 3, True), 3)
        self.assertIsNone(L.add_index(st, 9, True))                       # Sel not in the stack: the end
        st2, uid = L.add_module(st, 'explode', L.add_index(st, 1, True))
        self.assertEqual([i['type'] for i in st2], ['prox_push', 'explode', 'curl', 'wave'])
        self.assertEqual(uid, 4)

    def test_stack_page_pars(self):
        page = [s[0] for s in dict(L.CORE_PAGES)['Stack']]
        for n in ('Addafter', 'Solo', 'Unsolo'):
            self.assertIn(n, page)
        self.assertLess(page.index('Add'), page.index('Addafter'))
        self.assertLess(page.index('Toggleon'), page.index('Solo'))
        self.assertIn('Addafter', L.NOSNAP)

    def test_main_tab_unchanged(self):
        with open(os.path.join(BUILDERS, 'zk_essentials.json')) as fh:
            ess = json.load(fh)['PX_pointfx']
        self.assertLessEqual(len(ess['main']), 16)
        self.assertNotIn('Solo', ess['main'])                            # the user decides (default: not on Main)


class Solo(unittest.TestCase):
    def setUp(self):
        self.st = stack(('prox_push', True), ('curl', False), ('prox_colour', True), ('dissolve_noise', True))

    def test_solo_then_unsolo_restores_exactly(self):
        st1, saved = L.solo_stack(self.st, 3)
        self.assertEqual([i['enabled'] for i in st1], [False, False, True, False])
        self.assertEqual(saved, {'1': True, '2': False, '3': True, '4': True})
        back = L.unsolo_stack(st1, saved)
        self.assertEqual(back, self.st)

    def test_solo_another_keeps_the_first_saved_set(self):
        st1, saved = L.solo_stack(self.st, 3)
        st2, saved2 = L.solo_stack(st1, 1, saved)
        self.assertEqual([i['enabled'] for i in st2], [True, False, False, False])
        self.assertEqual(saved2, saved)
        self.assertEqual(L.unsolo_stack(st2, saved2), self.st)

    def test_solo_a_disabled_module_runs_it(self):
        st1, _s = L.solo_stack(self.st, 2)
        self.assertEqual([i['enabled'] for i in st1], [False, True, False, False])

    def test_unknown_uid_is_a_no_op(self):
        st1, saved = L.solo_stack(self.st, 9)
        self.assertEqual((st1, saved), (self.st, None))

    def test_added_and_removed_while_soloed(self):
        st1, saved = L.solo_stack(self.st, 3)
        st1, _u = L.add_module(st1, 'wave')                              # added while soloed: stays on
        st1 = L.remove_module(st1, 2)
        back = L.unsolo_stack(st1, saved)
        self.assertEqual([(i['uid'], i['enabled']) for i in back], [(1, True), (3, True), (4, True), (5, True)])

    def test_store_writes_the_real_set(self):
        st1, saved = L.solo_stack(self.st, 3)
        self.assertEqual(L.real_stack(st1, saved), self.st)
        self.assertEqual(L.real_stack(self.st, None), self.st)
        snap = L.snapshot(L.real_stack(st1, saved), {})
        self.assertEqual([i['enabled'] for i in snap['stack']], [True, False, True, True])

    def test_sel_labels(self):
        st1, _s = L.solo_stack(self.st, 3)
        labs = [L.sel_label(i, 3) for i in st1]
        self.assertEqual(labs, ['1 Proximity push / pull (off)', '2 Curl noise (off)', '3 Proximity colour (solo)',
                                '4 Dissolve: noise (off)'])
        self.assertEqual(L.sel_label(self.st[1]), '2 Curl noise (off)')
        self.assertEqual(L.sel_label(self.st[0]), '1 Proximity push / pull')


# expressions PX's TOPs use today (builders/px.py), as written there
PX_EXPRS = {
    'render_w': 'parent().par.Resx', 'render_h': 'parent().par.Resy',
    'preview_w': 'max(16, int(parent().par.Resx) // 2)', 'preview_h': 'max(16, int(parent().par.Resy) // 2)',
    'haze_q_w': 'max(1, int(parent().par.Resx) // 4)', 'haze_h_h': 'max(1, int(parent().par.Resy) // 2)',
    'proj_w': "(int(parent().par.Projface) if True else int(parent().par.Resx))",
    'proj_off_h': "(int(parent().par.Projface) if False else int(parent().par.Resy))",
    'env': 'max(16, int(parent().par.Geoenvres))',
}


class SizeLimits(unittest.TestCase):
    def test_count_cap_keeps_the_widest_point_texture_inside(self):
        side = L.side_for(L.COUNT_MAX)
        self.assertLessEqual(L.STATE_TEXELS * side, L.TEX_MAX)
        self.assertGreater(L.STATE_TEXELS * (side + 1), L.TEX_MAX)         # the cap is tight, not arbitrary
        self.assertEqual(L.COUNT_MAX, 1638 ** 2)

    def test_every_point_texture_at_every_count_extreme(self):
        cnt = _spec('Source', 'Count')
        for raw in ({'Quality': 'custom', 'Count': cnt[3]['max']}, {'Quality': 'custom', 'Count': 80000000},
                    {'Quality': 'custom', 'Count': 2 ** 31 - 1}, {'Quality': 'max'}, {'Quality': 'ultra'},
                    {'Quality': 'custom', 'Count': 0}, {'Quality': 'custom', 'Count': -5}):
            n = L.quality_count(raw)
            self.assertGreaterEqual(n, 1)
            self.assertLessEqual(n, L.COUNT_MAX, raw)
            ts = L.tex_sizes(n)
            for k in ('state', 'rest', 'look'):
                self.assertLessEqual(max(ts[k]), L.TEX_MAX, (raw, k))
            side = ts['side']
            self.assertLessEqual(side, L.TEX_MAX)                          # sort_keys side x side
            self.assertLessEqual(2 * side, L.TEX_MAX)                      # rest_files A|B stacked rows
            self.assertEqual(L.side_from_pars(raw.get('Quality'), raw.get('Count', 1)), side)
            ns, na, npool = L.layers(dict(raw, Actormode='file', Actorcount=10 ** 9, Pool=50), n)
            self.assertLessEqual(L.REST_TEXELS * L.side_for(max(na, 1)), L.TEX_MAX)   # rest_actor

    def test_quality_max_still_listed(self):
        self.assertIn('max', L.names(L.QUALITY))                          # nothing removed; it runs at the cap
        self.assertEqual(L.quality_count({'Quality': 'max'}), L.COUNT_MAX)

    def test_eff_res(self):
        self.assertEqual(L.eff_res(1080, 1920), (1080, 1920))
        self.assertEqual(L.eff_res(8192, 8192), (8192, 8192))
        self.assertEqual(L.eff_res(10000, 20000), (4096, 8192))           # aspect kept
        self.assertEqual(L.eff_res(16384, 9216), (8192, 4608))
        w, h = L.eff_res(10 ** 7, 3)
        self.assertLessEqual(max(w, h), L.TEX_MAX)
        self.assertGreaterEqual(min(w, h), 1)
        rx, ry = (_spec('Look', 'Resx')[3]['max'], _spec('Look', 'Resy')[3]['max'])
        self.assertLessEqual(max(L.eff_res(rx, ry)), L.TEX_MAX)

    def test_proj_res(self):
        self.assertEqual(L.proj_res({'Resx': 20000, 'Resy': 10000}), (8192.0, 4096.0))
        self.assertEqual(L.proj_res({'Proj': 'fisheye', 'Projface': 50000}), (4096.0, 4096.0))
        self.assertEqual(L.proj_res({'Resx': 1080, 'Resy': 1920}), (1080.0, 1920.0))

    def test_expressions_at_par_max(self):
        big = dict(Resx=100000, Resy=60000, Projface=99999, Geoenvres=99999)
        for k, e in PX_EXPRS.items():
            e2 = L.clamp_expr(e, 'px')
            self.assertNotEqual(e2, e, k)
            v = ev(e2, **big)
            self.assertLessEqual(v, L.TEX_MAX, k)
            self.assertGreaterEqual(v, 1, k)
            self.assertEqual(L.clamp_expr(e2, 'px'), e2, k)                 # idempotent
        self.assertLessEqual(ev(L.clamp_expr(PX_EXPRS['proj_w']), **big), L.CUBE_MAX)
        self.assertLessEqual(ev(L.clamp_expr(PX_EXPRS['env']), **big), L.CUBE_MAX)
        # aspect kept: both sides scale together
        w = ev(L.clamp_expr(PX_EXPRS['render_w']), **big)
        h = ev(L.clamp_expr(PX_EXPRS['render_h']), **big)
        self.assertEqual((w, h), L.eff_res(100000, 60000))
        # glow 1/4 and 1/8, trail, post, layers follow render / Resx: all <= the render size
        self.assertLessEqual(w // 4, L.TEX_MAX)

    def test_expressions_unchanged_inside_limits(self):
        for k, e in PX_EXPRS.items():
            self.assertEqual(int(ev(L.clamp_expr(e), Resx=1080, Resy=1920, Projface=1024, Geoenvres=128)),
                             int(ev(e, Resx=1080, Resy=1920, Projface=1024, Geoenvres=128)), k)

    def test_lines_rules(self):
        seg_h = "max(1, (int(parent().par.Maxseg.eval()) + 255) // 256)"
        e2 = L.clamp_expr(seg_h, 'lines')
        self.assertLessEqual(ev(e2, Maxseg=10 ** 10), L.TEX_MAX)
        self.assertEqual(ev(e2, Maxseg=20000), ev(seg_h, Maxseg=20000))
        self.assertEqual(L.clamp_expr(e2, 'lines'), e2)
        self.assertEqual(L.clamp_expr('parent().par.Resx.eval()', 'lines'), 'parent().par.Resx.eval()')  # PX_lines' own
        # Resx is fed by PX's clamped expression
        self.assertEqual(L.clamp_expr('parent().par.Maxseg', 'px'), 'parent().par.Maxseg')
        self.assertEqual(L.LINES_SEG_W, 256)
        self.assertIn('SEG_W = 256', _rd('px_lines_logic.py'))
        # cn_index is capped at 128 cells by its own expression: 128 * ceil(sqrt(128)) = 1536
        n = 128
        self.assertLessEqual(n * int(math.ceil(math.sqrt(n))), L.TEX_MAX)

    def test_other_names_untouched(self):
        for e in ("me.parent().par.Resx", "op('x').par.Resx", "parent(2).par.Resx", "parent().par.Resxtra",
                  "parent().par.Size * 2"):
            self.assertEqual(L.clamp_expr(e), e, e)

    def test_hot_pts_size(self):
        hs = lambda cnt, hm: max(8, int(-(-(min(cnt, hm) ** 0.5) // 1)))   # builders/px.py _grid
        self.assertLessEqual(hs(L.COUNT_MAX, 10 ** 9), L.TEX_MAX)

    def test_size_notes(self):
        self.assertEqual(L.size_notes({'Quality': 'std', 'Resx': 1080, 'Resy': 1920}), [])
        n = L.size_notes({'Quality': 'custom', 'Count': 80000000, 'Resx': 1080, 'Resy': 1920})
        self.assertEqual(n, ['Count 80M -> clamped to 2.68M (8192 px state texture)'])
        n = L.size_notes({'Quality': 'max', 'Resx': 9000, 'Resy': 1000, 'Projface': 5000, 'Geoenvres': 64},
                         maxseg=10 ** 8)
        self.assertEqual(n, ['Quality max 4.19M -> clamped to 2.68M (8192 px state texture)',
                             'Res 9000x1000 -> 8192x910 (8192 px max)', 'Projface 5000 -> 4096 (cube faces <= 4096)',
                             'Lines Maxseg 100M -> 2.1M'])

    def test_px_builder_uses_the_clamps(self):
        px = _rd('px.py')
        self.assertIn('def _clamp_exprs(c)', px)
        self.assertIn("Lg['clamp_expr'](p.expr, rules)", px)
        self.assertIn('_clamp_exprs(c)                                   # phase B', px)   # build() too
        rt = _rd('px_rt.py')
        self.assertIn("L().size_notes(raw", rt)


class PresetChecks(unittest.TestCase):
    def test_unknown_types(self):
        d = {'stack': [{'uid': 1, 'type': 'curl'}, {'uid': 2, 'type': 'zap'}, {'uid': 3, 'type': 'wave'}], 'values': {}}
        self.assertEqual(L.preset_unknown_types(d), ['zap'])
        snap = L.preset_loads(json.dumps(d))
        self.assertEqual([i['type'] for i in snap['stack']], ['curl', 'wave'])

    def test_files_only_when_used(self):
        ex = lambda p: p == '/ok.ply'
        v = {'Amode': 'file', 'Afile': '/gone.splat', 'Bmode': 'gen', 'Bfile': '/also_gone.ply', 'Actormode': 'file',
             'Actorfile': '/ok.ply', 'Palsource': 'neon_trio', 'Palfile': '/x.gpl', 'Imagefile': '/img.png'}
        self.assertEqual(L.preset_files(v, ex), ['/gone.splat', '/img.png'])
        self.assertEqual(L.preset_files({}, ex), [])

    def test_effectors_missing(self):
        st = stack(('prox_push', True), ('curl', True), ('light', True))
        vals = {'M1effectors': 'E1 E9 #hands all', 'M3effectors': 'all', 'M2effectors': 'E7'}
        self.assertEqual(L.preset_eff_missing(st, vals, ['E1'], ['sphere1']), ['E9'])   # curl takes none
        self.assertEqual(L.preset_eff_missing(st, {'M1effectors': 'sphere1 E1'}, ['E1'], ['sphere1']), [])

    def test_summary(self):
        self.assertEqual(L.preset_summary('X', {}), 'recalled X')
        self.assertEqual(L.preset_summary('X', {'pars': ['Bar', 'Foo'], 'failed': [], 'types': []}),
                         'recalled X: 2 pars skipped (Bar, Foo)')
        s = L.preset_summary('Y', {'pars': ['A'], 'types': ['zap'], 'effectors': ['E9'],
                                   'files': ['/media/demo/splats/truck.splat'], 'failed': ['Sprite']})
        self.assertEqual(s, 'recalled Y: 1 par skipped (A); 1 not set (Sprite); module type unknown: zap; '
                            'effector missing: E9; file missing: truck.splat')
        self.assertEqual(L.preset_summary('Z', {'error': 'no preset'}, 'recall failed:'),
                         'recall failed: Z: error: no preset')
        many = L.preset_summary('M', {'pars': ['p%d' % k for k in range(9)]})
        self.assertIn('9 pars skipped (p0, p1, p2, p3 ...)', many)

    def test_runtime_never_raises_on_recall(self):
        rt = _rd('px_rt.py')
        body = rt[rt.index('def recall(c, name):'):rt.index('def morph_to(')]
        self.assertIn('except Exception as e:', body)
        self.assertIn('_check_applied(c, snap, notes)', body)
        self.assertIn("_report(c, name, notes, 'recall failed:')", body)
        self.assertIn('def note(c, kind, text):', rt)
        self.assertIn("'px_notes'", _rd('px.py'))


class Instances(unittest.TestCase):
    def test_hot_key(self):
        self.assertEqual(L.hot_key('PX_pointfx'), 'px_hot_px_pointfx')
        self.assertEqual(L.hot_key('PX_pointfx1'), 'px_hot_px_pointfx1')
        self.assertEqual(L.hot_key('PX_pointfx', ['px_hot_px_pointfx']), 'px_hot_px_pointfx_2')
        self.assertEqual(L.hot_key('PX point-fx', []), 'px_hot_px_point_fx')
        self.assertNotEqual(L.hot_key('PX_pointfx'), 'px_hot')               # never the legacy shared name

    def test_path_swap(self):
        old, new = '/project1/lab/PX_pointfx', '/project1/lab/PX_pointfx1'
        self.assertEqual(L.path_swap(old + '/controls', old, new), (new + '/controls', True))
        self.assertEqual(L.path_swap(old + '1/geo/g1', old, '/x'), (old + '1/geo/g1', False))   # PX vs PX1
        self.assertEqual(L.path_swap('%s/geo/a %s/geo/b' % (old, old), old, new),
                         ('%s/geo/a %s/geo/b' % (new, new), True))
        self.assertEqual(L.path_swap(old, old, new), (new, True))
        self.assertEqual(L.path_swap("op('%s/out1')" % old, old, new), ("op('%s/out1')" % new, True))

    def test_other_px_hot_rows_are_not_clouds(self):
        st = [dict(L.new_instance('prox_push', 1), values={'effectors': 'all'})]
        rows = [{'name': 'px_hot_px_pointfx', 'kind': 'cloud'}, {'name': 'px_hot_px_pointfx1', 'kind': 'cloud'}]
        self.assertFalse(L.stack_cloud(st, [], rows, 'px_hot_px_pointfx'))
        self.assertTrue(L.stack_cloud(st, [], rows + [{'name': 'smoke', 'kind': 'cloud'}], 'px_hot_px_pointfx'))

    def test_runtime_pieces(self):
        rt = _rd('px_rt.py')
        for n in ('def instance_check(c):', 'def hot_name(c):', 'def _cooking(c, s):', 'def px_instances(',
                  'def solo(c, uid):', 'def unsolo(c, quiet=False):', 'def _end_solo(c):'):
            self.assertIn(n, rt)
        self.assertNotIn("ert.add('cloud', HOT_ROW", rt)                 # every PX registers its own row
        self.assertIn('PX cooking: %dx cost', rt)
        self.assertIn("phaseB_upgrade(parent_path='/project1/lab', name=NAME)", _rd('px.py'))

    def test_upgrade_is_ui_safe_and_staged(self):
        px = _rd('px.py')
        up = px[px.index('def phaseB_upgrade('):px.index('def phaseB_result(')]
        self.assertIn('_ui_safe(c)', up)                                  # T-249: off the screen first
        self.assertIn("_upg_later(parent_path, name, 'texts')", up)
        for bad in ('beatsync28_upgrade(', '_strmenu_from_menu(', '_clamp_exprs(', 'instance_check(', '_table('):
            self.assertNotIn(bad, up)                                     # nothing changes in the calling frame
        safe = px[px.index('def _ui_safe(c):'):px.index('def _presets_sig(')]
        for need in ('winclose.pulse()', 'closeViewer()', 'pn.owner = up', 'c.viewer = False'):
            self.assertIn(need, safe)
        self.assertIn("delayFrames=delay", px)
        self.assertGreaterEqual(int(re.search(r'UPG_GAP = (\d+)', px).group(1)), 2)
        step = px[px.index('def _phaseB_step('):px.index("REST_SCENE = 'smiley'")]
        self.assertIn("UPG_STEPS = ('texts', 'menus', 'tables', 'done')", px)
        self.assertIn("_upg_later(parent_path, name, UPG_STEPS[k + 1])", step)   # one step per scheduled frame
        self.assertIn("st['state'] = 'failed'", step)                     # a failing step stops, viewer back

    def test_ascii_sources(self):
        for f in ('px_logic.py', 'px_rt.py', 'px.py'):
            _rd(f).encode('ascii')


if __name__ == '__main__':
    unittest.main()
