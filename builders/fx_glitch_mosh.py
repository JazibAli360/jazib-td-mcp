# fx_glitch_mosh - FX_glitch module 'mosh' (FX1 DG-01 live datamosh engine; probes FX6 3a).
# The picture's motion is estimated per 8x8 block by a shared-memory SAD block match (one workgroup per block, at
# half res by default = 16x16 macroblocks at full res), and a decoded state S keeps the OLD picture's texture and
# moves it by the NEW motion (P-frames without I-frames). Refresh = the I-frame (manual / beat / random / period),
# Bloom = the motion field latched and applied again every frame (P-frame repeat). Source can be the live input, an
# offline tools/mosh.py clip, or a blend. Template: docs/builds/fx_glitch.md; doc: docs/builds/fx_glitch.md (Module mosh / moshcut).
# The engine (lum / mv / cprev / sfb / upd shaders + engine()) is shared with fx_glitch_moshcut.py (DG-02), its only
# other user. Compute GLSL everywhere (T-47); Amount 0 = exact passthrough (out_sel picks in1, nothing else cooks).
# ASCII only.

MODULE = 'mosh'
MODES = ['mosh', 'bloom', 'hit']
EST = ['full', 'half', 'quarter']
VIEWS = ['mosh', 'vectors', 'sad']

PAGES = [
    ('Mosh', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'mosh', {'names': MODES, 'labels': ['Mosh (drag)', 'Bloom (latched MVs)',
                                                             'Hit (bloom, then I-frame)']}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Gain (MV x)'}),
        ('Bloomgain', 'Float', 1.5, {'min': 0, 'max': 8, 'label': 'Bloom gain'}),
        ('Minmag', 'Float', 0.5, {'min': 0, 'max': 8, 'label': 'Min motion px'}),
        ('Residual', 'Float', 0.3, {'min': 0, 'max': 1.5, 'label': 'Residual'}),
        ('Decay', 'Float', 0.0, {'min': 0, 'max': 0.2, 'label': 'Decay (leak to live)'}),
        ('Blockwarp', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Block warp (0 hard, 1 fluid)'}),
        ('Subpel', 'Toggle', False, {'label': 'Sub-pixel'}),
        ('View', 'Menu', 'mosh', {'names': VIEWS, 'labels': ['Mosh', 'Motion vectors', 'Match error']}),
    ]),
    ('Refresh', [
        ('Refresh', 'Pulse', None, {'label': 'Refresh (I-frame)'}),
        ('Holdauto', 'Toggle', False, {'label': 'Hold (no auto refresh)'}),
        ('Randomrate', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Random I-frames /s'}),
        ('Period', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Every N s (0 off)'}),
        ('Beatevery', 'Int', 0, {'min': 0, 'max': 16, 'label': 'Every N beats (0 off)'}),
        ('Holdtime', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Hit bloom s'}),
        ('Blockrefresh', 'Float', 0.0, {'min': 0, 'max': 0.2, 'label': 'Block refresh /frame'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Estimator', [
        ('Estres', 'Menu', 'half', {'names': EST, 'labels': ['Full (8 px blocks)', 'Half (16 px)', 'Quarter (32 px)']}),
        ('Range', 'Int', 8, {'min': 1, 'max': 16, 'label': 'Search +- px'}),
        ('Penalty', 'Float', 0.01, {'min': 0, 'max': 0.2, 'label': 'MV length penalty'}),
    ]),
    ('Source', [
        ('Source', 'Menu', 'live', {'names': ['live', 'clip', 'blend'], 'labels': ['Live (in1)', 'Mosh clip',
                                                                                   'Blend live + clip']}),
        ('Clipblend', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Clip blend'}),
        ('Clipfile', 'Str', '', {'label': 'Mosh clip (tools/mosh.py)'}),
        ('Beatchop', 'Str', '', {'label': 'Beat CHOP path'}),
        ('Beatchan', 'Str', 'beat', {'label': 'Beat channel'}),
        ('Refreshcount', 'Int', 0, {'min': 0, 'max': 100, 'label': 'Refresh count (internal)'}),
    ]),
]
PANEL_PAGES = ['Mosh', 'Refresh', 'Estimator']
CLIP = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/demo/mosh/webcam_bloom_mid_540.mov'

PRESETS = [
    (1, 'drag', {'Amount': 1.0, 'Mode': 0, 'Gain': 1.0, 'Residual': 0.3, 'Decay': 0.0, 'Blockwarp': 0.0,
                 'Subpel': 0, 'Randomrate': 0.3, 'Period': 0.0, 'Blockrefresh': 0.0, 'Estres': 1, 'Range': 8}),
    (2, 'melt', {'Amount': 1.0, 'Mode': 0, 'Gain': 1.0, 'Residual': 0.0, 'Decay': 0.01, 'Blockwarp': 1.0,
                 'Subpel': 1, 'Randomrate': 0.0, 'Period': 4.0, 'Blockrefresh': 0.0, 'Estres': 1, 'Range': 8}),
    (3, 'bloom', {'Amount': 1.0, 'Mode': 1, 'Bloomgain': 2.0, 'Residual': 0.2, 'Blockwarp': 0.0, 'Subpel': 0,
                  'Randomrate': 0.0, 'Period': 2.0, 'Estres': 1, 'Range': 8}),
    (4, 'hit', {'Amount': 1.0, 'Mode': 2, 'Bloomgain': 3.0, 'Holdtime': 0.6, 'Residual': 0.3, 'Randomrate': 1.0,
                'Period': 0.0, 'Estres': 1, 'Range': 8}),
    (5, 'blocks', {'Amount': 1.0, 'Mode': 0, 'Gain': 1.0, 'Residual': 0.6, 'Blockwarp': 0.0, 'Subpel': 0,
                   'Blockrefresh': 0.02, 'Randomrate': 0.0, 'Period': 0.0, 'Estres': 2, 'Range': 12}),
]

# ------------------------------------------------------------------ shaders (shared with moshcut)
LUM = """// lum (compute, est res, rgba16float in place): r = this frame's luma, g = the previous cook's luma.
// in0 = picture (full res); 4 bilinear taps = an exact 2x2 box at half res, 4x4 at quarter.
// b = frame stamp (absTime.frame % 2048, exact in 16F): a second cook in the same frame keeps g (no zero motion).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS;   // est w, est h, frame stamp
void main() {
    ivec2 q = ivec2(gl_GlobalInvocationID.xy);
    if (q.x >= int(uS.x) || q.y >= int(uS.y)) return;
    vec2 uv = (vec2(q) + 0.5) / uS.xy;
    vec2 d = 0.25 / uS.xy;
    vec3 c = texture(sTD2DInputs[0], uv + vec2(-d.x, -d.y)).rgb + texture(sTD2DInputs[0], uv + vec2(d.x, -d.y)).rgb
           + texture(sTD2DInputs[0], uv + vec2(-d.x, d.y)).rgb + texture(sTD2DInputs[0], uv + vec2(d.x, d.y)).rgb;
    float l = dot(c * 0.25, vec3(0.2126, 0.7152, 0.0722));
    vec4 o = TDImageLoadOutput(0, ivec3(q, 0));
    float prev = (o.b == uS.z) ? o.g : o.r;
    TDImageStoreOutput(0, ivec3(q, 0), vec4(l, prev, uS.z, 1.0));
}
"""

MV = """// mv (compute, one texel per 8x8 block, rgba32float in place): xy = source offset o (cur(p) ~ prev(p + o), est px),
// z = best SAD / 64, w = zero-motion SAD / 64. One workgroup per block (FX6 3a): block + (8+2R)^2 window in shared
// memory, 64 threads share the (2R+1)^2 candidates, min-reduction. Latch (stamp w) keeps the old field = bloom.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uE;   // range R (<= 16), length penalty
shared float wnd[1600];
shared float blk[64];
shared float bs[64];
shared int bi[64];
void main() {
    ivec2 b = ivec2(gl_WorkGroupID.xy);
    ivec2 t = ivec2(gl_LocalInvocationID.xy);
    int tid = t.y * 8 + t.x;
    ivec2 msz = textureSize(sTD2DInputs[0], 0);
    ivec2 osz = ivec2(gl_NumWorkGroups.xy);
    int R = clamp(int(uE.x + 0.5), 0, 16);
    int WS = 8 + 2 * R;
    int NW = WS * WS;
    ivec2 org = b * 8 - ivec2(R);
    for (int i = tid; i < NW; i += 64) {
        ivec2 q = clamp(org + ivec2(i % WS, i / WS), ivec2(0), msz - 1);
        wnd[i] = texelFetch(sTD2DInputs[0], q, 0).g;                      // previous luma
    }
    blk[tid] = texelFetch(sTD2DInputs[0], clamp(b * 8 + t, ivec2(0), msz - 1), 0).r;   // current luma
    barrier();
    int D = 2 * R + 1;
    int NC = D * D;
    float best = 1e30;
    int bidx = R * D + R;
    for (int c = tid; c < NC; c += 64) {
        int dx = c % D;
        int dy = c / D;
        float s = 0.0;
        for (int k = 0; k < 64; k++) {
            s += abs(blk[k] - wnd[(dy + (k >> 3)) * WS + dx + (k & 7)]);
        }
        s += uE.y * float(abs(dx - R) + abs(dy - R));
        if (s < best) { best = s; bidx = c; }
    }
    bs[tid] = best;
    bi[tid] = bidx;
    barrier();
    for (int st = 32; st > 0; st >>= 1) {
        if (tid < st) {
            if (bs[tid + st] < bs[tid] || (bs[tid + st] == bs[tid] && bi[tid + st] < bi[tid])) {
                bs[tid] = bs[tid + st];
                bi[tid] = bi[tid + st];
            }
        }
        barrier();
    }
    if (tid == 0 && b.x < osz.x && b.y < osz.y) {
        vec4 lat = texelFetch(sTD2DInputs[1], ivec2(0), 0);
        if (lat.w > 0.5) return;                                                // latched: keep the old field
        int c = bi[0];
        vec2 o = vec2(float(c % D - R), float(c / D - R));
        float z = 0.0;
        for (int k = 0; k < 64; k++) z += abs(blk[k] - wnd[(R + (k >> 3)) * WS + R + (k & 7)]);
        TDImageStoreOutput(0, ivec3(b, 0), vec4(o, bs[0] / 64.0, z / 64.0));
    }
}
"""

UPD = """// upd (compute, full res, rgba16float; its Feedback = sfb): the decoded state S.
// in0 cur, in1 S prev (sfb), in2 mv, in3 cur prev (cprev), in4 stamp, in5 init picture, in6 lum.
// stamp texel0: z = global refresh (I-frame to cur), w = latched (bloom gain); texel1 w = init (S = in5).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // gain, bloomgain, minmag px, residual
uniform vec4 uB;   // decay, blockwarp, subpel, est scale
uniform vec4 uC;   // block refresh threshold, order (0 noise 1 top-down 2 bottom-up 3 radial 4 luma), animate, seed
uniform vec4 uD;   // centre x, centre y, frame
float h2(vec2 v) { return fract(sin(dot(v, vec2(12.9898, 78.233)) + uC.w * 3.17) * 43758.5453); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 cur = texelFetch(sTD2DInputs[0], p, 0);
    vec4 s0 = texelFetch(sTD2DInputs[4], ivec2(0, 0), 0);
    vec4 s1 = texelFetch(sTD2DInputs[4], ivec2(1, 0), 0);
    if (s1.w > 0.5) { TDImageStoreOutput(0, ivec3(p, 0), texelFetch(sTD2DInputs[5], p, 0)); return; }
    if (s0.z > 0.5) { TDImageStoreOutput(0, ivec3(p, 0), cur); return; }
    float bsz = 8.0 * uB.w;
    ivec2 msz = textureSize(sTD2DInputs[2], 0);
    ivec2 blk = clamp(ivec2(floor(vec2(p) / bsz)), ivec2(0), msz - 1);
    int ord = int(uC.y + 0.5);
    vec2 bc = (vec2(blk) + 0.5) / vec2(msz);
    float rank;
    if (ord == 1) rank = bc.y;
    else if (ord == 2) rank = 1.0 - bc.y;
    else if (ord == 3) rank = length((bc - uD.xy) * vec2(float(isz.x) / float(isz.y), 1.0)) / 1.2;
    else if (ord == 4) rank = 1.0 - texelFetch(sTD2DInputs[6], clamp(ivec2(bc * vec2(textureSize(sTD2DInputs[6], 0))),
                                    ivec2(0), textureSize(sTD2DInputs[6], 0) - 1), 0).r;
    else rank = h2(vec2(blk) + vec2(uC.z * uD.z, 0.37 * uC.z * uD.z));
    if (rank < uC.x) { TDImageStoreOutput(0, ivec3(p, 0), cur); return; }     // block intra refresh
    vec2 mh = texelFetch(sTD2DInputs[2], blk, 0).xy;
    vec2 g = (vec2(p) + 0.5) / bsz - 0.5;
    ivec2 g0 = ivec2(floor(g));
    vec2 f = g - vec2(g0);
    vec2 m00 = texelFetch(sTD2DInputs[2], clamp(g0, ivec2(0), msz - 1), 0).xy;
    vec2 m10 = texelFetch(sTD2DInputs[2], clamp(g0 + ivec2(1, 0), ivec2(0), msz - 1), 0).xy;
    vec2 m01 = texelFetch(sTD2DInputs[2], clamp(g0 + ivec2(0, 1), ivec2(0), msz - 1), 0).xy;
    vec2 m11 = texelFetch(sTD2DInputs[2], clamp(g0 + ivec2(1, 1), ivec2(0), msz - 1), 0).xy;
    vec2 ms = mix(mix(m00, m10, f.x), mix(m01, m11, f.x), f.y);
    vec2 m = mix(mh, ms, uB.y) * uB.w * ((s0.w > 0.5) ? uA.y : uA.x);
    if (length(m) < uA.z) m = vec2(0.0);
    if (uB.z < 0.5) m = floor(m + 0.5);
    vec2 uv = (vec2(p) + 0.5 + m) / vec2(isz);
    vec4 ref = texture(sTD2DInputs[1], uv);
    vec4 cp = texture(sTD2DInputs[3], uv);
    vec4 o = ref + uA.w * (cur - cp);
    o = mix(o, cur, uB.x);
    TDImageStoreOutput(0, ivec3(p, 0), clamp(o, 0.0, 1.0));
}
"""

FX = """// fx (compute, in1 res, format useinput): out = mix(dry, S, amount); views for checking the motion field.
// in0 = dry picture (in1), in1 = S (upd), in2 = mv.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uF;   // amount, view (0 mosh 1 vectors 2 sad), est scale, vector scale px
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 a = texelFetch(sTD2DInputs[0], p, 0);
    if (uF.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), a); return; }       // exact passthrough
    vec4 s = texelFetch(sTD2DInputs[1], p, 0);
    int view = int(uF.y + 0.5);
    if (view > 0) {
        ivec2 msz = textureSize(sTD2DInputs[2], 0);
        vec4 mv = texelFetch(sTD2DInputs[2], clamp(ivec2(vec2(p) / (8.0 * uF.z)), ivec2(0), msz - 1), 0);
        if (view == 1) s = vec4(0.5 + 0.5 * clamp(mv.xy / uF.w, -1.0, 1.0), 0.5, 1.0);
        else s = vec4(vec3(clamp(mv.z * 8.0, 0.0, 1.0)), 1.0);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(a, s, uF.x));
}
"""

STAMP = """// stamp (3x1 rgba32float in place, one invocation): the module's clock + I-frame triggers.
// texel0 = (now, previous cook's now, refresh, latch); texel1 = (refresh count, -, beat value, init);
// texel2 = (beat count, last trigger time, frames since init, -). A gap > 0.25 s since the last cook = init.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;   // now, refresh count, beat value, beat every (0 off)
uniform vec4 uM;   // mode (0 mosh 1 bloom 2 hit), hit hold s, random rate /s, period s (0 off)
uniform vec4 uH;   // hold auto, seed
void main() {
    if (gl_GlobalInvocationID.x != 0u || gl_GlobalInvocationID.y != 0u) return;
    vec4 a = TDImageLoadOutput(0, ivec3(0, 0, 0));
    vec4 b = TDImageLoadOutput(0, ivec3(1, 0, 0));
    vec4 c = TDImageLoadOutput(0, ivec3(2, 0, 0));
    float now = uT.x;
    if (a.x == now) return;                     // a second cook in the same frame (readback, force cook): keep
    float pn = a.x;
    bool fresh = (now - pn) > 0.25 || pn <= 0.0;
    bool man = abs(uT.y - b.x) > 0.5;
    bool edge = uT.w > 0.5 && uT.z > 0.5 && b.z <= 0.5;
    float bc = c.x + (edge ? 1.0 : 0.0);
    bool bt = edge && mod(bc, max(floor(uT.w + 0.5), 1.0)) < 0.5;
    float dt = max(now - pn, 0.0);
    float hh = fract(sin(now * 91.345 + uH.y * 12.9898) * 43758.5453);
    bool rnd = uM.z > 0.0 && hh < uM.z * dt;
    bool per = uM.w > 0.0 && floor(now / uM.w) != floor(pn / uM.w);
    bool trig = man || ((bt || rnd || per) && uH.x < 0.5);
    float last = c.y;
    float since = fresh ? 0.0 : c.z + 1.0;
    int mode = int(uM.x + 0.5);
    float refresh = 0.0;
    float latch = 0.0;
    if (fresh) { refresh = 1.0; last = -1e6; }
    else if (mode == 0) { refresh = trig ? 1.0 : 0.0; }
    else if (mode == 1) { refresh = trig ? 1.0 : 0.0; latch = (trig || since < 2.0) ? 0.0 : 1.0; }
    else {
        if (trig) { last = now; }
        else {
            float e = now - last;
            float ep = pn - last;
            latch = (e < uM.y && since >= 2.0) ? 1.0 : 0.0;
            refresh = (ep < uM.y && e >= uM.y) ? 1.0 : 0.0;
        }
    }
    TDImageStoreOutput(0, ivec3(0, 0, 0), vec4(now, pn, refresh, latch));
    TDImageStoreOutput(0, ivec3(1, 0, 0), vec4(uT.y, 0.0, uT.z, fresh ? 1.0 : 0.0));
    TDImageStoreOutput(0, ivec3(2, 0, 0), vec4(bc, last, since, 0.0));
}
"""

P = "parent().par.{}.eval()"
SCALE = "[1, 2, 4][parent().par.Estres.menuIndex]"


def _glsl(m, H, name, text, res=None, fmt='rgba16float', inplace=False, inputs=(), tops='', uniforms=(),
          dispatch=None, extend=None):
    """One compute GLSL TOP with its docked shader DAT. res = (w expr, h expr); dispatch = (x expr, y expr)."""
    mk, expr = H['mk'], H['expr']
    g = mk(m, glslTOP, name)
    d = m.op(name + '_compute')
    if d is None:
        d = mk(m, textDAT, name + '_compute')
        d.dock = g
    d.text = text
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    expr(g.par.resolutionw, res[0])
    expr(g.par.resolutionh, res[1])
    g.par.format = fmt
    if inplace:
        g.par.outputaccess = 'readwrite'
        g.par.clearoutputs = False
    if dispatch:
        g.par.autodispatchsize = False
        expr(g.par.dispatchsizex, dispatch[0])
        expr(g.par.dispatchsizey, dispatch[1])
        g.par.dispatchsizez = 1
    if extend:
        g.par.inputextenduv = extend
    for i, src in enumerate(inputs):
        g.inputConnectors[i].connect(src)
    g.par.tops = tops
    g.seq.vec.numBlocks = max(len(uniforms), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(uniforms):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)
    return g


def engine(m, H, cur, ini, stamp_text, stamp_uniforms, upd_uniforms):
    """Estimator + decoded state on picture `cur` (an op in m), S initialised from `ini`. Returns upd, mv, ops."""
    mk = H['mk']
    st = _glsl(m, H, 'stamp', stamp_text, res=('3', '1'), fmt='rgba32float', inplace=True, uniforms=stamp_uniforms)
    st.comment = 'Clock + I-frame triggers: refresh / latch / init flags for mv and upd (cooks only when they do).'
    lum = _glsl(m, H, 'lum', LUM, res=("max(8, int(op('in1').width / %s))" % SCALE,
                                       "max(8, int(op('in1').height / %s))" % SCALE),
                inplace=True, inputs=[cur], uniforms=[('uS', ["me.par.resolutionw.eval()", "me.par.resolutionh.eval()", 'absTime.frame % 2048',
                                 '0'])])
    lum.comment = 'Luma at the estimator res (Estres): r = now, g = previous cook (in place, no Feedback TOP).'
    mv = _glsl(m, H, 'mv', MV, res=("max(1, int(math.ceil(op('lum').width / 8.0)))",
                                    "max(1, int(math.ceil(op('lum').height / 8.0)))"),
               fmt='rgba32float', inplace=True, inputs=[lum, st],
               dispatch=("me.par.resolutionw.eval()", "me.par.resolutionh.eval()"),
               uniforms=[('uE', [P.format('Range'), P.format('Penalty'), '0', '0'])])
    mv.comment = 'Block match 8x8 SAD +-Range, one workgroup per block (shared memory, FX6 3a). Latch = bloom.'
    cp = mk(m, cacheTOP, 'cprev')
    cp.inputConnectors[0].connect(cur)
    cp.par.cachesize = 2
    cp.par.outputindex = -1
    cp.comment = 'Previous cooked picture (residual = cur - cprev(p + o)).'
    fb = mk(m, feedbackTOP, 'sfb')
    fb.inputConnectors[0].connect(cur)
    fb.par.top = 'upd'
    fb.comment = 'Decoded state S of the previous cook (upd).'
    upd = _glsl(m, H, 'upd', UPD, res=("op('in1').width", "op('in1').height"), inputs=[cur, fb, mv],
                tops='cprev stamp %s lum' % ini, uniforms=upd_uniforms, extend='hold')
    upd.comment = 'Decoded state: old texture moved by the new motion + residual; I-frame / block refresh -> cur.'
    return upd, mv, ['stamp', 'stamp_compute', 'lum', 'lum_compute', 'mv', 'mv_compute', 'cprev', 'sfb', 'upd',
                     'upd_compute']


def fx_out(m, H, dry, upd, mv, amount_expr, view_expr, sel_expr, extra=()):
    """fx (mix dry/S + views, format useinput) -> out_sel (Switch: 0 dry exact, 1 fx, extra...) -> out1."""
    mk, expr = H['mk'], H['expr']
    fx = _glsl(m, H, 'fx', FX, res=("op('in1').width", "op('in1').height"), fmt='useinput', inputs=[dry, upd, mv],
               uniforms=[('uF', [amount_expr, view_expr, SCALE, "4.0 * " + SCALE])])
    fx.comment = 'Out = mix(dry, S, Amount); View vectors / match error for checking.'
    sel = mk(m, switchTOP, 'out_sel')
    for i, src in enumerate([dry, fx] + list(extra)):
        sel.inputConnectors[i].connect(src)
    expr(sel.par.index, sel_expr)
    sel.comment = 'Amount 0 = in1 exact (the engine is not pulled, so it costs nothing).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return ['fx', 'fx_compute', 'out_sel', 'out1']


def pulses(m, H, text):
    """Parameter Execute for the instance's Pulse pars (they bump plain pars, which the uniforms read)."""
    pe = H['mk'](m, parameterexecuteDAT, 'pulses')
    pe.text = text
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = '*'
    pe.par.valuechange = False
    pe.par.onpulse = True
    pe.comment = 'Pulse pars -> plain pars (Refresh count / Go time), so uniforms see them.'
    return pe


PULSES = """# mosh: Refresh pulse -> Refreshcount + 1 (stamp sees the change = one I-frame)
def onPulse(par):
\tif par.name == 'Refresh':
\t\tpar.owner.par.Refreshcount = int(par.owner.par.Refreshcount.eval()) + 1
\treturn
"""

BEAT = ("(lambda o, ch: (float(o[ch][0]) if o is not None and o[ch] is not None else 0.0))"
        "(op(parent().par.Beatchop.eval()) if parent().par.Beatchop.eval() and parent().par.Beatevery.eval() > 0 "
        "else None, parent().par.Beatchan.eval())")


def build(m, H):
    mk, expr = H['mk'], H['expr']
    if not m.par.Clipfile.eval():
        m.par.Clipfile = CLIP
    in1 = mk(m, inTOP, 'in1')
    clip = mk(m, moviefileinTOP, 'clip')
    expr(clip.par.file, "parent().par.Clipfile.eval()")
    clip.par.outputresolution = 'custom'
    expr(clip.par.resolutionw, "op('in1').width")
    expr(clip.par.resolutionh, "op('in1').height")
    clip.par.outputaspect = 'resolution'
    clip.par.fillmode = 'fitoutside'
    expr(clip.par.play, "parent().par.Source.eval() != 'live'")
    clip.comment = 'Offline tools/mosh.py clip (Source clip / blend), filled to in1 size; plays only when used.'
    bl = mk(m, crossTOP, 'src_blend')
    bl.inputConnectors[0].connect(in1)
    bl.inputConnectors[1].connect(clip)
    expr(bl.par.cross, P.format('Clipblend'))
    src = mk(m, switchTOP, 'src')
    for i, s_ in enumerate([in1, clip, bl]):
        src.inputConnectors[i].connect(s_)
    expr(src.par.index, 'parent().par.Source.menuIndex')
    src.comment = 'Engine picture: live / mosh clip / blend.'
    pulses(m, H, PULSES)
    upd, mv, eops = engine(
        m, H, src, 'src', STAMP,
        [('uT', ['absTime.seconds', P.format('Refreshcount'), BEAT, P.format('Beatevery')]),
         ('uM', ['parent().par.Mode.menuIndex', P.format('Holdtime'), P.format('Randomrate'), P.format('Period')]),
         ('uH', ['1 if %s else 0' % P.format('Holdauto'), P.format('Seed'), '0', '0'])],
        [('uA', [P.format('Gain'), P.format('Bloomgain'), P.format('Minmag'), P.format('Residual')]),
         ('uB', [P.format('Decay'), P.format('Blockwarp'), '1 if %s else 0' % P.format('Subpel'), SCALE]),
         ('uC', [P.format('Blockrefresh'), '0', '1', P.format('Seed')]),
         ('uD', ['0.5', '0.5', 'absTime.frame % 10007', '0'])])
    oops = fx_out(m, H, in1, upd, mv, P.format('Amount'), 'parent().par.View.menuIndex',
                  '1 if %s > 0 else 0' % P.format('Amount'))
    return [
        {'title': '1 Source', 'role': 'input', 'ops': ['in1', 'clip', 'src_blend', 'src', 'pulses'],
         'body': 'Live in1, an offline tools/mosh.py clip, or a blend. Pulses: Refresh -> Refreshcount.'},
        {'title': '2 Engine', 'role': 'process', 'ops': eops,
         'body': 'stamp (clock + I-frames) -> lum (luma, est res) -> mv (block match) -> upd (state S, sfb feedback).'},
        {'title': '3 Out', 'role': 'output', 'ops': oops, 'body': 'Amount 0 = in1 exact; View = vectors / error.'},
    ]
