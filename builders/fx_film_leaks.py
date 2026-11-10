# fx_film_leaks - FX_film module 'leaks' (FX3 F7): light leaks and film burn, one compute pass.
# Leak: 1-4 soft blobs pinned to an Edge (left / right / top / bottom / corner / centre), drifting along it, warped
# by fbm, coloured from a 3-colour ramp (edge colour -> mid -> hot core), screen / add / lighten over the picture.
# Burn: a front grows from the Burn origin (distance field / farthest corner + Warp x (fbm - 0.5)): behind it the
# white-hot core, a coloured band (Burnwidth), then a charred darkening (Charwidth) before the untouched picture.
# Drive: Envmode continuous (Level, optional Breathe) or triggered (Trigger pulse -> Hittime, Attack / Hold / Release
# envelope x Level: a beat or cue fires a sweep / burn). No flash cap (user rule 26 Oct). Maths: fx_film_logic
# (envelope, burn_field, burn_fraction; fbm = the rack's lowbias32 value noise, exact in uint32). Amount 0 = exact.

MODULE = 'leaks'

PAGES = [
    ('Leaks', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'leak', {'names': ['leak', 'burn', 'both'], 'labels': ['Light leak', 'Film burn', 'Both']}),
        ('Intensity', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Intensity'}),
        ('Blend', 'Menu', 'screen', {'names': ['screen', 'add', 'lighten'], 'labels': ['Screen', 'Add', 'Lighten']}),
        ('Edge', 'Menu', 'left', {'names': ['left', 'right', 'top', 'bottom', 'corner', 'centre'],
                                  'labels': ['Left', 'Right', 'Top', 'Bottom', 'Corner (top left)', 'Centre wash']}),
        ('Position', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Position along edge'}),
        ('Size', 'Float', 0.45, {'min': 0.05, 'max': 1.5, 'label': 'Size (frame heights)'}),
        ('Softness', 'Float', 1.0, {'min': 0.2, 'max': 3, 'label': 'Softness'}),
        ('Blobs', 'Int', 3, {'min': 1, 'max': 4, 'label': 'Blobs'}),
        ('Drift', 'Float', 0.15, {'min': 0, 'max': 0.5, 'label': 'Drift'}),
        ('Speed', 'Float', 0.3, {'min': 0, 'max': 3, 'label': 'Speed'}),
        ('Warp', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'Noise warp'}),
        ('Noisescale', 'Float', 3.0, {'min': 0.5, 'max': 12, 'label': 'Noise scale'}),
        ('Color1', 'RGB', (1.0, 0.92, 0.7), {'label': 'Hot core'}),
        ('Color2', 'RGB', (1.0, 0.45, 0.1), {'label': 'Mid'}),
        ('Color3', 'RGB', (0.75, 0.05, 0.3), {'label': 'Edge'}),
        ('Freeze', 'Toggle', False, {'label': 'Freeze time'}),
        ('Phase', 'Float', 0.0, {'min': 0, 'max': 100, 'label': 'Time phase'}),
        ('Seed', 'Int', 7, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
    ('Burn', [
        ('Level', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Level (front / leak gain)'}),
        ('Burnwidth', 'Float', 0.06, {'min': 0.005, 'max': 0.3, 'label': 'Burn band width'}),
        ('Charwidth', 'Float', 0.02, {'min': 0, 'max': 0.2, 'label': 'Char edge width'}),
        ('Posx', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Burn origin x'}),
        ('Posy', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Burn origin y'}),
    ]),
    ('Trigger', [
        ('Envmode', 'Menu', 'continuous', {'names': ['continuous', 'triggered'], 'labels': ['Continuous', 'Triggered']}),
        ('Breathe', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Breathe (continuous)'}),
        ('Trigger', 'Pulse', None, {'label': 'Trigger'}),
        ('Attack', 'Float', 0.1, {'min': 0, 'max': 4, 'label': 'Attack s'}),
        ('Hold', 'Float', 0.5, {'min': 0, 'max': 30, 'label': 'Hold s'}),
        ('Release', 'Float', 0.8, {'min': 0, 'max': 8, 'label': 'Release s'}),
        ('Hittime', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Last trigger (absTime s)'}),
    ]),
]
PANEL_PAGES = ['Leaks', 'Burn']

PRESETS = [
    (1, 'edge warm', {'Amount': 1.0, 'Mode': 0, 'Intensity': 1.0, 'Blend': 0, 'Edge': 0, 'Position': 0.6,
                      'Size': 0.45, 'Blobs': 3, 'Drift': 0.15, 'Speed': 0.3, 'Level': 0.8, 'Envmode': 0,
                      'Breathe': 0.3}),
    (2, 'corner magenta', {'Amount': 1.0, 'Mode': 0, 'Intensity': 1.2, 'Blend': 0, 'Edge': 4, 'Size': 0.6,
                           'Blobs': 2, 'Color1r': 1.0, 'Color1g': 0.8, 'Color1b': 0.9, 'Color2r': 1.0, 'Color2g': 0.2,
                           'Color2b': 0.55, 'Color3r': 0.4, 'Color3g': 0.0, 'Color3b': 0.5, 'Level': 0.9,
                           'Envmode': 0}),
    (3, 'full wash', {'Amount': 1.0, 'Mode': 0, 'Intensity': 0.8, 'Blend': 0, 'Edge': 5, 'Size': 1.0, 'Blobs': 4,
                      'Drift': 0.3, 'Speed': 0.5, 'Softness': 2.0, 'Level': 0.7, 'Envmode': 0, 'Breathe': 0.5}),
    (4, 'burn flash', {'Amount': 1.0, 'Mode': 1, 'Intensity': 1.2, 'Level': 1.0, 'Burnwidth': 0.08,
                       'Charwidth': 0.03, 'Warp': 0.35, 'Posx': 0.5, 'Posy': 0.5, 'Envmode': 1, 'Attack': 0.6,
                       'Hold': 0.2, 'Release': 0.6}),
    (5, 'beat sweep', {'Amount': 1.0, 'Mode': 0, 'Intensity': 1.5, 'Blend': 1, 'Edge': 1, 'Size': 0.7, 'Blobs': 2,
                       'Level': 1.0, 'Envmode': 1, 'Attack': 0.05, 'Hold': 0.1, 'Release': 0.5}),
]

SHADER = """// FX_film leaks (compute). in0 = picture. uv: 0..1, y up.
// uA amount mode intensity blend | uB edge position size softness | uC time drift warp blobs
// uD env burnwidth charwidth noisescale | uE posx posy seed aspect | uF/uG/uH colours 1 2 3 (rgb)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;
uniform vec4 uB;
uniform vec4 uC;
uniform vec4 uD;
uniform vec4 uE;
uniform vec4 uF;
uniform vec4 uG;
uniform vec4 uH;
%s
vec3 ramp(float t) { t = clamp(t, 0.0, 1.0); return t < 0.5 ? mix(uH.rgb, uG.rgb, t * 2.0) : mix(uG.rgb, uF.rgb, t * 2.0 - 1.0); }
vec2 anchor(int e, float pos) {
    if (e == 0) return vec2(0.0, pos);
    if (e == 1) return vec2(1.0, pos);
    if (e == 2) return vec2(pos, 1.0);
    if (e == 3) return vec2(pos, 0.0);
    if (e == 4) return vec2(0.0, 1.0) + 0.25 * vec2(pos - 0.5, 0.5 - pos);
    return vec2(0.5) + 0.3 * vec2(pos - 0.5, 0.0);
}
vec3 leak(vec2 uv, float t, uint seed) {
    float asp = uE.w;
    vec2 w = vec2(fbm(uv * uD.w + 0.1 * t, seed + 11u, 3), fbm(uv * uD.w + 5.2 + 0.1 * t, seed + 23u, 3)) - 0.5;
    vec2 q = uv + uC.z * 0.3 * w;
    int e = int(uB.x + 0.5), nb = int(clamp(uC.w, 1.0, 4.0));
    float v = 0.0;
    for (int b = 0; b < 4; b++) {
        if (b >= nb) break;
        float hb = hsh(ivec2(b, 3), seed);
        float pos = uB.y + uC.y * sin(t * (0.7 + 0.37 * float(b)) + 6.2831853 * hb) + (float(b) - 0.5 * float(nb - 1)) * 0.25 * uB.z;
        vec2 a = anchor(e, pos);
        float r = uB.z * (0.6 + 0.4 * hsh(ivec2(b, 7), seed));
        vec2 d = (q - a) * vec2(asp, 1.0);
        v += exp(-dot(d, d) / (r * r) * (2.0 / max(uB.w, 0.05)));
    }
    v = min(v, 1.5);
    return ramp(v) * v;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    vec2 uv = (vec2(p) + 0.5) / vec2(isz);
    float t = uC.x, env = uD.x, asp = uE.w;
    uint seed = uint(uE.z);
    int mode = int(uA.y + 0.5), bl = int(uA.w + 0.5);
    vec3 o = c.rgb;
    if (mode != 1) {
        vec3 L = leak(uv, t, seed) * (uA.z * env);
        vec3 lo = bl == 0 ? o + (1.0 - min(o, vec3(1.0))) * L : (bl == 1 ? o + L : max(o, L));
        o = mix(o, lo, uA.x);
    }
    if (mode != 0) {                                             // fx_film_logic.burn_field / burn_fraction
        vec2 org = uE.xy;
        float far = 0.0;
        for (int k = 0; k < 4; k++) { vec2 cn = vec2(float(k & 1), float(k >> 1)); far = max(far, length((cn - org) * vec2(asp, 1.0))); }
        float tb = 0.1 * t;
        float f = length((uv - org) * vec2(asp, 1.0)) / far
                + uC.z * (fbm(vec2(uv.x * uD.w * asp + tb, uv.y * uD.w + 0.37 * tb), seed, 3) - 0.5);
        float bw = uD.y, cw = uD.z;
        float front = env * (1.0 + bw + uC.z);
        vec3 b = o;
        if (f < front - bw) b = uF.rgb * uA.z;
        else if (f < front) b = mix(uF.rgb, uG.rgb, (f - (front - bw)) / bw) * uA.z;
        else if (f < front + cw) b = o * mix(0.15, 1.0, (f - front) / max(cw, 1e-5));
        o = mix(o, b, uA.x);
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(o, c.a));
}
"""

PULSE_EXEC = """# Trigger pulse -> Hittime (absTime.seconds); the shader's envelope reads it (no per-frame Python).
def onPulse(par):
    if par.name == 'Trigger':
        par.owner.par.Hittime.val = absTime.seconds
    return
"""

TIME = "(%s if parent().par.Freeze.eval() else absTime.seconds * %s + %s)" % (
    "parent().par.Phase.eval()", "parent().par.Speed.eval()", "parent().par.Phase.eval()")
ENV = ("(lambda lv, cont, br, d, a, h, r: lv * ((1.0 - br * (0.5 + 0.5 * math.sin(absTime.seconds * 1.5707963)))"
       " if cont else (0.0 if d < 0 else (d / max(a, 1e-4) if d < a else (1.0 if d < a + h else"
       " max(0.0, 1.0 - (d - a - h) / max(r, 1e-4)))))))"
       "(parent().par.Level.eval(), parent().par.Envmode.eval() == 'continuous', parent().par.Breathe.eval(),"
       " (absTime.seconds - parent().par.Hittime.eval()) if parent().par.Hittime.eval() >= 0 else -1.0,"
       " parent().par.Attack.eval(), parent().par.Hold.eval(), parent().par.Release.eval())")


def shaders(H):
    return {'fx': SHADER % H['LIB']}


def build(m, H):
    """in1 -> fx (one compute pass) -> out1, + pulse_exec (Trigger -> Hittime)."""
    mk, P = H['mk'], H['P']
    in1 = mk(m, inTOP, 'in1')
    g = H['compute'](m, 'fx', shaders(H)['fx'], [in1])
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Intensity'),
                'parent().par.Blend.menuIndex']),
        ('uB', ['parent().par.Edge.menuIndex', P.format('Position'), P.format('Size'), P.format('Softness')]),
        ('uC', [TIME, P.format('Drift'), P.format('Warp'), P.format('Blobs')]),
        ('uD', [ENV, P.format('Burnwidth'), P.format('Charwidth'), P.format('Noisescale')]),
        ('uE', [P.format('Posx'), P.format('Posy'), P.format('Seed'), 'me.inputs[0].width / max(me.inputs[0].height, 1)']),
        ('uF', [P.format('Color1r'), P.format('Color1g'), P.format('Color1b'), '0']),
        ('uG', [P.format('Color2r'), P.format('Color2g'), P.format('Color2b'), '0']),
        ('uH', [P.format('Color3r'), P.format('Color3g'), P.format('Color3b'), '0']),
    ])
    g.comment = 'leaks: edge-pinned fbm blobs (screen/add/lighten) + film burn front; continuous or triggered envelope.'
    pe = mk(m, parameterexecuteDAT, 'pulse_exec')
    if pe.text != PULSE_EXEC:
        pe.text = PULSE_EXEC
        pe.par.active = False                                # T-97: toggle after a text rewrite
    pe.par.op = '..'
    pe.par.pars = 'Trigger'
    pe.par.valuechange = False
    pe.par.onpulse = True
    pe.par.active = True
    pe.comment = 'Trigger pulse -> Hittime (Trigger page); the envelope runs in the uniform expression.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1']},
        {'title': '2 Leaks + burn', 'role': 'process', 'ops': ['fx', 'fx_compute', 'pulse_exec'],
         'body': 'One compute pass; Trigger -> Hittime -> Attack/Hold/Release envelope x Level.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
