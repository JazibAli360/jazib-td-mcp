"""splat_render builder: /project1/lab/BL_splat_render (TD 2025.31550) - Gaussian splat renderer.

Spec: docs/research/BL_gaussian_splats_pointclouds.md section 7.1 (our clean-room design). Run inside TD via td_exec:
    g = dict(globals()); exec(open('<repo>/builders/splat_render.py').read(), g); g['build']('/project1/lab')
build(parent_path, name, controls=True, step='all') is idempotent (ops reused by name). step: 'core' (no controls),
'all'. Network: Script CHOP (numpy decode of .ply/.splat/.spz) -> CHOP to POP (P, scale+id, rot, Color, sh r/g/b)
-> Sort POP by a sort camera (GPU radix; the camera only moves on a sort tick) -> Switch POP -> Geometry COMP instancing
one quad per splat -> GLSL MAT (splat_render.glsl: covariance projection, oriented quads, premultiplied over) ->
Render TOP 16F -> ONE compute GLSL pass (sort-free normalise, background, alpha/premult) -> out1. CPU sort mode: draw
order in a Script TOP the MAT reads (no data re-upload). Pure logic: builders/splat_render_logic.py; runtime:
builders/splat_render_rt.py (both copied into Text DATs). T-70 safe: own controls_window closed first, destroys only
through safe_destroy, the panel container is never destroyed (zkit updates it in place), the network pane is never
moved. No functions in storage (T-67). Never reads TOP pixels (T-74). Pure ASCII.
"""
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
NAME = 'BL_splat_render'
SPLAT_FX_POINTER = ('Splat effect modules (30, stackable, effectors): a PX_pointfx COMP (Render splats); point the '
                    'Effectors page Splatfx at yours (empty = off).')
SPLATFX_LABEL = 'Splat FX COMP (PX_pointfx; empty = off)'
DEFAULT_FILE = '/Applications/TouchDesigner 2.app/Contents/Resources/tfs/Samples/PointClouds/SmileyPinata.spz'

DATA_SCRIPT = '''# splat_data: numpy splat arrays -> one sample per splat (splat_rt.data_cook)
def onSetupParameters(scriptOp):
\treturn

def onPulse(par):
\treturn

def onCook(scriptOp):
\tscriptOp.parent().op('splat_rt').module.data_cook(scriptOp)
\treturn
'''

ORDER_SCRIPT = DATA_SCRIPT.replace('splat_data: numpy splat arrays -> one sample per splat (splat_rt.data_cook)',
                                   'order_tex: cpu draw order (splat_rt.order_cook)').replace('data_cook', 'order_cook')
INFO_SCRIPT = DATA_SCRIPT.replace('splat_data: numpy splat arrays -> one sample per splat (splat_rt.data_cook)',
                                  'info: splats drawn sort_ms fps_cook ok (splat_rt.info_cook)').replace('data_cook',
                                                                                                         'info_cook')

FRAME_EXEC = '''# frame_exec: orbit camera, sort gate, MAT uniforms, info (splat_rt.frame); one call per frame (T-21)
def onFrameStart(frame):
\tc = parent()
\ttry:
\t\tc.op('splat_rt').module.frame(c)
\texcept Exception as e:
\t\tc.par.Status.val = ('frame: %s: %s' % (type(e).__name__, e))[:200]
\treturn
'''

PAR_EXEC = '''# par_exec: load pars -> debounced reload; pulses Reload / Sortnow / Frame / Reset (splat_rt)
def onValueChange(par, prev):
\tparent().op('splat_rt').module.on_value(parent(), par)
\treturn

def onPulse(par):
\tparent().op('splat_rt').module.on_pulse(parent(), par)
\treturn
'''

POST_GLSL = '''// splat post: ONE compute pass (T-47). in0 = splat render (premultiplied, 16F), in1 = background (premultiplied)
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uM;    // sortfree normalise, use bg TOP, output alpha, premultiplied out
uniform vec4 uBg;   // background colour rgb + alpha (straight)
void main()
{
\tivec2 px = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (px.x >= res.x || px.y >= res.y) return;
\tivec2 isz = textureSize(sTD2DInputs[0], 0);
\tvec4 c;
\tif (isz == res) c = texelFetch(sTD2DInputs[0], px, 0);
\telse {  // Renderscale < full: bilinear upscale of the premultiplied render, edge held (T-204)
\t\tvec2 hx = 0.5 / vec2(isz);
\t\tc = texture(sTD2DInputs[0], clamp((vec2(px) + 0.5) / vec2(res), hx, 1.0 - hx));
\t}
\tif (uM.x > 0.5) {
\t\tfloat A = max(c.a, 0.0);
\t\tfloat al = 1.0 - exp(-A);
\t\tc = (A > 1e-6) ? vec4(c.rgb / A * al, al) : vec4(0.0);
\t}
\tif (uM.y > 0.5) {
\t\tvec2 uv = (vec2(px) + 0.5) / vec2(res);
\t\tvec4 b = texture(sTD2DInputs[1], uv);
\t\tc = c + b * (1.0 - c.a);
\t}
\tvec4 bg = vec4(uBg.rgb * uBg.a, uBg.a);
\tc = c + bg * (1.0 - c.a);
\tif (uM.z < 0.5) c.a = 1.0;
\telse if (uM.w < 0.5) c.rgb = c.rgb / max(c.a, 1e-6);
\tTDImageStoreOutput(0, ivec3(px, 0), TDOutputSwizzle(c));
}
'''

AUDIOMAP_ROWS = [['chan', 'target', 'gain'], ['low', 'scale', '0'], ['mid', 'opacity', '0'], ['high', 'noise', '0'],
                 ['level', 'orbit', '0']]

STAGES = [
    {'title': 'Controls', 'role': 'control',
     'ops': ['controls', 'controls_window', 'par_exec', 'frame_exec', 'splat_render_logic', 'splat_rt', 'audiomap'],
     'body': 'zkit panel (Camera, Splat, Sort, Look pages); pulse Opencontrols. frame_exec: orbit camera, sort gate, '
             'MAT uniforms. par_exec: debounced reload + pulses. splat_render_logic: pure maths/decoders (offline '
             'tested); splat_rt: TD runtime (numpy cache). audiomap: chan -> target (scale opacity explode noise '
             'orbit) x gain from Audiochop.'},
    {'title': '1 Load', 'role': 'input', 'ops': ['splat_data', 'to_pop', 'loaded'],
     'body': 'File (.ply INRIA / points, .splat, .spz v2/v3) decoded in numpy, thin / crop / cull / budget, then one '
             'sample per splat -> CHOP to POP attributes P, scale (+ stable id), rot, Color, shr/shg/shb.'},
    {'title': '2 Order', 'role': 'process', 'ops': ['sort_cam', 'sort', 'sel_order', 'final', 'order_tex'],
     'body': 'Sort POP (GPU radix) by sort_cam, which copies the render camera only on a sort tick (Sorteveryn / '
             'Sortmovedeg / Sortnow; Frozen = never). cpu: numpy uint16 radix order -> order_tex (the MAT looks the '
             'splat up). sortfree: no order (weighted sum in post).'},
    {'title': '3 Draw + render', 'role': 'process', 'ops': ['draw', 'splatmat', 'splat_glsl', 'cam', 'render'],
     'body': 'Geometry COMP: one quad per splat (instancing, custom attribs 0-6). GLSL MAT: 3D covariance -> 2D '
             '(Jacobian + low-pass), oriented 3-sigma quads cut at the alpha threshold, SH1, dissolve / noise / '
             'explode / reveal, premultiplied "over" (sort-free: add). Render TOP 16F, alpha real.'},
    {'title': '3b Geometry (Geo page)', 'role': 'process',
     'ops': ['geo_key', 'geo_render', 'geo_pass', 'geo_switch', 'splat_geo_adapter', 'geo_env_cam', 'geo_env_cube',
             'geo_env_equi', 'geo_env_idle', 'geo_env_gate', 'geo_env_hold', 'geo_env_pull', 'geo_env_light'],
     'body': 'W1-E (docs/builds/px_geo.md). Geoon: user Geometry COMPs (Geocomps) render first in geo_render (opaque, '
             'depth write, lit by Geolights + geo_key + geo_env_light), then geo_pass (Render Pass TOP) draws the '
             'splats over it, depth test on / write off; geo_switch picks render (off) or geo_pass (on). '
             'splat_geo_adapter = hooks text put in front of splat_glsl only while Geoon. geo_env_*: low-res cube '
             'of the splats for chrome objects (Geoenv).'},
    {'title': '4 Output', 'role': 'output', 'ops': ['bg_sel', 'bg_none', 'bg_switch', 'post', 'post_compute',
                                                    'post_sel', 'out1', 'info', 'out_info'],
     'body': 'post = ONE compute pass: Renderscale upscale, sort-free normalise, background TOP / colour, alpha on/off, '
             'premultiplied or straight; post_sel skips it when it would only copy (Full, no bg, alpha + premult). '
             'out1 = image only. out_info: splats, drawn, sort_ms, fps_cook, ok (+ sorts, load_ms).'},
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


def splatfx_par(c):
    """Effectors page `Splatfx`: an optional COMP par naming the PX_pointfx that carries the splat effect modules
    (29 Oct drop-in: it was a read-only note holding the lab PX path; now empty = off, and when set it is a
    real OP reference that evaluates to that COMP). An old Str note is replaced (its text was only the hint).
    -> what changed ([] when already right)."""
    ch = []
    p = getattr(c.par, 'Splatfx', None)
    if p is not None and p.style != 'COMP':
        p.destroy()                                    # a custom par, not an op (T-70 is about ops)
        p = None
        ch.append('Splatfx: note -> COMP par')
    if p is None:
        pg = _page(c, 'Effectors')
        p = pg.appendCOMP('Splatfx', label=SPLATFX_LABEL)[0]
        p.default = ''
        p.val = ''
        if not ch:
            ch.append('Splatfx: COMP par')
    if p.readOnly:
        p.readOnly = False
        ch.append('Splatfx: editable')
    if p.label != SPLATFX_LABEL:
        p.label = SPLATFX_LABEL
    return ch


def _comment_pointer(c):
    base = c.comment.split(' Splat effect modules')[0].rstrip()
    want = base + ' ' + SPLAT_FX_POINTER
    if c.comment != want:
        c.comment = want
        return ['comment']
    return []


def indep_upgrade(comp_path='/project1/lab/' + NAME):
    """Drop-in round (29 Oct) in place on an existing BL_splat_render: Splatfx becomes an optional COMP par, empty
    = off (it held the lab PX path), and the COMP comment names no path. Own controls window closed first
    (UI-safe); one par replaced, nothing else touched. Idempotent: a second run returns changed = []."""
    c = op(comp_path)
    if c is None:
        return {'state': 'skipped', 'why': 'no ' + comp_path}
    closed = _close_window(c)
    ch = splatfx_par(c) + _comment_pointer(c)
    return {'state': 'done', 'changed': ch, 'closed_window': closed, 'Splatfx': c.par.Splatfx.val,
            'errors': len([o for o in c.findChildren(maxDepth=1) if o.errors()])}


def _par(c, page, style, name, label, default=None, rng=None, menu=None, size=1):
    """Idempotent custom par (any style, multi-component too)."""
    if getattr(c.parGroup, name, None) is not None:
        g = getattr(c.parGroup, name)
        if g.label != label:
            g.label = label
        return g
    pg = _page(c, page)
    if style == 'Menu':
        g = pg.appendMenu(name, label=label)
        g[0].menuNames = [m[0] for m in menu]
        g[0].menuLabels = [m[1] for m in menu]
    elif style in ('Int', 'Float') and size > 1:
        g = getattr(pg, 'append' + style)(name, label=label, size=size)
    else:
        g = getattr(pg, 'append' + style)(name, label=label)
    pars = list(g)
    if rng is not None:
        for p in pars:
            p.normMin, p.normMax = rng
    if default is not None:
        vals = default if isinstance(default, (tuple, list)) else [default]
        for p, v in zip(pars, vals):
            p.default = v
            p.val = v
    return g


def _pars(c, L):
    S, CA, SP, SO, LO, AU, OU = 'Source', 'Camera', 'Splat', 'Sort', 'Look', 'Audio', 'Output'
    _par(c, S, 'File', 'File', 'Splat file', DEFAULT_FILE)
    _par(c, S, 'Menu', 'Format', 'Format', 'auto', menu=L.FORMATS)
    _par(c, S, 'Pulse', 'Reload', 'Reload')
    _par(c, S, 'Int', 'Maxsplats', 'Max splats (0 = all)', 0, (0, 2000000))
    _par(c, S, 'Int', 'Thinstep', 'Thin step', 1, (1, 16))
    _par(c, S, 'Float', 'Thinrandom', 'Thin random', 0.0, (0, 1))
    _par(c, S, 'Float', 'Opacitycull', 'Opacity cull', 0.0, (0, 0.2))
    _par(c, S, 'Menu', 'Shdegree', 'SH degree', '1', menu=L.SHDEGREE)
    _par(c, S, 'Menu', 'Coordfix', 'Coord fix', 'auto', menu=L.COORDFIX)
    _par(c, S, 'Float', 'Pointscale', 'Point-cloud splat size', 0.01, (0, 0.1))
    _par(c, S, 'XYZ', 'Cropcenter', 'Crop centre', (0.0, 0.0, 0.0), (-10, 10))
    _par(c, S, 'XYZ', 'Cropsize', 'Crop size (0 = off)', (0.0, 0.0, 0.0), (0, 20))
    _par(c, S, 'Float', 'Cropradius', 'Crop radius (0 = off)', 0.0, (0, 20))
    _par(c, S, 'Toggle', 'Autoframe', 'Frame camera on load', True)
    _par(c, S, 'Str', 'Status', 'Status', '')
    c.par.Status.readOnly = True
    _par(c, S, 'Pulse', 'Reset', 'Reset look/camera')

    _par(c, CA, 'Menu', 'Cammode', 'Camera', 'orbit', menu=L.CAMMODE)
    _par(c, CA, 'COMP', 'Camcomp', 'External camera')
    _par(c, CA, 'Float', 'Orbitaz', 'Azimuth', 0.0, (-180, 180))
    _par(c, CA, 'Float', 'Orbitel', 'Elevation', 10.0, (-89, 89))
    _par(c, CA, 'Float', 'Orbitdist', 'Distance', 3.0, (0.1, 20))
    _par(c, CA, 'XYZ', 'Target', 'Target', (0.0, 0.0, 0.0), (-5, 5))
    _par(c, CA, 'Float', 'Fov', 'FOV (vertical deg)', 45.0, (10, 120))
    _par(c, CA, 'Float', 'Autorbit', 'Orbit deg/s', 10.0, (-90, 90))
    _par(c, CA, 'Menu', 'Orbitsync', 'Orbit sync', 'none', menu=L.ORBITSYNC)
    _par(c, CA, 'Float', 'Bpm', 'BPM', 120.0, (60, 200))
    _par(c, CA, 'Float', 'Beatsperrev', 'Beats per rev', 32.0, (1, 128))
    _par(c, CA, 'Pulse', 'Frame', 'Frame splats')

    _par(c, SP, 'Float', 'Scalemult', 'Scale', 1.0, (0, 3))
    _par(c, SP, 'Float', 'Opacitygain', 'Opacity', 1.0, (0, 3))
    _par(c, SP, 'Float', 'Alphathreshold', 'Alpha thr', 0.015, (0, 0.2))
    _par(c, SP, 'Float', 'Lowpass', 'Low-pass px2', 0.3, (0, 2))
    _par(c, SP, 'Float', 'Brightness', 'Brightness', 1.0, (0, 3))
    _par(c, SP, 'Float', 'Gamma', 'Gamma', 1.0, (0.2, 3))
    _par(c, SP, 'Toggle', 'Srgbtolinear', 'sRGB to linear', False)
    _par(c, SP, 'Float', 'Pointmix', 'Point mix', 0.0, (0, 1))
    _par(c, SP, 'Float', 'Pointsize', 'Point px', 3.0, (0.5, 20))

    _par(c, SO, 'Menu', 'Sortmode', 'Sort mode', 'sortpop', menu=L.SORTMODE)
    _par(c, SO, 'Int', 'Sorteveryn', 'Every N frames (0 = off)', 0, (0, 60))
    _par(c, SO, 'Float', 'Sortmovedeg', 'Re-sort after deg', 1.0, (0, 20))
    _par(c, SO, 'Pulse', 'Sortnow', 'Sort now')

    _par(c, LO, 'Float', 'Dissolve', 'Dissolve', 0.0, (0, 1))
    _par(c, LO, 'Float', 'Dissolveseed', 'Dissolve seed', 0.0, (0, 100))
    _par(c, LO, 'Float', 'Noiseamp', 'Noise amp', 0.0, (0, 0.5))
    _par(c, LO, 'Float', 'Noisefreq', 'Noise freq', 2.0, (0, 20))
    _par(c, LO, 'Float', 'Noisespeed', 'Noise speed', 0.3, (0, 3))
    _par(c, LO, 'Float', 'Explode', 'Explode', 0.0, (-1, 3))
    _par(c, LO, 'Float', 'Reveal', 'Reveal', 1.0, (0, 1))
    _par(c, LO, 'Float', 'Beatpulse', 'Beat pulse', 0.0, (0, 1))

    _par(c, AU, 'CHOP', 'Audiochop', 'Audio CHOP')

    geo_pars(c, L)

    _par(c, OU, 'Int', 'Resolution', 'Resolution', (1080, 1920), (1, 4096), size=2)
    _par(c, OU, 'Menu', 'Renderscale', 'Render scale', 'full', menu=L.RENDERSCALE)
    _par(c, OU, 'TOP', 'Bgtop', 'Background TOP')
    _par(c, OU, 'RGBA', 'Bgcolor', 'Background colour', (0.0, 0.0, 0.0, 0.0))
    _par(c, OU, 'Toggle', 'Premult', 'Premultiplied out', True)
    _par(c, OU, 'Toggle', 'Outputalpha', 'Output alpha', True)


GEO_P = 'parent().par.'


def geo_pars(c, L):
    """Geo page (W1-E, docs/builds/px_geo.md). Reusable: PX's wave-2 owner calls geo_pars + geo_stage + geo_sync on
    its own COMP. L = splat_render_logic module (menus)."""
    GE = 'Geo'
    _par(c, GE, 'Toggle', 'Geoon', 'Geometry in the scene', False)
    _par(c, GE, 'Str', 'Geocomps', 'Geometry COMPs (paths / patterns)', '')
    _par(c, GE, 'Str', 'Geolights', 'Lights (paths, #tag; #light = all in /project1/effectors)', '#light')
    _par(c, GE, 'Toggle', 'Geokey', 'Built-in key light', True)
    _par(c, GE, 'Float', 'Georelight', 'Relight splats (light effectors)', 0.0, (0, 1))
    _par(c, GE, 'Float', 'Geoambient', 'Splat ambient (relight)', 0.25, (0, 2))
    _par(c, GE, 'Menu', 'Geolightmode', 'Splat light mode', 'halflambert', menu=L.LIGHTMODES)
    _par(c, GE, 'Float', 'Geodepthbias', 'Splat depth bias (world)', 0.0, (-0.5, 0.5))
    _par(c, GE, 'Toggle', 'Geoenv', 'Scene environment (chrome)', False)
    _par(c, GE, 'Str', 'Geoenvgeo', 'Environment captures (geometry)', 'draw')
    _par(c, GE, 'XYZ', 'Geoenvcentre', 'Environment centre (chrome object)', (0.0, 0.0, 0.0), (-10, 10))
    _par(c, GE, 'Int', 'Geoenvres', 'Environment cube px', 256, (16, 1024))
    _par(c, GE, 'Int', 'Geoenveveryn', 'Environment every N frames', 4, (1, 30))
    _par(c, GE, 'Float', 'Geoenvdimmer', 'Environment dimmer', 1.0, (0, 4))


def _try(o, name, value=None, expr=None, notes=None):
    """Set a par whose name is not confirmed on 31550 yet (LIVE CHECK G1): misses go to notes, never fail."""
    p = getattr(o.par, name, None)
    if p is None:
        if notes is not None:
            notes.append('%s.%s: no such par' % (o.name, name))
        return None
    try:
        if expr is not None:
            p.expr = expr
        else:
            p.val = value
    except Exception as e:  # noqa: BLE001
        if notes is not None:
            notes.append('%s.%s: %s' % (o.name, name, e))
    return p


def geo_stage(c, render, draw='draw', mat='splatmat', cam_expr=None, res_exprs=None, P=GEO_P, notes=None):
    """Geometry in the splat scene, built next to an existing splat Render TOP `render` (W1-E). Returns geo_switch:
    the caller wires it where `render` went. Off (Geoon 0) = geo_switch passes `render` through untouched and the
    MAT keeps depth test off; nothing new cooks. On: geo_render (Geocomps + lights) -> geo_pass (Render Pass TOP, draws
    `draw` over geo_render's colour + depth) -> geo_switch input 1. Par names of the Render Pass TOP are LIVE CHECK
    G1 (tried, misses in notes)."""
    notes = [] if notes is None else notes
    cam_expr = cam_expr or render.par.camera.expr or repr(render.par.camera.eval().path)
    if res_exprs is None:
        res_exprs = (render.par.resolutionw.expr or str(render.par.resolutionw.eval()),
                     render.par.resolutionh.expr or str(render.par.resolutionh.eval()))
    key = _mk(c, lightCOMP, 'geo_key')
    key.par.tx, key.par.ty, key.par.tz = 2.0, 3.0, 4.0
    key.par.shadowcasters = ''      # shadows off: the default '*' only made layout read a wire from every op (28 Oct)
    key.comment = 'Geo key light (Geokey): lights the Geocomps when no light effectors exist.'
    gr = _mk(c, renderTOP, 'geo_render')
    gr.par.camera.expr = cam_expr
    # every geo op draws nothing while Geoon is off (their viewers stay on, so they must be cheap when unused)
    gr.par.geometry.expr = ("parent().op('splat_render_logic').module.geo_geometry(%sGeocomps.eval(), '%s') "
                            "if %sGeoon.eval() else ''" % (P, draw, P))
    gr.par.lights.expr = "parent().op('splat_rt').module.geo_lights(parent())"
    gr.par.outputresolution = 'custom'
    gr.par.resolutionw.expr, gr.par.resolutionh.expr = res_exprs
    gr.par.format = 'rgba16float'
    gr.par.bgcolorr = gr.par.bgcolorg = gr.par.bgcolorb = 0
    gr.par.bgcolora = 0
    gr.par.antialias = render.par.antialias.eval()
    gr.comment = 'Geo: user Geometry COMPs first (opaque, depth write), lit by Light COMPs (Geolights / Geokey / env).'
    gp = _mk(c, renderpassTOP, 'geo_pass')
    _wire(gr, gp)
    gp.par.camera.expr = cam_expr
    gp.par.geometry.expr = "'%s' if %sGeoon.eval() else ''" % (draw, P)
    gp.par.lights = ''
    for nm in ('cleardepth', 'clearpreviousdepth', 'cleardepthbuffer'):       # keep geo_render's depth (LIVE G1)
        if _try(gp, nm, False) is not None:
            break
    else:
        notes.append('geo_pass: no clear-depth par found (LIVE CHECK G1)')
    for nm in ('clearcolor', 'clearpreviouscolor', 'clearcolorbuffer'):       # keep geo_render's colour
        if _try(gp, nm, False) is not None:
            break
    gp.comment = 'Geo: splats drawn over geo_render (Render Pass TOP: its colour + depth kept), depth test on / write off.'
    sw = _mk(c, switchTOP, 'geo_switch')
    _wire(render, sw, 0)
    _wire(gp, sw, 1)
    sw.par.index.expr = '1 if %sGeoon.eval() else 0' % P
    sw.comment = 'Geo off: render (unchanged BL path). Geo on: geo_pass.'
    m = c.op(mat)
    m.par.depthtest.expr = 'bool(%sGeoon.eval())' % P               # off = False, as before (BL identical)
    m.par.depthwriting = False
    return sw


def geo_env(c, P=GEO_P, notes=None):
    """Chrome option (GE3): scene cube from MX_prox_material's env_capture (one implementation, prox_mat.py)."""
    try:
        ns = dict(globals())
        exec(open(REPO + '/builders/prox_mat.py').read(), ns)
        return ns['env_capture'](c, 'geo_env', "%sGeoenvgeo.eval() if %sGeoon.eval() and %sGeoenv.eval() else ''"
                                 % (P, P, P),
                                 (P + 'Geoenvcentrex', P + 'Geoenvcentrey', P + 'Geoenvcentrez'),
                                 'max(16, int(%sGeoenvres))' % P, P + 'Geoenveveryn', P + 'Geoenvdimmer',
                                 lights='geo_key', use_cond='p.par.Geoon.eval() and p.par.Geoenv.eval()')
    except Exception as e:  # noqa: BLE001
        if notes is not None:
            notes.append('geo_env skipped: %s' % e)
        return None


def geo_sync(c):
    """Geo adapter text + uGeo block to match Geoon (splat_rt.geo_sync; par_exec calls it on a Geoon change)."""
    return c.op('splat_rt').module.geo_sync(c)


def splat_text_refresh(c, dat='splat_glsl'):
    """Re-read builders/splat_render.glsl into the splat DAT, keeping the effectors block in front (no re-attach) and
    the geo block (geo_sync re-adds it)."""
    L = c.op('splat_render_logic').module
    sg = c.op(dat)
    t = L.geo_strip(sg.text)
    body = open(REPO + '/builders/splat_render.glsl').read()
    b = t.find(L.EFF_MARK_B)
    head = ''
    if b >= 0:
        e = t.find('\n', b)
        head = t[:len(t) if e < 0 else e + 1]
    new = head + body
    if sg.text != new:
        sg.text = new
    return bool(head)


def geo_upgrade(comp_path='/project1/lab/' + NAME):
    """W1-E on an existing BL_splat_render (main / build TDs) without a full rebuild: refresh logic / rt / splat text,
    Geo page, adapter DAT, geo_stage + geo_env, post input, par_exec pars, geo_sync, stage boxes. No effectors
    re-attach, no panel (run geo_panel() in its own exec). Reloads the splat file (the rt module is new)."""
    c = op(comp_path)
    c.allowCooking = True
    lg = _mk(c, textDAT, 'splat_render_logic')
    lg.text = open(REPO + '/builders/splat_render_logic.py').read()
    L = lg.module
    rt = _mk(c, textDAT, 'splat_rt')
    rt.text = open(REPO + '/builders/splat_render_rt.py').read()
    geo_pars(c, L)
    ga = _mk(c, textDAT, 'splat_geo_adapter')
    ga.text = open(REPO + '/builders/glsl/splat_geo_adapter.glsl').read()
    had_eff = splat_text_refresh(c)
    notes = []
    sw = geo_stage(c, c.op('render'), notes=notes)
    geo_env(c, notes=notes)
    _wire(sw, c.op('post'), 0)
    pe = c.op('par_exec')
    names = pe.par.pars.eval().split()
    for n in L.GEO_PARS:
        if n not in names:
            names.append(n)
    pe.par.pars = ' '.join(names)
    warn = geo_sync(c)
    for o in c.children:
        if o.family in ('TOP', 'CHOP', 'POP'):
            o.viewer = True
    rt.module.load(c, force=True)
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, STAGES, True, arrange='mixed')
    except Exception as e:  # noqa: BLE001
        lay = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'eff_block': had_eff, 'notes': notes, 'warn': warn,
            'status': c.par.Status.eval(), 'layout': str(lay)[:200]}


def geo_panel(comp_path='/project1/lab/' + NAME):
    """zkit panel with the Geo page (own exec, >= 5 frames after geo_upgrade: T-76 / T-98)."""
    ns = dict(globals())
    exec(open(REPO + '/builders/zkit.py').read(), ns)
    return str(ns['build_controls'](comp_path, pages=['Camera', 'Splat', 'Sort', 'Look', 'Geo'], d=56, cols=6))[:300]


def _eff_hook(c):
    """Shared effectors adapter (builders/effectors.py attach, docs/builds/effectors.md): Effectors page + a few ops,
    idempotent, run after every build; a failure is reported, never a broken build."""
    try:
        ns = dict(globals())
        exec(open(REPO + '/builders/effectors.py').read(), ns)
        return ns['attach'](c.path)
    except Exception as e:
        return 'effectors adapter skipped: %s' % e


def build(parent_path='/project1/lab', name=NAME, controls=True):
    pc = op(parent_path)
    c = pc.op(name) or pc.create(baseCOMP, name)
    c.allowCooking = True
    _close_window(c)
    lg = _mk(c, textDAT, 'splat_render_logic')
    lg.text = open(REPO + '/builders/splat_render_logic.py').read()
    L = lg.module
    rt = _mk(c, textDAT, 'splat_rt')
    rt.text = open(REPO + '/builders/splat_render_rt.py').read()
    _pars(c, L)
    c.comment = ('BL_splat_render: Gaussian splats (.ply/.splat/.spz) -> sorted instanced quads -> GLSL MAT -> out1 '
                 '(premultiplied, Resolution). out_info CHOP. Pulse Opencontrols. ' + SPLAT_FX_POINTER)
    am = _mk(c, tableDAT, 'audiomap')
    if am.numRows < 2:
        am.clear()
        for r in AUDIOMAP_ROWS:
            am.appendRow(r)

    # 1 Load
    data = _mk(c, scriptCHOP, 'splat_data')
    data.par.callbacks = data.name + '_callbacks'
    cb = c.op(data.name + '_callbacks') or c.create(textDAT, data.name + '_callbacks')
    cb.text = DATA_SCRIPT
    data.par.callbacks = cb.name
    tp = _mk(c, choptoPOP, 'to_pop')
    tp.par.chop = data.name
    _attrs_from_chop(tp)
    loaded = _mk(c, nullPOP, 'loaded')
    _wire(tp, loaded)

    # 2 Order
    sc = _mk(c, nullCOMP, 'sort_cam')
    srt = _mk(c, sortPOP, 'sort')
    _wire(loaded, srt)
    srt.par.ptmethod = 'object'
    srt.par.pointobj = sc.name
    sel = _mk(c, switchPOP, 'sel_order')
    _wire(loaded, sel, 0)
    _wire(srt, sel, 1)
    sel.par.index.expr = "1 if parent().par.Sortmode.eval() in ('sortpop', 'frozen') else 0"
    srt.par.bypass.expr = "parent().par.Sortmode.eval() not in ('sortpop', 'frozen')"
    final = _mk(c, nullPOP, 'final')
    _wire(sel, final)
    ot = _mk(c, scriptTOP, 'order_tex')
    ocb = c.op('order_tex_callbacks') or c.create(textDAT, 'order_tex_callbacks')
    ocb.text = ORDER_SCRIPT
    ot.par.callbacks = ocb.name
    ot.par.format = 'r32float'
    ot.par.outputresolution = 'custom'
    ot.par.resolutionw = 4096
    ot.par.resolutionh.expr = "max(1, (int(op('splat_data').numSamples) + 4095) // 4096)"

    # 3 Draw + render
    sg = _mk(c, textDAT, 'splat_glsl')
    sg.text = open(REPO + '/builders/splat_render.glsl').read()
    ga = _mk(c, textDAT, 'splat_geo_adapter')
    ga.text = open(REPO + '/builders/glsl/splat_geo_adapter.glsl').read()
    sg.text = L.geo_patch(sg.text, ga.text, bool(c.par.Geoon.eval()))
    mat = _mk(c, glslMAT, 'splatmat')
    mat.par.vdat = sg.name
    mat.par.pdat = sg.name
    mat.seq.vec.numBlocks = max(int(mat.seq.vec.numBlocks), 7)
    for k, nm in enumerate(['uRes', 'uP1', 'uP2', 'uP3', 'uP4', 'uP5', 'uP6']):
        getattr(mat.par, 'vec{}name'.format(k)).val = nm
    mat.par.sampler0name = 'sOrder'
    mat.par.sampler0top = ot.name
    mat.par.sampler0filter = 'nearest'
    mat.par.blending = True
    mat.par.srcblend = 'one'
    mat.par.destblend.expr = "'one' if parent().par.Sortmode.eval() == 'sortfree' else 'omsa'"
    mat.par.srcblenda = 'one'
    mat.par.destblenda.expr = "'one' if parent().par.Sortmode.eval() == 'sortfree' else 'omsa'"
    mat.par.depthtest = False
    mat.par.depthwriting = False
    mat.par.postmultalpha = False
    geo = _mk(c, geometryCOMP, 'draw')
    _geo(geo, final, mat)
    cam = _mk(c, cameraCOMP, 'cam')
    _cam(cam)
    ren = _mk(c, renderTOP, 'render')
    ren.par.camera.expr = ("(parent().par.Camcomp.eval().path if parent().par.Cammode.eval() == 'external' and "
                           "parent().par.Camcomp.eval() is not None else 'cam')")
    ren.par.geometry = geo.name
    ren.par.lights = ''
    ren.par.outputresolution = 'custom'
    for k, ax in enumerate('wh'):  # Renderscale: post scales back to Resolution (perf wave 27 Oct)
        getattr(ren.par, 'resolution' + ax).expr = (
            "parent().op('splat_render_logic').module.render_size(parent().par.Resolution1, parent().par.Resolution2, "
            "parent().par.Renderscale.eval())[%d]" % k)
    ren.par.format = 'rgba16float'
    ren.par.bgcolorr = ren.par.bgcolorg = ren.par.bgcolorb = 0
    ren.par.bgcolora = 0
    ren.par.antialias = 'aa1x' if 'aa1x' in ren.par.antialias.menuNames else ren.par.antialias.menuNames[0]

    # 4 Output
    bgs = _mk(c, selectTOP, 'bg_sel')
    bgs.par.top.expr = "parent().par.Bgtop.eval().path if parent().par.Bgtop.eval() is not None else ''"
    bgn = _mk(c, constantTOP, 'bg_none')
    bgn.par.outputresolution = 'custom'
    bgn.par.resolutionw = 8
    bgn.par.resolutionh = 8
    bgn.par.colorr = bgn.par.colorg = bgn.par.colorb = 0
    bgn.par.alpha = 0
    bsw = _mk(c, switchTOP, 'bg_switch')
    _wire(bgn, bsw, 0)
    _wire(bgs, bsw, 1)
    bsw.par.index.expr = '1 if parent().par.Bgtop.eval() is not None else 0'
    post = _mk(c, glslTOP, 'post')
    pcd = _mk(c, textDAT, 'post_compute')
    pcd.text = POST_GLSL
    post.par.mode = 'compute'
    post.par.computedat = pcd.name
    post.par.outputresolution = 'custom'
    post.par.resolutionw.expr = 'parent().par.Resolution1'
    post.par.resolutionh.expr = 'parent().par.Resolution2'
    post.par.format = 'rgba16float'
    post.par.autodispatchsize = True
    post.seq.vec.numBlocks = max(int(post.seq.vec.numBlocks), 2)
    post.par.vec0name = 'uM'
    post.par.vec0valuex.expr = "1 if parent().par.Sortmode.eval() == 'sortfree' else 0"
    post.par.vec0valuey.expr = '1 if parent().par.Bgtop.eval() is not None else 0'
    post.par.vec0valuez.expr = '1 if parent().par.Outputalpha else 0'
    post.par.vec0valuew.expr = '1 if parent().par.Premult else 0'
    post.par.vec1name = 'uBg'
    for ax, ch in zip('xyzw', 'rgba'):
        getattr(post.par, 'vec1value' + ax).expr = 'parent().par.Bgcolor' + ch
    geo_notes = []
    gsw = geo_stage(c, ren, notes=geo_notes)
    geo_env(c, notes=geo_notes)
    _wire(gsw, post, 0)
    _wire(bsw, post, 1)
    psel = _mk(c, switchTOP, 'post_sel')  # post would only copy the render (defaults at Full): skip it
    _wire(post, psel, 0)
    _wire(gsw, psel, 1)
    psel.par.index.expr = ("1 if parent().op('splat_render_logic').module.post_identity(parent().par.Sortmode.eval(), "
                           "parent().par.Bgtop.eval() is not None, parent().par.Bgcolora.eval(), "
                           "parent().par.Outputalpha.eval(), parent().par.Premult.eval(), "
                           "parent().par.Renderscale.eval()) else 0")
    out = _mk(c, outTOP, 'out1')
    _wire(psel, out)
    info = _mk(c, scriptCHOP, 'info')
    icb = c.op('info_callbacks') or c.create(textDAT, 'info_callbacks')
    icb.text = INFO_SCRIPT
    info.par.callbacks = icb.name
    oi = _mk(c, outCHOP, 'out_info')
    _wire(info, oi)

    # Control
    fe = _mk(c, executeDAT, 'frame_exec')
    fe.text = FRAME_EXEC
    fe.par.framestart = True
    fe.par.active = True
    pe = _mk(c, parameterexecuteDAT, 'par_exec')
    pe.text = PAR_EXEC
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = ' '.join(list(rt.module.LOAD_PARS) + ['Reload', 'Sortnow', 'Frame', 'Reset', 'Sortmode'] +
                           list(L.GEO_PARS))
    pe.par.valuechange = True
    pe.par.onpulse = True
    pe.par.active = True

    rt.module.load(c, force=True)

    ui = 'skipped'
    if controls:
        ns = dict(globals())
        exec(open(REPO + '/builders/zkit.py').read(), ns)
        ui = ns['build_controls'](c.path, pages=['Camera', 'Splat', 'Sort', 'Look', 'Geo'], d=56, cols=6)

    c.par.opviewer.expr = "me.op('out1')"
    c.viewer = True
    for o in c.children:
        if o.family in ('TOP', 'CHOP', 'POP'):
            o.viewer = True
    lay = None
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, STAGES, True, arrange='mixed')
    except Exception as e:  # noqa: BLE001
        lay = 'layout failed: {}'.format(e)
    eff = _eff_hook(c)
    splatfx_par(c)                               # optional PX pointer (empty = off, drop-in)
    geo_sync(c)                                  # after the effectors block (the geo block goes behind it)
    return {'effectors': str(eff)[:300], 'geo_notes': geo_notes,
            'comp': c.path, 'ops': len(c.children), 'status': c.par.Status.eval(), 'ui': str(ui)[:200],
            'layout': str(lay)[:300]}


ATTRS = [('P', 'tx ty tz', 3), ('scale', 'sx sy sz sid', 4), ('rot', 'qw qx qy qz', 4), ('Color', 'r g b a', 4),
         ('shr', 'shr0 shr1 shr2', 3), ('shg', 'shg0 shg1 shg2', 3), ('shb', 'shb0 shb1 shb2', 3)]


def _attrs_from_chop(tp):
    """CHOP to POP attribute blocks (probed names on 31550: attr<i>chanscope/name/customname/type/numcomps)."""
    tp.seq.attr.numBlocks = len(ATTRS)
    for i, (nm, chans, ncomp) in enumerate(ATTRS):
        g = lambda s: getattr(tp.par, 'attr{}{}'.format(i, s))  # noqa: E731
        g('chanscope').val = chans
        names = g('name').menuNames  # 31550 tokens are lower case: p, color (labels P, Color)
        if nm.lower() in names:
            g('name').val = nm.lower()
        else:
            g('name').val = 'custom' if 'custom' in names else names[-1]
            g('customname').val = nm
        g('numcomps').val = ncomp if not g('numcomps').isMenu else str(ncomp)


def _geo(geo, final, mat):
    for ch in list(geo.children):
        if ch.name != 'quad':
            _sd(ch)
    q = geo.op('quad') or geo.create(rectanglePOP, 'quad')
    q.par.sizex = 2
    q.par.sizey = 2
    for nm in ('texture', 'normals'):
        if hasattr(q.par, nm):
            getattr(q.par, nm).val = False
    q.render = True
    q.display = True
    geo.par.instancing = True
    geo.par.instanceop = final.name  # Geometry COMP OP pars resolve from its parent (31550): '../x' = None
    geo.par.instancecountmode = 'oplength' if 'oplength' in geo.par.instancecountmode.menuNames else \
        geo.par.instancecountmode.menuNames[0]
    blocks = [('P', 3), ('scale', 4), ('rot', 4), ('Color', 4), ('shr', 3), ('shg', 3), ('shb', 3)]
    for i, (nm, n) in enumerate(blocks):
        for k, ax in enumerate('xyzw'):
            par = getattr(geo.par, 'instance{}custom{}'.format(i, ax), None)
            if par is not None:
                par.val = '{}({})'.format(nm, k) if k < n else ''
    geo.par.material = mat.name


def _cam(cam):
    cam.par.viewanglemethod = 'vertfov' if 'vertfov' in cam.par.viewanglemethod.menuNames else \
        cam.par.viewanglemethod.val
    cam.par.fov.expr = 'parent().par.Fov'
    cam.par.near = 0.01
    cam.par.far = 1000
    cam.par.rord = 'xyz'
