# fx_retro builder - FX_retro: picture in -> a short chain of retro module slots -> Panic -> out1.
# The SAME lean rack as builders/fx_glitch.py / fx_destroy.py (template: docs/builds/fx_glitch.md), copied, not
# abstracted: a slot is the module COMP + a Cross TOP (<name>_mix) + a Switch TOP (<name>_slot: 0 bypass / 1 module /
# 2 mix); the `slots` table (name module enabled order mix) is the only rack state; add / remove / reorder = rewire.
# Module 'X' lives in builders/fx_retro_X.py (palette, dither, glyph, teletext, smalldisplay, pixelart, ...). Doc: docs/builds/fx_retro.md.
# Shared here (2+ modules use each today, no-bloat rule): the logic DATs (fx_retro_logic + palette_map_logic +
# fx_retro_font8x8, same files as builders/), the palette bank texture (palette, dither, glyph), the 64x64 blue-noise
# texture (palette, dither), the GLSL lib (hash, Bayer / IGN / blue dither, OKLab, palette search, 8x8 font), the
# Script CHOP -> texture-buffer text codes (teletext, smalldisplay), a pulse -> time-stamp Parameter Execute
# (teletext, smalldisplay), a compute GLSL helper with manual dispatch, texture-buffer arrays, extra in-place buffers.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_retro.py').read(), ns)
#   ns['build']('/project1/lab')                          # rack + palette1 (on) / dither1 / glyph1 / teletext1 /
#                                                         # smalldisplay1 (enabled 0) on first build; idempotent
#   ns['add']('/project1/lab/FX_retro', 'dither')          # dither2, wired last
#   ns['remove']('/project1/lab/FX_retro', 'dither2'); ns['rewire'](c) after editing order in `slots`
# T-70 safe (_sd = safe_destroy, instance windows closed before a remove; pane never moved). ASCII only.
import os
import sys

NAME = 'FX_retro'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
TEST_CLIP = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'
COLS = ['name', 'module', 'enabled', 'order', 'mix']
MODULES = ['palette', 'dither', 'glyph', 'teletext', 'smalldisplay', 'pixelart', 'scaler', 'stitch', 'ps1', 'retroscreen', 'cycle', 'halftone']
DEFAULT_ROWS = [['palette1', 'palette', 1, 1, 1], ['dither1', 'dither', 0, 2, 1], ['glyph1', 'glyph', 0, 3, 1],
                ['teletext1', 'teletext', 0, 4, 1], ['smalldisplay1', 'smalldisplay', 0, 5, 1],
                ['pixelart1', 'pixelart', 0, 6, 1], ['scaler1', 'scaler', 0, 7, 1], ['stitch1', 'stitch', 0, 8, 1],
                ['ps11', 'ps1', 0, 9, 1], ['retroscreen1', 'retroscreen', 0, 10, 1],
                ['cycle1', 'cycle', 0, 11, 1], ['halftone1', 'halftone', 0, 12, 1]]                 # lane D modules (27 Oct) rest enabled 0
LOGIC_DATS = ['fx_retro_logic', 'palette_map_logic', 'fx_retro_font8x8']     # Text DAT name = file stem in builders/
LX = "parent(2).op('fx_retro_logic').module"          # the logic module, from an op inside a module instance
INPUTS = ['auto', 'live', 'test', 'ramp']


def plan_chain(rows):
    """rows: [{name, order, ...}] -> names in chain order (order, then table position). Pure; tested offline."""
    idx = [(float(r.get('order') or 0), i, r['name']) for i, r in enumerate(rows)]
    return [n for _o, _i, n in sorted(idx)]


def chain_edges(names, src='img_src'):
    """Desired (dst, connector, src) wires for the chain names, then panic + out1. Pure; tested offline."""
    e, prev = [], src
    for n in names:
        e += [(n, 0, prev), (n + '_mix', 0, prev), (n + '_mix', 1, n),
              (n + '_slot', 0, prev), (n + '_slot', 1, n), (n + '_slot', 2, n + '_mix')]
        prev = n + '_slot'
    return e + [('panic', 0, prev), ('panic', 1, src), ('out1', 0, 'panic')]


def next_name(module, taken):
    k = 1
    while '%s%d' % (module, k) in taken:
        k += 1
    return '%s%d' % (module, k)


def load_logic():
    """The logic module from builders/ (offline and in the builder; the runtime uses the rack DAT copy)."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    ns = {'__name__': 'fx_retro_logic_build'}
    path = os.path.join(HERE, 'fx_retro_logic.py')
    with open(path) as fh:
        exec(compile(fh.read(), path, 'exec'), ns)
    return ns


# ------------------------------------------------------------------ shared GLSL (pure strings; mirrors fx_retro_logic)
GLSL_BASE = """// ---- FX_retro lib (builders/fx_retro.py; maths = builders/fx_retro_logic.py) ----
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hsh(ivec2 c, uint s) { return float(lb32(uint(c.x) * 1597334677u ^ lb32(uint(c.y) ^ (s * 2654435761u))) >> 8)
                                   * (1.0 / 16777216.0); }
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
float cbrtf(float x) { return sign(x) * pow(abs(x), 1.0 / 3.0); }
vec3 toLin(vec3 c) { c = clamp(c, 0.0, 1.0); return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c)); }
vec3 toSrgb(vec3 c) { c = clamp(c, 0.0, 1.0); return mix(12.92 * c, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c)); }
vec3 oklab(vec3 srgb) {
    vec3 c = toLin(srgb);
    float l = cbrtf(0.4122214708 * c.r + 0.5363325363 * c.g + 0.0514459929 * c.b);
    float m = cbrtf(0.2119034982 * c.r + 0.6806995451 * c.g + 0.1073969566 * c.b);
    float s = cbrtf(0.0883024619 * c.r + 0.2817188376 * c.g + 0.6299787005 * c.b);
    return vec3(0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s);
}
vec3 straight(vec4 s) { return s.a > 1e-5 ? s.rgb / s.a : s.rgb; }
vec3 preAdjust(vec3 c, float contrast, float bright, float sat) {
    c = (c - 0.5) * contrast + 0.5 + bright;
    return clamp(mix(vec3(luma(c)), c, sat), 0.0, 1.0);
}
float quantL(float v, float levels, float thr) {           // floor(v (L-1) + thr) / (L-1); thr 0.5 = round
    float L = max(levels, 2.0) - 1.0;
    return clamp(floor(v * L + thr) / L, 0.0, 1.0);
}
float bayerT(ivec2 q, int n) {                             // 2^n x 2^n ordered threshold, (v + 0.5) / 4^n
    uint x = uint(q.x), y = uint(q.y), v = 0u;
    for (int i = 0; i < 4; i++) {
        if (i >= n) break;
        uint bx = (x >> uint(i)) & 1u, by = (y >> uint(i)) & 1u, s = uint(2 * (n - 1 - i));
        v |= ((bx ^ by) << (s + 1u)) | (by << s);
    }
    return (float(v) + 0.5) / float(1 << (2 * n));
}
float ignT(ivec2 p) { return fract(52.9829189 * fract(dot(vec2(p), vec2(0.06711056, 0.00583715)))); }
"""

GLSL_BN = """#define BNS sTD2DInputs[BN_IN]
float blueT(ivec2 p) { ivec2 q = ((p % 64) + 64) % 64; return texelFetch(BNS, q, 0).r; }
"""

GLSL_DITHER = """float ditherT(int m, ivec2 p, uint seed, int tick) {    // m: 0 none 1-4 Bayer 2..16 5 IGN 6 white 7 blue
    if (m <= 0) return 0.5;
    ivec2 o = p + ivec2(tick * 37, tick * 23);
    if (m <= 4) { int k = (1 << m) - 1; return bayerT(ivec2(o.x & k, o.y & k), m); }
    if (m == 5) return ignT(o);
    if (m == 6) return hsh(p, seed * 7919u + uint(tick) * 131u);
#ifdef BN_IN
    return blueT(o);
#else
    return ignT(o);
#endif
}
float strengthT(float t, float s) { return 0.5 + (t - 0.5) * s; }
"""

GLSL_PAL = """#define PALS sTD2DInputs[PAL_IN]
float palv(int i, int row) { return texelFetch(PALS, ivec2(clamp(i, 0, textureSize(PALS, 0).x - 1), row), 0).r; }
vec3 palRgb(int i) { return vec3(palv(i, 0), palv(i, 1), palv(i, 2)); }
vec3 palLab(int i) { return vec3(palv(i, 3), palv(i, 4), palv(i, 5)); }
vec3 palQ(int i, bool lab) { return lab ? palLab(i) : palRgb(i); }
float pdist(vec3 a, vec3 b, bool lab, float wl) { vec3 d = a - b; if (lab) d.x *= wl; return dot(d, d); }
void nearest2(vec3 q, bool lab, float wl, int off, int n, out int i1, out float d1, out int i2, out float d2) {
    d1 = 1e30; d2 = 1e30; i1 = 0; i2 = 0;
    for (int i = 0; i < n; i++) {
        float d = pdist(q, palQ(off + i, lab), lab, wl);
        if (d < d1) { d2 = d1; i2 = i1; d1 = d; i1 = i; }
        else if (d < d2) { d2 = d; i2 = i; }
    }
}
int pickT(float d1, float d2, int i1, int i2, int n, bool dith, float thr, float amt) {   // palette_map's rule
    if (!dith || n < 2) return i1;
    float e1 = sqrt(d1), e2 = sqrt(d2);
    float t = (e1 + e2) > 0.0 ? e1 / (e1 + e2) : 0.0;
    return t * amt > thr ? i2 : i1;
}
int pickPal(vec3 c, bool lab, float wl, int off, int n, bool dith, float thr, float amt) {
    vec3 q = lab ? oklab(c) : c;
    int i1, i2; float d1, d2;
    nearest2(q, lab, wl, off, n, i1, d1, i2, d2);
    return pickT(d1, d2, i1, i2, n, dith, thr, amt);
}
"""


def glsl_lib(Lg, pal_in=None, bn_in=None, font=None, kernels=False, nixie=False, flap=False):
    """The lib text a module prepends (defines first). Lg = the logic namespace / module (font / kernel tables).
    pal_in / bn_in / font = the input index of the pal / bn / font Select TOP (None = not used)."""
    g = Lg if isinstance(Lg, dict) else vars(Lg)
    s = ''
    if pal_in is not None:
        s += '#define PAL_IN %d\n' % pal_in
    if bn_in is not None:
        s += '#define BN_IN %d\n' % bn_in
    if font is not None:
        assert not isinstance(font, bool), 'font = the font input index'
        s += '#define FONT_IN %d\n' % font
    s += GLSL_BASE
    if bn_in is not None:
        s += GLSL_BN
    s += GLSL_DITHER
    if pal_in is not None:
        s += GLSL_PAL
    if font is not None:
        s += g['font_glsl']()
    if kernels:
        s += g['kernels_glsl']()
    if nixie:
        s += g['nixie_glsl']()
    if flap:
        s += g['flap_glsl']()
    return s


PULSE_EXEC = """# Pulse pars -> a time stamp par (absTime.seconds) the shaders compare with (no per-frame Python).
TARGET = %r

def onPulse(par):
    t = TARGET.get(par.name)
    if t is not None:
        getattr(par.owner.par, t).val = absTime.seconds
    return
"""

CODES_CB = """# %(name)s: text codes for the module's shader (texture buffer uCodes, one float per cell, top row first).
# Logic: the rack's fx_retro_logic (%(fn)s). Cooks when a par it reads changes, and once a second (Tick).
import time

def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    L = parent(2).op('fx_retro_logic').module
    m = parent()
    tm = time.localtime()
    T = (tm.tm_year, tm.tm_mon, tm.tm_mday, tm.tm_hour, tm.tm_min, tm.tm_sec, tm.tm_wday)
    i1 = op('in1')
    w, h = (i1.width, i1.height) if i1 is not None and i1.width > 0 else (1080, 1920)
    vals = L.%(fn)s(m, T, w, h) or [0]
    scriptOp.clear()
    scriptOp.numSamples = len(vals)
    c = scriptOp.appendChan('c')
    c.vals = [float(v) for v in vals]
    return
"""


# ------------------------------------------------------------------ TD side
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


def _set(par, v):
    if isinstance(v, str) and v.startswith('='):
        _expr(par, v[1:])
    else:
        par.mode = ParMode.CONSTANT
        par.val = v


def _compute(m, name, text, inputs, w_expr, h_expr, fmt='useinput', uniforms=(), readwrite=False, extend=None,
             dispatch=None, arrays=(), bufs=1):
    """A compute GLSL TOP (T-47) with its shader in a docked Text DAT. w/h: expression str or int. uniforms =
    [(name, [4 exprs])]; dispatch = (x expr, y expr) workgroups (T-114 (1)), None = auto; arrays = [(uniform, CHOP)]
    as float texture buffers (T-110: `uniform samplerBuffer`). At most 3 wired inputs (T-84/T-88)."""
    assert len(inputs) <= 3, 'GLSL TOP: 3 wired inputs at most (T-88)'
    g = _mk(m, glslTOP, name)
    d = m.op(name + '_compute')
    if d is None:
        d = _mk(m, textDAT, name + '_compute')
        d.dock = g
    if d.text != text:
        d.text = text
    for extra in (name + '_pixel', name + '_info', name + '_compute1', name + '_vertex'):   # T-115 (5) templates
        if m.op(extra) is not None and extra != d.name:
            _sd(m.op(extra))
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    for par, e in ((g.par.resolutionw, w_expr), (g.par.resolutionh, h_expr)):
        _set(par, '=' + e if isinstance(e, str) else e)
    g.par.format = fmt
    if readwrite:
        g.par.outputaccess = 'readwrite'
        g.par.clearoutputs = False
    if bufs > 1:
        g.par.numcolorbufs = bufs                          # T-110 (5): extra buffers persist in place too
    if extend:
        g.par.inputextenduv = extend
    if dispatch:
        g.par.autodispatchsize = False
        _expr(g.par.dispatchsizex, dispatch[0])
        _expr(g.par.dispatchsizey, dispatch[1])
        g.par.dispatchsizez = 1
    else:
        g.par.autodispatchsize = True
    for k, src in enumerate(inputs):
        cn = g.inputConnectors[k].connections
        if not cn or cn[0].owner != src:
            g.inputConnectors[k].connect(src)
    g.seq.vec.numBlocks = max(len(uniforms), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(uniforms):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)
    if arrays:
        g.seq.array.numBlocks = max(int(g.seq.array.numBlocks), len(arrays))
        for k, (un, chop) in enumerate(arrays):
            getattr(g.par, 'array{}name'.format(k)).val = un
            getattr(g.par, 'array{}type'.format(k)).val = 'float'
            getattr(g.par, 'array{}arraytype'.format(k)).val = 'texturebuffer'
            getattr(g.par, 'array{}chop'.format(k)).val = chop.name
    return g


def _select(m, name, path):
    s = _mk(m, selectTOP, name)
    s.par.top = path
    return s


def _pulse_exec(m, targets):
    """targets = {Pulsepar: Timepar}; the time pars must exist (module PAGES)."""
    pe = _mk(m, parameterexecuteDAT, 'pulse_exec')
    txt = PULSE_EXEC % dict(targets)
    if pe.text != txt:
        pe.text = txt
        pe.par.active = False                              # T-97: toggle after a text rewrite
    pe.par.op = '..'
    pe.par.pars = ' '.join(sorted(targets))
    pe.par.valuechange = False
    pe.par.onpulse = True
    pe.par.active = True
    pe.comment = 'Pulses %s -> time stamp pars (read by the shaders).' % ' '.join(sorted(targets))
    return pe


def _codes_chop(m, fn, comment):
    """Script CHOP `codes` (channel c) from fx_retro_logic.<fn>(module, time tuple, w, h); Tick = once a second."""
    s = _mk(m, scriptCHOP, 'codes')
    cb = m.op('codes_callbacks') or _mk(m, textDAT, 'codes_callbacks')
    txt = CODES_CB % {'name': 'codes', 'fn': fn}
    if cb.text != txt:
        cb.text = txt
    cb.dock = s
    s.par.callbacks = cb.name
    if getattr(s.par, 'Tick', None) is None:
        pg = next((p for p in s.customPages if p.name == 'Clock'), None) or s.appendCustomPage('Clock')
        pg.appendFloat('Tick', label='Tick (1/s)')
    _expr(s.par.Tick, 'int(absTime.seconds)')
    s.comment = comment
    return s


P = "parent().par.{}.eval()"
H = {'mk': _mk, 'expr': _expr, 'sd': _sd, 'compute': _compute, 'select': _select,
     'pulse_exec': _pulse_exec, 'codes_chop': _codes_chop, 'P': P, 'LX': LX, 'glsl_lib': glsl_lib}


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            ex = getattr(c.par, name, None)
            if ex is not None and style == 'Menu' and list(ex.menuNames) != list(o['names']):   # T-175 / T-190
                v = ex.eval()
                ex.menuNames, ex.menuLabels = o['names'], o['labels']
                if v in o['names']:
                    ex.val = v
            if ex is not None or getattr(c.par, name + 'r', None) is not None:
                continue
            label = o.get('label', name)
            p = None
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']      # slider range only, no clamps (no limits)
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style == 'RGB':
                for q, v in zip(page.appendRGB(name, label=label), default):
                    q.default = v
                    q.val = v
            elif style in ('TOP', 'COMP', 'CHOP', 'DAT'):
                p = getattr(page, 'append' + style)(name, label=label)[0]
            if p is not None:
                p.default = default
                p.val = default


def _module(module):
    ns = dict(globals())
    exec(open(os.path.join(HERE, 'fx_retro_%s.py' % module)).read(), ns)
    return ns


def _rows(c):
    t = c.op('slots')
    return [dict((k, t[i, k].val) for k in COLS) for i in range(1, t.numRows)]


def _cell(name, col):
    return "op('slots')['%s', '%s'].val" % (name, col)


def _slot_ops(c, name):
    mx = _mk(c, crossTOP, name + '_mix')
    _expr(mx.par.cross, 'float(%s or 0)' % _cell(name, 'mix'))
    mx.comment = 'Slot %s: dry/wet (slots.mix); only cooks when 0 < mix < 1.' % name
    sw = _mk(c, switchTOP, name + '_slot')
    _expr(sw.par.index, "0 if not int({e} or 0) or float({m} or 0) <= 0 else (1 if float({m}) >= 1 else 2)"
          .format(e=_cell(name, 'enabled'), m=_cell(name, 'mix')))
    sw.comment = 'Slot %s: 0 bypass (exact, module not cooked) / 1 module / 2 mix.' % name


# slot_gate (T-198 / T-201; same block as builders/fx_glitch.py, this rack is a copy): a Switch TOP in each module COMP right before out1: 0 = in1 (exact passthrough,
# nothing upstream in the module cooks) when the rack slot is off (slots enabled 0 or mix <= 0, the same test as the
# rack's <name>_slot Switch), 1 = the module's own output (unchanged when the slot is on). The rack's <name>_mix Cross
# TOP keeps its viewer on (user rule) and a visible viewer pulls the module even while <name>_slot bypasses it, so
# with the network pane on the rack every disabled module cooked (docs/builds/RENDER_COST.md). No slots row = on.
# A module whose out1 already comes from a slot-aware out_sel (GEN_points OUT_SEL_E) is left alone.
_SLOT_CELL = "parent(2).op('slots')[parent().name, '%s']"
SLOT_OFF_E = ("(parent(2).op('slots') is not None and (not int(float(getattr(" + _SLOT_CELL % 'enabled' +
              ", 'val', '1') or 0)) or float(getattr(" + _SLOT_CELL % 'mix' + ", 'val', '1') or 0) <= 0))")
SLOT_GATE_E = '0 if ' + SLOT_OFF_E + ' else 1'


def slot_off(enabled, mix):
    """The gate / <name>_slot test on two slots cells (strings; None = no row = on). Pure; tested offline."""
    en = '1' if enabled is None else enabled
    mx = '1' if mix is None else mix
    return not int(float(en or 0)) or float(mx or 0) <= 0


def gate_needed(src_name, src_index_expr):
    """False when out1's source is already slot-aware (an out_sel whose index reads the slots table). Pure."""
    return not (src_name == 'out_sel' and "op('slots')" in (src_index_expr or ''))


def _slot_gate(m, stages):
    """Insert / refresh `slot_gate` (in1 / module out) before out1 in module COMP m; idempotent (a module rebuild that
    re-wires out1 to its own source is re-gated). Adds it to the stage holding out1. Returns stages."""
    out1, in1 = m.op('out1'), m.op('in1')
    if out1 is None or in1 is None or not out1.inputConnectors or not out1.inputConnectors[0].connections:
        return stages
    conn = out1.inputConnectors[0].connections[0]       # an output connector (a COMP source needs it, T-111 (2))
    src = conn.owner
    g = m.op('slot_gate')
    if src is not g:
        if not gate_needed(src.name, getattr(getattr(src.par, 'index', None), 'expr', '')) or src is in1:
            _sd(g)                                        # stale gate from an older layout
            return stages
        g = _mk(m, switchTOP, 'slot_gate')
        g.inputConnectors[0].connect(in1)
        g.inputConnectors[1].connect(conn)
        out1.inputConnectors[0].connect(g)
    elif not g.inputConnectors[0].connections or g.inputConnectors[0].connections[0].owner is not in1:
        g.inputConnectors[0].connect(in1)
    _expr(g.par.index, SLOT_GATE_E)
    g.comment = ('Slot off (slots enabled 0 / mix 0) = in1 untouched, nothing in this module cooks, also when a '
                 'viewer shows the rack (RENDER_COST.md, T-198); slot on = the module output.')
    return gate_stages(stages)


def gate_stages(stages):
    """Put 'slot_gate' just before 'out1' in the stage that lists out1 (else the last stage). Pure; tested offline."""
    if not stages or any('slot_gate' in s_['ops'] for s_ in stages):
        return stages
    s_ = next((s_ for s_ in stages if 'out1' in s_['ops']), stages[-1])
    s_['ops'] = [n for n in s_['ops'] if n != 'out1'] + ['slot_gate'] + (['out1'] if 'out1' in s_['ops'] else [])
    return stages

def gate_upgrade(comp_path, name):
    """Gate-only upgrade of an EXISTING instance (main, T-152: one rack per exec): adds / refreshes `slot_gate` and
    re-applies the module's stored stage plan with it, without rebuilding the module (shaders, pars, presets stay).
    Returns the gate index (0 = slot off) or why it was skipped."""
    c = op(comp_path)
    m = c.op(name) if c is not None else None
    if m is None or not m.isCOMP:
        return {'name': name, 'error': 'no instance'}
    hm = op('/jazib_mcp/handlers').module
    plan = hm._stage_plan(m) or {}
    stages = [dict(s_, ops=[n for n in (s_.get('ops') or []) if m.op(n) is not None]) for s_ in plan.get('stages', [])]
    had = m.op('slot_gate') is not None
    stages = [s_ for s_ in _slot_gate(m, stages) if s_['ops']]
    g = m.op('slot_gate')
    if g is not None and not had and stages:
        hm.layout_stages(m, stages, plan.get('colors', True), arrange=plan.get('arrange') or 'mixed')
    return {'name': name, 'gated': g is not None, 'new': g is not None and not had,
            'index': int(g.par.index.eval()) if g is not None else None}



def _instance(c, name, module, Lg, panel=True):
    M = _module(module)
    m = c.op(name)
    if m is None or not m.isCOMP:
        m = _mk(c, baseCOMP, name)
    _pars(m, M['PAGES'])
    m.comment = 'FX_retro module %s (%s). Pars on its custom pages; pulse Opencontrols for the zkit panel.' % (
        name, module)
    stages = _slot_gate(m, M['build'](m, H, Lg))
    m.par.opviewer.expr = "me.op('out1')"
    m.par.opviewer.mode = ParMode.EXPRESSION
    m.viewer = True
    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](m.path, pages=M['PANEL_PAGES'], d=56, cols=6)
        pt = m.op('controls/zk_presets')
        if pt is not None and pt.numRows <= 1:              # seed the module presets once (user's own kept)
            L = m.op('controls/zk_logic').module
            for slot, pname, vals in M['PRESETS']:
                pt.appendRow([slot, pname, L.DEFAULT_COLOR, L.preset_dump(vals)])
        stages = [{'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window']}] + stages
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if m.op(n) is not None]
    op('/jazib_mcp/handlers').module.layout_stages(m, [s_ for s_ in stages if s_['ops']], True, arrange='mixed')
    _slot_ops(c, name)
    return {'instance': m.path, 'panel': bool(info)}


def rewire(c):
    """Make the chain match `slots`; touches only connectors that differ. Returns the number of wires changed."""
    names = [n for n in plan_chain(_rows(c)) if c.op(n) is not None]
    changed = 0
    for dst, i, src in chain_edges(names):
        d, s = c.op(dst), c.op(src)
        conns = d.inputConnectors[i].connections
        if conns and conns[0].owner == s:
            continue
        d.inputConnectors[i].connect(s.outputConnectors[0])   # a COMP source needs its connector, not the op
        changed += 1
    return changed


def _shared(c, Lg):
    """Logic DATs, palette bank (pal_custom -> pal_bank -> pal_chop -> pal_top), blue noise (bn_table -> bn_chop ->
    bn_top). Static data cooks once; pal_bank recooks only when pal_custom changes."""
    for n in LOGIC_DATS:
        d = _mk(c, textDAT, n)
        txt = open(os.path.join(HERE, n + '.py')).read()
        if d.text != txt:
            d.text = txt
        d.comment = 'Module DAT = builders/%s.py (same text; edit the file and rebuild).' % n
    cust = _mk(c, tableDAT, 'pal_custom')
    if cust.numRows == 0 or (cust.numRows == 1 and cust[0, 0].val == ''):
        cust.clear()
        for h in ('000000', 'FFFFFF'):
            cust.appendRow([h])
    cust.comment = 'Custom palette (Machine = Custom): one hex per row, # optional. T-107: never assume a new table is empty.'
    bank = _mk(c, scriptDAT, 'pal_bank')
    cb = c.op('pal_bank_callbacks') or _mk(c, textDAT, 'pal_bank_callbacks')
    cb.text = PAL_BANK_CB
    cb.dock = bank
    bank.par.callbacks = cb.name
    bank.comment = 'Palette bank: every hardware palette + Lospec presets + pal_custom, rows hex r g b L A B.'
    pch = _mk(c, dattoCHOP, 'pal_chop')
    pch.par.dat = bank.name
    pch.par.output = 'chanpercol'
    pch.par.firstrow = 'names'
    pch.par.firstcolumn = 'ignored'
    ptop = _mk(c, choptoTOP, 'pal_top')
    ptop.par.chop = pch.name
    ptop.par.dataformat = 'r'
    ptop.par.format = 'r32float'
    ptop.comment = 'Palette bank texture: width = entries, rows r g b L A B (palette_map layout). Cooks on change only.'
    bt = _mk(c, tableDAT, 'bn_table')
    if bt.numRows != 65 or bt.numCols != 64:
        rows = Lg['bn_table_rows'](Lg['void_and_cluster'](64))
        bt.clear()
        for r in rows:
            bt.appendRow(r)
    bt.comment = 'Blue noise 64x64 (void-and-cluster, fx_retro_logic.void_and_cluster, generated at build).'
    bch = _mk(c, dattoCHOP, 'bn_chop')
    bch.par.dat = bt.name
    bch.par.output = 'chanpercol'
    bch.par.firstrow = 'names'
    bch.par.firstcolumn = 'values'                        # 31550 default 'names' drops column 0 -> 64 x 63 (live)
    btop = _mk(c, choptoTOP, 'bn_top')
    btop.par.chop = bch.name
    btop.par.dataformat = 'r'
    btop.par.format = 'r32float'
    btop.comment = 'Blue-noise threshold texture 64x64: texel (x, y) = (rank + 0.5) / 4096.'
    ft = _mk(c, tableDAT, 'font_table')
    frows = Lg['font_table_rows']()
    if ft.numRows != len(frows) or ft[1, 0] is None or ft[1, 0].val != frows[1][0]:
        ft.clear()
        for r in frows:
            ft.appendRow(r)
    ft.comment = 'Font 8x8 as uint32 words split lo / hi 16 bits (fx_retro_logic.font_table_rows, from fx_retro_font8x8).'
    fch = _mk(c, dattoCHOP, 'font_chop')
    fch.par.dat = ft.name
    fch.par.output = 'chanpercol'
    fch.par.firstrow = 'names'
    fch.par.firstcolumn = 'values'
    ftop = _mk(c, choptoTOP, 'font_top')
    ftop.par.chop = fch.name
    ftop.par.dataformat = 'r'
    ftop.par.format = 'r32float'
    ftop.comment = 'Font texture (glyph / teletext / smalldisplay): width 2 x glyphs, row 0 lo, row 1 hi 16 bits.'


PAL_BANK_CB = """# pal_bank: rows hex r g b L A B of every palette (fx_retro_logic.bank_rows); recooks when pal_custom changes.
def onCook(scriptOp):
    L = op('fx_retro_logic').module
    rows = [[c.val for c in r] for r in op('pal_custom').rows()]
    good = L.PM.parse_hex_list(rows)[0]
    scriptOp.clear()
    for r in L.bank_rows(good):
        scriptOp.appendRow(r)
    return
"""


def _layout(c):
    names = plan_chain(_rows(c))
    chain = []
    for n in names:
        chain += [n, n + '_mix', n + '_slot']
    stages = [
        {'title': 'Rack', 'role': 'control', 'ops': ['slots'] + LOGIC_DATS,
         'body': 'slots: name module enabled order mix. enabled/mix live; add/remove/order = builder rewire.'},
        {'title': 'Shared data', 'role': 'process', 'ops': ['pal_custom', 'pal_bank', 'pal_bank_callbacks', 'pal_chop',
                                                            'pal_top', 'bn_table', 'bn_chop', 'bn_top', 'font_table',
                                                            'font_chop', 'font_top'],
         'body': 'Palette bank, blue noise and font textures, read by the modules through Select TOPs.'},
        {'title': '1 Input', 'role': 'input', 'ops': ['in1', 'test_clip', 'test_ramp', 'img_src'],
         'body': 'in1 TOP, the stored webcam clip or a black->white ramp (Input: auto = in1 when wired).'},
        {'title': '2 Slots', 'role': 'process', 'ops': [n for n in chain if c.op(n) is not None],
         'body': 'Per slot: module COMP -> _mix (Cross) -> _slot (Switch 0 bypass / 1 module / 2 mix).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['panic', 'out1'], 'body': 'Panic = instant passthrough of the rack.'},
    ]
    stages = [s for s in stages if s['ops']]
    return op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')


def build(parent_path='/project1/lab', panel=True, rows=None):
    Lg = load_logic()
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('FX_retro: retro machines rack (palette, dither, glyph, teletext, smalldisplay). In: in1 TOP. Out: '
                 'out1 TOP. Module slots from `slots` (builders/fx_retro.py add/remove/rewire). Panic = passthrough.')
    _pars(c, [('Rack', [
        ('Panic', 'Toggle', False, {'label': 'Panic (passthrough)'}),
        ('Input', 'Menu', 'auto', {'names': INPUTS, 'labels': ['Auto', 'Live (in1)', 'Test clip', 'Test ramp']}),
    ])])
    _shared(c, Lg)
    in1 = _mk(c, inTOP, 'in1')
    tc = _mk(c, moviefileinTOP, 'test_clip')
    tc.par.file = TEST_CLIP
    tc.par.outputresolution = 'custom'
    tc.par.resolutionw, tc.par.resolutionh = 1080, 1920
    tc.par.outputaspect = 'resolution'
    tc.par.fillmode = 'fill'
    tc.comment = 'Test picture: stored 5 s webcam clip, filled to 1080x1920 (cooks only while selected).'
    rp = _mk(c, rampTOP, 'test_ramp')
    rp.par.type = 'horizontal'
    rp.par.outputresolution = 'custom'
    rp.par.resolutionw, rp.par.resolutionh = 1080, 1920
    rp.comment = 'Test ramp (Input = Test ramp): black -> white left to right, for dither / palette checks.'
    img = _mk(c, switchTOP, 'img_src')
    img.inputConnectors[0].connect(tc)
    img.inputConnectors[1].connect(in1)
    img.inputConnectors[2].connect(rp)
    _expr(img.par.index, "(2 if parent().par.Input.eval() == 'ramp' else (1 if parent().par.Input.eval() == 'live' or ("
          "parent().par.Input.eval() == 'auto' and any(len(cn.connections) for cn in parent().inputConnectors "
          "if cn.inOP is not None and cn.inOP.name == 'in1')) else 0))")
    pn = _mk(c, switchTOP, 'panic')
    _expr(pn.par.index, '1 if parent().par.Panic.eval() else 0')
    pn.comment = 'Panic: 1 = img_src straight to out1 (same frame; slots stop cooking).'
    _mk(c, outTOP, 'out1')
    t = c.op('slots')
    if t is None:
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        for r in (rows or DEFAULT_ROWS):
            t.appendRow(r)
    t.comment = 'Rack state: one row per module instance. enabled 0/1, mix 0..1 act live; order -> rewire.'
    out = []
    for r in _rows(c):
        out.append(_instance(c, r['name'], r['module'], Lg, panel=panel and c.op(r['name']) is None))
    wires = rewire(c)
    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    lay = _layout(c)
    return {'comp': c.path, 'instances': out, 'wires_changed': wires, 'layout': str(lay)[:300]}


def add(comp_path, module, name=None, order=None, enabled=1, mix=1, panel=True):
    c = op(comp_path)
    rows = _rows(c)
    name = name or next_name(module, set(r['name'] for r in rows) | set(o.name for o in c.children))
    if order is None:
        order = int(max([float(r['order'] or 0) for r in rows] + [0])) + 1
    c.op('slots').appendRow([name, module, enabled, order, mix])
    info = _instance(c, name, module, load_logic(), panel=panel)
    wires = rewire(c)
    _layout(c)
    return {'added': name, 'instance': info, 'wires_changed': wires}


def remove(comp_path, name):
    c = op(comp_path)
    t = c.op('slots')
    if t.row(name) is not None:
        t.deleteRow(name)
    wires = rewire(c)                                     # re-route around it first, then remove its ops
    m = c.op(name)
    if m is not None:
        w = m.op('controls_window')
        if w is not None and w.isOpen:
            w.par.winclose.pulse()
    for n in (name + '_slot', name + '_mix', name):
        _sd(c.op(n))
    _layout(c)
    return {'removed': name, 'wires_changed': wires}
