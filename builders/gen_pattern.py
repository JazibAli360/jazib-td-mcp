# gen_pattern builder - GEN_pattern: background -> a short chain of generator slots -> Panic -> out1.
# The lean rack of builders/fx_glitch.py (template: docs/builds/fx_glitch.md), copied, not abstracted, with a
# GENERATOR slot instead of an FX slot: every module is ONE compute GLSL pass whose network the rack builds itself
# (in1 -> fx -> out1 + a 2-op clock), so a module file is data only: pages, presets, uniforms and its GLSL function.
# Two kinds: 'gen' modules write gen(q, P, src, v, k) (pattern value v + palette coordinate k; the rack's shared
# Space / Colour / Blend code turns that into a picture over the slot's input), 'warp' modules write warp(P, c)
# (kaleido2 / droste / infzoom remap the slot's input, e.g. the generator before them in the chain).
# Shared here because ALL modules use it today (no-bloat rule): the Drive clock (BPM / beat CHOP / audio level on the
# rack, Speed / Beatevery / Beatgain / Audiogain on each module), Space + Colour pages (all 9 generators), hash / noise.
# Pure maths mirror: builders/gen_pattern_logic.py (expect() predicts any pixel from the uniforms read live).
# Doc + LIVE CHECKS: docs/builds/gen_pattern.md. Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/gen_pattern.py').read(), ns)
#   ns['build']('/project1/lab')                          # rack + 'truchet1' on first build; idempotent
#   ns['add']('/project1/lab/GEN_pattern', 'opart')        # opart1, wired last (zkit panel + presets)
#   ns['remove']('/project1/lab/GEN_pattern', 'opart1'); ns['rewire'](c) after editing order in `slots`
#   ns['freeze'](path_of_instance, t=1.0); ns['check'](path_of_instance); ns['unfreeze'](path_of_instance)
# T-70 safe (_sd = safe_destroy, windows closed before a remove); no functions in op storage (T-67). ASCII only.
import os

NAME = 'GEN_pattern'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
LOGIC_FILE = os.path.join(HERE, 'gen_pattern_logic.py')
PALMAP_FILE = os.path.join(HERE, 'palette_map_logic.py')        # W1-B shared palette (palette_convention.md)
PALGLSL_FILE = os.path.join(HERE, 'glsl', 'px_palette.glsl')
TEST_CLIP = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'
COLS = ['name', 'module', 'enabled', 'order', 'mix']
MODULES = ['truchet', 'opart', 'wallpaper', 'domainwarp', 'gyroid', 'cymatics', 'split', 'barcode', 'columns',
           'kaleido2', 'droste', 'infzoom', 'fireworks', 'bokeh', 'beams', 'moltenchrome', 'caustic']


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


def module_ns(module):
    """The module file's names (data + GLSL strings; loads outside TD too)."""
    ns = {}
    exec(open(os.path.join(HERE, 'gen_pattern_%s.py' % module)).read(), ns)
    return ns


# ------------------------------------------------------------------ shared pages (all modules / all generators)
PALETTES = ['duo', 'solid', 'rainbow', 'fire', 'ice', 'gold', 'neon', 'sunset']
PAL_LABELS = ['Duo (A -> B)', 'Solid A', 'Rainbow', 'Fire', 'Ice', 'Gold', 'Neon', 'Sunset']
BLENDS = ['replace', 'add', 'screen', 'multiply', 'difference', 'alpha']
BLEND_LABELS = ['Replace (bg colour)', 'Add', 'Screen', 'Multiply', 'Difference', 'Alpha out (premultiplied)']

DRIVE_PAGE = ('Drive', [
    ('Speed', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Speed (clock x)'}),
    ('Phase', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Phase (s added to the clock)'}),
    ('Audiospeed', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Audio -> speed'}),
    ('Audiogain', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Audio -> look'}),
    ('Beatevery', 'Float', 0.0, {'min': 0, 'max': 16, 'label': 'Step every N beats (0 off)'}),
    ('Beatgain', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Beat pulse gain'}),
    ('Beatdecay', 'Float', 0.25, {'min': 0.02, 'max': 2, 'label': 'Beat pulse decay s'}),
    ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
])
SPACE_PAGE = ('Space', [
    ('Scale', 'Float', 8.0, {'min': 0.5, 'max': 64, 'label': 'Scale (units per screen height)'}),
    ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate deg'}),
    ('Rotspeed', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Rotate deg/s'}),
    ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
    ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
    ('Driftx', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Drift x (units/s)'}),
    ('Drifty', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Drift y (units/s)'}),
])
COLOUR_PAGE = ('Colour', [
    ('Palette', 'Menu', 'duo', {'names': PALETTES, 'labels': PAL_LABELS}),
    ('Spread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Palette spread'}),
    ('Offset', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Palette offset'}),
    ('Huecycle', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Palette cycle /s'}),
    ('Colora', 'RGB', (1.0, 1.0, 1.0), {'label': 'Colour A'}),
    ('Colorb', 'RGB', (0.95, 0.7, 0.25), {'label': 'Colour B'}),
    ('Bgcolor', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background (Replace)'}),
    ('Blend', 'Menu', 'replace', {'names': BLENDS, 'labels': BLEND_LABELS}),
])

# uniform specs: {Par} value, {Par#} menu index, $t $step $age $level $W $H (see gen_pattern_logic.subst)
SHARED_UNIFORMS = {
    'gen': [('uAmt', ['{Amount}', '{Blend#}', '{Palette#}', '{Spread}']),
            ('uDrv', ['$t', '$step', '$age', '$level']),
            ('uBeat', ['{Beatgain}', '{Beatdecay}', '{Audiogain}', '{Seed}']),
            ('uSp', ['{Scale}', 'math.radians({Rotate})', '{Centerx} * $W', '{Centery} * $H']),
            ('uSp2', ['{Driftx}', '{Drifty}', 'math.radians({Rotspeed})', '0']),
            ('uCol', ['{Offset}', '{Huecycle}', '0', '0']),
            ('uCa', ['{Colorar}', '{Colorag}', '{Colorab}', '0']),
            ('uCb', ['{Colorbr}', '{Colorbg}', '{Colorbb}', '0']),
            ('uBg', ['{Bgcolorr}', '{Bgcolorg}', '{Bgcolorb}', '0'])],
    'warp': [('uAmt', ['{Amount}', '0', '0', '0']),
             ('uDrv', ['$t', '$step', '$age', '$level']),
             ('uBeat', ['{Beatgain}', '{Beatdecay}', '{Audiogain}', '{Seed}'])],
}


# W1-B shared palette (docs/builds/palette_convention.md), opt-in per module (M['PAL'] = True; the 12 first modules
# keep their shader text byte-identical): Colour page Palette gains 'Shared palette' (index 8 -> pxPal(k)), and a
# Palette page feeds the module's `pal` Script CHOP (uPal[16]) + uPalCtl (count, shift drive, mode, interp).
PAL_SRC = ['custom', 'neon_green', 'cyan_magenta', 'neon_trio', 'acid', 'magenta_inv', 'fire', 'px_ramp', 'rainbow',
           'pico8', 'sweetie16', 'endesga32', 'resurrect64', 'gameboy', 'cga0hi', 'solarized']
PAL_SRC_LABELS = ['Custom (Palcustom hex list)', 'Neon green', 'Cyan / magenta', 'Neon green / cyan / magenta',
                  'Acid', 'Magenta inversion', 'Fire', 'PX ramp (teal / orange)', 'Rainbow', 'PICO-8', 'Sweetie 16',
                  'Endesga 32',
                  'Resurrect 64', 'Game Boy', 'CGA', 'Solarized']
COLOUR_PAGE_PAL = ('Colour', [(('Palette', 'Menu', 'shared', {'names': PALETTES + ['shared'],
                                                              'labels': PAL_LABELS + ['Shared palette (Palette page)']})
                                if p[0] == 'Palette' else p) for p in COLOUR_PAGE[1]])
PALETTE_PAGE = ('Palette', [
    ('Palsource', 'Menu', 'rainbow', {'names': PAL_SRC, 'labels': PAL_SRC_LABELS}),
    ('Palcustom', 'Str', 'ff2a6d 05d9e8 f9c80e', {'label': 'Custom stops (hex or hex@pos, spaces)'}),
    ('Palmode', 'Menu', 'cycle', {'names': ['gradient', 'steps', 'cycle'],
                                  'labels': ['Gradient (positioned stops)', 'Steps (equal bands)',
                                             'Cycle (wraps, last -> first)']}),
    ('Palinterp', 'Menu', 'oklab', {'names': ['rgb', 'oklab'], 'labels': ['RGB', 'OKLab']}),
    ('Palreverse', 'Toggle', False, {'label': 'Reverse'}),
    ('Palshift', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Palette shift'}),
    ('Paldrive', 'Menu', 'manual', {'names': ['manual', 'bpm_step', 'bpm_cycle', 'audio'],
                                    'labels': ['Manual (Palshift)', 'BPM step (one stop every N beats)',
                                               'BPM cycle (full turn every N beats)', 'Audio level (continuous)']}),
    ('Palevery', 'Float', 4.0, {'min': 0.25, 'max': 32, 'label': 'Drive every N beats'}),
    ('Palgain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Audio -> shift'}),
])
# shift = Palshift + drive (palette_map_logic.pal_shift kinds manual / bpm_step / bpm_cycle / audio); the shader wraps
PAL_CTL_SPEC = ('uPalCtl', ['$palcount',
                            '{Palshift} + [0.0, math.floor($beats / max({Palevery}, 1e-3)) / max($palcount, 1.0), '
                            '$beats / max({Palevery}, 1e-3), {Palgain} * $level][int({Paldrive#})]',
                            '{Palmode#}', '{Palinterp#}'])


def shared_pages(kind, pal=False):
    if kind != 'gen':
        return [DRIVE_PAGE]
    return [DRIVE_PAGE, SPACE_PAGE] + ([COLOUR_PAGE_PAL, PALETTE_PAGE] if pal else [COLOUR_PAGE])


def m_pages(M):
    """Module page(s) + shared pages (+ hit state page) of module namespace M."""
    sp = shared_pages(M['KIND'], True) if M.get('PAL') else shared_pages(M['KIND'])   # 1-arg call kept: racks that
    return M['PAGES'] + sp + (hit_pages(M['HITS']) if M.get('HITS') else [])            # override it (gen_points)


def hit_pages(n):
    """Hit ring state (HITS modules): n stamps in module time (clock_int + Phase), next index. Written by the hit
    DATs; not on the panel."""
    return [('Hits', [('Hitnext', 'Int', 0, {'min': 0, 'max': 64, 'label': 'Next hit slot'})]
             + [('Hit%d' % i, 'Float', -1000.0, {'min': -1000, 'max': 1000, 'label': 'Hit %d time (s)' % i})
                for i in range(n)])]


def page_defaults(pages):
    """{Par: default} with RGB pars split into <name>r/g/b and menus as their index (preset / offline form)."""
    d = {}
    for _pg, pars in pages:
        for name, style, default, o in pars:
            if style == 'RGB':
                for ch, v in zip('rgb', default):
                    d[name + ch] = v
            elif style == 'Menu':
                d[name] = o['names'].index(default)
            elif style in ('Float', 'Int', 'Toggle'):
                d[name] = default
    return d


def module_pars(M, preset=None):
    """All par values of a module instance (module page + shared pages, DEFAULTS, then a preset's values)."""
    pages = m_pages(M)
    d = page_defaults(pages)
    menus = dict((p[0], p[3]['names']) for _pg, ps in pages for p in ps if p[1] == 'Menu')
    for src in (M.get('DEFAULTS', {}), preset or {}):
        for k, v in src.items():                         # menu values may be given by name
            d[k] = menus[k].index(v) if k in menus and isinstance(v, str) else v
    return d


def uniform_spec(M):
    return SHARED_UNIFORMS[M['KIND']] + M['UNIFORMS'] + ([PAL_CTL_SPEC] if M.get('PAL') else [])


# ------------------------------------------------------------------ GLSL (the logic file mirrors every line)
GLSL_COMMON = """
const float TAU = 6.283185307;
const float PI = 3.14159265;
float T; float STEP; float AGE; float ENV; float LEVEL; float PX; uint SEED; vec2 RES;
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float h2(ivec2 c, uint s) { return float(lb32(uint(c.x) * 1597334677u ^ lb32(uint(c.y) ^ (s * 2654435761u)))) * (1.0 / 4294967296.0); }
float h3(ivec3 c, uint s) { return h2(c.xy, s ^ lb32(uint(c.z) + 0x9e3779b9u)); }
float vnoise(vec2 x, uint s) {
    vec2 i = floor(x); vec2 f = x - i; f = f * f * (3.0 - 2.0 * f); ivec2 c = ivec2(i);
    float a = h2(c, s), b = h2(c + ivec2(1, 0), s), cc = h2(c + ivec2(0, 1), s), d = h2(c + ivec2(1, 1), s);
    return mix(mix(a, b, f.x), mix(cc, d, f.x), f.y);
}
float fbm(vec2 x, uint s, int oct) {
    float v = 0.0, a = 0.5, n = 0.0;
    for (int i = 0; i < 8; i++) {
        if (i >= oct) break;
        v += a * vnoise(x, s + uint(i)); n += a;
        x = vec2(0.8 * x.x - 0.6 * x.y, 0.6 * x.x + 0.8 * x.y) * 2.03 + vec2(17.1, 31.7);
        a *= 0.5;
    }
    return v / max(n, 1e-6);
}
float smooth01(float t) { t = clamp(t, 0.0, 1.0); return t * t * (3.0 - 2.0 * t); }
float stroke(float d, float w, float aa) { return clamp(0.5 + (w * 0.5 - d) / max(aa, 1e-9), 0.0, 1.0); }
float band(float u, float duty, float aa) { return clamp(0.5 + (duty * 0.5 - abs(fract(u) - 0.5)) / max(aa, 1e-9), 0.0, 1.0); }
vec2 rot2(vec2 v, float a) { float c = cos(a), s = sin(a); return vec2(c * v.x - s * v.y, s * v.x + c * v.y); }
float tri(float k) { return 1.0 - abs(fract(k * 0.5) * 2.0 - 1.0); }
float mirror1(float u) { return 1.0 - abs(1.0 - mod(u, 2.0)); }
void drive_globals(ivec2 isz) {
    RES = vec2(isz); T = uDrv.x; STEP = uDrv.y; AGE = uDrv.z;
    ENV = uBeat.x * exp(-uDrv.z / max(uBeat.y, 1e-3)); LEVEL = uBeat.z * uDrv.w; SEED = uint(int(uBeat.w));
}
"""

GLSL_GEN = """
const vec3 PA[6] = vec3[6](vec3(0.5, 0.5, 0.5), vec3(0.5, 0.5, 0.5), vec3(0.4, 0.6, 0.8), vec3(0.6, 0.45, 0.2), vec3(0.5, 0.5, 0.5), vec3(0.8, 0.5, 0.4));
const vec3 PB[6] = vec3[6](vec3(0.5, 0.5, 0.5), vec3(0.5, 0.5, 0.5), vec3(0.4, 0.4, 0.2), vec3(0.4, 0.35, 0.2), vec3(0.5, 0.5, 0.5), vec3(0.2, 0.4, 0.2));
const vec3 PC[6] = vec3[6](vec3(1.0, 1.0, 1.0), vec3(1.0, 0.7, 0.4), vec3(1.0, 1.0, 1.0), vec3(1.0, 1.0, 1.0), vec3(2.0, 1.0, 0.0), vec3(2.0, 1.0, 1.0));
const vec3 PD[6] = vec3[6](vec3(0.0, 0.33, 0.67), vec3(0.0, 0.15, 0.2), vec3(0.0, 0.05, 0.1), vec3(0.0, 0.05, 0.15), vec3(0.5, 0.2, 0.25), vec3(0.0, 0.25, 0.25));
vec3 pal(float k, int i) {
    if (i <= 0) return mix(uCa.rgb, uCb.rgb, tri(k));
    if (i == 1) return uCa.rgb;
    int j = min(i - 2, 5);
    return PA[j] + PB[j] * cos(TAU * (PC[j] * k + PD[j]));
}
vec2 space(vec2 P) {
    vec2 q = (P - uSp.zw) / RES.y;
    q = rot2(q, -(uSp.y + uSp2.z * T));
    return q * uSp.x + uSp2.xy * T;
}
vec4 compose(vec4 c, float v, float k) {
    float kk = k * uAmt.w + uCol.x + uCol.y * T;
    vec3 pc = pal(kk, int(uAmt.z + 0.5));
    float vc = clamp(v, 0.0, 1.0);
    int mode = int(uAmt.y + 0.5);
    vec3 fg = pc * vc;
    vec4 o;
    if (mode == 0) o = vec4(mix(uBg.rgb, pc, vc), 1.0);
    else if (mode == 1) o = vec4(c.rgb + fg, c.a);
    else if (mode == 2) o = vec4(1.0 - (1.0 - c.rgb) * (1.0 - fg), c.a);
    else if (mode == 3) o = vec4(c.rgb * mix(vec3(1.0), pc, vc), c.a);
    else if (mode == 4) o = vec4(abs(c.rgb - fg), c.a);
    else o = vec4(fg, vc);
    return mix(c, o, uAmt.x);
}
"""

MAIN = {
    'gen': """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uAmt.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    drive_globals(isz);
    PX = uSp.x / RES.y;
    vec2 P = vec2(p) + 0.5;
    float v = 0.0, k = 0.0;
    gen(space(P), P, c, v, k);
    TDImageStoreOutput(0, ivec3(p, 0), compose(c, v, k));
}
""",
    'warp': """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uAmt.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    drive_globals(isz);
    PX = 1.0 / RES.y;
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, warp(vec2(p) + 0.5, c), uAmt.x));
}
""",
}


PAL_HOOK = '    if (i == 1) return uCa.rgb;'   # PAL modules get the pxPal line after it (GLSL_GEN itself is unchanged:
                                                 # gen_points cuts pal() out of it, T-171 (2))


def shader(M):
    """The full compute shader of module namespace M (also compiled offline by test_gen_pattern with glslc).
    PAL modules: px_palette.glsl (declares uPal[16] + uPalCtl) before the shared code, pal() index >= 8 = pxPal."""
    pal = bool(M.get('PAL'))
    decl = ''.join('uniform vec4 %s;\n' % n for n, _e in uniform_spec(M) if not (pal and n == 'uPalCtl'))
    head = '// GEN_pattern %s (%s, compute; builders/gen_pattern.py + gen_pattern_%s.py)\n' % (
        M['MODULE'], M['KIND'], M['MODULE'])
    gen = GLSL_GEN.replace(PAL_HOOK, PAL_HOOK + '\n    if (i >= 8) return pxPal(k);') if pal else GLSL_GEN
    return (head + 'layout (local_size_x = 8, local_size_y = 8) in;\n' + decl
            + (open(PALGLSL_FILE).read() + '\n' if pal else '') + GLSL_COMMON
            + (gen if M['KIND'] == 'gen' else '') + M['GLSL'] + MAIN[M['KIND']])


# ------------------------------------------------------------------ TD expressions for the uniform tokens
D_OP = "parent(2).op('drive')"
E_PAR = "parent().par.Beatevery.eval()"
TOKENS = {
    't': "(float(op('clock_int')[0]) + parent().par.Phase.eval())",
    'step': "(math.floor(float({D}['beats']) / {E}) if {E} > 0 else 0.0)".format(D=D_OP, E=E_PAR),
    'age': ("((float({D}['beats']) - math.floor(float({D}['beats']) / {E}) * {E}) * 60.0 / max(float({D}['bpm']), 1.0)"
            " if {E} > 0 else 1000.0)").format(D=D_OP, E=E_PAR),
    'level': "float({D}['level'])".format(D=D_OP),
    'beats': "float({D}['beats'])".format(D=D_OP),
    'bpm': "float({D}['bpm'])".format(D=D_OP),
    'palcount': "float(len(op('pal_callbacks').module.stops(parent())))",
    'W': 'me.par.resolutionw.eval()',     # never me.width on the op itself (T-117 (2) cook loop)
    'H': 'me.par.resolutionh.eval()',
}


def td_expr(e):
    L = _logic()
    return L['subst'](str(e), lambda n, idx: ('parent().par.%s.menuIndex' if idx else 'float(parent().par.%s.eval())') % n,
                      lambda k: TOKENS[k])


_LOGIC = {}


def _logic():
    if not _LOGIC:
        ns = {}
        exec(open(LOGIC_FILE).read(), ns)
        _LOGIC.update(ns)
    return _LOGIC


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


def _refresh_menu(p, o):
    """Existing menu par whose names / labels differ from the spec: replace them, keep the value when it is still a
    valid name (T-190: idempotent builds skipped existing pars, so instances built before a menu grew kept the old
    menu and a preset's menu index fell on the wrong entry). Returns True when the menu changed."""
    if p is None or list(p.menuNames) == list(o['names']) and list(p.menuLabels) == list(o['labels']):
        return False
    v0 = p.eval()
    p.menuNames, p.menuLabels = o['names'], o['labels']
    if v0 in o['names']:
        p.val = v0
    return True


def _pars(c, pages, defaults=None):
    defaults = defaults or {}
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None or getattr(c.par, name + 'r', None) is not None:
                if style == 'Menu':                         # T-190: a menu that grew reaches old instances too
                    _refresh_menu(getattr(c.par, name, None), o)
                continue
            label = o.get('label', name)
            if style == 'RGB':
                for p, ch in zip(page.appendRGB(name, label=label), 'rgb'):
                    p.default = p.val = defaults.get(name + ch, default['rgb'.index(ch)])
                continue
            if style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
                dv = defaults.get(name, default)
                dv = o['names'][dv] if isinstance(dv, int) else dv
            else:
                if style == 'Float':
                    p = page.appendFloat(name, label=label)[0]
                elif style == 'Int':
                    p = page.appendInt(name, label=label)[0]
                elif style == 'Toggle':
                    p = page.appendToggle(name, label=label)[0]
                elif style == 'Str':
                    p = page.appendStr(name, label=label)[0]
                else:                                           # 'TOP' / 'CHOP' op references
                    p = getattr(page, 'append' + style)(name, label=label)[0]
                if style in ('Float', 'Int'):
                    p.normMin, p.normMax = o['min'], o['max']      # slider range only, no clamps (no limits)
                dv = defaults.get(name, default)
            p.default = dv
            p.val = dv


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


def _const_chop(c, name, chans):
    """Constant CHOP with named channels driven by expressions [(chan, expr)]."""
    ch = _mk(c, constantCHOP, name)
    ch.seq.const.numBlocks = max(len(chans), 1)
    for i, (cn, e) in enumerate(chans):
        getattr(ch.par, 'const%dname' % i).val = cn
        _expr(getattr(ch.par, 'const%dvalue' % i), e)
    return ch


def _module_network(m, M):
    """in1 -> fx (compute GLSL, docked fx_compute) -> out1; clock (rate) -> clock_int (Speed CHOP) = module time."""
    in1 = _mk(m, inTOP, 'in1')
    clk = _const_chop(m, 'clock', [('rate', "parent().par.Speed.eval() * (1.0 + parent().par.Audiospeed.eval() * "
                                            "float(parent(2).op('drive')['level']))")])
    clk.comment = 'Module clock rate = Speed x (1 + Audiospeed x rack level); integrated by clock_int.'
    ci = _mk(m, speedCHOP, 'clock_int')
    ci.inputConnectors[0].connect(clk)
    ci.comment = 'Module time (s, Speed-scaled, no jump when Speed changes). freeze() resets it to 0.'
    g = _mk(m, glslTOP, 'fx')
    d = m.op('fx_compute')
    if d is None:
        d = _mk(m, textDAT, 'fx_compute')
    d.text = shader(M)
    d.dock = g
    for extra in ('fx_pixel', 'fx_info', 'fx_compute1', 'fx_vertex'):   # TD's own template DATs (T-115 (5))
        _sd(m.op(extra))
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, 'me.inputs[0].width')
    _expr(g.par.resolutionh, 'me.inputs[0].height')
    g.par.format = 'useinput'
    g.par.inputextenduv = 'hold'                    # warps fold uv themselves; hold = clamp like the mirror
    g.par.inputfiltertype = 'linear'                 # texture() = bilinear (gen_pattern_logic.bilinear)
    g.inputConnectors[0].connect(in1)
    spec = uniform_spec(M)
    g.seq.vec.numBlocks = max(len(spec), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(spec):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), td_expr(e))
    g.comment = 'GEN_pattern %s (%s): one compute pass; Amount 0 = exact passthrough of in1.' % (M['MODULE'], M['KIND'])
    out1 = _mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    extra = []
    if M.get('PAL'):
        extra.append(_palette_ops(m, g))
    if M.get('HITS'):
        extra.append(_hit_ops(m, int(M['HITS'])))
    return extra + [
        {'title': '1 In + clock', 'role': 'input', 'ops': ['in1', 'clock', 'clock_int'],
         'body': 'in1 = the slot input (background or the slot before). clock_int = module time.'},
        {'title': '2 %s' % M['MODULE'], 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': M.get('BLURB', 'One compute pass.')},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]


PAL_CB = """# pal_callbacks: GEN_pattern shared palette (W1-B, docs/builds/palette_convention.md). Palette page ->
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


def _palette_ops(m, g):
    """palmap (palette_map_logic text) + pal (Script CHOP, pal_callbacks) -> fx Arrays block uPal (vec4,
    uniformarray). uPalCtl is a normal uniform of the spec (PAL_CTL_SPEC)."""
    pm = m.op('palmap') or _mk(m, textDAT, 'palmap')
    txt = open(PALMAP_FILE).read()
    if pm.text != txt:
        pm.text = txt
    pm.comment = 'palette_map_logic (builders/palette_map_logic.py): stops, pal_rows, cook_chop.'
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
    return {'title': 'Palette', 'role': 'control', 'ops': ['palmap', 'pal_callbacks', 'pal'],
            'body': 'Shared palette (Palette page) -> pal CHOP -> uPal[16] on fx.'}


HIT_CODE = """
N = %d
def _now(c):
    return float(c.op('clock_int')[0]) + float(c.par.Phase.eval())

def _fire(c):
    now = _now(c)
    n = N
    s = getattr(c.par, 'Shells', None)
    if s is not None:
        n = max(1, min(N, int(s.eval())))
    for j in range(N):
        p = getattr(c.par, 'Hit%%d' %% j)
        if float(p.eval()) > now + 0.05:
            p.val = -1000.0            # a stamp from another clock (relaunch / freeze), T-162
    i = int(c.par.Hitnext.eval()) %% n
    getattr(c.par, 'Hit%%d' %% i).val = now
    c.par.Hitnext.val = (i + 1) %% n

def _clear(c):
    for j in range(N):
        getattr(c.par, 'Hit%%d' %% j).val = -1000.0
    c.par.Hitnext.val = 0
"""
HIT_PEXEC = ("# hit_pexec: Hit pulse -> stamp module time into the next Hit<i> (ring of Shells); Clear -> all off."
             + HIT_CODE + """
def onPulse(par):
    if par.name == 'Hit':
        _fire(par.owner)
    elif par.name == 'Clear':
        _clear(par.owner)
    return
""")
HIT_CHOPEXEC = ("# hit_chopexec: Hitchop channel Hitchan rising edge (e.g. AC_audio/out_ctl kick) -> a hit (no limiter)."
                + HIT_CODE + """
def onOffToOn(channel, sampleIndex, val, prev):
    c = parent()
    if channel.name == str(c.par.Hitchan.eval()):
        _fire(c)
    return
""")


def _hit_ops(m, n):
    """Hit ring (HITS modules): Hit pulse / Clear (hit_pexec) and a CHOP rising edge (hit_chopexec) write module-time
    stamps into Hit0..Hit<n-1> (Hits page); the shader voids stamps later than now (T-162)."""
    pe = m.op('hit_pexec') or _mk(m, parameterexecuteDAT, 'hit_pexec')
    t = HIT_PEXEC % n
    if pe.text != t:
        pe.text = t
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Hit Clear'
    if getattr(pe.par, 'onpulse', None) is not None:
        pe.par.onpulse = True
    pe.par.valuechange = False
    pe.par.active = False
    pe.par.active = True                                   # recompile after the text change (T-113 (3))
    pe.comment = 'Hit / Clear pulses -> Hit<i> stamps (module time).'
    ce = m.op('hit_chopexec') or _mk(m, chopexecuteDAT, 'hit_chopexec')
    t = HIT_CHOPEXEC % n
    if ce.text != t:
        ce.text = t
    _expr(ce.par.chop, "parent().par.Hitchop.eval().path if parent().par.Hitchop.eval() is not None else ''")
    _expr(ce.par.active, "parent().par.Hitchop.eval() is not None")
    ce.par.offtoon = True
    ce.par.valuechange = False
    ce.comment = 'Hitchop / Hitchan rising edge -> a hit (Launch page).'
    return {'title': 'Hits', 'role': 'control', 'ops': ['hit_pexec', 'hit_chopexec'],
            'body': 'Hit pulse / Hitchop rising edge -> Hit<i> stamps; Clear.'}


# slot_gate (T-198 for every rack; same block as builders/fx_glitch.py, the two racks share no code): a Switch TOP in each module COMP right before out1: 0 = in1 (exact passthrough,
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
        hm.layout_stages(m, stages, plan.get('colors', True), arrange=plan.get('arrange') or module_arrange(m))
    return {'name': name, 'gated': g is not None, 'new': g is not None and not had,
            'index': int(g.par.index.eval()) if g is not None else None}



def _instance(c, name, module, panel=True):
    M = module_ns(module)
    m = c.op(name)
    if m is None or not m.isCOMP:
        m = _mk(c, baseCOMP, name)
    m.allowCooking = True
    pages = m_pages(M)
    _pars(m, pages, module_pars(M))
    m.comment = 'GEN_pattern module %s (%s). Pars on its pages; pulse Opencontrols for the zkit panel.' % (name, module)
    stages = _slot_gate(m, _module_network(m, M))
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
            for slot, pname, vals in M['PRESETS']:          # full state (defaults + preset): recall never
                pt.appendRow([slot, pname, L.DEFAULT_COLOR, L.preset_dump(module_pars(M, vals))])  # inherits

        stages = [{'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window']}] + stages
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if m.op(n) is not None]
    op('/jazib_mcp/handlers').module.layout_stages(m, [s_ for s_ in stages if s_['ops']], True,
                                                   arrange=module_arrange(m))
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
        d.inputConnectors[i].connect(s.outputConnectors[0])   # a COMP source needs its connector (T-111 (2))
        changed += 1
    return changed


def _layout(c):
    names = plan_chain(_rows(c))
    chain = []
    for n in names:
        chain += [n, n + '_mix', n + '_slot']
    stages = [
        {'title': 'Rack', 'role': 'control', 'ops': ['slots', 'drive_pexec'],
         'body': 'slots: name module enabled order mix. enabled/mix live; add/remove/order = builder rewire.'},
        {'title': '0 Drive', 'role': 'input', 'ops': ['drive_rate', 'drive_beats', 'drive'],
         'body': 'drive: beats (internal Bpm clock or a beat CHOP), bpm, level (audio CHOP channel).'},
        {'title': '1 Background', 'role': 'input', 'ops': ['bg', 'in1', 'test_clip', 'img_src'],
         'body': 'Input: auto (in1 if wired, else black bg) / black / live / test clip.'},
        {'title': '2 Slots', 'role': 'process', 'ops': [n for n in chain if c.op(n) is not None],
         'body': 'Per slot: module COMP -> _mix (Cross) -> _slot (Switch 0 bypass / 1 module / 2 mix).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['panic', 'out1'], 'body': 'Panic = the background straight out.'},
    ]
    stages = [dict(s, ops=[n for n in s['ops'] if c.op(n) is not None]) for s in stages]
    return op('/jazib_mcp/handlers').module.layout_stages(c, [s for s in stages if s['ops']], True, arrange='mixed')


def _chan(chop_par, chan_par, fallback):
    """Expression: float of channel `chan_par` of CHOP `chop_par` (rack pars), else `fallback`."""
    return ("(lambda c, n: float(c[n]) if c is not None and n and c[n] is not None else {f})"
            "(parent().par.{c}.eval(), parent().par.{n}.eval())").format(c=chop_par, n=chan_par, f=fallback)


def _drive(c):
    bpm = ("(lambda b: b if b > 0 else parent().par.Bpm.eval())(%s)" % _chan('Bpmchop', 'Bpmchan', '0.0'))
    _const_chop(c, 'drive_rate', [('rate', '%s / 60.0' % bpm)]).comment = 'Internal beat rate (beats/s) = Bpm / 60.'
    db = _mk(c, speedCHOP, 'drive_beats')
    db.inputConnectors[0].connect(c.op('drive_rate'))
    db.comment = 'Internal beat counter (beats since start / Resync).'
    internal = "float(op('drive_beats')[0])"
    ext = ("(lambda ch, pn, cn: float(ch[cn]) + float(ch[pn]) if ch is not None and ch[pn] is not None and "
           "ch[cn] is not None else {i})(parent().par.Beatchop.eval(), parent().par.Phasechan.eval(), "
           "parent().par.Countchan.eval())").format(i=internal)
    dr = _const_chop(c, 'drive', [
        ('beats', "(%s if parent().par.Beatsource.eval() == 'chop' else %s)" % (ext, internal)),
        ('bpm', bpm),
        ('level', _chan('Audiochop', 'Audiochan', '0.0')),
    ])
    dr.comment = 'Rack drive read by every module: beats, bpm, level.'
    pe = c.op('drive_pexec')
    if pe is None:
        pe = _mk(c, parameterexecuteDAT, 'drive_pexec')
    pe.text = ("def onPulse(par):\n    if par.name == 'Resync':\n"
               "        op('drive_beats').par.resetpulse.pulse()\n    return\n")
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Resync'
    if getattr(pe.par, 'onpulse', None) is not None:
        pe.par.onpulse = True
    pe.par.active = False
    pe.par.active = True                                   # recompile after the text change (T-113 (3))
    pe.comment = 'Resync pulse -> beat counter back to 0 (beat 1 = now).'


def build(parent_path='/project1/lab', panel=True, first='truchet'):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('GEN_pattern: one-pass generator rack. In: in1 TOP (optional background). Out: out1 TOP. Slots '
                 'from `slots` (builders/gen_pattern.py add/remove/rewire). Panic = background straight out.')
    _pars(c, [('Rack', [
        ('Panic', 'Toggle', False, {'label': 'Panic (background only)'}),
        ('Input', 'Menu', 'auto', {'names': ['auto', 'black', 'live', 'test'],
                                   'labels': ['Auto (in1 if wired)', 'Black', 'Live (in1)', 'Test clip']}),
        ('Resw', 'Int', 1080, {'min': 64, 'max': 4096, 'label': 'Width'}),
        ('Resh', 'Int', 1920, {'min': 64, 'max': 4096, 'label': 'Height'}),
    ]), ('Drive', [
        ('Beatsource', 'Menu', 'internal', {'names': ['internal', 'chop'],
                                            'labels': ['Internal (Bpm)', 'Beat CHOP (count + phase)']}),
        ('Bpm', 'Float', 120.0, {'min': 40, 'max': 200, 'label': 'Bpm'}),
        ('Bpmchop', 'CHOP', '', {'label': 'Bpm CHOP (e.g. AU_features/out1)'}),
        ('Bpmchan', 'Str', 'bpm', {'label': 'Bpm channel'}),
        ('Beatchop', 'CHOP', '', {'label': 'Beat CHOP (e.g. AU_features/out1)'}),
        ('Phasechan', 'Str', 'beat_phase', {'label': 'Beat phase channel'}),
        ('Countchan', 'Str', 'beat_count', {'label': 'Beat count channel'}),
        ('Audiochop', 'CHOP', '', {'label': 'Audio CHOP (e.g. AC_audio/out_ctl)'}),
        ('Audiochan', 'Str', 'low', {'label': 'Audio channel'}),
        ('Resync', 'Pulse', None, {'label': 'Resync (beat 1 now)'}),
    ])])
    _drive(c)
    bg = _mk(c, constantTOP, 'bg')
    bg.par.colorr = bg.par.colorg = bg.par.colorb = 0
    bg.par.alpha = 1
    bg.par.outputresolution = 'custom'
    _expr(bg.par.resolutionw, 'parent().par.Resw.eval()')
    _expr(bg.par.resolutionh, 'parent().par.Resh.eval()')
    bg.par.format = 'rgba8fixed'
    bg.comment = 'Black background at Resw x Resh (static: cooks once).'
    in1 = _mk(c, inTOP, 'in1')
    tc = _mk(c, moviefileinTOP, 'test_clip')
    tc.par.file = TEST_CLIP
    tc.par.outputresolution = 'custom'
    _expr(tc.par.resolutionw, 'parent().par.Resw.eval()')
    _expr(tc.par.resolutionh, 'parent().par.Resh.eval()')
    tc.par.outputaspect = 'resolution'
    tc.par.fillmode = 'fill'
    tc.comment = 'Test picture: stored 5 s webcam clip (cooks only while selected).'
    img = _mk(c, switchTOP, 'img_src')
    img.inputConnectors[0].connect(bg)
    img.inputConnectors[1].connect(in1)
    img.inputConnectors[2].connect(tc)
    _expr(img.par.index, "(lambda m, w: 1 if m == 'live' or (m == 'auto' and w) else (2 if m == 'test' else 0))("
          "parent().par.Input.eval(), any(len(cn.connections) for cn in parent().inputConnectors "
          "if cn.inOP is not None and cn.inOP.name == 'in1'))")
    pn = _mk(c, switchTOP, 'panic')
    _expr(pn.par.index, '1 if parent().par.Panic.eval() else 0')
    pn.comment = 'Panic: 1 = background straight to out1 (same frame; slots stop cooking).'
    _mk(c, outTOP, 'out1')
    t = c.op('slots')
    if t is None:
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        t.appendRow([first + '1', first, 1, 1, 1])
    t.comment = 'Rack state: one row per module instance. enabled 0/1, mix 0..1 act live; order -> rewire.'
    out = []
    for r in _rows(c):
        out.append(_instance(c, r['name'], r['module'], panel=panel and c.op(r['name']) is None))
    wires = rewire(c)
    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    lay = _layout(c)
    return {'comp': c.path, 'instances': out, 'wires_changed': wires, 'layout': str(lay)[:300]}


def module_arrange(m):
    """Stage arrange for a module COMP: 'rows' when it holds a Feedback TOP loop ('mixed' pulls the out stage under the
    loop stage there: box overlaps, intruders), else 'mixed' (T-163)."""
    kids = getattr(m, 'children', None) or []
    return 'rows' if any(getattr(o, 'OPType', '') == 'feedbackTOP' for o in kids) else 'mixed'


def add(comp_path, module, name=None, order=None, enabled=1, mix=1, panel=True):
    if module not in MODULES:
        raise ValueError('unknown module %r (have %s)' % (module, ', '.join(MODULES)))
    c = op(comp_path)
    rows = _rows(c)
    name = name or next_name(module, set(r['name'] for r in rows) | set(o.name for o in c.children))
    if order is None:
        order = int(max([float(r['order'] or 0) for r in rows] + [0])) + 1
    c.op('slots').appendRow([name, module, enabled, order, mix])
    info = _instance(c, name, module, panel=panel)
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


def preset(inst_path, slot):
    """Apply module preset `slot` straight to the instance pars (same values zkit Recall sets): the FULL state
    (defaults + the preset's values), so a preset never inherits pars from the one before (live, 26 Oct)."""
    m = op(inst_path)
    M = module_ns(m.parent().op('slots')[m.name, 'module'].val)
    vals = module_pars(M, next(v for s, _n, v in M['PRESETS'] if s == slot))
    for k, v in vals.items():
        p = getattr(m.par, k, None)
        if p is None:
            continue
        if p.isMenu:
            p.menuIndex = int(v)
        else:
            p.val = v
    return {'preset': slot, 'set': len(vals)}


# ------------------------------------------------------------------ live checks (docs/builds/gen_pattern.md)
def check_state(module):
    """(t, beats) a live check freezes at: the module's CHECK dict, else t 1 s, beats 0 (doc tables use the same)."""
    st = module_ns(module).get('CHECK', {})
    return st.get('t', 1.0), st.get('beats', 0.0)


def check_pars(module):
    """Extra par values a live check freezes with (CHECK['pars'], e.g. fireworks hit stamps); {} for most modules."""
    return dict(module_ns(module).get('CHECK', {}).get('pars', {}))


def freeze(inst_path, t=None, beats=None):
    """Deterministic state for a pixel check: module time = t (clock reset to 0, Phase = t), rack beats = `beats`
    (Speed CHOP reset value; Bpm 0 so it holds; age = frac(beats) x 60 s), no audio, test clip paused. Defaults:
    check_state(module). Old values kept in op storage (plain dicts, T-67); unfreeze() restores them. Read >= 3 frames
    later, in another exec (T-116 (4))."""
    m = op(inst_path)
    c = m.parent()
    module = c.op('slots')[m.name, 'module'].val
    t0, b0 = check_state(module)
    t = t0 if t is None else t
    beats = b0 if beats is None else beats
    cp = check_pars(module)                                      # e.g. fireworks hit stamps
    st = {'Speed': m.par.Speed.eval(), 'Phase': m.par.Phase.eval()}
    st.update(dict((k, getattr(m.par, k).eval()) for k in cp))
    m.store('gp_frozen', st)
    for k, v in cp.items():
        getattr(m.par, k).val = v
    path = lambda o_: o_.path if o_ is not None else ''
    c.store('gp_frozen', {'Bpm': c.par.Bpm.eval(), 'Beatsource': c.par.Beatsource.eval(),
                          'Audiochop': path(c.par.Audiochop.eval()), 'Bpmchop': path(c.par.Bpmchop.eval()),
                          'play': int(c.op('test_clip').par.play.eval())})
    m.par.Speed = 0
    m.par.Phase = t
    m.op('clock_int').par.resetvalue = 0
    m.op('clock_int').par.resetpulse.pulse()
    c.par.Bpm = 0
    c.par.Bpmchop = ''
    c.par.Beatsource = 'internal'
    c.par.Audiochop = ''
    c.op('test_clip').par.play = 0
    c.op('drive_beats').par.resetvalue = beats
    c.op('drive_beats').par.resetpulse.pulse()
    return {'frozen': inst_path, 't': t, 'beats': beats}


def unfreeze(inst_path):
    m = op(inst_path)
    c = m.parent()
    mk = tuple((m.fetch('gp_frozen', None, search=False) or {}).keys())
    for o_, keys in ((m, mk), (c, ('Bpm', 'Beatsource', 'Audiochop', 'Bpmchop'))):
        st = o_.fetch('gp_frozen', None, search=False) or {}
        for k in keys:
            if k in st:
                setattr(o_.par, k, st[k])
    st = c.fetch('gp_frozen', None, search=False) or {}
    if 'play' in st:
        c.op('test_clip').par.play = st['play']
    c.op('drive_beats').par.resetvalue = 0
    return {'unfrozen': inst_path}


def read_uniforms(g):
    U = {}
    for k in range(g.seq.vec.numBlocks):
        n = getattr(g.par, 'vec%dname' % k).eval()
        if n:
            U[n] = tuple(float(getattr(g.par, 'vec%dvalue%s' % (k, ch)).eval()) for ch in 'xyzw')
    for k in range(g.seq.array.numBlocks):                 # uPal (PAL modules): CHOP samples as rows r g b pos
        n = getattr(g.par, 'array%dname' % k).eval()
        ch = getattr(g.par, 'array%dchop' % k).eval()
        if n and ch is not None:
            U[n] = [[float(ch[cn][i]) for cn in ('r', 'g', 'b', 'pos')] for i in range(ch.numSamples)]
    return U


def check(inst_path, n=300, seed=7, tol=3.0 / 255.0, pts=None):
    """Compare out1 with gen_pattern_logic.expect at n random pixels (uniforms read from fx). Run in an exec of its
    own after freeze() (T-116 (4) / T-117 (4)). Tries both numpy row orders and reports the better one."""
    import random
    L = _logic()
    m = op(inst_path)
    module = m.parent().op('slots')[m.name, 'module'].val
    g = m.op('fx')
    U = read_uniforms(g)
    out = m.op('out1').numpyArray(delayed=False)
    src = m.op('in1').numpyArray(delayed=False)
    H, W = out.shape[0], out.shape[1]
    rnd = random.Random(seed)
    pts = pts or [(rnd.randrange(W), rnd.randrange(H)) for _ in range(n)]
    n = len(pts)
    best = None
    for flip in (False, True):
        o_ = out[::-1] if flip else out
        s_ = src[::-1] if flip else src
        diffs, lit = [], []
        for x, y in pts:
            e = L['expect'](module, U, x, y, W, H, s_)
            d = max(abs(float(o_[y][x][ch]) - e[ch]) for ch in range(4))
            diffs.append(d)
            if L['luma'](e) > 0.02:                       # sparse looks (fireworks): the lit pixels alone
                lit.append(d)
        diffs.sort()
        r = {'flip_rows': flip, 'n': n, 'max': round(diffs[-1], 4), 'p95': round(diffs[int(0.95 * (n - 1))], 4),
             'median': round(diffs[n // 2], 5), 'within_tol': round(sum(d <= tol for d in diffs) / float(n), 4),
             'lit_n': len(lit), 'lit_within_tol': round(sum(d <= tol for d in lit) / float(max(len(lit), 1)), 4)}
        if best is None or r['within_tol'] > best['within_tol']:
            best = r
    best.update({'module': module, 'W': W, 'H': H, 'uniforms': dict((k, [round(x, 5) for x in v]) for k, v in U.items() if k != 'uPal')})
    return best


def stats(inst_path, n=1000, seed=7, flip_rows=False):
    """Mean rgb + share of lit pixels (luma > 0.5) of out1 at gen_pattern_logic.sample_points (TD pixel coords, y up;
    pass the flip_rows that check() reported); compare with the expected table in docs/builds/gen_pattern.md."""
    L = _logic()
    a = op(inst_path).op('out1').numpyArray(delayed=False)
    a = a[::-1] if flip_rows else a
    H, W = a.shape[0], a.shape[1]
    return L['stats']([[float(v) for v in a[y][x]] for x, y in L['sample_points'](W, H, n, seed)])
