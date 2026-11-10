"""Offline tests for the Ableton commands in td/handlers.py (td_link, td_tda, td_live_audio); no TD, no Live.

Run from jazib-td-mcp/:  python3 -I -m unittest discover -s test -p 'test_*.py'
Reuses the stub `td` module from test_handlers (imported first).
"""
import inspect
import json
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from test_handlers import OP, OPS, FakePar, FakeParCollection, handlers  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OPS_JSON = os.path.join(os.path.dirname(HERE), 'docs', 'research', 'ops', 'ops_CHOP_2025.31550.json')


def _pc_getattr(self, k):
    d = self.__dict__.get('_d', {})
    if k in d:
        return d[k]
    raise AttributeError(k)


def _pc_setattr(self, k, v):
    d = self.__dict__.get('_d')
    if d is not None and k in d:
        d[k].val = v  # like TD: par.name = v sets the value
    else:
        object.__setattr__(self, k, v)


FakeParCollection.__getattr__ = _pc_getattr  # TD-style o.par.name access for these tests
FakeParCollection.__setattr__ = _pc_setattr


class Chan(object):
    def __init__(self, name, v):
        self.name, self.v = name, v

    def eval(self):
        return self.v


class Node(OP):
    nodeX = nodeY = 0
    nodeWidth, nodeHeight = 130, 90

    def __init__(self, path, optype='nullCHOP', family='CHOP', pars=(), n_in=1):
        OP.__init__(self, path, optype, family, n_in=n_in, pars=pars)
        self.viewer = False
        self.chan_vals = {}
        self.destroyed = False

    def chans(self):
        return [Chan(k, v) for k, v in self.chan_vals.items()]

    def cook(self, force=False):
        pass

    def destroy(self):
        self.destroyed = True

    @property
    def inputs(self):
        return [c.connections[0].owner for c in self.inputConnectors if c.connections]


class Comp(Node):
    def __init__(self, path):
        Node.__init__(self, path, 'baseCOMP', 'COMP', n_in=0)
        self.isCOMP = True
        self.kids = {}

    def op(self, name):
        return self.kids.get(name) or next((k for k in self.children if k.name == name), None)

    def create(self, cls, name):
        o = cls(self.path.rstrip('/') + '/' + name)
        self.kids[name] = o
        self.children.append(o)
        OPS[o.path] = o
        return o

    def loadTox(self, file):
        self.loaded = file
        return self.create(TdaPackage, 'tdAbletonPackage')


def par_list(*names):
    return [{'name': n} for n in names]


def chop_class(optype, pars, n_in=1):
    return type(optype, (Node,), {'__init__': lambda self, path: Node.__init__(self, path, optype, 'CHOP',
                                                                               par_list(*pars), n_in)})


LINK_PARS = ('active', 'enable', 'startstopsync', 'status', 'ramp', 'bar', 'beat', 'tempo', 'phase')
STUBS = {
    'abletonlinkCHOP': chop_class('abletonlinkCHOP', LINK_PARS, 0),
    'selectCHOP': chop_class('selectCHOP', ('channames', 'renamefrom', 'renameto')),
    'renameCHOP': chop_class('renameCHOP', ('renamefrom', 'renameto')),
    'nullCHOP': chop_class('nullCHOP', ('cooktype',)),
    'infoCHOP': chop_class('infoCHOP', ('op', 'infotype')),
    'switchCHOP': chop_class('switchCHOP', ('index',), 2),
    'audiodeviceinCHOP': chop_class('audiodeviceinCHOP', ('active', 'device', 'driver'), 0),
    'baseCOMP': type('baseCOMP', (Comp,), {}),
}
TDA_MASTER_PARS = ('Connect', 'Listenonly', 'Abletonaddress', 'Abletonport', 'Inport', 'Maxport', 'Suppresspopupdialogs',
                   'Abletonbroadcast', 'Startonload', 'Version', 'Install', 'Installtdableton', 'Updateabletoncomps',
                   'Start', 'Autostartlive')


class TdaPackage(Comp):
    def __init__(self, path):
        Comp.__init__(self, path)
        m = Node(path + '/tdAbleton', 'baseCOMP', 'COMP', par_list(*TDA_MASTER_PARS), n_in=0)
        m.par['Connect'].val = True  # its default (tdAbleton.cparm)
        m.par['Abletonaddress'].val = '127.0.0.1'
        m.par['Version'].val = '2.6.3'
        self.kids['tdAbleton'] = m


def install_stubs():
    for k, v in STUBS.items():
        setattr(handlers.td, k, v)


class LinkPlan(unittest.TestCase):
    def test_plan_defaults_and_names(self):
        plan = handlers.plan_link()
        self.assertEqual([p[0] for p in plan], ['link1', 'sel', 'ren', 'out', 'info'])
        link = plan[0]
        self.assertEqual(link[1], 'abletonlinkCHOP')
        self.assertIs(link[2]['enable'], False)
        self.assertIs(handlers.plan_link(True)[0][2]['enable'], True)
        self.assertEqual(plan[2][2], {'renamefrom': 'ramp numpeers', 'renameto': 'bar_ramp peers'})
        self.assertEqual(sorted(b for _, b in handlers.LINK_OUT), ['bar', 'bar_ramp', 'beat', 'peers', 'tempo'])

    def test_plan_pars_exist_in_31550_dump(self):
        with open(OPS_JSON) as f:
            dump = dict((o['type'], set(p['name'] for p in o['pars'])) for o in json.load(f)['dumped'])
        for name, optype, pars, _src in handlers.plan_link(True):
            self.assertIn(optype, dump, optype)
            self.assertFalse(set(pars) - dump[optype], (optype, set(pars) - dump[optype]))
        self.assertIn('index', dump['switchCHOP'])  # live_audio's src_sel

    def test_summary(self):
        r = handlers.link_summary({'beat': 2, 'bar': 3, 'bar_ramp': 0.5, 'tempo': 120.0, 'peers': 1},
                                  {'numpeers': 1, 'linked': 1, 'synced': 1, 'ramp': 0.5},
                                  {'ableton_tempo': 120.0, 'other': 9}, True)
        self.assertEqual(r['out']['tempo'], 120.0)
        self.assertEqual(r['status'], {'numpeers': 1, 'linked': 1, 'synced': 1})
        self.assertEqual(r['info'], {'ableton_tempo': 120.0})
        self.assertNotIn('missing', r)
        self.assertNotIn('hint', r)
        off = handlers.link_summary({}, {'ramp': 0}, {}, False)
        self.assertEqual(off['missing'], ['beat', 'bar', 'bar_ramp', 'tempo', 'peers'])
        self.assertEqual(off['link_channels'], ['ramp'])
        self.assertIn('enable:true', off['hint'])
        self.assertIn('no Link peers', handlers.link_summary({'peers': 0}, {'numpeers': 0}, {}, True)['hint'])


class LinkBuild(unittest.TestCase):
    def setUp(self):
        OPS.clear()
        install_stubs()
        self.root = Comp('/project1')
        OPS['/project1'] = self.root

    def test_build_then_enable(self):
        r = handlers.cmd_link()
        self.assertTrue(r['built'])
        comp = self.root.op('link')
        link, sel, ren, out, info = [comp.op(n) for n in ('link1', 'sel', 'ren', 'out', 'info')]
        self.assertIs(link.par['enable'].val, False)
        self.assertEqual((sel.inputs, ren.inputs, out.inputs), ([link], [sel], [ren]))
        self.assertEqual(info.par['op'].val, '/project1/link/link1')
        self.assertTrue(all(o.viewer for o in (link, sel, ren, out, info)))
        self.assertIn('hint', r)
        out.chan_vals = {'beat': 1, 'bar': 2, 'bar_ramp': 0.25, 'tempo': 100, 'peers': 1}
        r = handlers.cmd_link(enable=True)
        self.assertFalse(r['built'])
        self.assertIs(link.par['enable'].val, True)
        self.assertEqual(r['out']['tempo'], 100.0)
        self.assertEqual(handlers.cmd_link_status('/project1/link')['out']['peers'], 1.0)

    def test_existing_other_comp_refused(self):
        self.root.create(STUBS['baseCOMP'], 'link')
        with self.assertRaises(ValueError):
            handlers.cmd_link()

    def test_registration(self):
        for c in ('link', 'live_audio', 'tda_load'):
            self.assertIn(c, handlers.MUTATING)
        for c in ('link_status', 'tda_check', 'tda_status'):
            self.assertNotIn(c, handlers.MUTATING)
            self.assertIn(c, handlers.COMMANDS)


CFG = '''<Ableton><ContentLibrary/>
\t\t<UserLibrary>
\t\t\t<LibraryProject Id="0">
\t\t\t\t<ProjectName Value="User Library" />
\t\t\t\t<ProjectPath Value="{}" />
\t\t\t</LibraryProject>
\t\t</UserLibrary></Ableton>'''


class Tda(unittest.TestCase):
    def setUp(self):
        OPS.clear()
        install_stubs()
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.samples = os.path.join(t, 'Samples')
        pal = os.path.join(self.samples, 'Palette', 'TDAbleton', 'Live 11+')
        scr = os.path.join(self.samples, 'TDAbleton', 'Live 11+', 'TouchDesigner')
        os.makedirs(pal)
        os.makedirs(scr)
        for f in ('tdAbletonPackage.tox', 'abletonSong.tox'):
            open(os.path.join(pal, f), 'w').close()
        with open(os.path.join(scr, 'TDA.py'), 'w') as f:
            f.write("import sys\nTDA_VERSION = '2.6.3'\nDEFAULT_RECEIVE_PORT = 58888\n")
        self.home = os.path.join(t, 'home')
        self.prefs = os.path.join(self.home, 'Library', 'Preferences', 'Ableton')
        self.lib = os.path.join(t, 'Music', 'Ableton', 'User Library')
        os.makedirs(os.path.join(self.lib, 'Remote Scripts', 'AbletonMCP'))
        for v in ('Live 11.3.2', 'Live 12.4.3'):
            os.makedirs(os.path.join(self.prefs, v))
        with open(os.path.join(self.prefs, 'Live 12.4.3', 'Library.cfg'), 'w') as f:
            f.write(CFG.format(os.path.dirname(self.lib)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_pure(self):
        self.assertEqual(handlers.tda_version_from_py("x\nTDA_VERSION = '2.6.3'\n"), '2.6.3')
        self.assertIsNone(handlers.tda_version_from_py('nothing'))
        self.assertEqual(handlers.pick_live_prefs(['Live 9.7', 'Live 12.4.3', 'Live 12.10.1', 'Other']), 'Live 12.10.1')
        self.assertIsNone(handlers.pick_live_prefs([]))
        self.assertEqual(handlers.user_library_from_cfg(CFG.format('/Users/u/Music/Ableton')),
                         '/Users/u/Music/Ableton/User Library')
        self.assertIsNone(handlers.user_library_from_cfg('<x/>'))
        self.assertEqual(handlers.dup_names(['a', 'b', 'a', 'a', 'c', 'b']), ['a', 'b'])

    def test_check_not_installed(self):
        r = handlers.tda_check(samples=self.samples, palette='/nope', home=self.home)
        self.assertTrue(r['palette'].endswith('Live 11+'))
        self.assertEqual((r['palette_toxes'], r['version']), (2, '2.6.3'))
        self.assertEqual(r['user_library'], self.lib)
        self.assertIn('Library.cfg (read only)', r['user_library_from'])
        self.assertFalse(r['remote_script_installed'])
        self.assertTrue(r['abletonmcp_installed'])
        self.assertFalse(r['ready'])
        self.assertTrue(any('Install button' in c for c in r['checks']))
        self.assertTrue(any('0.0.0.0' in c for c in r['checks']))

    def test_check_installed_and_mismatch(self):
        inst = os.path.join(self.lib, 'Remote Scripts', 'TouchDesigner')
        os.makedirs(inst)
        with open(os.path.join(inst, 'TDA.py'), 'w') as f:
            f.write("TDA_VERSION = '2.6.3'\n")
        self.assertTrue(handlers.tda_check(samples=self.samples, home=self.home)['ready'])
        with open(os.path.join(inst, 'TDA.py'), 'w') as f:
            f.write("TDA_VERSION = '2.5.0'\n")
        r = handlers.tda_check(samples=self.samples, home=self.home)
        self.assertFalse(r['ready'])
        self.assertTrue(any('mismatch' in c for c in r['checks']))

    def test_check_reads_only(self):
        before = sorted(os.walk(self.tmp.name))
        cfg = os.path.join(self.prefs, 'Live 12.4.3', 'Library.cfg')
        mtime = os.path.getmtime(cfg)
        handlers.tda_check(samples=self.samples, home=self.home)
        self.assertEqual(sorted(os.walk(self.tmp.name)), before)
        self.assertEqual(os.path.getmtime(cfg), mtime)

    def test_load_needs_accept_risk(self):
        r = handlers.cmd_tda_load()
        self.assertFalse(r['loaded'])
        self.assertIn('runCode', r['why'])
        self.assertIn('0.0.0.0', r['why'])

    def test_load_safe_pars_never_install(self):
        root = Comp('/project1')
        OPS['/project1'] = root
        handlers.app.samplesFolder = self.samples
        try:
            r = handlers.cmd_tda_load(accept_risk=True)
        finally:
            del handlers.app.samplesFolder
        self.assertTrue(r['loaded'])
        self.assertTrue(root.loaded.endswith('tdAbletonPackage.tox'))
        m = root.op('tda').op('tdAbleton')
        self.assertEqual(r['master'], m.path)
        self.assertIs(m.par['Connect'].val, False)
        self.assertIs(m.par['Listenonly'].val, True)
        self.assertEqual(m.par['Abletonaddress'].val, '127.0.0.1')
        self.assertEqual(r['set'][0], 'Connect')
        for k in handlers.TDA_NEVER:
            self.assertEqual((m.par[k].val, m.par[k].pulsed), (0, 0), k)
        st = handlers.cmd_tda_status(r['path'])
        self.assertEqual((st['master'], st['pars']['Listenonly'], st['version']), (m.path, True, '2.6.3'))

    def test_static_never_touches_install_or_library_cfg(self):
        self.assertEqual([k for k, _ in handlers.tda_load_pars(True)][0], 'Connect')
        self.assertFalse(set(k for k, _ in handlers.tda_load_pars(True)) & set(handlers.TDA_NEVER))
        src = inspect.getsource(handlers.cmd_tda_load) + inspect.getsource(handlers.tda_check)
        for k in handlers.TDA_NEVER:
            self.assertNotIn("'" + k + "'", src)
            self.assertNotIn('.' + k, src)
        for fn in (handlers.tda_check, handlers.tda_user_library, handlers._read_text, handlers._tda_dirs):
            s = inspect.getsource(fn)
            self.assertNotRegex(s, r"open\([^)]*['\"][wa]")
            self.assertNotRegex(s, r'\.write\(|shutil|copytree|os\.(remove|rename|makedirs)')


class LiveAudio(unittest.TestCase):
    def setUp(self):
        OPS.clear()
        install_stubs()
        self.ac = Comp('/project1/lab/AC_audio')
        OPS[self.ac.path] = self.ac
        src = self.ac.create(chop_class('audiofileinCHOP', ('file', 'play')), 'src')
        trim = self.ac.create(chop_class('mathCHOP', ('gain',)), 'trim')
        trim.inputConnectors[0].connect(src.outputConnectors[0])
        self.src, self.trim = src, trim

    def test_pure(self):
        self.assertEqual(handlers.loopback_names(['MacBook Pro Microphone', 'BlackHole 2ch', 'Aggregate Device']),
                         ['BlackHole 2ch', 'Aggregate Device'])
        d = tempfile.mkdtemp()
        open(os.path.join(d, 'BlackHole2ch.driver'), 'w').close()
        open(os.path.join(d, 'readme.txt'), 'w').close()
        self.assertEqual(handlers.hal_drivers((d, '/no/such')), ['BlackHole2ch.driver'])

    def test_device_built_inactive_then_activated_then_file(self):
        r = handlers.cmd_live_audio(mode='device')
        sel, dev = self.ac.op('src_sel'), self.ac.op('src_device')
        self.assertEqual(r['built'], ['src_sel', 'src_device'])
        self.assertIs(dev.par['active'].val, False)
        self.assertEqual(sel.par['index'].val, 0)
        self.assertEqual(r['source'], 'file')
        self.assertEqual((sel.inputs, self.trim.inputs), ([self.src, dev], [sel]))
        self.assertIn('blackhole', r['loopback'])
        r = handlers.cmd_live_audio(mode='device', activate=True)
        self.assertEqual((r['built'], r['source'], dev.par['active'].val, sel.par['index'].val), ([], 'device', True, 1))
        self.assertEqual(len(sel.inputs), 2)
        r = handlers.cmd_live_audio(mode='file')
        self.assertEqual((r['source'], dev.par['active'].val, sel.par['index'].val), ('file', False, 0))

    def test_wire_failure_rolls_back(self):
        one_input = chop_class('switchCHOP', ('index',), 1)
        handlers.td.switchCHOP = one_input
        try:
            with self.assertRaises(RuntimeError):
                handlers.cmd_live_audio(mode='device')
        finally:
            handlers.td.switchCHOP = STUBS['switchCHOP']
        self.assertTrue(self.ac.op('src_sel').destroyed and self.ac.op('src_device').destroyed)
        self.assertEqual(self.trim.inputs, [self.src])

    def test_errors(self):
        with self.assertRaises(ValueError):
            handlers.cmd_live_audio(mode='mic')
        with self.assertRaises(ValueError):
            handlers.cmd_live_audio(mode='file', file='/no/such.wav')
        other = Comp('/project1/x')
        OPS[other.path] = other
        with self.assertRaises(ValueError):
            handlers.cmd_live_audio(path='/project1/x')


if __name__ == '__main__':
    unittest.main()
