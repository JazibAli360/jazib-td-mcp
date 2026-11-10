# fx_glass_rain - FX_glass module 'rain' (FX7a SX-02 + FX7c 7C-34 rain on glass / lens droplets: drops that slide
# down a window leaving clear trails, the scene seen flipped inside each drop, fogged glass elsewhere; BigWings
# "Heartfelt" and Gerardo LCDF's Godot port (MIT) as the look references, clean-room). Template:
# docs/builds/fx_glitch.md "Module template" (rack = builders/fx_glass.py). Doc: docs/builds/fx_glass.md. Mirror:
# builders/fx_glass_rain_logic.py.
# One compute pass over Layers (1-3) of drop cells (Size x 2 Size px, per layer 1 / 0.6 / 0.4 x Size): a cell holds a
# sliding drop with probability Rain (stick-slip descent, Speed), a clear trail above it (Trails) with small trail
# droplets, and a finer grid of static droplets (Static) that fade in and out. Each drop is a lens: the picture is
# sampled at centre - Refract x offset (flipped), rimmed darker (Rimdark). Outside drops and trails the glass is fogged
# (pre-blurred backdrop, Fog), tinted (Tint rgb, Tintamt). Amount 0 = in1 exact (out_sel). ASCII only.
import os

MODULE = 'rain'

with open(os.path.join(HERE, 'fx_stylise_lib.py')) as _fh:  # noqa: F821 (HERE from the rack)
    _LIBNS = {}
    exec(_fh.read(), _LIBNS)
GLSL_LIB = _LIBNS['GLSL_LIB']
BACKDROP_PAGE = ('Backdrop', [
    ('Backblur', 'Float', 24.0, {'min': 0, 'max': 200, 'label': 'Backdrop blur px (full-res px)'}),
    ('Backdown', 'Menu', 'half', {'names': ['full', 'half', 'quarter'], 'labels': ['Full', 'Half', 'Quarter'],
                                  'label': 'Backdrop resolution'}),
])                                                           # = fx_glass.BACKDROP_PAGE (the rack's _backdrop reads it)

PAGES = [
    ('Rain', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Rain', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Rain (share of cells with a sliding drop)'}),
        ('Size', 'Float', 120.0, {'min': 16, 'max': 600, 'label': 'Drop cell px'}),
        ('Layers', 'Int', 2, {'min': 1, 'max': 3, 'label': 'Layers'}),
        ('Speed', 'Float', 0.25, {'min': 0, 'max': 3, 'label': 'Slide speed'}),
        ('Trails', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Trails'}),
        ('Static', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Static droplets'}),
        ('Refract', 'Float', 1.6, {'min': -4, 'max': 6, 'label': 'Refraction (lens flip)'}),
        ('Rimdark', 'Float', 0.35, {'min': 0, 'max': 1, 'label': 'Drop rim darkening'}),
        ('Fog', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Fog (blurred glass between drops)'}),
        ('Tintr', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Tint R'}),
        ('Tintg', 'Float', 0.92, {'min': 0, 'max': 1, 'label': 'Tint G'}),
        ('Tintb', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Tint B'}),
        ('Tintamt', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Tint amount'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    BACKDROP_PAGE,
]
PANEL_PAGES = ['Rain', 'Backdrop']

_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl)


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'window rain', _p(Seed=1)),
    (2, 'storm', _p(Rain=0.9, Size=90.0, Layers=3, Speed=0.6, Static=0.8, Fog=0.9, Seed=2)),
    (3, 'lens drops', _p(Rain=0.25, Size=260.0, Layers=1, Speed=0.08, Trails=0.3, Static=0.2, Refract=3.0, Fog=0.0,
                         Tintamt=0.0, Seed=3)),
    (4, 'misty', _p(Rain=0.35, Speed=0.15, Static=0.9, Fog=1.0, Backblur=48.0, Tintamt=0.3, Seed=4)),
    (5, 'still glass', _p(Speed=0.0, Rain=0.7, Static=0.7, Fog=0.6, Seed=5)),
]

FX = """// rain fx (compute). in0 picture (bilinear), in1 pre-blurred backdrop. Drop layers -> lens offsets + clear mask.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, rain, size px, layers
uniform vec4 uB;   // time (speed x t), trails, static, refract
uniform vec4 uC;   // rimdark, fog, seed, -
uniform vec4 uD;   // tint rgb, tint amount
""" + GLSL_LIB + """
vec2 fs;
// one layer: returns (offset px, clear) in o and the summed rim in rim
void layer(vec2 pc, float size, uint sd, inout vec2 off, inout float clear, inout float rim) {
    vec2 cs = vec2(size, 2.0 * size);
    vec2 q = pc / cs;
    ivec2 id = ivec2(floor(q));
    vec2 f = fract(q) - 0.5;
    float t = uB.x;
    float n = hsh(id, sd);
    if (n < uA.y) {                                                   // a sliding drop in this cell
        float x = (hsh(id + ivec2(3, 1), sd) - 0.5) * 0.6;
        float ph = fract(t * (0.6 + 0.8 * hsh(id + ivec2(5, 7), sd)) + n * 7.0);
        float sl = ph + 0.05 * sin(18.849556 * ph);                 // stick-slip (monotonic: slope >= 0.06)
        float y = 0.42 - 0.84 * sl;
        float r = size * 0.16 * (0.7 + 0.6 * hsh(id + ivec2(9, 2), sd));
        vec2 dp = (f - vec2(x, y)) * cs;
        float d = length(dp * vec2(1.0, 0.85)) - r;
        float m = 1.0 - smoothstep(-1.0, 1.0, d);
        off += -(1.0 + uB.w) * dp * m;
        clear = max(clear, m);
        rim += m * smoothstep(-0.35 * r, 0.0, d);
        float tw = r * 0.45;                                          // clear trail above the drop
        float dx = abs((f.x - x) * cs.x);
        float above = (f.y - y) * cs.y;
        float tm = (1.0 - smoothstep(0.5 * tw, tw, dx)) * step(0.0, above) * (1.0 - smoothstep(0.0, 0.84 * cs.y, above));
        clear = max(clear, tm * uB.y);
        float ty = fract(above / max(tw * 1.6, 1.0));                // trail droplets
        vec2 tp = vec2((f.x - x) * cs.x, (ty - 0.5) * tw * 1.6);
        float tr = tw * 0.35;
        float td = length(tp) - tr;
        float tmk = (1.0 - smoothstep(-1.0, 1.0, td)) * tm * uB.y;
        off += -(1.0 + uB.w) * tp * tmk;
        clear = max(clear, tmk);
    }
    vec2 sc = vec2(size * 0.32);                                      // static droplets
    vec2 sq = pc / sc;
    ivec2 sid = ivec2(floor(sq));
    float sn = hsh(sid, sd + 17u);
    if (sn < uB.z) {
        vec2 sf = (fract(sq) - 0.5 - (vec2(hsh(sid + ivec2(1, 4), sd), hsh(sid + ivec2(6, 2), sd)) - 0.5) * 0.5) * sc;
        float life = fract(t * 0.2 + sn * 13.0);
        float fade = smoothstep(0.0, 0.1, life) * (1.0 - smoothstep(0.7, 1.0, life));
        float sr = sc.x * 0.18 * (0.5 + hsh(sid + ivec2(2, 9), sd)) * fade;
        float sdd = length(sf) - sr;
        float sm = (1.0 - smoothstep(-1.0, 1.0, sdd)) * step(0.5, sr);
        off += -(1.0 + uB.w) * sf * sm;
        clear = max(clear, sm);
        rim += sm * smoothstep(-0.35 * sr, 0.0, sdd);
    }
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }        // exact passthrough
    fs = vec2(isz);
    vec2 pc = vec2(p) + 0.5;
    vec2 off = vec2(0.0);
    float clear = 0.0, rim = 0.0;
    int L = clamp(int(uA.w + 0.5), 1, 3);
    uint sd = uint(uC.z) * 7919u;
    for (int k = 0; k < 3; k++) {
        if (k >= L) break;
        float sz = uA.z * (k == 0 ? 1.0 : (k == 1 ? 0.6 : 0.4));
        layer(pc, sz, sd + uint(k) * 101u, off, clear, rim);
    }
    vec2 q = (pc + off) / fs;
    vec3 sharp = texture(sTD2DInputs[0], q).rgb;
    vec3 fog = texture(sTD2DInputs[1], q).rgb;
    vec3 col = mix(fog, sharp, max(clear, 1.0 - uC.y));
    col *= 1.0 - uC.x * clamp(rim, 0.0, 1.0);
    col = mix(col, col * uD.rgb, uD.w);
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, vec4(col, c.a), uA.x));
}
"""

SHADERS = {'fx': FX}
NIN = {'fx': 2}                          # wired inputs per pass (TD sizes sTD2DInputs[] to it)

P = "parent().par.{}.eval()"


def uniforms():
    return {
        'fx': [('uA', [P.format('Amount'), P.format('Rain'), P.format('Size'), P.format('Layers')]),
               ('uB', ['%s * absTime.seconds' % P.format('Speed'), P.format('Trails'), P.format('Static'),
                       P.format('Refract')]),
               ('uC', [P.format('Rimdark'), P.format('Fog'), P.format('Seed'), '0']),
               ('uD', [P.format('Tintr'), P.format('Tintg'), P.format('Tintb'), P.format('Tintamt')])],
    }


def build(m, H):
    """in1 -> bd (backdrop) -> fx (in1, bd) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    bd = H['backdrop'](m, in1)
    fx = H['pas'](m, 'fx', FX, [in1, bd], 'me.inputs[0].width', 'me.inputs[0].height', 'useinput')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'rain: sliding drops + trails + static droplets as lenses; fogged glass between.'
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact.'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'bd_down', 'bd']},
        {'title': '2 Rain', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'Drop layers (sliding, trails, static) as lenses over fogged glass.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
