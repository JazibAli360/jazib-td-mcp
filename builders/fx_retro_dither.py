# fx_retro_dither - FX_retro module 'dither' (FX2 AV-35 dither engine, FX5 G25, FX3 S4; FX0 row 23).
# Module file = pages / presets + shader_texts + build(m, H, Lg) (template: docs/builds/fx_glitch.md; rack:
# builders/fx_retro.py). Per virtual pixel (Pixelsize, whole px): ordered dither (Bayer 2-16, IGN, white, 64x64 blue
# noise from the rack, Animate Hz offsets the pattern), Game Boy Camera style (contrast + edge enhance + Bayer 4x4
# to the ranks of a 4-entry palette), or error diffusion (Floyd-Steinberg, Atkinson, Sierra Lite, Jarvis, Stucki,
# Burkes) run TILE-PARALLEL: one thread per Tile x Tile block, serial raster scan (serpentine option), errors that
# leave the tile are dropped (FX2 AV-35 option a: seams only at high zoom). Targets: Levels per channel, luma levels or
# a rack palette (Machine). Amount 0 = exact passthrough (out_sel = in1). ASCII only.

MODULE = 'dither'


def pages(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    ml = [l for _k, l in Lg['MACHINE_MENU']]
    return [
        ('Dither', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Method', 'Menu', 'bayer8', {'names': Lg['DITHER_ALL'], 'labels': Lg['DITHER_ALL_LABELS']}),
            ('Colour', 'Menu', 'rgb', {'names': ['rgb', 'luma', 'palette'],
                                       'labels': ['Levels per channel', 'Grey levels', 'Palette (Machine)']}),
            ('Levels', 'Int', 2, {'min': 2, 'max': 16, 'label': 'Levels'}),
            ('Machine', 'Menu', 'dmg', {'names': mk, 'labels': ml}),
            ('Pixelsize', 'Float', 1.0, {'min': 1, 'max': 16, 'label': 'Pixel size (px)'}),
            ('Strength', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Strength'}),
            ('Animate', 'Float', 0.0, {'min': 0, 'max': 24, 'label': 'Animate Hz (0 = still)'}),
            ('Linear', 'Toggle', False, {'label': 'Quantise in linear light'}),
            ('Distance', 'Menu', 'oklab', {'names': ['oklab', 'srgb'], 'labels': ['OKLab', 'sRGB']}),
            ('Contrast', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Contrast (pre)'}),
            ('Brightness', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Brightness (pre)'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
        ('Diffusion', [
            ('Tile', 'Int', 16, {'min': 4, 'max': 64, 'label': 'Tile (virtual px, <= 64)'}),
            ('Serpentine', 'Toggle', True, {'label': 'Serpentine rows'}),
            ('Gbcontrast', 'Float', 1.4, {'min': 0, 'max': 4, 'label': 'GB Cam contrast'}),
            ('Gbedge', 'Float', 0.35, {'min': 0, 'max': 2, 'label': 'GB Cam edge enhance'}),
        ]),
    ]


PANEL_PAGES = ['Dither', 'Diffusion']


def presets(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    dm = Lg['DITHER_ALL']
    base = {'Amount': 1.0, 'Pixelsize': 1.0, 'Strength': 1.0, 'Animate': 0.0, 'Linear': 0, 'Distance': 0,
            'Contrast': 1.0, 'Brightness': 0.0, 'Seed': 1, 'Tile': 16, 'Serpentine': 1}
    return [
        (1, 'bayer 1-bit', dict(base, Method=dm.index('bayer8'), Colour=1, Levels=2, Pixelsize=2.0)),
        (2, 'blue 4-level', dict(base, Method=dm.index('blue'), Colour=0, Levels=4)),
        (3, 'atkinson mac', dict(base, Method=dm.index('atkinson'), Colour=1, Levels=2, Pixelsize=2.0)),
        (4, 'gb camera', dict(base, Method=dm.index('gbcam'), Colour=2, Machine=mk.index('dmg'), Pixelsize=8.0,
                              Gbcontrast=1.4, Gbedge=0.35)),
        (5, 'floyd pico-8', dict(base, Method=dm.index('fs'), Colour=2, Machine=mk.index('pico8'), Pixelsize=3.0)),
        (6, 'shimmer', dict(base, Method=dm.index('ign'), Colour=0, Levels=3, Animate=12.0)),
    ]


COMMON = """// in0 = picture, in1 = rack pal_top (bank), in2 = rack bn_top (blue noise)
uniform vec4 uA;   // amount, method (DITHER_ALL index), colour (0 rgb, 1 luma, 2 palette), levels
uniform vec4 uB;   // psx, psy, strength, tick
uniform vec4 uC;   // bank offset, bank count, space (0 OKLab, 1 sRGB), linear
uniform vec4 uD;   // contrast, brightness, GB contrast, GB edge
uniform vec4 uE;   // VW, VH, seed, lightness weight
uniform vec4 uG;   // tile, serpentine, -, -
vec3 sampleV(ivec2 v, ivec2 ps, ivec2 res) {                 // box average of virtual pixel v (straight colour)
    ivec2 o = v * ps;
    vec3 acc = vec3(0.0);
    int n = 0;
    for (int y = 0; y < ps.y; y++) {
        int yy = o.y + y;
        if (yy >= res.y) break;
        for (int x = 0; x < ps.x; x++) {
            int xx = o.x + x;
            if (xx >= res.x) break;
            acc += straight(texelFetch(sTD2DInputs[0], ivec2(xx, yy), 0));
            n++;
        }
    }
    return acc / float(max(n, 1));
}
vec3 adj(vec3 c) { return preAdjust(c, uD.x, uD.y, 1.0); }
void writeBlock(ivec2 v, ivec2 ps, ivec2 res, vec3 o) {
    ivec2 b = v * ps;
    for (int y = 0; y < ps.y; y++) {
        int yy = b.y + y;
        if (yy >= res.y) break;
        for (int x = 0; x < ps.x; x++) {
            int xx = b.x + x;
            if (xx >= res.x) break;
            vec4 s = texelFetch(sTD2DInputs[0], ivec2(xx, yy), 0);
            vec3 c = mix(straight(s), o, uA.x);
            TDImageStoreOutput(0, ivec3(xx, yy, 0), TDOutputSwizzle(vec4(c * s.a, s.a)));
        }
    }
}
"""

FX = """// FX_retro dither: ordered / GB Camera, one thread per virtual pixel (no barriers).
layout (local_size_x = 8, local_size_y = 8) in;
%LIB%
%COMMON%
void main() {
    ivec2 v = ivec2(gl_GlobalInvocationID.xy);
    ivec2 res = ivec2(uTDOutputInfo.res.zw);
    ivec2 ps = ivec2(max(int(uB.x + 0.5), 1), max(int(uB.y + 0.5), 1));
    ivec2 vg = ivec2(uE.xy + 0.5);
    if (v.x >= vg.x || v.y >= vg.y) return;
    vec3 c = adj(sampleV(v, ps, res));
    int m = int(uA.y + 0.5), cm = int(uA.z + 0.5);
    bool lab = uC.z < 0.5, lin = uC.w > 0.5;
    int off = int(uC.x + 0.5), n = max(int(uC.y + 0.5), 1);
    uint seed = uint(uE.z);
    int tick = int(uB.w);
    vec3 o;
    if (m == 8) {                                            // Game Boy Camera style
        float y = luma(c);
        float nb = 0.0;
        for (int k = 0; k < 4; k++) {
            ivec2 d = k == 0 ? ivec2(1, 0) : k == 1 ? ivec2(-1, 0) : k == 2 ? ivec2(0, 1) : ivec2(0, -1);
            nb += luma(adj(sampleV(clamp(v + d, ivec2(0), vg - 1), ps, res)));
        }
        float t = strengthT(ditherT(2, v, seed, tick), uB.z);
        float val = (y - 0.5) * uD.z + 0.5 + uD.w * (4.0 * y - nb);
        int lev = int(quantL(val, float(n), t) * float(n - 1) + 0.5);
        int pick = 0;
        for (int i = 0; i < n; i++) {                        // the entry whose OKLab-L rank is lev
            float li = palLab(off + i).x;
            int rk = 0;
            for (int j = 0; j < n; j++) {
                float lj = palLab(off + j).x;
                if (lj < li || (lj == li && j < i)) rk++;
            }
            if (rk == lev) pick = i;
        }
        o = palRgb(off + pick);
    } else {
        float t0 = ditherT(m, v, seed, tick);
        if (cm == 2) {
            o = palRgb(off + pickPal(c, lab, uE.w, off, n, m > 0, t0, uB.z));     // palette_map rule
        } else {
            float t = strengthT(t0, uB.z);
            vec3 x = lin ? toLin(c) : c;
            x = cm == 1 ? vec3(quantL(luma(x), uA.w, t))
                        : vec3(quantL(x.r, uA.w, t), quantL(x.g, uA.w, t), quantL(x.b, uA.w, t));
            o = lin ? toSrgb(x) : x;
        }
    }
    writeBlock(v, ps, res, o);
}
"""

FXD = """// FX_retro dither: tile-parallel error diffusion (one thread = one Tile x Tile block, serial raster scan).
// Errors live in colour buffer 1 as a 3-row ring per thread, interleaved by thread (texel index
// ((row % 3) * T + x) * NT + t) so neighbouring threads touch neighbouring texels; each thread owns its ring: no
// races, no shared memory. (Live 31550: a 12 KB shared ring per 4-thread group left ~8 threads per GPU core:
// 12-17 ms at any Tile; buffer 1 lets 64-thread groups run.) 3 * N / T texels fit for T >= 3.
layout (local_size_x = 64, local_size_y = 1) in;
%LIB%
%COMMON%
int gT, gNT, gt, gRX;
ivec3 eAt(int x, int row) { int i = ((row % 3) * gT + x) * gNT + gt; return ivec3(i % gRX, i / gRX, 0); }
vec3 eGet(int x, int row) { return TDImageLoadOutput(1, eAt(x, row)).rgb; }
void eSet(int x, int row, vec3 e) { TDImageStoreOutput(1, eAt(x, row), vec4(e, 0.0)); }
vec3 quantD(vec3 c, int cm, bool lab, int off, int n) {
    if (cm == 2) return palRgb(off + pickPal(clamp(c, 0.0, 1.0), lab, uE.w, off, n, false, 0.5, 1.0));
    if (cm == 1) return vec3(quantL(luma(c), uA.w, 0.5));
    return vec3(quantL(c.r, uA.w, 0.5), quantL(c.g, uA.w, 0.5), quantL(c.b, uA.w, 0.5));
}
void main() {
    int t = int(gl_GlobalInvocationID.x);
    ivec2 res = ivec2(uTDOutputInfo.res.zw);
    ivec2 ps = ivec2(max(int(uB.x + 0.5), 1), max(int(uB.y + 0.5), 1));
    ivec2 vg = ivec2(uE.xy + 0.5);
    int T = clamp(int(uG.x + 0.5), 4, 64);
    int TX = (vg.x + T - 1) / T, TY = (vg.y + T - 1) / T;
    if (t >= TX * TY) return;
    gT = T; gNT = TX * TY; gt = t; gRX = res.x;
    int x0 = (t % TX) * T, r0 = (t / TX) * T;                // tile rows counted from the TOP
    int w = min(T, vg.x - x0), h = min(T, vg.y - r0);
    int cm = int(uA.z + 0.5);
    bool lab = uC.z < 0.5, lin = uC.w > 0.5 && cm != 2, serp = uG.y > 0.5;
    int off = int(uC.x + 0.5), n = max(int(uC.y + 0.5), 1);
    ivec2 kr = KRANGE[clamp(int(uA.y + 0.5) - 9, 0, 5)];
    for (int r = 0; r < min(3, h); r++)
        for (int x = 0; x < w; x++) eSet(x, r, vec3(0.0));
    for (int r = 0; r < h; r++) {
        if (r > 0 && r + 2 < h)
            for (int x = 0; x < w; x++) eSet(x, r + 2, vec3(0.0));
        bool rev = serp && (r & 1) == 1;
        int vy = vg.y - 1 - (r0 + r);
        for (int i = 0; i < w; i++) {
            int x = rev ? w - 1 - i : i;
            ivec2 v = ivec2(x0 + x, vy);
            vec3 c = adj(sampleV(v, ps, res));
            if (lin) c = toLin(c);
            c += eGet(x, r);
            vec3 q = quantD(c, cm, lab, off, n);
            vec3 e = c - q;
            for (int k = kr.x; k < kr.x + kr.y; k++) {
                vec3 kt = KTAB[k];
                int dx = int(kt.x), dy = int(kt.y);
                int xx = x + (rev ? -dx : dx), yy = r + dy;
                if (xx < 0 || xx >= w || yy >= h) continue;
                eSet(xx, yy, eGet(xx, yy) + e * kt.z);
            }
            writeBlock(v, ps, res, lin ? toSrgb(q) : q);
        }
    }
}
"""


def shader_texts(lib):
    L = lib(pal_in=1, bn_in=2)
    LK = lib(pal_in=1, bn_in=2, kernels=True)
    return {'fx': FX.replace('%LIB%', L).replace('%COMMON%', COMMON),
            'fxd': FXD.replace('%LIB%', LK).replace('%COMMON%', COMMON)}


def uniforms(H):
    P, LX = H['P'], H['LX']
    mach = "parent().par.Machine.eval()"
    W, Hh = 'me.inputs[0].width', 'me.inputs[0].height'
    grid = "%s.vgrid(%s, %s, %s)" % (LX, W, Hh, P.format('Pixelsize'))
    slot = "%s.bank_slot(%s, parent(2).op('pal_bank').numRows)" % (LX, mach)
    tick = "int(absTime.seconds * %s) if %s > 0 else 0" % (P.format('Animate'), P.format('Animate'))
    return [
        ('uA', [P.format('Amount'), 'parent().par.Method.menuIndex', 'parent().par.Colour.menuIndex',
                P.format('Levels')]),
        ('uB', [grid + '[0]', grid + '[1]', P.format('Strength'), tick]),
        ('uC', [slot + '[0]', slot + '[1]', 'parent().par.Distance.menuIndex', '1 if %s else 0' % P.format('Linear')]),
        ('uD', [P.format('Contrast'), P.format('Brightness'), P.format('Gbcontrast'), P.format('Gbedge')]),
        ('uE', [grid + '[2]', grid + '[3]', P.format('Seed'), '1.0']),
        ('uG', [P.format('Tile'), '1 if %s else 0' % P.format('Serpentine'), '0', '0']),
    ], grid


def build(m, H, Lg):
    """in1 -> fx (ordered / GB Cam) | fxd (diffusion tiles) -> out_sel (0 in1 at Amount 0, 1 fx, 2 fxd) -> out1."""
    mk, expr, compute, LX = H['mk'], H['expr'], H['compute'], H['LX']
    in1 = mk(m, inTOP, 'in1')
    pal = H['select'](m, 'pal', '../pal_top')
    bn = H['select'](m, 'bn', '../bn_top')
    U, grid = uniforms(H)
    sh = shader_texts(lambda **k: H['glsl_lib'](Lg, **k))
    W, Hh = 'me.inputs[0].width', 'me.inputs[0].height'
    fx = compute(m, 'fx', sh['fx'], [in1, pal, bn], W, Hh, uniforms=U,
                 dispatch=('%s.groups(%s[2], 8)' % (LX, grid), '%s.groups(%s[3], 8)' % (LX, grid)))
    fx.comment = 'dither: ordered (Bayer / IGN / white / blue) + GB Camera, per virtual pixel.'
    tiles = "%s.groups(%s[2], max(4, min(64, %s))) * %s.groups(%s[3], max(4, min(64, %s)))" % (
        LX, grid, H['P'].format('Tile'), LX, grid, H['P'].format('Tile'))
    fxd = compute(m, 'fxd', sh['fxd'], [in1, pal, bn], W, Hh, fmt='rgba32float', uniforms=U, readwrite=True,
                  bufs=2, dispatch=('%s.groups(%s, 64)' % (LX, tiles), '1'))
    fxd.comment = 'dither: error diffusion, one thread per Tile block (tile-parallel, errors stop at tile edges).'
    sel = mk(m, switchTOP, 'out_sel')
    for k, s in enumerate((in1, fx, fxd)):
        sel.inputConnectors[k].connect(s)
    expr(sel.par.index, "0 if parent().par.Amount.eval() <= 0 else (2 if parent().par.Method.menuIndex >= 9 else 1)")
    sel.comment = 'Amount 0 = in1 exactly; diffusion methods -> fxd, the rest -> fx (only the selected pass cooks).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pal', 'bn'], 'body': 'Picture, rack palette bank, blue noise.'},
        {'title': '2 Dither', 'role': 'process', 'ops': ['fx', 'fx_compute', 'fxd', 'fxd_compute'],
         'body': 'fx: ordered / GB Cam per virtual px. fxd: diffusion tiles.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
