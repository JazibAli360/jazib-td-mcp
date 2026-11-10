"""Offline tests for builders/fluid2d_logic.py + builders/glsl/fluid2d_*.glsl (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fluid2d.py'"""
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
import fluid2d_logic as L  # noqa: E402

P = dict(L.REF_DEFAULTS)


def prm(**kw):
    q = dict(P)
    q.update(kw)
    return q


def rand_vel(h, w, seed=3):
    r = np.random.default_rng(seed)
    return r.standard_normal((h, w)), r.standard_normal((h, w))


def project(ux, uy, sol, p, K):
    d = L.pass_div(ux, uy, sol, p)
    pr = np.zeros_like(ux)
    for _ in range(K):
        pr = L.pass_press(pr, d, sol, p)
    return L.pass_grad(pr, ux, uy, sol, p)


def l2(a):
    return float(np.sqrt((a * a).sum()))


class Splat(unittest.TestCase):
    def test_integral_pi_r2(self):
        H = W = 400                                   # aspect 1: uv units = screen heights
        X, Y = L.grid(W, H)
        r = 0.05
        g = L.splat((X + 0.5) / W, (Y + 0.5) / H, 0.5, 0.5, r, 1.0)
        self.assertAlmostEqual(g.sum() / (W * H) / (math.pi * r * r), 1.0, delta=0.01)

    def test_aspect_round_on_screen(self):
        # 9:16 grid: a point 0.1 screen heights right (= 0.1/aspect uv) and one 0.1 up get the same weight
        a = 1080.0 / 1920.0
        gx = L.splat(np.array(0.5 + 0.1 / a), np.array(0.5), 0.5, 0.5, 0.05, a)
        gy = L.splat(np.array(0.5), np.array(0.6), 0.5, 0.5, 0.05, a)
        self.assertAlmostEqual(float(gx), float(gy), places=12)


class ZeroInZeroOut(unittest.TestCase):
    def test_200_steps_exact_zero(self):
        st = L.new_sim(32, 48, 54, 96)
        for _ in range(200):
            st = L.step(st, prm(aspect=54 / 96.0))
        for k in ('ux', 'uy', 'p', 'dye'):
            self.assertEqual(float(np.abs(st[k]).max()), 0.0, k)
        self.assertEqual(L.stats(st)['maxvel'], 0.0)
        self.assertEqual(L.stats(st)['divmax'], 0.0)

    def test_zero_with_mask_and_curl(self):
        st = L.new_sim(16, 16, 16, 16)
        mask = np.zeros((16, 16))
        mask[6:10, 6:10] = 1.0
        for e in (0, 1, 2):
            s = st
            for _ in range(50):
                s = L.step(s, prm(edge=e, aspect=1.0), mask=mask)
            self.assertEqual(float(np.abs(s['ux']).max() + np.abs(s['uy']).max() + np.abs(s['dye']).max()), 0.0)


class Projection(unittest.TestCase):
    def test_periodic_converges(self):
        p = prm(edge=1)
        ux, uy = rand_vel(16, 16)
        sol = np.zeros((16, 16))
        d0 = l2(L.pass_div(ux, uy, sol, p))
        prev = d0
        for K in (5, 10, 20, 40, 80):
            gx, gy = project(ux, uy, sol, p, K)
            d = l2(L.pass_div(gx, gy, sol, p))
            self.assertLess(d, prev)                  # monotone in K
            prev = d
        gx, gy = project(ux, uy, sol, p, 200)
        self.assertLess(l2(L.pass_div(gx, gy, sol, p)), 1e-3 * d0)

    def test_k20_reduces_10x_small_grid(self):
        p = prm(edge=1)
        ux, uy = rand_vel(8, 8, 5)
        sol = np.zeros((8, 8))
        d0 = np.abs(L.pass_div(ux, uy, sol, p)).max()
        gx, gy = project(ux, uy, sol, p, 20)
        self.assertLess(np.abs(L.pass_div(gx, gy, sol, p)).max(), d0 / 10.0)

    def test_wall_with_obstacle_converges(self):
        p = prm(edge=0)
        ux, uy = rand_vel(16, 16, 9)
        sol = np.zeros((16, 16))
        sol[5:9, 6:11] = 1.0
        # start from a field that already respects the walls (as fx_pre / fx_vort deliver it)
        X, Y = L.grid(16, 16)
        S = lambda dx, dy: L.fetch(sol, X + dx, Y + dy, L.solid_mode(0), L.solid_const(0))
        ux = np.where((sol > 0.5) | (S(1, 0) > 0.5), 0.0, ux)
        uy = np.where((sol > 0.5) | (S(0, 1) > 0.5), 0.0, uy)
        d0 = l2(L.pass_div(ux, uy, sol, p))
        prev = d0
        for K in (10, 40, 160):
            gx, gy = project(ux, uy, sol, p, K)
            d = l2(L.pass_div(gx, gy, sol, p))
            self.assertLess(d, prev)
            prev = d
        gx, gy = project(ux, uy, sol, p, 2000)
        self.assertLess(l2(L.pass_div(gx, gy, sol, p)), 1e-3 * d0)
        # walls hold: no flow through the box edges or the obstacle
        self.assertEqual(float(np.abs(gx[:, -1]).max()), 0.0)
        self.assertEqual(float(np.abs(gy[-1, :]).max()), 0.0)
        self.assertEqual(float(np.abs(gx[5:9, 5:11]).max()), 0.0)


class Jacobi(unittest.TestCase):
    def test_manufactured_poisson(self):
        N = 32
        p = prm(edge=1)
        X, Y = L.grid(N, N)
        x = (X + 0.5) / N
        y = (Y + 0.5) / N
        true = np.sin(2 * np.pi * x) * np.sin(2 * np.pi * y)
        rhs = -8 * np.pi ** 2 / N ** 2 * true             # continuous Laplacian * h^2
        sol = np.zeros((N, N))
        pr = np.zeros((N, N))

        def resid(q):
            lap = sum(L.fetch(q, X + dx, Y + dy, L.M_WRAP) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))) - 4 * q
            return l2(lap - rhs)

        prev = resid(pr)
        for _ in range(500):
            pr = L.pass_press(pr, rhs, sol, p)
            r = resid(pr)
            self.assertLessEqual(r, prev * (1 + 1e-12))
            prev = r
        self.assertLess(l2(pr - true) / l2(true), 0.05)

    def test_warm_scale(self):
        pin = np.ones((4, 4))
        out = L.pass_press(pin, np.zeros((4, 4)), np.zeros((4, 4)), prm(edge=1), scale=0.5)
        self.assertTrue(np.allclose(out, 0.5))


class Advection(unittest.TestCase):
    def test_one_cell_shift_exact(self):
        N = 32
        p = prm(edge=1, dt=1 / 60.0, veldiss=0.0, dyediss=0.0, aspect=1.0)
        X, Y = L.grid(N, N)
        g = np.exp(-((X - 10.0) ** 2 + (Y - 16.0) ** 2) / 8.0)
        dye = np.stack([g, g * 0.5, g * 0.25], axis=2)
        ux = np.full((N, N), 60.0)                         # 60 cells/s * 1/60 s = 1 cell per step
        uy = np.zeros((N, N))
        sol = np.zeros((N, N))
        out = L.pass_advdye(dye, ux, uy, sol, None, (), p)
        self.assertTrue(np.allclose(out, np.roll(dye, 1, axis=1), atol=1e-12))
        nx, ny = L.pass_advvel(ux, uy, sol, p)
        self.assertTrue(np.allclose(nx, 60.0) and np.allclose(ny, 0.0))

    def test_half_cell_peak_loss_bounded(self):
        N = 64
        p = prm(edge=1, dt=1 / 60.0, dyediss=0.0, aspect=1.0)
        X, Y = L.grid(N, N)
        g = np.exp(-((X - 20.0) ** 2 + (Y - 32.0) ** 2) / 32.0)
        dye = np.stack([g] * 3, axis=2)
        out = L.pass_advdye(dye, np.full((N, N), 30.0), np.zeros((N, N)), np.zeros((N, N)), None, (), p)
        self.assertGreater(out[..., 0].max(), 0.98 * g.max())
        self.assertAlmostEqual(out[..., 0].sum(), g.sum(), delta=1e-9 * g.sum())   # wrap: conservative here

    def test_dissipation_exp(self):
        N = 16
        k, dt, n = 0.7, 1 / 60.0, 120
        p = prm(edge=0, dt=dt, dyediss=k, aspect=1.0)
        dye = np.ones((N, N, 3))
        z = np.zeros((N, N))
        s0 = dye.sum()
        for _ in range(n):
            dye = L.pass_advdye(dye, z, z, z, None, (), p)
        self.assertAlmostEqual(dye.sum() / s0, math.exp(-k * dt * n), delta=1e-6)


class Boundaries(unittest.TestCase):
    def _box(self, e):
        N = 24
        mask = np.zeros((N, N))
        mask[9:15, 9:15] = 1.0
        st = L.new_sim(N, N, N, N)
        st['dye'][:] = 1.0
        sol = L.solid_from_mask(mask, 0.5)
        st['dye'][sol > 0.5] = 0.0
        rows = [L.row(0.25, 0.5, 2.0, 1.0, 0.08, 0.0, 1.0, (0, 0, 0))]
        p = prm(edge=e, aspect=1.0, dyediss=0.0, veldiss=0.0)
        s0 = st['dye'].sum()
        for k in range(100):
            st = L.step(st, p, rows if k < 5 else (), mask=mask)
        return st, sol, s0

    def test_wall_no_dye_or_flow_in_solids(self):
        st, sol, s0 = self._box(0)
        self.assertEqual(float(st['dye'][sol > 0.5].max()), 0.0)
        gx, gy, _ = st['vel']
        self.assertEqual(float(np.abs(gx[9:15, 8:15]).max()), 0.0)
        self.assertEqual(float(np.abs(gy[8:15, 9:15]).max()), 0.0)
        s = L.stats(st, prm(edge=0))
        self.assertGreater(s['maxvel'], 10.0)                    # it did move
        self.assertLess(s['divmax'], 0.05 * s['maxvel'])         # projected
        # backtraces that land in the obstacle bring back 0: measured -9.1 % after 100 steps (semi-Lagrangian)
        self.assertLess(abs(st['dye'].sum() / s0 - 1.0), 0.15)

    def test_wrap_mass(self):
        st, sol, s0 = self._box(1)
        self.assertEqual(float(st['dye'][sol > 0.5].max()), 0.0)
        s = L.stats(st, prm(edge=1))
        self.assertLess(s['divmax'], 0.05 * s['maxvel'])
        self.assertLess(abs(st['dye'].sum() / s0 - 1.0), 0.15)

    def test_blob_drift_no_obstacle(self):
        # measured: wall -3.8 %, wrap +6.1 % after 100 steps (bilinear semi-Lagrangian is not conservative)
        N = 32
        X, Y = L.grid(N, N)
        g = np.exp(-((X - 16.0) ** 2 + (Y - 16.0) ** 2) / 30.0)
        rows = [L.row(0.25, 0.5, 2.0, 1.0, 0.08, 0.0, 1.0, (0, 0, 0))]
        for e in (0, 1):
            st = L.new_sim(N, N, N, N)
            st['dye'][:] = g[..., None]
            p = prm(edge=e, aspect=1.0, dyediss=0.0, veldiss=0.0)
            for k in range(100):
                st = L.step(st, p, rows if k < 5 else ())
            self.assertLess(abs(st['dye'].sum() / (3 * g.sum()) - 1.0), 0.08, e)

    def test_zero_velocity_mass_exact(self):
        N = 12
        st = L.new_sim(N, N, N, N)
        st['dye'][:] = 0.5
        for e in (0, 1):
            s = st
            for _ in range(100):
                s = L.step(s, prm(edge=e, aspect=1.0, dyediss=0.0))
            self.assertAlmostEqual(s['dye'].sum(), st['dye'].sum(), delta=1e-9)


class Flags(unittest.TestCase):
    def test_solid_and_edge_rules(self):
        m = np.zeros((5, 5))
        m[2, 1:5] = 0.9
        m[0, 0] = 0.5                               # not above 0.5
        s = L.solid_from_mask(m, 0.5)
        want = np.zeros((5, 5))
        want[2, 1:5] = 1.0
        self.assertTrue(np.array_equal(s, want))
        X = np.array([-1, 5, 2])
        Y = np.array([2, 2, -1])
        self.assertEqual(list(L.fetch(s, X, Y, L.solid_mode(0), L.solid_const(0))), [1.0, 1.0, 1.0])   # wall
        self.assertEqual(list(L.fetch(s, X, Y, L.solid_mode(1), L.solid_const(1))), [1.0, 0.0, 0.0])   # wrap
        self.assertEqual(list(L.fetch(s, X, Y, L.solid_mode(2), L.solid_const(2))), [0.0, 0.0, 0.0])   # open
        v = np.arange(25.0).reshape(5, 5)
        self.assertEqual(list(L.fetch(v, X, Y, L.vel_mode(0))), [0.0, 0.0, 0.0])
        self.assertEqual(list(L.fetch(v, X, Y, L.vel_mode(1))), [14.0, 10.0, 22.0])
        self.assertEqual(list(L.fetch(v, X, Y, L.vel_mode(2))), [10.0, 14.0, 2.0])
        self.assertEqual(list(L.fetch(v, X, Y, L.pres_mode(0))), [10.0, 14.0, 2.0])
        self.assertEqual(list(L.fetch(v, X, Y, L.pres_mode(2))), [0.0, 0.0, 0.0])


class Clock(unittest.TestCase):
    def test_bpm_ticks_minute(self):
        ticks = []
        t0 = 0.0
        for f in range(1, 3601):
            t1 = f / 60.0
            ticks += L.bpm_ticks(t0, t1, 120.0, 1.0)
            t0 = t1
        self.assertEqual(len(ticks), 120)
        self.assertAlmostEqual(ticks[0], 0.5)
        self.assertTrue(all(abs((b - a) - 0.5) < 1e-9 for a, b in zip(ticks, ticks[1:])))

    def test_bpm_no_drift_one_hour(self):
        n = 0
        last = None
        for f in range(1, 216001):
            tk = L.bpm_ticks((f - 1) / 60.0, f / 60.0, 128.0, 2.0)
            n += len(tk)
            if tk:
                last = tk[-1]
        self.assertEqual(n, int(3600.0 / (60.0 / 128.0 * 2.0) + 1e-9))     # 3840
        self.assertAlmostEqual(last, 3600.0, places=6)

    def test_divs(self):
        for name, beats in L.BPMDIV_BEATS.items():
            self.assertEqual(len(L.bpm_ticks(0.0, 60.0, 120.0, beats)), int(round(120 / beats)), name)

    def test_engine_internal_beats(self):
        st = None
        beats = 0
        for f in range(3600):
            st, o, rows = L.engine_step(st, f / 60.0, {'bpmmode': 'internal', 'bpm': 120.0})
            beats += int(o['beat'])
            if o['beat']:
                self.assertEqual(len(rows), L.NEMIT)          # ring burst on the beat
        self.assertIn(beats, (119, 120))                     # the tick at exactly 60.0 s lands in frame 3600


class Kick(unittest.TestCase):
    def test_refractory(self):
        st = None
        fires = []
        for f in range(60):
            t = f / 60.0
            lvl = 1.0 if f % 4 < 2 else 0.0                  # a trigger every 4 frames (15 Hz)
            st, k = L.kick_step(st, t, lvl, 0.5, 0.15)
            if k:
                fires.append(f)
        self.assertEqual(fires[:3], [0, 12, 24])            # 0.2 s apart: the 4-frame ones inside 0.15 s are blocked

    def test_audio_bursts_loud_vs_quiet(self):
        rate, fps = 48000, 60
        n = rate * 4
        t = np.arange(n) / rate
        sig = np.zeros(n)
        for k in range(8):
            a = 0.8 if k % 2 == 0 else 0.05
            on = (t >= k * 0.5) & (t < k * 0.5 + 0.1)
            sig[on] = a * np.sin(2 * np.pi * 60.0 * t[on])
        block = rate // fps
        st = None
        fired = []
        for f in range(n // block):
            b = sig[f * block:(f + 1) * block].tolist()
            st, o, _ = L.engine_step(st, f / fps, {'audiomode': 'kickburst', 'audiogain': 1.0, 'burstthresh': 0.3},
                                     {'low_block': b, 'level_block': b})
            if o['kick']:
                fired.append(f / fps)
        self.assertEqual(len(fired), 4)
        for x, k in zip(fired, (0, 2, 4, 6)):
            self.assertAlmostEqual(x, k * 0.5, delta=0.04)

    def test_block_rms(self):
        self.assertAlmostEqual(L.block_rms([[1.0, -1.0], [1.0, -1.0]]), 1.0)
        self.assertEqual(L.block_rms([]), 0.0)


class Emitters(unittest.TestCase):
    def test_pack_roundtrip(self):
        rows = L.ring_burst(0, dict(L.ENGINE_DEFAULTS))
        ch = L.pack_rows(rows)
        self.assertEqual([len(c) for c in ch], [24] * 4)
        back = L.unpack_rows(ch)
        self.assertEqual(len(back), 8)
        self.assertTrue(np.allclose(np.array(back), np.array(rows)))
        self.assertEqual(L.unpack_rows(L.pack_rows([])), [])

    def test_ring_symmetric(self):
        rows = L.ring_burst(3, dict(L.ENGINE_DEFAULTS))
        self.assertAlmostEqual(sum(r[2] for r in rows), 0.0, places=12)
        self.assertAlmostEqual(sum(r[3] for r in rows), 0.0, places=12)
        a = L.ENGINE_DEFAULTS['aspect']
        for r in rows:                                       # on a screen circle of Burstring
            self.assertAlmostEqual(math.hypot((r[0] - 0.5) * a, r[1] - 0.5), 0.12, places=12)

    def test_manual_burst_and_patterns(self):
        for pat, n in (('ring', 8), ('sweep', 8), ('random', 3)):
            _, o, rows = L.engine_step(None, 0.0, {'bpmpattern': pat}, {}, ['burst'])
            self.assertEqual(len(rows), n, pat)
        pts = [{'x': 0.2, 'y': 0.3, 'vx': 0.0, 'vy': 1.0, 'radius': 0.05, 'strength': 1.0, 'col': (1, 1, 1)}]
        _, o, rows = L.engine_step(None, 0.0, {'bpmpattern': 'points'}, {'points': pts}, ['burst'])
        self.assertEqual(len(rows), 2)                       # 1 burst row + the continuous point
        self.assertAlmostEqual(rows[0][3], 1.0)

    def test_points_from_chans(self):
        p = dict(L.ENGINE_DEFAULTS)
        pts = L.points_from_chans({'x': [0.1, 0.9], 'y': [0.2, 0.8], 'vx': [1.0, 0.0]}, p)
        self.assertEqual(len(pts), 2)
        self.assertEqual(pts[0]['radius'], p['emitradius'])
        self.assertEqual(pts[1]['col'], p['emitcolor'])
        self.assertEqual(L.points_from_chans({'tx': [0.1]}, p), [])

    def test_testmodes(self):
        st = None
        for f in range(30):
            st, o, rows = L.engine_step(st, f / 60.0, {'testmode': 'zero', 'bpmmode': 'internal'}, {}, ['burst'])
            self.assertEqual(rows, [])
            self.assertEqual((o['srcon'], o['forceon']), (0.0, 0.0))
        st = None
        got = []
        for f in range(30):
            st, o, rows = L.engine_step(st, f / 60.0, {'testmode': 'fixed', 'seed': 4})
            if rows:
                got.append(int(o['steps']) - 1)
        self.assertEqual(got, list(L.FIXED_STEPS))
        self.assertEqual(L.fixed_splats(4, 10), L.fixed_splats(4, 10))
        self.assertNotEqual(L.fixed_splats(4, 10), L.fixed_splats(5, 10))

    def test_pause_step_stopat(self):
        st, o, _ = L.engine_step(None, 0.0, {'pause': True})
        self.assertEqual((o['run'], o['dt'], o['steps']), (0.0, 0.0, 0.0))
        st, o, _ = L.engine_step(st, 1 / 60.0, {'pause': True}, {}, ['step'])
        self.assertEqual((o['run'], o['steps']), (1.0, 1.0))
        self.assertAlmostEqual(o['dt'], 1 / 60.0)
        st = None
        for f in range(10):
            st, o, _ = L.engine_step(st, f / 60.0, {'stopat': 6})
        self.assertEqual((o['steps'], o['run']), (6.0, 0.0))
        st, o, _ = L.engine_step(st, 1.0, {'stopat': 6}, {}, ['reset'])
        self.assertEqual(o['steps'], 1.0)

    def test_dt(self):
        self.assertAlmostEqual(L.frame_dt('auto', 0.5, 1.0, 60.0), 1 / 60.0)
        self.assertAlmostEqual(L.frame_dt('auto', 0.5, 2.0, 30.0), 2 / 30.0)
        self.assertAlmostEqual(L.frame_dt('fixed', 0.01, 0.5, 60.0), 0.005)

    def test_engine_params_getter(self):
        vals = {}
        for _, pars in L.PAGES:
            for name, style, default, _o in pars:
                if style == 'RGB':
                    for c, v in zip('rgb', default):
                        vals[name + c] = v
                elif style != 'Pulse':
                    vals[name] = default
        p = L.engine_params(lambda n: vals[n], 60.0)
        self.assertEqual(p['palette'], L.DEFAULT_PALETTE)
        self.assertAlmostEqual(p['aspect'], 1080 / 1920.0)
        self.assertEqual(p['bpmdiv'], 'b1')

    def test_stir(self):
        _, o, rows = L.engine_step(None, 0.0, {'audiomode': 'levelstir', 'audiogain': 1.0}, {'level': 0.5, 'low': 0.25})
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(math.hypot(rows[0][2], rows[0][3]), 0.5)


class Look(unittest.TestCase):
    def test_modes(self):
        dye = np.zeros((2, 2, 3))
        dye[0, 0] = (0.5, 0.25, 0.0)
        z = np.zeros((2, 2))
        o = L.pass_look(dye, z, z, prm(), {'mode': 0, 'alpha': 0, 'bg': (0.0, 0.0, 1.0)})
        self.assertTrue(np.allclose(o[0, 0], (0.5, 0.25, 0.5, 1.0)))   # bg * (1 - density 0.5)
        self.assertTrue(np.allclose(o[1, 1], (0, 0, 1, 1)))
        o = L.pass_look(dye, z, z, prm(), {'mode': 0, 'alpha': 1, 'premult': False})
        self.assertTrue(np.allclose(o[0, 0], (1.0, 0.5, 0.0, 0.5)))
        o = L.pass_look(dye, z, z, prm(), {'mode': 1, 'alpha': 1, 'premult': True})
        want = np.array(L.palette_at(L.DEFAULT_PALETTE, 0.5)) * 0.5
        self.assertTrue(np.allclose(o[0, 0, :3], want))
        o = L.pass_look(dye, z, z, prm(), {'mode': 0, 'alpha': 1, 'exposure': 1.0, 'gamma': 1.0})
        self.assertTrue(np.allclose(o[0, 0, :3], (1.0, 0.5, 0.0)))

    def test_palette_ends(self):
        self.assertEqual(L.palette_at(L.DEFAULT_PALETTE, -1), L.DEFAULT_PALETTE[0])
        self.assertTrue(np.allclose(L.palette_at(L.DEFAULT_PALETTE, 1.0), L.DEFAULT_PALETTE[4]))
        self.assertTrue(np.allclose(L.palette_at(L.DEFAULT_PALETTE, 0.25), L.DEFAULT_PALETTE[1]))


class Reference(unittest.TestCase):
    def test_pause_copies(self):
        st = L.run_fixed(steps=12, simh=16, resw=32, resh=32)
        st2 = L.step(st, prm(), run=False)
        for k in ('ux', 'uy', 'p', 'dye'):
            self.assertTrue(np.array_equal(st[k], st2[k]))

    def test_fixed_run_deterministic_and_finite(self):
        a = L.run_fixed(steps=30, simh=32, resw=64, resh=64)
        b = L.run_fixed(steps=30, simh=32, resw=64, resh=64)
        self.assertTrue(np.array_equal(a['dye'], b['dye']) and np.array_equal(a['ux'], b['ux']))
        s = L.stats(a, prm(aspect=1.0))
        self.assertTrue(all(math.isfinite(v) for v in s.values()))
        self.assertGreater(s['maxvel'], 1.0)
        self.assertGreater(s['dyesum'], 1.0)
        self.assertLess(s['divmax'], 0.25 * s['maxvel'])    # projected (K = 20 from a warm start)

    def test_rel_l2(self):
        self.assertEqual(L.rel_l2([1.0, 2.0], [1.0, 2.0]), 0.0)
        self.assertAlmostEqual(L.rel_l2([0.0, 0.0], [3.0, 4.0]), 1.0)

    def test_sim_size(self):
        self.assertEqual(L.sim_size(1080, 1920, 456), (256, 456))
        self.assertEqual(L.sim_size(128, 128, 64), (64, 64))
        self.assertEqual(L.sim_size(1920, 1080, 256), (455, 256))


def _read(name):
    with open(os.path.join(GLSL, name)) as f:
        return f.read()


def _decl(src, kind):
    return set(re.findall(r'uniform\s+%s\s+(\w+)\s*;' % kind, src))


class PerfQuality(unittest.TestCase):
    """Perf pass (26 Oct): Quality scales the dye grid only; idle sleep wakes on any injection."""

    def test_dye_size(self):
        self.assertEqual(L.dye_size(1080, 1920, 'high'), (1080, 1920))
        self.assertEqual(L.dye_size(1080, 1920, 'balanced'), (810, 1440))
        self.assertEqual(L.dye_size(1080, 1920, 'fast'), (540, 960))
        self.assertEqual(L.dye_size(1080, 1920, 'bogus'), (1080, 1920))
        self.assertEqual(dict(L.PASSES)['look']['res'], 'out')
        self.assertEqual(dict(L.PASSES)['advdye']['res'], 'dye')

    def test_sleep_after(self):
        self.assertIsNone(L.sleep_after(0.0))
        t = L.sleep_after(1.0, 0.0)
        self.assertAlmostEqual(L.SLEEP_DYE_PEAK * math.exp(-t), L.SLEEP_FLOOR, places=9)
        self.assertGreater(L.sleep_after(1.0, 2.0), t)

    def test_engine_sleeps_and_wakes(self):
        p = {'idlesleep': True, 'dyediss': 1.0}
        lim = L.sleep_after(1.0)
        st, o, _ = L.engine_step(None, 0.0, p, {}, ['burst'])
        self.assertEqual(o['awake'], 1.0)
        st, o, _ = L.engine_step(st, lim - 0.1, p)
        self.assertEqual(o['awake'], 1.0)
        st, o, _ = L.engine_step(st, lim + 0.1, p)
        self.assertEqual(o['awake'], 0.0)
        st, o, rows = L.engine_step(st, lim + 0.2, p, {}, ['burst'])
        self.assertTrue(rows)
        self.assertEqual(o['awake'], 1.0)
        st, o, _ = L.engine_step(st, lim * 3, p, {'srcwired': 1})
        self.assertEqual(o['awake'], 1.0)
        st, o, _ = L.engine_step(st, lim * 5, dict(p, pause=True))
        self.assertEqual(o['awake'], 1.0)
        _, o, _ = L.engine_step(st, lim * 9, dict(p, idlesleep=False))
        self.assertEqual(o['awake'], 1.0)


class ShaderContract(unittest.TestCase):
    def test_common_constants(self):
        c = _read('fluid2d_common.glsl')
        self.assertIn('#define NEMIT %d' % L.NEMIT, c)
        self.assertIn('#define EMIT_TEXELS %d' % L.EMIT_TEXELS, c)
        self.assertIn('#define INV_BETA %s' % L.INV_BETA, c)
        self.assertEqual(float(re.search(r'#define VORT_EPS (\S+)', c).group(1)), L.VORT_EPS)
        for k, v in (('M_CLAMP', L.M_CLAMP), ('M_WRAP', L.M_WRAP), ('M_CONST', L.M_CONST)):
            self.assertIn('#define %s %d' % (k, v), c)
        self.assertIn('exp(-dot(dp, dp) / (r * r))', c)
        self.assertIn('vec2(aspect, 1.0)', c)

    def test_every_pass(self):
        names = [n for n, _ in L.PASSES]
        files = sorted(f for f in os.listdir(GLSL) if f.startswith('fluid2d_') and f.endswith('.glsl'))
        variants = {'press_blocked': 'press'}             # perf lane 2: blocked press = the press pass's contract, 16x16
        self.assertEqual(sorted(files), sorted(['fluid2d_common.glsl'] + ['fluid2d_%s.glsl' % n for n in names]
                                               + ['fluid2d_%s.glsl' % v for v in variants]))
        for n, spec in list(L.PASSES) + [(v, dict(L.PASSES)[b]) for v, b in variants.items()]:
            src = _read('fluid2d_%s.glsl' % n)
            wg = 16 if n == 'press_blocked' else L.WG
            self.assertIn('layout (local_size_x = %d, local_size_y = %d) in;' % (wg, wg), src, n)
            self.assertIn('TDImageStoreOutput(0, ivec3(T, 0)', src, n)
            self.assertIn('uTDOutputInfo.res.zw', src, n)
            self.assertNotIn('#version', src, n)
            self.assertNotIn('fragColor', src, n)
            self.assertNotIn('gl_FragCoord', src, n)
            self.assertNotIn('texture(', src, n)            # compute: textureLod / texelFetch only
            self.assertEqual(_decl(src, 'vec4'), set(spec['vecs']), n)
            self.assertEqual(_decl(src, 'samplerBuffer'), set(spec['arrays']), n)
            used = set(int(i) for i in re.findall(r'sTD2DInputs\[(\d+)\]', src))
            self.assertTrue(used, n)
            self.assertLess(max(used), len(spec['inputs']), n)   # never reads an unwired input
            self.assertLessEqual(len(spec['inputs']), 3, n)      # GLSL TOP: max 3 wired inputs
            self.assertTrue(all(ord(ch) < 128 for ch in src), n)
            for m in re.finditer(r'texelFetch\(uEmit, ([^)]*)\)', src):
                self.assertIn('EMIT_TEXELS', m.group(1), n)
            if spec['arrays']:
                self.assertIn('textureSize(uEmit) / EMIT_TEXELS', src, n)   # T-35: no out-of-range buffer reads
        self.assertIn('TDOutputSwizzle(', _read('fluid2d_look.glsl'))

    def test_vec_slots_fit(self):
        for n, spec in L.PASSES:
            self.assertLessEqual(len(spec['vecs']), 8, n)

    def test_par_names(self):
        seen = set()
        for _, pars in L.PAGES:
            for name, style, default, o in pars:
                self.assertRegex(name, r'^[A-Z][a-z0-9]+$')
                self.assertNotIn(name, seen)
                seen.add(name)
                if style == 'Menu':
                    self.assertIn(default, o['names'])
                    self.assertEqual(len(o['names']), len(o['labels']))
        for fn in ('fluid2d_logic.py', 'fluid2d.py'):
            with open(os.path.join(BUILDERS, fn)) as f:
                self.assertTrue(all(ord(ch) < 128 for ch in f.read()), fn)


# ---------------------------------------------------------------- builder dry run against a minimal fake TD
class _Par(object):
    def __init__(self, name, val=None):
        self.name, self.val, self.expr, self.mode, self.default = name, val, None, None, None
        self.menuNames, self.menuLabels, self.pulses = [], [], 0

    def eval(self):
        return self.val

    def pulse(self):
        self.pulses += 1

    @property
    def menuIndex(self):
        return self.menuNames.index(self.val) if self.val in self.menuNames else 0


class _Pars(object):
    def __init__(self):
        object.__setattr__(self, '_d', {})

    def _get(self, name, create):
        d = object.__getattribute__(self, '_d')
        if name not in d and create:
            d[name] = _Par(name)
        return d.get(name)

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)
        return self._get(name, not name[:1].isupper())   # custom (Capitalised) pars exist only once appended

    def __setattr__(self, name, v):
        self._get(name, True).val = v


class _Page(object):
    def __init__(self, o, name):
        self.o, self.name = o, name

    def _add(self, names):
        ps = []
        for n in names:
            p = _Par(n)
            object.__getattribute__(self.o.par, '_d')[n] = p
            ps.append(p)
        return ps

    def appendFloat(self, n, label=None):
        return self._add([n])
    appendInt = appendMenu = appendToggle = appendPulse = appendCHOP = appendStr = appendFloat

    def appendRGB(self, n, label=None):
        return self._add([n + 'r', n + 'g', n + 'b'])


class _Conn(object):
    def __init__(self, o, i):
        self.o, self.i = o, i

    def connect(self, src):
        ins = self.o.inputs
        while len(ins) <= self.i:
            ins.append(None)
        ins[self.i] = src


class _Seq(object):
    def __init__(self):
        self.numBlocks = 1


class _OP(object):
    family = 'TOP'

    def __init__(self, parent, name):
        self.parent_, self.name, self.children, self.inputs = parent, name, [], []
        self.par, self.valid, self.viewer, self.comment, self.docked = _Pars(), True, False, '', []
        self.text, self.customPages, self.allowCooking = '', [], False
        self.seq = type('S', (), {})()
        self.seq.vec, self.seq.array = _Seq(), _Seq()
        self.inputConnectors = [_Conn(self, i) for i in range(8)]

    @property
    def OPType(self):
        return type(self).__name__

    @property
    def path(self):
        return (self.parent_.path if self.parent_ else '') + '/' + self.name

    def op(self, name):
        return next((o for o in self.children if o.name == name), None)

    def create(self, cls, name):
        o = cls(self, name)
        self.children.append(o)
        return o

    def appendCustomPage(self, name):
        pg = _Page(self, name)
        self.customPages.append(pg)
        return pg


_CLASSES = dict((n, type(n, (_OP,), {})) for n in (
    'baseCOMP', 'textDAT', 'constantTOP', 'inTOP', 'switchTOP', 'resolutionTOP', 'inCHOP', 'audiofilterCHOP',
    'scriptCHOP', 'parameterexecuteDAT', 'feedbackTOP', 'glslTOP', 'outTOP', 'analyzeTOP', 'toptoCHOP', 'outCHOP'))


class UniRows(unittest.TestCase):
    """perf 28 Oct: the uni CHOP's rows = the old par expressions, evaluated the same way (bit-exact uniforms)."""
    def test_rows_match_old_expressions(self):
        ns = {}
        with open(os.path.join(BUILDERS, 'fluid2d.py')) as f:
            exec(compile(f.read(), 'fluid2d.py', 'exec'), ns)
        vx = ns['_vec_exprs']()
        g = {}
        exec(ns['uni_text'](vx).split('def onCook')[0].replace('import numpy as np', ''), g)
        eng = {'dt': 0.016666668, 'run': 1.0, 'forceon': 1.0, 'srcon': 0.0}
        pv = {'Dyediss': 1.0, 'Srcgain': 2.5, 'Curl': 30.0, 'Forcegain': 1.7, 'Maskthresh': 0.5, 'Veldiss': 0.2,
              'Resw': 1080, 'Resh': 1920}

        class _P(object):
            def __init__(self, v, mi=None):
                self.v, self.menuIndex = v, mi

            def eval(self):
                return self.v

            def __float__(self):
                return float(self.v)

        class _PP(object):
            pass
        P = _PP()
        P.par = _PP()
        for k, v in pv.items():
            setattr(P.par, k, _P(v))
        P.par.Dyeblend, P.par.Edge = _P('add', 0), _P('wrap', 1)
        rows = g['uni_rows'](lambda n: eng.get(n, 0.0), P)

        class _Ch(object):
            def __init__(self, v):
                self.v = v

            def eval(self):
                return self.v

            def __getitem__(self, n):
                return _Ch(eng[n])

            def __ne__(self, o):
                return o is not None
        old_ns = {'parent': lambda: P, 'op': lambda n: _Ch(0) if n == 'engine' else None}
        for k, u in enumerate(g['UNI_VECS']):
            want = [float(eval(str(e), old_ns)) for e in vx[u]]
            self.assertEqual(rows[k], want, u)


class BuilderDryRun(unittest.TestCase):
    def _ns(self):
        root = _CLASSES['baseCOMP'](None, 'project1')
        lab = root.create(_CLASSES['baseCOMP'], 'lab')
        self.destroyed, self.layouts = [], []

        def safe_destroy(o):
            o.valid = False
            o.parent_.children.remove(o)
            self.destroyed.append(o.name)

        def layout_stages(c, stages, colors=True, arrange='mixed'):
            for s in stages:
                for n in s['ops']:
                    assert c.op(n) is not None, n
            self.layouts.append(stages)
            return 'ok'

        handlers = type('H', (), {'module': type('M', (), {'safe_destroy': staticmethod(safe_destroy),
                                                            'layout_stages': staticmethod(layout_stages)})})

        def op(path):
            if path == '/project1/lab':
                return lab
            if path == '/jazib_mcp/handlers':
                return handlers
            return None

        ns = dict(_CLASSES)
        ns.update({'op': op, 'ParMode': type('PM', (), {'EXPRESSION': 'expr', 'CONSTANT': 'const'}), '__name__': 'fluid2d_dry'})
        with open(os.path.join(BUILDERS, 'fluid2d.py')) as f:
            exec(compile(f.read(), 'fluid2d.py', 'exec'), ns)
        return ns, lab

    def test_build_chain_twice_then_fewer_iterations(self):
        ns, lab = self._ns()
        r = ns['build']('/project1/lab', panel=False, press_mode='chain')
        c = lab.op('BN_fluid2d')
        c.par.Iterations.val = 20
        r = ns['build']('/project1/lab', panel=False, press_mode='chain')
        self.assertEqual(r['press'], 'chain x20')
        g = [o for o in c.children if o.OPType == 'glslTOP']
        self.assertEqual(len(g), 8 + 20)
        self.assertEqual(c.op('press_fb').par.top.val, 'fx_press_20')
        self.assertEqual(c.op('vel_fb').par.top.val, 'fx_advvel')
        self.assertEqual(c.op('dye_fb').par.top.val, 'fx_advdye')
        self.assertIs(c.op('fx_press_01').inputs[0], c.op('press_fb'))
        self.assertIs(c.op('fx_press_02').inputs[0], c.op('fx_press_01'))
        self.assertIs(c.op('fx_grad').inputs[0], c.op('fx_press_20'))
        self.assertEqual(c.op('fx_press_01').par.vec0valuex.expr, 'parent().par.Warmstart')   # uStep is in uV now
        self.assertEqual(c.op('fx_press_02').par.vec0valuex.expr, '1')
        uv = ns['uni_vecs'](ns['_vec_exprs']())
        self.assertEqual(uv, ['uDye', 'uForce', 'uStep'])
        self.assertEqual([o.name for o in c.op('fx_advdye').inputs], ['dye_fb', 'fx_grad', 'src_prep'])
        for name, spec in L.PASSES:
            o = c.op('fx_' + name) or c.op('fx_press_01')
            self.assertEqual(o.par.mode.val, 'compute', name)
            self.assertEqual(o.par.format.val, spec['fmt'], name)
            plain = [u for u in spec['vecs'] if u not in uv]
            self.assertEqual(o.seq.vec.numBlocks, max(1, len(plain)), name)
            self.assertEqual([getattr(o.par, 'vec%dname' % k).val for k in range(len(plain))], plain, name)
            arrs = [(getattr(o.par, 'array%dname' % k).val, getattr(o.par, 'array%dchop' % k).val,
                     getattr(o.par, 'array%darraytype' % k).val) for k in range(o.seq.array.numBlocks)]
            if plain != spec['vecs']:                  # perf 28 Oct: engine-fed vecs come from the uni CHOP as uV
                self.assertIn(('uV', 'uni', 'uniformarray'), arrs, name)
                code_ = c.op(o.par.computedat.val).text
                self.assertIn('uniform vec4 uV[3];', code_, name)
                for k, u in enumerate(uv):
                    if u in spec['vecs']:
                        self.assertIn('#define %s uV[%d]' % (u, k), code_, name)
                        self.assertNotIn('uniform vec4 %s;' % u, code_, name)
            else:
                self.assertNotIn('uV', [a[0] for a in arrs], name)
            for k in range(o.seq.vec.numBlocks):        # no engine-reading expressions left on any GLSL TOP
                for ax in 'xyzw':
                    self.assertNotIn("op('engine')", str(getattr(o.par, 'vec%dvalue%s' % (k, ax)).expr), name)
            self.assertLessEqual(len(o.inputs), 3, name)
            code = c.op(o.par.computedat.val).text
            self.assertIn('#define NEMIT', code)
            self.assertIn('layout (local_size_x = 8', code)
        self.assertEqual(c.op('fx_pre').par.array0chop.val, 'emit')
        self.assertEqual(c.op('fx_pre').par.array0arraytype.val, 'texturebuffer')
        self.assertIs(c.op('uni').inputs[0], c.op('engine'))
        self.assertIn("[float(_e('dt')), float(_e('run')), float(P.par.Edge.menuIndex)", c.op('uni_callbacks').text)
        for n in ('out1', 'out2', 'out3', 'engine_callbacks', 'emit_callbacks', 'stats_callbacks', 'fluid2d_logic'):
            self.assertIsNotNone(c.op(n), n)
        self.assertIn('def onCook', c.op('engine_callbacks').text)
        n_ops = len(c.children)
        ns['build']('/project1/lab', panel=False, press_mode='chain')   # idempotent
        self.assertEqual(len(c.children), n_ops)
        self.assertEqual(self.destroyed, [])
        c.par.Iterations.val = 12
        r = ns['build']('/project1/lab', panel=False, press_mode='chain')
        self.assertEqual(r['press'], 'chain x12')
        self.assertIsNone(c.op('fx_press_13'))
        self.assertEqual(sorted(self.destroyed), sorted('fx_press_%02d' % k for k in range(13, 21)))
        self.assertEqual(c.op('press_fb').par.top.val, 'fx_press_12')
        self.assertEqual(len(self.layouts), 4)

    def test_build_npasses(self):
        ns, lab = self._ns()
        ns['build']('/project1/lab', panel=False, press_mode='chain')
        r = ns['build']('/project1/lab', panel=False, press_mode='npasses')   # live: pass n+1 reads pass n
        c = lab.op('BN_fluid2d')
        self.assertEqual(r['press'], 'npasses x8')
        self.assertIsNone(c.op('fx_press_01'))
        self.assertIs(c.op('fx_grad').inputs[0], c.op('fx_press'))
        self.assertEqual(c.op('press_fb').par.top.val, 'fx_press')
        self.assertTrue(c.op('fx_press_compute').text.startswith('#define FLUID2D_NPASSES'))

    def test_build_blocked_default(self):
        """perf lane 2: default = blocked (8 Jacobi iterations per dispatch in shared memory, ceil(N / 8) passes)."""
        ns, lab = self._ns()
        ns['build']('/project1/lab', panel=False, press_mode='chain')
        r = ns['build']('/project1/lab', panel=False)
        c = lab.op('BN_fluid2d')
        self.assertEqual(r['press'], 'blocked x8')
        self.assertIsNone(c.op('fx_press_01'))
        g = c.op('fx_press')
        self.assertIs(c.op('fx_grad').inputs[0], g)
        self.assertEqual(c.op('press_fb').par.top.val, 'fx_press')
        t = c.op('fx_press_compute').text
        self.assertFalse(t.startswith('#define FLUID2D_NPASSES'))
        self.assertIn('#define KB 8', t)
        self.assertIn('// 8', g.par.npasses.expr)
        for n, want in ((8, 1), (12, 2), (1, 1), (16, 2), (17, 3)):
            self.assertEqual(eval(g.par.npasses.expr.replace('int(parent().par.Iterations.eval())', str(n))), want)


if __name__ == '__main__':
    unittest.main()
