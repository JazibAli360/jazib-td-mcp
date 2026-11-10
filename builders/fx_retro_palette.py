# fx_retro_palette - FX_retro module 'palette' (FX2 AV-34 hardware palette quantiser; FX0 row 23).
# Module file = PAGES + PRESETS + shader_texts + build(m, H, Lg) (template: docs/builds/fx_glitch.md; rack:
# builders/fx_retro.py). Virtual pixels (Pixelsize x Pixelaspect, whole px, nearest up) -> nearest entry of a
# hardware palette from the rack's bank (OKLab or sRGB, palette_map's dither rule) or a per-channel bit depth
# (Amiga 12-bit), with two constraints: `cell` = attribute clash (ONE pair of colours per 8x8 virtual-pixel cell,
# Spectrum: both from the same bright half; one workgroup per cell, shared-memory pair search) and `ham` = Amiga HAM6
# (per row, each pixel = a base entry or the previous pixel with one channel set to 4 bits; one thread per row).
# Amount 0 = exact passthrough (out_sel = in1, nothing cooks). ASCII only.

MODULE = 'palette'


def _menu(Lg_menu):
    return [k for k, _l in Lg_menu], [l for _k, l in Lg_menu]


def pages(Lg):
    mk, ml = _menu(Lg['MACHINE_MENU'])
    return [
        ('Palette', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Machine', 'Menu', 'dmg', {'names': mk, 'labels': ml}),
            ('Constraint', 'Menu', 'auto', {'names': Lg['CONSTRAINTS'],
                                            'labels': ['Auto (machine)', 'None', 'Cell 8x8 (2 colours)',
                                                       'HAM (per row)']}),
            ('Pixelsize', 'Float', 4.0, {'min': 1, 'max': 32, 'label': 'Pixel size (px)'}),
            ('Pixelaspect', 'Float', 1.0, {'min': 0.5, 'max': 2, 'label': 'Pixel aspect (w / h)'}),
            ('Sampling', 'Menu', 'box', {'names': ['centre', 'box'], 'labels': ['Centre pixel', 'Box average']}),
            ('Distance', 'Menu', 'oklab', {'names': ['oklab', 'srgb'], 'labels': ['OKLab', 'sRGB']}),
            ('Lightnessweight', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Lightness weight (OKLab)'}),
            ('Dither', 'Menu', 'none', {'names': Lg['DITHER_METHODS'], 'labels': Lg['DITHER_LABELS']}),
            ('Ditheramt', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Dither amount'}),
            ('Ditheranim', 'Float', 0.0, {'min': 0, 'max': 24, 'label': 'Dither animate Hz (0 = still)'}),
            ('Contrast', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Contrast (pre)'}),
            ('Brightness', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Brightness (pre)'}),
            ('Saturation', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Saturation (pre)'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
    ]


PANEL_PAGES = ['Palette']


def presets(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    dm = Lg['DITHER_METHODS']
    base = {'Amount': 1.0, 'Constraint': 0, 'Sampling': 1, 'Distance': 0, 'Lightnessweight': 1.0, 'Ditheramt': 1.0,
            'Ditheranim': 0.0, 'Contrast': 1.0, 'Brightness': 0.0, 'Saturation': 1.0, 'Seed': 1, 'Pixelaspect': 1.0}
    return [
        (1, 'game boy', dict(base, Machine=mk.index('dmg'), Pixelsize=8.0, Dither=dm.index('bayer4'), Ditheramt=0.8,
                             Contrast=1.2)),
        (2, 'nes', dict(base, Machine=mk.index('nes'), Pixelsize=4.0, Pixelaspect=8.0 / 7.0, Dither=dm.index('bayer4'),
                        Ditheramt=0.5)),
        (3, 'c64', dict(base, Machine=mk.index('c64'), Pixelsize=4.0, Pixelaspect=0.936, Dither=0, Saturation=1.2)),
        (4, 'spectrum clash', dict(base, Machine=mk.index('spectrum'), Pixelsize=4.0, Dither=0, Saturation=1.3)),
        (5, 'amiga ham', dict(base, Machine=mk.index('amigaham'), Pixelsize=4.0, Dither=0)),
        (6, 'pico-8', dict(base, Machine=mk.index('pico8'), Pixelsize=6.0, Dither=dm.index('bayer8'),
                           Ditheramt=0.6)),
    ]


COMMON = """// in0 = picture, in1 = rack pal_top (bank), in2 = rack bn_top (blue noise)
uniform vec4 uA;   // amount, bank offset, bank count, kind (0 list, 1 bits)
uniform vec4 uB;   // bits r g b, constraint (0 none, 1 cell, 2 ham)
uniform vec4 uC;   // psx, psy, sampling (0 centre, 1 box), space (0 OKLab, 1 sRGB)
uniform vec4 uD;   // lightness weight, halves rule, dither method, dither amount
uniform vec4 uE;   // contrast, brightness, saturation, dither tick
uniform vec4 uF;   // VW, VH, seed, -
vec3 sampleV(ivec2 v, ivec2 ps, ivec2 res) {                 // straight colour of virtual pixel v
    ivec2 o = v * ps;
    if (uC.z < 0.5) {
        ivec2 c = min(o + ps / 2, res - 1);
        return straight(texelFetch(sTD2DInputs[0], c, 0));
    }
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
vec3 adj(vec3 c) { return preAdjust(c, uE.x, uE.y, uE.z); }
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

FX = """// FX_retro palette: nearest hardware-palette colour per virtual pixel; cell = attribute clash (one compute pass).
layout (local_size_x = 8, local_size_y = 8) in;
%LIB%
%COMMON%
shared vec3 sQ[64];
shared int sV[64];
shared float sCost[64];
shared int sPair[64];
void main() {
    ivec2 v = ivec2(gl_GlobalInvocationID.xy);
    ivec2 res = ivec2(uTDOutputInfo.res.zw);
    ivec2 ps = ivec2(max(int(uC.x + 0.5), 1), max(int(uC.y + 0.5), 1));
    ivec2 vg = ivec2(uF.xy + 0.5);
    bool valid = v.x < vg.x && v.y < vg.y;
    int lid = int(gl_LocalInvocationIndex);
    vec3 c = valid ? adj(sampleV(v, ps, res)) : vec3(0.0);
    bool lab = uC.w < 0.5;
    float wl = uD.x;
    int off = int(uA.y + 0.5), n = max(int(uA.z + 0.5), 1);
    int dm = int(uD.z + 0.5);
    float thr = ditherT(dm, v, uint(uF.z), int(uE.w));      // palette_map rule: t * Ditheramt > thr
    bool dith = dm > 0;
    vec3 o = c;
    int cons = int(uB.w + 0.5);
    if (uA.w > 0.5) {                                        // bit depth machine (Amiga 12-bit)
        float tb = strengthT(thr, uD.w);
        o = vec3(quantL(c.r, exp2(uB.x), tb), quantL(c.g, exp2(uB.y), tb), quantL(c.b, exp2(uB.z), tb));
    } else if (cons == 1) {                                  // attribute clash: workgroup = one 8x8 cell (uniform branch)
        sQ[lid] = lab ? oklab(c) : c;
        sV[lid] = valid ? 1 : 0;
        barrier();
        int P = n * (n - 1) / 2;
        int h = n / 2;
        bool halves = uD.y > 0.5;
        float best = 1e30;
        int bp = 2147483647;
        for (int p = lid; p < P; p += 64) {
            int i = 0, r = p;
            while (r >= n - 1 - i) { r -= n - 1 - i; i++; }
            int j = i + 1 + r;
            if (halves && ((i < h) != (j < h))) continue;
            vec3 qi = palQ(off + i, lab), qj = palQ(off + j, lab);
            float cost = 0.0;
            for (int k = 0; k < 64; k++) {
                if (sV[k] == 0) continue;
                cost += min(pdist(sQ[k], qi, lab, wl), pdist(sQ[k], qj, lab, wl));
            }
            if (cost < best) { best = cost; bp = p; }
        }
        sCost[lid] = best;
        sPair[lid] = bp;
        barrier();
        if (lid == 0) {
            float bc = sCost[0];
            int bpp = sPair[0];
            for (int k = 1; k < 64; k++)
                if (sCost[k] < bc || (sCost[k] == bc && sPair[k] < bpp)) { bc = sCost[k]; bpp = sPair[k]; }
            sPair[0] = bpp;
        }
        barrier();
        int bpw = sPair[0];
        int i = 0, j = 0;
        if (bpw < P) {
            int r = bpw;
            while (r >= n - 1 - i) { r -= n - 1 - i; i++; }
            j = i + 1 + r;
        }
        float di = pdist(sQ[lid], palQ(off + i, lab), lab, wl), dj = pdist(sQ[lid], palQ(off + j, lab), lab, wl);
        int pk = dj < di ? 1 : 0;                            // palette_map nearest2 order on (i, j): i wins ties
        int k1 = pk == 1 ? j : i, k2 = pk == 1 ? i : j;
        float d1 = min(di, dj), d2 = pk == 1 ? di : dj;
        int sel = pickT(d1, d2, k1, k2, i == j ? 1 : 2, dith, thr, uD.w);
        o = palRgb(off + sel);
    } else {
        o = palRgb(off + pickPal(c, lab, wl, off, n, dith, thr, uD.w));
    }
    if (valid) writeBlock(v, ps, res, o);
}
"""

HAM = """// FX_retro palette HAM6: one workgroup per virtual row. The 64 threads compute each pixel's colour, OKLab and best
// base entry in parallel (256-px chunks in shared memory); thread 0 then runs the hold-and-modify scan (3 candidates
// per pixel, sequential by nature); then all 64 write the blocks. (Live 31550: one thread per row doing all of it was
// 4-9 ms at Pixelsize 3-6.) Shared: 4 x 256 vec4 = 16 KB.
layout (local_size_x = 64, local_size_y = 1) in;
%LIB%
%COMMON%
shared vec4 sC[256];                                         // c.rgb, best base distance
shared vec4 sQ[256];                                         // c in the distance space
shared vec4 sB[256];                                         // best base rgb
shared vec4 sO[256];                                         // chosen colour
shared vec4 sPrev;
void main() {
    int row = int(gl_WorkGroupID.x), lx = int(gl_LocalInvocationID.x);
    ivec2 res = ivec2(uTDOutputInfo.res.zw);
    ivec2 ps = ivec2(max(int(uC.x + 0.5), 1), max(int(uC.y + 0.5), 1));
    ivec2 vg = ivec2(uF.xy + 0.5);
    if (row >= vg.y) return;                                 // whole workgroup returns together (barriers stay uniform)
    bool lab = uC.w < 0.5;
    float wl = uD.x;
    int off = int(uA.y + 0.5), n = max(int(uA.z + 0.5), 1);
    if (lx == 0) sPrev = vec4(palRgb(off), 0.0);             // border = base entry 0
    for (int x0 = 0; x0 < vg.x; x0 += 256) {
        int cnt = min(256, vg.x - x0);
        for (int i = lx; i < cnt; i += 64) {
            vec3 c = adj(sampleV(ivec2(x0 + i, row), ps, res));
            vec3 q = lab ? oklab(c) : c;
            float best = 1e30;
            vec3 o = vec3(0.0);
            for (int j = 0; j < n; j++) {
                float d = pdist(q, palQ(off + j, lab), lab, wl);
                if (d < best) { best = d; o = palRgb(off + j); }
            }
            sC[i] = vec4(c, best); sQ[i] = vec4(q, 0.0); sB[i] = vec4(o, 0.0);
        }
        barrier();
        if (lx == 0) {
            vec3 prev = sPrev.rgb;
            for (int i = 0; i < cnt; i++) {
                vec3 c = sC[i].rgb, q = sQ[i].rgb;
                float best = sC[i].w;
                vec3 o = best < 1e30 ? sB[i].rgb : prev;
                for (int k = 0; k < 3; k++) {
                    vec3 m = prev;
                    m[k] = floor(c[k] * 15.0 + 0.5) / 15.0;
                    float d = pdist(q, lab ? oklab(m) : m, lab, wl);
                    if (d < best) { best = d; o = m; }
                }
                prev = o;
                sO[i] = vec4(o, 0.0);
            }
            sPrev = vec4(prev, 0.0);
        }
        barrier();
        for (int i = lx; i < cnt; i += 64) writeBlock(ivec2(x0 + i, row), ps, res, sO[i].rgb);
        barrier();
    }
}
"""


def shader_texts(lib):
    """{op name: compute shader text}; lib = rack glsl_lib bound to the logic (pal_in, bn_in keywords)."""
    L = lib(pal_in=1, bn_in=2)
    return {'fx': FX.replace('%LIB%', L).replace('%COMMON%', COMMON),
            'ham': HAM.replace('%LIB%', L).replace('%COMMON%', COMMON)}


def uniforms(H, Lg):
    P, LX = H['P'], H['LX']
    mach = "parent().par.Machine.eval()"
    W, Hh = 'me.inputs[0].width', 'me.inputs[0].height'
    grid = "%s.vgrid(%s, %s, %s, %s)" % (LX, W, Hh, P.format('Pixelsize'), P.format('Pixelaspect'))
    slot = "%s.bank_slot(%s, parent(2).op('pal_bank').numRows)" % (LX, mach)
    bits = "%s.machine_bits(%s)" % (LX, mach)
    tick = "int(absTime.seconds * %s) if %s > 0 else 0" % (P.format('Ditheranim'), P.format('Ditheranim'))
    return [
        ('uA', [P.format('Amount'), slot + '[0]', slot + '[1]', slot + '[2]']),
        ('uB', [bits + '[0]', bits + '[1]', bits + '[2]',
                "%s.constraint_index(parent().par.Constraint.eval(), %s)" % (LX, mach)]),
        ('uC', [grid + '[0]', grid + '[1]', 'parent().par.Sampling.menuIndex', 'parent().par.Distance.menuIndex']),
        ('uD', [P.format('Lightnessweight'), "%s.halves(%s)" % (LX, mach), 'parent().par.Dither.menuIndex',
                P.format('Ditheramt')]),
        ('uE', [P.format('Contrast'), P.format('Brightness'), P.format('Saturation'), tick]),
        ('uF', [grid + '[2]', grid + '[3]', P.format('Seed'), '0']),
    ], grid


def build(m, H, Lg):
    """in1 -> fx (per virtual pixel / cell) | ham (per row) -> out_sel (0 in1 at Amount 0, 1 fx, 2 ham) -> out1."""
    mk, expr, compute, LX = H['mk'], H['expr'], H['compute'], H['LX']
    in1 = mk(m, inTOP, 'in1')
    pal = H['select'](m, 'pal', '../pal_top')
    pal.comment = 'Rack palette bank (width = entries, rows r g b L A B).'
    bn = H['select'](m, 'bn', '../bn_top')
    bn.comment = 'Rack blue noise 64x64.'
    U, grid = uniforms(H, Lg)
    sh = shader_texts(lambda **k: H['glsl_lib'](Lg, **k))
    W, Hh = 'me.inputs[0].width', 'me.inputs[0].height'
    fx = compute(m, 'fx', sh['fx'], [in1, pal, bn], W, Hh, uniforms=U,
                 dispatch=('%s.groups(%s[2], 8)' % (LX, grid), '%s.groups(%s[3], 8)' % (LX, grid)))
    fx.comment = 'palette: nearest entry per virtual pixel; Constraint cell = 2 colours per 8x8 cell (workgroup).'
    ham = compute(m, 'ham', sh['ham'], [in1, pal, bn], W, Hh, uniforms=U,
                  dispatch=('%s[3]' % grid, '1'))
    ham.comment = 'palette HAM6: one workgroup per virtual row (parallel base search, sequential hold-and-modify).'
    sel = mk(m, switchTOP, 'out_sel')
    for k, s in enumerate((in1, fx, ham)):
        sel.inputConnectors[k].connect(s)
    expr(sel.par.index, "0 if parent().par.Amount.eval() <= 0 else (2 if %s.constraint_index("
                        "parent().par.Constraint.eval(), parent().par.Machine.eval()) == 2 and %s.bank_slot("
                        "parent().par.Machine.eval())[2] == 0 else 1)" % (LX, LX))
    sel.comment = 'Amount 0 = in1 exactly (fx / ham not pulled); HAM constraint -> ham.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pal', 'bn'], 'body': 'Picture, rack palette bank, blue noise.'},
        {'title': '2 Palette', 'role': 'process', 'ops': ['fx', 'fx_compute', 'ham', 'ham_compute'],
         'body': 'fx: nearest / cell clash (one pass). ham: HAM6 rows.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


# module API the rack reads (PAGES / PRESETS need the logic tables: filled by the rack exec namespace)
try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:                                        # exec'd alone (tests): the test sets them
    PAGES, PRESETS = None, None
