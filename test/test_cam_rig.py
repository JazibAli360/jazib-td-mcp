"""Offline tests of builders/cam_rig_logic.py (camera rigs, view store, director, TD binding). No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_cam_rig.py'
LIVE CHECKS (Camera COMP world matrix vs pose_matrix, director cuts vs the beat clock): docs/builds/cam_rig.md."""
import math
import os
import random
import sys
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import cam_rig_logic as C  # noqa: E402


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def mclose(A, B, tol=1e-9):
    return all(abs(A[r][c] - B[r][c]) <= tol for r in range(len(A)) for c in range(len(A[0])))


class Maths(unittest.TestCase):
    def test_eases(self):
        for n in C.names(C.EASES):
            self.assertAlmostEqual(C.ease(0.0, n), 0.0, places=12)
            self.assertAlmostEqual(C.ease(1.0, n), 1.0, places=12)
            self.assertAlmostEqual(C.ease(-3.0, n), 0.0, places=12)          # clamped
        self.assertAlmostEqual(C.ease(0.5, 'smooth'), 0.5)
        self.assertAlmostEqual(C.ease(0.5, 'sine'), 0.5)
        self.assertGreater(max(C.ease(u / 100.0, 'back') for u in range(101)), 1.05)   # overshoot

    def test_axes_default_look(self):
        p = C.pose((0, 0, 5), (0, 0, 0))
        x, y, z = C.axes(p)
        self.assertTrue(close(x, (1, 0, 0)) and close(y, (0, 1, 0)) and close(z, (0, 0, 1)))
        M = C.pose_matrix(p)
        self.assertTrue(mclose(M, [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 5], [0, 0, 0, 1]]))

    def test_axes_orthonormal_and_looking(self):
        rng = random.Random(4)
        for _ in range(200):
            pos = [rng.uniform(-5, 5) for _ in range(3)]
            tgt = [rng.uniform(-5, 5) for _ in range(3)]
            p = C.pose(pos, tgt, rng.uniform(-180, 180))
            x, y, z = C.axes(p)
            for a in (x, y, z):
                self.assertAlmostEqual(C.length(a), 1.0, places=9)
            self.assertAlmostEqual(C.dot(x, y), 0.0, places=9)
            self.assertAlmostEqual(C.dot(x, z), 0.0, places=9)
            self.assertTrue(close(C.cross(x, y), z, 1e-9))                    # right-handed
            self.assertTrue(close(C.mul(z, -1.0), C.norm(C.sub(tgt, pos)), 1e-9))  # -Z looks at the target

    def test_roll_sign(self):
        """roll + 90: camera X turns to world +Y (CCW about its own +Z, same as TD rz on a camera looking -Z)."""
        x, y, _ = C.axes(C.pose((0, 0, 5), (0, 0, 0), 90.0))
        self.assertTrue(close(x, (0, 1, 0), 1e-12) and close(y, (-1, 0, 0), 1e-12))
        R = C.matrix_from_euler(0, 0, 90, 'xyz')
        self.assertTrue(close([R[0][0], R[1][0], R[2][0]], x, 1e-12))

    def test_straight_down_no_nan(self):
        p = C.pose((0, 10, 0), (0, 0, 0))
        x, y, z = C.axes(p)
        for a in (x, y, z):
            self.assertFalse(any(math.isnan(c) for c in a))
        self.assertTrue(close(z, (0, 1, 0)))

    def test_view_inverse(self):
        p = C.pose((1, 2, 3), (-2, 0.5, 1), 33.0)
        I = C.matmul(C.view_matrix(p), C.pose_matrix(p))
        self.assertTrue(mclose(I, [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], 1e-12))

    def test_viewproj_centre(self):
        """The target projects to the screen centre; matches px_logic.cam_viewproj for a level orbit camera."""
        p = C.pose((1, 2, 3), (-2, 0.5, 1), 0.0, 55.0)
        vp = C.viewproj(p, 1080, 1920)
        q = [sum(vp[r][k] * (list(p['target']) + [1.0])[k] for k in range(4)) for r in range(4)]
        self.assertAlmostEqual(q[0] / q[3], 0.0, places=9)
        self.assertAlmostEqual(q[1] / q[3], 0.0, places=9)
        import px_logic as PXL
        ry = 37.0
        a = math.radians(ry)
        pos = (0.5, 0.15, 1.3)
        fwd = (-math.sin(a), 0.0, -math.cos(a))                               # Ry(ry) applied to -Z
        cp = C.pose(pos, C.add(pos, fwd), 0.0, 55.0)
        self.assertTrue(mclose(C.viewproj(cp, 1080, 1920), PXL.cam_viewproj(list(pos) + [ry], 55.0, 1080, 1920), 1e-9))

    def test_euler_round_trip_all_orders(self):
        rng = random.Random(7)
        for order in C.ORDERS:
            for _ in range(200):
                a = [rng.uniform(-179, 179) for _ in range(3)]
                R = C.matrix_from_euler(a[0], a[1], a[2], order)
                e = C.euler_from_matrix(R, order)
                self.assertTrue(mclose(C.matrix_from_euler(e[0], e[1], e[2], order), R, 1e-9), order)
            for mid in (90.0, -90.0):                                          # gimbal lock still round-trips
                ang = {'x': 20.0, 'y': 30.0, 'z': 40.0}
                ang[order[1]] = mid
                R = C.matrix_from_euler(ang['x'], ang['y'], ang['z'], order)
                e = C.euler_from_matrix(R, order)
                self.assertTrue(mclose(C.matrix_from_euler(e[0], e[1], e[2], order), R, 1e-7), (order, mid))

    def test_euler_order_semantics(self):
        """'xyz' = rotate about x first (R = Rz Ry Rx): a point on +Z, rx 90 then ry 90 -> -Y then stays -Y."""
        R = C.matrix_from_euler(90, 90, 0, 'xyz')
        v = [sum(R[r][k] * (0, 0, 1)[k] for k in range(3)) for r in range(3)]
        self.assertTrue(close(v, (0, -1, 0), 1e-12))
        R2 = C.matrix_from_euler(90, 90, 0, 'yxz')                             # y first: +Z -> +X, then x: +X
        v2 = [sum(R2[r][k] * (0, 0, 1)[k] for k in range(3)) for r in range(3)]
        self.assertTrue(close(v2, (1, 0, 0), 1e-12))

    def test_td_pars_rebuild_pose(self):
        rng = random.Random(11)
        for order in C.ORDERS:
            for _ in range(50):
                p = C.pose([rng.uniform(-5, 5) for _ in range(3)], [rng.uniform(-5, 5) for _ in range(3)],
                           rng.uniform(-90, 90), 50.0)
                t = C.td_pars(p, order)
                R = C.matrix_from_euler(t['rx'], t['ry'], t['rz'], order)
                self.assertTrue(mclose(R, C.rot3(p), 1e-9))
                self.assertEqual((t['tx'], t['ty'], t['tz'], t['fov']), tuple(p['pos']) + (50.0,))
        t = C.td_pars(C.pose((0, 0, 5), (0, 0, 0)))
        self.assertTrue(close((t['rx'], t['ry'], t['rz']), (0, 0, 0), 1e-12))
        t = C.td_pars(C.pose((5, 0, 0), (0, 0, 0)))                            # looking -X = ry 90
        self.assertTrue(close((t['rx'], t['ry'], t['rz']), (0, 90, 0), 1e-9))


class Rigs(unittest.TestCase):
    def test_orbit(self):
        p = C.orbit((1, 0, 0), 4.0, 0.5, 90.0)
        self.assertTrue(close(p['pos'], (5, 0.5, 0), 1e-12))
        self.assertTrue(close(p['target'], (1, 0, 0)))
        p0 = C.orbit_at(0.0, speed_deg=10.0)
        p9 = C.orbit_at(9.0, speed_deg=10.0)
        self.assertTrue(close(p9['pos'], C.orbit(az_deg=90.0)['pos'], 1e-12))
        self.assertTrue(close(p0['pos'], (0, 0.5, 4.0)))

    def test_crane_arm(self):
        """The camera sits at the arm's end (length from the base) and always looks at the base."""
        for h in (0.0, 45.0, 170.0):
            for pt in (-30.0, 0.0, 60.0):
                p = C.crane((1, 2, 3), h, pt, 5.0)
                self.assertAlmostEqual(C.length(C.sub(p['pos'], (1, 2, 3))), 5.0, places=12)
                self.assertTrue(close(p['target'], (1, 2, 3)))
                self.assertAlmostEqual(p['pos'][1] - 2.0, 5.0 * math.sin(math.radians(pt)), places=12)
        self.assertTrue(close(C.crane((0, 0, 0), 0.0, 0.0, 2.0)['pos'], (0, 0, 2)))     # heading 0 = +Z side

    def test_dolly(self):
        a, b = (0, 1, 6), (0, 1, 2)
        self.assertTrue(close(C.dolly(a, b, 0.0)['pos'], a) and close(C.dolly(a, b, 1.0)['pos'], b))
        self.assertTrue(close(C.dolly(a, b, 0.5)['pos'], (0, 1, 4)))
        p = C.dolly(a, b, 0.3, target=None, look_dir=(0, 0, -1))
        self.assertTrue(close(C.axes(p)[2], (0, 0, 1)))                        # view direction kept
        q = C.dolly(a, b, 0.3, target=(0, 0, 0))
        self.assertTrue(close(q['target'], (0, 0, 0)))

    def test_path_passes_points_even_speed(self):
        pts = [(0, 0, 0), (2, 0, 0), (2, 0, 2), (0, 1, 2)]
        pa = C.Path(pts, samples=64)
        self.assertTrue(close(pa.at(0.0), pts[0], 1e-9) and close(pa.at(1.0), pts[-1], 1e-9))
        for k in range(1, 3):                                                   # passes through the inner points
            self.assertTrue(close(C.spline_raw(pts, float(k)), pts[k], 1e-12))
        steps = [C.length(C.sub(pa.at((i + 1) / 50.0), pa.at(i / 50.0))) for i in range(50)]
        self.assertLess(max(steps) / min(steps), 1.02)                          # arc-length: even speed
        cl = C.Path(pts, closed=True)
        self.assertTrue(close(cl.at(0.0), cl.at(1.0), 1e-9))
        pp = C.path_pose(pa, 0.2)
        self.assertGreater(C.dot(C.mul(C.axes(pp)[2], -1.0), pa.tangent(0.2)), 0.9)   # looks ahead

    def test_follow_lag(self):
        p0 = C.follow(None, (0, 0, 0), (0, 1, 4))
        self.assertTrue(close(p0['pos'], (0, 1, 4)))
        p1 = C.follow(p0, (2, 0, 0), (0, 1, 4), lag=0.5, dt=0.5)
        k = 1.0 - math.exp(-1.0)
        self.assertTrue(close(p1['pos'], (2 * k, 1, 4), 1e-12))
        p2 = C.follow(p0, (2, 0, 0), (0, 1, 4), lag=0.0, dt=0.1)
        self.assertTrue(close(p2['pos'], (2, 1, 4)))

    def test_shake(self):
        p = C.pose((0, 1, 5), (0, 1, 0))
        self.assertEqual(C.shake(p, 3.0), p)
        q = C.shake(p, 1.234, amp=0.05, rot_deg=2.0, freq=5.0, seed=3)
        self.assertLessEqual(C.length(C.sub(q['pos'], p['pos'])), 0.05 * math.sqrt(3) + 1e-9)
        self.assertLessEqual(abs(q['roll']), 2.0 + 1e-9)
        self.assertEqual(q, C.shake(p, 1.234, amp=0.05, rot_deg=2.0, freq=5.0, seed=3))    # deterministic
        self.assertNotEqual(q['pos'], C.shake(p, 1.334, amp=0.05, rot_deg=2.0, freq=5.0, seed=3)['pos'])

    def test_blend_line_arc(self):
        a = C.orbit(az_deg=0.0, radius=4.0, height=0.0)
        b = C.orbit(az_deg=90.0, radius=4.0, height=0.0)
        self.assertEqual(C.blend(a, b, 0.0, 'arc'), C.blend(a, a, 0.0, 'arc'))
        self.assertTrue(close(C.blend(a, b, 1.0, 'arc')['pos'], b['pos'], 1e-9))
        m = C.blend(a, b, 0.5, 'arc', 'linear')
        self.assertAlmostEqual(C.length(m['pos']), 4.0, places=9)                # stays on the circle
        self.assertTrue(close(m['pos'], C.orbit(az_deg=45.0, radius=4.0, height=0.0)['pos'], 1e-9))
        ln = C.blend(a, b, 0.5, 'ease', 'linear')
        self.assertAlmostEqual(C.length(ln['pos']), 4.0 * math.sqrt(0.5), places=9)   # straight: cuts the corner
        self.assertEqual(C.blend(a, b, 0.0, 'cut'), a)
        self.assertEqual(C.blend(a, b, 0.01, 'cut'), b)
        o = C.blend(C.orbit(az_deg=0.0), C.orbit(az_deg=180.0), 0.5, 'arc')         # opposite: no NaN
        self.assertFalse(any(math.isnan(x) for x in o['pos']))


class ViewsAndDirector(unittest.TestCase):
    def test_views_rows(self):
        v = C.Views()
        v.store('wide', C.pose((0, 2, 8), (0, 1, 0), 0.0, 60.0))
        v.store('close', C.pose((1, 1.5, 2), (0, 1.2, 0), 5.0, 35.0))
        w = C.Views.from_rows(v.to_rows())
        self.assertEqual(w.names(), ['wide', 'close'])
        for n in w.names():
            a, b = v.get(n), w.get(n)
            self.assertTrue(close(a['pos'] + a['target'], b['pos'] + b['target'], 1e-5))
            self.assertAlmostEqual(a['fov'], b['fov'])
        self.assertTrue(close(v.fly('wide', 'close', 1.0)['pos'], (1, 1.5, 2), 1e-9))
        v.remove('wide')
        self.assertEqual(v.names(), ['close'])

    def test_list_schedule_and_quant(self):
        shots = [C.shot('view', 3.0, pose=C.pose((0, 0, 5), (0, 0, 0))),
                 C.shot('orbit', 2.5, 'ease', 1.0, radius=3.0)]
        d = C.Director(shots, 'list', quant=4.0, min_hold=1.0)
        d.ensure(40)
        self.assertEqual([(s[0], s[1], s[2]) for s in d.sched[:4]], [(0, 0.0, 4.0), (1, 4.0, 4.0), (0, 8.0, 4.0),
                                                                     (1, 12.0, 4.0)])
        for s in d.sched:
            self.assertEqual(s[1] % 4.0, 0.0)                                   # every cut on a bar
        self.assertEqual(d.cuts(3.0, 12.0), [4.0, 8.0, 12.0])
        k, i, st, ln = d.segment(5.5)
        self.assertEqual((k, i, st, ln), (1, 1, 4.0, 4.0))

    def test_random_never_repeats_and_holds(self):
        shots = [C.shot('view', pose=C.pose((k, 0, 5), (0, 0, 0))) for k in range(4)]
        d = C.Director(shots, 'random', seed=5, quant=1.0, min_hold=2.0, max_hold=6.0)
        d.ensure(500)
        for a, b in zip(d.sched, d.sched[1:]):
            self.assertNotEqual(a[0], b[0])
            self.assertEqual(b[1], a[1] + a[2])
        for s in d.sched:
            self.assertTrue(2.0 <= s[2] <= 6.0 and s[2] == int(s[2]) and s[1] == int(s[1]))
        self.assertEqual(set(s[0] for s in d.sched), {0, 1, 2, 3})
        d2 = C.Director(shots, 'random', seed=5, quant=1.0, min_hold=2.0, max_hold=6.0)
        d2.ensure(500)
        self.assertEqual(d.sched[:50], d2.sched[:50])                           # seeded: same show every run

    def test_poses_cut_and_ease(self):
        A, B = C.pose((0, 0, 5), (0, 0, 0)), C.pose((5, 0, 0), (0, 0, 0))
        d = C.Director([C.shot('view', 4.0, pose=A), C.shot('view', 4.0, 'arc', 2.0, pose=B),
                        C.shot('view', 4.0, 'cut', pose=A)], 'list', quant=1.0)
        self.assertEqual(d.at(3.99)[0]['pos'], A['pos'])
        p, info = d.at(5.0)
        self.assertEqual((info['segment'], info['shot']), (1, 1))
        self.assertAlmostEqual(info['progress'], 0.5)
        self.assertAlmostEqual(C.length(p['pos']), 5.0, places=9)               # arc about the target
        self.assertTrue(close(d.at(6.0)[0]['pos'], B['pos'], 1e-12))              # transition done: hold
        self.assertEqual(d.at(8.0)[0]['pos'], A['pos'])                          # hard cut on beat 8

    def test_moving_shots_and_seconds(self):
        sh = [C.shot('orbit', 8.0, radius=4.0, height=0.0, speed_deg=90.0),
              C.shot('crane', 8.0, base=(0, 0, 0), heading=0.0, heading_speed=45.0, pitch=10.0, length=3.0),
              C.shot('dolly', 8.0, a=(0, 1, 6), b=(0, 1, 2), ease='linear'),
              C.shot('path', 8.0, points=[(0, 0, 4), (4, 0, 0), (0, 0, -4)], target=(0, 0, 0))]
        d = C.Director(sh, 'list', bpm=60.0)                                    # 1 beat = 1 s
        p = d.at(1.0)[0]
        self.assertTrue(close(p['pos'], C.orbit(radius=4.0, height=0.0, az_deg=90.0)['pos'], 1e-9))
        p = d.at(10.0)[0]
        self.assertTrue(close(p['pos'], C.crane((0, 0, 0), 90.0, 10.0, 3.0)['pos'], 1e-9))
        self.assertTrue(close(d.at(20.0)[0]['pos'], (0, 1, 4), 1e-12))          # dolly half way at beat 4 of 8
        p = d.at(24.0)[0]
        self.assertTrue(close(p['pos'], (0, 0, 4), 1e-9) and close(p['target'], (0, 0, 0)))
        # moving rigs run on the beat clock (seconds only feed the follow lag's dt): same pose for any seconds
        self.assertTrue(close(d.at(1.0, seconds=2.0)[0]['pos'], C.orbit(radius=4.0, height=0.0, az_deg=90.0)['pos'],
                              1e-9))
        fp = C.Director([C.shot('follow', 4.0, offset=(0, 1, 4), lag=0.0)], bpm=60.0)
        self.assertTrue(close(fp.at(1.0, follow_point=(3, 0, 0))[0]['pos'], (3, 1, 4)))

    def test_view_names(self):
        v = C.Views({'a': C.pose((0, 0, 5), (0, 0, 0)), 'b': C.pose((0, 5, 0.01), (0, 0, 0))})
        d = C.Director([C.shot('view', 2.0, name='a'), C.shot('view', 2.0, 'ease', 1.0, name='b')], views=v)
        self.assertTrue(close(d.at(1.0)[0]['pos'], (0, 0, 5)))
        self.assertTrue(close(d.at(3.0)[0]['pos'], (0, 5, 0.01)))


class Binding(unittest.TestCase):
    def test_bind_exprs_and_memo(self):
        ex = C.bind_exprs("op('rig').module", "op('beat')['beats']")
        self.assertEqual(set(ex), set(C.BIND_PARS))
        self.assertIn("op('beat')['beats']", ex['tx'])
        calls = []

        def fn(t):
            calls.append(t)
            return C.orbit(radius=4.0, height=0.0, az_deg=90.0 * t)
        m = C.Memo(fn)
        ns = {'op': lambda p: types.SimpleNamespace(module=m) if p == 'rig' else {'beats': 1.0},
              'me': types.SimpleNamespace(par=types.SimpleNamespace(rord=types.SimpleNamespace(eval=lambda: 'xyz')))}
        vals = dict((k, eval(e, ns)) for k, e in ex.items())
        self.assertEqual(len(calls), 1)                                          # one pose for the 7 pars
        self.assertTrue(close((vals['tx'], vals['ty'], vals['tz']), (4, 0, 0), 1e-12))
        self.assertTrue(close((vals['rx'], vals['ry'], vals['rz']), (0, 90, 0), 1e-9))

    def test_apply_bind(self):
        PM = types.SimpleNamespace(EXPRESSION='E', CONSTANT='C')

        class P:
            def __init__(self):
                self.mode, self.expr = 'C', ''
        cam = types.SimpleNamespace(par=types.SimpleNamespace(**dict((n, P()) for n in C.BIND_PARS if n != 'fov')))
        done = C.apply_bind(cam, C.bind_exprs("op('r').module"), PM)
        self.assertEqual(set(done), set(C.BIND_PARS) - {'fov'})
        self.assertEqual(cam.par.tx.mode, 'E')

    def test_ascii_no_td(self):
        with open(C.__file__) as fh:
            src = fh.read()
        src.encode('ascii')
        self.assertNotIn('import td', src)


if __name__ == '__main__':
    unittest.main()
