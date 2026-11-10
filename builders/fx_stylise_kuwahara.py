# fx_stylise_kuwahara - FX_stylise module 'kuwahara' (FX0 #71 Kuwahara / paint: the anisotropic generalized Kuwahara
# filter, Kyprianidis, Kang, Doellner 2009 "Image and video abstraction by anisotropic Kuwahara filtering"; the
# polynomial sector weights of Kyprianidis 2010 as in Garrett Gunnell's Post-Processing AnisotropicKuwahara (MIT),
# clean-room). Template: docs/builds/fx_glitch.md "Module template" (rack = builders/fx_stylise.py). Doc:
# docs/builds/fx_stylise.md. Mirror: builders/fx_stylise_kuwahara_logic.py.
# Passes (compute, at Res except fx):
#   tens  : structure tensor of in1 (rgb Sobel from bilinear taps D px apart): (E, F, G) = (Sx.Sx, Sx.Sy, Sy.Sy)
#   tblur : 5x5 Gaussian (sigma 1.5 texels) of the tensor
#   kuw   : orientation + anisotropy A from the tensor's eigenvectors; an ellipse (Radius x (Alpha + A) / Alpha by
#           Radius x Alpha / (Alpha + A)) rotated to the edge; 8 sectors with polynomial weights (Zeta, Zerocross) and a
#           Gaussian falloff; each sector's mean + variance; output = sum of means weighted 1 / (1 + (1000 var)^(q/2))
#   fx    : bilinear kuw at full res, Amount mix with in1
# Amount 0 = in1 exact (out_sel). <= 3 GLSL TOP inputs (T-88). ASCII only.
import os

MODULE = 'kuwahara'
RMAX = 12

with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821 (HERE from the rack)
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']

PAGES = [
    ('Kuwahara', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Radius', 'Int', 3, {'min': 1, 'max': 12, 'label': 'Radius (texels at Res: x 4 px at quarter)'}),
        ('Res', 'Menu', 'quarter', {'names': ['full', 'half', 'quarter'], 'labels': ['Full', 'Half', 'Quarter (default)'],
                                 'label': 'Filter resolution'}),
        ('Sharpness', 'Float', 8.0, {'min': 1, 'max': 20, 'label': 'Sharpness q'}),
        ('Alpha', 'Float', 1.0, {'min': 0.01, 'max': 4, 'label': 'Anisotropy alpha (small = stretched strokes)'}),
        ('Anisotropy', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Anisotropy amount (0 = isotropic)'}),
        ('Zerocross', 'Float', 0.58, {'min': 0.3, 'max': 1.2, 'label': 'Sector overlap (zero crossing)'}),
        ('Zeta', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Zeta (0 = 2 / Radius)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (unused: deterministic)'}),
    ]),
]
PANEL_PAGES = ['Kuwahara']

_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl)


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'oil paint', _p()),
    (2, 'brush strokes', _p(Radius=3, Alpha=0.35, Sharpness=10.0)),
    (3, 'watercolour blobs', _p(Radius=4, Anisotropy=0.0, Sharpness=6.0)),
    (4, 'fine detail', _p(Radius=2, Res=1, Sharpness=12.0)),
    (5, 'poster', _p(Radius=5, Alpha=1.5, Sharpness=16.0)),
]

TENS = """// kuwahara tens (compute, rgba16float, size = in1 / Res). rgb Sobel from bilinear taps D px apart -> E F G.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uT;   // res div, -, -, -
vec2 fs;
vec3 S(vec2 q) { return texture(sTD2DInputs[0], q / fs).rgb; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    fs = vec2(textureSize(sTD2DInputs[0], 0));
    float D = uT.x;
    ivec2 jsz = ivec2(ceil(fs / D));
    if (p.x >= jsz.x || p.y >= jsz.y) return;
    vec2 pc = (vec2(p) + 0.5) * D;
    vec3 tl = S(pc + D * vec2(-1.0, 1.0)), tc = S(pc + D * vec2(0.0, 1.0)), tr = S(pc + D * vec2(1.0, 1.0));
    vec3 ml = S(pc + D * vec2(-1.0, 0.0)), mr = S(pc + D * vec2(1.0, 0.0));
    vec3 bl = S(pc + D * vec2(-1.0, -1.0)), bc = S(pc + D * vec2(0.0, -1.0)), br = S(pc + D * vec2(1.0, -1.0));
    vec3 sx = ((tr + 2.0 * mr + br) - (tl + 2.0 * ml + bl)) * 0.25;
    vec3 sy = ((tl + 2.0 * tc + tr) - (bl + 2.0 * bc + br)) * 0.25;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(dot(sx, sx), dot(sx, sy), dot(sy, sy), 1.0));
}
"""

TBLUR = """// kuwahara tblur (compute, rgba16float): 5x5 Gaussian (sigma 1.5 texels) of the tensor, clamped taps.
layout (local_size_x = 8, local_size_y = 8) in;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 a = vec4(0.0);
    float ws = 0.0;
    for (int j = -2; j <= 2; j++) for (int i = -2; i <= 2; i++) {
        float w = exp(-float(i * i + j * j) / 4.5);
        a += w * texelFetch(sTD2DInputs[0], clamp(p + ivec2(i, j), ivec2(0), isz - 1), 0);
        ws += w;
    }
    TDImageStoreOutput(0, ivec3(p, 0), a / ws);
}
"""

KUW = """// kuwahara kuw (compute, rgba16float, size = tensor size). in0 in1 (bilinear, offsets D px), in1 blurred tensor.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uK;   // radius, sharpness q, alpha, res div
uniform vec4 uZ;   // zeta (0 = 2 / radius), zero crossing, anisotropy amount, -
vec2 fs;
vec4 sector(vec4 m, vec3 s, float q) {
    if (m.w <= 0.0) return vec4(0.0);
    vec3 mu = m.rgb / m.w;
    vec3 vr = abs(s / m.w - mu * mu);
    float wk = 1.0 / (1.0 + pow(1000.0 * (vr.r + vr.g + vr.b), 0.5 * q));
    return vec4(mu * wk, wk);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 tsz = textureSize(sTD2DInputs[1], 0);
    if (p.x >= tsz.x || p.y >= tsz.y) return;
    fs = vec2(textureSize(sTD2DInputs[0], 0));
    float D = uK.w;
    vec2 pc = (vec2(p) + 0.5) * D;
    vec3 t = texelFetch(sTD2DInputs[1], p, 0).xyz;
    float E = t.x, F = t.y, G = t.z;
    float rt = sqrt(max((E - G) * (E - G) + 4.0 * F * F, 0.0));
    float l1 = 0.5 * (E + G + rt), l2 = 0.5 * (E + G - rt);
    vec2 v = vec2(l1 - E, -F);
    vec2 dir = dot(v, v) > 0.0 ? normalize(v) : vec2(0.0, 1.0);
    float phi = -atan(dir.y, dir.x);
    float A = (l1 + l2 > 0.0 ? (l1 - l2) / (l1 + l2) : 0.0) * uZ.z;
    int R = int(uK.x + 0.5);
    float r = float(R);
    float al = uK.z;
    float a = r * clamp((al + A) / al, 0.1, 2.0);
    float b = r * clamp(al / (al + A), 0.1, 2.0);
    float cp = cos(phi), sp = sin(phi);
    mat2 SR = mat2(0.5 / a, 0.0, 0.0, 0.5 / b) * mat2(cp, -sp, sp, cp);
    float zeta = uZ.x > 0.0 ? uZ.x : 2.0 / r;
    float zc = uZ.y;
    float sz = sin(zc);
    float eta = (zeta + cos(zc)) / (sz * sz);
    vec4 m0 = vec4(0.0), m1 = m0, m2 = m0, m3 = m0, m4 = m0, m5 = m0, m6 = m0, m7 = m0;    // named accumulators:
    vec3 s0 = vec3(0.0), s1 = s0, s2 = s0, s3 = s0, s4 = s0, s5 = s0, s6 = s0, s7 = s0;    // no per-thread arrays
    int mxx = int(ceil(sqrt(a * a * cp * cp + b * b * sp * sp)));        // rotated ellipse bounding box
    int mxy = int(ceil(sqrt(a * a * sp * sp + b * b * cp * cp)));
    for (int yi = 0; yi <= 2 * RMAXB; yi++) {
        if (yi > 2 * mxy) break;
        int y = yi - mxy;
        for (int xi = 0; xi <= 2 * RMAXB; xi++) {
            if (xi > 2 * mxx) break;
            int x = xi - mxx;
            vec2 w2 = SR * vec2(float(x), float(y));
            if (dot(w2, w2) > 0.25) continue;
            vec3 c = clamp(texture(sTD2DInputs[0], (pc + vec2(float(x), float(y)) * D) / fs).rgb, 0.0, 1.0);
            vec3 cc = c * c;
            float vxx = zeta - eta * w2.x * w2.x, vyy = zeta - eta * w2.y * w2.y;
            vec2 u2 = 0.70710678 * vec2(w2.x - w2.y, w2.x + w2.y);
            float uxx = zeta - eta * u2.x * u2.x, uyy = zeta - eta * u2.y * u2.y;
            vec4 wa = max(vec4(w2.y + vxx, -w2.x + vyy, -w2.y + vxx, w2.x + vyy), 0.0);   // sectors 0 2 4 6
            vec4 wb = max(vec4(u2.y + uxx, -u2.x + uyy, -u2.y + uxx, u2.x + uyy), 0.0);   // sectors 1 3 5 7
            wa *= wa; wb *= wb;
            float g = exp(-3.125 * dot(w2, w2)) / max(dot(wa, vec4(1.0)) + dot(wb, vec4(1.0)), 1e-8);
            wa *= g; wb *= g;
            m0 += vec4(c * wa.x, wa.x); s0 += cc * wa.x;  m2 += vec4(c * wa.y, wa.y); s2 += cc * wa.y;
            m4 += vec4(c * wa.z, wa.z); s4 += cc * wa.z;  m6 += vec4(c * wa.w, wa.w); s6 += cc * wa.w;
            m1 += vec4(c * wb.x, wb.x); s1 += cc * wb.x;  m3 += vec4(c * wb.y, wb.y); s3 += cc * wb.y;
            m5 += vec4(c * wb.z, wb.z); s5 += cc * wb.z;  m7 += vec4(c * wb.w, wb.w); s7 += cc * wb.w;
        }
    }
    vec4 o = vec4(0.0);
    o += sector(m0, s0, uK.y); o += sector(m1, s1, uK.y); o += sector(m2, s2, uK.y); o += sector(m3, s3, uK.y);
    o += sector(m4, s4, uK.y); o += sector(m5, s5, uK.y); o += sector(m6, s6, uK.y); o += sector(m7, s7, uK.y);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(o.w > 0.0 ? o.rgb / o.w : texture(sTD2DInputs[0], pc / fs).rgb, 1.0));
}
""".replace('RMAXB', str(2 * RMAX))

FX = """// kuwahara fx (compute). in0 in1, in1 kuw (bilinear up from Res). Amount mix, alpha from in1.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, -, -, -
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    vec3 k = texture(sTD2DInputs[1], (vec2(p) + 0.5) / vec2(isz)).rgb;
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(k, c.a), uA.x));
}
"""

SHADERS = {'tens': TENS, 'tblur': TBLUR, 'kuw': KUW, 'fx': FX}
NIN = {'tens': 1, 'tblur': 1, 'kuw': 2, 'fx': 2}     # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"
DIV = "(1 if parent().par.Res.eval() == 'full' else (2 if parent().par.Res.eval() == 'half' else 4))"


def uniforms():
    return {
        'tens': [('uT', [DIV, '0', '0', '0'])],
        'tblur': [],
        'kuw': [('uK', [P.format('Radius'), P.format('Sharpness'), P.format('Alpha'), DIV]),
                ('uZ', [P.format('Zeta'), P.format('Zerocross'), P.format('Anisotropy'), '0'])],
        'fx': [('uA', [P.format('Amount'), '0', '0', '0'])],
    }


def build(m, H):
    """in1 -> tens (Res) -> tblur -> kuw (+ in1) -> fx (+ in1) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    W = 'int(math.ceil(me.inputs[0].width / %s))' % DIV
    Hh = 'int(math.ceil(me.inputs[0].height / %s))' % DIV
    te = H['pas'](m, 'tens', TENS, [in1], W, Hh, 'rgba16float')
    H['uniforms'](te, U['tens'])
    te.comment = 'Structure tensor (rgb Sobel) at Res.'
    tb = H['pas'](m, 'tblur', TBLUR, [te], 'me.inputs[0].width', 'me.inputs[0].height', 'rgba16float')
    tb.comment = '5x5 Gaussian of the tensor.'
    kw = H['pas'](m, 'kuw', KUW, [in1, tb], 'me.inputs[1].width', 'me.inputs[1].height', 'rgba16float')
    H['uniforms'](kw, U['kuw'])
    kw.comment = 'Anisotropic generalized Kuwahara: 8 sectors on an edge-aligned ellipse.'
    fx = H['pas'](m, 'fx', FX, [in1, kw], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'Bilinear up from Res + Amount mix.'
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact.'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Tensor', 'role': 'process', 'ops': ['tens', 'tens_compute', 'tblur', 'tblur_compute'],
         'body': 'Edge orientation + anisotropy (structure tensor) at Res.'},
        {'title': '3 Paint', 'role': 'process', 'ops': ['kuw', 'kuw_compute', 'fx', 'fx_compute'],
         'body': '8-sector anisotropic Kuwahara; up to full res + Amount.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
