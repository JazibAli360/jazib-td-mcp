"""Offline tests for builders/particles_logic.py, the GLSL files and the builder (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_particles.py'"""
import ast
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILDERS = os.path.join(REPO, 'builders')
GLSL = os.path.join(BUILDERS, 'glsl')
sys.path.insert(0, BUILDERS)
import particles_logic as L  # noqa: E402

FPS = 60.0
SHADERS = ('state', 'vert', 'pixel', 'trail', 'camdiff')


def raw(**kw):
    d = dict(L.DEFAULTS)
    d.update(kw)
    return d


def run_steps(r, frames, events_at=None, ctl=None, t0=0.0):
    st, outs = None, []
    for f in range(frames):
        st, o = L.step(st, r, ctl, (events_at or {}).get(f, ()), t0 + f / FPS)
        outs.append(o)
    return st, outs


def glsl(name):
    with open(os.path.join(GLSL, 'particles_{}.glsl'.format(name))) as fh:
        return fh.read()


class Contract(unittest.TestCase):
    def test_par_names_and_defaults(self):
        seen = set()
        for page, pars in L.PAGES:
            for name, style, default, o in pars:
                self.assertRegex(name, r'^[A-Z][a-z0-9]*$', name)          # T-00e
                self.assertNotIn(name, seen)
                seen.add(name)
                if style == 'Menu':
                    self.assertIn(default, o['names'], name)
                    self.assertEqual(len(o['names']), len(o['labels']), name)
                if style in ('XYZ', 'RGB'):
                    self.assertEqual(len(default), 3, name)
                if style in ('Float', 'Int'):
                    self.assertLessEqual(o['min'], o['max'], name)
        self.assertIn('Colours', L.PANEL_PAGES)                             # T-68: RGB on their own page
        self.assertTrue(all(st == 'RGB' for _, st, _, _ in dict(L.PAGES)['Colours']))
        for k in ('Count', 'Seed', 'Emitposx', 'Colour3b', 'Boundsizez'):
            self.assertIn(k, L.DEFAULTS)
        self.assertNotIn('Reset', L.DEFAULTS)

    def test_rows_shape_and_shader_array_size(self):
        st, o = L.step(None, raw(), None, (), 0.0)
        self.assertEqual(len(o['rows']), L.NROWS)
        self.assertTrue(all(len(r) == 4 and all(isinstance(v, float) for v in r) for r in o['rows']))
        for n in ('state', 'vert', 'pixel'):
            self.assertIn('uniform vec4 uP[{}];'.format(L.NROWS), glsl(n), n)

    def test_step_works_on_empty_raw(self):
        st, o = L.step(None, {}, None, (), 0.0)                             # every par has a default
        self.assertEqual(o['rows'][0][3], 65536.0)

    def test_grid(self):
        self.assertEqual(L.side(65536), 256)
        self.assertEqual(L.side(65537), 257)
        self.assertEqual(L.side(1), 1)
        self.assertEqual(L.side(0), 1)
        self.assertEqual(L.state_res(1048576), (3072, 1024))
        self.assertEqual(L.id_texel(257, 65536), (3, 1))

    def test_menus_and_helpers(self):
        self.assertEqual(L.menu_index(L.BOUNDS, 'kill'), 3)
        self.assertEqual(L.menu_index(L.BOUNDS, 'nope'), 0)
        self.assertEqual(L.emit_index('auto', False), 0)
        self.assertEqual(L.emit_index('auto', True), 1)
        self.assertEqual(L.emit_index('input', False), 1)
        self.assertEqual(L.emit_index('cam', True), 2)
        self.assertEqual(L.emit_index('none', True), 0)

    def test_sample_ids(self):
        ids = L.sample_ids(4096)
        self.assertEqual(len(ids), 64)
        self.assertEqual(len(set(ids)), 64)
        self.assertTrue(all(0 <= i < 4096 for i in ids))
        self.assertEqual(ids, L.sample_ids(4096))


class Clock(unittest.TestCase):
    def test_reset_frame_then_count(self):
        _, o = run_steps(raw(), 4)
        self.assertEqual([x['rows'][0][2] for x in o], [1.0, 0.0, 0.0, 0.0])
        self.assertEqual([x['info']['frame'] for x in o], [0.0, 1.0, 2.0, 3.0])
        self.assertEqual(o[0]['rows'][0][0], 0.0)                           # no motion on the reset frame
        self.assertAlmostEqual(o[1]['rows'][0][0], 1.0 / 60.0)

    def test_reset_triggers(self):
        st, _ = run_steps(raw(), 3)
        for r2, ev in ((raw(), ('reset',)), (raw(Count=1000), ()), (raw(Seed=7), ()), (raw(Statemode='inplace'), ())):
            _, o = L.step(st, r2, None, ev, 1.0)
            self.assertEqual(o['rows'][0][2], 1.0, (ev, r2.get('Count'), r2.get('Seed')))
        _, o = L.step(st, raw(Curlstrength=5.0), None, (), 1.0)             # look/force pars never reset
        self.assertEqual(o['rows'][0][2], 0.0)

    def test_play_off_freezes(self):
        st, _ = run_steps(raw(Emitmode='rate'), 5)
        st2, o = L.step(st, raw(Emitmode='rate', Play=False), None, ('burst',), 1.0)
        self.assertEqual(o['rows'][0][0], 0.0)
        self.assertEqual(o['info']['frame'], 4.0)
        self.assertEqual(o['rows'][2][1], 5000.0)                           # Burst still works while paused
        _, o = L.step(st2, raw(Emitmode='rate', Play=False), None, (), 1.1)
        self.assertEqual(o['rows'][2][1], 0.0)

    def test_speed_and_curl_time(self):
        _, o = run_steps(raw(Speed=2.0, Curlspeed=0.5), 61)
        self.assertAlmostEqual(o[-1]['info']['simt'], 2.0, places=9)
        self.assertAlmostEqual(o[-1]['rows'][3][2], 1.0, places=9)
        st = L.new_state()
        st.update(started=True, key=(65536, 1, 'feedback'), simt=L.CURL_WRAP / 0.3 + 1.0, t=0.0)
        _, o = L.step(st, raw(), None, (), 1 / 60.0)
        self.assertLess(o['rows'][3][2], 1.0)                               # wrapped

    def test_frame_wraps(self):
        st = L.new_state()
        st.update(started=True, key=(65536, 1, 'feedback'), frame=L.FRAME_WRAP - 1, t=0.0)
        _, o = L.step(st, raw(), None, (), 1 / 60.0)
        self.assertEqual(o['rows'][0][1], 0.0)


class Emission(unittest.TestCase):
    def test_rate_births(self):
        _, o = run_steps(raw(Emitmode='rate', Rate=5000.0), 61)
        n = sum(x['rows'][2][1] for x in o)
        self.assertIn(n, (4999.0, 5000.0))
        heads = [x['rows'][2][0] for x in o]
        self.assertEqual(heads[2], heads[1] + o[1]['rows'][2][1])

    def test_continuous_has_no_rate_births(self):
        _, o = run_steps(raw(Emitmode='continuous', Rate=5000.0), 30)
        self.assertEqual(sum(x['rows'][2][1] for x in o), 0.0)

    def test_burst_and_ring_wrap(self):
        r = raw(Count=100, Burstcount=70)
        _, o = run_steps(r, 4, events_at={1: ('burst',), 2: ('burst',), 3: ('burst',)})
        self.assertEqual([x['rows'][2][:2] for x in o[1:]], [(0.0, 70.0), (70.0, 70.0), (40.0, 70.0)])
        _, o = run_steps(raw(Count=100, Burstcount=500), 2, events_at={1: ('burst',)})
        self.assertEqual(o[1]['rows'][2][1], 100.0)                         # never more than Count
        self.assertTrue(L.in_window(5, 90, 20, 100))
        self.assertFalse(L.in_window(10, 90, 20, 100))
        self.assertFalse(L.in_window(0, 0, 0, 100))

    def test_audio_burst_on_kick_edges(self):
        r = raw(Audiosrc='bpm', Bpm=120.0, Smooth=0.0, Amtburst=1.0, Burstcount=10)
        _, o = run_steps(r, 601)
        self.assertEqual(sum(x['rows'][2][1] for x in o), 200.0)           # 20 kicks x 10


class Audio(unittest.TestCase):
    def test_bpm_kicks_v8(self):
        r = raw(Audiosrc='bpm', Bpm=120.0, Smooth=0.0)
        _, o = run_steps(r, 600)
        k = [x['info']['kick'] for x in o]
        peaks = [f for f in range(len(k)) if k[f] > 0.99]
        self.assertEqual(len(peaks), 20)
        self.assertTrue(all(b - a == 30 for a, b in zip(peaks, peaks[1:])))
        _, o = run_steps(raw(Audiosrc='bpm', Bpm=120.0, Smooth=0.0, Tapnudge=0.5), 2)
        self.assertAlmostEqual(o[0]['info']['phase'], 0.5)

    def test_bpm_env_shape(self):
        e = L.bpm_env(120.0, 0.0)
        self.assertAlmostEqual(e['kick'], 1.0)
        self.assertAlmostEqual(e['mid'], math.exp(-4.0))
        e = L.bpm_env(120.0, 0.25)                                          # half a beat
        self.assertAlmostEqual(e['mid'], 1.0)

    def test_manual_chop_off(self):
        _, o = run_steps(raw(Audiosrc='manual', Smooth=0.0, Manual1=1.0, Manual3=0.5), 1)
        i = o[0]['info']
        self.assertEqual((i['kick'], i['bass'], i['mid'], i['high'], i['level']), (1.0, 0.0, 0.5, 0.0, 0.375))
        _, o = run_steps(raw(Audiosrc='chop', Smooth=0.0), 1, ctl={'kick': 0.8, 'bass': 0.4})
        self.assertAlmostEqual(o[0]['info']['level'], 0.6)
        _, o = run_steps(raw(Audiosrc='chop', Smooth=0.0), 1, ctl={'kick': 0.8, 'level': 0.1})
        self.assertAlmostEqual(o[0]['info']['level'], 0.1)
        _, o = run_steps(raw(Audiosrc='off', Manual1=1.0), 1)
        self.assertEqual(o[0]['info']['kick'], 0.0)

    def test_smoothing(self):
        self.assertEqual(L.smooth(None, 1.0, 1 / 60, 0.1), 1.0)
        self.assertEqual(L.smooth(0.0, 1.0, 1 / 60, 0.0), 1.0)
        y = 0.0
        for _ in range(60):
            y = L.smooth(y, 1.0, 1 / 60, 0.1)
        self.assertAlmostEqual(y, 1.0 - math.exp(-10.0), places=9)

    def test_amounts_map_to_uniforms(self):
        r = raw(Audiosrc='manual', Smooth=0.0, Manual1=1.0, Manual2=1.0, Manual3=1.0, Manual4=1.0, Amtcurl=2.0,
                Amtsize=1.0, Amtbright=0.5, Amtatt=1.0, Att1on=True, Att2on=False, Amtspeed=1.0, Size=0.01)
        _, o = run_steps(r, 2)
        rows = o[1]['rows']
        self.assertAlmostEqual(rows[3][0], 1.0 + 2.0)                       # curl + bass
        self.assertAlmostEqual(rows[15][0], 0.02)                           # size x (1 + kick)
        self.assertAlmostEqual(rows[15][3], 0.6 + 0.5)                      # bright + level
        self.assertAlmostEqual(rows[6][3], 0.5 + 1.0)                       # att1 + mid
        self.assertEqual(rows[7][3], 0.0)                                   # att2 off
        self.assertAlmostEqual(rows[0][0], 2.0 / 60.0)                      # speed x (1 + level)


class Maths(unittest.TestCase):
    def test_hash_known_values(self):
        self.assertEqual(L.hash_u32(0), 0)
        self.assertEqual(L.hash_u32(1), self._ref_hash(1))
        self.assertEqual(L.hash_u32(0xFFFFFFFF), self._ref_hash(0xFFFFFFFF))
        vals = [L.rnd(i, 99) for i in range(2000)]
        self.assertTrue(all(0.0 <= v < 1.0 for v in vals))
        self.assertAlmostEqual(sum(vals) / len(vals), 0.5, delta=0.03)
        self.assertNotEqual(L.spawn_salt(1, 5), L.spawn_salt(2, 5))
        self.assertNotEqual(L.spawn_salt(1, 5), L.spawn_salt(1, 6))

    @staticmethod
    def _ref_hash(x):                                                       # independent re-statement (lowbias32)
        x &= 0xFFFFFFFF
        x = (x ^ (x >> 16)) * 0x7feb352d % (1 << 32)
        x = (x ^ (x >> 15)) * 0x846ca68b % (1 << 32)
        return x ^ (x >> 16)

    def test_hash_matches_numpy_reference(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest('numpy not available')
        ref = os.path.join(REPO, 'research_src', 'BO_particle_sims', 'ref_particles.py')
        if not os.path.exists(ref):
            self.skipTest('ref_particles.py missing')
        ns = {}
        with open(ref) as fh:
            exec(compile(fh.read().split('if __name__')[0], ref, 'exec'), ns)
        ids = np.arange(300)
        r = ns['rnd'](ids, 77)
        for i in range(300):
            self.assertEqual(float(r[i]), L.rnd(i, 77))

    def test_glsl_uses_same_constants(self):
        s = glsl('state')
        for k in ('0x7feb352du', '0x846ca68bu', '2654435761u', '0x9E3779B9u', '16777216.0', '17.0 * float(o)'):
            self.assertIn(k, s, k)
        for k in ('p.x - 0.6 * t', 'p.y + 0.5 * t', 'p.z + 0.9 * t', 'p.x + 1.1 * t', 'p.y + 1.3 * t', 'p.z - 0.7 * t'):
            self.assertIn(k, s, k)
        for i in range(8):                                                  # salt offsets used in both
            self.assertTrue(('sb + {}u'.format(i) in s) or i == 0, i)

    def test_curl_analytic_matches_fd_and_is_divergence_free(self):
        pts = [(L.rnd(i, 1) * 4 - 2, L.rnd(i, 2) * 4 - 2, L.rnd(i, 3) * 4 - 2) for i in range(200)]
        worst = 0.0
        for p in pts:
            a, b = L.curl1(p, 0.37), L.curl_fd(p, 0.37)
            worst = max(worst, max(abs(a[k] - b[k]) for k in range(3)))
        self.assertLess(worst, 1e-6)
        h, worst = 1e-4, 0.0
        for p in pts:
            div = 0.0
            for ax in range(3):
                q1, q0 = list(p), list(p)
                q1[ax] += h
                q0[ax] -= h
                div += (L.curl1(q1, 1.1)[ax] - L.curl1(q0, 1.1)[ax]) / (2 * h)
            worst = max(worst, abs(div))
        self.assertLess(worst, 1e-6)

    def test_camera(self):
        self.assertEqual(L.cam_pose(6.0, 0.0, 10.0, 0.5, -1.0), (0.5, -1.0, 6.0, 0.0))
        tx, ty, tz, ry = L.cam_pose(6.0, 90.0, 1.0)
        self.assertAlmostEqual(tx, 6.0)
        self.assertAlmostEqual(tz, 0.0)
        self.assertAlmostEqual(ry, 90.0)
        self.assertAlmostEqual(L.ortho_width(6.0, 90.0), 12.0)


V1 = dict(L.V1_PARS)


class Reference(unittest.TestCase):
    def test_compare_state_roundtrip(self):
        ids = L.sample_ids(4096)
        S, _ = L.reference_run(raw(**V1), 241, ids)
        w, h = L.state_res(4096)
        arr = [[(0.0, 0.0, 0.0, 0.0)] * w for _ in range(h)]
        for i in ids:
            x, y = L.id_texel(i, 4096)
            arr[y][x], arr[y][x + 1] = tuple(S[i][0]), tuple(S[i][1])
        e = L.compare_state(arr, V1, 241, ids)
        self.assertEqual((e['P'], e['V'], e['age'], e['n']), (0.0, 0.0, 0.0, 64))
        x, y = L.id_texel(ids[5], 4096)
        arr[y][x] = (arr[y][x][0] + 0.01,) + tuple(arr[y][x][1:])
        e = L.compare_state(arr, V1, 241, ids)
        self.assertAlmostEqual(e['P'], 0.01, places=9)
        self.assertEqual(e['id'], ids[5])

    def test_deterministic_finite_v1_v6(self):
        ids = L.sample_ids(4096)
        A, _ = L.reference_run(raw(**V1), 241, ids)
        B, _ = L.reference_run(raw(**V1), 241, ids)
        self.assertEqual(A, B)
        moved = 0
        for i in ids:
            a, b, c = A[i]
            self.assertTrue(all(math.isfinite(v) for v in a + b + c))
            self.assertAlmostEqual(a[3], 240 / 60.0, places=9)                 # all born at reset, none died
            moved += _len3(b[:3]) > 1e-3
        self.assertGreater(moved, 60)
        C, _ = L.reference_run(raw(**dict(V1, Seed=2)), 241, ids)
        self.assertNotEqual(A, C)

    def test_continuous_alive_fraction_v4(self):
        ids = list(range(256))
        r = raw(Count=256, Life=0.5, Lifevar=0.5)
        S, _ = L.reference_run(r, 120, ids)
        alive = sum(L.alive(S[i]) for i in ids) / 256.0
        self.assertGreaterEqual(alive, 0.99)                                # respawn on death: ~all alive
        dormant_at_start, _ = L.reference_run(r, 1, ids)
        self.assertTrue(all(dormant_at_start[i][0][3] <= 0.0 for i in ids))  # stagger: born over one life

    def test_rate_mode_counts(self):
        ids = list(range(256))
        r = raw(Count=256, Emitmode='rate', Rate=600.0, Life=10.0, Lifevar=0.0)
        S, out = L.reference_run(r, 13, ids)                                # reset + 12 frames x 10 births
        self.assertEqual(sum(L.alive(S[i]) for i in ids), 120)
        self.assertEqual(out['info']['head'], 120.0)

    def test_bounds_wrap_bounce_kill_floor(self):
        ids = list(range(64))
        base = dict(Count=64, Stagger=False, Life=100.0, Lifevar=0.0, Curlstrength=0.0, Drag=0.0,
                    Initspeed=3.0, Initspread=1.0, Boundsizex=0.5, Boundsizey=0.5, Boundsizez=0.5,
                    Emitsizex=0.1, Emitsizey=0.1, Emitsizez=0.1)
        S, _ = L.reference_run(raw(Bounds='wrap', **base), 120, ids)
        self.assertTrue(all(abs(S[i][0][k]) <= 0.5 + 1e-9 for i in ids for k in range(3)))
        S, _ = L.reference_run(raw(Bounds='bounce', Bounce=1.0, **base), 120, ids)
        self.assertTrue(all(abs(S[i][0][k]) <= 0.5 + 1e-9 for i in ids for k in range(3)))
        self.assertTrue(all(abs(_len3(S[i][1][:3]) - 3.0) < 1e-9 for i in ids))  # elastic: speed kept
        S, _ = L.reference_run(raw(Bounds='kill', Emitmode='rate', Rate=0.0, **base), 2, ids,
                               events_at={1: ('burst',)})
        self.assertEqual(sum(L.alive(S[i]) for i in ids), 64)
        S, _ = L.reference_run(raw(Bounds='kill', Emitmode='rate', Rate=0.0, Burstcount=64, **base), 60, ids,
                               events_at={1: ('burst',)})
        self.assertEqual(sum(L.alive(S[i]) for i in ids), 0)                  # all left the box -> dead
        S, _ = L.reference_run(raw(Bounds='none', Floor=True, Floory=-0.2, Bounce=0.0,
                                   Gravityy=-9.8, **dict(base, Initspeed=0.0)), 120, ids)
        self.assertTrue(all(S[i][0][1] >= -0.2 for i in ids))

    def test_forces_attractor_pulls_in(self):
        ids = list(range(32))
        r = raw(Count=32, Stagger=False, Life=100.0, Curlstrength=0.0, Drag=2.0, Initspeed=0.0, Att1on=True,
                Att1posx=0.0, Att1posy=0.0, Att1posz=0.0, Att1strength=2.0, Emitsizex=2.0, Emitsizey=2.0,
                Emitsizez=2.0, Source='box', Bounds='none')
        S0, _ = L.reference_run(r, 1, ids)
        S1, _ = L.reference_run(r, 300, ids)
        d0 = sum(_len3(S0[i][0][:3]) for i in ids)
        d1 = sum(_len3(S1[i][0][:3]) for i in ids)
        self.assertLess(d1, 0.5 * d0)

    def test_sources(self):
        for src, check in (('ball', lambda p: _len3(p) <= 0.3 + 1e-9),
                           ('box', lambda p: all(abs(x) <= 0.3 for x in p)),
                           ('ring', lambda p: abs(_len3(p) - 0.3) < 1e-9 and p[2] == 0.0),
                           ('line', lambda p: p[1] == 0.0 and p[2] == 0.0)):
            S, _ = L.reference_run(raw(Count=64, Source=src, Stagger=False), 1, list(range(64)))
            self.assertTrue(all(check(S[i][0][:3]) for i in range(64)), src)

    def test_top_source_weight_and_colour(self):
        emit = lambda u, v: (1.0, 0.2, 0.1, 1.0) if u < 0.25 else (0.0, 0.0, 0.0, 1.0)
        r = raw(Count=64, Source='top', Stagger=False, Emitsizex=1.0, Emitsizey=1.0, Emitthreshold=0.1)
        S, _ = L.reference_run(r, 1, list(range(64)), emit=emit)
        born = [i for i in range(64) if S[i][1][3] > 0.0]
        self.assertGreater(len(born), 40)                                   # 8 tries at 25 % -> ~90 %
        for i in born:
            self.assertLessEqual(S[i][0][0], -0.5)                          # u < 0.25 -> x < -0.5
            self.assertEqual(S[i][2][:3], [1.0, 0.2, 0.1])
        S, _ = L.reference_run(raw(Count=64, Source='top', Emitweight='alpha', Emitthreshold=0.5, Stagger=False), 1,
                               list(range(64)), emit=lambda u, v: (1.0, 1.0, 1.0, 0.0))
        self.assertTrue(all(S[i][1][3] == 0.0 for i in range(64)))          # alpha 0: nothing emits

    def test_debugstamp(self):
        S, out = L.reference_run(raw(Count=16, Debugstamp=True), 10, list(range(16)))
        self.assertTrue(all(S[i][2][3] == out['rows'][0][1] == 9.0 for i in range(16)))


def _len3(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


class Files(unittest.TestCase):
    def test_ascii(self):
        paths = [os.path.join(BUILDERS, f) for f in ('particles.py', 'particles_logic.py')]
        paths += [os.path.join(GLSL, 'particles_{}.glsl'.format(n)) for n in SHADERS]
        for p in paths:
            with open(p, 'rb') as fh:
                fh.read().decode('ascii')

    def test_compute_conventions(self):
        for n in ('state', 'trail', 'camdiff'):
            s = glsl(n)
            self.assertIn('layout (local_size_x = 8, local_size_y = 8) in;', s, n)
            self.assertIn('TDImageStoreOutput(0, ivec3(', s, n)
            self.assertNotIn('fragColor', s, n)
            self.assertNotIn('gl_FragCoord', s, n)
        self.assertIn('#ifdef STATE_INPLACE', glsl('state'))
        self.assertIn('TDInstanceID()', glsl('vert'))
        self.assertIn('layout(location = 0) out vec4 fragColor;', glsl('pixel'))
        self.assertIn('TDCheckDiscard();', glsl('pixel'))

    def test_builder_static(self):
        with open(os.path.join(BUILDERS, 'particles.py')) as fh:
            src = fh.read()
        tree = ast.parse(src)
        self.assertIn('build', [n.name for n in tree.body if isinstance(n, ast.FunctionDef)])
        code = '\n'.join(ln.split('#')[0] for ln in src.splitlines())
        for bad in ('numpyArray', 'evalTextSize', 'cookRate', '.destroy(', 'store('):
            self.assertFalse(bad in code, bad)                              # T-74/T-76/T-64/T-70/T-67
        ns = {}
        exec(compile(src.split('\ndef _logic')[0], 'particles.py', 'exec'), ns)
        created = set(re.findall(r"_(?:mk|text|compute|script|constant)\(c, (?:\w+, )?'(\w+)'", src))
        created |= set(re.findall(r"_compute\(c, '\w+', '(\w+)'", src))
        created |= {n + '_callbacks' for n in re.findall(r"_script\(c, '(\w+)'", src)}
        created |= {'controls', 'controls_window'}                          # zkit
        created |= {'PX_lines'}                                             # built by builders/px_lines.py
        for s_ in ns['STAGES']:
            for n in s_['ops']:
                self.assertIn(n, created, (s_['title'], n))
        for n in re.findall(r"_glsl\('(\w+)'\)", src):
            self.assertTrue(os.path.exists(os.path.join(GLSL, 'particles_{}.glsl'.format(n))), n)
        for n in ('engine_callbacks', 'info_callbacks'):
            self.assertIn(n, [x for s_ in ns['STAGES'] for x in s_['ops']])
        self.assertIn("'uP'", src)
        self.assertIn("array0arraytype = 'uniformarray'", src)

    def test_logic_has_no_td_import(self):
        with open(os.path.join(BUILDERS, 'particles_logic.py')) as fh:
            tree = ast.parse(fh.read())
        mods = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        mods |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertEqual(mods, {'math'})


def _ns(path):
    ns = {}
    with open(os.path.join(BUILDERS, path)) as fh:
        exec(compile(fh.read(), path, 'exec'), ns)
    return ns


class LaneG(unittest.TestCase):
    """Lane G (27 Oct): spiral fields + strand seeds (TC-13), palette colour, PX_lines light trails (TC-08), presets."""

    def test_spiral_force_shape(self):
        r = raw(Sp1on=True, Sp1swirl=2.0, Sp1pull=0.5, Sp1lift=0.3, Sp1radius=1.0, Sp1axisx=0.0, Sp1axisy=2.0,
                Sp1axisz=0.0)
        _, o = L.step(None, r, None, (), 0.0)
        U = o['rows']
        self.assertEqual(U[21][:3], (0.0, 1.0, 0.0))                         # axis normalised on the CPU
        F = L.spiral_force((1.0, 5.0, 0.0), U[20], U[21], U[22])            # d = 1 from the axis: g = 1/2
        self.assertAlmostEqual(F[0], -0.5 * 0.5)                            # pull toward the axis
        self.assertAlmostEqual(F[1], 0.3 * 0.5)                             # lift along it
        self.assertAlmostEqual(F[2], -2.0 * 0.5)                            # swirl: y x (1,0,0) = (0,0,-1)
        F2 = L.spiral_force((3.0, 0.0, 0.0), U[20], U[21], U[22])           # g = 1/10
        self.assertAlmostEqual(F2[2], -2.0 * 0.1)
        self.assertEqual(L.spiral_force((0.0, 1.0, 0.0), U[20], U[21], U[22]), (0.0, 0.3, 0.0))   # on the axis
        _, o2 = L.step(None, raw(), None, (), 0.0)                          # off = zero rows
        self.assertEqual(L.spiral_force((1.0, 0.0, 0.0), *o2['rows'][20:23]), (0.0, 0.0, 0.0))
        s = glsl('state')
        self.assertIn('for (int k = %d; k <= %d; k += 3)' % L.SPIRAL_ROWS, s)
        self.assertIn('uP[%d].x' % L.STRAND_ROW, s)
        self.assertIn('uP[%d].x' % L.PAL_ROW, glsl('vert'))

    def test_spiral_orbits_and_lifts(self):
        r = raw(Seed=3, Count=256, Stagger=False, Life=100.0, Lifevar=0.0, Bounds='none', Drag=1.0, Initspeed=0.0,
                Curlstrength=0.0, Source='ring', Emitsizex=1.0, Emitsizey=1.0, Emitsizez=0.0, Sp1on=True,
                Sp1axisx=0.0, Sp1axisy=0.0, Sp1axisz=1.0, Sp1swirl=1.0, Sp1pull=0.0, Sp1lift=0.5, Sp1radius=0.0)
        S0, _ = L.reference_run(r, 1, [0, 1, 2, 3])
        S, _ = L.reference_run(r, 61, [0, 1, 2, 3])
        for i, s_ in S.items():
            P, Q = s_[0][:3], S0[i][0][:3]
            turn = (math.atan2(P[1], P[0]) - math.atan2(Q[1], Q[0])) % math.tau
            self.assertTrue(0.3 < turn < 1.2, turn)                          # counter-clockwise about +z
            self.assertGreater(P[2], 0.1)                                    # lifted along +z

    def test_strand_seeds(self):
        r = raw(Source='strands', Strands=5, Strandjitter=0.0, Emitsizex=1.0, Emitsizey=1.0, Emitsizez=1.0)
        _, o = L.step(None, r, None, (), 0.0)
        U = o['rows']
        seen = set()
        for i in range(400):
            a, b, c = L.spawn(i, L.spawn_salt(1, 0), U)
            k = int(round(c[3] * 5 - 0.5))
            seen.add(k)
            ang = math.tau * k / 5
            self.assertAlmostEqual(a[0], math.cos(ang), places=9)
            self.assertAlmostEqual(a[1], math.sin(ang), places=9)
            self.assertEqual(a[2], 0.0)
        self.assertEqual(seen, set(range(5)))

    def test_v12_reference_and_compare(self):
        r = dict(L.DEFAULTS)
        r.update(L.V12_PARS)
        ids = L.sample_ids(4096, 16)
        S, _ = L.reference_run(r, 120, ids)
        for i in ids:
            self.assertTrue(all(math.isfinite(v) for t in S[i] for v in t))
        side = L.side(4096)
        arr = [[(0.0, 0.0, 0.0, 0.0)] * (3 * side) for _ in range(side)]
        for i in ids:
            x, y = L.id_texel(i, 4096)
            arr[y][x], arr[y][x + 1] = tuple(S[i][0]), tuple(S[i][1])
        w = L.compare_state(arr, L.V12_PARS, 120, ids)
        self.assertLess(w['P'], 1e-12)

    def test_palette_rows_and_names(self):
        _, o = L.step(None, raw(Palby='height', Palpos=0.25, Palspread=-2.0), None, (), 0.0)
        self.assertEqual(o['rows'][L.PAL_ROW], (3.0, 0.25, -2.0, 0.0))
        pm = _ns('palette_map_logic.py')
        for k in L.PAL_SOURCES:
            self.assertTrue(k == 'custom' or pm['stop_preset'](k) is not None, k)
        pl = _ns('px_lines_logic.py')
        self.assertEqual(L.LINE_COLSRC, [a for a, _b in pl['COLSRC']])
        self.assertEqual(L.LINE_ATTR, [a for a, _b in pl['ATTR']])
        self.assertEqual(L.PAL_MODES, [a for a, _b in pl['PAL_MODES']])
        self.assertTrue(set(L.PAL_SOURCES) <= set(pl['PAL_SOURCE_KEYS']))

    def test_line_links_target_px_lines(self):
        pl = _ns('px_lines_logic.py')
        spec = pl['par_specs']()
        flat = set()
        for n, (st, _d, _o) in spec.items():
            flat |= {n + x for x in ('rgb' if st == 'RGB' else 'xyz')} if st in ('RGB', 'XYZ') else {n}
        for child, e in L.line_links().items():
            self.assertIn(child, flat, child)
            for mine in re.findall(r'parent\(\)\.par\.(\w+)', e):
                self.assertIn(mine, L.DEFAULTS, mine)
        for k, v in L.LINE_CONST.items():
            self.assertIn(k, flat, k)
            st, _d, o = spec[k]
            if st == 'Menu':
                self.assertIn(v, o['names'], k)
        for child, mine in L.LINE_PAIRS:                                     # menus map name to name
            if child in spec and spec[child][0] == 'Menu':
                self.assertTrue(set(L.MENUS[mine]) <= set(spec[child][2]['names']), child)

    def test_presets_full_state(self):
        self.assertEqual(len(set(L.PRESET_NAMES)), len(L.PRESETS))
        keys = set(L.DEFAULTS) - set(L.PRESET_KEEP)
        for _slot, name, vals in L.PRESETS:
            d = L.preset_pars(name)
            self.assertEqual(set(d) - {'Chop'}, keys, name)                   # every par, every time (+ a CHOP path)
            for k in vals:
                self.assertIn(k, L.PAR_STYLE, (name, k))
            for k, v in d.items():
                if k in L.MENUS:
                    self.assertIn(v, L.MENUS[k], (name, k))
            z = L.preset_zk(name)
            self.assertTrue(all(isinstance(z[k], int) for k in L.MENUS if k in z), name)
            st, o = L.step(None, d, None, (), 0.0)
            self.assertEqual(len(o['rows']), L.NROWS)
        a, b = L.preset_pars('vortex'), L.preset_pars('default')               # no inheritance between presets
        self.assertEqual(b['Sp1on'], False)
        self.assertEqual(a['Sp1on'], True)
        lt = L.preset_pars('lighttrails')
        self.assertTrue(lt['Lineson'] and not lt['Linedots'])
        self.assertLessEqual(L.line_segments(lt), int(lt['Linetracks']) * int(lt['Linesamples']))
        self.assertEqual(L.preset_pars(2), lt)                                 # by slot too


STUB_COMPUTE = """#version 460
uniform sampler2D sTD2DInputs[3];
struct TDTexInfo { vec4 res; vec4 depth; };
uniform TDTexInfo uTDOutputInfo;
layout(rgba32f) uniform image2DArray mTDComputeOutputs[1];
void TDImageStoreOutput(uint i, ivec3 c, vec4 v) { imageStore(mTDComputeOutputs[i], c, v); }
vec4 TDImageLoadOutput(uint i, ivec3 c) { return imageLoad(mTDComputeOutputs[i], c); }
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""
STUB_VERT = """#version 460
in vec3 P;
struct TDMatrix { mat4 world; mat4 worldCam; mat4 proj; };
uniform TDMatrix uTDMats[1];
int TDInstanceID() { return gl_InstanceID; }
int TDCameraIndex() { return 0; }
"""
STUB_PIXEL = """#version 460
void TDCheckDiscard() {}
vec4 TDOutputSwizzle(vec4 c) { return c; }
"""


@unittest.skipUnless(shutil.which('glslc'), 'glslc not installed')
class Compile(unittest.TestCase):
    """Syntax/type check with TD-like stubs (glslc, OpenGL target). Not a TD compile: LIVE CHECK still applies."""

    def _ok(self, text, ext):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 's.' + ext)
            with open(p, 'w') as fh:
                fh.write(text)
            r = subprocess.run(['glslc', '--target-env=opengl', '-fauto-bind-uniforms', '-fauto-map-locations',
                                '-o', os.devnull, p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_all(self):
        for n in ('state', 'trail', 'camdiff'):
            self._ok(STUB_COMPUTE + glsl(n), 'comp')
        self._ok(STUB_COMPUTE + '#define STATE_INPLACE 1\n' + glsl('state'), 'comp')
        with open(os.path.join(GLSL, 'px_palette.glsl')) as fh:
            pal = fh.read()
        self._ok(STUB_VERT + pal + glsl('vert'), 'vert')
        self._ok(STUB_PIXEL + glsl('pixel'), 'frag')


if __name__ == '__main__':
    unittest.main()


class LaneGConfetti(unittest.TestCase):
    """Lane G (27 Oct): confetti (7C-11): flutter force, shapes, Hit / Autohit."""

    def test_flutter_and_rows(self):
        _, o = L.step(None, raw(Flutter=2.0, Flutterhz=1.0, Shape='paper', Spinrate=3.0, Lightdirx=0.0,
                                Lightdiry=0.0, Lightdirz=2.0), None, (), 0.0)
        U = o['rows']
        self.assertEqual(U[L.SHAPE_ROW][:3], (1.0, 3.0, 0.6))
        self.assertEqual(U[29][:3], (0.0, 0.0, 1.0))                          # light dir normalised
        f = L.flutter(0.25, 0.0, U)                                            # sin(pi/2) = 1
        self.assertAlmostEqual(f[0], 2.0)
        self.assertEqual(f[1], 0.0)
        _, o0 = L.step(None, raw(), None, (), 0.0)
        self.assertEqual(L.flutter(0.3, 0.2, o0['rows']), (0.0, 0.0, 0.0))
        self.assertIn('uP[30].x != 0.0', glsl('state'))
        self.assertIn('forces(P, V, a.w, c.w)', glsl('state'))
        for n in ('Rodrigues', 'shp == 2', 'uP[28].x'):
            self.assertIn(n, glsl('vert'))

    def test_hit_and_autohit(self):
        r = raw(Emitmode='rate', Rate=0.0, Burstcount=100, Amtburst=1.0, Audiosrc='manual', Smooth=0.0,
                Autohit=False)
        st, outs = run_steps(dict(r, Manual1=0.0), 2)
        st, o = L.step(st, dict(r, Manual1=1.0), None, (), 2 / 60.0)          # kick edge, Auto off: nothing
        self.assertEqual(o['info']['births'], 0.0)
        st, o = L.step(st, dict(r, Manual1=1.0), None, ('burst',), 3 / 60.0)   # Hit (Burst) always fires
        self.assertEqual(o['info']['births'], 100.0)
        st2, _ = run_steps(dict(r, Manual1=0.0, Autohit=True), 2)
        st2, o2 = L.step(st2, dict(r, Manual1=1.0, Autohit=True), None, (), 2 / 60.0)
        self.assertEqual(o2['info']['births'], 100.0)                          # Auto on: the kick fires

    def test_confetti_falls_at_terminal_speed(self):
        d = L.preset_pars('confetti')
        self.assertEqual(d['Chop'], L.KICK_CHOP)
        self.assertFalse(d['Autohit'])
        d = dict(d, Seed=2, Count=256, Emitmode='continuous', Stagger=False, Life=100.0, Lifevar=0.0,
                 Curlstrength=0.0, Flutter=0.0, Audiosrc='off')
        S, _ = L.reference_run(d, 600, [0, 1, 2, 3])
        for i, s_ in S.items():
            v = s_[1][:3]
            self.assertAlmostEqual(v[1], -2.5 / 1.2, delta=0.05)               # g / drag
