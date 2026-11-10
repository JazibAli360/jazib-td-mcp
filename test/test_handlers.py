"""Offline tests for td/handlers.py (stdlib only; no TouchDesigner).

Run from jazib-td-mcp/:  python3 -I -m unittest discover -s test -p 'test_*.py'
A stub `td` module is injected into sys.modules before handlers is imported.
"""
import enum
import json
import os
import stat
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TD_DIR = os.path.join(os.path.dirname(HERE), 'td')


# ---------------------------------------------------------------- stub td

class ParMode(enum.Enum):
    CONSTANT = 0
    EXPRESSION = 1
    EXPORT = 2
    BIND = 3


class FakePar(object):
    def __init__(self, owner, name, val=0, default=0, menu=None, pulse=False, page='Common'):
        self.owner, self.name, self.val, self.default = owner, name, val, default
        self.label = name.title()
        self.page = types.SimpleNamespace(name=page)
        self.style = 'Menu' if menu else ('Pulse' if pulse else 'Float')
        self.mode = ParMode.CONSTANT
        self.expr = ''
        self.bindExpr = ''
        self.isMenu = bool(menu)
        self.isPulse = pulse
        self.isNumber = not menu and not pulse
        self.menuNames = [n for n, _ in menu] if menu else []
        self.menuLabels = [l for _, l in menu] if menu else []
        self.menuIndex = 0
        self.readOnly = False
        self.isCustom = False
        self.min, self.max = 0, 1
        self.pulsed = 0

    def eval(self):
        return self.val

    def pulse(self):
        self.pulsed += 1


class FakeParCollection(object):
    def __init__(self, pars):
        self._d = {p.name: p for p in pars}

    def __getitem__(self, k):
        return self._d.get(k)


class FakeConnector(object):
    def __init__(self, owner, index, is_input):
        self.owner, self.index, self.is_input = owner, index, is_input
        self.connections = []

    def connect(self, target):
        if isinstance(target, FakeConnector):
            src, dst = (self, target) if not self.is_input else (target, self)
        else:  # an OP: like TD, output.connect(op) lands on its input 0
            if self.is_input:
                src, dst = target.outputConnectors[0], self
            else:
                src, dst = self, target.inputConnectors[0]
        dst.connections = [src]
        src.connections.append(dst)

    def disconnect(self):
        self.connections = []


class OP(object):
    def __init__(self, path, optype='noiseTOP', family='TOP', n_in=1, pars=()):
        self.path = path
        self.name = path.rsplit('/', 1)[-1]
        self.OPType = optype
        self.family = family
        self.inputConnectors = [FakeConnector(self, i, True) for i in range(n_in)]
        self.outputConnectors = [FakeConnector(self, 0, False)]
        self._pars = [FakePar(self, **p) for p in pars]
        self.par = FakeParCollection(self._pars)
        self.isCOMP = False
        self.children = []

    def pars(self, *pat):
        return list(self._pars)

    def errors(self):
        return ''

    def warnings(self):
        return ''


OPS = {}


def fake_op(path):
    return OPS.get(path)


def install_stub():
    td = types.ModuleType('td')
    td.OP = OP
    td.ParMode = ParMode
    td.op = fake_op
    td.run = lambda *a, **k: None
    td.app = types.SimpleNamespace(version='2025', build='31550', osName='macOS')
    td.project = types.SimpleNamespace(name='t.toe', folder='/tmp', cookRate=60, realTime=True)
    td.absTime = types.SimpleNamespace(frame=10, seconds=1.0)
    td.noiseTOP = type('noiseTOP', (OP,), {})
    td.__all__ = ['OP', 'ParMode', 'op', 'run', 'app', 'project', 'absTime', 'noiseTOP']
    sys.modules['td'] = td
    return td


install_stub()
sys.dont_write_bytecode = True  # keep td/ free of __pycache__
sys.path.insert(0, TD_DIR)
import handlers  # noqa: E402
handlers.SAFETY_DIR = TD_DIR  # td/safety.py beside this handlers.py (the pre-risk check runs on every exec)


def collect():
    out = []
    return out, (lambda t: out.append(json.loads(t)))


# ---------------------------------------------------------------- tests

class ToJson(unittest.TestCase):
    def test_scalars_and_containers(self):
        self.assertEqual(handlers.to_json([1, 2.5, 'a', True, None, (3, 4)]), [1, 2.5, 'a', True, None, [3, 4]])
        self.assertEqual(handlers.to_json({1: 'x'}), {'1': 'x'})

    def test_op_becomes_path(self):
        self.assertEqual(handlers.to_json(OP('/project1/noise1')), '/project1/noise1')
        self.assertEqual(handlers.to_json([OP('/a')]), ['/a'])

    def test_other_becomes_repr_and_nan_safe(self):
        class X(object):
            def __repr__(self):
                return '<X>'
        self.assertEqual(handlers.to_json(X()), '<X>')
        self.assertEqual(handlers.to_json(float('nan')), 'nan')
        self.assertEqual(handlers.to_json(float('inf')), 'inf')
        json.loads(handlers.dumps({'v': float('nan')}))  # valid JSON for Node

    def test_build_string(self):
        self.assertEqual(handlers.td_build_string('2025', '31550'), '2025.31550')
        self.assertEqual(handlers.td_build_string('2025', '2025.31550'), '2025.31550')


class Names(unittest.TestCase):
    def test_custom_par_rule(self):
        for ok in ('Speed', 'A', 'Level2', 'Handlersfile'):
            self.assertTrue(handlers.valid_custom_name(ok), ok)
        for bad in ('speed', 'SpeedX', 'Speed_x', '2speed', '', 'Spe ed', None, 'Sp\u00e9ed'):
            self.assertFalse(handlers.valid_custom_name(bad), bad)

    def test_custom_specs_checked_before_change(self):
        with self.assertRaises(ValueError) as cm:
            handlers.check_custom_specs([{'name': 'Good', 'style': 'Float'}, {'name': 'bad', 'style': 'Float'},
                                         {'name': 'Menu', 'style': 'Menu'}, {'name': 'X', 'style': 'Nope'}])
        msg = str(cm.exception)
        self.assertIn("'bad'", msg)
        self.assertIn('menuNames', msg)
        self.assertIn('Nope', msg)
        handlers.check_custom_specs([{'name': 'Speed', 'style': 'Float'}])

    def test_op_names(self):
        self.assertTrue(handlers.valid_op_name('noise1'))
        self.assertFalse(handlers.valid_op_name('noise 1'))
        self.assertFalse(handlers.valid_op_name('a/b'))


class Undo(unittest.TestCase):
    def test_block_wraps_and_ends_on_error(self):
        calls = []

        class U(object):
            def startBlock(self, name):
                calls.append(('start', name))

            def endBlock(self):
                calls.append(('end',))

        class UI(object):
            undo = U()
        handlers.ui = UI()
        try:
            self.assertEqual(handlers.undo_block('create', lambda: 5), 5)
            with self.assertRaises(ValueError):
                handlers.undo_block('delete', lambda: (_ for _ in ()).throw(ValueError('x')))
        finally:
            del handlers.ui
        self.assertEqual(calls, [('start', 'jazib-td: create'), ('end',), ('start', 'jazib-td: delete'), ('end',)])

    def test_no_ui_just_runs(self):
        self.assertEqual(handlers.undo_block('create', lambda: 7), 7)

    def test_mutating_set(self):
        for c in ('create', 'delete', 'set_pars', 'exec', 'layout'):
            self.assertIn(c, handlers.MUTATING)
        for c in ('info', 'list', 'errors', 'housekeeping', 'screenshot', 'status'):
            self.assertNotIn(c, handlers.MUTATING)


class Housekeeping(unittest.TestCase):
    def test_default_named(self):
        self.assertTrue(handlers.default_named('noise1', 'noiseTOP'))
        self.assertTrue(handlers.default_named('base12', 'baseCOMP'))
        self.assertFalse(handlers.default_named('noise_bg', 'noiseTOP'))
        self.assertFalse(handlers.default_named('null_out', 'nullTOP'))
        self.assertFalse(handlers.default_named('level1', 'noiseTOP'))
        self.assertFalse(handlers.default_named('x1', ''))

    def test_debug_names(self):
        for n in ('_probe_t46', 'tmp_a', 'test_b', 'scratch2'):
            self.assertTrue(handlers._DEBUG_NAME.match(n), n)
        for n in ('looks', 'mixer', 'contest'):
            self.assertFalse(handlers._DEBUG_NAME.match(n), n)


class Menus(unittest.TestCase):
    NAMES = ['rgba8fixed', 'rgba16float', 'rgba32float']
    LABELS = ['8-bit fixed (RGBA)', '16-bit float (RGBA)', '32-bit float (RGBA)']

    def test_name_and_label(self):
        self.assertEqual(handlers.match_menu(self.NAMES, self.LABELS, 'RGBA16Float'), ('rgba16float', None))
        self.assertEqual(handlers.match_menu(self.NAMES, self.LABELS, '32-bit float (rgba)'), ('rgba32float', None))

    def test_loose(self):
        self.assertEqual(handlers.match_menu(self.NAMES, self.LABELS, '8-bit fixed')[0], 'rgba8fixed')

    def test_miss_warns(self):
        hit, warn = handlers.match_menu(self.NAMES, self.LABELS, 'half')
        self.assertIsNone(hit)
        self.assertIn('half', warn)
        acts, warns = handlers.plan_par_set('format', {'menu': 'half'}, is_menu=True,
                                            menu_names=self.NAMES, menu_labels=self.LABELS)
        self.assertEqual(acts, [])
        self.assertEqual(len(warns), 1)


class ParsPlan(unittest.TestCase):
    def test_scalar_dict_pulse_mode(self):
        self.assertEqual(handlers.plan_par_set('tx', 3)[0], [('val', 3)])
        self.assertEqual(handlers.plan_par_set('tx', {'expr': 'absTime.seconds'})[0], [('expr', 'absTime.seconds')])
        self.assertEqual(handlers.plan_par_set('tx', {'bindExpr': 'x'})[0], [('bindExpr', 'x'), ('mode', 'BIND')])
        self.assertEqual(handlers.plan_par_set('p', True, is_pulse=True)[0], [('pulse', None)])
        self.assertEqual(len(handlers.plan_par_set('p', False, is_pulse=True)[1]), 1)
        with self.assertRaises(ValueError):
            handlers.plan_par_set('tx', {'mode': 'weird'})
        with self.assertRaises(ValueError):
            handlers.plan_par_set('tx', {'value': 1})

    def test_menu_label_as_val(self):
        acts, _ = handlers.plan_par_set('f', '16-bit float (RGBA)', is_menu=True, menu_names=Menus.NAMES,
                                        menu_labels=Menus.LABELS)
        self.assertEqual(acts, [('val', 'rgba16float')])

    def test_differs(self):
        self.assertFalse(handlers.par_differs(ParMode.CONSTANT, 1.0, 1))
        self.assertTrue(handlers.par_differs(ParMode.CONSTANT, 1.5, 1))
        self.assertTrue(handlers.par_differs(ParMode.EXPRESSION, 1, 1))
        self.assertTrue(handlers.par_differs('ParMode.BIND', 'a', 'a'))
        self.assertFalse(handlers.par_differs(ParMode.CONSTANT, 'a', 'a'))

    def test_set_pars_validates_all_first(self):
        o = OP('/p/n', pars=[{'name': 'amp', 'val': 1, 'default': 1},
                             {'name': 'reset', 'pulse': True, 'val': False, 'default': False},
                             {'name': 'mono', 'menu': [('on', 'On'), ('off', 'Off')], 'val': 'on', 'default': 'on'}])
        OPS['/p/n'] = o
        with self.assertRaises(ValueError):
            handlers.cmd_set_pars('/p/n', {'amp': 5, 'nope': 1})
        self.assertEqual(o.par['amp'].val, 1)  # nothing changed
        r = handlers.cmd_set_pars('/p/n', {'amp': 5, 'reset': True, 'mono': {'menu': 'Off'}})
        self.assertEqual(sorted(r['set']), ['amp', 'mono', 'reset'])
        self.assertEqual((o.par['amp'].val, o.par['reset'].pulsed, o.par['mono'].val), (5, 1, 'off'))
        r = handlers.cmd_set_pars('/p/n', {'amp': {'expr': 'me.time.frame', 'mode': 'EXPRESSION'}})
        self.assertEqual(o.par['amp'].mode, ParMode.EXPRESSION)


class Connect(unittest.TestCase):
    def setUp(self):
        OPS.clear()
        OPS['/p/a'] = OP('/p/a')
        OPS['/p/b'] = OP('/p/b')
        OPS['/p/g'] = OP('/p/g', optype='glslTOP', n_in=3)

    def test_lands_on_requested_input(self):
        r = handlers.cmd_connect('/p/a', '/p/g', inIndex=2)
        self.assertEqual(r['inputs'], [None, None, '/p/a'])
        r = handlers.cmd_connect('/p/b', '/p/g', inIndex=0)
        self.assertEqual(r['inputs'], ['/p/b', None, '/p/a'])
        self.assertEqual(handlers.cmd_disconnect('/p/g', 2)['inputs'], ['/p/b', None, None])

    def test_glsl_out_of_range_message(self):
        with self.assertRaises(ValueError) as cm:
            handlers.cmd_connect('/p/a', '/p/g', inIndex=3)
        self.assertIn('3 input connector', str(cm.exception))
        self.assertIn('tops', str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            handlers.cmd_connect('/p/a', '/p/b', inIndex=1)
        self.assertNotIn('tops', str(cm.exception))

    def test_verification_catches_wrong_landing(self):
        g = OPS['/p/g']
        orig = FakeConnector.connect

        def always_input0(self_, target):  # simulate the TD behaviour LEARNINGS warns about
            g.inputConnectors[0].connections = [OPS['/p/a'].outputConnectors[0]]
        FakeConnector.connect = always_input0
        try:
            with self.assertRaises(RuntimeError) as cm:
                handlers.cmd_connect('/p/a', '/p/g', inIndex=1)
            self.assertIn('connect check failed', str(cm.exception))
        finally:
            FakeConnector.connect = orig

    def test_delete_refuses_own_comp(self):
        for p in ('/', '/jazib_mcp', '/jazib_mcp/ws'):
            with self.assertRaises(ValueError):
                handlers.cmd_delete([p])
        self.assertEqual(handlers.cmd_delete(['/nope'])['missing'], ['/nope'])


class Exec(unittest.TestCase):
    def test_last_expression_and_stdout(self):
        r = handlers.run_code("x = 2\nprint('hi')\nx * 21", {})
        self.assertEqual(r, {'stdout': 'hi\n', 'stderr': '', 'result': 42})

    def test_no_expression_and_stderr(self):
        r = handlers.run_code("import sys\nsys.stderr.write('e')\ny = 1", {})
        self.assertEqual((r['result'], r['stderr']), (None, 'e'))

    def test_non_json_result_is_repr_op_is_path(self):
        self.assertEqual(handlers.run_code('object', {})['result'], repr(object))
        self.assertEqual(handlers.run_code('o', {'o': OP('/x/y')})['result'], '/x/y')

    def test_traceback(self):
        with self.assertRaises(handlers.ExecError) as cm:
            handlers.run_code("print('before')\n1/0", {})
        tb = cm.exception.full_traceback()
        self.assertIn('ZeroDivisionError', tb)
        self.assertIn('before', tb)

    def test_namespace_has_td_globals(self):
        ns = handlers.exec_namespace()
        for n in ('op', 'project', 'app', 'absTime', 'td', 'ParMode', 'me'):
            self.assertIn(n, ns)

    def test_split(self):
        body, last = handlers.split_last_expr('a = 1\nif a:\n    pass\n')
        self.assertIsNotNone(body)
        self.assertIsNone(last)
        body, last = handlers.split_last_expr('3')
        self.assertIsNone(body)
        self.assertEqual(eval(last), 3)


class Dispatch(unittest.TestCase):
    def setUp(self):
        handlers._PENDING.clear()

    def test_unknown_cmd(self):
        out, send = collect()
        handlers.dispatch(json.dumps({'id': 1, 'cmd': 'frobnicate', 'args': {}}), send)
        self.assertEqual(out[0]['id'], 1)
        self.assertFalse(out[0]['ok'])
        self.assertIn('frobnicate', out[0]['error'])

    def test_bad_json(self):
        out, send = collect()
        handlers.dispatch('{nope', send)
        self.assertEqual((out[0]['id'], out[0]['ok']), (None, False))
        self.assertIn('traceback', out[0])

    def test_exception_gives_traceback(self):
        out, send = collect()
        handlers.dispatch(json.dumps({'id': 2, 'cmd': 'info', 'args': {'path': '/does/not/exist'}}), send)
        self.assertFalse(out[0]['ok'])
        self.assertIn('Traceback', out[0]['traceback'])
        handlers.dispatch(json.dumps({'id': 3, 'cmd': 'exec', 'args': {'code': 'raise KeyError("k")'}}), send)
        self.assertEqual((out[1]['id'], out[1]['ok']), (3, False))
        self.assertIn('KeyError', out[1]['traceback'])

    def test_bad_args(self):
        out, send = collect()
        handlers.dispatch(json.dumps({'id': 4, 'cmd': 'move', 'args': {'path': '/x', 'bogus': 1}}), send)
        self.assertFalse(out[0]['ok'])
        self.assertIn('bogus', out[0]['error'])

    def test_ping_pong_and_ignored_types(self):
        out, send = collect()
        handlers.dispatch('{"type":"ping"}', send)
        handlers.dispatch('{"type":"whatever"}', send)
        self.assertEqual(out, [{'type': 'pong'}])

    def test_exec_ok(self):
        out, send = collect()
        handlers.dispatch(json.dumps({'id': 5, 'cmd': 'exec', 'args': {'code': 'print(1)\n2+2'}}), send)
        self.assertEqual(out[0], {'id': 5, 'ok': True, 'result': {'stdout': '1\n', 'stderr': '', 'result': 4}})

    def test_status(self):
        out, send = collect()
        handlers.dispatch('{"id":6,"cmd":"status","args":{}}', send)
        r = out[0]['result']
        self.assertEqual((r['build'], r['fps'], r['protocol']), ('2025.31550', 60, 1))

    def test_pending_flow(self):
        calls = []
        handlers._runner = lambda script, frames: calls.append((script, frames))
        try:
            out, send = collect()
            handlers.dispatch(json.dumps({'id': 9, 'cmd': 'exec', 'args': {'code': '7*6', 'frames': 3}}), send)
            self.assertEqual(out, [])
            self.assertEqual(calls, [("op('/jazib_mcp/handlers').module._finish(9)", 3)])
            self.assertIn(9, handlers._PENDING)
            handlers._finish(9)
            self.assertEqual(out[0], {'id': 9, 'ok': True, 'result': {'stdout': '', 'stderr': '', 'result': 42}})
            self.assertNotIn(9, handlers._PENDING)
            handlers._finish(9)  # second call (or after a reload): ignored
            self.assertEqual(len(out), 1)
            # a delayed failure still replies ok:false with a traceback
            handlers.dispatch(json.dumps({'id': 10, 'cmd': 'exec', 'args': {'code': '1/0', 'frames': 1}}), send)
            handlers._finish(10)
            self.assertEqual((out[1]['id'], out[1]['ok']), (10, False))
            self.assertIn('ZeroDivisionError', out[1]['traceback'])
            # syntax errors fail at once, not frames later
            handlers.dispatch(json.dumps({'id': 11, 'cmd': 'exec', 'args': {'code': 'def', 'frames': 2}}), send)
            self.assertEqual((out[2]['id'], out[2]['ok']), (11, False))
            # errors: frames=0 is still at least one frame later
            handlers.dispatch(json.dumps({'id': 12, 'cmd': 'errors', 'args': {'frames': 0}}), send)
            self.assertEqual(calls[-1][1], 1)
        finally:
            handlers._runner = None

    def test_reply_is_ascii_json(self):
        out = []
        handlers.dispatch(json.dumps({'id': 13, 'cmd': 'exec', 'args': {'code': "'\\u00e9'"}}), out.append)
        out[0].encode('ascii')
        self.assertEqual(json.loads(out[0])['result']['result'], '\u00e9')


class Token(unittest.TestCase):
    def test_created_mode_600_and_reused(self):
        with tempfile.TemporaryDirectory() as d:
            sd = os.path.join(d, 'state')
            old = os.environ.get('JTD_STATE_DIR')
            os.environ['JTD_STATE_DIR'] = sd
            try:
                tok = handlers.read_or_create_token()
            finally:
                if old is None:
                    del os.environ['JTD_STATE_DIR']
                else:
                    os.environ['JTD_STATE_DIR'] = old
            path = os.path.join(sd, 'token')
            self.assertRegex(tok, r'^[0-9a-f]{48}$')
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            self.assertEqual(handlers.read_or_create_token(sd), tok)  # existing file wins

    def test_bad_token_file(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'token'), 'w') as f:
                f.write('short')
            with self.assertRaises(ValueError):
                handlers.read_or_create_token(d)

    def test_hello_shape(self):
        h = handlers.build_hello('a' * 48, handlers.td_info())
        self.assertEqual(h['type'], 'hello')
        self.assertEqual(h['td']['protocol'], 1)
        self.assertEqual(h['td']['build'], '2025.31550')
        for k in ('version', 'osName', 'project', 'folder', 'pid'):
            self.assertIn(k, h['td'])


class Ascii(unittest.TestCase):
    def test_every_td_file_is_ascii(self):
        names = [n for n in sorted(os.listdir(TD_DIR)) if os.path.isfile(os.path.join(TD_DIR, n))
                 and not n.endswith(('.tox', '.pyc'))]
        self.assertIn('handlers.py', names)
        for n in names:
            with open(os.path.join(TD_DIR, n), 'rb') as f:
                f.read().decode('ascii')  # raises on any non-ASCII byte

    def test_td_files_compile(self):
        for n in ('handlers.py', 'callbacks.py', 'install.py'):
            with open(os.path.join(TD_DIR, n), encoding='utf-8') as f:
                compile(f.read(), n, 'exec')


class Layout(unittest.TestCase):
    T = {'w': 130, 'h': 90, 'fam': 'TOP'}

    def nodes(self, *names, **extra):
        d = {n: dict(self.T) for n in names}
        d.update(extra)
        return d

    def test_chain_one_row_left_to_right(self):
        n = self.nodes('cam', 'blur', 'level', 'null_out')
        e = [('cam', 'blur', 0), ('blur', 'level', 0), ('level', 'null_out', 0)]
        p = handlers.plan_flow(n, e)
        ys = {p[k][1] for k in n}
        self.assertEqual(len(ys), 1)
        xs = [p[k][0] for k in ('cam', 'blur', 'level', 'null_out')]
        self.assertEqual(xs, sorted(xs))
        self.assertEqual(xs[1] - xs[0], 130 + handlers.GAP_X)
        r = handlers.layout_check(n, e, p)
        self.assertEqual(r['overlaps'], [])
        self.assertEqual(r['back_wires'], [])

    def test_side_input_below_spine(self):
        n = self.nodes('a', 'b', 'mask', 'comp', 'out')
        e = [('a', 'b', 0), ('b', 'comp', 0), ('mask', 'comp', 1), ('comp', 'out', 0)]
        p = handlers.plan_flow(n, e)
        self.assertEqual(p['a'][1], p['out'][1])  # spine straight
        self.assertLess(p['mask'][1], p['b'][1])   # side input on a lower row
        self.assertEqual(p['mask'][0], p['b'][0])  # and in the column just before its consumer
        self.assertEqual(handlers.layout_check(n, e, p)['overlaps'], [])

    def test_feedback_cycle_no_crash_no_overlap(self):
        n = self.nodes('src', 'comp', 'fb', 'out')
        e = [('src', 'comp', 0), ('fb', 'comp', 1), ('comp', 'fb', 0), ('comp', 'out', 0)]
        p = handlers.plan_flow(n, e)
        self.assertEqual(set(p), set(n))
        self.assertEqual(handlers.layout_check(n, e, p)['overlaps'], [])

    def test_bands_chop_above_top_and_docks_get_room(self):
        n = self.nodes('lfo', 'math', 'noise', 'glsl', 'null1')
        n['lfo']['fam'] = n['math']['fam'] = 'CHOP'
        n['glsl']['docks'] = [(130, 90), (130, 90), (130, 90)]
        e = [('lfo', 'math', 0), ('noise', 'glsl', 0), ('glsl', 'null1', 0)]
        p = handlers.plan_flow(n, e)
        self.assertGreater(p['lfo'][1], p['noise'][1])
        docks = handlers.dock_offsets(p['glsl'], n['glsl']['docks'])
        rects = [(x, y, 130, 90) for x, y in docks] + [(p[k][0], p[k][1], 130, 90) for k in n]
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                self.assertFalse(handlers.rects_overlap(a, b), (a, b))

    def test_scrambled_twelve_ops_clean(self):
        names = ['op%d' % i for i in range(12)]
        n = self.nodes(*names)
        e = [('op0', 'op1', 0), ('op1', 'op2', 0), ('op2', 'op3', 0), ('op4', 'op2', 1), ('op5', 'op6', 0),
             ('op6', 'op7', 0), ('op8', 'op7', 1), ('op9', 'op10', 0), ('op3', 'op11', 0), ('op7', 'op11', 1)]
        p = handlers.plan_flow(n, e)
        r = handlers.layout_check(n, e, p)
        self.assertEqual(r['overlaps'], [])
        self.assertEqual(r['back_wires'], [])

    def test_unwired_singles_in_rows(self):
        n = {k: {'w': 160, 'h': 130, 'fam': 'COMP'} for k in ('state', 'looks', 'mixer', 'ui', 'ui_window')}
        n['midi_map'] = {'w': 130, 'h': 90, 'fam': 'DAT'}
        p = handlers.plan_flow(n, [])
        comps = {p[k][1] for k in ('state', 'looks', 'mixer', 'ui', 'ui_window')}
        self.assertEqual(len(comps), 1)                       # one row, not a column
        self.assertGreater(p['midi_map'][1], min(comps))     # DAT band above the COMP band
        self.assertEqual(handlers.layout_check(n, [], p)['overlaps'], [])

    def test_feedback_back_wires_by_design(self):  # T-163
        n = self.nodes('src', 'comp', 'level', 'fb', 'other')
        e = [('src', 'comp', 0), ('comp', 'level', 0), ('fb', 'comp', 1), ('level', 'fb', 0), ('other', 'src', 0)]
        p = {'src': (0, 0), 'comp': (200, 0), 'level': (400, 0), 'fb': (100, -200), 'other': (600, 0)}
        self.assertEqual(handlers.layout_check(n, e, p)['back_wires'], [['fb', 'comp'], ['level', 'fb'],
                                                                         ['other', 'src']])
        n['fb']['fb'] = True
        self.assertEqual(handlers.layout_check(n, e, p)['back_wires'], [['other', 'src']])
        n['other']['fb_src'] = True
        self.assertEqual(handlers.layout_check(n, e, p)['back_wires'], [])

    def test_layout_nodes_marks_feedback(self):  # T-163
        c = OP('/p', optype='baseCOMP', family='COMP')
        src = OP('/p/src')
        last = OP('/p/last')
        fb = OP('/p/fb', optype='feedbackTOP')
        fb.par = types.SimpleNamespace(top=FakePar(fb, 'top', val=last))
        for o in (src, last, fb):
            o.dock = None
            o.nodeWidth, o.nodeHeight = 130, 90
            o.docked = []
            o.parent = (lambda: c)
        c.children = [src, last, fb]
        fb.inputConnectors[0].connect(src.outputConnectors[0])
        _k, _b, nodes, _e = handlers._layout_nodes(c)
        self.assertTrue(nodes['fb'].get('fb'))
        self.assertTrue(nodes['last'].get('fb_src'))
        self.assertFalse(nodes['src'].get('fb') or nodes['src'].get('fb_src'))
        fb.par.top.val = 'last'  # a path string reads the same
        self.assertTrue(handlers._layout_nodes(c)[2]['last'].get('fb_src'))

    def test_foreign_comp_needs_externaltox_path(self):  # T-163
        def comp(on, path):
            o = OP('/p/c', optype='baseCOMP', family='COMP')
            o.par = types.SimpleNamespace(**{k: FakePar(o, k, val=v) for k, v in (
                ('enableexternaltox', on), ('externaltox', path), ('clone', None), ('opshortcut', ''))})
            return o
        self.assertFalse(handlers._foreign_comp(comp(True, '')))
        self.assertFalse(handlers._foreign_comp(comp(True, '  ')))
        self.assertTrue(handlers._foreign_comp(comp(True, 'lib/x.tox')))
        self.assertFalse(handlers._foreign_comp(comp(False, 'lib/x.tox')))

    def test_free_spot_steps_down(self):
        x, y = handlers.free_spot([(0, 0, 130, 90)], 0, 0, 130, 90)
        self.assertEqual(x, 0)
        self.assertLessEqual(y, -90)


class DefaultRes(unittest.TestCase):
    def test_generator_gets_vertical_1080p(self):
        self.assertEqual(handlers.default_res_plan('noiseTOP', None, None),
                         {'outputresolution': {'menu': 'custom'}, 'resolutionw': 1080, 'resolutionh': 1920})

    def test_filter_and_overrides_untouched(self):
        self.assertEqual(handlers.default_res_plan('blurTOP', None, None), {})
        self.assertEqual(handlers.default_res_plan('glslTOP', {'resolutionw': 512}, None), {})
        self.assertEqual(handlers.default_res_plan('glslTOP', None, False), {})
        self.assertEqual(handlers.default_res_plan('textTOP', None, [720, 1280])['resolutionh'], 1280)


class SaveConflicts(unittest.TestCase):
    def test_target_and_numbered_siblings(self):
        names = ['Show.toe', 'Show.1.toe', 'Show.12.toe', 'Show2.toe', 'Show.tox', 'CrashAutoSave.Show.1.toe', 'x.txt']
        self.assertEqual(handlers.save_conflicts('/p/Show.toe', names), ['Show.1.toe', 'Show.12.toe', 'Show.toe'])

    def test_numbered_target_maps_to_base(self):
        self.assertEqual(handlers.save_conflicts('/p/Show.1.toe', ['Show.toe']), ['Show.toe'])

    def test_no_conflict(self):
        self.assertEqual(handlers.save_conflicts('/p/New.toe', ['Show.toe', 'Show.1.toe']), [])


class FakePane(object):
    def __init__(self, name, type_='PaneType.NETWORKEDITOR', owner=None, pid=1):
        self.name, self.type, self.owner, self.id = name, type_, owner, pid
        self.zoom, self.calls = 1.0, []

    def home(self, zoom=True, op=None):
        self.calls.append(('home', op.path if op is not None else None))

    def homeSelected(self, zoom=True):
        self.calls.append(('homeSelected', zoom))


class FakePanes(list):
    current = None


class FocusOp(OP):
    _n = 100

    def __init__(self, path, parent_=None):
        OP.__init__(self, path)
        FocusOp._n += 1
        self.id = FocusOp._n
        self.valid = True
        self.color = (0.55, 0.55, 0.55)
        self.selected = self.current = False
        self._parent, self._store = parent_, {}

    def parent(self):
        return self._parent

    def store(self, k, v):
        self._store[k] = v

    def fetch(self, k, default=None, search=True):
        return self._store.get(k, default)

    def unstore(self, k):
        self._store.pop(k, None)


class FocusComp(FocusOp):
    def __init__(self, path):
        FocusOp.__init__(self, path)
        self.isCOMP = True

    @property
    def selectedChildren(self):
        return [c for c in self.children if c.selected]

    @property
    def currentChild(self):
        return next((c for c in self.children if c.current), None)


class Focus(unittest.TestCase):
    def setUp(self):
        self.comp = FocusComp('/project1')
        self.a = FocusOp('/project1/a', self.comp)
        self.b = FocusOp('/project1/b', self.comp)
        self.comp.children = [self.a, self.b]
        self.b.selected = True
        self.text = FakePane('t', 'PaneType.TEXTPORT', pid=1)
        self.net = FakePane('net', owner=OP('/'), pid=2)
        panes = FakePanes([self.text, self.net])
        panes.current = self.text
        self.runs = []
        for o in (self.comp, self.a, self.b):
            OPS[o.path] = o
            OPS[o.id] = o
        handlers.ui = types.SimpleNamespace(panes=panes, rolloverOp=self.b)
        handlers.run = lambda script, **kw: self.runs.append((script, kw))

    def tearDown(self):
        del handlers.ui
        handlers.run = sys.modules['td'].run
        for o in (self.comp, self.a, self.b):
            OPS.pop(o.path, None)
            OPS.pop(o.id, None)

    def test_pick_pane_prefers_current_network(self):
        n2 = FakePane('n2', pid=3)
        self.assertIs(handlers.pick_network_pane([self.text, self.net, n2], n2), n2)
        self.assertIs(handlers.pick_network_pane([self.text, self.net, n2], self.text), self.net)
        self.assertIsNone(handlers.pick_network_pane([self.text], None))

    def test_pick_this(self):
        a, b = OP('/a'), OP('/b')
        self.assertIs(handlers.pick_this([a], a), a)
        self.assertIs(handlers.pick_this([], a), a)
        self.assertIs(handlers.pick_this([b], a), b)
        self.assertIsNone(handlers.pick_this([b, OP('/c')], a))
        self.assertIsNone(handlers.pick_this([], None))
        self.assertIs(handlers.pick_this([OP('/a')], a), a)  # same path, other object

    def test_focus_selects_pans_homes_no_flash_by_default(self):
        r = handlers.cmd_focus('/project1/a')
        self.assertIs(self.net.owner, self.comp)
        self.assertTrue(self.a.selected and self.a.current)
        self.assertFalse(self.b.selected)
        self.assertEqual(self.net.calls, [('homeSelected', False)])
        self.assertEqual(r['owner'], '/project1')
        self.assertEqual(self.runs, [])
        self.assertEqual(self.a.color, (0.55, 0.55, 0.55))
        self.assertNotIn('focus', handlers.MUTATING)
        self.assertNotIn('selection', handlers.MUTATING)

    def test_focus_no_select_homes_on_op_and_number_zoom(self):
        handlers.cmd_focus('/project1/a', select=False, zoom=2.5)
        self.assertTrue(self.b.selected)
        self.assertEqual(self.net.calls, [('home', '/project1/a')])
        self.assertEqual(self.net.zoom, 2.5)

    def test_focus_without_network_pane_is_a_note(self):
        handlers.ui.panes = FakePanes([self.text])
        r = handlers.cmd_focus('/project1/a')
        self.assertIn('no network editor pane', r['notes'][0])

    def test_flash_restores_colour(self):
        handlers.cmd_focus('/project1/a', flash=True)
        self.assertEqual(self.a.color, handlers.FLASH_COLOR)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(self.runs[0][1], {'delayMilliSeconds': 500})
        handlers.cmd_focus('/project1/a', flash=True)  # second flash keeps the true original
        self.assertTrue(handlers._unflash(self.a.id, self.a.path))
        self.assertEqual(tuple(self.a.color), (0.55, 0.55, 0.55))
        self.assertIsNone(self.a.fetch(handlers.FLASH_KEY))
        self.assertFalse(handlers._unflash(self.a.id, self.a.path))  # second timer: nothing left to do

    def test_unflash_op_deleted_or_recoloured(self):
        handlers._flash(self.a)
        OPS.pop(self.a.id)
        OPS.pop(self.a.path)
        self.assertFalse(handlers._unflash(self.a.id, self.a.path))  # gone: no raise
        OPS[self.a.path] = self.a  # back from an undo with a new id: found by path
        self.assertTrue(handlers._unflash(99999, self.a.path))
        self.assertEqual(tuple(self.a.color), (0.55, 0.55, 0.55))
        handlers._flash(self.b)
        self.b.color = (0.1, 0.2, 0.3)  # the user recoloured it meanwhile: theirs wins
        handlers._unflash(self.b.id, self.b.path)
        self.assertEqual(self.b.color, (0.1, 0.2, 0.3))

    def test_flash_falls_back_to_frames_then_restores_on_failure(self):
        def no_ms(script, **kw):
            if 'delayMilliSeconds' in kw:
                raise TypeError('no ms')
            self.runs.append((script, kw))
        handlers.run = no_ms
        self.assertIsNone(handlers._flash(self.a))
        self.assertEqual(self.runs[0][1], {'delayFrames': 30})

        def broken(script, **kw):
            raise RuntimeError('x')
        handlers.run = broken
        self.assertIn('flash skipped', handlers._flash(self.b))
        self.assertEqual(self.b.color, (0.55, 0.55, 0.55))
        self.assertIsNone(self.b.fetch(handlers.FLASH_KEY))

    def test_selection(self):
        self.net.owner = self.comp
        self.a.current = True
        r = handlers.cmd_selection()
        self.assertEqual(r['owner'], '/project1')
        self.assertEqual(r['selected'], ['/project1/b'])
        self.assertEqual(r['current']['path'], '/project1/a')
        self.assertEqual(r['rollover']['path'], '/project1/b')
        self.assertEqual(r['this']['path'], '/project1/b')  # lone selected beats an unselected current
        self.assertEqual([p['current'] for p in r['panes']], [True, False])
        self.a.selected = True
        self.assertEqual(handlers.cmd_selection()['this']['path'], '/project1/a')  # current and selected
        self.a.current = False
        r = handlers.cmd_selection()
        self.assertIsNone(r['this'])
        self.assertIn('ask which', r['notes'][0])
        handlers.dumps(r)
class InspectHelpers(unittest.TestCase):
    def test_rnd(self):
        self.assertEqual(handlers.rnd(3.14159265), 3.1416)
        self.assertEqual(handlers.rnd(123456789.0), 123460000.0)
        self.assertEqual(handlers.rnd(0), 0.0)
        self.assertEqual(handlers.rnd(float('nan')), 'nan')
        self.assertEqual(handlers.rnd(True), True)
        self.assertEqual(handlers.rnd('x'), 'x')

    def test_num_stats(self):
        self.assertEqual(handlers.num_stats([1, 2, 3, 6]), {'min': 1.0, 'max': 6.0, 'mean': 3.0})
        self.assertEqual(handlers.num_stats([]), {'min': None, 'max': None, 'mean': None})
        d = handlers.num_stats([1, float('inf'), 'z', 3])
        self.assertEqual((d['mean'], d['nonfinite']), (2.0, 2))

    def test_glob_pick(self):
        names = ['tx', 'ty', 'tz', 'rx', 'chan1']
        self.assertEqual(handlers.glob_pick(names), (names, 5))
        self.assertEqual(handlers.glob_pick(names, 't*'), (['tx', 'ty', 'tz'], 3))
        self.assertEqual(handlers.glob_pick(names, 'tx rx'), (['tx', 'rx'], 2))
        self.assertEqual(handlers.glob_pick(names, ['ch*', 'ty']), (['ty', 'chan1'], 2))
        self.assertEqual(handlers.glob_pick(names, 't*', cap=2), (['tx', 'ty'], 3))

    def test_channel_stats_and_heads(self):
        st = handlers.channel_stats([(0, 1, 0.5, 1), (1, 0, 0.5, 1)])
        self.assertEqual(st['r'], {'min': 0.0, 'max': 1.0, 'mean': 0.5})
        self.assertEqual(sorted(st), ['a', 'b', 'g', 'r'])
        self.assertEqual(handlers.head_table([['a' * 100, 'b']] * 5, 2, max_len=3), [['aaa...', 'b']] * 2)
        self.assertEqual(handlers.head_lines('x\ny\nz', 2), (['x', 'y'], 3))
        self.assertEqual(handlers.count_by(['TOP', 'CHOP', 'TOP']), {'TOP': 2, 'CHOP': 1})
        self.assertEqual(handlers.count_by(['a', 'b', 'b', 'c'], top=1), {'b': 2})

    def test_defaults(self):
        self.assertEqual(handlers.inspect_defaults(None, None, None, 'TOP'), ('summary', 5, 0))
        self.assertEqual(handlers.inspect_defaults('full', None, None, 'TOP'), ('full', 20, 4))
        self.assertEqual(handlers.inspect_defaults('full', 999, 99, 'CHOP'), ('full', 100, 16))
        self.assertEqual(handlers.inspect_defaults('summary', 3, 0, 'TOP'), ('summary', 3, 0))
        with self.assertRaises(ValueError):
            handlers.inspect_defaults('everything', None, None, 'TOP')

    def test_build_gate(self):
        self.assertEqual(handlers.build_num('2025.31550'), 31550.0)
        self.assertEqual(handlers.build_num('31550'), 31550.0)
        self.assertIsNone(handlers.build_num(''))
        self.assertIsNone(handlers.build_gate('31550', 30000, 'x'))
        self.assertIsNone(handlers.build_gate('', 30000, 'x'))
        g = handlers.build_gate('29000', 30000, 'POPs')
        self.assertEqual(g, {'available': False, 'note': 'needs TD >= 30000: POPs'})

    def test_read_only(self):
        self.assertNotIn('inspect', handlers.MUTATING)
        self.assertIn('inspect', handlers.COMMANDS)


class FakeChan(object):
    def __init__(self, name, vals):
        self.name, self.vals = name, vals


class FakeCell(object):
    def __init__(self, val):
        self.val = val


class Inspect(unittest.TestCase):
    def setUp(self):
        handlers._PENDING.clear()
        self.calls = []
        handlers._runner = lambda script, frames: self.calls.append(frames)

    def tearDown(self):
        handlers._runner = None
        OPS.clear()

    def run_inspect(self, args):
        out, send = collect()
        handlers.dispatch(json.dumps({'id': 77, 'cmd': 'inspect', 'args': args}), send)
        self.assertEqual(self.calls, [1])
        handlers._finish(77)
        self.assertTrue(out[0]['ok'], out[0])
        return out[0]['result']

    def test_chop(self):
        o = OP('/p/lfo', 'lfoCHOP', 'CHOP')
        o.numChans, o.numSamples, o.rate, o.start, o.end, o.isTimeSlice = 3, 4, 60, 0, 3, False
        o.cooked = 0
        o.cook = lambda force=False: setattr(o, 'cooked', o.cooked + 1)
        o.chans = lambda *a: [FakeChan('tx', [0, 1, 2, 3]), FakeChan('ty', [5, 5, 5, 5]), FakeChan('rz', [1, 1, 1, -1])]
        OPS['/p/lfo'] = o
        r = self.run_inspect({'path': '/p/lfo', 'channels': 't*'})
        self.assertEqual(o.cooked, 1)
        self.assertEqual([c['name'] for c in r['channels']], ['tx', 'ty'])
        self.assertEqual(r['channels'][0], {'name': 'tx', 'min': 0.0, 'max': 3.0, 'mean': 1.5, 'last': 3.0})
        self.calls.clear()
        r = self.run_inspect({'path': '/p/lfo', 'detail': 'full', 'rows': 2, 'cook': False})
        self.assertEqual(o.cooked, 1)
        self.assertEqual(r['channels'][2]['head'], [1.0, 1.0])

    def test_top_numpy_broken_falls_back_to_sample(self):
        o = OP('/p/out', 'nullTOP', 'TOP')
        o.width, o.height, o.pixelFormat = 1080, 1920, 'rgba8fixed'

        def broken(delayed=False):
            raise ImportError('numpy._core.multiarray failed to import')
        o.numpyArray = broken
        o.sample = lambda u=0, v=0: (u, v, 0.0, 1.0)
        OPS['/p/out'] = o
        r = self.run_inspect({'path': '/p/out', 'sample': 2})
        self.assertIn('T-48', r['notes'][0])
        self.assertTrue(r['stats_source'].startswith('approx: 2x2'))
        self.assertEqual(r['grid'][0][0], [0.25, 0.75, 0.0, 1.0])  # row 0 = top (v high)
        self.assertEqual(r['stats']['a'], {'min': 1.0, 'max': 1.0, 'mean': 1.0})

    def test_top_numpy_path(self):
        try:
            import numpy as np
        except Exception:
            self.skipTest('numpy not installed (optional for this test)')
        o = OP('/p/ramp', 'rampTOP', 'TOP')
        o.width, o.height = 4, 4
        a = np.zeros((4, 4, 4), dtype=np.float32)
        a[0:2, :, 0] = 1.0  # rows 0-1 = bottom half red (TD numpyArray row 0 = bottom)
        a[:, :, 3] = 1.0
        o.numpyArray = lambda delayed=False: a
        OPS['/p/ramp'] = o
        r = self.run_inspect({'path': '/p/ramp', 'sample': 2})
        self.assertEqual(r['stats']['r'], {'min': 0.0, 'max': 1.0, 'mean': 0.5})
        self.assertEqual([row[0][0] for row in r['grid']], [0.0, 1.0])  # flipped: top row first
        self.assertNotIn('notes', r)

    def test_top_all_broken_notes_not_raises(self):
        o = OP('/p/out', 'nullTOP', 'TOP')
        o.numpyArray = lambda delayed=False: (_ for _ in ()).throw(RecursionError('deep'))
        o.sample = lambda **k: (_ for _ in ()).throw(RuntimeError('no'))
        OPS['/p/out'] = o
        r = self.run_inspect({'path': '/p/out'})
        self.assertEqual(len(r['notes']), 2)
        self.assertNotIn('stats', r)

    def test_dat_table_and_text(self):
        t = OP('/p/table', 'tableDAT', 'DAT')
        t.isTable, t.numRows, t.numCols = True, 3, 2
        t.rows = lambda: [[FakeCell('a'), FakeCell('b')], [FakeCell('1'), FakeCell('2')], [FakeCell('3'), FakeCell('4')]]
        OPS['/p/table'] = t
        r = self.run_inspect({'path': '/p/table', 'rows': 2})
        self.assertEqual(r['rows'], [['a', 'b'], ['1', '2']])
        self.calls.clear()
        x = OP('/p/text', 'textDAT', 'DAT')
        x.isTable, x.text = False, 'l1\nl2\nl3'
        OPS['/p/text'] = x
        r = self.run_inspect({'path': '/p/text', 'rows': 1})
        self.assertEqual((r['numLines'], r['lines'], r['text_len']), (3, ['l1'], 8))

    def test_sop_pop_comp(self):
        P = types.SimpleNamespace
        s = OP('/p/box', 'boxSOP', 'SOP')
        s.numPoints, s.numPrims = 8, 6
        s.computeBounds = lambda: P(min=P(x=-1, y=-1, z=-1), max=P(x=1, y=1, z=1), center=P(x=0, y=0, z=0),
                                    size=P(x=2, y=2, z=2))
        s.pointAttribs = [P(name='P'), P(name='N')]
        OPS['/p/box'] = s
        r = self.run_inspect({'path': '/p/box'})
        self.assertEqual((r['numPoints'], r['bounds']['size'], r['attribs']['point']), (8, [2.0, 2.0, 2.0], ['P', 'N']))
        self.calls.clear()
        p = OP('/p/pts', 'pointgeneratorPOP', 'POP')
        p.numPoints = lambda delayed=False, max=False: 10000
        p.pointAttributes = [P(name='P'), P(name='Color')]
        OPS['/p/pts'] = p
        r = self.run_inspect({'path': '/p/pts'})
        self.assertEqual((r['numPoints'], r['attribs']['point']), (10000, ['P', 'Color']))
        self.assertTrue(any('numPrims' in n for n in r['notes']))  # missing API -> note, not a raise
        self.calls.clear()
        old = handlers.app
        handlers.app = types.SimpleNamespace(build='29000')
        try:
            r = self.run_inspect({'path': '/p/pts'})
        finally:
            handlers.app = old
        self.assertEqual(r['pop']['available'], False)
        self.assertNotIn('numPoints', r)
        self.calls.clear()
        c = OP('/p', 'baseCOMP', 'COMP')
        c.isCOMP = True
        c.children = [OP('/p/a'), OP('/p/b'), OP('/p/c', 'lfoCHOP', 'CHOP')]
        OPS['/p'] = c
        r = self.run_inspect({'path': '/p'})
        self.assertEqual((r['children'], r['by_family']), (3, {'TOP': 2, 'CHOP': 1}))
class NetExport(unittest.TestCase):
    def test_values_and_codes(self):
        self.assertEqual(handlers.net_value(0.1 + 0.2), 0.3)
        self.assertEqual(handlers.net_value(-0.0000001), 0.0)
        self.assertEqual(handlers.net_value([1.23456789, 'a']), [1.234568, 'a'])
        self.assertEqual(handlers.net_par_code(ParMode.EXPRESSION, 3, 'me.time.frame'), '=me.time.frame')
        self.assertEqual(handlers.net_par_code(ParMode.BIND, 3, '', "op('c').par.x"), "~op('c').par.x")
        self.assertEqual(handlers.net_par_code(ParMode.EXPORT, 3), '@export')
        self.assertEqual(handlers.net_par_code(ParMode.CONSTANT, '=lit'), '==lit')
        self.assertEqual(handlers.net_par_code(ParMode.CONSTANT, '~x'), '~~x')
        self.assertEqual(handlers.net_par_code(ParMode.CONSTANT, 'plain'), 'plain')

    def test_text_fields(self):
        self.assertEqual(handlers.net_text_fields('short'), {'text': 'short'})
        big = '\n'.join('line %d' % i for i in range(200))
        f = handlers.net_text_fields(big)
        self.assertEqual((f['text_lines'], f['text_len'], len(f['text_sha1'])), (200, len(big), 16))
        self.assertEqual(f['text_head'][0], 'line 0')
        self.assertEqual(len(f['text_head']), handlers.NET_HEAD_LINES)
        self.assertNotEqual(f['text_sha1'], handlers.net_text_fields(big + 'x')['text_sha1'])

    def test_ref(self):
        self.assertEqual(handlers.net_ref('/r/a/n1', '/r/a/n2', '/r'), 'n1')
        self.assertEqual(handlers.net_ref('/r/b/n1', '/r/a/n2', '/r'), 'b/n1')
        self.assertEqual(handlers.net_ref('/x/n1', '/r/a/n2', '/r'), '/x/n1')
        self.assertEqual(handlers.net_ref('/a/n', '/b/m', '/'), 'a/n')

    def test_line_order_and_render_cap(self):
        ln = handlers.net_line({'pars': {'b': 1, 'a': 2}, 'zz': 1, 't': 'noiseTOP', 'p': 'n'})
        self.assertEqual(ln, '{"p":"n","t":"noiseTOP","pars":{"a":2,"b":1},"zz":1}')
        recs = [{'p': 'op%03d' % i, 't': 'nullTOP'} for i in range(100)]
        text, n, tr = handlers.net_render({'format': 'jtd-net'}, recs, 0)
        self.assertEqual((n, tr), (100, False))
        text, n, tr = handlers.net_render({'format': 'jtd-net'}, recs, 1000)
        self.assertTrue(tr and 0 < n < 100 and len(text) <= 1000)
        self.assertEqual(json.loads(text.strip().split('\n')[-1]), {'end': True, 'ops': n, 'total': 100, 'truncated': True})

    def tree(self):
        OPS.clear()
        root = OP('/r/look', optype='baseCOMP', family='COMP', n_in=0,
                  pars=[{'name': 'Speed', 'val': 2, 'default': 1, 'page': 'Controls'}])
        root.par['Speed'].isCustom = True
        root.isCOMP = True
        noise = OP('/r/look/noise1', pars=[{'name': 'amp', 'val': 2, 'default': 1}, {'name': 'seed', 'val': 0, 'default': 0},
                                            {'name': 'go', 'pulse': True, 'val': False, 'default': False}])
        noise.par['seed'].mode, noise.par['seed'].expr = ParMode.EXPRESSION, 'absTime.frame'
        lvl = OP('/r/look/level1', n_in=2)
        noise.outputConnectors[0].connect(lvl.inputConnectors[1])
        dat = OP('/r/look/notes', optype='textDAT', family='DAT', n_in=0)
        dat.text, dat.isEditable = 'hello', True
        clone = OP('/r/look/kit', optype='baseCOMP', family='COMP', n_in=0, pars=[{'name': 'opshortcut', 'val': 'KIT', 'default': ''}])
        clone.isCOMP, clone.children = True, [OP('/r/look/kit/inner')]
        clone.par = types.SimpleNamespace(opshortcut=clone.par['opshortcut'])  # TD: o.par.<name>
        mcp = OP('/jazib_mcp', optype='baseCOMP', family='COMP')
        root.children = [noise, lvl, dat, clone]
        return root, mcp

    def test_export_tree(self):
        root, _ = self.tree()
        OPS['/r/look'] = root
        r = handlers.cmd_net_export('/r/look')
        lines = [json.loads(l) for l in r['text'].strip().split('\n')]
        self.assertEqual(lines[0]['format'], 'jtd-net')
        self.assertEqual(lines[-1], {'end': True, 'ops': 5, 'total': 5, 'truncated': False})
        by = {l['p']: l for l in lines[1:-1]}
        self.assertEqual(sorted(by), ['.', 'kit', 'level1', 'noise1', 'notes'])
        self.assertEqual(by['noise1']['pars'], {'amp': 2, 'seed': '=absTime.frame'})  # pulse skipped, default omitted
        self.assertEqual(by['level1']['in'], [None, ['noise1', 0]])
        self.assertEqual(by['notes']['text'], 'hello')
        self.assertEqual((by['kit']['skip'], by['kit']['kids']), ('package', 1))
        self.assertNotIn('kit/inner', by)
        self.assertEqual(by['.']['cp']['Controls']['Speed']['v'], 2)
        self.assertEqual(by['.']['cp']['Controls']['Speed']['def'], 1)
        self.assertEqual(handlers.cmd_net_export('/r/look')['text'], r['text'])  # deterministic
        self.assertNotIn('net_export', handlers.MUTATING)
        self.assertIn('net_export', handlers.COMMANDS)

    def test_depth_and_protected(self):
        root, mcp = self.tree()
        sub = OP('/r/look/sub', optype='baseCOMP', family='COMP', n_in=0)
        sub.isCOMP, sub.children = True, [OP('/r/look/sub/x')]
        root.children = root.children + [sub, mcp]
        recs, notes = handlers.net_collect(root, depth=1)
        ps = [r['p'] for r in recs]
        self.assertNotIn('sub/x', ps)
        self.assertEqual([r for r in recs if r['p'] == 'sub'][0]['kids'], 1)
        self.assertNotIn('jazib_mcp', ps)
        self.assertTrue(any('MCP itself' in n for n in notes))
        recs, _ = handlers.net_collect(root, depth=2)
        self.assertIn('sub/x', [r['p'] for r in recs])


class RecOp(object):
    """Minimal op for the AE / render commands: pars by name (FakePar), storage, docking, destroy."""

    def __init__(self, comp, name, optype):
        self.comp, self.name, self.OPType = comp, name, optype
        self.path = comp.path.rstrip('/') + '/' + name
        self.family = 'DAT' if optype.endswith('DAT') else ('CHOP' if optype.endswith('CHOP') else
                                                            ('COMP' if optype.endswith('COMP') else 'TOP'))
        self.valid, self.dock, self.text, self.viewer = True, None, '', False
        self.nodeX = self.nodeY = 0
        self.nodeWidth, self.nodeHeight = 130, 90
        self.inputConnectors = [FakeConnector(self, 0, True)]
        self.outputConnectors = [FakeConnector(self, 0, False)]
        self._store = {}
        menus = {'videocodectype': [('proreshq', 'ProRes 422 HQ'), ('prores4444xq', 'ProRes 4444 XQ'),
                                    ('prores4444', 'ProRes 4444')],
                 'videopixelformat': [('yuv444p10', 'YUV 4:4:4 10 bit'), ('yuva444p12', 'YUVA 4:4:4:4 12 bit')]}
        names = ('type', 'moviecontainer', 'videocodec', 'file', 'fps', 'record', 'frameend', 'active', 'dat',
                 'output', 'firstrow', 'firstcolumn')
        pars = [FakePar(self, n) for n in names] + [FakePar(self, n, menu=m) for n, m in menus.items()]
        self.par = types.SimpleNamespace(**dict((p.name, p) for p in pars))
        self.isCOMP = self.family == 'COMP'
        self.children = []

    def parent(self):
        return self.comp

    def store(self, k, v):
        self._store[k] = v

    def fetch(self, k, d=None):
        return self._store.get(k, d)

    def cook(self, force=False):
        pass

    def destroy(self):
        self.valid = False
        for o in list(self.comp.children):
            if o.dock is self:  # docked ops go with their host (T-28)
                o.valid = False


class RecComp(RecOp):
    def __init__(self, path, parent=None):
        self.path, self.name, self.OPType, self.family = path, path.rsplit('/', 1)[-1], 'baseCOMP', 'COMP'
        self.children, self.isCOMP, self.valid = [], True, True
        self.nodeX = self.nodeY = 0
        self.nodeWidth, self.nodeHeight = 130, 90
        self._parent = parent

    def parent(self):
        return self._parent

    def op(self, name):
        for c in self.children:
            if c.name == name and c.valid:
                return c
        return None

    def create(self, cls, name=None):
        if cls == 'baseCOMP':
            o = RecComp(self.path.rstrip('/') + '/' + name, self)
        else:
            o = RecOp(self, name, cls)
        self.children.append(o)
        OPS[o.path] = o
        return o

    def destroy(self):
        self.valid = False


class AEHelpers(unittest.TestCase):
    def test_pick_menu_entry(self):
        names = ['proreshq', 'prores4444xq', 'prores4444']
        labels = ['ProRes 422 HQ', 'ProRes 4444 XQ', 'ProRes 4444']
        self.assertEqual(handlers.pick_menu_entry(names, labels, all_of=('4444',), none_of=('xq',)), 'prores4444')
        self.assertEqual(handlers.pick_menu_entry(names, labels, all_of=('422', 'hq')), 'proreshq')
        self.assertIsNone(handlers.pick_menu_entry(names, labels, all_of=('hap',)))
        self.assertEqual(handlers.pick_menu_entry(['a', 'b'], ['RGB', 'RGBA'], any_of=('rgba',)), 'b')

    def test_render_plan(self):
        spec, n, f = handlers.render_plan('prores4444', 30, 30)
        self.assertEqual((spec[0], n, f, spec[3]), ('prores', 30, 30.0, True))
        for bad in (('h264', 30, 30), ('prores4444', 0, 30), ('prores4444', 30, 0), ('prores4444', 'x', 30)):
            with self.assertRaises(ValueError):
                handlers.render_plan(*bad)

    def test_pump_script_compiles_ascii(self):
        s = handlers.pump_script('/p/_jz_render', 30, True)
        s.encode('ascii')
        compile(s, 'pump', 'exec')
        self.assertIn('N = 30', s)
        self.assertIn('RT = True', s)
        self.assertIn("MFO = '/p/_jz_render'", s)

    def test_tsv_and_data_text(self):
        self.assertEqual(handlers.tsv([['a', 'b\tc'], [1, 0.5, None]]), 'a\tb c\n1\t0.5\t')
        j = json.loads(handlers.ae_data_text(['tx', 'ty'], [[0.1, 1], [0.2, 2]], 'json', 30, '/p/out'))
        self.assertEqual((j['frames'], j['channels']['tx'], j['frame']), (2, [0.1, 0.2], [0, 1]))
        c = handlers.ae_data_text(['tx'], [[0.5], [1]], 'csv', 30, '/p/out', [10, 11])
        self.assertEqual(c, 'frame,"tx"\n10,0.5\n11,1.0\n')
        with self.assertRaises(ValueError):
            handlers.ae_data_text(['a'], [], 'xml', 30, '')

    def test_mutating(self):
        self.assertIn('import_ae_anim', handlers.MUTATING)
        for c in ('export_ae_data', 'render_for_ae'):
            self.assertNotIn(c, handlers.MUTATING)
            self.assertIn(c, handlers.COMMANDS)


class AECommands(unittest.TestCase):
    def setUp(self):
        handlers._PENDING.clear()
        self.calls = []
        handlers._runner = lambda script, frames: self.calls.append(frames)
        for n in ('moviefileoutTOP', 'executeDAT', 'tableDAT', 'textDAT', 'dattoCHOP', 'nullCHOP', 'baseCOMP'):
            setattr(handlers, n, n)
        self.comp = RecComp('/p')
        OPS['/p'] = self.comp
        self.src = self.comp.create('noiseTOP', 'noise1')
        self.tmp = tempfile.mkdtemp()
        handlers.project.realTime = True

    def tearDown(self):
        handlers._runner = None
        for n in ('moviefileoutTOP', 'executeDAT', 'tableDAT', 'textDAT', 'dattoCHOP', 'nullCHOP', 'baseCOMP'):
            delattr(handlers, n)
        OPS.clear()
        handlers.project.realTime = True

    def test_render_chain_restores_realtime_and_cleans_up(self):
        out, send = collect()
        f = os.path.join(self.tmp, 'ae_out', 'take.mov')
        handlers.dispatch(json.dumps({'id': 9, 'cmd': 'render_for_ae', 'args': {
            'source': '/p/noise1', 'file': f, 'frames': 3, 'fps': 30}}), send)
        self.assertEqual(out, [])
        m = self.comp.op('_jz_render')
        ex = self.comp.op('_jz_render_pump')
        self.assertIs(ex.dock, m)
        self.assertEqual((m.par.videocodec.val, m.par.file.val, m.inputConnectors[0].connections[0].owner),
                         ('prores', f, self.src))
        handlers._finish(9)  # step_codec
        self.assertEqual((m.par.videocodectype.val, m.par.videopixelformat.val), ('prores4444', 'yuva444p12'))
        self.assertEqual((handlers.project.realTime, m.par.record.val), (False, True))
        compile(ex.text, 'pump', 'exec')
        handlers._finish(9)  # poll: not done yet
        self.assertEqual(out, [])
        m.store('jz_n', 3)
        m.store('jz_done', True)  # what the pump does after N frames
        handlers._finish(9)  # poll: done -> record off, realTime back
        self.assertEqual((handlers.project.realTime, m.par.record.val), (True, False))
        handlers._finish(9)  # finish: temp ops gone
        r = out[0]['result']
        self.assertTrue(out[0]['ok'], out[0])
        self.assertEqual((r['frames_asked'], r['cooks_counted'], r['codectype'], r['realtime_restored']),
                         (3, 3, 'prores4444', True))
        self.assertFalse(m.valid)
        self.assertFalse(ex.valid)
        self.assertEqual(self.calls, [1, 2, 5, 15])

    def test_render_error_restores_realtime(self):
        out, send = collect()
        f = os.path.join(self.tmp, 'x.mov')
        handlers.dispatch(json.dumps({'id': 10, 'cmd': 'render_for_ae', 'args': {
            'source': '/p/noise1', 'file': f, 'frames': 3}}), send)
        m = self.comp.op('_jz_render')
        m.par.videocodectype.menuNames, m.par.videocodectype.menuLabels = ['hap'], ['Hap']
        handlers._finish(10)
        self.assertFalse(out[0]['ok'])
        self.assertIn('codec type', out[0]['error'])
        self.assertTrue(handlers.project.realTime)
        self.assertFalse(m.valid)

    def test_render_refusals(self):
        with self.assertRaises(ValueError):
            handlers.cmd_render_for_ae('/p/noise1', '/tmp/x.mov', 3, alpha='straight')
        with self.assertRaises(ValueError):
            handlers.cmd_render_for_ae('/p/noise1', '/tmp/x.mp4', 3)
        with self.assertRaises(ValueError):
            handlers.cmd_render_for_ae('/p/noise1', 'rel.mov', 3)

    def test_import_builds_tables_chop_out(self):
        rows = {'meta': [['key', 'value'], ['fps', 30]], 'keys': [['layer'], ['a']], 'text': [['layer']],
                'markers': [['layer']], 'baked': [['a_opacity'], [0.0], [0.5]]}
        r = handlers.cmd_import_ae_anim('/p', 'ae_card', warnings=['w1'], arrange=False, **rows)
        c = self.comp.op('ae_card')
        self.assertEqual(sorted(o.name for o in c.children),
                         ['baked', 'baked_chop', 'keys', 'markers', 'meta', 'out', 'report', 'text'])
        self.assertEqual(c.op('baked').text, 'a_opacity\n0.0\n0.5')
        ch = c.op('baked_chop')
        self.assertEqual((ch.par.dat.val, ch.par.output.val, ch.par.firstrow.val), ('/p/ae_card/baked', 'chanpercol', 'names'))
        self.assertIs(c.op('out').inputConnectors[0].connections[0].owner, ch)
        self.assertIn('w1', c.op('report').text)
        self.assertEqual((r['frames'], r['channels'], r['out']), (2, 1, '/p/ae_card/out'))
        with self.assertRaises(ValueError):
            handlers.cmd_import_ae_anim('/p', 'ae_card', arrange=False, **rows)

    def test_export_static_and_live(self):
        chop = self.comp.create('nullCHOP', 'curves')
        chop.numSamples, chop.rate = 2, 30.0
        chans = [FakeChan('tx', [0.0, 1.0]), FakeChan('ty', [5.0, 6.0])]
        for ch in chans:
            ch.eval = (lambda c: (lambda: c.vals[-1]))(ch)
        chop.chans = lambda: chans
        f = os.path.join(self.tmp, 'ae_out', 'c.json')
        r = handlers.cmd_export_ae_data('/p/curves', f, 'json')
        self.assertEqual((r['samples'], r['channels']), (2, 2))
        with open(f) as fh:
            self.assertEqual(json.load(fh)['channels']['ty'], [5.0, 6.0])
        out, send = collect()
        f2 = os.path.join(self.tmp, 'ae_out', 'c.csv')
        handlers.dispatch(json.dumps({'id': 11, 'cmd': 'export_ae_data', 'args': {
            'chop': '/p/curves', 'file': f2, 'format': 'csv', 'frames': 3}}), send)
        for _ in range(3):
            handlers._finish(11)
        self.assertTrue(out[0]['ok'], out[0])
        self.assertEqual(out[0]['result']['samples'], 3)
        with open(f2) as fh:
            self.assertEqual(fh.read().splitlines()[0], 'frame,"tx","ty"')
        with self.assertRaises(ValueError):
            handlers.cmd_export_ae_data('/p/curves', f2, 'json')  # extension must match format


class PendingChain(unittest.TestCase):
    def test_finish_returning_pending_reschedules(self):
        handlers._PENDING.clear()
        calls, out = [], []
        handlers._runner = lambda script, frames: calls.append(frames)
        try:
            handlers._PENDING['r'] = {'send': lambda t: out.append(json.loads(t)),
                                      'finish': lambda: handlers.Pending(4, lambda: 'done')}
            handlers._finish('r')
            self.assertEqual((calls, out), ([4], []))
            handlers._finish('r')
            self.assertEqual(out, [{'id': 'r', 'ok': True, 'result': 'done'}])
            self.assertNotIn('r', handlers._PENDING)
        finally:
            handlers._runner = None


class StageSlots(unittest.TestCase):
    def test_chain_and_branches(self):
        names = ['src', 'trim', 'mono', 'speaker', 'dev']
        edges = [('src', 'trim', 0), ('trim', 'mono', 0), ('src', 'speaker', 0)]
        sl = handlers.stage_slots(names, edges)
        self.assertEqual(sl['src'], (0, 0))
        self.assertEqual(sl['trim'], (1, 0))
        self.assertEqual(sl['mono'], (2, 0))
        self.assertEqual(sl['speaker'][0], 1)
        self.assertNotEqual(sl['speaker'][1], 0)  # branch gets its own lane
        self.assertEqual(sl['dev'][0], 0)
        self.assertNotEqual(sl['dev'][1], 0)  # second root: own lane

    def test_two_parallel_chains_keep_order(self):
        names = ['a1', 'b1', 'a2', 'b2']
        sl = handlers.stage_slots(names, [('a1', 'a2', 0), ('b1', 'b2', 0)])
        self.assertEqual(sl['a2'], (1, sl['a1'][1]))
        self.assertEqual(sl['b2'], (1, sl['b1'][1]))
        self.assertNotEqual(sl['a1'][1], sl['b1'][1])


class StageGrid(unittest.TestCase):
    def test_feeding_left_parallel_stacked(self):
        # 0 audio in -> 1 bands, 0 -> 3 spectrum (parallel to bands), 1 -> 2 kick, 1,2 -> 4 out
        g = handlers.stage_grid(5, {(0, 1), (0, 3), (1, 2), (1, 4), (2, 4)})
        self.assertEqual(g[0], (0, 0))
        self.assertEqual(g[1][0], 1)
        self.assertEqual(g[3][0], 1)            # same depth as bands
        self.assertNotEqual(g[1][1], g[3][1])   # stacked, not on top of each other
        self.assertEqual(g[2][0], 2)
        self.assertEqual(g[4][0], 3)

    def test_after_without_wires(self):
        g = handlers.stage_grid(3, set(), after={1: [0], 2: [1]})
        self.assertEqual([g[k][0] for k in range(3)], [0, 1, 2])


class AssignNewOps(unittest.TestCase):
    """T-69: a stored stage plan places ops added later instead of a plain flow piling them into other boxes."""
    ST = [{'title': 'In', 'ops': ['a']}, {'title': 'Out', 'ops': ['z']}]

    def test_wired_op_joins_its_source_stage_chain_follows(self):
        edges = [('a', 'b', 0), ('b', 'c', 0), ('c', 'z', 0)]
        st, placed = handlers.assign_new_ops(self.ST, ['a', 'b', 'c', 'z'], edges, {})
        self.assertEqual(st[0]['ops'], ['a', 'b', 'c'])
        self.assertEqual(placed, {'b': 'In', 'c': 'In'})
        self.assertEqual(self.ST[0]['ops'], ['a'])  # caller's plan untouched

    def test_feeds_only_joins_consumer(self):
        st, _p = handlers.assign_new_ops(self.ST, ['a', 'q', 'z'], [('q', 'z', 1)], {})
        self.assertEqual(st[1]['ops'], ['z', 'q'])

    def test_unwired_controls_and_other(self):
        types = {'controls': 'containerCOMP', 'win': 'windowCOMP', 'pe': 'parameterexecuteDAT', 'junk': 'noiseTOP'}
        st, placed = handlers.assign_new_ops(self.ST, ['a', 'z', 'controls', 'win', 'pe', 'junk'], [], types)
        ctl = [s for s in st if s['title'] == 'Controls'][0]
        self.assertEqual((ctl['ops'], ctl['role']), (['controls', 'win', 'pe'], 'control'))
        self.assertEqual(placed['junk'], 'Other')

    def test_gone_ops_and_empty_stages_drop(self):
        st, _p = handlers.assign_new_ops(self.ST, ['z'], [], {})
        self.assertEqual([s['title'] for s in st], ['Out'])

    def test_existing_controls_stage_reused(self):
        st0 = self.ST + [{'title': 'Controls', 'role': 'control', 'ops': ['controls']}]
        st, _p = handlers.assign_new_ops(st0, ['a', 'z', 'controls', 'win'], [], {'win': 'windowCOMP'})
        self.assertEqual([s['title'] for s in st].count('Controls'), 1)
        self.assertEqual(st[2]['ops'], ['controls', 'win'])


class BoxProblems(unittest.TestCase):
    def test_intruder_unboxed_overlap(self):
        boxes = {'b1': (0, 0, 200, 200), 'b2': (300, 0, 200, 200), 'b3': (450, 0, 100, 100)}
        rects = {'x': (10, 10, 50, 50), 'y': (320, 10, 50, 50), 'lost': (1000, 0, 50, 50)}
        r = handlers.box_problems(boxes, rects, {'x': 'b1', 'y': 'b1'})
        self.assertEqual(r['intruders'], [['y', 'b2']])
        self.assertEqual(r['unboxed'], ['lost'])
        self.assertEqual(r['box_overlaps'], [['b2', 'b3']])

    def test_clean(self):
        r = handlers.box_problems({'b1': (0, 0, 200, 200)}, {'x': (10, 10, 50, 50)}, {'x': 'b1'})
        self.assertEqual(r, {'intruders': [], 'unboxed': [], 'box_overlaps': []})


class AtlasPure(unittest.TestCase):
    """td-atlas port: pure helpers (health / trace / save hook)."""

    def test_clock_calls(self):
        self.assertEqual(handlers.clock_calls('a = absTime.seconds + absTime.frame; t = time.time()'),
                         ['absTime.seconds', 'absTime.frame', 'time.time()'])
        self.assertEqual(handlers.clock_calls('x = random.random()'), ['random.random()'])
        self.assertEqual(handlers.clock_calls('random.seed(3)\nx = random.random()'), [])
        self.assertEqual(handlers.clock_calls('np.random.default_rng(1); tdu.rand(me.digits)'), [])
        self.assertEqual(handlers.clock_calls('me.time.seconds'), [])

    def test_negative_settings(self):
        ns = handlers.negative_settings
        self.assertEqual(ns('rgba16float', 2, 0, 0, False, 0), {'contrast': 2.0})
        self.assertEqual(ns('rgba32float', 1, 0.5, -0.1, False, 0), {'inlow': 0.5, 'outlow': -0.1})
        self.assertIsNone(ns('rgba8fixed', 2, 0, 0, False, 0))
        self.assertIsNone(ns('rgba11float', 2, 0, 0, False, 0))
        self.assertIsNone(ns('rgba16float', 2, 0, 0, True, 0))
        self.assertEqual(ns('rgba16float', 2, 0, 0, True, -1), {'contrast': 2.0})
        self.assertIsNone(ns('rgba16float', 1, 0, 0, False, 0))

    def test_trace_state_and_marks(self):
        ok = {'min': [0, 0, 0, 1], 'max': [0.8, 0.5, 0.2, 1], 'mean': [0.4] * 4}
        black = {'min': [0, 0, 0, 1], 'max': [0, 0, 0, 1], 'mean': [0, 0, 0, 1]}
        neg = {'min': [-0.3, 0, 0, 1], 'max': [0.5, 0.5, 0.5, 1], 'mean': [0.1] * 4}
        self.assertEqual(handlers.trace_state(None), 'unsampled')
        self.assertEqual(handlers.trace_state(ok), 'ok')
        self.assertEqual(handlers.trace_state(black), 'black')
        self.assertEqual(handlers.trace_state(neg), 'negative')
        self.assertEqual(handlers.trace_state(dict(ok, nan=2)), 'nan')
        self.assertEqual(handlers.trace_state({'min': [0, 0, 0, 0], 'max': [1, 1, 1, 0]}), 'transparent')
        nodes = [{'path': '/o', 'type': 'nullTOP', 'inputs': ['/lv'], 'stats': black},
                 {'path': '/lv', 'type': 'levelTOP', 'inputs': ['/n'], 'stats': black, 'pars': {'opacity': 0},
                  'bypass': True},
                 {'path': '/n', 'type': 'noiseTOP', 'inputs': [], 'stats': ok}]
        m = handlers.trace_marks(nodes)
        self.assertEqual(list(m), ['/lv'])
        self.assertEqual(m['/lv'][0], 'dropped here')
        self.assertIn('opacity 0', m['/lv'][1])
        self.assertIn('bypass', m['/lv'][1])
        nodes = [{'path': '/add', 'type': 'addTOP', 'inputs': ['/lv', '/n'], 'stats': ok},
                 {'path': '/lv', 'type': 'levelTOP', 'inputs': [], 'stats': neg, 'negativeFloat': {'contrast': 2.0}},
                 {'path': '/n', 'type': 'noiseTOP', 'inputs': ['/x'], 'stats': black},
                 {'path': '/x', 'type': 'moviefileinTOP', 'inputs': [], 'unsampled': 'never cooked'}]
        m = handlers.trace_marks(nodes)
        self.assertEqual(m['/add'][0], 'dropped here')
        self.assertEqual(m['/lv'][0], 'negative values start here')
        self.assertEqual(m['/n'][0], 'dropped here?')
        self.assertIn('never cooked', ' '.join(m['/n'][1]))
        # QC 26 Oct (live 31550): a failed GLSL TOP shows TD's magenta error pattern (stats 'ok') and was not marked
        magenta = {'min': [0, 0, 0, 1], 'max': [0.698, 0, 0.698, 1], 'mean': [0.349, 0, 0.349, 1]}
        nodes = [{'path': '/out', 'type': 'outTOP', 'inputs': ['/g'], 'stats': magenta},
                 {'path': '/g', 'type': 'glslTOP', 'inputs': [], 'stats': magenta,
                  'warnings': 'The GLSL Shader has compile errors',
                  'compile': "ERROR: /g/shader:3: 'bogus' : undeclared identifier"}]
        m = handlers.trace_marks(nodes)
        self.assertEqual(list(m), ['/g'], 'only the broken node, not every op downstream of it')
        self.assertEqual(m['/g'][0], 'broken here')
        self.assertIn('bogus', ' '.join(m['/g'][1]))

    def test_sidecar_and_ours(self):
        self.assertEqual(handlers.sidecar_name('JazibTD_home.3.toe', '/project1'), 'JazibTD_home.project1.jtdnet')
        self.assertEqual(handlers.sidecar_name('show.toe', '/project1/show'), 'show.project1_show.jtdnet')
        self.assertEqual(handlers.sidecar_name('', '/'), 'project.root.jtdnet')
        self.assertTrue(handlers.is_our_net_text('{"format":"jtd-net","v":1}\n'))
        self.assertFalse(handlers.is_our_net_text('{"format":"other"}'))
        self.assertFalse(handlers.is_our_net_text('hello'))
        self.assertFalse(handlers.is_our_net_text(''))

    def test_bare_script_error(self):
        self.assertEqual(handlers.bare_script_error('Error: boom (/p/x)', '/p/x'), 'boom')
        self.assertEqual(handlers.bare_script_error('boom', '/p/x'), 'boom')

    def test_write_text_atomic(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, 'a.jtdnet')
        handlers.write_text_atomic(f, 'x\n')
        handlers.write_text_atomic(f, 'y\n')
        with open(f) as fh:
            self.assertEqual(fh.read(), 'y\n')
        self.assertEqual(os.listdir(d), ['a.jtdnet'])

    def test_registered_and_read_only(self):
        for c in ('health_sample', 'health_probe', 'script_errors_recheck', 'trace', 'save_hook'):
            self.assertIn(c, handlers.COMMANDS)
        for c in ('health_sample', 'health_probe', 'script_errors_recheck', 'trace'):
            self.assertNotIn(c, handlers.MUTATING)
        self.assertIn('save_hook', handlers.MUTATING)


class CookOp(OP):
    def __init__(self, path, cooks=1, **kw):
        OP.__init__(self, path, **kw)
        self.totalCooks, self.cookTime, self.bypass = cooks, 0.1, False
        self.cooked = 0

    def cook(self, force=False):
        self.cooked += 1
        if getattr(self, 'live', False):
            self.totalCooks += 1

    def scriptErrors(self, recurse=False):
        return getattr(self, 'serr', '')


class AtlasTD(unittest.TestCase):
    def setUp(self):
        OPS.clear()
        self.root = CookOp('/p', optype='baseCOMP', family='COMP', n_in=0)
        self.root.isCOMP = True
        self.noise = CookOp('/p/noise1', cooks=5)
        self.noise.live = True
        self.const = CookOp('/p/const1', optype='constantTOP', cooks=2)
        self.never = CookOp('/p/n0', cooks=0)
        self.out = CookOp('/p/mov', optype='moviefileoutTOP', cooks=3, pars=[{'name': 'record', 'val': False}])
        self.fb = CookOp('/p/fb', optype='feedbackTOP', pars=[{'name': 'reset', 'val': False},
                                                             {'name': 'resetpulse', 'pulse': True}])
        self.mcp = CookOp('/jazib_mcp', optype='baseCOMP', family='COMP')
        self.root.children = [self.noise, self.const, self.never, self.out, self.fb, self.mcp]
        for o in [self.root] + self.root.children:
            OPS[o.path] = o

    def test_sample_counts_only_and_full(self):
        r = handlers.cmd_health_sample('/p', counts_only=True)
        self.assertEqual(r['counts'], {'/p/noise1': 5, '/p/const1': 2, '/p/n0': 0, '/p/mov': 3, '/p/fb': 1})
        self.assertEqual(r['frame'], 10)
        self.assertEqual(self.noise.cooked, 0, 'counts_only cooks nothing')
        self.noise._pars.append(FakePar(self.noise, 'tz', 0))
        self.noise.par = FakeParCollection(self.noise._pars)
        self.noise.par['tz'].mode, self.noise.par['tz'].expr = ParMode.EXPRESSION, 'absTime.seconds * 2'
        self.fb.serr = 'Error: Traceback\nNameError: q (/p/fb)'
        self.root.serr = self.fb.serr  # recursive read sees it
        full = handlers.cmd_health_sample('/p')
        by = {n['path']: n for n in full['nodes']}
        self.assertNotIn('/jazib_mcp', by)
        self.assertEqual(by['/p/fb']['feedback'], {'target': '', 'reset': False})
        self.assertTrue(by['/p/fb']['history'])
        self.assertEqual(by['/p/mov']['record'], False)
        self.assertEqual(full['clockReads'], [['/p/noise1', 'tz', 'absTime.seconds']])
        self.assertIn('/p/fb', full['scriptErrors'])
        with self.assertRaises(ValueError):
            handlers.cmd_health_sample('/p/noise1')

    def test_probe(self):
        r = handlers.cmd_health_probe(['/p/noise1', '/p/const1', '/p/n0', '/p/mov', '/p', '/p/gone'])
        self.assertEqual(r['cooked'], ['/p/noise1'])
        self.assertEqual(r['quiet'], ['/p/const1'])
        self.assertEqual(r['never'], ['/p/n0'])
        self.assertEqual(r['skipped'], ['/p/mov', '/p'])
        self.assertEqual(r['missing'], ['/p/gone'])
        self.assertEqual(self.out.cooked, 0, 'outputs are never asked to cook')
        self.assertEqual(self.never.cooked, 0)

    def test_recheck_gated_without_api(self):
        r = handlers.cmd_script_errors_recheck('clear', paths=['/p/fb'])
        self.assertEqual(r['available'], False)

    def test_trace_without_numpy_image(self):
        self.noise.numpyArray = lambda delayed=False: None
        self.noise.width, self.noise.height = 4, 4
        r = handlers.cmd_trace('/p/noise1')
        self.assertEqual(r['root'], '/p/noise1')
        self.assertEqual(r['nodes'][0]['state'], 'unsampled')
        self.assertIn('numpyArray returned None', r['nodes'][0]['unsampled'])
        with self.assertRaises(ValueError):
            handlers.cmd_trace('/p')

    def test_save_hook_status_and_write_now(self):
        d = tempfile.mkdtemp()
        old = handlers.project
        handlers.project = types.SimpleNamespace(name='show.2.toe', folder=d, realTime=True)
        try:
            OPS['/jazib_mcp'] = self.mcp
            self.mcp.op = lambda name: None
            r = handlers.cmd_save_hook(path='/p', write_now=True)
            self.assertFalse(r['installed'])
            self.assertEqual(r['file'], os.path.join(d, 'show.p.jtdnet'))
            self.assertEqual(r['wrote']['file'], r['file'])
            with open(r['file']) as fh:
                self.assertTrue(handlers.is_our_net_text(fh.readline()))
            with open(os.path.join(d, 'other.p.jtdnet'), 'w') as fh:
                fh.write('not ours\n')
            handlers.project.name = 'other.toe'
            r2 = handlers.cmd_save_hook(path='/p', write_now=True)
            self.assertIn('not a jtd-net text', r2['wrote']['error'])
            with open(os.path.join(d, 'other.p.jtdnet')) as fh:
                self.assertEqual(fh.read(), 'not ours\n')
        finally:
            handlers.project = old


if __name__ == '__main__':
    unittest.main()


# ---------------------------------------------------------------- TD -> Resolume (td_publish, td_osc_learn)

class LearnCell(object):
    """A Table DAT cell: like TD, whatever is assigned reads back as a string."""
    def __init__(self, v):
        self.val = v

    @property
    def val(self):
        return self._v

    @val.setter
    def val(self, v):
        self._v = str(v)


class FakeTable(object):
    """Just enough of a Table DAT for the OSC learn callback: rows by first-column name, cells by [row, col]."""
    def __init__(self, header):
        self._rows = [[LearnCell(h) for h in header]]

    @property
    def numRows(self):
        return len(self._rows)

    def rows(self):
        return self._rows

    def row(self, name):
        for r in self._rows[1:]:
            if r[0].val == name:
                return r
        return None

    def appendRow(self, vals):
        self._rows.append([LearnCell(v) for v in vals])

    def _cell(self, key):
        r, c = key
        ci = [h.val for h in self._rows[0]].index(c)
        return self.row(r)[ci]

    def __getitem__(self, key):
        return self._cell(key)

    def __setitem__(self, key, v):
        self._cell(key).val = str(v)


class Resolume(unittest.TestCase):
    def test_res(self):
        self.assertIsNone(handlers.check_res(None))
        self.assertEqual(handlers.check_res((1080, 1920)), [1080, 1920])
        self.assertEqual(handlers.check_res([1080.0, 1920]), [1080, 1920])
        for bad in ([1080], [8, 100], [100, 20000], ['a', 1], [True, 100], [10.5, 100], 1080):
            with self.assertRaises(ValueError, msg=bad):
                handlers.check_res(bad)

    def test_ndi_name(self):
        self.assertEqual(handlers.ndi_source_name('Jazibs-MacBook-Pro.local', 'TD_look'), 'JAZIBS-MACBOOK-PRO (TD_look)')
        self.assertEqual(handlers.ndi_source_name('', 'x'), 'HOST (x)')

    def test_alpha_steps(self):
        A = handlers.alpha_step
        self.assertIsNone(A('premultiplied', 'premultiplied'))
        self.assertIsNone(A('straight', 'straight'))
        self.assertEqual(A('premultiplied', 'straight'), {'name': 'alpha', 'type': 'levelTOP',
                                                          'pars': {'premultrgbbyalpha': True}, 'does': 'premultiply'})
        self.assertEqual(A('straight', 'premultiplied')['shader'], 'unpremult')
        self.assertEqual(A('none', 'premultiplied')['shader'], 'opaque')
        self.assertEqual(A('none', 'straight')['shader'], 'opaque_straight')
        with self.assertRaises(ValueError):
            A('pre', 'premultiplied')
        with self.assertRaises(ValueError):
            A('none', 'none')

    def test_shaders_follow_td_glsl_rules(self):
        for k, src in handlers.GLSL_ALPHA.items():
            src.encode('ascii')
            self.assertNotIn('#version', src, k)
            self.assertIn('sTD2DInputs[0]', src)
            self.assertIn('TDOutputSwizzle', src)
        self.assertIn('max(c.a, 1e-4)', handlers.GLSL_ALPHA['unpremult'])

    def test_plan_default_syphon(self):
        p = handlers.plan_publish('look1', '/project1/look1/out1')
        self.assertEqual(p['comp'], 'publish_look1')
        self.assertEqual(p['sender'], 'TD_look1')
        self.assertEqual([c['name'] for c in p['chain']], ['src', 'out'], 'premultiplied in and out: no step, no fit')
        self.assertEqual(p['chain'][0]['pars'], {'top': '/project1/look1/out1'})
        self.assertEqual(p['senders'], [{'kind': 'syphon', 'name': 'syphon_out', 'type': 'syphonspoutoutTOP',
                                         'pars': {'sendername': 'TD_look1'}}])
        self.assertEqual(p['arena'], {'syphon': 'TD_look1'})
        self.assertEqual(p['config'], {'source': '/project1/look1/out1', 'transport': 'syphon',
                                       'alpha': 'premultiplied', 'source_alpha': 'premultiplied', 'res': None,
                                       'sender': 'TD_look1'})

    def test_plan_both_fit_none(self):
        p = handlers.plan_publish('x', '/a/b', 'both', 'none', 'premultiplied', [1080, 1920], 'Show Look',
                                  'mac.local', cook_rate=30)
        self.assertEqual([c['name'] for c in p['chain']], ['src', 'fit', 'alpha', 'out'])
        self.assertEqual(p['chain'][1]['pars']['resolutionw'], 1080)
        self.assertEqual(p['chain'][1]['pars']['outputresolution'], {'menu': 'custom'})
        ndi = [s for s in p['senders'] if s['kind'] == 'ndi'][0]
        self.assertEqual(ndi['pars'], {'name': 'Show Look', 'fps': 30, 'lowperformancebehavior': {'menu': 'skipframes'},
                                       'outputpixelformat': {'menu': 'fixed8'}, 'includealpha': False})
        self.assertEqual(p['arena'], {'syphon': 'Show Look', 'ndi': 'MAC (Show Look)'})
        p2 = handlers.plan_publish('x', '/a/b', 'ndi', cook_rate=None)
        self.assertTrue(p2['senders'][0]['pars']['includealpha'])
        self.assertEqual(p2['senders'][0]['pars']['fps'], 60)

    def test_plan_gates_and_errors(self):
        p = handlers.plan_publish('x', '/a', 'both', available=('ndi',))
        self.assertEqual([s['kind'] for s in p['senders']], ['ndi'])
        self.assertEqual(len(p['notes']), 1)
        n = handlers.plan_publish('x', '/a', 'syphon', available=())
        self.assertEqual(n['available'], False)
        self.assertIn('syphonspoutoutTOP', n['note'])
        for args in (('bad name', '/a'), ('1x', '/a'), ('x', 'a'), ('x', '/a', 'spout')):
            with self.assertRaises(ValueError, msg=args):
                handlers.plan_publish(*args)
        with self.assertRaises(ValueError):
            handlers.plan_publish('x', '/a', sender='bad/name')

    def test_conflicts(self):
        cfg = handlers.plan_publish('x', '/a', res=[100, 200])['config']
        given = {'source': None, 'transport': None, 'alpha': None, 'source_alpha': None, 'res': None, 'sender': None}
        self.assertEqual(handlers.publish_conflicts(cfg, given), [])
        self.assertEqual(handlers.publish_conflicts(cfg, dict(given, res=[100, 200], source='/a')), [])
        self.assertEqual(handlers.publish_conflicts(cfg, dict(given, res=[1, 2], transport='ndi')), ['res', 'transport'])

    def test_reply(self):
        p = handlers.plan_publish('x', '/a', 'both', host='m')
        off = handlers.publish_reply('/project1/publish_x', p['config'], p['arena'], False, True, 60)
        self.assertFalse(off['active'])
        self.assertIn('inactive', off['next'])
        self.assertNotIn('resolume_723', off)
        self.assertEqual(off['pick_in_arena']['syphon']['sendername'], 'TD_x')
        self.assertIn('M (TD_x)', off['pick_in_arena']['ndi']['arena'])
        on = handlers.publish_reply('/project1/publish_x', p['config'], p['arena'], True, False, 60)
        self.assertTrue(any('resolume_get_composition' in t for t in on['resolume_723']))
        self.assertIn('Premultiplied', on['alpha'])
        json.dumps(on)

    def test_dup_senders(self):
        rows = [{'kind': 'syphon', 'sender': 'A'}, {'kind': 'syphon', 'sender': 'A'}, {'kind': 'ndi', 'sender': 'A'}]
        self.assertEqual(handlers.dup_senders(rows), ['syphon "A" x2'])

    def test_mutating(self):
        self.assertIn('publish', handlers.MUTATING)
        self.assertIn('osc_learn', handlers.MUTATING)
        self.assertNotIn('publish_status', handlers.MUTATING)
        for c in ('publish', 'publish_status', 'osc_learn'):
            self.assertIn(c, handlers.COMMANDS)

    def test_publish_bad_name_before_td(self):
        with self.assertRaises(ValueError):
            handlers.cmd_publish('bad name', '/a')

    def test_osc_export_name(self):
        self.assertEqual(handlers.osc_export_name('7.23.2 (51094)'), 'osc_addresses_7.23.2_51094.json')
        self.assertEqual(handlers.osc_export_name(None), 'osc_addresses_arena.json')
        self.assertEqual(handlers.osc_export_name('../..'), 'osc_addresses_arena.json')

    def test_osc_learn_args_checked_before_td(self):
        for kw in ({'action': 'listen'}, {'action': 'stop'}, {'action': 'start', 'seconds': 5},
                   {'action': 'start', 'seconds': 9999, 'file': '/tmp/x.json'}, {'action': 'export', 'file': 'x.json'}):
            with self.assertRaises(ValueError, msg=kw):
                handlers.cmd_osc_learn(**kw)

    def test_osc_callback_and_export(self):
        t = FakeTable(handlers.OSC_LEARN_HEADER)
        dat = types.SimpleNamespace(parent=lambda: types.SimpleNamespace(op=lambda n: t if n == 'learned' else None))
        ns = {}
        handlers.OSC_LEARN_CB.encode('ascii')
        exec(compile(handlers.OSC_LEARN_CB, 'osc_cb', 'exec'), ns)
        f = ns['onReceiveOSC']
        f(dat, 1, '', b'', 0, '/composition/layers/1/video/opacity', [0.5], None)
        f(dat, 2, '', b'', 0, '/composition/layers/1/video/opacity', [0.75], None)
        f(dat, 3, '', b'', 0, '/composition/tempocontroller/tempo', [0.208], None)
        self.assertEqual(t.numRows, 3)
        self.assertEqual(t['/composition/layers/1/video/opacity', 'count'].val, '2')
        self.assertEqual(t['/composition/layers/1/video/opacity', 'args'].val, '0.75')
        rows = [[c.val for c in r] for r in t.rows()]
        e = handlers.learned_export(rows, {'arena_build': '7.23.2', 'port': 7001})
        self.assertEqual(e['format'], 'jtd-osc-learn')
        self.assertEqual(e['count'], 2)
        self.assertEqual(e['messages'], 3)
        self.assertEqual([a['address'] for a in e['addresses']],
                         ['/composition/layers/1/video/opacity', '/composition/tempocontroller/tempo'])
        self.assertEqual(e['arena_build'], '7.23.2')
        json.dumps(e)
        self.assertEqual(handlers.learned_top(rows, 1), [['/composition/layers/1/video/opacity', 2]])
        compile(handlers.OSC_LEARN_EXEC, 'exec', 'exec')


class SafeDestroy(unittest.TestCase):
    """T-70: a panel shown in an open window is never destroyed in the same frame."""
    def test_inside(self):
        self.assertTrue(handlers._inside('/a/b', '/a/b'))
        self.assertTrue(handlers._inside('/a/b/c', '/a/b'))
        self.assertFalse(handlers._inside('/a/bc', '/a/b'))


class Autosave(unittest.TestCase):
    """T-71: the in-TD autosave timer."""
    def test_due(self):
        self.assertFalse(handlers.autosave_due(100.0, None, 10))      # first tick only arms
        self.assertFalse(handlers.autosave_due(100.0, 50.0, 10))
        self.assertTrue(handlers.autosave_due(700.0, 50.0, 10))
        self.assertFalse(handlers.autosave_due(10 ** 6, 0.0, 0))      # off


class McpBeat(unittest.TestCase):
    """T-95: the second heartbeat, written from the WebSocket callbacks (not frame callbacks)."""
    def test_record_tracks_frame_changes(self):
        prev = {}
        a = handlers.mcp_beat_record(100.0, 500, 'ws', 7, prev)
        self.assertEqual((a['frame'], a['frame_changed_at'], a['pid'], a['src']), (500, 100.0, 7, 'ws'))
        b = handlers.mcp_beat_record(160.0, 500, 'ws', 7, prev)   # frozen frame clock
        self.assertEqual(b['frame_changed_at'], 100.0)
        c = handlers.mcp_beat_record(161.0, 501, 'tick', 7, prev)
        self.assertEqual(c['frame_changed_at'], 161.0)

    def test_writes_file_rate_limited(self):
        d = tempfile.mkdtemp()
        old = os.environ.get('JTD_STATE_DIR')
        os.environ['JTD_STATE_DIR'] = d
        try:
            handlers._MCP_BEAT.update(last=0.0, frame=None, frame_wall=None)
            p = handlers.mcp_beat('ws')
            self.assertEqual(p, os.path.join(d, 'heartbeat_mcp.json'))
            with open(p) as f:
                rec = json.load(f)
            self.assertEqual(rec['pid'], os.getpid())
            self.assertEqual(rec['src'], 'ws')
            self.assertIsNone(handlers.mcp_beat('ws'))  # within MCP_BEAT_MIN_S
        finally:
            if old is None:
                os.environ.pop('JTD_STATE_DIR', None)
            else:
                os.environ['JTD_STATE_DIR'] = old


class NextSaveName(unittest.TestCase):
    def test_skips_existing(self):
        ls = ['JazibTD_home.toe', 'JazibTD_home.2.toe', 'JazibTD_home.3.toe', 'CrashAutoSave.JazibTD_home.2.toe']
        self.assertEqual(handlers.next_save_name('JazibTD_home.2.toe', ls), 'JazibTD_home.4.toe')
        self.assertEqual(handlers.next_save_name('New.toe', []), 'New.1.toe')


class RotateSaves(unittest.TestCase):
    def test_keeps_newest(self):
        ls = ['P.toe'] + ['P.%d.toe' % i for i in range(1, 15)] + ['CrashAutoSave.P.3.toe', 'Q.2.toe']
        old = handlers.saves_to_rotate('P.14.toe', ls, keep=10)
        self.assertEqual(old, ['P.1.toe', 'P.2.toe', 'P.3.toe', 'P.4.toe'])


class ReadbackHazard(unittest.TestCase):
    """T-74: numpyArray in the same script as TOP changes crashed TD."""
    def test_flags(self):
        self.assertEqual(handlers.readback_hazard("a = op('x').numpyArray()"), [])
        self.assertIn('create(', handlers.readback_hazard("t = c.create(textTOP); a = t.numpyArray()"))
        self.assertIn('fontsize', handlers.readback_hazard("t.par.fontsizex = 24; t.numpyArray(delayed=False)"))
        self.assertEqual(handlers.readback_hazard("t.par.fontsizex=2; t.numpyArray() # allow-readback"), [])


class EvalTextSizeHazard(unittest.TestCase):
    def test_flags(self):
        self.assertIn('create(', handlers.readback_hazard("t=c.create(textTOP,'m'); t.par.font='X'; t.evalTextSize('a')"))
        self.assertEqual(handlers.readback_hazard("op('/a/t').evalTextSize('a')"), [])


class ScratchRoute(unittest.TestCase):
    """T-83: scratch TD rules (which code to try on the scratch TD) and the exec guard there."""
    def setUp(self):
        self._env = os.environ.pop('JTD_SCRATCH', None)

    def tearDown(self):
        os.environ.pop('JTD_SCRATCH', None)
        if self._env is not None:
            os.environ['JTD_SCRATCH'] = self._env

    def test_hint_patterns(self):
        self.assertEqual(handlers.scratch_hint('1+1'), [])
        self.assertEqual(handlers.scratch_hint(None), [])
        self.assertTrue(any('T-76' in h for h in handlers.scratch_hint("op('/t').evalTextSize('a')")))
        self.assertTrue(any('T-64' in h for h in handlers.scratch_hint('project.cookRate = 30')))
        self.assertTrue(any('T-70' in h for h in handlers.scratch_hint("op('/p/x').destroy()")))
        self.assertTrue(any('T-79' in h for h in handlers.scratch_hint("c.create(windowCOMP, 'w')")))

    def test_main_refusal_points_to_scratch(self):
        out, send = collect()
        code = "t = op('/').create(textTOP, 'm'); t.par.font = 'X'; t.evalTextSize('a')"
        handlers.dispatch(json.dumps({'id': 81, 'cmd': 'exec', 'args': {'code': code}}), send)
        self.assertFalse(out[0]['ok'])
        self.assertIn("target:'scratch'", out[0]['error'])

    def test_main_note_on_risky_code(self):
        out, send = collect()
        handlers.dispatch(json.dumps({'id': 82, 'cmd': 'exec', 'args': {'code': "x = 'cookRate = 1'\n2"}}), send)
        r = out[0]['result']
        self.assertEqual(r['result'], 2)
        self.assertTrue(any("target:'scratch'" in n for n in r['notes']))

    def test_scratch_waives_guard_with_note(self):
        os.environ['JTD_SCRATCH'] = '1'
        self.assertTrue(handlers.is_scratch())
        out, send = collect()
        code = "s = 'create( .par.font evalTextSize('\n3"
        handlers.dispatch(json.dumps({'id': 83, 'cmd': 'exec', 'args': {'code': code}}), send)
        r = out[0]['result']
        self.assertTrue(out[0]['ok'])
        self.assertEqual((r['result'], r['scratch']), (3, True))
        self.assertTrue(any('guard waived' in n for n in r['notes']))

    def test_autosave_default_env(self):
        old = os.environ.get('JTD_AUTOSAVE_MIN')
        try:
            os.environ['JTD_AUTOSAVE_MIN'] = '0'
            self.assertEqual(handlers._autosave_default(), 0.0)
            os.environ['JTD_AUTOSAVE_MIN'] = 'x'
            self.assertEqual(handlers._autosave_default(), 5.0)
            del os.environ['JTD_AUTOSAVE_MIN']
            self.assertEqual(handlers._autosave_default(), 5.0)
        finally:
            if old is not None:
                os.environ['JTD_AUTOSAVE_MIN'] = old


class CrashGuard(unittest.TestCase):
    """td_exec consults td/crashdb.py + logs/crash_patterns.json (T-64, T-70, T-74, T-76) before running code."""
    def setUp(self):
        self._dir, self._pats = handlers.CRASHDB_DIR, handlers.CRASH_PATTERNS
        handlers.CRASHDB_DIR = TD_DIR
        handlers.CRASH_PATTERNS = os.path.join(os.path.dirname(TD_DIR), 'logs', 'crash_patterns.json')
        self._ow = handlers.open_windows

    def tearDown(self):
        handlers.CRASHDB_DIR, handlers.CRASH_PATTERNS = self._dir, self._pats
        handlers.open_windows = self._ow

    def test_refuses_readback_after_change(self):
        for code in ("t = c.create(textTOP); a = t.numpyArray()", "t.par.fontsizex = 24; t.numpyArray(delayed=False)",
                     "t=c.create(textTOP,'m'); t.par.font='X'; t.evalTextSize('a')"):
            with self.assertRaises(ValueError) as cm:
                handlers.cmd_exec(code)
            self.assertIn('crash guard: refused', str(cm.exception))
            self.assertIn('frames >= 2', str(cm.exception))
        with self.assertRaises(ValueError) as cm:
            handlers.cmd_exec('project.cookRate = 30')
        self.assertIn('T-64', str(cm.exception))

    def test_allowed_with_frames_or_optout(self):
        p = handlers.cmd_exec("t = None\nif t: t.par.text = 'a'; t.numpyArray()", frames=2)
        self.assertIsInstance(p, handlers.Pending)
        # T-182: the readback opt-out was removed (it froze scratch); the comment no longer passes the guard
        with self.assertRaises(ValueError):
            handlers.cmd_exec("t = None\nif t: t.par.fontsizex = 2; t.numpyArray()  # allow-readback\n7")
        self.assertEqual(handlers.cmd_exec("a = 1\na")['result'], 1)

    def test_destroy_refused_only_with_open_windows(self):
        code = "x = None\nif x: x.destroy()\n3"
        handlers.open_windows = lambda: []
        self.assertEqual(handlers.cmd_exec(code)['result'], 3)
        handlers.open_windows = lambda: [(OP('/project1/w'), None)]
        with self.assertRaises(ValueError) as cm:
            handlers.cmd_exec(code)
        self.assertIn('T-70', str(cm.exception))
        self.assertEqual(handlers.cmd_exec(code + '  # allow-destroy')['result'], 3)

    def test_broken_pattern_file_keeps_fallback(self):
        d = tempfile.mkdtemp()
        try:
            handlers.CRASH_PATTERNS = os.path.join(d, 'missing.json')
            with self.assertRaises(ValueError):
                handlers.cmd_exec("t = c.create(textTOP); a = t.numpyArray()")
            r = handlers.cmd_exec('5')
            self.assertTrue(any('pattern file problem' in n for n in r['notes']))
        finally:
            os.rmdir(d)

    def test_missing_crashdb_never_blocks(self):
        handlers.CRASHDB_DIR = tempfile.gettempdir()
        r = handlers.cmd_exec('6')
        self.assertEqual(r['result'], 6)
        self.assertTrue(any('crash guard unavailable' in n for n in r['notes']))


class FaultHandler(unittest.TestCase):
    def test_install_idempotent_one_header(self):
        import faulthandler
        d = tempfile.mkdtemp()
        st = handlers._fh_state()
        saved = (st.file, st.pid, st.path, st.since)
        try:
            r1 = handlers.install_faulthandler(log_dir=d)
            r2 = handlers.install_faulthandler(log_dir=d)
            self.assertTrue(r1['new'])
            self.assertFalse(r2['new'])
            self.assertTrue(faulthandler.is_enabled())
            self.assertTrue(handlers.faulthandler_status()['ours'])
            with open(os.path.join(d, handlers.FAULT_LOG)) as f:
                lines = f.read().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertRegex(lines[0], r'^=== jazib-td faulthandler session pid=\d+ build=2025\.31550 project=t\.toe '
                                       r'started=\S+ python=3\.\d+\S* ===$')
            st.pid = -1   # a new TD process: new header, same file (append)
            self.assertTrue(handlers.install_faulthandler(log_dir=d)['new'])
            with open(os.path.join(d, handlers.FAULT_LOG)) as f:
                self.assertEqual(len(f.read().splitlines()), 2)
        finally:
            faulthandler.disable()
            if st.file is not None and st.file is not saved[0]:
                st.file.close()
            st.file, st.pid, st.path, st.since = saved
            for n in os.listdir(d):
                os.remove(os.path.join(d, n))
            os.rmdir(d)

    def test_rotation(self):
        import faulthandler
        d = tempfile.mkdtemp()
        st = handlers._fh_state()
        saved = (st.file, st.pid, st.path, st.since)
        try:
            with open(os.path.join(d, handlers.FAULT_LOG), 'w') as f:
                f.write('x' * (handlers.FAULT_LOG_MAX + 1))
            handlers.install_faulthandler(log_dir=d, force=True)
            self.assertTrue(os.path.isfile(os.path.join(d, handlers.FAULT_LOG + '.1')))
            self.assertLess(os.path.getsize(os.path.join(d, handlers.FAULT_LOG)), 1000)
        finally:
            faulthandler.disable()
            if st.file is not None and st.file is not saved[0]:
                st.file.close()
            st.file, st.pid, st.path, st.since = saved
            for n in os.listdir(d):
                os.remove(os.path.join(d, n))
            os.rmdir(d)

    def test_not_in_td_under_tests(self):
        self.assertFalse(handlers._in_td())


class StageGridUnwired(unittest.TestCase):
    """T-98: unwired ops in a stage flow left to right in rows, not one tall column."""
    def test_grid(self):
        names = ['a%d' % i for i in range(8)]
        sl = handlers.stage_slots(names, [])
        self.assertEqual(sl['a0'], (0, 0))
        self.assertEqual(sl['a5'], (5, 0))
        self.assertEqual(sl['a6'], (0, 1))


class StageGridMixed(unittest.TestCase):
    def test_wired_then_grid(self):
        sl = handlers.stage_slots(['a', 'b', 'x', 'y', 'z'], [('a', 'b', 0)])
        self.assertEqual(sl['a'][1], sl['b'][1])          # wired pair on one lane
        self.assertLess(sl['a'][0], sl['b'][0])
        self.assertEqual([sl[n] for n in 'xyz'], [(0, 1), (1, 1), (2, 1)])
