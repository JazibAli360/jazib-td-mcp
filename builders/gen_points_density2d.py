# gen_points_density2d - GEN_points module 'density2d' (FX5 G04): 2D iterated maps (Clifford, Peter de Jong, Svensson,
# Bedhead, Tinkerbell) drawn as additive 1-px dust; with Persist + log tone = the classic log-density image. Every
# point is iterated Iterations times per frame (dt > 0), escapes / NaN re-seed; params drift (LFO), audio (Audiogain)
# and the beat pulse (Kick) nudge a b c d. Fold = rotational copies. Mirror: gen_points_logic.density2d_*.
# Parameter sets: Paul Bourke's pages (docs/research/FX7_gen_points_sources.md). ASCII only.
MODULE = 'density2d'
KIND = '2d'
BLURB = 'x\' = f(x, y): Clifford / de Jong / Svensson / Bedhead / Tinkerbell, Iterations per frame.'
MAPS = ['clifford', 'dejong', 'svensson', 'bedhead', 'tinkerbell']
COLORBY = ['speed', 'angle', 'radius', 'index']
EFFECTORS = None            # map dynamics re-converge within a few iterations: a push would not show
EPOCH = '0'
W_IS_ANGLE = True        # state w = the motion angle (colour coordinate; live check compares it wrapped)

PAGES = [('Density', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Map', 'Menu', 'clifford', {'names': MAPS, 'labels': ['Clifford', 'Peter de Jong', 'Svensson', 'Bedhead',
                                                          'Tinkerbell']}),
    ('A', 'Float', -1.4, {'min': -3, 'max': 3, 'label': 'a'}),
    ('B', 'Float', 1.6, {'min': -3, 'max': 3, 'label': 'b'}),
    ('C', 'Float', 1.0, {'min': -3, 'max': 3, 'label': 'c'}),
    ('D', 'Float', 0.7, {'min': -3, 'max': 3, 'label': 'd'}),
    ('Drift', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Drift (LFO amplitude on a b c d)'}),
    ('Driftspeed', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Drift Hz'}),
    ('Iterations', 'Int', 2, {'min': 1, 'max': 16, 'label': 'Iterations per frame'}),
    ('Colorby', 'Menu', 'speed', {'names': COLORBY, 'labels': ['Jump length', 'Jump angle', 'Radius', 'Index']}),
    ('Kick', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Beat pulse -> params'}),
])]
DEFAULTS = {'Count': 65536, 'Persist': 0.9, 'Tonemap': 2, 'Exposure': 0.0, 'Palette': 0, 'Respawn': 0.0}
PANEL_PAGES = ['Density', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'lace', {'Map': 0, 'A': -1.4, 'B': 1.6, 'C': 1.0, 'D': 0.7, 'Iterations': 2, 'Colorby': 0, 'Palette': 0,
                 'Tonemap': 2, 'Persist': 0.9, 'Count': 65536, 'Spread': 1.5}),
    (2, 'smoke', {'Map': 1, 'A': 1.4, 'B': -2.3, 'C': 2.4, 'D': -2.1, 'Iterations': 2, 'Colorby': 1, 'Palette': 4,
                  'Tonemap': 2, 'Persist': 0.95, 'Count': 65536, 'Drift': 0.05, 'Driftspeed': 0.03}),
    (3, 'starfield', {'Map': 0, 'A': 1.7, 'B': 1.7, 'C': 0.6, 'D': 1.2, 'Iterations': 1, 'Colorby': 2,
                      'Palette': 3, 'Tonemap': 0, 'Persist': 0.0, 'Count': 65536, 'Exposure': -1.0, 'Size': 1.0}),
    (4, 'bedhead fold', {'Map': 3, 'A': -0.81, 'B': -0.92, 'Iterations': 2, 'Colorby': 0, 'Palette': 6,
                         'Tonemap': 2, 'Persist': 0.9, 'Count': 65536, 'Fold': 4, 'Fit': 0.8}),
    (5, 'beat drift', {'Map': 2, 'A': 1.5, 'B': -1.8, 'C': 1.6, 'D': 0.9, 'Iterations': 3, 'Colorby': 1,
                       'Palette': 5, 'Tonemap': 2, 'Persist': 0.85, 'Count': 65536, 'Drift': 0.08,
                       'Driftspeed': 0.05, 'Kick': 1.0, 'Beatevery': 1.0, 'Beatgain': 1.0}),
]
UNIFORMS = [('uM0', ['{Map#}', '{A}', '{B}', '{C}']),
            ('uM1', ['{D}', '{Drift}', '{Driftspeed}', '{Iterations}']),
            ('uM2', ['{Colorby#}', '{Kick}', '0', '0'])]

COMMON = """
const vec2 D2_CEN[5] = vec2[5](vec2(0.0), vec2(0.0), vec2(0.0), vec2(0.0), vec2(-0.4, -0.5));
vec4 d2_params() {
    return vec4(uM0.yzw, uM1.x) + uM1.y * sin(TAU * uM1.z * T + vec4(0.0, 1.7, 3.1, 4.5))
         + (LEVEL + uM2.y * ENV) * vec4(0.15, -0.15, 0.075, -0.075);
}
float d2_ext(int m, vec4 p) {
    if (m == 0) return max(1.0 + abs(p.z), 1.0 + abs(p.w));
    if (m == 1) return 2.0;
    if (m == 2) return max(abs(p.w) + 1.0, abs(p.z) + 1.0);
    if (m == 3) return 3.0;
    return 1.05;
}
"""

STEP = """
vec2 d2_map(int m, vec2 q, vec4 p) {
    float x = q.x, y = q.y;
    if (m == 0) return vec2(sin(p.x * y) + p.z * cos(p.x * x), sin(p.y * x) + p.w * cos(p.y * y));
    if (m == 1) return vec2(sin(p.x * y) - cos(p.y * x), sin(p.z * x) - cos(p.w * y));
    if (m == 2) return vec2(p.w * sin(p.x * x) - sin(p.y * y), p.z * cos(p.x * x) + cos(p.y * y));
    if (m == 3) { float b = abs(p.y) > 1e-3 ? p.y : 1e-3; return vec2(sin(x * y / b) * y + cos(p.x * x - y), x + sin(y) / b); }
    return vec2(x * x - y * y + p.x * x + p.y * y, 2.0 * x * y + p.z * x + p.w * y);
}
vec4 d2_seed(int i, uint salt) {
    int m = int(uM0.x + 0.5);
    vec4 pa = d2_params();
    float e = d2_ext(m, pa);
    vec2 p = D2_CEN[min(m, 4)] + (vec2(rnd(i, salt), rnd(i, salt + 1u)) * 2.0 - 1.0) * e * 0.5;
    vec2 q = p;
    for (int k = 0; k < 12; k++) { q = p; p = d2_map(m, p, pa); }
    vec2 dl = p - q;
    return vec4(p, length(dl), atan(dl.y, dl.x));
}
vec4 pt_seed(int i) { return d2_seed(i, 11u); }
vec4 pt_step(int i, vec4 s, float dt) {
    if (dt <= 0.0) return s;
    int m = int(uM0.x + 0.5);
    vec4 pa = d2_params();
    int it = clamp(int(uM1.w + 0.5), 1, 64);
    vec2 p = s.xy, q = p;
    for (int k = 0; k < 64; k++) { if (k >= it) break; q = p; p = d2_map(m, p, pa); }
    bool bad = !(dot(p, p) < 1e8);
    if (bad || rnd(i, FR * 4u + 3u) < uSt2.x * dt) return d2_seed(i, FR * 4u + 7u);
    vec2 dl = p - q;
    return vec4(p, length(dl), atan(dl.y, dl.x));
}
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    int m = int(uM0.x + 0.5);
    vec4 pa = d2_params();
    float e = d2_ext(m, pa);
    P = vec3((s.xy - D2_CEN[min(m, 4)]) * (min(ASP, 1.0) * 0.95 / e), 0.0);
    int cb = int(uM2.x + 0.5);
    float k = cb == 0 ? s.z / e : (cb == 1 ? s.w / TAU + 0.5 : (cb == 2 ? length(s.xy) / e : rnd(i, 5u)));
    C = vec4(ptpal(k), 1.0);
    return dot(s.xy, s.xy) < 1e8;
}
"""
