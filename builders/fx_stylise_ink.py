# fx_stylise_ink - FX_stylise module 'ink' (FX7a SX-07: XDoG pen-and-ink (Winnemoeller, Kyprianidis, Olsen 2012), cel
# / toon bands with ink lines, comic = toon + halftone dots; Gunnell Post-Processing "Comic" / "Edge Detection" (MIT)
# and three.js ToonShader as references, clean-room). Template: docs/builds/fx_glitch.md "Module template" (rack =
# builders/fx_stylise.py). Doc: docs/builds/fx_stylise.md. Numpy mirror: builders/fx_stylise_ink_logic.py.
# Passes (compute, separable Gaussians of luma, exact weights so the mirror matches):
#   blurh : r = G_sigma(luma), g = G_(k sigma)(luma) along x, b = luma (rgba16float)
#   blurv : the same along y on blurh -> two blurred lumas
#   fx    : XDoG S = (1 + p) G_s - p G_ks, E = 1 if S >= eps else 1 + tanh(phi (S - eps)); modes xdog (paper / picture /
#           palette by E), toon (soft luma bands x hue kept or palette, ink = 1 - E), comic (toon + halftone dots in
#           the shadows, rotated screen); Amount mix with in1
# Amount 0 = in1 exact (out_sel). <= 3 GLSL TOP inputs (T-88). ASCII only.
import os

MODULE = 'ink'
MODES = ['xdog', 'toon', 'comic']
FILLS = ['paper', 'picture', 'palette']
RMAX = 48                                   # max Gaussian radius px (constant loop bound, T-124)

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']

PAGES = [
    ('Ink', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'xdog', {'names': MODES, 'labels': ['XDoG pen and ink', 'Toon (cel bands + ink)',
                                                             'Comic (toon + halftone)']}),
        ('Sigma', 'Float', 1.2, {'min': 0.3, 'max': 8, 'label': 'Line scale (sigma px)'}),
        ('K', 'Float', 1.6, {'min': 1.05, 'max': 4, 'label': 'Sigma ratio k'}),
        ('Sharpen', 'Float', 18.0, {'min': 0, 'max': 80, 'label': 'Sharpen p'}),
        ('Eps', 'Float', 0.35, {'min': -0.5, 'max': 1.5, 'label': 'Threshold eps'}),
        ('Phi', 'Float', 25.0, {'min': 0.5, 'max': 200, 'label': 'Softness phi (high = hard)'}),
        ('Inkamount', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Ink amount'}),
        ('Fill', 'Menu', 'paper', {'names': FILLS, 'labels': ['Paper', 'Picture', 'Palette by E']}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (dot jitter)'}),
    ]),
    ('Toon', [
        ('Bands', 'Int', 4, {'min': 2, 'max': 12, 'label': 'Bands'}),
        ('Bandsoft', 'Float', 0.08, {'min': 0, 'max': 0.5, 'label': 'Band edge softness'}),
        ('Saturation', 'Float', 1.25, {'min': 0, 'max': 3, 'label': 'Saturation'}),
        ('Toonpal', 'Toggle', False, {'label': 'Bands from the palette'}),
        ('Dotsize', 'Float', 7.0, {'min': 2, 'max': 40, 'label': 'Halftone cell px'}),
        ('Dotangle', 'Float', 45.0, {'min': 0, 'max': 90, 'label': 'Screen angle deg'}),
        ('Dotthr', 'Float', 0.45, {'min': 0, 'max': 1, 'label': 'Dots below this luma'}),
        ('Dotjitter', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Dot jitter'}),
    ]),
    ('Colour', [
        ('Inkr', 'Float', 0.03, {'min': 0, 'max': 1, 'label': 'Ink R'}),
        ('Inkg', 'Float', 0.02, {'min': 0, 'max': 1, 'label': 'Ink G'}),
        ('Inkb', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Ink B'}),
        ('Paperr', 'Float', 0.97, {'min': 0, 'max': 1, 'label': 'Paper R'}),
        ('Paperg', 'Float', 0.95, {'min': 0, 'max': 1, 'label': 'Paper G'}),
        ('Paperb', 'Float', 0.90, {'min': 0, 'max': 1, 'label': 'Paper B'}),
    ]),
    pal_page('neon_trio', 'gradient'),  # noqa: F821
]
PANEL_PAGES = ['Ink', 'Toon', 'Colour', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
for _k in ('Palreverse', 'Toonpal'):
    _D[_k] = int(_D[_k])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'pen and ink', _p(Seed=1)),
    (2, 'woodcut', _p(Sigma=2.2, Sharpen=30.0, Eps=0.55, Phi=60.0, Seed=2)),
    (3, 'cel shade', _p(Mode=1, Bands=4, Sigma=1.4, Eps=0.3, Phi=40.0, Saturation=1.4, Seed=3)),
    (4, 'comic', _p(Mode=2, Bands=3, Sigma=1.6, Eps=0.3, Phi=40.0, Saturation=1.6, Dotsize=8.0, Dotthr=0.5, Seed=4)),
    (5, 'neon pastel', _p(Mode=0, Fill=2, Sigma=1.0, Eps=0.5, Phi=12.0, Inkamount=0.8, Inkr=0.0, Inkg=0.0, Inkb=0.0,
                          Palsource=PAL_SOURCE_NAMES.index('neon_trio'), Seed=5)),  # noqa: F821
]

BLUR = """// ink blur (compute, rgba16float): two Gaussians of luma along DIR (sigma s, k s), weights exp(-i^2 / 2 s^2)
// (incremental, float32) normalised, radius R = min(ceil(3 k s), RMAX); taps clamp at the frame edge. Pass h reads in1 (luma), v reads h.r/g.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uG;   // sigma, k, radius, direction (0 x / 1 y)
""" + GLSL_LIB + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    bool vert = uG.w > 0.5;
    ivec2 dv = vert ? ivec2(0, 1) : ivec2(1, 0);
    int R = int(uG.z + 0.5);
    float s1 = max(uG.x, 1e-3), s2 = max(uG.x * uG.y, 1e-3);
    float a1 = 0.0, a2 = 0.0, w1 = 0.0, w2 = 0.0;
    // incremental Gaussian (GPU Gems 3 ch. 40) from the centre out: w(i) = exp(-i^2 / 2s^2) by two multiplies per
    // tap pair, no exp in the loop; tiny weights underflow to 0 harmlessly
    float q1 = exp(-1.0 / (s1 * s1)), q2 = exp(-1.0 / (s2 * s2));
    float e1 = 1.0, e2 = 1.0;
    float r1 = exp(-0.5 / (s1 * s1)), r2 = exp(-0.5 / (s2 * s2));
    for (int i = 0; i <= RMAX; i++) {
        if (i > R) break;
        vec4 t = texelFetch(sTD2DInputs[0], clamp(p + dv * i, ivec2(0), isz - 1), 0);
        float l1 = vert ? t.r : luma(t.rgb);
        float l2 = vert ? t.g : l1;
        a1 += e1 * l1; w1 += e1;
        a2 += e2 * l2; w2 += e2;
        if (i > 0) {
            vec4 u = texelFetch(sTD2DInputs[0], clamp(p - dv * i, ivec2(0), isz - 1), 0);
            float m1 = vert ? u.r : luma(u.rgb);
            float m2 = vert ? u.g : m1;
            a1 += e1 * m1; w1 += e1;
            a2 += e2 * m2; w2 += e2;
        }
        e1 *= r1; r1 *= q1;
        e2 *= r2; r2 *= q2;
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(a1 / w1, a2 / w2, 0.0, 1.0));
}
""".replace('RMAX', str(RMAX))

FX = """// ink fx (compute). in0 in1 picture, in1 blurred lumas (r G_s, g G_ks). XDoG + toon / comic + fill, Amount mix.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode, fill, ink amount
uniform vec4 uB;   // sharpen p, eps, phi, seed
uniform vec4 uC;   // bands, bandsoft, saturation, toonpal
uniform vec4 uD;   // dotsize, dot angle deg, dot thr, dot jitter
uniform vec4 uE;   // ink rgb, -
uniform vec4 uF;   // paper rgb, -
""" + GLSL_LIB + PAL_GLSL + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    vec4 g = texelFetch(sTD2DInputs[1], p, 0);
    float S = (1.0 + uB.x) * g.r - uB.x * g.g;
    float E = S >= uB.y ? 1.0 : 1.0 + tanh(uB.z * (S - uB.y));
    float ink = clamp((1.0 - E) * uA.w, 0.0, 1.0);
    int mode = int(uA.y + 0.5);
    int fm = int(uA.z + 0.5);
    vec3 col;
    if (mode == 0) {
        col = fm == 0 ? uF.rgb : (fm == 1 ? c.rgb : pxPal(E));
    } else {
        float L = luma(c.rgb);
        float n = max(uC.x, 2.0);
        float x = L * n;
        float f = fract(x);
        float lq = (floor(x) + smoothstep(0.5 - uC.y, 0.5 + uC.y, f)) / n;
        if (uC.w > 0.5) col = pxPal(lq);
        else {
            vec3 sat = mix(vec3(L), c.rgb, uC.z);
            col = sat * (lq / max(L, 1e-3));
        }
        if (mode == 2 && L < uD.z) {                                              // halftone in the shadows
            float a = radians(uD.y);
            vec2 q = mat2(cos(a), sin(a), -sin(a), cos(a)) * (vec2(p) + 0.5);
            float cs = max(uD.x, 1.0);
            vec2 cell = floor(q / cs);
            vec2 jit = (vec2(hsh(ivec2(cell), uint(uB.w)), hsh(ivec2(cell) + ivec2(7, 3), uint(uB.w))) - 0.5) * uD.w;
            vec2 fq = q / cs - cell - 0.5 - jit;
            float r = sqrt(clamp((uD.z - L) / max(uD.z, 1e-3), 0.0, 1.0)) * 0.5;
            float dot_ = 1.0 - smoothstep(r - 0.06, r + 0.06, length(fq));
            ink = max(ink, dot_ * uA.w);
        }
    }
    vec3 o3 = mix(col, uE.rgb, clamp(ink, 0.0, 1.0));
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(o3, c.a), uA.x));
}
"""

SHADERS = {'blurh': BLUR, 'blurv': BLUR, 'fx': FX}
NIN = {'blurh': 1, 'blurv': 1, 'fx': 2}             # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"
RAD = "min(%d, int(math.ceil(3 * %s * %s)))" % (RMAX, P.format('Sigma'), P.format('K'))


def uniforms():
    return {
        'blurh': [('uG', [P.format('Sigma'), P.format('K'), RAD, '0'])],
        'blurv': [('uG', [P.format('Sigma'), P.format('K'), RAD, '1'])],
        'fx': [('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', 'parent().par.Fill.menuIndex',
                       P.format('Inkamount')]),
               ('uB', [P.format('Sharpen'), P.format('Eps'), P.format('Phi'), P.format('Seed')]),
               ('uC', [P.format('Bands'), P.format('Bandsoft'), P.format('Saturation'), 'float(%s)' % P.format('Toonpal')]),
               ('uD', [P.format('Dotsize'), P.format('Dotangle'), P.format('Dotthr'), P.format('Dotjitter')]),
               ('uE', [P.format('Inkr'), P.format('Inkg'), P.format('Inkb'), '0']),
               ('uF', [P.format('Paperr'), P.format('Paperg'), P.format('Paperb'), '0'])],
    }


def build(m, H):
    """in1 -> blurh -> blurv -> fx (+ in1) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    bh = H['pas'](m, 'blurh', BLUR, [in1], 'me.inputs[0].width', 'me.inputs[0].height', 'rgba16float')
    H['uniforms'](bh, U['blurh'])
    bh.comment = 'Two Gaussians of luma along x (sigma, k sigma), exact weights.'
    bv = H['pas'](m, 'blurv', BLUR, [bh], 'me.inputs[0].width', 'me.inputs[0].height', 'rgba16float')
    H['uniforms'](bv, U['blurv'])
    bv.comment = 'The same along y: r = G_sigma(luma), g = G_k sigma(luma).'
    fx = H['pas'](m, 'fx', FX, [in1, bv], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'ink: XDoG lines + toon bands / comic halftone + fill; Amount mix.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (blurs / fx not pulled).'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Blur', 'role': 'process', 'ops': ['blurh', 'blurh_compute', 'blurv', 'blurv_compute'],
         'body': 'Separable Gaussians of luma at sigma and k sigma (DoG).'},
        {'title': '3 Ink', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'XDoG ink, toon bands, comic halftone, fill.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
