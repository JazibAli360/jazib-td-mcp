# fx_film_star - FX_film module 'star' (FX3 L3 + G-STARGLOW): cross-screen / star-filter spikes from highlights.
# in1 -> ext (rack EXT at half / quarter res, soft knee, padded to 64, mipmap) -> `star` (at the extract size: for
# each of Points / 2 lines at Rotation + k 180 / lines, both arms, Taps samples at distances Length x (j / Taps) ^
# Taper: fine steps near the light (a thin hot core), coarse far out; each tap reads the mip level that matches its
# step so no light falls between taps, weighted exp(-Falloff t) x step, optional Rainbow along the arm) -> `fx`
# (bilinear lookup, tint, add) -> out_sel (Amount 0 = in1) -> out1. Arm angles: fx_film_logic.star_angles. ASCII only.

MODULE = 'star'

PAGES = [
    ('Star', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Intensity', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Intensity'}),
        ('Threshold', 'Float', 0.85, {'min': 0, 'max': 4, 'label': 'Threshold'}),
        ('Knee', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Knee'}),
        ('Points', 'Int', 6, {'min': 2, 'max': 16, 'label': 'Points (even)'}),
        ('Length', 'Float', 220.0, {'min': 10, 'max': 1200, 'label': 'Length px'}),
        ('Falloff', 'Float', 3.0, {'min': 0, 'max': 10, 'label': 'Falloff'}),
        ('Rotation', 'Float', 15.0, {'min': -180, 'max': 180, 'label': 'Rotation deg'}),
        ('Taper', 'Float', 2.0, {'min': 1, 'max': 3, 'label': 'Tap spacing taper'}),
        ('Taps', 'Int', 16, {'min': 4, 'max': 32, 'label': 'Taps per arm'}),
        ('Rainbow', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Rainbow along arm'}),
        ('Hue', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Rainbow hue'}),
        ('Tint', 'RGB', (1.0, 1.0, 1.0), {'label': 'Tint'}),
        ('Spin', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Spin deg/s'}),
        ('Quality', 'Menu', 'half', {'names': ['half', 'quarter'], 'labels': ['Half res', 'Quarter res']}),
    ]),
]
PANEL_PAGES = ['Star']

PRESETS = [
    (1, 'six point', {'Amount': 1.0, 'Intensity': 1.5, 'Points': 6, 'Length': 220.0, 'Falloff': 3.0, 'Rotation': 15.0,
                      'Rainbow': 0.3, 'Spin': 0.0}),
    (2, 'cross screen', {'Amount': 1.0, 'Intensity': 2.0, 'Points': 4, 'Length': 320.0, 'Falloff': 2.5,
                         'Rotation': 45.0, 'Rainbow': 0.0}),
    (3, 'eight sparkle', {'Amount': 1.0, 'Intensity': 1.2, 'Points': 8, 'Length': 140.0, 'Falloff': 4.0,
                          'Rotation': 0.0, 'Rainbow': 0.6, 'Spin': 10.0}),
    (4, 'long diffraction', {'Amount': 1.0, 'Intensity': 3.0, 'Points': 6, 'Length': 600.0, 'Falloff': 2.0,
                             'Taper': 2.5, 'Taps': 24, 'Rainbow': 0.8, 'Quality': 1}),
]

STAR = """// FX_film star (compute) at the extract size. in0 = EXT (mipmap, extend zero).
// uT0 lines length(px) falloff rot(rad) | uT1 taps scale validW validH | uT2 rainbow hue taper -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uT0;
uniform vec4 uT1;
uniform vec4 uT2;
%s
void main() {
    ivec2 q = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (q.x >= osz.x || q.y >= osz.y) return;
    if (float(q.x) >= uT1.z || float(q.y) >= uT1.w) { TDImageStoreOutput(0, ivec3(q, 0), vec4(0.0)); return; }
    vec2 pad = vec2(textureSize(sTD2DInputs[0], 0));
    vec2 uv0 = (vec2(q) + 0.5) / pad;
    int lines = int(clamp(uT0.x, 1.0, 8.0)), taps = int(clamp(uT1.x, 1.0, 32.0));
    float sc = uT1.y, len = uT0.y;
    vec3 acc = vec3(0.0);
    for (int l = 0; l < 8; l++) {
        if (l >= lines) break;
        float a = uT0.w + float(l) * 3.14159265 / float(lines);
        vec2 d = vec2(cos(a), sin(a));
        for (int j = 1; j <= 32; j++) {
            if (j > taps) break;
            float t = float(j) / float(taps);
            float dist = len * pow(t, uT2.z);
            float stp = max(len * (pow(t, uT2.z) - pow(float(j - 1) / float(taps), uT2.z)) / sc, 1.0);
            float lod = clamp(log2(stp), 0.0, 6.0);
            vec2 o = d * dist / sc / pad;
            vec3 s = textureLod(sTD2DInputs[0], uv0 + o, lod).rgb + textureLod(sTD2DInputs[0], uv0 - o, lod).rgb;
            vec3 tint = mix(vec3(1.0), hue2rgb(fract(uT2.y + 0.8 * t)), uT2.x);
            acc += s * tint * exp(-uT0.z * t) * stp;
        }
    }
    TDImageStoreOutput(0, ivec3(q, 0), vec4(acc / float(taps), 1.0));
}
"""

FX = """// FX_film star composite (compute). in0 = picture, in1 = star buffer (bilinear).
// uA amount intensity scale - | uB tint rgb -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    vec2 ssz = vec2(textureSize(sTD2DInputs[1], 0));
    vec3 s = texture(sTD2DInputs[1], ((vec2(p) + 0.5) / uA.z) / ssz).rgb;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(c.rgb + uA.x * uA.y * uB.rgb * s, c.a));
}
"""

SCALE = "(2 if parent().par.Quality.eval() == 'half' else 4)"


def shaders(H):
    return {'star': STAR % H['LIB'], 'fx': FX}


def build(m, H):
    """in1 -> ext (rack EXT) -> star (arms at extract size) -> fx (add) -> out_sel -> out1."""
    mk, P = H['mk'], H['P']
    T = shaders(H)
    in1 = mk(m, inTOP, 'in1')
    ext, X = H['ext'](m, 'ext', in1, SCALE, P.format('Threshold'), 'max(%s, 1e-4)' % P.format('Knee'),
                      byluma='0', mode='0', mult=64)
    st = H['compute'](m, 'star', T['star'], [ext], fmt='rgba16float', extend='zero', filt='mipmap')
    H['uniforms'](st, [
        ('uT0', ['max(1, int(%s) // 2)' % P.format('Points'), P.format('Length'), P.format('Falloff'),
                 'math.radians(%s + %s * absTime.seconds)' % (P.format('Rotation'), P.format('Spin'))]),
        ('uT1', [P.format('Taps'), X['scale'], X['vw'], X['vh']]),
        ('uT2', [P.format('Rainbow'), P.format('Hue'), P.format('Taper'), '0']),
    ])
    st.comment = 'star: Points/2 lines, both arms, tapered taps on matching mip levels (extract size).'
    g = H['compute'](m, 'fx', T['fx'], [in1, st], extend='zero')
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), P.format('Intensity'), X['scale'], '0']),
        ('uB', [P.format('Tintr'), P.format('Tintg'), P.format('Tintb'), '0']),
    ])
    g.comment = 'star composite: bilinear lookup, tint, add.'
    sel = H['outsel'](m, in1, g)
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Extract', 'role': 'process', 'ops': ['ext', 'ext_compute'],
         'body': 'Half/quarter box mean + soft knee, padded to 64.'},
        {'title': '3 Star arms', 'role': 'process', 'ops': ['star', 'star_compute']},
        {'title': '4 Composite', 'role': 'process', 'ops': ['fx', 'fx_compute']},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
