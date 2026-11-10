# pop_tree - POP_tree (BUILD_PLAN_27OCT lane H, row FX7b TC-18 "GPU L-system", paketa12's recursive subdivision with
# POPs). The CPU turtle L-system already exists (GEN_points lsystem); this is the GPU branching tree. Doc + LIVE CHECKS:
# docs/builds/pop_lane_h.md "TC-18".
# Route (decided offline 27 Oct): implicit complete B-ary tree in BFS order (node k > 0: parent (k - 1) / B, slot
# (k - 1) % B), so no POP topology is built or grown at all. ONE compute GLSL TOP `segs` (2*side x side rgba32f; texel
# 2x = start xyz + level, 2x+1 = end xyz + width) where every thread walks its node's ancestor chain from the root
# (loop capped by #define MAXD 20) composing per-level rotations (twist ry, wind sway rz, spread rx, hashed jitter),
# length x Ratio per level, Progress growing outward by level. Draw = points dust along the segments: ONE static Grid
# POP of points (pside x pside) + GLSL MAT (the proven GEN_points / physarum class, T-112). Optional `Lines` = a second
# static Grid POP (2 rows x N cols, liney only) whose column i is segment i: LIVE CHECK gated, default off.
# Hard caps: segments <= 262144 (Depth clamped per Branches), points <= 1M (Samples clamped). No POP compute (T-124).
# numpy mirror: builders/pop_tree_logic.py. Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_tree.py').read(), ns); ns['build']('/project1/lab', first=True)
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())

NAME = 'POP_tree'

PAGES = [
    ('Tree', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Branches', 'Int', 2, {'min': 2, 'max': 4, 'clampmin': 2, 'clampmax': 4, 'label': 'Branches per node'}),
        ('Depth', 'Int', 10, {'min': 0, 'max': 17, 'clampmin': 0, 'clampmax': 17,
                              'label': 'Depth (branchings; capped so segments <= 262k)'}),
        ('Spread', 'Float', 30.0, {'min': 0, 'max': 120, 'label': 'Spread deg'}),
        ('Twist', 'Float', 137.5, {'min': 0, 'max': 360, 'label': 'Twist deg per level (phyllotaxis)'}),
        ('Jitter', 'Float', 8.0, {'min': 0, 'max': 60, 'label': 'Angle jitter deg (per node)'}),
        ('Ratio', 'Float', 0.72, {'min': 0.3, 'max': 1.0, 'label': 'Length ratio per level'}),
        ('Length', 'Float', 0.35, {'min': 0.01, 'max': 2, 'label': 'Trunk length'}),
        ('Lenjitter', 'Float', 0.15, {'min': 0, 'max': 0.9, 'label': 'Length jitter (per node)'}),
        ('Progress', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Growth (outward by level)'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
    ]),
    ('Wind', [
        ('Speed', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Clock speed'}),
        ('Sway', 'Float', 6.0, {'min': 0, 'max': 45, 'label': 'Sway deg (grows with level)'}),
        ('Swayspeed', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Sway rad / s'}),
    ]),
    ('Draw', [
        ('Samples', 'Int', 8, {'min': 1, 'max': 64, 'clampmin': 1, 'clampmax': 256,
                               'label': 'Dust points per segment (total capped at 1M)'}),
        ('Pointsize', 'Float', 1.0, {'min': 1, 'max': 8, 'label': 'Point size px'}),
        ('Lines', 'Toggle', False, {'label': 'Draw lines instead of dust (LIVE CHECK gated)'}),
        ('Hue0', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Hue at the root'}),
        ('Hue1', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Hue at the tips'}),
        ('Sat', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Saturation'}),
        ('Bright', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Brightness'}),
        ('Gain', 'Float', 0.35, {'min': 0, 'max': 4, 'label': 'Gain per point (additive)'}),
        ('Width', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Width (stored for consumers)'}),
        ('Widthratio', 'Float', 0.75, {'min': 0.1, 'max': 1, 'label': 'Width ratio per level'}),
        ('Composite', 'Menu', 'alone', {'names': ['alone', 'add'], 'labels': ['Tree alone', 'Add over in1']}),
    ]),
    ('View', [
        ('Dist', 'Float', 3.0, {'min': 0.5, 'max': 20, 'label': 'Camera distance'}),
        ('Camheight', 'Float', 1.0, {'min': -5, 'max': 5, 'label': 'Camera height'}),
        ('Fov', 'Float', 45.0, {'min': 5, 'max': 120, 'label': 'Vertical fov deg'}),
        ('Orbit', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Orbit deg'}),
        ('Spin', 'Float', 10.0, {'min': -90, 'max': 90, 'label': 'Spin deg / s'}),
    ]),
    OUT_PAGE,
]
PANEL_PAGES = ['Tree', 'Wind', 'Draw', 'View']
FIRST = {'Branches': 2, 'Depth': 10, 'Samples': 4, 'Lines': False}

MAXDEPTH = {2: 17, 3: 10, 4: 8}            # largest Depth with N <= 262144 (pop_tree_logic.max_depth)
B_E = "max(2, min(int(parent().par.Branches.eval()), 4))"
DEFF_E = "max(0, min(int(parent().par.Depth.eval()), {2: 17, 3: 10, 4: 8}[%s]))" % B_E
NSEG_E = "(({b}) ** (({d}) + 1) - 1) // (({b}) - 1)".format(b=B_E, d=DEFF_E)
SIDE_E = "max(int(math.ceil(math.sqrt(max(%s, 1)))), 1)" % NSEG_E
SAMP_E = "max(1, min(int(parent().par.Samples.eval()), 1048576 // max(%s, 1)))" % NSEG_E
NPTS_E = "(%s) * (%s)" % (NSEG_E, SAMP_E)
PSIDE_E = "max(int(math.ceil(math.sqrt(max(%s, 1)))), 2)" % NPTS_E
DIMS = [('b', B_E), ('deff', DEFF_E), ('nseg', NSEG_E), ('side', SIDE_E), ('samples', SAMP_E), ('npts', NPTS_E),
        ('pside', PSIDE_E)]


def D(n):
    return "float(op('dims')['%s'])" % n


SEG_UNIFORMS = [
    ('uT', (D('b'), D('deff'), D('nseg'), D('side'))),
    ('uT2', ("math.radians(parent().par.Spread.eval())", "math.radians(parent().par.Twist.eval())",
             "math.radians(parent().par.Jitter.eval())", PP.format('Ratio'))),
    ('uT3', (PP.format('Length'), "math.radians(parent().par.Sway.eval())",
             "float(op('clock')[0]) * parent().par.Swayspeed.eval()", PP.format('Progress'))),
    ('uT4', ("float(parent().par.Seed.eval())", PP.format('Lenjitter'), PP.format('Width'), PP.format('Widthratio'))),
]
MAT_UNIFORMS = [
    ('uP', (D('npts'), D('pside'), D('samples'), PP.format('Pointsize'))),
    ('uP2', (PP.format('Hue0'), PP.format('Hue1'), PP.format('Sat'), PP.format('Bright'))),
    ('uP3', (D('deff'), D('nseg'), D('side'), PP.format('Gain'))),
]
LOOK_UNIFORMS = [('uK', ("1.0 if parent().par.Composite.eval() == 'add' else 0.0", "0.0", "0.0", "0.0"))]

COMMON = """
const float TAU = 6.283185307179586;
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float h1(int i, int s) { return float(lowbias(uint(i) * 747796405u + uint(s) * 2891336453u + 1u) >> 8) / 16777216.0; }
"""

SEGS = """// POP_tree segs (compute, T-47): one thread per texel; texel 2x = start xyz + level, 2x+1 = end xyz + width of
// segment k = y * side + x. Each thread walks k's ancestors (BFS: parent (k-1)/B) then composes from the root.
// Mirror: pop_tree_logic.segments / texture.
layout (local_size_x = 8, local_size_y = 8) in;
#define MAXD 20
uniform vec4 uT;    // branches, depth eff, nseg, side
uniform vec4 uT2;   // spread rad, twist rad, jitter rad, ratio
uniform vec4 uT3;   // trunk length, sway rad, sway time, progress
uniform vec4 uT4;   // seed, length jitter, width, width ratio
""" + COMMON + """
mat3 rx(float a) { float c = cos(a), s = sin(a); return mat3(1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c); }
mat3 ry(float a) { float c = cos(a), s = sin(a); return mat3(c, 0.0, -s, 0.0, 1.0, 0.0, s, 0.0, c); }
mat3 rz(float a) { float c = cos(a), s = sin(a); return mat3(c, s, 0.0, -s, c, 0.0, 0.0, 0.0, 1.0); }
void main()
{
    ivec2 T = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (T.x >= sz.x || T.y >= sz.y) return;
    int B = int(uT.x + 0.5), Dp = int(uT.y + 0.5), N = int(uT.z + 0.5), side = int(uT.w + 0.5);
    int x = T.x / 2;
    bool isEnd = (T.x & 1) == 1;
    int k = T.y * side + x;
    if (x >= side || k >= N) { TDImageStoreOutput(0, ivec3(T, 0), vec4(0.0, 0.0, 0.0, isEnd ? 0.0 : -1.0)); return; }
    int nodes[MAXD];
    int L = 0;
    int kk = k;
    for (int s = 0; s < MAXD; s++) {
        if (kk <= 0) break;
        nodes[s] = kk;
        kk = (kk - 1) / B;
        L = s + 1;
    }
    int seed = int(uT4.x + 0.5);
    vec3 p = vec3(0.0);
    mat3 R = mat3(1.0);
    float len = uT3.x;
    for (int s = 0; s < MAXD; s++) {
        int q = L - 1 - s;
        if (q < 0) break;
        p += R[1] * len;                                   // parent end (full length)
        int n = nodes[q];
        float lev = float(s + 1);
        int slot = (n - 1) % B;
        float phi = float(slot) * TAU / float(B) + lev * uT2.y + uT2.z * (2.0 * h1(n, seed) - 1.0);
        float spr = uT2.x + uT2.z * (2.0 * h1(n, seed + 1) - 1.0);
        float sw = uT3.y * sin(uT3.z + lev * 0.7) * lev / float(max(Dp, 1));
        R = R * ry(phi) * rz(sw) * rx(spr);
        len *= uT2.w * (1.0 + uT4.y * (2.0 * h1(n, seed + 2) - 1.0));
    }
    float g = clamp(uT3.w * float(Dp + 1) - float(L), 0.0, 1.0);
    vec4 o = isEnd ? vec4(p + R[1] * (len * g), uT4.z * pow(uT4.w, float(L))) : vec4(p, float(L));
    TDImageStoreOutput(0, ivec3(T, 0), o);
}
"""

VCOMMON = """
vec3 hsv2rgb(vec3 c)
{
    vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
    return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}
vec4 segcol(float lev)
{
    float lv = lev / max(uP3.x, 1.0);
    return vec4(hsv2rgb(vec3(mix(uP2.x, uP2.y, lv), uP2.z, uP2.w)) * uP3.w, uP3.w);
}
"""

VERTEX = """// POP_tree points vertex: Grid POP point i -> segment i / S, sample i % S at (j + 0.5) / S along it.
uniform vec4 uP;    // npts, pside, samples, point size
uniform vec4 uP2;   // hue root, hue tips, sat, bright
uniform vec4 uP3;   // depth eff, nseg, seg side, gain
uniform sampler2D sSeg;
out Vertex { vec4 color; } oV;
""" + VCOMMON + """
void main()
{
    int ps = int(uP.y + 0.5);
    ivec2 t = ivec2(floor((TDPos().xy + 0.5) * float(ps - 1) + 0.5));   // T-112: TDPos, never raw P
    int i = t.y * ps + t.x;
    int S = max(int(uP.z + 0.5), 1), N = int(uP3.y + 0.5), side = max(int(uP3.z + 0.5), 1);
    int k = i / S;
    int j = i - k * S;
    vec4 clip = vec4(2.0, 2.0, 0.0, 1.0);
    vec4 col = vec4(0.0);
    if (i < int(uP.x + 0.5) && k < N) {
        ivec2 c0 = ivec2(2 * (k % side), k / side);
        vec4 s0 = texelFetch(sSeg, c0, 0);
        vec4 s1 = texelFetch(sSeg, c0 + ivec2(1, 0), 0);
        if (distance(s0.xyz, s1.xyz) > 1e-7) {
            clip = TDWorldToProj(TDDeform(mix(s0.xyz, s1.xyz, (float(j) + 0.5) / float(S))));
            col = segcol(s0.w);
        }
    }
    gl_Position = clip;
    gl_PointSize = max(uP.w, 1.0);
    oV.color = col;
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

LVERTEX = """// POP_tree lines vertex (LIVE CHECK gated): Grid POP 2 rows x N cols, liney only; column i = segment i,
// row 0 = start, row 1 = end.
uniform vec4 uP;
uniform vec4 uP2;
uniform vec4 uP3;
uniform sampler2D sSeg;
out Vertex { vec4 color; } oV;
""" + VCOMMON + """
void main()
{
    int N = int(uP3.y + 0.5), side = max(int(uP3.z + 0.5), 1);
    vec3 P0 = TDPos();
    int k = int(floor((P0.x + 0.5) * float(max(N, 2) - 1) + 0.5));
    int r = P0.y > 0.0 ? 1 : 0;
    vec4 clip = vec4(2.0, 2.0, 0.0, 1.0);
    vec4 col = vec4(0.0);
    if (k < N) {
        ivec2 c0 = ivec2(2 * (k % side), k / side);
        vec4 s0 = texelFetch(sSeg, c0, 0);
        vec4 s1 = texelFetch(sSeg, c0 + ivec2(1, 0), 0);
        clip = TDWorldToProj(TDDeform(r == 0 ? s0.xyz : s1.xyz));
        col = segcol(s0.w);
    }
    gl_Position = clip;
    oV.color = col;
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

PIXEL = """// POP_tree pixel: colour through, additive one/one.
in Vertex { vec4 color; } iV;
layout(location = 0) out vec4 fragColor;
void main() { fragColor = iV.color; }
"""

LOOK = """// POP_tree look (compute): render alone or added over in1 (premultiplied).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uK;    // composite add, -, -, -
void main()
{
    ivec2 T = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (T.x >= sz.x || T.y >= sz.y) return;
    vec2 uv = (vec2(T) + 0.5) / vec2(sz);
    vec4 r = texture(sTD2DInputs[0], uv);
    vec4 o = vec4(r.rgb, clamp(r.a, 0.0, 1.0));
    if (uK.x > 0.5) {
        vec4 b = texture(sTD2DInputs[1], uv);
        o = vec4(b.rgb + r.rgb, max(b.a, o.a));
    }
    TDImageStoreOutput(0, ivec3(T, 0), o);
}
"""

CAM = {'ty': PP.format('Camheight'), 'tz': PP.format('Dist'), 'viewanglemethod': ('menu', 'vertfov'),
       'fov': PP.format('Fov'), 'near': 0.01, 'far': 200.0}


def shader_texts():
    return {'segs': SEGS, 'vertex': VERTEX, 'lvertex': LVERTEX, 'pixel': PIXEL, 'look': LOOK}


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_tree (TC-18): GPU branching tree (implicit B-ary, Depth levels, <= 262k segments) '
                                 'computed in one compute pass (each thread walks its ancestors), drawn as points dust '
                                 '(or lines, gated). Amount 0 = in1 untouched. Out: out1 look, out2 segs texture.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    if first:
        _apply_first(c, FIRST)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Background for Composite add.'
    clk = _clock(c, 'clock', "parent().par.Speed.eval()")
    dims = _mk(c, constantCHOP, 'dims')
    for i, (n, e) in enumerate(DIMS):
        getattr(dims.par, 'name%d' % i).val = n
        _expr(getattr(dims.par, 'value%d' % i), e)
    dims.comment = 'b deff nseg side samples npts pside: the caps (segments <= 262144, points <= 1M) live here.'
    segs = _compute(c, 'segs', SEGS, [], "2 * int(op('dims')['side'])", "int(op('dims')['side'])",
                    fmt='rgba32float', spec=SEG_UNIFORMS)
    segs.comment = 'Texel 2x = start xyz + level, 2x+1 = end xyz + width (segment y * side + x). One pass, no state.'
    out2 = _mk(c, outTOP, 'out2')
    _wire(segs, out2)
    pts = _grid(c, 'pts', "int(op('dims')['pside'])", "int(op('dims')['pside'])", 'points')
    pts.comment = 'Static pside x pside points: point i = sample i % S of segment i / S. The draw POP.'
    m = _mat(c, 'mat', VERTEX, PIXEL, samplers=[('sSeg', 'segs', 'nearest')], spec=MAT_UNIFORMS, blend='add',
             depth=False)
    m.comment = 'Dust: fetch the segment, place the sample, colour by level (hue root -> tips), additive.'
    geo = _geo(c, 'geo', 'pts', 'mat')
    lg = _grid(c, 'lines_grid', "max(int(op('dims')['nseg']), 2)", "2", 'lines')
    lg.par.linex = False
    lg.par.liney = True
    lg.comment = 'LIVE CHECK gated (Lines): 2 rows x N cols, vertical lines only: column i = segment i.'
    lm = _mat(c, 'lmat', LVERTEX, PIXEL, samplers=[('sSeg', 'segs', 'nearest')], spec=MAT_UNIFORMS, blend='add',
              depth=False)
    lm.comment = 'Lines: row 0 -> start, row 1 -> end of segment column.'
    lgeo = _geo(c, 'geo_lines', 'lines_grid', 'lmat')
    for g_ in (geo, lgeo):
        _expr(g_.par.ry, "parent().par.Orbit.eval() + parent().par.Spin.eval() * float(op('clock')[0])")
    cam = _cam(c, 'cam', CAM)
    cam.comment = 'At (0, Camheight, Dist) looking -z; the tree grows up +y from the origin.'
    r = _render(c, 'render', 'cam', 'geo', fmt='rgba16float', aa='aa1')
    _expr(r.par.geometry, "'geo_lines' if parent().par.Lines.eval() else 'geo'")
    r.comment = 'Dust (or lines) additive, rgba16f.'
    lk = _compute(c, 'look', LOOK, [r, in1], RESW, RESH, fmt='rgba16float', spec=LOOK_UNIFORMS, filt='linear')
    _out_switch(c, in1, lk)
    stages = [
        {'title': '1 In + clock + dims', 'role': 'input', 'ops': ['in1', 'clock_rate', 'clock', 'dims'],
         'body': 'clock = sway / spin time. dims = segment / point counts with the hard caps.'},
        {'title': '2 Segments (one compute pass)', 'role': 'process', 'ops': ['segs', 'segs_compute', 'out2'],
         'body': 'Each texel walks its node ancestors from the root: start / end of every segment.'},
        {'title': '3 Draw (static Grid POPs)', 'role': 'process',
         'ops': ['pts', 'mat', 'mat_vertex', 'mat_pixel', 'geo', 'lines_grid', 'lmat', 'lmat_vertex', 'lmat_pixel',
                 'geo_lines', 'cam', 'render'],
         'body': 'Dust points (default) or lines (gated) read segs; additive render.'},
        {'title': '4 Look + out', 'role': 'output', 'ops': ['look', 'look_compute', 'out_sel', 'out1'],
         'body': 'Alone or add over in1. Amount 0 = in1 untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
