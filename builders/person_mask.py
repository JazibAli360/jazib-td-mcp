"""person_mask builder: /project1/lab/CV_person_mask (TD 2025.31550). Apple Vision person matte -> cut-out, matte, inverse.

Run inside TD through td_exec:
    g = dict(globals()); exec(open('<repo>/builders/person_mask.py').read(), g); g['build']('/project1/lab')
build(parent_path, name, controls=True, vision=None) is idempotent (ops reused by name). vision=True/False sets the
Visionon toggle (loads / unloads the C++ plugin); None keeps the COMP's current value (new COMP: off).
Network: source (stored clip or In TOP) -> vis_in (Resolution TOP, Inputscale; 960x540 = fast path, T-99) -> avm
(CPlusPlus TOP, AppleVisionMask.plugin loaded by ABSOLUTE PATH, never the per-user Plugins folder, T-81/T-99; mask in
alpha only) -> mask_sel (no plugin -> full matte) -> mask_blur (Feather + Grow) -> ONE compute pass `matte` (edge
remap, temporal smooth via matte_fb, invert; source size, rgba16float) -> ONE compute pass `comp` (person = delayed
source or fill colour, over transparent / colour / in2 background, premultiplied) -> out1; matte -> out2;
`inverse` (1 - matte) -> out3. RGB delay: Cache TOP on the full-res source indexed by the plugin's latency_frames
(or the plugin's own delayed RGB via Render Select bufferindex 1). Compute mode only (T-46/T-47). T-70 safe: own
window closed first, destroys via safe_destroy, pane never moved. No functions in storage (T-67). Pure ASCII.
"""

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
NAME = 'CV_person_mask'
CLIP = REPO + '/media/webcam/webcam_ref_5s.mp4'
LOGIC = "op('person_mask_logic').module"

MATTE_GLSL = '''// person_mask: edge remap (Feather/Grow) + temporal smooth + invert (one compute pass, output = source size)
// in0 = blurred Vision mask (alpha, mask res, sampled bilinear), in1 = last matte (feedback, r = m)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uE;   // lo, hi, smooth, invert
uniform vec4 uR;   // reset, 0, 0, 0
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tvec2 uv = (vec2(px) + 0.5) / vec2(res);
\tfloat b = texture(sTD2DInputs[0], uv).a;
\tfloat m = clamp((b - uE.x) / max(uE.y - uE.x, 1e-6), 0.0, 1.0);
\tfloat last = texelFetch(sTD2DInputs[1], px, 0).r;
\tfloat s = (uR.x > 0.5) ? 0.0 : clamp(uE.z, 0.0, 0.99);
\tm = mix(m, last, s);
\tfloat o = (uE.w > 0.5) ? 1.0 - m : m;
\t// r = smoothed (un-inverted) state for the feedback, g = output matte
\tTDImageStoreOutput(0, ivec3(px, 0), vec4(m, o, 0.0, 1.0));
}
'''

COMP_GLSL = '''// person_mask: person over background, premultiplied (one compute pass, output = source size)
// in0 = person RGB (delayed source), in1 = matte (g), in2 = background TOP (premultiplied, sampled by uv)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uFill;  // rgb fill colour, a = person mode (0 source, 1 fill)
uniform vec4 uBg;    // rgb background colour, a = background alpha
uniform vec4 uM;     // background mode (0 none, 1 colour, 2 input), opacity, view (0 cutout, 1 matte, 2 inverse)
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tvec2 uv = (vec2(px) + 0.5) / vec2(res);
\tvec3 src = texture(sTD2DInputs[0], uv).rgb;
\tfloat m = clamp(texture(sTD2DInputs[1], uv).g, 0.0, 1.0) * uM.y;
\tvec3 pc = (uFill.a > 0.5) ? uFill.rgb : src;
\tvec4 b = vec4(0.0);
\tint bm = int(uM.x + 0.5);
\tif (bm == 1) b = vec4(uBg.rgb * uBg.a, uBg.a);
\telse if (bm == 2) b = texture(sTD2DInputs[2], uv);
\tvec4 o = vec4(pc * m, m) + b * (1.0 - m);
\tint v = int(uM.z + 0.5);
\tif (v == 1) o = vec4(vec3(m), 1.0);
\telse if (v == 2) o = vec4(vec3(1.0 - m), 1.0);
\tTDImageStoreOutput(0, ivec3(px, 0), TDOutputSwizzle(o));
}
'''

INV_GLSL = '''// person_mask: inverse matte (1 - matte), opaque mono
layout (local_size_x = 8, local_size_y = 8) in;
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tfloat m = texelFetch(sTD2DInputs[0], px, 0).g;
\tTDImageStoreOutput(0, ivec3(px, 0), vec4(vec3(1.0 - m), 1.0));
}
'''

MATTE_VIEW_GLSL = '''// person_mask: matte as opaque mono (g channel of the matte state)
layout (local_size_x = 8, local_size_y = 8) in;
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tfloat m = texelFetch(sTD2DInputs[0], px, 0).g;
\tTDImageStoreOutput(0, ivec3(px, 0), vec4(vec3(m), 1.0));
}
'''

WRAP_GLSL = '''// person_mask: light wrap + despill (FX7c 7C-08; one compute pass after comp, output = source size)
// in0 = comp (premultiplied), in1 = matte (g), in2 = wrap light (blurred background / source)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uW;     // light wrap, width px, gamma, despill
uniform vec4 uL;     // light from: 0 = in2 texture, 1 = colour; rgb colour in yzw
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tvec2 rs = vec2(res), pc = vec2(px) + 0.5;
\tvec4 c = texelFetch(sTD2DInputs[0], px, 0);
\tfloat m = clamp(texture(sTD2DInputs[1], pc / rs).g, 0.0, 1.0);
\tfloat acc = 0.0;
\tfor (int k = 0; k < 16; k++)
\t{
\t\tfloat r = k < 8 ? uW.y : 0.5 * uW.y;
\t\tfloat a = float(k % 8) * 0.785398163397 + (k < 8 ? 0.0 : 0.392699081699);
\t\tacc += clamp(texture(sTD2DInputs[1], (pc + r * vec2(cos(a), sin(a))) / rs).g, 0.0, 1.0);
\t}
\tfloat band = m * pow(clamp(1.0 - acc / 16.0, 0.0, 1.0), max(uW.z, 1e-3));
\tvec3 rgb = c.rgb;
\trgb.g += (min(rgb.g, max(rgb.r, rgb.b)) - rgb.g) * clamp(uW.w, 0.0, 1.0) * m;   // person only
\tvec3 L = uL.x < 0.5 ? texture(sTD2DInputs[2], pc / rs).rgb : uL.yzw;
\tvec3 lw = clamp(uW.x * band * L, 0.0, 1.0);
\trgb += (vec3(m) - rgb) * lw;
\tTDImageStoreOutput(0, ivec3(px, 0), vec4(rgb, c.a));
}
'''

STAGES = [
    {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'person_mask_logic', 'par_exec'],
     'body': 'zkit panel (Matte + Look pages); pulse Opencontrols. person_mask_logic: pure logic the par '
             'expressions call (Inputscale -> Vision size, Feather/Grow -> blur + edge remap, latency -> cache index).'},
    {'title': '1 Input', 'role': 'input', 'ops': ['in1', 'clip', 'src_switch', 'src', 'in2'],
     'body': 'Source = stored clip (default webcam_ref_5s.mp4) or the In TOP in1. in2 = optional background TOP.'},
    {'title': '2 Apple Vision', 'role': 'process', 'ops': ['vis_in', 'avm', 'avm_info', 'avm_rgb', 'nomask',
                                                           'mask_sel'],
     'body': 'vis_in = Inputscale (half = 960x540 fast path, T-99). avm = AppleVisionMask C++ TOP loaded by absolute '
             'path when Visionon (mask in ALPHA only). avm_info: latency_frames. avm_rgb = plugin delayed RGB '
             '(Render Select bufferindex 1). mask_sel: Vision off -> nomask (alpha 1, full matte).'},
    {'title': 'Feedback', 'role': 'feedback', 'ops': ['blank', 'matte_fb'],
     'body': 'matte_fb = last matte (temporal smooth); blank = clear start.'},
    {'title': '3 Matte', 'role': 'process', 'ops': ['mask_blur', 'matte', 'matte_compute', 'rgb_delay',
                                                    'rgb_sel'],
     'body': 'mask_blur: gaussian, size from Feather + |Grow|. matte = ONE compute pass: linear remap [lo, hi] '
             '(edge moves Grow px, Feather px soft), mix with last (Smooth), Invert. rgb_delay = Cache TOP of the '
             'full-res source, index = -latency_frames, so colour and mask line up.'},
    {'title': '3b Light wrap', 'role': 'process', 'ops': ['wrap_src', 'wrap_blur', 'wrap', 'wrap_compute', 'wrap_sel'],
     'body': 'Light wrap (7C-08): the blurred background (in2) or the blurred source bleeds over the matte edge band '
             '(ring of 16 taps at Wrapwidth), screen-added and kept premultiplied; Despill pulls green to max(r, b). '
             'Lightwrap 0 and Despill 0 = comp exactly (wrap not cooked).'},
    {'title': '4 Outputs', 'role': 'output', 'ops': ['comp', 'comp_compute', 'out1', 'matte_view',
                                                     'matte_view_compute', 'out2', 'inverse', 'inverse_compute',
                                                     'out3'],
     'body': 'comp = person (source or Fill colour) over transparent / colour / in2, PREMULTIPLIED -> out1. '
             'out2 = matte (white = person), out3 = inverse. View par shows matte/inverse on out1 for checks.'},
]


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
        return
    if getattr(c.par, name, None) is not None:
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


def _pars(c, L):
    M, K, S = 'Matte', 'Look', 'Setup'
    _par(c, M, 'Float', 'Feather', 'Feather px', 2.0, (0, 20), clamp_min=True)
    _par(c, M, 'Float', 'Grow', 'Choke/grow px', 0.0, (-20, 20))
    _par(c, M, 'Float', 'Smooth', 'Temporal smooth', 0.3, (0, 0.95), clamp_min=True)
    _par(c, M, 'Toggle', 'Invert', 'Invert', False)
    _par(c, M, 'Float', 'Opacity', 'Opacity', 1.0, (0, 1))
    _par(c, K, 'Menu', 'Person', 'Person', 'source', menu=L.PERSON)
    _par(c, K, 'RGB', 'Fillcolor', 'Fill colour', (1.0, 1.0, 1.0))
    _par(c, K, 'Menu', 'Background', 'Background', 'none', menu=L.BACKGROUND)
    _par(c, K, 'RGB', 'Bgcolor', 'Bg colour', (0.0, 0.0, 0.0))
    _par(c, K, 'Float', 'Bgalpha', 'Bg alpha', 1.0, (0, 1))
    _par(c, K, 'Menu', 'View', 'View on out1', 'cutout',
         menu=[('cutout', 'Cut-out'), ('matte', 'Matte'), ('inverse', 'Inverse matte')])
    _par(c, 'Wrap', 'Float', 'Lightwrap', 'Light wrap', 0.0, (0, 4))
    _par(c, 'Wrap', 'Float', 'Wrapwidth', 'Wrap width px', 12.0, (0, 100))
    _par(c, 'Wrap', 'Float', 'Wrapblur', 'Wrap light blur px', 24.0, (0, 200))
    _par(c, 'Wrap', 'Float', 'Wrapgamma', 'Wrap falloff (gamma)', 1.0, (0.1, 4))
    _par(c, 'Wrap', 'Menu', 'Wrapsrc', 'Wrap light from', 'background', menu=L.WRAPSRC)
    _par(c, 'Wrap', 'Float', 'Despill', 'Despill (green -> max(r, b))', 0.0, (0, 1))
    _par(c, S, 'Toggle', 'Visionon', 'Vision on (loads the C++ plugin)', False)
    _par(c, S, 'Menu', 'Quality', 'Vision quality', 'Balanced', menu=L.QUALITY)
    _par(c, S, 'Menu', 'Inputscale', 'Vision input size', 'half', menu=L.INPUTSCALE)
    _par(c, S, 'Menu', 'Visionres', 'Vision resolution', 'Input', menu=[('Input', 'Input size'),
                                                                         ('Native', 'Native (Vision decides)')])
    _par(c, S, 'Menu', 'Rgbdelay', 'RGB delay', 'match', menu=L.RGBDELAY)
    _par(c, S, 'Menu', 'Source', 'Source', 'clip', menu=[('clip', 'Stored clip'), ('input', 'In TOP (in1)')])
    _par(c, S, 'File', 'Clipfile', 'Clip file', CLIP)
    _par(c, S, 'File', 'Pluginpath', 'Plugin path', L.PLUGIN)
    _par(c, S, 'Pulse', 'Resetsmooth', 'Reset smoothing')


def _glsl(c, name, code, w_expr, h_expr, fmt, uniforms=()):
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
    if uniforms:
        g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), len(uniforms))
    for k, (uname, exprs) in enumerate(uniforms):
        getattr(g.par, 'vec{}name'.format(k)).val = uname
        for ax, e in zip('xyzw', exprs):
            getattr(g.par, 'vec{}value{}'.format(k, ax)).expr = e
    return g


def build(parent_path='/project1/lab', name=NAME, controls=True, vision=None):
    pc = op(parent_path)
    c = pc.op(name) or pc.create(baseCOMP, name)
    c.allowCooking = True
    was_open = _close_window(c)
    lg = _mk(c, textDAT, 'person_mask_logic')
    lg.text = open(REPO + '/builders/person_mask_logic.py').read()
    L = lg.module
    _pars(c, L)
    if vision is not None:
        c.par.Visionon = bool(vision)
    c.comment = ('person_mask: Apple Vision person matte (C++ TOP by path) -> premultiplied cut-out (out1), '
                 'matte (out2), inverse (out3)')

    # 1 Input
    inp = _mk(c, inTOP, 'in1')
    clip = _mk(c, moviefileinTOP, 'clip')
    clip.par.file.expr = 'parent().par.Clipfile'
    clip.par.play = True
    sw = _mk(c, switchTOP, 'src_switch')
    _wire(inp, sw, 0)
    _wire(clip, sw, 1)
    sw.par.index.expr = "1 if parent().par.Source.eval() == 'clip' else 0"
    src = _mk(c, nullTOP, 'src')
    _wire(sw, src)
    bgin = _mk(c, inTOP, 'in2')

    # 2 Apple Vision
    vis = _mk(c, resolutionTOP, 'vis_in')
    _wire(src, vis)
    vis.par.outputresolution = 'custom'
    vexpr = "{}.vision_size(op('src').width, op('src').height, parent().par.Inputscale.eval())[{}]"
    vis.par.resolutionw.expr = vexpr.format(LOGIC, 0)
    vis.par.resolutionh.expr = vexpr.format(LOGIC, 1)
    vis.par.format = 'rgba8fixed'
    avm = _mk(c, cplusplusTOP, 'avm')
    _wire(vis, avm)
    nomask = _mk(c, constantTOP, 'nomask')
    nomask.par.outputresolution = 'custom'
    nomask.par.resolutionw.expr = "op('vis_in').width"
    nomask.par.resolutionh.expr = "op('vis_in').height"
    nomask.par.colorr = nomask.par.colorg = nomask.par.colorb = 0
    nomask.par.alpha = 1
    sel = _mk(c, switchTOP, 'mask_sel')
    _wire(nomask, sel, 0)
    _wire(avm, sel, 1)
    sel.par.index.expr = '1 if parent().par.Visionon else 0'
    info = _mk(c, infoCHOP, 'avm_info')
    info.par.op = avm.name
    rgbp = _mk(c, renderselectTOP, 'avm_rgb')
    rgbp.par.top = avm.name
    rgbp.par.bufferindex = 1
    # plugin: absolute path only while Visionon (T-99); its own pars follow ours once loaded (first cook)
    set_vision(c, c.par.Visionon.eval())

    # 3 Matte
    blur = _mk(c, blurTOP, 'mask_blur')
    _wire(sel, blur)
    blur.par.type = 'gaussian'
    blur.par.extend = 'hold'
    blur.par.size.expr = "{}.edge_params(parent().par.Feather, parent().par.Grow)[0]".format(LOGIC)
    blur.par.format = 'rgba16float'
    blank = _mk(c, constantTOP, 'blank')
    blank.par.outputresolution = 'custom'
    blank.par.resolutionw.expr = "op('src').width"
    blank.par.resolutionh.expr = "op('src').height"
    blank.par.format = 'rgba16float'
    blank.par.colorr = blank.par.colorg = blank.par.colorb = 0
    blank.par.alpha = 1
    fb = _mk(c, feedbackTOP, 'matte_fb')
    _wire(blank, fb)
    ep = "{}.edge_params(parent().par.Feather, parent().par.Grow)".format(LOGIC)
    matte = _glsl(c, 'matte', MATTE_GLSL, "op('src').width", "op('src').height", 'rgba16float',
                  [('uE', (ep + '[1]', ep + '[2]', 'parent().par.Smooth', '1 if parent().par.Invert else 0')),
                   ('uR', ("1 if absTime.frame - (lambda k, f: k if k <= f else -99)(parent().fetch('jz_reset', -99, search=False), absTime.frame) < 3 else 0",
                           '0', '0', '0'))])
    _wire(blur, matte, 0)
    _wire(fb, matte, 1)
    fb.par.top = matte.name
    cache = _mk(c, cacheTOP, 'rgb_delay')
    _wire(src, cache)
    cache.par.cachesize = L.CACHE_SIZE
    cache.par.outputindex.expr = ("{}.cache_index(op('avm_info')['latency_frames'] if parent().par.Visionon "
                                  "and op('avm_info')['latency_frames'] is not None else 0)").format(LOGIC)
    rsel = _mk(c, switchTOP, 'rgb_sel')
    _wire(cache, rsel, 0)
    _wire(rgbp, rsel, 1)
    _wire(src, rsel, 2)
    rsel.par.index.expr = ("{L}.menu_index({L}.RGBDELAY, parent().par.Rgbdelay.eval()) if parent().par.Visionon "
                           "else 2").format(L=LOGIC)
    rsel.par.blend = False

    # 4 Outputs
    comp = _glsl(c, 'comp', COMP_GLSL, "op('src').width", "op('src').height", 'rgba8fixed',
                 [('uFill', ('parent().par.Fillcolorr', 'parent().par.Fillcolorg', 'parent().par.Fillcolorb',
                             "1 if parent().par.Person.eval() == 'fill' else 0")),
                  ('uBg', ('parent().par.Bgcolorr', 'parent().par.Bgcolorg', 'parent().par.Bgcolorb',
                           'parent().par.Bgalpha')),
                  ('uM', ("{L}.menu_index({L}.BACKGROUND, parent().par.Background.eval())".format(L=LOGIC),
                          'parent().par.Opacity',
                          "['cutout', 'matte', 'inverse'].index(parent().par.View.eval())", '0'))])
    _wire(rsel, comp, 0)
    _wire(matte, comp, 1)
    _wire(bgin, comp, 2)
    # 3b Light wrap (7C-08): only cooks while Lightwrap or Despill is on
    wsrc = _mk(c, switchTOP, 'wrap_src')
    _wire(bgin, wsrc, 0)
    _wire(src, wsrc, 1)
    wsrc.par.index.expr = "1 if parent().par.Wrapsrc.eval() == 'source' else 0"
    wblur = _mk(c, blurTOP, 'wrap_blur')
    _wire(wsrc, wblur)
    wblur.par.type = 'gaussian'
    wblur.par.extend = 'hold'
    wblur.par.size.expr = 'parent().par.Wrapblur'
    wblur.par.outputresolution = 'custom'
    wblur.par.resolutionw.expr = "op('src').width"
    wblur.par.resolutionh.expr = "op('src').height"
    wblur.par.format = 'rgba16float'
    BGC = "(parent().par.Wrapsrc.eval() == 'background' and parent().par.Background.eval() == 'color')"
    wrap = _glsl(c, 'wrap', WRAP_GLSL, "op('src').width", "op('src').height", 'rgba16float',
                 [('uW', ('parent().par.Lightwrap', 'parent().par.Wrapwidth', 'parent().par.Wrapgamma',
                          'parent().par.Despill')),
                  ('uL', ('1 if %s else 0' % BGC, 'parent().par.Bgcolorr', 'parent().par.Bgcolorg',
                          'parent().par.Bgcolorb'))])
    _wire(comp, wrap, 0)
    _wire(matte, wrap, 1)
    _wire(wblur, wrap, 2)
    wsel = _mk(c, switchTOP, 'wrap_sel')
    _wire(comp, wsel, 0)
    _wire(wrap, wsel, 1)
    wsel.par.index.expr = '1 if (parent().par.Lightwrap > 0 or parent().par.Despill > 0) else 0'
    wsel.par.blend = False
    out1 = _mk(c, outTOP, 'out1')
    _wire(wsel, out1)
    mv = _glsl(c, 'matte_view', MATTE_VIEW_GLSL, "op('matte').width", "op('matte').height", 'r8fixed')
    _wire(matte, mv)
    out2 = _mk(c, outTOP, 'out2')
    _wire(mv, out2)
    inv = _glsl(c, 'inverse', INV_GLSL, "op('matte').width", "op('matte').height", 'r8fixed')
    _wire(matte, inv)
    out3 = _mk(c, outTOP, 'out3')
    _wire(inv, out3)

    pe = _mk(c, parameterexecuteDAT, 'par_exec')
    pe.text = ("# person_mask: Resetsmooth -> matte feedback cleared for 3 frames; Visionon -> rebuild the plugin "
               "step\ndef onPulse(par):\n\tif par.name == 'Resetsmooth':\n\t\tparent().store('jz_reset', "
               "int(absTime.frame))\n\treturn\n\ndef onValueChange(par, prev):\n\tif par.name == 'Visionon':\n"
               "\t\tg = dict(globals()); exec(open('" + REPO + "/builders/person_mask.py').read(), g)\n"
               "\t\tg['set_vision'](parent(), par.eval())\n\treturn\n")
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Resetsmooth Visionon'
    pe.par.onpulse = True
    pe.par.valuechange = True
    pe.par.active = True

    ui = 'skipped'
    if controls:
        ns = dict(globals())
        exec(open(REPO + '/builders/zkit.py').read(), ns)
        ui = ns['build_controls'](c.path, pages=['Matte', 'Look', 'Wrap'], d=56, cols=6, open_window=was_open)

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
    return {'comp': c.path, 'ops': len(c.children), 'vision': bool(c.par.Visionon.eval()), 'ui': str(ui)[:200],
            'layout': str(lay)[:300]}


PLUGIN_BINDS = (('Outputmode', "'Maskonly'"), ('Quality', 'parent().par.Quality.eval()'),
                ('Nativeresolution', 'parent().par.Visionres.eval()'))

BIND_CODE = '''o = op(args[0])
left = args[1]
if o is not None and o.par.plugin.eval():
\tif getattr(o.par, 'Quality', None) is None:
\t\to.cook()
\tif getattr(o.par, 'Quality', None) is None:
\t\tif left > 0:
\t\t\trun(args[2], args[0], left - 1, args[2], args[3], delayFrames=1)
\telse:
\t\tfor pn, e in args[3]:
\t\t\tp = getattr(o.par, pn, None)
\t\t\tif p is not None and p.expr != e:
\t\t\t\tp.expr = e
'''


def bind_plugin_pars(avm_path, tries=60):
    """Bind the plugin's Outputmode/Quality/Nativeresolution to the COMP pars once they exist."""
    run(BIND_CODE, avm_path, tries, BIND_CODE, PLUGIN_BINDS, delayFrames=1)


def set_vision(c, on):
    """Vision on: load the AppleVisionMask plugin by absolute path once (T-99) and un-bypass it. Vision off: bypass
    only; the plugin stays loaded. Never unload/reload a running AppleVisionMask: unload + reload cycles every 30
    frames segfaulted the scratch TD (LEARNINGS T-106). To free it for good: bypass, wait >= 10 frames, then
    delete the COMP (or Unloadplugin by hand)."""
    avm = c.op('avm')
    if avm is None:
        return 'no avm'
    if on:
        path = c.par.Pluginpath.eval()
        if avm.par.plugin.eval() != path:
            avm.par.plugin = path
        avm.bypass = False
        # the plugin's own pars exist only after its first cook: bind them when they appear (up to 60 frames)
        bind_plugin_pars(avm.path, 60)
        return 'on'
    avm.bypass = True
    return 'bypassed'
