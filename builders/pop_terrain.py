# pop_terrain - POP_terrain (BUILD_PLAN_27OCT lane H, row FX7b TC-19 "terrain flyover with clipmap LOD", Artcraft
# Grid POP LOD). Endless fly-over landscape: shaded / contour / wire / height ramp, distance fog, fine detail near the
# camera and coarse far away. Doc + LIVE CHECKS: docs/builds/pop_lane_h.md "TC-19".
# Route (lowest risk, decided offline 27 Oct): ONE static Grid POP (quads, Cols x Rows, size 2 x 2, pars set at build
# only) -> geo (Select POP) -> GLSL MAT whose VERTEX shader does everything: radial LOD remap of the grid coords
# (world = sign(g) |g|^Lodpow Extent: the clipmap's "dense near, coarse far" without rings or stitching), fly-over =
# scroll of the noise domain by module time (optional Snap to the finest cell so near vertices never swim), height =
# fbm value noise. Styles are pixel-shader only (the Grid POP never changes live). No glsladvancedPOP compute, no
# attribute layouts (T-124). numpy mirror: builders/pop_terrain_logic.py.
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_terrain.py').read(), ns); ns['build']('/project1/lab')
# build(parent_path, panel=True, first=False): idempotent; first=True applies FIRST (small grid) before any render op.
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())

NAME = 'POP_terrain'
STYLES = ['shaded', 'contour', 'wire', 'ramp', 'data']
STYLE_LABELS = ['Shaded (lambert)', 'Contour lines', 'Wire (grid lines)', 'Height colour ramp',
                'Data (r height/Heightscale, g x, b z; LIVE CHECK)']

PAGES = [
    ('Terrain', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Style', 'Menu', 'shaded', {'names': STYLES, 'labels': STYLE_LABELS}),
        ('Speed', 'Float', 2.0, {'min': -20, 'max': 20, 'label': 'Fly speed (world units / s)'}),
        ('Snap', 'Toggle', True, {'label': 'Snap scroll to the finest cell (no swimming near the camera)'}),
        ('Extent', 'Float', 40.0, {'min': 5, 'max': 200, 'label': 'Extent (half size, world units)'}),
        ('Lodpow', 'Float', 2.0, {'min': 1, 'max': 3, 'label': 'LOD power (1 = uniform, 3 = very dense near)'}),
        ('Freq', 'Float', 0.08, {'min': 0.005, 'max': 0.5, 'label': 'Noise frequency (per world unit)'}),
        ('Heightscale', 'Float', 6.0, {'min': 0, 'max': 30, 'label': 'Height scale'}),
        ('Octaves', 'Int', 5, {'min': 1, 'max': 8, 'clampmin': 1, 'clampmax': 8, 'label': 'Octaves'}),
        ('Ridge', 'Toggle', False, {'label': 'Ridged noise (1 - |2n - 1|)'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
    ]),
    ('Look', [
        ('Contours', 'Float', 12.0, {'min': 1, 'max': 60, 'label': 'Contour lines per Heightscale'}),
        ('Fog', 'Float', 0.02, {'min': 0, 'max': 0.2, 'label': 'Fog density'}),
    ]),
    ('Camera', [
        ('Cols', 'Int', 160, {'min': 8, 'max': 512, 'clampmin': 2, 'clampmax': 512, 'label': 'Grid columns'}),
        ('Rows', 'Int', 160, {'min': 8, 'max': 512, 'clampmin': 2, 'clampmax': 512, 'label': 'Grid rows'}),
        ('Camh', 'Float', 10.0, {'min': 0.5, 'max': 60, 'label': 'Camera height'}),
        ('Camz', 'Float', 0.0, {'min': -40, 'max': 40, 'label': 'Camera z'}),
        ('Pitch', 'Float', 25.0, {'min': -10, 'max': 90, 'label': 'Pitch down (deg)'}),
        ('Fov', 'Float', 70.0, {'min': 10, 'max': 120, 'label': 'Vertical fov (deg)'}),
    ]),
    OUT_PAGE,
]
PANEL_PAGES = ['Terrain', 'Look', 'Camera']
FIRST = {'Cols': 96, 'Rows': 96, 'Octaves': 3, 'Resw': 540, 'Resh': 960}

# RGB pars (pop_common._pars has no RGB style): page 'Look', made by _rgb_pars after _pars.
COLOURS = [('Lowcolor', (0.05, 0.10, 0.30), 'Low colour'), ('Midcolor', (0.10, 0.60, 0.50), 'Mid colour'),
           ('Highcolor', (1.00, 0.90, 0.70), 'High colour'), ('Fogcolor', (0.0, 0.0, 0.0), 'Fog colour')]


def _rgb(n):
    return tuple('parent().par.%s%s.eval()' % (n, ch) for ch in 'rgb') + ('1.0',)


def _rgb_pars(c, page_name, colours):
    page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
    for name, default, label in colours:
        p = getattr(c.par, name + 'r', None)
        if p is not None and getattr(p, 'val', None) is not None:
            continue
        for p, v in zip(page.appendRGB(name, label=label), default):
            p.default = v
            p.val = v


UNIFORMS = [
    ('uT', (PP.format('Extent'), PP.format('Lodpow'), PP.format('Freq'), PP.format('Heightscale'))),
    ('uT2', ("float(parent().par.Octaves.eval())", "1.0 if parent().par.Ridge.eval() else 0.0",
             "float(parent().par.Seed.eval())", "float(op('clock')[0])")),
    ('uT3', ("float(parent().par.Cols.eval())", "float(parent().par.Rows.eval())",
             "1.0 if parent().par.Snap.eval() else 0.0", "float(parent().par.Style.menuIndex)")),
    ('uT4', (PP.format('Contours'), PP.format('Fog'), PP.format('Camh'), PP.format('Camz'))),
    ('uLow', _rgb('Lowcolor')),
    ('uMid', _rgb('Midcolor')),
    ('uHigh', _rgb('Highcolor')),
    ('uFogc', _rgb('Fogcolor')),
]

COMMON = """
#define MAXOCT 8
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
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
// Mirror: pop_terrain_logic.fbm (0..1)
float fbm(vec2 W)
{
    int oct = clamp(int(uT2.x + 0.5), 1, MAXOCT);
    int seed = int(uT2.z + 0.5);
    float s = 0.0, wsum = 0.0, a = 1.0, f = uT.z;
    for (int o = 0; o < MAXOCT; o++) {
        if (o >= oct) break;
        s += a * vnoise(W * f, seed + o);
        wsum += a;
        a *= 0.5;
        f *= 2.0;
    }
    float n = s / wsum;
    if (uT2.y > 0.5) n = 1.0 - abs(2.0 * n - 1.0);
    return n;
}
float remap(float g) { g = clamp(g, -1.0, 1.0); return sign(g) * pow(abs(g), uT.y) * uT.x; }
"""

VERTEX = """// POP_terrain vertex (TC-19): static Grid POP quads (size 2 x 2); LOD remap + fly scroll + fbm height here.
uniform vec4 uT;    // extent, lod power, freq, height scale
uniform vec4 uT2;   // octaves, ridge, seed, scroll (module time x Speed)
uniform vec4 uT3;   // cols, rows, snap, style
uniform vec4 uT4;   // contours, fog, cam h, cam z
out Vertex { vec3 wpos; vec2 W; float h; vec2 gc; } oV;
""" + COMMON + """
void main()
{
    vec2 g = clamp(TDPos().xy, -1.0, 1.0);          // T-112: TDPos, never raw P
    float x = remap(g.x), zg = remap(g.y);
    float cell = uT.x * pow(2.0 / max(uT3.y - 1.0, 1.0), uT.y);
    float snap = uT3.z > 0.5 ? floor(uT2.w / cell) * cell : uT2.w;
    vec2 W = vec2(x, zg - snap);
    float h = uT.w * fbm(W);
    vec3 p = vec3(x, h, zg - snap + uT2.w);
    oV.wpos = p;
    oV.W = W;
    oV.h = h;
    oV.gc = (g * 0.5 + 0.5) * vec2(max(uT3.x - 1.0, 1.0), max(uT3.y - 1.0, 1.0));
    gl_Position = TDWorldToProj(TDDeform(p));
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

PIXEL = """// POP_terrain pixel: styles + fog; data style writes (h / Heightscale, Wx, Wz, 1) for the LIVE CHECK.
uniform vec4 uT;
uniform vec4 uT3;
uniform vec4 uT4;
uniform vec4 uLow;
uniform vec4 uMid;
uniform vec4 uHigh;
uniform vec4 uFogc;
in Vertex { vec3 wpos; vec2 W; float h; vec2 gc; } iV;
layout(location = 0) out vec4 fragColor;
void main()
{
    TDCheckDiscard();
    int st = int(uT3.w + 0.5);
    float hn = iV.h / max(uT.w, 1e-6);
    if (st == 4) { fragColor = vec4(hn, iV.W.x, iV.W.y, 1.0); return; }
    float k = clamp(hn, 0.0, 1.0);
    vec3 base = k < 0.5 ? mix(uLow.rgb, uMid.rgb, k * 2.0) : mix(uMid.rgb, uHigh.rgb, k * 2.0 - 1.0);
    vec3 n = normalize(cross(dFdx(iV.wpos), dFdy(iV.wpos)) + vec3(0.0, 1e-9, 0.0));
    if (n.y < 0.0) n = -n;
    float lam = max(dot(n, normalize(vec3(0.4, 0.8, 0.3))), 0.0);
    vec3 c = base;
    if (st == 0) {
        c = base * (0.25 + 0.75 * lam);
    } else if (st == 1) {
        float q = hn * uT4.x;
        float dd = min(fract(q), 1.0 - fract(q));
        float line = 1.0 - smoothstep(0.0, 1.5 * fwidth(q) + 1e-6, dd);
        c = base * (0.08 + 0.92 * line);
    } else if (st == 2) {
        vec2 f = min(fract(iV.gc), 1.0 - fract(iV.gc));
        vec2 w = 1.5 * fwidth(iV.gc) + 1e-6;
        float line = max(1.0 - smoothstep(0.0, w.x, f.x), 1.0 - smoothstep(0.0, w.y, f.y));
        c = base * (0.05 + 0.95 * line);
    }
    float dist = length(iV.wpos - vec3(0.0, uT4.z, uT4.w));
    c = mix(uFogc.rgb, c, exp(-uT4.y * dist));
    fragColor = TDOutputSwizzle(vec4(c, 1.0));
}
"""

CAM = {'ty': PP.format('Camh'), 'tz': PP.format('Camz'), 'rx': "-parent().par.Pitch.eval()",
       'viewanglemethod': ('menu', 'vertfov'), 'fov': PP.format('Fov'), 'near': 0.05,
       'far': "parent().par.Extent.eval() * 4.0"}
DATA_E = "parent().par.Style.eval() == 'data'"


def shader_texts():
    return {'vertex': VERTEX, 'pixel': PIXEL}


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_terrain (TC-19): endless fly-over terrain from ONE static Grid POP; LOD remap, '
                                 'scroll and fbm height in the GLSL MAT vertex shader; styles shaded / contour / wire '
                                 '/ ramp / data. Amount 0 = in1 untouched. Out: out1.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    _rgb_pars(c, 'Look', COLOURS)
    if first:
        _apply_first(c, FIRST)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Passed through when Amount is 0 (rack slot convention).'
    _clock(c, 'clock', "parent().par.Speed.eval()")
    g = _grid(c, 'grid', "parent().par.Cols.eval()", "parent().par.Rows.eval()", 'quads', 2.0, 2.0)
    g.comment = 'Static Cols x Rows quads, size 2 x 2 (TDPos().xy = grid coord -1..1): the only POP.'
    m = _mat(c, 'mat', VERTEX, PIXEL, spec=UNIFORMS, blend='none', depth=True)
    m.comment = 'Vertex: LOD remap, scroll (+ Snap), fbm height. Pixel: style, fog (data style = check values).'
    _geo(c, 'geo', 'grid', 'mat')
    c.op('geo').comment = 'The terrain grid (Select POP of ../grid) drawn with mat.'
    cam = _cam(c, 'cam', CAM)
    cam.comment = 'At (0, Camh, Camz), pitched down Pitch; looks -z over the terrain.'
    r = _render(c, 'render', 'cam', 'geo', fmt='rgba16float', aa='aa4')
    _expr(r.par.format, "'rgba32float' if %s else 'rgba16float'" % DATA_E)
    _expr(r.par.antialias, "'aa1' if %s else 'aa4'" % DATA_E)
    r.comment = 'Terrain render (rgba16f, aa4); Style data = rgba32f aa1 (no MSAA blend of the check values).'
    _out_switch(c, in1, r)
    stages = [
        {'title': '1 In + clock', 'role': 'input', 'ops': ['in1', 'clock_rate', 'clock'],
         'body': 'clock = scroll distance (Speed x time).'},
        {'title': '2 Terrain (static Grid POP)', 'role': 'process',
         'ops': ['grid', 'mat', 'mat_vertex', 'mat_pixel', 'geo'],
         'body': 'Grid POP quads -> mat: LOD remap + scroll + fbm height; pixel styles + fog.'},
        {'title': '3 Render', 'role': 'process', 'ops': ['cam', 'render'], 'body': 'Camera above the origin.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
