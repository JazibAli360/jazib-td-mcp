# fx_film_ca - FX_film module 'ca' (FX3 L5): PHYSICAL chromatic aberration, one compute pass. (FX_glitch `chroma`
# stays the stylised split; this one follows a lens: displacement grows with the radius as K1 r^2 + K2 r^4 (Brown
# radial terms, px at the half-diagonal), wavelengths bend by Cauchy 1/lambda^2 (blue ~2.3x red at Curve 1, so the
# fringe is blue/violet-heavy like real glass), Spectral = N wavelength taps weighted by a CIE-like rgb response and
# normalised per channel (white stays white), Longitudinal = per-wavelength defocus blur (mip lod, `inputfiltertype
# mipmap`: wider for the wavelengths furthest from green), Fringe = purple fringing where a bright blurred
# neighbourhood meets darker pixels. Anisotropy x / y (sensor CA along one axis). Maths: fx_film_logic.cauchy_delta,
# spectral_rgb, ca_shift_px. Amount 0 = exact passthrough. ASCII only.

MODULE = 'ca'

PAGES = [
    ('Lens CA', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'spectral', {'names': ['rgb', 'spectral'], 'labels': ['RGB (3 taps)', 'Spectral (N taps)']}),
        ('Lateral', 'Float', 6.0, {'min': -40, 'max': 40, 'label': 'Lateral K1 (px at edge, red)'}),
        ('Lateral4', 'Float', 0.0, {'min': -40, 'max': 40, 'label': 'Lateral K2 (r^4)'}),
        ('Curve', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Dispersion (linear -> Cauchy)'}),
        ('Taps', 'Int', 8, {'min': 3, 'max': 16, 'label': 'Spectral taps'}),
        ('Longitudinal', 'Float', 0.0, {'min': 0, 'max': 16, 'label': 'Longitudinal blur px'}),
        ('Fringe', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Purple fringe'}),
        ('Fringethr', 'Float', 0.8, {'min': 0, 'max': 2, 'label': 'Fringe threshold'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Optical centre x'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Optical centre y'}),
        ('Anisox', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Anisotropy x'}),
        ('Anisoy', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Anisotropy y'}),
    ]),
]
PANEL_PAGES = ['Lens CA']

PRESETS = [
    (1, 'clean prime', {'Amount': 1.0, 'Mode': 0, 'Lateral': 2.0, 'Lateral4': 0.0, 'Curve': 1.0, 'Longitudinal': 0.0,
                        'Fringe': 0.0}),
    (2, 'vintage zoom', {'Amount': 1.0, 'Mode': 1, 'Lateral': 8.0, 'Lateral4': 4.0, 'Curve': 1.0, 'Taps': 8,
                         'Longitudinal': 2.0, 'Fringe': 0.3}),
    (3, 'cheap wide', {'Amount': 1.0, 'Mode': 1, 'Lateral': 16.0, 'Lateral4': 10.0, 'Curve': 0.8, 'Taps': 12,
                       'Longitudinal': 4.0, 'Fringe': 0.6, 'Fringethr': 0.7}),
    (4, 'prism dream', {'Amount': 1.0, 'Mode': 1, 'Lateral': 30.0, 'Lateral4': 0.0, 'Curve': 0.3, 'Taps': 16,
                        'Longitudinal': 6.0, 'Fringe': 0.0}),
    (5, 'sensor fringe', {'Amount': 1.0, 'Mode': 0, 'Lateral': 4.0, 'Anisox': 1.0, 'Anisoy': 0.0, 'Fringe': 1.0,
                          'Fringethr': 0.6}),
]

SHADER = """// FX_film ca (compute). in0 = picture (mipmap filter for the longitudinal blur; texelFetch stays exact).
// uA amount mode K1 K2 | uB centre x y (px) aniso x y | uC taps longitudinal curve fringe | uD fringethr - - -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
%s
float cdelta(float t) {                                      // fx_film_logic.cauchy_delta
    float lam = 550.0 + 150.0 * t;
    float d = (1.0 / (550.0 * 550.0) - 1.0 / (lam * lam)) / (1.0 / (550.0 * 550.0) - 1.0 / (700.0 * 700.0));
    return mix(t, d, uC.z);
}
vec3 sresp(float t) {                                         // fx_film_logic.spectral_rgb
    float lam = 550.0 + 150.0 * t;
    float r = exp(-pow((lam - 600.0) / 45.0, 2.0)) + 0.25 * exp(-pow((lam - 445.0) / 25.0, 2.0));
    return vec3(r, exp(-pow((lam - 550.0) / 45.0, 2.0)), exp(-pow((lam - 450.0) / 35.0, 2.0)));
}
vec2 SZ; vec2 P; vec2 DIR; float D;
vec4 tapAt(float t) {
    float dt = cdelta(t);
    vec2 q = P + DIR * D * dt;
    float b = uC.y * abs(dt);
    return textureLod(sTD2DInputs[0], q / SZ, b > 1.0 ? log2(b) : 0.0);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    SZ = vec2(isz); P = vec2(p) + 0.5;
    vec2 v = P - uB.xy;
    float rmax = 0.5 * length(SZ);
    float rn = length(v * uB.zw) / rmax;
    DIR = length(v) > 1e-4 ? v / length(v) : vec2(0.0);
    D = (uA.z * rn * rn + uA.w * rn * rn * rn * rn) * uA.x;
    vec3 o;
    if (int(uA.y + 0.5) == 0) {
        o = vec3(tapAt(1.0).r, tapAt(0.0).g, tapAt(-1.0).b);
    } else {
        int n = int(clamp(uC.x, 3.0, 16.0));
        vec3 acc = vec3(0.0), ws = vec3(0.0);
        for (int k = 0; k < 16; k++) {
            if (k >= n) break;
            float t = -1.0 + 2.0 * float(k) / float(n - 1);
            vec3 w = sresp(t);
            acc += w * tapAt(t).rgb;
            ws += w;
        }
        o = acc / max(ws, vec3(1e-6));
    }
    if (uC.w > 0.0) {                                          // purple fringing at bright edges
        float lb = luma(textureLod(sTD2DInputs[0], P / SZ, 3.0).rgb);
        o += uC.w * uA.x * smoothstep(uD.x, uD.x + 0.2, lb) * max(lb - luma(c.rgb), 0.0) * vec3(0.55, 0.12, 1.0);
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(o, c.a));
}
"""


def shaders(H):
    return {'fx': SHADER % H['LIB']}


def build(m, H):
    """in1 -> fx (one compute pass, mipmap input) -> out1."""
    mk, P = H['mk'], H['P']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', shaders(H)['fx'], [in1], extend='hold', filt='mipmap')
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Lateral'), P.format('Lateral4')]),
        ('uB', ['%s * me.inputs[0].width' % P.format('Centerx'), '%s * me.inputs[0].height' % P.format('Centery'),
                P.format('Anisox'), P.format('Anisoy')]),
        ('uC', [P.format('Taps'), P.format('Longitudinal'), P.format('Curve'), P.format('Fringe')]),
        ('uD', [P.format('Fringethr'), '0', '0', '0']),
    ])
    # mips only while something reads them (longitudinal blur / fringe); without mips textureLod reads level 0
    H['expr'](g.par.inputfiltertype, "'mipmap' if parent().par.Longitudinal.eval() > 0 or parent().par.Fringe.eval() > 0"
              " else 'linear'")
    g.comment = 'ca: radial K1 r^2 + K2 r^4, Cauchy dispersion, RGB / spectral taps, longitudinal blur, purple fringe.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Lens CA', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass (input mips for the longitudinal blur).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
