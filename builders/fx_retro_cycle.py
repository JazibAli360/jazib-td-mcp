# fx_retro_cycle - FX_retro module 'cycle' (FX2 AV-37 palette cycling, Mark Ferrari "Living Worlds" style; FX0 row
# 59). ONE compute pass: every pixel becomes an index (luma, hue or saturation x Indices), up to 4 index ranges rotate
# at their own speed (indices per second, sign = direction; fractional steps blend when Blend is on), and the index
# picks a colour from a Ramp: fire, water, rainbow, grey, sunset, or the rack palette bank (Machine). Works on any clip
# (water / fire / sky loops); chain the palette or dither module after it for hardware looks. Shifts are computed per
# cook in the uniform expressions (absTime x speed, wrapped), so the shader is stateless. Premultiplied out, Amount mix,
# out_sel: Amount 0 = in1. Mirror: builders/fx_retro_cycle_logic.py. ASCII only.

MODULE = 'cycle'
SOURCES = ['luma', 'hue', 'sat']
RAMPS = ['fire', 'water', 'rainbow', 'grey', 'sunset', 'machine']


def pages(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    ml = [l for _k, l in Lg['MACHINE_MENU']]
    rng = []
    for k, (s0, s1, v) in enumerate(((0.0, 1.0, 8.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))):
        rng += [('R%dstart' % (k + 1), 'Float', s0, {'min': 0, 'max': 1, 'label': 'Range %d start' % (k + 1)}),
                ('R%dend' % (k + 1), 'Float', s1, {'min': 0, 'max': 1, 'label': 'Range %d end' % (k + 1)}),
                ('R%dspeed' % (k + 1), 'Float', v, {'min': -60, 'max': 60, 'label': 'Range %d speed idx/s' % (k + 1)})]
    return [
        ('Cycle', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Source', 'Menu', 'luma', {'names': SOURCES, 'labels': ['Luma', 'Hue', 'Saturation']}),
            ('Indices', 'Int', 32, {'min': 2, 'max': 256, 'label': 'Indices'}),
            ('Ramp', 'Menu', 'fire', {'names': RAMPS, 'labels': ['Fire', 'Water', 'Rainbow', 'Grey', 'Sunset',
                                                                 'Palette (Machine)']}),
            ('Machine', 'Menu', 'pico8', {'names': mk, 'labels': ml}),
            ('Blend', 'Toggle', True, {'label': 'Blend between steps'}),
            ('Contrast', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Contrast (pre)'}),
            ('Offset', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Index offset (share)'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
        ('Ranges', rng),
    ]


PANEL_PAGES = ['Cycle', 'Ranges']


def presets(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in pages(Lg) for n, s, d, o in pl)
    return [
        (1, 'lava', dict(D)),
        (2, 'waterfall', dict(D, Ramp=1, Indices=48, R1start=0.3, R1end=1.0, R1speed=-14.0, Seed=2)),
        (3, 'rainbow road', dict(D, Ramp=2, Source=1, Indices=64, R1speed=20.0, Blend=0, Seed=3)),
        (4, 'two zones', dict(D, Ramp=4, Indices=40, R1start=0.0, R1end=0.45, R1speed=6.0, R2start=0.6,
                              R2end=1.0, R2speed=-10.0, Seed=4)),
        (5, 'pico cycle', dict(D, Ramp=5, Machine=mk.index('pico8'), Indices=16, R1speed=3.0, Blend=0, Seed=5)),
    ]


FX = """// FX_retro cycle (compute, full res). in0 = picture, in1 = rack pal_top. = fx_retro_cycle_logic.render
layout (local_size_x = 8, local_size_y = 8) in;
%LIB%
uniform vec4 uA;   // amount source indices ramp
uniform vec4 uB;   // blend contrast offset -
uniform vec4 uS0;  // range 1: start end shift(indices) -   (start / end in indices)
uniform vec4 uS1;
uniform vec4 uS2;
uniform vec4 uS3;
uniform vec4 uP;   // bank offset, bank count, -, -
float hueOf(vec3 c) {
    float mx = max(c.r, max(c.g, c.b)), mn = min(c.r, min(c.g, c.b)), d = mx - mn;
    if (d <= 1e-6) return 0.0;
    float h = (mx == c.r) ? mod((c.g - c.b) / d, 6.0) : ((mx == c.g) ? (c.b - c.r) / d + 2.0 : (c.r - c.g) / d + 4.0);
    return h / 6.0;
}
vec3 ramp(float u, int r) {
    u = clamp(u, 0.0, 1.0);
    if (r == 0) return clamp(vec3(u * 3.0, u * 3.0 - 1.0, u * 3.0 - 2.0), 0.0, 1.0);                     // fire
    if (r == 1) return clamp(vec3(u * u, 0.25 + 0.75 * u, 0.45 + 0.55 * sqrt(u)), 0.0, 1.0) * vec3(1.0, u + 0.2, 1.0);
    if (r == 2) return clamp(abs(fract(u + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    if (r == 3) return vec3(u);
    if (r == 4) return clamp(vec3(0.15 + 0.85 * sqrt(u), 0.05 + 0.9 * u * u, 0.35 * (1.0 - u) + 0.6 * u * u * u), 0.0, 1.0);
    int n = max(int(uP.y + 0.5), 1);
    return palRgb(int(uP.x + 0.5) + min(int(floor(u * float(n))), n - 1));
}
float rotate(float i, vec4 R) {                            // inside [start, end): shift and wrap
    float len = R.y - R.x;
    if (len < 1.0 || i < R.x || i >= R.y) return i;
    return R.x + mod(i - R.x + R.z, len);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 res = textureSize(sTD2DInputs[0], 0);
    if (p.x >= res.x || p.y >= res.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    vec3 c = c0.a > 1e-5 ? c0.rgb / c0.a : c0.rgb;
    int sm = int(uA.y + 0.5);
    float v = sm == 0 ? luma(c) : (sm == 1 ? hueOf(c) : (max(c.r, max(c.g, c.b)) <= 1e-6 ? 0.0
             : (max(c.r, max(c.g, c.b)) - min(c.r, min(c.g, c.b))) / max(c.r, max(c.g, c.b))));
    v = clamp((v - 0.5) * uB.y + 0.5 + uB.z, 0.0, 1.0);
    float N = max(floor(uA.z + 0.5), 2.0);
    float i = min(floor(v * N), N - 1.0);
    float j = rotate(rotate(rotate(rotate(i, uS0), uS1), uS2), uS3);
    int r = int(uA.w + 0.5);
    vec3 col;
    if (uB.x > 0.5) {                                       // blend: fractional index between two ramp steps
        float f = fract(j), j0 = floor(j);
        float j1 = j0 + 1.0;
        vec4 Rs[4] = vec4[4](uS0, uS1, uS2, uS3);
        for (int k = 0; k < 4; k++) if (j0 >= Rs[k].x && j0 < Rs[k].y && Rs[k].y - Rs[k].x >= 1.0 && j1 >= Rs[k].y)
            j1 = Rs[k].x;                                   // wrap inside its range
        col = mix(ramp((j0 + 0.5) / N, r), ramp((min(j1, N - 1.0) + 0.5) / N, r), f);
    } else col = ramp((floor(j) + 0.5) / N, r);
    vec3 fin = mix(c, col, uA.x);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(fin * c0.a, c0.a));
}
"""


def shader_texts(lib):
    return {'fx': FX.replace('%LIB%', lib(pal_in=1))}


def uniforms(H):
    P, LX = H['P'], H['LX']
    N = "max(2, int(%s + 0.5))" % P.format('Indices')
    U = [('uA', [P.format('Amount'), 'parent().par.Source.menuIndex', P.format('Indices'),
                 'parent().par.Ramp.menuIndex']),
         ('uB', ['1 if %s else 0' % P.format('Blend'), P.format('Contrast'), P.format('Offset'), '0'])]
    for k in range(4):
        s0 = "math.floor(%s * %s + 0.5)" % (P.format('R%dstart' % (k + 1)), N)
        s1 = "math.floor(%s * %s + 0.5)" % (P.format('R%dend' % (k + 1)), N)
        sh = "((%s * absTime.seconds) %% max(1, %s - %s))" % (P.format('R%dspeed' % (k + 1)), s1, s0)
        U.append(('uS%d' % k, [s0, s1, sh, '0']))
    slot = "%s.bank_slot(parent().par.Machine.eval(), parent(2).op('pal_bank').numRows)" % LX
    U.append(('uP', [slot + '[0]', slot + '[1]', '0', '0']))
    return U


def build(m, H, Lg):
    """in1 -> fx (one pass) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr, compute = H['mk'], H['expr'], H['compute']
    in1 = mk(m, inTOP, 'in1')
    pal = H['select'](m, 'pal', '../pal_top')
    sh = shader_texts(lambda **k: H['glsl_lib'](Lg, **k))
    fx = compute(m, 'fx', sh['fx'], [in1, pal], 'me.inputs[0].width', 'me.inputs[0].height', uniforms=uniforms(H))
    fx.comment = 'cycle: picture -> index -> rotating ranges -> ramp / palette colour (palette cycling, AV-37).'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '0 if parent().par.Amount.eval() <= 0 else 1')
    sel.comment = 'Amount 0 = in1 exactly.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pal']},
        {'title': '2 Cycle', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'Index, rotate ranges, ramp.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
