# fx_track_hud - FX_track module 'hud' (FX7b TC-02 tracking HUD / "manual tracking VFX": boxes, corner brackets,
# circles, crosshairs, ids and coordinate read-outs locked onto the tracked points). Template: docs/builds/fx_glitch.md
# "Module template" (rack = builders/fx_track.py). Doc: docs/builds/fx_track.md. Mirror: fx_track_logic.hud_pixel.
# One compute pass: in1 + the rack's trk_pts -> fx -> out_sel (Amount 0 = in1) -> out1. Text = 8x8 font
# (builders/fx_retro_font8x8.py via fx_track_lib). No limits: sizes / counts are open ranges. ASCII only.
import os

MODULE = 'hud'
BOXSTYLES = ['off', 'box', 'corners', 'circle']

exec(open(os.path.join(HERE, 'fx_stylise_pal.py')).read())  # noqa: F821 (HERE from the rack) -> pal_page, pal_bind
_L = {'HERE': HERE}  # noqa: F821
exec(compile(open(os.path.join(HERE, 'fx_track_lib.py')).read(), 'fx_track_lib.py', 'exec'), _L)  # noqa: F821

PAGES = [
    ('Hud', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Boxstyle', 'Menu', 'corners', {'names': BOXSTYLES, 'labels': ['Off', 'Box', 'Corner brackets', 'Circle']}),
        ('Boxpad', 'Float', 6.0, {'min': -20, 'max': 100, 'label': 'Box padding px'}),
        ('Boxmin', 'Float', 28.0, {'min': 0, 'max': 400, 'label': 'Box min size px'}),
        ('Boxwidth', 'Float', 1.5, {'min': 0.25, 'max': 12, 'label': 'Line width px'}),
        ('Cornerlen', 'Float', 0.25, {'min': 0, 'max': 0.5, 'label': 'Corner length (share of the side)'}),
        ('Cross', 'Float', 8.0, {'min': 0, 'max': 200, 'label': 'Crosshair arm px (0 off)'}),
        ('Crossgap', 'Float', 3.0, {'min': 0, 'max': 100, 'label': 'Crosshair gap px'}),
        ('Labels', 'Menu', 'idpos', {'names': [k for k, _l in _L['LABELS']], 'labels': [b for _k, b in _L['LABELS']]}),
        ('Labelscale', 'Float', 2.0, {'min': 1, 'max': 8, 'label': 'Label pixel size px'}),
        ('Labelgap', 'Float', 4.0, {'min': -50, 'max': 50, 'label': 'Label gap px'}),
        ('Labelbg', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'Label background'}),
        ('Share', 'Float', 0.12, {'min': 0, 'max': 1, 'label': 'Share of points shown (by id)'}),
        ('Minstrength', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Min strength'}),
        ('Flicker', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Label flicker'}),
        ('Flickerhz', 'Float', 8.0, {'min': 0, 'max': 60, 'label': 'Flicker Hz'}),
        ('Seed', 'Int', 1, {'min': 0, 'max': 999, 'label': 'Seed'}),
    ]),
    ('Colour', [
        ('Colsrc', 'Menu', 'solid', {'names': [k for k, _l in _L['COLSRC']], 'labels': [b for _k, b in _L['COLSRC']]}),
        ('Colr', 'Float', 0.25, {'min': 0, 'max': 1, 'label': 'HUD R'}),
        ('Colg', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'HUD G'}),
        ('Colb', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'HUD B'}),
        ('Gain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Gain'}),
        ('Speedref', 'Float', 400.0, {'min': 1, 'max': 4000, 'label': 'Speed for palette end px/s'}),
        ('Bgdim', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Dim the picture'}),
    ]),
    pal_page('neon_trio', 'gradient'),  # noqa: F821
]
PANEL_PAGES = ['Hud', 'Colour', 'Palette']

_SKIP = ('Palstops', 'Palfile')
_D = dict((n, o['names'].index(d) if s == 'Menu' else d) for _pg, pl in PAGES for n, s, d, o in pl if n not in _SKIP)
_D['Palreverse'] = int(_D['Palreverse'])


def _p(**kw):
    return dict(_D, Amount=1.0, **kw)


PRESETS = [
    (1, 'tracker', _p()),
    (2, 'target boxes', _p(Boxstyle=1, Labels=1, Cross=0.0, Colr=1.0, Colg=0.2, Colb=0.25, Share=0.25, Seed=2)),
    (3, 'scan rings', _p(Boxstyle=3, Labels=5, Labelscale=1.0, Cross=14.0, Crossgap=5.0, Colsrc=3, Labelbg=0.0, Share=0.3,
                         Palsource=PAL_SOURCE_NAMES.index('cyan_magenta'), Seed=3)),  # noqa: F821
    (4, 'data storm', _p(Boxstyle=2, Labels=7, Labelscale=1.0, Boxmin=12.0, Flicker=0.35, Flickerhz=14.0,
                         Colsrc=1, Bgdim=0.35, Share=0.6, Seed=4)),
    (5, 'minimal ids', _p(Boxstyle=0, Labels=2, Labelscale=3.0, Labelbg=0.0, Cross=5.0, Crossgap=0.0, Share=0.1,
                          Colr=1.0, Colg=1.0, Colb=1.0, Seed=5)),
]

FX = ("""// hud fx (compute). in0 in1, in1 trk_pts. Per candidate point (valid, strength >= min, id hash <= Share): box /
// corners / circle around its bounds (+ pad, >= min size), crosshair at the centroid, 1-2 label lines (8x8 font) on a
// dark plate above the box, label flicker per id; colour source. Amount mix with in1.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount, box style, box pad px, line width px
uniform vec4 uB;   // box min px, corner share, cross arm px, cross gap px
uniform vec4 uC;   // label mode, label pixel px, label gap px, label bg
uniform vec4 uD;   // share, min strength, flicker, flicker hz
uniform vec4 uE;   // colour r g b, gain
uniform vec4 uF;   // colour source, speed ref px/s, bg dim, seed
uniform vec4 uT;   // time s, label line 0 kind, label line 1 kind, -
uniform vec4 uG;   // detector, cells x, cells y, N
#define FT_PTS sTD2DInputs[1]
""" + PAL_GLSL + _L['GLSL_LIB'] + _L['GLSL_COL'] + """
// tile list (GEN_interactive pattern): the 8x8 workgroup gathers the points whose drawing (box, crosshair, label)
// can touch its tile into shared memory once; each pixel then walks only that list. Ties: the lower point index wins
// (as the mirror's ascending order), so the atomic list order never shows.
shared int sL[256];
shared uint sN;
ivec4 ftTile(vec2 uvlo, vec2 uvhi, vec2 rneg, vec2 rpos) {
    if (uG.x < 0.5) {
        ivec2 cn = ivec2(max(uG.yz, vec2(1.0)));
        ivec2 lo = clamp(ivec2(floor(uvlo * vec2(cn))), ivec2(0), cn - 1);
        ivec2 hi = clamp(ivec2(floor(uvhi * vec2(cn))), ivec2(0), cn - 1);
        ivec2 rn = min(ivec2(ceil(rneg * vec2(cn))), ivec2(FT_REACH));
        ivec2 rp = min(ivec2(ceil(rpos * vec2(cn))), ivec2(FT_REACH));
        return ivec4(max(lo - rn, ivec2(0)), min(hi + rp, cn - 1));
    }
    return ivec4(0, 0, min(int(uG.w), 256) - 1, 0);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 sz = ivec2(uTDOutputInfo.res.zw);
    bool inb = p.x < sz.x && p.y < sz.y;
    vec2 res = vec2(sz), pc = vec2(p) + 0.5;
    int l0 = int(uT.y + 0.5), l1 = int(uT.z + 0.5);
    int nl = (l0 > 0 ? 1 : 0) + (l1 > 0 ? 1 : 0);
    float sc = max(uC.y, 1e-3), w = max(uA.w, 0.25);
    float lw = float(max(ftLineLen(l0), ftLineLen(l1))) * 8.0 * sc;
    float ex = abs(uA.z) + uB.x + uB.z + w + 2.0;                  // box / crosshair extent around a point
    vec2 rneg = vec2(lw + 2.0 * sc + ex, float(nl) * 9.0 * sc + abs(uC.z) + 2.0 * sc + ex) / res;
    vec2 rpos = vec2(ex) / res + vec2(1.0) / max(uG.yz, vec2(1.0));   // + one cell: bounds anywhere in the cell
    int bs = int(uA.y + 0.5);
    uint lid = gl_LocalInvocationIndex;
    if (lid == 0u) sN = 0u;
    barrier();
    vec2 tmin = vec2(gl_WorkGroupID.xy * 8u), tmax = tmin + 8.0;
    ivec4 rg = ftTile((tmin + 0.5) / res, (tmax - 0.5) / res, rneg, rpos);
    int nx = rg.z - rg.x + 1, nc = nx * (rg.w - rg.y + 1);
    for (int k = int(lid); k < min(nc, 4096); k += 64) {
        int i = ftIndex(rg.x + k % nx, rg.y + k / nx);
        vec4 T0 = ftT(i, 0);
        if (T0.w < 0.5) continue;
        vec4 T3 = ftT(i, 3);
        if (ftHash(T3.x, uint(uF.w) + 1u) > uD.x) continue;
        vec4 T1 = ftT(i, 1);
        if (T1.z < uD.y) continue;
        vec4 T2 = ftT(i, 2);
        vec2 b0 = T2.xy * res - uA.z, b1 = T2.zw * res + uA.z;
        vec2 bc = 0.5 * (b0 + b1), hf = max(0.5 * (b1 - b0), vec2(0.5 * uB.x));
        float m = (bs == 3 ? max(hf.x, hf.y) : 0.0) + w + 2.0;
        vec2 r0 = bc - max(hf, vec2(bs == 3 ? max(hf.x, hf.y) : 0.0)) - m, r1 = bc + max(hf, vec2(bs == 3 ? max(hf.x, hf.y) : 0.0)) + m;
        vec2 c = T1.xy * res;
        r0 = min(r0, c - uB.z - w - 2.0); r1 = max(r1, c + uB.z + w + 2.0);
        if (nl > 0) {
            float y0 = bc.y + hf.y + uC.z;
            r0 = min(r0, vec2(bc.x - hf.x - sc - 2.0, y0 - sc - 2.0));
            r1 = max(r1, vec2(bc.x - hf.x + lw + sc + 2.0, y0 + float(nl) * 9.0 * sc + 2.0));
        }
        if (r1.x < tmin.x || r0.x > tmax.x || r1.y < tmin.y || r0.y > tmax.y) continue;
        uint s = atomicAdd(sN, 1u);
        if (s < 256u) sL[s] = i;
    }
    barrier();
    if (!inb) return;                                          // after the barrier (T-154)
    vec4 src = texelFetch(sTD2DInputs[0], p, 0);
    vec3 col = src.rgb * (1.0 - uF.z);
    float ha = 0.0, ba = 0.0;
    int hi = 1 << 30;
    vec3 hc = vec3(0.0);
    int ln = int(min(sN, 256u));
    for (int j = 0; j < 256; j++) {
        if (j >= ln) break;
        int i = sL[j];
        vec4 T1 = ftT(i, 1), T2 = ftT(i, 2), T3 = ftT(i, 3);
        vec2 c = T1.xy * res;
        vec2 b0 = T2.xy * res - uA.z, b1 = T2.zw * res + uA.z;
        vec2 bc = 0.5 * (b0 + b1), hf = max(0.5 * (b1 - b0), vec2(0.5 * uB.x));
        b0 = bc - hf; b1 = bc + hf;
        float a = 0.0;
        if (bs == 1 || bs == 2) {
            vec2 q = abs(pc - bc) - hf;
            float sd = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);
            a = clamp(0.5 * w - abs(sd) + 0.5, 0.0, 1.0);
            if (bs == 2) {
                float L = uB.y * 2.0 * min(hf.x, hf.y);
                vec2 d = abs(pc - bc);
                if (!(d.x >= hf.x - L && d.y >= hf.y - L)) a = 0.0;
            }
        } else if (bs == 3) a = clamp(0.5 * w - abs(length(pc - bc) - max(hf.x, hf.y)) + 0.5, 0.0, 1.0);
        if (uB.z > 0.0) {
            vec2 aq = abs(pc - c);
            float mm = max(aq.x, aq.y);
            if (mm <= uB.z && mm >= uB.w) a = max(a, clamp(0.5 * w - min(aq.x, aq.y) + 0.5, 0.0, 1.0));
        }
        if (nl > 0 && ftHash(T3.x * 7.0 + floor(uT.x * uD.w), uint(uF.w) + 3u) >= uD.z) {
            float y0 = b1.y + uC.z;
            if (pc.x >= b0.x - sc && pc.x < b0.x + lw + sc && pc.y >= y0 - sc && pc.y < y0 + float(nl) * 9.0 * sc)
                ba = max(ba, uC.w);
            vec4 v = vec4(T3.x, floor(c + 0.5), length(T3.zw * res));   // px rounded: centres sit on whole px
            float t = 0.0;
            if (l0 > 0) t = ftText(pc, vec2(b0.x, y0 + float(nl - 1) * 9.0 * sc), sc, l0, l0 == 4 ? vec4(v.xyz, T3.y) : v);
            if (l1 > 0) t = max(t, ftText(pc, vec2(b0.x, y0), sc, l1, l1 == 4 ? vec4(v.xyz, T3.y) : v));
            a = max(a, t);
        }
        if (a > ha || (a == ha && a > 0.0 && i < hi)) { ha = a; hi = i; hc = ftCol(int(uF.x + 0.5), uE.rgb, T1, T3, res, uF.y) * uE.w; }
    }
    col = mix(col, vec3(0.0), ba);
    col = mix(col, hc, ha);
    vec4 o = vec4(col, max(src.a, max(ha, ba)));
    TDImageStoreOutput(0, ivec3(p, 0), mix(src, o, uA.x));
}
""")

SHADERS = {'fx': FX}
NIN = {'fx': 2}

P = "parent().par.{}.eval()"
G = ['parent(2).par.Detector.menuIndex', 'parent(2).par.Cellsx.eval()', 'parent(2).par.Cellsy.eval()',
     ("(int(parent(2).par.Cellsx.eval()) * int(parent(2).par.Cellsy.eval()) if parent(2).par.Detector.eval() == "
      "'cells' else int(parent(2).par.Maxblobs.eval()))")]


def uniforms():
    return {'fx': [
        ('uA', [P.format('Amount'), 'parent().par.Boxstyle.menuIndex', P.format('Boxpad'), P.format('Boxwidth')]),
        ('uB', [P.format('Boxmin'), P.format('Cornerlen'), P.format('Cross'), P.format('Crossgap')]),
        ('uC', ['parent().par.Labels.menuIndex', P.format('Labelscale'), P.format('Labelgap'), P.format('Labelbg')]),
        ('uD', [P.format('Share'), P.format('Minstrength'), P.format('Flicker'), P.format('Flickerhz')]),
        ('uE', [P.format('Colr'), P.format('Colg'), P.format('Colb'), P.format('Gain')]),
        ('uF', ['parent().par.Colsrc.menuIndex', P.format('Speedref'), P.format('Bgdim'), P.format('Seed')]),
        ('uT', ['absTime.seconds', '%r[parent().par.Labels.menuIndex]' % [_L['LABEL_LINES'][k][0] for k in range(8)],
                '%r[parent().par.Labels.menuIndex]' % [_L['LABEL_LINES'][k][1] for k in range(8)], '0']),
        ('uG', G),
    ]}


def build(m, H):
    """in1 + pts -> fx -> out_sel (Amount 0 = in1) -> out1."""
    mk, expr = H['mk'], H['expr']
    U = uniforms()
    in1 = mk(m, inTOP, 'in1')  # noqa: F821
    pts = mk(m, selectTOP, 'pts')  # noqa: F821
    pts.par.top = '../trk_pts'
    pts.comment = "The rack's points (trk_pts)."
    fx = H['pas'](m, 'fx', FX, [in1, pts], 'me.inputs[0].width', 'me.inputs[0].height', 'rgba16float', 'hold')
    H['uniforms'](fx, U['fx'])
    fx.comment = 'HUD: boxes / corners / circles, crosshairs, id + coordinate labels at the tracked points.'
    pal_bind(m, H, [fx])  # noqa: F821
    sel = mk(m, switchTOP, 'out_sel')  # noqa: F821
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, '1 if %s > 0 else 0' % P.format('Amount'))
    sel.comment = 'Amount 0 = in1 exact (fx not pulled).'
    out1 = mk(m, outTOP, 'out1')  # noqa: F821
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pts']},
        {'title': '2 Draw', 'role': 'process', 'ops': ['pal', 'pal_callbacks', 'fx', 'fx_compute'],
         'body': 'Boxes, crosshairs and labels at the tracked points.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 exact.'},
    ]
