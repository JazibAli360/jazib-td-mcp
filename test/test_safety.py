"""Offline tests for td/safety.py (lose nothing: pre-risk save + per-COMP .tox checkpoints) and its hook in
td/handlers.py dispatch. No TouchDesigner: a fake op tree whose COMP.save writes a file and parent.loadTox reads it.
Run: python3 -I -m unittest discover -s test -p 'test_*.py'"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TD_DIR = os.path.join(os.path.dirname(HERE), 'td')
sys.path.insert(0, HERE)
import test_handlers as TH  # noqa: E402  (stub td module + handlers)

handlers = TH.handlers


def load():
    spec = importlib.util.spec_from_file_location('jazib_safety_test', os.path.join(TD_DIR, 'safety.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


S = load()


# ---------------------------------------------------------------- fake TD

class Conn(object):
    def __init__(self, owner, index, is_input):
        self.owner, self.index, self.is_input, self.connections = owner, index, is_input, []

    def connect(self, other):
        src, dst = (other, self) if self.is_input else (self, other)
        for c in dst.connections:
            c.connections = [x for x in c.connections if x is not dst]
        dst.connections = [src]
        src.connections.append(dst)


class Par(object):
    def __init__(self, val=''):
        self.val = val
        self.pulsed = 0

    def eval(self):
        return self.val

    def pulse(self):
        self.pulsed += 1


class Pars(object):
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, Par(v))

    def __getitem__(self, k):
        return getattr(self, k, None)


class Tree(object):
    def __init__(self):
        self.ops = {}
        self.next_id = 1
        self.destroyed = []

    def get(self, path):
        return self.ops.get(path)


T = Tree()


class Node(object):
    def __init__(self, parent, name, optype='baseCOMP', n_in=1, n_out=1, comp=None):
        self._parent = parent
        self._name = name
        self.OPType = optype
        self.isCOMP = optype.endswith('COMP') if comp is None else comp
        self.id = T.next_id
        T.next_id += 1
        self.kids = []
        self.inputConnectors = [Conn(self, i, True) for i in range(n_in)]
        self.outputConnectors = [Conn(self, i, False) for i in range(n_out)]
        self.par = Pars(externaltox='', enableexternaltox=True, winopen=None)
        self.nodeX, self.nodeY, self.color, self.comment, self.allowCooking = 0, 0, (0.5, 0.5, 0.5), '', True
        self.storage = {}
        self.err = ''
        self.valid = True
        self.saves = []
        if parent is not None:
            parent.kids.append(self)
        T.ops[self.path] = self

    @property
    def path(self):
        if self._parent is None:
            return '/'
        return self._parent.path.rstrip('/') + '/' + self._name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, v):
        old = self.path
        subs = [(o.path, o) for o in [self] + self.findChildren()]
        self._name = v
        for p, o in subs:
            T.ops.pop(p, None)
        for _p, o in subs:
            T.ops[o.path] = o
        assert old not in T.ops or T.ops[old] is not self

    def parent(self):
        return self._parent

    @property
    def children(self):
        return list(self.kids)

    def findChildren(self, **kw):
        out = []
        for k in self.kids:
            out.append(k)
            out += k.findChildren()
        return out

    def op(self, rel):
        return T.ops.get(self.path.rstrip('/') + '/' + rel)

    def fetch(self, k, d=None, search=False):
        return self.storage.get(k, d)

    def store(self, k, v):
        self.storage[k] = v

    def errors(self):
        return self.err

    def scriptErrors(self):
        return ''

    def destroy(self):
        for o in [self] + self.findChildren():
            T.ops.pop(o.path, None)
            o.valid = False
        self._parent.kids.remove(self)
        T.destroyed.append(self.path)

    def save(self, file):  # a "tox": JSON of the subtree (names, types, storage, par externaltox)
        def rec(o):
            return {'name': o.name, 'type': o.OPType, 'storage': o.storage, 'ext': o.par.externaltox.val,
                    'kids': [rec(k) for k in o.kids]}
        with open(file, 'w') as f:
            json.dump(rec(self), f)
        self.saves.append(file)

    def loadTox(self, file):
        with open(file) as f:
            d = json.load(f)

        def mk(parent, r):
            name = r['name']
            n = 1
            while parent.op(name) is not None:
                name = '{}{}'.format(r['name'], n)
                n += 1
            o = Node(parent, name, r['type'])
            o.storage = dict(r['storage'])
            o.par.externaltox.val = r['ext']
            for k in r['kids']:
                mk(o, k)
            return o
        return mk(self, d)


ROOT = Node(None, '')
T.ops['/'] = ROOT


def reset():
    T.ops.clear()
    T.destroyed[:] = []
    global ROOT
    ROOT = Node(None, '')
    T.ops = {'/': ROOT}
    return ROOT


class Proj(object):
    def __init__(self, folder):
        self.folder, self.name, self.realTime, self.saved = folder, 'home.3.toe', True, []


def fake_h(tmp, proj=None, windows=()):
    """A handlers-like dict for S.bind(): real pure helpers from handlers, fake TD around them."""
    h = dict(vars(handlers))
    h.update(op=T.get, project=proj or Proj(tmp), app=types.SimpleNamespace(version='2025', build='31550'),
             ui=types.SimpleNamespace(performMode=False),
             handlers_file=lambda: os.path.join(tmp, 'td', 'handlers.py'),
             open_windows=lambda: list(windows), PRESAVE={'on': True, 'min_s': 60.0, 'last': None, 'seen': None})
    calls = {'destroy': [], 'save': [], 'errors': []}

    def safe_destroy(o, frames=3):
        calls['destroy'].append(o.path)
        o.destroy()
        return {'destroyed': o.path, 'windows_closed': [], 'panes_moved': 0}

    def save_project(file=None):
        calls['save'].append(file)
        h['PRESAVE']['last'] = __import__('time').monotonic()
        return {'file': os.path.join(tmp, 'home.4.toe')}

    def cmd_errors(path, frames=2, recurse=True, cook=True):
        calls['errors'].append(path)
        root = T.get(path)

        def finish():
            return {'items': [{'path': o.path, 'errors': o.err} for o in [root] + root.findChildren() if o.err]}
        return handlers.Pending(frames, finish)

    def _op(path, what='path'):
        o = T.get(path)
        if o is None:
            raise ValueError('no operator at {}'.format(path))
        return o
    restaged = []
    h.update(safe_destroy=safe_destroy, cmd_save_project=save_project, cmd_errors=cmd_errors, _op=_op,
             _protected=lambda p: p.startswith('/jazib_mcp'), restage=lambda c: restaged.append(c.path) or {'ok': True})
    h['_calls'], h['_restaged'] = calls, restaged
    return h


# ---------------------------------------------------------------- risk (pure)

class Risk(unittest.TestCase):
    SEEN = {'noiseTOP', 'baseCOMP', 'nullTOP', 'textDAT'}

    def r(self, cmd, args, is_comp=lambda p: False):
        return S.risk_reasons(cmd, args, self.SEEN, is_comp)

    def test_exec_new_types_only(self):
        self.assertEqual(self.r('exec', {'code': "c.create(noiseTOP, 'n')"}), [])
        self.assertEqual(self.r('exec', {'code': "c.create(td.glslTOP, 'g'); c.create('nullTOP')"}),
                         ['new op type glslTOP'])
        self.assertEqual(self.r('exec', {'code': "_mk(c, syphonspoutoutTOP, 'out')"}), ['new op type syphonspoutoutTOP'])
        self.assertEqual(S.exec_types("a.create(x1TOP); b.create( 'x1TOP' ); _mk(c, moviefileinTOP, 'm')"),
                         ['x1TOP', 'moviefileinTOP'])

    def test_exec_patterns(self):
        cases = {
            "p.loadTox('/x/y.tox')": 'loads a .tox',
            "c.par.externaltox = 'a.tox'": 'loads a .tox',
            "t.par.font = 'Noto'": 'font change',
            "t.par.fontfile = '/f.ttf'": 'font change',
            "c.create(cplusplusTOP)": 'C++ op / plugin',
            "o.par.plugin = '/a.plugin'": 'C++ op / plugin',
            "ns = dict(globals()); exec(open('/r/builders/strobe.py').read(), ns); ns['build']('/project1/lab')":
                'builder build',
            "safe_destroy(op('/p/x'))": 'destroy',
            "op('/p/x').destroy()": 'destroy',
            "import importlib; importlib.reload(m)": 'module reload',
        }
        for code, why in cases.items():
            self.assertIn(why, self.r('exec', {'code': code}), code)
        for code in ("op('/p/n').par.seed = 3", "t.par.text = 'x'", "c.save('/o/x.tox')", "a = 1"):
            self.assertEqual(self.r('exec', {'code': code}), [], code)
        self.assertEqual(self.r('exec', {'code': "safe_destroy(x)  # no-presave"}), [], 'opt-out')

    def test_typed_commands(self):
        self.assertEqual(self.r('create', {'type': 'noiseTOP'}), [])
        self.assertEqual(self.r('create', {'type': 'ndioutTOP'}), ['new op type ndioutTOP'])
        self.assertIn('C++ op / plugin', self.r('create', {'type': 'cplusplusCHOP'}))
        self.assertEqual(self.r('set_pars', {'pars': {'font': 'X'}}), ['font change'])
        self.assertEqual(self.r('set_pars', {'pars': {'fontsizex': 3}}), ['font change'])
        self.assertEqual(self.r('set_pars', {'pars': {'seed': 3}}), [])
        self.assertEqual(self.r('tox_load', {}), ['loads a .tox'])
        self.assertEqual(self.r('delete', {'paths': ['/p/a', '/p/b']}, lambda p: p == '/p/b'), ['destroys COMP /p/b'])
        self.assertEqual(self.r('delete', {'paths': ['/p/a']}), [])
        self.assertEqual(self.r('reload', {}), ['module reload'])
        self.assertEqual(self.r('shadertoy', {}), ['builder shadertoy'])
        self.assertTrue(self.r('restore_checkpoint', {}))
        self.assertEqual(self.r('list', {}), [])
        for c in ('exec', 'create', 'delete', 'tox_load', 'reload', 'shadertoy', 'restore_checkpoint',
                  'debug_panel_build'):
            self.assertIn(c, handlers.PRESAVE_CMDS)
        for c in ('status', 'list', 'info', 'errors', 'save_project', 'checkpoint', 'presave'):
            self.assertNotIn(c, handlers.PRESAVE_CMDS)

    def test_skip_rules(self):
        st = {'on': True, 'min_s': 60, 'last': None}
        self.assertIsNone(S.presave_skip(st, True, False, True, 100.0))
        self.assertIn('realTime', S.presave_skip(st, False, False, True, 100.0))
        self.assertIn('perform', S.presave_skip(st, True, True, True, 100.0))
        self.assertIn('never saved', S.presave_skip(st, True, False, False, 100.0))
        self.assertIn('ago', S.presave_skip(dict(st, last=70.0), True, False, True, 100.0))
        self.assertIsNone(S.presave_skip(dict(st, last=40.0), True, False, True, 100.0))
        self.assertIn('off', S.presave_skip(dict(st, on=False), True, False, True, 100.0))


class PreRisk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        reset()
        p1 = Node(ROOT, 'project1')
        Node(p1, 'n1', 'noiseTOP')
        sysc = Node(ROOT, 'sys')
        Node(sysc, 'g', 'glslTOP')  # /sys types do not count as seen
        self.h = fake_h(self.tmp)
        S.bind(self.h)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_once_then_rate_limited_and_types_remembered(self):
        self.assertIsNone(S.pre_risk('exec', {'code': "c.create(noiseTOP)"}))
        r = S.pre_risk('exec', {'code': "c.create(glslTOP)"})
        self.assertEqual(r['reasons'], ['new op type glslTOP'])
        self.assertTrue(r['saved'].endswith('home.4.toe'))
        self.assertEqual(len(self.h['_calls']['save']), 1)
        self.assertIsNone(S.pre_risk('exec', {'code': "c.create(glslTOP)"}), 'glslTOP is seen now')
        r = S.pre_risk('tox_load', {'parent': '/project1', 'file': '/x.tox'})
        self.assertIn('ago', r['skipped'])
        self.assertEqual(len(self.h['_calls']['save']), 1, 'rate limited')
        self.h['PRESAVE']['last'] -= 61
        self.assertIn('saved', S.pre_risk('tox_load', {}))

    def test_no_project_scan_unless_something_is_created(self):
        looked = []
        self.h['op'] = lambda p: looked.append(p) or T.get(p)
        self.assertIsNone(S.pre_risk('exec', {'code': "op('/project1/n1').par.seed = 2"}))
        self.assertEqual(looked, [], 'plain execs never scan the project')
        S.pre_risk('exec', {'code': "c.create(noiseTOP)"})
        self.assertEqual(looked, ['/'])

    def test_skips_offline_render(self):
        self.h['project'].realTime = False
        r = S.pre_risk('exec', {'code': 'safe_destroy(x)'})
        self.assertIn('realTime', r['skipped'])
        self.assertEqual(self.h['_calls']['save'], [])

    def test_save_error_never_raises(self):
        def boom(file=None):
            raise RuntimeError('disk full')
        self.h['cmd_save_project'] = boom
        r = S.pre_risk('exec', {'code': 'safe_destroy(x)'})
        self.assertIn('disk full', r['error'])
        self.assertIn('ago', S.pre_risk('exec', {'code': 'safe_destroy(x)'})['skipped'], 'no retry storm')

    def test_presave_command(self):
        r = S.cmd_presave(on=False, min_s=120, check={'cmd': 'exec', 'args': {'code': "c.create(rampTOP)"}})
        self.assertEqual((r['on'], r['min_s']), (False, 120.0))
        self.assertEqual(r['check'], {'reasons': ['new op type rampTOP'], 'would_save': False})
        with self.assertRaises(ValueError):
            S.cmd_presave(min_s=5)
        self.assertEqual(self.h['_calls']['save'], [], 'check saves nothing')

    def test_dispatch_hook_adds_pre_save_and_never_blocks(self):
        sent = []
        saved = handlers.SAFETY_DIR, dict(handlers.PRESAVE), handlers.COMMANDS.get('zz_fake')
        handlers.SAFETY_DIR = TD_DIR
        handlers.COMMANDS['zz_fake'] = lambda **kw: {'ran': True}
        calls = []
        orig = handlers._pre_risk
        try:
            handlers._pre_risk = lambda cmd, args: calls.append(cmd) or {'reasons': ['x'], 'saved': '/p/a.5.toe'}
            handlers.dispatch(json.dumps({'id': 1, 'cmd': 'zz_fake', 'args': {}}), lambda t: sent.append(json.loads(t)))
            self.assertNotIn('pre_save', sent[-1]['result'], 'commands outside PRESAVE_CMDS are not checked')
            handlers.dispatch(json.dumps({'id': 2, 'cmd': 'exec', 'args': {'code': '1+1'}}),
                              lambda t: sent.append(json.loads(t)))
            self.assertEqual(sent[-1]['result']['result'], 2)
            self.assertEqual(sent[-1]['result']['pre_save']['saved'], '/p/a.5.toe')
            handlers.dispatch(json.dumps({'id': 3, 'cmd': 'exec', 'args': {'code': 'raise ValueError(7)'}}),
                              lambda t: sent.append(json.loads(t)))
            self.assertFalse(sent[-1]['ok'])
            self.assertEqual(sent[-1]['pre_save']['saved'], '/p/a.5.toe', 'error replies say where the save is')
            self.assertEqual(calls, ['exec', 'exec'])
            handlers._pre_risk = orig
            # a broken safety module only costs the save
            handlers.SAFETY_DIR = os.path.join(self.tmp, 'nope')
            handlers._SAFETY.update(mod=None, mtime=None, file=None)
            handlers.dispatch(json.dumps({'id': 4, 'cmd': 'exec', 'args': {'code': '3'}}),
                              lambda t: sent.append(json.loads(t)))
            self.assertTrue(sent[-1]['ok'])
            self.assertIn('pre-risk check failed', sent[-1]['result']['pre_save']['error'])
        finally:
            handlers._pre_risk = orig
            handlers.SAFETY_DIR = saved[0]
            handlers.PRESAVE.clear()
            handlers.PRESAVE.update(saved[1])
            handlers.COMMANDS.pop('zz_fake', None)
            handlers._SAFETY.update(mod=None, mtime=None, file=None)

    def test_pending_chain_carries_pre_save(self):
        P = handlers.Pending
        res = handlers._with_pre(P(1, lambda: P(1, lambda: {'done': 1})), {'saved': 'f'})
        step = res.finish()
        self.assertIsInstance(step, P)
        self.assertEqual(step.finish(), {'done': 1, 'pre_save': {'saved': 'f'}})

    def test_save_project_marks_time(self):
        with open(os.path.join(TD_DIR, 'handlers.py')) as f:
            self.assertIn("PRESAVE['last'] = time.monotonic()", f.read())

    def test_registered(self):
        for c in ('checkpoint', 'restore_checkpoint', 'presave'):
            self.assertIn(c, handlers.COMMANDS)
        self.assertIn('restore_checkpoint', handlers.MUTATING)
        self.assertNotIn('checkpoint', handlers.MUTATING)
        saved = handlers.SAFETY_DIR
        handlers.SAFETY_DIR = TD_DIR
        try:
            m = handlers._safety()
            self.assertIs(m.H['Pending'], handlers.Pending)
            self.assertIs(handlers._safety(), m, 'cached while unchanged')
        finally:
            handlers.SAFETY_DIR = saved
            handlers._SAFETY.update(mod=None, mtime=None, file=None)

    def test_ascii(self):
        with open(os.path.join(TD_DIR, 'safety.py'), 'rb') as f:
            f.read().decode('ascii')


# ---------------------------------------------------------------- checkpoints

class CkptPure(unittest.TestCase):
    LS = ['FX_20261026-120000.tox', 'FX_20261026-120000.json', 'FX_20261026-120000-2.tox',
          'FX_20261026-130000.tox', 'FX_x_20261026-140000.tox', '.path', 'FX_20261026-110000.tox']

    def test_list_order_and_prune(self):
        self.assertEqual([s for s, _f in S.ckpt_list(self.LS, 'FX')],
                         ['20261026-130000', '20261026-120000-2', '20261026-120000', '20261026-110000'])
        self.assertEqual(S.ckpt_prune(self.LS, 'FX', keep=2),
                         ['FX_20261026-120000.tox', 'FX_20261026-120000.json', 'FX_20261026-110000.tox'])
        self.assertEqual(S.ckpt_stamp(self.LS, 'FX', '20261026-120000'), '20261026-120000-3')
        self.assertEqual(S.ckpt_stamp(self.LS, 'FX', '20261026-150000'), '20261026-150000')
        self.assertEqual(S.ckpt_stamp(['FX_20261026-120000-4.tox'], 'FX', '20261026-120000'), '20261026-120000-5',
                         'a pruned base is not reused')

    def test_pick(self):
        items = S.ckpt_list(self.LS, 'FX')
        self.assertEqual(S.ckpt_pick(items)[0], '20261026-130000')
        self.assertEqual(S.ckpt_pick(items, 'previous')[0], '20261026-120000-2')
        self.assertEqual(S.ckpt_pick(items, 3)[0], '20261026-110000')
        self.assertEqual(S.ckpt_pick(items, '2')[0], '20261026-120000')
        self.assertEqual(S.ckpt_pick(items, '20261026-11')[0], '20261026-110000')
        for bad in (9, 'x', True):
            with self.assertRaises(ValueError):
                S.ckpt_pick(items, bad)
        with self.assertRaises(ValueError):
            S.ckpt_pick([], 'latest')

    def test_dir_names(self):
        self.assertEqual(S.ckpt_dir_names('/project1/lab/FX'), ['FX', 'FX__project1_lab'])


class Ckpt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, 'ckpt')
        reset()
        self.p1 = Node(ROOT, 'project1')
        self.lab = Node(self.p1, 'lab')
        self.src = Node(self.lab, 'src', 'noiseTOP')
        self.fx = Node(self.lab, 'FX')
        Node(self.fx, 'in1', 'inTOP')
        Node(self.fx, 'out1', 'outTOP')
        self.win = Node(self.fx, 'controls_window', 'windowCOMP')
        self.dst = Node(self.lab, 'dst', 'nullTOP')
        self.fx.inputConnectors[0].connect(self.src.outputConnectors[0])
        self.dst.inputConnectors[0].connect(self.fx.outputConnectors[0])
        self.fx.nodeX, self.fx.nodeY, self.fx.allowCooking = 400, -200, False
        self.fx.store(handlers.STAGE_KEY, {'stages': [{'title': 'A', 'ops': ['in1', 'out1']}]})
        self.h = fake_h(self.tmp, windows=[(self.win, self.fx)])
        S.bind(self.h)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def ck(self, **kw):
        r = S.cmd_checkpoint('/project1/lab/FX', root=self.root, **kw)
        return r.finish() if isinstance(r, handlers.Pending) else r

    def test_checkpoint_writes_tox_meta_and_keeps_5(self):
        for i in range(7):
            r = self.ck(note='n%d' % i)
            self.assertTrue(r['saved'])
            self.assertTrue(r['verified'])
        d = os.path.join(self.root, 'FX')
        toxes = sorted(f for f in os.listdir(d) if f.endswith('.tox'))
        self.assertEqual(len(toxes), 5)
        self.assertEqual(len([f for f in os.listdir(d) if f.endswith('.json')]), 5)
        with open(os.path.join(d, '.path')) as f:
            self.assertEqual(f.read().strip(), '/project1/lab/FX')
        newest = S.ckpt_list(os.listdir(d), 'FX')[0][1]
        with open(os.path.join(d, newest[:-4] + '.json')) as f:
            meta = json.load(f)
        self.assertEqual(meta['note'], 'n6')
        self.assertEqual(meta['inputs'], [['/project1/lab/src', 0]])
        self.assertEqual(meta['outputs'], [[0, '/project1/lab/dst', 0]])
        self.assertEqual((meta['xy'], meta['allowCooking'], meta['parent']), ([400, -200], False, '/project1/lab'))
        self.assertEqual(meta['open_windows'], ['controls_window'])
        self.assertEqual(meta['build'], '2025.31550')
        self.assertTrue(meta['stages']['stages'])
        self.assertEqual(self.fx.par.externaltox.val, '', 'never switched to externaltox')
        self.assertFalse(any(f.endswith('.part.tox') for f in os.listdir(d)))
        lst = S.cmd_checkpoint('/project1/lab/FX', root=self.root, list_only=True)
        self.assertEqual(len(lst['checkpoints']), 5)
        self.assertEqual(lst['checkpoints'][0]['note'], 'n6')

    def test_errors_block_unless_force(self):
        self.fx.op('out1').err = 'boom'
        r = self.ck()
        self.assertFalse(r['saved'])
        self.assertEqual(r['errors'][0]['path'], '/project1/lab/FX/out1')
        self.assertFalse(os.path.isdir(os.path.join(self.root, 'FX')) and
                         any(f.endswith('.tox') for f in os.listdir(os.path.join(self.root, 'FX'))))
        r = self.ck(force=True)
        self.assertTrue(r['saved'])
        self.assertFalse(r['verified'])
        r = self.ck(verify=False)
        self.assertTrue(r['file'].endswith('.tox'))

    def test_externaltox_put_back_if_save_moves_it(self):
        orig = Node.save

        def sneaky(o, file):
            orig(o, file)
            o.par.externaltox.val = file
        Node.save = sneaky
        try:
            r = self.ck()
        finally:
            Node.save = orig
        self.assertEqual(self.fx.par.externaltox.val, '')
        self.assertIn('put back', r['notes'][0])

    def test_same_name_elsewhere_gets_own_folder(self):
        self.ck()
        other = Node(self.p1, 'FX')
        r = S.cmd_checkpoint(other.path, root=self.root, verify=False)
        self.assertIn('FX__project1', r['file'])
        self.assertEqual(S.cmd_checkpoint('/project1/lab/FX', root=self.root, list_only=True)['dir'],
                         os.path.join(self.root, 'FX'))

    def test_refuses_mcp_and_non_comp(self):
        Node(ROOT, 'jazib_mcp')
        with self.assertRaises(ValueError):
            S.cmd_checkpoint('/jazib_mcp', root=self.root)
        with self.assertRaises(ValueError):
            S.cmd_checkpoint('/project1/lab/src', root=self.root)

    def test_restore_swaps_safely(self):
        self.ck(note='good')
        Node(self.fx, 'junk', 'noiseTOP')        # the "broken" later state
        old_id = self.fx.id
        r = S.cmd_restore_checkpoint('/project1/lab/FX', root=self.root)
        self.assertIsInstance(r, handlers.Pending)
        new = T.get('/project1/lab/FX')
        self.assertIsNotNone(new)
        self.assertNotEqual(new.id, old_id)
        self.assertIsNone(new.op('junk'), 'checkpoint content')
        self.assertEqual(self.h['_calls']['destroy'], ['/project1/lab/FX'], 'old one through safe_destroy')
        self.assertEqual((new.nodeX, new.nodeY, new.allowCooking), (400, -200, False))
        self.assertIs(new.inputConnectors[0].connections[0].owner, self.src)
        self.assertIs(self.dst.inputConnectors[0].connections[0].owner, new)
        self.assertEqual(self.h['_restaged'], ['/project1/lab/FX'], 'stage plan re-applied')
        pre = os.path.join(self.root, 'FX', 'pre_restore')
        self.assertEqual(len([f for f in os.listdir(pre) if f.endswith('.tox')]), 1, 'the replaced COMP was kept')
        self.assertEqual(len([o for o in self.lab.kids if o.name.startswith('FX')]), 1)
        out = r.finish()
        self.assertEqual(out['reopened'], ['/project1/lab/FX/controls_window'])
        self.assertEqual(new.op('controls_window').par.winopen.pulsed, 1)
        self.assertEqual(out['errors'], [])

    def test_restore_missing_comp_from_record(self):
        self.ck()
        self.fx.destroy()
        r = S.cmd_restore_checkpoint('/project1/lab/FX', root=self.root, reopen=False).finish()
        new = T.get('/project1/lab/FX')
        self.assertEqual((new.nodeX, new.nodeY), (400, -200))
        self.assertIs(self.dst.inputConnectors[0].connections[0].owner, new)
        self.assertIn('not in the project', r['notes'][0])
        self.assertEqual(r['reopened'], [])
        self.assertIsNone(r['pre_restore'])

    def test_restore_which_and_missing(self):
        with self.assertRaises(ValueError):
            S.cmd_restore_checkpoint('/project1/lab/FX', root=self.root)
        self.ck(note='a')
        self.ck(note='b')
        r = S.cmd_restore_checkpoint('/project1/lab/FX', which='previous', root=self.root)
        self.assertTrue(r.finish()['file'].endswith('.tox'))
        with self.assertRaises(ValueError):
            S.cmd_restore_checkpoint('/nope/FX', root=self.root)


if __name__ == '__main__':
    unittest.main()
