# fx_analog_plasma - FX_analog module 'plasma' (FX2 AV-15 plasma display dynamic false contour; FX0 row 78).
# Template: docs/builds/fx_glitch.md "Module template" (FX_analog rack = builders/fx_analog.py). Doc:
# docs/builds/fx_analog_plasma.md. Numpy mirror: builders/fx_analog_plasma_logic.py.
# A PDP shows each 8-bit level as a sum of time-sliced sub-fields (weights 1, 2, 4 ... per frame). The eye tracks a
# moving picture, so it collects sub-field k from the pixel at p + v * (t_k - 0.5): on moving gradients the sums jump
# across sub-field boundaries (127 -> 128 = all bits flip) = coloured false contours. Passes:
#   est (optional, Motion = estimate): coarse normal-flow motion per Estres cell from the previous cook's cell luma
#        (in place, rgba32float, no optical flow op: T-18), pulled only in estimate mode (mv_src Switch)
#   fx : per pixel, per sub-field: sample code at the tracked position, greedy sub-field split, sum lit weights;
#        Greenlag (slow green phosphor), Dither (dark-level noise), Cells (RGB stripe + ribs)
# Amount 0 = in1 exact (out_sel; fx also writes texelFetch). <= 3 GLSL TOP inputs (T-88). ASCII only.

MODULE = 'plasma'
TABLE_NAMES = ['binary8', 'pdp10', 'pdp12']
MOTIONS = ['vector', 'sweep', 'estimate']

PAGES = [
    ('Plasma', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Subfields', 'Menu', 'binary8', {'names': TABLE_NAMES, 'labels': [
            'Binary 8 (1..128, strongest contours)', 'PDP 10 (4 x 48 MSB)', 'PDP 12 (5 x 32 + 40 MSB)']}),
        ('Order', 'Menu', 'asc', {'names': ['asc', 'desc'], 'labels': ['Ascending weights', 'Descending weights']}),
        ('Address', 'Float', 6.0, {'min': 0, 'max': 30, 'label': 'Address time per sub-field (weight units)'}),
        ('Gamma', 'Float', 2.2, {'min': 1, 'max': 3, 'label': 'Panel gamma (1 = linear codes)'}),
        ('Motion', 'Menu', 'vector', {'names': MOTIONS, 'labels': [
            'Vector (Motion x/y)', 'Sweep (vector x sine)', 'Estimate (frame difference) + vector']}),
        ('Motionx', 'Float', 6.0, {'min': -24, 'max': 24, 'label': 'Motion x px per frame'}),
        ('Motiony', 'Float', 0.0, {'min': -24, 'max': 24, 'label': 'Motion y px per frame'}),
        ('Period', 'Float', 2.0, {'min': 0.1, 'max': 10, 'label': 'Sweep period s'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (dither)'}),
    ]),
    ('Estimate', [
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 5, 'label': 'Estimated motion gain'}),
        ('Estres', 'Int', 8, {'min': 2, 'max': 32, 'label': 'Estimate cell px'}),
        ('Eps', 'Float', 0.0004, {'min': 0, 'max': 0.01, 'label': 'Flat-area damping'}),
        ('Minmotion', 'Float', 0.1, {'min': 0, 'max': 4, 'label': 'Min motion px (noise gate)'}),
        ('Smooth', 'Float', 0.5, {'min': 0, 'max': 0.95, 'label': 'Temporal smoothing'}),
    ]),
    ('Look', [
        ('Dither', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Dither (code units)'}),
        ('Greenlag', 'Float', 0.0, {'min': -0.5, 'max': 0.5, 'label': 'Green phosphor lag (frames)'}),
        ('Cells', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Cell structure'}),
        ('Cellsize', 'Float', 6.0, {'min': 2, 'max': 32, 'label': 'Cell px'}),
    ]),
]
PANEL_PAGES = ['Plasma', 'Estimate', 'Look']

_Z = {'Dither': 0.0, 'Greenlag': 0.0, 'Cells': 0.0, 'Order': 0, 'Address': 6.0, 'Gamma': 2.2, 'Motiony': 0.0}
PRESETS = [
    (1, 'pan contour', dict(_Z, Amount=1.0, Subfields=0, Motion=0, Motionx=6.0, Seed=1)),
    (2, 'sweep', dict(_Z, Amount=1.0, Subfields=0, Motion=1, Motionx=10.0, Period=2.0, Seed=2)),
    (3, 'real pdp', dict(_Z, Amount=1.0, Subfields=1, Motion=2, Motionx=0.0, Gain=1.5, Dither=0.6, Greenlag=0.15,
                         Cells=0.25, Cellsize=6.0, Seed=3)),
    (4, 'heavy', dict(_Z, Amount=1.0, Subfields=0, Order=1, Motion=2, Motionx=0.0, Gain=3.0, Greenlag=0.3, Seed=4)),
    (5, 'plasma wall', dict(_Z, Amount=1.0, Subfields=2, Motion=0, Motionx=3.0, Motiony=2.0, Cells=0.5,
                            Cellsize=9.0, Seed=5)),
]

LIB = """
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hsh(ivec2 c, uint s) { return float(lb32(uint(c.x) * 1597334677u ^ lb32(uint(c.y) ^ (s * 2654435761u)))) * (1.0 / 4294967296.0); }
"""

WT = """
float wt(int tb, int k) {                // ascending weight tables, each sums to 255
    if (tb == 0) return k < 8 ? float(1 << k) : 0.0;
    if (tb == 1) return k < 6 ? float(1 << k) : (k < 10 ? 48.0 : 0.0);
    if (k < 5) return float(1 << k);
    if (k == 5) return 24.0;
    if (k < 11) return 32.0;
    return k == 11 ? 40.0 : 0.0;
}
uint lit(float code, int tb, int n) {    // greedy split, largest weight first -> bit mask (bit k = sub-field k)
    // closed form of the greedy loop per table (perf lane 2, 27 Oct; same masks for every code 0..255, test)
    uint c = uint(code);
    if (tb == 0) return c;                                                  // 1..128: the binary code itself
    if (tb == 1) {                                                          // 1..32 + 4 x 48 (bits 9 down to 6)
        uint h = min(c / 48u, 4u);
        return (((1u << h) - 1u) << (10u - h)) | (c - 48u * h);
    }
    uint m = 0u;                                                            // 1..16, 24, 5 x 32, 40
    if (c >= 40u) { m = 1u << 11; c -= 40u; }
    uint h = min(c / 32u, 5u);
    m |= ((1u << h) - 1u) << (11u - h);
    c -= 32u * h;
    if (c >= 24u) { m |= 1u << 5; c -= 24u; }
    return m | c;
}
float gp(float x) { x = max(x, 0.0); return uA.w == 1.0 ? x : pow(x, uA.w); }
float code(float x, float d) { return clamp(floor(gp(x) * 255.0 + d + 0.5), 0.0, 255.0); }
"""

CODES = """// plasma codes (compute, rgba32float, picture size; perf lane 2, 27 Oct). Per pixel once: 8-bit code (Gamma,
// dither at this pixel) -> sub-field bit masks r, g, b (exact integers in float). fx reads them at the tracked positions
// instead of re-coding every sub-field's source pixel (same masks: the dither hash is per source pixel).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, subfield table, order, gamma
uniform vec4 uC;   // dither, greenlag, cells, cellsize
uniform vec4 uD;   // seed, frame, address, -
""" + LIB + WT + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    int tb = clamp(int(uA.y + 0.5), 0, 2);
    int n = tb == 0 ? 8 : (tb == 1 ? 10 : 12);
    uint sd = uint(uD.x) * 977u + uint(uD.y);
    vec4 sp = texelFetch(sTD2DInputs[0], p, 0);
    float d = (hsh(p, sd) - 0.5) * uC.x;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(float(lit(code(sp.r, d), tb, n)), float(lit(code(sp.g, d), tb, n)),
                                            float(lit(code(sp.b, d), tb, n)), 0.0));
}
"""

FX = """// FX_analog plasma fx (compute, T-47). in0 picture (texelFetch only), in1 motion field (est: rgba32float, xy = full px
// per cook; or the 1x1 zero), in2 codes (sub-field masks per pixel). Sub-field k of each 8-bit code is seen from the
// pixel at p + v * (t_k - 0.5) (eye tracks the motion): sums differ from the code where the picture moves across sub-field boundaries = false contours (AV-15).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, subfield table, order, gamma
uniform vec4 uB;   // vx, vy (px per cook), motion mode, gain
uniform vec4 uC;   // dither, greenlag, cells, cellsize
uniform vec4 uD;   // seed, frame, address, -
""" + WT + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    int tb = clamp(int(uA.y + 0.5), 0, 2);
    int n = tb == 0 ? 8 : (tb == 1 ? 10 : 12);
    float total = float(n) * uD.z + 255.0;
    vec2 v = uB.xy;
    if (int(uB.z + 0.5) == 2) v += texture(sTD2DInputs[1], (vec2(p) + 0.5) / vec2(isz)).xy * uB.w;
    vec2 pc = vec2(p) + 0.5;
    float gl = uC.y;
    vec3 acc = vec3(0.0);
    ivec2 lq = ivec2(-1 << 20);
    uvec3 lm = uvec3(0u);
    ivec2 lg = ivec2(-1 << 20);
    uint lmg = 0u;
    bool asc = int(uA.z + 0.5) == 0;
    float cum = 0.0;
    for (int s = 0; s < 12; s++) {                     // time order; t_k inline (no per-thread array, T-187)
        if (s >= n) break;
        int k = asc ? s : n - 1 - s;
        float w = wt(tb, k);
        float t = (cum + uD.z + 0.5 * w) / total - 0.5;
        cum += uD.z + w;
        ivec2 q = clamp(ivec2(floor(pc + v * t)), ivec2(0), isz - 1);
        if (q != lq) {                                                        // neighbours often share a pixel
            lq = q;
            lm = uvec3(texelFetch(sTD2DInputs[2], q, 0).rgb);
        }
        uint mg = lm.g;
        if (gl != 0.0) {
            ivec2 qg = clamp(ivec2(floor(pc + v * (t + gl))), ivec2(0), isz - 1);
            if (qg != lg) {
                lg = qg;
                lmg = uint(texelFetch(sTD2DInputs[2], qg, 0).g);
            }
            mg = lmg;
        }
        uint b = 1u << uint(k);
        acc += w * vec3((lm.r & b) != 0u ? 1.0 : 0.0, (mg & b) != 0u ? 1.0 : 0.0, (lm.b & b) != 0u ? 1.0 : 0.0);
    }
    vec3 o = acc / 255.0;
    if (uA.w != 1.0) o = pow(o, vec3(1.0 / uA.w));
    if (uC.z > 0.0) {                                                           // RGB stripe cells + ribs
        float cs = max(uC.w, 1.0);
        int sub = min(int(fract(pc.x / cs) * 3.0), 2);
        vec3 msk = vec3(1.0 - uC.z);
        msk[sub] = 1.0;
        if (fract(pc.y / cs) < 0.12) msk *= 1.0 - uC.z;
        o *= msk;
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(mix(c.rgb, o, uA.x), c.a));
}
"""

EST = """// plasma motion estimate (compute, rgba32float, in place: outputaccess readwrite, clearoutputs off). One texel per
// Estres x Estres cell: xy = motion (full px per cook), z = cell luma, w = last cook time. Normal flow from the
// previous cook's cell luma (no optical flow op, T-18). Same frame = unchanged; gap > 0.25 s = restart (v 0).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uE;   // estres, eps, minmotion px, now
uniform vec4 uF;   // smooth, -, -, -
float cellL(ivec2 c, ivec2 isz, int E) {
    float s = 0.0;
    for (int j = 0; j < 4; j++) for (int i = 0; i < 4; i++) {
        ivec2 q = clamp(c * E + ivec2((vec2(i, j) + 0.5) * float(E) * 0.25), ivec2(0), isz - 1);
        s += dot(texelFetch(sTD2DInputs[0], q, 0).rgb, vec3(0.2126, 0.7152, 0.0722));
    }
    return s / 16.0;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    int E = max(int(uE.x + 0.5), 1);
    ivec2 csz = (isz + E - 1) / E;
    if (p.x >= csz.x || p.y >= csz.y) return;
    vec4 prev = TDImageLoadOutput(0, ivec3(p, 0));
    if (prev.w == uE.w) { TDImageStoreOutput(0, ivec3(p, 0), prev); return; }  // second cook in the same frame
    float L = cellL(p, isz, E);
    float gx = 0.5 * (cellL(min(p + ivec2(1, 0), csz - 1), isz, E) - cellL(max(p - ivec2(1, 0), ivec2(0)), isz, E));
    float gy = 0.5 * (cellL(min(p + ivec2(0, 1), csz - 1), isz, E) - cellL(max(p - ivec2(0, 1), ivec2(0)), isz, E));
    vec2 v = vec2(0.0);
    bool fresh = !(uE.w - prev.w <= 0.25) || prev.w <= 0.0;
    if (!fresh) {
        vec2 g = vec2(gx, gy);
        v = -(L - prev.z) * g / (dot(g, g) + uE.y) * float(E);
        if (length(v) < uE.z) v = vec2(0.0);
        v = v * (1.0 - uF.x) + prev.xy * uF.x;
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(v, L, uE.w));
}
"""

SHADERS = {'codes': CODES, 'fx': FX, 'est': EST}

P = "parent().par.{}.eval()"
SWEEP = ("(math.sin(2 * math.pi * absTime.seconds / max(%s, 1e-3)) if parent().par.Motion.eval() == 'sweep' else 1.0)"
         % P.format('Period'))


def uniforms():
    return {
        'fx': [('uA', [P.format('Amount'), 'parent().par.Subfields.menuIndex', 'parent().par.Order.menuIndex',
                       P.format('Gamma')]),
               ('uB', ['%s * %s' % (P.format('Motionx'), SWEEP), '%s * %s' % (P.format('Motiony'), SWEEP),
                       'parent().par.Motion.menuIndex', P.format('Gain')]),
               ('uC', [P.format('Dither'), P.format('Greenlag'), P.format('Cells'), P.format('Cellsize')]),
               ('uD', [P.format('Seed'), 'absTime.frame', P.format('Address'), '0'])],
        'codes': [('uA', [P.format('Amount'), 'parent().par.Subfields.menuIndex', 'parent().par.Order.menuIndex',
                           P.format('Gamma')]),
                  ('uC', [P.format('Dither'), '0', '0', '0']),
                  ('uD', [P.format('Seed'), 'absTime.frame', '0', '0'])],
        'est': [('uE', [P.format('Estres'), P.format('Eps'), P.format('Minmotion'), 'absTime.seconds']),
                ('uF', [P.format('Smooth'), '0', '0', '0'])],
    }


def build(m, H):
    """Fill instance COMP m: in1 -> est (estimate only, via mv_src) -> fx -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')
    est = H['compute'](m, 'est', EST, [in1], fmt='rgba32float')
    expr(est.par.resolutionw, "int(math.ceil(me.inputs[0].width / max(1, int(round(%s)))))" % P.format('Estres'))
    expr(est.par.resolutionh, "int(math.ceil(me.inputs[0].height / max(1, int(round(%s)))))" % P.format('Estres'))
    est.par.outputaccess = 'readwrite'
    est.par.clearoutputs = False
    H['uniforms'](est, U['est'])
    est.comment = 'Motion estimate per Estres cell (in place): xy full px per cook, z cell luma, w last cook.'
    zero = mk(m, constantTOP, 'mv_zero')
    zero.par.outputresolution = 'custom'
    zero.par.resolutionw, zero.par.resolutionh = 1, 1
    zero.par.colorr = zero.par.colorg = zero.par.colorb = zero.par.alpha = 0
    zero.comment = '1x1 zero motion field (vector / sweep modes: est is not pulled).'
    mv = mk(m, switchTOP, 'mv_src')
    mv.inputConnectors[0].connect(zero)
    mv.inputConnectors[1].connect(est)
    expr(mv.par.index, "1 if parent().par.Motion.eval() == 'estimate' else 0")
    mv.comment = 'Motion field: est only in Estimate mode.'
    codes = H['compute'](m, 'codes', CODES, [in1], fmt='rgba32float')
    H['uniforms'](codes, U['codes'])
    codes.comment = 'Sub-field masks per pixel (Gamma + dither + split once per pixel; fx reads them at the tracked positions).'
    fx = H['compute'](m, 'fx', FX, [in1, mv, codes])
    fx.par.inputextenduv = 'hold'                     # bilinear est field reads hold at the frame edge
    H['uniforms'](fx, U['fx'])
    fx.comment = 'plasma: sub-field split per tracked position -> dynamic false contour (AV-15). Amount 0 = exact.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (fx / est not pulled).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Motion', 'role': 'process', 'ops': ['est', 'est_compute', 'mv_zero', 'mv_src'],
         'body': 'Estimate mode: coarse normal flow from the previous cook (in place). Else a 1x1 zero field.'},
        {'title': '3 Sub-fields', 'role': 'process', 'ops': ['codes', 'codes_compute', 'fx', 'fx_compute'],
         'body': 'Per pixel: sub-field k from p + v (t_k - 0.5), greedy split, sum -> false contours.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
