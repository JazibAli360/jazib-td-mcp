# fx_trans_logic - pure logic of FX_trans (G-TRANS transition bank, FX0 row 69). No TD needed: the builder, the
# runtime (Text DAT `fx_trans_logic` in the COMP, same text) and the offline tests all use this file.
#   * the bank: 25 gl-transitions (builders/glsl/fx_trans/*.glsl, vendored unchanged, MIT, SOURCES.md) + 3 of ours
#     (matte = luma-matte wipe from any TOP, tvoff = CRT power-off -> power-on (fx_analog_crt_logic.power_shape),
#     mosh = FX_glitch moshcut's engine in a sub-COMP);
#   * the wrapper that turns gl-transition source into ONE compute shader (T-47) for the selected type (or the whole
#     bank): identifiers prefixed per transition, uniforms -> globals filled from the 10 generic knobs K1..K10;
#   * progress: drive (manual / seconds / beats), Go / Back / Cut, quantize to the beat, easing, swap for "back";
#   * numpy references (fade, fadecolor, directional wipe, circle open, matte, tvoff) used by the tests + LIVE CHECKS.
# ASCII only.
import math
import os
import random
import re

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else \
    '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
GL_DIR = os.path.join(HERE, 'glsl', 'fx_trans')
NKNOBS = 10                      # K1..K10 -> uniforms uK0 uK1 uK2 (12 floats, 10 used)

# (id, file stem) in menu order; ids are the Type menu names
GL = [('fade', 'Fade'), ('fadecolor', 'FadeColor'), ('wipe', 'DirectionalWipe'), ('circleopen', 'CircleOpen'),
      ('clock', 'ClockWipe'), ('crosswarp', 'CrossWarp'), ('crosszoom', 'CrossZoom'), ('cube', 'Cube'),
      ('swirl', 'Swirl'), ('pixelize', 'Pixelize'), ('morph', 'Morph'), ('glitchmem', 'GlitchMemories'),
      ('burn', 'BurnThrough'), ('filmburn', 'FilmBurn'), ('ripple', 'Ripple'), ('dreamy', 'Dreamy'),
      ('doorway', 'Doorway'), ('kaleido', 'Kaleidoscope'), ('doommelt', 'DoomMelt'), ('slices', 'WindowSlices'),
      ('polka', 'PolkaDotsCurtain'), ('hexagon', 'Hexagonalize'), ('displace', 'DisplacementMap'),
      ('glitchdisplace', 'GlitchDisplace'), ('stripmosh', 'StripDatamoshGlitch')]
# our own: params (name, type, default, min, max) - same shape as parsed gl params
OWN = {
    'matte': {'label': 'Matte wipe (luma of any TOP)', 'params': [
        ('softness', 'float', [0.1], 0.0, 1.0), ('invert', 'bool', [0.0], 0.0, 1.0),
        ('channel', 'int', [0.0], 0.0, 4.0), ('gamma', 'float', [1.0], 0.1, 4.0)]},
    'tvoff': {'label': 'TV off -> on (CRT power)', 'params': [
        ('gap', 'float', [0.1], 0.0, 0.8), ('dotsize', 'float', [0.012], 0.002, 0.05),
        ('glow', 'float', [4.0], 1.0, 8.0), ('line', 'float', [0.004], 0.001, 0.05)]},
    'beatripple': {'label': 'Beat ripple pool (TC-33): drops on the beats of the run, B inside the rings', 'params': [
        ('drops', 'int', [4.0], 1.0, 16.0), ('amp', 'float', [0.02], 0.0, 0.2), ('waves', 'float', [12.0], 0.0, 60.0),
        ('width', 'float', [0.08], 0.005, 0.5), ('soft', 'float', [0.03], 0.0, 0.3), ('seed', 'int', [1.0], 0.0, 999.0),
        ('damp', 'float', [1.0], 0.0, 8.0), ('grow', 'float', [2.0], 0.5, 4.0)]},
    'jigsaw': {'label': 'Jigsaw (7C-29): interlocking pieces flip over one by one from A to B', 'params': [
        ('cols', 'int', [6.0], 1.0, 24.0), ('rows', 'int', [10.0], 1.0, 40.0), ('knob', 'float', [0.18], 0.0, 0.3),
        ('random', 'float', [0.6], 0.0, 1.0), ('spread', 'float', [0.7], 0.0, 0.95), ('seed', 'int', [1.0], 0.0, 999.0),
        ('shade', 'float', [0.6], 0.0, 1.0), ('border', 'float', [0.0], 0.0, 0.1), ('gap', 'float', [0.0], 0.0, 1.0)]},
    'mosh': {'label': 'Datamosh cut (FX_glitch moshcut engine)', 'params': [
        ('melt', 'float', [0.35], 0.0, 1.0), ('order', 'int', [0.0], 0.0, 4.0), ('cutmode', 'int', [0.0], 0.0, 2.0),
        ('gain', 'float', [1.0], 0.0, 4.0), ('residual', 'float', [0.4], 0.0, 1.5), ('decay', 'float', [0.0], 0.0, 0.2),
        ('bloomgain', 'float', [2.0], 0.0, 8.0), ('seed', 'int', [1.0], 1.0, 100.0)]},
}
MOSH_ORDERS = ['noise', 'topdown', 'bottomup', 'radial', 'luma']       # fx_glitch_moshcut.ORDERS
MOSH_CMODES = ['hard', 'soft', 'bloom']                                # fx_glitch_moshcut.CMODES
# menu order: the gl list with matte after wipe, tvoff + mosh at the end
# wave 2 (lane C, 27 Oct; FX7a SX-31 melt / burn / dissolve + SX-34 blur / warp / motion): appended AFTER the own types
GL_MORE = [('lummelt', 'LuminanceMelt'), ('burnout', 'UndulatingBurnOut'), ('glowdissolve', 'GlowDissolve'),
           ('perlindissolve', 'PerlinDissolve'), ('noisedissolve', 'NoiseDissolve'), ('overexposure', 'Overexposure'),
           ('edgeglow', 'EdgeGlow'), ('linearblur', 'LinearBlur'), ('dirwarp', 'DirectionalWarp'),
           ('tanblur', 'TangentMotionBlur'), ('squeeze', 'Squeeze'), ('flyeye', 'FlyEye'), ('shatter', 'Shatter'),
           ('crazyfun', 'CrazyParametricFun')]
# wave 3 (lane C2, 27 Oct; FX7a SX-32 signal failure (2 of 7: static + colour phase; GlitchBands overlaps stripmosh),
# SX-33 page / flip / 3D (+ FX7c 7C-06 page flip), SX-35 shape wipes): appended after wave 2, then our jigsaw (7C-29)
GL_W3 = [('tvstatic', 'TvStatic'), ('colorphase', 'ColorPhase'), ('bookflip', 'BookFlip'),
         ('pagecurl', 'InvertedPageCurl'), ('rolls', 'Rolls'), ('heart', 'HeartWipe'), ('pinwheel', 'Pinwheel'),
         ('lissajous', 'LissajousTiles'), ('gridflip', 'GridFlip')]
GL_ALL = GL + GL_MORE + GL_W3
TYPES = [g[0] for g in GL[:3]] + ['matte'] + [g[0] for g in GL[3:]] + ['tvoff', 'mosh', 'beatripple'] + \
    [g[0] for g in GL_MORE] + [g[0] for g in GL_W3] + ['jigsaw']
# (new types go at the END: zkit presets store the Type menu index, so earlier indices never move)
OWN_SHADER = ('matte', 'tvoff', 'beatripple', 'jigsaw')                # ours, written here (no gl wrapper)
SHADER_TYPES = [t for t in TYPES if t != 'mosh']                        # mosh runs in its own sub-COMP
EASES = ['linear', 'smooth', 'in', 'out', 'inout', 'expo', 'sine']
DRIVES = ['manual', 'seconds', 'beats']
QUANT = ['off', 'beat', 'bar']
BACKSTYLES = ['rewind', 'forward']
OUTSIDE = ['hold', 'transparent']

TYPE_RE = r'(?:float|int|bool|vec[234]|ivec[234]|bvec[234]|mat[234]|sampler2D)'
NDIM = {'float': 1, 'int': 1, 'bool': 1, 'vec2': 2, 'vec3': 3, 'vec4': 4, 'ivec2': 2, 'ivec3': 3, 'ivec4': 4}


# ------------------------------------------------------------------------------------------------ parsing
def _num_list(s, n):
    s = s.strip().rstrip(';').strip()
    if s in ('true', 'false'):
        return [1.0 if s == 'true' else 0.0]
    m = re.match(r'^[ib]?vec[234]\s*\((.*)\)$', s)
    vals = [float(x) for x in (m.group(1) if m else s).split(',') if x.strip()]
    if len(vals) == 1 and n > 1:
        vals = vals * n
    return vals


def parse_gl(text):
    """gl-transition source -> {'author', 'license', 'description', 'params': [(name, type, default list, min, max)],
    'samplers': [name]}. Defaults from '// = x' or '/* = x */'; ranges from a preceding '// @range(a, b)'."""
    info = {'author': '', 'license': 'MIT', 'description': '', 'params': [], 'samplers': []}
    rng = None
    for line in text.split('\n'):
        s = line.strip()
        for key in ('Author', 'License', 'Description'):
            m = re.match(r'^//\s*%s\s*:\s*(.*)$' % key, s)
            if m:
                info[key.lower()] = m.group(1).strip()
        m = re.match(r'^//\s*@range\(\s*([-0-9.e]+)\s*,\s*([-0-9.e]+)\s*\)', s)
        if m:
            rng = (float(m.group(1)), float(m.group(2)))
            continue
        m = re.match(r'^uniform\s+(\w+)\s+(\w+)\s*(?:/\*\s*=\s*(.*?)\s*\*/)?\s*;\s*(?://\s*=\s*([^;]*))?', s)
        if not m:
            if s and not s.startswith('//'):
                rng = None
            continue
        ty, name = m.group(1), m.group(2)
        if ty == 'sampler2D':
            info['samplers'].append(name)
            rng = None
            continue
        d = m.group(3) or m.group(4)
        n = NDIM[ty]
        dv = _num_list(d, n) if d else [0.0] * n
        if rng:
            lo, hi = rng
        else:
            a = max(abs(v) for v in dv) if dv else 1.0
            lo, hi = (0.0, 1.0) if ty == 'bool' else (min(0.0, min(dv)), max(1.0, 2.0 * a))
        info['params'].append((name, ty, dv, lo, hi))
        rng = None
    return info


SRC = {}                         # stem -> source; filled in TD from the fx_trans_src DAT (no repo needed at runtime)


def load_sources(json_text):
    """TD runtime: the vendored sources from the COMP's fx_trans_src Text DAT (JSON). Idempotent."""
    import json
    if json_text and not SRC:
        SRC.update(json.loads(json_text))
    return len(SRC)


def gl_text(stem):
    if stem in SRC:
        return SRC[stem]
    with open(os.path.join(GL_DIR, stem + '.glsl')) as fh:
        return fh.read()


_BANK = {}


def bank():
    """{type id: {'label', 'stem', 'params', 'author', 'license', 'description', 'samplers'}} (cached)."""
    if _BANK:
        return _BANK
    for tid, stem in GL_ALL:
        info = parse_gl(gl_text(stem))
        info['stem'] = stem
        info['label'] = stem
        _BANK[tid] = info
    for tid, o in OWN.items():
        _BANK[tid] = {'label': o['label'], 'stem': None, 'params': o['params'], 'author': 'jazib-td-mcp',
                      'license': 'own', 'description': o['label'], 'samplers': []}
    return _BANK


def knob_slots(params):
    """[(param name, type, [knob index per component])]; knob index 0..NKNOBS-1. Raises when a type needs more."""
    out, k = [], 0
    for name, ty, _d, _lo, _hi in params:
        n = NDIM[ty]
        out.append((name, ty, list(range(k, k + n))))
        k += n
    if k > NKNOBS:
        raise ValueError('%d knob floats > %d' % (k, NKNOBS))
    return out


def knob_table(tid):
    """[(knob label, default, min, max)] for K1..K(n) of a type (labels name the param + component)."""
    rows = []
    for name, ty, dv, lo, hi in bank()[tid]['params']:
        n = NDIM[ty]
        comps = 'xyzw' if n <= 2 or ty.startswith('ivec') or ty == 'vec2' else ('rgb' if n == 3 else 'rgba')
        for c in range(n):
            lab = name if n == 1 else '%s %s' % (name, comps[c])
            rows.append((lab, dv[c] if c < len(dv) else 0.0, lo, hi))
    return rows


def kref(k):
    return 'uK%d.%s' % (k // 4, 'xyzw'[k % 4])


def _ctor(ty, ks):
    f = [kref(k) for k in ks]
    if ty == 'float':
        return f[0]
    if ty == 'int':
        return 'int(round(%s))' % f[0]
    if ty == 'bool':
        return '(%s > 0.5)' % f[0]
    if ty.startswith('ivec'):
        return '%s(%s)' % (ty, ', '.join('int(round(%s))' % x for x in f))
    return '%s(%s)' % (ty, ', '.join(f))


# ------------------------------------------------------------------------------------------------ wrapping
def _top_names(text):
    """Names declared at brace depth 0 (functions, consts, globals, structs) + every #define name + uniforms."""
    names, depth = set(), 0
    for line in text.split('\n'):
        code = line.split('//')[0]
        m = re.match(r'^\s*#\s*define\s+(\w+)', code)
        if m:
            names.add(m.group(1))
            continue
        if depth == 0:
            m = re.match(r'^\s*uniform\s+\w+\s+(\w+)', code)
            if m:
                names.add(m.group(1))
            else:
                m = re.match(r'^\s*struct\s+(\w+)', code)
                if m:
                    names.add(m.group(1))
                m = re.match(r'^\s*(?:const\s+)?(?:highp\s+|mediump\s+|lowp\s+)?(\w+)\s+(\w+)\s*(\(|=|;|\[|,)', code)
                if m and m.group(1) not in ('return', 'else', 'precision', 'uniform'):
                    names.add(m.group(2))
                    if m.group(3) == ',':                       # float a, b, c;
                        for extra in re.findall(r',\s*(\w+)', code):
                            names.add(extra)
        depth += code.count('{') - code.count('}')
    return names - {'main', 'progress', 'ratio', 'getFromColor', 'getToColor'}


def _strip_comments(text):
    text = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'), text, flags=re.S)
    return '\n'.join(l.split('//')[0].rstrip() for l in text.split('\n'))


def wrap_gl(tid, text, params, samplers=(), matte_sampler='sMatte'):
    """One gl-transition -> a prefixed block: t<tid>_init() (knobs -> globals) + t<tid>_transition(uv)."""
    pre = 't%s_' % tid
    body = _strip_comments(text)
    names = _top_names(body)
    defs = re.findall(r'^\s*#\s*define\s+(\w+)', body, flags=re.M)
    body = re.sub(r'^\s*uniform\s+[^;]*;\s*$', '', body, flags=re.M)         # uniforms -> globals below
    if names:
        body = re.sub(r'(?<![\w.])(%s)\b' % '|'.join(sorted(names, key=len, reverse=True)),
                      lambda m: pre + m.group(1), body)
    body = re.sub(r'\btexture2D\b', 'texture', body)
    slots = knob_slots(params)
    glob = ['%s %s%s;' % (ty, pre, name) for name, ty, _ks in slots]
    for s in samplers:
        glob.append('#define %s%s %s' % (pre, s, matte_sampler))
    init = ['void %sinit() {' % pre] + ['    %s%s = %s;' % (pre, name, _ctor(ty, ks)) for name, ty, ks in slots] + ['}']
    undef = ['#undef %s%s' % (pre, d) for d in defs] + ['#undef %s%s' % (pre, s) for s in samplers]
    head = '// ---- %s (%s, %s; vendored builders/glsl/fx_trans) ----' % (tid, bank()[tid]['stem'],
                                                                          bank()[tid]['license'])
    for old, new in PATCHES.get(tid, ()):
        body = body.replace(old, new)
    return '\n'.join([head] + glob + init + [body.strip('\n')] + undef) + '\n'


# Perf patches on the WRAPPED (prefixed) text; the vendored files stay unchanged. Tests check every `old` is found.
# filmburn (live b5, 26 Oct, LEARNINGS): the 13 light-leak positions (smooth_random of progress: the same for every
# pixel) and the 50 blur tap offsets are computed once per 8x8 workgroup into shared memory; the blur tap radius is per
# tap (rand(vec2(i, 0.5))) instead of per pixel (rand(vec2(i, p.x + p.y)): 100 scattered taps); A or B alone is
# fetched while the blend weight is < 0.001 / > 0.999. Same maths otherwise.
_FB_OLD = """vec4 tfilmburn_transition(vec2 p) {
  vec3 f = vec3(0.);
  for (float i = 0.; i < 13.; i++) {
    f += sin(((p.x*tfilmburn_rand(i)*6.)+(progress*8.))+tfilmburn_rand(i+1.43))*sin(((p.y*tfilmburn_rand(i+4.4)*6.)+(progress*6.))+tfilmburn_rand(i+2.4));
    f += 1.-tfilmburn_clamps(length(p-vec2(tfilmburn_smooth_random(vec2(progress*1.3),i+1.),tfilmburn_smooth_random(vec2(progress*.5),i+6.25)))*mix(20.,70.,tfilmburn_rand(i)));
  }"""
_FB_NEW = """shared vec4 tfilmburn_sL[13];
shared vec4 tfilmburn_sW[13];
shared vec2 tfilmburn_sQ[50];
shared float tfilmburn_sZ;
vec4 tfilmburn_transition(vec2 p) {
  // FX_trans perf patch: per-frame values once per workgroup (shared memory), tap radius per tap.
  uint li = gl_LocalInvocationIndex;
  float ba = sin(progress*tfilmburn_pi)*.03;
  if (li < 13u) {
    float i = float(li);
    tfilmburn_sL[li] = vec4(tfilmburn_smooth_random(vec2(progress*1.3),i+1.), tfilmburn_smooth_random(vec2(progress*.5),i+6.25), mix(20.,70.,tfilmburn_rand(i)), 0.);
    tfilmburn_sW[li] = vec4(tfilmburn_rand(i), tfilmburn_rand(i+1.43), tfilmburn_rand(i+4.4), tfilmburn_rand(i+2.4));
  }
  if (li == 13u) tfilmburn_sZ = tfilmburn_smooth_random(vec2(progress*5.),6.3);
  if (li < 50u) {
    float i = float(li);
    tfilmburn_sQ[li] = vec2(cos(degrees((i/50.)*360.)),sin(degrees((i/50.)*360.))) * (tfilmburn_rand(vec2(i,0.5))+ba) * ba;
  }
  memoryBarrierShared();
  barrier();
  vec3 f = vec3(0.);
  for (int k = 0; k < 13; k++) {
    vec4 w = tfilmburn_sW[k];
    vec4 l = tfilmburn_sL[k];
    f += sin(((p.x*w.x*6.)+(progress*8.))+w.y)*sin(((p.y*w.z*6.)+(progress*6.))+w.w);
    f += 1.-tfilmburn_clamps(length(p-l.xy)*l.z);
  }"""
_FB_OLD2 = """  p *= 1.+(tfilmburn_smooth_random(vec2(progress*5.),6.3)*sin(progress*tfilmburn_pi)*.05);
  p += .5;

  vec4 blurred_image = vec4(0.);
  float bluramount = sin(progress*tfilmburn_pi)*.03;
  #define tfilmburn_repeats  50.
  for (float i = 0.; i < tfilmburn_repeats; i++) {
      vec2 q = vec2(cos(degrees((i/tfilmburn_repeats)*360.)),sin(degrees((i/tfilmburn_repeats)*360.))) *  (tfilmburn_rand(vec2(i,p.x+p.y))+bluramount);
      vec2 uv2 = p+(q*bluramount);
      blurred_image += tfilmburn_blendedColor(uv2);
  }
  blurred_image /= tfilmburn_repeats;"""
_FB_NEW2 = """  p *= 1.+(tfilmburn_sZ*sin(progress*tfilmburn_pi)*.05);
  p += .5;

  vec4 blurred_image = vec4(0.);
  float bw = tfilmburn_sigmoid(progress,10.);
  #define tfilmburn_repeats  50.
  for (int k = 0; k < 50; k++) {
      vec2 uv2 = p+tfilmburn_sQ[k];
      blurred_image += bw < 0.001 ? getFromColor(uv2) : (bw > 0.999 ? getToColor(uv2) : mix(getFromColor(uv2), getToColor(uv2), bw));
  }
  blurred_image /= tfilmburn_repeats;"""
PATCHES = {'filmburn': [(_FB_OLD, _FB_NEW), (_FB_OLD2, _FB_NEW2)]}


PRELUDE = """// FX_trans (G-TRANS) compute shader, generated by builders/fx_trans_logic.py shader_text(). T-47 compute.
// in0 = A (from), in1 = B (to), in2 = matte (luma wipe / displacement map). gl-transitions API: progress, ratio,
// getFromColor / getToColor (straight alpha, uv 0..1 bottom-left). Knobs K1..K10 = uK0..uK2.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uT;    // progress (eased), type index, swap (1 = from B to A), outside (0 hold, 1 transparent)
uniform vec4 uK0;
uniform vec4 uK1;
uniform vec4 uK2;
#define sMatte sTD2DInputs[2]
float progress;
float ratio;
vec4 fxtStraight(vec4 c) { return c.a > 1e-5 ? vec4(c.rgb / c.a, c.a) : vec4(0.0); }
vec4 fxtTap(int i, vec2 uv) {
    if (uT.w > 0.5 && (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0)) return vec4(0.0);
    return fxtStraight(i == 0 ? texture(sTD2DInputs[0], uv) : texture(sTD2DInputs[1], uv));
}
vec4 getFromColor(vec2 uv) { return fxtTap(uT.z > 0.5 ? 1 : 0, uv); }
vec4 getToColor(vec2 uv) { return fxtTap(uT.z > 0.5 ? 0 : 1, uv); }
float fxtLuma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
"""

MATTE = """// ---- matte (ours): luma-matte wipe from any TOP (in2). A pixel turns to B when progress passes its matte value.
// K: softness, invert, channel (0 luma 1 r 2 g 3 b 4 a), gamma.
vec4 tmatte_transition(vec2 uv) {
    vec4 mm = texture(sMatte, uv);
    int ch = int(round(uK0.z));
    float v = ch == 1 ? mm.r : (ch == 2 ? mm.g : (ch == 3 ? mm.b : (ch == 4 ? mm.a : fxtLuma(mm.rgb))));
    v = pow(clamp(v, 0.0, 1.0), max(uK0.w, 1e-3));
    if (uK0.y > 0.5) v = 1.0 - v;
    float s = max(uK0.x, 0.0);
    float e = progress * (1.0 + s);                 // edge sweeps 0 -> 1 + s so progress 1 = all B
    float m = s > 0.0 ? smoothstep(v, v + s, e) : step(v, e);
    if (progress <= 0.0) m = 0.0;
    return mix(getFromColor(uv), getToColor(uv), m);
}
"""

TVOFF = """// ---- tvoff (ours): CRT power-off of A, a black gap, then power-on of B. Maths = fx_analog_crt_logic.power_shape
// (FX_analog crtfault AV-07), ported: off 0-35 %% squeeze to a bright line, 35-55 %% line to a dot, 55-100 %% dot fades;
// on: dim and small (60 %% / 75 %%) growing to full. K: gap (fraction of the run that is black), dot size (heights),
// glow (gain cap on the line), line (collapsed line height).
vec4 tvPower(bool on, float s) {          // -> sy, sx, gain, dot  (s = since / dur)
    float LH = max(uK0.w, 1e-4);
    if (on) {
        if (s >= 1.0) return vec4(1.0, 1.0, 1.0, 0.0);
        float e = s * s * (3.0 - 2.0 * s);
        return vec4(0.6 + 0.4 * e, 0.75 + 0.25 * e, e, 0.0);
    }
    if (s < 0.35) {
        float e = s / 0.35;
        float sy = 1.0 - (1.0 - LH) * (e * e);
        return vec4(sy, 1.0, min(1.0 / sqrt(sy), uK0.z), 0.0);
    }
    if (s < 0.55) {
        float e = (s - 0.35) / 0.2;
        return vec4(LH, 1.0 - (1.0 - LH) * e, uK0.z, 0.0);
    }
    if (s < 1.0) return vec4(0.0, 0.0, 0.0, exp(-6.0 * (s - 0.55) / 0.45));
    return vec4(0.0);
}
vec4 ttvoff_transition(vec2 uv) {
    float g = clamp(uK0.x, 0.0, 0.95);
    float h = 0.5 * (1.0 - g);                      // off over [0, h), black gap [h, 1 - h), on over [1 - h, 1]
    bool on = progress >= 1.0 - h;
    float s = on ? (progress - (1.0 - h)) / max(h, 1e-4) : progress / max(h, 1e-4);
    vec4 pw = (!on && progress >= h) ? vec4(0.0) : tvPower(on, s);
    vec2 c = uv - 0.5;
    bool inside = abs(c.x) <= 0.5 * pw.y && abs(c.y) <= 0.5 * pw.x && pw.x > 0.0 && pw.y > 0.0;
    vec4 col = vec4(0.0, 0.0, 0.0, 1.0);
    if (inside) {
        vec2 sp = c / max(pw.yx, vec2(1e-4)) + 0.5;
        vec4 src = on ? getToColor(sp) : getFromColor(sp);
        col = vec4(clamp(src.rgb * pw.z, 0.0, 1.0), src.a);
    }
    if (pw.w > 0.0) {
        float r = length(vec2(c.x * ratio, c.y));
        float dv = pw.w * exp(-(r / max(uK0.y, 1e-4)) * (r / max(uK0.y, 1e-4)));
        col.rgb = max(col.rgb, vec3(dv));
    }
    return col;
}
"""


BEATRIPPLE = """// ---- beatripple (ours, TC-33 blues-Qing 'Image Transition', clean-room): K1 drops are born on evenly spaced
// beats of the run (drop k at progress k / drops; Drive beats + Beats = drops gives one per beat), at hashed spots
// (seed). Each ring grows from its spot (radius = f^grow x far, f = the drop's own 0..1 run) to that spot's farthest
// frame corner (+ soft) by progress 1, so the union of the discs is all B at the end; inside a disc = B (soft edge). Damped sine waves at every ring front (amp, waves
// per unit, gaussian width, fading as the ring grows: (1 - f) exp(-damp f)) bend both pictures. Units: the frame
// height = 1 (aspect-correct circles). Loop capped at 16 (T-124).
uint tbrH(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
vec2 tbrSpot(int k, int seed) {
    uint h = tbrH(uint(k) * 2654435761u ^ uint(seed) * 1597334677u);
    uint g = tbrH(h ^ 0x9e3779b9u);
    return vec2(float(h >> 8u), float(g >> 8u)) * (1.0 / 16777216.0);
}
vec4 tbeatripple_transition(vec2 uv) {
    int n = clamp(int(round(uK0.x)), 1, 16);
    float amp = uK0.y, waves = uK0.z, wid = max(uK0.w, 1e-4), soft = max(uK1.x, 0.0), damp = uK1.z;
    float grow = max(uK1.w, 1e-3);
    int seed = int(round(uK1.y));
    vec2 q = vec2(uv.x * ratio, uv.y);
    vec2 off = vec2(0.0);
    float m = 0.0;
    for (int k = 0; k < 16; k++) {
        if (k >= n) break;
        float b = float(k) / float(n);
        if (progress <= b) continue;
        float f = min((progress - b) / (1.0 - b), 1.0);
        vec2 c = tbrSpot(k, seed) * vec2(ratio, 1.0);
        vec2 d = q - c;
        float dist = length(d);
        float far = length(vec2(max(c.x, ratio - c.x), max(c.y, 1.0 - c.y))) + soft;
        float r = pow(f, grow) * far;
        m = max(m, soft > 0.0 ? 1.0 - smoothstep(r - soft, r, dist) : (dist <= r ? 1.0 : 0.0));
        float x = (dist - r) / wid;
        float a = amp * sin(6.283185307 * waves * (dist - r)) * exp(-x * x) * (1.0 - f) * exp(-damp * f);
        if (dist > 1e-6) off += d / dist * a;
    }
    vec2 o = vec2(off.x / ratio, off.y);
    return mix(getFromColor(uv + o), getToColor(uv + o), m);
}
"""


JIGSAW = """// ---- jigsaw (ours, FX7c 7C-29, clean-room from the Notch Jigsaw description): a cols x rows grid of interlocking
// pieces; every inner edge carries one round knob whose side comes from a hash of the EDGE (both neighbours agree). Each
// piece flips over around its vertical centre line (A on the front, B on the back) at its own time: order = diagonal
// sweep mixed with a hash (random), spread over the run (spread). Gap colour behind a turning piece = grey level gap,
// optional borders (border, in cell units). Loops: none (4 knob tests + <= 4 border probes per pixel).
uint tjgH(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float tjgSide(int x, int y, int k, int seed) {
    return (tjgH(uint(x) * 73856093u ^ uint(y) * 19349663u ^ uint(k) * 83492791u ^ uint(seed) * 2654435761u) & 1u) == 1u ? 1.0 : -1.0;
}
ivec2 tjgPiece(vec2 q, ivec2 n, float kr, int seed) {
    ivec2 c = clamp(ivec2(floor(q)), ivec2(0), n - 1);
    vec2 f = q - vec2(c);
    float o = 0.6 * kr;
    if (c.x > 0 && tjgSide(c.x, c.y, 0, seed) > 0.0 && length(f - vec2(o, 0.5)) < kr) return c + ivec2(-1, 0);
    if (c.x < n.x - 1 && tjgSide(c.x + 1, c.y, 0, seed) < 0.0 && length(f - vec2(1.0 - o, 0.5)) < kr) return c + ivec2(1, 0);
    if (c.y > 0 && tjgSide(c.x, c.y, 1, seed) > 0.0 && length(f - vec2(0.5, o)) < kr) return c + ivec2(0, -1);
    if (c.y < n.y - 1 && tjgSide(c.x, c.y + 1, 1, seed) < 0.0 && length(f - vec2(0.5, 1.0 - o)) < kr) return c + ivec2(0, 1);
    return c;
}
vec4 tjigsaw_transition(vec2 uv) {
    ivec2 n = ivec2(clamp(int(round(uK0.x)), 1, 64), clamp(int(round(uK0.y)), 1, 64));
    float kr = uK0.z, rnd = uK0.w, spread = clamp(uK1.x, 0.0, 0.95), shade = uK1.z, bw = uK1.w, gap = uK2.x;
    int seed = int(round(uK1.y));
    vec2 q = uv * vec2(n);
    ivec2 pc = tjgPiece(q, n, kr, seed);
    vec4 gc = vec4(vec3(gap), 1.0);
    if (bw > 0.0) {
        if (tjgPiece(q + vec2(bw, 0.0), n, kr, seed) != pc || tjgPiece(q - vec2(bw, 0.0), n, kr, seed) != pc ||
            tjgPiece(q + vec2(0.0, bw), n, kr, seed) != pc || tjgPiece(q - vec2(0.0, bw), n, kr, seed) != pc) return gc;
    }
    float sweep = float(pc.x + pc.y) / float(max(n.x + n.y - 2, 1));
    float hr = float(tjgH(uint(pc.x) * 1597334677u ^ uint(pc.y) * 3812015801u ^ uint(seed) * 2654435761u) >> 8u) * (1.0 / 16777216.0);
    float ord = mix(sweep, hr, rnd);
    float f = clamp((progress - ord * spread) / (1.0 - spread), 0.0, 1.0);
    float s = cos(3.14159265 * f);
    if (abs(s) < 1e-3) return gc;
    float cx = float(pc.x) + 0.5;
    vec2 sq = vec2(cx + (q.x - cx) / abs(s), q.y);
    if (tjgPiece(sq, n, kr, seed) != pc) return gc;
    vec2 su = sq / vec2(n);
    vec4 c = f < 0.5 ? getFromColor(su) : getToColor(su);
    return vec4(c.rgb * (1.0 - shade * (1.0 - abs(s))), c.a);
}
"""


def own_block(tid):
    return {'matte': MATTE, 'tvoff': TVOFF, 'beatripple': BEATRIPPLE, 'jigsaw': JIGSAW}[tid]


def shader_text(types=None):
    """Compute shader for the given type ids (default: the whole shader bank). The case index = SHADER_TYPES index,
    so a one-type shader and the bank read the same uT.y."""
    types = [t for t in (types or SHADER_TYPES) if t in SHADER_TYPES]
    B = bank()
    parts = [PRELUDE]
    for t in types:
        if t in OWN_SHADER:
            parts.append(own_block(t))
        else:
            parts.append(wrap_gl(t, gl_text(B[t]['stem']), B[t]['params'], B[t]['samplers']))
    cases = []
    for t in types:
        k = SHADER_TYPES.index(t)
        init = '' if t in OWN_SHADER else 't%s_init(); ' % t
        cases.append('        case %d: %sc = t%s_transition(uv); break;' % (k, init, t))
    parts.append("""void main() {
    ivec2 P = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    bool inside = P.x < R.x && P.y < R.y;     // no early return: a type may use barrier() (filmburn patch)
    vec2 uv = (vec2(P) + 0.5) / vec2(R);
    progress = clamp(uT.x, 0.0, 1.0);
    ratio = float(R.x) / float(R.y);
    vec4 c = vec4(0.0);
    switch (int(round(uT.y))) {
%s
        default: c = mix(getFromColor(uv), getToColor(uv), progress); break;
    }
    c = clamp(c, 0.0, 1.0);
    if (inside) TDImageStoreOutput(0, ivec3(P, 0), vec4(c.rgb * c.a, c.a));     // premultiplied out (TD / Resolume)
}
""" % '\n'.join(cases))
    return '\n'.join(parts)


def type_index(tid):
    """uT.y for a shader type (-1 for mosh: not in the shader)."""
    return SHADER_TYPES.index(tid) if tid in SHADER_TYPES else -1


# ------------------------------------------------------------------------------------------------ progress
def ease(name, t, steps=0):
    t = min(max(float(t), 0.0), 1.0)
    if steps and steps > 0:
        t = math.floor(t * steps + 1e-9) / float(steps) if t < 1.0 else 1.0
    if name == 'smooth':
        return t * t * (3.0 - 2.0 * t)
    if name == 'in':
        return t * t * t
    if name == 'out':
        return 1.0 - (1.0 - t) ** 3
    if name == 'inout':
        return 4.0 * t * t * t if t < 0.5 else 1.0 - (-2.0 * t + 2.0) ** 3 / 2.0
    if name == 'expo':
        if t <= 0.0 or t >= 1.0:
            return t
        return 2.0 ** (20.0 * t - 10.0) / 2.0 if t < 0.5 else (2.0 - 2.0 ** (-20.0 * t + 10.0)) / 2.0
    if name == 'sine':
        return 0.5 - 0.5 * math.cos(math.pi * t)
    return t


def run_seconds(drive, duration, beats, bpm):
    """Length of a Go run in seconds (beats: Beats x 60 / BPM). manual = 0 (no run)."""
    if drive == 'beats':
        return max(float(beats), 0.0) * 60.0 / max(float(bpm), 1e-3)
    if drive == 'seconds':
        return max(float(duration), 0.0)
    return 0.0


def quantize_start(now, quant, bpm, phase=None):
    """Start time of a Go: now (off) or the next beat / bar boundary. phase = the beat clock's 0..1 phase at `now`
    (a CHOP channel), else a grid anchored at absTime 0. A Go within 1/32 beat of a boundary starts at once."""
    if quant not in ('beat', 'bar'):
        return float(now)
    beat = 60.0 / max(float(bpm), 1e-3)
    unit = beat * (4.0 if quant == 'bar' else 1.0)
    if phase is None:
        ph = (now % unit) / unit
    else:
        ph = float(phase) % 1.0 if quant == 'beat' else (float(phase) % 4.0) / 4.0
    wait = (1.0 - ph) * unit
    if wait >= unit - beat / 32.0 or wait < 1e-6:
        wait = 0.0
    return float(now) + wait


def go_state(cur_raw, now, run_s, start, backstyle='rewind', target=None):
    """A Go / Back from the current raw progress: dict of the State pars. target None = the far side (toggle)."""
    tgt = (0.0 if cur_raw >= 0.5 else 1.0) if target is None else float(target)
    swap = 1.0 if (backstyle == 'forward' and tgt < cur_raw) else 0.0
    return {'Gofrom': float(cur_raw), 'Goto': tgt, 'Gotime': float(start), 'Godur': float(run_s), 'Goswap': swap}


def progress_raw(drive, manual, st, now):
    """Raw progress 0..1. manual: the slider. Else the Go run in st (Gofrom, Goto, Gotime, Godur); Gotime < 0 = the
    slider (no Go yet)."""
    if drive == 'manual' or st.get('Gotime', -1.0) < 0:
        return min(max(float(manual), 0.0), 1.0)
    a, b, t0, d = st['Gofrom'], st['Goto'], st['Gotime'], st['Godur']
    if now < t0:
        return a
    f = 1.0 if d <= 0 else min(max((now - t0) / d, 0.0), 1.0)
    return a + (b - a) * f


def shader_progress(raw, swap, ease_name, steps=0):
    """(eased progress for the shader, swap flag). Swap (Backstyle forward on the way back): the shader plays B -> A
    forward, so it gets 1 - raw with from/to exchanged; the out ends stay A at raw 0 and B at raw 1."""
    if swap > 0.5:
        return ease(ease_name, 1.0 - raw, steps), 1.0
    return ease(ease_name, raw, steps), 0.0


def out_index(raw, is_mosh):
    """out_sel: 0 = A exactly, 1 = B exactly, 2 = shader, 3 = mosh sub-COMP. Ends never cook the transition."""
    if raw <= 0.0:
        return 0
    if raw >= 1.0:
        return 1
    return 3 if is_mosh else 2


def pick_random(pool_text, current, seed=None):
    """Random type from a pool text ('wipe cube #all' ...); never the current one when there is a choice."""
    words = [w for w in re.split(r'[\s,]+', pool_text or '') if w]
    pool = list(TYPES) if any(w in ('*', 'all', '#all') for w in words) else [w for w in words if w in TYPES]
    if not pool:
        return current
    choice = [t for t in pool if t != current] or pool
    r = random.Random(seed)
    return choice[r.randrange(len(choice))]


# ------------------------------------------------------------------------------------------------ TD runtime
# (called from expressions / the Parameter Execute DAT in FX_trans; `c` = the FX_trans COMP)
def _p(c, name, d=0.0):
    p = getattr(c.par, name, None)
    return d if p is None else p.eval()


def bpm_of(c):
    path, chan = _p(c, 'Bpmchop', ''), _p(c, 'Bpmchan', 'bpm')
    if path:
        o = c.op(path) if not str(path).startswith('/') else op(path)       # noqa: F821 (TD global)
        if o is not None and o.numChans:
            ch = o[chan] if chan else o[0]
            if ch is not None and float(ch[0]) > 0:
                return float(ch[0])
    return float(_p(c, 'Bpm', 120.0))


def phase_of(c):
    path, chan = _p(c, 'Bpmchop', ''), _p(c, 'Phasechan', '')
    if path and chan:
        o = c.op(path) if not str(path).startswith('/') else op(path)       # noqa: F821
        if o is not None and o[chan] is not None:
            return float(o[chan][0])
    return None


def state_of(c):
    return {k: float(_p(c, k, -1.0 if k == 'Gotime' else 0.0)) for k in ('Gofrom', 'Goto', 'Gotime', 'Godur', 'Goswap')}


def raw_of(c, now):
    return progress_raw(_p(c, 'Drive', 'manual'), _p(c, 'Progress', 0.0), state_of(c), now)


def values(c, now):
    """[raw, eased, swap, out index, type index] for the `prog` Constant CHOP (one call per frame)."""
    raw = raw_of(c, now)
    st = state_of(c)
    swap = st['Goswap'] if _p(c, 'Drive', 'manual') != 'manual' and st['Gotime'] >= 0 else 0.0
    p, sw = shader_progress(raw, swap, _p(c, 'Ease', 'linear'), int(_p(c, 'Steps', 0)))
    tid = _p(c, 'Type', 'fade')
    return [raw, p, sw, float(out_index(raw, tid == 'mosh')), float(type_index(tid))]


_VC = {}


def chan(c, now, k):
    """values()[k] for the prog CHOP's channel k. Channel 0 computes (once per cook), channels 1..4 reuse that result
    when it is for the same COMP and time: one values() call per cook instead of 5 (~75 us each live)."""
    key = (c.path, now)
    hit = _VC.get(key[0])
    if k == 0 or hit is None or hit[0] != now:
        hit = (now, values(c, now))
        _VC[key[0]] = hit
    return hit[1][k]


def on_go(c, now, target=None):
    """Go (target None: toward the far side), Back (target 0), Cut (instant)."""
    drive = _p(c, 'Drive', 'manual')
    if drive == 'manual':
        c.par.Drive.val = 'seconds'
        drive = 'seconds'
    bpm = bpm_of(c)
    run_s = run_seconds(drive, _p(c, 'Duration', 2.0), _p(c, 'Beats', 4.0), bpm)
    start = quantize_start(now, _p(c, 'Quantize', 'off'), bpm, phase_of(c))
    pool = _p(c, 'Randompool', '')
    if pool:
        c.par.Type.val = pick_random(pool, _p(c, 'Type', 'fade'))
    st = go_state(raw_of(c, now), now, run_s, start, _p(c, 'Backstyle', 'rewind'), target)
    for k, v in st.items():
        getattr(c.par, k).val = v
    return st


def on_cut(c, now):
    st = go_state(raw_of(c, now), now, 0.0, now, 'rewind', None)
    for k, v in st.items():
        getattr(c.par, k).val = v
    if _p(c, 'Drive', 'manual') == 'manual':
        c.par.Progress.val = st['Goto']
    return st


def apply_type(c, keep=False):
    """Type changed: knob labels K1..K10 follow the type, values reset to its defaults (unless keep), unused knobs
    disabled, and (Compile = selected) the shader text = this type only. Returns the knob table."""
    tid = _p(c, 'Type', 'fade')
    rows = knob_table(tid)
    for k in range(NKNOBS):
        p = getattr(c.par, 'K%d' % (k + 1))
        if k < len(rows):
            lab, d, lo, hi = rows[k]
            p.label = 'K%d %s' % (k + 1, lab)
            p.enable = True
            p.normMin, p.normMax = lo, hi
            p.default = d
            if not keep:
                p.val = d
        else:
            p.label = 'K%d -' % (k + 1)
            p.enable = False
    dat = c.op('trans_compute')
    if dat is not None:
        txt = shader_text(None if _p(c, 'Compile', 'selected') == 'bank' else
                          ([tid] if tid in SHADER_TYPES else ['fade']))
        if dat.text != txt:
            dat.text = txt
    return rows


# ------------------------------------------------------------------------------------------------ numpy references
def ref_uv(w, h):
    import numpy as np
    x = (np.arange(w) + 0.5) / w
    y = (np.arange(h) + 0.5) / h
    return np.meshgrid(x, y)                         # row 0 = bottom (TD numpyArray order is bottom-first too)


def _smoothstep(e0, e1, x):
    import numpy as np
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0) if e1 != e0 else (x >= e0).astype(float)
    return t * t * (3.0 - 2.0 * t)


def ref_mask(tid, p, w=54, h=96, knobs=None, matte=None):
    """B weight per pixel (0 = A, 1 = B) for the mask-type transitions, numpy, rows bottom-first. knobs = K list."""
    import numpy as np
    k = list(knobs) if knobs is not None else [r[1] for r in knob_table(tid)]
    U, V = ref_uv(w, h)
    if tid == 'fade':
        return np.full(U.shape, p)
    if tid == 'wipe':
        dx, dy, sm = k[0], k[1], k[2]
        n = math.hypot(dx, dy)
        vx, vy = dx / n, dy / n
        s = abs(vx) + abs(vy)
        vx, vy = vx / s, vy / s
        d = vx * 0.5 + vy * 0.5
        m = (0.0 if p <= 0 else 1.0) * (1.0 - _smoothstep(-sm, 0.0, vx * U + vy * V - (d - 0.5 + p * (1.0 + sm))))
        return m
    if tid == 'circleopen':
        sm, opening = k[0], k[1] > 0.5
        x = p if opening else 1.0 - p
        m = _smoothstep(-sm, 0.0, math.sqrt(2.0) * np.hypot(U - 0.5, V - 0.5) - x * (1.0 + sm))
        return 1.0 - m if opening else m
    if tid == 'beatripple':
        return ref_beatripple(p, w, h, k)[0]
    if tid == 'jigsaw':
        return (ref_jigsaw(p, w, h, k)[0] == 1).astype(float)
    if tid == 'matte':
        sm, inv, _ch, gam = k[0], k[1] > 0.5, k[2], k[3]
        v = np.clip(matte if matte is not None else U, 0.0, 1.0) ** max(gam, 1e-3)
        if inv:
            v = 1.0 - v
        e = p * (1.0 + sm)
        if sm > 0:
            m = np.clip((e - v) / sm, 0.0, 1.0)
            m = m * m * (3.0 - 2.0 * m)
        else:
            m = (e >= v).astype(float)
        return m * (0.0 if p <= 0 else 1.0)
    raise ValueError('no mask reference for %s' % tid)


def _br_hash(x):
    import numpy as np
    x = np.asarray(x, dtype=np.uint64) & 0xffffffff
    x ^= x >> 16
    x = (x * 0x7feb352d) & 0xffffffff
    x ^= x >> 15
    x = (x * 0x846ca68b) & 0xffffffff
    x ^= x >> 16
    return x


def br_spot(k, seed):
    h = int(_br_hash((k * 2654435761 ^ seed * 1597334677) & 0xffffffff))
    g = int(_br_hash(h ^ 0x9e3779b9))
    return (h >> 8) / 16777216.0, (g >> 8) / 16777216.0


def ref_beatripple(p, w=54, h=96, knobs=None):
    """(m, ox, oy): B weight and the uv offset per pixel of tbeatripple_transition (numpy, rows bottom-first)."""
    import numpy as np
    k = list(knobs) if knobs is not None else [r[1] for r in knob_table('beatripple')]
    n = min(max(int(round(k[0])), 1), 16)
    amp, waves, wid, soft, seed, damp = k[1], k[2], max(k[3], 1e-4), max(k[4], 0.0), int(round(k[5])), k[6]
    grow = max(k[7], 1e-3)
    ratio = float(w) / float(h)
    U, V = ref_uv(w, h)
    qx, qy = U * ratio, V
    m = np.zeros(U.shape)
    ox, oy = np.zeros(U.shape), np.zeros(U.shape)
    for i in range(n):
        b = float(i) / n
        if p <= b:
            continue
        f = min((p - b) / (1.0 - b), 1.0)
        sx, sy = br_spot(i, seed)
        cx, cy = sx * ratio, sy
        dx, dy = qx - cx, qy - cy
        dist = np.hypot(dx, dy)
        far = math.hypot(max(cx, ratio - cx), max(cy, 1.0 - cy)) + soft
        r = f ** grow * far
        mi = (1.0 - _smoothstep(r - soft, r, dist)) if soft > 0 else (dist <= r).astype(float)
        m = np.maximum(m, mi)
        x = (dist - r) / wid
        a = amp * np.sin(6.283185307 * waves * (dist - r)) * np.exp(-x * x) * (1.0 - f) * math.exp(-damp * f)
        nz = dist > 1e-6
        ox = ox + np.where(nz, dx / np.where(nz, dist, 1.0) * a, 0.0)
        oy = oy + np.where(nz, dy / np.where(nz, dist, 1.0) * a, 0.0)
    return m, ox / ratio, oy


def _jg_side(x, y, k, seed):
    import numpy as np
    m = 0xffffffff
    v = ((np.asarray(x, np.int64) & m) * 73856093 & m) ^ ((np.asarray(y, np.int64) & m) * 19349663 & m) ^ \
        ((k * 83492791) & m) ^ ((seed * 2654435761) & m)
    return np.where((_br_hash(v) & 1) == 1, 1.0, -1.0)


def jg_piece(qx, qy, n, kr, seed):
    """tjgPiece in numpy: piece (px, py) of cell-space points (qx, qy); n = (cols, rows)."""
    import numpy as np
    cx = np.clip(np.floor(qx).astype(np.int64), 0, n[0] - 1)
    cy = np.clip(np.floor(qy).astype(np.int64), 0, n[1] - 1)
    fx, fy = qx - cx, qy - cy
    o = 0.6 * kr
    px, py = cx.copy(), cy.copy()
    done = np.zeros(cx.shape, bool)
    for cond, dx, dy, kx, ky in (
            ((cx > 0) & (_jg_side(cx, cy, 0, seed) > 0) & (np.hypot(fx - o, fy - 0.5) < kr), -1, 0, 0, 0),
            ((cx < n[0] - 1) & (_jg_side(cx + 1, cy, 0, seed) < 0) & (np.hypot(fx - (1 - o), fy - 0.5) < kr), 1, 0, 0, 0),
            ((cy > 0) & (_jg_side(cx, cy, 1, seed) > 0) & (np.hypot(fx - 0.5, fy - o) < kr), 0, -1, 0, 0),
            ((cy < n[1] - 1) & (_jg_side(cx, cy + 1, 1, seed) < 0) & (np.hypot(fx - 0.5, fy - (1 - o)) < kr), 0, 1, 0, 0)):
        hit = cond & ~done
        px, py = np.where(hit, cx + dx, px), np.where(hit, cy + dy, py)
        done |= hit
    return px, py


def ref_jigsaw(p, w=54, h=96, knobs=None):
    """(which, sx, sy): per pixel 0 = A, 1 = B, -1 = gap, and the uv each side is read at (rows bottom-first)."""
    import numpy as np
    k = list(knobs) if knobs is not None else [r[1] for r in knob_table('jigsaw')]
    n = (min(max(int(round(k[0])), 1), 64), min(max(int(round(k[1])), 1), 64))
    kr, rnd, spread, seed, bw = k[2], k[3], min(max(k[4], 0.0), 0.95), int(round(k[5])), k[7]
    U, V = ref_uv(w, h)
    qx, qy = U * n[0], V * n[1]
    px, py = jg_piece(qx, qy, n, kr, seed)
    gapm = np.zeros(U.shape, bool)
    if bw > 0:
        for dx, dy in ((bw, 0), (-bw, 0), (0, bw), (0, -bw)):
            ax, ay = jg_piece(qx + dx, qy + dy, n, kr, seed)
            gapm |= (ax != px) | (ay != py)
    sweep = (px + py) / float(max(n[0] + n[1] - 2, 1))
    m = 0xffffffff
    hr = (_br_hash(((px & m) * 1597334677 & m) ^ ((py & m) * 3812015801 & m) ^ ((seed * 2654435761) & m)) >> 8) / 16777216.0
    order = sweep + (hr - sweep) * rnd
    f = np.clip((p - order * spread) / (1.0 - spread), 0.0, 1.0)
    s = np.cos(3.14159265 * f)
    cx = px + 0.5
    sqx = cx + (qx - cx) / np.maximum(np.abs(s), 1e-3)
    bx, by = jg_piece(sqx, qy, n, kr, seed)
    gapm |= (np.abs(s) < 1e-3) | (bx != px) | (by != py)
    which = np.where(gapm, -1, np.where(f < 0.5, 0, 1))
    return which, sqx / n[0], V


def ref_fadecolor(p, a, b, color=(0.0, 0.0, 0.0, 1.0), phase=0.4):
    """FadeColor on flat colours a, b (rgba): the output colour (scalar maths, GLSL smoothstep incl. reversed edges)."""
    def ss(e0, e1, x):
        t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
        return t * t * (3.0 - 2.0 * t)
    fa = [color[i] + (a[i] - color[i]) * ss(1.0 - phase, 0.0, p) for i in range(4)]
    fb = [color[i] + (b[i] - color[i]) * ss(phase, 1.0, p) for i in range(4)]
    return [fa[i] + (fb[i] - fa[i]) * p for i in range(4)]


def ref_tvoff(p, gap=0.1, line=0.004, glow=4.0):
    """(which, sy, sx, gain, dot): which = 'A' / 'B' / 'black' at raw progress p (mirror of ttvoff_transition)."""
    g = min(max(gap, 0.0), 0.95)
    h = 0.5 * (1.0 - g)
    on = p >= 1.0 - h
    if not on and p >= h:
        return ('black', 0.0, 0.0, 0.0, 0.0)
    s = (p - (1.0 - h)) / h if on else p / h
    sy, sx, gain, dot = power_mirror(on, s, line, glow)
    return ('B' if on else 'A', sy, sx, gain, dot)


def power_mirror(on, s, line=0.004, glow=4.0):
    """tvPower in Python (= fx_analog_crt_logic.power_shape with its LINE_H = line and the 4.0 gain cap = glow)."""
    if on:
        if s >= 1.0:
            return 1.0, 1.0, 1.0, 0.0
        e = s * s * (3.0 - 2.0 * s)
        return 0.6 + 0.4 * e, 0.75 + 0.25 * e, e, 0.0
    if s < 0.35:
        e = s / 0.35
        sy = 1.0 - (1.0 - line) * (e * e)
        return sy, 1.0, min(1.0 / math.sqrt(sy), glow), 0.0
    if s < 0.55:
        e = (s - 0.35) / 0.2
        return line, 1.0 - (1.0 - line) * e, glow, 0.0
    if s < 1.0:
        return 0.0, 0.0, 0.0, math.exp(-6.0 * (s - 0.55) / 0.45)
    return 0.0, 0.0, 0.0, 0.0


def sources_rows():
    """[(type id, file, author, licence, description)] for SOURCES / the doc."""
    B = bank()
    return [(t, (B[t]['stem'] or '-') + ('.glsl' if B[t]['stem'] else ''), B[t]['author'], B[t]['license'],
             B[t]['description']) for t in TYPES]
