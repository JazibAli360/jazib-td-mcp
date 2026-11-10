# gen_points_attractor3d - GEN_points module 'attractor3d' (FX5 G03): strange attractor dust. Every point integrates
# dp/dt = f(p) with RK4 (Substeps per frame, raised automatically to keep the step <= the system's stable hmax), seeded
# in a blob / box around the attractor; orbit camera; colour by speed / age / depth / index. Systems: Lorenz, Thomas,
# Aizawa, Halvorsen, Dadras, Chen, Rossler, Sprott, Rabinovich-Fabrikant, four-wing; Adelta / Bdelta / Cdelta move
# a b c off the literature values; audio (Audiogain) and the beat pulse (Kick) scale them by 5 %. Shared effectors:
# push / attract / vortex / wake / kill / spawn (BO_particles adapter, Effon default off).
# Constants: gen_points_logic.A3_* (centre / extent / rate / hmax measured offline). Mirror: attractor3d_*. ASCII only.
_L = {}
exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/gen_points_logic.py').read(), _L)

MODULE = 'attractor3d'
KIND = '3d'
BLURB = 'dp/dt = f(p), RK4: Lorenz / Thomas / Aizawa / Halvorsen / Dadras / Chen / Rossler / Sprott / RF / four-wing.'
SYSTEMS = _L['A3_SYSTEMS']
COLORBY = ['speed', 'age', 'depth', 'index']
EFFECTORS = 'particles'
EPOCH = '{System#}'          # a new system re-seeds every point

PAGES = [('Attractor', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('System', 'Menu', 'thomas', {'names': SYSTEMS, 'labels': ['Lorenz', 'Thomas', 'Aizawa', 'Halvorsen', 'Dadras',
                                                              'Chen', 'Rossler', 'Sprott', 'Rabinovich-Fabrikant',
                                                              'Four-wing']}),
    ('Adelta', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'a offset'}),
    ('Bdelta', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'b offset'}),
    ('Cdelta', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'c offset'}),
    ('Rate', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Rate (x the system default)'}),
    ('Substeps', 'Int', 2, {'min': 1, 'max': 16, 'label': 'RK4 substeps (min)'}),
    ('Seedmode', 'Menu', 'blob', {'names': ['blob', 'box'], 'labels': ['Blob (ribbons)', 'Box (dust)']}),
    ('Seedsize', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Seed size (x extent)'}),
    ('Fadein', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Fade in s (after spawn)'}),
    ('Worldsize', 'Float', 1.0, {'min': 0.1, 'max': 4, 'label': 'Size (world)'}),
    ('Colorby', 'Menu', 'speed', {'names': COLORBY, 'labels': ['Speed', 'Age', 'Depth', 'Index']}),
    ('Colorscale', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Colour scale'}),
    ('Kick', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Beat pulse -> params'}),
])]
DEFAULTS = {'Count': 65536, 'Persist': 0.6, 'Tonemap': 0, 'Palette': 0, 'Respawn': 0.02, 'Distance': 4.5}
PANEL_PAGES = ['Attractor', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'thomas silk', {'System': 1, 'Seedmode': 1, 'Seedsize': 1.0, 'Colorby': 0, 'Palette': 0, 'Persist': 0.7,
                        'Count': 65536, 'Orbit': 6.0, 'Respawn': 0.0, 'Distance': 5.5}),
    (2, 'aizawa torus', {'System': 2, 'Seedmode': 1, 'Colorby': 2, 'Palette': 4, 'Persist': 0.5, 'Count': 65536,
                         'Pitch': -25.0, 'Orbit': 8.0}),
    (3, 'halvorsen petals', {'System': 3, 'Seedmode': 1, 'Colorby': 0, 'Palette': 5, 'Persist': 0.6,
                             'Count': 65536, 'Pitch': 35.0, 'Yaw': 45.0, 'Colorscale': 0.5}),
    (4, 'lorenz ribbons', {'System': 0, 'Seedmode': 0, 'Seedsize': 0.05, 'Respawn': 0.05, 'Colorby': 1,
                           'Palette': 3, 'Persist': 0.85, 'Count': 65536, 'Pitch': -70.0, 'Colorscale': 2.0}),
    (5, 'dadras beat', {'System': 4, 'Seedmode': 1, 'Colorby': 0, 'Palette': 6, 'Persist': 0.6, 'Count': 65536,
                        'Kick': 2.0, 'Beatevery': 1.0, 'Beatgain': 1.0, 'Colorscale': 0.5}),
]
UNIFORMS = [('uM0', ['{System#}', '{Adelta}', '{Bdelta}', '{Cdelta}']),
            ('uM1', ['{Rate}', '{Substeps}', '{Seedsize}', '{Seedmode#}']),
            ('uM2', ['{Colorby#}', '{Worldsize}', '{Kick}', '{Colorscale}']),
            ('uM3', ['{Fadein}', '0', '0', '0'])]


def _arr(kind, name, vals):
    if kind == 'vec3':
        items = ', '.join('vec3(%r, %r, %r)' % tuple(float(x) for x in v) for v in vals)
    else:
        items = ', '.join(repr(float(v)) for v in vals)
    return 'const %s %s[%d] = %s[%d](%s);\n' % (kind, name, len(vals), kind, len(vals), items)


COMMON = (_arr('vec3', 'A3_PAR', _L['A3_PAR']) + _arr('vec3', 'A3_CEN', _L['A3_CEN']) +
          _arr('float', 'A3_EXT', _L['A3_EXT']) + _arr('float', 'A3_RATE', _L['A3_RATE']) +
          _arr('float', 'A3_HMAX', _L['A3_HMAX']) + """
int a3_sys() { return clamp(int(uM0.x + 0.5), 0, %d); }
vec3 a3_par(int s) { return A3_PAR[s] * (1.0 + 0.05 * (LEVEL + uM2.z * ENV)) + uM0.yzw; }
vec3 a3_f(int s, vec3 p, vec3 k) {
    float x = p.x, y = p.y, z = p.z, a = k.x, b = k.y, c = k.z;
    if (s == 0) return vec3(a * (y - x), x * (b - z) - y, x * y - c * z);
    if (s == 1) return vec3(sin(y) - a * x, sin(z) - a * y, sin(x) - a * z);
    if (s == 2) return vec3((z - b) * x - 3.5 * y, 3.5 * x + (z - b) * y,
                            c + a * z - z * z * z / 3.0 - (x * x + y * y) * (1.0 + 0.25 * z) + 0.1 * z * x * x * x);
    if (s == 3) return vec3(-a * x - 4.0 * y - 4.0 * z - y * y, -a * y - 4.0 * z - 4.0 * x - z * z,
                            -a * z - 4.0 * x - 4.0 * y - x * x);
    if (s == 4) return vec3(y - a * x + b * y * z, c * y - x * z + z, 2.0 * x * y - 9.0 * z);
    if (s == 5) return vec3(a * (y - x), (c - a) * x - x * z + c * y, x * y - b * z);
    if (s == 6) return vec3(-y - z, x + a * y, b + z * (x - c));
    if (s == 7) return vec3(y + a * x * y + x * z, 1.0 - b * x * x + y * z, x - x * x - y * y);
    if (s == 8) return vec3(y * (z - 1.0 + x * x) + b * x, x * (3.0 * z + 1.0 - x * x) + b * y, -2.0 * z * (a + x * y));
    return vec3(a * x + y * z, b * x + c * y - x * z, -z - x * y);
}
""" % (len(_L['A3_SYSTEMS']) - 1))

STEP = """
vec4 a3_seed(int i, uint salt) {
    int s = a3_sys();
    vec3 r = rnd3(i, salt);
    vec3 u = uM1.w < 0.5 ? ballPoint(r) * uM1.z : (r * 2.0 - 1.0) * uM1.z;
    return vec4(A3_CEN[s] + u * A3_EXT[s], 0.0);
}
vec4 pt_seed(int i) { return a3_seed(i, 21u); }
vec4 pt_step(int i, vec4 s4, float dt) {
    if (dt <= 0.0) return s4;
    int s = a3_sys();
    vec3 k = a3_par(s);
    float Hh = dt * A3_RATE[s] * uM1.x;
    int n = clamp(max(int(uM1.y + 0.5), int(ceil(abs(Hh) / A3_HMAX[s]))), 1, 32);
    float h = Hh / float(n);
    vec3 p = s4.xyz;
    for (int j = 0; j < 32; j++) {
        if (j >= n) break;
        vec3 k1 = a3_f(s, p, k);
        vec3 k2 = a3_f(s, p + 0.5 * h * k1, k);
        vec3 k3 = a3_f(s, p + 0.5 * h * k2, k);
        vec3 k4 = a3_f(s, p + h * k3, k);
        p += h / 6.0 * (k1 + 2.0 * k2 + 2.0 * k3 + k4);
    }
    vec3 c = A3_CEN[s];
    float e = A3_EXT[s];
    bool bad = !(dot(p - c, p - c) < 400.0 * e * e);
    bool resp = rnd(i, FR * 4u + 1u) < uSt2.x * dt;
#ifdef PXE_PARTICLES
    float W = max(uM2.y, 1e-6);
    vec3 Pw = (p - c) / e * W;
    vec3 F = pxeParticleForce(Pw, a3_f(s, p, k) * A3_RATE[s] * uM1.x / e * W);
    p += F * (dt * e / W);                     // effector force acts as a world velocity (no inertia here)
    if (pxeKill(Pw)) bad = true;
#endif
    if (bad || resp) {
        vec4 n4 = a3_seed(i, FR * 4u + 2u);
#ifdef PXE_PARTICLES
        uint sb = FR * 8u + 60u;
        vec3 Ps = pxeSpawnAt((n4.xyz - c) / e * W, rnd(i, sb), rnd(i, sb + 1u), rnd(i, sb + 2u), rnd(i, sb + 3u));
        n4.xyz = c + Ps / W * e;
#endif
        return n4;
    }
    return vec4(p, s4.w + dt);
}
"""

PLACE = """
bool pt_place(int i, vec4 s4, out vec3 P, out vec4 C) {
    int s = a3_sys();
    vec3 c = A3_CEN[s];
    float e = A3_EXT[s];
    float W = uM2.y;
    P = (s4.xyz - c) / e * W;
    int cb = int(uM2.x + 0.5);
    float k;
    if (cb == 0) k = length(a3_f(s, s4.xyz, a3_par(s))) * A3_RATE[s] / e * uM2.w;
    else if (cb == 1) k = s4.w * 0.1 * uM2.w;
    else if (cb == 2) k = (P.z / max(W, 1e-6)) * 0.5 + 0.5;
    else k = rnd(i, 5u);
    float a = uM3.x > 0.0 ? clamp(s4.w / uM3.x, 0.0, 1.0) : 1.0;
    C = vec4(ptpal(k), a);
    return dot(P, P) < 1e6;
}
"""
