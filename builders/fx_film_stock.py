# fx_film_stock - FX_film module 'stock' (FX3 F2): a LUT-free film-stock engine in one compute pass.
# decode -> dye crosstalk matrix (Mix rows) -> process on the records (Two-strip Technicolor: red record -> red-orange
# dye, green record -> its complement; Three-strip: white-preserving crosstalk that pushes the primaries apart; B&W:
# filter-weighted mono) -> per-channel density S-curve in stops (Slope / Offset per channel, Toe / Shoulder steepness,
# White) -> process on the print (Bleach bypass: overlay with its own luma; Cross process: R steep, G mild, B flat +
# lifted) -> saturation by luma (shadow / mid / high) -> split tone (shadow / highlight tint, Balance) -> Fade (black
# lift) -> encode -> Amount mix. Presets are descriptors ("warm print", "tungsten night"), never a stock's trademark,
# and no claim to match one (FX3 s3). Maths: builders/fx_film_logic.py (stock_curve, bleach, tech2, tech3).
# Amount 0 = exact passthrough. ASCII only.

MODULE = 'stock'
PROCESS_LABELS = ['Print (normal)', 'Bleach bypass', 'Cross process', 'Two-strip Technicolor',
                  'Three-strip Technicolor', 'Black and white']

PAGES = [
    ('Stock', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Process', 'Menu', 'print', {'names': ['print', 'bleach', 'cross', 'tech2', 'tech3', 'bw'],
                                      'labels': PROCESS_LABELS}),
        ('Inspace', 'Menu', 'srgb', {'names': ['srgb', 'linear'], 'labels': ['sRGB-encoded in', 'Linear in']}),
        ('Slope', 'RGB', (1.0, 1.0, 1.0), {'label': 'Contrast per channel'}),
        ('Offset', 'RGB', (0.0, 0.0, 0.0), {'label': 'Offset per channel (stops)'}),
        ('Toe', 'Float', 1.4, {'min': 0.3, 'max': 3, 'label': 'Toe steepness'}),
        ('Shoulder', 'Float', 1.4, {'min': 0.3, 'max': 3, 'label': 'Shoulder steepness'}),
        ('White', 'Float', 1.6, {'min': 0.5, 'max': 4, 'label': 'Print white (linear)'}),
        ('Satshadow', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Sat shadows'}),
        ('Satmid', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Sat mids'}),
        ('Sathigh', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Sat highlights'}),
        ('Shadowtint', 'RGB', (1.0, 1.0, 1.0), {'label': 'Shadow tint'}),
        ('Hightint', 'RGB', (1.0, 1.0, 1.0), {'label': 'Highlight tint'}),
        ('Tintbalance', 'Float', 0.0, {'min': -0.5, 'max': 0.5, 'label': 'Tint balance'}),
        ('Fade', 'Float', 0.0, {'min': 0, 'max': 0.3, 'label': 'Fade (black lift)'}),
    ]),
    ('Process', [
        ('Bleach', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Bleach amount'}),
        ('Cross', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Cross amount'}),
        ('Dye', 'RGB', (1.0, 0.42, 0.16), {'label': 'Two-strip red dye'}),
        ('Techamount', 'Float', 0.15, {'min': 0, 'max': 0.5, 'label': 'Three-strip separation'}),
        ('Bwfilter', 'RGB', (0.30, 0.59, 0.11), {'label': 'B&W filter weights'}),
        ('Mixr', 'RGB', (1.0, 0.0, 0.0), {'label': 'Crosstalk: red from'}),
        ('Mixg', 'RGB', (0.0, 1.0, 0.0), {'label': 'Crosstalk: green from'}),
        ('Mixb', 'RGB', (0.0, 0.0, 1.0), {'label': 'Crosstalk: blue from'}),
    ]),
]
PANEL_PAGES = ['Stock', 'Process']

PRESETS = [
    (1, 'warm print', {'Amount': 1.0, 'Process': 0, 'Sloper': 1.0, 'Slopeg': 1.0, 'Slopeb': 0.95, 'Offsetr': 0.1,
                       'Offsetg': 0.0, 'Offsetb': -0.15, 'Shadowtintr': 0.94, 'Shadowtintg': 1.0, 'Shadowtintb': 1.04,
                       'Hightintr': 1.05, 'Hightintg': 1.0, 'Hightintb': 0.9, 'Satmid': 1.1, 'Fade': 0.01}),
    (2, 'tungsten night', {'Amount': 1.0, 'Process': 0, 'Offsetr': -0.1, 'Offsetg': 0.0, 'Offsetb': 0.25,
                           'Shadowtintr': 0.88, 'Shadowtintg': 1.0, 'Shadowtintb': 1.12, 'Hightintr': 1.1,
                           'Hightintg': 1.0, 'Hightintb': 0.88, 'Satshadow': 0.9, 'Sathigh': 0.85, 'Toe': 1.6}),
    (3, 'bleach bypass', {'Amount': 1.0, 'Process': 1, 'Bleach': 0.8, 'Satmid': 0.75, 'Toe': 1.6, 'Shoulder': 1.6}),
    (4, 'cross process', {'Amount': 1.0, 'Process': 2, 'Cross': 1.0, 'Satmid': 1.2, 'Offsetb': -0.2}),
    (5, 'two-strip', {'Amount': 1.0, 'Process': 3, 'Dyer': 1.0, 'Dyeg': 0.42, 'Dyeb': 0.16, 'Satmid': 1.0}),
]

SHADER = """// FX_film stock (compute). in0 = picture. All in linear light between decode and encode.
// uA amount process inspace white | uB slope rgb toe | uC offset rgb shoulder | uD sat shadow mid high fade
// uE shadow tint rgb balance | uF highlight tint rgb bleach | uG cross techamount - - | uH dye rgb -
// uI bw filter rgb - | uJ/uK/uL crosstalk rows (red / green / blue from rgb)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
uniform vec4 uE;
uniform vec4 uF;
uniform vec4 uG;
uniform vec4 uH;
uniform vec4 uI;
uniform vec4 uJ;
uniform vec4 uK;
uniform vec4 uL;
%s
float dcurve(float x, float slope, float offs) {              // fx_film_logic.stock_curve
    float lc = slope * log2(max(x, 1e-6) / 0.18) + offs;
    float t = clamp((lc + 1.0) * 0.5, 0.0, 1.0); t = t * t * (3.0 - 2.0 * t);
    float k = mix(uB.w, uC.w, t);
    float W = uA.w;
    return W / (1.0 + exp2(-lc * k) * (W / 0.18 - 1.0));
}
float sig(float v, float k) { v = clamp(v, 0.0, 1.0); return v < 0.5 ? 0.5 * pow(2.0 * v, k) : 1.0 - 0.5 * pow(2.0 - 2.0 * v, k); }
vec3 bleachb(vec3 base, float op) {
    float lum = luma(base);
    float L = clamp(10.0 * (lum - 0.45), 0.0, 1.0);
    vec3 r1 = 2.0 * base * lum, r2 = 1.0 - 2.0 * (1.0 - lum) * (1.0 - base);
    return mix(base, mix(r1, r2, L), op);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    int ins = int(uA.z + 0.5), pr = int(uA.y + 0.5);
    vec3 x = ins == 0 ? srgb2lin(c.rgb) : c.rgb;
    x = vec3(dot(uJ.xyz, x), dot(uK.xyz, x), dot(uL.xyz, x));              // dye crosstalk
    if (pr == 3) { float rr = x.r, gr = 0.5 * (x.g + x.b); x = rr * uH.rgb + gr * (1.0 - uH.rgb); }
    else if (pr == 4) { float s = x.r + x.g + x.b; x = max((1.0 + 3.0 * uG.y) * x - uG.y * s, vec3(0.0)); }
    else if (pr == 5) { x = vec3(dot(x, uI.rgb) / max(uI.r + uI.g + uI.b, 1e-4)); }
    vec3 y = vec3(dcurve(x.r, uB.x, uC.x), dcurve(x.g, uB.y, uC.y), dcurve(x.b, uB.z, uC.z));
    if (pr == 1) y = srgb2lin(bleachb(lin2srgb(y), uF.w));
    else if (pr == 2) {
        vec3 d = lin2srgb(y);
        d = mix(d, vec3(sig(d.r, 1.5), sig(d.g, 1.2), 0.25 + 0.5 * d.b), uG.x);
        y = srgb2lin(d);
    }
    float L = clamp(luma(lin2srgb(y)), 0.0, 1.0);
    float sat = L < 0.5 ? mix(uD.x, uD.y, L * 2.0) : mix(uD.y, uD.z, L * 2.0 - 1.0);
    y = mix(vec3(luma(y)), y, sat);
    float tb = clamp(L + uE.w, 0.0, 1.0);
    y *= mix(uE.rgb, uF.rgb, tb * tb * (3.0 - 2.0 * tb));
    y = uD.w + y * (1.0 - uD.w);
    vec3 o = ins == 0 ? lin2srgb(y) : y;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(mix(c.rgb, o, uA.x), c.a));
}
"""


def shaders(H):
    return {'fx': SHADER % H['LIB']}


def _rgb(name, P):
    return [P.format(name + 'r'), P.format(name + 'g'), P.format(name + 'b')]


def build(m, H):
    """in1 -> fx (one compute pass) -> out1."""
    mk, P = H['mk'], H['P']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', shaders(H)['fx'], [in1])
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), 'parent().par.Process.menuIndex', 'parent().par.Inspace.menuIndex',
                P.format('White')]),
        ('uB', _rgb('Slope', P) + [P.format('Toe')]),
        ('uC', _rgb('Offset', P) + [P.format('Shoulder')]),
        ('uD', [P.format('Satshadow'), P.format('Satmid'), P.format('Sathigh'), P.format('Fade')]),
        ('uE', _rgb('Shadowtint', P) + [P.format('Tintbalance')]),
        ('uF', _rgb('Hightint', P) + [P.format('Bleach')]),
        ('uG', [P.format('Cross'), P.format('Techamount'), '0', '0']),
        ('uH', _rgb('Dye', P) + ['0']),
        ('uI', _rgb('Bwfilter', P) + ['0']),
        ('uJ', _rgb('Mixr', P) + ['0']),
        ('uK', _rgb('Mixg', P) + ['0']),
        ('uL', _rgb('Mixb', P) + ['0']),
    ])
    g.comment = 'stock: crosstalk -> process -> density curve per channel -> sat by luma -> split tone -> fade.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Stock', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass; Process = print / bleach / cross / two-strip / three-strip / B&W.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
