"""Offline tests for the FX_glitch rack's pure parts (builders/fx_glitch.py). Run:
cd jazib-td-mcp && python3 -I -m unittest discover -s test -p 'test_fx_glitch.py'"""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
NS = {}
exec(open(os.path.join(os.path.dirname(HERE), 'builders', 'fx_glitch.py')).read(), NS)


class Chain(unittest.TestCase):
    def test_order_then_position(self):
        rows = [{'name': 'a', 'order': '2'}, {'name': 'b', 'order': '1'}, {'name': 'c', 'order': '2'}]
        self.assertEqual(NS['plan_chain'](rows), ['b', 'a', 'c'])

    def test_empty_chain_is_passthrough(self):
        self.assertEqual(NS['chain_edges']([]), [('panic', 0, 'img_src'), ('panic', 1, 'img_src'), ('out1', 0, 'panic')])

    def test_two_slots(self):
        e = NS['chain_edges'](['s1', 's2'])
        self.assertIn(('s2', 0, 's1_slot'), e)
        self.assertIn(('s2_slot', 2, 's2_mix'), e)
        self.assertIn(('panic', 0, 's2_slot'), e)
        self.assertEqual(len(e), 6 * 2 + 3)

    def test_add_second_changes_seven_wires(self):
        a = set(NS['chain_edges'](['s1']))
        b = set(NS['chain_edges'](['s1', 's2']))
        self.assertEqual(len(b - a), 7)          # 6 new slot wires + panic in0 (live: add -> 7, remove -> 1)

    def test_next_name(self):
        self.assertEqual(NS['next_name']('smear', {'smear1', 'smear3'}), 'smear2')


class ModuleArrange(unittest.TestCase):  # T-163: feedback modules lay out in rows
    def test_feedback_module_rows(self):
        from types import SimpleNamespace as S
        fb = S(children=[S(OPType='glslTOP'), S(OPType='feedbackTOP'), S(OPType='nullTOP')])
        plain = S(children=[S(OPType='glslTOP'), S(OPType='nullTOP')])
        self.assertEqual(NS['module_arrange'](fb), 'rows')
        self.assertEqual(NS['module_arrange'](plain), 'mixed')
        self.assertEqual(NS['module_arrange'](S(children=[])), 'mixed')

    def test_module_layout_uses_it(self):
        self.assertIn('arrange=module_arrange(m)', SRC_FXG)


with open(os.path.join(os.path.dirname(HERE), 'builders', 'fx_glitch.py')) as _fh:
    SRC_FXG = _fh.read()


class _Cell(object):
    def __init__(self, v):
        self.val = v


class _Table(object):
    def __init__(self, rows):
        self.rows = rows                                  # {name: {col: val}}

    def __getitem__(self, k):
        r = self.rows.get(k[0])
        return None if r is None or k[1] not in r else _Cell(r[k[1]])


class _Rack(object):
    def __init__(self, rows):
        self.t = None if rows is None else _Table(rows)

    def op(self, n):
        return self.t if n == 'slots' else None


def _gate_index(rows, name='m1'):
    """Evaluate SLOT_GATE_E the way TD does, with parent() = the module, parent(2) = the rack."""
    from types import SimpleNamespace as S
    mod, rack = S(name=name), _Rack(rows)
    return eval(NS['SLOT_GATE_E'], {'parent': lambda n=1: mod if n == 1 else rack, 'getattr': getattr,
                                     'float': float, 'int': int})


class _Conn(object):
    def __init__(self, owner, inp=False):
        self.owner, self.inp, self.connections = owner, inp, []

    def connect(self, src):
        src = src if isinstance(src, _Conn) else src.outputConnectors[0]
        self.connections = [src]


class _Par(object):
    def __init__(self):
        self.expr, self.mode = '', None


class _Op(object):
    def __init__(self, name, typ, parent_=None):
        from types import SimpleNamespace as S
        self.name, self.OPType, self.valid, self.isCOMP, self.viewer, self.comment = name, typ, True, False, False, ''
        self.inputConnectors = [_Conn(self, True) for _ in range(3)]
        self.outputConnectors = [_Conn(self)]
        self.par = S(index=_Par())
        self.parent_ = parent_


class _Mod(object):
    def __init__(self, src_name='fx', src_expr=''):
        self.kids = {}
        for n, t in (('in1', 'inTOP'), ('out1', 'outTOP'), (src_name, 'switchTOP')):
            self.kids[n] = _Op(n, t, self)
        self.kids[src_name].par.index.expr = src_expr
        self.kids[src_name].inputConnectors[0].connect(self.kids['in1'])
        self.kids['out1'].inputConnectors[0].connect(self.kids[src_name])

    def op(self, n):
        return self.kids.get(n)

    def create(self, cls, n):
        self.kids[n] = _Op(n, cls.__name__, self)
        return self.kids[n]


class switchTOP(object):  # noqa: N801  (TD's class name, only __name__ is read)
    pass


class ParMode(object):
    EXPRESSION = 'expr'


def _src_of(o, i=0):
    c = o.inputConnectors[i].connections
    return c[0].owner.name if c else None


class SlotGate(unittest.TestCase):
    """T-198 for every rack: a slot that is off (enabled 0 / mix <= 0) passes in1 inside the module, so a visible
    <name>_mix viewer no longer pulls the module; on = the module's own output, unchanged."""

    def test_slot_off_matches_slot_switch(self):
        so = NS['slot_off']
        for en, mx, off in (('1', '1', False), ('1', '0.5', False), ('0', '1', True), ('1', '0', True),
                            ('', '1', True), ('1', '', True), ('1', '-1', True), ('1.0', '1', False),
                            (None, None, False)):
            self.assertEqual(so(en, mx), off, (en, mx))
            sw = 0 if not int(float(en or 0)) or float(mx or 0) <= 0 else 1   # the rack's <name>_slot index test
            if en is not None:
                self.assertEqual(off, sw == 0)

    def test_gate_expression(self):
        self.assertEqual(_gate_index({'m1': {'enabled': '1', 'mix': '1'}}), 1)
        self.assertEqual(_gate_index({'m1': {'enabled': '1', 'mix': '0.3'}}), 1)
        self.assertEqual(_gate_index({'m1': {'enabled': '0', 'mix': '1'}}), 0)
        self.assertEqual(_gate_index({'m1': {'enabled': '1', 'mix': '0'}}), 0)
        self.assertEqual(_gate_index({}), 1)                       # no row = on
        self.assertEqual(_gate_index(None), 1)                     # no slots table = on

    def test_gate_needed(self):
        self.assertTrue(NS['gate_needed']('out_sel', '0 if parent().par.Amount.eval() <= 0 else 1'))
        self.assertTrue(NS['gate_needed']('fx', ''))
        self.assertFalse(NS['gate_needed']('out_sel', "0 if parent(2).op('slots') is not None else 1"))

    def test_stages(self):
        st = NS['gate_stages']([{'ops': ['in1']}, {'ops': ['out_sel', 'out1']}])
        self.assertEqual(st[1]['ops'], ['out_sel', 'slot_gate', 'out1'])
        self.assertEqual(NS['gate_stages'](st)[1]['ops'], ['out_sel', 'slot_gate', 'out1'])   # idempotent
        self.assertEqual(NS['gate_stages']([{'ops': ['fx']}])[0]['ops'], ['fx', 'slot_gate'])

    def _ns(self):
        ns = {'switchTOP': switchTOP, 'ParMode': ParMode}
        exec(RACK_SRC, ns)                                        # rack functions bound to the fake TD globals
        ns['_sd'] = lambda o: None
        return ns

    def test_wiring_idempotent(self):
        ns = self._ns()
        m = _Mod()
        st = ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])
        g = m.op('slot_gate')
        self.assertEqual((_src_of(g, 0), _src_of(g, 1), _src_of(m.op('out1'))), ('in1', 'fx', 'slot_gate'))
        self.assertEqual(g.par.index.expr, NS['SLOT_GATE_E'])
        self.assertEqual(st[0]['ops'], ['fx', 'slot_gate', 'out1'])
        m.op('out1').inputConnectors[0].connect(m.op('fx'))      # a module rebuild re-wires out1 to its source
        ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])
        self.assertEqual((_src_of(g, 0), _src_of(g, 1), _src_of(m.op('out1'))), ('in1', 'fx', 'slot_gate'))
        ns['_slot_gate'](m, [{'ops': ['fx', 'out1']}])           # already gated: unchanged
        self.assertEqual(_src_of(m.op('out1')), 'slot_gate')

    def test_slot_aware_out_sel_left_alone(self):              # GEN_points OUT_SEL_E
        ns = self._ns()
        m = _Mod('out_sel', "0 if parent().par.Amount.eval() <= 0 or (parent(2).op('slots') is not None) else 1")
        ns['_slot_gate'](m, [{'ops': ['out_sel', 'out1']}])
        self.assertIsNone(m.op('slot_gate'))
        self.assertEqual(_src_of(m.op('out1')), 'out_sel')


def _family_src(name):
    with open(os.path.join(BDIR, name + '.py')) as fh:
        return fh.read()


def _instance_body(src):
    i = src.find('\ndef _instance(')
    if i < 0:
        return None
    j = src.find('\ndef ', i + 1)
    return src[i:j if j > 0 else len(src)]


class Families(unittest.TestCase):
    """Every rack built on fx_glitch.py gets the gate: it execs the rack (directly or via fx_stylise / gen_sim) and
    uses the rack's _instance (none of its own)."""
    FAMILIES = {'fx_analog': 'fx_glitch.py', 'fx_stylise': 'fx_glitch.py', 'fx_glass': 'fx_stylise.py',
                'fx_scope': 'fx_glitch.py', 'fx_synth': 'fx_glitch.py', 'fx_track': 'fx_glitch.py',
                'gen_sim': 'fx_glitch.py', 'gen_interactive': 'gen_sim.py'}

    def test_family_uses_gated_instance(self):
        for fam, rack in self.FAMILIES.items():
            src = _family_src(fam)
            self.assertIn("os.path.join(HERE, '%s')" % rack, src, fam)
            body = _instance_body(src)
            self.assertTrue(body is None or '_slot_gate(' in body or '_rack_instance(' in body, fam)

    def test_rack_instance_gates(self):
        self.assertIn('stages = _slot_gate(m, M[\'build\'](m, H))', _instance_body(RACK_SRC))


BDIR = os.path.join(os.path.dirname(HERE), 'builders')
with open(os.path.join(BDIR, 'fx_glitch.py')) as _fh:
    RACK_SRC = _fh.read()

if __name__ == '__main__':
    unittest.main()
