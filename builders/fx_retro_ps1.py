# fx_retro_ps1 - FX_retro module 'ps1' (FX7c 7C-07 PS1 / early-3D console look; Keijiro Retro3D / NoPersRetro ideas,
# no code copied) in two parts:
# (1) the rack module (post, any picture): ONE compute pass `fx` at the input size: a low-res frame buffer (Downscale
#     px per virtual pixel, nearest, no AA), 15-bit colour (Bits per channel) with the PlayStation GPU's 4x4 ordered
#     dither table added in 8-bit units before truncation (psx-spx "dither"), and Wobble = the vertex-snapping /
#     affine texture swim seen on 2D content: a triangle lattice (Wobblesize px) whose vertices jump up to Wobble px
#     Wobblerate times a second, the picture warped piecewise-affine across it. Mirror: fx_retro_ps1_logic.py.
# (2) `ps1_mat(comp, name)`: a GLSL MAT for real meshes (vertex snap after the projection divide to a Snapw x Snaph
#     grid, `noperspective` UVs = affine texture mapping, nearest texture, flat vertex colour light) - LIVE PROBE on
#     31550 / MoltenVK first (doc docs/builds/fx_retro.md); render its Render TOP at 320 x 240-ish and feed the rack.
# Premultiplied out, Amount mix, out_sel: Amount 0 = in1 exactly. ASCII only.

MODULE = 'ps1'
DITHERS = ['psx', 'none', 'bayer4']


def pages(Lg):
    return [
        ('Ps1', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Downscale', 'Float', 4.0, {'min': 1, 'max': 16, 'label': 'Downscale (px per virtual px)'}),
            ('Bits', 'Int', 5, {'min': 1, 'max': 8, 'label': 'Bits per channel (5 = 15-bit)'}),
            ('Dither', 'Menu', 'psx', {'names': DITHERS, 'labels': ['PS1 GPU 4x4 table', 'None (truncate)',
                                                                    'Bayer 4x4']}),
            ('Ditheramt', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Dither amount'}),
            ('Wobble', 'Float', 0.0, {'min': 0, 'max': 40, 'label': 'Wobble px (vertex snap swim)'}),
            ('Wobblesize', 'Float', 120.0, {'min': 8, 'max': 600, 'label': 'Wobble triangle size px'}),
            ('Wobblerate', 'Float', 15.0, {'min': 0, 'max': 60, 'label': 'Wobble jumps per s'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
    ]


PANEL_PAGES = ['Ps1']


def presets(Lg):
    D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in pages(Lg) for n, s, d, o in pl)
    return [
        (1, 'psx', dict(D)),
        (2, 'swimmy', dict(D, Wobble=6.0, Wobblesize=160.0, Wobblerate=20.0, Seed=2)),
        (3, 'saturn', dict(D, Downscale=3.0, Dither=1, Wobble=2.0, Wobblesize=90.0, Wobblerate=10.0, Seed=3)),
        (4, 'crunchy', dict(D, Downscale=6.0, Bits=4, Ditheramt=1.5, Wobble=10.0, Wobblesize=200.0,
                            Wobblerate=12.0, Seed=4)),
    ]


FX = """// FX_retro ps1 (compute, full res): wobble warp -> virtual pixel (Downscale) -> 15-bit + PS1 dither -> out.
// in0 = picture. = fx_retro_ps1_logic.render
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount downscale bits dither
uniform vec4 uB;   // ditheramt wobble wobblesize epoch
uniform vec4 uC;   // seed - - -
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hv(ivec2 v, uint k) { return float(lb32(uint(v.x) * 1597334677u ^ lb32(uint(v.y) ^ (k * 2654435761u))) >> 8)
                                   / 16777216.0; }
vec2 joff(ivec2 v, uint s) { return (vec2(hv(v, s), hv(v, s + 7u)) - 0.5) * 2.0 * uB.y; }
const float PSX[16] = float[16](-4.0, 0.0, -3.0, 1.0, 2.0, -2.0, 3.0, -1.0, -3.0, 1.0, -4.0, 0.0, 3.0, -1.0, 2.0, -2.0);
const float BAY[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 res = textureSize(sTD2DInputs[0], 0);
    if (p.x >= res.x || p.y >= res.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    vec2 q = vec2(p) + 0.5;
    if (uB.y > 0.0) {                                       // piecewise-affine warp over a jittered triangle lattice
        float S = max(uB.z, 1.0);
        vec2 g = q / S; vec2 f0 = floor(g); vec2 f = g - f0; ivec2 i = ivec2(f0);
        uint s = uint(uC.x) * 7919u + uint(uB.w) * 104729u;
        vec2 o00 = joff(i, s), o11 = joff(i + ivec2(1, 1), s);
        vec2 d = f.x >= f.y ? (o00 + (joff(i + ivec2(1, 0), s) - o00) * f.x + (o11 - joff(i + ivec2(1, 0), s)) * f.y)
                            : (o00 + (joff(i + ivec2(0, 1), s) - o00) * f.y + (o11 - joff(i + ivec2(0, 1), s)) * f.x);
        q -= d;
    }
    float ds = max(floor(uA.y + 0.5), 1.0);
    ivec2 v = ivec2(floor(q / ds));
    ivec2 sp = clamp(ivec2(floor((vec2(v) + 0.5) * ds)), ivec2(0), res - 1);
    vec4 s4 = texelFetch(sTD2DInputs[0], sp, 0);
    vec3 c = s4.a > 1e-5 ? s4.rgb / s4.a : s4.rgb;
    int dm = int(uA.w + 0.5);
    int k = (v.y & 3) * 4 + (v.x & 3);
    float dv = dm == 0 ? PSX[k] : (dm == 2 ? (BAY[k] + 0.5) / 16.0 * 8.0 - 4.0 : 0.0);
    int bits = clamp(int(uA.z + 0.5), 1, 8);
    int sh = 8 - bits;
    vec3 c8 = clamp(floor(clamp(c, 0.0, 1.0) * 255.0 + 0.5) + dv * uB.x, 0.0, 255.0);
    vec3 cq = floor(c8 / float(1 << sh));                      // truncate to Bits
    float mx = float((1 << bits) - 1);
    vec3 o = cq / mx;                                          // expand to full range (31 -> 1.0)
    vec3 src = c0.a > 1e-5 ? c0.rgb / c0.a : c0.rgb;
    vec3 fin = mix(src, o, uA.x);
    float a = mix(c0.a, s4.a, uA.x);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(fin * a, a));
}
"""

MAT_VERT = """// FX_retro ps1 GLSL MAT vertex shader (7C-07): vertex snap after the projection divide + affine (noperspective) UVs.
uniform vec4 uSnap;   // snap grid w h (virtual screen px), amount 0..1, -
out Vert { noperspective vec2 uv; flat vec3 lit; } oVert;
void main()
{
	vec4 w = TDDeform(P);
	vec4 cp = TDWorldToProj(w);
	vec2 ndc = cp.xy / cp.w;
	vec2 g = max(uSnap.xy, vec2(1.0)) * 0.5;
	vec2 sn = floor(ndc * g + 0.5) / g;
	cp.xy = mix(ndc, sn, uSnap.z) * cp.w;
	gl_Position = cp;
#ifndef TD_PICKING_ACTIVE
	vec3 n = normalize(TDDeformNorm(N));
	oVert.uv = uv[0].st;
	oVert.lit = vec3(0.35 + 0.65 * max(dot(n, normalize(vec3(0.4, 0.8, 0.5))), 0.0));
#else
	TDWritePickingValues();
#endif
}
"""

MAT_PIXEL = """// FX_retro ps1 GLSL MAT pixel shader: nearest texture at the affine UV, flat per-vertex light, no AA.
uniform sampler2D sTex;
uniform vec4 uTint;   // rgb, use texture 0/1
in Vert { noperspective vec2 uv; flat vec3 lit; } iVert;
layout(location = 0) out vec4 fragColor;
void main()
{
	TDCheckDiscard();
	vec3 t = uTint.w > 0.5 ? texture(sTex, iVert.uv).rgb : vec3(1.0);
	vec3 c = t * uTint.rgb * iVert.lit;
	fragColor = TDOutputSwizzle(vec4(c, 1.0));
}
"""


def shader_texts(lib):
    return {'fx': FX}


def uniforms(H):
    P = H['P']
    ep = "int(absTime.seconds * %s) if %s > 0 else 0" % (P.format('Wobblerate'), P.format('Wobblerate'))
    return [('uA', [P.format('Amount'), P.format('Downscale'), P.format('Bits'), 'parent().par.Dither.menuIndex']),
            ('uB', [P.format('Ditheramt'), P.format('Wobble'), P.format('Wobblesize'), ep]),
            ('uC', [P.format('Seed'), '0', '0', '0'])]


def build(m, H, Lg):
    """in1 -> fx (one pass) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr, compute = H['mk'], H['expr'], H['compute']
    in1 = mk(m, inTOP, 'in1')
    fx = compute(m, 'fx', FX, [in1], 'me.inputs[0].width', 'me.inputs[0].height', uniforms=uniforms(H))
    fx.comment = 'ps1: wobble (snapped triangle warp) -> low-res nearest -> 15-bit + PS1 GPU dither.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '0 if parent().par.Amount.eval() <= 0 else 1')
    sel.comment = 'Amount 0 = in1 exactly.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 PS1', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'One pass: wobble, downscale, dither.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


def ps1_mat(comp_path, name='ps1_mat', snap=(320, 240), amount=1.0, tex=None):
    """Make / update a PS1 GLSL MAT (vertex snap + affine UVs) inside comp_path (any 3D scene COMP); assign it to a
    Geometry COMP's material par yourself. Returns the MAT path. TD side only (ops: glslMAT + 2 docked Text DATs)."""
    c = op(comp_path)                                                    # noqa: F821
    mat = c.op(name) or c.create(glslMAT, name)                          # noqa: F821
    vd = c.op(name + '_vert') or c.create(textDAT, name + '_vert')      # noqa: F821
    pd = c.op(name + '_pix') or c.create(textDAT, name + '_pix')        # noqa: F821
    vd.text, pd.text = MAT_VERT, MAT_PIXEL
    mat.par.vdat, mat.par.pdat = vd.name, pd.name
    vd.dock = mat
    pd.dock = mat
    mat.par.vec0name = 'uSnap'
    mat.par.vec0valuex, mat.par.vec0valuey, mat.par.vec0valuez = snap[0], snap[1], amount
    mat.par.vec1name = 'uTint'
    mat.par.vec1valuex = mat.par.vec1valuey = mat.par.vec1valuez = 1.0
    mat.par.vec1valuew = 1.0 if tex else 0.0
    if not tex:                                                          # no texture: a white 1x1, so sTex is bound
        w = c.op(name + '_white') or c.create(constantTOP, name + '_white')     # noqa: F821
        w.par.outputresolution = 'custom'
        w.par.resolutionw, w.par.resolutionh = 1, 1
        tex = w.path
    mat.par.sampler0name = 'sTex'
    mat.par.sampler0top = tex
    mat.par.sampler0filter = 'nearest'
    mat.comment = 'PS1 look MAT (7C-07): vertex snap to %d x %d + noperspective (affine) UVs, nearest texture.' % snap
    return mat.path


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
