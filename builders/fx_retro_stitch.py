# fx_retro_stitch - FX_retro module 'stitch' (FX7b TC-27 digital embroidery / cross-stitch; Xtal's look rebuilt from
# its description, procedural, no code seen). Two compute passes: `low` = pixelart's virtual-pixel pass (one texel per
# cell: centre / box sample, pre-adjust, thread colours = source / levels / rack palette Machine + dither; the same
# shader text and uniforms, so the two modules share it) -> `fx` (full res): Aida-style fabric (Fabric colour, woven
# ridges, holes at the cell corners), and per cell a stitch in the cell's thread colour: cross (\ under /), half
# (/ only) or satin (parallel diagonal strands). Threads are capsules Thread wide with cylinder shading, Twist ridges
# along the strand, a Gloss highlight, a drop Shadow on the fabric and per-cell hand Jitter. Cells close to the fabric
# colour (Skip) stay bare cloth. Premultiplied out, Amount mix, out_sel: Amount 0 = in1. Mirror:
# builders/fx_retro_stitch_logic.py. ASCII only.
import os

MODULE = 'stitch'
STYLES = ['cross', 'half', 'satin']
_PA = dict(globals())
with open(os.path.join(HERE, 'fx_retro_pixelart.py')) as _fh:         # noqa: F821 (rack HERE)
    exec(_fh.read(), _PA)                                                 # pixelart's LOW + its uniforms


def pages(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    ml = [l for _k, l in Lg['MACHINE_MENU']]
    return [
        ('Stitch', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Style', 'Menu', 'cross', {'names': STYLES, 'labels': ['Cross stitch', 'Half stitch (/)',
                                                                   'Satin strands']}),
            ('Pixelsize', 'Float', 18.0, {'min': 4, 'max': 96, 'label': 'Cell size px'}),
            ('Pixelaspect', 'Float', 1.0, {'min': 0.5, 'max': 2, 'label': 'Cell aspect (w / h)'}),
            ('Thread', 'Float', 0.55, {'min': 0.05, 'max': 1.5, 'label': 'Thread width'}),
            ('Twist', 'Float', 3.0, {'min': 0, 'max': 12, 'label': 'Twist ridges'}),
            ('Gloss', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Gloss'}),
            ('Shadow', 'Float', 0.45, {'min': 0, 'max': 1, 'label': 'Shadow on fabric'}),
            ('Jitter', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Hand jitter'}),
            ('Strands', 'Int', 4, {'min': 1, 'max': 8, 'label': 'Satin strands per cell'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
        ('Cloth', [
            ('Fabricr', 'Float', 0.93, {'min': 0, 'max': 1, 'label': 'Fabric R'}),
            ('Fabricg', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Fabric G'}),
            ('Fabricb', 'Float', 0.82, {'min': 0, 'max': 1, 'label': 'Fabric B'}),
            ('Weave', 'Float', 0.18, {'min': 0, 'max': 1, 'label': 'Weave ridges'}),
            ('Holes', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Corner holes'}),
            ('Skip', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Skip cells near fabric colour'}),
        ]),
        ('Threads', [
            ('Sampling', 'Menu', 'box', {'names': ['centre', 'box'], 'labels': ['Centre pixel', 'Box average']}),
            ('Colour', 'Menu', 'palette', {'names': ['none', 'levels', 'palette'],
                                           'labels': ['Source colours', 'Levels per channel', 'Palette (Machine)']}),
            ('Levels', 'Int', 5, {'min': 2, 'max': 32, 'label': 'Levels'}),
            ('Machine', 'Menu', 'pm_sweetie16' if 'pm_sweetie16' in mk else 'pico8', {'names': mk, 'labels': ml}),
            ('Dither', 'Menu', 'none', {'names': Lg['DITHER_METHODS'], 'labels': Lg['DITHER_LABELS']}),
            ('Ditheramt', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Dither amount'}),
            ('Contrast', 'Float', 1.1, {'min': 0, 'max': 3, 'label': 'Contrast (pre)'}),
            ('Brightness', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Brightness (pre)'}),
            ('Saturation', 'Float', 1.25, {'min': 0, 'max': 3, 'label': 'Saturation (pre)'}),
        ]),
    ]


PANEL_PAGES = ['Stitch', 'Cloth', 'Threads']


def presets(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in pages(Lg) for n, s, d, o in pl)
    return [
        (1, 'sampler', dict(D)),
        (2, 'fine cross', dict(D, Pixelsize=10.0, Thread=0.6, Twist=2.0, Jitter=0.15, Seed=2)),
        (3, 'half stitch', dict(D, Style=1, Pixelsize=14.0, Thread=0.8, Colour=1, Levels=4, Seed=3)),
        (4, 'satin patch', dict(D, Style=2, Pixelsize=24.0, Strands=5, Thread=0.5, Gloss=0.6, Skip=0.0,
                                Colour=2, Machine=mk.index('pico8'), Seed=4)),
        (5, 'dark denim', dict(D, Pixelsize=16.0, Fabricr=0.12, Fabricg=0.16, Fabricb=0.28, Weave=0.3, Holes=0.7,
                               Skip=0.12, Colour=0, Saturation=1.5, Seed=5)),
    ]


FX = """// FX_retro stitch fx pass (full res). in0 = picture (Amount mix), in1 = low (one straight colour per cell).
// = fx_retro_stitch_logic.render
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount style thread twist
uniform vec4 uB;   // fabric rgb, skip
uniform vec4 uC;   // shadow gloss jitter holes
uniform vec4 uD;   // psx psy seed strands
uniform vec4 uE;   // weave - - -
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hc(ivec2 v, uint k) { return float(lb32(uint(v.x) * 1597334677u ^ lb32(uint(v.y) ^ (k * 2654435761u))) >> 8)
                                   / 16777216.0; }
float W2;   // half thread width (cell units)
// capsule A -> B: x = shade (0 outside), y = along t (0..1)
vec2 strand(vec2 l, vec2 A, vec2 B) {
    vec2 d = B - A; float L2 = max(dot(d, d), 1e-6);
    float t = clamp(dot(l - A, d) / L2, 0.0, 1.0);
    float r = length(l - A - d * t) / W2;
    return vec2(r < 1.0 ? sqrt(1.0 - r * r) : 0.0, t);
}
vec3 thread(vec3 col, vec2 s, float sgn) {
    float ridge = 1.0 - 0.18 * (0.5 + 0.5 * sin(6.2831853 * (s.y * uA.w + sgn * 0.25 * (1.0 - s.x))));
    return col * (0.45 + 0.55 * s.x) * ridge + uC.y * pow(s.x, 8.0);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 res = textureSize(sTD2DInputs[0], 0);
    if (p.x >= res.x || p.y >= res.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    ivec2 ps = ivec2(max(int(uD.x + 0.5), 1), max(int(uD.y + 0.5), 1));
    ivec2 VG = textureSize(sTD2DInputs[1], 0);
    ivec2 v = p / ps;
    vec2 l = (vec2(p - v * ps) + 0.5) / vec2(ps);                // cell local 0..1 (y up)
    vec3 cell = texelFetch(sTD2DInputs[1], min(v, VG - 1), 0).rgb;
    uint sd = uint(uD.z) * 7919u;
    // fabric: woven ridges + holes at the cell corners
    vec3 fab = uB.rgb * (1.0 - uE.x * (0.5 + 0.5 * cos(6.2831853 * 2.0 * l.x) * cos(6.2831853 * 2.0 * l.y)));
    vec2 cq = min(l, 1.0 - l);
    float hole = uC.w * (1.0 - smoothstep(0.06, 0.14, length(cq)));
    fab *= 1.0 - 0.8 * hole;
    bool sew = length(cell - uB.rgb) > uB.w;
    vec3 o = fab;
    if (sew) {
        W2 = 0.5 * uA.z * 0.36;
        float j = uC.z * 0.12;
        vec2 jA = (vec2(hc(v, sd + 1u), hc(v, sd + 2u)) - 0.5) * j, jB = (vec2(hc(v, sd + 3u), hc(v, sd + 4u)) - 0.5) * j;
        int st = int(uA.y + 0.5);
        vec2 sh = vec2(0.07, -0.07);                                 // shadow offset (right, down)
        vec2 top = vec2(0.0), bot = vec2(0.0);
        float shd = 0.0;
        if (st == 2) {                                              // satin: parallel strands along '/'
            int n = max(int(uD.w + 0.5), 1);
            float k = (l.x - l.y) * float(n) * 0.5 + float(n) * 0.5;   // strand coordinate across the cell
            float fi = clamp(floor(k), 0.0, float(n) - 1.0);
            float off = (fi + 0.5) / float(n) * 2.0 - 1.0;          // -1..1 along x - y
            vec2 A = vec2(0.0, 0.0) + vec2(0.5, -0.5) * off, B = vec2(1.0, 1.0) + vec2(0.5, -0.5) * off;
            W2 = 0.5 * uA.z * 0.7071 / float(n) * 1.15;
            top = strand(l, A + jA, B + jB);
            shd = strand(l - sh, A + jA, B + jB).x;
        } else {
            top = strand(l, vec2(0.08) + jA, vec2(0.92) + jB);                       // '/'
            shd = strand(l - sh, vec2(0.08) + jA, vec2(0.92) + jB).x;
            if (st == 0) {
                bot = strand(l, vec2(0.08, 0.92) + jB, vec2(0.92, 0.08) + jA);       // '\\' under
                shd = max(shd, strand(l - sh, vec2(0.08, 0.92) + jB, vec2(0.92, 0.08) + jA).x);
            }
        }
        o = fab * (1.0 - uC.x * min(shd * 2.0, 1.0));
        if (bot.x > 0.0) o = thread(cell, bot, -1.0);
        if (top.x > 0.0) o = thread(cell, top, 1.0);
    }
    vec3 src = c0.a > 1e-5 ? c0.rgb / c0.a : c0.rgb;
    vec3 fin = mix(src, o, uA.x);
    float a = mix(c0.a, 1.0, uA.x);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(fin * a, a));
}
"""


def shader_texts(lib):
    return {'low': _PA['LOW'].replace('%LIB%', lib(pal_in=1, bn_in=2)), 'fx': FX}


def uniforms(H):
    P = H['P']
    low, _fx, grid = _PA['uniforms'](H)
    fx = [('uA', [P.format('Amount'), 'parent().par.Style.menuIndex', P.format('Thread'), P.format('Twist')]),
          ('uB', [P.format('Fabricr'), P.format('Fabricg'), P.format('Fabricb'), P.format('Skip')]),
          ('uC', [P.format('Shadow'), P.format('Gloss'), P.format('Jitter'), P.format('Holes')]),
          ('uD', [grid + '[0]', grid + '[1]', P.format('Seed'), P.format('Strands')]),
          ('uE', [P.format('Weave'), '0', '0', '0'])]
    return low, fx, grid


def build(m, H, Lg):
    """in1 -> low (cells, pixelart's pass) -> fx (fabric + stitches) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr, compute = H['mk'], H['expr'], H['compute']
    in1 = mk(m, inTOP, 'in1')
    pal = H['select'](m, 'pal', '../pal_top')
    bn = H['select'](m, 'bn', '../bn_top')
    U1, U2, grid = uniforms(H)
    sh = shader_texts(lambda **k: H['glsl_lib'](Lg, **k))
    low = compute(m, 'low', sh['low'], [in1, pal, bn], grid + '[2]', grid + '[3]', fmt='rgba16float', uniforms=U1)
    low.comment = "stitch: one thread colour per cell (pixelart's low pass: sample, levels / palette + dither)."
    fx = compute(m, 'fx', sh['fx'], [in1, low], 'me.inputs[0].width', 'me.inputs[0].height', uniforms=U2)
    fx.comment = 'stitch: fabric (weave, corner holes) + cross / half / satin stitches with shading, twist, gloss.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '0 if parent().par.Amount.eval() <= 0 else 1')
    sel.comment = 'Amount 0 = in1 exactly.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pal', 'bn'], 'body': 'Picture, rack palette bank, blue noise.'},
        {'title': '2 Stitch', 'role': 'process', 'ops': ['low', 'low_compute', 'fx', 'fx_compute'],
         'body': 'low: thread colour per cell. fx: fabric + stitches.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
