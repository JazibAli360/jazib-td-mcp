# fx_destroy_burn - FX_destroy module 'burn' (FX1 DG-18: burn / erode / dissolve edge + fire-spread CA).
# Module file = PAGES + PRESETS + build(m, H) (template: docs/builds/fx_glitch.md; rack: builders/fx_destroy.py).
# Noise dissolve: one pass, a Progress threshold over fbm + an origin front (bottom/top/point/mask/sparks).
# Fire spread CA: `state` (rgba32float in place at Cell res: r = burn age s, -1 unburnt) where a burning neighbour
# ignites a cell with probability Spread * wind * fuel per step; ignition from the origin (Effector Nulls / Point,
# mask, an edge, random sparks). Both map the burn phase through hot -> ember rim -> char -> ash (Back).
# Amount 0 = exact passthrough. The CA restarts after a stall > 0.25 s (bypass / panic) or a Reset pulse. ASCII only.

MODULE = 'burn'
ORIGINS = ['noise', 'bottom', 'top', 'point', 'mask', 'sparks']

PAGES = [
    ('Burn', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Mode', 'Menu', 'noise', {'names': ['noise', 'ca'], 'labels': ['Noise dissolve (Progress)',
                                                                         'Fire spread CA (runs)']}),
        ('Progress', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Progress'}),
        ('Origin', 'Menu', 'bottom', {'names': ORIGINS, 'labels': ['Noise only', 'Bottom edge', 'Top edge',
                                                                   'Point / Effectors', 'Mask (white starts)',
                                                                   'Random sparks']}),
        ('Effector2', 'COMP', '', {'label': 'Effector 2 Null'}),
        ('Radius', 'Float', 0.03, {'min': 0, 'max': 0.5, 'label': 'Start radius'}),
        ('Scale', 'Float', 6.0, {'min': 0.5, 'max': 40, 'label': 'Noise scale'}),
        ('Roughness', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Roughness'}),
        ('Band', 'Float', 0.08, {'min': 0.005, 'max': 0.5, 'label': 'Burn band'}),
        ('Char', 'Float', 0.05, {'min': 0, 'max': 0.5, 'label': 'Char ahead'}),
        ('Rise', 'Float', 0.3, {'min': 0, 'max': 3, 'label': 'Flame rise'}),
        ('Emissive', 'Float', 1.6, {'min': 0, 'max': 6, 'label': 'Emissive'}),
        ('Fuel', 'Float', 0.4, {'min': -1, 'max': 1, 'label': 'Fuel from luma'}),
        ('Spread', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'CA spread'}),
        ('Burntime', 'Float', 0.5, {'min': 0.05, 'max': 10, 'label': 'CA burn s'}),
        ('Reach', 'Int', 1, {'min': 1, 'max': 4, 'label': 'CA reach cells'}),
        ('Cell', 'Menu', '4', {'names': ['2', '4', '8'], 'labels': ['2 px', '4 px', '8 px']}),
        ('Windangle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Wind angle (0 = up)'}),
        ('Windforce', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Wind force'}),
        ('Sparks', 'Float', 0.2, {'min': 0, 'max': 1, 'label': 'Sparks rate'}),
        ('Maskuse', 'Menu', 'limit', {'names': ['limit', 'ignore'], 'labels': ['Burn only in mask', 'Ignore']}),
        ('Back', 'Menu', 'black', {'names': ['black', 'alpha'], 'labels': ['Black', 'Transparent']}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ('Reset', 'Pulse', None, {'label': 'Reset (re-light CA)'}),
    ]),
    ('Colours', [
        ('Hotcolor', 'RGB', (1.0, 0.92, 0.62), {'label': 'Hot core'}),
        ('Embercolor', 'RGB', (1.0, 0.38, 0.04), {'label': 'Ember rim'}),
        ('Charcolor', 'RGB', (0.10, 0.03, 0.015), {'label': 'Char'}),
    ]),
    MASK_PAGE, POINT_PAGE, STATE_PAGE,          # shared pages (rack builders/fx_destroy.py)
]
PANEL_PAGES = ['Burn', 'Colours', 'Mask', 'Point']

PRESETS = [
    (1, 'paper burn', {'Amount': 1.0, 'Mode': 1, 'Origin': 1, 'Spread': 0.55, 'Burntime': 0.6, 'Reach': 1,
                       'Cell': 1, 'Windangle': 0.0, 'Windforce': 0.6, 'Fuel': 0.5, 'Roughness': 0.4,
                       'Emissive': 1.8, 'Seed': 1}),
    (2, 'ember rise', {'Amount': 1.0, 'Mode': 0, 'Origin': 1, 'Progress': 0.45, 'Scale': 5.0, 'Roughness': 0.6,
                       'Band': 0.1, 'Char': 0.06, 'Rise': 0.8, 'Emissive': 2.2, 'Seed': 2}),
    (3, 'acid melt', {'Amount': 1.0, 'Mode': 0, 'Origin': 0, 'Progress': 0.5, 'Scale': 9.0, 'Roughness': 1.0,
                      'Band': 0.05, 'Char': 0.02, 'Rise': 0.0, 'Emissive': 1.4, 'Hotcolorr': 0.85,
                      'Hotcolorg': 1.0, 'Hotcolorb': 0.4, 'Embercolorr': 0.2, 'Embercolorg': 0.95,
                      'Embercolorb': 0.1, 'Charcolorr': 0.02, 'Charcolorg': 0.08, 'Charcolorb': 0.02, 'Seed': 3}),
    (4, 'wildfire', {'Amount': 1.0, 'Mode': 1, 'Origin': 3, 'Radius': 0.03, 'Spread': 0.8, 'Burntime': 0.3,
                     'Reach': 2, 'Cell': 1, 'Windangle': 30.0, 'Windforce': 1.2, 'Fuel': 0.3, 'Emissive': 2.4,
                     'Seed': 4}),
    (5, 'spark holes', {'Amount': 1.0, 'Mode': 1, 'Origin': 5, 'Sparks': 0.5, 'Spread': 0.45, 'Burntime': 0.8,
                        'Reach': 1, 'Cell': 0, 'Windforce': 0.2, 'Fuel': 0.6, 'Emissive': 1.6, 'Seed': 5}),
]

STATE = """// burn CA state (compute, rgba32float in place at Cell res): r = burn age s (-1 = unburnt), a = last cook time.
// in0 = picture (fuel), in1 = mask.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, origin, spread, reach
uniform vec4 uB;   // now, resettime, burntime, fuel
uniform vec4 uC;   // wind x, wind y (force * dir), sparks, radius
uniform vec4 uD;   // point1 uv, point2 uv
uniform vec4 uE;   // maskuse, seed, state w, state h
""" + '%LIB%' + '%MASK%' + """
float fuelAt(vec2 uv) { return max(0.05, 1.0 + uB.w * (luma(texture(sTD2DInputs[0], uv).rgb) - 0.5) * 2.0); }
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 ssz = ivec2(uE.zw);
    if (p.x >= ssz.x || p.y >= ssz.y) return;
    vec4 s = TDImageLoadOutput(0, ivec3(p, 0));
    float now = uB.x;
    // Reset stamp (voided when from another clock, T-155) >= last cook: equal still resets (T-160)
    if (!(now - s.a <= 0.25) || uB.y >= s.a || uA.x <= 0.0) {
        TDImageStoreOutput(0, ivec3(p, 0), vec4(-1.0, 0.0, 0.0, now)); return;
    }
    float dt = clamp(now - s.a, 0.0, 0.1);
    float age = s.r;
    if (age >= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), vec4(age + dt, 0.0, 0.0, now)); return; }
    vec2 uv = (vec2(p) + 0.5) / vec2(ssz);
    vec2 fsz = vec2(textureSize(sTD2DInputs[0], 0));
    vec2 asp = vec2(fsz.x / fsz.y, 1.0);
    float msk = fxMask(uv, texture(sTD2DInputs[0], uv).rgb);
    int org = int(uA.y + 0.5);
    if (int(uE.x + 0.5) == 0 && org != 4 && msk < 0.5) {             // limit: never burns outside the mask
        TDImageStoreOutput(0, ivec3(p, 0), vec4(-1.0, 0.0, 0.0, now)); return;
    }
    uint sd = uint(uE.y);
    float rnd = hsh3(ivec3(p, int(now * 240.0)), sd);
    bool ign = false;
    if (org == 1) ign = p.y == 0;
    else if (org == 2) ign = p.y == ssz.y - 1;
    else if (org == 3) ign = min(length((uv - uD.xy) * asp), length((uv - uD.zw) * asp)) < uC.w;
    else if (org == 4) ign = msk > 0.5;
    else ign = rnd < uC.z * 0.0004 * dt * 60.0;                       // noise / sparks: random ignitions
    float fu = fuelAt(uv);
    if (!ign) {
        float acc = 0.0;
        int R = max(1, int(uA.w + 0.5));
        for (int j = -1; j <= 1; j++) {
            for (int i = -1; i <= 1; i++) {
                if (i == 0 && j == 0) continue;
                ivec2 q = p + ivec2(i, j) * R;
                if (q.x < 0 || q.y < 0 || q.x >= ssz.x || q.y >= ssz.y) continue;
                float a2 = TDImageLoadOutput(0, ivec3(q, 0)).r;
                if (a2 >= 0.0 && a2 < uB.z * fu) {
                    vec2 o = normalize(-vec2(float(i), float(j)));
                    acc += max(0.0, 1.0 + dot(o, uC.xy)) * (abs(i) + abs(j) == 2 ? 0.7071 : 1.0);
                }
            }
        }
        float pr = uA.z * acc * 0.25 * fu * dt * 60.0;
        ign = hsh3(ivec3(p, int(now * 240.0) + 7), sd + 3u) < pr;
    }
    TDImageStoreOutput(0, ivec3(p, 0), vec4(ign ? 0.0 : -1.0, 0.0, 0.0, now));
}
"""

FX = """// burn fx (compute, format useinput). in0 = picture, in1 = CA state (or 1x1 white in Noise mode), in2 = mask.
// Amount 0 = exact passthrough (texelFetch).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, mode, progress, origin
uniform vec4 uB;   // scale, roughness, band, char
uniform vec4 uC;   // now, rise, fuel, back
uniform vec4 uD;   // point1 uv, point2 uv
uniform vec4 uE;   // burntime, maskuse, seed, radius
uniform vec4 uH;   // hot rgb, emissive
uniform vec4 uR;   // ember rgb
uniform vec4 uK;   // char rgb
""" + '%LIB%' + '%MASK%' + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c0 = texelFetch(sTD2DInputs[0], p, 0);
    if (uA.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c0); return; }
    vec2 sz = vec2(isz);
    vec2 uv = (vec2(p) + 0.5) / sz;
    vec2 asp = vec2(sz.x / sz.y, 1.0);
    uint sd = uint(uE.z);
    float n = fbm(uv * asp * uB.x + vec2(0.0, -uC.x * uC.y), sd, 4);
    float L = luma(c0.rgb);
    float fu = max(0.05, 1.0 + uC.z * (L - 0.5) * 2.0);
    float msk = fxMask(uv, c0.rgb);
    int org = int(uA.w + 0.5);
    float t;     // burn phase: < -char = untouched, -char..0 char ahead, 0..band burning, > band ash
    float band = max(uB.z, 1e-3);
    if (int(uA.y + 0.5) == 0) {
        float f = 0.0, R = uB.y;
        if (org == 0) R = 1.0;
        else if (org == 1) f = uv.y;
        else if (org == 2) f = 1.0 - uv.y;
        else if (org == 3) f = clamp(min(length((uv - uD.xy) * asp), length((uv - uD.zw) * asp)) / 1.2, 0.0, 1.0);
        else if (org == 4) f = 1.0 - msk;
        else f = fbm(uv * asp * uB.x * 0.2 + 3.7, sd + 5u, 2);
        float v = mix(f, n, R) + uC.z * (L - 0.5) * 0.15;
        t = uA.z * (1.0 + band + uB.w + 0.15) - uB.w - 0.075 - v;
    } else {
        vec2 cpx = sz / vec2(textureSize(sTD2DInputs[1], 0));           // CA cell size in px
        vec2 wp = vec2(fbm(uv * asp * uB.x * 3.0, sd + 11u, 2), fbm(uv * asp * uB.x * 3.0 + 5.3, sd + 13u, 2)) - 0.5;
        vec2 uw = uv + wp * uB.y * cpx * 6.0 / sz;                      // warp breaks the cell grid
        vec2 h = 0.5 * cpx / sz;
        float age = 0.25 * (texture(sTD2DInputs[1], uw + vec2(h.x, h.y)).r + texture(sTD2DInputs[1], uw + vec2(-h.x, h.y)).r
                          + texture(sTD2DInputs[1], uw + vec2(h.x, -h.y)).r + texture(sTD2DInputs[1], uw - h).r);
        if (age < 0.0) t = (age + 1.0) * uB.w - uB.w - 1e-4;          // bilinear front -> char ahead
        else t = (age / (uE.x * fu) + (n - 0.5) * uB.y * 0.6) * band;
    }
    if (int(uE.y + 0.5) == 0 && org != 4 && msk < 0.5 && int(uA.y + 0.5) == 0) t = -1.0;   // limit to the mask
    vec4 o = c0;
    vec4 back = int(uC.w + 0.5) == 1 ? vec4(0.0) : vec4(0.0, 0.0, 0.0, c0.a);
    if (t > -uB.w && t <= 0.0) {
        float k = 1.0 + t / max(uB.w, 1e-4);
        o.rgb = mix(c0.rgb, c0.rgb * vec3(0.55, 0.36, 0.22), k * 0.8) + uR.rgb * pow(k, 6.0) * 0.4 * uH.w;
    } else if (t > 0.0) {
        float b = t / band;
        vec3 hot = uH.rgb * uH.w, emb = uR.rgb * uH.w;
        if (b < 0.15) o = vec4(mix(hot, emb, b / 0.15), c0.a);
        else if (b < 0.5) o = vec4(mix(emb, uK.rgb, (b - 0.15) / 0.35), c0.a);
        else if (b < 1.0) o = mix(vec4(uK.rgb, c0.a), back, (b - 0.5) / 0.5);
        else o = back;
    }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c0, o, uA.x));
}
"""

P = "parent().par.{}.eval()"


def build(m, H):
    """Fill instance COMP m: in1 -> state (CA, Cell res) -> st_sel -> fx -> out1, + mask_src / pulse_exec."""
    mk, expr, compute, pt = H['mk'], H['expr'], H['compute'], H['pt_expr']
    lib = H['GLSL_LIB']
    in1 = mk(m, inTOP, 'in1')
    mn, ms = H['mask_ops'](m)
    H['pulse_exec'](m, ['Reset'])
    pts = ('uD', [pt('u'), pt('v'), pt('u', '2'), pt('v', '2')])
    cell = "int(parent().par.Cell.eval())"
    sw, sh = 'max(1, me.inputs[0].width // %s)' % cell, 'max(1, me.inputs[0].height // %s)' % cell
    st = compute(m, 'state', STATE.replace('%LIB%', lib).replace('%MASK%', H['mask_glsl'](1)), [in1, ms], sw, sh,
                 fmt='rgba32float', readwrite=True,
                 uniforms=[('uA', [P.format('Amount'), 'parent().par.Origin.menuIndex', P.format('Spread'),
                                   P.format('Reach')]),
                           ('uB', ['absTime.seconds', H['stamp']('Resettime'), P.format('Burntime'), P.format('Fuel')]),
                           ('uC', ['%s * math.sin(math.radians(%s))' % (P.format('Windforce'), P.format('Windangle')),
                                   '%s * math.cos(math.radians(%s))' % (P.format('Windforce'), P.format('Windangle')),
                                   P.format('Sparks'), P.format('Radius')]),
                           pts,
                           ('uE', ['parent().par.Maskuse.menuIndex', P.format('Seed'), sw, sh])]
                 + H['MASK_UNIFORMS'])
    st.comment = 'burn CA: per cell burn age (rgba32float in place, Cell px). Restarts after a stall / Reset.'
    sel = mk(m, switchTOP, 'st_sel')
    sel.inputConnectors[0].connect(st)
    sel.inputConnectors[1].connect(mn)
    expr(sel.par.index, "0 if parent().par.Mode.eval() == 'ca' else 1")
    sel.comment = 'Noise dissolve needs no state: mask_none instead, so the CA pass is not pulled.'
    g = compute(m, 'fx', FX.replace('%LIB%', lib).replace('%MASK%', H['mask_glsl'](2)), [in1, sel, ms],
                'me.inputs[0].width', 'me.inputs[0].height', extend='hold',      # zero-extend = a burning frame edge
                uniforms=[('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Progress'),
                                  'parent().par.Origin.menuIndex']),
                          ('uB', [P.format('Scale'), P.format('Roughness'), P.format('Band'), P.format('Char')]),
                          ('uC', ['absTime.seconds', P.format('Rise'), P.format('Fuel'), 'parent().par.Back.menuIndex']),
                          pts,
                          ('uE', [P.format('Burntime'), 'parent().par.Maskuse.menuIndex', P.format('Seed'),
                                  P.format('Radius')]),
                          ('uH', [P.format('Hotcolorr'), P.format('Hotcolorg'), P.format('Hotcolorb'),
                                  P.format('Emissive')]),
                          ('uR', [P.format('Embercolorr'), P.format('Embercolorg'), P.format('Embercolorb'), '0']),
                          ('uK', [P.format('Charcolorr'), P.format('Charcolorg'), P.format('Charcolorb'), '0'])]
                + H['MASK_UNIFORMS'])
    g.comment = 'burn: Noise dissolve / Fire spread CA (DG-18), hot -> ember -> char -> ash. Amount 0 = exact passthrough.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'mask_none', 'mask_src', 'pulse_exec'],
         'body': 'Picture (fuel), mask, Reset pulse -> Resettime.'},
        {'title': '2 Burn', 'role': 'process', 'ops': ['state', 'state_compute', 'st_sel', 'fx', 'fx_compute'],
         'body': 'state: fire-spread CA at Cell px (in place). fx: phase -> hot / ember / char / ash.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out1']},
    ]
