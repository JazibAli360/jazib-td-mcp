# fx_stylise_watercolour - FX_stylise module 'watercolour' (FX7c 7C-02: bleeding pigment, darkened wet edges, paper
# granulation, soft white gaps; KinoAqua / flockaroo-style gradient-guided smear and Arena "Acuarela" as references,
# clean-room). Template: docs/builds/fx_glitch.md "Module template" (rack = builders/fx_stylise.py). Doc:
# docs/builds/fx_stylise.md. Mirror: builders/fx_stylise_watercolour_logic.py.
# Passes (compute):
#   wash : at Res (half by default): luma gradient at the texel -> direction (Bleed: across edges / Flow: along them)
#          bent by value noise (Wobble); Taps bilinear samples of in1 over +- Spread px along it, tent weights
#   look : full res: bilinear wash, wet-edge darkening (luma gradient of the wash x Edgedark), pigment density noise
#          (Pigment at Pigmentscale), paper granulation (2-octave noise, Granulation), whites to paper above
#          Whitethr, colour = wash or palette by luma; Amount mix with in1
# Amount 0 = in1 exact (out_sel). <= 3 GLSL TOP inputs (T-88). ASCII only.
import os

MODULE = 'watercolour'
TAPS = 16

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']

PAGES = [
    ('Watercolour', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Flow', 'Menu', 'bleed', {'names': ['bleed', 'flow'], 'labels': ['Bleed across edges', 'Flow along edges']}),
        ('Spread', 'Float', 10.0, {'min': 0, 'max': 60, 'label': 'Spread px (wetness)'}),
        ('Taps', 'Int', 9, {'min': 2, 'max': 16, 'label': 'Taps'}),
        ('Wobble', 'Float', 0.6, {'min': 0, 'max': 3, 'label': 'Direction wobble'}),
        ('Wobblescale', 'Float', 80.0, {'min': 4, 'max': 400, 'label': 'Wobble scale px'}),
        ('Res', 'Menu', 'half', {'names': ['full', 'half', 'quarter'], 'labels': ['Full', 'Half', 'Quarter'],
                                 'label': 'Wash resolution'}),
        ('Edgedark', 'Float', 0.6, {'min': 0, 'max': 3, 'label': 'Wet edge darkening'}),
        ('Pigment', 'Float', 0.35, {'min': 0, 'max': 1.5, 'label': 'Pigment density variation'}),
        ('Pigmentscale', 'Float', 140.0, {'min': 8, 'max': 600, 'label': 'Pigment scale px'}),
        ('Granulation', 'Float', 0.3, {'min': 0, 'max': 1.5, 'label': 'Paper granulation'}),
        ('Grainscale', 'Float', 3.0, {'min': 1, 'max': 24, 'label': 'Grain px'}),
        ('Whitethr', 'Float', 0.85, {'min': 0, 'max': 1.2, 'label': 'Whites to paper above'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Colour', [
        ('Colsrc', 'Menu', 'picture', {'names': ['picture', 'palette'], 'labels': ['Picture', 'Palette by luma']}),
        ('Saturation', 'Float', 1.1, {'min': 0, 'max': 3, 'label': 'Saturation'}),
        ('Paperr', 'Float', 0.97, {'min': 0, 'max': 1, 'label': 'Paper R'}),
        ('Paperg', 'Float', 0.95, {'min': 0, 'max': 1, 'label': 'Paper G'}),
        ('Paperb', 'Float', 0.90, {'min': 0, 'max': 1, 'label': 'Paper B'}),
    ]),
    pal_page('neon_trio', 'gradient'),  # noqa: F821
]
PANEL_PAGES = ['Watercolour', 'Colour', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
_D['Palreverse'] = int(_D['Palreverse'])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'wash', _p(Seed=1)),
    (2, 'wet bleed', _p(Spread=22.0, Taps=12, Edgedark=1.2, Pigment=0.5, Whitethr=0.8, Seed=2)),
    (3, 'dry brush', _p(Flow=1, Spread=14.0, Wobble=1.5, Wobblescale=30.0, Granulation=0.7, Edgedark=0.3, Seed=3)),
    (4, 'pastel palette', _p(Colsrc=1, Spread=12.0, Pigment=0.25, Whitethr=0.95, Palsource=PAL_SOURCE_NAMES.index(  # noqa: F821
        'neon_trio'), Seed=4)),
    (5, 'ink wash', _p(Saturation=0.0, Spread=8.0, Edgedark=1.6, Pigment=0.6, Granulation=0.5, Seed=5)),
]

WASH = """// watercolour wash (compute, rgba16float, size = in1 / Res). Direction from the luma gradient (bleed) or its
// perpendicular (flow), bent by value noise; TAPS tent-weighted bilinear samples of in1 over +- Spread px.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uW;   // res div, spread px, taps, flow
uniform vec4 uV;   // wobble, wobble scale px, seed, -
""" + GLSL_LIB + """
vec2 fs;
vec4 S(vec2 q) { return texture(sTD2DInputs[0], q / fs); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    fs = vec2(textureSize(sTD2DInputs[0], 0));
    float D = uW.x;
    ivec2 jsz = ivec2(ceil(fs / D));
    if (p.x >= jsz.x || p.y >= jsz.y) return;
    vec2 pc = (vec2(p) + 0.5) * D;
    float gx = luma(S(pc + vec2(D, 0.0)).rgb) - luma(S(pc - vec2(D, 0.0)).rgb);
    float gy = luma(S(pc + vec2(0.0, D)).rgb) - luma(S(pc - vec2(0.0, D)).rgb);
    vec2 n = 2.0 * vnoise2(pc / max(uV.y, 1.0), uint(uV.z)) - 1.0;
    vec2 g = vec2(gx, gy);
    vec2 dir = dot(g, g) > 1e-8 ? normalize(g) : vec2(1.0, 0.0);
    if (uW.w > 0.5) dir = vec2(-dir.y, dir.x);
    dir += uV.x * n;
    dir = dot(dir, dir) > 1e-8 ? normalize(dir) : vec2(1.0, 0.0);
    int N = clamp(int(uW.z + 0.5), 2, TAPS);
    vec4 acc = vec4(0.0);
    float ws = 0.0;
    for (int k = 0; k < TAPS; k++) {
        if (k >= N) break;
        float f = float(k) / float(N - 1) - 0.5;
        float w = 1.0 - abs(f);
        acc += w * S(pc + dir * (2.0 * f * uW.y));
        ws += w;
    }
    TDImageStoreOutput(0, ivec3(p, 0), acc / ws);
}
""".replace('TAPS', str(TAPS))

LOOK = """// watercolour look (compute). in0 in1, in1 wash (bilinear). Wet edges, pigment, granulation, whites, palette.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, edgedark, pigment, pigment scale px
uniform vec4 uB;   // granulation, grain px, white thr, seed
uniform vec4 uC;   // paper rgb, colsrc
uniform vec4 uD;   // saturation, -, -, -
""" + GLSL_LIB + PAL_GLSL + """
vec2 fs;
vec4 Wq(vec2 q) { return texture(sTD2DInputs[1], q / fs); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    fs = vec2(isz);
    vec2 pc = vec2(p) + 0.5;
    vec4 w = Wq(pc);
    float gx = luma(Wq(pc + vec2(1.5, 0.0)).rgb) - luma(Wq(pc - vec2(1.5, 0.0)).rgb);
    float gy = luma(Wq(pc + vec2(0.0, 1.5)).rgb) - luma(Wq(pc - vec2(0.0, 1.5)).rgb);
    float rim = clamp(length(vec2(gx, gy)) * uA.y * 4.0, 0.0, 1.0);
    float L = luma(w.rgb);
    vec3 col = uC.w > 0.5 ? pxPal(L) : mix(vec3(L), w.rgb, uD.x);
    vec3 paper = uC.rgb;
    uint sd = uint(uB.w);
    float pg = 1.0 + uA.z * (2.0 * vnoise(pc / max(uA.w, 1.0), sd + 3u) - 1.0);
    float gr = 0.6 * vnoise(pc / max(uB.y, 1.0), sd + 11u) + 0.4 * vnoise(pc / max(0.5 * uB.y, 0.5), sd + 17u);
    float dens = pg * (1.0 + uB.x * (2.0 * gr - 1.0)) * (1.0 + 0.6 * rim);
    vec3 o = paper - (paper - col) * dens;
    o = mix(o, paper, smoothstep(uB.z, uB.z + 0.1, L));
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(o, c.a), uA.x));
}
"""

SHADERS = {'wash': WASH, 'look': LOOK}
NIN = {'wash': 1, 'look': 2}             # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"
DIV = "(1 if parent().par.Res.eval() == 'full' else (2 if parent().par.Res.eval() == 'half' else 4))"


def uniforms():
    return {
        'wash': [('uW', [DIV, P.format('Spread'), P.format('Taps'), 'parent().par.Flow.menuIndex']),
                 ('uV', [P.format('Wobble'), P.format('Wobblescale'), P.format('Seed'), '0'])],
        'look': [('uA', [P.format('Amount'), P.format('Edgedark'), P.format('Pigment'), P.format('Pigmentscale')]),
                 ('uB', [P.format('Granulation'), P.format('Grainscale'), P.format('Whitethr'), P.format('Seed')]),
                 ('uC', [P.format('Paperr'), P.format('Paperg'), P.format('Paperb'), 'parent().par.Colsrc.menuIndex']),
                 ('uD', [P.format('Saturation'), '0', '0', '0'])],
    }


def build(m, H):
    """in1 -> wash (Res) -> look (+ in1) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    wa = H['pas'](m, 'wash', WASH, [in1], 'int(math.ceil(me.inputs[0].width / %s))' % DIV,
                  'int(math.ceil(me.inputs[0].height / %s))' % DIV, 'rgba16float')
    H['uniforms'](wa, U['wash'])
    wa.comment = 'Pigment smear along / across the luma gradient (bent by noise), at Res.'
    lk = H['pas'](m, 'look', LOOK, [in1, wa], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](lk, U['look'])
    lk.comment = 'Wet edges + pigment + paper grain + whites; Amount mix.'
    pal_bind(m, H, [lk])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(lk)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact.'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Wash', 'role': 'process', 'ops': ['wash', 'wash_compute'],
         'body': 'Gradient-guided pigment smear at Res.'},
        {'title': '3 Paper', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'look', 'look_compute'],
         'body': 'Wet edges, pigment density, granulation, whites, palette.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
