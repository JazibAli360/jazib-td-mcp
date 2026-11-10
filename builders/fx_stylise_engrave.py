# fx_stylise_engrave - FX_stylise module 'engrave' (FX7c 7C-04: engraving / banknote line screen: parallel lines whose
# width follows darkness and that bend around forms; Sapphire Etching as the look reference, clean-room). Template:
# docs/builds/fx_glitch.md "Module template" (rack = builders/fx_stylise.py). Doc: docs/builds/fx_stylise.md. Mirror:
# builders/fx_stylise_engrave_logic.py.
# One compute pass: smoothed luma Lb (5 bilinear taps at Smooth px) -> line coordinate v = position across the lines
# (Angle) + Bend x Spacing x Lb (lines warp along tone) + Wave x sin(along x Wavefreq + phase) (guilloche) -> line
# half-width = Width x (1 - L)^Gamma x Spacing / 2 -> antialiased ink; a Cross set at Angle + Crossangle where L <
# Cross (deep shadows); ink over paper / picture / palette. Amount 0 = in1 exact (out_sel). ASCII only.
import os

MODULE = 'engrave'
FILLS = ['paper', 'picture', 'palette']

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']

PAGES = [
    ('Engrave', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Spacing', 'Float', 7.0, {'min': 2, 'max': 40, 'label': 'Line spacing px'}),
        ('Angle', 'Float', 30.0, {'min': -180, 'max': 180, 'label': 'Line angle deg'}),
        ('Bend', 'Float', 1.5, {'min': -6, 'max': 6, 'label': 'Bend with tone (x spacing)'}),
        ('Smooth', 'Float', 4.0, {'min': 0, 'max': 30, 'label': 'Tone smoothing px'}),
        ('Width', 'Float', 0.9, {'min': 0, 'max': 1.5, 'label': 'Max line width (share of spacing)'}),
        ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 4, 'label': 'Tone gamma'}),
        ('Aa', 'Float', 0.75, {'min': 0.1, 'max': 4, 'label': 'Antialias px'}),
        ('Cross', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Cross lines below luma'}),
        ('Crossangle', 'Float', 90.0, {'min': -180, 'max': 180, 'label': 'Cross angle (relative) deg'}),
        ('Wave', 'Float', 0.0, {'min': 0, 'max': 40, 'label': 'Guilloche wave px'}),
        ('Wavefreq', 'Float', 0.02, {'min': 0, 'max': 0.2, 'label': 'Wave frequency (cycles / px)'}),
        ('Speed', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Line drift (spacings / s)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (wave phase)'}),
    ]),
    ('Colour', [
        ('Fill', 'Menu', 'paper', {'names': FILLS, 'labels': ['Paper', 'Picture under the ink', 'Palette by luma']}),
        ('Inkcolour', 'Menu', 'ink', {'names': ['ink', 'picture'], 'labels': ['Ink colour', 'Picture colour']}),
        ('Inkr', 'Float', 0.06, {'min': 0, 'max': 1, 'label': 'Ink R'}),
        ('Inkg', 'Float', 0.12, {'min': 0, 'max': 1, 'label': 'Ink G'}),
        ('Inkb', 'Float', 0.10, {'min': 0, 'max': 1, 'label': 'Ink B'}),
        ('Paperr', 'Float', 0.95, {'min': 0, 'max': 1, 'label': 'Paper R'}),
        ('Paperg', 'Float', 0.93, {'min': 0, 'max': 1, 'label': 'Paper G'}),
        ('Paperb', 'Float', 0.84, {'min': 0, 'max': 1, 'label': 'Paper B'}),
    ]),
    pal_page('neon_trio', 'gradient'),  # noqa: F821
]
PANEL_PAGES = ['Engrave', 'Colour', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
_D['Palreverse'] = int(_D['Palreverse'])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'etching', _p(Seed=1)),
    (2, 'banknote', _p(Spacing=5.0, Angle=0.0, Bend=2.5, Wave=6.0, Wavefreq=0.015, Cross=0.3, Inkr=0.1, Inkg=0.25,
                       Inkb=0.15, Seed=2)),
    (3, 'woodcut lines', _p(Spacing=12.0, Angle=-20.0, Bend=3.0, Width=1.1, Gamma=0.7, Cross=0.0, Seed=3)),
    (4, 'neon scan', _p(Spacing=6.0, Angle=90.0, Bend=1.0, Speed=0.5, Fill=2, Inkcolour=0, Inkr=0.0, Inkg=0.0, Inkb=0.0,
                        Cross=0.0, Palsource=PAL_SOURCE_NAMES.index('neon_trio'), Seed=4)),  # noqa: F821
    (5, 'colour lines', _p(Spacing=8.0, Angle=45.0, Inkcolour=1, Fill=0, Paperr=0.02, Paperg=0.02, Paperb=0.03,
                           Gamma=0.6, Width=1.0, Cross=0.0, Seed=5)),
]

FX = """// engrave fx (compute). in0 in1. Line screen whose width follows darkness and whose lines bend with tone.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, spacing px, angle deg, bend
uniform vec4 uB;   // smooth px, width, gamma, aa px
uniform vec4 uC;   // cross thr, cross angle deg, wave px, wave freq
uniform vec4 uD;   // drift (spacings), seed, fill, ink colour mode
uniform vec4 uE;   // ink rgb, -
uniform vec4 uF;   // paper rgb, -
""" + GLSL_LIB + PAL_GLSL + """
vec2 fs;
float Lt(vec2 q) { return luma(texture(sTD2DInputs[0], q / fs).rgb); }
float lines(vec2 pc, float ang, float sp, float lb, float hw) {
    float a = radians(ang);
    vec2 n = vec2(-sin(a), cos(a));
    vec2 t = vec2(cos(a), sin(a));
    float along = dot(pc, t);
    float v = dot(pc, n) + uA.w * sp * lb + uC.z * sin(6.2831853 * (along * uC.w + 0.137 * uD.y)) + uD.x * sp;
    float f = fract(v / sp);
    float dist = abs(f - 0.5) * sp;
    return (1.0 - smoothstep(hw - 0.5 * uB.w, hw + 0.5 * uB.w, dist)) * clamp(2.0 * hw / max(uB.w, 1e-3), 0.0, 1.0);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    fs = vec2(isz);
    vec2 pc = vec2(p) + 0.5;
    float s = uB.x;
    float lb = (Lt(pc) + Lt(pc + vec2(s, 0.0)) + Lt(pc - vec2(s, 0.0)) + Lt(pc + vec2(0.0, s)) + Lt(pc - vec2(0.0, s))) * 0.2;
    float sp = max(uA.y, 1.0);
    float dk = pow(clamp(1.0 - lb, 0.0, 1.0), uB.z);
    float ink = lines(pc, uA.z, sp, lb, 0.5 * uB.y * dk * sp);
    if (lb < uC.x) {
        float dk2 = clamp((uC.x - lb) / max(uC.x, 1e-3), 0.0, 1.0);
        ink = max(ink, lines(pc, uA.z + uC.y, sp, lb, 0.5 * uB.y * dk2 * sp));
    }
    int fm = int(uD.z + 0.5);
    vec3 base = fm == 0 ? uF.rgb : (fm == 1 ? c.rgb : pxPal(lb));
    vec3 ic = uD.w > 0.5 ? c.rgb : uE.rgb;
    vec3 o = mix(base, ic, ink);
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(o, c.a), uA.x));
}
"""

SHADERS = {'fx': FX}
NIN = {'fx': 1}                          # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"


def uniforms():
    return {
        'fx': [('uA', [P.format('Amount'), P.format('Spacing'), P.format('Angle'), P.format('Bend')]),
               ('uB', [P.format('Smooth'), P.format('Width'), P.format('Gamma'), P.format('Aa')]),
               ('uC', [P.format('Cross'), P.format('Crossangle'), P.format('Wave'), P.format('Wavefreq')]),
               ('uD', ['%s * absTime.seconds' % P.format('Speed'), P.format('Seed'), 'parent().par.Fill.menuIndex',
                       'parent().par.Inkcolour.menuIndex']),
               ('uE', [P.format('Inkr'), P.format('Inkg'), P.format('Inkb'), '0']),
               ('uF', [P.format('Paperr'), P.format('Paperg'), P.format('Paperb'), '0'])],
    }


def build(m, H):
    """in1 -> fx -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    fx = H['pas'](m, 'fx', FX, [in1], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'engrave: tone-bent line screen, width by darkness, cross lines in deep shadow.'
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
        {'title': '2 Engrave', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'Line screen: width by darkness, bend by tone, cross set, guilloche wave.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
