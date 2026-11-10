# gen_pattern_droste - GEN_pattern warp module 'droste' (FX5 G16, Escher / Lenstra Droste): log-polar map of the
# slot's input, rotated by alpha = atan(Strands ln(Ratio) / 2pi) x Twist and scaled by 1/cos(alpha) so one turn
# lands on the copy Ratio x smaller, wrapped every ln(Ratio): the picture spirals into itself forever. Zoomspeed =
# copies per second inward, Radius = the inner copy's radius (screen heights). Beat pulse -> quarter-copy zoom kick,
# audio -> rotation + radius. Twist 0 = a straight infinite zoom tunnel. Mirror: gen_pattern_logic.droste_src.
MODULE = 'droste'
KIND = 'warp'
BLURB = 'Droste spiral (log-polar, Escher): the input spirals into itself; Twist 0 = zoom tunnel.'

PAGES = [('Droste', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Ratio', 'Float', 4.0, {'min': 1.1, 'max': 20, 'label': 'Copy ratio'}),
    ('Strands', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Strands (spiral arms)'}),
    ('Twist', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Twist (0 = tunnel)'}),
    ('Zoomspeed', 'Float', 0.15, {'min': -2, 'max': 2, 'label': 'Zoom copies/s'}),
    ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate deg'}),
    ('Rotspeed', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate deg/s'}),
    ('Radius', 'Float', 0.12, {'min': 0.01, 'max': 1, 'label': 'Inner radius (screen h)'}),
    ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
    ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
    ('Srcx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Source x'}),
    ('Srcy', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Source y'}),
])]
DEFAULTS = {}
PANEL_PAGES = ['Droste', 'Drive']
PRESETS = [
    (1, 'escher', {'Amount': 1.0, 'Ratio': 4.0, 'Strands': 1.0, 'Twist': 1.0, 'Zoomspeed': 0.15, 'Radius': 0.12}),
    (2, 'tunnel', {'Amount': 1.0, 'Ratio': 3.0, 'Twist': 0.0, 'Zoomspeed': 0.3, 'Radius': 0.1}),
    (3, 'double', {'Amount': 1.0, 'Ratio': 6.0, 'Strands': 2.0, 'Twist': 1.0, 'Zoomspeed': 0.1, 'Rotspeed': 8.0}),
    (4, 'beat dive', {'Amount': 1.0, 'Ratio': 4.0, 'Strands': 1.0, 'Zoomspeed': 0.0, 'Beatevery': 1.0,
                      'Beatgain': 1.0, 'Beatdecay': 0.5}),
]
UNIFORMS = [('uM0', ['{Ratio}', '{Strands}', '{Twist}', '{Zoomspeed}']),
            ('uM1', ['math.radians({Rotate})', 'math.radians({Rotspeed})', '{Radius}', '{Centerx}']),
            ('uM2', ['{Centery}', '{Srcx}', '{Srcy}', '0'])]

GLSL = """
vec4 warp(vec2 P, vec4 c) {
    float ratio = max(uM0.x, 1.0001), twist = uM0.z;
    float rotr = uM1.x + uM1.y * T + LEVEL * 0.5, R0 = uM1.z * (1.0 + 0.3 * LEVEL);
    vec2 z = vec2((P.x - uM1.w * RES.x) / RES.y, (P.y - uM2.x * RES.y) / RES.y);
    float r = max(length(z), 1e-6);
    vec2 w = vec2(log(r / max(R0, 1e-6)), atan(z.y, z.x));
    float L = log(ratio);
    float al = atan(uM0.y * L / TAU) * twist, f = 1.0 / cos(al);   // 1/cos: one turn = (-Strands L, 2pi), seamless (live fix)
    w = f * vec2(w.x * cos(al) - w.y * sin(al), w.x * sin(al) + w.y * cos(al));
    w.x = mod(w.x - (uM0.w * T + 0.25 * ENV) * L, L);
    w.y += rotr;
    vec2 u = exp(w.x) * R0 * vec2(cos(w.y), sin(w.y));
    return texture(sTD2DInputs[0], vec2(mirror1(uM2.y + u.x * RES.y / RES.x), mirror1(uM2.z + u.y)));
}
"""
