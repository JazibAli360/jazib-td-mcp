"""Offline tests for builders/fps_gov_logic.py (FG_fps_governor step / hysteresis, no TD). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fps_gov.py'"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'builders'))
import fps_gov_logic as L  # noqa: E402

FAST = (1000 / 60.0, 5.0)     # 60 fps, 5 ms busy -> 11.7 ms headroom
SLOW = (1000 / 40.0, 24.0)    # 40 fps
MID = (1000 / 58.0, 15.0)     # 58 fps: between the thresholds


def run(st, c, sample, n):
    ev = []
    for _ in range(n):
        r = L.tick(st, sample[0], sample[1], c)
        if r:
            ev.append((st['frames'], r))
    return ev


class Quality(unittest.TestCase):
    def test_ladder(self):
        self.assertEqual([L.quality(s, 4, 0.2) for s in range(5)], [1.0, 0.8, 0.6, 0.4, 0.2])
        self.assertEqual(L.quality(9, 4, 0.2), 0.2)
        self.assertEqual(L.quality(-1, 4, 0.2), 1.0)
        self.assertEqual(L.quality(3, 0, 0.2), 1.0)    # Steps 0 = never below full

    def test_cfg_clamps(self):
        c = L.cfg(target=0, downafter=0, upafter=-5, steps=-1, floor=2, upmargin=-1)
        self.assertEqual((c['target'], c['downafter'], c['upafter'], c['steps'], c['floor'], c['upmargin']),
                         (1.0, 1, 1, 0, 1.0, 0.0))


class Hysteresis(unittest.TestCase):
    def test_holds_at_full_when_fast(self):
        st, c = L.new_state(), L.cfg()
        self.assertEqual(run(st, c, FAST, 1000), [])
        o = L.outputs(st, c)
        self.assertEqual((o['quality'], o['step'], o['fps']), (1.0, 0.0, 60.0))
        self.assertAlmostEqual(o['headroom_ms'], 11.67, places=2)

    def test_steps_down_after_downafter_and_stops_at_floor(self):
        st, c = L.new_state(), L.cfg(downafter=30, steps=4, floor=0.25)
        ev = run(st, c, SLOW, 30)
        self.assertEqual(ev, [(30, 1)])                 # exactly Downafter slow frames
        ev = run(st, c, SLOW, 200)
        self.assertEqual([e[1] for e in ev], [1, 1, 1])  # 30 frames each after the EMA re-seed
        self.assertEqual([e[0] for e in ev], [60, 90, 120])
        self.assertEqual(st['step'], 4)
        self.assertEqual(L.outputs(st, c)['quality'], 0.25)

    def test_short_dip_does_nothing(self):
        st, c = L.new_state(), L.cfg(downafter=30)
        run(st, c, FAST, 50)
        run(st, c, SLOW, 10)          # the EMA stays low a few frames longer than the dip itself
        run(st, c, FAST, 50)
        run(st, c, SLOW, 10)
        run(st, c, FAST, 50)
        self.assertEqual(st['step'], 0)

    def test_steps_up_after_upafter(self):
        st, c = L.new_state(), L.cfg(downafter=10, upafter=100)
        run(st, c, SLOW, 20)
        self.assertEqual(st['step'], 2)
        ev = run(st, c, FAST, 250)
        self.assertEqual(ev, [(120, -1), (220, -1)])
        self.assertEqual(L.outputs(st, c)['quality'], 1.0)

    def test_no_step_up_without_headroom(self):
        st, c = L.new_state(), L.cfg(downafter=10, upafter=50, upmargin=3)
        run(st, c, SLOW, 10)
        self.assertEqual(run(st, c, (1000 / 60.0, 15.0), 500), [])    # 60 fps but 1.7 ms headroom
        self.assertEqual(st['step'], 1)

    def test_between_thresholds_holds(self):
        st, c = L.new_state(), L.cfg(downafter=10, upafter=50)
        run(st, c, SLOW, 10)
        self.assertEqual(run(st, c, MID, 500), [])
        self.assertEqual(st['step'], 1)

    def test_jitter_between_does_not_restart_the_up_count(self):
        st, c = L.new_state(), L.cfg(downafter=10, upafter=100)
        run(st, c, SLOW, 10)
        for _ in range(10):                      # 60 fps with short 58 fps wobbles (machine jitter)
            run(st, c, FAST, 15)
            run(st, c, MID, 3)
        self.assertEqual(st['step'], 0)

    def test_outside_drop_with_cheap_frames_does_not_step_down(self):
        st, c = L.new_state(), L.cfg(downafter=10)
        self.assertEqual(run(st, c, (1000 / 40.0, 4.0), 300), [])   # 40 fps but this TD cooks 4 ms
        self.assertEqual(st['step'], 0)

    def test_outputs_keep_last_values_while_reseeding(self):
        st, c = L.new_state(), L.cfg(downafter=10)
        run(st, c, SLOW, 9)
        L.outputs(st, c)
        run(st, c, SLOW, 1)                      # step change re-seeds the EMA
        o = L.outputs(st, c)
        self.assertEqual(o['step'], 1.0)
        self.assertGreater(o['fps'], 30)
        self.assertLess(o['headroom_ms'], 0)

    def test_backoff_doubles_and_resets(self):
        st, c = L.new_state(), L.cfg(downafter=10, upafter=100)
        run(st, c, SLOW, 10)                     # step 1
        run(st, c, FAST, 100)                    # up at frame 110
        self.assertEqual(st['step'], 0)
        run(st, c, SLOW, 10)                     # down 10 frames later -> backoff 2
        self.assertEqual((st['step'], st['backoff']), (1, 2))
        ev = run(st, c, FAST, 300)
        self.assertEqual(ev[0][0] - 120, 200)    # waited 2 x Upafter
        run(st, c, FAST, 101)                    # held a whole base wait
        self.assertEqual(st['backoff'], 1)

    def test_stall_sample_is_capped(self):
        st, c = L.new_state(), L.cfg(downafter=5)
        run(st, c, FAST, 20)
        L.tick(st, 2000.0, 2000.0, c)            # one 2 s stall
        self.assertGreater(L.outputs(st, c)['fps'], 40)
        self.assertEqual(st['step'], 0)

    def test_steps_lowered_live_and_zero(self):
        st, c = L.new_state(), L.cfg(downafter=5, steps=4)
        run(st, c, SLOW, 20)
        self.assertEqual(st['step'], 4)
        c2 = L.cfg(steps=2, downafter=5)
        L.tick(st, *FAST, c2)
        self.assertEqual(st['step'], 2)
        st0, c0 = L.new_state(), L.cfg(steps=0, downafter=5)
        run(st0, c0, SLOW, 100)
        self.assertEqual(L.outputs(st0, c0)['quality'], 1.0)

    def test_busy_sampled_every_few_frames(self):
        st, c = L.new_state(), L.cfg(downafter=10, upafter=50)
        run(st, c, SLOW, 10)
        self.assertEqual(st['step'], 1)
        for i in range(40):                       # no busy sample yet: headroom 0, no blind step-up
            L.tick(st, 1000 / 60.0, None, c)
        self.assertEqual(st['up'], 0)
        for i in range(60):
            L.tick(st, 1000 / 60.0, 5.0 if i % 4 == 0 else None, c)
        self.assertEqual(st['step'], 0)

    def test_zero_interval_ignored(self):
        st, c = L.new_state(), L.cfg()
        self.assertEqual(L.tick(st, 0, 0, c), 0)
        self.assertIsNone(st['ema_int'])


class PxPlan(unittest.TestCase):
    def test_one_rung_per_step_at_steps5(self):
        c = L.cfg(steps=5, floor=0.25)
        plans = [L.px_plan(L.quality(s, c['steps'], c['floor'])) for s in range(6)]
        self.assertEqual(plans, [(False, 1.0, 1.0), (True, 1.0, 1.0), (True, 0.75, 1.0), (True, 0.5, 1.0),
                                 (True, 0.5, 0.75), (True, 0.5, 0.5)])

    def test_thresholds_ordered(self):
        t = [x for x, _ in L.PX_LEVELS]
        self.assertEqual(t, sorted(t, reverse=True))
        self.assertEqual(L.px_plan(1.0), (False, 1.0, 1.0))
        self.assertEqual(L.px_plan(0.0), (True, 0.5, 0.5))


if __name__ == '__main__':
    unittest.main()
