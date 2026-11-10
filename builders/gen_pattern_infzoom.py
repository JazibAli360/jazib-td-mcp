# gen_pattern_infzoom - GEN_pattern warp module 'infzoom' (FX4 G-INFZOOM, Arena "Infinite Zoom"): Layers copies of
# the slot's input at magnifications Zoomstep^(i + f - Layers/2), f = fract(Zoomspeed t), each faded by
# sin(pi (i + f) / Layers)^(2 Fade): a seamless endless zoom in one pass (no feedback, so no stale history after a
# bypass). Layerrot turns each copy, Rotspeed turns all. Beat pulse -> half-layer zoom kick. Negative Zoomspeed
# zooms out. Mirror: gen_pattern_logic.infzoom_src. ASCII only.
MODULE = 'infzoom'
KIND = 'warp'
BLURB = 'Endless zoom: Layers cross-faded copies of the input at Zoomstep ratios, one pass.'

PAGES = [('Infzoom', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Layers', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Layers'}),
    ('Zoomstep', 'Float', 2.0, {'min': 1.05, 'max': 8, 'label': 'Zoom per layer'}),
    ('Zoomspeed', 'Float', 0.2, {'min': -2, 'max': 2, 'label': 'Layers/s'}),
    ('Layerrot', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate per layer deg'}),
    ('Rotspeed', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate deg/s'}),
    ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
    ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
    ('Fade', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Fade sharpness'}),
])]
DEFAULTS = {}
PANEL_PAGES = ['Infzoom', 'Drive']
PRESETS = [
    (1, 'dive', {'Amount': 1.0, 'Layers': 4, 'Zoomstep': 2.0, 'Zoomspeed': 0.2, 'Layerrot': 0.0}),
    (2, 'spiral', {'Amount': 1.0, 'Layers': 5, 'Zoomstep': 1.8, 'Zoomspeed': 0.25, 'Layerrot': 30.0}),
    (3, 'out', {'Amount': 1.0, 'Layers': 4, 'Zoomstep': 2.0, 'Zoomspeed': -0.2}),
    (4, 'beat', {'Amount': 1.0, 'Layers': 4, 'Zoomstep': 2.5, 'Zoomspeed': 0.05, 'Beatevery': 1.0, 'Beatgain': 1.0,
                 'Beatdecay': 0.4}),
]
UNIFORMS = [('uM0', ['{Layers}', '{Zoomstep}', '{Zoomspeed}', 'math.radians({Layerrot})']),
            ('uM1', ['{Centerx}', '{Centery}', '{Fade}', 'math.radians({Rotspeed})'])]

GLSL = """
vec4 warp(vec2 P, vec4 c) {
    int n = max(int(uM0.x + 0.5), 1);
    float zstep = max(uM0.y, 1.0001), f = fract(uM0.z * T + 0.5 * ENV), asp = RES.x / RES.y;
    vec2 p = vec2((P.x / RES.x - uM1.x) * asp, P.y / RES.y - uM1.y);
    vec4 acc = vec4(0.0);
    float ws = 0.0;
    for (int i = 0; i < 8; i++) {
        if (i >= n) break;
        float e = (float(i) + f) / float(n);
        float mag = pow(zstep, float(i) + f - float(n) * 0.5);
        vec2 u = rot2(p / mag, (float(i) + f) * uM0.w + uM1.w * T);
        float w = pow(max(sin(PI * e), 0.0), max(2.0 * uM1.z, 1e-3));
        acc += texture(sTD2DInputs[0], vec2(mirror1(uM1.x + u.x / asp), mirror1(uM1.y + u.y))) * w;
        ws += w;
    }
    return acc / max(ws, 1e-6);
}
"""
