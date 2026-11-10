# gen_pattern_moltenchrome - GEN_pattern module 'moltenchrome' (FX7b TC-23 "Molten chrome (2D liquid metal)",
# instant infinite "Molten Surge" / MechBullRodeo "Liquid Metal in 10 nodes" looks; BUILD_PLAN_27OCT lane A). One
# pass, no feedback: a height field from an iterated sine domain warp (Iter steps, Warp strength, Flow speed; Surge =
# slow swells of the warp so the surface surges, creases and collapses), normals by forward differences (3 height
# evaluations), mirror reflection of the view ray into a procedural studio environment: sky / floor gradient, Lights
# soft strips sliding with Lightspeed (the travelling highlights), a sharp specular sun, Fresnel rim. Output value =
# reflected light, palette coordinate = reflected ray height (sky vs floor tint): Colour A -> B duo = silver, Gold /
# shared palettes = gold or neon chrome. Space page: Scale (blob size), Rotate, Drift. Audio -> warp, beat pulse ->
# warp kick. Mirror: gen_pattern_logic.gen_moltenchrome. ASCII only.
MODULE = 'moltenchrome'
KIND = 'gen'
PAL = True
BLURB = 'Molten chrome: iterated sine-warp height field, normals, reflection of a studio env with sliding strips.'

PAGES = [('Chrome', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Warp', 'Float', 0.7, {'min': 0, 'max': 3, 'label': 'Warp strength'}),
    ('Flow', 'Float', 0.25, {'min': -4, 'max': 4, 'label': 'Flow speed'}),
    ('Iter', 'Int', 5, {'min': 1, 'max': 8, 'label': 'Warp steps (1-8)'}),
    ('Surge', 'Float', 0.4, {'min': 0, 'max': 2, 'label': 'Surge (warp swells)'}),
    ('Surgerate', 'Float', 0.12, {'min': 0, 'max': 2, 'label': 'Surge Hz'}),
    ('Bump', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Bump (normal strength)'}),
    ('Lights', 'Int', 3, {'min': 0, 'max': 4, 'label': 'Light strips (0-4)'}),
    ('Stripw', 'Float', 0.12, {'min': 0.01, 'max': 1, 'label': 'Strip width'}),
    ('Lightspeed', 'Float', 0.08, {'min': -2, 'max': 2, 'label': 'Strip slide Hz'}),
    ('Envtilt', 'Float', 20.0, {'min': -180, 'max': 180, 'label': 'Environment tilt deg'}),
    ('Shine', 'Float', 60.0, {'min': 1, 'max': 400, 'label': 'Specular sharpness'}),
    ('Spec', 'Float', 0.8, {'min': 0, 'max': 4, 'label': 'Specular'}),
    ('Fresnel', 'Float', 0.4, {'min': 0, 'max': 2, 'label': 'Fresnel rim'}),
    ('Floor', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Floor (dark side) level'}),
    ('Sky', 'Float', 0.55, {'min': 0, 'max': 2, 'label': 'Sky level'}),
])]
DEFAULTS = {'Scale': 3.0, 'Palette': 'duo', 'Colorar': 0.97, 'Colorag': 0.98, 'Colorab': 1.0, 'Colorbr': 0.32,
            'Colorbg': 0.36, 'Colorbb': 0.44, 'Spread': 0.5, 'Blend': 'replace', 'Palsource': 'px_ramp'}
PANEL_PAGES = ['Chrome', 'Space', 'Drive', 'Colour', 'Palette']
PRESETS = [
    (1, 'liquid silver', {'Amount': 1.0}),
    (2, 'molten gold', {'Amount': 1.0, 'Palette': 'duo', 'Colorar': 1.0, 'Colorag': 0.86, 'Colorab': 0.45,
                        'Colorbr': 0.36, 'Colorbg': 0.18, 'Colorbb': 0.02, 'Warp': 0.9, 'Lights': 2, 'Sky': 0.8,
                        'Floor': 0.15}),
    (3, 'surge', {'Amount': 1.0, 'Surge': 0.8, 'Surgerate': 0.25, 'Warp': 0.85, 'Flow': 0.4, 'Bump': 0.7,
                  'Audiogain': 1.0}),
    (4, 'neon mercury', {'Amount': 1.0, 'Palette': 'shared', 'Palsource': 'cyan_magenta', 'Palmode': 'gradient',
                         'Spread': 1.0, 'Lights': 4, 'Stripw': 0.07, 'Shine': 120.0}),
    (5, 'beat ripple', {'Amount': 1.0, 'Beatevery': 1.0, 'Beatgain': 1.0, 'Beatdecay': 0.35, 'Scale': 4.0,
                        'Iter': 4, 'Lightspeed': 0.2}),
]
UNIFORMS = [('uM0', ['{Warp}', '{Flow}', '{Iter}', '{Bump}']),
            ('uM1', ['{Surge}', '{Surgerate}', '{Lights}', '{Stripw}']),
            ('uM2', ['{Lightspeed}', 'math.radians({Envtilt})', '{Shine}', '{Spec}']),
            ('uM3', ['{Fresnel}', '{Floor}', '{Sky}', '0'])]

GLSL = """
float mc_h(vec2 p, float A) {
    float t = T * uM0.y;
    int n = clamp(int(uM0.z + 0.5), 1, 8);
    for (int i = 1; i <= 8; i++) {
        if (i > n) break;
        float fi = float(i);
        p += A / fi * sin(p.yx * (1.3 * fi) + vec2(t, -t) * (0.5 + 0.17 * fi) + fi * vec2(1.7, 2.3));
    }
    return 0.25 * (sin(p.x) + sin(p.y)) + 0.5;
}
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    float A = uM0.x * (1.0 + uM1.x * sin(TAU * T * uM1.y)) * (1.0 + LEVEL) + ENV * 0.5;
    float e = PX * 1.5;
    float h0 = mc_h(q, A), hx = mc_h(q + vec2(e, 0.0), A), hy = mc_h(q + vec2(0.0, e), A);
    vec3 n = normalize(vec3(-(hx - h0) / e * uM0.w, -(hy - h0) / e * uM0.w, 1.0));
    vec3 r = vec3(2.0 * n.z * n.x, 2.0 * n.z * n.y, 2.0 * n.z * n.z - 1.0);
    vec2 re = rot2(r.xy, uM2.y);
    float env = mix(uM3.y, uM3.z, smooth01(0.5 + 0.5 * re.y));
    int nl = clamp(int(uM1.z + 0.5), 0, 4);
    for (int j = 0; j < 4; j++) {
        if (j >= nl) break;
        float fj = float(j);
        float y = (fj + 0.5) / float(nl) * 1.6 - 0.8 + 0.3 * sin(TAU * T * uM2.x + fj * 2.1);
        float d = (re.y - y) / uM1.w;
        env += 0.9 * exp(-d * d);
    }
    vec3 L = normalize(vec3(cos(TAU * T * uM2.x * 0.7), sin(TAU * T * uM2.x * 0.5), 1.5));
    env += uM2.w * pow(max(dot(r, L), 0.0), uM2.z);
    env += uM3.x * pow(1.0 - n.z, 3.0);
    v = env;
    k = 0.5 + 0.5 * re.y;
}
"""
