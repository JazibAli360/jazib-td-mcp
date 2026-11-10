# pop_fillbody - POP_fillbody (BUILD_PLAN_27OCT lane H, row FX7b TC-15 "Swarm fills an animated mesh", Memo Akten).
# Glowing points wander INSIDE a moving body and stay inside while it dances; trails via Persist. Doc + LIVE CHECKS:
# docs/builds/pop_lane_h.md "TC-15".
# Route (decided offline 27 Oct): Sprinkle POP volume modes need hardware ray tracing (not on macOS, MoltenVK) -> the
# body is an SDF: union of <= 16 capsules. `caps` (compute 16 x 2 rgba32f) writes the capsule table each frame from
# the built-in procedural dancer (pose maths in GLSL, module time x Dancespeed + Posetime) or from a CHOP (in CHOP:
# channels x y z w, 2 samples per capsule: a + r, b); `state` (ONE compute TOP, 2 rgba32f buffers IN PLACE, FX6 5a)
# spawns inside by bounded rejection sampling and steps wander + damping + keep-inside (project along the SDF
# gradient). Drawn by the shared lane-H points MAT over a STATIC Grid POP (T-112), compute look (Persist) over in1.
# No POP compute, no attribute layout (T-124). numpy mirror: builders/pop_fillbody_logic.py.
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_fillbody.py').read(), ns); ns['build']('/project1/lab', first=True)
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())
_LG = {}
with open(HERE + '/pop_collide_logic.py') as _fh:      # shared with POP_collide: hash, points MAT, look, Look page
    exec(_fh.read(), _LG)

NAME = 'POP_fillbody'
CAP = _LG['COUNT_CAP']

PAGES = [
    ('Fillbody', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Count', 'Int', 16384, {'min': 1, 'max': CAP, 'clampmin': 1, 'clampmax': CAP, 'label': 'Particles'}),
        ('Speed', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Speed'}),
        ('Substeps', 'Int', 2, {'min': 1, 'max': 4, 'clampmin': 1, 'clampmax': 4, 'label': 'Substeps'}),
        ('Wander', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Wander force'}),
        ('Wanderfreq', 'Float', 6.0, {'min': 0, 'max': 40, 'label': 'Wander frequency'}),
        ('Damp', 'Float', 2.0, {'min': 0, 'max': 20, 'label': 'Damping'}),
        ('Margin', 'Float', 0.004, {'min': 0, 'max': 0.05, 'label': 'Keep this far inside the skin'}),
        ('Respawn', 'Float', 0.02, {'min': 0, 'max': 2, 'label': 'Respawn per second (fraction)'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (spawn inside again)'}),
    ]),
    ('Body', [
        ('Bodysrc', 'Menu', 'dancer', {'names': ['dancer', 'chop'], 'labels': ['Procedural dancer (12 capsules)',
                                                                            'CHOP capsules (in CHOP, x y z w rows)']}),
        ('Dancespeed', 'Float', 0.5, {'min': 0, 'max': 3, 'label': 'Dance speed (0 = frozen pose)'}),
        ('Posetime', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Pose time offset s'}),
        ('Pose', 'Float', 1.0, {'min': 0, 'max': 1.5, 'label': 'Pose amount (0 = standing)'}),
        ('Bodyx', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Body x'}),
        ('Bodyy', 'Float', 0.04, {'min': -1, 'max': 1, 'label': 'Body y'}),
        ('Bodyz', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Body z'}),
        ('Bodyscale', 'Float', 0.9, {'min': 0.1, 'max': 3, 'label': 'Body scale'}),
    ]),
    _LG['LOOK_PAGE'],
    OUT_PAGE,
]
PANEL_PAGES = ['Fillbody', 'Body', 'Look']
FIRST = {'Count': 4096, 'Substeps': 1, 'Size': 2.0, 'Persist': 0.0}

NCAPS_E = ("12.0 if parent().par.Bodysrc.eval() == 'dancer' else "
           "float(min(16, op('caps_chop').numSamples // 2 if op('caps_sel').par.index.eval() > 0.5 else 0))")
TB_E = "float(op('clock')[0]) * parent().par.Dancespeed.eval() + parent().par.Posetime.eval()"

CAPS_SPEC = [
    ('uB', ("1.0 if parent().par.Bodysrc.eval() == 'chop' else 0.0", NCAPS_E, TB_E, PP.format('Pose'))),
    ('uB2', (PP.format('Bodyx'), PP.format('Bodyy'), PP.format('Bodyz'), PP.format('Bodyscale'))),
]
STATE_SPEC = CAPS_SPEC + [
    ('uS', ("parent().par.Speed.eval() / 60.0", "float(parent().par.Substeps.eval())", "float(op('clock')[0])",
            _LG['RESET_E'])),
    ('uN', ("float(parent().par.Count.eval())", "float(" + _LG['SIDE_E'] + ")", "float(parent().par.Seed.eval())",
            NCAPS_E)),
    ('uW', (PP.format('Wander'), PP.format('Wanderfreq'), PP.format('Damp'), PP.format('Margin'))),
    ('uW2', (PP.format('Respawn'), "0.0", "0.0", "0.0")),
]

DANCER = """// TAU comes from HASH_GLSL (pop_collide_logic)
void dancer(int k, float t, float amt, out vec3 a, out vec3 b, out float r)
{
    float ph = TAU * t;
    float sw = sin(ph), cw = cos(ph), s2 = sin(2.0 * ph);
    vec3 pelvis = vec3(0.05 * amt * sw, -0.08 + 0.015 * amt * s2, 0.0);
    vec3 neck = pelvis + vec3(0.03 * amt * sin(ph + 0.6), 0.27, 0.02 * amt * cw);
    vec3 head = neck + vec3(0.01 * amt * sw, 0.085, 0.0);
    vec3 shl = neck + vec3(-0.085, -0.025, 0.0), shr = neck + vec3(0.085, -0.025, 0.0);
    float al = 0.3 + amt * (1.3 + 1.0 * sin(ph));
    float ar = 0.3 + amt * (1.3 + 1.0 * sin(ph + 3.14159));
    vec3 el = shl + 0.14 * vec3(-sin(al), -cos(al), 0.15 * amt * cw);
    vec3 er = shr + 0.14 * vec3(sin(ar), -cos(ar), -0.15 * amt * cw);
    float fl = al + 0.4 + 0.8 * amt * (0.5 + 0.5 * sin(2.0 * ph));
    float fr = ar + 0.4 + 0.8 * amt * (0.5 + 0.5 * sin(2.0 * ph + 1.0));
    vec3 hdl = el + 0.13 * vec3(-sin(fl), -cos(fl), 0.0);
    vec3 hdr = er + 0.13 * vec3(sin(fr), -cos(fr), 0.0);
    vec3 hl = pelvis + vec3(-0.06, -0.02, 0.0), hr = pelvis + vec3(0.06, -0.02, 0.0);
    float ll = 0.08 + amt * 0.35 * max(sw, 0.0), lr = 0.08 + amt * 0.35 * max(-sw, 0.0);
    vec3 knl = hl + 0.2 * vec3(-sin(ll), -cos(ll), 0.3 * amt * max(sw, 0.0));
    vec3 knr = hr + 0.2 * vec3(sin(lr), -cos(lr), 0.3 * amt * max(-sw, 0.0));
    vec3 ftl = knl + 0.2 * vec3(-sin(ll * 0.3), -cos(ll * 0.3), -0.2 * amt * max(sw, 0.0));
    vec3 ftr = knr + 0.2 * vec3(sin(lr * 0.3), -cos(lr * 0.3), -0.2 * amt * max(-sw, 0.0));
    a = pelvis; b = neck; r = 0.075;
    if (k == 1) { a = head; b = head; r = 0.065; }
    else if (k == 2) { a = shl; b = shr; r = 0.035; }
    else if (k == 3) { a = hl; b = hr; r = 0.05; }
    else if (k == 4) { a = shl; b = el; r = 0.035; }
    else if (k == 5) { a = shr; b = er; r = 0.035; }
    else if (k == 6) { a = el; b = hdl; r = 0.028; }
    else if (k == 7) { a = er; b = hdr; r = 0.028; }
    else if (k == 8) { a = hl; b = knl; r = 0.05; }
    else if (k == 9) { a = hr; b = knr; r = 0.05; }
    else if (k == 10) { a = knl; b = ftl; r = 0.04; }
    else if (k == 11) { a = knr; b = ftr; r = 0.04; }
}
"""

STATE = """// POP_fillbody state (TC-15): b0 = pos.xyz + (capsule k + phase 0.5..1, > 0 = drawn), b1 = vel.xyz + steps
// (0 = spawn). In place, no inputs: the first 32 threads of each workgroup build the 16 x 2 capsule table (dancer pose
// or CHOP rows; was a separate `caps` pass: merged + shared memory, perf wave 27 Oct, bit-exact) before any return.
// Each particle stays inside the capsule it was born in (analytic
// normal; was the nearest capsule, which drained the swarm into the feet while dancing). Mirror:
// pop_fillbody_logic.step (same order, same hash).
layout(local_size_x = 8, local_size_y = 8) in;
#define SUBSTEPS 4
#define MAXCAPS 16
#define TRIES 32
uniform vec4 uS;    // dt per cook, substeps, time, reset
uniform vec4 uN;    // count, side, seed, ncaps
uniform vec4 uW;    // wander, wander freq, damp, margin
uniform vec4 uW2;   // respawn per s, -, -, -
uniform vec4 uB;    // body: src (0 dancer, 1 chop), ncaps, body time, pose amount
uniform vec4 uB2;   // body origin xyz, scale
uniform samplerBuffer uCaps;   // CHOP rows (samples 2k = a.xyz + r, 2k + 1 = b.xyz)
""" + _LG['HASH_GLSL'] + DANCER + """
shared vec4 CA[MAXCAPS];   // the capsule table in shared memory, loaded once per workgroup (perf wave 27 Oct:
shared vec4 CB[MAXCAPS];   // per-thread arrays are slow on 31550 / Metal, T-187)
int NC;
float sdf(vec3 p)
{
    float d = 1e9;
    for (int k = 0; k < MAXCAPS; k++) {
        if (k >= NC) break;
        if (CB[k].w < 0.5) continue;
        vec3 a = CA[k].xyz, ba = CB[k].xyz - a, pa = p - a;
        float hh = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-12), 0.0, 1.0);
        d = min(d, length(pa - hh * ba) - CA[k].w);
    }
    return d;
}
float capd(vec3 p, int k, out vec3 nr)        // capsule k alone + outward unit normal
{
    vec3 a = CA[k].xyz, ba = CB[k].xyz - a, pa = p - a;
    float hh = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-12), 0.0, 1.0);
    vec3 e = pa - hh * ba;
    float L = length(e);
    nr = L > 1e-12 ? e / L : vec3(0.0);
    return L - CA[k].w;
}
int owner(vec3 p)                               // smallest own distance, first on ties (mirror: owner)
{
    float best = 1e9;
    int kk = 0;
    vec3 nr;
    for (int k = 0; k < MAXCAPS; k++) {
        if (k >= NC) break;
        if (CB[k].w < 0.5) continue;
        float d = capd(p, k, nr);
        if (d < best) { best = d; kk = k; }
    }
    return kk;
}
void main()
{
    uint li = gl_LocalInvocationIndex;          // 64 threads: the first 32 load the 16 x 2 table, before any return
    if (li < uint(2 * MAXCAPS)) {               // capsule k: row 0 a + r, row 1 b + valid (mirror: caps_table)
        int k = int(li) % MAXCAPS;
        int nc = min(int(uB.y + 0.5), MAXCAPS);
        vec3 a = vec3(0.0), b = vec3(0.0);
        float r = 0.0, valid = 0.0;
        if (k < nc) {
            if (uB.x > 0.5) {
                vec4 ra = texelFetch(uCaps, 2 * k);      // k < nc <= numSamples / 2: never out of bounds (T-35)
                vec4 rb = texelFetch(uCaps, 2 * k + 1);
                a = ra.xyz; b = rb.xyz; r = ra.w;
            } else {
                dancer(k, uB.z, uB.w, a, b, r);
            }
            valid = 1.0;
            a = uB2.xyz + uB2.w * a;
            b = uB2.xyz + uB2.w * b;
            r *= uB2.w;
        }
        if (li < uint(MAXCAPS)) CA[k] = vec4(a, r);
        else CB[k] = vec4(b, valid);
    }
    memoryBarrierShared();
    barrier();
    ivec2 px = ivec2(gl_GlobalInvocationID.xy);
    int side = int(uN.y + 0.5);
    if (px.x >= side || px.y >= side) return;
    int i = px.y * side + px.x;
    int n = min(int(uN.x + 0.5), side * side);
    int seed = int(uN.z + 0.5);
    NC = min(int(uN.w + 0.5), MAXCAPS);
    vec4 P = TDImageLoadOutput(0, ivec3(px, 0));
    vec4 V = TDImageLoadOutput(1, ivec3(px, 0));
    if (uS.w > 0.5) V.w = 0.0;
    if (bad(P) || bad(V)) { P = vec4(0.0); V = vec4(0.0); }
    if (i >= n) {
        TDImageStoreOutput(0, ivec3(px, 0), vec4(0.0, -1000.0, 0.0, -1.0));
        TDImageStoreOutput(1, ivec3(px, 0), vec4(0.0));
        return;
    }
    int steps = int(floor(V.w + 0.5));
    bool resp = h1(i, steps * 7919 + seed + 3) < uW2.x * uS.x;
    int kc = int(floor(P.w));
    bool lost = kc < 0 || kc >= NC || CB[clamp(kc, 0, MAXCAPS - 1)].w < 0.5;
    if (V.w < 0.5 || resp || lost) {
        vec3 lo = vec3(1e9), hi = vec3(-1e9);
        for (int k = 0; k < MAXCAPS; k++) {
            if (k >= NC) break;
            if (CB[k].w < 0.5) continue;
            lo = min(lo, min(CA[k].xyz, CB[k].xyz) - CA[k].w);
            hi = max(hi, max(CA[k].xyz, CB[k].xyz) + CA[k].w);
        }
        int s = seed * 7919 + steps;
        int cap = NC > 0 ? i % NC : 0;
        vec3 pos = CA[cap].xyz;
        bool done = false;
        for (int k = 0; k < TRIES; k++) {
            if (done) break;
            vec3 q = lo + (hi - lo) * vec3(h1(i * 64 + 3 * k, s), h1(i * 64 + 3 * k + 1, s), h1(i * 64 + 3 * k + 2, s));
            if (sdf(q) < -uW.w) { pos = q; done = true; }
        }
        if (done) cap = owner(pos);
        P = vec4(pos, float(cap) + 0.5 + 0.5 * h1(i, seed + 11));
        V = vec4(0.0, 0.0, 0.0, floor(V.w + 0.5) + 1.0);
    } else {
        int nsub = clamp(int(uS.y + 0.5), 1, SUBSTEPS);
        float h = uS.x / float(nsub);
        float t = uS.z, F = uW.y;
        vec3 p = P.xyz, v = V.xyz;
        for (int k = 0; k < SUBSTEPS; k++) {
            if (k >= nsub) break;
            vec3 w = vec3(vnoise(vec2(p.y * F + t * 0.3, p.z * F), seed) - 0.5,
                          vnoise(vec2(p.z * F + 13.1, p.x * F + t * 0.3), seed) - 0.5,
                          vnoise(vec2(p.x * F + t * 0.3, p.y * F + 27.7), seed) - 0.5);
            v += 2.0 * uW.x * w * h;
            v *= max(1.0 - uW.z * h, 0.0);
            p += v * h;
            vec3 nr;
            float d = capd(p, kc, nr);                 // own capsule (kc valid here: lost ones respawned)
            if (d > -uW.w) {
                p -= nr * (d + uW.w);
                v -= max(dot(v, nr), 0.0) * nr;
            }
        }
        P.xyz = p;
        V = vec4(v, V.w + 1.0);
    }
    TDImageStoreOutput(0, ivec3(px, 0), P);
    TDImageStoreOutput(1, ivec3(px, 0), V);
}
"""

POINTS_VERTEX = _LG['POINTS_VERTEX']
POINTS_PIXEL = _LG['POINTS_PIXEL']
LOOK = _LG['LOOK_COMPUTE']


def shader_texts():
    return {'state': STATE, 'vertex': POINTS_VERTEX, 'pixel': POINTS_PIXEL, 'look': LOOK}


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_fillbody (TC-15): points wander inside a dancing body (union of <= 16 capsules: '
                                 'procedural dancer or CHOP rows) and stay inside; Persist trails. in CHOP caps_in: '
                                 'x y z w, 2 samples per capsule (a + r, b). Amount 0 = in1 untouched. Out: out1.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    if first:
        _apply_first(c, FIRST)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Background (premultiplied); the swarm composites over it.'
    _clock(c, 'clock', "parent().par.Speed.eval()")
    px = _mk(c, parameterexecuteDAT, 'reset_exec')
    if px.text != _LG['PEXEC']:
        px.text = _LG['PEXEC']
    px.par.op = c
    px.par.pars = 'Reset Count Seed Bodysrc'
    px.par.custom = True
    px.par.builtin = False
    px.par.valuechange = True
    px.par.onpulse = True
    px.comment = 'Reset pulse / Count / Seed / Bodysrc change -> jz_reset frame (spawn inside again).'
    ci = _mk(c, inCHOP, 'caps_in')
    ci.comment = 'Optional capsules: channels x y z w, samples 2k = a.xyz + r, 2k + 1 = b.xyz (max 16 capsules).'
    cd = _mk(c, constantCHOP, 'caps_default')
    for k, ch in enumerate('xyzw'):
        getattr(cd.par, 'name%d' % k).val = ch
        getattr(cd.par, 'value%d' % k).val = 0.0
    cd.comment = 'Stand-in (1 sample of zeros) so the array uniform is never empty.'
    cs = _mk(c, switchCHOP, 'caps_sel')
    _wire(cd, cs, 0)
    _wire(ci, cs, 1)
    _expr(cs.par.index, "1 if op('caps_in').numChans >= 4 and op('caps_in').numSamples >= 2 else 0")
    cn = _mk(c, nullCHOP, 'caps_chop')
    _wire(cs, cn)
    for n in ('caps', 'caps_compute'):          # merged into state (perf wave 27 Oct)
        if c.op(n) is not None:
            _sd(c.op(n))
    side = _LG['SIDE_E']
    st = _compute(c, 'state', STATE, [], side, side, fmt='rgba32float', spec=STATE_SPEC, bufs=2, inplace=True)
    if len(getattr(st, 'inputs', ())):         # an older build wired caps here: no inputs now (nothing pulled)
        for cn in st.inputConnectors:
            cn.disconnect()
    st.seq.array.numBlocks = max(int(st.seq.array.numBlocks), 1)
    st.par.array0name = 'uCaps'
    st.par.array0type = 'vec4'
    st.par.array0chop = 'caps_chop'
    st.par.array0arraytype = 'texturebuffer'
    st.comment = ('Swarm state, 2 rgba32f buffers in place (b0 pos + phase, b1 vel + steps): capsule table per workgroup '
                  '(dancer / CHOP rows), spawn inside, wander, keep inside.')
    sv = _mk(c, renderselectTOP, 'state_v')
    sv.par.top = 'state'
    sv.par.bufferindex = 1
    sv.comment = 'state colour buffer 1 (velocity + steps).'
    g = _grid(c, 'pts', side, side, 'points')
    g.comment = 'Static side x side points: TDPos().xy + 0.5 = the state texel (mat vertex, T-112).'
    m = _mat(c, 'mat', POINTS_VERTEX, POINTS_PIXEL, samplers=[('sP', 'state', 'nearest'), ('sV', 'state_v', 'nearest')],
             spec=_LG['POINT_SPEC'], blend='add', depth=False)
    m.comment = 'Points: state texel -> world pos -> TDWorldToProj; additive, depth off; hue by speed.'
    geo = _geo(c, 'geo', 'pts', 'mat')
    _expr(geo.par.rx, PP.format('Tilt'))
    _expr(geo.par.ry, PP.format('Orbit'))
    cam = _cam(c, 'cam', _LG['CAM'])
    cam.comment = 'At z = Dist looking -z; the 1-unit-tall frame at z 0 fills the output at Zoom 1.'
    r = _render(c, 'render', 'cam', 'geo', fmt='rgba16float', aa='aa1')
    r.comment = 'Swarm (additive, rgba16f, transparent background).'
    lk = _compute(c, 'look', LOOK, [r, in1], RESW, RESH, fmt='rgba16float', spec=_LG['LOOK_SPEC'], bufs=2,
                  inplace=True, filt='linear')
    lk.comment = 'acc (buffer 1, in place) = render x Gain + Persist x acc; out = acc over in1.'
    _out_switch(c, in1, lk)
    stages = [
        {'title': '1 In + clock', 'role': 'input', 'ops': ['in1', 'clock_rate', 'clock', 'reset_exec'],
         'body': 'in1 = background. clock = module time (wander + dance). reset_exec stamps jz_reset.'},
        {'title': '2 Body (capsules)', 'role': 'process', 'ops': ['caps_in', 'caps_default', 'caps_sel', 'caps_chop'],
         'body': 'CHOP rows for Bodysrc chop (state builds the 16 x 2 capsule table itself).'},
        {'title': '3 State (in place)', 'role': 'process', 'ops': ['state', 'state_compute', 'state_v'],
         'body': 'Spawn inside (rejection), wander, damp, keep inside (SDF gradient), respawn.'},
        {'title': '4 Points render', 'role': 'process', 'ops': ['pts', 'mat', 'mat_vertex', 'mat_pixel', 'geo', 'cam',
                                                               'render'],
         'body': 'Grid POP points -> mat reads state -> additive sprites.'},
        {'title': '5 Look + out', 'role': 'output', 'ops': ['look', 'look_compute', 'out_sel', 'out1'],
         'body': 'Persist trails over in1. Amount 0 = in1 untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
