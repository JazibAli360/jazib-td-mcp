# gen_sdf_planet - GEN_sdf module 'planet' (FX7b TC-34; lane C, 27 Oct): an analytic ringed gas giant. No ray
# marching: each pixel's ray is intersected in closed form with a flattened sphere (Flatten), the ring plane (Ringin
# .. Ringout) and up to 3 moons; a second closed-form ray toward the sun gives the ring shadow on the planet and the
# planet shadow on the rings. Bands = the palette at sin(latitude x Bands + turbulence), torn by two moving sine
# fields (Turb, Turbspeed) and sheared by latitude (differential rotation, Shear); one oval storm (Stormlat,
# Stormlon, Stormsize) with swirl rings. Lambert with a soft terminator + atmosphere rim (Colour A), stars behind.
# Clean-room from Yaado Lab's description ("A Ringed Planet in One Shader", 5 Oct 2026; the project file was not
# used). Resolution-independent and cheap, so default Quality 1.0 (crisp limb and ring edges). KIND 'flat'.
# Mirror: gen_sdf_logic.planet_rm. ASCII only.
MODULE = 'planet'
KIND = 'flat'
BLURB = 'Analytic ringed planet: flattened sphere + ring plane + moons, closed-form shadows, banded storms.'

PAGES = [('Planet', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Flatten', 'Float', 0.08, {'min': 0, 'max': 0.5, 'label': 'Flattening (poles)'}),
    ('Axistilt', 'Float', 22.0, {'min': -90, 'max': 90, 'label': 'Axis tilt deg'}),
    ('Spin', 'Float', 6.0, {'min': -60, 'max': 60, 'label': 'Spin deg/s (bands drift)'}),
    ('Bands', 'Float', 9.0, {'min': 1, 'max': 40, 'label': 'Bands'}),
    ('Turb', 'Float', 0.6, {'min': 0, 'max': 3, 'label': 'Band turbulence'}),
    ('Turbspeed', 'Float', 0.15, {'min': -2, 'max': 2, 'label': 'Turbulence speed'}),
    ('Shear', 'Float', 0.3, {'min': -2, 'max': 2, 'label': 'Band shear (differential rotation)'}),
    ('Stormsize', 'Float', 0.18, {'min': 0, 'max': 0.6, 'label': 'Storm size (0 off)'}),
    ('Stormlat', 'Float', -20.0, {'min': -80, 'max': 80, 'label': 'Storm latitude deg'}),
    ('Stormlon', 'Float', 30.0, {'min': -180, 'max': 180, 'label': 'Storm longitude deg'}),
    ('Rings', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Ring opacity (0 off)'}),
    ('Ringin', 'Float', 1.35, {'min': 1.0, 'max': 4, 'label': 'Ring inner radius'}),
    ('Ringout', 'Float', 2.3, {'min': 1.05, 'max': 6, 'label': 'Ring outer radius'}),
    ('Ringbands', 'Float', 18.0, {'min': 0, 'max': 80, 'label': 'Ring band detail'}),
    ('Moons', 'Int', 2, {'min': 0, 'max': 3, 'label': 'Moons (cap 3)'}),
    ('Moonsize', 'Float', 0.09, {'min': 0.01, 'max': 0.4, 'label': 'Moon radius'}),
    ('Moonorbit', 'Float', 2.8, {'min': 1.2, 'max': 8, 'label': 'Moon orbit radius'}),
    ('Moonspeed', 'Float', 12.0, {'min': -90, 'max': 90, 'label': 'Moon orbit deg/s'}),
    ('Sunyaw', 'Float', -50.0, {'min': -180, 'max': 180, 'label': 'Sun yaw deg'}),
    ('Sunpitch', 'Float', 15.0, {'min': -89, 'max': 89, 'label': 'Sun pitch deg'}),
    ('Ambient', 'Float', 0.04, {'min': 0, 'max': 1, 'label': 'Ambient'}),
    ('Rim', 'Float', 0.6, {'min': 0, 'max': 3, 'label': 'Atmosphere rim (Colour A)'}),
    ('Stars', 'Float', 0.06, {'min': 0, 'max': 1, 'label': 'Star density'}),
    ('Camdist', 'Float', 6.0, {'min': 1.5, 'max': 30, 'label': 'Camera distance'}),
    ('Camyaw', 'Float', 20.0, {'min': -180, 'max': 180, 'label': 'Camera yaw deg'}),
    ('Campitch', 'Float', 25.0, {'min': -89, 'max': 89, 'label': 'Camera pitch deg'}),
    ('Orbitspeed', 'Float', 2.0, {'min': -45, 'max': 45, 'label': 'Camera orbit deg/s'}),
    ('Fov', 'Float', 45.0, {'min': 5, 'max': 120, 'label': 'FOV deg (vertical)'}),
    ('Beatzoom', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Beat pulse -> dolly in'}),
])]
DEFAULTS = {'Quality': 1.0, 'Palette': 5, 'Spread': 1.0, 'Colorar': 0.45, 'Colorag': 0.7, 'Colorab': 1.0}
PANEL_PAGES = ['Planet', 'Render', 'Colour', 'Drive']
PRESETS = [
    (1, 'ringed giant', {}),
    (2, 'close pass', {'Camdist': 2.6, 'Campitch': 14.0, 'Camyaw': 35.0, 'Fov': 60.0, 'Orbitspeed': 1.0, 'Stormsize': 0.25}),
    (3, 'edge-on rings', {'Axistilt': 0.0, 'Campitch': 1.5, 'Camdist': 7.0, 'Moons': 3, 'Sunpitch': 25.0}),
    (4, 'ice giant', {'Palette': 4, 'Bands': 5.0, 'Turb': 0.25, 'Rings': 0.4, 'Ringin': 1.6, 'Ringout': 1.9,
                      'Stormsize': 0.0, 'Rim': 1.2, 'Colorar': 0.6, 'Colorag': 0.9, 'Colorab': 1.0}),
    (5, 'beat orbit', {'Beatevery': 1.0, 'Beatgain': 1.0, 'Beatdecay': 0.3, 'Beatzoom': 0.15, 'Orbitspeed': 8.0,
                       'Palette': 7, 'Turbspeed': 0.4}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
_R = 'math.radians'
UNIFORMS = [('uM0', ['{Flatten}', _R + '({Axistilt})', _R + '({Spin})', '{Bands}']),
            ('uM1', ['{Turb}', '{Turbspeed}', '{Shear}', '{Stormsize}']),
            ('uM2', [_R + '({Stormlat})', _R + '({Stormlon})', '{Rings}', '{Ringin}']),
            ('uM3', ['{Ringout}', '{Ringbands}', '{Moons}', '{Moonsize}']),
            ('uM4', ['{Moonorbit}', _R + '({Moonspeed})', _R + '({Sunyaw})', _R + '({Sunpitch})']),
            ('uM5', ['{Ambient}', '{Rim}', '{Stars}', '{Camdist}']),
            ('uM6', [_R + '({Camyaw})', _R + '({Campitch})', _R + '({Orbitspeed})', _R + '({Fov})']),
            ('uM7', ['{Beatzoom}', '0', '0', '0'])]

GLSL = """
vec3 ptilt(vec3 v) { float c = cos(uM0.y), s = sin(uM0.y); return vec3(c * v.x + s * v.y, -s * v.x + c * v.y, v.z); }
float psph(vec3 ro, vec3 rd, vec3 c, float r) {          // nearest t > 0 of a sphere, -1 if none
    vec3 o = ro - c;
    float b = dot(o, rd), q = dot(o, o) - r * r, h = b * b - q;
    if (h < 0.0) return -1.0;
    h = sqrt(h);
    float t = -b - h;
    if (t < 0.0) t = -b + h;
    return t;
}
float pring(float r) {                                    // ring density at radius r
    if (uM2.z <= 0.0 || r < uM2.w || r > uM3.x) return 0.0;
    float u = (r - uM2.w) / max(uM3.x - uM2.w, 1e-4);
    float d = 0.55 + 0.25 * sin(u * uM3.y * 3.1) + 0.2 * sin(u * uM3.y * 7.7 + 1.3);
    d *= smoothstep(0.0, 0.04, u) * smoothstep(1.0, 0.92, u);
    d *= 1.0 - 0.85 * smoothstep(0.012, 0.0, abs(u - 0.62));                    // a gap
    return clamp(d, 0.0, 1.0) * uM2.z;
}
vec4 render2d(vec2 P) {
    vec2 uv = (P - 0.5 * RES) / RES.y;
    float yaw = uM6.x + uM6.z * T, pitch = uM6.y;
    float dist = uM5.w * (1.0 - uM7.x * ENV);
    vec3 ro = dist * vec3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw));
    vec3 ww = normalize(-ro);
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = cross(uu, ww);
    vec3 rd = normalize(uv.x * uu + uv.y * vv + (0.5 / tan(0.5 * uM6.w)) * ww);
    vec3 L = vec3(cos(uM4.w) * sin(uM4.z), sin(uM4.w), cos(uM4.w) * cos(uM4.z));
    vec3 pro = ptilt(ro), prd = ptilt(rd), pL = ptilt(L);  // planet frame: axis = y
    float k = 1.0 / (1.0 - uM0.x);                         // flattened sphere: y scaled by k -> unit sphere
    vec3 so = vec3(pro.x, pro.y * k, pro.z), sd = vec3(prd.x, prd.y * k, prd.z);
    float sl = length(sd);
    float tp = psph(so, sd / sl, vec3(0.0), 1.0);
    tp = tp > 0.0 ? tp / sl : -1.0;
    float tr = abs(prd.y) > 1e-6 ? -pro.y / prd.y : -1.0;
    vec3 rp = pro + prd * tr;
    float dr = tr > 0.0 ? pring(length(rp.xz)) : 0.0;
    vec3 col = vec3(0.0);
    float a = 0.0, tbest = 1e9;
    if (tp > 0.0) {
        vec3 p = pro + prd * tp;
        vec3 n = normalize(vec3(p.x, p.y * k * k, p.z));
        float lat = asin(clamp(p.y * k, -1.0, 1.0));
        float lon = atan(p.z, p.x) + uM0.z * T + uM1.z * sin(lat * uM0.w * 0.5) * T;
        float tt = uM1.y * T;
        float b = lat * uM0.w + uM1.x * (0.6 * sin(3.0 * lon + 5.0 * lat + tt) * sin(7.0 * lat - 2.0 * lon - 0.7 * tt)
                                         + 0.4 * sin(11.0 * lat + 4.0 * lon + 1.3 * tt));
        vec3 base = palk(0.5 + 0.5 * sin(b));
        if (uM1.w > 0.0) {
            float dl = lon - uM2.y - uM0.z * T;
            dl = atan(sin(dl), cos(dl));
            float d = length(vec2(dl * cos(lat) * 0.6, lat - uM2.x)) / uM1.w;
            float st = smoothstep(1.0, 0.5, d);
            base = mix(base, palk(0.95) * (0.85 + 0.15 * sin(d * 14.0 - T * 2.0)), st * 0.85);
        }
        float dif = smoothstep(-0.08, 0.35, dot(n, pL));
        float trs = abs(pL.y) > 1e-6 ? -p.y / pL.y : -1.0;               // ring shadow on the planet
        if (trs > 0.0) dif *= 1.0 - 0.8 * pring(length((p + pL * trs).xz)) / max(uM2.z, 1e-4);
        float fre = pow(clamp(1.0 + dot(n, prd), 0.0, 1.0), 3.0);
        col = base * (dif + uM5.x) + uCa.rgb * fre * uM5.y * (0.3 + 0.7 * dif);
        a = 1.0;
        tbest = tp;
    }
    if (dr > 0.0 && tr < tbest) {                          // rings in front of the planet (or no planet)
        float sh = psph(vec3(rp.x, rp.y * k, rp.z), normalize(vec3(pL.x, pL.y * k, pL.z)), vec3(0.0), 1.0) > 0.0 ? 0.08 : 1.0;
        vec3 rc = palk(0.2 + 0.25 * (length(rp.xz) - uM2.w)) * (0.25 + 0.75 * abs(pL.y)) * sh + uM5.x;
        col = mix(col, rc, dr);
        a = a + dr * (1.0 - a);
        tbest = min(tbest, tr);
    }
    int nm = int(uM3.z + 0.5);
    for (int i = 0; i < 3; i++) {
        if (i >= nm) break;
        float ang = uM4.y * T / (1.0 + float(i)) + float(i) * 2.1;
        float orb = uM4.x * (1.0 + 0.45 * float(i));
        vec3 mc = vec3(orb * cos(ang), orb * 0.06 * sin(ang * 1.7 + float(i)), orb * sin(ang));
        float rr = uM3.w * (1.0 - 0.25 * float(i));
        float tm = psph(pro, prd, mc, rr);
        if (tm > 0.0 && tm < tbest) {
            vec3 n = normalize(pro + prd * tm - mc);
            col = vec3(0.75, 0.72, 0.68) * (max(dot(n, pL), 0.0) + uM5.x);
            a = 1.0;
            tbest = tm;
        }
    }
    if (a < 1.0 && uM5.z > 0.0) {                          // stars behind
        vec3 s = rd * 260.0;
        ivec3 c = ivec3(floor(s));
        float h = h2(ivec2(c.x, c.y ^ (c.z * 7919)), SEED);
        if (h < uM5.z) {
            float h1 = h2(ivec2(c.y, c.z ^ (c.x * 7919)), SEED + 1u), h3 = h2(ivec2(c.z, c.x ^ (c.y * 7919)), SEED + 2u);
            vec3 sp = vec3(c) + 0.5 + (vec3(h1, h3, h / max(uM5.z, 1e-6)) - 0.5) * 0.5;
            float sv = max(0.0, 1.0 - length(s - sp) * 2.5) * (1.0 - a);       // premultiplied, behind
            col += vec3(sv);
            a += sv;
        }
    }
    if (int(uMat.y + 0.5) == 1) return vec4(tp, tr, dr, a);
    return vec4(col, a);
}
"""
