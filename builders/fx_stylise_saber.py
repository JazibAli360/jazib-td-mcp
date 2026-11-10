# fx_stylise_saber - FX_stylise module 'saber' (FX7c 7C-09 energy beam on paths / text / masks; Video Copilot Saber
# look: hot core, exponential glow with Spread / Bias, noise distortion, flicker, draw-on Start / End). Template:
# docs/builds/fx_glitch.md "Module template" (rack = builders/fx_stylise.py). Doc: docs/builds/fx_stylise.md. Numpy
# mirror: builders/fx_stylise_saber_logic.py.
# Distance d to the beam's shape, then core 1 / (1 + (d / Corewidth)^Corepow) + glow Glowint x (Bias exp(-d / Glow) +
# (1 - Bias) exp(-d / (Glow x Spread))):
#   path  : up to 64 points from a Table DAT (`path`, or Pathdat): rows 'x y' (uv 0..1 or px), a row '-' = pen up;
#           Script CHOP `segs` -> uniform array uPts (x, y, u = arc length 0..1, pen); capsule distance per segment,
#           draw-on = the u range Start..End, a hot Tip at the moving end
#   mask  : the matte of in1 or of Masktop (a Text TOP of a whole word, a logo, a person matte): the outline module's
#           seed pass + GEN_sim's JFA (both imported read-only) -> distance to the matte's edge (Solid: inside = 0);
#           draw-on by angle around Revcentre or along Wipeangle
# Back / Blend as outline (add = light over the picture; transparent back = premultiplied light). Amount 0 = in1
# exact (out_sel). <= 3 GLSL TOP inputs (T-88). ASCII only.
import os

MODULE = 'saber'
SOURCES = ['path', 'mask', 'masktop']
REVS = ['angle', 'axis']
BACKS = ['picture', 'dim', 'black', 'transparent']
NPTS = 64

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']
_OUT = {'HERE': HERE}                                        # noqa: F821
with open(os.path.join(HERE, 'fx_stylise_outline.py')) as _fh:  # noqa: F821
    exec(_fh.read(), _OUT)                                   # outline's seed shader + JFA wiring, read-only reuse
SEED = _OUT['SEED']
JFA_FILE = _OUT['JFA_FILE']

DEFAULT_PATH = ['0.5 0.82', '0.58 0.6', '0.8 0.6', '0.62 0.46', '0.7 0.22', '0.5 0.36', '0.3 0.22', '0.38 0.46',
                '0.2 0.6', '0.42 0.6', '0.5 0.82']          # a star in uv (whole frame)

PAGES = [
    ('Saber', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Source', 'Menu', 'path', {'names': SOURCES, 'labels': [
            'Path (Table DAT points)', 'Mask: matte of in1', 'Mask: Masktop (Text TOP / logo / person matte)']}),
        ('Corewidth', 'Float', 3.0, {'min': 0.2, 'max': 40, 'label': 'Core width px'}),
        ('Corepow', 'Float', 2.5, {'min': 0.5, 'max': 8, 'label': 'Core falloff power'}),
        ('Glow', 'Float', 14.0, {'min': 0.5, 'max': 200, 'label': 'Glow px'}),
        ('Spread', 'Float', 4.0, {'min': 1, 'max': 20, 'label': 'Glow spread (wide glow = Glow x Spread)'}),
        ('Bias', 'Float', 0.65, {'min': 0, 'max': 1, 'label': 'Bias (tight vs wide glow)'}),
        ('Glowint', 'Float', 1.2, {'min': 0, 'max': 6, 'label': 'Glow intensity'}),
        ('Intensity', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Intensity (HDR with Hdr on)'}),
        ('Offset', 'Float', 0.0, {'min': -60, 'max': 60, 'label': 'Mask offset px (+ out)'}),
        ('Solid', 'Toggle', False, {'label': 'Mask: solid inside (neon sign fill)'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (distortion / flicker)'}),
    ]),
    ('Motion', [
        ('Start', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Start (draw-on)'}),
        ('End', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'End (draw-on)'}),
        ('Tip', 'Float', 1.5, {'min': 0, 'max': 8, 'label': 'Hot tip at End (path)'}),
        ('Revmode', 'Menu', 'angle', {'names': REVS, 'labels': ['Mask: around Revcentre', 'Mask: along Wipeangle']}),
        ('Revcentrex', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Rev centre u'}),
        ('Revcentrey', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Rev centre v'}),
        ('Wipeangle', 'Float', 90.0, {'min': -180, 'max': 180, 'label': 'Wipe angle deg'}),
        ('Distort', 'Float', 2.0, {'min': 0, 'max': 40, 'label': 'Distortion px'}),
        ('Distortscale', 'Float', 40.0, {'min': 2, 'max': 400, 'label': 'Distortion scale px'}),
        ('Distortspeed', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Distortion speed'}),
        ('Flicker', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Flicker'}),
        ('Flickerhz', 'Float', 24.0, {'min': 0, 'max': 60, 'label': 'Flicker Hz'}),
    ]),
    ('Look', [
        ('Corer', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Core R'}),
        ('Coreg', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Core G'}),
        ('Coreb', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Core B'}),
        ('Colsrc', 'Menu', 'solid', {'names': [m for m, _l in _PML.COLSRC_MODES],  # noqa: F821
                                     'labels': [lb for _m, lb in _PML.COLSRC_MODES], 'label': 'Glow colour source'}),  # noqa: F821
        ('Glowr', 'Float', 0.1, {'min': 0, 'max': 1, 'label': 'Glow R'}),
        ('Glowg', 'Float', 0.45, {'min': 0, 'max': 1, 'label': 'Glow G'}),
        ('Glowb', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Glow B'}),
        ('Palpos', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Palette position'}),
        ('Palspread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Palette spread (x along the beam)'}),
        ('Keep', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Keep picture colour'}),
        ('Back', 'Menu', 'picture', {'names': BACKS, 'labels': ['Picture', 'Dimmed', 'Black', 'Transparent']}),
        ('Backdim', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Dim level'}),
        ('Matte', 'Menu', 'luma', {'names': ['luma', 'alpha', 'maxrgb'], 'labels': ['Luma', 'Alpha', 'Max RGB']}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Mask threshold'}),
        ('Invert', 'Toggle', False, {'label': 'Invert mask'}),
        ('Res', 'Menu', 'half', {'names': ['full', 'half', 'quarter'], 'labels': ['Full', 'Half', 'Quarter'],
                                 'label': 'Mask distance resolution'}),
        ('Pathunits', 'Menu', 'uv', {'names': ['uv', 'px'], 'labels': ['uv (0..1 of the frame)', 'Pixels']}),
        ('Hdr', 'Toggle', False, {'label': 'HDR out (rgba16float)'}),
    ]),
    ('Inputs', [
        ('Masktop', 'TOP', '', {'label': 'Mask TOP (Source masktop)'}),
        ('Pathdat', 'Str', '', {'label': 'Path DAT path (empty = the module\'s own `path` table)'}),
    ]),
    pal_page('neon_trio', 'gradient'),  # noqa: F821
]
PANEL_PAGES = ['Saber', 'Motion', 'Look', 'Palette']

_SKIP = ('Palstops', 'Palfile', 'Masktop', 'Pathdat')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
for _k in ('Solid', 'Palreverse', 'Hdr', 'Invert'):
    _D[_k] = int(_D[_k])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'blue saber', _p(Seed=1)),
    (2, 'red sith', _p(Corewidth=2.5, Glow=10.0, Spread=5.0, Glowr=1.0, Glowg=0.08, Glowb=0.05, Distort=4.0,
                       Flicker=0.3, Seed=2)),
    (3, 'neon sign', _p(Source=2, Solid=0, Corewidth=2.0, Glow=8.0, Spread=6.0, Bias=0.5, Distort=0.0,
                        Flicker=0.05, Glowr=1.0, Glowg=0.2, Glowb=0.8, Back=1, Seed=3)),
    (4, 'draw on', _p(Start=0.0, End=0.6, Tip=3.0, Colsrc=2, Palspread=1.0, Back=2, Seed=4)),
    (5, 'person aura', _p(Source=1, Offset=6.0, Corewidth=1.5, Glow=18.0, Spread=5.0, Bias=0.4, Distort=6.0,
                          Distortscale=60.0, Glowr=0.4, Glowg=1.0, Glowb=0.5, Res=2, Seed=5)),
]

SEGS_CB = '''# segs: the saber path (fx_stylise_saber.py): Table DAT rows 'x y' (a row '-' = pen up) -> 64 samples x y u pen.
def rows(m):
\tt = (op(m.par.Pathdat.eval()) if m.par.Pathdat.eval() else None) or m.op('path')
\tout = []
\tif t is None:
\t\treturn out
\tfor i in range(t.numRows):
\t\tcs = [c.val.strip() for c in t.row(i) if c.val.strip()]
\t\tif not cs or cs[0] in ('-', 'up', 'x'):
\t\t\tif cs and cs[0] == 'x':
\t\t\t\tcontinue
\t\t\tout.append(None)
\t\t\tcontinue
\t\ttry:
\t\t\tout.append((float(cs[0]), float(cs[1])))
\t\texcept Exception:
\t\t\tcontinue
\treturn out

def pts(m):
\t"""-> [(x, y, u, pen)] (<= 64): pen 1 = joined to the previous point; u = arc length 0..1 over joined segments."""
\tP, pen, acc, last = [], 0.0, 0.0, None
\tfor r in rows(m):
\t\tif r is None:
\t\t\tpen = 0.0
\t\t\tcontinue
\t\tif last is not None and pen > 0:
\t\t\tacc += ((r[0] - last[0]) ** 2 + (r[1] - last[1]) ** 2) ** 0.5
\t\tP.append([r[0], r[1], acc, pen])
\t\tlast, pen = r, 1.0
\t\tif len(P) >= 64:
\t\t\tbreak
\ttot = acc if acc > 0 else 1.0
\tfor q in P:
\t\tq[2] /= tot
\treturn P

def count(m):
\treturn float(len(pts(m)))

def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tP = pts(scriptOp.parent())
\tscriptOp.clear()
\tscriptOp.numSamples = 64
\tfor k, n in enumerate(('x', 'y', 'u', 'pen')):
\t\tch = scriptOp.appendChan(n)
\t\tfor i in range(64):
\t\t\tch[i] = P[i][k] if i < len(P) else 0.0
'''

FX = ("""// saber fx (compute). in0 picture, in1 JFA of the mask (mask sources; a 1x1 zero for path). d = distance to the
// beam shape (px) -> core + two-scale glow, distortion, flicker, draw-on (Start..End), tip; light over Back.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, source, threshold, matte
uniform vec4 uB;   // corewidth, corepow, glow, spread
uniform vec4 uC;   // bias, glowint, intensity, offset
uniform vec4 uD;   // distort px, distort scale, distort time, flicker
uniform vec4 uE;   // time, flicker hz, seed, tip
uniform vec4 uF;   // start, end, revmode, wipe angle deg
uniform vec4 uG;   // core rgb, solid
uniform vec4 uH;   // glow rgb, back
uniform vec4 uI;   // backdim, res div, invert, point count
uniform vec4 uJ;   // rev centre uv, path units (0 uv / 1 px), -
uniform vec4 uCs;  // colour source (mode, palpos, palspread, keep)
uniform vec4 uPts[NPTS];
""" + GLSL_LIB + """
float matteOf(vec4 c, int mt, float inv) {
    float m = mt == 1 ? c.a : (mt == 2 ? max(c.r, max(c.g, c.b)) : dot(c.rgb, vec3(0.2126, 0.7152, 0.0722)));
    return inv > 0.5 ? 1.0 - m : m;
}
""" + PAL_GLSL + """
vec4 baseOf(int k, vec4 c, float dim) {
    if (k == 1) return c * dim;
    if (k == 2) return vec4(0.0, 0.0, 0.0, 1.0);
    if (k == 3) return vec4(0.0);
    return c;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    vec2 pc = vec2(p) + 0.5;
    vec2 fs = vec2(isz);
    int src = int(uA.y + 0.5);
    float d = 1e6, u = 0.0, tipd = 1e6;
    if (src == 0) {
        int n = int(uI.w + 0.5);
        vec2 sc = uJ.z > 0.5 ? vec2(1.0) : fs;
        for (int i = 1; i < NPTS; i++) {
            if (i >= n) break;
            vec4 b = uPts[i];
            if (b.w < 0.5) continue;
            vec4 a = uPts[i - 1];
            float ua = a.z, ub = b.z;
            if (ub < uF.x || ua > uF.y) continue;                                 // segment outside Start..End
            vec2 A = a.xy * sc, B = b.xy * sc;
            float fa = ub > ua ? clamp((uF.x - ua) / (ub - ua), 0.0, 1.0) : 0.0;
            float fb = ub > ua ? clamp((uF.y - ua) / (ub - ua), 0.0, 1.0) : 1.0;
            vec2 A2 = mix(A, B, fa), B2 = mix(A, B, fb);
            vec2 ab = B2 - A2;
            float h = clamp(dot(pc - A2, ab) / max(dot(ab, ab), 1e-6), 0.0, 1.0);
            float dd = length(pc - A2 - ab * h);
            if (dd < d) { d = dd; u = mix(mix(ua, ub, fa), mix(ua, ub, fb), h); }
            if (uF.y >= ua && uF.y <= ub) tipd = min(tipd, length(pc - B2));
        }
    } else {
        int D = clamp(int(uI.y + 0.5), 1, 4);
        ivec2 jsz = textureSize(sTD2DInputs[1], 0);
        vec2 q = pc / float(D);
        ivec2 b = ivec2(floor(q - 0.5));
        float bd = 1e30;
        for (int j = 0; j < 2; j++) for (int i = 0; i < 2; i++) {
            vec4 s = texelFetch(sTD2DInputs[1], clamp(b + ivec2(i, j), ivec2(0), jsz - 1), 0);
            if (s.z > 0.0) { vec2 e = q - s.xy; bd = min(bd, dot(e, e)); }
        }
        float dist = bd < 1e29 ? sqrt(bd) * float(D) : 1e6;
        vec4 mc = c;
        if (src == 2) mc = texelFetch(sTD2DInputs[2], p, 0);                    // mfit = Masktop at in1's size
        bool ins = matteOf(mc, int(uA.w + 0.5), uI.z) > uA.z;
        float sd = (ins ? -dist : dist) - uC.w;
        d = (uG.w > 0.5) ? max(sd, 0.0) : abs(sd);
        vec2 rc = uJ.xy * fs;
        if (uF.z < 0.5) u = fract(atan(pc.y - rc.y, pc.x - rc.x) / 6.2831853 + 1.0);
        else {
            float a = radians(uF.w);
            vec2 dir = vec2(cos(a), sin(a));
            float ext = 0.5 * (abs(dir.x) * fs.x + abs(dir.y) * fs.y);
            u = clamp(dot(pc - 0.5 * fs, dir) / max(2.0 * ext, 1.0) + 0.5, 0.0, 1.0);
        }
        if (u < uF.x || u > uF.y) d = 1e6;
    }
    if (uD.x != 0.0) d = max(d + uD.x * (2.0 * vnoise(pc / max(uD.y, 1.0) + vec2(uD.z, 0.61 * uD.z), uint(uE.z)) - 1.0), 0.0);
    float core = 1.0 / (1.0 + pow(d / max(uB.x, 1e-3), uB.y));
    float glow = uC.y * (uC.x * exp(-d / max(uB.z, 1e-3)) + (1.0 - uC.x) * exp(-d / max(uB.z * uB.w, 1e-3)));
    float tip = uE.w * exp(-tipd / max(uB.z, 1e-3));
    float fl = 1.0 + uD.w * (2.0 * hsh(ivec2(int(floor(uE.x * uE.y)), 3), uint(uE.z)) - 1.0);
    vec3 gcol = pxColSrc(uCs, uH.rgb, c.rgb, u);
    vec3 L = (core * uG.rgb + (glow + tip) * gcol) * uC.z * fl;
    vec4 base = baseOf(int(uH.w + 0.5), c, uI.x);
    float cov = clamp(max(core, glow + tip) * fl, 0.0, 1.0);
    vec4 o = vec4(base.rgb + L, max(base.a, cov));
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, o, uA.x));
}
""").replace('NPTS', str(NPTS))

SHADERS = {'seed': SEED, 'fx': FX}
NIN = {'seed': 1, 'jfa': 1, 'fx': 3}             # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"
DIV = _OUT['DIV']
JW, JH = _OUT['JW'], _OUT['JH']
PMFULL = _OUT['PMFULL']
_PP = "parent().par."
RANGE = ("(abs(%sOffset.eval()) + %sDistort.eval() + 2 + 6 * max(%sCorewidth.eval(), %sGlow.eval() * %sSpread.eval()))"
         % (_PP, _PP, _PP, _PP, _PP))
PM = "min(%s, max(1, int(math.ceil(math.log2(%s / %s + 2)))))" % (PMFULL, RANGE, DIV)


def uniforms():
    return {
        'seed': [('uS', [DIV, P.format('Threshold'), 'parent().par.Matte.menuIndex', 'float(%s)' % P.format('Invert')])],
        'jfa': [('uJ', ["op('seed').width", "op('seed').height", PM, '0'])],
        'fx': [('uA', [P.format('Amount'), 'parent().par.Source.menuIndex', P.format('Threshold'),
                       'parent().par.Matte.menuIndex']),
               ('uB', [P.format('Corewidth'), P.format('Corepow'), P.format('Glow'), P.format('Spread')]),
               ('uC', [P.format('Bias'), P.format('Glowint'), P.format('Intensity'), P.format('Offset')]),
               ('uD', [P.format('Distort'), P.format('Distortscale'), '%s * absTime.seconds' % P.format('Distortspeed'),
                       P.format('Flicker')]),
               ('uE', ['absTime.seconds', P.format('Flickerhz'), P.format('Seed'), P.format('Tip')]),
               ('uF', [P.format('Start'), P.format('End'), 'parent().par.Revmode.menuIndex', P.format('Wipeangle')]),
               ('uG', [P.format('Corer'), P.format('Coreg'), P.format('Coreb'), 'float(%s)' % P.format('Solid')]),
               ('uH', [P.format('Glowr'), P.format('Glowg'), P.format('Glowb'), 'parent().par.Back.menuIndex']),
               ('uI', [P.format('Backdim'), DIV, 'float(%s)' % P.format('Invert'),
                       "op('segs_callbacks').module.count(parent())"]),
               ('uJ', [P.format('Revcentrex'), P.format('Revcentrey'), 'parent().par.Pathunits.menuIndex', '0']),
               ('uCs', ['parent().par.Colsrc.menuIndex', P.format('Palpos'), P.format('Palspread'), P.format('Keep')])],
    }


def build(m, H):
    """in1 / masktop -> msrc -> seed -> jfa -> dsrc (path: 1x1 zero) -> fx (+ in1, mask) -> out_sel -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    mt = mk(m, selectTOP, 'masktop')  # noqa: F821
    expr(mt.par.top, "(%s.path if %s else 'in1')" % (P.format('Masktop'), P.format('Masktop')))
    mt.comment = 'Masktop (or in1 when empty).'
    mf = mk(m, resolutionTOP, 'mfit')  # noqa: F821
    mf.inputConnectors[0].connect(mt)
    mf.par.outputresolution = 'custom'
    expr(mf.par.resolutionw, "op('in1').width")
    expr(mf.par.resolutionh, "op('in1').height")
    mf.comment = 'Masktop fitted to in1 (distances in in1 pixels).'
    ms = mk(m, switchTOP, 'msrc')  # noqa: F821
    ms.inputConnectors[0].connect(in1)
    ms.inputConnectors[1].connect(mf)
    expr(ms.par.index, "1 if parent().par.Source.eval() == 'masktop' else 0")
    seed = H['pas'](m, 'seed', SEED, [ms], JW, JH, 'rgba32float')
    H['uniforms'](seed, U['seed'])
    seed.comment = 'Mask edge seeds (outline module seed shader, reused).'
    jfa = H['pas'](m, 'jfa', H['glsl'](JFA_FILE), [seed], "op('seed').width", "op('seed').height", 'rgba32float',
                   npasses='%s + 1' % PM)
    H['uniforms'](jfa, U['jfa'])
    jfa.comment = 'Jump flood (GEN_sim gen_sim_vor_jfa.glsl, read-only); Pm = the glow reach.'
    z = mk(m, constantTOP, 'dzero')  # noqa: F821
    z.par.outputresolution = 'custom'
    z.par.resolutionw, z.par.resolutionh = 1, 1
    z.par.colorr = z.par.colorg = z.par.colorb = z.par.alpha = 0
    ds = mk(m, switchTOP, 'dsrc')  # noqa: F821
    ds.inputConnectors[0].connect(z)
    ds.inputConnectors[1].connect(jfa)
    expr(ds.par.index, "0 if parent().par.Source.eval() == 'path' else 1")
    ds.comment = 'Path source: 1x1 zero (seed / jfa not pulled).'
    mz = mk(m, switchTOP, 'mtsrc')  # noqa: F821
    mz.inputConnectors[0].connect(z)
    mz.inputConnectors[1].connect(mf)
    expr(mz.par.index, "1 if parent().par.Source.eval() == 'masktop' else 0")
    t = m.op('path')
    if t is None:
        t = mk(m, tableDAT, 'path')  # noqa: F821
        t.clear()
        for r in DEFAULT_PATH:
            t.appendRow(r.split())
    t.comment = "Saber path: rows 'x y' (uv 0..1 or px, Pathunits), a row '-' = pen up. <= 64 points."
    sg = mk(m, scriptCHOP, 'segs')  # noqa: F821
    d = m.op('segs_callbacks')
    if d is None:
        d = mk(m, textDAT, 'segs_callbacks')  # noqa: F821
    if d.text != SEGS_CB:
        d.text = SEGS_CB
    d.dock = sg
    sg.par.callbacks = 'segs_callbacks'
    sg.comment = 'uPts: 64 samples x y u pen from the path table.'
    fx = H['pas'](m, 'fx', FX, [in1, ds, mz], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    expr(fx.par.format, "'rgba16float' if %s else 'useinput'" % P.format('Hdr'))
    H['uniforms'](fx, U['fx'])
    k = _PML._block(fx.seq.array, fx.par, ('array', 'name'), 'uPts')  # noqa: F821
    getattr(fx.par, 'array%dname' % k).val = 'uPts'
    getattr(fx.par, 'array%dtype' % k).val = 'vec4'
    getattr(fx.par, 'array%dchop' % k).val = 'segs'
    getattr(fx.par, 'array%darraytype' % k).val = 'uniformarray'
    fx.comment = 'saber: core + glow + tip along the path / mask edge, distortion, flicker, draw-on.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact.'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'masktop', 'mfit', 'msrc', 'path', 'segs', 'segs_callbacks']},
        {'title': '2 Mask distance', 'role': 'process', 'ops': ['seed', 'seed_compute', 'jfa', 'jfa_compute', 'dzero',
                                                             'dsrc', 'mtsrc'],
         'body': 'Mask sources: edge seeds + jump flood (reused). Path: not pulled.'},
        {'title': '3 Beam', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'Core + glow + tip, distortion, flicker, draw-on; light over Back.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
