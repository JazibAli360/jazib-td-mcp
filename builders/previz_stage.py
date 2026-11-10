"""previz_stage builder: a stage previz in haze (LED wall, crowd, screen-following stage light, camera presets).

Run inside TouchDesigner (td_exec):
    p = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/previz_stage.py'
    g = dict(globals()); exec(open(p).read(), g); g['build']('/project1/lab')
Idempotent: a rebuild keeps the COMP (and its wiring from outside) and the values of its custom parameters, and
re-creates everything inside. Spec: docs/research/BI_rudiment_previz_stage.md (generic wall, no show branding);
how-to: docs/builds/previz_stage.md. Pure logic: builders/previz_stage_logic.py (copied into the DAT previz_logic).
"""
import os

NAME = 'PV_previz_stage'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(HERE, 'previz_stage_logic.py')

# ------------------------------------------------------------------ custom parameters
# (page, name, label, style, default, min, max, extra)
PARS = [
    ('Stage', 'Layout', 'Wall layout', 'Menu', 'flat', None, None, (['flat', 'sides', 'custom'], ['Flat 16:9', 'Main + side screens', 'Custom (face_table)'])),
    ('Stage', 'Wallw', 'Main width (m)', 'Float', 12.0, 1, 60, None),
    ('Stage', 'Wallh', 'Main height (m)', 'Float', 6.75, 0.5, 30, None),
    ('Stage', 'Curve', 'Main curve (deg)', 'Float', 0.0, -120, 120, None),
    ('Stage', 'Sidew', 'Side width (m)', 'Float', 4.0, 0.5, 30, None),
    ('Stage', 'Sideh', 'Side height (m)', 'Float', 6.0, 0.5, 30, None),
    ('Stage', 'Sidefold', 'Side fold (deg)', 'Float', 20.0, -90, 90, None),
    ('Stage', 'Gap', 'Gap between faces (m)', 'Float', 1.5, 0, 20, None),
    ('Stage', 'Contentmap', 'Content on faces', 'Menu', 'span', None, None, (['span', 'repeat'], ['Span all faces', 'Repeat per face'])),
    ('Stage', 'Screenelev', 'Screen above deck (m)', 'Float', 1.0, 0, 20, None),
    ('Stage', 'Screenemit', 'Screen brightness', 'Float', 1.0, 0, 4, None),
    ('Stage', 'Stageh', 'Deck height (m)', 'Float', 1.2, 0, 4, None),
    ('Stage', 'Stagedepth', 'Deck depth (m)', 'Float', 10.0, 2, 40, None),
    ('Stage', 'Trussh', 'Truss height (m)', 'Float', 10.5, 2, 40, None),
    ('Stage', 'Trussz', 'Truss distance from wall (m)', 'Float', 3.0, 0, 30, None),
    ('Crowd', 'Crowdon', 'Crowd on', 'Toggle', True, None, None, None),
    ('Crowd', 'Count', 'Count', 'Int', 800, 0, 5000, None),
    ('Crowd', 'Rows', 'Rows', 'Int', 20, 1, 200, None),
    ('Crowd', 'Spacing', 'Spacing (m)', 'Float', 0.65, 0.3, 3, None),
    ('Crowd', 'Crowdgap', 'Gap to stage (m)', 'Float', 3.0, 0, 30, None),
    ('Crowd', 'Heightvar', 'Height variation', 'Float', 0.08, 0, 0.5, None),
    ('Crowd', 'Seed', 'Seed', 'Int', 1, 0, 9999, None),
    ('Crowd', 'Sway', 'Sway', 'Float', 0.3, 0, 1, None),
    ('Crowd', 'Swayspeed', 'Sway speed', 'Float', 0.5, 0, 5, None),
    ('Crowd', 'Hands', 'Raised hands (fraction)', 'Float', 0.15, 0, 1, None),
    ('Crowd', 'Crowdlit', 'Screen light on crowd', 'Float', 1.0, 0, 4, None),
    ('Haze', 'Hazeon', 'Haze on', 'Toggle', True, None, None, None),
    ('Haze', 'Density', 'Density', 'Float', 0.5, 0, 3, None),
    ('Haze', 'Falloff', 'Height falloff', 'Float', 1.0, 0, 5, None),
    ('Haze', 'Drift', 'Drift speed', 'Float', 0.05, 0, 1, None),
    ('Haze', 'Scatter', 'Beam visibility', 'Float', 0.6, 0, 3, None),
    ('Haze', 'Hazeglow', 'Screen glow in haze', 'Float', 0.5, 0, 3, None),
    ('Lights', 'Lightson', 'Lights on', 'Toggle', True, None, None, None),
    ('Lights', 'Beams', 'Beams', 'Int', 8, 1, 24, None),
    ('Lights', 'Spread', 'Beam spread (deg)', 'Float', 6.0, 0.5, 60, None),
    ('Lights', 'Fan', 'Fan (deg)', 'Float', 50.0, 0, 160, None),
    ('Lights', 'Beamtilt', 'Tilt to crowd (deg)', 'Float', 30.0, -80, 80, None),
    ('Lights', 'Beamlen', 'Beam length (m)', 'Float', 30.0, 1, 120, None),
    ('Lights', 'Intensity', 'Intensity', 'Float', 1.0, 0, 5, None),
    ('Lights', 'Follow', 'Follow screen colour', 'Float', 1.0, 0, 1, None),
    ('Lights', 'Reactmode', 'React mode', 'Menu', 'average', None, None, (['average', 'leftright', 'perface', 'dominant'], ['Average', 'Left / right', 'Per face', 'Dominant colour'])),
    ('Lights', 'Reactlag', 'React lag (s)', 'Float', 0.2, 0, 5, None),
    ('Lights', 'Beamsweep', 'Sweep', 'Float', 0.3, 0, 2, None),
    ('Lights', 'Beamsweepspeed', 'Sweep speed (Hz)', 'Float', 0.2, 0, 4, None),
    ('Lights', 'Wash', 'Wash light', 'Float', 1.0, 0, 5, None),
    ('Lights', 'Strobe', 'Strobe', 'Float', 0.0, 0, 1, None),
    ('Lights', 'Strobehz', 'Strobe rate (Hz)', 'Float', 4.0, 0, 30, None),
    ('Camera', 'Preset', 'Camera preset', 'Menu', 'foh', None, None, (['foh', 'stageleft', 'stageright', 'drone', 'crowdpov', 'orbit'], ['FOH', 'Stage left', 'Stage right', 'Drone', 'Crowd POV', 'Orbit'])),
    ('Camera', 'Fov', 'Field of view (deg)', 'Float', 45.0, 5, 120, None),
    ('Camera', 'Orbitx', 'Orbit yaw (deg)', 'Float', 0.0, -180, 180, None),
    ('Camera', 'Orbity', 'Orbit pitch (deg)', 'Float', 0.0, -60, 60, None),
    ('Camera', 'Orbitdist', 'Distance x', 'Float', 1.0, 0.1, 4, None),
    ('Camera', 'Autoorbit', 'Auto orbit', 'Toggle', False, None, None, None),
    ('Camera', 'Orbitspeed', 'Orbit speed (deg/s)', 'Float', 5.0, -90, 90, None),
    ('Output', 'Source', 'Screen source', 'Menu', 'input', None, None, (['input', 'noise', 'ramp', 'color'], ['Input (in1)', 'Test noise', 'Test ramp', 'Test colour'])),
    ('Output', 'Quality', 'Quality', 'Menu', 'high', None, None, (['draft', 'medium', 'high'], ['Draft (1/2 res, no AA)', 'Medium (3/4 res, AA <= 2x)', 'High (full res, Antialias)'])),
    ('Output', 'Resx', 'Width', 'Int', 1920, 64, 7680, None),
    ('Output', 'Resy', 'Height', 'Int', 1080, 64, 4320, None),
    ('Output', 'Msaa', 'Antialias', 'Menu', 'aa4', None, None, (['aa1', 'aa2', 'aa4', 'aa8mid'], ['Off', '2x', '4x', '8x'])),
    ('Output', 'Showscreenonly', 'Show screen only', 'Toggle', False, None, None, None),
    ('Output', 'Exposure', 'Exposure (stops)', 'Float', 0.0, -4, 4, None),
    ('Output', 'Bloom', 'Bloom', 'Float', 0.5, 0, 3, None),
    ('Output', 'Bloomres', 'Bloom resolution', 'Menu', 'quarter', None, None, (['full', 'half', 'quarter'], ['Full (render size)', 'Half', 'Quarter (fast)'])),
    ('Output', 'Texw', 'Screen texture width', 'Int', 1920, 64, 8192, None),
    ('Audio', 'Audioreact', 'Audio to beams', 'Float', 0.0, 0, 4, None),
    ('Audio', 'Audiogain', 'Audio gain', 'Float', 1.0, 0, 20, None),
    ('Colours', 'Basecolor', 'Beam base colour', 'RGB', (1.0, 1.0, 1.0), None, None, None),
    ('Colours', 'Hazecolor', 'Haze colour', 'RGB', (0.55, 0.6, 0.7), None, None, None),
    ('Colours', 'Testcolor', 'Test colour', 'RGB', (1.0, 0.0, 0.0), None, None, None),
    ('Window', 'Opencontrols', 'Open controls window', 'Pulse', None, None, None, None),
    ('Window', 'Openview', 'Open view window', 'Pulse', None, None, None, None),
    ('Window', 'Reset', 'Reset to defaults', 'Pulse', None, None, None, None),
]
UI_COLUMNS = [['Stage', 'Haze'], ['Crowd', 'Audio', 'Camera'], ['Lights', 'Output']]

FACE_TABLE = [['name', 'width', 'height', 'fold', 'curve', 'lift'],
              ['left', '4', '6', '20', '0', '0.375'],
              ['main', '12', '6.75', '0', '0', '0'],
              ['right', '4', '6', '20', '0', '0.375']]

# ------------------------------------------------------------------ DAT texts (callbacks + helpers)
TD_HELPERS = r'''# previz_td: TD-side helpers for the callbacks (reads this COMP's parameters, calls previz_logic)
def L():
	return op('previz_logic').module

def faces_list():
	C = parent()
	rows = []
	t = op('face_table')
	for r in range(1, t.numRows):
		def num(c):
			try:
				return float(t[r, c].val)
			except Exception:
				return 0.0
		rows.append({'name': t[r, 'name'].val or 'face%d' % r, 'width': num('width'), 'height': num('height'),
		             'fold': num('fold'), 'curve': num('curve'), 'lift': num('lift')})
	return L().preset_faces(C.par.Layout.eval(), C.par.Wallw.eval(), C.par.Wallh.eval(), C.par.Curve.eval(),
	                        C.par.Sidew.eval(), C.par.Sideh.eval(), C.par.Sidefold.eval(), rows)

def layout():
	C = parent()
	return L().face_layout(faces_list(), C.par.Gap.eval(), C.par.Stageh.eval() + C.par.Screenelev.eval(),
	                       C.par.Contentmap.eval())

def faces_u():
	f = op('faces')
	return [(float(f[i, 'u0']), float(f[i, 'u1'])) for i in range(1, f.numRows)]

def wall_x():
	f = op('faces')
	xs = [float(f[i, c]) for i in range(1, f.numRows) for c in ('x0', 'x1')]
	return (min(xs), max(xs)) if xs else (-6.0, 6.0)

def wall_info():
	f = op('faces')
	if f.numRows < 2:
		return 16 / 9.0, 12.0, 6.75
	return float(f[1, 'aspect']), float(f[1, 'span']), float(f[1, 'canvas'])

def tex_res():
	a = wall_info()[0]
	w = int(parent().par.Texw.eval())
	return w, max(8, min(8192, int(round(w / max(0.05, a)))))

def audio_level():
	a = op('audio_rms')
	try:
		return float(a[0].eval()) if a is not None and a.numChans else 0.0
	except Exception:
		return 0.0

def quality():
	C = parent()
	return L().quality_settings(C.par.Quality.eval(), C.par.Resx.eval(), C.par.Resy.eval(), C.par.Msaa.eval())

def render_res():
	return quality()[:2]

def aa():
	return quality()[2]

def source_index():
	s = parent().par.Source.eval()
	if s == 'input':
		return 0 if len(parent().inputs) else 1
	return {'noise': 1, 'ramp': 2, 'color': 3}.get(s, 1)

def noise_res():
	# the test noise is smooth (period 0.6): drawn at 1/4 of the screen texture, at the wall aspect (no fit pass)
	w, h = tex_res()
	return max(8, int(w / 4)), max(8, int(h / 4))

def bloom_index():
	return {'full': 0, 'half': 1, 'quarter': 2}.get(parent().par.Bloomres.eval(), 2)

def sway_u():
	# crowd_xf time in noise cells: (fraction, whole cells), split on the CPU in double precision
	import math
	u = absTime.seconds * parent().par.Swayspeed.eval() * L().SWAY_RATE
	c = math.floor(u)
	return u - c, float(c)

REACT = {}   # the react Script CHOP's last output (name -> value), read by beams in the same frame

def react_dict():
	v = REACT if REACT else dict((c.name, c[0]) for c in op('react').chans())
	g = lambda n: v.get(n, 0.0)
	faces = []
	k = 1
	while ('f%dr' % k) in v:
		faces.append((g('f%dr' % k), g('f%dg' % k), g('f%db' % k)))
		k += 1
	return {'avg': (g('r'), g('g'), g('b')), 'dom': (g('dr'), g('dg'), g('db')),
	        'left': (g('lr'), g('lg'), g('lb')), 'right': (g('rr'), g('rg'), g('rb')), 'faces': faces}

def out_chans(scriptOp, names, n):
	# the Script CHOP keeps its channels between cooks: rebuild them only when the names / length change
	ch = scriptOp.chans()
	if scriptOp.numSamples != n or len(ch) != len(names) or [c.name for c in ch] != names:
		scriptOp.clear()
		scriptOp.numSamples = n
		ch = [scriptOp.appendChan(x) for x in names]
	return ch
'''

FACES_CB = r'''# faces: the LED wall layout as a table (one row per face), built from the Stage page + face_table
def onCook(scriptOp):
	m = op('previz_td').module
	lay = m.layout()
	scriptOp.clear()
	scriptOp.appendRow(['name', 'u0', 'u1', 'v0', 'v1', 'x0', 'z0', 'x1', 'z1', 'y0', 'y1', 'segs', 'aspect', 'span', 'canvas'])
	for f in lay['faces']:
		(x0, z0), (x1, z1) = f['cols'][0], f['cols'][-1]
		scriptOp.appendRow([f['name']] + ['%.6g' % v for v in (f['u0'], f['u1'], f['v0'], f['v1'], x0, z0, x1, z1, f['y0'], f['y1'])]
		                   + [len(f['cols']) - 1, '%.6g' % lay['aspect'], '%.6g' % lay['span_w'], '%.6g' % lay['canvas_h']])
	return
'''

WALL_CB = r'''# wall_sop: one quad strip per face, uv = where that face samples the screen texture
def onCook(scriptOp):
	m = op('../previz_td').module
	op('../faces').cook()
	pts, quads = m.L().wall_mesh(m.layout())
	scriptOp.clear()
	scriptOp.pointAttribs.create('uv')
	scriptOp.pointAttribs.create('N')
	P = []
	for (x, y, z, u, v) in pts:
		p = scriptOp.appendPoint()
		p.P = (x, y, z)
		p.uv = (u, v, 0.0)
		p.N = (0.0, 0.0, 1.0)
		P.append(p)
	for q in quads:
		poly = scriptOp.appendPoly(4, closed=True, addPoints=False)
		for k in range(4):
			poly[k].point = P[q[k]]
	return
'''

REACT_CB = r'''# react: screen colour analysis with lag -> r g b lum, dominant, left/right, per face (f1r f1g f1b ...)
# lag state lives in this module (not op storage: store/fetch on the cooking op made a cook loop)
import numpy as np
_STATE = {}

def onCook(scriptOp):
	C = parent()
	m = op('previz_td').module
	L = m.L()
	src = scriptOp.inputs[0]
	# TOP to CHOP crop full: channels r0 g0 b0 a0 ... per row (row 0 = bottom), one sample per column. One numpy read
	# (perf wave 2: the per-channel .vals reads were 56 us), then the same row-major (r, g, b) list as before.
	cols = src.numSamples
	A = src.numpyArray()
	r = A.shape[0] // 4
	grid = A[:r * 4].reshape(r, 4, cols)[:, :3, :].transpose(0, 2, 1).reshape(-1, 3).tolist()
	a = L.analyse(grid, cols, r, m.faces_u())  # plain Python: numpy (and a hand-rolled one-pass loop) were slower on 64 px under Rosetta
	names = ['r', 'g', 'b', 'lum', 'dr', 'dg', 'db', 'lr', 'lg', 'lb', 'rr', 'rg', 'rb']
	target = list(a['avg']) + [L.luma(a['avg'])] + list(a['dom']) + list(a['left']) + list(a['right'])
	for k, c in enumerate(a['faces']):
		names += ['f%dr' % (k + 1), 'f%dg' % (k + 1), 'f%db' % (k + 1)]
		target += list(c)
	prev = _STATE.get('prev')
	if not prev or len(prev) != len(target):
		prev = target
	al = L.lag_alpha(absTime.stepSeconds, C.par.Reactlag.eval())
	vals = [p + (t - p) * al for p, t in zip(prev, target)]
	_STATE['prev'] = [float(v) for v in vals]
	for ch, v in zip(m.out_chans(scriptOp, names, 1), vals):
		ch[0] = v
	m.REACT.clear()
	m.REACT.update(zip(names, np.asarray(_STATE['prev'], np.float32).tolist()))   # = what the channels hold
	return
'''

BEAMS_CB = r'''# beams: one sample per beam -> instance position, aim (rx rz), size, colour (screen-following)
import math
def onCook(scriptOp):
	C = parent()
	m = op('previz_td').module
	L = m.L()
	t = absTime.seconds
	x0, x1 = m.wall_x()
	rig = L.beam_rig(C.par.Beams.eval(), (x1 - x0) * 0.85, C.par.Trussh.eval(), C.par.Trussz.eval(), C.par.Fan.eval(),
	                 C.par.Beamtilt.eval(), C.par.Beamsweep.eval(), C.par.Beamsweepspeed.eval(), t)
	react = m.react_dict()
	fu = m.faces_u()
	base = tuple(C.parGroup.Basecolor.eval())
	gate = L.strobe_gate(t, C.par.Strobehz.eval(), C.par.Strobe.eval())
	aud = 1.0 + C.par.Audioreact.eval() * C.par.Audiogain.eval() * m.audio_level()
	haze = 0.3 * C.par.Scatter.eval() * ((0.25 + C.par.Density.eval()) if C.par.Hazeon.eval() else 0.1)
	k = C.par.Intensity.eval() * gate * aud * haze * (1.0 if C.par.Lightson.eval() else 0.0)
	ln = C.par.Beamlen.eval()
	rad = ln * math.tan(math.radians(C.par.Spread.eval() * 0.5))
	ch = dict((n, []) for n in ('tx', 'ty', 'tz', 'rx', 'rz', 'sr', 'sl', 'cr', 'cg', 'cb', 'wr', 'wg', 'wb'))
	mode, follow = C.par.Reactmode.eval(), C.par.Follow.eval()
	for (x, y, z, pan, tl, xf) in rig:
		rx, rz = L.aim_to_euler(L.dir_from_angles(pan, tl))
		col = L.lerp_follow(base, L.beam_colour(mode, xf, react, fu), follow)
		for n, v in (('tx', x), ('ty', y), ('tz', z), ('rx', rx), ('rz', rz), ('sr', rad), ('sl', ln)):
			ch[n].append(v)
		for n, v in zip(('cr', 'cg', 'cb'), col):
			ch[n].append(v * k)
		for n, v in zip(('wr', 'wg', 'wb'), col):
			ch[n].append(v * gate * aud)
	for c, n in zip(m.out_chans(scriptOp, list(ch), len(rig)), ch):
		c.vals = ch[n]
	return
'''

CROWD_CB = r'''# crowd_base: seeded audience grid (cooks only when a Crowd/Stage parameter changes)
def onCook(scriptOp):
	C = parent()
	L = op('previz_td').module.L()
	front = C.par.Stagedepth.eval() - 1.0 + C.par.Crowdgap.eval()
	n = int(C.par.Count.eval()) if C.par.Crowdon.eval() else 0
	rows = L.crowd_rows(max(1, n), C.par.Rows.eval(), C.par.Spacing.eval(), C.par.Heightvar.eval(), C.par.Seed.eval(),
	                    front, C.par.Hands.eval())
	scriptOp.clear()
	scriptOp.numSamples = len(rows)
	cols = list(zip(*rows))
	for name, k in (('tx', 0), ('tz', 1), ('s', 2), ('ry', 3), ('phase', 4)):
		scriptOp.appendChan(name).vals = list(cols[k])
	scriptOp.appendChan('hs').vals = [s * h for s, h in zip(cols[2], cols[5])]
	return
'''

CROWD_GLSL = r'''// crowd_xf: per-person instance data for crowd + hands; the sway runs here (perf wave 2, 27 Oct: replaced the
// crowd_swz / crowd_bob Noise CHOPs; twin: previz_stage_logic.crowd_sway). in0 = crowd_tex (CHOP to TOP of crowd_base:
// x = person, rows tx tz s ry phase hs). out0 = (tx, bob, tz, s): translate + body scale; out1 = (ry, rz, hs, s): rotate
// + hand scale (crowd_rot).
layout (local_size_x = 64, local_size_y = 1) in;
uniform vec4 uSw;   // x = time fraction, w = whole cells (absTime x Swayspeed x SWAY_RATE), y = Sway x 6 deg, z = Sway x 0.06 m
uint swayH(uint x) { x ^= x >> 16u; x *= 0x7feb352du; x ^= x >> 15u; x *= 0x846ca68bu; x ^= x >> 16u; return x; }
float swayV(uint person, int cell, uint salt)
{
	return float(swayH(swayH(person * 2u + salt) + uint(cell))) / 4294967295.0 * 2.0 - 1.0;
}
float swayN(uint person, uint salt)       // uniform cubic B-spline over hashed values (one cell per SWAY_RATE)
{
	float f = uSw.x;
	int c = int(uSw.w);
	float f2 = f * f, f3 = f2 * f;
	vec4 w = vec4((1.0 - f) * (1.0 - f) * (1.0 - f), 3.0 * f3 - 6.0 * f2 + 4.0, -3.0 * f3 + 3.0 * f2 + 3.0 * f + 1.0, f3) / 6.0;
	return w.x * swayV(person, c - 1, salt) + w.y * swayV(person, c, salt) + w.z * swayV(person, c + 1, salt)
	     + w.w * swayV(person, c + 2, salt);
}
float row(int i, int k) { return texelFetch(sTD2DInputs[0], ivec2(i, k), 0).r; }
void main()
{
	int i = int(gl_GlobalInvocationID.x);
	if (i >= int(uTDOutputInfo.res.z)) return;
	float rz = uSw.y * %(gain)r * swayN(uint(i), %(s0)du);
	float ty = uSw.z * %(gain)r * swayN(uint(i), %(s1)du);
	float s = row(i, 2);
	TDImageStoreOutput(0, ivec3(i, 0, 0), vec4(row(i, 0), ty, row(i, 1), s));
	TDImageStoreOutput(1, ivec3(i, 0, 0), vec4(row(i, 3), rz, row(i, 5), s));
}
'''

CAM_CB = r'''# campose: eye (tx ty tz) and target (lx ly lz) from the Camera page; auto orbit adds yaw over time
def onCook(scriptOp):
	C = parent()
	m = op('previz_td').module
	L = m.L()
	_a, span, canvas = m.wall_info()
	yaw = C.par.Orbitx.eval() + (absTime.seconds * C.par.Orbitspeed.eval() if C.par.Autoorbit.eval() else 0.0)
	eye, tgt = L.cam_pose(C.par.Preset.eval(), yaw, C.par.Orbity.eval(), C.par.Orbitdist.eval(), L.wall_scale(span, canvas))
	scriptOp.clear()
	scriptOp.numSamples = 1
	for n, v in zip(('tx', 'ty', 'tz', 'lx', 'ly', 'lz'), list(eye) + list(tgt)):
		scriptOp.appendChan(n).vals = [v]
	return
'''

HAZE_GLSL = r'''// haze: single pass (T-46 safe). in0 = render colour, in1 = camera-space depth, in2 = drifting noise
uniform vec4 uHaze;   // rgb = haze colour (incl. screen glow), a = density
uniform vec4 uPar;    // x = height falloff, y = drift offset, z = far distance, w = haze on
out vec4 fragColor;
void main(){
	vec2 uv = vUV.st;
	vec4 c = texture(sTD2DInputs[0], uv);
	float d = abs(texture(sTD2DInputs[1], uv).r);
	if (d <= 0.0001 || d > uPar.z) d = uPar.z;
	float n = texture(sTD2DInputs[2], uv * vec2(1.0, 0.6) + vec2(uPar.y, uPar.y * 0.3)).r;
	float h = clamp(exp(-uPar.x * (uv.y - 0.35)), 0.15, 3.0);
	float fog = (1.0 - exp(-uHaze.a * 0.035 * d * (0.55 + 0.9 * n) * h)) * uPar.w;
	fragColor = TDOutputSwizzle(vec4(mix(c.rgb, uHaze.rgb, fog), 1.0));
}
'''

POST_GLSL = r'''// post: haze + bloom (any size, upsampled) x exposure, at Resx x Resy (one pass; replaced a Composite + Level)
uniform vec4 uExp;    // x = 2 ^ Exposure
out vec4 fragColor;
vec4 edge(int i, vec2 uv){
	vec2 hx = 0.5 / vec2(textureSize(sTD2DInputs[i], 0));
	return texture(sTD2DInputs[i], clamp(uv, hx, 1.0 - hx));  // hold the edge (T-204)
}
void main(){
	vec2 uv = vUV.st;
	vec4 c = edge(0, uv);
	vec3 b = edge(1, uv).rgb;
	fragColor = TDOutputSwizzle(vec4((c.rgb + b) * uExp.x, c.a));
}
'''

PAREXEC = r'''# Window page pulses: open this COMP's controls / view window, reset parameters to defaults
def onPulse(par):
	C = parent()
	if par.name == 'Opencontrols':
		C.op('controls_window').par.winopen.pulse()
	elif par.name == 'Openview':
		C.op('view_window').par.winopen.pulse()
	elif par.name == 'Reset':
		for p in C.customPars:
			if p.page.name != 'Window' and p.style != 'Pulse' and not p.readOnly:
				p.val = p.default
	return
'''


def _pars(C, keep):
    """Custom parameters in place (T-70: no page/par is destroyed while panels bind to it, values stay).
    Missing pars are appended, existing ones get label/range/default/menu updated, pars not in PARS are removed."""
    pages = dict((pg.name, pg) for pg in C.customPages)
    want = set()
    for (page, name, label, style, default, mn, mx, extra) in PARS:
        want.update([name + c for c in 'rgb'] if style == 'RGB' else [name])
    for p in list(C.customPars):
        if p.name not in want and p.page.name != 'Zkit':  # the zkit panel's own page (knob size, columns) stays
            try:
                p.destroy()
            except Exception:
                pass
    for (page, name, label, style, default, mn, mx, extra) in PARS:
        pg = pages.get(page)
        if pg is None:
            pg = pages[page] = C.appendCustomPage(page)
        have = C.par[name + 'r'] if style == 'RGB' else C.par[name]
        if have is not None:
            if style == 'RGB':
                for q, v in zip([C.par[name + c] for c in 'rgb'], default):
                    q.default = v
                    q.label = label
                continue
            have.label = label
            if style == 'Menu':
                have.menuNames, have.menuLabels = extra
            if mn is not None:
                have.normMin, have.normMax = mn, mx
                have.min, have.max = mn, mx
            if style != 'Pulse':
                have.default = default
            continue
        if style == 'Float':
            p = pg.appendFloat(name, label=label)[0]
        elif style == 'Int':
            p = pg.appendInt(name, label=label)[0]
        elif style == 'Toggle':
            p = pg.appendToggle(name, label=label)[0]
        elif style == 'Pulse':
            pg.appendPulse(name, label=label)
            continue
        elif style == 'Menu':
            p = pg.appendMenu(name, label=label)[0]
            p.menuNames, p.menuLabels = extra
        elif style == 'RGB':
            ps = pg.appendRGB(name, label=label)
            for q, v in zip(ps, default):
                q.default = v
                q.val = keep.get(q.name, v)
            continue
        if mn is not None:
            p.normMin, p.normMax = mn, mx
            p.min, p.max = mn, mx
        p.default = default
        p.val = keep.get(name, default)


def _cb(o, text):
    """Script op: write the docked callbacks DAT TD made (name_callbacks)."""
    cb = o.par.callbacks.eval()
    if cb is None:
        cb = o.parent().create(textDAT, o.name + '_callbacks')
        o.par.callbacks = cb.name
        cb.dock = o
    cb.text = text
    return cb


def _geo(C, name, mat=None, render=True):
    g = C.create(geometryCOMP, name)
    for ch in list(g.children):
        ch.destroy()
    if mat:
        g.par.material = mat
    g.par.render = render
    return g


KEEP_OPS = ('controls', 'controls_window', 'view_window')  # panel + windows survive a rebuild (T-70)


def _safe_destroy():
    sd = globals().get('safe_destroy')
    if sd is None:
        sd = op('/jazib_mcp/handlers').module.safe_destroy
    return sd


def _close_windows(C):
    """Close this COMP's own windows before anything inside is rebuilt (T-70)."""
    closed = []
    for w in C.findChildren(type=windowCOMP, maxDepth=1):
        try:
            if w.isOpen:
                w.par.winclose.pulse()
                closed.append(w.name)
        except Exception:
            pass
    return closed


def _window(C, name):
    w = C.op(name)
    if w is None:
        w = C.create(windowCOMP, name)
    return w


def build(parent_path='/project1/lab'):
    P = op(parent_path)
    C = P.op(NAME)
    if C is None:
        C = P.create(baseCOMP, NAME)
    _close_windows(C)
    sd = _safe_destroy()
    for ch in list(C.children):
        if ch.name in KEEP_OPS:
            continue
        try:
            if ch.valid:
                sd(ch)  # closes windows / moves panes off first; defers if a window showed it (T-70)
        except Exception:
            pass
    _pars(C, {})
    C.comment = 'PREVIZ STAGE: any TOP in -> LED wall in a hazy hall with crowd + screen-following lights. out1 = render, out_react = colours.'
    E = lambda o, par, expr: setattr(getattr(o.par, par), 'expr', expr)

    # ---- logic + helpers
    lg = C.create(textDAT, 'previz_logic')
    lg.text = open(LOGIC_FILE).read()
    lg.comment = 'Pure logic (copy of builders/previz_stage_logic.py; tested offline)'
    hp = C.create(textDAT, 'previz_td')
    hp.text = TD_HELPERS
    hp.comment = 'TD helpers the callbacks share'
    ft = C.create(tableDAT, 'face_table')
    ft.clear()
    for r in FACE_TABLE:
        ft.appendRow(r)
    ft.comment = 'Custom wall (Layout = Custom): one row per face, left to right; fold/curve in deg, lift in m'
    fc = C.create(scriptDAT, 'faces')
    _cb(fc, FACES_CB)
    fc.comment = 'Wall layout table (computed)'

    # ---- input
    i1 = C.create(inTOP, 'in1')
    sn = C.create(noiseTOP, 'src_noise')
    sn.par.outputresolution = 'custom'
    E(sn, 'resolutionw', "op('previz_td').module.noise_res()[0]")
    E(sn, 'resolutionh', "op('previz_td').module.noise_res()[1]")
    sn.par.mono = False; sn.par.period = 0.6; sn.par.amp = 0.8; sn.par.offset = 0.4
    E(sn, 'tz', 'absTime.seconds * 0.3')
    sr = C.create(rampTOP, 'src_ramp')
    sr.par.outputresolution = 'custom'; sr.par.resolutionw = 1920; sr.par.resolutionh = 1080
    sr.par.type = 'horizontal'
    sc = C.create(constantTOP, 'src_color')
    sc.par.outputresolution = 'custom'; sc.par.resolutionw = 1920; sc.par.resolutionh = 1080
    for a, b in (('colorr', 'Testcolorr'), ('colorg', 'Testcolorg'), ('colorb', 'Testcolorb')):
        E(sc, a, "parent().par.%s" % b)
    sw = C.create(switchTOP, 'src')
    for k, o in enumerate((i1, sn, sr, sc)):
        sw.inputConnectors[k].connect(o)
    E(sw, 'index', "op('previz_td').module.source_index()")
    ft_ = C.create(fitTOP, 'fit')
    ft_.inputConnectors[0].connect(sw)
    ft_.par.fit = 'fill'
    ft_.par.outputresolution = 'custom'
    E(ft_, 'resolutionw', "op('previz_td').module.tex_res()[0]")
    E(ft_, 'resolutionh', "op('previz_td').module.tex_res()[1]")
    ss = C.create(switchTOP, 'screen_sel')  # test noise is drawn at the wall aspect: skips the fit pass
    ss.inputConnectors[0].connect(ft_)
    ss.inputConnectors[1].connect(sn)
    E(ss, 'index', "1 if op('previz_td').module.source_index() == 1 else 0")
    st = C.create(nullTOP, 'screen_tex')
    st.inputConnectors[0].connect(ss)

    # ---- analysis
    ad = C.create(resolutionTOP, 'an_down')
    ad.inputConnectors[0].connect(st)
    ad.par.outputresolution = 'custom'; ad.par.resolutionw = 16; ad.par.resolutionh = 4
    ad.par.inputfiltertype = 'mipmap'
    ac = C.create(toptoCHOP, 'an_chop')
    ac.par.top = 'an_down'
    ac.par.crop = 'full'
    clk = C.create(constantCHOP, 'clock')
    clk.par.name0 = 't'
    E(clk, 'value0', 'absTime.seconds')
    clk.comment = 'time tick: makes the react / beams / camera scripts cook every frame'
    rc = C.create(scriptCHOP, 'react')
    rc.inputConnectors[0].connect(ac)
    rc.inputConnectors[1].connect(clk)
    _cb(rc, REACT_CB)
    orc = C.create(outCHOP, 'out_react')
    orc.inputConnectors[0].connect(rc)

    # ---- materials
    wm = C.create(constantMAT, 'wall_mat')
    wm.par.colormap = 'screen_tex'
    for a in ('colorr', 'colorg', 'colorb'):
        E(wm, a, 'parent().par.Screenemit')
    wm.par.cullface = 'neither'
    sm = C.create(phongMAT, 'stage_mat')
    sm.par.diffr, sm.par.diffg, sm.par.diffb = 0.18, 0.18, 0.2
    sm.par.specr = sm.par.specg = sm.par.specb = 0.15
    sm.par.ambr = sm.par.ambg = sm.par.ambb = 0.2
    cm = C.create(phongMAT, 'crowd_mat')
    cm.par.diffr, cm.par.diffg, cm.par.diffb = 0.22, 0.2, 0.2
    cm.par.specr = cm.par.specg = cm.par.specb = 0.05
    cm.par.ambr = cm.par.ambg = cm.par.ambb = 0.1
    fr = C.create(rampTOP, 'beam_fade')
    fr.par.outputresolution = 'custom'; fr.par.resolutionw = 8; fr.par.resolutionh = 256
    fr.par.type = 'vertical'
    bm = C.create(constantMAT, 'beam_mat')
    bm.par.colormap = 'beam_fade'
    bm.par.applypointcolor = True
    bm.par.blending = True
    bm.par.srcblend = 'one'; bm.par.destblend = 'one'
    bm.par.depthwriting = False
    bm.par.cullface = 'neither'

    # ---- stage geometry
    gw = _geo(C, 'wall', 'wall_mat')
    ws = gw.create(scriptSOP, 'wall_sop')
    _cb(ws, WALL_CB)
    ws.render = ws.display = True
    gd = _geo(C, 'deck', 'stage_mat')
    db = gd.create(boxSOP, 'deck_box')
    E(db, 'sizex', "op('../previz_td').module.wall_x()[1] - op('../previz_td').module.wall_x()[0] + 6")
    E(db, 'sizey', 'parent(2).par.Stageh')
    E(db, 'sizez', 'parent(2).par.Stagedepth')
    E(db, 'ty', 'parent(2).par.Stageh * 0.5')
    E(db, 'tz', 'parent(2).par.Stagedepth * 0.5 - 1')
    db.render = db.display = True
    gt = _geo(C, 'truss', 'stage_mat')
    tb = gt.create(boxSOP, 'truss_bar')
    E(tb, 'sizex', "op('../previz_td').module.wall_x()[1] - op('../previz_td').module.wall_x()[0] + 4")
    tb.par.sizey = 0.4; tb.par.sizez = 0.4
    E(tb, 'ty', 'parent(2).par.Trussh + 0.3')
    E(tb, 'tz', 'parent(2).par.Trussz')
    tb.render = tb.display = True
    gf = _geo(C, 'floor', 'stage_mat')
    fg = gf.create(gridSOP, 'floor_grid')
    fg.par.sizex = 200; fg.par.sizey = 200; fg.par.rows = 2; fg.par.cols = 2
    fg.par.orient = 'zx'
    fg.render = fg.display = True

    # ---- crowd
    cb_ = C.create(scriptCHOP, 'crowd_base')
    _cb(cb_, CROWD_CB)
    # sway on the GPU (perf wave 2): crowd_base (static) -> crowd_tex -> crowd_xf (compute, 2 buffers) -> TOP instancing
    ctx = C.create(choptoTOP, 'crowd_tex')
    ctx.par.chop = 'crowd_base'
    ctx.par.dataformat = 'r'
    ctx.par.format = 'r32float'
    ctx.comment = 'crowd_base as a 32-bit TOP (x = person, rows tx tz s ry phase hs); cooks only when the crowd changes'
    cgl = C.create(textDAT, 'crowd_glsl')
    Lm = lg.module
    cgl.text = CROWD_GLSL % {'gain': Lm.SWAY_GAIN, 's0': Lm.SWAY_SALTS[0], 's1': Lm.SWAY_SALTS[1]}
    cx = C.create(glslTOP, 'crowd_xf')
    cx.par.mode = 'compute'
    cx.par.computedat = 'crowd_glsl'
    cx.inputConnectors[0].connect(ctx)
    cx.par.outputresolution = 'custom'
    E(cx, 'resolutionw', "max(1, op('crowd_base').numSamples)")
    cx.par.resolutionh = 1
    cx.par.format = 'rgba32float'
    cx.par.numcolorbufs = 2
    cx.par.inputfiltertype = 'nearest'
    cx.seq.vec.numBlocks = 1
    cx.par.vec0name = 'uSw'
    # simple expressions (native, double precision; T-214: a module call per uniform is the Python path); the
    # fraction and the whole cells use the same % so they always add back to u (= previz_td.sway_u)
    u_ = 'absTime.seconds * parent().par.Swayspeed * %r' % Lm.SWAY_RATE
    E(cx, 'vec0valuex', '(%s) %% 1' % u_)
    E(cx, 'vec0valuey', 'parent().par.Sway * 6')
    E(cx, 'vec0valuez', 'parent().par.Sway * 0.06')
    E(cx, 'vec0valuew', '%s - (%s) %% 1' % (u_, u_))
    cx.comment = 'Per-person instance data + sway (GPU): out0 tx bob tz s, out1 ry rz hs s (crowd_rot)'
    cgl.dock = cx
    crt = C.create(renderselectTOP, 'crowd_rot')
    crt.par.top = 'crowd_xf'
    crt.par.bufferindex = 1   # 31550 name (not colorbufferindex)
    crt.comment = 'crowd_xf buffer 1: ry rz hs s'
    gc = _geo(C, 'crowd', 'crowd_mat')
    parts = []
    for nm, kind, sz, ty in (('head', sphereSOP, (0.11, 0.13, 0.11), 1.62), ('torso', boxSOP, (0.42, 0.62, 0.25), 1.18),
                             ('legs', boxSOP, (0.34, 0.86, 0.2), 0.43)):
        s = gc.create(kind, nm)
        if kind == sphereSOP:
            s.par.radx, s.par.rady, s.par.radz = sz
            s.par.rows = 6; s.par.cols = 8
        else:
            s.par.sizex, s.par.sizey, s.par.sizez = sz
        s.par.ty = ty
        parts.append(s)
    bm_ = gc.create(mergeSOP, 'body')
    for k, s in enumerate(parts):
        bm_.inputConnectors[k].connect(s)
    bm_.render = bm_.display = True
    gh = _geo(C, 'hands', 'crowd_mat')
    arm = gh.create(boxSOP, 'arm')
    arm.par.sizex, arm.par.sizey, arm.par.sizez = 0.09, 0.62, 0.09
    arm.par.tx, arm.par.ty = 0.2, 1.75
    arm.par.rz = -12
    arm.render = arm.display = True
    for g, sop, sy in ((gc, 'crowd_xf', 'a'), (gh, 'crowd_rot', 'b')):   # TOP instancing: channels r g b a
        g.par.instancing = True
        g.par.instanceop = 'crowd_xf'
        g.par.instancetop = 'crowd_xf'
        g.par.instancerop = 'crowd_rot'
        g.par.instancesop = sop
        g.par.instancetx, g.par.instancety, g.par.instancetz = 'r', 'g', 'b'
        g.par.instancery, g.par.instancerz = 'r', 'g'
        g.par.instancesx, g.par.instancesy, g.par.instancesz = 'a', sy, 'a'
        E(g, 'render', 'parent().par.Crowdon')

    # ---- lights
    ia = C.create(inCHOP, 'in_audio')
    ar = C.create(analyzeCHOP, 'audio_rms')
    ar.inputConnectors[0].connect(ia)
    ar.par.function = 'rmspower'
    bc = C.create(scriptCHOP, 'beams')
    bc.inputConnectors[0].connect(rc)
    bc.inputConnectors[1].connect(clk)
    _cb(bc, BEAMS_CB)
    gb = _geo(C, 'beam_geo', 'beam_mat')
    tu = gb.create(tubeSOP, 'cone')
    tu.par.rad1 = 0.0; tu.par.rad2 = 1.0; tu.par.height = 1.0; tu.par.ty = -0.5
    tu.par.rows = 2; tu.par.cols = 24; tu.par.cap = False
    tu.par.texture = 'rowcol'
    tu.render = tu.display = True
    gb.par.instancing = True
    gb.par.instanceop = 'beams'
    gb.par.instancetx, gb.par.instancety, gb.par.instancetz = 'tx', 'ty', 'tz'
    gb.par.instancerx, gb.par.instancerz = 'rx', 'rz'
    gb.par.instancesx, gb.par.instancesy, gb.par.instancesz = 'sr', 'sl', 'sr'
    gb.par.instancecolorop = 'beams'
    gb.par.instancer, gb.par.instanceg, gb.par.instanceb = 'cr', 'cg', 'cb'
    gb.par.drawpriority = -1
    E(gb, 'render', 'parent().par.Lightson')
    sp = C.create(lightCOMP, 'spill')
    sp.par.lighttype = 'point'
    E(sp, 'ty', "parent().par.Stageh + parent().par.Screenelev + parent().par.Wallh * 0.5")
    sp.par.tz = 2.0
    for a, ch in (('cr', 'r'), ('cg', 'g'), ('cb', 'b')):
        E(sp, a, "op('react')['%s'] * parent().par.Screenemit * parent().par.Crowdlit * 1.5" % ch)
    wt = C.create(nullCOMP, 'wash_target')
    E(wt, 'tz', 'parent().par.Stagedepth + parent().par.Crowdgap + 6')
    wa = C.create(lightCOMP, 'wash')
    wa.par.lighttype = 'cone'
    wa.par.coneangle = 70; wa.par.conedelta = 20
    E(wa, 'ty', 'parent().par.Trussh')
    E(wa, 'tz', 'parent().par.Trussz')
    wa.par.lookat = 'wash_target'
    for a, ch in (('cr', 'wr'), ('cg', 'wg'), ('cb', 'wb')):
        E(wa, a, "(sum(op('beams')['%s'].vals) / max(1, op('beams').numSamples)) * parent().par.Wash * parent().par.Lightson" % ch)
    am = C.create(ambientlightCOMP, 'amb')
    am.par.cr = am.par.cg = am.par.cb = 0.04

    # ---- camera
    cp = C.create(scriptCHOP, 'campose')
    cp.inputConnectors[0].connect(clk)
    _cb(cp, CAM_CB)
    ct = C.create(nullCOMP, 'cam_target')
    cam = C.create(cameraCOMP, 'cam')
    for a, ch in (('tx', 'lx'), ('ty', 'ly'), ('tz', 'lz')):
        E(ct, a, "op('campose')['%s']" % ch)
    for a in ('tx', 'ty', 'tz'):
        E(cam, a, "op('campose')['%s']" % a)
    cam.par.lookat = 'cam_target'
    E(cam, 'fov', 'parent().par.Fov')
    cam.par.near = 0.1; cam.par.far = 400

    # ---- render + haze + output
    rd = C.create(renderTOP, 'render')
    rd.par.camera = 'cam'
    rd.par.geometry = 'wall deck truss floor crowd hands beam_geo'
    rd.par.lights = 'spill wash amb'
    rd.par.outputresolution = 'custom'
    E(rd, 'resolutionw', "op('previz_td').module.render_res()[0]")
    E(rd, 'resolutionh', "op('previz_td').module.render_res()[1]")
    rd.par.format = 'rgba16float'
    E(rd, 'antialias', "op('previz_td').module.aa()")
    rd.par.bgcolorr = rd.par.bgcolorg = rd.par.bgcolorb = 0.0
    dp = C.create(depthTOP, 'depth')
    dp.par.op = 'render'
    dp.par.depthspace = 'cameraspace'
    dp.par.pixelformat = 'r16float' if 'r16float' in dp.par.pixelformat.menuNames else 'rgba16float'
    hn = C.create(noiseTOP, 'haze_noise')
    hn.par.outputresolution = 'custom'; hn.par.resolutionw = 256; hn.par.resolutionh = 144
    hn.par.period = 0.5; hn.par.amp = 0.5; hn.par.offset = 0.5
    E(hn, 'tz', 'absTime.seconds * parent().par.Drift * 2')
    hg = C.create(textDAT, 'haze_glsl')
    hg.text = HAZE_GLSL
    hz = C.create(glslTOP, 'haze')
    hz.par.pixeldat = 'haze_glsl'
    hz.inputConnectors[0].connect(rd)
    hz.inputConnectors[1].connect(dp)
    hz.inputConnectors[2].connect(hn)
    hz.par.outputresolution = 'useinput'
    hz.par.format = 'rgba16float'
    hz.seq.vec.numBlocks = 2
    hz.par.vec0name = 'uHaze'
    E(hz, 'vec0valuex', "parent().par.Hazecolorr * 0.22 + op('react')['r'] * parent().par.Hazeglow * parent().par.Screenemit * 0.5")
    E(hz, 'vec0valuey', "parent().par.Hazecolorg * 0.22 + op('react')['g'] * parent().par.Hazeglow * parent().par.Screenemit * 0.5")
    E(hz, 'vec0valuez', "parent().par.Hazecolorb * 0.22 + op('react')['b'] * parent().par.Hazeglow * parent().par.Screenemit * 0.5")
    E(hz, 'vec0valuew', 'parent().par.Density')
    hz.par.vec1name = 'uPar'
    E(hz, 'vec1valuex', 'parent().par.Falloff')
    E(hz, 'vec1valuey', 'absTime.seconds * parent().par.Drift')
    hz.par.vec1valuez = 120.0
    E(hz, 'vec1valuew', '1 if parent().par.Hazeon else 0')
    hg.dock = hz
    # bloom on a smaller copy (Bloomres; Full = the haze image itself), added back in post (perf wave 27 Oct)
    bh = C.create(resolutionTOP, 'bloom_half')
    bh.inputConnectors[0].connect(hz)
    bh.par.outputresolution = 'half'
    bh.par.inputfiltertype = 'linear'  # exact 2x2 box at half size
    bq = C.create(resolutionTOP, 'bloom_quarter')
    bq.inputConnectors[0].connect(bh)
    bq.par.outputresolution = 'half'
    bq.par.inputfiltertype = 'linear'
    bs = C.create(switchTOP, 'bloom_sel')
    for k, o in enumerate((hz, bh, bq)):
        bs.inputConnectors[k].connect(o)
    E(bs, 'index', "op('previz_td').module.bloom_index()")
    bl = C.create(bloomTOP, 'bloom')
    bl.inputConnectors[0].connect(bs)
    bl.par.output = 'bloom'
    E(bl, 'bloomintensity', 'parent().par.Bloom')
    bo = C.create(constantTOP, 'bloom_off')
    bo.par.outputresolution = 'custom'; bo.par.resolutionw = 8; bo.par.resolutionh = 8
    bo.par.colorr = bo.par.colorg = bo.par.colorb = 0.0
    bo.par.alpha = 0.0
    bg = C.create(switchTOP, 'bloom_gate')  # Bloom 0: the bloom chain does not cook
    bg.inputConnectors[0].connect(bo)
    bg.inputConnectors[1].connect(bl)
    E(bg, 'index', '1 if parent().par.Bloom > 0 else 0')
    pg_ = C.create(textDAT, 'post_glsl')
    pg_.text = POST_GLSL
    gr = C.create(glslTOP, 'post')
    gr.par.pixeldat = 'post_glsl'
    gr.inputConnectors[0].connect(hz)
    gr.inputConnectors[1].connect(bg)
    gr.par.outputresolution = 'custom'  # Quality renders smaller; out1 stays Resx x Resy
    E(gr, 'resolutionw', 'parent().par.Resx')
    E(gr, 'resolutionh', 'parent().par.Resy')
    gr.par.format = 'rgba16float'
    gr.seq.vec.numBlocks = 1
    gr.par.vec0name = 'uExp'
    E(gr, 'vec0valuex', '2 ** parent().par.Exposure')
    pg_.dock = gr
    sh = C.create(switchTOP, 'show')
    sh.inputConnectors[0].connect(gr)
    sh.inputConnectors[1].connect(st)
    E(sh, 'index', '1 if parent().par.Showscreenonly else 0')
    o1 = C.create(outTOP, 'out1')
    o1.inputConnectors[0].connect(sh)

    # ---- controls (autoUI sections in columns) + windows
    _controls(C)
    vw = _window(C, 'view_window')
    vw.par.winop = 'out1'
    vw.par.title = NAME + ' view'
    vw.par.winw = 960; vw.par.winh = 540
    pe = C.create(parameterexecuteDAT, 'controls_open')
    pe.par.op = C
    pe.par.pars = 'Opencontrols Openview Reset'
    pe.par.valuechange = False
    pe.par.onpulse = True
    pe.text = PAREXEC
    pe.par.active = True
    C.par.opviewer = 'out1'
    C.viewer = True
    for o in C.children:
        if o.family in ('TOP', 'CHOP', 'SOP') or o.OPType in ('scriptDAT', 'tableDAT'):
            try:
                o.viewer = True
            except Exception:
                pass
    for g in (gw, gd, gt, gf, gc, gh, gb):
        for o in g.children:
            o.viewer = True
    layout(C)
    return C


def _ui_sig():
    return repr([(p[0], p[1], p[2], p[3], p[5], p[6], p[7]) for p in PARS]) + repr(UI_COLUMNS)


def _zkit_refresh(comp):
    """The COMP carries a zkit panel (builders/zkit.py, rolled out 26 Oct): refresh it in place (T-70 safe) instead
    of making autoUI widgets. None when there is no kit panel."""
    p_ = comp.op('controls')
    if p_ is None or p_.op('zk_rt') is None:
        return None
    ns_ = dict(globals())
    exec(open('~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/zkit.py').read(), ns_)
    return ns_['build_controls'](comp.path)


def _controls(C):
    """Controls panel, T-70 safe: kept as-is when the parameter set is unchanged; otherwise a new panel is built
    beside it, the window is pointed at it, and the old one goes through safe_destroy (never a plain destroy)."""
    if _zkit_refresh(C) is not None:
        return C.op('controls')
    old = C.op('controls')
    sig = _ui_sig()
    if old is not None and C.fetch('pv_ui_sig', '', search=False) == sig:
        win = _window(C, 'controls_window')
        win.par.winop = 'controls'
        win.par.title = NAME + ' controls'
        return old
    ctrl = _build_panel(C, 'controls_new')
    win = _window(C, 'controls_window')
    if old is not None:
        # windows were closed by _close_windows, so safe_destroy would destroy at once; defer it anyway so the UI
        # thread never draws a panel destroyed under it in the same frame (T-70)
        op('/jazib_mcp/handlers').module.ui_release(old)  # close any window on it, move panes off
        oid = int(old.id)
        old.name = 'controls_gone%d' % oid
        old.allowCooking = False
        run("o = op(%d)\nif o is not None: o.destroy()" % oid, delayFrames=5, delayRef=op.TDResources)
    ctrl.name = 'controls'
    win.par.winop = 'controls'
    win.par.title = NAME + ' controls'
    win.par.winw = int(ctrl.par.w) + 20
    win.par.winh = int(ctrl.par.h) + 28
    C.store('pv_ui_sig', sig)
    return ctrl


def _build_panel(C, name):
    au = op('/project1/show/tools/autoUI')
    ctrl = C.create(containerCOMP, name)
    ctrl.par.align = 'horizlr'
    ctrl.comment = "CONTROLS: sliders bound to this COMP's own parameters (works with or without this panel)"
    colw = 330
    heights = []
    old = (au.par.Pagetabs.eval(), au.par.Pagescope.eval(), au.par.Header.eval() if hasattr(au.par, 'Header') else None)
    try:
        for ci, pages in enumerate(UI_COLUMNS):
            col = ctrl.create(containerCOMP, 'col%d' % (ci + 1))
            col.par.align = 'verttb'
            col.par.w = colw
            colh = 0
            for k, pgname in enumerate(pages):
                sec = col.create(containerCOMP, 'sec_' + pgname.lower())
                sec.par.w = colw
                sec.par.align = 'verttb'
                sec.par.alignorder = k
                au.par.Pagetabs = False
                au.par.Pagescope = pgname
                au.ext.AutoUIExt.GenerateUI(customComp=C, ui=sec, shortcutDialog=False)
                for w in sec.children:
                    w.par.hmode = 'fill'
                    if hasattr(w.par, 'clone'):
                        w.par.enablecloning = False
                        w.par.clone = ''
                hd = sec.op('header')
                if hd is not None and hasattr(hd.par, 'Headerlabel'):
                    hd.par.Headerlabel = pgname.upper()
                sec.par.h = sum(int(c.par.h) for c in sec.children if c.isPanel) + 4
                colh += int(sec.par.h)
            col.par.h = colh
            col.par.alignorder = ci
            heights.append(colh)
    finally:
        au.par.Pagetabs = old[0]
        au.par.Pagescope = old[1]
    ctrl.par.w = colw * len(UI_COLUMNS)
    ctrl.par.h = max(heights) if heights else 200
    for col in ctrl.findChildren(type=containerCOMP, maxDepth=1):
        col.par.h = ctrl.par.h  # equal heights: verttb then packs every column from the top (no gap above)
    return ctrl


STAGES = [
    {'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window', 'view_window', 'controls_open'],
     'body': 'Panel bound to the COMP parameters; Window page pulses open it / the view'},
    {'title': '1 Screen input', 'role': 'input', 'ops': ['in1', 'src_noise', 'src_ramp', 'src_color', 'src', 'fit', 'screen_sel', 'screen_tex'],
     'body': 'Source menu: in1 or a test pattern -> fit to the wall aspect'},
    {'title': '2 Wall layout', 'role': 'process', 'ops': ['previz_logic', 'previz_td', 'face_table', 'faces'],
     'body': 'Layout menu or face_table -> faces (positions + UV windows)'},
    {'title': '3 Screen analysis', 'role': 'process', 'ops': ['an_down', 'an_chop', 'clock', 'react', 'out_react'],
     'body': '16x4 colours -> avg / dominant / left-right / per face, lagged'},
    {'title': '4 Stage + wall', 'role': 'process', 'ops': ['wall_mat', 'wall', 'stage_mat', 'deck', 'truss', 'floor'],
     'body': 'LED faces textured with the screen, deck, truss, floor'},
    {'title': '5 Crowd', 'role': 'process', 'ops': ['crowd_base', 'crowd_tex', 'crowd_xf', 'crowd_rot', 'crowd_mat', 'crowd', 'hands'],
     'body': 'Seeded grid -> crowd_xf (GPU: per-person transform + noise sway) -> TOP-instanced bodies + raised hands'},
    {'title': '6 Lights', 'role': 'process', 'ops': ['in_audio', 'audio_rms', 'beams', 'beam_fade', 'beam_mat', 'beam_geo', 'spill', 'wash_target', 'wash', 'amb'],
     'body': 'Beams take the screen colour (Follow, React mode); spill + wash light the crowd'},
    {'title': '7 Camera', 'role': 'process', 'ops': ['campose', 'cam_target', 'cam'],
     'body': 'Preset + orbit -> eye and target'},
    {'title': '8 Render, haze, output', 'role': 'output', 'ops': ['render', 'depth', 'haze_noise', 'haze', 'bloom_half', 'bloom_quarter', 'bloom_sel', 'bloom', 'bloom_off', 'bloom_gate', 'post', 'show', 'out1'],
     'body': 'Render -> depth haze (single pass) -> bloom at Bloomres -> post (haze + bloom, exposure, Resx x Resy) -> out1'},
]


def layout(C):
    h = op('/jazib_mcp/handlers').module
    return h.layout_stages(C, STAGES, True, arrange='mixed')
