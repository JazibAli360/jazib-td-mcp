# gen_points_polytope4d - GEN_points module 'polytope4d' (FX7b TC-17, exsstas "4D geometry and transformations"):
# 4D shapes as point dust, rotated in the six planes of 4D space (XY XZ XW YZ YW ZW: angle + spin each, beat Kick
# turns XW / YW), then projected to 3D (perspective from w = Wdist, stereographic from the pole, orthographic, or a
# SLICE: only the points near the hyperplane w = Wslice, the 3D cross-section), then the engine's 3D orbit camera.
# Shapes: the regular polytopes 5-cell, tesseract (8-cell), 16-cell, 24-cell, 600-cell, 120-cell as edge dust (edge
# table in the `aux` Script TOP, built in Python only when Shape changes: gen_points_logic.p4_*), and the analytic
# Clifford torus, Hopf fibration (linked great circles) and the glome (3-sphere). GLSL state route (TC-17 suggested a
# Math Combine POP; this lane keeps positions in the state texture, no POP attributes / buffers, T-124). Stateless: the
# point is a pure function of index + module time (frame-exact, Speed 0 holds). Shared effectors push / dissolve the
# projected dust (PXE_POINTS; Effon off). Mirror: gen_points_logic.polytope4d_* / p4_*. ASCII only.
MODULE = 'polytope4d'
KIND = '3d'
BLURB = '4D polytopes / tori / glome as dust: 6-plane 4D rotation, then perspective / stereo / ortho / slice to 3D.'
SHAPES = ['5cell', 'tesseract', '16cell', '24cell', '600cell', '120cell', 'clifford', 'hopf', 'glome']
PROJS = ['perspective', 'stereo', 'ortho', 'slice']
COLORBY = ['w', 'element', 'along', 'random']
EFFECTORS = 'points'
EPOCH = '0'
CHECK = {'t': 1.0}
MIN_VISIBLE = {5: 0.03}                              # the slice preset shows a thin cross-section by design

PAGES = [('Polytope4d', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Shape', 'Menu', 'tesseract', {'names': SHAPES, 'labels': ['5-cell (simplex)', 'Tesseract (8-cell)', '16-cell',
                                                               '24-cell', '600-cell', '120-cell', 'Clifford torus',
                                                               'Hopf fibration', 'Glome (3-sphere)']}),
    ('Projection', 'Menu', 'perspective', {'names': PROJS, 'labels': ['Perspective (eye at w = Wdist)',
                                                                      'Stereographic (from the pole)', 'Orthographic',
                                                                      'Slice (cross-section at w = Wslice)']}),
    ('Wdist', 'Float', 2.5, {'min': 1.05, 'max': 20, 'label': '4D eye distance (perspective)'}),
    ('Worldsize', 'Float', 1.0, {'min': 0.05, 'max': 8, 'label': 'Size'}),
    ('Rxy', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle XY deg'}),
    ('Rxz', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle XZ deg'}),
    ('Rxw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle XW deg'}),
    ('Ryz', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle YZ deg'}),
    ('Ryw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle YW deg'}),
    ('Rzw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Angle ZW deg'}),
    ('Sxy', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Spin XY deg/s'}),
    ('Sxz', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Spin XZ deg/s'}),
    ('Sxw', 'Float', 20.0, {'min': -180, 'max': 180, 'label': 'Spin XW deg/s (turns inside out)'}),
    ('Syz', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Spin YZ deg/s'}),
    ('Syw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Spin YW deg/s'}),
    ('Szw', 'Float', 12.0, {'min': -180, 'max': 180, 'label': 'Spin ZW deg/s'}),
    ('Kick', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Beat pulse -> XW / YW turn deg'}),
    ('Flow', 'Float', 0.05, {'min': -4, 'max': 4, 'label': 'Dust flow along edges / circles per s'}),
    ('Edgejitter', 'Float', 0.0, {'min': 0, 'max': 0.5, 'label': 'Dust thickness (4D jitter)'}),
    ('Torusratio', 'Float', 0.7071, {'min': 0, 'max': 1, 'label': 'Clifford torus radius ratio'}),
    ('Fibers', 'Int', 48, {'min': 1, 'max': 4096, 'label': 'Hopf fibers (circles)'}),
    ('Hopfrings', 'Int', 4, {'min': 1, 'max': 64, 'label': 'Hopf base rings (latitudes)'}),
    ('Wslice', 'Float', 0.0, {'min': -1.5, 'max': 1.5, 'label': 'Slice position w'}),
    ('Slicewidth', 'Float', 0.08, {'min': 0.001, 'max': 2, 'label': 'Slice width'}),
    ('Wfade', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Dim the far side in w'}),
    ('Colorby', 'Menu', 'w', {'names': COLORBY, 'labels': ['4D depth w', 'Element (edge / circle)', 'Along the edge',
                                                           'Random']}),
])]
DEFAULTS = {'Count': 65536, 'Persist': 0.0, 'Tonemap': 0, 'Palette': 6, 'Orbit': 6.0, 'Pitch': -15.0,
            'Distance': 4.0, 'Intensity': 1.0, 'Size': 1.0, 'Glow': 0.0, 'Exposure': -1.0, 'Normalize': 0}
PANEL_PAGES = ['Polytope4d', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'tesseract turn', {'Shape': 1, 'Projection': 0, 'Sxw': 20.0, 'Szw': 12.0, 'Colorby': 0, 'Palette': 6,
                           'Count': 65536, 'Exposure': -1.5, 'Worldsize': 0.8}),
    (2, '24-cell slow', {'Shape': 3, 'Projection': 0, 'Sxw': 10.0, 'Syw': 7.0, 'Sxy': 4.0, 'Szw': 0.0,
                         'Colorby': 1, 'Palette': 4, 'Count': 65536, 'Edgejitter': 0.004, 'Exposure': -1.0,
                         'Worldsize': 0.9}),
    (3, 'hopf links', {'Shape': 7, 'Projection': 1, 'Fibers': 64, 'Hopfrings': 4, 'Sxw': 8.0, 'Szw': 0.0,
                       'Syz': 6.0, 'Worldsize': 0.6, 'Colorby': 1, 'Palette': 5, 'Count': 65536, 'Flow': 0.1,
                       'Exposure': -0.5}),
    (4, 'clifford breathe', {'Shape': 6, 'Projection': 1, 'Torusratio': 0.7071, 'Sxw': 15.0, 'Szw': 0.0,
                             'Syw': 9.0, 'Worldsize': 0.6, 'Colorby': 2, 'Palette': 3, 'Count': 65536,
                             'Exposure': 0.0}),
    (5, '120-cell slice', {'Shape': 5, 'Projection': 3, 'Slicewidth': 0.12, 'Sxw': 6.0, 'Syw': 4.0, 'Szw': 0.0,
                           'Colorby': 0, 'Palette': 6, 'Count': 131072, 'Exposure': 1.5, 'Kick': 20.0,
                           'Beatevery': 1.0, 'Beatgain': 1.0}),
]
UNIFORMS = [('uM0', ['{Shape#}', '{Projection#}', '{Wdist}', '{Worldsize}']),
            ('uM1', ['{Rxy}', '{Rxz}', '{Rxw}', '{Ryz}']),
            ('uM2', ['{Ryw}', '{Rzw}', '{Kick}', '{Colorby#}']),
            ('uM3', ['{Sxy}', '{Sxz}', '{Sxw}', '{Syz}']),
            ('uM4', ['{Syw}', '{Szw}', '{Flow}', '{Edgejitter}']),
            ('uM5', ['{Torusratio}', '{Fibers}', '{Hopfrings}', '{Slicewidth}']),
            ('uM6', ['{Wslice}', '{Wfade}', '0', '0'])]

AUX_SCRIPT = """# GEN_points polytope4d edge table (builders/gen_points_polytope4d.py; maths gen_points_logic.p4_*).
# Cooks only when Shape changes (TD tracks the par read below): vertices + edges in numpy, then one upload.
_P4 = {}

def onSetupParameters(scriptOp):
	return

def onCook(scriptOp):
	import numpy as np
	if not _P4:
		exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/gen_points_logic.py').read(), _P4)
	m = scriptOp.parent()
	scriptOp.copyNumpyArray(np.ascontiguousarray(_P4['p4_table'](m.par.Shape.eval()), dtype=np.float32))
	return
"""

STEP = """
const int P4_POLY = 6;                                  // shapes below this use the aux edge table
vec4 p4Tex(int q) { return texelFetch(GP_AUX, ivec2(q - (q / 1024) * 1024, q / 1024), 0); }
vec4 p4Rotate(vec4 p) {
    float sp = T * (1.0 + LEVEL);
    float kk = uM2.z * ENV;
    vec3 a1 = radians(uM1.xyz + uM3.xyz * sp + vec3(0.0, 0.0, kk));                          // xy xz xw
    vec3 a2 = radians(vec3(uM1.w, uM2.x, uM2.y) + vec3(uM3.w, uM4.x, uM4.y) * sp + vec3(0.0, kk, 0.0));  // yz yw zw
    p.xy = rot2(p.xy, a1.x);
    p.xz = rot2(p.xz, a1.y);
    p.xw = rot2(p.xw, a1.z);
    p.yz = rot2(p.yz, a2.x);
    p.yw = rot2(p.yw, a2.y);
    p.zw = rot2(p.zw, a2.z);
    return p;
}
vec4 p4Base(int i, out float el, out float al) {
    int sh = int(uM0.x + 0.5);
    el = 0.0; al = 0.0;
    if (sh < P4_POLY) {
        int E = int(p4Tex(0).x + 0.5);
        if (E < 1) return vec4(0.0);
        int per = max(NPTS / E, 1);
        int e = i / per;
        float t;
        if (e < E) t = (float(i - e * per) + rnd(i, 31u)) / float(per);
        else { e = i - (i / E) * E; t = rnd(i, 32u); }
        t = fract(t + uM4.z * T);
        el = (float(e) + 0.5) / float(E);
        al = t;
        vec4 p = mix(p4Tex(1 + 2 * e), p4Tex(2 + 2 * e), t);
        return p + (vec4(rnd3(i, 33u), rnd(i, 36u)) * 2.0 - 1.0) * uM4.w;
    }
    if (sh == 6) {                                       // Clifford torus: (r cos a, r sin a, s cos b, s sin b)
        int n = max(int(ceil(sqrt(float(NPTS)))), 1);
        int ib = i / n, ia = i - ib * n;
        float a = TAU * ((float(ia) + 0.5) / float(n) + uM4.z * T), b = TAU * (float(ib) + 0.5) / float(n);
        float r = clamp(uM5.x, 0.0, 1.0), s = sqrt(max(1.0 - r * r, 0.0));
        el = (float(ib) + 0.5) / float(n); al = fract(a / TAU);
        return vec4(r * cos(a), r * sin(a), s * cos(b), s * sin(b));
    }
    if (sh == 7) {                                       // Hopf fibration: great circle over each base point
        int F = max(int(uM5.y + 0.5), 1), R = clamp(int(uM5.z + 0.5), 1, F);
        int per = max(NPTS / F, 1);
        int f = min(i / per, F - 1);
        int fpr = (F + R - 1) / R;
        int j = f / fpr, m = f - j * fpr;
        float th = PI * (float(j) + 0.5) / float(R);
        float ph = TAU * float(m) / float(fpr) + 0.5 * float(j);
        float ps = TAU * ((float(i - f * per) + rnd(i, 37u)) / float(per) + uM4.z * T);
        el = (float(f) + 0.5) / float(F); al = fract(ps / TAU);
        float c = cos(0.5 * th), s = sin(0.5 * th);
        return vec4(c * cos(ps), c * sin(ps), s * cos(ps + ph), s * sin(ps + ph));
    }
    vec3 u = rnd3(i, 41u);                               // glome: uniform on the unit 3-sphere
    float s = sqrt(u.x), c = sqrt(1.0 - u.x);
    el = rnd(i, 5u); al = u.x;
    return vec4(s * cos(TAU * u.y), s * sin(TAU * u.y), c * cos(TAU * u.z), c * sin(TAU * u.z));
}
vec3 p4Project(vec4 q, out float vis) {
    int pm = int(uM0.y + 0.5);
    vis = 1.0;
    vec3 x = q.xyz;
    if (pm == 0) { float d = uM0.z - q.w; if (d <= 1e-3) { vis = 0.0; return vec3(0.0); } x *= uM0.z / d; }
    else if (pm == 1) { float d = 1.0 - q.w; if (d <= 0.02) { vis = 0.0; return vec3(0.0); } x /= d; }
    else if (pm == 3) vis = clamp(1.0 - abs(q.w - uM6.x) / max(uM5.w, 1e-6), 0.0, 1.0);
    return x * uM0.w;
}
vec4 p4_eval(int i) {
    float el, al, vis;
    vec4 q = p4Rotate(p4Base(i, el, al));
    vec3 P = p4Project(q, vis);
    float a = vis * (1.0 - uM6.y * (0.5 - 0.5 * clamp(q.w, -1.0, 1.0)));
#ifdef PXE_POINTS
    PXEFx fx = pxePointFx(P, float(i));
    P += fx.off;
    a *= fx.alpha;
#endif
    int cb = int(uM2.w + 0.5);
    float k = cb == 0 ? clamp(0.5 + 0.5 * q.w, 0.0, 0.999) : (cb == 1 ? el : (cb == 2 ? al : rnd(i, 5u)));
    return vec4(P, packKA(k, a));
}
vec4 pt_seed(int i) { return p4_eval(i); }
vec4 pt_step(int i, vec4 s, float dt) { return p4_eval(i); }
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    P = s.xyz;
    float a = unpackA(s.w);
    C = vec4(ptpal(unpackK(s.w)), a);
    return a > 0.0;
}
"""
