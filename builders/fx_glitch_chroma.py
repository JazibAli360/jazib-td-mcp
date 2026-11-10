# fx_glitch_chroma - FX_glitch module 'chroma' (FX1 DG-10): RGB / prism / spectral split in one compute pass.
# Split: RGB (each channel sampled at its own place), Prism (two hue-tinted ghosts added), Spectral (N taps along a
# wavelength ramp, weights normalised so white stays white). Mode: Offset (along Angle), Radial (lens dispersion from
# Centre, Falloff keeps the middle clean), Angle (channels rotated around Centre). Per-channel blur along the split,
# per-line jitter, audio drive (any CHOP channel scales the distance). Amount 0 = exact passthrough.
# Split Time (TC-26 RGB time split): the channels come from different frames, now / Delay / 2 x Delay cooks ago (Order
# picks which channel is which), through the shared native ring (builders/fx_time_ring.py: Texture 3D ring + cook
# counter stamp) and two Time Machine TOPs with 1x1 offset maps (whole cooks, clamped to what the ring holds, so a
# restart never shows stale frames). Spatial Mode / Distance / blur still apply on top. Mirror: fx_glitch_chroma_logic.
import os
_RING = os.path.join(globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders',
                     'fx_time_ring.py')
exec(open(_RING).read())                            # STAMP_RING (cook counter) - the ring's third user
# Template: docs/builds/fx_glitch.md "Module template". ASCII only.

MODULE = 'chroma'
SPLITS = ['rgb', 'prism', 'spectral', 'time']
ORDERS = ['rgb', 'rbg', 'grb', 'gbr', 'brg', 'bgr']   # letters = channel taken now / Delay ago / 2 x Delay ago
MODES = ['offset', 'radial', 'angle']

PAGES = [
    ('Chroma', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Split', 'Menu', 'rgb', {'names': SPLITS, 'labels': ['RGB', 'Prism ghosts', 'Spectral',
                                                               'Time split (TC-26)']}),
        ('Mode', 'Menu', 'offset', {'names': MODES, 'labels': ['Offset', 'Radial', 'Angle (rotate)']}),
        ('Distance', 'Float', 12.0, {'min': 0, 'max': 120, 'label': 'Distance px'}),
        ('Angle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle deg (Offset)'}),
        ('Rotate', 'Float', 2.0, {'min': -30, 'max': 30, 'label': 'Rotate deg (Angle)'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
        ('Falloff', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Radial falloff'}),
        ('Greenshift', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Green position'}),
        ('Taps', 'Int', 8, {'min': 3, 'max': 16, 'label': 'Spectral taps'}),
        ('Ghost', 'Float', 0.6, {'min': 0, 'max': 2, 'label': 'Prism ghost gain'}),
        ('Hue', 'Float', 0.85, {'min': 0, 'max': 1, 'label': 'Prism hue'}),
        ('Blurr', 'Float', 0.0, {'min': 0, 'max': 40, 'label': 'Blur R px'}),
        ('Blurg', 'Float', 0.0, {'min': 0, 'max': 40, 'label': 'Blur G px'}),
        ('Blurb', 'Float', 0.0, {'min': 0, 'max': 40, 'label': 'Blur B px'}),
        ('Linejitter', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Line jitter'}),
        ('Linesize', 'Float', 6.0, {'min': 1, 'max': 200, 'label': 'Line size px'}),
        ('Linerate', 'Float', 8.0, {'min': 0, 'max': 30, 'label': 'Jitter rate Hz'}),
        ('Audiogain', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Audio gain'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Time', [                                    # Split time
        ('Delay', 'Int', 3, {'min': 1, 'max': 30, 'label': 'Delay (cooks per step)'}),
        ('Order', 'Menu', 'rgb', {'names': ORDERS, 'labels': ['R now, G, B late', 'R now, B, G late',
                                                              'G now, R, B late', 'G now, B, R late',
                                                              'B now, R, G late', 'B now, G, R late']}),
        ('Ringquality', 'Menu', 'full', {'names': ['full', 'half'], 'labels': ['Full res ring',
                                                                             'Half res ring (1/4 VRAM)']}),
    ]),
    ('Inputs', [
        ('Audiochop', 'CHOP', '', {'label': 'Audio CHOP (e.g. AC_audio/out_ctl)'}),
        ('Audiochan', 'Str', 'low', {'label': 'Audio channel'}),
    ]),
]
PANEL_PAGES = ['Chroma', 'Time']

# Full state (T-124 (1)): page defaults + the look; op / str pars (Audiochop / Audiochan) are not stored.
_D = dict((n, o['names'].index(d) if s_ == 'Menu' else d) for _pg, pl in PAGES for n, s_, d, o in pl
          if s_ not in ('CHOP', 'Str'))
PRESETS = [
    (1, 'tear', dict(_D, Amount=1.0, Split=0, Mode=0, Distance=14.0, Angle=0.0, Linejitter=0.8, Linesize=6.0,
                     Linerate=10.0)),
    (2, 'lens', dict(_D, Amount=1.0, Split=2, Mode=1, Distance=28.0, Falloff=1.6, Taps=10)),
    (3, 'prism', dict(_D, Amount=1.0, Split=1, Mode=0, Distance=40.0, Angle=30.0, Ghost=0.7, Hue=0.85, Blurr=6.0,
                      Blurg=6.0, Blurb=6.0)),
    (4, 'twist', dict(_D, Amount=1.0, Split=0, Mode=2, Rotate=1.5, Blurr=10.0, Blurb=10.0)),
    (5, 'bass hit', dict(_D, Amount=1.0, Split=2, Mode=0, Distance=6.0, Angle=90.0, Taps=8, Linejitter=0.3,
                         Linesize=24.0, Linerate=4.0, Audiogain=4.0)),
    (6, 'time split', dict(_D, Amount=1.0, Split=3, Distance=0.0, Delay=3, Order=0)),
    (7, 'time smear', dict(_D, Amount=1.0, Split=3, Mode=0, Distance=6.0, Angle=90.0, Delay=6, Order=5, Blurr=8.0,
                           Blurb=8.0)),
    (8, 'ghost lens', dict(_D, Amount=1.0, Split=3, Mode=1, Distance=24.0, Falloff=1.4, Delay=10, Order=2,
                           Ringquality=1)),
]

SHADER = """// FX_glitch chroma (compute). in0 = picture. Every sample is pos(t): t = +1 red side, -1 blue side.
// uA amount split mode distance | uB dir.x dir.y rotate(rad) greenshift | uC centre.x centre.y (px) falloff taps
// uD blurR blurG blurB ghost | uE hue linejitter linesize jitterclock | uF audio factor seed - -
// uG = source slot of R G B for Split time (0 = in0 now, 1 = in1 Delay ago, 2 = in2 2 x Delay ago)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
uniform vec4 uE;
uniform vec4 uF;
uniform vec4 uG;
float hsh(float n) { return fract(sin(n * 12.9898 + uF.y * 78.233) * 43758.5453); }
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
vec3 hue2rgb(float h) { return clamp(abs(mod(h * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0); }
vec3 spec(float t) {                                          // wavelength ramp: t -1 violet/blue .. +1 red
    float x = 0.5 * (t + 1.0);
    return vec3(smoothstep(0.45, 0.85, x) + 0.35 * smoothstep(0.2, 0.0, x),
                clamp(1.0 - abs(x - 0.5) * 2.4, 0.0, 1.0),
                smoothstep(0.6, 0.15, x));
}
vec2 P;  vec2 C;  vec2 SZ;  vec2 TANG;  float D;  float AR;  int MODE;
vec2 pos(float t) {
    if (MODE == 0) return P + uB.xy * D * t;
    if (MODE == 1) {
        vec2 v = P - C; float r = length(v);
        float rmax = 0.5 * length(SZ);
        return P + (r > 1e-4 ? v / r : vec2(0.0)) * D * pow(r / rmax, uC.z) * t;
    }
    float a = AR * t;                                           // Angle: channels rotated by Rotate * t
    vec2 v = P - C; float cs = cos(a), sn = sin(a);
    return C + vec2(cs * v.x - sn * v.y, sn * v.x + cs * v.y);
}
int SRC = 0;
vec4 tap(vec2 q) {
    if (SRC == 1) return texture(sTD2DInputs[1], q / SZ);
    if (SRC == 2) return texture(sTD2DInputs[2], q / SZ);
    return texture(sTD2DInputs[0], q / SZ);
}
vec4 blurred(float t, float b) {                               // box blur along the split direction, <= 8 taps
    vec2 q = pos(t);
    if (b <= 0.5) return tap(q);
    int n = int(clamp(ceil(b / 2.0), 2.0, 8.0));
    vec4 s = vec4(0.0);
    for (int k = 0; k < 8; k++) {
        if (k >= n) break;
        float u = (float(k) + 0.5) / float(n) * 2.0 - 1.0;
        s += tap(q + TANG * b * u);
    }
    return s / float(n);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    SZ = vec2(isz); P = vec2(p) + 0.5; C = uC.xy; MODE = int(uA.z + 0.5);
    float jf = 1.0;                                             // per-line jitter of the split size
    if (uE.y > 0.0) jf = 1.0 + uE.y * (2.0 * hsh(floor(P.y / max(uE.z, 1.0)) + 17.0 * uE.w) - 1.0);
    D = uA.w * uA.x * uF.x * jf;
    AR = uB.z * uA.x * uF.x * jf;
    TANG = uB.xy;
    if (MODE == 1) { vec2 v = P - C; TANG = length(v) > 1e-4 ? normalize(v) : vec2(1.0, 0.0); }
    if (MODE == 2) { vec2 v = P - C; TANG = length(v) > 1e-4 ? vec2(-v.y, v.x) / length(v) : vec2(1.0, 0.0); }
    int split = int(uA.y + 0.5);
    vec4 o = c;
    if (split == 3) {                                           // time split: each channel from its own frame
        SRC = int(uG.x + 0.5); o.r = blurred(1.0, uD.x).r;
        SRC = int(uG.y + 0.5); o.g = blurred(uB.w, uD.y).g;
        SRC = int(uG.z + 0.5); o.b = blurred(-1.0, uD.z).b;
        o.rgb = mix(c.rgb, o.rgb, uA.x);                          // Amount fades the time split in
    } else if (split == 0) {
        o.r = blurred(1.0, uD.x).r;
        o.g = blurred(uB.w, uD.y).g;
        o.b = blurred(-1.0, uD.z).b;
    } else if (split == 1) {
        vec3 base = blurred(uB.w, uD.y).rgb;
        float la = luma(blurred(1.0, uD.x).rgb), lb = luma(blurred(-1.0, uD.z).rgb);
        o.rgb = base + uD.w * (hue2rgb(uE.x) * la + hue2rgb(uE.x + 0.5) * lb);
    } else {
        int n = int(clamp(uC.w, 3.0, 16.0));
        vec3 acc = vec3(0.0), ws = vec3(0.0);
        for (int k = 0; k < 16; k++) {
            if (k >= n) break;
            float t = float(k) / float(n - 1) * 2.0 - 1.0;
            vec3 w = spec(t);
            acc += w * tap(pos(t)).rgb;
            ws += w;
        }
        o.rgb = acc / max(ws, vec3(1e-4));
    }
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
"""

P = "parent().par.{}.eval()"
AUDIO = ("(lambda c, n: float(c[n]) if c is not None and n and c[n] is not None else 0.0)"
         "(parent().par.Audiochop.eval(), parent().par.Audiochan.eval())")


MAPK = """// chroma time-split offset map (1x1, compute): grey m for the Time Machine = uK.x cooks back, clamped to the cooks
// the ring holds (stamp z), T-122 encoding m = 1 - (off + 1) / Depth. in0 = stamp. uK = k, Depth - 1.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uK;
void main() {
    float n = texelFetch(sTD2DInputs[0], ivec2(0), 0).z;
    float D = max(uK.y, 1.0);
    float off = clamp(uK.x, 0.0, min(D, n));
    float m = 1.0 - (off + 1.0) / (D + 1.0);
    TDImageStoreOutput(0, ivec3(0, 0, 0), vec4(m, m, m, 1.0));
}
"""

CDEPTH = 'max(2, 2 * int(parent().par.Delay.eval()) + 1)'
CHALF = "(0.5 if parent().par.Ringquality.eval() == 'half' else 1.0)"
TIME_ON = "parent().par.Split.eval() == 'time'"


def uniforms():
    """fx uniforms [(name, [x, y, z, w exprs])] (tested offline against SHADER)."""
    order = 'parent().par.Order.eval()'
    return [('uA', [P.format('Amount'), 'parent().par.Split.menuIndex', 'parent().par.Mode.menuIndex',
                    P.format('Distance')]),
            ('uB', ['math.cos(math.radians(%s))' % P.format('Angle'), 'math.sin(math.radians(%s))' % P.format('Angle'),
                    'math.radians(%s)' % P.format('Rotate'), P.format('Greenshift')]),
            ('uC', ['%s * me.inputs[0].width' % P.format('Centerx'), '%s * me.inputs[0].height' % P.format('Centery'),
                    P.format('Falloff'), P.format('Taps')]),
            ('uD', [P.format('Blurr'), P.format('Blurg'), P.format('Blurb'), P.format('Ghost')]),
            ('uE', [P.format('Hue'), P.format('Linejitter'), P.format('Linesize'),
                    'math.floor(absTime.seconds * %s)' % P.format('Linerate')]),
            ('uF', ['1.0 + %s * %s' % (P.format('Audiogain'), AUDIO), P.format('Seed'), '0', '0']),
            ('uG', ["%s.index('r')" % order, "%s.index('g')" % order, "%s.index('b')" % order, '0'])]


def build_time(m, H, in1):
    """Split time: ring (Texture 3D, Depth = 2 x Delay + 1) + stamp (cook counter) + map1 / map2 (1x1) -> tm1 / tm2
    (Time Machine, Delay and 2 x Delay cooks back) -> t1_sel / t2_sel (Switch: in1 unless Split = time, so the ring
    is only pulled while it is used)."""
    mk, expr = H['mk'], H['expr']
    ring = mk(m, texture3dTOP, 'ring')
    ring.inputConnectors[0].connect(in1)
    ring.par.type = 'texture3d'
    expr(ring.par.cachesize, CDEPTH)
    ring.par.step = 1
    ring.par.outputresolution = 'custom'
    expr(ring.par.resolutionw, "max(1, int(op('in1').width * %s))" % CHALF)
    expr(ring.par.resolutionh, "max(1, int(op('in1').height * %s))" % CHALF)
    ring.par.format = 'useinput'
    ring.comment = 'Time split ring: 2 x Delay + 1 frames (records only while Split = time pulls it).'
    st = H['compute'](m, 'stamp', STAMP_RING, [], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    H['uniforms'](st, [('uT', ['absTime.seconds',
                               "%s * 4 + (1 if parent().par.Ringquality.eval() == 'half' else 0)" % CDEPTH, '0', '0'])])
    st.comment = 'Cook counter: z = cooks since the ring restarted (bypass > 0.25 s / Delay / quality change).'
    sels = []
    for k in (1, 2):
        mp = H['compute'](m, 'map%d' % k, MAPK, [st], res=(1, 1), fmt='rgba32float')
        H['uniforms'](mp, [('uK', ['%d * int(parent().par.Delay.eval())' % k, '%s - 1' % CDEPTH, '0', '0'])])
        mp.comment = 'Offset map: %d x Delay cooks back, clamped to the stamp count (no stale frames).' % k
        tm = mk(m, timemachineTOP, 'tm%d' % k)
        tm.inputConnectors[0].connect(ring)
        tm.inputConnectors[1].connect(mp)
        expr(tm.par.blackoffset, '-(%s - 1)' % CDEPTH)
        tm.par.blackoffsetunit = 'indices'
        tm.par.whiteoffset = 0
        tm.par.whiteoffsetunit = 'indices'
        tm.par.samplemode = 'depthoffset'
        tm.par.outputresolution = 'custom'
        expr(tm.par.resolutionw, "op('in1').width")
        expr(tm.par.resolutionh, "op('in1').height")
        tm.comment = 'Frame %d x Delay cooks ago (whole cooks, T-122).' % k
        sw = mk(m, switchTOP, 't%d_sel' % k)
        sw.inputConnectors[0].connect(in1)
        sw.inputConnectors[1].connect(tm)
        expr(sw.par.index, '1 if %s and %s > 0 else 0' % (TIME_ON, P.format('Amount')))
        sw.comment = 'in1 unless Split = time (then the delayed frame): the ring cooks only while used.'
        sels.append(sw)
    return sels


def build(m, H):
    """in1 -> fx (one compute pass) -> out1."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    g = mk(m, glslTOP, 'fx')
    d = m.op('fx_compute')
    if d is None:
        d = mk(m, textDAT, 'fx_compute')
    d.text = SHADER
    d.dock = g
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    expr(g.par.resolutionw, 'me.inputs[0].width')
    expr(g.par.resolutionh, 'me.inputs[0].height')
    g.par.format = 'useinput'
    g.par.inputextenduv = 'hold'                     # edges hold, not black (T-108 (4))
    g.inputConnectors[0].connect(in1)
    t1, t2 = build_time(m, H, in1)
    g.inputConnectors[1].connect(t1)
    g.inputConnectors[2].connect(t2)
    U = uniforms()
    g.seq.vec.numBlocks = max(len(U), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)
    g.comment = ('chroma: RGB / prism / spectral / time split; Offset / Radial / Angle; Amount 0 = exact '
                 'passthrough.')
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2a Time split', 'role': 'process', 'ops': ['ring', 'stamp', 'stamp_compute', 'map1', 'map1_compute',
                                                             'tm1', 't1_sel', 'map2', 'map2_compute', 'tm2', 't2_sel'],
         'body': 'Split time: ring + cook counter -> Time Machines (Delay, 2 x Delay back); in1 otherwise.'},
        {'title': '2 Chroma', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'One compute pass; Audiochop/Audiochan (Inputs page) scale the distance.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
