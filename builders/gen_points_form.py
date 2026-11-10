# gen_points_form - GEN_points module 'form' (FX4 G-FORM, Trapcode Form look): a grid of points (box with Layers,
# Fibonacci sphere shells, cylinder, plane) displaced every frame by a fractal field (scalar fbm along the normal, or
# PX's 3D curl noise), the slot input's luma (layer map), random Disperse (+ beat pulse Kick) and Twist around y;
# colour by displacement / depth / height / index / the input picture (layer colour). Stateless: positions are a pure
# function of the index and time (no drift, frame-exact). Shared effectors = Form's spherical field and more: per-point
# push / dissolve (reveal) / scale near effectors (PXE_POINTS, Effon default off). Mirror: gen_points_logic.form_*.
MODULE = 'form'
KIND = '3d'
BLURB = 'Grid / sphere / cylinder / plane of points displaced by fractal noise, picture luma, disperse, twist.'
SHAPES = ['box', 'sphere', 'cylinder', 'plane', 'clip']
COLORBY = ['displacement', 'depth', 'height', 'index', 'input']
EFFECTORS = 'points'
EPOCH = '0'

PAGES = [('Form', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Shape', 'Menu', 'box', {'names': SHAPES, 'labels': ['Box grid (Layers)', 'Sphere shells', 'Cylinder',
                                                         'Plane', 'Clip (plane in the input aspect, TC-20)']}),
    ('Layers', 'Int', 8, {'min': 1, 'max': 64, 'label': 'Layers (z / shells)'}),
    ('Sizex', 'Float', 1.0, {'min': 0.05, 'max': 8, 'label': 'Size x (world)'}),
    ('Sizey', 'Float', 1.8, {'min': 0.05, 'max': 8, 'label': 'Size y'}),
    ('Sizez', 'Float', 0.6, {'min': 0, 'max': 8, 'label': 'Size z'}),
    ('Fractal', 'Float', 0.15, {'min': 0, 'max': 2, 'label': 'Fractal displacement (world)'}),
    ('Freq', 'Float', 2.0, {'min': 0.05, 'max': 16, 'label': 'Fractal frequency'}),
    ('Octaves', 'Int', 3, {'min': 1, 'max': 6, 'label': 'Octaves'}),
    ('Flow', 'Float', 0.2, {'min': -4, 'max': 4, 'label': 'Flow (z per s)'}),
    ('Evolve', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Evolve speed'}),
    ('Dispmode', 'Menu', 'normal', {'names': ['normal', 'curl'], 'labels': ['Scalar along normal', 'Curl xyz']}),
    ('Mapdisp', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Input luma displacement'}),
    ('Disperse', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Disperse (random)'}),
    ('Twist', 'Float', 0.0, {'min': -720, 'max': 720, 'label': 'Twist deg (top vs centre)'}),
    ('Colorby', 'Menu', 'displacement', {'names': COLORBY, 'labels': ['Displacement', 'Depth', 'Height', 'Index',
                                                                     'Input picture']}),
    ('Kick', 'Float', 0.0, {'min': 0, 'max': 8, 'label': 'Beat pulse -> disperse'}),
    ('Rise', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Rise toward the camera by brightness (world)'}),
    ('Risespeed', 'Float', 0.25, {'min': 0, 'max': 4, 'label': 'Rise cycles per s'}),
    ('Risethreshold', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Rise threshold (input luma)'}),
    ('Risecurl', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Curl spread while rising'}),
])]
DEFAULTS = {'Count': 65536, 'Persist': 0.0, 'Tonemap': 0, 'Palette': 6, 'Orbit': 8.0, 'Pitch': -15.0,
            'Distance': 4.2, 'Intensity': 1.0, 'Size': 2.0, 'Glow': 0.6, 'Exposure': -1.5, 'Spread': 2.0}
PANEL_PAGES = ['Form', 'Points', 'Look', 'View', 'Drive']
PRESETS = [
    (1, 'form grid', {'Shape': 0, 'Layers': 8, 'Fractal': 0.15, 'Freq': 2.0, 'Colorby': 0, 'Palette': 6,
                      'Count': 65536, 'Pitch': -15.0, 'Orbit': 8.0}),
    (2, 'sphere shells', {'Shape': 1, 'Layers': 6, 'Sizex': 1.0, 'Fractal': 0.2, 'Dispmode': 0, 'Colorby': 0,
                          'Palette': 4, 'Count': 65536, 'Orbit': 10.0}),
    (3, 'curl cloud', {'Shape': 0, 'Layers': 16, 'Sizez': 1.0, 'Fractal': 0.25, 'Dispmode': 1, 'Freq': 1.5,
                       'Colorby': 1, 'Palette': 5, 'Count': 65536, 'Persist': 0.5}),
    (4, 'picture terrain', {'Shape': 3, 'Layers': 1, 'Mapdisp': 0.4, 'Fractal': 0.05, 'Colorby': 4,
                            'Count': 65536, 'Pitch': -55.0, 'Orbit': 0.0, 'Sizex': 1.1, 'Sizey': 1.9}),
    (5, 'twist beat', {'Shape': 2, 'Layers': 4, 'Sizex': 0.9, 'Twist': 180.0, 'Fractal': 0.1, 'Colorby': 2,
                       'Palette': 6, 'Count': 65536, 'Kick': 0.15, 'Beatevery': 1.0, 'Beatgain': 1.0,
                       'Disperse': 0.01}),
    # TC-20 video to particles (lane G): the clip as a point plane, bright points rise toward the camera and curl,
    # Persist draws their trails (rack Input = test clip, or wire any clip into the rack)
    (6, 'video particles', {'Shape': 4, 'Layers': 1, 'Sizey': 1.9, 'Mapdisp': 0.25, 'Fractal': 0.0, 'Colorby': 4,
                            'Rise': 1.6, 'Risespeed': 0.25, 'Risethreshold': 0.35, 'Risecurl': 0.35,
                            'Count': 131072, 'Pitch': -8.0, 'Orbit': 0.0, 'Distance': 3.2, 'Persist': 0.6,
                            'Size': 1.0, 'Glow': 0.3, 'Exposure': -1.0, 'Blend': 0}),
]
UNIFORMS = [('uM0', ['{Shape#}', '{Layers}', '{Sizex}', '{Sizey}']),
            ('uM1', ['{Sizez}', '{Fractal}', '{Freq}', '{Octaves}']),
            ('uM2', ['{Flow}', '{Evolve}', '{Dispmode#}', '{Mapdisp}']),
            ('uM3', ['{Disperse}', '{Twist}', '{Colorby#}', '{Kick}']),
            ('uM4', ['{Rise}', '{Risespeed}', '{Risethreshold}', '{Risecurl}'])]

COMMON = """
void fm_base(int i, out vec3 uvw, out vec3 B, out vec3 N) {
    int L = max(int(uM0.y + 0.5), 1);
    int sh = int(uM0.x + 0.5);
    int m = max((NPTS + L - 1) / L, 1);
    int layer = i / m;
    int j = i - layer * m;
    float w = L > 1 ? float(layer) / float(L - 1) : 0.5;
    vec3 S = vec3(uM0.z, uM0.w, uM1.x);
    if (sh == 1) {
        float z = 1.0 - 2.0 * (float(j) + 0.5) / float(m);
        float r = sqrt(max(0.0, 1.0 - z * z));
        float ph = float(j) * 2.39996323;
        N = vec3(r * cos(ph), z, r * sin(ph));
        B = N * (0.5 * S.x * (L > 1 ? 0.5 + 0.5 * w : 1.0));
        uvw = vec3(fract(ph / TAU), z * 0.5 + 0.5, w);
        return;
    }
    float gw = sh == 4 ? S.y * ASP : S.x;
    int gx = max(int(sqrt(float(m) * gw / max(S.y, 1e-3)) + 0.5), 1);
    int gy = (m + gx - 1) / gx;
    int ix = j - (j / gx) * gx, iy = j / gx;
    float u = gx > 1 ? float(ix) / float(gx - 1) : 0.5;
    float v = gy > 1 ? float(iy) / float(gy - 1) : 0.5;
    uvw = vec3(u, v, w);
    if (sh == 2) {
        float a = TAU * float(ix) / float(gx);
        N = vec3(cos(a), 0.0, sin(a));
        float rs = L > 1 ? 0.6 + 0.4 * w : 1.0;
        B = vec3(N.x * 0.5 * S.x * rs, (v - 0.5) * S.y, N.z * 0.5 * S.x * rs);
        return;
    }
    N = vec3(0.0, 0.0, 1.0);
    if (sh == 4) { B = vec3((u - 0.5) * S.y * ASP, (v - 0.5) * S.y, 0.0); return; }   // clip: input aspect
    B = vec3((u - 0.5) * S.x, (v - 0.5) * S.y, sh == 3 ? 0.0 : (w - 0.5) * S.z);
}
"""

STEP = """
vec4 fm_eval(int i) {
    vec3 uvw, B, N;
    fm_base(i, uvw, B, N);
    float te = T * uM2.y;
    int oct = clamp(int(uM1.w + 0.5), 1, 6);
    float amp = uM1.y * (1.0 + LEVEL);
    vec3 D;
    float kd;
    if (int(uM2.z + 0.5) == 0) {
        float f = pxFbm(B * uM1.z + vec3(te * 0.61, te * 0.37, uM2.x * T), oct, SEED);
        kd = f;
        D = N * ((f - 0.5) * 2.0 * amp);
    } else {
        vec3 c = pxCurl(B * uM1.z + vec3(0.0, 0.0, uM2.x * T), te, min(oct, 4));
        D = c * amp;
        kd = clamp(length(c) * 0.5, 0.0, 1.0);
    }
    if (uM2.w != 0.0) D += N * (lum(textureLod(GP_IN, uvw.xy, 0.0).rgb) * uM2.w);
    D += (rnd3(i, 51u) * 2.0 - 1.0) * uM3.x * (1.0 + uM3.w * ENV);
    float fa = 1.0;
    if (uM4.x != 0.0) {                                  // TC-20: bright points rise toward the camera and curl
        float g = smoothstep(uM4.z, 1.0, lum(textureLod(GP_IN, uvw.xy, 0.0).rgb));
        float ph = fract(T * uM4.y * (0.5 + rnd(i, 57u)) + rnd(i, 58u)) * g;
        D += N * (uM4.x * ph) + pxCurl(B * 2.0 + vec3(0.0, 0.0, 0.37 * T), T * 0.5, 2) * (uM4.w * ph);
        fa = 1.0 - ph * ph * ph * ph;
    }
    vec3 P = B + D;
    P.xz = rot2(P.xz, radians(uM3.y) * (P.y / max(0.5 * uM0.w, 1e-3)));
    float a = fa;
#ifdef PXE_POINTS
    PXEFx fx = pxePointFx(P, float(i));
    P += fx.off;
    a *= fx.alpha;
#endif
    int cb = int(uM3.z + 0.5);
    float k = cb == 0 ? kd : (cb == 1 ? P.z / max(uM1.x, 1e-3) + 0.5 : (cb == 2 ? P.y / max(uM0.w, 1e-3) + 0.5 : rnd(i, 5u)));
    return vec4(P, packKA(k, a));
}
vec4 pt_seed(int i) { return fm_eval(i); }
vec4 pt_step(int i, vec4 s, float dt) { return fm_eval(i); }
"""

PLACE = """
bool pt_place(int i, vec4 s, out vec3 P, out vec4 C) {
    P = s.xyz;
    vec3 col;
    if (int(uM3.z + 0.5) == 4) { vec3 uvw, B, N; fm_base(i, uvw, B, N); col = textureLod(GP_IN, uvw.xy, 0.0).rgb; }
    else col = ptpal(unpackK(s.w));
    C = vec4(col, unpackA(s.w));
    return true;
}
"""
