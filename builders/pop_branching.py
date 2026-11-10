# pop_branching - POP_branching (BUILD_PLAN_27OCT lane H, row FX7b TC-10 "emergent feedback branching", Dan Tapper;
# the author warns his Feedback-POP version is unstable: this item is LAST in the lane, or never). Doc + LIVE
# CHECKS: docs/builds/pop_lane_h.md "TC-10". Route (lowest risk, decided offline 27 Oct): no Feedback POP, no POP
# add/delete. A pool of growth tips (up to 4096) lives in a 64 x 65 rgba32f state texture (x, y px, heading, age;
# texel (0, 64) = count, frame); a trail texture at sim res keeps what grew. Per frame (all compute, T-47): `tips`
# (sense 3 sensors ahead like physarum, turn away from trail, wander, move, die on dense trail / wall / age, split
# flag where the trail is thin) -> `alloc` (ONE workgroup: two prefix scans from builders/pop_scan.py, survivors
# densely then children, capped) -> `trail` (wrap 3x3 mix x decay + the deposit gathered per tile from alloc; until
# 27 Oct a Render TOP of 1-px points did the deposit) -> look. numpy mirror: builders/pop_branching_logic.py.
# Run inside TD 2025.31550 through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/pop_branching.py').read(), ns); ns['build']('/project1/lab', first=True)
# ASCII only.
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_common.py') as _fh:
    exec(_fh.read(), globals())
with open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/pop_scan.py') as _fh:
    _SCAN = {}
    exec(_fh.read(), _SCAN)
SCAN_GLSL = _SCAN['SCAN_GLSL']

NAME = 'POP_branching'
TW, TROWS, MAXT = 64, 64, 4096
SEEDMODES = ['center', 'bottom']

PAGES = [
    ('Branching', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (0 = in1 untouched)'}),
        ('Play', 'Toggle', True, {'label': 'Play (off = hold)'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (reseed, clear trail)'}),
        ('Seedmode', 'Menu', 'center', {'names': SEEDMODES, 'labels': ['Centre burst', 'Bottom row, growing up']}),
        ('Seedcount', 'Int', 8, {'min': 1, 'max': 64, 'clampmin': 1, 'label': 'Seed tips'}),
        ('Maxtips', 'Int', 256, {'min': 16, 'max': 4096, 'clampmin': 1, 'clampmax': 4096, 'label': 'Max tips'}),
        ('Step', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Step px / frame'}),
        ('Sensorangle', 'Float', 30.0, {'min': 0, 'max': 90, 'label': 'Sensor angle deg'}),
        ('Sensordist', 'Float', 6.0, {'min': 1, 'max': 30, 'label': 'Sensor distance px'}),
        ('Turn', 'Float', 20.0, {'min': 0, 'max': 90, 'label': 'Turn deg'}),
        ('Wander', 'Float', 10.0, {'min': 0, 'max': 90, 'label': 'Wander deg'}),
        ('Killthresh', 'Float', 2.0, {'min': 0.05, 'max': 20, 'label': 'Die when trail ahead >'}),
        ('Splitrate', 'Float', 0.02, {'min': 0, 'max': 0.5, 'label': 'Split chance / frame'}),
        ('Splitangle', 'Float', 25.0, {'min': 0, 'max': 90, 'label': 'Split angle deg'}),
        ('Maxage', 'Int', 600, {'min': 10, 'max': 5000, 'clampmin': 1, 'label': 'Max age (frames)'}),
        ('Deposit', 'Float', 1.0, {'min': 0, 'max': 5, 'label': 'Deposit'}),
        ('Decay', 'Float', 0.995, {'min': 0.9, 'max': 1, 'label': 'Trail decay / frame'}),
        ('Diffuse', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Trail diffuse (wrap 3x3)'}),
        ('Simw', 'Int', 540, {'min': 64, 'max': 1080, 'clampmin': 16, 'clampmax': 2160, 'label': 'Sim width'}),
        ('Simh', 'Int', 960, {'min': 64, 'max': 1920, 'clampmin': 16, 'clampmax': 3840, 'label': 'Sim height'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 1000, 'label': 'Seed'}),
        ('Resetat', 'Int', -10, {'min': -10, 'max': 10, 'label': 'Reset frame (internal, set by Reset)'}),
    ]),
    ('Look', [
        ('Huea', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Hue (young)'}),
        ('Hueb', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Hue (old)'}),
        ('Sat', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Saturation'}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Gain'}),
    ]),
    OUT_PAGE,
]
PANEL_PAGES = ['Branching', 'Look']
FIRST = {'Maxtips': 256, 'Seedcount': 8, 'Simw': 270, 'Simh': 480, 'Resw': 540, 'Resh': 960}

RESET_E = "1.0 if absTime.frame - parent().par.Resetat.eval() <= 1 else 0.0"
SIM_U = [
    ('uT', (PP.format('Step'), "math.radians(parent().par.Sensorangle.eval())", PP.format('Sensordist'),
            "math.radians(parent().par.Turn.eval())")),
    ('uU', ("math.radians(parent().par.Wander.eval())", PP.format('Killthresh'), PP.format('Splitrate'),
            "math.radians(parent().par.Splitangle.eval())")),
    ('uS', ("float(parent().par.Simw.eval())", "float(parent().par.Simh.eval())",
            "float(parent().par.Maxage.eval())", "float(parent().par.Seed.eval())")),
    ('uR', (RESET_E, "1.0 if parent().par.Play.eval() else 0.0", "float(parent().par.Maxtips.eval())",
            "float(parent().par.Seedmode.menuIndex) * 1000.0 + float(parent().par.Seedcount.eval())")),
]
DEP_U = [('uV', ("float(parent().par.Simw.eval())", "float(parent().par.Simh.eval())", PP.format('Deposit'),
                 "float(parent().par.Maxage.eval())"))]
TRAIL_U = [('uK', (PP.format('Decay'), PP.format('Diffuse'), RESET_E, "0.0"))]
LOOK_U = [('uL', (PP.format('Huea'), PP.format('Hueb'), PP.format('Sat'), PP.format('Gain')))]

HEAD = """
#define TW 64
#define TROWS 64
#define MAXT 4096
const float TAU = 6.283185307179586;
uniform vec4 uT;   // step, sensor angle (rad), sensor dist, turn (rad)
uniform vec4 uU;   // wander (rad), kill thresh, split rate, split angle (rad)
uniform vec4 uS;   // sim w, sim h, max age, seed
uniform vec4 uR;   // reset, play, max tips, seedmode * 1000 + seedcount
ivec2 tx(int i) { return ivec2(i % TW, i / TW); }
vec4 tip(int i) { return texelFetch(sTD2DInputs[0], tx(i), 0); }
int max_tips() { return clamp(int(uR.z + 0.5), 1, MAXT); }
"""

TIPS = """// POP_branching tips (TC-10): seed, or sense -> steer away from trail -> wander -> move -> die / split flag.
// w out: -1 dead, else age + 1 (+ 0.25 = split). Mirror: pop_branching_logic.tips + seed_tips.
layout(local_size_x = 8, local_size_y = 8) in;
""" + HEAD + """
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hh(uint i, uint s) { return float(lowbias(i * 747796405u + s * 2891336453u + 1u) >> 8) / 16777216.0; }
float sense(vec2 q)
{
    ivec2 k = ivec2(floor(q));
    if (k.x < 0 || k.y < 0 || k.x >= int(uS.x + 0.5) || k.y >= int(uS.y + 0.5)) return 1e9;
    return texelFetch(sTD2DInputs[1], k, 0).r;
}
vec2 dir(float h) { return vec2(cos(h), sin(h)); }
void main()
{
    ivec2 g = ivec2(gl_GlobalInvocationID.xy);
    if (g.x >= TW || g.y > TROWS) return;
    int i = g.y * TW + g.x;
    vec4 ct = texelFetch(sTD2DInputs[0], ivec2(0, TROWS), 0);
    int cnt = int(ct.x + 0.5);
    int frame = int(ct.y + 0.5);
    bool seeding = uR.x > 0.5 || cnt <= 0;
    int mode = int(uR.w / 1000.0);
    int nseed = clamp(int(uR.w + 0.5) - mode * 1000, 1, max_tips());
    vec4 o = vec4(0.0);
    if (g.y == TROWS) {
        if (g.x == 0) o = vec4(float(seeding ? nseed : cnt), float(frame + 1), 0.0, 0.0);
        TDImageStoreOutput(0, ivec3(g, 0), o);
        return;
    }
    if (seeding) {
        float fi = float(i), n = float(nseed);
        if (i < nseed) o = mode == 0 ? vec4(uS.x * 0.5, uS.y * 0.5, TAU * fi / n, 0.0)
                                     : vec4(uS.x * (fi + 0.5) / n, 2.0, 1.5707963267948966, 0.0);
    } else if (i < cnt) {
        o = tip(i);
        if (uR.y > 0.5) {
            vec2 p = o.xy;
            float h = o.z, age = o.w;
            float F = sense(p + uT.z * dir(h));
            float Lf = sense(p + uT.z * dir(h + uT.y));
            float Rf = sense(p + uT.z * dir(h - uT.y));
            if (!(F <= Lf && F <= Rf)) h = Lf < Rf ? h + uT.w : h - uT.w;
            uint salt = uint(int(uS.w + 0.5)) * 65537u + uint(frame) * 4u;
            h += uU.x * (hh(uint(i), salt) - 0.5) * 2.0;
            p += uT.x * dir(h);
            bool outb = p.x < 0.0 || p.x >= uS.x || p.y < 0.0 || p.y >= uS.y;
            bool dead = F > uU.y || outb || age + 1.0 > uS.z;
            float pr = uU.z * (1.0 - clamp(sense(p) / uU.y, 0.0, 1.0));
            bool split = !dead && hh(uint(i), salt + 1u) < pr;
            o = vec4(p, h, dead ? -1.0 : age + 1.0 + (split ? 0.25 : 0.0));
        }
    }
    TDImageStoreOutput(0, ivec3(g, 0), o);
}
"""

ALLOC = """// POP_branching alloc (TC-10): ONE workgroup (dispatch 1 x 1 x 1). Survivors densely in order (parent heading
// + split angle), then children (heading - split angle, age 0), all capped at Maxtips. Mirror: logic.alloc.
layout(local_size_x = 1024) in;
#define CHUNK 4
""" + HEAD + SCAN_GLSL + """
void put(int i, vec4 v) { TDImageStoreOutput(0, ivec3(tx(i), 0), v); }
void main()
{
    uint tid = gl_LocalInvocationID.x;
    vec4 ct = texelFetch(sTD2DInputs[0], ivec2(0, TROWS), 0);
    int cnt = int(ct.x + 0.5);
    int mx = max_tips();
    int base = int(tid) * CHUNK;
    uint ls = 0u, lc = 0u;
    for (int k = 0; k < CHUNK; k++) {
        int i = base + k;
        if (i < cnt) {
            float w = tip(i).w;
            if (w >= 0.0) { ls += 1u; if (fract(w) > 0.1) lc += 1u; }
        }
    }
    uint S, C;
    uint rs = scan_excl(ls, tid, S);
    uint rc = scan_excl(lc, tid, C);
    for (int k = 0; k < CHUNK; k++) {
        int i = base + k;
        if (i >= cnt) break;
        vec4 t = tip(i);
        if (t.w < 0.0) continue;
        bool split = fract(t.w) > 0.1;
        if (int(rs) < mx) put(int(rs), vec4(t.xy, t.z + (split ? uU.w : 0.0), floor(t.w)));
        rs += 1u;
        if (split) {
            int d = int(S + rc);
            if (d < mx) put(d, vec4(t.xy, t.z - uU.w, 0.0));
            rc += 1u;
        }
    }
    if (tid == 0u) TDImageStoreOutput(0, ivec3(0, TROWS, 0), vec4(float(min(int(S + C), mx)), ct.y, 0.0, 0.0));
}
"""

TRAIL = """// POP_branching trail: t = mix(trail, wrap 3x3 mean, diffuse) x decay + deposit (sum-preserving mix); Reset
// clears. Mirror: logic.trail_step. Perf 27 Oct (b3 wave 3): the deposit is gathered here (was a Render TOP of 1-px
// points, one per live tip at its texel centre): each 16 x 16 tile loads the tips in batches of 256 into shared memory
// (kept when their texel falls in the tile), every texel sums its own tips: r = Deposit, g = Deposit x age, b = 0,
// a = Deposit (exact in 32F like the additive render). Diffuse 0 skips the 3 x 3 mean (same value: x 0 adds 0).
layout(local_size_x = 16, local_size_y = 16) in;
#define TW 64
#define TROWS 64
#define MAXT 4096
#define NB 256
uniform vec4 uK;   // decay, diffuse, reset, -
uniform vec4 uV;   // sim w, sim h, deposit, max age
shared ivec2 sT[NB];
shared float sG[NB];
shared int sN;
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    int lt = int(gl_LocalInvocationIndex);
    ivec2 t0 = ivec2(gl_WorkGroupID.xy) * 16;
    int cnt = clamp(int(texelFetch(sTD2DInputs[1], ivec2(0, TROWS), 0).x + 0.5), 0, MAXT);
    vec4 dep = vec4(0.0);
    for (int b0 = 0; b0 < MAXT; b0 += NB) {
        if (b0 >= cnt) break;                                 // uniform: cnt is the same for every thread
        if (lt == 0) sN = 0;
        barrier();
        int i = b0 + lt;
        if (i < cnt) {
            vec4 s = texelFetch(sTD2DInputs[1], ivec2(i % TW, i / TW), 0);
            ivec2 k = ivec2(floor(s.xy));
            ivec2 d = k - t0;
            if (d.x >= 0 && d.y >= 0 && d.x < 16 && d.y < 16 && k.x < R.x && k.y < R.y) {
                int n = atomicAdd(sN, 1);
                sT[n] = k;
                sG[n] = clamp(s.w / max(uV.w, 1.0), 0.0, 1.0);
            }
        }
        barrier();
        int n = sN;
        for (int j = 0; j < NB; j++) {
            if (j >= n) break;
            if (sT[j] == p) dep += vec4(uV.z, uV.z * sG[j], 0.0, uV.z);
        }
        barrier();
    }
    if (p.x >= R.x || p.y >= R.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    vec4 t;
    if (uK.z > 0.5) t = vec4(0.0);
    else if (uK.y == 0.0) t = c * uK.x;
    else {
        vec4 m = vec4(0.0);
        for (int dy = -1; dy <= 1; dy++)
            for (int dx = -1; dx <= 1; dx++)
                m += texelFetch(sTD2DInputs[0], (p + ivec2(dx, dy) + R) % R, 0);
        t = (c + (m / 9.0 - c) * uK.y) * uK.x;
    }
    TDImageStoreOutput(0, ivec3(p, 0), t + dep);
}
"""

LOOK = """// POP_branching look: hue by age (g / r), tone 1 - exp(-gain r), premultiplied over in1.
layout(local_size_x = 8, local_size_y = 8) in;
uniform vec4 uL;   // hue young, hue old, sat, gain
vec3 hsv(float h, float s) { vec3 k = clamp(abs(fract(h + vec3(0.0, 2.0, 1.0) / 3.0) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return mix(vec3(1.0), k, s); }
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= int(uTDOutputInfo.res.z) || p.y >= int(uTDOutputInfo.res.w)) return;
    vec2 uv = (vec2(p) + 0.5) * uTDOutputInfo.res.xy;
    vec4 t = texture(sTD2DInputs[0], uv);
    vec4 b = texture(sTD2DInputs[1], uv);
    float a = 1.0 - exp(-max(t.r, 0.0) * uL.w);
    float ag = t.r > 1e-6 ? clamp(t.g / t.r, 0.0, 1.0) : 0.0;
    vec3 c = hsv(mix(uL.x, uL.y, ag), uL.z) * a;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(c + b.rgb * (1.0 - a), a + b.a * (1.0 - a)));
}
"""

PULSES = """# POP_branching pulses: Reset stamps the frame; tips reseed and trail clears while absTime.frame - Resetat <= 1.
def onPulse(par):
    if par.name == 'Reset':
        par.owner.par.Resetat = absTime.frame
    return
"""

SIMW = "parent().par.Simw.eval()"
SIMH = "parent().par.Simh.eval()"


def shader_texts():
    return {'tips': TIPS, 'alloc': ALLOC, 'trail': TRAIL, 'look': LOOK}


def build(parent_path='/project1/lab', panel=True, first=False):
    del NOTES[:]
    c = _comp(parent_path, NAME, 'POP_branching (TC-10): growth tips steer away from their own trail, die in dense '
                                 'trail, split where it is thin. Tips state 64 x 65 (count at texel 0,64), trail at '
                                 'Simw x Simh. Pulse Reset. Amount 0 = in1 untouched. Out: out1.')
    was_open = _close_window(c)
    _pars(c, PAGES)
    if first:
        _apply_first(c, FIRST)
    in1 = _mk(c, inTOP, 'in1')
    in1.comment = 'Background (premultiplied).'
    pe = _mk(c, parameterexecuteDAT, 'br_pulses')
    if pe.text != PULSES:
        pe.text = PULSES
    pe.par.op = c
    pe.par.pars = 'Reset'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = False
    pe.par.onpulse = True
    sb = _blank(c, 'state_blank', str(TW), str(TROWS + 1))
    sb.comment = 'Zero state: count 0 -> tips seed on the first frame.'
    tb = _blank(c, 'trail_blank', SIMW, SIMH)
    tb.comment = 'Zero trail (sim res).'
    sfb = _mk(c, feedbackTOP, 'state_fb')
    _wire(sb, sfb)
    tfb = _mk(c, feedbackTOP, 'trail_fb')
    _wire(tb, tfb)
    tp = _compute(c, 'tips', TIPS, [sfb, tfb], str(TW), str(TROWS + 1), spec=SIM_U)
    tp.comment = 'One thread per tip: seed, or sense / steer / wander / move / die / split flag.'
    al = _compute(c, 'alloc', ALLOC, [tp], str(TW), str(TROWS + 1), spec=SIM_U)
    al.par.autodispatchsize = False
    _try(al, 'dispatchsizex', 1)
    _try(al, 'dispatchsizey', 1)
    _try(al, 'dispatchsizez', 1)
    al.comment = 'ONE workgroup of 1024: two prefix scans (pop_scan): survivors then children, capped at Maxtips.'
    sfb.par.top = 'alloc'
    for n in ('deposit', 'dep_geo', 'dep_cam', 'dep_mat', 'dep_mat_vertex', 'dep_mat_pixel', 'pts'):
        _sd(c.op(n))                                # the pre-27-Oct deposit Render TOP path (now gathered in trail)
    tr = _compute(c, 'trail', TRAIL, [tfb, al], SIMW, SIMH, spec=TRAIL_U + DEP_U)
    tr.comment = 'trail x decay (+ wrap diffuse) + deposit gathered from alloc (one per live tip); Reset clears.'
    tfb.par.top = 'trail'
    lk = _compute(c, 'look', LOOK, [tr, in1], RESW, RESH, fmt='rgba16float', spec=LOOK_U, filt='linear')
    lk.comment = 'Hue by age, tone by density, premultiplied over in1.'
    _out_switch(c, in1, lk)
    stages = [
        {'title': '1 In + controls', 'role': 'input', 'ops': ['in1', 'br_pulses'], 'body': 'in1 background; Reset.'},
        {'title': '2 Tips loop', 'role': 'feedback', 'ops': ['state_blank', 'state_fb', 'tips', 'tips_compute',
                                                             'alloc', 'alloc_compute'],
         'body': 'state_fb -> tips (per tip) -> alloc (one workgroup, 2 scans) -> state_fb.'},
        {'title': '3 Trail loop', 'role': 'feedback', 'ops': ['trail_blank', 'trail_fb', 'trail', 'trail_compute'],
         'body': 'trail_fb -> trail (+ deposit gathered from alloc) -> trail_fb; tips sense trail_fb.'},
        {'title': '4 Look + out', 'role': 'output', 'ops': ['look', 'look_compute', 'out_sel', 'out1'],
         'body': 'Amount 0 = in1 untouched.'},
    ]
    return _finish(c, stages, PANEL_PAGES, was_open, panel)
