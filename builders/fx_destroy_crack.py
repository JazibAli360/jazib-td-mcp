# fx_destroy_crack - FX_destroy module 'crack' (FX1 DG-16 / FX4 D5: glass crack, broken LCD, dead pixels, stuck lines).
# Module file = PAGES + PRESETS + build(m, H) (template: docs/builds/fx_glitch.md; rack: builders/fx_destroy.py).
# Glass: log-polar Voronoi around each impact (cells shrink as 1/r = radial spokes + concentric rings), crack lines =
# distance to the cell edges converted to screen px through the log-polar Jacobian, each edge with its own reach
# (jagged front), ring edges thinned by Ringcracks, a finer Detail layer, a crushed Core, per-cell refraction + tint,
# Chips (cells near the impact fall out to Back). LCD: ink blot with spectral halo, bleed bars from the impact, stuck
# lines (black / colour / smeared pixel), dead + stuck-on pixel clusters, Flicker.
# Impacts: Source point = one crack at the Point / Effector Null (follows it, size = Radius); Source hits = each
# Trigger / Beat CHOP rising edge / Auto period stores a hit (up to Maxhits, ring) in `hits` (compute 9x1
# rgba32float in place, FX6 probe 5a pattern), which then grows at Speed and fades after Fade s.
# `fx` = ONE compute pass (T-46/T-47), bars + lines precomputed per workgroup in shared memory. Amount 0 = exact
# passthrough; pixels no part touches are written from texelFetch (exact). numpy reference: fx_destroy_crack_logic.py.
# ASCII only.

MODULE = 'crack'

PAGES = [
    ('Crack', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Source', 'Menu', 'point', {'names': ['point', 'hits'], 'labels': ['Point / Effector (live)',
                                                                          'Hits (Trigger / beat / Auto)']}),
        ('Trigger', 'Pulse', None, {'label': 'Trigger (hit)'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (clear hits)'}),
        ('Auto', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Auto hit every s (0 = off)'}),
        ('Beatchop', 'CHOP', '', {'label': 'Beat CHOP (rising edge hits)'}),
        ('Maxhits', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Max hits kept'}),
        ('Scatter', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Hit scatter (0 = at Point)'}),
        ('Speed', 'Float', 4.0, {'min': 0.1, 'max': 20, 'label': 'Growth speed (1/s)'}),
        ('Fade', 'Float', 0.0, {'min': 0, 'max': 20, 'label': 'Fade s (0 = never)'}),
        ('Radius', 'Float', 0.6, {'min': 0, 'max': 2, 'label': 'Radius (x height)'}),
        ('Radials', 'Int', 14, {'min': 3, 'max': 48, 'label': 'Radial cracks'}),
        ('Rings', 'Float', 1.6, {'min': 0.3, 'max': 6, 'label': 'Ring density'}),
        ('Ringcracks', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Ring cracks'}),
        ('Jitter', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Jitter'}),
        ('Wobble', 'Float', 3.0, {'min': 0, 'max': 30, 'label': 'Wobble px'}),
        ('Detail', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Fine cracks'}),
        ('Core', 'Float', 18.0, {'min': 0, 'max': 200, 'label': 'Crushed core px'}),
        ('Crackwidth', 'Float', 2.5, {'min': 0, 'max': 20, 'label': 'Crack width px'}),
        ('Crackglow', 'Float', 1.2, {'min': 0, 'max': 4, 'label': 'Crack glow'}),
        ('Crackdark', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Crack dark core'}),
        ('Refract', 'Float', 6.0, {'min': 0, 'max': 40, 'label': 'Refract px'}),
        ('Tint', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Piece tint'}),
        ('Chips', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Chips (holes)'}),
        ('Back', 'Menu', 'black', {'names': ['black', 'alpha'], 'labels': ['Black', 'Transparent']}),
        ('View', 'Menu', 'look', {'names': ['look', 'map'], 'labels': ['Look', 'Crack map (r line g chip b cell)']}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('LCD', [
        ('Ink', 'Float', 0.0, {'min': 0, 'max': 0.6, 'label': 'Ink blot (x height)'}),
        ('Inkhue', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Ink halo hue'}),
        ('Bars', 'Int', 0, {'min': 0, 'max': 32, 'label': 'Bleed bars per hit'}),
        ('Bardir', 'Menu', 'v', {'names': ['v', 'h', 'both'], 'labels': ['Vertical', 'Horizontal', 'Both']}),
        ('Barwidth', 'Float', 6.0, {'min': 0, 'max': 60, 'label': 'Bar width px'}),
        ('Barspread', 'Float', 0.3, {'min': 0, 'max': 1.5, 'label': 'Bar spread (x width)'}),
        ('Baropacity', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Bar opacity'}),
        ('Lines', 'Int', 0, {'min': 0, 'max': 64, 'label': 'Stuck lines'}),
        ('Linedir', 'Menu', 'v', {'names': ['v', 'h', 'both'], 'labels': ['Vertical', 'Horizontal', 'Both']}),
        ('Linewidth', 'Int', 1, {'min': 1, 'max': 8, 'label': 'Line width px'}),
        ('Dead', 'Float', 0.0, {'min': 0, 'max': 0.05, 'label': 'Dead clusters'}),
        ('Cluster', 'Int', 3, {'min': 1, 'max': 32, 'label': 'Cluster px'}),
        ('Clusterfill', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Cluster fill'}),
        ('Deadlit', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Stuck-on share'}),
        ('Flicker', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Bar / line flicker Hz'}),
    ]),
    ('Colours', [
        ('Crackcolor', 'RGB', (0.85, 0.93, 1.0), {'label': 'Crack glint'}),
    ]),
    POINT_PAGE, STATE_PAGE,                     # shared pages (rack builders/fx_destroy.py)
]
PANEL_PAGES = ['Crack', 'LCD', 'Colours', 'Point']

_OFF = {'Ink': 0.0, 'Bars': 0, 'Lines': 0, 'Dead': 0.0, 'Flicker': 0.0}
PRESETS = [
    (1, 'dropped phone', dict(_OFF, Amount=1.0, Source=0, Radius=0.9, Radials=16, Rings=1.8, Ringcracks=0.4,
                              Jitter=0.8, Wobble=3.0, Detail=0.6, Core=24.0, Crackwidth=2.5, Crackglow=1.3,
                              Crackdark=0.3, Refract=6.0, Tint=0.08, Chips=0.12, Back=0, Seed=1)),
    (2, 'bullet hole', dict(_OFF, Amount=1.0, Source=0, Radius=0.35, Radials=22, Rings=3.0, Ringcracks=0.7,
                            Jitter=0.9, Wobble=1.5, Detail=0.8, Core=40.0, Crackwidth=1.6, Crackglow=1.8,
                            Crackdark=0.2, Refract=10.0, Tint=0.12, Chips=0.35, Back=0, Seed=2)),
    (3, 'broken LCD', dict(_OFF, Amount=1.0, Source=0, Radius=0.25, Radials=10, Rings=1.4, Ringcracks=0.2,
                           Detail=0.3, Core=10.0, Crackwidth=3.0, Crackglow=0.4, Crackdark=0.9, Refract=3.0,
                           Chips=0.0, Ink=0.12, Inkhue=0.0, Bars=14, Bardir=2, Barwidth=8.0, Barspread=0.5,
                           Baropacity=1.0, Lines=6, Linedir=0, Linewidth=2, Dead=0.002, Cluster=3, Seed=3)),
    (4, 'dead LED wall', dict(_OFF, Amount=1.0, Source=0, Radius=0.0, Lines=12, Linedir=2, Linewidth=1,
                              Dead=0.004, Cluster=4, Clusterfill=0.6, Deadlit=0.35, Flicker=6.0, Seed=4)),
    (5, 'beat cracks', dict(_OFF, Amount=1.0, Source=1, Maxhits=4, Scatter=0.8, Speed=5.0, Fade=4.0, Auto=1.0,
                            Radius=0.38, Radials=12, Rings=1.6, Ringcracks=0.3, Detail=0.0, Core=14.0,
                            Crackwidth=2.2, Crackglow=1.4, Refract=5.0, Chips=0.08, Ink=0.05, Bars=4, Bardir=0,
                            Seed=5)),
]

HITS = """// crack hits (compute, rgba32float in place, 9 x 1; FX6 probe 5a). Texel 0..7 = hit x px, y px, time (-1 = empty),
// hit number (1..); texel 8 = seen trigger time, hits so far, 7 (initialised marker), last cook time. No inputs.
layout (local_size_x = 16, local_size_y = 1) in;
uniform vec4 uA;   // now, hit time (Trigger / beat / Auto), reset time, max hits
uniform vec4 uB;   // point px x, y, scatter, seed
uniform vec4 uC;   // W, H, -, -
""" + '%LIB%' + """
void main() {
    if (gl_GlobalInvocationID.x != 0u || gl_GlobalInvocationID.y != 0u) return;
    float now = uA.x;
    vec4 hd = TDImageLoadOutput(0, ivec3(8, 0, 0));
    // uA.y / uA.z come voided when later than now (rack stamp exprs, T-155); a seen hit stored by an older shader
    // from another clock is void too (no replay), else it blocks every later hit (T-160).
    if (!(hd.x <= now + 0.05)) hd.x = uA.y;
    // Reset: >= (a stamp equal to the last cook still resets, T-160); a hit stamped after the Reset is kept pending
    // (seen = the Reset time), so the second reset in the next frame does not swallow it.
    if (!(hd.z == 7.0) || uA.z >= hd.w) {                                 // fresh texture or Reset: empty, no replay
        for (int i = 0; i < 8; i++) TDImageStoreOutput(0, ivec3(i, 0, 0), vec4(0.0, 0.0, -1.0, 0.0));
        float seen = (hd.z == 7.0 && uA.y > uA.z) ? uA.z : uA.y;
        TDImageStoreOutput(0, ivec3(8, 0, 0), vec4(seen, 0.0, 7.0, now));
        return;
    }
    if (uA.y > hd.x + 1e-4 && uA.y <= now + 0.05) {                       // a new hit
        int n = int(hd.y + 0.5);
        int k = n % clamp(int(uA.w + 0.5), 1, 8);
        uint sd = uint(uB.w);
        vec2 rnd = vec2(hsh(ivec2(n, 1), sd + 70u), hsh(ivec2(n, 2), sd + 70u)) * uC.xy;
        vec2 pos = mix(uB.xy, rnd, clamp(uB.z, 0.0, 1.0));
        TDImageStoreOutput(0, ivec3(k, 0, 0), vec4(pos, uA.y, float(n + 1)));
        hd.x = uA.y;
        hd.y = float(n + 1);
    }
    hd.w = now;
    TDImageStoreOutput(0, ivec3(8, 0, 0), hd);
}
"""

FX = """// crack fx (compute 16x16, format useinput). in0 = picture, in1 = hits (Source hits) or 1x1 idle.
// Amount 0 = exact passthrough (texelFetch); untouched pixels are written from texelFetch too.
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uA;   // amount, source (0 point, 1 hits), now, view (0 look, 1 map)
uniform vec4 uP;   // point px x, y, radius px, core px
uniform vec4 uG;   // radials, rings per e-fold, jitter, wobble px
uniform vec4 uL;   // crack width px, glow, dark, refract px
uniform vec4 uK;   // crack rgb, chips
uniform vec4 uT;   // speed, fade s, max hits, detail
uniform vec4 uI;   // ink px, ink hue, bars per hit, bar spread px
uniform vec4 uJ;   // bar width px, bar dir, bar opacity, flicker hz
uniform vec4 uD;   // dead fraction, cluster px, stuck-on share, cluster fill
uniform vec4 uS;   // lines, line dir, line width px, seed
uniform vec4 uB;   // back (0 black, 1 alpha), tint, ring cracks, H px
""" + '%LIB%' + """
#define NB 256
shared vec4 sH[8];      // hit x, y, reach px, weight (0 = off)
shared vec4 sH2[8];     // ink px, growth 0..1, hit number, -
shared vec4 sBa[NB];    // axis (-1 = off), centre, half width, -
shared vec4 sBb[NB];    // along lo, along hi, colour, opacity
shared vec4 sLn[64];    // axis (-1 = off), first px, width px, kind + smear pos * 0.5
vec3 pal7(int i) {
    if (i == 0) return vec3(1.0, 0.0, 0.0);
    if (i == 1) return vec3(0.0, 1.0, 0.0);
    if (i == 2) return vec3(0.0, 0.0, 1.0);
    if (i == 3) return vec3(0.0, 1.0, 1.0);
    if (i == 4) return vec3(1.0, 0.0, 1.0);
    if (i == 5) return vec3(1.0, 1.0, 0.0);
    return vec3(1.0);
}
float ease3(float x) { x = clamp(x, 0.0, 1.0); return 1.0 - (1.0 - x) * (1.0 - x) * (1.0 - x); }
int wrapc(int x, int n) { return ((x % n) + n) % n; }
vec2 cellSeed(ivec2 k, int NR, uint s) {
    ivec2 kk = ivec2(wrapc(k.x, NR), k.y);
    return vec2(k) + 0.5 + (vec2(hsh(kk, s), hsh(kk, s + 1u)) - 0.5) * uG.z;
}
// One log-polar Voronoi crack layer. d = pixel - impact (px), R = reach px, w = crack width px.
// Returns the line strength 0..1; nrm = screen normal of that edge, bid = own cell id, rc = own cell seed radius px.
float glassLayer(vec2 d, float R, float NRf, float b, float w, uint s, out vec2 nrm, out int bid, out float rc) {
    int NR = max(3, int(NRf + 0.5));
    float a = float(NR) / 6.2831853;
    float rr = max(length(d), 1.0);
    float th = atan(d.y, d.x);
    vec2 q = vec2((th + 3.14159265) * a, log(rr) * b);
    ivec2 c = ivec2(floor(q));
    vec2 S[9];                                                              // 3x3 seeds, reused by the edge loop
    float d1 = 1e20; int bi = 4;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
        int ix = (j + 1) * 3 + i + 1;
        S[ix] = cellSeed(c + ivec2(i, j), NR, s); vec2 v = S[ix] - q; float dd = dot(v, v);
        if (dd < d1) { d1 = dd; bi = ix; }
    }
    ivec2 bo = ivec2(bi % 3 - 1, bi / 3 - 1);
    ivec2 bk = c + bo; vec2 s1 = S[bi];
    bid = bk.y * NR + wrapc(bk.x, NR);
    rc = exp(s1.y / b);
    vec2 tr = vec2(-sin(th), cos(th)), rd = vec2(cos(th), sin(th));
    float kmax = 0.0; nrm = rd;
    float taper = 1.0 - 0.6 * clamp(rr / max(R, 1.0), 0.0, 1.0);
    float wmax = w * taper;                                                 // widest any edge can be here
    if (wmax <= 0.0) return 0.0;
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
        if (i == 0 && j == 0) continue;
        ivec2 o2 = bo + ivec2(i, j);
        ivec2 k = c + o2;
        vec2 sn = (abs(o2.x) <= 1 && abs(o2.y) <= 1) ? S[(o2.y + 1) * 3 + o2.x + 1] : cellSeed(k, NR, s);
        vec2 n = sn - s1; float L = length(n);
        if (L < 1e-5) continue;
        n /= L;
        float e = dot(0.5 * (s1 + sn) - q, n);                              // log-polar distance to the bisector
        float g = sqrt(a * a * n.x * n.x + b * b * n.y * n.y);
        float epx = e * rr / max(g, 1e-6);                                  // -> screen px (Jacobian = diag(a, b) / r)
        if (epx >= wmax) continue;                                          // too far from this edge (exact skip)
        int nid = k.y * NR + wrapc(k.x, NR);
        ivec2 pr = ivec2(min(bid, nid), max(bid, nid));
        if (abs(n.y) * b > abs(n.x) * a && hsh(pr, s + 6u) >= uB.z) continue;   // ring edge, thinned
        float reach = R * (0.55 + 0.6 * hsh(pr, s + 5u));
        float wk = w * taper * (1.0 - smoothstep(reach * 0.8, reach, rr));
        if (wk <= 0.0) continue;
        float k1 = clamp(1.0 - epx / wk, 0.0, 1.0);
        if (k1 > kmax) { kmax = k1; nrm = normalize(a * n.x * tr + b * n.y * rd); }
    }
    return kmax;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    bool ok = p.x < isz.x && p.y < isz.y;
    vec4 c0 = ok ? texelFetch(sTD2DInputs[0], p, 0) : vec4(0.0);
    if (uA.x <= 0.0) { if (ok) TDImageStoreOutput(0, ivec3(p, 0), c0); return; }   // uniform: whole dispatch
    int lid = int(gl_LocalInvocationIndex);
    uint sd = uint(uS.w);
    float now = uA.z;
    bool hits = int(uA.y + 0.5) == 1;
    int nh = hits ? clamp(int(uT.z + 0.5), 1, 8) : 1;
    if (lid < 8) {                                                          // impacts -> shared
        vec4 h = vec4(0.0), h2 = vec4(0.0);
        if (!hits) {
            if (lid == 0) { h = vec4(uP.xy, uP.z, 1.0); h2 = vec4(uI.x, 1.0, 0.0, 0.0); }
        } else if (lid < nh) {
            vec4 t = texelFetch(sTD2DInputs[1], ivec2(lid, 0), 0);
            float age = now - t.z;
            if (t.z >= 0.0 && age >= 0.0) {
                float f = uT.y > 0.0 ? clamp(1.0 - age / uT.y, 0.0, 1.0) : 1.0;
                float g = ease3(age * uT.x);
                h = vec4(t.xy, uP.z * g, f);
                h2 = vec4(uI.x * sqrt(clamp(age * uT.x * 0.35, 0.0, 1.0)), g, t.w, 0.0);
            }
        }
        sH[lid] = h; sH2[lid] = h2;
    }
    barrier();
    int nb = clamp(int(uI.z + 0.5), 0, 32);
    {                                                                       // bleed bars -> shared (1 per thread)
        int bi = lid;
        int hi = bi / 32, j = bi % 32;
        vec4 A = vec4(-1.0), B = vec4(0.0);
        vec4 h = sH[hi], h2 = sH2[hi];
        if (j < nb && h.w > 0.0) {
            uint hs = sd + uint(h2.z) * 977u + 3u;
            float r1 = hsh(ivec2(j, 1), hs), r2 = hsh(ivec2(j, 2), hs), r3 = hsh(ivec2(j, 3), hs);
            float r4 = hsh(ivec2(j, 4), hs);
            int dir = int(uJ.y + 0.5);
            int ax = dir == 2 ? (j & 1) : dir;
            float pos = (ax == 0 ? h.x : h.y) + (r1 - 0.5) * uI.w;
            float ext = h2.y * uB.w * (0.25 + 1.5 * r3);
            float along = ax == 0 ? h.y : h.x;
            bool on = uJ.w <= 0.0 || hsh(ivec2(j, int(floor(now * uJ.w))), hs + 9u) > 0.3;
            if (on) {
                A = vec4(float(ax), pos, 0.5 * (1.0 + floor(r2 * uJ.x)), 0.0);
                B = vec4(along - ext, along + ext, floor(r4 * 7.0), h.w * uJ.z);
            }
        }
        sBa[bi] = A; sBb[bi] = B;
    }
    {                                                                       // stuck lines -> shared (1 per thread)
        vec4 Ln = vec4(-1.0);
        if (lid < clamp(int(uS.x + 0.5), 0, 64)) {
            float r1 = hsh(ivec2(lid, 11), sd), r2 = hsh(ivec2(lid, 12), sd), r3 = hsh(ivec2(lid, 13), sd);
            int dir = int(uS.y + 0.5);
            int ax = dir == 2 ? (lid & 1) : dir;
            float pos = floor(r1 * float(ax == 0 ? isz.x : isz.y));
            bool on = uJ.w <= 0.0 || hsh(ivec2(lid + 100, int(floor(now * uJ.w))), sd + 9u) > 0.3;
            if (on) Ln = vec4(float(ax), pos, max(1.0, floor(uS.z + 0.5)), floor(r2 * 9.0) + r3 * 0.5);
        }
        if (lid < 64) sLn[lid] = Ln;
    }
    barrier();
    if (!ok) return;
    vec2 pc = vec2(p) + 0.5;
    vec2 disp = vec2(0.0), nrmB = vec2(0.0);
    float line = 0.0, chip = 0.0, cmap = 0.0, tint = 0.0, kB = 0.0, inkA = 0.0, inkCore = 0.0;
    vec3 inkc = vec3(0.0);
    bool touched = false;
    for (int i = 0; i < nh; i++) {
        vec4 h = sH[i];
        if (h.w <= 0.0) continue;
        vec4 h2 = sH2[i];
        uint hs = sd + uint(h2.z) * 977u;
        vec2 d = pc - h.xy;
        float r = length(d), R = h.z;
        if (R > 0.0 && r < R * 1.15 + uG.w + 2.0) {                         // glass
            vec2 dw = d;
            if (uG.w > 0.0) dw += uG.w * (vec2(vnoise(pc / 40.0, hs + 60u), vnoise(pc / 40.0 + 19.3, hs + 61u)) * 2.0 - 1.0);
            vec2 n1; int bid; float rc;
            float k1 = glassLayer(dw, R, uG.x, uG.y, uL.x, hs, n1, bid, rc) * h.w;
            if (k1 > kB) { kB = k1; nrmB = n1; }
            line = max(line, k1);
            if (rc < R * 0.9) {                                             // a cracked piece
                float fall = clamp(1.0 - r / max(R, 1.0), 0.0, 1.0) * (1.0 - smoothstep(R * 0.5, R * 0.9, rc));
                disp += (vec2(hsh(ivec2(bid, 2), hs), hsh(ivec2(bid, 3), hs)) - 0.5) * uL.w * 0.5 * fall * h.w;
                tint += (hsh(ivec2(bid, 4), hs) - 0.5) * uB.y * h.w * (1.0 - smoothstep(R * 0.5, R * 0.9, rc));
                cmap = max(cmap, hsh(ivec2(bid, 7), hs));
                if (hsh(ivec2(bid, 9), hs) < uK.w * clamp(1.0 - rc / (R * 0.6), 0.0, 1.0)) chip = max(chip, h.w);
                touched = true;
            }
            if (uT.w > 0.0 && r < R * 0.69 + 1.5 * uG.w + 2.0) {            // fine cracks (reach <= 0.69 R)
                vec2 n2; int bid2; float rc2;
                float k2 = glassLayer(dw, R * 0.6, uG.x * 2.3, uG.y * 2.0, uL.x * 0.5, hs + 101u, n2, bid2, rc2)
                           * uT.w * h.w;
                if (k2 > kB) { kB = k2; nrmB = n2; }
                line = max(line, k2);
            }
            if (uP.w > 0.0 && r < uP.w) {                                   // crushed core
                float kc = (1.0 - smoothstep(uP.w * 0.4, uP.w, r)) * h.w;
                ivec2 g2 = ivec2(floor(pc / 2.0)), g3 = ivec2(floor(pc / 3.0));
                line = max(line, kc * (0.4 + 0.6 * hsh(g2, hs + 30u)));
                disp += (vec2(hsh(g3, hs + 31u), hsh(g3, hs + 32u)) - 0.5) * uL.w * 2.0 * kc;
                touched = true;
            }
            if (line > 0.0) touched = true;
        }
        float Ri = h2.x;                                                    // ink blot
        if (Ri > 0.5) {
            vec2 qi = d / Ri;
            float L = length(qi);
            if (L < 1.6) {
                float n = fbm(qi * 2.0 + vec2(h2.z * 7.31, 3.7), hs + 21u, 3);
                float dd = L / (0.6 + 0.8 * n);
                if (dd < 1.0) {
                    inkCore = max(inkCore, (1.0 - smoothstep(0.45, 0.6, dd)) * h.w);
                    float ha = (1.0 - smoothstep(0.75, 1.0, dd)) * 0.9 * h.w;
                    if (ha > inkA) { inkA = ha; inkc = 0.5 + 0.5 * cos(6.2831853 * (dd * 1.3 + uI.y + vec3(0.0, 0.33, 0.67))); }
                    touched = true;
                }
            }
        }
    }
    vec4 o = c0;
    if (touched) {
        vec2 off = disp - nrmB * uL.w * kB * kB;
        if (off != vec2(0.0)) o = texture(sTD2DInputs[0], (pc + off) / vec2(isz));
        o.rgb = o.rgb * (1.0 + tint) * (1.0 - uL.z * line) + uK.rgb * uL.y * line * line;
        o.rgb = mix(o.rgb, inkc, inkA) * (1.0 - inkCore);
        if (chip > 0.0) o = mix(o, int(uB.x + 0.5) == 1 ? vec4(0.0) : vec4(0.0, 0.0, 0.0, c0.a), chip);
    }
    for (int bh = 0; bh < nh; bh++) for (int bj = 0; bj < nb; bj++) {      // bleed bars (only the used ones)
        int bi = bh * 32 + bj;
        vec4 A = sBa[bi];
        if (A.x < 0.0) continue;
        vec4 B = sBb[bi];
        float u = A.x < 0.5 ? pc.x : pc.y, v = A.x < 0.5 ? pc.y : pc.x;
        if (abs(u - A.y) < A.z && v > B.x && v < B.y) o.rgb = mix(o.rgb, pal7(int(B.z)), B.w);
    }
    int nl = clamp(int(uS.x + 0.5), 0, 64);
    for (int i = 0; i < nl; i++) {                                          // stuck lines (exact px)
        vec4 Ln = sLn[i];
        if (Ln.x < 0.0) continue;
        bool vert = Ln.x < 0.5;
        int cc = vert ? p.x : p.y, p0 = int(Ln.y);
        if (cc >= p0 && cc < p0 + int(Ln.z)) {
            int kind = int(floor(Ln.w));
            if (kind == 0) o.rgb = vec3(0.0);
            else if (kind < 8) o.rgb = pal7(kind - 1);
            else {
                float sp = fract(Ln.w) * 2.0;
                ivec2 q = vert ? ivec2(p.x, min(isz.y - 1, int(sp * float(isz.y)))) : ivec2(min(isz.x - 1, int(sp * float(isz.x))), p.y);
                o.rgb = texelFetch(sTD2DInputs[0], q, 0).rgb;
            }
        }
    }
    if (uD.x > 0.0) {                                                       // dead / stuck-on pixel clusters (exact px)
        ivec2 cl = p / max(1, int(uD.y + 0.5));
        if (hsh(cl, sd + 40u) < uD.x && hsh(p, sd + 41u) < uD.w) {
            int t = int(floor(hsh(cl, sd + 43u) * 4.0));
            o.rgb = hsh(cl, sd + 42u) < uD.z ? (t == 3 ? vec3(1.0) : pal7(t)) : vec3(0.0);
        }
    }
    if (int(uA.w + 0.5) == 1) o = vec4(line, chip, cmap, 1.0);
    else o = mix(c0, o, uA.x);
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
"""

BEAT_EXEC = """# Beat CHOP rising edge -> Hittime (the crack hits shader stores a hit).
def onOffToOn(channel, sampleIndex, val, prev):
    parent().par.Hittime.val = absTime.seconds
    return
"""

P = "parent().par.{}.eval()"


def shader_texts(lib):
    """The two compute shaders with the rack's GLSL_LIB inlined (tests compile these with glslc)."""
    return {'hits': HITS.replace('%LIB%', lib), 'fx': FX.replace('%LIB%', lib)}


def build(m, H):
    """Fill instance COMP m: hits (9x1 state, in place) / idle -> hit_sel -> fx (+ in1) -> out1, + pulse/beat."""
    mk, expr, compute, pt = H['mk'], H['expr'], H['compute'], H['pt_expr']
    tx = shader_texts(H['GLSL_LIB'])
    in1 = mk(m, inTOP, 'in1')
    H['pulse_exec'](m, ['Trigger', 'Reset'])
    be = mk(m, chopexecuteDAT, 'beat_exec')
    if be.text != BEAT_EXEC:
        be.text = BEAT_EXEC
    expr(be.par.chop, "parent().par.Beatchop.eval().path if parent().par.Beatchop.eval() is not None else ''")
    expr(be.par.active, "parent().par.Beatchop.eval() is not None")
    be.par.offtoon = True
    be.par.valuechange = False
    be.comment = 'Beat CHOP (Crack page) rising edge -> Hittime.'
    idle = mk(m, constantTOP, 'idle')
    idle.par.outputresolution = 'custom'
    idle.par.resolutionw, idle.par.resolutionh = 1, 1
    idle.comment = '1x1: fx input 1 while Source = point, so the hits state is not pulled.'
    W, Hh = "op('in1').width", "op('in1').height"
    st = compute(m, 'hits', tx['hits'], [], 9, 1, fmt='rgba32float', readwrite=True,     # stamps voided: T-155
                 uniforms=[('uA', ['absTime.seconds', H['hit'](), H['stamp']('Resettime'), P.format('Maxhits')]),
                           ('uB', ['%s * %s' % (pt('u'), W), '%s * %s' % (pt('v'), Hh), P.format('Scatter'),
                                   P.format('Seed')]),
                           ('uC', [W, Hh, '0', '0'])])
    st.comment = 'crack hits: texel 0..7 = x, y, time, number; texel 8 = seen, count, 7, last cook (in place).'
    sel = mk(m, switchTOP, 'hit_sel')
    sel.inputConnectors[0].connect(idle)
    sel.inputConnectors[1].connect(st)
    expr(sel.par.index, "1 if parent().par.Source.eval() == 'hits' else 0")
    sel.comment = 'Source point: idle (hits not cooked). Source hits: the hits state.'
    w, h = 'me.inputs[0].width', 'me.inputs[0].height'
    g = compute(m, 'fx', tx['fx'], [in1, sel], w, h, extend='hold',
                uniforms=[('uA', [P.format('Amount'), 'parent().par.Source.menuIndex', 'absTime.seconds',
                                  'parent().par.View.menuIndex']),
                          ('uP', ['%s * %s' % (pt('u'), w), '%s * %s' % (pt('v'), h),
                                  '%s * %s' % (P.format('Radius'), h), P.format('Core')]),
                          ('uG', [P.format('Radials'), P.format('Rings'), P.format('Jitter'), P.format('Wobble')]),
                          ('uL', [P.format('Crackwidth'), P.format('Crackglow'), P.format('Crackdark'),
                                  P.format('Refract')]),
                          ('uK', [P.format('Crackcolorr'), P.format('Crackcolorg'), P.format('Crackcolorb'),
                                  P.format('Chips')]),
                          ('uT', [P.format('Speed'), P.format('Fade'), P.format('Maxhits'), P.format('Detail')]),
                          ('uI', ['%s * %s' % (P.format('Ink'), h), P.format('Inkhue'), P.format('Bars'),
                                  '%s * %s' % (P.format('Barspread'), w)]),
                          ('uJ', [P.format('Barwidth'), 'parent().par.Bardir.menuIndex', P.format('Baropacity'),
                                  P.format('Flicker')]),
                          ('uD', [P.format('Dead'), P.format('Cluster'), P.format('Deadlit'),
                                  P.format('Clusterfill')]),
                          ('uS', [P.format('Lines'), 'parent().par.Linedir.menuIndex', P.format('Linewidth'),
                                  P.format('Seed')]),
                          ('uB', ['parent().par.Back.menuIndex', P.format('Tint'), P.format('Ringcracks'), h])])
    g.comment = ('crack: log-polar Voronoi glass + LCD ink / bars / stuck lines / dead pixels (DG-16), one compute '
                 'pass. Amount 0 = exact passthrough.')
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulse_exec', 'beat_exec', 'idle'],
         'body': 'Picture; Trigger / Reset pulses + Beat CHOP -> Hittime / Resettime.'},
        {'title': '2 Crack', 'role': 'process', 'ops': ['hits', 'hits_compute', 'hit_sel', 'fx', 'fx_compute'],
         'body': 'hits: impact list (9x1, in place; Source hits only). fx: glass + LCD in one pass.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
