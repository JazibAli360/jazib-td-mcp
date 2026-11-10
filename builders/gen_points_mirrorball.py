# gen_points_mirrorball - GEN_points module 'mirrorball' (FX7c card 19, the dance-floor staple; clean-room): light
# spots thrown on the wall by a turning mirror ball. Facets = a Fibonacci sphere of normals (Facets = Count / Lights),
# turned about a tilted axis (Spin deg/s, Tilt); each light j (Lights 1..4, directions fanned by Lightspread around y,
# Elevation) reflects off every facet that faces it: r = d - 2 (d . n) n; the ray from the ball (at the origin) hits
# the wall plane z = -Walldist; the spot is drawn there as a sprite (engine Sprite: soft disc or glint) whose size grows
# with the grazing angle (Spotsize / |r.z|^Elongate), brightness = facet facing x Twinkle (per-facet sparkle) x the
# fall-off to the wall edge, beat Kick flashes all spots. Colour by light (palette stop per light) / facet / position.
# Stateless (pure function of index + module time). Mirror: gen_points_logic.mirrorball_*. ASCII only.
MODULE = 'mirrorball'
KIND = '2d'
BLURB = 'Mirror-ball light spots: Fibonacci facets turn, reflect up to 4 lights onto the wall plane as sprites.'
COLORBY = ['light', 'facet', 'position']
EFFECTORS = None
EPOCH = '0'
CHECK = {'t': 1.0}
MIN_VISIBLE = dict((k, 0.05) for k in range(1, 6))   # only facets that face a light AND throw onto the wall (~1/4)

PAGES = [('Mirrorball', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Lights', 'Int', 2, {'min': 1, 'max': 4, 'label': 'Lights (spots per facet)'}),
    ('Spin', 'Float', 20.0, {'min': -360, 'max': 360, 'label': 'Ball spin deg/s'}),
    ('Tilt', 'Float', 15.0, {'min': -90, 'max': 90, 'label': 'Spin axis tilt deg'}),
    ('Elevation', 'Float', 25.0, {'min': -89, 'max': 89, 'label': 'Light elevation deg'}),
    ('Azimuth', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Light azimuth deg (0 = from the viewer)'}),
    ('Lightspread', 'Float', 50.0, {'min': 0, 'max': 180, 'label': 'Light fan deg (around y)'}),
    ('Walldist', 'Float', 3.0, {'min': 0.1, 'max': 50, 'label': 'Wall distance'}),
    ('Wallscale', 'Float', 0.25, {'min': 0.01, 'max': 4, 'label': 'Wall -> screen scale'}),
    ('Spotsize', 'Float', 2.0, {'min': 0, 'max': 8, 'label': 'Spot size (x Size px)'}),
    ('Elongate', 'Float', 0.6, {'min': 0, 'max': 2, 'label': 'Grazing spots grow (power)'}),
    ('Twinkle', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Facet twinkle'}),
    ('Twinklehz', 'Float', 3.0, {'min': 0, 'max': 30, 'label': 'Twinkle rate Hz'}),
    ('Edgefade', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Fade toward the wall edge (screen units)'}),
    ('Kick', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Beat pulse -> flash'}),
    ('Colorby', 'Menu', 'light', {'names': COLORBY, 'labels': ['Light (stop per light)', 'Facet (random)',
                                                               'Position on the wall']}),
])]
DEFAULTS = {'Count': 4096, 'Persist': 0.0, 'Tonemap': 0, 'Palette': 4, 'Exposure': 2.5, 'Normalize': 1,
            'Size': 10.0, 'Sprite': 0, 'Glow': 0.8, 'Intensity': 1.0}
PANEL_PAGES = ['Mirrorball', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'disco', {'Lights': 2, 'Spin': 20.0, 'Colorby': 0, 'Palette': 4, 'Count': 4096, 'Size': 10.0}),
    (2, 'white club', {'Lights': 1, 'Spin': 12.0, 'Colorby': 1, 'Palette': 1, 'Colorar': 1.0, 'Colorag': 0.95,
                       'Colorab': 0.85, 'Count': 3000, 'Size': 12.0, 'Sprite': 3, 'Rays': 4}),
    (3, 'four colours', {'Lights': 4, 'Lightspread': 90.0, 'Spin': 30.0, 'Colorby': 0, 'Palette': 6, 'Count': 8192,
                         'Size': 8.0}),
    (4, 'beat flash', {'Lights': 2, 'Spin': 25.0, 'Kick': 3.0, 'Beatevery': 1.0, 'Beatgain': 1.0, 'Twinkle': 0.6,
                       'Colorby': 2, 'Palette': 5, 'Count': 4096, 'Size': 10.0}),
    (5, 'slow glints', {'Lights': 1, 'Spin': 6.0, 'Twinkle': 0.8, 'Twinklehz': 1.0, 'Colorby': 1, 'Palette': 5,
                        'Count': 2048, 'Size': 18.0, 'Sprite': 3, 'Rays': 6, 'Glow': 0.8}),
]
UNIFORMS = [('uM0', ['{Lights}', '{Spin}', '{Tilt}', '{Elevation}']),
            ('uM1', ['{Azimuth}', '{Lightspread}', '{Walldist}', '{Wallscale}']),
            ('uM2', ['{Spotsize}', '{Elongate}', '{Twinkle}', '{Twinklehz}']),
            ('uM3', ['{Edgefade}', '{Kick}', '{Colorby#}', '0'])]

STEP = """
vec3 mb_light(int j, int nl) {
    float az = radians(uM1.x + (nl > 1 ? uM1.y * (float(j) / float(nl - 1) - 0.5) : 0.0));
    float el = radians(uM0.w);
    return vec3(sin(az) * cos(el), sin(el), cos(az) * cos(el));      // direction from the ball TO the light
}
vec4 mb_eval(int i) {
    int nl = clamp(int(uM0.x + 0.5), 1, 4);
    int nf = max(NPTS / nl, 1);
    int j = i / nf, f = i - j * nf;
    if (j >= nl) return vec4(0.0);
    float z = 1.0 - 2.0 * (float(f) + 0.5) / float(nf);
    float rr = sqrt(max(0.0, 1.0 - z * z));
    float ph = float(f) * 2.39996323;
    vec3 n = vec3(rr * cos(ph), z, rr * sin(ph));                       // Fibonacci facet normal (y up)
    n.xz = rot2(n.xz, radians(uM0.y * T));                              // spin about y ...
    n.yz = rot2(n.yz, radians(uM0.z));                                  // ... tilted axis
    vec3 Ld = mb_light(j, nl);
    float face = dot(n, Ld);
    if (face <= 0.0) return vec4(0.0);
    vec3 r = 2.0 * face * n - Ld;                                       // reflect the incoming ray (-Ld)
    if (r.z >= -1e-3) return vec4(0.0);                                 // goes away from the wall
    float t = uM1.z / -r.z;
    vec2 w = r.xy * t * uM1.w;
    float a = face * (1.0 - uM2.z * rnd(f, uint(floor(T * uM2.w)) * 3u + 11u));
    a *= uM3.x > 0.0 ? clamp(1.0 - length(w) / uM3.x, 0.0, 1.0) : 1.0;
    if (a <= 0.0 || length(w) > 64.0) return vec4(0.0);                // off the wall: nothing (grazing rays
                                                                        // land far away with float32 noise)
    a *= 1.0 + uM3.y * ENV;                                             // flash (clamped at 1 by the pack) ...
    float sz = uM2.x * pow(1.0 / max(-r.z, 0.05), uM2.y) * (1.0 + 0.5 * uM3.y * ENV);   // ... and bigger spots
    int cb = int(uM3.z + 0.5);
    float kc = cb == 0 ? (float(j) + 0.5) / float(nl) : (cb == 1 ? rnd(f, 5u) : clamp(0.5 + 0.25 * w.x, 0.0, 0.999));
    return vec4(w, sz, packKA(kc, clamp(a, 0.0, 1.0)));
}
vec4 pt_seed(int i) { return mb_eval(i); }
vec4 pt_step(int i, vec4 s, float dt) { if (dt <= 0.0) return s; return mb_eval(i); }
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    P = vec3(s.xy, 0.0);
    PSIZE = s.z;
    float a = unpackA(s.w);
    C = vec4(ptpal(unpackK(s.w)), a);
    return a > 0.0;
}
"""
