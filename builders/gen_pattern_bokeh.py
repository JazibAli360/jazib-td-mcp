# gen_pattern_bokeh - GEN_pattern module 'bokeh' (FX7a SX-22 "Bokeh parallax drift", knarkowicz idea, clean-room;
# BUILD_PLAN_27OCT lane A). Up to 6 depth layers of out-of-focus discs on hashed cell grids (3x3 neighbours per layer):
# near layers bigger, brighter and faster (parallax), far layers smaller and dimmer; aperture circle / pentagon /
# hexagon / octagon with blade rotation; soft edge = Softness + Defocus x |depth - Focus| (one layer can be sharp);
# Rim = the bright "onion ring" edge of real bokeh; per-disc slow twinkle; drift direction + whole-layer sway; a soft
# vertical palette gradient behind (Gradient). Colour = shared palette (W1-B uPal) or any Colour page palette:
# disc k = hash, gradient k = 1 - y. Audio -> brightness + size, beat pulse -> brightness. Calm always-on backdrop
# for talk / hold states. Mirror: gen_pattern_logic.gen_bokeh. ASCII only.
MODULE = 'bokeh'
KIND = 'gen'
PAL = True
BLURB = 'Bokeh parallax drift: depth layers of soft discs (aperture shapes, rim, focus), drift + sway, gradient.'

PAGES = [('Bokeh', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Layers', 'Int', 4, {'min': 1, 'max': 6, 'label': 'Depth layers (1-6)'}),
    ('Size', 'Float', 0.07, {'min': 0.005, 'max': 0.4, 'label': 'Near disc radius (screen heights)'}),
    ('Depthscale', 'Float', 0.35, {'min': 0.05, 'max': 1, 'label': 'Far / near size'}),
    ('Density', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'Density (discs per cell)'}),
    ('Bright', 'Float', 0.55, {'min': 0, 'max': 4, 'label': 'Brightness'}),
    ('Depthfade', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'Far layers dimmer'}),
    ('Softness', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Edge softness'}),
    ('Defocus', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Defocus away from Focus'}),
    ('Focus', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Focus depth (1 near, 0 far)'}),
    ('Rim', 'Float', 0.4, {'min': 0, 'max': 3, 'label': 'Rim (onion ring edge)'}),
    ('Shape', 'Menu', 'circle', {'names': ['circle', 'pentagon', 'hexagon', 'octagon'],
                                 'labels': ['Circle', 'Pentagon (5 blades)', 'Hexagon (6 blades)', 'Octagon (8 blades)']}),
    ('Bladerot', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Blade rotation deg'}),
    ('Drift', 'Float', 0.03, {'min': -1, 'max': 1, 'label': 'Drift (screen heights/s, near layer)'}),
    ('Direction', 'Float', 90.0, {'min': -180, 'max': 180, 'label': 'Drift direction deg (90 = up)'}),
    ('Sway', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'Layer sway (cells)'}),
    ('Twinkle', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Twinkle'}),
    ('Twinklerate', 'Float', 0.25, {'min': 0, 'max': 4, 'label': 'Twinkle Hz'}),
    ('Gradient', 'Float', 0.18, {'min': 0, 'max': 1, 'label': 'Background gradient'}),
])]
DEFAULTS = {'Palette': 'shared', 'Palsource': 'cyan_magenta', 'Palmode': 'gradient', 'Blend': 'replace'}
PANEL_PAGES = ['Bokeh', 'Drive', 'Colour', 'Palette']
PRESETS = [
    (1, 'calm drift', {'Amount': 1.0, 'Layers': 4, 'Palsource': 'cyan_magenta', 'Palmode': 'gradient'}),
    (2, 'warm hexes', {'Amount': 1.0, 'Layers': 5, 'Shape': 'hexagon', 'Palsource': 'fire', 'Palmode': 'gradient',
                       'Size': 0.09, 'Rim': 0.8, 'Gradient': 0.12, 'Bladerot': 15.0}),
    (3, 'deep focus', {'Amount': 1.0, 'Layers': 6, 'Focus': 0.4, 'Defocus': 1.0, 'Softness': 0.05,
                       'Palsource': 'rainbow', 'Palmode': 'cycle', 'Density': 0.4, 'Depthscale': 0.2, 'Bright': 0.4}),
    (4, 'rain of light', {'Amount': 1.0, 'Layers': 4, 'Direction': -90.0, 'Drift': 0.12, 'Sway': 0.05,
                          'Size': 0.04, 'Density': 0.5, 'Palsource': 'neon_trio', 'Palmode': 'steps',
                          'Shape': 'octagon', 'Gradient': 0.05}),
    (5, 'beat glow', {'Amount': 1.0, 'Layers': 3, 'Beatevery': 1.0, 'Beatgain': 0.8, 'Beatdecay': 0.3,
                      'Palsource': 'magenta_inv', 'Palmode': 'gradient', 'Paldrive': 'bpm_cycle',
                      'Palevery': 16.0, 'Size': 0.11, 'Twinkle': 0.6}),
]
UNIFORMS = [('uM0', ['{Layers}', '{Size}', '{Depthscale}', '{Density}']),
            ('uM1', ['{Bright}', '{Depthfade}', '{Softness}', '{Defocus}']),
            ('uM2', ['{Focus}', '{Rim}', '{Shape#}', 'math.radians({Bladerot})']),
            ('uM3', ['{Drift}', 'math.radians({Direction})', '{Sway}', '{Twinkle}']),
            ('uM4', ['{Twinklerate}', '{Gradient}', '0', '0'])]

GLSL = """
float bk_nd(vec2 d, float r, int sh) {             // distance / edge distance (1 = on the aperture edge)
    float L = length(d);
    if (sh == 0) return L / r;
    float n = sh == 1 ? 5.0 : (sh == 2 ? 6.0 : 8.0), seg = TAU / n;
    float m = mod(atan(d.y, d.x) - uM2.w, seg) - 0.5 * seg;
    return L * cos(m) / (r * cos(0.5 * seg));
}
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int NL = clamp(int(uM0.x + 0.5), 1, 6), sh = int(uM2.z + 0.5);
    float H = RES.y, V = 0.0, KK = 0.0;
    float g = uM4.y * mix(0.5, 1.0, P.y / H);
    V += g; KK += g * (1.0 - P.y / H);
    vec2 dir = vec2(cos(uM3.y), sin(uM3.y));
    for (int l = 0; l < 6; l++) {
        if (l >= NL) break;
        float z = float(l + 1) / float(NL), fl = float(l);
        float rc = uM0.y * mix(uM0.z, 1.0, z), cs = 2.2 * rc;
        vec2 sw = uM3.z * cs * vec2(sin(T * 0.31 + fl * 1.3), cos(T * 0.23 + fl * 2.1));
        vec2 u = (P / H - dir * uM3.x * mix(0.25, 1.0, z) * T - sw) / cs + vec2(fl * 17.31, fl * 9.73);
        vec2 cl = floor(u);
        float soft = clamp(uM1.z + uM1.w * abs(z - uM2.x), 0.0, 1.0);
        float lf = uM1.x * mix(1.0 - uM1.y, 1.0, z) * (1.0 + ENV) * (1.0 + LEVEL);
        float rmax = 0.45 * (1.0 + 0.3 * LEVEL);          // disc radius bound (cells); centres in [c + 0.15, c + 0.85]
        for (int dy = -1; dy <= 1; dy++) {
            for (int dx = -1; dx <= 1; dx++) {
                ivec2 c = ivec2(cl) + ivec2(dx, dy);
                vec2 bx = clamp(u, vec2(c) + 0.15, vec2(c) + 0.85) - u;
                if (dot(bx, bx) > rmax * rmax) continue;   // no disc of this cell can reach the pixel (no hash)
                uint h = lb32(uint(c.x) * 0x8da6b343u ^ uint(c.y) * 0xd8163841u ^ uint(l) * 0xcb1ab31fu ^ SEED * 0x165667b1u);
                if (float(h & 0xffffu) * (1.0 / 65536.0) >= uM0.w) continue;
                vec2 ctr = vec2(c) + 0.15 + 0.7 * vec2(float((h >> 16) & 0xffu), float(h >> 24)) * (1.0 / 255.0);
                uint h2b = lb32(h ^ 0x68e31da4u);
                float r = mix(0.25, 0.45, float(h2b & 0xffu) * (1.0 / 255.0)) * cs * H * (1.0 + 0.3 * LEVEL);
                vec2 d = (u - ctr) * cs * H;
                if (dot(d, d) > r * r) continue;
                float nd = bk_nd(d, r, sh);
                float inside = clamp((1.0 - nd) / max(soft, 1.0 / r), 0.0, 1.0);
                if (inside <= 0.0) continue;
                inside = inside * inside * (3.0 - 2.0 * inside);
                float tw = 1.0 - uM3.w * (0.5 + 0.5 * sin(TAU * (T * uM4.x * (0.5 + float((h2b >> 8) & 0xffu) * (1.0 / 255.0)) + float((h2b >> 16) & 0xffu) * (1.0 / 255.0))));
                float I = lf * tw * inside * (1.0 + uM2.y * smooth01((nd - 0.6) / 0.4));
                V += I; KK += I * float(h2b >> 24) * (1.0 / 255.0);
            }
        }
    }
    v = V;
    k = V > 1e-6 ? KK / V : 0.0;
}
"""
