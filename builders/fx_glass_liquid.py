# fx_glass_liquid - FX_glass module 'liquid' (FX7a SX-01 liquid glass panel + FX7c 7C-23 liquid-glass lens; the
# 2025-26 "liquid glass" UI look: rounded glass slabs / pills / lenses that refract the picture at a bevel, blur it
# inside, split colour at the rim, Fresnel rim + specular; archisvaze liquid-glass (MIT) and the mws post as references,
# clean-room). Pilot of FX_glass. Template: docs/builds/fx_glitch.md "Module template" (rack = builders/fx_glass.py).
# Doc: docs/builds/fx_glass.md. Mirror: builders/fx_glass_liquid_logic.py.
# Shapes: Table DAT `shapes` (rows 'cx cy w h r rot': centre in uv, size / corner radius px, rotation deg; <= 8) ->
# Script CHOP `shp` -> uniform array uShp[16]; rounded boxes smooth-unioned (Smooth px), drifting (Drift). Or Source
# mask: a blurred matte (Masktop or in1, `mblur`) as a height field. Per pixel: d = signed distance (px), gradient by
# central differences of the SDF itself (no dFdx, compute pass), dome bevel height over Bevel px -> normal -> refract
# (IOR, Thickness px) with Dispersion (3 IORs); inside = sharp picture / pre-blurred backdrop (Frost) at the refracted
# spot, tint (solid or palette stop per shape), Fresnel rim, specular (Lightangle, Shine), edge line; drop shadow
# outside. Amount 0 = in1 exact (out_sel). <= 3 GLSL TOP inputs (T-88): in1, backdrop, mask height. ASCII only.
import os

MODULE = 'liquid'
NSHP = 8

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']
BACKDROP_PAGE = ('Backdrop', [
    ('Backblur', 'Float', 24.0, {'min': 0, 'max': 200, 'label': 'Backdrop blur px (full-res px)'}),
    ('Backdown', 'Menu', 'half', {'names': ['full', 'half', 'quarter'], 'labels': ['Full', 'Half', 'Quarter'],
                                  'label': 'Backdrop resolution'}),
])                                                           # = fx_glass.BACKDROP_PAGE (the rack's _backdrop reads it)

DEFAULT_SHAPES = ['0.5 0.78 760 180 90 0', '0.3 0.5 360 360 180 0', '0.66 0.3 520 300 60 -8']

PAGES = [
    ('Glass', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Source', 'Menu', 'shapes', {'names': ['shapes', 'mask'], 'labels': [
            'Shapes (Table DAT, smooth union)', 'Mask (blurred matte of Masktop or in1)']}),
        ('Ior', 'Float', 1.45, {'min': 1.0, 'max': 3, 'label': 'Index of refraction'}),
        ('Thickness', 'Float', 60.0, {'min': 0, 'max': 400, 'label': 'Thickness px (refraction shift)'}),
        ('Bevel', 'Float', 40.0, {'min': 1, 'max': 300, 'label': 'Bevel px'}),
        ('Smooth', 'Float', 60.0, {'min': 0, 'max': 400, 'label': 'Smooth union px (merging blobs)'}),
        ('Dispersion', 'Float', 0.03, {'min': 0, 'max': 0.3, 'label': 'Dispersion (rim colour split)'}),
        ('Frost', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Frost (blurred inside)'}),
        ('Bright', 'Float', 1.08, {'min': 0, 'max': 3, 'label': 'Inside brightness'}),
        ('Drift', 'Float', 0.0, {'min': 0, 'max': 300, 'label': 'Drift px'}),
        ('Driftspeed', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Drift speed'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed (drift phases)'}),
    ]),
    ('Light', [
        ('Rim', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Fresnel rim'}),
        ('Rimpow', 'Float', 3.0, {'min': 0.5, 'max': 10, 'label': 'Rim power (higher = thinner)'}),
        ('Spec', 'Float', 0.5, {'min': 0, 'max': 4, 'label': 'Specular'}),
        ('Shine', 'Float', 60.0, {'min': 2, 'max': 400, 'label': 'Shininess'}),
        ('Lightangle', 'Float', 120.0, {'min': -180, 'max': 180, 'label': 'Light angle deg'}),
        ('Edge', 'Float', 0.35, {'min': 0, 'max': 3, 'label': 'Edge line'}),
        ('Shadow', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Drop shadow'}),
        ('Shadowsoft', 'Float', 30.0, {'min': 1, 'max': 200, 'label': 'Shadow softness px'}),
        ('Shadowoffset', 'Float', 18.0, {'min': -100, 'max': 100, 'label': 'Shadow offset px (down)'}),
        ('Tintsrc', 'Menu', 'solid', {'names': ['solid', 'palette'], 'labels': ['Solid tint', 'Palette stop per shape']}),
        ('Tintr', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Tint R'}),
        ('Tintg', 'Float', 0.92, {'min': 0, 'max': 1, 'label': 'Tint G'}),
        ('Tintb', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Tint B'}),
        ('Tintamt', 'Float', 0.12, {'min': 0, 'max': 1, 'label': 'Tint amount'}),
    ]),
    ('Mask', [
        ('Masktop', 'TOP', '', {'label': 'Mask TOP (Source mask; empty = in1)'}),
        ('Matte', 'Menu', 'alpha', {'names': ['luma', 'alpha', 'maxrgb'], 'labels': ['Luma', 'Alpha', 'Max RGB']}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Mask threshold'}),
        ('Invert', 'Toggle', False, {'label': 'Invert mask'}),
        ('Maskblur', 'Float', 20.0, {'min': 0, 'max': 200, 'label': 'Mask bevel blur px'}),
    ]),
    BACKDROP_PAGE,
    pal_page('neon_trio', 'steps'),  # noqa: F821
]
PANEL_PAGES = ['Glass', 'Light', 'Mask', 'Backdrop', 'Palette']

_SKIP = ('Palstops', 'Palfile', 'Masktop')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
for _k in ('Invert', 'Palreverse'):
    _D[_k] = int(_D[_k])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'glass panels', _p(Seed=1)),
    (2, 'lens', _p(Thickness=160.0, Bevel=140.0, Frost=0.0, Dispersion=0.06, Tintamt=0.0, Rim=0.4, Seed=2)),
    (3, 'merging blobs', _p(Smooth=180.0, Drift=120.0, Driftspeed=0.4, Tintsrc=1, Tintamt=0.25, Seed=3)),
    (4, 'frosted pills', _p(Frost=1.0, Backblur=48.0, Thickness=30.0, Dispersion=0.0, Rim=0.9, Seed=4)),
    (5, 'glass word', _p(Source=1, Thickness=40.0, Bevel=24.0, Maskblur=14.0, Frost=0.3, Dispersion=0.05, Seed=5)),
]

SHP_CB = '''# shp: liquid glass shapes (fx_glass_liquid.py): Table DAT `shapes` rows 'cx cy w h r rot' -> 16 samples x y z w:
# samples 0..7 = (cx, cy, w, h), 8..15 = (r, rot, 1 = on, 0).
def rows(m):
\tt = m.op('shapes')
\tout = []
\tif t is None:
\t\treturn out
\tfor i in range(t.numRows):
\t\tcs = [c.val.strip() for c in t.row(i) if c.val.strip()]
\t\ttry:
\t\t\tv = [float(x) for x in cs[:6]]
\t\texcept Exception:
\t\t\tcontinue
\t\tif len(v) < 4:
\t\t\tcontinue
\t\tv += [0.0] * (6 - len(v))
\t\tout.append(v)
\t\tif len(out) >= 8:
\t\t\tbreak
\treturn out

def count(m):
\treturn float(len(rows(m)))

def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tR = rows(scriptOp.parent())
\tscriptOp.clear()
\tscriptOp.numSamples = 16
\tch = [scriptOp.appendChan(n) for n in ('x', 'y', 'z', 'w')]
\tfor i in range(8):
\t\tr = R[i] if i < len(R) else [0.0] * 6
\t\ton = 1.0 if i < len(R) else 0.0
\t\tfor k, v in enumerate((r[0], r[1], r[2], r[3])):
\t\t\tch[k][i] = v
\t\tfor k, v in enumerate((r[4], r[5], on, 0.0)):
\t\t\tch[k][8 + i] = v
'''

FX = ("""// liquid glass fx (compute). in0 picture (bilinear), in1 pre-blurred backdrop, in2 mask height (Source mask).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, source, ior, thickness px
uniform vec4 uB;   // bevel px, smooth px, dispersion, frost
uniform vec4 uC;   // tint rgb, tint amount
uniform vec4 uD;   // rim, rim power, spec, shine
uniform vec4 uE;   // light angle deg, shadow, shadow soft px, shadow offset px
uniform vec4 uF;   // drift px, drift time, shape count, brightness
uniform vec4 uG;   // mask threshold, edge, tint source, seed
uniform vec4 uShp[16];
""" + GLSL_LIB + PAL_GLSL + """
vec2 fs;
float sdBox(vec2 q, vec2 b, float r) {
    r = min(r, min(b.x, b.y));
    vec2 d = abs(q) - b + r;
    return length(max(d, 0.0)) + min(max(d.x, d.y), 0.0) - r;
}
float sdf(vec2 pc, out float idx) {
    int n = int(uF.z + 0.5);
    float d = 1e6;
    idx = 0.0;
    float best = 1e6;
    if (int(uA.y + 0.5) == 1) {
        float h = texture(sTD2DInputs[2], pc / fs).r;           // blurred matte as a height: < 0 inside; outside
        float dd = (uG.x - h) * 2.0 * uB.x;                     // it grows fast as h -> 0 (so the shadow fades)
        return h < uG.x ? dd / max(h / max(uG.x, 1e-3), 0.02) : dd;
    }
    for (int i = 0; i < NSHP; i++) {
        if (i >= n) break;
        vec4 a = uShp[i], b = uShp[NSHP + i];
        float fi = float(i);
        vec2 c = a.xy * fs + uF.x * vec2(sin(uF.y * 0.7 + fi * 1.9 + uG.w), cos(uF.y * 0.53 + fi * 2.7 + uG.w));
        float ang = radians(b.y);
        vec2 q = pc - c;
        q = vec2(cos(ang) * q.x + sin(ang) * q.y, -sin(ang) * q.x + cos(ang) * q.y);
        float di = sdBox(q, 0.5 * a.zw, b.x);
        if (di < best) { best = di; idx = fi; }
        float k = max(uB.y, 1e-3);
        float hh = max(k - abs(d - di), 0.0) / k;
        d = min(d, di) - hh * hh * k * 0.25;
    }
    return d;
}
vec3 samp(vec2 q, float frost) {
    return mix(texture(sTD2DInputs[0], q / fs).rgb, texture(sTD2DInputs[1], q / fs).rgb, frost);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    fs = vec2(isz);
    vec2 pc = vec2(p) + 0.5;
    float idx, i2;
    float d = sdf(pc, idx);
    if (d > 1.0 && (uE.y <= 0.0 || d > abs(uE.w) + 6.0 * uE.z)) {             // far outside: nothing to draw
        TDImageStoreOutput(0, ivec3(p, 0), c);
        return;
    }
    float cov = 1.0 - smoothstep(-0.75, 0.75, d);
    float ds = sdf(pc + vec2(0.0, uE.w), i2);
    float sh = uE.y * exp(-max(ds, 0.0) / max(uE.z, 1e-3)) * (1.0 - cov);
    vec4 back = vec4(c.rgb * (1.0 - sh), max(c.a, sh));
    if (cov <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), mix(c, back, uA.x)); return; }  // outside the glass
    float e = 0.75;
    vec2 g = vec2(sdf(pc + vec2(e, 0.0), i2) - sdf(pc - vec2(e, 0.0), i2),
                  sdf(pc + vec2(0.0, e), i2) - sdf(pc - vec2(0.0, e), i2)) / (2.0 * e);
    g = dot(g, g) > 1e-12 ? normalize(g) : vec2(0.0);
    float t = clamp(-d / max(uB.x, 1e-3), 0.0, 1.0);
    float u = 1.0 - t;
    float slope = u / sqrt(max(1.0 - u * u, 1e-4));
    vec3 n = normalize(vec3(g * min(slope, 8.0), 1.0));
    vec3 col;
    vec3 ior3 = uA.z * (1.0 + uB.z * vec3(-1.0, 0.0, 1.0));
    for (int k = 0; k < 3; k++) {
        vec3 r = refract(vec3(0.0, 0.0, -1.0), n, 1.0 / ior3[k]);
        vec2 off = r.xy / max(-r.z, 0.05) * uA.w;
        col[k] = samp(pc + off, uB.w)[k];
    }
    vec3 tint = uG.z > 0.5 ? pxPalStep(int(idx + 0.5)) : uC.rgb;
    col = mix(col, tint, uC.w) * uF.w;
    float la = radians(uE.x);
    vec3 L = normalize(vec3(cos(la), sin(la), 1.2));
    float spec = pow(max(dot(n, normalize(L + vec3(0.0, 0.0, 1.0))), 0.0), uD.w) * uD.z;
    float rim = pow(clamp(1.0 - n.z, 0.0, 1.0), max(uD.y, 0.1) * 0.25) * uD.x * (1.0 - t);
    float edge = uG.y * (1.0 - smoothstep(0.0, 1.5, abs(d)));
    col += vec3(spec + rim + edge);
    vec4 o = mix(back, vec4(col, 1.0), cov);
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, o, uA.x));
}
""").replace('NSHP', str(NSHP))

SHADERS = {'fx': FX}
NIN = {'fx': 3}                          # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"


def uniforms():
    return {
        'fx': [('uA', [P.format('Amount'), 'parent().par.Source.menuIndex', P.format('Ior'), P.format('Thickness')]),
               ('uB', [P.format('Bevel'), P.format('Smooth'), P.format('Dispersion'), P.format('Frost')]),
               ('uC', [P.format('Tintr'), P.format('Tintg'), P.format('Tintb'), P.format('Tintamt')]),
               ('uD', [P.format('Rim'), P.format('Rimpow'), P.format('Spec'), P.format('Shine')]),
               ('uE', [P.format('Lightangle'), P.format('Shadow'), P.format('Shadowsoft'), P.format('Shadowoffset')]),
               ('uF', [P.format('Drift'), '%s * absTime.seconds' % P.format('Driftspeed'),
                       "op('shp_callbacks').module.count(parent())", P.format('Bright')]),
               ('uG', [P.format('Threshold'), P.format('Edge'), 'parent().par.Tintsrc.menuIndex', P.format('Seed')])],
        'matte': [('uM', ['parent().par.Matte.menuIndex', 'float(%s)' % P.format('Invert'),
                          "max(1, op('in1').width // 2)", "max(1, op('in1').height // 2)"])],
    }


def build(m, H):
    """in1 -> bd (backdrop) / mask -> mblur; shapes -> shp; fx (in1, bd, mask height) -> out_sel -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    bd = H['backdrop'](m, in1)
    mt = mk(m, selectTOP, 'masktop')  # noqa: F821
    expr(mt.par.top, "(%s.path if %s else 'in1')" % (P.format('Masktop'), P.format('Masktop')))
    mt.comment = 'Masktop (or in1 when empty).'
    mm = H['pas'](m, 'matte', MATTE, [mt], "max(1, op('in1').width // 2)", "max(1, op('in1').height // 2)",
                  'rgba16float')
    H['uniforms'](mm, U['matte'])
    mm.comment = 'Matte of the mask (luma / alpha / max rgb, Invert) at half the in1 size.'
    mb = mk(m, blurTOP, 'mblur')  # noqa: F821
    mb.inputConnectors[0].connect(mm)
    expr(mb.par.size, '%s * 0.5' % P.format('Maskblur'))          # matte at half res
    mb.par.type = 'gaussian'
    mb.par.extend = 'hold'
    mb.comment = 'Blurred matte = glass height (Source mask).'
    z = mk(m, constantTOP, 'mzero')  # noqa: F821
    z.par.outputresolution = 'custom'
    z.par.resolutionw, z.par.resolutionh = 1, 1
    z.par.colorr = z.par.colorg = z.par.colorb = z.par.alpha = 0
    ms = mk(m, switchTOP, 'msrc')  # noqa: F821
    ms.inputConnectors[0].connect(z)
    ms.inputConnectors[1].connect(mb)
    expr(ms.par.index, "1 if parent().par.Source.eval() == 'mask' else 0")
    ms.comment = 'Shapes source: 1x1 zero (matte / blur not pulled).'
    t = m.op('shapes')
    if t is None:
        t = mk(m, tableDAT, 'shapes')  # noqa: F821
        t.clear()
        for r in DEFAULT_SHAPES:
            t.appendRow(r.split())
    t.comment = "Glass shapes: rows 'cx cy w h r rot' (centre uv, size / corner radius px, rotation deg), <= 8."
    sg = mk(m, scriptCHOP, 'shp')  # noqa: F821
    d = m.op('shp_callbacks')
    if d is None:
        d = mk(m, textDAT, 'shp_callbacks')  # noqa: F821
    if d.text != SHP_CB:
        d.text = SHP_CB
    d.dock = sg
    sg.par.callbacks = 'shp_callbacks'
    sg.comment = 'uShp: 16 samples (cx cy w h | r rot on -) from the shapes table.'
    fx = H['pas'](m, 'fx', FX, [in1, bd, ms], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](fx, U['fx'])
    k = _PML._block(fx.seq.array, fx.par, ('array', 'name'), 'uShp')  # noqa: F821
    getattr(fx.par, 'array%dname' % k).val = 'uShp'
    getattr(fx.par, 'array%dtype' % k).val = 'vec4'
    getattr(fx.par, 'array%dchop' % k).val = 'shp'
    getattr(fx.par, 'array%darraytype' % k).val = 'uniformarray'
    fx.comment = 'liquid glass: SDF bevel -> refraction + dispersion, frost, tint, rim, spec, edge, shadow.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact.'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'bd_down', 'bd', 'shapes', 'shp', 'shp_callbacks']},
        {'title': '2 Mask', 'role': 'process', 'ops': ['masktop', 'matte', 'matte_compute', 'mblur', 'mzero', 'msrc'],
         'body': 'Source mask: blurred matte as the glass height.'},
        {'title': '3 Glass', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'SDF bevel, refraction + dispersion, frost, tint, rim, spec, edge, shadow.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]


MATTE = """// liquid matte (compute, rgba16float): matte of the mask picture (luma / alpha / max rgb, invert) in r.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uM;   // matte, invert, out width, out height (= in1 / 2; output-info uniform not used in compute, T-119 (1))
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uM.zw);
    if (p.x >= osz.x || p.y >= osz.y) return;
    vec2 uv = (vec2(p) + 0.5) / vec2(osz);
    vec4 c = texture(sTD2DInputs[0], uv);
    int mt = int(uM.x + 0.5);
    float m = mt == 1 ? c.a : (mt == 2 ? max(c.r, max(c.g, c.b)) : dot(c.rgb, vec3(0.2126, 0.7152, 0.0722)));
    if (uM.y > 0.5) m = 1.0 - m;
    TDImageStoreOutput(0, ivec3(p, 0), vec4(m, m, m, 1.0));
}
"""
SHADERS['matte'] = MATTE
NIN['matte'] = 1
