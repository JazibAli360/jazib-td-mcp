"""Offline tests for FX_destroy module 'disintegrate' (builders/fx_destroy_disintegrate.py + _logic.py). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_destroy_disintegrate.py'
GLSL is compiled with glslc (OpenGL target) against TD stubs: a syntax/type check, not a TD compile (that is live)."""
import math
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
sys.path.insert(0, B)
import fx_destroy_disintegrate_logic as L  # noqa: E402

RACK = {}
exec(open(os.path.join(B, 'fx_destroy.py')).read(), RACK)
NS = dict(RACK)
exec(open(os.path.join(B, 'fx_destroy_disintegrate.py')).read(), NS)
W, H = 1080, 1920


def defaults():
    d = {}
    for _page, pars in NS['PAGES']:
        for name, style, default, _o in pars:
            if style == 'RGB':
                for k, v in zip('rgb', default):
                    d[name + k] = v
            elif style == 'Menu':
                d[name] = 0
            elif style not in ('Pulse', 'TOP', 'COMP', 'CHOP'):
                d[name] = float(default) if style == 'Float' else int(default)
    return d


class Spec(unittest.TestCase):
    def test_pages_presets(self):
        names = {}
        for _p, pars in NS['PAGES']:
            for name, style, default, o in pars:
                if style == 'RGB':
                    for k in 'rgb':
                        names[name + k] = ('Float', o)
                else:
                    names[name] = (style, o)
        self.assertEqual(NS['PAGES'][0][1][0][0], 'Amount')
        for k in ('Trigger', 'Reset', 'Beatchop', 'Effector', 'Hittime', 'Resettime', 'Masksource', 'Return',
                  'Front', 'Grain', 'Push'):
            self.assertIn(k, names)
        self.assertEqual(len(NS['PRESETS']), 5)
        d = defaults()
        for _s, _n, vals in NS['PRESETS']:
            self.assertEqual(set(vals) - set(names), set())
            own = [n for n in d if n not in ('Progress', 'Masklevel', 'Masksoft', 'Maskinvert', 'Pointu', 'Pointv',
                                             'Resettime', 'Hittime', 'Masksource')]
            self.assertEqual(set(own) - set(vals), set(), 'presets must be full states (T-124)')
            for k, v in vals.items():
                if names[k][0] == 'Menu':
                    self.assertTrue(0 <= v < len(names[k][1]['names']), k)
        for pg in NS['PANEL_PAGES']:
            self.assertIn(pg, [p for p, _ in NS['PAGES']])
        for k, v in L.MENUS.items():
            if k in names and names[k][0] == 'Menu':
                self.assertEqual(names[k][1]['names'], v, k)

    def test_page_defaults_equal_base(self):
        d = defaults()
        for k, v in NS['BASE'].items():
            self.assertAlmostEqual(float(d[k]), float(v), msg=k)

    def test_reuses_explode_latch(self):
        tx = NS['shader_texts'](RACK['GLSL_LIB'], RACK['mask_glsl'](1))
        X = dict(RACK)
        exec(open(os.path.join(B, 'fx_destroy_explode.py')).read(), X)
        self.assertEqual(tx['hit'], X['HIT'])


class Front(unittest.TestCase):
    def test_dir_wipe_left_to_right(self):
        P = dict(defaults(), Front=0, Frontangle=0.0, Roughness=0.0, Jitter=0.0, Sweep=2.0)
        tb, f = L.grains(P, W, H, (540, 960))
        self.assertTrue(np.all(np.diff(tb, axis=1) >= 0))
        self.assertAlmostEqual(float(tb.min()), 2.0 / W, places=3)
        self.assertLessEqual(float(tb.max()), 2.0)

    def test_point_out_and_in(self):
        P = dict(defaults(), Front=1, Roughness=0.0, Jitter=0.0)
        tb, _ = L.grains(P, W, H, (540, 960))
        gh, gw = tb.shape
        self.assertLess(tb[gh // 2, gw // 2], tb[0, 0])
        P['Front'] = 2
        tb2, _ = L.grains(P, W, H, (540, 960))
        self.assertGreater(tb2[gh // 2, gw // 2], tb2[0, 0])

    def test_range_jitter_reverse_mask(self):
        P = dict(defaults(), Roughness=0.7, Jitter=0.5, Sweep=3.0, Reverse=1, Grain=4)
        tb, f = L.grains(P, W, H, (540, 960))
        self.assertTrue(np.all((tb >= 0) & (tb <= 3.0)))
        self.assertGreater(f.std(), 0.1)
        m = np.zeros(tb.shape)
        m[:, : tb.shape[1] // 2] = 1
        tb2, _ = L.grains(P, W, H, (540, 960), mask=m)
        self.assertTrue(np.all(tb2[:, tb.shape[1] // 2:] == -1))

    def test_noise_front_spans(self):
        P = dict(defaults(), Front=3, Roughness=0.0, Jitter=0.0)
        _tb, f = L.grains(P, W, H, (0, 0))
        self.assertLess(np.percentile(f, 5), 0.3)
        self.assertGreater(np.percentile(f, 95), 0.7)


class Time(unittest.TestCase):
    def test_away_return(self):
        P = dict(defaults(), Hold=1.0, Return=2.0)
        tb = np.array([0.5, 1.0, -1.0])
        self.assertTrue(np.all(L.flight(P, 0.4, tb) == 0))
        np.testing.assert_allclose(L.flight(P, 1.2, tb), [0.7, 0.2, 0.0])
        self.assertTrue(np.all(L.flight(P, 1.0 + 3.0 + 1e-6, tb) == 0))      # all home after Sweep + Hold + Return
        mid = L.flight(P, 0.5 + 2.0, tb)[0]                                    # half-way back retraces to Hold / 2
        self.assertAlmostEqual(mid, 0.5)

    def test_gone_without_return_and_assemble(self):
        P = dict(defaults(), Return=0.0)
        self.assertGreater(L.flight(P, 50.0, np.array([0.3]))[0], 0)
        self.assertIsNone(L.end_time(P))
        P = dict(defaults(), Mode=1, Duration=1.5)
        tb = np.array([0.0, 2.0])
        np.testing.assert_allclose(L.flight(P, 0.0, tb), [1.5, 1.5])
        np.testing.assert_allclose(L.flight(P, 3.5, tb), [0.0, 0.0])
        np.testing.assert_allclose(L.flight(P, 3.0, tb), [0.0, 0.5])

    def test_manual_age(self):
        P = dict(defaults(), Drive=1, Progress=0.25, Duration=4.0)
        self.assertEqual(L.age_of(P), (True, 1.0))
        P['Progress'] = 0.0
        self.assertFalse(L.age_of(P)[0])


class Motion(unittest.TestCase):
    def _run(self, **kw):
        P = dict(defaults(), Grain=8, **kw)
        tb, _ = L.grains(P, W, H, (540, 960))
        return P, tb, L.particles(P, W, H, 3.0, (540.0, 960.0), tb)

    def test_wind_only_moves_along_wind(self):
        P, tb, pr = self._run(Turbulence=0.0, Cone=0.0, Spread=0.0, Gravity=0.0, Blast=0.0, Windangle=90.0,
                              Windspeed=100.0, Life=0.0)
        on = pr['on']
        self.assertGreater(on.sum(), 0)
        _gw, _gh, _gx, _gy, rx, ry = L.grid(P, W, H)
        np.testing.assert_allclose(pr['x'][on], rx[on], atol=1e-6)
        np.testing.assert_allclose(pr['y'][on] - ry[on], 100.0 * pr['tau'][on], atol=1e-6)

    def test_amount_zero_rest_and_lift(self):
        _P, _tb, pr = self._run(Amount=0.0)
        self.assertEqual(int(pr['on'].sum()), 0)
        P, tb, pr = self._run(Turbulence=0.0, Windspeed=0.0, Blast=0.0, Gravity=-200.0, Life=0.0)
        _gw, _gh, _gx, _gy, _rx, ry = L.grid(P, W, H)
        on = pr['on']
        self.assertTrue(np.all(pr['y'][on] > ry[on]))

    def test_blast_outward_and_coverage(self):
        P, tb, pr = self._run(Turbulence=0.0, Windspeed=0.0, Gravity=0.0, Blast=800.0, Front=1, Life=0.0)
        _gw, _gh, _gx, _gy, rx, ry = L.grid(P, W, H)
        on = pr['on']
        d0 = np.hypot(rx[on] - 540, ry[on] - 960)
        d1 = np.hypot(pr['x'][on] - 540, pr['y'][on] - 960)
        self.assertTrue(np.all(d1 >= d0 - 1e-6))
        cov = L.dust_alpha(P, W, H, pr)
        self.assertGreater(cov.mean(), 0.01)

    def test_remnant_matches_flight(self):
        P = dict(defaults(), Grain=3)
        tb, _ = L.grains(P, W, H, (540, 960))
        rem = L.remnant(P, W, H, 1.2, tb)
        self.assertEqual(rem.shape, (H, W))
        self.assertTrue(0.05 < rem.mean() < 0.95)


TD_STUB = """#version 460
uniform sampler2D sTD2DInputs[4];
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
"""


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    def test_shaders(self):
        tx = NS['shader_texts'](RACK['GLSL_LIB'], RACK['mask_glsl'](1))
        for k in ('hit', 'grains', 'dust', 'fx'):
            self.assertTrue(all(ord(ch) < 128 for ch in tx[k]), k)
            with tempfile.TemporaryDirectory() as d:
                p = os.path.join(d, 's.comp')
                with open(p, 'w') as fh:
                    fh.write(TD_STUB + tx[k])
                r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                    '-o', os.devnull, p], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, '%s\n%s' % (k, r.stderr[:3000]))


class FakeBuild(unittest.TestCase):
    def test_expected_numbers_run(self):
        rows = L.expected_numbers(W=270, H=480)
        self.assertGreaterEqual(len(rows), 4)
        for _slot, _name, row in rows:
            self.assertTrue(all(0 <= v <= 1 for _t, v in row))


if __name__ == '__main__':
    unittest.main()
