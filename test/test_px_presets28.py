"""Offline tests for the PX 28 Oct presets lane (docs/builds/px.md "28 Oct: presets"): auto progress on explode /
dissolve_noise / dissolve_gradient, preset reorder / sort / rename, the v1 effector fix, Trigauto. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_px_presets28.py'"""
import json
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


class AutoProgress(unittest.TestCase):
    def test_pars_on_the_three_modules(self):
        for t in L.AUTO_TYPES:
            names = [p['name'] for p in L.MODULES[t]['params']]
            k = names.index('progress')
            self.assertEqual(names[k + 1:k + 4], ['auto', 'rate', 'automax'], t)
            self.assertEqual(L.param(t, 'auto')['default'], 'off')
            self.assertTrue(L.param(t, 'rate')['rate'])

    def test_snippets_use_the_auto_value(self):
        snips = L.parse_snippets(_rd('glsl', 'px_modules.glsl'))
        for t in L.AUTO_TYPES:
            code = snips[(t, 'update')]
            self.assertIn('fract($rateph)', code)
            self.assertIn('$auto', code)
            self.assertEqual(code.count('$progress'), 1, t)                 # only inside the pg = ... line
            self.assertNotRegex(code, r'float e = [^\n]*\$progress')
        self.assertEqual(L.check_snippets(snips), [])

    def test_reference_curve(self):
        self.assertEqual(L.auto_progress(0.3, 'off', 7.25), 0.3)
        self.assertAlmostEqual(L.auto_progress(0.3, 'loop', 7.25), 0.25)
        self.assertAlmostEqual(L.auto_progress(0.0, 'pingpong', 0.5), 1.0)
        self.assertAlmostEqual(L.auto_progress(0.0, 'pingpong', 1.0), 0.0)
        self.assertAlmostEqual(L.auto_progress(0.0, 'pingpong', 0.25), 0.5)
        self.assertAlmostEqual(L.auto_progress(0.0, 2, 0.75), 0.5)        # menu index works too

    def test_drive_on_progress_turns_auto_off(self):
        v = {'auto': 'pingpong', 'progress': 0.0}
        d, _ = L.parse_drives('progress:lfo1*1')
        self.assertEqual(L.auto_vals('explode', v, d)['auto'], 'off')
        self.assertEqual(v['auto'], 'pingpong')                            # cached dict untouched
        d2, _ = L.parse_drives('distance:low*2')
        self.assertIs(L.auto_vals('explode', v, d2), v)
        self.assertIs(L.auto_vals('curl', v, d), v)

    def test_rate_only_live_while_auto_on(self):
        p = L.param('explode', 'rate')
        self.assertFalse(L.rate_live('explode', {'auto': 'off', 'rate': 0.1}, p))
        self.assertTrue(L.rate_live('explode', {'auto': 'loop', 'rate': 0.1}, p))
        self.assertFalse(L.rate_live('explode', {'auto': 'loop', 'rate': 0.0}, p))
        self.assertTrue(L.rate_live('dissolve_time', {'rate': 0.2}, L.param('dissolve_time', 'rate')))

    def test_auto_top(self):
        self.assertAlmostEqual(L.auto_progress(0.0, 'pingpong', 0.5, 0.6), 0.6)
        self.assertAlmostEqual(L.auto_progress(0.0, 'loop', 0.5, 0.6), 0.3)
        self.assertIn('$automax', L.parse_snippets(_rd('glsl', 'px_modules.glsl'))[('explode', 'update')])

    def test_guard_hand_and_echo(self):
        g = L.auto_guard_off
        self.assertEqual(g('M3progress', 0.4, 'pingpong'), 3)                       # by hand
        self.assertIsNone(g('M3progress', 0.4, 'off'))                              # already off
        self.assertIsNone(g('M3progress', 0.4, 'loop', True, own=0.4))              # PX's own write (recall echo)
        self.assertEqual(g('M3progress', 0.5, 'loop', True, own=0.4), 3)            # user moved it after
        self.assertEqual(g('M3progress', 0.4, 'loop', False, own=0.4), 3)           # expression / export / CHOP
        self.assertEqual(g('M3drive', 'progress:lfo1*1', 'loop'), 3)
        self.assertIsNone(g('M3drive', 'distance:low*2', 'loop'))
        self.assertIsNone(g('M3amount', 0.4, 'loop'))

    def test_new_module_defaults_pingpong(self):
        self.assertEqual(L.new_module_values('explode', 5), {'M5auto': 'pingpong', 'M5rate': 0.1})
        self.assertEqual(L.new_module_values('curl', 5), {})

    def test_packed_rows_carry_auto_and_phase(self):
        st, uid = L.add_module([], 'explode')
        lay, nrows = L.layout(st)
        vals = {uid: dict(L.instance_defaults(st[0]), auto='pingpong', rate=0.5)}
        ph = L.integrate_phases({}, lay, vals, 1.0)
        rows = L.pack_module_rows(lay, nrows, vals, [], ph)
        r, c = lay[0]['slots']['auto']
        self.assertEqual(rows[r][c], 2.0)
        r, c = lay[0]['slots']['rateph']
        self.assertAlmostEqual(rows[r][c], 0.5)

    def test_old_presets_load_with_auto_off(self):
        st, uid = L.add_module([], 'dissolve_noise')
        snap = L.snapshot(st, {'M%dprogress' % uid: 0.4})
        d = L.preset_loads(L.preset_dumps(snap))
        self.assertEqual(d['values']['M%dauto' % uid], 'off')
        snap['values']['M%dauto' % uid] = 'loop'                           # a preset that says loop keeps it
        self.assertEqual(L.preset_loads(L.preset_dumps(snap))['values']['M%dauto' % uid], 'loop')

    def test_builtins_say_off(self):
        for nm in ('Radial blast', 'Tile city', 'Spiral reveal'):
            s = L.builtin_preset(nm)
            for i in s['stack']:
                if i['type'] in L.AUTO_TYPES:
                    self.assertEqual(s['values']['M%dauto' % i['uid']], 'off', nm)


class PresetOrder(unittest.TestCase):
    N = ['b', 'KANDA swipe', 'a', 'Tile city (splats)', 'Zed', 'splat_showcase']

    def test_move(self):
        self.assertEqual(L.preset_move(self.N, 'a', -1), ['b', 'a', 'KANDA swipe', 'Tile city (splats)', 'Zed', 'splat_showcase'])
        self.assertEqual(L.preset_move(self.N, 'b', -1), self.N)                    # top stays top
        self.assertEqual(L.preset_move(self.N, 'splat_showcase', 1), self.N)        # bottom stays bottom
        self.assertEqual(L.preset_move(self.N, 'nope', 1), self.N)
        self.assertEqual(sorted(L.preset_move(self.N, 'Zed', -3)), sorted(self.N))  # never loses one

    def test_sort_builtins_first(self):
        self.assertEqual(L.preset_sort(self.N), ['KANDA swipe', 'splat_showcase', 'Tile city (splats)', 'a', 'b', 'Zed'])
        self.assertEqual(L.preset_sort(L.preset_sort(self.N)), L.preset_sort(self.N))

    def test_rename_check(self):
        self.assertEqual(L.preset_rename_check(self.N, 'a', 'c'), '')
        self.assertTrue(L.preset_rename_check(self.N, 'a', 'b'))
        self.assertTrue(L.preset_rename_check(self.N, 'a', '  '))
        self.assertTrue(L.preset_rename_check(self.N, 'x', 'c'))

    def test_new_presets_page_pars(self):
        pg = dict(L.CORE_PAGES)['Presets']
        names = [p[0] for p in pg]
        for n in ('Presetup', 'Presetdown', 'Newname', 'Presetrename', 'Presetsort'):
            self.assertIn(n, names)
        self.assertLess(names.index('Morphto'), names.index('Presetup'))


class V1Fix(unittest.TestCase):
    def test_adds_effectors_once(self):
        st, _u = L.add_module([], 'prox_push')
        snap = L.snapshot(st, {'M1effectors': 'N1 N2 N3'})
        a, ch = L.fix_v1_preset('hand_push_cloud', snap)
        self.assertTrue(ch)
        self.assertEqual([m[0] for m in a['make']], ['N1', 'N2', 'N3'])
        self.assertEqual(a['effpars']['N1']['Motion'], 'lissajous')
        b, ch2 = L.fix_v1_preset('hand_push_cloud', json.loads(L.preset_dumps(a)))
        self.assertFalse(ch2)
        self.assertEqual(L.preset_dumps(b), L.preset_dumps(a))
        _c, ch3 = L.fix_v1_preset('KANDA swipe', snap)
        self.assertFalse(ch3)

    def test_motion_close_to_old_expression(self):
        import math
        ep = L.fix_v1_preset('hand_push_cloud', L.snapshot([], {}))[0]['effpars']['N1']
        s = L.eff_settings(dict((k + s_, v[i]) if isinstance(v, list) else (k, v)
                                for k, v in ep.items() for i, s_ in (enumerate('xyz') if isinstance(v, list) else [(0, '')])))
        for t in (0.0, 1.3, 4.0):
            p = L.motion_pos('lissajous', t, s)
            self.assertAlmostEqual(p[0], 0.75 * math.sin(t * 0.9), places=5)
            self.assertAlmostEqual(p[1], 0.45 * math.cos(t * 0.7), places=5)


class TrigAuto(unittest.TestCase):
    def test_fires_every_n(self):
        self.assertEqual(L.trig_auto(5.0, None, 0.0, 'all'), ([], None))
        f, last = L.trig_auto(5.0, None, 2.0, 'all')
        self.assertEqual((f, last), ([0, 1, 2, 3], 5.0))
        self.assertEqual(L.trig_auto(6.0, 5.0, 2.0, 'all'), ([], 5.0))
        self.assertEqual(L.trig_auto(7.0, 5.0, 2.0, 'trig2'), ([1], 7.0))
        self.assertEqual(L.trig_auto(1.0, 5.0, 2.0, 'trig1'), ([0], 1.0))      # sim time went back (Reset)

    def test_core_pars(self):
        names = [p[0] for p in dict(L.CORE_PAGES)['Drive']]
        self.assertLess(names.index('Trigdecay'), names.index('Trigauto'))
        self.assertIn('Trigautowhich', names)


class Upgrade(unittest.TestCase):
    def test_upgrade_function_present(self):
        src = _rd('px.py')
        self.assertIn('def presets28_upgrade(', src)
        self.assertIn("V1_FIX_PRESETS", src)
        self.assertTrue(re.search(r"def _sort_page\(pg, first\)", src))


if __name__ == '__main__':
    unittest.main()
