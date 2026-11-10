# fx_film_diffusion - FX_film module 'diffusion' (FX3 L4 + G-BLOOM): bloom and diffusion filters on ONE shared
# pyramid. in1 -> ext (rack EXT, padded to 128: mode Bloom/Glimmer = soft-knee excess, mode Mist = the picture
# itself) -> pyra + pyrb (rack pyramid: [1 3 3 1] levels 1..7) -> glow (gather over levels around log2(Radius) at the
# Quality res, perf lane 3) -> fx (full-res composite; `mipmap` only while the Mist veil reads the mean of EXT) ->
# out_sel -> out1.
#   Bloom   : out = in + I x tint x gathered excess (energy added = I x tint x excess, weights normalised).
#   Mist    : Pro-Mist / Black-Mist: out = mix(in, B, Soften x h(B)) + Veil x mean(B) + I x tint x knee(B), B = the
#             blurred picture, h = soft highlight weight (bright areas bleed into the dark ones, contrast drops).
#   Glimmer : Bloom + sparkle points in the bright areas (Glimmerglass), re-rolled Glimrate times a second.
# Maths: fx_film_logic.level_weights / ext_np. Amount 0 = in1 (not cooked). ASCII only.

MODULE = 'diffusion'

PAGES = [
    ('Diffusion', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'bloom', {'names': ['bloom', 'mist', 'glimmer'],
                                   'labels': ['Bloom', 'Mist (Pro-Mist)', 'Glimmer']}),
        ('Intensity', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Intensity (bloom)'}),
        ('Threshold', 'Float', 0.9, {'min': 0, 'max': 4, 'label': 'Threshold'}),
        ('Knee', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Knee'}),
        ('Radius', 'Float', 60.0, {'min': 2, 'max': 500, 'label': 'Radius px'}),
        ('Spread', 'Float', 1.5, {'min': 0.2, 'max': 4, 'label': 'Spread (mip levels)'}),
        ('Soften', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Soften (mist)'}),
        ('Veil', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Veil / black lift (mist)'}),
        ('Tint', 'RGB', (1.0, 0.97, 0.92), {'label': 'Tint'}),
        ('Glimmer', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Glimmer gain'}),
        ('Glimsize', 'Float', 2.0, {'min': 1, 'max': 8, 'label': 'Glimmer size px'}),
        ('Glimdensity', 'Float', 0.02, {'min': 0, 'max': 0.2, 'label': 'Glimmer density'}),
        ('Glimrate', 'Float', 12.0, {'min': 0, 'max': 60, 'label': 'Glimmer rate Hz'}),
        ('Quality', 'Menu', 'half', {'names': ['half', 'quarter', 'full'],
                                     'labels': ['Half res (default)', 'Quarter res', 'Full res gather (finest core)']}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['Diffusion']

PRESETS = [
    (1, 'bloom', {'Amount': 1.0, 'Mode': 0, 'Intensity': 0.6, 'Threshold': 0.9, 'Knee': 0.3, 'Radius': 60.0,
                  'Spread': 1.5}),
    (2, 'pro-mist 1/2', {'Amount': 1.0, 'Mode': 1, 'Intensity': 0.3, 'Threshold': 0.7, 'Knee': 0.3, 'Radius': 80.0,
                         'Spread': 1.5, 'Soften': 0.45, 'Veil': 0.03, 'Tintr': 1.0, 'Tintg': 0.95, 'Tintb': 0.88}),
    (3, 'black mist 1/8', {'Amount': 1.0, 'Mode': 1, 'Intensity': 0.2, 'Threshold': 0.75, 'Knee': 0.2,
                           'Radius': 24.0, 'Spread': 1.0, 'Soften': 0.3, 'Veil': 0.0}),
    (4, 'glimmerglass', {'Amount': 1.0, 'Mode': 2, 'Intensity': 0.5, 'Threshold': 0.8, 'Radius': 40.0,
                         'Glimmer': 1.5, 'Glimsize': 2.0, 'Glimdensity': 0.03, 'Glimrate': 12.0}),
    (5, 'dream glow', {'Amount': 1.0, 'Mode': 0, 'Intensity': 1.4, 'Threshold': 0.5, 'Knee': 0.5, 'Radius': 220.0,
                       'Spread': 2.5, 'Quality': 1}),
]

GLOW = """// FX_film diffusion glow (compute, gather res: EXT res for Quality half / quarter, full res for full).
// in0 = EXT (padded), in1 = PYRA (levels 1..4), in2 = PYRB (levels 5..7). Out rgb = B (the gather over levels around
// log2(Radius), weights normalised), a = luma of the level-0 tap (Glimmer).
// uA - mode radius spread | uD scale gscale - -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uD;
%s
%s
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= osz.x || p.y >= osz.y) return;
    vec2 esz = vec2(textureSize(sTD2DInputs[0], 0));
    float sc = uD.x;
    vec2 uv = ((vec2(p) + 0.5) * (uD.y / sc)) / esz;
    float kc = log2(max(uA.z, 1e-3) / sc);
    vec3 acc = vec3(0.0), s0 = vec3(0.0);
    float ws = 0.0;
    for (int k = 0; k < 8; k++) {
        float w = lvlw(float(k), kc, uA.w);
        if (w < WSKIP && (k > 0 || int(uA.y + 0.5) != 2)) continue;   // level adds < 1e-3: not read (Glimmer needs 0)
        vec3 s = mipTap(uv, float(k), esz).rgb;
        if (k == 0) s0 = s;
        acc += w * s;
        ws += w;
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(acc / max(ws, 1e-6), luma(s0)));
}
"""

SHADER = """// FX_film diffusion composite (compute, full res). in0 = picture, in1 = glow (gather res: B rgb, level-0 luma a),
// in2 = EXT (mipmap filter only while the Mist veil reads its mean).
// uA amount mode - gscale | uB intensity soften veil - | uC tint rgb glimmer | uD thr knee seed tick | uE glimsize glimdensity - -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
uniform vec4 uE;
%s
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    vec2 gsz = vec2(textureSize(sTD2DInputs[1], 0));
    vec4 G = textureLod(sTD2DInputs[1], ((vec2(p) + 0.5) / uA.w) / gsz, 0.0);
    vec3 B = G.rgb;
    int mode = int(uA.y + 0.5);
    float A = uA.x;
    vec3 o;
    if (mode == 1) {
        float h = smoothstep(uD.x - uD.y, uD.x + uD.y + 1e-4, luma(B));
        vec3 mean = textureLod(sTD2DInputs[2], vec2(0.5), 12.0).rgb;
        o = mix(c.rgb, B, A * uB.y * h) + A * uB.z * mean + A * uB.x * uC.rgb * kneex(B, uD.x, max(uD.y, 1e-4), 0.0);
    } else {
        o = c.rgb + A * uB.x * uC.rgb * B;
        if (mode == 2) {
            ivec2 cell = ivec2(floor((vec2(p) + 0.5) / max(uE.x, 1.0)));
            float sp = step(1.0 - uE.y, hsh(cell, uint(uD.z) * 7919u + uint(uD.w) * 104729u));
            o += A * uC.w * sp * G.a * 4.0 * uC.rgb;
        }
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(o, c.a));
}
"""


def shaders(H):
    return {'glow': GLOW % (H['LIB'], H['MIPG']), 'fx': SHADER % H['LIB']}


def build(m, H):
    """in1 -> ext (rack EXT; mist stores the picture) -> pyra + pyrb -> glow (gather) -> fx (composite) -> out_sel."""
    mk, P, Q = H['mk'], H['P'], H['GQ']
    sh = shaders(H)
    in1 = mk(m, inTOP, 'in1')
    ext, X = H['ext'](m, 'ext', in1, Q['scale'], P.format('Threshold'), 'max(%s, 1e-4)' % P.format('Knee'),
                      byluma='0', mode="1 if parent().par.Mode.eval() == 'mist' else 0", mult=128)
    pyr = H['pyr'](m, ext)
    gl = H['compute'](m, 'glow', sh['glow'], [ext] + pyr, res=Q['res'], fmt='rgba16float', extend='hold',
                      filt='linear')
    H['uniforms'](gl, [
        ('uA', ['0', 'parent().par.Mode.menuIndex', P.format('Radius'), P.format('Spread')]),
        ('uD', [X['scale'], Q['g'], '0', '0']),
    ])
    gl.comment = 'diffusion glow: gather over the pyramid levels around log2(Radius), at the gather res (Quality).'
    g = H['compute'](m, 'fx', sh['fx'], [in1, gl, ext], extend='hold', filt='mipmap')
    # mips only for the Mist veil (mean of EXT at lod 12); the glow is read at lod 0
    H['expr'](g.par.inputfiltertype, "'mipmap' if parent().par.Mode.eval() == 'mist' and parent().par.Veil.eval() > 0"
              " else 'linear'")
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', '0', Q['g']]),
        ('uB', [P.format('Intensity'), P.format('Soften'), P.format('Veil'), '0']),
        ('uC', [P.format('Tintr'), P.format('Tintg'), P.format('Tintb'), P.format('Glimmer')]),
        ('uD', [P.format('Threshold'), P.format('Knee'), P.format('Seed'),
                'int(absTime.seconds * max(parent().par.Glimrate.eval(), 0.0)) % 1000003']),
        ('uE', [P.format('Glimsize'), P.format('Glimdensity'), '0', '0']),
    ])
    g.comment = 'diffusion: bloom / mist / glimmer at full res from the glow (bilinear from the gather res).'
    sel = H['outsel'](m, in1, g)
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Extract', 'role': 'process', 'ops': ['ext', 'ext_compute'] + H['pyr_ops'],
         'body': 'Bloom/Glimmer: soft-knee excess; Mist: the picture. Padded to 128 (exact mips).'},
        {'title': '3 Diffusion', 'role': 'process', 'ops': ['glow', 'glow_compute', 'fx', 'fx_compute'],
         'body': 'Mip gather around log2(Radius); bloom add, mist mix + veil, glimmer sparkle.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
