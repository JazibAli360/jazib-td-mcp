# gen_sdf_terrain - GEN_sdf module 'terrain' (FX7a SX-20 raymarch route; lane C2, 27 Oct): a fly-over of mountains and
# valleys with erosion-like gullies, snow line, sun, fog and sky. Clean-room (U8 default): the research row names TDM
# "Mountain Peak" and IQ "Elevated" (Shadertoy, CC BY-NC-SA, not opened); the public technique (value noise with
# analytic derivatives, an fbm that damps octaves where the slope is steep: a += b n / (1 + Erosion |sum dn|^2)) is
# written fresh here, with a 32-bit integer lattice hash so GPU and mirror agree exactly. The camera glides along Yaw
# at Camheight above a 3-octave copy of the ground; rays relax-march the height field (Steps, cap 256; step Relax x
# (y - h)), normals by finite differences with Detail octaves (cap 12). Shading: grass (Colour B) -> rock (Colour A)
# by slope, snow above Snowline on flat ground, sun (Sunyaw / Sunpitch / Suncolor) with optional terrain soft shadows
# (Shadowsteps, cap 32), sky ambient, exponential fog to the horizon (Bgcolor) with sun glow, sky gradient + sun.
# KIND 'flat'; default Quality 0.4 (FSR opt-in). Mirror: gen_sdf_logic.terrain_rm. ASCII only.
MODULE = 'terrain'
KIND = 'flat'
BLURB = 'Terrain fly-over: eroded fbm height field (derivative damping), snow line, sun + shadows, fog, sky.'

PAGES = [('Terrain', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Octaves', 'Int', 5, {'min': 1, 'max': 12, 'label': 'Octaves, march (cap 12)'}),
    ('Detail', 'Int', 8, {'min': 1, 'max': 12, 'label': 'Octaves, normals (cap 12)'}),
    ('Steps', 'Int', 80, {'min': 8, 'max': 256, 'label': 'March steps (cap 256)'}),
    ('Relax', 'Float', 0.45, {'min': 0.1, 'max': 1, 'label': 'Step relax (lower = safer)'}),
    ('Far', 'Float', 120.0, {'min': 10, 'max': 600, 'label': 'Far distance'}),
    ('Tscale', 'Float', 0.06, {'min': 0.005, 'max': 1, 'label': 'Feature scale (1 / size)'}),
    ('Theight', 'Float', 7.0, {'min': 0, 'max': 40, 'label': 'Mountain height'}),
    ('Erosion', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Erosion (gullies)'}),
    ('Snowline', 'Float', 0.55, {'min': 0, 'max': 1.5, 'label': 'Snow line (x height, > 1 = none)'}),
    ('Camheight', 'Float', 2.5, {'min': 0.2, 'max': 40, 'label': 'Camera height above the ground'}),
    ('Flyspeed', 'Float', 3.0, {'min': -40, 'max': 40, 'label': 'Fly speed /s (along Yaw)'}),
    ('Pitch', 'Float', -6.0, {'min': -89, 'max': 60, 'label': 'Camera pitch deg'}),
    ('Yaw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Camera yaw deg'}),
    ('Yawspeed', 'Float', 0.0, {'min': -30, 'max': 30, 'label': 'Yaw drift deg/s'}),
    ('Fov', 'Float', 60.0, {'min': 20, 'max': 150, 'label': 'FOV deg (vertical)'}),
    ('Fogdensity', 'Float', 0.012, {'min': 0, 'max': 0.3, 'label': 'Fog density'}),
    ('Skycolor', 'RGB', (0.25, 0.45, 0.8), {'label': 'Sky zenith colour (horizon = Bgcolor)'}),
    ('Suncolor', 'RGB', (1.0, 0.9, 0.75), {'label': 'Sun colour'}),
    ('Sunintensity', 'Float', 1.6, {'min': 0, 'max': 8, 'label': 'Sun intensity'}),
    ('Sunyaw', 'Float', 150.0, {'min': -180, 'max': 180, 'label': 'Sun yaw deg'}),
    ('Sunpitch', 'Float', 20.0, {'min': -10, 'max': 89, 'label': 'Sun pitch deg'}),
    ('Ambient', 'Float', 0.4, {'min': 0, 'max': 2, 'label': 'Sky ambient'}),
    ('Shadowsteps', 'Int', 0, {'min': 0, 'max': 32, 'label': 'Soft shadow steps (0 off, cap 32)'}),
    ('Beatlight', 'Float', 0.0, {'min': -1, 'max': 4, 'label': 'Beat pulse -> sun'}),
    ('Audioheight', 'Float', 0.0, {'min': -1, 'max': 4, 'label': 'Audio level -> mountain height'}),
])]
DEFAULTS = {'Quality': 0.4, 'Palette': 0, 'Colorar': 0.32, 'Colorag': 0.27, 'Colorab': 0.23, 'Colorbr': 0.2,
            'Colorbg': 0.3, 'Colorbb': 0.12, 'Bgcolorr': 0.7, 'Bgcolorg': 0.75, 'Bgcolorb': 0.82}
PANEL_PAGES = ['Terrain', 'Render', 'Colour', 'Drive']
PRESETS = [
    (1, 'alpine flight', {}),
    (2, 'desert dunes', {'Erosion': 0.2, 'Theight': 4.0, 'Tscale': 0.04, 'Snowline': 2.0, 'Colorar': 0.75,
                         'Colorag': 0.48, 'Colorab': 0.28, 'Colorbr': 0.85, 'Colorbg': 0.6, 'Colorbb': 0.36,
                         'Bgcolorr': 0.9, 'Bgcolorg': 0.78, 'Bgcolorb': 0.62, 'Sunpitch': 12.0, 'Fogdensity': 0.008}),
    (3, 'sunset ridges', {'Sunpitch': 4.0, 'Sunyaw': 0.0, 'Suncolorr': 1.0, 'Suncolorg': 0.5, 'Suncolorb': 0.25,
                          'Sunintensity': 2.5, 'Skycolorr': 0.3, 'Skycolorg': 0.25, 'Skycolorb': 0.5,
                          'Bgcolorr': 0.95, 'Bgcolorg': 0.55, 'Bgcolorb': 0.35, 'Shadowsteps': 12, 'Pitch': -3.0,
                          'Quality': 0.35}),
    (4, 'snow peaks', {'Theight': 10.0, 'Snowline': 0.3, 'Erosion': 1.6, 'Camheight': 4.0, 'Flyspeed': 2.0,
                       'Pitch': -10.0, 'Fogdensity': 0.02}),
    (5, 'night valley', {'Sunintensity': 0.5, 'Suncolorr': 0.6, 'Suncolorg': 0.7, 'Suncolorb': 1.0, 'Sunpitch': 35.0,
                         'Skycolorr': 0.01, 'Skycolorg': 0.02, 'Skycolorb': 0.06, 'Bgcolorr': 0.05, 'Bgcolorg': 0.07,
                         'Bgcolorb': 0.12, 'Ambient': 0.2, 'Snowline': 0.45, 'Beatevery': 1.0, 'Beatgain': 1.0,
                         'Beatdecay': 0.2, 'Beatlight': 2.0}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
_R = 'math.radians'
UNIFORMS = [('uM0', ['{Octaves}', '{Detail}', '{Steps}', '{Relax}']),
            ('uM1', ['{Far}', '{Tscale}', '{Theight}', '{Erosion}']),
            ('uM2', ['{Snowline}', '{Camheight}', '{Flyspeed}', '{Fogdensity}']),
            ('uM3', [_R + '({Pitch})', _R + '({Yaw})', _R + '({Yawspeed})', _R + '({Fov})']),
            ('uM4', ['{Skycolorr}', '{Skycolorg}', '{Skycolorb}', '{Sunintensity}']),
            ('uM5', ['{Suncolorr}', '{Suncolorg}', '{Suncolorb}', '{Ambient}']),
            ('uM6', [_R + '({Sunyaw})', _R + '({Sunpitch})', '{Shadowsteps}', '{Beatlight}']),
            ('uM7', ['{Bgcolorr}', '{Bgcolorg}', '{Bgcolorb}', '{Audioheight}'])]

GLSL = """
float TH;
float th_hash(ivec2 c) {
    return float(lb32(uint(c.x) * 73856093u ^ uint(c.y) * 19349663u ^ SEED * 2654435761u)) * (2.0 / 4294967296.0) - 1.0;
}
vec3 th_noised(vec2 x) {
    vec2 fl = floor(x), f = x - fl;
    ivec2 i = ivec2(fl);
    vec2 u = f * f * (3.0 - 2.0 * f), du = 6.0 * f * (1.0 - f);
    float a = th_hash(i), b = th_hash(i + ivec2(1, 0)), c = th_hash(i + ivec2(0, 1)), d = th_hash(i + ivec2(1, 1));
    float k1 = b - a, k2 = c - a, k4 = a - b - c + d;
    return vec3(a + k1 * u.x + k2 * u.y + k4 * u.x * u.y, du * vec2(k1 + k4 * u.y, k2 + k4 * u.x));
}
float terrain_h(vec2 xz, int n) {
    vec2 p = xz * uM1.y, d = vec2(0.0);
    float a = 0.0, b = 1.0;
    for (int i = 0; i < 12; i++) {
        if (i >= n) break;
        vec3 nd = th_noised(p);
        d += nd.yz;
        a += b * nd.x / (1.0 + uM1.w * dot(d, d));
        b *= 0.5;
        p = vec2(0.8 * p.x - 0.6 * p.y, 0.6 * p.x + 0.8 * p.y) * 2.0;
    }
    return a * TH;
}
vec3 tsky(vec3 rd, vec3 L) {
    float y = max(rd.y, 0.0);
    vec3 c = mix(uM7.rgb, uM4.rgb, 1.0 - exp(-3.0 * y));
    float s = max(dot(rd, L), 0.0);
    return c + uM5.rgb * (uM4.w * (0.15 * pow(s, 12.0) + 2.0 * pow(s, 3000.0)));
}
vec4 render2d(vec2 P) {
    TH = uM1.z * (1.0 + uM7.w * LEVEL);
    vec2 uv = (P - 0.5 * RES) / RES.y;
    float yaw = uM3.y + uM3.z * T, pitch = uM3.x;
    vec3 ww = vec3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw));
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = cross(uu, ww);
    vec3 rd = normalize(uv.x * uu + uv.y * vv + (0.5 / tan(0.5 * uM3.w)) * ww);
    vec3 ro = vec3(sin(uM3.y), 0.0, cos(uM3.y)) * (uM2.z * T);
    ro.y = terrain_h(ro.xz, 3) + uM2.y;
    vec3 L = vec3(cos(uM6.y) * sin(uM6.x), sin(uM6.y), cos(uM6.y) * cos(uM6.x));
    int ng = int(uM0.x + 0.5), nd = int(uM0.y + 0.5), N = int(uM0.z + 0.5);
    float t = 0.5, far = uM1.x;
    bool hit = false;
    for (int i = 0; i < 256; i++) {
        if (i >= N) break;
        vec3 p = ro + rd * t;
        float d = p.y - terrain_h(p.xz, ng);
        if (d < 0.002 * t) { hit = true; break; }
        t += uM0.w * d;
        if (t > far) break;
    }
    vec3 col = tsky(rd, L);
    float hh = 0.0;
    if (hit) {
        vec3 p = ro + rd * t;
        float e = max(0.005, 0.002 * t);
        hh = terrain_h(p.xz, nd);
        vec3 n = normalize(vec3(hh - terrain_h(p.xz + vec2(e, 0.0), nd), e, hh - terrain_h(p.xz + vec2(0.0, e), nd)));
        float rock = clamp((0.85 - n.y) * 5.0, 0.0, 1.0);
        vec3 base = mix(uCb.rgb, uCa.rgb, rock);
        float sn = clamp((hh / max(TH, 1e-3) - uM2.x) * 6.0, 0.0, 1.0) * clamp((n.y - 0.6) * 5.0, 0.0, 1.0);
        base = mix(base, vec3(0.92, 0.94, 0.98), sn);
        float sh = 1.0;
        int ns = int(uM6.z + 0.5);
        if (ns > 0) {
            float st = 0.3;
            for (int j = 0; j < 32; j++) {
                if (j >= ns) break;
                vec3 sp = p + L * st;
                float dh = sp.y - terrain_h(sp.xz, ng);
                sh = min(sh, 8.0 * dh / st);
                st += clamp(dh, 0.1, 2.0);
                if (sh < 0.001) break;
            }
            sh = clamp(sh, 0.0, 1.0);
        }
        float dif = max(dot(n, L), 0.0) * sh;
        float sun = uM4.w * (1.0 + uM6.w * ENV);
        vec3 c = base * (uM5.rgb * (dif * sun) + uM4.rgb * (uM5.w * (0.5 + 0.5 * n.y)));
        vec3 fc = tsky(normalize(vec3(rd.x, 0.02, rd.z)), L);
        col = mix(c, fc, 1.0 - exp(-uM2.w * t));
    }
    if (int(uMat.y + 0.5) == 1) return vec4(t, hit ? 1.0 : 0.0, hh, 1.0);
    return vec4(col, 1.0);
}
"""
