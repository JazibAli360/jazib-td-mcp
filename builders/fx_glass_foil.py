# fx_glass_foil - FX_glass module 'foil' (FX7c 7C-22 thin-film holo foil: oil-slick / soap-bubble / holographic foil
# colours that shift with angle; footage luma = film thickness; two-beam thin-film interference after three.js
# evalIridescence / Belcour-Barla 2017 in spirit, clean-room). Template: docs/builds/fx_glitch.md "Module template"
# (rack = builders/fx_glass.py). Doc: docs/builds/fx_glass.md. Mirror: builders/fx_glass_foil_logic.py.
# One compute pass: smoothed luma Lb (5 bilinear taps at Smooth px) -> thickness d = Base + Range x (Lb + Noise x
# (value noise - 0.5)) nm; pseudo-normal from the luma gradient x Tilt -> view angle, Snell into the film (Filmior) ->
# per channel I = 0.5 + 0.5 cos(4 pi n d cos(theta_t) / lambda + Shift) (lambda 650 / 532 / 450 nm); or Mode cosine
# (IQ palette of the same phase) / palette (W1-B, t = d / (Base + Range)); Saturation, Keepluma; blended with the
# picture (replace / multiply / screen / overlay / add) by Amount. ASCII only.
import os

MODULE = 'foil'
MODES = ['thinfilm', 'cosine', 'palette']
BLENDS = ['replace', 'multiply', 'screen', 'overlay', 'add']

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']

PAGES = [
    ('Foil', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'thinfilm', {'names': MODES, 'labels': ['Thin-film interference', 'Cosine rainbow',
                                                                 'Palette (W1-B)']}),
        ('Blend', 'Menu', 'overlay', {'names': BLENDS, 'labels': ['Replace', 'Multiply', 'Screen', 'Overlay', 'Add']}),
        ('Base', 'Float', 250.0, {'min': 0, 'max': 1500, 'label': 'Base thickness nm'}),
        ('Range', 'Float', 700.0, {'min': 0, 'max': 3000, 'label': 'Thickness range nm (x luma)'}),
        ('Filmior', 'Float', 1.4, {'min': 1, 'max': 2.5, 'label': 'Film IOR'}),
        ('Tilt', 'Float', 3.0, {'min': 0, 'max': 20, 'label': 'Tilt (angle from the luma relief)'}),
        ('Smooth', 'Float', 3.0, {'min': 0, 'max': 30, 'label': 'Smoothing px'}),
        ('Noise', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'Thickness noise'}),
        ('Noisescale', 'Float', 220.0, {'min': 4, 'max': 1000, 'label': 'Noise scale px'}),
        ('Noisespeed', 'Float', 0.15, {'min': 0, 'max': 4, 'label': 'Noise drift'}),
        ('Shift', 'Float', 0.0, {'min': 0, 'max': 6.2832, 'label': 'Phase shift (bind an LFO / beat)'}),
        ('Speed', 'Float', 0.4, {'min': -6, 'max': 6, 'label': 'Phase speed rad / s'}),
        ('Saturation', 'Float', 1.2, {'min': 0, 'max': 3, 'label': 'Saturation'}),
        ('Keepluma', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Keep picture luma'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    pal_page('rainbow', 'cycle'),  # noqa: F821
]
PANEL_PAGES = ['Foil', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
_D['Palreverse'] = int(_D['Palreverse'])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'holo foil', _p(Seed=1)),
    (2, 'oil slick', _p(Blend=0, Base=150.0, Range=500.0, Filmior=1.5, Noise=0.8, Noisescale=120.0, Keepluma=0.6,
                        Seed=2)),
    (3, 'soap bubble', _p(Blend=2, Base=400.0, Range=900.0, Filmior=1.33, Tilt=6.0, Saturation=1.5, Keepluma=0.0,
                          Seed=3)),
    (4, 'rainbow chrome', _p(Mode=1, Blend=3, Range=1200.0, Speed=1.0, Saturation=1.0, Seed=4)),
    (5, 'palette sheen', _p(Mode=2, Blend=1, Range=900.0, Speed=0.6, Keepluma=0.2, Seed=5)),
]

FX = """// foil fx (compute). in0 in1. Thin-film colour from luma-driven thickness + luma-relief view angle.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode, blend, phase (shift + speed t)
uniform vec4 uB;   // base nm, range nm, film ior, tilt
uniform vec4 uC;   // smooth px, noise, noise scale px, noise time
uniform vec4 uD;   // saturation, keep luma, seed, -
""" + GLSL_LIB + PAL_GLSL + """
vec2 fs;
float Lt(vec2 q) { return luma(texture(sTD2DInputs[0], q / fs).rgb); }
vec3 blendf(vec3 a, vec3 b, int m) {
    if (m == 1) return a * b;
    if (m == 2) return 1.0 - (1.0 - a) * (1.0 - b);
    if (m == 3) return mix(2.0 * a * b, 1.0 - 2.0 * (1.0 - a) * (1.0 - b), step(0.5, a));
    if (m == 4) return a + b;
    return b;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    fs = vec2(isz);
    vec2 pc = vec2(p) + 0.5;
    float s = max(uC.x, 0.5);
    float l0 = Lt(pc), lxp = Lt(pc + vec2(s, 0.0)), lxm = Lt(pc - vec2(s, 0.0));
    float lyp = Lt(pc + vec2(0.0, s)), lym = Lt(pc - vec2(0.0, s));
    float lb = (l0 + lxp + lxm + lyp + lym) * 0.2;
    vec2 g = vec2(lxp - lxm, lyp - lym) / (2.0 * s);
    float nz = vnoise(pc / max(uC.z, 1.0) + vec2(uC.w, 0.71 * uC.w), uint(uD.z));
    float d = uB.x + uB.y * (lb + uC.y * (nz - 0.5));
    vec3 n = normalize(vec3(-g * uB.w * s, 1.0));
    float sint = sqrt(max(1.0 - n.z * n.z, 0.0)) / max(uB.z, 1.0);
    float cost = sqrt(max(1.0 - sint * sint, 0.0));
    int mode = int(uA.y + 0.5);
    vec3 f;
    if (mode == 0) {
        vec3 ph = 12.566371 * uB.z * d * cost / vec3(650.0, 532.0, 450.0) + uA.w;
        f = 0.5 + 0.5 * cos(ph);
    } else if (mode == 1) {
        float t = d * cost / 600.0 + uA.w / 6.2831853;
        f = 0.5 + 0.5 * cos(6.2831853 * (t + vec3(0.0, 0.33, 0.67)));
    } else {
        f = pxPal(d * cost / max(uB.x + uB.y, 1.0) + uA.w / 6.2831853);
    }
    float fl = luma(f);
    f = mix(vec3(fl), f, uD.x);
    f = mix(f, f * (luma(c.rgb) / max(fl, 1e-3)), uD.y);
    vec3 o = blendf(c.rgb, f, int(uA.z + 0.5));
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(o, c.a), uA.x));
}
"""

SHADERS = {'fx': FX}
NIN = {'fx': 1}                          # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"


def uniforms():
    return {
        'fx': [('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', 'parent().par.Blend.menuIndex',
                       '%s + %s * absTime.seconds' % (P.format('Shift'), P.format('Speed'))]),
               ('uB', [P.format('Base'), P.format('Range'), P.format('Filmior'), P.format('Tilt')]),
               ('uC', [P.format('Smooth'), P.format('Noise'), P.format('Noisescale'),
                       '%s * absTime.seconds' % P.format('Noisespeed')]),
               ('uD', [P.format('Saturation'), P.format('Keepluma'), P.format('Seed'), '0'])],
    }


def build(m, H):
    """in1 -> fx -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    fx = H['pas'](m, 'fx', FX, [in1], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'foil: thin-film interference colour from luma thickness + relief angle; blend with the picture.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact.'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Foil', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'Thickness from luma + noise, angle from relief, interference colour, blend.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
