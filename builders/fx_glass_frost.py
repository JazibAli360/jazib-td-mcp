# fx_glass_frost - FX_glass module 'frost' (FX7a SX-03: frosted / reeded (ribbed) / fly-eye glass; ISF Frosted Glass
# (MIT) and gl-transitions FlyEye (MIT) as references, clean-room). Template: docs/builds/fx_glitch.md "Module template"
# (rack = builders/fx_glass.py). Doc: docs/builds/fx_glass.md. Mirror: builders/fx_glass_frost_logic.py.
# One compute pass (in1 + pre-blurred backdrop):
#   frosted : each pixel samples a hashed point within Radius px (re-rolled Animate times / s), mixed with the backdrop
#   reeded  : ribs Width px wide at Angle; inside a rib (s = -0.5..0.5) the picture is sampled at the rib centre +
#             s x Width x Mag (Mag 1 = clear, 0.3 = compressed, -1 = flipped), rim light at the rib edges, Blurmix
#             toward the backdrop at the rib edges
#   flyeye  : square or hex lens cells of Cell px; each shows the picture around its centre scaled by Mag (negative =
#             inverted), Gap (dark border), Vignette per cell
# Amount 0 = in1 exact (out_sel). ASCII only.
import os

MODULE = 'frost'
MODES = ['frosted', 'reeded', 'flyeye']

with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821 (HERE from the rack)
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']
BACKDROP_PAGE = ('Backdrop', [
    ('Backblur', 'Float', 24.0, {'min': 0, 'max': 200, 'label': 'Backdrop blur px (full-res px)'}),
    ('Backdown', 'Menu', 'half', {'names': ['full', 'half', 'quarter'], 'labels': ['Full', 'Half', 'Quarter'],
                                  'label': 'Backdrop resolution'}),
])                                                           # = fx_glass.BACKDROP_PAGE (the rack's _backdrop reads it)

PAGES = [
    ('Frost', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'frosted', {'names': MODES, 'labels': ['Frosted', 'Reeded (ribbed)', 'Fly-eye lens array']}),
        ('Radius', 'Float', 8.0, {'min': 0, 'max': 60, 'label': 'Frost radius px'}),
        ('Animate', 'Float', 0.0, {'min': 0, 'max': 60, 'label': 'Frost re-roll per s (0 = still)'}),
        ('Width', 'Float', 36.0, {'min': 2, 'max': 300, 'label': 'Rib width px'}),
        ('Angle', 'Float', 90.0, {'min': -180, 'max': 180, 'label': 'Rib angle deg (90 = vertical ribs)'}),
        ('Mag', 'Float', 0.35, {'min': -3, 'max': 3, 'label': 'Lens magnification (negative = flipped)'}),
        ('Cell', 'Float', 90.0, {'min': 8, 'max': 600, 'label': 'Fly-eye cell px'}),
        ('Shape', 'Menu', 'hex', {'names': ['square', 'hex'], 'labels': ['Square', 'Hex']}),
        ('Gap', 'Float', 0.06, {'min': 0, 'max': 0.5, 'label': 'Cell gap (share)'}),
        ('Vignette', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Cell vignette'}),
        ('Rimlight', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'Rim light'}),
        ('Blurmix', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Mix toward the blurred backdrop'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    BACKDROP_PAGE,
]
PANEL_PAGES = ['Frost', 'Backdrop']

_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl)


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'frosted', _p()),
    (2, 'shower glass', _p(Mode=0, Radius=22.0, Blurmix=0.7, Backblur=40.0, Seed=2)),
    (3, 'reeded', _p(Mode=1, Width=36.0, Mag=0.35, Rimlight=0.3, Blurmix=0.3, Seed=3)),
    (4, 'flipped ribs', _p(Mode=1, Width=80.0, Angle=0.0, Mag=-1.0, Rimlight=0.5, Blurmix=0.15, Seed=4)),
    (5, 'fly eye', _p(Mode=2, Cell=110.0, Mag=-0.6, Gap=0.05, Vignette=0.6, Blurmix=0.0, Seed=5)),
]

FX = """// frost fx (compute). in0 picture (bilinear), in1 pre-blurred backdrop.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode, frost radius px, frost tick
uniform vec4 uB;   // rib width px, rib angle deg, mag, blurmix
uniform vec4 uC;   // cell px, shape (0 square / 1 hex), gap, vignette
uniform vec4 uD;   // rim light, seed, -, -
""" + GLSL_LIB + """
vec2 fs;
vec3 S0(vec2 q) { return texture(sTD2DInputs[0], q / fs).rgb; }
vec3 S1(vec2 q) { return texture(sTD2DInputs[1], q / fs).rgb; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    fs = vec2(isz);
    vec2 pc = vec2(p) + 0.5;
    int mode = int(uA.y + 0.5);
    uint sd = uint(uD.y) * 7919u + uint(uA.w) * 2654435761u;
    vec3 col;
    if (mode == 0) {
        vec2 h = vec2(hsh(p, sd), hsh(p + ivec2(4099, 7), sd)) - 0.5;
        vec2 q = pc + 2.0 * h * uA.z;
        col = mix(S0(q), S1(q), uB.w);
    } else if (mode == 1) {
        float a = radians(uB.y);
        vec2 t = vec2(cos(a), sin(a));
        vec2 n = vec2(-t.y, t.x);
        float w = max(uB.x, 1.0);
        float v = dot(pc, n) / w;
        float s = fract(v) - 0.5;
        vec2 q = pc + n * (s * w * (uB.z - 1.0));
        float e = abs(2.0 * s);
        col = mix(S0(q), S1(q), uB.w * e * e);
        col += uD.x * pow(e, 6.0);
    } else {
        float cs = max(uC.x, 2.0);
        vec2 ctr;
        vec2 lp;
        float rr;
        if (uC.y < 0.5) {
            ctr = (floor(pc / cs) + 0.5) * cs;
            lp = (pc - ctr) / (0.5 * cs);
            rr = max(abs(lp.x), abs(lp.y));
        } else {
            vec2 r = vec2(1.0, 1.7320508) * cs;
            vec2 a1 = (floor(pc / r) + 0.5) * r;
            vec2 a2 = (floor((pc - 0.5 * r) / r) + 0.5) * r + 0.5 * r;
            ctr = dot(pc - a1, pc - a1) < dot(pc - a2, pc - a2) ? a1 : a2;
            lp = (pc - ctr) / (0.5 * cs);
            vec2 ap = abs(lp);
            rr = max(dot(ap, vec2(0.5, 0.8660254)), ap.x);
        }
        vec2 q = ctr + (pc - ctr) * uB.z;
        col = mix(S0(q), S1(q), uB.w);
        col *= 1.0 - uC.w * rr * rr * 0.5;
        col *= 1.0 - smoothstep(1.0 - uC.z * 2.0 - 0.03, 1.0 - uC.z * 2.0, rr);
        col += uD.x * pow(clamp(rr, 0.0, 1.0), 8.0);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(col, c.a), uA.x));
}
"""

SHADERS = {'fx': FX}
NIN = {'fx': 2}                          # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"


def uniforms():
    return {
        'fx': [('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Radius'),
                       'math.floor(absTime.seconds * %s) %% 65536' % P.format('Animate')]),
               ('uB', [P.format('Width'), P.format('Angle'), P.format('Mag'), P.format('Blurmix')]),
               ('uC', [P.format('Cell'), 'parent().par.Shape.menuIndex', P.format('Gap'), P.format('Vignette')]),
               ('uD', [P.format('Rimlight'), P.format('Seed'), '0', '0'])],
    }


def build(m, H):
    """in1 -> bd (backdrop) -> fx (in1, bd) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    bd = H['backdrop'](m, in1)
    fx = H['pas'](m, 'fx', FX, [in1, bd], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'frost: frosted / reeded / fly-eye glass.'
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact.'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'bd_down', 'bd']},
        {'title': '2 Glass', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'Frosted (hashed scatter), reeded (rib lenses), fly-eye (cell lenses).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
