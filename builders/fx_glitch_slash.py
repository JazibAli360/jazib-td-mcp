# fx_glitch_slash - FX_glitch module 'slash' (FX1 DG-27 slash cuts / parted image; FX0 row 74).
# Template: docs/builds/fx_glitch.md "Module template". One compute pass `fx` + a 1x1 `stamp` (cook clock + hits).
# Up to 8 cut lines (Count) split the picture; each cut parts its two sides by Gap px across and Slide px along the
# cut, applied one after another (cut k acts on the result of cuts 0..k-1), so the shader inverts them exactly in
# reverse order: for an output pixel and cut k, the + side's source is q - off (if it lies on the + side), else the
# - side's q + off, else the pixel is in the gap (Back + sparks). Cuts are straight or jagged (piecewise-linear hashed
# offsets along the cut), placed random / radial through the Point / parallel across the frame. Drive: manual (Open)
# or hit (Hit edge > 0.5 or Auto s -> per-cut Attack / Hold / Release envelope, staggered; each hit re-rolls the
# random cuts). Edge glow + sparks in the Glow colour. Amount 0 = exact passthrough (texelFetch). Mirror:
# builders/fx_glitch_slash_logic.py (numpy, same hash). ASCII only.

MODULE = 'slash'
PLACEMENTS = ['random', 'radial', 'parallel']

PAGES = [
    ('Slash', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Drive', 'Menu', 'hit', {'names': ['manual', 'hit'], 'labels': ['Manual (Open)', 'Hit / Auto envelope']}),
        ('Open', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Open (manual)'}),
        ('Hit', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Hit (edge > 0.5)'}),
        ('Auto', 'Float', 2.0, {'min': 0, 'max': 8, 'label': 'Auto hit every s (0 = off)'}),
        ('Count', 'Int', 1, {'min': 1, 'max': 8, 'label': 'Cuts (shader max 8)'}),
        ('Placement', 'Menu', 'random', {'names': PLACEMENTS,
                                         'labels': ['Random', 'Radial (through Point)', 'Parallel']}),
        ('Angle', 'Float', 20.0, {'min': -180, 'max': 180, 'label': 'Angle deg (0 = horizontal cut)'}),
        ('Anglejitter', 'Float', 30.0, {'min': 0, 'max': 90, 'label': 'Angle jitter deg'}),
        ('Spread', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Spread (random / parallel)'}),
        ('Gap', 'Float', 24.0, {'min': 0, 'max': 400, 'label': 'Gap px (across)'}),
        ('Slide', 'Float', 160.0, {'min': -800, 'max': 800, 'label': 'Slide px (along)'}),
        ('Randomdir', 'Toggle', True, {'label': 'Random slide direction per cut'}),
        ('Jag', 'Float', 0.0, {'min': 0, 'max': 80, 'label': 'Jag px'}),
        ('Jagsize', 'Float', 60.0, {'min': 4, 'max': 400, 'label': 'Jag segment px'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Look', [
        ('Attack', 'Float', 0.06, {'min': 0, 'max': 2, 'label': 'Attack s'}),
        ('Hold', 'Float', 0.6, {'min': 0, 'max': 8, 'label': 'Hold s'}),
        ('Release', 'Float', 0.4, {'min': 0, 'max': 4, 'label': 'Release s (0 = stay open)'}),
        ('Stagger', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Stagger s per cut'}),
        ('Back', 'Menu', 'black', {'names': ['black', 'dim', 'transparent'],
                                   'labels': ['Black', 'Dimmed picture', 'Transparent']}),
        ('Backdim', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Back dim'}),
        ('Glow', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Edge glow'}),
        ('Glowwidth', 'Float', 4.0, {'min': 0, 'max': 40, 'label': 'Glow width px'}),
        ('Sparks', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Sparks in the gap'}),
        ('Glowr', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Glow red'}),
        ('Glowg', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Glow green'}),
        ('Glowb', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Glow blue'}),
        ('Pointu', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Point u'}),
        ('Pointv', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Point v'}),
    ]),
]
PANEL_PAGES = ['Slash', 'Look']

# full-state presets (T-124 (1)): page defaults + the look, so a recall never inherits the previous preset's
# pars; edge triggers (Hit) are not stored.
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl
          if n not in ('Hit',))
PRESETS = [
    (1, 'katana', dict(_D, **{'Amount': 1.0, 'Drive': 1, 'Auto': 2.0, 'Count': 1, 'Placement': 0, 'Angle': 20.0,
                   'Anglejitter': 30.0, 'Spread': 0.5, 'Gap': 24.0, 'Slide': 160.0, 'Randomdir': 1, 'Jag': 0.0,
                   'Attack': 0.06, 'Hold': 0.6, 'Release': 0.4, 'Stagger': 0.05, 'Glow': 1.0, 'Sparks': 0.3,
                   'Back': 0, 'Seed': 1})),
    (2, 'star split', dict(_D, **{'Amount': 1.0, 'Drive': 1, 'Auto': 2.0, 'Count': 4, 'Placement': 1, 'Angle': 0.0,
                       'Anglejitter': 10.0, 'Gap': 30.0, 'Slide': 0.0, 'Randomdir': 0, 'Jag': 0.0, 'Attack': 0.1,
                       'Hold': 0.5, 'Release': 0.5, 'Stagger': 0.05, 'Glow': 1.5, 'Sparks': 0.5, 'Back': 0,
                       'Seed': 2})),
    (3, 'blinds', dict(_D, **{'Amount': 1.0, 'Drive': 1, 'Auto': 2.0, 'Count': 6, 'Placement': 2, 'Angle': 0.0,
                   'Anglejitter': 0.0, 'Spread': 1.0, 'Gap': 16.0, 'Slide': 60.0, 'Randomdir': 1, 'Jag': 0.0,
                   'Attack': 0.08, 'Hold': 0.8, 'Release': 0.3, 'Stagger': 0.04, 'Glow': 0.5, 'Sparks': 0.0,
                   'Back': 1, 'Backdim': 0.15, 'Seed': 3})),
    (4, 'jagged tear', dict(_D, **{'Amount': 1.0, 'Drive': 1, 'Auto': 2.0, 'Count': 5, 'Placement': 0, 'Angle': 70.0,
                        'Anglejitter': 60.0, 'Spread': 0.7, 'Gap': 10.0, 'Slide': 40.0, 'Randomdir': 1, 'Jag': 18.0,
                        'Jagsize': 40.0, 'Attack': 0.05, 'Hold': 0.7, 'Release': 0.5, 'Stagger': 0.08,
                        'Glow': 2.0, 'Sparks': 0.6, 'Back': 0, 'Seed': 4})),
    (5, 'manual part', dict(_D, **{'Amount': 1.0, 'Drive': 0, 'Open': 1.0, 'Auto': 0.0, 'Count': 2, 'Placement': 2,
                        'Angle': 90.0, 'Anglejitter': 0.0, 'Spread': 0.6, 'Gap': 40.0, 'Slide': 0.0, 'Randomdir': 0,
                        'Jag': 0.0, 'Glow': 1.0, 'Sparks': 0.2, 'Back': 0, 'Seed': 5})),
]

LIB = """
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float h3(uint a, uint b, uint c) { return float(lb32(a * 1597334677u ^ lb32(b ^ lb32(c + 0x9e3779b9u)))) * (1.0 / 4294967296.0); }
"""

SHADER = """// FX_glitch slash (compute, T-47). in0 = picture (inputextenduv hold), in1 = stamp (1x1: x now, y previous cook,
// z last hit time (< -500 = never), w = 2 * hit count + last edge bit).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, count, gap px, slide px
uniform vec4 uB;   // placement, angle deg, angle jitter deg, spread
uniform vec4 uC;   // jag px, jag segment px, randomdir, seed
uniform vec4 uD;   // drive, open, attack, hold
uniform vec4 uE;   // release, stagger, back, backdim
uniform vec4 uF;   // glow, glow width, sparks, -
uniform vec4 uG;   // point u, point v, -, -
uniform vec4 uK;   // glow rgb, -
""" + LIB + """
float jag(float u, uint key) {                     // piecewise-linear hashed offset along the cut, -1..1
    float s = u / max(uC.y, 1.0);
    float i = floor(s);
    float f = s - i;
    uint ii = uint(int(i) + 1048576);
    float a = h3(ii, key, 11u) * 2.0 - 1.0;
    float b = h3(ii + 1u, key, 11u) * 2.0 - 1.0;
    return mix(a, b, f);
}
float sideF(vec2 q, vec2 c, vec2 t, vec2 n, uint key) {
    vec2 r = q - c;
    float f = dot(r, n);
    if (uC.x > 0.0) f -= uC.x * jag(dot(r, t), key);
    return f;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c0); return; }      // exact passthrough
    vec4 st = texelFetch(sTD2DInputs[1], ivec2(0), 0);
    vec2 sz = vec2(isz);
    float now = st.x;
    uint cnt = uint(max(floor(st.w * 0.5), 0.0));
    uint seed = uint(uC.w);
    int N = clamp(int(uA.y + 0.5), 0, 8);
    int pl = int(uB.x + 0.5);
    vec2 P = uG.xy * sz;
    float ext = 0.0;
    vec2 q = vec2(p) + 0.5;
    bool gap = false;
    float edge = 1e20, eo = 0.0;
    int gk = -1; float gu = 0.0, gf = 0.0, gh = 1.0;
    for (int k = 7; k >= 0; k--) {
        if (k >= N) continue;
        uint key = lb32(seed * 7919u + cnt * 104729u + uint(k) * 31u);
        float o;                                                                 // open 0..1
        if (int(uD.x + 0.5) == 0) o = uD.y;
        else {
            float tk = now - (st.z + float(k) * uE.y);
            if (st.z < -500.0 || tk < 0.0) o = 0.0;
            else if (tk < uD.z) o = smoothstep(0.0, 1.0, tk / uD.z);
            else if (tk < uD.z + uD.w || uE.x <= 0.0) o = 1.0;
            else o = 1.0 - smoothstep(0.0, 1.0, (tk - uD.z - uD.w) / uE.x);
        }
        if (o <= 0.0) continue;
        float a = radians(uB.y + (h3(key, 1u, 0u) * 2.0 - 1.0) * uB.z);
        vec2 cen = P;
        if (pl == 1) a = radians(uB.y + float(k) * 180.0 / float(max(N, 1)) + (h3(key, 1u, 0u) * 2.0 - 1.0) * uB.z);
        vec2 t = vec2(cos(a), sin(a));
        vec2 n = vec2(-t.y, t.x);
        if (pl == 0) cen = P + (vec2(h3(key, 2u, 0u), h3(key, 3u, 0u)) - 0.5) * uB.w * sz;
        else if (pl == 2) {
            ext = abs(n.x) * sz.x + abs(n.y) * sz.y;
            cen = P + n * ((float(k) + 0.5) / float(max(N, 1)) - 0.5) * uB.w * ext;
        }
        float sg = (uC.z > 0.5 && h3(key, 4u, 0u) < 0.5) ? -1.0 : 1.0;
        vec2 off = o * (n * uA.z * 0.5 + t * uA.w * 0.5 * sg);
        float fp = sideF(q - off, cen, t, n, key);
        if (fp > 0.0) { q -= off; if (fp < edge) { edge = fp; eo = o; } continue; }
        float fm = sideF(q + off, cen, t, n, key);
        if (fm <= 0.0) { q += off; if (-fm < edge) { edge = -fm; eo = o; } continue; }
        gap = true; gk = k; gu = dot(q - cen, t); gf = sideF(q, cen, t, n, key); gh = max(o * uA.z * 0.5, 1e-3);
        break;
    }
    int bm = int(uE.z + 0.5);
    vec4 back = bm == 0 ? vec4(0.0, 0.0, 0.0, c0.a) : (bm == 1 ? vec4(c0.rgb * uE.w, c0.a) : vec4(0.0));
    vec4 res;
    if (gap) {
        res = back;
        if (uF.z > 0.0) {                                                        // sparks: hashed dots in the gap
            uint key = lb32(seed * 7919u + cnt * 104729u + uint(gk) * 31u);
            uint cell = uint(int(floor(gu / 4.0)) + 1048576);
            uint tick = uint(max(floor(now * 30.0), 0.0));
            float s = h3(cell, tick, key);
            if (s < uF.z * 0.5) {
                float w = (1.0 - clamp(abs(gf) / gh, 0.0, 1.0)) * (0.5 + h3(cell, tick, key + 5u));
                res.rgb += uK.rgb * uF.x * w;
                res.a = max(res.a, clamp(w, 0.0, 1.0));
            }
        }
    } else if (q.x < 0.0 || q.y < 0.0 || q.x > sz.x || q.y > sz.y) {
        res = back;                                                              // moved in from outside the frame
    } else {
        res = texture(sTD2DInputs[0], q / sz);
        if (uF.x > 0.0 && edge < 1e19) res.rgb += uK.rgb * uF.x * eo * exp(-edge / max(uF.y, 1e-3));
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c0, res, uA.x));
}
"""

STAMP = """// stamp: 1x1 rgba32float in place. x now, y previous cook, z last hit time (-1000 = never), w = 2 * count + edge.
// Hit on the Hit edge (> 0.5) or when Auto s have passed since the last hit (Auto > 0).
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;   // now, hit value, auto s, -
void main() {
    vec4 s = TDImageLoadOutput(0, ivec3(0));
    if (s.x <= 0.0) s = vec4(0.0, 0.0, -1000.0, 0.0);                              // first cook: never hit
    float cnt = floor(s.w * 0.5);
    float pb = s.w - cnt * 2.0;
    float b = uT.y > 0.5 ? 1.0 : 0.0;
    float ht = s.z;
    bool go = (b > 0.5 && pb < 0.5) || (uT.z > 0.0 && uT.x - ht >= uT.z);
    if (go) { ht = uT.x; cnt += 1.0; }
    TDImageStoreOutput(0, ivec3(0), vec4(uT.x, s.x, ht, cnt * 2.0 + b));
}
"""

P = "parent().par.{}.eval()"


def uniforms():
    """(stamp uniforms, fx uniforms) as [(name, [x, y, z, w exprs])]; pure, tested offline."""
    st = [('uT', ['absTime.seconds', P.format('Hit'), P.format('Auto'), '0'])]
    fx = [('uA', [P.format('Amount'), P.format('Count'), P.format('Gap'), P.format('Slide')]),
          ('uB', ['parent().par.Placement.menuIndex', P.format('Angle'), P.format('Anglejitter'), P.format('Spread')]),
          ('uC', [P.format('Jag'), P.format('Jagsize'), 'float(%s)' % P.format('Randomdir'), P.format('Seed')]),
          ('uD', ['parent().par.Drive.menuIndex', P.format('Open'), P.format('Attack'), P.format('Hold')]),
          ('uE', [P.format('Release'), P.format('Stagger'), 'parent().par.Back.menuIndex', P.format('Backdim')]),
          ('uF', [P.format('Glow'), P.format('Glowwidth'), P.format('Sparks'), '0']),
          ('uG', [P.format('Pointu'), P.format('Pointv'), '0', '0']),
          ('uK', [P.format('Glowr'), P.format('Glowg'), P.format('Glowb'), '0'])]
    return st, fx


def build(m, H):
    """Fill instance COMP m: in1 -> stamp (1x1 clock + hits) -> fx (compute, hold extend) -> out1."""
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    ust, ufx = uniforms()
    st = H['compute'](m, 'stamp', STAMP, [], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    H['uniforms'](st, ust)
    st.comment = 'Cook clock + hits: x now, y prev cook, z last hit (Hit edge / Auto), w = 2 * count + edge bit.'
    g = H['compute'](m, 'fx', SHADER, [in1, st])
    g.par.inputextenduv = 'hold'
    H['uniforms'](g, ufx)
    g.comment = 'slash: up to 8 cuts part the picture (gap + slide), inverted in reverse order; glow + sparks (DG-27).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Slash', 'role': 'process', 'ops': ['stamp', 'stamp_compute', 'fx', 'fx_compute'],
         'body': 'stamp = clock + hit count; fx inverts the cuts (last first) per pixel.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
