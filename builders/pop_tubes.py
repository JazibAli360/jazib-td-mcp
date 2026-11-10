# pop_tubes - POP_tubes (BUILD_PLAN_27OCT lane H, row FX7b TC-08 "light-trail tubes", the Trail POP + Skin POP
# geometry; Depth Buffer Studio "Neo City", SARV "Skin your Trails"). Glowing tapering 3D tubes along moving heads,
# colour running along each trail. The flat-line version of the look already exists (lane G: PX_lines on BO_particles);
# this is the TUBE geometry. Doc + LIVE CHECKS: docs/builds/pop_lane_h.md "TC-08".
# Route A (default, lowest risk, decided offline 27 Oct): history texture K samples x N tracks (rgba32f: xyz + time
# stamp, column 0 = head) updated by ONE compute pass per frame as a shift through a Feedback TOP (order-free; an
# in-place shift would race between threads) -> ONE static tall Grid POP (quads, Samples cols x Tracks x (Sides + 3)
# rows; per track Sides + 1 ring rows + 2 seam rows: the seam quads are either zero-area or discarded in the pixel
# shader) drawn with a GLSL MAT whose vertex shader builds the ring from the central-difference tangent and a
# Gram-Schmidt frame (same sharp-curve limits as Skin POP on 31550: keep curves smooth). No instancing (one more
# untested POP feature on 31550), no Trail / Skin POP, no POP compute (T-124). numpy mirror: builders/pop_tubes_logic.py.
# Route B (optional, build(..., native=True)): sub-COMP `native` with the literal chain Point Generator POP -> Particle
# POP (32) -> Trail POP (30 frames, rows) -> Skin POP -> geo -> render, pars set once, allowCooking OFF until the one
# structured LIVE probe (pop_lane_h.md TC-08 B).
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_tubes.py').read(), ns); ns['build']('/project1/lab', first=True)
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())

NAME = 'POP_tubes'
SOURCES = ['lissajous', 'vortex', 'flow', 'input']
PALETTES = ['neon', 'fire', 'ice', 'white']
PAL = [((0.2, 1.0, 0.9), (0.9, 0.1, 1.0)), ((1.0, 0.9, 0.4), (1.0, 0.1, 0.0)), ((0.9, 1.0, 1.0), (0.1, 0.3, 1.0)),
       ((1.0, 1.0, 1.0), (0.6, 0.6, 0.6))]
WIRED = ("1.0 if any(len(cn.connections) for cn in parent().inputConnectors "
         "if cn.inOP is not None and cn.inOP.name == 'in2') else 0.0")

PAGES = [
    ('Tubes', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Route', 'Menu', 'tubes', {'names': ['tubes', 'native'], 'labels': ['Tubes (history texture + MAT)',
                                                                         'Native Trail + Skin POP (probe)']}),
        ('Source', 'Menu', 'lissajous', {'names': SOURCES, 'labels': ['Lissajous paths', 'Vortex', 'Flow field',
                                                                      'in2 xyz TOP (texel i = track i)']}),
        ('Play', 'Toggle', True, {'label': 'Play'}),
        ('Reset', 'Pulse', None, {'label': 'Reset trails'}),
        ('Speed', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Speed'}),
        ('Scale', 'Float', 0.6, {'min': 0.05, 'max': 3, 'label': 'Path scale'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
        ('Tracks', 'Int', 64, {'min': 1, 'max': 256, 'clampmin': 1, 'clampmax': 256, 'label': 'Tracks'}),
        ('Samples', 'Int', 64, {'min': 2, 'max': 128, 'clampmin': 2, 'clampmax': 128, 'label': 'Samples per trail'}),
        ('Sides', 'Int', 8, {'min': 3, 'max': 16, 'clampmin': 3, 'clampmax': 16, 'label': 'Tube sides'}),
        ('Radius', 'Float', 0.012, {'min': 0, 'max': 0.1, 'label': 'Tube radius at the head'}),
        ('Taper', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Taper exponent'}),
        ('Resetat', 'Float', -100.0, {'min': -100, 'max': 100, 'label': 'internal: frame of the last Reset'}),
    ]),
    ('Look', [
        ('Palette', 'Menu', 'neon', {'names': PALETTES, 'labels': ['Neon', 'Fire', 'Ice', 'White']}),
        ('Fade', 'Float', 1.5, {'min': 0, 'max': 6, 'label': 'Fade along the trail (exponent)'}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Gain'}),
        ('Halo', 'Float', 0.6, {'min': 0, 'max': 3, 'label': 'Halo (render mips, no Bloom TOP)'}),
        ('Spin', 'Float', 6.0, {'min': -90, 'max': 90, 'label': 'Spin deg / s'}),
        ('Dist', 'Float', 2.4, {'min': 0.5, 'max': 10, 'label': 'Camera distance'}),
        ('Zoom', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Zoom'}),
        ('Msaa', 'Menu', 'aa4', {'names': ['aa1', 'aa2', 'aa4', 'aa8'], 'labels': ['1x (cheapest)', '2x', '4x',
                                                                              '8x'],
                                 'label': 'Render MSAA (1x saves ~0.6 ms GPU, aliased tube edges)'}),
    ]),
    OUT_PAGE,
]
PANEL_PAGES = ['Tubes', 'Look']
FIRST = {'Tracks': 16, 'Samples': 32, 'Sides': 6}

ROWS_E = "parent().par.Tracks.eval() * (parent().par.Sides.eval() + 3)"
HIST_UNIFORMS = [
    ('uH', ("float(parent().par.Source.menuIndex)", "float(op('clock')[0])", "1.0 if parent().par.Play.eval() else 0.0",
            "1.0 if absTime.frame - parent().par.Resetat.eval() < 2 else 0.0")),
    ('uH2', ("float(parent().par.Tracks.eval())", "float(parent().par.Samples.eval())", PP.format('Scale'),
             "float(parent().par.Seed.eval())")),
    ('uH3', (WIRED, "0.0", "0.0", "0.0")),
]


def _pal(k):
    return "%r[parent().par.Palette.menuIndex][%d][%d]" % ([[list(a), list(b)] for a, b in PAL], k // 3, k % 3)


MAT_UNIFORMS = [
    ('uT', ("float(parent().par.Tracks.eval())", "float(parent().par.Samples.eval())",
            "float(parent().par.Sides.eval())", PP.format('Radius'))),
    ('uT2', (PP.format('Taper'), "float(" + ROWS_E + ")", PP.format('Fade'), PP.format('Gain'))),
    ('uC1', (_pal(0), _pal(1), _pal(2), "0.0")),
    ('uC2', (_pal(3), _pal(4), _pal(5), "0.0")),
]
LOOK_UNIFORMS = [('uL', (PP.format('Halo'), "0.0", "0.0", "0.0"))]

HASH = """
const float TAU = 6.283185307179586;
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float h1(int i, int s) { return float(lowbias(uint(i) * 747796405u + uint(s) * 2891336453u + 1u) >> 8) / 16777216.0; }
"""

HIST = """// POP_tubes history (compute, T-47): K samples (x) x N tracks (y), rgba32f xyz + time stamp; column 0 = head.
// in0 = last frame (hist_fb), in1 = xyz source (in2 or blank). Mirror: pop_tubes_logic.head / shift / init_hist.
uniform vec4 uH;    // source, time, play, reset
uniform vec4 uH2;   // tracks, samples, scale, seed
uniform vec4 uH3;   // in2 wired
layout(local_size_x = 8, local_size_y = 8) in;
""" + HASH + """
vec3 headp(int src, int i, float t, vec4 prev)
{
    int s = int(uH2.w + 0.5);
    float sc = uH2.z;
    float f1 = 0.7 + 0.6 * h1(i, s), f2 = 0.9 + 0.6 * h1(i, s + 1), f3 = 0.5 + 0.5 * h1(i, s + 2);
    float p1 = TAU * h1(i, s + 3), p2 = TAU * h1(i, s + 4), p3 = TAU * h1(i, s + 5);
    if (src == 3 && uH3.x > 0.5) {
        ivec2 isz = textureSize(sTD2DInputs[1], 0);
        int w = max(isz.x, 1);
        ivec2 tx = ivec2(i % w, min(i / w, max(isz.y - 1, 0)));
        return texelFetch(sTD2DInputs[1], tx, 0).xyz * sc;
    }
    if (src == 1) {
        float a = TAU * 0.25 * t * (0.5 + f1) + p1;
        float rr = 0.2 + 0.4 * h1(i, s + 6);
        float y = 0.8 * (2.0 * h1(i, s + 7) - 1.0) + 0.1 * sin(TAU * 0.1 * t + p2);
        return vec3(rr * cos(a), y, rr * sin(a)) * sc;
    }
    if (src == 2) {
        vec3 q = prev.xyz / max(sc, 1e-6);
        vec3 v = vec3(sin(2.1 * q.y + p1) + cos(1.7 * q.z), sin(1.9 * q.z + p2) + cos(2.3 * q.x),
                      sin(2.2 * q.x + p3) + cos(1.6 * q.y)) * 0.5 - 0.3 * q;
        return (q + v * clamp(t - prev.w, 0.0, 0.1)) * sc;
    }
    float w = TAU * 0.25 * t;
    return vec3(0.6 * sin(w * f1 + p1), sin(w * f2 + p2), 0.6 * sin(w * f3 + p3)) * sc;
}
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= sz.x || p.y >= sz.y) return;
    int src = int(uH.x + 0.5);
    float t = uH.y;
    bool same = textureSize(sTD2DInputs[0], 0) == sz;
    if (uH.w > 0.5 || !same) {
        int s0 = (src == 2) ? 0 : src;                      // flow starts on the Lissajous point
        TDImageStoreOutput(0, ivec3(p, 0), vec4(headp(s0, p.y, t, vec4(0.0)), t));
        return;
    }
    if (uH.z < 0.5) { TDImageStoreOutput(0, ivec3(p, 0), texelFetch(sTD2DInputs[0], p, 0)); return; }
    if (p.x == 0) {
        vec4 prev = texelFetch(sTD2DInputs[0], ivec2(0, p.y), 0);
        TDImageStoreOutput(0, ivec3(p, 0), vec4(headp(src, p.y, t, prev), t));
    } else {
        TDImageStoreOutput(0, ivec3(p, 0), texelFetch(sTD2DInputs[0], ivec2(p.x - 1, p.y), 0));
    }
}
"""

VERTEX = """// POP_tubes vertex (TC-08 route A): static tall Grid POP -> tube rings along the history. Mirror: pop_tubes_logic.vertex
uniform sampler2D sH;
uniform vec4 uT;    // tracks, samples, sides, radius
uniform vec4 uT2;   // taper, rows, fade, gain
uniform vec4 uC1;   // head colour
uniform vec4 uC2;   // tail colour
out Vertex { vec4 color; vec3 wn; float gap; } oV;
const float TAU = 6.283185307179586;
vec3 hp(int i, int k) { return texelFetch(sH, ivec2(k, i), 0).xyz; }
void main()
{
    int n = int(uT.x + 0.5), K = int(uT.y + 0.5), S = int(uT.z + 0.5), rows = int(uT2.y + 0.5);
    vec2 uv = TDPos().xy + 0.5;                 // T-112: TDPos, never raw P
    ivec2 g = ivec2(floor(uv * vec2(float(K - 1), float(rows - 1)) + 0.5));
    int per = S + 3;
    int i = g.y / per, j = g.y - (g.y / per) * per, k = clamp(g.x, 0, K - 1);
    float gap = 0.0;
    if (j == S + 1) { j = S; gap = 1.0; }
    else if (j == S + 2) { i = min(i + 1, n - 1); j = 0; gap = 1.0; }
    vec3 T = hp(i, max(k - 1, 0)) - hp(i, min(k + 1, K - 1));
    T = length(T) > 1e-8 ? normalize(T) : vec3(0.0, 0.0, 1.0);
    vec3 up = abs(T.y) > 0.99 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
    vec3 N = normalize(up - dot(up, T) * T);
    vec3 B = cross(T, N);
    float a = TAU * float(j) / float(S);
    float x = float(k) / max(float(K - 1), 1.0);
    float r = uT.w * pow(max(1.0 - x, 0.0), uT2.x);
    vec3 rn = cos(a) * N + sin(a) * B;
    vec4 w = TDDeform(hp(i, k) + r * rn);
    float f = pow(max(1.0 - x, 0.0), uT2.z) * uT2.w;
    oV.color = vec4(mix(uC1.rgb, uC2.rgb, x) * f, f);
    oV.wn = normalize(TDDeformNorm(rn));
    oV.gap = gap;
    gl_Position = TDWorldToProj(w);
    // Perf 27 Oct: the seam quad between track i's last ring and track i + 1's first ring spans the screen; all
    // four of its vertices are gap vertices, so a negative clip distance drops it before rasterisation (it was
    // filled and discarded per pixel: ~1.2 ms GPU at 64 tracks). Ring quads never touch a gap vertex; out1 bit-exact.
    gl_ClipDistance[0] = gap > 0.5 ? -1.0 : 1.0;
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

PIXEL = """// POP_tubes pixel: seam quads discarded; emissive colour, brighter where the tube faces the camera. Additive.
in Vertex { vec4 color; vec3 wn; float gap; } iV;
layout(location = 0) out vec4 fragColor;
void main()
{
    TDCheckDiscard();
    if (iV.gap > 0.5) discard;
    float facing = abs(normalize(iV.wn).z);
    fragColor = TDOutputSwizzle(vec4(iV.color.rgb * (0.55 + 0.45 * facing), iV.color.a));
}
"""

LOOK = """// POP_tubes look (compute): render + Halo x (mip 2 + mip 4) / 2. in0 = render (inputfiltertype mipmap).
uniform vec4 uL;    // halo
layout(local_size_x = 8, local_size_y = 8) in;
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec2 uv = (vec2(p) + 0.5) / vec2(sz);
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    vec4 h = 0.5 * (textureLod(sTD2DInputs[0], uv, 2.0) + textureLod(sTD2DInputs[0], uv, 4.0));
    TDImageStoreOutput(0, ivec3(p, 0), c + uL.x * h);
}
"""

NATIVE_VERT = """// POP_tubes native probe MAT (route B): position only, flat colour (no attribute assumptions).
out Vertex { float d; } oV;
void main()
{
    vec4 w = TDDeform(TDPos());
    oV.d = 1.0;
    gl_Position = TDWorldToProj(w);
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

NATIVE_PIXEL = """// POP_tubes native probe pixel.
in Vertex { float d; } iV;
layout(location = 0) out vec4 fragColor;
void main()
{
    TDCheckDiscard();
    fragColor = TDOutputSwizzle(vec4(0.2, 1.0, 0.9, 1.0) * iV.d);
}
"""

PULSES = """# POP_tubes pulses: Reset stamps the frame; hist writes every column = head for 2 frames (uH.w).
def onPulse(par):
    if par.name == 'Reset':
        par.owner.par.Resetat = absTime.frame
    return
"""

CAM = {'tz': PP.format('Dist'), 'viewanglemethod': ('menu', 'vertfov'),
       'fov': "40.0 / max(parent().par.Zoom.eval(), 0.01)", 'near': 0.01, 'far': 100.0}

# Route B: (op class name, op name, {par: constant}); counts tiny and set once (no live changes).
NATIVE_CHAIN = [
    ('pointgeneratorPOP', 'pts', {'shape': 'sphere', 'numpoints': 32, 'distribution': 'surface', 'sizex': 0.5,
                                  'sizey': 0.5, 'sizez': 0.5}),
    ('particlePOP', 'parts', {'maxparticles': 32, 'birthrate': 16.0, 'life': 2.0, 'initvelocityy': 0.3}),
    ('trailPOP', 'trail', {'length': 30.0, 'lengthunit': 'frames', 'surftype': 'rows'}),
    ('skinPOP', 'skin', {}),
]


def shader_texts():
    return {'hist': HIST, 'vertex': VERTEX, 'pixel': PIXEL, 'look': LOOK, 'native_vertex': NATIVE_VERT,
            'native_pixel': NATIVE_PIXEL}


def _native(c):
    """Route B sub-COMP. allowCooking stays OFF: the LIVE probe turns it on once (pop_lane_h.md TC-08 B)."""
    nc = c.op('native') or c.create(baseCOMP, 'native')
    nc.allowCooking = False
    nc.comment = ('Route B probe: Point Generator POP (32) -> Particle POP (32) -> Trail POP (30 frames, rows) -> Skin '
                  'POP -> geo -> render. Pars set once; allowCooking OFF until the structured probe.')
    prev = None
    for cls_name, n, pars in NATIVE_CHAIN:
        o = _mk(nc, eval(cls_name), n)            # TD class by name (td module)
        for k, v in pars.items():
            _try(o, k, v)
        if prev is not None:
            _wire(prev, o)
        prev = o
    _mat(nc, 'mat', NATIVE_VERT, NATIVE_PIXEL, blend='add', depth=False)
    _geo(nc, 'geo', 'skin', 'mat')
    cam = _cam(nc, 'cam', {'tz': 2.4, 'viewanglemethod': ('menu', 'vertfov'), 'fov': 40.0})
    r = _render(nc, 'render', 'cam', 'geo', w=1080, h=1920, fmt='rgba16float', aa='aa1')
    return nc, r


def build(parent_path='/project1/lab', panel=True, first=False, native=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_tubes (TC-08 geometry): tapering 3D light tubes along Tracks moving heads '
                                 '(Lissajous / vortex / flow / in2 xyz TOP). History texture + one static tall Grid '
                                 'POP whose MAT builds the rings. Pulse Reset. Out: out1, out2 = history.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    if first:
        _apply_first(c, FIRST)
    c.par.Resetat = absTime.frame
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Passthrough when Amount 0.'
    in2 = _mk(c, inTOP, 'in2')
    in2.comment = 'Optional xyz TOP (Source input): texel i (row-major) = head of track i, e.g. BO_particles state.'
    pe = _mk(c, parameterexecuteDAT, 'pulses')
    if pe.text != PULSES:
        pe.text = PULSES
    pe.par.op = c
    pe.par.pars = 'Reset'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = False
    pe.par.onpulse = True
    clk = _clock(c, 'clock', "parent().par.Speed.eval()")
    sclk = _clock(c, 'spin', "parent().par.Spin.eval()")
    sclk.comment = 'Spin angle (deg).'
    blank = _blank(c, 'blank', "parent().par.Samples.eval()", "parent().par.Tracks.eval()", 'rgba32float')
    xb = _blank(c, 'xyz_blank', 1, 1, 'rgba32float')
    xs = _mk(c, switchTOP, 'xyz_sel')
    _wire(xb, xs, 0)
    _wire(in2, xs, 1)
    _expr(xs.par.index, "int(" + WIRED + ")")
    fb = _feedback(c, 'hist_fb', 'hist', blank)
    h = _compute(c, 'hist', HIST, [fb, xs], "parent().par.Samples.eval()", "parent().par.Tracks.eval()",
                 'rgba32float', HIST_UNIFORMS)
    h.comment = 'History shift: column 0 = new head, k = last frame k - 1 (Play off = hold, Reset = all = head).'
    o2 = _mk(c, outTOP, 'out2')
    _wire(h, o2)
    g = _grid(c, 'tubes', "parent().par.Samples.eval()", ROWS_E, 'quads')
    g.comment = 'Static Samples x Tracks*(Sides+3) quads: per track Sides+1 ring rows + 2 seam rows (hidden).'
    m = _mat(c, 'mat', VERTEX, PIXEL, samplers=[('sH', 'hist', 'nearest')], spec=MAT_UNIFORMS, blend='add',
             depth=False)
    m.comment = 'Vertex: ring around the history polyline (tangent + Gram-Schmidt frame), taper. Pixel: emissive.'
    geo = _geo(c, 'geo', 'tubes', 'mat')
    _expr(geo.par.ry, "float(op('spin')[0])")
    cam = _cam(c, 'cam', CAM)
    r = _render(c, 'render', 'cam', 'geo', fmt='rgba16float', aa='aa4')
    _expr(r.par.antialias, "parent().par.Msaa.eval()")
    r.comment = 'Tubes, additive (premultiplied light on transparent). MSAA = Msaa (Look page, default 4x).'
    lk = _compute(c, 'look', LOOK, [r], RESW, RESH, 'rgba16float', LOOK_UNIFORMS, filt='mipmap')
    lk.comment = 'render + Halo x mips (no Bloom TOP: ~2 ms at 1080x1920, lane G G7).'
    extra = []
    if native:
        _native(c)
        ns_ = _mk(c, selectTOP, 'native_sel')
        ns_.par.top = 'native/render'
        extra = [ns_]
    s, o = _out_switch(c, in1, lk, extra=extra)
    if native:
        _expr(s.par.index, "0 if parent().par.Amount.eval() <= 0 else (2 if parent().par.Route.eval() == 'native' "
                           "else 1)")
    stages = [
        {'title': '1 In + control', 'role': 'input',
         'ops': ['in1', 'in2', 'pulses', 'clock_rate', 'clock', 'spin_rate', 'spin', 'xyz_blank', 'xyz_sel'],
         'body': 'in2 = optional xyz TOP. pulses: Reset. clock = module time, spin = angle.'},
        {'title': '2 History', 'role': 'process', 'ops': ['blank', 'hist_fb', 'hist', 'hist_compute', 'out2'],
         'body': 'hist_fb -> hist (shift, head in column 0).'},
        {'title': '3 Tubes (static Grid POP)', 'role': 'process', 'ops': ['tubes', 'mat', 'mat_vertex', 'mat_pixel',
                                                                         'geo'],
         'body': 'Grid POP quads -> rings in the MAT; seam quads discarded.'},
        {'title': '4 Render + look + out', 'role': 'output',
         'ops': ['cam', 'render', 'look', 'look_compute', 'native', 'native_sel', 'out_sel', 'out1'],
         'body': 'Halo from render mips. Amount 0 = in1 untouched. Route native = probe sub-COMP.'},
    ]
    for st_ in stages:                      # native / native_sel exist only with native=True (live 27 Oct: layout
        st_['ops'] = [n for n in st_['ops'] if c.op(n) is not None]     # failed on the missing op names)
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
