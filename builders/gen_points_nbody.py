# gen_points_nbody - GEN_points module 'nbody' (FX7c card 12, GPU Gems 3 ch. 31 tiling idea; clean-room): galaxies of
# Bodies gravitating bodies (all pairs, Plummer softening) + decorative stars riding on them. The first Bodies texels of
# the state are bodies (x, z, vx, vz in the disc plane): Galaxies cores (heavy, Coremass) then exponential discs on
# circular orbits (v from the core + the enclosed disc mass); 2 galaxies start apart and fall into each other (Approach,
# Impact, Spin2 co / counter): the tidal tails. The all-pairs sum runs in shared-memory tiles of 64 bodies (one load
# per workgroup, barrier, 64 interactions per thread; the loop bound is uniform, so the barriers stay in uniform control
# flow); symplectic Euler, step = Timescale x module dt (one step per frame: a substep would need the other
# workgroups' new positions, i.e. another dispatch). Points past Bodies are stateless stars drawn in the MAT
# around a random body (Starspread, disc Thickness). Reset (re-seed) = the collision trigger. No limits on the counts.
# Mirror: gen_points_logic.nbody_* (brute force float64). ASCII only.
MODULE = 'nbody'
KIND = '3d'
BLURB = 'Galaxies: all-pairs gravity in shared-memory tiles (Bodies <= 4096) + decorative stars on the bodies.'
COLORBY = ['speed', 'galaxy', 'radius', 'random']
EFFECTORS = None
EPOCH = '{Bodies} * 7 + {Galaxies}'
CHECK = {'t': 1.0}
MAXB = 4096

PAGES = [('Nbody', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Bodies', 'Int', 2048, {'min': 2, 'max': MAXB, 'label': 'Bodies (all pairs; re-seeds)'}),
    ('Galaxies', 'Int', 2, {'min': 1, 'max': 2, 'label': 'Galaxies (re-seeds)'}),
    ('Gconst', 'Float', 1.0, {'min': 0, 'max': 10, 'label': 'Gravity G'}),
    ('Soft', 'Float', 0.05, {'min': 0.001, 'max': 1, 'label': 'Softening'}),
    ('Timescale', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Sim time per module s'}),
    ('Coremass', 'Float', 1.0, {'min': 0, 'max': 20, 'label': 'Core mass'}),
    ('Coresoft', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'Core size (extra softening with a core)'}),
    ('Discmass', 'Float', 0.5, {'min': 0, 'max': 20, 'label': 'Disc mass (per galaxy)'}),
    ('Discradius', 'Float', 0.18, {'min': 0.01, 'max': 2, 'label': 'Disc scale length'}),
    ('Separation', 'Float', 1.4, {'min': 0, 'max': 6, 'label': 'Start separation'}),
    ('Impact', 'Float', 0.35, {'min': -3, 'max': 3, 'label': 'Impact offset'}),
    ('Approach', 'Float', 0.45, {'min': -4, 'max': 4, 'label': 'Approach speed'}),
    ('Spin2', 'Menu', 'co', {'names': ['co', 'counter'], 'labels': ['Co-rotating', 'Counter-rotating']}),
    ('Thickness', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Disc thickness (stars)'}),
    ('Starspread', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Star spread around a body'}),
    ('Bodygain', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Body brightness'}),
    ('Stargain', 'Float', 0.4, {'min': 0, 'max': 8, 'label': 'Star brightness'}),
    ('Colorby', 'Menu', 'speed', {'names': COLORBY, 'labels': ['Speed', 'Galaxy', 'Radius from the origin',
                                                               'Random']}),
    ('Colorscale', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Colour scale'}),
])]
DEFAULTS = {'Count': 131072, 'Persist': 0.0, 'Tonemap': 2, 'Palette': 5, 'Exposure': 1.0, 'Normalize': 0,
            'Pitch': -55.0, 'Orbit': 0.0, 'Distance': 3.6, 'Size': 1.0, 'Glow': 0.4}
PANEL_PAGES = ['Nbody', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'collision', {'Bodies': 2048, 'Galaxies': 2, 'Count': 131072, 'Palette': 5, 'Colorby': 0}),
    (2, 'counter spin', {'Bodies': 2048, 'Galaxies': 2, 'Spin2': 1, 'Impact': 0.2, 'Count': 131072, 'Palette': 6,
                         'Colorby': 1}),
    (3, 'lone spiral', {'Bodies': 2048, 'Galaxies': 1, 'Discmass': 1.0, 'Discradius': 0.25, 'Count': 131072,
                        'Palette': 4, 'Colorby': 2, 'Colorscale': 1.5, 'Pitch': -60.0}),
    (4, 'dense 4k', {'Bodies': 4096, 'Galaxies': 2, 'Count': 262144, 'Palette': 5, 'Starspread': 0.02,
                     'Stargain': 0.3}),
    (5, 'head on', {'Bodies': 2048, 'Galaxies': 2, 'Impact': 0.0, 'Approach': 0.8, 'Separation': 1.8,
                    'Count': 131072, 'Palette': 3, 'Colorby': 1, 'Persist': 0.5}),
]
UNIFORMS = [('uM0', ['{Bodies}', '{Galaxies}', '{Gconst}', '{Soft}']),
            ('uM1', ['{Timescale}', '0', '{Coremass}', '{Discmass}']),
            ('uM2', ['{Discradius}', '{Separation}', '{Impact}', '{Approach}']),
            ('uM3', ['{Spin2#}', '{Thickness}', '{Starspread}', '{Colorby#}']),
            ('uM4', ['{Bodygain}', '{Stargain}', '{Colorscale}', '{Coresoft}'])]

COMMON = """
int nb_n() { return clamp(int(uM0.x + 0.5), 2, min(NPTS, 4096)); }
int nb_g() { return clamp(int(uM0.y + 0.5), 1, 2); }
float nb_mass(int j) {
    int G = nb_g();
    return j < G ? uM1.z : uM1.w * float(G) / float(max(nb_n() - G, 1));
}
int nb_gal(int j) { int G = nb_g(); return j < G ? j : (j - G) - ((j - G) / G) * G; }
"""

STEP = """
vec4 nb_seed(int i) {
    int G = nb_g(), N = nb_n();
    if (i >= N) return vec4(0.0);
    int g = nb_gal(i);
    float sg = G == 2 ? (g == 0 ? -1.0 : 1.0) : 0.0;
    vec2 C = vec2(sg * 0.5 * uM2.z, sg * 0.5 * uM2.y);  // apart along z (vertical on a portrait screen after
    vec2 V = vec2(0.0, -sg * 0.5 * uM2.w);               // the camera pitch), impact offset along x
    if (i < G) return vec4(C, V);
    float h = uM2.x;
    float r = -h * log(1.0 - 0.95 * rnd(i, 21u));
    float a = TAU * rnd(i, 22u);
    float x = r / h;
    float md = uM1.w * (1.0 - (1.0 + x) * exp(-x));
    float e2 = uM0.w * uM0.w, e2c = e2 + uM4.w * uM4.w;
    float vc = sqrt(uM0.z * r * r * (uM1.z / pow(r * r + e2c, 1.5) + md / pow(r * r + e2, 1.5)));
    float spin = (g == 1 && int(uM3.x + 0.5) == 1) ? -1.0 : 1.0;
    return vec4(C + r * vec2(cos(a), sin(a)), V + spin * vc * vec2(-sin(a), cos(a)));
}
vec4 pt_seed(int i) { return nb_seed(i); }
vec4 pt_step(int i, vec4 s, float dt) { return s; }     // bodies are stepped in the tiled main below
"""

STATE_MAIN = """
shared vec4 nbT[64];
void main() {
    ivec2 T2 = ivec2(gl_GlobalInvocationID.xy);
    int side = int(uSt.y + 0.5);
    bool inside = T2.x < side && T2.y < side;
    int i = T2.y * side + T2.x;
    SIDE = side;
    int last = side * side - 1;
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    bool same = isz.x == side && isz.y == side;
    vec4 clk = same ? texelFetch(sTD2DInputs[0], ivec2(last - (last / side) * side, last / side), 0) : vec4(0.0);
    drive_globals(ivec2(uSt2.zw));
    ASP = uSt2.y;
    bool reset = !same || clk.w < 0.5 || abs(clk.z - uSt.z) > 0.5;
    float dt = reset ? 0.0 : clamp(T - clk.x, 0.0, uSt.w);
#ifdef GP_PROBE_DT
    reset = false; dt = GP_PROBE_DT;
#endif
    FR = uint(max(clk.y, 0.0)) + (dt > 0.0 ? 1u : 0u);
    NPTS = min(int(uSt.x + 0.5), last);
    int N = nb_n();
    vec4 s = inside && same ? texelFetch(sTD2DInputs[0], T2, 0) : vec4(0.0);
    bool body = inside && i < N && !reset;
    int lid = int(gl_LocalInvocationIndex);
    bool wgb = int(gl_WorkGroupID.y) * 8 * side < N;    // this workgroup holds bodies (uniform per workgroup)
    int tiles = (reset || dt <= 0.0 || !wgb) ? 0 : (N + 63) / 64;   // star-only workgroups skip the sum
    float h = dt * uM1.x;
    float e2 = uM0.w * uM0.w, c2 = uM4.w * uM4.w;
    float selfc = i < nb_g() ? 1.0 : 0.0;
    vec2 acc = vec2(0.0);
    for (int t = 0; t < 64; t++) {                      // shared-memory tiles of 64 bodies (<= 4096)
        if (t >= tiles) break;
        int j = t * 64 + lid;
        vec4 q = vec4(0.0);
        if (j < N) q = vec4(texelFetch(sTD2DInputs[0], gpTex(j), 0).xy, nb_mass(j), j < nb_g() ? 1.0 : 0.0);
        nbT[lid] = q;
        memoryBarrierShared();
        barrier();
        if (body) {
            for (int k = 0; k < 64; k++) {
                vec4 b = nbT[k];
                vec2 d = b.xy - s.xy;
                float r2 = dot(d, d) + e2 + ((b.w + selfc) > 0.5 ? c2 : 0.0);   // a core in the pair: softer
                acc += d * (b.z / (r2 * sqrt(r2)));
            }
        }
        barrier();
    }
    if (body && tiles > 0) { s.zw += uM0.z * acc * h; s.xy += s.zw * h; }
    if (!inside) return;
    if (i == last) { TDImageStoreOutput(0, ivec3(T2, 0), vec4(T, reset ? 0.0 : float(FR), uSt.z, 1.0)); return; }
    if (i >= NPTS) { TDImageStoreOutput(0, ivec3(T2, 0), vec4(0.0)); return; }
    if (reset) s = pt_seed(i);
    else if (i >= N) s = vec4(0.0);
    TDImageStoreOutput(0, ivec3(T2, 0), s);
}
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    int N = nb_n(), G = nb_g();
    vec4 b = s;
    int j = i;
    float gain = uM4.x;
    vec3 off = vec3(0.0);
    if (i >= N) {                                       // decorative star on a random disc body
        j = G + int(floor(rnd(i, 31u) * float(max(N - G, 1))));
        j = min(j, N - 1);
        b = texelFetch(GP_ST, gpTex(j), 0);
        float rr = uM3.z * sqrt(rnd(i, 32u)), an = TAU * rnd(i, 33u);
        off = vec3(rr * cos(an), 0.0, rr * sin(an));
        gain = uM4.y;
    }
    off.y = (rnd(i, 34u) * 2.0 - 1.0) * uM3.y;
    P = vec3(b.x, 0.0, b.y) + off;
    int cb = int(uM3.w + 0.5);
    float k = cb == 0 ? length(b.zw) * 0.5 * uM4.z : (cb == 1 ? (float(nb_gal(j)) + 0.5) * 0.5
            : (cb == 2 ? length(b.xy) * uM4.z : rnd(j, 5u)));
    C = vec4(ptpal(k), gain);
    return true;
}
"""
