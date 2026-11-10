# fx_glitch_misc - FX_glitch module 'misc' (FX0 row 82, FX4 G-* micro effects): ONE module, a Type menu picks one of
# eight small picture effects, all in ONE compute pass `fx` (+ a 2x1 `stats` pass that only works for autolevel):
#   bend       G-BEND: rectangular -> polar morph around the Point (Strength = morph, Length = radius of the top row)
#   suck       Suckr black hole: radial pull toward the Point + swirl, event-horizon disc (Size px)
#   tri        G-TRI: triangle lattice pixelation (Size px, Angle), Sierpinski midpoint subdivision where detail is high
#   longshadow G-LONGSHADOW: pixels above Threshold cast a shadow along Angle up to Length px (<= 32 taps), Colour
#   electrify  G-ELECTRIFY: Sobel luma edges at a noise-jittered position, glow Colour x Glow, flicker per Rate tick
#   autolevel  G-AUTOLEVEL: black / white point per channel or linked, from `stats` (mip level reduction, smoothed)
#   displace   G-DISP: displace by the luma gradient of the picture or a Map TOP; Prism = per-channel amounts
#   zap        G-ZAP: lightning bolt Point -> Point 2 (fbm offset, tapered ends) + up to 6 branches, additive glow
#   arcs       TC-03 arc bolts between tracked points: any Points CHOP (blob / hand / effector centres) -> the
#              `arcs` Script CHOP builds <= 32 arcs (chain / pairs within Reach / nearest) whose power rises as the
#              points get closer; the shader draws each as a zap bolt (culled per pixel), glow x power
# Skipped on purpose (doc docs/builds/fx_glitch_misc.md): sparkle (GEN_points.sparkle), Tao / Mir (3D generators),
# heat (FX_palette_map thermal), smear (FX_glitch.smear).
# Template: docs/builds/fx_glitch.md "Module template". Numpy reference: builders/fx_glitch_misc_logic.py.
# Amount 0 = exact passthrough (texelFetch). Rate re-rolls electrify / zap (0 = frozen). No limits. ASCII only.

MODULE = 'misc'
TYPES = ['bend', 'suck', 'tri', 'longshadow', 'electrify', 'autolevel', 'displace', 'zap', 'arcs']
TYPE_LABELS = ['Bend (polar morph)', 'Suck (black hole)', 'Triangulate', 'Long shadow', 'Electrify (edge glow)',
               'Auto levels', 'Displace (gradient)', 'Zap (lightning)', 'Arcs between points (TC-03)']
ARCMODES = ['chain', 'pairs', 'nearest']
SPACES = ['uv', 'ndc', 'pixels']

PAGES = [
    ('Misc', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Type', 'Menu', 'bend', {'names': TYPES, 'labels': TYPE_LABELS}),
        ('Strength', 'Float', 1.0, {'min': -2, 'max': 2, 'label': 'Strength'}),
        ('Size', 'Float', 40.0, {'min': 1, 'max': 200, 'label': 'Size px (cell / hole / noise / gradient)'}),
        ('Angle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle deg (shadow / lattice / swirl / seam)'}),
        ('Length', 'Float', 240.0, {'min': 0, 'max': 1000, 'label': 'Length px (shadow / radius / jitter / push)'}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Threshold'}),
        ('Softness', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Softness'}),
        ('Decay', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Shadow falloff'}),
        ('Width', 'Float', 3.0, {'min': 0.5, 'max': 20, 'label': 'Width px (edge / bolt)'}),
        ('Rate', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Re-roll / flicker per s (0 = frozen)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Points', [
        ('Pointu', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Point u (centre / bolt start)'}),
        ('Pointv', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Point v'}),
        ('Point2u', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Point 2 u (bolt end)'}),
        ('Point2v', 'Float', 0.95, {'min': 0, 'max': 1, 'label': 'Point 2 v'}),
        ('Pointchop', 'CHOP', '', {'label': 'Points CHOP (arcs; empty = Point + Point 2)'}),
        ('Pointspace', 'Menu', 'uv', {'names': SPACES, 'labels': ['UV 0..1', 'NDC -1..1', 'Pixels']}),
        ('Arcmode', 'Menu', 'chain', {'names': ARCMODES, 'labels': ['Chain (in order)', 'All pairs within Reach',
                                                                     'Nearest neighbour']}),
        ('Reach', 'Float', 0.4, {'min': 0, 'max': 1.5, 'label': 'Reach (frame heights; 0 = always full)'}),
        ('Arcfalloff', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Power falloff with distance'}),
        ('Maxarcs', 'Int', 16, {'min': 1, 'max': 32, 'label': 'Max arcs'}),
    ]),
    ('Colour', [
        ('Colr', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'Colour R'}),
        ('Colg', 'Float', 0.75, {'min': 0, 'max': 1, 'label': 'Colour G'}),
        ('Colb', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Colour B'}),
        ('Glow', 'Float', 1.5, {'min': 0, 'max': 6, 'label': 'Glow gain (electrify / zap)'}),
    ]),
    ('Tri', [
        ('Detail', 'Float', 0.08, {'min': 0, 'max': 0.5, 'label': 'Detail (split above)'}),
        ('Levels', 'Int', 3, {'min': 0, 'max': 4, 'label': 'Subdivision levels'}),
        ('Edges', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Edge darken'}),
        ('Lattice', 'Menu', 'equilateral', {'names': ['classic', 'equilateral'],
                                            'labels': ['Classic (row-shifted, 26 Oct look)', 'Equilateral']}),
    ]),
    ('Levels', [
        ('Clip', 'Float', 0.0, {'min': -0.25, 'max': 0.45, 'label': 'Clip (range shrink)'}),
        ('Linked', 'Toggle', False, {'label': 'Linked (one range for RGB)'}),
        ('Smooth', 'Float', 0.3, {'min': 0, 'max': 3, 'label': 'Smooth s (0 = instant)'}),
        ('Level', 'Int', 4, {'min': 0, 'max': 8, 'label': 'Stats mip level'}),
    ]),
    ('Displace', [
        ('Prism', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Prism (per-channel spread)'}),
        ('Maptop', 'TOP', '', {'label': 'Map TOP (empty = picture)'}),
    ]),
    ('Zap', [
        ('Jag', 'Float', 0.15, {'min': 0, 'max': 0.6, 'label': 'Jaggedness'}),
        ('Branches', 'Int', 3, {'min': 0, 'max': 6, 'label': 'Branches'}),
    ]),
]
PANEL_PAGES = ['Misc', 'Points', 'Colour', 'Tri', 'Levels', 'Displace', 'Zap']

# Full-state presets (T-124 (1): a partial preset inherits the previous look): page defaults + the look.
_D = {'Amount': 1.0, 'Type': 0, 'Strength': 1.0, 'Size': 40.0, 'Angle': 0.0, 'Length': 240.0, 'Threshold': 0.5,
      'Softness': 0.1, 'Decay': 0.6, 'Width': 3.0, 'Rate': 0.0, 'Seed': 1, 'Pointu': 0.5, 'Pointv': 0.5,
      'Point2u': 0.5, 'Point2v': 0.95, 'Colr': 0.55, 'Colg': 0.75, 'Colb': 1.0, 'Glow': 1.5, 'Detail': 0.08,
      'Levels': 3, 'Edges': 0.3, 'Clip': 0.0, 'Linked': 0, 'Smooth': 0.3, 'Level': 4, 'Prism': 0.0, 'Jag': 0.15,
      'Branches': 3, 'Lattice': 1, 'Pointspace': 0, 'Arcmode': 0, 'Reach': 0.4, 'Arcfalloff': 1.0, 'Maxarcs': 16}
PRESETS = [
    (1, 'black hole', dict(_D, Type=1, Strength=1.5, Size=60.0, Angle=120.0, Length=300.0, Softness=0.3)),
    (2, 'long shadow', dict(_D, Type=3, Angle=135.0, Length=300.0, Threshold=0.55, Softness=0.1, Decay=0.5,
                            Strength=0.85, Colr=0.0, Colg=0.0, Colb=0.0)),
    (3, 'triangulate', dict(_D, Type=2, Size=96.0, Detail=0.06, Levels=3, Edges=0.4, Lattice=0)),  # 26 Oct look
    (4, 'electric', dict(_D, Type=4, Size=24.0, Length=4.0, Threshold=0.25, Softness=0.3, Width=2.0, Rate=12.0,
                         Colr=0.5, Colg=0.8, Colb=1.0, Glow=2.0)),
    (5, 'zap', dict(_D, Type=7, Rate=10.0, Jag=0.15, Branches=4, Width=3.0, Glow=2.0, Pointu=0.5, Pointv=0.1,
                    Point2u=0.5, Point2v=0.9, Colr=0.6, Colg=0.8, Colb=1.0)),
    (6, 'arc pair', dict(_D, Type=8, Rate=14.0, Jag=0.18, Width=2.5, Glow=2.5, Pointu=0.3, Pointv=0.45,
                         Point2u=0.7, Point2v=0.55, Colr=0.55, Colg=0.75, Colb=1.0, Arcmode=0, Reach=0.0)),
    (7, 'plasma web', dict(_D, Type=8, Rate=20.0, Jag=0.22, Width=2.0, Glow=2.0, Colr=0.8, Colg=0.5, Colb=1.0,
                           Arcmode=1, Reach=0.45, Arcfalloff=1.5, Maxarcs=24)),
    (8, 'neighbour sparks', dict(_D, Type=8, Rate=10.0, Jag=0.3, Width=1.5, Glow=3.0, Colr=1.0, Colg=0.8,
                                 Colb=0.4, Arcmode=2, Reach=0.3, Arcfalloff=0.7, Maxarcs=32)),
]

ARCS_PY = '''# misc `arcs` (TC-03): points -> arc list. Pure Python, shared by the Script CHOP and the offline tests.
import math


def read_points(chans, nsamples, space, W, H):
    """chans = [(name, [values])]. Samples = points (channels tx/ty, u/v, x/y or the first two), or one sample with
    channels x y x y ... (hand / face landmark CHOPs). -> [(x px, y px)] (TD y up)."""
    names = [n for n, _v in chans]
    vals = dict(chans)
    pts = []
    pair = None
    for a, b in (('tx', 'ty'), ('u', 'v'), ('x', 'y')):
        if a in vals and b in vals:
            pair = (a, b)
            break
    if pair is None and nsamples > 1 and len(names) >= 2:
        pair = (names[0], names[1])
    if nsamples < 1:
        return []
    if pair is not None and nsamples > 1:
        pts = list(zip(vals[pair[0]], vals[pair[1]]))
    elif len(names) >= 2:
        flat = [vals[n][0] for n in names]
        pts = [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]
    out = []
    for x, y in pts:
        if space == 1:
            x, y = (x + 1.0) * 0.5, (y + 1.0) * 0.5
        if space != 2:
            x, y = x * W, y * H
        out.append((float(x), float(y)))
    return out


def arc_list(pts, mode, reach, falloff, maxarcs, H):
    """-> [(x0, y0, x1, y1, power, seed)] strongest first, at most maxarcs. Distance in frame heights; power =
    (1 - d / reach) ^ falloff inside reach (reach 0 = power 1 always). Many points (tracker CHOPs: 64+) take the
    numpy path (same arcs, ~10x faster in TD; tested equal to the loop below)."""
    if mode in (1, 2) and len(pts) >= 12:
        try:
            return arc_list_np(pts, mode, reach, falloff, maxarcs, H)
        except ImportError:
            pass
    return arc_list_py(pts, mode, reach, falloff, maxarcs, H)


def arc_list_np(pts, mode, reach, falloff, maxarcs, H):
    import numpy as np
    P = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    n = len(P)
    if mode == 1:
        I, J = np.triu_indices(n, 1)                     # (i, j) i < j in the loop's order
    else:
        d2 = ((P[:, None, :] - P[None, :, :]) ** 2).sum(-1)
        np.fill_diagonal(d2, np.inf)
        best = np.argmin(d2, axis=1)                     # first minimum, like the loop's strict <
        seen, I, J = set(), [], []
        for i in range(n):
            k = (min(i, int(best[i])), max(i, int(best[i])))
            if k not in seen:
                seen.add(k)
                I.append(k[0])
                J.append(k[1])
        I, J = np.array(I, dtype=np.int64), np.array(J, dtype=np.int64)
    d = np.hypot(P[I, 0] - P[J, 0], P[I, 1] - P[J, 1]) / max(H, 1)
    if reach <= 0:
        p = np.ones(len(I))
    else:
        p = np.where(d < reach, np.maximum(0.0, 1.0 - d / reach) ** falloff, 0.0)
    keep = np.nonzero(p > 0)[0]
    keep = keep[np.argsort(-p[keep], kind='stable')][:max(1, int(maxarcs))]
    return [(float(P[I[k], 0]), float(P[I[k], 1]), float(P[J[k], 0]), float(P[J[k], 1]), float(p[k]),
             float((int(I[k]) * 31 + int(J[k]) * 17) % 997)) for k in keep]


def arc_list_py(pts, mode, reach, falloff, maxarcs, H):
    def pw(i, j):
        d = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]) / max(H, 1)
        if reach <= 0:
            return 1.0
        return max(0.0, 1.0 - d / reach) ** falloff if d < reach else 0.0
    cand = []
    n = len(pts)
    if mode == 0:
        cand = [(i, i + 1) for i in range(n - 1)]
    elif mode == 1:
        cand = [(i, j) for i in range(n) for j in range(i + 1, n)]
    else:
        seen = set()
        for i in range(n):
            best = None
            for j in range(n):
                if j != i:
                    d = (pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2
                    if best is None or d < best[0]:
                        best = (d, j)
            if best is not None:
                k = (min(i, best[1]), max(i, best[1]))
                if k not in seen:
                    seen.add(k)
                    cand.append(k)
    arcs = []
    for i, j in cand:
        p = pw(i, j)
        if p > 0:
            arcs.append((pts[i][0], pts[i][1], pts[j][0], pts[j][1], p, float((i * 31 + j * 17) % 997)))
    arcs.sort(key=lambda a: -a[4])
    return arcs[:max(1, int(maxarcs))]
'''

ARCS_CB = '''# arcs: Points CHOP (input 0 = pts_sel) or the Point / Point 2 pars -> 2 samples per arc, channels a b c d:
# sample 2k = x0 y0 x1 y1 (px), 2k + 1 = power seed 0 0; read by fx as uniform samplerBuffer uArcs (count = uH.y).
def onSetupParameters(scriptOp):
    return

def onCook(scriptOp):
    m = parent()
    A = op('arcs_logic').module
    i1 = op('in1')
    W, H = (i1.width, i1.height) if i1 is not None and i1.width > 0 else (1080, 1920)
    src = scriptOp.inputs[0] if scriptOp.inputs else None
    pts = []
    if src is not None and src.numChans >= 2 and m.par.Pointchop.eval() is not None:
        pts = A.read_points([(c.name, list(c.vals)) for c in src.chans()], src.numSamples,
                            m.par.Pointspace.menuIndex, W, H)
    if len(pts) < 2 and m.par.Pointchop.eval() is None:      # a Points CHOP with < 2 points = no arcs
        pts = [(m.par.Pointu.eval() * W, m.par.Pointv.eval() * H), (m.par.Point2u.eval() * W, m.par.Point2v.eval() * H)]
    arcs = A.arc_list(pts, m.par.Arcmode.menuIndex, m.par.Reach.eval(), m.par.Arcfalloff.eval(),
                      m.par.Maxarcs.eval(), H)
    scriptOp.clear()
    scriptOp.numSamples = 2 * max(1, len(arcs))
    ch = [scriptOp.appendChan(n) for n in 'abcd']
    vals = [[0.0] * scriptOp.numSamples for _ in range(4)]
    for k, a in enumerate(arcs):
        for q in range(4):
            vals[q][2 * k] = a[q]
        vals[0][2 * k + 1], vals[1][2 * k + 1] = a[4], a[5]
    for c, v in zip(ch, vals):
        c.vals = v
    scriptOp.store('count', len(arcs))
    return
'''

LIB = """
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hsh(ivec2 c, uint s) { return float(lb32(uint(c.x) * 1597334677u ^ lb32(uint(c.y) ^ (s * 2654435761u)))) * (1.0 / 4294967296.0); }
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
"""

STATS = """// misc stats (compute, ONE 256-thread workgroup, 2x1 rgba32float in place): texel 0 = lo rgb + last cook time,
// texel 1 = hi rgb + mean luma, over the input's mip level uT.z (inputfiltertype mipmap only while Type = autolevel).
// Smoothed: k = 1 - exp(-dt / Smooth); first cook / a gap > 0.25 s / Smooth 0 = take the new values.
layout (local_size_x = 256, local_size_y = 1) in;
uniform vec4 uT;   // now, smooth s, mip level, active (Type == autolevel)
""" + LIB + """
shared vec3 sLo[256];
shared vec3 sHi[256];
shared float sM[256];
void main() {
    uint lid = gl_LocalInvocationIndex;
    if (uT.w < 0.5) return;                                                    // uniform: not autolevel
    int L = int(uT.z + 0.5);
    ivec2 ms = textureSize(sTD2DInputs[0], L);
    int n = ms.x * ms.y;
    vec3 lo = vec3(1e9), hi = vec3(-1e9);
    float sm = 0.0;
    for (int k = 0; k < 256; k++) {                                             // <= 65536 texels
        int i = int(lid) + k * 256;
        if (i >= n) break;
        vec3 c = texelFetch(sTD2DInputs[0], ivec2(i % ms.x, i / ms.x), L).rgb;
        lo = min(lo, c); hi = max(hi, c); sm += luma(c);
    }
    sLo[lid] = lo; sHi[lid] = hi; sM[lid] = sm;
    barrier();
    for (uint st = 128u; st > 0u; st >>= 1) {
        if (lid < st) {
            sLo[lid] = min(sLo[lid], sLo[lid + st]);
            sHi[lid] = max(sHi[lid], sHi[lid + st]);
            sM[lid] += sM[lid + st];
        }
        barrier();
    }
    if (lid == 0u) {
        vec4 s0 = TDImageLoadOutput(0, ivec3(0, 0, 0));
        vec4 s1 = TDImageLoadOutput(0, ivec3(1, 0, 0));
        float dt = uT.x - s0.w;
        float k = (s0.w <= 0.0 || dt > 0.25 || dt < 0.0 || uT.y <= 0.0) ? 1.0 : 1.0 - exp(-dt / uT.y);
        float mean = sM[0] / float(max(n, 1));
        TDImageStoreOutput(0, ivec3(0, 0, 0), vec4(mix(s0.rgb, sLo[0], k), uT.x));
        TDImageStoreOutput(0, ivec3(1, 0, 0), vec4(mix(s1.rgb, sHi[0], k), mix(s1.a, mean, k)));
    }
}
"""

SHADER = """// FX_glitch misc (compute, T-47). in0 picture (texelFetch / texture, extend hold), in1 stats (2x1), in2 map
// (Select: Map TOP or a 1x1). One Type per cook; Amount 0 = exact passthrough. Mirror: fx_glitch_misc_logic.py.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount type strength size
uniform vec4 uB;   // angle(deg) length threshold softness
uniform vec4 uC;   // point u v, point2 u v
uniform vec4 uD;   // colour rgb, glow
uniform vec4 uE;   // epoch seed decay width
uniform vec4 uF;   // detail levels edges prism
uniform vec4 uG;   // jag branches clip linked
uniform vec4 uH;   // usemap arccount lattice (tri: 0 classic row shift, 1 equilateral) -
uniform samplerBuffer uArcs;   // arcs Script CHOP: 2 samples per arc (x0 y0 x1 y1 px | power seed 0 0)
""" + LIB + """
vec2 SZ;
vec4 tex(vec2 q) { return texture(sTD2DInputs[0], q / SZ); }
float ltex(vec2 q) { return luma(tex(q).rgb); }
float vnoise(vec2 x, uint s) {
    ivec2 i = ivec2(floor(x)); vec2 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    float a = hsh(i, s), b = hsh(i + ivec2(1, 0), s), c = hsh(i + ivec2(0, 1), s), d = hsh(i + ivec2(1, 1), s);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float vn1(float x, uint s) {
    float i = floor(x); float f = x - i; f = f * f * (3.0 - 2.0 * f);
    return mix(hsh(ivec2(int(i), 0), s), hsh(ivec2(int(i) + 1, 0), s), f);
}
float fbm1(float x, uint s) {
    float v = 0.0, a = 0.5, n = 0.0;
    for (int k = 0; k < 5; k++) { v += a * vn1(x, s + uint(k) * 101u); n += a; x = x * 2.03 + 17.1; a *= 0.5; }
    return v / n;
}
float cast_(vec4 c) { return smoothstep(uB.z - uB.w, uB.z + uB.w + 1e-4, luma(c.rgb)) * c.a; }
vec3 bary(vec2 a, vec2 b, vec2 c, vec2 p) {
    vec2 v0 = b - a, v1 = c - a, v2 = p - a;
    float d00 = dot(v0, v0), d01 = dot(v0, v1), d11 = dot(v1, v1), d20 = dot(v2, v0), d21 = dot(v2, v1);
    float den = d00 * d11 - d01 * d01;
    float v = (d11 * d20 - d01 * d21) / den, w = (d00 * d21 - d01 * d20) / den;
    return vec3(1.0 - v - w, v, w);
}
float CA, SA;
vec2 unrot(vec2 v) { return vec2(CA * v.x - SA * v.y, SA * v.x + CA * v.y) + 0.5 * SZ; }
float bolt(vec2 q, vec2 P0, vec2 P1, uint s) {
    vec2 d = P1 - P0; float L = max(length(d), 1e-3); vec2 u = d / L; vec2 n = vec2(-u.y, u.x);
    vec2 r = q - P0; float t = dot(r, u) / L; float dp = dot(r, n);
    float tc = clamp(t, 0.0, 1.0);
    float off = uG.x * L * (fbm1(tc * 6.0, s) - 0.5) * 4.0 * tc * (1.0 - tc);
    return length(vec2((t - tc) * L, dp - off));
}
float mapL(vec2 q) {
    return uH.x > 0.5 ? luma(texture(sTD2DInputs[2], q / SZ).rgb) : ltex(q);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }       // exact passthrough
    SZ = vec2(isz);
    vec2 pc = vec2(p) + 0.5;
    int ty = int(uA.y + 0.5);
    uint sd = uint(uE.y) * 7919u + uint(uE.x) * 104729u;
    vec4 o = c;
    if (ty == 0) {                                                              // bend: rect -> polar morph
        vec2 C = uC.xy * SZ; vec2 r = pc - C;
        float a = atan(r.y, r.x);
        float up = fract(a / 6.2831853 + 0.5 + uB.x / 360.0);
        vec2 ps = vec2(up * SZ.x, length(r) / max(uB.y, 1e-3) * SZ.y);
        o = tex(pc + (ps - pc) * uA.z);
    } else if (ty == 1) {                                                       // suck: black hole
        vec2 C = uC.xy * SZ; vec2 d = pc - C; float r = length(d);
        float Ls = max(uB.y, 1e-3);
        float rs = r * (1.0 + uA.z * Ls / (r + Ls));
        float sw = radians(uB.x) * exp(-r / Ls);
        vec2 u = r > 1e-4 ? d / r : vec2(0.0);
        float cs = cos(sw), sn = sin(sw);
        vec4 s = tex(C + vec2(cs * u.x - sn * u.y, sn * u.x + cs * u.y) * rs);
        float hole = 1.0 - smoothstep(uA.w, uA.w * (1.0 + uB.w) + 1.0, r);
        o = vec4(s.rgb * (1.0 - hole), s.a);
    } else if (ty == 2) {                                                       // tri: lattice + Sierpinski split
        float s = max(uA.w, 1.0);
        float an = radians(uB.x); CA = cos(an); SA = sin(an);
        vec2 q0 = pc - 0.5 * SZ;
        vec2 q = vec2(CA * q0.x + SA * q0.y, -SA * q0.x + CA * q0.y);
        float h = s * 0.8660254;
        float j = floor(q.y / h); float fy = q.y / h - j;
        float xs = q.x / s - 0.5 * (uH.z > 0.5 ? q.y / h : j); float i = floor(xs); float fx = xs - i;
        vec2 V0, V1, V2;
        if (fx + fy < 1.0) { V0 = vec2((i + 0.5 * j) * s, j * h); V1 = vec2((i + 1.0 + 0.5 * j) * s, j * h); }
        else { V0 = vec2((i + 1.0 + 0.5 * j) * s, j * h); V1 = vec2((i + 1.0 + 0.5 * (j + 1.0)) * s, (j + 1.0) * h); }
        V2 = vec2((i + 0.5 * (j + 1.0)) * s, (j + 1.0) * h);
        for (int k = 0; k < 4; k++) {
            if (float(k) >= uF.y) break;
            vec2 G = (V0 + V1 + V2) / 3.0;
            float lg = ltex(unrot(G));
            float var = max(max(abs(ltex(unrot(V0)) - lg), abs(ltex(unrot(V1)) - lg)), abs(ltex(unrot(V2)) - lg));
            if (var <= uF.x) break;
            vec3 l = bary(V0, V1, V2, q);
            vec2 m01 = (V0 + V1) / 2.0, m12 = (V1 + V2) / 2.0, m20 = (V2 + V0) / 2.0;
            if (l.x > 0.5) { V1 = m01; V2 = m20; }
            else if (l.y > 0.5) { V0 = m01; V2 = m12; }
            else if (l.z > 0.5) { V0 = m20; V1 = m12; }
            else { V0 = m12; V1 = m20; V2 = m01; }
        }
        vec2 G = (V0 + V1 + V2) / 3.0;
        vec4 col = tex(unrot(G));
        vec3 l = bary(V0, V1, V2, q);
        float dpx = min(l.x, min(l.y, l.z)) * length(V1 - V0) * 0.8660254;
        o = vec4(col.rgb * (1.0 - uF.z * (1.0 - smoothstep(0.0, 1.5, dpx))), col.a);
    } else if (ty == 3) {                                                       // long shadow
        float an = radians(uB.x); vec2 dir = vec2(sin(an), -cos(an));
        int N = int(clamp(ceil(uB.y / 6.0), 1.0, 32.0));                       // <= 32 taps (perf)
        float stp = uB.y / float(N);
        float sh = 0.0;
        for (int k = 1; k <= 32; k++) {
            if (k > N) break;
            vec4 s = tex(pc - dir * stp * float(k));
            sh = max(sh, cast_(s) * (1.0 - float(k) / float(N) * uE.z));
        }
        sh *= 1.0 - cast_(c);
        o = vec4(mix(c.rgb, uD.rgb, sh * uA.z), c.a);
    } else if (ty == 4) {                                                       // electrify
        vec2 nq = pc / max(uA.w, 1.0);
        vec2 jit = (vec2(vnoise(nq, sd), vnoise(nq + 31.7, sd + 17u)) - 0.5) * 2.0 * uB.y;
        vec2 q = pc + jit;
        float w = max(uE.w, 0.5);
        float tl = ltex(q + vec2(-w, w)), t = ltex(q + vec2(0.0, w)), tr = ltex(q + vec2(w, w));
        float l = ltex(q + vec2(-w, 0.0)), r = ltex(q + vec2(w, 0.0));
        float bl = ltex(q + vec2(-w, -w)), b = ltex(q + vec2(0.0, -w)), br = ltex(q + vec2(w, -w));
        float gx = (tr + 2.0 * r + br) - (tl + 2.0 * l + bl);
        float gy = (tl + 2.0 * t + tr) - (bl + 2.0 * b + br);
        float g = smoothstep(uB.z, uB.z + uB.w + 1e-4, length(vec2(gx, gy)));
        float fl = 0.4 + 0.6 * hsh(ivec2(7, 11), sd);
        o = vec4(c.rgb + uD.rgb * uD.w * g * fl * uA.z, c.a);
    } else if (ty == 5) {                                                       // auto levels
        vec4 s0 = texelFetch(sTD2DInputs[1], ivec2(0, 0), 0);
        vec4 s1 = texelFetch(sTD2DInputs[1], ivec2(1, 0), 0);
        vec3 lo = s0.rgb, hi = s1.rgb;
        if (uG.w > 0.5) { lo = vec3(min(lo.r, min(lo.g, lo.b))); hi = vec3(max(hi.r, max(hi.g, hi.b))); }
        vec3 rg = hi - lo;
        lo += rg * uG.z; hi -= rg * uG.z;
        o = vec4((c.rgb - lo) / max(hi - lo, vec3(1e-4)), c.a);
    } else if (ty == 6) {                                                       // displace by gradient
        float sp = max(uA.w, 1.0);
        vec2 g = vec2(mapL(pc + vec2(sp, 0.0)) - mapL(pc - vec2(sp, 0.0)),
                      mapL(pc + vec2(0.0, sp)) - mapL(pc - vec2(0.0, sp))) * 0.5;
        vec2 off = g * uA.z * uB.y;
        vec4 sr = tex(pc - off * (1.0 - uF.w)), sg = tex(pc - off), sb = tex(pc - off * (1.0 + uF.w));
        o = vec4(sr.r, sg.g, sb.b, sg.a);
    } else if (ty == 8) {                                                       // arcs between points (TC-03)
        float W = max(uE.w, 0.25);
        float v = 0.0;
        int na = int(uH.y + 0.5);
        for (int k = 0; k < 32; k++) {
            if (k >= na) break;
            vec4 A = texelFetch(uArcs, 2 * k), B = texelFetch(uArcs, 2 * k + 1);
            if (B.x <= 0.0) continue;
            vec2 P0 = A.xy, P1 = A.zw, d = P1 - P0;
            float L = max(length(d), 1e-3);
            float t = clamp(dot(pc - P0, d) / (L * L), 0.0, 1.0);
            if (length(pc - P0 - d * t) > W * 14.0 + 0.5 * uG.x * L + 2.0) continue;    // exp(-14) cut + jag bound
            v += B.x * exp(-bolt(pc, P0, P1, sd + uint(B.y) * 7u + 1000u) / W);
        }
        float fl = 0.6 + 0.4 * hsh(ivec2(5, 9), sd);
        o = vec4(c.rgb + uD.rgb * uD.w * v * fl * uA.z, c.a);
    } else {                                                                    // zap
        vec2 A = uC.xy * SZ, B = uC.zw * SZ;
        float W = max(uE.w, 0.25);
        float v = exp(-bolt(pc, A, B, sd) / W);
        vec2 d = B - A; float L = length(d); vec2 u = d / max(L, 1e-3); vec2 nr = vec2(-u.y, u.x);
        int nb = int(uG.y + 0.5);
        for (int k = 0; k < 6; k++) {
            if (k >= nb) break;
            uint sk = sd + uint(k) * 7u + 1000u;
            float s0 = 0.15 + 0.6 * hsh(ivec2(k, 1), sk);
            float off0 = uG.x * L * (fbm1(s0 * 6.0, sd) - 0.5) * 4.0 * s0 * (1.0 - s0);
            vec2 P0 = A + u * s0 * L + nr * off0;
            float ang = (0.35 + 0.6 * hsh(ivec2(k, 2), sk)) * (hsh(ivec2(k, 3), sk) < 0.5 ? -1.0 : 1.0);
            vec2 bd = vec2(cos(ang) * u.x - sin(ang) * u.y, sin(ang) * u.x + cos(ang) * u.y);
            float bl = L * (0.15 + 0.3 * hsh(ivec2(k, 4), sk));
            v += 0.6 * exp(-bolt(pc, P0, P0 + bd * bl, sk) / (W * 0.7));
        }
        float fl = 0.6 + 0.4 * hsh(ivec2(5, 9), sd);
        o = vec4(c.rgb + uD.rgb * uD.w * v * fl * uA.z, c.a);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, o, uA.x));
}
"""

P = "parent().par.{}.eval()"
AUTOLEVEL = "parent().par.Type.eval() == 'autolevel'"


def uniforms():
    """fx uniforms [(name, [x, y, z, w exprs])] (tested offline against SHADER)."""
    return [
        ('uA', [P.format('Amount'), 'parent().par.Type.menuIndex', P.format('Strength'), P.format('Size')]),
        ('uB', [P.format('Angle'), P.format('Length'), P.format('Threshold'), P.format('Softness')]),
        ('uC', [P.format('Pointu'), P.format('Pointv'), P.format('Point2u'), P.format('Point2v')]),
        ('uD', [P.format('Colr'), P.format('Colg'), P.format('Colb'), P.format('Glow')]),
        ('uE', ['math.floor(absTime.seconds * %s)' % P.format('Rate'), P.format('Seed'), P.format('Decay'),
                P.format('Width')]),
        ('uF', [P.format('Detail'), P.format('Levels'), P.format('Edges'), P.format('Prism')]),
        ('uG', [P.format('Jag'), P.format('Branches'), P.format('Clip'), '1 if %s else 0' % P.format('Linked')]),
        ('uH', ["1 if parent().par.Type.eval() == 'displace' and parent().par.Maptop.eval() is not None else 0",
                "(op('arcs').numSamples // 2 if parent().par.Type.eval() == 'arcs' else 0)",
                'parent().par.Lattice.menuIndex', '0']),
    ]


def stats_uniforms():
    return [('uT', ['absTime.seconds', P.format('Smooth'), P.format('Level'), '1 if %s else 0' % AUTOLEVEL])]


def build(m, H):
    """Fill instance COMP m: in1 -> stats (2x1, autolevel only) ; map_src (Select) -> fx (compute) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    mn = mk(m, constantTOP, 'map_none')
    mn.par.outputresolution = 'custom'
    mn.par.resolutionw, mn.par.resolutionh = 1, 1
    mn.comment = '1x1: the map input while no Map TOP is used (Type displace + Maptop set).'
    ms = mk(m, selectTOP, 'map_src')
    expr(ms.par.top, "parent().par.Maptop.eval().path if parent().par.Type.eval() == 'displace' and "
                     "parent().par.Maptop.eval() is not None else me.parent().op('map_none').path")
    ms.comment = 'Map TOP (Displace page) only while Type = displace, else map_none: nothing else gets pulled.'
    st = H['compute'](m, 'stats', STATS, [in1], res=(2, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    expr(st.par.inputfiltertype, "'mipmap' if %s else 'linear'" % AUTOLEVEL)
    H['uniforms'](st, stats_uniforms())
    st.comment = 'autolevel stats (2x1 in place): lo rgb + time, hi rgb + mean, over mip Level; idle otherwise.'
    lg = mk(m, textDAT, 'arcs_logic')
    if lg.text != ARCS_PY:
        lg.text = ARCS_PY
    lg.comment = 'Arc list maths (points -> arcs), the module DAT the arcs Script CHOP imports.'
    pn = mk(m, constantCHOP, 'pts_none')
    pn.comment = 'Empty points (no Points CHOP set): the arcs CHOP uses Point / Point 2.'
    ps = mk(m, selectCHOP, 'pts_sel')
    expr(ps.par.chops, "parent().par.Pointchop.eval().path if parent().par.Type.eval() == 'arcs' and "
                       "parent().par.Pointchop.eval() is not None else me.parent().op('pts_none').path")
    ps.comment = 'Points CHOP (Points page) while Type = arcs, else the empty pts_none (nothing else pulled).'
    ac = mk(m, scriptCHOP, 'arcs')
    cb = m.op('arcs_callbacks') or mk(m, textDAT, 'arcs_callbacks')
    if cb.text != ARCS_CB:
        cb.text = ARCS_CB
    cb.dock = ac
    ac.par.callbacks = cb.name
    ac.inputConnectors[0].connect(ps)
    ac.comment = 'Arc list (2 samples per arc, channels a b c d) for the fx texture buffer uArcs.'
    g = H['compute'](m, 'fx', SHADER, [in1, st, ms])
    g.seq.array.numBlocks = max(int(g.seq.array.numBlocks), 1)
    g.par.array0name = 'uArcs'
    g.par.array0type = 'vec4'
    g.par.array0chop = 'arcs'
    g.par.array0arraytype = 'texturebuffer'
    g.par.inputextenduv = 'hold'
    H['uniforms'](g, uniforms())
    g.comment = ('misc: bend / suck / tri / longshadow / electrify / autolevel / displace / zap / arcs. Amount 0 = '
                 'passthrough.')
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'map_none', 'map_src', 'pts_none', 'pts_sel', 'arcs_logic',
                                                   'arcs', 'arcs_callbacks']},
        {'title': '2 Misc', 'role': 'process', 'ops': ['stats', 'stats_compute', 'fx', 'fx_compute'],
         'body': 'One compute pass per Type; stats only for autolevel (mip reduction).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
