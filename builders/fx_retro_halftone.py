# fx_retro_halftone - FX_retro module 'halftone' (FX0 FX_retro row: print screens). Adapted from td-port
# halftone/halftone.frag (itself the StageLab FFGL Halftone port, same owner): mono / RGB / CMYK screens, round /
# square / line / diamond dots, paper and ink colours. Changes for the rack: compute pass (T-47), no fwidth (the AA
# width is one output pixel in cell units), lowbias32 hash instead of sin-hash (exact mirror), and Sampling cell =
# the dot size comes from the picture at the dot's cell centre (true halftone dots) or per pixel (threshold screen,
# the td-port look). Screen angles C 15 / M 75 / Y 0 / K 45 deg (+ Angle). Premultiplied in / out, Amount mix,
# out_sel: Amount 0 = in1. Mirror: builders/fx_retro_halftone_logic.py. ASCII only.

MODULE = 'halftone'
MODES = ['mono', 'rgb', 'cmyk']
SHAPES = ['round', 'square', 'line', 'diamond']


def pages(Lg):
    return [
        ('Halftone', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Mode', 'Menu', 'cmyk', {'names': MODES, 'labels': ['Mono', 'RGB (additive)', 'CMYK (print)']}),
            ('Shape', 'Menu', 'round', {'names': SHAPES, 'labels': ['Round', 'Square', 'Line', 'Diamond']}),
            ('Sampling', 'Menu', 'cell', {'names': ['cell', 'pixel'], 'labels': ['Cell centre (dots)',
                                                                             'Per pixel (threshold screen)']}),
            ('Cellsize', 'Float', 14.0, {'min': 2, 'max': 120, 'label': 'Cell size px'}),
            ('Angle', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Screen angle deg'}),
            ('Softness', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Softness'}),
            ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 3, 'label': 'Gamma'}),
            ('Randomness', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Dot jitter'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
        ('Inks', [
            ('Paperr', 'Float', 0.96, {'min': 0, 'max': 1, 'label': 'Paper R'}),
            ('Paperg', 'Float', 0.94, {'min': 0, 'max': 1, 'label': 'Paper G'}),
            ('Paperb', 'Float', 0.88, {'min': 0, 'max': 1, 'label': 'Paper B'}),
            ('Inkr', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Ink R (mono / K)'}),
            ('Inkg', 'Float', 0.07, {'min': 0, 'max': 1, 'label': 'Ink G'}),
            ('Inkb', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Ink B'}),
        ]),
    ]


PANEL_PAGES = ['Halftone', 'Inks']


def presets(Lg):
    D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in pages(Lg) for n, s, d, o in pl)
    return [
        (1, 'cmyk print', dict(D)),
        (2, 'newspaper', dict(D, Mode=0, Cellsize=10.0, Angle=45.0, Seed=2)),
        (3, 'pop art', dict(D, Mode=0, Cellsize=28.0, Paperr=1.0, Paperg=0.86, Paperb=0.2, Inkr=0.85, Inkg=0.05,
                            Inkb=0.25, Seed=3)),
        (4, 'rgb screen', dict(D, Mode=1, Shape=3, Cellsize=12.0, Paperr=1.0, Paperg=1.0, Paperb=1.0, Inkr=0.0,
                               Inkg=0.0, Inkb=0.0, Seed=4)),
        (5, 'line engraving', dict(D, Mode=0, Shape=2, Sampling=1, Cellsize=8.0, Angle=30.0, Softness=0.3, Seed=5)),
    ]


FX = """// FX_retro halftone (compute, full res). in0 = picture (premultiplied). = fx_retro_halftone_logic.render
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount mode shape sampling
uniform vec4 uB;   // cellsize angle(rad) softness gamma
uniform vec4 uC;   // randomness seed - -
uniform vec4 uD;   // paper rgb -
uniform vec4 uE;   // ink rgb -
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hc(ivec2 v, uint k) { return float(lb32(uint(v.x) * 1597334677u ^ lb32(uint(v.y) ^ (k * 2654435761u))) >> 8)
                                   / 16777216.0; }
vec2 SZ;
ivec2 RES;
vec3 pic(vec2 q) {                                          // straight colour at pixel-space point q, gamma'd
    vec4 s = texelFetch(sTD2DInputs[0], clamp(ivec2(floor(q)), ivec2(0), RES - 1), 0);
    vec3 c = clamp(s.a > 1e-6 ? s.rgb / s.a : s.rgb, 0.0, 1.0);
    return pow(c, vec3(uB.w));
}
// one screen at angle a: x = dot coverage (0..1) for value v; cell centre in pixel space via `ctr`
float spot(vec2 pc, float a, int ch, int salt) {
    float cs = cos(a), sn = sin(a);
    vec2 p = pc - 0.5 * SZ;
    vec2 r = vec2(cs * p.x + sn * p.y, -sn * p.x + cs * p.y) / uB.x;
    vec2 tile = floor(r);
    ivec2 ti = ivec2(tile);
    uint sd = uint(uC.y) * 7919u + uint(salt) * 31u;
    vec2 jit = (vec2(hc(ti, sd), hc(ti, sd + 17u)) - 0.5) * uC.x * 0.35;
    vec2 q = r - tile - 0.5 - jit;
    float v;
    vec3 c;
    if (uA.w < 0.5) {                                       // cell centre back to pixel space
        vec2 cc = (tile + 0.5) * uB.x;
        c = pic(vec2(cs * cc.x - sn * cc.y, sn * cc.x + cs * cc.y) + 0.5 * SZ);
    } else c = pic(pc);
    int md = int(uA.y + 0.5);
    if (md == 0) v = 1.0 - dot(c, vec3(0.299, 0.587, 0.114));
    else if (md == 1) v = c[ch];
    else {
        vec3 cym = 1.0 - c; float k = min(min(cym.r, cym.g), cym.b);
        v = ch == 3 ? k : cym[ch] - k;
    }
    if (v <= 0.0001) return 0.0;
    if (v >= 0.9999) return 1.0;
    int sh = int(uA.z + 0.5);
    float d = sh == 0 ? length(q) * 1.77245385 : (sh == 1 ? max(abs(q.x), abs(q.y)) * 2.0
            : (sh == 2 ? abs(q.y) * 2.0 : (abs(q.x) + abs(q.y)) * 1.41421356));
    float edge = sqrt(v);
    float aa = 1.0 / uB.x + uB.z * 0.3;                     // one output px in cell units (+ softness)
    return 1.0 - smoothstep(edge - aa, edge + aa, d);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    RES = textureSize(sTD2DInputs[0], 0);
    if (p.x >= RES.x || p.y >= RES.y) return;
    SZ = vec2(RES);
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    if (c0.a <= 1e-6) { TDImageStoreOutput(0, ivec3(p, 0), c0); return; }
    vec2 pc = vec2(p) + 0.5;
    int md = int(uA.y + 0.5);
    float A = uB.y;
    vec3 o;
    if (md == 0) o = mix(uD.rgb, uE.rgb, spot(pc, A, 0, 0));
    else if (md == 1) {
        vec3 s3 = vec3(spot(pc, A, 0, 0), spot(pc, A + 0.5235988, 1, 1), spot(pc, A + 1.0471976, 2, 2));
        o = mix(uE.rgb, s3 * uD.rgb, 0.85);
    } else {
        float C = spot(pc, A + 0.2617994, 0, 0), M = spot(pc, A + 1.3089969, 1, 1), Y = spot(pc, A, 2, 2);
        float K = spot(pc, A + 0.7853982, 3, 3);
        o = mix(uD.rgb * vec3(1.0 - C, 1.0 - M, 1.0 - Y), uE.rgb, K);
    }
    o = clamp(o, 0.0, 1.0);
    vec3 src = c0.rgb / c0.a;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(mix(src, o, uA.x) * c0.a, c0.a));
}
"""


def shader_texts(lib):
    return {'fx': FX}


def uniforms(H):
    P = H['P']
    return [('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', 'parent().par.Shape.menuIndex',
                    'parent().par.Sampling.menuIndex']),
            ('uB', ['max(%s, 1.0)' % P.format('Cellsize'), 'math.radians(%s)' % P.format('Angle'),
                    P.format('Softness'), P.format('Gamma')]),
            ('uC', [P.format('Randomness'), P.format('Seed'), '0', '0']),
            ('uD', [P.format('Paperr'), P.format('Paperg'), P.format('Paperb'), '0']),
            ('uE', [P.format('Inkr'), P.format('Inkg'), P.format('Inkb'), '0'])]


def build(m, H, Lg):
    """in1 -> fx (one pass) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr, compute = H['mk'], H['expr'], H['compute']
    in1 = mk(m, inTOP, 'in1')
    fx = compute(m, 'fx', FX, [in1], 'me.inputs[0].width', 'me.inputs[0].height', uniforms=uniforms(H))
    fx.comment = 'halftone: mono / RGB / CMYK screens, dot shapes, cell-centre or per-pixel coverage.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '0 if parent().par.Amount.eval() <= 0 else 1')
    sel.comment = 'Amount 0 = in1 exactly.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Halftone', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'One pass: screens and dots.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
