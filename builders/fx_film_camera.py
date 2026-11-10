# fx_film_camera - FX_film module 'camera' (FX3 C1 + C2 + C3 + C4 + C8; FX0 rows 33, 34, 63, 79): what the camera
# body does to the picture.
#   path  (257 x 1, rgba32float): the handheld move over a short time window around now: 1/f shake (fbm, Octaves),
#         footfall bumps (Steprate or Bpm, alternating roll), wobble (jello), pan velocity, zoom. Texel 128 = now.
#   ae    (1 x 1, in place): auto exposure: log-average luma of in1 (16 x 16 taps on a mip), target / attack /
#         release lag, frame-stamped so a second cook in one frame changes nothing.
#   geo   (in1 size, rgba16float, linear light): ROLLING SHUTTER = every row has its own time (Readout, Direction), so
#         the move is read per row (skew / jello of our own moves exactly, Pan for content); SHUTTER = Samples taps of
#         the move inside the open shutter (analytic camera motion blur, Shutter angle at Fpsbasis); exposure (stops +
#         ae), mains flicker bands (lamp 2 x Mains Hz integrated over the shutter: sinc), flash banding (a flash lights
#         only the rows whose exposure window holds it: Trigger pulse or every Flashbeats beats).
#   acc   (in place, rgba32float, Trail on only): geo's maths fused with the content motion trail (same mean age as
#         the shutter box: a = (S - 1) / (S + 1), S = shutter in timeline frames); one buffer (trail rgb, frame
#         stamp); geo is not cooked while acc is used; skipped (trail_sel -> geo) when a = 0.
#   fx    (in1 format): ISO sensor noise (Poisson-Gaussian sqrt(a I + b) per channel, chroma share + blotch size, fixed
#         pattern columns, hot pixels), encode back, Amount mix.
# -> out_sel (Amount 0 = in1, nothing cooks) -> out1. Maths: builders/fx_film_camera_logic.py. No flash / flicker caps
# (user rule 26 Oct). ASCII only.

MODULE = 'camera'

PAGES = [
    ('Camera', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Inspace', 'Menu', 'srgb', {'names': ['srgb', 'linear'], 'labels': ['sRGB-encoded in', 'Linear in']}),
        ('Shutter', 'Float', 180.0, {'min': 0, 'max': 720, 'label': 'Shutter angle (deg)'}),
        ('Fpsbasis', 'Float', 24.0, {'min': 1, 'max': 120, 'label': 'Camera fps'}),
        ('Moveblur', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Move blur (x shutter)'}),
        ('Samples', 'Int', 8, {'min': 1, 'max': 32, 'label': 'Blur samples'}),
        ('Trail', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Content trail (x shutter)'}),
        ('Edge', 'Menu', 'mirror', {'names': ['hold', 'zero', 'repeat', 'mirror'],
                                    'labels': ['Hold', 'Black', 'Repeat', 'Mirror']}),
        ('Overscan', 'Float', 1.0, {'min': 1, 'max': 1.5, 'label': 'Overscan zoom'}),
        ('Freeze', 'Toggle', False, {'label': 'Freeze time'}),
        ('Phase', 'Float', 0.0, {'min': 0, 'max': 100, 'label': 'Time phase (s)'}),
        ('Speed', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Time speed'}),
    ]),
    ('Handheld', [
        ('Shake', 'Float', 0.0, {'min': 0, 'max': 80, 'label': 'Shake (px)'}),
        ('Shakefreq', 'Float', 0.6, {'min': 0.05, 'max': 12, 'label': 'Shake frequency (Hz)'}),
        ('Octaves', 'Int', 3, {'min': 1, 'max': 6, 'label': 'Octaves (1/f)'}),
        ('Shakerot', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Shake roll (deg)'}),
        ('Zoomshake', 'Float', 0.0, {'min': 0, 'max': 0.2, 'label': 'Zoom breathe (log2)'}),
        ('Zoom', 'Float', 1.0, {'min': 0.5, 'max': 3, 'label': 'Zoom / push-in'}),
        ('Pivotx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Pivot x'}),
        ('Pivoty', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Pivot y'}),
        ('Steps', 'Float', 0.0, {'min': 0, 'max': 60, 'label': 'Footsteps (px)'}),
        ('Stepsroll', 'Float', 0.0, {'min': 0, 'max': 5, 'label': 'Footsteps roll (deg)'}),
        ('Drive', 'Menu', 'free', {'names': ['free', 'bpm'], 'labels': ['Free (Steprate)', 'Bpm']}),
        ('Steprate', 'Float', 1.8, {'min': 0.1, 'max': 6, 'label': 'Step rate (Hz)'}),
        ('Bpm', 'Float', 120.0, {'min': 40, 'max': 200, 'label': 'Bpm'}),
        ('Stepsperbeat', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Steps per beat'}),
        ('Seed', 'Int', 3, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Rolling', [
        ('Readout', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Readout (frames)'}),
        ('Direction', 'Menu', 'topdown', {'names': ['topdown', 'bottomup', 'leftright', 'rightleft'],
                                          'labels': ['Top -> bottom', 'Bottom -> top', 'Left -> right',
                                                     'Right -> left']}),
        ('Panx', 'Float', 0.0, {'min': -3000, 'max': 3000, 'label': 'Pan x (px/s)'}),
        ('Pany', 'Float', 0.0, {'min': -3000, 'max': 3000, 'label': 'Pan y (px/s)'}),
        ('Wobble', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Wobble (px)'}),
        ('Wobblefreq', 'Float', 12.0, {'min': 0.5, 'max': 60, 'label': 'Wobble (Hz)'}),
        ('Mains', 'Menu', 'off', {'names': ['off', 'hz50', 'hz60'], 'labels': ['Off', '50 Hz mains', '60 Hz mains']}),
        ('Banddepth', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Flicker band depth'}),
        ('Flashmode', 'Menu', 'off', {'names': ['off', 'trigger', 'bpm'],
                                      'labels': ['Off', 'Trigger pulse', 'Every Flashbeats beats']}),
        ('Flash', 'Pulse', None, {'label': 'Flash'}),
        ('Flashbeats', 'Float', 1.0, {'min': 0.25, 'max': 16, 'label': 'Flash every (beats)'}),
        ('Flashlen', 'Float', 0.002, {'min': 0.0005, 'max': 0.1, 'label': 'Flash length (s)'}),
        ('Flashgain', 'Float', 2.0, {'min': 0, 'max': 10, 'label': 'Flash gain'}),
        ('Flashwash', 'Float', 0.2, {'min': 0, 'max': 2, 'label': 'Flash wash (add)'}),
        ('Flashtime', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Last flash (time s)'}),
    ]),
    ('Exposure', [
        ('Exposure', 'Float', 0.0, {'min': -6, 'max': 6, 'label': 'Exposure (stops)'}),
        ('Autoexp', 'Toggle', False, {'label': 'Auto exposure'}),
        ('Aetarget', 'Float', 0.18, {'min': 0.01, 'max': 1, 'label': 'AE target (linear)'}),
        ('Aeattack', 'Float', 0.08, {'min': 0, 'max': 2, 'label': 'AE attack (s, darken)'}),
        ('Aerelease', 'Float', 0.6, {'min': 0, 'max': 8, 'label': 'AE release (s, brighten)'}),
        ('Aemax', 'Float', 4.0, {'min': 0, 'max': 8, 'label': 'AE range (stops)'}),
        ('Iso', 'Float', 0.0, {'min': 0, 'max': 25600, 'label': 'ISO (0 = no noise)'}),
        ('Shotnoise', 'Float', 0.0004, {'min': 0, 'max': 0.01, 'label': 'Shot noise gain @100'}),
        ('Readnoise', 'Float', 0.002, {'min': 0, 'max': 0.05, 'label': 'Read noise std @100'}),
        ('Chroma', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Chroma noise share'}),
        ('Chromasize', 'Float', 1.0, {'min': 1, 'max': 16, 'label': 'Chroma blotch (px)'}),
        ('Fpn', 'Float', 0.0, {'min': 0, 'max': 0.05, 'label': 'Fixed-pattern columns'}),
        ('Hotpixels', 'Float', 0.0, {'min': 0, 'max': 500, 'label': 'Hot pixels per Mpx'}),
        ('Hotgain', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Hot pixel level'}),
        ('Animate', 'Toggle', True, {'label': 'Animate noise'}),
    ]),
]
PANEL_PAGES = ['Camera', 'Handheld', 'Rolling', 'Exposure']

PRESETS = [
    (1, 'cine 24p', {'Amount': 1.0, 'Shutter': 180.0, 'Fpsbasis': 24.0, 'Moveblur': 1.0, 'Trail': 1.0,
                     'Shake': 0.0, 'Steps': 0.0, 'Readout': 0.0, 'Iso': 0.0, 'Mains': 0, 'Flashmode': 0}),
    (2, 'handheld doc', {'Amount': 1.0, 'Shutter': 180.0, 'Fpsbasis': 25.0, 'Moveblur': 1.0, 'Samples': 8,
                         'Shake': 7.0, 'Shakefreq': 0.7, 'Octaves': 3, 'Shakerot': 0.4, 'Zoomshake': 0.01,
                         'Steps': 4.0, 'Stepsroll': 0.3, 'Drive': 0, 'Steprate': 1.8, 'Readout': 0.5,
                         'Overscan': 1.06, 'Iso': 400.0}),
    (3, 'phone jello', {'Amount': 1.0, 'Shutter': 90.0, 'Fpsbasis': 30.0, 'Readout': 1.0, 'Direction': 0,
                        'Wobble': 4.0, 'Wobblefreq': 14.0, 'Shake': 3.0, 'Shakefreq': 2.0, 'Overscan': 1.04,
                        'Iso': 800.0}),
    (4, 'stage strobe cam', {'Amount': 1.0, 'Shutter': 45.0, 'Fpsbasis': 30.0, 'Readout': 0.9, 'Flashmode': 2,
                             'Flashbeats': 1.0, 'Flashgain': 3.0, 'Flashwash': 0.3, 'Mains': 1, 'Banddepth': 0.25,
                             'Iso': 1600.0, 'Chroma': 0.4}),
    (5, 'night iso', {'Amount': 1.0, 'Exposure': 1.5, 'Autoexp': 1, 'Aetarget': 0.18, 'Iso': 6400.0, 'Chroma': 0.5,
                      'Chromasize': 3.0, 'Fpn': 0.003, 'Hotpixels': 30.0, 'Animate': 1, 'Shake': 2.0}),
]

PATH = """// FX_film camera path (compute, 257 x 1, rgba32float): (dx px, dy px, roll rad, log2 zoom) at dt = (i/256 - 0.5) 2 Wh.
// uP0 n0 freq oct seed | uP1 shake rot(deg) zoomshake Wh | uP2 steps stepsroll(deg) ph0 rate | uP3 wobble wph0 wfreq panx
// uP4 pany zoom(log2) - -     (fx_film_camera_logic.path_at mirrors this)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uP0;
uniform vec4 uP1;
uniform vec4 uP2;
uniform vec4 uP3;
uniform vec4 uP4;
%s
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= int(uTDOutputInfo.res.z) || p.y >= 1) return;
    float dt = (float(p.x) / 256.0 - 0.5) * 2.0 * uP1.w;
    float na = uP0.x + dt * uP0.y;
    uint s = uint(uP0.w + 0.5);
    int oct = int(uP0.z + 0.5);
    float sx = 2.0 * fbm(vec2(na, 0.5), s, oct) - 1.0;
    float sy = 2.0 * fbm(vec2(na, 37.5), s, oct) - 1.0;
    float sr = 2.0 * fbm(vec2(na, 71.5), s, oct) - 1.0;
    float sz = 2.0 * fbm(vec2(na, 113.5), s, oct) - 1.0;
    float ph = uP2.z + dt * uP2.w;
    float f = fract(ph);
    float side = mod(floor(ph), 2.0) < 0.5 ? -1.0 : 1.0;
    float e = exp(-7.0 * f) - (1.0 - exp(-7.0)) / 7.0;
    vec2 off = uP1.x * vec2(sx, sy) + vec2(0.0, -uP2.x * e)
             + vec2(uP3.x * sin(6.2831853 * (uP3.y + dt * uP3.z)), 0.0) + vec2(uP3.w, uP4.x) * dt;
    float rot = radians(uP1.y * sr + side * uP2.y * e);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(off, rot, uP4.y + uP1.z * sz));
}
"""

AE = """// FX_film camera ae (compute, 1 x 1, rgba32float in place): r = ev after this frame, g = ev before, b = frame stamp,
// a = dt. 64 threads meter a 16 x 16 grid of in1 at mip 5 (log-average luma), thread 0 lags toward the target.
// uM0 target attack release maxstops | uM1 stamp cookrate enabled inspace
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uM0;
uniform vec4 uM1;
shared float sl[64];
%s
void main() {
    ivec2 t = ivec2(gl_LocalInvocationID.xy);
    if (gl_WorkGroupID.x != 0u || gl_WorkGroupID.y != 0u) return;
    int id = t.y * 8 + t.x;
    float a = 0.0;
    for (int k = 0; k < 4; k++) {
        int c = id * 4 + k;
        vec2 uv = (vec2(float(c %% 16), float(c / 16)) + 0.5) / 16.0;
        vec3 s = textureLod(sTD2DInputs[0], uv, 5.0).rgb;
        if (uM1.w < 0.5) s = srgb2lin(s);
        a += log2(max(luma(s), 1e-4));
    }
    sl[id] = a;
    barrier();
    if (id != 0) return;
    float sum = 0.0;
    for (int k = 0; k < 64; k++) sum += sl[k];
    float gm = exp2(sum / 256.0);
    float des = clamp(log2(uM0.x / max(gm, 1e-4)), -uM0.w, uM0.w);
    vec4 o = TDImageLoadOutput(0, ivec3(0));
    if (uM1.z < 0.5) { TDImageStoreOutput(0, ivec3(0), vec4(0.0, 0.0, uM1.x, 0.0)); return; }
    float gap = mod(uM1.x - o.b + 2048.0, 2048.0);
    float before = gap < 0.5 ? o.g : (gap < 30.5 ? o.r : des);   // > 30 frames: AE was off (T-156)
    float dt = gap < 0.5 ? o.a : gap / max(uM1.y, 1.0);
    float tau = des < before ? uM0.y : uM0.z;
    float after = before + (des - before) * (1.0 - exp(-dt / max(tau, 1e-3)));
    TDImageStoreOutput(0, ivec3(0), vec4(after, before, uM1.x, dt));
}
"""

GEO = """// FX_film camera geo (compute, linear light out). in0 = picture, in1 = path (257 x 1), in2 = ae (1 x 1).
// uA amount inspace samples moveblur | uB readout(s) direction shutter(s) Wh | uC pivot px x y, overscan log2, -
// uD exposure autoexp banddepth lampHz | uE flicker phase0, flash age(s), flash len(s), flash gain | uF wash - - -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
uniform vec4 uE;
uniform vec4 uF;
%s
vec4 pathAt(float dt) {                    // linear between texels; dt 0 = texel 128 exactly
    float x = clamp((dt / (2.0 * uB.w) + 0.5) * 256.0, 0.0, 256.0);
    int i0 = min(int(floor(x)), 255);
    return mix(texelFetch(sTD2DInputs[1], ivec2(i0, 0), 0), texelFetch(sTD2DInputs[1], ivec2(i0 + 1, 0), 0),
               x - float(i0));
}
vec3 geoAt(ivec2 p, ivec2 isz) {          // the camera image at pixel p (linear light); shared by geo and acc
    vec2 sz = vec2(isz);
    int dir = int(uB.y + 0.5);
    vec2 P = vec2(p) + 0.5;
    float rf = dir == 0 ? 1.0 - P.y / sz.y : (dir == 1 ? P.y / sz.y : (dir == 2 ? P.x / sz.x : 1.0 - P.x / sz.x));
    float tr = (rf - 0.5) * uB.x;
    int S = uA.w > 0.0 ? int(uA.z + 0.5) : 1;
    vec3 acc = vec3(0.0);
    for (int k = 0; k < 32; k++) {
        if (k >= S) break;
        float ts = tr + (S > 1 ? ((float(k) + 0.5) / float(S) - 0.5) * uB.z * uA.w : 0.0);
        vec4 T = pathAt(ts);
        vec2 q = P - uC.xy - T.xy;
        float sc = exp2(-(T.w + uC.z));
        float cr = cos(-T.z), sr = sin(-T.z);
        vec2 X = uC.xy + sc * vec2(cr * q.x - sr * q.y, sr * q.x + cr * q.y);
        vec3 s = texture(sTD2DInputs[0], X / sz).rgb;
        acc += uA.y < 0.5 ? srgb2lin(s) : s;
    }
    vec3 col = acc / float(S);
    float g = exp2(uD.x + (uD.y > 0.5 ? texelFetch(sTD2DInputs[2], ivec2(0), 0).r : 0.0));
    if (uD.z > 0.0 && uD.w > 0.0) {         // mains flicker integrated over the shutter window: sinc(pi f T)
        float x = 3.14159265 * uD.w * uB.z;
        float sn = x > 1e-6 ? sin(x) / x : 1.0;
        g *= max(1.0 + uD.z * sn * cos(6.2831853 * (uE.x + uD.w * tr)), 0.0);
    }
    float Ts = max(uB.z, 1e-4);              // flash: share of the flash inside this row's exposure window
    float age = uE.y + tr;
    float ov = max(0.0, min(age + 0.5 * Ts, uE.z) - max(age - 0.5 * Ts, 0.0));
    float cov = ov / max(min(uE.z, Ts), 1e-6);
    return col * g * (1.0 + uE.w * cov) + uF.x * cov;
}
"""

GEO_MAIN = """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(geoAt(p, isz), texelFetch(sTD2DInputs[0], p, 0).a));
}
"""

ACC_MAIN = """
// acc (Trail on): geo fused with the content trail, in place: (trail rgb, frame stamp). A gap of g timeline frames
// decays by a^g (time-correct when TD drops frames, T-156); > 30 frames (module was off) restarts from the picture; a
// second cook in the same frame keeps the stored result (no double step, no work). uT0 a stamp - -
uniform vec4 uT0;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 o = TDImageLoadOutput(0, ivec3(p, 0));
    float gap = mod(uT0.y - o.a + 2048.0, 2048.0);
    if (gap < 0.5) return;
    vec3 c = geoAt(p, isz);
    float w = gap < 30.5 ? pow(uT0.x, gap) : 0.0;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(mix(c, o.rgb, w), uT0.y));
}
"""

FX = """// FX_film camera fx (compute, in1 format). in0 = picture (alpha, Amount mix), in1 = linear camera image (geo / acc).
// uN0 amount inspace iso shot(x1e3) | uN1 read chroma fpn hot(per Mpx) | uN2 hotgain seed chromasize -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uN0;
uniform vec4 uN1;
uniform vec4 uN2;
%s
const float VN2 = %r;
float bm(ivec2 c, uint s) {                  // fx_film_camera_logic.box_muller
    float u1 = max(hsh(c, s), 1e-9), u2 = hsh(c, s * 7u + 13u);
    return sqrt(-2.0 * log(u1)) * cos(6.2831853 * u2);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uN0.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    vec3 x = texelFetch(sTD2DInputs[1], p, 0).rgb;
    uint sd = uint(uN2.y + 0.5);
    if (uN0.z > 0.0) {
        float k = uN0.z / 100.0;
        vec3 sig = sqrt(max(uN0.w * 1e-3 * k * max(x, vec3(0.0)) + (uN1.x * k) * (uN1.x * k), vec3(0.0)));
        float nl = bm(p, sd);
        vec3 nc;
        if (uN2.z <= 1.0) nc = vec3(bm(p, sd + 101u), bm(p, sd + 202u), bm(p, sd + 303u));
        else { vec2 q = (vec2(p) + 0.5) / uN2.z;
               nc = VN2 * (vec3(vnoise(q, sd + 101u), vnoise(q, sd + 202u), vnoise(q, sd + 303u)) - 0.5); }
        x += sig * (sqrt(1.0 - uN1.y) * nl + sqrt(uN1.y) * nc);
    }
    if (uN1.z > 0.0) x += uN1.z * bm(ivec2(p.x, 0), 7771u);
    if (uN1.w > 0.0 && hsh(p, 9973u) < uN1.w * 1e-6) x += vec3(uN2.x);
    vec3 o = uN0.y < 0.5 ? lin2srgb(x) : x;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(mix(c.rgb, o, uN0.x), c.a));
}
"""

PULSE_EXEC = """# Flash pulse -> Flashtime (= the module's time T, so Freeze holds the flash band still for checks).
def onPulse(par):
    if par.name == 'Flash':
        o = par.owner
        o.par.Flashtime.val = (o.par.Phase.eval() if o.par.Freeze.eval()
                               else absTime.seconds * o.par.Speed.eval() + o.par.Phase.eval())
    return
"""

Q = "parent().par.{}.eval()"
T = "({p} if {f} else absTime.seconds * {s} + {p})".format(p=Q.format('Phase'), f=Q.format('Freeze'),
                                                          s=Q.format('Speed'))
FPS = "max(%s, 1e-3)" % Q.format('Fpsbasis')
TSH = "(%s / 360.0 / %s)" % (Q.format('Shutter'), FPS)
RO = "(%s / %s)" % (Q.format('Readout'), FPS)
WH = "(0.5 * %s + 0.5 * %s * max(%s, 0.0) + 1e-4)" % (RO, TSH, Q.format('Moveblur'))
RATE = "(%s / 60.0 * %s if parent().par.Drive.eval() == 'bpm' else %s)" % (
    Q.format('Bpm'), Q.format('Stepsperbeat'), Q.format('Steprate'))
LAMP = "(0.0 if parent().par.Mains.eval() == 'off' else (100.0 if parent().par.Mains.eval() == 'hz50' else 120.0))"
AGE = ("(lambda m, t, b, fb, ft: -1000.0 if m == 'off' else ((t - ft if ft >= 0 else -1000.0) if m == 'trigger' else "
       "t - math.floor(t * b / 60.0 / max(fb, 1e-3)) * max(fb, 1e-3) * 60.0 / max(b, 1e-3)))"
       "(parent().par.Flashmode.eval(), %s, %s, %s, %s)" % (T, Q.format('Bpm'), Q.format('Flashbeats'),
                                                          Q.format('Flashtime')))
TRAIL_A = ("(lambda s, tr: min(tr * (s - 1.0) / (s + 1.0), 0.995) if s > 1.0 and tr > 0 else 0.0)"
           "(%s / 360.0 * project.cookRate / %s, %s)" % (Q.format('Shutter'), FPS, Q.format('Trail')))
SEED = "(%s * 977 + (absTime.frame %% 1024) * 7919 if %s else %s * 977)" % (
    Q.format('Seed'), Q.format('Animate'), Q.format('Seed'))
STAMP = 'absTime.frame % 2048'


def shaders(H):
    return {'path': PATH % H['LIB'], 'ae': AE % H['LIB'], 'geo': GEO % H['LIB'] + GEO_MAIN,
            'acc': GEO % H['LIB'] + ACC_MAIN,
            'fx': FX % (H['LIB'], H['L'].vn_norm(2))}


def build(m, H):
    """in1 -> path, ae -> geo (rolling + shutter taps + exposure) -> acc (trail) -> fx (ISO) -> out_sel -> out1."""
    mk, P = H['mk'], H['P']
    sh = shaders(H)
    in1 = mk(m, inTOP, 'in1')
    path = H['compute'](m, 'path', sh['path'], [in1], res=(257, 1), fmt='rgba32float')
    H['uniforms'](path, [
        ('uP0', ['(%s * %s) %% 4096.0' % (T, P.format('Shakefreq')), P.format('Shakefreq'), P.format('Octaves'),
                 P.format('Seed')]),
        ('uP1', [P.format('Shake'), P.format('Shakerot'), P.format('Zoomshake'), WH]),
        ('uP2', [P.format('Steps'), P.format('Stepsroll'), '(%s * %s) %% 2.0' % (T, RATE), RATE]),
        ('uP3', [P.format('Wobble'), '(%s * %s) %% 1.0' % (T, P.format('Wobblefreq')), P.format('Wobblefreq'),
                 P.format('Panx')]),
        ('uP4', [P.format('Pany'), 'math.log2(max(%s, 1e-3))' % P.format('Zoom'), '0', '0']),
    ])
    path.comment = 'path: the handheld move (shake, steps, wobble, pan, zoom) over +-Wh s around now; texel 128 = now.'
    ae = H['compute'](m, 'ae', sh['ae'], [in1], res=(1, 1), fmt='rgba32float', filt='mipmap')
    ae.par.outputaccess = 'readwrite'
    ae.par.clearoutputs = False
    H['uniforms'](ae, [
        ('uM0', [P.format('Aetarget'), P.format('Aeattack'), P.format('Aerelease'), P.format('Aemax')]),
        ('uM1', [STAMP, 'project.cookRate', '1 if %s else 0' % P.format('Autoexp'), 'parent().par.Inspace.menuIndex']),
    ])
    ae.comment = 'ae: log-average meter of in1 -> lagged ev (attack / release), in place, frame-stamped.'
    GU = [
        ('uA', [P.format('Amount'), 'parent().par.Inspace.menuIndex', P.format('Samples'), P.format('Moveblur')]),
        ('uB', [RO, 'parent().par.Direction.menuIndex', TSH, WH]),
        ('uC', ['me.inputs[0].width * %s' % P.format('Pivotx'), 'me.inputs[0].height * %s' % P.format('Pivoty'),
                'math.log2(max(%s, 1e-3))' % P.format('Overscan'), '0']),
        ('uD', [P.format('Exposure'), '1 if %s else 0' % P.format('Autoexp'), P.format('Banddepth'), LAMP]),
        ('uE', ['(%s * %s) %% 1.0' % (T, LAMP), AGE, P.format('Flashlen'), P.format('Flashgain')]),
        ('uF', [P.format('Flashwash'), '0', '0', '0']),
    ]
    geo = H['compute'](m, 'geo', sh['geo'], [in1, path, ae], fmt='rgba16float')
    H['expr'](geo.par.inputextenduv, "parent().par.Edge.eval()")
    H['uniforms'](geo, GU)
    geo.comment = 'geo: rolling shutter (row time) + shutter taps of the move + exposure, flicker, flash bands (linear).'
    acc = H['compute'](m, 'acc', sh['acc'], [in1, path, ae], fmt='rgba32float')
    H['expr'](acc.par.inputextenduv, "parent().par.Edge.eval()")
    acc.par.outputaccess = 'readwrite'
    acc.par.clearoutputs = False
    acc.par.numcolorbufs = 1
    H['uniforms'](acc, GU + [('uT0', [TRAIL_A, STAMP, '0', '0'])])
    acc.comment = ('acc: geo fused with the content trail, a = (S - 1) / (S + 1) x Trail (S = shutter in cooks); '
                   'in place, stamped; geo is not cooked while Trail is on.')
    ts = mk(m, switchTOP, 'trail_sel')
    ts.inputConnectors[0].connect(geo)
    ts.inputConnectors[1].connect(acc)
    H['expr'](ts.par.index, '1 if %s > 0 else 0' % TRAIL_A)
    ts.comment = 'Trail a = 0 -> geo (acc not cooked).'
    g = H['compute'](m, 'fx', sh['fx'], [in1, ts])
    H['uniforms'](g, [
        ('uN0', [P.format('Amount'), 'parent().par.Inspace.menuIndex', P.format('Iso'),
                 '%s * 1000.0' % P.format('Shotnoise')]),
        ('uN1', [P.format('Readnoise'), P.format('Chroma'), P.format('Fpn'), P.format('Hotpixels')]),
        ('uN2', [P.format('Hotgain'), SEED, P.format('Chromasize'), '0']),
    ])
    g.comment = 'fx: ISO noise (Poisson-Gaussian, chroma, fixed pattern, hot pixels), encode, Amount mix.'
    pe = mk(m, parameterexecuteDAT, 'pulse_exec')
    if pe.text != PULSE_EXEC:
        pe.text = PULSE_EXEC
        pe.par.active = False                                # T-97: toggle after a text rewrite
    pe.par.op = '..'
    pe.par.pars = 'Flash'
    pe.par.valuechange = False
    pe.par.onpulse = True
    pe.par.active = True
    sel = H['outsel'](m, in1, g)
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Move + meter', 'role': 'process', 'ops': ['path', 'path_compute', 'ae', 'ae_compute', 'pulse_exec'],
         'body': 'path: handheld move around now (257 texels). ae: auto exposure, in place. Flash pulse -> Flashtime.'},
        {'title': '3 Sensor', 'role': 'process', 'ops': ['geo', 'geo_compute', 'acc', 'acc_compute', 'trail_sel'],
         'body': 'Rolling shutter row time + shutter taps + exposure / flicker / flash bands; acc = content trail.'},
        {'title': '4 Noise', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'ISO noise, encode, Amount.'},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
