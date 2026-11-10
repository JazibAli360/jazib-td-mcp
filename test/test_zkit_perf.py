"""Offline perf tests for the zkit runtime (builders/zkit_rt.py) on a fake TD (no TouchDesigner needed).

The fake implements only what zk_rt touches (Table DATs, pars, Text/GLSL TOP pars, the panel's mouse values) and
counts every write, so the tests can pin how much work one mouse event / one synced par change does: DAT cell writes,
table clears, Text TOP spec rewrites, segments rebuilt. Timing is printed by the bench, not asserted tightly.
Run: cd <repo> && python3 -I -m unittest discover -s test -p 'test_zkit_perf.py'
Bench (prints ms per event): python3 -I test/test_zkit_perf.py bench [path/to/zkit_rt.py]
"""
import importlib.util
import os
import random
import statistics
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDERS = os.path.join(os.path.dirname(HERE), 'builders')
RT_FILE = os.path.join(BUILDERS, 'zkit_rt.py')
LOGIC_FILE = os.path.join(BUILDERS, 'zkit_logic.py')


# ---------------------------------------------------------------- fake TD
class Counter(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self.cells = {}          # table name -> cell writes
        self.clears = {}         # table name -> clear() calls
        self.rows = {}           # table name -> appended rows
        self.pars = {}           # 'owner.par' -> writes

    def add(self, d, k, n=1):
        d[k] = d.get(k, 0) + n

    def total_cells(self, prefix=''):
        return sum(v for k, v in self.cells.items() if k.startswith(prefix))

    def touched(self, prefix=''):
        """Tables (by name prefix) that saw any write."""
        out = set()
        for d in (self.cells, self.clears, self.rows):
            out |= set(k for k, v in d.items() if v and k.startswith(prefix))
        return out


C = Counter()


class ParMode(object):
    CONSTANT, EXPRESSION, EXPORT, BIND = 'CONSTANT', 'EXPRESSION', 'EXPORT', 'BIND'


class Cell(object):
    __slots__ = ('val',)

    def __init__(self, v):
        self.val = str(v)


def _s(v):
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, float):
        return repr(v) if v != int(v) or abs(v) >= 1e15 else (str(int(v)) if float(int(v)) == v else repr(v))
    return str(v)


class Table(object):
    OPType = 'tableDAT'

    def __init__(self, name, rows=None):
        self.name = name
        self.data = [[Cell('')]] if rows is None else [[Cell(_s(v)) for v in r] for r in rows]

    @property
    def numRows(self):
        return len(self.data)

    @property
    def numCols(self):
        return max([len(r) for r in self.data] or [0])

    def _ri(self, r):
        if isinstance(r, int):
            return r if 0 <= r < len(self.data) else None
        for i, row in enumerate(self.data):
            if row and row[0].val == str(r):
                return i
        return None

    def _ci(self, c):
        if isinstance(c, int):
            return c
        if not self.data:
            return None
        for i, cell in enumerate(self.data[0]):
            if cell.val == str(c):
                return i
        return None

    def __getitem__(self, rc):
        r, c = rc
        ri, ci = self._ri(r), self._ci(c)
        if ri is None or ci is None or ci >= len(self.data[ri]):
            return None
        return self.data[ri][ci]

    def __setitem__(self, rc, v):
        r, c = rc
        ri, ci = self._ri(r), self._ci(c)
        if ri is None or ci is None:
            raise IndexError('%s[%r]' % (self.name, rc))
        row = self.data[ri]
        while len(row) <= ci:
            row.append(Cell(''))
        row[ci].val = _s(v)
        C.add(C.cells, self.name)

    def row(self, key):
        ri = self._ri(key)
        return None if ri is None else self.data[ri]

    def clear(self):
        self.data = []
        C.add(C.clears, self.name)

    def appendRow(self, vals):
        self.data.append([Cell(_s(v)) for v in vals])
        C.add(C.rows, self.name)

    def appendRows(self, rows):
        for r in rows:
            self.data.append([Cell(_s(v)) for v in r])
        C.add(C.rows, self.name, len(rows))

    def deleteRow(self, key):
        ri = self._ri(key)
        if ri is not None:
            del self.data[ri]
            C.add(C.rows, self.name)

    def snapshot(self):
        return [[c.val for c in r] for r in self.data]


class Par(object):
    def __init__(self, owner, name, val=0.0, style='Float', label=None, lo=0.0, hi=1.0, menu=None, tuplet=None):
        self.owner, self.name, self._v, self.style = owner, name, val, style
        self.label = label or name
        self.tupletName = tuplet or name
        self.readOnly = False
        self.isMenu = style in ('Menu', 'StrMenu')
        self.menuNames = list(menu or [])
        self.menuLabels = list(menu or [])
        self.normMin, self.normMax = lo, hi
        self.default = val
        self.mode = ParMode.CONSTANT

    def eval(self):
        return self._v

    @property
    def val(self):
        return self._v

    @val.setter
    def val(self, v):
        self._v = v
        C.add(C.pars, '%s.%s' % (getattr(self.owner, 'name', '?'), self.name))
        if getattr(self.owner, 'on_change', None):
            self.owner.on_change(self)

    @property
    def menuIndex(self):
        try:
            return self.menuNames.index(self._v)
        except ValueError:
            return 0

    @menuIndex.setter
    def menuIndex(self, i):
        self.val = self.menuNames[int(i)]

    def pulse(self):
        C.add(C.pars, '%s.%s' % (getattr(self.owner, 'name', '?'), self.name))

    def __float__(self):
        return float(self._v)

    def __int__(self):
        return int(self._v)


class ParNS(object):
    def __init__(self, owner):
        object.__setattr__(self, '_owner', owner)
        object.__setattr__(self, '_pars', {})

    def add(self, p):
        self._pars[p.name] = p
        return p

    def __getattr__(self, n):
        try:
            return self._pars[n]
        except KeyError:
            raise AttributeError(n)

    def __setattr__(self, n, v):
        p = self._pars.get(n)
        if p is None:
            p = self.add(Par(self._owner, n, v))
        p.val = v


class Simple(object):
    """Any op with a par namespace (Text TOP, GLSL TOP, DAT with .par.active, window)."""

    def __init__(self, name, optype='', **pars):
        self.name, self.OPType = name, optype
        self.par = ParNS(self)
        for k, v in pars.items():
            self.par.add(Par(self, k, v))
        self.valid = True

    def evalTextSize(self, text):
        # Open-Sans-ish at size 20: narrow chars narrower (only proportions matter for the tests)
        w = sum(5.5 if ch in 'il.:,;!|' else 12.0 if ch in 'mwMW' else 10.0 for ch in str(text))
        return (w, 20.0)


class Page(object):
    def __init__(self, name, tuplets):
        self.name, self.parTuplets = name, tuplets


class Host(object):
    OPType = 'baseCOMP'

    def __init__(self, name='HOST'):
        self.name = name
        self.path = '/project1/lab/' + name
        self.valid = True
        self.par = ParNS(self)
        self.customPages = []
        self.children = {}
        self.sync = None             # set to the rt's Sync after load; called after the event like TD does
        self.queue = []

    def on_change(self, par):
        if par.name not in self.queue:
            self.queue.append(par.name)

    def op(self, name):
        return self.children.get(name)

    def openParameters(self):
        pass


class Panel(object):
    OPType = 'containerCOMP'

    def __init__(self, name='controls'):
        self.name = name
        self.par = ParNS(self)
        self.par.add(Par(self, 'w', 100))
        self.par.add(Par(self, 'h', 100))
        self.panel = Simple('panel')
        for k in ('u', 'v'):
            setattr(self.panel, k, 0.0)
        for k in ('shift', 'ctrl', 'cmd', 'alt'):
            setattr(self.panel, k, False)
        self.ops = {}

    def op(self, name):
        return self.ops.get(name)


class Me(object):
    def __init__(self, panel):
        self._p = panel

    def parent(self):
        return self._p


def _load_logic(path):
    spec = importlib.util.spec_from_file_location('zkit_logic_perf', path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


PAGES = {
    'Look': [('Gain%d' % i, 'Float') for i in range(14)] + [('Mode', 'Menu'), ('Mono', 'Toggle'), ('Tint', 'RGB'),
                                                             ('Steps', 'Int')],
    'Motion': [('Speed%d' % i, 'Float') for i in range(12)] + [('Flash', 'Momentary'), ('Reseed', 'Pulse'),
                                                               ('Caption', 'Str'), ('Clip', 'File')],
    'Stage': [('Pos%d' % i, 'Float') for i in range(16)] + [('Preset', 'Menu'), ('Haze', 'Toggle'),
                                                             ('Wash', 'RGB'), ('Count', 'Int')],
    'Out': [('Level%d' % i, 'Float') for i in range(14)] + [('Bypass', 'Toggle'), ('Playhead', 'Float')],
}


def make_panel(rt_file=RT_FILE, logic_file=LOGIC_FILE, pages=None, d=56, cols=8, with_new_ops=True, screen='2056 1329',
               maxh=0, tab='All', cfg=()):
    """A host COMP with ~70 knobs (PV_previz_stage-sized) + a zkit panel. Returns (ns, host, panel).
    screen = zk_cfg 'screen' (points; this MacBook's), maxh = Zkmaxh."""
    pages = PAGES if pages is None else pages
    h = Host()
    for pg, spec in pages.items():
        tups = []
        for name, style in spec:
            if style == 'RGB':
                tups.append([h.par.add(Par(h, name + c, v, 'RGB', name, tuplet=name))
                             for c, v in zip('rgb', (0.9, 0.3, 0.1))])
            elif style == 'Menu':
                tups.append([h.par.add(Par(h, name, 'b', 'Menu', name, menu=['a', 'b', 'c', 'longer item']))])
            elif style == 'Toggle':
                tups.append([h.par.add(Par(h, name, False, 'Toggle', name))])
            elif style == 'Int':
                tups.append([h.par.add(Par(h, name, 3, 'Int', name, lo=0, hi=8))])
            elif style in ('Momentary', 'Pulse'):
                tups.append([h.par.add(Par(h, name, False, style, name))])
            elif style in ('Str', 'File'):
                tups.append([h.par.add(Par(h, name, '/media/demo/clip.mov' if style == 'File' else 'hi', style,
                                           name))])
            else:
                tups.append([h.par.add(Par(h, name, 0.25, 'Float', name, lo=-1.0, hi=1.0))])
        h.customPages.append(Page(pg, tups))
    zk = Page('Zkit', [])
    h.customPages.append(zk)
    h.par.add(Par(h, 'Zktheme', 'night', 'Menu', menu=['night', 'day']))
    h.par.add(Par(h, 'Zkd', d, 'Int'))
    h.par.add(Par(h, 'Zkcols', cols, 'Int'))
    h.par.add(Par(h, 'Zkrandamount', 0.5))
    h.par.add(Par(h, 'Zkmaxh', maxh, 'Int'))
    win = Simple('controls_window', 'windowCOMP')
    win.isOpen = True
    h.children['controls_window'] = win
    P = Panel()
    L = _load_logic(logic_file)
    lg = Simple('zk_logic', 'textDAT')
    lg.module = L
    P.ops['zk_logic'] = lg
    P.ops['zk_cfg'] = Table('zk_cfg', [['key', 'value'], ['target', h.path], ['pages', ''], ['exclude', ''],
                                       ['d', str(d)], ['cols', str(cols)], ['collapsed', '']] +
                               ([['screen', screen]] if screen else []) + ([['tab', tab]] if tab else []) +
                               [list(r) for r in cfg])
    P.ops['zk_props'] = Table('zk_props')
    P.ops['zk_presets'] = Table('zk_presets', [['slot', 'name', 'color', 'data']])
    P.ops['zk_gpu'] = Table('zk_gpu')
    P.ops['zk_tick'] = Simple('zk_tick', 'executeDAT', active=False)
    P.ops['zk_keys'] = Simple('zk_keys', 'keyboardinDAT', active=False)
    P.ops['zk_measure'] = Simple('zk_measure', 'textTOP', fontsizex=20)
    face = Simple('zk_face', 'glslTOP', resolutionw=8, resolutionh=8)
    for k in range(9 if with_new_ops else 8):
        for c in 'xyzw':
            face.par.add(Par(face, 'vec%dvalue%s' % (k, c), 0.0))
    P.ops['zk_face'] = face
    P.ops['zk_comp'] = Simple('zk_comp', 'compositeTOP', resolutionw=8, resolutionh=8)
    for k in range(8):
        P.ops['zk_ts%d' % k] = Table('zk_ts%d' % k)
        P.ops['zk_text%d' % k] = Simple('zk_text%d' % k, 'textTOP', fontsizex=20, resolutionw=8, resolutionh=8)
    if with_new_ops:
        P.ops['zk_tiles'] = Table('zk_tiles')
        for k in range(2):
            P.ops['zk_hs%d' % k] = Table('zk_hs%d' % k)
            P.ops['zk_hot%d' % k] = Simple('zk_hot%d' % k, 'textTOP', fontsizex=20, resolutionw=8, resolutionh=8)
    runs = []

    class _Op(object):
        TDResources = object()

        def __call__(self, path):
            return h if path == h.path else None

    class _Abs(object):
        seconds = 100.0

    class _Proj(object):
        cookRate = 60.0

    ns = {'__name__': 'zk_rt', 'me': Me(P), 'op': _Op(), 'ParMode': ParMode, 'absTime': _Abs(), 'project': _Proj(),
          'run': lambda *a, **k: runs.append((a, k))}
    with open(rt_file) as f:
        exec(compile(f.read(), rt_file, 'exec'), ns)
    ns['_runs'] = runs
    h.sync = ns['Sync']
    ns['Rebuild']()
    deliver(ns, h)
    return ns, h, P


def deliver(ns, h):
    """TD calls zk_sync after the script that set the pars; then the delayed Flush runs one frame later."""
    q, h.queue = h.queue, []
    for n in q:
        ns['Sync'](getattr(h.par, n))
    if ns['_runs']:
        del ns['_runs'][:]
        ns['Flush']()


class Mouse(object):
    def __init__(self, ns, h, P):
        self.ns, self.h, self.P = ns, h, P
        self.u = self.v = 0.0

    def _wh(self):
        return float(self.P.par.w.eval()), float(self.P.par.h.eval())

    def move(self, x, y):
        w, hh = self._wh()
        pn = self.P.panel
        nu, nv = x / w, 1.0 - y / hh
        if nu != pn.u:
            pu, pn.u = pn.u, nu
            self.ns['OnPanel']('u', nu, pu)
            deliver(self.ns, self.h)
        if nv != pn.v:
            pv, pn.v = pn.v, nv
            self.ns['OnPanel']('v', nv, pv)
            deliver(self.ns, self.h)

    def button(self, name, down):
        self.ns['OnPanel'](name, 1 if down else 0, 0 if down else 1)
        deliver(self.ns, self.h)


def knob_centre(ns, iid):
    """View px of a knob (scroll applied); scrolls it into view first when it is off screen."""
    S = ns['S']
    x, y, w, h = S['lay']['items'][iid]
    v = S['lay'].get('view')
    if v is None:                    # an older runtime: no viewport
        return x + w / 2.0, y + h * 0.4
    if not iid.startswith('_') and (y - S['scroll'] < v['hdr'] or y - S['scroll'] + h > v['H']):
        ns['ScrollTo'](y - v['hdr'] - 4)
    if iid.startswith('_'):          # presets bar / tabs: header, never scrolled
        return x + w / 2.0, y + h * 0.4
    return x + w / 2.0, y - S['scroll'] + h * 0.4


# PX_pointfx-sized (main: 432 knobs, a 666 x 6935 px panel before the viewport cap, T-231)
BIG = dict(('Mod%d' % g, [('M%dk%d' % (g, i), 'Float') for i in range(32)] + [('M%dmode' % g, 'Menu'),
                                                                               ('M%don' % g, 'Toggle'),
                                                                               ('M%dcol' % g, 'RGB'),
                                                                               ('M%dn' % g, 'Int')])
           for g in range(12))


def state(P):
    """Everything the GPU sees: instance table, tile table, text spec tables, Text TOP sizes, uniforms, res."""
    out = {}
    for n, o in sorted(P.ops.items()):
        if isinstance(o, Table) and n not in ('zk_cfg', 'zk_props', 'zk_presets'):
            out[n] = o.snapshot()
        elif n.startswith('zk_text') or n.startswith('zk_hot') or n == 'zk_face':
            out[n] = sorted((k, p.eval()) for k, p in o.par._pars.items())
    out['wh'] = (P.par.w.eval(), P.par.h.eval())
    return out


def reset_caches(ns, P):
    """Forget every incremental cache and blank the tables: the next Render is a from-scratch draw."""
    S = ns['S']
    for k in list(S):
        if k in ('gpu_last', 'txt_last', 'uni_last', 'hot_last', 'tiles_last', 'cull_last', 'tw', 'hs_last',
                 'hotsize_last', 'asm_key', 'bkey', 'bmap', 'fs_last'):
            S[k] = {} if k == 'tw' else None
    if 'segs' in S:
        S['segs'] = {}
    for n, o in P.ops.items():
        if isinstance(o, Table) and n not in ('zk_cfg', 'zk_props', 'zk_presets'):
            o.data = [[Cell('')]]


# ---------------------------------------------------------------- tests
class PerEventWork(unittest.TestCase):
    def setUp(self):
        self.ns, self.h, self.P = make_panel()
        self.m = Mouse(self.ns, self.h, self.P)
        self.S = self.ns['S']
        C.reset()

    def test_panel_size_and_knobs(self):
        self.assertGreaterEqual(len(self.S['order']), 70)
        self.assertGreater(self.P.par.w.eval(), 500)

    def test_idle_render_writes_nothing(self):
        self.ns['Render']()
        self.ns['Render']()
        self.assertEqual(C.touched(), set())
        self.assertEqual(C.pars, {})

    def test_drag_one_knob(self):
        x, y = knob_centre(self.ns, 'Gain3')
        self.m.move(x, y)
        self.m.button('lselect', True)
        self.m.move(x, y - 6)                          # past the click tolerance; first change
        C.reset()
        rebuilt = []
        for k in range(1, 21):
            self.ns['S']['stats'] = {'segs': 0}
            self.m.move(x, y - 6 - 3 * k)
            rebuilt.append(self.S['stats']['segs'])
        self.m.button('lselect', False)
        per = C.total_cells('zk_gpu') / 20.0
        self.assertLessEqual(per, 6, C.cells)          # knob u + its value-text box: a few cells, not a column sweep
        self.assertEqual(sum(C.clears.values()), 0, C.clears)
        # the label/value buckets of the other knobs never change while one knob is dragged: only its hot slot does
        self.assertEqual(C.touched('zk_ts'), set(), C.cells)
        self.assertEqual(C.touched('zk_tiles'), set(), C.cells)
        self.assertLessEqual(C.total_cells('zk_hs') / 20.0, 3)
        self.assertEqual(max(rebuilt), 1, rebuilt)      # one segment per event (the dragged knob)
        self.assertEqual(C.pars.get('HOST.Gain3'), 20)  # one par write per move, no echo re-render writes

    def test_horizontal_move_while_dragging_is_free(self):
        x, y = knob_centre(self.ns, 'Gain3')
        self.m.move(x, y)
        self.m.button('lselect', True)
        self.m.move(x, y - 10)
        C.reset()
        for k in range(10):
            self.m.move(x + k + 1, y - 10)
        self.assertEqual(C.touched(), set())
        self.assertEqual(C.pars, {})

    def test_hover_redraws_two_knobs(self):
        ids = ['Gain1', 'Gain2', 'Gain3', 'Gain4']
        self.m.move(*knob_centre(self.ns, ids[0]))
        C.reset()
        for iid in ids[1:]:
            self.S['stats'] = {'segs': 0}
            self.m.move(*knob_centre(self.ns, iid))
            self.assertLessEqual(self.S['stats']['segs'], 2)
        self.assertEqual(C.touched('zk_ts'), set())
        self.assertEqual(C.touched('zk_hs'), set())
        self.assertLessEqual(C.total_cells('zk_gpu'), 3 * 2)   # flags field of old + new knob
        self.assertEqual(C.pars, {})

    def test_external_par_every_frame(self):
        # TL_timeline's playhead: a par moving every frame while the window is open (scrolled into view)
        knob_centre(self.ns, 'Playhead')
        C.reset()
        segs = []
        for f in range(30):
            self.h.par.Playhead.val = -1.0 + f * 0.05
            self.S['stats'] = {'segs': 0}
            deliver(self.ns, self.h)
            segs.append(self.S['stats']['segs'])
        self.assertEqual(max(segs), 1)
        # first change moves the playhead's value text to a hot slot (its bucket rewritten once); then only the slot
        self.assertLessEqual(sum(v for k, v in C.clears.items() if k.startswith('zk_ts')), 1, C.clears)
        C.reset()
        for f in range(10):
            self.h.par.Playhead.val = 0.5 + f * 0.01
            deliver(self.ns, self.h)
        self.assertEqual(C.touched('zk_ts'), set())
        self.assertEqual(C.touched('zk_tiles'), set())
        self.assertLessEqual(C.total_cells('zk_gpu') / 10.0, 6)

    def test_window_closed_draws_nothing(self):
        self.h.children['controls_window'].isOpen = False
        C.reset()
        for f in range(10):
            self.h.par.Playhead.val = f * 0.1
            deliver(self.ns, self.h)
        self.assertEqual(C.touched(), set())
        self.assertTrue(self.S['dirty'])

    def test_own_write_echo_is_free(self):
        x, y = knob_centre(self.ns, 'Pos2')
        self.m.move(x, y)
        self.m.button('lselect', True)
        self.m.move(x, y - 20)
        # the Sync echo of the kit's own write already ran inside move(); a second Flush finds nothing to draw
        C.reset()
        self.ns['Flush']()
        self.assertEqual(C.touched(), set())

    def test_incremental_equals_full_draw(self):
        rng = random.Random(7)
        ids = [i for i in self.S['order']]
        for step in range(40):
            iid = rng.choice(ids)
            x, y = knob_centre(self.ns, iid)
            self.m.move(x, y)
            r = rng.random()
            if r < 0.5:
                self.m.button('lselect', True)
                for k in range(3):
                    self.m.move(x, y - 8 * (k + 1))
                self.m.button('lselect', False)
            elif r < 0.7:
                self.h.par.Playhead.val = rng.uniform(-1, 1)
                deliver(self.ns, self.h)
            elif r < 0.8:
                self.ns['OnPanel']('wheel', 1, 0)
                deliver(self.ns, self.h)
            elif r < 0.9:
                self.m.button('rselect', True)       # properties menu open/close
                self.m.button('rselect', False)
        self.m.move(1, 1)
        if self.S['popup']:
            self.m.button('rselect', True)
        inc = state(self.P)
        reset_caches(self.ns, self.P)
        self.ns['Render']()
        full = state(self.P)
        self.assertEqual(inc, full)


class MoreEvents(unittest.TestCase):
    """Bar, theme, collapse, presets, typing, older panels: the incremental draw still equals a from-scratch draw."""

    def check(self, ns, P):
        inc = state(P)
        reset_caches(ns, P)
        ns['Render']()
        self.assertEqual(inc, state(P))

    def test_presets_theme_collapse_typing(self):
        ns, h, P = make_panel()
        m = Mouse(ns, h, P)
        S = ns['S']
        bx = lambda iid: (S['lay']['items'][iid][0] + 5, S['lay']['items'][iid][1] + 5)
        m.move(*bx('_plus'))
        m.button('lselect', True)
        m.button('lselect', False)                          # store p1
        self.check(ns, P)
        x, y = knob_centre(ns, 'Gain5')
        m.move(x, y)
        m.button('lselect', True)
        m.move(x, y - 40)
        m.button('lselect', False)
        m.move(*bx('_p1'))
        m.button('lselect', True)
        m.move(bx('_p1')[0], bx('_p1')[1] - 50)             # morph back toward p1
        m.button('lselect', False)
        self.check(ns, P)
        h.par.Zktheme.val = 'day'
        deliver(ns, h)
        self.check(ns, P)
        gx, gy, gw, gh, _c = S['lay']['groups']['_g:Motion']
        m.move(gx + 30, gy + 4)
        m.button('lselect', True)                           # collapse Motion
        m.button('lselect', False)
        self.assertNotIn('Speed0', S['lay']['items'])
        h.par.Speed0.val = 0.9                              # a hidden knob's par moving: nothing to draw
        deliver(ns, h)
        self.check(ns, P)
        x, y = knob_centre(ns, 'Pos3')
        m.move(x, y)
        m.button('lselect', True)
        m.button('lselect', False)                          # click = type a value
        self.assertIsNotNone(S['edit'])

        class K(object):
            state = True

            def __init__(self, ch):
                self.key, self.character = ch, ch
        for ch in '0.5':
            ns['Key'](K(ch))
        self.check(ns, P)
        k = K('enter')
        k.character = ''
        ns['Key'](k)
        deliver(ns, h)
        self.assertAlmostEqual(h.par.Pos3.eval(), 0.5)
        self.check(ns, P)

    def test_first_recall_after_build_applies(self):
        # T-157: right after a module add the zk_rt module can be fresh (S empty, Rebuild not run yet): the first
        # Recall applied nothing because the par map was empty. Now it builds the map first.
        ns, h, P = make_panel()
        S, L = ns['S'], P.ops['zk_logic'].module
        P.ops['zk_presets'].appendRow([1, 'p1', L.DEFAULT_COLOR, L.preset_dump({'Gain5': 0.75, 'Haze': True})])
        S['pmap'], S['order'], S['items'] = {}, [], {}       # fresh module state, as after a panel build
        self.assertTrue(ns['Recall'](1))
        self.assertAlmostEqual(h.par.Gain5.eval(), 0.75)
        self.assertTrue(h.par.Haze.eval())
        S['pmap'], S['order'], S['items'] = {}, [], {}
        ns['Store'](2)                                       # Store from a fresh state stores the values too
        self.assertAlmostEqual(ns['preset'](2)['Gain5'], 0.75)

    def test_older_panel_without_new_ops(self):
        ns, h, P = make_panel(with_new_ops=False)          # a panel built before this pass: no tiles / hot TOPs
        m = Mouse(ns, h, P)
        x, y = knob_centre(ns, 'Gain3')
        m.move(x, y)
        m.button('lselect', True)
        for k in range(5):
            m.move(x, y - 5 * (k + 1))
        m.button('lselect', False)
        self.assertEqual(P.ops['zk_face'].par.vec0valuew.eval(), 0)    # shader falls back to all instances
        inc = state(P)
        reset_caches(ns, P)
        ns['Render']()
        self.assertEqual(inc, state(P))

    @unittest.skipUnless(os.path.isdir(os.path.join(os.path.dirname(HERE), '.git')), 'needs the git history')
    def test_same_picture_as_before_the_perf_pass(self):
        """The 26 Oct rollout runtime (commit 643a043) and this one draw the same instances and text for the same
        events (except the tcol 'u' field, which now names the text input, and value text moved to hot slots)."""
        import subprocess
        import tempfile
        try:
            old = subprocess.check_output(['git', '-C', os.path.dirname(HERE), 'show', '643a043:builders/zkit_rt.py'])
        except Exception:
            self.skipTest('commit 643a043 not available')
        d = tempfile.mkdtemp()
        p = os.path.join(d, 'zkit_rt_old.py')
        with open(p, 'wb') as f:
            f.write(old)

        small = {'Look': [('Gain%d' % i, 'Float') for i in range(5)] + [('Mode', 'Menu'), ('Tint', 'RGB'),
                                                                         ('Playhead', 'Float')]}

        def run(rt, new):
            # one page that fits on screen and fills one row: no tabs, no scrolling, nothing to balance, so the new
            # viewport runtime must draw exactly what the rollout runtime drew
            ns, h, P = make_panel(rt, with_new_ops=new, pages=small)
            m = Mouse(ns, h, P)
            snaps = []
            x, y = knob_centre(ns, 'Gain3')
            m.move(x, y)
            m.button('lselect', True)
            for k in range(5):
                m.move(x, y - 7 * (k + 1))
            m.button('lselect', False)
            snaps.append(state(P))
            m.move(*knob_centre(ns, 'Gain2'))
            m.button('rselect', True)
            m.button('rselect', False)
            snaps.append(state(P))
            m.button('rselect', True)
            m.button('rselect', False)
            h.par.Playhead.val = 0.77
            h.par.Zktheme.val = 'day'
            deliver(ns, h)
            snaps.append(state(P))
            return snaps

        def norm(st):
            rows = [r[:] for r in st['zk_gpu']]
            for c in range(1, len(rows[8])):
                if rows[8][c] == '16':
                    rows[7][c] = '0'
            txt = sorted(tuple(r) for n, t in st.items() if n.startswith('zk_ts') or n.startswith('zk_hs')
                         for r in t[1:] if r and r != [''])
            return rows, txt, st['wh']
        try:
            for a, b in zip(run(p, False), run(RT_FILE, True)):
                self.assertEqual(norm(a), norm(b))
        finally:
            os.remove(p)
            os.rmdir(d)


class Viewport(unittest.TestCase):
    """Pages + scroll (28 Oct, T-231): capped textures, tabs, scrolling, offset hit tests, culling."""

    def setUp(self):
        self.ns, self.h, self.P = make_panel(pages=BIG)
        self.m = Mouse(self.ns, self.h, self.P)
        self.S = self.ns['S']
        self.L = self.P.ops['zk_logic'].module
        C.reset()

    def sizes(self):
        P, L = self.P, self.L
        cap = L.viewport_cap(0, (2056, 1329))
        out = {'panel': (P.par.w.eval(), P.par.h.eval()), 'cap': cap}
        for n, o in P.ops.items():
            if n.startswith('zk_text') or n.startswith('zk_hot') or n == 'zk_face':
                out[n] = (o.par.resolutionw.eval(), o.par.resolutionh.eval())
        out['inst'] = P.ops['zk_gpu'].numCols - 1
        out['tiles'] = P.ops['zk_tiles'].numCols - 1
        return out

    def assert_capped(self):
        z = self.sizes()
        cw, ch = z['cap']
        self.assertLessEqual(z['panel'][0], cw)
        self.assertLessEqual(z['panel'][1], ch)
        for n, wh in z.items():
            if n.startswith('zk_'):
                w, h = wh
                self.assertLessEqual(w, min(cw, self.L.TEX_CAP), n)
                if n == 'zk_face':                          # the face = the viewport
                    self.assertLessEqual(h, min(ch, self.L.TEX_CAP), n)
                else:                                       # text = the stage band: <= 2 views, <= the cap
                    self.assertLessEqual(h, min(2 * ch, self.L.TEX_CAP), n)
        self.assertLessEqual(4 * z['inst'], self.L.TEX_CAP)
        self.assertLessEqual(z['tiles'], self.L.TEX_CAP)
        return z

    def test_textures_capped(self):
        self.assertEqual(len(self.S['order']), 432)
        z = self.assert_capped()
        self.assertGreater(self.S['lay']['h'], 3 * z['panel'][1])               # content far taller than the view
        self.assertEqual(z['zk_face'], z['panel'])
        self.h.par.Zkmaxh.val = 500                                            # the user's cap
        deliver(self.ns, self.h)
        self.assertEqual(self.P.par.h.eval(), 500)
        self.assert_capped()
        self.h.par.Zkd.val = 160                                               # big knobs: fewer columns, still capped
        deliver(self.ns, self.h)
        self.assert_capped()
        self.h.par.Zkd.val = 24
        self.h.par.Zkmaxh.val = 0
        deliver(self.ns, self.h)
        self.assert_capped()

    def test_tab_filter_and_memory(self):
        x, y = knob_centre(self.ns, '_t:Mod3')
        self.m.move(x, y)
        self.m.button('lselect', True)
        self.m.button('lselect', False)
        self.assertEqual(self.P.ops['zk_cfg']['tab', 1].val, 'Mod3')
        self.assertEqual(set(self.S['draw']), set(i for i in self.S['order'] if i.startswith('M3')))
        self.assertEqual(len(self.S['order']), 432)                            # presets still see every page
        self.assertEqual(list(self.S['lay']['groups']), ['_g:Mod3'])
        drawn = set(k for k in self.S['seglist'] if not k.startswith('_'))
        self.assertTrue(drawn and all(k.startswith('M3') for k in drawn))
        self.ns['S']['lay'] = None                                             # module state lost (recompile)
        self.ns['Rebuild']()
        self.assertEqual(self.S['lay']['view']['tab'], 'Mod3')                 # remembered in zk_cfg
        self.ns['SetTab']('All')
        self.assertEqual(len(self.S['draw']), 432)
        self.assert_capped()

    def test_scroll_wheel_thumb_clamp_per_tab(self):
        v = self.S['lay']['view']
        x, y = v['W'] - 3, v['hdr'] + 40                                       # over the scrollbar
        self.m.move(x, y)
        self.ns['OnPanel']('wheel', -1, 0)                                     # wheel down = scroll down
        s1 = self.S['scroll']
        self.assertGreater(s1, 0)
        for _k in range(5000):
            self.ns['OnPanel']('wheel', -1, 0)
        self.assertEqual(self.S['scroll'], v['smax'])                          # clamped
        for _k in range(5000):
            self.ns['OnPanel']('wheel', 1, 0)
        self.assertEqual(self.S['scroll'], 0)
        # over a knob the wheel changes its value, not the scroll; Shift+wheel scrolls anywhere
        kx, ky = knob_centre(self.ns, 'M0k3')
        s0 = self.S['scroll']
        self.m.move(kx, ky)
        before = self.h.par.M0k3.eval()
        self.ns['OnPanel']('wheel', 1, 0)
        deliver(self.ns, self.h)
        self.assertNotEqual(self.h.par.M0k3.eval(), before)
        self.assertEqual(self.S['scroll'], s0)
        self.P.panel.shift = True
        val = self.h.par.M0k3.eval()
        self.ns['OnPanel']('wheel', -1, 0)
        self.P.panel.shift = False
        self.assertEqual(self.h.par.M0k3.eval(), val)
        self.assertGreater(self.S['scroll'], s0)
        # group title: scrolls
        gx, gy, gw, gh, _c = self.S['lay']['groups']['_g:Mod5']
        self.ns['ScrollTo'](gy - v['hdr'] - 2)
        st = self.S['scroll']
        self.m.move(gx + 40, gy - st + 4)
        self.ns['OnPanel']('wheel', -1, 0)
        self.assertGreater(self.S['scroll'], st)
        # thumb drag: pointer down on the thumb, move down -> scroll follows, proportional
        self.ns['ScrollTo'](0)
        t = self.L.thumb(v, 0, self.S['lay']['h'])
        tx = v['track'][0] + 1
        self.m.move(tx, t[0] + t[1] / 2.0)
        self.m.button('lselect', True)
        self.m.move(tx, t[0] + t[1] / 2.0 + 100)
        self.assertEqual(self.S['scroll'], self.L.thumb_drag(v, 0, 100, self.S['lay']['h']))
        self.m.move(tx, t[0] + t[1] / 2.0 + 100000)
        self.assertEqual(self.S['scroll'], v['smax'])
        self.m.button('lselect', False)
        # a click on the track below the thumb = one page down
        self.ns['ScrollTo'](0)
        self.m.move(tx, v['track'][1] + v['track'][3] - 2)
        self.m.button('lselect', True)
        self.m.button('lselect', False)
        self.assertGreater(self.S['scroll'], 100)
        # per tab, kept in zk_cfg, survives a rebuild
        all_s = self.S['scroll']
        self.ns['SetTab']('Mod2')
        self.assertEqual(self.S['scroll'], 0)
        self.ns['ScrollTo'](40)
        self.ns['SetTab']('All')
        self.assertEqual(self.S['scroll'], all_s)
        self.ns['Rebuild']()
        self.assertEqual(self.S['scroll'], all_s)
        self.ns['SetTab']('Mod2')
        self.assertEqual(self.S['scroll'], self.L.clamp_scroll(40, self.S['lay']['view']['smax']))

    def test_drag_menu_typing_presets_after_scroll(self):
        iid = 'M9k20'                                                          # far down: off screen at first
        self.assertNotIn(iid, self.ns['_visible']())
        x, y = knob_centre(self.ns, iid)                                      # scrolls it into view
        self.assertGreater(self.S['scroll'], 1000)
        self.assertIn(iid, self.ns['_visible']())
        self.m.move(x, y)
        self.assertEqual(self.S['hover'], iid)                                 # hover is offset-aware
        u0 = self.h.par.M9k20.eval()
        others = dict((n, getattr(self.h.par, n).eval()) for n in ('M9k19', 'M9k21', 'M8k20'))
        self.m.button('lselect', True)
        for k in range(6):
            self.m.move(x, y - 10 * (k + 1))
        self.m.button('lselect', False)
        self.assertGreater(self.h.par.M9k20.eval(), u0)                        # the right knob moved
        for n, v_ in others.items():
            self.assertEqual(getattr(self.h.par, n).eval(), v_)
        # properties menu after scrolling: opens beside the knob in view px, rows hit correctly
        self.m.move(x, y)
        self.m.button('rselect', True)
        self.m.button('rselect', False)
        self.assertEqual(self.S['popup'], iid)
        g = self.ns['_menu_geom']()
        bx, by, bw, bh = g['box']
        self.assertLessEqual(by + bh, self.P.par.h.eval())
        k = [r[0] for r in g['rows']].index('recall')
        self.m.move(bx + 20, by + (k + 1.5) * g['rh'])
        self.m.button('lselect', True)
        self.m.button('lselect', False)
        self.assertEqual(self.ns['props'](iid)['recall'], 0)
        # scrolling closes the menu
        self.m.move(self.S['lay']['view']['W'] - 3, self.S['lay']['view']['hdr'] + 30)
        self.ns['OnPanel']('wheel', 1, 0)
        self.assertIsNone(self.S['popup'])
        # typing after scrolling: click = type into the knob under the pointer
        x, y = knob_centre(self.ns, 'M10k5')
        self.m.move(x, y)
        self.m.button('lselect', True)
        self.m.button('lselect', False)
        self.assertEqual(self.S['edit']['id'], 'M10k5')

        class K(object):
            state = True

            def __init__(self, ch):
                self.key, self.character = ch, ch
        for ch in '0.42':
            self.ns['Key'](K(ch))
        k = K('enter')
        k.character = ''
        self.ns['Key'](k)
        deliver(self.ns, self.h)
        self.assertAlmostEqual(self.h.par.M10k5.eval(), 0.42)
        # presets after scrolling: the bar is in the header (not scrolled); a store holds every page's pars
        bx_, by_ = knob_centre(self.ns, '_plus')
        self.m.move(bx_, by_)
        self.m.button('lselect', True)
        self.m.button('lselect', False)
        pr = self.ns['preset'](1)
        self.assertIn('M0k0', pr)
        self.assertIn('M11k31', pr)
        self.assertAlmostEqual(pr['M10k5'], 0.42)
        self.h.par.M10k5.val = 0.0
        self.h.par.M0k0.val = 0.9
        deliver(self.ns, self.h)
        px, py = knob_centre(self.ns, '_p1')
        self.m.move(px, py)
        self.m.button('lselect', True)
        self.m.button('lselect', False)                                        # classic recall
        self.assertAlmostEqual(self.h.par.M10k5.eval(), 0.42)
        self.assertAlmostEqual(self.h.par.M0k0.eval(), 0.25)

    def test_scroll_notch_inside_band_is_one_uniform(self):
        v = self.S['lay']['view']
        self.m.move(v['W'] - 3, v['hdr'] + 30)
        self.ns['OnPanel']('wheel', -1, 0)                   # first notch may build the band
        w0 = self.S['win']
        C.reset()
        self.ns['OnPanel']('wheel', -1, 0)
        self.assertEqual(self.S['win'], w0)
        self.assertEqual(C.touched('zk_ts'), set())           # no text rewrite
        self.assertEqual(C.touched('zk_hs'), set())
        self.assertLessEqual(C.total_cells('zk_gpu'), 8, C.cells)   # the thumb instance only
        face_writes = [k for k in C.pars if k.startswith('zk_face')]
        self.assertTrue(face_writes and all('vec8' in k for k in face_writes), C.pars)
        # leaving the band rebuilds it once, then notches are cheap again
        for _k in range(200):
            self.ns['OnPanel']('wheel', -1, 0)
        self.assertNotEqual(self.S['win'], w0)
        self.assertTrue(self.L.in_window(self.S['win'], v, self.S['scroll']))

    def test_culling_keeps_cost_flat(self):
        vis = self.ns['_visible']()
        self.assertLess(len(vis), 120)
        knob_segs = [k for k in self.S['segs'] if not k.startswith('_')]
        self.assertLessEqual(len(knob_segs), len(vis))
        n = self.P.ops['zk_gpu'].numCols - 1
        self.assertLess(n, 4 * len(vis) + 60)
        # an off-screen knob changing draws nothing
        C.reset()
        self.h.par.M11k30.val = 0.8
        deliver(self.ns, self.h)
        self.assertEqual(C.touched('zk_'), set())
        # ... and shows its new value once scrolled into view
        knob_centre(self.ns, 'M11k30')
        sg = self.S['segs']['M11k30']
        self.assertEqual(sg.sig[1], 0.8)

    def test_incremental_equals_full_after_scrolls(self):
        rng = random.Random(11)
        ids = list(self.S['order'])
        v = self.S['lay']['view']
        for step in range(40):
            r = rng.random()
            if r < 0.3:
                self.ns['ScrollTo'](rng.randint(0, v['smax']))
            elif r < 0.6:
                iid = rng.choice(self.S['draw'])
                x, y = knob_centre(self.ns, iid)
                self.m.move(x, y)
                self.m.button('lselect', True)
                self.m.move(x, y - 12)
                self.m.button('lselect', False)
            elif r < 0.75:
                self.m.move(v['W'] - 3, v['hdr'] + 20)
                self.ns['OnPanel']('wheel', rng.choice((-1, 1)), 0)
            elif r < 0.85:
                self.ns['SetTab'](rng.choice(['All', 'Mod1', 'Mod7']))
                v = self.S['lay']['view']
            else:
                getattr(self.h.par, rng.choice([i for i in ids if 'k' in i])).val = rng.random()
                deliver(self.ns, self.h)
        self.m.move(1, 1)
        inc = state(self.P)
        reset_caches(self.ns, self.P)
        self.ns['Render']()
        self.assertEqual(inc, state(self.P))
        self.assert_capped()

    def test_small_panel_unchanged_size(self):
        ns, h, P = make_panel(pages={'Look': [('A%d' % i, 'Float') for i in range(6)]})
        v = ns['S']['lay']['view']
        self.assertFalse(v['overflow'])
        self.assertEqual(v['tabs'], [])
        self.assertEqual((P.par.w.eval(), P.par.h.eval()), (ns['S']['lay']['w'], ns['S']['lay']['h']))

    def test_bench_432_knobs(self):
        out = Bench.run(pages=BIG, n=60)
        cap = self.L.viewport_cap(0, (2056, 1329))
        self.assertLessEqual(out['face res'][1], cap[1])
        self.assertLessEqual(out['face res'][0], cap[0])
        self.assertLessEqual(out['instance texture px'], self.L.TEX_CAP)
        self.assertEqual(out['knobs'], 432)
        self.assertLess(out['drag event ms (median)'], 5.0, out)              # loose: offline CPython, not TD
        self.assertLess(out['scroll notch ms (median)'], 60.0, out)


class EssentialsRuntime(unittest.TestCase):
    """Main tab, macros (drive, no fighting, presets), fallback, hidden pages, on the fake TD."""
    MAC = [{'name': 'Zkm1', 'label': 'Energy', 'drives': [{'par': 'Gain1', 'from': -1.0, 'to': 1.0},
                                                          {'par': 'Steps', 'from': 0, 'to': 8}]}]

    def make(self, main='Gain3 Mode Tint Speed2', macros=None, pages=None):
        import json
        cfg = [('main', main), ('macros', json.dumps(self.MAC if macros is None else macros))]
        ns, h, P = make_panel(tab=None, cfg=cfg, pages=pages)
        return ns, h, P

    def add_macro(self, h):
        p = h.par.add(Par(h, 'Zkm1', 0.5, 'Float', 'Energy'))
        return p

    def test_main_default_and_order(self):
        ns, h, P = make_panel(tab=None, cfg=[('main', 'Gain3 Mode Tint Speed2')])
        S = ns['S']
        self.assertEqual(S['lay']['view']['tab'], 'Main')
        self.assertEqual(S['draw'], ['Gain3', 'Mode', 'Tint', 'Speed2'])
        self.assertEqual(S['lay']['view']['tabs'][0], 'Main')
        self.assertEqual(S['lay']['view']['tabs'][-1], 'All')
        self.assertGreaterEqual(len(S['order']), 70)                           # presets still see every page

    def test_fallback_main(self):
        ns, h, P = make_panel(tab=None)
        S = ns['S']
        self.assertEqual(S['lay']['view']['tab'], 'Main')
        self.assertEqual(S['draw'], ['Gain%d' % i for i in range(12)])         # first 12 of the first page
        ns2, h2, P2 = make_panel(tab=None, pages={'Only': [('A%d' % i, 'Float') for i in range(6)]})
        self.assertEqual(ns2['S']['lay']['view']['tabs'], [])                  # Main would equal All: no tabs

    def test_macro_drives_and_is_not_fought(self):
        ns, h, P = make_panel(tab=None, cfg=[('main', 'Gain3'), ('macros', __import__('json').dumps(self.MAC))],
                              pages=dict(PAGES))
        # the builder adds the macro par; the fake host gets it here, then a rebuild picks it up
        self.add_macro(h)
        ns['Rebuild']()
        S = ns['S']
        self.assertEqual(S['draw'], ['Gain3', 'Zkm1'])
        self.assertIn('Zkm1', S['order'])
        h.par.Zkm1.val = 0.75
        deliver(ns, h)
        self.assertAlmostEqual(h.par.Gain1.eval(), 0.5)
        self.assertEqual(h.par.Steps.eval(), 6)
        h.par.Gain1.val = -0.9                                                  # by hand: the macro leaves it
        deliver(ns, h)
        self.assertAlmostEqual(h.par.Gain1.eval(), -0.9)
        self.assertAlmostEqual(h.par.Zkm1.eval(), 0.75)
        # drag the macro knob on the Main tab: drives again
        m = Mouse(ns, h, P)
        x, y = knob_centre(ns, 'Zkm1')
        m.move(x, y)
        m.button('lselect', True)
        m.move(x, y - 20)
        m.button('lselect', False)
        self.assertGreater(h.par.Zkm1.eval(), 0.75)
        self.assertAlmostEqual(h.par.Gain1.eval(), -1.0 + 2.0 * h.par.Zkm1.eval())
        # presets hold the macro; a recall does not let the macro overwrite the stored driven values
        ns['Store'](1)
        pr = ns['preset'](1)
        self.assertIn('Zkm1', pr)
        g1 = h.par.Gain1.eval()
        h.par.Gain1.val = 0.0
        h.par.Zkm1.val = 0.1
        deliver(ns, h)
        h.par.Gain1.val = 0.33                                                 # by hand after the macro
        deliver(ns, h)
        pr['Gain1'] = 0.2                                                      # a preset whose Gain1 was hand-set
        P.ops['zk_presets'][str(1), 'data'] = P.ops['zk_logic'].module.preset_dump(pr)
        ns['Recall'](1)
        deliver(ns, h)
        self.assertAlmostEqual(h.par.Zkm1.eval(), pr['Zkm1'])
        self.assertAlmostEqual(h.par.Gain1.eval(), 0.2)                        # stored value, not the macro's
        # randomise includes the macro
        ns['Randomize'](1.0)
        deliver(ns, h)
        self.assertNotAlmostEqual(h.par.Zkm1.eval(), pr['Zkm1'])
        del g1

    def test_unknown_macro_par_is_ignored(self):
        ns, h, P = make_panel(tab=None, cfg=[('main', 'Gain3'), ('macros', __import__('json').dumps(self.MAC))])
        self.assertEqual(ns['S']['draw'], ['Gain3'])                           # Zkm1 not made (not on the host)

    def test_page_switch_and_stack(self):
        pages = dict(PAGES)
        pages['Haze'] = [('Vhon', 'Toggle'), ('Vhamount', 'Float'), ('Vhdensity', 'Float')]
        pages['M4_curl'] = [('M4amount', 'Float'), ('M4scale', 'Float')]
        pages['M1_prox_push'] = [('M1amount', 'Float')]
        ns, h, P = make_panel(pages=pages)
        S = ns['S']
        self.assertIn('Vhon', S['order'])
        self.assertNotIn('Vhamount', S['order'])                               # switch off: only the switch shows
        h.par.Vhon.val = True
        deliver(ns, h)
        self.assertIn('Vhamount', S['order'])
        self.assertIn('M4amount', S['order'])                                  # no stack table: shown
        st = Table('px_stack', [['uid', 'type', 'enabled', 'label'], [1, 'prox_push', 1, ''], [4, 'curl', 0, '']])
        h.children['px_stack'] = st
        ns['StackChanged']()
        self.assertNotIn('M4amount', S['order'])
        self.assertIn('M1amount', S['order'])
        self.assertNotIn('M4_curl', S['lay']['view']['tabs'])
        st[2, 'enabled'] = 1
        ns['StackChanged']()
        self.assertIn('M4amount', S['order'])

    def test_px_uid_pars_follow_the_stack(self):
        import json
        pages = dict(PAGES)
        pages['M1_prox_push'] = [('M1strength', 'Float')]
        pages['M2_curl'] = [('M2strength', 'Float'), ('M2speed', 'Float')]
        mac = [{'name': 'Zkm1', 'label': 'Energy', 'drives': [{'par': 'Gain1', 'from': 0, 'to': 1},
                                                              {'par': 'M2strength', 'from': 0, 'to': 1.8}]}]
        ns, h, P = make_panel(tab=None, pages=pages, cfg=[('main', 'Gain3 M1strength M2strength'),
                                                        ('macros', json.dumps(mac)),
                                                        ('uidtypes', '1:prox_push 2:curl 3:prox_colour')])
        st = Table('px_stack', [['uid', 'type', 'enabled'], [1, 'prox_push', 1], [2, 'curl', 1]])
        h.children['px_stack'] = st
        h.par.add(Par(h, 'Zkm1', 0.0, 'Float', 'Energy'))
        ns['Rebuild']()
        S = ns['S']
        self.assertEqual(S['draw'], ['Gain3', 'M1strength', 'M2strength', 'Zkm1'])
        h.par.Zkm1.val = 0.5
        deliver(ns, h)
        self.assertAlmostEqual(h.par.M2strength.eval(), 0.9)
        st[2, 'type'] = 'prox_colour'                                         # uid 2 is another module now
        ns['StackChanged']()
        self.assertEqual(S['draw'], ['Gain3', 'M1strength', 'Zkm1'])
        self.assertIn('M2strength', P.ops['zk_cfg']['rt_notes', 1].val)
        h.par.M2strength.val = 0.1
        h.par.Zkm1.val = 1.0
        deliver(ns, h)
        self.assertAlmostEqual(h.par.M2strength.eval(), 0.1)                  # not driven any more
        self.assertAlmostEqual(h.par.Gain1.eval(), 1.0)


class DynPar(Par):
    """A StrMenu with a live menuSource: menuNames / menuLabels come from src() on EVERY read (as in TD, T-233)."""

    def __init__(self, owner, name, val, src, label=None):
        Par.__init__(self, owner, name, val, 'StrMenu', label)
        self._src = src
        self.reads = 0
        self.menuSource = 'live'

    @property
    def menuNames(self):
        self.reads += 1
        return list(self._src()[0])

    @menuNames.setter
    def menuNames(self, v):
        pass

    @property
    def menuLabels(self):
        self.reads += 1
        return list(self._src()[1])

    @menuLabels.setter
    def menuLabels(self, v):
        pass


class Key(object):
    def __init__(self, key, ch=''):
        self.key, self.character, self.state = key, ch, True


def _menu_logic():
    spec = importlib.util.spec_from_file_location('menu_logic_t', os.path.join(BUILDERS, 'menu_logic.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class DropdownRuntime(unittest.TestCase):
    """StrMenu fields with a live menuSource (28 Oct): field + pop-up list read at click time, pick = the name."""

    def setUp(self):
        ML = _menu_logic()
        self.eff = ['sphere1', 'box1']
        ns, h, P = make_panel(pages={'Eff': [('Gain', 'Float'), ('Mode', 'Menu')]}, tab=None)
        tm = lambda: (lambda m: (m.menuNames, m.menuLabels))(ML.name_menu(self.eff, ['%s (x)' % e for e in self.eff]))
        sel = {}
        sm = lambda: (lambda m: (m.menuNames, m.menuLabels))(ML.select_menu(sel['p'].eval(), self.eff, ['demo']))
        self.tgt = h.par.add(DynPar(h, 'Target', 'sphere1', tm))
        sel['p'] = self.sel = h.par.add(DynPar(h, 'Effselect', 'all', sm))
        h.customPages[0].parTuplets += [[self.tgt], [self.sel]]
        self.tgt.reads = self.sel.reads = 0
        ns['Rebuild']()
        self.ns, self.h, self.P = ns, h, P
        self.m = Mouse(ns, h, P)

    def click(self, x, y, alt=False):
        self.P.panel.alt = alt
        self.m.move(x, y)
        self.m.button('lselect', True)
        self.m.button('lselect', False)
        self.P.panel.alt = False

    def open(self, iid):
        self.click(*knob_centre(self.ns, iid))
        return self.ns['_menu_geom']()

    def row_xy(self, g, i):
        bx, by, bw, bh = g['box']
        return bx + 20, by + (i - self.ns['S']['drop']['off'] + 1.5) * g['rh']

    def pick(self, iid, name):
        g = self.open(iid)
        i = self.ns['S']['drop']['names'].index(name)
        self.click(*self.row_xy(g, i))

    def test_kind_and_no_read_at_build(self):
        S = self.ns['S']
        self.assertEqual(S['items']['Target']['kind'], 'dropdown')
        self.assertEqual(S['items']['Mode']['kind'], 'menu')               # static Menu keeps its knob
        self.assertEqual((self.tgt.reads, self.sel.reads), (0, 0))         # items are not read at panel build
        x, y, w, hh = S['lay']['items']['Target']
        self.assertGreater(w, S['lay']['items']['Gain'][2])                # a wide (two-cell) field

    def test_live_items_pick_sets_name(self):
        self.eff.append('capsule1')                                        # added after the panel was built
        g = self.open('Target')
        S = self.ns['S']
        self.assertEqual(S['drop']['names'], ['sphere1', 'box1', 'capsule1'])
        self.assertEqual(S['drop']['labels'][2], 'capsule1 (x)')
        v = S['lay']['view']
        bx, by, bw, bh = g['box']
        self.assertTrue(0 <= bx and bx + bw <= v['W'] and 0 <= by and by + bh <= v['H'])
        self.click(*self.row_xy(g, 2))
        self.assertEqual(self.tgt.eval(), 'capsule1')                      # the NAME, not an index
        self.assertIsNone(S['drop'])
        self.assertFalse(self.P.ops['zk_keys'].par.active.eval())

    def test_helper_items_set_whole_text(self):
        self.pick('Effselect', 'sphere1')                                   # '+ sphere1' replaces 'all'
        self.assertEqual(self.sel.eval(), 'sphere1')
        self.pick('Effselect', 'sphere1 #demo')                             # '+ #demo'
        self.assertEqual(self.sel.eval(), 'sphere1 #demo')
        self.assertIn('+ #demo', _menu_logic().select_menu('sphere1', self.eff, ['demo']).menuLabels)
        self.pick('Effselect', '#demo')                                     # '- sphere1'
        self.assertEqual(self.sel.eval(), '#demo')

    def test_typed_value_alt_click_and_header(self):
        S = self.ns['S']
        self.click(*knob_centre(self.ns, 'Target'), alt=True)
        self.assertEqual(S['edit']['buf'], 'sphere1')                       # starts from the current text
        for _k in range(7):
            self.ns['Key'](Key('backspace'))
        for ch in 'my #x/1':
            self.ns['Key'](Key(ch, ch))
        self.ns['Key'](Key('enter'))
        self.assertEqual(self.tgt.eval(), 'my #x/1')                        # a value not in the list is fine
        g = self.open('Target')
        bx, by, bw, bh = g['box']
        self.click(bx + 10, by + g['rh'] * 0.5)                             # header row = type
        self.assertIsNotNone(S['edit'])
        self.ns['Key'](Key('esc'))
        self.assertEqual(self.tgt.eval(), 'my #x/1')

    def test_esc_click_outside_rollover_close(self):
        S = self.ns['S']
        self.open('Target')
        self.assertTrue(self.P.ops['zk_keys'].par.active.eval())
        self.ns['Key'](Key('esc'))
        self.assertIsNone(S['drop'])
        self.assertFalse(self.P.ops['zk_keys'].par.active.eval())
        self.open('Target')
        gx, gy = knob_centre(self.ns, 'Gain')
        g0 = self.h.par.Gain.eval()
        self.click(gx, gy)                                                  # outside: closes, nothing else
        self.assertIsNone(S['drop'])
        self.assertIsNone(S['edit'])
        self.assertEqual(self.h.par.Gain.eval(), g0)
        self.open('Target')
        self.ns['OnPanel']('rollover', 0, 1)
        self.assertIsNone(S['drop'])
        self.assertEqual(self.tgt.eval(), 'sphere1')

    def test_wheel_safe_and_long_list_scrolls(self):
        S = self.ns['S']
        x, y = knob_centre(self.ns, 'Target')
        self.m.move(x, y)
        self.ns['OnPanel']('wheel', 1, 0)
        self.assertEqual(self.tgt.eval(), 'sphere1')                        # wheel never changes a name field
        self.eff[:] = ['n%03d' % i for i in range(300)]
        g = self.open('Target')
        self.assertLess(g['nvis'], 300)
        self.assertEqual(S['drop']['off'], 0)
        bx, by, bw, bh = g['box']
        self.m.move(bx + 10, by + g['rh'] * 2)
        self.ns['OnPanel']('wheel', -1, 0)                                  # down one notch: one row on
        self.assertEqual(S['drop']['off'], 1)
        self.click(*self.row_xy(g, 5))
        self.assertEqual(self.tgt.eval(), 'n005')
        insts = int(self.P.ops['zk_face'].par.vec0valuex.eval())
        self.assertLessEqual(insts, 1024)

    def test_presets_store_text_random_skips(self):
        ns = self.ns
        self.tgt.val = 'box1'
        deliver(ns, self.h)
        slot = ns['Store']()
        self.tgt.val = 'sphere1'
        ns['Recall'](slot)
        self.assertEqual(self.tgt.eval(), 'box1')                            # the text came back
        self.assertIn('"Target":"box1"', self.P.ops['zk_presets'][str(slot), 'data'].val)
        ns['Randomize'](1.0)
        self.assertEqual(self.tgt.eval(), 'box1')
        self.assertEqual(self.sel.eval(), 'all')
        self.assertEqual((self.tgt.reads, self.sel.reads), (0, 0))           # presets / random read no items

    def test_idle_zero_and_open_draw_cost(self):
        ns = self.ns
        self.open('Target')
        self.ns['Key'](Key('esc'))
        C.reset()
        ns['Render']()
        self.assertEqual(C.total_cells(), 0)                                 # idle after close: nothing written
        self.assertEqual(sum(C.pars.values()), 0)


class Bench(object):
    @staticmethod
    def run(rt_file=RT_FILE, logic_file=LOGIC_FILE, n=200, pages=None):
        new_ops = 'zk_tiles' in open(rt_file).read()
        ns, h, P = make_panel(rt_file, logic_file, with_new_ops=new_ops, pages=pages)
        if pages is not None:
            Bench.knob = next(i for i in ns['S']['order'] if 'k' in i and i.endswith('3'))
            Bench.ph = [i for i in ns['S']['order'] if 'k' in i][-1]
        else:
            Bench.knob, Bench.ph = 'Gain3', 'Playhead'
        m = Mouse(ns, h, P)
        out = {}
        x, y = knob_centre(ns, Bench.knob)
        m.move(x, y)
        m.button('lselect', True)
        m.move(x, y - 6)
        ts = []
        for k in range(n):
            t0 = time.perf_counter()
            m.move(x, y - 6 - (k % 40))
            ts.append((time.perf_counter() - t0) * 1000.0)
        m.button('lselect', False)
        out['drag event ms (median)'] = statistics.median(ts)
        ts = []
        ids = ns['S']['order'][:40]
        for k in range(n):
            t0 = time.perf_counter()
            m.move(*knob_centre(ns, ids[k % len(ids)]))
            ts.append((time.perf_counter() - t0) * 1000.0)
        out['hover change ms (median)'] = statistics.median(ts)
        ts = []
        knob_centre(ns, Bench.ph)
        for k in range(n):
            getattr(h.par, Bench.ph).val = (k % 40) * 0.05 - 1.0
            t0 = time.perf_counter()
            deliver(ns, h)
            ts.append((time.perf_counter() - t0) * 1000.0)
        out['synced par per frame ms (median)'] = statistics.median(ts)
        t0 = time.perf_counter()
        ns['Rebuild']()
        out['Rebuild ms'] = (time.perf_counter() - t0) * 1000.0
        C.reset()
        x, y = knob_centre(ns, Bench.knob)              # the playhead check scrolled: where the knob is now
        m.move(x, y)
        m.button('lselect', True)
        m.move(x, y - 6)
        C.reset()
        for k in range(20):
            m.move(x, y - 9 - 3 * k)
        m.button('lselect', False)
        out['cell writes per drag event'] = sum(C.cells.values()) / 20.0
        out['tables touched while dragging'] = sorted(C.touched())
        out['knobs'] = len(ns['S']['order'])
        S = ns['S']
        if 'view' in S.get('lay', {}):
            v = S['lay']['view']
            ts = []
            for k in range(n):                                  # wheel notches over the scrollbar
                m.move(v['W'] - 3, v['hdr'] + 20)
                t0 = time.perf_counter()
                ns['OnPanel']('wheel', -1 if (k // 40) % 2 == 0 else 1, 0)
                ts.append((time.perf_counter() - t0) * 1000.0)
            out['scroll notch ms (median)'] = statistics.median(ts)
            out['scroll notch ms (max)'] = max(ts)
            t0 = time.perf_counter()
            ns['SetTab'](S['lay']['view']['tabs'][2] if len(S['lay']['view']['tabs']) > 2 else 'All')
            ns['SetTab']('All')
            out['tab switch ms (x2)'] = (time.perf_counter() - t0) * 1000.0
            out['content px'] = (S['lay']['w'], S['lay']['h'])
            out['view / face px'] = (P.par.w.eval(), P.par.h.eval())
            out['face res'] = (P.ops['zk_face'].par.resolutionw.eval(), P.ops['zk_face'].par.resolutionh.eval())
            out['instances drawn'] = P.ops['zk_gpu'].numCols - 1
            out['instance texture px'] = 4 * (P.ops['zk_gpu'].numCols - 1)
            out['visible knobs'] = len(ns['_visible']())
        return out


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'bench':
        args = [a for a in sys.argv[2:] if a != 'big']
        rt = args[0] if args else RT_FILE
        lg = args[1] if len(args) > 1 else os.path.join(os.path.dirname(os.path.abspath(rt)), 'zkit_logic.py')
        big = 'big' in sys.argv
        for k, v in Bench.run(rt, lg, pages=BIG if big else None).items():
            print('%-34s %s' % (k, ('%.3f' % v) if isinstance(v, float) else v))
    else:
        unittest.main()
