# fx_film_grain - FX_film module 'grain' (FX3 F4): film grain, three models, one compute pass.
# Models: Hash (white noise per Size cell, TV-like), Noise 3D (value noise in x, y and film time: Evolve < 1 morphs
# the grain instead of re-rolling it; the glsl-film-grain idea, own code), Clumped (3 octaves Size, 2 Size, 4 Size,
# weights 1, c, c^2: dye clouds). Every model is normalised to unit variance (fx_film_logic.vn_norm / HASH_NORM /
# clump_weights; noise 3D divides by its z-axis factor at fract(z)), so Strength is the grain's std dev at
# sigma(L) = 1. Luma response sigma(L) = Shadow (1-L)^2 + Mid 2L(1-L) + High L^2. Colour: 3 per-channel noises, mono
# part = their sum / sqrt 3 (chroma_norm keeps unit variance).
# Lattice 2 adds a second lattice turned 36.87 deg (StageLab JZB_Lofi_Grain's trick: no grid shows) at sqrt 2 cost.
# Animate: every frame / Hold at Grain fps (24 on a 60 fps output = the film cue) / frozen. Amount 0 = exact. ASCII.

MODULE = 'grain'

PAGES = [
    ('Grain', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Strength', 'Float', 0.08, {'min': 0, 'max': 0.5, 'label': 'Strength (std dev)'}),
        ('Model', 'Menu', 'clumped', {'names': ['hash', 'noise3d', 'clumped'],
                                      'labels': ['Hash (white)', 'Noise 3D (evolving)', 'Clumped (dye clouds)']}),
        ('Size', 'Float', 1.5, {'min': 1, 'max': 8, 'label': 'Size px'}),
        ('Clump', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Clump (octave weight)'}),
        ('Chroma', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Colour grain'}),
        ('Shadow', 'Float', 0.6, {'min': 0, 'max': 2, 'label': 'Response shadows'}),
        ('Mid', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Response mids'}),
        ('High', 'Float', 0.4, {'min': 0, 'max': 2, 'label': 'Response highlights'}),
        ('Blend', 'Menu', 'add', {'names': ['add', 'multiply', 'overlay'], 'labels': ['Add', 'Multiply', 'Overlay']}),
        ('Animate', 'Menu', 'hold', {'names': ['frame', 'hold', 'frozen'],
                                     'labels': ['Every frame', 'Hold (Grain fps)', 'Frozen']}),
        ('Grainfps', 'Float', 24.0, {'min': 1, 'max': 60, 'label': 'Grain fps'}),
        ('Evolve', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Evolve (noise 3D)'}),
        ('Lattice2', 'Toggle', False, {'label': 'Second lattice (36.87 deg)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['Grain']

PRESETS = [
    (1, '35mm', {'Amount': 1.0, 'Strength': 0.05, 'Model': 2, 'Size': 1.2, 'Clump': 0.4, 'Chroma': 0.15,
                 'Shadow': 0.6, 'Mid': 1.0, 'High': 0.3, 'Blend': 2, 'Animate': 1, 'Grainfps': 24.0, 'Lattice2': 1}),
    (2, '16mm', {'Amount': 1.0, 'Strength': 0.09, 'Model': 1, 'Size': 2.0, 'Evolve': 1.0, 'Chroma': 0.2,
                 'Shadow': 0.7, 'Mid': 1.0, 'High': 0.4, 'Blend': 0, 'Animate': 1, 'Grainfps': 24.0, 'Lattice2': 1}),
    (3, 'super 8', {'Amount': 1.0, 'Strength': 0.15, 'Model': 2, 'Size': 3.0, 'Clump': 0.6, 'Chroma': 0.3,
                    'Shadow': 0.8, 'Mid': 1.0, 'High': 0.5, 'Blend': 0, 'Animate': 1, 'Grainfps': 18.0, 'Lattice2': 1}),
    (4, 'pushed 3200', {'Amount': 1.0, 'Strength': 0.22, 'Model': 2, 'Size': 2.5, 'Clump': 0.8, 'Chroma': 0.25,
                        'Shadow': 1.0, 'Mid': 1.0, 'High': 0.3, 'Blend': 0, 'Animate': 1, 'Grainfps': 24.0}),
    (5, 'still texture', {'Amount': 1.0, 'Strength': 0.06, 'Model': 0, 'Size': 2.0, 'Chroma': 0.0, 'Shadow': 0.5,
                          'Mid': 1.0, 'High': 0.5, 'Blend': 0, 'Animate': 2}),
]

SHADER = """// FX_film grain (compute). in0 = picture.
// uA amount strength model size | uB clump chroma tick evolve | uC shadow mid high blend | uD seed lattice2 - -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
%s
const float HASHN = %r;
const float VN2 = %r;
float noise1(vec2 P, uint s, int model, float sz, uint tick, vec3 cw) {   // unit-variance noise, one lattice
    if (model == 0) return (hsh(ivec2(floor(P / sz)), s + tick * 104729u) - 0.5) * HASHN;
    if (model == 1) {                     // z variance factor depends on fract(z): (1-s)^2 + s^2 (exact unit var)
        float z = float(tick) * uB.w, fz = fract(z); fz = fz * fz * (3.0 - 2.0 * fz);
        return (vnoise3(vec3(P / sz, z), s) - 0.5) * VN2 / sqrt((1.0 - fz) * (1.0 - fz) + fz * fz);
    }
    uint s2 = s + tick * 104729u;
    return ((vnoise(P / sz, s2) - 0.5) * cw.x + (vnoise(P / (2.0 * sz), s2 + 31u) - 0.5) * cw.y
            + (vnoise(P / (4.0 * sz), s2 + 62u) - 0.5) * cw.z) * VN2;
}
float noise(vec2 P, uint s, int model, float sz, uint tick, vec3 cw) {
    float n = noise1(P, s, model, sz, tick, cw);
    if (uD.y < 0.5) return n;
    vec2 Q = vec2(0.8 * P.x - 0.6 * P.y, 0.6 * P.x + 0.8 * P.y) + 1013.0;   // 36.87 deg, own seed
    return (n + noise1(Q, s ^ 0x5bd1e995u, model, sz, tick, cw)) * 0.70710678;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    vec2 P = vec2(p) + 0.5;
    int model = int(uA.z + 0.5);
    float sz = max(uA.w, 1.0);
    uint tick = uint(uB.z), seed = uint(uD.x) * 7919u;
    float cl = uB.x;
    vec3 cw = vec3(1.0, cl, cl * cl) / sqrt(1.0 + cl * cl + cl * cl * cl * cl);
    float ch = uB.y;
    vec3 n;
    if (ch <= 0.0) n = vec3(noise(P, seed, model, sz, tick, cw));
    else {
        vec3 nc = vec3(noise(P, seed + 1u, model, sz, tick, cw), noise(P, seed + 2u, model, sz, tick, cw),
                       noise(P, seed + 3u, model, sz, tick, cw));
        float nl = (nc.r + nc.g + nc.b) * 0.57735027;
        n = mix(vec3(nl), nc, ch) / sqrt((1.0 - ch) * (1.0 - ch) + ch * ch + 2.0 * ch * (1.0 - ch) * 0.57735027);
    }
    float L = clamp(luma(c.rgb), 0.0, 1.0);
    float sigma = uC.x * (1.0 - L) * (1.0 - L) + uC.y * 2.0 * L * (1.0 - L) + uC.z * L * L;
    vec3 g = n * (uA.y * sigma * uA.x);
    int bl = int(uC.w + 0.5);
    vec3 o = bl == 0 ? c.rgb + g : (bl == 1 ? c.rgb * (1.0 + g) : c.rgb + g * 4.0 * c.rgb * (1.0 - c.rgb));
    TDImageStoreOutput(0, ivec3(p, 0), vec4(o, c.a));
}
"""


def shaders(H):
    L = H['L']
    return {'fx': SHADER % (H['LIB'], L.HASH_NORM, L.vn_norm(2))}


TICK = ("(absTime.frame if parent().par.Animate.eval() == 'frame' else (0 if parent().par.Animate.eval() == 'frozen' "
        "else int(absTime.seconds * max(parent().par.Grainfps.eval(), 0.01)))) % 1000003")


def build(m, H):
    """in1 -> fx (one compute pass) -> out1."""
    mk, P = H['mk'], H['P']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', shaders(H)['fx'], [in1])
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), P.format('Strength'), 'parent().par.Model.menuIndex', P.format('Size')]),
        ('uB', [P.format('Clump'), P.format('Chroma'), TICK, P.format('Evolve')]),
        ('uC', [P.format('Shadow'), P.format('Mid'), P.format('High'), 'parent().par.Blend.menuIndex']),
        ('uD', [P.format('Seed'), '1 if parent().par.Lattice2.eval() else 0', '0', '0']),
    ])
    g.comment = 'grain: hash / noise 3D / clumped, unit variance x Strength x sigma(luma). Amount 0 = exact passthrough.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Grain', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass; Animate hold = Grain fps (24 on 60 = the film cue).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
