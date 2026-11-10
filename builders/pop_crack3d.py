# pop_crack3d - POP_crack3d (BUILD_PLAN_27OCT lane H, row FX7b TC-12 "Voronoi crack lines on any mesh", Lake
# Heckaman GLSL for POPs 6-7). Glowing crack network spreading over a sphere / torus / box / any POP from an impact
# point; cells erode away (pieces missing); lit surface or cracks-only overlay. Doc + LIVE CHECKS:
# docs/builds/pop_lane_h.md "TC-12".
# Route (lowest risk, decided offline 27 Oct): the cracks are computed PER PIXEL in a GLSL MAT (3D Worley F1 / F2 of
# the object-space position, jittered cell grid, 27-cell search, compile-time bounded) instead of Heckaman's
# glsladvancedPOP that repositions pre-allocated line segments on triangle edges. The meshes are three built-in
# generator POPs (Sphere geodesic, Torus, Box) created once with fixed pars; geo's Select POP picks one by name. No POP
# compute, no attribute layout, no count changes (T-124). Normals from screen derivatives (no N attribute assumed).
# numpy mirror: builders/pop_crack3d_logic.py.
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_crack3d.py').read(), ns); ns['build']('/project1/lab')
# build(parent_path, panel=True, first=False): idempotent; first=True applies FIRST before any render op.
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())

NAME = 'POP_crack3d'
SHAPES = ['sphere', 'torus', 'box', 'custom']
STYLES = ['lit', 'lines', 'pos', 'data']
STYLE_LABELS = ['Lit surface + glowing cracks', 'Cracks only (transparent overlay)',
                'Data: object position xyz (LIVE CHECK)', 'Data: F1, F2 - F1, crack, reached (LIVE CHECK)']

PAGES = [
    ('Crack', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Style', 'Menu', 'lit', {'names': STYLES, 'labels': STYLE_LABELS}),
        ('Cellscale', 'Float', 4.0, {'min': 0.5, 'max': 20, 'label': 'Cells per object unit'}),
        ('Width', 'Float', 0.05, {'min': 0, 'max': 0.5, 'label': 'Crack width (F2 - F1, cell units)'}),
        ('Progress', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Crack front progress'}),
        ('Auto', 'Toggle', False, {'label': 'Auto progress (loops 0..1)'}),
        ('Autospeed', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'Auto speed (per s)'}),
        ('Reach', 'Float', 2.5, {'min': 0, 'max': 6, 'label': 'Reach at progress 1 (object units)'}),
        ('Soft', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Front softness'}),
        ('Impactx', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Impact x (object space)'}),
        ('Impacty', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Impact y'}),
        ('Impactz', 'Float', 1.0, {'min': -2, 'max': 2, 'label': 'Impact z'}),
        ('Erode', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Erode (fraction of reached cells removed)'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
        ('Glow', 'Float', 2.0, {'min': 0, 'max': 10, 'label': 'Crack glow intensity'}),
        ('Basemode', 'Menu', 'flat', {'names': ['flat', 'in1'], 'labels': ['Flat base colour',
                                                                          'in1 (spherical uv)']}),
    ]),
    ('Object', [
        ('Shape', 'Menu', 'sphere', {'names': SHAPES, 'labels': ['Sphere (geodesic)', 'Torus', 'Box',
                                                                 'Custom POP (Custompop)']}),
        ('Custompop', 'Str', '', {'label': 'Custom POP path (Shape custom)'}),
        ('Detail', 'Int', 24, {'min': 2, 'max': 64, 'clampmin': 1, 'clampmax': 96, 'label': 'Sphere geodesic freq'}),
        ('Tilt', 'Float', 15.0, {'min': -90, 'max': 90, 'label': 'Tilt deg (x)'}),
        ('Orbit', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Orbit deg (y)'}),
        ('Spin', 'Float', 10.0, {'min': -90, 'max': 90, 'label': 'Spin deg / s (y)'}),
        ('Dist', 'Float', 4.0, {'min': 1.5, 'max': 20, 'label': 'Camera distance'}),
        ('Fov', 'Float', 40.0, {'min': 10, 'max': 100, 'label': 'Vertical fov'}),
    ]),
    OUT_PAGE,
]
PANEL_PAGES = ['Crack', 'Object']
FIRST = {'Detail': 8, 'Resw': 540, 'Resh': 960, 'Spin': 0.0, 'Auto': False}

COLOURS = [('Glowcolor', (1.0, 0.55, 0.15), 'Crack glow colour'), ('Basecolor', (0.12, 0.12, 0.14), 'Base colour')]


def _rgb(n, w):
    return tuple('parent().par.%s%s.eval()' % (n, ch) for ch in 'rgb') + (w,)


def _rgb_pars(c, page_name, colours):
    page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
    for name, default, label in colours:
        p = getattr(c.par, name + 'r', None)
        if p is not None and getattr(p, 'val', None) is not None:
            continue
        for p, v in zip(page.appendRGB(name, label=label), default):
            p.default = v
            p.val = v


PROG_E = ("(float(op('clock')[0]) % 1.0) if parent().par.Auto.eval() else parent().par.Progress.eval()")
UNIFORMS = [
    ('uC', (PP.format('Cellscale'), PP.format('Width'), PROG_E, PP.format('Reach'))),
    ('uC2', (PP.format('Impactx'), PP.format('Impacty'), PP.format('Impactz'), PP.format('Erode'))),
    ('uC3', ("float(parent().par.Seed.eval())", "float(parent().par.Style.menuIndex)", PP.format('Soft'),
             PP.format('Glow'))),
    ('uGlowc', _rgb('Glowcolor', '1.0')),
    ('uBasec', _rgb('Basecolor', "1.0 if parent().par.Basemode.eval() == 'in1' else 0.0")),
]

VERTEX = """// POP_crack3d vertex (TC-12): object-space position out; no attribute other than TDPos() is read.
out Vertex { vec3 opos; vec3 wpos; } oV;
void main()
{
    vec3 p = TDPos();                               // T-112
    vec4 w = TDDeform(p);
    oV.opos = p;
    oV.wpos = w.xyz;
    gl_Position = TDWorldToProj(w);
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

PIXEL = """// POP_crack3d pixel: 3D Worley F1 / F2 (27 cells), crack = F2 - F1 < Width inside the front, eroded cells cut.
// Mirror: pop_crack3d_logic (hcell / hcomp / worley / front / eroded).
uniform vec4 uC;      // cellscale, width, progress, reach
uniform vec4 uC2;     // impact xyz, erode
uniform vec4 uC3;     // seed, style, soft, glow
uniform vec4 uGlowc;  // rgb, -
uniform vec4 uBasec;  // rgb, base from in1
uniform sampler2D sIn;
in Vertex { vec3 opos; vec3 wpos; } iV;
layout(location = 0) out vec4 fragColor;
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
// ONE lowbias per cell (was 6: 3 chained + 3 hcomp), jitter from 10-bit fields of the same hash: GPU 3.5 -> see
// pop_lane_h.md "Live results" (27 Oct, b5). hcomp stays for the erosion draw (once per pixel).
uint hcell(ivec3 c, int s)
{
    return lowbias((uint(c.x) * 747796405u) ^ (uint(c.y) * 1597334677u) ^ (uint(c.z) * 3812015801u)
                   ^ (uint(s) * 2891336453u + 11u));
}
vec3 jit(uint h) { return vec3(uvec3(h, h >> 10u, h >> 20u) & uvec3(1023u)) / 1024.0; }
float hcomp(uint h, uint k) { return float(lowbias(h + k * 0x9E3779B9u) >> 8) / 16777216.0; }
float front(vec3 p)
{
    float d = length(p - uC2.xyz);
    return clamp((uC.w * uC.z - d) / max(uC3.z, 1e-6) + 0.5, 0.0, 1.0);
}
// One Worley cell (squared distances: 2 sqrt per pixel instead of 27).
void wcell(ivec3 c, vec3 q, int seed, inout float wF1, inout float wF2, inout ivec3 cid, inout uint hid)
{
    uint h = hcell(c, seed);
    vec3 dv = vec3(c) + jit(h) - q;
    float d = dot(dv, dv);
    if (d < wF1) { wF2 = wF1; wF1 = d; cid = c; hid = h; }
    else wF2 = min(wF2, d);
}
void main()
{
    TDCheckDiscard();
    int seed = int(uC3.x + 0.5);
    int st = int(uC3.y + 0.5);
    vec3 q = iV.opos * uC.x;
    ivec3 b = ivec3(floor(q));
    float wF1 = 1e9, wF2 = 1e9;
    ivec3 cid = b;
    uint hid = 0u;
    // Exact pruned search (perf 27 Oct): the site of cell b + o lies inside that cell, so its squared distance is at
    // least lb = sum over axes of (o < 0 ? f^2 : o > 0 ? (1 - f)^2 : 0). A cell with lb >= F2 cannot change F1 / F2,
    // so it is skipped. Centre cell first, then the other 26 (faces before edges / corners tighten F2 early); same
    // F1 / F2 / cell as the full 27-cell search (order only matters on exact distance ties).
    vec3 f = q - vec3(b);
    vec3 lo = f * f, hi = (1.0 - f) * (1.0 - f);
    wcell(b, q, seed, wF1, wF2, cid, hid);
    for (int pass = 0; pass < 2; pass++)
    for (int dz = -1; dz <= 1; dz++)
    for (int dy = -1; dy <= 1; dy++)
    for (int dx = -1; dx <= 1; dx++) {
        int m = abs(dx) + abs(dy) + abs(dz);
        if (m == 0 || (pass == 0) != (m == 1)) continue;          // pass 0: 6 faces, pass 1: 12 edges + 8 corners
        float lb = (dx < 0 ? lo.x : (dx > 0 ? hi.x : 0.0)) + (dy < 0 ? lo.y : (dy > 0 ? hi.y : 0.0))
                 + (dz < 0 ? lo.z : (dz > 0 ? hi.z : 0.0));
        if (lb >= wF2) continue;
        wcell(b + ivec3(dx, dy, dz), q, seed, wF1, wF2, cid, hid);
    }
    wF1 = sqrt(wF1);
    wF2 = sqrt(wF2);
    float gap = wF2 - wF1;
    vec3 site = vec3(cid) + jit(hid);
    bool cut = hcomp(hid, 3u) < uC2.w && front(site / max(uC.x, 1e-6)) > 0.5;
    float fr = front(iV.opos);
    float aa = fwidth(gap) + 1e-6;                    // derivatives before any discard
    float crack = (1.0 - smoothstep(uC.y - aa, uC.y + aa, gap)) * fr;
    vec3 n = normalize(cross(dFdx(iV.wpos), dFdy(iV.wpos)) + vec3(0.0, 0.0, 1e-9));
    if (cut) discard;
    if (st == 2) { fragColor = vec4(iV.opos, 1.0); return; }
    if (st == 3) { fragColor = vec4(wF1, gap, (gap < uC.y && fr > 0.5) ? 1.0 : 0.0, 1.0); return; }
    vec3 glow = uGlowc.rgb * uC3.w * crack;
    if (st == 1) {
        if (crack < 1e-3) discard;
        fragColor = TDOutputSwizzle(vec4(glow, clamp(crack, 0.0, 1.0)));
        return;
    }
    vec3 base = uBasec.rgb;
    if (uBasec.w > 0.5) {
        vec3 d = normalize(iV.opos + vec3(0.0, 0.0, 1e-9));
        vec2 uv = vec2(atan(d.z, d.x) / 6.283185307179586 + 0.5, asin(clamp(d.y, -1.0, 1.0)) / 3.14159265 + 0.5);
        base = texture(sIn, uv).rgb;
    }
    float lam = abs(dot(n, normalize(vec3(0.4, 0.7, 0.6))));
    vec3 c = base * (0.2 + 0.8 * lam) * (1.0 - clamp(crack, 0.0, 1.0)) + glow;
    fragColor = TDOutputSwizzle(vec4(c, 1.0));
}
"""

SEL_E = ("{'sphere': '../sphere', 'torus': '../torus', 'box': '../box'}.get(parent(2).par.Shape.eval(), "
         "parent(2).par.Custompop.eval() or '../sphere')")
CAM = {'tz': PP.format('Dist'), 'viewanglemethod': ('menu', 'vertfov'), 'fov': PP.format('Fov'), 'near': 0.05,
       'far': 100.0}
DATA_E = "parent().par.Style.eval() in ('pos', 'data')"
# Perf 27 Oct (b3): the pixel shader discards (erosion), so the GPU has no early depth test and shaded every back
# face as well (~2x the Worley work). Back faces are culled only while they cannot be seen: no erosion holes (Erode
# 0), not the see-through 'lines' style, a closed built-in shape (a custom POP may be open) and the camera outside
# every built-in shape (bounding radius 1.4 + near 0.05). Then out1 is the same picture (b3: sphere bit-exact, torus
# 2 px / box 13 px of 2.07 M differ at silhouette depth ties, max 0.018).
CULL_E = ("'backfaces' if (parent().par.Erode.eval() <= 0 and parent().par.Style.eval() != 'lines' and "
          "parent().par.Shape.eval() != 'custom' and parent().par.Dist.eval() > 1.45) else 'neither'")


def shader_texts():
    return {'vertex': VERTEX, 'pixel': PIXEL}


def _shapes(c):
    s = _mk(c, spherePOP, 'sphere')
    s.par.type = 'geodesic'
    _try(s, 'geodesictype', 'triangles')
    s.par.radx = s.par.rady = s.par.radz = 1.0
    _expr(s.par.freq, "parent().par.Detail.eval()")
    s.comment = 'Unit geodesic sphere (freq = Detail).'
    t = _mk(c, torusPOP, 'torus')
    t.par.radx, t.par.rady = 1.0, 0.4
    t.par.cols, t.par.rows = 96, 48
    t.comment = 'Torus R 1, r 0.4, 96 x 48 quads.'
    b = _mk(c, boxPOP, 'box')
    b.par.sizex = b.par.sizey = b.par.sizez = 1.6
    b.comment = 'Box 1.6 (the pixel shader makes all the detail).'
    return s, t, b


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_crack3d (TC-12): Voronoi crack network spreading from an impact over a sphere / '
                                 'torus / box / custom POP, cells erode away; per-pixel 3D Worley in a GLSL MAT. '
                                 'Amount 0 = in1 untouched. Out: out1.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    _rgb_pars(c, 'Crack', COLOURS)
    if first:
        _apply_first(c, FIRST)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Passed through at Amount 0; base colour source when Basemode is in1.'
    _clock(c, 'clock', "parent().par.Autospeed.eval() if parent().par.Auto.eval() else 0.0")
    _clock(c, 'spin', "parent().par.Spin.eval()")
    _shapes(c)
    m = _mat(c, 'mat', VERTEX, PIXEL, samplers=[('sIn', 'in1', 'linear')], spec=UNIFORMS, blend='over', depth=True)
    m.comment = ('Pixel: Worley F1 / F2, crack front from Impact, eroded cells discarded; styles lit / lines / data. '
                 'Back faces culled while nothing can show them (CULL_E).')
    _expr(m.par.cullface, CULL_E)
    geo = _geo(c, 'geo', 'sphere', 'mat')
    _expr(geo.op('sel').par.pop, SEL_E)
    _expr(geo.par.rx, PP.format('Tilt'))
    _expr(geo.par.ry, "parent().par.Orbit.eval() + float(op('spin')[0])")
    geo.comment = 'Select POP picks sphere / torus / box / Custompop by Shape; Tilt / Orbit + Spin rotate it.'
    cam = _cam(c, 'cam', CAM)
    cam.comment = 'At z = Dist looking -z.'
    r = _render(c, 'render', 'cam', 'geo', fmt='rgba16float', aa='aa4')
    _expr(r.par.format, "'rgba32float' if %s else 'rgba16float'" % DATA_E)
    _expr(r.par.antialias, "'aa1' if %s else 'aa4'" % DATA_E)
    r.comment = 'Render (rgba16f aa4; Style pos / data = rgba32f aa1 for the LIVE CHECK).'
    _out_switch(c, in1, r)
    stages = [
        {'title': '1 In + clocks', 'role': 'input', 'ops': ['in1', 'clock_rate', 'clock', 'spin_rate', 'spin'],
         'body': 'clock = auto progress, spin = rotation.'},
        {'title': '2 Shapes (static POPs)', 'role': 'process', 'ops': ['sphere', 'torus', 'box'],
         'body': 'Built-in generators, fixed pars; Shape picks one.'},
        {'title': '3 Crack material', 'role': 'process', 'ops': ['mat', 'mat_vertex', 'mat_pixel', 'geo'],
         'body': 'Per-pixel 3D Worley cracks + front + erosion.'},
        {'title': '4 Render', 'role': 'process', 'ops': ['cam', 'render'], 'body': 'Camera at Dist.'},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
