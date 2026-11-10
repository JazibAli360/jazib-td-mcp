# gen_sdf_sky - GEN_sdf module 'sky' (FX7a SX-18; lane C, 27 Oct): a physically shaped sky (blue noon, orange
# horizon, purple twilight) from single scattering, driven by one time-of-day knob. Port of wwwtyro/glsl-atmosphere
# (Unlicense, public domain): ray-sphere intersect, Steps view samples x Lightsteps light samples, Rayleigh + Mie
# densities from scale heights, Rayleigh + Henyey-Greenstein-like Mie phase; units km (not m: keeps float32 sane).
# Additions here: a fixed camera (Tilt / Yaw / Fov, like aurora), the sun from Daytime (0..1 = a day: sunrise 0.25,
# noon 0.5, sunset 0.75) or Sunelev, Sunspeed (auto day cycle), a sun disk, ground below the horizon (Bgcolor), and
# 1 - exp(-Exposure x c) tone mapping. KIND 'flat'; loops capped (32 view, 16 light; T-124). Pairs with aurora
# (rack order: sky first, aurora with Blend add). Mirror: gen_sdf_logic.sky_rm. ASCII only.
MODULE = 'sky'
KIND = 'flat'
BLURB = 'Single-scatter sky (Rayleigh + Mie): time-of-day knob, sun disk, ground; wwwtyro glsl-atmosphere port.'

PAGES = [('Sky', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Sunmode', 'Menu', 'daytime', {'names': ['daytime', 'elevation'], 'labels': ['Daytime knob (0..1 = a day)',
                                                                               'Sun elevation deg']}),
    ('Daytime', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Daytime (0.25 sunrise, 0.5 noon, 0.75 sunset)'}),
    ('Sunspeed', 'Float', 0.0, {'min': -0.2, 'max': 0.2, 'label': 'Day cycle per s (auto)'}),
    ('Sunelev', 'Float', 10.0, {'min': -20, 'max': 90, 'label': 'Sun elevation deg'}),
    ('Sunazim', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Sun azimuth deg'}),
    ('Sunintensity', 'Float', 22.0, {'min': 0, 'max': 100, 'label': 'Sun intensity'}),
    ('Sunsize', 'Float', 0.6, {'min': 0, 'max': 5, 'label': 'Sun disk deg (0 off)'}),
    ('Exposure', 'Float', 1.0, {'min': 0.05, 'max': 8, 'label': 'Exposure'}),
    ('Rayleigh', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Rayleigh (blue) x'}),
    ('Mie', 'Float', 1.0, {'min': 0, 'max': 20, 'label': 'Mie (haze) x'}),
    ('Mieg', 'Float', 0.758, {'min': 0, 'max': 0.99, 'label': 'Mie forward glow g'}),
    ('Altitude', 'Float', 1.0, {'min': 0.001, 'max': 50, 'label': 'Camera altitude km'}),
    ('Steps', 'Int', 16, {'min': 4, 'max': 32, 'label': 'View steps (cap 32)'}),
    ('Lightsteps', 'Int', 8, {'min': 2, 'max': 16, 'label': 'Light steps (cap 16)'}),
    ('Tilt', 'Float', 12.0, {'min': -30, 'max': 89, 'label': 'Camera tilt deg (up)'}),
    ('Yaw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Camera yaw deg (0 = toward the sun azimuth 0)'}),
    ('Fov', 'Float', 80.0, {'min': 20, 'max': 150, 'label': 'FOV deg (vertical)'}),
])]
DEFAULTS = {'Quality': 0.5, 'Bgcolorr': 0.02, 'Bgcolorg': 0.018, 'Bgcolorb': 0.02}
PANEL_PAGES = ['Sky', 'Render', 'Colour', 'Drive']
PRESETS = [
    (1, 'golden hour', {'Daytime': 0.3}),
    (2, 'noon', {'Daytime': 0.5, 'Tilt': 30.0}),
    (3, 'sunset haze', {'Daytime': 0.74, 'Mie': 4.0, 'Mieg': 0.85}),
    (4, 'twilight', {'Daytime': 0.755, 'Exposure': 3.0}),
    (5, 'day cycle', {'Daytime': 0.27, 'Sunspeed': 0.02}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
_R = 'math.radians'
UNIFORMS = [('uM0', ['{Sunmode#}', '{Daytime}', '{Sunspeed}', _R + '({Sunelev})']),
            ('uM1', [_R + '({Sunazim})', '{Sunintensity}', _R + '({Sunsize})', '{Exposure}']),
            ('uM2', ['{Rayleigh}', '{Mie}', '{Mieg}', '{Altitude}']),
            ('uM3', ['{Steps}', '{Lightsteps}', _R + '({Tilt})', _R + '({Yaw})']),
            ('uM4', [_R + '({Fov})', '0', '0', '0'])]

GLSL = """
const float RP = 6371.0;
const float RA = 6471.0;
vec2 rsi(vec3 r0, vec3 rd, float sr) {
    float a = dot(rd, rd), b = 2.0 * dot(rd, r0), c = dot(r0, r0) - sr * sr;
    float d = b * b - 4.0 * a * c;
    if (d < 0.0) return vec2(1e5, -1e5);
    float q = sqrt(d);
    return vec2((-b - q) / (2.0 * a), (-b + q) / (2.0 * a));
}
vec3 sky_sun() {
    float el = uM0.w;
    if (uM0.x < 0.5) el = sin(TAU * (uM0.y + uM0.z * T - 0.25)) * 1.5707963;
    float az = uM1.x;
    return vec3(cos(el) * sin(az), sin(el), cos(el) * cos(az));
}
vec3 sky_dir(vec2 P) {
    vec2 uv = (P - 0.5 * RES) / RES.y;
    float yaw = uM3.w, pitch = uM3.z;
    vec3 ww = vec3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw));
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = cross(uu, ww);
    return normalize(uv.x * uu + uv.y * vv + (0.5 / tan(0.5 * uM4.x)) * ww);
}
vec3 atmo(vec3 r, vec3 r0, vec3 ps) {
    vec3 kR = vec3(5.5e-3, 13.0e-3, 22.4e-3) * uM2.x;
    float kM = 21e-3 * uM2.y;
    const float shR = 8.0, shM = 1.2;
    float g = uM2.z;
    vec2 p = rsi(r0, r, RA);
    if (p.x > p.y) return vec3(0.0);
    p.x = max(p.x, 0.0);                                  // camera inside the atmosphere: start at the eye
    float pg = rsi(r0, r, RP).x;
    if (pg > 0.0) p.y = min(p.y, pg);                     // stop at the ground (roots behind the eye ignored)
    int NI = int(uM3.x + 0.5), NJ = int(uM3.y + 0.5);
    float iss = (p.y - p.x) / float(NI);
    float it = p.x;
    vec3 tR = vec3(0.0), tM = vec3(0.0);
    float odR = 0.0, odM = 0.0;
    float mu = dot(r, ps), mumu = mu * mu, gg = g * g;
    float pR = 3.0 / (16.0 * PI) * (1.0 + mumu);
    float pM = 3.0 / (8.0 * PI) * ((1.0 - gg) * (mumu + 1.0)) / (pow(1.0 + gg - 2.0 * mu * g, 1.5) * (2.0 + gg));
    for (int i = 0; i < 32; i++) {
        if (i >= NI) break;
        vec3 ip = r0 + r * (it + iss * 0.5);
        float ih = length(ip) - RP;
        float sR = exp(-ih / shR) * iss, sM = exp(-ih / shM) * iss;
        odR += sR;
        odM += sM;
        float jss = rsi(ip, ps, RA).y / float(NJ);
        float jt = 0.0, jR = 0.0, jM = 0.0;
        for (int j = 0; j < 16; j++) {
            if (j >= NJ) break;
            vec3 jp = ip + ps * (jt + jss * 0.5);
            float jh = length(jp) - RP;
            jR += exp(-jh / shR) * jss;
            jM += exp(-jh / shM) * jss;
            jt += jss;
        }
        vec3 at = exp(-(kM * (odM + jM) + kR * (odR + jR)));
        tR += sR * at;
        tM += sM * at;
        it += iss;
    }
    return uM1.y * (pR * kR * tR + pM * kM * tM);
}
vec4 render2d(vec2 P) {
    vec3 rd = sky_dir(P);
    vec3 ps = sky_sun();
    vec3 r0 = vec3(0.0, RP + uM2.w, 0.0);
    vec3 c = atmo(rd, r0, ps);
    float ground = rsi(r0, rd, RP).x;
    bool hitg = ground > 0.0 && ground < 1e4;
    if (!hitg && uM1.z > 0.0 && dot(rd, ps) > cos(uM1.z)) {          // sun disk (attenuated like the sky)
        float od = rsi(r0, ps, RA).y;
        c += uM1.y * 0.25 * exp(-(vec3(5.5e-3, 13.0e-3, 22.4e-3) * uM2.x * exp(-uM2.w / 8.0) +
                                 21e-3 * uM2.y * exp(-uM2.w / 1.2)) * od * 0.1);
    }
    if (hitg) c *= 0.35;                                   // ground: dimmed aerial haze (Bgcolor shows through)
    vec3 col = 1.0 - exp(-uM1.w * c);
    float a = 1.0;
    if (hitg) { a = clamp(max(col.r, max(col.g, col.b)), 0.0, 1.0); }
    if (int(uMat.y + 0.5) == 1) return vec4(c, hitg ? 1.0 : 0.0);
    return vec4(col, a);
}
"""
