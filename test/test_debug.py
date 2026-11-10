"""Offline tests for td/debug.py + td/debug_panel_rt.py (debug toolkit). No TouchDesigner: fake op trees, a fake
handlers dict H, and a fake toeexpand folder. Run: python3 -I -m unittest discover -s test -p 'test_*.py'"""
import importlib.util
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TD_DIR = os.path.join(os.path.dirname(HERE), 'td')
sys.path.insert(0, HERE)
import test_handlers as TH  # noqa: E402  (installs the stub td module and imports handlers)

handlers = TH.handlers


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TD_DIR, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


D = load('jazib_debug_test', 'debug.py')
RT = load('jazib_debug_rt_test', 'debug_panel_rt.py')
Pending = handlers.Pending


# ---------------------------------------------------------------- fake TD

class P(object):
    def __init__(self, owner, name, val=None, mode='CONSTANT', style='Float', expr='', bind='', custom=False,
                 default=None, evalv=None, exporter=None):
        self.owner, self.name, self.val, self.style = owner, name, val, style
        self.mode = types.SimpleNamespace(name=mode)
        self.expr, self.bindExpr, self.isCustom, self.default = expr, bind, custom, default
        self.evalv, self.exportOP = evalv, exporter
        self.pulsed = 0

    def eval(self):
        return self.evalv if self.evalv is not None else self.val

    @property
    def isDefault(self):
        return self.val == self.default

    def pulse(self):
        self.pulsed += 1


class Pars(object):
    def __init__(self, owner):
        object.__setattr__(self, '_o', owner)

    def __getitem__(self, k):
        return self._o._p.get(k)

    def __getattr__(self, k):
        d = self._o._p
        if k not in d:
            d[k] = P(self._o, k, val='', style='Str', custom=True)
        return d[k]


class Conn(object):
    def __init__(self, owner, is_in):
        self.owner, self.is_in, self.connections = owner, is_in, []

    def connect(self, other):
        src = other if not hasattr(other, 'is_in') else other.owner
        self.connections = [types.SimpleNamespace(owner=src)]
        src.outputConnectors[0].connections.append(types.SimpleNamespace(owner=self.owner))


REG = {}
FAM = re.compile(r'(TOP|CHOP|SOP|DAT|COMP|MAT|POP)$')


class O(object):
    def __init__(self, path, t='noiseTOP', pars=(), text=None, err='', warn='', serr='', cpu=0.0, gpu=0.0, cooks=0,
                 n_in=1, **flags):
        self.path, self.name, self.OPType = path, path.rsplit('/', 1)[-1] or '/', t
        self.family = FAM.search(t).group(1) if FAM.search(t) else ''
        self.isCOMP = self.family == 'COMP'
        self.children = []
        self._p = {}
        self.par = Pars(self)
        for spec in pars:
            p = P(self, **spec)
            self._p[p.name] = p
        self.inputConnectors = [Conn(self, True) for _ in range(n_in)]
        self.outputConnectors = [Conn(self, False)]
        self.text = text
        self.isTable = False
        self._e, self._w, self._s = err, warn, serr
        self.cpuCookTime, self.gpuCookTime, self.totalCooks = cpu, gpu, cooks
        self.cookAbsFrame, self.gpuMemory = 990, 0
        self.display = flags.get('display', False)
        self.render = flags.get('render', False)
        self.bypass = flags.get('bypass', False)
        self.lock = False
        self.viewer = flags.get('viewer', False)
        self.allowCooking = flags.get('allowCooking', True)
        self.export = flags.get('export', False)
        self.valid = True
        self.comment = ''
        self.isOpen = False
        self.rows = []
        REG[path] = self
        par = path.rsplit('/', 1)[0] or '/'
        if path != '/' and par in REG:
            REG[par].children.append(self)

    def pars(self):
        return list(self._p.values())

    def errors(self):
        return self._e

    def warnings(self):
        return self._w

    def scriptErrors(self):
        return self._s

    def parent(self, n=1):
        p = self.path
        for _ in range(n):
            p = p.rsplit('/', 1)[0] or '/'
        return REG.get(p)

    def op(self, rel):
        return REG.get(rel if rel.startswith('/') else (self.path.rstrip('/') + '/' + rel))

    def findChildren(self, type=None):
        out = []
        stack = list(self.children)
        while stack:
            o = stack.pop(0)
            if type is None or o.family == type:
                out.append(o)
            stack.extend(o.children)
        return out

    def create(self, cls, name):
        return O(self.path.rstrip('/') + '/' + name, cls)

    # table DAT bits (panel)
    def clear(self):
        self.rows = []

    def appendRow(self, r):
        self.rows.append([str(x) for x in r])

    @property
    def numRows(self):
        return len(self.rows)

    @property
    def numCols(self):
        return max([len(r) for r in self.rows] or [0])

    def __getitem__(self, rc):
        r, c = rc
        return types.SimpleNamespace(val=self.rows[r][c])


def wire(src, dst, i=0):
    dst.inputConnectors[i].connections = [types.SimpleNamespace(owner=src)]
    src.outputConnectors[0].connections.append(types.SimpleNamespace(owner=dst))


def fake_H(**extra):
    def _op(p):
        o = REG.get(p)
        if o is None:
            raise ValueError('no operator at {}'.format(p))
        return o
    h = {'op': REG.get, '_op': _op, 'Pending': Pending, 'absTime': types.SimpleNamespace(frame=1000),
         'project': types.SimpleNamespace(folder=tempfile.gettempdir(), name='fake.toe', cookRate=60),
         'app': types.SimpleNamespace(version='2025', build='31550'),
         'td': types.SimpleNamespace(DAT='DAT'), 'comp_path': lambda: '/jazib_mcp',
         'valid_op_name': handlers.valid_op_name}
    h.update(extra)
    return D.bind(h)


def drive(r, cap=10000):
    n = 0
    while isinstance(r, Pending):
        r = r.finish()
        n += 1
        if n > cap:
            raise AssertionError('Pending chain never ended')
    return r, n


def project():
    """/project1: noise -> level -> out (null); a select TOP referencing noise; an expression + bind; a CHOP export;
    an Execute DAT watching level; a callbacks DAT; an OSC In; a missing file; a dead branch; /jazib_mcp."""
    REG.clear()
    O('/', 'rootCOMP')
    O('/jazib_mcp', 'baseCOMP')
    O('/jazib_mcp/handlers', 'textDAT', text="op('/project1/noise1')")
    O('/project1', 'containerCOMP', pars=[{'name': 'top', 'val': './out', 'style': 'TOP', 'evalv': None}])
    n = O('/project1/noise1', 'noiseTOP', cpu=2.5, gpu=1.0, cooks=50, viewer=True)
    lv = O('/project1/level1', 'levelTOP', pars=[
        {'name': 'opacity', 'mode': 'EXPRESSION', 'expr': "op('lfo1')['chan1'] * parent().par.Gain"},
        {'name': 'brightness1', 'mode': 'BIND', 'expr': '', 'bind': "op('/project1/ctrl').par.Bright"}])
    out = O('/project1/out', 'nullTOP', pars=[{'name': 'opacity', 'val': 1.0, 'default': 1.0}], display=True)
    wire(n, lv)
    wire(lv, out)
    O('/project1/lfo1', 'lfoCHOP', export=True)
    O('/project1/ctrl', 'baseCOMP', pars=[{'name': 'Bright', 'val': 0.5, 'custom': True, 'default': 0.0},
                                          {'name': 'parentshortcut', 'val': 'Ctrl', 'style': 'Str'}])
    O('/project1/sel', 'selectTOP', pars=[{'name': 'top', 'val': 'noise1', 'style': 'TOP'}], display=True)
    O('/project1/geo1', 'geometryCOMP', pars=[{'name': 'tx', 'mode': 'EXPORT', 'val': 0, 'exporter': REG['/project1/lfo1']}])
    O('/project1/pexec', 'parameterexecuteDAT', pars=[
        {'name': 'op', 'val': 'level1', 'style': 'OP', 'evalv': lv}, {'name': 'active', 'val': True, 'style': 'Toggle'},
        {'name': 'valuechange', 'val': True, 'style': 'Toggle'}],
        text="def onValueChange(par, prev):\n    op('out').par.opacity = par.eval()\n    return\n")
    O('/project1/osc_cb', 'textDAT', text='def onReceiveOSC(dat, rowIndex, message, bytes, timeStamp, address, args, peer):\n    return\n')
    O('/project1/osc_in', 'oscinDAT', pars=[{'name': 'port', 'val': 7001, 'style': 'Int'},
                                            {'name': 'active', 'val': False, 'style': 'Toggle'},
                                            {'name': 'callbacks', 'val': 'osc_cb', 'style': 'DAT'}])
    O('/project1/movie', 'moviefileinTOP', pars=[{'name': 'file', 'val': '/nope/missing_clip.mov', 'style': 'File'}],
      err='Failed to open file', cooks=1)
    O('/project1/orphan_blur', 'blurTOP', warn='input missing')
    O('/project1/ext_comp', 'baseCOMP', pars=[{'name': 'ext0object', 'val': "op('./Ext').module.MyExt(me)", 'style': 'Str'}])
    O('/project1/ext_comp/Ext', 'textDAT', text='class MyExt:\n    pass\n')
    O('/project1/widget', 'containerCOMP', pars=[{'name': 'clone', 'val': '/sys/x', 'style': 'COMP',
                                                  'evalv': types.SimpleNamespace(path='/sys/x', OPType='baseCOMP')}])
    O('/project1/widget/inner', 'textDAT', text='x')
    return REG


# ---------------------------------------------------------------- pure: references

class Refs(unittest.TestCase):
    def test_parse_kinds(self):
        refs = D.parse_refs("op('a/b').par.tx + parent(2).par.Speed + op.Show.par.Fade + parent.Widget.par.Value0 "
                            "+ me.op('x')['chan'] + mod.util.f() + ops('noise*') + c.op('rel') + op(\"/abs\").module.F()")
        kinds = [(r['kind'], r.get('arg'), r.get('base'), r.get('par'), r.get('chan')) for r in refs]
        self.assertIn(('op', 'a/b', None, 'tx', None), kinds)
        self.assertIn(('parent', 2, None, 'Speed', None), kinds)
        self.assertIn(('oshort', 'Show', None, 'Fade', None), kinds)
        self.assertIn(('pshort', 'Widget', None, 'Value0', None), kinds)
        self.assertIn(('op', 'x', 'me', None, 'chan'), kinds)
        self.assertIn(('mod', 'util', None, None, None), kinds)
        self.assertIn(('ops', 'noise*', None, None, None), kinds)
        self.assertIn(('op', 'rel', 'obj', None, None), kinds)
        self.assertTrue(any(r['kind'] == 'op' and r['arg'] == '/abs' and r.get('module') for r in refs))
        # op.TDAnnotate.mod.AnnotateExt is the shortcut's module, not a top-level mod.X
        refs = D.parse_refs('op.TDAnnotate.mod.AnnotateExt.AnnotateExt(me)')
        self.assertEqual([r['kind'] for r in refs], ['oshort', 'me'])

    def test_paths(self):
        self.assertEqual(D.join_path('/a/b', '../c'), '/a/c')
        self.assertEqual(D.join_path('/a/b', './c/d'), '/a/b/c/d')
        self.assertEqual(D.join_path('/a', '/x/y'), '/x/y')
        self.assertEqual(D.ancestor('/a/b/c', 2), '/a')
        self.assertIsNone(D.parent_path('/'))
        self.assertTrue(D.under('/a/b', '/a') and D.under('/a', '/') and not D.under('/ab', '/a'))

    def test_resolve(self):
        ctx = D.Ctx(paths=['/p', '/p/a', '/p/c', '/p/c/k'], comps=['/p', '/p/c'], op_shortcuts={'Show': '/p/c'},
                    parent_shortcuts={'/p': 'Proj'}, packages=['/p/pkg'])
        r = lambda s, owner='/p/a', comp=False: D.resolve_ref(D.parse_refs(s)[0], owner, comp, ctx)  # noqa: E731
        self.assertEqual(r("op('c')"), ('/p/c', True))
        self.assertEqual(r("op('k')", '/p/c', True), ('/p/c/k', True), 'a COMP resolves children first')
        self.assertEqual(r("op('nope')"), ('/p/nope', False))
        self.assertEqual(r("op('/p/pkg/deep/x')"), ('/p/pkg/deep/x', True), 'inside a package counts as found')
        self.assertEqual(r('parent()'), ('/p', True))
        self.assertEqual(r('op.Show'), ('/p/c', True))
        self.assertEqual(r('parent.Proj', '/p/c/k'), ('/p', True))
        self.assertEqual(r('parent.Nope'), (None, False))
        self.assertEqual(r("x.op('c')"), (None, False), 'obj.op(relative) is not guessed')
        self.assertEqual(D.ext_class("op('./Ext').module.MyExt(me)"), 'MyExt')
        self.assertEqual(D.ext_class('op.TDAnnotate.mod.AnnotateExt.AnnotateExt(me)'), 'AnnotateExt')

    def test_keep_par(self):
        self.assertTrue(D.need_value('noiseTOP', 'tx', 'e', 'Float'))
        self.assertFalse(D.need_value('noiseTOP', 'tx', 'c', 'Float'))
        self.assertTrue(D.need_value('oscinDAT', 'port', 'c', 'Int'))
        self.assertTrue(D.need_value('executeDAT', 'framestart', 'c', 'Toggle'))
        self.assertFalse(D.keep_par('selectTOP', 'top', 'c', 'TOP', ''))
        self.assertTrue(D.keep_par('selectTOP', 'top', 'c', 'TOP', 'noise1'))
        self.assertFalse(D.keep_par('oscoutCHOP', 'cookalways', 'c', 'Toggle', False))
        self.assertTrue(D.keep_par('oscoutCHOP', 'cookalways', 'c', 'Toggle', 'on'))
        self.assertEqual(D.mode_code(types.SimpleNamespace(name='BIND')), 'b')
        self.assertEqual(D.mode_code('ParMode.EXPRESSION'), 'e')


# ---------------------------------------------------------------- live: records, analyze (chunked), why, watch

class Analyze(unittest.TestCase):
    def setUp(self):
        project()
        fake_H()

    def test_op_record(self):
        r = D.op_record(REG['/project1/level1'])
        self.assertEqual(r['in'], ['/project1/noise1'])
        self.assertEqual(r['outs'], 1)
        pars = {p['n']: p for p in r['pars']}
        self.assertEqual(pars['opacity']['m'], 'e')
        self.assertEqual(pars['brightness1']['e'], "op('/project1/ctrl').par.Bright")
        self.assertNotIn('tx', pars)
        g = D.op_record(REG['/project1/geo1'])
        self.assertEqual(g['pars'][0]['x'], '/project1/lfo1', 'export source from Par.exportOP')

    def test_walk_skips_mcp_and_packages(self):
        ps = [o.path for o, _k in D.walk_ops(REG['/'])]
        self.assertNotIn('/jazib_mcp/handlers', ps)
        self.assertIn('/project1/widget', ps)
        self.assertNotIn('/project1/widget/inner', ps, 'a clone is listed, not entered')
        self.assertEqual(ps, sorted(ps, key=lambda p: p.split('/')), 'depth-first by name')
        ps2 = [o.path for o, _k in D.walk_ops(REG['/'], packages=True, mcp=True)]
        self.assertIn('/project1/widget/inner', ps2)
        self.assertIn('/jazib_mcp/handlers', ps2)

    def test_analyze_sections(self):
        s, _n = drive(D.cmd_analyze('/project1'))
        self.assertEqual(s['source'], 'live')
        self.assertEqual(s['build'], '2025.31550')
        kinds = s['graph']['edges_by_kind']
        for k in ('wire', 'expr', 'bind', 'export', 'ref', 'watch', 'callbacks', 'extension'):
            self.assertIn(k, kinds, k)
        edges = {(a, b, k) for a, b, k, _l in s['graph']['edges']}
        self.assertIn(('/project1/noise1', '/project1/sel', 'ref'), edges)
        self.assertIn(('/project1/lfo1', '/project1/level1', 'expr'), edges)
        self.assertIn(('/project1', '/project1/level1', 'expr'), edges, 'parent().par.Gain')
        self.assertIn(('/project1/ctrl', '/project1/level1', 'bind'), edges)
        self.assertIn(('/project1/lfo1', '/project1/geo1', 'export'), edges)
        self.assertIn(('/project1/level1', '/project1/pexec', 'watch'), edges)
        self.assertIn(('/project1/osc_cb', '/project1/osc_in', 'callbacks'), edges)
        self.assertIn(('/project1/out', '/project1/pexec', 'script'), edges, "op('out') in the DAT text")
        self.assertIn(('/project1/ext_comp/Ext', '/project1/ext_comp', 'extension'), edges)
        ex = s['python']['exec_dats']['items'][0]
        self.assertEqual((ex['p'], ex['active'], ex['triggers'], ex['watches']),
                         ('/project1/pexec', True, ['valuechange'], '/project1/level1'))
        self.assertEqual(s['extensions']['items'][0]['class'], 'MyExt')
        dev = s['devices']['items'][0]
        self.assertEqual((dev['kind'], dev['active'], dev['settings']['port']), ('OSC in', False, 7001))
        self.assertEqual(s['files']['missing'], 1)
        self.assertEqual(s['files']['items'][0]['path'], '/nope/missing_clip.mov')
        h = s['health']
        self.assertEqual(h['errors']['items'][0]['p'], '/project1/movie')
        self.assertEqual(h['warnings']['items'][0]['p'], '/project1/orphan_blur')
        self.assertIn('/project1/orphan_blur', h['dead_branches']['items'])
        self.assertNotIn('/project1/out', h['dead_branches']['items'], 'display flag / sink type')
        self.assertNotIn('/project1/noise1', h['dead_branches']['items'])
        self.assertEqual(h['heavy'][0]['p'], '/project1/noise1')
        self.assertEqual(h['exporting']['items'], ['/project1/lfo1'])
        self.assertEqual(h['viewers_on'], 1)
        self.assertEqual(s['inventory']['packages'][0]['p'], '/project1/widget')
        self.assertEqual(s['inventory']['comp_tree']['p'], '/project1')
        top = {n['p'] for n in s['graph']['top_level']['nodes']}
        self.assertIn('/project1/ext_comp', top)
        self.assertTrue(s['graph']['top_level']['edges'])
        json.dumps(s)

    def test_chunked_and_paged(self):
        for i in range(300):
            O('/project1/bulk%03d' % i, 'constantCHOP')
        r = D.cmd_analyze('/project1', budget_ms=1)
        orig = D._now
        t = [0.0]

        def clock():  # 0.4 ms per read: a 1 ms budget holds ~2 ops, so the scan must span frames
            t[0] += 0.0004
            return t[0]
        D._now = clock
        try:
            r = D.cmd_analyze('/project1', budget_ms=1)
            self.assertIsInstance(r, Pending, 'big scans hand the rest to the next frame')
            s, frames = drive(r)
        finally:
            D._now = orig
        self.assertGreater(frames, 10)
        self.assertGreater(s['frames'], 10)
        self.assertEqual(s['total_ops'], s['ops'])
        s2, _ = drive(D.cmd_analyze('/project1', limit=50, offset=0))
        self.assertEqual(s2['ops'], 50)
        self.assertEqual(s2['next_offset'], 50)
        self.assertGreater(s2['total_ops'], 300)
        s3, _ = drive(D.cmd_analyze('/project1', limit=50, offset=50))
        self.assertEqual(s3['offset'], 50)
        self.assertFalse(set(n['p'] for n in []) & set())

    def test_why(self):
        r = D.cmd_why('/project1/out', depth=4)
        self.assertEqual(r['tree']['p'], '/project1/out')
        up = r['tree']['up'][0]
        self.assertEqual((up['p'], up['via']), ('/project1/level1', 'wire in0'))
        vias = {x['via']: x.get('p') for x in up['up']}
        self.assertEqual(vias['wire in0'], '/project1/noise1')
        self.assertTrue(any(k.startswith('expr opacity') and v == '/project1/lfo1' for k, v in vias.items()), vias)
        self.assertTrue(any(k.startswith('bind brightness1') and v == '/project1/ctrl' for k, v in vias.items()), vias)
        self.assertEqual(r['scripts']['writes'][0]['dat'], '/project1/pexec', 'op(out).par.opacity = ... found')
        rp = D.cmd_why('/project1/out', par='opacity')
        self.assertEqual(rp['par']['mode'], 'CONSTANT')
        self.assertEqual(rp['scripts']['writes'][0]['line'], 2)
        w = D.cmd_why('/project1/level1')
        self.assertEqual(w['watchers'][0]['dat'], '/project1/pexec')
        g = D.cmd_why('/project1/geo1', par='tx')
        self.assertEqual(g['par']['export_from'], '/project1/lfo1')
        self.assertEqual(g['tree']['up'][0]['p'], '/project1/lfo1')
        with self.assertRaises(ValueError):
            D.cmd_why('/project1/out', par='nope')

    def test_script_hits_pure(self):
        h = D.script_hits([('/d', "x = op('noise1')\nop('noise1').par.seed = 3\nprint(op('noise1').par.seed)\n")],
                          'noise1', '/p/noise1', 'seed')
        self.assertEqual([x['line'] for x in h['writes']], [2])
        self.assertEqual([x['line'] for x in h['mentions']], [3])


class Watch(unittest.TestCase):
    def test_pure_fold(self):
        st = D.watch_new({'cook_rate': 60})
        D.watch_sample(st, {'t': 0.0, 'frame': 100, 'cooks': {'/a': 10, '/b': 5}, 'cms': {'/a': 2.0},
                            'pars': {'/a:tx': 0}, 'errs': {'/a': {}}, 'err_checked': ['/a']})
        D.watch_sample(st, {'t': 0.5, 'frame': 130, 'cooks': {'/a': 40, '/b': 5}, 'cms': {'/a': 2.0},
                            'pars': {'/a:tx': 1}, 'errs': {'/a': {'error': 'boom'}}, 'err_checked': ['/a']})
        D.watch_sample(st, {'t': 1.0, 'frame': 160, 'cooks': {'/a': 70, '/b': 5}, 'cms': {'/a': 2.0},
                            'pars': {'/a:tx': 1}, 'errs': {'/a': {}}, 'err_checked': ['/a']})
        s = D.watch_summary(st)
        self.assertEqual(s['fps']['avg'], 60.0)
        self.assertEqual(s['top_cook'][0]['p'], '/a')
        self.assertEqual(s['top_cook'][0]['cooks'], 60)
        self.assertEqual(s['top_cook'][0]['est_ms'], 120.0)
        self.assertEqual(s['cooking_ops'], 1, '/b never cooked')
        self.assertEqual(s['par_changes']['items'][0]['changes'], 1)
        self.assertEqual([(e['what'], e['kind']) for e in s['events']], [('appeared', 'error'), ('cleared', 'error')])

    def test_cmd_watch_pending_chain(self):
        project()
        fake_H()
        orig = D._now
        t = [0.0]

        def clock():
            t[0] += 0.01
            return t[0]
        D._now = clock
        try:
            r = D.cmd_watch('/project1', seconds=0.5, sample_hz=10)
            n = REG['/project1/noise1']
            steps = 0
            while isinstance(r, Pending):
                n.totalCooks += 2
                REG['/project1/ctrl'].par.Bright.val = 0.5 + steps * 0.01
                r = r.finish()
                steps += 1
        finally:
            D._now = orig
        self.assertGreater(steps, 2)
        self.assertEqual(r['meta']['frames_per_sample'], 6)
        self.assertEqual(r['top_cook'][0]['p'], '/project1/noise1')
        self.assertTrue(any(c['par'] == '/project1/ctrl:Bright' for c in r['par_changes']['items']))
        self.assertIn('/project1/movie', r['errors_now'])
        self.assertTrue(r['timeline'])
        json.dumps(r)


# ---------------------------------------------------------------- offline: toeexpand folder

def text_file(payload):
    b = payload.encode('utf-8')
    return b'2\n*' + struct.pack('>6I', 1, 1, 1, 1, 2, len(b)) + b


def fake_expanded(root):
    def w(rel, data, binary=False):
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb' if binary else 'w') as f:
            f.write(data)
    w('.build', 'version 099\nbuild 2025.31550\ntime Mon Oct 26 11:57:37 2026\n')
    w('project1.n', 'COMP:container\ntile 0 0 100 100\nflags =  viewer 1 parlanguage 0\nend\n')
    w('project1.parm', '?\ntop 0 ./out1\nparentshortcut 0 Project\n?\n')
    w('project1/noise1.n', 'TOP:noise\ntile 0 0 130 90\nflags =  viewer 1 parlanguage 0\nend\n')
    w('project1/noise1.parm', '?\nseed 17 1 "absTime.frame % 7"\n?\n')
    w('project1/level1.n', 'TOP:level\nflags =  viewer 1\ninputs\n{\n0 \tnoise1\n}\nend\n')
    w('project1/level1.parm', '?\nopacity 515 1 parent.Project.par.Fade\nbrightness1 2 1\n?\n')
    w('project1/out1.n', 'TOP:null\nflags =  display on viewer 1\ninputs\n{\n0 \tlevel1\n}\nend\n')
    w('project1/movie.n', 'TOP:moviefilein\nflags =  viewer 0\nend\n')
    w('project1/movie.parm', '?\nfile 0 /nope/gone.mov\n?\n')
    w('project1/osc.n', 'DAT:oscin\nend\n')
    w('project1/osc.parm', '?\nport 0 7001\ncallbacks 0 osc_cb\n?\n')
    w('project1/osc_cb.n', 'DAT:text\nend\n')
    w('project1/osc_cb.text', text_file("def onReceiveOSC(*a):\n    op('noise1').par.seed = 2\n"), binary=True)
    w('project1/exec1.n', 'DAT:execute\nend\n')
    w('project1/exec1.parm', '?\nframestart 0 on\n?\n')
    w('project1/exec1.text', text_file("def onFrameStart(frame):\n    op('/project1/level1').cook(force=True)\n"),
      binary=True)
    w('project1/widget.n', 'COMP:container\nend\n')
    w('project1/widget.parm', '?\nclone 49 "" "op.TDBasicWidgets.op(\'button\')"\n?\n')
    w('project1/widget/inner.n', 'DAT:text\nend\n')
    w('project1/dead_blur.n', 'TOP:blur\nend\n')


class Offline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='jtd-dbg-')
        self.dir = os.path.join(self.tmp, 'src.toe.dir')
        fake_expanded(self.dir)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_readers(self):
        self.assertEqual(D.read_payload(text_file('hi\n')), 'hi\n')
        self.assertIsNone(D.read_payload(b'xx'))
        p = D.read_parms('?\nfile 16 /a.mov "\'TDMovieOut\' + me.fileSuffix"\nopacity 515 1 parent.W.par.Fade\n'
                         'clickthrough 529 off parent.W.par.c parent.W.par.c\nw 2 400\ntop 0 ./out1\n?\n')
        self.assertEqual(p['file']['mode'], 'c', 'expression stored, constant mode (flags 16: no mode bits)')
        self.assertEqual(p['file']['expr'], "'TDMovieOut' + me.fileSuffix")
        self.assertEqual((p['opacity']['mode'], p['opacity']['bind']), ('b', 'parent.W.par.Fade'))
        self.assertEqual((p['clickthrough']['mode'], p['clickthrough']['expr']), ('e', 'parent.W.par.c'))
        self.assertEqual(p['w']['mode'], 'x')
        n = D.read_node('TOP:null\nflags =  display on viewer 1\ninputs\n{\n0 \tlevel1\n}\nend\n')
        self.assertEqual((n['family'], n['type'], n['inputs'], n['flags']['display']), ('TOP', 'null', [(0, 'level1')], 'on'))

    def test_analyze_expanded(self):
        s = D.analyze_expanded(self.dir, folder=self.tmp, ops_dir=os.path.join(os.path.dirname(HERE), 'docs', 'research', 'ops'))
        self.assertEqual((s['source'], s['build']), ('file', '2025.31550'))
        edges = {(a, b, k) for a, b, k, _l in s['graph']['edges']}
        self.assertIn(('/project1/noise1', '/project1/level1', 'wire'), edges)
        self.assertIn(('/project1', '/project1/level1', 'bind'), edges, 'parent.Project shortcut')
        self.assertIn(('/project1/osc_cb', '/project1/osc', 'callbacks'), edges)
        self.assertIn(('/project1/noise1', '/project1/osc_cb', 'script'), edges)
        self.assertIn(('/project1/out1', '/project1', 'ref'), edges, "COMP top par './out1'")
        self.assertEqual(s['files']['missing'], 1)
        self.assertEqual(s['devices']['items'][0]['settings']['port'], '7001')
        self.assertIsNone(s['devices']['items'][0]['active'], 'defaults are not saved: unknown offline')
        self.assertEqual(s['python']['exec_dats']['items'][0]['triggers'], ['framestart'])
        self.assertEqual(s['python']['where']['frame_callbacks'], ['/project1/exec1'])
        self.assertEqual(s['inventory']['packages'][0]['p'], '/project1/widget')
        self.assertNotIn('/project1/widget/inner', [r for r in s['graph']['edges']])
        self.assertIn('/project1/dead_blur', s['health']['dead_branches']['items'])
        self.assertEqual(s['exports']['count'], 1)

    def test_cli(self):
        out = subprocess.run([sys.executable, '-I', os.path.join(TD_DIR, 'debug.py'), 'analyze-expanded', self.dir,
                              '--root', '/project1', '--file', 'x.toe'], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        s = json.loads(out.stdout)
        self.assertEqual((s['root'], s['file']), ('/project1', 'x.toe'))
        self.assertGreater(s['ops'], 5)
        bad = subprocess.run([sys.executable, '-I', os.path.join(TD_DIR, 'debug.py'), 'analyze-expanded', self.dir,
                              '--root', '/nope'], capture_output=True, text=True, timeout=60)
        self.assertNotEqual(bad.returncode, 0)


# ---------------------------------------------------------------- panel builder + runtime

class Panel(unittest.TestCase):
    def setUp(self):
        project()
        self.calls = {'custom': [], 'destroy': [], 'stages': None, 'set': []}
        cls = ('containerCOMP', 'textDAT', 'tableDAT', 'executeDAT', 'dattoCHOP', 'opviewerCOMP', 'textTOP',
               'constantTOP', 'compositeTOP', 'nullTOP', 'panelexecuteDAT', 'windowCOMP', 'listCOMP')
        td_ = types.SimpleNamespace(DAT='DAT', **{c: c for c in cls})

        def plan(o, pars):
            return [(o, k, v) for k, v in pars.items()], []

        def apply(plans):
            for o, k, v in plans:
                self.calls['set'].append((o.name, k, v))
                o.par.__getattr__(k).val = v

        def custom(path, page, pars):
            self.calls['custom'].append((path, page, [p['name'] for p in pars]))
            return {'added': [p['name'] for p in pars]}

        def stages(c, st, colors):
            self.calls['stages'] = st
            return {'ok': True}
        fake_H(td=td_, _plan_pars=plan, _apply_plans=apply, cmd_custom_pars=custom,
               safe_destroy=lambda o: self.calls['destroy'].append(o.path), layout_stages=stages,
               _arrange=lambda c: {'comp': c.path}, _auto_xy=lambda p, c: (0, 0))

    def test_build_and_rebuild_in_place(self):
        r = D.cmd_debug_panel_build('/project1/debug', scope='/project1')
        self.assertTrue(r['created'])
        c = REG['/project1/debug']
        for n in ('rt', 'tick', 'click', 'top_ops', 'errs', 'acts', 'fps_hist', 'fps_chop', 'fps_graph', 'sp_head',
                  'sp_title', 'sp_body', 'sp_err', 'tx_head', 'tx_title', 'tx_body', 'tx_err', 'view_bg',
                  'view_comp', 'view', 'table_view', 'debug_window'):
            self.assertIsNotNone(c.op(n), n)
        for n in ('top_list', 'err_list', 'act_list', 'perform', 'header'):
            self.assertIsNone(c.op(n), 'no List COMPs / Perform graph any more (T-72): ' + n)
        self.assertIn('def tick(c)', c.op('rt').text)
        self.assertIn('module.click(c,', c.op('click').text)
        self.assertEqual(c.op('top_ops').rows[0], ['path', 'ms', 'cooks/s', 'type'])
        self.assertEqual(c.op('sp_body').rows[0], ['x', 'y', 'text'])
        self.assertEqual(self.calls['custom'][0][2], ['Active', 'Scope', 'Refreshhz', 'Slice', 'Logdir'])
        self.assertEqual([s['title'] for s in self.calls['stages']], ['Runtime', 'Data', 'View', 'Panel'])
        self.assertIn(('fps_graph', 'opviewer', {'expr': "parent().op('fps_chop')", 'mode': 'EXPRESSION'}), self.calls['set'])
        self.assertIn(('table_view', 'top', 'view'), self.calls['set'])
        self.assertIn(('click', 'panels', 'table_view'), self.calls['set'])
        self.assertEqual(c.op('view').inputConnectors[0].connections[0].owner.path, '/project1/debug/view_comp')
        # rebuild with the window open, a wrong-type child and old List-COMP-panel ops: container kept, window
        # closed first + reopened, everything removed goes through safe_destroy (T-70)
        c.op('debug_window').isOpen = True
        REG.pop('/project1/debug/view')
        c.children = [k for k in c.children if k.name != 'view']
        O('/project1/debug/view', 'textDAT')
        O('/project1/debug/top_list', 'listCOMP')
        O('/project1/debug/perform', 'performCHOP')
        r2 = D.cmd_debug_panel_build('/project1/debug')
        self.assertFalse(r2['created'])
        self.assertIs(REG['/project1/debug'], c, 'the panel container is never destroyed (T-70)')
        self.assertEqual(sorted(self.calls['destroy']), ['/project1/debug/perform', '/project1/debug/top_list',
                                                         '/project1/debug/view'])
        self.assertEqual(sorted(r2['removed_ops']), ['perform', 'top_list'])
        self.assertEqual(c.op('debug_window').par.winclose.pulsed, 1)
        self.assertEqual(c.op('debug_window').par.winopen.pulsed, 1, 'reopened (fallback: no td.run in the fake)')
        self.assertTrue(r2['window_open'])
        with self.assertRaises(ValueError):
            D.cmd_debug_panel_build('/project1/noise1')
        self.assertIsNone(D._kit_hook(c, 'plain', []))

    def test_runtime_pure(self):
        e = RT.cook_entry(None, 3.0, 10, 90, 'noiseTOP')
        self.assertIsNone(e[2], 'first read: not seen cooking yet')
        e = RT.cook_entry(e, 3.0, 20, 100, 'noiseTOP')
        self.assertEqual((e[2], e[3]), (100, 60.0))
        e2 = RT.cook_entry(e, 0.0, 20, 104, 'noiseTOP')
        self.assertEqual((e2[0], e2[2], e2[3]), (3.0, 100, 60.0), 're-read without a cook keeps the last change')
        cook = {'/a': e2, '/b': RT.cook_entry(RT.cook_entry(None, 9.0, 5, 90, 'blurTOP'), 9.0, 5, 100, 'blurTOP'),
                '/c': (1.0, 8, 100, 30.0, 'levelTOP', 100), '/old': (50.0, 9, -100, 5.0, 'x', 100)}
        rows = RT.top_ops(cook, 104)
        self.assertEqual([r[0] for r in rows], ['/a', '/c'], 'only ops that cooked lately, slowest first')
        self.assertEqual(rows[0][2], '60')
        self.assertEqual(RT.err_rows({'/w': ('warning', 'w'), '/e': ('error', 'e\nmore')}), [['/e', 'error', 'e'], ['/w', 'warning', 'w']])
        lines = [json.dumps({'time': '2026-10-26T10:00:00.000Z', 'phase': 'start', 'code': 'x=1'}),
                 json.dumps({'time': '2026-10-26T10:00:01.000Z', 'phase': 'end', 'code': 'x=1\ny', 'ok': True}),
                 json.dumps({'t': '2026-10-26T10:00:02.000Z', 'cmd': 'create', 'ok': False, 'path': '/p'}), 'torn{']
        self.assertEqual(RT.log_rows(lines), [['10:00:02', 'create', '/p', 'ERR'], ['10:00:01', 'exec', 'x=1', 'ok']])
        self.assertIn('fps 60.0', RT.fps_text(60, 16.6, 0, 0.2, 10, 1.5))

    def test_runtime_view_and_logs(self):
        big = json.dumps({'time': '2026-10-26T10:00:03.000Z', 'pid': 1, 'phase': 'end', 'code': 'a = 1\nb', 'ok': False,
                          'result': 'x' * 5000 + '"ok":true'})
        self.assertEqual(RT.parse_log_line(big), ('2026-10-26T10:00:03.000Z', 'exec', 'a = 1', 'ERR'))
        self.assertIsNone(RT.parse_log_line('{"time":"t","phase":"start","code":"x"}'))
        self.assertIsNone(RT.parse_log_line('{"time":"t","phase":"end","co'))
        # incremental read: tail first, then only new bytes; torn last line waits; rotation restarts
        d = tempfile.mkdtemp(prefix='jtd-log-')
        try:
            f = os.path.join(d, 'exec.log')
            with open(f, 'w') as fh:
                fh.write('one\ntwo\nthr')
            st = {}
            self.assertEqual(RT.read_new(f, st), ['one', 'two'])
            self.assertEqual(RT.read_new(f, st), [])
            with open(f, 'a') as fh:
                fh.write('ee\nfour\n')
            self.assertEqual(RT.read_new(f, st), ['three', 'four'])
            with open(f, 'w') as fh:
                fh.write('new\n')
            self.assertEqual(RT.read_new(f, st), ['new'])
            self.assertEqual(RT.read_new(os.path.join(d, 'missing'), {}), [])
        finally:
            shutil.rmtree(d, ignore_errors=True)
        fs = RT.frame_stats([1 / 60.0] * 59 + [0.05], 60)
        self.assertEqual((fs['slow'], fs['n'], round(fs['max_ms'])), (1, 60, 50))
        self.assertIsNone(RT.frame_stats([])['fps'])
        self.assertEqual(RT.fit('/project1/lab/very_long_name', 12, True), '..._long_name'[1:])
        self.assertEqual(RT.fit('ab', 4), 'ab  ')
        self.assertEqual(RT.short_path('/project1/lab/x', '/project1'), 'lab/x')
        top = [['/project1/lab/a', '1.25', '60', 'noiseTOP']]
        errs = [['/project1/m', 'error', 'Failed to open file']]
        acts = [['10:00:02', 'create', '/project1/p', 'ok'], ['10:00:01', 'exec', 'x=1', 'ERR']]
        L = RT.view_lines(['fps 60', 'sub'], top, errs, 3, acts, '/project1')
        self.assertEqual(len(L), 3 + 1 + RT.TOP_N + 1 + 1 + RT.ERR_N + 1 + 1 + RT.ACT_N, 'fixed slots')
        self.assertTrue(all(len(t) <= RT.CHARS for _k, t, _p in L), 'every line fits the view width')
        self.assertEqual(L[4][2], '/project1/lab/a')
        self.assertIn('(3, 2 more)', L[3 + 1 + RT.TOP_N + 1][1])
        e = L[3 + 1 + RT.TOP_N + 2]
        self.assertEqual((e[0], e[2]), ('err', '/project1/m'))
        a0 = 3 + 1 + RT.TOP_N + 1 + 1 + RT.ERR_N + 2
        self.assertEqual((L[a0][2], L[a0 + 1][0], L[a0 + 1][2]), ('/project1/p', 'err', None))
        # click mapping: the middle of line i -> i; spec rows place line i at that height
        for i in (0, 4, a0, len(L) - 1):
            y_mid = RT.VIEW_H - RT.PAD_TOP - (i + 0.5) * RT.LINE_H
            self.assertEqual(RT.line_at(y_mid / RT.VIEW_H, len(L)), i)
        self.assertIsNone(RT.line_at(0.0, len(L)), 'below the last slot')
        self.assertIsNone(RT.line_at(1.0, len(L)), 'in the top padding')
        rows = RT.spec_rows(L, 'body')
        first = [k for k, x in enumerate(L) if x[0] == 'body'][0]
        self.assertEqual(rows[0][1], RT.VIEW_H - RT.PAD_TOP - (first + 1) * RT.LINE_H + 3)
        self.assertEqual(RT.line_at((rows[0][1] + 5) / float(RT.VIEW_H), len(L)), first, 'drawn row = clicked row')
        h = []
        for _ in range(70):
            RT.graph_push(h, 15, 0.25)
        self.assertEqual((len(h), h[-1]), (RT.GRAPH_POINTS, 60.0))

    def test_runtime_tick(self):
        D.cmd_debug_panel_build('/project1/debug', scope='/project1')
        c = REG['/project1/debug']
        logs = tempfile.mkdtemp(prefix='jtd-rt-')
        with open(os.path.join(logs, 'exec.log'), 'w') as f:
            f.write(json.dumps({'time': '2026-10-26T10:00:01.000Z', 'phase': 'end', 'code': 'print(1)', 'ok': True}) + '\n')
        c.par.Scope.val, c.par.Slice.val, c.par.Refreshhz.val, c.par.Logdir.val = '/project1', 500, 10.0, logs
        c.par.Active.val = True
        RT.reset(c)
        orig_f, orig_b = RT._frame, RT.TICK_BUDGET_MS
        frame = [100]
        RT._frame = lambda: frame[0]
        RT.TICK_BUDGET_MS = 1000.0

        def publish():  # one publish = one phase per frame (staggered)
            RT._ST[c.path]['last_pub'] = 0.0
            for _ in range(len(RT.PHASES)):
                RT.tick(c)
        try:
            RT.tick(c)
            REG['/project1/noise1'].totalCooks += 10
            frame[0] = 110
            publish()
            self.assertEqual(c.op('sp_body').rows, [['x', 'y', 'text']], 'window closed: the view is not drawn')
            c.op('debug_window').isOpen = True
            publish()
            w = RT._ST[c.path]['writes']
            RT._ST[c.path]['last_log'] = 0.0
            publish()
            self.assertLessEqual(RT._ST[c.path]['writes'] - w, 1, 'unchanged rows are not rewritten (header only)')
        finally:
            RT._frame, RT.TICK_BUDGET_MS = orig_f, orig_b
            shutil.rmtree(logs, ignore_errors=True)
        top = c.op('top_ops').rows
        self.assertEqual(top[1][0], '/project1/noise1')
        errs = c.op('errs').rows
        self.assertIn(['/project1/movie', 'error', 'Failed to open file'], errs)
        self.assertNotIn('/project1/debug', ' '.join(r[0] for r in errs + top), 'the panel never lists itself')
        self.assertEqual(c.op('acts').rows[1][1], 'exec')
        body = ' '.join(r[2] for r in c.op('sp_body').rows[1:])
        self.assertIn('noise1', body)
        self.assertIn('fps', ' '.join(r[2] for r in c.op('sp_head').rows[1:]))
        self.assertIn('movie', ' '.join(r[2] for r in c.op('sp_err').rows[1:]))
        # a click on the noise1 row focuses it
        L = RT._ST[c.path]['lines']
        i = [k for k, x in enumerate(L) if x[2] == '/project1/noise1'][0]
        got = []
        orig_focus = RT.focus
        RT.focus = lambda comp, p: got.append(p) or True
        try:
            self.assertTrue(RT.click(c, (RT.VIEW_H - RT.PAD_TOP - (i + 0.5) * RT.LINE_H) / RT.VIEW_H))
        finally:
            RT.focus = orig_focus
        self.assertEqual(got, ['/project1/noise1'])
        st = RT.stats(c)
        self.assertGreater(st['ticks'], 2)
        self.assertIn('real_fps_2s', st)


class HandlersWiring(unittest.TestCase):
    def test_commands_mutating_and_loader(self):
        for c in ('analyze', 'why', 'watch', 'debug_panel_build'):
            self.assertIn(c, handlers.COMMANDS)
        self.assertIn('debug_panel_build', handlers.MUTATING)
        for c in ('analyze', 'why', 'watch'):
            self.assertNotIn(c, handlers.MUTATING)
        with open(os.path.join(TD_DIR, 'handlers.py')) as f:
            src = f.read()
        lit = re.search(r'MUTATING = frozenset\(\(([\s\S]*?)\)\)', src).group(1)
        self.assertNotIn('debug_panel_build', lit, 'the literal stays as it was (journal parity test)')
        handlers.DEBUG_DIR = TD_DIR
        try:
            m = handlers._debug()
            self.assertIs(m.H['Pending'], handlers.Pending)
            self.assertIs(handlers._debug(), m, 'cached while the file is unchanged')
            self.assertTrue(m.HERE.endswith('td'))
        finally:
            handlers.DEBUG_DIR = None

    def test_dispatch_pending_chain(self):
        """analyze through handlers.dispatch: Pending steps are scheduled via _runner and the reply comes at the end."""
        project()
        for i in range(120):
            O('/project1/n%03d' % i, 'constantTOP')
        sent, sched = [], []
        saved = handlers.op, handlers._runner, handlers.DEBUG_DIR
        handlers.op = REG.get
        handlers._runner = lambda script, frames: sched.append(script)
        handlers.DEBUG_DIR = TD_DIR
        orig = D._now
        try:
            m = handlers._debug()
            t = [0.0]

            def clock():
                t[0] += 0.003
                return t[0]
            m._now = clock
            handlers.dispatch(json.dumps({'id': 9, 'cmd': 'analyze', 'args': {'path': '/project1', 'budget_ms': 5}}),
                              lambda s: sent.append(json.loads(s)))
            n = 0
            while not sent and n < 1000:
                self.assertEqual(len(sched), n + 1)
                handlers._finish(9)
                n += 1
            self.assertGreater(n, 3, 'the scan spread over frames')
            self.assertTrue(sent[0]['ok'], sent[0])
            self.assertGreater(sent[0]['result']['ops'], 120)
            handlers.dispatch(json.dumps({'id': 10, 'cmd': 'why', 'args': {'path': '/project1/out'}}),
                              lambda s: sent.append(json.loads(s)))
            self.assertEqual(sent[-1]['result']['tree']['up'][0]['p'], '/project1/level1')
            handlers.dispatch(json.dumps({'id': 11, 'cmd': 'why', 'args': {'path': '/nope'}}),
                              lambda s: sent.append(json.loads(s)))
            self.assertFalse(sent[-1]['ok'])
        finally:
            handlers.op, handlers._runner, handlers.DEBUG_DIR = saved
            D._now = orig
            handlers._DEBUG.update(mod=None, mtime=None, file=None)

    def test_ascii(self):
        for f in ('debug.py', 'debug_panel_rt.py', 'handlers.py'):
            with open(os.path.join(TD_DIR, f), 'rb') as fh:
                fh.read().decode('ascii')


if __name__ == '__main__':
    unittest.main()
