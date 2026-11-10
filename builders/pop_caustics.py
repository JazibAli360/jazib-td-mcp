# pop_caustics - POP_caustics (BUILD_PLAN_27OCT lane H, row FX7b TC-30 "caustics cast by geometry", Heckaman's
# no-code Ray POP caustics). Doc + LIVE CHECKS: docs/builds/pop_lane_h.md "TC-30".
# Route (decided offline 27 Oct): Ray POP does NOT work on macOS (MoltenVK has no ray queries: Z_forum_nodes_comps.md,
# T-35), so the refraction is analytic, in a GLSL MAT VERTEX shader over ONE static Grid POP of points (Rays x Rays,
# pars set at build only). Each point = one parallel light ray: refractor (water heightfield of 4 travelling sines /
# glass sphere in + out with TIR drop / slab whose top = Thickness x in1 luma) -> GLSL refract() -> floor plane at
# Floordepth -> written straight to clip space over the Floorsize square (no camera maths), 1-px points additive
# one/one into a 32F Render TOP at Simres (physarum deposit class, T-112: exact sums; Simres = Rays with a flat
# refractor gives EXACTLY 1.0 per texel). Then ONE compute look pass (T-47): Exposure tone, tint, optional add over
# in1; Persist > 0 adds the `acc` pass at floor resolution before it (perf 27 Oct, was an in-place buffer). numpy mirror:
# builders/pop_caustics_logic.py (hits + histogram). No POP compute, no attribute layouts (T-124).
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_caustics.py').read(), ns); ns['build']('/project1/lab', first=True)
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())

NAME = 'POP_caustics'
REFRACTORS = ['water', 'sphere', 'slab']
REFRACTOR_LABELS = ['Water (heightfield of travelling sines)', 'Glass sphere (in + out refraction)',
                    'Slab (top height = Thickness x in1 luma)']

PAGES = [
    ('Caustics', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Refractor', 'Menu', 'water', {'names': REFRACTORS, 'labels': REFRACTOR_LABELS}),
        ('Ior', 'Float', 1.33, {'min': 1.0, 'max': 2.5, 'label': 'Index of refraction'}),
        ('Lightangle', 'Float', 0.0, {'min': -60, 'max': 60, 'label': 'Light tilt deg (about y)'}),
        ('Speed', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Speed (water time / s)'}),
        ('Amp', 'Float', 0.02, {'min': 0, 'max': 0.2, 'label': 'Water amplitude'}),
        ('Freq', 'Float', 6.0, {'min': 0.5, 'max': 40, 'label': 'Water frequency'}),
        ('Radius', 'Float', 0.5, {'min': 0.05, 'max': 1, 'label': 'Sphere radius'}),
        ('Thickness', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Slab thickness x in1 luma'}),
        ('Direct', 'Toggle', True, {'label': 'Rays that miss the sphere still light the floor'}),
    ]),
    ('Rays', [
        ('Rays', 'Int', 256, {'min': 16, 'max': 1024, 'clampmin': 2, 'clampmax': 1024,
                              'label': 'Rays per side (count = Rays^2, cap 1M)'}),
        ('Simres', 'Int', 0, {'min': 0, 'max': 2048, 'clampmin': 0, 'clampmax': 2048,
                              'label': 'Floor texels per side (0 = Rays)'}),
        ('Lightsize', 'Float', 2.0, {'min': 0.1, 'max': 10, 'label': 'Light square size (world)'}),
        ('Floorsize', 'Float', 2.0, {'min': 0.1, 'max': 10, 'label': 'Floor square shown (world)'}),
        ('Floordepth', 'Float', 1.0, {'min': 0.05, 'max': 10, 'label': 'Floor depth below the surface / centre'}),
        ('Size', 'Float', 1.0, {'min': 1, 'max': 8, 'label': 'Point size px (1 = exact sums)'}),
        ('Jitter', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Ray jitter in its cell (hashed per frame, 0 = grid)'}),
    ]),
    ('Look', [
        ('Exposure', 'Float', 0.5, {'min': 0, 'max': 8, 'label': 'Exposure'}),
        ('Persist', 'Float', 0.0, {'min': 0, 'max': 0.99, 'label': 'Persist (long exposure)'}),
        ('Composite', 'Menu', 'alone', {'names': ['alone', 'add'], 'labels': ['Caustics alone', 'Add over in1']}),
        ('Tintr', 'Float', 0.75, {'min': 0, 'max': 2, 'label': 'Tint red'}),
        ('Tintg', 'Float', 0.95, {'min': 0, 'max': 2, 'label': 'Tint green'}),
        ('Tintb', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Tint blue'}),
    ]),
    OUT_PAGE,
]
PANEL_PAGES = ['Caustics', 'Rays', 'Look']
FIRST = {'Rays': 128, 'Simres': 0, 'Persist': 0.0, 'Size': 1.0, 'Refractor': 'water'}

SIDE_E = "max(int(parent().par.Rays.eval()), 2)"
SIM_E = "int(parent().par.Simres.eval()) or max(int(parent().par.Rays.eval()), 2)"

MAT_UNIFORMS = [
    ('uC', ("float(parent().par.Refractor.menuIndex)", PP.format('Ior'), PP.format('Lightangle'),
            "float(op('clock')[0])")),
    ('uC2', (PP.format('Lightsize'), PP.format('Floorsize'), PP.format('Floordepth'), "float(%s)" % SIDE_E)),
    ('uC3', (PP.format('Amp'), PP.format('Freq'), PP.format('Radius'), PP.format('Thickness'))),
    ('uC4', (PP.format('Size'), "1.0 if parent().par.Direct.eval() else 0.0", "float(op('in1').width)",
             "float(op('in1').height)")),
    ('uC5', (PP.format('Jitter'), "float(absTime.frame % 16777216)", "0.0", "0.0")),
]
ACC_UNIFORMS = [('uA', (PP.format('Persist'), "float(absTime.frame % 16777216)", "0.0", "0.0"))]
LOOK_UNIFORMS = [
    ('uL', (PP.format('Exposure'), PP.format('Persist'), "1.0 if parent().par.Composite.eval() == 'add' else 0.0",
            "parent().par.Resw.eval() / max(parent().par.Resh.eval(), 1)")),
    ('uL2', (PP.format('Tintr'), PP.format('Tintg'), PP.format('Tintb'), "0.0")),
]

VERTEX = """// POP_caustics vertex (TC-30): one parallel light ray per Grid POP point -> refractor -> floor -> clip space.
// Analytic refraction (no Ray POP: not on macOS). Mirror: pop_caustics_logic.hits / deposit.
uniform vec4 uC;    // refractor, ior, light angle deg, time
uniform vec4 uC2;   // light size, floor size, floor depth, rays side
uniform vec4 uC3;   // water amp, water freq, sphere radius, slab thickness
uniform vec4 uC4;   // point size, direct, in1 w, in1 h
uniform vec4 uC5;   // jitter (0..1 of a cell), salt (frame), -, -
uniform sampler2D sIn;
out Vertex { vec4 color; float size; } oV;
const float WANG[4] = float[4](0.0, 1.1, 2.3, 3.7);
const float WFS[4] = float[4](1.0, 1.59, 2.44, 3.7);
const float WA[4] = float[4](1.0, 0.5, 0.3, 0.2);
const float WW[4] = float[4](1.0, 1.3, 1.7, 2.3);
const float WPH[4] = float[4](0.0, 1.7, 4.1, 2.9);

vec3 water(vec2 p)          // h, dh/dx, dh/dy
{
    vec3 r = vec3(0.0);
    for (int k = 0; k < 4; k++) {
        vec2 dir = vec2(cos(WANG[k]), sin(WANG[k]));
        float kk = uC3.y * WFS[k];
        float a = kk * dot(dir, p) + WW[k] * uC.w + WPH[k];
        r.x += WA[k] * sin(a);
        r.yz += WA[k] * kk * cos(a) * dir;
    }
    return r * uC3.x;
}
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
// Per-ray, per-frame offset inside the ray's own cell, |j| < 0.5 cell: the ray lattice stops showing where rays
// diverge, every ray still lands once (sum unchanged; flat refractor at Simres = Rays still 1.0 per texel).
vec2 rayJitter(ivec2 t, float salt)
{
    uint h = lowbias((uint(t.x) * 747796405u) ^ (uint(t.y) * 1597334677u) ^ (uint(salt) * 2891336453u + 11u));
    return ((vec2(float(h & 0xFFFFu), float(h >> 16u)) + 0.5) / 65536.0 - 0.5) * uC5.x;
}
float luma(vec2 uv) { return dot(textureLod(sIn, uv, 0.0).rgb, vec3(0.2126, 0.7152, 0.0722)); }

void main()
{
    int side = int(uC2.w + 0.5);
    ivec2 t = ivec2(floor((TDPos().xy + 0.5) * float(side - 1) + 0.5));   // T-112: TDPos, never raw P
    vec2 o2 = ((vec2(t) + 0.5 + rayJitter(t, uC5.y)) / float(side) - 0.5) * uC2.x;
    float la = radians(uC.z);
    vec3 d = vec3(sin(la), 0.0, -cos(la));
    float eta = 1.0 / uC.y;
    int m = int(uC.x + 0.5);
    bool ok = true;
    vec3 pos = vec3(o2, 0.0);
    vec3 tr = d;
    if (m == 0) {
        vec3 w = water(o2);
        pos = vec3(o2, w.x);
        tr = refract(d, normalize(vec3(-w.y, -w.z, 1.0)), eta);
    } else if (m == 1) {
        float R = uC3.z;
        vec3 o = vec3(o2, 2.0 * R);
        float b = dot(o, d), c = dot(o, o) - R * R, disc = b * b - c;
        pos = o;
        if (disc > 0.0) {
            vec3 p1 = o + d * (-b - sqrt(disc));
            vec3 t1 = refract(d, p1 / R, eta);
            vec3 p2 = p1 + t1 * (-2.0 * dot(t1, p1));
            vec3 t2 = refract(t1, -p2 / R, uC.y);
            if (dot(t2, t2) == 0.0) ok = false;          // total internal reflection: drop
            pos = p2;
            tr = t2;
        } else if (uC4.y < 0.5) {
            ok = false;
        }
    } else {
        vec2 uv = o2 / uC2.x + 0.5;
        vec2 e = 1.0 / max(uC4.zw, vec2(1.0));
        float top = uC3.w * luma(uv);
        float gx = uC3.w * (luma(uv + vec2(e.x, 0.0)) - luma(uv - vec2(e.x, 0.0))) / (2.0 * e.x * uC2.x);
        float gy = uC3.w * (luma(uv + vec2(0.0, e.y)) - luma(uv - vec2(0.0, e.y))) / (2.0 * e.y * uC2.x);
        vec3 t1 = refract(d, normalize(vec3(-gx, -gy, 1.0)), eta);
        if (t1.z >= -1e-6) ok = false;
        vec3 p1 = vec3(o2, top);
        pos = p1 + t1 * (-top / min(t1.z, -1e-6));
        tr = refract(t1, vec3(0.0, 0.0, 1.0), uC.y);
        if (dot(tr, tr) == 0.0) ok = false;
    }
    if (tr.z >= -1e-6) ok = false;
    float tz = abs(tr.z) > 1e-6 ? tr.z : -1.0;
    vec3 q = pos + tr * ((-uC2.z - pos.z) / tz);
    gl_Position = ok ? vec4(q.xy / (0.5 * uC2.y), 0.0, 1.0) : vec4(2.0, 2.0, 0.0, 1.0);
    gl_PointSize = max(uC4.x, 1.0);
    oV.size = gl_PointSize;
    oV.color = vec4(1.0);
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

PIXEL = """// POP_caustics pixel: 1-px points pass 1.0 through (exact additive counts); Size > 1 = soft round sprite.
in Vertex { vec4 color; float size; } iV;
layout(location = 0) out vec4 fragColor;
void main()
{
    vec4 c = iV.color;
    if (iV.size > 1.5) {
        vec2 d = gl_PointCoord * 2.0 - 1.0;
        c *= max(1.0 - dot(d, d), 0.0);
    }
    fragColor = c;
}
"""

LOOK = """// POP_caustics look (compute, T-47): tone + tint of acc; optional add over in1. in0 = acc (square floor, cropped to
// the output aspect), in1 = in1. One write-only buffer (perf 27 Oct: see ACC).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uL;    // exposure, persist, composite add, aspect
uniform vec4 uL2;   // tint rgb, -
void main()
{
    ivec2 T = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (T.x >= sz.x || T.y >= sz.y) return;
    vec2 uv = (vec2(T) + 0.5) / vec2(sz);
    vec2 hd = 0.5 / vec2(textureSize(sTD2DInputs[0], 0));   // hold the edge texel (T-204: the input extend
    vec2 ud = clamp(vec2((uv.x - 0.5) * uL.w + 0.5, uv.y), hd, 1.0 - hd);   // blended 0 into the edge rows)
    vec3 acc = texture(sTD2DInputs[0], ud).rgb;
    vec3 c = (1.0 - exp(-uL.x * acc)) * uL2.rgb;
    float a = clamp(max(c.r, max(c.g, c.b)), 0.0, 1.0);
    vec4 o = vec4(c, a);
    if (uL.z > 0.5) {
        vec4 b = texture(sTD2DInputs[1], uv);
        o = vec4(b.rgb + c, max(b.a, a));
    }
    TDImageStoreOutput(0, ivec3(T, 0), o);
}
"""

ACC = """// POP_caustics acc (compute, floor resolution, cooks only while Persist > 0: acc_sel): rgb = deposit + Persist x
// last frame's acc (acc_fb), a = the frame it was written (a last acc older than 30 frames, e.g. Persist was 0 for a
// while, or another size starts from zero). Perf 27 Oct: the long exposure moved off the 1080x1920 look (an in-place
// readwrite buffer there; such instances cooked 3-5x slower in 2 of 6 fresh copies on b3, write-only 0 of 8) to the
// floor grid before the resample. Persist 0 (default): the look reads the deposit itself, out1 bit-exact; Persist > 0
// sums before instead of after the bilinear resample (same in exact maths) and in 32F instead of 16F (b3: max 0.0005).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;    // persist, frame, -, -
void main()
{
    ivec2 T = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (T.x >= sz.x || T.y >= sz.y) return;
    vec4 last = textureSize(sTD2DInputs[1], 0) == sz ? texelFetch(sTD2DInputs[1], T, 0) : vec4(0.0);
    vec3 prev = (uA.y - last.a <= 30.0 && uA.y > last.a) ? last.rgb : vec3(0.0);
    TDImageStoreOutput(0, ivec3(T, 0), vec4(texelFetch(sTD2DInputs[0], T, 0).rgb + uA.x * prev, uA.y));
}
"""


def shader_texts():
    return {'vertex': VERTEX, 'pixel': PIXEL, 'look': LOOK, 'acc': ACC}


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_caustics (TC-30): Rays x Rays parallel light rays refracted by water / a glass '
                                 'sphere / an in1-luma slab onto a floor (analytic, no Ray POP), deposited additively '
                                 '(exact counts), then toned. Out: out1 (look), out2 (raw deposit, rays per texel).')
    was_open = _close_window(c)
    _pars(c, PAGES)
    if first:
        _apply_first(c, FIRST)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Slab refractor height (luma) and the Composite add background.'
    clk = _clock(c, 'clock', "parent().par.Speed.eval()")
    g = _grid(c, 'rays', SIDE_E, SIDE_E, 'points')
    g.comment = 'Static Rays x Rays points: one light ray each (TDPos().xy + 0.5 = ray texel). The only POP.'
    m = _mat(c, 'mat', VERTEX, PIXEL, samplers=[('sIn', 'in1', 'linear')], spec=MAT_UNIFORMS, blend='add',
             depth=False)
    m.comment = 'Vertex: ray -> refractor -> floor hit -> clip. Pixel: 1.0 per ray, additive one/one (exact sums).'
    geo = _geo(c, 'geo', 'rays', 'mat')
    geo.comment = 'The ray points (Select POP of ../rays) drawn with mat.'
    cam = _cam(c, 'cam', {})
    cam.comment = 'Unused by the shader (it writes clip space) but a Render TOP needs a camera.'
    dep = _render(c, 'deposit', 'cam', 'geo', w=SIM_E, h=SIM_E, fmt='rgba32float', aa='aa1')
    dep.comment = 'Rays per floor texel (rgb = a = count). Simres = Rays + flat water: every texel 1.0 exactly.'
    ab = _blank(c, 'acc_blank', SIM_E, SIM_E, 'rgba32float')
    ab.comment = 'Zero acc (Feedback start / size change).'
    afb = _feedback(c, 'acc_fb', 'acc', ab)
    _expr(afb.par.top, "'acc' if parent().par.Persist.eval() > 0 else ''")
    afb.comment = ("Last frame's acc. Target only while Persist > 0: a Feedback TOP cooks its target every frame it "
                   "cooks itself, even when nothing selects the target (b3 27 Oct).")
    ac = _compute(c, 'acc', ACC, [dep, afb], SIM_E, SIM_E, fmt='rgba32float', spec=ACC_UNIFORMS)
    ac.comment = 'acc = deposit + Persist x acc_fb at floor resolution; a = frame stamp.'
    asel = _mk(c, switchTOP, 'acc_sel')
    _wire(dep, asel, 0)
    _wire(ac, asel, 1)
    _expr(asel.par.index, "1 if parent().par.Persist.eval() > 0 else 0")
    asel.comment = 'Persist 0 = the deposit itself (acc does not cook), else acc.'
    lk = _compute(c, 'look', LOOK, [asel, in1], RESW, RESH, fmt='rgba16float', spec=LOOK_UNIFORMS, filt='linear')
    _try(lk, 'numcolorbufs', 1)                    # rebuilds of the old 2-buffer in-place look
    _try(lk, 'outputaccess', 'writeonly')
    _try(lk, 'clearoutputs', True)
    lk.comment = 'Tone 1 - exp(-Exposure acc) x tint (+ add over in1). One write-only buffer.'
    out2 = _mk(c, outTOP, 'out2')
    _wire(dep, out2)
    _out_switch(c, in1, lk)
    stages = [
        {'title': '1 In + clock', 'role': 'input', 'ops': ['in1', 'clock_rate', 'clock'],
         'body': 'in1 = slab height / add background. clock = water time (Speed).'},
        {'title': '2 Rays (static Grid POP)', 'role': 'process',
         'ops': ['rays', 'mat', 'mat_vertex', 'mat_pixel', 'geo', 'cam'],
         'body': 'Grid POP points -> mat vertex: refract (water / sphere / slab) -> floor -> clip.'},
        {'title': '3 Deposit', 'role': 'process', 'ops': ['deposit', 'out2'],
         'body': 'Render TOP 32F, additive 1-px points: rays per floor texel (exact).'},
        {'title': '4 Look + out', 'role': 'output',
         'ops': ['acc_blank', 'acc_fb', 'acc', 'acc_compute', 'acc_sel', 'look', 'look_compute', 'out_sel', 'out1'],
         'body': 'acc = deposit + Persist x acc_fb (floor res, only while Persist > 0) -> acc_sel -> look (tone + tint, + add over in1). Amount 0 = in1 '
                 'untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
