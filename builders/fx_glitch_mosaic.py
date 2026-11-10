# fx_glitch_mosaic - FX_glitch module 'mosaic' (FX1 DG-20 mosaic decay / quadtree pixelation by detail).
# Template: docs/builds/fx_glitch.md "Module template". Two compute passes: `stats` writes (rgb, luma^2) in rgba16float;
# `fx` samples its mip chain (inputfiltertype mipmap, textureLod) for each candidate cell, from Maxblock down to
# Minblock, and stops at the first cell whose luma std dev <= Detail: flat areas become big blocks, detail stays
# sharp (a quadtree, since a parent that is flat stops for all its pixels). Decay: per-cell noise on the threshold
# (Decay, Decayrate), Grow = threshold rises with the age since the last Rebuild (edge > 0.5, or Autorebuild s), Fall =
# a share of the Maxblock cells drops away under Gravity (gather per column; holes black / source / transparent).
# Shape hex / tri / square (7C-33 cell mosaic with beat flips): a lattice instead of the quadtree; each cell is filled
# flat (centre pixel or mip mean) or shows its own piece of the picture, with Gap lines; on every Rebuild edge /
# Autorebuild tick a Flip share of the cells (hash per cell and beat) flips (y / x through 0, shrink or spin) over
# Fliptime s, the back side mirrored and hue-turned by Recolour. Mirror: builders/fx_glitch_mosaic_logic.py.
# Amount 0 = exact passthrough. ASCII only.

MODULE = 'mosaic'
SHAPES = ['quad', 'hex', 'tri', 'square']
CELLFILLS = ['centre', 'mean', 'image']
FLIPMODES = ['flipy', 'flipx', 'shrink', 'spin']

PAGES = [
    ('Mosaic', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Shape', 'Menu', 'quad', {'names': SHAPES, 'labels': ['Quadtree (detail)', 'Hexagons', 'Triangles',
                                                                'Squares']}),
        ('Maxblock', 'Int', 64, {'min': 2, 'max': 256, 'label': 'Max block px'}),
        ('Minblock', 'Int', 4, {'min': 1, 'max': 64, 'label': 'Min block px (1 = keep pixels)'}),
        ('Detail', 'Float', 0.06, {'min': 0, 'max': 0.5, 'label': 'Detail (luma std dev kept)'}),
        ('Fill', 'Menu', 'mean', {'names': ['mean', 'centre'], 'labels': ['Cell mean', 'Centre pixel']}),
        ('Edges', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Cell edge darken'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Decay', [
        ('Decay', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Per-cell threshold noise'}),
        ('Decayrate', 'Float', 2.0, {'min': 0, 'max': 30, 'label': 'Noise rate Hz'}),
        ('Grow', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Grow (threshold per s since rebuild)'}),
        ('Rebuild', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Rebuild (edge > 0.5)'}),
        ('Autorebuild', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Auto rebuild every s (0 = off)'}),
        ('Fall', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Falling cell share'}),
        ('Gravity', 'Float', 500.0, {'min': 0, 'max': 4000, 'label': 'Gravity px/s2'}),
        ('Hole', 'Menu', 'black', {'names': ['black', 'source', 'transparent'],
                                   'labels': ['Black', 'Source picture', 'Transparent']}),
    ]),
    ('Cells', [                                   # Shape hex / tri / square (7C-33); Rebuild / Autorebuild = the beat
        ('Cellsize', 'Float', 48.0, {'min': 4, 'max': 400, 'label': 'Cell size px'}),
        ('Cellfill', 'Menu', 'centre', {'names': CELLFILLS, 'labels': ['Centre pixel', 'Cell mean (mip)',
                                                                       'Picture in the cell']}),
        ('Gap', 'Float', 2.0, {'min': 0, 'max': 40, 'label': 'Gap px'}),
        ('Gapr', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Gap R'}),
        ('Gapg', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Gap G'}),
        ('Gapb', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Gap B'}),
        ('Flip', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Flip share per beat'}),
        ('Flipmode', 'Menu', 'flipy', {'names': FLIPMODES, 'labels': ['Flip Y', 'Flip X', 'Shrink', 'Spin']}),
        ('Fliptime', 'Float', 0.4, {'min': 0.02, 'max': 4, 'label': 'Flip time s'}),
        ('Recolour', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Back side hue turn'}),
    ]),
]
PANEL_PAGES = ['Mosaic', 'Decay', 'Cells']

# Full state (T-124 (1)): page defaults + the look.
_D = dict((n, o['names'].index(d) if s_ == 'Menu' else d) for _pg, pl in PAGES for n, s_, d, o in pl)
PRESETS = [
    (1, 'quadtree', dict(_D, Amount=1.0, Maxblock=64, Minblock=4, Detail=0.05, Seed=1)),
    (2, 'decay loop', dict(_D, Amount=1.0, Maxblock=128, Minblock=2, Detail=0.02, Grow=0.03, Autorebuild=6.0,
                           Decay=0.5, Decayrate=3.0, Seed=2)),
    (3, 'crumble', dict(_D, Amount=1.0, Maxblock=64, Minblock=4, Detail=0.04, Grow=0.02, Fall=0.3, Gravity=700.0,
                        Autorebuild=4.0, Hole=0, Seed=3)),
    (4, 'big pixels', dict(_D, Amount=1.0, Maxblock=128, Minblock=16, Detail=0.12, Fill=1, Edges=0.5, Seed=4)),
    (5, 'shimmer', dict(_D, Amount=1.0, Maxblock=64, Minblock=2, Detail=0.035, Decay=1.0, Decayrate=8.0, Seed=5)),
    (6, 'hex flips', dict(_D, Amount=1.0, Shape=1, Cellsize=56.0, Cellfill=1, Gap=3.0, Flip=0.35, Flipmode=0,
                          Fliptime=0.35, Recolour=0.3, Autorebuild=0.5, Seed=6)),
    (7, 'tri shards', dict(_D, Amount=1.0, Shape=2, Cellsize=90.0, Cellfill=2, Gap=2.0, Flip=0.25, Flipmode=3,
                           Fliptime=0.5, Edges=0.4, Autorebuild=0.5, Seed=7)),
    (8, 'grid flip', dict(_D, Amount=1.0, Shape=3, Cellsize=120.0, Cellfill=2, Gap=4.0, Gapr=0.05, Gapg=0.05,
                          Gapb=0.05, Flip=0.5, Flipmode=1, Fliptime=0.3, Recolour=-0.5, Autorebuild=0.5, Seed=8)),
]

STATS = """// mosaic stats: rgb + luma^2 (rgba16float) for the fx pass's mip chain (cell mean + variance). Output padded to
// a multiple of 128 px (edge held) so every mip texel up to level 7 covers exactly one grid cell.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS;   // output w h
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= int(uS.x) || p.y >= int(uS.y)) return;
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    vec3 c = texelFetch(sTD2DInputs[0], min(p, isz - 1), 0).rgb;
    float Y = dot(c, vec3(0.2126, 0.7152, 0.0722));
    TDImageStoreOutput(0, ivec3(p, 0), vec4(c, Y * Y));
}
"""

SHADER = """// FX_glitch mosaic (compute, T-47). in0 picture (texelFetch only), in1 stats (mipmapped: textureLod), in2 stamp.
// stamp (1x1): x now, y previous cook, z last rebuild time, w = 2 * rebuild count + last edge bit.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount maxblock minblock detail
uniform vec4 uB;   // fill edges seed time
uniform vec4 uC;   // decay decayrate grow fall
uniform vec4 uD;   // gravity hole
uniform vec4 uE;   // shape cellsize gap cellfill
uniform vec4 uF;   // flip fliptime flipmode recolour
uniform vec4 uG;   // gap r g b, edges
uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h(uvec4 k) { return float(pcg(k.x ^ pcg(k.y ^ pcg(k.z ^ pcg(k.w)))) >> 8) / 16777215.0; }
// ---- cells (7C-33): lattice in cell units, frame-centred. = fx_glitch_mosaic_logic.lattice
void lattice(vec2 q, int shp, out vec2 cen, out float edge, out ivec2 id) {
    if (shp == 1) {                                                             // hex (two offset grids)
        vec2 r = vec2(1.0, 1.7320508), hh = 0.5 * r;
        vec2 a = mod(q, r) - hh, b = mod(q - hh, r) - hh;
        vec2 gv = dot(a, a) < dot(b, b) ? a : b;
        cen = q - gv;
        vec2 g = abs(gv);
        edge = 0.5 - max(dot(g, vec2(0.5, 0.8660254)), g.x);
        id = ivec2(floor(cen.x * 2.0 + 0.5), floor(cen.y / 0.8660254 + 0.5));
    } else if (shp == 2) {                                                      // triangles
        float h = 0.8660254;
        float bq = q.y / h;                                                     // lattice basis (1, 0), (0.5, h)
        float j = floor(bq), fy = bq - j;
        float xs = q.x - 0.5 * bq, i = floor(xs), fx = xs - i;
        bool up = fx + fy >= 1.0;
        vec2 V0 = up ? vec2(i + 1.0 + 0.5 * j, j * h) : vec2(i + 0.5 * j, j * h);
        vec2 V1 = up ? vec2(i + 1.0 + 0.5 * (j + 1.0), (j + 1.0) * h) : vec2(i + 1.0 + 0.5 * j, j * h);
        vec2 V2 = vec2(i + 0.5 * (j + 1.0), (j + 1.0) * h);
        cen = (V0 + V1 + V2) / 3.0;
        float e0 = up ? 1.0 - fy : fy;                                          // distances to the 3 sides / h
        float e1 = up ? fx + fy - 1.0 : 1.0 - fx - fy;
        float e2 = up ? 1.0 - fx : fx;
        edge = min(e0, min(e1, e2)) * h;
        id = ivec2(int(i) * 2 + (up ? 1 : 0), int(j));
    } else {                                                                    // squares
        vec2 f = floor(q);
        cen = f + 0.5;
        vec2 g = abs(q - cen);
        edge = 0.5 - max(g.x, g.y);
        id = ivec2(f);
    }
}
vec3 hueTurn(vec3 c, float t) {                                                 // YIQ rotation, t turns
    float y = dot(c, vec3(0.299, 0.587, 0.114));
    float i = dot(c, vec3(0.596, -0.274, -0.322)), qq = dot(c, vec3(0.211, -0.523, 0.312));
    float a = 6.2831853 * t, cs = cos(a), sn = sin(a);
    float i2 = i * cs - qq * sn, q2 = i * sn + qq * cs;
    return vec3(y + 0.956 * i2 + 0.621 * q2, y - 0.272 * i2 - 0.647 * q2, y - 1.106 * i2 + 1.703 * q2);
}
vec4 cells(ivec2 p, ivec2 isz, vec4 c, vec4 st) {
    vec2 SZ = vec2(isz);
    float S = max(uE.y, 1.0);
    int shp = int(uE.x + 0.5);
    vec2 q = (vec2(p) + 0.5 - 0.5 * SZ) / S;
    vec2 cen; float edge; ivec2 id;
    lattice(q, shp, cen, edge, id);
    vec4 gapc = vec4(uG.rgb, c.a);
    if (edge * S < 0.5 * uE.z) return gapc;
    uint cnt = uint(floor(st.w * 0.5));
    float age = max(st.x - st.z, 0.0);
    float ph = clamp(age / max(uF.y, 1e-3), 0.0, 1.0);
    bool flp = ph < 1.0 && h(uvec4(uvec2(id), cnt, uint(uB.z) * 7919u + 3u)) < uF.x;
    vec2 gv = q - cen;
    bool back = false;
    if (flp) {
        int fm = int(uF.z + 0.5);
        float k = cos(3.14159265 * ph);
        back = k < 0.0;
        if (fm == 0) gv.y = gv.y / max(abs(k), 1e-3) * (back ? -1.0 : 1.0);
        else if (fm == 1) gv.x = gv.x / max(abs(k), 1e-3) * (back ? -1.0 : 1.0);
        else if (fm == 2) gv = gv / max(1.0 - sin(3.14159265 * ph), 1e-3);
        else { float a = 3.14159265 * ph; gv = vec2(cos(a) * gv.x + sin(a) * gv.y, -sin(a) * gv.x + cos(a) * gv.y); }
        vec2 c2; float e2; ivec2 id2;
        lattice(cen + gv, shp, c2, e2, id2);
        if (id2 != id || e2 * S < 0.5 * uE.z) return gapc;
    }
    int fill = int(uE.w + 0.5);
    vec3 col;
    if (fill == 2) col = texelFetch(sTD2DInputs[0], clamp(ivec2(floor((cen + gv) * S + 0.5 * SZ)), ivec2(0), isz - 1), 0).rgb;
    else if (fill == 1) col = textureLod(sTD2DInputs[1], (cen * S + 0.5 * SZ) / vec2(textureSize(sTD2DInputs[1], 0)),
                                         log2(S)).rgb;
    else col = texelFetch(sTD2DInputs[0], clamp(ivec2(floor(cen * S + 0.5 * SZ)), ivec2(0), isz - 1), 0).rgb;
    if (back) col = hueTurn(col, uF.w);
    col *= 1.0 - uG.w * (1.0 - smoothstep(0.0, 3.0, edge * S - 0.5 * uE.z));
    return vec4(col, c.a);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }       // exact passthrough
    vec4 st = texelFetch(sTD2DInputs[2], ivec2(0), 0);
    if (uE.x > 0.5) { TDImageStoreOutput(0, ivec3(p, 0), mix(c, cells(p, isz, c, st), uA.x)); return; }
    float age = max(st.x - st.z, 0.0);
    uint cnt = uint(floor(st.w * 0.5));
    uint seed = uint(uB.z) * 7919u + cnt * 104729u;
    vec2 sz = vec2(textureSize(sTD2DInputs[1], 0));                            // padded stats size
    int S = max(int(uA.y + 0.5), 1);
    int Smin = clamp(int(uA.z + 0.5), 1, S);
    ivec2 q = p;
    bool hole = false;
    if (uC.w > 0.0) {                                                           // falling Maxblock cells (gather)
        int colx = p.x / S;
        float d = 0.5 * uD.x * age * age * (0.5 + h(uvec4(uint(colx), seed, 41u, 0u)));
        ivec2 qs = p + ivec2(0, int(d));                                        // TD y is up: content falls to y 0
        bool srcFalls = qs.y < isz.y && h(uvec4(uvec2(qs / S), seed, 43u)) < uC.w;
        bool ownFalls = h(uvec4(uvec2(p / S), seed, 43u)) < uC.w;
        if (d >= 1.0) { if (srcFalls) q = qs; else if (ownFalls) hole = true; }
    }
    vec4 res;
    if (hole) {
        int hm = int(uD.y + 0.5);
        res = hm == 0 ? vec4(0.0, 0.0, 0.0, c.a) : (hm == 1 ? c : vec4(0.0));
    } else {
        uint tE = uint(floor(uB.w * uC.y));
        float thr0 = uA.w + uC.z * age;
        int s = S;
        vec3 col = texelFetch(sTD2DInputs[0], q, 0).rgb;
        ivec2 o = q;
        for (int k = 0; k < 10; k++) {                                          // Maxblock -> Minblock, halving
            o = (q / s) * s;
            if (s <= 1) { col = texelFetch(sTD2DInputs[0], q, 0).rgb; break; }
            float n = h(uvec4(uvec2(o), uint(s) + seed, tE));
            float thr = thr0 * (1.0 + 2.0 * uC.x * n);
            vec2 uv = (vec2(o) + 0.5 * float(s)) / sz;
            vec4 m = textureLod(sTD2DInputs[1], uv, log2(float(s)));
            float Y = dot(m.rgb, vec3(0.2126, 0.7152, 0.0722));
            float sd = sqrt(max(m.a - Y * Y, 0.0));
            if (sd <= thr || s / 2 < Smin) {
                col = uB.x > 0.5 ? texelFetch(sTD2DInputs[0], clamp(o + s / 2, ivec2(0), isz - 1), 0).rgb : m.rgb;
                if (s >= 4 && (q.x == o.x || q.y == o.y)) col *= 1.0 - uB.y;
                break;
            }
            s /= 2;
        }
        res = vec4(col, texelFetch(sTD2DInputs[0], q, 0).a);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, res, uA.x));
}
"""

STAMP = """// stamp: 1x1 rgba32float in place. x now, y previous cook, z last rebuild, w = 2 * rebuild count + edge bit.
// Rebuild on: first cook, a gap > 1 s (re-enabled after bypass; 1 s, not 0.25, so frame hitches don't reset the
// decay), the Rebuild edge, or Autorebuild elapsed.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;   // now, rebuild value, autorebuild s
void main() {
    vec4 s = TDImageLoadOutput(0, ivec3(0));
    float cnt = floor(s.w * 0.5);
    float pb = s.w - cnt * 2.0;
    float b = uT.y > 0.5 ? 1.0 : 0.0;
    float bt = s.z;
    bool go = (s.x <= 0.0) || (uT.x - s.x > 1.0) || (b > 0.5 && pb < 0.5) || (uT.z > 0.0 && uT.x - bt >= uT.z);
    if (go) { bt = uT.x; cnt += 1.0; }
    TDImageStoreOutput(0, ivec3(0), vec4(uT.x, s.x, bt, cnt * 2.0 + b));
}
"""

P = "parent().par.{}.eval()"


def uniforms():
    """fx uniforms [(name, [x, y, z, w exprs])] (tested offline against SHADER)."""
    return [('uA', [P.format('Amount'), P.format('Maxblock'), P.format('Minblock'), P.format('Detail')]),
            ('uB', ['parent().par.Fill.menuIndex', P.format('Edges'), P.format('Seed'), 'absTime.seconds']),
            ('uC', [P.format('Decay'), P.format('Decayrate'), P.format('Grow'), P.format('Fall')]),
            ('uD', [P.format('Gravity'), 'parent().par.Hole.menuIndex', '0', '0']),
            ('uE', ['parent().par.Shape.menuIndex', P.format('Cellsize'), P.format('Gap'),
                    'parent().par.Cellfill.menuIndex']),
            ('uF', [P.format('Flip'), P.format('Fliptime'), 'parent().par.Flipmode.menuIndex', P.format('Recolour')]),
            ('uG', [P.format('Gapr'), P.format('Gapg'), P.format('Gapb'), P.format('Edges')])]


def build(m, H):
    """Fill instance COMP m: in1 -> stats (rgb + luma^2) / stamp -> fx (mipmapped stats) -> out1."""
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    sg = H['compute'](m, 'stats', STATS, [in1], fmt='rgba16float')
    H['expr'](sg.par.resolutionw, 'int(math.ceil(me.inputs[0].width / 128.0)) * 128')
    H['expr'](sg.par.resolutionh, 'int(math.ceil(me.inputs[0].height / 128.0)) * 128')
    H['uniforms'](sg, [('uS', ['me.par.resolutionw.eval()', 'me.par.resolutionh.eval()', '0', '0'])])
    sg.comment = 'rgb + luma^2 for the fx pass mip chain (cell mean + variance).'
    st = H['compute'](m, 'stamp', STAMP, [], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    H['uniforms'](st, [('uT', ['absTime.seconds', P.format('Rebuild'), P.format('Autorebuild'), '0'])])
    st.comment = 'Cook clock + rebuild: x now, y prev cook, z last rebuild (first cook / re-enable / edge / auto), w count.'
    g = H['compute'](m, 'fx', SHADER, [in1, sg, st])
    g.par.inputfiltertype = 'mipmap'                  # textureLod on stats; in0 is read with texelFetch (exact)
    H['uniforms'](g, uniforms())
    g.comment = ('mosaic: quadtree pixelation by detail + decay/fall (DG-20); hex / tri / square cells with beat '
                 'flips (7C-33). Amount 0 = exact passthrough.')
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Mosaic', 'role': 'process', 'ops': ['stats', 'stats_compute', 'stamp', 'stamp_compute', 'fx',
                                                         'fx_compute'],
         'body': 'stats (rgb, luma^2) -> mip chain -> fx picks the biggest flat cell per pixel.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
