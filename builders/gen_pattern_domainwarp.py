# gen_pattern_domainwarp - GEN_pattern module 'domainwarp' (FX5 G28): IQ-style warped fbm f(p + W fbm(p + W fbm(p)))
# at Depth 1-3, value-noise fbm (lowbias32 hash, 2-8 octaves), Evolve moves the inner layers, Bands = marble
# contours, Tint colours by the warp vector, Contrast stretches the fbm around 0.5 (fbm sits near 0.5).
# Audio -> warp amount, beat pulse -> evolve kick. Mirror: gen_pattern_logic.gen_domainwarp. ASCII only.
MODULE = 'domainwarp'
KIND = 'gen'
BLURB = 'Domain-warped fbm (ink / marble / smoke / oil); Depth 1-3 nested warps.'

PAGES = [('Domainwarp', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Depth', 'Int', 2, {'min': 1, 'max': 3, 'label': 'Warp depth'}),
    ('Warp', 'Float', 1.5, {'min': 0, 'max': 6, 'label': 'Warp amount'}),
    ('Octaves', 'Int', 5, {'min': 1, 'max': 8, 'label': 'Octaves'}),
    ('Evolve', 'Float', 0.15, {'min': -2, 'max': 2, 'label': 'Evolve speed'}),
    ('Bands', 'Float', 0.0, {'min': 0, 'max': 12, 'label': 'Marble bands (0 smooth)'}),
    ('Tint', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Tint by warp'}),
    ('Contrast', 'Float', 2.5, {'min': 0, 'max': 8, 'label': 'Contrast'}),
])]
DEFAULTS = {'Scale': 3.0, 'Palette': 4}
PANEL_PAGES = ['Domainwarp', 'Drive', 'Space', 'Colour']
PRESETS = [
    (1, 'marble', {'Amount': 1.0, 'Depth': 2, 'Warp': 1.2, 'Octaves': 5, 'Evolve': 0.1, 'Bands': 4.0, 'Tint': 0.0,
                   'Palette': 0, 'Colorar': 0.95, 'Colorag': 0.93, 'Colorab': 0.88, 'Colorbr': 0.25,
                   'Colorbg': 0.22, 'Colorbb': 0.2}),
    (2, 'smoke', {'Amount': 1.0, 'Depth': 3, 'Warp': 1.2, 'Octaves': 4, 'Evolve': 0.2, 'Bands': 0.0, 'Tint': 0.3,
                  'Palette': 4}),
    (3, 'oil', {'Amount': 1.0, 'Depth': 2, 'Warp': 1.8, 'Octaves': 5, 'Evolve': 0.12, 'Tint': 1.0, 'Palette': 2,
                'Spread': 2.0}),
    (4, 'lava', {'Amount': 1.0, 'Depth': 2, 'Warp': 2.2, 'Octaves': 4, 'Evolve': 0.4, 'Tint': 0.2, 'Palette': 3}),
    (5, 'beat ink', {'Amount': 1.0, 'Depth': 2, 'Warp': 1.5, 'Evolve': 0.1, 'Beatevery': 1.0, 'Beatgain': 1.5,
                     'Beatdecay': 0.4, 'Audiogain': 0.5, 'Palette': 6}),
]
UNIFORMS = [('uM0', ['{Depth}', '{Warp}', '{Octaves}', '{Evolve}']),
            ('uM1', ['{Bands}', '{Tint}', '{Contrast}', '0'])]

GLSL = """
float F(vec2 x, int o) { return 2.0 * fbm(x, SEED, o) - 1.0; }
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int depth = int(uM0.x + 0.5), o = int(uM0.z + 0.5);
    float W = uM0.y * (1.0 + LEVEL), tt = T * uM0.w + ENV;
    vec2 w = vec2(F(q + vec2(tt * 0.31, 0.0), o), F(q + vec2(5.2, 1.3 + tt * 0.27), o));
    if (depth >= 2) w = vec2(F(q + W * w + vec2(1.7 + tt * 0.15, 9.2), o), F(q + W * w + vec2(8.3, 2.8 + tt * 0.126), o));
    if (depth >= 3) w = vec2(F(q + W * w + vec2(3.1, 4.7), o), F(q + W * w + vec2(6.9, 0.4), o));
    v = 0.5 + (fbm(q + W * w, SEED, o) - 0.5) * uM1.z;
    k = mix(v, clamp(length(w) * 0.70710678, 0.0, 1.0), uM1.y);
    if (uM1.x > 0.0) v = 0.5 + 0.5 * sin(TAU * v * uM1.x);
}
"""
