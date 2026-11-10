# fx_retro_scaler - FX_retro module 'scaler' (FX7a SX-09 shimmer-free pixel scalers for low-res sources). Clean-room
# GLSL (no libretro file copied, so no per-file licence to carry): the ideas are the public ones - sharp bilinear /
# box-filter pixel AA (blend only across one output pixel at texel edges), EPX / Scale2x corner rule (Eric Johnston
# 1992, the classic public algorithm), and a diagonal variant that cuts each Scale2x corner on a 45 degree line with a
# one-output-pixel antialiased edge (clean diagonals, no staircase).
# Source = this slot's picture reduced to a virtual grid (Pixelsize, centre / box) by `low`, or any low-res TOP
# (Sourcetop: a game capture, pixel art clip, a TD low-res render). `fx` scales it to the rack size: Fit stretch /
# fit (aspect kept, borders transparent) / integer (largest whole scale, the classic no-shimmer case). Taps are
# texelFetch only (manual bilinear), so the numpy mirror (fx_retro_scaler_logic.py) is exact. Premultiplied out,
# Amount mix; out_sel: Amount 0 = in1 exactly. ASCII only.

MODULE = 'scaler'
MODES = ['nearest', 'sharp', 'epx', 'diag']
FITS = ['stretch', 'fit', 'integer']


def pages(Lg):
    return [
        ('Scaler', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Mode', 'Menu', 'diag', {'names': MODES, 'labels': ['Nearest', 'Sharp bilinear (pixel AA)',
                                                                 'EPX / Scale2x corners', 'Diagonal (AA 45 deg)']}),
            ('Sharpness', 'Float', 1.0, {'min': 0.05, 'max': 4, 'label': 'Sharpness (1 = one output px blend)'}),
            ('Tolerance', 'Float', 0.04, {'min': 0, 'max': 0.5, 'label': 'Colour equal tolerance (EPX / diag)'}),
            ('Fit', 'Menu', 'stretch', {'names': FITS, 'labels': ['Stretch', 'Fit (keep aspect)',
                                                                  'Integer scale']}),
            ('Source', 'Menu', 'grid', {'names': ['grid', 'top'], 'labels': ['This picture on a pixel grid',
                                                                             'Source TOP (low res)']}),
            ('Pixelsize', 'Float', 8.0, {'min': 1, 'max': 64, 'label': 'Pixel size (grid source)'}),
            ('Sampling', 'Menu', 'centre', {'names': ['centre', 'box'], 'labels': ['Centre pixel', 'Box average']}),
        ]),
        ('Inputs', [
            ('Sourcetop', 'TOP', '', {'label': 'Source TOP (Source = top)'}),
        ]),
    ]


PANEL_PAGES = ['Scaler']


def presets(Lg):
    D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in pages(Lg) for n, s, d, o in pl
             if s != 'TOP')
    return [
        (1, 'clean diagonals', dict(D, Mode=3, Pixelsize=8.0)),
        (2, 'sharp bilinear', dict(D, Mode=1, Sharpness=1.0, Pixelsize=6.0)),
        (3, 'scale2x', dict(D, Mode=2, Pixelsize=10.0)),
        (4, 'soft pixels', dict(D, Mode=1, Sharpness=0.3, Pixelsize=12.0, Sampling=1)),
        (5, 'integer nearest', dict(D, Mode=0, Fit=2, Pixelsize=4.0)),
    ]


LOW = """// FX_retro scaler low pass: the picture on a virtual grid (VW x VH, straight colour). in0 = picture.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // psx psy sampling -
void main() {
    ivec2 v = ivec2(gl_GlobalInvocationID.xy);
    ivec2 vg = ivec2(uTDOutputInfo.res.zw);
    if (v.x >= vg.x || v.y >= vg.y) return;
    ivec2 res = textureSize(sTD2DInputs[0], 0);
    ivec2 ps = ivec2(max(int(uA.x + 0.5), 1), max(int(uA.y + 0.5), 1));
    ivec2 o = v * ps;
    vec4 s;
    if (uA.z < 0.5) s = texelFetch(sTD2DInputs[0], min(o + ps / 2, res - 1), 0);
    else {
        vec4 acc = vec4(0.0); int n = 0;
        for (int y = 0; y < 64; y++) {
            if (y >= ps.y || o.y + y >= res.y) break;
            for (int x = 0; x < 64; x++) {
                if (x >= ps.x || o.x + x >= res.x) break;
                acc += texelFetch(sTD2DInputs[0], o + ivec2(x, y), 0); n++;
            }
        }
        s = acc / float(max(n, 1));
    }
    TDImageStoreOutput(0, ivec3(v, 0), s);
}
"""

FX = """// FX_retro scaler fx pass (compute, full res). in0 = picture (Amount mix), in1 = source (low or Source TOP).
// = fx_retro_scaler_logic.render
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount mode sharpness tolerance
uniform vec4 uB;   // fit, premultiplied source (1 = Source TOP), -, -
ivec2 S;
vec4 F(ivec2 i) { return texelFetch(sTD2DInputs[1], clamp(i, ivec2(0), S - 1), 0); }
vec4 bil(vec2 q) {                                       // texel space, centres at i + 0.5
    vec2 x = q - 0.5; vec2 i0 = floor(x); vec2 f = x - i0; ivec2 i = ivec2(i0);
    return mix(mix(F(i), F(i + ivec2(1, 0)), f.x), mix(F(i + ivec2(0, 1)), F(i + ivec2(1, 1)), f.x), f.y);
}
bool eq(vec4 a, vec4 b) { vec4 d = abs(a - b); return max(max(d.r, d.g), max(d.b, d.a)) <= uA.w; }
float cover(float d, float w) { return clamp(d / max(w, 1e-4) + 0.5, 0.0, 1.0); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 res = textureSize(sTD2DInputs[0], 0);
    if (p.x >= res.x || p.y >= res.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    S = textureSize(sTD2DInputs[1], 0);
    vec2 SZ = vec2(res), Sf = vec2(S);
    vec2 sc = SZ / Sf;
    int fit = int(uB.x + 0.5);
    if (fit == 1) sc = vec2(min(sc.x, sc.y));
    else if (fit == 2) sc = vec2(max(1.0, floor(min(sc.x, sc.y))));
    vec2 off = 0.5 * (SZ - Sf * sc);
    vec2 t = (vec2(p) + 0.5 - off) / sc;
    vec4 o = vec4(0.0);
    if (t.x >= 0.0 && t.y >= 0.0 && t.x < Sf.x && t.y < Sf.y) {
        int mode = int(uA.y + 0.5);
        ivec2 i = ivec2(floor(t));
        vec2 fr = t - vec2(i);
        if (mode == 0) o = F(i);
        else if (mode == 1) {
            vec2 k = max(sc * uA.z, vec2(1.0));
            vec2 rr = 0.5 - 0.5 / k;
            vec2 cd = fr - 0.5;
            vec2 f = (cd - clamp(cd, -rr, rr)) * k + 0.5;
            o = bil(vec2(i) + f);
        } else {
            vec4 P = F(i), A = F(i + ivec2(0, 1)), B = F(i + ivec2(1, 0)), C = F(i - ivec2(1, 0)), D = F(i - ivec2(0, 1));
            bool r0 = eq(C, A) && !eq(C, D) && !eq(A, B);    // top-left    -> A
            bool r1 = eq(A, B) && !eq(A, C) && !eq(B, D);    // top-right   -> B
            bool r2 = eq(D, C) && !eq(D, B) && !eq(C, A);    // bottom-left -> C
            bool r3 = eq(B, D) && !eq(B, A) && !eq(D, C);    // bottom-right-> D
            if (mode == 2) {
                bool top = fr.y >= 0.5, right = fr.x >= 0.5;
                o = P;
                if (top && !right && r0) o = A;
                else if (top && right && r1) o = B;
                else if (!top && !right && r2) o = C;
                else if (!top && right && r3) o = D;
            } else {
                float w = 1.0 / max(min(sc.x, sc.y) * uA.z, 1e-3);      // one output px across the 45 deg edge
                float u = 0.5 - fr.x, v = fr.y - 0.5;                   // toward left, toward top
                o = P;
                if (r0) o = mix(o, A, cover((u + v - 0.5) * 0.7071, w));
                if (r1) o = mix(o, B, cover((-u + v - 0.5) * 0.7071, w));
                if (r2) o = mix(o, C, cover((u - v - 0.5) * 0.7071, w));
                if (r3) o = mix(o, D, cover((-u - v - 0.5) * 0.7071, w));
            }
        }
        if (uB.y < 0.5) o.rgb *= o.a;                        // grid source is straight: premultiply
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c0, o, uA.x));
}
"""


def shader_texts(lib):
    return {'low': LOW, 'fx': FX}


def uniforms(H):
    P, LX = H['P'], H['LX']
    W, Hh = "op('in1').width", "op('in1').height"
    grid = "%s.vgrid(%s, %s, %s)" % (LX, W, Hh, P.format('Pixelsize'))
    topsrc = "(parent().par.Source.eval() == 'top' and parent().par.Sourcetop.eval() is not None)"
    low = [('uA', [grid + '[0]', grid + '[1]', 'parent().par.Sampling.menuIndex', '0'])]
    fx = [('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Sharpness'), P.format('Tolerance')]),
          ('uB', ['parent().par.Fit.menuIndex', '1 if %s else 0' % topsrc, '0', '0'])]
    return low, fx, grid, topsrc


def build(m, H, Lg):
    """in1 -> low (virtual grid) | src_top (Select: Sourcetop) -> src (Switch) -> fx (full res) -> out_sel -> out1."""
    mk, expr, compute = H['mk'], H['expr'], H['compute']
    in1 = mk(m, inTOP, 'in1')
    U1, U2, grid, topsrc = uniforms(H)
    sh = shader_texts(None)
    low = compute(m, 'low', sh['low'], [in1], grid + '[2]', grid + '[3]', fmt='rgba16float', uniforms=U1)
    low.comment = 'scaler: the picture on a virtual grid (Pixelsize, centre / box).'
    st = mk(m, selectTOP, 'src_top')
    expr(st.par.top, "parent().par.Sourcetop.eval().path if %s else me.parent().op('low').path" % topsrc)
    st.comment = 'Source TOP (Inputs page) while Source = top, else low.'
    src = mk(m, switchTOP, 'src')
    src.inputConnectors[0].connect(low)
    src.inputConnectors[1].connect(st)
    expr(src.par.index, '1 if %s else 0' % topsrc)
    src.comment = 'Scaler source: low (grid) or the Source TOP (its own resolution).'
    fx = compute(m, 'fx', sh['fx'], [in1, src], "me.inputs[0].width", "me.inputs[0].height", uniforms=U2)
    fx.comment = 'scaler: nearest / sharp bilinear / EPX / diagonal AA to the rack size (Fit stretch / fit / integer).'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '0 if parent().par.Amount.eval() <= 0 else 1')
    sel.comment = 'Amount 0 = in1 exactly.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'low', 'low_compute', 'src_top', 'src'],
         'body': 'Source: the picture on a pixel grid, or a low-res Source TOP.'},
        {'title': '2 Scale', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'Nearest / sharp bilinear / EPX corners / diagonal AA.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
