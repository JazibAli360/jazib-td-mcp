# fx_film_flare - FX_film module 'flare' (FX3 L2): pseudo lens flare after John Chapman (2013; re-implemented from
# the article: no code licence). in1 -> ext (rack EXT at quarter / half res, soft knee, padded to 64, mipmap) ->
# `flare` (at the extract size: the picture flipped through the optical Centre; Ghosts samples along the vector to the
# centre spaced by Dispersal, weighted by a radial falloff, each ghost hue-tinted and split R/G/B by Distortion px;
# a Halo ring at Halowidth) -> `fx` (full res: the flare buffer bilinear x lens Dirt (fbm) x Starburst (blades around
# the centre), added) -> out_sel (Amount 0 = in1) -> out1. Out-of-frame ghost samples are 0 (no wrap, unlike Chapman's
# fract). Ghost positions: fx_film_logic.ghost_positions (the live check). ASCII only.

MODULE = 'flare'

PAGES = [
    ('Flare', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Intensity', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Intensity'}),
        ('Threshold', 'Float', 0.9, {'min': 0, 'max': 4, 'label': 'Threshold'}),
        ('Knee', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Knee'}),
        ('Ghosts', 'Int', 6, {'min': 0, 'max': 12, 'label': 'Ghosts'}),
        ('Dispersal', 'Float', 0.35, {'min': -1, 'max': 1, 'label': 'Ghost dispersal'}),
        ('Ghostfalloff', 'Float', 2.0, {'min': 0.2, 'max': 12, 'label': 'Ghost falloff (exp)'}),
        ('Ghostblur', 'Float', 1.0, {'min': 0, 'max': 5, 'label': 'Ghost blur (mip lod)'}),
        ('Ghosthue', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Ghost hue'}),
        ('Ghostsat', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Ghost colour'}),
        ('Distortion', 'Float', 6.0, {'min': 0, 'max': 40, 'label': 'Chromatic split px'}),
        ('Halowidth', 'Float', 0.45, {'min': 0, 'max': 1, 'label': 'Halo width'}),
        ('Halogain', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Halo gain'}),
        ('Halofalloff', 'Float', 5.0, {'min': 0.5, 'max': 20, 'label': 'Halo falloff (exp)'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Optical centre x'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Optical centre y'}),
        ('Dirt', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Lens dirt'}),
        ('Dirtscale', 'Float', 6.0, {'min': 1, 'max': 40, 'label': 'Dirt scale'}),
        ('Burst', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Starburst'}),
        ('Blades', 'Int', 12, {'min': 3, 'max': 32, 'label': 'Starburst rays'}),
        ('Burstsharp', 'Float', 8.0, {'min': 1, 'max': 40, 'label': 'Starburst sharpness'}),
        ('Burstrot', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Starburst rotation deg'}),
        ('Quality', 'Menu', 'quarter', {'names': ['half', 'quarter'], 'labels': ['Half res', 'Quarter res']}),
        ('Seed', 'Int', 3, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['Flare']

PRESETS = [
    (1, 'classic', {'Amount': 1.0, 'Intensity': 1.0, 'Ghosts': 6, 'Dispersal': 0.35, 'Ghostfalloff': 2.0,
                    'Halowidth': 0.45, 'Halogain': 0.5, 'Distortion': 6.0, 'Dirt': 0.3, 'Burst': 0.3}),
    (2, 'clean ghosts', {'Amount': 1.0, 'Intensity': 1.5, 'Ghosts': 8, 'Dispersal': 0.25, 'Ghostfalloff': 1.5,
                         'Ghostblur': 2.0, 'Halogain': 0.0, 'Distortion': 2.0, 'Dirt': 0.0, 'Burst': 0.0}),
    (3, 'halo ring', {'Amount': 1.0, 'Intensity': 1.0, 'Ghosts': 2, 'Halowidth': 0.6, 'Halogain': 1.5,
                      'Halofalloff': 8.0, 'Distortion': 12.0, 'Dirt': 0.2, 'Burst': 0.0}),
    (4, 'dirty sun', {'Amount': 1.0, 'Intensity': 2.0, 'Threshold': 0.8, 'Ghosts': 5, 'Dispersal': 0.4,
                      'Dirt': 0.8, 'Dirtscale': 10.0, 'Burst': 0.7, 'Blades': 16, 'Burstsharp': 12.0}),
    (5, 'rainbow chain', {'Amount': 1.0, 'Intensity': 1.2, 'Ghosts': 12, 'Dispersal': 0.18, 'Ghostsat': 1.0,
                          'Ghosthue': 0.0, 'Distortion': 10.0, 'Halogain': 0.3, 'Burst': 0.0}),
]

FLARE = """// FX_film flare ghosts (compute) at the extract size. in0 = EXT (mipmap, extend zero). uv: image 0..1, y up.
// uF0 ghosts dispersal ghostfalloff halowidth | uF1 distortion(uv) halofalloff ghostblur halogain
// uF2 centre x y ghosthue ghostsat | uF3 validW validH aspect -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uF0;
uniform vec4 uF1;
uniform vec4 uF2;
uniform vec4 uF3;
%s
vec2 VS;
vec3 smp(vec2 s, float lod) {                                // image uv -> padded extract uv; 0 outside the frame
    if (s.x < 0.0 || s.y < 0.0 || s.x > 1.0 || s.y > 1.0) return vec3(0.0);
    return textureLod(sTD2DInputs[0], s * VS, lod).rgb;
}
vec3 smpCA(vec2 s, vec2 dir, float lod) {
    vec2 o = dir * uF1.x;
    return vec3(smp(s + o, lod).r, smp(s, lod).g, smp(s - o, lod).b);
}
void main() {
    ivec2 q = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (q.x >= osz.x || q.y >= osz.y) return;
    if (float(q.x) >= uF3.x || float(q.y) >= uF3.y) { TDImageStoreOutput(0, ivec3(q, 0), vec4(0.0)); return; }
    VS = uF3.xy / vec2(textureSize(sTD2DInputs[0], 0));
    vec2 uv = (vec2(q) + 0.5) / uF3.xy;
    vec2 C = uF2.xy;
    vec2 uvf = 2.0 * C - uv;
    vec2 gv = (C - uvf) * uF0.y;
    vec2 dir = length(gv) > 1e-6 ? normalize(gv) : vec2(0.0);
    vec3 acc = vec3(0.0);
    int ng = int(uF0.x + 0.5);
    for (int i = 0; i < 12; i++) {
        if (i >= ng) break;
        vec2 s = uvf + gv * float(i);
        float w = pow(max(1.0 - length(C - s) / 0.70710678, 0.0), uF0.z);
        vec3 tint = mix(vec3(1.0), hue2rgb(fract(uF2.z + float(i) * 0.137)), uF2.w);
        acc += smpCA(s, dir, uF1.z) * w * tint;
    }
    if (uF1.w > 0.0) {
        vec2 hd = (C - uvf) * vec2(uF3.z, 1.0);
        hd = length(hd) > 1e-6 ? normalize(hd) / vec2(uF3.z, 1.0) : vec2(0.0);
        vec2 s = uvf + hd * uF0.w;
        float w = pow(max(1.0 - length((C - s) * vec2(uF3.z, 1.0)) / 0.70710678, 0.0), uF1.y);
        acc += smpCA(s, dir, uF1.z) * w * uF1.w;
    }
    TDImageStoreOutput(0, ivec3(q, 0), vec4(acc, 1.0));
}
"""

FX = """// FX_film flare composite (compute). in0 = picture, in1 = flare buffer (bilinear).
// uA amount intensity dirt dirtscale | uB burst blades sharp rot(rad) | uC centre x y seed aspect | uD validW validH - -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
%s
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    vec2 uv = (vec2(p) + 0.5) / vec2(isz);
    vec2 fsz = vec2(textureSize(sTD2DInputs[1], 0));
    vec3 f = texture(sTD2DInputs[1], uv * uD.xy / fsz).rgb;
    float dirt = mix(1.0, 2.0 * fbm(uv * uA.w * vec2(uC.w, 1.0), uint(uC.z), 3), uA.z);
    vec2 d = (uv - uC.xy) * vec2(uC.w, 1.0);
    float ang = atan(d.y, d.x) + uB.w;
    float rays = pow(abs(cos(ang * uB.y * 0.5)), uB.z) * (0.6 + 0.8 * vnoise(vec2(ang * uB.y * 0.159, 0.5), uint(uC.z) + 9u));
    float burst = mix(1.0, 2.0 * rays, uB.x);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(c.rgb + uA.x * uA.y * f * dirt * burst, c.a));
}
"""

SCALE = "(2 if parent().par.Quality.eval() == 'half' else 4)"


def shaders(H):
    return {'flare': FLARE % H['LIB'], 'fx': FX % H['LIB']}


def build(m, H):
    """in1 -> ext (rack EXT) -> flare (ghosts + halo at extract size) -> fx (dirt x starburst, add) -> out_sel."""
    mk, P = H['mk'], H['P']
    T = shaders(H)
    in1 = mk(m, inTOP, 'in1')
    ext, X = H['ext'](m, 'ext', in1, SCALE, P.format('Threshold'), 'max(%s, 1e-4)' % P.format('Knee'),
                      byluma='0', mode='0', mult=64)
    fl = H['compute'](m, 'flare', T['flare'], [ext], fmt='rgba16float', extend='zero', filt='mipmap')
    asp = '%s / max(%s, 1)' % (H['W'], H['H'])
    H['uniforms'](fl, [
        ('uF0', [P.format('Ghosts'), P.format('Dispersal'), P.format('Ghostfalloff'), P.format('Halowidth')]),
        ('uF1', ['%s / %s' % (P.format('Distortion'), H['W']), P.format('Halofalloff'), P.format('Ghostblur'),
                 P.format('Halogain')]),
        ('uF2', [P.format('Centerx'), P.format('Centery'), P.format('Ghosthue'), P.format('Ghostsat')]),
        ('uF3', [X['vw'], X['vh'], asp, '0']),
    ])
    fl.comment = 'flare: ghosts along the vector to the optical centre + halo ring, R/G/B split (extract size).'
    g = H['compute'](m, 'fx', T['fx'], [in1, fl], extend='zero')
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), P.format('Intensity'), P.format('Dirt'), P.format('Dirtscale')]),
        ('uB', [P.format('Burst'), P.format('Blades'), P.format('Burstsharp'),
                'math.radians(%s)' % P.format('Burstrot')]),
        ('uC', [P.format('Centerx'), P.format('Centery'), P.format('Seed'), asp]),
        ('uD', [X['vw'], X['vh'], '0', '0']),
    ])
    g.comment = 'flare composite: flare x lens dirt x starburst, added.'
    sel = H['outsel'](m, in1, g)
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Extract', 'role': 'process', 'ops': ['ext', 'ext_compute'],
         'body': 'Quarter/half box mean + soft knee, padded to 64 (mips for the ghost blur).'},
        {'title': '3 Ghosts + halo', 'role': 'process', 'ops': ['flare', 'flare_compute']},
        {'title': '4 Composite', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'x dirt x starburst, add.'},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
