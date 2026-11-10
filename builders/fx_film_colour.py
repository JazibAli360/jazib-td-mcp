# fx_film_colour - FX_film module 'colour' (FX3 S1 + S2 + S3 + S5; FX0 rows 35, 79): an ACES-style colour pipeline.
# One compute pass + two Script TOPs (the LUT bank):
#   in (Inspace: sRGB / Rec.709 / linear / ACEScg / LogC3 / S-Log3 / ACEScct) -> ACEScg working (AP1 linear, matrices
#   from the primaries + Bradford, fx_film_colour_logic) -> grade: Exposure, white balance (Temperature / Tint), ASC
#   CDL (Slope / Offset / Power), Lift / Gamma / Gain (master + RGB), Contrast around Pivot, Saturation + Vibrance, in
#   linear or log (ACEScct, Gradespace) -> LUT A/B (.cube 3D or 1D, any DOMAIN; Lutin = the space the LUT expects,
#   Lutout = what it returns; tetrahedral or trilinear, Lutmorph A -> B, Lutmix) -> view: none (encode Outspace, e.g.
#   LogC3 = the flat LOG VIEW) or ACES SDR (Hill RRT+ODT fit -> sRGB), Gamut clip; Split = graded / ungraded wipe.
# LUT files are parsed in Python (lut_a / lut_b Script TOPs, cached by path + mtime, Reload pulse) into an rgba32float
# strip (fx_film_colour_logic.cube_strip) and read with texelFetch (exact, no float filtering needed). Amount 0 =
# exact passthrough. ASCII only.

MODULE = 'colour'

LOGIC_PATH = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/fx_film_colour_logic.py'
_CL = {}
with open(LOGIC_PATH) as _fh:
    exec(_fh.read(), _CL)
SPACES, LABELS = _CL['SPACES'], _CL['SPACE_LABELS']

PAGES = [
    ('Grade', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Inspace', 'Menu', 'srgb', {'names': SPACES, 'labels': LABELS}),
        ('Exposure', 'Float', 0.0, {'min': -6, 'max': 6, 'label': 'Exposure (stops)'}),
        ('Temperature', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Temperature (cool - warm)'}),
        ('Tint', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Tint (green - magenta)'}),
        ('Gradespace', 'Menu', 'linear', {'names': ['linear', 'log'], 'labels': ['Linear (ACEScg)', 'Log (ACEScct)']}),
        ('Contrast', 'Float', 1.0, {'min': 0.3, 'max': 2.5, 'label': 'Contrast'}),
        ('Pivot', 'Float', 0.18, {'min': 0.01, 'max': 1, 'label': 'Contrast pivot (linear)'}),
        ('Saturation', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Saturation'}),
        ('Vibrance', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Vibrance'}),
    ]),
    ('Wheels', [
        ('Lift', 'Float', 0.0, {'min': -0.5, 'max': 0.5, 'label': 'Lift (master)'}),
        ('Liftc', 'RGB', (0.0, 0.0, 0.0), {'label': 'Lift RGB'}),
        ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 3, 'label': 'Gamma (master)'}),
        ('Gammac', 'RGB', (1.0, 1.0, 1.0), {'label': 'Gamma RGB'}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Gain (master)'}),
        ('Gainc', 'RGB', (1.0, 1.0, 1.0), {'label': 'Gain RGB'}),
        ('Slope', 'RGB', (1.0, 1.0, 1.0), {'label': 'CDL slope'}),
        ('Offset', 'RGB', (0.0, 0.0, 0.0), {'label': 'CDL offset'}),
        ('Power', 'RGB', (1.0, 1.0, 1.0), {'label': 'CDL power'}),
    ]),
    ('LUT', [
        ('Lutfilea', 'Str', '', {'label': 'LUT A (.cube path)'}),
        ('Lutfileb', 'Str', '', {'label': 'LUT B (.cube path)'}),
        ('Lutin', 'Menu', 'logc3', {'names': SPACES, 'labels': LABELS}),
        ('Lutout', 'Menu', 'same', {'names': ['same'] + SPACES, 'labels': ['Same as LUT in'] + LABELS}),
        ('Lutmix', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'LUT mix'}),
        ('Lutmorph', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Morph A -> B'}),
        ('Interp', 'Menu', 'tetrahedral', {'names': ['tetrahedral', 'trilinear'], 'labels': ['Tetrahedral', 'Trilinear']}),
        ('Reload', 'Pulse', None, {'label': 'Reload LUT files'}),
    ]),
    ('View', [
        ('Viewmode', 'Menu', 'none', {'names': ['none', 'aces'],
                                      'labels': ['None (encode Outspace)', 'ACES SDR (Hill RRT+ODT) -> sRGB']}),
        ('Outspace', 'Menu', 'same', {'names': ['same'] + SPACES, 'labels': ['Same as in'] + LABELS}),
        ('Gamutclip', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Gamut clip (negatives -> grey)'}),
        ('Split', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Split (0 off; left = ungraded)'}),
        ('Splitline', 'Toggle', True, {'label': 'Split line'}),
    ]),
]
PANEL_PAGES = ['Grade', 'Wheels', 'LUT', 'View']

PRESETS = [
    (1, 'neutral aces', {'Amount': 1.0, 'Inspace': 0, 'Viewmode': 1, 'Exposure': 0.5, 'Contrast': 1.0,
                         'Saturation': 1.0, 'Gradespace': 0}),
    (2, 'log view', {'Amount': 1.0, 'Inspace': 0, 'Viewmode': 0, 'Outspace': 5, 'Saturation': 1.0, 'Exposure': 0.0}),
    (3, 'teal orange', {'Amount': 1.0, 'Inspace': 0, 'Gradespace': 1, 'Liftcr': -0.02, 'Liftcg': 0.0, 'Liftcb': 0.03,
                        'Gaincr': 1.08, 'Gaincg': 1.0, 'Gaincb': 0.92, 'Contrast': 1.15, 'Saturation': 1.1,
                        'Vibrance': 0.3, 'Viewmode': 0, 'Outspace': 0}),
    (4, 'warm print', {'Amount': 1.0, 'Inspace': 0, 'Temperature': 0.6, 'Tint': 0.1, 'Slopeb': 0.95, 'Offsetr': 0.005,
                       'Contrast': 1.1, 'Saturation': 0.9, 'Viewmode': 1}),
    (5, 'bleak cold', {'Amount': 1.0, 'Inspace': 0, 'Temperature': -0.7, 'Saturation': 0.55, 'Lift': 0.03,
                       'Gamma': 1.1, 'Contrast': 1.2, 'Viewmode': 0, 'Outspace': 0}),
]


def _consts():
    L = _CL
    rows = []
    for p in L['PRIM_ORDER']:
        rows += ['vec3(%r, %r, %r)' % tuple(r) for r in L['TO_AP1'][p]]
    frows = []
    for p in L['PRIM_ORDER']:
        frows += ['vec3(%r, %r, %r)' % tuple(r) for r in L['FROM_AP1'][p]]
    curve = ', '.join(str(L['CURVE'][s]) for s in SPACES)
    prim = ', '.join(str(L['PRIM_ORDER'].index(L['PRIM_OF'][s])) for s in SPACES)
    return ('const vec3 TOAP1[12] = vec3[12](%s);\nconst vec3 FROMAP1[12] = vec3[12](%s);\n'
            'const int SCURVE[7] = int[7](%s);\nconst int SPRIM[7] = int[7](%s);\nconst vec3 AP1Y = vec3(%r, %r, %r);\n'
            % ((', '.join(rows), ', '.join(frows), curve, prim) + tuple(L['AP1_Y'])))


SHADER = """// FX_film colour (compute). in0 = picture, in1 = LUT A strip, in2 = LUT B strip (fx_film_colour_logic.cube_strip).
// uA amount inspace outspace(-1 same) view | uB exposure temp tint gradespace | uC slope rgb contrast
// uD offset rgb pivot | uE power rgb sat | uF lift rgb vibrance | uG gamma rgb gamutclip | uH gain rgb lutmix
// uI lutin lutout(-1 same) morph interp(0 tetra 1 tri) | uJ split splitline - -
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
uniform vec4 uE;
uniform vec4 uF;
uniform vec4 uG;
uniform vec4 uH;
uniform vec4 uI;
uniform vec4 uJ;
%s
%s
const vec3 HILL_IN0 = vec3(0.59719, 0.35458, 0.04823), HILL_IN1 = vec3(0.07600, 0.90834, 0.01566),
           HILL_IN2 = vec3(0.02840, 0.13383, 0.83777);
const vec3 HILL_OUT0 = vec3(1.60475, -0.53108, -0.07367), HILL_OUT1 = vec3(-0.10208, 1.10813, -0.00605),
           HILL_OUT2 = vec3(-0.00327, -0.07276, 1.07602);
float dec1(float v, int c) {
    if (c == 0) return v <= 0.04045 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4);
    if (c == 1) return v < 0.081 ? v / 4.5 : pow((v + 0.099) / 1.099, 1.0 / 0.45);
    if (c == 3) return v > 5.367655 * 0.010591 + 0.092809 ? (pow(10.0, (v - 0.385537) / 0.247190) - 0.052272) / 5.555556
                                                          : (v - 0.092809) / 5.367655;
    if (c == 4) return v >= 171.2102946929 / 1023.0 ? pow(10.0, (v * 1023.0 - 420.0) / 261.5) * 0.19 - 0.01
                                                   : (v * 1023.0 - 95.0) * 0.01125 / (171.2102946929 - 95.0);
    if (c == 5) return v <= 0.155251141552511 ? (v - 0.0729055341958355) / 10.5402377416545 : exp2(v * 17.52 - 9.72);
    return v;
}
float enc1(float x, int c) {
    if (c == 0) { x = max(x, 0.0); return x <= 0.0031308 ? x * 12.92 : 1.055 * pow(x, 1.0 / 2.4) - 0.055; }
    if (c == 1) { x = max(x, 0.0); return x < 0.018 ? 4.5 * x : 1.099 * pow(x, 0.45) - 0.099; }
    if (c == 3) return x > 0.010591 ? 0.247190 * log(max(5.555556 * x + 0.052272, 1e-10)) / log(10.0) + 0.385537
                                    : 5.367655 * x + 0.092809;
    if (c == 4) return x >= 0.01125 ? (420.0 + log(max((x + 0.01) / 0.19, 1e-10)) / log(10.0) * 261.5) / 1023.0
                                    : (x * (171.2102946929 - 95.0) / 0.01125 + 95.0) / 1023.0;
    if (c == 5) return x <= 0.0078125 ? 10.5402377416545 * x + 0.0729055341958355 : (log2(max(x, 1e-10)) + 9.72) / 17.52;
    return x;
}
vec3 dec3(vec3 v, int c) { return vec3(dec1(v.r, c), dec1(v.g, c), dec1(v.b, c)); }
vec3 enc3(vec3 v, int c) { return vec3(enc1(v.r, c), enc1(v.g, c), enc1(v.b, c)); }
vec3 toAP1(vec3 v, int sp) { int k = 3 * SPRIM[sp]; v = dec3(v, SCURVE[sp]);
    return vec3(dot(TOAP1[k], v), dot(TOAP1[k + 1], v), dot(TOAP1[k + 2], v)); }
vec3 fromAP1lin(vec3 w, int sp) { int k = 3 * SPRIM[sp];
    return vec3(dot(FROMAP1[k], w), dot(FROMAP1[k + 1], w), dot(FROMAP1[k + 2], w)); }
vec3 lutC(int s, int n, int r, int g, int b) {
    ivec2 c = ivec2(b * n + r, g);
    return s == 1 ? texelFetch(sTD2DInputs[1], c, 0).rgb : texelFetch(sTD2DInputs[2], c, 0).rgb;
}
vec4 lutHead(int s, int k) {
    int h = s == 1 ? textureSize(sTD2DInputs[1], 0).y : textureSize(sTD2DInputs[2], 0).y;
    return s == 1 ? texelFetch(sTD2DInputs[1], ivec2(k, h - 1), 0) : texelFetch(sTD2DInputs[2], ivec2(k, h - 1), 0);
}
bool lutValid(int s) { return lutHead(s, 1).w > 0.5; }
vec3 lut3(int s, vec3 v, int tri) {                       // fx_film_colour_logic.lut_apply
    vec4 h0 = lutHead(s, 0), h1 = lutHead(s, 1);
    int n = int(h0.w + 0.5);
    vec3 x = clamp((v - h0.rgb) / max(h1.rgb - h0.rgb, vec3(1e-9)), 0.0, 1.0) * float(n - 1);
    ivec3 i = min(ivec3(floor(x)), ivec3(n - 2));
    vec3 f = x - vec3(i);
    if (tri == 1) {
        vec3 c00 = mix(lutC(s, n, i.x, i.y, i.z), lutC(s, n, i.x + 1, i.y, i.z), f.x);
        vec3 c10 = mix(lutC(s, n, i.x, i.y + 1, i.z), lutC(s, n, i.x + 1, i.y + 1, i.z), f.x);
        vec3 c01 = mix(lutC(s, n, i.x, i.y, i.z + 1), lutC(s, n, i.x + 1, i.y, i.z + 1), f.x);
        vec3 c11 = mix(lutC(s, n, i.x, i.y + 1, i.z + 1), lutC(s, n, i.x + 1, i.y + 1, i.z + 1), f.x);
        return mix(mix(c00, c10, f.y), mix(c01, c11, f.y), f.z);
    }
    vec3 c000 = lutC(s, n, i.x, i.y, i.z), c111 = lutC(s, n, i.x + 1, i.y + 1, i.z + 1);
    if (f.x >= f.y) {
        if (f.y >= f.z) return (1.0 - f.x) * c000 + (f.x - f.y) * lutC(s, n, i.x + 1, i.y, i.z)
                             + (f.y - f.z) * lutC(s, n, i.x + 1, i.y + 1, i.z) + f.z * c111;
        if (f.x >= f.z) return (1.0 - f.x) * c000 + (f.x - f.z) * lutC(s, n, i.x + 1, i.y, i.z)
                             + (f.z - f.y) * lutC(s, n, i.x + 1, i.y, i.z + 1) + f.y * c111;
        return (1.0 - f.z) * c000 + (f.z - f.x) * lutC(s, n, i.x, i.y, i.z + 1)
             + (f.x - f.y) * lutC(s, n, i.x + 1, i.y, i.z + 1) + f.y * c111;
    }
    if (f.z >= f.y) return (1.0 - f.z) * c000 + (f.z - f.y) * lutC(s, n, i.x, i.y, i.z + 1)
                         + (f.y - f.x) * lutC(s, n, i.x, i.y + 1, i.z + 1) + f.x * c111;
    if (f.z >= f.x) return (1.0 - f.y) * c000 + (f.y - f.z) * lutC(s, n, i.x, i.y + 1, i.z)
                         + (f.z - f.x) * lutC(s, n, i.x, i.y + 1, i.z + 1) + f.x * c111;
    return (1.0 - f.y) * c000 + (f.y - f.x) * lutC(s, n, i.x, i.y + 1, i.z)
         + (f.x - f.z) * lutC(s, n, i.x + 1, i.y + 1, i.z) + f.z * c111;
}
float lgg1(float x, float lift, float gam, float gain) {
    float y = gain * (x + lift * (1.0 - x));
    return sign(y) * pow(abs(y), 1.0 / max(gam, 1e-4));
}
float cdl1(float x, float sl, float of, float pw) { float y = x * sl + of; return y > 0.0 ? pow(y, pw) : y; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }
    float sx = (float(p.x) + 0.5) / float(isz.x);
    if (uJ.x > 0.0 && sx < uJ.x) {                          // split: left = ungraded, 2 px line
        bool ln = uJ.y > 0.5 && abs(float(p.x) + 0.5 - uJ.x * float(isz.x)) < 1.0;
        TDImageStoreOutput(0, ivec3(p, 0), ln ? vec4(1.0, 1.0, 1.0, c.a) : c);
        return;
    }
    int ins = int(uA.y + 0.5);
    vec3 w = toAP1(c.rgb, ins);
    vec3 wb = vec3(exp2(0.25 * uB.y), exp2(-0.25 * uB.z), exp2(-0.25 * uB.y));
    w *= exp2(uB.x) * wb / dot(AP1Y, wb);
    bool lg = uB.w > 0.5;
    if (lg) w = enc3(w, 5);
    w = vec3(lgg1(cdl1(w.r, uC.r, uD.r, uE.r), uF.r, uG.r, uH.r), lgg1(cdl1(w.g, uC.g, uD.g, uE.g), uF.g, uG.g, uH.g),
             lgg1(cdl1(w.b, uC.b, uD.b, uE.b), uF.b, uG.b, uH.b));
    if (lg) { float pl = enc1(uD.w, 5); w = dec3((w - pl) * uC.w + pl, 5); }
    else w = sign(w) * uD.w * pow(abs(w) / uD.w, vec3(uC.w));
    float y = dot(AP1Y, w), mx = max(w.r, max(w.g, w.b)), mn = min(w.r, min(w.g, w.b));
    float ch = mx > 1e-6 ? clamp((mx - mn) / mx, 0.0, 1.0) : 0.0;
    w = y + (w - y) * (uE.w * (1.0 + uF.w * (1.0 - ch)));
    bool va = lutValid(1), vb = lutValid(2);
    if ((va || vb) && uH.w > 0.0) {
        int li = int(uI.x + 0.5), lo = uI.y < -0.5 ? li : int(uI.y + 0.5), tri = int(uI.w + 0.5);
        vec3 v = enc3(fromAP1lin(w, li), SCURVE[li]);
        vec3 la = va ? lut3(1, v, tri) : v;
        vec3 lb = vb ? lut3(2, v, tri) : la;
        v = mix(v, mix(la, lb, uI.z), uH.w);
        w = toAP1(v, lo);
    }
    vec3 o;
    if (uA.w > 0.5) {                                        // ACES SDR: Hill RRT+ODT fit on linear Rec.709 -> sRGB
        vec3 l = fromAP1lin(w, 2);
        vec3 v = vec3(dot(HILL_IN0, l), dot(HILL_IN1, l), dot(HILL_IN2, l));
        v = (v * (v + 0.0245786) - 0.000090537) / (v * (0.983729 * v + 0.4329510) + 0.238081);
        o = lin2srgb(clamp(vec3(dot(HILL_OUT0, v), dot(HILL_OUT1, v), dot(HILL_OUT2, v)), 0.0, 1.0));
    } else {
        int os = uA.z < -0.5 ? ins : int(uA.z + 0.5);
        vec3 l = fromAP1lin(w, os);
        float m2 = min(l.r, min(l.g, l.b)), y2 = dot(AP1Y, w);
        if (uG.w > 0.0 && m2 < 0.0 && y2 > m2) l = mix(l, vec3(y2), uG.w * (-m2) / (y2 - m2));
        o = enc3(l, SCURVE[os]);
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(mix(c.rgb, o, uA.x), c.a));
}
"""

LUT_CB = """# lut_a / lut_b Script TOP: parse the .cube named by parent().par.Lutfile<a|b> into an rgba32float strip
# (fx_film_colour_logic.cube_strip). Parsed once per (path, mtime, size, reload); storage holds arrays only (T-67).
# The cache uses the plain storage dict, not fetch/store: store() inside its own cook made a cook dependency loop
# (T-156).
import os
LOGIC = %r
def onSetupParameters(scriptOp):
    return
def onCook(scriptOp):
    m = scriptOp.parent()
    slot = scriptOp.name[-1]
    path = (getattr(m.par, 'Lutfile' + slot).eval() or '').strip()
    st = scriptOp.storage
    key = (path, os.path.getmtime(path) if path and os.path.isfile(path) else 0,
           os.path.getsize(path) if path and os.path.isfile(path) else 0, st.get('reload', 0))
    if st.get('key') != key or st.get('arr') is None:
        ns = {}
        exec(open(LOGIC).read(), ns)
        cube, err = None, ''
        if path:
            try:
                cube = ns['parse_cube'](open(path).read())
            except Exception as e:
                err = '%%s: %%s' %% (os.path.basename(path), e)
        st['arr'] = ns['cube_strip'](cube)
        st['key'] = key
        st['err'] = err
        st['title'] = cube['title'] if cube else ''
    err = st.get('err', '')
    if err:
        scriptOp.addWarning(err)
    scriptOp.copyNumpyArray(st['arr'])
    return
""" % LOGIC_PATH

RELOAD_EXEC = """# Reload pulse -> bump the lut Script TOPs' reload counter and recook them.
def onPulse(par):
    if par.name == 'Reload':
        for n in ('lut_a', 'lut_b'):
            s = par.owner.op(n)
            if s is not None:
                s.storage['reload'] = s.storage.get('reload', 0) + 1
                s.cook(force=True)
    return
"""


def shaders(H):
    return {'fx': SHADER % (H['LIB'], _consts())}


def _idx(par, base=0):
    return "parent().par.%s.menuIndex" % par if not base else "parent().par.%s.menuIndex - 1" % par


def build(m, H):
    """in1 + lut_a + lut_b (Script TOPs) -> fx (one compute pass) -> out1, + reload_exec."""
    mk, P = H['mk'], H['P']
    in1 = mk(m, inTOP, 'in1')
    luts = []
    for slot in 'ab':
        s = mk(m, scriptTOP, 'lut_' + slot)
        cb = m.op('lut_%s_callbacks' % slot)
        if cb is None:
            cb = mk(m, textDAT, 'lut_%s_callbacks' % slot)
            cb.dock = s
        if cb.text != LUT_CB:
            cb.text = LUT_CB
        s.par.callbacks = cb.name
        s.par.format = 'rgba32float'
        s.comment = 'LUT %s strip: .cube from parent().par.Lutfile%s (cached by path + mtime; Reload pulse).' % (
            slot.upper(), slot)
        luts.append(s)
    g = H['compute'](m, 'fx', shaders(H)['fx'], [in1] + luts)
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), _idx('Inspace'), _idx('Outspace', 1), _idx('Viewmode')]),
        ('uB', [P.format('Exposure'), P.format('Temperature'), P.format('Tint'), _idx('Gradespace')]),
        ('uC', [P.format('Sloper'), P.format('Slopeg'), P.format('Slopeb'), P.format('Contrast')]),
        ('uD', [P.format('Offsetr'), P.format('Offsetg'), P.format('Offsetb'), 'max(%s, 1e-4)' % P.format('Pivot')]),
        ('uE', [P.format('Powerr'), P.format('Powerg'), P.format('Powerb'), P.format('Saturation')]),
        ('uF', ['%s + %s' % (P.format('Lift'), P.format('Liftc' + ch)) for ch in 'rgb'] + [P.format('Vibrance')]),
        ('uG', ['%s * %s' % (P.format('Gamma'), P.format('Gammac' + ch)) for ch in 'rgb'] + [P.format('Gamutclip')]),
        ('uH', ['%s * %s' % (P.format('Gain'), P.format('Gainc' + ch)) for ch in 'rgb'] + [P.format('Lutmix')]),
        ('uI', [_idx('Lutin'), _idx('Lutout', 1), P.format('Lutmorph'), _idx('Interp')]),
        ('uJ', [P.format('Split'), '1 if %s else 0' % P.format('Splitline'), '0', '0']),
    ])
    g.comment = 'colour: in -> ACEScg, exposure / WB / CDL / LGG / contrast / sat, LUT A/B, view (log / ACES SDR).'
    pe = mk(m, parameterexecuteDAT, 'reload_exec')
    if pe.text != RELOAD_EXEC:
        pe.text = RELOAD_EXEC
        pe.par.active = False                                # T-97: toggle after a text rewrite
    pe.par.op = '..'
    pe.par.pars = 'Reload'
    pe.par.valuechange = False
    pe.par.onpulse = True
    pe.par.active = True
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In + LUTs', 'role': 'input',
         'ops': ['in1', 'lut_a', 'lut_a_callbacks', 'lut_b', 'lut_b_callbacks', 'reload_exec'],
         'body': 'lut_a / lut_b: .cube -> rgba32float strip (Script TOP, cached); Reload pulse re-reads.'},
        {'title': '2 Colour', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One pass: in -> ACEScg, grade, LUT A/B, view. Amount 0 = exact passthrough.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
