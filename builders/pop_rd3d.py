# pop_rd3d - POP_rd3d (BUILD_PLAN_27OCT lane H, row FX7b TC-11 "3D reaction-diffusion structures by POP<->TOP
# feedback", Dan Tapper Dec 2025). Organic 3D forms: a Gray-Scott field on a WRAP texture grows on a torus / sphere /
# plane and pushes the surface out along its normal. Doc + LIVE CHECKS: docs/builds/pop_lane_h.md "TC-11".
# Route (lowest risk, decided offline 27 Oct): the "TOP" half = ONE compute GLSL TOP `gs` running Steps 1/2/4
# Gray-Scott steps per dispatch in shared memory (perf 27 Oct; it was a chain of 4 one-step TOPs, T-46/T-47), the
# result feeds a Feedback TOP. The "POP" half
# = ONE static Grid POP (quads, pars set at build) whose GLSL MAT vertex shader maps (u, v) to the shape and displaces
# it by Height x V (texture fetch in the vertex shader), with finite-difference normals. No POP compute, no attribute
# layout, no TOP-to-POP (T-124). The step counter lives in the state (b) so Stopat freezes after exactly N steps
# whatever the frame rate (LIVE CHECK parity). numpy mirror: builders/pop_rd3d_logic.py.
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_rd3d.py').read(), ns); ns['build']('/project1/lab', first=True)
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())

NAME = 'POP_rd3d'
PRESETS = ['coral', 'mitosis', 'worms', 'spots', 'maze', 'custom']
PRESET_FK = [(0.0545, 0.062), (0.0367, 0.0649), (0.078, 0.061), (0.03, 0.0625), (0.029, 0.057)]
SHAPES = ['torus', 'sphere', 'plane']
PALETTES = ['bio', 'fire', 'ice', 'mono', 'ink']
PAL = [((0.0, 0.08, 0.1), (0.5, 1.0, 0.7)), ((0.12, 0.02, 0.0), (1.0, 0.7, 0.15)), ((0.02, 0.06, 0.2), (0.7, 0.9, 1.0)),
       ((0.1, 0.1, 0.1), (0.95, 0.95, 0.95)), ((0.9, 0.88, 0.84), (0.06, 0.06, 0.08))]

PAGES = [
    ('Rd3d', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Preset', 'Menu', 'coral', {'names': PRESETS, 'labels': ['Coral', 'Mitosis', 'Worms', 'Spots', 'Maze',
                                                                  'Custom (Customf / Customk)']}),
        ('Customf', 'Float', 0.0545, {'min': 0, 'max': 0.1, 'label': 'Custom feed'}),
        ('Customk', 'Float', 0.062, {'min': 0, 'max': 0.1, 'label': 'Custom kill'}),
        ('Play', 'Toggle', True, {'label': 'Play'}),
        ('Steps', 'Menu', '4', {'names': ['1', '2', '4'], 'labels': ['1 step / frame', '2 steps / frame',
                                                                    '4 steps / frame']}),
        ('Stopat', 'Int', -1, {'min': -1, 'max': 5000, 'label': 'Stop after N steps (-1 = run)'}),
        ('Reseed', 'Pulse', None, {'label': 'Reseed'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
        ('Density', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Seed spot density'}),
        ('Spotsize', 'Float', 0.3, {'min': 0.05, 'max': 0.5, 'label': 'Seed spot radius (cells)'}),
        ('Simres', 'Int', 256, {'min': 32, 'max': 1024, 'clampmin': 16, 'clampmax': 1024,
                                'label': 'Sim resolution (square, wraps)'}),
        ('Resetat', 'Float', -100.0, {'min': -100, 'max': 100, 'label': 'internal: frame of the last Reseed'}),
    ]),
    ('Surface', [
        ('Shape', 'Menu', 'torus', {'names': SHAPES, 'labels': ['Torus (u, v both wrap)', 'Sphere', 'Plane']}),
        ('Height', 'Float', 0.15, {'min': -0.5, 'max': 0.5, 'label': 'Height x V (along the normal)'}),
        ('Cols', 'Int', 256, {'min': 8, 'max': 512, 'clampmin': 2, 'clampmax': 512, 'label': 'Mesh columns (u)'}),
        ('Rows', 'Int', 128, {'min': 8, 'max': 512, 'clampmin': 2, 'clampmax': 512, 'label': 'Mesh rows (v)'}),
        ('Spin', 'Float', 10.0, {'min': -90, 'max': 90, 'label': 'Spin deg / s (y)'}),
        ('Tilt', 'Float', 60.0, {'min': -90, 'max': 90, 'label': 'Tilt deg (x)'}),
        ('Dist', 'Float', 5.2, {'min': 0.5, 'max': 10, 'label': 'Camera distance (5.2 fits the torus in 9:16)'}),
        ('Zoom', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Zoom'}),
        ('Palette', 'Menu', 'bio', {'names': PALETTES, 'labels': ['Bio', 'Fire', 'Ice', 'Mono', 'Ink']}),
        ('Light', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Lambert amount'}),
        ('Rim', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Rim light'}),
    ]),
    OUT_PAGE,
]
PANEL_PAGES = ['Rd3d', 'Surface']
FIRST = {'Simres': 128, 'Cols': 128, 'Rows': 64, 'Steps': '1'}

SIMRES = "parent().par.Simres.eval()"
F_E = ("parent().par.Customf.eval() if parent().par.Preset.eval() == 'custom' else "
       + repr([f for f, _k in PRESET_FK]) + "[parent().par.Preset.menuIndex]")
K_E = ("parent().par.Customk.eval() if parent().par.Preset.eval() == 'custom' else "
       + repr([k for _f, k in PRESET_FK]) + "[parent().par.Preset.menuIndex]")
SIM_UNIFORMS = [
    ('uP', (F_E, K_E, "1.0 if parent().par.Play.eval() else 0.0",
            "1.0 if absTime.frame - parent().par.Resetat.eval() < 2 else 0.0")),
    ('uP2', ("float(parent().par.Stopat.eval())", "float(parent().par.Seed.eval())", PP.format('Density'),
             PP.format('Spotsize'))),
    ('uP3', ("float(parent().par.Steps.eval())", "0.0", "0.0", "0.0")),
]


def _pal(k):
    return "%r[parent().par.Palette.menuIndex][%d][%d]" % ([[list(a), list(b)] for a, b in PAL], k // 3, k % 3)


MAT_UNIFORMS = [
    ('uS', ("float(parent().par.Shape.menuIndex)", PP.format('Height'),
            "parent().par.Resw.eval() / max(parent().par.Resh.eval(), 1)", "float(parent().par.Cols.eval())")),
    ('uS2', ("float(parent().par.Rows.eval())", "0.0", "0.0", "0.0")),
    ('uC1', (_pal(0), _pal(1), _pal(2), "0.0")),
    ('uC2', (_pal(3), _pal(4), _pal(5), PP.format('Rim'))),
    ('uCam', ("0.0", "0.0", PP.format('Dist'), PP.format('Light'))),
]

HASH = """
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float h2(int x, int y, int s)
{
    uint h = lowbias(uint(y) * 2891336453u + uint(s) * 1597334677u + 7u);
    h = lowbias(h ^ (uint(x) * 747796405u));
    return float(h >> 8) / 16777216.0;
}
"""

GS = """// POP_rd3d Gray-Scott step (compute, T-47). in0 = previous state (r U, g V, b step count, a 1). Wrap edges.
// One step (reference for GSF, which runs Steps of these per dispatch). Mirror: pop_rd3d_logic.gs_step / seed_state.
uniform vec4 uP;    // feed, kill, play, reset
uniform vec4 uP2;   // stopat (-1 = run), seed, density, spot radius (cells)
layout(local_size_x = 8, local_size_y = 8) in;
#define SEED_CELL 16
""" + HASH + """
vec4 seedv(ivec2 p)
{
    ivec2 cell = p / SEED_CELL;
    bool on = h2(cell.x, cell.y, int(uP2.y + 0.5)) < uP2.z;
    vec2 f = (vec2(p % SEED_CELL) + 0.5) / float(SEED_CELL) - 0.5;
    bool inside = dot(f, f) < uP2.w * uP2.w;
    return vec4(1.0, (on && inside) ? 1.0 : 0.0, 0.0, 1.0);
}
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= sz.x || p.y >= sz.y) return;
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (uP.w > 0.5 || isz != sz) { TDImageStoreOutput(0, ivec3(p, 0), seedv(p)); return; }
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uP.z < 0.5 || (uP2.x >= 0.0 && c.b >= uP2.x)) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    vec2 e = texelFetch(sTD2DInputs[0], (p + ivec2(1, 0)) % sz, 0).rg + texelFetch(sTD2DInputs[0], (p + ivec2(sz.x - 1, 0)) % sz, 0).rg
           + texelFetch(sTD2DInputs[0], (p + ivec2(0, 1)) % sz, 0).rg + texelFetch(sTD2DInputs[0], (p + ivec2(0, sz.y - 1)) % sz, 0).rg;
    vec2 d = texelFetch(sTD2DInputs[0], (p + ivec2(1, 1)) % sz, 0).rg + texelFetch(sTD2DInputs[0], (p + ivec2(1, sz.y - 1)) % sz, 0).rg
           + texelFetch(sTD2DInputs[0], (p + ivec2(sz.x - 1, 1)) % sz, 0).rg + texelFetch(sTD2DInputs[0], (p + ivec2(sz.x - 1, sz.y - 1)) % sz, 0).rg;
    vec2 L = 0.2 * e + 0.05 * d - c.rg;
    float uvv = c.r * c.g * c.g;
    float U = c.r + (1.0 * L.x - uvv + uP.x * (1.0 - c.r)) * 1.0;
    float V = c.g + (0.5 * L.y + uvv - (uP.x + uP.y) * c.g) * 1.0;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(U, V, c.b + 1.0, 1.0));
}
"""

GSF = """// POP_rd3d fused Gray-Scott (compute, perf 27 Oct): Steps (1 / 2 / 4) steps in ONE dispatch on a 16 x 16 tile with
// a 4-cell wrapped halo in shared memory (T-199 (3) temporal blocking; was the gs1..gs4 chain of one dispatch each).
// Same per-cell maths and neighbour order as GS, so the state equals the chain's (Reseed = seed only; a size change
// = seed, then Steps - 1 steps, as the chain did). Mirror: pop_rd3d_logic.gs_step / seed_state.
uniform vec4 uP;    // feed, kill, play, reset
uniform vec4 uP2;   // stopat (-1 = run), seed, density, spot radius (cells)
uniform vec4 uP3;   // steps, -, -, -
layout(local_size_x = 16, local_size_y = 16) in;
#define SEED_CELL 16
#define TS 16
#define HALO 4
#define RS 24
""" + HASH + """
shared vec3 sC[RS * RS];
vec4 seedv(ivec2 p)
{
    ivec2 cell = p / SEED_CELL;
    bool on = h2(cell.x, cell.y, int(uP2.y + 0.5)) < uP2.z;
    vec2 f = (vec2(p % SEED_CELL) + 0.5) / float(SEED_CELL) - 0.5;
    bool inside = dot(f, f) < uP2.w * uP2.w;
    return vec4(1.0, (on && inside) ? 1.0 : 0.0, 0.0, 1.0);
}
vec3 stepc(int k)
{
    vec3 c = sC[k];
    if (uP2.x >= 0.0 && c.b >= uP2.x) return c;
    vec2 e = sC[k + 1].rg + sC[k - 1].rg + sC[k + RS].rg + sC[k - RS].rg;
    vec2 d = sC[k + RS + 1].rg + sC[k - RS + 1].rg + sC[k + RS - 1].rg + sC[k - RS - 1].rg;
    vec2 L = 0.2 * e + 0.05 * d - c.rg;
    float uvv = c.r * c.g * c.g;
    float U = c.r + (1.0 * L.x - uvv + uP.x * (1.0 - c.r)) * 1.0;
    float V = c.g + (0.5 * L.y + uvv - (uP.x + uP.y) * c.g) * 1.0;
    return vec3(U, V, c.b + 1.0);
}
void main()
{
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 o = ivec2(gl_WorkGroupID.xy) * TS - HALO;
    int lt = int(gl_LocalInvocationIndex);
    bool fresh = textureSize(sTD2DInputs[0], 0) != sz;
    if (uP.w > 0.5) {
        if (p.x < sz.x && p.y < sz.y) TDImageStoreOutput(0, ivec3(p, 0), seedv(p));
        return;                                              // uniform: every thread returns here
    }
    for (int k = lt; k < RS * RS; k += TS * TS) {
        ivec2 q = (o + ivec2(k % RS, k / RS)) % sz;
        q = (q + sz) % sz;
        sC[k] = fresh ? seedv(q).rgb : texelFetch(sTD2DInputs[0], q, 0).rgb;
    }
    barrier();
    int n = (uP.z < 0.5) ? 0 : clamp(int(uP3.x + 0.5), 1, HALO) - (fresh ? 1 : 0);
    for (int s = 0; s < HALO; s++) {
        if (s >= n) break;                                   // uniform
        vec3 t0 = vec3(0.0), t1 = vec3(0.0), t2 = vec3(0.0);
        int k0 = lt, k1 = lt + TS * TS, k2 = lt + 2 * TS * TS;
        bool i0 = k0 % RS > 0 && k0 % RS < RS - 1 && k0 / RS > 0 && k0 / RS < RS - 1;
        bool i1 = k1 < RS * RS && k1 % RS > 0 && k1 % RS < RS - 1 && k1 / RS > 0 && k1 / RS < RS - 1;
        bool i2 = k2 < RS * RS && k2 % RS > 0 && k2 % RS < RS - 1 && k2 / RS > 0 && k2 / RS < RS - 1;
        if (i0) t0 = stepc(k0);
        if (i1) t1 = stepc(k1);
        if (i2) t2 = stepc(k2);
        barrier();
        if (i0) sC[k0] = t0;
        if (i1) sC[k1] = t1;
        if (i2) sC[k2] = t2;
        barrier();
    }
    if (p.x >= sz.x || p.y >= sz.y) return;
    ivec2 l = ivec2(gl_LocalInvocationID.xy) + HALO;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(sC[l.y * RS + l.x], 1.0));
}
"""

VERT_COMMON = """
const float TAU = 6.283185307179586;
void base(vec2 uv, out vec3 p, out vec3 n)
{
    int s = int(uS.x + 0.5);
    if (s == 0) {
        float a = TAU * uv.x, b = TAU * uv.y;
        float ring = 0.6 + 0.25 * cos(b);
        p = vec3(ring * cos(a), ring * sin(a), 0.25 * sin(b));
        n = vec3(cos(b) * cos(a), cos(b) * sin(a), sin(b));
    } else if (s == 1) {
        float th = TAU * uv.x, ph = 3.14159265358979 * uv.y;
        n = vec3(sin(ph) * cos(th), -cos(ph), sin(ph) * sin(th));
        p = n * 0.7;
    } else {
        p = vec3((uv.x - 0.5) * uS.z, uv.y - 0.5, 0.0);
        n = vec3(0.0, 0.0, 1.0);
    }
}
float dV(vec2 uv)
{
    vec2 t = vec2(fract(uv.x), int(uS.x + 0.5) == 1 ? clamp(uv.y, 0.0, 1.0) : fract(uv.y));
    return textureLod(sSt, t, 0.0).g;
}
vec3 surf(vec2 uv) { vec3 p, n; base(uv, p, n); return p + n * uS.y * dV(uv); }
"""

VERTEX = """// POP_rd3d vertex (TC-11): static Grid POP quads -> torus / sphere / plane, pushed out by Height x V.
uniform sampler2D sSt;
uniform vec4 uS;    // shape, height, aspect, cols
uniform vec4 uS2;   // rows, -, -, -
out Vertex { vec3 wp; vec3 wn; float v; } oV;
""" + VERT_COMMON + """
void main()
{
    vec2 uv = TDPos().xy + 0.5;                 // T-112: TDPos, never raw P
    vec3 p0, n0;
    base(uv, p0, n0);
    vec3 p = surf(uv);
    vec2 e = vec2(1.0 / max(uS.w - 1.0, 1.0), 1.0 / max(uS2.x - 1.0, 1.0));
    vec3 n = cross(surf(uv + vec2(e.x, 0.0)) - p, surf(uv + vec2(0.0, e.y)) - p);
    n = length(n) > 1e-12 ? normalize(n) : n0;
    if (dot(n, n0) < 0.0) n = -n;
    vec4 w = TDDeform(p);
    oV.wp = w.xyz;
    oV.wn = normalize(TDDeformNorm(n));
    oV.v = dV(uv);
    gl_Position = TDWorldToProj(w);
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

PIXEL = """// POP_rd3d pixel: palette by V, lambert + rim, opaque.
uniform vec4 uC1;   // colour low V
uniform vec4 uC2;   // colour high V, rim
uniform vec4 uCam;  // camera xyz (world), light amount
in Vertex { vec3 wp; vec3 wn; float v; } iV;
layout(location = 0) out vec4 fragColor;
void main()
{
    TDCheckDiscard();
    vec3 n = normalize(iV.wn);
    vec3 V = normalize(uCam.xyz - iV.wp);
    if (dot(n, V) < 0.0) n = -n;
    float lam = max(dot(n, normalize(vec3(0.4, 0.6, 0.7))), 0.0);
    vec3 col = mix(uC1.rgb, uC2.rgb, smoothstep(0.0, 0.4, iV.v));
    float rim = pow(1.0 - max(dot(n, V), 0.0), 3.0) * uC2.w;
    vec3 c = col * (0.25 + 0.75 * mix(1.0, lam, uCam.w)) + rim * uC2.rgb;
    fragColor = TDOutputSwizzle(vec4(c, 1.0));
}
"""

PULSES = """# POP_rd3d pulses: Reseed stamps the frame; the gs passes write the seed for 2 frames (uP.w).
def onPulse(par):
    if par.name == 'Reseed':
        par.owner.par.Resetat = absTime.frame
    return
"""

CAM = {'tz': PP.format('Dist'), 'viewanglemethod': ('menu', 'vertfov'),
       'fov': "40.0 / max(parent().par.Zoom.eval(), 0.01)", 'near': 0.01, 'far': 100.0}


def shader_texts():
    return {'gs': GSF, 'gs_step': GS, 'vertex': VERTEX, 'pixel': PIXEL}


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_rd3d (TC-11): Gray-Scott on a wrap texture (fused compute pass, Steps 1/2/4 per dispatch) '
                                 'grows on a torus / sphere / plane Grid POP mesh, displaced by Height x V in the MAT '
                                 'vertex shader. Pulse Reseed; Stopat = freeze after N steps. Out: out1, out2 = state.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    if first:
        _apply_first(c, FIRST)
    c.par.Resetat = absTime.frame                       # seed on the first cooks (a zero field is a dead fixed point)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Passthrough when Amount 0 (the look itself is an opaque object on transparent).'
    pe = _mk(c, parameterexecuteDAT, 'pulses')
    if pe.text != PULSES:
        pe.text = PULSES
    pe.par.op = c
    pe.par.pars = 'Reseed'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = False
    pe.par.onpulse = True
    blank = _blank(c, 'blank', SIMRES, SIMRES, 'rgba32float')
    blank.comment = 'Sim-res zero: Feedback start (a size mismatch / zero field reseeds in the shader).'
    fb = _feedback(c, 'state_fb', 'state', blank)
    for n in ('gs1', 'gs2', 'gs3', 'gs4', 'gs1_compute', 'gs2_compute', 'gs3_compute', 'gs4_compute', 'step_sel'):
        _sd(c.op(n))                                # the pre-27-Oct chain (one dispatch per step)
    g = _compute(c, 'gs', GSF, [fb], SIMRES, SIMRES, 'rgba32float', SIM_UNIFORMS)
    g.comment = 'Steps (1 / 2 / 4) Gray-Scott steps in one dispatch (16 x 16 tile + 4-cell wrapped halo, shared memory).'
    st = _mk(c, nullTOP, 'state')
    _wire(g, st)
    st.comment = 'This frame\'s state; state_fb reads it next frame; the MAT samples it.'
    o2 = _mk(c, outTOP, 'out2')
    _wire(st, o2)
    clk = _clock(c, 'clock', "parent().par.Spin.eval()")
    clk.comment = 'Spin angle (deg) = integral of Spin.'
    g = _grid(c, 'surf', "parent().par.Cols.eval()", "parent().par.Rows.eval()", 'quads')
    g.comment = 'Static Cols x Rows quads (size 1 x 1): (u, v) = TDPos().xy + 0.5 -> shape in the MAT.'
    m = _mat(c, 'mat', VERTEX, PIXEL, samplers=[('sSt', 'state', 'linear')], spec=MAT_UNIFORMS, blend='none',
             depth=True)
    _try(m, 'sampler0extendu', 'repeat')
    _try(m, 'sampler0extendv', 'repeat')
    m.comment = 'Vertex: shape(u, v) + n x Height x V, finite-difference normal. Pixel: palette by V, lambert + rim.'
    geo = _geo(c, 'geo', 'surf', 'mat')
    _expr(geo.par.rx, PP.format('Tilt'))
    _expr(geo.par.ry, "float(op('clock')[0])")
    cam = _cam(c, 'cam', CAM)
    cam.comment = 'At z = Dist looking -z.'
    r = _render(c, 'render', 'cam', 'geo', fmt='rgba16float', aa='aa4')
    r.comment = 'Surface render (rgba16f, opaque object on transparent).'
    _out_switch(c, in1, r)
    stages = [
        {'title': '1 In + control', 'role': 'input', 'ops': ['in1', 'pulses', 'clock_rate', 'clock'],
         'body': 'pulses: Reseed. clock = spin angle.'},
        {'title': '2 Gray-Scott (wrap)', 'role': 'process',
         'ops': ['blank', 'state_fb', 'gs', 'gs_compute', 'state', 'out2'],
         'body': 'state_fb -> gs (Steps steps in one dispatch) -> state.'},
        {'title': '3 Surface (static Grid POP)', 'role': 'process',
         'ops': ['surf', 'mat', 'mat_vertex', 'mat_pixel', 'geo'], 'body': 'Grid POP quads -> shape + Height x V.'},
        {'title': '4 Render + out', 'role': 'output', 'ops': ['cam', 'render', 'out_sel', 'out1'],
         'body': 'Amount 0 = in1 untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
