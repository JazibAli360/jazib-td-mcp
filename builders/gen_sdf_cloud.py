# gen_sdf_cloud - GEN_sdf module 'cloud' (FX7a SX-17; lane C2, 27 Oct): a volumetric cloud deck lit by a low sun,
# silver linings, sky behind, slow camera push. Clean-room (U8 default): the research row names IQ "Clouds"
# (Shadertoy, CC BY-NC-SA, not seen), Maxime Heckel's cloudscape article and a Godot shader; none was copied. Technique,
# written fresh here: a slab between Base and Top; density = fbm of 3D value noise (Octaves, cap 6; one 32-bit integer
# hash per lattice corner, so GPU and mirror agree exactly) shaped by a height profile and Coverage, moved by Wind and
# Evolve. The ray is clipped to the slab (and Maxdist) and marched in Steps equal steps (cap 64) with a per-pixel hashed
# start offset (Dither); each sample with density takes one light sample toward the sun (Lightoctaves, Lightstep),
# Beer-Lambert opacity, a Henyey-Greenstein forward lobe (Silver) mixed with an isotropic part, ambient from the sky
# rising with height, aerial fade to the horizon (Fogdensity); the march stops when the transmittance drops below
# 0.01. Sky behind = Bgcolor horizon -> Skycolor zenith + sun glow / disk. KIND 'flat'; default Quality 0.35 (soft
# subject: bilinear upscale is fine; FSR is opt-in). Mirror: gen_sdf_logic.cloud_rm. ASCII only.
MODULE = 'cloud'
KIND = 'flat'
BLURB = 'Volumetric cloud deck: 3D value-noise fbm in a slab, sun light sample, silver lining, sky behind.'

PAGES = [('Cloud', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Steps', 'Int', 24, {'min': 4, 'max': 64, 'label': 'March steps (cap 64)'}),
    ('Octaves', 'Int', 4, {'min': 1, 'max': 6, 'label': 'Noise octaves (cap 6)'}),
    ('Lightoctaves', 'Int', 2, {'min': 1, 'max': 6, 'label': 'Light sample octaves (cap 6)'}),
    ('Base', 'Float', 1.5, {'min': -10, 'max': 20, 'label': 'Deck base height'}),
    ('Top', 'Float', 4.0, {'min': -9, 'max': 30, 'label': 'Deck top height'}),
    ('Scale', 'Float', 0.35, {'min': 0.02, 'max': 4, 'label': 'Noise scale'}),
    ('Coverage', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Coverage'}),
    ('Density', 'Float', 3.0, {'min': 0, 'max': 20, 'label': 'Density'}),
    ('Absorb', 'Float', 2.5, {'min': 0, 'max': 20, 'label': 'Light absorption'}),
    ('Lightstep', 'Float', 0.6, {'min': 0.05, 'max': 4, 'label': 'Light sample distance'}),
    ('Silver', 'Float', 0.6, {'min': 0, 'max': 0.95, 'label': 'Silver lining (forward scatter g)'}),
    ('Ambient', 'Float', 0.6, {'min': 0, 'max': 2, 'label': 'Sky ambient'}),
    ('Maxdist', 'Float', 40.0, {'min': 2, 'max': 400, 'label': 'Max march distance'}),
    ('Fogdensity', 'Float', 0.03, {'min': 0, 'max': 0.5, 'label': 'Aerial fade to the horizon'}),
    ('Dither', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Start dither (hides banding)'}),
    ('Windx', 'Float', 0.3, {'min': -5, 'max': 5, 'label': 'Wind x /s'}),
    ('Windz', 'Float', 0.15, {'min': -5, 'max': 5, 'label': 'Wind z /s'}),
    ('Evolve', 'Float', 0.05, {'min': -2, 'max': 2, 'label': 'Evolve /s'}),
    ('Camheight', 'Float', 0.0, {'min': -10, 'max': 30, 'label': 'Camera height'}),
    ('Flyspeed', 'Float', 0.0, {'min': -20, 'max': 20, 'label': 'Camera push /s (along Yaw)'}),
    ('Pitch', 'Float', 14.0, {'min': -89, 'max': 89, 'label': 'Camera pitch deg'}),
    ('Yaw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Camera yaw deg'}),
    ('Yawspeed', 'Float', 0.0, {'min': -30, 'max': 30, 'label': 'Yaw drift deg/s'}),
    ('Fov', 'Float', 70.0, {'min': 20, 'max': 150, 'label': 'FOV deg (vertical)'}),
    ('Skycolor', 'RGB', (0.2, 0.4, 0.75), {'label': 'Sky zenith colour (horizon = Bgcolor)'}),
    ('Suncolor', 'RGB', (1.0, 0.85, 0.65), {'label': 'Sun colour'}),
    ('Sunintensity', 'Float', 2.0, {'min': 0, 'max': 10, 'label': 'Sun intensity'}),
    ('Sunyaw', 'Float', 10.0, {'min': -180, 'max': 180, 'label': 'Sun yaw deg'}),
    ('Sunpitch', 'Float', 10.0, {'min': -10, 'max': 89, 'label': 'Sun pitch deg'}),
    ('Beatlight', 'Float', 0.0, {'min': -1, 'max': 4, 'label': 'Beat pulse -> sun light'}),
    ('Audiolight', 'Float', 0.0, {'min': -1, 'max': 4, 'label': 'Audio level -> sun light'}),
])]
DEFAULTS = {'Quality': 0.35, 'Palette': 0, 'Bgcolorr': 0.75, 'Bgcolorg': 0.72, 'Bgcolorb': 0.7}
PANEL_PAGES = ['Cloud', 'Render', 'Colour', 'Drive']
PRESETS = [
    (1, 'cumulus day', {}),
    (2, 'golden hour', {'Sunpitch': 3.0, 'Sunyaw': 0.0, 'Suncolorr': 1.0, 'Suncolorg': 0.6, 'Suncolorb': 0.3,
                        'Sunintensity': 3.0, 'Skycolorr': 0.25, 'Skycolorg': 0.3, 'Skycolorb': 0.55,
                        'Bgcolorr': 0.95, 'Bgcolorg': 0.62, 'Bgcolorb': 0.4, 'Silver': 0.75, 'Pitch': 8.0}),
    (3, 'fly through', {'Steps': 32, 'Base': 0.0, 'Top': 8.0, 'Camheight': 3.0, 'Flyspeed': 2.0, 'Pitch': 2.0,
                        'Coverage': 0.45, 'Density': 4.0, 'Fogdensity': 0.02, 'Maxdist': 30.0, 'Scale': 0.3}),
    (4, 'storm deck', {'Coverage': 0.75, 'Density': 6.0, 'Absorb': 5.0, 'Sunintensity': 0.8, 'Ambient': 0.35,
                       'Skycolorr': 0.25, 'Skycolorg': 0.27, 'Skycolorb': 0.32, 'Bgcolorr': 0.4, 'Bgcolorg': 0.41,
                       'Bgcolorb': 0.44, 'Windx': 0.9, 'Evolve': 0.2, 'Beatevery': 1.0, 'Beatgain': 1.0,
                       'Beatdecay': 0.15, 'Beatlight': 3.0}),
    (5, 'above the clouds', {'Camheight': 6.0, 'Pitch': -10.0, 'Top': 3.5, 'Coverage': 0.55, 'Sunpitch': 6.0,
                             'Skycolorr': 0.1, 'Skycolorg': 0.22, 'Skycolorb': 0.55, 'Flyspeed': 1.0}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
_R = 'math.radians'
UNIFORMS = [('uM0', ['{Steps}', '{Octaves}', '{Lightoctaves}', '{Scale}']),
            ('uM1', ['{Base}', '{Top}', '{Coverage}', '{Density}']),
            ('uM2', ['{Absorb}', '{Lightstep}', '{Silver}', '{Ambient}']),
            ('uM3', ['{Maxdist}', '{Fogdensity}', '{Dither}', '{Evolve}']),
            ('uM4', ['{Windx}', '{Windz}', '{Camheight}', '{Flyspeed}']),
            ('uM5', [_R + '({Pitch})', _R + '({Yaw})', _R + '({Yawspeed})', _R + '({Fov})']),
            ('uM6', ['{Skycolorr}', '{Skycolorg}', '{Skycolorb}', '{Sunintensity}']),
            ('uM7', ['{Suncolorr}', '{Suncolorg}', '{Suncolorb}', '{Beatlight}']),
            ('uM8', [_R + '({Sunyaw})', _R + '({Sunpitch})', '{Audiolight}', '0']),
            ('uM9', ['{Bgcolorr}', '{Bgcolorg}', '{Bgcolorb}', '0'])]

GLSL = """
float cn_hash(ivec3 c) {
    return float(lb32(uint(c.x) * 73856093u ^ uint(c.y) * 19349663u ^ uint(c.z) * 83492791u ^ SEED * 2654435761u)) * (1.0 / 4294967296.0);
}
float cn_noise(vec3 p) {
    vec3 fl = floor(p), f = p - fl;
    ivec3 i = ivec3(fl);
    vec3 u = f * f * (3.0 - 2.0 * f);
    float a = mix(cn_hash(i), cn_hash(i + ivec3(1, 0, 0)), u.x);
    float b = mix(cn_hash(i + ivec3(0, 1, 0)), cn_hash(i + ivec3(1, 1, 0)), u.x);
    float c = mix(cn_hash(i + ivec3(0, 0, 1)), cn_hash(i + ivec3(1, 0, 1)), u.x);
    float d = mix(cn_hash(i + ivec3(0, 1, 1)), cn_hash(i + ivec3(1, 1, 1)), u.x);
    return mix(mix(a, b, u.y), mix(c, d, u.y), u.z);
}
float cl_dens(vec3 p, int n) {
    float hf = (p.y - uM1.x) / max(uM1.y - uM1.x, 1e-3);
    if (hf <= 0.0 || hf >= 1.0) return 0.0;
    vec3 q = p * uM0.w + vec3(uM4.x, uM3.w, uM4.y) * T;
    float s = 0.0, a = 0.5, w = 0.0;
    for (int o = 0; o < 6; o++) {
        if (o >= n) break;
        s += a * cn_noise(q);
        w += a;
        q = q * 2.03 + vec3(17.1, 31.7, 7.3);
        a *= 0.5;
    }
    float prof = clamp(hf * 5.0, 0.0, 1.0) * clamp((1.0 - hf) * 2.0, 0.0, 1.0);
    return max(s / w * prof - (1.0 - uM1.z), 0.0) * uM1.w;
}
vec3 cl_sky(vec3 rd, vec3 L) {
    float y = max(rd.y, 0.0);
    vec3 c = mix(uM9.rgb, uM6.rgb, 1.0 - exp(-3.0 * y));
    float s = max(dot(rd, L), 0.0);
    return c + uM7.rgb * (uM6.w * (0.12 * pow(s, 16.0) + 2.0 * pow(s, 3000.0)));
}
vec4 render2d(vec2 P) {
    vec2 uv = (P - 0.5 * RES) / RES.y;
    float yaw = uM5.y + uM5.z * T, pitch = uM5.x;
    vec3 ww = vec3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw));
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = cross(uu, ww);
    vec3 rd = normalize(uv.x * uu + uv.y * vv + (0.5 / tan(0.5 * uM5.w)) * ww);
    vec3 ro = vec3(sin(uM5.y), 0.0, cos(uM5.y)) * (uM4.w * T) + vec3(0.0, uM4.z, 0.0);
    vec3 L = vec3(cos(uM8.y) * sin(uM8.x), sin(uM8.y), cos(uM8.y) * cos(uM8.x));
    vec3 sky = cl_sky(rd, L);
    float t0 = 0.0, t1 = -1.0;
    if (abs(rd.y) > 1e-4) {
        float ta = (uM1.x - ro.y) / rd.y, tb = (uM1.y - ro.y) / rd.y;
        t0 = max(min(ta, tb), 0.0);
        t1 = max(ta, tb);
    } else if (ro.y > uM1.x && ro.y < uM1.y) {
        t1 = uM3.x;
    }
    t1 = min(t1, uM3.x);
    float tr = 1.0, dsum = 0.0;
    vec3 col = vec3(0.0);
    if (t1 > t0) {
        int N = int(uM0.x + 0.5), no = int(uM0.y + 0.5), nl = int(uM0.z + 0.5);
        float dt = (t1 - t0) / float(N);
        float t = t0 + dt * uM3.z * h2(ivec2(P), SEED);
        float mu = dot(rd, L), g = uM2.z;
        float hg = (1.0 - g * g) / pow(max(1.0 + g * g - 2.0 * g * mu, 1e-4), 1.5);
        float ph = 0.4 + 0.08 * hg;
        float sun = uM6.w * (1.0 + uM7.w * ENV + uM8.z * LEVEL);
        for (int i = 0; i < 64; i++) {
            if (i >= N) break;
            vec3 p = ro + rd * t;
            float d = cl_dens(p, no);
            if (d > 0.0) {
                float dl = cl_dens(p + L * uM2.y, nl);
                float lum = exp(-dl * uM2.x * uM2.y);
                float hf = (p.y - uM1.x) / max(uM1.y - uM1.x, 1e-3);
                vec3 S = uM7.rgb * (lum * ph * sun) + uM6.rgb * (uM2.w * (0.4 + 0.6 * hf));
                S = mix(uM9.rgb, S, exp(-uM3.y * t));
                float a = 1.0 - exp(-d * dt);
                col += tr * a * S;
                tr *= 1.0 - a;
                dsum += d * dt;
                if (tr < 0.01) break;
            }
            t += dt;
        }
    }
    if (int(uMat.y + 0.5) == 1) return vec4(t0, t1 > t0 ? 1.0 : 0.0, tr, dsum);
    return vec4(col + tr * sky, 1.0);
}
"""
