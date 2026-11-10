"""Builder for the face_track COMP (Apple Vision face landmarks through helpers/vision_bridge), TD 2025.31550.

Run inside TD (td_exec), re-runnable / idempotent (ops are reused, texts and pars rewritten, the helper this COMP
started is stopped first). T-70 crash-safe: the COMP's own controls_window is closed before anything changes, the
`controls` container is never destroyed (its widgets are regenerated in place only when build(..., regen_ui=True) or
when it is empty), every destroy goes through the MCP's safe_destroy, and the builder never moves a network pane:
    g = dict(globals()); exec(open('<repo>/builders/face_track.py').read(), g); g['build']('/project1/lab')
Spec: docs/research/BH_rudiment_face_tracking.md. Pure logic: builders/face_track_logic.py (tests:
test/test_face_track.py). TD glue: builders/face_track_runtime.py. Both are copied into Text DATs, as is the socket
client helpers/vision_bridge/lib/camera_bridge.py, so the COMP is self-contained except for the helper binary
(par Helper, default helpers/vision_bridge/build/jzb_vision_bridge).
"""
import os

REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
NAME = 'FT_face_track'
CLIP = REPO + '/media/webcam/webcam_ref_5s.mp4'
HELPER = REPO + '/helpers/vision_bridge/build/jzb_vision_bridge'
SLIDER_PAGE = 'Track'

FRAME_EXEC = '''# face_track: pump the vision helper at frame start, send the newest frame at frame end (runtime DAT)
def onFrameStart(frame):
\tparent().op('runtime').module.frame_start(parent())
\treturn

def onFrameEnd(frame):
\tparent().op('runtime').module.frame_end(parent())
\treturn
'''

PAR_EXEC = '''# face_track: Active off stops the helper; Calibrate captures the rest pose; Opencontrols opens the panel window
def onValueChange(par, prev):
\tif par.name == 'Active' and not par.eval():
\t\tparent().op('runtime').module.stop(parent())
\treturn

def onPulse(par):
\tif par.name == 'Opencontrols':
\t\tparent().op('controls_window').par.winopen.pulse()
\telif par.name == 'Calibrate':
\t\tparent().op('runtime').module.calibrate(parent())
\treturn
'''

SCRIPT_CB = '''# face_track Script CHOP: channels come from the runtime DAT ({fn})
def onCook(scriptOp):
\tscriptOp.parent().op('runtime').module.{fn}(scriptOp.parent(), scriptOp)
\treturn
'''

MASK_GLSL = '''// face_track masks: one compute pass, even-odd point-in-polygon over every polygon (T-46/T-47: compute, no chain).
// uPolys texel = (x, v, polygon index, kind): kind 0 face -> R, 1 eyes -> G, 2 mouth -> B, -1 dummy.
layout (local_size_x = 8, local_size_y = 8) in;
uniform samplerBuffer uPolys;
void main()
{
	ivec2 px = ivec2(gl_GlobalInvocationID.xy);
	ivec2 res = ivec2(uTDOutputInfo.res.zw);
	if (px.x >= res.x || px.y >= res.y) return;
	vec2 p = (vec2(px) + 0.5) / vec2(res);
	int n = min(textureSize(uPolys), 4096);
	vec4 m = vec4(0.0, 0.0, 0.0, 1.0);
	int start = 0;
	bool c = false;
	for (int i = 0; i < n; i++) {
		vec4 a = texelFetch(uPolys, i);
		bool last = (i + 1 >= n) || (texelFetch(uPolys, i + 1).z != a.z);
		vec4 b = last ? texelFetch(uPolys, start) : texelFetch(uPolys, i + 1);
		if (((a.y > p.y) != (b.y > p.y)) && (p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x)) c = !c;
		if (last) {
			if (c && a.w > -0.5) {
				int k = int(a.w + 0.5);
				if (k == 0) m.r = 1.0; else if (k == 1) m.g = 1.0; else m.b = 1.0;
			}
			c = false;
			start = i + 1;
		}
	}
	TDImageStoreOutput(0, ivec3(px, 0), TDOutputSwizzle(m));
}
'''

WIRE_GLSL = '''// face_track wire overlay: one compute pass over the video. Per face a bbox early-out, then the distance to each
// landmark segment (uv). Zero-length segments are pupils, drawn as dots. Over-composite, premultiplied.
layout (local_size_x = 8, local_size_y = 8) in;
uniform samplerBuffer uSegs;    // x0 v0 x1 v1
uniform samplerBuffer uFbox;    // min x, min v, max x, max v
uniform samplerBuffer uFrange;  // start, count, present, -
uniform vec4 uWire;             // rgb, opacity
uniform vec4 uParams;           // width px
void main()
{
	ivec2 px = ivec2(gl_GlobalInvocationID.xy);
	vec2 res = uTDOutputInfo.res.zw;
	if (px.x >= int(res.x) || px.y >= int(res.y)) return;
	vec4 src = texelFetch(sTD2DInputs[0], px, 0);
	vec2 p = vec2(px) + 0.5;
	float hw = max(uParams.x, 0.25) * 0.5;
	float d = 1e9;
	float pres = 0.0;
	int nf = min(textureSize(uFrange), 32);
	for (int f = 0; f < nf; f++) {
		vec4 rg = texelFetch(uFrange, f);
		if (rg.y < 0.5) continue;
		vec4 bb = texelFetch(uFbox, f) * vec4(res, res);
		float m = hw * 3.0 + 2.0;
		if (p.x < bb.x - m || p.x > bb.z + m || p.y < bb.y - m || p.y > bb.w + m) continue;
		int s0 = int(rg.x + 0.5);
		int sn = min(int(rg.y + 0.5), 512);
		for (int i = 0; i < sn; i++) {
			vec4 sg = texelFetch(uSegs, s0 + i) * vec4(res, res);
			vec2 pa = p - sg.xy;
			vec2 ba = sg.zw - sg.xy;
			float bb2 = dot(ba, ba);
			float dd;
			if (bb2 < 1e-6) dd = max(0.0, length(pa) - hw * 2.0);
			else dd = length(pa - ba * clamp(dot(pa, ba) / bb2, 0.0, 1.0));
			if (dd < d) { d = dd; pres = rg.z; }
		}
	}
	float a = clamp(hw + 0.5 - d, 0.0, 1.0) * clamp(uWire.a, 0.0, 1.0) * pres;
	vec4 col = vec4(uWire.rgb * a + src.rgb * (1.0 - a), a + src.a * (1.0 - a));
	TDImageStoreOutput(0, ivec3(px, 0), TDOutputSwizzle(col));
}
'''

STAGES = [
    {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'par_exec'],
     'body': 'Panel (autoUI) bound to the Track page; Opencontrols opens the window. par_exec: Active off stops the helper.'},
    {'title': '1 Source', 'role': 'input', 'ops': ['in_video', 'clip', 'src_switch', 'src_flip', 'src'],
     'body': 'Source: stored clip (default) or the In TOP. Mirror flips before detection.'},
    {'title': '2 Vision bridge', 'role': 'process',
     'ops': ['detect', 'frame_exec', 'runtime', 'vision_client', 'face_track_logic', 'info', 'out_info'],
     'body': 'detect = small copy read back each frame; native arm64 helper (Apple Vision landmarks, kind 5), one request in flight, newest frame wins. Status in info.'},
    {'title': '3 Landmarks + measures', 'role': 'process', 'ops': ['pts', 'out_pts', 'ctl', 'out_ctl'],
     'body': 'pts: f<n>_<region>_<kk>x/y (0..1, top-left). ctl: facecount + per face present, rect, roll/yaw/pitch, eye/mouth openness, smile.'},
    {'title': '4 Masks', 'role': 'process',
     'ops': ['polys', 'mask_raw', 'mask_blur', 'face_sel', 'eyes_sel', 'mouth_sel', 'out_face', 'out_eyes', 'out_mouth'],
     'body': 'One compute pass draws face / eyes / mouth polygons into R / G / B; blur; split to mono Out TOPs.'},
    {'title': '5 Wire overlay', 'role': 'output', 'ops': ['segs', 'fbox', 'frange', 'overlay', 'out_video'],
     'body': 'Compute pass: landmark wire (and boxes) over the video. No faces = the video passes through.'},
]


def _page(comp, name):
    for p in comp.customPages:
        if p.name == name:
            return p
    return comp.appendCustomPage(name)


def _par(comp, page, style, name, label, default=None, rng=None, menu=None, readonly=False):
    pg = _page(comp, page)
    if hasattr(comp.par, name) and getattr(comp.par, name) is not None:
        p = getattr(comp.par, name)
        if style != 'RGB' and p.label != label:
            p.label = label
        if rng is not None and style in ('Int', 'Float'):  # a rebuild keeps the value but updates range + default
            p.normMin, p.normMax = rng
            p.min, p.max = rng
            if default is not None:
                p.default = default
        return p
    if style == 'Menu':
        p = pg.appendMenu(name, label=label)[0]
        p.menuNames = [m[0] for m in menu]
        p.menuLabels = [m[1] for m in menu]
    else:
        p = getattr(pg, 'append' + style)(name, label=label)
        p = p[0]
    if rng is not None:
        p.normMin, p.normMax = rng
        p.min, p.max = rng
    if default is not None:
        if style == 'RGB':
            for k, v in zip(getattr(comp.parGroup, name), default):
                k.default = v
                k.val = v
            return p
        p.default = default
        p.val = default
    if readonly:
        p.readOnly = True
    return p


def _pars(comp):
    T, S, C, O = SLIDER_PAGE, 'Setup', 'Colours', 'Output'
    _par(comp, T, 'Toggle', 'Active', 'Active (runs the helper)', False)
    _par(comp, T, 'Int', 'Maxfaces', 'Max faces', 4, (1, 32))  # user 26 Oct: multi-face by default, no hard cap
    _par(comp, T, 'Float', 'Smooth', 'Smoothing (One-Euro)', 0.5, (0, 1))
    _par(comp, T, 'Float', 'Minconf', 'Min confidence', 0.5, (0, 1))
    _par(comp, T, 'Int', 'Holdframes', 'Hold frames on loss', 8, (0, 60))
    _par(comp, T, 'Toggle', 'Mirror', 'Mirror source', False)
    _par(comp, T, 'Toggle', 'Showwire', 'Show wire', True)
    _par(comp, T, 'Toggle', 'Showboxes', 'Show face boxes', False)
    _par(comp, T, 'Float', 'Wirewidth', 'Wire width (px)', 2.0, (0.5, 8))
    _par(comp, T, 'Float', 'Wireopacity', 'Wire opacity', 1.0, (0, 1))
    _par(comp, T, 'Float', 'Maskblur', 'Mask blur (px)', 4.0, (0, 32))
    _par(comp, T, 'Float', 'Maskgrow', 'Mask grow (x0.1% h)', 0.0, (-20, 40))
    _par(comp, T, 'Float', 'Eyeexpand', 'Eye mask scale', 1.3, (0.5, 3))
    _par(comp, T, 'Float', 'Mouthexpand', 'Mouth mask scale', 1.1, (0.5, 3))
    _par(comp, T, 'Float', 'Forehead', 'Face mask forehead', 0.25, (0, 0.8))
    _par(comp, T, 'Pulse', 'Opencontrols', 'Open controls window')
    _par(comp, S, 'Menu', 'Source', 'Source', 'clip', menu=[('clip', 'Stored clip'), ('input', 'In TOP (in_video)')])
    _par(comp, S, 'File', 'Clipfile', 'Clip file', CLIP)
    _par(comp, S, 'Menu', 'Detectsize', 'Detect width', 'w640', menu=[('w480', '480 px'), ('w640', '640 px'), ('w960', '960 px')])
    _par(comp, S, 'Menu', 'Maskres', 'Mask resolution', 'r512', menu=[('r256', '256 wide'), ('r512', '512 wide'), ('full', 'Source size')])
    _par(comp, S, 'Menu', 'Rollunit', 'Roll / yaw / pitch unit', 'deg', menu=[('deg', 'Degrees'), ('rad', 'Radians')])
    _par(comp, S, 'File', 'Helper', 'Vision helper binary', HELPER)
    _par(comp, S, 'Float', 'Eyeclosed', 'Eye ratio closed', 0.12, (0, 1))
    _par(comp, S, 'Float', 'Eyeopen', 'Eye ratio open', 0.35, (0, 1))
    _par(comp, S, 'Float', 'Mouthrest', 'Mouth ratio at rest', 0.02, (0, 1))
    _par(comp, S, 'Float', 'Mouthmax', 'Mouth ratio wide open', 0.6, (0, 1))
    _par(comp, S, 'Pulse', 'Calibrate', 'Calibrate rest pose (face 1)')
    _par(comp, S, 'Toggle', 'Fakeface', 'Fake face (test without helper)', False)
    _par(comp, C, 'RGB', 'Wirecolor', 'Wire colour', (1.0, 1.0, 1.0))
    _par(comp, O, 'Int', 'Facecount', 'Faces tracked', 0, readonly=True)
    _par(comp, O, 'Float', 'Latency', 'Round trip median (ms)', 0.0, readonly=True)
    _par(comp, O, 'Str', 'Status', 'Status', 'off', readonly=True)


def _kill(o):
    """T-70: never a bare destroy (a window/pane may show it). The MCP's safe_destroy closes those windows, moves
    panes off, renames the op out of the way and defers the destroy; fallback only when the MCP is absent."""
    h = op('/jazib_mcp/handlers')
    fn = getattr(h.module, 'safe_destroy', None) if h is not None else None
    if fn is not None:
        fn(o)
    else:
        o.destroy()


def _close_window(comp):
    w = comp.op('controls_window')
    if w is not None and getattr(w, 'isOpen', False):
        w.par.winclose.pulse()
        return True
    return False


def _mk(comp, optype, name):
    o = comp.op(name)
    if o is not None and o.OPType != optype.__name__:
        _kill(o)
        o = None
    return o or comp.create(optype, name)


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _read(path):
    with open(path) as f:
        return f.read()


def _glsl(comp, name, code, arrays, vecs, res_w, res_h, inp=None):
    g = _mk(comp, glslTOP, name)
    g.par.mode = 'compute'
    cd = g.par.computedat.eval()
    if cd is None:
        cd = _mk(comp, textDAT, name + '_compute')
        g.par.computedat = cd.name
    cd.text = code
    g.par.outputresolution = 'custom'
    g.par.resolutionw.expr = res_w
    g.par.resolutionh.expr = res_h
    g.par.format = 'rgba8fixed'
    g.par.autodispatchsize = True
    g.seq.array.numBlocks = len(arrays)
    for k, (uname, chop) in enumerate(arrays):
        getattr(g.par, 'array{}name'.format(k)).val = uname
        getattr(g.par, 'array{}type'.format(k)).val = 'vec4'
        getattr(g.par, 'array{}chop'.format(k)).val = chop
        getattr(g.par, 'array{}arraytype'.format(k)).val = 'texturebuffer'
    if vecs:
        g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), len(vecs))
        for k, (uname, exprs) in enumerate(vecs):
            getattr(g.par, 'vec{}name'.format(k)).val = uname
            for ax, e in zip('xyzw', exprs):
                getattr(g.par, 'vec{}value{}'.format(k, ax)).expr = e
    if inp is not None:
        _wire(inp, g)
    return g


def _script_chop(comp, name, fn):
    s = _mk(comp, scriptCHOP, name)
    cb = s.par.callbacks.eval()
    if cb is None:
        cb = _mk(comp, textDAT, name + '_callbacks')
        s.par.callbacks = cb.name
    cb.text = SCRIPT_CB.format(fn=fn)
    return s


def _zkit_refresh(comp):
    """The COMP carries a zkit panel (builders/zkit.py, rolled out 26 Oct): refresh it in place (T-70 safe) instead
    of making autoUI widgets. None when there is no kit panel."""
    p_ = comp.op('controls')
    if p_ is None or p_.op('zk_rt') is None:
        return None
    ns_ = dict(globals())
    exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/zkit.py').read(), ns_)
    return ns_['build_controls'](comp.path)


def _controls(comp, regen_ui=False):
    """T-70: the container is reused, never destroyed. Widgets are regenerated only on request or when it is empty
    (the window is closed first, old widgets go through safe_destroy)."""
    zk = _zkit_refresh(comp)
    if zk is not None:
        return comp.op('controls'), 'zkit ' + zk['rebuild']
    au = op('/project1/show/tools/autoUI')
    ctrl = comp.op('controls')
    if ctrl is not None and ctrl.OPType != 'containerCOMP':
        _kill(ctrl)
        ctrl = None
    if ctrl is None:
        ctrl = comp.create(containerCOMP, 'controls')
    ctrl.par.w = 380
    ctrl.par.align = 'verttb'
    win = _mk(comp, windowCOMP, 'controls_window')
    if ctrl.children and not regen_ui:
        _win_pars(win, ctrl)
        return ctrl, 'ok (panel kept)'
    _close_window(comp)
    for w in list(ctrl.children):
        _kill(w)
    if au is None:
        return ctrl, 'autoUI missing: panel empty'
    prev = (au.par.Pagetabs.eval(), au.par.Pagescope.eval())
    try:
        au.par.Pagetabs = False
        au.par.Pagescope = SLIDER_PAGE
        au.ext.AutoUIExt.GenerateUI(customComp=comp, ui=ctrl, shortcutDialog=False)
    finally:
        au.par.Pagetabs, au.par.Pagescope = prev
    for w in ctrl.children:
        if hasattr(w.par, 'hmode'):
            w.par.hmode = 'fill'
        if hasattr(w.par, 'clone'):
            w.par.enablecloning = False
            w.par.clone = ''
    hd = ctrl.op('header')
    if hd is not None and hasattr(hd.par, 'Headerlabel'):
        hd.par.Headerlabel = 'FACE TRACK  controls'
    ctrl.par.h = sum(int(c.par.h) for c in ctrl.children if c.isPanel) + 6
    ctrl.comment = "CONTROLS: widgets bound to this COMP's Track page (the COMP works with or without this panel)"
    _win_pars(win, ctrl)
    return ctrl, 'ok (panel regenerated)'


def _win_pars(win, ctrl):
    win.par.winop = ctrl.name
    win.par.title = NAME + ' controls'
    win.par.winw = 400
    win.par.winh = min(int(ctrl.par.h) + 28, 1000)


def build(parent_path='/project1/lab', name=NAME, regen_ui=False):
    parent_comp = op(parent_path)
    comp = parent_comp.op(name) or parent_comp.create(baseCOMP, name)
    _close_window(comp)  # T-70: own window closed before any rebuild
    rt = comp.op('runtime')
    if rt is not None:
        try:
            rt.module.stop(comp)
        except Exception:
            pass
    _pars(comp)
    comp.comment = 'face_track: Apple Vision face landmarks (native helper) -> CHOPs, masks, wire overlay'

    # 2 texts first (fallible reads before touching the network, T-00b)
    logic = _read(REPO + '/builders/face_track_logic.py')
    runtime = _read(REPO + '/builders/face_track_runtime.py')
    client = _read(REPO + '/helpers/vision_bridge/lib/camera_bridge.py')

    # 1 Source
    inv = _mk(comp, inTOP, 'in_video')
    clip = _mk(comp, moviefileinTOP, 'clip')
    clip.par.file.expr = "parent().par.Clipfile"
    clip.par.playmode = 'sequential'
    clip.par.play = True
    sw = _mk(comp, switchTOP, 'src_switch')
    _wire(inv, sw, 0)
    _wire(clip, sw, 1)
    sw.par.index.expr = "1 if parent().par.Source.eval() == 'clip' else 0"
    fl = _mk(comp, flipTOP, 'src_flip')
    _wire(sw, fl)
    fl.par.flipx.expr = 'parent().par.Mirror'
    src = _mk(comp, nullTOP, 'src')
    _wire(fl, src)

    # 2 Vision bridge
    det = _mk(comp, resolutionTOP, 'detect')
    _wire(src, det)
    det.par.outputresolution = 'custom'
    det.par.resolutionw.expr = "int(parent().par.Detectsize.eval()[1:])"
    det.par.resolutionh.expr = ("max(2, int(round(int(parent().par.Detectsize.eval()[1:]) * op('src').height / "
                                "max(1, op('src').width) / 2.0)) * 2)")
    det.par.format = 'rgba8fixed'
    for n, text in (('face_track_logic', logic), ('runtime', runtime), ('vision_client', client)):
        d = _mk(comp, textDAT, n)
        d.text = text
    info = _mk(comp, tableDAT, 'info')
    oi = _mk(comp, outDAT, 'out_info')
    _wire(info, oi)
    fx = _mk(comp, executeDAT, 'frame_exec')
    fx.text = FRAME_EXEC
    fx.par.framestart = True
    fx.par.frameend = True
    fx.par.active = True
    pe = _mk(comp, parameterexecuteDAT, 'par_exec')
    pe.text = PAR_EXEC
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Active Opencontrols Calibrate'
    pe.par.valuechange = True
    pe.par.onpulse = True
    pe.par.active = True

    # 3 Landmarks + measures
    pts = _script_chop(comp, 'pts', 'cook_pts')
    op_pts = _mk(comp, outCHOP, 'out_pts')
    _wire(pts, op_pts)
    ctl = _script_chop(comp, 'ctl', 'cook_ctl')
    op_ctl = _mk(comp, outCHOP, 'out_ctl')
    _wire(ctl, op_ctl)

    # 4 Masks
    _script_chop(comp, 'polys', 'cook_polys')
    mw = "{'r256': 256, 'r512': 512}.get(parent().par.Maskres.eval(), op('src').width)"
    mh = ("max(2, int(round(({}) * op('src').height / max(1, op('src').width))))".format(mw))
    mraw = _glsl(comp, 'mask_raw', MASK_GLSL, [('uPolys', 'polys')], [], mw, mh)
    mb = _mk(comp, blurTOP, 'mask_blur')
    _wire(mraw, mb)
    mb.par.size.expr = 'parent().par.Maskblur'
    for n, ch in (('face', 'red'), ('eyes', 'green'), ('mouth', 'blue')):
        r = _mk(comp, reorderTOP, n + '_sel')
        _wire(mb, r)
        for c in ('red', 'green', 'blue', 'alpha'):
            getattr(r.par, 'output' + c).val = 'input1'
            getattr(r.par, 'output' + c + 'chan').val = ch
        r.par.format = 'mono8fixed'
        o = _mk(comp, outTOP, 'out_' + n)
        _wire(r, o)

    # 5 Wire overlay
    for n, fn in (('segs', 'cook_segs'), ('fbox', 'cook_fbox'), ('frange', 'cook_frange')):
        _script_chop(comp, n, fn)
    ov = _glsl(comp, 'overlay', WIRE_GLSL, [('uSegs', 'segs'), ('uFbox', 'fbox'), ('uFrange', 'frange')],
               [('uWire', ('parent().par.Wirecolorr', 'parent().par.Wirecolorg', 'parent().par.Wirecolorb',
                           'parent().par.Wireopacity')),
                ('uParams', ('parent().par.Wirewidth', '0', '0', '0'))],
               "op('src').width", "op('src').height", inp=src)
    ov_out = _mk(comp, outTOP, 'out_video')
    _wire(ov, ov_out)

    # Controls
    ctrl, ui_note = _controls(comp, regen_ui)

    # COMP tile shows its output
    comp.par.opviewer.expr = "me.op('out_video')"
    comp.viewer = True
    for o in comp.children:
        if o.family in ('TOP', 'CHOP') or o.OPType in ('tableDAT', 'outDAT'):
            o.viewer = True

    # readable network (T-69: plan stored on the COMP, re-applied by later builds)
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(comp, STAGES, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    return {'comp': comp.path, 'ops': len(comp.children), 'ui': ui_note,
            'layout': lay if isinstance(lay, str) else 'ok'}
