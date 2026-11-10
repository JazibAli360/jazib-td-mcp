# fx_analog_crt - FX_analog module 'crt' (FX2 AV-01..AV-06 + the AV-08 'monitor' presets; FX0 row 14).
# Template: docs/builds/fx_glitch.md "Module template" (FX_analog rack = the FX_glitch rack, builders/fx_analog.py).
# Control names, ranges and behaviour match StageLab JZB_Lofi_CRT (stagelab/ffgl/crt/CRT.cpp): Amount, Curvature,
# Scanlines, Mask, Halation, Degauss, Lines, Sharpness, Mask Size, Mask Strength, Corner, Vignette, Brightness, Border,
# Roll, Flicker, Hum Bar, Seed, Randomness (labels = the JZB names), so a look dialled in TD translates to Arena.
# Extras (Tube / Raster / Screen pages): convergence + focus (AV-06), phosphor persistence + scan bar (AV-05),
# interlace alternate / weave + crawl (AV-02), phosphor colours, LCD mask, damper wires, overscan, glass, line axis.
# Monitor menu = 13 named monitors (AV-08) applied as par sets of this module (no second engine).
# Passes, all compute (T-46/T-47):
#   raster  picture -> virtual raster (Lines, pitch >= 3 px, square virtual px), box average, rgba16float; history
#           (fb = its own last output) for phosphor persistence and interlace weave
#   glow    raster -> 1/8 output, two 7x7 Gaussians (near + wide) in linear light; only pulled while Halation > 0
#   fx      composite at the input size: warp + rounded screen + border, Gaussian beams of the two nearest lines,
#           sharpness, convergence, focus, phosphor colour, mask, damper, flicker, hum, vignette, scan bar, glass,
#           halation, roll + blanking bar, purity blotches / Degauss swirl; Amount crossfades over the equally warped
#           picture. Amount 0 with no Degauss running = texelFetch of the input (exact passthrough).
# Motion state (roll lock-in, flicker steps, hum, Degauss, field) = the `clock` Script CHOP running the same Python as
# the offline tests (builders/fx_analog_crt_logic.py, copied into `crt_logic`), fed to every pass as uniform array uK.
# ASCII only.
import os

MODULE = 'crt'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(_HERE, 'fx_analog_crt_logic.py')
CL = dict(globals())                     # TD names (textDAT, scriptCHOP, ...) for td_common (live fix)
with open(LOGIC_FILE) as _fh:
    exec(_fh.read(), CL)

MASK_LABELS = ['Off', 'Aperture (Trinitron stripes)', 'Slot (staggered slots)', 'Shadow (delta dots)',
               'LCD (cells)']
PAGES = [
    ('CRT', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Curvature', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Curvature'}),
        ('Scanlines', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Scanlines'}),
        ('Mask', 'Menu', 'aperture', {'names': CL['MASKS'], 'labels': MASK_LABELS, 'label': 'Mask'}),
        ('Halation', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Halation'}),
        ('Degauss', 'Pulse', None, {'label': 'Degauss'}),
        ('Monitor', 'Menu', 'custom', {'names': CL['monitor_names'](), 'labels': CL['monitor_labels'](),
                                       'label': 'Monitor (applies a whole set)'}),
    ]),
    ('Raster', [
        ('Lines', 'Int', 480, {'min': 120, 'max': 1080, 'label': 'Lines'}),
        ('Sharpness', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Sharpness'}),
        ('Masksize', 'Int', 6, {'min': 3, 'max': 12, 'label': 'Mask Size'}),
        ('Maskstrength', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Mask Strength'}),
        ('Beammin', 'Float', 0.15, {'min': 0.05, 'max': 0.5, 'label': 'Beam width (dark), lines'}),
        ('Beamgrow', 'Float', 0.2, {'min': 0, 'max': 0.6, 'label': 'Beam growth (bright)'}),
        ('Interlace', 'Menu', 'off', {'names': ['off', 'alternate', 'weave'],
                                      'labels': ['Off (progressive)', 'Alternate fields (30 Hz line flicker)',
                                                 'Weave (combing on motion)']}),
        ('Interdim', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Other field dim (Alternate)'}),
        ('Crawl', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Line crawl, lines/s'}),
        ('Lineaxis', 'Menu', 'x', {'names': ['x', 'y'],
                                   'labels': ['Lines across (TV upright)', 'Lines down (TV on its side)']}),
    ]),
    ('Screen', [
        ('Corner', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Corner'}),
        ('Vignette', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Vignette'}),
        ('Brightness', 'Float', 1.2, {'min': 0, 'max': 2, 'label': 'Brightness'}),
        ('Border', 'Menu', 'black', {'names': ['black', 'transparent'], 'labels': ['Black', 'Transparent'],
                                     'label': 'Border'}),
        ('Curveaxis', 'Menu', 'both', {'names': ['both', 'x', 'y'],
                                       'labels': ['Both (bulged glass)', 'Left/right edges only (Trinitron)',
                                                  'Top/bottom edges only']}),
        ('Overscan', 'Float', 0.0, {'min': 0, 'max': 0.15, 'label': 'Overscan'}),
        ('Glass', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Glass highlight'}),
        ('Damper', 'Int', 0, {'min': 0, 'max': 3, 'label': 'Damper wires'}),
    ]),
    ('Tube', [
        ('Phosphor', 'Menu', 'colour', {'names': CL['PHOSPHORS'],
                                        'labels': ['Colour (RGB)', 'White (P4)', 'Green (P1)', 'Amber (P3)']}),
        ('Convx', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Convergence X px (R +, B -)'}),
        ('Convy', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Convergence Y px (R +, B -)'}),
        ('Convedge', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Convergence edge growth'}),
        ('Focus', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Corner defocus'}),
        ('Persistr', 'Float', 0.0, {'min': 0, 'max': 0.98, 'label': 'Persistence R (per frame)'}),
        ('Persistg', 'Float', 0.0, {'min': 0, 'max': 0.98, 'label': 'Persistence G (per frame)'}),
        ('Persistb', 'Float', 0.0, {'min': 0, 'max': 0.98, 'label': 'Persistence B (per frame)'}),
        ('Glowradius', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Halation radius'}),
        ('Scanbar', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Scan bar (rolling beam)'}),
        ('Scanbarwidth', 'Float', 0.15, {'min': 0.01, 'max': 1, 'label': 'Scan bar tail (heights)'}),
        ('Scanbarspeed', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Scan bar speed, screens/s'}),
    ]),
    ('Motion', [
        ('Roll', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Roll'}),
        ('Flicker', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Flicker'}),
        ('Humbar', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Hum Bar'}),
    ]),
    ('Random', [
        ('Seed', 'Int', 1, {'min': 0, 'max': 99, 'label': 'Seed'}),
        ('Randomness', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Randomness'}),
    ]),
    ('State', [
        ('Degausstime', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Last Degauss (absTime s)'}),
        ('Degausscount', 'Int', 0, {'min': 0, 'max': 100, 'label': 'Degauss count'}),
    ]),
]
PANEL_PAGES = ['CRT', 'Raster', 'Screen', 'Tube', 'Motion', 'Random']
MENUS = dict((n, o['names']) for _pg, pars in PAGES for n, s, _d, o in pars if s == 'Menu')


def preset_vals(names_vals):
    """A look with menus by name -> zkit preset raw values (menus as index; Monitor = custom so recall is exact)."""
    out = {}
    for k, v in names_vals.items():
        out[k] = MENUS[k].index(v) if k in MENUS else v
    out['Monitor'] = 0
    return out


def _look(over):
    v = dict(CL['CRT_DEFAULTS'])
    v.update(over)
    return preset_vals(v)


_REC = dict((k, o) for k, _l, o in CL['JZB_RECIPES'])
_MON = dict((k, o) for k, _l, o in CL['MONITORS'])
# 8 zkit slots: the 5 JZB_Lofi_CRT recipes (same names as Arena's presets) + 3 monitors; all 13 via the Monitor menu.
PRESETS = [
    (1, 'Broadcast Monitor', _look(_REC['broadcast'])),
    (2, 'Arcade', _look(_REC['arcade'])),
    (3, 'Old Television', _look(_REC['oldtv'])),
    (4, 'Lost Sync', _look(_REC['lostsync'])),
    (5, 'Flat Scanlines', _look(_REC['flatscan'])),
    (6, 'Green terminal', _look(_MON['greenterm'])),
    (7, 'LED-wall safe', _look(_MON['ledwall'])),
    (8, 'Dead set', _look(_MON['deadset'])),
]

RASTER = """// FX_analog crt raster (compute, T-47). in0 = picture, in1 = this pass's last output (Feedback fb).
// Each texel = box average of its output-px block (logical frame: Lineaxis y = canvas turned), premultiplied.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uR;   // pitch vw vh lineaxis
uniform vec4 uP;   // persistence r g b, interlace mode (0 off 1 alternate 2 weave)
%(LIB)s
void main() {
    ivec2 cell = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    if (cell.x >= R.x || cell.y >= R.y) return;
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    bool ax = uR.w > 0.5;
    vec2 S = ax ? vec2(isz.yx) : vec2(isz);
    float pitch = max(uR.x, 1.0);
    vec2 bs = vec2(S.x / max(uR.y, 1.0), pitch);
    vec2 p0 = vec2(cell) * bs;
    vec2 p1 = min((vec2(cell) + 1.0) * bs, S);
    int taps = clamp((int(pitch) + 1) / 2, 1, 8);
    vec4 s = vec4(0.0);
    for (int j = 0; j < 8; j++) {
        if (j >= taps) break;
        for (int i = 0; i < 8; i++) {
            if (i >= taps) break;
            vec2 uv = clamp(mix(p0, p1, (vec2(float(i), float(j)) + 0.5) / float(taps)) / S, 0.0, 1.0);
            s += texture(sTD2DInputs[0], ax ? uv.yx : uv);
        }
    }
    s /= float(taps * taps);
    ivec2 psz = textureSize(sTD2DInputs[1], 0);
    if (psz == R && uK[8].w < 0.5) {                        // history valid (same size, no cook gap)
        vec4 pv = texelFetch(sTD2DInputs[1], cell, 0);
        int im = int(uP.w + 0.5);
        int field = int(uK[7].w + 0.5);
        if (im == 2 && (cell.y & 1) != field) s = pv;       // weave: the other field shows the previous frame
        else if (max(max(uP.x, uP.y), uP.z) > 0.0) {
            s.rgb = max(s.rgb, pv.rgb * uP.xyz);
            s.a = max(s.a, pv.a * max(max(uP.x, uP.y), uP.z));
        }
    }
    TDImageStoreOutput(0, ivec3(cell, 0), s);
}
"""

GLOW = """// FX_analog crt halation (compute). in0 = raster. Output 1/8 of the logical frame, linear light (gamma 2),
// near + wide 7x7 Gaussians (0.6 / 0.4), radius = Glowradius glow texels per tap.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uG;   // radius
vec3 lin(vec4 c) { vec3 u = c.a > 1e-5 ? clamp(c.rgb / c.a, 0.0, 1.0) : vec3(0.0); return u * u * c.a; }
void main() {
    ivec2 g = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    if (g.x >= R.x || g.y >= R.y) return;
    vec2 uv = (vec2(g) + 0.5) / vec2(R);
    vec2 stp = max(uG.x, 0.0) / vec2(R);
    vec3 n = vec3(0.0), w = vec3(0.0);
    float ws = 0.0;
    for (int j = -3; j <= 3; j++) {
        for (int i = -3; i <= 3; i++) {
            float k = exp(-float(i * i + j * j) / 4.5);
            vec2 o = vec2(float(i), float(j)) * stp;
            n += k * lin(texture(sTD2DInputs[0], uv + o));
            w += k * lin(texture(sTD2DInputs[0], uv + 3.0 * o));
            ws += k;
        }
    }
    TDImageStoreOutput(0, ivec3(g, 0), vec4((0.6 * n + 0.4 * w) / ws, 1.0));
}
"""

FX = """// FX_analog crt composite (compute, T-47; JZB_Lofi_CRT compositeShader + FX2 extras). in0 = picture,
// in1 = raster (vw x vh, logical), in2 = glow (1/8, linear) or 1x1 black while Halation is 0.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount curvature corner scanlines
uniform vec4 uB;   // sharp slope, mask type, mask size, mask strength
uniform vec4 uC;   // halation vignette brightness border (0 black, 1 transparent)
uniform vec4 uD;   // pitch vw vh lineaxis
uniform vec4 uE;   // beammin beamgrow focus damper
uniform vec4 uF;   // convx convy convedge curveaxis
uniform vec4 uG;   // interlace interdim overscan glass
uniform vec4 uH;   // scanbar scanbarwidth phosphor (0 colour 1 white 2 green 3 amber) 0
%(LIB)s
float AX;
vec2 SO;
vec4 tex0(vec2 t) { return texture(sTD2DInputs[0], AX > 0.5 ? t.yx : t); }

int maskChannel(ivec2 p) {                         // mirror of crt_logic.mask_channel
    int size = clamp(int(uB.z + 0.5), 3, 12);
    int type = int(uB.y + 0.5);
    int sub = size / 3;
    int x = max(p.x, 0), y = max(p.y, 0);
    if (type == 2) {
        int gap = max(1, size / 4);
        int yy = (y + ((x / size) & 1) * (size / 2)) % size;
        if (yy < gap) return -1;
    } else if (type == 3) {
        int rowH = max(2, (size + 1) / 2);
        int row = y / rowH;
        if (rowH >= 3 && y % rowH == rowH - 1) return -1;
        x += (row & 1) * (size / 2);
    } else if (type == 4) {
        if (size >= 4 && y % size == size - 1) return -1;
    }
    int k = (x % size) / sub;
    return k < 3 ? k : -1;
}
vec4 rasterAt(float u, float j) {
    float jj = clamp(j, 0.0, uD.z - 1.0);
    vec2 p = vec2(clamp(u, 0.5 / uD.y, 1.0 - 0.5 / uD.y), (jj + 0.5) / uD.z);
    return texture(sTD2DInputs[1], p);
}
vec4 lineAt(float u, float j) {                     // linear light (gamma 2) + alpha, line flicker, interlace dim
    vec4 c = rasterAt(u, j);
    vec3 rgb = c.a > 1e-5 ? clamp(c.rgb / c.a, 0.0, 1.0) : vec3(0.0);
    vec3 l = rgb * rgb;
    int ji = int(j) + 4096;
    float f = 1.0;
    if (uK[0].w > 0.0) f *= 1.0 - uK[0].w * h01(uint(ji) * 73856093u ^ uint(uK[1].x), uint(uK[2].w) + 5u);
    if (int(uG.x + 0.5) == 1 && (ji & 1) != int(uK[7].w + 0.5)) f *= 1.0 - uG.y;
    return vec4(l * f, c.a);
}
vec4 beamAt(vec2 ct, float du, float dl, float foc) {   // the two nearest lines as Gaussian beams
    float yl = ct.y * SO.y / uD.x + dl + uK[12].y;
    float j0 = floor(yl - 0.5);
    float d0 = yl - 0.5 - j0;
    float xv = ct.x * uD.y - 0.5;
    float xi = floor(xv);
    float xf = clamp((xv - xi - 0.5) * (uB.x / foc) + 0.5, 0.0, 1.0);
    float u = (xi + 0.5 + xf) / uD.y + du;
    vec4 L0 = lineAt(u, j0), L1 = lineAt(u, j0 + 1.0);
    vec3 s0 = (uE.x + uE.y * sqrt(L0.rgb)) * foc, s1 = (uE.x + uE.y * sqrt(L1.rgb)) * foc;
    vec3 e0 = d0 / s0, e1 = (1.0 - d0) / s1;
    vec3 bm = L0.rgb * exp(-0.5 * e0 * e0) + L1.rgb * exp(-0.5 * e1 * e1);
    return vec4(mix(mix(L0.rgb, L1.rgb, d0), bm, uA.w), mix(L0.a, L1.a, d0));
}
void main() {
    ivec2 P = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    if (P.x >= R.x || P.y >= R.y) return;
    vec4 src = texelFetch(sTD2DInputs[0], P, 0);
    float A = uA.x;
    if (A <= 0.0 && uK[3].w <= 0.0) { TDImageStoreOutput(0, ivec3(P, 0), src); return; }   // exact passthrough
    AX = uD.w;
    ivec2 q = AX > 0.5 ? P.yx : P;
    SO = AX > 0.5 ? vec2(R.yx) : vec2(R);
    vec2 uv = (vec2(q) + 0.5) / SO;
    float aspect = SO.x / SO.y;
    vec2 c = uv * 2.0 - 1.0;
    float k = uA.y * 0.25 * A;
    int cax = int(uF.w + 0.5);
    vec2 wk = vec2(cax == 2 ? 0.0 : k / aspect, cax == 1 ? 0.0 : k);
    vec2 cw = vec2(c.x * (1.0 + c.y * c.y * wk.x), c.y * (1.0 + c.x * c.x * wk.y));
    float cr = uA.z * 0.5 * A;
    vec2 qq = abs(cw) * vec2(aspect, 1.0) - vec2(aspect, 1.0) + cr;
    float d = length(max(qq, 0.0)) + min(max(qq.x, qq.y), 0.0) - cr;
    float tube = clamp(0.5 - d * SO.y * 0.5, 0.0, 1.0);
    vec2 t = (cw / (1.0 + uG.z * A)) * 0.5 + 0.5;
    t = degaussShake(t);
    vec4 col = A < 1.0 ? tex0(clamp(t, 0.0, 1.0)) : vec4(0.0);
    if (A > 0.0) {
        vec2 ct = t;
        bool blank = false;
        if (uK[0].x != 0.0) {                           // V-hold roll + blanking bar
            float s = mod(ct.y - uK[0].x, 1.0 + uK[0].y);
            blank = s > 1.0;
            ct.y = min(s, 1.0);
        }
        float r2 = dot(c, c) * 0.5;
        float foc = 1.0 + uE.z * r2 * 2.0;
        vec4 L = beamAt(ct, 0.0, 0.0, foc);
        vec3 lin = L.rgb;
        float a = L.a;
        float conv = uK[2].z;
        if (conv > 0.0 || uF.x != 0.0 || uF.y != 0.0) {    // misconvergence: R and B beams land elsewhere
            float grow = 1.0 + uF.z * r2;
            float duR = conv * (uK[9].x * cw.x + 0.5 * uK[9].y) / uD.y + uF.x * grow / SO.x;
            float duB = conv * (uK[9].z * cw.x + 0.5 * uK[9].w) / uD.y - uF.x * grow / SO.x;
            float dl = uF.y * grow / uD.x;
            lin.r = beamAt(ct, duR, dl, foc).r;
            lin.b = beamAt(ct, duB, -dl, foc).b;
        }
        int ph = int(uH.z + 0.5);
        if (ph > 0) {
            vec3 tint = ph == 1 ? vec3(0.93, 0.95, 1.0) : (ph == 2 ? vec3(0.25, 1.0, 0.35) : vec3(1.0, 0.62, 0.12));
            lin = dot(lin, vec3(0.2126, 0.7152, 0.0722)) * tint * tint;
        }
        if (uB.y > 0.5) {
            int mc = maskChannel(q);
            vec3 w = vec3(1.0 - uB.w);
            if (mc == 0) w.r = 1.0 + 0.5 * uB.w; else if (mc == 1) w.g = 1.0 + 0.5 * uB.w;
            else if (mc == 2) w.b = 1.0 + 0.5 * uB.w;
            lin *= w;
        }
        int nd = int(uE.w + 0.5);
        for (int i = 1; i <= 3; i++) {
            if (i > nd) break;
            if (q.y == int(SO.y * float(i) / float(nd + 1))) lin *= 0.3;
        }
        float kk = uC.z * uK[0].z;
        if (uK[1].y > 0.0) {
            float hb = 0.5 + 0.5 * cos(6.2831853 * (t.y - uK[1].z));
            hb *= hb;
            kk *= 1.0 - uK[1].y * hb * hb;
        }
        float vg = 0.5 * uC.y;
        if (vg > 0.0) {
            vec2 v = clamp(t, 0.0, 1.0) * (1.0 - clamp(t, 0.0, 1.0));
            kk *= pow(clamp(16.0 * v.x * v.y, 1e-4, 1.0), vg);
        }
        if (uH.x != 0.0) {                              // rolling beam: bright front, exponential tail above it
            float dd = mod(t.y - (1.0 - uK[12].z), 1.0);
            kk *= 1.0 + uH.x * (2.0 * exp(-dd / max(uH.y, 1e-3)) - 1.0);
        }
        vec3 Pm = lin * a * kk;
        vec3 G = uC.x > 0.0 ? uC.x * kk * texture(sTD2DInputs[2], ct).rgb : vec3(0.0);
        if (uG.w > 0.0) {
            vec2 e = (c - vec2(-0.45, 0.55)) * vec2(1.6, 2.4);
            G += vec3(uG.w * 0.25 * A * exp(-dot(e, e) * 2.0));
        }
        Pm += G;
        float aOut = max(a, min(1.0, sqrt(max(max(G.r, G.g), G.b))));
        vec3 rgb = sqrt(clamp(Pm / max(aOut, 1e-5), 0.0, 1.0)) * aOut;
        vec4 crt = blank ? vec4(0.0, 0.0, 0.0, uC.w > 0.5 ? 0.0 : 1.0) : vec4(rgb, aOut);
        col = mix(col, crt, A);
    }
    col.rgb *= purity(t, aspect);
    col *= tube;
    if (uC.w < 0.5) col.a += 1.0 - tube;
    col = clamp(col, 0.0, 1.0);
    col.rgb = min(col.rgb, vec3(col.a));
    TDImageStoreOutput(0, ivec3(P, 0), col);
}
"""


def shader_texts():
    """The three compute shaders exactly as the build writes them (tests compile these with glslc)."""
    lib = CL['GLSL_LIB']
    return {'raster': RASTER.replace('%(LIB)s', lib), 'glow': GLOW, 'fx': FX.replace('%(LIB)s', lib)}


P = "parent().par.{}.eval()"
L_ = "parent().op('crt_logic').module"
DIMS = "me.inputs[0].width, me.inputs[0].height"


def build(m, H):
    """Fill instance COMP m: in1 -> raster (+ fb history) -> glow -> fx -> out1, + crt_logic, clock, pulse_exec."""
    mk, expr = H['mk'], H['expr']
    T = shader_texts()
    in1 = mk(m, inTOP, 'in1')
    CL['td_common'](m, H, LOGIC_FILE, 'crt_logic', ['Degauss'], ['Monitor'])
    fb = mk(m, feedbackTOP, 'fb')
    if not fb.inputConnectors[0].connections:
        fb.inputConnectors[0].connect(in1)
    fb.par.top = 'raster'
    fb.comment = 'raster history (persistence / weave); the raster pass ignores it when its size differs or after a gap.'
    ras = H['compute'](m, 'raster', T['raster'], [in1, fb], fmt='rgba16float')
    for par, i in ((ras.par.resolutionw, 0), (ras.par.resolutionh, 1)):
        expr(par, "%s.raster_wh(%s, %s, parent().par.Lineaxis.menuIndex)[%d]" % (
            L_, "me.inputs[0].width, me.inputs[0].height", P.format('Lines'), i))
    ras.par.inputextenduv = 'hold'
    ras.par.inputfiltertype = 'linear'
    H['uniforms'](ras, [
        ('uR', ["%s.line_pitch(me.inputs[0].height if parent().par.Lineaxis.menuIndex == 0 else me.inputs[0].width, "
                "%s)" % (L_, P.format('Lines')), 'me.par.resolutionw.eval()', 'me.par.resolutionh.eval()',
                'parent().par.Lineaxis.menuIndex']),                # not me.width: own size = cook loop (live)
        ('uP', [P.format('Persistr'), P.format('Persistg'), P.format('Persistb'), 'parent().par.Interlace.menuIndex']),
    ])
    CL['td_clock_uniform'](ras)
    ras.comment = 'Virtual raster (Lines, >= 3 px per line, square px), rgba16f; persistence / weave from fb.'
    gl = H['compute'](m, 'glow', T['glow'], [ras], fmt='rgba16float')
    for par, i in ((gl.par.resolutionw, 0), (gl.par.resolutionh, 1)):
        expr(par, "%s.glow_wh(parent().op('in1').width, parent().op('in1').height, "
                  "parent().par.Lineaxis.menuIndex)[%d]" % (L_, i))
    gl.par.inputextenduv = 'hold'
    H['uniforms'](gl, [('uG', [P.format('Glowradius'), '0', '0', '0'])])
    gl.comment = 'Halation: 1/8 size, near + wide Gaussians in linear light. Pulled only while Halation > 0.'
    gn = mk(m, constantTOP, 'glow_none')
    gn.par.outputresolution = 'custom'
    gn.par.resolutionw, gn.par.resolutionh = 1, 1
    gn.par.colorr = gn.par.colorg = gn.par.colorb = 0
    gn.par.alpha = 0
    gs = mk(m, switchTOP, 'glow_src')
    gs.inputConnectors[0].connect(gn)
    gs.inputConnectors[1].connect(gl)
    expr(gs.par.index, '1 if %s > 0 else 0' % P.format('Halation'))
    gs.comment = 'Halation 0 -> 1x1 black (glow not cooked).'
    g = H['compute'](m, 'fx', T['fx'], [in1, ras, gs])
    g.par.inputextenduv = 'hold'
    g.par.inputfiltertype = 'linear'
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), P.format('Curvature'), P.format('Corner'), P.format('Scanlines')]),
        ('uB', ['%s.sharp_slope(%s)' % (L_, P.format('Sharpness')), 'parent().par.Mask.menuIndex',
                P.format('Masksize'), P.format('Maskstrength')]),
        ('uC', [P.format('Halation'), P.format('Vignette'), P.format('Brightness'), 'parent().par.Border.menuIndex']),
        ('uD', ["%s.line_pitch(me.inputs[0].height if parent().par.Lineaxis.menuIndex == 0 else me.inputs[0].width, "
                "%s)" % (L_, P.format('Lines')), "op('raster').width", "op('raster').height",
                'parent().par.Lineaxis.menuIndex']),
        ('uE', [P.format('Beammin'), P.format('Beamgrow'), P.format('Focus'), P.format('Damper')]),
        ('uF', [P.format('Convx'), P.format('Convy'), P.format('Convedge'), 'parent().par.Curveaxis.menuIndex']),
        ('uG', ['parent().par.Interlace.menuIndex', P.format('Interdim'), P.format('Overscan'), P.format('Glass')]),
        ('uH', [P.format('Scanbar'), P.format('Scanbarwidth'), 'parent().par.Phosphor.menuIndex', '0']),
    ])
    CL['td_clock_uniform'](g)
    g.comment = 'crt: beams + mask + geometry + halation + motion (JZB_Lofi_CRT names). Amount 0 = exact passthrough.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Clock', 'role': 'control', 'ops': ['crt_logic', 'clock', 'clock_callbacks', 'pulse_exec'],
         'body': 'Per-frame motion state (roll, flicker, hum, Degauss) -> uniform array uK. Pulses -> State page.'},
        {'title': '3 Raster + Halation', 'role': 'process',
         'ops': ['fb', 'raster', 'raster_compute', 'glow', 'glow_compute', 'glow_none', 'glow_src'],
         'body': 'Picture -> virtual raster (fb = its last output: persistence, weave) -> 1/8 glow (Halation > 0 only). '
                 'One stage: fb reads raster by reference, so split boxes overlapped (live).'},
        {'title': '4 Tube', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'One compute composite.'},
        {'title': '5 Out', 'role': 'output', 'ops': ['out1']},
    ]
