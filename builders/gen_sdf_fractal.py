# gen_sdf_fractal - GEN_sdf module 'fractal' (FX5 G14 3D part, FX0 row 67): raymarched distance-estimated fractals:
# Mandelbulb (power n, running derivative DE 0.5 ln r r / dr), Mandelbox (box fold + sphere fold + scale), quaternion
# Julia (4D slice, DE 0.25 |z| ln|z| / |z'|) and a Menger-type KIFS (abs fold + sort + rotate + scale). Juliamix
# morphs Mandel -> Julia (c = mix(p, Juliac, Juliamix)) for bulb and box; Julia c orbits (Juliaorbit / Juliaspeed);
# Power swings / follows beat and audio. Orbit-trap colour. Shared ray core in gen_sdf.py.
# Maths is public (White / Nylander 2009 Mandelbulb, Lowe 2010 Mandelbox, IQ quaternion Julia article); written
# fresh here. Mirror: gen_sdf_logic.fractal_*. ASCII only.
MODULE = 'fractal'
KIND = 'ray'
BLURB = 'Distance-estimated fractal raymarch: Mandelbulb / Mandelbox / quaternion Julia / KIFS.'
TYPES = ['mandelbulb', 'mandelbox', 'quatjulia', 'kifs']

PAGES = [('Fractal', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Type', 'Menu', 'mandelbulb', {'names': TYPES, 'labels': ['Mandelbulb', 'Mandelbox', 'Quaternion Julia', 'KIFS (Menger fold)']}),
    ('Iterations', 'Int', 8, {'min': 1, 'max': 32, 'label': 'Iterations (cap 32)'}),
    ('Power', 'Float', 8.0, {'min': 2, 'max': 16, 'label': 'Power (bulb)'}),
    ('Powerswing', 'Float', 0.0, {'min': 0, 'max': 6, 'label': 'Power swing'}),
    ('Powerspeed', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Power swing rad/s'}),
    ('Beatpower', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Beat pulse -> power'}),
    ('Bailout', 'Float', 2.0, {'min': 1.5, 'max': 16, 'label': 'Bailout (bulb)'}),
    ('Juliamix', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Mandel -> Julia (bulb / box)'}),
    ('Juliacx', 'Float', 0.095, {'min': -2, 'max': 2, 'label': 'Julia c x'}),
    ('Juliacy', 'Float', -0.327, {'min': -2, 'max': 2, 'label': 'Julia c y'}),
    ('Juliacz', 'Float', 0.077, {'min': -2, 'max': 2, 'label': 'Julia c z'}),
    ('Juliacw', 'Float', 0.204, {'min': -2, 'max': 2, 'label': 'Julia c w (quaternion)'}),
    ('Juliaorbit', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Julia c orbit radius'}),
    ('Juliaspeed', 'Float', 0.3, {'min': -4, 'max': 4, 'label': 'Julia c orbit rad/s'}),
    ('Boxscale', 'Float', -1.5, {'min': -4, 'max': 4, 'label': 'Box scale'}),
    ('Foldlimit', 'Float', 1.0, {'min': 0.2, 'max': 3, 'label': 'Box fold limit'}),
    ('Minradius', 'Float', 0.5, {'min': 0.05, 'max': 2, 'label': 'Sphere fold min radius'}),
    ('Fixedradius', 'Float', 1.0, {'min': 0.1, 'max': 3, 'label': 'Sphere fold fixed radius'}),
    ('Kifsscale', 'Float', 3.0, {'min': 1.2, 'max': 4, 'label': 'KIFS scale'}),
    ('Kifsoffset', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'KIFS offset'}),
    ('Kifsangle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'KIFS rotate deg'}),
    ('Kifsspeed', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'KIFS rotate deg/s'}),
])]
DEFAULTS = {'Quality': 0.35, 'Steps': 128, 'Epsilon': 1.0, 'Stepscale': 0.8, 'Camdist': 2.8, 'Shadowsteps': 0, 'Aosteps': 3,
            'Fogdensity': 0.02, 'Palette': 5}
PANEL_PAGES = ['Fractal', 'Render', 'Camera', 'Look', 'Colour', 'Drive']
PRESETS = [
    (1, 'mandelbulb', {'Type': 0, 'Power': 8.0, 'Camdist': 2.8, 'Campitch': 20.0, 'Orbitspeed': 8.0, 'Material': 1,
                       'Palette': 5, 'Spread': 1.5}),
    (2, 'bulb breathe', {'Type': 0, 'Power': 6.0, 'Powerswing': 2.0, 'Powerspeed': 0.4, 'Beatpower': 1.0,
                         'Beatevery': 1.0, 'Beatgain': 1.0, 'Camdist': 2.6, 'Material': 3, 'Rim': 0.8,
                         'Palette': 6, 'Glow': 0.5}),
    (3, 'julia bulb', {'Type': 0, 'Power': 8.0, 'Juliamix': 1.0, 'Juliacx': 0.45, 'Juliacy': -0.5, 'Juliacz': 0.3,
                       'Juliaorbit': 0.1, 'Juliaspeed': 0.25, 'Camdist': 2.6, 'Material': 2, 'Palette': 2}),
    (4, 'mandelbox', {'Type': 1, 'Iterations': 12, 'Boxscale': -1.5, 'Camdist': 7.0, 'Campitch': 25.0,
                      'Material': 1, 'Palette': 3, 'Fogdensity': 0.04}),
    (5, 'quaternion julia', {'Type': 2, 'Iterations': 11, 'Juliaorbit': 0.1, 'Juliaspeed': 0.3, 'Camdist': 3.0,
                             'Material': 1, 'Palette': 7, 'Specpower': 48.0}),
    (6, 'kifs temple', {'Type': 3, 'Iterations': 6, 'Kifsscale': 3.0, 'Kifsangle': 12.0, 'Kifsspeed': 4.0,
                        'Camdist': 4.0, 'Campitch': 30.0, 'Material': 4, 'Rim': 0.3, 'Palette': 4, 'Aosteps': 4}),
    # SX-23 (lane C2, 27 Oct): inversion / KIFS glow fly-throughs (Fizzer / Kali / Leon looks, clean-room presets of the
    # existing types: fly camera inside the fold, near-miss glow carries the picture, dense fog)
    (7, 'kifs glow orbit', {'Type': 3, 'Iterations': 7, 'Kifsscale': 2.4, 'Kifsoffset': 1.0, 'Kifsangle': 25.0,
                             'Kifsspeed': 0.0, 'Campath': 2, 'Camdist': 2.6, 'Sway': 0.3,
                             'Campitch': 10.0, 'Camyaw': 0.0, 'Orbitspeed': 6.0, 'Fov': 75.0, 'Material': 3, 'Rim': 0.6,
                             'Glow': 2.2, 'Glowfalloff': 10.0, 'Glowhue': 0.3, 'Fogdensity': 0.06, 'Palette': 4,
                             'Spread': 0.6, 'Aosteps': 0, 'Far': 12.0}),
    (8, 'box cathedral', {'Type': 1, 'Iterations': 10, 'Boxscale': 2.0, 'Foldlimit': 1.0, 'Minradius': 0.5,
                          'Campath': 2, 'Camdist': 10.0, 'Campitch': 25.0, 'Orbitspeed': 4.0, 'Sway': 0.4, 'Fov': 60.0,
                          'Material': 1, 'Glow': 0.8, 'Glowfalloff': 6.0, 'Fogdensity': 0.12, 'Palette': 7,
                          'Spread': 1.2, 'Aosteps': 3}),
    (9, 'julia glow', {'Type': 2, 'Iterations': 10, 'Juliacx': -0.2, 'Juliacy': 0.6, 'Juliacz': 0.2, 'Juliacw': 0.2,
                       'Juliaorbit': 0.15, 'Juliaspeed': 0.4, 'Camdist': 2.6, 'Material': 3, 'Rim': 1.0,
                       'Glow': 1.6, 'Glowfalloff': 10.0, 'Beatglow': 1.0, 'Beatevery': 1.0, 'Beatgain': 1.0,
                       'Palette': 6, 'Spread': 0.8, 'Aosteps': 0}),
    (10, 'power coils', {'Type': 0, 'Power': 3.0, 'Powerswing': 1.0, 'Powerspeed': 0.25, 'Iterations': 7, 'Quality': 0.28,
                         'Juliamix': 1.0, 'Juliacx': 0.3, 'Juliacy': 0.5, 'Juliacz': -0.4, 'Juliaorbit': 0.2,
                         'Camdist': 2.4, 'Campitch': 35.0, 'Material': 3, 'Rim': 0.7, 'Glow': 1.0,
                         'Glowfalloff': 14.0, 'Palette': 4, 'Spread': 1.4, 'Fogdensity': 0.08}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
UNIFORMS = [('uM0', ['{Type#}', '{Iterations}', '{Power}', '{Powerswing}']),
            ('uM1', ['{Powerspeed}', '{Beatpower}', '{Bailout}', '{Juliaorbit}']),
            ('uM2', ['{Juliacx}', '{Juliacy}', '{Juliacz}', '{Juliacw}']),
            ('uM3', ['{Juliamix}', '{Juliaspeed}', '{Boxscale}', '{Foldlimit}']),
            ('uM4', ['{Minradius}', '{Fixedradius}', 'math.radians({Kifsangle})', 'math.radians({Kifsspeed})']),
            ('uM5', ['{Kifsscale}', '{Kifsoffset}', '0', '0'])]

GLSL = """
float POW; vec4 JC; vec2 KR;
void setup() {
    POW = uM0.z + uM0.w * sin(uM1.x * T) + uM1.y * ENV + LEVEL;
    float w = uM3.y * T;
    JC = vec4(uM2.xyz + uM1.w * vec3(cos(w), sin(w), 0.5 * sin(0.7 * w)), uM2.w);
    float ka = uM4.z + uM4.w * T;
    KR = vec2(cos(ka), sin(ka));
}
vec2 cmul(vec2 a, vec2 b) { return vec2(a.x * b.x - a.y * b.y, a.x * b.y + a.y * b.x); }
float de_bulb(vec3 p, out float trap) {
    vec3 z = p, c = mix(p, JC.xyz, uM3.x);
    float dr = 1.0, r = 0.0;
    trap = 1e10;
    int n = int(uM0.y + 0.5);
    float pn = floor(POW + 0.5);
    bool ip = abs(POW - pn) < 1e-4 && pn >= 2.0;   // whole power: trig-free (complex powers of the two angles)
    int ni = int(pn);
    for (int i = 0; i < MAXIT; i++) {
        if (i >= n) break;
        r = length(z);
        if (r > uM1.z) break;
        float ri = 1.0 / max(r, 1e-9), rpw;
        if (ip) {
            // (cos th + i sin th)^n, (cos ph + i sin ph)^n with th = acos(z.z / r), ph = atan(z.y, z.x)
            float rho = length(z.xy);
            vec2 u = vec2(z.z, rho) * ri, v = rho > 1e-9 ? z.xy / rho : vec2(1.0, 0.0);
            vec2 un = vec2(1.0, 0.0), vn = vec2(1.0, 0.0);
            float rn = 1.0, rb = r;
            int ex = ni;
            for (int k = 0; k < 5; k++) {          // binary powers, n <= 31
                if ((ex & 1) != 0) { un = cmul(un, u); vn = cmul(vn, v); rn *= rb; }
                ex >>= 1;
                if (ex == 0) break;
                u = cmul(u, u); v = cmul(v, v); rb *= rb;
            }
            rpw = rn;
            z = rn * vec3(un.y * vn.x, un.y * vn.y, un.x) + c;
        } else {
            float th = acos(clamp(z.z * ri, -1.0, 1.0)) * POW;
            float ph = atan(z.y, z.x) * POW;
            rpw = pow(r, POW);
            z = rpw * vec3(sin(th) * cos(ph), sin(th) * sin(ph), cos(th)) + c;
        }
        dr = rpw * ri * POW * dr + (1.0 - uM3.x);   // r^(POW-1) = r^POW / r
        trap = min(trap, dot(z, z));
    }
    return 0.5 * log(max(r, 1e-9)) * r / max(dr, 1e-9);
}
float de_box(vec3 p, out float trap) {
    vec3 z = p, c = mix(p, JC.xyz, uM3.x);
    float S = uM3.z, fl = uM3.w, mr2 = max(uM4.x * uM4.x, 1e-6), fr2 = uM4.y * uM4.y, dr = 1.0;
    trap = 1e10;
    int n = int(uM0.y + 0.5);
    for (int i = 0; i < MAXIT; i++) {
        if (i >= n) break;
        z = clamp(z, -fl, fl) * 2.0 - z;
        float r2 = dot(z, z);
        if (r2 < mr2) { z *= fr2 / mr2; dr *= fr2 / mr2; }
        else if (r2 < fr2) { z *= fr2 / r2; dr *= fr2 / r2; }
        z = z * S + c;
        dr = dr * abs(S) + (1.0 - uM3.x);
        trap = min(trap, r2);
    }
    return length(z) / abs(dr);
}
float de_quat(vec3 p, out float trap) {
    vec4 z = vec4(p, 0.0);
    float md2 = 1.0, mz2 = dot(z, z);
    trap = 1e10;
    int n = int(uM0.y + 0.5);
    for (int i = 0; i < MAXIT; i++) {
        if (i >= n) break;
        md2 *= 4.0 * mz2;
        z = vec4(z.x * z.x - dot(z.yzw, z.yzw), 2.0 * z.x * z.yzw) + JC;
        mz2 = dot(z, z);
        trap = min(trap, mz2);
        if (mz2 > 256.0) break;
    }
    return 0.25 * sqrt(mz2 / max(md2, 1e-20)) * log(max(mz2, 1e-20));
}
float de_kifs(vec3 p, out float trap) {
    float S = uM5.x, o = uM5.y, sc = 1.0;
    trap = 1e10;
    int n = int(uM0.y + 0.5);
    for (int i = 0; i < MAXIT; i++) {
        if (i >= n) break;
        p = abs(p);
        if (p.x < p.y) p.xy = p.yx;
        if (p.x < p.z) p.xz = p.zx;
        if (p.y < p.z) p.yz = p.zy;
        p.xy = vec2(KR.x * p.x - KR.y * p.y, KR.y * p.x + KR.x * p.y);
        p = p * S - vec3(o * (S - 1.0));
        if (p.z < -0.5 * o * (S - 1.0)) p.z += o * (S - 1.0);
        sc *= S;
        trap = min(trap, dot(p, p));
    }
    return sdBox(p, vec3(1.0)) / sc;
}
float de(vec3 p, out float trap) {
    int ty = int(uM0.x + 0.5);
    if (ty == 0) return de_bulb(p, trap);
    if (ty == 1) return de_box(p, trap);
    if (ty == 2) return de_quat(p, trap);
    return de_kifs(p, trap);
}
float map(vec3 p) { float tr; return de(p, tr); }
float mapk(vec3 p) { float tr; float d = de(p, tr); return sqrt(max(tr, 0.0)); }
"""
