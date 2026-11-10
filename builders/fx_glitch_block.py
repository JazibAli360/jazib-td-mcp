# fx_glitch_block - FX_glitch module 'block' (FX1 DG-07 block glitch / macroblock corruption + tile scramble).
# Template: docs/builds/fx_glitch.md "Module template". One compute pass: a grid of Blocksize cells (2-level quadtree
# split by Irregular), each cell re-rolled Rate times a second (or on a Beat): hit by Chance, then one of five
# modes by weight: smear (one column/row stretched over the cell), repeat (a Tile px sub-block tiled), offset (the cell
# shows another place, optionally snapped to the grid = tile scramble), colour (channel swap + Cb/Cr DC drift, the
# green/magenta macroblocks) and freeze (previous output). Slice = a hit row runs to the end of the line (slice loss).
# Beat (edge > 0.5, or the Bpm metronome) bursts Burstchance on top of Chance, decaying over Burstdecay s, and
# re-rolls every cell at once. Amount 0 = exact passthrough. ASCII only.

MODULE = 'block'

PAGES = [
    ('Block', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Blocksize', 'Int', 32, {'min': 4, 'max': 128, 'label': 'Block size px'}),
        ('Irregular', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Irregular (quadtree split)'}),
        ('Chance', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Corruption chance'}),
        ('Rate', 'Float', 8.0, {'min': 0, 'max': 30, 'label': 'Rate Hz (re-roll)'}),
        ('Jitter', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Per-cell rate jitter'}),
        ('Slice', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Slice loss (row runs on)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Modes', [
        ('Wsmear', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Smear weight'}),
        ('Wrepeat', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Repeat weight'}),
        ('Woffset', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Offset weight'}),
        ('Wcolour', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Colour swap weight'}),
        ('Wfreeze', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Freeze weight'}),
        ('Smeardir', 'Menu', 'random', {'names': ['random', 'horizontal', 'vertical'],
                                        'labels': ['Random', 'Horizontal', 'Vertical']}),
        ('Tile', 'Int', 6, {'min': 1, 'max': 32, 'label': 'Repeat tile px'}),
        ('Shiftmax', 'Float', 160.0, {'min': 0, 'max': 1080, 'label': 'Offset max px'}),
        ('Snap', 'Toggle', True, {'label': 'Snap offset to grid'}),
        ('Colourerr', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Chroma drift'}),
    ]),
    ('Beat', [
        ('Beat', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Beat (edge > 0.5 = burst)'}),
        ('Bpm', 'Float', 0.0, {'min': 0, 'max': 200, 'label': 'Metronome BPM (0 = off)'}),
        ('Burstchance', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Burst chance'}),
        ('Burstdecay', 'Float', 0.3, {'min': 0.02, 'max': 2, 'label': 'Burst decay s'}),
    ]),
]
PANEL_PAGES = ['Block', 'Modes', 'Beat']

_OFF = {'Bpm': 0.0}
PRESETS = [
    (1, 'tv loss', dict(_OFF, Amount=1.0, Blocksize=32, Irregular=0.4, Chance=0.15, Rate=8.0, Jitter=0.5, Slice=0.08,
                        Wsmear=1.0, Wrepeat=0.5, Woffset=1.0, Wcolour=0.3, Wfreeze=0.0, Snap=1, Seed=1)),
    (2, 'green macro', dict(_OFF, Amount=1.0, Blocksize=16, Irregular=0.5, Chance=0.25, Rate=4.0, Jitter=0.8,
                            Slice=0.0, Wsmear=0.0, Wrepeat=0.0, Woffset=0.0, Wcolour=1.0, Wfreeze=0.0,
                            Colourerr=0.7, Seed=2)),
    (3, 'stuck decoder', dict(_OFF, Amount=1.0, Blocksize=64, Irregular=0.6, Chance=0.3, Rate=2.0, Jitter=0.3,
                              Slice=0.0, Wsmear=0.3, Wrepeat=1.0, Woffset=0.0, Wcolour=0.0, Wfreeze=1.0, Tile=4, Seed=3)),
    (4, 'slice drop', dict(_OFF, Amount=1.0, Blocksize=16, Irregular=0.0, Chance=0.03, Rate=10.0, Jitter=0.0,
                           Slice=0.35, Wsmear=1.0, Wrepeat=0.0, Woffset=1.0, Wcolour=0.2, Wfreeze=0.0, Snap=0, Seed=4)),
    (5, 'beat burst', dict(Amount=1.0, Blocksize=24, Irregular=0.5, Chance=0.0, Rate=0.0, Jitter=0.0, Slice=0.1,
                           Wsmear=1.0, Wrepeat=0.6, Woffset=1.0, Wcolour=0.5, Wfreeze=0.0, Bpm=120.0,
                           Burstchance=0.7, Burstdecay=0.35, Seed=5)),
]

SHADER = """// FX_glitch block (compute, T-47). in0 = picture, in1 = previous output (freeze) or the picture, in2 = stamp.
// stamp (1x1): x now, y previous cook, z last burst time, w = 2 * beat count + last beat bit.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount blocksize chance irregular
uniform vec4 uB;   // rate jitter seed time
uniform vec4 uC;   // weights smear repeat offset colour
uniform vec4 uD;   // weight freeze, shiftmax, snap, tile
uniform vec4 uE;   // colourerr smeardir slice burstchance
uniform vec4 uF;   // burstdecay
uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
float h(uvec4 k) { return float(pcg(k.x ^ pcg(k.y ^ pcg(k.z ^ pcg(k.w)))) >> 8) / 16777215.0; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }       // exact passthrough
    vec4 st = texelFetch(sTD2DInputs[2], ivec2(0), 0);
    bool fresh = st.x - st.y > 0.25;
    float env = (st.z > 0.0) ? exp(-max(st.x - st.z, 0.0) / max(uF.x, 1e-3)) : 0.0;
    uint seed = uint(uB.z) * 7919u;
    uint cnt = uint(floor(st.w * 0.5));
    int B = max(int(uA.y + 0.5), 1);
    ivec2 bc = p / B;                                                           // base cell
    float hj = h(uvec4(uvec2(bc), seed, 11u));
    uint E = uint(floor(uB.w * uB.x * (1.0 + uB.y * (hj - 0.5)) + uB.y * hj * 13.0)) + cnt * 104729u;
    float chance = uA.z + uE.w * env;
    // slice loss: a hit row runs from a start cell to the end of the line, all with the start cell's state
    uint rowE = uint(floor(uB.w * uB.x)) + cnt * 104729u;
    bool slice = h(uvec4(uint(bc.y), rowE, seed, 21u)) < uE.z * (1.0 + env);
    int cols = (isz.x + B - 1) / B;
    int sx = int(h(uvec4(uint(bc.y), rowE, seed, 22u)) * float(cols));
    int s = B;
    ivec2 o = bc * B;
    uvec4 key;
    bool hit;
    if (slice && bc.x >= sx) {
        key = uvec4(uint(sx), uint(bc.y), uint(B), rowE + seed);
        hit = true;
    } else {
        for (int k = 0; k < 2; k++) {                                           // 2-level quadtree split
            if (s < 4) break;
            ivec2 cc = p / s;
            if (h(uvec4(uvec2(cc), uint(s) + seed, E + 31u)) >= uA.w) break;
            s /= 2;
        }
        o = (p / s) * s;
        key = uvec4(uvec2(o), uint(s), E + seed);
        hit = h(key ^ uvec4(1u)) < chance;
    }
    if (!hit) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    float wt[5] = float[5](uC.x, uC.y, uC.z, uC.w, uD.x);
    float tot = wt[0] + wt[1] + wt[2] + wt[3] + wt[4];
    if (tot <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    float r = h(key ^ uvec4(2u)) * tot;
    int mode = 4;
    for (int k = 0; k < 4; k++) { if (r < wt[k]) { mode = k; break; } r -= wt[k]; }
    float r2 = h(key ^ uvec4(3u));
    float r3 = h(key ^ uvec4(4u));
    ivec2 l = p - o;
    vec4 res = c;
    if (mode == 0) {                                                            // smear: one column/row over the cell
        int dm = int(uE.y + 0.5);
        bool hor = (dm == 1) || (dm == 0 && r3 < 0.5);
        ivec2 q = hor ? ivec2(o.x + int(r2 * float(s)), p.y) : ivec2(p.x, o.y + int(r2 * float(s)));
        res = texelFetch(sTD2DInputs[0], clamp(q, ivec2(0), isz - 1), 0);
    } else if (mode == 1) {                                                     // repeat: a sub-block tiled
        int T = clamp(int(uD.w + 0.5), 1, s);
        ivec2 org = o + ivec2(vec2(r2, r3) * float(s - T));
        res = texelFetch(sTD2DInputs[0], clamp(org + l % T, ivec2(0), isz - 1), 0);
    } else if (mode == 2) {                                                     // offset / tile scramble
        vec2 off = (vec2(r2, r3) - 0.5) * 2.0 * uD.y;
        if (uD.z > 0.5) off = round(off / float(s)) * float(s);
        ivec2 q = ivec2(mod(vec2(p) + floor(off), vec2(isz)));                  // wraps (int % of negatives is undefined)
        res = texelFetch(sTD2DInputs[0], clamp(q, ivec2(0), isz - 1), 0);
    } else if (mode == 3) {                                                     // colour: swap + Cb/Cr DC drift
        int pm = int(r2 * 5.0);
        vec3 v = pm == 0 ? c.gbr : pm == 1 ? c.brg : pm == 2 ? c.rbg : pm == 3 ? c.bgr : c.grb;
        float Y = dot(v, vec3(0.299, 0.587, 0.114));
        float cb = (v.b - Y) * 0.564 + (h(key ^ uvec4(5u)) - 0.5) * 2.0 * uE.x;
        float cr = (v.r - Y) * 0.713 + (r3 - 0.5) * 2.0 * uE.x;
        res = vec4(Y + 1.403 * cr, Y - 0.344 * cb - 0.714 * cr, Y + 1.773 * cb, c.a);
    } else {                                                                    // freeze: previous output
        res = fresh ? c : texelFetch(sTD2DInputs[1], p, 0);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, res, uA.x));
}
"""

STAMP = """// stamp: 1x1 rgba32float in place. x now, y previous cook, z last burst time, w = 2 * beat count + last beat bit.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;   // now, beat value
void main() {
    vec4 s = TDImageLoadOutput(0, ivec3(0));
    float cnt = floor(s.w * 0.5);
    float pb = s.w - cnt * 2.0;
    float b = uT.y > 0.5 ? 1.0 : 0.0;
    float bt = s.z;
    if (b > 0.5 && pb < 0.5) { bt = uT.x; cnt += 1.0; }
    TDImageStoreOutput(0, ivec3(0), vec4(uT.x, s.x, bt, cnt * 2.0 + b));
}
"""

P = "parent().par.{}.eval()"


def build(m, H):
    """Fill instance COMP m: in1 -> prev_src (+ fb) / stamp -> fx (compute GLSL) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    fb = mk(m, feedbackTOP, 'fb')
    fb.inputConnectors[0].connect(in1)
    fb.par.top = 'fx'
    fb.comment = 'Previous fx output (Freeze mode only; cooks only while prev_src selects it).'
    prev = mk(m, switchTOP, 'prev_src')
    prev.inputConnectors[0].connect(in1)
    prev.inputConnectors[1].connect(fb)
    expr(prev.par.index, '1 if %s > 0 else 0' % P.format('Wfreeze'))
    st = H['compute'](m, 'stamp', STAMP, [], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    H['uniforms'](st, [('uT', ['absTime.seconds',
                              'max(%s, 1.0 if %s > 0 and (absTime.seconds * %s / 60.0) %% 1.0 < 0.25 else 0.0)'
                              % (P.format('Beat'), P.format('Bpm'), P.format('Bpm')), '0', '0'])])
    st.comment = 'Cook clock + beat edge: x now, y prev cook (gap > 0.25 s = stale freeze), z burst time, w beats.'
    g = H['compute'](m, 'fx', SHADER, [in1, prev, st])
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), P.format('Blocksize'), P.format('Chance'), P.format('Irregular')]),
        ('uB', [P.format('Rate'), P.format('Jitter'), P.format('Seed'), 'absTime.seconds']),
        ('uC', [P.format('Wsmear'), P.format('Wrepeat'), P.format('Woffset'), P.format('Wcolour')]),
        ('uD', [P.format('Wfreeze'), P.format('Shiftmax'), '1 if %s else 0' % P.format('Snap'), P.format('Tile')]),
        ('uE', [P.format('Colourerr'), 'parent().par.Smeardir.menuIndex', P.format('Slice'),
                P.format('Burstchance')]),
        ('uF', [P.format('Burstdecay'), '0', '0', '0']),
    ])
    g.comment = 'block: macroblock corruption + tile scramble (DG-07), one compute pass. Amount 0 = exact passthrough.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Block', 'role': 'process', 'ops': ['fb', 'prev_src', 'stamp', 'stamp_compute', 'fx', 'fx_compute'],
         'body': 'One compute pass; stamp = cook clock + beat bursts; fb only for Freeze.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
