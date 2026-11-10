"""urdu_type builder: /project1/lab/BJ_urdu_type (TD 2025.31550). Urdu / Arabic / mixed text as whole-word rasters
with our own bidi-lite layout and word-level animation (fade, slide, scale, wipe, blur, pulse), outline, glow, shadow.

Spec: docs/research/BJ_urdu_arabic_text_shaping.md section 5 (clean-room, our own), SAFE ROUTE (T-76): words are shaped
and rasterised OUTSIDE TD by HarfBuzz (builders/urdu_render.py, a child process on the system Python running hb-view +
hb-shape) into ONE atlas PNG with alpha + a metrics JSON (advance, ink box, baseline, glyph clusters per word). The
COMP loads the atlas with Movie File In TOPs (two, double-buffered) and lays words out from the JSON
(builders/urdu_type_logic.py). NO Text TOP with an Urdu font, NO TOP method call (numpyArray / evalTextSize / sample /
cook(force) on a TOP), here or in the runtime (builders/urdu_type_rt.py). Run inside TD through td_exec:
    g = dict(globals()); exec(open('<repo>/builders/urdu_type.py').read(), g); g['build']('/project1/lab', upto=1)
build(parent_path, name, pool=32, controls=True, upto=4) is idempotent (ops reused by name); upto = build in steps
(1 atlas + tables + render, 2 + place pass, 3 + style/compose/out + watchers, 4 + zkit controls + stage layout).
GPU: ONE compute pass places every word (atlas via the `tops` par, word params via a CHOP to TOP read into shared
memory), half-res Blur TOPs for glow + shadow, ONE compute pass composes bg / shadow / glow / outline / fill.
Compute mode only (T-46/T-47). T-70 safe: own controls_window closed first, every destroy through safe_destroy,
the panel container is never destroyed (zkit updates it in place), the network pane is never moved. No functions in
storage (T-67). Pure ASCII (Urdu defaults written as escapes).
"""

import os

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
NAME = 'BJ_urdu_type'
POOL = 32
RENDER_VERSION = 2
LOGIC = "op('urdu_type_logic').module"
DEFAULT_TEXT = '\u0627\u0631\u062f\u0648 \u0632\u0628\u0627\u0646\\n\u06c1\u06cc\u0644\u0648 hello \u0627\u0631\u062f\u0648 2026'

PAR_EXEC = '''# urdu_type: parameter changes -> coalesced rebuild / relayout; Trigger / Rebuild pulses
RT = op('urdu_rt')

def onValueChange(par, prev):
\tm = RT.module
\tif par.name in m.REBUILD_PARS:
\t\tm.schedule('rebuild')
\telif par.name in m.RELAYOUT_PARS:
\t\tm.schedule('relayout')
\telif par.page.name == 'Anim':
\t\tm.cook_anim()
\treturn

def onPulse(par):
\tm = RT.module
\tif par.name == 'Trigger':
\t\tm.trigger()
\telif par.name == 'Rebuild':
\t\tm.rebuild(force=True)
\treturn
'''

DAT_EXEC = '''# urdu_type: the Textdat DAT changed -> rebuild (one flush next frame)
def onTableChange(dat):
\top('urdu_rt').module.schedule('rebuild')
\treturn
'''

ANIM_CB = '''# urdu_type: per-word animation (one sample per word slot, one channel per field)
def onCook(scriptOp):
\top('urdu_rt').module.anim_cook(scriptOp)
\treturn

def onSetupParameters(scriptOp):
\treturn

def onPulse(par):
\treturn
'''

TICK = '''# urdu_type: frame start -> cook the anim CHOP only while something moves
def onFrameStart(frame):
\top('urdu_rt').module.tick()
\treturn
'''

REST_CB = ANIM_CB.replace('anim_cook', 'rest_cook').replace('per-word animation', 'rest layout x/y/w/h/rank')


def place_glsl(pool, nfields):
    """ONE compute pass: every live word is inverse-transformed into its atlas rect and composited (coverage only)."""
    assert pool <= 32, 'tile masks are one uint'
    return """// urdu_type place: input 0 = params (CHOP to TOP: x = word slot, y = field), inputs 1, 2 = atlas A / B (alpha)
// 16x16 groups and only the n live words are loaded into shared memory (8x8 + all slots cost 2.6 ms GPU, 26 Oct)
// Perf 27 Oct (b3 wave 3): each group keeps a bit mask of the words whose box touches its tile (M) and runs only
// those, in slot order (same composite order, bit-exact); g = 1 where a word box grown by the outline radius + 2 px
// touches the pixel (MN), so compose runs its 24-tap outline only there (elsewhere every tap reads 0: same result).
layout (local_size_x = 16, local_size_y = 16) in;
uniform vec4 uA;   // n words, pad px, wipe soft px, blur taps
uniform vec4 uB;   // show ink boxes (1/0), box line px, atlas slot (0 = A, 1 = B), outline px (0 = off)
#define NW {pool}
#define NF {nf}
shared float P[NF][NW];
shared vec4 R[NW];   // screen-space AABB per word (x0, y0, x1, y1)
shared uint M;       // words whose box touches this tile
shared uint MN;      // words whose box grown by the outline reach touches this tile

vec2 rot2(vec2 d, float deg) {{ float a = radians(deg); float c = cos(a), s = sin(a); return vec2(c * d.x + s * d.y, -s * d.x + c * d.y); }}

float atlasA(int i, vec2 d)
{{
\tvec2 ts = vec2(P[19][i], P[20][i]);
\tvec2 q = clamp(d + 0.5 * ts, vec2(0.5), ts - 0.5) + vec2(P[17][i], P[18][i]);
\tif (uB.z < 0.5) return texture(sTD2DInputs[1], q * uTD2DInfos[1].res.xy).a;
\treturn texture(sTD2DInputs[2], q * uTD2DInfos[2].res.xy).a;
}}

float word(int i, vec2 p, float cov)
{{
\tif (P[15][i] < 0.5 || P[7][i] <= 0.0) return cov;
\tvec4 r = R[i];
\tif (p.x < r.x || p.x > r.z || p.y < r.y || p.y > r.w) return cov;
\tfloat pad = uA.y + P[9][i];
\tvec2 d = p - vec2(P[0][i] + P[2][i], P[1][i] + P[3][i]);
\td = rot2(d, P[6][i]) / vec2(max(abs(P[4][i]), 1e-4), max(abs(P[5][i]), 1e-4));
\tfloat bx0 = P[10][i], by0 = P[11][i], bx1 = P[12][i], by1 = P[13][i];
\tif (uB.x > 0.5) {{
\t\tfloat e = uB.y / max(abs(P[4][i]), 1e-4);
\t\tbool inb = d.x > bx0 - e && d.x < bx1 + e && d.y > by0 - e && d.y < by1 + e;
\t\tbool core = d.x > bx0 && d.x < bx1 && d.y > by0 && d.y < by1;
\t\tif (inb && !core) return max(cov, 0.7);
\t}}
\tif (d.x < bx0 - pad || d.x > bx1 + pad || d.y < by0 - pad || d.y > by1 + pad) return cov;
\tfloat a;
\tfloat bl = P[9][i];
\tif (bl > 0.5) {{
\t\ta = 0.0;
\t\tint taps = int(uA.w);
\t\tfor (int k = 0; k < taps; k++) {{
\t\t\tfloat rr = bl * sqrt((float(k) + 0.5) / float(taps));
\t\t\tfloat th = float(k) * 2.39996323;
\t\t\ta += atlasA(i, d + vec2(cos(th), sin(th)) * rr);
\t\t}}
\t\ta /= float(taps);
\t}} else {{
\t\ta = atlasA(i, d);
\t}}
\tfloat rv = P[8][i];
\tif (rv < 1.0) {{
\t\tfloat W = (bx1 - bx0) + 2.0 * pad;
\t\tfloat t = (P[14][i] > 0.5) ? (bx1 + pad - d.x) / W : (d.x - (bx0 - pad)) / W;
\t\tfloat soft = max(uA.z / W, 1e-4);
\t\ta *= (rv <= 0.0) ? 0.0 : 1.0 - smoothstep(rv - soft, rv, t);
\t}}
\ta *= clamp(P[7][i], 0.0, 1.0);
\treturn a + cov * (1.0 - a);
}}

void main()
{{
\tuint li = gl_LocalInvocationIndex;
\tint n = clamp(int(uA.x), 0, NW);
\tif (li == 0u) {{ M = 0u; MN = 0u; }}
\tfor (int k = int(li); k < NF * n; k += 256) {{
\t\tint f = k / n, w = k - f * n;
\t\tP[f][w] = texelFetch(sTD2DInputs[0], ivec2(w, f), 0).r;
\t}}
\tbarrier();
\tif (li < uint(n)) {{
\t\tint i = int(li);
\t\tfloat pad = uA.y + P[9][i];
\t\tvec2 c = vec2(P[0][i] + P[2][i], P[1][i] + P[3][i]);
\t\tvec2 lo = vec2(P[10][i], P[11][i]) - pad, hi = vec2(P[12][i], P[13][i]) + pad;
\t\tvec2 s = vec2(abs(P[4][i]), abs(P[5][i]));
\t\tvec2 e0 = lo * s, e1 = hi * s;
\t\tfloat rad = max(max(length(e0), length(e1)), max(length(vec2(e0.x, e1.y)), length(vec2(e1.x, e0.y))));
\t\tvec4 box = vec4(c + e0, c + e1);
\t\tif (abs(P[6][i]) > 0.001) box = vec4(c - rad, c + rad);
\t\tR[i] = box;
\t\tvec2 t0 = vec2(gl_WorkGroupID.xy * 16u) + 0.5, t1 = t0 + 15.0;
\t\tif (box.z >= t0.x && box.x <= t1.x && box.w >= t0.y && box.y <= t1.y) atomicOr(M, 1u << uint(i));
\t\tfloat e = uB.w > 0.0 ? uB.w + 2.0 : -1.0;
\t\tif (e > 0.0 && box.z + e >= t0.x && box.x - e <= t1.x && box.w + e >= t0.y && box.y - e <= t1.y)
\t\t\tatomicOr(MN, 1u << uint(i));
\t}}
\tbarrier();
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tvec2 p = vec2(px) + 0.5;
\tfloat cov = 0.0;
\tuint m = M;
\tfor (int j = 0; j < NW; j++) {{
\t\tif (m == 0u) break;
\t\tint k = findLSB(m);
\t\tm &= m - 1u;
\t\tcov = word(k, p, cov);
\t}}
\tfloat near = 0.0;
\tuint mn = MN;
\tfloat e = uB.w + 2.0;
\tfor (int j = 0; j < NW; j++) {{
\t\tif (mn == 0u) break;
\t\tint k = findLSB(mn);
\t\tmn &= mn - 1u;
\t\tvec4 r = R[k];
\t\tif (p.x >= r.x - e && p.x <= r.z + e && p.y >= r.y - e && p.y <= r.w + e) {{ near = 1.0; break; }}
\t}}
\tTDImageStoreOutput(0, ivec3(px, 0), vec4(cov, near, cov, cov));
}}
""".format(pool=pool, nf=nfields)


COMPOSE_GLSL = '''// urdu_type compose: in0 = coverage, in1 = glow blur (half), in2 = shadow blur (half), in3 = background (in1 TOP)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uFill;   // rgb, alpha
uniform vec4 uLine;   // outline rgb, outline px
uniform vec4 uGlow;   // glow rgb, amount
uniform vec4 uShad;   // offset x px, offset y px, amount, premult (1/0)
uniform vec4 uBg;     // rgb, alpha
uniform vec4 uMode;   // background mode (0 none, 1 colour, 2 input), outline alpha, 0, 0
vec4 over(vec4 top, vec4 bot) { return top + bot * (1.0 - top.a); }
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tvec2 uv = (vec2(px) + 0.5) / vec2(res);
\tvec4 pc = texelFetch(sTD2DInputs[0], px, 0);   // r = coverage, g = 1 near a word (place, perf 27 Oct)
\tfloat cov = pc.r;
\tvec4 col = vec4(0.0);
\tint bm = int(uMode.x + 0.5);
\tif (bm == 1) col = vec4(uBg.rgb * uBg.a, uBg.a);
\telse if (bm == 2) col = texture(sTD2DInputs[3], uv);
\tif (uShad.z > 0.0) {
\t\tfloat sa = clamp(texture(sTD2DInputs[2], uv - uShad.xy / vec2(res)).r * uShad.z, 0.0, 1.0);
\t\tcol = over(vec4(0.0, 0.0, 0.0, sa), col);
\t}
\tif (uGlow.a > 0.0) {
\t\tfloat ga = clamp(texture(sTD2DInputs[1], uv).r * uGlow.a, 0.0, 1.0);
\t\tcol = over(vec4(uGlow.rgb * ga, ga), col);
\t}
\tif (uLine.a > 0.25 && pc.g > 0.5) {
\t\tfloat oa = cov;
\t\tfloat r = uLine.a;
\t\tfor (int k = 0; k < 16; k++) {
\t\t\tfloat th = float(k) * 0.39269908;
\t\t\tvec2 o = vec2(cos(th), sin(th));
\t\t\toa = max(oa, texelFetch(sTD2DInputs[0], px + ivec2(round(o * r)), 0).r);
\t\t\tif ((k & 1) == 0) oa = max(oa, texelFetch(sTD2DInputs[0], px + ivec2(round(o * r * 0.5)), 0).r);
\t\t}
\t\toa *= uMode.y;
\t\tcol = over(vec4(uLine.rgb * oa, oa), col);
\t}
\tfloat fa = cov * uFill.a;
\tcol = over(vec4(uFill.rgb * fa, fa), col);
\tif (uShad.w < 0.5 && col.a > 0.0) col.rgb /= col.a;
\tTDImageStoreOutput(0, ivec3(px, 0), TDOutputSwizzle(col));
}
'''

STAGES = [
    {'title': 'Controls', 'role': 'control',
     'ops': ['controls', 'controls_window', 'par_exec', 'textdat_exec', 'tick', 'urdu_type_logic', 'urdu_render',
             'urdu_rt', 'anim_cb', 'rest_cb'],
     'body': 'zkit panel (Text, Anim, Style pages); pulse Opencontrols. par_exec: text/font/size -> re-render, '
             'gap/align/anchor -> relayout (coalesced, next frame); Trigger restarts timed transitions. tick cooks '
             'anim only while words move. urdu_type_logic = pure logic, urdu_render = the OUTSIDE-TD HarfBuzz renderer '
             '(run as a child process), urdu_rt = TD runtime.'},
    {'title': '1 Parse + shape (outside TD)', 'role': 'process', 'ops': ['words'],
     'body': 'Text (or line Line of Textdat) -> words (punctuation stays glued), bidi level per word (UAX #9 at word '
             'level, checked vs fribidi). A child process (system Python + hb-view/hb-shape) shapes each word with '
             'HarfBuzz and packs one atlas PNG + metrics JSON (ink box, baseline, advance, glyph clusters) in the '
             'cache. No Text TOP, no TOP method in TD (T-74, T-76).'},
    {'title': '2 Atlas (double buffer)', 'role': 'input', 'ops': ['atlas_a', 'atlas_b'],
     'body': 'Movie File In TOPs load the atlas PNG. The new atlas goes into the idle slot; 4 frames later the slot '
             'swaps together with the words table, so boxes and pixels always match.'},
    {'title': '3 Layout', 'role': 'process', 'ops': ['layout', 'rest', 'out_words', 'out_rest'],
     'body': 'Lines filled in logical order, wrapped at Maxwidth, each line reordered by level (L2), Wordgap x Size '
             'between ink boxes, one baseline per line across fonts, Align start = right edge for RTL. '
             'out_words = table, out_rest = x/y/w/h/rank per word.'},
    {'title': '4 Animate', 'role': 'process', 'ops': ['in2', 'anim', 'params'],
     'body': 'Progress from Timing (manual / seconds / bpm / audio; in2 CHOP level / beat / progress override) -> '
             'per-word local progress with Stagger + Order + Ease -> 21 fields per word -> params texture.'},
    {'title': '5 Place (1 compute pass)', 'role': 'process', 'ops': ['place', 'place_compute'],
     'body': 'Every word inverse-transformed into its atlas rect in ONE compute dispatch (params in shared memory, '
             'per-word screen box cull). Wipe reveals along each word reading direction, blur = disc taps.'},
    {'title': '6 Style + output', 'role': 'output',
     'ops': ['in1', 'glow_src', 'glow_blur', 'shadow_blur', 'compose', 'compose_compute', 'result', 'out1',
             'info_view', 'preview'],
     'body': 'Half-res blurs for glow + shadow, ONE compute pass: background (none / colour / in1) <- shadow <- '
             'glow <- outline (dilated coverage) <- fill. Premultiplied unless Premult off. out1 = output only. '
             'preview = out + info line (Showinfo, ASCII only).'},
]


def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _close_window(c):
    w = c.op('controls_window')
    if w is not None and w.OPType == 'windowCOMP' and w.isOpen:
        w.par.winclose.pulse()
        return True
    return False


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType != cls.__name__:
        _sd(o)
        o = None
    return o or c.create(cls, name)


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _page(c, name):
    for p in c.customPages:
        if p.name == name:
            return p
    return c.appendCustomPage(name)


def _par(c, page, style, name, label, default=None, rng=None, menu=None, clamp_min=False, ro=False):
    pg = _page(c, page)
    if style in ('RGB', 'XY') and getattr(c.parGroup, name, None) is not None:
        return
    if style not in ('RGB', 'XY') and getattr(c.par, name, None) is not None:
        ex = getattr(c.par, name)
        if ex.label != label:
            ex.label = label
        return
    if style == 'Menu':
        p = pg.appendMenu(name, label=label)[0]
        p.menuNames = [m[0] for m in menu]
        p.menuLabels = [m[1] for m in menu]
    elif style == 'StrMenu':
        p = pg.appendStrMenu(name, label=label)[0]
        p.menuNames = list(menu)
        p.menuLabels = list(menu)
    else:
        p = getattr(pg, 'append' + style)(name, label=label)[0]
    if style in ('RGB', 'XY'):
        for k, v in zip(getattr(c.parGroup, name), default):
            k.default = v
            k.val = v
            if rng is not None:
                k.normMin, k.normMax = rng
        return
    if rng is not None:
        p.normMin, p.normMax = rng
        if clamp_min:
            p.min = rng[0]
            p.clampMin = True
    if default is not None:
        p.default = default
        p.val = default
    if ro:
        p.readOnly = True


def _pars(c, L, fonts):
    T, S, A, Y, K, I, F = 'Text', 'Style', 'Anim', 'Layout', 'Control', 'Info', 'Files'
    _par(c, T, 'Str', 'Text', 'Text (\\n = new line)', DEFAULT_TEXT)
    _par(c, T, 'OP', 'Textdat', 'Text DAT (lines)')
    _par(c, T, 'Int', 'Line', 'Line (cue)', 0, (0, 16))
    _par(c, T, 'Menu', 'Direction', 'Direction', 'auto', menu=L.DIRECTION)
    _par(c, T, 'StrMenu', 'Fontrtl', 'Urdu font', 'Noto Nastaliq Urdu', menu=fonts)
    _par(c, T, 'File', 'Fontfilertl', 'Urdu font file')
    _par(c, T, 'Menu', 'Typefacertl', 'Urdu typeface', 'Regular', menu=L.TYPEFACE)
    _par(c, T, 'Int', 'Weight', 'Urdu weight (wght axis, 0 = font default)', 0, (0, 900))
    _par(c, T, 'StrMenu', 'Fontltr', 'Latin font', 'Helvetica Neue', menu=fonts)
    _par(c, T, 'File', 'Fontfileltr', 'Latin font file')
    _par(c, T, 'StrMenu', 'Fontdigits', 'Digits font (empty = Latin)', '', menu=fonts)
    _par(c, T, 'Float', 'Size', 'Size px', 160.0, (16, 400))
    _par(c, T, 'Float', 'Wordgap', 'Word gap em', 0.30, (0, 2))
    _par(c, T, 'Float', 'Linegap', 'Line gap', 1.0, (0.4, 2))
    _par(c, T, 'Float', 'Maxwidth', 'Wrap width px (0 off)', 960.0, (0, 4000))
    _par(c, T, 'Menu', 'Align', 'Align', 'center', menu=L.ALIGN)
    _par(c, T, 'Float', 'Anchorx', 'Anchor x', 0.5, (0, 1))
    _par(c, T, 'Float', 'Anchory', 'Anchor y', 0.5, (0, 1))
    _par(c, T, 'Int', 'Maxwords', 'Max words', 24, (1, POOL))

    _par(c, S, 'RGB', 'Fill', 'Fill', (1.0, 1.0, 1.0), (0, 1))
    _par(c, S, 'Float', 'Fillalpha', 'Fill alpha', 1.0, (0, 1))
    _par(c, S, 'RGB', 'Outline', 'Outline', (0.85, 0.65, 0.2), (0, 1))
    _par(c, S, 'Float', 'Outlinepx', 'Outline px', 0.0, (0, 16))
    _par(c, S, 'Float', 'Outlinealpha', 'Outline alpha', 1.0, (0, 1))
    _par(c, S, 'RGB', 'Glowcolor', 'Glow colour', (1.0, 0.8, 0.4), (0, 1))
    _par(c, S, 'Float', 'Glow', 'Glow', 0.0, (0, 4))
    _par(c, S, 'Float', 'Glowsize', 'Glow size px', 24.0, (1, 120))
    _par(c, S, 'Float', 'Shadow', 'Shadow', 0.0, (0, 2))
    _par(c, S, 'Float', 'Shadowsize', 'Shadow soft px', 12.0, (1, 80))
    _par(c, S, 'XY', 'Shadowoff', 'Shadow offset px', (8.0, -8.0), (-60, 60))
    _par(c, S, 'Menu', 'Background', 'Background', 'none', menu=L.BACKGROUND)
    _par(c, S, 'RGB', 'Bgcolor', 'Bg colour', (0.0, 0.0, 0.0), (0, 1))
    _par(c, S, 'Float', 'Bgalpha', 'Bg alpha', 1.0, (0, 1))
    _par(c, S, 'Toggle', 'Premult', 'Premultiplied out', True)

    _par(c, A, 'Menu', 'Mode', 'Mode', 'fade', menu=L.MODE)
    _par(c, A, 'Menu', 'Timing', 'Timing', 'seconds', menu=L.TIMING)
    _par(c, A, 'Float', 'Progress', 'Progress (manual)', 1.0, (0, 1))
    _par(c, A, 'Float', 'Stagger', 'Stagger', 0.6, (0, 1))
    _par(c, A, 'Menu', 'Order', 'Order', 'reading', menu=L.ORDER)
    _par(c, A, 'Int', 'Seed', 'Random seed', 1, (0, 100))
    _par(c, A, 'Menu', 'Ease', 'Ease', 'ease', menu=L.EASE)
    _par(c, A, 'Float', 'Seconds', 'Seconds', 2.0, (0.1, 10))
    _par(c, A, 'Float', 'Bpm', 'BPM', 120.0, (60, 200))
    _par(c, A, 'Float', 'Beats', 'Beats', 4.0, (0.25, 32))
    _par(c, A, 'Float', 'Slidex', 'Slide x px', 0.0, (-400, 400))
    _par(c, A, 'Float', 'Slidey', 'Slide y px', -80.0, (-400, 400))
    _par(c, A, 'Float', 'Scalefrom', 'Scale from', 0.6, (0, 2))
    _par(c, A, 'Float', 'Blurmax', 'Blur max px', 24.0, (0, 80))
    _par(c, A, 'Float', 'Pulseamt', 'Pulse amount', 0.25, (0, 1))
    _par(c, A, 'Float', 'Audiolevel', 'Audio level', 0.0, (0, 1))
    _par(c, A, 'Float', 'Audiogain', 'Audio gain', 1.0, (0, 8))
    _par(c, A, 'Float', 'Audiosmooth', 'Audio smooth', 0.6, (0, 0.99))
    _par(c, A, 'Pulse', 'Trigger', 'Trigger')
    _par(c, A, 'Toggle', 'Hold', 'Hold', False)
    _par(c, A, 'Toggle', 'Loop', 'Loop', False)
    _par(c, A, 'Toggle', 'Autotrigger', 'Trigger on new text', True)

    _par(c, Y, 'Int', 'Outw', 'Out width', 1080, (64, 3840))
    _par(c, Y, 'Int', 'Outh', 'Out height', 1920, (64, 3840))
    _par(c, Y, 'Float', 'Lineh', 'Line box em', 2.5, (0.8, 4))
    _par(c, Y, 'Float', 'Marginem', 'Raster margin em', 0.6, (0.1, 2))
    _par(c, Y, 'Toggle', 'Showboxes', 'Show ink boxes', False)
    _par(c, Y, 'Float', 'Wipesoft', 'Wipe edge px', 24.0, (0, 200))
    _par(c, Y, 'Int', 'Blurtaps', 'Blur taps', 16, (4, 48))
    _par(c, Y, 'Pulse', 'Rebuild', 'Re-render')

    _par(c, F, 'Folder', 'Cachedir', 'Render cache (empty = <repo>/output/urdu_type/cache)')
    _par(c, F, 'File', 'Python', 'Python 3 for the renderer', PY)
    _par(c, F, 'Float', 'Timeout', 'Render timeout s', 20.0, (1, 120))

    _par(c, K, 'Toggle', 'Showinfo', 'Show info on preview', False)

    _par(c, I, 'Str', 'Status', 'Status', '', ro=True)
    _par(c, I, 'Int', 'Nwords', 'Words', 0, ro=True)
    _par(c, I, 'Int', 'Nlines', 'Lines', 0, ro=True)
    _par(c, I, 'Int', 'Atlasslot', 'Atlas slot (0 A, 1 B)', 0, ro=True)
    _par(c, I, 'Int', 'Atlasw', 'Atlas width', 0, ro=True)
    _par(c, I, 'Int', 'Atlash', 'Atlas height', 0, ro=True)
    _par(c, I, 'Float', 'Parsems', 'Parse ms (TD)', 0.0, ro=True)
    _par(c, I, 'Float', 'Renderms', 'Render ms (child process)', 0.0, ro=True)
    _par(c, I, 'Float', 'Layoutms', 'Layout ms (TD)', 0.0, ro=True)


def _glsl(c, name, code, w_expr, h_expr, fmt, uniforms, tops):
    g = _mk(c, glslTOP, name)
    g.par.mode = 'compute'
    cd = _mk(c, textDAT, name + '_compute')
    if cd.text != code:
        cd.text = code
    g.par.computedat = cd.name
    g.par.outputresolution = 'custom'
    g.par.resolutionw.expr = w_expr
    g.par.resolutionh.expr = h_expr
    g.par.format = fmt
    g.par.autodispatchsize = True
    g.par.tops = ' '.join(tops)
    g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), len(uniforms))
    for k, (uname, exprs) in enumerate(uniforms):
        getattr(g.par, 'vec{}name'.format(k)).val = uname
        for ax, e in zip('xyzw', exprs):
            getattr(g.par, 'vec{}value{}'.format(k, ax)).expr = e
    return g


PY = '/Library/Frameworks/Python.framework/Versions/3.13/bin/python3'

FONTS = ['Noto Nastaliq Urdu', 'Noto Nastaliq Urdu UI', 'Geeza Pro', 'Al Nile', 'Baghdad', 'Damascus', 'Farah',
         'Helvetica Neue', 'Helvetica', 'Avenir Next', 'Arial', 'Menlo']


def _blank_png(path):
    """8x8 fully transparent RGBA PNG (the atlas slots' start file; written with zlib, no TOP involved)."""
    import struct, zlib
    if os.path.isfile(path):
        return path

    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    raw = b''.join(b'\x00' + b'\x00' * 32 for _ in range(8))
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 6, 0, 0, 0)) + \
        chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    with open(path, 'wb') as f:
        f.write(data)
    return path


def _prepare_controls(c):
    """Pre-create the zkit panel + its zk_measure Text TOP (Open Sans, ASCII labels only) with zkit's own settings, so
    build_controls (a LATER td_exec, >= 2 frames on) finds it existing and cooked: zkit's Rebuild() calls
    evalTextSize on zk_measure, which must never happen in the script that creates it (T-76)."""
    panel = c.op('controls')
    if panel is None:
        panel = c.create(containerCOMP, 'controls')
    m = panel.op('zk_measure')
    if m is None:
        m = panel.create(textTOP, 'zk_measure')
        m.par.text = ''
        m.par.font = 'Open Sans'
        m.par.bold = False
        m.par.fontsizexunit = 'pixels'
        m.par.fontsizex = 20
        m.par.alignx = 'left'
        m.par.aligny = 'bottom'
        m.par.positionunit = 'pixels'
        m.par.outputresolution = 'custom'
        m.par.resolutionw, m.par.resolutionh = 8, 8
        m.par.bgalpha = 0
        m.par.format = 'rgba8fixed'
    m.viewer = True
    return m.path


def build(parent_path='/project1/lab', name=NAME, pool=POOL, controls=True, upto=4):
    pc = op(parent_path)
    c = pc.op(name) or pc.create(baseCOMP, name)
    c.allowCooking = True
    _close_window(c)
    for o in list(c.children):                   # never a Text TOP word pool again (T-76)
        if o.OPType == 'textTOP' and (o.name.startswith(('w', 'probe_')) or o.name == 'meter'):
            _sd(o)
    c.store('jz_pool', int(pool))
    c.store('jz_render_version', RENDER_VERSION)
    for dat, fn in (('urdu_type_logic', 'urdu_type_logic.py'), ('urdu_render', 'urdu_render.py'),
                    ('urdu_rt', 'urdu_type_rt.py')):
        d = _mk(c, textDAT, dat)
        t = open(REPO + '/builders/' + fn).read()
        if d.text != t:
            d.text = t
    L = c.op('urdu_type_logic').module
    _pars(c, L, FONTS)
    c.comment = ('urdu_type: Urdu / Arabic / mixed lines shaped by HarfBuzz OUTSIDE TD into one atlas PNG; own bidi + '
                 'layout + word animation; no Text TOP with an Urdu font, no TOP readback')
    cache = REPO + '/output/urdu_type/cache'
    os.makedirs(cache, exist_ok=True)
    c.store('jz_cache', cache)                   # runtime default cache (a scratch project's folder differs)
    blank = _blank_png(cache + '/blank8.png')
    for nm in ('atlas_a', 'atlas_b'):
        m = _mk(c, moviefileinTOP, nm)
        if not m.par.file.eval() or 'Banana' in m.par.file.eval():
            m.par.file = blank
        m.par.playmode = 'specify'
        m.par.index = 0
        m.par.premultrgbbyalpha = 'off'
    words = _mk(c, tableDAT, 'words')
    lay = _mk(c, tableDAT, 'layout')
    for cb, txt in (('anim_cb', ANIM_CB), ('rest_cb', REST_CB)):
        d = _mk(c, textDAT, cb)
        if d.text != txt:
            d.text = txt

    # 3 Layout outputs
    rest = _mk(c, scriptCHOP, 'rest')
    rest.par.callbacks = 'rest_cb'
    ow = _mk(c, outDAT, 'out_words')
    _wire(lay, ow)
    orr = _mk(c, outCHOP, 'out_rest')
    _wire(rest, orr)

    # 4 Animate
    _mk(c, inCHOP, 'in2')
    an = _mk(c, scriptCHOP, 'anim')
    an.par.callbacks = 'anim_cb'
    pt = _mk(c, choptoTOP, 'params')
    pt.par.chop = an.name
    pt.par.format = 'r32float' if 'r32float' in pt.par.format.menuNames else 'rgba32float'
    if hasattr(pt.par, 'dataformat') and 'r' in pt.par.dataformat.menuNames:
        pt.par.dataformat = 'r'
    rt = c.op('urdu_rt')
    if upto <= 1:
        rt.module.schedule('rebuild')
        return {'comp': c.path, 'ops': len(c.children), 'step': 1, 'rebuild': 'scheduled'}

    # 5 Place
    nf = len(L.FIELDS)
    _glsl(c, 'place', place_glsl(pool, nf), 'parent().par.Outw', 'parent().par.Outh', 'rgba8fixed',
          [('uA', ('min(parent().par.Nwords.eval(), {})'.format(pool), '0.12 * parent().par.Size',
                   'parent().par.Wipesoft', 'parent().par.Blurtaps')),
           ('uB', ('1 if parent().par.Showboxes else 0', '2', 'parent().par.Atlasslot',
                   'parent().par.Outlinepx if parent().par.Outlinepx > 0.25 else 0'))],
          ['params', 'atlas_a', 'atlas_b'])
    if upto <= 2:
        rt.module.schedule('rebuild')
        return {'comp': c.path, 'ops': len(c.children), 'step': 2, 'rebuild': 'scheduled'}

    # 6 Style + output
    pl = c.op('place')
    _mk(c, inTOP, 'in1')
    gs = _mk(c, resolutionTOP, 'glow_src')
    _wire(pl, gs)
    gb = _mk(c, blurTOP, 'glow_blur')
    _wire(gs, gb)
    gb.par.size.expr = 'max(1, parent().par.Glowsize / 2)'
    sb = _mk(c, blurTOP, 'shadow_blur')
    _wire(gs, sb)
    sb.par.size.expr = 'max(1, parent().par.Shadowsize / 2)'
    used = '(parent().par.Glow > 0 or parent().par.Shadow > 0)'
    gs.par.outputresolution = 'custom'          # unused glow / shadow: 8x8 blurs, ~0 ms (60 fps budget)
    gs.par.resolutionw.expr = 'max(8, parent().par.Outw // 2) if {} else 8'.format(used)
    gs.par.resolutionh.expr = 'max(8, parent().par.Outh // 2) if {} else 8'.format(used)
    P = 'parent().par.'
    cp = _glsl(c, 'compose', COMPOSE_GLSL, P + 'Outw', P + 'Outh', 'rgba8fixed',
               [('uFill', (P + 'Fillr', P + 'Fillg', P + 'Fillb', P + 'Fillalpha')),
                ('uLine', (P + 'Outliner', P + 'Outlineg', P + 'Outlineb', P + 'Outlinepx')),
                ('uGlow', (P + 'Glowcolorr', P + 'Glowcolorg', P + 'Glowcolorb', P + 'Glow')),
                ('uShad', (P + 'Shadowoffx', P + 'Shadowoffy', P + 'Shadow', '1 if parent().par.Premult else 0')),
                ('uBg', (P + 'Bgcolorr', P + 'Bgcolorg', P + 'Bgcolorb', P + 'Bgalpha')),
                ('uMode', ('{}.menu_index({}.BACKGROUND, parent().par.Background.eval())'.format(LOGIC, LOGIC),
                           P + 'Outlinealpha', '0', '0'))],
               ['place', 'glow_blur', 'shadow_blur', 'in1'])
    res = _mk(c, nullTOP, 'result')
    _wire(cp, res)
    out = _mk(c, outTOP, 'out1')
    _wire(res, out)
    iv = _mk(c, textTOP, 'info_view')            # ASCII status only, Latin font (never Urdu text, T-76)
    iv.par.text.expr = "op('urdu_rt').module.info_text() if parent().par.Showinfo else ''"
    iv.par.outputresolution = 'custom'
    iv.par.resolutionw.expr = P + 'Outw'
    iv.par.resolutionh.expr = P + 'Outh'
    iv.par.fontsizexunit = 'pixels'
    iv.par.fontsizex = 28
    iv.par.alignx = 'left'
    iv.par.aligny = 'top'
    iv.par.bgalpha = 0
    iv.par.font = 'Open Sans'                   # Helvetica Neue .ttc: 'Unsupported character map' on 31550
    pv = _mk(c, overTOP, 'preview')
    _wire(iv, pv, 0)
    _wire(res, pv, 1)

    # parameter + DAT + frame watchers
    pe = _mk(c, parameterexecuteDAT, 'par_exec')
    if pe.text != PAR_EXEC:
        pe.text = PAR_EXEC
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = '*'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = True
    pe.par.onpulse = True
    pe.par.active = True
    de = _mk(c, datexecuteDAT, 'textdat_exec')
    if de.text != DAT_EXEC:
        de.text = DAT_EXEC
    de.par.dat.expr = "parent().par.Textdat.eval().path if parent().par.Textdat.eval() is not None else ''"
    de.par.tablechange = True
    de.par.active = True
    tk = _mk(c, executeDAT, 'tick')
    if tk.text != TICK:
        tk.text = TICK
    tk.par.framestart = True
    tk.par.active = True

    rt.module.schedule('rebuild')               # rendered by the child process, applied frames later

    if controls and upto == 3:
        _prepare_controls(c)                    # zk_measure exists + cooks before zkit's first evalTextSize
    ui = 'skipped'
    if controls and upto >= 4:
        ns = dict(globals())
        exec(open(REPO + '/builders/zkit.py').read(), ns)
        ui = ns['build_controls'](c.path, pages=['Text', 'Anim', 'Style'],
                                  exclude=('Text', 'Textdat', 'Fontfilertl', 'Fontfileltr'), d=56, cols=8)

    c.par.opviewer.expr = "me.op('preview') if me.par.Showinfo else me.op('out1')"
    c.viewer = True
    for o in c.children:
        if o.family in ('TOP', 'CHOP'):
            o.viewer = True
    try:
        st = [dict(s, ops=[n for n in s['ops'] if c.op(n) is not None]) for s in STAGES]   # upto < 4: no window
        lay_r = op('/jazib_mcp/handlers').module.layout_stages(c, [s for s in st if s['ops']], True, arrange='mixed')
    except Exception as e:
        lay_r = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'ui': str(ui)[:300], 'layout': str(lay_r)[:400]}
