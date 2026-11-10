# fx_analog builder - FX_analog: the FX_glitch rack (builders/fx_glitch.py: slots table, Cross + Switch per slot,
# Panic, add/remove/rewire) reused as is, with its own COMP name, its own module files builders/fx_analog_<X>.py
# (template: docs/builds/fx_glitch.md) and 'ntsc1' as the first row. No copy of the rack code (no-bloat rule).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_analog.py').read(), ns)
#   ns['build']('/project1/lab')                          # rack + 'ntsc1' on first build; idempotent
#   ns['add']('/project1/lab/FX_analog', 'ntsc')           # ntsc2, wired last
#   ns['remove']('/project1/lab/FX_analog', 'ntsc2'); ns['rewire'](c) after editing order in `slots`
# ASCII only.
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
with open(os.path.join(HERE, 'fx_glitch.py')) as _fh:
    exec(_fh.read(), globals())                          # the rack functions; they look NAME / _module up at call time

_rack_compute = _compute


def _compute(m, name, text, ins, res=None, fmt='useinput'):
    """The rack's compute pass, but a GLSL Multi TOP when a pass has > 3 inputs: GLSL TOP has 3 input connectors
    from Python on 31550 (T-84; vhs fx = in1, sig, prev_src, stamp); GLSL Multi has compute mode + any count."""
    if len(ins) <= 3:
        return _rack_compute(m, name, text, ins, res, fmt)
    g = m.op(name)
    if g is not None and g.OPType != 'glslmultiTOP':
        d = m.op(name + '_compute')
        if d is not None:
            d.dock = None                                 # keep the DAT: safe_destroy also kills docked ops (T-28)
        _sd(g)                                            # renames it out of the way at once (T-70)
    g = _mk(m, glslmultiTOP, name)
    for t in list(g.docked):                              # a new GLSL op docks its own template '<name>_compute1'
        if t.name == name + '_compute1' and m.op(name + '_compute') is not None:
            _sd(t)
    d = m.op(name + '_compute')
    if d is None:
        d = _mk(m, textDAT, name + '_compute')
    d.dock = g
    d.text = text
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    if res:
        g.par.resolutionw, g.par.resolutionh = res
    else:
        _expr(g.par.resolutionw, 'me.inputs[0].width')
        _expr(g.par.resolutionh, 'me.inputs[0].height')
    g.par.format = fmt
    for i, src in enumerate(ins):
        g.inputConnectors[i].connect(src)
    return g


H = dict(H, compute=_compute)
NAME = 'FX_analog'
FIRST = ('ntsc1', 'ntsc')
_rack_build = build
_rack_add = add


def _comment(c, name, module):
    m = c.op(name)
    if m is not None:
        m.comment = 'FX_analog module %s (%s). Pars on its custom pages; pulse Opencontrols for the zkit panel.' % (
            name, module)


def module_file(module):
    return os.path.join(HERE, 'fx_analog_%s.py' % module)


def _module(module):
    ns = dict(globals())
    with open(module_file(module)) as fh:
        exec(fh.read(), ns)
    return ns


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    if c.op('slots') is None:                             # first row = ntsc1 (the rack would seed smear1)
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        t.appendRow([FIRST[0], FIRST[1], 1, 1, 1])
    res = _rack_build(parent_path, panel)
    c.comment = ('FX_analog: analog signal rack (CRT/NTSC/VHS modules). In: in1 TOP. Out: out1 TOP. Slots from '
                 '`slots` (builders/fx_analog.py add/remove/rewire). Panic = instant passthrough.')
    for r in _rows(c):
        _comment(c, r['name'], r['module'])
    return res


def add(comp_path, module, name=None, order=None, enabled=1, mix=1, panel=True):
    res = _rack_add(comp_path, module, name=name, order=order, enabled=enabled, mix=mix, panel=panel)
    _comment(op(comp_path), res['added'], module)
    return res
