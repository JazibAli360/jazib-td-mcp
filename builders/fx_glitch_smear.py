# fx_glitch_smear - FX_glitch module 'smear' (FX1 DG-05 smear/stretch + DG-06 displace-feedback smear + TC-25 pixel
# strips by coordinate remap: mode `strips`, numpy mirror builders/fx_glitch_smear_logic.py).
# A module file = PAGES (custom pars on the instance COMP) + PRESETS (zkit slots) + build(m, H) that fills the
# instance COMP with in1 -> ... -> out1. The rack (builders/fx_glitch.py) makes the COMP, adds the pars, calls build,
# adds the zkit panel and wires the slot. Template: docs/builds/fx_glitch.md "Module template".
# Rules: Amount 0 = exact passthrough (texelFetch, same format); compute-mode GLSL (T-47, a rack is a multi-pass
# chain); output size = input size; ASCII only.

MODULE = 'smear'
MODES = ['smearmax', 'smearmin', 'stretch', 'feedback', 'strips', 'radial', 'maskedge']

PAGES = [
    ('Smear', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'smearmax', {'names': MODES, 'labels': ['Smear max', 'Smear min', 'Stretch band',
                                                                  'Feedback drag', 'Pixel strips',
                                                                  'Radial stretch', 'Mask edge stretch']}),
        ('Angle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle (0 = down)'}),
        ('Length', 'Float', 160.0, {'min': 0, 'max': 400, 'label': 'Length px'}),
        ('Threshold', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Threshold'}),
        ('Decay', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Decay'}),
        ('Wobble', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Wobble'}),
        ('Bandpos', 'Float', 0.45, {'min': 0, 'max': 1, 'label': 'Band pos'}),
        ('Bandwidth', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Band width'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Strips', [                                  # mode strips (TC-25); Length / Wobble / Decay / Threshold shared
        ('Stripwidth', 'Float', 8.0, {'min': 1, 'max': 200, 'label': 'Strip width px'}),
        ('Stripjitter', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Strip phase jitter'}),
        ('Snap', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Snap across (1 = flat strips)'}),
        ('Curve', 'Float', 0.0, {'min': -400, 'max': 400, 'label': 'Curve px'}),
        ('Curvefreq', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Curve waves'}),
        ('Speed', 'Float', 0.0, {'min': -800, 'max': 800, 'label': 'Scroll px/s'}),
        ('Density', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Share of strips'}),
    ]),
    ('Radial', [                                  # modes radial / maskedge (DG-05 rest)
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x (radial)'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y (radial)'}),
        ('Masktop', 'TOP', '', {'label': 'Mask TOP (mask edge stretch)'}),
    ]),
]
PANEL_PAGES = ['Smear', 'Strips', 'Radial']

# zkit preset slots: (slot, name, values); menus as their index (zkit stores raw menu indices). Full state (T-124
# (1)): page defaults + the look, so a recall never inherits the previous preset's pars.
_D = dict((n, o['names'].index(d) if s_ == 'Menu' else d) for _pg, pl in PAGES for n, s_, d, o in pl if s_ != 'TOP')
PRESETS = [
    (1, 'drip', dict(_D, Amount=1.0, Mode=0, Angle=0.0, Length=220.0, Threshold=0.55, Decay=0.7, Wobble=0.5, Seed=1)),
    (2, 'shadow', dict(_D, Amount=1.0, Mode=1, Angle=90.0, Length=160.0, Threshold=0.6, Decay=0.8, Wobble=0.3,
                       Seed=2)),
    (3, 'stretch', dict(_D, Amount=1.0, Mode=2, Angle=0.0, Bandpos=0.45, Bandwidth=0.08, Wobble=0.2, Seed=3)),
    (4, 'mosh', dict(_D, Amount=1.0, Mode=3, Angle=0.0, Length=120.0, Threshold=0.05, Decay=0.92, Wobble=0.4,
                     Seed=4)),
    (5, 'pixel strips', dict(_D, Amount=1.0, Mode=4, Angle=0.0, Length=140.0, Threshold=0.0, Decay=1.0, Wobble=0.7,
                             Stripwidth=6.0, Stripjitter=1.0, Snap=1.0, Density=0.85, Seed=5)),
    (6, 'liquid strips', dict(_D, Amount=1.0, Mode=4, Angle=90.0, Length=90.0, Threshold=0.0, Decay=0.6, Wobble=0.5,
                              Stripwidth=14.0, Stripjitter=1.0, Snap=0.0, Curve=70.0, Curvefreq=2.0, Speed=60.0,
                              Seed=6)),
    (7, 'bright streaks', dict(_D, Amount=1.0, Mode=4, Angle=0.0, Length=320.0, Threshold=0.6, Decay=0.85,
                               Wobble=0.8, Stripwidth=3.0, Stripjitter=1.0, Snap=0.5, Density=1.0, Seed=7)),
    (8, 'radial burst', dict(_D, Amount=1.0, Mode=5, Bandpos=0.12, Bandwidth=0.05, Wobble=0.6, Centerx=0.5,
                             Centery=0.55, Seed=8)),
]

SHADER = """// FX_glitch smear (compute, T-47). in0 = picture, in1 = previous output (Feedback mode) or the picture.
// in2 = stamp (1x1: x = this cook's time, y = the previous cook's time); a gap > 0.25 s = stale feedback history.
// uA = amount mode length threshold; uB = dir.x dir.y decay wobble; uC = bandpos bandwidth seed; uD.x = time
// uE = stripwidth stripjitter curve curvefreq; uF = snap speed density (mode strips, = fx_glitch_smear_logic)
// uG = centre x y (px) (radial). Mode maskedge: in1 = the mask (prev_src switches to it).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
uniform vec4 uE;
uniform vec4 uF;
uniform vec4 uG;
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
float hash(float n) { return fract(sin(n * 12.9898 + uC.z * 78.233) * 43758.5453); }
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hk(int k, uint salt) { return float(lb32(uint(k) * 0x9e3779b9u ^ lb32(salt + uint(uC.z) * 7919u)) >> 8)
                                    / 16777216.0; }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }       // exact passthrough
    vec2 sz = vec2(isz);
    vec2 pc = vec2(p) + 0.5;
    vec2 dir = uB.xy;
    vec2 perp = vec2(-dir.y, dir.x);
    float col = floor(dot(pc, perp) / 2.0);                                     // 2 px columns across the drag
    float wob = 1.0 - uB.w * hash(col);
    int mode = int(uA.y + 0.5);
    vec4 o = c;
    if (mode <= 1) {                                                            // smear max / min
        float L = uA.z * wob;
        int N = int(clamp(ceil(L / 6.0), 1.0, 24.0));                  // <= 24 bilinear taps (perf, 60 fps)
        float stp = L / float(N);
        float bs = (mode == 0) ? luma(c.rgb) : 1.0 - luma(c.rgb);
        for (int k = 1; k <= 24; k++) {
            if (k > N) break;
            float f = float(k) / float(N);
            vec4 s = texture(sTD2DInputs[0], (pc - dir * stp * float(k)) / sz);
            float l = (mode == 0) ? luma(s.rgb) : 1.0 - luma(s.rgb);
            float fall = 1.0 - f * (1.0 - uB.z);
            if (l > uA.w && l * fall > bs) { bs = l * fall; o = mix(c, s, fall); }
        }
    } else if (mode == 2) {                                                     // stretch band
        float E = abs(dir.x) * sz.x + abs(dir.y) * sz.y;
        float s = dot(pc - 0.5 * sz, dir);
        float s0 = (uC.x - 0.5) * E;
        float s1 = s0 + uC.y * E * wob;
        float sc = clamp(s, s0, s1);
        o = texture(sTD2DInputs[0], (pc + dir * (sc - s)) / sz);
    } else if (mode == 4) {                                                     // pixel strips (TC-25)
        vec2 cc = pc - 0.5 * sz;
        float s = dot(cc, dir), t = dot(cc, perp);
        float E = abs(dir.x) * sz.x + abs(dir.y) * sz.y;
        float tb = t + uE.z * sin(6.2831853 * uE.w * s / E);                     // curved strips
        float W = max(uE.x, 1.0);
        float k = floor(tb / W);
        int ki = int(k);
        if (hk(ki, 3u) < uF.z) {                                                // Density: share of strips
            float Lk = max(uA.z * (1.0 - uB.w * hk(ki, 1u)), 1.0);
            float ph = uF.y * uD.x + hk(ki, 2u) * Lk * uE.y;
            float s0 = floor((s + ph) / Lk) * Lk - ph;                          // segment start along the strip
            vec2 q = pc + dir * (s0 + 0.5 - s) + perp * (uF.x * ((k + 0.5) * W - tb));
            vec4 sm = texelFetch(sTD2DInputs[0], clamp(ivec2(floor(q)), ivec2(0), isz - 1), 0);
            if (luma(sm.rgb) >= uA.w) o = mix(sm, c, (1.0 - uB.z) * (s - s0) / Lk);
        }
    } else if (mode == 5) {                                                     // radial stretch band (DG-05)
        vec2 v = pc - uG.xy; float r = length(v);
        float R = 0.5 * length(sz);
        float ang = atan(v.y, v.x);
        float wr = 1.0 - uB.w * hk(int(floor((ang + 3.14159265) / 6.2831853 * 256.0)), 5u);   // per-ray jitter
        float r0 = uC.x * R, r1 = r0 + uC.y * R * wr;
        float rc = clamp(r, r0, r1);
        if (r > 1e-4) o = texture(sTD2DInputs[0], (uG.xy + v / r * rc) / sz);
    } else if (mode == 6) {                                                     // mask edge stretch (DG-05)
        if (luma(texture(sTD2DInputs[1], pc / sz).rgb) <= uA.w) {               // outside the mask: drag its edge
            float L = uA.z * wob;
            int N = int(clamp(ceil(L / 4.0), 1.0, 24.0));
            float stp = L / float(N);
            for (int k = 1; k <= 24; k++) {
                if (k > N) break;
                vec2 q = pc - dir * stp * float(k);
                if (luma(texture(sTD2DInputs[1], q / sz).rgb) > uA.w) {
                    vec4 s = texture(sTD2DInputs[0], q / sz);
                    o = mix(s, c, (float(k) / float(N)) * (1.0 - uB.z));
                    break;
                }
            }
        }
    } else if (mode == 3) {                                                     // feedback drag (DG-06)
        vec4 st = texelFetch(sTD2DInputs[2], ivec2(0), 0);
        if (st.x - st.y > 0.25) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }  // fresh: no stale history
        float n = hash(col + floor(uD.x * 8.0));
        vec2 d = dir + perp * (n - 0.5) * uB.w;
        vec4 pd = texture(sTD2DInputs[1], (pc - d * uA.z * 0.05 * (0.25 + luma(c.rgb))) / sz);
        float keep = uB.z * smoothstep(uA.w, uA.w + 0.2, length(c.rgb - pd.rgb) + luma(pd.rgb) * 0.5);
        o = mix(c, pd, keep);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, o, uA.x));
}
"""

STAMP = """// stamp: 1x1 rgba32float in place (T-110 (5)): x = now, y = the previous cook's now. Cooks only when fx does.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;
void main() {
    vec4 s = TDImageLoadOutput(0, ivec3(0));
    TDImageStoreOutput(0, ivec3(0), vec4(uT.x, s.x, 0.0, 1.0));
}
"""

P = "parent().par.{}.eval()"


def uniforms():
    """fx uniforms [(name, [x, y, z, w exprs])] (tested offline against SHADER)."""
    return [('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Length'), P.format('Threshold')]),
            ('uB', ['math.sin(math.radians(%s))' % P.format('Angle'),
                    '-math.cos(math.radians(%s))' % P.format('Angle'), P.format('Decay'), P.format('Wobble')]),
            ('uC', [P.format('Bandpos'), P.format('Bandwidth'), P.format('Seed'), '0']),
            ('uD', ['absTime.seconds', '0', '0', '0']),
            ('uE', [P.format('Stripwidth'), P.format('Stripjitter'), P.format('Curve'), P.format('Curvefreq')]),
            ('uF', [P.format('Snap'), P.format('Speed'), P.format('Density'), '0']),
            ('uG', ['%s * me.inputs[0].width' % P.format('Centerx'), '%s * me.inputs[0].height' % P.format('Centery'),
                    '0', '0'])]


def build(m, H):
    """Fill instance COMP m: in1 -> prev_src (+ fb) -> fx (compute GLSL) -> out1. H = rack helpers (mk, expr, sd)."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    fb = mk(m, feedbackTOP, 'fb')
    fb.inputConnectors[0].connect(in1)
    fb.par.top = 'fx'
    fb.comment = 'Previous fx output (Feedback mode only; cooks only while prev_src selects it).'
    prev = mk(m, switchTOP, 'prev_src')
    prev.inputConnectors[0].connect(in1)
    prev.inputConnectors[1].connect(fb)
    ms = mk(m, selectTOP, 'mask_sel')
    expr(ms.par.top, "parent().par.Masktop.eval().path if parent().par.Mode.eval() == 'maskedge' and "
                     "parent().par.Masktop.eval() is not None else me.parent().op('in1').path")
    ms.comment = 'Mask TOP (Radial page) while Mode = mask edge stretch, else in1.'
    prev.inputConnectors[2].connect(ms)
    expr(prev.par.index, "1 if parent().par.Mode.eval() == 'feedback' else (2 if parent().par.Mode.eval() == "
                         "'maskedge' else 0)")
    st = mk(m, glslTOP, 'stamp')
    sd = m.op('stamp_compute')
    if sd is None:
        sd = mk(m, textDAT, 'stamp_compute')
        sd.dock = st
    sd.text = STAMP
    st.par.mode = 'compute'
    st.par.computedat = sd
    st.par.outputresolution = 'custom'
    st.par.resolutionw, st.par.resolutionh = 1, 1
    st.par.format = 'rgba32float'
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    st.par.vec0name = 'uT'
    expr(st.par.vec0valuex, 'absTime.seconds')
    st.comment = 'Cook clock for fx: a gap > 0.25 s since its last cook = bypassed/panicked -> Feedback history stale.'
    g = mk(m, glslTOP, 'fx')
    d = m.op('fx_compute')
    if d is None:
        d = mk(m, textDAT, 'fx_compute')
        d.dock = g
    d.text = SHADER
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    expr(g.par.resolutionw, 'me.inputs[0].width')
    expr(g.par.resolutionh, 'me.inputs[0].height')
    g.par.format = 'useinput'
    g.inputConnectors[0].connect(in1)
    g.inputConnectors[1].connect(prev)
    g.inputConnectors[2].connect(st)
    U = uniforms()
    g.seq.vec.numBlocks = max(len(U), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)
    g.comment = ('smear: Smear max/min (DG-05), Stretch band, Feedback drag (DG-06), Pixel strips (TC-25). '
                 'Amount 0 = exact passthrough.')
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'mask_sel']},
        {'title': '2 Smear', 'role': 'process', 'ops': ['fb', 'prev_src', 'stamp', 'stamp_compute', 'fx', 'fx_compute'],
         'body': 'One compute pass (smear / stretch / feedback / strips); fb + prev_src only for Feedback drag.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
