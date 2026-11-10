# gen_sdf_scene - GEN_sdf module 'scene' (FX5 G13, FX0 row 41): SDF raymarch toolkit with 8 preset scenes (box
# tunnel, gyroid cave, Menger sponge, Apollonian foam, blob orbit, neon lattice, city blocks, gyroscope rings),
# domain modifiers (Size, Repeat, Twist, Fold) and a live morph between two scenes (Scenea -> Sceneb: Morph +
# Morphswing ping-pong + beat pulse). Shading, camera, fog, glow: the shared ray core in gen_sdf.py.
# Techniques: IQ's SDF articles (primitives, smooth min, Menger, Apollonian; MIT snippets), written fresh here.
# Mirror: gen_sdf_logic.scene_*. ASCII only.
MODULE = 'scene'
KIND = 'ray'
BLURB = 'Sphere-traced SDF scene: Scenea / Sceneb morph, modifiers, shared camera + shading.'
SCENES = ['tunnel', 'gyroid', 'sponge', 'apollonian', 'blobs', 'lattice', 'city', 'rings', 'stairs']
SCENE_LABELS = ['Box tunnel', 'Gyroid cave (tunnel along z)', 'Menger sponge', 'Apollonian foam', 'Blob orbit', 'Neon lattice',
                'City blocks', 'Gyroscope rings', 'Dreamcore stairs (helix of floating steps)']

PAGES = [('Scene', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Scenea', 'Menu', 'sponge', {'names': SCENES, 'labels': SCENE_LABELS}),
    ('Sceneb', 'Menu', 'blobs', {'names': SCENES, 'labels': SCENE_LABELS}),
    ('Morph', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Morph A -> B'}),
    ('Morphswing', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Morph swing (ping-pong)'}),
    ('Morphrate', 'Float', 0.1, {'min': 0, 'max': 2, 'label': 'Morph swing rate /s'}),
    ('Beatmorph', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Beat pulse -> morph'}),
    ('Size', 'Float', 1.0, {'min': 0.1, 'max': 8, 'label': 'Size'}),
    ('Thickness', 'Float', 0.1, {'min': 0.005, 'max': 1, 'label': 'Thickness (walls / rods / rings)'}),
    ('Detail', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Detail (sponge iterations, apollonian +4, rings)'}),
    ('Smooth', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Smooth union k (blobs)'}),
    ('Blobs', 'Int', 8, {'min': 1, 'max': 16, 'label': 'Blob count (cap 16)'}),
    ('Shape', 'Float', 1.2, {'min': 0.8, 'max': 1.6, 'label': 'Apollonian shape'}),
    ('Twist', 'Float', 0.0, {'min': -3, 'max': 3, 'label': 'Twist (rad per unit y)'}),
    ('Fold', 'Int', 0, {'min': 0, 'max': 16, 'label': 'Kaleido fold around y (0 off, >= 2)'}),
    ('Repeat', 'Float', 0.0, {'min': 0, 'max': 16, 'label': 'Repeat cell (0 off)'}),
])]
DEFAULTS = {}
PANEL_PAGES = ['Scene', 'Render', 'Camera', 'Look', 'Colour', 'Drive']
PRESETS = [
    (1, 'box tunnel', {'Scenea': 0, 'Campath': 1, 'Flyspeed': 1.5, 'Camyaw': 0.0, 'Campitch': 0.0, 'Sway': 0.2,
                       'Rollspeed': 8.0, 'Thickness': 0.12, 'Material': 1, 'Palette': 6, 'Fogdensity': 0.12,
                       'Shadowsteps': 0, 'Aosteps': 4, 'Glow': 0.4, 'Spread': 0.6}),
    (2, 'gyroid cave', {'Scenea': 1, 'Campath': 1, 'Flyspeed': 0.7, 'Camyaw': 0.0, 'Campitch': 0.0, 'Sway': 0.3,
                        'Rollspeed': 6.0, 'Fov': 75.0, 'Thickness': 0.2, 'Material': 1, 'Palette': 7, 'Spread': 3.0,
                        'Fogdensity': 0.2, 'Shadowsteps': 0, 'Aosteps': 5, 'Stepscale': 0.8}),
    (3, 'menger sponge', {'Scenea': 2, 'Detail': 4, 'Camdist': 3.4, 'Campitch': 25.0, 'Orbitspeed': 8.0,
                          'Material': 1, 'Palette': 5, 'Ambient': 0.35, 'Lightintensity': 1.5, 'Fogdensity': 0.02,
                          'Shadowsteps': 24, 'Aosteps': 5}),
    (4, 'apollonian glow', {'Scenea': 3, 'Detail': 3, 'Epsilon': 1.0, 'Shape': 1.2, 'Camdist': 2.2, 'Campitch': 10.0,
                            'Orbitspeed': 6.0, 'Material': 3, 'Rim': 0.8, 'Palette': 2, 'Glow': 0.6,
                            'Fogdensity': 0.25, 'Shadowsteps': 0, 'Aosteps': 4, 'Stepscale': 0.8, 'Overrelax': 1.6}),
    (5, 'blob orbit', {'Scenea': 4, 'Blobs': 8, 'Smooth': 0.6, 'Camdist': 5.0, 'Campitch': 10.0, 'Material': 1,
                       'Palette': 0, 'Colorar': 0.85, 'Colorag': 0.9, 'Colorab': 1.0, 'Colorbr': 0.3,
                       'Colorbg': 0.45, 'Colorbb': 1.0, 'Specpower': 64.0,
                       'Audiogain': 1.0, 'Beatevery': 1.0, 'Beatgain': 1.0, 'Fogdensity': 0.0, 'Shadowsteps': 16}),
    (6, 'neon lattice', {'Scenea': 5, 'Campath': 1, 'Flyspeed': 1.0, 'Camyaw': 0.0, 'Campitch': 0.0,
                         'Targetx': 0.5, 'Targety': 0.5, 'Rollspeed': 12.0, 'Thickness': 0.06, 'Material': 3,
                         'Rim': 1.0, 'Emissive': 0.3, 'Palette': 6, 'Glow': 1.0, 'Glowfalloff': 12.0,
                         'Fogdensity': 0.15, 'Shadowsteps': 0, 'Aosteps': 0}),
    (7, 'city beat', {'Scenea': 6, 'Camdist': 7.0, 'Campitch': 35.0, 'Targety': -0.5, 'Orbitspeed': 6.0,
                      'Material': 4, 'Rim': 0.4, 'Palette': 6, 'Ambient': 0.4, 'Beatevery': 1.0, 'Beatgain': 1.0, 'Beatyaw': 15.0,
                      'Fogdensity': 0.06, 'Shadowsteps': 16, 'Aosteps': 4}),
    (8, 'gyroscope', {'Scenea': 7, 'Detail': 5, 'Thickness': 0.12, 'Camdist': 4.5, 'Campitch': 20.0,
                      'Material': 2, 'Palette': 5, 'Fogdensity': 0.0, 'Shadowsteps': 24, 'Aosteps': 5}),
    (10, 'dreamcore', {'Scenea': 8, 'Camdist': 6.5, 'Campitch': 12.0, 'Targety': 0.6, 'Orbitspeed': 7.0, 'Fov': 55.0,
                       'Thickness': 0.1, 'Material': 1, 'Palette': 0, 'Colorar': 0.95, 'Colorag': 0.93, 'Colorab': 0.9,
                       'Colorbr': 1.0, 'Colorbg': 0.85, 'Colorbb': 0.55, 'Spread': 1.0, 'Lightintensity': 1.4,
                       'Ambient': 0.45, 'Bgcolorr': 0.86, 'Bgcolorg': 0.78, 'Bgcolorb': 0.92, 'Fogdensity': 0.05,
                       'Shadowsteps': 8, 'Aosteps': 2, 'Quality': 0.4, 'Glow': 0.25, 'Glowfalloff': 6.0,
                       'Glowhue': 1.0}),
    (9, 'morph sponge-blobs', {'Scenea': 2, 'Sceneb': 4, 'Morphswing': 1.0, 'Morphrate': 0.1, 'Camdist': 4.0,
                               'Campitch': 20.0, 'Stepscale': 0.9, 'Material': 1, 'Palette': 7, 'Fogdensity': 0.02,
                               'Shadowsteps': 16, 'Aosteps': 4}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
UNIFORMS = [('uM0', ['{Scenea#}', '{Sceneb#}', '{Morph}', '{Morphswing}']),
            ('uM1', ['{Morphrate}', '{Beatmorph}', '{Size}', '{Thickness}']),
            ('uM2', ['{Detail}', '{Smooth}', '{Blobs}', '{Twist}']),
            ('uM3', ['{Fold}', '{Repeat}', '{Shape}', '0'])]

GLSL = """
float PUL; float MORPH; vec3 BC[16]; float BR[16]; vec4 RC[6];
void setup() {
    PUL = 1.0 + LEVEL + ENV;
    MORPH = clamp(uM0.z + uM0.w * (0.5 - 0.5 * cos(TAU * uM1.x * T)) + uM1.y * ENV, 0.0, 1.0);
    for (int i = 0; i < 16; i++) {
        float fi = float(i);
        BC[i] = 1.2 * vec3(sin(T * 0.7 * (1.0 + 0.13 * fi) + fi * 1.7), cos(T * 0.53 * (1.0 + 0.11 * fi) + fi * 2.3),
                           sin(T * 0.61 * (1.0 + 0.07 * fi) + fi * 0.9));
        BR[i] = 0.35 * (0.6 + 0.4 * fract(fi * 0.618034)) * (1.0 + 0.5 * LEVEL + 0.3 * ENV);
    }
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float a1 = T * (0.4 + 0.15 * fi) + fi, a2 = T * (0.3 + 0.1 * fi) + 0.5 * fi;
        RC[i] = vec4(cos(a1), sin(a1), cos(a2), sin(a2));
    }
}
float sc_tunnel(vec3 p) {
    float m = max(abs(p.x), abs(p.y));
    float qz = mod(p.z + 0.5, 1.0) - 0.5;
    return min(1.2 - m, max(abs(qz) - 0.5 * uM1.w * PUL, 0.95 - m));
}
float sc_gyroid(vec3 p) {
    vec3 q = 2.0 * p;
    return max((abs(dot(sin(q), cos(q.zxy))) - uM1.w * PUL) * 0.25, 0.8 - length(p.xy));
}
float sc_sponge(vec3 p) {
    float d = sdBox(p, vec3(1.0)), s = 1.0;
    int n = int(uM2.x + 0.5);
    for (int i = 0; i < 8; i++) {
        if (i >= n) break;
        vec3 a = mod(p * s, 2.0) - 1.0;
        s *= 3.0;
        vec3 r = abs(1.0 - 3.0 * abs(a));
        float c = (min(max(r.x, r.y), min(max(r.y, r.z), max(r.z, r.x))) - 1.0) / s;
        d = max(d, c);
    }
    return d;
}
float sc_apollo(vec3 p, out float orb) {
    float sc = 1.0;
    orb = 1e10;
    int n = int(uM2.x + 0.5) + 4;
    for (int i = 0; i < 12; i++) {
        if (i >= n) break;
        p = -1.0 + 2.0 * fract(0.5 * p + 0.5);
        float r2 = max(dot(p, p), 1e-6);
        orb = min(orb, r2);
        float k = uM3.z / r2;
        p *= k;
        sc *= k;
    }
    return 0.25 * abs(p.y) / sc;
}
float sc_blobs(vec3 p) {
    float d = 1e10;
    int n = int(uM2.z + 0.5);
    for (int i = 0; i < 16; i++) {
        if (i >= n) break;
        d = smin(d, length(p - BC[i]) - BR[i], uM2.y);
    }
    return d;
}
float sc_lattice(vec3 p) {
    vec3 q = p - floor(p + 0.5);
    return min(min(length(q.yz), length(q.xz)), length(q.xy)) - 0.5 * uM1.w * PUL;
}
float sc_city(vec3 p) {
    vec2 id = floor(p.xz + 0.5);
    vec2 q = p.xz - id;
    ivec2 ii = ivec2(id);
    float h = (0.3 + 1.5 * h2(ii, SEED) + 0.8 * ENV * h2(ii, SEED + 7u)) * (1.0 + 0.5 * LEVEL);
    float b = sdBox(vec3(q.x, p.y + 1.0 - h, q.y), vec3(0.35, h, 0.35));
    return min(p.y + 1.0, min(b, 0.55 - max(abs(q.x), abs(q.y))));
}
float sc_rings(vec3 p) {
    float d = 1e10;
    int n = clamp(int(uM2.x + 0.5), 1, 6);
    for (int i = 0; i < 6; i++) {
        if (i >= n) break;
        vec4 r = RC[i];
        vec3 q = p;
        q.yz = vec2(r.x * q.y - r.y * q.z, r.y * q.y + r.x * q.z);
        q.xy = vec2(r.z * q.x - r.w * q.y, r.w * q.x + r.z * q.y);
        float R = 1.5 - 0.22 * float(i);
        d = min(d, length(vec2(length(q.xz) - R, q.y)) - 0.5 * uM1.w * PUL);
    }
    return d;
}
float sc_stairs(vec3 p) {       // TC-35 dreamcore: 24 steps on a helix; angle + height -> step index, 3 boxes tested
    const float DA = TAU / 12.0, DH = 0.2, RH = 1.6, NS = 24.0;
    float y0 = 0.5 * NS * DH;
    float ka = atan(p.z, p.x) / DA;
    float kc = ka + 12.0 * floor(((p.y + y0) / DH - ka) / 12.0 + 0.5);
    float d = 1e10;
    for (int j = 0; j < 3; j++) {
        float k = floor(kc + 0.5) + float(j - 1);
        if (k < 0.0 || k > NS - 1.0) continue;
        float th = k * DA;
        vec3 q = p - vec3(RH * cos(th), k * DH - y0 + 0.05 * sin(T * 1.3 + k), RH * sin(th));
        q.xz = rot2(q.xz, -th);                           // step frame: x radial, z along the helix
        q.xy = rot2(q.xy, 0.08 * sin(T * 0.9 + 0.7 * k));
        d = min(d, sdBox(q, vec3(0.38, 0.4 * uM1.w * PUL, 0.24)) - 0.02);
    }
    float thd = NS * DA;
    vec3 q = p - vec3(RH * cos(thd), NS * DH - y0 + 0.55, RH * sin(thd));
    q.xz = rot2(q.xz, -thd);
    float door = max(sdBox(q, vec3(0.08, 0.78, 0.5)), -sdBox(q, vec3(0.3, 0.64, 0.36)));
    door = min(door, sdBox(q, vec3(0.012, 0.64, 0.36)));
    float cl = p.y + y0 + 0.7 + 0.25 * sin(p.x * 1.1 + T * 0.15) * sin(p.z * 0.9 - T * 0.1);
    return min(min(d, door), cl);
}
float scene(int id, vec3 p) {
    if (id == 0) return sc_tunnel(p);
    if (id == 1) return sc_gyroid(p);
    if (id == 2) return sc_sponge(p);
    if (id == 3) { float o; return sc_apollo(p, o); }
    if (id == 4) return sc_blobs(p);
    if (id == 5) return sc_lattice(p);
    if (id == 6) return sc_city(p);
    if (id == 7) return sc_rings(p);
    return sc_stairs(p);
}
float scenek(int id, vec3 p) {
    if (id == 0) return 0.1 * p.z + 0.2 * max(abs(p.x), abs(p.y));
    if (id == 1) return 0.1 * (p.x + p.y + p.z);
    if (id == 2) return 0.3 * length(p);
    if (id == 3) { float o; float d = sc_apollo(p, o); return 0.5 * sqrt(o); }
    if (id == 4) return 0.25 * p.y + 0.15 * length(p);
    if (id == 5) return 0.05 * (floor(p.x + 0.5) + floor(p.y + 0.5) + floor(p.z + 0.5));
    if (id == 6) return h2(ivec2(floor(p.xz + 0.5)), SEED + 3u) + 0.1 * p.y;
    if (id == 7) return 0.2 * length(p);
    return p.y > 2.6 ? 1.0 : 0.15 + 0.15 * clamp((p.y + 2.4) / 4.8, 0.0, 1.0);
}
vec3 domain(vec3 p) {
    p /= uM1.z;
    if (uM3.y > 0.0) p = p - uM3.y * floor(p / uM3.y + 0.5);
    if (uM2.w != 0.0) p.xz = rot2(p.xz, uM2.w * p.y);
    if (uM3.x >= 2.0) {
        float sec = TAU / floor(uM3.x + 0.5);
        float a = abs(mod(atan(p.z, p.x) + 0.5 * sec, sec) - 0.5 * sec);
        p.xz = length(p.xz) * vec2(cos(a), sin(a));
    }
    return p;
}
float map(vec3 p) {
    vec3 q = domain(p);
    float d = MORPH < 1.0 ? scene(int(uM0.x + 0.5), q) : 0.0;
    if (MORPH > 0.0) d = mix(d, scene(int(uM0.y + 0.5), q), MORPH);
    return d * uM1.z;
}
float mapk(vec3 p) {
    vec3 q = domain(p);
    float k = MORPH < 1.0 ? scenek(int(uM0.x + 0.5), q) : 0.0;
    if (MORPH > 0.0) k = mix(k, scenek(int(uM0.y + 0.5), q), MORPH);
    return k;
}
"""
