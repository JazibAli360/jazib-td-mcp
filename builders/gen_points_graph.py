# gen_points_graph - GEN_points module 'graph' (FX5 G22): force-directed network / constellation. The first Nodes
# texels of the state are nodes (x, y, vx, vy) laid out by Fruchterman-Reingold forces in the state pass: repulsion
# K^2 d / (|d|^2 + soft) against every other node (brute force, Nodes <= 4096, bounded loop), springs |d| / K on the
# edges of a random recursive tree (parent(k) = floor(rnd k)) + Extra random links, gravity to the centre, damping,
# speed cap, beat Kick shakes. The rest of the points are stateless and drawn in the MAT from the node texels: a glow
# disc of Nodepoints per node and dust along every edge (Edgeflow slides it, Edgefade hides long edges). Shared
# effectors push / attract / vortex the nodes (BO_particles adapter, Effon off). Mirror: gen_points_logic.graph_*.
MODULE = 'graph'
KIND = '2d'
BLURB = 'Nodes (first texels) by force layout: repulsion all pairs + edge springs; edges + node glows as dust.'
COLORBY = ['index', 'speed', 'length']
EFFECTORS = 'particles'
EPOCH = '{Nodes}'           # a new node count re-seeds the layout

PAGES = [('Graph', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Nodes', 'Int', 384, {'min': 2, 'max': 4096, 'label': 'Nodes'}),
    ('Spacing', 'Float', 0.04, {'min': 0.005, 'max': 1, 'label': 'Spacing K (world)'}),
    ('Spring', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Edge spring'}),
    ('Extra', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Extra links (share of nodes)'}),
    ('Repulsion', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Repulsion'}),
    ('Gravity', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Gravity to centre'}),
    ('Damping', 'Float', 8.0, {'min': 0, 'max': 20, 'label': 'Damping per s'}),
    ('Maxspeed', 'Float', 1.0, {'min': 0.01, 'max': 10, 'label': 'Max node speed (world/s)'}),
    ('Seedsize', 'Float', 1.0, {'min': 0.05, 'max': 4, 'label': 'Seed disc size'}),
    ('Nodepoints', 'Int', 24, {'min': 0, 'max': 256, 'label': 'Glow points per node'}),
    ('Nodegain', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Node brightness'}),
    ('Nodesize', 'Float', 0.012, {'min': 0, 'max': 0.2, 'label': 'Node glow radius (world)'}),
    ('Edgegain', 'Float', 0.6, {'min': 0, 'max': 8, 'label': 'Edge brightness'}),
    ('Edgefade', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Edge fade length (0 = off)'}),
    ('Edgeflow', 'Float', 0.15, {'min': -4, 'max': 4, 'label': 'Edge dust flow per s'}),
    ('Colorby', 'Menu', 'index', {'names': COLORBY, 'labels': ['Node index', 'Node speed', 'Edge length']}),
    ('Colorscale', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Colour scale'}),
    ('Kick', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Beat pulse -> shake'}),
])]
DEFAULTS = {'Count': 65536, 'Persist': 0.5, 'Tonemap': 0, 'Palette': 4, 'Exposure': 0.0}
PANEL_PAGES = ['Graph', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'constellation', {'Nodes': 384, 'Spacing': 0.04, 'Extra': 0.15, 'Palette': 4, 'Count': 65536,
                          'Persist': 0.5}),
    (2, 'dense web', {'Nodes': 1024, 'Spacing': 0.025, 'Extra': 0.5, 'Nodepoints': 8, 'Edgegain': 0.4,
                      'Palette': 6, 'Count': 65536, 'Persist': 0.3}),
    (3, 'tree', {'Nodes': 256, 'Spacing': 0.06, 'Extra': 0.0, 'Gravity': 0.6, 'Colorby': 2, 'Palette': 5,
                 'Count': 65536}),
    (4, 'beat shake', {'Nodes': 384, 'Kick': 3.0, 'Beatevery': 1.0, 'Beatgain': 1.0, 'Colorby': 1,
                       'Colorscale': 2.0, 'Palette': 3, 'Count': 65536, 'Persist': 0.7}),
    (5, 'sparse stars', {'Nodes': 128, 'Spacing': 0.08, 'Extra': 0.3, 'Nodepoints': 64, 'Nodesize': 0.02,
                         'Edgegain': 0.3, 'Edgeflow': 0.4, 'Palette': 0, 'Count': 65536}),
]
UNIFORMS = [('uM0', ['{Nodes}', '{Spacing}', '{Spring}', '{Extra}']),
            ('uM1', ['{Repulsion}', '{Gravity}', '{Damping}', '{Maxspeed}']),
            ('uM2', ['{Kick}', '{Colorby#}', '{Colorscale}', '{Edgefade}']),
            ('uM3', ['{Nodepoints}', '{Nodegain}', '{Nodesize}', '{Edgeflow}']),
            ('uM4', ['{Edgegain}', '{Seedsize}', '0', '0'])]

COMMON = """
int gr_n() { return max(1, min(min(int(uM0.x + 0.5), NPTS), 4096)); }
int gr_parent(int k) { return k > 0 ? int(floor(rnd(k, 71u) * float(k))) : -1; }
int gr_extra(int k, int N) { int x = int(floor(rnd(k, 73u) * float(N))); return (rnd(k, 75u) < uM0.w && x != k) ? x : -1; }
"""

STEP = """
vec4 gr_seed(int i) {
    float a = TAU * rnd(i, 61u), r = sqrt(rnd(i, 62u)) * 0.5 * uM4.y;
    return i < gr_n() ? vec4(r * cos(a), r * sin(a), 0.0, 0.0) : vec4(0.0);
}
vec4 pt_seed(int i) { return gr_seed(i); }
vec4 pt_step(int i, vec4 s, float dt) {
    if (dt <= 0.0) return s;
    int N = gr_n();
    if (i >= N) return vec4(0.0);
    vec2 p = s.xy, v = s.zw;
    float K = uM0.y;
    float soft = (0.05 * K) * (0.05 * K);
    int pi_ = gr_parent(i), xi = gr_extra(i, N);
    vec2 F = vec2(0.0);
    for (int j = 0; j < 4096; j++) {
        if (j >= N) break;
        if (j == i) continue;
        vec2 d = p - texelFetch(GP_ST, gpTex(j), 0).xy;
        float d2 = dot(d, d);
        float f = uM1.x * K * K / (d2 + soft);
        if (gr_parent(j) == i || pi_ == j || gr_extra(j, N) == i || xi == j) f -= sqrt(d2) / K * uM0.z;
        F += d * f;
    }
    F -= p * uM1.y;
    F += (vec2(rnd(i, FR * 4u + 1u), rnd(i, FR * 4u + 2u)) - 0.5) * 2.0 * (uM2.x * ENV);
    v = v * exp(-uM1.z * dt) + F * dt;
    float sp = length(v);
    if (sp > uM1.w) v *= uM1.w / max(sp, 1e-12);
    vec2 ve = vec2(0.0);
#ifdef PXE_PARTICLES
    ve = pxeParticleForce(vec3(p, 0.0), vec3(v, 0.0)).xy;   // effector force = extra world velocity
#endif
    p += (v + ve) * dt;
    if (!(dot(p, p) < 1e4)) return gr_seed(i);
    return vec4(p, v);
}
"""

PLACE = """
float gr_k(int n, int N) {
    int cb = int(uM2.y + 0.5);
    vec4 q = texelFetch(GP_ST, gpTex(n), 0);
    return cb == 0 ? float(n) / float(N) : (cb == 1 ? length(q.zw) * uM2.z : rnd(n, 5u));
}
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    int N = gr_n();
    int G = max(int(uM3.x + 0.5), 0);
    P = vec3(0.0);
    C = vec4(0.0);
    if (i < N) { P.xy = s.xy; C = vec4(ptpal(gr_k(i, N)), uM3.y); return true; }
    if (i < N + N * G) {
        int n = (i - N) / max(G, 1);
        float r = sqrt(rnd(i, 91u)) * uM3.z, an = TAU * rnd(i, 92u);
        P.xy = texelFetch(GP_ST, gpTex(n), 0).xy + r * vec2(cos(an), sin(an));
        C = vec4(ptpal(gr_k(n, N)), uM3.y * 0.5);
        return true;
    }
    int e0 = N + N * G, ne = 2 * N - 1;
    int pe = max((NPTS - e0) / ne, 1);
    int e = (i - e0) / pe, loc = (i - e0) - e * pe;
    if (e >= ne) return false;
    int A, B;
    if (e < N - 1) { A = e + 1; B = gr_parent(A); }
    else { A = e - (N - 1); B = gr_extra(A, N); }
    if (B < 0 || A >= N) return false;
    vec2 pa = texelFetch(GP_ST, gpTex(A), 0).xy, pb = texelFetch(GP_ST, gpTex(B), 0).xy;
    float t = (float(loc) + fract(rnd(i, 93u) + T * uM3.w)) / float(pe);
    P.xy = mix(pa, pb, t);
    float L = length(pa - pb);
    float fade = uM2.w > 0.0 ? clamp(1.0 - L / uM2.w, 0.0, 1.0) : 1.0;
    float k = int(uM2.y + 0.5) == 2 ? L * uM2.z : (gr_k(A, N) + gr_k(B, N)) * 0.5;
    C = vec4(ptpal(k), fade * uM4.x);
    return fade > 0.0;
}
"""
