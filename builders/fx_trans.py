# fx_trans builder - FX_trans (G-TRANS, FX0 row 69): a transition bank A -> B as ONE standalone COMP.
#   in1 = A (from), in2 = B (to), in3 = matte (luma wipe / displacement map; optional) -> out1.
#   Type: 25 gl-transitions (builders/glsl/fx_trans/*.glsl, MIT, vendored unchanged; SOURCES.md) + matte (luma-matte
#   wipe from any TOP) + tvoff (CRT power-off -> on, fx_analog_crt_logic.power_shape maths) + mosh (FX_glitch
#   moshcut's engine, built in the sub-COMP `mosh` with FX_glitch's own helpers: reused, not copied).
#   Progress slider / Go / Back / Cut, Drive manual | seconds | beats (BPM par or CHOP), Quantize to beat / bar, Ease,
#   Steps, Backstyle (rewind / forward), Randompool (random type per Go). Knobs K1..K10 follow the type (labels +
#   defaults set on a Type change). Ends are exact: raw 0 = A, raw 1 = B (out_sel; the shader is not cooked).
# Why standalone, not inside td_layer_mixer: docs/builds/fx_trans.md "Mixer or standalone" (no mixer change needed).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_trans.py').read(), ns)
#   ns['build']('/project1/lab')            # idempotent; panel=False skips the zkit panel
# T-70 safe (_sd = safe_destroy; pane never moved). Pure logic: builders/fx_trans_logic.py. ASCII only.
import json
import os
import sys

NAME = 'FX_trans'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
GLITCH_FILE = os.path.join(HERE, 'fx_glitch.py')
MOSHCUT_FILE = os.path.join(HERE, 'fx_glitch_moshcut.py')
TEST_A = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'
TEST_B = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/clips/tl_testsrc2_30fps_8s.mp4'
LOGIC = "op('fx_trans_logic').module"


def load_logic():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    ns = {'__name__': 'fx_trans_logic_build', '__file__': os.path.join(HERE, 'fx_trans_logic.py')}
    path = os.path.join(HERE, 'fx_trans_logic.py')
    with open(path) as fh:
        exec(compile(fh.read(), path, 'exec'), ns)
    return ns


def pages(Lg):
    """Custom pages (name, style, default, opts), same format as the racks' _pars."""
    T = Lg['TYPES']
    B = Lg['bank']()
    return [
        ('Trans', [
            ('Type', 'Menu', 'fade', {'names': T, 'labels': [B[t]['label'] for t in T]}),
            ('Progress', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Progress A -> B'}),
            ('Drive', 'Menu', 'manual', {'names': Lg['DRIVES'], 'labels': ['Progress slider', 'Go: Duration s',
                                                                           'Go: Beats at BPM']}),
            ('Go', 'Pulse', None, {'label': 'Go (to the other side)'}),
            ('Back', 'Pulse', None, {'label': 'Back to A'}),
            ('Cut', 'Pulse', None, {'label': 'Cut (instant)'}),
            ('Duration', 'Float', 2.0, {'min': 0.05, 'max': 10, 'label': 'Duration s'}),
            ('Beats', 'Float', 4.0, {'min': 0.25, 'max': 32, 'label': 'Beats'}),
            ('Ease', 'Menu', 'smooth', {'names': Lg['EASES'], 'labels': ['Linear', 'Smooth', 'In (cubic)',
                                                                       'Out (cubic)', 'In-out (cubic)', 'Expo',
                                                                       'Sine']}),
            ('Steps', 'Int', 0, {'min': 0, 'max': 32, 'label': 'Steps (0 = continuous)'}),
            ('Backstyle', 'Menu', 'rewind', {'names': Lg['BACKSTYLES'], 'labels': ['Rewind (reverse play)',
                                                                                  'Forward (B -> A plays forward)']}),
            ('Quantize', 'Menu', 'off', {'names': Lg['QUANT'], 'labels': ['Off', 'Next beat', 'Next bar (4)']}),
            ('Randompool', 'Str', '', {'label': 'Random type per Go (ids, or all)'}),
        ]),
        ('Knobs', [('K%d' % (k + 1), 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'K%d' % (k + 1)})
                   for k in range(Lg['NKNOBS'])] + [
            ('Keepknobs', 'Toggle', False, {'label': 'Keep knob values on Type change'}),
            ('Resetknobs', 'Pulse', None, {'label': 'Knobs to type defaults'}),
        ]),
        ('Tempo', [
            ('Bpm', 'Float', 120.0, {'min': 40, 'max': 200, 'label': 'BPM (when no CHOP)'}),
            ('Bpmchop', 'Str', '', {'label': 'BPM CHOP path (optional)'}),
            ('Bpmchan', 'Str', 'bpm', {'label': 'BPM channel'}),
            ('Phasechan', 'Str', '', {'label': 'Beat phase channel 0..1 (optional, Quantize)'}),
        ]),
        ('Input', [
            ('Asource', 'Menu', 'auto', {'names': ['auto', 'test'], 'labels': ['Auto (in1 if wired)', 'Test clip']}),
            ('Bsource', 'Menu', 'auto', {'names': ['auto', 'test'], 'labels': ['Auto (in2 if wired)', 'Test clip']}),
            ('Mattesource', 'Menu', 'auto', {'names': ['auto', 'ramp', 'radial', 'noise', 'top'],
                                             'labels': ['Auto (in3 if wired, else ramp)', 'Ramp (horizontal)',
                                                        'Radial ramp', 'Noise', 'TOP path (Mattetop)']}),
            ('Mattetop', 'Str', '', {'label': 'Matte TOP path'}),
            ('Resw', 'Int', 1080, {'min': 16, 'max': 3840, 'label': 'Width'}),
            ('Resh', 'Int', 1920, {'min': 16, 'max': 3840, 'label': 'Height'}),
            ('Fit', 'Menu', 'fitoutside', {'names': ['fill', 'fitinside', 'fitoutside'],
                                           'labels': ['Stretch', 'Fit inside', 'Fill (crop)']}),
            ('Outside', 'Menu', 'hold', {'names': Lg['OUTSIDE'], 'labels': ['Hold edge', 'Transparent']}),
            ('Compile', 'Menu', 'bank', {'names': ['selected', 'bank'],      # bank default: live b5, a new type's
                                         'labels': ['Selected type only (recompile on change)',    # first compile
                                                    'Whole bank (no recompile)']}),               # froze 0.5-0.75 s
        ]),
        ('State', [
            ('Gofrom', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Run from (internal)'}),
            ('Goto', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Run to (internal)'}),
            ('Gotime', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Run start absTime (internal)'}),
            ('Godur', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Run seconds (internal)'}),
            ('Goswap', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Run swaps A/B (internal)'}),
        ]),
    ]


PANEL_PAGES = ['Trans', 'Knobs', 'Tempo']


def presets(Lg):
    """Full states (T-124 (1)): every Trans par + the type's knob defaults."""
    T, D, E, Q = Lg['TYPES'], Lg['DRIVES'], Lg['EASES'], Lg['QUANT']

    def st(tid, drive='seconds', dur=2.0, beats=4.0, ease='smooth', quant='off', back='rewind', pool='', **kn):
        v = {'Type': T.index(tid), 'Drive': D.index(drive), 'Duration': dur, 'Beats': beats, 'Ease': E.index(ease),
             'Steps': 0, 'Quantize': Q.index(quant), 'Backstyle': Lg['BACKSTYLES'].index(back)}
        rows = Lg['knob_table'](tid)
        for k in range(Lg['NKNOBS']):
            v['K%d' % (k + 1)] = rows[k][1] if k < len(rows) else 0.0
        v.update(kn)
        return v
    return [
        (1, 'fade 2 s', st('fade')),
        (2, 'wipe 1 bar', st('wipe', 'beats', beats=4.0, ease='inout', quant='bar')),
        (3, 'cube 2 beats', st('cube', 'beats', beats=2.0, ease='inout', quant='beat')),
        (4, 'glitch hit', st('stripmosh', dur=0.6, ease='linear')),
        (5, 'tv off', st('tvoff', dur=1.2, ease='linear')),
        (6, 'datamosh cut', st('mosh', dur=2.0, ease='linear')),
        (7, 'film burn', st('filmburn', dur=2.5, ease='sine')),
        (8, 'matte wipe', st('matte', dur=1.5, ease='smooth')),
        (9, 'beat ripple 4 beats', st('beatripple', 'beats', beats=4.0, ease='linear', quant='beat')),
        # wave 3 (lane C2, 27 Oct): page flip (SX-33 / 7C-06), jigsaw (7C-29), static cut (SX-32)
        (10, 'page flip 2 beats', st('bookflip', 'beats', beats=2.0, ease='inout', quant='beat')),
        (11, 'jigsaw 1 bar', st('jigsaw', 'beats', beats=4.0, ease='linear', quant='bar')),
        (12, 'static cut', st('tvstatic', dur=0.5, ease='linear')),
    ]


PEXEC = """# FX_trans: pulses -> fx_trans_logic (Go / Back / Cut / Resetknobs); Type / Compile -> knobs + shader text.
def onPulse(par):
    L = op('fx_trans_logic').module
    c = par.owner
    now = absTime.seconds
    if par.name == 'Go':
        L.on_go(c, now)
    elif par.name == 'Back':
        L.on_go(c, now, target=0.0)
    elif par.name == 'Cut':
        L.on_cut(c, now)
    elif par.name == 'Resetknobs':
        L.load_sources(op('fx_trans_src').text)
        L.apply_type(c, keep=False)
    return

def onValueChange(par, prev):
    L = op('fx_trans_logic').module
    if par.name in ('Type', 'Compile'):
        L.load_sources(op('fx_trans_src').text)
        L.apply_type(par.owner, keep=bool(par.owner.par.Keepknobs.eval()) and par.name == 'Type')
    return
"""


# ------------------------------------------------------------------ TD side (same helpers as builders/fx_glitch.py)
def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = True
    return o


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _wire(dst, i, src):
    cn = dst.inputConnectors[i].connections
    if not cn or cn[0].owner != src:
        dst.inputConnectors[i].connect(src.outputConnectors[0] if getattr(src, 'isCOMP', False) else src)


def _pars(c, pgs):
    for page_name, pars in pgs:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']      # slider range only (no limits)
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            p.default = default
            p.val = default


def _auto_index(conn_name):
    """1 when the COMP input feeding inTOP `conn_name` is wired, else 0."""
    return ("1 if any(len(cn.connections) for cn in parent().inputConnectors if cn.inOP is not None and "
            "cn.inOP.name == '%s') else 0" % conn_name)


def _fit(c, name, src):
    f = _mk(c, fitTOP, name)
    _wire(f, 0, src)
    f.par.outputresolution = 'custom'
    _expr(f.par.resolutionw, 'parent().par.Resw.eval()')
    _expr(f.par.resolutionh, 'parent().par.Resh.eval()')
    _expr(f.par.fit, 'parent().par.Fit.eval()')
    return f


def _sources(c):
    in1, in2, in3 = _mk(c, inTOP, 'in1'), _mk(c, inTOP, 'in2'), _mk(c, inTOP, 'in3')
    ta = _mk(c, moviefileinTOP, 'test_a')
    ta.par.file = TEST_A
    _expr(ta.par.play, "parent().op('a_src').par.index.eval() == 0")
    ta.comment = 'A test: stored 5 s webcam clip (plays only while A uses it).'
    tb = _mk(c, moviefileinTOP, 'test_b')
    tb.par.file = TEST_B
    _expr(tb.par.play, "parent().op('b_src').par.index.eval() == 0")
    tb.comment = 'B test: testsrc2 clip (moving; mosh needs motion in B).'
    a = _mk(c, switchTOP, 'a_src')
    _wire(a, 0, ta)
    _wire(a, 1, in1)
    _expr(a.par.index, "0 if parent().par.Asource.eval() == 'test' else (%s)" % _auto_index('in1'))
    b = _mk(c, switchTOP, 'b_src')
    _wire(b, 0, tb)
    _wire(b, 1, in2)
    _expr(b.par.index, "0 if parent().par.Bsource.eval() == 'test' else (%s)" % _auto_index('in2'))
    af, bf = _fit(c, 'a_fit', a), _fit(c, 'b_fit', b)
    af.comment = 'A fitted to Resw x Resh (Fit).'
    bf.comment = 'B fitted to Resw x Resh (Fit).'
    rp = _mk(c, rampTOP, 'm_ramp')
    _expr(rp.par.type, "'radial' if parent().par.Mattesource.eval() == 'radial' else 'horizontal'")
    rp.par.outputresolution = 'custom'
    rp.par.resolutionw, rp.par.resolutionh = 540, 960
    rp.comment = 'Built-in matte: horizontal or radial ramp (Mattesource).'
    nz = _mk(c, noiseTOP, 'm_noise')
    nz.par.outputresolution = 'custom'
    nz.par.resolutionw, nz.par.resolutionh = 540, 960
    nz.par.mono = True
    nz.comment = 'Built-in matte: noise (static unless you animate it).'
    ms = _mk(c, selectTOP, 'm_sel')
    _expr(ms.par.top, "parent().par.Mattetop.eval() or 'm_ramp'")
    ms.comment = 'Matte from any TOP path (Mattesource = top).'
    m = _mk(c, switchTOP, 'm_src')
    for i, s in enumerate((rp, in3, nz, ms)):
        _wire(m, i, s)
    _expr(m.par.index, "{'ramp': 0, 'radial': 0, 'noise': 2, 'top': 3}.get(parent().par.Mattesource.eval(), "
                       "1 if (%s) else 0)" % _auto_index('in3'))
    mf = _fit(c, 'm_fit', m)
    mf.comment = 'Matte fitted to the output size (in2 of the shader: matte / displace).'
    return af, bf, mf


def _prog(c):
    p = _mk(c, constantCHOP, 'prog')
    for k, nm in enumerate(['raw', 'p', 'swap', 'out', 'type']):
        getattr(p.par, 'name%d' % k).val = nm
        _expr(getattr(p.par, 'value%d' % k), "%s.chan(parent(), absTime.seconds, %d)" % (LOGIC, k))
    p.comment = ('Progress: raw (slider or Go run), p (eased, swapped), swap, out (0 A / 1 B / 2 shader / 3 mosh), '
                 'type index. One logic call per cook (chan: channel 0 computes, 1..4 reuse).')
    return p


def _shader(c, Lg, af, bf, mf):
    g = _mk(c, glslTOP, 'trans')
    d = c.op('trans_compute')
    if d is None:
        d = _mk(c, textDAT, 'trans_compute')
        d.dock = g
    tid = c.par.Type.eval()
    txt = Lg['shader_text'](None if c.par.Compile.eval() == 'bank' else
                            ([tid] if tid in Lg['SHADER_TYPES'] else ['fade']))
    if d.text != txt:
        d.text = txt
    for extra in ('trans_pixel', 'trans_info', 'trans_vertex', 'trans_compute1'):
        if c.op(extra) is not None:
            _sd(c.op(extra))
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, 'parent().par.Resw.eval()')
    _expr(g.par.resolutionh, 'parent().par.Resh.eval()')
    g.par.format = 'rgba16float'
    g.par.inputextenduv = 'hold'
    g.par.inputfiltertype = 'linear'
    for i, s in enumerate((af, bf, mf)):                     # 3 wired inputs (T-88 max)
        _wire(g, i, s)
    P = 'parent().par.K%d.eval()'
    U = [('uT', ["op('prog')['p']", "op('prog')['type']", "op('prog')['swap']", 'parent().par.Outside.menuIndex']),
         ('uK0', [P % 1, P % 2, P % 3, P % 4]), ('uK1', [P % 5, P % 6, P % 7, P % 8]),
         ('uK2', [P % 9, P % 10, '0', '0'])]
    g.seq.vec.numBlocks = max(len(U), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)
    g.comment = 'Transition shader (generated: fx_trans_logic.shader_text). Cooks only while 0 < raw < 1.'
    return g


MOSH_MAP = [('Melt', 'parent().par.K1.eval()'),
            ('Order', "['noise', 'topdown', 'bottomup', 'radial', 'luma'][int(round(parent().par.K2.eval())) % 5]"),
            ('Cutmode', "['hard', 'soft', 'bloom'][int(round(parent().par.K3.eval())) % 3]"),
            ('Gain', 'parent().par.K4.eval()'), ('Residual', 'parent().par.K5.eval()'),
            ('Decay', 'parent().par.K6.eval()'), ('Bloomgain', 'parent().par.K7.eval()'),
            ('Seed', 'int(round(parent().par.K8.eval()))'),
            ('Progress', "float(parent().op('prog')['p'])"), ('Btop', "parent().path + '/mosh_b'")]


def _mosh(c, af, bf):
    """Sub-COMP `mosh` = FX_glitch's moshcut module, built by FX_glitch's own helpers (fx_glitch.py + the module
    file, exec'd: nothing copied). A / B swap with the run (mosh_a / mosh_b)."""
    ma, mb = _mk(c, switchTOP, 'mosh_a'), _mk(c, switchTOP, 'mosh_b')
    for sw, (x, y) in ((ma, (af, bf)), (mb, (bf, af))):
        _wire(sw, 0, x)
        _wire(sw, 1, y)
        _expr(sw.par.index, "1 if op('prog')['swap'] > 0.5 else 0")
    G = dict(globals())
    with open(GLITCH_FILE) as fh:
        exec(fh.read(), G)
    M = dict(G)
    with open(MOSHCUT_FILE) as fh:
        exec(fh.read(), M)
    sub = c.op('mosh')
    if sub is None or not sub.isCOMP:
        sub = _mk(c, baseCOMP, 'mosh')
    G['_pars'](sub, M['PAGES'])
    stages = M['build'](sub, G['H'])
    sub.par.Amount = 1.0
    sub.par.Drive = 'manual'
    sub.par.Bsource = 'top'
    for pn, e in MOSH_MAP:
        _expr(getattr(sub.par, pn), e)
    sub.par.opviewer.expr = "me.op('out1')"
    sub.par.opviewer.mode = ParMode.EXPRESSION
    sub.viewer = True
    sub.comment = ('FX_glitch moshcut engine (builders/fx_glitch_moshcut.py). Knobs K1..K8 of FX_trans drive it when '
                   'Type = mosh; cooks only then.')
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if sub.op(n) is not None]
    op('/jazib_mcp/handlers').module.layout_stages(sub, [s_ for s_ in stages if s_['ops']], True, arrange='mixed')
    _wire(sub, 0, ma)
    return sub


def _logic_dats(c):
    d = _mk(c, textDAT, 'fx_trans_logic')
    with open(os.path.join(HERE, 'fx_trans_logic.py')) as fh:
        txt = fh.read()
    if d.text != txt:
        d.text = txt
    d.comment = 'Module DAT = builders/fx_trans_logic.py (same text; edit the file and rebuild).'
    Lg = load_logic()
    src = _mk(c, textDAT, 'fx_trans_src')
    s = json.dumps(dict((stem, Lg['gl_text'](stem)) for _t, stem in Lg['GL_ALL']), sort_keys=True)
    if src.text != s:
        src.text = s
    src.comment = 'The 25 vendored gl-transitions (JSON stem -> source; MIT, builders/glsl/fx_trans/SOURCES.md).'
    return Lg


def _type_menu(c, Lg):
    """Type menu names / labels = the logic's TYPES (an existing COMP keeps its value; new types append)."""
    B = Lg['bank']()
    p = c.par.Type
    names, labels = list(Lg['TYPES']), [B[t]['label'] for t in Lg['TYPES']]
    if list(p.menuNames) != names or list(p.menuLabels) != labels:
        v = p.eval()
        p.menuNames, p.menuLabels = names, labels
        p.val = v if v in names else names[0]


def _seed_presets(c, Lg):
    """Add the builder's preset slots that the panel's table lacks (never overwrites a slot: the user's own kept)."""
    pt = c.op('controls/zk_presets')
    if pt is None:
        return []
    L = c.op('controls/zk_logic').module
    have = set(pt[i, 'slot'].val for i in range(1, pt.numRows))
    added = []
    for slot, pname, vals in presets(Lg):
        if str(slot) not in have:
            pt.appendRow([slot, pname, L.DEFAULT_COLOR, L.preset_dump(vals)])
            added.append(slot)
    return added


def upgrade(parent_path='/project1/lab'):
    """Light update of an existing FX_trans (main, by builder; no mosh / panel rebuild): logic + sources DATs, Type
    menu, shader text (bank or the selected type), missing preset slots. Un-park + 2 frames first (T-146)."""
    Lg = load_logic()
    c = op(parent_path).op(NAME)
    _logic_dats(c)
    _type_menu(c, Lg)
    tid = c.par.Type.eval()
    d = c.op('trans_compute')
    txt = Lg['shader_text'](None if c.par.Compile.eval() == 'bank' else
                            ([tid] if tid in Lg['SHADER_TYPES'] else ['fade']))
    if d.text != txt:
        d.text = txt
    return {'comp': c.path, 'types': len(Lg['TYPES']), 'presets_added': _seed_presets(c, Lg),
            'shader_chars': len(txt)}


def build(parent_path='/project1/lab', panel=True):
    Lg = load_logic()
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('FX_trans (G-TRANS): transition bank A (in1) -> B (in2), matte in3. Type + Progress / Go / Back / '
                 'Cut, Drive seconds / beats, Ease, knobs K1..K10 follow the type. out1. builders/fx_trans.py.')
    _pars(c, pages(Lg))
    _logic_dats(c)
    _type_menu(c, Lg)
    af, bf, mf = _sources(c)
    _prog(c)
    g = _shader(c, Lg, af, bf, mf)
    sub = _mosh(c, af, bf)
    sel = _mk(c, switchTOP, 'out_sel')
    for i, s in enumerate((af, bf, g, sub)):
        _wire(sel, i, s)
    _expr(sel.par.index, "int(op('prog')['out'])")
    sel.comment = 'out: 0 = A exact (raw 0), 1 = B exact (raw 1), 2 = shader, 3 = mosh. Only the picked input cooks.'
    o1 = _mk(c, outTOP, 'out1')
    _wire(o1, 0, sel)
    pe = _mk(c, parameterexecuteDAT, 'pexec')
    if pe.text != PEXEC:
        pe.text = PEXEC
        pe.par.active = False                               # T-97: toggle after a text rewrite
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Go Back Cut Resetknobs Type Compile'
    pe.par.valuechange = True
    pe.par.onpulse = True
    pe.par.active = True
    pe.comment = 'Go / Back / Cut -> run state; Type / Compile -> knobs (labels, defaults) + shader text.'
    Lg['apply_type'](c, keep=c.fetch('fx_trans_built', False, search=False))
    c.store('fx_trans_built', True)
    info = None
    stages = [
        {'title': 'Logic', 'role': 'control', 'ops': ['fx_trans_logic', 'fx_trans_src', 'pexec', 'prog'],
         'body': 'fx_trans_logic (module), sources JSON, pulses / Type exec, prog CHOP (raw, p, swap, out, type).'},
        {'title': '1 Inputs', 'role': 'input', 'ops': ['in1', 'in2', 'in3', 'test_a', 'test_b', 'a_src', 'b_src',
                                                       'a_fit', 'b_fit', 'm_ramp', 'm_noise', 'm_sel', 'm_src',
                                                       'm_fit'],
         'body': 'A = in1 / test clip, B = in2 / testsrc2, matte = in3 / ramp / noise / TOP path; all fitted.'},
        {'title': '2 Transition', 'role': 'process', 'ops': ['trans', 'trans_compute', 'mosh_a', 'mosh_b', 'mosh'],
         'body': 'One compute shader (selected type or whole bank) or the moshcut sub-COMP (Type mosh).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Ends are exact A / B.'},
    ]
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=56, cols=6)
        _seed_presets(c, Lg)                                # missing slots only (the user's own kept)
        stages = [{'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window']}] + stages
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    lay = op('/jazib_mcp/handlers').module.layout_stages(c, [s_ for s_ in stages if s_['ops']], True, arrange='mixed')
    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    return {'comp': c.path, 'types': len(Lg['TYPES']), 'mosh': sub.path, 'panel': bool(info), 'layout': str(lay)[:200]}
