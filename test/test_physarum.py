"""Offline tests for builders/physarum_logic.py + builders/glsl/ph_*.glsl + the builder text (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_physarum.py'"""
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
import physarum_logic as L  # noqa: E402


def _read(p):
    with open(p) as f:
        return f.read()


def prm(**kw):
    q = dict(L.REF_DEFAULTS)
    q.update(kw)
    return q


def eng(**kw):
    p = dict(L.ENGINE_DEFAULTS)
    p.update(kw)
    return p


class Basics(unittest.TestCase):
    def test_lowbias32_known(self):
        def ref(x):
            x &= 0xffffffff
            x ^= x >> 16
            x = (x * 0x7feb352d) & 0xffffffff
            x ^= x >> 15
            x = (x * 0x846ca68b) & 0xffffffff
            x ^= x >> 16
            return x
        for v in (0, 1, 7, 12345, 2 ** 31 + 5, 2 ** 32 - 1):
            self.assertEqual(int(L.hash_u32(v)), ref(v))
        h = L.hash3(np.arange(1000), 5, 1)
        self.assertTrue((h >= 0).all() and (h < 1).all())

    def test_agent_side(self):
        for n, s in ((1, 1), (4, 2), (5, 3), (262144, 512), (262145, 513), (1048576, 1024), (1000000, 1000)):
            self.assertEqual(L.agent_side(n), s)

    def test_sim_size(self):
        self.assertEqual(L.sim_size(1080, 1920, 960), (540, 960))

    def test_presets_and_morph(self):
        self.assertEqual(len(L.PRESET_NAMES), len(L.PRESET_LABELS))
        a, b = L.preset_values('network'), L.preset_values('cells')
        m = L.morph_presets(a, b, 0.5)
        for k in L.PRESET_FIELDS:
            self.assertAlmostEqual(m[k], 0.5 * (a[k] + b[k]))
        c = L.preset_values('custom', {'sa': 33.0})
        self.assertEqual(c['sa'], 33.0)
        self.assertEqual(c['so'], a['so'])

    def test_pages_valid(self):
        names = set()
        for _, pars in L.PAGES:
            for n, st, d, o in pars:
                self.assertTrue(n[0].isupper() and n[1:] == n[1:].lower(), n)
                self.assertNotIn(n, names)
                names.add(n)
                if st == 'Menu':
                    self.assertIn(d, o['names'])
                    self.assertEqual(len(o['names']), len(o['labels']))
        for f in L.PRESET_FIELDS:
            self.assertIn('Custom' + f, names)
            self.assertIn(L.GAIN_PARS[f], names)


class Reference(unittest.TestCase):
    def test_deposit_exact(self):
        ag = L.seed_agents(1000, L.agent_side(1000), 40, 60, prm(seedmode='random'))
        D = L.deposit_map(ag, 40, 60, 2.0)
        self.assertEqual(D[..., 3].sum(), 1000)
        self.assertEqual(D[..., 0].sum(), 2000)
        self.assertEqual((ag[..., 3] < 0).sum(), L.agent_side(1000) ** 2 - 1000)

    def test_trail_mass_wrap(self):
        rng = np.random.default_rng(1)
        T = np.zeros((30, 20, 4))
        T[..., 0] = rng.random((30, 20))
        D = np.zeros_like(T)
        D[5, 5, 0] = 3.0
        out = L.trail_pass(T, D, prm(decay=0.0, diffuse=1.0))
        self.assertAlmostEqual(out[..., 0].sum(), T[..., 0].sum() + 3.0, 9)
        out = L.trail_pass(T, D, prm(decay=0.25, diffuse=0.5))
        self.assertAlmostEqual(out[..., 0].sum(), 0.75 * (T[..., 0].sum() + 3.0), 9)

    def test_steady_state_mean(self):
        ag, tr = L.run_fixed(120, 2000, 40, 60, prm(seedmode='random', decay=0.2))
        self.assertAlmostEqual(L.stats(tr, ag)['mean'], L.expected_mean(2000, 1.0, 0.2, 40, 60), 6)

    def test_presets_form_networks(self):
        # every preset keeps a structured trail: some cover, not all, finite
        for name, vals in L.PRESETS[:-1]:
            p = prm(seedmode='random', **dict(zip(L.PRESET_FIELDS, vals)))
            ag, tr = L.run_fixed(150, 6000, 60, 100, p)
            s = L.stats(tr, ag)
            self.assertTrue(np.isfinite(tr).all(), name)
            self.assertGreater(s['cover'], 0.05, name)
            self.assertLess(s['cover'], 0.9, name)

    def test_jones_rule(self):
        # trail ridge on the left of an agent heading +x: it turns left (+RA)
        w, h = 40, 40
        tr = np.zeros((h, w, 4))
        ag = np.array([[[20.5, 20.5, 0.0, 0.0]]])
        p = prm(sa=45.0, so=5.0, ra=30.0, ss=0.0, jitter=0.0)
        a = math.radians(45)
        tr[int(20.5 + 5 * math.sin(a)), int(20.5 + 5 * math.cos(a)), 0] = 1.0
        out = L.agent_pass(ag, tr, p, 1)
        self.assertAlmostEqual(out[0, 0, 2], math.radians(30), 9)
        tr[...] = 0
        tr[int(20.5 - 5 * math.sin(a)), int(20.5 + 5 * math.cos(a)), 0] = 1.0
        out = L.agent_pass(ag, tr, p, 1)
        self.assertAlmostEqual(out[0, 0, 2], 2 * math.pi - math.radians(30), 9)
        tr[...] = 0
        tr[20, 25, 0] = 1.0                           # straight ahead: keep heading
        out = L.agent_pass(ag, tr, p, 1)
        self.assertAlmostEqual(out[0, 0, 2], 0.0, 9)

    def test_species_avoid(self):
        # own trail ahead-left, other species ahead-right: with Otherw -1 the agent turns toward its own
        w, h = 40, 40
        tr = np.zeros((h, w, 4))
        a = math.radians(45)
        tr[int(20.5 + 5 * math.sin(a)), int(20.5 + 5 * math.cos(a)), 1] = 1.0   # species 1 on the left
        ag = np.array([[[20.5, 20.5, 0.0, 0.0]]])                                  # species 0
        out = L.agent_pass(ag, tr, prm(nspecies=2, sa=45.0, so=5.0, ra=30.0, ss=0.0, otherw=-1.0), 1)
        self.assertAlmostEqual(out[0, 0, 2], 2 * math.pi - math.radians(30), 9)
        out = L.agent_pass(ag, tr, prm(nspecies=2, sa=45.0, so=5.0, ra=30.0, ss=0.0, otherw=1.0), 1)
        self.assertAlmostEqual(out[0, 0, 2], math.radians(30), 9)

    def test_attractor_and_repeller(self):
        p = prm(seedmode='random', decay=0.3)
        rows_a = [L.row(0.5, 0.5, 0.2, 20.0)]
        rows_r = [L.row(0.5, 0.5, 0.2, -20.0)]
        w, h = 60, 60
        q = dict(p)
        ag = L.seed_agents(3000, L.agent_side(3000), w, h, q)
        res = {}
        for k, rows in (('a', rows_a), ('r', rows_r)):
            g = ag.copy()
            tr = np.zeros((h, w, 4))
            for s in range(1, 60):
                g = L.agent_pass(g, tr, q, s, rows=rows)
                tr = L.trail_pass(tr, L.deposit_map(g, w, h, 1.0), q)
            d = np.hypot(g[..., 0] - 30, g[..., 1] - 30)
            res[k] = float((d < 12)[g[..., 3] >= 0].mean())
        self.assertGreater(res['a'], 0.5)
        self.assertLess(res['r'], 0.05)

    def test_bounce_in_bounds_and_mask_blocks(self):
        w, h = 30, 50
        ag = L.seed_agents(500, L.agent_side(500), w, h, prm(seedmode='random'))
        tr = np.zeros((h, w, 4))
        q = prm(edge=1, ss=4.0)
        for s in range(1, 40):
            ag = L.agent_pass(ag, tr, q, s)
        live = ag[..., 3] >= 0
        self.assertTrue((ag[..., 0][live] >= 0).all() and (ag[..., 0][live] < w).all())
        self.assertTrue((ag[..., 1][live] >= 0).all() and (ag[..., 1][live] < h).all())
        maps = np.zeros((h, w, 4))
        maps[:, 15:, 0] = 1.0
        ag = L.seed_agents(500, L.agent_side(500), w, h, prm(seedmode='random'))
        left0 = ag[..., 0] < 15
        q = prm(edge=1, ss=1.0)
        for s in range(1, 40):
            ag = L.agent_pass(ag, tr, q, s, maps)
        self.assertTrue((ag[..., 0][left0 & (ag[..., 3] >= 0)] < 15).all())

    def test_seeds(self):
        w, h = 90, 160
        for mode in L.SEEDMODES:
            img = np.zeros((h, w))
            img[60:100, 30:60] = 1.0
            ag = L.seed_agents(400, 20, w, h, prm(seedmode=mode, heading='inward'), img)
            self.assertTrue((ag[..., 0] >= 0).all() and (ag[..., 0] < w).all(), mode)
            self.assertTrue((ag[..., 2] >= 0).all() and (ag[..., 2] < 2 * math.pi).all(), mode)
            if mode == 'image':
                inside = (ag[..., 0] >= 30) & (ag[..., 0] < 60) & (ag[..., 1] >= 60) & (ag[..., 1] < 100)
                self.assertGreater(inside.mean(), 0.85)
            if mode == 'disc':
                r = np.hypot(ag[..., 0] - 45, ag[..., 1] - 80)
                self.assertLessEqual(r.max(), 0.3 * h + 1e-9)

    def test_species_layouts(self):
        w, h = 90, 160
        for mode in L.SPECIESMODES:
            ag = L.seed_agents(900, 30, w, h, prm(seedmode='random', nspecies=3, speciesmode=mode))
            self.assertEqual(sorted(set(ag[..., 3].ravel().tolist())), [0.0, 1.0, 2.0], mode)

    def test_respawn_fraction(self):
        w, h = 60, 100
        ag = L.seed_agents(40000, 200, w, h, prm(seedmode='center'))
        out = L.agent_pass(ag, np.zeros((h, w, 4)), prm(ss=0.0, respawn=0.05), 3)
        moved = (out[..., 0] != ag[..., 0]) | (out[..., 1] != ag[..., 1])
        self.assertAlmostEqual(moved.mean(), 0.05, delta=0.005)
        self.assertTrue((out[..., 0] < w).all() and (out[..., 1] < h).all())

    def test_stats_order(self):
        ag = np.zeros((2, 2, 4))
        ag[..., 2] = 0.3
        ag[1, 1, 3] = -1
        s = L.stats(np.zeros((4, 4, 4)), ag)
        self.assertAlmostEqual(s['order'], 1.0)
        self.assertAlmostEqual(s['alive'], 0.75)


class Engine(unittest.TestCase):
    def test_reset_frame_then_steps(self):
        st, o, _ = L.engine_step(None, 0.0, eng())
        self.assertEqual((o['reset'], o['run'], o['steps']), (1.0, 0.0, 0.0))
        st, o, _ = L.engine_step(st, 1 / 60., eng())
        self.assertEqual((o['reset'], o['run'], o['steps']), (0.0, 1.0, 1.0))

    def test_size_change_resets(self):
        st, o, _ = L.engine_step(None, 0.0, eng(sizekey=(100, 960, 1080, 1920)))
        st, o, _ = L.engine_step(st, 0.1, eng(sizekey=(100, 960, 1080, 1920)))
        self.assertEqual(o['reset'], 0.0)
        st, o, _ = L.engine_step(st, 0.2, eng(sizekey=(400, 960, 1080, 1920)))
        self.assertEqual(o['reset'], 1.0)

    def test_pause_step_stopat(self):
        st, o, _ = L.engine_step(None, 0.0, eng())
        st, o, _ = L.engine_step(st, 0.1, eng(pause=True))
        self.assertEqual(o['run'], 0.0)
        st, o, _ = L.engine_step(st, 0.2, eng(pause=True), events=['step'])
        self.assertEqual((o['run'], o['steps']), (1.0, 1.0))
        for k in range(10):
            st, o, _ = L.engine_step(st, 0.3 + k, eng(stopat=5))
        self.assertEqual(o['steps'], 5.0)
        self.assertEqual(o['run'], 0.0)

    def test_morph_gains_audio(self):
        st, o, _ = L.engine_step(None, 0.0, eng(morph=0.5))
        a, b = L.preset_values('network'), L.preset_values('cells')
        self.assertAlmostEqual(o['so'], 0.5 * (a['so'] + b['so']))
        g = {k: 1.0 for k in L.PRESET_FIELDS}
        g['ss'] = 2.0
        st, o, _ = L.engine_step(None, 0.0, eng(gains=g))
        self.assertAlmostEqual(o['ss'], 2.0 * a['ss'])
        st, o, _ = L.engine_step(None, 0.0, eng(audiomode='level', audiotarget='deposit', audiogain=1.0, audioamt=1.0),
                                 {'level': 0.5})
        self.assertAlmostEqual(o['dep'], a['dep'] * 1.5)
        st, o, _ = L.engine_step(None, 0.0, eng(audiomode='level', audiotarget='step', testmode='fixed'),
                                 {'level': 0.5})
        self.assertAlmostEqual(o['ss'], a['ss'])

    def test_morph_go(self):
        st, o, _ = L.engine_step(None, 0.0, eng(morphtime=2.0))
        st, o, _ = L.engine_step(st, 1.0, eng(morphtime=2.0), events=['go'])
        self.assertAlmostEqual(o['morph'], 0.0)
        st, o, _ = L.engine_step(st, 2.0, eng(morphtime=2.0))
        self.assertAlmostEqual(o['morph'], 0.5)
        st, o, _ = L.engine_step(st, 3.5, eng(morphtime=2.0))
        self.assertAlmostEqual(o['morph'], 1.0)

    def test_kick_speed_and_bursts(self):
        p = eng(audiomode='kick', audiogain=1.0, kickthresh=0.3, kickspeed=3.0, kickrelease=0.5, burstframes=3)
        st, o, _ = L.engine_step(None, 0.0, p, {'low': 0.0})
        st, o, rows = L.engine_step(st, 0.1, p, {'low': 0.5})
        self.assertEqual(o['kick'], 1.0)
        self.assertAlmostEqual(o['ss'], 3.0)
        self.assertEqual(len(rows), 3)
        st, o, rows = L.engine_step(st, 0.6, p, {'low': 0.5})
        self.assertAlmostEqual(o['kenv'], math.exp(-1.0))
        self.assertEqual(len(rows), 3)
        st, o, rows = L.engine_step(st, 0.7, p, {'low': 0.0})
        st, o, rows = L.engine_step(st, 0.8, p, {'low': 0.0})
        self.assertEqual(len(rows), 0)

    def test_effector_and_mouse_rows(self):
        p = eng(mousemode='repel')
        e = {'tx': 0.0, 'ty': 0.25, 'sx': 2.0, 'sy': 1.0, 'strength': None, 'radius': None, 'deposit': 0.5,
             'falloff': None, 'active': True}
        st, o, rows = L.engine_step(None, 0.0, p, {'effectors': [e], 'mouse': (0.2, 0.3, True)})
        self.assertAlmostEqual(rows[0][0], 0.5)
        self.assertAlmostEqual(rows[0][1], 0.75)
        self.assertAlmostEqual(rows[0][2], 2.0 * p['effradius'])
        self.assertAlmostEqual(rows[0][4], 0.5)
        self.assertLess(rows[1][3], 0)
        self.assertEqual(rows[1][6], L.KIND_MOUSE)
        st, o, rows = L.engine_step(None, 0.0, eng(testmode='fixed'), {'effectors': [e]})
        self.assertEqual(rows, [])

    def test_pack_unpack(self):
        rows = [L.row(0.1, 0.2, 0.3, 0.4, 0.5, 1, 2), L.row(0.6, 0.7, 0.8, -1, 0, 0, 0)]
        ch = L.pack_rows(rows)
        self.assertEqual(len(ch[0]), L.NROWS * L.ROW_TEXELS)
        self.assertEqual(L.unpack_rows(ch), rows)


class ShaderContract(unittest.TestCase):
    def test_uniforms_match_pass_table(self):
        common = _read(os.path.join(GLSL, 'ph_common.glsl'))
        for name, s in L.PASSES:
            src = _read(os.path.join(GLSL, 'ph_%s.glsl' % name))
            vecs = re.findall(r'^uniform vec4 (\w+);', src, re.M)
            arrs = re.findall(r'^uniform samplerBuffer (\w+);', src, re.M)
            self.assertEqual(vecs, s['vecs'], name)
            self.assertEqual(arrs, s['arrays'], name)
            self.assertLessEqual(len(s['inputs']), 3, name)
            self.assertIn('local_size_x = 8, local_size_y = 8', src)
            self.assertIn('TDImageStoreOutput', src)
            self.assertNotIn('#version', src + common)
            hi = max([int(x) for x in re.findall(r'sTD2DInputs\[(\d)\]', src)] + [0])
            self.assertLess(hi, max(1, len(s['inputs'])), name)

    def test_constants_and_menus(self):
        common = _read(os.path.join(GLSL, 'ph_common.glsl'))
        for k in ('NROWS', 'ROW_TEXELS', 'NSPECIES'):
            m = re.search(r'#define %s ([0-9.]+)' % k, common)
            self.assertEqual(float(m.group(1)), float(getattr(L, k)), k)
        self.assertIn('0x7feb352du', common)
        ag = _read(os.path.join(GLSL, 'ph_agents.glsl'))
        # seed menu indices used by the shader
        self.assertEqual(L.SEEDMODES.index('disc'), 1)
        self.assertEqual(L.SEEDMODES.index('lines'), 4)
        self.assertEqual(L.SEEDMODES.index('image'), 5)
        self.assertEqual(L.SEEDMODES.index('center'), 7)
        self.assertIn('mode == 7', ag)
        self.assertEqual(L.HEADINGS, ['random', 'outward', 'inward', 'swirl'])
        self.assertEqual(L.SPECIESMODES, ['interleave', 'bands', 'rings'])
        self.assertEqual(L.VALUEMODES, ['soft', 'linear', 'log'])
        self.assertEqual(L.COLORMODES, ['species', 'palette', 'ramp', 'gray'])
        self.assertEqual(L.EDGES, ['wrap', 'bounce'])

    def test_deposit_material(self):
        v = _read(os.path.join(GLSL, 'ph_deposit_vertex.glsl'))
        self.assertIn('TDPos()', v)                     # raw P reads garbage on POP points (T-112)
        self.assertNotIn(' P.', v.split('\n', 3)[-1])
        self.assertIn('gl_PointSize = 1.0', v)

    def test_ascii(self):
        for f in os.listdir(GLSL):
            if f.startswith('ph_'):
                _read(os.path.join(GLSL, f)).encode('ascii')
        for f in ('physarum.py', 'physarum_logic.py'):
            _read(os.path.join(BUILDERS, f)).encode('ascii')


class BuilderText(unittest.TestCase):
    def setUp(self):
        self.src = _read(os.path.join(BUILDERS, 'physarum.py'))
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
        exec(compile(self.src, 'physarum.py', 'exec'), g)
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

    def test_engine_chans_cover_exprs(self):
        used = set(re.findall(r"E\('(\w+)'\)", self.src))
        self.assertTrue(used <= set(L.ENGINE_CHANS), used - set(L.ENGINE_CHANS))


if __name__ == '__main__':
    unittest.main()
