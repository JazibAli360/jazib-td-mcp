# fx_destroy_shatter - FX_destroy module 'shatter' (FX1 DG-15: Voronoi shards with physics).
# Module file = PAGES + PRESETS + build(m, H) (template: docs/builds/fx_glitch.md; rack: builders/fx_destroy.py).
# Shards = Voronoi cells of a jittered grid (Cells columns, square cells). Physics per FX6 probe 5a: ONE compute TOP
# `state` with 3 rgba32float colour buffers updated in place (outputaccess readwrite, clearoutputs off), one texel per
# shard (64 x 32 = up to 2048): b0 = pos.xy vel.xy (px), b1 = angle, spin, z, alpha (-1 = intact), b2 = seen hit,
# release time (-1 = at rest), vz, last cook. Impulse at the impact point (Effector Null / Point) on Trigger, a beat
# CHOP or every Auto s; gravity, spin, drag, floor bounce, stagger by distance, Return spring (reassemble), fade.
# `fx` (one compute pass, 16x16 tiles): each tile lists the shards that can reach it (shared memory + atomics), each
# pixel inverse-maps through those shards (Voronoi membership in the shard's own frame), refraction + glow on the
# crack edges; holes show Back. Amount 0 = exact passthrough; intact shards = the picture. ASCII only.
# Look glass (FX4 D11, Glass page): a flying shard is a glass pane: slope = per-shard tilt (hash, turned with the
# shard's angle, grows with its z scale) + a bevel toward its edges; offset = slope x Thickness x (1 - 1/Ior), RGB
# dispersion (R at 1 - D, G at 1, B at 1 + D of the offset; td-port prism_glass), Fresnel rim (Schlick, 0 on a flat
# face) + a Blinn spec in Rimcolor, Glasstint. Intact shards stay the exact picture. Mirror:
# builders/fx_destroy_shatter_glass_logic.py.

MODULE = 'shatter'
LOOKS = ['flat', 'glass']

PAGES = [
    ('Shatter', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Trigger', 'Pulse', None, {'label': 'Trigger (hit)'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (intact)'}),
        ('Auto', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Auto hit every s (0 = off)'}),
        ('Beatchop', 'CHOP', '', {'label': 'Beat CHOP (rising edge hits)'}),
        ('Cells', 'Int', 9, {'min': 3, 'max': 30, 'label': 'Cells across'}),
        ('Jitter', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Jitter'}),
        ('Impulse', 'Float', 900.0, {'min': -3000, 'max': 4000, 'label': 'Impulse px/s (- = implode)'}),
        ('Falloff', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Impulse falloff'}),
        ('Scatter', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Random scatter'}),
        ('Gravity', 'Float', 1600.0, {'min': -2000, 'max': 5000, 'label': 'Gravity px/s2'}),
        ('Spin', 'Float', 4.0, {'min': 0, 'max': 30, 'label': 'Spin rad/s'}),
        ('Depth', 'Float', 0.6, {'min': 0, 'max': 3, 'label': 'Depth (z kick)'}),
        ('Drag', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Drag'}),
        ('Floor', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Floor height (0 = none)'}),
        ('Bounce', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Bounce'}),
        ('Stagger', 'Float', 0.25, {'min': 0, 'max': 3, 'label': 'Stagger s'}),
        ('Return', 'Float', 0.0, {'min': 0, 'max': 20, 'label': 'Return spring'}),
        ('Fade', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Fade s (0 = never)'}),
        ('Timescale', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Time scale'}),
        ('Crackwidth', 'Float', 3.0, {'min': 0, 'max': 20, 'label': 'Crack width px'}),
        ('Crackglow', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Crack glow'}),
        ('Refract', 'Float', 8.0, {'min': 0, 'max': 40, 'label': 'Edge refract px'}),
        ('Back', 'Menu', 'dim', {'names': ['dim', 'alpha'], 'labels': ['Dimmed picture', 'Transparent']}),
        ('Backdim', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Back dim (0 = black)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Colours', [
        ('Crackcolor', 'RGB', (0.75, 0.9, 1.0), {'label': 'Crack glow'}),
    ]),
    ('Glass', [
        ('Look', 'Menu', 'flat', {'names': LOOKS, 'labels': ['Flat (crack refract)', 'Glass panes (D11)']}),
        ('Ior', 'Float', 1.5, {'min': 1, 'max': 2.5, 'label': 'IOR (1 = no bend)'}),
        ('Thickness', 'Float', 60.0, {'min': 0, 'max': 300, 'label': 'Thickness px'}),
        ('Dispersion', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Dispersion (R/B split)'}),
        ('Tilt', 'Float', 0.35, {'min': 0, 'max': 1.5, 'label': 'Pane tilt'}),
        ('Bevel', 'Float', 14.0, {'min': 0, 'max': 80, 'label': 'Bevel px'}),
        ('Fresnel', 'Float', 0.8, {'min': 0, 'max': 3, 'label': 'Fresnel rim'}),
        ('Specular', 'Float', 0.4, {'min': 0, 'max': 3, 'label': 'Specular'}),
        ('Shine', 'Float', 60.0, {'min': 1, 'max': 256, 'label': 'Shininess'}),
        ('Lightangle', 'Float', 45.0, {'min': -180, 'max': 180, 'label': 'Light angle deg'}),
        ('Glasstint', 'RGB', (0.95, 0.98, 1.0), {'label': 'Glass tint'}),
        ('Rimcolor', 'RGB', (0.85, 0.95, 1.0), {'label': 'Rim / spec colour'}),
    ]),
    POINT_PAGE, STATE_PAGE,                     # shared pages (rack builders/fx_destroy.py)
]
PANEL_PAGES = ['Shatter', 'Colours', 'Glass', 'Point']

PRESETS = [
    (1, 'screen smash', {'Amount': 1.0, 'Cells': 9, 'Jitter': 0.85, 'Impulse': 900.0, 'Falloff': 0.6,
                         'Scatter': 0.35, 'Gravity': 1600.0, 'Spin': 4.0, 'Depth': 0.6, 'Drag': 0.3, 'Floor': 0.0,
                         'Stagger': 0.25, 'Return': 0.0, 'Fade': 0.0, 'Timescale': 1.0, 'Auto': 0.0, 'Seed': 1,
                         'Look': 0}),
    (2, 'slow-mo glass', {'Amount': 1.0, 'Cells': 14, 'Impulse': 600.0, 'Falloff': 0.4, 'Scatter': 0.5,
                          'Gravity': 500.0, 'Spin': 2.0, 'Depth': 1.2, 'Drag': 0.1, 'Stagger': 0.6,
                          'Timescale': 0.25, 'Crackglow': 0.6, 'Refract': 14.0, 'Return': 0.0, 'Seed': 2,
                          'Look': 1, 'Ior': 1.5, 'Thickness': 70.0, 'Dispersion': 0.35, 'Tilt': 0.4,
                          'Bevel': 16.0, 'Fresnel': 1.0, 'Specular': 0.5, 'Shine': 60.0, 'Lightangle': 45.0}),
    (3, 'reassemble on beat', {'Amount': 1.0, 'Cells': 8, 'Impulse': 1400.0, 'Falloff': 0.3, 'Scatter': 0.4,
                               'Gravity': 0.0, 'Spin': 6.0, 'Depth': 0.8, 'Drag': 0.5, 'Stagger': 0.1,
                               'Return': 6.0, 'Auto': 1.0, 'Fade': 0.0, 'Timescale': 1.0, 'Seed': 3, 'Look': 0}),
    (4, 'explode', {'Amount': 1.0, 'Cells': 12, 'Impulse': 2600.0, 'Falloff': 0.2, 'Scatter': 0.6,
                    'Gravity': 0.0, 'Spin': 10.0, 'Depth': 2.0, 'Drag': 0.2, 'Stagger': 0.05, 'Fade': 1.5,
                    'Return': 0.0, 'Seed': 4, 'Look': 0}),
    (5, 'floor tiles', {'Amount': 1.0, 'Cells': 7, 'Impulse': 300.0, 'Falloff': 0.0, 'Scatter': 0.3,
                        'Gravity': 2400.0, 'Spin': 1.5, 'Depth': 0.2, 'Drag': 0.2, 'Floor': 0.06, 'Bounce': 0.4,
                        'Stagger': 1.2, 'Return': 0.0, 'Seed': 5, 'Look': 0}),
]

SEEDS_GLSL = """
uniform vec4 uG;   // cols, rows, cell px, jitter
uniform vec4 uS;   // seed, W, H, -
vec2 seedPos(ivec2 c) {
    uint sd = uint(uS.x);
    vec2 j = vec2(hsh(c, sd), hsh(c, sd + 77u)) - 0.5;
    return (vec2(c) + 0.5 + j * uG.w) * uG.z;
}
"""

STATE = """// shatter state (compute, 3 x rgba32float in place, 64 x 32 texels = shards). No inputs.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // now, hit time, reset time, timescale
uniform vec4 uC;   // impulse, falloff, gravity, spin
uniform vec4 uD;   // depth, drag, floor px, bounce
uniform vec4 uE;   // stagger, return, fade, scatter
uniform vec4 uF;   // impact px x, y, amount, -
""" + '%LIB%' + SEEDS_GLSL + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= 64 || p.y >= 32) return;
    int i = p.y * 64 + p.x;
    int cols = int(uG.x + 0.5), rows = int(uG.y + 0.5);
    vec4 b0 = TDImageLoadOutput(0, ivec3(p, 0));
    vec4 b1 = TDImageLoadOutput(1, ivec3(p, 0));
    vec4 b2 = TDImageLoadOutput(2, ivec3(p, 0));
    float now = uA.x;
    // Hittime / Resettime stamps later than now come from another clock (TD relaunched: absTime restarts; COMP moved
    // by tox from another TD): they are void, else a stale stamp blocks every hit / forces rest forever (T-155).
    float hv = uA.y <= now + 0.05 ? uA.y : -1.0;
    float rv = uA.z <= now + 0.05 ? uA.z : -1.0;
    // Reset: >= (not >): when the state already cooked earlier in the pulse's frame, the stamp EQUALS the last
    // cook time on every later cook and > never fires (T-160); a second reset in the next frame is harmless.
    if (i >= cols * rows || !(now - b2.w <= 0.25) || rv >= b2.w) {           // rest (fresh / Reset / unused)
        // old hits are not replayed; a hit that arrived during the stall itself (< 0.5 s ago, after any Reset) still lands
        float prev = (b2.x == b2.x && b2.x <= now + 0.05) ? b2.x : -1.0;
        bool keep = i < cols * rows && hv >= b2.w && now - hv < 0.5 && hv > rv;
        float seen = keep ? min(prev, hv - 1e-3) : max(prev, hv);
        TDImageStoreOutput(0, ivec3(p, 0), vec4(0.0));
        TDImageStoreOutput(1, ivec3(p, 0), vec4(0.0, 0.0, 0.0, -1.0));
        TDImageStoreOutput(2, ivec3(p, 0), vec4(seen, -1.0, 0.0, now));
        return;
    }
    if (!(b2.x <= now + 0.05)) b2.x = -1.0;           // a seen hit from another clock (older shader / relaunch, T-160)
    float dt = clamp(now - b2.w, 0.0, 0.1) * uA.w;
    ivec2 cell = ivec2(i % max(cols, 1), i / max(cols, 1));
    vec2 sp = seedPos(cell);
    vec2 W = uS.yz;
    uint sd = uint(uS.x) + uint(i) * 13u;
    if (hv > b2.x + 1e-4 && uF.z > 0.0) {                                      // a new hit
        vec2 r = sp + b0.xy - uF.xy;
        float d = length(r) / length(W);
        vec2 dir = length(r) > 1e-3 ? normalize(r) : vec2(0.0, 1.0);
        float a = 6.2831853 * hsh(ivec2(i, 1), sd);
        vec2 rnd = vec2(cos(a), sin(a)) * hsh(ivec2(i, 2), sd);
        float k = uC.x * exp(-uC.y * d * 4.0);
        b0.zw += (dir * (1.0 - uE.w) + rnd * uE.w) * k;
        b1.y += uC.w * (hsh(ivec2(i, 3), sd) * 2.0 - 1.0) * (0.3 + 0.7 * exp(-uC.y * d * 2.0));
        b2.z += uD.x * (0.3 + hsh(ivec2(i, 4), sd)) * exp(-uC.y * d * 2.0) * 1.5;
        if (b2.y < 0.0 || b2.y > now) b2.y = hv + uE.x * d * 1.4142 + uE.x * 0.25 * hsh(ivec2(i, 5), sd);
        b2.x = hv;
        if (b1.w < 0.0) b1.w = 1.0;
    }
    if (b2.y >= 0.0 && now >= b2.y) {                                           // flying
        float dg = exp(-uD.y * dt);
        b0.w -= uC.z * dt;
        if (uE.y > 0.0) {                                                       // return spring (critically damped)
            float w = uE.y;
            b0.zw += (-w * w * b0.xy - 2.0 * w * b0.zw) * dt;
            b1.y += (-w * w * b1.x - 2.0 * w * b1.y) * dt;
            b2.z += (-w * w * b1.z - 2.0 * w * b2.z) * dt;
        }
        b0.zw *= dg; b1.y *= dg; b2.z *= dg;
        b0.xy += b0.zw * dt;
        b1.x += b1.y * dt;
        b1.z = max(b1.z + b2.z * dt, -0.9);
        if (uD.z > 0.0 && sp.y + b0.y < uD.z && b0.w < 0.0) {                 // floor
            b0.y = uD.z - sp.y;
            b0.w = -b0.w * uD.w;
            b0.z *= 0.6; b1.y *= 0.5;
        }
        float age = now - b2.y;
        b1.w = uE.z > 0.0 ? clamp(1.0 - age / uE.z, 0.0, 1.0) : 1.0;
        if (uE.y > 0.0 && age > 0.3 && length(b0.xy) < 0.5 && length(b0.zw) < 8.0 && abs(b1.x) < 0.002
            && abs(b1.z) < 0.002) {                                             // reassembled: back to rest, exact
            b0 = vec4(0.0); b1 = vec4(0.0, 0.0, 0.0, -1.0); b2.y = -1.0; b2.z = 0.0;
        }
    }
    b2.w = now;
    TDImageStoreOutput(0, ivec3(p, 0), b0);
    TDImageStoreOutput(1, ivec3(p, 0), b1);
    TDImageStoreOutput(2, ivec3(p, 0), b2);
}
"""

FX = """// shatter fx (compute 16x16 tiles, format useinput). in0 = picture, in1 = state b0, in2 = state b1 (Render Select).
// Amount 0 = exact passthrough (texelFetch).
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uA;   // amount, crack width, glow, refract
uniform vec4 uB;   // back, backdim, -, -
uniform vec4 uK;   // crack rgb
uniform vec4 uL;   // look (0 flat, 1 glass), ior, thickness px, dispersion
uniform vec4 uT;   // tilt, bevel px, fresnel, specular
uniform vec4 uN;   // glass tint rgb, shininess
uniform vec4 uR;   // rim / spec rgb, light angle (rad)
""" + '%LIB%' + SEEDS_GLSL + """
#define MAXL 96
shared vec4 sP[MAXL];      // seed xy, pos xy
shared vec4 sR[MAXL];      // cos, sin, scale, alpha
shared int sI[MAXL];
shared vec2 sNb[MAXL * 9]; // each listed shard's 3x3 neighbour seeds (centre = 4; far away = outside the grid)
shared uint sN;
shared uint sMove;
int nearest(vec2 q, out vec2 s1) {
    int cols = int(uG.x + 0.5), rows = int(uG.y + 0.5);
    ivec2 c = ivec2(floor(q / uG.z));
    float d1 = 1e20; int best = -1; s1 = vec2(0.0);
    for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
        ivec2 k = c + ivec2(i, j);
        if (k.x < 0 || k.y < 0 || k.x >= cols || k.y >= rows) continue;
        vec2 s = seedPos(k); float d = dot(q - s, q - s);
        if (d < d1) { d1 = d; best = k.y * cols + k.x; s1 = s; }
    }
    return best;
}
bool member(int e, vec2 q) {            // is q in listed shard e's Voronoi cell (vs its 8 neighbours)?
    float d0 = dot(q - sNb[e * 9 + 4], q - sNb[e * 9 + 4]);
    for (int t = 0; t < 9; t++) { if (t == 4) continue; vec2 r = q - sNb[e * 9 + t]; if (dot(r, r) < d0) return false; }
    return true;
}
float edgeDist(int e, vec2 q, out vec2 nrm) {   // distance to listed shard e's nearest cell edge + inward normal
    vec2 s1 = sNb[e * 9 + 4];
    float ed = 1e20; nrm = vec2(0.0, 1.0);
    for (int t = 0; t < 9; t++) {
        if (t == 4) continue;
        vec2 n = s1 - sNb[e * 9 + t]; float L = length(n);
        if (L < 1e-4 || L > 1e8) continue;
        float d = dot(q - 0.5 * (s1 + sNb[e * 9 + t]), n / L);
        if (d < ed) { ed = d; nrm = n / L; }
    }
    return ed;
}
vec2 glassSlope(int bi, vec2 cs, float sc, float be, vec2 bn) {   // pane slope: tilt (per shard) + bevel
    uint sd = uint(uS.x) + 911u;
    vec2 h = vec2(hsh(ivec2(bi, 7), sd), hsh(ivec2(bi, 8), sd)) * 2.0 - 1.0;
    vec2 t = vec2(cs.x * h.x - cs.y * h.y, cs.y * h.x + cs.x * h.y) * uT.x * (1.0 + max(sc - 1.0, 0.0));
    float bv = uT.y > 0.0 ? clamp(1.0 - be / uT.y, 0.0, 1.0) : 0.0;
    return t - bn * bv * bv;
}
vec4 glassShade(vec2 q, vec2 sl, vec2 sz) {   // refract + dispersion + Fresnel rim + spec (mirror: glass_logic)
    vec2 off = sl * uL.z * (1.0 - 1.0 / max(uL.y, 1e-3));
    vec4 cg = texture(sTD2DInputs[0], (q + off) / sz);
    float r = texture(sTD2DInputs[0], (q + off * (1.0 - uL.w)) / sz).r;
    float b = texture(sTD2DInputs[0], (q + off * (1.0 + uL.w)) / sz).b;
    vec3 n = normalize(vec3(-sl, 1.0));
    float f0 = (uL.y - 1.0) / (uL.y + 1.0); f0 *= f0;
    float F = f0 + (1.0 - f0) * pow(1.0 - n.z, 5.0);
    float rim = uT.z * (F - f0) / max(1.0 - f0, 1e-4);
    vec3 hv = normalize(normalize(vec3(cos(uR.w), sin(uR.w), 1.0)) + vec3(0.0, 0.0, 1.0));
    float sp = uT.w * pow(max(dot(n, hv), 0.0), uN.w);
    return vec4(vec3(r, cg.g, b) * uN.rgb + uR.rgb * (rim + sp), cg.a);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    bool ok = p.x < isz.x && p.y < isz.y;
    vec4 c0 = ok ? texelFetch(sTD2DInputs[0], p, 0) : vec4(0.0);
    if (uA.x <= 0.0) { if (ok) TDImageStoreOutput(0, ivec3(p, 0), c0); return; }   // uniform: whole dispatch
    uint lid = gl_LocalInvocationIndex;
    if (lid == 0u) { sN = 0u; sMove = 0u; }
    barrier();
    int cols = int(uG.x + 0.5), rows = int(uG.y + 0.5), N = min(cols * rows, 2048);
    vec2 tc = vec2(gl_WorkGroupID.xy) * 16.0 + 8.0;
    float rad = 1.6 * uG.z;
    for (int k = int(lid); k < N; k += 256) {
        ivec2 t = ivec2(k % 64, k / 64);
        vec4 b1 = texelFetch(sTD2DInputs[2], t, 0);
        vec4 b0 = b1.w < 0.0 ? vec4(0.0) : texelFetch(sTD2DInputs[1], t, 0);
        ivec2 cl = ivec2(k % cols, k / cols);
        vec2 sp = seedPos(cl);
        float sc = 1.0 + b1.z;
        if (length(sp + b0.xy - tc) < rad * max(sc, 1.0) + 11.4 && (b1.w < 0.0 || b1.w > 0.0)) {
            uint n = atomicAdd(sN, 1u);
            if (n < uint(MAXL)) {
                sP[n] = vec4(sp, b0.xy); sR[n] = vec4(cos(b1.x), sin(b1.x), sc, b1.w); sI[n] = k;
                for (int t = 0; t < 9; t++) {
                    ivec2 kk = cl + ivec2(t % 3 - 1, t / 3 - 1);
                    bool in_ = kk.x >= 0 && kk.y >= 0 && kk.x < cols && kk.y < rows;
                    sNb[int(n) * 9 + t] = in_ ? seedPos(kk) : vec2(1e9);
                }
            }
            if (b1.w >= 0.0) atomicOr(sMove, 1u);
        }
    }
    barrier();
    if (!ok) return;
    vec2 pc = vec2(p) + 0.5;
    vec2 s1;
    int own = nearest(pc, s1);
    float ownA = own >= 0 ? texelFetch(sTD2DInputs[2], ivec2(own % 64, own / 64), 0).w : -1.0;
    if (sMove == 0u && ownA < 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c0); return; }   // tile intact
    int n = int(min(sN, uint(MAXL)));
    float bz = -1e9; int bi = -1, be_ = -1; vec2 bq = pc; float ba = 0.0;
    for (int j = 0; j < n; j++) {
        vec4 P = sP[j], R = sR[j];
        if (R.z < bz || (R.z == bz && sI[j] < bi)) continue;
        vec2 r = pc - P.xy - P.zw;
        vec2 q = vec2(R.x * r.x + R.y * r.y, -R.y * r.x + R.x * r.y) / R.z + P.xy;   // inverse rotate + scale
        if (length(q - P.xy) > rad) continue;
        if (!member(j, q)) continue;
        bz = R.z; bi = sI[j]; be_ = j; bq = q; ba = R.w;
    }
    vec4 back = int(uB.x + 0.5) == 1 ? vec4(0.0) : vec4(c0.rgb * uB.y, c0.a);
    vec4 o = back;
    if (bi >= 0) {
        vec2 sz = vec2(isz);
        if (ba < 0.0) o = texture(sTD2DInputs[0], bq / sz);                    // intact shard
        else {
            vec2 bn;
            float be = edgeDist(be_, bq, bn);
            float w = max(uA.y, 1e-3);
            float k = clamp(1.0 - be / w, 0.0, 1.0);
            vec4 s = uL.x > 0.5 ? glassShade(bq, glassSlope(bi, sR[be_].xy, sR[be_].z, be, bn), sz)
                                : texture(sTD2DInputs[0], (bq - bn * uA.w * k * k) / sz);
            s.rgb += uK.rgb * uA.z * k * k;
            o = mix(back, s, ba);
        }
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c0, o, uA.x));
}
"""

BEAT_EXEC = """# Beat CHOP rising edge -> Hittime (the shatter state shader applies the impulse).
def onOffToOn(channel, sampleIndex, val, prev):
    parent().par.Hittime.val = absTime.seconds
    return
"""

P = "parent().par.{}.eval()"
W, Hh = "op('in1').width", "op('in1').height"


def grid_uniforms():
    return [('uG', [P.format('Cells'), 'math.ceil(%s / max(1.0, %s / max(1, %s)))' % (Hh, W, P.format('Cells')),
                    '%s / max(1, %s)' % (W, P.format('Cells')), P.format('Jitter')]),
            ('uS', [P.format('Seed'), W, Hh, '0'])]


def state_uniforms(pt):
    # rack hit_expr: a stale Hittime is voided before the Auto max (else it hides the Auto ticks, T-155)
    return [('uA', ['absTime.seconds', hit_expr(), P.format('Resettime'), P.format('Timescale')]),
            ('uC', [P.format('Impulse'), P.format('Falloff'), P.format('Gravity'), P.format('Spin')]),
            ('uD', [P.format('Depth'), P.format('Drag'), '%s * %s' % (P.format('Floor'), Hh), P.format('Bounce')]),
            ('uE', [P.format('Stagger'), P.format('Return'), P.format('Fade'), P.format('Scatter')]),
            ('uF', ['%s * %s' % (pt('u'), W), '%s * %s' % (pt('v'), Hh), P.format('Amount'), '0'])] + grid_uniforms()


def fx_uniforms():
    return [('uA', [P.format('Amount'), P.format('Crackwidth'), P.format('Crackglow'), P.format('Refract')]),
            ('uB', ['parent().par.Back.menuIndex', P.format('Backdim'), '0', '0']),
            ('uK', [P.format('Crackcolorr'), P.format('Crackcolorg'), P.format('Crackcolorb'), '0']),
            ('uL', ['parent().par.Look.menuIndex', P.format('Ior'), P.format('Thickness'), P.format('Dispersion')]),
            ('uT', [P.format('Tilt'), P.format('Bevel'), P.format('Fresnel'), P.format('Specular')]),
            ('uN', [P.format('Glasstintr'), P.format('Glasstintg'), P.format('Glasstintb'), P.format('Shine')]),
            ('uR', [P.format('Rimcolorr'), P.format('Rimcolorg'), P.format('Rimcolorb'),
                    'math.radians(%s)' % P.format('Lightangle')])] + grid_uniforms()


def build(m, H):
    """Fill instance COMP m: state (3 buffers, in place) -> state_b1 (Render Select) -> fx (+ in1) -> out1."""
    mk, expr, compute, pt = H['mk'], H['expr'], H['compute'], H['pt_expr']
    lib = H['GLSL_LIB']
    in1 = mk(m, inTOP, 'in1')
    H['pulse_exec'](m, ['Trigger', 'Reset'])
    be = mk(m, chopexecuteDAT, 'beat_exec')
    if be.text != BEAT_EXEC:
        be.text = BEAT_EXEC
    expr(be.par.chop, "parent().par.Beatchop.eval().path if parent().par.Beatchop.eval() is not None else ''")
    expr(be.par.active, "parent().par.Beatchop.eval() is not None")
    be.par.offtoon = True
    be.par.valuechange = False
    be.comment = 'Beat CHOP (Shatter page) rising edge -> Hittime.'
    st = compute(m, 'state', STATE.replace('%LIB%', lib), [], 64, 32, fmt='rgba32float', readwrite=True, bufs=3,
                 uniforms=state_uniforms(pt))
    st.comment = 'shatter state: 1 texel per shard, 3 rgba32float buffers in place (b0 pos/vel, b1 rot/z/alpha, b2 hit/release/vz/last).'
    rs = mk(m, renderselectTOP, 'state_b1')
    rs.par.top = 'state'
    rs.par.bufferindex = 1
    rs.comment = 'state colour buffer 1 (angle, spin, z, alpha).'
    g = compute(m, 'fx', FX.replace('%LIB%', lib), [in1, st, rs], 'me.inputs[0].width', 'me.inputs[0].height',
                extend='hold', uniforms=fx_uniforms())
    g.comment = ('shatter: tiles list nearby shards, pixels inverse-map through them; crack refract + glow (DG-15); '
                 'Look glass = refracting panes, dispersion, Fresnel rim (D11).')
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulse_exec', 'beat_exec'],
         'body': 'Picture; Trigger / Reset pulses + Beat CHOP -> Hittime / Resettime.'},
        {'title': '2 Shatter', 'role': 'process', 'ops': ['state', 'state_compute', 'state_b1', 'fx', 'fx_compute'],
         'body': 'state: shard physics (3 buffers in place). fx: per-tile shard list, inverse map, cracks.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
