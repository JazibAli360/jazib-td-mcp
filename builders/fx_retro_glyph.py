# fx_retro_glyph - FX_retro module 'glyph' (FX2 AV-39 text-mode, FX5 G21 glyph rain, G-ASCII; FX0 row 60).
# Module file = pages / presets + shader_texts + build(m, H, Lg) (template: docs/builds/fx_glitch.md; rack:
# builders/fx_retro.py). ONE compute pass, one workgroup (8x8 threads) per character cell: the 64 threads sample the
# cell on an 8x8 grid into shared memory, then
#   ascii    - cell luma (Contrast, Gamma, Invert) picks a glyph from a brightness ramp (Charset / Chars);
#   matrix   - falling glyph columns (Layers streams per column, Speed, Trail, Density, Changerate, head colour),
#              optionally masked by the cell luma or tinted with its colour (Rainmask);
#   textmode - the cell's 8x8 pattern (brighter than its mean) is matched against every glyph of Shapeset by
#              popcount(pattern ^ glyph) (inverted glyphs allowed), with fg / bg = the mean colours of the two halves
#              (or quantised to a rack palette: EGA 16 by default) - ANSI / CP437 style art.
# Glyphs: the rack's 8x8 public-domain font (fx_retro_font8x8: ASCII, block elements, hiragana). Amount 0 = exact
# passthrough (out_sel = in1). ASCII only.

MODULE = 'glyph'


def pages(Lg):
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    ml = [l for _k, l in Lg['MACHINE_MENU']]
    return [
        ('Glyph', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Mode', 'Menu', 'ascii', {'names': ['ascii', 'matrix', 'textmode'],
                                       'labels': ['ASCII (luma ramp)', 'Matrix rain', 'Text mode (shape match)']}),
            ('Cellw', 'Int', 12, {'min': 4, 'max': 64, 'label': 'Cell width (px)'}),
            ('Cellh', 'Int', 12, {'min': 4, 'max': 64, 'label': 'Cell height (px)'}),
            ('Charset', 'Menu', 'ascii', {'names': Lg['CHARSETS'], 'labels': Lg['CHARSET_LABELS']}),
            ('Shapeset', 'Menu', 'basic+blocks', {'names': Lg['SHAPESETS'],
                                                  'labels': ['ASCII', 'Blocks', 'ASCII + blocks', 'All glyphs']}),
            ('Colour', 'Menu', 'source', {'names': ['source', 'mono', 'two', 'palette'],
                                          'labels': ['Source colour', 'Mono (Fg)', 'Two colour (Fg / Bg)',
                                                     'Palette (Machine)']}),
            ('Machine', 'Menu', 'cga16', {'names': mk, 'labels': ml}),
            ('Bgmode', 'Menu', 'black', {'names': ['black', 'dim', 'transparent', 'colour'],
                                         'labels': ['Black', 'Source dimmed', 'Transparent', 'Bg colour']}),
            ('Bgdim', 'Float', 0.15, {'min': 0, 'max': 1, 'label': 'Source dim'}),
            ('Contrast', 'Float', 1.0, {'min': 0, 'max': 3, 'label': 'Contrast'}),
            ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 3, 'label': 'Gamma'}),
            ('Invert', 'Toggle', False, {'label': 'Invert ramp'}),
            ('Smooth', 'Toggle', False, {'label': 'Smooth glyph diagonals'}),
        ]),
        ('Matrix', [
            ('Speed', 'Float', 12.0, {'min': 0, 'max': 60, 'label': 'Fall speed (cells/s)'}),
            ('Trail', 'Float', 14.0, {'min': 1, 'max': 80, 'label': 'Trail (cells)'}),
            ('Density', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Column density'}),
            ('Layers', 'Int', 2, {'min': 1, 'max': 4, 'label': 'Streams per column'}),
            ('Changerate', 'Float', 6.0, {'min': 0, 'max': 30, 'label': 'Glyph change Hz'}),
            ('Rainmask', 'Menu', 'none', {'names': ['none', 'luma', 'colour'],
                                          'labels': ['None', 'Source luma', 'Source colour']}),
            ('Mirror', 'Toggle', True, {'label': 'Mirror glyphs'}),
            ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
        ]),
        ('Colours', [
            ('Fg', 'RGB', (0.25, 1.0, 0.45), {'label': 'Fg'}),
            ('Bg', 'RGB', (0.0, 0.05, 0.02), {'label': 'Bg'}),
            ('Head', 'RGB', (0.85, 1.0, 0.9), {'label': 'Rain head'}),
        ]),
        ('Content', [
            ('Chars', 'Str', ' .:oO@', {'label': 'Chars (Charset = Custom)'}),
        ]),
    ]


PANEL_PAGES = ['Glyph', 'Matrix', 'Colours']


def presets(Lg):
    cs = Lg['CHARSETS']
    mk = [k for k, _l in Lg['MACHINE_MENU']]
    base = {'Amount': 1.0, 'Cellw': 12, 'Cellh': 12, 'Bgdim': 0.15, 'Contrast': 1.0, 'Gamma': 1.0, 'Invert': 0,
            'Smooth': 0}
    return [
        (1, 'ascii colour', dict(base, Mode=0, Charset=cs.index('ascii'), Colour=0, Bgmode=0)),
        (2, 'green terminal', dict(base, Mode=0, Charset=cs.index('dense'), Colour=1, Bgmode=0, Cellw=10, Cellh=16,
                                   Fgr=0.3, Fgg=1.0, Fgb=0.35, Contrast=1.3)),
        (3, 'matrix rain', dict(base, Mode=1, Charset=cs.index('hiragana'), Colour=1, Bgmode=1, Bgdim=0.12,
                                Cellw=16, Cellh=18, Speed=14.0, Trail=16.0, Density=0.75, Layers=2, Changerate=6.0,
                                Rainmask=1, Mirror=1)),
        (4, 'ega textmode', dict(base, Mode=2, Shapeset=2, Colour=3, Machine=mk.index('cga16'), Cellw=8, Cellh=16)),
        (5, 'blocks', dict(base, Mode=0, Charset=cs.index('blocks'), Colour=2, Bgmode=3, Cellw=16, Cellh=16,
                           Fgr=1.0, Fgg=0.75, Fgb=0.2, Bgr=0.05, Bgg=0.02, Bgb=0.1)),
    ]


FX = """// FX_retro glyph: one workgroup per character cell (ascii / matrix / textmode), one compute pass.
// in0 = picture, in1 = rack pal_top (bank). Cells counted from the TOP-left.
layout (local_size_x = 8, local_size_y = 8) in;
%LIB%
uniform vec4 uA;   // amount, mode (0 ascii, 1 matrix, 2 textmode), cell w, cell h (px)
uniform vec4 uB;   // colour (0 source, 1 mono, 2 two, 3 palette), bgmode (0 black, 1 dim, 2 transparent, 3 colour), bg dim, invert
uniform vec4 uC;   // contrast, gamma, smooth, mirror
uniform vec4 uD;   // fg rgb, -
uniform vec4 uE;   // bg rgb, -
uniform vec4 uH;   // head rgb, -
uniform vec4 uR0;  // ramp: 3 glyphs (g + 1, bytes) per float
uniform vec4 uR1;
uniform vec4 uR2;  // .w = ramp length
uniform vec4 uM;   // speed, trail, density, change rate
uniform vec4 uN;   // layers, rainmask (0 none, 1 luma, 2 colour), time s, seed
uniform vec4 uP;   // bank offset, bank count, shape range lo, hi
shared vec3 sC[64];
shared float sL[64];
shared vec4 sR[64];                                          // tree reductions (live 31550: lid-0 loops were the cost)
shared vec4 sR2[64];
shared vec4 sMean;
shared vec3 sFg;
shared vec3 sBg;
shared uint sPat[2];
shared int sScore[64];
shared int sOrd[64];
shared int sGlyph;
shared float sBright;
shared int sHead;
int rampN() { return clamp(int(uR2.w + 0.5), 1, 33); }
int rampAt(int i) {
    float R[12] = float[12](uR0.x, uR0.y, uR0.z, uR0.w, uR1.x, uR1.y, uR1.z, uR1.w, uR2.x, uR2.y, uR2.z, uR2.w);
    i = clamp(i, 0, 32);
    uint f = uint(R[i / 3] + 0.5);
    return int((f >> uint(8 * (i % 3))) & 255u) - 1;
}
vec3 nearestPal(vec3 c) {
    int off = int(uP.x + 0.5), n = max(int(uP.y + 0.5), 1);
    return palRgb(off + pickPal(c, true, 1.0, off, n, false, 0.5, 1.0));
}
void main() {
    ivec2 res = ivec2(uTDOutputInfo.res.zw);
    ivec2 cs = ivec2(max(int(uA.z + 0.5), 1), max(int(uA.w + 0.5), 1));
    ivec2 cell = ivec2(gl_WorkGroupID.xy);                   // x, row from the top
    ivec2 t = ivec2(gl_LocalInvocationID.xy);               // t.y = glyph row from the top
    int lid = t.y * 8 + t.x;
    int mode = int(uA.y + 0.5);
    ivec2 rows = (res + cs - 1) / cs;
    // 1. sample the cell on an 8x8 grid (bilinear, clamped)
    vec2 pxy = vec2(float(cell.x * cs.x) + (float(t.x) + 0.5) * float(cs.x) / 8.0,
                    float(res.y) - (float(cell.y * cs.y) + (float(t.y) + 0.5) * float(cs.y) / 8.0));
    vec3 c = straight(textureLod(sTD2DInputs[0], clamp(pxy, vec2(0.5), vec2(res) - 0.5) / vec2(res), 0.0));
    float cl = luma(c);
    sC[lid] = c;
    sL[lid] = cl;
    sR[lid] = vec4(c, cl);
    if (lid < 2) sPat[lid] = 0u;
    barrier();
    for (int st = 32; st > 0; st >>= 1) {                    // mean: 6-step tree
        if (lid < st) sR[lid] += sR[lid + st];
        barrier();
    }
    vec4 mean = sR[0] / 64.0;
    if (lid == 0) sMean = mean;
    if (mode == 2) {                                         // pattern (bit per thread) + the two half means
        bool up = cl > mean.w;
        if (up) atomicOr(sPat[lid >> 5], 1u << uint(lid & 31));
        barrier();                                           // every thread has read sR[0] before it is reused
        sR[lid] = up ? vec4(c, 1.0) : vec4(0.0);
        sR2[lid] = up ? vec4(0.0) : vec4(c, 1.0);
        barrier();
        for (int st = 32; st > 0; st >>= 1) {
            if (lid < st) { sR[lid] += sR[lid + st]; sR2[lid] += sR2[lid + st]; }
            barrier();
        }
        if (lid == 0) {
            sFg = sR[0].w > 0.5 ? sR[0].rgb / sR[0].w : mean.rgb;
            sBg = sR2[0].w > 0.5 ? sR2[0].rgb / sR2[0].w : mean.rgb;
        }
    }
    barrier();
    // 2. pick the glyph
    if (mode == 2) {                                         // textmode: shape match, uniform branch
        uint p0 = sPat[0], p1 = sPat[1];
        int pc = int(bitCount(p0) + bitCount(p1));
        int best = 1000, bo = 2147483647;
        if (lid == 0) { best = pc; bo = 0; if (64 - pc < best) { best = 64 - pc; bo = 1; } }
        int lo = int(uP.z + 0.5), hi = int(uP.w + 0.5);
        for (int g = lo + lid; g < hi; g += 64) {
            int s = int(bitCount(p0 ^ fontWord(2 * g)) + bitCount(p1 ^ fontWord(2 * g + 1)));
            int o = (g + 1) * 2;
            if (s < best) { best = s; bo = o; }
            if (64 - s < best) { best = 64 - s; bo = o + 1; }
        }
        sScore[lid] = best;
        sOrd[lid] = bo;
        barrier();
        for (int st = 32; st > 0; st >>= 1) {                // min score, ties to the lowest order: tree
            if (lid < st && (sScore[lid + st] < sScore[lid] ||
                             (sScore[lid + st] == sScore[lid] && sOrd[lid + st] < sOrd[lid]))) {
                sScore[lid] = sScore[lid + st]; sOrd[lid] = sOrd[lid + st];
            }
            barrier();
        }
        if (lid == 0) sGlyph = sOrd[0];
        barrier();
    } else if (lid == 0) {
        float l = clamp((sMean.w - 0.5) * uC.x + 0.5, 0.0, 1.0);
        l = pow(l, uC.y);
        if (uB.w > 0.5) l = 1.0 - l;
        int n = rampN();
        if (mode == 0) {
            sGlyph = rampAt(clamp(int(floor(l * float(n))), 0, n - 1));
            sBright = 1.0;
            sHead = 0;
        } else {                                             // matrix rain
            float tt = uN.z;
            uint seed = uint(uN.w);
            float bright = 0.0;
            int head = 0;
            int layers = clamp(int(uN.x + 0.5), 1, 4);
            for (int k = 0; k < 4; k++) {
                if (k >= layers) break;
                ivec2 col = ivec2(cell.x, k);
                if (hsh(col, seed + 1u) >= uM.z) continue;
                float spd = uM.x * (0.5 + hsh(col, seed + 2u));
                float len = max(1.0, uM.y * (0.5 + hsh(col, seed + 3u)));
                float period = float(rows.y) + len + float(rows.y) * hsh(col, seed + 4u);
                float pos = mod(tt * spd + hsh(col, seed + 5u) * period, period);
                float d = pos - float(cell.y);
                if (d >= 0.0 && d < len) {
                    float b = 1.0 - d / len;
                    if (b > bright) { bright = b; head = d < 1.0 ? 1 : 0; }
                }
            }
            if (int(uN.y + 0.5) == 1) bright *= sMean.w;
            float tick = floor(tt * uM.w + hsh(cell, seed + 6u) * 8.0);
            int gi = int(hsh(ivec2(cell.x * 131 + cell.y, int(tick)), seed + 7u) * float(n));
            sGlyph = rampAt(clamp(gi, 0, n - 1));
            sBright = bright;
            sHead = head;
        }
    }
    barrier();
    // 3. colours
    int code = sGlyph;
    int g = mode == 2 ? code / 2 - 1 : code;
    bool inv = mode == 2 && (code & 1) == 1;
    int cm = int(uB.x + 0.5), bgm = int(uB.y + 0.5);
    vec3 fg, bgc = uE.rgb;
    bool twoBg = false;
    if (mode == 2) {
        fg = inv ? sBg : sFg;
        bgc = inv ? sFg : sBg;
        twoBg = true;
        if (cm == 1) { fg = uD.rgb; twoBg = false; }
        else if (cm == 2) { fg = uD.rgb; bgc = uE.rgb; }
        else if (cm == 3) { fg = nearestPal(fg); bgc = nearestPal(bgc); }
    } else if (mode == 1) {
        int rm = int(uN.y + 0.5);
        fg = (sHead == 1 ? uH.rgb : (rm == 2 ? sMean.rgb : uD.rgb)) * sBright;
        if (cm == 3) fg = nearestPal(fg);
    } else {
        fg = cm == 0 ? sMean.rgb : (cm == 3 ? nearestPal(sMean.rgb) : uD.rgb);
        if (cm == 2) twoBg = true;
    }
    // 4. draw the cell's pixels (strided over the 64 threads)
    int x0 = cell.x * cs.x, y0t = cell.y * cs.y;
    bool smo = uC.z > 0.5, mir = mode == 1 && uC.w > 0.5;
    for (int k = lid; k < cs.x * cs.y; k += 64) {
        int lx = k % cs.x, ly = k / cs.x;
        int px = x0 + lx, pyt = y0t + ly;
        if (px >= res.x || pyt >= res.y) continue;
        ivec2 p = ivec2(px, res.y - 1 - pyt);
        vec4 s = texelFetch(sTD2DInputs[0], p, 0);
        vec2 uv = vec2((float(lx) + 0.5) / float(cs.x), (float(ly) + 0.5) / float(cs.y));
        if (mir) uv.x = 1.0 - uv.x;
        bool on = glyphAt(g, uv, smo);
        vec4 o;
        if (on) o = vec4(fg, 1.0);
        else if (twoBg || bgm == 3) o = vec4(bgc, 1.0);
        else if (bgm == 1) o = vec4(straight(s) * uB.z, 1.0);
        else if (bgm == 2) o = vec4(0.0);
        else o = vec4(0.0, 0.0, 0.0, 1.0);
        vec4 sp = vec4(straight(s), s.a);
        vec4 r = mix(sp, o, uA.x);
        TDImageStoreOutput(0, ivec3(p, 0), TDOutputSwizzle(vec4(r.rgb * r.a, r.a)));
    }
}
"""


def shader_texts(lib):
    return {'fx': FX.replace('%LIB%', lib(pal_in=1, font=2))}


def uniforms(H):
    P, LX = H['P'], H['LX']
    rp = "%s.ramp_packed(parent().par.Charset.eval(), parent().par.Chars.eval())" % LX
    shp = "%s.GLYPH_RANGES[parent().par.Shapeset.eval()]" % LX
    slot = "%s.bank_slot(parent().par.Machine.eval(), parent(2).op('pal_bank').numRows)" % LX
    rgb = lambda n: [P.format(n + 'r'), P.format(n + 'g'), P.format(n + 'b'), '0']   # noqa: E731
    return [
        ('uA', [P.format('Amount'), 'parent().par.Mode.menuIndex', P.format('Cellw'), P.format('Cellh')]),
        ('uB', ['parent().par.Colour.menuIndex', 'parent().par.Bgmode.menuIndex', P.format('Bgdim'),
                '1 if %s else 0' % P.format('Invert')]),
        ('uC', [P.format('Contrast'), P.format('Gamma'), '1 if %s else 0' % P.format('Smooth'),
                '1 if %s else 0' % P.format('Mirror')]),
        ('uD', rgb('Fg')), ('uE', rgb('Bg')), ('uH', rgb('Head')),
        ('uR0', [rp + '[%d]' % k for k in range(0, 4)]),
        ('uR1', [rp + '[%d]' % k for k in range(4, 8)]),
        ('uR2', [rp + '[%d]' % k for k in range(8, 12)]),
        ('uM', [P.format('Speed'), P.format('Trail'), P.format('Density'), P.format('Changerate')]),
        ('uN', [P.format('Layers'), 'parent().par.Rainmask.menuIndex', 'absTime.seconds', P.format('Seed')]),
        ('uP', [slot + '[0]', slot + '[1]', shp + '[0]', shp + '[1]']),
    ]


def build(m, H, Lg):
    """in1 -> fx (one workgroup per cell) -> out_sel (0 in1 at Amount 0, 1 fx) -> out1."""
    mk, expr, compute = H['mk'], H['expr'], H['compute']
    in1 = mk(m, inTOP, 'in1')
    pal = H['select'](m, 'pal', '../pal_top')
    font = H['select'](m, 'font', '../font_top')
    sh = shader_texts(lambda **k: H['glsl_lib'](Lg, **k))
    W, Hh = 'me.inputs[0].width', 'me.inputs[0].height'
    cols = "max(1, (me.inputs[0].width + %s - 1) // max(1, %s))" % (H['P'].format('Cellw'), H['P'].format('Cellw'))
    rows = "max(1, (me.inputs[0].height + %s - 1) // max(1, %s))" % (H['P'].format('Cellh'), H['P'].format('Cellh'))
    fx = compute(m, 'fx', sh['fx'], [in1, pal, font], W, Hh, uniforms=uniforms(H), dispatch=(cols, rows), extend='hold')
    fx.comment = 'glyph: ascii ramp / matrix rain / text-mode shape match; one workgroup per Cellw x Cellh cell.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, "0 if parent().par.Amount.eval() <= 0 else 1")
    sel.comment = 'Amount 0 = in1 exactly (fx not pulled).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'pal', 'font'], 'body': 'Picture, rack palette bank, font.'},
        {'title': '2 Glyph', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'One workgroup per cell.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
