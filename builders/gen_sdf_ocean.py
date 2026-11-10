# gen_sdf_ocean - GEN_sdf module 'ocean' (FX7a SX-14 + FX7c 7C-14; lane C2, 27 Oct): a sunlit or stormy sea under a
# sky gradient, camera gliding over it. Clean-room (U8 default: no CC BY-NC-SA code): the research rows name TDM
# "Seascape" and dr2 "Wavescape" (Shadertoy, CC BY-NC-SA) and lygia's Gerstner waves; none was copied. Technique,
# written fresh here: the sea is a height field h(x, z, t) = sum over octaves (cap 8) of two crossing wave trains per
# octave, each a sharp crest exp(Choppy (sin(phase) - 1)) (narrow peaks, wide troughs), the first train domain-warped
# (Warp); every octave rotates (0.8 / 0.6), scales x 1.9, amplitude x 0.42 and runs faster (deep-water dispersion).
# The ray finds the surface by regula falsi between the eye and Far (Steps, cap 64; geometry Octaves), the normal by
# finite differences with more octaves (Detail). Shading: Fresnel mix of the reflected sky and a deep colour (Colour A)
# with crest scatter (Colour B x height x Scatter, lit by a wrapped diffuse), sun specular, foam on the highest crests,
# exponential fog to the horizon colour (Bgcolor). Sky = horizon -> zenith gradient + sun glow + disk. KIND 'flat'
# (render2d): the rack's Quality / Upscale (FSR) / Still apply; default Quality 0.5. Beat / audio swell the waves.
# Mirror: gen_sdf_logic.ocean_rm. ASCII only.
MODULE = 'ocean'
KIND = 'flat'
BLURB = 'Ocean: sharp-crest wave octaves (height field, regula falsi), Fresnel sky, crest scatter, foam, sun.'

PAGES = [('Ocean', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Octaves', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Wave octaves, march (cap 8)'}),
    ('Detail', 'Int', 6, {'min': 1, 'max': 8, 'label': 'Wave octaves, normals (cap 8)'}),
    ('Height', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Wave height'}),
    ('Freq', 'Float', 0.16, {'min': 0.01, 'max': 2, 'label': 'Wave frequency'}),
    ('Choppy', 'Float', 4.0, {'min': 0.2, 'max': 12, 'label': 'Choppy (sharper crests)'}),
    ('Wavespeed', 'Float', 0.8, {'min': -4, 'max': 4, 'label': 'Wave speed'}),
    ('Warp', 'Float', 0.6, {'min': 0, 'max': 3, 'label': 'Crest warp'}),
    ('Steps', 'Int', 12, {'min': 2, 'max': 64, 'label': 'Surface search steps (cap 64)'}),
    ('Camheight', 'Float', 3.5, {'min': 0.2, 'max': 40, 'label': 'Camera height'}),
    ('Flyspeed', 'Float', 1.5, {'min': -20, 'max': 20, 'label': 'Glide speed /s'}),
    ('Pitch', 'Float', -12.0, {'min': -89, 'max': 60, 'label': 'Camera pitch deg'}),
    ('Yaw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Camera yaw deg'}),
    ('Yawspeed', 'Float', 0.0, {'min': -30, 'max': 30, 'label': 'Yaw drift deg/s'}),
    ('Fov', 'Float', 60.0, {'min': 20, 'max': 150, 'label': 'FOV deg (vertical)'}),
    ('Far', 'Float', 300.0, {'min': 20, 'max': 2000, 'label': 'Far distance'}),
    ('Fogdensity', 'Float', 0.004, {'min': 0, 'max': 0.2, 'label': 'Fog density'}),
    ('Skycolor', 'RGB', (0.16, 0.36, 0.66), {'label': 'Sky zenith colour (horizon = Bgcolor)'}),
    ('Suncolor', 'RGB', (1.0, 0.92, 0.78), {'label': 'Sun colour'}),
    ('Sunintensity', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Sun intensity'}),
    ('Sunyaw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Sun yaw deg'}),
    ('Sunpitch', 'Float', 12.0, {'min': -10, 'max': 89, 'label': 'Sun pitch deg'}),
    ('Specpower', 'Float', 60.0, {'min': 2, 'max': 1000, 'label': 'Sun glitter power'}),
    ('Scatter', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Crest scatter (Colour B)'}),
    ('Fresnelpow', 'Float', 3.0, {'min': 0.5, 'max': 8, 'label': 'Fresnel power'}),
    ('Foam', 'Float', 0.4, {'min': 0, 'max': 2, 'label': 'Foam on crests'}),
    ('Foamstart', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'Foam starts at crest height'}),
    ('Beatwave', 'Float', 0.0, {'min': -1, 'max': 4, 'label': 'Beat pulse -> wave height'}),
    ('Audiowave', 'Float', 0.0, {'min': -1, 'max': 4, 'label': 'Audio level -> wave height'}),
])]
DEFAULTS = {'Quality': 0.5, 'Palette': 0, 'Colorar': 0.01, 'Colorag': 0.08, 'Colorab': 0.14, 'Colorbr': 0.42,
            'Colorbg': 0.62, 'Colorbb': 0.52, 'Bgcolorr': 0.62, 'Bgcolorg': 0.7, 'Bgcolorb': 0.78}
PANEL_PAGES = ['Ocean', 'Render', 'Colour', 'Drive']
PRESETS = [
    (1, 'sunlit sea', {}),
    (2, 'storm', {'Height': 2.2, 'Freq': 0.2, 'Choppy': 2.5, 'Wavespeed': 1.4, 'Warp': 1.1, 'Foam': 1.0, 'Foamstart': 0.4,
                  'Sunintensity': 0.25, 'Skycolorr': 0.18, 'Skycolorg': 0.2, 'Skycolorb': 0.24, 'Bgcolorr': 0.34,
                  'Bgcolorg': 0.37, 'Bgcolorb': 0.4, 'Fogdensity': 0.012, 'Camheight': 4.5, 'Flyspeed': 3.0,
                  'Colorar': 0.01, 'Colorag': 0.05, 'Colorab': 0.07}),
    (3, 'golden sunset', {'Sunpitch': 2.5, 'Sunyaw': 0.0, 'Suncolorr': 1.0, 'Suncolorg': 0.55, 'Suncolorb': 0.22,
                          'Sunintensity': 2.0, 'Skycolorr': 0.2, 'Skycolorg': 0.16, 'Skycolorb': 0.36,
                          'Bgcolorr': 0.98, 'Bgcolorg': 0.55, 'Bgcolorb': 0.3, 'Pitch': -6.0, 'Specpower': 200.0}),
    (4, 'night moon', {'Sunpitch': 18.0, 'Suncolorr': 0.75, 'Suncolorg': 0.85, 'Suncolorb': 1.0, 'Sunintensity': 0.6,
                       'Skycolorr': 0.0, 'Skycolorg': 0.01, 'Skycolorb': 0.04, 'Bgcolorr': 0.04, 'Bgcolorg': 0.06,
                       'Bgcolorb': 0.1, 'Colorbr': 0.1, 'Colorbg': 0.2, 'Colorbb': 0.3, 'Scatter': 0.3,
                       'Specpower': 400.0, 'Foam': 0.1}),
    (5, 'beat swell', {'Beatevery': 1.0, 'Beatgain': 1.0, 'Beatdecay': 0.4, 'Beatwave': 1.2, 'Height': 0.5,
                       'Choppy': 5.0, 'Flyspeed': 2.0, 'Yawspeed': 2.0}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
_R = 'math.radians'
UNIFORMS = [('uM0', ['{Octaves}', '{Detail}', '{Height}', '{Freq}']),
            ('uM1', ['{Choppy}', '{Wavespeed}', '{Warp}', '{Steps}']),
            ('uM2', ['{Camheight}', '{Flyspeed}', _R + '({Pitch})', _R + '({Yaw})']),
            ('uM3', [_R + '({Yawspeed})', _R + '({Fov})', '{Far}', '{Fogdensity}']),
            ('uM4', ['{Skycolorr}', '{Skycolorg}', '{Skycolorb}', '{Sunintensity}']),
            ('uM5', [_R + '({Sunyaw})', _R + '({Sunpitch})', '{Specpower}', '{Foam}']),
            ('uM6', ['{Scatter}', '{Fresnelpow}', '{Beatwave}', '{Audiowave}']),
            ('uM7', ['{Suncolorr}', '{Suncolorg}', '{Suncolorb}', '{Foamstart}']),
            ('uM8', ['{Bgcolorr}', '{Bgcolorg}', '{Bgcolorb}', '0'])]

GLSL = """
float OGAIN;
float ocean_h(vec2 xz, int n) {
    vec2 q = xz * uM0.w;
    float amp = uM0.z, h = 0.0, ch = uM1.x, tt = T * uM1.y;
    for (int i = 0; i < 8; i++) {
        if (i >= n) break;
        float s1 = sin(q.x + tt + uM1.z * sin(0.7 * q.y + 1.3));
        float s2 = sin(0.5 * q.x + 0.866 * q.y - 0.7 * tt + 0.8);
        h += amp * (0.6 * exp(ch * (s1 - 1.0)) + 0.4 * exp(ch * (s2 - 1.0)));
        q = vec2(0.8 * q.x - 0.6 * q.y, 0.6 * q.x + 0.8 * q.y) * 1.9;
        amp *= 0.42;
        ch = mix(ch, 1.0, 0.2);
        tt *= 1.38;
    }
    return h * OGAIN;
}
vec3 osky(vec3 rd, vec3 L) {
    float y = max(rd.y, 0.0);
    vec3 c = mix(uM8.rgb, uM4.rgb, 1.0 - exp(-4.0 * y));
    float s = max(dot(rd, L), 0.0);
    return c + uM7.rgb * (uM4.w * (0.2 * pow(s, 32.0) + 3.0 * pow(s, 3000.0)));
}
vec4 render2d(vec2 P) {
    OGAIN = 1.0 + uM6.z * ENV + uM6.w * LEVEL;
    vec2 uv = (P - 0.5 * RES) / RES.y;
    float yaw = uM2.w + uM3.x * T, pitch = uM2.z;
    vec3 ww = vec3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw));
    vec3 uu = normalize(cross(ww, vec3(0.0, 1.0, 0.0)));
    vec3 vv = cross(uu, ww);
    vec3 rd = normalize(uv.x * uu + uv.y * vv + (0.5 / tan(0.5 * uM3.y)) * ww);
    vec3 ro = vec3(sin(uM2.w), 0.0, cos(uM2.w)) * (uM2.y * T) + vec3(0.0, uM2.x, 0.0);
    vec3 L = vec3(cos(uM5.y) * sin(uM5.x), sin(uM5.y), cos(uM5.y) * cos(uM5.x));
    int ng = int(uM0.x + 0.5), nd = int(uM0.y + 0.5), N = int(uM1.w + 0.5);
    float far = uM3.z;
    vec3 px = ro + rd * far;
    float hx = px.y - ocean_h(px.xz, ng);
    float hm = ro.y - ocean_h(ro.xz, ng);
    bool hit = hx < 0.0;
    float t = far;
    if (hit) {
        float tm = 0.0, tx = far;
        t = 0.0;
        if (hm > 0.0) {
            for (int i = 0; i < 64; i++) {             // regula falsi between the eye (above) and Far (below)
                if (i >= N) break;
                t = mix(tm, tx, hm / (hm - hx));
                vec3 p = ro + rd * t;
                float hc = p.y - ocean_h(p.xz, ng);
                if (hc < 0.0) { tx = t; hx = hc; } else { tm = t; hm = hc; }
            }
        }
    }
    vec3 col;
    float hh = 0.0;
    if (hit) {
        vec3 p = ro + rd * t;
        float e = max(0.01, 0.002 * t);
        hh = ocean_h(p.xz, nd);
        vec3 n = normalize(vec3(hh - ocean_h(p.xz + vec2(e, 0.0), nd), e, hh - ocean_h(p.xz + vec2(0.0, e), nd)));
        float fre = pow(1.0 - clamp(dot(n, -rd), 0.0, 1.0), uM6.y) * 0.85;
        vec3 rf = reflect(rd, n);
        rf.y = abs(rf.y);
        vec3 refl = osky(rf, L);
        float dif = clamp(dot(n, L) * 0.4 + 0.6, 0.0, 1.0);
        float hn = hh / max(uM0.z * 1.72 * OGAIN, 1e-4);
        vec3 refr = uCa.rgb + uCb.rgb * (dif * dif * 0.12 + hn * uM6.x * 0.3);
        col = mix(refr, refl, fre);
        col += uM7.rgb * (uM4.w * pow(max(dot(rf, L), 0.0), uM5.z));
        float fs = clamp((hn - uM7.w) / max(1.0 - uM7.w, 1e-3), 0.0, 1.0);
        col = mix(col, vec3(0.9, 0.95, 1.0) * (0.5 + 0.5 * dif), fs * fs * (3.0 - 2.0 * fs) * min(uM5.w, 1.0));
        col += vec3(0.9, 0.95, 1.0) * (fs * max(uM5.w - 1.0, 0.0));
        col = mix(col, uM8.rgb, 1.0 - exp(-uM3.w * t));
    } else {
        col = osky(rd, L);
    }
    if (int(uMat.y + 0.5) == 1) return vec4(t, hit ? 1.0 : 0.0, hh, 1.0);
    return vec4(col, 1.0);
}
"""
