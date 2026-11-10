# gen_points_flame - GEN_points module 'flame' (FX5 G15): fractal flames (Draves & Reckase chaos game, maths only;
# flam3 is GPL, no code used). Every point runs Iterations chaos-game steps per frame: pick an xform by weight, apply
# its affine part, then the weighted sum of its variations (16: linear .. fisheye); the colour index moves toward the
# xform's colour (Colorspeed). Additive 1-px dust + Persist + log-density tone (Vibrancy) = the flame image. Genome A
# -> B morph (Morph + LFO + audio + beat Kick), Electric-Sheep style rotation of the flagged xforms (Xrotate deg/s),
# Variation / Varweight adds one variation to every xform live, Fold (View) = rotational symmetry.
# Genomes + fit: gen_points_logic.FL_* (offline search, 26 Oct). Mirror: gen_points_logic.flame_*. ASCII only.
_L = {}
exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/gen_points_logic.py').read(), _L)

MODULE = 'flame'
KIND = '2d'
BLURB = 'Chaos game: xform by weight -> affine -> variations; colour index; genome A -> B morph + rotation.'
GENOMES = _L['FL_NAMES']
VARS = ['linear', 'sinusoidal', 'spherical', 'swirl', 'horseshoe', 'polar', 'handkerchief', 'heart', 'disc', 'spiral',
        'hyperbolic', 'diamond', 'ex', 'julia', 'bent', 'fisheye']
COLORBY = ['colour', 'xform', 'radius', 'index']
EFFECTORS = None            # a chaos game re-converges in a few iterations (as density2d)
EPOCH = '0'
_GL = ['Ring swirl', 'Loops', 'Eye', 'Orbit', 'Leaf', 'Hook']

PAGES = [('Flame', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Genome', 'Menu', 'ringswirl', {'names': GENOMES, 'labels': _GL}),
    ('Genomeb', 'Menu', 'loops', {'names': GENOMES, 'labels': _GL}),
    ('Morph', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Morph A -> B'}),
    ('Morphlfo', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Morph LFO depth'}),
    ('Morphspeed', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Morph LFO Hz'}),
    ('Xrotate', 'Float', 6.0, {'min': -180, 'max': 180, 'label': 'Xform rotation deg/s'}),
    ('Iterations', 'Int', 2, {'min': 1, 'max': 16, 'label': 'Iterations per frame'}),
    ('Colorspeed', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Colour speed (0.5 = flam3)'}),
    ('Variation', 'Menu', 'swirl', {'names': VARS, 'labels': [v.capitalize() for v in VARS]}),
    ('Varweight', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Variation added to every xform'}),
    ('Colorby', 'Menu', 'colour', {'names': COLORBY, 'labels': ['Colour index', 'Last xform', 'Radius', 'Index']}),
    ('Kick', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Beat pulse -> morph'}),
])]
DEFAULTS = {'Count': 65536, 'Persist': 0.9, 'Tonemap': 2, 'Exposure': 0.5, 'Palette': 3, 'Respawn': 0.0,
            'Vibrancy': 1.0, 'Gamma': 1.6}
PANEL_PAGES = ['Flame', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'ring swirl', {'Genome': 0, 'Genomeb': 1, 'Morph': 0.0, 'Xrotate': 6.0, 'Palette': 3, 'Persist': 0.9,
                       'Count': 65536, 'Tonemap': 2}),
    (2, 'loops morph', {'Genome': 1, 'Genomeb': 5, 'Morphlfo': 1.0, 'Morphspeed': 0.03, 'Xrotate': 0.0,
                        'Palette': 4, 'Persist': 0.92, 'Count': 65536}),
    (3, 'eye fold', {'Genome': 2, 'Fold': 3, 'Fit': 0.9, 'Xrotate': 10.0, 'Palette': 6, 'Persist': 0.9,
                     'Count': 65536}),
    (4, 'leaf swirl var', {'Genome': 4, 'Variation': 3, 'Varweight': 0.25, 'Xrotate': 4.0, 'Palette': 5,
                           'Persist': 0.9, 'Count': 65536}),
    (5, 'hook beat', {'Genome': 5, 'Genomeb': 3, 'Kick': 1.0, 'Beatevery': 1.0, 'Beatgain': 1.0, 'Xrotate': 8.0,
                      'Palette': 7, 'Persist': 0.85, 'Count': 65536}),
]
UNIFORMS = [('uM0', ['{Genome#}', '{Genomeb#}', '{Morph}', '{Morphlfo}']),
            ('uM1', ['{Iterations}', '{Xrotate}', '{Colorspeed}', '{Morphspeed}']),
            ('uM2', ['{Kick}', '{Varweight}', '{Variation#}', '{Colorby#}'])]


def _floats(name, vals):
    return 'const float %s[%d] = float[%d](%s);\n' % (name, len(vals), len(vals), ', '.join(repr(float(v)) for v in vals))


_NG = len(_L['FL_NAMES'])
COMMON = (_floats('FL_G', _L['FL_G']) + _floats('FL_CX', [c[0] for c in _L['FL_CEN']])
          + _floats('FL_CY', [c[1] for c in _L['FL_CEN']]) + _floats('FL_EXT', _L['FL_EXT']) + """
int FL_A; int FL_B; float FL_M;
void fl_globals() {
    FL_A = clamp(int(uM0.x + 0.5), 0, %d);
    FL_B = clamp(int(uM0.y + 0.5), 0, %d);
    FL_M = clamp(uM0.z + uM0.w * (0.5 - 0.5 * cos(TAU * uM1.w * T)) + 0.5 * LEVEL + 0.25 * uM2.x * ENV, 0.0, 1.0);
}
float fl_c(int k, int q) { return mix(FL_G[(FL_A * 4 + k) * 25 + q], FL_G[(FL_B * 4 + k) * 25 + q], FL_M); }
vec3 fl_frame() {
    return vec3(mix(FL_CX[FL_A], FL_CX[FL_B], FL_M), mix(FL_CY[FL_A], FL_CY[FL_B], FL_M), mix(FL_EXT[FL_A], FL_EXT[FL_B], FL_M));
}
""" % (_NG - 1, _NG - 1))

STEP = """
const float FL_EPS = 1e-10;
vec2 fl_var(int v, vec2 p, float rw) {
    float x = p.x, y = p.y;
    float r2 = x * x + y * y, r = sqrt(r2), th = atan(x, y);
    if (v == 0) return p;
    if (v == 1) return sin(p);
    if (v == 2) return p / (r2 + FL_EPS);
    if (v == 3) return vec2(x * sin(r2) - y * cos(r2), x * cos(r2) + y * sin(r2));
    if (v == 4) return vec2((x - y) * (x + y), 2.0 * x * y) / (r + FL_EPS);
    if (v == 5) return vec2(th / PI, r - 1.0);
    if (v == 6) return r * vec2(sin(th + r), cos(th - r));
    if (v == 7) return r * vec2(sin(r * th), -cos(r * th));
    if (v == 8) return th / PI * vec2(sin(PI * r), cos(PI * r));
    if (v == 9) return vec2(cos(th) + sin(r), sin(th) - cos(r)) / (r + FL_EPS);
    if (v == 10) return vec2(sin(th) / (r + FL_EPS), r * cos(th));
    if (v == 11) return vec2(sin(th) * cos(r), cos(th) * sin(r));
    if (v == 12) { float p0 = sin(th + r), p1 = cos(th - r); p0 = p0 * p0 * p0; p1 = p1 * p1 * p1;
                   return r * vec2(p0 + p1, p0 - p1); }
    if (v == 13) { float W = rw < 0.5 ? 0.0 : PI; return sqrt(r) * vec2(cos(th * 0.5 + W), sin(th * 0.5 + W)); }
    if (v == 14) return vec2(x < 0.0 ? 2.0 * x : x, y < 0.0 ? y * 0.5 : y);
    return 2.0 / (r + 1.0) * vec2(y, x);
}
vec4 fl_iter(int i, vec4 s, uint salt, float rc, float rs) {
    float w[4];
    float tot = 0.0;
    for (int k = 0; k < 4; k++) { w[k] = fl_c(k, 0); tot += w[k]; }
    float u = rnd(i, salt) * tot;
    int jj = 3;
    float cum = 0.0;
    for (int k = 0; k < 4; k++) { cum += w[k]; if (u < cum && w[k] > 0.0) { jj = k; break; } }
    float a = fl_c(jj, 3), b = fl_c(jj, 4), d = fl_c(jj, 6), e = fl_c(jj, 7);
    if (fl_c(jj, 2) > 0.5) {
        float a2 = rc * a - rs * d, b2 = rc * b - rs * e, d2 = rs * a + rc * d, e2 = rs * b + rc * e;
        a = a2; b = b2; d = d2; e = e2;
    }
    vec2 t = vec2(a * s.x + b * s.y + fl_c(jj, 5), d * s.x + e * s.y + fl_c(jj, 8));
    float rw = rnd(i, salt + 1u);
    int vs = int(uM2.z + 0.5);
    vec2 o = vec2(0.0);
    for (int v = 0; v < 16; v++) {
        float wv = fl_c(jj, 9 + v) + (v == vs && w[jj] > 0.0 ? uM2.y : 0.0);
        if (wv != 0.0) o += wv * fl_var(v, t, rw);
    }
    float col = fl_c(jj, 1);
    return vec4(o, s.z + (col - s.z) * uM1.z, float(jj));
}
vec4 fl_seed(int i, uint salt) {
    fl_globals();
    float th = radians(uM1.y * T), rc = cos(th), rs = sin(th);
    vec4 s = vec4(rnd(i, salt) * 2.0 - 1.0, rnd(i, salt + 1u) * 2.0 - 1.0, rnd(i, salt + 2u), 0.0);
    for (int k = 0; k < 20; k++) {
        s = fl_iter(i, s, salt + 8u + 2u * uint(k), rc, rs);
        if (!(dot(s.xy, s.xy) < 1e8)) s.xy = vec2(0.1);
    }
    return s;
}
vec4 pt_seed(int i) { return fl_seed(i, 1000u); }
vec4 pt_step(int i, vec4 s, float dt) {
    if (dt <= 0.0) return s;
    fl_globals();
    float th = radians(uM1.y * T), rc = cos(th), rs = sin(th);
    int it = clamp(int(uM1.x + 0.5), 1, 16);
    for (int k = 0; k < 16; k++) { if (k >= it) break; s = fl_iter(i, s, FR * 64u + uint(2 * k + 1), rc, rs); }
    bool bad = !(dot(s.xy, s.xy) < 1e8);
    if (bad || rnd(i, FR * 4u + 3u) < uSt2.x * dt) return fl_seed(i, FR * 4u + 7u);
    return s;
}
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    fl_globals();
    vec3 f = fl_frame();
    float sc = min(ASP, 1.0) * 0.95 / max(f.z, 1e-6);
    P = vec3((s.xy - f.xy) * sc, 0.0);
    int cb = int(uM2.w + 0.5);
    float k = cb == 0 ? s.z : (cb == 1 ? s.w / 3.0 : (cb == 2 ? length(s.xy - f.xy) / max(f.z, 1e-6) : rnd(i, 5u)));
    C = vec4(ptpal(k), 1.0);
    return dot(s.xy, s.xy) < 1e8;
}
"""
