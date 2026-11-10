# fx_stylise_clean - FX_stylise module 'clean' (FX7a SX-05: edge-preserving clean / beauty smoothing + median
# despeckle for IMAG; also cleans webcam noise before datamosh / pixel sort). References (clean-room): lygia
# smartDeNoise (BSD-2) / bilateral, ISF Median (McGuire-Whitson network, MIT). Template: docs/builds/fx_glitch.md
# "Module template" (rack = builders/fx_stylise.py). Doc: docs/builds/fx_stylise.md. Mirror:
# builders/fx_stylise_clean_logic.py.
# Passes (compute):
#   med  : 3x3 median per channel (min / max exchange network) (Median on; else msrc = in1, med not pulled)
#   bilh : bilateral along x: w = exp(-(i^2 / 2 Ss^2 + |c_i - c_0|^2 / 2 Sr^2)), radius Radius (<= 24), rgb or luma
#          range (Rangemode)
#   bilv : the same along y on bilh (separable approximation), then Amount mix with in1 and Detail (unsharp: adds
#          back Detail x (source - smoothed) so eyes / lashes stay crisp)
# Amount 0 = in1 exact (out_sel). <= 3 GLSL TOP inputs (T-88). ASCII only.
import os

MODULE = 'clean'
RMAX = 24

with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821 (HERE from the rack)
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']

PAGES = [
    ('Clean', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Median', 'Toggle', True, {'label': 'Median 3x3 despeckle first'}),
        ('Radius', 'Int', 6, {'min': 0, 'max': 24, 'label': 'Radius px (0 = median only)'}),
        ('Sigma', 'Float', 3.0, {'min': 0.5, 'max': 16, 'label': 'Spatial sigma px'}),
        ('Edge', 'Float', 0.08, {'min': 0.005, 'max': 1, 'label': 'Edge (range sigma: low keeps edges)'}),
        ('Rangemode', 'Menu', 'rgb', {'names': ['rgb', 'luma'], 'labels': ['RGB distance', 'Luma only']}),
        ('Detail', 'Float', 0.0, {'min': -1, 'max': 2, 'label': 'Detail (unsharp back)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (unused: deterministic)'}),
    ]),
]
PANEL_PAGES = ['Clean']

_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl)
_D['Median'] = int(_D['Median'])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'beauty', _p(Median=0, Radius=6, Sigma=3.0, Edge=0.08, Detail=0.15)),
    (2, 'despeckle', _p(Median=1, Radius=2, Sigma=1.0, Edge=0.05)),
    (3, 'flat cartoon', _p(Median=1, Radius=12, Sigma=6.0, Edge=0.15)),
    (4, 'pre-glitch', _p(Median=1, Radius=3, Sigma=1.5, Edge=0.04)),
    (5, 'plastic', _p(Median=0, Radius=20, Sigma=10.0, Edge=0.3, Rangemode=1, Detail=-0.2)),
]

MED = """// clean med (compute): 3x3 median per channel (exchange network of min / max; ISF Median idea, clean-room).
layout (local_size_x = 8, local_size_y = 8) in;
#define S2(a, b) { vec4 t_ = min(a, b); b = max(a, b); a = t_; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 v[9];
    for (int j = 0; j < 3; j++) for (int i = 0; i < 3; i++)
        v[j * 3 + i] = texelFetch(sTD2DInputs[0], clamp(p + ivec2(i - 1, j - 1), ivec2(0), isz - 1), 0);
    S2(v[1], v[2]); S2(v[4], v[5]); S2(v[7], v[8]); S2(v[0], v[1]); S2(v[3], v[4]); S2(v[6], v[7]);
    S2(v[1], v[2]); S2(v[4], v[5]); S2(v[7], v[8]); S2(v[0], v[3]); S2(v[5], v[8]); S2(v[4], v[7]);
    S2(v[3], v[6]); S2(v[1], v[4]); S2(v[2], v[5]); S2(v[4], v[7]); S2(v[4], v[2]); S2(v[6], v[4]);
    S2(v[4], v[2]);
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(v[4].rgb, c.a));
}
"""

BIL = """// clean bilateral along DIR (compute). in0 source; w = exp(-(i^2 / 2 Ss^2 + |c_i - c_0|^2 / 2 Sr^2)), radius R
// (runtime break under the constant bound RMAX); rgb or luma range. Pass v also mixes with in1 (Amount) and adds
// Detail x (in1 - smooth).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uB;   // radius, sigma spatial, edge (range sigma), direction (0 x / 1 y)
uniform vec4 uM;   // amount, detail, range mode (0 rgb / 1 luma), -
""" + GLSL_LIB + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    ivec2 dv = uB.w > 0.5 ? ivec2(0, 1) : ivec2(1, 0);
    int R = int(uB.x + 0.5);
    float is2 = 1.0 / (2.0 * max(uB.y * uB.y, 1e-6));
    float ir2 = 1.0 / (2.0 * max(uB.z * uB.z, 1e-8));
    bool lm = uM.z > 0.5;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    vec3 acc = c0.rgb;
    float ws = 1.0;
    for (int i = 1; i <= RMAX; i++) {
        if (i > R) break;
        vec3 a = texelFetch(sTD2DInputs[0], clamp(p + dv * i, ivec2(0), isz - 1), 0).rgb;
        vec3 b = texelFetch(sTD2DInputs[0], clamp(p - dv * i, ivec2(0), isz - 1), 0).rgb;
        float sp = float(i * i) * is2;
        vec3 da = a - c0.rgb, db = b - c0.rgb;
        float ra = lm ? luma(da) * luma(da) : dot(da, da);
        float rb = lm ? luma(db) * luma(db) : dot(db, db);
        float wa = exp(-(sp + ra * ir2)), wb = exp(-(sp + rb * ir2));
        acc += wa * a + wb * b;
        ws += wa + wb;
    }
    vec3 sm = acc / ws;
    vec4 o = vec4(sm, c0.a);
#ifdef FINAL
    vec4 c = texelFetch(sTD2DInputs[1], p, 0);                    // bilv only (2 inputs; TD sizes sTD2DInputs[])
    vec3 r = sm + uM.y * (c.rgb - sm);
    o = mix(c, vec4(r, c.a), uM.x);
#endif
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
""".replace('RMAX', str(RMAX))
BILH = BIL
BILV = BIL.replace('layout (local_size_x = 8', '#define FINAL 1\nlayout (local_size_x = 8', 1)

SHADERS = {'med': MED, 'bilh': BILH, 'bilv': BILV}
NIN = {'med': 1, 'bilh': 1, 'bilv': 2}             # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"


def uniforms():
    m = ['parent().par.Rangemode.menuIndex']
    return {
        'med': [],
        'bilh': [('uB', [P.format('Radius'), P.format('Sigma'), P.format('Edge'), '0']),
                 ('uM', ['1', '0', m[0], '0'])],
        'bilv': [('uB', [P.format('Radius'), P.format('Sigma'), P.format('Edge'), '1']),
                 ('uM', [P.format('Amount'), P.format('Detail'), m[0], '0'])],
    }


def build(m, H):
    """in1 -> med (Median) -> msrc -> bilh -> bilv (+ in1: Amount, Detail) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    md = H['pas'](m, 'med', MED, [in1], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    md.comment = '3x3 median per channel (despeckle).'
    ms = mk(m, switchTOP, 'msrc')  # noqa: F821
    ms.inputConnectors[0].connect(in1)
    ms.inputConnectors[1].connect(md)
    expr(ms.par.index, '1 if %s else 0' % P.format('Median'))
    ms.comment = 'Median off = in1 (med not pulled).'
    bh = H['pas'](m, 'bilh', BILH, [ms], 'me.inputs[0].width', 'me.inputs[0].height', 'rgba16float')
    H['uniforms'](bh, U['bilh'])
    bh.comment = 'Bilateral along x (edge-preserving).'
    bv = H['pas'](m, 'bilv', BILV, [bh, in1], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](bv, U['bilv'])
    bv.comment = 'Bilateral along y + Amount mix with in1 + Detail.'
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(bv)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact.'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Despeckle', 'role': 'process', 'ops': ['med', 'med_compute', 'msrc'],
         'body': 'Median 3x3 per channel (Median toggle).'},
        {'title': '3 Smooth', 'role': 'process', 'ops': ['bilh', 'bilh_compute', 'bilv', 'bilv_compute'],
         'body': 'Separable bilateral (Radius, Sigma, Edge), Amount + Detail.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
