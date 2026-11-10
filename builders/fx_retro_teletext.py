# fx_retro_teletext - FX_retro module 'teletext' (FX2 AV-38 teletext / Ceefax-style page; FX0 row 59).
# Module file = pages / presets + shader_texts + build(m, H, Lg) (template: docs/builds/fx_glitch.md; rack:
# builders/fx_retro.py). A Columns x Rows character grid (Rows 0 = auto from Cellaspect), level-1 look: 8 colours,
# 2x3 sixel mosaics (contiguous / separated), double height, flash, conceal / Reveal, page load (rows appear top to
# bottom after Reload), header row with a 12-hour clock. Modes: image (the picture as sixel mosaics: per cell the best
# fg / bg pair of the 8 colours + 6-bit mask, one workgroup per cell), page (header + page table with {colour}
# markup, picture mosaics below the text when Imagebody), subtitle (boxed double-height lines over the picture).
# Text -> `codes` Script CHOP (fx_retro_logic.teletext_codes_td, cooks on change + once a second) -> texture buffer
# uCodes. Glyphs: the rack 8x8 font (no Urdu: use urdu_type for Urdu lines). Amount 0 = exact passthrough. ASCII only.

MODULE = 'teletext'


def pages(Lg):
    tn = Lg['TT_NAMES']
    return [
        ('Teletext', [
            ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
            ('Mode', 'Menu', 'image', {'names': ['image', 'page', 'subtitle'],
                                       'labels': ['Image mosaic', 'Page (header + table)', 'Subtitles']}),
            ('Columns', 'Int', 40, {'min': 8, 'max': 120, 'label': 'Columns'}),
            ('Rows', 'Int', 0, {'min': 0, 'max': 120, 'label': 'Rows (0 = auto)'}),
            ('Cellaspect', 'Float', 1.2, {'min': 0.5, 'max': 3, 'label': 'Cell aspect (h / w, auto rows)'}),
            ('Separated', 'Toggle', False, {'label': 'Separated mosaics (image)'}),
            ('Sepgap', 'Float', 0.3, {'min': 0, 'max': 0.8, 'label': 'Separated gap'}),
            ('Smooth', 'Toggle', True, {'label': 'Smooth text (SAA5050 rounding)'}),
            ('Flashhz', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Flash Hz'}),
            ('Reveal', 'Toggle', False, {'label': 'Reveal concealed'}),
            ('Imagebody', 'Toggle', True, {'label': 'Picture behind / below text'}),
        ]),
        ('Page', [
            ('Header', 'Str', Lg['DEFAULT_HEADER'], {'label': 'Header (%a %d %b %l %M %S %p %P)'}),
            ('Pagenum', 'Str', '100', {'label': 'Page number'}),
            ('Pagedat', 'DAT', '', {'label': 'Page DAT (empty = the page table inside)'}),
            ('Loadtime', 'Float', 1.5, {'min': 0, 'max': 10, 'label': 'Page load s (Reload)'}),
            ('Reload', 'Pulse', None, {'label': 'Reload page'}),
            ('Reloadtime', 'Float', -100.0, {'min': -100, 'max': 0, 'label': 'Last reload (absTime s)'}),
        ]),
        ('Subtitle', [
            ('Subtitle', 'Str', 'Subtitles go here|second line', {'label': 'Subtitle (| = new line)'}),
            ('Subtitledat', 'DAT', '', {'label': 'Subtitle DAT (rows = lines)'}),
            ('Subcolour', 'Menu', 'white', {'names': tn, 'labels': [n.capitalize() for n in tn]}),
            ('Subdouble', 'Toggle', True, {'label': 'Double height'}),
            ('Subrow', 'Int', 2, {'min': 0, 'max': 40, 'label': 'Rows from the bottom'}),
        ]),
    ]


PANEL_PAGES = ['Teletext', 'Subtitle']   # live C2: Subcolour was not recalled without it


def presets(Lg):
    base = {'Amount': 1.0, 'Columns': 40, 'Rows': 0, 'Cellaspect': 1.2, 'Sepgap': 0.3, 'Smooth': 1, 'Flashhz': 1.0,
            'Reveal': 0, 'Imagebody': 1}
    return [
        (1, 'mosaic', dict(base, Mode=0, Separated=0)),
        (2, 'separated', dict(base, Mode=0, Separated=1, Columns=56)),
        (3, 'page', dict(base, Mode=1, Rows=25, Loadtime=1.5)),
        (4, 'subtitles', dict(base, Mode=2, Subdouble=1, Subrow=2, Subcolour=3)),
    ]


FX = """// FX_retro teletext: one workgroup per character cell; text cells from uCodes, image cells = best sixel mosaic.
// in0 = picture. uCodes: packed cells (fx_retro_logic.tt_pack), top row first.
layout (local_size_x = 8, local_size_y = 8) in;
%LIB%
uniform samplerBuffer uCodes;
uniform vec4 uA;   // amount, cols, rows, -
uniform vec4 uB;   // separated (image cells), smooth, flash off now (0/1), reveal
uniform vec4 uC;   // seconds since Reload, load time, separated gap, -
const vec3 TT[8] = vec3[8](vec3(0.0), vec3(1.0, 0.0, 0.0), vec3(0.0, 1.0, 0.0), vec3(1.0, 1.0, 0.0),
                           vec3(0.0, 0.0, 1.0), vec3(1.0, 0.0, 1.0), vec3(0.0, 1.0, 1.0), vec3(1.0));
const float SR[4] = float[4](0.0, 0.3, 0.7, 1.0);
shared vec3 sSix[6];
shared vec3 sTL[8];
shared float sCost[64];
shared int sMask[64];
shared int sSel;
int mosaicMask(int ch) { if ((ch >= 0x40 && ch <= 0x5F) || ch < 0x20) return -1; return (ch & 0x1F) | ((ch & 0x40) >> 1); }
bool sixelLit(int mask, vec2 uv, bool sep, float gap) {     // uv: u right, v DOWN
    int col = uv.x >= 0.5 ? 1 : 0;
    int row = uv.y < SR[1] ? 0 : (uv.y < SR[2] ? 1 : 2);
    if (((mask >> (row * 2 + col)) & 1) == 0) return false;
    if (!sep) return true;
    float su = fract(uv.x * 2.0), sv = (uv.y - SR[row]) / (SR[row + 1] - SR[row]);
    return su < 1.0 - gap && sv < 1.0 - gap;
}
void main() {
    ivec2 res = ivec2(uTDOutputInfo.res.zw);
    int cols = max(int(uA.y + 0.5), 1), rows = max(int(uA.z + 0.5), 1);
    vec2 cs = vec2(res) / vec2(float(cols), float(rows));
    ivec2 cell = ivec2(gl_WorkGroupID.xy);
    int lid = int(gl_LocalInvocationIndex);
    int idx = cell.y * cols + cell.x;
    int code = idx < textureSize(uCodes) ? int(texelFetch(uCodes, idx).r + 0.5) : (1 << 19);
    bool img = ((code >> 19) & 1) == 1;
    if (lid < 6) {                                            // sixel lid: column lid & 1, row lid >> 1 (from the top)
        int col = lid & 1, row = lid >> 1;
        vec3 acc = vec3(0.0);
        for (int k = 0; k < 4; k++) {
            float u = float(col) * 0.5 + (float(k & 1) + 0.5) * 0.25;
            float v = SR[row] + (float(k >> 1) + 0.5) * 0.5 * (SR[row + 1] - SR[row]);
            vec2 p = vec2((float(cell.x) + u) * cs.x, float(res.y) - (float(cell.y) + v) * cs.y);
            acc += straight(textureLod(sTD2DInputs[0], clamp(p, vec2(0.5), vec2(res) - 0.5) / vec2(res), 0.0));
        }
        sSix[lid] = oklab(acc * 0.25);
    }
    if (lid < 8) sTL[lid] = oklab(TT[lid]);
    barrier();
    int fg = (code >> 7) & 7, bg = (code >> 10) & 7, mask = 0;
    if (img) {                                                // same code for the whole workgroup: uniform branch
        int f = lid >> 3, b = lid & 7;
        float cost = 0.0;
        int mk = 0;
        for (int k = 0; k < 6; k++) {
            vec3 df = sSix[k] - sTL[f], db = sSix[k] - sTL[b];
            float a = dot(df, df), c = dot(db, db);
            if (a <= c) { cost += a; mk |= 1 << k; } else cost += c;
        }
        sCost[lid] = cost;
        sMask[lid] = mk;
        barrier();
        if (lid == 0) {
            int bi = 0;
            for (int k = 1; k < 64; k++) if (sCost[k] < sCost[bi]) bi = k;
            sSel = bi | (sMask[bi] << 8);
        }
        barrier();
        fg = (sSel >> 3) & 7;
        bg = sSel & 7;
        mask = (sSel >> 8) & 63;
    }
    int ch = code & 127;
    bool mos = img || ((code >> 13) & 1) == 1;
    bool sep = img ? uB.x > 0.5 : ((code >> 14) & 1) == 1;
    bool flash = ((code >> 15) & 1) == 1, conceal = ((code >> 16) & 1) == 1;
    bool dht = ((code >> 17) & 1) == 1, dhb = ((code >> 18) & 1) == 1;
    if (conceal && uB.w < 0.5) { ch = 32; mos = false; }
    if (flash && uB.z > 0.5) fg = bg;
    if (!img && mos) mask = max(mosaicMask(ch), 0);
    int g = (!mos && ch >= 33 && ch <= 126) ? ch - 33 : -1;
    bool shown = uC.y <= 0.0 || uC.x >= uC.y * float(cell.y) / float(rows);
    int xa = int(ceil(float(cell.x) * cs.x)), xb = int(ceil(float(cell.x + 1) * cs.x));
    int ya = int(ceil(float(cell.y) * cs.y)), yb = int(ceil(float(cell.y + 1) * cs.y));
    int w = max(xb - xa, 0), h = max(yb - ya, 0);
    bool smo = uB.y > 0.5;
    for (int k = lid; k < w * h; k += 64) {
        int px = xa + k % w, pyt = ya + k / w;
        if (px >= res.x || pyt >= res.y) continue;
        ivec2 p = ivec2(px, res.y - 1 - pyt);
        vec2 uv = vec2((float(px) + 0.5 - float(cell.x) * cs.x) / cs.x, (float(pyt) + 0.5 - float(cell.y) * cs.y) / cs.y);
        if (dht) uv.y *= 0.5;
        else if (dhb) uv.y = 0.5 + uv.y * 0.5;
        bool on = mos ? sixelLit(mask, uv, sep, uC.z) : glyphAt(g, uv, smo);
        vec3 col = shown ? (on ? TT[fg] : TT[bg]) : vec3(0.0);
        vec4 s = texelFetch(sTD2DInputs[0], p, 0);
        vec4 r = mix(vec4(straight(s), s.a), vec4(col, 1.0), uA.x);
        TDImageStoreOutput(0, ivec3(p, 0), TDOutputSwizzle(vec4(r.rgb * r.a, r.a)));
    }
}
"""


def shader_texts(lib):
    return {'fx': FX.replace('%LIB%', lib(font=1))}


def build(m, H, Lg):
    """in1 + codes (Script CHOP) -> fx (one workgroup per cell) -> out_sel -> out1; page table; Reload pulse."""
    mk, expr, compute, P, LX = H['mk'], H['expr'], H['compute'], H['P'], H['LX']
    in1 = mk(m, inTOP, 'in1')
    pg = mk(m, tableDAT, 'page')
    if pg.numRows <= 1 and (pg.numRows == 0 or pg[0, 0].val == ''):    # T-107: a new Table DAT is not empty
        pg.clear()
        for line in Lg['DEFAULT_PAGE'] + [''] * Lg['PAGE_GAP'] + [Lg['FASTEXT']]:
            pg.appendRow([line])
    pg.comment = 'Page lines (one per row, {red} {gyellow} {dh} {flash} ... markup; docs/builds/fx_retro.md).'
    codes = H['codes_chop'](m, 'teletext_codes_td', 'Teletext cells (fx_retro_logic.tt_pack), top row first.')
    H['pulse_exec'](m, {'Reload': 'Reloadtime'})
    grid = "%s.tt_grid(me.inputs[0].width, me.inputs[0].height, %s, %s, %s)" % (
        LX, P.format('Columns'), P.format('Rows'), P.format('Cellaspect'))
    U = [('uA', [P.format('Amount'), grid + '[0]', grid + '[1]', '0']),
         ('uB', ['1 if %s else 0' % P.format('Separated'), '1 if %s else 0' % P.format('Smooth'),
                 '1 if (%s > 0 and math.fmod(absTime.seconds * %s, 1.0) >= 0.5) else 0' % (
                     P.format('Flashhz'), P.format('Flashhz')),
                 '1 if %s else 0' % P.format('Reveal')]),
         ('uC', ['absTime.seconds - %s' % P.format('Reloadtime'),
                 "%s if parent().par.Mode.eval() == 'page' else 0" % P.format('Loadtime'), P.format('Sepgap'), '0'])]
    sh = shader_texts(lambda **k: H['glsl_lib'](Lg, **k))
    font = H['select'](m, 'font', '../font_top')
    fx = compute(m, 'fx', sh['fx'], [in1, font], 'me.inputs[0].width', 'me.inputs[0].height', uniforms=U,
                 dispatch=(grid + '[0]', grid + '[1]'), arrays=[('uCodes', codes)])
    fx.comment = 'teletext: one workgroup per cell; image cells = best 2-of-8 colour sixel mosaic.'
    sel = mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(fx)
    expr(sel.par.index, "0 if parent().par.Amount.eval() <= 0 else 1")
    sel.comment = 'Amount 0 = in1 exactly (fx and codes not pulled).'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'font', 'page', 'codes', 'codes_callbacks', 'pulse_exec'],
         'body': 'Picture, page lines, codes (Script CHOP), Reload pulse.'},
        {'title': '2 Teletext', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'One workgroup per cell.'},
        {'title': '3 Out', 'role': 'output', 'ops': ['out_sel', 'out1']},
    ]


try:
    _LG = load_logic()                                   # noqa: F821 (rack namespace)
    PAGES, PRESETS = pages(_LG), presets(_LG)
except NameError:
    PAGES, PRESETS = None, None
