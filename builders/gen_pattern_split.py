# gen_pattern_split - GEN_pattern module 'split' (FX5 E7 / G30, the "Parting Ways" recursive-split look): a BSP of
# the frame walked per pixel (heap node ids, lowbias32 decisions: split chance x Falloff^depth, long-side axis,
# ratio Ratiomin..Ratiomax). Progress (generations) = Growth + Autogrow t + Beatgrow (step + slide); each split's
# seam slides in from the edge over one generation; after Maxdepth + Hold generations the tree re-seeds. Leaves:
# fill / outline / both with a Gap, colour by leaf hash or depth, newborn leaves glow. Audio -> brightness.
# Mirror: gen_pattern_logic.gen_split. ASCII only.
MODULE = 'split'
KIND = 'gen'
BLURB = 'Recursive BSP split growing per generation / beat, seams slide in, re-seeds after Hold.'

PAGES = [('Split', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Maxdepth', 'Int', 7, {'min': 1, 'max': 10, 'label': 'Max depth'}),
    ('Splitchance', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Split chance'}),
    ('Falloff', 'Float', 0.92, {'min': 0, 'max': 1, 'label': 'Chance x per depth'}),
    ('Ratiomin', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Ratio min'}),
    ('Ratiomax', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Ratio max'}),
    ('Growth', 'Float', 0.0, {'min': 0, 'max': 12, 'label': 'Growth (generations)'}),
    ('Autogrow', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Auto grow /s'}),
    ('Beatgrow', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Generations per step'}),
    ('Slide', 'Float', 0.3, {'min': 0.01, 'max': 2, 'label': 'Seam slide s (beat)'}),
    ('Gap', 'Float', 6.0, {'min': 0, 'max': 40, 'label': 'Gap px'}),
    ('Outline', 'Float', 2.0, {'min': 0, 'max': 20, 'label': 'Outline px'}),
    ('Render', 'Menu', 'fill', {'names': ['fill', 'outline', 'both'], 'labels': ['Fill', 'Outline', 'Fill + outline']}),
    ('Colorvar', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Colour by leaf (0 = by depth)'}),
    ('Jitter', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Birth jitter'}),
    ('Newglow', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Newborn glow'}),
    ('Hold', 'Float', 1.5, {'min': 0, 'max': 8, 'label': 'Hold before re-seed'}),
])]
DEFAULTS = {'Palette': 2}
CHECK = {'t': 6.0, 'beats': 5.0}                     # live-check state: grown trees for every preset
PANEL_PAGES = ['Split', 'Drive', 'Colour']
PRESETS = [
    (1, 'parting', {'Amount': 1.0, 'Maxdepth': 7, 'Autogrow': 0.5, 'Beatgrow': 0.0, 'Render': 0, 'Gap': 6.0,
                    'Colorvar': 0.7, 'Palette': 2}),
    (2, 'beat split', {'Amount': 1.0, 'Maxdepth': 8, 'Autogrow': 0.0, 'Beatgrow': 1.0, 'Beatevery': 1.0,
                       'Slide': 0.25, 'Render': 2, 'Palette': 6}),
    (3, 'mondrian', {'Amount': 1.0, 'Maxdepth': 6, 'Growth': 7.0, 'Autogrow': 0.0, 'Hold': 50.0, 'Render': 2,
                     'Gap': 10.0, 'Outline': 4.0, 'Colorvar': 1.0, 'Palette': 7}),
    (4, 'wire', {'Amount': 1.0, 'Maxdepth': 9, 'Autogrow': 0.8, 'Render': 1, 'Gap': 2.0, 'Outline': 2.0,
                 'Palette': 1, 'Newglow': 2.0}),
    (5, 'deep', {'Amount': 1.0, 'Maxdepth': 10, 'Splitchance': 1.0, 'Falloff': 0.97, 'Autogrow': 1.0, 'Gap': 3.0,
                 'Colorvar': 0.0, 'Palette': 5}),
]
UNIFORMS = [('uM0', ['{Maxdepth}', '{Splitchance}', '{Falloff}', '{Ratiomin}']),
            ('uM1', ['{Ratiomax}', '{Growth}', '{Autogrow}', '{Beatgrow}']),
            ('uM2', ['{Slide}', '{Gap}', '{Outline}', '{Render#}']),
            ('uM3', ['{Colorvar}', '{Jitter}', '{Newglow}', '{Hold}'])]

GLSL = """
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int maxd = int(uM0.x + 0.5);
    float prog = uM1.y + uM1.z * T + uM1.w * (STEP + clamp(AGE / max(uM2.x, 1e-3), 0.0, 1.0));
    float L = float(maxd) + uM3.w;
    float cyc = floor(prog / L), loc = prog - cyc * L;
    uint sd = SEED + uint(int(cyc)) * 0x632BE5ABu;
    vec4 r = vec4(0.0, 0.0, RES);
    uint node = 1u; int depth = 0; float last = -10.0;
    for (int d = 0; d < 10; d++) {
        if (d >= maxd) break;
        int ni = int(node);
        if (h3(ivec3(ni, d, 0), sd) >= uM0.y * (d == 0 ? 1.0 : pow(max(uM0.z, 0.0), float(d)))) break;
        float birth = float(d) + uM3.y * h3(ivec3(ni, d, 1), sd);
        float grow = clamp(loc - birth, 0.0, 1.0);
        if (grow <= 0.0) break;
        float w = r.z - r.x, h = r.w - r.y;
        int ax = w > 1.3 * h ? 0 : (h > 1.3 * w ? 1 : (h3(ivec3(ni, d, 2), sd) < 0.5 ? 0 : 1));
        float ratio = mix(1.0, mix(uM0.w, uM1.x, h3(ivec3(ni, d, 3), sd)), smooth01(grow));
        last = birth;
        if (ax == 0) {
            float pos = r.x + w * ratio;
            if (P.x < pos) { node = node * 2u; r.z = pos; } else { node = node * 2u + 1u; r.x = pos; }
        } else {
            float pos = r.y + h * ratio;
            if (P.y < pos) { node = node * 2u; r.w = pos; } else { node = node * 2u + 1u; r.y = pos; }
        }
        depth = d + 1;
    }
    float e = min(min(P.x - r.x, r.z - P.x), min(P.y - r.y, r.w - P.y));
    float g2 = uM2.y * 0.5;
    float vf = clamp(0.5 + (e - g2), 0.0, 1.0);
    float vo = vf * clamp(0.5 + (g2 + uM2.z - e), 0.0, 1.0);
    int render = int(uM2.w + 0.5);
    v = render == 0 ? vf : (render == 1 ? vo : max(0.4 * vf, vo));
    v *= (1.0 + uM3.z * (1.0 - clamp(loc - last, 0.0, 1.0))) * (1.0 + LEVEL);
    k = uM3.x * h3(ivec3(int(node), depth, 4), sd) + (1.0 - uM3.x) * float(depth) / float(max(maxd, 1));
}
"""
