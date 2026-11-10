# fx_glitch_ghost - FX_glitch module 'ghost' (FX4 D12 frame-difference "ghost destruction" + background plate
# subtract, Notch Frame Difference / Background Plate Subtract; FX0 row 77).
# Template: docs/builds/fx_glitch.md "Module template". `stamp` (1x1 clock + plate Capture edge) -> `state`: ONE
# compute pass with 4 rgba16float colour buffers in place (outputaccess readwrite, clearoutputs off; FX6 5a):
#   b0 = the output, b1 = the previous input frame, b2 = trail (rgb = colour of moving pixels, a = mask), b3 = plate.
# Mask = smoothstep(Threshold, Threshold + Softness, Gain x difference) against the previous frame (modes ghost /
# glow / trails) or the plate (mode plate). Modes: Ghost (only what moves, rest = Back), Glow (Tint x decaying motion
# mask added), Trails (moving pixels leave decaying copies over the Back), Plate (background subtract: what differs
# from the captured plate stays). View Mask = white-on-black mask (feed another module's Mask TOP). A > 0.25 s gap
# between cooks (bypass / panic / parked) restarts from the current frame (no stale flash). Amount 0 = `out_sel`
# picks in1 (exact, state not cooked). Mirror: builders/fx_glitch_ghost_logic.py. ASCII only.

MODULE = 'ghost'
MODES = ['ghost', 'glow', 'trails', 'plate']

PAGES = [
    ('Ghost', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'ghost', {'names': MODES, 'labels': ['Ghost (only motion)', 'Glow (motion lights up)',
                                                             'Trails (motion echoes)', 'Plate (background subtract)']}),
        ('View', 'Menu', 'composite', {'names': ['composite', 'mask'], 'labels': ['Composite', 'Mask (white)']}),
        ('Diff', 'Menu', 'rgb', {'names': ['rgb', 'luma'], 'labels': ['RGB max', 'Luma']}),
        ('Threshold', 'Float', 0.08, {'min': 0, 'max': 1, 'label': 'Threshold'}),
        ('Softness', 'Float', 0.05, {'min': 0, 'max': 0.5, 'label': 'Softness'}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Difference gain'}),
        ('Decay', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Trail decay (per 1/60 s)'}),
        ('Capture', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Capture plate (edge > 0.5)'}),
    ]),
    ('Look', [
        ('Back', 'Menu', 'black', {'names': ['black', 'dim', 'transparent'],
                                   'labels': ['Black', 'Dimmed picture', 'Transparent']}),
        ('Backdim', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Back dim'}),
        ('Glowgain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Glow gain'}),
        ('Tintr', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Tint red'}),
        ('Tintg', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Tint green'}),
        ('Tintb', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Tint blue'}),
    ]),
]
PANEL_PAGES = ['Ghost', 'Look']

# full-state presets (T-124 (1)): page defaults + the look, so a recall never inherits the previous preset's
# pars; edge triggers (Capture) are not stored.
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl
          if n not in ('Capture',))
PRESETS = [
    (1, 'ghost', dict(_D, **{'Amount': 1.0, 'Mode': 0, 'View': 0, 'Diff': 0, 'Threshold': 0.06, 'Softness': 0.05, 'Gain': 1.0,
                  'Decay': 0.9, 'Back': 0})),
    (2, 'motion glow', dict(_D, **{'Amount': 1.0, 'Mode': 1, 'View': 0, 'Diff': 1, 'Threshold': 0.04, 'Softness': 0.06,
                        'Gain': 2.0, 'Decay': 0.85, 'Glowgain': 1.5, 'Tintr': 0.3, 'Tintg': 0.9, 'Tintb': 1.0})),
    (3, 'echo trails', dict(_D, **{'Amount': 1.0, 'Mode': 2, 'View': 0, 'Diff': 0, 'Threshold': 0.06, 'Softness': 0.05,
                        'Gain': 1.0, 'Decay': 0.94, 'Back': 1, 'Backdim': 0.35})),
    (4, 'plate cutout', dict(_D, **{'Amount': 1.0, 'Mode': 3, 'View': 0, 'Diff': 0, 'Threshold': 0.12, 'Softness': 0.08,
                         'Gain': 1.0, 'Back': 2})),
    (5, 'motion mask', dict(_D, **{'Amount': 1.0, 'Mode': 0, 'View': 1, 'Diff': 1, 'Threshold': 0.05, 'Softness': 0.05,
                        'Gain': 1.5, 'Decay': 0.9})),
]

STATE = """// FX_glitch ghost state + output (compute, 4 x rgba16float in place). in0 = picture, in1 = stamp
// (1x1: x now, y previous cook, z last plate capture time). b0 out, b1 previous frame, b2 trail, b3 plate.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode, view, diff
uniform vec4 uB;   // threshold, softness, gain, decay per 1/60 s
uniform vec4 uC;   // back, backdim, glow gain, -
uniform vec4 uK;   // tint rgb, -
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    vec4 st = texelFetch(sTD2DInputs[1], ivec2(0), 0);
    bool fresh = st.y <= 0.0 || st.x - st.y > 0.25;
    bool grab = st.z == st.x;
    vec4 prev = fresh ? c : TDImageLoadOutput(1, ivec3(p, 0));
    vec4 trail = fresh ? vec4(0.0) : TDImageLoadOutput(2, ivec3(p, 0));
    vec4 plate = grab ? c : TDImageLoadOutput(3, ivec3(p, 0));
    float dt = fresh ? 0.0 : clamp(st.x - st.y, 0.0, 0.1);
    int mode = int(uA.y + 0.5);
    vec3 ref = mode == 3 ? plate.rgb : prev.rgb;
    vec3 dd = abs(c.rgb - ref);
    float d = int(uA.w + 0.5) == 0 ? max(dd.r, max(dd.g, dd.b)) : abs(luma(c.rgb) - luma(ref));
    float m = smoothstep(uB.x, uB.x + max(uB.y, 1e-5), d * uB.z);
    float k = dt > 0.0 ? pow(max(uB.w, 0.0), dt * 60.0) : 1.0;                   // no pow(0, 0)
    trail = vec4(max(trail.rgb * k, c.rgb * m), max(trail.a * k, m));
    int bm = int(uC.x + 0.5);
    vec4 back = bm == 0 ? vec4(0.0, 0.0, 0.0, c.a) : (bm == 1 ? vec4(c.rgb * uC.y, c.a) : vec4(0.0));
    vec4 o;
    if (mode == 1) o = vec4(c.rgb + uK.rgb * uC.z * trail.a, c.a);
    else if (mode == 2) o = vec4(max(back.rgb, trail.rgb), max(back.a, trail.a));
    else o = mix(back, c, m);
    if (int(uA.z + 0.5) == 1) o = vec4(vec3((mode == 1 || mode == 2) ? trail.a : m), 1.0);
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, o, uA.x));
    TDImageStoreOutput(1, ivec3(p, 0), c);
    TDImageStoreOutput(2, ivec3(p, 0), trail);
    TDImageStoreOutput(3, ivec3(p, 0), plate);
}
"""

STAMP = """// stamp: 1x1 rgba32float in place. x now, y previous cook, z last plate capture, w = 2 * count + edge bit.
// Capture on the first cook and on each Capture edge (> 0.5); the state pass grabs the plate when z == now.
layout (local_size_x = 1, local_size_y = 1) in;
uniform vec4 uT;   // now, capture value, -, -
void main() {
    vec4 s = TDImageLoadOutput(0, ivec3(0));
    float cnt = floor(s.w * 0.5);
    float pb = s.w - cnt * 2.0;
    float b = uT.y > 0.5 ? 1.0 : 0.0;
    float ct = s.z;
    if (s.x <= 0.0 || (b > 0.5 && pb < 0.5)) { ct = uT.x; cnt += 1.0; }
    TDImageStoreOutput(0, ivec3(0), vec4(uT.x, s.x, ct, cnt * 2.0 + b));
}
"""

P = "parent().par.{}.eval()"


def uniforms():
    """(stamp uniforms, state uniforms); pure, tested offline."""
    st = [('uT', ['absTime.seconds', P.format('Capture'), '0', '0'])]
    sv = [('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', 'parent().par.View.menuIndex',
                  'parent().par.Diff.menuIndex']),
          ('uB', [P.format('Threshold'), P.format('Softness'), P.format('Gain'), P.format('Decay')]),
          ('uC', ['parent().par.Back.menuIndex', P.format('Backdim'), P.format('Glowgain'), '0']),
          ('uK', [P.format('Tintr'), P.format('Tintg'), P.format('Tintb'), '0'])]
    return st, sv


def build(m, H):
    """Fill instance COMP m: in1 -> stamp -> state (4 buffers in place, b0 = out) -> out_sel (Amount 0 = in1) -> out1.
    The state op is created with its final layout before its first cook (T-151 (2): never toggle buffers live)."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    ust, usv = uniforms()
    st = H['compute'](m, 'stamp', STAMP, [], res=(1, 1), fmt='rgba32float')
    st.par.outputaccess = 'readwrite'
    st.par.clearoutputs = False
    H['uniforms'](st, ust)
    st.comment = 'Cook clock + plate capture: x now, y prev cook, z last capture (first cook / Capture edge).'
    g = m.op('state')
    fresh = g is None
    g = H['compute'](m, 'state', STATE, [in1, st], fmt='rgba16float')
    if fresh or g.par.numcolorbufs.eval() != 4 or g.par.outputaccess.eval() != 'readwrite':
        g.par.numcolorbufs = 4
        g.par.outputaccess = 'readwrite'
        g.par.clearoutputs = False
    H['uniforms'](g, usv)
    g.comment = 'ghost: b0 out, b1 previous frame, b2 trail, b3 plate (rgba16float, in place). D12.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(g)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exactly (state not cooked); else the state pass output (buffer 0).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Ghost', 'role': 'process', 'ops': ['stamp', 'stamp_compute', 'state', 'state_compute'],
         'body': 'One in-place pass: difference vs previous frame or plate -> mask -> mode; keeps prev/trail/plate.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]
