# fx_glitch_feedbackkill - FX_glitch module 'feedbackkill' (FX1 DG-21 feedback destruction / generation loss,
# burn-in). Template: docs/builds/fx_glitch.md "Module template"; doc + LIVE CHECKS: docs/builds/fx_glitch_feedbackkill.md.
# A Feedback loop wrapped round ONE destructive compute pass (T-46/T-47): every generation the previous state is
#   1 resampled: zoom / rotate about the centre, shift (px per generation), displaced by its own luma gradient (Curl
#     = along the contours: swirls); integer shifts with no zoom/rotate use texelFetch (exact, no blur creep)
#   2 filtered: Soften (5-tap blur), Sharpen (unsharp), Burn (dilate brights = burn-in) at Radius px
#   3 coloured: hue step (rotation about grey, exact at 0), saturation, contrast + bright, wavefold
#   4 decayed and fed: the live picture comes in by Feed (mix / lighten = burn-in / darken / difference / add),
#     Leak x Key (only live pixels brighter than Key)
#   5 stabilised: Autogain pulls the frame mean toward Target (measured by the stamp meter: 64x64 grid of the previous
#     state), so no preset locks to black or white; then Crush (bits, with dither), Noise, clamp 0..1.
# Rate = generations per second (0 = every cook; e.g. 2 = photocopy twice a second), Hold freezes, Reset (toggle) =
# live. Precision 16f (smooth drift; default) or 8-bit (each generation re-quantised like a re-save). A separate
# `outc` pass mixes live -> state by Amount in the input format: Amount 0 = exact passthrough, while the state keeps
# evolving. Stale history (slot bypassed > 0.25 s) restarts from live. Pure maths: fx_time_logic.fk_*. ASCII only.

MODULE = 'feedbackkill'
FEEDS = ['mix', 'lighten', 'darken', 'difference', 'add']
EDGES = ['mirror', 'repeat', 'clamp', 'black']

PAGES = [
    ('Feedback', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (live -> state)'}),
        ('Leak', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Leak (live in per generation)'}),
        ('Feed', 'Menu', 'mix', {'names': FEEDS, 'labels': ['Mix', 'Lighten (burn-in)', 'Darken', 'Difference',
                                                           'Add']}),
        ('Key', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Key (live luma above)'}),
        ('Decay', 'Float', 1.0, {'min': 0.8, 'max': 1.05, 'label': 'Decay x per generation'}),
        ('Rate', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Generations/s (0 = every cook)'}),
        ('Hold', 'Toggle', False, {'label': 'Hold (freeze)'}),
        ('Reset', 'Toggle', False, {'label': 'Reset (state = live)'}),
        ('Precision', 'Menu', '16f', {'names': ['16f', '8bit'], 'labels': ['16-bit float', '8-bit (re-save)']}),
    ]),
    ('Transform', [
        ('Zoom', 'Float', 1.0, {'min': 0.9, 'max': 1.1, 'label': 'Zoom x per generation'}),
        ('Rotate', 'Float', 0.0, {'min': -5, 'max': 5, 'label': 'Rotate deg per generation'}),
        ('Shiftx', 'Float', 0.0, {'min': -8, 'max': 8, 'label': 'Shift x px per generation'}),
        ('Shifty', 'Float', 0.0, {'min': -8, 'max': 8, 'label': 'Shift y px per generation'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
        ('Edge', 'Menu', 'mirror', {'names': EDGES, 'labels': ['Mirror', 'Repeat', 'Clamp', 'Black']}),
        ('Displace', 'Float', 0.0, {'min': -20, 'max': 20, 'label': 'Displace px (own gradient)'}),
        ('Curl', 'Toggle', False, {'label': 'Curl (along contours)'}),
        ('Radius', 'Float', 1.5, {'min': 0.5, 'max': 8, 'label': 'Filter radius px'}),
    ]),
    ('Damage', [
        ('Soften', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Soften'}),
        ('Sharpen', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Sharpen'}),
        ('Burn', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Burn (dilate brights)'}),
        ('Huestep', 'Float', 0.0, {'min': -30, 'max': 30, 'label': 'Hue deg per generation'}),
        ('Saturation', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Saturation x'}),
        ('Contrast', 'Float', 1.0, {'min': 0.8, 'max': 1.2, 'label': 'Contrast x'}),
        ('Bright', 'Float', 0.0, {'min': -0.05, 'max': 0.05, 'label': 'Bright +'}),
        ('Fold', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Wavefold'}),
        ('Crush', 'Int', 0, {'min': 0, 'max': 8, 'label': 'Crush bits (0 = off)'}),
        ('Dither', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Crush dither'}),
        ('Noise', 'Float', 0.0, {'min': 0, 'max': 0.2, 'label': 'Noise per generation'}),
        ('Autogain', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Autogain (stabiliser)'}),
        ('Target', 'Float', 0.45, {'min': 0.05, 'max': 0.95, 'label': 'Autogain target mean'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['Feedback', 'Transform', 'Damage']

_Z = {'Feed': 0, 'Key': 0.0, 'Decay': 1.0, 'Rate': 0.0, 'Hold': 0, 'Reset': 0, 'Precision': 0, 'Zoom': 1.0,
      'Rotate': 0.0, 'Shiftx': 0.0, 'Shifty': 0.0, 'Centerx': 0.5, 'Centery': 0.5, 'Edge': 0, 'Displace': 0.0,
      'Curl': 0, 'Radius': 1.5, 'Soften': 0.0, 'Sharpen': 0.0, 'Burn': 0.0, 'Huestep': 0.0, 'Saturation': 1.0,
      'Contrast': 1.0, 'Bright': 0.0, 'Fold': 0.0, 'Crush': 0, 'Dither': 0.0, 'Noise': 0.0, 'Autogain': 0.0,
      'Target': 0.45}
PRESETS = [
    (1, 'photocopy decay', dict(_Z, Amount=1.0, Leak=0.05, Shifty=-1.0, Contrast=1.04, Sharpen=0.35,
                                Saturation=0.9, Noise=0.02, Autogain=0.5, Target=0.5, Seed=1)),
    (2, 'tape dub', dict(_Z, Amount=1.0, Leak=0.1, Shiftx=1.0, Soften=0.25, Huestep=1.5, Saturation=0.97,
                         Noise=0.01, Autogain=0.3, Seed=2)),
    (3, 'burn-in', dict(_Z, Amount=1.0, Leak=1.0, Feed=1, Key=0.5, Decay=0.97, Burn=0.6, Radius=1.0, Seed=3)),
    (4, 'acid loop', dict(_Z, Amount=1.0, Leak=0.06, Zoom=1.02, Rotate=1.5, Huestep=6.0, Saturation=1.05,
                          Fold=0.2, Autogain=0.6, Seed=4)),
    (5, 'melt flow', dict(_Z, Amount=1.0, Leak=0.04, Displace=4.0, Curl=1, Radius=2.0, Soften=0.2, Autogain=0.4,
                          Seed=5)),
]

HASH = """uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h(uvec4 k) { return float(pcg(k.x ^ pcg(k.y ^ pcg(k.z ^ pcg(k.w)))) >> 8) / 16777215.0; }
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
"""

SHADER = """// FX_glitch feedbackkill (compute, T-47; DG-21). in0 live picture, in1 previous state (Feedback TOP of fx),
// in2 stamp/meter (x now, y previous cook, z cooks since fresh, w mean luma of the previous state).
// = fx_time_logic.fk_colour / fk_shift / fk_edge.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // leak feed key decay
uniform vec4 uB;   // rate hold reset seed
uniform vec4 uC;   // zoom rotate(deg) shiftx shifty
uniform vec4 uD;   // centrex centrey edge displace
uniform vec4 uE;   // curl radius soften sharpen
uniform vec4 uF;   // burn huestep(deg) saturation contrast
uniform vec4 uG;   // bright fold crush dither
uniform vec4 uH;   // noise autogain target frame
""" + HASH + """bool ig;                                              // exact geometry: integer shift only -> texelFetch
vec2 edgep(vec2 q, vec2 sz, int e) {
    if (e == 1) return mod(q, sz);
    if (e == 0) { vec2 t = mod(q, 2.0 * sz); return min(t, 2.0 * sz - t); }
    return clamp(q, vec2(0.5), sz - 0.5);
}
vec3 tap(vec2 q, vec2 sz, int e) {
    if (e == 3 && (any(lessThan(q, vec2(0.0))) || any(greaterThan(q, sz)))) return vec3(0.0);
    vec2 r = edgep(q, sz, e);
    if (ig) return texelFetch(sTD2DInputs[1], clamp(ivec2(floor(r)), ivec2(0), ivec2(sz) - 1), 0).rgb;
    return texture(sTD2DInputs[1], r / sz).rgb;
}
vec3 kill(vec3 c, vec3 live, float mean, uvec4 key) {
    if (uF.y != 0.0) {                                 // Rodrigues about grey: exact at 0, r -> g -> b at 120
        float a = radians(uF.y); vec3 k = vec3(0.57735026919);
        c = c * cos(a) + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - cos(a));
    }
    float y = lum(c);
    c = y + (c - y) * uF.z;
    c = (c - 0.5) * uF.w + 0.5 + uG.x;
    if (uG.y > 0.0) c = 1.0 - abs(1.0 - mod(c * (1.0 + uG.y), 2.0));
    c *= uA.w;
    float kw = uA.z <= 0.0 ? 1.0 : smoothstep(uA.z - 0.05, uA.z + 0.05, lum(live));
    float L = uA.x * kw;
    int fm = int(uA.y + 0.5);
    if (fm == 0) c = c + (live - c) * L;
    else if (fm == 1) c = max(c, live * L);
    else if (fm == 2) c = min(c, 1.0 + (live - 1.0) * L);
    else if (fm == 3) c = abs(c - live * L);
    else c = c + live * L;
    if (uH.y > 0.0) {
        float g = uH.z / max(mean, 0.02);
        c = c * (1.0 + (g - 1.0) * 0.2 * uH.y) + (uH.z - mean) * 0.05 * uH.y;
    }
    if (uG.z >= 1.0) {
        float lv = exp2(floor(uG.z)) - 1.0;
        vec3 dz = uG.w > 0.0 ? (vec3(h(key), h(key ^ uvec4(0u, 0u, 0u, 1u)), h(key ^ uvec4(0u, 0u, 0u, 2u))) - 0.5) * uG.w
                             : vec3(0.0);
        c = floor(c * lv + 0.5 + dz) / lv;
    }
    if (uH.x > 0.0) c += (vec3(h(key ^ uvec4(0u, 0u, 0u, 3u)), h(key ^ uvec4(0u, 0u, 0u, 4u)),
                               h(key ^ uvec4(0u, 0u, 0u, 5u))) - 0.5) * uH.x;
    return clamp(c, 0.0, 1.0);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec2 sz = vec2(isz);
    vec4 live = texelFetch(sTD2DInputs[0], p, 0);
    vec4 st = texelFetch(sTD2DInputs[2], ivec2(0), 0);
    if (st.z < 0.5 || uB.z > 0.5) { TDImageStoreOutput(0, ivec3(p, 0), live); return; }   // fresh / Reset
    vec4 prev = texelFetch(sTD2DInputs[1], p, 0);
    bool tick = uB.x <= 0.0 || floor(st.x * uB.x) != floor(st.y * uB.x);
    if (uB.y > 0.5 || !tick) { TDImageStoreOutput(0, ivec3(p, 0), prev); return; }       // Hold / between ticks
    ig = uC.x == 1.0 && uC.y == 0.0 && fract(uC.z) == 0.0 && fract(uC.w) == 0.0 && uD.w == 0.0;
    vec2 q0 = vec2(p) + 0.5;
    vec2 C = uD.xy * sz;
    float a = radians(uC.y);
    vec2 d = q0 - C;
    vec2 q = C + vec2(cos(a) * d.x + sin(a) * d.y, -sin(a) * d.x + cos(a) * d.y) / max(uC.x, 1e-4) - uC.zw;
    int e = int(uD.z + 0.5);
    vec3 c;
    if (uE.z == 0.0 && uE.w == 0.0 && uF.x == 0.0 && uD.w == 0.0) c = tap(q, sz, e);
    else {
        float r = uE.y;
        vec3 tl = tap(q - vec2(r, 0.0), sz, e), tr = tap(q + vec2(r, 0.0), sz, e);
        vec3 td = tap(q - vec2(0.0, r), sz, e), tu = tap(q + vec2(0.0, r), sz, e);
        if (uD.w != 0.0) {
            vec2 gr = vec2(lum(tr) - lum(tl), lum(tu) - lum(td));
            if (uE.x > 0.5) gr = vec2(-gr.y, gr.x);
            q += gr * uD.w;
        }
        c = tap(q, sz, e);
        vec3 blur = (c + tl + tr + td + tu) * 0.2;
        c = mix(c, blur, uE.z);
        c += (c - blur) * uE.w;
        if (uF.x != 0.0) c = max(c, max(max(tl, tr), max(td, tu)) * uF.x);
    }
    uvec4 key = uvec4(uvec2(p), uint(uH.w), uint(uB.w) * 7919u);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(kill(c, live.rgb, st.w, key), live.a));
}
"""

METER = """// feedbackkill stamp + meter (T-111): 1x1 rgba32float in place, ONE 16x16 workgroup. x now, y previous cook,
// z cooks since fresh (gap > 0.25 s = slot was bypassed -> restart from live), w mean luma of in0 (the previous
// state) over a 64x64 texel grid (= fx_time_logic.fk_mean_grid), shared-memory sum.
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uT;   // now
shared float sm[256];
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
void main() {
    uint t = gl_LocalInvocationIndex;
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    ivec2 l = ivec2(gl_LocalInvocationID.xy);
    float acc = 0.0;
    for (int j = 0; j < 4; j++) {
        for (int i = 0; i < 4; i++) {
            ivec2 gp = l * 4 + ivec2(i, j);
            ivec2 q = clamp(ivec2((vec2(gp) + 0.5) / 64.0 * vec2(sz)), ivec2(0), sz - 1);
            acc += lum(texelFetch(sTD2DInputs[0], q, 0).rgb);
        }
    }
    sm[t] = acc / 16.0;
    barrier();
    for (uint s = 128u; s > 0u; s >>= 1u) {
        if (t < s) sm[t] += sm[t + s];
        barrier();
    }
    if (t == 0u) {
        vec4 o = TDImageLoadOutput(0, ivec3(0));
        bool fresh = uT.x - o.x > 0.25 || uT.x < o.x;
        TDImageStoreOutput(0, ivec3(0), vec4(uT.x, o.x, fresh ? 0.0 : o.z + 1.0, sm[0] / 256.0));
    }
}
"""

OUTC = """// feedbackkill out: live -> state by Amount, in the input format (Amount 0 = in0 texel, exact).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 a = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), a); return; }
    TDImageStoreOutput(0, ivec3(p, 0), mix(a, texelFetch(sTD2DInputs[1], p, 0), uA.x));
}
"""

P = "parent().par.{}.eval()"
TOG = '1 if parent().par.{}.eval() else 0'


def build(m, H):
    """in1 -> fb (Feedback of fx) -> stamp (meter) -> fx (one pass, state) -> outc (Amount, input format) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    fb = mk(m, feedbackTOP, 'fb')
    fb.inputConnectors[0].connect(in1)
    st = H['compute'](m, 'stamp', METER, [fb], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    st.par.autodispatchsize = False                    # exactly one 16x16 workgroup
    st.par.dispatchsizex, st.par.dispatchsizey, st.par.dispatchsizez = 1, 1, 1
    H['uniforms'](st, [('uT', ['absTime.seconds', '0', '0', '0'])])
    st.comment = 'Cook clock + mean luma of the previous state (Autogain); gap > 0.25 s = restart from live.'
    g = H['compute'](m, 'fx', SHADER, [in1, fb, st])
    expr(g.par.format, "'rgba16float' if parent().par.Precision.eval() == '16f' else 'useinput'")
    g.par.inputextenduv = 'hold'
    H['uniforms'](g, uniforms())
    g.comment = 'feedbackkill: one generation per tick (resample, filter, colour, feed, stabilise, crush) = state.'
    fb.par.top = 'fx'
    fb.comment = 'Previous state (fx); stale after a bypass -> the stamp restarts it from live.'
    oc = H['compute'](m, 'outc', OUTC, [in1, g])
    H['uniforms'](oc, [('uA', [P.format('Amount'), '0', '0', '0'])])
    oc.comment = 'Amount mix in the input format (Amount 0 = exact in1); the state keeps evolving.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(oc)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Generation', 'role': 'process',
         'ops': ['fb', 'stamp', 'stamp_compute', 'fx', 'fx_compute'],
         'body': 'fb (Feedback of fx) -> stamp (clock + mean) -> fx: one destructive generation per tick.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['outc', 'outc_compute', 'out1']},
    ]


def uniforms():
    """[(uniform, [x, y, z, w expressions])] of the fx pass (names = the SHADER declarations; tested offline)."""
    return [
        ('uA', [P.format('Leak'), 'parent().par.Feed.menuIndex', P.format('Key'), P.format('Decay')]),
        ('uB', [P.format('Rate'), TOG.format('Hold'), TOG.format('Reset'), P.format('Seed')]),
        ('uC', [P.format('Zoom'), P.format('Rotate'), P.format('Shiftx'), P.format('Shifty')]),
        ('uD', [P.format('Centerx'), P.format('Centery'), 'parent().par.Edge.menuIndex', P.format('Displace')]),
        ('uE', [TOG.format('Curl'), P.format('Radius'), P.format('Soften'), P.format('Sharpen')]),
        ('uF', [P.format('Burn'), P.format('Huestep'), P.format('Saturation'), P.format('Contrast')]),
        ('uG', [P.format('Bright'), P.format('Fold'), P.format('Crush'), P.format('Dither')]),
        ('uH', [P.format('Noise'), P.format('Autogain'), P.format('Target'), 'absTime.frame']),
    ]
