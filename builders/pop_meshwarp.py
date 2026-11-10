# pop_meshwarp - POP_meshwarp (BUILD_PLAN_27OCT lane H, row FX7b TC-07 "POP mesh warp via Tex", elekktronaut T80).
# A clip mapped on a dense grid whose texture coordinates and depth are bent: ripple, swirl, slice, melt, wave, bulge,
# noise, with real 3D depth (tilt / orbit the sheet). Doc + LIVE CHECKS: docs/builds/pop_lane_h.md "TC-07".
# Route (lowest risk, decided offline 27 Oct): ONE static Grid POP (quads, Cols x Rows, Tex = point, pars set at build
# only) -> geo (Select POP) -> GLSL MAT whose VERTEX shader does the warp (uv' + dz + finite-difference normal) and
# whose pixel shader samples in1 at uv'. No POP filter chain on Tex, no POP compute, no attribute layout (T-124): the
# Tex-attribute POP chain of T80 is the same maths moved into the MAT. numpy mirror: builders/pop_meshwarp_logic.py.
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_meshwarp.py').read(), ns); ns['build']('/project1/lab')
# build(parent_path, panel=True, first=False): first=True applies FIRST (small grid) before any render op. Idempotent (ops reused by name, texts / pars / wires re-set, user par values kept).
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())

NAME = 'POP_meshwarp'
MODES = ['ripple', 'swirl', 'slice', 'melt', 'wave', 'bulge', 'noise']
MODE_LABELS = ['Ripple (rings from the centre)', 'Swirl (twist round the centre)', 'Slice (bands shift on a clock)',
               'Melt (columns drip down)', 'Wave (travelling sheet wave)', 'Bulge (lens round the centre)',
               'Noise (value-noise wobble)']

PAGES = [
    ('Meshwarp', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Mode', 'Menu', 'ripple', {'names': MODES, 'labels': MODE_LABELS}),
        ('Strength', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Strength'}),
        ('Freq', 'Float', 3.0, {'min': 0, 'max': 20, 'label': 'Frequency'}),
        ('Speed', 'Float', 0.25, {'min': -2, 'max': 2, 'label': 'Speed (cycles / s)'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre u'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre v'}),
        ('Radius', 'Float', 0.5, {'min': 0.01, 'max': 2, 'label': 'Radius (sheet heights)'}),
        ('Depth', 'Float', 0.3, {'min': 0, 'max': 2, 'label': 'Depth (z out of the sheet)'}),
        ('Uvwarp', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Texture warp'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
    ]),
    ('Sheet', [
        ('Cols', 'Int', 128, {'min': 8, 'max': 512, 'clampmin': 2, 'clampmax': 512, 'label': 'Grid columns'}),
        ('Rows', 'Int', 228, {'min': 8, 'max': 912, 'clampmin': 2, 'clampmax': 912, 'label': 'Grid rows'}),
        ('Tilt', 'Float', 0.0, {'min': -80, 'max': 80, 'label': 'Tilt deg (x)'}),
        ('Orbit', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Orbit deg (y)'}),
        ('Roll', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Roll deg (z)'}),
        ('Dist', 'Float', 1.2, {'min': 0.2, 'max': 5, 'label': 'Camera distance'}),
        ('Zoom', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Zoom (1 = sheet fills the frame)'}),
        ('Shade', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Shading from the bent normal'}),
        ('Edge', 'Menu', 'hold', {'names': ['hold', 'zero'], 'labels': ['Hold edge pixels', 'Transparent outside']}),
        ('Wire', 'Toggle', False, {'label': 'Wireframe (MAT wireframe, 1 px on macOS)'}),
    ]),
    OUT_PAGE,
]
PANEL_PAGES = ['Meshwarp', 'Sheet']
FIRST = {'Cols': 64, 'Rows': 114}     # first-frame safe values (docs/builds/pop_lane_h.md "TC-07")

UNIFORMS = [
    ('uW', ("float(parent().par.Mode.menuIndex)", PP.format('Strength'), PP.format('Freq'),
            "float(op('clock')[0])")),
    ('uW2', (PP.format('Centerx'), PP.format('Centery'), PP.format('Radius'),
             "parent().par.Depth.eval() * parent().par.Amount.eval()")),
    ('uW3', ("parent().par.Resw.eval() / max(parent().par.Resh.eval(), 1)", PP.format('Shade'),
             "float(parent().par.Seed.eval())", "parent().par.Amount.eval() * parent().par.Uvwarp.eval()")),
    ('uW4', ("float(parent().par.Cols.eval())", "float(parent().par.Rows.eval())",
             "1.0 if parent().par.Edge.eval() == 'zero' else 0.0", "0.0")),
]

COMMON = """
const float TAU = 6.283185307179586;
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float h1(int i, int s) { return float(lowbias(uint(i) * 747796405u + uint(s) * 2891336453u + 1u) >> 8) / 16777216.0; }
float h2(int x, int y, int s)
{
    uint h = lowbias(uint(y) * 2891336453u + uint(s) * 1597334677u + 7u);
    h = lowbias(h ^ (uint(x) * 747796405u));
    return float(h >> 8) / 16777216.0;
}
float vnoise(vec2 p, int s)
{
    vec2 i = floor(p);
    vec2 f = p - i;
    vec2 w = f * f * (3.0 - 2.0 * f);
    ivec2 k = ivec2(i);
    float a = h2(k.x, k.y, s), b = h2(k.x + 1, k.y, s), c = h2(k.x, k.y + 1, s), d = h2(k.x + 1, k.y + 1, s);
    return (a + (b - a) * w.x) * (1.0 - w.y) + (c + (d - c) * w.x) * w.y;
}
// grid uv (0..1) -> xy = texture lookup uv', z = dz (sheet units). Mirror: pop_meshwarp_logic.warp
vec3 warp(vec2 uv)
{
    int m = int(uW.x + 0.5);
    float S = uW.y, F = uW.z, t = uW.w, asp = uW3.x;
    int seed = int(uW3.z + 0.5);
    vec2 q = vec2((uv.x - uW2.x) * asp, uv.y - uW2.y);
    float r = length(q);
    float R = max(uW2.z, 1e-4);
    float f = exp(-(r / R) * (r / R));
    vec2 d = vec2(0.0);
    float dz = 0.0;
    if (m == 0) {
        float h = S * sin(TAU * (F * r - t)) * f;
        vec2 dir = r > 1e-6 ? q / r : vec2(0.0);
        d = vec2(dir.x * h * 0.05 / asp, dir.y * h * 0.05);
        dz = h;
    } else if (m == 1) {
        float a = S * 3.14159265358979 * f * (0.75 + 0.25 * sin(TAU * t * 0.25));
        float ca = cos(a), sa = sin(a);
        vec2 rq = vec2(ca * q.x - sa * q.y, sa * q.x + ca * q.y);
        d = vec2((rq.x - q.x) / asp, rq.y - q.y);
        dz = 0.5 * S * f;
    } else if (m == 2) {
        int k = int(floor(uv.y * F * 8.0));
        float s = h1(k, seed + int(floor(t * 2.0))) - 0.5;
        d = vec2(S * 0.1 * s, 0.0);
        dz = S * 0.5 * s;
    } else if (m == 3) {
        float n = vnoise(vec2(uv.x * F * 24.0, 0.5), seed);
        float amt = S * 0.35 * n * (0.5 - 0.5 * cos(TAU * t * 0.1));
        d = vec2(0.0, amt * uv.y);
        dz = -0.5 * amt;
    } else if (m == 4) {
        float ph = TAU * (F * uv.x * asp + t), ph2 = TAU * (F * 0.7 * uv.y - 0.5 * t);
        dz = S * sin(ph) * cos(ph2) * 0.5;
        d = vec2(0.02 * S * cos(ph) * cos(ph2), -0.02 * S * sin(ph) * sin(ph2));
    } else if (m == 5) {
        float s = S * f;
        d = vec2(-0.5 * s * q.x / asp, -0.5 * s * q.y);
        dz = 0.5 * s;
    } else {
        vec2 b = vec2(uv.x * asp, uv.y) * F * 4.0;
        float n1 = vnoise(b + vec2(t * 0.5, 0.0), seed);
        float n2 = vnoise(b + vec2(17.3, t * 0.5), seed);
        d = vec2(0.05 * S * (n2 - 0.5), 0.05 * S * (n1 - 0.5));
        dz = S * (n1 - 0.5);
    }
    return vec3(uv + d * uW3.w, dz * uW2.w);
}
vec3 sheet(vec2 uv) { return vec3((uv.x - 0.5) * uW3.x, uv.y - 0.5, warp(uv).z); }
"""

VERTEX = """// POP_meshwarp vertex (TC-07): static Grid POP quads; warp + normal here (no POP compute, T-124).
uniform vec4 uW;    // mode, strength, freq, time
uniform vec4 uW2;   // centre u, centre v, radius, depth x amount
uniform vec4 uW3;   // aspect, shade, seed, uv warp x amount
uniform vec4 uW4;   // cols, rows, edge zero, -
out Vertex { vec2 uv; float shade; } oV;
""" + COMMON + """
void main()
{
    vec2 uv = TDPos().xy + 0.5;                 // Grid POP size 1 x 1 centred: T-112 (TDPos, never raw P)
    vec3 w = warp(uv);
    vec3 p = vec3((uv.x - 0.5) * uW3.x, uv.y - 0.5, w.z);
    vec2 e = vec2(1.0 / max(uW4.x - 1.0, 1.0), 1.0 / max(uW4.y - 1.0, 1.0));
    vec3 pu = sheet(uv + vec2(e.x, 0.0)) - p;
    vec3 pv = sheet(uv + vec2(0.0, e.y)) - p;
    vec3 n = normalize(cross(pu, pv) + vec3(0.0, 0.0, 1e-12));
    float lam = max(dot(n, normalize(vec3(0.3, 0.5, 0.8))), 0.0);
    oV.uv = w.xy;
    oV.shade = 1.0 + (0.3 + 0.7 * lam - 1.0) * uW3.y;
    gl_Position = TDWorldToProj(TDDeform(p));
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

PIXEL = """// POP_meshwarp pixel: in1 at the warped uv, premultiplied out (overlay rule).
uniform sampler2D sIn;
uniform vec4 uW4;
in Vertex { vec2 uv; float shade; } iV;
layout(location = 0) out vec4 fragColor;
void main()
{
    TDCheckDiscard();
    vec2 uv = iV.uv;
    vec2 hx = 0.5 / vec2(textureSize(sIn, 0));     // clamp to the edge TEXEL centres: clamp(uv, 0, 1) under the
    vec4 c = texture(sIn, clamp(uv, hx, 1.0 - hx)); // MAT's default repeat extend blended the opposite edge in (live)
    if (uW4.z > 0.5 && (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0)) c = vec4(0.0);
    fragColor = TDOutputSwizzle(vec4(c.rgb * iV.shade, c.a));
}
"""

CAM = {'tz': PP.format('Dist'), 'viewanglemethod': ('menu', 'vertfov'),
       'fov': "2.0 * math.degrees(math.atan(0.5 / max(parent().par.Dist.eval(), 0.01))) / "
              "max(parent().par.Zoom.eval(), 0.01)",
       'near': 0.01, 'far': 100.0}


def shader_texts():
    return {'vertex': VERTEX, 'pixel': PIXEL}


TEST_CLIP = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'   # as the FX racks
IN_WIRED = ("(1 if any(len(cn.connections) for cn in parent().inputConnectors "
            "if cn.inOP is not None and cn.inOP.name == 'in1') else 0)")


def demo_upgrade(c):
    """Existing POP_meshwarp (main / a library copy), no rebuild (drop-in, 28 Oct): test_clip + img_src (in1 when the
    COMP input is wired, else the stored clip), mat sIn and out_sel input 0 from img_src. Idempotent; -> changed."""
    changed = []
    in1 = c.op('in1')
    tc = c.op('test_clip')
    if tc is None:
        tc = c.create(moviefileinTOP, 'test_clip')
        tc.par.file = TEST_CLIP
        tc.viewer = False
        tc.nodeX, tc.nodeY = in1.nodeX, in1.nodeY - 150
        changed.append('test_clip')
    src = c.op('img_src')
    if src is None:
        src = c.create(switchTOP, 'img_src')
        src.viewer = False
        src.nodeX, src.nodeY = in1.nodeX + 150, in1.nodeY - 75
        changed.append('img_src')
    if not src.inputs or src.inputs[0] != tc or len(src.inputs) < 2 or src.inputs[1] != in1:
        src.inputConnectors[0].connect(tc)
        src.inputConnectors[1].connect(in1)
        changed.append('img_src wiring')
    if src.par.index.mode != ParMode.EXPRESSION or src.par.index.expr != IN_WIRED:
        src.par.index.expr = IN_WIRED
        src.par.index.mode = ParMode.EXPRESSION
        changed.append('img_src index')
    m = c.op('mat')
    if m is not None and m.par.sampler0top.eval() != src:
        m.par.sampler0top = 'img_src'
        changed.append('mat sIn')
    sel = c.op('out_sel')
    if sel is not None and (not sel.inputs or sel.inputs[0] != src):
        sel.inputConnectors[0].connect(src)
        changed.append('out_sel in0')
    return changed


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_meshwarp (TC-07): in1 mapped on a Cols x Rows Grid POP sheet, warped in the '
                                 'GLSL MAT vertex shader (ripple / swirl / slice / melt / wave / bulge / noise) with '
                                 'real depth; Tilt / Orbit / Roll turn the sheet. Amount 0 = in1 untouched. Out: out1.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    if first:
        _apply_first(c, FIRST)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'The clip to warp (premultiplied).'
    # drop-in (28 Oct): a copy with nothing wired shows the stored webcam clip (the FX racks' auto input), not black
    tc = _mk(c, moviefileinTOP, 'test_clip')
    tc.par.file = TEST_CLIP
    tc.comment = 'Demo picture while in1 is not wired (stored 5 s webcam clip; cooks only while selected).'
    src = _mk(c, switchTOP, 'img_src')
    src.inputConnectors[0].connect(tc)
    src.inputConnectors[1].connect(in1)
    _expr(src.par.index, IN_WIRED)
    src.comment = 'in1 when the COMP input is wired, else test_clip.'
    clk = _clock(c, 'clock', "parent().par.Speed.eval()")
    g = _grid(c, 'sheet', "parent().par.Cols.eval()", "parent().par.Rows.eval()", 'quads')
    g.comment = 'Static Cols x Rows quads (size 1 x 1, centred): the only POP; nothing POP-side changes live.'
    m = _mat(c, 'mat', VERTEX, PIXEL, samplers=[('sIn', 'img_src', 'linear')], spec=UNIFORMS, blend='over', depth=True)
    _try(m, 'wireframe', expr="'tesselated' if parent().par.Wire.eval() else 'off'")
    m.comment = 'Vertex: warp(uv) -> uv\', dz, finite-difference normal. Pixel: in1 at uv\' x shade.'
    geo = _geo(c, 'geo', 'sheet', 'mat')
    _expr(geo.par.rx, PP.format('Tilt'))
    _expr(geo.par.ry, PP.format('Orbit'))
    _expr(geo.par.rz, PP.format('Roll'))
    geo.comment = 'The sheet (Select POP of ../sheet) drawn with mat; Tilt / Orbit / Roll rotate it.'
    cam = _cam(c, 'cam', CAM)
    cam.comment = 'At z = Dist looking -z; vertical fov fills the 1-unit-tall sheet at Zoom 1.'
    r = _render(c, 'render', 'cam', 'geo', fmt='rgba16float', aa='aa4')
    r.comment = 'Sheet render (rgba16f, premultiplied, transparent background).'
    s, o = _out_switch(c, src, r)
    stages = [
        {'title': '1 In + clock', 'role': 'input', 'ops': ['in1', 'test_clip', 'img_src', 'clock_rate', 'clock'],
         'body': 'in1 = clip (test_clip while not wired). clock = module time (Speed).'},
        {'title': '2 Sheet (static Grid POP)', 'role': 'process', 'ops': ['sheet', 'mat', 'mat_vertex', 'mat_pixel',
                                                                         'geo'],
         'body': 'Grid POP quads -> mat: vertex warp + normal, pixel samples in1.'},
        {'title': '3 Render', 'role': 'process', 'ops': ['cam', 'render'], 'body': 'Camera fills the sheet at Zoom 1.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
