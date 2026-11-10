# gen_sdf_aurora - GEN_sdf module 'aurora' (FX7a SX-13 + FX7c 7C-13; lane C, 27 Oct): volumetric aurora curtains
# over a star field, with an optional mirrored water reflection below the horizon. Clean-room (U8 default: no CC BY-NC-SA
# code): the research rows name nimitz "Auroras" (Shadertoy) and Gerardo LCDF's MIT Godot port; neither was copied.
# Technique, written fresh here: a fixed camera (yaw / tilt / FOV, slow yaw drift) looks up through N emission
# layers stacked above it (heights Height + i x Spacing); each ray meets layer i at t = h / rd.y, reads a curtain
# field there (4 octaves of a domain-warped triangle-wave pattern: thin bright folds, Sharp = thinner), colours it by
# the layer's height through the palette (duo default: green low -> magenta high) and adds it with an exponential
# height fade and a fixed distance haze exp(-0.035 t) (tames the far, aliased layers near the horizon); a horizon falloff, hashed stars (twinkle) and a mirrored, rippled copy for water. KIND 'flat'
# (render2d), so the rack's Quality / Upscale (FSR) / Still apply; default Quality 0.5. Loops capped (layers 64,
# octaves 4; T-124). Mirror: gen_sdf_logic.aurora_rm. ASCII only.
MODULE = 'aurora'
KIND = 'flat'
BLURB = 'Aurora curtains: N emission layers over a star field, palette by height, optional water mirror.'

PAGES = [('Aurora', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Layers', 'Int', 32, {'min': 4, 'max': 64, 'label': 'Layers (march steps, cap 64)'}),
    ('Height', 'Float', 1.0, {'min': 0.1, 'max': 5, 'label': 'Lowest layer height'}),
    ('Spacing', 'Float', 0.12, {'min': 0.005, 'max': 0.5, 'label': 'Layer spacing'}),
    ('Fade', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Fade with height'}),
    ('Scale', 'Float', 0.5, {'min': 0.02, 'max': 4, 'label': 'Curtain scale'}),
    ('Warp', 'Float', 0.6, {'min': 0, 'max': 2, 'label': 'Warp (fold wiggle)'}),
    ('Sharp', 'Float', 8.0, {'min': 0.5, 'max': 12, 'label': 'Sharpness (thin folds)'}),
    ('Intensity', 'Float', 2.0, {'min': 0, 'max': 8, 'label': 'Intensity'}),
    ('Flow', 'Float', 0.08, {'min': -1, 'max': 1, 'label': 'Curtain motion /s'}),
    ('Driftx', 'Float', 0.05, {'min': -1, 'max': 1, 'label': 'Drift x /s'}),
    ('Driftz', 'Float', 0.1, {'min': -1, 'max': 1, 'label': 'Drift z /s'}),
    ('Tilt', 'Float', 22.0, {'min': -30, 'max': 89, 'label': 'Camera tilt deg (up)'}),
    ('Yaw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Camera yaw deg'}),
    ('Yawspeed', 'Float', 0.0, {'min': -20, 'max': 20, 'label': 'Yaw drift deg/s'}),
    ('Fov', 'Float', 75.0, {'min': 20, 'max': 150, 'label': 'FOV deg (vertical)'}),
    ('Horizon', 'Float', 8.0, {'min': 0.5, 'max': 40, 'label': 'Horizon falloff'}),
    ('Stars', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Star density'}),
    ('Starscale', 'Float', 240.0, {'min': 20, 'max': 1000, 'label': 'Star grid (higher = smaller)'}),
    ('Twinkle', 'Float', 2.0, {'min': 0, 'max': 10, 'label': 'Twinkle /s'}),
    ('Reflect', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Water reflection below the horizon'}),
    ('Ripple', 'Float', 0.02, {'min': 0, 'max': 0.2, 'label': 'Water ripple'}),
    ('Beatglow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Beat pulse -> intensity'}),
    ('Audioglow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Audio level -> intensity'}),
])]
DEFAULTS = {'Quality': 0.5, 'Palette': 0, 'Colorar': 0.15, 'Colorag': 1.0, 'Colorab': 0.45, 'Colorbr': 0.7,
            'Colorbg': 0.2, 'Colorbb': 1.0, 'Bgcolorr': 0.0, 'Bgcolorg': 0.012, 'Bgcolorb': 0.035, 'Spread': 1.0}
PANEL_PAGES = ['Aurora', 'Render', 'Colour', 'Drive']
PRESETS = [
    (1, 'green curtains', {}),
    (2, 'violet storm', {'Warp': 1.2, 'Flow': 0.25, 'Sharp': 5.0, 'Intensity': 2.2, 'Driftz': 0.3, 'Colorar': 0.4,
                         'Colorag': 0.3, 'Colorab': 1.0, 'Colorbr': 1.0, 'Colorbg': 0.25, 'Colorbb': 0.6}),
    (3, 'polar mirror', {'Tilt': 6.0, 'Reflect': 0.6, 'Ripple': 0.03, 'Stars': 0.12, 'Fov': 70.0}),
    (4, 'beat veil', {'Beatevery': 1.0, 'Beatgain': 1.0, 'Beatdecay': 0.25, 'Beatglow': 1.0, 'Intensity': 1.0,
                      'Sharp': 5.0, 'Palette': 7, 'Spread': 0.8}),
    (5, 'slow drift', {'Layers': 48, 'Spacing': 0.08, 'Flow': 0.03, 'Driftx': 0.02, 'Driftz': 0.04,
                       'Yawspeed': 1.5, 'Palette': 4, 'Spread': 0.4}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
_R = 'math.radians'
UNIFORMS = [('uM0', ['{Layers}', '{Height}', '{Spacing}', '{Fade}']),
            ('uM1', ['{Scale}', '{Warp}', '{Sharp}', '{Intensity}']),
            ('uM2', ['{Flow}', '{Driftx}', '{Driftz}', _R + '({Tilt})']),
            ('uM3', [_R + '({Yaw})', _R + '({Yawspeed})', _R + '({Fov})', '{Horizon}']),
            ('uM4', ['{Stars}', '{Starscale}', '{Twinkle}', '{Reflect}']),
            ('uM5', ['{Ripple}', '{Beatglow}', '{Audioglow}', '0'])]

GLSL = """
float tw(float x) { return abs(fract(x) - 0.5) * 2.0; }
float curtain(vec2 q, float w) {
    float a = 0.0, amp = 0.5;
    for (int o = 0; o < 4; o++) {
        vec2 g = vec2(tw(q.y * 0.43 + w), tw(q.x * 0.31 - 0.7 * w));
        q += (g - 0.5) * uM1.y;
        a += amp * tw(q.x + 0.35 * tw(q.y * 0.23));
        q = vec2(0.8 * q.x - 0.6 * q.y, 0.6 * q.x + 0.8 * q.y) * 1.7;
        amp *= 0.5;
        w *= 1.3;
    }
    return pow(clamp(a / 0.9375, 0.0, 1.0), uM1.z);
}
vec3 adir(vec2 P) {
    vec2 uv = (P - 0.5 * RES) / RES.y;
    float yaw = uM3.x + uM3.y * T, pitch = uM2.w;
    vec3 ww = vec3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw));
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = cross(uu, ww);
    float fk = 0.5 / tan(0.5 * uM3.z);
    return normalize(uv.x * uu + uv.y * vv + fk * ww);
}
vec3 asky(vec3 rd, out float nsum) {
    nsum = 0.0;
    vec3 acc = vec3(0.0);
    if (rd.y <= 0.0) return acc;
    int N = int(uM0.x + 0.5);
    float inv = 1.0 / max(float(N - 1), 1.0);
    vec2 drift = vec2(uM2.y, uM2.z) * T;
    float w = uM2.x * T;
    for (int i = 0; i < MAXLAYER; i++) {
        if (i >= N) break;
        float k = float(i) * inv;
        float t = min((uM0.y + float(i) * uM0.z) / rd.y, 60.0);
        float n = curtain(rd.xz * t * uM1.x + drift, w);
        nsum += n;
        acc += palk(k) * (n * exp(-uM0.w * 4.0 * k - 0.035 * t));      // height fade + distance haze
    }
    float g = uM1.w * (1.0 + uM5.y * ENV + uM5.z * LEVEL) / max(float(N), 1.0) * 6.0;
    acc *= g * clamp(rd.y * uM3.w, 0.0, 1.0);
    nsum /= max(float(N), 1.0);
    if (uM4.x > 0.0) {                                   // stars: one candidate per cell of the scaled direction
        vec3 s = rd * uM4.y;
        ivec3 c = ivec3(floor(s));
        float h = h2(ivec2(c.x, c.y ^ (c.z * 7919)), SEED);
        if (h < uM4.x) {
            float h1 = h2(ivec2(c.y, c.z ^ (c.x * 7919)), SEED + 1u), h3 = h2(ivec2(c.z, c.x ^ (c.y * 7919)), SEED + 2u);
            vec3 sp = vec3(c) + 0.5 + (vec3(h1, h3, h / max(uM4.x, 1e-6)) - 0.5) * 0.5;
            float d = length(s - sp);
            float tw2 = 0.65 + 0.35 * sin(uM4.z * T + h1 * TAU);
            acc += vec3(1.0) * (max(0.0, 1.0 - d * 2.5) * tw2) * clamp(rd.y * 20.0, 0.0, 1.0);
        }
    }
    return acc;
}
vec4 render2d(vec2 P) {
    vec3 rd = adir(P);
    float nsum = 0.0;
    vec3 col;
    if (rd.y >= 0.0) {
        col = asky(rd, nsum);
    } else {
        col = vec3(0.0);
        if (uM4.w > 0.0) {
            float rp = uM5.x * sin(rd.x * 140.0 / max(-rd.y, 0.05) + T * 1.7) * sin(rd.z * 90.0 + T * 1.3);
            vec3 r2 = normalize(vec3(rd.x + rp, -rd.y, rd.z));
            col = asky(r2, nsum) * uM4.w * (0.6 + 0.4 * clamp(1.0 + rd.y * 4.0, 0.0, 1.0));
        }
    }
    if (int(uMat.y + 0.5) == 1) return vec4(nsum, rd.y, col.g, 1.0);
    return vec4(col, clamp(max(col.r, max(col.g, col.b)), 0.0, 1.0));
}
"""
