"""Offline tests for builders/cuelist_logic.py (CQ_cuelist). No TD. Run: python3 -m pytest -q test/test_cuelist.py"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'builders'))
import cuelist_logic as L  # noqa: E402

H = L.COLUMNS


def row(num, name='', trigger='manual', at='', fade='', curve='', kind='note', target='', value='', follow='',
        delay='', enabled='1'):
    d = dict(num=str(num), name=name, trigger=trigger, at=at, fade=fade, curve=curve, kind=kind, target=target,
             value=value, follow=follow, delay=delay, enabled=enabled)
    return [d.get(h, '') for h in H]


# 1 timecode -------------------------------------------------------------------------------------------------
def test_parse_shorthands():
    assert L.parse_tc('1h30') == 5400.0
    assert L.parse_tc('01h30m') == 5400.0
    assert L.parse_tc('0100') == 3600.0
    assert L.parse_tc('100000') == 36000.0
    assert L.parse_tc('00:00:01:12', 25) == 1.48
    for bad in ('', 'abc', '00:61:00:00', '00:00:00:25', None, '1h75'):
        assert L.parse_tc(bad, 25) is None


def test_df_reference_points():
    assert L.tc_to_frames(0, 1, 0, 2, 30, True) == 1800
    assert L.tc_to_frames(0, 10, 0, 0, 30, True) == 17982
    assert L.tc_to_frames(1, 0, 0, 0, 30, True) == 107892
    assert abs(L.seconds_of_frames(107892, 30, True) - 3600.0) < 0.004   # 30000/1001: DF drifts 3.6 ms/h
    n = L.tc_to_frames(0, 0, 59, 29, 30, True)
    assert L.frames_to_tc(n + 1, 30, True) == (0, 1, 0, 2)
    assert L.frames_to_tc(L.tc_to_frames(0, 10, 0, 0, 30, True), 30, True) == (0, 10, 0, 0)


def test_df_round_trip_3h_exhaustive():
    for n in range(0, 3 * 107892):
        assert L.tc_to_frames(*L.frames_to_tc(n, 30, True), 30, True) == n


def test_fmt_tc():
    assert L.fmt_tc(3600.0, 30, True) == '01:00:00;00'
    assert L.fmt_tc(61.04, 25) == '00:01:01:01'


# 2 engine ---------------------------------------------------------------------------------------------------
def eng(rows):
    g, err = L.parse_cues([H] + rows)
    return L.Engine(g), err


def test_go_order_disabled_skip_and_end():
    e, _ = eng([row(1, 'a'), row(2, 'b', enabled='0'), row(3, 'c')])
    assert e.go() and e.running == 0 and e.standby == 1
    assert e.go() and e.groups[e.running]['name'] == 'c'
    assert not e.go()
    assert e.drain()[1][-1][0] == 'go_end'


def test_group_rows_fire_together():
    e, _ = eng([row(1, kind='par', target='x:a', value='1'), row(1, kind='par', target='x:b', value='2')])
    e.go()
    out, _ = e.drain()
    assert sorted(o['target'] for o in out) == ['x:a', 'x:b']


def test_goto_unknown_noop():
    e, _ = eng([row(1, 'a'), row(2, 'b')])
    assert not e.goto('nope') and e.standby == 0
    assert e.goto('b') and e.standby == 1
    assert e.goto('1') and e.standby == 0


def test_queue_interrupt_ignore():
    rows = [row(1, kind='par', target='x:a', value='1', fade='2'), row(2, kind='par', target='x:a', value='0', fade='2')]
    for mode, fired in (('queue', False), ('interrupt', True), ('ignore', False)):
        e, _ = eng(rows)
        e.go(0, mode)
        e.tick(1.0, 1.0)
        assert e.go(1.0, mode) is fired
        if mode == 'interrupt':
            e.tick(1.0, 0.0)
            assert abs(e.values['par:x:a'] - 0.5) < 1e-9      # starts from current value: no jump
        if mode == 'queue':
            e.tick(2.0, 1.0)                                   # fade 1 ends, queued GO fires
            assert e.running == 1
        if mode == 'ignore':
            e.tick(2.0, 1.0)
            assert e.running == 0


def test_follow_and_continue():
    e, _ = eng([row(1, kind='par', target='x:a', value='1', fade='2'), row(2, trigger='follow', delay='0.5'),
                row(3, trigger='follow', follow='continue')])
    e.go(0.0)
    e.tick(0.4, 0.4)
    assert e.running == 0
    e.tick(0.5, 0.1)
    assert e.running == 1                              # 2 = start + 0.5
    e.tick(1.9, 1.4)
    assert e.running == 1
    e.tick(2.01, 0.11)
    assert e.running == 2                              # 3 = after the longest fade (2 s)


# 3 timecode triggers ----------------------------------------------------------------------------------------
def tc_rows(n, seed=1):
    rnd = random.Random(seed)
    rows = []
    for i in range(n):
        rows.append(row(i + 1, trigger='tc', at='%.3fs' % (0.5 + i * 0.3), kind='par',
                        target='x:%d' % rnd.randrange(4), value=str(rnd.random())))
    return rows


def test_tc_fire_once_and_jump_resolves():
    e, _ = eng(tc_rows(100))
    t = 0.0
    fired = []
    e.tick(0, 0, clock_t=0.0, clock_ok=True)
    e.drain()
    while t < 31.0:
        t += 1 / 60.0
        e.tick(t, 1 / 60.0, clock_t=t, clock_ok=True)
        fired += [d for n, d in e.drain()[1] if n == 'fire']
    assert len(fired) == 100 and len(set(fired)) == 100


def test_jump_state_equals_replay_property():
    for seed in range(20):
        rows = tc_rows(40, seed)
        a, _ = eng(rows)
        b, _ = eng(rows)
        target = random.Random(seed).uniform(1.5, 14)
        t = 0.0
        a.tick(0, 0, clock_t=0.0, clock_ok=True)
        while t + 1 / 60.0 <= target:
            t += 1 / 60.0
            a.tick(t, 1 / 60.0, clock_t=t, clock_ok=True)
        b.tick(0, 0, clock_t=0.0, clock_ok=True)
        b.tick(0, 0, clock_t=t, clock_ok=True)            # one big step = locate
        assert any(n == 'locate' for n, _ in b.drain()[1])
        assert a.values == b.values
        assert a.standby == b.standby


def test_first_tick_keeps_manual_fade():
    e, _ = eng([row(1, kind='par', target='x:a', value='1', fade='2')])
    e.go(0.0)
    e.tick(0.1, 0.1, clock_t=0.0, clock_ok=True)
    assert e.fader.active()


def test_rewind_locates_no_fire():
    e, _ = eng(tc_rows(10))
    e.tick(0, 0, clock_t=2.0, clock_ok=True)
    e.drain()
    e.tick(0, 0, clock_t=1.0, clock_ok=True)
    ev = [n for n, _ in e.drain()[1]]
    assert 'locate' in ev and 'fire' not in ev


# 4 fades ----------------------------------------------------------------------------------------------------
def test_curves():
    for c in L.CURVES:
        assert L.curve(1.0, c) == 1.0
        prev = -1
        for i in range(101):
            v = L.curve(i / 100.0, c)
            assert v >= prev
            prev = v
    assert L.curve(0.0, 'linear') == 0.0 and L.curve(0.0, 'smooth') == 0.0


def test_fade_timing_and_rate():
    f = L.Fader()
    f.start('k', 0, 1, 2.0, 'linear')
    assert abs(f.tick(1.0)[0][1] - 0.5) < 1e-9
    assert f.tick(0.5, 0.0)[0][1] == 0.5                 # Rate 0 holds
    assert f.tick(1.0)[0][1] == 1.0 and f.done == ['k'] and not f.active()
    assert f.tick(1.0) == []                             # nothing written after done
    f.start('k', 0, 1, 2.0, 'linear', now=10.0)          # started mid-frame: the first tick counts from the start
    assert abs(f.tick(0.016, 1.0, now=10.004)[0][1] - 0.002) < 1e-9


# 5 chase ----------------------------------------------------------------------------------------------------
def test_chase_lock_freewheel_lost_relock():
    c = L.Chase(fps=25, lockwindow=3, freewheel=2.0)
    own, src, dt = 0.0, 10.0, 1 / 60.0
    states = []
    for i in range(60):
        src += dt + (random.Random(i).choice([-1, 0, 1]) / 25.0 if i > 30 else 0)   # +-1 frame jitter
        own, st, err, loc = c.step(own, src, dt)
        states.append(st)
    assert states[5:].count('locked') >= 50 and states[-1] == 'locked'
    for i in range(int(1.5 / dt)):                    # source stops
        own, st, _, _ = c.step(own, src, dt)
    assert st == 'freewheel' and own > src
    for i in range(int(1.0 / dt)):
        own, st, _, _ = c.step(own, src, dt)
    assert st == 'lost'
    held = own
    own, st, _, _ = c.step(own, src, dt)
    assert own == held
    for i in range(30):
        src += dt
        own, st, _, _ = c.step(own, src, dt)
    assert st == 'locked'


def test_chase_backward_is_locate():
    c = L.Chase(fps=25)
    own = 5.0
    for i in range(10):
        own, st, _, _ = c.step(own, 5.0 + (i + 1) / 60.0, 1 / 60.0)
    own, st, err, loc = c.step(own, 1.0, 1 / 60.0)
    assert loc and own == 1.0


# 6 log / 7 parsers / 8 tracking ---------------------------------------------------------------------------
def test_log_ring_and_csv():
    r = L.LogRing(3)
    for i in range(5):
        r.add([i])
    assert r.rows == [[2], [3], [4]]
    assert L.csv_line(['a', 'b,c', 'd"e']) == 'a,"b,c","d""e"\n'


def test_parse_bad_rows_never_raise():
    g, err = L.parse_cues([H, row('x'), row(1, trigger='zz'), row(2, kind='zz'), ['', '3'], row(4, trigger='tc', at='bad'),
                           row(5, trigger='bar', at='1.1'), row(5, kind='note')])
    assert [x['num'] for x in g] == [3.0, 5.0] and len(err) == 5
    assert L.parse_cues([]) == ([], [])
    assert L.parse_cues([['a', 'b']])[0] == []


def test_tracking_vs_direct():
    rows = [row(1, trigger='tc', at='1s', kind='par', target='x:a', value='1'),
            row(2, trigger='tc', at='2s', kind='par', target='x:b', value='1'),
            row(3, trigger='tc', at='3s', kind='par', target='x:a', value='0')]
    g, _ = L.parse_cues([H] + rows)
    assert L.resolve_state(g, 3.5) == {'par:x:a': '0', 'par:x:b': '1'}
    assert L.resolve_state(g, 3.5, tracking=False) == {'par:x:a': '0'}
    assert L.resolve_state(g, 0.5) == {}
