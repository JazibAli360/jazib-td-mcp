# gen_sdf_blackhole - GEN_sdf module 'blackhole' (FX7a SX-19; lane C2, 27 Oct): a black hole with a glowing accretion
# disk whose light is bent around the dark core (the far side of the disk shows above and below the shadow), a photon
# ring glow and Doppler-brightened approaching side, over a star field that is lensed too. Clean-room: the research row
# names XorDev "Accretion", Shadertoy tsBXW3 and a Godot shader (all UNVERIFIED licences, none opened or copied).
# Technique, written fresh from the physics: each pixel's photon is integrated in Schwarzschild units (horizon radius
# Horizon) with the classic bending term a = -1.5 Bend Horizon h^2 p / r^5 (h = |p x v|, conserved), semi-implicit
# Euler with steps Stepsize x r (Steps, cap 256). A step that crosses the y = 0 plane between Diskin and Diskout
# composites the disk there (front to back): palette by radius (fire by default), 1 / r^2 brightness, Keplerian swirl
# (Swirl x r^-1.5), bands with a turbulent wobble (Bands, Turb), Doppler boost (1 + Doppler beta cos)^3 with beta =
# sqrt(0.5 Horizon / r), soft inner / outer edges. Captured photons (r < Horizon) stay black; escaped ones read hashed
# stars in their bent final direction. Photon-ring glow accumulates near r = 1.5 Horizon. Tone map 1 - exp(-c).
# Orbit camera (Camdist, Campitch, Camyaw, Orbitspeed, Fov). KIND 'flat'; default Quality 0.4, Steps 64 (b4 hang, LEARNINGS T-194). Mirror:
# gen_sdf_logic.blackhole_rm. ASCII only.
MODULE = 'blackhole'
KIND = 'flat'
BLURB = 'Black hole: bent photon paths, lensed accretion disk (Doppler, swirl, bands), photon ring, lensed stars.'

PAGES = [('Blackhole', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Steps', 'Int', 64, {'min': 8, 'max': 256, 'label': 'Integration steps (cap 256)'}),
    ('Stepsize', 'Float', 0.08, {'min': 0.01, 'max': 0.5, 'label': 'Step size (x radius)'}),
    ('Bend', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Bending (1 = Schwarzschild)'}),
    ('Horizon', 'Float', 1.0, {'min': 0.1, 'max': 4, 'label': 'Horizon radius'}),
    ('Diskin', 'Float', 3.0, {'min': 1, 'max': 20, 'label': 'Disk inner radius'}),
    ('Diskout', 'Float', 9.0, {'min': 1.5, 'max': 40, 'label': 'Disk outer radius'}),
    ('Diskopacity', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Disk opacity'}),
    ('Diskgain', 'Float', 4.0, {'min': 0, 'max': 20, 'label': 'Disk brightness'}),
    ('Swirl', 'Float', 1.0, {'min': -8, 'max': 8, 'label': 'Swirl speed (Keplerian)'}),
    ('Bands', 'Float', 6.0, {'min': 0, 'max': 40, 'label': 'Bands per unit radius'}),
    ('Turb', 'Float', 1.5, {'min': 0, 'max': 6, 'label': 'Band turbulence'}),
    ('Doppler', 'Float', 0.8, {'min': 0, 'max': 2, 'label': 'Doppler brightening'}),
    ('Ringglow', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Photon ring glow'}),
    ('Exposure', 'Float', 1.0, {'min': 0.05, 'max': 8, 'label': 'Exposure'}),
    ('Camdist', 'Float', 16.0, {'min': 3, 'max': 80, 'label': 'Camera distance'}),
    ('Campitch', 'Float', 8.0, {'min': -89, 'max': 89, 'label': 'Camera pitch deg (above the disk)'}),
    ('Camyaw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Camera yaw deg'}),
    ('Orbitspeed', 'Float', 3.0, {'min': -60, 'max': 60, 'label': 'Orbit deg/s'}),
    ('Fov', 'Float', 50.0, {'min': 10, 'max': 150, 'label': 'FOV deg (vertical)'}),
    ('Stars', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Star density'}),
    ('Starscale', 'Float', 180.0, {'min': 20, 'max': 1000, 'label': 'Star grid (higher = smaller)'}),
    ('Beatglow', 'Float', 0.0, {'min': -1, 'max': 4, 'label': 'Beat pulse -> disk brightness'}),
    ('Audioglow', 'Float', 0.0, {'min': -1, 'max': 4, 'label': 'Audio level -> disk brightness'}),
])]
DEFAULTS = {'Quality': 0.4, 'Palette': 0, 'Spread': 1.0, 'Offset': 0.0, 'Colorar': 1.0, 'Colorag': 0.62, 'Colorab': 0.25,
            'Colorbr': 0.75, 'Colorbg': 0.16, 'Colorbb': 0.03}
PANEL_PAGES = ['Blackhole', 'Render', 'Colour', 'Drive']
PRESETS = [
    (1, 'interstellar', {}),
    (2, 'edge on', {'Campitch': 2.0, 'Camdist': 14.0, 'Orbitspeed': 0.0, 'Doppler': 1.4, 'Fov': 45.0}),
    (3, 'top down', {'Campitch': 70.0, 'Camdist': 20.0, 'Swirl': 2.0, 'Turb': 3.0, 'Palette': 6, 'Spread': 0.7}),
    (4, 'blue quasar', {'Palette': 4, 'Diskgain': 5.0, 'Ringglow': 1.2, 'Diskin': 2.6, 'Diskout': 12.0,
                        'Campitch': 15.0, 'Beatevery': 1.0, 'Beatgain': 1.0, 'Beatdecay': 0.3, 'Beatglow': 1.5}),
    (5, 'close orbit', {'Camdist': 8.0, 'Campitch': 12.0, 'Orbitspeed': 12.0, 'Fov': 80.0, 'Steps': 96,
                        'Palette': 5, 'Spread': 0.8}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
_R = 'math.radians'
UNIFORMS = [('uM0', ['{Steps}', '{Stepsize}', '{Bend}', '{Horizon}']),
            ('uM1', ['{Diskin}', '{Diskout}', '{Diskopacity}', '{Diskgain}']),
            ('uM2', ['{Swirl}', '{Bands}', '{Turb}', '{Doppler}']),
            ('uM3', ['{Camdist}', _R + '({Campitch})', _R + '({Camyaw})', _R + '({Orbitspeed})']),
            ('uM4', [_R + '({Fov})', '{Exposure}', '{Stars}', '{Starscale}']),
            ('uM5', ['{Ringglow}', '{Beatglow}', '{Audioglow}', '0'])]

GLSL = """
float bh_band(float rq, float aa) {
    return 0.55 + 0.45 * sin(rq * uM2.y + uM2.z * sin(3.0 * aa + 1.7 * rq)) * sin(5.0 * aa + 2.0 * rq);
}
vec3 bh_disk(vec3 q, vec3 vdir, float gain, out float op) {
    float rq = length(q.xz);
    float k = (rq - uM1.x) / max(uM1.y - uM1.x, 1e-3);
    float fin = clamp(k * 8.0, 0.0, 1.0), fout = clamp((1.0 - k) * 3.0, 0.0, 1.0);
    // Keplerian shear without winding up: two copies, each sheared over a 4-unit cycle, cross-faded (weight 0 at
    // each copy's reset), so the bands keep their width at any time
    float kk = pow(uM1.x / rq, 1.5), a0 = atan(q.z, q.x), ph = uM2.x * T * 0.25;
    float w1 = fract(ph), w2 = fract(ph + 0.5), x1 = 1.0 - abs(2.0 * w1 - 1.0);
    float band = bh_band(rq, a0 + (w1 - 0.5) * 4.0 * kk) * x1 + bh_band(rq, a0 + (w2 - 0.5) * 4.0 * kk) * (1.0 - x1);
    op = uM1.z * fin * fout * clamp(band + 0.2, 0.0, 1.0);
    vec3 vd = normalize(vec3(-q.z, 0.0, q.x));
    float beta = sqrt(0.5 * uM0.w / rq);
    float boost = 1.0 + uM2.w * beta * dot(vd, -vdir);
    boost = max(boost, 0.05);
    return palk(k) * (gain * band * (uM1.x * uM1.x) / (rq * rq) * boost * boost * boost);
}
vec4 render2d(vec2 P) {
    vec2 uv = (P - 0.5 * RES) / RES.y;
    float yaw = uM3.z + uM3.w * T, pitch = uM3.y;
    vec3 ro = uM3.x * vec3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw));
    vec3 ww = normalize(-ro);
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = cross(uu, ww);
    vec3 v = normalize(uv.x * uu + uv.y * vv + (0.5 / tan(0.5 * uM4.x)) * ww);
    vec3 p = ro;
    vec3 hv = cross(p, v);
    float hh = dot(hv, hv);
    float rs = uM0.w, far = uM3.x * 1.5 + uM1.y;
    float gain = uM1.w * (1.0 + uM5.y * ENV + uM5.z * LEVEL);
    vec3 col = vec3(0.0);
    float al = 0.0, glow = 0.0, rmin = 1e9;
    bool cap = false;
    int N = int(uM0.x + 0.5);
    for (int i = 0; i < 256; i++) {
        if (i >= N) break;
        float r2 = dot(p, p), r = sqrt(r2);
        rmin = min(rmin, r);
        float dt = uM0.y * max(r, 0.2);
        v += (-1.5 * uM0.z * rs * hh / (r2 * r2 * r)) * p * dt;
        vec3 pn = p + v * dt;
        if (p.y * pn.y < 0.0) {
            vec3 q = mix(p, pn, p.y / (p.y - pn.y));
            float rq = length(q.xz);
            if (rq > uM1.x && rq < uM1.y) {
                float op;
                vec3 e = bh_disk(q, normalize(v), gain, op);
                col += (1.0 - al) * op * e;
                al += (1.0 - al) * op;
            }
        }
        glow += exp(-abs(r - 1.5 * rs) * 6.0 / rs) * dt;
        p = pn;
        if (length(p) < rs) { cap = true; break; }
        if (r > far || al > 0.99) break;
    }
    if (!cap) {
        vec3 d = normalize(v);
        vec3 bg = vec3(0.0);
        if (uM4.z > 0.0) {
            vec3 s = d * uM4.w;
            ivec3 c = ivec3(floor(s));
            float h = h2(ivec2(c.x, c.y ^ (c.z * 7919)), SEED);
            if (h < uM4.z) {
                float h1 = h2(ivec2(c.y, c.z ^ (c.x * 7919)), SEED + 1u), h3 = h2(ivec2(c.z, c.x ^ (c.y * 7919)), SEED + 2u);
                vec3 sp = vec3(c) + 0.5 + (vec3(h1, h3, h / max(uM4.z, 1e-6)) - 0.5) * 0.5;
                bg = vec3(1.0) * max(0.0, 1.0 - length(s - sp) * 2.5) * (0.4 + 0.6 * h1);
            }
        }
        col += (1.0 - al) * bg;
    }
    col += palk(0.15) * (uM5.x * glow * 0.15 * (1.0 - al));
    if (int(uMat.y + 0.5) == 1) return vec4(rmin, cap ? 1.0 : 0.0, al, glow);
    col = 1.0 - exp(-uM4.y * col);
    return vec4(col, 1.0);
}
"""
