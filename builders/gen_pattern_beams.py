# gen_pattern_beams - GEN_pattern module 'beams' (FX7b TC-32 "beam fans that paint" + FX7c 7C-20 "virtual laser
# show"; BUILD_PLAN_27OCT lane A). Concert light vocabulary in 2D, one pass, no state: up to 32 beams.
# Modes: fans (two mirrored groups from the floor, fan + tilt + sweep), cones (a row of moving heads, per-beam tilt),
# tunnel (radial laser spokes from the centre, rotating), waves (laser sheets: horizontal lines that wave).
# Style beam (soft cone, gaussian across, widens with Spread) or laser (thin core + glow). Beat steps (Beatevery)
# re-arrange the look: tilt / fan / per-beam targets from a hash of the step, eased over Morph s. Haze = fbm smoke
# that drifts up and modulates the beams (the "painting" smoke of TC-32 without state; for real painted trails put
# FX_synth vfeedback / a feedback module after it). Flares at the beam sources. Colour: shared palette (W1-B uPal),
# beam i -> k = (i + 0.5) / Count (palette steps = one stop per beam). No limiter. Mirror: gen_pattern_logic.gen_beams.
MODULE = 'beams'
KIND = 'gen'
PAL = True
BLURB = 'Beam fans / moving-head cones / laser tunnel / laser waves; beat re-arranges, haze, flares.'

PAGES = [('Beams', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Mode', 'Menu', 'fans', {'names': ['fans', 'cones', 'tunnel', 'waves'],
                              'labels': ['Fans (two mirrored groups)', 'Cones (row of moving heads)',
                                         'Tunnel (radial spokes)', 'Waves (laser sheets)']}),
    ('Style', 'Menu', 'beam', {'names': ['beam', 'laser'], 'labels': ['Beam (soft cone)', 'Laser (thin line)']}),
    ('Count', 'Int', 12, {'min': 1, 'max': 32, 'label': 'Beams (<= 32)'}),
    ('Bright', 'Float', 0.8, {'min': 0, 'max': 4, 'label': 'Brightness'}),
    ('Fan', 'Float', 50.0, {'min': 0, 'max': 180, 'label': 'Fan width deg'}),
    ('Tilt', 'Float', 20.0, {'min': 0, 'max': 90, 'label': 'Tilt range deg (beat targets)'}),
    ('Sweep', 'Float', 12.0, {'min': 0, 'max': 90, 'label': 'Sweep deg'}),
    ('Sweepspeed', 'Float', 0.15, {'min': -4, 'max': 4, 'label': 'Sweep Hz'}),
    ('Beamspread', 'Float', 2.5, {'min': 0, 'max': 30, 'label': 'Beam spread deg (cone half angle)'}),
    ('Coresize', 'Float', 6.0, {'min': 0.3, 'max': 100, 'label': 'Source / laser width px'}),
    ('Length', 'Float', 1.2, {'min': 0.05, 'max': 10, 'label': 'Falloff length (screen heights)'}),
    ('Beamphase', 'Float', 0.08, {'min': -1, 'max': 1, 'label': 'Sweep phase per beam'}),
    ('Gap', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Fan groups apart (x width)'}),
    ('Originy', 'Float', 0.0, {'min': -0.5, 'max': 1.5, 'label': 'Source height (0 floor, 1 truss)'}),
    ('Morph', 'Float', 0.35, {'min': 0.01, 'max': 4, 'label': 'Beat re-arrange ease s'}),
    ('Flare', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Source flare'}),
    ('Haze', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Haze (smoke in the beams)'}),
    ('Hazescale', 'Float', 3.0, {'min': 0.2, 'max': 20, 'label': 'Haze scale'}),
    ('Hazespeed', 'Float', 0.15, {'min': -2, 'max': 2, 'label': 'Haze rise /s'}),
    ('Rotspeedb', 'Float', 20.0, {'min': -360, 'max': 360, 'label': 'Tunnel rotate deg/s'}),
    ('Waveamp', 'Float', 0.04, {'min': 0, 'max': 0.5, 'label': 'Wave amplitude (screen heights)'}),
    ('Wavefreq', 'Float', 1.5, {'min': 0, 'max': 16, 'label': 'Waves per width'}),
    ('Wavespeed', 'Float', 0.4, {'min': -8, 'max': 8, 'label': 'Wave speed /s'}),
])]
DEFAULTS = {'Palette': 'shared', 'Palsource': 'cyan_magenta', 'Palmode': 'gradient', 'Blend': 'add'}
PANEL_PAGES = ['Beams', 'Drive', 'Colour', 'Palette']
PRESETS = [
    (1, 'floor fans', {'Amount': 1.0, 'Mode': 'fans', 'Style': 'beam', 'Count': 12, 'Fan': 80.0, 'Beamspread': 1.2,
                       'Coresize': 4.0, 'Palsource': 'cyan_magenta'}),
    (2, 'moving heads', {'Amount': 1.0, 'Mode': 'cones', 'Style': 'beam', 'Count': 7, 'Originy': 1.02,
                         'Tilt': 30.0, 'Sweep': 18.0, 'Beamspread': 4.0, 'Coresize': 10.0, 'Beatevery': 2.0,
                         'Palsource': 'fire', 'Palmode': 'gradient'}),
    (3, 'laser tunnel', {'Amount': 1.0, 'Mode': 'tunnel', 'Style': 'laser', 'Count': 24, 'Coresize': 1.5,
                         'Length': 0.8, 'Flare': 1.0, 'Palsource': 'neon_trio', 'Palmode': 'steps', 'Haze': 0.6}),
    (4, 'laser sheets', {'Amount': 1.0, 'Mode': 'waves', 'Style': 'laser', 'Count': 9, 'Coresize': 1.8,
                         'Flare': 0.0, 'Palsource': 'neon_trio', 'Palmode': 'gradient', 'Haze': 0.35}),
    (5, 'beat fans', {'Amount': 1.0, 'Mode': 'fans', 'Style': 'laser', 'Count': 16, 'Coresize': 2.0, 'Fan': 70.0,
                      'Tilt': 35.0, 'Beatevery': 1.0, 'Beatgain': 0.6, 'Morph': 0.15, 'Palsource': 'acid',
                      'Palmode': 'steps', 'Paldrive': 'bpm_step', 'Palevery': 4.0}),
]
CHECK = {'t': 1.0, 'beats': 2.5}          # beat 2.5: Beatevery presets show a later step (freeze: Bpm 0 = settled)
UNIFORMS = [('uM0', ['{Mode#}', '{Style#}', '{Count}', '{Bright}']),
            ('uM1', ['math.radians({Fan})', 'math.radians({Tilt})', 'math.radians({Sweep})', '{Sweepspeed}']),
            ('uM2', ['math.radians({Beamspread})', '{Coresize}', '{Length}', '{Beamphase}']),
            ('uM3', ['{Gap}', '{Originy}', '{Morph}', '{Flare}']),
            ('uM4', ['{Haze}', '{Hazescale}', '{Hazespeed}', '{Waveamp}']),
            ('uM5', ['{Wavefreq}', '{Wavespeed}', 'math.radians({Rotspeedb})', '0'])]

GLSL = """
float bm_h(int s, int n) { return h2(ivec2(s, n), SEED ^ 0xBEA3u); }
float bm_beam(vec2 P, vec2 o, float ang, float H, int style) {
    vec2 dir = vec2(cos(ang), sin(ang)), d = P - o;
    float al = dot(d, dir);
    if (al <= 0.0) return 0.0;
    float pe = abs(d.x * dir.y - d.y * dir.x), fall = exp(-al / max(uM2.z * H, 1.0)), w = uM2.y;
    if (style == 1) {
        float x = pe / w;
        return fall * (exp(-x * x) + 0.25 / (1.0 + x * x / 16.0));
    }
    float x = pe / max(w + al * tan(uM2.x), 1e-3);
    return x > 4.0 ? 0.0 : fall * exp(-2.0 * x * x);
}
float bm_flare(vec2 P, vec2 o) { vec2 d = P - o; float w = 6.0 * uM2.y; return uM3.w * w * w / (dot(d, d) + w * w); }
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int mode = int(uM0.x + 0.5), style = int(uM0.y + 0.5), n = clamp(int(uM0.z + 0.5), 1, 32);
    float H = RES.y, W = RES.x;
    int st = int(STEP);
    float e = smooth01(AGE / max(uM3.z, 1e-3));
    float tilt = mix(uM1.y * (2.0 * bm_h(st - 1, 1) - 1.0), uM1.y * (2.0 * bm_h(st, 1) - 1.0), e);
    float fan = mix(uM1.x * (0.4 + 0.6 * bm_h(st - 1, 2)), uM1.x * (0.4 + 0.6 * bm_h(st, 2)), e);
    float br = uM0.w * (1.0 + ENV) * (1.0 + LEVEL);
    float V = 0.0, KK = 0.0, Vf = 0.0, Kf = 0.0;
    for (int i = 0; i < 32; i++) {
        if (i >= n) break;
        float fi = float(i), ki = (fi + 0.5) / float(n), I = 0.0, F = 0.0;
        if (mode == 3) {
            float y = (fi + 0.5) / float(n) * H + uM4.w * H * sin(TAU * (P.x / W * uM5.x + T * uM5.y + fi * uM2.w));
            float pe = abs(P.y - y), x = pe / uM2.y;
            I = style == 1 ? exp(-x * x) + 0.25 / (1.0 + x * x / 16.0) : (x > 4.0 ? 0.0 : exp(-2.0 * x * x));
        } else {
            vec2 o; float ang;
            float sw = uM1.z * sin(TAU * (T * uM1.w + fi * uM2.w));
            if (mode == 0) {
                int m = (n + 1) / 2, j = i / 2;
                float fr = m > 1 ? float(j) / float(m - 1) - 0.5 : 0.0;
                ang = 0.5 * PI - tilt + fr * fan + sw;
                o = vec2((0.5 - 0.5 * uM3.x) * W, uM3.y * H);
                if ((i & 1) == 1) { ang = PI - ang; o.x = (0.5 + 0.5 * uM3.x) * W; }
            } else if (mode == 1) {
                float ti = mix(uM1.y * (2.0 * bm_h(st - 1, 10 + i) - 1.0), uM1.y * (2.0 * bm_h(st, 10 + i) - 1.0), e);
                ang = -0.5 * PI + ti + sw;
                o = vec2((fi + 0.5) / float(n) * W, uM3.y * H);
            } else {
                ang = TAU * fi / float(n) + uM5.z * T + tilt;
                o = 0.5 * RES;
            }
            I = bm_beam(P, o, ang, H, style);
            F = (mode == 2 && i > 0) ? 0.0 : bm_flare(P, o);   // the tunnel's spokes share one source
        }
        V += I; KK += I * ki; Vf += F; Kf += F * ki;
    }
    // haze is a common factor of the beams: fbm only where a beam is (dark pixels skip it)
    float hz = V > 1e-5 ? mix(1.0, 0.25 + 1.5 * fbm(P / H * uM4.y + vec2(0.0, -T * uM4.z), SEED, 3), uM4.x) : 1.0;
    V = (V * hz + Vf) * br; KK = (KK * hz + Kf) * br;
    v = V;
    k = V > 1e-6 ? KK / V : 0.0;
}
"""
