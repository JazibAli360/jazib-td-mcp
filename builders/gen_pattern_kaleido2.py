# gen_pattern_kaleido2 - GEN_pattern warp module 'kaleido2' (FX5 G16 / FX4 G-KALEIDO2): the td-port / StageLab
# Kaleido folds (wedge, mirror squares, hex 12-fold; td-port/kaleido/kaleido.frag) plus diamonds and two fly's-eye
# lens grids (hex / rect: each cell a lens onto the source, Lenszoom, Cellshift parallax, Vignette). Remaps the slot's
# input (put it after a generator, or over the background picture). Beat pulse -> +30 deg rotation kick, audio ->
# zoom. Mirror: gen_pattern_logic.kaleido2_src. ASCII only.
MODULE = 'kaleido2'
KIND = 'warp'
BLURB = 'Kaleidoscope folds of the slot input: wedge / squares / diamonds / hex12 / fly-eye hex / fly-eye rect.'
MODES = ['wedge', 'squares', 'diamonds', 'hex12', 'flyhex', 'flyrect']

PAGES = [('Kaleido2', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Mode', 'Menu', 'wedge', {'names': MODES, 'labels': ['Wedge (polar)', 'Mirror squares', 'Diamonds',
                                                          'Hex 12-fold', "Fly's eye hex", "Fly's eye rect"]}),
    ('Segments', 'Float', 6.0, {'min': 1, 'max': 32, 'label': 'Segments / cells'}),
    ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate deg'}),
    ('Rotspeed', 'Float', 10.0, {'min': -180, 'max': 180, 'label': 'Rotate deg/s'}),
    ('Zoom', 'Float', 1.0, {'min': 0.1, 'max': 8, 'label': 'Zoom'}),
    ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
    ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
    ('Srcx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Source x'}),
    ('Srcy', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Source y'}),
    ('Srcrot', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Source rotate deg'}),
    ('Lenszoom', 'Float', 1.5, {'min': 0.1, 'max': 8, 'label': "Fly's eye lens zoom"}),
    ('Cellshift', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Cell parallax'}),
    ('Vignette', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Cell vignette'}),
])]
DEFAULTS = {}
PANEL_PAGES = ['Kaleido2', 'Drive']
PRESETS = [
    (1, 'mandala', {'Amount': 1.0, 'Mode': 0, 'Segments': 8.0, 'Rotspeed': 6.0, 'Zoom': 1.0}),
    (2, 'tiles', {'Amount': 1.0, 'Mode': 1, 'Segments': 3.0, 'Rotspeed': 0.0, 'Zoom': 1.0}),
    (3, 'hex', {'Amount': 1.0, 'Mode': 3, 'Segments': 4.0, 'Rotspeed': 4.0, 'Zoom': 1.2}),
    (4, 'flys eye', {'Amount': 1.0, 'Mode': 4, 'Segments': 6.0, 'Rotspeed': 0.0, 'Lenszoom': 1.6, 'Vignette': 0.5,
                     'Cellshift': 0.15}),
    (5, 'beat spin', {'Amount': 1.0, 'Mode': 0, 'Segments': 12.0, 'Rotspeed': 0.0, 'Beatevery': 1.0,
                      'Beatgain': 1.0, 'Beatdecay': 0.3}),
]
UNIFORMS = [('uM0', ['{Mode#}', '{Segments}', 'math.radians({Rotate})', '{Zoom}']),
            ('uM1', ['{Centerx}', '{Centery}', '0', 'math.radians({Rotspeed})']),
            ('uM2', ['{Srcx}', '{Srcy}', 'math.radians({Srcrot})', '{Lenszoom}']),
            ('uM3', ['{Cellshift}', '{Vignette}', '0', '0'])]

GLSL = """
vec4 warp(vec2 P, vec4 c) {
    int mode = int(uM0.x + 0.5);
    float n = max(uM0.y, 1.0);
    float rotr = uM0.z + uM1.w * T + ENV * 0.5235988, zoom = uM0.w * (1.0 + 0.5 * LEVEL);
    float asp = RES.x / RES.y;
    vec2 p = vec2((P.x / RES.x - uM1.x) * asp, P.y / RES.y - uM1.y);
    float r = length(p), gain = 1.0;
    vec2 s;
    if (mode == 0) {
        float sector = TAU / n, th = atan(p.y, p.x) - rotr;
        float t = abs(mod(th, sector) - 0.5 * sector);
        s = r * vec2(cos(t), sin(t));
    } else if (mode == 1 || mode == 2) {
        vec2 u = rot2(p, -(rotr + (mode == 2 ? 0.78539816 : 0.0))) * n;
        s = abs(mod(u + 1.0, 2.0) - 1.0) / n;
    } else {
        float hn = n * 0.5;
        vec2 u = rot2(p, -rotr) * hn, g, cc;
        float rr;
        if (mode == 5) { g = mod(u, 1.0) - 0.5; cc = u - g; rr = max(abs(g.x), abs(g.y)) * 2.0; }
        else {
            const vec2 lat = vec2(1.0, 1.7320508);
            vec2 a = mod(u, lat) - lat * 0.5, b = mod(u - lat * 0.5, lat) - lat * 0.5;
            g = dot(a, a) < dot(b, b) ? a : b; cc = u - g; rr = length(g) * 2.0;
        }
        if (mode == 3) {
            float t = abs(mod(atan(g.y, g.x), PI / 3.0) - PI / 6.0);
            s = length(g) * vec2(cos(t), sin(t)) / hn;
        } else {
            s = (g / max(uM2.w, 1e-3) + cc * uM3.x) / hn;
            gain = 1.0 - uM3.y * smooth01(rr);
        }
    }
    s = rot2(s / max(zoom, 1e-3), uM2.z);
    vec4 o = texture(sTD2DInputs[0], vec2(mirror1(uM2.x + s.x / asp), mirror1(uM2.y + s.y)));
    return vec4(o.rgb * gain, o.a);
}
"""
