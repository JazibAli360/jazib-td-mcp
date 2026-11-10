# pop_collide - POP_collide (BUILD_PLAN_27OCT lane H, row FX7b TC-14 "Ray POP collisions", elekktronaut T78 /
# paketa12). Particles rain from an emitter, bounce and slide off a floor, up to 4 spheres and 2 boxes; wind, drag,
# restitution, friction, life + respawn, Persist trails. Doc + LIVE CHECKS: docs/builds/pop_lane_h.md "TC-14".
# Route (decided offline 27 Oct): Ray POP / GLSL ray queries / hardware collision do NOT run on macOS (MoltenVK,
# Z_forum_nodes_comps.md, T-35): analytic SDF colliders in ONE compute GLSL TOP `state` (2 rgba32f colour buffers
# updated IN PLACE, FX6 probe 5a; b0 = pos + life, b1 = vel + generation), drawn by a STATIC Grid POP of points + GLSL
# MAT (pop_collide_logic.POINTS_VERTEX) into a Render TOP, then a write-only compute look over in1 (Persist > 0 adds
# the `acc` pass before it; perf 27 Oct, was an in-place buffer). No POP compute, no
# attribute layout (T-124). numpy mirror: builders/pop_collide_logic.py (step, test_series).
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_collide.py').read(), ns); ns['build']('/project1/lab', first=True)
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())
_LG = {}
with open(HERE + '/pop_collide_logic.py') as _fh:
    exec(_fh.read(), _LG)

NAME = 'POP_collide'
CAP = _LG['COUNT_CAP']


def _sphere_pars(k, on, x, y, z, r):
    n = 'Sphere%d' % k
    return [(n + 'on', 'Toggle', on, {'label': 'Sphere %d on' % k}),
            (n + 'x', 'Float', x, {'min': -1, 'max': 1, 'label': 'Sphere %d x' % k}),
            (n + 'y', 'Float', y, {'min': -1, 'max': 1, 'label': 'Sphere %d y' % k}),
            (n + 'z', 'Float', z, {'min': -1, 'max': 1, 'label': 'Sphere %d z' % k}),
            (n + 'r', 'Float', r, {'min': 0, 'max': 0.5, 'label': 'Sphere %d radius' % k})]


def _box_pars(k, on, c, hb):
    n = 'Box%d' % k
    out = [(n + 'on', 'Toggle', on, {'label': 'Box %d on' % k})]
    for ax, v in zip('xyz', c):
        out.append((n + ax, 'Float', v, {'min': -1, 'max': 1, 'label': 'Box %d centre %s' % (k, ax)}))
    for ax, v in zip('xyz', hb):
        out.append((n + 'h' + ax, 'Float', v, {'min': 0, 'max': 0.5, 'label': 'Box %d half size %s' % (k, ax)}))
    return out


_D = _LG['DEFAULTS']
_SPH = sum([_sphere_pars(k + 1, bool(s[3] > 0), s[0], s[1], s[2], s[3] if s[3] > 0 else 0.1)
            for k, s in enumerate(_D['spheres'])], [])
_BOX = sum([_box_pars(k + 1, bool(b[2]), b[0], b[1]) for k, b in enumerate(_D['boxes'])], [])

PAGES = [
    ('Collide', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Count', 'Int', 16384, {'min': 1, 'max': CAP, 'clampmin': 1, 'clampmax': CAP, 'label': 'Particles'}),
        ('Speed', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Speed (sim seconds per second at 60 fps)'}),
        ('Substeps', 'Int', 2, {'min': 1, 'max': 4, 'clampmin': 1, 'clampmax': 4, 'label': 'Substeps'}),
        ('Gravity', 'Float', -0.8, {'min': -4, 'max': 4, 'label': 'Gravity (units / s2)'}),
        ('Drag', 'Float', 0.1, {'min': 0, 'max': 5, 'label': 'Drag'}),
        ('Wind', 'Float', 0.2, {'min': 0, 'max': 4, 'label': 'Wind (value noise)'}),
        ('Windfreq', 'Float', 3.0, {'min': 0, 'max': 20, 'label': 'Wind frequency'}),
        ('Restitution', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Restitution (bounce)'}),
        ('Friction', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Friction (tangential loss)'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
        ('Reset', 'Pulse', None, {'label': 'Reset'}),
        ('Testmode', 'Toggle', False, {'label': 'Test mode (one particle, no wind / drag)'}),
        ('Testh', 'Float', 0.4, {'min': -0.5, 'max': 0.5, 'label': 'Test particle start y'}),
    ]),
    ('Emitter', [
        ('Emitshape', 'Menu', 'line', {'names': _LG['EMIT_SHAPES'], 'labels': ['Point', 'Disc (xz)', 'Line (x)']}),
        ('Emitx', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Emitter x'}),
        ('Emity', 'Float', 0.48, {'min': -1, 'max': 1, 'label': 'Emitter y'}),
        ('Emitz', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Emitter z'}),
        ('Emitsize', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Emitter size'}),
        ('Emitvx', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Start velocity x'}),
        ('Emitvy', 'Float', -0.1, {'min': -2, 'max': 2, 'label': 'Start velocity y'}),
        ('Emitvz', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Start velocity z'}),
        ('Spread', 'Float', 0.05, {'min': 0, 'max': 2, 'label': 'Velocity spread'}),
        ('Life', 'Float', 6.0, {'min': 0.1, 'max': 30, 'label': 'Life s (x 0.5..1.5)'}),
    ]),
    ('Colliders', [
        ('Floor', 'Toggle', True, {'label': 'Floor on'}),
        ('Floory', 'Float', -0.45, {'min': -1, 'max': 1, 'label': 'Floor y'}),
    ] + _SPH + _BOX),
    _LG['LOOK_PAGE'],
    OUT_PAGE,
]
PANEL_PAGES = ['Collide', 'Emitter', 'Colliders', 'Look']
FIRST = {'Count': 4096, 'Substeps': 1, 'Size': 2.0, 'Persist': 0.0}


def _on(n, val):
    return "(%s if parent().par.%son.eval() else 0.0)" % (val, n)


STATE_SPEC = [
    ('uS', ("parent().par.Speed.eval() / 60.0", "float(parent().par.Substeps.eval())", "float(op('clock')[0])",
            _LG['RESET_E'])),
    ('uN', ("float(parent().par.Count.eval())", "float(" + _LG['SIDE_E'] + ")",
            "1.0 if parent().par.Testmode.eval() else 0.0", "float(parent().par.Seed.eval())")),
    ('uE', (PP.format('Emitx'), PP.format('Emity'), PP.format('Emitz'), PP.format('Emitsize'))),
    ('uE2', ("float(parent().par.Emitshape.menuIndex)", PP.format('Spread'), PP.format('Life'), PP.format('Testh'))),
    ('uV0', (PP.format('Emitvx'), PP.format('Emitvy'), PP.format('Emitvz'), "0.0")),
    ('uF', (PP.format('Gravity'), PP.format('Drag'), PP.format('Wind'), PP.format('Windfreq'))),
    ('uR', ("1.0 if parent().par.Floor.eval() else 0.0", PP.format('Floory'), PP.format('Restitution'),
            PP.format('Friction'))),
] + [('uSp%d' % k, (PP.format('Sphere%dx' % (k + 1)), PP.format('Sphere%dy' % (k + 1)),
                    PP.format('Sphere%dz' % (k + 1)), _on('Sphere%d' % (k + 1), PP.format('Sphere%dr' % (k + 1)))))
     for k in range(4)] + \
    [('uBc%d' % k, (PP.format('Box%dx' % (k + 1)), PP.format('Box%dy' % (k + 1)), PP.format('Box%dz' % (k + 1)),
                    "1.0 if parent().par.Box%don.eval() else 0.0" % (k + 1))) for k in range(2)] + \
    [('uBh%d' % k, (PP.format('Box%dhx' % (k + 1)), PP.format('Box%dhy' % (k + 1)), PP.format('Box%dhz' % (k + 1)),
                    "0.0")) for k in range(2)]

STATE = """// POP_collide state (TC-14): b0 = pos.xyz + life, b1 = vel.xyz + generation (Testmode: steps since reset).
// In place (readwrite, clear off, FX6 5a). Mirror: pop_collide_logic.step (same collider order, same hash).
layout(local_size_x = 8, local_size_y = 8) in;
#define SUBSTEPS 4
uniform vec4 uS;    // dt per cook, substeps, time, reset
uniform vec4 uN;    // count, side, testmode, seed
uniform vec4 uE;    // emitter xyz, size
uniform vec4 uE2;   // shape, spread, life, test start y
uniform vec4 uV0;   // start velocity
uniform vec4 uF;    // gravity, drag, wind, wind freq
uniform vec4 uR;    // floor on, floor y, restitution, friction
uniform vec4 uSp0;
uniform vec4 uSp1;
uniform vec4 uSp2;
uniform vec4 uSp3;
uniform vec4 uBc0;
uniform vec4 uBc1;
uniform vec4 uBh0;
uniform vec4 uBh1;
""" + _LG['HASH_GLSL'] + """
void resolve(inout vec3 p, inout vec3 v, vec3 n, float d)
{
    p -= n * d;
    float vn = dot(v, n);
    if (vn < 0.0) {
        vec3 vt = v - vn * n;
        v = vt * (1.0 - uR.w) - uR.z * vn * n;
    }
}
void sphere(inout vec3 p, inout vec3 v, vec4 s)
{
    if (s.w <= 0.0) return;
    vec3 q = p - s.xyz;
    float L = length(q);
    float d = L - s.w;
    if (d < 0.0) resolve(p, v, L > 1e-6 ? q / max(L, 1e-6) : vec3(0.0, 1.0, 0.0), d);
}
void box(inout vec3 p, inout vec3 v, vec4 c, vec4 hb)
{
    if (c.w < 0.5) return;
    vec3 q = p - c.xyz;
    vec3 dq = abs(q) - hb.xyz;
    if (!(dq.x < 0.0 && dq.y < 0.0 && dq.z < 0.0)) return;
    int a = dq.x >= dq.y ? (dq.x >= dq.z ? 0 : 2) : (dq.y >= dq.z ? 1 : 2);
    vec3 n = vec3(0.0);
    n[a] = q[a] < 0.0 ? -1.0 : 1.0;
    resolve(p, v, n, dq[a]);
}
void collide(inout vec3 p, inout vec3 v)
{
    if (uR.x > 0.5) { float d = p.y - uR.y; if (d < 0.0) resolve(p, v, vec3(0.0, 1.0, 0.0), d); }
    sphere(p, v, uSp0);
    sphere(p, v, uSp1);
    sphere(p, v, uSp2);
    sphere(p, v, uSp3);
    box(p, v, uBc0, uBh0);
    box(p, v, uBc1, uBh1);
}
void main()
{
    ivec2 px = ivec2(gl_GlobalInvocationID.xy);
    int side = int(uN.y + 0.5);
    if (px.x >= side || px.y >= side) return;
    int i = px.y * side + px.x;
    bool test = uN.z > 0.5;
    int n = test ? 1 : min(int(uN.x + 0.5), side * side);
    vec4 P = TDImageLoadOutput(0, ivec3(px, 0));
    vec4 V = TDImageLoadOutput(1, ivec3(px, 0));
    bool reset = uS.w > 0.5;
    if (reset) { P.w = 0.0; V.w = 0.0; }
    if (bad(P) || bad(V)) { P = vec4(0.0); V = vec4(0.0); }
    if (i >= n) {
        TDImageStoreOutput(0, ivec3(px, 0), vec4(0.0, -1000.0, 0.0, -1.0));
        TDImageStoreOutput(1, ivec3(px, 0), vec4(0.0));
        return;
    }
    bool run = true;
    if (test) {
        if (P.w <= 0.0 || reset) { P = vec4(0.0, uE2.w, 0.0, 1.0); V = vec4(0.0); run = false; }
    } else if (P.w <= 0.0) {
        float g = floor(V.w + 0.5) + 1.0;
        int s = int(g) * 7919 + int(uN.w + 0.5);
        float r0 = h1(i * 8 + 0, s), r1 = h1(i * 8 + 1, s), r2 = h1(i * 8 + 2, s);
        float r3 = h1(i * 8 + 3, s), r4 = h1(i * 8 + 4, s), r5 = h1(i * 8 + 5, s);
        int shape = int(uE2.x + 0.5);
        vec3 off = vec3(0.0);
        if (shape == 1) { float a = TAU * r0, rad = sqrt(r1) * uE.w; off = vec3(cos(a) * rad, 0.0, sin(a) * rad); }
        else if (shape == 2) off = vec3((r0 - 0.5) * 2.0 * uE.w, 0.0, 0.0);
        P = vec4(uE.xyz + off, uE2.z * (0.5 + r5));
        V = vec4(uV0.xyz + uE2.y * 2.0 * vec3(r2 - 0.5, r3 - 0.5, r4 - 0.5), g);
        run = false;
    }
    if (run) {
        int nsub = clamp(int(uS.y + 0.5), 1, SUBSTEPS);
        float h = uS.x / float(nsub);
        float t = uS.z;
        int seed = int(uN.w + 0.5);
        vec3 p = P.xyz, v = V.xyz;
        for (int k = 0; k < SUBSTEPS; k++) {
            if (k >= nsub) break;
            vec3 acc = vec3(0.0, uF.x, 0.0);
            if (!test) {
                vec2 b = p.xy * uF.w;
                acc.x += uF.z * (vnoise(b + vec2(t, 0.0), seed) - 0.5);
                acc.y += uF.z * (vnoise(b + vec2(17.3, t), seed) - 0.5);
            }
            v += acc * h;
            if (!test) v *= max(1.0 - uF.y * h, 0.0);
            p += v * h;
            collide(p, v);
        }
        P.xyz = p;
        V.xyz = v;
        if (test) V.w += 1.0; else P.w -= uS.x;
    }
    TDImageStoreOutput(0, ivec3(px, 0), P);
    TDImageStoreOutput(1, ivec3(px, 0), V);
}
"""

POINTS_VERTEX = _LG['POINTS_VERTEX']
POINTS_PIXEL = _LG['POINTS_PIXEL']
LOOK_U = [('uL', ("parent().par.Persist.eval()", "parent().par.Gain.eval()",
                  "1.0 if parent().par.Persist.eval() > 0 else 0.0", "0.0"))]
ACC_U = [('uA', ("parent().par.Persist.eval()", "parent().par.Gain.eval()",
                 "float(absTime.frame - (lambda k, f: k if k <= f else -99)(parent().fetch('jz_pon', -99, search=False), absTime.frame))", "0.0"))]
LOOK = """// POP_collide look (perf 27 Oct, b3 wave 3): ONE write-only buffer. out = acc over in1 (premultiplied), acc =
// render x Gain (Persist 0, the default: bit-exact with the old in-place look) or the `acc` pass (Persist > 0, already
// gained). Was the lane-H look with acc in colour buffer 1 read-write in place: such 1080x1920 instances cook 3-5x
// slower on some fresh copies (T-216 (1); main final pass look 1.75 ms).
layout(local_size_x = 8, local_size_y = 8) in;
uniform vec4 uL;    // persist, gain, in0 is acc (1) / render (0), -
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= int(uTDOutputInfo.res.z) || p.y >= int(uTDOutputInfo.res.w)) return;
    vec2 uv = (vec2(p) + 0.5) * uTDOutputInfo.res.xy;
    vec4 r = texture(sTD2DInputs[0], uv);
    vec4 acc = uL.z > 0.5 ? r : r * uL.y;
    vec4 c = vec4(acc.rgb, clamp(acc.a, 0.0, 1.0));
    vec4 bg = texture(sTD2DInputs[1], uv);
    TDImageStoreOutput(0, ivec3(p, 0), c + bg * (1.0 - c.a));
}
"""
ACC = """// POP_collide acc (cooks only while Persist > 0: acc_sel + the acc_fb target gate, T-216 (3)): acc = render x Gain +
// Persist x last acc (acc_fb), rgba16f like the old in-place buffer 1. uA.z = frames since Persist left 0 (persist_exec
// stamps jz_pon): the first frame starts from zero (acc_fb still holds the picture from the last time trails were on).
layout(local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;    // persist, gain, frames since Persist > 0, -
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec2 uv = (vec2(p) + 0.5) * uTDOutputInfo.res.xy;
    vec4 r = texture(sTD2DInputs[0], uv) * uA.y;
    vec4 last = (uA.z >= 1.0 && textureSize(sTD2DInputs[1], 0) == sz) ? texelFetch(sTD2DInputs[1], p, 0) : vec4(0.0);
    TDImageStoreOutput(0, ivec3(p, 0), r + last * uA.x);
}
"""
PON = """# POP_collide persist_exec: stamp the frame Persist leaves 0 (the acc pass then starts from zero, not from the
# picture acc_fb kept from the last time trails were on).
def onValueChange(par, prev):
    if par.name == 'Persist' and par.eval() > 0 and not (prev > 0):
        parent().store('jz_pon', absTime.frame)
    return
"""


def shader_texts():
    return {'state': STATE, 'vertex': POINTS_VERTEX, 'pixel': POINTS_PIXEL, 'look': LOOK, 'acc': ACC}


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_collide (TC-14): particles from an emitter bounce off a floor, 4 spheres and 2 '
                                 'boxes (analytic SDF, compute state in place; Ray POP does not run on macOS). '
                                 'Testmode = one particle for the bounce check. Amount 0 = in1 untouched. Out: out1.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    if first:
        _apply_first(c, FIRST)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Background (premultiplied); particles composite over it.'
    _clock(c, 'clock', "parent().par.Speed.eval()")
    px = _mk(c, parameterexecuteDAT, 'reset_exec')
    if px.text != _LG['PEXEC']:
        px.text = _LG['PEXEC']
    px.par.op = c
    px.par.pars = 'Reset Count Testmode Seed Testh Emitshape'
    px.par.custom = True
    px.par.builtin = False
    px.par.valuechange = True
    px.par.onpulse = True
    px.comment = 'Reset pulse / Count / Testmode / Seed / Testh / Emitshape change -> jz_reset frame (3 reset cooks).'
    side = _LG['SIDE_E']
    st = _compute(c, 'state', STATE, [], side, side, fmt='rgba32float', spec=STATE_SPEC, bufs=2, inplace=True)
    st.comment = 'Particle state, side x side texels, 2 rgba32f buffers in place (b0 pos + life, b1 vel + gen).'
    sv = _mk(c, renderselectTOP, 'state_v')
    sv.par.top = 'state'
    sv.par.bufferindex = 1
    sv.comment = 'state colour buffer 1 (velocity + generation / test steps).'
    g = _grid(c, 'pts', side, side, 'points')
    g.comment = 'Static side x side points: TDPos().xy + 0.5 = the state texel (mat vertex, T-112).'
    m = _mat(c, 'mat', POINTS_VERTEX, POINTS_PIXEL, samplers=[('sP', 'state', 'nearest'), ('sV', 'state_v', 'nearest')],
             spec=_LG['POINT_SPEC'], blend='add', depth=False)
    m.comment = 'Points: state texel -> world pos -> TDWorldToProj; additive one/one, depth off; hue by speed.'
    geo = _geo(c, 'geo', 'pts', 'mat')
    _expr(geo.par.rx, PP.format('Tilt'))
    _expr(geo.par.ry, PP.format('Orbit'))
    cam = _cam(c, 'cam', _LG['CAM'])
    cam.comment = 'At z = Dist looking -z; the 1-unit-tall frame at z 0 fills the output at Zoom 1.'
    r = _render(c, 'render', 'cam', 'geo', fmt='rgba16float', aa='aa1')
    r.comment = 'Particles (additive, rgba16f, transparent background).'
    pe = _mk(c, parameterexecuteDAT, 'persist_exec')
    if pe.text != PON:
        pe.text = PON
    pe.par.op = c
    pe.par.pars = 'Persist'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = True
    pe.par.onpulse = False
    pe.comment = 'Persist leaves 0 -> jz_pon frame (the acc pass starts from zero).'
    ab = _blank(c, 'acc_blank', RESW, RESH, 'rgba16float')
    ab.comment = 'Zero acc (Feedback start / size change).'
    afb = _feedback(c, 'acc_fb', 'acc', ab)
    _expr(afb.par.top, "'acc' if parent().par.Persist.eval() > 0 else ''")
    afb.comment = ("Last frame's acc. Target only while Persist > 0: a Feedback TOP cooks its target every frame it "
                   "cooks itself (T-216 (3)).")
    ac = _compute(c, 'acc', ACC, [r, afb], RESW, RESH, fmt='rgba16float', spec=ACC_U, filt='linear')
    ac.comment = 'Trails: acc = render x Gain + Persist x acc_fb (write-only, cooks only while Persist > 0).'
    asel = _mk(c, switchTOP, 'acc_sel')
    _wire(r, asel, 0)
    _wire(ac, asel, 1)
    _expr(asel.par.index, "1 if parent().par.Persist.eval() > 0 else 0")
    asel.comment = 'Persist 0 = the render itself (acc does not cook), else acc.'
    lk = _compute(c, 'look', LOOK, [asel, in1], RESW, RESH, fmt='rgba16float', spec=LOOK_U, filt='linear')
    _try(lk, 'numcolorbufs', 1)                    # rebuilds of the old 2-buffer in-place look
    _try(lk, 'outputaccess', 'writeonly')
    _try(lk, 'clearoutputs', True)
    lk.comment = 'out = (render x Gain, or acc) over in1. One write-only buffer.'
    _out_switch(c, in1, lk)
    stages = [
        {'title': '1 In + clock', 'role': 'input', 'ops': ['in1', 'clock_rate', 'clock', 'reset_exec'],
         'body': 'in1 = background. clock = module time (wind). reset_exec stamps jz_reset.'},
        {'title': '2 State (in place)', 'role': 'process', 'ops': ['state', 'state_compute', 'state_v'],
         'body': 'Spawn / gravity / wind / drag / substeps / floor + spheres + boxes / life.'},
        {'title': '3 Points render', 'role': 'process', 'ops': ['pts', 'mat', 'mat_vertex', 'mat_pixel', 'geo', 'cam',
                                                               'render'],
         'body': 'Grid POP points -> mat reads state -> additive sprites.'},
        {'title': '4 Look + out', 'role': 'output',
         'ops': ['persist_exec', 'acc_blank', 'acc_fb', 'acc', 'acc_compute', 'acc_sel', 'look', 'look_compute',
                 'out_sel', 'out1'],
         'body': 'Persist > 0: acc = render x Gain + Persist x acc_fb -> acc_sel -> look over in1. Amount 0 = in1 '
                 'untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
