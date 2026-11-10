# gen_pattern_caustic - GEN_pattern module 'caustic' (FX7a SX-04 "Caustics light overlay"; BUILD_PLAN_27OCT lane A).
# Clean-room (U8 default: the CC BY-NC-SA Shadertoy loop is NOT used). Two ways, both tileable (one tile = 1 pattern
# unit, so Space page Scale = tiles per screen height and the picture wraps seamlessly):
#  refract: a water height h = sum of Waves sines with integer wave vectors (2 pi (m, n), |m|, |n| <= Freq) moving at
#           Flow; light through it focuses where the refraction map x -> x + Depth grad h folds: intensity =
#           1 / (|det(I + Depth Hess h)| + Soft) (the physical caustic density), minus Base, x Gain.
#  cells:   two layers of animated Worley cells, bright where F2 - F1 is small (the classic water-light net), Width.
# Blend default Add (overlay on footage), Multiply also works. Colour: Colour A -> B duo (cyan -> white by default)
# or the shared palette, k = intensity. Audio -> Depth (refract) / brightness, beat pulse -> brightness.
# Mirror: gen_pattern_logic.gen_caustic. ASCII only.
MODULE = 'caustic'
KIND = 'gen'
PAL = True
BLURB = 'Tileable water caustics: refraction Jacobian of moving sines, or Worley-edge net; overlay (Add).'

PAGES = [('Caustic', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Mode', 'Menu', 'refract', {'names': ['refract', 'cells'],
                                 'labels': ['Refract (physical: Jacobian of the water)', 'Cells (Worley edge net)']}),
    ('Waves', 'Int', 10, {'min': 1, 'max': 16, 'label': 'Waves (refract)'}),
    ('Freq', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Max wave number per tile'}),
    ('Depth', 'Float', 2.2, {'min': 0, 'max': 6, 'label': 'Depth (focusing)'}),
    ('Soft', 'Float', 0.08, {'min': 0.005, 'max': 2, 'label': 'Softness'}),
    ('Base', 'Float', 0.65, {'min': 0, 'max': 2, 'label': 'Base (subtract)'}),
    ('Gain', 'Float', 0.35, {'min': 0, 'max': 4, 'label': 'Gain'}),
    ('Flow', 'Float', 0.25, {'min': -4, 'max': 4, 'label': 'Flow speed'}),
    ('Cells', 'Int', 4, {'min': 1, 'max': 32, 'label': 'Cells per tile (cells)'}),
    ('Width', 'Float', 0.06, {'min': 0.002, 'max': 0.5, 'label': 'Edge width (cells)'}),
])]
DEFAULTS = {'Scale': 2.0, 'Palette': 'duo', 'Colorar': 0.15, 'Colorag': 0.55, 'Colorab': 0.85, 'Colorbr': 0.9,
            'Colorbg': 1.0, 'Colorbb': 1.0, 'Spread': 0.5, 'Blend': 'add', 'Palsource': 'px_ramp'}
PANEL_PAGES = ['Caustic', 'Space', 'Drive', 'Colour', 'Palette']
PRESETS = [
    (1, 'pool light', {'Amount': 1.0, 'Mode': 'refract'}),
    (2, 'deep focus', {'Amount': 1.0, 'Mode': 'refract', 'Depth': 3.2, 'Soft': 0.04, 'Base': 0.8, 'Gain': 0.25,
                       'Waves': 12, 'Freq': 5}),
    (3, 'water net', {'Amount': 1.0, 'Mode': 'cells', 'Cells': 4, 'Width': 0.05, 'Gain': 0.9}),
    (4, 'sunlit shallows', {'Amount': 1.0, 'Mode': 'refract', 'Palette': 'shared', 'Palsource': 'px_ramp',
                            'Palmode': 'gradient', 'Spread': 0.7, 'Scale': 1.2, 'Flow': 0.15}),
    (5, 'beat ripple', {'Amount': 1.0, 'Mode': 'refract', 'Beatevery': 1.0, 'Beatgain': 0.8, 'Audiogain': 1.0,
                        'Flow': 0.4, 'Depth': 1.8}),
]
UNIFORMS = [('uM0', ['{Mode#}', '{Waves}', '{Freq}', '{Depth}']),
            ('uM1', ['{Soft}', '{Base}', '{Gain}', '{Flow}']),
            ('uM2', ['{Cells}', '{Width}', '0', '0'])]

GLSL = """
float ca_cells(vec2 x, float n, float t, uint s) {   // F2 - F1 of animated points, cells wrap every n (tileable)
    vec2 g = x * n, c = floor(g);
    float f1 = 1e9, f2 = 1e9;
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            vec2 cc = c + vec2(dx, dy);
            ivec2 w = ivec2(mod(cc, n));
            float a = TAU * h2(w, s), r = 0.25 + 0.15 * h2(w, s ^ 0x55u);
            vec2 pt = cc + 0.5 + r * vec2(cos(a + t), sin(a + 1.3 * t));
            float d = length(g - pt);
            if (d < f1) { f2 = f1; f1 = d; } else if (d < f2) f2 = d;
        }
    }
    return f2 - f1;
}
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int mode = int(uM0.x + 0.5);
    float t = T * uM1.w, I;
    if (mode == 0) {
        int n = clamp(int(uM0.y + 0.5), 1, 16), F = max(int(uM0.z + 0.5), 1);
        float hxx = 0.0, hxy = 0.0, hyy = 0.0, norm = inversesqrt(float(n));
        for (int i = 0; i < 16; i++) {
            if (i >= n) break;
            int m = int(floor((2.0 * h2(ivec2(i, 1), SEED) - 1.0) * float(F) + 0.5));
            int l = int(floor((2.0 * h2(ivec2(i, 2), SEED) - 1.0) * float(F) + 0.5));
            if (m == 0 && l == 0) m = 1;
            vec2 kv = TAU * vec2(float(m), float(l));
            float kk = dot(kv, kv);
            float sv = sin(dot(kv, q) + t * TAU * (0.5 + 0.5 * h2(ivec2(i, 3), SEED)) * sqrt(sqrt(kk) / TAU) + TAU * h2(ivec2(i, 4), SEED));
            float a = norm / kk;
            hxx -= a * sv * kv.x * kv.x; hxy -= a * sv * kv.x * kv.y; hyy -= a * sv * kv.y * kv.y;
        }
        float D = uM0.w * (1.0 + LEVEL);
        float det = (1.0 + D * hxx) * (1.0 + D * hyy) - D * D * hxy * hxy;
        I = max(1.0 / (abs(det) + uM1.x) - uM1.y, 0.0);
    } else {
        float nc = max(floor(uM2.x + 0.5), 1.0);
        float e1 = ca_cells(q, nc, t * TAU * 0.5, SEED), e2 = ca_cells(q + vec2(0.37, 0.71), nc * 2.0, -t * TAU * 0.7, SEED ^ 0x9Bu);
        I = exp(-e1 / uM2.y) + 0.5 * exp(-e2 / (uM2.y * 1.5));
    }
    v = I * uM1.z * (1.0 + ENV) * (mode == 1 ? 1.0 + LEVEL : 1.0);
    k = min(v, 2.0) * 0.5;
}
"""
