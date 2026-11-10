"""Offline tests for FX_glitch module 'chroma' (builders/fx_glitch_chroma.py), Split time mirror
builders/fx_glitch_chroma_logic.py. Run: python3 -I -m unittest discover -s test -p 'test_fx_glitch_chroma.py'"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import numpy as np  # noqa: E402
import fx_glitch_chroma_logic as L  # noqa: E402

NS = K.load_module('chroma')


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'chroma')
        self.assertEqual(pars['Split'][2]['names'][:3], ['rgb', 'prism', 'spectral'])   # old indices kept
        self.assertEqual(pars['Split'][2]['names'][3], 'time')
        self.assertEqual(pars['Order'][2]['names'], L.ORDERS)
        K.check_uniforms(self, NS['uniforms'](), NS['SHADER'], pars)

    def test_presets_full_state(self):
        names = set(n for _pg, pl in NS['PAGES'] for n, s, _d, _o in pl if s not in ('CHOP', 'Str'))
        for _slot, pname, vals in NS['PRESETS']:
            self.assertEqual(set(vals), names, pname)

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_glitch_chroma.py'))
        K.check_td_rules(self, K.source('fx_glitch_chroma_logic.py'))

    def test_order_expressions(self):
        u = dict(NS['uniforms']())['uG']
        for i, o in enumerate(L.ORDERS):
            class Par:
                def eval(s): return o
            env = {'parent': lambda: type('X', (), {'par': type('Y', (), {'Order': Par()})()})()}
            self.assertEqual([eval(e, env) for e in u[:3]], L.slots(i))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_all(self):
        for n in ('SHADER', 'MAPK', 'STAMP_RING'):
            ok, err = K.glslc(NS[n])
            self.assertTrue(ok, n + err)


class TimeSplit(unittest.TestCase):
    def test_offsets(self):
        self.assertEqual(L.offsets(3, 'rgb', 100), [0, 3, 6])
        self.assertEqual(L.offsets(3, 'bgr', 100), [6, 3, 0])
        self.assertEqual(L.offsets(3, 'rgb', 4), [0, 3, 4])          # clamped to what the ring holds
        self.assertEqual(L.offsets(3, 'rgb', 0), [0, 0, 0])

    def test_reference_channels(self):
        fr = [np.full((2, 2, 4), k, dtype=float) for k in range(20)]
        out = L.reference(fr, 3, 'rgb', 50)
        self.assertEqual(list(out[0, 0, :3]), [19, 16, 13])
        self.assertEqual(L.decode(19, out[0, 0, :3]), [0, 3, 6])

    def test_map_encoding_matches_ring(self):
        # MAPK writes m = 1 - (off + 1) / Depth with Depth = 2 Delay + 1 (T-122, as fx_time_ring)
        self.assertIn('1.0 - (off + 1.0) / (D + 1.0)', NS['MAPK'])
        self.assertIn('2 * int(parent().par.Delay.eval()) + 1', NS['CDEPTH'])


if __name__ == '__main__':
    unittest.main()
