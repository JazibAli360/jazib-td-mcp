# fx_analog_vhs - FX_analog module 'vhs' (FX2 AV-17 VHS tape; FX0 row 13; DG-23 / G-VHS). The TD twin of StageLab's
# JZB_Lofi_VHS (stagelab/ffgl/vhs/VHS.cpp v2, read-only): the same control names, ranges, defaults and recipes, so a
# look moves between Arena and TD. Template: docs/builds/fx_glitch.md "Module template" (rack = builders/fx_analog.py).
# Three compute passes (T-46/T-47), two of them at the tape's virtual raster (Lines follow the picture height, whole px
# per line >= 3; 1080x1920 at 480 lines = 203 x 480 samples):
#   enc  per virtual sample a tx x ty point average, RGB -> YIQ (rgba16float)
#   sig  luma: (Generations + tape speed) x [1 2 1] low-pass + one-sided Sharpen ring; colour-under chroma: delayed
#        right by Chroma Shift and smeared right by Generations cascaded one-sided exponential filters (negative
#        binomial kernel, 24 taps): colour never smears left (rgba16float)
#   fx   output size: tape wobble + line jitter + flagging (top lines bend), tracking band + snow, Glitch burst band,
#        head-switch tear (bottom lines), Interlace (odd lines from the previous signal frame, stale-safe via `stamp`),
#        noise / dropouts (+ compensation) stepped <= 24 Hz, scanlines (one virtual line period), Saturation / Warmth,
#        Amount mix. format useinput.
# Amount 0 with no Glitch burst running = `out_sel` picks in1 (exact passthrough; nothing else cooks). Glitch works at
# any Amount (as in Arena). Maths + numpy reference: builders/fx_analog_signal_logic.py. Doc + LIVE CHECKS:
# docs/builds/fx_analog_vhs.md. ASCII only.
import os

MODULE = 'vhs'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
_LG = dict(globals())                    # TD names (parameterexecuteDAT, ...) for the helpers that build ops
with open(os.path.join(_HERE, 'fx_analog_signal_logic.py')) as _fh:
    exec(_fh.read(), _LG)

PAGES = [
    ('VHS', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Bleed', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Bleed'}),
        ('Wobble', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Wobble'}),
        ('Tracking', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Tracking'}),
        ('Glitch', 'Pulse', None, {'label': 'Glitch'}),
    ]),
    ('Signal', [
        ('Lines', 'Menu', '480', {'names': _LG['VHS_LINES'], 'labels': ['240', '480', '576']}),
        ('Sharpen', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Sharpen'}),
        ('Chromashift', 'Float', 1.5, {'min': 0, 'max': 8, 'label': 'Chroma Shift'}),
        ('Noise', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Noise'}),
        ('Dropouts', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Dropouts'}),
        ('Tapespeed', 'Menu', 'sp', {'names': _LG['TAPE_SPEEDS'], 'labels': ['SP (standard)', 'LP (long play)',
                                                                            'EP (extended)']}),
        ('Generations', 'Int', 1, {'min': 1, 'max': _LG['VHS_MAX_GENS'], 'label': 'Generations (dubs)'}),
        ('Flagging', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Flagging (top lines bend)'}),
        ('Dropcomp', 'Toggle', False, {'label': 'Dropout compensation'}),
    ]),
    ('Look', [
        ('Scanlines', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Scanlines'}),
        ('Saturation', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Saturation'}),
        ('Warmth', 'Float', 0.2, {'min': -1, 'max': 1, 'label': 'Warmth'}),
        ('Headswitch', 'Toggle', True, {'label': 'Head Switch'}),
        ('Headlines', 'Int', 6, {'min': 1, 'max': 12, 'label': 'Head switch lines'}),
        ('Interlace', 'Toggle', False, {'label': 'Interlace'}),
        _LG['AXIS_PAR'],
    ]),
    ('Random', [
        ('Seed', 'Int', 1, {'min': 0, 'max': 99, 'label': 'Seed'}),
        ('Randomness', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Randomness'}),
    ]),
    ('State', [
        ('Glitchtime', 'Float', -1000.0, {'min': -1, 'max': 1, 'label': 'Last Glitch (absTime s)'}),
        ('Glitchcount', 'Int', 0, {'min': 0, 'max': 100, 'label': 'Glitch presses'}),
    ]),
]
PANEL_PAGES = ['VHS', 'Signal', 'Look', 'Random']

# StageLab's own recipes (presets/JZB_Lofi_VHS.yaml) on top of the StageLab defaults, plus TD-only tapes.
# Menus as index (Lines 0 = 240, 1 = 480, 2 = 576; Tapespeed 0 SP / 1 LP / 2 EP), toggles 0/1.
_BASE = {'Amount': 1.0, 'Bleed': 0.5, 'Wobble': 0.3, 'Tracking': 0.2, 'Lines': 1, 'Sharpen': 0.3, 'Chromashift': 1.5,
         'Noise': 0.25, 'Dropouts': 0.2, 'Scanlines': 0.3, 'Saturation': 0.8, 'Warmth': 0.2, 'Headswitch': 1,
         'Interlace': 0, 'Tapespeed': 0, 'Generations': 1, 'Flagging': 0.0, 'Dropcomp': 0, 'Headlines': 6}
PRESETS = [
    (1, 'home video', dict(_BASE, Amount=0.7, Bleed=0.5, Wobble=0.2, Tracking=0.1, Noise=0.2, Dropouts=0.1)),
    (2, 'worn tape', dict(_BASE, Amount=1.0, Bleed=0.8, Wobble=0.6, Tracking=0.5, Lines=0, Noise=0.5, Dropouts=0.6,
                          Saturation=0.6, Flagging=0.3)),
    (3, 'clean retro', dict(_BASE, Amount=0.6, Bleed=0.3, Wobble=0.05, Tracking=0.0, Noise=0.1, Dropouts=0.0,
                            Scanlines=0.5, Headswitch=0)),
    (4, 'breakdown', dict(_BASE, Amount=1.0, Bleed=1.0, Wobble=1.0, Tracking=1.0, Chromashift=5.0, Noise=0.8,
                          Dropouts=1.0, Interlace=1, Flagging=0.8)),
    (5, 'fresh rental', dict(_BASE, Amount=0.5, Bleed=0.3, Wobble=0.1, Tracking=0.0, Noise=0.1, Dropouts=0.03,
                             Sharpen=0.45, Saturation=0.9)),
    (6, 'lp bootleg', dict(_BASE, Amount=1.0, Tapespeed=2, Generations=3, Bleed=0.7, Chromashift=3.0, Wobble=0.5,
                           Tracking=0.3, Lines=0, Noise=0.5, Dropouts=0.4, Dropcomp=1, Saturation=0.6, Flagging=0.5,
                           Warmth=0.35)),
    (7, 'clean tape', dict(_BASE, Amount=1.0, Wobble=0.0, Tracking=0.0, Noise=0.0, Dropouts=0.0, Headswitch=0,
                           Interlace=0, Flagging=0.0)),          # deterministic: = ref_vhs_clean (LIVE CHECK V3)
]

ENC = """// FX_analog vhs enc (compute, T-47). in0 = picture -> virtual raster in tape coords (x = sample along the line,
// y = line from the bottom): per virtual sample the average of tx x ty texelFetch points, RGB -> YIQ.
// Mirror: fx_analog_signal_logic.ref_vhs_encode.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uR;   // pitch (px per line), taps x, taps y, line axis (0 x, 1 y)
""" + _LG['GLSL_LIB'] + """
void main() {
    ivec2 o = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (o.x >= osz.x || o.y >= osz.y) return;
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    bool ay = uR.w > 0.5;
    ivec2 T = tdims(isz, ay);
    float x0 = float(o.x) * float(T.x) / float(osz.x);
    float x1 = float(o.x + 1) * float(T.x) / float(osz.x);
    float y0 = float(o.y) * uR.x;
    float y1 = min(float(o.y + 1) * uR.x, float(T.y));
    int tx = int(uR.y + 0.5);
    int ty = int(uR.z + 0.5);
    vec4 s = vec4(0.0);
    for (int j = 0; j < 4; j++) {
        if (j >= ty) break;
        for (int i = 0; i < 8; i++) {
            if (i >= tx) break;
            ivec2 q = ivec2(floor(vec2(x0 + (float(i) + 0.5) / float(tx) * (x1 - x0),
                                       y0 + (float(j) + 0.5) / float(ty) * (y1 - y0))));
            q = clamp(q, ivec2(0), T - 1);
            s += texelFetch(sTD2DInputs[0], to_pix(q, isz, ay), 0);
        }
    }
    s /= float(tx * ty);
    vec3 c = clamp(s.rgb, 0.0, 1.0);
    TDImageStoreOutput(0, ivec3(o, 0), vec4(dot(c, vec3(0.299, 0.587, 0.114)), dot(c, vec3(0.595716, -0.274453, -0.321263)),
                                            dot(c, vec3(0.211456, -0.522591, 0.311135)), s.a));
}
"""

SIG = """// FX_analog vhs sig (compute, virtual raster). Luma: n x [1 2 1]/4 (binomial C(2n,j)/4^n) + one-sided Sharpen
// ring (halo right of rising edges). Chroma (colour-under): delayed right by `shift` samples, smeared right by `gens`
// cascaded one-sided exponential filters = negative binomial C(k+g-1, g-1) r^k, 24 taps (only samples at or left of
// x contribute). Mirror: fx_analog_signal_logic.ref_vhs_signal.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS;   // sharpen, chroma shift total (samples), tau (samples), generations
uniform vec4 uP;   // luma passes
vec4 E(int x, int y, int w) { return texelFetch(sTD2DInputs[0], ivec2(clamp(x, 0, w - 1), y), 0); }
void main() {
    ivec2 o = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = textureSize(sTD2DInputs[0], 0);
    if (o.x >= sz.x || o.y >= sz.y) return;
    int w = sz.x; int x = o.x; int y = o.y;
    vec4 own = E(x, y, w);
    int n = int(clamp(uP.x + 0.5, 1.0, 7.0));
    float norm = 1.0 / pow(4.0, float(n));
    float c = 1.0;
    float yl = 0.0;
    for (int j = 0; j <= 14; j++) {
        if (j > 2 * n) break;
        yl += c * norm * E(x - n + j, y, w).r;
        c = c * float(2 * n - j) / float(j + 1);
    }
    float left = 0.5 * (E(x - 1, y, w).r + E(x - 2, y, w).r);
    float ys = yl + uS.x * 1.5 * (yl - left);
    float r = exp(-1.0 / max(uS.z, 1e-6));
    int g = int(max(uS.w + 0.5, 1.0));
    float wk = 1.0;
    float ws = 0.0;
    vec2 acc = vec2(0.0);
    for (int k = 0; k < 24; k++) {
        if (k > 0) wk *= r * float(k + g - 1) / float(k);
        float sx = float(x) - uS.y - float(k);
        float f0 = floor(sx);
        float fr = sx - f0;
        acc += wk * mix(E(int(f0), y, w).gb, E(int(f0) + 1, y, w).gb, fr);
        ws += wk;
    }
    TDImageStoreOutput(0, ivec3(o, 0), vec4(ys, acc / ws, own.a));
}
"""

FX = """// FX_analog vhs fx (compute, output = input size, format useinput). in0 picture, in1 sig (this frame), in2 sig of
// the previous frame (Interlace) or sig, in3 stamp (x now, y previous cook: a gap > 0.25 s = stale history).
// StageLab VHS.cpp compositeShader + flagging, tape speed, generations, dropout compensation, line axis.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, wobble, noise, dropouts
uniform vec4 uB;   // scanlines, saturation (x generation loss), warmth, head-switch lines (0 off)
uniform vec4 uC;   // tracking, randomness, seed, interlace
uniform vec4 uD;   // t (s), noise step (<= 24 Hz), seconds since Glitch, Glitch presses
uniform vec4 uE;   // pitch, line axis, flagging, dropout compensation
uniform vec4 uF;   // noise x (tape speed), jitter x (tape speed)
""" + _LG['GLSL_LIB'] + """
vec4 S1(float sx, int ln, int w) {        // sig at virtual sample position sx (centres at k + 0.5), line ln
    float q = sx - 0.5; float f0 = floor(q); float fr = q - f0; int i0 = int(f0);
    return mix(texelFetch(sTD2DInputs[1], ivec2(clamp(i0, 0, w - 1), ln), 0),
               texelFetch(sTD2DInputs[1], ivec2(clamp(i0 + 1, 0, w - 1), ln), 0), fr);
}
vec4 S2(float sx, int ln, int w) {
    float q = sx - 0.5; float f0 = floor(q); float fr = q - f0; int i0 = int(f0);
    return mix(texelFetch(sTD2DInputs[2], ivec2(clamp(i0, 0, w - 1), ln), 0),
               texelFetch(sTD2DInputs[2], ivec2(clamp(i0 + 1, 0, w - 1), ln), 0), fr);
}
vec3 dec(vec4 e, float sat, float warm) {
    float Y = e.r * 0.94 + 0.04;                                 // lifted blacks
    vec2 iq = e.gb * sat + vec2(warm * 0.08, 0.0);               // I axis = orange / cyan
    return clamp(vec3(Y + 0.9563 * iq.x + 0.6210 * iq.y, Y - 0.2721 * iq.x - 0.6474 * iq.y,
                      Y - 1.1070 * iq.x + 1.7046 * iq.y), 0.0, 1.0);
}
// Perf (perf lane 2, 27 Oct): everything per tape row (wobble, jitter, flagging, tracking / Glitch band, head switch,
// dropout pick) and the noise lattice hashes are computed once per 8x8 group by a few lanes into shared memory instead
// of by every pixel; same maths and values (pixels outside the 4x4 lattice block fall back to hashing).
shared vec4 sR[8];       // per tape row of the group: off, ts (band), gm (Glitch band), hs (head switch)
shared vec4 sD[8];       // per tape row: dropout hit (0/1), x0, len, -
shared vec3 sN[16];      // noise lattice hh(i, sd + 17 / 19 / 23), 4 x 4 from sO
shared ivec2 sO;
vec3 vn2x3(vec2 x, uint sd) {
    ivec2 i = ivec2(floor(x)); vec2 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    ivec2 r = i - sO;
    vec3 a; vec3 b; vec3 c; vec3 d;
    if (r.x >= 0 && r.y >= 0 && r.x < 3 && r.y < 3) {
        int k = r.y * 4 + r.x;
        a = sN[k]; b = sN[k + 1]; c = sN[k + 4]; d = sN[k + 5];
    } else {
        a = vec3(hh(i, sd + 17u), hh(i, sd + 19u), hh(i, sd + 23u));
        b = vec3(hh(i + ivec2(1, 0), sd + 17u), hh(i + ivec2(1, 0), sd + 19u), hh(i + ivec2(1, 0), sd + 23u));
        c = vec3(hh(i + ivec2(0, 1), sd + 17u), hh(i + ivec2(0, 1), sd + 19u), hh(i + ivec2(0, 1), sd + 23u));
        d = vec3(hh(i + ivec2(1, 1), sd + 17u), hh(i + ivec2(1, 1), sd + 19u), hh(i + ivec2(1, 1), sd + 23u));
    }
    return vec3(mix(mix(a.x, b.x, f.x), mix(c.x, d.x, f.x), f.y), mix(mix(a.y, b.y, f.x), mix(c.y, d.y, f.x), f.y),
                mix(mix(a.z, b.z, f.x), mix(c.z, d.z, f.x), f.y));
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    float A = uA.x;
    float since = uD.z;
    float g = since >= 0.0 ? exp(-since / 0.4) : 0.0;
    if (g < 0.01) g = 0.0;
    bool ay = uE.y > 0.5;
    ivec2 T = tdims(isz, ay);
    ivec2 vsz = textureSize(sTD2DInputs[1], 0);
    float pitch = max(uE.x, 1.0);
    uint seedI = uint(max(uC.z, 0.0) + 0.5);
    uint sd = pcg(seedI + 0x9e37u);
    int st = int(uD.y);
    float t = uD.x;
    float rnd = clamp(uC.y, 0.0, 1.0);
    float na = uA.z * A * uF.x;
    ivec2 g0 = ivec2(gl_WorkGroupID.xy) * 8;
    int li = int(gl_LocalInvocationIndex);
    if (li < 8) {                                                // lanes 0-7: the group's 8 tape rows
        int ty = (ay ? g0.x : g0.y) + li;
        int line = int(floor(float(ty) / pitch));                // 0 = bottom line
        float v = (float(ty) + 0.5) / float(T.y);
        float off = 0.0;
        float wob = uA.y * A * uF.y;
        off += wob * 2.5 * (vn2(vec2(float(line) * 0.02, t * 0.6), sd) * 2.0 - 1.0);   // tape wobble, smooth
        off += wob * (hh(ivec2(line, st), sd + 11u) * 2.0 - 1.0);                        // line jitter <= 1 sample
        float fl = smoothstep(0.86, 1.0, v);
        off += uE.z * A * 12.0 * fl * fl * (0.6 + 0.4 * vn1(t * 1.3, sd + 2u));           // flagging: top lines bend
        float ph = h01(seedI, 0x5eedu);                                                   // tracking band (StageLab)
        float bloop = 0.5 + 0.42 * sin(6.2831853 * (t / 9.0 + ph));
        float wander = 0.5 + 0.45 * (vn1(t * 0.15, seedI * 31u + 7u) * 2.0 - 1.0);
        float flutter = vn1(t * 0.5, seedI * 31u + 11u) * 2.0 - 1.0;
        float bpos = mix(bloop, wander, rnd);
        float bh = 0.05 * (1.0 + 0.6 * rnd * flutter);
        float bs = clamp(uC.x, 0.0, 1.0) * A * (1.0 - 0.4 * rnd * (0.5 + 0.5 * flutter));
        float gn = uD.w;                                                                  // Glitch band
        float gl = 0.15 + 0.7 * mod(ph + 0.381966 * gn, 1.0);
        float gr = 0.1 + 0.8 * h01(uint(gn), seedI * 104729u + 3u);
        float gpos = mix(gl, gr, rnd) + (1.0 - g) * 0.08;
        float gh = 0.08 + 0.1 * g;
        float tm = bs * (1.0 - smoothstep(0.5, 1.0, abs(v - bpos) / max(bh, 1e-4)));
        float gm = g * (1.0 - smoothstep(0.5, 1.0, abs(v - gpos) / max(gh, 1e-4)));
        float ts = max(tm, gm);
        off += ts * (6.0 + 14.0 * (vn2(vec2(float(line) * 0.3, float(st) * 0.7), sd + 3u) * 2.0 - 1.0));
        float hsl = uB.w;
        float hs = 0.0;
        if (hsl >= 1.0 && float(line) < hsl) hs = A * (hsl - float(line)) / hsl;        // head switch, bottom lines
        off += hs * (10.0 + 8.0 * hh(ivec2(line, st), sd + 5u));
        sR[li] = vec4(off, ts, gm, hs);
        float da = uA.w * A;
        uint nst = uint(max(uD.y, 0.0));
        uint dstep = (rnd > 0.0 && h01(nst, seedI * 7919u + 17u) < rnd) ? 48u + nst : nst % 48u;
        bool hit = da > 0.0 && hh(ivec2(line, int(dstep)), sd + 29u) < da * 0.05;          // dropouts
        sD[li] = hit ? vec4(1.0, hh(ivec2(line, int(dstep)), sd + 31u),
                            0.01 + 0.06 * hh(ivec2(line, int(dstep)), sd + 37u), 0.0) : vec4(0.0);
    } else if (li >= 32 && li < 48 && na > 0.0) {                // lanes 32-47: the noise lattice block
        int txm = ay ? isz.y - 1 - min(g0.y + 7, isz.y - 1) : g0.x;      // smallest tape x / y in the group
        int tym = ay ? g0.x : g0.y;
        float xm = (float(txm) + 0.5) / float(T.x) * float(vsz.x);
        int lm = int(floor(float(tym) / pitch));
        ivec2 o = ivec2(floor(vec2(xm / 24.0, float(lm) / 4.0 + float(st) * 5.3)));
        if (li == 32) sO = o;
        ivec2 i = o + ivec2((li - 32) & 3, (li - 32) >> 2);
        sN[li - 32] = vec3(hh(i, sd + 17u), hh(i, sd + 19u), hh(i, sd + 23u));
    }
    barrier();
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    if (A <= 0.0 && g <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c0); return; }   // exact passthrough
    ivec2 tp = to_tape(p, isz, ay);
    int line = int(floor(float(tp.y) / pitch));                  // 0 = bottom line
    int ln = clamp(line, 0, vsz.y - 1);
    float u = (float(tp.x) + 0.5) / float(T.x);
    float xv = u * float(vsz.x);
    int rI = ay ? int(gl_LocalInvocationID.x) : int(gl_LocalInvocationID.y);
    vec4 rw = sR[rI];
    float off = rw.x; float ts = rw.y; float gm = rw.z; float hs = rw.w;
    float sx = xv - off;
    bool inside = sx >= 0.0 && sx <= float(vsz.x);
    vec4 ck = texelFetch(sTD2DInputs[3], ivec2(0), 0);
    bool fresh = ck.x - ck.y > 0.25;
    bool prevl = uC.w > 0.5 && (line & 1) == 1 && !fresh;
    vec4 col = vec4(0.0, 0.0, 0.0, c0.a);
    if (inside) {
        vec4 e = prevl ? S2(sx, ln, vsz.x) : S1(sx, ln, vsz.x);
        int sp = clamp(int(floor(sx / float(vsz.x) * float(T.x))), 0, T.x - 1);
        vec4 inp = texelFetch(sTD2DInputs[0], to_pix(ivec2(sp, tp.y), isz, ay), 0);
        col.rgb = mix(inp.rgb, dec(e, uB.y, uB.z), max(A, gm));
    }
    if (ts > 0.02) {                                                                       // band snow streaks
        float sn = vn2(vec2(xv / 10.0, float(line) * 1.7 + float(st) * 31.0), sd + 7u);
        float thr = 1.0 - ts * 0.3;
        col.rgb = mix(col.rgb, vec3(0.9), smoothstep(thr, thr + 0.04, sn) * 0.9);
    }
    if (hs > 0.0) col.rgb += hs * 0.3 * (hh(ivec2(int(xv / 2.0), line + st * 977), sd + 41u) - 0.5);
    if (na > 0.0) {                                                                        // streaky grain + blotches
        float n1 = hh(ivec2(int(xv / 2.0), line + st * 977), sd + 13u) - 0.5;
        vec2 q = vec2(xv / 24.0, float(line) / 4.0 + float(st) * 5.3);
        vec3 cn = vn2x3(q, sd) - 0.5;
        col.rgb += (vec3(n1 * 0.25) + cn * 0.15) * na;
    }
    vec4 dr = sD[rI];
    if (dr.x > 0.5) {                                                                      // dropouts
        float u0 = u - dr.y;
        if (u0 >= 0.0 && u0 < dr.z) {
            if (uE.w > 0.5) col.rgb = dec(S1(sx, clamp(ln + 1, 0, vsz.y - 1), vsz.x), uB.y, uB.z);  // line above
            else col.rgb = mix(col.rgb, vec3(1.0), 0.85);
        }
    }
    float f = 0.5 - 0.5 * cos(6.2831853 * fract((float(tp.y) + 0.5) / pitch));            // scanlines
    col.rgb *= 1.0 - uB.x * A * 0.6 * (1.0 - f);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(clamp(col.rgb, 0.0, 1.0), c0.a));
}
"""

SHADERS = {'enc': ENC, 'sig': SIG, 'fx': FX, 'stamp': _LG['STAMP']}

P = _LG['P']
G = 'max(1, int(%s))' % P.format('Generations')
UNIFORMS = {
    'enc': [('uR', [_LG['raster_expr']('pitch'), _LG['raster_expr']('tx'), _LG['raster_expr']('ty'),
                    'parent().par.Lineaxis.menuIndex'])],
    'sig': [('uS', [P.format('Sharpen'), '%s * (1.0 + 0.5 * (%s - 1))' % (P.format('Chromashift'), G),
                    '(0.3 + 4.7 * min(1.0, max(0.0, %s))) * %s' % (P.format('Bleed'), _LG['speed_list'](1)), G]),
            ('uP', ['min(%d, %s + int(%s))' % (_LG['VHS_MAX_LUMA_PASSES'], G, _LG['speed_list'](0)), '0', '0', '0'])],
    'fx': [('uA', [P.format('Amount'), P.format('Wobble'), P.format('Noise'), P.format('Dropouts')]),
           ('uB', [P.format('Scanlines'), '%s * 0.92 ** (%s - 1)' % (P.format('Saturation'), G), P.format('Warmth'),
                   '(%s if %s else 0)' % (P.format('Headlines'), P.format('Headswitch'))]),
           ('uC', [P.format('Tracking'), P.format('Randomness'), P.format('Seed'),
                   '1 if %s else 0' % P.format('Interlace')]),
           ('uD', ['absTime.seconds', _LG['NOISE_STEP_EXPR'], 'absTime.seconds - %s' % P.format('Glitchtime'),
                   P.format('Glitchcount')]),
           ('uE', [_LG['raster_expr']('pitch'), 'parent().par.Lineaxis.menuIndex', P.format('Flagging'),
                   '1 if %s else 0' % P.format('Dropcomp')]),
           ('uF', [_LG['speed_list'](2), _LG['speed_list'](3), '0', '0'])],
}


def build(m, H):
    """Fill instance COMP m: in1 -> enc -> sig (+ sprev / prev_src for Interlace) -> fx (+ stamp) -> out_sel -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    _LG['pulse_exec'](m, H, {'Glitch': ('Glitchtime', 'Glitchcount')})
    enc = H['compute'](m, 'enc', ENC, [in1], fmt='rgba16float')
    _LG['custom_res'](enc, H, _LG['raster_expr']('vw', 'me.inputs[0]'), _LG['raster_expr']('vh', 'me.inputs[0]'))
    H['uniforms'](enc, UNIFORMS['enc'])
    enc.comment = 'Tape raster (Lines follow the height, >= 3 px per line): box average, RGB -> YIQ.'
    sig = H['compute'](m, 'sig', SIG, [enc], fmt='rgba16float')
    H['uniforms'](sig, UNIFORMS['sig'])
    sig.comment = 'Luma low-pass + Sharpen ring; colour-under chroma shifted + smeared right (Bleed, Generations).'
    sp = mk(m, cacheTOP, 'sprev')
    sp.inputConnectors[0].connect(sig)
    sp.par.cachesize = 2
    sp.par.outputindex = -1
    sp.comment = 'Previous signal frame (Interlace only; pulled only while prev_src selects it).'
    pv = mk(m, switchTOP, 'prev_src')
    pv.inputConnectors[0].connect(sig)
    pv.inputConnectors[1].connect(sp)
    expr(pv.par.index, '1 if %s else 0' % P.format('Interlace'))
    st = _LG['stamp'](m, H)
    fx = H['compute'](m, 'fx', FX, [in1, sig, pv, st])
    H['uniforms'](fx, UNIFORMS['fx'])
    fx.comment = 'Wobble, flagging, tracking band, Glitch, head switch, interlace, noise, dropouts, scanlines, Amount.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, _LG['vhs_active_expr']())
    sel.comment = 'Amount 0 and no Glitch burst = in1 exact (enc / sig / fx not pulled).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulses'], 'body': 'Glitch pulse -> Glitchtime / Glitchcount.'},
        {'title': '2 Tape signal', 'role': 'process', 'ops': ['enc', 'enc_compute', 'sig', 'sig_compute', 'sprev',
                                                              'prev_src'],
         'body': 'Virtual raster: enc (YIQ) -> sig (luma ring, colour-under bleed). sprev only for Interlace.'},
        {'title': '3 Composite', 'role': 'process', 'ops': ['stamp', 'stamp_compute', 'fx', 'fx_compute'],
         'body': 'Output size: line effects, band, Glitch, head switch, noise, dropouts, scanlines.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
