"""Offline tests for the perf wave 27 Oct (b3; docs/builds/PERF_FINAL_27OCT.md "Perf wave 27 Oct (b3)"): cheaper
defaults with the full quality one click away. No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_perf27_b3.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDERS = os.path.join(os.path.dirname(HERE), 'builders')
sys.path.insert(0, BUILDERS)
import px_logic as L  # noqa: E402


def _rd(name):
    with open(os.path.join(BUILDERS, name)) as f:
        return f.read()


def _core(page, name):
    for pg, pars in L.CORE_PAGES:
        if pg == page:
            for p in pars:
                if p[0] == name:
                    return p
    return None


class PXSplatDefaults(unittest.TestCase):
    def test_splataa_menu(self):
        p = _core('Look', 'Splataa')
        self.assertIsNotNone(p)
        self.assertEqual(p[1], 'Menu')
        self.assertEqual(p[2], 'aa1')
        self.assertIn('aa4', p[3]['names'])                 # full quality one click away
        self.assertIn('Splataa', L.LOOK_SCENE_KEYS)          # a look recall keeps the user's choice

    def test_sorteveryn_default(self):
        self.assertEqual(_core('Look', 'Sorteveryn')[2], 6)
        self.assertIn("int(raw.get('Sorteveryn', 6))", _rd('px_rt.py'))

    def test_srender_reads_splataa(self):
        src = _rd('px.py')
        self.assertIn("_expr(sr.par.antialias, SPLAT_AA_E)", src)
        self.assertIn("def perf27_upgrade(", src)

    def test_sort_due_every_n(self):
        # moving centres, camera still: due only after N engine frames
        self.assertFalse(L.sort_due('auto', 105, 100, 6, True, False, since_s=1.0, max_hz=20.0))
        self.assertTrue(L.sort_due('auto', 106, 100, 6, True, False, since_s=1.0, max_hz=20.0))
        # camera gate still sorts at once (within the Sortmaxhz cap)
        self.assertTrue(L.sort_due('auto', 101, 100, 6, True, True, since_s=1.0, max_hz=20.0))


if __name__ == '__main__':
    unittest.main()
