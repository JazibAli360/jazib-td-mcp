# fx_glitch_bits - FX_glitch module 'bits' (FX1 DG-09 bit-crush / bit-plane / bit-flip; FX6 probe 2: uint ops exact).
# Template: docs/builds/fx_glitch.md "Module template". ONE compute pass, per pixel, in this order:
# float mantissa crush (Floatbits) -> colour depth (per-channel bits, RGB565 / RGB332 / 1-bit / grey) with optional
# ordered Bayer 4/8 or hash dither, in gamma or linear light -> 8-bit integer ops: bit-plane keep/drop, logic op
# (XOR/AND/OR/NOT/rotate/reverse) with a Mask that can spread across channels and walk per Rate tick -> random bit
# flips (Fliprate, only bits >= Flipmin). Amount 0 = exact passthrough. ASCII only.

MODULE = 'bits'

PAGES = [
    ('Bits', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Depth', 'Menu', 'rgb', {'names': ['rgb', 'rgb565', 'rgb332', 'onebit', 'grey'],
                                  'labels': ['Per channel (Bits R/G/B)', 'RGB565', 'RGB332', '1-bit', 'Grey (Bits R)']}),
        ('Bitsr', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Bits R'}),
        ('Bitsg', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Bits G'}),
        ('Bitsb', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Bits B'}),
        ('Dither', 'Menu', 'bayer4', {'names': ['none', 'bayer4', 'bayer8', 'hash'],
                                      'labels': ['None', 'Bayer 4x4', 'Bayer 8x8', 'Hash noise']}),
        ('Ditheramt', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Dither amount'}),
        ('Ditherscale', 'Int', 1, {'min': 1, 'max': 16, 'label': 'Dither pixel size'}),
        ('Linear', 'Toggle', False, {'label': 'Quantise in linear light'}),
        ('Floatbits', 'Int', 0, {'min': 0, 'max': 23, 'label': 'Float mantissa bits dropped'}),
    ]),
    ('Ops', [
        ('Planemode', 'Menu', 'off', {'names': ['off', 'keep', 'drop'],
                                      'labels': ['Off', 'Keep only plane', 'Drop plane']}),
        ('Plane', 'Int', 7, {'min': 0, 'max': 7, 'label': 'Bit plane (0 = LSB)'}),
        ('Op', 'Menu', 'none', {'names': ['none', 'xor', 'and', 'or', 'not', 'rotate', 'reverse'],
                                'labels': ['None', 'XOR mask', 'AND mask', 'OR mask', 'NOT', 'Rotate left', 'Reverse']}),
        ('Mask', 'Int', 170, {'min': 0, 'max': 255, 'label': 'Mask (0-255)'}),
        ('Maskspread', 'Int', 0, {'min': 0, 'max': 7, 'label': 'Mask rotate per channel'}),
        ('Maskwalk', 'Toggle', False, {'label': 'Mask walks per tick'}),
        ('Rotate', 'Int', 1, {'min': 0, 'max': 7, 'label': 'Rotate bits'}),
        ('Fliprate', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Bit-flip chance'}),
        ('Flipmin', 'Int', 5, {'min': 0, 'max': 7, 'label': 'Flip bits >='}),
        ('Rate', 'Float', 12.0, {'min': 0, 'max': 60, 'label': 'Rate Hz (flip / walk ticks)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['Bits', 'Ops']

_Z = {'Planemode': 0, 'Op': 0, 'Fliprate': 0.0, 'Floatbits': 0, 'Maskwalk': 0, 'Maskspread': 0, 'Linear': 0,
      'Ditherscale': 1}
PRESETS = [
    (1, '4-bit arcade', dict(_Z, Amount=1.0, Depth=0, Bitsr=4, Bitsg=4, Bitsb=4, Dither=1, Ditheramt=1.0, Seed=1)),
    (2, 'gameboy 2-bit', dict(_Z, Amount=1.0, Depth=4, Bitsr=2, Dither=2, Ditheramt=1.0, Ditherscale=4, Seed=2)),
    (3, 'xor psychedelia', dict(_Z, Amount=1.0, Depth=0, Bitsr=8, Bitsg=8, Bitsb=8, Dither=0, Op=1, Mask=170,
                                Maskspread=3, Maskwalk=1, Rate=4.0, Seed=3)),
    (4, 'speckle corrupt', dict(_Z, Amount=1.0, Depth=1, Dither=0, Fliprate=0.02, Flipmin=6, Rate=24.0, Seed=4)),
    (5, 'plane slice', dict(_Z, Amount=1.0, Depth=0, Bitsr=8, Bitsg=8, Bitsb=8, Dither=0, Planemode=1, Plane=6,
                            Seed=5)),
]

SHADER = """// FX_glitch bits (compute, T-47; FX6 probe 2). in0 = picture.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount depthmode dithermode ditheramt
uniform vec4 uB;   // bits r g b, linear
uniform vec4 uC;   // planemode plane op mask
uniform vec4 uD;   // maskspread maskwalk rotate fliprate
uniform vec4 uE;   // flipmin rate seed time
uniform vec4 uF;   // floatbits ditherscale
uint pcg(uint v) { uint s = v * 747796405u + 2891336453u; uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
                   return (w >> 22u) ^ w; }
uint hu(uvec4 k) { return pcg(k.x ^ pcg(k.y ^ pcg(k.z ^ pcg(k.w)))); }
float h(uvec4 k) { return float(hu(k) >> 8) / 16777215.0; }
float bayer(ivec2 q, int n) {                                                  // ordered Bayer threshold in [0,1)
    uint x = uint(q.x), y = uint(q.y), v = 0u;                                  // checked vs the 4x4 / 8x8 tables
    for (int i = 0; i < 3; i++) {
        if (i >= n) break;
        uint bx = (x >> uint(i)) & 1u, by = (y >> uint(i)) & 1u, s = uint(2 * (n - 1 - i));
        v |= ((bx ^ by) << (s + 1u)) | (by << s);
    }
    return (float(v) + 0.5) / float(1 << (2 * n));
}
vec3 toLin(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c)); }
vec3 toGam(vec3 c) { return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
uint rotl8(uint u, uint r) { r &= 7u; return ((u << r) | (u >> ((8u - r) & 7u))) & 255u; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }       // exact passthrough
    vec3 v = c.rgb;
    int fb = int(uF.x + 0.5);
    if (fb > 0) {                                                               // float mantissa crush
        uint m = ~((1u << uint(min(fb, 23))) - 1u);
        v = uintBitsToFloat(floatBitsToUint(v) & uvec3(m));
    }
    bool lin = uB.w > 0.5;
    if (lin) v = toLin(clamp(v, 0.0, 1.0));
    int dm = int(uA.z + 0.5);
    ivec2 dq = p / max(int(uF.y + 0.5), 1);
    uint seed = uint(uE.z) * 7919u;
    uint E = uint(floor(uE.w * uE.y));
    float d = 0.5;
    if (dm == 1) d = bayer(dq, 2); else if (dm == 2) d = bayer(dq, 3);
    else if (dm == 3) d = h(uvec4(uvec2(dq), seed, 3u));
    d = 0.5 + (d - 0.5) * uA.w;
    int depth = int(uA.y + 0.5);
    vec3 bits = depth == 1 ? vec3(5, 6, 5) : depth == 2 ? vec3(3, 3, 2) : uB.xyz;
    if (depth == 3 || depth == 4) {                                             // 1-bit / grey
        float Y = dot(v, vec3(0.2126, 0.7152, 0.0722));
        float L = depth == 3 ? 1.0 : exp2(clamp(uB.x, 1.0, 8.0)) - 1.0;
        v = vec3(floor(Y * L + d) / L);
    } else {
        vec3 L = exp2(clamp(bits, 1.0, 8.0)) - 1.0;
        v = floor(v * L + d) / L;
    }
    v = clamp(v, 0.0, 1.0);
    if (lin) v = toGam(v);
    uvec3 u = uvec3(round(v * 255.0));
    int pm = int(uC.x + 0.5);
    uint pl = uint(clamp(uC.y, 0.0, 7.0));
    if (pm == 1) u = ((u >> pl) & 1u) * 255u;
    else if (pm == 2) u &= uvec3(~(1u << pl) & 255u);
    int op = int(uC.z + 0.5);
    if (op > 0) {
        uint mk = uint(clamp(uC.w, 0.0, 255.0));
        if (uD.y > 0.5) mk ^= hu(uvec4(E, seed, 5u, 0u)) & 255u;
        uint sp = uint(uD.x);
        uvec3 M = uvec3(mk, rotl8(mk, sp), rotl8(mk, 2u * sp));
        uint r = uint(uD.z);
        for (int k = 0; k < 3; k++) {
            uint x = u[k];
            if (op == 1) x ^= M[k]; else if (op == 2) x &= M[k]; else if (op == 3) x |= M[k];
            else if (op == 4) x = ~x & 255u; else if (op == 5) x = rotl8(x, r);
            else x = bitfieldReverse(x) >> 24u;
            u[k] = x;
        }
    }
    if (uD.w > 0.0) {                                                           // random bit flips
        uint fm = uint(clamp(uE.x, 0.0, 7.0));
        for (int k = 0; k < 3; k++) {
            uvec4 key = uvec4(uvec2(p), E, seed + uint(k) * 17u);
            if (h(key) < uD.w) {
                uint b = fm + (hu(key ^ uvec4(9u)) % (8u - fm));
                u[k] ^= (1u << b);
            }
        }
    }
    vec3 o = vec3(u & 255u) / 255.0;
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(o, c.a), uA.x));
}
"""

P = "parent().par.{}.eval()"


def build(m, H):
    """Fill instance COMP m: in1 -> fx (one compute pass) -> out1."""
    mk = H['mk']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', SHADER, [in1])
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), 'parent().par.Depth.menuIndex', 'parent().par.Dither.menuIndex',
                P.format('Ditheramt')]),
        ('uB', [P.format('Bitsr'), P.format('Bitsg'), P.format('Bitsb'), '1 if %s else 0' % P.format('Linear')]),
        ('uC', ['parent().par.Planemode.menuIndex', P.format('Plane'), 'parent().par.Op.menuIndex', P.format('Mask')]),
        ('uD', [P.format('Maskspread'), '1 if %s else 0' % P.format('Maskwalk'), P.format('Rotate'),
                P.format('Fliprate')]),
        ('uE', [P.format('Flipmin'), P.format('Rate'), P.format('Seed'), 'absTime.seconds']),
        ('uF', [P.format('Floatbits'), P.format('Ditherscale'), '0', '0']),
    ])
    g.comment = 'bits: bit-crush / plane / logic ops / flips (DG-09), one uint compute pass. Amount 0 = exact.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Bits', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'One uint compute pass.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
