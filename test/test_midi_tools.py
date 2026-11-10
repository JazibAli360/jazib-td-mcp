"""Offline tests for the MIDI mapping TD side: td/midi_runtime.py + the midi_* commands in td/handlers.py.

No TouchDesigner, no MIDI hardware: a fake op tree (tables, custom pages, Text DAT modules executed from their text)
and the REAL td/midi_core.py (lane A). Every message goes through runtime.on_receive with raw bytes, the same entry
the MIDI In DAT callback uses; one test calls the callback DAT text itself.
"""
import json
import os
import shutil
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_handlers as TH  # noqa: E402  (installs the stub td module and imports handlers)

handlers = TH.handlers
TD = sys.modules['td']
TD_DIR = TH.TD_DIR


# ---------------------------------------------------------------- fakes

class Cell(object):
    def __init__(self, val):
        self.val = val


class Par(object):
    def __init__(self, owner, name, val=0, style='Float', menu=None, normMin=0.0, normMax=1.0, default=None):
        self.owner, self.name, self.style = owner, name, style
        self.menuNames = list(menu or [])
        self.menuLabels = list(menu or [])
        self.val = val
        self.default = val if default is None else default
        self.normMin, self.normMax = normMin, normMax
        self.mode = TH.ParMode.CONSTANT
        self.expr = ''
        self.bindExpr = ''
        self.pulsed = 0
        self.isMenu = style in ('Menu', 'StrMenu')
        self.isPulse = style == 'Pulse'

    def eval(self):
        return self.val

    def pulse(self):
        self.pulsed += 1

    @property
    def menuIndex(self):
        return self.menuNames.index(self.val) if self.val in self.menuNames else 0

    @menuIndex.setter
    def menuIndex(self, i):
        self.val = self.menuNames[int(i)]


class Pars(object):
    def __init__(self):
        object.__setattr__(self, '_d', {})

    def __getitem__(self, k):
        return self._d.get(k)

    def __getattr__(self, k):
        try:
            return self._d[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):  # op.par.X = v sets the value, like TD
        self._d[k].val = v

    def add(self, p):
        self._d[p.name] = p
        return p


class Page(object):
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def _add(self, name, style, val, menu=None):
        p = self.owner.par.add(Par(self.owner, name, val, style, menu))
        self.owner.customPars.append(p)
        return [p]

    def appendToggle(self, name, label=None):
        return self._add(name, 'Toggle', False)

    def appendPulse(self, name, label=None):
        return self._add(name, 'Pulse', False)

    def appendInt(self, name, label=None, size=1):
        return self._add(name, 'Int', 0)

    def appendFloat(self, name, label=None, size=1):
        return self._add(name, 'Float', 0.0)

    def appendStr(self, name, label=None):
        return self._add(name, 'Str', '')

    def appendMenu(self, name, label=None):
        return self._add(name, 'Menu', '', menu=[])


PARS = {  # built-in pars the builder sets (names from TD's offline help, 2025.31550 app)
    'midiinDAT': [('active', True, 'Toggle'), ('id', 1, 'Int'), ('callbacks', '', 'Str'), ('bytes', False, 'Toggle')],
    'midioutCHOP': [('active', True, 'Toggle'), ('id', 1, 'Int'), ('destination', 'device', 'Menu'),
                    ('onebased', False, 'Toggle'), ('controlnorm', '0to1', 'Menu'), ('notenorm', '0to1', 'Menu'),
                    ('cookalways', False, 'Toggle')],
    'executeDAT': [('framestart', False, 'Toggle')],
    'parameterexecuteDAT': [('op', '', 'Str'), ('pars', '', 'Str'), ('onpulse', False, 'Toggle'),
                            ('valuechange', True, 'Toggle')],
    'containerCOMP': [('w', 100, 'Int'), ('h', 100, 'Int')],
    'textCOMP': [('x', 0, 'Int'), ('y', 0, 'Int'), ('w', 100, 'Int'), ('h', 100, 'Int'), ('text', '', 'Str'),
                 ('alignx', 'center', 'Menu'), ('fontsize', 20, 'Float')],
    'listCOMP': [('x', 0, 'Int'), ('y', 0, 'Int'), ('w', 100, 'Int'), ('h', 100, 'Int'), ('rows', 3, 'Int'),
                 ('cols', 3, 'Int'), ('callbacks', '', 'Str'), ('lockfirstrow', False, 'Toggle'),
                 ('vscrollbar', True, 'Toggle'), ('reset', False, 'Pulse')],
    'annotateCOMP': [(n, '', 'Str') for n in ('Mode', 'Titletext', 'Bodytext', 'Backcolorr', 'Backcolorg',
                                                'Backcolorb')],
    'windowCOMP': [('winop', '', 'Str'), ('title', '', 'Str'), ('size', 'automatic', 'Menu'), ('winw', 0, 'Int'),
                   ('winh', 0, 'Int'), ('winopen', False, 'Pulse')],
}
MENUS = {'destination': ['device', 'file'], 'controlnorm': ['off', '0to1', '-1to1', 'onoff'],
         'notenorm': ['off', '0to1'], 'size': ['automatic', 'fill', 'custom', 'exclusive'],
         'alignx': ['left', 'center', 'right']}
REG = {}  # path -> op


class FOp(object):
    def __init__(self, parent, name, optype):
        self._parent, self.name, self.OPType = parent, name, optype
        self.path = (parent.path.rstrip('/') + '/' + name) if parent is not None else name
        self.family = next((f for f in ('DAT', 'CHOP', 'TOP', 'COMP', 'SOP') if optype.endswith(f)), 'COMP')
        self.isCOMP = self.family == 'COMP'
        self.valid, self.viewer, self.dock, self.comment = True, False, None, ''
        self.nodeX = self.nodeY = 0
        self.nodeWidth, self.nodeHeight = 130, 90
        self.inputConnectors, self.outputConnectors = [], []
        self.children, self.customPages, self.customPars = [], [], []
        self.par = Pars()
        for n, v, st in PARS.get(optype, []):
            self.par.add(Par(self, n, v, st, MENUS.get(n)))
        self._text, self._mod = '', (None, None)
        self.rows_ = []
        self.sent = []
        self.cooks = 0
        self._store = {}
        REG[self.path] = self

    # --- OP
    def __setattr__(self, k, v):
        if k == 'name' and getattr(self, '_parent', None) is not None and 'path' in self.__dict__:
            REG.pop(self.path, None)  # a rename moves the path, like TD
            object.__setattr__(self, 'path', self._parent.path.rstrip('/') + '/' + v)
            REG[self.path] = self
        object.__setattr__(self, k, v)

    def parent(self, n=1):
        o = self
        for _ in range(n):
            o = o._parent
        return o

    def cook(self, force=False):
        self.cooks += 1

    def destroy(self):
        self.valid = False
        REG.pop(self.path, None)
        if self._parent is not None:
            self._parent.children = [k for k in self._parent.children if k is not self]

    def store(self, k, v):
        self._store[k] = v

    def fetch(self, k, d=None, search=False):
        return self._store.get(k, d)

    def unstore(self, k):
        self._store.pop(k, None)

    def errors(self):
        return ''

    warnings = errors

    # --- COMP
    def op(self, name):
        if name.startswith('/'):
            o = REG.get(name)
            return o if o is not None and o.valid else None
        o = self
        for part in name.split('/'):
            o = next((k for k in o.children if k.name == part and k.valid), None)
            if o is None:
                return None
        return o

    def create(self, cls, name=None):
        if name is None:
            name = '%s%d' % (cls.__name__[:-4], len(self.children) + 1)
        o = (FComp if cls.__name__.endswith('COMP') else FOp)(self, name, cls.__name__)
        if cls.__name__ == 'tableDAT':
            o.rows_ = [['']]  # like TD 2025.31550: a new Table DAT holds one blank cell, not zero rows
        self.children.append(o)
        return o

    def appendCustomPage(self, name):
        p = Page(self, name)
        self.customPages.append(p)
        return p

    # --- DAT
    @property
    def text(self):
        if self.OPType == 'tableDAT':
            return '\n'.join('\t'.join(r) for r in self.rows_)
        return self._text

    @text.setter
    def text(self, t):
        self._text = t

    @property
    def module(self):
        if self._mod[0] != self._text:
            m = types.ModuleType('dat_' + self.name)
            exec(compile(self._text, self.path, 'exec'), m.__dict__)
            self._mod = (self._text, m)
        return self._mod[1]

    @property
    def numRows(self):
        return len(self.rows_)

    def rows(self):
        return [[Cell(v) for v in r] for r in self.rows_]

    def clear(self):
        self.rows_ = []

    def appendRow(self, r):
        self.rows_.append([str(v) for v in r])

    def deleteRow(self, i):
        del self.rows_[i]

    def _ri(self, r):
        if isinstance(r, int):
            return r if r < len(self.rows_) else None
        return next((i for i, row in enumerate(self.rows_) if row and row[0] == r), None)

    def __getitem__(self, rc):
        i = self._ri(rc[0])
        if i is None or rc[1] >= len(self.rows_[i]):
            return None
        return Cell(self.rows_[i][rc[1]])

    def __setitem__(self, rc, v):
        self.rows_[self._ri(rc[0])][rc[1]] = str(v)

    # --- MIDI Out CHOP
    def sendControl(self, ch, num, val):
        self.sent.append(('cc', ch, num, val))

    def sendNoteOn(self, ch, num, val):
        self.sent.append(('noteon', ch, num, val))

    def sendNoteOff(self, ch, num, val=0):
        self.sent.append(('noteoff', ch, num, val))

    def sendPitchBend(self, ch, val):
        self.sent.append(('pb', ch, val))


class FComp(FOp):
    pass


OPTYPES = ('baseCOMP', 'textDAT', 'tableDAT', 'midiinDAT', 'midioutCHOP', 'executeDAT', 'parameterexecuteDAT',
           'containerCOMP', 'textCOMP', 'listCOMP', 'windowCOMP', 'annotateCOMP')


class Clock(object):
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def strftime(self, *a):
        return '00:00:00'


class MidiBase(unittest.TestCase):
    def setUp(self):
        REG.clear()
        self.saved = {}
        for n in OPTYPES:
            cls = type(n, (), {})
            setattr(TD, n, cls)
            setattr(handlers, n, cls)
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, 'td')
        os.makedirs(self.src)
        for f in ('midi_core.py', 'midi_runtime.py'):
            shutil.copy(os.path.join(TD_DIR, f), self.src)
        handlers.MIDI_DIR = self.src
        self.proj = os.path.join(self.tmp, 'proj')
        os.makedirs(self.proj)
        self._folder = handlers.project.folder
        handlers.project.folder = self.proj
        self._op = handlers.op
        handlers.op = lambda p: REG.get(p)
        self.root = FComp(None, '/project1', 'baseCOMP')
        self.root.path = '/project1'
        REG['/project1'] = self.root
        REG['/'] = FComp(None, '/', 'baseCOMP')
        self.look = self.root.create(TD.baseCOMP, 'look')
        for p in (Par(self.look, 'Gain', 0.0, 'Float', normMin=0.0, normMax=10.0),
                  Par(self.look, 'Count', 0, 'Int', normMin=0, normMax=4),
                  Par(self.look, 'On', False, 'Toggle'),
                  Par(self.look, 'Fire', False, 'Pulse'),
                  Par(self.look, 'Shape', 'a', 'Menu', menu=['a', 'b', 'c', 'd'])):
            self.look.par.add(p)
        r = handlers.cmd_midi_build('/project1/jazib_midi')
        self.build = r
        self.c = REG['/project1/jazib_midi']
        self.rt = self.c.op('runtime').module
        self.clock = Clock()
        self.rt.time = self.clock

    def tearDown(self):
        handlers.MIDI_DIR = None
        handlers.project.folder = self._folder
        handlers.op = self._op
        for n in OPTYPES:
            for m in (TD, handlers):
                if hasattr(m, n):
                    delattr(m, n)
        for m in (TD, handlers):
            if hasattr(m, 'ui'):
                delattr(m, 'ui')
        REG.clear()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sim(self, **kw):
        return handlers.cmd_midi_simulate('/project1/jazib_midi', **kw)

    def map(self, **kw):
        return handlers.cmd_midi_map('/project1/jazib_midi', kw)['mapping']

    def frames(self, n, dt=1 / 60.0):
        for _ in range(n):
            self.clock.t += dt
            self.rt.on_frame(self.c)


# ---------------------------------------------------------------- pure helpers

class Pure(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, TD_DIR)
        import midi_runtime
        self.rt = midi_runtime

    def test_bytes_round_trip(self):
        rt = self.rt
        self.assertEqual(rt.sim_bytes('cc', 2, 7, 64), [[0xB1, 7, 64]])
        self.assertEqual(rt.event_args([0xB1, 7, 64]), ('cc', 2, 7, 64, None))
        self.assertEqual(rt.event_args([0x90, 60, 0])[0], 'noteoff')
        self.assertEqual(rt.event_args([0x80, 60, 30]), ('noteoff', 1, 60, 0, None))
        self.assertEqual(rt.sim_bytes('pitchbend', 1, 0, 16383), [[0xE0, 127, 127]])
        self.assertEqual(rt.event_args([0xE0, 0, 64]), ('pitchbend', 1, 0, 0, 64))
        self.assertEqual(rt.sim_bytes('cc14', 1, 1, 16383), [[0xB0, 1, 127], [0xB0, 33, 127]])
        self.assertEqual(rt.event_args([0xD0, 5]), ('aftertouch', 1, -1, 5, None))
        self.assertEqual(rt.event_args([0xC3, 9]), ('program', 4, 9, 0, None))
        self.assertIsNone(rt.event_args([0xF8]))
        self.assertEqual(rt.decode_bytes('b0 07 40'), [0xB0, 7, 64])
        self.assertEqual(rt.decode_bytes(bytes([0x90, 1, 2])), [0x90, 1, 2])
        with self.assertRaises(ValueError):
            rt.sim_bytes('sysex', 1)

    def test_files_ascii_and_compile(self):
        for f in ('midi_runtime.py',):
            with open(os.path.join(TD_DIR, f), encoding='utf-8') as fh:
                t = fh.read()
            t.encode('ascii')
            compile(t, f, 'exec')
        for t in (handlers.MIDI_CB, handlers.MIDI_TICK, handlers.MIDI_PAREXEC, handlers.MIDI_LIST_CB):
            t.encode('ascii')
            compile(t, 'cb', 'exec')
            self.assertNotIn('jazib_mcp', t)

    def test_midi_file_policy(self):
        old = handlers.project.folder
        d = tempfile.mkdtemp()
        handlers.project.folder = d
        try:
            rd = os.path.realpath(d)
            self.assertEqual(handlers.midi_file('show.json'), os.path.join(rd, 'midi_maps', 'show.json'))
            self.assertEqual(handlers.midi_file('maps/a.json', write=True), os.path.join(rd, 'maps', 'a.json'))
            for bad in ('x.txt', '', '../../etc/x.json', '/etc/x.json'):
                with self.assertRaises(ValueError):
                    handlers.midi_file(bad, write=True)
            self.assertEqual(handlers.midi_file('/etc/x.json'), os.path.realpath('/etc/x.json'))  # load may read anywhere
        finally:
            handlers.project.folder = old
            shutil.rmtree(d)

    def test_commands_registered(self):
        for c in ('midi_build', 'midi_status', 'midi_learn', 'midi_map', 'midi_unmap', 'midi_list', 'midi_bank',
                  'midi_save', 'midi_load', 'midi_monitor', 'midi_simulate', 'midi_preset'):
            self.assertIn(c, handlers.COMMANDS)
        for c in ('midi_build', 'midi_learn', 'midi_map', 'midi_unmap', 'midi_bank', 'midi_load', 'midi_simulate',
                  'midi_preset'):
            self.assertIn(c, handlers.MUTATING)
        for c in ('midi_status', 'midi_list', 'midi_monitor', 'midi_save'):
            self.assertNotIn(c, handlers.MUTATING)


# ---------------------------------------------------------------- build

class Build(MidiBase):
    def test_self_contained_comp(self):
        c = self.c
        names = sorted(k.name for k in c.children)
        for n in ('midi_core', 'runtime', 'bindings', 'config', 'events', 'midi_in', 'midi_cb', 'midi_out', 'tick',
                  'par_exec', 'editor', 'editor_window'):
            self.assertIn(n, names)
        for dat, f in (('midi_core', 'midi_core.py'), ('runtime', 'midi_runtime.py')):
            with open(os.path.join(TD_DIR, f)) as fh:
                self.assertEqual(c.op(dat).text, fh.read())
        for k in c.children + c.op('editor').children:
            if k.family == 'DAT' and k.OPType == 'textDAT':
                self.assertNotIn('/jazib_mcp', k.text, k.name)
        mi = c.op('midi_in')
        self.assertEqual((mi.par.callbacks.val, mi.par.bytes.val), ('midi_cb', True))
        self.assertEqual(mi.par.active.expr, 'parent().par.Enable')
        self.assertEqual(mi.par.active.mode, TH.ParMode.EXPRESSION)
        self.assertIs(c.op('midi_cb').dock, mi)
        mo = c.op('midi_out')
        self.assertEqual((mo.par.controlnorm.val, mo.par.notenorm.val, mo.par.onebased.val, mo.par.cookalways.val),
                         ('off', 'off', False, True))
        self.assertTrue(c.op('tick').par.framestart.val)
        pe = c.op('par_exec')
        self.assertEqual((pe.par.op.val, pe.par.pars.val), ('..', 'Learn Activebank Sendfeedback Openeditor '
                                                                     'Refreshdevices'))
        self.assertEqual(c.op('editor/list').par.callbacks.val, 'list_cb')
        self.assertEqual(c.op('editor_window').par.winop.val, 'editor')
        for n in ('Enable', 'Device', 'Activebank', 'Learn', 'Feedback', 'Sendfeedback', 'Openeditor',
                  'Refreshdevices'):
            self.assertIsNotNone(c.par[n], n)
        self.assertEqual((c.par.Enable.val, c.par.Activebank.val, c.par.Feedback.val), (True, 1, True))
        self.assertEqual(c.par.Device.menuNames, ['1'])  # no device table in the fake
        self.assertEqual(c.op('bindings').rows_[0], self.rt.core(c).FIELDS)
        self.assertEqual(c.op('config')['active_bank', 1].val, '1')
        self.assertTrue(self.build['created'])
        self.assertNotIn('notes', self.build, self.build.get('notes'))
        self.assertEqual(self.build['layout'], {'ok': True})  # stage boxes: MIDI in, Engine, Data, LED feedback, Controls
        self.assertEqual(sorted(k.name for k in c.children if k.OPType == 'annotateCOMP'),
                         ['stage_Controls', 'stage_Data', 'stage_Engine', 'stage_LED_feedback', 'stage_MIDI_in'])
        for k in c.children:
            if k.family in ('DAT', 'CHOP'):
                self.assertTrue(k.viewer, k.name)

    def test_rebuild_keeps_bindings_and_reads_devices(self):
        self.map(target='/project1/look', par='Gain', kind='cc', channel=1, number=7)
        dev = FOp(REG['/'], 'local/midi/device', 'tableDAT')
        dev.path = '/local/midi/device'
        REG[dev.path] = dev
        dev.rows_ = [['id', 'indevice', 'outdevice'], ['1', 'IAC Bus 1', 'IAC Bus 1'], ['2', 'nanoKONTROL2', '']]
        r = handlers.cmd_midi_build('/project1/jazib_midi', device='nano')
        self.assertFalse(r['created'])
        self.assertEqual(r['mappings'], 1)
        self.assertEqual(r['device'], '2')
        self.assertEqual(self.c.par.Device.menuLabels, ['1: IAC Bus 1', '2: nanoKONTROL2'])
        st = handlers.cmd_midi_status('/project1/jazib_midi')
        self.assertEqual(len(st['devices']), 2)
        r2 = handlers.cmd_midi_build('/project1/jazib_midi', device='Launchpad')
        self.assertIn('not in the MIDI Device Mapper', ' '.join(r2['notes']))

    def test_refusals(self):
        with self.assertRaises(ValueError):
            handlers.cmd_midi_build('jazib_midi')
        with self.assertRaises(ValueError):
            handlers.cmd_midi_status('/project1/look')  # not a midi COMP
        handlers.MIDI_DIR = os.path.join(self.tmp, 'nowhere')
        with self.assertRaises(IOError):
            handlers.cmd_midi_build('/project1/m2')
        self.assertIsNone(REG.get('/project1/m2'), 'nothing built when the code files are missing')


# ---------------------------------------------------------------- engine through simulate

class Engine(MidiBase):
    def test_absolute_cc_and_callback_path(self):
        m = self.map(target='/project1/look', par='Gain', kind='cc', channel=1, number=7)
        self.assertEqual((m['min'], m['max'], m['bank'], m['label']), (0.0, 10.0, 1, 'look.Gain'))
        r = self.sim(kind='cc', channel=1, number=7, value=127)
        self.assertEqual(r['writes'][0]['id'], m['id'])
        self.assertEqual(self.look.par.Gain.val, 10.0)
        self.sim(kind='cc', channel=2, number=7, value=0)  # other channel: no match
        self.assertEqual(self.look.par.Gain.val, 10.0)
        ns = {}
        exec(compile(handlers.MIDI_CB, 'midi_cb', 'exec'), ns)  # the MIDI In DAT's own callback text
        ns['onReceiveMIDI'](self.c.op('midi_in'), 1, 'Control Change', 1, 7, 0, True, bytes([0xB0, 7, 0]))
        self.assertEqual(self.look.par.Gain.val, 0.0)
        ns['onReceiveMIDI'](self.c.op('midi_in'), 1, 'Control Change', 1, 7, 127, True, None)  # no bytes: row parse
        self.assertEqual(self.look.par.Gain.val, 10.0)
        # TD's own template names the last argument byteData: a keyword call must work too
        ns['onReceiveMIDI'](dat=self.c.op('midi_in'), rowIndex=1, message='Control Change', channel=1, index=7,
                            value=0, input=True, byteData=bytes([0xB0, 7, 0]))
        self.assertEqual(self.look.par.Gain.val, 0.0)
        ev = handlers.cmd_midi_monitor('/project1/jazib_midi', 4)['events']
        self.assertEqual([e['src'] for e in ev], ['sim', 'midi', 'midi', 'midi'])
        self.assertEqual(ev[-1]['hits'], m['id'])

    def test_pickup_takeover(self):
        self.look.par.Gain.val = 5.0
        self.map(target='/project1/look', par='Gain', number=1, takeover='pickup')
        r = self.sim(number=1, value=10)
        self.assertEqual((r['writes'], self.look.par.Gain.val), ([], 5.0))
        self.sim(number=1, value=127)  # crossed the par's position -> picked up
        self.assertEqual(self.look.par.Gain.val, 10.0)
        self.sim(number=1, value=0)
        self.assertEqual(self.look.par.Gain.val, 0.0)
        self.look.par.Gain.val = 5.0  # moved elsewhere -> the 10 Hz poll resets pickup
        self.frames(6)
        self.sim(number=1, value=120)
        self.assertEqual(self.look.par.Gain.val, 5.0)

    def test_relative_int_menu_toggle_pulse(self):
        self.map(target='/project1/look', par='Count', number=2, mode='relative_2c', step=0.25)
        for _ in range(3):
            self.sim(number=2, value=1)
        self.assertEqual(self.look.par.Count.val, 3)
        self.sim(number=2, value=127)
        self.assertEqual(self.look.par.Count.val, 2)
        self.map(target='/project1/look', par='Shape', number=3)
        self.sim(number=3, value=127)
        self.assertEqual(self.look.par.Shape.val, 'd')
        self.map(target='/project1/look', par='On', kind='note', number=60, mode='toggle')
        self.sim(kind='note', number=60, value=100)
        self.sim(kind='noteoff', number=60)
        self.assertIs(self.look.par.On.val, True)
        self.sim(kind='note', number=60, value=100)
        self.assertIs(self.look.par.On.val, False)
        self.map(target='/project1/look', par='Fire', kind='note', number=61, mode='trigger')
        self.sim(kind='note', number=61, value=127)
        self.sim(kind='noteoff', number=61)
        self.assertEqual(self.look.par.Fire.pulsed, 1)

    def test_cc14_and_pitchbend(self):
        self.map(target='/project1/look', par='Gain', kind='cc14', number=1)
        self.sim(kind='cc14', number=1, value=16383)
        self.assertEqual(self.look.par.Gain.val, 10.0)
        self.sim(kind='cc14', number=1, value=8192)
        self.assertAlmostEqual(self.look.par.Gain.val, 5.0, 2)
        self.map(target='/project1/look', par='Count', kind='pitchbend')
        self.sim(kind='pitchbend', value=16383)
        self.assertEqual(self.look.par.Count.val, 4)

    def test_banks(self):
        a = self.map(target='/project1/look', par='Gain', number=5, bank=2)
        self.map(target='/project1/look', par='Count', number=5, bank=0)
        self.sim(number=5, value=127)
        self.assertEqual((self.look.par.Gain.val, self.look.par.Count.val), (0.0, 4))
        r = handlers.cmd_midi_bank('/project1/jazib_midi', 2)
        self.assertEqual((r['active_bank'], r['banks']), (2, [2]))
        self.assertIn(a['id'], r['live'])
        self.sim(number=5, value=127)
        self.assertEqual(self.look.par.Gain.val, 10.0)
        with self.assertRaises(ValueError):
            handlers.cmd_midi_bank('/project1/jazib_midi', 0)
        self.assertEqual(handlers.cmd_midi_list('/project1/jazib_midi', bank=2)['count'], 1)

    def test_disabled_and_exported(self):
        self.map(target='/project1/look', par='Gain', number=9)
        self.c.par.Enable.val = False
        self.sim(number=9, value=127)
        self.assertEqual(self.look.par.Gain.val, 0.0)
        self.c.par.Enable.val = True
        self.look.par.Gain.mode = TH.ParMode.EXPORT
        r = self.sim(number=9, value=127)
        self.assertEqual((r['writes'], self.look.par.Gain.val), ([], 0.0))
        self.assertIn('exported', handlers.cmd_midi_monitor('/project1/jazib_midi', 1)['events'][0]['note'])

    def test_feedback_on_outside_change_and_relative_echo(self):
        m = self.map(target='/project1/look', par='Gain', number=11, feedback=True)
        self.frames(6)  # first poll records the value
        self.look.par.Gain.val = 5.0
        self.frames(6)
        self.assertEqual(self.c.op('midi_out').sent[-1], ('cc', 1, 11, 64))
        n = len(self.c.op('midi_out').sent)
        self.sim(number=11, value=127)  # absolute: our own write is not echoed (motor faders)
        self.frames(6)
        self.assertEqual(len(self.c.op('midi_out').sent), n)
        self.c.par.Feedback.val = False
        self.look.par.Gain.val = 1.0
        self.frames(6)
        self.assertEqual(len(self.c.op('midi_out').sent), n)
        self.c.par.Feedback.val = True
        self.map(id=m['id'], mode='relative_bin', step=0.1)
        self.sim(number=11, value=65)
        self.assertEqual(self.c.op('midi_out').sent[-1][:3], ('cc', 1, 11))  # LED ring follows the encoder
        self.assertGreater(self.rt.send_all_feedback(self.c), 0)

    def test_feedback_send_error_never_aborts(self):
        # live 31550: MIDI Out CHOP send* raise tdError when no device is behind it
        mo = self.c.op('midi_out')

        def boom(*a):
            raise RuntimeError('Cannot communicate with the MIDI device.')
        mo.sendControl = boom
        m1 = self.map(target='/project1/look', par='Count', number=13, mode='relative_bin', step=0.25, feedback=True)
        m2 = self.map(target='/project1/look', par='Gain', number=13, feedback=True)
        r = self.sim(number=13, value=65)
        self.assertEqual(sorted(w['id'] for w in r['writes']), sorted([m1['id'], m2['id']]))
        self.assertNotIn('errors', r)
        self.assertIn('feedback not sent', handlers.cmd_midi_status('/project1/jazib_midi')['last_error'])
        self.look.par.Gain.val = 2.0
        self.frames(12)  # poll -> feedback -> raises inside: the tick keeps going
        self.assertIn('feedback not sent', handlers.cmd_midi_status('/project1/jazib_midi')['last_error'])

    def test_smoothing(self):
        self.map(target='/project1/look', par='Gain', number=12, smooth=0.05)
        r = self.sim(number=12, value=127)
        self.assertIn('smoothing_to', r['writes'][0])
        self.frames(1)
        g1 = self.look.par.Gain.val
        self.assertTrue(0.0 < g1 < 10.0, g1)
        self.frames(120)
        self.assertEqual(self.look.par.Gain.val, 10.0)
        self.assertEqual(self.rt.status(self.c)['smoothing'], [])

    def test_errors_never_raise_in_callback(self):
        self.c.op('bindings').rows_ = [['id', 'number'], ['x', 'notanumber']]
        r = self.rt.on_receive(self.c, None, None, None, None, [0xB0, 1, 1])
        self.assertIn('error', r)
        st = handlers.cmd_midi_status('/project1/jazib_midi')
        self.assertIn('ValueError', st['last_error'])
        self.assertIn('ValueError', st['bindings_error'])


# ---------------------------------------------------------------- learn

class Learn(MidiBase):
    P = '/project1/jazib_midi'

    def test_par_learn_absolute(self):
        r = handlers.cmd_midi_learn(self.P, target='/project1/look', par='Gain', curve='ease_in')
        self.assertEqual((r['state'], r['mode']), ('listening', 'par'))
        s = self.sim(events=[{'number': 20, 'value': v} for v in (10, 20, 30)])
        self.assertEqual((s['writes'], self.look.par.Gain.val), ([], 0.0))  # learning does not drive pars
        self.frames(40)  # learn window (0.5 s) passes
        st = handlers.cmd_midi_learn(self.P, action='status')
        self.assertEqual(st['state'], 'done')
        m = st['mapping']
        self.assertEqual((m['kind'], m['channel'], m['number'], m['mode'], m['curve'], m['max']),
                         ('cc', 1, 20, 'absolute', 'ease_in', 10.0))
        handlers.cmd_midi_learn(self.P, target='/project1/look', par='Gain')
        self.sim(number=21, value=5)
        handlers.cmd_midi_learn(self.P, action='finish')
        ms = handlers.cmd_midi_list(self.P)['mappings']
        self.assertEqual([(x['id'], x['number']) for x in ms], [(m['id'], 21)], 're-learn replaces the binding')

    def test_encoder_button_and_auto_finish(self):
        handlers.cmd_midi_learn(self.P, target='/project1/look', par='Count')
        self.sim(events=[{'number': 30, 'value': v} for v in (1, 1, 127)])
        self.assertEqual(handlers.cmd_midi_learn(self.P, action='finish')['mapping']['mode'], 'relative_2c')
        handlers.cmd_midi_learn(self.P, target='/project1/look', par='Fire')
        r = self.sim(events=[{'kind': 'note', 'number': 40, 'value': 127}, {'kind': 'noteoff', 'number': 40}] * 6)
        self.assertEqual(r['learn']['state'], 'done')  # 12 messages: classified at once
        self.assertEqual(r['learn']['mapping']['mode'], 'trigger')  # button on a Pulse par

    def test_hover_and_slot_learn_and_timeout(self):
        self.assertEqual(handlers.cmd_midi_learn(self.P)['available'], False)  # no ui in this build
        ui = types.SimpleNamespace(rolloverPar=None)
        handlers.ui = ui
        TD.ui = ui
        handlers.cmd_midi_learn(self.P)  # hover
        self.sim(number=50, value=3)
        self.frames(40)
        st = handlers.cmd_midi_learn(self.P, action='status')
        self.assertEqual(st['state'], 'listening')
        self.assertIn('hover', st['note'])
        ui.rolloverPar = self.look.par.Gain
        self.sim(number=50, value=4)
        self.frames(40)
        st = handlers.cmd_midi_learn(self.P, action='status')
        self.assertEqual((st['state'], st['mapping']['par'], st['mapping']['number']), ('done', 'Gain', 50))
        handlers.cmd_midi_learn(self.P, id=st['mapping']['id'])  # slot: new message for the same mapping
        self.sim(number=51, value=9)
        self.assertEqual(handlers.cmd_midi_learn(self.P, action='finish')['mapping']['number'], 51)
        handlers.cmd_midi_learn(self.P, target='/project1/look', par='Gain')
        self.clock.t += 31
        self.frames(1)
        self.assertEqual(handlers.cmd_midi_learn(self.P, action='status')['state'], 'timeout')
        with self.assertRaises(ValueError):
            handlers.cmd_midi_learn(self.P, target='/project1/look', par='Nope')

    def test_learn_wait_replies_when_done(self):
        handlers._PENDING.clear()
        calls, out = [], []
        handlers._runner = lambda script, frames: calls.append(frames)
        try:
            handlers.dispatch(json.dumps({'id': 5, 'cmd': 'midi_learn', 'args': {
                'path': self.P, 'target': '/project1/look', 'par': 'Gain', 'wait_s': 5}}),
                lambda t: out.append(json.loads(t)))
            self.assertEqual((out, calls), ([], [15]))
            handlers._finish(5)
            self.assertEqual(out, [])  # still listening: polls again
            self.sim(events=[{'number': 3, 'value': v} for v in range(12)])
            handlers._finish(5)
            self.assertTrue(out[0]['ok'], out)
            self.assertEqual(out[0]['result']['state'], 'done')
        finally:
            handlers._runner = None

    def test_learn_pulse_par_and_bank_par(self):
        self.rt.on_par(self.c, 'Learn')  # no ui: hover learn starts anyway (runtime side)
        self.assertEqual(self.rt.cfg(self.c, 'learn_state'), 'listening')
        self.rt.on_par(self.c, 'Learn')
        self.assertEqual(self.rt.cfg(self.c, 'learn_state'), 'stopped')
        self.c.par.Activebank.val = 3
        self.rt.on_par(self.c, 'Activebank')
        self.assertEqual(self.rt.cfg(self.c, 'active_bank'), '3')
        self.rt.on_par(self.c, 'Openeditor')
        self.assertEqual(self.c.op('editor_window').par.winopen.pulsed, 1)


# ---------------------------------------------------------------- files, presets, editor

class Data(MidiBase):
    P = '/project1/jazib_midi'

    def test_save_load_unmap(self):
        a = self.map(target='/project1/look', par='Gain', number=1)
        b = self.map(target='/project1/look', par='Count', number=2, bank=2)
        r = handlers.cmd_midi_save(self.P, 'show.json')
        self.assertTrue(r['file'].endswith(os.path.join('midi_maps', 'show.json')))
        with open(r['file']) as fh:
            data = json.load(fh)
        self.assertEqual(len(data['mappings']), 2)
        u = handlers.cmd_midi_unmap(self.P, ids=[a['id'], 'zz'])
        self.assertEqual((u['removed'], u['missing']), ([a['id']], ['zz']))
        handlers.cmd_midi_unmap(self.P, target='/project1/look')
        self.assertEqual(handlers.cmd_midi_list(self.P)['count'], 0)
        r = handlers.cmd_midi_load(self.P, 'show.json')
        self.assertEqual(r['mappings'], 2)
        self.assertEqual({m['id'] for m in handlers.cmd_midi_list(self.P)['mappings']}, {a['id'], b['id']})
        self.sim(number=1, value=127)
        self.assertEqual(self.look.par.Gain.val, 10.0)
        with self.assertRaises(ValueError):
            handlers.cmd_midi_save(self.P, '../escape.json')
        with self.assertRaises(ValueError):
            handlers.cmd_midi_unmap(self.P)

    def test_map_validation(self):
        with self.assertRaises(ValueError):
            self.map(target='/project1/look', par='Gain', mode='spin')
        with self.assertRaises(ValueError):
            self.map(target='/project1/look', par='Nope')
        with self.assertRaises(ValueError):
            self.map(target='look', par='Gain')
        with self.assertRaises(ValueError):
            self.map(colour='red')
        m = self.map(target='/project1/look', par='Gain', number=4)
        m2 = self.map(id=m['id'], max=2.0)
        self.assertEqual((m2['max'], m2['number']), (2.0, 4))

    def test_preset_slots(self):
        lst = handlers.cmd_midi_preset(self.P)
        self.assertIn('generic_8x8', lst['presets'])
        r = handlers.cmd_midi_preset(self.P, 'generic_8x8')
        self.assertEqual(len(r['added']), 16)
        st = handlers.cmd_midi_status(self.P)
        self.assertEqual(len(st['unbound']), 16)
        self.sim(number=0, value=127)  # unbound slots do nothing
        handlers.cmd_midi_map(self.P, {'id': r['added'][0], 'target': '/project1/look', 'par': 'Gain'})
        self.sim(number=0, value=127)
        self.assertEqual(self.look.par.Gain.val, 10.0)
        with self.assertRaises(ValueError):
            handlers.cmd_midi_preset(self.P, 'nope')

    def test_editor(self):
        rt, c = self.rt, self.c
        self.assertIn('no mappings', rt.editor_cell(c, 1, 1))
        m = self.map(target='/project1/look', par='Gain', number=7, channel=1)
        lst = c.op('editor/list')
        self.assertEqual((lst.par.rows.val, lst.par.cols.val), (2, len(rt.EDITOR_COLS)))
        self.assertEqual(rt.editor_cell(c, 0, 3), 'msg')
        self.assertEqual(rt.editor_cell(c, 1, 3), 'cc ch1 #7')
        self.assertEqual(rt.editor_cell(c, 1, 4), '/project1/look.Gain')
        rt.editor_edit(c, 1, rt.EDITOR_COLS.index('max'), '4')
        self.assertEqual(rt.find(c, m['id'])['max'], 4.0)
        rt.editor_edit(c, 1, rt.EDITOR_COLS.index('mode'), 'bogus')  # refused, error noted, mapping unchanged
        self.assertEqual(rt.find(c, m['id'])['mode'], 'absolute')
        self.assertIn('editor mode', rt.cfg(c, 'last_error'))
        rt.editor_select(c, 1, rt.EDITOR_COLS.index('learn'))
        self.assertEqual((rt.cfg(c, 'learn_mode'), rt.cfg(c, 'learn_id')), ('slot', m['id']))
        m2 = self.map(target='/project1/look', par='Count', number=8, channel=1)
        dl = rt.EDITOR_COLS.index('del')
        rt.editor_select(c, 1, dl)
        self.assertEqual([x['id'] for x in rt.mappings(c)], [m2['id']])
        self.clock.t += 1 / 60.0
        rt.editor_select(c, 1, dl)  # onSelect again in the same press: row 1 is now m2, it must stay
        self.assertEqual([x['id'] for x in rt.mappings(c)], [m2['id']])
        self.clock.t += 1.0
        rt.editor_select(c, 1, dl)  # a new click later deletes
        self.assertEqual(rt.mappings(c), [])
        self.assertIn('bank 1', c.op('editor/header').par.text.val)
        ns = {}
        exec(compile(handlers.MIDI_LIST_CB, 'list_cb', 'exec'), ns)
        attribs = types.SimpleNamespace()
        ns['onInitCell'](lst, 0, 0, attribs)
        self.assertEqual(attribs.text, 'id')

    def test_dispatch_status(self):
        out = []
        handlers.dispatch(json.dumps({'id': 1, 'cmd': 'midi_status', 'args': {'path': self.P}}),
                          lambda t: out.append(json.loads(t)))
        self.assertTrue(out[0]['ok'], out)
        r = out[0]['result']
        for k in ('enable', 'device', 'active_bank', 'mappings', 'learn', 'last_events', 'devices', 'midi_in'):
            self.assertIn(k, r)
        self.assertIn('MIDI Device Mapper', r['hint'])


if __name__ == '__main__':
    unittest.main()
