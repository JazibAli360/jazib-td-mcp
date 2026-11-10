"""Offline tests for td/library.py (component library) and its registration in td/handlers.py. No TouchDesigner: a
small fake op tree whose COMP.save writes JSON and parent.loadTox reads it back.
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


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TD_DIR, file))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L = load('jazib_library_test', 'library.py')
S = load('jazib_safety_for_library_test', 'safety.py')
OPS = {}


class Par(object):
    def __init__(self, name, val='', style='Str', default='', label=None):
        self.name, self.val, self.style, self.default, self.label = name, val, style, default, label or name

    def eval(self):
        return self.val


class Pars(object):
    def __init__(self, plist):
        for p in plist:
            setattr(self, p.name, p)


class Page(object):
    def __init__(self, name, pars):
        self.name, self.pars = name, pars


class Conn(object):
    def __init__(self, out_op=None):
        self.outOP = out_op


class Node(object):
    def __init__(self, parent, name, optype='baseCOMP', pars=(), pages=()):
        self._parent, self._name, self.OPType = parent, name, optype
        self.isCOMP = optype.endswith('COMP')
        self.family = 'COMP' if self.isCOMP else optype[-3:] if optype[-3:] in ('TOP', 'DAT', 'SOP', 'MAT') else 'CHOP'
        self.kids, self.storage, self.allowCooking, self.valid, self.viewer = [], {}, True, True, False
        self._pars = [Par('externaltox', '', 'File'), Par('enableexternaltox', False, 'Toggle')] + list(pars)
        self.customPages = list(pages)
        self.par = Pars(self._pars + [q for pg in self.customPages for q in pg.pars])
        self.outputConnectors = []
        self.cookTime, self.cpuCookTime, self.gpuCookTime = 0.5, 0.3, 0.2
        self.width, self.height, self.cooks = 1080, 1920, 0
        if parent is not None:
            parent.kids.append(self)
        OPS[self.path] = self

    @property
    def path(self):
        return '/' if self._parent is None else self._parent.path.rstrip('/') + '/' + self._name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, v):
        subs = [self] + self.findChildren()
        for o in subs:
            OPS.pop(o.path, None)
        self._name = v
        for o in subs:
            OPS[o.path] = o

    @property
    def children(self):
        return list(self.kids)

    def parent(self):
        return self._parent

    def findChildren(self, **kw):
        out = []
        for k in self.kids:
            out += [k] + k.findChildren()
        return out

    def pars(self):
        return list(self._pars)

    def op(self, rel):
        return OPS.get(self.path.rstrip('/') + '/' + rel)

    def fetch(self, k, d=None, search=False):
        return self.storage.get(k, d)

    def store(self, k, v):
        self.storage[k] = v

    def cook(self, force=False):
        self.cooks += 1

    def saveByteArray(self, ext):
        assert ext == '.png'
        return b'\x89PNG fake ' + self.name.encode()

    def save(self, file):
        def rec(o):
            return {'name': o.name, 'type': o.OPType, 'storage': o.storage,
                    'pars': [[p.name, p.val, p.style] for p in o._pars[2:]],
                    'pages': [[pg.name, [[p.name, p.val, p.style] for p in pg.pars]] for pg in o.customPages],
                    'kids': [rec(k) for k in o.kids]}
        with open(file, 'w') as f:
            json.dump(rec(self), f)

    def loadTox(self, file):
        with open(file) as f:
            d = json.load(f)

        def mk(parent, r):
            pages = [Page(n, [Par(a, b, c) for a, b, c in ps]) for n, ps in r['pages']]
            o = Node(parent, r['name'], r['type'], [Par(a, b, c) for a, b, c in r['pars']],
                     pages)
            o.storage = dict(r['storage'])
            for k in r['kids']:
                mk(o, k)
            return o
        return mk(self, d)


def build_tree(tmp):
    OPS.clear()
    root = Node(None, '')
    lab = Node(root, 'lab')
    look = Node(lab, 'GN_demo', pages=[Page('Look', [Par('Speed', 2.0, 'Float', 1.0), Par('Mode', 'a', 'Menu', 'a')])])
    Node(look, 'in1', 'inTOP')
    out = Node(look, 'out1', 'outTOP')
    look.outputConnectors = [Conn(out)]
    Node(look, 'clip', 'moviefileinTOP', [Par('file', '/Users/x/Movies/clip.mov', 'File')])
    Node(look, 'glsl_src', 'textDAT', [Par('file', 'builders/glsl/a.glsl', 'File')])
    look.allowCooking = False
    return root, lab, look


def fake_h(tmp):
    repo = os.path.join(tmp, 'repo')
    os.makedirs(os.path.join(repo, 'td'))
    os.makedirs(os.path.join(repo, 'docs', 'builds'))
    os.makedirs(os.path.join(repo, 'logs'))
    os.makedirs(os.path.join(repo, 'builders', 'glsl'))
    open(os.path.join(repo, 'builders', 'glsl', 'a.glsl'), 'w').close()
    with open(os.path.join(repo, 'docs', 'builds', 'demo.md'), 'w') as f:
        f.write('# GN_demo - a demo look\n\nLine one of the doc.\nLine two.\n\n## Details\nnot in the readme\n')
    h = dict(vars(handlers))
    S.bind(h)
    lay = []
    h.update(op=lambda p: OPS.get(p), project=types.SimpleNamespace(folder=repo, name='home.toe'),
             app=types.SimpleNamespace(version='2025', build='31550', installFolder='/Applications/TD.app'),
             handlers_file=lambda: os.path.join(repo, 'td', 'handlers.py'), _safety=lambda: S,
             _protected=lambda p: p.startswith('/jazib_mcp'), _arrange=lambda c, a=True: lay.append(c.path) or {'ok': 1},
             restage=lambda c: {'restaged': c.path})

    def _op(path, what='path'):
        o = OPS.get(path)
        if o is None:
            raise ValueError('no operator at {}'.format(path))
        return o
    h['_op'] = _op
    L.bind(h)
    return repo, h


def rd(file):
    with open(file) as f:
        return f.read()


def run_pending(r, log=None):
    while isinstance(r, handlers.Pending):
        if log is not None:
            log.append(r.frames)
        r = r.finish()
    return r


class Pure(unittest.TestCase):
    def test_doc_candidates_and_head(self):
        self.assertEqual(L.doc_candidates('GN_physarum'), ['gn_physarum', 'physarum'])
        self.assertEqual(L.doc_candidates('AU_features')[0], 'au_features')
        t, b = L.doc_head('# Title\n\nA\nB\n\n## Next\nC\n')
        self.assertEqual((t, b), ('Title', ['A', 'B']))
        self.assertEqual(len(L.doc_head('# T\n' + 'x\n' * 40, 5)[1]), 5)

    def test_classify_file(self):
        ex = lambda p: p.endswith('ok.mov')  # noqa: E731
        self.assertIsNone(L.classify_file('', '/r', '/r'))
        f = L.classify_file('media/ok.mov', '/r/projects', '/r', None, ex)
        self.assertEqual((f['where'], f['exists'], f['resolved']), ('repo', True, '/r/projects/media/ok.mov'))
        self.assertEqual(L.classify_file('/Applications/TD.app/x.tox', '/r', '/r', '/Applications/TD.app')['where'],
                         'td_app')
        f = L.classify_file('/Users/x/a.mov', '/r', '/r', None, ex)
        self.assertEqual((f['where'], f['exists']), ('outside', False))
        self.assertEqual(L.classify_file('/rx/a', '/r', '/r')['where'], 'outside', 'prefix is not a folder match')

    def test_version_and_gitignore(self):
        self.assertEqual(L.version_for(None, None, None), '0.1.0')
        self.assertEqual(L.version_for(None, '1.2.0', '0.9'), '1.2.0')
        self.assertEqual(L.version_for('2.0', '1.2.0', '0.9'), '2.0')
        self.assertEqual(L.version_for(None, '', '0.9'), '0.9')
        g = L.gitignore_lines('', 'Big', True)
        self.assertEqual(g[1:], ['/Big/Big.tox'])
        self.assertEqual(L.gitignore_lines('\n'.join(g), 'Big', False)[1:], [])
        self.assertEqual(L.gitignore_lines('\n'.join(g), 'Other', True)[1:], ['/Big/Big.tox', '/Other/Other.tox'])

    def test_index_md(self):
        md = L.index_md([{'name': 'A', 'version': '0.1.0', 'td_build': '2025.31550', 'size': 2 * 1048576,
                          'in_git': True, 'outside_files': 1, 'summary': 'a | b'}])
        self.assertIn('| [A](A/README.md) | 0.1.0 | 2025.31550 | 2.00 MB | yes | 1 | a \\| b |', md)


class ExportLoad(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo, self.h = fake_h(self.tmp)
        self.root, self.lab, self.look = build_tree(self.tmp)
        self.lib = os.path.join(self.repo, 'library')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_export_unparks_reads_late_and_reparks(self):
        frames = []
        p = L.cmd_library_export('/lab/GN_demo', root=self.lib)
        self.assertTrue(self.look.allowCooking, 'un-parked for the thumbnail')
        self.assertEqual(self.look.op('out1').cooks, 0, 'no cook in the un-parking script')
        p2 = p.finish()
        self.assertEqual(self.look.op('out1').cooks, 1)
        while self.look.op('out1').cooks < 25:
            self.assertEqual(p2.frames, 1)
            self.assertFalse(os.path.exists(os.path.join(self.lib, 'GN_demo', 'thumb.png')), 'no read while cooking')
            p2 = p2.finish()
        self.assertEqual(p2.frames, 3, 'read 3 frames after the last force-cook (T-74)')
        r = run_pending(p2)
        self.assertEqual(self.look.op('out1').cooks, 25)
        self.assertFalse(self.look.allowCooking, 'parked again')
        self.assertTrue(r['reparked'])
        d = os.path.join(self.lib, 'GN_demo')
        for f in ('GN_demo.tox', 'thumb.png', 'README.md', 'meta.json'):
            self.assertTrue(os.path.isfile(os.path.join(d, f)), f)
        meta = json.loads(rd(os.path.join(d, 'meta.json')))
        self.assertEqual(meta['version'], '0.1.0')
        self.assertEqual(meta['td_build'], handlers.td_build_string('2025', '31550'))
        self.assertEqual([x['name'] for x in meta['inputs']], ['in1'])
        self.assertEqual(meta['outputs'][0]['width'], 1080)
        self.assertEqual(meta['pars'][0]['page'], 'Look')
        self.assertEqual(meta['pars'][0]['pars'][0], {'name': 'Speed', 'label': 'Speed', 'style': 'Float',
                                                      'default': 1.0, 'value': 2.0})
        where = {(f['op'], f['par']): (f['where'], f['exists']) for f in meta['files']}
        self.assertEqual(where[('clip', 'file')], ('outside', False))
        self.assertEqual(where[('glsl_src', 'file')], ('repo', True))
        self.assertEqual(len(r['outside_files']), 1)
        self.assertEqual(meta['sha256'], L.sha256_file(os.path.join(d, 'GN_demo.tox')))
        self.assertTrue(meta['in_git'])
        self.assertEqual(meta['doc'], os.path.join('docs', 'builds', 'demo.md'))
        txt = rd(os.path.join(d, 'README.md'))
        self.assertIn('Line one of the doc.', txt)
        self.assertNotIn('not in the readme', txt)
        self.assertIn('### Look', txt)
        self.assertIn('/Users/x/Movies/clip.mov', txt)
        idx = json.loads(rd(os.path.join(self.lib, 'index.json')))
        self.assertEqual([i['name'] for i in idx['items']], ['GN_demo'])
        self.assertIn('GN_demo', rd(os.path.join(self.lib, 'INDEX.md')))
        self.assertTrue(r['thumb']['ok'])

    def test_cooking_comp_stays_cooking_and_lane_refused(self):
        self.look.allowCooking = True
        r = run_pending(L.cmd_library_export('/lab/GN_demo', name='Demo2', version='1.0.0', root=self.lib))
        self.assertTrue(self.look.allowCooking)
        self.assertEqual((r['name'], r['version'], r['reparked']), ('Demo2', '1.0.0', False))
        with open(os.path.join(self.repo, 'logs', 'active_lanes.json'), 'w') as f:
            json.dump({'/lab/GN_demo': {'agent': 'other lane'}}, f)
        with self.assertRaises(ValueError) as e:
            L.cmd_library_export('/lab/GN_demo', root=self.lib)
        self.assertIn('other lane', str(e.exception))
        self.assertTrue(isinstance(L.cmd_library_export('/lab/GN_demo', root=self.lib, force=True), handlers.Pending))

    def test_thumb_false_never_unparks(self):
        r = L.cmd_library_export('/lab/GN_demo', root=self.lib, thumb=False)
        self.assertIsInstance(r, dict, 'no Pending: nothing to wait for')
        self.assertFalse(self.look.allowCooking)
        self.assertEqual(self.look.op('out1').cooks, 0)
        self.assertFalse(r['thumb']['ok'])
        self.assertTrue(os.path.isfile(r['tox']))

    def test_big_tox_gitignored(self):
        old = L.BIG_TOX
        L.BIG_TOX = 10
        try:
            r = run_pending(L.cmd_library_export('/lab/GN_demo', root=self.lib))
        finally:
            L.BIG_TOX = old
        self.assertFalse(r['in_git'])
        self.assertIn('/GN_demo/GN_demo.tox', rd(os.path.join(self.lib, '.gitignore')))

    def test_list_info_load(self):
        run_pending(L.cmd_library_export('/lab/GN_demo', root=self.lib))
        self.assertEqual(L.cmd_library_list(root=self.lib)['count'], 1)
        i = L.cmd_library_info('GN_demo', root=self.lib)
        self.assertTrue(i['tox_present'] and i['sha_ok'])
        self.assertIn('Line one', i['readme'])
        test = Node(self.lab, '_libtest')
        r = L.cmd_library_load('GN_demo', '/lab/_libtest', newname='copy1', root=self.lib)
        c = OPS['/lab/_libtest/copy1']
        self.assertFalse(c.allowCooking, 'lands parked')
        self.assertTrue(c.viewer and c.op('out1').viewer)
        self.assertEqual(c.par.Speed.eval(), 2.0, 'custom par value kept')
        self.assertTrue(r['sha_ok'] and r['parked'])
        self.assertIn('notes', r)  # the clip par pointed at a missing file
        with self.assertRaises(ValueError):
            L.cmd_library_load('GN_demo', '/lab/_libtest', newname='copy1', root=self.lib)
        with self.assertRaises(ValueError):
            L.cmd_library_info('Nope', root=self.lib)
        self.assertIsNotNone(test)


class Registration(unittest.TestCase):
    def test_commands_and_sets(self):
        for c in ('library_export', 'library_list', 'library_info', 'library_load'):
            self.assertIn(c, handlers.COMMANDS)
        self.assertIn('library_load', handlers.MUTATING)
        self.assertIn('library_load', handlers.PRESAVE_CMDS)
        self.assertNotIn('library_export', handlers.MUTATING)
        self.assertIn('loads a .tox', S.risk_reasons('library_load', {}, set()))
        old = handlers.LIBRARY_DIR
        handlers.LIBRARY_DIR = TD_DIR
        try:
            m = handlers._library()
            self.assertTrue(hasattr(m, 'cmd_library_export'))
            self.assertIs(handlers._library(), m, 'cached until the mtime changes')
        finally:
            handlers.LIBRARY_DIR = old
        rd(os.path.join(TD_DIR, 'library.py')).encode('ascii')  # pure ASCII (rule 1)


if __name__ == '__main__':
    unittest.main()
