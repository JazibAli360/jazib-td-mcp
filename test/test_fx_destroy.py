"""Offline tests for the FX_destroy rack + modules (builders/fx_destroy*.py): chain wiring, module specs (every preset
key is a par, Amount first, menus in range), the Effector/Point expression. Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_destroy.py'"""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(os.path.dirname(HERE), 'builders')
NS = {}
exec(open(os.path.join(B, 'fx_destroy.py')).read(), NS)


def module(name):
    ns = dict(NS)
    exec(open(os.path.join(B, 'fx_destroy_%s.py' % name)).read(), ns)
    return ns


def par_names(pages):
    out = {}
    for _page, pars in pages:
        for name, style, default, o in pars:
            if style == 'RGB':
                for k in 'rgb':
                    out[name + k] = ('Float', None, {})
            else:
                out[name] = (style, default, o)
    return out


class Rack(unittest.TestCase):
    def test_default_rows_chain(self):
        rows = [dict(zip(NS['COLS'], r)) for r in NS['DEFAULT_ROWS']]
        self.assertEqual(NS['plan_chain'](rows), ['melt1', 'burn1', 'shatter1'])
        e = NS['chain_edges'](['melt1', 'burn1', 'shatter1'])
        self.assertIn(('burn1', 0, 'melt1_slot'), e)
        self.assertIn(('panic', 0, 'shatter1_slot'), e)
        self.assertEqual(len(e), 6 * 3 + 3)       # live first build: 21 wires changed

    def test_point_expr_falls_back(self):
        e = NS['pt_expr']('u')
        self.assertIn('Effector', e)
        self.assertIn('Pointu', e)
        self.assertIn('par.Effector2.eval()', NS['pt_expr']('v', '2'))
        self.assertIn('par.ty', NS['pt_expr']('v', '2'))


class Modules(unittest.TestCase):
    def check(self, name):
        M = module(name)
        self.assertEqual(M['MODULE'], name)
        pars = par_names(M['PAGES'])
        self.assertEqual(M['PAGES'][0][1][0][0], 'Amount')
        for page in M['PANEL_PAGES']:
            self.assertIn(page, [p for p, _ in M['PAGES']])
        self.assertTrue(3 <= len(M['PRESETS']) <= 5)
        for _slot, _pname, vals in M['PRESETS']:
            for k, v in vals.items():
                self.assertIn(k, pars, '%s preset uses unknown par %s' % (name, k))
                style, _d, o = pars[k]
                if style == 'Menu':
                    self.assertTrue(0 <= v < len(o['names']), '%s %s menu index %s' % (name, k, v))
        for t in ('State',):
            self.assertIn(t, [p for p, _ in M['PAGES']])
        return M, pars

    def test_melt(self):
        M, pars = self.check('melt')
        self.assertIn('Resettime', pars)
        self.assertIn('fxMask', M['FX'] + NS['mask_glsl'](2))

    def test_burn(self):
        M, pars = self.check('burn')
        for k in ('Hotcolorr', 'Embercolorg', 'Charcolorb', 'Effector2', 'Masksource'):
            self.assertIn(k, pars)

    def test_shatter(self):
        M, pars = self.check('shatter')
        for k in ('Trigger', 'Hittime', 'Beatchop', 'Crackcolorr'):
            self.assertIn(k, pars)
        self.assertIn('TDImageLoadOutput(2', M['STATE'])     # 3 buffers in place (FX6 5a)
        self.assertIn('atomicAdd', M['FX'])


class _Par(object):
    def __init__(self, v):
        self.v = v

    def eval(self):
        return self.v


def eval_expr(e, now, **pars):
    """Evaluate a uniform expression string like TD would: parent().par.X.eval(), absTime.seconds, math."""
    import math
    import types
    owner = types.SimpleNamespace(par=types.SimpleNamespace(**dict((k, _Par(v)) for k, v in pars.items())))
    return eval(e, {'math': math, 'parent': lambda: owner, 'absTime': types.SimpleNamespace(seconds=now)})


class Stamps(unittest.TestCase):
    """T-155: State stamps from another clock (TD relaunch / tox move) are void in the uniforms."""

    def test_stamp_expr(self):
        e = NS['stamp_expr']('Resettime')
        self.assertEqual(eval_expr(e, 100.0, Resettime=10554.7), -1.0)      # stale: later than now
        self.assertEqual(eval_expr(e, 100.0, Resettime=99.5), 99.5)          # normal stamp passes
        self.assertEqual(eval_expr(e, 100.0, Resettime=100.04), 100.04)      # within the 0.05 s slack
        self.assertEqual(eval_expr(e, 100.0, Resettime=-1.0), -1.0)

    def test_hit_expr(self):
        e = NS['hit_expr']()
        self.assertEqual(eval_expr(e, 100.0, Hittime=10554.7, Auto=0.0), -1.0)
        self.assertEqual(eval_expr(e, 100.0, Hittime=99.0, Auto=0.0), 99.0)  # a normal hit still fires
        self.assertEqual(eval_expr(e, 101.3, Hittime=10554.7, Auto=2.0), 100.0)   # stale stamp no longer hides Auto
        self.assertEqual(eval_expr(e, 101.3, Hittime=101.2, Auto=2.0), 101.2)

    def test_every_module_voids_its_stamps(self):
        src = dict((n, open(os.path.join(B, 'fx_destroy_%s.py' % n)).read())
                   for n in ('melt', 'burn', 'crack', 'explode', 'disintegrate', 'shatter'))
        for n in ('melt', 'burn', 'crack', 'explode', 'disintegrate'):
            self.assertIn("H['stamp']('Resettime')", src[n], n)
            self.assertNotIn("P.format('Resettime')", src[n], n)
        for n in ('crack', 'explode', 'disintegrate'):
            self.assertIn("H['hit']()", src[n], n)
        for n in src:
            self.assertNotIn("P.format('Hittime')", src[n], n)      # no raw Hittime reaches a uniform
        sh = module('shatter')
        self.assertEqual(sh['state_uniforms'](NS['pt_expr'])[0][1][1], NS['hit_expr']())
        self.assertIs(NS['H']['stamp'], NS['stamp_expr'])

    def test_melt_burn_reset_ge(self):
        # T-160: a Reset stamp equal to the last cook (state cooked earlier in the pulse's frame) still resets
        self.assertIn('uC.y >= s.a', module('melt')['STATE'])
        self.assertIn('uB.y >= s.a', module('burn')['STATE'])



# ---- slot_gate (T-201): same checks as test_fx_glitch SlotGate, on this rack's copy of the gate
_GATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'builders', 'fx_destroy.py')
with open(_GATE_FILE) as _fh:
    GATE_SRC = _fh.read()
GATE_NS = {}
exec(GATE_SRC, GATE_NS)

class _GCell(object):
    def __init__(self, v):
        self.val = v


class _GTable(object):
    def __init__(self, rows):
        self.rows = rows                                  # {name: {col: val}}

    def __getitem__(self, k):
        r = self.rows.get(k[0])
        return None if r is None or k[1] not in r else _GCell(r[k[1]])


class _GRack(object):
    def __init__(self, rows):
        self.t = None if rows is None else _GTable(rows)

    def op(self, n):
        return self.t if n == 'slots' else None


def _Ggate_index(rows, name='m1'):
    """Evaluate SLOT_GATE_E the way TD does, with parent() = the module, parent(2) = the rack."""
    from types import SimpleNamespace as S
    mod, rack = S(name=name), _GRack(rows)
    return eval(GATE_NS['SLOT_GATE_E'], {'parent': lambda n=1: mod if n == 1 else rack, 'getattr': getattr,
                                     'float': float, 'int': int})


class _GConn(object):
    def __init__(self, owner, inp=False):
        self.owner, self.inp, self.connections = owner, inp, []

    def connect(self, src):
        src = src if isinstance(src, _GConn) else src.outputConnectors[0]
        self.connections = [src]


class _GPar(object):
    def __init__(self):
        self.expr, self.mode = '', None


class _GOp(object):
    def __init__(self, name, typ, parent_=None):
        from types import SimpleNamespace as S
        self.name, self.OPType, self.valid, self.isCOMP, self.viewer, self.comment = name, typ, True, False, False, ''
        self.inputConnectors = [_GConn(self, True) for _ in range(3)]
        self.outputConnectors = [_GConn(self)]
        self.par = S(index=_GPar())
        self.parent_ = parent_


class _GMod(object):
    def __init__(self, src_name='fx', src_expr=''):
        self.kids = {}
        for n, t in (('in1', 'inTOP'), ('out1', 'outTOP'), (src_name, 'switchTOP')):
            self.kids[n] = _GOp(n, t, self)
        self.kids[src_name].par.index.expr = src_expr
        self.kids[src_name].inputConnectors[0].connect(self.kids['in1'])
        self.kids['out1'].inputConnectors[0].connect(self.kids[src_name])

    def op(self, n):
        return self.kids.get(n)

    def create(self, cls, n):
        self.kids[n] = _GOp(n, cls.__name__, self)
        return self.kids[n]


class _GswitchTOP(object):  # noqa: N801  (TD's class name, only __name__ is read)
    pass


class _GParMode(object):
    EXPRESSION = 'expr'


def _Gsrc_of(o, i=0):
    c = o.inputConnectors[i].connections
    return c[0].owner.name if c else None


class SlotGate(unittest.TestCase):
    """T-198 for every rack: a slot that is off (enabled 0 / mix <= 0) passes in1 inside the module, so a visible
    <name>_mix viewer no longer pulls the module; on = the module's own output, unchanged."""

    def test_slot_off_matches_slot_switch(self):
        so = GATE_NS['slot_off']
        for en, mx, off in (('1', '1', False), ('1', '0.5', False), ('0', '1', True), ('1', '0', True),
                            ('', '1', True), ('1', '', True), ('1', '-1', True), ('1.0', '1', False),
                            (None, None, False)):
            self.assertEqual(so(en, mx), off, (en, mx))
            sw = 0 if not int(float(en or 0)) or float(mx or 0) <= 0 else 1   # the rack's <name>_slot index test
            if en is not None:
                self.assertEqual(off, sw == 0)

    def test_gate_expression(self):
        self.assertEqual(_Ggate_index({'m1': {'enabled': '1', 'mix': '1'}}), 1)
        self.assertEqual(_Ggate_index({'m1': {'enabled': '1', 'mix': '0.3'}}), 1)
        self.assertEqual(_Ggate_index({'m1': {'enabled': '0', 'mix': '1'}}), 0)
        self.assertEqual(_Ggate_index({'m1': {'enabled': '1', 'mix': '0'}}), 0)
        self.assertEqual(_Ggate_index({}), 1)                       # no row = on
        self.assertEqual(_Ggate_index(None), 1)                     # no slots table = on

    def test_gate_needed(self):
        self.assertTrue(GATE_NS['gate_needed']('out_sel', '0 if parent().par.Amount.eval() <= 0 else 1'))
        self.assertTrue(GATE_NS['gate_needed']('fx', ''))
        self.assertFalse(GATE_NS['gate_needed']('out_sel', "0 if parent(2).op('slots') is not None else 1"))

    def test_stages(self):
        st = GATE_NS['gate_stages']([{'ops': ['in1']}, {'ops': ['out_sel', 'out1']}])
        self.assertEqual(st[1]['ops'], ['out_sel', 'slot_gate', 'out1'])
        self.assertEqual(GATE_NS['gate_stages'](st)[1]['ops'], ['out_sel', 'slot_gate', 'out1'])   # idempotent
        self.assertEqual(GATE_NS['gate_stages']([{'ops': ['fx']}])[0]['ops'], ['fx', 'slot_gate'])

    def _ns(self):
        ns = {'switchTOP': _GswitchTOP, 'ParMode': _GParMode}
        exec(GATE_SRC, ns)                                        # rack functions bound to the fake TD globals
        ns['_sd'] = lambda o: None
        return ns

    def test_wiring_idempotent(self):
        ns = self._ns()
        m = _GMod()
        st = ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])
        g = m.op('slot_gate')
        self.assertEqual((_Gsrc_of(g, 0), _Gsrc_of(g, 1), _Gsrc_of(m.op('out1'))), ('in1', 'fx', 'slot_gate'))
        self.assertEqual(g.par.index.expr, GATE_NS['SLOT_GATE_E'])
        self.assertEqual(st[0]['ops'], ['fx', 'slot_gate', 'out1'])
        m.op('out1').inputConnectors[0].connect(m.op('fx'))      # a module rebuild re-wires out1 to its source
        ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])
        self.assertEqual((_Gsrc_of(g, 0), _Gsrc_of(g, 1), _Gsrc_of(m.op('out1'))), ('in1', 'fx', 'slot_gate'))
        ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])           # already gated: unchanged
        self.assertEqual(_Gsrc_of(m.op('out1')), 'slot_gate')

    def test_slot_aware_out_sel_left_alone(self):              # GEN_points OUT_SEL_E
        ns = self._ns()
        m = _GMod('out_sel', "0 if parent().par.Amount.eval() <= 0 or (parent(2).op('slots') is not None) else 1")
        ns['_slot_gate'](m, [{'ops': ['out_sel', 'out1']}])
        self.assertIsNone(m.op('slot_gate'))
        self.assertEqual(_Gsrc_of(m.op('out1')), 'out_sel')


def _Gfamily_src(name):
    with open(os.path.join(BDIR, name + '.py')) as fh:
        return fh.read()


def _Ginstance_body(src):
    i = src.find('\ndef _instance(')
    if i < 0:
        return None
    j = src.find('\ndef ', i + 1)
    return src[i:j if j > 0 else len(src)]



class GateInInstance(unittest.TestCase):
    def test_instance_gates(self):
        i = GATE_SRC.index('\ndef _instance(')
        self.assertIn("stages = _slot_gate(m, M['build'](m, H))", GATE_SRC[i:GATE_SRC.index('\ndef ', i + 1)])
        self.assertIn('def gate_upgrade(', GATE_SRC)


if __name__ == '__main__':
    unittest.main()
