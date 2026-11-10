# gen_points_sparkle - GEN_points module 'sparkle' (G-SPARKLE, own clean-room design, FX7 3.8): twinkling glints.
# Stateless: point i flashes Rate x (0.5..1.5) times per second, brightness sin(pi q)^Sharp over each cycle q, and
# jumps to a new place every cycle (anywhere / centre disc / bright pixels of the slot input, the Nuke Glint
# threshold idea); Drift moves it during a cycle; beat Kick flashes random ones. Drawn as glint sprites (engine Sprite
# 'glint': soft core + Rays thin rays) sized per point (Sizevar, Grow with brightness); colour from the palette or the
# input picture. Shared effectors reveal / push them (PXE_POINTS; Effon off). Mirror: gen_points_logic.sparkle_*.
MODULE = 'sparkle'
KIND = '2d'
BLURB = 'Twinkles: each point flashes, then jumps (anywhere / disc / bright pixels); glint sprites with rays.'
PLACES = ['anywhere', 'disc', 'image']
COLORBY = ['palette', 'input']
EFFECTORS = 'points'
EPOCH = '0'

PAGES = [('Sparkle', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Rate', 'Float', 0.5, {'min': 0.01, 'max': 8, 'label': 'Twinkles per s'}),
    ('Placement', 'Menu', 'anywhere', {'names': PLACES, 'labels': ['Anywhere', 'Centre disc',
                                                                  'Bright input pixels']}),
    ('Discradius', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Disc radius'}),
    ('Threshold', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Bright pixel threshold (luma)'}),
    ('Driftx', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Drift x (world/s)'}),
    ('Drifty', 'Float', 0.02, {'min': -2, 'max': 2, 'label': 'Drift y (world/s)'}),
    ('Sharp', 'Float', 8.0, {'min': 1, 'max': 48, 'label': 'Sharpness (higher = rarer glints)'}),
    ('Kick', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Beat pulse -> flash'}),
    ('Sizevar', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Size variation'}),
    ('Grow', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Size follows brightness'}),
    ('Colorby', 'Menu', 'palette', {'names': COLORBY, 'labels': ['Palette (random per glint)', 'Input picture']}),
])]
DEFAULTS = {'Count': 3000, 'Size': 28.0, 'Sprite': 3, 'Rays': 4, 'Raywidth': 0.05, 'Persist': 0.0, 'Tonemap': 0,
            'Normalize': 1, 'Exposure': 1.0, 'Palette': 5, 'Glow': 0.0, 'Respawn': 0.0}
PANEL_PAGES = ['Sparkle', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'gold twinkle', {'Rate': 0.5, 'Placement': 0, 'Palette': 5, 'Count': 3000, 'Size': 28.0, 'Sprite': 3}),
    (2, 'glint on bright', {'Placement': 2, 'Threshold': 0.65, 'Colorby': 1, 'Rate': 1.0, 'Count': 2000,
                            'Size': 36.0, 'Sprite': 3, 'Rays': 6}),
    (3, 'snow glitter', {'Rate': 1.5, 'Drifty': -0.15, 'Sharp': 16.0, 'Palette': 4, 'Count': 12000, 'Size': 10.0,
                         'Sprite': 3, 'Exposure': 0.5}),
    (4, 'diamond burst', {'Placement': 1, 'Discradius': 0.6, 'Kick': 2.0, 'Beatevery': 1.0, 'Beatgain': 1.0,
                          'Sharp': 24.0, 'Palette': 1, 'Colorar': 0.85, 'Colorag': 0.9, 'Colorab': 1.0, 'Count': 3000, 'Size': 40.0,
                          'Sprite': 3, 'Rays': 8}),
    (5, 'neon dust', {'Rate': 2.0, 'Size': 1.0, 'Count': 65536, 'Normalize': 0, 'Persist': 0.6, 'Palette': 6,
                      'Sharp': 6.0}),
]
UNIFORMS = [('uM0', ['{Rate}', '{Placement#}', '{Discradius}', '{Threshold}']),
            ('uM1', ['{Driftx}', '{Drifty}', '{Sharp}', '{Kick}']),
            ('uM2', ['{Sizevar}', '{Grow}', '{Colorby#}', '0'])]

STEP = """
vec4 sp_eval(int i) {
    float f = uM0.x * (0.5 + rnd(i, 81u));
    float x = max(T, 0.0) * f + rnd(i, 82u);
    float n = floor(x), q = x - n;
    uint salt = uint(int(n)) * 8u;
    int mode = int(uM0.y + 0.5);
    float r0 = rnd(i, salt + 100u), r1 = rnd(i, salt + 101u);
    vec2 p;
    float vis = 1.0;
    if (mode == 1) { float an = TAU * r0; p = uM0.z * sqrt(r1) * vec2(cos(an), sin(an)); }
    else p = vec2((r0 * 2.0 - 1.0) * ASP, r1 * 2.0 - 1.0);
    if (mode == 2) {
        vis = 0.0;
        for (int k = 0; k < 16; k++) {
            vec2 u = vec2(rnd(i, salt + 110u + 2u * uint(k)), rnd(i, salt + 111u + 2u * uint(k)));
            if (lum(texture(GP_IN, u).rgb) > uM0.w) { p = vec2((u.x * 2.0 - 1.0) * ASP, u.y * 2.0 - 1.0); vis = 1.0; break; }
        }
    }
    p += uM1.xy * (q / max(f, 1e-6));
    float b = pow(max(sin(PI * q), 0.0), uM1.z);
    b = max(b, uM1.w * ENV * rnd(i, salt + 7u)) * vis;
    vec3 P = vec3(p, 0.0);
#ifdef PXE_POINTS
    PXEFx fx = pxePointFx(P, float(i));
    P += fx.off;
    b *= fx.alpha;
#endif
    float sz = (1.0 + (0.25 + 1.5 * rnd(i, salt + 6u) - 1.0) * uM2.x) * (1.0 + (b - 1.0) * uM2.y);
    return vec4(P.xy, packKA(rnd(i, salt + 5u), b), sz);
}
vec4 pt_seed(int i) { return sp_eval(i); }
vec4 pt_step(int i, vec4 s, float dt) { if (dt <= 0.0) return s; return sp_eval(i); }
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    P = vec3(s.xy, 0.0);
    float a = unpackA(s.z);
    vec3 col = int(uM2.z + 0.5) == 1 ? textureLod(GP_IN, vec2(s.x / (2.0 * ASP) + 0.5, s.y * 0.5 + 0.5), 0.0).rgb
                                     : ptpal(unpackK(s.z));
    C = vec4(col, a);
    PSIZE = max(s.w, 0.0);
    return a > 0.0;
}
"""
