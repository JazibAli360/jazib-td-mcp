# fx_retro_pixelart - FX_retro module 'pixelart' (FX7a SX-08 pixel-art re-render with outlines; three.js
# RenderPixelatedPass / Gunnell "Pixel Art" ideas, re-written for 2D video, no code copied).
# Two compute passes: `low` (one texel per virtual pixel: centre / box sample, pre-adjust, colour = none / levels /
# rack palette (Machine) with the rack's ordered dither) -> `fx` (full res: nearest upscale of `low`, then per
# virtual pixel a 1-px OUTLINE on the darker side of every edge (a 4-neighbour brighter by > Edge, luma or rgb
# distance) in Outline colour, an inner HIGHLIGHT on the side facing Lightangle (brighter than the neighbour away from
# the light by > Edge), optional grid lines between virtual pixels). Premultiplied out (rack rule), Amount mix,
# out_sel: Amount 0 = in1 exactly. Mirror: builders/fx_retro_pixelart_logic.py. ASCII only.

MODULE = 'pixelart'
COLOURS = ['none', 'levels', 'palette']


def pages(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    ml = [l for _k, l in Lg['MACHINE_MENU']]
    return [
        ('Pixelart', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Pixelsize', 'Float', 6.0, {'min': 1, 'max': 32, 'label': 'Pixel size (px)'}),
            ('Pixelaspect', 'Float', 1.0, {'min': 0.5, 'max': 2, 'label': 'Pixel aspect (w / h)'}),
            ('Sampling', 'Menu', 'centre', {'names': ['centre', 'box'], 'labels': ['Centre pixel', 'Box average']}),
            ('Colour', 'Menu', 'levels', {'names': COLOURS, 'labels': ['Source colours', 'Levels per channel',
                                                                       'Palette (Machine)']}),
            ('Levels', 'Int', 6, {'min': 2, 'max': 32, 'label': 'Levels'}),
            ('Machine', 'Menu', 'pico8', {'names': mk, 'labels': ml}),
            ('Dither', 'Menu', 'none', {'names': Lg['DITHER_METHODS'], 'labels': Lg['DITHER_LABELS']}),
            ('Ditheramt', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Dither amount'}),
            ('Contrast', 'Float', 1.1, {'min': 0, 'max': 3, 'label': 'Contrast (pre)'}),
            ('Brightness', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Brightness (pre)'}),
            ('Saturation', 'Float', 1.2, {'min': 0, 'max': 3, 'label': 'Saturation (pre)'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
        ('Edges', [
            ('Edgeby', 'Menu', 'luma', {'names': ['luma', 'rgb'], 'labels': ['Luma step', 'RGB distance']}),
            ('Edge', 'Float', 0.12, {'min': 0, 'max': 1, 'label': 'Edge threshold'}),
            ('Outline', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Outline strength'}),
            ('Outliner', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Outline R'}),
            ('Outlineg', 'Float', 0.03, {'min': 0, 'max': 1, 'label': 'Outline G'}),
            ('Outlineb', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Outline B'}),
            ('Highlight', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Highlight (lighten)'}),
            ('Lightangle', 'Float', 135.0, {'min': -180, 'max': 180, 'label': 'Light from deg (0 = right)'}),
            ('Grid', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Grid lines darken'}),
        ]),
    ]


PANEL_PAGES = ['Pixelart', 'Edges']


def presets(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    dm = Lg['DITHER_METHODS']
    D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in pages(Lg) for n, s, d, o in pl)
    return [
        (1, 'sprite', dict(D, Pixelsize=6.0, Colour=1, Levels=6, Edge=0.12, Outline=0.85, Highlight=0.35)),
        (2, 'pico-8 toon', dict(D, Pixelsize=8.0, Colour=2, Machine=mk.index('pico8'), Dither=dm.index('bayer4'),
                                Ditheramt=0.4, Edge=0.1, Outline=1.0, Highlight=0.25, Seed=2)),
        (3, 'chunky clean', dict(D, Pixelsize=12.0, Sampling=1, Colour=0, Edge=0.08, Outline=0.6, Highlight=0.5,
                                 Grid=0.25, Seed=3)),
        (4, 'nes outline', dict(D, Pixelsize=4.0, Pixelaspect=8.0 / 7.0, Colour=2, Machine=mk.index('nes'),
                                Edgeby=1, Edge=0.2, Outline=0.9, Highlight=0.0, Seed=4)),
        (5, 'neon edge', dict(D, Pixelsize=5.0, Colour=1, Levels=4, Edge=0.1, Outline=1.0, Outliner=0.1,
                              Outlineg=0.9, Outlineb=1.0, Highlight=0.6, Lightangle=90.0, Seed=5)),
    ]


LOW = """// FX_retro pixelart low pass: one texel per virtual pixel (straight colour, alpha = coverage).
// in0 = picture, in1 = rack pal_top, in2 = rack bn_top. Output VW x VH rgba16float.
layout (local_size_x = 8, local_size_y = 8) in;
%LIB%
uniform vec4 uA;   // psx psy sampling colour
uniform vec4 uB;   // levels bank off, bank count, kind
uniform vec4 uC;   // dither method, dither amount, seed, -
uniform vec4 uD;   // contrast brightness saturation -
void main() {
    ivec2 v = ivec2(gl_GlobalInvocationID.xy);
    ivec2 vg = ivec2(uTDOutputInfo.res.zw);
    if (v.x >= vg.x || v.y >= vg.y) return;
    ivec2 res = textureSize(sTD2DInputs[0], 0);
    ivec2 ps = ivec2(max(int(uA.x + 0.5), 1), max(int(uA.y + 0.5), 1));
    ivec2 o = v * ps;
    vec4 s;
    if (uA.z < 0.5) s = texelFetch(sTD2DInputs[0], min(o + ps / 2, res - 1), 0);
    else {
        vec4 acc = vec4(0.0); int n = 0;
        for (int y = 0; y < 32; y++) {
            if (y >= ps.y || o.y + y >= res.y) break;
            for (int x = 0; x < 32; x++) {
                if (x >= ps.x || o.x + x >= res.x) break;
                acc += texelFetch(sTD2DInputs[0], o + ivec2(x, y), 0); n++;
            }
        }
        s = acc / float(max(n, 1));
    }
    vec3 c = preAdjust(straight(s), uD.x, uD.y, uD.z);
    int dm = int(uC.x + 0.5);
    float thr = ditherT(dm, v, uint(uC.z), 0);
    int cm = int(uA.w + 0.5);
    if (cm == 1) {
        float tb = strengthT(thr, uC.y);
        c = vec3(quantL(c.r, uB.x, tb), quantL(c.g, uB.x, tb), quantL(c.b, uB.x, tb));
    } else if (cm == 2 && uB.w < 0.5) {
        int off = int(uB.y + 0.5), np = max(int(uB.z + 0.5), 1);
        c = palRgb(off + pickPal(c, true, 1.0, off, np, dm > 0, thr, uC.y));
    }
    TDImageStoreOutput(0, ivec3(v, 0), vec4(c, s.a));
}
"""

FX = """// FX_retro pixelart fx pass: nearest upscale of `low` + outlines / highlights / grid (full res, premultiplied out).
// in0 = picture, in1 = low (VW x VH). = fx_retro_pixelart_logic.render
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount psx psy edgeby
uniform vec4 uB;   // edge outline highlight grid
uniform vec4 uC;   // outline rgb, -
uniform vec4 uD;   // light dir x y (whole-pixel step), -
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
ivec2 VG;
vec4 L(ivec2 v) { return texelFetch(sTD2DInputs[1], clamp(v, ivec2(0), VG - 1), 0); }
bool brighter(vec4 n, vec4 c) {                       // n is across an edge AND brighter than c
    float dl = lum(n.rgb) - lum(c.rgb);
    if (uA.w < 0.5) return dl > uB.x;
    return dl > 0.0 && length(n.rgb - c.rgb) > uB.x;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 res = textureSize(sTD2DInputs[0], 0);
    if (p.x >= res.x || p.y >= res.y) return;
    vec4 src = texelFetch(sTD2DInputs[0], p, 0);
    VG = textureSize(sTD2DInputs[1], 0);
    ivec2 ps = ivec2(max(int(uA.y + 0.5), 1), max(int(uA.z + 0.5), 1));
    ivec2 v = p / ps;
    vec4 c = L(v);
    vec3 o = c.rgb;
    bool edge = brighter(L(v + ivec2(1, 0)), c) || brighter(L(v - ivec2(1, 0)), c)
             || brighter(L(v + ivec2(0, 1)), c) || brighter(L(v - ivec2(0, 1)), c);
    if (edge) o = mix(o, uC.rgb, uB.y);
    else if (uB.z > 0.0) {
        ivec2 ld = ivec2(uD.xy);
        if (brighter(c, L(v - ld))) o = o + (1.0 - o) * uB.z;   // the far side of the light is darker: lit rim
    }
    if (uB.w > 0.0) {
        ivec2 q = p - v * ps;
        if (q.x == 0 || q.y == ps.y - 1) o *= 1.0 - uB.w;
    }
    vec3 fin = mix(src.a > 1e-5 ? src.rgb / src.a : src.rgb, o, uA.x);
    float a = mix(src.a, c.a, uA.x);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(fin * a, a));
}
"""


def shader_texts(lib):
    return {'low': LOW.replace('%LIB%', lib(pal_in=1, bn_in=2)), 'fx': FX}


def uniforms(H):
    P, LX = H['P'], H['LX']
    mach = "parent().par.Machine.eval()"
    W, Hh = "op('in1').width", "op('in1').height"
    grid = "%s.vgrid(%s, %s, %s, %s)" % (LX, W, Hh, P.format('Pixelsize'), P.format('Pixelaspect'))
    slot = "%s.bank_slot(%s, parent(2).op('pal_bank').numRows)" % (LX, mach)
    a = "math.radians(%s)" % P.format('Lightangle')
    low = [('uA', [grid + '[0]', grid + '[1]', 'parent().par.Sampling.menuIndex', 'parent().par.Colour.menuIndex']),
           ('uB', [P.format('Levels'), slot + '[0]', slot + '[1]', slot + '[2]']),
           ('uC', ['parent().par.Dither.menuIndex', P.format('Ditheramt'), P.format('Seed'), '0']),
           ('uD', [P.format('Contrast'), P.format('Brightness'), P.format('Saturation'), '0'])]
    fx = [('uA', [P.format('Amount'), grid + '[0]', grid + '[1]', 'parent().par.Edgeby.menuIndex']),
          ('uB', [P.format('Edge'), P.format('Outline'), P.format('Highlight'), P.format('Grid')]),
          ('uC', [P.format('Outliner'), P.format('Outlineg'), P.format('Outlineb'), '0']),
          ('uD', ['round(math.cos(%s))' % a, 'round(math.sin(%s))' % a, '0', '0'])]
    return low, fx, grid


def build(m, H, Lg):
    """in1 -> low (virtual res) -> fx (full res) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr, compute, LX = H['mk'], H['expr'], H['compute'], H['LX']
    in1 = mk(m, inTOP, 'in1')
    pal = H['select'](m, 'pal', '../pal_top')
    bn = H['select'](m, 'bn', '../bn_top')
    U1, U2, grid = uniforms(H)
    sh = shader_texts(lambda **k: H['glsl_lib'](Lg, **k))
    low = compute(m, 'low', sh['low'], [in1, pal, bn], grid + '[2]', grid + '[3]', fmt='rgba16float', uniforms=U1)
    low.comment = 'pixelart: one texel per virtual pixel (sample, pre-adjust, levels / palette + dither).'
    fx = compute(m, 'fx', sh['fx'], [in1, low], "me.inputs[0].width", "me.inputs[0].height", uniforms=U2)
    fx.comment = 'pixelart: nearest upscale + darker-side outline, light-side highlight, grid (premultiplied).'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '0 if parent().par.Amount.eval() <= 0 else 1')
    sel.comment = 'Amount 0 = in1 exactly (low / fx not pulled).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pal', 'bn'], 'body': 'Picture, rack palette bank, blue noise.'},
        {'title': '2 Pixel art', 'role': 'process', 'ops': ['low', 'low_compute', 'fx', 'fx_compute'],
         'body': 'low: virtual pixels. fx: upscale + outlines + highlights.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
