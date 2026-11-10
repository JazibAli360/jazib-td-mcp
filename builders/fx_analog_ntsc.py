# fx_analog_ntsc - FX_analog module 'ntsc' (FX2 AV-10 composite encode/decode; AV-11 PAL-D / PAL-S as a mode).
# Template: docs/builds/fx_glitch.md "Module template" (the FX_analog rack = the FX_glitch rack, builders/fx_analog.py).
# Four compute passes (T-46/T-47), three of them at signal res (Samples x Lines, default 754 x 480 = 0.36 MP):
#   enc  picture -> per-sample box resample -> YIQ (YUV) -> C = I cos + Q sin (PAL: U sin +- V cos) on the subcarrier
#        (phase = cps*k + lineadv*line + frame phase: dot crawl) + noise -> composite / Y / C (rgba32float)
#   sep  Y/C separation: none (full cross-colour) / notch at fsc / comb 1H / comb 2H / S-Video (rgba32float)
#   dec  windowed-sinc FIR: Y (+ peaking = Y - wide Y), demodulate 2C cos/sin, I/Q (U/V) low-pass, PAL-D delay-line
#        average, hue/sat/phase error, matrix -> RGB at signal res (rgba16float)
#   up   back to the input size (horizontal linear, vertical nearest..bilinear by Lineblend), mix by Amount
# Amount 0 = `wet` Switch picks in1 (exact passthrough; the passes are not pulled). Maths + numpy reference:
# builders/fx_analog_ntsc_logic.py (copied into `ntsc_logic`; uniforms are expressions on it). ASCII only.
import os

MODULE = 'ntsc'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(_HERE, 'fx_analog_ntsc_logic.py')

PAGES = [
    ('NTSC', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Standard', 'Menu', 'ntsc', {'names': ['ntsc', 'pald', 'pals'],
                                      'labels': ['NTSC (YIQ, 3.58 MHz)', 'PAL-D (YUV 4.43 MHz, delay line)',
                                                 'PAL-S (simple, Hanover bars)']}),
        ('Separation', 'Menu', 'comb1', {'names': ['none', 'notch', 'comb1', 'comb2', 'svideo'],
                                         'labels': ['None (full cross-colour)', 'Notch (trap at fsc)',
                                                    'Comb 1H (2-line)', 'Comb 2H (3-line)', 'S-Video (Y/C apart)']}),
        ('Crawl', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Dot crawl speed (1 real, 0 frozen)'}),
        ('Hue', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Hue deg'}),
        ('Saturation', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Saturation'}),
        ('Phaseerr', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Chroma phase error deg'}),
        ('Peaking', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Peaking (sharpness overshoot)'}),
        ('Ringing', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Ringing (0 Gaussian, 0.5 sinc, 1 bare sinc)'}),
        ('Noise', 'Float', 0.0, {'min': 0, 'max': 0.3, 'label': 'Noise on the signal'}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Signal gain'}),
    ]),
    ('Signal', [
        ('Samples', 'Int', 754, {'min': 240, 'max': 1200, 'label': 'Samples per line (754 = 4 fsc)'}),
        ('Lines', 'Int', 480, {'min': 120, 'max': 1080, 'label': 'Lines'}),
        ('Subcarrier', 'Float', 1.0, {'min': 0.25, 'max': 2, 'label': 'Subcarrier x real'}),
        ('Ybw', 'Float', 4.2, {'min': 0.5, 'max': 7, 'label': 'Luma bandwidth MHz'}),
        ('Ibw', 'Float', 1.3, {'min': 0.1, 'max': 4, 'label': 'I / U bandwidth MHz'}),
        ('Qbw', 'Float', 0.5, {'min': 0.1, 'max': 4, 'label': 'Q / V bandwidth MHz'}),
        ('Lineblend', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Line blend (0 hard lines, 1 smooth)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['NTSC', 'Signal']

_N = {'Hue': 0.0, 'Saturation': 1.0, 'Phaseerr': 0.0, 'Peaking': 0.0, 'Ringing': 0.0, 'Noise': 0.0, 'Gain': 1.0,
      'Crawl': 1.0, 'Samples': 754, 'Lines': 480, 'Subcarrier': 1.0, 'Ybw': 4.2, 'Ibw': 1.3, 'Qbw': 0.5,
      'Lineblend': 1.0}
# menus as index: Standard ntsc 0 / pald 1 / pals 2; Separation none 0 / notch 1 / comb1 2 / comb2 3 / svideo 4
PRESETS = [
    (1, 'broadcast', dict(_N, Amount=1.0, Standard=0, Separation=3, Peaking=0.2, Seed=1)),
    (2, 'cheap tv', dict(_N, Amount=1.0, Standard=0, Separation=1, Ybw=3.0, Ibw=0.8, Qbw=0.4, Peaking=0.7,
                         Ringing=0.5, Noise=0.03, Saturation=1.2, Seed=2)),
    (3, 'dot crawl', dict(_N, Amount=1.0, Standard=0, Separation=0, Ybw=4.2, Saturation=1.3, Seed=3)),
    (4, 'console 80s', dict(_N, Amount=1.0, Standard=0, Separation=1, Samples=640, Lines=240, Crawl=0.0,
                            Peaking=0.4, Ringing=0.3, Lineblend=0.0, Seed=4)),
    (5, 'pal hanover', dict(_N, Amount=1.0, Standard=2, Separation=2, Samples=922, Lines=576, Ibw=1.3, Qbw=1.3,
                            Phaseerr=20.0, Seed=5)),
]

_HEAD = """layout (local_size_x = 8, local_size_y = 8) in;
const float PI = 3.14159265358979;
const float TAU = 6.28318530717959;
"""

ENC = """// FX_analog ntsc: enc (compute, T-47). in0 picture -> composite at signal res (r composite, g Y, b C).
""" + _HEAD + """uniform vec4 uS;   // ws lines cps lineadv
uniform vec4 uF;   // framephase frame seed noise
uniform vec4 uE;   // pal gain sep combd
uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h(uvec4 k) { return float(pcg(k.x ^ pcg(k.y ^ pcg(k.z ^ pcg(k.w)))) >> 8) / 16777215.0; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    int ws = int(uS.x); int L = int(uS.y);
    if (p.x >= ws || p.y >= L) return;
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    int x0 = (p.x * isz.x) / ws; int sx = max(1, ((p.x + 1) * isz.x) / ws - x0); int nx = min(sx, 4);
    int y0 = (p.y * isz.y) / L;  int sy = max(1, ((p.y + 1) * isz.y) / L - y0);  int ny = min(sy, 8);
    vec3 acc = vec3(0.0);
    for (int j = 0; j < 8; j++) {
        if (j >= ny) break;
        int yy = min(y0 + (j * sy) / ny, isz.y - 1);
        for (int i = 0; i < 4; i++) {
            if (i >= nx) break;
            acc += texelFetch(sTD2DInputs[0], ivec2(min(x0 + (i * sx) / nx, isz.x - 1), yy), 0).rgb;
        }
    }
    vec3 c = acc / float(nx * ny);
    float th = TAU * fract(uS.z * float(p.x) + uS.w * float(p.y) + uF.x);
    float Y = dot(c, vec3(0.299, 0.587, 0.114));
    float C;
    if (uE.x > 0.5) {                                                     // PAL: U sin + V cos, V switch per line
        float U = dot(c, vec3(-0.14713, -0.28886, 0.436));
        float V = dot(c, vec3(0.615, -0.51499, -0.10001));
        C = U * sin(th) + ((p.y & 1) == 1 ? -1.0 : 1.0) * V * cos(th);
    } else {                                                              // NTSC: I cos + Q sin
        float I = dot(c, vec3(0.595716, -0.274453, -0.321263));
        float Q = dot(c, vec3(0.211456, -0.522591, 0.311135));
        C = I * cos(th) + Q * sin(th);
    }
    float n1 = 0.0; float n2 = 0.0;
    if (uF.w > 0.0) {
        uint fr = uint(uF.y); uint sd = uint(uF.z) * 7919u; uint kx = uint(p.x); uint ky = uint(p.y);
        n1 = (h(uvec4(kx, ky, fr, sd)) + h(uvec4(kx, ky, fr, sd + 1u)) - 1.0) * uF.w;
        n2 = (h(uvec4(kx, ky, fr, sd + 2u)) + h(uvec4(kx, ky, fr, sd + 3u)) - 1.0) * uF.w;
    }
    float g = uE.y;
    TDImageStoreOutput(0, ivec3(p, 0), vec4((Y + C + n1) * g, (Y + n1) * g, (C + n2) * g, 1.0));
}
"""

SEP = """// FX_analog ntsc: sep (compute). in0 enc -> r Y, g C as the decoder's separator sees them.
""" + _HEAD + """uniform vec4 uS;   // ws lines cps lineadv
uniform vec4 uE;   // pal gain sep combd
float cmp(int k, int r, int ws) { return texelFetch(sTD2DInputs[0], ivec2(clamp(k, 0, ws - 1), r), 0).r; }
float at(float x, int r, int ws) { float fl = floor(x); int k0 = int(fl); float f = x - fl;
                                    return mix(cmp(k0, r, ws), cmp(k0 + 1, r, ws), f); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    int ws = int(uS.x); int L = int(uS.y);
    if (p.x >= ws || p.y >= L) return;
    vec4 e = texelFetch(sTD2DInputs[0], p, 0);
    int sep = int(uE.z + 0.5); int D = int(uE.w + 0.5);
    float Ys = e.r; float Cs = e.r;                                       // 0 none: Y and C both = composite
    if (sep == 1) {                                                       // notch: [1 2 1]/4 at half a subcarrier cycle
        float d = 0.5 / uS.z;
        Ys = (at(float(p.x) - d, p.y, ws) + 2.0 * e.r + at(float(p.x) + d, p.y, ws)) * 0.25;
        Cs = e.r - Ys;
    } else if (sep == 2 || sep == 3) {                                    // comb: C(line - D) = -C(line)
        int rm = p.y - D < 0 ? p.y + D : p.y - D; rm = clamp(rm, 0, L - 1);
        float cm = texelFetch(sTD2DInputs[0], ivec2(p.x, rm), 0).r;
        if (sep == 2) { Ys = (e.r + cm) * 0.5; Cs = (e.r - cm) * 0.5; }
        else {
            int rq = p.y + D > L - 1 ? p.y - D : p.y + D; rq = clamp(rq, 0, L - 1);
            Ys = (cm + 2.0 * e.r + texelFetch(sTD2DInputs[0], ivec2(p.x, rq), 0).r) * 0.25;
            Cs = e.r - Ys;
        }
    } else if (sep == 4) { Ys = e.g; Cs = e.b; }                          // S-Video
    TDImageStoreOutput(0, ivec3(p, 0), vec4(Ys, Cs, 0.0, 1.0));
}
"""

DEC = """// FX_analog ntsc: dec (compute). in0 sep -> RGB at signal res. One loop of up to 2*24+1 taps along the line.
// Perf (perf lane 2, 27 Oct): the 4 x 49 tap weights depend only on uniforms, so each 8x8 group fills them once into
// shared memory (KW); the subcarrier phase per tap advances by a fixed rotation (cos/sin once per pixel, not per tap).
""" + _HEAD + """uniform vec4 uS;   // ws lines cps lineadv
uniform vec4 uF;   // framephase frame seed noise
uniform vec4 uK;   // fcY fcYw fcI fcQ (cycles/sample)
uniform vec4 uR;   // rY rYw rI rQ (half-widths)
uniform vec4 uP;   // peaking ringing hue sat
uniform vec4 uQ;   // phaseerr pal pald R
shared vec4 KW[49];                                       // tap weights j = -24..24: Y, Ywide, I/U, Q/V
float kern(int j, float fc, int R, float ring) {          // ring 0 Gaussian, 0.5 windowed sinc, 1 bare sinc
    if (abs(j) > R) return 0.0;
    float x = float(j);
    float sg = 0.1874 / fc;
    float g = exp(-0.5 * x * x / (sg * sg));
    float a = PI * x / float(R + 1);
    float win = 0.42 + 0.5 * cos(a) + 0.08 * cos(2.0 * a);
    float sn = j == 0 ? 1.0 : sin(TAU * fc * x) / (TAU * fc * x);
    float ta = clamp(2.0 * ring, 0.0, 1.0); float tb = clamp(2.0 * ring - 1.0, 0.0, 1.0);
    float wsn = win * sn;
    return g + (wsn - g) * ta + (sn - wsn) * tb;
}
vec2 ph(int k, int r) {                                   // (cos, sin) of the demodulator phase at sample k, line r
    float th = TAU * fract(uS.z * float(k) + uS.w * float(r) + uF.x) + uQ.x;
    return vec2(cos(th), sin(th));
}
vec2 demod(float c, vec2 cs, int r) {
    if (uQ.y > 0.5) return vec2(2.0 * c * cs.y, 2.0 * c * cs.x * ((r & 1) == 1 ? -1.0 : 1.0));
    return vec2(2.0 * c * cs.x, 2.0 * c * cs.y);
}
void main() {
    int rY = int(uR.x + 0.5); int rYw = int(uR.y + 0.5); int rI = int(uR.z + 0.5); int rQ = int(uR.w + 0.5);
    uint li = gl_LocalInvocationIndex;
    if (li < 49u) {
        int jj = int(li) - 24;
        KW[li] = vec4(kern(jj, uK.x, rY, uP.y), kern(jj, uK.y, rYw, uP.y), kern(jj, uK.z, rI, uP.y),
                      kern(jj, uK.w, rQ, uP.y));
    }
    barrier();
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    int ws = int(uS.x); int L = int(uS.y);
    if (p.x >= ws || p.y >= L) return;
    int R = int(uQ.w + 0.5);
    bool pald = uQ.z > 0.5;
    int r2 = clamp(p.y - 1 < 0 ? p.y + 1 : p.y - 1, 0, L - 1);
    float st = TAU * fract(uS.z);
    vec2 rot = vec2(cos(st), sin(st));                    // one sample step of the subcarrier
    vec2 cs = ph(p.x - 24, p.y); vec2 cs2 = ph(p.x - 24, r2);
    vec4 acc = vec4(0.0); vec4 sw = vec4(0.0);                            // Y, Ywide, a (I/U), b (Q/V)
    for (int j = -24; j <= 24; j++) {
        int kk = p.x + j;
        if (j >= -R && j <= R && kk >= 0 && kk < ws) {                    // taps off the line are skipped
            vec2 yc = texelFetch(sTD2DInputs[0], ivec2(kk, p.y), 0).rg;
            vec4 w = KW[j + 24];
            vec2 ab = demod(yc.y, cs, p.y);
            if (pald) ab = 0.5 * (ab + demod(texelFetch(sTD2DInputs[0], ivec2(kk, r2), 0).g, cs2, r2));
            acc += w * vec4(yc.x, yc.x, ab);
            sw += w;
        }
        cs = vec2(cs.x * rot.x - cs.y * rot.y, cs.y * rot.x + cs.x * rot.y);
        cs2 = vec2(cs2.x * rot.x - cs2.y * rot.y, cs2.y * rot.x + cs2.x * rot.y);
    }
    float Y = (1.0 + uP.x) * acc.x / sw.x - uP.x * acc.y / sw.y;
    vec2 ab = acc.zw / sw.zw;
    float ch = cos(uP.z); float sh = sin(uP.z);
    ab = vec2(ab.x * ch - ab.y * sh, ab.x * sh + ab.y * ch) * uP.w;
    vec3 rgb;
    if (uQ.y > 0.5) rgb = vec3(Y + 1.139835 * ab.y, Y - 0.394646 * ab.x - 0.580594 * ab.y, Y + 2.032112 * ab.x);
    else rgb = vec3(Y + 0.956296 * ab.x + 0.621024 * ab.y, Y - 0.272122 * ab.x - 0.647381 * ab.y,
                    Y - 1.106989 * ab.x + 1.704615 * ab.y);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(rgb, 1.0));
}
"""

UP = """// FX_analog ntsc: up (compute). in0 picture (size + Amount mix), in1 dec -> out at the picture's size.
""" + _HEAD + """uniform vec4 uS;   // ws lines cps lineadv
uniform vec4 uU;   // amount lineblend
vec3 hrow(float u, int r, int ws) {
    float fl = floor(u); int k0 = int(fl); float f = u - fl;
    return mix(texelFetch(sTD2DInputs[1], ivec2(clamp(k0, 0, ws - 1), r), 0).rgb,
               texelFetch(sTD2DInputs[1], ivec2(clamp(k0 + 1, 0, ws - 1), r), 0).rgb, f);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= osz.x || p.y >= osz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    int ws = int(uS.x); int L = int(uS.y);
    float u = (float(p.x) + 0.5) * float(ws) / float(osz.x) - 0.5;
    float v = (float(p.y) + 0.5) * float(L) / float(osz.y);
    int rn = clamp(int(floor(v)), 0, L - 1);
    float vb = v - 0.5; float r0 = floor(vb); float fv = vb - r0;
    vec3 near = hrow(u, rn, ws);
    vec3 bil = mix(hrow(u, clamp(int(r0), 0, L - 1), ws), hrow(u, clamp(int(r0) + 1, 0, L - 1), ws), fv);
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(mix(near, bil, uU.y), c.a), uU.x));
}
"""

SHADERS = {'enc': ENC, 'sep': SEP, 'dec': DEC, 'up': UP}
# uniforms per pass (only what each shader declares)
PASS_UNIFORMS = {'enc': ['uS', 'uF', 'uE'], 'sep': ['uS', 'uE'], 'dec': ['uS', 'uF', 'uK', 'uR', 'uP', 'uQ'],
                 'up': ['uS', 'uU']}
U_EXPR = "op('ntsc_logic').module.UNI(parent())['{}'][{}]"
FPH_EXPR = "op('ntsc_logic').module.frame_phase(parent(), absTime.frame)"
FRAME_EXPR = 'absTime.frame % 16777216'


def uniform_exprs(name):
    """[(uniform, [x, y, z, w] expressions)] for pass `name`. Pure; tested offline."""
    out = []
    for u in PASS_UNIFORMS[name]:
        ex = [U_EXPR.format(u, i) for i in range(4)]
        if u == 'uF':
            ex[0], ex[1] = FPH_EXPR, FRAME_EXPR
        out.append((u, ex))
    return out


def build(m, H):
    """Fill instance COMP m: in1 -> enc -> sep -> dec -> up (+ in1) -> wet (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    lg = mk(m, textDAT, 'ntsc_logic')
    with open(LOGIC_FILE) as fh:
        lg.text = fh.read()
    lg.comment = 'Pure maths (builders/fx_analog_ntsc_logic.py): uniforms UNI(parent()), frame_phase, numpy reference.'
    enc = H['compute'](m, 'enc', ENC, [in1], res=(754, 480), fmt='rgba32float')
    expr(enc.par.resolutionw, 'int(parent().par.Samples.eval())')
    expr(enc.par.resolutionh, 'int(parent().par.Lines.eval())')
    enc.comment = 'enc: box resample -> YIQ/YUV -> composite on the subcarrier (r comp, g Y, b C), signal res.'
    sep = H['compute'](m, 'sep', SEP, [enc], fmt='rgba32float')
    sep.comment = 'sep: Y/C separation (none / notch / comb 1H / comb 2H / S-Video).'
    dec = H['compute'](m, 'dec', DEC, [sep], fmt='rgba16float')
    dec.comment = 'dec: FIR Y + peaking, demodulate, I/Q (U/V) low-pass, PAL-D average, hue/sat -> RGB.'
    up = H['compute'](m, 'up', UP, [in1, dec])
    up.comment = 'up: to the input size (Lineblend), mix by Amount.'
    for g, name in ((enc, 'enc'), (sep, 'sep'), (dec, 'dec'), (up, 'up')):
        H['uniforms'](g, uniform_exprs(name))
    wet = mk(m, switchTOP, 'wet')
    wet.inputConnectors[0].connect(in1)
    wet.inputConnectors[1].connect(up)
    expr(wet.par.index, '1 if parent().par.Amount.eval() > 0 else 0')
    wet.comment = 'Amount 0 -> in1 (exact passthrough, passes not pulled).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(wet)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'ntsc_logic']},
        {'title': '2 Encode', 'role': 'process', 'ops': ['enc', 'enc_compute'],
         'body': 'Picture -> composite signal at Samples x Lines (dot crawl = subcarrier phase per line/frame).'},
        {'title': '3 Decode', 'role': 'process', 'ops': ['sep', 'sep_compute', 'dec', 'dec_compute'],
         'body': 'Y/C separation, then FIR + demodulation back to RGB (cross-colour, ringing).'},
        {'title': '4 Out', 'role': 'output', 'ops': ['up', 'up_compute', 'wet', 'out1']},
    ]
