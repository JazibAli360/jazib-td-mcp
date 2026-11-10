"""Offline tests of builders/cam_seq_logic.py v2 (CS_cam_sequencer as a Camera COMP: easings, the cam / Look At preset
tables and their edits, Select scrub with the ease INTO each preset incl. the wrap, Ease Override, spline, any-to-any,
playmodes, shake, global target / framing, the Out CHOP contract, v1 shot migration). No TD needed.
Run: python3 -I -m unittest discover -s test -p 'test_cam_seq*.py'
LIVE CHECKS (drop-in, Bind, Look At, pop-up, copies, cost on a build TD): docs/builds/cs_cam_sequencer.md."""
import math
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import cam_rig_logic as R  # noqa: E402
import cam_seq_logic as L  # noqa: E402

# Reference values worked out by hand from the easings.net formulas (F4), not from the code under test.
REF = {
    ('inSine', 0.5): 1 - math.cos(math.pi / 4), ('outSine', 0.5): math.sin(math.pi / 4), ('inOutSine', 0.25):
    (1 - math.cos(math.pi / 4)) / 2,
    ('inQuad', 0.5): 0.25, ('outQuad', 0.5): 0.75, ('inOutQuad', 0.25): 0.125, ('inOutQuad', 0.75): 0.875,
    ('inCubic', 0.5): 0.125, ('outCubic', 0.5): 0.875, ('inOutCubic', 0.25): 0.0625,
    ('inQuart', 0.5): 0.0625, ('outQuart', 0.5): 0.9375, ('inOutQuart', 0.25): 0.03125,
    ('inQuint', 0.5): 0.03125, ('outQuint', 0.5): 0.96875, ('inOutQuint', 0.25): 0.015625,
    ('inExpo', 0.5): 2 ** -5, ('outExpo', 0.5): 1 - 2 ** -5, ('inOutExpo', 0.25): 2 ** -5 / 2,
    ('inCirc', 0.5): 1 - math.sqrt(0.75), ('outCirc', 0.5): math.sqrt(0.75), ('inOutCirc', 0.25):
    (1 - math.sqrt(0.75)) / 2,
    ('inBack', 0.5): 2.70158 * 0.125 - 1.70158 * 0.25, ('outBack', 0.5): 1 + 2.70158 * -0.125 + 1.70158 * 0.25,
    ('inOutBack', 0.25): (0.25 * ((1.70158 * 1.525 + 1) * 0.5 - 1.70158 * 1.525)) / 2,
    ('inElastic', 0.5): -(2 ** -5) * math.sin((5 - 10.75) * 2 * math.pi / 3),
    ('outElastic', 0.5): 2 ** -5 * math.sin((5 - 0.75) * 2 * math.pi / 3) + 1,
    ('inOutElastic', 0.25): -(2 ** -5 * math.sin((5 - 11.125) * 2 * math.pi / 4.5)) / 2,
    ('outBounce', 0.5): 7.5625 * (0.5 - 1.5 / 2.75) ** 2 + 0.75, ('inBounce', 0.5): 1 - (7.5625 * (0.5 - 1.5 / 2.75) ** 2
                                                                                         + 0.75),
    ('outBounce', 0.2): 7.5625 * 0.04, ('inOutBounce', 0.25): (1 - (7.5625 * (0.5 - 1.5 / 2.75) ** 2 + 0.75)) / 2,
    ('smooth', 0.25): 0.15625, ('smoother', 0.25): 0.103515625, ('linear', 0.3): 0.3,
}


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def corners(r=5.0, h=1.0, ease_name=''):
    """4 camera presets at the square corners around the origin (az 45 / 135 / 225 / 315), aimed at the centre."""
    out = []
    for az in (45, 135, 225, 315):
        a = math.radians(az)
        v = R.td_pars(R.pose((r * math.sin(a), h, r * math.cos(a)), (0, 0, 0)))
        out.append(L.make_preset((v['tx'], v['ty'], v['tz'], v['rx'], v['ry'], v['rz'], 1, 1, 1, 0, 0, 0, 45.0),
                                 ease_name))
    return out


def looks(n=4):
    return [L.make_preset((k * 0.5, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0)) for k in range(n)]


class Easings(unittest.TestCase):
    def test_thirty_curves(self):
        pen = [n for n in L.EASE_NAMES if n not in ('linear', 'smooth', 'smoother', 'custom')]
        self.assertEqual(len(pen), 30)
        self.assertEqual(len(L.EASE_NAMES), len(L.EASE_LABELS))
        for n in L.EASE_NAMES:
            self.assertAlmostEqual(L.ease(0.0, n), 0.0, places=9, msg=n)
            self.assertAlmostEqual(L.ease(1.0, n), 1.0, places=9, msg=n)
            self.assertAlmostEqual(L.ease(-2.0, n), 0.0, places=9, msg=n)      # input clamped

    def test_reference_values(self):
        for (n, u), v in REF.items():
            self.assertAlmostEqual(L.ease(u, n), v, places=12, msg='%s(%s)' % (n, u))

    def test_shapes(self):
        for n in L.EASE_NAMES:
            ys = [L.ease(k / 200.0, n) for k in range(201)]
            if n.endswith(('Back', 'Elastic')):
                self.assertTrue(min(ys) < -1e-3 or max(ys) > 1.0 + 1e-3, n)      # leaves 0..1
            elif n.endswith('Bounce'):
                self.assertTrue(all(-1e-12 <= y <= 1.0 + 1e-12 for y in ys), n)
            else:
                self.assertTrue(all(b >= a - 1e-12 for a, b in zip(ys, ys[1:])), n)   # monotone
        for fam in L.FAMILIES:                                                    # in / out mirror symmetry
            for u in (0.1, 0.3, 0.7):
                self.assertAlmostEqual(L.ease(u, 'in' + fam), 1 - L.ease(1 - u, 'out' + fam), places=9)
                self.assertAlmostEqual(L.ease(u, 'inOut' + fam), 1 - L.ease(1 - u, 'inOut' + fam), places=9)

    def test_legacy_names_match_cam_rig(self):
        for n in ('linear', 'smooth', 'smoother', 'in', 'out', 'sine', 'expo', 'back'):
            for u in (0.1, 0.35, 0.5, 0.8):
                self.assertAlmostEqual(L.ease(u, n), R.ease(u, n), places=12, msg=n)

    def test_custom_lookup(self):
        s = [0.0, 0.0, 0.0, 1.0]                          # long hold then a jump
        self.assertAlmostEqual(L.ease(0.5, 'custom', s), 0.0)
        self.assertAlmostEqual(L.ease(5.0 / 6.0, 'custom', s), 0.5)
        self.assertAlmostEqual(L.ease(0.4, 'custom', None), 0.4)               # no CHOP = linear




def V(cam):
    return [p['v'] for p in cam]


class Tables(unittest.TestCase):
    def test_round_trip_and_header(self):
        cam = corners(ease_name='outBounce')
        rows = L.preset_rows(cam, L.CAM_PARS)
        self.assertEqual(rows[0], ['#', 'EASE'] + L.CAM_PARS)
        self.assertEqual([r[0] for r in rows[1:]], ['0', '1', '2', '3'])
        back = L.presets_from_rows(rows, L.CAM_PARS)
        self.assertEqual([p['ease'] for p in back], ['outBounce'] * 4)
        for a, b in zip(cam, back):
            self.assertTrue(close(a['v'], b['v'], 1e-6))
        self.assertEqual(L.preset_rows(looks(1), L.LOOK_PARS)[0], ['#', 'EASE'] + L.LOOK_PARS)

    def test_missing_columns_bad_cells_blank_rows(self):
        rows = [['tz', 'EASE', 'tx'], ['3', 'inQuad', 'x'], ['', '', ''], ['1', '', '2']]
        p = L.presets_from_rows(rows, L.CAM_PARS)
        self.assertEqual(len(p), 2)
        self.assertEqual(p[0]['v'][:3], (0.0, 0.0, 3.0))           # bad cell = default
        self.assertEqual(p[0]['v'][6:9], (1.0, 1.0, 1.0))          # scale defaults to 1
        self.assertEqual(p[0]['v'][12], 45.0)                      # fov default
        self.assertEqual((p[0]['ease'], p[1]['ease']), ('inQuad', ''))
        self.assertEqual(L.presets_from_rows([], L.CAM_PARS), [])

    def test_sort_by_number(self):
        rows = [['#', 'EASE', 'tx'], ['0', '', 'a'], ['1', '', 'b'], ['0.5', '', 'c'], ['', '', 'd']]
        out = L.sort_rows_by_number(rows)
        self.assertEqual([r[2] for r in out[1:]], ['a', 'c', 'b', 'd'])
        self.assertEqual([r[0] for r in out[1:]], ['0', '1', '2', '3'])

    def test_edits(self):
        v = lambda x: (x,) + (0,) * 12
        p, i = L.edit([], 'init', vec=v(1), ease_name='inQuad')
        self.assertEqual((len(p), i, p[0]['ease']), (1, 0, 'inQuad'))
        p, i = L.edit(p, 'append', vec=v(2))
        p, i = L.edit(p, 'append', vec=v(3))
        self.assertEqual(([q['v'][0] for q in p], i), ([1, 2, 3], 2))
        p, i = L.edit(p, 'insert', sel=1, vec=v(9))                # before the selected
        self.assertEqual(([q['v'][0] for q in p], i), ([1, 9, 2, 3], 1))
        p, i = L.edit(p, 'replace', sel=1, vec=v(7), ease_name='inOutCirc')   # values AND the current ease
        self.assertEqual((p[1]['v'][0], p[1]['ease']), (7, 'inOutCirc'))
        p, i = L.edit(p, 'duplicate', sel=1)
        p, i = L.edit(p, 'moveup', sel=2)
        self.assertEqual(i, 1)
        p, i = L.edit(p, 'movedown', sel=4)
        self.assertEqual(i, 4)
        p, i = L.edit(p, 'remove', sel=4)
        self.assertEqual(([q['v'][0] for q in p], i), ([1, 7, 7, 2], 3))
        with self.assertRaises(ValueError):
            L.edit(p, 'append')

    def test_edit_pair_keeps_rows_aligned(self):
        c = lambda x: (x,) + (0,) * 12
        lk = lambda x: (x,) + (0,) * 11
        cam, look, s = L.edit_pair([], [], 'init', camv=c(0))
        for x in (1, 2):
            cam, look, s = L.edit_pair(cam, look, 'append', s, c(x))
        self.assertEqual((len(cam), len(look)), (3, 0))            # no Look At op yet: its table stays empty
        cam, look, s = L.edit_pair(cam, look, 'append', s, c(3), lk(5))
        self.assertEqual((len(cam), len(look)), (4, 4))            # padded with the current Look At, then appended
        self.assertEqual([q['v'][0] for q in look], [5, 5, 5, 5])
        cam, look, s = L.edit_pair(cam, look, 'insert', 1, c(9), lk(8))
        self.assertEqual(([q['v'][0] for q in cam], [q['v'][0] for q in look]), ([0, 9, 1, 2, 3], [5, 8, 5, 5, 5]))
        cam, look, s = L.edit_pair(cam, look, 'remove', 1)
        self.assertEqual((len(cam), len(look), look[1]['v'][0]), (4, 4, 5))
        cam, look, s = L.edit_pair(cam, look, 'append', s, c(4))   # Look At cleared: a copy keeps the alignment
        self.assertEqual(len(look), 5)
        cam, look, s = L.edit_pair(cam, look, 'init', None, c(0))
        self.assertEqual((len(cam), len(look)), (1, 0))

    def test_selected_is_nearest(self):
        self.assertEqual(L.selected(1.4, 4), 1)
        self.assertEqual(L.selected(1.6, 4), 2)
        self.assertEqual(L.selected(3.7, 4), 0)                    # wraps
        self.assertIsNone(L.selected(0, 0))


class Select(unittest.TestCase):
    def test_parts(self):
        self.assertEqual(L.select_parts(0.0, 0), (None, None, 0.0))
        self.assertEqual(L.select_parts(3.7, 1), (0, 0, 0.0))
        i, j, f = L.select_parts(1.25, 4)
        self.assertEqual((i, j), (1, 2))
        self.assertAlmostEqual(f, 0.25)
        self.assertEqual(L.select_parts(3.5, 4)[:2], (3, 0))      # loop: 3 -> 0 is a real segment
        self.assertEqual(L.select_parts(-0.5, 4)[:2], (3, 0))
        i, j, f = L.select_parts(4.5, 4, 'pingpong')
        self.assertEqual((i, j), (2, 1))
        self.assertEqual(L.select_parts(9.0, 4, 'once'), (2, 3, 1.0))

    def test_fraction_is_the_blend(self):
        cam = corners(ease_name='linear')
        P = dict(L.DEFAULTS)
        for f in (0.0, 0.25, 0.5, 0.9):
            v = L.track_pose(cam, 1 + f, P)[0]
            self.assertTrue(close(v, L.vlerp(cam[1]['v'], cam[2]['v'], f), 1e-12), f)
        self.assertTrue(close(L.track_pose(cam, 2.0, P)[0], cam[2]['v']))

    def test_ease_into_each_preset_including_the_wrap(self):
        cam = corners()
        cam[1]['ease'], cam[2]['ease'], cam[0]['ease'] = 'inQuad', 'outQuad', 'inOutBounce'
        P = dict(L.DEFAULTS, easing='linear')
        v = L.track_pose(cam, 0.5, P)[0]                           # 0 -> 1 eased by preset 1 (inQuad)
        self.assertTrue(close(v, L.vlerp(cam[0]['v'], cam[1]['v'], 0.25), 1e-12))
        v = L.track_pose(cam, 1.5, P)[0]                           # 1 -> 2 by preset 2 (outQuad)
        self.assertTrue(close(v, L.vlerp(cam[1]['v'], cam[2]['v'], 0.75), 1e-12))
        v = L.track_pose(cam, 2.5, P)[0]                           # preset 3 has no ease: the Easing par
        self.assertTrue(close(v, L.vlerp(cam[2]['v'], cam[3]['v'], 0.5), 1e-12))
        v = L.track_pose(cam, 3.3, P)[0]                           # the wrap 3 -> 0 eases INTO preset 0
        self.assertTrue(close(v, L.vlerp(cam[3]['v'], cam[0]['v'], L.ease(0.3, 'inOutBounce')), 1e-9))

    def test_override_one_curve_for_all(self):
        cam = corners()
        cam[1]['ease'] = 'inQuad'
        P = dict(L.DEFAULTS, override=True, easing='outQuad')
        v = L.track_pose(cam, 0.5, P)[0]
        self.assertTrue(close(v, L.vlerp(cam[0]['v'], cam[1]['v'], 0.75), 1e-12))

    def test_shortrot(self):
        a = L.make_preset((0, 0, 0, 0, 350, 0, 1, 1, 1, 0, 0, 0, 45))
        b = L.make_preset((0, 0, 0, 0, 10, 0, 1, 1, 1, 0, 0, 0, 45), 'linear')
        raw = L.track_pose([a, b], 0.5, dict(L.DEFAULTS, loopmode='once'))[0]
        self.assertAlmostEqual(raw[4], 180.0)                      # raw pars, as the original
        short = L.track_pose([a, b], 0.5, dict(L.DEFAULTS, loopmode='once', shortrot=True))[0]
        self.assertAlmostEqual(short[4] % 360.0, 0.0)


class Spline(unittest.TestCase):
    def cam(self):
        rnd = random.Random(7)
        return [L.make_preset([rnd.uniform(-6, 6), rnd.uniform(0, 3), rnd.uniform(-6, 6), rnd.uniform(-30, 30),
                               rnd.uniform(-90, 90), 0, 1, 1, 1, 0, 0, 0, rnd.uniform(30, 60)]) for _ in range(6)]

    def test_passes_through_every_preset(self):
        cam = self.cam()
        P = dict(L.DEFAULTS, splineinterp=True)
        for k in range(6):
            self.assertTrue(close(L.track_pose(cam, float(k), P)[0], cam[k]['v'], 1e-9))
            self.assertTrue(close(L.spline_vec(V(cam), k, 1.0), cam[(k + 1) % 6]['v'], 1e-9))

    def test_smooth_at_keys(self):
        """Velocity just before a key ~ velocity just after it (closed loop, incl. the wrap); a straight-line
        scrub has a kink there."""
        cam = self.cam()
        P = dict(L.DEFAULTS, splineinterp=True)
        h = 1e-4
        for k in range(6):
            a = L.track_pose(cam, k - h, P)[0][:3]
            b = L.track_pose(cam, k, P)[0][:3]
            c = L.track_pose(cam, k + h, P)[0][:3]
            v1 = [(y - x) / h for x, y in zip(a, b)]
            v2 = [(y - x) / h for x, y in zip(b, c)]
            n1 = math.sqrt(sum(x * x for x in v1))
            cosang = sum(x * y for x, y in zip(v1, v2)) / max(n1 * math.sqrt(sum(x * x for x in v2)), 1e-12)
            self.assertGreater(cosang, 0.999, k)
        Pl = dict(L.DEFAULTS, easing='linear')
        a, b, c = (L.track_pose(cam, 1 + d, Pl)[0][:3] for d in (-h, 0, h))
        v1 = [(y - x) for x, y in zip(a, b)]
        v2 = [(y - x) for x, y in zip(b, c)]
        cosang = sum(x * y for x, y in zip(v1, v2)) / (math.sqrt(sum(x * x for x in v1)) *
                                                       math.sqrt(sum(x * x for x in v2)))
        self.assertLess(cosang, 0.999)

    def test_centripetal_bounded_on_a_sharp_corner(self):
        pts = [(0, 0, 0), (10, 0, 0), (10.2, 0, 0.2), (10.2, 0, 10)]
        vecs = [p + (0,) * 10 for p in pts]
        far = max(abs(L.spline_vec(vecs, 1, k / 50.0, False)[0] - 10.1) for k in range(51))
        self.assertLess(far, 0.5)

    def test_tension_zero_is_straight(self):
        cam = self.cam()
        v = L.spline_vec(V(cam), 2, 0.3, True, 0.0)
        self.assertTrue(close(v, L.vlerp(cam[2]['v'], cam[3]['v'], 0.3), 1e-12))

    def test_rotation_only_presets_do_not_fold(self):
        vecs = [(0, 0, 5, 0, a, 0, 1, 1, 1, 0, 0, 0, 45) for a in (0, 30, 60, 90)]
        ys = [L.spline_vec(vecs, 1, k / 20.0, False)[4] for k in range(21)]
        self.assertTrue(all(b >= a - 1e-9 for a, b in zip(ys, ys[1:])))


def run(E, cam, look, P, t0, t1, fps=60.0, events_at=None, bpm=120.0):
    out = []
    for k in range(int(round((t1 - t0) * fps)) + 1):
        t = t0 + k / fps
        c, lk, info = E.step(cam, look, P, t * bpm / 60.0, t, (events_at or {}).get(k, ()))
        out.append((t, c, lk, info))
    return out


class AnyToAny(unittest.TestCase):
    def test_goto_3_to_0_never_visits_1_or_2(self):
        cam = corners()
        lk = looks()
        E = L.Engine()
        P = dict(L.DEFAULTS, select=3.0, gotoblend='ease', gototime=2.0, haslook=True)
        frames = run(E, cam, lk, P, 0.0, 0.0)
        P['select'] = 0.0                                          # cs_rt sets a constant Select to the target
        frames += run(E, cam, lk, P, 0.0, 1.2, events_at={0: [('goto', 0)]})
        a, b = cam[3]['v'][:3], cam[0]['v'][:3]
        for _t, c, _l, _i in frames:                               # every frame on the straight line 3 -> 0
            d = R.sub(c[:3], a)
            ab = R.sub(b, a)
            u = R.dot(d, ab) / R.dot(ab, ab)
            self.assertLess(R.length(R.sub(d, R.mul(ab, u))), 1e-9)
        self.assertTrue(close(frames[-1][1], cam[0]['v'], 1e-9))
        self.assertTrue(close(frames[-1][2], lk[0]['v'], 1e-9))   # the Look At goes with it

    def test_arc_keeps_distance_to_the_look_point(self):
        cam = corners()
        lk = [L.make_preset((0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0))] * 4
        ac, bc = cam[0]['v'], cam[2]['v']
        for e in (0.2, 0.5, 0.8):
            c, _l = L.blend_vecs(ac, bc, lk[0]['v'], lk[2]['v'], e, 'arc')
            self.assertAlmostEqual(R.length(c[:3]), R.length(ac[:3]), places=9)

    def test_hand_wins(self):
        cam = corners()
        E = L.Engine()
        P = dict(L.DEFAULTS, select=0.0, gototime=8.0)
        E.step(cam, [], P, 0, 0.0)
        E.step(cam, [], P, 0, 0.1, [('goto', 2)])
        self.assertIsNotNone(E.goto)
        P['select'] = 1.0
        c, _l, info = E.step(cam, [], P, 0, 0.2)
        self.assertIsNone(E.goto)
        self.assertTrue(close(c, cam[1]['v'], 1e-9))

    def test_trig_next_in_manual_is_a_jump(self):
        E = L.Engine()
        P = dict(L.DEFAULTS, select=1.0, gotoblend='cut')
        cam = corners()
        E.step(cam, [], P, 0, 0.0)
        c, _l, info = E.step(cam, [], P, 0, 0.1, [('next',)])
        self.assertEqual(info['preset'], 2)
        self.assertTrue(close(c, cam[2]['v'], 1e-9))


class Playmodes(unittest.TestCase):
    def test_sequence_cuts_on_the_grid_in_order(self):
        cam = corners()
        P = dict(L.DEFAULTS, playmode='sequence', quant=4.0, defaulthold=6.0, trans='cut')
        frames = run(L.Engine(), cam, [], P, 0.0, 30.0)
        cuts = [i['beats'] for _t, _c, _l, i in frames if i['cut']]
        self.assertGreater(len(cuts), 4)
        for b in cuts[1:]:
            r = b % 4.0
            self.assertLess(min(r, 4.0 - r), 2.0 / 60.0 + 1e-6, b)
        order = []
        for _t, _c, _l, i in frames:
            if not order or order[-1] != i['preset']:
                order.append(i['preset'])
        self.assertEqual(order[:5], [0, 1, 2, 3, 0])

    def test_transition_eases_into_next(self):
        cam = corners(ease_name='linear')
        E = L.Engine()
        P = dict(L.DEFAULTS, playmode='sequence', quant=4.0, defaulthold=4.0, tdur=2.0, trans='ease')
        res = dict((b, E.step(cam, [], P, b, b * 0.5)) for b in (3.9, 4.0, 5.0, 6.5))
        self.assertTrue(close(res[5.0][0], L.vlerp(cam[0]['v'], cam[1]['v'], 0.5), 1e-9))
        self.assertTrue(close(res[6.5][0], cam[1]['v'], 1e-9))

    def test_random_never_repeats_and_is_seeded(self):
        cam = corners() + corners(3.0)
        P = dict(L.DEFAULTS, playmode='random', quant=1.0, minhold=1, maxhold=3, seed=5)
        seqs = []
        for _rep in range(2):
            E = L.Engine()
            order = []
            for k in range(400):
                info = E.step(cam, [], P, k * 0.25, k * 0.125)[2]
                if not order or order[-1] != info['preset']:
                    order.append(info['preset'])
            seqs.append(order)
            self.assertTrue(all(a != b for a, b in zip(order, order[1:])))
            self.assertGreater(len(set(order)), 4)
        self.assertEqual(seqs[0], seqs[1])

    def test_beat_mode_trig_quantised_and_cut(self):
        cam = corners()
        E = L.Engine()
        P = dict(L.DEFAULTS, playmode='beat', quant=4.0, defaulthold=64.0, tdur=2.0)
        E.step(cam, [], P, 1.0, 0.5)
        self.assertEqual(E.step(cam, [], P, 1.5, 0.75, [('next',)])[2]['preset'], 0)   # waits for the bar
        self.assertEqual(E.step(cam, [], P, 3.99, 2.0)[2]['preset'], 0)
        c, _l, info = E.step(cam, [], P, 4.0, 2.0)
        self.assertEqual((info['preset'], info['cut']), (1, 1.0))
        self.assertTrue(close(c, cam[1]['v'], 1e-9))               # beat mode = a hard cut

    def test_goto_in_sequence_resumes_from_target(self):
        cam = corners()
        E = L.Engine()
        P = dict(L.DEFAULTS, playmode='sequence', quant=4.0, defaulthold=4.0, trans='cut', gototime=1.0)
        E.step(cam, [], P, 0.0, 0.0)
        E.step(cam, [], P, 1.0, 0.5, [('goto', 2)])
        c, _l, info = E.step(cam, [], P, 3.0, 1.5)
        self.assertEqual(info['preset'], 2)
        self.assertTrue(close(c, cam[2]['v'], 1e-9))
        self.assertEqual(E.step(cam, [], P, 8.0, 4.0)[2]['preset'], 3)

    def test_mode_change_replans(self):
        cam = corners()
        E = L.Engine()
        P = dict(L.DEFAULTS, playmode='beat', quant=4.0, defaulthold=64.0)
        E.step(cam, [], P, 0.0, 0.0)
        P.update(playmode='random', quant=1.0, minhold=1.0, maxhold=3.0)
        got = set(E.step(cam, [], P, b * 0.25, b * 0.125)[2]['preset'] for b in range(1, 200))
        self.assertGreater(len(got), 2)

    def test_lag_smooths_select(self):
        cam = corners(ease_name='linear')
        E = L.Engine()
        P = dict(L.DEFAULTS, select=0.0, lag=0.5)
        E.step(cam, [], P, 0, 0.0)
        P['select'] = 1.0
        c, _l, info = E.step(cam, [], P, 0, 0.5)
        self.assertTrue(0.5 < info['select'] < 0.7)
        self.assertTrue(info['needs_tick'])


class ShakeLook(unittest.TestCase):
    def test_off_is_identity(self):
        c = corners()[0]['v']
        self.assertEqual(L.shake_vec(c, None, 1.0, 'off')[0], tuple(c))
        self.assertEqual(L.shake_vec(c, None, 1.0, 'handheld', 0.0)[0], tuple(c))

    def test_profiles_bounded_and_deterministic(self):
        c = corners()[0]['v']
        for prof in L.SHAKE_NAMES[1:]:
            bp, br = L.shake_bound(prof)
            for k in range(200):
                t = k * 0.037
                a = L.shake_vec(c, None, t, prof, beat_phase=(t % 1.0))
                self.assertEqual(a, L.shake_vec(c, None, t, prof, beat_phase=(t % 1.0)))
                self.assertLessEqual(a[2], bp + 1e-9, prof)
                for ax in (3, 4, 5):
                    self.assertLessEqual(abs(a[0][ax] - c[ax]), br + 1e-9, prof)

    def test_with_look_point_aim_noise_moves_the_point(self):
        c = (0, 0, 5) + (0,) * 9 + (45,)
        lk = (0,) * 6 + (1, 1, 1, 0, 0, 0)
        c2, l2, _o = L.shake_vec(c, lk, 0.7, 'handheld', 1.0, pscale=0.0)
        self.assertEqual(tuple(c2[:5]), tuple(c[:5]))              # no position, no rx / ry: Look At owns the aim
        self.assertGreater(R.length(l2[:3]), 1e-5)

    def test_global_target_aims_without_look_at(self):
        cam = [L.make_preset((3, 1, 4) + (0,) * 3 + (1, 1, 1, 0, 0, 0, 40))]
        E = L.Engine()
        c, lk, info = E.step(cam, [], dict(L.DEFAULTS, targetmode='op', targetpoint=(0, 1, 0)), 0, 0.0)
        want = R.td_pars(R.pose((3, 1, 4), (0, 1, 0), 0.0, 40))
        self.assertTrue(close(c[3:6], (want['rx'], want['ry'], want['rz']), 1e-9))
        self.assertIsNone(lk)
        self.assertAlmostEqual(info['dist'], 5.0)

    def test_global_target_drives_the_look_at(self):
        cam = corners()
        E = L.Engine()
        c, lk, _i = E.step(cam, looks(), dict(L.DEFAULTS, targetmode='op', targetpoint=(2, 3, 4), haslook=True), 0,
                           0.0)
        self.assertEqual(lk[:3], (2.0, 3.0, 4.0))
        self.assertTrue(close(c, cam[0]['v']))

    def test_look_damp(self):
        E = L.Engine()
        cam = corners()
        P = dict(L.DEFAULTS, targetmode='op', targetpoint=(0, 0, 0), lookdamp=0.5, haslook=True)
        E.step(cam, looks(), P, 0, 0.0)
        P['targetpoint'] = (4, 0, 0)
        _c, lk, info = E.step(cam, looks(), P, 0, 0.1)
        self.assertTrue(0.0 < lk[0] < 4.0)
        self.assertTrue(info['needs_tick'])

    def test_frame_portrait_uses_horizontal(self):
        d_port = L.frame_distance(1.0, 40.0, 1080, 1920)
        d_land = L.frame_distance(1.0, 40.0, 1920, 1080)
        self.assertAlmostEqual(d_port, 1.0 / math.sin(math.radians(20.0)), places=9)
        self.assertLess(d_port, d_land)                            # landscape: the vertical angle is the narrower
        c = L.frame_cam((0, 0, 10) + (0,) * 9 + (40,), (0, 0, 0), 1.0, 1080, 1920)
        self.assertAlmostEqual(c[2], d_port, places=9)

    def test_roll_and_fov_offsets(self):
        cam = corners()
        c, _l, _i = L.Engine().step(cam, [], dict(L.DEFAULTS, roll=10.0, fovoffset=-5.0), 0, 0.0)
        self.assertAlmostEqual(c[5], cam[0]['v'][5] + 10.0)
        self.assertAlmostEqual(c[12], 40.0)


class Output(unittest.TestCase):
    def test_names_and_values(self):
        names = L.out_names()
        self.assertEqual(names[:13], ['cs_' + n for n in L.CAM_PARS])
        self.assertEqual(names[13:25], ['cs_la_' + n for n in L.LOOK_PARS])
        self.assertEqual(len(set(names)), len(names))
        c, lk, info = L.Engine().step(corners(), looks(), dict(L.DEFAULTS, select=1.0, haslook=True), 0, 0.0)
        vals = L.out_values(c, lk, info, True, 7)
        self.assertEqual(len(vals), len(names))
        self.assertEqual(vals[names.index('cs_preset')], 1.0)
        self.assertEqual(vals[names.index('cs_ver')], 7.0)

    def test_empty_and_one(self):
        c, lk, info = L.Engine().step([], [], dict(L.DEFAULTS), 0, 0.0)
        self.assertIsNone(c)
        one = corners()[:1]
        c, lk, info = L.Engine().step(one, [], dict(L.DEFAULTS, select=2.7), 0, 0.0)
        self.assertTrue(close(c, one[0]['v']))

    def test_idle_manual_needs_no_tick(self):
        E = L.Engine()
        cam = corners()
        E.step(cam, [], dict(L.DEFAULTS, select=1.0), 0, 0.0)
        self.assertFalse(E.step(cam, [], dict(L.DEFAULTS, select=1.0), 0, 0.1)[2]['needs_tick'])


class Migration(unittest.TestCase):
    def test_v1_shots_become_presets(self):
        rows = [['name', 'px', 'py', 'pz', 'tx', 'ty', 'tz', 'roll', 'fov', 'rig', 'hold', 'trans', 'tdur', 'ease'],
                ['a', '3', '1', '4', '0', '1', '0', '10', '50', 'view', '0', '', '-1', 'outQuad'],
                ['', '1', '1', '1', '0', '0', '0', '0', '45', '', '', '', '', ''],
                ['b', '-2', '2', '6', '1', '0', '0', '0', '40', 'orbit', '0', '', '-1', 'nope']]
        cam, look = L.from_old_shots(rows, 'xyz', 'inOutSine')
        self.assertEqual((len(cam), len(look)), (2, 2))
        want = R.td_pars(R.pose((3, 1, 4), (0, 1, 0), 10.0, 50.0))
        self.assertTrue(close(cam[0]['v'], (3, 1, 4, want['rx'], want['ry'], want['rz'], 1, 1, 1, 0, 0, 0, 50), 1e-9))
        self.assertEqual(look[0]['v'][:3], (0.0, 1.0, 0.0))
        self.assertEqual((cam[0]['ease'], cam[1]['ease']), ('outQuad', 'inOutSine'))
        # the camera aims at the old target: its view axis (-Z) points from pos to target
        M = R.matrix_from_euler(cam[0]['v'][3], cam[0]['v'][4], cam[0]['v'][5], 'xyz')
        fwd = (-M[0][2], -M[1][2], -M[2][2])
        self.assertTrue(close(fwd, R.norm(R.sub((0, 1, 0), (3, 1, 4))), 1e-9))


if __name__ == '__main__':
    unittest.main()
