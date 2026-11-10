# depth_cam builder - DC_depth_cam: depth from the camera (Core ML Depth Anything V2 Small in the native arm64
# vision helper, kind 1) -> a depth TOP + depth effects (Depth view / Fog / Slice / Outline) behind a Mode par.
# Doc: docs/builds/depth_cam.md. Helper + protocol: helpers/vision_bridge/README.md. Client pattern = face_track's
# (non-blocking, one request in flight, newest frame wins, pass-through when the helper or model is missing).
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/depth_cam.py').read(), ns); ns['build']('/project1/lab')
# Idempotent: ops reused by name, texts/pars/wires re-set; custom par values kept; zkit panel refreshed in place.
# T-70 safe: nothing destroyed directly (_sd = safe_destroy); the COMP's controls_window is closed before a rebuild
# (zkit reopens it if it was open); the panel container is never destroyed; the network pane is never moved here.
# T-74 safe: the builder never reads pixels; the runtime reads `detect_bgra` with numpyArray(delayed=True) only,
# skipping the first frames after a start. No Python functions in op storage (T-67). ASCII only.
import os

NAME = 'DC_depth_cam'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = REPO + '/builders'
LOGIC_FILE = os.path.join(HERE, 'depth_cam_logic.py')
RUNTIME_FILE = os.path.join(HERE, 'depth_cam_runtime.py')
CLIENT_FILE = REPO + '/helpers/vision_bridge/lib/camera_bridge.py'
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
CLIP = REPO + '/media/webcam/webcam_ref_5s.mp4'
HELPER = REPO + '/helpers/vision_bridge/build/jzb_vision_bridge'
MODEL = REPO + '/helpers/vision_bridge/assets/DepthAnythingV2SmallF16.mlmodelc'

SHADER = """// DC_depth_cam fx: ONE pixel pass (T-46 safe). in0 = video, in1 = depth (R = nearness, 0 far .. 1 near, any size,
// sampled by uv). Havedepth 0 (no helper / no model / stale) = the video passes through untouched.
uniform vec4 uMode;     // mode (0 depth, 1 fog, 2 slice, 3 outline), mix, have depth, invert
uniform vec4 uFog;      // amount, start (farness), end (farness), -
uniform vec4 uFogCol;   // rgb, -
uniform vec4 uSlice;    // centre (nearness), width, soft edge, outside level (0 = transparent black, 1 = untouched)
uniform vec4 uLine;     // threshold (depth step), width px, lines only, -
uniform vec4 uLineCol;  // rgb, -
out vec4 fragColor;
float D(vec2 uv) {
    float d = texture(sTD2DInputs[1], uv).r;
    return uMode.w > 0.5 ? 1.0 - d : d;
}
void main() {
    vec2 uv = vUV.st;
    vec4 c = texture(sTD2DInputs[0], uv);
    if (uMode.z < 0.5) { fragColor = TDOutputSwizzle(c); return; }
    float d = D(uv);
    int m = int(uMode.x + 0.5);
    vec4 o = c;
    if (m == 0) {
        o = vec4(vec3(d), 1.0);
    } else if (m == 1) {
        float f = smoothstep(uFog.y, max(uFog.z, uFog.y + 1e-4), 1.0 - d) * clamp(uFog.x, 0.0, 1.0);
        o = vec4(mix(c.rgb, uFogCol.rgb * c.a, f), c.a);
    } else if (m == 2) {
        float hw = max(uSlice.y, 0.0) * 0.5;
        float k = 1.0 - smoothstep(hw, hw + max(uSlice.z, 1e-4), abs(d - uSlice.x));
        o = c * mix(clamp(uSlice.w, 0.0, 1.0), 1.0, k);   // premultiplied: rgb and alpha scale together
    } else {
        vec2 px = max(uLine.y, 0.5) * uTDOutputInfo.res.xy;
        float gx = D(uv + vec2(px.x, 0.0)) - D(uv - vec2(px.x, 0.0));
        float gy = D(uv + vec2(0.0, px.y)) - D(uv - vec2(0.0, px.y));
        float t = max(uLine.x, 1e-4);
        float e = smoothstep(t, t * 1.5, length(vec2(gx, gy)));
        vec4 base = uLine.z > 0.5 ? vec4(0.0) : c;
        o = vec4(mix(base.rgb, uLineCol.rgb, e), max(base.a, e));
    }
    fragColor = TDOutputSwizzle(mix(c, o, clamp(uMode.y, 0.0, 1.0)));
}
"""

FRAME_EXEC = '''# depth_cam: pump the vision helper at frame start, send the newest frame at frame end (runtime DAT)
def onFrameStart(frame):
\tparent().op('runtime').module.frame_start(parent())
\treturn

def onFrameEnd(frame):
\tparent().op('runtime').module.frame_end(parent())
\treturn
'''

PAR_EXEC = '''# depth_cam: Active off stops the helper at once (frame_start would too, one frame later)
def onValueChange(par, prev):
\tif par.name == 'Active' and not par.eval():
\t\tparent().op('runtime').module.stop(parent())
\treturn
'''

SCRIPT_TOP_CB = '''# depth_cam depth_field Script TOP: uploads the eased depth field from the runtime DAT
def onCook(scriptOp):
\tscriptOp.parent().op('runtime').module.cook_depth(scriptOp.parent(), scriptOp)
\treturn
'''

P = "parent().par.{}"
PANEL_PAGES = ['Depth', 'Fog', 'Slice', 'Outline']


def _pages():
    return [
        ('Depth', [
            ('Active', 'Toggle', False, {'label': 'Active (runs the helper)'}),
            ('Mode', 'Menu', 'depth', {'names': ['depth', 'fog', 'slice', 'outline'],
                                       'labels': ['Depth view', 'Fog', 'Slice', 'Outline']}),
            ('Mix', 'Float', 1.0, {'min': 0, 'max': 1}),
            ('Smooth', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Smoothing'}),
            ('Hold', 'Float', 1.0, {'min': 0.05, 'max': 5, 'label': 'Hold s (then pass-through)'}),
            ('Invert', 'Toggle', False, {'label': 'Invert depth'}),
            ('Mirror', 'Toggle', False, {'label': 'Mirror source'}),
        ]),
        ('Fog', [
            ('Fogamount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Fog amount'}),
            ('Fogstart', 'Float', 0.3, {'min': 0, 'max': 1, 'label': 'Fog start (far)'}),
            ('Fogend', 'Float', 0.9, {'min': 0, 'max': 1, 'label': 'Fog end (far)'}),
            ('Fogcolour', 'RGB', (0.06, 0.08, 0.14), {'label': 'Fog colour'}),
        ]),
        ('Slice', [
            ('Slicecenter', 'Float', 0.8, {'min': 0, 'max': 1, 'label': 'Slice centre (near)'}),
            ('Slicewidth', 'Float', 0.4, {'min': 0, 'max': 1, 'label': 'Slice width'}),
            ('Slicesoft', 'Float', 0.05, {'min': 0, 'max': 0.5, 'label': 'Slice soft edge'}),
            ('Slicespeed', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Sweep Hz (0 = still)'}),
            ('Sliceoutside', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Outside level'}),
        ]),
        ('Outline', [
            ('Linethresh', 'Float', 0.03, {'min': 0.002, 'max': 0.3, 'label': 'Edge threshold'}),
            ('Linewidth', 'Float', 2.0, {'min': 0.5, 'max': 12, 'label': 'Line width px'}),
            ('Lineonly', 'Toggle', False, {'label': 'Lines only'}),
            ('Linecolour', 'RGB', (1.0, 1.0, 1.0), {'label': 'Line colour'}),
        ]),
        ('Setup', [
            ('Source', 'Menu', 'clip', {'names': ['clip', 'input'], 'labels': ['Stored clip', 'In TOP (in_video)']}),
            ('Clipfile', 'File', CLIP, {'label': 'Clip file'}),
            ('Helper', 'File', HELPER, {'label': 'Vision helper binary'}),
            ('Model', 'Folder', MODEL, {'label': 'Depth model (.mlmodelc)'}),
            ('Fakedepth', 'Toggle', False, {'label': 'Fake depth (test without helper)'}),
        ]),
        ('Output', [
            ('Status', 'Str', 'off', {'label': 'Status', 'ro': True}),
            ('Latency', 'Float', 0.0, {'min': 0, 'max': 200, 'label': 'Round trip median (ms)', 'ro': True}),
            ('Rate', 'Float', 0.0, {'min': 0, 'max': 30, 'label': 'Depth maps per s', 'ro': True}),
            ('Havedepth', 'Int', 0, {'min': 0, 'max': 1, 'label': 'Have depth', 'ro': True}),
        ]),
    ]


def _pars(c, pages):
    for page_name, pars in pages:
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if getattr(c.par, name, None) is not None or (style == 'RGB' and getattr(c.par, name + 'r', None) is not None):
                continue
            label = o.get('label', name)
            if style == 'RGB':
                for p, v in zip(page.appendRGB(name, label=label), default):
                    p.default = v
                    p.val = v
                continue
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
            else:
                p = getattr(page, 'append' + style)(name, label=label)[0]
            if 'min' in o:
                p.normMin, p.normMax = o['min'], o['max']
            p.default = default
            p.val = default
            if o.get('ro'):
                p.readOnly = True


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


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _read(path):
    with open(path) as f:
        return f.read()


def build(parent_path='/project1/lab', panel=True):
    # fallible reads first, before touching the network (T-00b)
    logic, runtime, client = _read(LOGIC_FILE), _read(RUNTIME_FILE), _read(CLIENT_FILE)
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('DC_depth_cam: camera depth (Core ML Depth Anything V2 Small, native arm64 helper kind 1) -> '
                 'out_depth (nearness 0..1) + out_video (Mode: Depth view / Fog / Slice / Outline). Pass-through '
                 'without helper/model. Pulse Opencontrols.')
    _close_window(c)  # T-70: own window closed before any rebuild
    rt = c.op('runtime')
    if rt is not None:
        try:
            rt.module.stop(c)
        except Exception:
            pass
    _pars(c, _pages())

    # 1 Source
    inv = _mk(c, inTOP, 'in_video')
    clip = _mk(c, moviefileinTOP, 'clip')
    _expr(clip.par.file, P.format('Clipfile'))
    clip.par.playmode = 'sequential'
    clip.par.play = True
    sw = _mk(c, switchTOP, 'src_switch')
    _wire(inv, sw, 0)
    _wire(clip, sw, 1)
    _expr(sw.par.index, "1 if parent().par.Source.eval() == 'clip' else 0")
    fl = _mk(c, flipTOP, 'src_flip')
    _wire(sw, fl)
    _expr(fl.par.flipx, P.format('Mirror'))
    src = _mk(c, nullTOP, 'src')
    _wire(fl, src)

    # 2 Vision bridge: fixed 518x392 rgba8 (never resized at run time, T-74), R/B swapped on the GPU -> BGRA
    det = _mk(c, resolutionTOP, 'detect')
    _wire(src, det)
    det.par.outputresolution = 'custom'
    det.par.resolutionw, det.par.resolutionh = 518, 392
    det.par.format = 'rgba8fixed'
    bg = _mk(c, reorderTOP, 'detect_bgra')
    _wire(det, bg)
    for out_c, in_c in (('red', 'blue'), ('green', 'green'), ('blue', 'red'), ('alpha', 'alpha')):
        getattr(bg.par, 'output' + out_c).val = 'input1'
        getattr(bg.par, 'output' + out_c + 'chan').val = in_c
    bg.par.format = 'rgba8fixed'
    for n, text in (('depth_cam_logic', logic), ('runtime', runtime), ('vision_client', client)):
        d = _mk(c, textDAT, n)
        d.text = text
    info = _mk(c, tableDAT, 'info')
    oi = _mk(c, outDAT, 'out_info')
    _wire(info, oi)
    fx = _mk(c, executeDAT, 'frame_exec')
    fx.text = FRAME_EXEC
    fx.par.framestart = True
    fx.par.frameend = True
    fx.par.active = True
    pe = _mk(c, parameterexecuteDAT, 'par_exec')
    pe.text = PAR_EXEC
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Active'
    pe.par.valuechange = True
    pe.par.onpulse = False
    pe.par.active = True

    # 3 Depth map: Script TOP uploads the eased field (mono 32-bit float, 1 = near) -> out_depth
    df = _mk(c, scriptTOP, 'depth_field')
    cb = df.par.callbacks.eval()
    if cb is None:
        cb = _mk(c, textDAT, 'depth_field_callbacks')
        df.par.callbacks = cb.name
    cb.text = SCRIPT_TOP_CB
    df.par.format = 'mono32float'
    dn = _mk(c, nullTOP, 'depth')
    _wire(df, dn)
    od = _mk(c, outTOP, 'out_depth')
    _wire(dn, od)

    # 4 Effects: one pixel GLSL pass (T-46: single pass), shader in its docked pixel DAT
    g = _mk(c, glslTOP, 'fx')
    gl = c.op('fx_pixel')
    if gl is None:
        gl = _mk(c, textDAT, 'fx_pixel')
        gl.dock = g
    gl.text = SHADER
    g.par.pixeldat = gl
    g.par.outputresolution = 'useinput'
    g.par.format = 'rgba8fixed'
    _wire(src, g, 0)
    _wire(dn, g, 1)
    U = [('uMode', ['parent().par.Mode.menuIndex', P.format('Mix'), P.format('Havedepth'), P.format('Invert')]),
         ('uFog', [P.format('Fogamount'), P.format('Fogstart'), P.format('Fogend'), '0']),
         ('uFogCol', [P.format('Fogcolourr'), P.format('Fogcolourg'), P.format('Fogcolourb'), '1']),
         ('uSlice', ["op('depth_cam_logic').module.slice_center(absTime.seconds, parent().par.Slicecenter.eval(), "
                     "parent().par.Slicespeed.eval())", P.format('Slicewidth'), P.format('Slicesoft'),
                     P.format('Sliceoutside')]),
         ('uLine', [P.format('Linethresh'), P.format('Linewidth'), P.format('Lineonly'), '0']),
         ('uLineCol', [P.format('Linecolourr'), P.format('Linecolourg'), P.format('Linecolourb'), '1'])]
    g.seq.vec.numBlocks = max(len(U), int(g.seq.vec.numBlocks))
    for k, (un, ex) in enumerate(U):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for ax, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, ax)), e)
    ov = _mk(c, outTOP, 'out_video')
    _wire(g, ov)

    c.par.opviewer.expr = "me.op('out_video')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    for o in c.children:
        if o.family in ('TOP', 'CHOP') or o.OPType in ('tableDAT', 'outDAT'):
            o.viewer = True

    # Controls (zkit, rebuilt in place)
    info_ui = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info_ui = ns['build_controls'](c.path, pages=PANEL_PAGES, d=56, cols=8)

    stages = [
        {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'par_exec'],
         'body': 'zkit panel (Depth / Fog / Slice / Outline pages); pulse Opencontrols. par_exec: Active off stops the helper.'},
        {'title': '1 Source', 'role': 'input', 'ops': ['in_video', 'clip', 'src_switch', 'src_flip', 'src'],
         'body': 'Stored clip (default) or the In TOP; Mirror flips before depth.'},
        {'title': '2 Vision bridge', 'role': 'process',
         'ops': ['detect', 'detect_bgra', 'frame_exec', 'runtime', 'vision_client', 'depth_cam_logic', 'info',
                 'out_info'],
         'body': 'detect_bgra = 518x392 BGRA read back (delayed) and sent to the native arm64 helper (Core ML depth, kind 1); one request in flight, newest frame wins. Status in info.'},
        {'title': '3 Depth map', 'role': 'process', 'ops': ['depth_field', 'depth_field_callbacks', 'depth', 'out_depth'],
         'body': 'Script TOP uploads the eased field: mono 32-bit float, 0 far .. 1 near, model size 518x392.'},
        {'title': '4 Effects', 'role': 'output', 'ops': ['fx', 'fx_pixel', 'out_video'],
         'body': 'One GLSL pass: Depth view / Fog / Slice / Outline by Mode; Mix; no depth = video passes through.'},
    ]
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
    stages = [s_ for s_ in stages if s_['ops']]
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'panel': info_ui, 'layout': str(lay)[:400]}
