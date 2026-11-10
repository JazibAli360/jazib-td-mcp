# palette_map builder - FX_palette_map: map every pixel to the nearest colour of a palette (OKLab or sRGB),
# with ordered / noise dither, blend and preserve-luma. Spec: docs/research/AZ_closest_color_palette.md section 4
# (our own clean-room design; idea credit "Closest Color Palette TOX" by percolated, never downloaded or loaded).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/palette_map.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set, custom par values kept, palette_custom rows kept.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy); the COMP's controls_window is closed before a rebuild
# (zkit reopens it if it was open); the panel container is never destroyed; the network pane is never moved here.
# One compute GLSL pass (T-46/T-47). No limits (palette size, dither amount): the operator decides. ASCII only.
import os

NAME = 'FX_palette_map'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
LOGIC_FILE = REPO + '/builders/palette_map_logic.py'
ZKIT_FILE = REPO + '/builders/zkit.py'
CLIP = REPO + '/media/webcam/webcam_ref_5s.mp4'
LG = "op('palette_map_logic').module"

# pal_top rows (CHOP to TOP, one channel per row): set from the live probe of row order, see ROW_* below.
SHADER = """// FX_palette_map: nearest palette colour per pixel, ONE compute pass (T-46/T-47 safe).
// in0 = picture, in1 = pal_top (width N, one row per channel: r g b L A B, 32-bit float), in2 = noise (dither input)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // count, blend, lightness weight, preserve luma
uniform vec4 uB;   // dither mode (0 off, 1 bayer, 2 ign, 3 input), dither amount, colour space (0 oklab, 1 srgb), frame offset
uniform vec4 uC;   // noise input wired (0/1)
@BAYER@
#define ROW_R @ROW_R@
#define ROW_G @ROW_G@
#define ROW_B @ROW_B@
#define ROW_L @ROW_L@
#define ROW_A @ROW_A@
#define ROW_BB @ROW_BB@
float cbrtf(float x) { return sign(x) * pow(abs(x), 1.0 / 3.0); }
vec3 toLin(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c)); }
vec3 toSrgb(vec3 c) {
\tc = clamp(c, 0.0, 1.0);
\treturn mix(12.92 * c, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c));
}
vec3 oklab(vec3 srgb) {
\tvec3 c = toLin(srgb);
\tfloat l = cbrtf(0.4122214708 * c.r + 0.5363325363 * c.g + 0.0514459929 * c.b);
\tfloat m = cbrtf(0.2119034982 * c.r + 0.6806995451 * c.g + 0.1073969566 * c.b);
\tfloat s = cbrtf(0.0883024619 * c.r + 0.2817188376 * c.g + 0.6299787005 * c.b);
\treturn vec3(0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
\t            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
\t            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s);
}
vec3 oklabToSrgb(vec3 q) {
\tfloat l = q.x + 0.3963377774 * q.y + 0.2158037573 * q.z;
\tfloat m = q.x - 0.1055613458 * q.y - 0.0638541728 * q.z;
\tfloat s = q.x - 0.0894841775 * q.y - 1.2914855480 * q.z;
\tl = l * l * l; m = m * m * m; s = s * s * s;
\treturn toSrgb(vec3(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
\t                 -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
\t                 -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s));
}
float pal(int i, int row) { return texelFetch(sTD2DInputs[1], ivec2(i, row), 0).r; }
vec3 palRgb(int i) { return vec3(pal(i, ROW_R), pal(i, ROW_G), pal(i, ROW_B)); }
vec3 palLab(int i) { return vec3(pal(i, ROW_L), pal(i, ROW_A), pal(i, ROW_BB)); }
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tvec4 s = texelFetch(sTD2DInputs[0], px, 0);
\tfloat a = s.a;
\tvec3 c = clamp(a > 1e-5 ? s.rgb / a : s.rgb, 0.0, 1.0);      // premultiplied in: map the straight colour
\tint n = max(int(uA.x + 0.5), 1);
\tbool lab = uB.z < 0.5;
\tvec3 q = lab ? oklab(c) : c;
\tvec3 w = lab ? vec3(uA.z, 1.0, 1.0) : vec3(1.0);
\tfloat d1 = 1e30, d2 = 1e30;
\tint i1 = 0, i2 = 0;
\tfor (int i = 0; i < n; i++) {
\t\tvec3 dd = (q - (lab ? palLab(i) : palRgb(i))) * w;
\t\tfloat d = dot(dd, dd);
\t\tif (d < d1) { d2 = d1; i2 = i1; d1 = d; i1 = i; }
\t\telse if (d < d2) { d2 = d; i2 = i; }
\t}
\tint pick = i1;
\tint dm = int(uB.x + 0.5);
\tif (dm > 0 && n > 1) {
\t\tfloat e1 = sqrt(d1), e2 = sqrt(d2);
\t\tfloat t = (e1 + e2) > 0.0 ? e1 / (e1 + e2) : 0.0;           // 0 on the best colour, 0.5 midway
\t\tint off = int(uB.w + 0.5);
\t\tivec2 pp = px + ivec2(off * 5, off * 3);
\t\tfloat thr;
\t\tif (dm == 1) thr = (BAYER[(pp.y & 7) * 8 + (pp.x & 7)] + 0.5) / 64.0;
\t\telse if (dm == 3 && uC.x > 0.5) {
\t\t\tivec2 ns = max(textureSize(sTD2DInputs[2], 0), ivec2(1));
\t\t\tthr = texelFetch(sTD2DInputs[2], ((pp % ns) + ns) % ns, 0).r;
\t\t}
\t\telse thr = fract(52.9829189 * fract(dot(vec2(pp), vec2(0.06711056, 0.00583715))));   // IGN (Jimenez 2014)
\t\tif (t * uB.y > thr) pick = i2;
\t}
\tvec3 o = palRgb(pick);
\tif (uA.w != 0.0) {
\t\tvec3 pl = palLab(pick);
\t\tpl.x = mix(pl.x, oklab(c).x, uA.w);
\t\to = oklabToSrgb(pl);
\t}
\to = mix(c, o, uA.y);
\tTDImageStoreOutput(0, ivec3(px, 0), TDOutputSwizzle(vec4(o * a, a)));   // premultiplied out
}
"""

ACTIVE_CB = """# palette_active: the active palette as rows hex r g b L A B (cooks on palette_custom / par changes;
# par_exec forces a cook on Palette / File / Load). Logic: palette_map_logic (tests: test/test_palette_map.py).
import os

def onCook(scriptOp):
    L = op('palette_map_logic').module
    P = parent()
    mode = P.par.Palette.eval()
    src = scriptOp.inputs[0] if scriptOp.inputs else None
    rows = [[c.val for c in r] for r in src.rows()] if src is not None else []
    fhex, notes = None, []
    if mode == 'file':
        path = str(P.par.File.eval() or '')
        if path:
            full = path if os.path.isabs(path) else os.path.join(project.folder, path)
            try:
                with open(full, 'rb') as f:
                    fhex = L.parse_file(full, f.read())
                if not fhex:
                    notes.append('no colours read from ' + full)
            except Exception as e:
                notes.append('palette file: ' + str(e))
        else:
            notes.append('Palette = From file but File is empty')
    if mode == 'custom':
        bad = L.parse_hex_list(rows)[1]
        if bad:
            notes.append('skipped cells: ' + ', '.join(bad[:8]))
    hexes = L.resolve(mode, rows, fhex)
    scriptOp.clear()
    for r in L.palette_table(hexes):
        scriptOp.appendRow(r)
    for n in notes:
        scriptOp.addWarning(n)
    return
"""

PAR_EXEC = """# par_exec: Palette / File change and the Load pulse re-read the palette; Copytotable copies the active
# palette into palette_custom (then Palette = Custom so it can be edited).
def _reload():
    op('palette_active').cook(force=True)

def onValueChange(par, prev):
    if par.name in ('Palette', 'File'):
        _reload()
    return

def onPulse(par):
    if par.name == 'Load':
        if parent().par.Palette.eval() != 'file':
            parent().par.Palette = 'file'
        _reload()
    elif par.name == 'Copytotable':
        a = op('palette_active')
        t = op('palette_custom')
        hexes = [a[r, 0].val for r in range(1, a.numRows) if a[r, 0].val != 'none']
        t.clear()
        for h in hexes:
            t.appendRow(['#' + h])
        parent().par.Palette = 'custom'
        _reload()
    return
"""

DEFAULT_CUSTOM = ['#000000', '#FFFFFF', '#CA47E9', '#29ADFF']


def _logic():
    ns = {}
    exec(open(LOGIC_FILE, encoding='utf-8').read(), ns)
    return ns


def _pages(Lg):
    m = Lg['PALETTE_MENU']
    return [
        ('Palette', [
            ('Palette', 'Menu', 'pico8', {'names': [k for k, _ in m], 'labels': [l for _, l in m]}),
            ('Colourspace', 'Menu', 'oklab', {'names': [k for k, _ in Lg['COLOURSPACE']],
                                              'labels': [l for _, l in Lg['COLOURSPACE']], 'label': 'Colour space'}),
            ('Blend', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Blend'}),
            ('Lightnessweight', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Lightness weight'}),
            ('Preserveluma', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Preserve luma'}),
            ('Dither', 'Menu', 'off', {'names': [k for k, _ in Lg['DITHER']], 'labels': [l for _, l in Lg['DITHER']]}),
            ('Ditheramount', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Dither amount'}),
            ('Ditheranimate', 'Toggle', False, {'label': 'Animate dither'}),
            ('Copytotable', 'Pulse', None, {'label': 'Copy to table'}),
            ('Load', 'Pulse', None, {'label': 'Load file'}),
        ]),
        ('Setup', [
            ('File', 'File', '', {'label': 'Palette file (.txt .hex .json .gpl .pal .ase)'}),
            ('Count', 'Int', 0, {'min': 0, 'max': 64, 'label': 'Colours (read-only)'}),
            ('Source', 'Menu', 'auto', {'names': [k for k, _ in Lg['SOURCE']], 'labels': [l for _, l in Lg['SOURCE']]}),
            ('Clipfile', 'File', CLIP, {'label': 'Clip file'}),
        ]),
    ]


PANEL_PAGES = ['Palette']


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            elif style == 'Float':
                p = page.appendFloat(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']   # slider range only: no clamps (no limits)
            elif style == 'Int':
                p = page.appendInt(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
                continue
            elif style == 'File':
                p = page.appendFile(name, label=label)[0]
            p.default = default
            p.val = default


def _sd(o):
    if o is None or not o.valid:
        return None
    f = globals().get('safe_destroy') or op('/jazib_mcp/handlers').module.safe_destroy
    return f(o)


def _close_window(c):
    w = c.op('controls_window')
    if w is not None and w.OPType == 'windowCOMP' and w.isOpen:
        w.par.winclose.pulse()
        return True
    return False


def _mk(c, cls, name):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = True
    return o


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _wire(a, b, i=0):
    b.inputConnectors[i].connect(a)


# Row order of pal_top (CHOP to TOP, dataformat r): probed live on 31550, see docs/builds/palette_map.md.
ROWS = {'R': 0, 'G': 1, 'B': 2, 'L': 3, 'A': 4, 'BB': 5}


def shader_text(Lg, rows=None):
    rows = rows or ROWS
    s = SHADER.replace('@BAYER@', Lg['bayer_glsl']())
    for k, v in rows.items():
        s = s.replace('@ROW_%s@' % k, str(v))
    return s


def build(parent_path='/project1/lab', panel=True, rows=None):
    Lg = _logic()
    pc = op(parent_path)
    c = pc.op(NAME) or pc.create(baseCOMP, NAME)
    c.allowCooking = True                       # never parked while being built (user rule)
    c.comment = ('FX_palette_map: nearest palette colour per pixel (OKLab or sRGB), Bayer / IGN / noise-input dither, '
                 'blend, preserve luma. In: in1 TOP (picture), in2 TOP (optional dither noise). Out: out1 TOP. '
                 'Palette: presets (Lospec), palette_custom table, or a file. Pulse Opencontrols.')
    _close_window(c)
    _pars(c, _pages(Lg))
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)

    # 1 Picture in
    in1 = _mk(c, inTOP, 'in1')
    clip = _mk(c, moviefileinTOP, 'clip')
    _expr(clip.par.file, 'parent().par.Clipfile')
    clip.par.play = True
    ramp = _mk(c, rampTOP, 'test_ramp')
    ramp.par.type = 'horizontal'
    ramp.par.outputresolution = 'custom'
    ramp.par.resolutionw, ramp.par.resolutionh = 1080, 1920
    ramp.comment = 'Test ramp (Source = Test ramp): black -> white, for dither checks. 1080x1920.'
    wired = ("any(len(cn.connections) for cn in parent().inputConnectors "
             "if cn.inOP is not None and cn.inOP.name == 'in1')")
    sw = _mk(c, switchTOP, 'src_switch')
    _wire(in1, sw, 0)
    _wire(clip, sw, 1)
    _wire(ramp, sw, 2)
    _expr(sw.par.index, "{{'input': 0, 'clip': 1, 'ramp': 2}}.get(parent().par.Source.eval(), 0 if {} else 1)"
          .format(wired))
    src = _mk(c, nullTOP, 'src')
    _wire(sw, src)

    # 2 Palette
    lg = _mk(c, textDAT, 'palette_map_logic')
    lg.text = open(LOGIC_FILE, encoding='utf-8').read()
    lg.comment = 'Pure logic (copy of builders/palette_map_logic.py; tests test/test_palette_map.py). Presets cite Lospec.'
    cust = _mk(c, tableDAT, 'palette_custom')
    if cust.numRows == 0 or (cust.numRows == 1 and cust[0, 0].val == ''):
        cust.clear()
        for h in DEFAULT_CUSTOM:
            cust.appendRow([h])
    cust.comment = 'Custom palette (Palette = Custom): one hex per row, # optional, #RGB ok. Edit freely.'
    act = _mk(c, scriptDAT, 'palette_active')
    _wire(cust, act)
    cb = act.par.callbacks.eval()
    if cb is None:
        cb = _mk(c, textDAT, 'palette_active_callbacks')
        cb.dock = act
        act.par.callbacks = cb.name
    if cb.name != 'palette_active_callbacks':
        cb.name = 'palette_active_callbacks'
        act.par.callbacks = 'palette_active_callbacks'
    cb.text = ACTIVE_CB
    pchop = _mk(c, dattoCHOP, 'pal_chop')
    pchop.par.dat = 'palette_active'
    pchop.par.output = 'chanpercol'
    pchop.par.firstrow = 'names'
    pchop.par.firstcolumn = 'ignored'
    ptop = _mk(c, choptoTOP, 'pal_top')
    ptop.par.chop = 'pal_chop'
    ptop.par.dataformat = 'r'
    ptop.par.format = 'r32float'
    ptop.comment = 'Palette texture: width = colours, one row per channel (r g b L A B), 32-bit float.'

    # 3 Map + out
    in2 = _mk(c, inTOP, 'in2')
    nblank = _mk(c, constantTOP, 'noise_blank')
    nblank.par.outputresolution = 'custom'
    nblank.par.resolutionw, nblank.par.resolutionh = 8, 8
    nsw = _mk(c, switchTOP, 'noise_src')
    _wire(nblank, nsw, 0)
    _wire(in2, nsw, 1)
    wired2 = ("(1 if any(len(cn.connections) for cn in parent().inputConnectors "
              "if cn.inOP is not None and cn.inOP.name == 'in2') else 0)")
    _expr(nsw.par.index, wired2)
    nsw.comment = 'Dither noise: in2 when wired (e.g. a blue-noise image), else a blank (shader falls back to IGN).'
    g = _mk(c, glslTOP, 'map')
    g.par.mode = 'compute'
    cd = _mk(c, textDAT, 'map_compute')
    cd.text = shader_text(Lg, rows)
    g.par.computedat = cd.name
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, "op('src').width")
    _expr(g.par.resolutionh, "op('src').height")
    g.par.format = 'rgba8fixed'
    g.par.autodispatchsize = True
    _wire(src, g, 0)
    _wire(ptop, g, 1)
    _wire(nsw, g, 2)
    g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), 3)
    pp = 'parent().par.'
    U = [('uA', ["op('pal_top').width", pp + 'Blend', pp + 'Lightnessweight', pp + 'Preserveluma']),
         ('uB', ["{}.menu_index({}.DITHER, parent().par.Dither.eval())".format(LG, LG), pp + 'Ditheramount',
                 "{}.menu_index({}.COLOURSPACE, parent().par.Colourspace.eval())".format(LG, LG),
                 "(absTime.frame % 64) if parent().par.Ditheranimate else 0"]),
         ('uC', [wired2, '0', '0', '0'])]
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), e)
    out1 = _mk(c, outTOP, 'out1')
    _wire(g, out1)

    # a COMP's own par expressions resolve op() from its parent: use me.op() here
    _expr(c.par.Count, "me.op('palette_map_logic').module.count(me.op('palette_active')[1, 0].val "
                       "if me.op('palette_active').numRows > 1 else None, me.op('palette_active').numRows)")
    c.par.Count.readOnly = True

    pe = _mk(c, parameterexecuteDAT, 'par_exec')
    pe.text = PAR_EXEC
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Palette File Load Copytotable'
    pe.par.custom = True
    pe.par.builtin = False
    pe.par.valuechange = True
    pe.par.onpulse = True
    pe.par.active = True
    act.cook(force=True)

    _expr(c.par.opviewer, "me.op('out1')")
    c.viewer = True
    for o in c.children:
        if o.family in ('TOP', 'CHOP'):
            o.viewer = True

    info = 'skipped'
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](c.path, pages=PANEL_PAGES, d=56, cols=5)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'par_exec'],
         'body': 'zkit panel + window (pulse Opencontrols). par_exec: Palette/File/Load re-read, Copy to table.'},
        {'title': '1 Picture in', 'role': 'input', 'ops': ['in1', 'clip', 'test_ramp', 'src_switch', 'src'],
         'body': 'Source: auto = in1 when wired, else the stored webcam clip; Test ramp for dither checks.'},
        {'title': '2 Palette', 'role': 'process',
         'ops': ['palette_map_logic', 'palette_custom', 'palette_active', 'palette_active_callbacks', 'pal_chop', 'pal_top'],
         'body': 'Preset / palette_custom / file -> palette_active (hex r g b L A B) -> pal_chop -> pal_top '
                 '(N x 6, 32F). OKLab precomputed once per palette change.'},
        {'title': '3 Map + out', 'role': 'output', 'ops': ['in2', 'noise_blank', 'noise_src', 'map', 'map_compute', 'out1'],
         'body': 'ONE compute pass: nearest (+ second) colour in OKLab / sRGB, dither Bayer / IGN / in2 noise, '
                 'preserve luma, blend; premultiplied in and out.'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'panel': str(info)[:300], 'layout': str(lay)[:400]}
