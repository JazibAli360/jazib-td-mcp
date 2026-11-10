# fx_film_halation - FX_film module 'halation' (FX3 F3): the red-orange glow film makes around bright lights (light
# goes through the emulsion, bounces off the base and re-exposes the red layer most).
# in1 -> ext (rack EXT: half / quarter res box mean + soft-knee excess, padded to 128 so mips are exact, T-116 (1)) ->
# pyra + pyrb (rack pyramid: [1 3 3 1] levels 1..7 in two atlas ops, so the halo stays centred on the light) -> glow
# (gather at the Quality res: per channel a gaussian over pyramid LEVELS around log2(Radius x ratio), red widest
# (Ratio R/G/B 1.4 / 1.0 / 0.7, FX3 s3 starting point); Core subtracts the light's own footprint so the halo sits
# AROUND the light) -> fx (full res: tint, add or screen) -> out_sel (Amount 0 = in1, nothing cooks) -> out1.
# Perf lane 3 (27 Oct): the gather ran at every full-res pixel (1.4 ms GPU); at the EXT res + a bilinear read it is
# ~4x fewer gather pixels (Quality full keeps the old per-pixel gather).
# Why a pyramid and not Bloom/Blur TOPs: the stock Bloom TOP costs ~1.7 ms at any size (T-113 (5)); one gather is one
# pass; why not TD's box mips: T-129 (halo off-centre). Maths: fx_film_logic.level_weights / knee_excess / ext_np. ASCII only.

MODULE = 'halation'

PAGES = [
    ('Halation', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Intensity', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Intensity'}),
        ('Threshold', 'Float', 0.8, {'min': 0, 'max': 4, 'label': 'Threshold'}),
        ('Knee', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Knee'}),
        ('Kneeby', 'Menu', 'max', {'names': ['max', 'luma'], 'labels': ['Brightest channel', 'Luma']}),
        ('Radius', 'Float', 40.0, {'min': 2, 'max': 400, 'label': 'Radius px'}),
        ('Spread', 'Float', 1.0, {'min': 0.2, 'max': 3, 'label': 'Spread (mip levels)'}),
        ('Ratior', 'Float', 1.4, {'min': 0.1, 'max': 4, 'label': 'Radius ratio R'}),
        ('Ratiog', 'Float', 1.0, {'min': 0.1, 'max': 4, 'label': 'Radius ratio G'}),
        ('Ratiob', 'Float', 0.7, {'min': 0.1, 'max': 4, 'label': 'Radius ratio B'}),
        ('Tint', 'RGB', (1.0, 0.3, 0.06), {'label': 'Tint (per channel gain)'}),
        ('Source', 'Menu', 'luma', {'names': ['luma', 'colour'], 'labels': ['Light luma (classic)', 'Light colour']}),
        ('Blend', 'Menu', 'add', {'names': ['add', 'screen'], 'labels': ['Add', 'Screen']}),
        ('Core', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Core subtract'}),
        ('Quality', 'Menu', 'half', {'names': ['half', 'quarter', 'full'],
                                     'labels': ['Half res (default)', 'Quarter res', 'Full res gather (finest core)']}),
    ]),
]
PANEL_PAGES = ['Halation']

PRESETS = [
    (1, '800T neon', {'Amount': 1.0, 'Intensity': 1.5, 'Threshold': 0.7, 'Knee': 0.25, 'Radius': 60.0, 'Spread': 1.0,
                      'Tintr': 1.0, 'Tintg': 0.25, 'Tintb': 0.05, 'Source': 0, 'Blend': 0, 'Core': 0.3}),
    (2, 'subtle print', {'Amount': 1.0, 'Intensity': 0.4, 'Threshold': 0.85, 'Knee': 0.2, 'Radius': 30.0,
                         'Spread': 1.0, 'Tintr': 1.0, 'Tintg': 0.35, 'Tintb': 0.1, 'Source': 0, 'Blend': 1, 'Core': 0.0}),
    (3, 'super 8 glow', {'Amount': 1.0, 'Intensity': 1.0, 'Threshold': 0.6, 'Knee': 0.3, 'Radius': 90.0,
                         'Spread': 1.5, 'Tintr': 1.0, 'Tintg': 0.5, 'Tintb': 0.2, 'Source': 1, 'Blend': 1}),
    (4, 'hot lamps', {'Amount': 1.0, 'Intensity': 2.5, 'Threshold': 0.9, 'Knee': 0.1, 'Radius': 45.0, 'Spread': 0.8,
                      'Tintr': 1.0, 'Tintg': 0.3, 'Tintb': 0.06, 'Source': 0, 'Blend': 0, 'Core': 0.5}),
]

GLOW = """// FX_film halation glow (compute, gather res: EXT res for Quality half / quarter, full res for full).
// in0 = EXT (excess rgb, luma in a; padded), in1 = PYRA (levels 1..4), in2 = PYRB (levels 5..7). Out rgb = the halo
// before tint / Intensity: per channel a gaussian over pyramid levels around log2(Radius x ratio), minus Core x level 0.
// uA - - radius spread | uB ratio r g b - | uD scale gscale source core
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uD;
%s
%s
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= osz.x || p.y >= osz.y) return;
    vec2 esz = vec2(textureSize(sTD2DInputs[0], 0));
    vec2 uv = ((vec2(p) + 0.5) * (uD.y / uD.x)) / esz;      // gather texel centre in EXT texels
    vec3 kc = log2(max(uA.z * uB.xyz, vec3(1e-3)) / uD.x);
    vec3 acc = vec3(0.0), ws = vec3(0.0), core = vec3(0.0);
    for (int k = 0; k < 8; k++) {
        float fk = float(k);
        vec3 w = vec3(lvlw(fk, kc.r, uA.w), lvlw(fk, kc.g, uA.w), lvlw(fk, kc.b, uA.w));
        if (max(w.r, max(w.g, w.b)) < WSKIP && (k > 0 || uD.w <= 0.0)) continue;   // level adds < 1e-3: not read
        vec4 s = mipTap(uv, fk, esz);
        vec3 src = uD.z > 0.5 ? s.rgb : vec3(s.a);
        if (k == 0) core = src;
        acc += w * src;
        ws += w;
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(max(acc / max(ws, vec3(1e-6)) - uD.w * core, vec3(0.0)), 1.0));
}
"""

SHADER = """// FX_film halation composite (compute, full res). in0 = picture, in1 = glow (gather res, read bilinearly).
// uA amount intensity blend gscale | uC tint rgb -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uC;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    vec2 gsz = vec2(textureSize(sTD2DInputs[1], 0));
    vec3 g = texture(sTD2DInputs[1], ((vec2(p) + 0.5) / uA.w) / gsz).rgb * uC.rgb * (uA.y * uA.x);
    vec3 o = uA.z > 0.5 ? c.rgb + (1.0 - min(c.rgb, vec3(1.0))) * g : c.rgb + g;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(o, c.a));
}
"""


def shaders(H):
    return {'glow': GLOW % (H['LIB'], H['MIPG']), 'fx': SHADER}


def build(m, H):
    """in1 -> ext (rack EXT) -> pyra + pyrb (rack pyramid) -> glow (gather) -> fx (composite) -> out_sel -> out1."""
    mk, P, Q = H['mk'], H['P'], H['GQ']
    sh = shaders(H)
    in1 = mk(m, inTOP, 'in1')
    ext, X = H['ext'](m, 'ext', in1, Q['scale'], P.format('Threshold'), 'max(%s, 1e-4)' % P.format('Knee'),
                      byluma='parent().par.Kneeby.menuIndex', mode='0', mult=128)
    pyr = H['pyr'](m, ext)
    gl = H['compute'](m, 'glow', sh['glow'], [ext] + pyr, res=Q['res'], fmt='rgba16float', extend='hold',
                      filt='linear')
    H['uniforms'](gl, [
        ('uA', ['0', '0', P.format('Radius'), P.format('Spread')]),
        ('uB', [P.format('Ratior'), P.format('Ratiog'), P.format('Ratiob'), '0']),
        ('uD', [X['scale'], Q['g'], 'parent().par.Source.menuIndex', P.format('Core')]),
    ])
    gl.comment = 'halation glow: per-channel gaussian over the pyramid levels (R widest), at the gather res (Quality).'
    g = H['compute'](m, 'fx', sh['fx'], [in1, gl], extend='hold', filt='linear')
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), P.format('Intensity'), 'parent().par.Blend.menuIndex', Q['g']]),
        ('uC', [P.format('Tintr'), P.format('Tintg'), P.format('Tintb'), '0']),
    ])
    g.comment = 'halation: the glow (bilinear from the gather res) x tint x Intensity, add / screen.'
    sel = H['outsel'](m, in1, g)
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Extract', 'role': 'process', 'ops': ['ext', 'ext_compute'] + H['pyr_ops'],
         'body': 'Half/quarter box mean + soft knee, padded to 128; pyra / pyrb: [1 3 3 1] levels 1..7 (centred).'},
        {'title': '3 Halation', 'role': 'process', 'ops': ['glow', 'glow_compute', 'fx', 'fx_compute'],
         'body': 'glow: gather per channel (Radius x ratio) at the gather res; fx: tint, add / screen at full res.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
