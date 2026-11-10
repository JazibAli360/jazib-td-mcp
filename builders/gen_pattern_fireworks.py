# gen_pattern_fireworks - GEN_pattern module 'fireworks' (FX7a SX-15 + FX7c 7C-10 shell types; BUILD_PLAN_27OCT lane
# A pilot). Analytic per-pixel bursts, no state texture: up to 8 shell slots x up to 128 sparks. A slot shows its
# youngest launch from three sources: the Hit ring (Hit pulse or a CHOP rising edge, e.g. AC_audio/out_ctl kick;
# stamps in module time, Hits page), Auto (Rate shells/s round robin, OFF by default: user rule U7) and Beatlaunch
# (one shell per rack beat step, Beatevery). Shell types peony (Fibonacci sphere), ring (tilted ellipse), willow
# (heavy drag + gravity, long trails), crossette (parents split in 4 at Split x life); mixed = per shell hash.
# Rocket rise (Rise s), flash, soft glow, sparks as capsules (trail Trail s) with 1/(1 + d^2/w^2) glow cut at 16 w,
# twinkle in the last Twinkle of life. Colour = shared palette (W1-B uPal) or any Colour page palette: k = shell hash
# + Colvar per spark + Colshift over life. No limiter (user rule). Clean-room from the SX-15 description (BigWings'
# shader not copied). Mirror: gen_pattern_logic.gen_fireworks. ASCII only.
MODULE = 'fireworks'
KIND = 'gen'
PAL = True
HITS = 8
BLURB = 'Analytic fireworks: 8 shell slots x sparks; Hit / CHOP kick, Auto rate (off), beat launches; shell types.'

PAGES = [('Fireworks', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Type', 'Menu', 'mixed', {'names': ['mixed', 'peony', 'ring', 'willow', 'crossette'],
                               'labels': ['Mixed (per shell)', 'Peony (sphere)', 'Ring', 'Willow (gold rain)',
                                          'Crossette (splits in 4)']}),
    ('Shells', 'Int', 6, {'min': 1, 'max': 8, 'label': 'Shell slots (1-8)'}),
    ('Sparks', 'Int', 48, {'min': 4, 'max': 128, 'label': 'Sparks per shell (<= 128)'}),
    ('Size', 'Float', 0.22, {'min': 0.02, 'max': 0.8, 'label': 'Burst radius (screen heights)'}),
    ('Ylow', 'Float', 0.45, {'min': 0, 'max': 1, 'label': 'Burst height low'}),
    ('Yhigh', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Burst height high'}),
    ('Area', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Burst x spread'}),
    ('Rise', 'Float', 0.6, {'min': 0, 'max': 3, 'label': 'Rocket rise s (0 = burst at once)'}),
    ('Life', 'Float', 1.6, {'min': 0.1, 'max': 6, 'label': 'Spark life s'}),
    ('Drag', 'Float', 3.0, {'min': 0.01, 'max': 12, 'label': 'Drag'}),
    ('Gravity', 'Float', 0.08, {'min': -0.5, 'max': 1, 'label': 'Gravity (screen heights/s2)'}),
    ('Trail', 'Float', 0.12, {'min': 0, 'max': 1, 'label': 'Trail s'}),
    ('Sparksize', 'Float', 2.5, {'min': 0.3, 'max': 20, 'label': 'Spark size px'}),
    ('Bright', 'Float', 0.9, {'min': 0, 'max': 4, 'label': 'Brightness'}),
    ('Flash', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Burst flash'}),
    ('Glow', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'Smoke glow'}),
    ('Twinkle', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Twinkle (last part of life)'}),
    ('Colvar', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Colour spread per spark'}),
    ('Colshift', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Colour shift over life'}),
    ('Variety', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Spark speed variety'}),
    ('Rocket', 'Float', 0.8, {'min': 0, 'max': 4, 'label': 'Rocket brightness'}),
    ('Split', 'Float', 0.45, {'min': 0.05, 'max': 0.95, 'label': 'Crossette split (x life)'}),
]), ('Launch', [
    ('Hit', 'Pulse', None, {'label': 'Hit (launch a shell now)'}),
    ('Hitchop', 'CHOP', '/project1/lab/AC_audio/out_ctl', {'label': 'Hit CHOP (rising edge launches)'}),
    ('Hitchan', 'Str', 'kick', {'label': 'Hit channel'}),
    ('Auto', 'Toggle', False, {'label': 'Auto launch (off by default)'}),
    ('Rate', 'Float', 1.5, {'min': 0.05, 'max': 16, 'label': 'Auto shells/s'}),
    ('Beatlaunch', 'Toggle', False, {'label': 'Launch on beat steps (Drive Beatevery)'}),
    ('Clear', 'Pulse', None, {'label': 'Clear hits'}),
])]
DEFAULTS = {'Palette': 'shared', 'Palsource': 'rainbow', 'Palmode': 'cycle', 'Blend': 'add'}
PANEL_PAGES = ['Fireworks', 'Launch', 'Drive', 'Colour', 'Palette']
PRESETS = [
    (1, 'finale mix', {'Amount': 1.0, 'Type': 'mixed', 'Shells': 8, 'Sparks': 64, 'Palsource': 'rainbow',
                       'Palmode': 'cycle'}),
    (2, 'gold willow', {'Amount': 1.0, 'Type': 'willow', 'Shells': 5, 'Sparks': 72, 'Palsource': 'fire',
                        'Palmode': 'gradient', 'Colvar': 0.25, 'Colshift': -0.35, 'Twinkle': 0.6, 'Sparksize': 2.0,
                        'Size': 0.26}),
    (3, 'neon rings', {'Amount': 1.0, 'Type': 'ring', 'Shells': 6, 'Sparks': 64, 'Palsource': 'neon_trio',
                       'Palmode': 'steps', 'Colvar': 0.0, 'Flash': 0.3, 'Variety': 0.0, 'Trail': 0.08}),
    (4, 'crossette crackle', {'Amount': 1.0, 'Type': 'crossette', 'Shells': 6, 'Sparks': 64, 'Palsource': 'acid',
                              'Palmode': 'cycle', 'Twinkle': 0.7, 'Split': 0.4}),
    (5, 'beat barrage', {'Amount': 1.0, 'Type': 'mixed', 'Shells': 8, 'Sparks': 48, 'Beatlaunch': True,
                         'Beatevery': 1.0, 'Beatgain': 0.5, 'Rise': 0.4, 'Life': 1.4, 'Palsource': 'cyan_magenta',
                         'Palmode': 'cycle', 'Paldrive': 'bpm_step', 'Palevery': 4.0}),
]
# live / offline checks freeze at t = 2 s with these hit stamps (ages 1.8 .. 0.1 s: 5 bursts at several ages, 2 rockets)
CHECK = {'t': 2.0, 'beats': 0.0, 'pars': {'Hit0': 0.2, 'Hit1': 0.5, 'Hit2': 0.8, 'Hit3': 1.05, 'Hit4': 1.25,
                                          'Hit5': 1.7, 'Hit6': 1.9, 'Hit7': -1000.0}}
VOID = '({h} if {h} <= $t + 0.05 else -1000.0)'          # stamps later than now = another clock (T-162)
UNIFORMS = [('uM0', ['{Type#}', '{Shells}', '{Sparks}', '{Size}']),
            ('uM1', ['{Ylow}', '{Yhigh}', '{Area}', '{Rise}']),
            ('uM2', ['{Life}', '{Drag}', '{Gravity}', '{Trail}']),
            ('uM3', ['{Sparksize}', '{Bright}', '{Flash}', '{Glow}']),
            ('uM4', ['{Twinkle}', '{Colvar}', '{Colshift}', '{Auto} * {Rate}']),
            ('uM5', ['({Beatevery} * 60.0 / max($bpm, 1.0) if {Beatlaunch} and {Beatevery} > 0 else 0.0)',
                     '{Rocket}', '{Split}', '{Variety}']),
            ('uH0', [VOID.format(h='{Hit%d}' % i) for i in range(4)]),
            ('uH1', [VOID.format(h='{Hit%d}' % i) for i in range(4, 8)])]

GLSL = """
float fw_seg(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-6), 0.0, 1.0);
    vec2 d = pa - ba * h;
    return dot(d, d);
}
float fw_pt(float d2, float w) { float w2 = w * w; return d2 > 256.0 * w2 ? 0.0 : w2 / (d2 + w2); }
float fw_f(float b, float D, float L) { return (1.0 - exp(-D * b)) / (1.0 - exp(-D * L)); }
float fw_h(uint id, int n) { return float(lb32(id ^ (uint(n) * 0x9E3779B9u) ^ (SEED * 0x85EBCA6Bu))) * (1.0 / 4294967296.0); }
void fw_acc(inout float V, inout float KK, float I, int j, int tk, bool twk, uint id, float kb, float u) {
    if (I <= 0.0) return;
    if (twk && h2(ivec2(j, tk), id ^ 0x77u) >= 0.5) I *= 0.15;
    V += I; KK += I * (kb + uM4.y * (fract(float(j) * 0.381966) - 0.5) + uM4.z * u);
}
void fw_slot(int s, int N, out float age, out uint id) {
    age = 1e9; id = 0u;
    float st = s < 4 ? uH0[s] : uH1[s - 4];
    if (st > -999.0) {
        float a = T - st;
        if (a >= 0.0 && a < age) { age = a; id = (uint(int(floor(st * 64.0))) * 2654435761u) ^ 0x1u; }
    }
    float R = uM4.w;
    if (R > 0.0) {
        float K = floor(T * R);
        float k = K - mod(K - float(s), float(N));
        float a = T - k / R;
        if (k >= 0.0 && a < age) { age = a; id = (uint(int(k)) * 2246822519u) ^ 0xA5A5A5u; }
    }
    float Pb = uM5.x;
    if (Pb > 0.0) {
        float K = STEP;
        float k = K - mod(K - float(s), float(N));
        float a = AGE + (K - k) * Pb;
        if (k >= 0.0 && a < age) { age = a; id = (uint(int(k)) * 3266489917u) ^ 0x5EEDu; }
    }
}
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int N = clamp(int(uM0.y + 0.5), 1, 8), M = clamp(int(uM0.z + 0.5), 1, 128);
    float H = RES.y, w = max(uM3.x, 0.1), L = max(uM2.x, 0.05), D = max(uM2.y, 1e-3), rise = max(uM1.w, 0.0);
    float V = 0.0, KK = 0.0;
    for (int s = 0; s < 8; s++) {
        if (s >= N) break;
        float a; uint id;
        fw_slot(s, N, a, id);
        if (a > 1e8) continue;
        int typ = int(uM0.x + 0.5);
        if (typ == 0) typ = 1 + min(int(fw_h(id, 2) * 4.0), 3);
        float Ls = L, Ds = D, G = uM2.z, Tr = uM2.w;
        if (typ == 3) { Ls *= 1.6; Ds *= 2.5; G *= 1.6; Tr *= 3.0; }
        if (a >= rise + Ls) continue;
        vec2 c = vec2((0.5 + (fw_h(id, 0) - 0.5) * uM1.z) * RES.x, mix(uM1.x, uM1.y, fw_h(id, 1)) * H);
        float kb = fw_h(id, 5), br = uM3.y * (1.0 + ENV);
        if (a < rise) {                                   // rocket: eased climb from the bottom edge, short streak
            float u = a / rise, ua = max(u - 0.12, 0.0);
            float d2 = fw_seg(P, vec2(c.x, c.y * (1.0 - (1.0 - ua) * (1.0 - ua))), vec2(c.x, c.y * (1.0 - (1.0 - u) * (1.0 - u))));
            float I = fw_pt(d2, w * 0.8) * br * uM5.y;
            V += I; KK += I * kb;
            continue;
        }
        float R = uM0.w * H * (0.75 + 0.5 * fw_h(id, 6)) * (1.0 + LEVEL);
        float b = a - rise, u = b / Ls, fade = 1.0 - u * u;
        float fb = fw_f(b, Ds, Ls), gy = -0.5 * G * H * b * b;
        float b0 = max(b - Tr, 0.0), f0 = fw_f(b0, Ds, Ls), gy0 = -0.5 * G * H * b0 * b0;
        float lim = 1.4 * R + 16.0 * w;                   // flash (cut at 8 Rf), glow and every spark lie within lim
        if (fw_seg(P, c, c + vec2(0.0, gy)) > lim * lim) continue;     // of the segment c .. c + gravity drop
        vec2 dv = P - c;
        float dc2 = dot(dv, dv);
        if (uM3.z > 0.0) {                                // burst flash
            float Rf = 0.12 * R + w;
            if (dc2 < 64.0 * Rf * Rf) { float I = uM3.z * br * exp(-b / 0.06) * Rf * Rf / (dc2 + Rf * Rf); V += I; KK += I * kb; }
        }
        if (uM3.w > 0.0) {                                // smoke glow (compact)
            float Rg = R * fb + w;
            float x = 1.0 - dc2 / (Rg * Rg);
            if (x > 0.0) { float I = uM3.w * 0.3 * fade * x * x; V += I; KK += I * kb; }
        }
        float rot = fw_h(id, 3) * TAU, ct = 0.25 + 0.75 * fw_h(id, 4), jo = fw_h(id, 7), orient = fw_h(id, 8) * PI;
        bool twk = u > 1.0 - uM4.x;
        int tk = int(floor(b * 24.0));
        float cut = 16.0 * w + abs(gy - gy0), bf = br * fade;
        vec2 cg = c + vec2(0.0, gy);
        if (typ == 4) {                                   // crossette: Pn parents (Fibonacci), each splits in 4
            int Pn = max(M / 4, 2);
            float ts = uM5.z * Ls, fts = fw_f(ts, Ds, Ls), fc0 = fw_f(max(b0 - ts, 0.0), Ds, Ls), fc = fw_f(max(b - ts, 0.0), Ds, Ls);
            for (int p = 0; p < 32; p++) {
                if (p >= Pn) break;
                float fp = float(p);
                float z = 1.0 - (2.0 * fp + 1.0) / float(Pn), rr = sqrt(max(1.0 - z * z, 0.0));
                float phi = fp * 2.39996323 + rot, sp = 1.0 - uM5.w * fract(fp * 0.5698403 + jo);
                vec2 dir = rr * vec2(cos(phi), sin(phi)) * sp;
                if (b < ts) {
                    fw_acc(V, KK, fw_pt(fw_seg(P, c + dir * R * f0 + vec2(0.0, gy0), cg + dir * R * fb), w) * bf, p * 4, tk, twk, id, kb, u);
                    continue;
                }
                vec2 base = c + dir * R * fts, e = P - base - vec2(0.0, gy);
                float lim = 0.35 * R + cut;
                if (dot(e, e) > lim * lim) continue;      // all 4 children are farther than the glow cut
                for (int ci = 0; ci < 4; ci++) {
                    float ca = rot + float(ci) * PI * 0.5 + fp;
                    vec2 ce = vec2(cos(ca), sin(ca)) * 0.35 * R;
                    fw_acc(V, KK, fw_pt(fw_seg(P, base + ce * fc0 + vec2(0.0, gy0), base + ce * fc + vec2(0.0, gy)), w) * bf, p * 4 + ci, tk, twk, id, kb, u);
                }
            }
            continue;
        }
        // peony / willow / ring: every spark lies on a ray from cg (its trail start is off it by |gy - gy0|), so only
        // sparks whose ray angle is within asin(cut / rho) of the pixel's angle can reach it: loop that window only.
        vec2 e = P - cg;
        float rho = length(e), th = atan(e.y, e.x), fM = float(M);
        float dlt = rho > cut ? asin(cut / rho) : 4.0;
        int j0 = 0, n = M;
        if (typ == 2) {
            if (dlt / ct < PI) {
                float aa = th - orient;
                float uu = (atan(sin(aa) / ct, cos(aa)) - rot) / TAU * fM, dj = dlt / ct / TAU * fM;
                j0 = int(floor(uu - dj)); n = min(int(ceil(uu + dj)) - j0 + 1, M);
            }
        } else if (dlt < PI) {
            float uu = (th - rot) / TAU * fM, dj = dlt / TAU * fM;
            j0 = int(floor(uu - dj - 0.9)); n = min(int(floor(uu + dj - 0.1)) - j0 + 1, M);
        }
        j0 = int(mod(float(j0), fM));
        float jz = fw_h(id, 9);
        for (int i = 0; i < 128; i++) {
            if (i >= n) break;
            int j = j0 + i;
            if (j >= M) j -= M;
            float fj = float(j);
            vec2 dir;
            if (typ == 2) {
                float phi = rot + TAU * fj / fM;
                dir = rot2(vec2(cos(phi), ct * sin(phi)), orient);
            } else {
                float phi = rot + TAU * (fj + 0.5 + 0.8 * (fract(fj * 0.7548777 + jo) - 0.5)) / fM;
                float z = 2.0 * fract(fj * 0.6180339887 + jz) - 1.0;
                dir = sqrt(max(1.0 - z * z, 0.0)) * (1.0 - uM5.w * fract(fj * 0.5698403 + jo)) * vec2(cos(phi), sin(phi));
            }
            fw_acc(V, KK, fw_pt(fw_seg(P, c + dir * R * f0 + vec2(0.0, gy0), cg + dir * R * fb), w) * bf, j, tk, twk, id, kb, u);
        }
    }
    v = V;
    k = V > 1e-6 ? KK / V : 0.0;
}
"""
