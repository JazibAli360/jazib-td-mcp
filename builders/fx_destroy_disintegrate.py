# fx_destroy_disintegrate - FX_destroy module 'disintegrate' (FX1 DG-17, FX4 D4: the picture crumbles into dust that
# blows away, Thanos-style, and can fly back together).
# Module file = PAGES + PRESETS + build(m, H) (template: docs/builds/fx_glitch.md; rack: builders/fx_destroy.py).
# Doc + live results: docs/builds/fx_destroy_disintegrate.md. Reference maths: builders/fx_destroy_disintegrate_logic.py.
# Reused, not re-made: explode's `hit` latch shader + Beat CHOP exec (exec'd from fx_destroy_explode.py), the rack's
# Point page (Effector Null / Point uv), Mask page + fxMask(), State page + pulse_exec, GLSL lib, compute helper;
# the dust ideas of PX v2's ember pool (cone around the wind, keep-colour vs hot tint, lift, lifespan).
# The picture is cut into grains of Grain px (one particle each; 2 px at 1080x1920 = 518400 particles). Everything is
# ANALYTIC in the time since the hit (or Progress x Duration), so no particle state can go stale and scrubbing
# Progress back reassembles the picture:
#   grains (grain res): release time tb per grain = Sweep x front(f) (wipe direction / from the Point / inward / noise /
#     bright first / Mask as a wipe map) mixed with fbm (Roughness) + per-grain Jitter; Mask < 0.5 = never released.
#   dust (full res, cleared every cook, dispatched one thread per grain): each released grain flies (wind in a cone,
#     speed variety, blast from the Point with falloff, drag, gravity / lift, curl-noise turbulence, push away from the
#     live Effector), fades over Life, shrinks, hot tint -> ash; stored as a Size px square (last write wins).
#   fx (full res): remnant (intact grains = texelFetch of the picture, released = Back), pre-release edge glow, dust
#     composited over / added. Amount 0, no hit, and a finished Return / assemble are exact passthrough. ASCII only.
import os

MODULE = 'disintegrate'

PAGES = [
    ('Disintegrate', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (motion + fade)'}),
        ('Mode', 'Menu', 'away', {'names': ['away', 'assemble'], 'labels': ['Blow away', 'Assemble (dust flies in)']}),
        ('Drive', 'Menu', 'hits', {'names': ['hits', 'manual'], 'labels': ['Hits (Trigger / Beat / Auto)',
                                                                           'Manual (Progress)']}),
        ('Progress', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Progress (manual, x Duration s)'}),
        ('Duration', 'Float', 4.0, {'min': 0.1, 'max': 12, 'label': 'Duration s (manual / assemble flight)'}),
        ('Trigger', 'Pulse', None, {'label': 'Trigger (snap)'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (intact)'}),
        ('Auto', 'Float', 0.0, {'min': 0, 'max': 12, 'label': 'Auto snap every s (0 = off)'}),
        ('Beatchop', 'CHOP', '', {'label': 'Beat CHOP (rising edge snaps)'}),
        ('Ignorehits', 'Toggle', False, {'label': 'Ignore hits while running'}),
        ('Hold', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Fly-out s (before Return)'}),
        ('Return', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Return s (retrace home, 0 = gone)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Front', [
        ('Front', 'Menu', 'dir', {'names': ['dir', 'point', 'inward', 'noise', 'luma', 'mask'],
                                  'labels': ['Wipe direction', 'Out from Point', 'In to Point', 'Noise only',
                                             'Bright first', 'Mask as wipe map']}),
        ('Frontangle', 'Float', 20.0, {'min': -180, 'max': 180, 'label': 'Wipe angle deg (0 = to the right)'}),
        ('Sweep', 'Float', 2.5, {'min': 0, 'max': 10, 'label': 'Sweep s (front crosses)'}),
        ('Roughness', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Roughness (noise in the front)'}),
        ('Noisescale', 'Float', 160.0, {'min': 8, 'max': 800, 'label': 'Noise scale px'}),
        ('Detail', 'Int', 4, {'min': 1, 'max': 6, 'label': 'Noise octaves'}),
        ('Jitter', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Per-grain jitter'}),
        ('Reverse', 'Toggle', False, {'label': 'Reverse front'}),
        ('Edge', 'Float', 0.3, {'min': 0, 'max': 2, 'label': 'Edge glow s before release'}),
        ('Edgeglow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Edge glow'}),
        ('Edgecolor', 'RGB', (1.0, 0.55, 0.2), {'label': 'Edge colour'}),
    ]),
    ('Dust', [
        ('Grain', 'Int', 2, {'min': 1, 'max': 8, 'label': 'Grain px (quality: 1 = per pixel)'}),
        ('Size', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Particle size (x grain)'}),
        ('Shrink', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Size at end of life (x)'}),
        ('Windangle', 'Float', 30.0, {'min': -180, 'max': 180, 'label': 'Wind angle deg (90 = up)'}),
        ('Windspeed', 'Float', 260.0, {'min': 0, 'max': 2000, 'label': 'Wind px/s'}),
        ('Cone', 'Float', 35.0, {'min': 0, 'max': 360, 'label': 'Wind cone deg'}),
        ('Spread', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Speed variety'}),
        ('Blast', 'Float', 0.0, {'min': -2000, 'max': 3000, 'label': 'Blast px/s from the Point'}),
        ('Falloff', 'Float', 0.5, {'min': 0, 'max': 3, 'label': 'Blast falloff'}),
        ('Gravity', 'Float', -60.0, {'min': -1500, 'max': 1500, 'label': 'Gravity px/s2 (< 0 = lift)'}),
        ('Drag', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Drag (blast)'}),
        ('Turbulence', 'Float', 120.0, {'min': 0, 'max': 1500, 'label': 'Turbulence px/s'}),
        ('Turbscale', 'Float', 140.0, {'min': 8, 'max': 800, 'label': 'Turbulence scale px'}),
        ('Turbspeed', 'Float', 0.6, {'min': 0, 'max': 5, 'label': 'Turbulence evolve /s'}),
        ('Push', 'Float', 0.0, {'min': -600, 'max': 600, 'label': 'Effector push px'}),
        ('Pushradius', 'Float', 200.0, {'min': 1, 'max': 1500, 'label': 'Push radius px'}),
        ('Life', 'Float', 2.2, {'min': 0, 'max': 10, 'label': 'Life s (fade out, 0 = never)'}),
        ('Hot', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Hot tint at release'}),
        ('Hotcolor', 'RGB', (1.0, 0.45, 0.1), {'label': 'Hot colour'}),
        ('Hottime', 'Float', 0.5, {'min': 0.01, 'max': 4, 'label': 'Hot cools s'}),
        ('Ash', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Ash (darken over life)'}),
        ('Blend', 'Menu', 'over', {'names': ['over', 'add'], 'labels': ['Over', 'Add (glow)']}),
        ('Back', 'Menu', 'dim', {'names': ['dim', 'alpha'], 'labels': ['Dimmed picture', 'Transparent']}),
        ('Backdim', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Back dim (0 = black)'}),
    ]),
    MASK_PAGE, POINT_PAGE, STATE_PAGE,          # shared pages (rack builders/fx_destroy.py)
]
PANEL_PAGES = ['Disintegrate', 'Front', 'Dust', 'Point']

# Presets are FULL states over the module pars (T-124 (1): partial presets inherit the previous one).
BASE = {'Amount': 1.0, 'Mode': 0, 'Drive': 0, 'Auto': 0.0, 'Ignorehits': 0, 'Hold': 1.5, 'Return': 0.0,
        'Duration': 4.0, 'Front': 0, 'Frontangle': 20.0, 'Sweep': 2.5, 'Roughness': 0.5, 'Noisescale': 160.0,
        'Detail': 4, 'Jitter': 0.08, 'Reverse': 0, 'Edge': 0.3, 'Edgeglow': 0.0, 'Edgecolorr': 1.0,
        'Edgecolorg': 0.55, 'Edgecolorb': 0.2, 'Grain': 2, 'Size': 1.0, 'Shrink': 0.5, 'Windangle': 30.0,
        'Windspeed': 260.0, 'Cone': 35.0, 'Spread': 0.6, 'Blast': 0.0, 'Falloff': 0.5, 'Gravity': -60.0,
        'Drag': 1.0, 'Turbulence': 120.0, 'Turbscale': 140.0, 'Turbspeed': 0.6, 'Push': 0.0,
        'Pushradius': 200.0, 'Life': 2.2, 'Hot': 0.0, 'Hotcolorr': 1.0, 'Hotcolorg': 0.45, 'Hotcolorb': 0.1,
        'Hottime': 0.5, 'Ash': 0.4, 'Blend': 0, 'Back': 0, 'Backdim': 0.0, 'Seed': 1}


def _p(**kw):
    d = dict(BASE)
    d.update(kw)
    return d


PRESETS = [
    (1, 'snap', _p()),
    (2, 'ash sweep', _p(Frontangle=90.0, Sweep=3.0, Roughness=0.4, Edge=0.4, Edgeglow=1.5, Windangle=90.0,
                        Windspeed=70.0, Cone=60.0, Gravity=-260.0, Turbulence=220.0, Turbscale=110.0, Life=3.0,
                        Hot=0.85, Hottime=0.7, Ash=0.8, Blend=1, Seed=2)),
    (3, 'pixel blow', _p(Frontangle=0.0, Sweep=1.6, Roughness=0.15, Jitter=0.25, Grain=6, Size=0.9, Shrink=1.0,
                         Windangle=0.0, Windspeed=700.0, Cone=12.0, Spread=0.8, Gravity=0.0, Turbulence=30.0,
                         Life=1.5, Ash=0.0, Seed=3)),
    (4, 'radial + reassemble', _p(Front=1, Sweep=1.2, Roughness=0.35, Windspeed=0.0, Blast=500.0, Falloff=0.6,
                                  Drag=1.5, Gravity=0.0, Turbulence=160.0, Life=0.0, Hold=1.4, Return=1.6, Shrink=0.8,
                                  Ash=0.0, Edgeglow=0.6, Edgecolorr=0.4, Edgecolorg=0.8, Edgecolorb=1.0, Seed=4)),
    (5, 'assemble', _p(Mode=1, Front=3, Sweep=1.5, Roughness=1.0, Duration=1.8, Windangle=200.0, Windspeed=320.0,
                       Cone=50.0, Gravity=0.0, Turbulence=180.0, Life=0.0, Shrink=1.0, Ash=0.0, Seed=5)),
]

SPLAT_MAX = 12                  # GLSL loop bound for a particle's square (px per side): T-124, bounded loops

# Shared by dust and fx: the time model (age since the hit / Progress x Duration, flight time of one grain).
TIME_GLSL = """
uniform vec4 uT;   // now, mode (0 away, 1 assemble), drive (0 hits, 1 manual), manual time s
uniform vec4 uR;   // sweep s, fly-out (hold) s, return s, duration s
uniform vec4 uQ;   // amount, life s, -, -
bool ageNow(vec4 hit, out float age) {
    bool manual = uT.z > 0.5;
    age = manual ? uT.w : uT.x - hit.x;
    return manual ? uT.w > 0.0 : (hit.w == 7.0 && hit.x >= 0.0 && uT.x >= hit.x);
}
float flight(float age, float tb) {          // seconds of flight of a grain released at tb (0 = at rest, intact)
    if (tb < 0.0) return 0.0;                // protected by the mask
    if (int(uT.y + 0.5) == 1) return clamp(uR.w - (age - tb), 0.0, uR.w);     // assemble: lands at tb + Duration
    float tau = age - tb;
    if (tau <= 0.0) return 0.0;
    if (uR.z > 0.0) {                        // Return: out for Hold s, then retrace the path home over Return s
        if (tau >= uR.y + uR.z) return 0.0;
        if (tau > uR.y) tau = uR.y * (1.0 - smoothstep(uR.y, uR.y + uR.z, tau));
    }
    return tau;
}
"""

GRAINS = """// disintegrate grains (compute 8x8, one texel per grain, rgba32float). in0 = picture, in1 = mask_src, in2 = hit.
// r = release time tb s after the hit (-1 = protected), g = front value 0..1, b = mask. Extra top row, texel 0 = a
// copy of the hit latch texel (fx reads it here: a GLSL TOP takes 3 inputs, T-123).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS;   // seed, W, H, grain px
uniform vec4 uF;   // front mode, wipe angle rad, roughness, jitter
uniform vec4 uJ;   // noise scale px, octaves, sweep s, reverse
uniform vec4 uC;   // live centre px x, y, drive (1 manual), -
""" + '%LIB%' + '%MASK%' + """
void main() {
    ivec2 g = ivec2(gl_GlobalInvocationID.xy);
    float G = max(1.0, uS.w);
    ivec2 gs = ivec2(ceil(uS.yz / G));
    vec4 hit = texelFetch(sTD2DInputs[2], ivec2(0, 0), 0);
    if (g.y == gs.y && g.x == 0) { TDImageStoreOutput(0, ivec3(g, 0), hit); return; }
    if (g.x >= gs.x || g.y >= gs.y) return;
    vec2 rest = (vec2(g) + 0.5) * G;
    vec2 uv = rest / uS.yz;
    vec2 ctr = uC.z > 0.5 ? uC.xy : hit.yz;
    vec3 col = texture(sTD2DInputs[0], uv).rgb;
    float m = fxMask(uv, col);
    int mode = int(uF.x + 0.5);
    uint sd = uint(uS.x) * 7919u;
    if (mode != 5 && m < 0.5) { TDImageStoreOutput(0, ivec3(g, 0), vec4(-1.0, 0.0, m, 0.0)); return; }
    float n = clamp((fbm(rest / max(uJ.x, 1.0), sd + 13u, int(uJ.y + 0.5)) - 0.25) * 2.0, 0.0, 1.0);
    float f0;
    if (mode == 0) {
        vec2 d = vec2(cos(uF.y), sin(uF.y));
        float a = 0.0, b = dot(uS.yz, d), c = uS.y * d.x, e = uS.z * d.y;
        float mn = min(min(a, b), min(c, e)), mx = max(max(a, b), max(c, e));
        f0 = (dot(rest, d) - mn) / max(mx - mn, 1e-3);
    } else if (mode == 1 || mode == 2) {
        float md = max(max(length(ctr), length(ctr - vec2(uS.y, 0.0))), max(length(ctr - vec2(0.0, uS.z)),
                                                                          length(ctr - uS.yz)));
        f0 = length(rest - ctr) / max(md, 1e-3);
        if (mode == 2) f0 = 1.0 - f0;
    } else if (mode == 3) f0 = n;
    else if (mode == 4) f0 = 1.0 - luma(col);
    else f0 = 1.0 - m;
    float f = mix(f0, n, uF.z);
    if (uJ.w > 0.5) f = 1.0 - f;
    f += uF.w * (hsh3(ivec3(g, 9), sd) - 0.5);
    f = clamp(f, 0.0, 1.0);
    TDImageStoreOutput(0, ivec3(g, 0), vec4(uJ.z * f, f, m, 0.0));
}
"""

DUST = """// disintegrate dust (compute 8x8 dispatched over the grains, output full res rgba16float, cleared every cook).
// in0 = picture, in1 = grains, in2 = hit. Each released grain is one particle drawn as a square (last write wins).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS;   // seed, W, H, grain px
uniform vec4 uW;   // wind dir x, y (unit), wind px/s, cone rad
uniform vec4 uV;   // speed variety, blast px/s, blast falloff, gravity px/s2 (+ = down)
uniform vec4 uU;   // turbulence px/s, turbulence scale px, evolve /s, drag
uniform vec4 uZ;   // size (x grain), size at end of life, -, -
uniform vec4 uP;   // live centre px x, y (Effector / Point), push px, push radius px
uniform vec4 uO;   // hot rgb, hot amount
uniform vec4 uN;   // hot cools s, ash, -, -
""" + '%LIB%' + '%TIME%' + """
float integ(float k, float t) { return k > 1e-4 ? (1.0 - exp(-k * t)) / k : t; }
vec2 curl(vec2 q, uint s) {                  // curl of value noise (finite differences), about unit size
    const float e = 0.35;
    float nx = vnoise(q + vec2(e, 0.0), s) - vnoise(q - vec2(e, 0.0), s);
    float ny = vnoise(q + vec2(0.0, e), s) - vnoise(q - vec2(0.0, e), s);
    return vec2(ny, -nx) / (2.0 * e);
}
void main() {
    ivec2 g = ivec2(gl_GlobalInvocationID.xy);
    ivec2 gs = textureSize(sTD2DInputs[1], 0) - ivec2(0, 1);     // last row = hit copy
    if (g.x >= gs.x || g.y >= gs.y) return;
    vec4 hit = texelFetch(sTD2DInputs[2], ivec2(0, 0), 0);
    float age;
    if (!ageNow(hit, age) || uQ.x <= 0.0) return;
    float tb = texelFetch(sTD2DInputs[1], g, 0).x;
    float tau = flight(age, tb);
    if (tau <= 0.0) return;
    float life = uQ.y;
    float lt = life > 0.0 ? clamp(tau / life, 0.0, 1.0) : 0.0;
    float al = life > 0.0 ? 1.0 - smoothstep(0.3 * life, life, tau) : 1.0;
    al = mix(1.0, al, uQ.x);
    if (al <= 0.002) return;
    float G = max(1.0, uS.w);
    vec2 rest = (vec2(g) + 0.5) * G;
    uint sd = uint(uS.x) * 7919u;
    float h1 = hsh3(ivec3(g, 1), sd), h2 = hsh3(ivec3(g, 2), sd), h3 = hsh3(ivec3(g, 3), sd);
    float h4 = hsh3(ivec3(g, 4), sd);
    float an = (h1 - 0.5) * uW.w, ca = cos(an), sa = sin(an);
    vec2 dir = vec2(ca * uW.x - sa * uW.y, sa * uW.x + ca * uW.y);
    float sp = uW.z * (1.0 - 0.5 * uV.x + uV.x * h2);
    bool manual = uT.z > 0.5;
    vec2 ctr = manual ? uP.xy : hit.yz;
    vec2 r = rest - ctr;
    float rl = length(r);
    float d = rl / length(uS.yz);
    vec2 dout = rl > 1e-3 ? r / rl : vec2(0.0, 1.0);
    vec2 v0 = dout * uV.y * exp(-uV.z * d * 4.0) * (0.5 + h3);
    vec2 pos = rest + dir * sp * tau + v0 * integ(uU.w, tau) - vec2(0.0, 0.5 * uV.w * tau * tau);
    if (uU.x != 0.0) {
        vec2 q = (rest + dir * sp * tau * 0.5) / max(uU.y, 1.0) + vec2(0.0, tau * uU.z);
        pos += curl(q, sd + 31u) * uU.x * tau * (0.5 + h4);
    }
    if (uP.z != 0.0) {
        vec2 pp = pos - uP.xy;
        float dl = length(pp);
        pos += (dl > 1e-3 ? pp / dl : dout) * uP.z * exp(-(dl * dl) / max(uP.w * uP.w, 1.0)) * min(tau * 4.0, 1.0);
    }
    pos = rest + (pos - rest) * uQ.x;
    vec4 c = texture(sTD2DInputs[0], rest / uS.yz);
    c.rgb = mix(c.rgb, uO.rgb, uO.w * exp(-tau / max(uN.x, 1e-3)));
    c.rgb *= 1.0 - uN.y * lt;
    c.a *= al;
    float s = uZ.x * G * mix(1.0, uZ.y, lt);
    int si = clamp(int(s + 0.5), 1, @SPLAT@);
    ivec2 o = ivec2(floor(pos - 0.5 * float(si) + 0.5));
    ivec2 W = ivec2(uS.yz);
    for (int y = 0; y < @SPLAT@; y++) {
        if (y >= si) break;
        for (int x = 0; x < @SPLAT@; x++) {
            if (x >= si) break;
            ivec2 q = o + ivec2(x, y);
            if (q.x >= 0 && q.y >= 0 && q.x < W.x && q.y < W.y) TDImageStoreOutput(0, ivec3(q, 0), c);
        }
    }
}
"""

FX = """// disintegrate fx (compute 16x16, format useinput). in0 = picture, in1 = grains (+ hit copy row), in2 = dust.
// Remnant = intact grains (texelFetch, exact) / released = Back; edge glow before release; dust over / added.
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uS;   // seed, W, H, grain px
uniform vec4 uA;   // back (0 dim, 1 alpha), backdim, edge s, edge glow
uniform vec4 uK;   // edge rgb, blend (0 over, 1 add)
""" + '%TIME%' + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    vec4 hit = texelFetch(sTD2DInputs[1], ivec2(0, textureSize(sTD2DInputs[1], 0).y - 1), 0);
    float age;
    if (!ageNow(hit, age) || uQ.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c0); return; }
    int G = max(1, int(uS.w + 0.5));
    float tb = texelFetch(sTD2DInputs[1], p / G, 0).x;
    float tau = flight(age, tb);
    vec4 back = int(uA.x + 0.5) == 1 ? vec4(0.0) : vec4(c0.rgb * uA.y, c0.a);
    vec4 o = tau > 0.0 ? mix(c0, back, uQ.x) : c0;
    if (tau <= 0.0 && tb >= 0.0 && uA.z > 0.0 && uA.w > 0.0) {
        float dt = int(uT.y + 0.5) == 1 ? age - tb - uR.w : tb - age;   // away: before release; assemble: after landing
        if (dt >= 0.0 && dt < uA.z) { float k = 1.0 - dt / uA.z; o.rgb += uK.rgb * uA.w * k * k * uQ.x; }
    }
    vec4 d = texelFetch(sTD2DInputs[2], p, 0);
    if (d.a > 0.0) {
        if (uK.w > 0.5) { o.rgb += d.rgb * d.a; o.a = max(o.a, d.a); }
        else { o.rgb = mix(o.rgb, d.rgb, d.a); o.a = d.a + o.a * (1.0 - d.a); }
    }
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
"""

P = "parent().par.{}.eval()"
GR = 'max(1, int(%s))' % P.format('Grain')


def _explode():
    """explode's module namespace (hit latch shader + Beat CHOP exec are reused as they are)."""
    ns = dict(globals())
    with open(os.path.join(HERE, 'fx_destroy_explode.py')) as fh:
        exec(fh.read(), ns)
    return ns


def shader_texts(lib, mask):
    """grains / dust / fx with the rack GLSL lib, mask GLSL and time model filled in; hit = explode's latch."""
    out = {'hit': _explode()['HIT']}
    for k, t in (('grains', GRAINS), ('dust', DUST), ('fx', FX)):
        for a, b in (('%LIB%', lib), ('%MASK%', mask), ('%TIME%', TIME_GLSL), ('@SPLAT@', str(SPLAT_MAX))):
            t = t.replace(a, b)
        out[k] = t
    return out


def time_uniforms():
    return [('uT', ['absTime.seconds', 'parent().par.Mode.menuIndex', 'parent().par.Drive.menuIndex',
                    '%s * %s' % (P.format('Progress'), P.format('Duration'))]),
            ('uR', [P.format('Sweep'), P.format('Hold'), P.format('Return'), P.format('Duration')]),
            ('uQ', [P.format('Amount'), P.format('Life'), '0', '0'])]


def build(m, H):
    """Fill instance COMP m: hit (explode's latch) -> grains (grain res) -> dust (scatter) -> fx -> out1."""
    mk, expr, compute, pt = H['mk'], H['expr'], H['compute'], H['pt_expr']
    X = _explode()
    tx = shader_texts(H['GLSL_LIB'], H['mask_glsl'](1))
    in1 = mk(m, inTOP, 'in1')
    H['pulse_exec'](m, ['Trigger', 'Reset'])
    _mn, ms = H['mask_ops'](m)
    be = mk(m, chopexecuteDAT, 'beat_exec')
    if be.text != X['BEAT_EXEC']:
        be.text = X['BEAT_EXEC']
    expr(be.par.chop, "parent().par.Beatchop.eval().path if parent().par.Beatchop.eval() is not None else ''")
    expr(be.par.active, "parent().par.Beatchop.eval() is not None")
    be.par.offtoon = True
    be.par.valuechange = False
    be.comment = 'Beat CHOP (Disintegrate page) rising edge -> Hittime.'
    W, Hh = "op('in1').width", "op('in1').height"
    ctr = ['%s * %s' % (pt('u'), W), '%s * %s' % (pt('v'), Hh)]
    # explode's latch: mode 2 = finite run (Duration + Sweep), else Return > 0 -> Sweep + Hold + Return (uE.x x 1.7)
    hit = compute(m, 'hit', tx['hit'], [], 2, 1, fmt='rgba32float', readwrite=True,
                  uniforms=[('uA', ['absTime.seconds', H['hit'](), H['stamp']('Resettime'),
                                    'float(%s)' % P.format('Ignorehits')]),
                            ('uB', ctr + ['parent().par.Mode.menuIndex * 2', '0']),
                            ('uE', ['%s / 1.7' % P.format('Sweep'), P.format('Hold'), P.format('Return'),
                                    P.format('Duration')])])
    hit.comment = 'hit latch (explode\'s shader): texel 0 = hit time, centre px, 7; texel 1 = last seen hit/reset.'
    uS = ('uS', [P.format('Seed'), W, Hh, GR])
    gw, gh = 'math.ceil(%s / %s)' % (W, GR), 'math.ceil(%s / %s)' % (Hh, GR)
    gr = compute(m, 'grains', tx['grains'], [in1, ms, hit], gw, gh + ' + 1', fmt='rgba32float', extend='hold',
                 uniforms=[uS,
                           ('uF', ['parent().par.Front.menuIndex', 'math.radians(%s)' % P.format('Frontangle'),
                                   P.format('Roughness'), P.format('Jitter')]),
                           ('uJ', [P.format('Noisescale'), P.format('Detail'), P.format('Sweep'),
                                   'float(%s)' % P.format('Reverse')]),
                           ('uC', ctr + ['parent().par.Drive.menuIndex', '0'])] + H['MASK_UNIFORMS'])
    gr.comment = 'grains: release time per grain (front + noise + jitter, Mask < 0.5 = kept); one texel per grain.'
    wa = 'math.radians(%s)' % P.format('Windangle')
    du = compute(m, 'dust', tx['dust'], [in1, gr, hit], W, Hh, fmt='rgba16float', extend='hold',
                 uniforms=[uS,
                           ('uW', ['math.cos(%s)' % wa, 'math.sin(%s)' % wa, P.format('Windspeed'),
                                   'math.radians(%s)' % P.format('Cone')]),
                           ('uV', [P.format('Spread'), P.format('Blast'), P.format('Falloff'), P.format('Gravity')]),
                           ('uU', [P.format('Turbulence'), P.format('Turbscale'), P.format('Turbspeed'),
                                   P.format('Drag')]),
                           ('uZ', [P.format('Size'), P.format('Shrink'), '0', '0']),
                           ('uP', ctr + [P.format('Push'), P.format('Pushradius')]),
                           ('uO', [P.format('Hotcolorr'), P.format('Hotcolorg'), P.format('Hotcolorb'),
                                   P.format('Hot')]),
                           ('uN', [P.format('Hottime'), P.format('Ash'), '0', '0'])] + time_uniforms())
    du.par.clearoutputs = True                       # dust is drawn fresh every cook (nothing written = alpha 0)
    du.par.autodispatchsize = False                  # one thread per grain, not per output pixel
    expr(du.par.dispatchsizex, 'math.ceil(%s / 8)' % gw)
    expr(du.par.dispatchsizey, 'math.ceil(%s / 8)' % gh)
    du.par.dispatchsizez = 1
    du.comment = 'dust: one thread per grain; released grains fly (wind cone, blast, drag, lift, curl turbulence, push).'
    g = compute(m, 'fx', tx['fx'], [in1, gr, du], 'me.inputs[0].width', 'me.inputs[0].height',
                uniforms=[uS,
                          ('uA', ['parent().par.Back.menuIndex', P.format('Backdim'), P.format('Edge'),
                                  P.format('Edgeglow')]),
                          ('uK', [P.format('Edgecolorr'), P.format('Edgecolorg'), P.format('Edgecolorb'),
                                  'parent().par.Blend.menuIndex'])] + time_uniforms())
    g.comment = 'disintegrate: remnant (intact = exact picture, released = Back) + edge glow + dust (DG-17).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulse_exec', 'beat_exec', 'mask_none', 'mask_src'],
         'body': 'Picture; Trigger / Reset pulses + Beat CHOP -> Hittime / Resettime; Mask source.'},
        {'title': '2 Disintegrate', 'role': 'process', 'ops': ['hit', 'hit_compute', 'grains', 'grains_compute',
                                                               'dust', 'dust_compute', 'fx', 'fx_compute'],
         'body': 'hit: latch. grains: release time per grain. dust: analytic particles drawn. fx: remnant + dust.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
