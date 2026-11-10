"""Offline tests for TL_timeline phase 4 (agent API): builders/timeline_api_logic.py (pure), the TimelineExt text
(builders/timeline_ext.py) run against fake ops, the record clock in tl_actions.tick and the handlers timeline_*
commands. No TD needed.

Run: cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_timeline*.py'
"""
import fnmatch
import json
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDERS = os.path.join(os.path.dirname(HERE), 'builders')
sys.path.insert(0, BUILDERS)
import timeline_logic as TL  # noqa: E402
import timeline_clips_logic as CL  # noqa: E402
import timeline_api_logic as API  # noqa: E402

API.bind(TL, CL)


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def demo_show(clips=True):
    sh = API.empty_show()
    sh['settings'] = {'length': 16.0, 'fps': 30.0, 'bpm': 120.0, 'beatsperbar': 4, 'inpoint': 0.0, 'outpoint': 16.0,
                      'loop': True, 'rate': 1.0, 'snap': True, 'snapdiv': 1, 'snapunit': 'beat', 'tcmode': 'smpte',
                      'clockmode': 'realtime', 'markername': 'Marker'}
    sh['lanes'] = [{'name': 'level', 'op': 'demo_level', 'par': 'value0', 'min': 0.0, 'max': 1.0, 'enabled': True,
                    'keys': [[0.0, 0.0, 'linear'], [4.0, 1.0, 'ease'], [8.0, 0.25, 'hold']]},
                   {'name': 'drift', 'op': 'demo_noise', 'par': 'tx', 'min': -1.0, 'max': 1.0, 'enabled': True,
                    'keys': [[0.0, -0.5, 'bezier'], [16.0, 0.5, 'bezier']]}]
    sh['markers'] = [[0.0, 'Intro'], [8.0, 'Drop']]
    sh['clips'] = [{'id': 'ramp', 'track': 0, 'start': 0.0, 'dur': 6.0, 'src': 'a.mp4', 'in': 2.0, 'speed': 1.0,
                    'fade': 0.0, 'proxy': '', 'enabled': True}] if clips else None
    return sh


class Times(unittest.TestCase):
    def setUp(self):
        self.ctx = API.Ctx(fps=30, bpm=120, bpb=4, markers=[(8.0, 'Drop'), (0.0, 'Intro')])

    def test_forms(self):
        c = self.ctx
        self.assertEqual(API.to_seconds(2.5, c), 2.5)
        self.assertEqual(API.to_seconds('2.5', c), 2.5)
        self.assertEqual(API.to_seconds('2.5s', c), 2.5)
        self.assertAlmostEqual(API.to_seconds('45f', c), 1.5)
        self.assertAlmostEqual(API.to_seconds('8b', c), 4.0)
        self.assertAlmostEqual(API.to_seconds('2bar', c), 4.0)
        self.assertAlmostEqual(API.to_seconds('3.1.1', c), 4.0)         # bar 3 beat 1 = 8 beats in
        self.assertAlmostEqual(API.to_seconds('1.2.3', c), 0.75)        # 1 beat + 2 sixteenths
        self.assertAlmostEqual(API.to_seconds('00:00:04:15', c), 4.5)
        self.assertAlmostEqual(API.to_seconds('01:04.5', c), 64.5)
        self.assertAlmostEqual(API.to_seconds('@Drop', c), 8.0)
        self.assertAlmostEqual(API.to_seconds('@Drop+2b', c), 9.0)
        self.assertAlmostEqual(API.to_seconds('@Drop-15f', c), 7.5)

    def test_bad(self):
        for x in ('@Nope', 'abc', None, '0.0.1', float('nan'), True):
            with self.assertRaises(API.OpError, msg=repr(x)):
                API.to_seconds(x, self.ctx)
        with self.assertRaises(API.OpError):
            API.to_seconds('4b', API.Ctx(bpm=0))


class Edits(unittest.TestCase):
    def apply(self, ops, sh=None, atomic=True):
        return API.apply_ops(sh or demo_show(), ops, atomic)

    def test_add_move_delete_key(self):
        sh, res, ok = self.apply([{'op': 'add_key', 'lane': 'level', 't': '3b', 'v': 0.9, 'interp': 'hold'}])
        self.assertTrue(ok, res)
        self.assertIn([1.5, 0.9, 'hold'], sh['lanes'][0]['keys'])
        self.assertEqual(res[0]['index'], 1)
        sh, res, ok = self.apply([{'op': 'move_key', 'lane': 'level', 'at': 4, 't': 5, 'v': 0.7}], sh)
        self.assertTrue(ok, res)
        self.assertIn([5.0, 0.7, 'ease'], sh['lanes'][0]['keys'])  # interp kept
        sh, res, ok = self.apply([{'op': 'move_key', 'lane': 'level', 'index': -1, 'by': '2b'}], sh)
        self.assertEqual(sh['lanes'][0]['keys'][-1][0], 9.0)
        sh, res, ok = self.apply([{'op': 'delete_key', 'lane': 'level', 'at': 1.5}], sh)
        self.assertTrue(ok)
        self.assertEqual([k[0] for k in sh['lanes'][0]['keys']], [0.0, 5.0, 9.0])

    def test_move_onto_key_refused(self):
        _, res, ok = self.apply([{'op': 'move_key', 'lane': 'level', 'at': 4, 't': 8}])
        self.assertFalse(ok)
        self.assertIn('already sits', res[0]['error'])

    def test_snap(self):
        sh, res, ok = self.apply([{'op': 'add_key', 'lane': 'level', 't': 2.2, 'v': 0.1, 'snap': True}])
        self.assertTrue(ok)
        self.assertIn(2.0, [k[0] for k in sh['lanes'][0]['keys']])

    def test_atomic(self):
        orig = demo_show()
        sh, res, ok = API.apply_ops(orig, [{'op': 'add_key', 'lane': 'level', 't': 1, 'v': 1},
                                           {'op': 'add_key', 'lane': 'nope', 't': 1, 'v': 1}])
        self.assertFalse(ok)
        self.assertTrue(res[0]['ok'])
        self.assertFalse(res[1]['ok'])
        self.assertEqual(sh, orig)
        sh, res, ok = API.apply_ops(orig, [{'op': 'add_key', 'lane': 'level', 't': 1, 'v': 1},
                                           {'op': 'add_key', 'lane': 'nope', 't': 1, 'v': 1}], atomic=False)
        self.assertFalse(ok)
        self.assertEqual(len(sh['lanes'][0]['keys']), 4)

    def test_unknown_op_and_limits(self):
        _, res, ok = self.apply([{'op': 'explode'}])
        self.assertFalse(ok)
        self.assertIn('unknown op', res[0]['error'])
        with self.assertRaises(API.OpError):
            API.apply_ops(demo_show(), 'add_key')
        with self.assertRaises(API.OpError):
            API.apply_ops(demo_show(), [{}] * (API.MAX_OPS + 1))

    def test_lanes(self):
        sh, res, ok = self.apply([
            {'op': 'add_lane', 'name': 'hue', 'target': '/project1/lab/x/level1.opacity', 'max': 2,
             'keys': [['@Drop', 2], [0, 0, 'ease']]},
            {'op': 'set_lane', 'name': 'drift', 'rename': 'wobble', 'enabled': False},
            {'op': 'move_lane', 'name': 'hue', 'to': 0}])
        self.assertTrue(ok, res)
        self.assertEqual([l['name'] for l in sh['lanes']], ['hue', 'level', 'wobble'])
        self.assertEqual(sh['lanes'][0]['op'], '/project1/lab/x/level1')
        self.assertEqual(sh['lanes'][0]['keys'], [[0.0, 0.0, 'ease'], [8.0, 2.0, 'linear']])
        self.assertFalse(sh['lanes'][2]['enabled'])
        sh, res, ok = self.apply([{'op': 'delete_lane', 'name': 'hue'}], sh)
        self.assertEqual(len(sh['lanes']), 2)
        for bad in ({'op': 'add_lane', 'name': 'level'}, {'op': 'add_lane', 'name': 'bad name'},
                    {'op': 'add_lane', 'name': 'x', 'min': 1, 'max': 1},
                    {'op': 'add_lane', 'name': 'x', 'target': 'noparhere'},
                    {'op': 'set_keys', 'lane': 'level', 'keys': [[1, 1], [1, 2]]},
                    {'op': 'set_keys', 'lane': 'level', 'keys': [[1, 1, 'cubic']]}):
            _, res, ok = self.apply([bad])
            self.assertFalse(ok, bad)

    def test_no_target_warns(self):
        _, res, ok = self.apply([{'op': 'add_lane', 'name': 'spare'}])
        self.assertTrue(ok)
        self.assertIn('warnings', res[0])

    def test_markers(self):
        sh, res, ok = self.apply([{'op': 'add_marker', 't': '3.1.1', 'name': 'Verse'},
                                  {'op': 'add_key', 'lane': 'level', 't': '@Verse+1b', 'v': 1}])
        self.assertTrue(ok, res)
        self.assertEqual(sh['markers'], [[0.0, 'Intro'], [4.0, 'Verse'], [8.0, 'Drop']])
        self.assertIn(4.5, [k[0] for k in sh['lanes'][0]['keys']])
        sh, res, ok = self.apply([{'op': 'move_marker', 'name': 'Drop', 't': 12, 'rename': 'Drop2'},
                                  {'op': 'delete_marker', 'at': 0}], sh)
        self.assertTrue(ok, res)
        self.assertEqual(sh['markers'], [[4.0, 'Verse'], [12.0, 'Drop2']])
        _, res, ok = self.apply([{'op': 'add_marker', 't': 3, 'name': 'Drop'}])
        self.assertFalse(ok)   # names unique
        _, res, ok = self.apply([{'op': 'add_marker', 't': 3, 'name': 'a\tb'}])
        self.assertFalse(ok)

    def test_clips(self):
        sh, res, ok = self.apply([
            {'op': 'add_clip', 'src': 'b.mp4', 'start': '@Drop', 'dur': '4bar', 'track': 1, 'fade': '15f'},
            {'op': 'move_clip', 'id': 'ramp', 'by': 1},
            {'op': 'trim_clip', 'id': 'ramp', 'edge': 'in', 't': 2},
            {'op': 'set_clip', 'id': 'ramp', 'speed': -1}])
        self.assertTrue(ok, res)
        new = sh['clips'][1]
        self.assertEqual(new['id'], 'clip2')
        self.assertEqual((new['start'], new['dur'], new['track'], new['fade']), (8.0, 8.0, 1, 0.5))
        ramp = sh['clips'][0]
        self.assertEqual((ramp['start'], ramp['dur'], ramp['in'], ramp['speed']), (2.0, 5.0, 3.0, -1.0))
        sh, res, ok = self.apply([{'op': 'set_clip', 'id': 'clip2', 'end': 10, 'rename': 'outro'},
                                  {'op': 'delete_clip', 'id': 'ramp'}], sh)
        self.assertTrue(ok, res)
        self.assertEqual([(c['id'], c['dur']) for c in sh['clips']], [('outro', 2.0)])
        for bad in ({'op': 'add_clip', 'id': 'ramp', 'src': 'x', 'dur': 1}, {'op': 'add_clip', 'src': 'x'},
                    {'op': 'add_clip', 'src': 'x', 'dur': 1, 'track': -1}, {'op': 'set_clip', 'id': 'nope'},
                    {'op': 'trim_clip', 'id': 'ramp', 'edge': 'mid', 't': 1}):
            _, res, ok = self.apply([bad])
            self.assertFalse(ok, bad)
        _, res, ok = self.apply([{'op': 'add_clip', 'src': 'x', 'dur': 1}], demo_show(clips=False))
        self.assertFalse(ok)
        self.assertIn('no clips track', res[0]['error'])

    def test_settings(self):
        sh, res, ok = self.apply([{'op': 'set', 'bpm': 128, 'tcmode': 'bars', 'loop': 'off'},
                                  {'op': 'add_key', 'lane': 'level', 't': '4b', 'v': 1}])
        self.assertTrue(ok, res)
        self.assertEqual(sh['settings']['bpm'], 128.0)
        self.assertFalse(sh['settings']['loop'])
        self.assertAlmostEqual(sh['lanes'][0]['keys'][1][0], 4 * 60 / 128.0)  # beats use the new bpm
        for bad in ({'op': 'set', 'bpm': -1}, {'op': 'set', 'tcmode': 'x'}, {'op': 'set', 'beatsperbar': 2.5},
                    {'op': 'set', 'nope': 1}):
            _, res, ok = self.apply([bad])
            self.assertFalse(ok, bad)

    def test_range_warning(self):
        _, res, ok = self.apply([{'op': 'add_key', 'lane': 'level', 't': 20, 'v': 1}])
        self.assertTrue(ok)
        self.assertIn('outside', res[0]['warnings'][0])


class Tables(unittest.TestCase):
    def test_round_trip(self):
        sh = demo_show()
        tt = API.table_texts(sh)
        self.assertEqual(sorted(tt), ['clips', 'lane_drift', 'lane_level', 'lanes', 'markers'])
        back = API.show_from_tables(sh['settings'], tt['lanes'], {'level': tt['lane_level'], 'drift': tt['lane_drift']},
                                    tt['markers'], tt['clips'])
        self.assertEqual(back, sh)
        no_clips = API.show_from_tables({}, tt['lanes'], {}, tt['markers'], None)
        self.assertIsNone(no_clips['clips'])

    def test_changed(self):
        a = demo_show()
        b, _, _ = API.apply_ops(a, [{'op': 'add_key', 'lane': 'level', 't': 1, 'v': 1},
                                    {'op': 'delete_lane', 'name': 'drift'},
                                    {'op': 'add_lane', 'name': 'new'}, {'op': 'set', 'bpm': 90}])
        ch, rm = API.changed_tables(a, b)
        self.assertEqual(sorted(ch), ['lane_level', 'lane_new', 'lanes'])
        self.assertEqual(rm, ['lane_drift'])
        self.assertEqual(API.changed_settings(a, b), {'bpm': 90.0})
        self.assertEqual(API.changed_tables(a, a), ({}, []))


class Documents(unittest.TestCase):
    def test_norm_and_errors(self):
        cur = demo_show()
        doc = {'format': 'tl-show', 'v': 1, 'settings': {'bpm': 100},
               'markers': [{'t': '@A+1bar', 'name': 'B'}, ['2b', 'A']],
               'lanes': [{'name': 'x', 'target': 'n.tx', 'keys': [{'t': '@B', 'v': 1}]}]}
        sh = API.norm_show(doc, cur)
        self.assertEqual([(round(t, 9), n) for t, n in sh['markers']], [(1.2, 'A'), (3.6, 'B')])
        self.assertEqual(sh['lanes'][0]['keys'], [[sh['markers'][1][0], 1.0, 'linear']])
        self.assertEqual(sh['clips'], cur['clips'])            # missing part kept
        self.assertEqual(sh['settings']['length'], 16.0)
        for bad in ({'format': 'x'}, {'v': 9}, {'lanes': [{'name': 'a'}, {'name': 'a'}]},
                    {'markers': [[1, 'a'], [2, 'a']]}, {'clips': [{'id': 'a', 'src': 's', 'dur': 1},
                                                                {'id': 'a', 'src': 's', 'dur': 1}]}, []):
            with self.assertRaises(API.OpError, msg=repr(bad)):
                API.norm_show(bad, cur)

    def test_merge(self):
        cur = demo_show()
        sh = API.merge_show(cur, {'lanes': [{'name': 'level', 'keys': [[0, 1]]}, {'name': 'extra'}],
                                  'markers': [[2, 'Drop'], [3, 'New']], 'clips': [{'id': 'c', 'src': 'c.mp4', 'dur': 2}]})
        self.assertEqual([l['name'] for l in sh['lanes']], ['drift', 'level', 'extra'])
        self.assertEqual(sh['lanes'][1]['keys'], [[0.0, 1.0, 'linear']])
        self.assertEqual(sh['markers'], [[0.0, 'Intro'], [2.0, 'Drop'], [3.0, 'New']])
        self.assertEqual([c['id'] for c in sh['clips']], ['ramp', 'c'])

    def test_exports(self):
        sh = demo_show()
        text, n, names = API.lanes_csv(sh, 0, 1, 4)
        lines = text.strip().split('\n')
        self.assertEqual(lines[0], 'frame,time,"level","drift"')
        self.assertEqual(n, 4)
        self.assertEqual(lines[2].split(',')[:3], ['1', '0.25', '0.0625'])   # level linear 0 -> 1 over 4 s
        doc = API.markers_doc(sh)
        self.assertEqual(doc['markers'][1], {'t': 8.0, 'name': 'Drop', 'frame': 240, 'smpte': '00:00:08:00',
                                             'bars': '5.1.1'})
        self.assertEqual(API.markers_csv(sh).split('\n')[2], '8,240,00:00:08:00,"Drop"')
        self.assertEqual(API.lane_values(sh, 8.0), {'level': 0.25, 'drift': TL.lane_value([(0.0, -0.5, 'bezier'), (16.0, 0.5, 'bezier')], 8.0)})

    def test_record_plan(self):
        p = API.record_plan(2.0, 4.0, 30, 16, 60)
        self.assertEqual((p['frames'], p['cooks'], p['dt']), (60, 120, 1 / 60.0))
        self.assertEqual(API.record_plan(0, 1.01, 30, 16, 30)['frames'], 31)
        for a, b in ((4, 2), (-1, 2), (0, 20)):
            with self.assertRaises(API.OpError):
                API.record_plan(a, b, 30, 16, 60)

    def test_transport_plan(self):
        ctx = API.Ctx.of(demo_show())
        cur = {'seek': 5.0, 'play': False, 'inpoint': 2.0, 'outpoint': 10.0, 'length': 16.0}
        tp = lambda a, **d: API.transport_plan(a, d, cur, ctx, [4.0, 6.0])  # noqa: E731
        self.assertEqual(tp('play'), {'Play': True})
        self.assertEqual(tp('toggle'), {'Play': True})
        self.assertEqual(tp('stop'), {'Play': False, 'Seek': 2.0})
        self.assertEqual(tp('end'), {'Seek': 10.0})
        self.assertEqual(tp('seek', t='@Drop'), {'Seek': 8.0})
        self.assertEqual(tp('seek', frame=45), {'Seek': 1.5})
        self.assertAlmostEqual(tp('step', n=-3)['Seek'], 4.9)
        self.assertEqual(tp('next_marker'), {'Seek': 8.0})
        self.assertEqual(tp('prev_key'), {'Seek': 4.0})
        self.assertEqual(tp(None, rate=2, loop=False, outpoint='8bar'), {'Rate': 2.0, 'Loop': False, 'Outpoint': 16.0})
        for bad in (('seek', {'t': 99}), ('fly', {}), (None, {'rate': 9})):
            with self.assertRaises(API.OpError):
                API.transport_plan(bad[0], bad[1], cur, ctx, [])
        with self.assertRaises(API.OpError):
            API.transport_plan('prev_marker', {}, dict(cur, seek=0.0), ctx, [])


# ---------------------------------------------------------------- fakes for the TD-side text
class Cell(object):
    def __init__(self, v):
        self.val = str(v)


class Par(object):
    def __init__(self, v):
        self.v = v

    def eval(self):
        return self.v

    @property
    def val(self):
        return self.v

    @val.setter
    def val(self, x):
        self.v = x

    def __float__(self):
        return float(self.v)

    def __int__(self):
        return int(self.v)

    def __bool__(self):
        return bool(self.v)


class Pars(object):
    def __init__(self, d):
        object.__setattr__(self, '_d', dict((k, Par(v)) for k, v in d.items()))

    def __getattr__(self, n):
        try:
            return self._d[n]
        except KeyError:
            raise AttributeError(n)

    def __setattr__(self, n, v):
        self._d[n].val = v


class Table(object):
    isTOP = False

    def __init__(self, name, rows=()):
        self.name = name
        self.path = '/p/TL_timeline/' + name
        self._rows = [list(map(str, r)) for r in rows]
        self.viewer = False

    def rows(self):
        return [[Cell(c) for c in r] for r in self._rows]

    def destroy(self):
        self._parent.kids.pop(self.name, None)
        self._parent.destroyed.append(self.name)

    def clear(self):
        self._rows = []

    def appendRow(self, r):
        self._rows.append([str(c) for c in r])

    @property
    def text(self):
        return '\n'.join('\t'.join(r) for r in self._rows)


class Mod(object):
    isTOP = False

    def __init__(self, name, module):
        self.name, self.module = name, module


class Comp(object):
    def __init__(self, path, children, pars):
        self.path = path
        self.kids = dict((c.name, c) for c in children)
        self.par = Pars(pars)
        self.storage = {}
        self.destroyed = []
        for k in children:
            k._parent = self

    def op(self, n):
        return self.kids.get(n)

    def ops(self, pat):
        return [o for n, o in self.kids.items() if fnmatch.fnmatch(n, pat)]

    def create(self, cls, name):
        t = Table(name)
        t._parent = self
        self.kids[name] = t
        return t

    def fetch(self, k, d=None):
        return self.storage.get(k, d)

    def store(self, k, v):
        self.storage[k] = v

    def unstore(self, k):
        self.storage.pop(k, None)


class Top(object):
    isTOP = True

    def __init__(self, name, path):
        self.name, self.path = name, path


def load_builder_text(name, var):
    ns = {}
    exec(_read(os.path.join(BUILDERS, name)), ns)
    return ns[var]


def td_module(text, extra=None):
    td = types.ModuleType('td')
    td.tableDAT = object
    saved = sys.modules.get('td')
    sys.modules['td'] = td
    try:
        m = types.ModuleType('fake_dat')
        m.__dict__.update(extra or {})
        exec(compile(text, 'fake_dat', 'exec'), m.__dict__)
    finally:
        if saved is None:
            sys.modules.pop('td', None)
        else:
            sys.modules['td'] = saved
    return m


ROOT_OP = types.SimpleNamespace(time=types.SimpleNamespace(rate=60.0))


def make_comp(clips=True):
    sh = demo_show(clips)
    tt = API.table_texts(sh)
    api_mod = types.ModuleType('tl_api_logic')
    exec(_read(os.path.join(BUILDERS, 'timeline_api_logic.py')), api_mod.__dict__)
    frame = {'n': 100}
    clock = types.SimpleNamespace()
    clock.frame = 100
    g = {'op': lambda p: ROOT_OP if p == '/' else None, 'absTime': clock,
         'project': types.SimpleNamespace(cookRate=60.0)}
    actions = td_module(load_builder_text('timeline.py', 'ACTIONS'), g)
    ext = td_module(load_builder_text('timeline_ext.py', 'EXT_TEXT'), g)
    kids = [Mod('tl_logic', TL), Mod('tl_api_logic', api_mod), Mod('tl_actions', actions),
            Mod('TimelineExt', ext), Top('program', '/p/TL_timeline/program'), Table('lane_status', [['name', 'target', 'state']])]
    if clips:
        kids.append(Mod('tl_clips_logic', CL))
    for name, rows in tt.items():
        kids.append(Table(name, rows))
    pars = {'Play': False, 'Seek': 0.0, 'Loop': True, 'Rate': 1.0, 'Inpoint': 0.0, 'Outpoint': 16.0, 'Length': 16.0,
            'Fps': 30.0, 'Bpm': 120.0, 'Beatsperbar': 4, 'Snap': True, 'Snapdiv': 1, 'Snapunit': 'beat',
            'Tcmode': 'smpte', 'Clockmode': 'realtime', 'Markername': 'Marker', 'Lane': 0, 'Timecode': '',
            'Barbeat': '', 'Marker': '', 'Lanecount': 2}
    if clips:
        pars.update({'Program': 'clips', 'Maxplayers': 2, 'Sourcemode': 'full', 'Blendmode': 'over', 'Premult': True,
                     'Fit': 'fit', 'Preroll': 0.5, 'Clipactive': 'ramp'})
    c = Comp('/p/TL_timeline', kids, pars)
    return c, ext.TimelineExt(c), clock, frame


class Extension(unittest.TestCase):
    def test_show_matches_tables(self):
        c, x, _, _ = make_comp()
        sh = x.Show()
        self.assertEqual(sh['lanes'], demo_show()['lanes'])
        self.assertEqual(sh['settings']['maxplayers'], 2)
        self.assertEqual(sorted(x.Show(['markers'])), ['format', 'markers', 'v'])
        with self.assertRaises(ValueError):
            x.Show(['nope'])

    def test_edit_writes_only_changed(self):
        c, x, _, _ = make_comp()
        lv = c.op('lane_level')
        drift_before = c.op('lane_drift')._rows
        r = x.Edit([{'op': 'add_key', 'lane': 'level', 't': 2, 'v': 0.5}, {'op': 'add_lane', 'name': 'hue',
                                                                            'target': 'h.x'},
                    {'op': 'set', 'bpm': 90}])
        self.assertTrue(r['ok'] and r['written'], r)
        self.assertEqual(r['changed'], ['lane_hue', 'lane_level', 'lanes'])
        self.assertIn(['2', '0.5', 'linear'], lv._rows)
        self.assertIs(c.op('lane_drift')._rows, drift_before)
        self.assertEqual(c.op('lane_hue')._rows, [['time', 'value', 'interp']])
        self.assertEqual(c.par.Bpm.eval(), 90.0)
        r = x.DeleteLane('hue')
        self.assertEqual(r['removed'], ['lane_hue'])
        self.assertEqual(c.destroyed, ['lane_hue'])

    def test_dry_and_atomic_write_nothing(self):
        c, x, _, _ = make_comp()
        before = c.op('lane_level')._rows
        r = x.Edit([{'op': 'add_key', 'lane': 'level', 't': 3, 'v': 1}], dry=True)
        self.assertFalse(r['written'])
        self.assertEqual(r['changed'], ['lane_level'])
        r = x.Edit([{'op': 'add_key', 'lane': 'level', 't': 3, 'v': 1}, {'op': 'delete_key', 'lane': 'level', 'at': 99}])
        self.assertFalse(r['ok'] or r['written'])
        self.assertIs(c.op('lane_level')._rows, before)

    def test_convenience_and_load(self):
        c, x, _, _ = make_comp()
        self.assertTrue(x.AddMarker('3.1.1', 'Verse')['ok'])
        self.assertTrue(x.MoveClip('ramp', start='@Verse')['ok'])
        self.assertEqual(c.op('clips')._rows[1][2], '4')
        r = x.Load({'lanes': [{'name': 'only', 'keys': [[0, 1]]}]})
        self.assertTrue(r['ok'], r)
        self.assertEqual(sorted(r['removed']), ['lane_drift', 'lane_level'])
        self.assertEqual(c.op('lanes')._rows[1][0], 'only')
        bad = x.Load({'lanes': [{'name': 'a b'}]})
        self.assertFalse(bad['ok'])
        self.assertIn('lane name', bad['error'])

    def test_export_load_round_trip_is_a_no_op(self):
        c, x, _, _ = make_comp()
        doc = json.loads(x.Export('show')['text'])
        for mode in ('replace', 'merge'):
            r = x.Load(doc, mode=mode)
            self.assertEqual((r['ok'], r['changed'], r['removed'], r['settings']), (True, [], [], {}), mode)

    def test_transport_state(self):
        c, x, _, _ = make_comp()
        r = x.Seek('@Drop')
        self.assertEqual(c.par.Seek.eval(), 8.0)
        self.assertEqual(r['t'], 8.0)
        self.assertEqual(r['values']['level'], 0.25)
        x.Play()
        self.assertTrue(c.par.Play.eval())
        x.Transport('prev_key')
        self.assertEqual(c.par.Seek.eval(), 4.0)
        st = x.State(at=['2b'])
        self.assertEqual(st['at'][0]['t'], 1.0)
        self.assertEqual(st['clips_active'], ['ramp'])
        self.assertEqual(x.Sample(4), {'level': 1.0, 'drift': TL.lane_value([(0.0, -0.5, 'bezier'), (16.0, 0.5, 'bezier')], 4.0)})

    def test_export(self):
        c, x, _, _ = make_comp()
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'sub', 'show.json')
            r = x.Export('show', f)
            with open(f) as fh:
                doc = json.load(fh)
            self.assertEqual(doc['format'], 'tl-show')
            self.assertEqual(r['bytes'], os.path.getsize(f))
            r = x.Export('lanes_csv', None, start='@Drop', end='9', fps=2)
            self.assertEqual(r['frames'], 2)
            self.assertTrue(r['text'].startswith('frame,time'))
            with self.assertRaises(ValueError):
                x.Export('show', 'rel.json')
            with self.assertRaises(ValueError):
                x.Export('pdf')

    def test_record_prepare_arm_finish(self):
        c, x, clock, _ = make_comp()
        c.par.Seek = 5.0
        c.par.Play = True
        plan = x.RecordPrepare(2, 4, 30)
        self.assertEqual((plan['frames'], plan['cooks'], plan['source']), (60, 120, '/p/TL_timeline/program'))
        self.assertEqual((c.par.Play.eval(), c.par.Seek.eval(), c.par.Inpoint.eval(), c.par.Outpoint.eval(),
                          c.par.Loop.eval()), (False, 2.0, 2.0, 4.0, False))
        with self.assertRaises(RuntimeError):
            x.RecordPrepare(2, 4, 30)
        clock.frame = 200
        self.assertTrue(x.RecordArm())
        self.assertEqual(c.fetch('tl_rec')['arm_frame'], 200)
        self.assertTrue(c.par.Play.eval())
        saved = x.RecordFinish()
        self.assertEqual(saved['Seek'], 5.0)
        self.assertEqual((c.par.Play.eval(), c.par.Seek.eval(), c.par.Loop.eval(), c.par.Outpoint.eval()),
                         (True, 5.0, True, 16.0))
        self.assertIsNone(c.fetch('tl_rec'))
        self.assertEqual(x.RecordFinish(), {})
        with self.assertRaises(ValueError):
            x.RecordPrepare(2, 4, 30, source='nope')
        self.assertIsNone(c.fetch('tl_rec'))

    def test_phase1_comp_without_clips(self):
        c, x, _, _ = make_comp(clips=False)
        self.assertIsNone(x.Show()['clips'])
        r = x.Edit([{'op': 'add_clip', 'src': 'a', 'dur': 1}])
        self.assertFalse(r['ok'])


class RecordClock(unittest.TestCase):
    """tl_actions.tick: armed take = 0 step in the arming frame, then 1/cookRate per frame (not wall time)."""

    def test_tick_steps(self):
        c, x, clock, _ = make_comp()

        class Chop(object):
            def cook(self, force=False):
                pass

            def chan(self, n):
                return None
        c.kids['clock'] = Chop()
        c.kids['lanes_eval'] = Chop()
        A = c.op('tl_actions').module
        x.RecordPrepare(2, 4, 30)
        A.tick(c)                         # not armed, paused: stays at 2
        self.assertEqual(c.par.Seek.eval(), 2.0)
        clock.frame = 300
        x.RecordArm()
        A.tick(c)                         # arming frame: no step
        self.assertEqual(c.par.Seek.eval(), 2.0)
        for k in range(1, 4):
            clock.frame = 300 + k
            A.tick(c)
        self.assertAlmostEqual(c.par.Seek.eval(), 2.0 + 3 / 60.0)
        x.RecordFinish()


class Builder(unittest.TestCase):
    def test_texts_compile_and_ascii(self):
        for name, var in (('timeline_ext.py', 'EXT_TEXT'), ('timeline.py', 'ACTIONS')):
            text = load_builder_text(name, var)
            text.encode('ascii')
            compile(text, name, 'exec')
        for f in ('timeline_api_logic.py', 'timeline_ext.py', 'timeline.py'):
            _read(os.path.join(BUILDERS, f)).encode('ascii')

    def test_build_api_sets_extension(self):
        ns = {'TL_ROOT': BUILDERS, 'textDAT': object}
        made = {}

        class D(object):
            def __init__(self, n):
                self.name, self.text, self.comment = n, '', ''

        def _get(comp, cls, name):
            made.setdefault(name, D(name))
            return made[name]
        ns['_get'] = _get
        exec(_read(os.path.join(BUILDERS, 'timeline_ext.py')), ns)
        comp = types.SimpleNamespace(par=types.SimpleNamespace(ext0object=Par(''), ext0name=Par(''),
                                                               ext0promote=Par(False)),
                                     initializeExtensions=lambda: None)
        self.assertEqual(ns['build_api'](comp), [])
        self.assertEqual(comp.par.ext0object.val, "op('./TimelineExt').module.TimelineExt(me)")
        self.assertTrue(comp.par.ext0promote.val)
        self.assertIn('def apply_ops', made['tl_api_logic'].text)
        self.assertIn('class TimelineExt', made['TimelineExt'].text)


# ---------------------------------------------------------------- handlers commands (route + record chain)
class Handlers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, HERE)
        import test_handlers  # noqa: F401  installs the stub td module, imports handlers
        cls.h = test_handlers.handlers

    def test_registered(self):
        h = self.h
        for c in ('timeline_state', 'timeline_show', 'timeline_edit', 'timeline_load', 'timeline_transport',
                  'timeline_export', 'timeline_record'):
            self.assertIn(c, h.COMMANDS)
        self.assertIn('timeline_edit', h.MUTATING)
        self.assertIn('timeline_load', h.MUTATING)
        self.assertNotIn('timeline_transport', h.MUTATING)

    def test_routes_to_ext(self):
        h = self.h
        c, x, _, _ = make_comp()
        saved = h._tl
        h._tl = lambda comp=None: x
        try:
            self.assertTrue(h.cmd_timeline_edit([{'op': 'add_marker', 't': 1, 'name': 'A'}])['ok'])
            self.assertEqual(h.cmd_timeline_transport(action='seek', t='@A')['t'], 1.0)
            self.assertEqual(h.cmd_timeline_show(parts=['markers'])['markers'][1], [1.0, 'A'])
            with self.assertRaises(ValueError):
                h.cmd_timeline_export('/tmp/x.txt', what='show')
            with self.assertRaises(ValueError):
                h.cmd_timeline_export('/tmp/x.json', what='nope')
            with self.assertRaises(ValueError):
                h.cmd_timeline_record('/tmp/x.mov', codec='h264')
        finally:
            h._tl = saved

    def test_record_chain_restores(self):
        h = self.h
        c, x, _, _ = make_comp()
        calls = {}

        def fake_render(source, file, frames, fps=30, codec='prores4444', timeout_s=None, on_start=None):
            calls.update(source=source, frames=frames, fps=fps, codec=codec)

            def step():
                on_start()
                return h.Pending(2, lambda: {'file': file, 'frames_asked': frames})
            return h.Pending(1, step)
        saved = h._tl, h.offline_render
        h._tl, h.offline_render = (lambda comp=None: x), fake_render
        try:
            c.par.Seek = 7.0
            p = h.cmd_timeline_record('/tmp/take.mov', start=0, end=1, fps=30)
            self.assertIsInstance(p, h.Pending)
            self.assertEqual(calls, {'source': '/p/TL_timeline/program', 'frames': 30, 'fps': 30.0, 'codec': 'prores422hq'})
            p2 = p.finish()
            self.assertTrue(c.fetch('tl_rec')['armed'])
            r = p2.finish()
            self.assertEqual(r['frames_asked'], 30)
            self.assertEqual(r['timeline']['cooks'], 60)
            self.assertEqual(r['restored']['Seek'], 7.0)
            self.assertIsNone(c.fetch('tl_rec'))
            self.assertEqual(c.par.Seek.eval(), 7.0)

            def boom(*a, **k):
                def step():
                    raise RuntimeError('codec menu')
                return h.Pending(1, step)
            h.offline_render = boom
            p = h.cmd_timeline_record('/tmp/take.mov', start=0, end=1)
            with self.assertRaises(RuntimeError):
                p.finish()
            self.assertIsNone(c.fetch('tl_rec'))
        finally:
            h._tl, h.offline_render = saved


if __name__ == '__main__':
    unittest.main()
