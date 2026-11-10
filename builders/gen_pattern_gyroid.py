# gen_pattern_gyroid - GEN_pattern module 'gyroid' (FX5 G29): 2D slices of triply periodic minimal surfaces
# (gyroid, Schwarz P, diamond, Neovius) with an animated slice plane; contour lines of constant pixel width (analytic
# gradient), two-colour bands, or a glow. Twist bends the slice with the radius. Audio -> iso level, beat pulse ->
# line width. Mirror: gen_pattern_logic.gen_gyroid. ASCII only.
MODULE = 'gyroid'
KIND = 'gen'
BLURB = 'TPMS slices (gyroid / Schwarz P / diamond / Neovius): contours, bands or glow.'
SURFACES = ['gyroid', 'schwarzp', 'diamond', 'neovius']

PAGES = [('Gyroid', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Surface', 'Menu', 'gyroid', {'names': SURFACES, 'labels': ['Gyroid', 'Schwarz P', 'Diamond', 'Neovius']}),
    ('Render', 'Menu', 'lines', {'names': ['lines', 'bands', 'glow'], 'labels': ['Contour lines', 'Bands', 'Glow']}),
    ('Contours', 'Float', 4.0, {'min': 0.5, 'max': 16, 'label': 'Contours'}),
    ('Linewidth', 'Float', 2.0, {'min': 0.5, 'max': 12, 'label': 'Line width px'}),
    ('Slice', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Slice z'}),
    ('Slicespeed', 'Float', 0.3, {'min': -4, 'max': 4, 'label': 'Slice speed /s'}),
    ('Twist', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Twist (z by radius)'}),
    ('Iso', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Iso level'}),
    ('Glow', 'Float', 6.0, {'min': 0.5, 'max': 40, 'label': 'Glow sharpness'}),
])]
DEFAULTS = {'Scale': 3.0, 'Palette': 6}
PANEL_PAGES = ['Gyroid', 'Drive', 'Space', 'Colour']
PRESETS = [
    (1, 'contours', {'Amount': 1.0, 'Surface': 0, 'Render': 0, 'Contours': 4.0, 'Linewidth': 3.0, 'Slicespeed': 0.3,
                     'Scale': 3.0, 'Palette': 6}),
    (2, 'cells', {'Amount': 1.0, 'Surface': 1, 'Render': 1, 'Slicespeed': 0.2, 'Scale': 4.0, 'Palette': 0}),
    (3, 'diamond glow', {'Amount': 1.0, 'Surface': 2, 'Render': 2, 'Glow': 10.0, 'Slicespeed': 0.25, 'Scale': 2.5,
                         'Palette': 4}),
    (4, 'neovius twist', {'Amount': 1.0, 'Surface': 3, 'Render': 2, 'Glow': 8.0, 'Twist': 0.6,
                          'Slicespeed': 0.15, 'Scale': 2.0, 'Palette': 0}),
    (5, 'beat lines', {'Amount': 1.0, 'Surface': 0, 'Render': 0, 'Contours': 6.0, 'Linewidth': 1.5,
                       'Beatevery': 1.0, 'Beatgain': 1.0, 'Audiogain': 1.0, 'Palette': 2}),
]
UNIFORMS = [('uM0', ['{Surface#}', '{Render#}', '{Contours}', '{Linewidth}']),
            ('uM1', ['{Slice}', '{Slicespeed}', '{Twist}', '{Iso}']),
            ('uM2', ['{Glow}', '0', '0', '0'])]

GLSL = """
vec3 tpms(int s, float x, float y, float z) {      // value, d/dx, d/dy
    float sx = sin(x), cx = cos(x), sy = sin(y), cy = cos(y), sz = sin(z), cz = cos(z);
    if (s == 0) return vec3(sx * cy + sy * cz + sz * cx, cx * cy - sz * sx, -sx * sy + cy * cz);
    if (s == 1) return vec3(cx + cy + cz, -sx, -sy);
    if (s == 2) return vec3(sx * sy * sz + sx * cy * cz + cx * sy * cz + cx * cy * sz,
                            cx * sy * sz + cx * cy * cz - sx * sy * cz - sx * cy * sz,
                            sx * cy * sz - sx * sy * cz + cx * cy * cz - cx * sy * sz);
    return vec3(3.0 * (cx + cy + cz) + 4.0 * cx * cy * cz, -3.0 * sx - 4.0 * sx * cy * cz, -3.0 * sy - 4.0 * cx * sy * cz);
}
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int surf = clamp(int(uM0.x + 0.5), 0, 3), render = int(uM0.y + 0.5);
    float cont = uM0.z, lw = uM0.w * (1.0 + 2.0 * ENV);
    float z = uM1.x + uM1.y * T + uM1.z * length(q) * TAU;
    float iso = uM1.w + LEVEL * 0.3;
    float R = surf == 0 ? 1.5 : (surf == 1 ? 3.0 : (surf == 2 ? 1.41421356 : 13.0));
    vec3 G = tpms(surf, TAU * q.x, TAU * q.y, z);
    float gpx = length(G.yz) * TAU * PX, gn = G.x / R;
    if (render == 0) {
        float c = (G.x - iso * R) / R * cont;
        float dpx = abs(c - floor(c + 0.5)) / max(cont / R * gpx, 1e-6);
        v = clamp(0.5 + (lw * 0.5 - dpx), 0.0, 1.0);
    } else if (render == 1) v = clamp(0.5 + (G.x - iso * R) / max(gpx, 1e-6), 0.0, 1.0);
    else v = exp(-uM2.x * abs(gn - iso));
    k = 0.5 + 0.5 * gn;
}
"""
