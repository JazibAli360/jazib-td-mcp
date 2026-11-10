# fx_stylise_outline - FX_stylise module 'outline' (FX7a SX-06 mask outline / neon halo / sticker + FX7c 7C-05 Notch
# "Image Distance" contour echo; BUILD_PLAN_27OCT rank 6, pilot of FX_stylise). Template: docs/builds/fx_glitch.md
# "Module template" (rack = builders/fx_stylise.py). Doc: docs/builds/fx_stylise.md. Numpy mirror:
# builders/fx_stylise_outline_logic.py.
# A matte (luma / alpha / max rgb of in1, Threshold, Invert) -> jump-flood distance to its outline at Res (full / half /
# quarter) -> signed distance per full-res pixel -> outline / halo / contour bands / sticker / distance view, coloured
# solid or from the module palette (W1-B), composited premultiplied over Back / Inside (picture, dim, black,
# transparent). Passes:
#   seed : per JFA texel, box-mean matte of its Res x Res block; an inside texel next to an outside one stores the
#          sub-texel edge point (linear crossing of Threshold) = a JFA seed (px, 1, 1)
#   jfa  : builders/glsl/gen_sim_vor_jfa.glsl imported READ-ONLY (GEN_sim's file, not edited), npasses = Pm + Extra
#   fx   : nearest seed over the 2x2 JFA texels around the pixel -> distance (full px), sign from the full-res matte,
#          Wobble noise, the look, palette colour, Amount mix
# Amount 0 = in1 exact (out_sel; fx also writes texelFetch). <= 3 GLSL TOP inputs (T-88). ASCII only.
import os

MODULE = 'outline'
MODES = ['outline', 'halo', 'contour', 'sticker', 'distance']
MATTES = ['luma', 'alpha', 'maxrgb']
RES = ['full', 'half', 'quarter']
DIRS = ['outward', 'inward', 'both']
FUNCS = ['lines', 'saw', 'bounce', 'sine']
BACKS = ['picture', 'dim', 'black', 'transparent']
BLENDS = ['over', 'add']

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
COLSRC = [m for m, _l in _PML.COLSRC_MODES]  # noqa: F821

PAGES = [
    ('Outline', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'outline', {'names': MODES, 'labels': [
            'Outline (line at Offset)', 'Neon halo (line + glow outside)', 'Contour echo (bands, Notch Image Distance)',
            'Sticker border (solid around the shape)', 'Distance view (grey, debug)']}),
        ('Matte', 'Menu', 'luma', {'names': MATTES, 'labels': ['Luma', 'Alpha (keyed / person matte)', 'Max RGB']}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Matte threshold'}),
        ('Invert', 'Toggle', False, {'label': 'Invert matte'}),
        ('Res', 'Menu', 'half', {'names': RES, 'labels': ['Full', 'Half (default)', 'Quarter (fastest)'],
                                 'label': 'Distance resolution'}),
        ('Extra', 'Int', 1, {'min': 0, 'max': 3, 'label': 'JFA clean-up passes'}),
        ('Maxdist', 'Float', 0.0, {'min': 0, 'max': 2000, 'label': 'Distance range px (0 = auto from the look)'}),
        ('Width', 'Float', 6.0, {'min': 0, 'max': 64, 'label': 'Line width px'}),
        ('Offset', 'Float', 0.0, {'min': -100, 'max': 200, 'label': 'Offset px (+ = outward)'}),
        ('Soft', 'Float', 1.5, {'min': 0, 'max': 20, 'label': 'Edge softness px'}),
        ('Intensity', 'Float', 1.5, {'min': 0, 'max': 8, 'label': 'Intensity (HDR with Hdr on)'}),
        ('Glow', 'Float', 24.0, {'min': 0, 'max': 300, 'label': 'Halo falloff px'}),
        ('Glowgain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Halo gain'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (wobble)'}),
    ]),
    ('Contour', [
        ('Spacing', 'Float', 24.0, {'min': 2, 'max': 200, 'label': 'Band spacing px'}),
        ('Bands', 'Int', 8, {'min': 0, 'max': 64, 'label': 'Bands (0 = endless)'}),
        ('Fade', 'Float', 3.0, {'min': 0, 'max': 32, 'label': 'Fade over the last N bands'}),
        ('Direction', 'Menu', 'outward', {'names': DIRS, 'labels': ['Outward', 'Inward', 'Both']}),
        ('Function', 'Menu', 'lines', {'names': FUNCS, 'labels': ['Lines (Width)', 'Saw', 'Bounce', 'Sine']}),
        ('Gap', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Gap (share of each band left empty)'}),
        ('Speed', 'Float', 0.5, {'min': -4, 'max': 4, 'label': 'Speed (bands / s; ripple)'}),
        ('Phase', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Phase (bind audio)'}),
    ]),
    ('Look', [
        ('Colsrc', 'Menu', 'solid', {'names': COLSRC, 'labels': [lb for _m, lb in _PML.COLSRC_MODES],  # noqa: F821
                                     'label': 'Colour source'}),
        ('Colr', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Colour R'}),
        ('Colg', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Colour G'}),
        ('Colb', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Colour B'}),
        ('Palpos', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Palette position'}),
        ('Palspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Palette spread (x attribute)'}),
        ('Keep', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Keep picture colour'}),
        ('Back', 'Menu', 'picture', {'names': BACKS, 'labels': ['Picture', 'Dimmed', 'Black', 'Transparent']}),
        ('Inside', 'Menu', 'picture', {'names': BACKS, 'labels': ['Picture', 'Dimmed', 'Black', 'Transparent']}),
        ('Backdim', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Dim level'}),
        ('Blend', 'Menu', 'over', {'names': BLENDS, 'labels': ['Over (premultiplied)', 'Add (light)']}),
        ('Wobble', 'Float', 0.0, {'min': 0, 'max': 40, 'label': 'Wobble px (noise on distance)'}),
        ('Wobblescale', 'Float', 60.0, {'min': 2, 'max': 400, 'label': 'Wobble scale px'}),
        ('Wobblespeed', 'Float', 0.5, {'min': 0, 'max': 8, 'label': 'Wobble speed'}),
        ('Pulse', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Pulse (bind a beat / kick)'}),
        ('Pulsegain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Pulse gain (width, glow, intensity)'}),
        ('Hdr', 'Toggle', False, {'label': 'HDR out (rgba16float)'}),
    ]),
    pal_page('neon_trio', 'cycle'),  # noqa: F821
]
PANEL_PAGES = ['Outline', 'Contour', 'Look', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
for _k in ('Invert', 'Palreverse', 'Hdr'):
    _D[_k] = int(_D[_k])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'neon outline', _p(Mode=0, Width=8.0, Intensity=1.6, Colr=0.1, Colg=1.0, Colb=0.6, Seed=1)),
    (2, 'halo', _p(Mode=1, Res=2, Width=4.0, Glow=40.0, Glowgain=1.2, Colsrc=1, Palpos=0.35, Back=1, Backdim=0.35, Seed=2)),
    (3, 'contour echo', _p(Mode=2, Res=2, Spacing=22.0, Bands=12, Fade=4.0, Width=5.0, Speed=0.6, Colsrc=4, Palspread=1.0,
                           Back=2, Inside=0, Seed=3)),
    (4, 'sticker', _p(Mode=3, Width=28.0, Soft=1.0, Colr=1.0, Colg=1.0, Colb=1.0, Intensity=1.0, Back=3, Seed=4)),
    (5, 'wobble rings', _p(Mode=2, Res=2, Direction=2, Function=3, Spacing=36.0, Bands=0, Speed=-0.4, Wobble=10.0,
                           Wobblescale=90.0, Colsrc=2, Palspread=0.25, Blend=1, Back=1, Backdim=0.2, Seed=5)),
]

LIB = """
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hsh(ivec2 c, uint s) { return float(lb32(uint(c.x) * 1597334677u ^ lb32(uint(c.y) ^ (s * 2654435761u)))) * (1.0 / 4294967296.0); }
float matteOf(vec4 c, int mt, float inv) {
    float m = mt == 1 ? c.a : (mt == 2 ? max(c.r, max(c.g, c.b)) : dot(c.rgb, vec3(0.2126, 0.7152, 0.0722)));
    return inv > 0.5 ? 1.0 - m : m;
}
"""

SEED = """// FX_stylise outline seed (compute, rgba32float, JFA size). One texel per Res x Res block of in1: m = matte of the
// block's mean colour (bilinear taps, inputextenduv hold); an inside texel (m > Threshold) with an outside 4-neighbour stores the nearest linear Threshold
// crossing toward it as a JFA seed (px, 1, 1); every other texel (0). Neighbour order +x -x +y -y, strict <.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS;   // res div, threshold, matte, invert
""" + LIB + """
vec4 cellC(ivec2 j, int D, ivec2 isz) {          // block mean: D 1 texelFetch, D 2 one bilinear tap at the block
    if (D == 1) return texelFetch(sTD2DInputs[0], min(j, isz - 1), 0);   // centre (exact 2x2 mean), D 4 four taps
    int h = D / 2;
    vec4 s = vec4(0.0);
    for (int b = 0; b < 2; b++) for (int a = 0; a < 2; a++) {
        if (a >= h || b >= h) continue;
        s += texture(sTD2DInputs[0], (vec2(j * D) + vec2(1 + 2 * a, 1 + 2 * b)) / vec2(isz));
    }
    return s / float(h * h);
}
float cellM(ivec2 j, int D, ivec2 isz, int mt, float inv) { return matteOf(cellC(j, D, isz), mt, inv); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    int D = clamp(int(uS.x + 0.5), 1, 4);
    ivec2 jsz = (isz + D - 1) / D;
    if (p.x >= jsz.x || p.y >= jsz.y) return;
    int mt = int(uS.z + 0.5);
    float thr = uS.y;
    float m0 = cellM(p, D, isz, mt, uS.w);
    vec4 o = vec4(0.0);
    if (m0 > thr) {
        float bt = 2.0;
        vec2 bp = vec2(0.0);
        for (int k = 0; k < 4; k++) {
            ivec2 dv = k == 0 ? ivec2(1, 0) : (k == 1 ? ivec2(-1, 0) : (k == 2 ? ivec2(0, 1) : ivec2(0, -1)));
            ivec2 q = p + dv;
            if (q.x < 0 || q.y < 0 || q.x >= jsz.x || q.y >= jsz.y) continue;
            float m1 = cellM(q, D, isz, mt, uS.w);
            if (m1 > thr) continue;
            float t = (m0 - thr) / max(m0 - m1, 1e-6);
            if (t < bt) { bt = t; bp = vec2(p) + 0.5 + t * vec2(dv); }
        }
        if (bt < 2.0) o = vec4(bp, 1.0, 1.0);
    }
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
"""

FX = """// FX_stylise outline fx (compute). in0 picture (full res, texelFetch), in1 JFA (nearest edge seed per texel).
// Signed distance sd (full px, < 0 inside the matte) -> outline / halo / contour / sticker / distance view, colour
// from pxColSrc (solid / W1-B palette / picture), premultiplied over the Back (outside) / Inside base.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode, threshold, matte
uniform vec4 uB;   // width, offset, soft, intensity
uniform vec4 uC;   // glow, glowgain, spacing, bands
uniform vec4 uD;   // phase (bands), direction, function, gap
uniform vec4 uE;   // back, inside, backdim, blend
uniform vec4 uF;   // colr, colg, colb, invert
uniform vec4 uG;   // wobble px, wobble scale px, wobble time, seed
uniform vec4 uH;   // res div, pulse scale, fade bands, -
uniform vec4 uCs;  // colour source (mode, palpos, palspread, keep)
""" + LIB + PAL_GLSL + """
float vnoise(vec2 x, uint s) {
    vec2 i = floor(x), f = fract(x);
    vec2 u = f * f * (3.0 - 2.0 * f);
    ivec2 c = ivec2(i);
    float a = hsh(c, s), b = hsh(c + ivec2(1, 0), s), d = hsh(c + ivec2(0, 1), s), e = hsh(c + ivec2(1, 1), s);
    return mix(mix(a, b, u.x), mix(d, e, u.x), u.y);
}
vec4 baseOf(int k, vec4 c, float dim) {
    if (k == 1) return c * dim;
    if (k == 2) return vec4(0.0, 0.0, 0.0, 1.0);
    if (k == 3) return vec4(0.0);
    return c;
}
float band(float x, float w, float soft) { return 1.0 - smoothstep(0.5 * (w - soft), 0.5 * (w + soft), abs(x)); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    int D = clamp(int(uH.x + 0.5), 1, 4);
    ivec2 jsz = textureSize(sTD2DInputs[1], 0);
    vec2 q = (vec2(p) + 0.5) / float(D);
    ivec2 b = ivec2(floor(q - 0.5));
    float bd = 1e30;
    for (int j = 0; j < 2; j++) for (int i = 0; i < 2; i++) {
        vec4 s = texelFetch(sTD2DInputs[1], clamp(b + ivec2(i, j), ivec2(0), jsz - 1), 0);
        if (s.z > 0.0) { vec2 e = q - s.xy; bd = min(bd, dot(e, e)); }
    }
    float d = bd < 1e29 ? sqrt(bd) * float(D) : 1e6;
    bool ins = matteOf(c, int(uA.w + 0.5), uF.w) > uA.z;
    float sd = ins ? -d : d;
    if (uG.x != 0.0) sd += uG.x * (2.0 * vnoise(vec2(p) / max(uG.y, 1.0) + vec2(uG.z, 0.37 * uG.z), uint(uG.w)) - 1.0);
    float S = uH.y;
    float W = uB.x * S, off = uB.y, soft = max(uB.z, 1e-3), I = uB.w * S;
    int mode = int(uA.y + 0.5);
    float a = 0.0, at = 0.0;
    float inCov = ins ? 1.0 : 0.0;
    if (mode == 0) {
        float e = sd - off;
        a = band(e, W, soft);
        at = clamp(e / max(W, 1e-3) + 0.5, 0.0, 1.0);
    } else if (mode == 1) {
        float e = sd - off;
        a = band(e, W, soft) + (e > 0.0 ? exp(-e / max(uC.x * S, 1e-3)) * uC.y : 0.0);
        at = clamp(e / max(3.0 * uC.x, 1e-3), 0.0, 1.0);
    } else if (mode == 2) {
        int dir = int(uD.y + 0.5);
        float u = (dir == 0 ? sd : (dir == 1 ? -sd : abs(sd))) - off;
        if (u >= 0.0) {
            float sp = max(uC.z, 1e-3);
            float ph = u / sp - uD.x;
            float k = floor(ph), f = ph - k;
            int fn = int(uD.z + 0.5);
            if (fn == 0) a = band(min(f, 1.0 - f) * sp, W, soft);
            else {
                a = fn == 1 ? 1.0 - f : (fn == 2 ? 1.0 - abs(2.0 * f - 1.0) : 0.5 + 0.5 * cos(6.2831853 * f));
                a *= f <= 1.0 - uD.w ? 1.0 : 0.0;
            }
            float x = u / sp + (fn == 0 ? 0.5 : 0.0);                  // lines: line k sits at x = k + 0.5
            if (uC.w > 0.0) a *= 1.0 - clamp((x - (uC.w - uH.z)) / max(uH.z, 1e-3), 0.0, 1.0);
            at = k;
        }
    } else if (mode == 3) {
        float e = sd - off;
        a = 1.0 - smoothstep(W - 0.5 * soft, W + 0.5 * soft, e);
        at = clamp(e / max(W, 1e-3), 0.0, 1.0);
        inCov = 1.0 - smoothstep(-0.5 * soft, 0.5 * soft, sd);
    }
    vec4 o;
    if (mode == 4) {
        float sc = max(uC.z * max(uC.w, 1.0), 1.0);
        o = vec4(vec3(clamp(0.5 + 0.5 * sd / sc, 0.0, 1.0)), 1.0);
    } else {
        vec4 base = mix(baseOf(int(uE.x + 0.5), c, uE.z), baseOf(int(uE.y + 0.5), c, uE.z), inCov);
        vec3 C = pxColSrc(uCs, uF.rgb, c.rgb, at) * I;
        float cov = clamp(a, 0.0, 1.0);
        if (mode == 3) {                                                  // sticker: under the shape's own picture
            vec4 st = vec4(C * cov, cov) + base * (1.0 - cov);
            o = mix(st, baseOf(int(uE.y + 0.5), c, uE.z), inCov);
        } else if (uE.w > 0.5) o = vec4(base.rgb + C * a, max(base.a, cov));
        else o = vec4(C * cov + base.rgb * (1.0 - cov), cov + base.a * (1.0 - cov));
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, o, uA.x));
}
"""

JFA_FILE = 'gen_sim_vor_jfa'           # GEN_sim's shader, imported read-only (BUILD_PLAN_27OCT s2 "JFA: reuse")
SHADERS = {'seed': SEED, 'fx': FX}
NIN = {'seed': 1, 'jfa': 1, 'fx': 2}             # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"
DIV = "(1 if parent().par.Res.eval() == 'full' else (2 if parent().par.Res.eval() == 'half' else 4))"
JW = "int(math.ceil(me.inputs[0].width / %s))" % DIV
JH = "int(math.ceil(me.inputs[0].height / %s))" % DIV
PMFULL = "max(1, int(math.ceil(math.log2(max(op('seed').width, op('seed').height, 2)))))"
# Range the look needs (full px): the JFA starts at step 2^(Pm-1) and reaches 2^Pm - 1 texels, so fewer passes when
# the look ends near the edge (outline 6 px: 4 passes instead of 10 at half res). Contour with Bands 0 / distance view
# = full frame. Pulse counts at its maximum (1 + Pulsegain) so a beat never changes the pass count.
_PP = "parent().par."
RANGE = ("(" + _PP + "Maxdist.eval() if " + _PP + "Maxdist.eval() > 0 else abs(" + _PP + "Offset.eval()) + " + _PP +
         "Soft.eval() + " + _PP + "Wobble.eval() + 2 + (1 + " + _PP + "Pulsegain.eval()) * max(" + _PP +
         "Width.eval(), 6 * " + _PP + "Glow.eval() if " + _PP + "Mode.eval() == 'halo' else 0, (" + _PP +
         "Spacing.eval() * (" + _PP + "Bands.eval() + 1) if " + _PP + "Bands.eval() > 0 else 1e9) if " + _PP +
         "Mode.eval() == 'contour' else 0, 1e9 if " + _PP + "Mode.eval() == 'distance' else 0))")
PM = "min(%s, max(1, int(math.ceil(math.log2(min(%s, 1e7) / %s + 2)))))" % (PMFULL, RANGE, DIV)
PULSE = "(1.0 + %s * %s)" % (P.format('Pulse'), P.format('Pulsegain'))


def uniforms():
    return {
        'seed': [('uS', [DIV, P.format('Threshold'), 'parent().par.Matte.menuIndex', 'float(%s)' % P.format('Invert')])],
        'jfa': [('uJ', ["op('seed').width", "op('seed').height", PM, '0'])],
        'fx': [('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Threshold'),
                       'parent().par.Matte.menuIndex']),
               ('uB', [P.format('Width'), P.format('Offset'), P.format('Soft'), P.format('Intensity')]),
               ('uC', [P.format('Glow'), P.format('Glowgain'), P.format('Spacing'), P.format('Bands')]),
               ('uD', ['%s * absTime.seconds + %s' % (P.format('Speed'), P.format('Phase')),
                       'parent().par.Direction.menuIndex', 'parent().par.Function.menuIndex', P.format('Gap')]),
               ('uE', ['parent().par.Back.menuIndex', 'parent().par.Inside.menuIndex', P.format('Backdim'),
                       'parent().par.Blend.menuIndex']),
               ('uF', [P.format('Colr'), P.format('Colg'), P.format('Colb'), 'float(%s)' % P.format('Invert')]),
               ('uG', [P.format('Wobble'), P.format('Wobblescale'), '%s * absTime.seconds' % P.format('Wobblespeed'),
                       P.format('Seed')]),
               ('uH', [DIV, PULSE, P.format('Fade'), '0']),
               ('uCs', ['parent().par.Colsrc.menuIndex', P.format('Palpos'), P.format('Palspread'),
                        P.format('Keep')])],
    }


def build(m, H):
    """Fill instance COMP m: in1 -> seed -> jfa (npasses) -> fx (+ in1) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    seed = H['pas'](m, 'seed', SEED, [in1], JW, JH, 'rgba32float')                 # extend hold (bilinear taps)
    H['uniforms'](seed, U['seed'])
    seed.comment = 'JFA seeds: sub-texel Threshold crossings of the box-mean matte at Res (px, 1, 1).'
    jfa = H['pas'](m, 'jfa', H['glsl'](JFA_FILE), [seed], "op('seed').width", "op('seed').height", 'rgba32float',
                   npasses='%s + int(%s)' % (PM, P.format('Extra')))
    H['uniforms'](jfa, U['jfa'])
    jfa.comment = ('Jump flood (GEN_sim gen_sim_vor_jfa.glsl, read-only): Pm = passes the look needs (Maxdist / auto, '
                   '<= ceil(log2(max size))), npasses = Pm + Extra.')
    fx = H['pas'](m, 'fx', FX, [in1, jfa], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput', extend='zero')
    expr(fx.par.format, "'rgba16float' if %s else 'useinput'" % P.format('Hdr'))
    H['uniforms'](fx, U['fx'])
    fx.comment = 'outline: signed distance -> outline / halo / contour / sticker; palette colour; Amount mix.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (seed / jfa / fx not pulled).'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Distance', 'role': 'process', 'ops': ['seed', 'seed_compute', 'jfa', 'jfa_compute'],
         'body': 'Matte edge seeds at Res, then jump flood: every texel knows its nearest edge point.'},
        {'title': '3 Look', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'Signed distance -> outline / halo / contour / sticker, palette colour (pal).'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
