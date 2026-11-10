# gen_pattern_wallpaper - GEN_pattern module 'wallpaper' (FX5 G07): quasicrystal (N plane waves at pi/N angles),
# Islamic star patterns by Hankin's polygons-in-contact (rays from each edge midpoint at the contact angle Theta,
# folded into the p4m square / p6m hexagon fundamental domain), and ring motifs on p4m / p6m. Audio -> line width,
# beat pulse -> Theta (+15 deg) and quasicrystal phase kick. Mirror: gen_pattern_logic.gen_wallpaper. ASCII only.
MODULE = 'wallpaper'
KIND = 'gen'
BLURB = 'Quasicrystal waves, Hankin star patterns (8- / 12-fold), p4m / p6m ring motifs.'
MODES = ['quasi', 'star8', 'star12', 'rings4', 'rings6']

PAGES = [('Wallpaper', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Mode', 'Menu', 'quasi', {'names': MODES, 'labels': ['Quasicrystal', 'Star 8-fold (square)',
                                                          'Star 12-fold (hex)', 'Rings p4m', 'Rings p6m']}),
    ('Waves', 'Int', 7, {'min': 3, 'max': 16, 'label': 'Waves N (quasicrystal)'}),
    ('Phasespeed', 'Float', 0.1, {'min': -2, 'max': 2, 'label': 'Phase speed /s'}),
    ('Bands', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Contour bands (0 smooth)'}),
    ('Theta', 'Float', 60.0, {'min': 0, 'max': 90, 'label': 'Star contact angle deg'}),
    ('Linewidth', 'Float', 0.04, {'min': 0, 'max': 0.3, 'label': 'Line width (cell)'}),
    ('Ringradius', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Ring radius (cell)'}),
])]
DEFAULTS = {'Scale': 6.0, 'Palette': 5}
PANEL_PAGES = ['Wallpaper', 'Drive', 'Space', 'Colour']
PRESETS = [
    (1, 'quasi 7', {'Amount': 1.0, 'Mode': 0, 'Waves': 7, 'Phasespeed': 0.1, 'Bands': 0.0, 'Scale': 10.0,
                    'Palette': 2}),
    (2, 'quasi bands', {'Amount': 1.0, 'Mode': 0, 'Waves': 5, 'Phasespeed': 0.15, 'Bands': 3.0, 'Scale': 8.0,
                        'Palette': 0}),
    (3, 'star 8', {'Amount': 1.0, 'Mode': 1, 'Theta': 67.5, 'Linewidth': 0.05, 'Scale': 5.0, 'Palette': 0,
                   'Rotspeed': 2.0}),
    (4, 'star 12', {'Amount': 1.0, 'Mode': 2, 'Theta': 60.0, 'Linewidth': 0.04, 'Scale': 5.0, 'Palette': 0}),
    (5, 'rings beat', {'Amount': 1.0, 'Mode': 4, 'Ringradius': 0.45, 'Linewidth': 0.05, 'Scale': 6.0,
                       'Beatevery': 1.0, 'Beatgain': 1.0, 'Audiogain': 1.0, 'Palette': 6}),
]
UNIFORMS = [('uM0', ['{Mode#}', '{Waves}', '{Phasespeed}', '{Bands}']),
            ('uM1', ['math.radians({Theta})', '{Linewidth}', '{Ringradius}', '0'])]

GLSL = """
vec2 fold_sq(vec2 g) { g = abs(g); return g.y > g.x ? g.yx : g; }
vec2 fold_hex(vec2 u) {
    const vec2 lat = vec2(1.0, 1.7320508);
    vec2 a = mod(u, lat) - lat * 0.5, b = mod(u - lat * 0.5, lat) - lat * 0.5;
    vec2 g = dot(a, a) < dot(b, b) ? a : b;
    float r = length(g);
    float a3 = abs(mod(atan(g.y, g.x) + PI / 6.0, PI / 3.0) - PI / 6.0);
    return r * vec2(cos(a3), sin(a3));
}
void gen(vec2 q, vec2 P, vec4 src, out float v, out float k) {
    int mode = int(uM0.x + 0.5), n = max(int(uM0.y + 0.5), 1);
    float theta = uM1.x + ENV * 0.2617994, lw = uM1.y * (1.0 + LEVEL), rr = uM1.z;
    if (mode == 0) {
        float ph = uM0.z * T + ENV, s = 0.0;
        for (int i = 0; i < 16; i++) {
            if (i >= n) break;
            float a = PI * float(i) / float(n);
            s += cos(TAU * (q.x * cos(a) + q.y * sin(a) + ph));
        }
        float v0 = 0.5 + 0.5 * s / float(n);
        v = uM0.w > 0.0 ? 0.5 + 0.5 * cos(TAU * v0 * uM0.w) : v0;
        k = v0;
        return;
    }
    vec2 g = (mode == 1 || mode == 3) ? fold_sq(q - floor(q) - 0.5) : fold_hex(q);
    k = clamp(length(g) * 1.41421356, 0.0, 1.0);
    if (mode == 1 || mode == 2) {
        vec2 d = vec2(-sin(theta), cos(theta)), e = g - vec2(0.5, 0.0);
        v = stroke(abs(e.x * d.y - e.y * d.x), lw, PX);
        return;
    }
    float dd = mode == 3 ? min(abs(length(g) - rr), abs(length(g - vec2(0.5, 0.5)) - rr))
                         : min(abs(length(g) - rr), abs(length(g - vec2(0.5, 0.28867513)) - rr * 0.57735));
    v = stroke(dd, lw, PX);
}
"""
