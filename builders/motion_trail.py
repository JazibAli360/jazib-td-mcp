"""motion_trail builder: /project1/lab/FX_motion_trail (TD 2025.31550). Motion leaves a fading trail, coloured by age.

Spec: docs/research/BA_motion_tracer.md section 5 (our own clean-room recipe; the Patreon .tox was never loaded).
Run inside TD through td_exec:
    g = dict(globals()); exec(open('<repo>/builders/motion_trail.py').read(), g); g['build']('/project1/lab')
build(parent_path, name, controls=True) is idempotent (ops reused by name).
Network: source (stored clip or In TOP) -> working size (Quality) -> Cache TOP (previous frame) -> ONE compute GLSL
pass (frame difference -> mask -> age trail, feedback) -> ONE compute GLSL pass (colour by age: ramp / white /
source / palette (palette texture, input 3) / rainbow; blend over the source at full size) -> out1. Compute mode only (T-46/T-47). Pure logic: builders/motion_trail_logic.py (copied into
the COMP as a Text DAT; par expressions call it). T-70 safe: own controls_window closed first, every destroy through
safe_destroy, the panel container is never destroyed (zkit updates it in place), the network pane is never moved.
No functions in storage (T-67). Pure ASCII.
"""
import os

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
NAME = 'FX_motion_trail'
CLIP = REPO + '/media/webcam/webcam_ref_5s.mp4'
LOGIC = "op('motion_trail_logic').module"

PAR_EXEC = '''# motion_trail: Clear pulse -> trail cleared for 2 frames (uniform reads this frame number from storage);
# Palette / Palettefile change -> pal_active re-reads the palette.
def onPulse(par):
\tif par.name == 'Clear':
\t\tparent().store('jz_clear', int(absTime.frame))
\treturn

def onValueChange(par, prev):
\tif par.name in ('Palette', 'Palettefile'):
\t\top('pal_active').cook(force=True)
\treturn
'''

PAL_CB = '''# pal_active: the trail palette as rows hex r g b (Palette menu: custom table pal_custom, file, or a preset).
# Logic = palette_map_logic (a copy of builders/palette_map_logic.py, the same presets as FX_palette_map).
import os

def onCook(scriptOp):
\tL = op('palette_map_logic').module
\tP = parent()
\tmode = P.par.Palette.eval()
\tsrc = scriptOp.inputs[0] if scriptOp.inputs else None
\trows = [[c.val for c in r] for r in src.rows()] if src is not None else []
\tfhex = None
\tif mode == 'file':
\t\tpath = str(P.par.Palettefile.eval() or '')
\t\tif path:
\t\t\tfull = path if os.path.isabs(path) else os.path.join(project.folder, path)
\t\t\ttry:
\t\t\t\twith open(full, 'rb') as f:
\t\t\t\t\tfhex = L.parse_file(full, f.read())
\t\t\texcept Exception as e:
\t\t\t\tscriptOp.addWarning('palette file: ' + str(e))
\t\telse:
\t\t\tscriptOp.addWarning('Palette = From file but Palette file is empty')
\tscriptOp.clear()
\tfor r in L.palette_table(L.resolve(mode, rows, fhex)):
\t\tscriptOp.appendRow(r[:4])
\treturn
'''

DEFAULT_PAL = ['#FFF1E8', '#FFEC27', '#FF004D', '#7E2553', '#1D2B53']

TRAIL_GLSL = '''// motion_trail: frame difference -> motion mask -> age trail (one compute pass, feedback on input 2)
// in0 = current (working size), in1 = previous frame, in2 = last trail (rgb = captured colour, a = age 1..0)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uP;   // threshold, softness, step per frame, reset
uniform vec4 uQ;   // hold, 0, 0, 0
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tvec4 c = texelFetch(sTD2DInputs[0], px, 0);
\tvec4 p = texelFetch(sTD2DInputs[1], px, 0);
\tvec4 f = texelFetch(sTD2DInputs[2], px, 0);
\tvec3 d = abs(c.rgb - p.rgb);
\tfloat m = smoothstep(uP.x, uP.x + max(uP.y, 1e-4), max(d.r, max(d.g, d.b)));
\tfloat age = (uQ.x > 0.5) ? f.a : max(f.a - uP.z, 0.0);
\tvec3 col = f.rgb;
\tif (m > 0.0 && m >= age) { age = m; col = c.rgb; }
\tif (uP.w > 0.5) { age = 0.0; col = vec3(0.0); }
\tTDImageStoreOutput(0, ivec3(px, 0), vec4(col, age));
}
'''

LOOK_GLSL = '''// motion_trail: colour by age + blend over the source (one compute pass, full source size)
// in0 = source, in1 = trail (working size, sampled bilinear), in2 = palette (N x 1, rgb)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uNew;   // rgb new colour, a = mix (trail opacity)
uniform vec4 uMid;   // rgb mid colour, a = gamma (from Decay)
uniform vec4 uOld;   // rgb old colour, a = source level
uniform vec4 uM;     // agecolor (0 ramp, 1 white, 2 source, 3 palette, 4 rainbow), blend (0 over, 1 add, 2 screen, 3 trail)
uniform vec4 uC;     // palette count, smooth, spread (cycles over a trail's life), phase (time, cycles 0..1)
vec3 palAt(float p)
{
\tint n = max(int(uC.x + 0.5), 1);
\tif (n == 1) return texelFetch(sTD2DInputs[2], ivec2(0, 0), 0).rgb;
\tif (uC.y < 0.5) return texelFetch(sTD2DInputs[2], ivec2(min(int(p * float(n)), n - 1), 0), 0).rgb;
\tfloat x = clamp(p, 0.0, 1.0) * float(n - 1);
\tint i = min(int(floor(x)), n - 2);
\treturn mix(texelFetch(sTD2DInputs[2], ivec2(i, 0), 0).rgb, texelFetch(sTD2DInputs[2], ivec2(i + 1, 0), 0).rgb, x - float(i));
}
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tvec2 uv = (vec2(px) + 0.5) / vec2(res);
\tvec4 s = texelFetch(sTD2DInputs[0], px, 0);
\tvec4 tr = texture(sTD2DInputs[1], uv);
\tfloat t = clamp(tr.a, 0.0, 1.0);
\tfloat a = (t > 0.0) ? pow(t, max(uMid.a, 1e-4)) * uNew.a : 0.0;
\tvec3 rc;
\tint mode = int(uM.x + 0.5);
\tif (mode == 1) rc = vec3(1.0);
\telse if (mode == 2) rc = tr.rgb;
\telse if (mode == 3) {
\t\tfloat p = (1.0 - t) * uC.z + uC.w;
\t\tp = (uC.z <= 1.0 && uC.w == 0.0) ? clamp(p, 0.0, 1.0) : fract(p);
\t\trc = palAt(p);
\t}
\telse if (mode == 4) {
\t\tfloat h = fract((1.0 - t) * uC.z + uC.w);
\t\trc = clamp(abs(fract(vec3(h) + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
\t}
\telse {
\t\tfloat k = 1.0 - t;
\t\trc = (k < 0.5) ? mix(uNew.rgb, uMid.rgb, k * 2.0) : mix(uMid.rgb, uOld.rgb, k * 2.0 - 1.0);
\t}
\tvec3 sc = s.rgb * uOld.a;
\tint bl = int(uM.y + 0.5);
\tvec4 o;
\tif (bl == 1) o = vec4(sc + rc * a, max(s.a, a));
\telse if (bl == 2) o = vec4(1.0 - (1.0 - sc) * (1.0 - rc * a), max(s.a, a));
\telse if (bl == 3) o = vec4(rc * a, a);
\telse o = vec4(mix(sc, rc, a), max(s.a, a));
\tTDImageStoreOutput(0, ivec3(px, 0), TDOutputSwizzle(o));
}
'''

STAGES = [
    {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'par_exec', 'motion_trail_logic'],
     'body': 'zkit panel (Trail + Colour pages); pulse Opencontrols. par_exec: Clear pulse, Palette re-read. '
             'motion_trail_logic: pure logic the par expressions call (length/beats -> step, Decay -> gamma, Quality '
             '-> size, Cycle -> phase).'},
    {'title': 'Palette', 'role': 'input',
     'ops': ['palette_map_logic', 'pal_custom', 'pal_active', 'pal_active_callbacks', 'pal_chop', 'pal_top'],
     'body': 'Age colour = Palette: preset (same Lospec set as FX_palette_map), pal_custom table (one hex per row) '
             'or a file -> pal_active (hex r g b) -> pal_top (N x 1 texture, look input 3).'},
    {'title': '1 Input', 'role': 'input', 'ops': ['in1', 'clip', 'clip_info', 'src_switch', 'src', 'in_level'],
     'body': 'Source = stored clip (default webcam_ref_5s.mp4) or the In TOP. clip_info index < 1 = loop point '
             '(trail reset, no ghost). in_level: optional audio level 0..1 (Audioamount scales Mix).'},
    {'title': 'Feedback', 'role': 'feedback', 'ops': ['blank', 'trail_fb'],
     'body': 'trail_fb = last frame of trail (its own box: layout check counts a feedback wire inside one box as a '
             'back wire). blank = clear start (alpha 0) when the feedback resets.'},
    {'title': '2 Motion + trail', 'role': 'process', 'ops': ['work', 'prev', 'trail', 'trail_compute'],
     'body': 'work = Quality size. prev = Cache TOP (previous frame). trail = ONE compute pass: |cur - prev| > '
             'Threshold (Softness) = motion; age = max(motion, last - 1/Length); rgb keeps the colour it moved with.'},
    {'title': '3 Colour + output', 'role': 'output', 'ops': ['look', 'look_compute', 'out1'],
     'body': 'ONE compute pass at source size: opacity = age ^ gamma(Decay) * Mix; colour Ramp new->mid->old, White, '
             'Source, Palette by age or Rainbow (hue by age + time; Spread, Cycle); Blend over / add / screen / trail '
             'only (premultiplied). out1 = output only.'},
]


def _sd(o):
    """T-70: destroy only through safe_destroy (td_exec namespace, else the MCP handlers module)."""
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
    if o is not None and o.OPType != cls.__name__:
        _sd(o)
        o = None
    return o or c.create(cls, name)


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _page(c, name):
    for p in c.customPages:
        if p.name == name:
            return p
    return c.appendCustomPage(name)


def _par(c, page, style, name, label, default=None, rng=None, menu=None, clamp_min=False):
    pg = _page(c, page)
    if style == 'RGB' and getattr(c.parGroup, name, None) is not None:
        grp = getattr(c.parGroup, name)
        if grp.label != label:
            grp.label = label
        return
    ex = getattr(c.par, name, None)
    if ex is not None:
        if style != 'RGB' and ex.label != label:
            ex.label = label
        if style == 'Menu' and list(ex.menuNames) != [m[0] for m in menu]:
            v = ex.eval()
            ex.menuNames = [m[0] for m in menu]
            ex.menuLabels = [m[1] for m in menu]
            if v in ex.menuNames:
                ex.val = v
        return
    if style == 'Menu':
        p = pg.appendMenu(name, label=label)[0]
        p.menuNames = [m[0] for m in menu]
        p.menuLabels = [m[1] for m in menu]
    else:
        p = getattr(pg, 'append' + style)(name, label=label)[0]
    if rng is not None:
        p.normMin, p.normMax = rng
        if clamp_min:
            p.min = rng[0]
            p.clampMin = True
    if default is not None:
        if style == 'RGB':
            for k, v in zip(getattr(c.parGroup, name), default):
                k.default = v
                k.val = v
            return
        p.default = default
        p.val = default


def _pars(c, L, PL):
    T, C, S = 'Trail', 'Colour', 'Setup'
    _par(c, T, 'Int', 'Length', 'Length', 30, (1, 120), clamp_min=True)
    _par(c, T, 'Menu', 'Lengthunit', 'Unit', 'frames', menu=L.LENGTHUNIT)
    _par(c, T, 'Float', 'Beats', 'Beats', 1.0, (0.25, 8))
    _par(c, T, 'Float', 'Bpm', 'BPM', 120.0, (60, 200))
    _par(c, T, 'Float', 'Decay', 'Decay', 0.5, (0, 1))
    _par(c, T, 'Float', 'Threshold', 'Threshold', 0.08, (0, 1))
    _par(c, T, 'Float', 'Softness', 'Softness', 0.05, (0, 0.2))
    _par(c, T, 'Float', 'Mix', 'Mix', 1.0, (0, 1))
    _par(c, T, 'Float', 'Sourcelevel', 'Source lvl', 1.0, (0, 1))
    _par(c, T, 'Float', 'Audioamount', 'Audio mix', 0.0, (0, 1))
    _par(c, T, 'Toggle', 'Hold', 'Hold', False)
    _par(c, T, 'Pulse', 'Clear', 'Clear')
    _par(c, C, 'Menu', 'Agecolor', 'Age colour', 'ramp', menu=L.AGECOLOR)
    _par(c, C, 'Menu', 'Blend', 'Blend', 'over', menu=L.BLEND)
    _par(c, C, 'RGB', 'Colornew', 'New', (1.0, 1.0, 1.0))
    _par(c, C, 'RGB', 'Colormid', 'Mid', (0.62, 0.64, 0.68))
    _par(c, C, 'RGB', 'Colorold', 'Old', (0.22, 0.23, 0.26))
    _par(c, C, 'Menu', 'Palette', 'Palette', 'custom', menu=PL.PALETTE_MENU)
    _par(c, C, 'Toggle', 'Palettesmooth', 'Smooth pal', True)
    _par(c, C, 'Float', 'Spread', 'Spread', 1.0, (0, 4))
    _par(c, C, 'Float', 'Cycle', 'Cycle /s', 0.0, (-2, 2))
    _par(c, S, 'Menu', 'Source', 'Source', 'clip', menu=[('clip', 'Stored clip'), ('input', 'In TOP (in1)')])
    _par(c, S, 'File', 'Clipfile', 'Clip file', CLIP)
    _par(c, S, 'Menu', 'Quality', 'Working size', 'half', menu=L.QUALITY)
    _par(c, S, 'Toggle', 'Resetonloop', 'Clear at clip loop point', True)
    _par(c, S, 'File', 'Palettefile', 'Palette file (.txt .hex .json .gpl .pal .ase)', '')


def _glsl(c, name, code, w_expr, h_expr, fmt, uniforms):
    g = _mk(c, glslTOP, name)
    g.par.mode = 'compute'
    cd = _mk(c, textDAT, name + '_compute')
    cd.text = code
    g.par.computedat = cd.name
    g.par.outputresolution = 'custom'
    g.par.resolutionw.expr = w_expr
    g.par.resolutionh.expr = h_expr
    g.par.format = fmt
    g.par.autodispatchsize = True
    g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), len(uniforms))
    for k, (uname, exprs) in enumerate(uniforms):
        getattr(g.par, 'vec{}name'.format(k)).val = uname
        for ax, e in zip('xyzw', exprs):
            getattr(g.par, 'vec{}value{}'.format(k, ax)).expr = e
    return g


def build(parent_path='/project1/lab', name=NAME, controls=True):
    pc = op(parent_path)
    c = pc.op(name) or pc.create(baseCOMP, name)
    c.allowCooking = True                      # never parked while being built (user rule)
    _close_window(c)                           # T-70: own window closed before any rebuild
    logic_text = open(REPO + '/builders/motion_trail_logic.py').read()
    lg = _mk(c, textDAT, 'motion_trail_logic')
    lg.text = logic_text
    L = lg.module
    pl = _mk(c, textDAT, 'palette_map_logic')
    pl.text = open(REPO + '/builders/palette_map_logic.py').read()
    pl.comment = 'Copy of builders/palette_map_logic.py (FX_palette_map presets, hex parsing, files).'
    PL = pl.module
    _pars(c, L, PL)
    c.comment = 'motion_trail: moving things leave a fading trail, coloured by age (2 compute passes, stock TOPs)'

    # 1 Input
    inp = _mk(c, inTOP, 'in1')
    clip = _mk(c, moviefileinTOP, 'clip')
    clip.par.file.expr = 'parent().par.Clipfile'
    clip.par.play = True
    info = _mk(c, infoCHOP, 'clip_info')
    info.par.op = clip.name
    sw = _mk(c, switchTOP, 'src_switch')
    _wire(inp, sw, 0)
    _wire(clip, sw, 1)
    sw.par.index.expr = "1 if parent().par.Source.eval() == 'clip' else 0"
    src = _mk(c, nullTOP, 'src')
    _wire(sw, src)
    _mk(c, inCHOP, 'in_level')

    # 2 Motion + trail
    work = _mk(c, resolutionTOP, 'work')
    _wire(src, work)
    work.par.outputresolution = 'custom'
    wexpr = "{}.work_size(op('src').width, op('src').height, parent().par.Quality.eval())[{}]"
    work.par.resolutionw.expr = wexpr.format(LOGIC, 0)
    work.par.resolutionh.expr = wexpr.format(LOGIC, 1)
    work.par.format = 'rgba8fixed'
    prev = _mk(c, cacheTOP, 'prev')
    _wire(work, prev)
    prev.par.cachesize = 2
    prev.par.outputindex = -1
    blank = _mk(c, constantTOP, 'blank')
    blank.par.outputresolution = 'custom'
    blank.par.resolutionw.expr = "op('work').width"
    blank.par.resolutionh.expr = "op('work').height"
    blank.par.format = 'rgba16float'
    blank.par.colorr = blank.par.colorg = blank.par.colorb = 0
    blank.par.alpha = 0
    fb = _mk(c, feedbackTOP, 'trail_fb')
    _wire(blank, fb)
    step = ("{L}.step(parent().par.Length, parent().par.Lengthunit.eval(), parent().par.Beats, parent().par.Bpm, "
            "project.cookRate)").format(L=LOGIC)
    reset = ("{L}.reset_now(absTime.frame, (lambda k, f: k if k <= f else -99)(parent().fetch('jz_clear', -99, search=False), absTime.frame), "
             "float(op('clip_info')['index']) if op('clip_info')['index'] is not None else None, "
             "parent().par.Resetonloop.eval(), parent().par.Source.eval())").format(L=LOGIC)
    trail = _glsl(c, 'trail', TRAIL_GLSL, "op('work').width", "op('work').height", 'rgba16float',
                  [('uP', ('parent().par.Threshold', 'parent().par.Softness', step, reset)),
                   ('uQ', ('1 if parent().par.Hold else 0', '0', '0', '0'))])
    _wire(work, trail, 0)
    _wire(prev, trail, 1)
    _wire(fb, trail, 2)
    fb.par.top = trail.name

    # Palette (Age colour = Palette)
    cust = _mk(c, tableDAT, 'pal_custom')
    if cust.numRows == 0 or (cust.numRows == 1 and cust[0, 0].val == ''):
        cust.clear()
        for h in DEFAULT_PAL:
            cust.appendRow([h])
    cust.comment = 'Custom trail palette (Palette = Custom): one hex per row, newest -> oldest. Edit freely.'
    act = _mk(c, scriptDAT, 'pal_active')
    _wire(cust, act)
    cb = c.op('pal_active_callbacks')
    if cb is None:
        cb = act.par.callbacks.eval()
        if cb is None or cb.parent() != c:
            cb = _mk(c, textDAT, 'pal_active_callbacks')
        elif cb.name != 'pal_active_callbacks':
            cb.name = 'pal_active_callbacks'
    cb.text = PAL_CB
    cb.dock = act
    act.par.callbacks = cb.name
    pchop = _mk(c, dattoCHOP, 'pal_chop')
    pchop.par.dat = act.name
    pchop.par.output = 'chanpercol'
    pchop.par.firstrow = 'names'
    pchop.par.firstcolumn = 'ignored'
    ptop = _mk(c, choptoTOP, 'pal_top')
    ptop.par.chop = pchop.name
    ptop.par.dataformat = 'rgb'
    ptop.par.format = 'rgba32float'
    ptop.comment = 'Trail palette texture: width = colours (newest first), rgb.'

    # 3 Colour + output
    mix = ("{L}.mix_amount(parent().par.Mix, parent().par.Audioamount, "
           "(op('in_level')[0].eval() if op('in_level').numChans else None))").format(L=LOGIC)
    look = _glsl(c, 'look', LOOK_GLSL, "op('src').width", "op('src').height", 'rgba8fixed',
                 [('uNew', ('parent().par.Colornewr', 'parent().par.Colornewg', 'parent().par.Colornewb', mix)),
                  ('uMid', ('parent().par.Colormidr', 'parent().par.Colormidg', 'parent().par.Colormidb',
                            '{}.gamma(parent().par.Decay)'.format(LOGIC))),
                  ('uOld', ('parent().par.Coloroldr', 'parent().par.Coloroldg',
                            'parent().par.Coloroldb', 'parent().par.Sourcelevel')),
                  ('uM', ("{}.menu_index({}.AGECOLOR, parent().par.Agecolor.eval())".format(LOGIC, LOGIC),
                          "{}.menu_index({}.BLEND, parent().par.Blend.eval())".format(LOGIC, LOGIC), '0', '0')),
                  ('uC', ("max(op('pal_active').numRows - 1, 1)", '1 if parent().par.Palettesmooth else 0',
                          'parent().par.Spread',
                          '{}.cycle_phase(absTime.seconds, parent().par.Cycle)'.format(LOGIC)))])
    _wire(src, look, 0)
    _wire(trail, look, 1)
    _wire(ptop, look, 2)
    out = _mk(c, outTOP, 'out1')
    _wire(look, out)

    pe = _mk(c, parameterexecuteDAT, 'par_exec')
    pe.text = PAR_EXEC
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Clear'
    pe.par.onpulse = True
    pe.par.valuechange = False
    pe.par.active = True

    # Controls (zkit, verified kit): Trail + Colour pages as knobs; Setup stays on the COMP
    ui = 'skipped'
    if controls:
        ns = dict(globals())
        exec(open(REPO + '/builders/zkit.py').read(), ns)
        ui = ns['build_controls'](c.path, pages=['Trail', 'Colour'], d=56, cols=6)

    c.par.opviewer.expr = "me.op('out1')"
    c.viewer = True
    for o in c.children:
        if o.family in ('TOP', 'CHOP'):
            o.viewer = True

    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, STAGES, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'ui': str(ui)[:300], 'layout': str(lay)[:400]}
