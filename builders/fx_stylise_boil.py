# fx_stylise_boil - FX_stylise module 'boil' (FX7c 7C-01 line boil / animated on twos; Spider-Verse style limited
# animation). Template: docs/builds/fx_glitch.md "Module template" (rack = builders/fx_stylise.py). Doc:
# docs/builds/fx_stylise.md. Numpy mirror: builders/fx_stylise_boil_logic.py.
# The picture holds on Holdfps ticks (on twos / threes at 12 / 8 fps) while the rest of the show runs at 60; each tick
# re-rolls one of Boilframes noise seeds that displace the ink lines (and a share of the fill): outlines wobble and
# re-draw like hand-drawn frames. Passes:
#   stamp : 1x1 in place: x tick, y time the tick last changed (or first cook / > 0.25 s gap), z last cook
#   hold  : in place copy of in1 when stamp.y == now (Holdfps 0: not pulled, hsrc = in1)
#   fx    : boil offset (value noise, seed = tick mod Boilframes) -> Sobel ink lines of the held luma at Linewidth px,
#           fill (posterise / paper / picture / palette by luma), paper grain, ink colour, Amount mix with in1
# Amount 0 = in1 exact (out_sel). <= 3 GLSL TOP inputs (T-88). ASCII only.
import os

MODULE = 'boil'
FILLS = ['posterise', 'paper', 'picture', 'palette']

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']

PAGES = [
    ('Boil', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Holdfps', 'Float', 12.0, {'min': 0, 'max': 30, 'label': 'Hold fps (0 = no hold; 12 = on twos, 8 = threes)'}),
        ('Boil', 'Float', 2.5, {'min': 0, 'max': 16, 'label': 'Boil px (line wobble)'}),
        ('Boilscale', 'Float', 18.0, {'min': 2, 'max': 200, 'label': 'Boil noise scale px'}),
        ('Boilframes', 'Int', 3, {'min': 1, 'max': 8, 'label': 'Boil drawings (seeds cycled per tick)'}),
        ('Fillboil', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Boil share on the fill'}),
        ('Linewidth', 'Float', 1.5, {'min': 0.5, 'max': 8, 'label': 'Line width px (Sobel tap distance)'}),
        ('Edgethr', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Edge threshold'}),
        ('Edgesoft', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Edge softness'}),
        ('Inkamount', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Ink amount'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Fill', [
        ('Fill', 'Menu', 'posterise', {'names': FILLS, 'labels': [
            'Posterise (Levels)', 'Paper only (line art)', 'Picture', 'Palette by luma (Levels steps)']}),
        ('Levels', 'Int', 5, {'min': 2, 'max': 16, 'label': 'Levels'}),
        ('Inkr', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Ink R'}),
        ('Inkg', 'Float', 0.04, {'min': 0, 'max': 1, 'label': 'Ink G'}),
        ('Inkb', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Ink B'}),
        ('Paper', 'Float', 0.12, {'min': 0, 'max': 1, 'label': 'Paper grain'}),
        ('Grainscale', 'Float', 2.0, {'min': 1, 'max': 16, 'label': 'Grain px'}),
        ('Paperr', 'Float', 0.96, {'min': 0, 'max': 1, 'label': 'Paper R'}),
        ('Paperg', 'Float', 0.93, {'min': 0, 'max': 1, 'label': 'Paper G'}),
        ('Paperb', 'Float', 0.86, {'min': 0, 'max': 1, 'label': 'Paper B'}),
    ]),
    pal_page('neon_trio', 'gradient'),  # noqa: F821
]
PANEL_PAGES = ['Boil', 'Fill', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
_D['Palreverse'] = int(_D['Palreverse'])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'on twos', _p(Seed=1)),
    (2, 'sketch', _p(Fill=1, Holdfps=8.0, Boil=3.5, Linewidth=1.2, Edgethr=0.05, Paper=0.2, Seed=2)),
    (3, 'jittery ink', _p(Fill=2, Holdfps=12.0, Boil=6.0, Boilscale=10.0, Boilframes=2, Fillboil=0.0,
                          Linewidth=2.5, Inkamount=1.3, Paper=0.0, Seed=3)),
    (4, 'poster boil', _p(Fill=3, Levels=4, Holdfps=6.0, Boil=4.0, Fillboil=0.8, Linewidth=2.0, Inkr=0.0,
                          Inkg=0.0, Inkb=0.0, Palsource=PAL_SOURCE_NAMES.index('neon_trio'), Seed=4)),  # noqa: F821
    (5, 'smooth 60', _p(Holdfps=0.0, Boil=1.5, Boilscale=30.0, Boilframes=4, Levels=8, Paper=0.05, Seed=5)),
]

STAMP = """// boil stamp: 1x1 rgba32float in place. x tick, y time the tick last changed (first cook / > 0.25 s gap count as a
// change), z last cook time. hold copies in1 when y == now (twice in one frame = same copy).
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;   // now, tick, -, -
void main() {
    vec4 s = TDImageLoadOutput(0, ivec3(0));
    bool ch = s.z <= 0.0 || uT.y != s.x || uT.x - s.z > 0.25;
    TDImageStoreOutput(0, ivec3(0), vec4(uT.y, ch ? uT.x : s.y, uT.x, 0.0));
}
"""

HOLD = """// boil hold: in place (readwrite, clearoutputs off), = in1 at the last tick. in0 in1, in1 stamp.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uH;   // now, -, -, -
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    if (texelFetch(sTD2DInputs[1], ivec2(0), 0).y != uH.x) return;      // not a tick frame: keep the held picture
    TDImageStoreOutput(0, ivec3(p, 0), texelFetch(sTD2DInputs[0], p, 0));
}
"""

FX = """// boil fx (compute). in0 held picture (bilinear, hold), in1 live in1 (Amount mix). Boil offset o = Boil x (2 vnoise2
// - 1) at pc / Boilscale with seed = tick mod Boilframes; ink = Sobel of luma at pc + o, taps Linewidth px apart, g =
// |grad| / 4, line = smoothstep(Edgethr, Edgethr + Edgesoft, g); fill at pc + o x Fillboil.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, fill mode, levels, linewidth
uniform vec4 uB;   // boil px, boil scale px, boil seed, fillboil
uniform vec4 uC;   // edge thr, edge soft, ink amount, paper grain
uniform vec4 uD;   // ink r g b, grain px
uniform vec4 uE;   // paper r g b, seed
""" + GLSL_LIB + PAL_GLSL + """
vec2 isz2;
float L(vec2 q) { return luma(texture(sTD2DInputs[0], q / isz2).rgb); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[1], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[1], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    isz2 = vec2(textureSize(sTD2DInputs[0], 0));
    vec2 pc = vec2(p) + 0.5;
    uint sk = uint(uB.z);
    vec2 o = (2.0 * vnoise2(pc / max(uB.y, 1.0), sk) - 1.0) * uB.x;
    vec2 q = pc + o;
    float w = max(uA.w, 0.5);
    float tl = L(q + vec2(-w, w)), tc = L(q + vec2(0.0, w)), tr = L(q + vec2(w, w));
    float ml = L(q + vec2(-w, 0.0)), mr = L(q + vec2(w, 0.0));
    float bl = L(q + vec2(-w, -w)), bc = L(q + vec2(0.0, -w)), br = L(q + vec2(w, -w));
    float gx = (tr + 2.0 * mr + br) - (tl + 2.0 * ml + bl);
    float gy = (tl + 2.0 * tc + tr) - (bl + 2.0 * bc + br);
    float g = length(vec2(gx, gy)) * 0.25;
    float line = smoothstep(uC.x, uC.x + max(uC.y, 1e-4), g);
    vec4 f = texture(sTD2DInputs[0], (pc + o * uB.w) / isz2);
    int fm = int(uA.y + 0.5);
    float lv = max(uA.z - 1.0, 1.0);
    vec3 fill;
    if (fm == 0) fill = floor(f.rgb * lv + 0.5) / lv;
    else if (fm == 1) fill = uE.rgb;
    else if (fm == 2) fill = f.rgb;
    else fill = pxPal(floor(luma(f.rgb) * lv + 0.5) / lv);
    float gr = (hsh(ivec2(floor(pc / max(uD.w, 1.0))), uint(uE.w) + 7u) - 0.5) * uC.w;
    fill *= 1.0 + gr;
    vec3 o3 = mix(fill, uD.rgb, clamp(line * uC.z, 0.0, 1.0));
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(o3, c.a), uA.x));
}
"""

SHADERS = {'stamp': STAMP, 'hold': HOLD, 'fx': FX}
NIN = {'stamp': 0, 'hold': 2, 'fx': 2}             # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"
TICK = "math.floor(absTime.seconds * (%s if %s > 0 else 12.0))" % (P.format('Holdfps'), P.format('Holdfps'))
BSEED = "(%s %% max(1, int(%s))) + 1000 * int(%s)" % (TICK, P.format('Boilframes'), P.format('Seed'))


def uniforms():
    return {
        'stamp': [('uT', ['absTime.seconds', TICK, '0', '0'])],
        'hold': [('uH', ['absTime.seconds', '0', '0', '0'])],
        'fx': [('uA', [P.format('Amount'), 'parent().par.Fill.menuIndex', P.format('Levels'), P.format('Linewidth')]),
               ('uB', [P.format('Boil'), P.format('Boilscale'), BSEED, P.format('Fillboil')]),
               ('uC', [P.format('Edgethr'), P.format('Edgesoft'), P.format('Inkamount'), P.format('Paper')]),
               ('uD', [P.format('Inkr'), P.format('Inkg'), P.format('Inkb'), P.format('Grainscale')]),
               ('uE', [P.format('Paperr'), P.format('Paperg'), P.format('Paperb'), P.format('Seed')])],
    }


def build(m, H):
    """in1 -> stamp -> hold (in place) -> hsrc (Holdfps 0 = in1) -> fx (+ in1) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    st = H['pas'](m, 'stamp', STAMP, [], '1', '1', 'rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    H['uniforms'](st, U['stamp'])
    st.comment = 'Hold clock: x tick, y time of the last tick change (hold copies then), z last cook.'
    hd = H['pas'](m, 'hold', HOLD, [in1, st], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    hd.par.outputaccess = 'readwrite'
    hd.par.clearoutputs = False
    H['uniforms'](hd, U['hold'])
    hd.comment = 'Held picture (in place): copies in1 only on hold ticks.'
    hs = mk(m, switchTOP, 'hsrc')  # noqa: F821
    hs.inputConnectors[0].connect(in1)
    hs.inputConnectors[1].connect(hd)
    expr(hs.par.index, '1 if %s > 0 else 0' % P.format('Holdfps'))
    hs.comment = 'Holdfps 0 = live in1 (hold not pulled).'
    fx = H['pas'](m, 'fx', FX, [hs, in1], 'me.inputs[1].width', 'me.inputs[1].height', 'useinput')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'boil: noise-displaced Sobel ink + posterised / paper / palette fill + grain; seed per hold tick.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (stamp / hold / fx not pulled).'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Hold', 'role': 'process', 'ops': ['stamp', 'stamp_compute', 'hold', 'hold_compute', 'hsrc'],
         'body': 'Picture holds on Holdfps ticks (on twos / threes); stamp = tick clock.'},
        {'title': '3 Draw', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'Boiling ink lines (seed per tick) + fill + paper grain.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
