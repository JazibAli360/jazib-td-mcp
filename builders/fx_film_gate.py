# fx_film_gate - FX_film module 'gate' (FX3 F8 + L7 + L12; FX0 row 79): film gate / format overlays and vintage-lens
# character in ONE compute pass.
#   Gate: aspect aperture (2.39 / 2.00 / 1.85 / 1.66 / 1.43 / 4:3 / 1:1 / custom) on the vertical canvas, Fitmode mask
#   (bars over the picture) / fit (whole frame inside) / fill (crop to fill), Rotate (picture turned 90 deg inside a
#   tall aperture), rounded + soft gate edge, gate jitter (loose gate), bar colour.
#   Strip: film strip with Frames stacked cells, frame lines, side bands with sprocket holes (4-perf / 2-perf /
#   super 8 / 16 mm), edge marks, scrolling (frames/s or Bpm: one frame per Beatsperframe beats).
#   Lens (on the picture, in source coordinates): barrel / pincushion Distortion (k1 r^2), cos^4 Vignette (+ oval,
#   edge colour cast), mechanical vignette, soft corners (field curvature: disc blur grows with r^2), Petzval Swirl
#   (tangential blur grows with r^2), spherical-aberration Glow and lost Microcontrast (local mean, Glowradius).
# Maths: builders/fx_film_gate_logic.py. Amount 0 = exact passthrough. ASCII only.

MODULE = 'gate'

LOGIC_PATH = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_film_gate_logic.py'
_GL = {}
with open(LOGIC_PATH) as _fh:
    exec(_fh.read(), _GL)

PAGES = [
    ('Gate', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Aspect', 'Menu', 'a239', {'names': _GL['ASPECTS'], 'labels': _GL['ASPECT_LABELS']}),
        ('Customaspect', 'Float', 2.0, {'min': 0.2, 'max': 4, 'label': 'Custom aspect (w/h)'}),
        ('Fitmode', 'Menu', 'mask', {'names': ['mask', 'fit', 'fill'],
                                     'labels': ['Mask (bars over picture)', 'Fit whole frame', 'Fill (crop)']}),
        ('Rotate', 'Toggle', False, {'label': 'Rotate 90 deg inside'}),
        ('Barcolour', 'RGB', (0.0, 0.0, 0.0), {'label': 'Bar colour'}),
        ('Gateround', 'Float', 0.0, {'min': 0, 'max': 120, 'label': 'Gate corner radius (px)'}),
        ('Gatesoft', 'Float', 1.0, {'min': 0, 'max': 60, 'label': 'Gate edge softness (px)'}),
        ('Gatejitter', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Gate jitter (px)'}),
        ('Seed', 'Int', 5, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Strip', [
        ('Strip', 'Toggle', False, {'label': 'Film strip'}),
        ('Frames', 'Int', 3, {'min': 1, 'max': 8, 'label': 'Frames visible'}),
        ('Frameline', 'Float', 14.0, {'min': 0, 'max': 80, 'label': 'Frame line (px)'}),
        ('Sideband', 'Float', 0.12, {'min': 0, 'max': 0.3, 'label': 'Side band (x width)'}),
        ('Sprockets', 'Menu', 'p4', {'names': _GL['SPROCKETS'],
                                     'labels': ['Off', '4-perf (35 mm)', '2-perf', 'Super 8 (one side)', '16 mm (one side)']}),
        ('Holew', 'Float', 0.5, {'min': 0.1, 'max': 1, 'label': 'Hole width (x band)'}),
        ('Holeh', 'Float', 0.45, {'min': 0.1, 'max': 1, 'label': 'Hole height (x pitch)'}),
        ('Holecolour', 'RGB', (0.92, 0.9, 0.85), {'label': 'Hole (light) colour'}),
        ('Stripcolour', 'RGB', (0.04, 0.03, 0.02), {'label': 'Film base colour'}),
        ('Edgemarks', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Edge marks'}),
        ('Drive', 'Menu', 'free', {'names': ['free', 'bpm'], 'labels': ['Free (Scroll)', 'Bpm']}),
        ('Scroll', 'Float', 0.0, {'min': -24, 'max': 24, 'label': 'Scroll (frames/s)'}),
        ('Bpm', 'Float', 120.0, {'min': 40, 'max': 200, 'label': 'Bpm'}),
        ('Beatsperframe', 'Float', 1.0, {'min': 0.25, 'max': 16, 'label': 'Beats per frame'}),
        ('Scrollphase', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Scroll phase (frames)'}),
    ]),
    ('Lens', [
        ('Distortion', 'Float', 0.0, {'min': -0.5, 'max': 0.5, 'label': 'Distortion k1 (+ barrel)'}),
        ('Vignette', 'Float', 0.0, {'min': 0, 'max': 3, 'label': 'Vignette (cos^4 k)'}),
        ('Vigoval', 'Float', 1.0, {'min': 0.3, 'max': 3, 'label': 'Vignette oval (x)'}),
        ('Vigcolour', 'RGB', (1.0, 0.85, 0.7), {'label': 'Vignette edge colour'}),
        ('Mechvig', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Mechanical vignette'}),
        ('Mechstart', 'Float', 0.8, {'min': 0, 'max': 1.2, 'label': 'Mechanical start (r)'}),
        ('Softcorners', 'Float', 0.0, {'min': 0, 'max': 40, 'label': 'Soft corners (px at corner)'}),
        ('Swirl', 'Float', 0.0, {'min': 0, 'max': 60, 'label': 'Swirl (px at corner)'}),
        ('Glow', 'Float', 0.0, {'min': 0, 'max': 3, 'label': 'Spherical glow'}),
        ('Glowradius', 'Float', 24.0, {'min': 2, 'max': 120, 'label': 'Glow / local radius (px)'}),
        ('Glowthr', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Glow threshold'}),
        ('Microcontrast', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Microcontrast loss'}),
        ('Taps', 'Int', 12, {'min': 4, 'max': 32, 'label': 'Blur taps'}),
    ]),
]
PANEL_PAGES = ['Gate', 'Strip', 'Lens']

PRESETS = [
    (1, 'scope 2.39', {'Amount': 1.0, 'Aspect': 1, 'Fitmode': 0, 'Rotate': 0, 'Strip': 0, 'Gateround': 0.0,
                       'Gatesoft': 1.0, 'Gatejitter': 0.0, 'Vignette': 0.4, 'Distortion': 0.0}),
    (2, 'super 8 gate', {'Amount': 1.0, 'Aspect': 6, 'Fitmode': 2, 'Strip': 0, 'Gateround': 40.0, 'Gatesoft': 12.0,
                         'Gatejitter': 2.0, 'Vignette': 1.0, 'Mechvig': 0.3, 'Softcorners': 6.0, 'Distortion': 0.05}),
    (3, 'film strip 35', {'Amount': 1.0, 'Strip': 1, 'Frames': 3, 'Sprockets': 1, 'Fitmode': 2, 'Scroll': 0.5,
                          'Drive': 0, 'Gateround': 10.0, 'Edgemarks': 0.6, 'Vignette': 0.5}),
    (4, 'soviet swirl', {'Amount': 1.0, 'Aspect': 0, 'Strip': 0, 'Swirl': 24.0, 'Softcorners': 8.0, 'Vignette': 1.2,
                         'Vigoval': 1.0, 'Taps': 16, 'Microcontrast': 0.15}),
    (5, '50s portrait glow', {'Amount': 1.0, 'Aspect': 0, 'Strip': 0, 'Glow': 0.8, 'Glowradius': 30.0,
                              'Glowthr': 0.45, 'Microcontrast': 0.3, 'Vignette': 0.8, 'Softcorners': 4.0}),
]

SHADER = """// FX_film gate (compute). in0 = picture.
// uA amount aspect(0 = canvas) fitmode rotate | uB bar rgb, round | uC soft jitter frame seed
// uD strip frames frameline sideband | uE sprockets holew holeh scrollphase(frames) | uF hole rgb, edgemarks
// uG base rgb, - | uH vignette oval mechvig mechstart | uI vigcolour rgb, distortion
// uJ softcorners swirl glow glowradius | uK glowthr microcontrast taps -
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
%s
float rbox(vec2 q, vec2 h, float r) {                    // fx_film_gate_logic.rbox (q relative to the centre)
    r = min(r, min(h.x, h.y));
    vec2 d = abs(q) - (h - r);
    return length(max(d, vec2(0.0))) + min(max(d.x, d.y), 0.0) - r;
}
vec2 vogel(int k, int n) {
    float rho = sqrt((float(k) + 0.5) / float(n)), th = float(k) * 2.39996323;
    return rho * vec2(cos(th), sin(th));
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    vec2 sz = vec2(isz), P = vec2(p) + 0.5;
    bool strip = uD.x > 0.5;
    bool rot = uA.w > 0.5;
    int fit = int(uA.z + 0.5);
    vec2 ac, ah;
    float yy = 0.0, ch = 0.0, band = 0.0;
    if (strip) {
        ch = sz.y / max(uD.y, 1.0);
        band = uD.w * sz.x;
        yy = P.y + uE.w * ch;
        float k = floor(yy / ch);
        ac = vec2(0.5 * sz.x, k * ch - uE.w * ch + 0.5 * ch);
        ah = vec2(0.5 * sz.x - band, 0.5 * ch - 0.5 * uD.z);
        if (fit == 0) fit = 2;
    } else {
        float A = uA.y > 0.0 ? uA.y : sz.x / sz.y;
        if (rot) A = 1.0 / A;
        ah = sz.x / sz.y > A ? vec2(0.5 * sz.y * A, 0.5 * sz.y) : vec2(0.5 * sz.x, 0.5 * sz.x / A);
        ac = 0.5 * sz;
    }
    if (uC.y > 0.0) {
        uint s = uint(uC.w + 0.5);
        ac += uC.y * 2.0 * (vec2(hsh(ivec2(int(uC.z), 0), s), hsh(ivec2(int(uC.z), 1), s)) - 0.5);
    }
    float sd = rbox(P - ac, max(ah, vec2(0.0)), uB.w);
    float m = uC.x > 0.0 ? clamp(0.5 - sd / uC.x, 0.0, 1.0) : (sd <= 0.0 ? 1.0 : 0.0);
    vec2 S = P;
    if (fit > 0) {
        float sa = rot ? sz.y / sz.x : sz.x / sz.y, apA = ah.x / max(ah.y, 1e-3);
        bool wide = sa > apA;
        vec2 D = (fit == 1) == wide ? vec2(2.0 * ah.x, 2.0 * ah.x / sa) : vec2(2.0 * ah.y * sa, 2.0 * ah.y);
        vec2 uv = (P - ac) / D + 0.5;
        if (fit == 1 && (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0)) m = 0.0;
        if (rot) uv = vec2(uv.y, 1.0 - uv.x);
        S = uv * sz;
    }
    vec2 sc = 0.5 * sz, d0 = S - sc;
    vec2 qn = d0 / sc * vec2(uH.y, 1.0);
    float rn = length(qn) * 0.70710678;
    vec2 Sd = sc + d0 * (1.0 + uI.w * rn * rn);
    int N = int(uK.z + 0.5);
    vec3 col;
    float R1 = uJ.x * rn * rn, Rw = uJ.y * rn * rn;
    if (R1 > 0.0 || Rw > 0.0) {
        vec2 tg = length(d0) > 1e-3 ? vec2(-d0.y, d0.x) / length(d0) : vec2(0.0);
        col = vec3(0.0);
        for (int k = 0; k < 32; k++) { if (k >= N) break;
            float s_ = ((float(k) + 0.5) / float(N) - 0.5) * 2.0;
            col += texture(sTD2DInputs[0], (Sd + R1 * vogel(k, N) + Rw * s_ * tg) / sz).rgb;
        }
        col /= float(N);
    } else col = texture(sTD2DInputs[0], Sd / sz).rgb;
    if (uJ.z > 0.0 || uK.y > 0.0) {
        vec3 mn = vec3(0.0);
        for (int k = 0; k < 32; k++) { if (k >= N) break; mn += texture(sTD2DInputs[0], (Sd + uJ.w * vogel(k, N)) / sz).rgb; }
        mn /= float(N);
        col = mix(col, mn, uK.y) + uJ.z * max(mn - uK.x, vec3(0.0)) * (1.0 - 0.5 * min(rn, 1.0));
    }
    float v = 1.0 / pow(1.0 + (uH.x * rn) * (uH.x * rn), 2.0);
    v *= 1.0 - uH.z * smoothstep(uH.w, uH.w + 0.25, rn);
    col *= v * mix(uI.rgb, vec3(1.0), v);
    vec3 base = strip ? uG.rgb : uB.rgb;
    vec3 o = mix(base, col, m);
    if (strip && uE.x > 0.5 && (P.x < band || P.x > sz.x - band)) {
        int kind = int(uE.x + 0.5);
        float nh = kind == 1 ? 4.0 : (kind == 2 ? 2.0 : 1.0);
        bool left = P.x < band;
        if (left || kind <= 2) {
            float per = ch / nh, off = kind == 3 ? 0.0 : 0.5;
            float t = yy / per - off;
            float dyh = (fract(t + 0.5) - 0.5) * per;
            float dxh = left ? P.x - 0.5 * band : P.x - (sz.x - 0.5 * band);
            vec2 hh = vec2(0.5 * uE.y * band, 0.5 * uE.z * per);
            float hm = clamp(0.5 - rbox(vec2(dxh, dyh), hh, 0.3 * min(hh.x, hh.y)), 0.0, 1.0);
            float ex = left ? P.x / max(band, 1.0) : (sz.x - P.x) / max(band, 1.0);
            if (uF.w > 0.0 && ex > 0.8 && ex < 0.94) {
                float q = yy / (0.25 * per);
                if (hsh(ivec2(int(floor(q)), left ? 0 : 1), uint(uC.w + 0.5)) < uF.w && fract(q) < 0.6)
                    o = mix(o, 0.6 * uF.rgb, 1.0);
            }
            o = mix(o, uF.rgb, hm);
        }
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(mix(c.rgb, o, uA.x), c.a));
}
"""

ASPECT = ("(lambda v: %s if v < 0 else v)(%r[parent().par.Aspect.menuIndex])"
          % ("parent().par.Customaspect.eval()", _GL['ASPECT_VALUES']))
SCROLL = ("((absTime.seconds * (%s / 60.0 / max(%s, 1e-3) if parent().par.Drive.eval() == 'bpm' else %s)"
          " + %s) %% 1.0)" % ("parent().par.Bpm.eval()", "parent().par.Beatsperframe.eval()",
                              "parent().par.Scroll.eval()", "parent().par.Scrollphase.eval()"))


def shaders(H):
    return {'fx': SHADER % H['LIB']}


def build(m, H):
    """in1 -> fx (one compute pass) -> out1."""
    mk, P = H['mk'], H['P']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', shaders(H)['fx'], [in1], extend='zero')
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), ASPECT, 'parent().par.Fitmode.menuIndex', '1 if %s else 0' % P.format('Rotate')]),
        ('uB', [P.format('Barcolourr'), P.format('Barcolourg'), P.format('Barcolourb'), P.format('Gateround')]),
        ('uC', [P.format('Gatesoft'), P.format('Gatejitter'), 'absTime.frame % 100000', P.format('Seed')]),
        ('uD', ['1 if %s else 0' % P.format('Strip'), P.format('Frames'), P.format('Frameline'), P.format('Sideband')]),
        ('uE', ['parent().par.Sprockets.menuIndex', P.format('Holew'), P.format('Holeh'), SCROLL]),
        ('uF', [P.format('Holecolourr'), P.format('Holecolourg'), P.format('Holecolourb'), P.format('Edgemarks')]),
        ('uG', [P.format('Stripcolourr'), P.format('Stripcolourg'), P.format('Stripcolourb'), '0']),
        ('uH', [P.format('Vignette'), P.format('Vigoval'), P.format('Mechvig'), P.format('Mechstart')]),
        ('uI', [P.format('Vigcolourr'), P.format('Vigcolourg'), P.format('Vigcolourb'), P.format('Distortion')]),
        ('uJ', [P.format('Softcorners'), P.format('Swirl'), P.format('Glow'), P.format('Glowradius')]),
        ('uK', [P.format('Glowthr'), P.format('Microcontrast'), P.format('Taps'), '0']),
    ])
    g.comment = 'gate: aspect aperture / film strip + sprockets; lens: distortion, vignette, soft corners, swirl, glow.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Gate + lens', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass: aperture / strip mask, picture mapping, vintage-lens taps, vignette, sprockets.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
