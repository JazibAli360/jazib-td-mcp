# fx_glitch_databend - FX_glitch module 'databend' (FX1 DG-25 data-bending in 1D, FX0 row 73): the picture as a raw
# byte stream (8-bit R G B per pixel, rows from the top like an image file, or columns, or planar R..G..B planes) put
# through audio-style effects, the way Audacity raw-import databenders do it, then written back in place:
#   echo (Repeats taps Delay bytes apart x Feedback^n: a delay that wraps into the next row = diagonal ghosts),
#   delay (one tap, Mix), lowpass (exponential FIR, Cutoff, <= Taps), highpass (byte - lowpass), crush (Bits),
#   hold (sample-rate reduction: every Hold bytes repeat the first), reverse (Chunk-byte blocks backwards),
#   wah (lowpass whose cutoff sweeps Rate cycles per 10000 bytes, Depth), reverb (4 comb taps, prime delays).
# ONE compute pass, every output byte gathers its taps independently (FIR forms, no serial scan), so it runs in
# parallel and the numpy mirror (fx_glitch_databend_logic.py) is exact in integer bytes. Drift scrolls Delay
# (bytes per second). Amount 0 = exact passthrough. No limits. Template: docs/builds/fx_glitch.md. ASCII only.

MODULE = 'databend'
EFFECTS = ['echo', 'delay', 'lowpass', 'highpass', 'crush', 'hold', 'reverse', 'wah', 'reverb']
ORDERS = ['rows', 'columns', 'planar']

PAGES = [
    ('Databend', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Effect', 'Menu', 'echo', {'names': EFFECTS, 'labels': ['Echo (feedback taps)', 'Delay (one tap)',
                                                                  'Low-pass', 'High-pass', 'Bit crush',
                                                                  'Sample hold', 'Reverse chunks', 'Wah sweep',
                                                                  'Reverb (4 combs)']}),
        ('Order', 'Menu', 'rows', {'names': ORDERS, 'labels': ['Rows (RGB interleaved)', 'Columns',
                                                               'Planar (R then G then B)']}),
        ('Delay', 'Int', 3000, {'min': 1, 'max': 100000, 'label': 'Delay bytes'}),
        ('Drift', 'Float', 0.0, {'min': -20000, 'max': 20000, 'label': 'Delay drift bytes/s'}),
        ('Feedback', 'Float', 0.6, {'min': 0, 'max': 1.2, 'label': 'Feedback'}),
        ('Repeats', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Echo repeats'}),
        ('Mix', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Wet mix'}),
        ('Cutoff', 'Float', 0.15, {'min': 0.001, 'max': 1, 'label': 'Cutoff (filter a)'}),
        ('Taps', 'Int', 12, {'min': 2, 'max': 32, 'label': 'Filter taps (cost ~ taps)'}),
        ('Bits', 'Int', 3, {'min': 1, 'max': 8, 'label': 'Crush bits'}),
        ('Hold', 'Int', 24, {'min': 1, 'max': 4096, 'label': 'Hold bytes'}),
        ('Chunk', 'Int', 600, {'min': 2, 'max': 100000, 'label': 'Reverse chunk bytes'}),
        ('Rate', 'Float', 3.0, {'min': 0, 'max': 50, 'label': 'Wah cycles / 10000 bytes'}),
        ('Depth', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Wah depth'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (reverb delays)'}),
    ]),
]
PANEL_PAGES = ['Databend']

_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl)
PRESETS = [
    (1, 'diagonal echo', dict(_D)),
    (2, 'tape smear', dict(_D, Effect=2, Cutoff=0.1, Taps=16, Mix=1.0, Order=1)),
    (3, 'edge buzz', dict(_D, Effect=3, Cutoff=0.3, Taps=8, Mix=1.0)),
    (4, 'reverse tape', dict(_D, Effect=6, Chunk=1440, Mix=1.0, Order=0)),
    (5, 'wah sweep', dict(_D, Effect=7, Rate=6.0, Depth=0.9, Taps=12, Mix=1.0, Drift=0.0)),
    (6, 'planar reverb', dict(_D, Effect=8, Order=2, Delay=1201, Feedback=0.5, Mix=0.7, Seed=6)),
    (7, 'crushed hold', dict(_D, Effect=5, Hold=48, Mix=1.0, Order=1)),
    (8, 'drifting ghost', dict(_D, Effect=0, Delay=9000, Drift=4000.0, Feedback=0.8, Repeats=6, Mix=0.7)),
]

SHADER = """// FX_glitch databend (compute, T-47; DG-25). in0 = picture (8-bit). Each output byte = f(byte stream).
// = fx_glitch_databend_logic.reference
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount effect order delay (incl. drift, whole bytes)
uniform vec4 uB;   // feedback repeats mix cutoff
uniform vec4 uC;   // taps bits hold chunk
uniform vec4 uD;   // rate depth seed -
ivec2 SZ;
int ORD;
int NB;            // stream length in bytes
ivec3 locate(int k) {                                     // byte index -> (x, y TD, channel)
    int W = SZ.x, H = SZ.y;
    if (ORD == 2) { int ch = k / (W * H); int r = k - ch * W * H; int row = r / W; return ivec3(r - row * W, H - 1 - row, ch); }
    int px = k / 3, ch = k - px * 3;
    if (ORD == 1) { int col = px / H; int row = px - col * H; return ivec3(col, H - 1 - row, ch); }
    int row = px / W; return ivec3(px - row * W, H - 1 - row, ch);
}
int index(ivec2 p, int ch) {                              // (x, y TD, channel) -> byte index
    int W = SZ.x, H = SZ.y, row = H - 1 - p.y;
    if (ORD == 2) return ch * W * H + row * W + p.x;
    if (ORD == 1) return (p.x * H + row) * 3 + ch;
    return (row * W + p.x) * 3 + ch;
}
float B(int k) {                                          // byte k in 0..255 (0 outside the stream = silence)
    if (k < 0 || k >= NB) return 0.0;
    ivec3 q = locate(k);
    return floor(texelFetch(sTD2DInputs[0], q.xy, 0)[q.z] * 255.0 + 0.5);
}
float lowpass(int k, float a, int taps) {                 // slow exact form (planar plane starts only)
    float s = 0.0, w = 0.0, g = a;
    for (int m = 0; m < 32; m++) {
        if (m >= taps) break;
        s += g * B(k - m); w += g; g *= 1.0 - a;
    }
    return s / max(w, 1e-6);
}
vec3 bytes(int P) {                                       // the 3 bytes of stream pixel P (rows / columns order)
    if (P < 0) return vec3(0.0);
    int W = SZ.x, H = SZ.y;
    ivec2 q;
    if (ORD == 1) { int col = P / H; q = ivec2(col, H - 1 - (P - col * H)); }
    else { int r = P / W; q = ivec2(P - r * W, H - 1 - r); }
    return floor(texelFetch(sTD2DInputs[0], q, 0).rgb * 255.0 + 0.5);
}
vec3 lp3(ivec2 p, vec3 a, int taps) {                     // all 3 channels' low-pass, each pixel fetched once
    int W = SZ.x, H = SZ.y, row = H - 1 - p.y;
    vec3 s = vec3(0.0), w = vec3(0.0);
    if (ORD == 2) {
        int P0 = row * W + p.x;
        if (P0 < taps) return vec3(lowpass(index(p, 0), a.x, taps), lowpass(index(p, 1), a.y, taps),
                                   lowpass(index(p, 2), a.z, taps));
        vec3 g = a;
        for (int m = 0; m < 32; m++) {
            if (m >= taps) break;
            int P = P0 - m; int r = P / W;
            vec3 b = floor(texelFetch(sTD2DInputs[0], ivec2(P - r * W, H - 1 - r), 0).rgb * 255.0 + 0.5);
            s += g * b; w += g; g *= 1.0 - a;
        }
        return s / max(w, vec3(1e-6));
    }
    int P0 = ORD == 1 ? p.x * H + row : row * W + p.x;
    int np = (taps + 2) / 3 + 1;
    for (int d = 0; d < 13; d++) {
        if (d >= np) break;
        vec3 b = bytes(P0 - d);
        for (int cp = 0; cp < 3; cp++) {
            for (int ch = 0; ch < 3; ch++) {
                int m = 3 * d + ch - cp;                  // byte distance from channel ch's output byte
                if (m < 0 || m >= taps) continue;
                float g = a[ch] * pow(1.0 - a[ch], float(m));
                s[ch] += g * b[cp]; w[ch] += g;
            }
        }
    }
    return s / max(w, vec3(1e-6));
}
float bend(int k, float x, float lp) {
    int ef = int(uA.y + 0.5);
    int D = max(int(uA.w), 1);
    if (ef == 0) {                                        // echo
        float s = x, g = 1.0;
        int R = int(uB.y + 0.5);
        for (int n = 1; n <= 8; n++) { if (n > R) break; g *= uB.x; s += g * B(k - n * D); }
        return mix(x, s, uB.z);
    }
    if (ef == 1) return mix(x, B(k - D), uB.z);
    if (ef == 2) return mix(x, lp, uB.z);
    if (ef == 3) return mix(x, clamp(x - lp + 128.0, 0.0, 255.0), uB.z);
    if (ef == 4) { float st = exp2(8.0 - floor(uC.y + 0.5)); return mix(x, floor(x / st) * st, uB.z); }
    if (ef == 5) { int h = max(int(uC.z + 0.5), 1); return mix(x, B((k / h) * h), uB.z); }
    if (ef == 6) { int c = max(int(uC.w + 0.5), 2); int b = (k / c) * c; return mix(x, B(b + c - 1 - (k - b)), uB.z); }
    if (ef == 7) return mix(x, lp, uB.z);                 // wah: lp with the swept cutoff (main)
    // reverb: 4 comb taps at D x (1, 1.37, 1.71, 2.13) (+ seed), gains Feedback^n
    float s = x, g = 1.0;
    float m4[4] = float[4](1.0, 1.37, 1.71, 2.13);
    for (int n = 0; n < 4; n++) {
        g *= uB.x;
        s += g * B(k - int(float(D) * m4[n]) - n * int(uD.z));
    }
    return mix(x, s / (1.0 + uB.x), uB.z);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    SZ = textureSize(sTD2DInputs[0], 0);
    if (p.x >= SZ.x || p.y >= SZ.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    ORD = int(uA.z + 0.5);
    NB = SZ.x * SZ.y * 3;
    int ef = int(uA.y + 0.5);
    vec3 lp = vec3(0.0);
    if (ef == 2 || ef == 3 || ef == 7) {
        vec3 a = vec3(uB.w);
        if (ef == 7) for (int ch = 0; ch < 3; ch++)
            a[ch] = max(uB.w * (1.0 - uD.y * (0.5 + 0.5 * sin(6.2831853 * uD.x * float(index(p, ch)) / 10000.0))), 0.001);
        lp = lp3(p, a, int(uC.x + 0.5));
    }
    vec3 o;
    for (int ch = 0; ch < 3; ch++) {
        int k = index(p, ch);
        o[ch] = floor(clamp(bend(k, floor(c[ch] * 255.0 + 0.5), lp[ch]), 0.0, 255.0) + 0.5) / 255.0;
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(mix(c.rgb, o, uA.x), c.a));
}
"""

P = "parent().par.{}.eval()"


def uniforms():
    dly = "max(1, int(%s + %s * absTime.seconds))" % (P.format('Delay'), P.format('Drift'))
    return [('uA', [P.format('Amount'), 'parent().par.Effect.menuIndex', 'parent().par.Order.menuIndex', dly]),
            ('uB', [P.format('Feedback'), P.format('Repeats'), P.format('Mix'), P.format('Cutoff')]),
            ('uC', [P.format('Taps'), P.format('Bits'), P.format('Hold'), P.format('Chunk')]),
            ('uD', [P.format('Rate'), P.format('Depth'), P.format('Seed'), '0'])]


def build(m, H):
    """in1 -> fx (one compute pass) -> out1."""
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', SHADER, [in1])
    H['uniforms'](g, uniforms())
    g.comment = 'databend: the picture as a byte stream through echo / filters / crush / hold / reverse / wah / reverb.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Databend', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One pass: every output byte gathers its stream taps (FIR forms, parallel).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
