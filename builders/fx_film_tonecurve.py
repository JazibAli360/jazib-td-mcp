# fx_film_tonecurve - FX_film module 'tonecurve' (FX3 F1 + S4): the grade's tone stage + the display stage.
# One compute pass: decode (sRGB / linear) -> Exposure (stops) -> Contrast around Pivot (scene-linear) -> Curve (ACES
# fit Narkowicz, ACES RRT+ODT fit Hill, Hable, Reinhard extended, Lottes parametric; per channel or on luminance) ->
# Saturation, Highlight desat -> Softclip (chroma compress so no channel tops 1, hue kept) -> encode -> Amount mix ->
# DISPLAY DITHER (a mode of this grade, not a module: Bayer 8x8 / IGN / white / TPDF to Bits, before 8-bit out).
# Maths: builders/fx_film_logic.py (tone_rgb, quantize, bayer_index, ign). Amount 0 = exact passthrough. ASCII only.

MODULE = 'tonecurve'

PAGES = [
    ('Tone', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Inspace', 'Menu', 'srgb', {'names': ['srgb', 'linear'], 'labels': ['sRGB-encoded in', 'Linear in']}),
        ('Exposure', 'Float', 0.0, {'min': -6, 'max': 6, 'label': 'Exposure (stops)'}),
        ('Curve', 'Menu', 'aces_fit', {'names': ['off', 'aces_fit', 'aces_hill', 'hable', 'reinhard', 'lottes'],
                                       'labels': ['Off', 'ACES fit (Narkowicz)', 'ACES RRT+ODT (Hill)', 'Hable filmic',
                                                  'Reinhard extended', 'Parametric (Lottes)']}),
        ('Curvemode', 'Menu', 'channel', {'names': ['channel', 'luma'], 'labels': ['Per channel', 'Luminance (hue kept)']}),
        ('Contrast', 'Float', 1.0, {'min': 0.3, 'max': 2.5, 'label': 'Contrast'}),
        ('Pivot', 'Float', 0.18, {'min': 0.01, 'max': 1, 'label': 'Contrast pivot (linear)'}),
        ('Whitepoint', 'Float', 11.2, {'min': 1, 'max': 16, 'label': 'White point (Hable/Reinhard/Lottes)'}),
        ('Lcontrast', 'Float', 1.6, {'min': 0.5, 'max': 3, 'label': 'Lottes contrast'}),
        ('Shoulder', 'Float', 0.977, {'min': 0.5, 'max': 1.5, 'label': 'Lottes shoulder'}),
        ('Saturation', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Saturation'}),
        ('Hdesat', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Highlight desat'}),
    ]),
    ('Display', [
        ('Outspace', 'Menu', 'same', {'names': ['same', 'srgb', 'linear'], 'labels': ['Same as in', 'sRGB', 'Linear']}),
        ('Softclip', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Soft clip (gamut)'}),
        ('Dither', 'Menu', 'off', {'names': ['off', 'bayer8', 'ign', 'white', 'tpdf'],
                                   'labels': ['Off (float out)', 'Bayer 8x8', 'Interleaved gradient', 'White noise',
                                              'Triangular (TPDF)']}),
        ('Bits', 'Int', 8, {'min': 1, 'max': 12, 'label': 'Display bits'}),
        ('Ditheramp', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Dither amount (LSB)'}),
        ('Ditheranim', 'Toggle', False, {'label': 'Animate dither'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['Tone', 'Display']

PRESETS = [
    (1, 'aces filmic', {'Amount': 1.0, 'Curve': 1, 'Curvemode': 0, 'Exposure': 0.0, 'Contrast': 1.0,
                        'Saturation': 1.0, 'Hdesat': 0.3, 'Dither': 0}),
    (2, 'hable soft', {'Amount': 1.0, 'Curve': 3, 'Curvemode': 0, 'Exposure': 1.0, 'Whitepoint': 11.2,
                       'Contrast': 0.9, 'Saturation': 1.05, 'Hdesat': 0.0, 'Dither': 0}),
    (3, 'punchy lottes', {'Amount': 1.0, 'Curve': 5, 'Curvemode': 1, 'Lcontrast': 1.9, 'Shoulder': 0.97,
                          'Whitepoint': 8.0, 'Contrast': 1.15, 'Saturation': 1.15, 'Dither': 0}),
    (4, 'flat log', {'Amount': 1.0, 'Curve': 4, 'Curvemode': 1, 'Whitepoint': 4.0, 'Contrast': 0.7,
                     'Saturation': 0.75, 'Hdesat': 0.0, 'Dither': 0}),
    (5, 'display dither', {'Amount': 1.0, 'Curve': 0, 'Exposure': 0.0, 'Contrast': 1.0, 'Saturation': 1.0,
                           'Hdesat': 0.0, 'Softclip': 1.0, 'Dither': 2, 'Bits': 8, 'Ditheramp': 1.0}),
]

SHADER = """// FX_film tonecurve (compute). in0 = picture.
// uA amount inspace exposure curve | uB contrast pivot white curvemode | uC lottesA lottesD saturation hdesat
// uD outspace(0 same 1 srgb 2 linear) dither bits ditheramp | uE tick softclip seed -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
uniform vec4 uE;
%s
float acesfit(float x) { return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0); }
vec3 aceshill(vec3 c) {
    vec3 v = vec3(dot(vec3(0.59719, 0.35458, 0.04823), c), dot(vec3(0.07600, 0.90834, 0.01566), c),
                  dot(vec3(0.02840, 0.13383, 0.83777), c));
    v = (v * (v + 0.0245786) - 0.000090537) / (v * (0.983729 * v + 0.4329510) + 0.238081);
    return clamp(vec3(dot(vec3(1.60475, -0.53108, -0.07367), v), dot(vec3(-0.10208, 1.10813, -0.00605), v),
                      dot(vec3(-0.00327, -0.07276, 1.07602), v)), 0.0, 1.0);
}
float hablef(float x) { return ((x * (0.15 * x + 0.05) + 0.004) / (x * (0.15 * x + 0.50) + 0.06)) - 0.02 / 0.30; }
float curve1(float x, int cv) {
    float W = uB.z;
    if (cv == 1) return acesfit(x);
    if (cv == 3) return hablef(x) / hablef(W);
    if (cv == 4) return x * (1.0 + x / (W * W)) / (1.0 + x);
    if (cv == 5) {                                            // Lottes 2016, mid 0.18 -> 0.18
        float a = uC.x, d = uC.y, ad = a * d, mi = 0.18, mo = 0.18;
        float den = (pow(W, ad) - pow(mi, ad)) * mo;
        float b = (-pow(mi, a) + pow(W, a) * mo) / den;
        float c = (pow(W, ad) * pow(mi, a) - pow(W, a) * pow(mi, ad) * mo) / den;
        x = max(x, 0.0);
        return pow(x, a) / (pow(x, ad) * b + c);
    }
    return x;
}
uint bayer8(ivec2 p) {                                         // fx_film_logic.bayer_index
    uint x = uint(p.x) & 7u, y = (uint(p.x) ^ uint(p.y)) & 7u, v = 0u;
    for (int b = 0; b < 3; b++) {
        v |= ((y >> uint(b)) & 1u) << uint(2 * (2 - b) + 1);
        v |= ((x >> uint(b)) & 1u) << uint(2 * (2 - b));
    }
    return v;
}
float dthr(ivec2 p, int type, uint tick, uint seed) {        // threshold t in [0, 1) (tpdf: -0.5..1.5, mean 0.5)
    if (type == 1) {
        ivec2 o = tick == 0u ? ivec2(0) : ivec2(int(lb32(tick) & 7u), int(lb32(tick + 77u) & 7u));
        return (float(bayer8(p + o)) + 0.5) / 64.0;
    }
    if (type == 2) {
        vec2 q = vec2(p) + 5.588238 * float(tick);
        return fract(52.9829189 * fract(0.06711056 * q.x + 0.00583715 * q.y));
    }
    if (type == 3) return hsh(p, seed + tick * 7919u);
    return hsh(p, seed + tick * 7919u) + hsh(p, seed * 31u + 17u + tick * 7919u) - 0.5;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    int ins = int(uA.y + 0.5);
    vec3 x = ins == 0 ? srgb2lin(c.rgb) : c.rgb;
    x *= exp2(uA.z);
    x = uB.y * pow(max(x, vec3(0.0)) / uB.y, vec3(uB.x));
    int cv = int(uA.w + 0.5);
    if (cv == 2) x = aceshill(x);
    else if (uB.w > 0.5) { float y = luma(x); x *= curve1(y, cv) / max(y, 1e-6); }
    else x = vec3(curve1(x.r, cv), curve1(x.g, cv), curve1(x.b, cv));
    x = mix(vec3(luma(x)), x, uC.z);
    x = mix(x, vec3(luma(x)), uC.w * smoothstep(0.5, 1.0, luma(x)));
    float m = max(x.r, max(x.g, x.b)), yl = min(luma(x), 1.0);
    if (uE.y > 0.0 && m > 1.0 && yl < m) x = mix(x, mix(x, vec3(yl), (m - 1.0) / (m - yl)), uE.y);
    int os = int(uD.x + 0.5) == 0 ? ins : int(uD.x + 0.5) - 1;
    vec3 o = mix(c.rgb, os == 0 ? lin2srgb(x) : x, uA.x);
    int dt = int(uD.y + 0.5);
    if (dt > 0) {                                              // display dither: floor(v L + 0.5 + amp (t - 0.5)) / L
        float L = exp2(floor(uD.z + 0.5)) - 1.0;
        float t = dthr(p, dt, uint(uE.x), uint(uE.z));
        o = floor(o * L + 0.5 + uD.w * (t - 0.5)) / L;
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(o, c.a));
}
"""


def shaders(H):
    return {'fx': SHADER % H['LIB']}


def build(m, H):
    """in1 -> fx (one compute pass) -> out1."""
    mk, P = H['mk'], H['P']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', shaders(H)['fx'], [in1])
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), 'parent().par.Inspace.menuIndex', P.format('Exposure'),
                'parent().par.Curve.menuIndex']),
        ('uB', [P.format('Contrast'), 'max(%s, 1e-4)' % P.format('Pivot'), P.format('Whitepoint'),
                'parent().par.Curvemode.menuIndex']),
        ('uC', [P.format('Lcontrast'), P.format('Shoulder'), P.format('Saturation'), P.format('Hdesat')]),
        ('uD', ['parent().par.Outspace.menuIndex', 'parent().par.Dither.menuIndex', P.format('Bits'),
                P.format('Ditheramp')]),
        ('uE', ['(absTime.frame % 4096) if parent().par.Ditheranim.eval() else 0', P.format('Softclip'),
                P.format('Seed'), '0']),
    ])
    g.comment = 'tonecurve: exposure, contrast, filmic curve, sat; display dither (Bits). Amount 0 = exact passthrough.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Tone + display', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass: curve, then the display dither (a mode of the grade, Display page).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
