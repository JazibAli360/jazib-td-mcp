# fx_destroy_explode - FX_destroy module 'explode' (FX1 DG-19, FX4 D6: 2D / 3D implode-explode of the picture in tiles).
# Module file = PAGES + PRESETS + build(m, H) (template: docs/builds/fx_glitch.md; rack: builders/fx_destroy.py).
# Doc + live results: docs/builds/fx_destroy_explode.md. Reference maths: builders/fx_destroy_explode_logic.py.
# The picture is cut into a grid of tiles (Cells across, Aspect, Brick rows; up to 64 x 72 = 4608 tiles, small tiles
# read as particles). Motion is ANALYTIC in the time since the hit (no physics state to go stale): a 2x1 `hit` compute
# (in place) latches the hit time + blast centre (Effector Null / Point) from Trigger, a Beat CHOP rising edge or Auto;
# `tiles` (one texel per tile, 2 rgba32float buffers) evaluates every tile's 3D centre, alpha and rotation x scale
# (quaternion) for Mode explode / implode / assemble, Drive hits or manual (Progress), Stagger (shock front), Hold +
# Return (reassemble), Fade; `fx` (16x16 workgroups) lists the moving tiles that can reach each workgroup in shared
# memory, then ray-casts every pixel through them (perspective camera, Focal): the nearest tile wins (depth sorted,
# tilted tiles intersect correctly), back faces darkened, edge glow, holes show Back. Tiles at rest are written with
# texelFetch, so Amount 0, no hit, and a finished reassembly are exact passthrough. ASCII only.

MODULE = 'explode'

PAGES = [
    ('Explode', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (motion scale)'}),
        ('Mode', 'Menu', 'explode', {'names': ['explode', 'implode', 'assemble'],
                                     'labels': ['Explode (blast out)', 'Implode (suck in)', 'Assemble (fly in)']}),
        ('Drive', 'Menu', 'hits', {'names': ['hits', 'manual'], 'labels': ['Hits (Trigger / Beat / Auto)',
                                                                           'Manual (Progress)']}),
        ('Progress', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Progress (manual, x Duration s)'}),
        ('Duration', 'Float', 2.0, {'min': 0.1, 'max': 8, 'label': 'Duration s (manual / assemble)'}),
        ('Trigger', 'Pulse', None, {'label': 'Trigger (hit)'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (intact)'}),
        ('Auto', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Auto hit every s (0 = off)'}),
        ('Beatchop', 'CHOP', '', {'label': 'Beat CHOP (rising edge hits)'}),
        ('Ignorehits', 'Toggle', False, {'label': 'Ignore hits while flying'}),
        ('Cells', 'Int', 24, {'min': 2, 'max': 48, 'label': 'Cells across'}),
        ('Aspect', 'Float', 1.0, {'min': 0.5, 'max': 2, 'label': 'Tile height / width'}),
        ('Brick', 'Toggle', False, {'label': 'Brick rows'}),
        ('Force', 'Float', 1200.0, {'min': -3000, 'max': 5000, 'label': 'Force px/s (implode: pull)'}),
        ('Falloff', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Force falloff'}),
        ('Scatter', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Random scatter'}),
        ('Swirl', 'Float', 0.0, {'min': -6, 'max': 6, 'label': 'Swirl rad'}),
        ('Gravity', 'Float', 0.0, {'min': -2000, 'max': 4000, 'label': 'Gravity px/s2'}),
        ('Drag', 'Float', 0.8, {'min': 0, 'max': 6, 'label': 'Drag'}),
        ('Spin', 'Float', 3.0, {'min': 0, 'max': 30, 'label': 'Spin rad/s'}),
        ('Tilt', 'Float', 0.0, {'min': 0, 'max': 20, 'label': '3D tilt rad/s (0 = flat)'}),
        ('Depth', 'Float', 0.3, {'min': -2, 'max': 3, 'label': 'Depth (z kick, x height /s)'}),
        ('Focal', 'Float', 1.2, {'min': 0.3, 'max': 5, 'label': 'Camera distance (x height)'}),
        ('Shrink', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Implode shrink'}),
        ('Stagger', 'Float', 0.3, {'min': 0, 'max': 3, 'label': 'Stagger s (shock front)'}),
        ('Hold', 'Float', 0.6, {'min': 0, 'max': 8, 'label': 'Hold s before return'}),
        ('Return', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Return s (0 = stay)'}),
        ('Fade', 'Float', 0.0, {'min': 0, 'max': 10, 'label': 'Fade s (0 = never)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Look', [
        ('Gap', 'Float', 2.0, {'min': 0, 'max': 20, 'label': 'Gap px (moving tiles)'}),
        ('Edgewidth', 'Float', 3.0, {'min': 0, 'max': 30, 'label': 'Edge glow width px'}),
        ('Edgeglow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Edge glow'}),
        ('Edgecolor', 'RGB', (1.0, 0.6, 0.25), {'label': 'Edge colour'}),
        ('Shade', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Tilt shading'}),
        ('Backside', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Back face brightness'}),
        ('Back', 'Menu', 'dim', {'names': ['dim', 'alpha'], 'labels': ['Dimmed picture', 'Transparent']}),
        ('Backdim', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Back dim (0 = black)'}),
    ]),
    POINT_PAGE, STATE_PAGE,                     # shared pages (rack builders/fx_destroy.py)
]
PANEL_PAGES = ['Explode', 'Look', 'Point']

PRESETS = [
    (1, 'pop on beat', {'Amount': 1.0, 'Mode': 0, 'Drive': 0, 'Cells': 16, 'Aspect': 1.0, 'Force': 1500.0,
                        'Falloff': 0.8, 'Scatter': 0.2, 'Swirl': 0.0, 'Gravity': 0.0, 'Drag': 3.0, 'Spin': 2.0,
                        'Tilt': 0.0, 'Depth': 0.4, 'Stagger': 0.08, 'Hold': 0.05, 'Return': 0.3, 'Fade': 0.0,
                        'Auto': 0.5, 'Gap': 3.0, 'Edgeglow': 0.0, 'Seed': 1}),
    (2, 'debris cloud', {'Amount': 1.0, 'Mode': 0, 'Drive': 0, 'Cells': 44, 'Aspect': 1.0, 'Force': 1800.0,
                         'Falloff': 0.3, 'Scatter': 0.7, 'Swirl': 0.4, 'Gravity': 900.0, 'Drag': 0.6, 'Spin': 8.0,
                         'Tilt': 6.0, 'Depth': 0.5, 'Stagger': 0.25, 'Hold': 0.0, 'Return': 0.0, 'Fade': 2.5,
                         'Auto': 0.0, 'Gap': 1.0, 'Shade': 0.6, 'Edgeglow': 0.0, 'Seed': 2}),
    (3, 'implode pull', {'Amount': 1.0, 'Mode': 1, 'Drive': 0, 'Cells': 30, 'Force': 900.0, 'Falloff': 0.0,
                         'Scatter': 0.5, 'Swirl': 2.5, 'Spin': 4.0, 'Tilt': 0.0, 'Depth': 0.3, 'Shrink': 0.95,
                         'Stagger': 0.4, 'Hold': 0.4, 'Return': 1.2, 'Fade': 0.0, 'Auto': 0.0, 'Gap': 2.0,
                         'Edgeglow': 0.6, 'Edgewidth': 3.0, 'Seed': 3}),
    (4, '3D tilt blast', {'Amount': 1.0, 'Mode': 0, 'Drive': 0, 'Cells': 10, 'Aspect': 1.0, 'Force': 700.0,
                          'Falloff': 0.4, 'Scatter': 0.3, 'Gravity': 0.0, 'Drag': 1.2, 'Spin': 1.0, 'Tilt': 4.0,
                          'Depth': 0.8, 'Focal': 1.2, 'Stagger': 0.2, 'Hold': 1.0, 'Return': 1.5, 'Shade': 0.8,
                          'Backside': 0.3, 'Edgeglow': 1.2, 'Edgewidth': 4.0, 'Gap': 4.0, 'Auto': 0.0, 'Seed': 4}),
    (5, 'assemble', {'Amount': 1.0, 'Mode': 2, 'Drive': 0, 'Cells': 20, 'Aspect': 1.0, 'Brick': 1,
                     'Force': 1600.0, 'Falloff': 0.2, 'Scatter': 0.5, 'Swirl': 0.8, 'Gravity': 0.0, 'Drag': 1.0,
                     'Spin': 5.0, 'Tilt': 5.0, 'Depth': 0.6, 'Stagger': 0.3, 'Duration': 1.5, 'Fade': 0.0,
                     'Auto': 0.0, 'Gap': 2.0, 'Edgeglow': 0.0, 'Seed': 5}),
]

NX, NY = 64, 72                 # tile texels (one per tile); row NY of the tiles texture holds the global flag
NMAX = NX * NY

GRID_GLSL = """
uniform vec4 uG;   // stride (cols + 1), rows, cell w px, cell h px
uniform vec4 uS;   // seed, W, H, brick
vec2 restCentre(int i) {        // tile i's rest centre (px); x < 0 = unused slot
    int st = int(uG.x + 0.5), row = i / st, col = i - row * st;
    float off = (uS.w > 0.5 && (row & 1) == 1) ? 0.5 * uG.z : 0.0;
    float x0 = float(col) * uG.z - off;
    if (row >= int(uG.y + 0.5) || x0 >= uS.y || i >= %d) return vec2(-1.0);
    return vec2(x0 + 0.5 * uG.z, (float(row) + 0.5) * uG.w);
}
int tileAt(vec2 q) {            // index of the rest tile containing q (px)
    int row = int(floor(q.y / uG.w));
    float off = (uS.w > 0.5 && (row & 1) == 1) ? 0.5 * uG.z : 0.0;
    int col = int(floor((q.x + off) / uG.z));
    return row * int(uG.x + 0.5) + col;
}
""" % NMAX

HIT = """// explode hit latch (compute 1 thread, 2x1 rgba32float in place). No inputs.
// texel 0 = latched hit time (-1 = none), blast centre x, y px, 7 (initialised); texel 1 = last seen hit / reset time.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uA;   // now, hit time, reset time, ignore hits while flying
uniform vec4 uB;   // centre px x, y, mode, -
uniform vec4 uE;   // stagger, hold, return, duration
void main() {
    if (gl_GlobalInvocationID.x != 0u || gl_GlobalInvocationID.y != 0u) return;
    vec4 h = TDImageLoadOutput(0, ivec3(0, 0, 0));
    vec4 s = TDImageLoadOutput(0, ivec3(1, 0, 0));
    float now = uA.x;
    // uA.y / uA.z come voided when later than now (rack stamp exprs, T-155); a seen stamp stored by an older shader
    // from another clock (> now) would block every later hit: start over like a fresh texture (T-160).
    if (!(h.w == 7.0) || !(s.x <= now + 0.05)) {           // fresh texture: intact, old hits are not replayed
        h = vec4(-1.0, uB.xy, 7.0); s = vec4(max(uA.y, uA.z), 0.0, 0.0, 0.0);
    } else {
        if (uA.z > s.x) { h.x = -1.0; s.x = uA.z; }        // Reset
        if (uA.y > s.x) {                                   // a new hit
            int mode = int(uB.z + 0.5);
            float end = (mode == 2) ? uE.w + uE.x * 1.7 : ((uE.z > 0.0) ? uE.x * 1.7 + uE.y + uE.z : 1e30);
            bool flying = h.x >= 0.0 && now - h.x < end;
            if (!(uA.w > 0.5 && flying)) { h.x = uA.y; h.yz = uB.xy; }
            s.x = uA.y;
        }
    }
    TDImageStoreOutput(0, ivec3(0, 0, 0), h);
    TDImageStoreOutput(0, ivec3(1, 0, 0), s);
}
"""

TILES = """// explode tiles (compute, @NX@ x @NY1@, 2 x rgba32float). in0 = hit latch. One texel per tile:
// b0 = centre x, y px, z px (toward the camera), alpha (-1 = at rest); b1 = rotation quaternion x scale.
// Texel (0, @NY@) b0 = (any tile moving, tile count, -, -).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // now, mode (0 explode, 1 implode, 2 assemble), drive (0 hits, 1 manual), manual time s
uniform vec4 uC;   // force, falloff, scatter, gravity
uniform vec4 uD;   // spin, tilt, depth (x H per s), drag
uniform vec4 uE;   // stagger, hold, return, fade
uniform vec4 uF;   // amount, duration, live centre px x, y
uniform vec4 uH;   // shrink, swirl, -, -
""" + '%LIB%' + GRID_GLSL + """
vec4 quatEuler(vec3 a) {        // q = qz * qy * qx
    vec3 c = cos(0.5 * a), s = sin(0.5 * a);
    return vec4(s.x * c.y * c.z - c.x * s.y * s.z, c.x * s.y * c.z + s.x * c.y * s.z,
                c.x * c.y * s.z - s.x * s.y * c.z, c.x * c.y * c.z + s.x * s.y * s.z);
}
float integ(float k, float t) { return k > 1e-4 ? (1.0 - exp(-k * t)) / k : t; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= @NX@ || p.y > @NY@) return;
    vec4 hit = texelFetch(sTD2DInputs[0], ivec2(0, 0), 0);
    int mode = int(uA.y + 0.5);
    bool manual = uA.z > 0.5;
    float W = uS.y, Hh = uS.z, diag = length(vec2(W, Hh));
    bool valid = manual ? uA.w > 0.0 : (hit.w == 7.0 && hit.x >= 0.0 && uA.x >= hit.x);
    float age0 = manual ? uA.w : uA.x - hit.x;
    vec2 ctr = manual ? uF.zw : hit.yz;
    if (p.y == @NY@) {                                    // global flag: can any tile be off its rest place?
        float sx = uE.x * 1.7;
        float end = (mode == 2) ? uF.y + sx : ((uE.z > 0.0) ? sx + uE.y + uE.z : 1e30);
        bool act = valid && uF.x > 0.0 && (manual || age0 < end + 0.05);
        if (p.x == 0) TDImageStoreOutput(0, ivec3(p, 0), vec4(act ? 1.0 : 0.0, uG.x * uG.y, 0.0, 0.0));
        return;
    }
    int i = p.y * @NX@ + p.x;
    vec2 rc = restCentre(i);
    vec4 b0 = vec4(rc, 0.0, -1.0), b1 = vec4(0.0, 0.0, 0.0, 1.0);
    if (rc.x >= 0.0 && valid && uF.x > 0.0) {
        uint sd = uint(uS.x) * 7919u;
        float h1 = hsh(ivec2(i, 1), sd), h2 = hsh(ivec2(i, 2), sd), h3 = hsh(ivec2(i, 3), sd);
        float h4 = hsh(ivec2(i, 4), sd), h5 = hsh(ivec2(i, 5), sd), h6 = hsh(ivec2(i, 6), sd);
        vec2 r = rc - ctr;
        float d = length(r) / diag;
        float a = age0 - uE.x * (d * 1.4142 + 0.25 * hsh(ivec2(i, 7), sd));
        float tau, m = uF.x;
        if (mode == 2) tau = clamp(uF.y - a, 0.0, uF.y);                       // assemble: run the explode backwards
        else {
            tau = max(a, 0.0);
            if (uE.z > 0.0) m *= 1.0 - smoothstep(uE.y, uE.y + uE.z, tau);       // Hold, then Return (reassemble)
        }
        if (tau > 0.0 && m > 0.0) {
            float fall = exp(-uC.y * d * 4.0);
            vec3 pos = vec3(rc, 0.0);
            float sc = 1.0, al = uE.w > 0.0 ? clamp(1.0 - tau / uE.w, 0.0, 1.0) : 1.0;
            float I = integ(uD.w, tau);
            vec3 ang = vec3(uD.y * (2.0 * h5 - 1.0) * I, uD.y * (2.0 * h6 - 1.0) * I, uD.x * (2.0 * h4 - 1.0) * I);
            if (mode == 1) {                                                    // implode: pulled into the centre
                float e = 1.0 - exp(-tau * abs(uC.x) / 600.0 * (1.0 - 0.5 * uC.z + uC.z * h2) * (0.25 + fall));
                float sw = uH.y * e, cs = cos(sw), sn = sin(sw);
                vec2 rr = vec2(cs * r.x - sn * r.y, sn * r.x + cs * r.y) * (1.0 - e);
                pos = vec3(ctr + rr, -uD.z * Hh * e * (0.3 + h3));
                sc = 1.0 - uH.x * e;
            } else {                                                            // explode / assemble
                vec2 d0 = length(r) > 1e-3 ? r / length(r) : vec2(0.0, 1.0);
                float an = 6.2831853 * h1;
                vec2 dir = mix(d0, vec2(cos(an), sin(an)), uC.z);
                dir = length(dir) > 1e-4 ? normalize(dir) : vec2(cos(an), sin(an));
                float cw = cos(uH.y), sw = sin(uH.y);
                dir = vec2(cw * dir.x - sw * dir.y, sw * dir.x + cw * dir.y);
                float sp = uC.x * fall * (1.0 - 0.5 * uC.z + uC.z * h2);
                pos.xy = rc + dir * sp * I - vec2(0.0, 0.5 * uC.w * tau * tau);
                pos.z = uD.z * Hh * (1.6 * h3 - 0.3) * exp(-uC.y * d * 2.0) * I;
            }
            pos = vec3(rc, 0.0) + (pos - vec3(rc, 0.0)) * m;
            ang *= m;
            sc = mix(1.0, sc, m);
            al = mix(1.0, al, m);
            b0 = vec4(pos, sc > 1e-4 ? al : 0.0);
            b1 = quatEuler(ang) * max(sc, 1e-4);
        }
    }
    TDImageStoreOutput(0, ivec3(p, 0), b0);
    TDImageStoreOutput(1, ivec3(p, 0), b1);
}
"""

FX = """// explode fx (compute 16x16 tiles, format useinput). in0 = picture, in1 = tiles b0, in2 = tiles b1 (Render Select).
// Amount 0 / nothing moving / tiles at rest = exact passthrough (texelFetch).
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uA;   // amount, back (0 dim, 1 alpha), backdim, camera distance px
uniform vec4 uB;   // gap px, edge width px, edge glow, shade
uniform vec4 uK;   // edge rgb, back face brightness
""" + '%LIB%' + GRID_GLSL + """
#define MAXL 128
shared vec4 sP[MAXL];      // centre xyz, alpha
shared vec4 sX[MAXL];      // tile x axis, scale
shared vec4 sY[MAXL];      // tile y axis, index
shared vec4 sZ[MAXL];      // tile normal, -
shared uint sN;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    bool ok = p.x < isz.x && p.y < isz.y;
    vec4 c0 = ok ? texelFetch(sTD2DInputs[0], p, 0) : vec4(0.0);
    vec4 gl = texelFetch(sTD2DInputs[1], ivec2(0, @NY@), 0);
    if (uA.x <= 0.0 || gl.x < 0.5) { if (ok) TDImageStoreOutput(0, ivec3(p, 0), c0); return; }   // whole dispatch
    uint lid = gl_LocalInvocationIndex;
    if (lid == 0u) sN = 0u;
    barrier();
    int N = min(int(gl.y + 0.5), @NMAX@);
    vec2 W2 = 0.5 * uS.yz;
    float F = uA.w;
    vec2 tc = vec2(gl_WorkGroupID.xy) * 16.0 + 8.0;
    float hr = 0.5 * length(uG.zw);
    for (int k = int(lid); k < N; k += 256) {
        ivec2 t = ivec2(k % @NX@, k / @NX@);
        vec4 b0 = texelFetch(sTD2DInputs[1], t, 0);
        if (b0.w <= 0.0) continue;                          // at rest (-1) or faded out (0)
        vec4 q = texelFetch(sTD2DInputs[2], t, 0);
        float s = length(q);
        float R = hr * s;
        if (b0.z + R >= F * 0.98) continue;                 // at / behind the camera
        float f = F / (F - b0.z), fb = F / (F - b0.z - R);
        vec2 sc = W2 + (b0.xy - W2) * f;
        if (length(sc - tc) > R * fb * 1.05 + 11.4) continue;
        uint n = atomicAdd(sN, 1u);
        if (n < uint(MAXL)) {
            q /= s;
            vec3 ax = vec3(1.0 - 2.0 * (q.y * q.y + q.z * q.z), 2.0 * (q.x * q.y + q.w * q.z), 2.0 * (q.x * q.z - q.w * q.y));
            vec3 ay = vec3(2.0 * (q.x * q.y - q.w * q.z), 1.0 - 2.0 * (q.x * q.x + q.z * q.z), 2.0 * (q.y * q.z + q.w * q.x));
            vec3 az = vec3(2.0 * (q.x * q.z + q.w * q.y), 2.0 * (q.y * q.z - q.w * q.x), 1.0 - 2.0 * (q.x * q.x + q.y * q.y));
            sP[n] = b0; sX[n] = vec4(ax, s); sY[n] = vec4(ay, float(k)); sZ[n] = vec4(az, 0.0);
        }
    }
    barrier();
    if (!ok) return;
    vec2 pc = vec2(p) + 0.5;
    vec3 E = vec3(W2, F);
    vec3 rd = vec3(pc - W2, -F);
    float bt = 1e30; int bj = -2, bs = 0; vec2 bq = pc; float bed = 0.0; bool bback = false;
    int own = tileAt(pc);
    if (own >= 0 && own < N && texelFetch(sTD2DInputs[1], ivec2(own % @NX@, own / @NX@), 0).w < 0.0) {
        bt = 1.0 + 1e-4; bj = -1;                           // own tile at rest: the picture (exact); flat flyers win ties
    }
    int n = int(min(sN, uint(MAXL)));
    vec2 hs = 0.5 * uG.zw;
    for (int j = 0; j < n; j++) {
        vec3 nz = sZ[j].xyz;
        float dn = dot(rd, nz);
        if (abs(dn) < 1e-6) continue;
        vec3 P = sP[j].xyz;
        float t = dot(P - E, nz) / dn;
        if (t <= 0.0 || t > bt) continue;
        int k = int(sY[j].w + 0.5);
        if (t == bt && k > bj) continue;                    // ties: lower index wins (stable)
        vec3 h = E + t * rd - P;
        float s = sX[j].w;
        vec2 l = vec2(dot(h, sX[j].xyz), dot(h, sY[j].xyz)) / s;
        vec2 rc = restCentre(k);
        float g = min(uB.x, 0.2 * (length(P.xy - rc) + abs(P.z)));    // gap grows from 0 as the tile leaves
        vec2 e2 = hs - g - abs(l);
        if (e2.x < 0.0 || e2.y < 0.0) continue;
        vec2 q = rc + l;
        if (q.x < 0.0 || q.y < 0.0 || q.x >= uS.y || q.y >= uS.z) continue;   // tile part outside the picture
        bt = t; bj = k; bs = j; bq = q; bed = min(e2.x, e2.y) * s; bback = dn > 0.0;
    }
    vec4 back = int(uA.y + 0.5) == 1 ? vec4(0.0) : vec4(c0.rgb * uA.z, c0.a);
    vec4 o = back;
    if (bj == -1) o = c0;
    else if (bj >= 0) {
        vec4 c = texture(sTD2DInputs[0], bq / vec2(isz));
        float fz = abs(sZ[bs].z);
        float br = mix(1.0, fz, uB.w) * (bback ? uK.w : 1.0);
        c.rgb *= br;
        float ek = uB.y > 0.0 ? clamp(1.0 - bed / uB.y, 0.0, 1.0) : 0.0;
        c.rgb += uK.rgb * uB.z * ek * ek;
        o = mix(back, c, sP[bs].w);
    }
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
"""


BEAT_EXEC = """# Beat CHOP rising edge -> Hittime (the explode hit latch picks it up).
def onOffToOn(channel, sampleIndex, val, prev):
    parent().par.Hittime.val = absTime.seconds
    return
"""

P = "parent().par.{}.eval()"


def shader_texts(lib):
    """The three compute shaders with the rack GLSL lib and the tile texture size filled in."""
    out = {}
    for k, t in (('hit', HIT), ('tiles', TILES), ('fx', FX)):
        for a, b in (('%LIB%', lib), ('@NX@', str(NX)), ('@NY1@', str(NY + 1)), ('@NY@', str(NY)),
                     ('@NMAX@', str(NMAX))):
            t = t.replace(a, b)
        out[k] = t
    return out


def grid_exprs():
    """uG / uS uniform expressions (TD side): stride, rows, cell w/h px; seed, W, H, brick. Cells capped so the grid
    fits NMAX tiles (Cells <= sqrt(0.9 NMAX x Aspect x W / H))."""
    W, Hh = "op('in1').width", "op('in1').height"
    asp = 'max(0.05, %s)' % P.format('Aspect')
    cols = ('max(1, min(%s, int(math.sqrt(%d * %s * %s / max(1, %s)))))'
            % (P.format('Cells'), int(NMAX * 0.9), asp, W, Hh))
    cw = '%s / %s' % (W, cols)
    return [('uG', ['%s + 1' % cols, 'math.ceil(%s / (%s * %s))' % (Hh, cw, asp), cw, '%s * %s' % (cw, asp)]),
            ('uS', [P.format('Seed'), W, Hh, 'float(%s)' % P.format('Brick')])]


def build(m, H):
    """Fill instance COMP m: hit (2x1 latch, in place) -> tiles (+ tiles_b1) -> fx (+ in1) -> out1."""
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
    be.comment = 'Beat CHOP (Explode page) rising edge -> Hittime.'
    W, Hh = "op('in1').width", "op('in1').height"
    ctr = ['%s * %s' % (pt('u'), W), '%s * %s' % (pt('v'), Hh)]
    stag = ('uE', [P.format('Stagger'), P.format('Hold'), P.format('Return'), P.format('Duration')])
    hit = compute(m, 'hit', tx['hit'], [], 2, 1, fmt='rgba32float', readwrite=True,
                  uniforms=[('uA', ['absTime.seconds', H['hit'](), H['stamp']('Resettime'),
                                    'float(%s)' % P.format('Ignorehits')]),
                            ('uB', ctr + ['parent().par.Mode.menuIndex', '0']), stag])
    hit.comment = 'explode hit latch: texel 0 = hit time, blast centre px, 7; texel 1 = last seen hit/reset (in place).'
    grid = grid_exprs()
    tl = compute(m, 'tiles', tx['tiles'], [hit], NX, NY + 1, fmt='rgba32float', bufs=2,
                 uniforms=[('uA', ['absTime.seconds', 'parent().par.Mode.menuIndex',
                                   'parent().par.Drive.menuIndex', '%s * %s' % (P.format('Progress'),
                                                                                P.format('Duration'))]),
                           ('uC', [P.format('Force'), P.format('Falloff'), P.format('Scatter'), P.format('Gravity')]),
                           ('uD', [P.format('Spin'), P.format('Tilt'), P.format('Depth'), P.format('Drag')]),
                           ('uE', [P.format('Stagger'), P.format('Hold'), P.format('Return'), P.format('Fade')]),
                           ('uF', [P.format('Amount'), P.format('Duration')] + ctr),
                           ('uH', [P.format('Shrink'), P.format('Swirl'), '0', '0'])] + grid)
    tl.comment = ('explode tiles: 1 texel per tile, b0 = centre xyz px + alpha (-1 rest), b1 = quaternion x scale; '
                  'row %d = global moving flag.' % NY)
    rs = mk(m, renderselectTOP, 'tiles_b1')
    rs.par.top = 'tiles'
    rs.par.bufferindex = 1
    rs.comment = 'tiles colour buffer 1 (rotation quaternion x scale).'
    g = compute(m, 'fx', tx['fx'], [in1, tl, rs], 'me.inputs[0].width', 'me.inputs[0].height', extend='hold',
                uniforms=[('uA', [P.format('Amount'), 'parent().par.Back.menuIndex', P.format('Backdim'),
                                  '%s * %s' % (P.format('Focal'), Hh)]),
                          ('uB', [P.format('Gap'), P.format('Edgewidth'), P.format('Edgeglow'), P.format('Shade')]),
                          ('uK', [P.format('Edgecolorr'), P.format('Edgecolorg'), P.format('Edgecolorb'),
                                  P.format('Backside')])] + grid)
    g.comment = 'explode: workgroups list moving tiles, pixels ray-cast through them (nearest wins), edge glow (DG-19).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pulse_exec', 'beat_exec'],
         'body': 'Picture; Trigger / Reset pulses + Beat CHOP -> Hittime / Resettime.'},
        {'title': '2 Explode', 'role': 'process', 'ops': ['hit', 'hit_compute', 'tiles', 'tiles_compute', 'tiles_b1',
                                                          'fx', 'fx_compute'],
         'body': 'hit: latch time + centre. tiles: analytic 3D tile motion. fx: per-workgroup tile list, ray cast.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
