# fx_glitch_timeshuffle - FX_glitch module 'timeshuffle' (FX1 DG-12 frame shuffle / per-block time offset).
# Template: docs/builds/fx_glitch.md "Module template"; doc + LIVE CHECKS: docs/builds/fx_glitch_timeshuffle.md.
# Same native ring as timedisplace (FX6 4b, builders/fx_time_ring.py): the only GLSL is the map pass, which gives
# every block (squares, full-width rows or full-height columns) a whole-frame time offset:
#   random  - random delay 0..Length-1 per block, new draw Rate times a second (the temporal macroblock look)
#   permute - plays the previous Length frames in a shuffled order, new permutation every chunk
#   reverse - plays each Length-frame chunk backwards (needs Depth >= 2*Length-1)
#   hold    - freezes each chunk's first frame for Length frames (stutter)
#   luma    - bright blocks lag (Invert: dark blocks lag)
#   wave    - delay from the block's place along Angle (stepped slit-scan, Repeat / Phase scroll)
# Perblock staggers the chunk phase per block; Chance x Amount = share of blocks affected; Gridshift jumps the block
# grid per Rate tick. Offsets are whole cooks (map rgba32float, error ~1e-6 slice), clamped to what the ring holds.
#   cadence - TC-31 frame-cadence editor: a Pattern of steps (p play, h hold, r repeat the previous step, v reverse,
#             b fill colour frame, w white frame; each with a length in cooks, e.g. `p4 h4 r4 b1 p3`) loops over the
#             cooks since the ring restarted; blocks + Perblock stagger it, Chance picks the blocks (whole frame with
#             Blocksize 512 / full-frame rows). Fill frames go through the `cad` pass (map alpha = keep).
# Amount 0 = exact passthrough. Pure maths: fx_time_logic.ts_offsets / cadence_offset. ASCII only.
import os

MODULE = 'timeshuffle'
_RING = os.path.join(globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders',
                     'fx_time_ring.py')
exec(open(_RING).read())                            # GLSL_HASH, STAMP_RING, RING_PAR, build_ring, map_size_exprs

MODES = ['random', 'permute', 'reverse', 'hold', 'luma', 'wave', 'cadence']
SHAPES = ['squares', 'rows', 'columns']

PAGES = [
    ('Shuffle', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (x Chance)'}),
        ('Depth', 'Int', 32, {'min': 2, 'max': 120, 'label': 'Depth (ring cooks)'}),
        RING_PAR,
        ('Mode', 'Menu', 'random', {'names': MODES, 'labels': ['Random delay', 'Permute chunk', 'Reverse chunk',
                                                               'Hold (stutter)', 'Luma lag', 'Wave (stepped)',
                                                               'Cadence (pattern)']}),
        ('Length', 'Int', 16, {'min': 1, 'max': 60, 'label': 'Length (frames)'}),
        ('Blocksize', 'Float', 64.0, {'min': 4, 'max': 512, 'label': 'Block size px'}),
        ('Shape', 'Menu', 'squares', {'names': SHAPES, 'labels': ['Squares', 'Rows (strips)', 'Columns']}),
        ('Chance', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Chance (share of blocks)'}),
        ('Rate', 'Float', 4.0, {'min': 0, 'max': 30, 'label': 'Rate Hz (random/luma/wave/grid)'}),
        ('Perblock', 'Toggle', False, {'label': 'Per-block chunk phase'}),
        ('Gridshift', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Grid shift per tick'}),
    ]),
    ('Wave', [
        ('Angle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Wave angle (0 = up)'}),
        ('Repeat', 'Float', 1.0, {'min': 0.25, 'max': 8, 'label': 'Wave repeat'}),
        ('Phase', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Wave scroll (cycles/s)'}),
        ('Invert', 'Toggle', False, {'label': 'Invert (luma / wave)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
BANK = [('stutter', 'p6 h6 r6 v6'), ('strobe', 'p3 b1 p2 w1 h4 b1'), ('rhythm', 'p4 h8 r4 v4'),
        ('reel', 'p8 r8 r8 b2'), ('blink', 'p5 b1'), ('rewind', 'p12 v12')]
PAGES.append(('Cadence', [                       # Mode cadence (TC-31)
    ('Cadence', 'Menu', 'custom', {'names': ['custom'] + [n for n, _p in BANK],
                                   'labels': ['Custom (Pattern)'] + ['%s: %s' % (n, p_) for n, p_ in BANK]}),
    ('Pattern', 'Str', 'p4 h4 r4 b1 p3', {'label': 'Pattern (p h r v b w + cooks)'}),
    ('Fillr', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Fill R (b frames)'}),
    ('Fillg', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Fill G'}),
    ('Fillb', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Fill B'}),
]))
PANEL_PAGES = ['Shuffle', 'Wave', 'Cadence']

_Z = {'Chance': 1.0, 'Perblock': 0, 'Gridshift': 0.0, 'Angle': 0.0, 'Repeat': 1.0, 'Phase': 0.0, 'Invert': 0,
      'Quality': 0, 'Rate': 4.0, 'Cadence': 0, 'Fillr': 0.0, 'Fillg': 0.0, 'Fillb': 0.0}
PRESETS = [
    (1, 'temporal blocks', dict(_Z, Amount=1.0, Depth=32, Mode=0, Length=16, Blocksize=64.0, Shape=0, Chance=0.6,
                                Rate=4.0, Seed=1)),
    (2, 'stutter strips', dict(_Z, Amount=1.0, Depth=32, Mode=3, Length=8, Blocksize=24.0, Shape=1, Perblock=1,
                               Seed=2)),
    (3, 'rewind', dict(_Z, Amount=1.0, Depth=32, Mode=2, Length=12, Blocksize=512.0, Shape=0, Seed=3)),
    (4, 'shuffle deck', dict(_Z, Amount=1.0, Depth=32, Mode=1, Length=8, Blocksize=128.0, Shape=0, Perblock=1,
                             Gridshift=0.5, Rate=2.0, Seed=4)),
    (5, 'time stairs', dict(_Z, Amount=1.0, Depth=32, Mode=5, Length=30, Blocksize=48.0, Shape=1, Phase=0.2,
                            Seed=5)),
    (6, 'stutter cut', dict(_Z, Amount=1.0, Depth=24, Mode=6, Cadence=1, Length=4, Blocksize=512.0, Shape=0,
                            Seed=6)),
    (7, 'strobe edit', dict(_Z, Amount=1.0, Depth=16, Mode=6, Cadence=2, Length=2, Blocksize=512.0, Shape=0,
                            Seed=7)),
    (8, 'rhythm strips', dict(_Z, Amount=1.0, Depth=24, Mode=6, Cadence=3, Length=6, Blocksize=96.0, Shape=1,
                              Perblock=1, Chance=0.7, Seed=8)),
]
# Pattern is a Str par (the zkit stores numbers only): presets pick a BANK pattern through the Cadence menu.

CADENCE_PY = '''# timeshuffle cadence: Pattern text -> step codes / lengths (Mode cadence, TC-31). Pure Python; the map's uniforms.
CODES = 'phrvbw'


def parse(text, default_len):
    steps = []
    for tok in str(text or '').replace(',', ' ').split():
        ch = tok[0].lower()
        if ch not in CODES:
            continue
        num = tok[1:]
        n = int(num) if num.isdigit() else int(default_len)
        steps.append((CODES.index(ch), max(1, n)))
    return steps[:16] or [(0, 1)]


BANK = %r


def pattern(m):
    i = m.par.Cadence.menuIndex
    return BANK[i - 1][1] if 1 <= i <= len(BANK) else m.par.Pattern.eval()


def U(m):
    st = parse(pattern(m), max(1, int(m.par.Length.eval())))
    codes = [float(c) for c, _n in st] + [0.0] * (16 - len(st))
    lens = [float(n) for _c, n in st] + [0.0] * (16 - len(st))
    return codes + lens + [float(sum(n for _c, n in st)), float(len(st))]
'''

MAP = """// FX_glitch timeshuffle: per-block time offsets (compute, T-47; DG-12). in0 picture, in1 = in0 (unused),
// in2 stamp (z = cooks since the ring restarted = n). Writes grey m = 1 - k/(Depth-1) per block, k whole cooks,
// clamped to [0, min(Depth-1, n)]. = fx_time_logic.ts_offsets / ts_block_offset.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount depthm1 mode length
uniform vec4 uB;   // blocksize shape chance rate
uniform vec4 uC;   // perblock gridshift time seed
uniform vec4 uD;   // angle repeat phase invert
uniform vec4 uE;   // mapw maph
// cadence: uP0..3 = step codes (16), uL0..3 = step lengths in cooks (16)
uniform vec4 uP0;
uniform vec4 uP1;
uniform vec4 uP2;
uniform vec4 uP3;
uniform vec4 uL0;
uniform vec4 uL1;
uniform vec4 uL2;
uniform vec4 uL3;
uniform vec4 uQ;   // cadence total cooks, steps
""" + GLSL_HASH + """uint perm(uint i, uint L, uint key) {             // bijection on [0, L): cycle-walk on 2^k (= perm)
    uint P = 1u;
    for (int b = 0; b < 31 && P < L; b++) P <<= 1u;
    uint M = P - 1u;
    uint r = uint(max(1, findMSB(P) / 2));
    uint x = i;
    for (int it = 0; it < 512; it++) {
        x = (x * 5u + (key & M)) & M;
        x ^= x >> r;
        x = (x * 9u + ((key >> 8u) & M)) & M;
        x ^= x >> 1u;
        if (x < L) break;
    }
    return x;
}
float stepv(int j, bool len) {
    vec4 a = len ? (j < 4 ? uL0 : (j < 8 ? uL1 : (j < 12 ? uL2 : uL3)))
                 : (j < 4 ? uP0 : (j < 8 ? uP1 : (j < 12 ? uP2 : uP3)));
    int q = j - (j / 4) * 4;
    return q == 0 ? a.x : (q == 1 ? a.y : (q == 2 ? a.z : a.w));
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    vec2 sz = uE.xy;
    if (p.x >= int(sz.x) || p.y >= int(sz.y)) return;
    float T = uC.z;
    uint seed = uint(uC.w) * 7919u;
    int mode = int(uA.z + 0.5);
    float L = max(1.0, floor(uA.w));
    float D = max(uA.y, 1.0);
    float bs = max(1.0, floor(uB.x));
    int shp = int(uB.y + 0.5);
    vec2 cell = vec2(shp == 1 ? sz.x : bs, shp == 2 ? sz.y : bs);
    uint ep = uint(floor(T * uB.w));
    vec2 g = floor(vec2(h(uvec4(ep, seed, 1u, 9u)), h(uvec4(ep, seed, 2u, 9u))) * uC.y * bs);
    ivec2 b = ivec2(floor((vec2(p) + g) / cell));
    uvec2 ub = uvec2(b);
    float n = texelFetch(sTD2DInputs[2], ivec2(0), 0).z;
    float k = 0.0;
    float keep = 1.0;
    uint ce = ep;
    if (mode == 6) {                                    // cadence: pattern steps over the cook count
        float T = max(uQ.x, 1.0);
        float c = n + (uC.x > 0.5 ? floor(h(uvec4(ub, seed, 11u)) * T) : 0.0);
        float cyc = floor(c / T);
        c -= cyc * T;
        ce = uint(cyc);
        float st = 0.0, prevl = 0.0;
        int ns = int(uQ.y + 0.5);
        for (int j = 0; j < 16; j++) {
            if (j >= ns) break;
            float l = stepv(j, true);
            if (c < st + l) {
                float i = c - st;
                int code = int(stepv(j, false) + 0.5);
                if (code == 1) k = i;
                else if (code == 2) k = prevl;
                else if (code == 3) k = 2.0 * i;
                else if (code == 4) keep = 0.0;
                else if (code == 5) keep = 0.5;
                break;
            }
            st += l; prevl = l;
        }
    } else if (mode == 0) {
        k = floor(h(uvec4(ub, ep, seed)) * L);
    } else if (mode <= 3) {
        float c = n + (uC.x > 0.5 ? floor(h(uvec4(ub, seed, 11u)) * L) : 0.0);
        float chunk = floor(c / L);
        float i = c - chunk * L;
        ce = uint(chunk);
        if (mode == 1) {
            uint blk = uC.x > 0.5 ? pcg(ub.x ^ pcg(ub.y)) : 0u;
            uint key = pcg(uint(chunk) ^ pcg(seed ^ blk));
            k = i + L - float(perm(uint(i), uint(L), key));
        } else if (mode == 2) k = 2.0 * i;
        else k = i;
    } else {
        vec2 bc = (vec2(b) + 0.5) * cell - g;
        float s;
        if (mode == 4) s = lum(texelFetch(sTD2DInputs[0], ivec2(clamp(floor(bc), vec2(0.0), sz - 1.0)), 0).rgb);
        else {
            float a = radians(uD.x); vec2 d = vec2(sin(a), cos(a));
            s = dot(bc / sz - 0.5, d) / (abs(d.x) + abs(d.y)) + 0.5;
            float w = s * uD.y + uD.z * T;
            s = 1.0 - abs(fract(w * 0.5) * 2.0 - 1.0);
        }
        if (uD.w > 0.5) s = 1.0 - s;
        k = floor(s * (L - 1.0) + 0.5);
    }
    if (h(uvec4(ub, ce, seed + 5u)) >= uB.z * uA.x) { k = 0.0; keep = 1.0; }
    float off = clamp(k, 0.0, min(D, n));
    float m = 1.0 - (off + 1.0) / (D + 1.0);           // 31550 Time Machine reads (1-m)*Depth - 1 slices (T-122)
    TDImageStoreOutput(0, ivec3(p, 0), vec4(m, m, m, keep));   // alpha: 1 keep, 0 fill colour, 0.5 white (cad)
}
"""

P = "parent().par.{}.eval()"
CAD = "op('cadence').module.U(parent())[%d]"

CAD_FX = """// timeshuffle cadence fill (compute): in0 = tmachine, in1 = map (alpha 1 keep, 0 fill colour, 0.5 white).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uF;   // fill rgb
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    ivec2 ms = textureSize(sTD2DInputs[1], 0);
    float a = texelFetch(sTD2DInputs[1], min(p * ms / isz, ms - 1), 0).a;
    vec4 o = a > 0.75 ? c : (a > 0.25 ? vec4(1.0, 1.0, 1.0, c.a) : vec4(uF.rgb, c.a));
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
"""


def uniforms():
    """[(uniform, [x, y, z, w expressions])] of the map pass (names = the MAP declarations; tested offline)."""
    mw, mh = map_size_exprs('1.0')
    tog = '1 if parent().par.{}.eval() else 0'
    return [
        ('uA', [P.format('Amount'), '%s - 1' % DEPTH, 'parent().par.Mode.menuIndex', P.format('Length')]),
        ('uB', [P.format('Blocksize'), 'parent().par.Shape.menuIndex', P.format('Chance'), P.format('Rate')]),
        ('uC', [tog.format('Perblock'), P.format('Gridshift'), 'absTime.seconds', P.format('Seed')]),
        ('uD', [P.format('Angle'), P.format('Repeat'), P.format('Phase'), tog.format('Invert')]),
        ('uE', [mw, mh, '0', '0']),
    ] + [('uP%d' % j, [CAD % (4 * j + q) for q in range(4)]) for j in range(4)] + \
        [('uL%d' % j, [CAD % (16 + 4 * j + q) for q in range(4)]) for j in range(4)] + \
        [('uQ', [CAD % 32, CAD % 33, '0', '0'])]


def build(m, H):
    """in1 -> ring / stamp / map (per-block offsets) -> tmachine -> out_sw -> out1 (fx_time_ring)."""
    cd = H['mk'](m, textDAT, 'cadence')
    txt = CADENCE_PY % (BANK,)
    if cd.text != txt:
        cd.text = txt
    cd.comment = 'Cadence pattern parser (Mode cadence): step codes / lengths for the map uniforms.'
    stages = build_ring(m, H, MAP, uniforms(), map_scale='1.0', title='2 Block time')
    m.op('map').comment = 'timeshuffle map: whole-cook offset per block (random/permute/reverse/hold/luma/wave/cadence).'
    cf = H['compute'](m, 'cad', CAD_FX, [m.op('tmachine'), m.op('map')])
    H['uniforms'](cf, [('uF', [P.format('Fillr'), P.format('Fillg'), P.format('Fillb'), '0'])])
    cf.comment = 'Cadence fill: b / w steps replace the frame (fill colour / white); other modes skip this pass.'
    sw = m.op('out_sw')
    sw.inputConnectors[2].connect(cf)
    H['expr'](sw.par.index, "0 if parent().par.Amount.eval() <= 0 else (2 if parent().par.Mode.eval() == 'cadence' "
                            "else 1)")
    for s_ in stages:
        if s_['title'] == '2 Block time':
            s_['ops'] = ['cadence'] + s_['ops'] + ['cad', 'cad_compute']
    return stages
