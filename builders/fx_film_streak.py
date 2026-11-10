# fx_film_streak - FX_film module 'streak' (FX3 L1): anamorphic streaks from every bright light, at any Angle.
# The streak direction is a vector, not a rotate-blur-rotate (FX3: our canvas is portrait): `ext` samples the picture
# in a ROTATED work frame (axis e1 along Angle) into an anisotropic buffer, Along px per texel along the streak and
# Thickness px across it (soft-knee excess, luma in a); `run` does the exact two-sided exponential sum of every row
# (sum_i e_i r^|x - i|, r = exp(-Along / Length)): a chunked scan, one workgroup per row, 8 elements per thread in
# registers, only the 64 chunk carries shared (2 KB), 2 barriers (fx_film_logic.scan_chunked == scan_brute); rgb
# uses Length, alpha (luma) Corelength for a hot core; `fx` maps every
# pixel into the frame, samples the run buffer bilinear and adds tint x long + core tint x core. Rows <= 512 texels
# (Along grows when a row would be longer). out_sel: Amount 0 = in1, nothing upstream cooks. ASCII only.

MODULE = 'streak'

PAGES = [
    ('Streak', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Intensity', 'Float', 2.0, {'min': 0, 'max': 10, 'label': 'Intensity'}),
        ('Threshold', 'Float', 0.8, {'min': 0, 'max': 4, 'label': 'Threshold'}),
        ('Knee', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Knee'}),
        ('Length', 'Float', 300.0, {'min': 10, 'max': 2000, 'label': 'Length px (falls by e)'}),
        ('Corelength', 'Float', 40.0, {'min': 2, 'max': 400, 'label': 'Core length px'}),
        ('Coregain', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Core gain'}),
        ('Angle', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Angle deg (0 = across the width)'}),
        ('Tint', 'RGB', (0.35, 0.55, 1.0), {'label': 'Streak tint'}),
        ('Coretint', 'RGB', (0.8, 0.9, 1.0), {'label': 'Core tint'}),
        ('Sourcecolor', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Light colour (0 = tint)'}),
        ('Along', 'Float', 8.0, {'min': 2, 'max': 32, 'label': 'Along px per texel'}),
        ('Thickness', 'Float', 2.0, {'min': 1, 'max': 16, 'label': 'Thickness px per texel'}),
    ]),
]
PANEL_PAGES = ['Streak']

PRESETS = [
    (1, 'blue anamorphic', {'Amount': 1.0, 'Intensity': 2.0, 'Threshold': 0.8, 'Length': 300.0, 'Corelength': 40.0,
                            'Coregain': 0.5, 'Angle': 0.0, 'Tintr': 0.35, 'Tintg': 0.55, 'Tintb': 1.0,
                            'Sourcecolor': 0.0}),
    (2, 'amber long', {'Amount': 1.0, 'Intensity': 3.0, 'Threshold': 0.85, 'Length': 700.0, 'Corelength': 60.0,
                       'Coregain': 0.8, 'Angle': 0.0, 'Tintr': 1.0, 'Tintg': 0.6, 'Tintb': 0.2,
                       'Coretintr': 1.0, 'Coretintg': 0.9, 'Coretintb': 0.7}),
    (3, 'vertical tower', {'Amount': 1.0, 'Intensity': 2.5, 'Threshold': 0.8, 'Length': 500.0, 'Angle': 90.0,
                           'Tintr': 0.6, 'Tintg': 0.4, 'Tintb': 1.0}),
    (4, 'light colour', {'Amount': 1.0, 'Intensity': 2.0, 'Threshold': 0.7, 'Length': 250.0, 'Sourcecolor': 1.0,
                         'Coregain': 1.0}),
    (5, 'diagonal sweep', {'Amount': 1.0, 'Intensity': 2.0, 'Threshold': 0.8, 'Length': 400.0, 'Angle': 30.0,
                           'Tintr': 1.0, 'Tintg': 0.3, 'Tintb': 0.8, 'Thickness': 3.0}),
]

EXT_S = """// FX_film streak ext (compute): rotated anisotropic extract. in0 = picture (extend zero).
// uS0 cos sin ds1 ds2 | uS1 Lx Ly thr knee
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS0;
uniform vec4 uS1;
%s
void main() {
    ivec2 q = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (q.x >= osz.x || q.y >= osz.y) return;
    vec2 isz = vec2(textureSize(sTD2DInputs[0], 0));
    vec2 e1 = uS0.xy, e2 = vec2(-uS0.y, uS0.x);
    vec2 f = vec2(-0.5 * uS1.x + (float(q.x) + 0.5) * uS0.z, -0.5 * uS1.y + (float(q.y) + 0.5) * uS0.w);
    vec2 P = 0.5 * isz + f.x * e1 + f.y * e2;
    int n = int(clamp(ceil(uS0.z / 2.0), 1.0, 16.0)), m = int(clamp(ceil(uS0.w / 2.0), 1.0, 8.0));
    vec3 acc = vec3(0.0);
    for (int k = 0; k < 16; k++) {                     // box over Along x Thickness, bilinear taps 2 px apart
        if (k >= n) break;
        float o = (float(k) + 0.5) / float(n) - 0.5;
        for (int l = 0; l < 8; l++) {
            if (l >= m) break;
            float o2 = (float(l) + 0.5) / float(m) - 0.5;
            acc += texture(sTD2DInputs[0], (P + e1 * o * uS0.z + e2 * o2 * uS0.w) / isz).rgb;
        }
    }
    vec3 e = kneex(acc / float(n * m), uS1.z, uS1.w, 0.0);
    TDImageStoreOutput(0, ivec3(q, 0), vec4(e, luma(e)));
}
"""

RUN = """// FX_film streak run (compute): exact two-sided exponential row sum, chunked scan.
// One workgroup per row (manual dispatch 1 x rows), 64 threads x 8 elements (in registers) = rows <= 512 texels.
// Only the 2 x 64 chunk carries are shared (2 KB; Apple GPUs allow 32 KB per workgroup).
// uR = rate rgb (Length), rate a (Corelength) | uN = row length - - -
layout (local_size_x = 64, local_size_y = 1) in;
uniform vec4 uR;
uniform vec4 uN;
shared vec4 CF[64];
shared vec4 CB[64];
void main() {
    int t = int(gl_LocalInvocationID.x);
    int row = int(gl_WorkGroupID.y);
    int n = int(uN.x + 0.5);
    vec4 r = uR;
    vec4 e[8], f[8], b[8];
    for (int j = 0; j < 8; j++) {
        int i = t * 8 + j;
        e[j] = i < n ? texelFetch(sTD2DInputs[0], ivec2(i, row), 0) : vec4(0.0);
    }
    vec4 acc = vec4(0.0);
    for (int j = 0; j < 8; j++) { acc = e[j] + r * acc; f[j] = acc; }
    CF[t] = acc;
    acc = vec4(0.0);
    for (int j = 7; j >= 0; j--) { acc = e[j] + r * acc; b[j] = acc; }
    CB[t] = acc;
    memoryBarrierShared();
    barrier();
    vec4 r8 = pow(r, vec4(8.0));
    if (t == 0) {
        vec4 cin = vec4(0.0);
        for (int u = 0; u < 64; u++) { vec4 tmp = CF[u]; CF[u] = cin; cin = tmp + r8 * cin; }
    } else if (t == 1) {
        vec4 cin = vec4(0.0);
        for (int u = 63; u >= 0; u--) { vec4 tmp = CB[u]; CB[u] = cin; cin = tmp + r8 * cin; }
    }
    memoryBarrierShared();
    barrier();
    for (int j = 0; j < 8; j++) {
        int i = t * 8 + j;
        vec4 S = f[j] + pow(r, vec4(float(j + 1))) * CF[t] + b[j] + pow(r, vec4(float(8 - j))) * CB[t] - e[j];
        if (i < n) TDImageStoreOutput(0, ivec3(i, row, 0), S);
    }
}
"""

FX = """// FX_film streak fx (compute). in0 = picture, in1 = run buffer (bilinear, extend zero).
// uS0 cos sin ds1 ds2 | uS1 Lx Ly intensity amount | uT tint rgb sourcecolor | uU coretint rgb coregain
// uV 1-rLong 1-rCore - -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uS0;
uniform vec4 uS1;
uniform vec4 uT;
uniform vec4 uU;
uniform vec4 uV;
%s
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uS1.w <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }  // exact passthrough
    vec2 d = vec2(p) + 0.5 - 0.5 * vec2(isz);
    vec2 f = vec2(dot(d, uS0.xy), dot(d, vec2(-uS0.y, uS0.x)));
    vec2 rsz = vec2(textureSize(sTD2DInputs[1], 0));
    vec2 uv = vec2((f.x + 0.5 * uS1.x) / uS0.z, (f.y + 0.5 * uS1.y) / uS0.w) / rsz;
    vec4 S = texture(sTD2DInputs[1], uv);
    vec3 lng = mix(uT.rgb * luma(S.rgb), S.rgb, uT.w) * uV.x;
    vec3 core = uU.rgb * uU.w * S.a * uV.y;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(c.rgb + uS1.w * uS1.z * (lng + core), c.a));
}
"""


def shaders(H):
    return {'ext': EXT_S % H['LIB'], 'run': RUN, 'fx': FX % H['LIB']}


A_ = "math.radians(parent().par.Angle.eval())"
LX = "(%s * abs(math.cos(%s)) + %s * abs(math.sin(%s)))"
LY = "(%s * abs(math.sin(%s)) + %s * abs(math.cos(%s)))"


def exprs(H):
    """Frame expressions (fx_film_logic.streak_dims), all on op('in1')."""
    W, Hh = H['W'], H['H']
    lx = LX % (W, A_, Hh, A_)
    ly = LY % (W, A_, Hh, A_)
    ds1 = 'max(parent().par.Along.eval(), %s / 512.0)' % lx
    ds2 = 'max(parent().par.Thickness.eval(), 1.0)'
    return {'lx': lx, 'ly': ly, 'ds1': ds1, 'ds2': ds2, 'nx': 'int(math.ceil(round(%s / %s, 6)))' % (lx, ds1),
            'ny': 'int(math.ceil(round(%s / %s, 6)))' % (ly, ds2), 'cos': 'math.cos(%s)' % A_,
            'sin': 'math.sin(%s)' % A_}


def build(m, H):
    """in1 -> ext (rotated anisotropic extract) -> run (row scan) -> fx -> out_sel -> out1."""
    mk, P = H['mk'], H['P']
    T = shaders(H)
    X = exprs(H)
    in1 = mk(m, inTOP, 'in1')
    ext = H['compute'](m, 'ext', T['ext'], [in1], res=(X['nx'], X['ny']), fmt='rgba16float', extend='zero')
    H['uniforms'](ext, [('uS0', [X['cos'], X['sin'], X['ds1'], X['ds2']]),
                        ('uS1', [X['lx'], X['ly'], P.format('Threshold'), 'max(%s, 1e-4)' % P.format('Knee')])])
    ext.comment = 'streak ext: rotated frame, Along x Thickness px per texel, soft-knee excess (luma in a).'
    rl = 'math.exp(-(%s) / max(parent().par.Length.eval(), 1e-3))' % X['ds1']
    rc = 'math.exp(-(%s) / max(parent().par.Corelength.eval(), 1e-3))' % X['ds1']
    run = H['compute'](m, 'run', T['run'], [ext], fmt='rgba16float', dispatch=('1', 'me.inputs[0].height'))
    H['uniforms'](run, [('uR', [rl, rl, rl, rc]), ('uN', ['me.inputs[0].width', '0', '0', '0'])])
    run.comment = 'streak run: exact exponential row sum (shared-memory chunked scan, one workgroup per row).'
    g = H['compute'](m, 'fx', T['fx'], [in1, run], extend='zero')
    H['uniforms'](g, [
        ('uS0', [X['cos'], X['sin'], X['ds1'], X['ds2']]),
        ('uS1', [X['lx'], X['ly'], P.format('Intensity'), P.format('Amount')]),
        ('uT', [P.format('Tintr'), P.format('Tintg'), P.format('Tintb'), P.format('Sourcecolor')]),
        ('uU', [P.format('Coretintr'), P.format('Coretintg'), P.format('Coretintb'), P.format('Coregain')]),
        ('uV', ['1.0 - %s' % rl, '1.0 - %s' % rc, '0', '0']),
    ])
    g.comment = 'streak fx: frame lookup of the row sums, tint x long + core tint x core, added.'
    sel = H['outsel'](m, in1, g)
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Extract (rotated)', 'role': 'process', 'ops': ['ext', 'ext_compute'],
         'body': 'Along x Thickness px per texel in the Angle frame; soft knee.'},
        {'title': '3 Row scan', 'role': 'process', 'ops': ['run', 'run_compute'],
         'body': 'sum e_i r^|x-i| per row: chunked scan, 2 KB shared, 2 barriers.'},
        {'title': '4 Composite', 'role': 'process', 'ops': ['fx', 'fx_compute']},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
