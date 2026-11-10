# fx_destroy_melt - FX_destroy module 'melt' (FX1 DG-14: drip / sag / liquify with gravity + mask).
# Module file = PAGES + PRESETS + build(m, H) (template: docs/builds/fx_glitch.md "Module template"; rack:
# builders/fx_destroy.py). Two compute passes: `state` (per-texel sag distance + speed, rgba32float in place, at
# Quality res, T-110 (5)) and `fx` (full res, samples the CLEAN input at p - dir * sag, so no resolution loss).
# Amount 0 = exact passthrough (texelFetch, format useinput). The state restarts from zero (intact picture) after a
# stall > 0.25 s (slot bypassed / panicked) or a Reset pulse. ASCII only.

MODULE = 'melt'
MODES = ['field', 'streaks', 'wave']
DIRS = ['down', 'up', 'left', 'right', 'out', 'in']

PAGES = [
    ('Melt', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'field', {'names': MODES, 'labels': ['Melt field (gravity sag)', 'Drip streaks',
                                                              'Heat wave (no state)']}),
        ('Direction', 'Menu', 'down', {'names': DIRS, 'labels': ['Down', 'Up', 'Left', 'Right', 'Radial out (Point)',
                                                                 'Radial in (Point)']}),
        ('Gravity', 'Float', 0.15, {'min': 0, 'max': 2, 'label': 'Gravity'}),
        ('Drip', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Drip (streams)'}),
        ('Columns', 'Float', 24.0, {'min': 2, 'max': 200, 'label': 'Columns'}),
        ('Weight', 'Float', 0.5, {'min': -1, 'max': 1, 'label': 'Luma weight'}),
        ('Viscosity', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Viscosity'}),
        ('Recover', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Recover'}),
        ('Maxlen', 'Float', 0.0, {'min': 0, 'max': 1920, 'label': 'Max sag px (0 = none)'}),
        ('Wobble', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Wobble'}),
        ('Speed', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Noise speed'}),
        ('Start', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Streak start spread'}),
        ('Length', 'Float', 160.0, {'min': 0, 'max': 800, 'label': 'Wave length px'}),
        ('Quality', 'Menu', 'half', {'names': ['full', 'half', 'quarter'], 'labels': ['Full', 'Half', 'Quarter']}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (unmelt)'}),
    ]),
    MASK_PAGE, POINT_PAGE, STATE_PAGE,          # shared pages (rack builders/fx_destroy.py)
]
PANEL_PAGES = ['Melt', 'Mask', 'Point']

PRESETS = [
    (1, 'wax', {'Amount': 1.0, 'Mode': 0, 'Direction': 0, 'Gravity': 0.12, 'Drip': 0.8, 'Columns': 28.0,
                'Weight': 0.7, 'Viscosity': 0.5, 'Recover': 0.0, 'Wobble': 0.3, 'Speed': 0.2, 'Seed': 1}),
    (2, 'acid drip', {'Amount': 1.0, 'Mode': 1, 'Direction': 0, 'Gravity': 0.8, 'Drip': 1.0, 'Columns': 60.0,
                      'Weight': 0.3, 'Viscosity': 0.2, 'Start': 0.8, 'Wobble': 0.15, 'Seed': 7}),
    (3, 'heat haze', {'Amount': 1.0, 'Mode': 2, 'Direction': 0, 'Length': 120.0, 'Columns': 10.0, 'Wobble': 0.5,
                      'Speed': 1.2, 'Seed': 3}),
    (4, 'beat sag', {'Amount': 1.0, 'Mode': 0, 'Direction': 0, 'Gravity': 0.8, 'Drip': 0.5, 'Columns': 16.0,
                     'Weight': 0.4, 'Viscosity': 0.6, 'Recover': 0.6, 'Maxlen': 300.0, 'Wobble': 0.2, 'Seed': 4}),
    (5, 'implode', {'Amount': 1.0, 'Mode': 0, 'Direction': 5, 'Gravity': 0.2, 'Drip': 0.6, 'Columns': 40.0,
                    'Weight': 0.5, 'Viscosity': 0.4, 'Recover': 0.0, 'Wobble': 0.2, 'Seed': 5}),
]

# direction field shared by both passes: d = unit vector the content moves along, c = across coordinate (for noise)
DIR_GLSL = """
uniform vec4 uD;   // dir mode, point u, point v, seed
void meltDir(vec2 uv, vec2 asp, out vec2 d, out float c) {
    int m = int(uD.x + 0.5);
    if (m == 0) { d = vec2(0.0, -1.0); c = uv.x * asp.x; }
    else if (m == 1) { d = vec2(0.0, 1.0); c = uv.x * asp.x; }
    else if (m == 2) { d = vec2(-1.0, 0.0); c = uv.y; }
    else if (m == 3) { d = vec2(1.0, 0.0); c = uv.y; }
    else {
        vec2 r = (uv - uD.yz) * asp;
        d = length(r) > 1e-5 ? normalize(r) : vec2(0.0, -1.0);
        if (m == 5) d = -d;
        c = (atan(r.y, r.x) / 6.2831853 + 0.5) * 2.0;
    }
}
"""

STATE = """// melt state (compute, rgba32float in place): r = sag px, g = speed px/s, b = -, a = last cook time.
// in0 = picture, in1 = mask. Restarts at 0 after a gap > 0.25 s, a Reset pulse, or a NaN.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode, gravity, drip
uniform vec4 uB;   // columns, weight, viscosity, recover
uniform vec4 uC;   // now, resettime, maxlen, speed
uniform vec4 uS;   // state w, h
""" + '%LIB%' + DIR_GLSL + '%MASK%' + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 ssz = ivec2(uS.xy);
    if (p.x >= ssz.x || p.y >= ssz.y) return;
    vec4 s = TDImageLoadOutput(0, ivec3(p, 0));
    float now = uC.x;
    // Reset stamp (voided when from another clock, T-155) >= last cook: equal still resets (T-160)
    if (!(now - s.a <= 0.25) || uC.y >= s.a || uA.y > 1.5 || uA.x <= 0.0) {
        TDImageStoreOutput(0, ivec3(p, 0), vec4(0.0, 0.0, 0.0, now)); return;
    }
    float dt = clamp(now - s.a, 0.0, 0.1);
    vec2 fsz = vec2(textureSize(sTD2DInputs[0], 0));
    vec2 asp = vec2(fsz.x / fsz.y, 1.0);
    vec2 uv = (vec2(p) + 0.5) / vec2(ssz);
    vec2 d; float c;
    meltDir(uv, asp, d, c);
    uint sd = uint(uD.w);
    float n = vnoise(vec2(c * uB.x, now * uC.w), sd);
    float f = mix(1.0, 3.0 * n * n * n + 0.05, uA.w);                 // drip: streams of fast columns
    vec3 col = texture(sTD2DInputs[0], uv - d * s.r / fsz).rgb;       // what is sagging here now
    float w = max(0.0, 1.0 + uB.y * (luma(col) - 0.5) * 2.0);
    float msk = fxMask(uv, texture(sTD2DInputs[0], uv).rgb);
    float v = s.g + uA.z * 2000.0 * f * w * msk * dt;                // gravity px/s^2
    v *= exp(-uB.z * 6.0 * dt);                                        // viscosity
    float k = exp(-uB.w * 6.0 * dt);                                   // recover pulls back
    float r = max(0.0, (s.r + v * dt) * k);
    v *= k;
    if (uC.z > 0.0) { r = min(r, uC.z); }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(r, v, 0.0, now));
}
"""

FX = """// melt fx (compute, format useinput). in0 = picture, in1 = state (or 1x1 white in Heat wave), in2 = mask.
// Amount 0 = exact passthrough (texelFetch).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode, wobble, columns
uniform vec4 uB;   // now, speed, start, length
""" + '%LIB%' + DIR_GLSL + '%MASK%' + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c0); return; }
    vec2 sz = vec2(isz);
    vec2 pc = vec2(p) + 0.5;
    vec2 uv = pc / sz;
    vec2 asp = vec2(sz.x / sz.y, 1.0);
    vec2 d; float c;
    meltDir(uv, asp, d, c);
    vec2 pp = vec2(-d.y, d.x);
    uint sd = uint(uD.w);
    int mode = int(uA.y + 0.5);
    vec4 o = c0;
    if (mode == 0) {
        float s = texture(sTD2DInputs[1], uv).r;
        float wob = (vnoise(vec2(c * uA.w * 3.0, s * 0.01 + uB.x * uB.y), sd + 7u) - 0.5) * uA.z * s * 0.3;
        o = texture(sTD2DInputs[0], (pc - d * s - pp * wob) / sz);
    } else if (mode == 1) {
        // streaks: column k starts at h(k) along d; from h to h + L the colour at h is stretched, round drop head
        float E = abs(d.x) * sz.x + abs(d.y) * sz.y;
        float a = dot(pc, d) + (dot(d, vec2(1.0)) < 0.0 ? E : 0.0);   // distance along d from the start edge
        if (int(uD.x + 0.5) >= 4) a = length((uv - uD.yz) * asp) * sz.y;
        float cw = max(1.0, sz.x / max(1.0, uA.w));                     // column width px
        float ck = floor(c * sz.y / cw);
        float cx = (c * sz.y - (ck + 0.5) * cw);                        // offset from the column centre, px
        float h = (1.0 - uB.z * hsh(ivec2(int(ck), 3), sd)) * E * 0.5 * (0.2 + hsh(ivec2(int(ck), 9), sd));
        h = min(h, E);
        vec2 hp = pc - d * (a - h);                                     // the streak's source pixel
        float L = texture(sTD2DInputs[1], hp / sz).r * (0.4 + 1.2 * hsh(ivec2(int(ck), 5), sd));
        float rad = cw * 0.5 * (0.6 + 0.4 * hsh(ivec2(int(ck), 11), sd));
        float t = a - h;
        bool inside = t > 0.0 && t < L && abs(cx) < rad;
        if (inside && t > L - rad) inside = length(vec2(cx, t - (L - rad))) < rad;   // round drop head
        if (inside) o = texture(sTD2DInputs[0], hp / sz);
    } else {
        float E = abs(d.x) * sz.x + abs(d.y) * sz.y;
        float a = clamp((dot(pc, d) + (dot(d, vec2(1.0)) < 0.0 ? E : 0.0)) / E, 0.0, 1.0);
        if (int(uD.x + 0.5) >= 4) a = clamp(length((uv - uD.yz) * asp), 0.0, 1.0);
        float m = fxMask(uv, c0.rgb);
        float ph = c * uA.w * 6.2831853 + uB.x * uB.y * 6.0;
        float sag = uB.w * a * a * (0.6 + 0.4 * sin(ph * 0.5 + 1.3)) * m;
        float lat = uA.z * uB.w * 0.25 * a * sin(ph + a * 9.0) * m;
        o = texture(sTD2DInputs[0], (pc - d * sag - pp * lat) / sz);
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c0, o, uA.x));
}
"""

P = "parent().par.{}.eval()"


def build(m, H):
    """Fill instance COMP m: in1 -> state (Quality res) -> st_sel -> fx -> out1, + mask_src / pulse_exec."""
    mk, expr, compute = H['mk'], H['expr'], H['compute']
    lib = H['GLSL_LIB']
    in1 = mk(m, inTOP, 'in1')
    mn, ms = H['mask_ops'](m)
    H['pulse_exec'](m, ['Reset'])
    dir_u = ('uD', ['parent().par.Direction.menuIndex', H['pt_expr']('u'), H['pt_expr']('v'), P.format('Seed')])
    q = "[1, 0.5, 0.25][parent().par.Quality.menuIndex]"
    sw, sh = 'max(1, int(me.inputs[0].width * %s))' % q, 'max(1, int(me.inputs[0].height * %s))' % q
    st = compute(m, 'state', STATE.replace('%LIB%', lib).replace('%MASK%', H['mask_glsl'](1)), [in1, ms], sw, sh,
                 fmt='rgba32float', readwrite=True, extend='hold',
                 uniforms=[('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Gravity'),
                                   P.format('Drip')]),
                           ('uB', [P.format('Columns'), P.format('Weight'), P.format('Viscosity'), P.format('Recover')]),
                           ('uC', ['absTime.seconds', H['stamp']('Resettime'), P.format('Maxlen'), P.format('Speed')]),
                           dir_u] + H['MASK_UNIFORMS'] + [('uS', [sw, sh, '0', '0'])])
    st.comment = 'melt state: per texel sag px + speed (rgba32float in place, Quality res). Restarts after a stall/Reset.'
    sel = mk(m, switchTOP, 'st_sel')
    sel.inputConnectors[0].connect(st)
    sel.inputConnectors[1].connect(mn)
    expr(sel.par.index, "1 if parent().par.Mode.eval() == 'wave' else 0")
    sel.comment = 'Heat wave needs no state: mask_none instead, so the state pass is not pulled.'
    g = compute(m, 'fx', FX.replace('%LIB%', lib).replace('%MASK%', H['mask_glsl'](2)), [in1, sel, ms],
                'me.inputs[0].width', 'me.inputs[0].height', extend='hold',
                uniforms=[('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Wobble'),
                                  P.format('Columns')]),
                          ('uB', ['absTime.seconds', P.format('Speed'), P.format('Start'), P.format('Length')]),
                          dir_u] + H['MASK_UNIFORMS'])
    g.comment = 'melt: Melt field / Drip streaks / Heat wave (DG-14). Samples the clean input. Amount 0 = exact passthrough.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'mask_none', 'mask_src', 'pulse_exec'],
         'body': 'Picture, mask (Mask page), Reset pulse -> Resettime.'},
        {'title': '2 Melt', 'role': 'process', 'ops': ['state', 'state_compute', 'st_sel', 'fx', 'fx_compute'],
         'body': 'state: sag field at Quality res (in place). fx: full-res sample of the clean picture.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
