"""Offline tests for FX_stylise rack + module 'outline' (builders/fx_stylise.py, fx_stylise_outline.py,
fx_stylise_outline_logic.py, fx_stylise_pal.py). No TD.
Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_stylise_outline.py'
glslc compiles every pass against stubs of TD's compute globals (syntax/type check, NOT a TD compile: LIVE CHECK 1 in
docs/builds/fx_stylise.md)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_time_testkit as K  # noqa: E402
import fx_stylise_outline_logic as L  # noqa: E402
import numpy as np  # noqa: E402


def load(module):
    ns = {'HERE': K.BUILDERS}
    path = os.path.join(K.BUILDERS, 'fx_stylise_%s.py' % module)
    with open(path) as fh:
        exec(compile(fh.read(), path, 'exec'), ns)
    return ns


NS = load('outline')


def pars_of(ns):
    out = {}
    for _pg, pl in ns['PAGES']:
        for n, s, d, o in pl:
            out[n] = o['names'].index(d) if s == 'Menu' else (int(d) if s == 'Toggle' else d)
    return out


class Rack(unittest.TestCase):
    def test_rack_reuses_glitch_rack(self):
        src = K.source('fx_stylise.py')
        self.assertIn("exec(_fh.read(), globals())", src)
        self.assertIn("'fx_glitch.py'", src)
        self.assertNotIn('def rewire', src)                  # no copy of the rack code
        K.check_td_rules(self, src)
        ns = {}
        exec(compile(src.replace("with open(os.path.join(HERE, 'fx_glitch.py')) as _fh:\n    exec(_fh.read(), globals())",
                                 "exec(open(os.path.join(HERE, 'fx_glitch.py')).read(), globals())"),
                     'fx_stylise.py', 'exec'), ns)
        self.assertEqual(ns['NAME'], 'FX_stylise')
        self.assertTrue(ns['module_file']('outline').endswith('fx_stylise_outline.py'))
        self.assertEqual(ns['chain_edges'](['outline1'])[-1], ('out1', 0, 'panic'))
        self.assertIn('pas', ns['H'])
        self.assertIn('void main()', ns['glsl_text']('gen_sim_vor_jfa'))

    def test_pal_helper(self):
        src = K.source('fx_stylise_pal.py')
        K.check_td_rules(self, src)
        ns = {'HERE': K.BUILDERS}
        exec(compile(src, 'fx_stylise_pal.py', 'exec'), ns)
        self.assertNotIn('image', ns['PAL_SOURCE_NAMES'])
        page = ns['pal_page']()
        self.assertEqual(page[0], 'Palette')

        class Par:
            def __init__(self, v):
                self.v = v

            def eval(self):
                return self.v

        class M:
            pass
        m = M()
        m.par = M()
        for k, v in {'Palsource': 'custom', 'Palmode': 'gradient', 'Palreverse': False,
                     'Palstops': '#ff0000 #0000ff', 'Palfile': ''}.items():
            setattr(m.par, k, Par(v))
        import palette_map_logic as Pm
        st = ns['stops_of'](m, Pm)
        self.assertEqual(len(st), 2)
        self.assertAlmostEqual(st[0][0], 1.0)
        self.assertAlmostEqual(st[1][2], 1.0)
        m.par.Palsource = Par('fire')
        self.assertGreaterEqual(len(ns['stops_of'](m, Pm)), 3)
        # callback text has the same stop logic + count(); pure ASCII
        ns['PAL_CB'].encode('ascii')
        self.assertIn('def count(m)', ns['PAL_CB'])


class Contract(unittest.TestCase):
    def test_template(self):
        pars = K.check_module_contract(self, NS, 'outline')
        self.assertEqual(pars['Mode'][2]['names'], L.MODES)

    def test_uniforms_match_shaders(self):
        pars = K.check_module_contract(self, NS, 'outline')
        U = NS['uniforms']()
        texts = dict(NS['SHADERS'])
        texts['jfa'] = open(os.path.join(K.BUILDERS, 'glsl', 'gen_sim_vor_jfa.glsl')).read()
        self.assertEqual(set(U), set(texts))
        for name, text in texts.items():
            decl = [u for u in K.declared_uniforms(text) if u != 'uPalCtl']
            self.assertEqual([u for u, _ in U[name]], decl, name)
            K.check_uniforms(self, U[name], '\n'.join('uniform vec4 %s;' % u for u in decl), pars)

    def test_rules(self):
        K.check_td_rules(self, K.source('fx_stylise_outline.py'))
        K.source('fx_stylise_outline_logic.py').encode('ascii')
        for name, text in NS['SHADERS'].items():
            self.assertNotIn('sTD2DInputs[2]', text, name)

    def test_presets_full_state(self):
        pars = K.check_module_contract(self, NS, 'outline')
        keys = set(n for n, (s, _d, _o) in pars.items() if s != 'Str')
        for _s, name, vals in NS['PRESETS']:
            self.assertEqual(set(vals), keys, name)            # every non-string par: no inheritance (T-124 (1))
            for k, v in vals.items():
                if pars[k][0] in ('Menu', 'Int', 'Toggle'):
                    self.assertIsInstance(v, int, (name, k))
                else:
                    self.assertIsInstance(v, float, (name, k))


@unittest.skipUnless(K.HAVE_GLSLC, 'glslc not installed')
class Compile(unittest.TestCase):
    def test_every_pass(self):
        texts = dict(NS['SHADERS'])
        texts['jfa'] = open(os.path.join(K.BUILDERS, 'glsl', 'gen_sim_vor_jfa.glsl')).read()
        import fx_stylise_testkit as T
        for name, text in texts.items():
            self.assertTrue(all(ord(ch) < 128 for ch in text), name)
            ok, err = T.glslc_n(text, NS['NIN'][name])
            self.assertTrue(ok, name + ': ' + err)


class Distance(unittest.TestCase):
    def test_seeds_on_the_edge(self):
        im = L.disc_matte(96, 64, 40.3, 30.7, 18.0)
        for D in (1, 2):
            sm = L.seed_map(im, D)
            has = sm[..., 2] > 0
            self.assertGreater(has.sum(), 20)
            r = np.hypot(sm[has, 0] * D - 40.3, sm[has, 1] * D - 30.7)
            self.assertLess(np.abs(r - 18.0).max(), 0.75 * D + 0.5, D)   # box-mean crossings sit on the circle

    def test_jfa_vs_brute(self):
        """LIVE CHECK target: JFA distance vs brute force max err <= 1 px at half res."""
        rng = np.random.default_rng(3)
        for trial in range(3):
            im = np.zeros((96, 80, 4), np.float32)
            im[..., 3] = 1
            for _ in range(4):
                cx, cy, r = rng.uniform(5, 75), rng.uniform(5, 90), rng.uniform(4, 20)
                im[..., :3] = np.maximum(im[..., :3], L.disc_matte(80, 96, cx, cy, r)[..., :3])
            sm = L.seed_map(im, 2)
            e = np.abs(L.jfa_dist(L.jfa(sm, 1)) - L.brute(sm))
            self.assertLessEqual(float(e[np.isfinite(e)].max()), 1.0, trial)

    def test_signed_distance_of_a_disc(self):
        W, H, cx, cy, r = 128, 96, 60.2, 47.6, 25.0
        im = L.disc_matte(W, H, cx, cy, r)
        P = pars_of(NS)
        P.update(Res=1)
        _o, sd, _j = L.reference(im, P)
        py, px = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
        true = np.hypot(px - cx, py - cy) - r
        near = np.abs(true) < 30
        err = np.abs(sd - true)[near]
        self.assertLess(float(err.max()), 2.1)                   # seeds are one per Res texel along the edge
        self.assertLess(float(err.mean()), 0.2)
        self.assertTrue(np.all(sd[np.hypot(px - cx, py - cy) < r - 2] < 0))

    def test_range_limited_passes(self):
        P = pars_of(NS)
        self.assertEqual(L.jfa_passes_for(540, 960, L.look_range(P), 2), 4)        # outline 6 px: 4 (+1) not 10
        self.assertEqual(L.jfa_passes_for(540, 960, L.look_range(dict(P, Mode=4)), 2), 10)   # distance view: full
        self.assertEqual(L.jfa_passes_for(540, 960, L.look_range(dict(P, Mode=2, Bands=0)), 2), 10)
        # within the reach (2^Pm - 1 texels) the limited JFA still matches brute force
        im = L.disc_matte(160, 120, 70.3, 61.2, 30.0)
        sm = L.seed_map(im, 2)
        for Pm in (3, 4, 5):
            bf = L.brute(sm)
            e = np.abs(L.jfa_dist(L.jfa_pm(sm, Pm, 1)) - bf)[bf <= 2 ** Pm - 1]
            self.assertLessEqual(float(e.max()), 1.0, Pm)

    def test_no_edge_is_far(self):
        im = np.ones((32, 32, 4), np.float32)
        sm = L.seed_map(im, 2)
        self.assertEqual(int((sm[..., 2] > 0).sum()), 0)


class Look(unittest.TestCase):
    def setUp(self):
        self.im = L.disc_matte(128, 96, 60.2, 47.6, 25.0)
        self.P = pars_of(NS)

    def test_amount_zero_is_input(self):
        P = dict(self.P, Amount=0.0)
        out, _sd, _j = L.reference(self.im, P)
        self.assertEqual(float(np.abs(out - self.im).max()), 0.0)

    def test_outline_ring(self):
        P = dict(self.P, Mode=0, Width=6.0, Offset=4.0, Soft=1.0, Intensity=1.0, Colr=1.0, Colg=0.0, Colb=0.0)
        out, sd, _j = L.reference(self.im, P)
        on = np.abs(sd - 4.0) < 2.0
        off = np.abs(sd - 4.0) > 4.5
        self.assertGreater(float(out[on, 0].mean()), 0.95)
        self.assertLess(float(out[on, 1].max()), 0.05)
        self.assertEqual(float(np.abs(out[off] - self.im[off]).max()), 0.0)

    def test_contour_band_count(self):
        P = dict(self.P, Mode=2, Spacing=8.0, Bands=3, Fade=0.001, Width=2.0, Soft=0.5, Function=0, Back=2,
                 Inside=2, Intensity=1.0, Colr=1.0, Colg=1.0, Colb=1.0)
        out, sd, _j = L.reference(self.im, P)
        lit = out[..., 0] > 0.5
        # lines at u = 0, 8, 16 px outward (3 bands, the 4th at 24 faded out)
        for u in (0.0, 8.0, 16.0):
            self.assertTrue(np.any(lit & (np.abs(sd - u) < 0.6)), u)
        self.assertFalse(np.any(lit & (sd > 21)))             # the 4th line (24 px) is faded out
        self.assertFalse(np.any(lit & (sd < -1.5)))

    def test_transparent_back_is_premultiplied(self):
        P = dict(self.P, Mode=1, Back=3, Inside=3, Intensity=1.0, Glowgain=0.5, Colr=0.2, Colg=1.0, Colb=0.5)
        out, _sd, _j = L.reference(self.im, P)
        self.assertLessEqual(L.pm_check(out), 1e-6)
        P = dict(self.P, Mode=3, Width=28.0, Back=3, Intensity=1.0, Colr=1.0, Colg=1.0, Colb=1.0)
        out, sd, _j = L.reference(self.im, P)
        self.assertLessEqual(L.pm_check(out), 1e-6)
        self.assertEqual(float(out[sd > 40, 3].max()), 0.0)          # far outside the sticker: transparent
        self.assertGreater(float(out[(sd > 2) & (sd < 20), 3].min()), 0.99)


if __name__ == '__main__':
    unittest.main()
