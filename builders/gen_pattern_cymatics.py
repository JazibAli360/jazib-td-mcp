# gen_pattern_cymatics - GEN_pattern module 'cymatics' (FX5 G27): Chladni plate nodal patterns
# cos(n pi x) cos(m pi y) -/+ cos(m pi x) cos(n pi y), a 3-wave triangular plate and a radial (Bessel-like) plate;
# sand = exp(-(f / Width)^2) with per-pixel grains. Modes: manual N / M (+ Wobble) or a 12-mode list stepped by the
# beat, morphing over Morph s. Audio -> sand line width, beat pulse -> brightness. Mirror: gen_cymatics. ASCII only.
MODULE = 'cymatics'
KIND = 'gen'
BLURB = 'Chladni plate sand: nodal lines of standing waves; modes manual or stepped on the beat.'

PAGES = [('Cymatics', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Plate', 'Menu', 'square', {'names': ['square', 'squaresum', 'triangle', 'radial'],
                                 'labels': ['Square (n,m - m,n)', 'Square (n,m + m,n)', 'Triangular', 'Radial']}),
    ('Render', 'Menu', 'sand', {'names': ['sand', 'field'], 'labels': ['Sand (nodal lines)', 'Field']}),
    ('N', 'Float', 3.0, {'min': 1, 'max': 12, 'label': 'Mode n'}),
    ('M', 'Float', 5.0, {'min': 1, 'max': 12, 'label': 'Mode m'}),
    ('Modesource', 'Menu', 'manual', {'names': ['manual', 'beat'], 'labels': ['Manual n / m', 'Beat list (12 modes)']}),
    ('Morph', 'Float', 0.6, {'min': 0.01, 'max': 4, 'label': 'Morph s'}),
    ('Width', 'Float', 0.08, {'min': 0.005, 'max': 1, 'label': 'Sand width'}),
    ('Grain', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Grain'}),
    ('Grainsize', 'Float', 2.0, {'min': 1, 'max': 12, 'label': 'Grain px'}),
    ('Wobble', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Mode wobble'}),
])]
DEFAULTS = {'Scale': 2.0, 'Palette': 0, 'Colorar': 0.95, 'Colorag': 0.88, 'Colorab': 0.7}
PANEL_PAGES = ['Cymatics', 'Drive', 'Space', 'Colour']
PRESETS = [
    (1, 'sand plate', {'Amount': 1.0, 'Plate': 0, 'Render': 0, 'N': 3.0, 'M': 5.0, 'Modesource': 0, 'Width': 0.08,
                       'Grain': 0.5}),
    (2, 'beat modes', {'Amount': 1.0, 'Plate': 0, 'Render': 0, 'Modesource': 1, 'Morph': 0.5, 'Beatevery': 2.0,
                       'Beatgain': 0.6, 'Width': 0.1}),
    (3, 'radial', {'Amount': 1.0, 'Plate': 3, 'Render': 0, 'N': 4.0, 'M': 6.0, 'Width': 0.12, 'Grain': 0.3}),
    (4, 'field', {'Amount': 1.0, 'Plate': 1, 'Render': 1, 'N': 2.0, 'M': 7.0, 'Palette': 2}),
    (5, 'wobble', {'Amount': 1.0, 'Plate': 2, 'Render': 0, 'N': 3.0, 'M': 4.0, 'Wobble': 0.4, 'Width': 0.1,
                   'Audiogain': 1.0}),
]
UNIFORMS = [('uM0', ['{Plate#}', '{Render#}', '{N}', '{M}']),
            ('uM1', ['{Modesource#}', '{Morph}', '{Width}', '{Grain}']),
            ('uM2', ['{Grainsize}', '{Wobble}', '0', '0'])]

GLSL = """
const ivec2 CYM[12] = ivec2[12](ivec2(1, 2), ivec2(2, 3), ivec2(1, 4), ivec2(3, 4), ivec2(2, 5), ivec2(3, 5),
                                ivec2(1, 6), ivec2(4, 5), ivec2(3, 7), ivec2(5, 6), ivec2(2, 7), ivec2(4, 7));
float plate(int pl, float n, float m, vec2 p) {
    if (pl == 0) return cos(n * PI * p.x) * cos(m * PI * p.y) - cos(m * PI * p.x) * cos(n * PI * p.y);
    if (pl == 1) return cos(n * PI * p.x) * cos(m * PI * p.y) + cos(m * PI * p.x) * cos(n * PI * p.y);
    if (pl == 2) {
        float f = 0.0;
        for (int j = 0; j < 3; j++) {
            float a = float(j) * TAU / 3.0, d = p.x * cos(a) + p.y * sin(a);
            f += cos(n * PI * d) - cos(m * PI * d);
        }
        return f * 0.6666667;
    }
    return 2.0 * cos(n * PI * length(p)) * cos(m * atan(p.y, p.x));
}
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int pl = int(uM0.x + 0.5), render = int(uM0.y + 0.5);
    float width = uM1.z * (1.0 + LEVEL), f;
    if (int(uM1.x + 0.5) == 1) {
        int st = int(STEP);
        int i1 = st - 12 * int(floor(float(st) / 12.0)), i0 = (st - 1) - 12 * int(floor(float(st - 1) / 12.0));
        float w = smooth01(AGE / max(uM1.y, 1e-3));
        f = mix(plate(pl, float(CYM[i0].x), float(CYM[i0].y), q), plate(pl, float(CYM[i1].x), float(CYM[i1].y), q), w);
    } else f = plate(pl, uM0.z + uM2.y * sin(T * 0.7), uM0.w + uM2.y * sin(T * 0.53 + 1.0), q);
    k = 0.5 + 0.25 * f;
    if (render == 1) { v = 0.5 + 0.25 * f; return; }
    float r = f / max(width, 1e-4);
    v = exp(-r * r) * (1.0 + ENV);
    if (uM1.w > 0.0) {
        float gs = max(uM2.x, 1.0);
        float g = h2(ivec2(floor(P / gs)), SEED ^ 0x77u) < v ? 1.0 : 0.0;
        v = mix(v, g, uM1.w);
    }
}
"""
