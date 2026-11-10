# gen_pattern_truchet - GEN_pattern module 'truchet' (FX5 G06): Smith quarter-arcs, diagonals (10 PRINT maze),
# half-square triangles, two-coloured arc regions; multi-scale (Carlson-style recursive subdivision, Levels /
# Subdivide). Steps (Beatevery) and Fliprate re-roll which Flipshare of the tiles turn. Audio -> line width, beat
# pulse -> line width. Mirror: gen_pattern_logic.gen_truchet. ASCII only.
MODULE = 'truchet'
KIND = 'gen'
BLURB = 'Truchet tiles: hash per cell -> orientation; Levels subdivide cells; steps flip Flipshare of the tiles.'
TILES = ['arc', 'diagonal', 'triangle', 'arcfill']

PAGES = [('Truchet', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Tile', 'Menu', 'arc', {'names': TILES, 'labels': ['Quarter arcs (Smith)', 'Diagonal (maze)',
                                                         'Triangles (fill)', 'Arc regions (2-colour)']}),
    ('Levels', 'Int', 1, {'min': 1, 'max': 4, 'label': 'Levels (multi-scale)'}),
    ('Subdivide', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Subdivide chance'}),
    ('Linewidth', 'Float', 0.14, {'min': 0, 'max': 0.5, 'label': 'Line width (cell)'}),
    ('Flipshare', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Flip share per step'}),
    ('Fliprate', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Flip re-roll Hz'}),
    ('Colorvar', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Colour per tile'}),
])]
DEFAULTS = {'Scale': 12.0}
PANEL_PAGES = ['Truchet', 'Drive', 'Space', 'Colour']
PRESETS = [
    (1, 'weave', {'Amount': 1.0, 'Tile': 0, 'Levels': 1, 'Linewidth': 0.16, 'Flipshare': 0.0, 'Scale': 12.0,
                  'Palette': 0, 'Colorvar': 0.0, 'Beatevery': 0.0}),
    (2, 'maze', {'Amount': 1.0, 'Tile': 1, 'Levels': 1, 'Linewidth': 0.12, 'Flipshare': 0.5, 'Scale': 24.0,
                 'Beatevery': 1.0, 'Palette': 1}),
    (3, 'bridges', {'Amount': 1.0, 'Tile': 0, 'Levels': 3, 'Subdivide': 0.45, 'Linewidth': 0.18, 'Scale': 6.0,
                    'Colorvar': 0.0, 'Palette': 5, 'Spread': 1.0}),
    (4, 'quilt', {'Amount': 1.0, 'Tile': 2, 'Levels': 2, 'Subdivide': 0.3, 'Scale': 10.0, 'Colorvar': 1.0,
                  'Palette': 2, 'Fliprate': 2.0, 'Flipshare': 0.15}),
    (5, 'knots', {'Amount': 1.0, 'Tile': 3, 'Levels': 1, 'Scale': 9.0, 'Flipshare': 0.3, 'Beatevery': 2.0,
                  'Palette': 0, 'Driftx': 0.15}),
]
UNIFORMS = [('uM0', ['{Tile#}', '{Levels}', '{Subdivide}', '{Linewidth}']),
            ('uM1', ['{Flipshare}', '{Fliprate}', '{Colorvar}', '0'])]

GLSL = """
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int tile = int(uM0.x + 0.5), levels = int(uM0.y + 0.5);
    vec2 g = q; float s = 1.0; int lev = 0;
    for (int l = 0; l < 4; l++) {
        ivec2 cl = ivec2(floor(g));
        if (l + 1 >= levels) break;
        if (h3(ivec3(cl, l), SEED ^ 0x51u) >= uM0.z) break;
        g *= 2.0; s *= 2.0; lev = l + 1;
    }
    ivec2 ci = ivec2(floor(g)); vec2 f = g - vec2(ci);
    uint roll = uint(int(STEP)) * 0x9E37u + uint(int(floor(T * uM1.y)));
    int o = h3(ivec3(ci, lev), SEED) < 0.5 ? 1 : 0;
    if (h3(ivec3(ci, lev), SEED ^ lb32(roll + 1u)) < uM1.x) o ^= 1;
    float w = uM0.w * (1.0 + LEVEL) + ENV * uM0.w;
    float aa = PX * s;
    vec2 c1 = o == 1 ? vec2(0.0, 0.0) : vec2(1.0, 0.0);
    vec2 c2 = o == 1 ? vec2(1.0, 1.0) : vec2(0.0, 1.0);
    float d1 = length(f - c1), d2 = length(f - c2);
    if (tile == 0) v = stroke(min(abs(d1 - 0.5), abs(d2 - 0.5)), w, aa);
    else if (tile == 1) v = stroke((o == 1 ? abs(f.x - f.y) : abs(f.x + f.y - 1.0)) * 0.70710678, w, aa);
    else if (tile == 2) v = clamp(0.5 + (o == 1 ? f.x - f.y : f.x + f.y - 1.0) * 0.70710678 / aa, 0.0, 1.0);
    else {
        float ins = clamp(0.5 + (0.5 - min(d1, d2)) / aa, 0.0, 1.0);
        int par = ((ci.x + ci.y) & 1) ^ o;
        v = par == 1 ? ins : 1.0 - ins;
    }
    k = uM1.z * h3(ivec3(ci, lev + 32), SEED) + 0.2 * float(lev);
}
"""
