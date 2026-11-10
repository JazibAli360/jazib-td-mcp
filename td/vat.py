"""Jazib MCP for TouchDesigner -- td_vat_load: play a vertex animation texture (VAT) baked in Blender on a mesh.

Contract: docs/PROTOCOL.md `vat_load`; how to use: docs/USING_TD.md "VAT (baked sims)". Bake side:
tools/blender_vat.py (headless Blender 5.2.2) + tools/vat_logic.py (layout, EXR, OBJ, sidecar 'jazib-vat/1').
Research: docs/research/FX7c_other_tools_effects.md card 26 (Keijiro HdrpVatExample / SideFX Labs VAT idea; own code).

The COMP (storage jz_kit kind 'vat'):
  pos / nrm   Movie File In TOPs: <name>_pos.exr / _nrm.exr, 32-bit float, colour passthrough (data, not colour)
  rate, clock Constant CHOP (Play x Speed x bake fps) -> Speed CHOP: the running frame (frames of the bake)
  geo         Geometry COMP: File In SOP `mesh` = the rest .obj (uv[0].z = VAT point index), material vat_mat
  vat_mat     GLSL MAT: vertex shader fetches the point's position (+ normal) for frames f0 / f1 by texelFetch and
              lerps (Interp); pixel shader: colour x optional Map TOP, own key + fill light, baked or flat normals
  frame_pos   GLSL TOP (width x rows_per_frame, 32F): the current frame's positions per point (same maths) -> out2,
              for instancing / point effects / checks
  cam, render Camera COMP orbiting the bake's bounds (Camera page) + Render TOP -> out1 (default 1080x1920)
Pars (page VAT): Play, Speed (1 = real time at the bake fps), Loop (loop / once / pingpong), Interp, Scrub + Frame
(drive Frame from anything, e.g. audio, with Scrub on), Reset; page Look: Color, Backcolor, Map, Normals, Light;
page Camera: Camorbit, Camelev, Camdist, Camfov, Targetx/y/z; Resw/Resh.

Frame logic (mirrored in tools/vat_logic.frame_pick, tested): loop wraps the last frame into the first, once
clamps, pingpong bounces; t = fraction when Interp is on.

Loading: like td/isf.py (handlers._ext_module reads THIS FILE, re-reads on mtime change, bind(globals())). Pure ASCII.
"""
import json
import os

H = {}
VAT_KIND = 'vat'
SCHEMA = 'jazib-vat/1'
LOOP_NAMES = ('loop', 'once', 'pingpong')
NORMAL_NAMES = ('baked', 'flat')


def bind(g):
    global H
    H = g
    return H


def G(name, default=None):
    return H.get(name, default)


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# ================================================================== pure: GLSL
VAT_COMMON = '''// td_vat_load (jazib-td): VAT lookup shared by the MAT and frame_pos. tools/vat_logic.py = reference.
uniform vec4 uVat;    // width, rows per frame, frames, points
uniform vec4 uTime;   // raw frame, loop mode (0 loop, 1 once, 2 pingpong), interp (0/1), normals (0 baked, 1 flat)

ivec2 vatTexel(int i, int f)
{
	int W = int(uVat.x + 0.5);
	int R = int(uVat.y + 0.5);
	return ivec2(i % W, f * R + i / W);
}

void vatPick(out int f0, out int f1, out float t)
{
	int n = int(uVat.z + 0.5);
	f0 = 0; f1 = 0; t = 0.0;
	if (n <= 1) return;
	float raw = uTime.x;
	int mode = int(uTime.y + 0.5);
	float f;
	if (mode == 0) {
		f = mod(raw, float(n));
		f0 = int(floor(f));
		f0 = clamp(f0, 0, n - 1);
		f1 = (f0 + 1) % n;
	} else if (mode == 1) {
		f = clamp(raw, 0.0, float(n - 1));
		f0 = clamp(int(floor(f)), 0, n - 1);
		f1 = min(f0 + 1, n - 1);
	} else {
		float per = 2.0 * float(n - 1);
		float g = mod(raw, per);
		f = g <= float(n - 1) ? g : per - g;
		f0 = clamp(int(floor(f)), 0, n - 1);
		f1 = min(f0 + 1, n - 1);
	}
	t = uTime.z > 0.5 ? clamp(f - float(f0), 0.0, 1.0) : 0.0;
}
'''

VAT_VERTEX = VAT_COMMON + '''
uniform sampler2D sPos;
uniform sampler2D sNrm;
out Vert { vec3 wpos; vec3 wnorm; vec2 tuv; } oVert;

void main()
{
	int i = int(uv[0].z + 0.5);
	int f0, f1; float t;
	vatPick(f0, f1, t);
	vec3 p = mix(texelFetch(sPos, vatTexel(i, f0), 0).xyz, texelFetch(sPos, vatTexel(i, f1), 0).xyz, t);
	vec3 n = mix(texelFetch(sNrm, vatTexel(i, f0), 0).xyz, texelFetch(sNrm, vatTexel(i, f1), 0).xyz, t);
	n = dot(n, n) > 1e-12 ? normalize(n) : vec3(0.0, 1.0, 0.0);
	vec4 worldSpacePos = TDDeform(p);
	gl_Position = TDWorldToProj(worldSpacePos);
#ifndef TD_PICKING_ACTIVE
	oVert.wpos = worldSpacePos.xyz;
	oVert.wnorm = normalize(TDDeformNorm(n));
	oVert.tuv = uv[0].st;
#else
	TDWritePickingValues();
#endif
}
'''

VAT_PIXEL = '''// td_vat_load (jazib-td): colour x Map, own key + fill light; baked (lerped) or flat normals; double-sided.
uniform sampler2D sMap;
uniform vec4 uTime;    // .w = normals (0 baked, 1 flat)
uniform vec4 uFront;   // rgb, map amount
uniform vec4 uBack;    // rgb, ambient
uniform vec4 uLight;   // key direction xyz (towards the light), specular
uniform vec4 uCam;     // camera position xyz
in Vert { vec3 wpos; vec3 wnorm; vec2 tuv; } iVert;
layout(location = 0) out vec4 fragColor;

void main()
{
	TDCheckDiscard();
	vec3 n = iVert.wnorm;
	if (uTime.w > 0.5) n = cross(dFdx(iVert.wpos), dFdy(iVert.wpos));
	n = dot(n, n) > 1e-20 ? normalize(n) : vec3(0.0, 1.0, 0.0);
	vec3 V = normalize(uCam.xyz - iVert.wpos);
	if (dot(n, V) < 0.0) n = -n;
	vec3 base = gl_FrontFacing ? uFront.rgb : uBack.rgb;
	base *= mix(vec3(1.0), texture(sMap, iVert.tuv).rgb, uFront.w);
	vec3 L = normalize(uLight.xyz);
	float key = max(dot(n, L), 0.0);
	float fill = max(dot(n, normalize(vec3(-L.x, 0.4, -L.z))), 0.0) * 0.25;
	float spec = pow(max(dot(reflect(-L, n), V), 0.0), 40.0) * uLight.w;
	vec3 col = base * (uBack.w + key * 0.85 + fill) + vec3(spec);
	fragColor = TDOutputSwizzle(vec4(col, 1.0));
}
'''

FRAME_POS_PIXEL = VAT_COMMON + '''
// frame_pos: one texel per point (same layout as one frame band): the interpolated position, w = 1 (0 = unused).
out vec4 fragColor;

void main()
{
	ivec2 c = ivec2(gl_FragCoord.xy);
	int W = int(uVat.x + 0.5);
	int i = c.y * W + c.x;
	if (i >= int(uVat.w + 0.5)) { fragColor = vec4(0.0); return; }
	int f0, f1; float t;
	vatPick(f0, f1, t);
	vec3 p = mix(texelFetch(sTD2DInputs[0], vatTexel(i, f0), 0).xyz, texelFetch(sTD2DInputs[0], vatTexel(i, f1), 0).xyz, t);
	fragColor = vec4(p, 1.0);
}
'''


def check_sidecar(side):
    """Same rules as tools/vat_logic.check_sidecar (kept here: td/ does not import tools/)."""
    bad = []
    if not isinstance(side, dict):
        return ['sidecar must be a JSON object']
    if side.get('schema') != SCHEMA:
        bad.append('schema is {!r}, want {!r} (bake with tools/blender_vat.py)'.format(side.get('schema'), SCHEMA))
    for k in ('frames', 'points', 'width', 'rows_per_frame', 'height'):
        if not isinstance(side.get(k), int) or side.get(k) < 1:
            bad.append('{} must be a positive int'.format(k))
    if not bad:
        if side['width'] * side['rows_per_frame'] < side['points']:
            bad.append('width x rows_per_frame < points')
        if side['height'] != side['frames'] * side['rows_per_frame']:
            bad.append('height != frames x rows_per_frame')
    return bad


def camera_defaults(side, hfov=45.0, aspect=1080.0 / 1920.0):
    """Target = bounds centre; distance so the bounds sphere fits the narrower view (horizontal FOV hfov, aspect
    w/h), plus 15 %."""
    import math
    b = side.get('bounds') or {'min': [-1, -1, -1], 'max': [1, 1, 1]}
    lo, hi = b['min'], b['max']
    ctr = [(lo[k] + hi[k]) * 0.5 for k in range(3)]
    r = max(0.5 * math.sqrt(sum((hi[k] - lo[k]) ** 2 for k in range(3))), 1e-3)
    th = math.tan(math.radians(hfov) * 0.5)
    tv = th / max(aspect, 1e-6)
    d = r / max(min(th, tv), 1e-6) * 1.15
    return {'target': [round(x, 4) for x in ctr], 'dist': round(d, 4)}


def uniform_rows():
    """GLSL MAT / TOP vector uniforms (name, 4 expressions); parent() = the VAT COMP for frame_pos, parent(2) is not
    needed because the MAT lives in the COMP too."""
    P = 'parent().par.'
    raw = "({P}Frame.eval() if {P}Scrub else op('clock')['frames'].eval())".format(P=P)
    side = "parent().fetch('vat_side', {{}}, search=False).get('{}', 1)"
    vat = [side.format('width'), side.format('rows_per_frame'), side.format('frames'), side.format('points')]
    tim = [raw, P + 'Loop.menuIndex', '1 if {}Interp else 0'.format(P), P + 'Normals.menuIndex']
    return vat, tim


# ================================================================== TD builder
def _set(o, name, value, notes):
    G('_midi_set')(o, name, value, notes)


def _vecs(o, rows, notes):
    _try(lambda: setattr(o.seq.vec, 'numBlocks', len(rows)))
    for k, (nm, ex) in enumerate(rows):
        _set(o, 'vec{}name'.format(k), nm, notes)
        for comp_, e in zip('xyzw', ex):
            v = {'expr': e} if isinstance(e, str) else float(e)
            _set(o, 'vec{}value{}'.format(k, comp_), v, notes)


def _zkit_panel(c, pages, notes):
    f = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(G('handlers_file')()))), 'builders', 'zkit.py')
    try:
        ns = dict(G('exec_namespace')())
        with open(f, 'r', encoding='utf-8') as fh:
            exec(compile(fh.read(), f, 'exec'), ns)
        return ns['build_controls'](c.path, pages=pages, d=56, cols=6)
    except Exception as e:
        notes.append('zkit panel failed ({}: {}): plain panel used'.format(type(e).__name__, str(e)[:160]))
        return None


EVENTS_EXEC = '''# td_vat_load events (jazib-td): Reset restarts the clock (frame 0).
def onPulse(par):
    if par.name == 'Reset':
        parent().op('clock').par.resetpulse.pulse()
'''


def _movie(c, nm, path, made, notes):
    m = G('_kit_child')(c, 'moviefileinTOP', nm, made, notes)
    for k, v in (('file', path), ('inputcolorspace', 'passthrough'), ('decodepixelformat', 'best'),
                 ('premultrgbbyalpha', 'off'), ('format', 'rgba32float'), ('filtertype', 'nearest'),
                 ('inputfiltertype', 'nearest')):
        _set(m, k, v, notes)
    return m


def cmd_vat_load(sidecar, mesh_file, pos_file, nrm_file=None, sidecar_file=None, parent='/project1', name=None,
                 res=None, panel='zkit', frames=3):
    """Sidecar dict (tools/blender_vat.py) + absolute file paths -> a self-contained VAT COMP (module docstring).
    Called again on the same COMP it updates in place. Replies after `frames` with compile state + sizes."""
    bad = check_sidecar(sidecar)
    if bad:
        raise ValueError('bad VAT sidecar: ' + '; '.join(bad))
    for k, f in (('mesh_file', mesh_file), ('pos_file', pos_file)):
        if not f or not os.path.isfile(f):
            raise ValueError('{} not found: {}'.format(k, f))
    if nrm_file and not os.path.isfile(nrm_file):
        raise ValueError('nrm_file not found: {}'.format(nrm_file))
    if panel not in ('zkit', 'plain'):
        raise ValueError("panel must be 'zkit' or 'plain'")
    if res is not None and (not isinstance(res, (list, tuple)) or len(res) != 2):
        raise ValueError('res must be [w, h]')
    kit_child, kit_pars, kit_wire, stage = G('_kit_child'), G('_kit_pars'), G('_kit_wire'), G('_stage')
    safe_destroy = G('safe_destroy')
    stem = ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in str(sidecar.get('name') or 'bake'))
    default_name = stem if stem.startswith('vat_') else 'vat_' + stem
    c, created = G('_kit_comp')(parent, name or default_name, VAT_KIND, default_name)
    par_ = c.parent()
    w, h = (int(res[0]), int(res[1])) if res else G('DEFAULT_RES')
    made, notes = [], []
    nfr = int(sidecar['frames'])
    cam0 = camera_defaults(sidecar, 45.0, float(w) / float(h))
    kit_pars(c, 'VAT', [
        ('Play', 'Toggle', True, {'label': 'Play'}),
        ('Speed', 'Float', 1.0, {'label': 'Speed (1 = bake fps)', 'min': -4.0, 'max': 4.0}),
        ('Loop', 'Menu', 'loop', {'label': 'Loop', 'names': list(LOOP_NAMES), 'labels': ['Loop', 'Once', 'Ping-pong']}),
        ('Interp', 'Toggle', True, {'label': 'Interpolate frames'}),
        ('Scrub', 'Toggle', False, {'label': 'Scrub (Frame drives)'}),
        ('Frame', 'Float', 0.0, {'label': 'Frame (bake frames)', 'min': 0.0, 'max': float(max(nfr - 1, 1))}),
        ('Reset', 'Pulse', None, {'label': 'Reset (frame 0)'}),
        ('Resw', 'Int', w, {'label': 'Render width', 'min': 16, 'max': 8192}),
        ('Resh', 'Int', h, {'label': 'Render height', 'min': 16, 'max': 8192})])
    _try(lambda: setattr(c.par.Frame, 'normMax', float(max(nfr - 1, 1))))
    if res:
        c.par.Resw.val, c.par.Resh.val = w, h
    kit_pars(c, 'Look', [
        ('Color', 'RGB', [0.86, 0.80, 0.72], {'label': 'Front colour'}),
        ('Backcolor', 'RGB', [0.55, 0.42, 0.40], {'label': 'Back colour'}),
        ('Map', 'TOP', '', {'label': 'Map TOP (mesh uv)'}),
        ('Mapamount', 'Float', 1.0, {'label': 'Map amount', 'min': 0.0, 'max': 1.0}),
        ('Normals', 'Menu', 'baked' if nrm_file else 'flat', {'label': 'Normals', 'names': list(NORMAL_NAMES),
                                                             'labels': ['Baked (lerped)', 'Flat (screen)']}),
        ('Lightdirx', 'Float', 0.4, {'label': 'Light dir x', 'min': -1.0, 'max': 1.0}),
        ('Lightdiry', 'Float', 0.8, {'label': 'Light dir y', 'min': -1.0, 'max': 1.0}),
        ('Lightdirz', 'Float', 0.5, {'label': 'Light dir z', 'min': -1.0, 'max': 1.0}),
        ('Ambient', 'Float', 0.22, {'label': 'Ambient', 'min': 0.0, 'max': 1.0}),
        ('Specular', 'Float', 0.25, {'label': 'Specular', 'min': 0.0, 'max': 1.0})])
    if not nrm_file:
        c.par.Normals.val = 'flat'
    kit_pars(c, 'Camera', [
        ('Camorbit', 'Float', 25.0, {'label': 'Orbit (deg)', 'min': -180.0, 'max': 180.0}),
        ('Camelev', 'Float', 18.0, {'label': 'Elevation (deg)', 'min': -89.0, 'max': 89.0}),
        ('Camdist', 'Float', cam0['dist'], {'label': 'Distance (m)', 'min': 0.1, 'max': max(cam0['dist'] * 4, 1.0)}),
        ('Camfov', 'Float', 45.0, {'label': 'Horizontal FOV', 'min': 5.0, 'max': 120.0}),
        ('Targetx', 'Float', cam0['target'][0], {'label': 'Target x', 'min': -10.0, 'max': 10.0}),
        ('Targety', 'Float', cam0['target'][1], {'label': 'Target y', 'min': -10.0, 'max': 10.0}),
        ('Targetz', 'Float', cam0['target'][2], {'label': 'Target z', 'min': -10.0, 'max': 10.0})])
    kit_pars(c, 'About', [('Vatfile', 'Str', '', {'label': 'VAT sidecar'})])
    c.par.Vatfile.val = sidecar_file or ''
    c.store('vat_side', {k: sidecar[k] for k in ('width', 'rows_per_frame', 'frames', 'points', 'fps')
                         if k in sidecar})
    # sources
    sd = kit_child(c, 'textDAT', 'sidecar', made, notes)
    sd.text = json.dumps(sidecar, indent=1)
    pos = _movie(c, 'pos', pos_file, made, notes)
    nrm = _movie(c, 'nrm', nrm_file or pos_file, made, notes)
    white = kit_child(c, 'constantTOP', 'vat_white', made, notes)
    for k, v in (('colorr', 1), ('colorg', 1), ('colorb', 1), ('alpha', 1), ('outputresolution', {'menu': 'custom'}),
                 ('resolutionw', 4), ('resolutionh', 4)):
        _set(white, k, v, notes)
    mapsel = kit_child(c, 'selectTOP', 'map', made, notes)
    _set(mapsel, 'top', {'expr': "parent().par.Map.eval() or op('vat_white')"}, notes)
    # clock
    rate = kit_child(c, 'constantCHOP', 'rate', made, notes)
    fps = float(sidecar.get('fps') or 30.0)
    for k, v in (('const0name', 'frames'),
                 ('const0value', {'expr': 'float(parent().par.Play) * parent().par.Speed * {!r}'.format(fps)})):
        _set(rate, k, v, notes)
    clock = kit_child(c, 'speedCHOP', 'clock', made, notes)
    kit_wire([rate], clock, notes)
    ev = kit_child(c, 'parameterexecuteDAT', 'vat_events', made, notes)
    ev.text = EVENTS_EXEC
    for k, v in (('op', '..'), ('pars', 'Reset'), ('custom', True), ('builtin', False), ('onpulse', True),
                 ('valuechange', False)):
        _set(ev, k, v, notes)
    vat_u, tim_u = uniform_rows()
    # frame positions TOP
    fpd = kit_child(c, 'textDAT', 'frame_pos_pixel', made, notes)
    fpd.text = FRAME_POS_PIXEL
    fp = kit_child(c, 'glslTOP', 'frame_pos', made, notes)
    for k, v in (('glslversion', {'menu': 'glsl460'}), ('pixeldat', 'frame_pos_pixel'),
                 ('outputresolution', {'menu': 'custom'}), ('resolutionw', int(sidecar['width'])),
                 ('resolutionh', int(sidecar['rows_per_frame'])), ('format', 'rgba32float'),
                 ('inputfiltertype', 'nearest')):
        _set(fp, k, v, notes)
    for dn in ('frame_pos_info', 'frame_pos_compute', 'frame_pos_pixel1'):
        o = c.op(dn)
        if o is not None and o.name != fpd.name and _try(lambda: o.OPType, '') == 'textDAT':
            safe_destroy(o)
    kit_wire([pos], fp, notes)
    _vecs(fp, [('uVat', vat_u), ('uTime', tim_u)], notes)
    out2 = kit_child(c, 'outTOP', 'out2', made, notes)
    kit_wire([fp], out2, notes)
    # material
    vd = kit_child(c, 'textDAT', 'vat_vertex', made, notes)
    vd.text = VAT_VERTEX
    pd = kit_child(c, 'textDAT', 'vat_pixel', made, notes)
    pd.text = VAT_PIXEL
    mat = kit_child(c, 'glslMAT', 'vat_mat', made, notes)
    _set(mat, 'vdat', 'vat_vertex', notes)
    _set(mat, 'pdat', 'vat_pixel', notes)
    for dn in ('_vertex', '_pixel', '_info'):  # the MAT's auto-made docked DATs
        o = c.op('vat_mat' + dn)
        if o is not None and o.name not in (vd.name, pd.name):
            safe_destroy(o)
    _try(lambda: setattr(vd, 'dock', mat))
    _try(lambda: setattr(pd, 'dock', mat))
    _try(lambda: setattr(mat.seq.sampler, 'numBlocks', 3))
    for k, (sn, top, flt) in enumerate((('sPos', 'pos', 'nearest'), ('sNrm', 'nrm', 'nearest'),
                                        ('sMap', 'map', 'linear'))):
        for pn, v in (('name', sn), ('top', top), ('filter', flt), ('extendu', 'hold'), ('extendv', 'hold')):
            _set(mat, 'sampler{}{}'.format(k, pn), v, notes)
    P = 'parent().par.'
    _vecs(mat, [('uVat', vat_u), ('uTime', tim_u),
                ('uFront', [P + 'Colorr', P + 'Colorg', P + 'Colorb', "{}Mapamount if {}Map.eval() else 0".format(P, P)]),
                ('uBack', [P + 'Backcolorr', P + 'Backcolorg', P + 'Backcolorb', P + 'Ambient']),
                ('uLight', [P + 'Lightdirx', P + 'Lightdiry', P + 'Lightdirz', P + 'Specular']),
                ('uCam', ["op('cam').worldTransform.decompose()[2][0]", "op('cam').worldTransform.decompose()[2][1]",
                          "op('cam').worldTransform.decompose()[2][2]", 0])], notes)
    _set(mat, 'cullface', 'neither', notes)
    # geometry
    geo = kit_child(c, 'geometryCOMP', 'geo', made, notes)
    if geo is not None:
        for ch in list(_try(lambda: list(geo.children), [])):
            if ch.name != 'mesh':
                safe_destroy(ch)
        sop = geo.op('mesh') or geo.create(G('td').fileinSOP, 'mesh')
        _set(sop, 'file', mesh_file, notes)
        _try(lambda: setattr(sop, 'render', True))
        _try(lambda: setattr(sop, 'display', True))
        _try(lambda: setattr(geo.par, 'material', mat))  # an op, not a path string: '../vat_mat' via _midi_set stayed None
        if _try(lambda: geo.par.material.eval(), None) is None:
            notes.append('geo.material not set: the mesh renders without the VAT material')
    # camera + render
    cam = kit_child(c, 'cameraCOMP', 'cam', made, notes)
    rad = 'math.radians({}{})'
    o_, e_ = rad.format(P, 'Camorbit'), rad.format(P, 'Camelev')
    for k, v in (('tx', '{}Targetx + {}Camdist * math.sin({}) * math.cos({})'.format(P, P, o_, e_)),
                 ('ty', '{}Targety + {}Camdist * math.sin({})'.format(P, P, e_)),
                 ('tz', '{}Targetz + {}Camdist * math.cos({}) * math.cos({})'.format(P, P, o_, e_)),
                 ('rx', '-' + P + 'Camelev'), ('ry', P + 'Camorbit'), ('fov', P + 'Camfov')):
        _set(cam, k, {'expr': v}, notes)
    for k, v in (('rz', 0), ('rord', 'xyz'), ('xord', 'srt'), ('viewanglemethod', 'horzfov'), ('near', 0.01),
                 ('far', 1000)):
        _set(cam, k, v, notes)
    rnd = kit_child(c, 'renderTOP', 'render', made, notes)
    for k, v in (('camera', 'cam'), ('geometry', 'geo'), ('lights', ''), ('outputresolution', {'menu': 'custom'}),
                 ('resolutionw', {'expr': P + 'Resw'}), ('resolutionh', {'expr': P + 'Resh'}),
                 ('bgcolorr', 0), ('bgcolorg', 0), ('bgcolorb', 0), ('bgcolora', 0)):
        _set(rnd, k, v, notes)
    out1 = kit_child(c, 'outTOP', 'out1', made, notes)
    kit_wire([rnd], out1, notes)
    # controls
    ctl, used_panel = [], panel
    info = _zkit_panel(c, ['VAT', 'Look', 'Camera'], notes) if panel == 'zkit' else None
    if info is not None:
        ctl = ['controls', 'controls_window']
    else:
        used_panel = 'plain'
        kit_pars(c, 'Controls', [('Opencontrols', 'Pulse', None, {'label': 'Open controls'})])
        ctl = G('_kit_controls')(c, 'VAT', made, notes, 420, 600, 'VAT Look Camera About')
    c.store(G('KIT_KEY'), {'kind': VAT_KIND, 'frames': nfr, 'points': int(sidecar['points']), 'panel': used_panel})
    c.comment = 'td_vat_load: {} ({} points x {} frames @ {} fps, {}x{} EXR). Blender bake: tools/blender_vat.py'.format(
        sidecar.get('name'), sidecar['points'], nfr, fps, sidecar['width'], sidecar['height'])
    about = G('about_values')(_try(lambda: c.par.Version.eval(), None), None, None,
                              G('td_build_string')(_try(lambda: G('app').version, ''), _try(lambda: G('app').build, '')))
    G('_stamp_about')(c, about)
    stages = [stage(c, 'Bake', 'input', ['sidecar', 'pos', 'nrm', 'vat_white', 'map'],
                    'the Blender bake: sidecar json, position / normal EXRs (32F, passthrough), Map TOP'),
              stage(c, 'Clock', 'control', ['rate', 'clock', 'vat_events'], 'frame counter: Play x Speed x bake fps; Reset'),
              stage(c, 'Points', 'process', ['frame_pos_pixel', 'frame_pos', 'out2'],
                    'frame_pos: this frame\'s positions per point (32F) -> out2 (instancing / checks)'),
              stage(c, 'Material', 'process', ['vat_vertex', 'vat_pixel', 'vat_mat'],
                    'GLSL MAT: texelFetch by uv[0].z (point index), lerp f0 -> f1, own lighting'),
              stage(c, 'Render', 'output', ['geo', 'cam', 'render', 'out1'], 'rest mesh + MAT, orbit camera -> out1'),
              stage(c, 'Controls', 'control', ctl, 'Opencontrols opens the panel')]
    fin = G('_kit_finish')(c, stages, created, par_, notes)

    def finish():
        bad_ = []
        for o in (mat, fp, pos, nrm, rnd):
            if o is None:
                continue
            _try(lambda: o.cook(force=True))
            err = (_try(lambda: o.errors(), '') or '')
            bad_ += ['{}: {}'.format(o.name, ln) for ln in err.splitlines() if ln.strip()]
        log = ''
        for o in (mat, fp):
            lg = _try(lambda: G('_glsl_log')(o), '') or ''
            log += lg
            bad_ += ['{}: {}'.format(o.name, ln) for ln in lg.splitlines() if 'error' in ln.lower()]
        sop = geo.op('mesh') if geo is not None else None
        r = {'path': c.path, 'created': created, 'out1': out1.path, 'out2': out2.path,
             'frames': nfr, 'points': int(sidecar['points']), 'fps': fps,
             'texture': [int(sidecar['width']), int(sidecar['height'])],
             'pos_res': [_try(lambda: pos.width), _try(lambda: pos.height)],
             'mesh_points': _try(lambda: sop.numPoints), 'mesh_prims': _try(lambda: sop.numPrims),
             'compile': {'ok': not bad_, 'errors': bad_[:20], 'log': log.strip()[:3000]},
             'panel': used_panel, 'new_ops': made}
        if r['pos_res'] != r['texture']:
            r['warnings'] = ['pos EXR loaded as {} (sidecar says {})'.format(r['pos_res'], r['texture'])]
        r.update(fin)
        if notes:
            r['notes'] = notes
        r['hint'] = ('VAT page: Play / Speed / Loop / Interp; Scrub on + Frame to drive it (audio, timeline); out1 = '
                     'render, out2 = positions per point this frame (32F)')
        return r
    return G('Pending')(max(1, int(frames)), finish)
