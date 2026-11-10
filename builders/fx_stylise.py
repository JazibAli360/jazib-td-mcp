# fx_stylise builder - FX_stylise: the FX_glitch rack (builders/fx_glitch.py: slots table, Cross + Switch per slot,
# Panic, add/remove/rewire) reused as is (like fx_analog.py), with its own COMP name and module files
# builders/fx_stylise_<X>.py (template: docs/builds/fx_glitch.md "Module template"). Doc: docs/builds/fx_stylise.md.
# Rack additions, each used by 2+ modules (no-bloat rule): the Text DAT `palette_map_logic` (W1-B palette, read by the
# modules' `pal` Script CHOPs, builders/fx_stylise_pal.py), a multi-pass compute helper H['pas'] (npasses: JFA in
# outline / saber), H['glsl'] (read a shared shader file from builders/glsl/, read-only, e.g. gen_sim_vor_jfa.glsl).
# Rest state: every slot enabled 0 (the rack passes in1 through).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_stylise.py').read(), ns)
#   ns['build']('/project1/lab')                          # rack + 'outline1' (enabled 0) on first build; idempotent
#   ns['add']('/project1/lab/FX_stylise', 'boil', enabled=0)
#   ns['remove']('/project1/lab/FX_stylise', 'boil1'); ns['rewire'](c) after editing order in `slots`
# ASCII only.
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
with open(os.path.join(HERE, 'fx_glitch.py')) as _fh:
    exec(_fh.read(), globals())                          # the rack functions; they look NAME / _module up at call time

NAME = 'FX_stylise'
PREFIX = 'fx_stylise'
FIRST = ('outline1', 'outline')
LABEL = ('FX_stylise: image stylise rack (outline / boil / ink / saber / clean / watercolour / engrave / kuwahara). '
         'In: in1 TOP. Out: out1 TOP. Slots from `slots` (builders/fx_stylise.py add/remove/rewire). Panic = instant '
         'passthrough.')
_rack_build = build
_rack_add = add


def glsl_text(name):
    with open(os.path.join(HERE, 'glsl', name + '.glsl')) as fh:
        return fh.read()


def _pas(m, name, text, ins, w, h, fmt='rgba32float', npasses=None, extend='hold', filt=None):
    """Compute GLSL TOP with size expressions w / h and an optional npasses expression (pass n+1 reads pass n as
    input 0, T-91 (3)). <= 3 inputs (T-88)."""
    g = _compute(m, name, text, ins, None, fmt)
    for t in list(g.docked):                              # a new GLSL op docks its own templates (T-115 (5))
        if t.name != name + '_compute' and t.name.startswith(name + '_'):
            _sd(t)
    _expr(g.par.resolutionw, w)
    _expr(g.par.resolutionh, h)
    g.par.inputextenduv = extend
    if filt:
        g.par.inputfiltertype = filt
    if npasses:
        _expr(g.par.npasses, npasses)
    return g


H = dict(H, pas=_pas, glsl=glsl_text)


def _comment(c, name, module):
    m = c.op(name)
    if m is not None:
        m.comment = '%s module %s (%s). Pars on its custom pages; pulse Opencontrols for the zkit panel.' % (
            NAME, name, module)


def module_file(module):
    return os.path.join(HERE, '%s_%s.py' % (PREFIX, module))


def _module(module):
    ns = dict(globals())
    with open(module_file(module)) as fh:
        exec(fh.read(), ns)
    return ns


def _logic_dat(c):
    d = c.op('palette_map_logic')
    if d is None:
        d = _mk(c, textDAT, 'palette_map_logic')
    with open(os.path.join(HERE, 'palette_map_logic.py')) as fh:
        t = fh.read()
    if d.text != t:
        d.text = t
    d.comment = 'W1-B palette logic (copy of builders/palette_map_logic.py), read by the modules\' pal Script CHOPs.'
    return d


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    if c.op('slots') is None:                             # first row = the pilot, at rest (enabled 0)
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        t.appendRow([FIRST[0], FIRST[1], 0, 1, 1])
    _logic_dat(c)
    res = _rack_build(parent_path, panel)
    c.comment = LABEL
    for r in _rows(c):
        _comment(c, r['name'], r['module'])
    return res


def _layout(c):
    """The rack layout plus the palette logic DAT in the Rack stage."""
    names = plan_chain(_rows(c))
    chain = []
    for n in names:
        chain += [n, n + '_mix', n + '_slot']
    stages = [
        {'title': 'Rack', 'role': 'control', 'ops': ['slots', 'palette_map_logic'],
         'body': 'slots: name module enabled order mix (enabled/mix live). palette_map_logic: W1-B palette for modules.'},
        {'title': '1 Input', 'role': 'input', 'ops': ['in1', 'test_clip', 'img_src'],
         'body': 'in1 TOP or the stored webcam clip (Input: auto = in1 when wired).'},
        {'title': '2 Slots', 'role': 'process', 'ops': [n for n in chain if c.op(n) is not None],
         'body': 'Per slot: module COMP -> _mix (Cross) -> _slot (Switch 0 bypass / 1 module / 2 mix).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['panic', 'out1'], 'body': 'Panic = instant passthrough of the rack.'},
    ]
    stages = [s for s in stages if [n for n in s['ops'] if c.op(n) is not None]]
    for s in stages:
        s['ops'] = [n for n in s['ops'] if c.op(n) is not None]
    return op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')


def add(comp_path, module, name=None, order=None, enabled=0, mix=1, panel=True):
    c = op(comp_path)
    _logic_dat(c)
    res = _rack_add(comp_path, module, name=name, order=order, enabled=enabled, mix=mix, panel=panel)
    _comment(c, res['added'], module)
    return res
