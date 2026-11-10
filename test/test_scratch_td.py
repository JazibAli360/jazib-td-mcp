"""Offline tests for tools/scratch_td.py (T-83; stdlib only, no TouchDesigner)."""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
import scratch_td as S  # noqa: E402


class SideWatch(unittest.TestCase):
    def test_watch_due(self):
        run = {'state': 'running', 'pid': 1}
        self.assertTrue(S.watch_due(run, False, [], 100))
        self.assertFalse(S.watch_due(run, True, [], 100))            # alive
        self.assertFalse(S.watch_due(None, False, [], 100))           # stopped (state removed)
        self.assertFalse(S.watch_due({'state': 'launching', 'pid': 1}, False, [], 100))
        self.assertFalse(S.watch_due(run, False, [90, 91, 92, 93], 100))  # crash loop: gave up
        self.assertTrue(S.watch_due(run, False, [0, 1, 2, 3], 2000))      # old relaunches age out

    def test_hang_due(self):
        self.assertFalse(S.hang_due(None, 1000, 0.0))                     # answering
        self.assertFalse(S.hang_due(900, 1000, 0.0))                      # failing < HANG_S
        self.assertTrue(S.hang_due(600, 1000, 0.0))                       # 400 s, idle CPU
        self.assertFalse(S.hang_due(600, 1000, 85.0))                     # busy (long legit work)
        self.assertFalse(S.hang_due(600, 1000, None))                     # CPU unknown: don't kill
        self.assertFalse(S.hang_due(600, 1000, 13.0))                     # 400 s at 13 %: not yet
        self.assertTrue(S.hang_due(300, 1000, 13.0))                      # 700 s at 13 %: tier 2
        self.assertFalse(S.hang_due(300, 1000, 60.0))                     # 700 s at 60 %: busy, keep


class DatText(unittest.TestCase):
    def test_round_trip_and_header(self):
        b = S.encode_dat_text('print(1)\n')
        self.assertEqual(b[:3], b'2\n*')
        self.assertEqual(struct.unpack('>IIIIII', b[3:27]), (1, 1, 1, 1, 2, 9))
        self.assertEqual(S.decode_dat_text(b), 'print(1)\n')
        with self.assertRaises(UnicodeEncodeError):
            S.encode_dat_text('é')

    def test_td_sample_identical_when_present(self):
        # toeexpand output of TD's own PythonExamples.toe is not shipped; the header layout above is what it uses
        # (2\n*, 1,1,1,1,2, len). Checked live 26 Oct against execute1.text: identical bytes.
        self.assertRaises(ValueError, S.decode_dat_text, b'nope')


class Boot(unittest.TestCase):
    def test_boot_text_ascii_compiles_and_sets_env(self):
        t = S.boot_text(9336, '/x/td', '/x/logs/scratch')
        t.encode('ascii')
        compile(t, 'boot', 'exec')
        for k in ("'JTD_SCRATCH': '1'", "'JTD_AUTOSAVE_MIN': '0'", "'JTD_INSTALL_SAVE_TOX': '0'", 'PORT = 9336',
                  "TD_DIR = '/x/td'", 'def onStart', 'def onFrameStart', 'install.py'):
            self.assertIn(k, t)

    def test_boot_runs_once_and_logs_errors(self):
        import tempfile
        d = tempfile.mkdtemp()
        env = dict(os.environ)
        try:
            os.environ.pop('JTD_SCRATCH_BOOTED', None)
            ns = {}
            exec(compile(S.boot_text(9399, d, d), 'boot', 'exec'), ns)  # no install.py in d -> error logged
            ns['onStart']()
            ns['onFrameStart'](1)
            with open(os.path.join(d, 'boot.log')) as f:
                log = f.read()
            self.assertEqual(log.count(' port 9399: '), 1, 'boot runs once')
            self.assertIn('Traceback', log)
            self.assertEqual(os.environ.get('JTD_BRIDGE_PORT'), '9399')
        finally:
            os.environ.clear()
            os.environ.update(env)

    def test_parm_starts_and_frame_fallback(self):
        self.assertIn('start 0 on', S.BOOT_PARM)
        self.assertIn('framestart 0 on', S.BOOT_PARM)
        self.assertTrue(S.BOOT_N.startswith('DAT:execute\n'))


class Pids(unittest.TestCase):
    def test_new_pids(self):
        self.assertEqual(S.new_pids([1, 2], [2, 3, 1, 4]), [3, 4])

    def test_stop_targets_never_main(self):
        self.assertEqual(S.stop_targets(None, [1], 1)[0], None)
        self.assertEqual(S.stop_targets({'pid': 7, 'port': 9336}, [5, 7], 5), (7, 'scratch pid 7'))
        self.assertIsNone(S.stop_targets({'pid': 5, 'port': 9336}, [5], 5)[0], 'main heartbeat pid')
        self.assertIsNone(S.stop_targets({'pid': 7, 'port': 9335}, [7], 5)[0], 'main port')
        self.assertIsNone(S.stop_targets({'pid': 7, 'port': 9336}, [5], 5)[0], 'not running')

    def test_default_port_not_main(self):
        self.assertNotEqual(S.DEFAULT_PORT, S.MAIN_PORT)


class BuildTDs(unittest.TestCase):
    """T-120: build TDs b2 / b3 keep their project, autosave, and say who they are."""
    def test_instances_ports_and_files(self):
        self.assertEqual({n: v[0] for n, v in S.INSTANCES.items()}, {'scratch': S.DEFAULT_PORT, 'b2': 9337, 'b3': 9338, 'b4': 9339, 'b5': 9340})
        self.assertEqual(S.state_file('scratch'), S.SCRATCH_FILE)
        self.assertTrue(S.state_file('b2').endswith('scratch_td_b2.json'))
        i = S.inst('b3')
        self.assertTrue(i['toe'].endswith('/projects/build3/Build3.toe') and i['keep'])
        self.assertTrue(i['logs'].endswith('/logs/b3'))
        self.assertFalse(S.inst('scratch')['keep'])
        with self.assertRaises(SystemExit):
            S.inst('main')

    def test_boot_env(self):
        b = S.boot_env(9337, '/x/td', 'b2')
        self.assertEqual((b['JTD_INSTANCE'], b['JTD_AUTOSAVE_MIN'], b['JTD_INSTALL_SAVE_TOX']), ('b2', '5', '0'))
        self.assertNotIn('JTD_SCRATCH', b)
        sc = S.boot_env(9336, '/x/td')
        self.assertEqual((sc['JTD_SCRATCH'], sc['JTD_AUTOSAVE_MIN']), ('1', '0'))
        t = S.boot_text(9337, '/x/td', '/x/logs/b2', 'b2')
        compile(t, 'boot', 'exec')
        self.assertIn("'JTD_INSTANCE': 'b2'", t)
        self.assertNotIn("'JTD_SCRATCH'", t)

    def test_newest_toe(self):
        ls = ['Build2.toe', 'Build2.3.toe', 'Build2.12.toe', 'CrashAutoSave.Build2.20.toe', 'Build3.40.toe', 'x.toe']
        self.assertEqual(S.newest_toe(ls, 'Build2.toe'), 'Build2.12.toe')
        self.assertEqual(S.newest_toe(['Build2.toe'], 'Build2.toe'), 'Build2.toe')
        self.assertIsNone(S.newest_toe(['Build3.toe'], 'Build2.toe'))

    def test_launch_blocked(self):
        now = 1000.0
        st = {'b2': {'state': 'launching', 'time': 990.0}, 'b3': None, 'scratch': {'state': 'running', 'time': 0}}
        self.assertEqual(S.launch_blocked(st, now, 'b3'), 'b2')
        self.assertIsNone(S.launch_blocked(st, now, 'b2'), 'its own state never blocks')
        self.assertIsNone(S.launch_blocked(st, now + 500, 'b3'), 'grace over')

    def test_identity(self):
        self.assertTrue(S.identity_ok('b2', {'instance': 'b2'}))
        self.assertFalse(S.identity_ok('b2', {'instance': 'b3'}))
        self.assertFalse(S.identity_ok('b2', {'scratch': False}))
        self.assertTrue(S.identity_ok('scratch', {'scratch': True}))
        self.assertFalse(S.identity_ok('scratch', {'scratch': False, 'instance': 'main'}))


if __name__ == '__main__':
    unittest.main()


class SleptTest(unittest.TestCase):  # T-219
    def test_slept(self):
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools'))
        from td_watchdog import slept_s
        self.assertEqual(slept_s(None, None, 100.0, 5.0), 0.0)
        self.assertEqual(slept_s(100.0, 5.0, 110.0, 15.0), 0.0)      # awake: both clocks ran 10 s
        self.assertEqual(slept_s(100.0, 5.0, 700.0, 15.0), 590.0)    # slept ~590 s: monotonic stood still
        self.assertEqual(slept_s(100.0, 5.0, 99.0, 15.0), 0.0)       # wall clock set back: never negative
