# fx_retro_retroscreen - FX_retro module 'retroscreen' (FX2 AV-36 retro screen: console / computer framing; FX0 row
# 59). ONE compute pass at the input size: the picture fitted into a Screen rectangle (aspect full / 4:3 / 16:9 /
# 1:1 / 3:4, Fill fit or crop) on a virtual grid (Pixelsize, Pixelaspect, nearest), framed by a Border colour
# (C64-style), with optional raster bars (Amiga copper / C64: Bars count, Barheight, hue spread, Barspeed, drawn in the
# border, behind the screen picture where it is dark, or over everything), interlace flicker (every other frame the
# odd or even virtual lines dim by Flicker), screen Shake (px, re-rolled Shakerate times a second; bind it to a hit
# CHOP for a hit shake) and a colour Fade to black / white. Premultiplied out, Amount mix, out_sel: Amount 0 = in1.
# Mirror: builders/fx_retro_retroscreen_logic.py. ASCII only.

MODULE = 'retroscreen'
ASPECTS = ['full', 'a4x3', 'a16x9', 'a1x1', 'a3x4']
ZONES = ['border', 'behind', 'over']


def pages(Lg):
    return [
        ('Screen', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Aspect', 'Menu', 'a4x3', {'names': ASPECTS, 'labels': ['Full frame', '4:3', '16:9', '1:1', '3:4']}),
            ('Fill', 'Menu', 'fit', {'names': ['fit', 'crop'], 'labels': ['Fit picture', 'Crop picture']}),
            ('Margin', 'Float', 0.06, {'min': 0, 'max': 0.45, 'label': 'Border margin (share)'}),
            ('Pixelsize', 'Float', 4.0, {'min': 1, 'max': 32, 'label': 'Pixel size (px)'}),
            ('Pixelaspect', 'Float', 1.0, {'min': 0.5, 'max': 2, 'label': 'Pixel aspect (w / h)'}),
            ('Borderr', 'Float', 0.42, {'min': 0, 'max': 1, 'label': 'Border R'}),
            ('Borderg', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Border G'}),
            ('Borderb', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Border B'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
        ('Raster', [
            ('Bars', 'Int', 0, {'min': 0, 'max': 16, 'label': 'Raster bars'}),
            ('Barheight', 'Float', 40.0, {'min': 2, 'max': 400, 'label': 'Bar height px'}),
            ('Barspeed', 'Float', 0.4, {'min': -4, 'max': 4, 'label': 'Bar speed (cycles/s)'}),
            ('Barhue', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Bar hue'}),
            ('Barspread', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Hue spread per bar'}),
            ('Barzone', 'Menu', 'border', {'names': ZONES, 'labels': ['In the border', 'Behind (dark pixels)',
                                                                   'Over everything (add)']}),
            ('Flicker', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Interlace flicker'}),
            ('Shake', 'Float', 0.0, {'min': 0, 'max': 80, 'label': 'Shake px'}),
            ('Shakerate', 'Float', 20.0, {'min': 0, 'max': 60, 'label': 'Shake re-rolls / s'}),
            ('Fade', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Fade (- black, + white)'}),
        ]),
    ]


PANEL_PAGES = ['Screen', 'Raster']


def presets(Lg):
    D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in pages(Lg) for n, s, d, o in pl)
    return [
        (1, 'c64 frame', dict(D)),
        (2, 'amiga copper', dict(D, Bars=7, Barheight=36.0, Barspeed=0.35, Barhue=0.0, Barspread=0.12,
                                 Borderr=0.0, Borderg=0.0, Borderb=0.0, Barzone=0, Seed=2)),
        (3, 'arcade 3:4', dict(D, Aspect=4, Fill=1, Margin=0.02, Pixelsize=5.0, Borderr=0.0, Borderg=0.0,
                               Borderb=0.0, Flicker=0.25, Seed=3)),
        (4, 'demo bars', dict(D, Aspect=0, Margin=0.0, Pixelsize=3.0, Bars=10, Barheight=60.0, Barspeed=-0.6,
                              Barhue=0.55, Barspread=0.1, Barzone=1, Seed=4)),
        (5, 'hit shake', dict(D, Shake=12.0, Shakerate=24.0, Fade=0.15, Seed=5)),
    ]


FX = """// FX_retro retroscreen (compute, full res). in0 = picture. = fx_retro_retroscreen_logic.render
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount aspect fill margin
uniform vec4 uB;   // psx psy seed shake-epoch
uniform vec4 uC;   // border rgb, flicker
uniform vec4 uD;   // bars barheight barphase(cycles) barzone
uniform vec4 uE;   // barhue barspread shake fade
uniform vec4 uF;   // frame parity, -, -, -
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hs(uint a, uint b) { return float(lb32(a * 0x9e3779b9u ^ lb32(b)) >> 8) / 16777216.0; }
vec3 hue(float h) { return clamp(abs(fract(h + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 res = textureSize(sTD2DInputs[0], 0);
    if (p.x >= res.x || p.y >= res.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    vec2 SZ = vec2(res);
    int asp = int(uA.y + 0.5);
    float ar = asp == 1 ? 4.0 / 3.0 : (asp == 2 ? 16.0 / 9.0 : (asp == 3 ? 1.0 : (asp == 4 ? 0.75 : SZ.x / SZ.y)));
    vec2 avail = SZ * (1.0 - 2.0 * uA.w);
    vec2 scr = avail.x / avail.y > ar ? vec2(avail.y * ar, avail.y) : vec2(avail.x, avail.x / ar);
    scr = floor(scr + 0.5);
    uint sd = uint(uB.z) * 7919u;
    vec2 sh = (vec2(hs(uint(uB.w), sd + 1u), hs(uint(uB.w), sd + 2u)) - 0.5) * 2.0 * uE.z;
    vec2 o0 = floor(0.5 * (SZ - scr) + sh + 0.5);
    vec2 q = vec2(p) + 0.5 - o0;                                 // px inside the screen rect
    bool inside = q.x >= 0.0 && q.y >= 0.0 && q.x < scr.x && q.y < scr.y;
    vec3 col = uC.rgb;
    float lum = 0.0;
    if (inside) {
        vec2 ps = vec2(max(floor(uB.x + 0.5), 1.0), max(floor(uB.y + 0.5), 1.0));
        vec2 vc = (floor(q / ps) + 0.5) * ps;                    // virtual pixel centre (screen px)
        vec2 sc = SZ / scr;                                       // picture px per screen px: fit = all of it
        float k = uA.z > 0.5 ? min(sc.x, sc.y) : max(sc.x, sc.y);    // visible, crop = screen filled
        vec2 src = 0.5 * SZ + (vc - 0.5 * scr) * k;
        if (src.x >= 0.0 && src.y >= 0.0 && src.x < SZ.x && src.y < SZ.y) {
            vec4 s = texelFetch(sTD2DInputs[0], ivec2(floor(src)), 0);
            col = s.a > 1e-5 ? s.rgb / s.a : s.rgb;
        } else col = vec3(0.0);
        lum = dot(col, vec3(0.2126, 0.7152, 0.0722));
        int line = int(floor(q.y / ps.y));
        if (uC.w > 0.0 && ((line + int(uF.x)) & 1) == 1) col *= 1.0 - uC.w;
    }
    int nb = int(uD.x + 0.5);
    if (nb > 0) {
        float bar = 0.0; vec3 bc = vec3(0.0);
        for (int b = 0; b < 16; b++) {                            // copper bars: sine-moving, cosine profile
            if (b >= nb) break;
            float cy = (0.5 + 0.45 * sin(6.2831853 * (uD.z + float(b) * 0.61803))) * SZ.y;
            float d = abs(float(p.y) + 0.5 - cy) / max(uD.y * 0.5, 1.0);
            if (d < 1.0) { float w = 0.5 + 0.5 * cos(3.14159265 * d); if (w > bar) { bar = w; bc = hue(uE.x + uE.y * float(b)) * w; } }
        }
        int zone = int(uD.w + 0.5);
        if (zone == 0 && !inside) col = mix(col, bc, bar);
        else if (zone == 1 && (!inside || lum < 0.12)) col = mix(col, bc, bar * (inside ? 1.0 - lum / 0.12 : 1.0));
        else if (zone == 2) col += bc;
    }
    col = uE.w >= 0.0 ? mix(col, vec3(1.0), uE.w) : col * (1.0 + uE.w);
    vec3 srcc = c0.a > 1e-5 ? c0.rgb / c0.a : c0.rgb;
    vec3 fin = mix(srcc, col, uA.x);
    float a = mix(c0.a, 1.0, uA.x);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(fin * a, a));
}
"""


def shader_texts(lib):
    return {'fx': FX}


def uniforms(H):
    P, LX = H['P'], H['LX']
    W, Hh = "op('in1').width", "op('in1').height"
    grid = "%s.vgrid(%s, %s, %s, %s)" % (LX, W, Hh, P.format('Pixelsize'), P.format('Pixelaspect'))
    ep = "int(absTime.seconds * %s) if %s > 0 else 0" % (P.format('Shakerate'), P.format('Shakerate'))
    return [('uA', [P.format('Amount'), 'parent().par.Aspect.menuIndex', 'parent().par.Fill.menuIndex',
                    P.format('Margin')]),
            ('uB', [grid + '[0]', grid + '[1]', P.format('Seed'), ep]),
            ('uC', [P.format('Borderr'), P.format('Borderg'), P.format('Borderb'), P.format('Flicker')]),
            ('uD', [P.format('Bars'), P.format('Barheight'), '%s * absTime.seconds' % P.format('Barspeed'),
                    'parent().par.Barzone.menuIndex']),
            ('uE', [P.format('Barhue'), P.format('Barspread'), P.format('Shake'), P.format('Fade')]),
            ('uF', ['absTime.frame % 2', '0', '0', '0'])]


def build(m, H, Lg):
    """in1 -> fx (one pass) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr, compute = H['mk'], H['expr'], H['compute']
    in1 = mk(m, inTOP, 'in1')
    fx = compute(m, 'fx', FX, [in1], 'me.inputs[0].width', 'me.inputs[0].height', uniforms=uniforms(H))
    fx.comment = 'retroscreen: screen rect + virtual pixels + border, raster bars, flicker, shake, fade.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '0 if parent().par.Amount.eval() <= 0 else 1')
    sel.comment = 'Amount 0 = in1 exactly.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Screen', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One pass: screen fit, pixels, border, raster bars, flicker, shake, fade.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
