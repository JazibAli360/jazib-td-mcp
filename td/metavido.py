"""Jazib MCP for TouchDesigner -- td_metavido: decode Metavido video (colour + hue-encoded depth + burnt-in camera
pose, Keijiro Takahashi's iPhone LiDAR format) into TD TOPs + a pose CHOP + a camera.

Contract: docs/PROTOCOL.md `metavido`; how to use: docs/USING_TD.md "Metavido". Format notes and the numpy
reference: tools/metavido_logic.py (clean-room from the spec in github.com/keijiro/Metavido, Unlicense; no code
copied). Research: docs/research/FX7c_other_tools_effects.md card 27.

The COMP (storage jz_kit kind 'metavido'):
  movie        Movie File In (colour passthrough: the planes are data), Play / Speed or Scrub + Index (Scrub keeps
               the movie's play on: in specify mode a stopped Movie File In ignores index changes; index N = ffmpeg
               frame N - 1 on the demo clip)
  meta_decode  GLSL TOP 12x1 32F: the barcode's 12 float32 words (bits from the blue channel)
  pose         GLSL TOP 14x1 32F: TD camera pose (POSE_NAMES) -> pose_t2c (TOP to CHOP) -> pose_swap (Shuffle
               swap) -> pose_names (Rename) -> pose_out (Out CHOP), one sample per channel
  colour       GLSL TOP 960x1080: right half; Stencil on = premultiplied alpha from the human stencil -> out1
  depth        GLSL TOP 960x540 32F mono: metres along the view axis (hue decode, near..far) -> out2
  points       GLSL TOP 960x540 32F: TD world position per depth texel, w = 1 inside (near, far) -> out3
  cam          Camera COMP driven by pose_out (rotate order zxy, vertical FOV) = the recording camera
Coordinates: Unity left-handed -> TD by mirroring Z (p -> x, y, -z; q -> -x, -y, z, w).
Loading: handlers._ext_module (like td/isf.py). Pure ASCII.
"""
import os

H = {}
MV_KIND = 'metavido'
POSE_NAMES = ('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'fov', 'hfov', 'near', 'far', 'shiftx', 'shifty', 'valid', 'hash')


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


# ================================================================== pure: GLSL (reference: tools/metavido_logic.py)
META_DECODE = '''// td_metavido: barcode -> 12 float32 words (px py pz rx ry rz sx sy fov near far hash). Input 0 = the frame.
out vec4 fragColor;
void main()
{
	int k = int(gl_FragCoord.x);
	uint acc = 0u;
	for (int i = 0; i < 32; i++) {
		int y = i * 8 + 4;
		float b = texelFetch(sTD2DInputs[0], ivec2(k * 8 + 3, y), 0).b + texelFetch(sTD2DInputs[0], ivec2(k * 8 + 5, y), 0).b;
		if (b > 0.4) acc |= (1u << uint(i));
	}
	fragColor = vec4(uintBitsToFloat(acc), 0.0, 0.0, 1.0);
}
'''

MV_COMMON = '''// td_metavido common: metadata access + Unity -> TD pose. sMeta = the meta_decode TOP (12x1).
float mvMeta(sampler2D sMeta, int k) { return texelFetch(sMeta, ivec2(k, 0), 0).r; }
bool mvValid(sampler2D sMeta)
{
	float fov = mvMeta(sMeta, 8);
	return !isnan(fov) && fov > 0.0 && fov < 3.14159265 && mvMeta(sMeta, 9) < mvMeta(sMeta, 10);
}
vec3 mvPos(sampler2D sMeta) { return vec3(mvMeta(sMeta, 0), mvMeta(sMeta, 1), -mvMeta(sMeta, 2)); }
mat3 mvRot(sampler2D sMeta)
{
	float qx = mvMeta(sMeta, 3), qy = mvMeta(sMeta, 4), qz = mvMeta(sMeta, 5);
	float w = sqrt(max(1.0 - qx * qx - qy * qy - qz * qz, 0.0));
	float x = -qx, y = -qy, z = qz;
	// columns (GLSL mat3 is column-major)
	return mat3(1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y + z * w), 2.0 * (x * z - y * w),
	            2.0 * (x * y - z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z + x * w),
	            2.0 * (x * z + y * w), 2.0 * (y * z - x * w), 1.0 - 2.0 * (x * x + y * y));
}
'''

POSE = MV_COMMON + '''
// td_metavido pose: 14 values in POSE_NAMES order (TD camera, rotate order zxy, degrees).
out vec4 fragColor;
void main()
{
	int k = int(gl_FragCoord.x);
	mat3 R = mvRot(sTD2DInputs[0]);
	vec3 t = mvPos(sTD2DInputs[0]);
	float r12 = R[2][1];  // row 1, column 2
	float a = asin(-clamp(r12, -1.0, 1.0));
	float b, c;
	if (abs(r12) < 0.999999) { b = atan(R[2][0], R[2][2]); c = atan(R[0][1], R[1][1]); }
	else { b = atan(-R[0][2], R[0][0]); c = 0.0; }
	float fov = mvMeta(sTD2DInputs[0], 8);
	float h = tan(fov * 0.5);
	float v[14] = float[14](t.x, t.y, t.z, degrees(a), degrees(b), degrees(c), degrees(fov),
	                        degrees(2.0 * atan(h * 16.0 / 9.0)), mvMeta(sTD2DInputs[0], 9), mvMeta(sTD2DInputs[0], 10),
	                        mvMeta(sTD2DInputs[0], 6), mvMeta(sTD2DInputs[0], 7), mvValid(sTD2DInputs[0]) ? 1.0 : 0.0,
	                        mvMeta(sTD2DInputs[0], 11));
	fragColor = vec4(v[clamp(k, 0, 13)], 0.0, 0.0, 1.0);
}
'''

COLOUR = '''// td_metavido colour: right half of the frame; uOpt.y = 1 -> alpha = human stencil (premultiplied).
uniform vec4 uOpt;   // margin, stencil alpha (0/1)
out vec4 fragColor;
void main()
{
	ivec2 p = ivec2(gl_FragCoord.xy);
	vec3 c = texelFetch(sTD2DInputs[0], ivec2(p.x + 960, p.y), 0).rgb;
	float a = 1.0;
	if (uOpt.y > 0.5) {
		float s = texelFetch(sTD2DInputs[0], ivec2(p.x, p.y / 2), 0).r;
		a = clamp(mix(-0.1, 1.0, s), 0.0, 1.0);  // compression noise floor
	}
	fragColor = TDOutputSwizzle(vec4(c * a, a));
}
'''

DEPTH = MV_COMMON + '''
// td_metavido depth: top-left plane, hue -> metres (near..far from the barcode). Input 0 = frame, 1 = meta_decode.
uniform vec4 uOpt;   // margin
out vec4 fragColor;
float mvHue(vec3 c)
{
	float mn = min(min(c.r, c.g), c.b);
	float mx = max(max(c.r, c.g), c.b);
	float div = 1.0 / (6.0 * max(mx - mn, 1e-5));
	float hr = (c.g - c.b) * div;
	float hg = 1.0 / 3.0 + (c.b - c.r) * div;
	float hb = 2.0 / 3.0 + (c.r - c.g) * div;
	float d = c.r < max(c.g, c.b) ? (c.g < c.b ? hb : hg) : hr;
	return fract(d + 1.0 - 0.005) + 0.005;
}
void main()
{
	int m = int(uOpt.x + 0.5);
	ivec2 p = ivec2(gl_FragCoord.xy);
	ivec2 tc = ivec2(min(p.x, 959 - m), max(p.y + 540, 540 + m));
	float d = mvHue(texelFetch(sTD2DInputs[0], tc, 0).rgb);
	d = (d - 0.01) / 0.98;
	d = (d - 0.01) / 0.98;
	float n = mvMeta(sTD2DInputs[1], 9), f = mvMeta(sTD2DInputs[1], 10);
	fragColor = vec4(mix(n, f, d), 0.0, 0.0, 1.0);
}
'''

POINTS = MV_COMMON + '''
// td_metavido points: depth texel -> TD world position (w = 1 inside (near, far) of a valid frame).
// Input 0 = depth (960x540, metres), 1 = meta_decode.
out vec4 fragColor;
void main()
{
	ivec2 p = ivec2(gl_FragCoord.xy);
	vec2 uv = (vec2(p) + 0.5) / vec2(960.0, 540.0);
	float d = texelFetch(sTD2DInputs[0], p, 0).r;
	float fov = mvMeta(sTD2DInputs[1], 8);
	float h = tan(fov * 0.5);
	vec2 ray = ((uv - 0.5) * 2.0 + vec2(mvMeta(sTD2DInputs[1], 6), mvMeta(sTD2DInputs[1], 7))) * vec2(h * 16.0 / 9.0, h);
	vec3 local = vec3(ray * d, -d);
	vec3 w = mvRot(sTD2DInputs[1]) * local + mvPos(sTD2DInputs[1]);
	float n = mvMeta(sTD2DInputs[1], 9), f = mvMeta(sTD2DInputs[1], 10);
	bool ok = mvValid(sTD2DInputs[1]) && d > n && d < f - (f - n) * 0.002;
	fragColor = vec4(w, ok ? 1.0 : 0.0);
}
'''

STAGES = (('meta_decode', META_DECODE, (12, 1), 'mono32float', ['movie']),
          ('pose', POSE, (14, 1), 'mono32float', ['meta_decode']),
          ('colour', COLOUR, (960, 1080), 'rgba8fixed', ['movie']),
          ('depth', DEPTH, (960, 540), 'mono32float', ['movie', 'meta_decode']),
          ('points', POINTS, (960, 540), 'rgba32float', ['depth', 'meta_decode']))


# ================================================================== TD builder
def _set(o, name, value, notes):
    G('_midi_set')(o, name, value, notes)


def cmd_metavido(file, parent='/project1', name=None, panel='plain', frames=3):
    """A Metavido clip -> a self-contained decoder COMP (module docstring). Rebuilds in place."""
    if not file or not os.path.isfile(file):
        raise ValueError('Metavido file not found: {}'.format(file))
    if panel not in ('zkit', 'plain'):
        raise ValueError("panel must be 'zkit' or 'plain'")
    kit_child, kit_pars, kit_wire, stage = G('_kit_child'), G('_kit_pars'), G('_kit_wire'), G('_stage')
    stem = ''.join(ch if ch.isalnum() or ch == '_' else '_' for ch in os.path.splitext(os.path.basename(file))[0])
    c, created = G('_kit_comp')(parent, name or ('mv_' + stem)[:60], MV_KIND, 'mv_' + stem)
    par_ = c.parent()
    made, notes = [], []
    kit_pars(c, 'Metavido', [
        ('Play', 'Toggle', True, {'label': 'Play'}),
        ('Speed', 'Float', 1.0, {'label': 'Speed', 'min': -4.0, 'max': 4.0}),
        ('Scrub', 'Toggle', False, {'label': 'Scrub (Index drives)'}),
        ('Index', 'Float', 0.0, {'label': 'Index (frames)', 'min': 0.0, 'max': 2000.0}),
        ('Stencil', 'Toggle', False, {'label': 'Colour alpha = human stencil'}),
        ('Margin', 'Int', 1, {'label': 'Depth edge margin (px)', 'min': 0, 'max': 8, 'clamp': True})])
    kit_pars(c, 'About', [('Mvfile', 'Str', '', {'label': 'Metavido clip'})])
    c.par.Mvfile.val = file
    P = 'parent().par.'
    mv = kit_child(c, 'moviefileinTOP', 'movie', made, notes)
    for k, v in (('file', file), ('inputcolorspace', 'passthrough'), ('decodepixelformat', 'best'),
                 ('premultrgbbyalpha', 'off'), ('play', {'expr': '1 if ({0}Play or {0}Scrub) else 0'.format(P)}), ('speed', {'expr': P + 'Speed'}),
                 ('playmode', {'expr': "'specify' if {}Scrub else 'sequential'".format(P)}),
                 ('index', {'expr': P + 'Index'}), ('indexunit', 'frames'), ('filtertype', 'nearest')):
        _set(mv, k, v, notes)
    glsl = []
    for nm, code, (w, h), fmt, ins in STAGES:
        d = kit_child(c, 'textDAT', nm + '_glsl', made, notes)
        d.text = code
        g = kit_child(c, 'glslTOP', nm, made, notes)
        for k, v in (('glslversion', {'menu': 'glsl460'}), ('pixeldat', nm + '_glsl'),
                     ('outputresolution', {'menu': 'custom'}), ('resolutionw', w), ('resolutionh', h),
                     ('format', fmt), ('inputfiltertype', 'nearest')):
            _set(g, k, v, notes)
        for dn in (nm + '_info', nm + '_pixel', nm + '_compute'):  # auto-docked DATs of a new GLSL TOP
            o = c.op(dn)
            if o is not None and _try(lambda: o.OPType, '') == 'textDAT':
                G('safe_destroy')(o)
        kit_wire([c.op(i) for i in ins], g, notes)
        if nm in ('colour', 'depth'):
            _try(lambda: setattr(g.seq.vec, 'numBlocks', 1))
            _set(g, 'vec0name', 'uOpt', notes)
            _set(g, 'vec0valuex', {'expr': P + 'Margin'}, notes)
            _set(g, 'vec0valuey', {'expr': '1 if {}Stencil else 0'.format(P)}, notes)
        glsl.append(g)
    t2c = kit_child(c, 'toptoCHOP', 'pose_t2c', made, notes)
    for k, v in (('top', 'pose'), ('r', 'v'), ('g', ''), ('b', ''), ('a', ''), ('downloadtype', 'nextframe'),
                 ('outputcolorspace', 'passthrough')):
        _set(t2c, k, v, notes)
    sw = kit_child(c, 'shuffleCHOP', 'pose_swap', made, notes)
    _set(sw, 'method', 'swap', notes)
    kit_wire([t2c], sw, notes)
    rn = kit_child(c, 'renameCHOP', 'pose_names', made, notes)
    _set(rn, 'renamefrom', '*', notes)
    _set(rn, 'renameto', ' '.join(POSE_NAMES), notes)
    kit_wire([sw], rn, notes)
    po = kit_child(c, 'outCHOP', 'pose_out', made, notes)
    kit_wire([rn], po, notes)
    outs = []
    for k, src in enumerate(('colour', 'depth', 'points')):
        o = kit_child(c, 'outTOP', 'out{}'.format(k + 1), made, notes)
        kit_wire([c.op(src)], o, notes)
        outs.append(o)
    cam = kit_child(c, 'cameraCOMP', 'cam', made, notes)
    for k in ('tx', 'ty', 'tz', 'rx', 'ry', 'rz'):
        _set(cam, k, {'expr': "op('pose_names')['{}']".format(k)}, notes)
    for k, v in (('rord', 'zxy'), ('xord', 'srt'), ('viewanglemethod', 'vertfov'),
                 ('fov', {'expr': "op('pose_names')['fov']"}), ('near', 0.05), ('far', 1000)):
        _set(cam, k, v, notes)
    if panel == 'zkit':
        notes.append('panel zkit not offered for td_metavido yet: plain panel used')
    kit_pars(c, 'Controls', [('Opencontrols', 'Pulse', None, {'label': 'Open controls'})])
    ctl = G('_kit_controls')(c, 'Metavido', made, notes, 420, 380, 'Metavido About')
    c.store(G('KIT_KEY'), {'kind': MV_KIND, 'panel': 'plain'})
    c.comment = ('td_metavido: {} -> out1 colour (960x1080), out2 depth m (960x540 32F), out3 points (TD world, '
                 '32F), pose_out CHOP, cam. Format: Keijiro Metavido (Unlicense), decoder clean-room.').format(
        os.path.basename(file))
    about = G('about_values')(_try(lambda: c.par.Version.eval(), None), None, None,
                              G('td_build_string')(_try(lambda: G('app').version, ''), _try(lambda: G('app').build, '')))
    G('_stamp_about')(c, about)
    stages = [stage(c, 'Clip', 'input', ['movie'], 'Metavido clip (colour passthrough: planes are data)'),
              stage(c, 'Metadata', 'process', ['meta_decode_glsl', 'meta_decode', 'pose_glsl', 'pose', 'pose_t2c',
                                                'pose_swap', 'pose_names', 'pose_out', 'cam'],
                    'barcode -> 12 floats -> TD pose (zxy, vertical FOV) -> CHOP + camera'),
              stage(c, 'Planes', 'process', ['colour_glsl', 'colour', 'depth_glsl', 'depth', 'points_glsl', 'points'],
                    'colour (+ stencil alpha), hue depth (m), world points'),
              stage(c, 'Output', 'output', ['out1', 'out2', 'out3'], 'out1 colour, out2 depth, out3 points'),
              stage(c, 'Controls', 'control', ctl, 'Opencontrols opens the panel')]
    fin = G('_kit_finish')(c, stages, created, par_, notes)

    def finish():
        bad = []
        for o in [mv] + glsl + [t2c, rn]:
            _try(lambda: o.cook(force=True))
            bad += ['{}: {}'.format(o.name, ln) for ln in (_try(lambda: o.errors(), '') or '').splitlines() if ln.strip()]
        log = ''
        for g in glsl:
            lg = _try(lambda: G('_glsl_log')(g), '') or ''
            bad += ['{}: {}'.format(g.name, ln) for ln in lg.splitlines() if 'error' in ln.lower()]
            log += lg
        res = [_try(lambda: mv.width), _try(lambda: mv.height)]
        r = {'path': c.path, 'created': created, 'outs': [o.path for o in outs], 'pose': po.path, 'cam': cam.path,
             'movie_res': res, 'compile': {'ok': not bad, 'errors': bad[:20], 'log': log.strip()[:2000]},
             'pose_names': list(POSE_NAMES), 'new_ops': made}
        if res != [1920, 1080]:
            r['warnings'] = ['clip is {}x{}: Metavido frames are 1920x1080 (planes will be wrong)'.format(*res)]
        r.update(fin)
        if notes:
            r['notes'] = notes
        r['hint'] = ('out1 colour (Stencil = alpha), out2 depth metres, out3 TD world points (w = valid) for instancing '
                     '/ pointcloud; pose_out + cam = the recording camera (pose CHOP lags one frame: nextframe download)')
        return r
    return G('Pending')(max(1, int(frames)), finish)
