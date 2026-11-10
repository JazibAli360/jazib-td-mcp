"""Offline tests for td/crashdb.py (crash fingerprints + td_crash_report helper). stdlib only, no TouchDesigner.

Run from jazib-td-mcp/:  python3 -I -m unittest discover -s test -p 'test_*.py'
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TD_DIR = os.path.join(REPO, 'td')
FIX = os.path.join(HERE, 'fixtures', 'crash')
PATTERNS = os.path.join(REPO, 'logs', 'crash_patterns.json')


def load_crashdb():
    p = os.path.join(TD_DIR, 'crashdb.py')
    m = types.ModuleType('crashdb_under_test')
    m.__file__ = p
    with open(p, encoding='utf-8') as f:
        exec(compile(f.read(), p, 'exec'), m.__dict__)  # the way handlers loads it
    return m


C = load_crashdb()
PATS, PERR = C.load_patterns(PATTERNS)


def ids(matches, blocked=None):
    return sorted(m['id'] for m in matches if blocked is None or m['blocked'] == blocked)


class Features(unittest.TestCase):
    def test_ast_tokens(self):
        f, ok = C.features("t = c.create(textTOP, 'm')\nt.par.fontsizex = 24\nt.cook(force=True)\n"
                           "a = t.numpyArray(delayed=False)\nproject.cookRate = 30\nn.par['font'] = 'X'\n"
                           "setattr(project, 'realTime', False)\nq.par.text.val = 'hi'\nx, y.par.resolutionw = 1, 2")
        self.assertTrue(ok)
        for t in ('call:create', 'assign:par.fontsizex', 'kw:cook.force', 'call:numpyArray', 'assign:cookRate',
                  'assign:par.font', 'assign:realTime', 'assign:par.text', 'assign:par.resolutionw'):
            self.assertIn(t, f)
        self.assertNotIn('kw:numpyArray.delayed', f)   # delayed=False is falsy: no kw token
        self.assertNotIn('kw:cook.force', C.features('t.cook(force=False)')[0])

    def test_comparisons_and_reads_are_not_assignments(self):
        f, _ = C.features("if project.cookRate == 60:\n    r = t.par.resolutionw.eval()")
        self.assertNotIn('assign:cookRate', f)
        self.assertFalse(any(x.startswith('assign:par.') for x in f))

    def test_regex_fallback_on_syntax_error(self):
        f, ok = C.features("t.par.fontsizex = 24; t.numpyArray(\nproject.cookRate = 30\nif")
        self.assertFalse(ok)
        for t in ('assign:par.fontsizex', 'call:numpyArray', 'assign:cookRate'):
            self.assertIn(t, f)

    def test_comments_do_not_match_re_terms(self):
        p = {'id': 'x', 'matcher': {'any': ['re:cookRate']}, 'action': 'refuse'}
        self.assertEqual(C.check('# cookRate = 30 never\nx = 1', [p]), [])
        self.assertEqual(ids(C.check('s = "cookRate"', [p])), ['x'])


class SeedFile(unittest.TestCase):
    def test_loads_and_validates(self):
        self.assertIsNone(PERR)
        self.assertEqual([p['learnings'] for p in PATS], ['T-64', 'T-70', 'T-74', 'T-76'])
        for p in PATS:
            self.assertEqual(C.validate_pattern(p), [], p['id'])
            self.assertTrue(p['stack']['top'] and p['stack']['signals'] and p['reports'])
        with open(PATTERNS, 'rb') as f:
            f.read().decode('ascii')

    def test_t74_readback(self):
        code = "t = c.create(textTOP); a = t.numpyArray()"
        self.assertEqual(ids(C.check(code, PATS), True), ['T-74-readback-after-change'])
        self.assertEqual(C.check("a = op('x').numpyArray()", PATS), [])
        self.assertEqual(ids(C.check("t.par.fontsizex = 24; t.numpyArray(delayed=False)", PATS), True),
                         ['T-74-readback-after-change'])
        self.assertEqual(ids(C.check("t.cook(force=True)\nt.numpyArray()", PATS), True), ['T-74-readback-after-change'])
        m = C.check(code, PATS, frames=2)
        self.assertEqual((ids(m, False), m[0]['allowed_by']), (['T-74-readback-after-change'], 'frames>=2'))
        m = C.check("t.par.fontsizex=2; t.numpyArray() # allow-readback", PATS)
        self.assertEqual((ids(m, False), m[0]['allowed_by']), (['T-74-readback-after-change'], 'optout'))

    def test_t76_text_size(self):
        code = "t=c.create(textTOP,'m'); t.par.font='Noto Nastaliq Urdu'; t.evalTextSize('a')"
        self.assertEqual(ids(C.check(code, PATS), True), ['T-76-textsize-after-create'])
        self.assertEqual(C.check("op('/a/t').evalTextSize('a')", PATS), [])

    def test_t64_cookrate(self):
        self.assertEqual(ids(C.check('project.cookRate = 30', PATS), True), ['T-64-cookrate-live'])
        self.assertEqual(ids(C.check('project.cookRate = 30', PATS, frames=50), True), ['T-64-cookrate-live'])
        self.assertEqual(C.check('r = project.cookRate', PATS), [])
        self.assertEqual(ids(C.check('project.cookRate = 30  # allow-cookrate', PATS), False), ['T-64-cookrate-live'])

    def test_t70_destroy_only_with_open_windows(self):
        code = "op('/project1/lab/X/controls').destroy()"
        self.assertEqual(C.check(code, PATS, context={'open_windows': []}), [])
        m = C.check(code, PATS, context={'open_windows': ['/project1/lab/X/controls_window']})
        self.assertEqual(ids(m, True), ['T-70-destroy-shown-panel'])
        self.assertEqual(ids(C.check("safe_destroy(op('/p/x'))", PATS, context={'open_windows': ['/w']})), [])
        m = C.check(code, PATS)  # no context: matched, condition unknown
        self.assertEqual(m[0]['unknown'], ['open_windows'])
        self.assertEqual(ids(C.check(code + '  # allow-destroy', PATS, context={'open_windows': ['/w']}), True), [])

    def test_texts(self):
        m = C.check("t = c.create(textTOP); a = t.numpyArray()", PATS)
        txt = C.refusal_text(m)
        self.assertIn('T-74', txt)
        self.assertIn('frames >= 2', txt)
        self.assertIn('# allow-readback', txt)
        n = C.notes_for(C.check("t = c.create(textTOP); a = t.numpyArray()", PATS, frames=3))
        self.assertTrue(n and 'allowed by frames>=2' in n[0])

    def test_warn_action_and_proposed_skipped(self):
        p = {'id': 'w', 'matcher': {'all': ['call:sleep']}, 'action': 'warn'}
        m = C.check('time.sleep(1)', [p])
        self.assertEqual((ids(m), m[0]['blocked']), (['w'], False))
        self.assertEqual(C.check('time.sleep(1)', [dict(p, status='proposed', action='refuse')]), [])


class LoadPatterns(unittest.TestCase):
    def test_missing_and_broken_fall_back(self):
        d = tempfile.mkdtemp()
        try:
            pats, err = C.load_patterns(os.path.join(d, 'nope.json'))
            self.assertTrue(err)
            self.assertEqual(ids(C.check("t = c.create(textTOP); a = t.numpyArray()", pats), True), ['T-74-fallback'])
            self.assertEqual(ids(C.check("t = c.create(textTOP); t.evalTextSize('a')", pats), True), ['T-76-fallback'])
            bad = os.path.join(d, 'bad.json')
            with open(bad, 'w') as f:
                json.dump({'patterns': [{'id': 'x', 'matcher': {'any': ['oops']}}]}, f)
            pats, err = C.load_patterns(bad)
            self.assertIn('invalid', err)
        finally:
            shutil.rmtree(d)

    def test_validate(self):
        self.assertIn('matcher has no all/any terms', C.validate_pattern(
            {'id': 'a', 'title': 't', 'description': 'd', 'rule': 'r', 'matcher': {}}))
        self.assertTrue(any('bad regex' in x for x in C.validate_pattern(
            {'id': 'a', 'title': 't', 'description': 'd', 'rule': 'r', 'matcher': {'any': ['re:(']}})))
        self.assertTrue(any('optout' in x for x in C.validate_pattern(
            {'id': 'a', 'title': 't', 'description': 'd', 'rule': 'r', 'matcher': {'any': ['call:x']}, 'optout': 'x'})))


def read(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f:
        return f.read()


class Ips(unittest.TestCase):
    def test_parse_gx(self):
        s = C.parse_ips(read('TouchDesigner-2026-10-26-150020.ips'), 'TouchDesigner-2026-10-26-150020.ips')
        self.assertEqual(s['pid'], 4242)
        self.assertEqual(s['exception']['signal'], 'SIGSEGV')
        self.assertEqual(s['chain'][:5], ['libGX', 'libC_TOP', 'Python', 'libPY', 'libOP'])
        self.assertEqual(s['faulting_thread']['index'], 2)
        self.assertFalse(s['faulting_thread']['main'])
        self.assertTrue(s['python_in_stack'])
        self.assertIn('builtin_exec', s['symbols'])
        self.assertAlmostEqual(s['epoch'], 1793008820.5, places=3)   # 15:00:20.5 +0500 = 10:00:20.5Z
        self.assertEqual(s['app_version'], '2025.31550')
        by = [p['id'] for p in PATS if C.stack_matches(s, p)]
        self.assertEqual(by, ['T-74-readback-after-change', 'T-76-textsize-after-create'])

    def test_parse_ui_and_unknown(self):
        s = C.parse_ips(read('TouchDesigner-2026-10-26-131216.ips'))
        self.assertEqual(s['chain'], ['libUT', 'libUI', 'libOPUI', 'libUT'])
        self.assertEqual([p['id'] for p in PATS if C.stack_matches(s, p)], ['T-64-cookrate-live', 'T-70-destroy-shown-panel'])
        u = C.parse_ips(read('TouchDesigner-2026-10-27-090000.ips'))
        self.assertEqual([p['id'] for p in PATS if C.stack_matches(u, p)], [])

    def test_ips_epoch(self):
        self.assertAlmostEqual(C.ips_epoch('2026-10-26 15:53:36.2852 +0500'), 1793012016.2852, places=3)
        self.assertIsNone(C.ips_epoch('nope'))

    def test_newest(self):
        d = tempfile.mkdtemp()
        try:
            for i, n in enumerate(('TouchDesigner-a.ips', 'TouchDesigner-b.ips', 'Other-c.ips')):
                p = os.path.join(d, n)
                open(p, 'w').close()
                os.utime(p, (1000 + i, 1000 + i))
            self.assertEqual(os.path.basename(C.newest_ips(d)), 'TouchDesigner-b.ips')
            self.assertIsNone(C.newest_ips(os.path.join(d, 'none')))
        finally:
            shutil.rmtree(d)


class FaultLog(unittest.TestCase):
    def test_pick_session_by_pid(self):
        r = C.parse_fh_log(read('td_faulthandler.log'), pid=4242)
        self.assertEqual(r['session']['project'], 'JazibTD_home.97.toe')
        self.assertTrue(r['crashed'])
        self.assertEqual(r['fatal'], ['Fatal Python error: Segmentation fault'])
        self.assertEqual(len(r['threads']), 2)
        cur = [t for t in r['threads'] if t['current']][0]
        self.assertEqual(cur['frames'][0], {'file': '<jazib_mcp exec>', 'line': 3, 'func': '<module>'})
        self.assertEqual(r['exec_frames'][0]['line'], 3)
        self.assertEqual(r['sessions'], 3)

    def test_no_session_for_pid_and_newest(self):
        r = C.parse_fh_log(read('td_faulthandler.log'), pid=7890)
        self.assertIsNone(r['session'])
        self.assertIn('7890', r['note'])
        r = C.parse_fh_log(read('td_faulthandler.log'))
        self.assertEqual(r['session']['pid'], '9999')
        self.assertFalse(r['crashed'])
        self.assertIsNone(C.parse_fh_log('hello\n')['session'])

    def test_header_round_trip(self):
        sys.path.insert(0, HERE)
        try:
            import test_handlers  # noqa: F401 -- installs the stub td and imports handlers
            import handlers
        finally:
            sys.path.remove(HERE)
        line = handlers.fault_header(4242, '2025.31550', 'My Show.toe', '2026-10-26T14:40:05+0500', '3.11.1')
        r = C.parse_fh_log(line + 'Fatal Python error: Bus error\n', pid=4242)
        self.assertEqual(r['session']['project'], 'My_Show.toe')
        self.assertTrue(r['crashed'])


class InFlight(unittest.TestCase):
    CRASH = 1793008820.5  # fixture .ips captureTime

    def test_in_flight_and_recent(self):
        r = C.exec_in_flight(read('exec.log').splitlines(), self.CRASH, 120)
        self.assertEqual([x['time'] for x in r['in_flight']], ['2026-10-26T10:00:18.000Z', '2026-10-26T10:00:19.500Z'])
        self.assertEqual(r['in_flight'][0]['agent'], 'lane1')
        self.assertIn('disconnected', r['in_flight'][0]['ended']['error'])
        self.assertNotIn('ended', r['in_flight'][1])          # never ended
        self.assertEqual([x['code'] for x in r['recent']], ['x = 1', "op('/project1/lab/LK_room').par.Speed = 2"])
        self.assertEqual(r['basis'], 'crash report time')
        self.assertEqual(r['later_dead'], 0)
        self.assertEqual(len(r['codes']), 2)

    def test_hung_report_written_late(self):
        late = self.CRASH + 3600  # report written 1 h after TD's last reply (T-76: hung on the crash dialog)
        r = C.exec_in_flight(read('exec.log').splitlines(), late, 120)
        self.assertEqual(r['last_reply'], '2026-10-26T10:00:19Z')
        self.assertIn('last td_exec reply', r['basis'])
        self.assertEqual(len(r['in_flight']), 2)
        self.assertEqual(r['later_dead'], 1)  # the 10:30 exec that timed out against the hung TD

    def test_launch_bound_and_empty(self):
        r = C.exec_in_flight(read('exec.log').splitlines(), self.CRASH, 7200, launch_epoch=self.CRASH - 60)
        self.assertNotIn('2026-10-26T09:00:00.000Z', [x['time'] for x in r['in_flight']])
        r = C.exec_in_flight(read('exec.log').splitlines(), self.CRASH, 7200)
        self.assertIn('2026-10-26T09:00:00.000Z', [x['time'] for x in r['in_flight']])
        self.assertEqual(C.exec_in_flight([], self.CRASH)['in_flight'], [])


class Report(unittest.TestCase):
    def test_known_pattern(self):
        r = C.report(os.path.join(FIX, 'TouchDesigner-2026-10-26-150020.ips'), FIX, os.path.join(FIX, 'exec.log'),
                     os.path.join(FIX, 'td_faulthandler.log'), PATTERNS)
        self.assertEqual(r['known']['both'], ['T-74-readback-after-change'])
        self.assertTrue(r['verdict'].startswith('known pattern T-74'))
        self.assertIsNone(r['proposal'])
        self.assertTrue(r['faulthandler']['crashed'])
        self.assertEqual(len(r['exec']['in_flight']), 2)

    def test_unknown_gets_proposal(self):
        d = tempfile.mkdtemp()
        try:
            log = os.path.join(d, 'exec.log')
            with open(log, 'w') as f:
                for ph, t, extra in (('start', '2026-10-27T03:59:58.000Z', {}),):
                    f.write(json.dumps(dict({'time': t, 'pid': 7, 'phase': ph,
                                             'code': "s = op('/project1/geo1/sop')\ns.par.rows = 9000\n"
                                                     "pts = s.points\nprint(len(pts))"}, **extra)) + '\n')
            r = C.report(os.path.join(FIX, 'TouchDesigner-2026-10-27-090000.ips'), FIX, log, None, PATTERNS)
            self.assertEqual(r['known']['by_stack'], [])
            self.assertIn('unknown crash', r['verdict'])
            p = r['proposal']
            self.assertEqual(p['status'], 'proposed')
            self.assertEqual(p['stack']['top'], ['libC_SOP', 'libOP', 'Python'])
            self.assertEqual(p['stack']['signals'], ['SIGSEGV'])
            self.assertIn('assign:par.rows', p['matcher']['any'])
            self.assertNotIn('call:op', p['matcher']['any'])
            self.assertNotIn('assign:rows', p['matcher']['any'])
            self.assertEqual(C.validate_pattern(p, proposed=True), [])
            self.assertEqual(p['reports'], ['TouchDesigner-2026-10-27-090000.ips'])
            # a proposal never guards td_exec until the main session activates it
            self.assertEqual(C.check("x.par.rows = 1", [p]), [])
        finally:
            shutil.rmtree(d)

    def test_stack_only(self):
        r = C.report(os.path.join(FIX, 'TouchDesigner-2026-10-26-131216.ips'), FIX, os.path.join(FIX, 'exec.log'),
                     os.path.join(FIX, 'td_faulthandler.log'), PATTERNS)
        self.assertEqual(r['known']['by_stack'], ['T-64-cookrate-live', 'T-70-destroy-shown-panel'])
        self.assertIn('stack looks like', r['verdict'])
        self.assertIsNone(r['faulthandler']['session'])
        self.assertIsNotNone(r['proposal'])

    def test_no_reports(self):
        d = tempfile.mkdtemp()
        try:
            r = C.report(None, d, None, None, PATTERNS)
            self.assertEqual(r['verdict'], 'no crash report found')
            self.assertIsNone(r['proposal'])
        finally:
            shutil.rmtree(d)

    def test_cli(self):
        out = subprocess.run([sys.executable, '-I', os.path.join(TD_DIR, 'crashdb.py'), 'report', '--ips',
                              os.path.join(FIX, 'TouchDesigner-2026-10-26-150020.ips'), '--exec-log',
                              os.path.join(FIX, 'exec.log'), '--fh-log', os.path.join(FIX, 'td_faulthandler.log'),
                              '--patterns', PATTERNS], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)['known']['both'], ['T-74-readback-after-change'])
        out = subprocess.run([sys.executable, '-I', os.path.join(TD_DIR, 'crashdb.py'), 'check', '--patterns',
                              PATTERNS, '-'], input='project.cookRate = 30', capture_output=True, text=True, timeout=60)
        self.assertEqual([m['id'] for m in json.loads(out.stdout)['matches']], ['T-64-cookrate-live'])


if __name__ == '__main__':
    unittest.main()
