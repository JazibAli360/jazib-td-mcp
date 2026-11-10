# fx_film builder - FX_film: picture in -> a chain of film / lens module slots -> Panic -> out1.
# The SAME lean rack as builders/fx_glitch.py (template: docs/builds/fx_glitch.md), copied, not abstracted: a slot is
# the module COMP + a Cross TOP (<name>_mix) + a Switch TOP (<name>_slot: 0 bypass / 1 module / 2 mix); the `slots`
# table (name module enabled order mix) is the only rack state; add / remove / reorder = this builder re-wiring.
# Module 'X' lives in builders/fx_film_X.py; maths in builders/fx_film_logic.py; doc + LIVE CHECKS docs/builds/fx_film.md.
# Shared here because 2+ modules use each today (no-bloat rule): GLSL_LIB (hash / value noise / fbm: grain, leaks,
# diffusion, flare; sRGB: tonecurve, stock; soft knee: halation, diffusion, streak, flare, star), the EXT pass (box
# downsample + soft knee into a mip-padded buffer: halation, diffusion, flare, star), MIPG (level-weighted mip gather:
# halation, diffusion), the out_sel helper (Amount 0 = in1, engine not pulled: the 5 multi-pass modules) and the test
# chart (every module's live check).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/fx_film.py').read(), ns)
#   ns['build']('/project1/lab')                        # rack + the 10 wave A/B rows (all enabled 0) on first build
#   ns['build']('/project1/lab', rows=['halation'])     # rack + only the rows named (a lane builds one module)
#   ns['add']('/project1/lab/FX_film', 'grain')          # grain2, wired last
#   ns['remove']('/project1/lab/FX_film', 'grain2'); ns['rewire'](c) after editing order in `slots`
# Idempotent; T-70 safe (_sd = safe_destroy, instance windows closed before a remove; pane never moved). No functions
# in op storage (T-67). ASCII only.
import os
import types

NAME = 'FX_film'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
LOGIC_FILE = os.path.join(HERE, 'fx_film_logic.py')
TEST_CLIP = '~/Documents/StageLab_PrismFest/jazib-td-mcp/media/webcam/webcam_ref_5s.mp4'
COLS = ['name', 'module', 'enabled', 'order', 'mix']
# physical order: camera body (camera: handheld move, rolling shutter, shutter blur, exposure, ISO) -> lens (dof, ca)
# -> glare (diffusion, streak, flare, star) -> film (halation, leaks, grain, gate) -> colour (stock, colour, tonecurve
# with the display dither last). All start bypassed (enabled 0): cost 0 until a lane turns one on.
# Wave C (camera, dof, gate, colour) added to an existing rack with add(..., order=<between>) (docs/builds/fx_film.md).
MODULES = ['camera', 'dof', 'ca', 'diffusion', 'streak', 'flare', 'star', 'halation', 'leaks', 'grain', 'gate', 'stock',
           'colour', 'tonecurve']
DEFAULT_ROWS = [[m + '1', m, 0, k + 1, 1] for k, m in enumerate(MODULES)]


def plan_chain(rows):
    """rows: [{name, order, ...}] -> names in chain order (order, then table position). Pure; tested offline."""
    idx = [(float(r.get('order') or 0), i, r['name']) for i, r in enumerate(rows)]
    return [n for _o, _i, n in sorted(idx)]


def chain_edges(names, src='img_src'):
    """Desired (dst, connector, src) wires for the chain names, then panic + out1. Pure; tested offline."""
    e, prev = [], src
    for n in names:
        e += [(n, 0, prev), (n + '_mix', 0, prev), (n + '_mix', 1, n),
              (n + '_slot', 0, prev), (n + '_slot', 1, n), (n + '_slot', 2, n + '_mix')]
        prev = n + '_slot'
    return e + [('panic', 0, prev), ('panic', 1, src), ('out1', 0, 'panic')]


def next_name(module, taken):
    k = 1
    while '%s%d' % (module, k) in taken:
        k += 1
    return '%s%d' % (module, k)


def logic():
    """fx_film_logic as a namespace (TD has no sys.path entry for builders/)."""
    ns = {'__name__': 'fx_film_logic'}
    exec(open(LOGIC_FILE).read(), ns)
    return types.SimpleNamespace(**ns)


# ------------------------------------------------------------------ shared GLSL (pure strings)
# lowbias32 hash (T-108: matches numpy uint32), value noise (smoothstep), fbm, luma, sRGB, hue ramp, soft knee.
GLSL_LIB = """
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hsh(ivec2 c, uint s) { return float(lb32(uint(c.x) * 1597334677u ^ lb32(uint(c.y) ^ (s * 2654435761u)))) * (1.0 / 4294967296.0); }
float hsh3(ivec3 c, uint s) { return hsh(c.xy, s ^ lb32(uint(c.z) + 0x9e3779b9u)); }
float vnoise(vec2 x, uint s) {
    ivec2 i = ivec2(floor(x)); vec2 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    float a = hsh(i, s), b = hsh(i + ivec2(1, 0), s), c = hsh(i + ivec2(0, 1), s), d = hsh(i + ivec2(1, 1), s);
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float vnoise3(vec3 x, uint s) {
    ivec3 i = ivec3(floor(x)); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
    float a0 = mix(mix(hsh3(i, s), hsh3(i + ivec3(1, 0, 0), s), f.x),
                   mix(hsh3(i + ivec3(0, 1, 0), s), hsh3(i + ivec3(1, 1, 0), s), f.x), f.y);
    float a1 = mix(mix(hsh3(i + ivec3(0, 0, 1), s), hsh3(i + ivec3(1, 0, 1), s), f.x),
                   mix(hsh3(i + ivec3(0, 1, 1), s), hsh3(i + ivec3(1, 1, 1), s), f.x), f.y);
    return mix(a0, a1, f.z);
}
float fbm(vec2 x, uint s, int oct) {
    float v = 0.0, a = 0.5, n = 0.0;
    for (int k = 0; k < 6; k++) { if (k >= oct) break; v += a * vnoise(x, s + uint(k) * 101u); n += a; x = x * 2.03 + 17.1; a *= 0.5; }
    return v / n;
}
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
vec3 srgb2lin(vec3 c) { return mix(c / 12.92, pow(max((c + 0.055) / 1.055, vec3(0.0)), vec3(2.4)), step(vec3(0.04045), c)); }
vec3 lin2srgb(vec3 c) { c = max(c, vec3(0.0)); return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c)); }
vec3 hue2rgb(float h) { return clamp(abs(mod(h * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0); }
vec3 kneex(vec3 c, float thr, float kn, float byluma) {      // soft-knee excess (StageLab JZB_Color_Bloom prefilter)
    float br = byluma > 0.5 ? luma(c) : max(c.r, max(c.g, c.b));
    float rq = clamp(br - thr + kn, 0.0, 2.0 * kn);
    rq = rq * rq / (4.0 * kn + 1e-5);
    return c * (max(rq, br - thr) / max(br, 1e-5));
}
"""

# EXT: in0 = picture. Output texel q (padded size) = the scale x scale box mean of the picture (held into the padding,
# so every mip level up to the pad multiple is exact, T-116 (1)), then soft-knee excess (mode 0) or the image (mode 1).
# uX0 = scale thr knee mode | uX1 = validW validH byluma -
EXT = """// FX_film EXT (compute): box downsample + soft knee into a mip-padded buffer.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uX0;
uniform vec4 uX1;
%s
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= osz.x || p.y >= osz.y) return;
    vec2 isz = vec2(textureSize(sTD2DInputs[0], 0));
    ivec2 q = min(p, ivec2(uX1.xy) - 1);
    int s = int(uX0.x + 0.5);
    int n = max(s / 2, 1);
    vec3 acc = vec3(0.0);
    for (int a = 0; a < 4; a++) { if (a >= n) break;
        for (int b = 0; b < 4; b++) { if (b >= n) break;
            vec2 c = vec2(q * s) + vec2(2.0 * float(a) + 1.0, 2.0 * float(b) + 1.0);   // corner of 4 px = 2x2 mean
            acc += texture(sTD2DInputs[0], c / isz).rgb;
        }
    }
    vec3 col = acc / float(n * n);
    vec3 e = uX0.w > 0.5 ? col : kneex(col, uX0.y, uX0.z, uX1.z);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(e, luma(e)));
}
""" % GLSL_LIB

# PYR (halation, diffusion): the glow pyramid = 7 small compute ops pyr1..pyr7, each half its input (pad multiple
# 128 = 2^7: every level exact), level k = [1 3 3 1] x [1 3 3 1] / 64 of level k-1 as 4 bilinear taps (weights 3/4 and
# 1/4 are exact bilinear fractions), edge held (extend hold = index clamp). Not TD's 2x2 box mips: a box mip pins a
# light to its texel's centre, so the glow sat up to half a coarse texel off the light (live 26 Oct, 31550: halo
# centroid 8-19 px off on the chart's corner lights, T-129); [1 3 3 1] keeps the centroid exact at every level. Not one
# npasses op over an atlas: 7 passes cost 2.4 ms GPU and a 2-pass composite-kernel version 1.95 ms (long per-thread
# loops are latency bound); 7 tiny ops are 4 taps each.
PYR_LEVELS = 8          # level 0 = EXT itself + levels 1..7 in two atlas ops
# Perf lane 3 (27 Oct, b2): the 7 one-level ops cost ~1.1 ms (7 x ~0.06 CPU + dispatch floor ~0.04 GPU each, T-199
# (3)). Now TWO ops, each several levels in one dispatch with the levels in shared memory (temporal blocking):
#   pyra = levels 1..4 of EXT, pyrb = levels 5..7 of pyra's level 4. Each op writes its levels stacked in ONE atlas
#   texture (level k0 at y 0, the next below it, all left-aligned; fx_film_logic.pyr_atlas). Same maths as the chain:
#   level k = [1 3 3 1] x [1 3 3 1] / 64 of level k-1, edge held; the first level of each op = 4 bilinear taps of its
#   source at coordinates clamped to the source rect (= extend hold), the others from shared memory (packed half =
#   the 16F rounding the chain's textures had). A workgroup owns a C x C core of its LAST level and computes the halos
#   it needs below (level j: core x 2^(NL-j) + 2 (2^(NL-j) - 1)); pyra 46 / 22 / 10 / 4 (21.6 KB shared), pyrb 22 / 10
#   / 4. Any input size (pad multiple 128 keeps every level exact).
PYRN = """// FX_film %(name)s (compute): pyramid levels %(k0)d..%(k1)d in one pass, stacked in one atlas; [1 3 3 1] per level, edge held.
// in0 = %(src)s. Source level rect: x 0, y %(syo)s, size %(ssz)s (source texels). C x C core of the last level per workgroup.
layout (local_size_x = 16, local_size_y = 16) in;
%(shared)s
uvec2 pk(vec4 v) { return uvec2(packHalf2x16(v.xy), packHalf2x16(v.zw)); }
vec4 upk(uvec2 u) { return vec4(unpackHalf2x16(u.x), unpackHalf2x16(u.y)); }
const float WT[4] = float[4](0.125, 0.375, 0.375, 0.125);
void main() {
    ivec2 wg = ivec2(gl_WorkGroupID.xy);
    int id = int(gl_LocalInvocationIndex);
    vec2 tsz = vec2(textureSize(sTD2DInputs[0], 0));
    vec2 ssz = %(ssz)s;                                    // source level size (texels)
    float syo = %(syo)s;                                   // source level y offset in its texture
    ivec2 n0 = ivec2(ssz);
%(body)s
}
"""
_PYR_FIRST = """    {   // level %(k)d (j = 1): 4 bilinear taps of the source, coordinates clamped to its rect (= hold)
        ivec2 n = n0 / 2, o = wg * %(core)d - %(halo)d;
        for (int r = 0; r < %(rounds)d; r++) {
            int i = id + 256 * r;
            if (i >= %(len2)d) break;
            ivec2 g = o + ivec2(i %% %(len)d, i / %(len)d);
            ivec2 gc = clamp(g, ivec2(0), n - 1);
            vec2 a = clamp(vec2(2 * gc) + 0.25, vec2(0.5), ssz - 0.5), b = clamp(vec2(2 * gc) + 1.75, vec2(0.5), ssz - 0.5);
            vec4 v = 0.25 * (texture(sTD2DInputs[0], vec2(a.x, a.y + syo) / tsz) + texture(sTD2DInputs[0], vec2(b.x, a.y + syo) / tsz)
                           + texture(sTD2DInputs[0], vec2(a.x, b.y + syo) / tsz) + texture(sTD2DInputs[0], vec2(b.x, b.y + syo) / tsz));
            %(keep)s
            ivec2 c = g - wg * %(core)d;
            if (g == gc && c.x >= 0 && c.y >= 0 && c.x < %(core)d && c.y < %(core)d)
                TDImageStoreOutput(0, ivec3(g.x, g.y + %(yo)s, 0), v);
        }
    }
"""
_PYR_NEXT = """    memoryBarrierShared();
    barrier();
    {   // level %(k)d: [1 3 3 1] of the level before (shared s%(jp)d, origin wg * %(pcore)d - %(phalo)d)
        ivec2 n = n0 / %(div)d, o = wg * %(core)d - %(halo)d, op_ = wg * %(pcore)d - %(phalo)d;
        for (int r = 0; r < %(rounds)d; r++) {
            int i = id + 256 * r;
            if (i >= %(len2)d) break;
            ivec2 g = o + ivec2(i %% %(len)d, i / %(len)d);
            ivec2 gc = clamp(g, ivec2(0), n - 1);
            ivec2 f = 2 * gc - 1 - op_;
            vec4 v = vec4(0.0);
            for (int y = 0; y < 4; y++)
                for (int x = 0; x < 4; x++)
                    v += (WT[x] * WT[y]) * upk(s%(jp)d[(f.y + y) * %(plen)d + f.x + x]);
            %(keep)s
            ivec2 c = g - wg * %(core)d;
            if (g == gc && c.x >= 0 && c.y >= 0 && c.x < %(core)d && c.y < %(core)d)
                TDImageStoreOutput(0, ivec3(g.x, g.y + %(yo)s, 0), v);
        }
    }
"""


def pyr_shader(name, k0, nl, src, ssz, syo, core=4):
    """GLSL text of one multi-level pyramid op: levels k0 .. k0+nl-1 from a source level (rect x 0, y syo, size ssz;
    GLSL expressions of tsz = the source texture size). Shared arrays for every level but the last."""
    shared, body = [], []
    for j in range(1, nl + 1):
        sc = 2 ** (nl - j)
        cj, hj = core * sc, sc - 1
        ln = cj + 2 * hj
        k = k0 + j - 1
        yo = '0' if j == 1 else '(%s)' % ' + '.join('n0.y / %d' % (2 ** i) for i in range(1, j))
        keep = ('s%d[i] = pk(v);' % j) if j < nl else ''
        if j < nl:
            shared.append('shared uvec2 s%d[%d];' % (j, ln * ln))
        d = {'k': k, 'core': cj, 'halo': hj, 'len': ln, 'len2': ln * ln, 'rounds': -(-ln * ln // 256), 'keep': keep,
             'yo': yo, 'div': 2 ** j}
        if j == 1:
            body.append(_PYR_FIRST % d)
        else:
            pc = core * 2 ** (nl - j + 1)
            d.update({'jp': j - 1, 'pcore': pc, 'phalo': 2 ** (nl - j + 1) - 1, 'plen': pc + 2 * (2 ** (nl - j + 1) - 1)})
            body.append(_PYR_NEXT % d)
    return PYRN % {'name': name, 'k0': k0, 'k1': k0 + nl - 1, 'src': src, 'ssz': ssz, 'syo': syo,
                   'shared': '\n'.join(shared), 'body': ''.join(body)}


# pyra: levels 1..4 of EXT (whole texture). pyrb: levels 5..7 of level 4 = pyra rows 14 n4 .. 15 n4 (n4 = pyra.h / 15).
PYRA = pyr_shader('PYRA', 1, 4, 'EXT', 'tsz', '0.0')
PYRB = pyr_shader('PYRB', 5, 3, 'PYRA (level 4 = the bottom rows)', 'vec2(tsz.x / 8.0, tsz.y / 15.0)',
                  '(14.0 * tsz.y / 15.0)')

# MIPG (halation, diffusion): smooth 4-tap pyramid sample + gaussian level weight. The gather op's inputs are
# ext (level 0, sTD2DInputs[0]), pyra (levels 1..4, [1]), pyrb (levels 5..7, [2]); a level-k sample = bilinear at its
# atlas rect with the coordinate clamped to the rect (= the extend hold the per-level textures had); textureLod 0,
# no mipmap filter needed.
MIPG = """
const float WSKIP = 1e-3;                            // fx_film_logic.WSKIP: levels below it are skipped
vec4 lvlTex(int k, vec2 uv, vec2 esz) {
    if (k == 0) return textureLod(sTD2DInputs[0], uv, 0.0);
    vec2 n = esz / exp2(float(k));                   // level-k size; atlas rows: fx_film_logic.pyr_atlas
    vec2 x = clamp(uv * n, vec2(0.5), n - 0.5);
    if (k <= 4) return textureLod(sTD2DInputs[1], vec2(x.x, x.y + esz.y * (1.0 - exp2(1.0 - float(k))))
                                  / vec2(0.5 * esz.x, esz.y * 0.9375), 0.0);
    return textureLod(sTD2DInputs[2], vec2(x.x, x.y + esz.y * (0.0625 - exp2(1.0 - float(k))))
                      / vec2(esz.x * 0.03125, esz.y * 0.0546875), 0.0);
}
vec4 mipTap(vec2 uv, float k, vec2 esz) {            // 4 bilinear taps half a level-k texel apart: tent, no blocks
    vec2 t = 0.5 * exp2(k) / esz;
    int ki = int(k + 0.5);
    return 0.25 * (lvlTex(ki, uv + vec2(-t.x, -t.y), esz) + lvlTex(ki, uv + vec2(t.x, -t.y), esz)
                 + lvlTex(ki, uv + vec2(-t.x, t.y), esz) + lvlTex(ki, uv + vec2(t.x, t.y), esz));
}
float lvlw(float k, float kc, float sp) { float d = (k - kc) / max(sp, 0.05); return exp(-0.5 * d * d); }
"""

CHART = """// FX_film test chart (compute, rgba16float): lights / ramp / grey / patches (fx_film_logic.chart_pixel).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uC;     // chart value bg grey
const vec2 LIGHTS[5] = vec2[5](%s);
const vec3 PATCH[24] = vec3[24](%s);
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec2 P = vec2(p) + 0.5;
    int ch = int(uC.x + 0.5);
    vec3 o;
    if (ch == 0) {
        o = vec3(uC.z);
        for (int k = 0; k < 5; k++) { vec2 d = P - LIGHTS[k]; if (dot(d, d) <= %.1f) o = vec3(uC.y); }
    } else if (ch == 1) {
        float v = P.x / float(sz.x);
        o = vec3(p.y < sz.y / 2 ? v : 0.1 * v);
    } else if (ch == 2) {
        o = vec3(uC.w);
    } else {
        int r = min(3, p.y * 4 / sz.y), c = min(5, p.x * 6 / sz.x);
        o = PATCH[r * 6 + c];
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(o, 1.0));
}
"""


def chart_shader(L):
    lights = ', '.join('vec2(%.1f, %.1f)' % xy for xy in L.LIGHTS)
    patches = ', '.join('vec3(%r, %r, %r)' % c for row in L.PATCHES for c in row)
    return CHART % (lights, patches, L.LIGHT_R * L.LIGHT_R)


P = "parent().par.{}.eval()"
# Gather resolution of the glow modules (halation, diffusion; perf lane 3): Quality half / quarter gather at the EXT
# resolution (1/2, 1/4: the glow is low-frequency; energy identical, light-core peak ~4-6 % lower, offline test) and
# the full-res composite reads it bilinearly; Quality full = the extract at 1/2 and the gather at every full-res pixel
# (the pre-lane-3 look). GQ['scale'] = EXT scale, GQ['g'] = full-res px per gather texel, GQ['res'] = gather size.
GQ = {'scale': "(4 if parent().par.Quality.eval() == 'quarter' else 2)",
      'g': "(1 if parent().par.Quality.eval() == 'full' else (4 if parent().par.Quality.eval() == 'quarter' else 2))"}
GQ['res'] = tuple("int(math.ceil(op('in1').%s / %s))" % (a, GQ['g']) for a in ('width', 'height'))
W_IN, H_IN = "op('in1').width", "op('in1').height"


# ------------------------------------------------------------------ TD side
def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = True
    return o


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _setv(par, v):
    if isinstance(v, str):
        _expr(par, v)
    else:
        par.mode = ParMode.CONSTANT
        par.val = v


def _compute(m, name, text, ins, res=None, fmt='useinput', extend=None, filt=None, dispatch=None):
    """Compute GLSL TOP `name` (T-47) + docked `<name>_compute` DAT. res None = input 0's size, else (w, h) numbers or
    expressions. extend = inputextenduv ('hold' / 'zero'), filt = inputfiltertype ('mipmap', T-116 (1)), dispatch =
    (x, y) workgroup counts (T-114 (1): autodispatchsize off) for the shared-memory scan. > 3 inputs = a GLSL Multi TOP
    (same compute pars, any input count; GLSL TOP has 3 connectors from Python on 31550, T-123 (1))."""
    g = _mk(m, glslmultiTOP if len(ins) > 3 else glslTOP, name)
    d = m.op(name + '_compute')
    if d is None:
        d = _mk(m, textDAT, name + '_compute')
    if d.dock != g:                                       # a re-made op (type change) keeps its DAT docked
        d.dock = g
    if d.text != text:
        d.text = text
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    if res is None:
        res = ('me.inputs[0].width', 'me.inputs[0].height')
    _setv(g.par.resolutionw, res[0])
    _setv(g.par.resolutionh, res[1])
    g.par.format = fmt
    if extend:
        g.par.inputextenduv = extend
    if filt:
        g.par.inputfiltertype.mode = ParMode.CONSTANT
        g.par.inputfiltertype = filt
    if dispatch:
        g.par.autodispatchsize = False
        _setv(g.par.dispatchsizex, dispatch[0])
        _setv(g.par.dispatchsizey, dispatch[1])
        g.par.dispatchsizez = 1
    for i, src in enumerate(ins):
        g.inputConnectors[i].connect(src)
    for extra in (name + '_pixel', name + '_info', name + '_compute1', name + '_vertex'):   # T-115 (5) templates
        if m.op(extra) is not None and m.op(extra) is not d:
            _sd(m.op(extra))
    return g


def _uniforms(g, U):
    """U = [(name, [x, y, z, w expressions])] -> vec0..vecN uniforms, all expressions."""
    g.seq.vec.numBlocks = max(len(U), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _setv(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)


def ext_exprs(scale, mult):
    """Expressions (strings) for the EXT buffer of in1 at 1/scale (scale = number or expression), padded to mult."""
    s = '(%s)' % scale
    vw = 'int(math.ceil(%s / %s))' % (W_IN, s)
    vh = 'int(math.ceil(%s / %s))' % (H_IN, s)
    return {'scale': s, 'vw': vw, 'vh': vh,
            'pw': 'int(math.ceil(%s / %d.0) * %d)' % (vw, mult, mult),
            'ph': 'int(math.ceil(%s / %d.0) * %d)' % (vh, mult, mult)}


def _ext(m, name, src, scale, thr, knee, byluma='0', mode='0', mult=128):
    """The shared EXT pass (rgba16float, mip-padded); returns (op, exprs)."""
    X = ext_exprs(scale, mult)
    g = _compute(m, name, EXT, [src], res=(X['pw'], X['ph']), fmt='rgba16float', extend='hold')
    _uniforms(g, [('uX0', [X['scale'], thr, knee, mode]), ('uX1', [X['vw'], X['vh'], byluma, '0'])])
    g.comment = 'EXT: 1/%s box mean + soft knee, padded to %d (mips exact, T-116 (1)).' % (scale, mult)
    return g, X


def _pyr(m, ext):
    """The shared pyramid on an EXT buffer: pyra (levels 1..4) + pyrb (levels 5..7), rgba16float atlases (rows:
    fx_film_logic.pyr_atlas). Returns [pyra, pyrb]. The old one-level ops pyr1..pyr7 are removed (perf lane 3)."""
    a = _compute(m, 'pyra', PYRA, [ext], res=('me.inputs[0].width // 2', 'me.inputs[0].height * 15 // 16'),
                 fmt='rgba16float', extend='hold', filt='linear',
                 dispatch=('me.inputs[0].width // 64', 'me.inputs[0].height // 64'))
    a.comment = 'PYR levels 1..4 of ext in one pass (atlas rows L1 L2 L3 L4), [1 3 3 1] each: glow stays centred.'
    b = _compute(m, 'pyrb', PYRB, [a], res=('me.inputs[0].width // 16', 'me.inputs[0].height * 7 // 120'),
                 fmt='rgba16float', extend='hold', filt='linear',
                 dispatch=('(me.inputs[0].width + 255) // 256', '(me.inputs[0].height + 479) // 480'))
    b.comment = 'PYR levels 5..7 of pyra level 4 in one pass (atlas rows L5 L6 L7).'
    for k in range(1, PYR_LEVELS):
        for n in ('pyr%d_compute' % k, 'pyr%d' % k):
            _sd(m.op(n))
    return [a, b]


def _outsel(m, in1, wet, cond=None):
    """Switch out_sel: 0 = in1 (Amount 0: exact passthrough, the engine is not pulled), 1 = wet."""
    sw = _mk(m, switchTOP, 'out_sel')
    sw.inputConnectors[0].connect(in1)
    sw.inputConnectors[1].connect(wet)
    _expr(sw.par.index, cond or '1 if parent().par.Amount.eval() > 0 else 0')
    sw.comment = 'Amount 0 -> in1 (exact, nothing upstream cooks).'
    return sw


H = {'mk': _mk, 'expr': _expr, 'sd': _sd, 'compute': _compute, 'uniforms': _uniforms, 'ext': _ext, 'pyr': _pyr,
     'pyr_ops': ['pyra', 'pyra_compute', 'pyrb', 'pyrb_compute'],
     'ext_exprs': ext_exprs, 'outsel': _outsel, 'P': P, 'W': W_IN, 'H': H_IN,
     'LIB': GLSL_LIB, 'MIPG': MIPG, 'EXT': EXT, 'GQ': GQ}


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            ex = getattr(c.par, name, None)
            if ex is not None and style == 'Menu' and (list(ex.menuNames) != list(o['names']) or
                                                       list(ex.menuLabels) != list(o['labels'])):
                v = ex.eval()                              # a grown menu is refreshed, value kept (T-190)
                ex.menuNames, ex.menuLabels = o['names'], o['labels']
                if v in o['names']:
                    ex.val = v
            if ex is not None or getattr(c.par, name + 'r', None) is not None:
                continue
            label = o.get('label', name)
            p = None
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']      # slider range only, no clamps (no limits)
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style == 'RGB':
                for q, v in zip(page.appendRGB(name, label=label), default):
                    q.default = v
                    q.val = v
            elif style in ('TOP', 'COMP', 'CHOP'):
                p = getattr(page, 'append' + style)(name, label=label)[0]
            if p is not None:
                p.default = default
                p.val = default


def _module(module):
    ns = dict(globals())
    exec(open(os.path.join(HERE, 'fx_film_%s.py' % module)).read(), ns)
    return ns


def _rows(c):
    t = c.op('slots')
    return [dict((k, t[i, k].val) for k in COLS) for i in range(1, t.numRows)]


def _cell(name, col):
    return "op('slots')['%s', '%s'].val" % (name, col)


def _slot_ops(c, name):
    """The rack's two ops around instance `name` (module COMP itself is made by _instance)."""
    mx = _mk(c, crossTOP, name + '_mix')
    _expr(mx.par.cross, 'float(%s or 0)' % _cell(name, 'mix'))
    mx.comment = 'Slot %s: dry/wet (slots.mix); only cooks when 0 < mix < 1.' % name
    sw = _mk(c, switchTOP, name + '_slot')
    _expr(sw.par.index, "0 if not int({e} or 0) or float({m} or 0) <= 0 else (1 if float({m}) >= 1 else 2)"
          .format(e=_cell(name, 'enabled'), m=_cell(name, 'mix')))
    sw.comment = 'Slot %s: 0 bypass (exact, module not cooked) / 1 module / 2 mix.' % name


# slot_gate (T-198, as builders/fx_glitch.py; perf lane 3 for this copied rack): a Switch TOP in each module COMP
# right before out1: 0 = in1 (exact passthrough, nothing upstream in the module cooks) when the rack slot is off
# (slots enabled 0 or mix <= 0, the same test as the rack's <name>_slot Switch), 1 = the module's own output. A
# visible <name>_mix viewer pulls the module even while <name>_slot bypasses it (RENDER_COST.md); with the gate a
# disabled module cannot cook through out1 (the T-199 (4) tail candidate). No slots row = on.
_SLOT_CELL = "parent(2).op('slots')[parent().name, '%s']"
SLOT_OFF_E = ("(parent(2).op('slots') is not None and (not int(float(getattr(" + _SLOT_CELL % 'enabled' +
              ", 'val', '1') or 0)) or float(getattr(" + _SLOT_CELL % 'mix' + ", 'val', '1') or 0) <= 0))")
SLOT_GATE_E = '0 if ' + SLOT_OFF_E + ' else 1'


def slot_off(enabled, mix):
    """The gate / <name>_slot test on two slots cells (strings; None = no row = on). Pure; tested offline."""
    en = '1' if enabled is None else enabled
    mx = '1' if mix is None else mix
    return not int(float(en or 0)) or float(mx or 0) <= 0


def gate_stages(stages):
    """Put 'slot_gate' just before 'out1' in the stage that lists out1 (else the last stage). Pure; tested offline."""
    if not stages or any('slot_gate' in s_['ops'] for s_ in stages):
        return stages
    s_ = next((s_ for s_ in stages if 'out1' in s_['ops']), stages[-1])
    s_['ops'] = [n for n in s_['ops'] if n != 'out1'] + ['slot_gate'] + (['out1'] if 'out1' in s_['ops'] else [])
    return stages


def _slot_gate(m, stages):
    """Insert / refresh `slot_gate` (in1 / module out) before out1 in module COMP m; idempotent (a module rebuild that
    re-wires out1 to its own source is re-gated). Returns stages (with slot_gate in the out1 stage)."""
    out1, in1 = m.op('out1'), m.op('in1')
    if out1 is None or in1 is None or not out1.inputConnectors or not out1.inputConnectors[0].connections:
        return stages
    conn = out1.inputConnectors[0].connections[0]
    src = conn.owner
    g = m.op('slot_gate')
    if src is not g:
        if src is in1:
            _sd(g)
            return stages
        g = _mk(m, switchTOP, 'slot_gate')
        g.inputConnectors[0].connect(in1)
        g.inputConnectors[1].connect(conn)
        out1.inputConnectors[0].connect(g)
    elif not g.inputConnectors[0].connections or g.inputConnectors[0].connections[0].owner is not in1:
        g.inputConnectors[0].connect(in1)
    _expr(g.par.index, SLOT_GATE_E)
    g.comment = ('Slot off (slots enabled 0 / mix 0) = in1 untouched, nothing in this module cooks, also when a '
                 'viewer shows the rack (RENDER_COST.md, T-198); slot on = the module output.')
    return gate_stages(stages)


def gate_upgrade(comp_path, name):
    """Gate-only upgrade of an EXISTING instance (main: one rack per exec): adds / refreshes `slot_gate` and re-applies
    the module's stored stage plan with it, without rebuilding the module. Returns the gate index (0 = slot off)."""
    c = op(comp_path)
    m = c.op(name) if c is not None else None
    if m is None or not m.isCOMP:
        return {'name': name, 'error': 'no instance'}
    hm = op('/jazib_mcp/handlers').module
    plan = hm._stage_plan(m) or {}
    stages = [dict(s_, ops=[n for n in (s_.get('ops') or []) if m.op(n) is not None]) for s_ in plan.get('stages', [])]
    had = m.op('slot_gate') is not None
    stages = [s_ for s_ in _slot_gate(m, stages) if s_['ops']]
    g = m.op('slot_gate')
    if g is not None and not had and stages:
        hm.layout_stages(m, stages, plan.get('colors', True), arrange=plan.get('arrange') or 'mixed')
    return {'name': name, 'gated': g is not None, 'new': g is not None and not had,
            'index': int(g.par.index.eval()) if g is not None else None}


def _instance(c, name, module, panel=True):
    M = _module(module)
    m = c.op(name)
    if m is None or not m.isCOMP:
        m = _mk(c, baseCOMP, name)
    _pars(m, M['PAGES'])
    m.comment = 'FX_film module %s (%s). Pars on its custom pages; pulse Opencontrols for the zkit panel.' % (name, module)
    Hm = dict(H)
    Hm['L'] = logic()
    stages = _slot_gate(m, M['build'](m, Hm))
    m.par.opviewer.expr = "me.op('out1')"
    m.par.opviewer.mode = ParMode.EXPRESSION
    m.viewer = True
    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](m.path, pages=M['PANEL_PAGES'], d=56, cols=6)
        pt = m.op('controls/zk_presets')
        if pt is not None and pt.numRows <= 1:              # seed the module presets once (user's own kept)
            Lz = m.op('controls/zk_logic').module
            for slot, pname, vals in M['PRESETS']:
                pt.appendRow([slot, pname, Lz.DEFAULT_COLOR, Lz.preset_dump(vals)])
        stages = [{'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window']}] + stages
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if m.op(n) is not None]
    op('/jazib_mcp/handlers').module.layout_stages(m, [s_ for s_ in stages if s_['ops']], True, arrange='mixed')
    _slot_ops(c, name)
    return {'instance': m.path, 'panel': bool(info)}


def rewire(c):
    """Make the chain match `slots`; touches only connectors that differ. Returns the number of wires changed."""
    names = [n for n in plan_chain(_rows(c)) if c.op(n) is not None]
    changed = 0
    for dst, i, src in chain_edges(names):
        d, s = c.op(dst), c.op(src)
        conns = d.inputConnectors[i].connections
        if conns and conns[0].owner == s:
            continue
        d.inputConnectors[i].connect(s.outputConnectors[0])   # a COMP source needs its connector (T-111 (2))
        changed += 1
    return changed


def _layout(c):
    names = plan_chain(_rows(c))
    chain = []
    for n in names:
        chain += [n, n + '_mix', n + '_slot']
    stages = [
        {'title': 'Rack', 'role': 'control', 'ops': ['slots'],
         'body': 'slots: name module enabled order mix. enabled/mix live; add/remove/order = builder rewire.'},
        {'title': '1 Input', 'role': 'input', 'ops': ['in1', 'test_clip', 'test_chart', 'img_src'],
         'body': 'in1 TOP, the stored webcam clip or the test chart (Input: auto = in1 when wired).'},
        {'title': '2 Slots', 'role': 'process', 'ops': [n for n in chain if c.op(n) is not None],
         'body': 'Lens -> glare -> film -> colour. Per slot: module COMP -> _mix (Cross) -> _slot (Switch).'},
        {'title': '3 Out', 'role': 'output', 'ops': ['panic', 'out1'], 'body': 'Panic = instant passthrough of the rack.'},
    ]
    stages = [s for s in stages if s['ops']]
    return op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')


def build(parent_path='/project1/lab', panel=True, rows=None):
    """rows: module names for a first build (default MODULES). An existing `slots` table is kept as it is."""
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('FX_film: film + lens rack. In: in1 TOP. Out: out1 TOP. Module slots from `slots` '
                 '(builders/fx_film.py add/remove/rewire). Panic = instant passthrough.')
    L = logic()
    _pars(c, [('Rack', [
        ('Panic', 'Toggle', False, {'label': 'Panic (passthrough)'}),
        ('Input', 'Menu', 'auto', {'names': ['auto', 'live', 'test', 'chart'],
                                   'labels': ['Auto', 'Live (in1)', 'Test clip', 'Test chart']}),
        ('Chart', 'Menu', 'lights', {'names': L.CHARTS, 'labels': ['Lights (HDR discs)', 'Ramp', 'Grey', 'Patches']}),
        ('Chartvalue', 'Float', 4.0, {'min': 0, 'max': 16, 'label': 'Chart light value'}),
        ('Chartbg', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Chart background'}),
        ('Chartgrey', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Chart grey'}),
    ])])
    in1 = _mk(c, inTOP, 'in1')
    tc = _mk(c, moviefileinTOP, 'test_clip')
    tc.par.file = TEST_CLIP
    tc.par.outputresolution = 'custom'
    tc.par.resolutionw, tc.par.resolutionh = 1080, 1920
    tc.par.outputaspect = 'resolution'
    tc.par.fillmode = 'fill'
    tc.comment = 'Test picture: stored 5 s webcam clip, filled to 1080x1920 (cooks only while selected).'
    ch = _compute(c, 'test_chart', chart_shader(L), [], res=(1080, 1920), fmt='rgba16float')
    _uniforms(ch, [('uC', ['parent().par.Chart.menuIndex', P.format('Chartvalue'), P.format('Chartbg'),
                           P.format('Chartgrey')])])
    ch.comment = 'Test chart (rgba16float): lights (5 HDR discs r 6 px), ramp, grey, patches; cooks only while selected.'
    img = _mk(c, switchTOP, 'img_src')
    img.inputConnectors[0].connect(tc)
    img.inputConnectors[1].connect(in1)
    img.inputConnectors[2].connect(ch)
    _expr(img.par.index, "(2 if parent().par.Input.eval() == 'chart' else (1 if parent().par.Input.eval() == 'live' "
          "or (parent().par.Input.eval() == 'auto' and any(len(cn.connections) for cn in parent().inputConnectors "
          "if cn.inOP is not None and cn.inOP.name == 'in1')) else 0))")
    pn = _mk(c, switchTOP, 'panic')
    _expr(pn.par.index, '1 if parent().par.Panic.eval() else 0')
    pn.comment = 'Panic: 1 = img_src straight to out1 (same frame; slots stop cooking).'
    _mk(c, outTOP, 'out1')
    t = c.op('slots')
    if t is None:
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        for r in DEFAULT_ROWS:
            if rows is None or r[1] in rows:
                t.appendRow(r)
    t.comment = 'Rack state: one row per module instance. enabled 0/1, mix 0..1 act live; order -> rewire.'
    out = []
    for r in _rows(c):
        out.append(_instance(c, r['name'], r['module'], panel=panel and c.op(r['name']) is None))
    wires = rewire(c)
    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    lay = _layout(c)
    return {'comp': c.path, 'instances': out, 'wires_changed': wires, 'layout': str(lay)[:300]}


def add(comp_path, module, name=None, order=None, enabled=1, mix=1, panel=True):
    c = op(comp_path)
    rows = _rows(c)
    name = name or next_name(module, set(r['name'] for r in rows) | set(o.name for o in c.children))
    if order is None:
        order = int(max([float(r['order'] or 0) for r in rows] + [0])) + 1
    c.op('slots').appendRow([name, module, enabled, order, mix])
    info = _instance(c, name, module, panel=panel)
    wires = rewire(c)
    _layout(c)
    return {'added': name, 'instance': info, 'wires_changed': wires}


def remove(comp_path, name):
    c = op(comp_path)
    t = c.op('slots')
    if t.row(name) is not None:
        t.deleteRow(name)
    wires = rewire(c)                                     # re-route around it first, then remove its ops
    m = c.op(name)
    if m is not None:
        w = m.op('controls_window')
        if w is not None and w.isOpen:
            w.par.winclose.pulse()
    for n in (name + '_slot', name + '_mix', name):
        _sd(c.op(n))
    _layout(c)
    return {'removed': name, 'wires_changed': wires}


def solo(comp_path, name):
    """Live-check helper: enable only `name` (mix 1), every other slot enabled 0. Returns the previous enabled column."""
    t = op(comp_path).op('slots')
    prev = {}
    for i in range(1, t.numRows):
        n = t[i, 'name'].val
        prev[n] = t[i, 'enabled'].val
        t[i, 'enabled'] = 1 if n == name else 0
        if n == name:
            t[i, 'mix'] = 1
    return prev


def read(o):
    """numpyArray of a TOP (row 0 = bottom). Call in a separate exec >= 3 frames after a change (T-111 (4), T-116 (4))."""
    return o.numpyArray(delayed=False)
