# fx_glitch_pixelsort - FX_glitch module 'pixelsort' (FX1 DG-04): a TRUE pixel sort (Asendorf intervals), not a smear.
# FX6 recipe: one compute pass, segmented bitonic sort in shared memory (2048 elements per workgroup of 1024 threads,
# split into Chunk-sized blocks); interval id in the high key bits, quantised sort key in the middle, the element index
# in the low bits (bitonic is not stable: without it tied pixels shuffle every frame).
# Passes: sort (writes a rgba32float work map: xy = source pixel that lands here, zw = own pixel) -> fx (gathers the
# picture through the map, Amount mix) -> out_sel (Amount 0 = in1 straight, exact, sort not cooked) -> out1.
# Direction H / V sort rows / columns in place; Angle sorts lines of a rotated work frame and maps back (nearest).
# Method Lite (TC-24, masked pixel-stretch streaks): no sort; `lite` keeps a trail state (rgba32float, one extra row
# = its cook clock) through a Feedback TOP: pixels inside the threshold window seed the trail, the rest shows the
# previous trail dragged Length px along the direction and faded by Decay per cook (noise / per-column jitter), and
# `lite_fx` lays it over the picture (over / lighten / add). Mirror: builders/fx_glitch_pixelsort_logic.py.
# Template: docs/builds/fx_glitch.md "Module template". ASCII only.

MODULE = 'pixelsort'
DIRS = ['horizontal', 'vertical', 'angle']
KEYS = ['luma', 'hue', 'sat', 'red', 'green', 'blue']
THRESH = ['luma', 'hue', 'sat', 'mask']
METHODS = ['sort', 'lite']
BLENDS = ['over', 'lighten', 'add']
CHUNKS = ['c128', 'c256', 'c512', 'c1024', 'c2048']      # not digit strings (T-109 (1)); N = 128 << index

PAGES = [
    ('Pixelsort', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Method', 'Menu', 'sort', {'names': METHODS, 'labels': ['True sort', 'Lite (masked streaks, TC-24)']}),
        ('Direction', 'Menu', 'vertical', {'names': DIRS, 'labels': ['Horizontal (rows)', 'Vertical (columns)',
                                                                       'Angle']}),
        ('Angle', 'Float', 30.0, {'min': -180, 'max': 180, 'label': 'Angle deg (Angle mode)'}),
        ('Sortby', 'Menu', 'luma', {'names': KEYS, 'labels': ['Luma', 'Hue', 'Saturation', 'Red', 'Green', 'Blue']}),
        ('Threshby', 'Menu', 'luma', {'names': THRESH, 'labels': ['Luma', 'Hue', 'Saturation', 'Mask TOP']}),
        ('Lower', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Lower'}),
        ('Upper', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Upper'}),
        ('Invert', 'Toggle', False, {'label': 'Invert interval'}),
        ('Reverse', 'Toggle', False, {'label': 'Reverse order'}),
        ('Randrev', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Random reverse'}),
        ('Minlen', 'Int', 0, {'min': 0, 'max': 400, 'label': 'Min span px'}),
        ('Maxlen', 'Int', 0, {'min': 0, 'max': 2048, 'label': 'Max span px (0 off)'}),
        ('Breaks', 'Float', 0.0, {'min': 0, 'max': 0.05, 'label': 'Random breaks'}),
        ('Chunk', 'Menu', 'c1024', {'names': CHUNKS, 'labels': ['128', '256', '512', '1024', '2048']}),
        ('Chunkjitter', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Chunk jitter'}),
        ('Animspeed', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Thresh anim Hz'}),
        ('Animdepth', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Thresh anim depth'}),
        ('Quality', 'Menu', 'full', {'names': ['full', 'half'], 'labels': ['Full', 'Half (every 2nd line)']}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Lite', [                                     # Method lite; window / direction / Reverse / Seed shared
        ('Litelength', 'Float', 8.0, {'min': 0, 'max': 60, 'label': 'Drag px per cook'}),
        ('Litedecay', 'Float', 0.95, {'min': 0, 'max': 1, 'label': 'Trail keep per cook'}),
        ('Litenoise', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Direction noise'}),
        ('Litejitter', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Per-column speed jitter'}),
        ('Liteblend', 'Menu', 'over', {'names': BLENDS, 'labels': ['Over', 'Lighten', 'Add']}),
        ('Litegain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Trail gain'}),
    ]),
    ('Inputs', [
        ('Masktop', 'TOP', '', {'label': 'Mask TOP (Threshby Mask)'}),
    ]),
]
PANEL_PAGES = ['Pixelsort', 'Lite']

# menus as their index. Full state (T-124 (1)): page defaults + the look (no inheritance between recalls).
_D = dict((n, o['names'].index(d) if s_ == 'Menu' else d) for _pg, pl in PAGES for n, s_, d, o in pl
          if s_ not in ('TOP',))
PRESETS = [
    (1, 'asendorf', dict(_D, Amount=1.0, Direction=1, Sortby=0, Threshby=0, Lower=0.25, Upper=0.8, Chunk=4)),
    (2, 'comet', dict(_D, Amount=1.0, Direction=1, Sortby=0, Threshby=0, Lower=0.5, Upper=1.0, Reverse=1, Minlen=12,
                      Maxlen=360, Chunk=4)),
    (3, 'hue rainbow', dict(_D, Amount=1.0, Direction=0, Sortby=1, Threshby=2, Lower=0.2, Upper=1.0, Minlen=8,
                            Chunk=2, Chunkjitter=1.0)),
    (4, 'shards', dict(_D, Amount=1.0, Direction=2, Angle=30.0, Sortby=0, Threshby=0, Lower=0.3, Upper=0.9,
                       Randrev=0.5, Minlen=6, Maxlen=240, Breaks=0.004, Chunk=3, Chunkjitter=1.0, Quality=1)),
    (5, 'breathe', dict(_D, Amount=1.0, Direction=1, Sortby=0, Threshby=0, Lower=0.35, Upper=0.85, Minlen=16,
                        Chunk=4, Animspeed=0.25, Animdepth=0.2)),
    (6, 'lite drip', dict(_D, Amount=1.0, Method=1, Direction=1, Threshby=0, Lower=0.6, Upper=1.0, Litelength=10.0,
                          Litedecay=0.95, Litejitter=0.5, Liteblend=0, Seed=6)),
    (7, 'lite wind', dict(_D, Amount=1.0, Method=1, Direction=0, Threshby=0, Lower=0.45, Upper=1.0, Litelength=14.0,
                          Litedecay=0.93, Litenoise=0.25, Litejitter=0.8, Liteblend=1, Litegain=1.2, Seed=7)),
    (8, 'lite shadows', dict(_D, Amount=1.0, Method=1, Direction=2, Angle=-60.0, Threshby=0, Lower=0.0, Upper=0.25,
                             Litelength=6.0, Litedecay=0.97, Litejitter=0.2, Liteblend=0, Seed=8)),
]

SORT = """// pixelsort sort pass (compute). Workgroup = 1024 threads = 2048 line elements, split into N-element chunks.
// Line l, position s (work frame): H -> pixel (s, l), V -> (l, s), Angle -> rotated grid (nearest).
// Out (rgba32float, work frame L x lines): xy = source pixel sorted into this place, zw = own pixel (-1 outside).
// in0 = picture, in1 = mask (Threshby Mask).
// uA amount sortby threshby lower | uB upper invert reverse randrev | uC minlen maxlen breaks seed
// uD N jitter Lp lines | uE L mode dx dy | uF Lw Lh animoffset linestep
layout (local_size_x = 1024, local_size_y = 1, local_size_z = 1) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
uniform vec4 uE;
uniform vec4 uF;
shared uint K[2048];
shared uint S[2][2048];
uint hsh(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float h01(uint x) { return float(hsh(x) >> 8) / 16777216.0; }
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
float hue(vec3 c) {
    float mx = max(c.r, max(c.g, c.b)), mn = min(c.r, min(c.g, c.b)), d = mx - mn;
    if (d <= 1e-6) return 0.0;
    float h = (mx == c.r) ? mod((c.g - c.b) / d, 6.0) : ((mx == c.g) ? (c.b - c.r) / d + 2.0 : (c.r - c.g) / d + 4.0);
    return h / 6.0;
}
float sat(vec3 c) { float mx = max(c.r, max(c.g, c.b)); return mx <= 1e-6 ? 0.0 : (mx - min(c.r, min(c.g, c.b))) / mx; }
float chan(vec4 c, int k, vec2 uv) {
    if (k == 0) return luma(c.rgb);
    if (k == 1) return hue(c.rgb);
    if (k == 2) return sat(c.rgb);
    if (k == 3) return c.r;
    if (k == 4) return c.g;
    if (k == 5) return c.b;
    return luma(texture(sTD2DInputs[1], uv).rgb);
}
ivec2 srcOf(int line, int pos, vec2 isz) {
    int mode = int(uE.y + 0.5);
    int sc = int(uF.w + 0.5);                                    // Quality half: every 2nd line sorts for 2
    if (mode == 0) return ivec2(pos, line * sc);
    if (mode == 1) return ivec2(line * sc, pos);
    vec2 d = uE.zw, pp = vec2(-d.y, d.x);
    vec2 q = 0.5 * isz + d * (float(pos) + 0.5 - 0.5 * uF.x) + pp * (float(line * sc) + 0.5 - 0.5 * uF.y);
    return ivec2(floor(q));
}
void main() {
    uint t = gl_LocalInvocationID.x;
    uint g = gl_WorkGroupID.x;
    uint N = uint(uD.x + 0.5), Lp = uint(uD.z + 0.5), lines = uint(uD.w + 0.5);
    int L = int(uE.x + 0.5);
    if (g * 2048u >= lines * Lp) return;                          // whole group past the end (uniform per group)
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    vec2 fsz = vec2(isz);
    float lo = uA.w + uF.z, hi = uB.x + uF.z;
    uint seed = uint(uC.w + 0.5) * 0x9e3779b9u;
    int sortby = int(uA.y + 0.5), tb = int(uA.z + 0.5);
    int tk = (tb == 3) ? 6 : tb;
    uint N1 = N - 1u;
    uint minlen = uint(max(uC.x, 0.0) + 0.5), maxlen = uint(max(uC.y, 0.0) + 0.5);
    bool inW[2]; bool inI[2]; int lineE[2]; int posE[2]; ivec2 sE[2]; uint qE[2]; uint bkE[2];
    for (int h = 0; h < 2; h++) {
        uint e = t + 1024u * uint(h);
        uint f = g * 2048u + e;
        uint line = f / Lp;
        uint loc = f - line * Lp;
        uint off = (uD.y > 0.0) ? uint(floor(uD.y * h01(line * 747796405u + seed) * float(Lp))) % Lp : 0u;
        int pos = int((loc + Lp - off) % Lp);                      // chunk grid rotated per line; pad >= 1 apart
        bool w = line < lines && pos < L;
        ivec2 s = srcOf(int(line), pos, fsz);
        bool im = w && s.x >= 0 && s.y >= 0 && s.x < isz.x && s.y < isz.y;
        uint m = 0u, q = 0u, bk = 0u;
        if (im) {
            vec4 c = texelFetch(sTD2DInputs[0], s, 0);
            vec2 uv = (vec2(s) + 0.5) / fsz;
            float tv = chan(c, tk, uv);
            bool inside = tv >= lo && tv <= hi;
            if (uB.y > 0.5) inside = !inside;
            m = inside ? 1u : 0u;
            q = uint(clamp(chan(c, sortby, uv), 0.0, 1.0) * 1023.0 + 0.5);
            if (uC.z > 0.0 && h01(uint(s.x) + uint(s.y) * 4099u + seed) < uC.z) bk = 1u;
        }
        inW[h] = w; inI[h] = im; lineE[h] = int(line); posE[h] = pos; sE[h] = s; qE[h] = q; bkE[h] = bk;
        K[e] = m;
    }
    barrier();
    // interval start = prefix max of starts within the N-block (a start: block edge, run edge, random break)
    uint mE[2]; uint stE[2];
    for (int h = 0; h < 2; h++) {
        uint e = t + 1024u * uint(h); uint b = e & N1; uint m = K[e];
        mE[h] = m;
        bool r = (m == 0u) || (b == 0u) || (bkE[h] == 1u) || (K[e - (b == 0u ? 0u : 1u)] == 0u);
        S[0][e] = r ? e : 0u;
    }
    barrier();
    uint pb = 0u;
    for (uint o = 1u; o < N; o <<= 1u) {
        for (int h = 0; h < 2; h++) {
            uint e = t + 1024u * uint(h); uint v = S[pb][e];
            if ((e & N1) >= o) v = max(v, S[pb][e - o]);
            S[1u - pb][e] = v;
        }
        barrier();
        pb = 1u - pb;
    }
    for (int h = 0; h < 2; h++) stE[h] = S[pb][t + 1024u * uint(h)];
    if (minlen > 1u) {                                              // span ends (suffix min) only for Min span
        uint qb = 1u - pb;
        for (int h = 0; h < 2; h++) {
            uint e = t + 1024u * uint(h); uint b = e & N1;
            uint nb = (b == N1) ? 1u : 0u;
            bool l = (mE[h] == 0u) || (nb == 1u) || (S[pb][e + 1u - nb] == e + 1u);   // next element starts a span
            S[qb][e] = l ? e : 0xFFFFu;
        }
        barrier();
        pb = qb;
        for (uint o = 1u; o < N; o <<= 1u) {
            for (int h = 0; h < 2; h++) {
                uint e = t + 1024u * uint(h); uint v = S[pb][e];
                if ((e & N1) + o < N) v = min(v, S[pb][e + o]);
                S[1u - pb][e] = v;
            }
            barrier();
            pb = 1u - pb;
        }
        for (int h = 0; h < 2; h++) {
            uint e = t + 1024u * uint(h);
            if (mE[h] == 1u && S[pb][e] - stE[h] + 1u < minlen) mE[h] = 0u;   // span too short: unsorted
        }
    }
    barrier();
    for (int h = 0; h < 2; h++) {
        uint e = t + 1024u * uint(h);
        uint sid = e, seg = 0u;
        if (mE[h] == 1u) {
            seg = (maxlen > 0u) ? (e - stE[h]) / maxlen : 0u;
            sid = stE[h] + seg * maxlen;                              // sub-span start = interval id
        }
        bool rv = uB.z > 0.5;
        if (uB.w > 0.0 && h01((g * 2048u + sid) * 2654435761u + seed) < uB.w) rv = !rv;
        uint q = (mE[h] == 1u) ? (rv ? 1023u - qE[h] : qE[h]) : 0u;
        K[e] = (sid << 21) | (q << 11) | e;                           // interval | key | index (no tie flicker)
    }
    barrier();
    for (uint k = 2u; k <= N; k <<= 1u) {                             // bitonic, every N-block ascending
        for (uint j = k >> 1u; j > 0u; j >>= 1u) {
            uint i = (t / j) * (j * 2u) + (t % j);
            uint l = i + j;
            bool asc = (k == N) || ((i & k) == 0u);
            uint a = K[i], b = K[l];
            if ((a > b) == asc) { K[i] = b; K[l] = a; }
            barrier();
        }
    }
    for (int h = 0; h < 2; h++) {
        if (!inW[h]) continue;
        uint e = t + 1024u * uint(h);
        vec4 o = vec4(-1.0);
        if (inI[h]) {
            int d = int(K[e] & 2047u) - int(e);
            o = vec4(vec2(srcOf(lineE[h], posE[h] + d, fsz)), vec2(sE[h]));
        }
        TDImageStoreOutput(0, ivec3(posE[h], lineE[h], 0), o);
    }
}
"""

APPLY = """// pixelsort apply pass (compute): gather the picture through the sort map, mix by Amount.
// in0 = picture, in1 = sort map. uA = amount mode Lw Lh, uB = dx dy linestep.
// A pixel takes the sorted source of its map texel shifted by its own offset from that texel's pixel, so unsorted
// pixels are exact and Quality half lines follow the permutation of the line they share.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    int mode = int(uA.y + 0.5);
    int sc = int(uB.z + 0.5);
    ivec2 w = ivec2(p.x, p.y / sc);
    if (mode == 1) w = ivec2(p.y, p.x / sc);
    else if (mode == 2) {
        vec2 v = vec2(p) + 0.5 - 0.5 * vec2(isz);
        vec2 d = uB.xy;
        w = ivec2(floor(vec2(dot(v, d) + 0.5 * uA.z, (dot(v, vec2(-d.y, d.x)) + 0.5 * uA.w) / float(sc))));
    }
    ivec2 wsz = textureSize(sTD2DInputs[1], 0);
    vec4 s = c;
    if (w.x >= 0 && w.y >= 0 && w.x < wsz.x && w.y < wsz.y) {
        vec4 r = texelFetch(sTD2DInputs[1], w, 0);
        ivec2 q = ivec2(r.xy), own = ivec2(r.zw);
        if (r.x >= 0.0 && q != own) s = texelFetch(sTD2DInputs[0], clamp(q + p - own, ivec2(0), isz - 1), 0);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, s, uA.x));
}
"""

LITE = """// pixelsort Lite (TC-24): masked feedback streaks (compute). Out = trail state W x (H+1) rgba32float, rgb premultiplied
// by a; row H texel 0 = clock (x this cook's now, y the previous cook's now). in0 picture, in1 previous trail (fb),
// in2 mask (Threshby Mask). Inside the threshold window: trail = (c, 1); outside: previous trail at p - dir * Length *
// jitter (+ noise across), bilinear, zero outside the frame, x Decay. Mirror: fx_glitch_pixelsort_logic.lite_step.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // threshby lower upper invert
uniform vec4 uB;   // dir.x dir.y length decay
uniform vec4 uC;   // noise jitter seed frame
uniform vec4 uD;   // now - - -
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hf(uint a, uint b) { return float(lb32(a * 0x9e3779b9u ^ lb32(b)) >> 8) / 16777216.0; }
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
float hue(vec3 c) {
    float mx = max(c.r, max(c.g, c.b)), mn = min(c.r, min(c.g, c.b)), d = mx - mn;
    if (d <= 1e-6) return 0.0;
    float h = (mx == c.r) ? mod((c.g - c.b) / d, 6.0) : ((mx == c.g) ? (c.b - c.r) / d + 2.0 : (c.r - c.g) / d + 4.0);
    return h / 6.0;
}
float sat(vec3 c) { float mx = max(c.r, max(c.g, c.b)); return mx <= 1e-6 ? 0.0 : (mx - min(c.r, min(c.g, c.b))) / mx; }
ivec2 SZ;
vec4 tap(ivec2 i) {
    if (i.x < 0 || i.y < 0 || i.x >= SZ.x || i.y >= SZ.y) return vec4(0.0);
    return texelFetch(sTD2DInputs[1], i, 0);
}
vec4 bil(vec2 q) {
    vec2 x = q - 0.5; vec2 i0 = floor(x); vec2 f = x - i0; ivec2 i = ivec2(i0);
    return mix(mix(tap(i), tap(i + ivec2(1, 0)), f.x), mix(tap(i + ivec2(0, 1)), tap(i + ivec2(1, 1)), f.x), f.y);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    SZ = textureSize(sTD2DInputs[0], 0);
    if (p.x >= SZ.x || p.y > SZ.y) return;
    ivec2 fsz = textureSize(sTD2DInputs[1], 0);
    vec4 clk = (fsz == SZ + ivec2(0, 1)) ? texelFetch(sTD2DInputs[1], ivec2(0, SZ.y), 0) : vec4(0.0);
    if (p.y == SZ.y) {                                                            // clock row
        TDImageStoreOutput(0, ivec3(p, 0), p.x == 0 ? vec4(uD.x, clk.x, 0.0, 1.0) : vec4(0.0));
        return;
    }
    bool fresh = clk.x <= 0.0 || uD.x - clk.x > 0.25 || uD.x < clk.x;            // bypassed / first: no stale trail
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    vec2 pc = vec2(p) + 0.5;
    int tb = int(uA.x + 0.5);
    float tv = tb == 0 ? luma(c.rgb) : (tb == 1 ? hue(c.rgb) : (tb == 2 ? sat(c.rgb)
             : luma(texture(sTD2DInputs[2], pc / vec2(SZ)).rgb)));
    bool inside = tv >= uA.y && tv <= uA.z;
    if (uA.w > 0.5) inside = !inside;
    vec4 S;
    if (inside) S = vec4(c.rgb, 1.0);
    else if (fresh) S = vec4(0.0);
    else {
        vec2 d = uB.xy, pp = vec2(-d.y, d.x);
        int col = int(floor(dot(pc, pp) / 2.0));
        uint sd = uint(uC.z) * 7919u;
        float jit = 1.0 - uC.y * hf(uint(col), sd + 1u);
        float nz = (hf(uint(col) ^ lb32(uint(uC.w)), sd + 2u) - 0.5) * uC.x;
        S = bil(pc - (d + pp * nz) * uB.z * jit) * uB.w;
    }
    TDImageStoreOutput(0, ivec3(p, 0), S);
}
"""

LITE_FX = """// pixelsort Lite composite (compute): in0 picture, in1 trail (rows 0..H-1). uA = amount blend gain -.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    vec4 T = texelFetch(sTD2DInputs[1], p, 0);
    int b = int(uA.y + 0.5);
    vec3 o = b == 0 ? c.rgb * (1.0 - T.a) + T.rgb * uA.z : (b == 1 ? max(c.rgb, T.rgb * uA.z) : c.rgb + T.rgb * uA.z);
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(o, c.a), uA.x));
}
"""

GEOM = """# pixelsort geometry (work frame, chunk padding): G(comp) -> dict. Read by the sort/fx uniform expressions.
import math
def G(comp):
    i = comp.op('in1')
    W, H = max(1, i.width), max(1, i.height)
    mode = comp.par.Direction.menuIndex
    a = math.radians(comp.par.Angle.eval())
    dx, dy = math.cos(a), math.sin(a)
    Lw = int(math.ceil(abs(W * dx) + abs(H * dy) - 1e-6))
    Lh = int(math.ceil(abs(W * dy) + abs(H * dx) - 1e-6))
    if mode == 0:
        L, n = W, H
    elif mode == 1:
        L, n = H, W
    else:
        L, n = Lw, Lh
    sc = 2 if comp.par.Quality.menuIndex == 1 else 1
    n = -(-n // sc)
    N = 128 << comp.par.Chunk.menuIndex
    pad = 1 if comp.par.Chunkjitter.eval() > 0 else 0     # jitter rotates the chunk grid: >= 1 pad between ends
    Lp = -(-(L + pad) // N) * N
    return {'L': L, 'n': n, 'N': N, 'Lp': Lp, 'Lw': Lw, 'Lh': Lh, 'dx': dx, 'dy': dy, 'mode': mode, 'sc': sc,
            'groups': max(1, -(-(n * Lp) // 2048))}
"""

P = "parent().par.{}.eval()"
GQ = "parent().op('geom').module.G(parent())['{}']"


def _shader(m, mk, name):
    d = m.op(name + '_compute')
    if d is None:
        d = mk(m, textDAT, name + '_compute')
    return d


def lite_uniforms():
    """(lite, lite_fx) uniforms (tested offline against LITE / LITE_FX). Direction: rows -> +x, columns -> down
    (-y, TD y up), Angle -> (cos, sin); Reverse flips it."""
    rv = "(-1.0 if %s else 1.0)" % P.format('Reverse')
    ang = "math.radians(%s)" % P.format('Angle')
    dx = "%s * (1.0 if parent().par.Direction.menuIndex == 0 else (0.0 if parent().par.Direction.menuIndex == 1 " \
         "else math.cos(%s)))" % (rv, ang)
    dy = "%s * (0.0 if parent().par.Direction.menuIndex == 0 else (-1.0 if parent().par.Direction.menuIndex == 1 " \
         "else math.sin(%s)))" % (rv, ang)
    lite = [('uA', ['parent().par.Threshby.menuIndex', P.format('Lower'), P.format('Upper'),
                    'float(%s)' % P.format('Invert')]),
            ('uB', [dx, dy, P.format('Litelength'), P.format('Litedecay')]),
            ('uC', [P.format('Litenoise'), P.format('Litejitter'), P.format('Seed'), 'absTime.frame']),
            ('uD', ['absTime.seconds', '0', '0', '0'])]
    fx = [('uA', [P.format('Amount'), 'parent().par.Liteblend.menuIndex', P.format('Litegain'), '0'])]
    return lite, fx


def build(m, H):
    """in1 -> sort (rgba32float map) -> fx (gather + Amount) | lite (trail state) + fb -> lite_fx -> out_sel (Amount 0
    = in1; only the selected method cooks) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    gm = mk(m, textDAT, 'geom')
    gm.text = GEOM
    gm.comment = 'Work-frame geometry (line length, lines, chunk padding, dispatch) for the sort uniforms.'
    ms = mk(m, selectTOP, 'mask_sel')
    expr(ms.par.top, "parent().par.Masktop.eval() or op('in1')")
    ms.comment = 'Mask for Threshby Mask (Inputs page Masktop; in1 when empty).'
    st = mk(m, glslTOP, 'sort')
    sd = _shader(m, mk, 'sort')
    sd.text = SORT
    sd.dock = st
    st.par.mode = 'compute'
    st.par.computedat = sd
    st.par.outputresolution = 'custom'
    expr(st.par.resolutionw, GQ.format('L'))
    expr(st.par.resolutionh, GQ.format('n'))
    st.par.format = 'rgba32float'
    st.par.autodispatchsize = False
    expr(st.par.dispatchsizex, GQ.format('groups'))
    st.par.dispatchsizey, st.par.dispatchsizez = 1, 1
    st.inputConnectors[0].connect(in1)
    st.inputConnectors[1].connect(ms)
    st.seq.vec.numBlocks = max(6, st.seq.vec.numBlocks)
    anim = "%s * math.sin(2 * math.pi * %s * absTime.seconds)" % (P.format('Animdepth'), P.format('Animspeed'))
    U = [('uA', [P.format('Amount'), 'parent().par.Sortby.menuIndex', 'parent().par.Threshby.menuIndex',
                 P.format('Lower')]),
         ('uB', [P.format('Upper'), 'float(%s)' % P.format('Invert'), 'float(%s)' % P.format('Reverse'),
                 P.format('Randrev')]),
         ('uC', [P.format('Minlen'), P.format('Maxlen'), P.format('Breaks'), P.format('Seed')]),
         ('uD', [GQ.format('N'), P.format('Chunkjitter'), GQ.format('Lp'), GQ.format('n')]),
         ('uE', [GQ.format('L'), GQ.format('mode'), GQ.format('dx'), GQ.format('dy')]),
         ('uF', [GQ.format('Lw'), GQ.format('Lh'), anim, GQ.format('sc')])]
    for k, (un, ex) in enumerate(U):
        getattr(st.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            expr(getattr(st.par, 'vec{}value{}'.format(k, comp)), e)
    st.comment = 'Segmented bitonic sort (FX6): 2048 elements / 1024 threads per group, Chunk-sized blocks.'
    g = mk(m, glslTOP, 'fx')
    d = _shader(m, mk, 'fx')
    d.text = APPLY
    d.dock = g
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    expr(g.par.resolutionw, 'me.inputs[0].width')
    expr(g.par.resolutionh, 'me.inputs[0].height')
    g.par.format = 'useinput'
    g.inputConnectors[0].connect(in1)
    g.inputConnectors[1].connect(st)
    g.seq.vec.numBlocks = max(2, g.seq.vec.numBlocks)
    U = [('uA', [P.format('Amount'), GQ.format('mode'), GQ.format('Lw'), GQ.format('Lh')]),
         ('uB', [GQ.format('dx'), GQ.format('dy'), GQ.format('sc'), '0'])]
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)
    g.comment = 'Gathers the picture through the sort map; Amount mixes sorted vs source.'
    LU, LF = lite_uniforms()
    fb = mk(m, feedbackTOP, 'lite_fb')
    fb.inputConnectors[0].connect(in1)
    fb.par.top = 'lite'
    fb.comment = 'Previous Lite trail (+ clock row); cooks only while Method = lite.'
    lt = H['compute'](m, 'lite', LITE, [in1, fb, ms], fmt='rgba32float')
    expr(lt.par.resolutionh, 'me.inputs[0].height + 1')
    H['uniforms'](lt, LU)
    lt.comment = 'Lite (TC-24): trail state, masked pixels seed it, the rest drags + fades; row H = cook clock.'
    lf = H['compute'](m, 'lite_fx', LITE_FX, [in1, lt])
    H['uniforms'](lf, LF)
    lf.comment = 'Lite composite: trail over / lighten / add on the picture, Amount mix.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(g)
    sel.inputConnectors[2].connect(lf)
    expr(sel.par.index, "0 if %s <= 0 else (2 if parent().par.Method.eval() == 'lite' else 1)" % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 straight (exact); sort -> fx, lite -> lite_fx (only the selected method cooks).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'mask_sel']},
        {'title': '2 Sort', 'role': 'process', 'ops': ['geom', 'sort', 'sort_compute', 'fx', 'fx_compute'],
         'body': 'sort: segmented bitonic per line chunk -> map; fx: gather + Amount.'},
        {'title': '2b Lite', 'role': 'process', 'ops': ['lite_fb', 'lite', 'lite_compute', 'lite_fx', 'lite_fx_compute'],
         'body': 'Method lite (TC-24): trail state through a Feedback TOP, then composite.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
