# gen_points_hyperspace - GEN_points module 'hyperspace' (FX7c card 18, ISF "Hyperspace" / Arena WarpSpeed idea;
# clean-room): stars rush at the camera and stretch into streaks with speed. Each star = Samples points spread along
# its streak (evenly in screen space: uniform in 1/z between the head and the tail, the tail Stretch seconds of travel
# behind), jittered every frame (Jitter) so Persist or the eye joins them into lines. Stateless: depth = a pure
# function of module time (Warp x module clock: ramp the Drive Speed for a build-up, no jump), each pass through the
# volume re-rolls the star's place (field / tunnel wall / disc). Streak length follows the live speed (Speed x
# (1 + Audiospeed x level)) x Stretch x (1 + Kick x beat pulse); colour by depth / star / speed (the jump shifts the
# palette). Mirror: gen_points_logic.hyperspace_*. ASCII only.
MODULE = 'hyperspace'
KIND = '2d'
BLURB = 'Star streaks: stars rush at the camera, streak length = speed x Stretch; field / tunnel / disc.'
FIELDS = ['field', 'tunnel', 'disc']
COLORBY = ['depth', 'star', 'speed']
EFFECTORS = None
EPOCH = '0'
CHECK = {'t': 2.0}

PAGES = [('Hyperspace', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Warp', 'Float', 6.0, {'min': 0, 'max': 100, 'label': 'Warp (depth units per module s)'}),
    ('Stretch', 'Float', 0.08, {'min': 0, 'max': 2, 'label': 'Streak = s of travel (0 = dots)'}),
    ('Samples', 'Int', 16, {'min': 1, 'max': 256, 'label': 'Points per streak'}),
    ('Jitter', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Re-scatter along the streak per frame'}),
    ('Near', 'Float', 0.3, {'min': 0.01, 'max': 10, 'label': 'Near depth'}),
    ('Far', 'Float', 20.0, {'min': 0.5, 'max': 200, 'label': 'Far depth (spawn)'}),
    ('Fov', 'Float', 70.0, {'min': 5, 'max': 170, 'label': 'Field of view deg'}),
    ('Field', 'Menu', 'field', {'names': FIELDS, 'labels': ['Star field (square)', 'Tunnel wall (ring)', 'Disc']}),
    ('Fieldsize', 'Float', 3.0, {'min': 0.05, 'max': 50, 'label': 'Field half size / tunnel radius'}),
    ('Inner', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Tunnel inner radius (share)'}),
    ('Tailfade', 'Float', 1.5, {'min': 0, 'max': 8, 'label': 'Tail fade (power)'}),
    ('Fadein', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Fade in from far (share of depth)'}),
    ('Kick', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Beat pulse -> stretch'}),
    ('Colorby', 'Menu', 'depth', {'names': COLORBY, 'labels': ['Depth', 'Star (random)', 'Speed']}),
    ('Speedref', 'Float', 2.0, {'min': 0.01, 'max': 20, 'label': 'Speed for palette 1 (Colorby speed)'}),
])]
DEFAULTS = {'Count': 32768, 'Persist': 0.3, 'Tonemap': 0, 'Palette': 4, 'Exposure': 3.0, 'Normalize': 1,
            'Size': 1.0, 'Glow': 0.0}
PANEL_PAGES = ['Hyperspace', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'cruise', {'Warp': 6.0, 'Stretch': 0.08, 'Samples': 16, 'Field': 0, 'Colorby': 0, 'Palette': 4,
                   'Count': 32768}),
    (2, 'jump', {'Warp': 30.0, 'Stretch': 0.25, 'Samples': 48, 'Field': 0, 'Colorby': 2, 'Speedref': 3.0,
                 'Palette': 6, 'Count': 65536, 'Exposure': 3.5, 'Persist': 0.5}),
    (3, 'tunnel', {'Warp': 12.0, 'Stretch': 0.15, 'Samples': 32, 'Field': 1, 'Fieldsize': 1.5, 'Inner': 0.8,
                   'Colorby': 1, 'Palette': 5, 'Count': 65536, 'Rotspeed': 12.0}),
    (4, 'beat streaks', {'Warp': 10.0, 'Stretch': 0.05, 'Samples': 32, 'Kick': 4.0, 'Beatevery': 1.0,
                         'Beatgain': 1.0, 'Colorby': 0, 'Palette': 3, 'Count': 65536}),
    (5, 'snowfield dots', {'Warp': 2.0, 'Stretch': 0.0, 'Samples': 1, 'Field': 2, 'Fieldsize': 4.0, 'Size': 2.0,
                           'Sprite': 0, 'Colorby': 1, 'Palette': 4, 'Count': 16384, 'Exposure': 1.5,
                           'Persist': 0.0}),
]
UNIFORMS = [('uM0', ['{Warp}', '{Stretch}', '{Samples}', '{Jitter}']),
            ('uM1', ['{Near}', '{Far}', '{Fov}', '{Field#}']),
            ('uM2', ['{Fieldsize}', '{Inner}', '{Tailfade}', '{Fadein}']),
            ('uM3', ['{Kick}', '{Colorby#}', '{Speedref}', '0']),
            ('uM4', ['{Speed}', '{Audiospeed}', '0', '0'])]

STEP = """
vec4 hs_eval(int i) {
    int S = max(int(uM0.z + 0.5), 1);
    int s = i / S, k = i - s * S;
    float L = max(uM1.y - uM1.x, 1e-3);
    float spd = uM0.x * uM4.x * (1.0 + uM4.y * uDrv.w);                  // live speed (depth units / wall s)
    float x = rnd(s, 61u) * L + uM0.x * T;
    float n = floor(x / L);
    float zh = uM1.y - (x - n * L);                                       // head depth: Far -> Near, then again
    uint sl = uint(int(n)) * 4u;
    float r0 = rnd(s, sl + 200u), r1 = rnd(s, sl + 201u);
    int fm = int(uM1.w + 0.5);
    vec2 q;
    if (fm == 0) q = (vec2(r0, r1) * 2.0 - 1.0) * uM2.x;
    else {
        float rr = fm == 1 ? mix(uM2.y, 1.0, r0) : sqrt(r0);
        q = uM2.x * rr * vec2(cos(TAU * r1), sin(TAU * r1));
    }
    float zt = zh + spd * uM0.y * (1.0 + uM3.x * ENV);                   // tail: Stretch s of travel behind
    float u = S > 1 ? (float(k) + uM0.w * rnd(i, FR * 2u + 7u)) / float(S) : 0.0;
    float iz = mix(1.0 / zh, 1.0 / zt, u);                                // even in screen space
    float F = 1.0 / tan(radians(uM1.z) * 0.5);
    vec2 P = q * (iz * F);
    float a = pow(max(1.0 - u, 0.0), uM2.z);
    float fi = uM2.w > 0.0 ? clamp((uM1.y - zh) / (uM2.w * L), 0.0, 1.0) : 1.0;
    a *= fi * clamp(uM1.y / zh / 4.0, 0.0, 1.0);                          // nearer = brighter (1 at Far / 4)
    int cb = int(uM3.y + 0.5);
    float kc = cb == 0 ? clamp(1.0 - zh / uM1.y, 0.0, 0.999) : (cb == 1 ? rnd(s, 5u) : clamp(spd / max(uM3.z, 1e-6), 0.0, 4.0) * 0.249);
    return vec4(P, 0.0, packKA(kc, a));
}
vec4 pt_seed(int i) { return hs_eval(i); }
vec4 pt_step(int i, vec4 s, float dt) { if (dt <= 0.0) return s; return hs_eval(i); }
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    P = vec3(s.xy, 0.0);
    float a = unpackA(s.w);
    C = vec4(ptpal(unpackK(s.w)), a);
    return a > 0.0;
}
"""
