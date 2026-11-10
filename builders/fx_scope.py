# fx_scope builder - FX_scope: scopes, vector displays and camera HUD. The FX_glitch rack (builders/fx_glitch.py:
# slots table, Cross + Switch per slot, Panic, add/remove/rewire) reused as is, the way builders/fx_analog.py does:
# own COMP name, own module files builders/fx_scope_<X>.py (template: docs/builds/fx_glitch.md) and 'xy1' as the
# first row. No copy of the rack code (no-bloat rule). Modules: xy, vector, lissajous (shared beam engine
# builders/fx_scope_beam.py), scopes, hud. Doc: docs/builds/fx_scope.md.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_scope.py').read(), ns)
#   ns['build']('/project1/lab')                          # rack + 'xy1' on first build; idempotent
#   ns['add']('/project1/lab/FX_scope', 'scopes')          # scopes1, wired last
#   ns['remove']('/project1/lab/FX_scope', 'scopes1'); ns['rewire'](c) after editing order in `slots`
# ASCII only.
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
with open(os.path.join(HERE, 'fx_glitch.py')) as _fh:
    exec(_fh.read(), globals())                          # the rack functions; they look NAME / _module up at call time

NAME = 'FX_scope'
FIRST = ('xy1', 'xy')
MODULES = ['xy', 'vector', 'lissajous', 'scopes', 'hud']
_rack_build = build
_rack_add = add


def _comment(c, name, module):
    m = c.op(name)
    if m is not None:
        m.comment = 'FX_scope module %s (%s). Pars on its custom pages; pulse Opencontrols for the zkit panel.' % (
            name, module)


def module_file(module):
    return os.path.join(HERE, 'fx_scope_%s.py' % module)


def _module(module):
    ns = dict(globals())
    with open(module_file(module)) as fh:
        exec(fh.read(), ns)
    return ns


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    if c.op('slots') is None:                             # first row = xy1 (the rack would seed smear1)
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        t.appendRow([FIRST[0], FIRST[1], 1, 1, 1])
    res = _rack_build(parent_path, panel)
    c.comment = ('FX_scope: scopes / vector displays / camera HUD rack (xy, vector, lissajous, scopes, hud). In: in1 '
                 'TOP. Out: out1 TOP. Slots from `slots` (builders/fx_scope.py add/remove/rewire). Panic = passthrough.')
    for r in _rows(c):
        _comment(c, r['name'], r['module'])
    res['missing'] = dict((r['name'], c.op(r['name']).fetch('fx_scope_missing', '')) for r in _rows(c)
                          if c.op(r['name']) is not None)
    return res


def add(comp_path, module, name=None, order=None, enabled=1, mix=1, panel=True):
    res = _rack_add(comp_path, module, name=name, order=order, enabled=enabled, mix=mix, panel=panel)
    _comment(op(comp_path), res['added'], module)
    m = op(comp_path).op(res['added'])
    res['missing'] = m.fetch('fx_scope_missing', '') if m is not None else ''
    return res
