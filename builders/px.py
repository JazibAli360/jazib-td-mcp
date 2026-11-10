"""px builder: /project1/lab/PX_pointfx - modular point-cloud / splat FX system (TD 2025.31550). Clean-room.

Design + live checks: docs/builds/px.md. User rules: docs/builds/px_requirements.md. Catalog / maths:
docs/research/BR_rubenfro_pointcloud_fx.md section 4. Run inside TD through td_exec (two execs, >= 5 frames apart:
the zkit panel measures text in its own step, T-76/T-98):
    ns = dict(globals()); exec(open('<repo>/builders/px.py').read(), ns); ns['build']('/project1/lab')
    ns = dict(globals()); exec(open('<repo>/builders/px.py').read(), ns); ns['panel']('/project1/lab')
    ns['park']('/project1/lab')            # when the job is done (after saving): allowCooking off, own COMP only

Network (left to right): sources (files via the pointcloud / splat loaders -> rest_files (A|B) + rest_actor Script
TOPs, generators, depth camera DC_depth_cam out_depth/out_video, A->B morph, actor layer, ember pool) -> ONE compute
pass `source` (rest texture) -> ONE compute pass `update` (generated: enabled update modules in stack order, +
spring/damping/drag integration) -> ONE compute pass `look` (generated colour modules) -> sprites: Geometry COMP
instancing one quad per point + GLSL MAT (sprite shape, size by depth, DOF bokeh, streaks, cube / quad, add / alpha
blend) -> Render TOP (+ effector glow) | splats: sort_keys -> sorter/ (TOP to POP -> Sort POP, gated) -> sgeo + smat
(BL_splat_render's splat shader through px_splat_adapter.glsl) -> srender, + pool embers and glow as sprites -> layers
-> sw_render -> trail (compute) -> glow (1/8 res compute) -> grade (compute, + flare) -> out1.
Preview: a second render of a decimated cloud + the effector objects (boxes / spheres / planes as wire shapes, Nulls
and CHOP points as axes gizmos) -> out_preview. Output TOP carries the look only.
Module stack: table px_stack (uid type enabled label), one custom page per instance (M<uid>_<type>), values never
recompile; a stack change runs codegen once, compiles on probe TOPs, then swaps (px_rt.stack_changed/check_probe).
Idempotent: ops reused by name, texts/pars/wires re-set, custom par values + tables (stack, effectors, presets) kept.
T-70 safe: own controls_window closed first, destroys only via safe_destroy, the panel container is never destroyed,
the network pane is never moved. T-67: only plain data in storage. T-74/T-76: no TOP pixel reads. T-64: cookRate never
touched. T-46/T-47: every multi-pass stage is a compute GLSL TOP; GLSL TOPs get <= 3 wired inputs (T-84/T-88). ASCII.
"""
import os

NAME = 'PX_pointfx'
REPO = '~/Documents/StageLab_PrismFest/jazib-td-mcp'
HERE = os.path.join(REPO, 'builders')
GLSL = os.path.join(HERE, 'glsl')
LOGIC_FILE = os.path.join(HERE, 'px_logic.py')
RT_FILE = os.path.join(HERE, 'px_rt.py')
ZKIT_FILE = os.path.join(HERE, 'zkit.py')
PC_FILE = os.path.join(HERE, 'pointcloud_logic.py')
SPLAT_FILE = os.path.join(HERE, 'splat_render_logic.py')
MENU_FILE = os.path.join(HERE, 'menu_logic.py')        # live dropdowns (T-233), shared with effectors.py
SPLAT_GLSL = os.path.join(HERE, 'splat_render.glsl')       # BL_splat_render's shader, reused (S1), never copied
PALMAP_FILE = os.path.join(HERE, 'palette_map_logic.py')     # W1-B shared palette (read only here)
HAZE_FILE = os.path.join(HERE, 'px_haze_logic.py')           # W1-D haze + bloom v2 logic (read only here)
LINES_FILE = os.path.join(HERE, 'px_lines.py')               # W1-C lines pass builder (read only here)
CAMRIG_FILE = os.path.join(HERE, 'cam_rig_logic.py')          # camera rigs (lane E, read only here)
SPLAT_BUILDER = os.path.join(HERE, 'splat_render.py')        # W1-E geo_stage (read only here)
EFF_ROWS = '/project1/effectors/eff_rows'
# wave 2 (K37): PX reads the shared list; eff_none (empty list) while /project1/effectors is missing. The path is in
# the expression so effectors.refresh_consumers() re-sets it (T-159).
# Wave 4: only while PX uses the list (Constant CHOP eff_use, set by px_rt: a module's shared selection is on, or the
# stages read the shared grid); else eff_none, so the per-frame eff_rows cook is not re-uploaded to 4 GLSL TOPs (the
# "+0.75 ms CPU with everything off" of wave 2). No eff_use (older build) = always on.
EFF_ROWS_PUB = '/project1/effectors/eff_rows_pub'
# 29 Oct (drop-in): eff_use 2 = a module names a #pub row -> the full buffer eff_rows_pub (else eff_rows: #pub rows
# inert there, so PX holds no reference to another COMP's published points).
EFF_IN_EXPR = ("(lambda r, q, p, u: ((q.path if (q is not None and u is not None and u['use'] is not None and "
               "u['use'][0] > 1.5) else r.path) if (r is not None and (u is None or u['use'] is None or "
               "u['use'][0] > 0.5)) else p.op('eff_none').path))(op('%s'), op('%s'), me.parent(), "
               "me.parent().op('eff_use'))" % (EFF_ROWS, EFF_ROWS_PUB))
EFF_IN_OLD = ("(lambda r, p, u: '%s' if (r is not None and (u is None or u['use'] is None or u['use'][0] > 0.5)) "
              "else p.op('eff_none').path)(op('%s'), me.parent(), me.parent().op('eff_use'))" % (EFF_ROWS, EFF_ROWS))
LG = "op('px_logic').module"
PP = 'parent().par.'
PREVIEW_W = 'max(16, int(parent().par.Resx) // 2)'      # render_preview: half the render resolution (28 Oct)
PREVIEW_H = 'max(16, int(parent().par.Resy) // 2)'
VALUE_PARS = 'Geoon Echoes Soundon Resolution Resx Resy Cueindex'  # px_values (+ LOAD_PARS): px_rt.on_value
SIDE = "{}.side_from_pars({}Quality.eval(), {}Count.eval())".format(LG, PP, PP)
CONNECTED = ("any(len(cn.connections) for cn in parent().inputConnectors "
             "if cn.inOP is not None and cn.inOP.name == '{}')")

ROWS_CB = """# {name}: uniform rows '{key}' for the shaders, from px_rt.frame() (once per frame, cached)
def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tscriptOp.parent().op('px_rt').module.rows_cook(scriptOp, '{key}')
"""
REST_CB = """# {name}: rest image of source {key} (file mode), uploaded once per load (px_rt.rest_cook)
def onSetupParameters(scriptOp):
\treturn

def onCook(scriptOp):
\tscriptOp.parent().op('px_rt').module.rest_cook(scriptOp, '{key}')
"""
PULSES = """# px_pulses: every pulse on the COMP -> px_rt.on_pulse (stack edits, effectors, presets, triggers, reset)
def onPulse(par):
\top('px_rt').module.on_pulse(par)
"""
VALUES = """# px_values: source pars changed -> debounced reload (px_rt.on_value)
def onValueChange(par, prev):
\top('px_rt').module.on_value(par)
"""
STACK_WATCH = """# stack_watch: px_stack edited (by the Stack page, presets, MCP or by hand) -> codegen once (px_rt.stack_changed)
def onTableChange(dat):
\top('px_rt').module.stack_changed(parent())
"""
TICK = """# px_tick: engine tick at frame start (px_rt.tick): frame() once, before any cook, while the COMP is pulled (T-143)
def onFrameStart(frame):
\top('px_rt').module.tick(parent())
"""
DIRTY = """# px_dirty: a custom par changed (value or expression) -> patch the engine's cached value (px_rt.mark, T-143)
def onValueChange(par, prev):
\top('px_rt').module.mark(par)
"""
AUTOGUARD = """# px_autoguard: progress / drive of a module taken by the user (value, expression, export, mode) -> its auto
# progress goes Off (px_rt.auto_guard; echoes of PX's own writes ignored). Events only, never per frame (28 Oct).
def onValueChange(par, prev):
\top('px_rt').module.auto_guard(par)
def onExpressionChange(par, val, prev):
\top('px_rt').module.auto_guard(par)
def onExportChange(par, val, prev):
\top('px_rt').module.auto_guard(par)
def onModeChange(par, val, prev):
\top('px_rt').module.auto_guard(par)
"""
EFF_WATCH = """# eff_watch: an effector object moved / its Effector page changed -> engine re-reads effectors (px_rt.mark_eff)
def onValueChange(par, prev):
\top('px_rt').module.mark_eff(par)
"""
EFF_TAB_WATCH = """# eff_tab_watch: px_eff edited by hand -> engine re-reads its caches (px_rt.mark_all)
def onTableChange(dat):
\top('px_rt').module.mark_all(parent())
"""
DEPTH_PACK = """// depth_pack: ONE compute pass, rgb = video colour, a = depth nearness (DC_depth_cam out_depth .r), at depth size
layout (local_size_x = 8, local_size_y = 8) in;
void main()
{
\tivec2 g = ivec2(gl_GlobalInvocationID.xy);
\tivec2 res = ivec2(uTDOutputInfo.res.zw);
\tif (g.x >= res.x || g.y >= res.y) return;
\tvec2 uv = (vec2(g) + 0.5) / vec2(res);
\tTDImageStoreOutput(0, ivec3(g, 0), vec4(texture(sTD2DInputs[0], uv).rgb, texture(sTD2DInputs[1], uv).r));
}
"""

# ops other builders make inside PX (wave 2): splat_render.geo_stage, px_rt.add_geo, px_lines.build
EXTERNAL_OPS = ('geo_key', 'geo_render', 'geo_pass', 'geo', 'PX_lines', 'geo_env_cam', 'geo_env_cube', 'geo_env_equi',
                'geo_env_gate', 'geo_env_hold', 'geo_env_idle', 'geo_env_pull', 'geo_env_light')
NAMED_OPS = ('proj_render', 'proj_srender', 'pr_render', 'pr_srender')   # _proj makes them by name ('proj_' + nm)

# 'after' = reading order (user, 28 Oct: "reorganise nodes inside pointfx for cleaner readability and hierarchy"):
# Inputs / Engine -> Source -> State + update -> Sort | Look -> Render -> Lines -> Trails / glow / haze -> Post -> Out.
STAGES = [
    {'title': 'Controls', 'role': 'control',
     'ops': ['controls', 'controls_window', 'px_pulses', 'px_values', 'stack_watch', 'px_tick', 'px_dirty',
             'px_autoguard', 'eff_watch', 'eff_tab_watch', 'px_perf', 'px_auto'],
     'body': 'zkit panel (Opencontrols): core pages + one page per module. Pulses -> px_rt (stack, effectors, presets). '
             'px_tick / px_dirty / eff_watch / eff_tab_watch: the event-driven engine (T-143). px_perf (fps, frame ms; '
             'read only while Autoquality is on) -> px_auto (the auto-quality step the render expressions read).'},
    {'title': '0 Code + tables', 'role': 'process',
     'ops': ['px_logic', 'px_rt', 'pointcloud_logic', 'splat_logic', 'menu_logic', 'px_lib', 'px_modules', 'px_tmpl_update',
             'px_tmpl_colour', 'px_stack', 'px_eff', 'px_presets', 'px_setlist', 'px_notes', 'px_palette', 'px_palmap', 'px_hazelogic', 'cam_rig',
             'px_gridsec',
             'splat_geo_adapter'],
     'body': 'px_logic (schema + codegen), px_rt (runtime), loaders, GLSL library/modules/templates. px_stack = module '
             'stack (edit = one recompile), px_eff = effector objects, px_presets = whole looks.'},
    {'title': '1 Inputs', 'role': 'input',
     'ops': ['in_depth', 'in_video', 'in_mask', 'in_ctl', 'in_eff', 'depth_default', 'video_default', 'depth_src',
             'video_src', 'in_depth_pack', 'depth_pack_compute', 'mask_default', 'mask_src', 'grid_in', 'aux_src',
             'in_xyz', 'points_default', 'pts_sel', 'src_aux', 'atlas_default', 'atlas_src',
             'img_file', 'sound'],
     'body': 'in_depth/in_video (DC_depth_cam out_depth + out_video), in_mask (body / image mask), in_ctl (audio CHOP: '
             'low mid high level s0..s15), in_eff (CHOP effectors <name>tx ty tz sx). All optional.'},
    {'title': '2 Engine (CPU, per frame)', 'role': 'process',
     'ops': ['eng_g', 'eng_gs', 'eng_e', 'eng_m', 'eng_r', 'eng_q', 'eng_src', 'eng_cam', 'eng_pts', 'eng_ptsv',
             'eng_trail', 'eng_glow', 'eng_s', 'eng_sp', 'eng_info', 'eng_ez', 'out_info', 'eng_pal', 'eng_palc',
             'eng_h', 'eng_hl', 'eff_none', 'eff_use', 'eff_in'],
     'body': 'Script CHOPs: uniform rows / texture buffers from px_rt.frame() (pars, drives, effector matrices + motion '
             'paths, point sets, trails, glow, splat uniforms, clock). eng_g cooks every frame; the others only when '
             'their rows change (Frame bumped by the engine). No pixel reads.'},
    {'title': '3 Source (GPU)', 'role': 'process',
     'after': ['1 Inputs', '2 Engine (CPU, per frame)'],
     'ops': ['rest_files', 'rest_actor', 'source', 'source_compute'],
     'body': 'rest_files: A|B file rest images, rest_actor: actor file / sequence frame (uploaded on load / frame '
             'change). source: ONE compute pass, generators / depth / morph A->B, actor layer, pool -> rest texture.'},
    {'title': '4 State + update (GPU, generated)', 'role': 'feedback',
     'after': ['3 Source (GPU)'],
     'ops': ['state_init', 'state_fb', 'state_src', 'update', 'update_compute', 'update_inplace', 'update_probe',
             'update_next'],
     'body': 'state_fb = last frame of state (Statemode feedback), state_init = zeros (first frame / in place). '
             'update: ONE compute pass, text generated from the enabled update modules (stack order). update_probe: '
             '8x8 compile check of a new stack before it goes live (old shader kept on error).'},
    {'title': '5 Sort (splat order)', 'role': 'process',
     'after': ['4 State + update (GPU, generated)'],
     'ops': ['sort_keys', 'sortkey_compute', 'sorter'],
     'body': 'sort_keys (depth keys) -> sorter (TOP to POP -> Sort POP), un-parked only on sort frames (camera / '
             'motion gate, Sorteveryn): the last sorted order keeps feeding the splats.'},
    {'title': '6 Look / colour (GPU, generated)', 'role': 'process',
     'after': ['4 State + update (GPU, generated)'],
     'ops': ['look', 'colour_compute', 'colour_probe', 'colour_next', 'hot_pts', 'hot_compute'],
     'body': 'look: ONE compute pass, text generated from the enabled colour modules (stack order) + palette. '
             'colour_probe: compile check of a new stack.'},
    {'title': '7a Render: sprites + glow', 'role': 'process',
     'after': ['5 Sort (splat order)', '6 Look / colour (GPU, generated)'],
     'ops': ['pgeo', 'pmat', 'pmat_vertex', 'pmat_pixel', 'glowgeo', 'glowmat', 'glow_glsl', 'pcam', 'render',
             'proj_render', 'pr_render'],
     'body': 'Instanced quads, GLSL MAT reads state/look/rest textures (sprite, size by depth, DOF, streaks, cube / '
             'quad). glow: effector glow gaussians (reused splat shader), additive. Resx x Resy.'},
    {'title': '7b Render: splats (S1-S6)', 'role': 'process',
     'after': ['5 Sort (splat order)', '6 Look / colour (GPU, generated)'],
     'ops': ['sgeo', 'smat', 'smat_glsl', 'srender', 'proj_srender', 'pr_srender', 'layers', 'layers_compute',
             'sw_render'],
     'body': 'sgeo instancing of the sorted POP + smat (BL_splat_render shader + PX adapter: covariance, stretch, DOF) '
             '-> srender; layers adds the pool embers + glow; sw_render picks sprites or splats. Resx x Resy.'},
    {'title': '7c Render: geometry (Geo page)', 'role': 'process',
     'after': ['5 Sort (splat order)', '6 Look / colour (GPU, generated)'],
     'ops': ['geo', 'geo_key', 'geo_render', 'geo_pass', 'geo_spass', 'geo_out', 'lines_depth', 'geo_env_cam',
             'geo_env_cube', 'geo_env_equi', 'geo_env_gate', 'geo_env_hold', 'geo_env_idle', 'geo_env_pull',
             'geo_env_light'],
     'body': 'Geocomps (+ Geoadd objects in geo/) render first, lit by the light effectors; splats / sprites drawn over '
             'their colour + depth (Render Pass TOPs, depth test on): occlusion both ways (W1-E recipe).'},
    {'title': '8a Lines (Lines page)', 'role': 'process', 'ops': ['PX_lines', 'sw_lines'],
     'after': ['7a Render: sprites + glow', '7b Render: splats (S1-S6)', '7c Render: geometry (Geo page)'],
     'body': 'PX_lines inside PX: rings / contour / trails / connect / polyline / edges from the PX state, pcam; '
             'composite over sw_render before trail + bloom (so the HDR lines glow). Its Resx / Resy follow PX.'},
    {'title': '8b Trails + glow + haze', 'role': 'feedback',
     'after': ['8a Lines (Lines page)'],
     'ops': ['trail_blank', 'trail_fb', 'trail', 'trail_compute', 'sw_trail', 'glow_in', 'glow_q', 'glow_t', 'bloom',
             'glow_compute', 'bloom_off', 'sw_bloom', 'haze_src', 'haze_depth', 'haze_dsw', 'haze', 'haze_compute',
             'haze_off', 'sw_haze'],
     'body': 'Trails (compute, trail_fb = last frame, only with Trails on), glow (1/8 res + ONE 7x7 compute), haze '
             '(half / quarter of Resx x Resy). Each one is switched out (4x4 constant) while off.'},
    {'title': '8c Post (grade)', 'role': 'process', 'ops': ['post', 'post_compute'],
     'after': ['8b Trails + glow + haze'],
     'body': 'ONE compute: exposure, split tone, tone map, glow + haze add, vignette, grain. Resx x Resy.'},
    {'title': '9 Out', 'role': 'output', 'ops': ['out1', 'out_state'],
     'after': ['8c Post (grade)'],
     'body': 'out1 = the look, premultiplied RGBA 16F at Resx x Resy (Resolution menu, Look page). out_state = the '
             'point state (for PX_lines / other COMPs).'},
    {'title': '10 Preview + gizmos (not in out1)', 'role': 'output',
     'after': ['8c Post (grade)'],
     'ops': ['effectors', 'gizmos', 'pgeo_prev', 'pmat_prev', 'pv_cam', 'render_preview', 'out_preview'],
     'body': 'effectors: the effector objects (move / rotate / scale them). Preview = decimated cloud + wire shapes + '
             'axes gizmos, wider camera, half of Resx x Resy. Not part of out1.'},
]

SETLIST_NOTE = ('Setlist (28 Oct): preset names in show order, one per row (column name). Empty = the presets order. '
                'Next / Prev / Go on the Presets page; a name that is not a preset reads (missing) and is skipped.')

DEFAULT_STACK = [('prox_push', {'strength': 0.4}), ('curl', {'strength': 0.6}), ('prox_colour', {'emission': 3.0}),
                 ('dissolve_noise', {'progress': 0.0})]
DEFAULT_EFFECTORS = [('box', 'E1', {'tx': 0.8, 'sx': 0.6, 'sy': 0.6, 'sz': 0.6}), ('null', 'E2', {'tx': -0.8, 'ty': 0.3})]


def _read(path):
    with open(path) as fh:
        return fh.read()


def _logic():
    ns = {}
    exec(_read(LOGIC_FILE), ns)
    return ns


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


def _mk(c, cls, name, viewer=True):
    o = c.op(name)
    if o is not None and o.OPType == cls.__name__:
        return o
    if o is not None:
        _sd(o)
    o = c.create(cls, name)
    o.viewer = viewer
    return o


def _expr(par, e):
    par.expr = e
    par.mode = ParMode.EXPRESSION


def _wire(src, dst, i=0):
    if len(dst.inputs) > i and dst.inputs[i] is src:
        return
    dst.inputConnectors[i].connect(src)


def _text(c, name, text, dock=None, comment=''):
    d = _mk(c, textDAT, name)
    if d.text != text:
        d.text = text
    if dock is not None and d.dock is not dock:
        d.dock = dock
    if comment:
        d.comment = comment
    return d


def _table(c, name, header, comment=''):
    t = _mk(c, tableDAT, name)
    if t.numRows == 0 or [x.val for x in t.row(0)] != header:
        if t.numRows <= 1:
            t.clear()
            t.appendRow(header)
    if comment:
        t.comment = comment
    return t


_PARS_SKIP = set()                                # usecam_upgrade: the phase C Perf pars wait for phaseC_upgrade


def _pars(c, pages):
    msrc = None
    for page_name, pars in pages:
        if all(n in _PARS_SKIP for n, _s, _d, _o in pars):
            continue
        page = next((pg for pg in c.customPages if pg.name == page_name), None) or c.appendCustomPage(page_name)
        for name, style, default, o in pars:
            if name in _PARS_SKIP:
                continue
            probe = name + ('x' if style == 'XYZ' else ('r' if style == 'RGB' else ''))
            if getattr(c.par, probe, None) is not None:
                continue
            label = o.get('label', name)
            if style == 'Menu':
                p = page.appendMenu(name, label=label)[0]
                p.menuNames, p.menuLabels = o['names'], o['labels']
                p.default = default
                p.val = default
            elif style in ('Float', 'Int'):
                p = (page.appendFloat if style == 'Float' else page.appendInt)(name, label=label)[0]
                p.normMin, p.normMax = o['min'], o['max']             # slider range only: no clamps (no limits)
                p.default = default
                p.val = default
            elif style == 'Toggle':
                p = page.appendToggle(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'Pulse':
                page.appendPulse(name, label=label)
            elif style == 'Str' and o.get('menu'):     # live dropdown, free text kept (T-233)
                p = page.appendStrMenu(name, label=label)[0]
                msrc = msrc or _logic()['menu_source']
                p.menuSource = msrc(name)
                p.default = default
                p.val = default
            elif style == 'Str':
                p = page.appendStr(name, label=label)[0]
                p.default = default
                p.val = default
                if o.get('readonly'):
                    p.readOnly = True
            elif style in ('File', 'Folder'):
                p = (page.appendFile if style == 'File' else page.appendFolder)(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'CHOP':
                p = page.appendCHOP(name, label=label)[0]
            elif style in ('COMP', 'DAT'):                # 28 Oct phase A: Audiosrc, Setlist
                p = (page.appendCOMP if style == 'COMP' else page.appendDAT)(name, label=label)[0]
                p.default = default
                p.val = default
            elif style == 'TOP':
                p = page.appendTOP(name, label=label)[0]
            elif style in ('XYZ', 'RGB'):
                ps = page.appendRGB(name, label=label) if style == 'RGB' else page.appendXYZ(name, label=label)
                for p, v in zip(ps, default):
                    if style == 'XYZ':
                        p.normMin, p.normMax = o['min'], o['max']
                    p.default = v
                    p.val = v


TBUF = [('uPts', 'eng_pts', 'texturebuffer'), ('uPtsV', 'eng_ptsv', 'texturebuffer'),
        ('uTrail', 'eng_trail', 'texturebuffer')]
STAGE_ARRAYS = [('uG', 'eng_g'), ('uE', 'eng_e'), ('uM', 'eng_m')] + TBUF + [('uEffRows', 'eff_in', 'texturebuffer')]
# T-165: a parked COMP's Script CHOP has no channels until it cooks: guarded reads (0 until then), no error badge
_CH0 = "(lambda ch: 0.0 if ch is None else float(ch[0]))(op('{}')['{}'])"
PAL_CTL = [_CH0.format('eng_palc', k) for k in 'xyzw']
SRC_ARRAYS = [('uG', 'eng_gs'), ('uE', 'eng_ez'), ('uSrc', 'eng_src')] + [(n, 'eng_ez', t) for n, _ch, t in TBUF]
# T-143: glowgeo only while an effector glows (an empty glow draw still cost ~0.4 ms CPU + 0.35 ms GPU per frame)
RENDER_GEO = "'pgeo glowgeo' if op('eng_info')['glows'] > 0 else 'pgeo'"
# T-143: splats with no ember pool and no glow skip the sprite render + layers composite (~1.3 ms) entirely
SW_RENDER = ("0 if not int(op('eng_info')['splat']) else (2 if int(op('eng_info')['drawn']) == 0 "
             "and int(op('eng_info')['glows']) == 0 else 1)")
ENG_KEYS = (('eng_g', 'g'), ('eng_e', 'e'), ('eng_m', 'm'), ('eng_r', 'r'), ('eng_q', 'q'), ('eng_src', 'src'),
            ('eng_cam', 'cam'), ('eng_pts', 'pts'), ('eng_ptsv', 'ptsv'), ('eng_trail', 'trail'), ('eng_glow', 'glow'),
            ('eng_s', 's'), ('eng_sp', 'sp'), ('eng_info', 'info'), ('eng_gs', 'gs'), ('eng_ez', 'ez'),
            ('eng_pal', 'pal'), ('eng_palc', 'palc'), ('eng_h', 'h'), ('eng_hl', 'hl'))
ENG_W2 = (('eng_pal', 'pal', 'uPal[16]: shared palette stops r g b pos (Palette page, W1-B).'),
          ('eng_palc', 'palc', 'uPalCtl: count, shift (drive), mode, interp.'),
          ('eng_h', 'h', 'uH[13]: volumetric haze rows (Haze page + camera, W1-D).'),
          ('eng_hl', 'hl', 'uHL[40]: haze light rows from the light effectors (/project1/effectors).'))


def _arrays(o, specs):
    """GLSL TOP / MAT arrays from CHOPs: specs = [(name, chop[, arraytype])] (vec4; uniform array by default,
    'texturebuffer' = samplerBuffer, T-110: the point sets / trails, more samples than a uniform array holds)."""
    o.seq.array.numBlocks = max(int(o.seq.array.numBlocks), len(specs))
    for k, sp in enumerate(specs):
        nm, ch = sp[0], sp[1]
        getattr(o.par, 'array%dname' % k).val = nm
        getattr(o.par, 'array%dtype' % k).val = 'vec4'
        getattr(o.par, 'array%dchop' % k).val = ch
        getattr(o.par, 'array%darraytype' % k).val = sp[2] if len(sp) > 2 else 'uniformarray'


def _compute(c, name, dat_name, code, w_expr, h_expr, fmt, comment, viewer=True):
    g = _mk(c, glslTOP, name, viewer)
    g.par.mode = 'compute'
    _text(c, dat_name, code, dock=g)
    g.par.computedat = dat_name
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w_expr)
    _expr(g.par.resolutionh, h_expr)
    g.par.format = fmt
    g.par.autodispatchsize = True
    g.par.inputfiltertype = 'nearest'
    g.comment = comment
    for dn in ('_info', '_pixel', '_compute'):         # GLSL TOP docks its own DATs; ours is the compute DAT
        d = c.op(name + dn)
        if d is not None and d.name != dat_name:
            _sd(d)
    return g


def _script_chop(c, name, key, comment, clock=False):
    s = _mk(c, scriptCHOP, name)
    want = name + '_callbacks'
    cb = c.op(want) or _mk(c, textDAT, want)
    cb.text = ROWS_CB.format(name=name, key=key)
    cb.dock = s
    s.par.callbacks = want
    s.comment = comment
    # A Script CHOP only cooks when something makes it dirty: the GLSL TOPs reading it as a uniform array do not, so
    # without this the engine rows froze (eng_g 8 cooks while update cooked 651 times, live 31550). A Frame par bound
    # to absTime.frame makes it cook once per frame while pulled (particles pattern). T-143: only the clock CHOP
    # (eng_g) does; the others keep a CONSTANT Frame that px_rt._push bumps when their rows change.
    if getattr(s.par, 'Frame', None) is None:
        pg = next((p for p in s.customPages if p.name == 'Clock'), None) or s.appendCustomPage('Clock')
        pg.appendFloat('Frame', label='Frame (clock)')
    if clock:
        _expr(s.par.Frame, 'absTime.frame')
    else:
        s.par.Frame.mode = ParMode.CONSTANT
    return s


def _constant(c, name, w, h, fmt, rgba, comment):
    k = _mk(c, constantTOP, name)
    k.par.outputresolution = 'custom'
    _expr(k.par.resolutionw, str(w))
    _expr(k.par.resolutionh, str(h))
    k.par.format = fmt
    k.par.colorr, k.par.colorg, k.par.colorb, k.par.alpha = rgba
    k.comment = comment
    return k


def _switch(c, name, a, b, cond, comment):
    s = _mk(c, switchTOP, name)
    _wire(a, s, 0)
    _wire(b, s, 1)
    _expr(s.par.index, '1 if {} else 0'.format(cond))
    s.comment = comment
    return s


def _samplers(m, sampler_tops):
    m.seq.sampler.numBlocks = max(int(m.seq.sampler.numBlocks), len(sampler_tops))
    for k, (nm, top) in enumerate(sampler_tops):
        getattr(m.par, 'sampler%dname' % k).val = nm
        getattr(m.par, 'sampler%dtop' % k).val = top
        getattr(m.par, 'sampler%dfilter' % k).val = 'nearest'


def _mat(c, name, sampler_tops, stride_expr, all_ids=False):
    m = _mk(c, glslMAT, name)
    m.par.vdat = 'pmat_vertex'
    m.par.pdat = 'pmat_pixel'
    for dn in ('_vertex', '_pixel', '_info'):
        d = c.op(name + dn)
        if d is not None and d.name not in ('pmat_vertex', 'pmat_pixel'):
            _sd(d)
    _arrays(m, [('uR', 'eng_r')])
    _samplers(m, sampler_tops)
    m.seq.vec.numBlocks = max(int(m.seq.vec.numBlocks), 1)
    m.par.vec0name = 'uPv'
    _expr(m.par.vec0valuex, stride_expr)
    m.par.vec0valuey = 1 if all_ids else 0
    m.par.blending = True
    m.par.srcblend = 'one'
    _expr(m.par.destblend, "'one' if {}Blend.eval() == 'add' else 'omsa'".format(PP))
    m.par.postmultalpha = False                  # shader outputs premultiplied colour
    m.par.depthtest = False
    m.par.depthwriting = False
    return m


def _geo(c, name, mat, count_expr):
    geo = _mk(c, geometryCOMP, name)
    for ch in list(geo.children):
        if ch.name != 'quad':
            _sd(ch)
    q = geo.op('quad') or geo.create(rectangleSOP, 'quad')
    q.par.orient = 'xy'
    q.par.sizex, q.par.sizey = 1, 1
    q.par.normals = False
    q.render = True
    q.display = True
    geo.par.instancing = True
    geo.par.instancecountmode = 'manual'
    _expr(geo.par.numinstances, count_expr)
    geo.par.material = mat                        # sibling name (T-81)
    return geo


def _splat_geo(c, name, mat, instance_op=None, count_expr=None):
    """BL_splat_render's draw: one 2x2 Rectangle POP quad per instance (the shader's TDPos corners are -1..1).
    instance_op = the sorted POP (custom attribute 0 = pid); else a manual count (glow rows)."""
    geo = _mk(c, geometryCOMP, name)
    for ch in list(geo.children):
        if ch.name != 'quad':
            _sd(ch)
    q = geo.op('quad') or geo.create(rectanglePOP, 'quad')
    q.par.sizex, q.par.sizey = 2, 2
    for nm in ('texture', 'normals'):
        if hasattr(q.par, nm):
            getattr(q.par, nm).val = False
    q.render = True
    q.display = True
    geo.par.instancing = True
    if instance_op:
        geo.par.instanceop = instance_op           # resolves from geo's parent (T-81): 'sorter/sorted'
        geo.par.instancecountmode = 'oplength' if 'oplength' in geo.par.instancecountmode.menuNames else \
            geo.par.instancecountmode.menuNames[0]
        geo.par.instance0customx = 'pid(0)'        # LIVE CHECK P8: custom 1-comp POP attribute token
    else:
        geo.par.instancecountmode = 'manual'
        _expr(geo.par.numinstances, count_expr)
    geo.par.material = mat
    return geo


def _splat_mat(c, name, dat, vec_exprs, arrays, samplers, add_blend_expr):
    """GLSL MAT over the reused splat shader text (dat = adapter + splat_render.glsl, vertex + pixel in one DAT, as
    BL_splat_render). vec_exprs = 7 x 4 expressions for uRes, uP1..uP6 (BL's own uniforms)."""
    m = _mk(c, glslMAT, name)
    m.par.vdat = dat
    m.par.pdat = dat
    for dn in ('_vertex', '_pixel', '_info'):
        d = c.op(name + dn)
        if d is not None and d.name != dat:
            _sd(d)
    m.seq.vec.numBlocks = max(int(m.seq.vec.numBlocks), 7)
    for k, nm in enumerate(['uRes', 'uP1', 'uP2', 'uP3', 'uP4', 'uP5', 'uP6']):
        getattr(m.par, 'vec%dname' % k).val = nm
        for ax, e in zip('xyzw', vec_exprs[k]):
            _expr(getattr(m.par, 'vec%dvalue%s' % (k, ax)), str(e))
    _arrays(m, arrays)
    _samplers(m, samplers)
    m.par.blending = True
    m.par.srcblend = 'one'
    _expr(m.par.destblend, add_blend_expr)
    m.par.srcblenda = 'one'
    _expr(m.par.destblenda, add_blend_expr)
    m.par.depthtest = False
    m.par.depthwriting = False
    m.par.postmultalpha = False
    return m


def _sorter(c, keys, name):
    """S1 sort (the BL_splat_render route): sorter/ = TOP to POP of sort_keys (one point per texel: P + pid) -> Sort
    POP by sort_cam (ptmethod object) -> Switch (Sortmode off = unsorted) -> sorted. px_rt._sort_gate un-parks the
    COMP only on sort frames. Par names of toptoPOP are guarded (LIVE CHECK P8); failures go to the comment."""
    so = _mk(c, baseCOMP, name)
    so.comment = 'Splat order: un-parked only on sort frames (px_rt._sort_gate); the last sorted POP feeds sgeo.'
    notes = []
    tp = so.op('sort_pts') or so.create(toptoPOP, 'sort_pts')

    def setp(o, nm, v):
        try:
            getattr(o.par, nm).val = v
        except Exception as e:                    # noqa: BLE001
            notes.append('%s.%s: %s' % (o.name, nm, e))
    # Live 31550 (T-131): the input-sequence mappings apply only with rgba = 'custom' (else the TOP's RGBA goes to
    # Color / P and the sequence is ignored), and ONE block per TOP: r g b a -> 'P pid' in a single block (a second
    # block reading the same TOP left pid at its default).
    setp(tp, 'rgba', 'custom')
    try:
        tp.seq.input.numBlocks = 1
    except Exception as e:                        # noqa: BLE001
        notes.append('input seq: %s' % e)
    setp(tp, 'input0top', '../' + keys.name)
    setp(tp, 'input0chanscope', 'r g b a')
    setp(tp, 'input0attrscope', 'P pid')
    if hasattr(tp.par, 'input0filter'):
        setp(tp, 'input0filter', 'nearest')
    try:
        tp.seq.attr.numBlocks = max(int(tp.seq.attr.numBlocks), 1)
        nms = tp.par.attr0name.menuNames
        setp(tp, 'attr0name', 'custom' if 'custom' in nms else nms[-1])
        setp(tp, 'attr0customname', 'pid')
        setp(tp, 'attr0numcomps', 1 if not tp.par.attr0numcomps.isMenu else '1')
    except Exception as e:                        # noqa: BLE001
        notes.append('attr seq: %s' % e)
    sc = so.op('sort_cam') or so.create(nullCOMP, 'sort_cam')
    srt = so.op('sort') or so.create(sortPOP, 'sort')
    _wire(tp, srt)
    setp(srt, 'ptmethod', 'object')
    setp(srt, 'pointobj', sc.name)
    sel = so.op('sort_sel') or so.create(switchPOP, 'sort_sel')
    _wire(tp, sel, 0)
    _wire(srt, sel, 1)
    _expr(sel.par.index, "0 if parent(2).par.Sortmode.eval() == 'off' else 1")
    _expr(srt.par.bypass, "parent(2).par.Sortmode.eval() == 'off'")
    fin = so.op('sorted') or so.create(nullPOP, 'sorted')
    _wire(sel, fin)
    so.comment += (' setup notes: ' + '; '.join(notes))[:400] if notes else ''
    so.allowCooking = False                       # un-parked by the sort gate only
    return so


def build(parent_path='/project1/lab', name=NAME):
    Lg = _logic()
    pc = op(parent_path)
    c = pc.op(name) or pc.create(baseCOMP, name)
    c.allowCooking = True                         # never parked while being built (user rule)
    c.comment = ('PX_pointfx: modular point-cloud / splat FX (sources -> source -> update -> look -> render -> post). '
                 'Modules on the Stack page (add / remove / reorder / duplicate), effector objects in effectors/, '
                 'presets on Presets. Out: out1 (look only), out_preview (gizmos). Pulse Opencontrols.')
    _close_window(c)
    _pars(c, Lg['CORE_PAGES'])
    for ch in list(c.children):
        if ch.valid and ch.name.startswith('_'):
            _sd(ch)
    c.store('px_zkit_file', ZKIT_FILE)

    # 0 code + tables
    _text(c, 'px_logic', _read(LOGIC_FILE), comment='Pure logic: schema, codegen, packing, presets (builders/px_logic.py).')
    rt = _text(c, 'px_rt', _read(RT_FILE), comment='TD runtime (builders/px_rt.py).')
    _text(c, 'pointcloud_logic', _read(PC_FILE), comment='Point-cloud loaders (builders/pointcloud_logic.py, read only).')
    _text(c, 'splat_logic', _read(SPLAT_FILE), comment='Splat loaders (builders/splat_render_logic.py, read only).')
    _text(c, 'menu_logic', _read(MENU_FILE), comment='Live dropdown items (builders/menu_logic.py, T-233).')
    _menus(c)
    lib = _text(c, 'px_lib', _read(os.path.join(GLSL, 'px_common.glsl')), comment='GLSL library (px_common.glsl).')
    mods = _text(c, 'px_modules', _read(os.path.join(GLSL, 'px_modules.glsl')), comment='Module snippets (px_modules.glsl).')
    tu = _text(c, 'px_tmpl_update', _read(os.path.join(GLSL, 'px_update.glsl')), comment='Update stage template.')
    tcl = _text(c, 'px_tmpl_colour', _read(os.path.join(GLSL, 'px_colour.glsl')), comment='Colour stage template.')
    stk = _table(c, 'px_stack', Lg['STACK_COLS'], 'Module stack (order = execution order). Edit -> one recompile.')
    eff = _table(c, 'px_eff', ['name', 'kind', 'path', 'prefix'], 'Effector objects (index = id, max 8).')
    _table(c, 'px_presets', ['name', 'json'], 'Whole looks (Presets page).')
    _table(c, 'px_setlist', ['name'], SETLIST_NOTE)
    _table(c, 'px_notes', NOTES_COLS, NOTES_NOTE)
    _w2_texts(c)

    # 2 engine (before the shaders: the uniform CHOPs they read must exist)
    in_ctl = _mk(c, inCHOP, 'in_ctl')
    in_ctl.comment = 'Optional audio/control CHOP: low mid high level (0..1) + s0..s15 spectrum.'
    in_eff = _mk(c, inCHOP, 'in_eff')
    in_eff.comment = 'Optional CHOP effectors: channels <prefix>tx ty tz (sx = scale), kind chop rows in px_eff.'
    for nm, key, cm in (('eng_g', 'g', 'uG[24]: clock, audio, beat, triggers, sim + dissolve globals, spectrum, view-proj, '
                                       'camera forward, layers.'),
                        ('eng_e', 'e', 'uE[88]: 8 effectors x 11 rows (inverse + world matrix, sdf type + size, centre, '
                                       'axis + speed, velocity, point set + trail spans).'),
                        ('eng_m', 'm', 'uM[]: module rows in compiled layout (header + params; drives applied).'),
                        ('eng_r', 'r', 'uR[8]: render (size, sprite, streak, DOF, res, count).'),
                        ('eng_q', 'q', 'uQ[10]: grade (+ flare).'),
                        ('eng_src', 'src', 'uSrc[17]: sources + morph + actor layer.'),
                        ('eng_cam', 'cam', 'Camera pose tx ty tz ry (orbit integrated).'),
                        ('eng_pts', 'pts', 'uPts texture buffer: point-set effector points (world xyz), all sets.'),
                        ('eng_ptsv', 'ptsv', 'uPtsV texture buffer: their per-point velocities (frame difference).'),
                        ('eng_trail', 'trail', 'uTrail texture buffer: effector trail ring buffers (xyz, age s).'),
                        ('eng_glow', 'glow', 'uGl: effector glow gaussians (P, sigma, quat, colour) x glows.'),
                        ('eng_s', 's', 'Splat MAT uniforms uRes uP1..uP6 (BL_splat_render meaning).'),
                        ('eng_sp', 'sp', 'uSp[4]: splat adapter (side, count, draw end, DOF, fog, size).'),
                        ('eng_info', 'info', 'count side modules effectors drawn splat glows sorts.'),
                        ('eng_gs', 'gs', 'uG[24] for the source pass: static rows only (bounds, layers).'),
                        ('eng_ez', 'ez', 'Zero rows: uE + texture buffers of the source pass (it reads none).')) + ENG_W2:
        _script_chop(c, nm, key, cm, clock=(key == 'g'))
    _shared_eff(c)
    oinfo = _mk(c, outCHOP, 'out_info')
    _wire(c.op('eng_info'), oinfo)

    # 1 inputs
    in_depth = _mk(c, inTOP, 'in_depth')
    in_depth.comment = 'Depth nearness (r, 0..1): DC_depth_cam out_depth.'
    in_video = _mk(c, inTOP, 'in_video')
    in_video.comment = 'Colour for depth points: DC_depth_cam out_video.'
    in_mask = _mk(c, inTOP, 'in_mask')
    in_mask.comment = 'Mask image (mask_image module): body / hands / any TOP.'
    ddef = _constant(c, 'depth_default', 4, 4, 'rgba16float', (0, 0, 0, 1), 'No depth: nearness 0 (no depth points).')
    vdef = _constant(c, 'video_default', 4, 4, 'rgba8fixed', (1, 1, 1, 1), 'No video: white.')
    dsrc = _switch(c, 'depth_src', ddef, in_depth, CONNECTED.format('in_depth'), 'in_depth when wired.')
    vsrc = _switch(c, 'video_src', vdef, in_video, CONNECTED.format('in_video'), 'in_video when wired.')
    dpk = _compute(c, 'in_depth_pack', 'depth_pack_compute', DEPTH_PACK, "op('depth_src').width", "op('depth_src').height",
                   'rgba16float', 'rgb = video, a = nearness (depth size).')
    _wire(vsrc, dpk, 0)
    _wire(dsrc, dpk, 1)
    dpk.par.inputfiltertype = 'linear'
    mdef = _constant(c, 'mask_default', 4, 4, 'rgba8fixed', (0, 0, 0, 0), 'No mask: 0.')
    msrc = _switch(c, 'mask_src', mdef, in_mask, CONNECTED.format('in_mask'), 'in_mask when wired.')

    # 3 source (v1 rest_a / rest_b: A and B now share rest_files, so input 1 is free for the actor, T-84)
    for old in ('rest_a', 'rest_b', 'rest_a_callbacks', 'rest_b_callbacks'):
        _sd(c.op(old))
    for nm, key, cm in (('rest_files', 'files', 'File sources A (rows 0..side-1) and B (rows side..2 side-1), 4 texels '
                                                 'per point, uploaded on load only.'),
                        ('rest_actor', 'actor', 'Actor layer file / current sequence frame (its own side), uploaded on '
                                                'load and when the frame changes.')):
        r = _mk(c, scriptTOP, nm)
        cb = c.op(nm + '_callbacks') or _mk(c, textDAT, nm + '_callbacks')
        cb.text = REST_CB.format(name=nm, key=key)
        cb.dock = r
        r.par.callbacks = nm + '_callbacks'
        r.par.format = 'rgba32float'
        r.comment = cm
    rw4 = '4 * ' + SIDE
    rw5 = '5 * ' + SIDE
    rh = SIDE
    src = _compute(c, 'source', 'source_compute', Lg['source_text'](lib.text, _read(os.path.join(GLSL, 'px_source.glsl'))),
                   rw4, rh, 'rgba32float', 'ONE compute pass: A/B (file / generator / depth) + morph, actor layer, '
                   'pool -> rest texture.')
    _wire(c.op('rest_files'), src, 0)
    _wire(c.op('rest_actor'), src, 1)
    _wire(dpk, src, 2)
    # T-143: static uniforms only, so source cooks when a source input changes (load, spin, morph, depth), not per frame
    _arrays(src, SRC_ARRAYS)

    # state feedback + 4 update / colour (generated)
    st0 = Lg['stack_from_rows']([[x.val for x in stk.row(r)] for r in range(stk.numRows)])
    first = not st0                               # a new COMP: default effectors + stack are added below
    inplace = "{}Statemode.eval() == 'inplace'".format(PP)
    sinit = _constant(c, 'state_init', rw5, rh, 'rgba32float', (0, 0, 0, 0), 'Zero state (first frame / in place).')
    sfb = _mk(c, feedbackTOP, 'state_fb')
    _wire(sinit, sfb)
    ssrc = _switch(c, 'state_src', sfb, sinit, inplace, 'Feedback (last state) or zeros (in place mode).')
    cg = Lg['codegen'](st0, lib.text, tu.text, tcl.text, mods.text, c.op('px_palette').text)
    up = _compute(c, 'update', 'update_compute', cg['update'], rw5, rh, 'rgba32float',
                  'ONE compute pass (generated): update modules + spring / damping / drag. 5 texels per point.')
    _text(c, 'update_inplace', cg['update_inplace'], dock=up, comment='Same shader, reads its own output (In place).')
    _expr(up.par.computedat, "'update_inplace' if {} else 'update_compute'".format(inplace))
    _expr(up.par.outputaccess, "'readwrite' if {} else 'writeonly'".format(inplace))
    _expr(up.par.clearoutputs, '0 if {} else 1'.format(inplace))
    _wire(ssrc, up, 0)
    _wire(src, up, 1)
    _wire(msrc, up, 2)
    _arrays(up, STAGE_ARRAYS)
    sfb.par.top = up.name
    ost = _mk(c, outTOP, 'out_state')
    _wire(up, ost)
    lk = _compute(c, 'look', 'colour_compute', cg['colour'], '3 * ' + SIDE, rh, 'rgba32float',
                  'ONE compute pass (generated): colour modules + dissolve fade / edge glow. 3 texels per point.')
    _wire(up, lk, 0)
    _wire(src, lk, 1)
    _wire(msrc, lk, 2)
    _arrays(lk, STAGE_ARRAYS)
    _bind_pal(lk)
    for pn, dn, base, code in (('update_probe', 'update_next', up, cg['update']),
                               ('colour_probe', 'colour_next', lk, cg['colour'])):
        pr = _compute(c, pn, dn, code, '8', '8', 'rgba32float',
                      'Compile check of a new stack (8x8, cooked only when forced; output bounds-guarded).', viewer=False)
        for k, s_ in enumerate((ssrc if base is up else up, src, msrc)):
            _wire(s_, pr, k)
        _arrays(pr, STAGE_ARRAYS)
        if base is lk:
            _bind_pal(pr)
    c.store('px_layout', [dict(il, slots=dict((k, list(v)) for k, v in il['slots'].items())) for il in cg['layout']])
    c.store('px_rows', cg['rows'])
    c.store('px_hash', cg['hash'])

    # 5 render
    vtx = _text(c, 'pmat_vertex', _read(os.path.join(GLSL, 'px_vert.glsl')), comment='Instance -> textures -> quad.')
    pix = _text(c, 'pmat_pixel', _read(os.path.join(GLSL, 'px_pixel.glsl')), comment='Sprite shapes, premultiplied.')
    samplers = [('sState', 'update'), ('sLook', 'look'), ('sRest', 'source')]
    m = _mat(c, 'pmat', samplers, '1')
    vtx.dock = m
    pix.dock = m
    count = '{}.count_from_pars({}Quality.eval(), {}Count.eval())'.format(LG, PP, PP)
    _geo(c, 'pgeo', 'pmat', "max(1, int(op('eng_info')['drawn']))")   # all points, or the pool under splats
    # effector glow (A5): additive 3D gaussians through the reused splat shader (glow adapter), drawn with the sprites
    _text(c, 'glow_glsl', _read(os.path.join(GLSL, 'px_glow_adapter.glsl')) + _read(SPLAT_GLSL),
          comment='px_glow_adapter.glsl + splat_render.glsl (BL_splat_render, reused).')
    gvec = [[PP + 'Resx', PP + 'Resy', 0, "op('eng_info')['glows']"], [1, 1, 0.004, 0.3], [0, 3, 1, 1], [0, 0, 0, 0],
            [0, 0, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    gm = _splat_mat(c, 'glowmat', 'glow_glsl', gvec, [('uGl', 'eng_glow')], [('sOrder', 'mask_default')], "'one'")
    c.op('glow_glsl').dock = gm
    _splat_geo(c, 'glowgeo', 'glowmat', count_expr="max(1, int(op('eng_info')['glows']))")
    cam = _mk(c, cameraCOMP, 'pcam')
    for k in ('tx', 'ty', 'tz', 'ry'):
        _expr(getattr(cam.par, k), "op('eng_cam')['{}']".format(k))
    _expr(cam.par.fov, PP + 'Fov')
    cam.par.near = 0.01
    cam.par.far = 1000
    cam.comment = 'Output camera: orbit Camdist / Orbit / Camheight / Fov (Look page).'
    r = _mk(c, renderTOP, 'render')
    r.par.camera = 'pcam'
    _expr(r.par.geometry, RENDER_GEO)
    r.par.lights = ''
    r.par.outputresolution = 'custom'
    _expr(r.par.resolutionw, PP + 'Resx')
    _expr(r.par.resolutionh, PP + 'Resy')
    r.par.format = 'rgba16float'
    r.par.bgcolorr = r.par.bgcolorg = r.par.bgcolorb = r.par.bgcolora = 0
    r.par.cullface = 'neither'
    r.comment = ('Sprites + effector glow, Resx x Resy, 16F, transparent (premultiplied). No gizmos in the output. '
                 'Under splats: the pool embers only (+ glow).')

    # 5b splats (S1-S6): sort keys -> sorter (gated) -> sgeo + smat (BL_splat_render shader + PX adapter) -> srender
    keys = _compute(c, 'sort_keys', 'sortkey_compute', _read(os.path.join(GLSL, 'px_sortkey.glsl')), SIDE, SIDE,
                    'rgba32float', 'Sort keys: (P, id) per texel for the TOP to POP (cooks only on sort frames).')
    _wire(up, keys, 0)
    _arrays(keys, [('uSp', 'eng_sp')])
    _sorter(c, keys, 'sorter')
    _text(c, 'smat_glsl', _read(os.path.join(GLSL, 'px_splat_adapter.glsl')) + _read(SPLAT_GLSL),
          comment='px_splat_adapter.glsl + splat_render.glsl (BL_splat_render, reused, not copied).')
    svec = [["op('eng_s')['%s'][%d]" % (ax, k) for ax in 'xyzw'] for k in range(7)]
    sm = _splat_mat(c, 'smat', 'smat_glsl', svec, [('uSp', 'eng_sp')],
                    [('sOrder', 'mask_default'), ('sState', 'update'), ('sLook', 'look'), ('sRest', 'source')],
                    "'one' if {}Sortmode.eval() == 'off' else 'omsa'".format(PP))
    c.op('smat_glsl').dock = sm
    _splat_geo(c, 'sgeo', 'smat', instance_op='sorter/sorted')
    sr = _mk(c, renderTOP, 'srender')
    sr.par.camera = 'pcam'
    sr.par.geometry = 'sgeo'
    sr.par.lights = ''
    sr.par.outputresolution = 'custom'
    _expr(sr.par.resolutionw, PP + 'Resx')
    _expr(sr.par.resolutionh, PP + 'Resy')
    sr.par.format = 'rgba16float'
    sr.par.bgcolorr = sr.par.bgcolorg = sr.par.bgcolorb = sr.par.bgcolora = 0
    sr.par.cullface = 'neither'
    _expr(sr.par.antialias, SPLAT_AA_E)
    sr.comment = ('Gaussian splats (sorted, premultiplied over). Cooks only when Render resolves to splats. MSAA = '
                  'Splataa (Look page, default 1x: vertex-bound, aa4 cost ~1.5 ms GPU for no visible change).')
    lay_ = _compute(c, 'layers', 'layers_compute', _read(os.path.join(GLSL, 'px_layers.glsl')), PP + 'Resx',
                    PP + 'Resy', 'rgba16float', 'Splats + sprites (pool embers, glow): ONE compute pass.')
    _wire(sr, lay_, 0)
    _wire(r, lay_, 1)
    swr = _mk(c, switchTOP, 'sw_render')
    _wire(r, swr, 0)
    _wire(lay_, swr, 1)
    _wire(sr, swr, 2)
    _expr(swr.par.index, SW_RENDER)
    swr.comment = ('Sprites (render), splats + embers / glow (layers), or splats alone (srender: no pool, no glow, so '
                   'render + layers never cook, T-143). Render par, auto = splats for splat files.')

    # 6 preview + effectors
    holder = _mk(c, baseCOMP, 'effectors')
    holder.comment = 'Effector objects: move / rotate / scale them (Geometry COMPs = box/sphere/plane..., Null = point).'
    gz = _mk(c, baseCOMP, 'gizmos')
    gz.comment = 'Axes gizmos for Null / CHOP effectors (made by px_rt, follow their effector).'
    for h, col in ((holder, (1.0, 0.6, 0.1)), (gz, (1.0, 1.0, 1.0))):
        wm = h.op('giz_mat') or h.create(wireframeMAT, 'giz_mat')
        try:
            wm.par.colorr, wm.par.colorg, wm.par.colorb = col
        except Exception:
            pass
    stride = 'max(1, -(-{} // max(1, {}Previewcount.eval())))'.format(count, PP)
    mp = _mat(c, 'pmat_prev', samplers, stride, all_ids=True)
    _geo(c, 'pgeo_prev', 'pmat_prev', '-(-{} // ({}))'.format(count, stride))
    pv = _mk(c, cameraCOMP, 'pv_cam')
    for k in ('tx', 'ty', 'tz'):
        _expr(getattr(pv.par, k), "op('eng_cam')['{}'] * 1.6".format(k))
    _expr(pv.par.ry, "op('eng_cam')['ry']")
    _expr(pv.par.fov, PP + 'Fov')
    pv.par.near = 0.01
    pv.par.far = 1000
    rp = _mk(c, renderTOP, 'render_preview')
    rp.par.camera = 'pv_cam'
    rp.par.lights = ''
    rp.par.outputresolution = 'custom'
    _expr(rp.par.resolutionw, PREVIEW_W)               # half of Resx / Resy: follows the render resolution (28 Oct)
    _expr(rp.par.resolutionh, PREVIEW_H)
    rp.par.format = 'rgba8fixed'
    rp.par.bgcolorr = rp.par.bgcolorg = rp.par.bgcolorb = 0.03
    rp.par.bgcolora = 1
    rp.par.cullface = 'neither'
    rp.comment = ('Preview: decimated cloud + effector objects (wire) + gizmos. Half of Resx x Resy (540x960 at '
                  '1080x1920), only cooks when viewed.')
    op_ = _mk(c, outTOP, 'out_preview')
    _wire(rp, op_)
    rtm = c.op('px_rt').module
    if first:
        for kind, nm, xf in DEFAULT_EFFECTORS:
            if not any(row.get('name') == nm for row in rtm.eff_table(c)):
                rtm.add_effector(c, kind, nm, xf)
    for row in rtm.eff_table(c):                 # v1 effectors get the Effector page (motion, trail, glow, points)
        o = c.op(row['path']) if row.get('path') and row.get('kind') not in ('chop', 'camera', 'actor') else None
        if o is not None:
            rtm.eff_page(o)
    rtm.install_builtins(c)
    rtm._preview_geometry(c)

    # trail + 7 post
    tb = _constant(c, 'trail_blank', PP + 'Resx', PP + 'Resy', 'rgba16float', (0, 0, 0, 0),
                   'Trail start (transparent).')
    tfb = _mk(c, feedbackTOP, 'trail_fb')
    _wire(tb, tfb)
    tr = _compute(c, 'trail', 'trail_compute', _read(os.path.join(GLSL, 'px_trail.glsl')), PP + 'Resx',
                  PP + 'Resy', 'rgba16float', 'Trails: max(render, last * Trailkeep). Cooks only when Trails is on.')
    _wire(swr, tr, 0)
    _wire(tfb, tr, 1)
    tr.seq.vec.numBlocks = max(int(tr.seq.vec.numBlocks), 1)
    tr.par.vec0name = 'uT'
    _expr(tr.par.vec0valuex, PP + 'Trailkeep')
    tfb.par.top = tr.name
    swt = _mk(c, switchTOP, 'sw_trail')
    _wire(swr, swt, 0)
    _wire(tr, swt, 1)
    _expr(swt.par.index, '1 if {}Trails else 0'.format(PP))
    # Bloom = own glow: 1/8 mipmap downsample + ONE 7x7 compute pass, added in post (input 1). Live 31550: the stock
    # Bloom TOP cost ~1.7-3.2 ms per frame at full, half, quarter or eighth resolution alike (fixed passes).
    gin = _mk(c, resolutionTOP, 'glow_in')
    _wire(swt, gin)
    gin.par.outputresolution = 'eighth'
    gin.par.filtertype = 'mipmap'
    gin.par.format = 'rgba16float'
    gin.comment = '1/8 of the image, mipmap filtered (every point counts, no sparkle).'
    bl = _bloom_v2(c, gin)
    boff = _constant(c, 'bloom_off', 4, 4, 'rgba16float', (0, 0, 0, 0), 'Bloom 0: no glow (glow chain never cooks).')
    swb = _mk(c, switchTOP, 'sw_bloom')
    _wire(boff, swb, 0)
    _wire(bl, swb, 1)
    _expr(swb.par.index, '1 if {}Bloom > 0 else 0'.format(PP))
    po = _compute(c, 'post', 'post_compute', _read(os.path.join(GLSL, 'px_post.glsl')), PP + 'Resx',
                  PP + 'Resy', 'rgba16float', 'Grade: ONE compute pass (bloom add, exposure, split tone, tone map, haze...).')
    po.par.inputfiltertype = 'linear'
    _wire(swt, po, 0)
    _wire(swb, po, 1)
    _arrays(po, [('uQ', 'eng_q')])
    _post_clock(po)
    out1 = _mk(c, outTOP, 'out1')
    _wire(po, out1)
    _haze(c)
    _geo(c)
    _lines(c)
    _camera(c)
    _points_src(c)
    _atlas(c)
    _grid(c)
    _sound(c)
    _proj(c)

    # callbacks (last: nothing fires while the network is half built)
    pul = _mk(c, parameterexecuteDAT, 'px_pulses')
    pul.text = PULSES
    pul.par.op = c
    pul.par.pars = '*'
    pul.par.custom = True
    pul.par.builtin = False
    pul.par.valuechange = False
    pul.par.onpulse = True
    val = _mk(c, parameterexecuteDAT, 'px_values')
    val.text = VALUES
    val.par.op = c
    val.par.pars = ' '.join(rtm.LOAD_PARS) + ' ' + VALUE_PARS
    val.par.custom = True
    val.par.builtin = False
    val.par.valuechange = True
    val.par.onpulse = False
    sw = _mk(c, datexecuteDAT, 'stack_watch')
    sw.text = STACK_WATCH
    sw.par.dat = 'px_stack'
    sw.par.tablechange = True
    _engine_callbacks(c, rtm)
    for d in (pul, val, sw):                     # T-97: callbacks of a DAT whose text was rewritten need active off/on
        d.par.active = False
        d.par.active = True
    if first:                                    # default stack (+ its pages); the watch compiles it once
        st = []
        vals = {}
        for t, v in DEFAULT_STACK:
            st, uid = Lg['add_module'](st, t)
            for k, x in v.items():
                vals[Lg['par_name'](uid, k)] = x
        rtm.sync_pages(c, st, vals)
        rtm.write_stack(c, st)
    else:
        rtm.sync_pages(c, st0)
    # The new stack_watch DAT Execute did not fire for the write_stack above in the same exec (live, 31550): compile
    # explicitly. Idempotent: an unchanged stack hash returns at once.
    rtm.stack_changed(c)
    rtm.load(c, recook=True)

    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    _clamp_exprs(c)                                   # phase B hard size limits (T-231)
    _phaseC_ops(c)                                    # phase C: px_auto / px_perf, uKs on sort_keys
    _phaseC_exprs(c)                                  # phase C: auto-quality + external camera expressions
    rtm.instance_check(c)
    stages = []
    for s_ in STAGES:
        s2 = dict(s_)
        s2['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
        if s2['ops']:
            stages.append(s2)
    try:
        lay = op('/jazib_mcp/handlers').module.layout_stages(c, stages, True, arrange='mixed')
    except Exception as e:
        lay = 'layout failed: {}'.format(e)
    return {'comp': c.path, 'ops': len(c.children), 'stack': [[i['uid'], i['type']] for i in rtm.stack(c)],
            'effectors': [e['name'] for e in rtm.eff_table(c)], 'rows': c.fetch('px_rows', 0, search=False),
            'layout': str(lay)[:300]}


def _post_clock(po):
    """Grain seed = the frame, from a TOP expression (T-143: eng_q no longer cooks every frame for it)."""
    po.seq.vec.numBlocks = max(int(po.seq.vec.numBlocks), 1)
    po.par.vec0name = 'uQf'
    _expr(po.par.vec0valuex, 'absTime.frame % 65536')


def _autoguard(c):
    """px_autoguard (28 Oct): M*progress / M*drive events -> px_rt.auto_guard. Idempotent."""
    g = _mk(c, parameterexecuteDAT, 'px_autoguard')
    if g.text != AUTOGUARD:
        g.text = AUTOGUARD
    g.par.op = c
    g.par.pars = 'M*progress M*drive'
    g.par.custom = True
    g.par.builtin = False
    for nm in ('valuechange', 'expressionchange', 'exportchange', 'modechange'):
        getattr(g.par, nm).val = True
    g.par.onpulse = False
    g.comment = 'progress / drive taken by the user -> auto progress off (px_rt.auto_guard, 28 Oct).'
    return g


def _engine_callbacks(c, rtm):
    """T-143 event-driven engine: frame-start tick, par / effector / table watchers (all idempotent)."""
    tk = _mk(c, executeDAT, 'px_tick')
    tk.text = TICK
    for nm in ('framestart', 'frameend', 'start', 'create', 'exit', 'playstatechange', 'devicechange',
               'projectpresave', 'projectpostsave'):
        if hasattr(tk.par, nm):
            getattr(tk.par, nm).val = (nm == 'framestart')
    dt_ = _mk(c, parameterexecuteDAT, 'px_dirty')
    dt_.text = DIRTY
    dt_.par.op = c
    dt_.par.pars = '*'
    dt_.par.custom = True
    dt_.par.builtin = False
    dt_.par.valuechange = True
    dt_.par.onpulse = False
    _autoguard(c)
    ew = _mk(c, parameterexecuteDAT, 'eff_watch')
    ew.text = EFF_WATCH
    ew.par.op = 'effectors/*'                    # pattern, new effectors included (probed live, T-143)
    ew.par.pars = '*'
    ew.par.custom = True
    ew.par.builtin = True
    ew.par.valuechange = True
    ew.par.onpulse = False
    et = _mk(c, datexecuteDAT, 'eff_tab_watch')
    et.text = EFF_TAB_WATCH
    et.par.dat = 'px_eff'
    et.par.tablechange = True
    for d in (tk, dt_, ew, et):                  # T-97
        d.par.active = False
        d.par.active = True
    rtm.mark_all(c)


# ------------------------------------------------------------------------------------------------- wave 2 (27 Oct 2026)
# docs/builds/px.md "Wave 2": shared effectors (K37), light module (L1 / L2), shared palette (CO2-CO5), haze + bloom v2
# (H1-H3, GL1), geometry in the scene (GE1 / GE4), lines layer (G1-G6). Every new part is off by default: out1 is the
# v2 image exactly (live check W2-0: diff 0). Each helper is idempotent and is also a wave2_upgrade step for an
# existing PX (main: one step per exec, T-146 / T-152).

def _ns(path):
    ns = dict(globals())
    exec(_read(path), ns)
    return ns


def _w2_texts(c):
    """Text DATs wave 2 needs: px_palette.glsl (colour stage include), palette_map_logic (px_palmap), px_haze_logic
    (px_hazelogic), the W1-E splat geo adapter."""
    _text(c, 'px_palette', _read(os.path.join(GLSL, 'px_palette.glsl')), comment='W1-B palette include (colour stage).')
    _text(c, 'px_palmap', _read(PALMAP_FILE), comment='W1-B palette logic (builders/palette_map_logic.py, read only).')
    _text(c, 'px_hazelogic', _read(HAZE_FILE), comment='W1-D haze / bloom logic (builders/px_haze_logic.py, read only).')
    _text(c, 'splat_geo_adapter', _read(os.path.join(GLSL, 'splat_geo_adapter.glsl')),
          comment='W1-E geometry hooks for the splat MAT (only in smat_glsl while Geoon).')


def _shared_eff(c):
    """eff_none + eff_in (Select CHOP of /project1/effectors/eff_rows) = uEffRows of the update / colour stages."""
    none = _mk(c, constantCHOP, 'eff_none')
    for k, nm in enumerate('xyzw'):
        getattr(none.par, 'name%d' % k).val = nm
        getattr(none.par, 'value%d' % k).val = 0
    none.comment = 'Empty shared effector list (count 0) while /project1/effectors is missing.'
    use = c.op('eff_use')
    if use is None:
        use = _mk(c, constantCHOP, 'eff_use')
        use.par.name0 = 'use'
        use.par.value0 = 1
    use.comment = 'Wave 4: 1 while PX reads the shared list (px_rt._eff_use); 0 = eff_in is eff_none.'
    sel = _mk(c, selectCHOP, 'eff_in')
    _expr(sel.par.chops, EFF_IN_EXPR)
    sel.comment = ('Shared effector list (/project1/effectors/eff_rows) -> uEffRows: module effectors that are not '
                   'PX own names (names / #tag / all), and the light effectors (light module, haze).')
    return sel


def _bind_pal(o):
    """uPal (eng_pal, Arrays) + uPalCtl (eng_palc, Vectors) on a GLSL TOP (W1-B bind_glsl, blocks found by name)."""
    pm = _ns(PALMAP_FILE)
    return pm['bind_glsl'](o, 'eng_pal', PAL_CTL, ParMode)


def _vecs(o, specs):
    """Vectors blocks by name (found or appended): specs = [(name, 4 values / expressions)]."""
    for name, vals in specs:
        k = next((i for i in range(int(o.seq.vec.numBlocks)) if getattr(o.par, 'vec%dname' % i).eval() == name), None)
        if k is None:
            k = int(o.seq.vec.numBlocks)
            o.seq.vec.numBlocks = k + 1
        getattr(o.par, 'vec%dname' % k).val = name
        for ax, v in zip('xyzw', vals):
            p = getattr(o.par, 'vec%dvalue%s' % (k, ax))
            if isinstance(v, str):
                _expr(p, v)
            else:
                p.mode = ParMode.CONSTANT
                p.val = v


def _cs_exprs(prefix):
    return [PP + prefix + 'colsrc.menuIndex', PP + prefix + 'palpos', PP + prefix + 'palspread', PP + prefix + 'keep']


def _bloom_v2(c, gin):
    """Bloom v2 (W1-D px_bloom.glsl) in place of px_glow: input 0 = glow_in (1/8, wide), input 1 = glow_t (glow_in
    again = legacy, or glow_q 1/4 when the tight scale / ring is on). Defaults = px_glow exactly (W2-4 diff 0)."""
    src = c.op('sw_trail')
    gq = _mk(c, resolutionTOP, 'glow_q')
    _wire(src, gq)
    gq.par.outputresolution = 'quarter'
    gq.par.filtertype = 'mipmap'
    gq.par.format = 'rgba16float'
    gq.comment = '1/4 of the image, mipmap (tight bloom scale / ring; cooks only while Bloomtight or Bloomring > 0).'
    gt = _mk(c, switchTOP, 'glow_t')
    _wire(gin, gt, 0)
    _wire(gq, gt, 1)
    _expr(gt.par.index, '1 if ({0}Bloomtight > 0 or {0}Bloomring > 0) else 0'.format(PP))
    gt.comment = 'Bloom input 1: glow_in (legacy, one scale) or glow_q (tight scale / ring).'
    pal = _read(os.path.join(GLSL, 'px_palette.glsl'))
    bl = _compute(c, 'bloom', 'glow_compute', pal + '\n' + _read(os.path.join(GLSL, 'px_bloom.glsl')),
                  "op('glow_t').width", "op('glow_t').height", 'rgba16float',
                  'Bloom v2: wide 1/8 + tight 1/4, knee, firefly clamp, ring halo, palette tint (defaults = old glow).')
    bl.par.inputfiltertype = 'linear'
    _wire(gin, bl, 0)
    _wire(gt, bl, 1)
    _vecs(bl, [('uB', [PP + 'Bloomthr', PP + 'Bloom', 1.5, PP + 'Bloomknee']),
               ('uB2', [1.0, PP + 'Bloomtight', PP + 'Bloomtightspace', PP + 'Bloomclamp']),
               ('uBt', [PP + 'Bloomtintr', PP + 'Bloomtintg', PP + 'Bloomtintb', PP + 'Bloomsat']),
               ('uGlowCs', _cs_exprs('Bloom')),
               ('uBr', [PP + 'Bloomring', PP + 'Bloomringr', PP + 'Bloomringw', PP + 'Bloomringchroma'])])
    _bind_pal(bl)
    return bl


def _haze(c):
    """Volumetric haze + shafts (W1-D px_haze.glsl) inside PX: haze_src (1/4 or 1/2 of sw_trail, mipmap) -> haze
    (compute) -> sw_haze -> post input 2 (pxhApply folded into px_post, no extra composite op). Off (Vhon 0) = post
    never samples it (uQh.x 0) and haze / haze_src never cook."""
    src = c.op('sw_trail')
    hs = _mk(c, resolutionTOP, 'haze_src')
    _wire(src, hs)
    hs.par.outputresolution = 'custom'
    div = "(4 if parent().par.Vhres.eval() == 'quarter' else 2)"
    _expr(hs.par.resolutionw, "max(1, int(parent().par.Resx) // %s)" % div)
    _expr(hs.par.resolutionh, "max(1, int(parent().par.Resy) // %s)" % div)
    hs.par.filtertype = 'mipmap'
    hs.par.format = 'rgba16float'
    hs.comment = 'Haze input: the scene at 1/4 (or 1/2), mipmap; its alpha occludes the shafts.'
    hd = _constant(c, 'haze_depth', 1, 1, 'rgba16float', (0, 0, 0, 1), 'No scene depth (Depthmode none: alpha).')
    pal = _read(os.path.join(GLSL, 'px_palette.glsl'))
    hz = _compute(c, 'haze', 'haze_compute', pal + '\n' + _read(os.path.join(GLSL, 'px_haze.glsl')),
                  "max(1, int(parent().par.Resx) // %s)" % div, "max(1, int(parent().par.Resy) // %s)" % div,
                  'rgba16float', 'Volumetric haze: height fog + drift, in-scatter of up to 8 light effectors, shafts.')
    hz.par.inputfiltertype = 'mipmap'
    _wire(hs, hz, 0)
    _wire(hd, hz, 1)
    _arrays(hz, [('uH', 'eng_h'), ('uHL', 'eng_hl')])
    _vecs(hz, [('uHt', ['absTime.seconds', 'absTime.frame % 65536', 0.0, 0.0]), ('uHazeCs', _cs_exprs('Vh'))])
    _bind_pal(hz)
    off = _constant(c, 'haze_off', 4, 4, 'rgba16float', (0, 0, 0, 0), 'Haze off (post does not sample it).')
    sw = _mk(c, switchTOP, 'sw_haze')
    _wire(off, sw, 0)
    _wire(hz, sw, 1)
    _expr(sw.par.index, '1 if ({0}Vhon and {0}Vhamount > 0) else 0'.format(PP))
    sw.comment = 'Haze into post (input 2) only while Vhon.'
    po = c.op('post')
    _text(c, 'post_compute', _read(os.path.join(GLSL, 'px_post.glsl')))
    _wire(sw, po, 2)
    _vecs(po, [('uQh', ['{0}Vhamount if {0}Vhon else 0'.format(PP), 1.0, 0.0, 0.0])])
    return hz


def _scene_out(c):
    """The rendered scene that trail / lines / bloom / haze read: geo_out (Geo page) or sw_render."""
    return c.op('geo_out') or c.op('sw_render')


def _geo(c):
    """Geometry in the PX scene (W1-E recipe, docs/builds/px_geo.md), one Render Pass chain (31550: a Render TOP feeds
    only ONE Render Pass TOP, live b5): geo_render (Geocomps, lit by Geolights: the light effectors + geo_key, opaque,
    depth write) -> geo_pass (splats over its colour + depth, depth test on / write off; splat mode only) -> geo_spass
    (sprites / pool embers / effector glow the same way) -> geo_out (Switch: sw_render while Geoon is off). Off = the
    old wiring exactly (geo_out passes sw_render; the geo ops draw nothing and nothing pulls them)."""
    notes = []
    sr = c.op('srender')
    ns = _ns(SPLAT_BUILDER)
    sw = ns['geo_stage'](c, sr, draw='sgeo', mat='smat', cam_expr="'pcam'", res_exprs=(PP + 'Resx', PP + 'Resy'),
                         P=PP, notes=notes)
    _sd(sw)                                             # geo_stage's switch: PX uses geo_out after the whole chain
    splat = 'int(%s)' % _CH0.format('eng_info', 'splat')
    gr = c.op('geo_render')
    _expr(gr.par.geometry, "parent().op('splat_logic').module.geo_geometry({0}Geocomps.eval(), 'sgeo') "
                           "if {0}Geoon.eval() else ''".format(PP))
    _expr(gr.par.lights, "parent().op('px_rt').module.geo_lights(parent(), env=parent().par.Geoenv.eval() "
                         "if hasattr(parent().par, 'Geoenv') else False)")   # reading Geoenv = re-evaluated on it
    gp = c.op('geo_pass')
    _expr(gp.par.geometry, "'sgeo' if ({0}Geoon.eval() and {1}) else ''".format(PP, splat))
    sp = _mk(c, renderpassTOP, 'geo_spass')
    _wire(gp, sp)
    sp.par.camera = 'pcam'
    _expr(sp.par.geometry, "({0}) if {1}Geoon.eval() else ''".format(RENDER_GEO, PP))
    sp.par.lights = ''
    for nm in ('cleardepth', 'clearcolor'):
        if getattr(sp.par, nm, None) is not None:
            getattr(sp.par, nm).val = False
        else:
            notes.append('geo_spass.%s missing' % nm)
    sp.comment = 'Geo: sprites (+ pool embers, effector glow) over geo_pass, depth test on / write off (pmat).'
    _expr(c.op('pmat').par.depthtest, 'bool({}Geoon.eval())'.format(PP))
    c.op('pmat').par.depthwriting = False
    go = _mk(c, switchTOP, 'geo_out')
    _wire(c.op('sw_render'), go, 0)
    _wire(sp, go, 1)
    _expr(go.par.index, '1 if {}Geoon.eval() else 0'.format(PP))
    go.comment = 'Geo off: sw_render (unchanged). Geo on: geometry + splats + sprites (geo_spass).'
    for nm, k in (('trail', 0), ('sw_trail', 0), ('sw_lines', 0), ('PX_lines', 0)):
        o = c.op(nm)
        if o is not None and len(o.inputs) > k and o.inputs[k] is c.op('sw_render'):
            _wire(go, o, k)
    lay, swr = c.op('layers'), c.op('sw_render')       # the v2 wiring (an earlier draft rewired these); wave 4 K26:
    rr = c.op('pr_render') or c.op('render')            # through the projection switches when they exist
    ss = c.op('pr_srender') or sr
    _wire(ss, lay, 0)
    _wire(rr, lay, 1)
    _wire(rr, swr, 0)
    _wire(lay, swr, 1)
    _wire(ss, swr, 2)
    for nm in ('geo_switch', 'geo_sswitch'):           # earlier drafts
        _sd(c.op(nm))
    dp = _mk(c, depthTOP, 'lines_depth')
    dp.par.op = 'geo_render'
    if getattr(dp.par, 'depthspace', None) is not None:
        dp.par.depthspace = 'cameraspace'
    dp.comment = 'Linear eye depth of the geometry (geo_render): lines occlusion (Linesdepth) + haze depth (Geo on).'
    hz = c.op('haze')
    if hz is not None:                                  # wave 3: haze stops at the geometry (Geo on)
        hs = _mk(c, switchTOP, 'haze_dsw')
        _wire(c.op('haze_depth'), hs, 0)
        _wire(dp, hs, 1)
        _expr(hs.par.index, '1 if {}Geoon.eval() else 0'.format(PP))
        hs.comment = 'Haze depth: none (1x1) or the geometry eye depth while Geo is on.'
        _wire(hs, hz, 1)
    _geo_env(c, notes)
    c.op('px_rt').module.geo_sync(c)
    return notes


PROX_MAT_FILE = os.path.join(HERE, 'prox_mat.py')


def _geo_env(c, notes=None):
    """Wave 4 GE3 chrome: the scene as an environment for the Geo objects' PBR MATs, through W1-E's env_capture
    (prox_mat.py, read only: cube Render TOP -> equirect -> Cache hold, pulled only every Geoenveveryn frames) on PX's
    DECIMATED preview geometry (pgeo_prev: Previewcount sprites, not the full splat set: the BL capture of every splat
    was ~16 ms) at Geoenvres px; geo_env_light joins geo_render's lights (px_rt.geo_lights). Off by default (Geoenv)."""
    try:
        ns = dict(globals())
        exec(open(PROX_MAT_FILE).read(), ns)
        return ns['env_capture'](c, 'geo_env', "'pgeo_prev' if ({0}Geoon.eval() and {0}Geoenv.eval()) else ''".format(PP),
                                 (PP + 'Geoenvcentrex', PP + 'Geoenvcentrey', PP + 'Geoenvcentrez'),
                                 'max(16, int(%sGeoenvres))' % PP, PP + 'Geoenveveryn', PP + 'Geoenvdimmer',
                                 lights='', use_cond='p.par.Geoon.eval() and p.par.Geoenv.eval()')
    except Exception as e:  # noqa: BLE001
        if notes is not None:
            notes.append('geo_env skipped: %s' % e)
        return None


def _lines(c):
    """Lines layer (W1-C PX_lines, built INSIDE PX): in1 = sw_render (alpha occlusion, edges), in_points = update
    (state texture, Ptstride 5), in_depth = lines_depth (geometry depth), Camera = pcam; Outmode composite = scene +
    lines in one compute (no extra op), Amount 0 = sw_render exactly. sw_lines (Lineson) feeds trail / glow / post,
    so the bloom catches the HDR lines. Off = sw_render, PX_lines never cooks."""
    ns = _ns(LINES_FILE)
    r = ns['build'](c.path, 'PX_lines')
    pl = c.op('PX_lines')
    _wire(_scene_out(c), pl, 0)
    _wire(c.op('update'), pl, 1)
    _wire(c.op('lines_depth') or c.op('depth_default'), pl, 2)
    # PX-owned pars are EXPRESSIONS: a look recall (px_rt._apply_lines) resets every constant PX_lines par to its
    # default, which put Ptstride back to 1 (wave 4 found it: connect / contour read the wrong texels after a recall)
    _expr(pl.par.Outmode, "'composite'")
    _expr(pl.par.Ptstride, '5')
    _expr(pl.par.Ptcount, 'int(%s)' % _CH0.format('eng_info', 'count'))
    if getattr(pl.par, 'Cnindextop', None) is not None:          # wave 4: connect grid index on the REST positions
        _expr(pl.par.Cnindextop, "op('source')")                  # (static: indexed once per scene / source edit)
        _expr(pl.par.Cnistride, '4')
        c.op('px_rt').module._lines_box(c, c.op('px_rt').module.S(c).get('bb') or ((0.0, 0.0, 0.0), 2.0))
    _expr(pl.par.Camera, "op('pcam')")
    _expr(pl.par.Resx, PP + 'Resx')
    _expr(pl.par.Resy, PP + 'Resy')
    _expr(pl.par.Usedepth, 'bool({0}Linesdepth and {0}Geoon)'.format(PP))
    for nm in ('Palsource', 'Palmode', 'Palinterp', 'Palreverse', 'Palshift'):   # one palette: PX's Palette page
        p = getattr(pl.par, nm, None)
        if p is not None:
            _expr(p, (PP + nm + '.eval()') if nm != 'Palshift' else _CH0.format('eng_palc', 'y'))
    sl = _mk(c, switchTOP, 'sw_lines')
    _wire(_scene_out(c), sl, 0)
    if not (len(sl.inputs) > 1 and sl.inputs[1] is pl):
        sl.inputConnectors[1].connect(pl.outputConnectors[0])     # a COMP connects by its output connector
    _expr(sl.par.index, '1 if {}Lineson else 0'.format(PP))
    sl.comment = 'Lines layer on (PX_lines composite: scene + lines) or the render as it was.'
    for nm, k in (('trail', 0), ('sw_trail', 0)):
        _wire(sl, c.op(nm), k)
    pl.allowCooking = True
    return r


HOT_PTS = '''// hot_pts (PX wave 3, SA5 / SA21): every k-th point of the state as a `cloud` point for the shared voxel grid:
// rgb = P, a = 1 when its heat > uHot.x or its look luminance > uHot.y (uHot.y 0 = heat only), else 0 (not a seed).
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uHot;      // x heat threshold, y emission luma threshold (0 off), z stride (points per texel), w count
void main()
{
	ivec2 g = ivec2(gl_GlobalInvocationID.xy);
	ivec2 res = ivec2(uTDOutputInfo.res.zw);
	if (g.x >= res.x || g.y >= res.y) return;
	int id = (g.y * res.x + g.x) * max(int(uHot.z + 0.5), 1);
	ivec2 ssz = textureSize(sTD2DInputs[0], 0);
	int side = max(ssz.x / 5, 1);
	vec4 o = vec4(0.0);
	if (id < int(uHot.w + 0.5)) {
		vec4 s0 = texelFetch(sTD2DInputs[0], ivec2((id % side) * 5, id / side), 0);
		vec4 s2 = texelFetch(sTD2DInputs[0], ivec2((id % side) * 5 + 2, id / side), 0);
		vec4 l0 = texelFetch(sTD2DInputs[1], ivec2((id % side) * 3, id / side), 0);
		bool hot = s2.w > uHot.x || (uHot.y > 0.0 && dot(l0.rgb, vec3(0.2126, 0.7152, 0.0722)) > uHot.y);
		o = vec4(s0.xyz, hot && l0.a > 0.01 ? 1.0 : 0.0);
	}
	TDImageStoreOutput(0, ivec3(g, 0), o);
}
'''
GRID_IN_EXPR = ("(lambda r, p: '/project1/effectors/grid/grid_field' if r is not None else p.op('mask_default').path)"
                "(op('/project1/effectors/grid/grid_field'), me.parent())")


def _grid(c):
    """Wave 3 SA5 / SA21 plumbing: hot_pts (cloud TOP of hot / emissive points; cooks only while the grid pulls it),
    grid_in (Select TOP of the shared grid field), aux_src (mask or grid) on input 2 of update / look / probes, and the
    grid section of lane E's eff_consumer.glsl (px_gridsec). px_rt._grid_wire switches it per compiled stack."""
    _text(c, 'px_gridsec', _logic()['grid_section'](_read(os.path.join(GLSL, 'eff_consumer.glsl'))),
          comment='Shared voxel grid accessors (cut from builders/glsl/eff_consumer.glsl, lane E, read only).')
    hs = "max(8, int(-(-(min(%s, parent().par.Hotmax.eval()) ** 0.5) // 1)))" % _CH0.format('eng_info', 'count')
    hp = _compute(c, 'hot_pts', 'hot_compute', HOT_PTS, hs, hs, 'rgba32float',
                  'Hot / emissive points of the state (stride sampled) = the px_hot cloud of the shared grid.')
    _wire(c.op('update'), hp, 0)
    _wire(c.op('look'), hp, 1)
    _vecs(hp, [('uHot', [PP + 'Hotthr', PP + 'Hotemit',
                         'max(1.0, -(-%s // float(max(1, me.par.resolutionw.eval() * me.par.resolutionh.eval()))))'
                         % _CH0.format('eng_info', 'count'), _CH0.format('eng_info', 'count')])])
    gi = _mk(c, selectTOP, 'grid_in')
    _expr(gi.par.top, GRID_IN_EXPR)
    gi.comment = 'The shared voxel grid field (/project1/effectors/grid/grid_field), or a stand-in.'
    ax = _mk(c, switchTOP, 'aux_src')
    _wire(c.op('mask_src'), ax, 0)
    _wire(gi, ax, 1)
    ax.par.index = 0
    ax.comment = 'Input 2 of update / look: the mask (v2) or the grid field (grid modules; px_rt._grid_wire).'
    for nm in ('update', 'look', 'update_probe', 'colour_probe'):
        _wire(ax, c.op(nm), 2)


TOP_USED = ("1 if {'top', 'image'} & {parent().par.Amode.eval(), parent().par.Bmode.eval(), "
            "parent().par.Actormode.eval()} else 0")


PROJ_ON = "parent().par.Proj.eval() != 'perspective'"


def _proj(c):
    """Wave 4 K26 dome / 360 output: render + srender become cube maps (face Projface) while Proj is fisheye /
    equirect; proj_render / proj_srender (Projection TOP: cube map -> fisheye (Projfov, Projtilt) or equirectangular,
    Resx x Resy) -> pr_render / pr_srender switches feed sw_render and layers. Perspective = the old wiring through a
    pass-through switch (diff 0)."""
    out = {}
    for nm in ('render', 'srender'):
        r = c.op(nm)
        _expr(r.par.rendermode, "'cubemap' if %s else 'render2d'" % PROJ_ON)
        _expr(r.par.resolutionw, '(int(parent().par.Projface) if %s else int(parent().par.Resx))' % PROJ_ON)
        _expr(r.par.resolutionh, '(int(parent().par.Projface) if %s else int(parent().par.Resy))' % PROJ_ON)
        pj = _mk(c, projectionTOP, 'proj_' + nm)
        _wire(r, pj, 0)
        _expr(pj.par.input, "'cubemap' if %s else 'equirectangular'" % PROJ_ON)   # off: a 2D input, no error
        _expr(pj.par.output, "'equirectangular' if parent().par.Proj.eval() == 'equirect' else 'fisheye'")
        _expr(pj.par.fov, PP + 'Projfov')
        _expr(pj.par.rx, PP + 'Projtilt')
        pj.par.outputresolution = 'custom'
        _expr(pj.par.resolutionw, PP + 'Resx')
        _expr(pj.par.resolutionh, PP + 'Resy')
        pj.par.format = 'rgba16float'
        pj.comment = 'K26: cube map -> fisheye / equirect (Proj).'
        sw = _switch(c, 'pr_' + nm, r, pj, PROJ_ON, 'K26: %s as is, or its fisheye / equirect projection.' % nm)
        out[nm] = sw
    sr = c.op('sw_render')
    _wire(out['render'], sr, 0)
    _wire(out['srender'], sr, 2)
    lay = c.op('layers')
    for k, i in enumerate(lay.inputs):
        if i.name in out:
            _wire(out[i.name], lay, k)
    return out


def _sound(c):
    """Wave 4 K34 data -> sound, in its own COMP `sound` (parked unless Soundon, px_rt.on_value): snd_stats (compute,
    64 x 64 block sums of the state) -> snd_avg (Analyze average, 1 x 1) -> snd_chop (TOP to CHOP) -> snd_lag ->
    3 Audio Oscillators (drone: mean height, shimmer: mean speed, noise: dissolved fraction; px_logic.sound_freqs) ->
    snd_mix (add) -> snd_out (x Soundvol) -> snd_dev (Audio Device Out: the DEFAULT output device, active = Soundon,
    cookalways off). Nothing reads an audio input; nothing routes a mic to the speakers."""
    sc = _mk(c, baseCOMP, 'sound')
    sc.comment = 'K34: the cloud as sound (off by default; default output device only).'
    sel = _mk(sc, selectTOP, 'snd_state')
    sel.par.top = '../update'
    st = _compute(sc, 'snd_stats', 'snd_stats_compute', _read(os.path.join(GLSL, 'px_sound.glsl')), '64', '64',
                  'rgba32float', 'Block sums: speed, dissolve, height, count.')
    _wire(sel, st, 0)
    _vecs(st, [('uSn', ("float(op('../eng_info')['count'][0])", "float(op('../eng_info')['side'][0])",
                        "float(op('../eng_g')['y'][7])", "float(op('../eng_g')['w'][7])"))])
    av = _mk(sc, analyzeTOP, 'snd_avg')
    _wire(st, av, 0)
    av.par.op = 'average'
    if getattr(av.par, 'outputresolution', None) is not None:
        av.par.format = 'rgba32float'
    ch = _mk(sc, toptoCHOP, 'snd_chop')
    ch.par.top = 'snd_avg'
    if getattr(ch.par, 'downloadtype', None) is not None:
        ch.par.downloadtype = 'delayed'               # next-frame read: no GPU stall
    lag = _mk(sc, lagCHOP, 'snd_lag')
    _wire(ch, lag, 0)
    lag.par.lag1 = lag.par.lag2 = 0.15
    m = "op('snd_lag')"
    spd = "({0}['r'][0] / max({0}['a'][0], 1e-6))".format(m)
    dis = "min(max({0}['g'][0] / max({0}['a'][0], 1e-6), 0.0), 1.0)".format(m)
    hgt = "min(max({0}['b'][0] / max({0}['a'][0], 1e-6), -1.0), 1.0)".format(m)
    x = "min(max(%s / max(parent(2).par.Soundspeed.eval(), 1e-6), 0.0), 1.0)" % spd
    pitch = 'parent(2).par.Soundpitch.eval()'
    oscs = [('osc_drone', 'sin', '55.0 * %s * 2.0 ** (1.0 + %s)' % (pitch, hgt),
             '0.5 * parent(2).par.Sounddrone.eval() * (1.0 - %s)' % dis),
            ('osc_shimmer', 'tri', '220.0 * %s * (1.0 + 3.0 * %s)' % (pitch, x),
             '0.3 * parent(2).par.Soundshimmer.eval() * %s' % x),
            ('osc_noise', 'whitenoise', '440.0', '0.3 * parent(2).par.Soundnoise.eval() * %s' % dis)]
    mix = _mk(sc, mathCHOP, 'snd_mix')
    for k, (nm, wt, fq, amp) in enumerate(oscs):
        o = _mk(sc, audiooscillatorCHOP, nm)
        o.par.wavetype = wt
        _expr(o.par.frequency, fq)
        _expr(o.par.amp, amp)
        mix.inputConnectors[k].connect(o)
    mix.par.chopop = 'add'
    out = _mk(sc, mathCHOP, 'snd_out')
    _wire(mix, out, 0)
    _expr(out.par.gain, 'parent(2).par.Soundvol.eval()')
    dev = _mk(sc, audiodeviceoutCHOP, 'snd_dev')
    _wire(out, dev, 0)
    dev.par.cookalways = False
    _expr(dev.par.active, 'bool(parent(2).par.Soundon.eval())')
    dev.comment = 'Default output device only (built-in speakers); active = Soundon.'
    sc.allowCooking = bool(c.par.Soundon.eval()) if getattr(c.par, 'Soundon', None) is not None else False
    try:
        op('/jazib_mcp/handlers').module.layout_stages(sc, [
            {'title': 'Stats', 'role': 'process', 'ops': ['snd_state', 'snd_stats', 'snd_stats_compute', 'snd_avg',
                                                          'snd_chop', 'snd_lag'],
             'body': 'State -> block sums -> average -> CHOP (speed, dissolve, height, count).'},
            {'title': 'Synth + out', 'role': 'output', 'ops': ['osc_drone', 'osc_shimmer', 'osc_noise', 'snd_mix',
                                                               'snd_out', 'snd_dev'],
             'body': 'Drone = height, shimmer = speed, noise = dissolve; x Soundvol; default output device.'}],
            True, arrange='mixed')
    except Exception:
        pass
    return sc


def _points_src(c):
    """Wave 3 K19 / K28: source mode `top` (A / B / actor): any TOP of points on input 2 of `source` (shared with the
    depth input: depth OR top). Pointstop (a TOP par) wins, else the COMP input in_xyz (named to sort after in_video:
    existing COMP input indices unchanged), else a 1x1 empty stand-in."""
    ix = _mk(c, inTOP, 'in_xyz')
    ix.comment = 'Points TOP (rgb = xyz, a > 0.5 valid) for Amode / Bmode / Actormode top (or the Pointstop par).'
    pd = _constant(c, 'points_default', 1, 1, 'rgba32float', (0, 0, 0, 0), 'No points TOP: no points.')
    imf = _mk(c, moviefileinTOP, 'img_file')
    _expr(imf.par.file, "parent().par.Imagefile.eval() if hasattr(parent().par, 'Imagefile') else ''")
    imf.comment = 'Imagefile (wave 4 K27 image relief) when no Pointstop.'
    ps = _mk(c, selectTOP, 'pts_sel')
    _expr(ps.par.top, "(lambda t, cn, f: t.path if t is not None else ('img_file' if f else ('in_xyz' if cn else "
          "'points_default')))(parent().par.Pointstop.eval(), %s, getattr(parent().par, 'Imagefile', None) and "
          "parent().par.Imagefile.eval())" % CONNECTED.format('in_xyz'))
    ps.comment = 'Pointstop, else Imagefile, else in_xyz, else empty.'
    sw = _mk(c, switchTOP, 'src_aux')
    _wire(c.op('in_depth_pack'), sw, 0)
    _wire(ps, sw, 1)
    _expr(sw.par.index, TOP_USED)
    sw.comment = 'Source input 2: depth (in_depth_pack) or the points TOP (mode top).'
    _wire(sw, c.op('source'), 2)


def _atlas(c):
    """Wave 3 K21 / SA35 sprites glyph / dab / atlas: new sprite MAT texts, sampler sAtlas (Atlastop or a white
    stand-in) on both sprite MATs, uPv.z = the glyph cycle clock."""
    _text(c, 'pmat_vertex', _read(os.path.join(GLSL, 'px_vert.glsl')))
    _text(c, 'pmat_pixel', _read(os.path.join(GLSL, 'px_pixel.glsl')))
    wd = _constant(c, 'atlas_default', 4, 4, 'rgba8fixed', (1, 1, 1, 1), 'No atlas TOP: white cells.')
    at = _mk(c, selectTOP, 'atlas_src')
    _expr(at.par.top, "(lambda t: t.path if t is not None else 'atlas_default')(parent().par.Atlastop.eval())")
    at.comment = 'Sprite atlas (Atlastop) or white.'
    for nm in ('pmat', 'pmat_prev'):
        m = c.op(nm)
        if m is None:
            continue
        m.seq.sampler.numBlocks = max(int(m.seq.sampler.numBlocks), 4)
        m.par.sampler3name = 'sAtlas'
        m.par.sampler3top = 'atlas_src'
        m.par.sampler3filter = 'linear'
        _expr(m.par.vec0valuez, 'absTime.seconds * {}Glyphrate'.format(PP))


def _camera(c):
    """Wave 3 Camera page (K24 / TC-36): cam_rig_logic in a Text DAT; pcam (and the preview camera) take rx / rz
    from eng_cam too (rotate order xyz = cam_row). Orbit mode keeps rx = rz = 0: the v2 camera exactly."""
    _text(c, 'cam_rig', _read(CAMRIG_FILE), comment='Camera rigs (builders/cam_rig_logic.py, read only).')
    for nm, mul in (('pcam', ''), ('pv_cam', '')):
        cam = c.op(nm)
        if cam is None:
            continue
        cam.par.rord = 'xyz'
        for k in ('rx', 'rz'):
            _expr(getattr(cam.par, k), "op('eng_cam')['{}']".format(k))


WAVE2_STEPS = ('texts', 'engine', 'stages', 'post', 'geo', 'lines', 'camera', 'grid', 'finish')


def wave2_upgrade(step, parent_path='/project1/lab', name=NAME):
    """Bring an existing PX (v2 + splats) to wave 2 without a rebuild, ONE step per exec (T-146 / T-152; main: un-park
    + 2 frames first). texts: pars + logic / rt / GLSL texts; engine: new engine CHOPs + eff_in; stages: arrays +
    palette on update / look / probes + recompile (probe swap 3 frames later); post: bloom v2 + haze; geo: Geo stage;
    lines: PX_lines inside + sw_lines; finish: watchers, builtins, layout. Sorter untouched (T-124)."""
    Lg = _logic()
    c = op(parent_path).op(name)
    c.allowCooking = True
    rtm = c.op('px_rt').module
    out = {'step': step}
    if step == 'texts':
        _close_window(c)
        _pars(c, Lg['CORE_PAGES'])
        for _pg, pars in Lg['CORE_PAGES']:             # menus that grew (Amode / Actormode top, ...): new entries
            for nm, style, _d, o in pars:
                p = getattr(c.par, nm, None)
                if style == 'Menu' and p is not None and list(p.menuNames) != list(o['names']):
                    p.menuNames, p.menuLabels = o['names'], o['labels']
        st_ = rtm.stack(c)                                 # module menus too (new attributes, modes)
        for inst in st_:
            for nm, style, _d, o in Lg['instance_par_specs'](inst):
                p = getattr(c.par, nm, None)
                if style == 'Menu' and p is not None and list(p.menuNames) != list(o['names']):
                    p.menuNames, p.menuLabels = o['names'], o['labels']
        _text(c, 'px_logic', _read(LOGIC_FILE))
        _text(c, 'px_rt', _read(RT_FILE))
        _text(c, 'px_lib', _read(os.path.join(GLSL, 'px_common.glsl')))
        _text(c, 'px_modules', _read(os.path.join(GLSL, 'px_modules.glsl')))
        _text(c, 'splat_logic', _read(SPLAT_FILE))     # W1-E geo_patch / resolve_lights (loaders unchanged)
        _text(c, 'px_tmpl_update', _read(os.path.join(GLSL, 'px_update.glsl')))     # wave 3 markers (echoes)
        _text(c, 'px_tmpl_colour', _read(os.path.join(GLSL, 'px_colour.glsl')))
        _text(c, 'source_compute', Lg['source_text'](_read(os.path.join(GLSL, 'px_common.glsl')),
                                                     _read(os.path.join(GLSL, 'px_source.glsl'))))
        _w2_texts(c)
        out['pars'] = len(c.customPars)
    elif step == 'engine':
        for nm, key, cm in ENG_W2:
            _script_chop(c, nm, key, cm)
        _shared_eff(c)
        val = c.op('px_values')
        for nm in ('Geoon', 'Echoes'):
            if nm not in val.par.pars.eval().split():
                val.par.pars = val.par.pars.eval() + ' ' + nm
    elif step == 'stages':
        lk = c.op('look')
        for nm in ('update', 'look', 'update_probe', 'colour_probe'):
            _arrays(c.op(nm), STAGE_ARRAYS)
        for o in (lk, c.op('colour_probe')):
            _bind_pal(o)
        rtm.mark_all(c)
        rtm.stack_changed(c)
        out['status'] = c.par.Status.eval()
    elif step == 'post':
        _bloom_v2(c, c.op('glow_in'))
        _haze(c)
    elif step == 'geo':
        out['notes'] = _geo(c)
    elif step == 'lines':
        out['lines'] = str(_lines(c))[:200]
    elif step == 'camera':
        _camera(c)
        _points_src(c)
        _atlas(c)
    elif step == 'grid':
        _grid(c)
        rtm.stack_changed(c)
    elif step == 'proj':                             # wave 4 K26 (perspective = pass-through)
        out['proj'] = sorted(_proj(c))
    elif step == 'sound':                            # wave 4 K34 (parked unless Soundon)
        _sound(c)
        val = c.op('px_values')
        if 'Soundon' not in val.par.pars.eval().split():
            val.par.pars = val.par.pars.eval() + ' Soundon'
    elif step == 'finish':
        _engine_callbacks(c, rtm)
        rtm.install_builtins(c)
        rtm.mark_all(c)
        out['relayout'] = relayout(parent_path, name)
    out['errors'] = len([o for o in c.findChildren(maxDepth=1) if o.errors()])
    return out


def perf_upgrade(parent_path='/project1/lab', name=NAME):
    """Bring an existing PX COMP to the T-143 engine without a full build (the sorter is not touched, T-124): new
    px_rt / px_logic text, engine CHOPs (clock flag, eng_gs / eng_ez), source uniforms, callbacks."""
    Lg = _logic()
    c = op(parent_path).op(name)
    _pars(c, Lg['CORE_PAGES'])                    # new core pars only (values kept)
    _text(c, 'px_logic', _read(LOGIC_FILE))
    rt = _text(c, 'px_rt', _read(RT_FILE))
    for nm, key in ENG_KEYS:
        o = c.op(nm)
        _script_chop(c, nm, key, o.comment if o is not None else 'engine rows (%s)' % key, clock=(key == 'g'))
    _arrays(c.op('source'), SRC_ARRAYS)
    _text(c, 'post_compute', _read(os.path.join(GLSL, 'px_post.glsl')))
    _post_clock(c.op('post'))
    _expr(c.op('render').par.geometry, RENDER_GEO)
    for nm in ('trail_blank', 'trail', 'post'):   # Resx / Resy, not op('render').width: reading a TOP's size cooks it
        _expr(c.op(nm).par.resolutionw, PP + 'Resx')   # (T-143: the sprite render kept cooking under splats)
        _expr(c.op(nm).par.resolutionh, PP + 'Resy')
    _wire(c.op('srender'), c.op('sw_render'), 2)
    _expr(c.op('sw_render').par.index, SW_RENDER)
    _engine_callbacks(c, rt.module)
    return {'comp': c.path, 'frame_modes': dict((nm, c.op(nm).par.Frame.mode.name) for nm, _k in ENG_KEYS)}


SPLAT_AA_E = PP + 'Splataa.eval()'                # srender MSAA (perf wave 27 Oct)


def perf27_upgrade(parent_path='/project1/lab', name=NAME):
    """Perf wave 27 Oct (b3) on an existing PX, no rebuild: the new Look par Splataa (srender MSAA, default 1x) and
    Sorteveryn's new default 6 (was 2; only a value still at the old default moves), px_logic / px_rt text, the
    stored 'default' preset re-stored when it is the current one. Un-park >= 2 frames before (T-146); panel() after,
    in its own exec."""
    c = op(parent_path).op(name)
    _pars(c, _logic()['CORE_PAGES'])              # adds Splataa (default aa1); values of existing pars kept
    _text(c, 'px_logic', _read(LOGIC_FILE))
    _text(c, 'px_rt', _read(RT_FILE))
    _expr(c.op('srender').par.antialias, SPLAT_AA_E)
    c.op('srender').comment = ('Gaussian splats (sorted, premultiplied over). Cooks only when Render resolves to '
                               'splats. MSAA = Splataa (Look page, default 1x: vertex-bound, aa4 cost ~1.5 ms GPU '
                               'for no visible change).')
    se = c.par.Sorteveryn
    se.default = 6
    if se.mode == ParMode.CONSTANT and se.eval() == 2:
        se.val = 6
    out = {'Splataa': c.par.Splataa.eval(), 'Sorteveryn': se.eval(), 'aa': c.op('srender').par.antialias.eval()}
    if c.par.Presetname.eval() == REST_PRESET:
        rt = c.op('px_rt').module
        rt.store(c, REST_PRESET)
        out['stored'] = REST_PRESET
    return out


def _menu_logic():
    ns = {'__name__': 'menu_logic'}
    exec(_read(MENU_FILE), ns)
    return ns


def _menus(c):
    """Every PX name field a live dropdown (T-233): core specs + each module's effectors field with 'menu': True ->
    StrMenu with px_logic.menu_source, in place (values, expressions, page order kept; Sel's Int value -> its text).
    Idempotent. {par: 'converted' / 'source' / 'same'}."""
    Lg, ML = _logic(), _menu_logic()
    names = [n for _pg, pars in Lg['CORE_PAGES'] for n in Lg['menu_specs'](pars)]
    rtm = c.op('px_rt').module if c.op('px_rt') is not None else None
    for inst in (rtm.stack(c) if rtm is not None else []):
        names += Lg['menu_specs'](Lg['instance_par_specs'](inst))
    out = {}
    was = rtm._watchers(c, False) if rtm is not None else None   # T-143: no per-par watcher storm
    try:
        for n in names:
            r = ML['to_strmenu'](c, n, Lg['menu_source'](n))
            if r is not None:
                out[n] = r
    finally:
        if rtm is not None:
            rtm._watchers(c, was)
    return out


def oct28_upgrade(parent_path='/project1/lab', name=NAME):
    """28 Oct on an existing PX, no rebuild (user: "can u not have a drop down for these? and all" + "an option to
    change the render resolution and the hierarchy should follow it"): px_logic / px_rt text + the menu_logic DAT;
    every name field -> live dropdown in place (Presetname, Sel, Effname, Actorfollow, Camfollow, Vhlights,
    Geolights, M<uid>effectors); the Resolution menu before Resx (set to the item of the current Resx x Resy, else
    custom: the user's size is kept); px_values also watches Resolution / Resx / Resy; render_preview follows Resx /
    Resy (half). Values, presets (px_presets is never touched), expressions and page order kept. Controls window
    closed first (T-70 / T-231). Un-park >= 2 frames before (T-146), pane on /project1 (T-213); relayout() and
    panel() after, each in its own exec."""
    Lg = _logic()
    c = op(parent_path).op(name)
    c.allowCooking = True
    _close_window(c)
    pre = c.op('px_presets').numRows
    rx, ry = int(c.par.Resx.eval()), int(c.par.Resy.eval())
    _text(c, 'px_logic', _read(LOGIC_FILE))
    rt = _text(c, 'px_rt', _read(RT_FILE))
    _text(c, 'menu_logic', _read(MENU_FILE), comment='Live dropdown items (builders/menu_logic.py, T-233).')
    was = rt.module._watchers(c, False)
    try:
        _pars(c, Lg['CORE_PAGES'])                    # adds Resolution (end of its page)
        pg = c.par.Resx.page
        order = [t[0].tupletName for t in pg.parTuplets if t[0].tupletName != 'Resolution']
        order.insert(order.index('Resx'), 'Resolution')
        pg.sort(*order)
        c.par.Resolution.val = Lg['res_name'](rx, ry)
    finally:
        rt.module._watchers(c, was)
    val = c.op('px_values')
    have = val.par.pars.eval().split()
    val.par.pars = ' '.join(have + [n for n in VALUE_PARS.split() if n not in have])
    gk = c.op('geo_key')
    if gk is not None and gk.par.shadowtype.eval() == 'off':
        gk.par.shadowcasters = ''                    # '*' read as a wire from every op by the layout (28 Oct)
    rp = c.op('render_preview')
    _expr(rp.par.resolutionw, PREVIEW_W)
    _expr(rp.par.resolutionh, PREVIEW_H)
    out = {'menus': _menus(c), 'presets_rows': [pre, c.op('px_presets').numRows],
           'res': [c.par.Resolution.eval(), int(c.par.Resx.eval()), int(c.par.Resy.eval())],
           'errors': len([o for o in c.findChildren(maxDepth=1) if o.errors()])}
    return out


def _sort_page(pg, first):
    """Page order: tuplet names in `first` order (those present), the rest after in their order (T-234: tuplet names)."""
    have = [t[0].tupletName for t in pg.parTuplets]
    want = [n for n in first if n in have] + [n for n in have if n not in first]
    if want != have:
        pg.sort(*want)
        return True
    return False


def presets28_upgrade(parent_path='/project1/lab', name=NAME):
    """28 Oct presets lane on an existing PX, no rebuild (user: "can u see if presets work and how do i re-arrange
    them ... i just put explode and the animation froze"):
    - px_logic / px_rt / px_modules text (only when different);
    - new core pars: Presets page Presetup / Presetdown / Newname / Presetrename / Presetsort (after Morphto), Drive
      page Trigauto / Trigautowhich (after Trigdecay; 0 = off);
    - auto progress pars (auto Off, rate 0.1) on every explode / dissolve_noise / dissolve_gradient page, after progress:
      the user's stack keeps its behaviour;
    - preset rows: ONLY the v1 looks whose effectors were never stored (px_logic.V1_FIX_PRESETS: hand_push_cloud,
      lattice_collapse, ember_splat, ember_splat (splats)) get them; every other row, the row order and the count
      stay as they are;
    - the stack recompiles once when the module code changed.
    Idempotent: a second run returns changed = []. Un-park first (T-146), pane on /project1 (T-213); refresh_panel after."""
    import json as _json
    Lg = _logic()
    c = op(parent_path).op(name)
    c.allowCooking = True
    _close_window(c)
    t = c.op('px_presets')
    names0 = [t[r, 0].val for r in range(1, t.numRows)]
    changed = []
    for dat, path in (('px_logic', LOGIC_FILE), ('px_rt', RT_FILE), ('px_modules', os.path.join(GLSL, 'px_modules.glsl'))):
        txt = _read(path)
        if c.op(dat).text != txt:
            _text(c, dat, txt)
            changed.append(dat)
    rt = c.op('px_rt').module
    was = rt._watchers(c, False)
    try:
        pars0 = set(p.name for p in c.customPars)
        _pars(c, Lg['CORE_PAGES'])
        for pg_name, pars in Lg['CORE_PAGES']:
            if pg_name in ('Presets', 'Drive'):
                pg = next(p for p in c.customPages if p.name == pg_name)
                if _sort_page(pg, [n for n, _s, _d, _o in pars]):
                    changed.append('order ' + pg_name)
        st = rt.stack(c)
        rt._sync_pages(c, st)
        newpars = sorted(set(p.name for p in c.customPars) - pars0)
        if newpars:
            changed.append('pars ' + ' '.join(newpars))
        for inst in st:
            if inst['type'] in Lg['AUTO_TYPES']:
                pg = next((p for p in c.customPages if p.name == Lg['page_name'](inst)), None)
                if pg is not None and _sort_page(pg, [n for n, _s, _d, _o in Lg['instance_par_specs'](inst)]):
                    changed.append('order ' + pg.name)
    finally:
        rt._watchers(c, was)
    had = c.op('px_autoguard') is not None and c.op('px_autoguard').text == AUTOGUARD
    _autoguard(c)
    if not had:
        changed.append('px_autoguard')
    fixed = []
    for r in range(1, t.numRows):
        nm = t[r, 0].val
        if nm in Lg['V1_FIX_PRESETS']:
            snap, ch = Lg['fix_v1_preset'](nm, _json.loads(t[r, 1].val))
            if ch:
                t[r, 1] = Lg['preset_dumps'](snap)
                fixed.append(nm)
    if fixed:
        changed.append('presets ' + ', '.join(fixed))
    if 'px_modules' in changed or 'px_logic' in changed:
        rt.stack_changed(c)
    names1 = [t[r, 0].val for r in range(1, t.numRows)]
    return {'changed': changed, 'presets': [len(names0), len(names1)], 'same_order': names0 == names1,
            'errors': len([o for o in c.findChildren(maxDepth=1) if o.errors()])}


def beatsync28_upgrade(parent_path='/project1/lab', name=NAME):
    """28 Oct phase A on an existing PX, no rebuild (beat sync + setlist, docs/builds/px.md "28 Oct: beat sync +
    setlist"). Runs presets28_upgrade first (idempotent: texts, pars, page order, autoguard, v1 preset fix), then:
    - new core pars (via the CORE_PAGES specs): Drive Trigsource / Trigbeats / Audiosrc (default
      /project1/lab/AU_features) / Beatsync (off); Presets Next / Prev / Cue / Go / Transition / Transcurve / Current
      (read only) / Cueindex / Setlist (DAT, default px_setlist) / Setlistfill;
    - the px_setlist table (header only = the presets order), px_values also watches Cueindex;
    - Current shows the stored position. Presets are never touched (count, order, every row kept: checked).
    Beatsync off + Trigsource manual = the old behaviour exactly. Idempotent: a second run returns changed = [].
    Un-park first (T-146), pane on /project1 (T-213); relayout() and zkit refresh_panel after, each in its own exec."""
    c = op(parent_path).op(name)
    c.allowCooking = True
    t = c.op('px_presets')
    rows0 = [[t[r, 0].val, t[r, 1].val] for r in range(1, t.numRows)]
    r28 = presets28_upgrade(parent_path, name)
    changed = list(r28.get('changed', []))
    if c.op('px_setlist') is None:
        _table(c, 'px_setlist', ['name'], SETLIST_NOTE)
        changed.append('px_setlist')
    sp = c.par.Setlist
    if sp.mode == ParMode.CONSTANT and sp.eval() is None and str(sp.val) == 'px_setlist':
        sp.val = sp.default = './px_setlist'        # a bare name resolved as PX's sibling (T-244)
        changed.append('Setlist ./px_setlist')
    val = c.op('px_values')
    have = val.par.pars.eval().split()
    miss = [n for n in VALUE_PARS.split() if n not in have]
    if miss:
        val.par.pars = ' '.join(have + miss)
        changed.append('px_values ' + ' '.join(miss))
    rt = c.op('px_rt').module
    nm, _pr = rt.setlist(c)
    rt._set_current(c, nm, rt._cue_pos(c))
    rows1 = [[t[r, 0].val, t[r, 1].val] for r in range(1, t.numRows)]
    v1 = set(_logic()['V1_FIX_PRESETS'])
    kept = [a for a, b in zip(rows0, rows1) if a[0] not in v1] == [b for b in rows1 if b[0] not in v1]
    return {'changed': changed, 'presets': [len(rows0), len(rows1)], 'presets_kept': kept and
            [a[0] for a in rows0] == [b[0] for b in rows1],
            'setlist': len(nm), 'errors': len([o for o in c.findChildren(maxDepth=1) if o.errors()])}


NOTES_COLS = ['frame', 'kind', 'text']
NOTES_NOTE = ('px_notes (phase B): what a recall / morph could not apply (pars, module types, effectors, files), size '
              'clamps, copy fix-ups, "2 PX cooking". Newest last, 200 rows max. Plain table: clear it any time.')


def _clamp_exprs(c):
    """Phase B hard size limits: every expression of PX's own ops (and PX_lines' ops) that reads a size par
    (Resx / Resy / Projface / Geoenvres; PX_lines Maxseg) reads it through its clamp (px_logic.clamp_expr). The par
    keeps the user's value. Idempotent: -> ['op:par' changed]."""
    Lg = _logic()
    pl = c.op('PX_lines')
    done = []
    for o in [c] + list(c.findChildren(maxDepth=3)):
        pp_ = o.parent().path if o.parent() is not None else ''
        rules = 'px' if pp_ == c.path else ('lines' if (pl is not None and pp_ == pl.path) else None)
        if rules is None:
            continue
        for p in o.pars():
            try:
                if p.mode != ParMode.EXPRESSION or 'parent().par.' not in p.expr:
                    continue
                e2 = Lg['clamp_expr'](p.expr, rules)
                if e2 != p.expr:
                    p.expr = e2
                    done.append('%s:%s' % (o.path[len(c.path):] or '.', p.name))
            except Exception:
                continue
    return done


def _logic_spec_label(name):
    for _pg, pars in _logic()['CORE_PAGES']:
        for n, _st, _d, o in pars:
            if n == name:
                return o.get('label', n)
    return None


def _strmenu_from_menu(c, name, source):
    """A static Menu par -> StrMenu with a live menuSource, in place (value = the item name, default, label, page
    position, help kept). menu_logic.to_strmenu does Str / Int; this is the Menu case (phase B Addtype).
    -> 'converted', 'source', 'same' or None."""
    mpar = getattr(c.par, name, None)
    if mpar is None:
        return None
    if mpar.style == 'StrMenu':
        if mpar.menuSource != source:
            mpar.menuSource = source
            return 'source'
        return 'same'
    if mpar.style != 'Menu':
        return None
    page = mpar.page
    order = [t[0].tupletName for t in page.parTuplets]      # T-234: tuplet names
    keep = {'val': str(mpar.eval()), 'default': str(mpar.default), 'help': mpar.help, 'mode': mpar.mode,
            'expr': mpar.expr}
    mpar.destroy()                                   # a custom PAR (not an op: T-70 does not apply)
    q = page.appendStrMenu(name, label=_logic_spec_label(name) or name)[0]
    q.menuSource = source
    q.default = keep['default']
    q.val = keep['val']
    if keep['help']:
        q.help = keep['help']
    if getattr(keep['mode'], 'name', '') == 'EXPRESSION' and keep['expr']:
        q.expr = keep['expr']
        q.mode = keep['mode']
    page.sort(*order)
    return 'converted'


UPG_FILE = os.path.join(HERE, 'px.py')
UPG_STEPS = ('texts', 'menus', 'tables', 'done')
UPG_GAP = 3                                       # frames between two upgrade steps (T-249: never one frame)


def _ui_safe(c):
    """T-249 (b3 SIGBUS in the UI thread during an in-place upgrade): before touching a PX, take it off the screen.
    Closes every Window COMP inside it (controls, PX_lines controls) and floating viewers of its outputs, moves every
    network pane that shows the COMP, its inside or its parent's network one level up, turns the node viewer off.
    -> what to restore (plain data)."""
    out = {'viewer': bool(c.viewer), 'windows': [], 'panes': []}
    for w in c.findChildren(type=windowCOMP, maxDepth=3):
        try:
            if w.isOpen:
                w.par.winclose.pulse()
                out['windows'].append(w.path)
        except Exception:
            pass
    for o in [c] + list(c.findChildren(type=TOP, maxDepth=1)):
        try:
            o.closeViewer()
        except Exception:
            pass
    up = c.parent().parent() if c.parent() is not None and c.parent().parent() is not None else op('/')
    for pn in ui.panes:
        try:
            ow = pn.owner.path if pn.owner is not None else ''
            if ow == c.parent().path or ow == c.path or ow.startswith(c.path + '/'):
                pn.owner = up
                out['panes'].append(ow)
        except Exception:
            pass
    c.viewer = False
    out['current'] = bool(getattr(c, 'current', False))
    for o in [c] + list(c.findChildren(maxDepth=1)):   # T-251: nothing of it current / selected (the param UI
        try:                                            # follows the current op while its pars are rebuilt)
            o.current = False
            o.selected = False
        except Exception:
            pass
    c.allowCooking = True
    return out


def _presets_sig(c):
    """[rows, sha1 of the table, sha1 of every row except the 4 v1 looks presets28 fixes (V1_FIX_PRESETS), order]."""
    import hashlib
    t = c.op('px_presets')
    v1 = set(_logic()['V1_FIX_PRESETS'])
    rest = '\n'.join('%s\t%s' % (t[r, 0].val, t[r, 1].val if t[r, 0].val not in v1 else '') for r in range(1, t.numRows))
    return [t.numRows - 1, hashlib.sha1(t.text.encode()).hexdigest(), hashlib.sha1(rest.encode()).hexdigest()]


def _upg_later(parent_path, name, step, delay=UPG_GAP):
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_phaseB_step'](%r, %r, %r)"
        % (UPG_FILE, parent_path, name, step), delayFrames=delay, delayRef=op.TDResources)


def phaseB_upgrade(parent_path='/project1/lab', name=NAME):
    """28 Oct phase B on an existing PX, no rebuild (docs/builds/px.md "28 Oct: phase B"), UI-safe (T-249):
    this call only takes the PX off the screen (_ui_safe) and schedules the steps, each UPG_GAP frames after the last
    one, never in the frame of another change:
    1 texts  = beatsync28_upgrade (idempotent: px_logic / px_rt / px_modules texts, pars, page order, autoguard,
               setlist; recompiles only when module code changed);
    2 menus  = Stack page: Addtype static Menu -> the module browser dropdown (a custom PAR replaced, value kept),
               new Addafter / Solo / Unsolo, page order; Quality 'max' label, Count slider range;
    3 tables = px_notes table, size clamps on the expressions (_clamp_exprs, edited in place), instance_check (own
               hot-points row name, references of an earlier copy-paste come home);
    4 done   = node viewer as it was (windows stay closed: Opencontrols after refresh_panel); the result in
               storage 'px_upgrade'.
    Read it with phaseB_result(parent_path, name) in a LATER exec (>= 1 s). Presets are never touched (count + sha1
    checked). Idempotent: a second run reports changed = []. relayout() and zkit refresh_panel after, each in its
    own exec."""
    c = op(parent_path).op(name)
    prep = _ui_safe(c)
    c.store('px_upgrade', {'state': 'running', 'step': 'texts', 'start': absTime.frame, 'prep': prep,
                           'changed': [], 'presets0': _presets_sig(c)})
    _upg_later(parent_path, name, 'texts')
    return {'scheduled': UPG_STEPS, 'prep': prep, 'read': "phaseB_result(%r, name=%r)" % (parent_path, name)}


def phaseB_result(parent_path='/project1/lab', name=NAME):
    c = op(parent_path).op(name)
    return c.fetch('px_upgrade', None, search=False)


def _phaseB_work(c, parent_path, name, step, st):
    """One phase B step's work on c (texts / menus / tables); -> what changed. Shared by phaseB_upgrade and
    phaseC_upgrade (which runs these first)."""
    changed = []
    Lg = _logic()
    if step == 'texts':
        rb = beatsync28_upgrade(parent_path, name)
        changed += list(rb.get('changed', []))
    elif step == 'menus':
        rt = c.op('px_rt').module
        was = rt._watchers(c, False)
        try:
            r = _strmenu_from_menu(c, 'Addtype', Lg['menu_source']('Addtype'))
            if r in ('converted', 'source'):
                changed.append('Addtype ' + r)
            pars0 = set(p.name for p in c.customPars)
            _pars(c, Lg['CORE_PAGES'])
            newpars = sorted(set(p.name for p in c.customPars) - pars0)
            if newpars:
                changed.append('pars ' + ' '.join(newpars))
            pg = next(p for p in c.customPages if p.name == 'Stack')
            if _sort_page(pg, [n for n, _s, _d, _o in dict(Lg['CORE_PAGES'])['Stack']]):
                changed.append('order Stack')
            q = c.par.Quality
            ql = [x[1] for x in Lg['QUALITY']]
            if list(q.menuLabels) != ql:
                q.menuLabels = ql
                changed.append('Quality labels')
            if c.par.Count.normMax != Lg['COUNT_MAX']:
                c.par.Count.normMax = Lg['COUNT_MAX']
                changed.append('Count range')
        finally:
            rt._watchers(c, was)
    elif step == 'tables':
        if c.op('px_notes') is None:
            _table(c, 'px_notes', NOTES_COLS, NOTES_NOTE)
            changed.append('px_notes')
        ce = _clamp_exprs(c)
        if ce:
            changed.append('clamps %d' % len(ce))
        rec0 = c.fetch('px_inst', None, search=False)
        st['instance'] = c.op('px_rt').module.instance_check(c)
        if rec0 != c.fetch('px_inst', None, search=False):
            changed.append('instance %s' % st['instance'].get('key'))
    return changed


def _upg_done(c, st):
    """Last step of an upgrade: node viewer as it was (windows stay closed: Opencontrols after refresh_panel, T-249),
    presets checked against the start, op errors counted."""
    prep = st.get('prep') or {}
    c.viewer = bool(prep.get('viewer', True))
    st['closed_windows'] = list(prep.get('windows', []))
    st['presets1'] = _presets_sig(c)
    p0, p1 = st.get('presets0') or [None] * 3, st['presets1']
    st['presets_kept'] = p0[:2] == p1[:2]                 # every row byte-identical
    st['presets_kept_but_v1_fix'] = p0[0] == p1[0] and p0[2:] == p1[2:]   # rows, order, all but v1 looks
    st['errors'] = len([o for o in c.findChildren(maxDepth=1) if o.errors()])
    st['state'] = 'done'
    st['end'] = absTime.frame


def _phaseB_step(parent_path, name, step):
    c = op(parent_path).op(name)
    st = dict(c.fetch('px_upgrade', {}, search=False) or {})
    changed = list(st.get('changed', []))
    try:
        c.allowCooking = True
        if step == 'done':
            _upg_done(c, st)
        else:
            changed += _phaseB_work(c, parent_path, name, step, st)
    except Exception as e:
        st['state'] = 'failed'
        st['error'] = '%s at %s: %s' % (type(e).__name__, step, e)
        c.viewer = bool((st.get('prep') or {}).get('viewer', True))
    st['changed'] = changed
    st['step'] = step
    c.store('px_upgrade', st)
    k = UPG_STEPS.index(step)
    if st['state'] == 'running' and k + 1 < len(UPG_STEPS):
        _upg_later(parent_path, name, UPG_STEPS[k + 1])


# ---------------------------------------------------------------------------------------------- phase C (28 Oct)
# Auto quality (px_auto layer), LOD by distance, sort only on change, external camera (docs/builds/px.md "28 Oct:
# phase C"). Manual wins: the auto layer never writes a user par.
AQ_AA_E = "'aa1' if op('px_auto')['aa'] > 0.5 else " + PP + "Splataa.eval()"     # srender MSAA: Splataa, or 1x on the AA step
FOV_E = "(lambda ch, f: f if ch is None else float(ch[0]))(op('eng_cam')['fov'], " + PP + "Fov.eval())"   # pcam fov
STRIDE_E = "1.0 / max(0.01, float(op('px_auto')['countf']))"                       # pmat uPv.x: sprite stride
KSIDE_WRAP = "(int(op('px_auto')['kside']) if op('px_auto')['countf'] < 1 else ({}))"   # sort_keys size
AUTO_CHANS = (('aa', 0.0), ('countf', 1.0), ('resf', 1.0), ('kside', 1.0))
GLSL_DATS_C = (('sortkey_compute', 'px_sortkey.glsl'), ('pmat_vertex', 'px_vert.glsl'), ('pmat_pixel', 'px_pixel.glsl'),
               ('post_compute', 'px_post.glsl'))
UPGC_STEPS = ('b_texts', 'b_menus', 'b_tables', 'c_texts', 'c_pars', 'c_ops', 'c_exprs', 'done')
UPGC_GAP = 20                                     # frames between phase C steps (T-250: 3 crashed b3 once)
UPGC_WAIT = 10                                    # frames to wait while a stack recompile / probe swap is pending


def _phaseC_ops(c):
    """px_auto (Constant CHOP: aa countf resf kside, written by px_rt on a step), px_perf (Perform CHOP fps + msec,
    viewer off: read only while Autoquality is on, so it cooks only then), sort_keys' uKs block. Idempotent."""
    changed = []
    a = c.op('px_auto')
    if a is None or a.OPType != 'constantCHOP':
        a = _mk(c, constantCHOP, 'px_auto')
        changed.append('px_auto')
    if int(a.seq.const.numBlocks) < len(AUTO_CHANS):
        a.seq.const.numBlocks = len(AUTO_CHANS)
    for i, (nm, v) in enumerate(AUTO_CHANS):
        q = getattr(a.par, 'const%dname' % i)
        if q.eval() != nm:
            q.val = nm
            getattr(a.par, 'const%dvalue' % i).val = v
            changed.append('px_auto ' + nm)
    a.comment = ('Auto quality step (phase C), written by px_rt only when the step changes: aa 1 = splat MSAA 1x, '
                 'countf = point fraction, resf = render resolution fraction (post / out1 stay Resx x Resy), kside = '
                 'sort-key texture side at countf. The user pars stay as set (Perf page Aqstate shows the step).')
    pf = c.op('px_perf')
    if pf is None or pf.OPType != 'performCHOP':
        pf = _mk(c, performCHOP, 'px_perf', viewer=False)
        changed.append('px_perf')
    for nm in ('fps', 'msec'):
        if not getattr(pf.par, nm).eval():
            getattr(pf.par, nm).val = True
            changed.append('px_perf ' + nm)
    pf.viewer = False
    pf.comment = ('Auto quality input: fps + msec (frame cook ms). px_rt reads it only while Autoquality is on (then '
                  'it cooks). Viewer off on purpose: a viewer would cook it every frame.')
    k = c.op('sort_keys')
    if k is not None:
        nb = int(k.seq.vec.numBlocks)
        names_ = [getattr(k.par, 'vec%dname' % i).eval() for i in range(nb)]
        if 'uKs' in names_:
            blk = names_.index('uKs')
        elif '' in names_:
            blk = names_.index('')
        else:
            k.seq.vec.numBlocks = nb + 1
            blk = nb
        if getattr(k.par, 'vec%dname' % blk).eval() != 'uKs':
            getattr(k.par, 'vec%dname' % blk).val = 'uKs'
            changed.append('uKs')
        for ax, e in (('x', "op('px_auto')['countf']"), ('y', "op('px_auto')['kside']")):
            q = getattr(k.par, 'vec%dvalue%s' % (blk, ax))
            if q.mode != ParMode.EXPRESSION or q.expr != e:
                _expr(q, e)
                changed.append('uKs.' + ax)
    return changed


def _phaseC_exprs(c):
    """The auto-quality layer in the render expressions + pcam's fov from eng_cam (external camera). Idempotent:
    -> ['op:par' changed]. Every new form reads the old value when px_auto is at full quality."""
    Lg = _logic()
    done = []

    def put(o, pname, e):
        q = getattr(o.par, pname, None)
        if q is not None and (q.mode != ParMode.EXPRESSION or q.expr != e):
            _expr(q, e)
            done.append('%s:%s' % (o.name, pname))
    sr = c.op('srender')
    if sr is not None:
        put(sr, 'antialias', AQ_AA_E)
    for o in c.findChildren(maxDepth=1):
        if o.name in Lg['AQ_RES_SKIP']:
            continue
        for q in o.pars():
            try:
                if q.mode != ParMode.EXPRESSION or 'me.parent().par.Res' not in q.expr:
                    continue
                e2 = Lg['aq_res_expr'](q.expr)
                if e2 != q.expr:
                    q.expr = e2
                    done.append('%s:%s' % (o.name, q.name))
            except Exception:
                continue
    k = c.op('sort_keys')
    if k is not None:
        for pn in ('resolutionw', 'resolutionh'):
            q = getattr(k.par, pn)
            if 'px_auto' not in (q.expr or ''):
                put(k, pn, KSIDE_WRAP.format(q.expr if q.mode == ParMode.EXPRESSION else str(q.eval())))
    pm = c.op('pmat')
    if pm is not None:
        put(pm, 'vec0valuex', STRIDE_E)
    pc_ = c.op('pcam')
    if pc_ is not None:
        put(pc_, 'fov', FOV_E)
    return done


def _phaseC_texts(c, one=False):
    """The phase C shader texts (sort keys, sprite MAT, post; splat MAT = adapter + BL's shader, re-patched for Geo)
    + px_logic / px_rt (written by the b_texts step already: checked again). Only DATs whose text differs. one=True
    (the staged upgrade): at most ONE DAT per call (one recompile per step, T-250), the caller repeats the step."""
    changed = []
    for dat, path in (('px_logic', LOGIC_FILE), ('px_rt', RT_FILE)):
        txt = _read(path)
        if c.op(dat) is not None and c.op(dat).text != txt:
            _text(c, dat, txt)
            changed.append(dat)
            if one:
                return changed
    for dat, fn in GLSL_DATS_C:
        txt = _read(os.path.join(GLSL, fn))
        d = c.op(dat)
        if d is not None and d.text != txt:
            d.text = txt
            changed.append(dat)
            if one:
                return changed
    sm = c.op('smat_glsl')
    if sm is not None:
        base = _read(os.path.join(GLSL, 'px_splat_adapter.glsl')) + _read(SPLAT_GLSL)
        sl, ad = c.op('splat_logic'), c.op('splat_geo_adapter')
        want = base
        if sl is not None and ad is not None and getattr(c.par, 'Geoon', None) is not None and c.par.Geoon.eval():
            want = sl.module.geo_patch(base, ad.text, True)
        if sm.text != want:
            sm.text = want
            changed.append('smat_glsl')
            c.op('px_rt').module.geo_sync(c)
    return changed


def _phaseC_pars(c):
    """Perf page (Autoquality, Aq*, Sortstill, Lod*) + Camera page Camsource / Camcomp (first on their page)."""
    Lg = _logic()
    changed = []
    rt = c.op('px_rt').module
    was = rt._watchers(c, False)
    try:
        pars0 = set(p.name for p in c.customPars)
        _pars(c, Lg['CORE_PAGES'])
        newpars = sorted(set(p.name for p in c.customPars) - pars0)
        if newpars:
            changed.append('pars ' + ' '.join(newpars))
        specs = dict(Lg['CORE_PAGES'])
        for pg_name in ('Camera', 'Perf'):
            pg = next((p for p in c.customPages if p.name == pg_name), None)
            if pg is not None and _sort_page(pg, [n for n, _s, _d, _o in specs[pg_name]]):
                changed.append('order ' + pg_name)
        q = getattr(c.par, 'Camcomp', None)
        if q is not None and q.style == 'StrMenu' and q.menuSource != Lg['menu_source']('Camcomp'):
            q.menuSource = Lg['menu_source']('Camcomp')
            changed.append('Camcomp menu')
    finally:
        rt._watchers(c, was)
    rt.mark_all(c)
    return changed


# Usecam alone (coordinator, 28 Oct: hand it to main first): phase B's steps, px_logic / px_rt, the Camera page
# Camsource / Camcomp, pcam fov from eng_cam. No Perf page, no shader / op / size-expression change; the new runtime is
# inert without those pars (Sortstill absent = the old sort rule, Autoquality absent = off, LOD rows 0).
UPGU_STEPS = ('b_texts', 'b_menus', 'b_tables', 'u_texts', 'u_pars', 'u_exprs', 'done')


def _perf_names():
    return set(n for n, _s, _d, _o in dict(_logic()['CORE_PAGES'])['Perf'])


def _usecam_texts(c):
    changed = []
    for dat, path in (('px_logic', LOGIC_FILE), ('px_rt', RT_FILE)):
        txt = _read(path)
        if c.op(dat) is not None and c.op(dat).text != txt:
            _text(c, dat, txt)
            changed.append(dat)
    return changed


def _usecam_pars(c):
    Lg = _logic()
    changed = []
    rt = c.op('px_rt').module
    was = rt._watchers(c, False)
    try:
        pars0 = set(p.name for p in c.customPars)
        _pars(c, [pg for pg in Lg['CORE_PAGES'] if pg[0] == 'Camera'])
        newpars = sorted(set(p.name for p in c.customPars) - pars0)
        if newpars:
            changed.append('pars ' + ' '.join(newpars))
        pg = next((p for p in c.customPages if p.name == 'Camera'), None)
        if pg is not None and _sort_page(pg, [n for n, _s, _d, _o in dict(Lg['CORE_PAGES'])['Camera']]):
            changed.append('order Camera')
    finally:
        rt._watchers(c, was)
    rt.mark_all(c)
    return changed


def _usecam_exprs(c):
    pc_ = c.op('pcam')
    if pc_ is not None and (pc_.par.fov.mode != ParMode.EXPRESSION or pc_.par.fov.expr != FOV_E):
        _expr(pc_.par.fov, FOV_E)
        return ['pcam:fov']
    return []


def _upgU_later(parent_path, name, step, delay=UPGC_GAP):
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_usecam_step'](%r, %r, %r)"
        % (UPG_FILE, parent_path, name, step), delayFrames=delay, delayRef=op.TDResources)


def usecam_upgrade(parent_path='/project1/lab', name=NAME):
    """External camera only (Camera page Camsource / Camcomp), UI-safe and staged like phaseC_upgrade (T-249 / T-250:
    _ui_safe, zkit panel parked, steps 20 frames apart, waits on a pending recompile swap). Read usecam_result() in a
    later exec; a second run returns changed = []. phaseC_upgrade later adds the rest (it repeats these, idempotent)."""
    c = op(parent_path).op(name)
    prep = _ui_safe(c)
    pn = c.op('controls')
    prep['panel'] = bool(pn.allowCooking) if pn is not None else None
    if pn is not None:
        pn.allowCooking = False
    c.store('px_upgradeU', {'state': 'running', 'step': UPGU_STEPS[0], 'start': absTime.frame, 'prep': prep,
                            'changed': [], 'presets0': _presets_sig(c)})
    _upgU_later(parent_path, name, UPGU_STEPS[0])
    return {'scheduled': UPGU_STEPS, 'prep': prep, 'read': "usecam_result(%r, name=%r)" % (parent_path, name)}


def usecam_result(parent_path='/project1/lab', name=NAME):
    return op(parent_path).op(name).fetch('px_upgradeU', None, search=False)


def _usecam_step(parent_path, name, step):
    global _PARS_SKIP
    _PARS_SKIP = _perf_names()                     # this exec's namespace only: phase B's _pars calls skip Perf too
    c = op(parent_path).op(name)
    st = dict(c.fetch('px_upgradeU', {}, search=False) or {})
    changed = list(st.get('changed', []))
    try:
        c.allowCooking = True
        pend = c.fetch('px_pending', None, search=False)
        if pend is not None and step != 'b_texts' and st.get('waits', 0) < 60:
            st['waits'] = st.get('waits', 0) + 1
            c.store('px_upgradeU', st)
            _upgU_later(parent_path, name, step, UPGC_WAIT)
            return
        if step.startswith('b_'):
            changed += _phaseB_work(c, parent_path, name, step[2:], st)
        elif step == 'u_texts':
            changed += _usecam_texts(c)
        elif step == 'u_pars':
            changed += _usecam_pars(c)
        elif step == 'u_exprs':
            changed += _usecam_exprs(c)
        elif step == 'done':
            _upg_done(c, st)
            pn = c.op('controls')
            if pn is not None and (st.get('prep') or {}).get('panel') is not None:
                pn.allowCooking = bool(st['prep']['panel'])
    except Exception as e:
        st['state'] = 'failed'
        st['error'] = '%s at %s: %s' % (type(e).__name__, step, e)
        c.viewer = bool((st.get('prep') or {}).get('viewer', True))
        pn = c.op('controls')
        if pn is not None and (st.get('prep') or {}).get('panel') is not None:
            pn.allowCooking = bool(st['prep']['panel'])
    st['changed'] = changed
    st['step'] = step
    c.store('px_upgradeU', st)
    k = UPGU_STEPS.index(step)
    if st['state'] == 'running' and k + 1 < len(UPGU_STEPS):
        _upgU_later(parent_path, name, UPGU_STEPS[k + 1])


def _upgC_later(parent_path, name, step, delay=UPGC_GAP):
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_phaseC_step'](%r, %r, %r)"
        % (UPG_FILE, parent_path, name, step), delayFrames=delay, delayRef=op.TDResources)


def phaseC_upgrade(parent_path='/project1/lab', name=NAME):
    """28 Oct phase C on an existing PX, no rebuild (docs/builds/px.md "28 Oct: phase C"), UI-safe and staged like
    phaseB_upgrade (T-249): this call only takes the PX off the screen (_ui_safe) and schedules the steps, each UPG_GAP
    frames after the last:
    b_texts / b_menus / b_tables = phase B's steps (idempotent; a PX that has phase B changes nothing there);
    c_texts = px_logic / px_rt + the shader texts (sort keys uKs map, splat adapter LOD, sprite LOD + float stride,
              post samples a smaller chain by uv); c_pars = Perf page + Camera Camsource / Camcomp;
    c_ops = px_auto, px_perf, sort_keys uKs; c_exprs = srender MSAA / render-chain sizes / sort_keys size / sprite
    stride read px_auto, pcam fov reads eng_cam; done = node viewer back, presets + errors checked.
    Read the result with phaseC_result() in a LATER exec. Idempotent: a second run reports changed = [].
    relayout() and zkit refresh_panel after, each in its own exec."""
    c = op(parent_path).op(name)
    prep = _ui_safe(c)
    pn = c.op('controls')                             # T-250: the zkit panel (zk_sync on every par) parked meanwhile
    prep['panel'] = bool(pn.allowCooking) if pn is not None else None
    if pn is not None:
        pn.allowCooking = False
    c.store('px_upgradeC', {'state': 'running', 'step': UPGC_STEPS[0], 'start': absTime.frame, 'prep': prep,
                            'changed': [], 'presets0': _presets_sig(c)})
    _upgC_later(parent_path, name, UPGC_STEPS[0])
    return {'scheduled': UPGC_STEPS, 'prep': prep, 'read': "phaseC_result(%r, name=%r)" % (parent_path, name)}


def phaseC_result(parent_path='/project1/lab', name=NAME):
    c = op(parent_path).op(name)
    return c.fetch('px_upgradeC', None, search=False)


def _phaseC_step(parent_path, name, step):
    c = op(parent_path).op(name)
    st = dict(c.fetch('px_upgradeC', {}, search=False) or {})
    changed = list(st.get('changed', []))
    again = False
    try:
        c.allowCooking = True
        pend = c.fetch('px_pending', None, search=False)
        if pend is not None and step != 'b_texts' and st.get('waits', 0) < 60:
            st['waits'] = st.get('waits', 0) + 1           # T-250: never change PX while a recompile swap is pending
            c.store('px_upgradeC', st)
            _upgC_later(parent_path, name, step, UPGC_WAIT)
            return
        if step.startswith('b_'):
            changed += _phaseB_work(c, parent_path, name, step[2:], st)
        elif step == 'c_texts':
            ch = _phaseC_texts(c, one=True)
            changed += ch
            again = bool(ch)                               # one shader DAT per step: repeat until none differs
        elif step == 'c_pars':
            changed += _phaseC_pars(c)
        elif step == 'c_ops':
            changed += _phaseC_ops(c)
        elif step == 'c_exprs':
            ce = _phaseC_exprs(c)
            if ce:
                changed.append('exprs %d' % len(ce))
            c.op('px_rt').module.mark_all(c)
        elif step == 'done':
            _upg_done(c, st)
            pn = c.op('controls')
            if pn is not None and (st.get('prep') or {}).get('panel') is not None:
                pn.allowCooking = bool(st['prep']['panel'])
    except Exception as e:
        st['state'] = 'failed'
        st['error'] = '%s at %s: %s' % (type(e).__name__, step, e)
        c.viewer = bool((st.get('prep') or {}).get('viewer', True))
        pn = c.op('controls')
        if pn is not None and (st.get('prep') or {}).get('panel') is not None:
            pn.allowCooking = bool(st['prep']['panel'])
    st['changed'] = changed
    st['step'] = step
    c.store('px_upgradeC', st)
    k = UPGC_STEPS.index(step)
    if st['state'] == 'running' and again:
        _upgC_later(parent_path, name, step)
    elif st['state'] == 'running' and k + 1 < len(UPGC_STEPS):
        _upgC_later(parent_path, name, UPGC_STEPS[k + 1])


REST_SCENE = 'smiley'                          # px_logic.SPLAT_SCENES key of the rest state (27 Oct)
REST_EFFECTORS = {'E1': {'tx': 0.3, 'sx': 0.35, 'sy': 0.35, 'sz': 0.35}, 'E2': {'tx': -0.3, 'ty': 0.1}}
REST_PRESET = 'default'


# Presetsource (28 Oct, user bug: "changing a preset also changes the pointcloud or splat file that i have imported"):
# px_logic / px_rt texts (looks skip the Source page while Presetsource is off) + the Presets-page toggle. UI-safe and
# staged like usecam_upgrade (T-249 / T-250 / T-251). Presets are never touched (byte-identical, checked in done).
UPGS_STEPS = ('s_texts', 's_pars', 'done')


def _presetsrc_pars(c):
    Lg = _logic()
    changed = []
    rt = c.op('px_rt').module
    was = rt._watchers(c, False)
    try:
        pars0 = set(p.name for p in c.customPars)
        _pars(c, [pg for pg in Lg['CORE_PAGES'] if pg[0] == 'Presets'])
        newpars = sorted(set(p.name for p in c.customPars) - pars0)
        if newpars:
            changed.append('pars ' + ' '.join(newpars))
        pg = next((p for p in c.customPages if p.name == 'Presets'), None)
        if pg is not None and _sort_page(pg, [n for n, _s, _d, _o in dict(Lg['CORE_PAGES'])['Presets']]):
            changed.append('order Presets')
    finally:
        rt._watchers(c, was)
    rt.mark_all(c)
    return changed


def _upgS_later(parent_path, name, step, delay=UPGC_GAP):
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_presetsrc_step'](%r, %r, %r)"
        % (UPG_FILE, parent_path, name, step), delayFrames=delay, delayRef=op.TDResources)


def presetsrc_upgrade(parent_path='/project1/lab', name=NAME):
    """Presetsource on an existing PX (docs/builds/px.md "28 Oct: Presetsource"), no rebuild: s_texts (px_logic /
    px_rt), s_pars (Presets page toggle Presetsource, default Off), done. _ui_safe first, zkit panel parked, steps
    UPGC_GAP frames apart, waits on a pending recompile swap. Read presetsrc_result() in a later exec; a second run
    reports changed = [] and presets_kept True."""
    c = op(parent_path).op(name)
    prep = _ui_safe(c)
    pn = c.op('controls')
    prep['panel'] = bool(pn.allowCooking) if pn is not None else None
    if pn is not None:
        pn.allowCooking = False
    c.store('px_upgradeS', {'state': 'running', 'step': UPGS_STEPS[0], 'start': absTime.frame, 'prep': prep,
                            'changed': [], 'presets0': _presets_sig(c)})
    _upgS_later(parent_path, name, UPGS_STEPS[0])
    return {'scheduled': UPGS_STEPS, 'prep': prep, 'read': "presetsrc_result(%r, name=%r)" % (parent_path, name)}


def presetsrc_result(parent_path='/project1/lab', name=NAME):
    return op(parent_path).op(name).fetch('px_upgradeS', None, search=False)


def _presetsrc_step(parent_path, name, step):
    c = op(parent_path).op(name)
    st = dict(c.fetch('px_upgradeS', {}, search=False) or {})
    changed = list(st.get('changed', []))
    prep = st.get('prep') or {}
    try:
        c.allowCooking = True
        pend = c.fetch('px_pending', None, search=False)
        if pend is not None and step != UPGS_STEPS[0] and st.get('waits', 0) < 60:
            st['waits'] = st.get('waits', 0) + 1
            c.store('px_upgradeS', st)
            _upgS_later(parent_path, name, step, UPGC_WAIT)
            return
        if step == 's_texts':
            changed += _usecam_texts(c)
        elif step == 's_pars':
            changed += _presetsrc_pars(c)
        elif step == 'done':
            _upg_done(c, st)
            pn = c.op('controls')
            if pn is not None and prep.get('panel') is not None:
                pn.allowCooking = bool(prep['panel'])
    except Exception as e:
        st['state'] = 'failed'
        st['error'] = '%s at %s: %s' % (type(e).__name__, step, e)
        c.viewer = bool(prep.get('viewer', True))
        pn = c.op('controls')
        if pn is not None and prep.get('panel') is not None:
            pn.allowCooking = bool(prep['panel'])
    st['changed'] = changed
    st['step'] = step
    c.store('px_upgradeS', st)
    k = UPGS_STEPS.index(step)
    if st['state'] == 'running' and k + 1 < len(UPGS_STEPS):
        _upgS_later(parent_path, name, UPGS_STEPS[k + 1])


# ---------------------------------------------------------------------------------------------- drop-in round (29 Oct)
# User (29 Oct): "make sure everythings independent ... they should work if copy pasted in another project". The
# grey reference lines into PX_pointfx1 were every effectors consumer -> eff_rows -> PX's hot-points row. Now: the hot
# row is #pub and ON only while a compiled module reads the grid (px_rt._hot_sync, on stack events + the first cook),
# eff_in reads eff_rows_pub only when a module names a #pub row, the splat sorter is primed once per session (the
# sgeo "pid(0)" warning in sprites mode). In place: indep_upgrade (staged, UI-safe, presets byte-identical).
UPGI_STEPS = ('i_texts', 'i_exprs', 'i_hot', 'done')


def _indep_exprs(c):
    e = c.op('eff_in')
    if e is not None and e.par.chops.mode == ParMode.EXPRESSION and e.par.chops.expr == EFF_IN_OLD:
        e.par.chops.expr = EFF_IN_EXPR
        return ['eff_in:chops']
    return []


def _indep_hot(c):
    rt = c.op('px_rt').module
    ert = rt._eff_rt()
    before = None
    hn = rt.hot_name(c)
    if ert is not None:
        before = next((dict(r) for r in ert.rows() if r['name'] == hn), None)
    rt._hot_sync(c, rt.hot_want(c))
    rt.mark_all(c)                                    # eff_use / eff_pub re-read on the next engine frame
    after = next((dict(r) for r in ert.rows() if r['name'] == hn), None) if ert is not None else None
    if before != after:
        return ['hot row %s: %s -> %s' % (hn, (before or {}).get('enabled'), (after or {}).get('enabled'))]
    return []


def _upgI_later(parent_path, name, step, delay=UPGC_GAP):
    run("ns = dict(globals()); exec(open(%r).read(), ns); ns['_indep_step'](%r, %r, %r)"
        % (UPG_FILE, parent_path, name, step), delayFrames=delay, delayRef=op.TDResources)


def indep_upgrade(parent_path='/project1/lab', name=NAME):
    """Drop-in round on an existing PX, no rebuild: i_texts (px_logic / px_rt), i_exprs (eff_in -> eff_rows_pub only
    when a module names a #pub row), i_hot (own hot row: on only while a compiled module reads the grid, tagged
    #pub), done. _ui_safe first, zkit panel parked, steps UPGC_GAP frames apart, waits on a pending recompile. Read
    indep_result() in a LATER exec; a second run reports changed = [] and presets_kept True."""
    c = op(parent_path).op(name)
    prep = _ui_safe(c)
    pn = c.op('controls')
    prep['panel'] = bool(pn.allowCooking) if pn is not None else None
    if pn is not None:
        pn.allowCooking = False
    c.store('px_upgradeI', {'state': 'running', 'step': UPGI_STEPS[0], 'start': absTime.frame, 'prep': prep,
                            'changed': [], 'presets0': _presets_sig(c)})
    _upgI_later(parent_path, name, UPGI_STEPS[0])
    return {'scheduled': UPGI_STEPS, 'prep': prep, 'read': "indep_result(%r, name=%r)" % (parent_path, name)}


def indep_result(parent_path='/project1/lab', name=NAME):
    return op(parent_path).op(name).fetch('px_upgradeI', None, search=False)


def _indep_step(parent_path, name, step):
    c = op(parent_path).op(name)
    st = dict(c.fetch('px_upgradeI', {}, search=False) or {})
    changed = list(st.get('changed', []))
    prep = st.get('prep') or {}

    def panel_back():
        pn = c.op('controls')
        if pn is not None and prep.get('panel') is not None:
            pn.allowCooking = bool(prep['panel'])
    try:
        c.allowCooking = True
        pend = c.fetch('px_pending', None, search=False)
        if pend is not None and step != UPGI_STEPS[0] and st.get('waits', 0) < 60:
            st['waits'] = st.get('waits', 0) + 1
            c.store('px_upgradeI', st)
            _upgI_later(parent_path, name, step, UPGC_WAIT)
            return
        if step == 'i_texts':
            changed += _usecam_texts(c)
        elif step == 'i_exprs':
            changed += _indep_exprs(c)
        elif step == 'i_hot':
            changed += _indep_hot(c)
        elif step == 'done':
            _upg_done(c, st)
            panel_back()
    except Exception as e:
        st['state'] = 'failed'
        st['error'] = '%s at %s: %s' % (type(e).__name__, step, e)
        c.viewer = bool(prep.get('viewer', True))
        panel_back()
    st['changed'] = changed
    st['step'] = step
    c.store('px_upgradeI', st)
    k = UPGI_STEPS.index(step)
    if st['state'] == 'running' and k + 1 < len(UPGI_STEPS):
        _upgI_later(parent_path, name, UPGI_STEPS[k + 1])


def splat_upgrade(parent_path='/project1/lab', name=NAME):
    """Splat lane (27 Oct) on an existing PX: new core pars, px_logic / px_rt text (splat looks + splat_showcase in the
    preset table, built by install_builtins) and the splat MAT text (footprint cap, Ascale). Un-park the COMP >= 2 frames before (T-146); rest_state() in a later exec
    (the DAT modules rebuild when they cook)."""
    c = op(parent_path).op(name)
    c.allowCooking = True
    _pars(c, _logic()['CORE_PAGES'])              # new core pars only (Splatmaxpx), values kept
    _text(c, 'px_logic', _read(LOGIC_FILE))
    _text(c, 'px_rt', _read(RT_FILE))
    _text(c, 'smat_glsl', _read(os.path.join(GLSL, 'px_splat_adapter.glsl')) + _read(SPLAT_GLSL))   # footprint cap, Ascale
    return {'comp': c.path, 'logic': len(c.op('px_logic').text), 'rt': len(c.op('px_rt').text),
            'smat': len(c.op('smat_glsl').text), 'Splatmaxpx': c.par.Splatmaxpx.eval()}


def rest_state(parent_path='/project1/lab', name=NAME):
    """The documented rest state (docs/builds/px.md "Rest state in main"): the builder's DEFAULT_STACK + E1 box / E2 null
    on the SmileyPinata splat scene, Render auto (-> splats), Look / Grade defaults, Presetname 'default' stored as a
    preset; built-in looks + their splat versions + splat_showcase installed. Each par is set once and only when it
    differs (T-164: a reset-then-set replays through the zkit two-way sync)."""
    Lg = _logic()
    c = op(parent_path).op(name)
    c.allowCooking = True
    rt = c.op('px_rt').module
    for r in list(rt.eff_table(c)):
        if r['name'] not in REST_EFFECTORS:
            rt.remove_effector(c, r['name'])
    have = [r['name'] for r in rt.eff_table(c)]
    for kind, nm, xf in DEFAULT_EFFECTORS:
        if nm not in have:
            rt.add_effector(c, kind, nm, {})
        o = c.op('effectors/' + nm)
        base = {'tx': 0, 'ty': 0, 'tz': 0, 'rx': 0, 'ry': 0, 'rz': 0, 'sx': 1, 'sy': 1, 'sz': 1}
        base.update(REST_EFFECTORS[nm])
        for k, v in base.items():
            p = getattr(o.par, k)
            if p.mode != ParMode.CONSTANT:
                p.mode = ParMode.CONSTANT
            if p.eval() != v:
                p.val = v
        rt.eff_page(o, {'Motion': 'none', 'Trail': 0, 'Glow': False})
    st, vals = [], {}
    for t, v in DEFAULT_STACK:
        st, uid = Lg['add_module'](st, t)
        for k, x in v.items():
            vals[Lg['par_name'](uid, k)] = x
        if Lg['MODULES'][t].get('eff'):
            vals[Lg['par_name'](uid, 'effectors')] = 'E1 E2'
    rt.sync_pages(c, st, vals)
    rt.write_stack(c, st)
    rt.stack_changed(c)
    rt.sync_pages(c, st, vals)
    core = dict(Lg['look_defaults']())
    core.update(Lg['SPLAT_SCENES'][REST_SCENE])
    core['Render'] = 'auto'
    core['Presetname'] = REST_PRESET
    for k, v in core.items():
        p = getattr(c.par, k, None)
        if p is None or p.readOnly:
            continue
        if p.mode != ParMode.CONSTANT:
            p.mode = ParMode.CONSTANT
        try:
            if p.eval() != v:
                p.val = v
        except Exception:
            pass
    rt.install_builtins(c)
    rt.store(c, REST_PRESET)
    rt.load(c)
    return {'stack': [[i['uid'], i['type']] for i in rt.stack(c)], 'effectors': [e['name'] for e in rt.eff_table(c)],
            'presets': c.op('px_presets').numRows - 1, 'status': c.par.Status.eval()}


def relayout(parent_path='/project1/lab', name=NAME):
    """Re-flow the COMP by STAGES (the perf ops are in Controls / 2 Engine) and lay out inside `sorter` (positions
    only: the sorter's config is never touched, T-124)."""
    c = op(parent_path).op(name)
    h = op('/jazib_mcp/handlers').module
    stages = []
    for s_ in STAGES:
        s2 = dict(s_)
        s2['ops'] = [n for n in s_['ops'] if c.op(n) is not None]
        if s2['ops']:
            stages.append(s2)
    _sd(c.op('stage_Other'))                     # an old plan's catch-all box (MAIN_AUDIT D2); every op has a stage now
    a = h.layout_stages(c, stages, True, arrange='mixed')
    b = h.cmd_layout(c.op('sorter').path, mode='flow')
    return {'stages': str(a)[:200], 'sorter': str(b)[:200]}


def bl_pointer(parent_path='/project1/lab', name='BL_splat_render'):
    """MAIN_AUDIT D4, superseded 29 Oct (drop-in): BL_splat_render's Splatfx is an optional COMP par (empty = off);
    this delegates to builders/splat_render.py indep_upgrade (it no longer writes /project1/lab/PX_pointfx)."""
    ns = dict(globals())
    exec(_read(SPLAT_BUILDER), ns)
    return ns['indep_upgrade'](op(parent_path).op(name).path)


def panel(parent_path='/project1/lab', name=NAME, open_window=False):
    """zkit panel: separate exec, >= 5 frames after build() (zkit measures its text in its own step)."""
    c = op(parent_path).op(name)
    Lg = _logic()
    ns = dict(globals())
    exec(_read(ZKIT_FILE), ns)
    st = c.op('px_rt').module.stack(c)
    pages = list(Lg['PANEL_CORE_PAGES']) + [Lg['page_name'](i) for i in st]
    return str(ns['build_controls'](c.path, pages=pages, d=56, cols=8, open_window=open_window))[:300]


def park(parent_path='/project1/lab', name=NAME):
    """Park only this COMP (user rule: builders park their own COMP when the job is done, after saving)."""
    c = op(parent_path).op(name)
    if c is not None:
        _close_window(c)
        c.allowCooking = False
    return {'comp': name, 'allowCooking': False if c is not None else None}
