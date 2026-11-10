"""Offline tests for builders/cloth_logic.py + the cloth GLSL contract (no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_cloth.py'
Spec: docs/research/BN_fluid_cloth_sims.md 6.4 (numbers adapted to the small-steps solver, docs/builds/cloth.md)."""
import math
import os
import re
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'builders'))
import cloth_logic as L  # noqa: E402

GLSL = os.path.join(REPO, 'builders', 'glsl')
SHADERS = ['cloth_substep', 'cloth_rest', 'cloth_init', 'cloth_nrm', 'cloth_pos', 'cloth_stats', 'cloth_cov',
           'cloth_vert', 'cloth_frag']


def sim(frames, p, mask=None, events_fn=None, inp_fn=None, jelly=False, perturb=None):
    """Run engine + reference solver for `frames` at 60 fps. Returns (P, V, rest, pin, rows list, outs)."""
    W, H = int(p.get('gridw', 16)), int(p.get('gridh', 16))
    q = dict(L.DEFAULTS, **p)
    rest, pin = L.rest_arrays(W, H, q['sizew'], q['sizeh'], q['orient'], q['top'], q['pins'], mask)
    P = rest.copy() if perturb is None else perturb(rest.copy())
    V = np.zeros_like(P)
    st, outs, rowsl = None, [], []
    qq = (1.0, 0.0, 0.0, 0.0)
    for f in range(frames):
        ev = events_fn(f) if events_fn else ()
        inp = inp_fn(f) if inp_fn else {}
        st, o = L.step(st, f / 60.0, inp, q, ev)
        rows = o['rows']
        if jelly:
            rows, qq = L.jelly_rows_ref(P, rest, rows, qq)
        if f == 0 and perturb is not None:      # the engine's first frame is a reset: keep the perturbed start
            rows = list(rows)
            rows[L.ROW['R_GRAV']] = rows[L.ROW['R_GRAV']][:3] + (0.0,)
        P, V = L.frame_ref(P, V, rest, pin, rows)
        outs.append(o)
        rowsl.append(rows)
    return P, V, rest, pin, rowsl, outs


class Rest(unittest.TestCase):
    def test_rest_is_stable(self):
        P, V, rest, _, _, _ = sim(500, {'gridw': 12, 'gridh': 12, 'testmode': 'rest', 'pins': 'none', 'substeps': 4})
        self.assertLess(float(np.abs(P - rest).max()), 1e-7)
        self.assertLess(float(np.abs(V).max()), 1e-12)

    def test_all_pinned_stays_exact(self):
        mask = np.ones((10, 10))
        P, _, rest, _, _, _ = sim(200, {'gridw': 10, 'gridh': 10, 'pins': 'mask', 'windmode': 'constant'}, mask)
        self.assertEqual(float(np.abs(P - rest).max()), 0.0)

    def test_rest_shape(self):
        R, pin = L.rest_arrays(5, 3, 2.0, 1.0, 'vertical', 1.5, 'top')
        self.assertEqual(tuple(R[2, 4]), (1.0, 1.5, 0.0))            # top right
        self.assertEqual(tuple(R[0, 0]), (-1.0, 0.5, 0.0))           # bottom left
        self.assertEqual(pin[2].tolist(), [1.0] * 5)
        self.assertEqual(float(pin[:2].sum()), 0.0)
        Rh, _ = L.rest_arrays(5, 3, 2.0, 1.0, 'horizontal', 0.7, 'none')
        self.assertTrue(np.all(Rh[..., 1] == 0.7))
        self.assertAlmostEqual(float(Rh[2, 0, 2]), -0.5)
        self.assertEqual(L.rest_point(4, 2, 5, 3, 2.0, 1.0, 'vertical', 1.5), (1.0, 1.5, 0.0))
        self.assertEqual(L.rest_centroid(2.0, 1.0, 'vertical', 1.5), (0.0, 1.0, 0.0))
        self.assertAlmostEqual(float(R.reshape(-1, 3).mean(axis=0)[1]), 1.0)

    def test_pin_modes(self):
        W, H = 6, 5
        cnt = {m: sum(L.pinned(i, j, W, H, m) for i in range(W) for j in range(H)) for m in L.PINMODES[:4]}
        self.assertEqual(cnt, {'none': 0, 'top': 6, 'topcorners': 2, 'corners': 4})
        self.assertTrue(L.pinned(0, 0, W, H, 'mask', 0.6))
        self.assertFalse(L.pinned(0, 0, W, H, 'mask', 0.4))


class Hanging(unittest.TestCase):
    P = {'gridw': 24, 'gridh': 24, 'pins': 'top', 'windmode': 'off', 'tethers': False}

    def stretch(self, frames=150, **kw):
        P, V, _, _, rows, _ = sim(frames, dict(self.P, **kw))
        return L.structural_stretch(P, rows[-1]), float(np.abs(V).max())

    def test_more_substeps_less_stretch(self):
        means = [self.stretch(substeps=s)[0][1] for s in (2, 4, 8, 16)]
        self.assertTrue(all(a > b for a, b in zip(means, means[1:])), means)
        self.assertLess(means[-1], 0.02)                            # 24x24, 16 substeps: ~1.3% mean
        self.assertGreater(means[0], 4 * means[-1])                 # why Substeps is exposed

    def test_tethers_remove_hanging_stretch(self):
        (mx, mean), _ = self.stretch(substeps=8, tethers=True)
        self.assertLess(mx, 0.005)
        (mx0, _), _ = self.stretch(substeps=8, tethers=False)
        self.assertGreater(mx0, 10 * mx)

    def test_energy_decays(self):
        P, V, rest, pin, rows, _ = sim(90, dict(self.P, substeps=8))
        e = []
        for k in range(60):
            P, V = L.frame_ref(P, V, rest, pin, rows[-1])
            e.append(float(L.stats_ref(P, V, rest, pin, rows[-1])[..., 1].sum()))
        self.assertLess(np.mean(e[-10:]), np.mean(e[:10]))
        self.assertLess(e[-1], 0.05)


class Compliance(unittest.TestCase):
    def test_compliance_softens(self):
        base = {'gridw': 16, 'gridh': 16, 'pins': 'top', 'windmode': 'off', 'tethers': False, 'substeps': 8}
        s = []
        for c in (0.0, 1e-3, 1e-2):
            P, _, _, _, rows, _ = sim(120, dict(base, stretch=c, shear=c))
            s.append(L.structural_stretch(P, rows[-1])[1])
        self.assertTrue(s[0] < s[1] < s[2], s)

    def test_xpbd_substep_invariance(self):
        """XPBD: with a soft compliance the static stretch is set by the material, so 8 vs 16 substeps differ by
        less than 2x (plain PBD stiffness would depend on the step count)."""
        base = {'gridw': 12, 'gridh': 12, 'pins': 'top', 'windmode': 'off', 'tethers': False, 'stretch': 0.02,
                'shear': 0.02, 'bend': 1.0}
        a = L.structural_stretch(sim(150, dict(base, substeps=8))[0], sim(1, dict(base, substeps=8))[4][-1])[1]
        b = L.structural_stretch(sim(150, dict(base, substeps=16))[0], sim(1, dict(base, substeps=16))[4][-1])[1]
        self.assertLess(max(a, b) / min(a, b), 2.0, (a, b))


class Collide(unittest.TestCase):
    BASE = {'gridw': 20, 'gridh': 20, 'pins': 'none', 'orient': 'horizontal', 'top': 1.0, 'windmode': 'off',
            'substeps': 8, 'sphere1on': True, 'sphere1x': 0.0, 'sphere1y': 0.3, 'sphere1z': 0.0, 'sphere1r': 0.3,
            'thickness': 0.01}

    def test_never_inside_sphere(self):
        P, _, _, _, _, _ = sim(300, self.BASE)
        d = np.linalg.norm(P - np.array([0.0, 0.3, 0.0]), axis=-1)
        self.assertGreaterEqual(float(d.min()), 0.3 + 0.01 - 1e-9)
        self.assertLess(float(d.min()), 0.32)                      # it rests on it

    def test_friction_changes_drape(self):
        spread = []
        for fr in (0.0, 1.0):
            P, _, _, _, _, _ = sim(150, dict(self.BASE, friction=fr))
            spread.append(float(np.ptp(P[..., 0])))
        self.assertGreater(abs(spread[0] - spread[1]), 1e-3, spread)

    def test_floor(self):
        P, _, _, _, _, _ = sim(120, {'gridw': 10, 'gridh': 10, 'pins': 'none', 'orient': 'horizontal', 'top': 0.5,
                                     'windmode': 'off', 'floor': True, 'floory': -0.2, 'thickness': 0.0,
                                     'substeps': 4})
        self.assertGreaterEqual(float(P[..., 1].min()), -0.2 - 1e-12)
        self.assertLess(float(P[..., 1].max()), -0.15)

    def test_colliders_from_chop_fill_free_slots(self):
        p = dict(L.DEFAULTS, sphere2on=True)
        _, o = L.step(None, 0.0, {'colliders': [(1, 2, 3, 0.5), (4, 5, 6, 0.1), (7, 8, 9, 1), (0, 0, 0, 2)]}, p)
        r = o['rows']
        self.assertEqual(r[L.ROW['R_SPH0']], (0.0, 0.0, 0.0, 0.2))
        self.assertEqual(r[L.ROW['R_SPH1']], (1.0, 2.0, 3.0, 0.5))
        self.assertEqual(r[L.ROW['R_SPH3']], (7.0, 8.0, 9.0, 1.0))
        _, o = L.step(None, 0.0, {}, L.DEFAULTS)
        self.assertTrue(all(o['rows'][L.ROW['R_SPH0'] + k][3] < 0 for k in range(4)))


class Pins(unittest.TestCase):
    def test_pins_hold_then_release(self):
        p = {'gridw': 12, 'gridh': 12, 'pins': 'topcorners', 'windmode': 'off', 'substeps': 4}
        ev = lambda f: ('release',) if f == 30 else ()
        W, H = 12, 12
        P, _, rest, _, _, outs = sim(30, p)
        for (i, j) in ((0, H - 1), (W - 1, H - 1)):
            self.assertEqual(tuple(P[j, i]), tuple(rest[j, i]))
        P2, _, _, _, _, outs = sim(32, p, events_fn=ev)
        self.assertEqual(outs[29]['released'], 0.0)
        self.assertEqual(outs[30]['released'], 1.0)
        self.assertLess(float(P2[H - 1, 0, 1]), float(rest[H - 1, 0, 1]) - 1e-4)   # corner falls once released

    def test_reset_repins(self):
        st, o = L.step(None, 0.0, {}, L.DEFAULTS)
        self.assertEqual(o['reset'], 1.0)                        # first frame is a reset
        st, o = L.step(st, 1 / 60, {}, L.DEFAULTS, ('release',))
        self.assertEqual((o['reset'], o['released']), (0.0, 1.0))
        st, o = L.step(st, 2 / 60, {}, L.DEFAULTS, ('reset',))
        self.assertEqual((o['reset'], o['released']), (1.0, 0.0))
        self.assertEqual(o['rows'][L.ROW['R_GRAV']][3], 1.0)
        st, o = L.step(st, 3 / 60, {}, L.DEFAULTS)
        self.assertEqual(o['rows'][L.ROW['R_GRAV']][3], 0.0)

    def test_pause_and_step(self):
        p = dict(L.DEFAULTS, pause=True)
        st, o = L.step(None, 0.0, {}, p)
        self.assertEqual(o['run'], 1.0)                           # reset frame always runs
        st, o = L.step(st, 1 / 60, {}, p)
        self.assertEqual(o['run'], 0.0)
        st, o = L.step(st, 2 / 60, {}, p, ('step',))
        self.assertEqual(o['run'], 1.0)
        st, o = L.step(st, 3 / 60, {}, p)
        self.assertEqual(o['run'], 0.0)
        self.assertEqual(o['steps'], 2.0 * L.DEFAULTS['substeps'])
        P = np.ones((3, 3, 3))
        V = np.full((3, 3, 3), 2.0)
        rows = list(o['rows'])
        X, Vn = L.substep_ref(P, V, P, np.zeros((3, 3)), np.zeros((3, 3, 3)), rows)
        self.assertTrue(np.array_equal(X, P) and np.array_equal(Vn, V))


class Jelly(unittest.TestCase):
    def test_polar_rotation_proper(self):
        rng = np.random.default_rng(3)
        for _ in range(60):
            A = rng.normal(size=(3, 3))
            R = np.array(L.polar_rotation(A.tolist()))
            self.assertAlmostEqual(float(np.linalg.det(R)), 1.0, places=12)
            self.assertLess(float(np.abs(R.T @ R - np.eye(3)).max()), 1e-12)
            if np.linalg.det(A) > 0:                              # = the SVD polar factor
                U, _, Vt = np.linalg.svd(A)
                self.assertLess(float(np.abs(R - U @ Vt).max()), 1e-6)

    def test_flat_rank2_and_rigid_motion(self):
        rest, _ = L.rest_arrays(8, 8, 1.0, 1.0, 'vertical', 1.0, 'none')
        rc = np.array(L.rest_centroid(1.0, 1.0, 'vertical', 1.0))
        ang = math.radians(50)
        R0 = np.array([[math.cos(ang), 0, math.sin(ang)], [0, 1, 0], [-math.sin(ang), 0, math.cos(ang)]])
        P = (rest - rc) @ R0.T + rc + np.array([0.3, -0.2, 0.5])
        _, o = L.step(None, 0.0, {}, dict(L.DEFAULTS, gridw=8, gridh=8, mode='jelly'))
        rows, q = L.jelly_rows_ref(P, rest, o['rows'])
        R = np.array([rows[L.ROW['R_ROT0']][:3], rows[L.ROW['R_ROT1']][:3], rows[L.ROW['R_ROT2']][:3]])
        self.assertLess(float(np.abs(R - R0).max()), 1e-6)       # rank-2 covariance (flat sheet) still exact
        goal = np.array(rows[L.ROW['R_CENT']][:3]) + (rest - rc) @ R.T
        self.assertLess(float(np.abs(goal - P).max()), 1e-6)

    def test_jelly_returns_to_shape(self):
        rng = np.random.default_rng(1)
        pert = lambda R: R + rng.normal(scale=0.03, size=R.shape)
        p = {'gridw': 10, 'gridh': 10, 'pins': 'none', 'mode': 'jelly', 'shape': 0.3, 'testmode': 'rest',
             'substeps': 4}

        def shape_err(P, rest):
            rows, _ = L.jelly_rows_ref(P, rest, L.step(None, 0, {}, dict(L.DEFAULTS, **p))[1]['rows'])
            R = np.array([rows[L.ROW['R_ROT0']][:3], rows[L.ROW['R_ROT1']][:3], rows[L.ROW['R_ROT2']][:3]])
            rc = np.array(rows[L.ROW['R_REST']][:3])
            g = np.array(rows[L.ROW['R_CENT']][:3]) + (rest - rc) @ R.T
            return float(np.sqrt(np.mean(np.sum((P - g) ** 2, axis=-1))))
        P0, _, rest, _, _, _ = sim(1, dict(p, shape=0.0), perturb=pert)
        e0 = shape_err(P0, rest)
        rng = np.random.default_rng(1)
        P, _, rest, _, _, _ = sim(10, p, jelly=True, perturb=pert)
        self.assertLess(shape_err(P, rest), 0.5 * e0)

    def test_cov_chop_mapping(self):
        vals = {n: float(k) for k, n in enumerate(L.COV_CHANS)}
        A, c = L.cov_from_chop(vals)
        self.assertEqual(A, [[0.0, 1.0, 2.0], [4.0, 5.0, 6.0], [8.0, 9.0, 10.0]])
        self.assertEqual(c, (3.0, 7.0, 11.0))

    def test_engine_uses_cov_only_in_jelly(self):
        rest, _ = L.rest_arrays(6, 6, 1.0, 1.0, 'vertical', 1.0, 'none')
        rc = np.array(L.rest_centroid(1.0, 1.0))
        Q = (rest - rc).reshape(-1, 3)
        A = (rest.reshape(-1, 3).T @ Q) / 36
        c = rest.reshape(-1, 3).mean(axis=0)
        vals = {}
        for g in range(3):
            for k in range(3):
                vals[L.COV_CHANS[g * 4 + k]] = float(A[g, k])
            vals[L.COV_CHANS[g * 4 + 3]] = float(c[g])
        p = dict(L.DEFAULTS, gridw=6, gridh=6, mode='jelly')
        st, o = L.step(None, 0.0, {'cov': vals}, p)
        self.assertEqual(o['rows'][L.ROW['R_ROT0']][3], 0.0)    # reset frame ignores cov
        st, o = L.step(st, 1 / 60, {'cov': vals}, p)
        self.assertEqual(o['rows'][L.ROW['R_ROT0']][3], 1.0)
        self.assertAlmostEqual(o['rows'][L.ROW['R_ROT0']][0], 1.0, places=9)
        _, o = L.step(st, 2 / 60, {'cov': vals}, dict(p, mode='cloth'))
        self.assertEqual(o['rows'][L.ROW['R_ROT0']][3], 0.0)


class Wind(unittest.TestCase):
    def test_constant_wind_moves_centroid(self):
        p = {'gridw': 10, 'gridh': 10, 'pins': 'none', 'windmode': 'constant', 'windx': 0.0, 'windy': 0.0,
             'windz': 4.0, 'gravityy': 0.0, 'substeps': 4, 'turbulence': 0.0}
        P, _, rest, _, _, _ = sim(30, p)
        d = P.reshape(-1, 3).mean(axis=0) - rest.reshape(-1, 3).mean(axis=0)
        self.assertGreater(d[2], 0.1)
        self.assertLess(abs(d[0]) + abs(d[1]), 1e-6)

    def test_aero_edge_on_gets_no_push(self):
        p = {'gridw': 8, 'gridh': 8, 'pins': 'none', 'windmode': 'constant', 'windx': 4.0, 'windz': 0.0,
             'gravityy': 0.0, 'aero': 1.0, 'substeps': 2}
        P, _, rest, _, _, _ = sim(20, p)                           # wind along x, sheet in XY: edge-on
        self.assertLess(float(np.abs(P - rest).max()), 1e-9)

    def test_bpm_ticks_exact(self):
        ticks = []
        for f in range(3600):
            ticks += L.bpm_ticks(f / 60.0, (f + 1) / 60.0, 120.0, 1.0)
        self.assertEqual(len(ticks), 120)
        self.assertAlmostEqual(ticks[0], 0.5)
        self.assertAlmostEqual(ticks[-1], 60.0)
        n = sum(len(L.bpm_ticks(f / 60.0, (f + 1) / 60.0, 120.0, 1.0)) for f in range(216000))
        self.assertEqual(n, 7200)                                  # 1 h, no drift
        self.assertEqual(len(L.bpm_ticks(0.0, 2.0, 120.0, 4.0)), 1)

    def test_bpm_bursts_on_beats(self):
        p = dict(L.DEFAULTS, windmode='bpm', bpm=120.0, bpmdiv='b1', burstdecay=0.1)
        st, beats = None, []
        for f in range(121):
            st, o = L.step(st, f / 60.0, {}, p)
            if o['burst'] == 1.0:
                beats.append(f)
        self.assertEqual(beats, [30, 60, 90, 120])

    def test_burst_pulse_and_decay(self):
        p = dict(L.DEFAULTS, windmode='off', burstforce=10.0, burstdecay=0.5, windx=0.0, windy=0.0, windz=2.0)
        st, o = L.step(None, 0.0, {}, p)
        st, o = L.step(st, 1.0, {}, p, ('burst',))
        self.assertAlmostEqual(o['wind_z'], 10.0)
        st, o = L.step(st, 1.5, {}, p)
        self.assertAlmostEqual(o['wind_z'], 10.0 * math.exp(-1.0))

    def test_audio_kicks_refractory(self):
        p = dict(L.DEFAULTS, windmode='audio', burstthresh=0.5, burstrefractory=0.25, audiogain=1.0)
        # loud bursts every 0.1 s (2 frames on, 4 off): refractory 0.25 s lets every 3rd through
        lv = lambda f: {'level': 1.0 if f % 6 < 2 else 0.0}
        st, kicks = None, []
        for f in range(60):
            st, o = L.step(st, f / 60.0, lv(f), p)
            if o['burst'] == 1.0:
                kicks.append(f)
        self.assertEqual(kicks, [0, 18, 36, 54])
        quiet = lambda f: {'level': 0.3 if f % 6 < 2 else 0.0}
        st = None
        for f in range(60):
            st, o = L.step(st, f / 60.0, quiet(f), p)
        self.assertEqual(o['kicks'], 0.0)

    def test_noise_wind_deterministic_and_bounded(self):
        p = dict(L.DEFAULTS, windmode='noise', windz=3.0, seed=4)
        a = [L.wind_base(p, t / 10.0) for t in range(200)]
        b = [L.wind_base(p, t / 10.0) for t in range(200)]
        self.assertEqual(a, b)
        z = [w[2] for w in a]
        self.assertTrue(1.5 - 1e-9 <= min(z) and max(z) <= 4.5 + 1e-9)
        self.assertGreater(max(z) - min(z), 0.5)
        self.assertTrue(all(0.0 <= L.vnoise(x * 0.37, 2) < 1.0 for x in range(500)))

    def test_testmodes(self):
        p = dict(L.DEFAULTS, windmode='noise', sphere1on=True, floor=True)
        _, o = L.step(None, 0.0, {'colliders': [(0, 0, 0, 1)]}, dict(p, testmode='rest'))
        r = o['rows']
        self.assertEqual(r[L.ROW['R_GRAV']][:3], (0.0, 0.0, 0.0))
        self.assertEqual(r[L.ROW['R_WIND']][:3], (0.0, 0.0, 0.0))
        self.assertEqual(r[L.ROW['R_FLOOR']][0], 0.0)
        self.assertTrue(all(r[L.ROW['R_SPH0'] + k][3] < 0 for k in range(4)))
        _, o = L.step(None, 0.0, {'cookrate': 30.0}, dict(p, testmode='fixed'))
        self.assertAlmostEqual(o['rows'][L.ROW['R_STEP']][0], 1 / 60.0 / L.DEFAULTS['substeps'])
        self.assertEqual(o['rows'][L.ROW['R_TURB']][0], 0.0)
        self.assertEqual(o['rows'][L.ROW['R_WIND']][:3], (0.0, 0.0, 3.0))


class EngineRows(unittest.TestCase):
    def test_rows_complete(self):
        _, o = L.step(None, 0.0, {}, L.DEFAULTS)
        self.assertEqual(len(o['rows']), L.NROWS)
        self.assertTrue(all(len(r) == 4 and all(math.isfinite(x) for x in r) for r in o['rows']))
        self.assertEqual(set(L.ENGINE_CHANS), set(k for k in o if k != 'rows'))

    def test_dt_and_compliance_scaling(self):
        p = dict(L.DEFAULTS, substeps=8, dt=0.0, timescale=1.0, bend=0.5)
        _, o = L.step(None, 0.0, {'cookrate': 60.0}, p)
        dt = o['rows'][L.ROW['R_STEP']][0]
        self.assertAlmostEqual(dt, 1 / 480.0)
        self.assertAlmostEqual(o['rows'][L.ROW['R_COMP']][2], 0.5 / dt ** 2)
        self.assertAlmostEqual(o['rows'][L.ROW['R_STEP']][2], math.exp(-1.0 * dt))
        _, o = L.step(None, 0.0, {}, dict(p, dt=0.01, timescale=0.5, substeps=99))
        self.assertAlmostEqual(o['rows'][L.ROW['R_STEP']][0], 0.005 / L.SMAX)
        self.assertEqual(o['rows'][L.ROW['R_REST']][3], float(L.SMAX))
        self.assertAlmostEqual(o['rows'][L.ROW['R_MASS']][1], 128 * 128 / 1.0)

    def test_camera_looks_at_centre(self):
        c = (0.2, 0.5, -0.1)
        for cam in L.CAMS:
            for t in (0.0, 3.3):
                tx, ty, tz, rx, ry = L.camera_pose(cam, t, L.DEFAULTS, c)
                f = L.camera_forward(rx, ry)
                to = np.array(c) - np.array((tx, ty, tz))
                to /= np.linalg.norm(to)
                self.assertLess(float(np.abs(np.array(f) - to).max()), 1e-9, (cam, t))
        self.assertAlmostEqual(L.camera_pose('front', 0, L.DEFAULTS, c)[2], c[2] + 2.6 * math.cos(math.radians(10)))

    def test_stats(self):
        P, _ = L.rest_arrays(6, 6, 1.0, 1.0)
        V = np.zeros_like(P)
        V[2, 3] = (1.0, 0.0, 0.0)
        _, o = L.step(None, 0.0, {}, dict(L.DEFAULTS, gridw=6, gridh=6, mass=36.0))
        s = L.stats_ref(P, V, P, np.zeros((6, 6)), o['rows'])
        self.assertLess(float(np.abs(s[..., 0]).max()), 1e-12)
        self.assertAlmostEqual(float(s[2, 3, 1]), 0.5)
        P2 = P.copy()
        P2[0, 0, 0] = np.nan
        self.assertEqual(float(L.stats_ref(P2, V, P, np.zeros((6, 6)), o['rows'])[..., 2].sum()), 1.0)
        out = L.stats_from({'meanstretch': 0.01, 'energy_avg': 0.5 / 36, 'nan_avg': 0.0}, {'maxstretch': 0.1}, 6, 6)
        self.assertEqual(out, {'maxstretch': 0.1, 'meanstretch': 0.01, 'energy': 0.5, 'nan': 0})

    def test_audio_level(self):
        self.assertEqual(L.audio_level([]), 0.0)
        self.assertAlmostEqual(L.audio_level([1.0, -1.0, 1.0, -1.0]), 1.0)


class ShaderContract(unittest.TestCase):
    def read(self, n):
        with open(os.path.join(GLSL, n + '.glsl'), 'rb') as fh:
            return fh.read().decode('ascii')

    def test_files_ascii_no_version(self):
        for n in SHADERS:
            t = self.read(n)
            self.assertNotIn('#version', t, n)
        with open(os.path.join(REPO, 'builders', 'cloth_logic.py'), 'rb') as fh:
            fh.read().decode('ascii')
        with open(os.path.join(REPO, 'builders', 'cloth.py'), 'rb') as fh:
            fh.read().decode('ascii')

    def test_header_matches_python(self):
        h = L.glsl_header()
        for n, k in L.ROW.items():
            self.assertIn('#define %s %d\n' % (n, k), h)
        self.assertIn('#define NROWS %d\n' % L.NROWS, h)
        m = re.search(r'ivec3\[\]\((.*)\);', h)
        got = [tuple(int(x) for x in t) for t in re.findall(r'ivec3\((-?\d+), (-?\d+), (-?\d+)\)', m.group(1))]
        self.assertEqual(got, L.STENCIL)
        self.assertEqual(L.STENCIL[:4], L.STRUCTURAL)               # cloth_stats.glsl relies on this order
        for k, n in enumerate(L.PINMODES):
            self.assertIn('#define PIN_%s %d\n' % (n.upper(), k), h)

    def test_rest_lengths(self):
        d = 0.1
        got = sorted(set(round(L.rest_length(di, dj, d, d), 12) for di, dj, _ in L.STENCIL))
        self.assertEqual(got, sorted({round(d, 12), round(d * math.sqrt(2), 12), round(2 * d, 12)}))
        self.assertEqual(L.spacing(11, 5, 1.0, 2.0), (0.1, 0.5))

    def test_shader_names_defined(self):
        defined = set(L.ROW) | {'NROWS', 'NSPHERES', 'NSTENCIL', 'STENCIL'} | {'PIN_' + n.upper() for n in L.PINMODES}
        for n in SHADERS:
            for name in set(re.findall(r'\b(R_[A-Z0-9]+|PIN_[A-Z]+|NSPHERES|NSTENCIL|NROWS)\b', self.read(n))):
                self.assertIn(name, defined, (n, name))

    def test_shader_mirrors_reference(self):
        s = self.read('cloth_substep')
        for frag in ('al.w * corr / max(cnt, 1.0)', '-(ln - L) / den', 'wd.w * n * dot(n, wv)',
                     '(Y - P0) / st.x * st.z', 'min(fl.z, 1.0)', 'sp.w + fl.w', 'X += m.z * (g - X)'):
            self.assertIn(frag, s)
        self.assertEqual(L.NSPHERES, 4)
        self.assertIn('local_size_x = 8, local_size_y = 8', s)
        for n in SHADERS:
            if n not in ('cloth_vert', 'cloth_frag'):
                t = self.read(n)
                self.assertIn('TDImageStoreOutput', t, n)
                self.assertNotIn('fragColor', t, n)

    def test_builder_uses_logic_names(self):
        with open(os.path.join(REPO, 'builders', 'cloth.py')) as fh:
            b = fh.read()
        for n in SHADERS:
            self.assertIn("'%s'" % n, b)
        self.assertIn("'texturebuffer'", b)
        for name in ("Lg['COV_CHANS']", "Lg['STATS_AVG_CHANS']", "Lg['STATS_MAX_CHANS']", 'L.ENGINE_CHANS',
                     'L.STATS_CHANS', 'L.NROWS', 'glsl_header'):
            self.assertIn(name, b)
        self.assertEqual(len(L.COV_CHANS), 12)
        self.assertEqual(len(L.STATS_AVG_CHANS), 4)
        self.assertEqual(len(L.STATS_MAX_CHANS), 4)
        self.assertIn('meanstretch', L.STATS_AVG_CHANS)              # stats_from reads these names
        self.assertIn('maxstretch', L.STATS_MAX_CHANS)
        for n in ('energy_avg', 'nan_avg'):
            self.assertIn(n, L.STATS_AVG_CHANS)
        ns = {}
        exec(compile(b, 'cloth.py', 'exec'), ns)                       # parses; build() needs TD, not called
        pages = ns['_pages'](vars(L))
        names = [n for _, pars in pages for n, *_ in pars]
        self.assertEqual(len(names), len(set(names)))
        for n in names:
            self.assertRegex(n, r'^[A-Z][a-z0-9]*$')                    # TD custom par rule (T-00e)
        flat = set()
        for _, pars in pages:
            for n, style, *_ in pars:
                if style == 'XYZ':
                    flat |= {(n + a).lower() for a in 'xyz'}
                elif style not in ('Pulse', 'RGB'):
                    flat.add(n.lower())
        missing = [k for k in L.DEFAULTS if k not in flat]
        self.assertEqual(missing, [])                                   # every logic key has a par
        self.assertEqual(ns['PANEL_PAGES'], [p for p, _ in pages])
        self.assertNotIn('numpyArray', b)                           # T-74: no pixel readback in the builder
        self.assertNotIn('.destroy()', b)                           # T-70: safe_destroy only


if __name__ == '__main__':
    unittest.main()
