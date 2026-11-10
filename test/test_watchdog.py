"""Offline tests for tools/td_watchdog.py decide() (stdlib only)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import td_watchdog as W  # noqa: E402

CFG = {'stale': 8.0, 'boot_grace': 90.0, 'max_restarts': 3, 'window': 300.0, 'loop_backoff': 30.0}


class Decide(unittest.TestCase):
    def st(self, **kw):
        d = {'launched_at': None, 'restarts': []}
        d.update(kw)
        return d

    def test_no_td_launches(self):
        self.assertEqual(W.decide(1000, [], None, self.st(), CFG)[0], 'launch')

    def test_fresh_heartbeat_ok_and_remembered(self):
        st = self.st()
        self.assertEqual(W.decide(1000, [5], {'pid': 5, 'time': 995}, st, CFG)[0], 'ok')
        self.assertIn(5, st['beat_pids'])

    def test_stale_heartbeat_after_beating_kills_with_evidence(self):
        st = self.st(beat_pids={5})
        self.assertEqual(W.decide(1000, [5], {'pid': 5, 'time': 980}, st, CFG, hung={'dialog': 'Fatal Error'})[0], 'kill')

    def test_stale_without_evidence_waits_then_hard_stale_kills(self):
        st = self.st(beat_pids={5})
        self.assertEqual(W.decide(1000, [5], {'pid': 5, 'time': 980}, st, CFG)[0], 'warn')  # 20 s < 3 x 8
        self.assertEqual(W.decide(1000, [5], {'pid': 5, 'time': 970}, st, CFG)[0], 'kill')  # 30 s > 24

    def test_boot_grace_waits(self):
        self.assertEqual(W.decide(1000, [5], None, self.st(launched_at=950), CFG)[0], 'wait')

    def test_never_beat_after_grace_warns_not_kills(self):
        # the 19:24-19:25 kill loop: a project without /watchdog_hb must never be killed
        self.assertEqual(W.decide(1000, [5], None, self.st(launched_at=800), CFG)[0], 'warn')
        self.assertEqual(W.decide(1000, [6], {'pid': 5, 'time': 999}, self.st(launched_at=800), CFG)[0], 'warn')

    def test_foreign_td_gets_one_grace(self):
        st = self.st()
        self.assertEqual(W.decide(1000, [5], None, st, CFG)[0], 'wait')
        self.assertEqual(st['launched_at'], 1000)

    def test_two_tds_never_kill_extra(self):  # T-82: the other TD (scratch / user's) is left alone
        st = self.st(); st['beat_pids'] = {6}
        self.assertEqual(W.decide(1000, [5, 6], {'pid': 6, 'time': 999.5}, st, CFG)[0], 'ok')

    def test_crash_loop_backs_off(self):
        st = self.st(restarts=[900, 950, 990])
        self.assertEqual(W.decide(1000, [], None, st, CFG)[0], 'wait')
        self.assertEqual(W.decide(1025, [], None, st, CFG)[0], 'launch')

    def test_paused_never_acts(self):
        self.assertEqual(W.decide(1000, [], None, self.st(), CFG, paused=True)[0], 'paused')
        self.assertEqual(W.decide(1000, [5], {'pid': 5, 'time': 1}, self.st(), CFG, paused=True)[0], 'paused')


if __name__ == '__main__':
    unittest.main()


class CrashRecovery(unittest.TestCase):
    """T-77: open the crash autosave unless it holds the COMP that was in flight."""
    def test_newest_save(self):
        ls = ['P.toe', 'P.3.toe', 'P.9.toe', 'CrashAutoSave.P.9.toe']
        self.assertEqual(W.newest_save('/x/P.toe', ls, {'P.toe': 1, 'P.3.toe': 5, 'P.9.toe': 9, 'CrashAutoSave.P.9.toe': 99}), 'P.9.toe')

    def test_suspects(self):
        import json as j
        lines = [j.dumps({'time': '2026-10-26T10:12:04Z', 'phase': 'start', 'code': "c = op('/project1/lab/BJ_urdu_type')"}),
                 j.dumps({'time': '2026-10-26T10:12:01Z', 'phase': 'start', 'code': "op('/project1/lab/OK_one')"}),
                 j.dumps({'time': '2026-10-26T10:12:02Z', 'phase': 'end', 'code': "op('/project1/lab/OK_one')"})]
        self.assertEqual(W.suspects_from_exec_log(lines, '2026-10-26T10:11:00'), ['/project1/lab/BJ_urdu_type'])


class FalseKill(unittest.TestCase):
    """T-78: stale heartbeat but TD answered the MCP recently -> warn, never kill."""
    def test_alive_via_mcp(self):
        cfg = dict(stale=60, boot_grace=120, max_restarts=3, window=300, loop_backoff=30)
        st = {'beat_pids': {7}, 'restarts': []}
        hb = {'pid': 7, 'time': 0}
        self.assertEqual(W.decide(100.0, [7], hb, st, cfg, mcp_alive_at=90.0)[0], 'warn')
        # T-95: an MCP reply 90 s ago and no hang evidence: still under hard_stale (180) -> warn, not kill
        self.assertEqual(W.decide(100.0, [7], hb, st, cfg, mcp_alive_at=10.0)[0], 'warn')
        self.assertEqual(W.decide(100.0, [7], hb, st, cfg, mcp_alive_at=10.0, hung={'state': 'U'})[0], 'kill')
        self.assertEqual(W.decide(300.0, [7], hb, st, cfg, mcp_alive_at=10.0)[0], 'kill')  # silent 290 s > 180


class CutOffReplies(unittest.TestCase):
    """T-79: a reply cut off by the crash is still in flight."""
    def test_disconnected_end_is_suspect(self):
        import json as j
        code = "g['build']('/project1/lab') ; op('/project1/lab/BJ_urdu_type')"
        lines = [j.dumps({'time': '2026-10-26T11:11:28Z', 'phase': 'start', 'code': code}),
                 j.dumps({'time': '2026-10-26T11:11:38Z', 'phase': 'end', 'ok': False, 'code': code,
                          'error': 'TouchDesigner disconnected before replying'})]
        self.assertIn('/project1/lab/BJ_urdu_type', W.suspects_from_exec_log(lines, '2026-10-26T11:10:00'))


class TimeoutIsNoReply(unittest.TestCase):
    """T-82: MCP-side timeouts are not replies (hung TD kept 'alive' by polling agents)."""
    def test_timeout_rows(self):
        import json as j
        import tempfile
        rows = [{'time': '2026-10-26T11:19:29Z', 'phase': 'end', 'ok': True, 'code': 'x'},
                {'time': '2026-10-26T11:26:49Z', 'phase': 'end', 'ok': False, 'code': 'project.name',
                 'error': 'TouchDesigner timeout after 60000 ms on exec'}]
        with tempfile.NamedTemporaryFile('w', suffix='.log', delete=False) as f:
            f.write('\n'.join(j.dumps(r) for r in rows) + '\n')
        try:
            import calendar
            import time as t
            self.assertEqual(W.last_mcp_reply(f.name), calendar.timegm(t.strptime('2026-10-26T11:19:29', '%Y-%m-%dT%H:%M:%S')))
        finally:
            os.unlink(f.name)
        code = "c = op('/project1/lab/LP_laser_path')"
        lines = [j.dumps({'time': '2026-10-26T11:19:29Z', 'phase': 'start', 'code': code}),
                 j.dumps({'time': '2026-10-26T11:20:29Z', 'phase': 'end', 'ok': False, 'code': code,
                          'error': 'TouchDesigner timeout after 60000 ms on exec'})]
        self.assertIn('/project1/lab/LP_laser_path', W.suspects_from_exec_log(lines, '2026-10-26T11:19:00'))


class TimeoutsAreNotReplies(unittest.TestCase):
    """T-80: lanes' own timeouts kept re-arming the 'TD answered' guard."""
    def test_only_ok_counts(self):
        import json as j, tempfile, os as o
        f = tempfile.NamedTemporaryFile('w', delete=False, suffix='.log')
        f.write(j.dumps({'time': '2026-10-26T11:30:00Z', 'phase': 'end', 'ok': True, 'code': 'a'}) + '\n')
        f.write(j.dumps({'time': '2026-10-26T11:40:00Z', 'phase': 'end', 'ok': False, 'code': '1',
                         'error': 'TouchDesigner timeout after 30000 ms'}) + '\n')
        f.close()
        t = W.last_mcp_reply(f.name)
        o.remove(f.name)
        import calendar, time as tm
        self.assertEqual(t, calendar.timegm(tm.strptime('2026-10-26T11:30:00', '%Y-%m-%dT%H:%M:%S')))


class CrashSaveSanity(unittest.TestCase):
    def test_sizes(self):
        self.assertFalse(W.crash_save_sane(0, 2_000_000))
        self.assertFalse(W.crash_save_sane(300_000, 2_000_000))
        self.assertTrue(W.crash_save_sane(2_100_000, 2_000_000))


class ScratchTdCmdline(unittest.TestCase):
    def test_scratch(self):
        self.assertTrue(W.is_scratch_td('/Applications/TouchDesigner 2.app/Contents/MacOS/TouchDesigner /x/jazib-td-mcp/projects/scratch/Scratch.toe'))
        self.assertFalse(W.is_scratch_td('/Applications/TouchDesigner 2.app/Contents/MacOS/TouchDesigner /x/projects/JazibTD_home.108.toe'))


class BuildTdsIgnored(unittest.TestCase):
    """T-120: build TDs b2 / b3 (projects/buildN/, scratch_td_<name>.json) are side TDs like scratch."""
    def test_cmdline(self):
        exe = '/Applications/TouchDesigner 2.app/Contents/MacOS/TouchDesigner '
        self.assertTrue(W.is_scratch_td(exe + '/x/jazib-td-mcp/projects/build2/Build2.toe'))
        self.assertTrue(W.is_scratch_td(exe + '/x/jazib-td-mcp/projects/build3/Build3.4.toe'))
        self.assertFalse(W.is_scratch_td(exe + '/x/projects/JazibTD_home.108.toe'))

    def test_hb_and_list_of_states(self):
        self.assertFalse(W.hb_is_main({'pid': 2, 'project': '/r/projects/build2/Build2.toe'}, '/r/projects/JazibTD_home.toe'))
        states = [{'state': 'running', 'pid': 9}, {'state': 'running', 'pid': 11}, {'state': 'running', 'pid': 5}]
        self.assertEqual(W.scratch_pids([5, 9, 11], states, 1000.0, main_pid=5), {9, 11})
        self.assertEqual(W.scratch_pids([5], [], 1000.0, main_pid=5), set())


class ScratchIgnored(unittest.TestCase):
    """T-83: the scratch TD (tools/scratch_td.py) is never managed or killed; only the --toe project's heartbeat counts."""
    def test_project_base(self):
        self.assertEqual(W.project_base('/p/JazibTD_home.106.toe'), 'JazibTD_home')
        self.assertEqual(W.project_base('CrashAutoSave.JazibTD_home.3.toe'), 'JazibTD_home')
        self.assertEqual(W.project_base('JazibTD_home.toe'), 'JazibTD_home')

    def test_hb_is_main(self):
        toe = '/r/projects/JazibTD_home.toe'
        self.assertTrue(W.hb_is_main({'pid': 1, 'project': '/r/projects/JazibTD_home.106.toe'}, toe))
        self.assertTrue(W.hb_is_main({'pid': 1}, toe))  # old heartbeat without project
        self.assertFalse(W.hb_is_main({'pid': 2, 'project': '/r/projects/scratch/JazibTD_home.toe'}, toe))
        self.assertFalse(W.hb_is_main({'pid': 2, 'project': '/r/projects/scratch/Scratch.toe'}, toe))
        self.assertFalse(W.hb_is_main(None, toe))

    def test_scratch_pids(self):
        now = 1000.0
        self.assertEqual(W.scratch_pids([5, 9], None, now), set())
        self.assertEqual(W.scratch_pids([5, 9], {'state': 'running', 'pid': 9}, now, main_pid=5), {9})
        self.assertEqual(W.scratch_pids([5], {'state': 'running', 'pid': 5}, now, main_pid=5), set(), 'main never scratch')
        launching = {'state': 'launching', 'time': 990.0, 'before': [5]}
        self.assertEqual(W.scratch_pids([5, 9], launching, now, main_pid=5), {9})
        self.assertEqual(W.scratch_pids([5, 9], dict(launching, time=0.0), now, main_pid=5), set(), 'launch grace over')

    def test_no_kill_extra_with_scratch_running(self):
        # main pid 5 beating, scratch pid 9 running: the watchdog sees only [5] -> ok, never kill_extra
        sc = W.scratch_pids([5, 9], {'state': 'running', 'pid': 9}, 1000.0, main_pid=5)
        managed = [p for p in [5, 9] if p not in sc]
        self.assertEqual(W.decide(1000, managed, {'pid': 5, 'time': 999}, {'restarts': []}, CFG)[0], 'ok')
        self.assertNotEqual(W.decide(1000, [5, 9], {'pid': 5, 'time': 999}, {'restarts': []}, CFG)[0], 'kill_extra')  # T-82


class TimeoutIsNotAReply(unittest.TestCase):
    """26 Oct 16:20-16:31: exec timeouts counted as TD replies kept a hung TD alive (T-78 guard re-armed)."""
    def test_timeouts_ignored(self):
        import json as j
        import tempfile
        f = tempfile.NamedTemporaryFile('w', suffix='.log', delete=False)
        f.write(j.dumps({'time': '2026-10-26T11:00:00Z', 'phase': 'end', 'ok': True}) + '\n')
        f.write(j.dumps({'time': '2026-10-26T11:31:24Z', 'phase': 'end', 'ok': False,
                         'error': 'TouchDesigner timeout after 10000 ms on exec'}) + '\n')
        f.close()
        import calendar
        import time as t
        self.assertEqual(W.last_mcp_reply(f.name), calendar.timegm(t.strptime('2026-10-26T11:00:00', '%Y-%m-%dT%H:%M:%S')))
        os.remove(f.name)


class T79(unittest.TestCase):
    """T-95: two independent signals + hang evidence before a kill; recovery once per relaunched TD."""
    CFG = dict(stale=60, boot_grace=120, max_restarts=3, window=300, loop_backoff=30)

    def test_t78_replay_never_kills(self):
        # 16:01:52 frame heartbeat stops (absTime frozen), MCP heartbeat (ping every 20 s) keeps coming
        st = {'beat_pids': {36417}, 'restarts': []}
        hb = {'pid': 36417, 'time': 1000.0}
        for now in (1061, 1120, 1300):
            alive = W.mcp_alive(36417, None, {'pid': 36417, 'time': now - 15})
            self.assertEqual(W.decide(now, [36417], hb, st, self.CFG, mcp_alive_at=alive)[0], 'warn')

    def test_dialog_without_mcp_kills_fast(self):
        st = {'beat_pids': {5}, 'restarts': []}
        ev = W.hang_evidence([{'pid': 5, 'owner': 'TouchDesigner', 'name': 'Fatal Error'}], 5, 'S')
        self.assertEqual(W.decide(1061, [5], {'pid': 5, 'time': 1000}, st, self.CFG, mcp_alive_at=990, hung=ev)[0], 'kill')

    def test_hb_file_gone_uses_last_beat(self):
        st = {'beat_pids': set(), 'restarts': []}
        self.assertEqual(W.decide(1000, [5], {'pid': 5, 'time': 999}, st, self.CFG)[0], 'ok')
        self.assertEqual(W.decide(1100, [5], None, st, self.CFG)[0], 'warn')   # 101 s < 180
        self.assertEqual(W.decide(1200, [5], None, st, self.CFG)[0], 'kill')   # 201 s

    def test_hang_evidence(self):
        H = W.hang_evidence
        self.assertEqual(H([], 5, 'S'), {})
        self.assertEqual(H([{'pid': 5, 'owner': 'TouchDesigner', 'name': 'JazibTD_home.97.toe'}], 5, 'R'), {})
        self.assertIn('dialog', H([{'pid': 5, 'owner': 'TouchDesigner', 'name': 'Fatal Error - saved CrashAutoSave'}], 5, 'S'))
        self.assertIn('dialog', H([{'pid': 88, 'owner': 'UserNotificationCenter', 'name': 'TouchDesigner quit unexpectedly'}], 5, 'S'))
        self.assertEqual(H([{'pid': 6, 'owner': 'Finder', 'name': 'Fatal Error'}], 5, 'S'), {})  # other app
        self.assertEqual(H([], 5, 'U'), {'state': 'U'})
        self.assertEqual(H([], 5, 'S+'), {})
        self.assertEqual(H([], 5, ''), {})

    def test_mcp_alive_and_frozen(self):
        self.assertEqual(W.mcp_alive(5, None, None), None)
        self.assertEqual(W.mcp_alive(5, 100.0, {'pid': 5, 'time': 150.0}), 150.0)
        self.assertEqual(W.mcp_alive(5, 100.0, {'pid': 6, 'time': 150.0}), 100.0)  # another TD's file
        self.assertEqual(W.frames_frozen_s(200.0, {'frame_changed_at': 140.0}), 60.0)
        self.assertIsNone(W.frames_frozen_s(200.0, {}))

    def test_recover_due_once_per_pid(self):
        st = {'recover_pending': True}
        self.assertFalse(W.recover_due(st, 'wait', 9))
        self.assertTrue(W.recover_due(st, 'ok', 9))
        self.assertFalse(W.recover_due(st, 'ok', 9))
        st['recover_pending'] = True
        self.assertFalse(W.recover_due(st, 'ok', 9))     # same TD never twice
        self.assertTrue(W.recover_due(st, 'ok', 10))
        self.assertFalse(W.recover_due({}, 'ok', 11))    # TD the watchdog did not launch: never

    def test_list_windows_is_safe(self):
        rows = W.list_windows()  # real CoreGraphics on macOS, [] elsewhere; never raises
        self.assertIsInstance(rows, list)
        for r in rows[:3]:
            self.assertEqual(set(r), {'pid', 'owner', 'name'})


import td_recover as R  # noqa: E402
import lane as LN  # noqa: E402


class Recover(unittest.TestCase):
    def test_lanes_keep(self):
        now = 1_800_000_000.0
        fresh = R.iso(now - 60)
        old = R.iso(now - 7 * 3600)
        keep, stale = R.lanes_keep({'BK_dmx_out': {'agent': 'l2', 'time': fresh},
                                    '/project1/lab/LK_projection_room': {'agent': 'l3', 'time': fresh},
                                    'OLD_one': {'agent': 'x', 'time': old}, 'NOTIME': {}}, now)
        self.assertEqual(keep, {'BK_dmx_out', 'LK_projection_room', 'NOTIME'})
        self.assertEqual(stale, ['OLD_one'])
        self.assertEqual(R.lanes_keep(None, now), (set(), []))

    def test_plan_and_park_code(self):
        steps = R.plan('/project1/lab', {'BK_dmx_out'})
        self.assertEqual([s[1] for s in steps], ['td_reload', 'td_exec', 'td_autosave', 'td_save_project'])
        self.assertEqual(steps[2][2], {'minutes': 5})
        code = steps[1][2]['code']
        compile(code, 'park', 'exec')
        code.encode('ascii')
        self.assertIn("['BK_dmx_out']", code)
        self.assertNotIn('allowCooking = True', code)  # never un-parks

    def test_park_code_runs(self):
        class C:
            def __init__(s, n, t='baseCOMP', on=True):
                s.name, s.OPType, s.isCOMP, s.allowCooking = n, t, True, on
        kids = [C('A'), C('B'), C('note', 'annotateCOMP'), C('D', on=False)]
        lab = type('L', (), {'children': kids})()
        ns = {'op': lambda p: lab}
        code = R.park_code('/project1/lab', {'B'}).splitlines()
        exec('\n'.join(code[:-1]), ns)
        r = eval(code[-1], ns)
        self.assertEqual(r['parked'], ['A'])
        self.assertEqual(r['kept'], ['B'])
        self.assertTrue(kids[1].allowCooking and kids[2].allowCooking and not kids[0].allowCooking)

    def test_recent_lab_comps(self):
        import json as j
        lines = [j.dumps({'time': '2026-10-26T11:02:45.452Z', 'phase': 'start', 'code': "c=op('/project1/lab/BK_dmx_out')"}),
                 j.dumps({'time': '2026-10-26T10:00:00.000Z', 'phase': 'start', 'code': "op('/project1/lab/OLD')"}),
                 'not json']
        self.assertEqual(R.recent_lab_comps(lines, '2026-10-26T10:55:00'), {'BK_dmx_out'})

    def test_idempotent_and_summary(self):
        self.assertTrue(R.already_done({'pid': 5, 'status': 'done'}, 5))
        self.assertFalse(R.already_done({'pid': 5, 'status': 'partial'}, 5))
        self.assertFalse(R.already_done({'pid': 5, 'status': 'done'}, 6))
        self.assertFalse(R.already_done({}, 5))
        ok = R.summary_line(5, [('reload', {'ok': True}), ('save', {'ok': True})], {'B'})
        self.assertTrue(ok.startswith('TD recovered: pid 5'))
        bad = R.summary_line(5, [('reload', {'ok': False})], set())
        self.assertTrue(bad.startswith('TD recovery incomplete'))

    def test_lane_apply(self):
        d = LN.apply({}, 'add', 'BK_dmx_out', 'lane 2', '2026-10-26T16:00:00')
        self.assertEqual(d, {'BK_dmx_out': {'agent': 'lane 2', 'time': '2026-10-26T16:00:00'}})
        d = LN.apply(d, 'add', '/project1/lab/X', 'l3', 't')
        self.assertEqual(sorted(LN.apply(d, 'remove', 'X')), ['BK_dmx_out'])
        self.assertEqual(LN.apply(d, 'remove', '/project1/lab/BK_dmx_out'), {'/project1/lab/X': {'agent': 'l3', 'time': 't'}})

    def test_lane_file_roundtrip(self):
        import tempfile
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'logs', 'active_lanes.json')
        LN.update('add', 'A', 'me', path=p)
        LN.update('add', 'B', 'you', path=p)
        self.assertEqual(sorted(LN.update('list', path=p)), ['A', 'B'])
        LN.update('remove', 'A', path=p)
        self.assertEqual(sorted(LN.update('list', path=p)), ['B'])
