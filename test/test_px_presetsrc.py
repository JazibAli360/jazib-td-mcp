"""Offline tests for PX Presetsource (28 Oct, user bug: "changing a preset also changes the pointcloud or splat file
that i have imported"). With Presetsource Off (default) Recall / Morphto / setlist keep the Source page.
docs/builds/px.md "28 Oct: Presetsource". Run: python3 -I -m unittest discover -s test -p 'test_px_presetsrc.py'"""
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


def _func(src, name):
    m = re.search(r'^def %s\(.*?(?=^def |\Z)' % re.escape(name), src, re.S | re.M)
    return m.group(0) if m else ''


class PresetsourceLogic(unittest.TestCase):
    def test_par_spec_default_off_on_presets_page(self):
        s = _spec('Presets', 'Presetsource')
        self.assertIsNotNone(s)
        self.assertEqual(s[1], 'Toggle')
        self.assertIs(s[2], False)
        self.assertEqual(s[3]['label'], 'Presets change the source')

    def test_never_stored(self):
        self.assertIn('Presetsource', L.NOSNAP)

    def test_source_names_cover_the_source_page(self):
        n = L.source_par_names()
        for k in ('Afile', 'Bfile', 'Amode', 'Bmode', 'Agen', 'Bgen', 'Ascale', 'Morph', 'Quality', 'Count', 'Clip',
                  'Opacitymin', 'Actorfile', 'Actorseq', 'Pool', 'Pointstop', 'Imagefile', 'Camsource', 'Camcomp',
                  'Aoffsetx', 'Aoffsety', 'Aoffsetz', 'Acolourr', 'Acolourg', 'Acolourb', 'Actorup'):
            self.assertIn(k, n)
        for pg, pars in L.CORE_PAGES:
            if pg == 'Source':
                for spec in pars:
                    if spec[1] not in ('XYZ', 'RGB'):
                        self.assertIn(spec[0], n)

    def test_source_names_leave_the_look_alone(self):
        n = L.source_par_names()
        for k in ('Exposure', 'Bright', 'Saturation', 'Bloom', 'Haze', 'Size', 'Camdist', 'Orbit', 'Morphtime',
                  'Presetname', 'Presetsource'):
            self.assertNotIn(k, n)

    def test_live_page_names_are_added(self):
        self.assertIn('Brandnewsource', L.source_par_names(['Brandnewsource']))

    def test_keep_source(self):
        self.assertTrue(L.keep_source(False))
        self.assertTrue(L.keep_source(0))
        self.assertTrue(L.keep_source(None))          # a PX without the par keeps the source too
        self.assertFalse(L.keep_source(True))
        self.assertFalse(L.keep_source(1))

    def test_strip_source(self):
        vals = {'Afile': '/x/scan.ply', 'Amode': 'file', 'Count': 9000, 'Morph': 0.4, 'Exposure': 0.3,
                'M1amount': 0.5, 'Camsource': 'external'}
        kept, gone = L.strip_source(vals, L.source_par_names())
        self.assertEqual(kept, {'Exposure': 0.3, 'M1amount': 0.5})
        self.assertEqual(gone, ['Afile', 'Amode', 'Camsource', 'Count', 'Morph'])
        self.assertEqual(vals['Afile'], '/x/scan.ply')     # input untouched
        self.assertEqual(L.strip_source({'Exposure': 1}, L.source_par_names()), ({'Exposure': 1}, []))

    def test_extra_covers_px_rt_load_pars(self):
        src = _rd('px_rt.py')
        m = re.search(r'^LOAD_PARS = \((.*?)\)', src, re.S | re.M)
        load = set(re.findall(r"'(\w+)'", m.group(1)))
        self.assertTrue(load <= set(L.SOURCE_EXTRA), load - set(L.SOURCE_EXTRA))

    def test_builtin_looks_apply_to_any_source(self):
        """Every built-in look stripped of its source still has values to apply (it is a look, not a scene)."""
        names = L.source_par_names()
        scenes = 0
        for name in L.BUILTIN:
            snap = L.builtin_preset(name)
            kept, gone = L.strip_source(snap['values'], names)
            self.assertFalse(set(kept) & names, name)
            self.assertTrue(kept, name)
            if L.BUILTIN[name].get('scene'):
                scenes += 1
                self.assertIn('Afile', gone, name)         # a whole-scene look loses its splat file, keeps its look
        self.assertGreater(scenes, 0)

    def test_summary_note(self):
        self.assertEqual(L.preset_summary('KANDA', {'source_kept': ['Afile']}),
                         'recalled KANDA: source kept (Presetsource off)')
        self.assertEqual(L.preset_summary('KANDA', {}), 'recalled KANDA')


class PresetsourceRuntime(unittest.TestCase):
    """Text checks of builders/px_rt.py (TD runtime) and the upgrade in builders/px.py."""

    def test_load_checked_strips(self):
        f = _func(_rd('px_rt.py'), '_load_checked')
        self.assertIn('_keeps_source(c)', f)
        self.assertIn('strip_source', f)
        self.assertIn("notes['source_kept']", f)

    def test_recall_morph_setlist_go_through_load_checked(self):
        src = _rd('px_rt.py')
        self.assertIn('_load_checked(c, name)', _func(src, 'recall'))
        self.assertIn('_load_checked(c, name)', _func(src, 'morph_to'))
        go = _func(src, 'setlist_go')
        self.assertIn('recall(c, nm)', go)
        self.assertIn('morph_to(c, nm', go)
        self.assertIn('SOURCE_KEPT_NOTE', go)
        self.assertIn('setlist_go(c, k)', _func(src, 'setlist_step'))

    def test_morph_start_never_writes_the_source(self):
        f = _func(_rd('px_rt.py'), '_morph_start')
        self.assertLess(f.index('strip_source'), f.index("S(c)['morph'] = {"))

    def test_kept_source_is_not_a_px_notes_issue(self):
        f = _func(_rd('px_rt.py'), '_report')
        self.assertIn("k != 'source_kept'", f)

    def test_store_still_records_the_source(self):
        f = _func(_rd('px_rt.py'), 'store')
        self.assertNotIn('strip_source', f)
        self.assertNotIn('_keeps_source', f)

    def test_upgrade_is_staged_and_ui_safe(self):
        src = _rd('px.py')
        up = _func(src, 'presetsrc_upgrade')
        self.assertIn('_ui_safe(c)', up)
        self.assertIn("pn.allowCooking = False", up)
        self.assertIn('_presets_sig(c)', up)
        step = _func(src, '_presetsrc_step')
        self.assertIn('px_pending', step)
        self.assertIn('_upg_done(c, st)', step)
        self.assertIn('delay=UPGC_GAP', _func(src, '_upgS_later'))
        self.assertIn("pg[0] == 'Presets'", _func(src, '_presetsrc_pars'))
        self.assertIn('_watchers(c, False)', _func(src, '_presetsrc_pars'))
        self.assertIn('def presetsrc_result(', src)

    def test_compile_status_keeps_the_note(self):
        src = _rd('px_rt.py')
        self.assertIn('SOURCE_KEPT_NOTE', _func(src, '_solo_tail'))
        self.assertIn("S(c)['src_kept_frame'] = absTime.frame", _func(src, '_load_checked'))

    def test_ascii(self):
        for f in ('px_rt.py', 'px_logic.py', 'px.py'):
            _rd(f).encode('ascii')


if __name__ == '__main__':
    unittest.main()
