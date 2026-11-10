# fx_glitch_dct - FX_glitch module 'dct' (FX1 DG-08 JPEG / DCT crush + generation loss; FX6 probe 1d).
# Template: docs/builds/fx_glitch.md "Module template". ONE compute pass, local_size 16x16 = one workgroup per 16x16
# macroblock: RGB -> YCbCr (JFIF), chroma 4:2:0 (2x2 average = half res, one 8x8 block) or 4:4:4, separable
# orthonormal DCT-II on Blocksize (4/8/16) luma blocks in shared memory (barriers), quantise with the IJG luma/chroma
# tables scaled by Quality (JPEG semantics) x Crush, coefficient damage (Cutoff, DC drift, Corrupt), inverse DCT,
# bilinear chroma up inside the macroblock, back to RGB. Generation = previous output mixed into the encoder input
# (JPEG-of-a-JPEG patina, 8-bit like a real re-save); Gridshift moves the block grid per Rate tick (with Generation the
# seams walk). Amount 0 = exact passthrough. ASCII only.

MODULE = 'dct'

PAGES = [
    ('DCT', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Quality', 'Float', 30.0, {'min': 1, 'max': 100, 'label': 'Quality (JPEG 1-100)'}),
        ('Crush', 'Float', 1.0, {'min': 1, 'max': 20, 'label': 'Crush (x quant step)'}),
        ('Chromaq', 'Float', 1.0, {'min': 0.25, 'max': 10, 'label': 'Chroma quant x'}),
        ('Blocksize', 'Menu', '8', {'names': ['4', '8', '16'], 'labels': ['4 (H.264)', '8 (JPEG)', '16 (MPEG-2)']}),
        ('Chroma', 'Menu', '420', {'names': ['420', '444'], 'labels': ['4:2:0 (half res)', '4:4:4 (full res)']}),
        ('Generation', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Generation loss (feedback)'}),
        ('Gridshift', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Grid shift per tick'}),
        ('Rate', 'Float', 12.0, {'min': 0, 'max': 60, 'label': 'Rate Hz (drift/corrupt/shift ticks)'}),
    ]),
    ('Damage', [
        ('Cutoff', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'High-freq cutoff'}),
        ('Dcdrift', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'DC drift (block colour walk)'}),
        ('Corrupt', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Corrupt block chance'}),
        ('Corruptamp', 'Float', 6.0, {'min': 0, 'max': 32, 'label': 'Corrupt amplitude (quant steps)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['DCT', 'Damage']

_Z = {'Cutoff': 0.0, 'Dcdrift': 0.0, 'Corrupt': 0.0, 'Generation': 0.0, 'Gridshift': 0.0, 'Crush': 1.0,
      'Chromaq': 1.0}
PRESETS = [
    (1, 'jpeg 30', dict(_Z, Amount=1.0, Quality=30.0, Blocksize=1, Chroma=0, Seed=1)),
    (2, 'blocky 5', dict(_Z, Amount=1.0, Quality=5.0, Crush=2.0, Blocksize=1, Chroma=0, Seed=2)),
    (3, 'chroma rot', dict(_Z, Amount=1.0, Quality=20.0, Chromaq=6.0, Dcdrift=0.25, Rate=6.0, Blocksize=1, Chroma=0,
                           Seed=3)),
    (4, 'mpeg2 mud', dict(_Z, Amount=1.0, Quality=10.0, Cutoff=0.55, Blocksize=2, Chroma=0, Corrupt=0.02,
                          Corruptamp=4.0, Rate=8.0, Seed=4)),
    (5, 'generational', dict(_Z, Amount=1.0, Quality=25.0, Generation=0.9, Gridshift=0.6, Rate=30.0, Blocksize=1,
                             Chroma=0, Seed=5)),
]

SHADER = """// FX_glitch dct (compute, T-47; FX6 1d). One workgroup = one 16x16 macroblock. in0 picture, in1 previous output
// (Generation) or the picture, in2 stamp (x now, y previous cook: a gap > 0.25 s = stale history).
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uA;   // amount quality crush chromaq
uniform vec4 uB;   // blocksize chroma444 generation gridshift
uniform vec4 uC;   // cutoff dcdrift corrupt rate
uniform vec4 uD;   // time seed corruptamp
shared float sP[3][16][16];
shared float sT[3][16][16];
shared float cY[16][16];
shared float cC[16][16];
const float QL[64] = float[64](16.,11.,10.,16.,24.,40.,51.,61., 12.,12.,14.,19.,26.,58.,60.,55.,
    14.,13.,16.,24.,40.,57.,69.,56., 14.,17.,22.,29.,51.,87.,80.,62., 18.,22.,37.,56.,68.,109.,103.,77.,
    24.,35.,55.,64.,81.,104.,113.,92., 49.,64.,78.,87.,103.,121.,120.,101., 72.,92.,95.,98.,112.,100.,103.,99.);
const float QC[64] = float[64](17.,18.,24.,47.,99.,99.,99.,99., 18.,21.,26.,66.,99.,99.,99.,99.,
    24.,26.,56.,99.,99.,99.,99.,99., 47.,66.,99.,99.,99.,99.,99.,99., 99.,99.,99.,99.,99.,99.,99.,99.,
    99.,99.,99.,99.,99.,99.,99.,99., 99.,99.,99.,99.,99.,99.,99.,99., 99.,99.,99.,99.,99.,99.,99.,99.);
const float PI = 3.14159265358979;
uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h(uvec4 k) { return float(pcg(k.x ^ pcg(k.y ^ pcg(k.z ^ pcg(k.w)))) >> 8) / 16777215.0; }
void main() {
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    ivec2 l = ivec2(gl_LocalInvocationID.xy);
    int N = uB.x < 6.0 ? 4 : (uB.x > 12.0 ? 16 : 8);
    bool c444 = uB.y > 0.5;
    int NC = c444 ? N : 8;
    int SC = c444 ? 16 : 8;
    uint seed = uint(uD.y) * 7919u;
    uint E = uint(floor(uD.x * uC.w));
    ivec2 g = ivec2(floor(vec2(h(uvec4(E, seed, 1u, 7u)), h(uvec4(E, seed, 2u, 7u))) * uB.w * 16.0));
    if (uA.x <= 0.0) g = ivec2(0);
    ivec2 mb = ivec2(gl_WorkGroupID.xy) * 16 - g;                               // macroblock origin (image px)
    ivec2 p = mb + l;
    bool inside = all(greaterThanEqual(p, ivec2(0))) && all(lessThan(p, isz));
    ivec2 pc = clamp(p, ivec2(0), isz - 1);
    vec4 c = texelFetch(sTD2DInputs[0], pc, 0);
    if (uA.x <= 0.0) { if (inside) TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    vec4 st = texelFetch(sTD2DInputs[2], ivec2(0), 0);
    bool fresh = st.x - st.y > 0.25;
    vec3 s = c.rgb;
    if (!fresh && uB.z > 0.0) s = mix(s, texelFetch(sTD2DInputs[1], pc, 0).rgb, uB.z);
    vec3 v = clamp(s, 0.0, 1.0) * 255.0;
    sP[0][l.y][l.x] = dot(v, vec3(0.299, 0.587, 0.114)) - 128.0;
    sP[1][l.y][l.x] = dot(v, vec3(-0.168736, -0.331264, 0.5));
    sP[2][l.y][l.x] = dot(v, vec3(0.5, -0.418688, -0.081312));
    if (l.x < N && l.y < N) cY[l.y][l.x] = cos(float(2 * l.x + 1) * float(l.y) * PI / float(2 * N))
                                           * sqrt((l.y == 0 ? 1.0 : 2.0) / float(N));
    if (l.x < NC && l.y < NC) cC[l.y][l.x] = cos(float(2 * l.x + 1) * float(l.y) * PI / float(2 * NC))
                                             * sqrt((l.y == 0 ? 1.0 : 2.0) / float(NC));
    barrier();
    if (!c444) {                                                                // 4:2:0: 2x2 average -> 8x8
        if (l.x < 8 && l.y < 8) {
            for (int k = 1; k < 3; k++) {
                ivec2 q = l * 2;
                sT[k][l.y][l.x] = 0.25 * (sP[k][q.y][q.x] + sP[k][q.y][q.x + 1] + sP[k][q.y + 1][q.x]
                                          + sP[k][q.y + 1][q.x + 1]);
            }
        }
        barrier();
        if (l.x < 8 && l.y < 8) { sP[1][l.y][l.x] = sT[1][l.y][l.x]; sP[2][l.y][l.x] = sT[2][l.y][l.x]; }
        barrier();
    }
    float qf = clamp(uA.y, 1.0, 100.0);
    float qs = qf < 50.0 ? 5000.0 / qf : 200.0 - 2.0 * qf;                     // IJG quality scaling
    // forward rows
    for (int k = 0; k < 3; k++) {
        int n = k == 0 ? N : NC; int S = k == 0 ? 16 : SC;
        if (l.x < S && l.y < S) {
            int bx = (l.x / n) * n; int u = l.x - bx; float acc = 0.0;
            for (int j = 0; j < 16; j++) { if (j >= n) break;
                acc += sP[k][l.y][bx + j] * (k == 0 ? cY[u][j] : cC[u][j]); }
            sT[k][l.y][l.x] = acc;
        }
    }
    barrier();
    // forward columns + quantise + damage
    for (int k = 0; k < 3; k++) {
        int n = k == 0 ? N : NC; int S = k == 0 ? 16 : SC;
        if (l.x < S && l.y < S) {
            int bx = (l.x / n) * n; int by = (l.y / n) * n; int u = l.x - bx; int w = l.y - by;
            float acc = 0.0;
            for (int j = 0; j < 16; j++) { if (j >= n) break;
                acc += sT[k][by + j][l.x] * (k == 0 ? cY[w][j] : cC[w][j]); }
            int ti = (w * 8 / n) * 8 + (u * 8 / n);
            float T = k == 0 ? QL[ti] : QC[ti];
            float qv = max(1.0, floor((T * qs + 50.0) / 100.0)) * uA.z * (k == 0 ? 1.0 : uA.w) * float(n) / 8.0;
            float F = round(acc / qv) * qv;
            int sc = (k == 0 || c444) ? 1 : 2;                                  // block key in image space
            uvec4 key = uvec4(uvec2(ivec2(gl_WorkGroupID.xy) * 16 + ivec2(bx, by) * sc), E, seed + uint(k) * 31u);
            if (uC.x > 0.0 && float(u + w) > (1.0 - uC.x) * float(2 * n - 2) + 1e-3) F = 0.0;
            if (u == 0 && w == 0) F += (h(key) - 0.5) * 2.0 * uC.y * float(n) * 64.0;
            if ((u + w) > 0 && h(uvec4(key.xy, key.z, seed + 5u)) < uC.z) {
                uvec4 ck = uvec4(key.xy, uint(u + w * 16), key.z + 9u);
                F = F * (h(ck) < 0.5 ? -1.0 : 1.0) + (h(ck ^ uvec4(3u)) - 0.5) * 2.0 * uD.z * qv;
            }
            sP[k][l.y][l.x] = F;
        }
    }
    barrier();
    // inverse columns
    for (int k = 0; k < 3; k++) {
        int n = k == 0 ? N : NC; int S = k == 0 ? 16 : SC;
        if (l.x < S && l.y < S) {
            int by = (l.y / n) * n; int y = l.y - by; float acc = 0.0;
            for (int j = 0; j < 16; j++) { if (j >= n) break;
                acc += sP[k][by + j][l.x] * (k == 0 ? cY[j][y] : cC[j][y]); }
            sT[k][l.y][l.x] = acc;
        }
    }
    barrier();
    // inverse rows
    for (int k = 0; k < 3; k++) {
        int n = k == 0 ? N : NC; int S = k == 0 ? 16 : SC;
        if (l.x < S && l.y < S) {
            int bx = (l.x / n) * n; int x = l.x - bx; float acc = 0.0;
            for (int j = 0; j < 16; j++) { if (j >= n) break;
                acc += sT[k][l.y][bx + j] * (k == 0 ? cY[j][x] : cC[j][x]); }
            sP[k][l.y][l.x] = acc;
        }
    }
    barrier();
    float Y = sP[0][l.y][l.x] + 128.0;
    float cb, cr;
    if (c444) { cb = sP[1][l.y][l.x]; cr = sP[2][l.y][l.x]; }
    else {                                                                      // bilinear up inside the macroblock
        vec2 q = clamp((vec2(l) + 0.5) * 0.5 - 0.5, vec2(0.0), vec2(7.0));
        ivec2 i0 = ivec2(floor(q)); ivec2 i1 = min(i0 + 1, ivec2(7)); vec2 f = q - vec2(i0);
        cb = mix(mix(sP[1][i0.y][i0.x], sP[1][i0.y][i1.x], f.x), mix(sP[1][i1.y][i0.x], sP[1][i1.y][i1.x], f.x), f.y);
        cr = mix(mix(sP[2][i0.y][i0.x], sP[2][i0.y][i1.x], f.x), mix(sP[2][i1.y][i0.x], sP[2][i1.y][i1.x], f.x), f.y);
    }
    vec3 rgb = vec3(Y + 1.402 * cr, Y - 0.344136 * cb - 0.714136 * cr, Y + 1.772 * cb) / 255.0;
    if (inside) TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(clamp(rgb, 0.0, 1.0), c.a), uA.x));
}
"""

STAMP = """// stamp: 1x1 rgba32float in place (T-111): x = now, y = the previous cook's now. Cooks only when fx does.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;
void main() {
    vec4 s = TDImageLoadOutput(0, ivec3(0));
    TDImageStoreOutput(0, ivec3(0), vec4(uT.x, s.x, 0.0, 1.0));
}
"""

P = "parent().par.{}.eval()"


def build(m, H):
    """Fill instance COMP m: in1 -> prev_src (+ fb) / stamp -> fx (one compute pass, manual dispatch) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    fb = mk(m, feedbackTOP, 'fb')
    fb.inputConnectors[0].connect(in1)
    fb.par.top = 'fx'
    fb.comment = 'Previous fx output (Generation only; cooks only while prev_src selects it).'
    prev = mk(m, switchTOP, 'prev_src')
    prev.inputConnectors[0].connect(in1)
    prev.inputConnectors[1].connect(fb)
    expr(prev.par.index, '1 if %s > 0 else 0' % P.format('Generation'))
    st = H['compute'](m, 'stamp', STAMP, [], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    H['uniforms'](st, [('uT', ['absTime.seconds', '0', '0', '0'])])
    st.comment = 'Cook clock: x now, y previous cook; a gap > 0.25 s = bypassed -> Generation history stale.'
    g = H['compute'](m, 'fx', SHADER, [in1, prev, st])
    g.par.autodispatchsize = False                    # one 16x16 group per macroblock + 1 for the grid shift
    expr(g.par.dispatchsizex, 'int(math.ceil(me.inputs[0].width / 16.0)) + 1')
    expr(g.par.dispatchsizey, 'int(math.ceil(me.inputs[0].height / 16.0)) + 1')
    g.par.dispatchsizez = 1
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), P.format('Quality'), P.format('Crush'), P.format('Chromaq')]),
        ('uB', ['float(parent().par.Blocksize.eval())', '1 if parent().par.Chroma.eval() == "444" else 0',
                P.format('Generation'), P.format('Gridshift')]),
        ('uC', [P.format('Cutoff'), P.format('Dcdrift'), P.format('Corrupt'), P.format('Rate')]),
        ('uD', ['absTime.seconds', P.format('Seed'), P.format('Corruptamp'), '0']),
    ])
    g.comment = 'dct: JPEG crush (DG-08): YCbCr 4:2:0, DCT 4/8/16, IJG quant, damage, IDCT; one pass. Amount 0 = exact.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 DCT', 'role': 'process', 'ops': ['fb', 'prev_src', 'stamp', 'stamp_compute', 'fx', 'fx_compute'],
         'body': 'One compute pass (16x16 macroblock per workgroup); fb + prev_src only for Generation.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
