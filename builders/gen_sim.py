# gen_sim builder - GEN_sim: simulation generators (state textures stepped in compute) in the FX_glitch rack.
# The rack (builders/fx_glitch.py: slots table, Cross + Switch per slot, Panic, add/remove/rewire) is reused as is,
# like builders/fx_analog.py does, with a GENERATOR variant on top: no input is needed (img_src = auto: in1 when wired,
# else a black `bg` at Resw x Resh; or black / live / test clip), every module draws OVER its slot input (Blend on
# its Colour page) and can also use that input (seeds, inject, stained glass, refraction, LIC field). Module 'X' lives
# in builders/gen_sim_X.py (template: docs/builds/fx_glitch.md "Module template" + docs/builds/gen_sim.md), shaders in
# builders/glsl/gen_sim_*.glsl (gen_sim_common.glsl prefixed to each), maths in builders/gen_sim_logic.py.
# Shared here because every GEN_sim module uses it today (no-bloat rule): the Colour page (palette + blend), the GLSL
# loader, the compute-pass / state / clock helpers, and the Pulse -> Resetcount exec.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/gen_sim.py').read(), ns)
#   ns['build']('/project1/lab')                          # rack + 'ca1' on first build; idempotent
#   ns['add']('/project1/lab/GEN_sim', 'voronoi')          # voronoi1, wired last (zkit panel + presets)
#   ns['remove']('/project1/lab/GEN_sim', 'voronoi1'); ns['rewire'](c) after editing order in `slots`
# T-70 safe (_sd = safe_destroy); no functions in op storage (T-67). ASCII only.
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
with open(os.path.join(HERE, 'fx_glitch.py')) as _fh:
    exec(_fh.read(), globals())                          # the rack functions; they look NAME / _module up at call time

NAME = 'GEN_sim'
FIRST = ('ca1', 'ca')
MODULES = ['ca', 'voronoi', 'dla', 'blobs', 'lic', 'ripple', 'lavalamp', 'sand']
GLSL_DIR = os.path.join(HERE, 'glsl')
INPUTS = ['auto', 'black', 'live', 'test']
P = "parent().par.{}.eval()"
PI = "parent().par.{}.menuIndex"

# Colour page: every module's look pass reads it (uLook / uCa / uCb in gen_sim_common.glsl)
PALETTES = ['ab', 'fire', 'ice', 'neon', 'rainbow', 'mono', 'input']
PALETTE_LABELS = ['Colour A -> B', 'Fire', 'Ice', 'Neon', 'Rainbow', 'Mono white', 'Input (module)']
BLENDS = ['replace', 'over', 'add', 'screen', 'multiply', 'lighten', 'difference', 'alpha']
BLEND_LABELS = ['Replace', 'Over (alpha)', 'Add', 'Screen', 'Multiply', 'Lighten', 'Difference',
                'Alpha out (premultiplied)']


def colour_page(palette='ab', blend='replace', ca=(0.05, 0.1, 0.35), cb=(1.0, 0.85, 0.4)):
    return ('Colour', [
        ('Palette', 'Menu', palette, {'names': PALETTES, 'labels': PALETTE_LABELS}),
        ('Palshift', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Palette shift'}),
        ('Blend', 'Menu', blend, {'names': BLENDS, 'labels': BLEND_LABELS}),
        ('Colora', 'RGB', ca, {'label': 'Colour A'}),
        ('Colorb', 'RGB', cb, {'label': 'Colour B'}),
    ])


LOOK_UNIFORMS = [('uLook', [PI.format('Blend'), PI.format('Palette'), P.format('Palshift'), P.format('Amount')]),
                 ('uCa', [P.format('Colorar'), P.format('Colorag'), P.format('Colorab'), '0']),
                 ('uCb', [P.format('Colorbr'), P.format('Colorbg'), P.format('Colorbb'), '0'])]
STATE_PAGE = ('State', [('Resetcount', 'Int', 0, {'min': 0, 'max': 100, 'label': 'Reset count (Reset pulse +1)'})])
EPOCH = "float(int(parent().par.Resetcount.eval()) % 4096 + 1)"   # state alpha; a change re-seeds (never 0 = blank)
IN_W, IN_H = "op('in1').width", "op('in1').height"


def logic():
    """builders/gen_sim_logic.py as a namespace (rule / Lenia expressions, menus; numpy only inside its references)."""
    ns = {}
    with open(os.path.join(HERE, 'gen_sim_logic.py')) as fh:
        exec(fh.read(), ns)
    return ns


def glsl_text(*names):
    """gen_sim_common.glsl + the named pass files (no extension), as one compute shader text."""
    parts = []
    for n in ('gen_sim_common',) + tuple(names):
        with open(os.path.join(GLSL_DIR, n + '.glsl')) as fh:
            parts.append(fh.read())
    return '\n'.join(parts)


def scaled(axis_expr, factor_expr):
    """Expression: max(1, int(axis * factor + 0.5))."""
    return "max(1, int(%s * (%s) + 0.5))" % (axis_expr, factor_expr)


# ------------------------------------------------------------------ TD side (module helpers, passed in H)
def _pass(m, name, text, ins, w, h, fmt='rgba32float', U=(), npasses=None, dispatch=None, extend='hold',
          filt=None, readwrite=False):
    """Compute GLSL TOP `name` + docked `<name>_compute` (text), size from expressions w/h, inputs in order (<= 3,
    T-84), vec uniforms U, npasses expression, manual dispatch (x, y) expressions, inputextenduv, filter, in-place."""
    g = _mk(m, glslTOP, name)
    for t in list(g.docked):                              # a new GLSL op docks its own templates (T-115 (5))
        if t.name != name + '_compute' and t.name.startswith(name + '_'):
            _sd(t)
    d = m.op(name + '_compute')
    if d is None:
        d = _mk(m, textDAT, name + '_compute')
    d.dock = g
    if d.text != text:
        d.text = text
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w)
    _expr(g.par.resolutionh, h)
    g.par.format = fmt
    g.par.inputextenduv = extend
    if filt:
        g.par.inputfiltertype = filt
    if readwrite:
        g.par.outputaccess = 'readwrite'
        g.par.clearoutputs = False
    if npasses:
        _expr(g.par.npasses, npasses)
    if dispatch:
        g.par.autodispatchsize = False
        _expr(g.par.dispatchsizex, dispatch[0])
        _expr(g.par.dispatchsizey, dispatch[1])
        g.par.dispatchsizez = 1
    for i, src in enumerate(ins):
        g.inputConnectors[i].connect(src)
    U = list(U)                                           # common declares the look uniforms: a pass without them
    names = [u[0] for u in U]                             # warns "Uniform 'uLook' is not assigned" (live, 31550)
    U += [(n, ['0', '0', '0', '0']) for n in ('uLook', 'uCa', 'uCb') if n not in names]
    _uniforms(g, U)
    return g


def _state(m, name, target, w, h, fmt='rgba32float'):
    """Feedback TOP `name` holding `target`'s last output; its input is a blank Constant at the same size and format
    (alpha 0 = no epoch, so the state shader seeds on the first cook)."""
    b = _mk(m, constantTOP, name + '_blank')
    b.par.colorr = b.par.colorg = b.par.colorb = 0
    b.par.alpha = 0
    b.par.outputresolution = 'custom'
    _expr(b.par.resolutionw, w)
    _expr(b.par.resolutionh, h)
    b.par.format = fmt
    b.comment = 'Blank state (alpha 0 = no epoch -> the state pass seeds). Static: cooks once per size change.'
    fb = _mk(m, feedbackTOP, name)
    fb.inputConnectors[0].connect(b)
    fb.par.top = target
    fb.comment = 'Last frame of %s (state).' % target
    return fb


def _clock(m):
    """1x1 module clock (gen_sim_clock.glsl): x = integrated time (dt x Speed)."""
    return _pass(m, 'clock', glsl_text('gen_sim_clock'), [], '1', '1', 'rgba32float',
                 [('uClk', ['absTime.seconds', P.format('Speed'), '0', '0'])], readwrite=True)


PULSE_EXEC = """# GEN_sim module pulses: Reset -> Resetcount + 1 (the state passes compare it with the epoch, re-seed).
# A value change of a RESEED par does the same (new seed / family / shape -> a fresh start).
RESEED = %r

def onPulse(par):
\tif par.name == 'Reset':
\t\tpar.owner.par.Resetcount = int(par.owner.par.Resetcount.eval()) + 1
\treturn

def onValueChange(par, prev):
\tif par.name in RESEED:
\t\tpar.owner.par.Resetcount = int(par.owner.par.Resetcount.eval()) + 1
\treturn
"""


def _pulses(m, reseed=()):
    pe = _mk(m, parameterexecuteDAT, 'pulses')
    txt = PULSE_EXEC % list(reseed)
    if pe.text != txt:
        pe.text = txt
        pe.par.active = False                              # T-97: toggle after a text rewrite
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = '*'
    pe.par.valuechange = bool(reseed)
    pe.par.onpulse = True
    pe.par.active = True
    pe.comment = 'Reset pulse (and changes of %s) -> Resetcount + 1 = re-seed.' % (' '.join(reseed) or '-')
    return pe


def _out_sel(m, look):
    """Amount 0 = in1 straight out (exact, the module does not cook); else the look pass."""
    sel = _mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(m.op('in1'))
    sel.inputConnectors[1].connect(look)
    _expr(sel.par.index, "0 if parent().par.Amount.eval() <= 0 else 1")
    sel.comment = 'Amount 0 = the slot input untouched (nothing cooks).'
    out1 = _mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return sel


# ------------------------------------------------------------------ lane A (27 Oct): shared palette, hits, full presets
# Used by the lane A modules (ripple, lavalamp, sand); the 5 first modules' shader text and pages are unchanged.
# Shared palette (W1-B, docs/builds/palette_convention.md): Colour page Palette gains 'shared' (index 7 -> pxPal(t +
# Palshift)); a Palette page feeds the module's `pal` Script CHOP (uPal[16] on the look pass) + uPalCtl.
PALMAP_FILE = os.path.join(HERE, 'palette_map_logic.py')
PALGLSL_FILE = os.path.join(GLSL_DIR, 'px_palette.glsl')
PAL_SRC = ['custom', 'neon_green', 'cyan_magenta', 'neon_trio', 'acid', 'magenta_inv', 'fire', 'px_ramp', 'rainbow',
           'pico8', 'sweetie16', 'endesga32', 'resurrect64', 'gameboy', 'cga0hi', 'solarized']
PAL_HOOK = '\tif (m == 5) return vec3(1.0);'              # gs_pal's 'mono' line; 'shared' (7) goes after it


def colour_page_pal(palette='shared', blend='replace', ca=(0.05, 0.1, 0.35), cb=(1.0, 0.85, 0.4)):
    pg = colour_page(palette if palette in PALETTES else 'ab', blend, ca, cb)
    pars = [(('Palette', 'Menu', palette, {'names': PALETTES + ['shared'],
                                            'labels': PALETTE_LABELS + ['Shared palette (Palette page)']})
             if q[0] == 'Palette' else q) for q in pg[1]]
    return ('Colour', pars)


def palette_page(source='rainbow', mode='gradient'):
    return ('Palette', [
        ('Palsource', 'Menu', source, {'names': PAL_SRC, 'labels': PAL_SRC}),
        ('Palcustom', 'Str', 'ff2a6d 05d9e8 f9c80e', {'label': 'Custom stops (hex or hex@pos, spaces)'}),
        ('Palmode', 'Menu', mode, {'names': ['gradient', 'steps', 'cycle'],
                                   'labels': ['Gradient (positioned stops)', 'Steps (equal bands)',
                                              'Cycle (wraps, last -> first)']}),
        ('Palinterp', 'Menu', 'oklab', {'names': ['rgb', 'oklab'], 'labels': ['RGB', 'OKLab']}),
        ('Palreverse', 'Toggle', False, {'label': 'Reverse'}),
        ('Palcycle', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Palette cycle /s (shift drive)'}),
    ])


def pal_glsl(text):
    """A pass text with the shared palette: px_palette.glsl first, gs_pal index 7 = pxPal."""
    with open(PALGLSL_FILE) as fh:
        inc = fh.read()
    assert PAL_HOOK in text
    return inc + '\n' + text.replace(PAL_HOOK, PAL_HOOK + '\n\tif (m == 7) return pxPal(u);')


PAL_CTL = ("float(len(op('pal_callbacks').module.stops(parent())))", "absTime.seconds * parent().par.Palcycle.eval()",
           PI.format('Palmode'), PI.format('Palinterp'))
PAL_CB = """# pal_callbacks: GEN_sim shared palette (W1-B, docs/builds/palette_convention.md). Palette page ->
# palette_map_logic.palette_stops (palmap) -> pal: 16 samples r g b pos = uPal[16]. Recooks on palette edits only.
def stops(c):
\tPm = op('palmap').module
\tsrc = c.par.Palsource.eval()
\trows = None
\tif src == 'custom':
\t\trows = [t.split('@') for t in str(c.par.Palcustom.eval()).replace(',', ' ').split()]
\treturn Pm.palette_stops({'source': src, 'mode': c.par.Palmode.eval(), 'reverse': bool(c.par.Palreverse.eval())},
\t\trows, [])

def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tPm = op('palmap').module
\tPm.cook_chop(scriptOp, Pm.pal_rows(stops(scriptOp.parent())))
\treturn
"""


def _palette(m, g):
    """palmap + pal_callbacks + pal (Script CHOP) -> g's Arrays block uPal. uPalCtl comes with g's uniforms."""
    pm = m.op('palmap') or _mk(m, textDAT, 'palmap')
    with open(PALMAP_FILE) as fh:
        txt = fh.read()
    if pm.text != txt:
        pm.text = txt
    cb = m.op('pal_callbacks') or _mk(m, textDAT, 'pal_callbacks')
    if cb.text != PAL_CB:
        cb.text = PAL_CB
    sc = _mk(m, scriptCHOP, 'pal')
    sc.par.callbacks = cb
    sc.comment = 'uPal: 16 stops r g b pos from the Palette page (cooks on palette edits only).'
    g.seq.array.numBlocks = max(int(g.seq.array.numBlocks), 1)
    g.par.array0name = 'uPal'
    g.par.array0type = 'vec4'
    g.par.array0chop = 'pal'
    g.par.array0arraytype = 'uniformarray'
    return ['palmap', 'pal_callbacks', 'pal']


HIT_CODE = """
def _hit(c):
    c.par.Hitn = int(c.par.Hitn.eval()) + 1          # the step pass injects every hit it has not applied yet
"""
HIT_PEXEC = "# hits: Hit pulse -> Hitn + 1 (one drop / burst per hit, no limiter)." + HIT_CODE + """
def onPulse(par):
    if par.name == 'Hit':
        _hit(par.owner)
    return
"""
HIT_CHOPEXEC = "# hit_chopexec: Hitchop channel Hitchan rising edge (e.g. AC_audio/out_ctl kick) -> a hit." + HIT_CODE + """
def onOffToOn(channel, sampleIndex, val, prev):
    c = parent()
    if channel.name == str(c.par.Hitchan.eval()):
        _hit(c)
    return
"""


def _hits(m):
    """Hit pulse + Hitchop rising edge -> Hitn + 1 (State page). The state pass applies hits Hitn_applied+1 .. Hitn."""
    pe = m.op('hits') or _mk(m, parameterexecuteDAT, 'hits')
    if pe.text != HIT_PEXEC:
        pe.text = HIT_PEXEC
        pe.par.active = False
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Hit'
    pe.par.onpulse = True
    pe.par.valuechange = False
    pe.par.active = True
    pe.comment = 'Hit pulse -> Hitn + 1.'
    ce = m.op('hit_chopexec') or _mk(m, chopexecuteDAT, 'hit_chopexec')
    if ce.text != HIT_CHOPEXEC:
        ce.text = HIT_CHOPEXEC
    _expr(ce.par.chop, "parent().par.Hitchop.eval().path if parent().par.Hitchop.eval() is not None else ''")
    _expr(ce.par.active, "parent().par.Hitchop.eval() is not None")
    ce.par.offtoon = True
    ce.par.valuechange = False
    ce.comment = 'Hitchop / Hitchan rising edge -> Hitn + 1.'
    return ['hits', 'hit_chopexec']


def page_values(pages):
    """{par: default} of pages (RGB split r g b, menus as index): the base of a full-state preset."""
    d = {}
    for _pg, ps in pages:
        for n, s, dv, o in ps:
            if s == 'RGB':
                d.update((n + ch, v) for ch, v in zip('rgb', dv))
            elif s == 'Menu':
                d[n] = o['names'].index(dv)
            elif s in ('Float', 'Int', 'Toggle'):
                d[n] = dv
    return d


def full_presets(pages, presets, skip=('Resetcount', 'Hitn')):
    """Presets that set the FULL state (page defaults + the preset's values; menus by name or index), so a recall
    never inherits pars from the preset before (T-124 (1))."""
    base = dict((k, v) for k, v in page_values(pages).items() if k not in skip)
    menus = dict((n, o['names']) for _pg, ps in pages for n, s, _d, o in ps if s == 'Menu')
    out = []
    for slot, name, vals in presets:
        d = dict(base)
        for k, v in vals.items():
            d[k] = menus[k].index(v) if k in menus and isinstance(v, str) else v
        out.append((slot, name, d))
    return out


def preset(inst_path, slot):
    """Apply module preset `slot` straight to the instance pars (the values a zkit Recall sets)."""
    m = op(inst_path)
    M = _module(m.parent().op('slots')[m.name, 'module'].val)
    vals = next(v for s, _n, v in M['PRESETS'] if s == slot)
    for k, v in vals.items():
        p = getattr(m.par, k, None)
        if p is None:
            continue
        if p.isMenu:
            p.menuIndex = int(v)
        else:
            p.val = v
    return {'preset': slot, 'set': len(vals)}


H = dict(H, glsl=glsl_text, pas=_pass, state=_state, clock=_clock, pulses=_pulses, out_sel=_out_sel,
         look_uniforms=LOOK_UNIFORMS, epoch=EPOCH, in_w=IN_W, in_h=IN_H, scaled=scaled, palette=_palette,
         hits=_hits, pal_glsl=pal_glsl)

# ------------------------------------------------------------------ rack overrides (generator variant)
_rack_pars = _pars
_rack_build = build
_rack_add = add


def _pars(c, pages):
    """The rack's _pars + 'RGB' pars (three channels, defaults per channel). Order on the page is kept."""
    for page_name, pars in pages:
        run = []
        for spec in pars:
            if spec[1] != 'RGB':
                run.append(spec)
                continue
            if run:
                _rack_pars(c, [(page_name, run)])
                run = []
            name, _s, default, o = spec
            if getattr(c.par, name + 'r', None) is not None:
                continue
            page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
            for p, v in zip(page.appendRGB(name, label=o.get('label', name)), default):
                p.default = v
                p.val = v
        if run:
            _rack_pars(c, [(page_name, run)])


def module_file(module):
    return os.path.join(HERE, 'gen_sim_%s.py' % module)


def _module(module):
    ns = dict(globals())
    with open(module_file(module)) as fh:
        exec(fh.read(), ns)
    return ns


def _comment(c, name, module):
    m = c.op(name)
    if m is not None:
        m.comment = ('GEN_sim module %s (%s): draws over its slot input (Colour page Blend). Pars on its custom pages; '
                     'pulse Opencontrols for the zkit panel, Reset to re-seed.' % (name, module))


def _layout(c):
    names = plan_chain(_rows(c))
    chain = []
    for n in names:
        chain += [n, n + '_mix', n + '_slot']
    stages = [
        {'title': 'Rack', 'role': 'control', 'ops': ['slots'],
         'body': 'slots: name module enabled order mix. enabled/mix live; add/remove/order = builder rewire.'},
        {'title': '1 Background', 'role': 'input', 'ops': ['bg', 'in1', 'test_clip', 'img_src'],
         'body': 'Input: auto (in1 if wired, else black bg) / black / live (in1) / test clip.'},
        {'title': '2 Generators', 'role': 'process', 'ops': [n for n in chain if c.op(n) is not None],
         'body': 'Per slot: module COMP (draws over its input) -> _mix (Cross) -> _slot (Switch 0 bypass/1/2 mix).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['panic', 'out1'], 'body': 'Panic = the background straight out.'},
    ]
    for s in stages:                                     # the rack's build lays out before `bg` exists (live, 31550)
        s['ops'] = [n for n in s['ops'] if c.op(n) is not None]
    stages = [s for s in stages if s['ops']]
    return op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')


IMG_INDEX = ("(lambda m, w: 0 if m == 'black' else (1 if m == 'live' or (m == 'auto' and w) else "
             "(2 if m == 'test' else 0)))(parent().par.Input.eval(), any(len(cn.connections) for cn in "
             "parent().inputConnectors if cn.inOP is not None and cn.inOP.name == 'in1'))")


def build(parent_path='/project1/lab', panel=True):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    _pars(c, [('Rack', [
        ('Panic', 'Toggle', False, {'label': 'Panic (background only)'}),
        ('Input', 'Menu', 'auto', {'names': INPUTS, 'labels': ['Auto (in1 if wired, else black)', 'Black',
                                                                'Live (in1)', 'Test clip']}),
        ('Resw', 'Int', 1080, {'min': 16, 'max': 3840, 'label': 'Width (black bg)'}),
        ('Resh', 'Int', 1920, {'min': 16, 'max': 3840, 'label': 'Height (black bg)'}),
    ])])
    if c.op('slots') is None:                             # first row = ca1 (the rack would seed smear1)
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        t.appendRow([FIRST[0], FIRST[1], 1, 1, 1])
    res = _rack_build(parent_path, panel)
    bg = _mk(c, constantTOP, 'bg')
    bg.par.colorr = bg.par.colorg = bg.par.colorb = 0
    bg.par.alpha = 1
    bg.par.outputresolution = 'custom'
    _expr(bg.par.resolutionw, "parent().par.Resw.eval()")
    _expr(bg.par.resolutionh, "parent().par.Resh.eval()")
    bg.par.format = 'rgba8fixed'
    bg.comment = 'Black background at Resw x Resh (static: cooks once).'
    img = c.op('img_src')                                 # generator variant: 0 bg, 1 in1, 2 test clip
    for i, src in enumerate((bg, c.op('in1'), c.op('test_clip'))):
        cn = img.inputConnectors[i].connections
        if not cn or cn[0].owner != src:
            img.inputConnectors[i].connect(src)
    _expr(img.par.index, IMG_INDEX)
    img.comment = 'Background for the first slot: black bg / in1 / test clip (Input on the Rack page).'
    c.op('panic').comment = 'Panic: 1 = the background straight to out1 (same frame; slots stop cooking).'
    c.comment = ('GEN_sim: simulation generators (CA, Voronoi/JFA, DLA growth, blobs, LIC). In: in1 TOP (optional '
                 'background / seed). Out: out1 TOP. Slots from `slots` (builders/gen_sim.py add/remove/rewire). '
                 'Panic = background only.')
    for r in _rows(c):
        _comment(c, r['name'], r['module'])
    res['layout'] = str(_layout(c))[:300]
    return res


def add(comp_path, module, name=None, order=None, enabled=1, mix=1, panel=True):
    res = _rack_add(comp_path, module, name=name, order=order, enabled=enabled, mix=mix, panel=panel)
    _comment(op(comp_path), res['added'], module)
    return res
