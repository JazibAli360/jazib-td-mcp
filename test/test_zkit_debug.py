"""Offline tests for the zkit skin of the jazib-td debug panel (zkit_logic.debug_* + zkit.style_debug_panel). No TD.
Run: cd <repo> && python3 -I -m unittest discover -s test -p 'test_zkit_debug.py'
"""
import importlib.util
import os
import sys
import types
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(ROOT, 'builders'))
import zkit_logic as L  # noqa: E402

_spec = importlib.util.spec_from_file_location('dbg_rt_for_zkit', os.path.join(ROOT, 'td', 'debug_panel_rt.py'))
RT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RT)


def kinds():
    return [k for k, _t, _p in RT.view_lines(['', ''], [], [], 0, [])]


class Bands(unittest.TestCase):
    def test_bands_follow_the_panel_slots(self):
        k = kinds()
        b = L.debug_bands(k)
        self.assertEqual(len(b), len(k))
        self.assertEqual(b[:2], [L.BAND['head']] * 2)
        titles = [i for i, x in enumerate(k) if x == 'title']
        self.assertEqual([i for i, x in enumerate(b) if x == L.BAND['title']], titles)
        for t in titles[1:]:
            self.assertEqual(b[t - 1], L.BAND['none'], 'the blank line closing a section stays plain')
        self.assertEqual(b[titles[0] + 2], L.BAND['zebra'])
        self.assertEqual(b[titles[0] + 1], L.BAND['none'])
        self.assertEqual(b[-1], L.BAND['zebra'] if (len(k) - 1 - titles[-1]) % 2 == 0 else L.BAND['none'])
        # every slot fits the view (rt geometry)
        self.assertLessEqual(RT.PAD_TOP + len(k) * RT.LINE_H, RT.VIEW_H)

    def test_bg_shader_static_and_sized(self):
        b = L.debug_bands(kinds())
        for theme in L.DEBUG_THEMES:
            s = L.debug_bg_glsl(b, theme, RT.VIEW_H, RT.PAD_TOP, RT.LINE_H)
            self.assertIn('const int N = %d;' % len(b), s)
            self.assertIn('int[N](' + ', '.join(str(x) for x in b) + ')', s)
            self.assertNotIn('sTD2DInputs', s, 'no inputs: cooks once')
            self.assertNotIn('uTime', s)
            self.assertIn('i >= 0 && i < N', s, 'array index guarded (T-35)')
            s.encode('ascii')

    def test_graph_shader_texture_buffer_clamped(self):
        s = L.debug_graph_glsl('night', 60.0)
        self.assertIn('uniform samplerBuffer uFps;', s)
        self.assertIn('textureSize(uFps)', s)
        self.assertIn('clamp(int(floor(f)), 0, n - 1)', s)
        self.assertIn('min(i0 + 1, n - 1)', s)
        self.assertIn('const float RATE = 60.000;', s)
        self.assertNotIn('sTD2DInputs', s, 'no CHOP to TOP (0.7 ms GPU a cook, measured live)')
        s.encode('ascii')

    def test_theme_colours_distinct(self):
        for t in L.DEBUG_THEMES.values():
            tx = t['text']
            self.assertEqual(sorted(tx), ['body', 'err', 'head', 'title'])
            self.assertNotEqual(tx['err'], tx['body'])
            self.assertNotEqual(t['accent'], t['warn'])


# ---------------------------------------------------------------- fake TD for style_debug_panel
class P(object):
    def __init__(self, v=0):
        self.val, self.expr = v, ''
        self.pulsed = 0

    def eval(self):
        return self.val

    def pulse(self):
        self.pulsed += 1


class Pars(object):
    def __getattr__(self, n):
        p = P()
        object.__setattr__(self, n, p)
        return p


class Conn(object):
    def __init__(self):
        self.connections = []

    def connect(self, o):
        self.connections = [types.SimpleNamespace(owner=o)]

    def disconnect(self):
        self.connections = []


class Op(object):
    def __init__(self, parent, name, typ):
        self.parent_, self.name, self.OPType = parent, name, typ
        self.path = (parent.path + '/' + name) if parent else name
        self.par = Pars()
        self.valid, self.viewer, self.text, self.docked = True, False, '', []
        self.inputConnectors = [Conn() for _ in range(8)]
        self.seq = types.SimpleNamespace(array=types.SimpleNamespace(numBlocks=0))
        self.kids, self.store_ = {}, {}
        self.isOpen = False

    @property
    def inputs(self):
        return [c.connections[0].owner for c in self.inputConnectors if c.connections]

    def op(self, n):
        return self.kids.get(n)

    def create(self, cls, n):
        o = Op(self, n, cls.__name__)
        self.kids[n] = o
        return o

    def store(self, k, v):
        self.store_[k] = v


def fake_panel():
    c = Op(None, '/project1/debug', 'containerCOMP')
    for n, t in (('rt', 'textDAT'), ('view_comp', 'compositeTOP'), ('view_bg', 'constantTOP'),
                 ('debug_window', 'windowCOMP'), ('fps_graph', 'opviewerCOMP'), ('fps_chop', 'dattoCHOP')):
        c.kids[n] = Op(c, n, t)
    for k in ('head', 'title', 'body', 'err'):
        c.kids['tx_' + k] = Op(c, 'tx_' + k, 'textTOP')
        c.view_comp_k = None
    vc = c.op('view_comp')
    for i, k in enumerate(('head', 'title', 'body', 'err')):
        vc.inputConnectors[i].connect(c.op('tx_' + k))
    vc.inputConnectors[4].connect(c.op('view_bg'))
    c.op('rt').module = RT
    c.op('fps_graph').par.h.val = 110
    return c


def load_zkit(destroyed):
    with open(os.path.join(ROOT, 'builders', 'zkit.py')) as fh:
        src = fh.read()
    tdm = types.SimpleNamespace(**{n: type(n, (), {}) for n in ('textDAT', 'glslTOP', 'choptoTOP')})
    tdm.project = types.SimpleNamespace(cookRate=60.0)
    runs = []
    tdm.run = lambda code, delayFrames=0: runs.append((code, delayFrames))
    ns = {'__name__': 'zkit_dbg_t', 'td': tdm, 'safe_destroy': lambda o: destroyed.append(o.name),
          'op': lambda p: None}
    exec(compile(src, 'zkit.py', 'exec'), ns)
    return ns, runs


class Style(unittest.TestCase):
    def test_style_rewires_bg_and_graph_then_idempotent(self):
        destroyed = []
        ns, runs = load_zkit(destroyed)
        c = fake_panel()
        c.op('debug_window').isOpen = True
        r = ns['style_debug_panel'](c)
        vc = c.op('view_comp')
        self.assertIs(vc.inputConnectors[4].connections[0].owner, c.op('zk_bg'), 'bg swapped in the same slot')
        self.assertEqual([o.name for o in vc.inputs[:4]], ['tx_head', 'tx_title', 'tx_body', 'tx_err'])
        g = c.op('zk_graph')
        self.assertEqual((g.par.array0name.val, g.par.array0arraytype.val, g.par.array0chop.val),
                         ('uFps', 'texturebuffer', 'fps_chop'))
        self.assertEqual(g.seq.array.numBlocks, 1)
        self.assertEqual(c.op('fps_graph').par.opviewer.expr, "parent().op('zk_graph')")
        self.assertEqual(c.op('tx_err').par.fontcolorr.val, L.DEBUG_THEMES['night']['text']['err'][0])
        self.assertEqual(c.op('debug_window').par.winclose.pulsed, 1, 'T-70: window closed first')
        self.assertEqual(len(runs), 1, 'reopened later')
        self.assertTrue(r['window_reopened'])
        self.assertEqual(c.store_['zk_skin'], 'night')
        r2 = ns['style_debug_panel'](c)
        self.assertEqual(r2['changed'], [], 'second run writes nothing (no churn)')
        self.assertEqual(destroyed, [])

    def test_old_chop_to_top_removed_and_bad_theme(self):
        destroyed = []
        ns, _runs = load_zkit(destroyed)
        c = fake_panel()
        c.kids['zk_graph_tex'] = Op(c, 'zk_graph_tex', 'choptoTOP')
        r = ns['style_debug_panel'](c)
        self.assertIn('zk_graph_tex', destroyed)
        self.assertIn('-zk_graph_tex', r['changed'])
        self.assertFalse(r['window_reopened'])
        with self.assertRaises(ValueError):
            ns['style_debug_panel'](c, theme='neon')


if __name__ == '__main__':
    unittest.main()
