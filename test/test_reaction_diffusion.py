"""Offline tests for builders/reaction_diffusion_logic.py + builders/glsl/rd_*.glsl + the builder text (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_reaction_diffusion.py'"""
import ast
import math
import os
import re
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDERS = os.path.join(os.path.dirname(HERE), 'builders')
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
import reaction_diffusion_logic as L  # noqa: E402


def prm(**kw):
    q = dict(L.REF_DEFAULTS)
    q.update(kw)
    return q


def eng(**kw):
    p = dict(L.ENGINE_DEFAULTS)
    p.update(kw)
    return p


class Hash(unittest.TestCase):
    def test_lowbias32_known(self):
        self.assertEqual(int(L.hash_u32(0)), 0)
        # independent scalar implementation of lowbias32
        def h(x):
            x &= 0xffffffff
            x ^= x >> 16
            x = (x * 0x7feb352d) & 0xffffffff
            x ^= x >> 15
            x = (x * 0x846ca68b) & 0xffffffff
            x ^= x >> 16
            return x
        for v in (1, 2, 12345, 0xdeadbeef, 0xffffffff):
            self.assertEqual(int(L.hash_u32(v)), h(v))

    def test_hash3_range_and_negative_ints(self):
        X, Y = np.meshgrid(np.arange(-50, 50), np.arange(-50, 50))
        v = L.hash3(X, Y, 7)
        self.assertGreaterEqual(v.min(), 0.0)
        self.assertLess(v.max(), 1.0)
        self.assertAlmostEqual(float(v.mean()), 0.5, delta=0.02)
        self.assertEqual(float(L.hash3(-1, 3, 7)), float(L.hash3(0xffffffff, 3, 7)))   # uint(int) wrap, like GLSL

    def test_vnoise_continuous(self):
        x = np.linspace(0, 4, 4001)
        n = L.vnoise(x, np.zeros_like(x) + 0.3, 2)
        self.assertLess(float(np.abs(np.diff(n)).max()), 0.01)
        self.assertTrue(((n >= 0) & (n < 1)).all())


class Presets(unittest.TestCase):
    def test_table(self):
        for name in ('coral', 'mitosis', 'worms', 'spots', 'waves'):
            self.assertIn(name, L.PRESET_NAMES)
        self.assertEqual(L.preset_fk('coral'), (0.0545, 0.062))
        self.assertEqual(L.preset_fk('mitosis'), (0.0367, 0.0649))
        self.assertEqual(L.preset_fk('custom', 0.01, 0.05), (0.01, 0.05))
        self.assertEqual(len(L.PRESET_NAMES), len(L.PRESET_LABELS))

    def test_pages_valid(self):
        names = set()
        for _, pars in L.PAGES:
            for n, style, default, o in pars:
                self.assertRegex(n, r'^[A-Z][a-z0-9]*$')
                self.assertNotIn(n, names)
                names.add(n)
                if style == 'Menu':
                    self.assertIn(default, o['names'])
                    self.assertEqual(len(o['names']), len(o['labels']))
        for n in ('Steps', 'Simh', 'Preseta', 'Presetb', 'Morph', 'Seedmode', 'Anisomode', 'Flowmode', 'Effectors',
                  'Palette', 'Colormode'):
            self.assertIn(n, names)


class Reference(unittest.TestCase):
    def test_rest_state_is_fixed_point(self):
        for kw in ({}, {'anisomode': 'angle', 'aniso': 1.0}, {'flowmode': 'drift', 'flowx': 0.3, 'flowy': -0.2},
                   {'flowmode': 'curl'}, {'edge': 1}, {'mapmode': 'pearson'}):
            p = prm(**kw)
            s = L.new_state(40, 30)
            for _ in range(20):
                s = L.rd_pass(s, p)
            self.assertEqual(float(np.abs(s[..., 0] - 1).max()), 0.0, kw)
            self.assertEqual(float(np.abs(s[..., 1]).max()), 0.0, kw)

    def test_coral_grows_bounded(self):
        s0 = L.run_fixed(steps=0, w=64, h=64)
        s1 = L.run_fixed(steps=800, w=64, h=64)
        self.assertGreater(L.stats(s1)['cover'], L.stats(s0)['cover'] * 2)
        self.assertGreaterEqual(float(s1[..., :2].min()), 0.0)
        self.assertLessEqual(float(s1[..., :2].max()), 1.0)

    def test_integer_stencil_equals_bilinear(self):
        s = L.run_fixed(steps=50, w=48, h=40)
        for edge in (0, 1):
            a = L.rd_pass(s, prm(edge=edge, fa=0.0545, ka=0.062))
            b = L.rd_pass(s, prm(edge=edge, fa=0.0545, ka=0.062, flowmode='drift', flowx=0.0, flowy=0.0))
            self.assertLess(float(np.abs(a - b).max()), 1e-12)

    def test_drift_moves_one_cell(self):
        s = L.new_state(16, 12)
        s[..., 0] = 0.0                                       # A = 0: no reaction, pure transport
        s[5, 3, 1] = 1.0
        p = prm(flowmode='drift', flowx=1.0, flowy=0.0, da=0.0, db=0.0, fa=0.0, ka=0.0, fb=0.0, kb=0.0, clamp=False)
        out = L.rd_pass(s, p)
        self.assertAlmostEqual(float(out[5, 4, 1]), 1.0, places=12)
        self.assertAlmostEqual(float(out[..., 1].sum()), 1.0, places=12)
        s[5, 15, 1], s[5, 3, 1] = 1.0, 0.0                    # wrap: the right edge comes back on the left
        out = L.rd_pass(s, p)
        self.assertAlmostEqual(float(out[5, 0, 1]), 1.0, places=12)

    def test_aniso_angle_zero_spreads_along_x_only(self):
        s = L.new_state(21, 21)
        s[..., 0] = 0.0
        s[10, 10, 1] = 1.0
        p = prm(anisomode='angle', aniso=1.0, anisoangle=0.0, da=0.0, db=1.0, fa=0.0, ka=0.0, fb=0.0, kb=0.0,
                clamp=False)
        out = L.rd_pass(s, p)
        B = out[..., 1]
        self.assertEqual(float(np.abs(B[9]).max()) + float(np.abs(B[11]).max()), 0.0)
        self.assertGreater(float(B[10, 9]), 0.0)
        self.assertAlmostEqual(float(B.sum()), 1.0, places=12)          # diffusion conserves mass

    def test_iso_mass_conserved_wrap(self):
        s = L.new_state(21, 21)
        s[..., 0] = 0.0
        s[3, 4, 1] = 1.0
        p = prm(da=0.0, db=0.5, fa=0.0, ka=0.0, fb=0.0, kb=0.0, clamp=False)
        out = L.rd_pass(s, p)
        self.assertAlmostEqual(float(out[..., 1].sum()), 1.0, places=12)
        self.assertAlmostEqual(float(out[3, 4, 1]), 0.5, places=12)      # 1 + Db * (-1) * dt
        self.assertAlmostEqual(float(out[3, 5, 1]), 0.1, places=12)      # edge 0.2 * Db
        self.assertAlmostEqual(float(out[4, 5, 1]), 0.025, places=12)    # diagonal 0.05 * Db

    def test_morph_lerps_fk(self):
        # one step from a uniform state: dB depends on f, k only (lap = 0)
        s = L.new_state(8, 8)
        s[..., 0], s[..., 1] = 0.5, 0.25
        def dB(m):
            o = L.rd_pass(s, prm(morph=m))
            return float(o[0, 0, 1] - 0.25)
        a, b, h = dB(0.0), dB(1.0), dB(0.5)
        self.assertAlmostEqual(h, 0.5 * (a + b), places=12)
        fb, kb = 0.0367, 0.0649
        self.assertAlmostEqual(b, 0.5 * 0.25 * 0.25 - (kb + fb) * 0.25, places=12)

    def test_pearson_map(self):
        s = L.new_state(10, 10)
        s[..., 0], s[..., 1] = 0.5, 0.25
        o = L.rd_pass(s, prm(mapmode='pearson', fmin=0.01, fmax=0.09, kmin=0.05, kmax=0.07))
        dA = o[..., 0] - 0.5
        # dA = -A B^2 + f (1 - A): grows with y (f), constant along x
        self.assertTrue((np.diff(dA, axis=0) > 0).all())
        self.assertLess(float(np.abs(np.diff(dA, axis=1)).max()), 1e-15)

    def test_solid_held(self):
        s = L.run_fixed(steps=10, w=32, h=32)
        maps = np.zeros((32, 32, 4))
        maps[10:20, 10:20, 0] = 1.0
        s = L.seed_pass(s, prm(), run=True, maps=maps)
        o = L.rd_pass(s, prm())
        self.assertTrue((o[10:20, 10:20, 0] == 1).all() and (o[10:20, 10:20, 1] == 0).all())


class Seed(unittest.TestCase):
    def test_patterns(self):
        w, h = 90, 160
        for mode in L.SEEDMODES:
            B = L.seed_pattern(w, h, prm(seedmode=mode), img=np.full((h, w), 0.4))
            if mode == 'clear':
                self.assertEqual(float(B.sum()), 0.0)
            elif mode in ('image', 'text'):
                self.assertAlmostEqual(float(B.mean()), 0.4)
            else:
                self.assertGreater(float(B.sum()), 0.0, mode)
        c = L.seed_pattern(w, h, prm(seedmode='center', seedsize=0.05))
        self.assertAlmostEqual(float(c.sum()), (0.1 * h) ** 2, delta=0.1 * h * 4)
        a = L.seed_pattern(w, h, prm(seedmode='spots', seed=3))
        b = L.seed_pattern(w, h, prm(seedmode='spots', seed=3))
        d = L.seed_pattern(w, h, prm(seedmode='spots', seed=4))
        self.assertTrue((a == b).all())
        self.assertFalse((a == d).all())

    def test_rows_inject_erase_morph(self):
        s = L.new_state(64, 64)
        r = L.row(0.5, 0.5, 0.1, 1.0, 0.7, 2)                 # hard disc, full inject, morph 0.7
        o = L.seed_pass(s, prm(), rows=[r])
        self.assertAlmostEqual(float(o[32, 32, 1]), 1.0)
        self.assertAlmostEqual(float(o[32, 32, 2]), 0.7)
        self.assertEqual(float(o[0, 0, 1]), 0.0)
        e = L.seed_pass(o, prm(), rows=[L.row(0.5, 0.5, 0.1, -1.0, 0.0, 2)])
        self.assertEqual(float(e[32, 32, 1]), 0.0)
        self.assertEqual(float(e[32, 32, 0]), 1.0)
        self.assertAlmostEqual(float(e[32, 32, 2]), 0.0)       # morphdecay 0: no memory
        m = L.seed_pass(o, prm(morphdecay=0.5), rows=[])
        self.assertAlmostEqual(float(m[32, 32, 2]), 0.35)

    def test_paused_copies(self):
        s = L.run_fixed(steps=5, w=16, h=16)
        o = L.seed_pass(s, prm(), run=False, rows=[L.row(0.5, 0.5, 0.2, 1.0)])
        self.assertTrue((o == s).all())


class Engine(unittest.TestCase):
    def test_first_frame_resets_and_steps(self):
        st, o, rows = L.engine_step(None, 10.0, eng(steps=12))
        self.assertEqual(o['reset'], 1.0)
        self.assertEqual(o['nsteps'], 12.0)
        st, o, _ = L.engine_step(st, 10.02, eng(steps=12))
        self.assertEqual((o['reset'], o['steps']), (0.0, 24.0))

    def test_pause_step_stopat(self):
        st, o, _ = L.engine_step(None, 0.0, eng(steps=10, stopat=25))
        st, o, _ = L.engine_step(st, 0.1, eng(steps=10, stopat=25))
        st, o, _ = L.engine_step(st, 0.2, eng(steps=10, stopat=25))
        self.assertEqual((o['nsteps'], o['steps']), (5.0, 25.0))
        st, o, _ = L.engine_step(st, 0.3, eng(steps=10, stopat=25))
        self.assertEqual((o['nsteps'], o['run']), (0.0, 0.0))
        st, o, _ = L.engine_step(st, 0.4, eng(pause=True))
        self.assertEqual(o['nsteps'], 0.0)
        st, o, _ = L.engine_step(st, 0.5, eng(pause=True), events=['step'])
        self.assertEqual(o['nsteps'], 1.0)
        st, o, _ = L.engine_step(st, 0.6, eng(pause=True), events=['reset'])
        self.assertEqual((o['reset'], o['run']), (1.0, 1.0))

    def test_reseed(self):
        st, o, _ = L.engine_step(None, 0.0, eng(seed=5))
        self.assertEqual(o['seed'], 5.0)
        st, o, _ = L.engine_step(st, 0.1, eng(seed=5), events=['reseed'])
        self.assertEqual((o['seed'], o['reset']), (6.0, 1.0))
        st, o, _ = L.engine_step(st, 0.2, eng(seed=5), events=['reset'])
        self.assertEqual(o['seed'], 5.0)

    def test_morph_go_and_lfo(self):
        st, o, _ = L.engine_step(None, 0.0, eng(morphtime=2.0))
        st, o, _ = L.engine_step(st, 1.0, eng(morphtime=2.0), events=['go'])
        self.assertAlmostEqual(o['morph'], 0.0)
        st, o, _ = L.engine_step(st, 2.0, eng(morphtime=2.0))
        self.assertAlmostEqual(o['morph'], 0.5)
        st, o, _ = L.engine_step(st, 3.5, eng(morphtime=2.0))
        self.assertAlmostEqual(o['morph'], 1.0)
        st, o, _ = L.engine_step(st, 4.0, eng(morphtime=2.0), events=['go'])
        st, o, _ = L.engine_step(st, 7.0, eng(morphtime=2.0))
        self.assertAlmostEqual(o['morph'], 0.0)
        self.assertAlmostEqual(L.lfo('sine', 0.5), 1.0)
        self.assertAlmostEqual(L.lfo('triangle', 0.25), 0.5)
        st, o, _ = L.engine_step(None, 0.0, eng(morph=0.2, morphlfo='sine', morphrate=1.0, morphdepth=0.5))
        st, o, _ = L.engine_step(st, 0.5, eng(morph=0.2, morphlfo='sine', morphrate=1.0, morphdepth=0.5))
        self.assertAlmostEqual(o['morph'], 0.7)

    def test_effector_mapping(self):
        p = eng(planeh=2.0, aspect=0.5, effradius=0.1)
        r = L.effector_row({'tx': 0.5, 'ty': -0.5, 'sx': 2.0, 'sy': 1.0}, p)
        self.assertAlmostEqual(r[0], 0.5 / (2.0 * 0.5) + 0.5)
        self.assertAlmostEqual(r[1], 0.25)
        self.assertAlmostEqual(r[2], 0.1 * 2.0 / 2.0)
        self.assertIsNone(L.effector_row({'tx': 0, 'ty': 0, 'active': False}, p))
        r = L.effector_row({'tx': 0, 'ty': 0, 'strength': -0.5, 'radius': 0.3, 'morph': 1.0, 'falloff': 2}, eng())
        self.assertEqual((r[3], r[2], r[4], r[5], r[6]), (-0.5, 0.3, 1.0, 2.0, float(L.KIND_EFF)))

    def test_rows_sources_and_testmode(self):
        inp = {'effectors': [{'tx': 0, 'ty': 0}], 'points': L.points_from_chans({'x': [0.1, 0.2], 'y': [0.3, 0.4]},
                                                                                 eng()),
               'mouse': (0.5, 0.5, True)}
        st, o, rows = L.engine_step(None, 0.0, eng(mousemode='screen', burstcount=4), inp, events=['burst'])
        kinds = sorted(int(r[6]) for r in rows)
        self.assertEqual(kinds, [0, 1, 1, 2, 3, 3, 3, 3])
        self.assertEqual(o['nrows'], 8.0)
        st, o, rows = L.engine_step(None, 0.0, eng(testmode='fixed'), inp, events=['burst'])
        self.assertEqual(rows, [])
        st, o, rows = L.engine_step(None, 0.0, eng(effon=False), {'effectors': [{'tx': 0, 'ty': 0}]})
        self.assertEqual(rows, [])

    def test_audio_kick_and_morph(self):
        p = eng(audiomode='kick', audiogain=1.0, kickthresh=0.3, burstcount=2)
        st, o, rows = L.engine_step(None, 0.0, p, {'low': 0.1})
        self.assertEqual(len(rows), 0)
        st, o, rows = L.engine_step(st, 0.1, p, {'low': 0.5})
        self.assertEqual((o['kick'], len(rows)), (1.0, 2))
        st, o, rows = L.engine_step(st, 0.15, p, {'low': 0.1})
        st, o, rows = L.engine_step(st, 0.2, p, {'low': 0.5})        # within refractory 0.15 of 0.1? 0.1 later: ok
        self.assertEqual(o['kick'], 0.0)
        st, o, _ = L.engine_step(None, 0.0, eng(audiomode='morph', audiogain=2.0, audiomorph=0.5), {'level': 0.3})
        self.assertAlmostEqual(o['morph'], 0.3)

    def test_pack_unpack(self):
        rows = [L.row(0.1, 0.2, 0.3, 0.4, 0.5, 1, 2), L.row(0.6, 0.7, 0.8, -0.9, 0.0, 3, 0)]
        ch = L.pack_rows(rows)
        self.assertEqual(len(ch), 4)
        self.assertEqual(len(ch[0]), L.NROWS * L.ROW_TEXELS)
        back = L.unpack_rows(ch)
        self.assertEqual(len(back), 2)
        for a, b in zip(back, rows):
            self.assertEqual(tuple(a), tuple(b))

    def test_palette_channels(self):
        st, o, _ = L.engine_step(None, 0.0, eng(palette='fire'))
        self.assertEqual((o['pal4r'], o['pal4g'], o['pal4b']), L.PALETTES['fire'][4])
        cp = [(0.1, 0.2, 0.3)] * 5
        st, o, _ = L.engine_step(None, 0.0, eng(palette='custom', custompal=cp))
        self.assertEqual(o['pal2g'], 0.2)
        for n in L.ENGINE_CHANS:
            self.assertIn(n, o)


def _read(p):
    with open(p) as f:
        return f.read()


class ShaderContract(unittest.TestCase):
    def test_uniforms_match_pass_table(self):
        common = _read(os.path.join(GLSL, 'rd_common.glsl'))
        for name, s in L.PASSES:
            src = _read(os.path.join(GLSL, 'rd_%s.glsl' % name))
            vecs = re.findall(r'^uniform vec4 (\w+);', src, re.M)
            arrs = re.findall(r'^uniform samplerBuffer (\w+);', src, re.M)
            self.assertEqual(vecs, s['vecs'], name)
            self.assertEqual(arrs, s['arrays'], name)
            self.assertLessEqual(len(s['inputs']), 3, name)
            self.assertIn('local_size_x = 16, local_size_y = 16' if name == 'rd' else 'local_size_x = 8, local_size_y = 8', src)
            self.assertIn('TDImageStoreOutput', src)
            self.assertNotIn('#version', src + common)
            hi = max([int(x) for x in re.findall(r'sTD2DInputs\[(\d)\]', src)] + [0])
            self.assertLess(hi, max(1, len(s['inputs'])), name)

    def test_constants(self):
        common = _read(os.path.join(GLSL, 'rd_common.glsl'))
        for k in ('NROWS', 'ROW_TEXELS', 'LAP_EDGE', 'LAP_DIAG', 'ANISO_TRACE'):
            m = re.search(r'#define %s ([0-9.]+)' % k, common)
            self.assertIsNotNone(m, k)
            self.assertEqual(float(m.group(1)), float(getattr(L, k)), k)
        self.assertIn('0x7feb352du', common)
        self.assertIn('0x846ca68bu', common)

    def test_menu_orders_match_shader(self):
        rd = _read(os.path.join(GLSL, 'rd_rd.glsl'))
        self.assertEqual(L.FLOWMODES.index('curl'), 4)
        self.assertIn('fm == 4', rd)
        self.assertEqual(L.MAPMODES.index('pearson'), 5)
        self.assertIn('mm == 5', rd)
        self.assertEqual(L.SEEDMODES[:7], ['center', 'spots', 'noise', 'ring', 'stripes', 'image', 'text'])
        self.assertEqual(L.FALLOFFS, ['gauss', 'linear', 'hard', 'ring'])

    def test_ascii(self):
        files = [os.path.join(GLSL, f) for f in os.listdir(GLSL) if f.startswith('rd_')]
        files += [os.path.join(BUILDERS, 'reaction_diffusion.py'), os.path.join(BUILDERS, 'reaction_diffusion_logic.py')]
        for f in files:
            with open(f, 'rb') as fh:
                fh.read().decode('ascii')


class BuilderText(unittest.TestCase):
    def setUp(self):
        self.src = _read(os.path.join(BUILDERS, 'reaction_diffusion.py'))
        self.tree = ast.parse(self.src)
        self.ns = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                self.ns[node.targets[0].id] = node.value.value

    def test_callbacks_parse(self):
        for k in ('ENGINE_CB', 'ROWS_CB', 'STATS_CB', 'PULSES'):
            ast.parse(self.ns[k])

    def test_vec_exprs_cover_all_uniforms(self):
        g = {'os': os}
        exec(compile(self.src, 'reaction_diffusion.py', 'exec'), g)
        vx = g['_vec_exprs']()
        for _, s in L.PASSES:
            for u in s['vecs']:
                self.assertIn(u, vx)
                self.assertEqual(len(vx[u]), 4)
                for e in vx[u]:
                    compile(e, u, 'eval')

    def test_no_readback_or_fonts(self):
        self.assertNotIn('numpyArray(', self.src)
        self.assertNotIn('evalTextSize', self.src)
        self.assertNotIn('.par.font', self.src)

    def test_pulses_cover_pulse_pars(self):
        pulses = [n for _, pars in L.PAGES for n, st, _, _ in pars if st == 'Pulse']
        for n in pulses:
            self.assertIn(n, self.ns['PULSES'])


if __name__ == '__main__':
    unittest.main()
