"""Offline tests for builders/show_rig_logic.py (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_show_rig.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import show_rig_logic as L  # noqa: E402

LABELS = ['TP_test_pattern', 'LK_spectrum_glass', 'BO_particles', 'BN_fluid2d', 'BL_cloud_morph',
          'LK_projection_room']


def lay(src, op_, mute=False, solo=False, blend='over'):
    return {'source': src, 'opacity': op_, 'mute': mute, 'solo': solo, 'blend': blend}


class Effective(unittest.TestCase):
    def test_mute_solo(self):
        ls = [lay(0, 1), lay(1, 0.5, mute=True), lay(2, 0.3)]
        self.assertEqual(L.effective(ls), [1.0, 0.0, 0.3])
        ls[2]['solo'] = True
        self.assertEqual(L.effective(ls), [0.0, 0.0, 0.3])

    def test_shown(self):
        ls = [lay(0, 1), lay(0, 1), lay(3, 0), lay(4, 0.2, mute=True)]
        self.assertEqual(L.shown_sources(ls), [0])
        self.assertEqual(L.shown_sources(ls, master=0), [])

    def test_fx_live(self):
        self.assertEqual(L.fx_live(False, {'strobe': True}), [])
        self.assertEqual(L.fx_live(True, {'strobe': True, 'palette': True}), ['palette', 'strobe'])


class CookPlan(unittest.TestCase):
    def test_owned_wakes_and_parks_only_own(self):
        cands = {'/p/lab/A': False, '/p/lab/B': False, '/p/lab/C': True}
        wake, park, owned = L.cook_plan(cands, ['/p/lab/A'], [])
        self.assertEqual((wake, park, owned), (['/p/lab/A'], [], ['/p/lab/A']))
        # switch layer source A -> B: B wakes, A (ours) parks, C (the user's) stays on
        cands = {'/p/lab/A': True, '/p/lab/B': False, '/p/lab/C': True}
        wake, park, owned = L.cook_plan(cands, ['/p/lab/B'], owned)
        self.assertEqual((wake, park, owned), (['/p/lab/B'], ['/p/lab/A'], ['/p/lab/B']))

    def test_strict_parks_others_but_not_lanes_or_roots(self):
        cands = {'/p/lab/A': True, '/p/lab/LANE': True, '/project1': True, '/p/lab/B': False}
        wake, park, owned = L.cook_plan(cands, ['/p/lab/B'], [], protected=['/p/lab/LANE'], mode='strict')
        self.assertEqual(wake, ['/p/lab/B'])
        self.assertEqual(park, ['/p/lab/A'])

    def test_off_touches_nothing(self):
        wake, park, owned = L.cook_plan({'/p/lab/A': False}, ['/p/lab/A'], ['/p/lab/A'], mode='off')
        self.assertEqual((wake, park, owned), ([], [], ['/p/lab/A']))

    def test_lane_never_parked_even_if_owned(self):
        wake, park, owned = L.cook_plan({'/p/lab/A': True}, [], ['/p/lab/A'], protected=['/p/lab/A'])
        self.assertEqual((park, owned), ([], []))


class Presets(unittest.TestCase):
    def test_roundtrip_by_name(self):
        st = {'layers': [lay(1, 0.75, blend='add'), lay(2, 0, mute=True)], 'Master': 0.9, 'Masterfx': True,
              'fx': {'strobe': True}}
        h = L.preset_header(2)
        row = L.state_to_row('x', st, LABELS)
        self.assertEqual(row[1], 'LK_spectrum_glass')
        back, errs = L.row_to_state(h, row, LABELS, 2)
        self.assertEqual(errs, [])
        self.assertEqual(back['layers'][0], {'source': 1, 'opacity': 0.75, 'blend': 'add', 'mute': False, 'solo': False})
        self.assertTrue(back['layers'][1]['mute'])
        self.assertEqual(back['fx'], {'palette': False, 'trail': False, 'strobe': True})
        # bank reordered: names still resolve
        back2, _ = L.row_to_state(h, row, list(reversed(LABELS)), 2)
        self.assertEqual(back2['layers'][0]['source'], list(reversed(LABELS)).index('LK_spectrum_glass'))

    def test_unknown_source_is_error_not_crash(self):
        h = L.preset_header(1)
        st, errs = L.row_to_state(h, ['x', 'NOPE', '1'], LABELS, 1)
        self.assertEqual(len(errs), 1)
        self.assertNotIn('source', st['layers'][0])
        self.assertEqual(st['layers'][0]['opacity'], 1.0)

    def test_fade_plan_and_values(self):
        cur = {'layers': [lay(0, 1), lay(1, 0)], 'Master': 1.0, 'Masterfx': False, 'fx': {}}
        tgt = {'layers': [{'opacity': 0.0}, {'source': 2, 'opacity': 1.0}], 'Master': 0.5, 'fx': {'trail': True}}
        disc, fade = L.fade_plan(cur, tgt, 2)
        self.assertEqual(disc, {'L2source': 2, 'Fxtrail': True})
        self.assertEqual(fade, {'L1opacity': (1.0, 0.0), 'L2opacity': (0.0, 1.0), 'Master': (1.0, 0.5)})
        mid = L.fade_values(fade, 1.0, 2.0)
        self.assertAlmostEqual(mid['L1opacity'] + mid['L2opacity'], 1.0)
        self.assertAlmostEqual(mid['Master'], 0.75)
        self.assertEqual(L.fade_values(fade, 0.0, 0.0)['L2opacity'], 1.0)

    def test_default_presets_skip_missing(self):
        rows = L.default_presets(LABELS, 4)
        names = [r[0] for r in rows]
        self.assertIn('glass_particles', names)
        self.assertEqual(len(rows[0]), len(L.preset_header(4)))
        self.assertEqual(names, ['blackout', 'test', 'glass', 'glass_particles', 'fluid_cloud', 'room_palette'])
        self.assertNotIn('glass', [r[0] for r in L.default_presets(['TP_test_pattern'], 4)])


class Hooks(unittest.TestCase):
    def test_demo_cues_resolve_indices(self):
        rows = L.demo_cues(LABELS)
        self.assertEqual(rows[0][:3], ['id', 'num', 'name'])
        src = [r for r in rows[1:] if r[9].endswith(':L2source')][0]
        self.assertEqual(src[10], str(LABELS.index('LK_spectrum_glass')))
        self.assertTrue(all(r[8] == 'par' and r[9].startswith('/project1/show_rig:') for r in rows[1:]))

    def test_midi_binds_unique(self):
        b = L.midi_binds(6)
        self.assertEqual(len(set(m['id'] for m in b)), len(b))
        keys = [(m['kind'], m['number']) for m in b]
        self.assertEqual(len(set(keys)), len(keys))
        self.assertTrue(all(m['target'] == '/project1/show_rig' for m in b))


if __name__ == '__main__':
    unittest.main()
