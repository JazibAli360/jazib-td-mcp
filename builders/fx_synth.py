# fx_synth builder - FX_synth: the video-synth rack. The FX_glitch rack (builders/fx_glitch.py: slots table, Cross +
# Switch per slot, Panic, add/remove/rewire) reused as is, the way builders/fx_analog.py does it: own COMP name, own
# module files builders/fx_synth_<X>.py (template: docs/builds/fx_glitch.md; FX_synth doc: docs/builds/fx_synth.md),
# shaders in builders/glsl/fx_synth_*.glsl, 'colorize1' as the first row. No copy of the rack code (no-bloat rule).
# Modules: colorize, bands, keyer, ruttetra, scanimate, vfeedback, modulate (SX-12 Hydra bank, lane C 27 Oct).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_synth.py').read(), ns)
#   ns['build']('/project1/lab')                          # rack + 'colorize1' on first build; idempotent
#   ns['add']('/project1/lab/FX_synth', 'ruttetra')        # ruttetra1, wired last
#   ns['remove']('/project1/lab/FX_synth', 'ruttetra1'); ns['rewire'](c) after editing order in `slots`
# ASCII only.
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
with open(os.path.join(HERE, 'fx_glitch.py')) as _fh:
    exec(_fh.read(), globals())                          # the rack functions; they look NAME / _module up at call time

NAME = 'FX_synth'
FIRST = ('colorize1', 'colorize')
MODULES = ['colorize', 'bands', 'keyer', 'ruttetra', 'scanimate', 'vfeedback', 'modulate']
_rack_build = build
_rack_add = add


def _comment(c, name, module):
    m = c.op(name)
    if m is not None:
        m.comment = 'FX_synth module %s (%s). Pars on its custom pages; pulse Opencontrols for the zkit panel.' % (
            name, module)


def module_file(module):
    return os.path.join(HERE, 'fx_synth_%s.py' % module)


def _module(module):
    ns = dict(globals())
    with open(module_file(module)) as fh:
        exec(fh.read(), ns)
    return ns


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    if c.op('slots') is None:                             # first row = colorize1 (the rack would seed smear1)
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        t.appendRow([FIRST[0], FIRST[1], 1, 1, 1])
    res = _rack_build(parent_path, panel)
    c.comment = ('FX_synth: video-synth rack (colorize, bands, keyer, ruttetra, scanimate, vfeedback, modulate). In: in1 TOP. '
                 'Out: out1 TOP. Slots from `slots` (builders/fx_synth.py add/remove/rewire). Panic = passthrough.')
    for r in _rows(c):
        _comment(c, r['name'], r['module'])
    return res


def add(comp_path, module, name=None, order=None, enabled=1, mix=1, panel=True):
    res = _rack_add(comp_path, module, name=name, order=order, enabled=enabled, mix=mix, panel=panel)
    _comment(op(comp_path), res['added'], module)
    return res
