# fx_track_analytics - FX_track module 'analytics' (FX7b TC-04 surveillance analytics overlay: motion heat, zones,
# counters, redaction of movers; the CCTV-analytics look as a stage visual). Template: docs/builds/fx_glitch.md
# "Module template" (rack = builders/fx_track.py). Doc: docs/builds/fx_track.md. Mirror: fx_track_logic.hs_step /
# analytics_pixel. No faces are shown or identified: redaction covers movers (M_audience_interaction privacy line).
#   det (rack key, Select) + trk_pts + hs_fb -> hs (heat at Detw x Deth + one stats row: count, movers, mean
#   strength, time; per zone share / movers) -> fx (in1, trk_pts, hs: heat overlay / thermal, zone grid + hot zones +
#   labels, redaction bars / mosaic on movers, CAM / REC timecode / COUNT / MOVING text) -> out_sel -> out1.
# hs is self-clocked: dt = now - the time stored by its last cook (0 when cooked twice in a frame, capped 0.1 s).
# <= 3 GLSL TOP inputs (T-88). No limits. ASCII only.
import os

MODULE = 'analytics'
HEATMODES = ['off', 'overlay', 'thermal']
REDACT = ['off', 'bars', 'mosaic']

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
_L = {'HERE': HERE}  # noqa: F821
exec(compile(open(os.path.join(HERE, 'fx_track_lib.py')).read(), 'fx_track_lib.py', 'exec'), _L)  # noqa: F821

PAGES = [
    ('Analytics', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Heat', 'Menu', 'overlay', {'names': HEATMODES, 'labels': ['Off', 'Heat overlay', 'Thermal picture']}),
        ('Heatgain', 'Float', 3.0, {'min': 0, 'max': 40, 'label': 'Heat gain (per s over threshold)'}),
        ('Heatdecay', 'Float', 2.0, {'min': 0.01, 'max': 30, 'label': 'Heat decay s'}),
        ('Heatmax', 'Float', 1.0, {'min': 0.01, 'max': 10, 'label': 'Heat for palette end'}),
        ('Heatmix', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Heat overlay mix'}),
        ('Mono', 'Float', 0.6, {'min': 0, 'max': 1, 'label': 'Picture to mono (CCTV)'}),
        ('Zonesx', 'Int', 3, {'min': 1, 'max': 16, 'label': 'Zones across'}),
        ('Zonesy', 'Int', 4, {'min': 1, 'max': 16, 'label': 'Zones down'}),
        ('Zonewidth', 'Float', 1.0, {'min': 0, 'max': 12, 'label': 'Zone grid width px (0 off)'}),
        ('Zonethr', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Hot zone share of points'}),
        ('Zonefill', 'Float', 0.18, {'min': 0, 'max': 1, 'label': 'Hot zone fill'}),
        ('Zonelabels', 'Toggle', True, {'label': 'Zone labels (Z01 045%)'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 999, 'label': 'Seed'}),
    ]),
    ('Redact', [
        ('Redact', 'Menu', 'bars', {'names': REDACT, 'labels': ['Off', 'Bars', 'Mosaic']}),
        ('Redacton', 'Menu', 'movers', {'names': ['all', 'movers'], 'labels': ['All tracked', 'Movers only']}),
        ('Moverthr', 'Float', 60.0, {'min': 0, 'max': 2000, 'label': 'Mover speed px/s'}),
        ('Redactpad', 'Float', 4.0, {'min': -50, 'max': 200, 'label': 'Redaction padding px'}),
        ('Mosaic', 'Float', 16.0, {'min': 1, 'max': 200, 'label': 'Mosaic block px'}),
        ('Barr', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Bar R'}),
        ('Barg', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Bar G'}),
        ('Barb', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Bar B'}),
    ]),
    ('Text', [
        ('Overlay', 'Toggle', True, {'label': 'CAM / REC / COUNT text'}),
        ('Textscale', 'Float', 3.0, {'min': 1, 'max': 12, 'label': 'Text pixel px'}),
        ('Cam', 'Int', 1, {'min': 0, 'max': 99, 'label': 'Camera number'}),
        ('Margin', 'Float', 24.0, {'min': 0, 'max': 400, 'label': 'Margin px'}),
        ('Colr', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Text / grid R'}),
        ('Colg', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Text / grid G'}),
        ('Colb', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Text / grid B'}),
        ('Recr', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'REC dot R'}),
    ]),
    pal_page('fire', 'gradient'),  # noqa: F821
]
PANEL_PAGES = ['Analytics', 'Redact', 'Text', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
_D['Palreverse'] = int(_D['Palreverse'])
_D['Zonelabels'] = int(_D['Zonelabels'])
_D['Overlay'] = int(_D['Overlay'])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'cctv analytics', _p()),
    (2, 'thermal', _p(Heat=2, Heatgain=6.0, Heatdecay=3.0, Redact=0, Zonewidth=0.0, Zonelabels=0, Mono=0.0,
                      Palsource=PAL_SOURCE_NAMES.index('fire'), Seed=2)),  # noqa: F821
    (3, 'redacted crowd', _p(Heat=0, Redact=1, Redacton=0, Redactpad=8.0, Zonesx=2, Zonesy=2, Mono=1.0, Seed=3)),
    (4, 'mosaic movers', _p(Heat=1, Heatmix=0.4, Redact=2, Mosaic=24.0, Zonesx=4, Zonesy=6, Zonethr=0.08,
                            Palsource=PAL_SOURCE_NAMES.index('cyan_magenta'), Seed=4)),  # noqa: F821
    (5, 'data wall', _p(Heat=1, Heatmix=1.0, Heatgain=10.0, Heatdecay=6.0, Redact=0, Zonesx=8, Zonesy=12,
                        Zonethr=0.02, Zonefill=0.35, Textscale=2.0, Mono=1.0,
                        Palsource=PAL_SOURCE_NAMES.index('neon_trio'), Seed=5)),  # noqa: F821
]

HS = """// analytics hs (compute): Detw x (Deth + 1) rgba32f. in0 rack det (r key), in1 trk_pts, in2 hs_fb (last hs).
// Rows y < Deth: r heat = last x exp(-dt / decay) + max(key - threshold, 0) x gain x dt, g key. Row Deth (stats):
// x 0 = count, movers, mean strength, time of this cook; x 1 + z = zone z share of points, movers in it.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uH;   // heat gain, heat decay s, threshold, now s
uniform vec4 uZ;   // zones x, zones y, mover px/s, -
uniform vec4 uR;   // picture w, h (px for speeds), -, -
uniform vec4 uG;   // detector, cells x, cells y, N
#define FT_PTS sTD2DInputs[1]
""" + _L['GLSL_LIB'] + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 osz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= osz.x || p.y >= osz.y) return;
    int dh = osz.y - 1;
    bool same = textureSize(sTD2DInputs[2], 0) == osz;
    float last = same ? texelFetch(sTD2DInputs[2], ivec2(0, dh), 0).w : -1.0;
    float dt = last > 0.0 ? clamp(uH.w - last, 0.0, 0.1) : 0.0;
    if (p.y < dh) {
        float k = texture(sTD2DInputs[0], (vec2(p) + 0.5) / vec2(osz.x, dh)).r;
        float h = same ? texelFetch(sTD2DInputs[2], p, 0).r : 0.0;
        h = h * exp(-dt / max(uH.y, 1e-3)) + max(k - uH.z, 0.0) * uH.x * dt;
        TDImageStoreOutput(0, ivec3(p, 0), vec4(h, k, 0.0, 1.0));
        return;
    }
    int n = int(uG.w + 0.5), zx = max(int(uZ.x + 0.5), 1), zy = max(int(uZ.y + 0.5), 1);
    int z = p.x - 1;
    if (p.x > 0 && z >= zx * zy) { TDImageStoreOutput(0, ivec3(p, 0), vec4(0.0)); return; }
    float cnt = 0.0, mov = 0.0, ss = 0.0, zc = 0.0, zm = 0.0;
    for (int i = 0; i < 16384; i++) {
        if (i >= n) break;
        vec4 T0 = ftT(i, 0);
        if (T0.w < 0.5) continue;
        vec4 T1 = ftT(i, 1), T3 = ftT(i, 3);
        bool mv = length(T3.zw * uR.xy) > uZ.z;
        cnt += 1.0; ss += T1.z; mov += mv ? 1.0 : 0.0;
        if (p.x > 0) {
            ivec2 zc2 = clamp(ivec2(floor(T1.xy * vec2(zx, zy))), ivec2(0), ivec2(zx - 1, zy - 1));
            if (zc2.y * zx + zc2.x == z) { zc += 1.0; zm += mv ? 1.0 : 0.0; }
        }
    }
    vec4 o = p.x == 0 ? vec4(cnt, mov, ss / max(cnt, 1.0), uH.w) : vec4(zc / max(cnt, 1.0), zm, 0.0, 0.0);
    TDImageStoreOutput(0, ivec3(p, 0), o);
}
"""

FX = """// analytics fx (compute). in0 in1, in1 trk_pts, in2 hs. Mono / heat (overlay or thermal, palette), zone grid + hot
// zone fill + labels, redaction (bars / mosaic) on movers or all, CAM nn / REC timecode + blinking dot / COUNT /
// MOVING text. Amount mix with in1.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, heat mode, heat max, heat mix
uniform vec4 uB;   // mono, zone width px, zone threshold, zone fill
uniform vec4 uZ;   // zones x, zones y, mover px/s, zone labels
uniform vec4 uX;   // redact mode, redact on (0 all, 1 movers), pad px, mosaic px
uniform vec4 uY;   // bar r g b, overlay text
uniform vec4 uS;   // text px, cam, margin px, rec dot r
uniform vec4 uC;   // text / grid r g b, time s
uniform vec4 uG;   // detector, cells x, cells y, N
#define FT_PTS sTD2DInputs[1]
""" + PAL_GLSL + _L['GLSL_LIB'] + """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    if (p.x >= sz.x || p.y >= sz.y) return;
    vec2 res = vec2(sz), pc = vec2(p) + 0.5, uv = pc / res;
    vec4 src = texelFetch(sTD2DInputs[0], p, 0);
    ivec2 hsz = textureSize(sTD2DInputs[2], 0);
    int dh = hsz.y - 1;
    float L = dot(src.rgb, vec3(0.2126, 0.7152, 0.0722));
    vec3 col = mix(src.rgb, vec3(L), uB.x);
    float hv = texture(sTD2DInputs[2], vec2(uv.x, min(uv.y * float(dh), float(dh) - 0.5) / float(hsz.y))).r;
    float hn = hv / max(uA.z, 1e-4);
    int hm = int(uA.y + 0.5);
    if (hm == 1) col = mix(col, pxPal(clamp(hn, 0.0, 1.0)), uA.w * smoothstep(0.02, 0.3, hn));
    else if (hm == 2) col = mix(col, pxPal(clamp(0.35 * L + hn, 0.0, 1.0)), uA.w);
    // redaction
    int rm = int(uX.x + 0.5);
    if (rm > 0) {
        vec2 reach = vec2(abs(uX.z) + 2.0) / res;
        bool hit = false;
""" + _L['LOOP_OPEN'] + """
            if (uX.y > 0.5 && length(T3.zw * res) <= uZ.z) continue;
            vec2 b0 = T2.xy * res - uX.z, b1 = T2.zw * res + uX.z;
            if (pc.x >= b0.x && pc.x < b1.x && pc.y >= b0.y && pc.y < b1.y) hit = true;
""" + _L['LOOP_CLOSE'] + """
        if (hit) {
            if (rm == 1) col = uY.rgb;
            else {
                float m = max(uX.w, 1.0);
                vec4 s = texture(sTD2DInputs[0], (floor(pc / m) + 0.5) * m / res);
                col = mix(s.rgb, vec3(dot(s.rgb, vec3(0.2126, 0.7152, 0.0722))), uB.x);
            }
        }
    }
    // zones
    int zx = max(int(uZ.x + 0.5), 1), zy = max(int(uZ.y + 0.5), 1);
    vec2 zs = res / vec2(zx, zy);
    ivec2 zc = clamp(ivec2(floor(pc / zs)), ivec2(0), ivec2(zx - 1, zy - 1));
    int z = zc.y * zx + zc.x;
    vec4 st = texelFetch(sTD2DInputs[2], ivec2(1 + z, dh), 0);
    float a = 0.0;
    bool hot = st.x >= uB.z && uB.z >= 0.0 && st.x > 0.0;
    if (hot) col = mix(col, uC.rgb, uB.w);
    if (uB.y > 0.0) {
        vec2 fz = pc - vec2(zc) * zs;
        float d = min(min(fz.x, zs.x - fz.x), min(fz.y, zs.y - fz.y));
        a = max(a, clamp(0.5 * uB.y - d + 0.5, 0.0, 1.0));
    }
    float sc = max(uS.x, 1e-3);
    if (uZ.w > 0.5 && hot) {
        vec2 org = vec2(zc) * zs + vec2(6.0, zs.y - 6.0 - 8.0 * sc * 0.67);
        a = max(a, ftText(pc, org, sc * 0.67, 10, vec4(float(z + 1), floor(st.x * 100.0 + 0.5), 0.0, 0.0)));
    }
    vec3 tc = uC.rgb;
    float ra = 0.0;
    if (uY.w > 0.5) {
        vec4 s0 = texelFetch(sTD2DInputs[2], ivec2(0, dh), 0);
        float m = uS.z, top = res.y - m - 8.0 * sc;
        a = max(a, ftText(pc, vec2(m, top), sc, 9, vec4(uS.y, 0.0, 0.0, 0.0)));
        a = max(a, ftText(pc, vec2(m, top - 10.0 * sc), sc, 8, vec4(floor(uC.w), 0.0, 0.0, 0.0)));
        vec2 dc = vec2(m + 13.0 * 8.0 * sc + 4.0 * sc, top - 10.0 * sc + 4.0 * sc);
        if (fract(uC.w) < 0.5) ra = clamp(3.0 * sc - length(pc - dc) + 0.5, 0.0, 1.0);
        a = max(a, ftText(pc, vec2(m, m + 10.0 * sc), sc, 6, vec4(s0.x, 0.0, 0.0, 0.0)));
        a = max(a, ftText(pc, vec2(m, m), sc, 7, vec4(s0.y, 0.0, 0.0, 0.0)));
    }
    col = mix(col, tc, a);
    col = mix(col, vec3(uS.w, 0.05, 0.05), ra);
    vec4 o = vec4(col, max(src.a, max(a, ra)));
    TDImageStoreOutput(0, ivec3(p, 0), mix(src, o, uA.x));
}
"""

SHADERS = {'hs': HS, 'fx': FX}
NIN = {'hs': 3, 'fx': 3}

P = "parent().par.{}.eval()"
G = ['parent(2).par.Detector.menuIndex', 'parent(2).par.Cellsx.eval()', 'parent(2).par.Cellsy.eval()',
     ("(int(parent(2).par.Cellsx.eval()) * int(parent(2).par.Cellsy.eval()) if parent(2).par.Detector.eval() == "
      "'cells' else int(parent(2).par.Maxblobs.eval()))")]


def uniforms():
    return {
        'hs': [('uH', [P.format('Heatgain'), P.format('Heatdecay'), 'parent(2).par.Threshold.eval()',
                       'absTime.seconds']),
               ('uZ', [P.format('Zonesx'), P.format('Zonesy'), P.format('Moverthr'), '0']),
               ('uR', ['parent(2).par.Resw.eval()', 'parent(2).par.Resh.eval()', '0', '0']),
               ('uG', G)],
        'fx': [('uA', [P.format('Amount'), 'parent().par.Heat.menuIndex', P.format('Heatmax'), P.format('Heatmix')]),
               ('uB', [P.format('Mono'), P.format('Zonewidth'), P.format('Zonethr'), P.format('Zonefill')]),
               ('uZ', [P.format('Zonesx'), P.format('Zonesy'), P.format('Moverthr'), P.format('Zonelabels')]),
               ('uX', ['parent().par.Redact.menuIndex', 'parent().par.Redacton.menuIndex', P.format('Redactpad'),
                       P.format('Mosaic')]),
               ('uY', [P.format('Barr'), P.format('Barg'), P.format('Barb'), P.format('Overlay')]),
               ('uS', [P.format('Textscale'), P.format('Cam'), P.format('Margin'), P.format('Recr')]),
               ('uC', [P.format('Colr'), P.format('Colg'), P.format('Colb'), 'absTime.seconds']),
               ('uG', G)],
    }


def build(m, H):
    """det (Select) + pts + hs_fb -> hs -> fx (in1, pts, hs) -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    pts = mk(m, selectTOP, 'pts')  # noqa: F821
    pts.par.top = '../trk_pts'
    pts.comment = "The rack's points (trk_pts)."
    det = mk(m, selectTOP, 'det')  # noqa: F821
    det.par.top = '../det'
    det.comment = "The rack's key (det: r key)."
    blk = mk(m, constantTOP, 'black')  # noqa: F821
    blk.par.outputresolution = 'custom'
    blk.par.resolutionw, blk.par.resolutionh = 8, 8
    blk.par.format = 'rgba32float'
    blk.par.colorr = blk.par.colorg = blk.par.colorb = 0
    blk.par.alpha = 0
    blk.comment = 'Reset source of hs_fb.'
    hfb = mk(m, feedbackTOP, 'hs_fb')  # noqa: F821
    hs = H['pas'](m, 'hs', HS, [det, pts, hfb], 'parent(2).par.Detw.eval()', 'parent(2).par.Deth.eval() + 1',
                  'rgba32float', 'hold')
    hfb.inputConnectors[0].connect(blk)
    hfb.par.top = 'hs'
    H['uniforms'](hs, U['hs'])
    hs.comment = 'Heat (self-clocked decay + key over threshold) + stats row (count, movers, zones).'
    fx = H['pas'](m, 'fx', FX, [in1, pts, hs], 'me.inputs[0].width', 'me.inputs[0].height', 'rgba16float', 'hold')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'CCTV analytics: heat / thermal, zones, redaction of movers, CAM / REC / COUNT text.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (hs / fx not pulled).'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pts', 'det', 'black']},
        {'title': '2 Heat + stats', 'role': 'process', 'ops': ['hs_fb', 'hs', 'hs_compute'],
         'body': 'Heat accumulates key over threshold, decays; stats row counts points, movers, zones.'},
        {'title': '3 Draw', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'Heat / thermal, zones, redaction, CCTV text.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
