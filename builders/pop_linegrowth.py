# pop_linegrowth - POP_linegrowth (BUILD_PLAN_27OCT lane H, row FX7b TC-09 "differential line growth", polyhop).
# A closed (or open) curve that grows and folds like coral / brain / leaf veins. Doc + LIVE CHECKS:
# docs/builds/pop_lane_h.md "TC-09". Route (lowest risk, decided offline 27 Oct): the ordered node list lives in a
# 128 x 65 rgba32f state texture (rows 0..63 = up to 8192 nodes xy, texel (0, 64) = count, frame). Two compute GLSL
# TOPs per frame (T-47): `forces` (one thread per node, brute-force repulsion over shared-memory tiles of 256) and
# `insert` (ONE workgroup of 1024 threads: split flags, shared-memory prefix scan builders/pop_scan.py, budgeted
# midpoint insertion). Feedback TOP closes the loop. Drawn by a STATIC Grid POP of points (physarum / GEN_points
# class) whose GLSL MAT reads the state; an optional linestrip view is LIVE-CHECK gated (Lines off by default).
# No Neighbor POP, no GLSL POP, no POP compute (T-124). numpy mirror: builders/pop_linegrowth_logic.py.
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_linegrowth.py').read(), ns); ns['build']('/project1/lab', first=True)
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_scan.py') as _fh:
    _SCAN = {}
    exec(_fh.read(), _SCAN)
SCAN_GLSL = _SCAN['SCAN_GLSL']

NAME = 'POP_linegrowth'
NW, NROWS, MAXN = 128, 64, 8192
SHAPES = ['circle', 'polygon', 'line']

PAGES = [
    ('Growth', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Play', 'Toggle', True, {'label': 'Play (off = hold)'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (reseed)'}),
        ('Shape', 'Menu', 'circle', {'names': SHAPES, 'labels': ['Circle (closed)', 'Polygon (closed)',
                                                                 'Line (open)']}),
        ('Seedcount', 'Int', 64, {'min': 3, 'max': 512, 'clampmin': 3, 'label': 'Seed nodes'}),
        ('Seedradius', 'Float', 0.1, {'min': 0.01, 'max': 0.45, 'label': 'Seed radius (frame heights)'}),
        ('Sides', 'Int', 5, {'min': 3, 'max': 12, 'clampmin': 3, 'label': 'Polygon sides'}),
        ('Maxnodes', 'Int', 1024, {'min': 64, 'max': 8192, 'clampmin': 3, 'clampmax': 8192,
                                   'label': 'Max nodes (growth stops here)'}),
        ('Rest', 'Float', 0.006, {'min': 0.001, 'max': 0.03, 'label': 'Rest length'}),
        ('Maxedge', 'Float', 0.009, {'min': 0.001, 'max': 0.05, 'label': 'Split edges longer than'}),
        ('Radius', 'Float', 0.02, {'min': 0.002, 'max': 0.1, 'label': 'Repulsion radius'}),
        ('Spring', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Spring'}),
        ('Align', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Align (smooth)'}),
        ('Repel', 'Float', 0.02, {'min': 0, 'max': 0.2, 'label': 'Repel'}),
        ('Jitter', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Jitter (x rest)'}),
        ('Dt', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Step'}),
        ('Maxstep', 'Float', 0.003, {'min': 0.0001, 'max': 0.02, 'label': 'Max move per frame'}),
        ('Bound', 'Float', 0.45, {'min': 0.05, 'max': 1, 'label': 'Boundary circle radius'}),
        ('Boundk', 'Float', 1.0, {'min': 0, 'max': 5, 'label': 'Boundary push'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
        ('Resetat', 'Int', -10, {'min': -10, 'max': 10, 'label': 'Reset frame (internal, set by Reset)'}),
    ]),
    ('Look', [
        ('Lines', 'Toggle', False, {'label': 'Linestrip view (LIVE CHECK gated; off = points)'}),
        ('Raster', 'Menu', 'compute', {'names': ['compute', 'render'],
                                       'labels': ['Compute (points + look in one pass)', 'Render TOP (old path)']}),
        ('Size', 'Float', 2.0, {'min': 1, 'max': 8, 'label': 'Point size px'}),
        ('Zoom', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Zoom'}),
        ('Hue', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'Hue'}),
        ('Huespread', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Hue along the line'}),
        ('Sat', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Saturation'}),
        ('Gain', 'Float', 1.5, {'min': 0, 'max': 8, 'label': 'Gain'}),
    ]),
    OUT_PAGE,
]
PANEL_PAGES = ['Growth', 'Look']
FIRST = {'Maxnodes': 1024, 'Seedcount': 64, 'Resw': 540, 'Resh': 960, 'Lines': False}

RESET_E = "1.0 if absTime.frame - parent().par.Resetat.eval() <= 1 else 0.0"
SIM_U = [
    ('uA', (PP.format('Rest'), PP.format('Maxedge'), PP.format('Radius'), PP.format('Dt'))),
    ('uB', (PP.format('Spring'), PP.format('Align'), PP.format('Repel'), PP.format('Jitter'))),
    ('uC', (PP.format('Bound'), PP.format('Boundk'), PP.format('Maxstep'), "float(parent().par.Seed.eval())")),
    ('uD', ("float(parent().par.Shape.menuIndex)", "float(parent().par.Seedcount.eval())", PP.format('Seedradius'),
            "float(parent().par.Sides.eval())")),
    ('uE', (RESET_E, "1.0 if parent().par.Play.eval() else 0.0", "float(parent().par.Maxnodes.eval())",
            "parent().par.Resw.eval() / max(parent().par.Resh.eval(), 1)")),
]
MAT_U = [
    ('uV', ("parent().par.Resw.eval() / max(parent().par.Resh.eval(), 1)", PP.format('Zoom'), PP.format('Size'),
            "float(parent().par.Shape.menuIndex)")),
    ('uH', (PP.format('Hue'), PP.format('Huespread'), PP.format('Sat'), "0.0")),
]
LOOK_U = [('uL', (PP.format('Gain'), "0.0", "0.0", "0.0"))]
GLOOK_ON_E = "1 if parent().par.Raster.eval() == 'compute' and not parent().par.Lines.eval() else 0"

HEAD = """
#define NW 128
#define NROWS 64
#define MAXN 8192
const float TAU = 6.283185307179586;
uniform vec4 uA;   // rest, maxedge, radius, dt
uniform vec4 uB;   // spring, align, repel, jitter
uniform vec4 uC;   // bound, boundk, maxstep, seed
uniform vec4 uD;   // shape, seedcount, seedradius, sides
uniform vec4 uE;   // reset, play, maxnodes, aspect
ivec2 tx(int i) { return ivec2(i % NW, i / NW); }
vec2 node(int i) { return texelFetch(sTD2DInputs[0], tx(i), 0).xy; }
bool is_closed() { return int(uD.x + 0.5) != 2; }
int max_nodes() { return clamp(int(uE.z + 0.5), 3, MAXN); }
"""

FORCES = """// POP_linegrowth forces (TC-09): seed / spring / align / repulsion (brute force, shared tiles) / bound / jitter.
// Mirror: pop_linegrowth_logic.forces + seed_nodes. Every thread reaches every barrier (uniform flow).
layout(local_size_x = 128, local_size_y = 2) in;
#define TILE 256
#define NTILES 32
""" + HEAD + """
shared vec2 sP[TILE];
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hh(uint i, uint s) { return float(lowbias(i * 747796405u + s * 2891336453u + 1u) >> 8) / 16777216.0; }
vec2 seedpos(int i, int n)
{
    float fi = float(i), R = uD.z;
    int m = int(uD.x + 0.5);
    if (m == 0) { float a = TAU * fi / float(n); return vec2(R * cos(a), R * sin(a)); }
    if (m == 1) {
        float sides = float(max(int(uD.w + 0.5), 3));
        float s = fi / float(n) * sides;
        float k = floor(s);
        float f = s - k;
        float a0 = TAU * k / sides + 1.5707963267948966, a1 = TAU * (k + 1.0) / sides + 1.5707963267948966;
        return mix(vec2(R * cos(a0), R * sin(a0)), vec2(R * cos(a1), R * sin(a1)), f);
    }
    return vec2(-R + 2.0 * R * fi / float(n - 1), 0.0);
}
vec2 spring(vec2 p, vec2 q)
{
    vec2 d = q - p;
    float L = length(d);
    return L > 1e-9 ? uB.x * (L - uA.x) * d / L : vec2(0.0);
}
void main()
{
    ivec2 g = ivec2(gl_GlobalInvocationID.xy);
    int lt = int(gl_LocalInvocationID.y) * NW + int(gl_LocalInvocationID.x);
    int i = g.y * NW + g.x;
    vec4 ct = texelFetch(sTD2DInputs[0], ivec2(0, NROWS), 0);
    int cnt = int(ct.x + 0.5);
    int frame = int(ct.y + 0.5);
    bool seeding = uE.x > 0.5 || cnt <= 0;
    bool live = !seeding && uE.y > 0.5;
    int nseed = clamp(int(uD.y + 0.5), 3, max_nodes());
    vec2 p = i < MAXN ? node(i) : vec2(0.0);
    vec2 f = vec2(0.0);
    if (live) {
        for (int t = 0; t < NTILES; t++) {
            if (t * TILE >= cnt) break;                       // uniform: cnt is the same for every thread
            int j = t * TILE + lt;
            sP[lt] = j < cnt ? node(j) : vec2(1e9);
            barrier();
            if (i < cnt) {
                for (int k = 0; k < TILE; k++) {
                    if (t * TILE + k == i) continue;
                    vec2 d = p - sP[k];
                    float r = length(d);
                    if (r < uA.z && r > 1e-9) f += uB.z * (uA.z - r) / uA.z * d / r;
                }
            }
            barrier();
        }
    }
    if (g.x >= NW || g.y > NROWS) return;
    vec4 o = vec4(0.0);
    if (g.y == NROWS) {
        if (g.x == 0) o = vec4(float(seeding ? nseed : cnt), float(frame + 1), 0.0, 0.0);
        TDImageStoreOutput(0, ivec3(g, 0), o);
        return;
    }
    if (seeding) {
        if (i < nseed) o = vec4(seedpos(i, nseed), 0.0, 1.0);
    } else if (i < cnt) {
        if (live) {
            bool cl = is_closed();
            int ia = cl ? (i - 1 + cnt) % cnt : max(i - 1, 0);
            int ib = cl ? (i + 1) % cnt : min(i + 1, cnt - 1);
            vec2 a = node(ia), b = node(ib);
            if (ia != i) f += spring(p, a);
            if (ib != i) f += spring(p, b);
            if (cl || (i > 0 && i < cnt - 1)) f += uB.y * (0.5 * (a + b) - p);
            float L = length(p);
            if (L > uC.x) f -= uC.y * (L - uC.x) * p / L;
            uint salt = uint(int(uC.w + 0.5)) * 65537u + uint(frame) * 2u;
            vec2 jit = vec2(hh(uint(i), salt) - 0.5, hh(uint(i), salt + 1u) - 0.5) * 2.0;
            vec2 dp = uA.w * f + uB.w * uA.x * jit;
            float dl = length(dp);
            if (dl > uC.z) dp *= uC.z / max(dl, 1e-30);
            p += dp;
        }
        o = vec4(p, 0.0, 1.0);
    }
    TDImageStoreOutput(0, ivec3(g, 0), o);
}
"""

INSERT = """// POP_linegrowth insert (TC-09): ONE workgroup (dispatch 1 x 1 x 1). Split flags -> exclusive scan -> node i to
// i + accepted splits before it, accepted split -> midpoint after it. Budget = maxnodes - count (first flags win).
// Mirror: pop_linegrowth_logic.insert.
layout(local_size_x = 1024) in;
#define CHUNK 8
""" + HEAD + SCAN_GLSL + """
void put(int i, vec4 v) { TDImageStoreOutput(0, ivec3(tx(i), 0), v); }
void main()
{
    uint tid = gl_LocalInvocationID.x;
    vec4 ct = texelFetch(sTD2DInputs[0], ivec2(0, NROWS), 0);
    int cnt = int(ct.x + 0.5);
    bool cl = is_closed();
    bool grow = uE.y > 0.5 && cnt > 1;
    int budget = max(max_nodes() - cnt, 0);
    int base = int(tid) * CHUNK;
    uint flags = 0u;
    uint loc = 0u;
    for (int k = 0; k < CHUNK; k++) {
        int i = base + k;
        if (grow && i < cnt && (cl || i < cnt - 1)) {
            if (distance(node(i), node((i + 1) % cnt)) > uA.y) { flags |= 1u << uint(k); loc += 1u; }
        }
    }
    uint total;
    uint run = scan_excl(loc, tid, total);
    for (int k = 0; k < CHUNK; k++) {
        int i = base + k;
        if (i >= cnt) break;
        int dst = i + min(int(run), budget);
        vec2 p = node(i);
        put(dst, vec4(p, 0.0, 1.0));
        if ((flags & (1u << uint(k))) != 0u) {
            if (int(run) < budget) put(dst + 1, vec4(0.5 * (p + node((i + 1) % cnt)), 0.0, 1.0));
            run += 1u;
        }
    }
    if (tid == 0u)
        TDImageStoreOutput(0, ivec3(0, NROWS, 0), vec4(float(cnt + min(int(total), budget)), ct.y, 0.0, 0.0));
}
"""

VERT_COMMON = """
#define NW 128
#define NROWS 64
#define MAXN 8192
uniform sampler2D sSt;
uniform vec4 uV;   // aspect, zoom, size, shape
uniform vec4 uH;   // hue, hue spread, sat, -
out Vertex { vec4 color; float size; } oV;
vec3 hsv(float h, float s) { vec3 k = clamp(abs(fract(h + vec3(0.0, 2.0, 1.0) / 3.0) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return mix(vec3(1.0), k, s); }
void place(int i, int cnt)
{
    vec2 p = texelFetch(sSt, ivec2(i % NW, i / NW), 0).xy;
    float z = uV.y;
    gl_Position = vec4(p.x * 2.0 * z / max(uV.x, 1e-6), p.y * 2.0 * z, 0.0, 1.0);
    oV.color = vec4(hsv(uH.x + uH.y * float(i) / float(max(cnt, 1)), uH.z), 1.0);
}
"""

VERT_POINTS = """// POP_linegrowth points: static 128 x 64 Grid POP; point (col, row) -> node row * 128 + col (T-112: TDPos).
""" + VERT_COMMON + """
void main()
{
    ivec2 t = ivec2(floor((TDPos().xy + 0.5) * vec2(float(NW - 1), float(NROWS - 1)) + 0.5));
    int i = t.y * NW + t.x;
    int cnt = int(texelFetch(sSt, ivec2(0, NROWS), 0).x + 0.5);
    gl_PointSize = max(uV.z, 1.0);
    oV.size = gl_PointSize;
    if (i < cnt) place(i, cnt);
    else { gl_Position = vec4(2.0, 2.0, 0.0, 1.0); oV.color = vec4(0.0); }
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

VERT_LINES = """// POP_linegrowth linestrip (LIVE CHECK gated): Grid POP 1 x (MAXN + 1) linestrips; vertex k -> node k,
// k >= count collapses onto node 0 (closed) / the last node (open): degenerate segments draw nothing.
""" + VERT_COMMON + """
void main()
{
    int k = int(floor((TDPos().x + 0.5) * float(MAXN) + 0.5));
    int cnt = int(texelFetch(sSt, ivec2(0, NROWS), 0).x + 0.5);
    int i = k < cnt ? k : (int(uV.w + 0.5) != 2 ? 0 : max(cnt - 1, 0));
    gl_PointSize = 1.0;
    oV.size = 1.0;
    place(i, cnt);
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

PIXEL = """// POP_linegrowth pixel: round sprite (Size > 1) or 1 px, additive.
in Vertex { vec4 color; float size; } iV;
layout(location = 0) out vec4 fragColor;
void main()
{
    TDCheckDiscard();
    float w = 1.0;
    if (iV.size > 1.5) { vec2 d = gl_PointCoord * 2.0 - 1.0; w = max(1.0 - dot(d, d), 0.0); }
    fragColor = TDOutputSwizzle(iV.color * w);
}
"""

GLOOK = """// POP_linegrowth glook (perf 27 Oct, Raster 'compute' = the default points view): the points render, tone and
// over-in1 in ONE compute pass (RENDER_COST rule 5: <= ~8k points, no Render TOP CPU floor). Same maths as
// VERT_POINTS + PIXEL + LOOK: node -> clip (place) -> window; a point of size S covers the pixel centres inside
// [w - S/2, w + S/2) per axis (point coord q / S), w = 1 - |2 q / S - 1|^2 when S > 1.5; w snapped to 1/256 px and no
// centre clip (b3 parity vs the Render TOP: Size 1 bit-exact, Size 2 / 8 / zoom 2.5 max 0.008, mean <= 1e-7). 16 x 16
// tiles: each batch of 256 nodes is culled to the tile into shared memory, then every pixel sums its sprites (fp32).
layout(local_size_x = 16, local_size_y = 16) in;
#define NW 128
#define NROWS 64
#define MAXN 8192
#define NB 256
uniform vec4 uV;   // aspect, zoom, size, shape
uniform vec4 uH;   // hue, hue spread, sat, -
uniform vec4 uL;   // gain
shared vec2 sXY[NB];
shared vec4 sC[NB];
shared int sN;
vec3 hsv(float h, float s) { vec3 k = clamp(abs(fract(h + vec3(0.0, 2.0, 1.0) / 3.0) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return mix(vec3(1.0), k, s); }
void main()
{
    ivec2 T = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    vec2 W = vec2(sz);
    int lt = int(gl_LocalInvocationIndex);
    vec2 c = vec2(T) + 0.5;
    vec2 t0 = vec2(gl_WorkGroupID.xy * 16u) + 0.5;
    vec2 t1 = t0 + 15.0;
    int cnt = clamp(int(texelFetch(sTD2DInputs[0], ivec2(0, NROWS), 0).x + 0.5), 0, MAXN);
    float S = max(uV.z, 1.0);
    float hs = 0.5 * S;
    bool rnd = S > 1.5;
    vec4 acc = vec4(0.0);
    for (int b0 = 0; b0 < MAXN; b0 += NB) {
        if (b0 >= cnt) break;                                 // uniform: cnt is the same for every thread
        if (lt == 0) sN = 0;
        barrier();
        int i = b0 + lt;
        if (i < cnt) {
            vec2 p = texelFetch(sTD2DInputs[0], ivec2(i % NW, i / NW), 0).xy;
            vec2 ndc = vec2(p.x * 2.0 * uV.y / max(uV.x, 1e-6), p.y * 2.0 * uV.y);
            vec2 w = floor((ndc * 0.5 + 0.5) * W * 256.0 + 0.5) / 256.0;     // 1/256 px vertex snap like the raster
            if (w.x + hs > t0.x && w.x - hs <= t1.x && w.y + hs > t0.y && w.y - hs <= t1.y) {
                int k = atomicAdd(sN, 1);
                sXY[k] = w - hs;
                sC[k] = vec4(hsv(uH.x + uH.y * float(i) / float(max(cnt, 1)), uH.z), 1.0);
            }
        }
        barrier();
        int n = sN;
        for (int k = 0; k < NB; k++) {
            if (k >= n) break;
            vec2 q = c - sXY[k];
            if (q.x >= 0.0 && q.x < S && q.y >= 0.0 && q.y < S) {
                float wt = 1.0;
                if (rnd) { vec2 d = q / S * 2.0 - 1.0; wt = max(1.0 - dot(d, d), 0.0); }
                acc += sC[k] * wt;
            }
        }
        barrier();
    }
    if (T.x >= sz.x || T.y >= sz.y) return;
    vec2 uv = c * uTDOutputInfo.res.xy;
    vec4 b = texture(sTD2DInputs[1], uv);
    vec3 col = 1.0 - exp(-acc.rgb * uL.x);
    float a = clamp(max(col.r, max(col.g, col.b)), 0.0, 1.0);
    TDImageStoreOutput(0, ivec3(T, 0), vec4(col + b.rgb * (1.0 - a), a + b.a * (1.0 - a)));
}
"""

LOOK = """// POP_linegrowth look: tone the additive render, premultiplied over in1.
layout(local_size_x = 8, local_size_y = 8) in;
uniform vec4 uL;   // gain
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= int(uTDOutputInfo.res.z) || p.y >= int(uTDOutputInfo.res.w)) return;
    vec2 uv = (vec2(p) + 0.5) * uTDOutputInfo.res.xy;
    vec4 r = texture(sTD2DInputs[0], uv);
    vec4 b = texture(sTD2DInputs[1], uv);
    vec3 c = 1.0 - exp(-r.rgb * uL.x);
    float a = clamp(max(c.r, max(c.g, c.b)), 0.0, 1.0);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(c + b.rgb * (1.0 - a), a + b.a * (1.0 - a)));
}
"""

PULSES = """# POP_linegrowth pulses: Reset stamps the frame; the forces pass reseeds while absTime.frame - Resetat <= 1.
def onPulse(par):
    if par.name == 'Reset':
        par.owner.par.Resetat = absTime.frame
    return
"""


def shader_texts():
    return {'forces': FORCES, 'insert': INSERT, 'vert_points': VERT_POINTS, 'vert_lines': VERT_LINES,
            'pixel': PIXEL, 'look': LOOK, 'glook': GLOOK}


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_linegrowth (TC-09): differential line growth. Node list in a 128 x 65 state '
                                 'texture (count at texel 0,64); forces + single-workgroup insert compute passes; '
                                 'static Grid POP points draw it. Pulse Reset. Amount 0 = in1 untouched. Out: out1.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    if first:
        _apply_first(c, FIRST)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Background (premultiplied); the growth is drawn over it.'
    pe = _mk(c, parameterexecuteDAT, 'lg_pulses')
    if pe.text != PULSES:
        pe.text = PULSES
    pe.par.op = c
    pe.par.pars = 'Reset'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = False
    pe.par.onpulse = True
    blank = _blank(c, 'state_blank', str(NW), str(NROWS + 1))
    blank.comment = 'Zero state: count 0 -> the forces pass seeds on the first frame.'
    fb = _mk(c, feedbackTOP, 'state_fb')
    _wire(blank, fb)
    fo = _compute(c, 'forces', FORCES, [fb], str(NW), str(NROWS + 1), spec=SIM_U)
    fo.comment = 'One thread per node: seed (Reset / count 0) or spring + align + repulsion + bound + jitter.'
    ins = _compute(c, 'insert', INSERT, [fo], str(NW), str(NROWS + 1), spec=SIM_U)
    ins.par.autodispatchsize = False
    _try(ins, 'dispatchsizex', 1)
    _try(ins, 'dispatchsizey', 1)
    _try(ins, 'dispatchsizez', 1)
    ins.comment = 'ONE workgroup of 1024: split flags -> prefix scan (pop_scan) -> midpoints inserted in order.'
    fb.par.top = 'insert'
    pts = _grid(c, 'pts', str(NW), str(NROWS), 'points')
    pts.comment = 'Static 128 x 64 points (one per node slot).'
    strip = _grid(c, 'strip', str(MAXN + 1), '1', 'linestrips')
    strip.comment = 'Static 1 x 8193 linestrip (Lines view, LIVE CHECK gated).'
    samp = [('sSt', 'insert', 'nearest')]
    mp = _mat(c, 'mat', VERT_POINTS, PIXEL, samplers=samp, spec=MAT_U, blend='add', depth=False)
    ml = _mat(c, 'mat_lines', VERT_LINES, PIXEL, samplers=samp, spec=MAT_U, blend='add', depth=False)
    mp.comment = ml.comment = 'Vertex reads the node texel (clip space written directly), additive colour.'
    _geo(c, 'geo', 'pts', 'mat')
    _geo(c, 'geo_lines', 'strip', 'mat_lines')
    cam = _cam(c, 'cam', {})
    cam.comment = 'Unused by the shaders (they write clip space) but a Render TOP needs a camera.'
    rp = _render(c, 'render', 'cam', 'geo', fmt='rgba32float', aa='aa1')
    rl = _render(c, 'render_lines', 'cam', 'geo_lines', fmt='rgba32float', aa='aa1')
    rs = _mk(c, switchTOP, 'view_sel')
    _wire(rp, rs, 0)
    _wire(rl, rs, 1)
    _expr(rs.par.index, "1 if parent().par.Lines.eval() else 0")
    rs.comment = 'Points (default) or the linestrip view; only the chosen render cooks.'
    # Render gate (27 Oct polish): each Render TOP's viewer pulls it while the pane is inside this COMP, even when
    # view_sel does not select it (T-206: render_lines ~1.0 ms CPU with Lines off); its Render par follows the view.
    _expr(rp.par.render, "not parent().par.Lines.eval() and parent().par.Raster.eval() == 'render'")
    _expr(rl.par.render, "bool(parent().par.Lines.eval())")
    rp.comment = 'Points view, Raster render (renders only then: Render par gate; Raster compute = glook).'
    rl.comment = 'Linestrip view (renders only while Lines is on: Render par gate).'
    lk = _compute(c, 'look', LOOK, [rs, in1], RESW, RESH, fmt='rgba16float', spec=LOOK_U, filt='linear')
    lk.comment = 'Tone (1 - exp(-gain x render)) premultiplied over in1 (Lines on, or Raster render).'
    gl = _compute(c, 'glook', GLOOK, [ins, in1], RESW, RESH, fmt='rgba16float', spec=MAT_U + LOOK_U, filt='linear')
    gl.comment = 'Raster compute (default points view): points + tone + over in1 in one pass, no Render TOP.'
    ls = _mk(c, switchTOP, 'look_sel')
    _wire(lk, ls, 0)
    _wire(gl, ls, 1)
    _expr(ls.par.index, GLOOK_ON_E)
    ls.comment = 'glook (Raster compute, points) or the Render TOP look (Lines, or Raster render).'
    _out_switch(c, in1, ls)
    stages = [
        {'title': '1 In + controls', 'role': 'input', 'ops': ['in1', 'lg_pulses'], 'body': 'in1 background; Reset.'},
        {'title': '2 State loop', 'role': 'feedback', 'ops': ['state_blank', 'state_fb', 'forces', 'forces_compute',
                                                              'insert', 'insert_compute'],
         'body': 'state_fb -> forces (per node) -> insert (one workgroup, scan) -> state_fb.'},
        {'title': '3 Draw', 'role': 'process', 'ops': ['pts', 'strip', 'mat', 'mat_vertex', 'mat_pixel', 'mat_lines',
                                                       'mat_lines_vertex', 'mat_lines_pixel', 'geo', 'geo_lines',
                                                       'cam', 'render', 'render_lines', 'view_sel'],
         'body': 'Static Grid POPs read the state in their MAT; additive 32F renders.'},
        {'title': '4 Look + out', 'role': 'output', 'ops': ['look', 'look_compute', 'glook', 'glook_compute',
                                                            'look_sel', 'out_sel', 'out1'],
         'body': 'Raster compute: glook = points + tone over in1 in one pass; else look tones a render. '
                 'Amount 0 = in1 untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
