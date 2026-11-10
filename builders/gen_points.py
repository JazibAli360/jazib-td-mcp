# gen_points builder - GEN_points: additive point generators (FX0 GEN_points: G04 density2d, G03 attractor3d,
# G01 streamlines, G-FORM form, ...) in the GEN_pattern rack. The rack (builders/gen_pattern.py: slots table, Cross +
# Switch per slot, background bg / in1 / test clip, rack Drive = Bpm / beat CHOP / audio level, Panic, add / remove /
# rewire, preset / freeze) is exec'd and reused as is; only the module network differs: every module is the same
# POINTS ENGINE (one design, proven pieces of this repo):
#   state  compute GLSL rgba32float side x side, one texel per point (+ 1 reserved clock texel: last t, frame, epoch),
#          state_fb = last frame (Feedback TOP). Module GLSL: pt_seed(i) / pt_step(i, s, dt). dt = module clock delta
#          (Speed 0 / freeze = hold). Effectors (shared /project1/effectors, Effon default off) via builders/effectors.py:
#          particle forces / kill / spawn (PXE_PARTICLES) or per-point push / dissolve (PXE_POINTS) in this pass.
#   render Grid POP side x side points -> geo (Select POP) with `mat` (GLSL MAT: vertex reads the state texel at
#          TDPos(), module pt_place() -> world point + colour, 2D fit or 3D orbit camera -> clip space; 1-px points or
#          sprites; additive one/one, depth off) -> Render TOP rgba32float (GN_physarum's exact scatter-add, T-112).
#   acc    compute: acc = render + Persist x last acc (trails / long exposure density).
#   look   compute: tone (soft / linear / log density with vibrancy, Draves) + mip glow + beat flash, blended over the
#          slot input (replace / add / screen / lighten / alpha out premultiplied). out_sel: Amount 0 = input untouched.
# No POP compute buffers, no attribute layouts, no POP loops (T-124): positions live in a TOP; the POP is a plain grid.
# Pure maths mirror: builders/gen_points_logic.py. Doc + LIVE CHECKS: docs/builds/gen_points.md.
# Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/gen_points.py').read(), ns)
#   ns['build']('/project1/lab')                        # rack + 'density2d1' on first build; idempotent
#   ns['add']('/project1/lab/GEN_points', 'attractor3d') # attractor3d1, wired last (zkit panel + presets)
#   ns['preset'](inst, 2); ns['freeze'](inst); ns['probe'](inst); ns['check_step'](inst); ns['check_render'](inst)
# T-70 safe (_sd = safe_destroy), no functions in op storage (T-67), no TOP readback in build (T-74). ASCII only.
import math
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
with open(os.path.join(HERE, 'gen_pattern.py')) as _fh:
    exec(_fh.read(), globals())      # the rack; its functions look module_ns / shared_pages / _module_network /
                                     # TOKENS / NAME / MODULES up in this namespace at call time

NAME = 'GEN_points'
MODULES = ['density2d', 'attractor3d', 'streamlines', 'form', 'flame', 'lsystem', 'graph', 'sparkle', 'polytope4d', 'hyperspace', 'mirrorball', 'nbody']
FIRST = 'density2d'
GLSL_DIR = os.path.join(HERE, 'glsl')
PLOGIC_FILE = os.path.join(HERE, 'gen_points_logic.py')
EFFECTORS_FILE = os.path.join(HERE, 'effectors.py')
PX_COMMON_FILE = os.path.join(GLSL_DIR, 'px_common.glsl')


def module_ns(module):
    ns = {}
    with open(os.path.join(HERE, 'gen_points_%s.py' % module)) as fh:
        exec(fh.read(), ns)
    return ns


def _read(path):
    with open(path) as fh:
        return fh.read()


# ------------------------------------------------------------------ shared pages
BLENDS_P = ['replace', 'add', 'screen', 'lighten', 'alpha']
BLEND_P_LABELS = ['Replace (bg colour + points)', 'Add', 'Screen', 'Lighten', 'Alpha out (premultiplied)']
TONEMAPS = ['soft', 'linear', 'log']
TONEMAP_LABELS = ['Soft (1 - exp)', 'Linear', 'Log density (flame, Vibrancy)']
SPRITES = ['disc', 'star', 'square', 'glint']

POINTS_PAGE = ('Points', [
    ('Count', 'Int', 65536, {'min': 1024, 'max': 1048576, 'label': 'Points'}),
    ('Size', 'Float', 1.0, {'min': 1, 'max': 16, 'label': 'Point size px (1 = exact dust)'}),
    ('Sprite', 'Menu', 'disc', {'names': SPRITES, 'labels': ['Soft disc', 'Star glint', 'Square',
                                                            'Glint (core + rays)']}),
    ('Rays', 'Int', 4, {'min': 2, 'max': 12, 'label': 'Glint rays'}),
    ('Raywidth', 'Float', 0.06, {'min': 0.005, 'max': 0.5, 'label': 'Glint ray width'}),
    ('Rayangle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Glint ray angle deg'}),
    ('Intensity', 'Float', 1.0, {'min': 0, 'max': 8, 'label': 'Intensity'}),
    ('Persist', 'Float', 0.0, {'min': 0, 'max': 0.999, 'label': 'Trail persistence (0 = none)'}),
    ('Quality', 'Float', 1.0, {'min': 0.25, 'max': 1, 'label': 'Render scale'}),
    ('Precision', 'Menu', 'half', {'names': ['half', 'float'], 'labels': ['16-bit float render (faster)',
                                                                       '32-bit float render (exact sums)']}),
    ('Respawn', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Respawn share per s'}),
    ('Resetcount', 'Int', 0, {'min': 0, 'max': 100, 'label': 'Reset count (Reset +1)'}),
    ('Reset', 'Pulse', None, {'label': 'Reset (re-seed)'}),
])
LOOK_PAGE = ('Look', [
    ('Palette', 'Menu', 'duo', {'names': PALETTES, 'labels': PAL_LABELS}),
    ('Spread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Palette spread'}),
    ('Offset', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Palette offset'}),
    ('Huecycle', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Palette cycle /s'}),
    ('Colora', 'RGB', (0.25, 0.55, 1.0), {'label': 'Colour A'}),
    ('Colorb', 'RGB', (1.0, 0.75, 0.3), {'label': 'Colour B'}),
    ('Tonemap', 'Menu', 'soft', {'names': TONEMAPS, 'labels': TONEMAP_LABELS}),
    ('Exposure', 'Float', 0.0, {'min': -8, 'max': 8, 'label': 'Exposure (stops)'}),
    ('Gamma', 'Float', 1.0, {'min': 0.2, 'max': 4, 'label': 'Gamma'}),
    ('Vibrancy', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Vibrancy (log)'}),
    ('Glow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Glow'}),
    ('Glowsize', 'Float', 2.0, {'min': 0, 'max': 6, 'label': 'Glow size (mip level)'}),
    ('Beatflash', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Beat pulse -> brightness'}),
    ('Bgcolor', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background (Replace)'}),
    ('Blend', 'Menu', 'add', {'names': BLENDS_P, 'labels': BLEND_P_LABELS}),
    ('Normalize', 'Menu', 'density', {'names': ['density', 'off'],
                                      'labels': ['Per point (even spread = 1)', 'Off (raw sums, sprites)']}),
])
VIEW2D_PAGE = ('View', [
    ('Fit', 'Float', 1.0, {'min': 0.1, 'max': 8, 'label': 'Zoom'}),
    ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate deg'}),
    ('Rotspeed', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Rotate deg/s'}),
    ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
    ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
    ('Fold', 'Int', 1, {'min': 1, 'max': 12, 'label': 'Rotational copies (fold)'}),
])
VIEW3D_PAGE = ('View', [
    ('Yaw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Yaw deg'}),
    ('Pitch', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Pitch deg'}),
    ('Orbit', 'Float', 6.0, {'min': -90, 'max': 90, 'label': 'Orbit deg/s'}),
    ('Distance', 'Float', 3.0, {'min': 0.5, 'max': 20, 'label': 'Camera distance'}),
    ('Fov', 'Float', 40.0, {'min': 5, 'max': 120, 'label': 'Field of view deg'}),
    ('Depthfade', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Depth fade (near brighter)'}),
])


def shared_pages(kind):
    """GEN_points: Drive (rack-shared, gen_pattern) + Points + Look + View (2D fit or 3D orbit camera)."""
    return [DRIVE_PAGE, POINTS_PAGE, LOOK_PAGE, VIEW3D_PAGE if kind == '3d' else VIEW2D_PAGE]


# ------------------------------------------------------------------ expressions / tokens
SIDE_E = "max(2, int(math.ceil(math.sqrt(max(int(parent().par.Count.eval()), 1) + 1))))"
OW_E, OH_E = "op('in1').width", "op('in1').height"
RW_E = "max(1, int(op('in1').width * parent().par.Quality.eval()))"
RH_E = "max(1, int(op('in1').height * parent().par.Quality.eval()))"
TOKENS = dict(TOKENS)
TOKENS.update({'W': 'float(%s)' % OW_E, 'H': 'float(%s)' % OH_E, 'RW': 'float(%s)' % RW_E, 'RH': 'float(%s)' % RH_E,
               'side': 'float(%s)' % SIDE_E})

DRV_U = [('uDrv', ['$t', '$step', '$age', '$level']), ('uBeat', ['{Beatgain}', '{Beatdecay}', '{Audiogain}', '{Seed}'])]
PAL_U = [('uPal', ['{Palette#}', '{Spread}', '{Offset}', '{Huecycle}']),
         ('uCa', ['{Colorar}', '{Colorag}', '{Colorab}', '0']),
         ('uCb', ['{Colorbr}', '{Colorbg}', '{Colorbb}', '0'])]


def state_spec(M):
    epoch = "({Resetcount}) * 64 + (%s) + 1" % M.get('EPOCH', '0')
    return DRV_U + [('uSt', ['{Count}', '$side', epoch, '0.1']),
                    ('uSt2', ['{Respawn}', '$W / max($H, 1.0)', '$W', '$H'])] + M['UNIFORMS']


def view_spec(M):
    if M['KIND'] == '3d':
        return [('uView', ['{Yaw}', '{Pitch}', '{Distance}', '{Fov}']), ('uView2', ['{Orbit}', '{Depthfade}', '0', '0'])]
    return [('uView', ['{Fit}', '{Rotate}', '{Centerx}', '{Centery}']), ('uView2', ['{Rotspeed}', '0', '0', '0'])]


def mat_spec(M):
    fold = '{Fold}' if M['KIND'] == '2d' else '1'
    return DRV_U + [('uV', ['{Count}', '$side', '{Size}', '{Intensity}']), ('uV2', ['$RW', '$RH', fold, '{Sprite#}']),
                    ('uV3', ['{Rays}', '{Raywidth}', '{Rayangle}', '0'])] + view_spec(M) + PAL_U + M['UNIFORMS']


LOOK_SPEC = DRV_U + [('uLk', ['{Tonemap#}', '{Exposure}', '{Gamma}', '{Vibrancy}']),
                     ('uLk2', ['{Glow}', '{Glowsize}', '$RW * $RH', '{Blend#}']),
                     ('uLk3', ['{Amount}', '{Beatflash}', '{Count}', '{Persist}']),
                     ('uBg', ['{Bgcolorr}', '{Bgcolorg}', '{Bgcolorb}', '{Normalize#}'])]


def uniform_spec(M):
    """All uniforms of a module (state + MAT + acc + look), for tests and docs."""
    seen, out = set(), []
    for n, e in state_spec(M) + mat_spec(M) + LOOK_SPEC:
        if n not in seen:
            seen.add(n)
            out.append((n, e))
    return out


# ------------------------------------------------------------------ GLSL
def px_util():
    """px_common.glsl up to its uniform-dependent part (hash, rnd, noise, fbm, curl, rot...): the free helpers."""
    t = _read(PX_COMMON_FILE)
    return t[:t.index('#ifndef PX_PACKED_ONLY')]


def pal_block():
    """gen_pattern's palette constants + pal() (needs uCa / uCb), cut from its GLSL_GEN."""
    return GLSL_GEN[:GLSL_GEN.index('vec2 space(')]


def decl(spec):
    return ''.join('uniform vec4 %s;\n' % n for n, _e in spec)


GP_COMMON = """
uint FR; int NPTS; float ASP; float PSIZE = 1.0; int SIDE;
ivec2 gpTex(int j) { return ivec2(j - (j / SIDE) * SIDE, j / SIDE); }       // point index -> state texel
float rnd(int i, uint salt) { return pxRnd(uint(i), salt + SEED * 7919u); }
vec3 rnd3(int i, uint salt) { return vec3(rnd(i, salt), rnd(i, salt + 1u), rnd(i, salt + 2u)); }
float packKA(float k, float a) { return floor(clamp(a, 0.0, 1.0) * 1023.0 + 0.5) + fract(k) * 0.999; }
float unpackA(float w) { return floor(w) / 1023.0; }
float unpackK(float w) { return fract(w) / 0.999; }
float lum(vec3 c) { return dot(c, vec3(0.299, 0.587, 0.114)); }
vec3 ballPoint(vec3 r) {
    float z = 2.0 * r.x - 1.0; float ph = TAU * r.y; float s = sqrt(max(0.0, 1.0 - z * z));
    return vec3(s * cos(ph), s * sin(ph), z) * pow(r.z, 1.0 / 3.0);
}
"""

STATE_MAIN = """
void main() {
    ivec2 T2 = ivec2(gl_GlobalInvocationID.xy);
    int side = int(uSt.y + 0.5);
    if (T2.x >= side || T2.y >= side) return;
    int i = T2.y * side + T2.x;
    SIDE = side;
    int last = side * side - 1;
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    bool same = isz.x == side && isz.y == side;
    vec4 clk = same ? texelFetch(sTD2DInputs[0], ivec2(last - (last / side) * side, last / side), 0) : vec4(0.0);
    drive_globals(ivec2(uSt2.zw));
    ASP = uSt2.y;
    bool reset = !same || clk.w < 0.5 || abs(clk.z - uSt.z) > 0.5;
    float dt = reset ? 0.0 : clamp(T - clk.x, 0.0, uSt.w);
#ifdef GP_PROBE_DT
    reset = false; dt = GP_PROBE_DT;
#endif
    FR = uint(max(clk.y, 0.0)) + (dt > 0.0 ? 1u : 0u);
    NPTS = min(int(uSt.x + 0.5), last);
    if (i == last) { TDImageStoreOutput(0, ivec3(T2, 0), vec4(T, reset ? 0.0 : float(FR), uSt.z, 1.0)); return; }
    if (i >= NPTS) { TDImageStoreOutput(0, ivec3(T2, 0), vec4(0.0)); return; }
    vec4 s = texelFetch(sTD2DInputs[0], T2, 0);
    s = reset ? pt_seed(i) : pt_step(i, s, dt);
    TDImageStoreOutput(0, ivec3(T2, 0), s);
}
"""

VERT_MAIN = {
    '2d': """
vec4 project(int i, vec3 P, inout vec4 C) {
    vec2 q = P.xy;
    int fold = max(int(uV2.z + 0.5), 1);
    if (fold > 1) q = rot2(q, TAU * float(i - (i / fold) * fold) / float(fold));
    q = rot2(q, radians(uView.y + uView2.x * T));
    q = q * uView.x + vec2((uView.z - 0.5) * 2.0 * ASP, (uView.w - 0.5) * 2.0);
    return vec4(q.x / ASP, q.y, 0.0, 1.0);
}
""",
    '3d': """
vec4 project(int i, vec3 P, inout vec4 C) {
    vec3 p = P;
    p.xz = rot2(p.xz, radians(uView.x + uView2.x * T));
    p.yz = rot2(p.yz, radians(uView.y));
    float z = uView.z - p.z;
    if (z <= 1e-3) return vec4(2.0, 2.0, 0.0, 1.0);
    float f = 1.0 / tan(radians(uView.w) * 0.5);
    C.a *= pow(max(uView.z / z, 0.0), uView2.y);
    return vec4(p.x * f / (ASP * z), p.y * f / z, 0.0, 1.0);
}
""",
}

VERT_TAIL = """
vec3 ptpal(float k) { return pal(k * uPal.y + uPal.z + uPal.w * T, int(uPal.x + 0.5)); }
out Vertex { vec4 color; float size; } oV;
"""

VERT_BODY = """
void main()
{
    int side = int(uV.y + 0.5);
    SIDE = side;
    ivec2 t = ivec2(floor((TDPos().xy + 0.5) * float(side - 1) + 0.5));
    int i = t.y * side + t.x;
    drive_globals(ivec2(uV2.xy));
    ASP = uV2.x / max(uV2.y, 1.0);
    NPTS = min(int(uV.x + 0.5), side * side - 1);
    FR = 0u;
    vec4 s = texelFetch(sSt, t, 0);
    vec3 P = vec3(0.0);
    vec4 C = vec4(0.0);
    vec4 clip = vec4(2.0, 2.0, 0.0, 1.0);
    PSIZE = 1.0;                                   // pt_place may scale this point's sprite size
    if (i < NPTS && pt_place(i, s, P, C)) clip = project(i, P, C);
    gl_Position = clip;
    gl_PointSize = max(uV.z * PSIZE, 1.0);
    oV.size = gl_PointSize;
    oV.color = vec4(C.rgb * C.a * uV.w, C.a);
}
"""

PIXEL = """// GEN_points mat pixel: 1-px points pass the colour through (exact additive counts); Size > 1 = sprite shape.
uniform vec4 uV;
uniform vec4 uV2;
uniform vec4 uV3;
in Vertex { vec4 color; float size; } iV;
layout(location = 0) out vec4 fragColor;

void main()
{
	vec4 c = iV.color;
	if (iV.size > 1.5) {
		vec2 d = gl_PointCoord * 2.0 - 1.0;
		float r2 = dot(d, d);
		int sp = int(uV2.w + 0.5);
		float w = 1.0;
		if (sp == 0) { w = max(1.0 - r2, 0.0); w *= w; }
		else if (sp == 1) {
			float core = max(1.0 - r2 * 4.0, 0.0);
			float gx = max(1.0 - abs(d.y) * 8.0, 0.0) * (1.0 - abs(d.x));
			float gy = max(1.0 - abs(d.x) * 8.0, 0.0) * (1.0 - abs(d.y));
			w = max(core, max(gx, gy));
		}
		else if (sp == 3) {                         // glint: soft core + N thin rays fading out (Nuke Glint style)
			float r = sqrt(r2);
			float a = atan(d.y, d.x) - radians(uV3.z);
			float n = max(uV3.x, 1.0);
			float k = abs(sin(a * n * 0.5));                  // 0 on each of the n ray axes
			float ray = exp(-k * r / max(uV3.y, 1e-3)) * max(1.0 - r, 0.0);
			w = exp(-r2 * 40.0) + ray;
			if (r2 > 1.0) w = 0.0;
		}
		c *= w;
	}
	fragColor = c;
}
"""

LOOK_BODY = """
vec3 tone(vec4 v) {
    float n = (uBg.w > 0.5 ? 1.0 : uLk2.z / max(uLk3.z, 1.0)) * (1.0 - uLk3.w);
    float E = exp2(uLk.y);
    vec3 r = v.rgb * n * E;
    float d = v.a * n;
    int m = int(uLk.x + 0.5);
    vec3 col;
    if (m == 1) col = r;
    else if (m == 2) {
        vec3 avg = v.a > 0.0 ? v.rgb / v.a : vec3(0.0);
        float b = log2(1.0 + d * E) * 0.25;
        vec3 per = log2(1.0 + r) * 0.25;
        col = mix(per, avg * b, clamp(uLk.w, 0.0, 1.0));
    }
    else col = 1.0 - exp(-r);
    return pow(max(col, vec3(0.0)), vec3(1.0 / max(uLk.z, 1e-3)));
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[1], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[1], p, 0);
    drive_globals(isz);
    vec2 uv = (vec2(p) + 0.5) / vec2(isz);
    ivec2 rsz = textureSize(sTD2DInputs[0], 0);
    vec4 v = (rsz.x == isz.x && rsz.y == isz.y) ? texelFetch(sTD2DInputs[0], p, 0) : textureLod(sTD2DInputs[0], uv, 0.0);
#ifdef GP_ACC
    v += uLk3.w * TDImageLoadOutput(1, ivec3(p, 0));            // trails: acc kept in place in colour buffer 1
    TDImageStoreOutput(1, ivec3(p, 0), v);
#endif
    if (uLk2.x > 0.0) {                                        // glow = mips of this frame's points (render)
        float L = uLk2.y;
        vec4 g = 0.5 * textureLod(sTD2DInputs[0], uv, L) + 0.3 * textureLod(sTD2DInputs[0], uv, L + 1.0)
               + 0.2 * textureLod(sTD2DInputs[0], uv, L + 2.0);
        v += uLk2.x * g / (1.0 - min(uLk3.w, 0.999));
    }
    vec3 col = tone(v) * (1.0 + uLk3.y * ENV);
    int mode = int(uLk2.w + 0.5);
    vec4 o;
    if (mode == 0) o = vec4(uBg.rgb + col, 1.0);
    else if (mode == 1) o = vec4(c.rgb + col, c.a);
    else if (mode == 2) o = vec4(1.0 - (1.0 - c.rgb) * (1.0 - clamp(col, 0.0, 1.0)), c.a);
    else if (mode == 3) o = vec4(max(c.rgb, col), c.a);
    else { vec3 cc = clamp(col, 0.0, 1.0); o = vec4(cc, max(cc.r, max(cc.g, cc.b))); }
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, o, uLk3.x));
}
"""


def state_text(M, probe_dt=None):
    """The state compute shader (without the effector prefix; effector_prefix() goes in front)."""
    head = '// GEN_points %s state (compute; builders/gen_points.py + gen_points_%s.py)\n' % (M['MODULE'], M['MODULE'])
    pre = '#define GP_PROBE_DT %r\n' % float(probe_dt) if probe_dt is not None else ''
    return (pre + head + 'layout (local_size_x = 8, local_size_y = 8) in;\n' + decl(state_spec(M)) + GLSL_COMMON
            + '#ifndef PXE_HOOK\n' + px_util() + '#endif\n' + GP_COMMON + '#define GP_IN sTD2DInputs[1]\n'
            + '#define GP_ST sTD2DInputs[0]\n' + ('#define GP_AUX sTD2DInputs[2]\n' if M.get('AUX_SCRIPT') else '')
            + M.get('COMMON', '') + M['STEP'] + M.get('STATE_MAIN', STATE_MAIN))


def vertex_text(M):
    head = '// GEN_points %s mat vertex (builders/gen_points.py + gen_points_%s.py)\n' % (M['MODULE'], M['MODULE'])
    return (head + 'uniform sampler2D sSt;\nuniform sampler2D sIn;\n' + decl(mat_spec(M)) + GLSL_COMMON + pal_block()
            + px_util() + GP_COMMON + VERT_TAIL + '#define GP_IN sIn\n#define GP_ST sSt\n' + M.get('COMMON', '')
            + M['PLACE']
            + VERT_MAIN[M['KIND']] + VERT_BODY)


def look_text(acc=False):
    """acc False: `look` (Persist 0, one buffer). acc True: `look_acc` (Persist > 0): the trail buffer (render +
    Persist x last) lives in its own colour buffer 1 in place (readwrite), so no separate acc pass / feedback."""
    return (('#define GP_ACC 1\n' if acc else '') + '// GEN_points look (compute): acc (buffer 1, in place) + tone + glow + beat flash over the slot input '
            '(in0 render, in1 input)\n'
            'layout (local_size_x = 8, local_size_y = 8) in;\n' + decl(LOOK_SPEC) + GLSL_COMMON + LOOK_BODY)


# ------------------------------------------------------------------ effectors (shared list, builders/effectors.py)
_EFF = {}


def _eff():
    """builders/effectors.py as a namespace (its adapters / helpers; never edited from here)."""
    if not _EFF and os.path.exists(EFFECTORS_FILE):
        ns = dict(globals())
        exec(_read(EFFECTORS_FILE), ns)
        _EFF.update(ns)
    return _EFF


def effector_prefix(M):
    E = _eff()
    kind = M.get('EFFECTORS')
    if not E or not kind:
        return None
    return E['_prefix'](E['_logic'](), ('PXE_PARTICLES',) if kind == 'particles' else ('PXE_POINTS',))


def _refresh_eff_in(m):
    """eff_in's `chops` expression names /project1/effectors/eff_rows only if it exists; built before the list
    existed it stays on eff_none until the par is evaluated again (live b3, T-126): evaluate it once here."""
    e = m.op('eff_in')
    if e is not None:
        e.par.chops.eval()


def _attach_effectors(m, M):
    """Effectors page + eff_in + buffer / selection uniforms on `state` (prefix already in state_compute)."""
    E = _eff()
    kind = M.get('EFFECTORS')
    if not E or not kind:
        return None
    Lg = E['_logic']()
    if kind == 'particles':
        r = E['attach_particles'](m, Lg)           # BO_particles adapter: state_compute + state (same names here)
        _refresh_eff_in(m)
        return r
    E['_pars'](m, 'Effectors', E['_points_page'](Lg))
    E['_eff_in'](m)
    E['_patch_text'](Lg, m.op('state_compute'), E['_prefix'](Lg, ('PXE_POINTS',)))
    st = m.op('state')
    E['_buffer'](st)
    E['_vecs'](st, E['_points_vecs'](Lg))
    _refresh_eff_in(m)
    return 'GEN_points %s: per-point push / dissolve near effectors (state, PXE_POINTS)' % M['MODULE']


# ------------------------------------------------------------------ TD side: the module network
def _uniforms(g, spec):
    g.seq.vec.numBlocks = max(len(spec), int(g.seq.vec.numBlocks))
    for k, (un, ex) in enumerate(spec):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), td_expr(e))


def _pass(m, name, text, ins, w, h, fmt='rgba32float', spec=(), extend='hold', filt=None, bufs=1):
    """Compute GLSL TOP `name` + docked `<name>_compute` (text), size w / h expressions, inputs in order (<= 3).
    bufs > 1: extra colour buffers kept in place (readwrite, not cleared: TDImageLoadOutput, T-110 (5))."""
    g = _mk(m, glslTOP, name)
    for t in list(getattr(g, 'docked', []) or []):          # a new GLSL op docks its own templates (T-115 (5))
        if t.valid and t.name != name + '_compute' and t.name.startswith(name + '_'):
            _sd(t)
    d = m.op(name + '_compute')
    if d is None:
        d = _mk(m, textDAT, name + '_compute')
    d.dock = g
    if d.text != text:
        d.text = text
    g.par.mode = 'compute'
    g.par.computedat = d
    g.par.outputresolution = 'custom'
    _expr(g.par.resolutionw, w)
    _expr(g.par.resolutionh, h)
    g.par.format = fmt
    g.par.inputextenduv = extend
    if filt:
        g.par.inputfiltertype = filt
    if bufs > 1:
        g.par.numcolorbufs = bufs
        g.par.outputaccess = 'readwrite'
        g.par.clearoutputs = False
    elif g.par.numcolorbufs.eval() not in (None, 1):         # v2 look on a b3 test build had 2: back to 1
        g.par.numcolorbufs = 1
        g.par.outputaccess = 'writeonly'
        g.par.clearoutputs = True
    for i, src in enumerate(ins):
        g.inputConnectors[i].connect(src)
    if spec:
        _uniforms(g, spec)
    return g


def _feedback(m, name, target, fmt='rgba32float'):
    b = _mk(m, constantTOP, name + '_blank')
    b.par.colorr = b.par.colorg = b.par.colorb = 0
    b.par.alpha = 0
    b.par.outputresolution = 'custom'
    for p_ in (b.par.resolutionw, b.par.resolutionh):      # 2 x 2 constant: never re-cooks (a side-sized blank
        p_.mode = ParMode.CONSTANT                          # followed in1's size and re-filled 33 MB on changes)
        p_.val = 2
    b.par.format = fmt
    b.comment = ('Start of %s: 2 x 2 zero. The state pass sees a size other than side x side and seeds every point.'
                 % name)
    fb = _mk(m, feedbackTOP, name)
    fb.inputConnectors[0].connect(b)
    fb.par.top = target
    fb.comment = 'Last frame of %s.' % target
    return fb


PULSE_EXEC = """# GEN_points module pulses: Reset -> Resetcount + 1 (the state pass sees a new epoch and re-seeds).
def onPulse(par):
\tif par.name == 'Reset':
\t\tpar.owner.par.Resetcount = int(par.owner.par.Resetcount.eval()) + 1
\treturn
"""


def _pulses(m):
    pe = m.op('pulses')
    if pe is None:
        pe = _mk(m, parameterexecuteDAT, 'pulses')
    if pe.text != PULSE_EXEC:
        pe.text = PULSE_EXEC
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Reset'
    if getattr(pe.par, 'onpulse', None) is not None:
        pe.par.onpulse = True
    pe.par.active = False
    pe.par.active = True                                   # recompile after a text change (T-113 (3))
    pe.comment = 'Reset pulse -> Resetcount + 1 = re-seed every point.'
    return pe


def _aux(m, M):
    """Module data texture (state input 2, GP_AUX): a Script TOP whose callbacks DAT is the module's AUX_SCRIPT
    (cooks only when the pars it reads change; lsystem = the segment table)."""
    text = M.get('AUX_SCRIPT')
    if not text:
        for n in ('aux', 'aux_callbacks'):
            _sd(m.op(n))
        return None
    d = m.op('aux_callbacks') or _mk(m, textDAT, 'aux_callbacks')
    if d.text != text:
        d.text = text
    a = _mk(m, scriptTOP, 'aux')
    a.par.callbacks = d
    _try(a, 'format', 'rgba32float')
    d.dock = a
    a.comment = 'Module data texture (%s): built in Python only when its pars change; read by state.' % M['MODULE']
    return a


def _try(o, name, value):
    p = getattr(o.par, name, None)
    if p is not None:
        try:
            p.val = value
        except Exception:
            pass


def _points_render(m, M):
    """Grid POP side x side points -> geo (Select POP) + mat (GLSL MAT) -> render (Render TOP 32F, additive)."""
    g = _mk(m, gridPOP, 'pts')
    g.par.surftype = 'points'
    _expr(g.par.cols, SIDE_E)
    _expr(g.par.rows, SIDE_E)
    g.par.sizex, g.par.sizey = 1, 1
    _try(g, 'texture', 'point')
    g.comment = 'side x side points (static grid): TDPos().xy + 0.5 = the point texel (mat vertex).'
    mat = _mk(m, glslMAT, 'mat')
    for suf, text in (('_vertex', vertex_text(M)), ('_pixel', PIXEL)):
        d = m.op('mat' + suf) or _mk(m, textDAT, 'mat' + suf)
        if d.text != text:
            d.text = text
        d.dock = mat
    mat.par.vdat = 'mat_vertex'
    mat.par.pdat = 'mat_pixel'
    mat.seq.sampler.numBlocks = max(int(mat.seq.sampler.numBlocks), 2)
    mat.par.sampler0name, mat.par.sampler0top = 'sSt', 'state'
    _try(mat, 'sampler0filter', 'nearest')
    mat.par.sampler1name, mat.par.sampler1top = 'sIn', 'in1'
    _try(mat, 'sampler1filter', 'linear')
    _uniforms(mat, mat_spec(M))
    mat.par.blending = True
    for n in ('srcblend', 'destblend', 'srcblenda', 'destblenda'):
        getattr(mat.par, n).val = 'one'
    _try(mat, 'postmultalpha', False)
    mat.par.depthtest = False
    mat.par.depthwriting = False
    mat.comment = 'Points: state texel -> pt_place -> %s projection; additive one/one, depth off.' % M['KIND']
    geo = _mk(m, geometryCOMP, 'geo')
    for ch in list(geo.children):
        if ch.name != 'sel':
            _sd(ch)
    s = geo.op('sel') or geo.create(selectPOP, 'sel')
    s.par.pop = '../pts'
    s.render = True
    s.display = True
    geo.par.material = 'mat'
    geo.comment = 'The point grid (Select POP of ../pts) drawn with mat.'
    cam = _mk(m, cameraCOMP, 'cam')
    cam.comment = 'Unused by the shader (it writes clip space) but a Render TOP needs a camera.'
    r = _mk(m, renderTOP, 'render')
    r.par.camera = 'cam'
    r.par.geometry = 'geo'
    r.par.lights = ''
    r.par.outputresolution = 'custom'
    _expr(r.par.resolutionw, RW_E)
    _expr(r.par.resolutionh, RH_E)
    _expr(r.par.format, "'rgba32float' if parent().par.Precision.eval() == 'float' else 'rgba16float'")
    r.par.antialias = 'aa1'
    r.par.bgcolorr = r.par.bgcolorg = r.par.bgcolorb = r.par.bgcolora = 0
    r.comment = ('Points this frame: rgb = sum of colours, a = sum of weights (additive; Precision float = exact 32F '
                 'sums, half = 16F, ~2x less bandwidth).')
    return r


# out_sel: 0 (in1 passthrough, nothing upstream cooks) when Amount 0 OR the rack slot is off (enabled 0 / mix 0).
# The rack's per-slot `<name>_mix` Cross TOP keeps its viewer on (user rule) and a visible viewer pulls the module
# even while the slot Switch bypasses it: with the network pane on the rack all 12 modules cooked every frame (12
# Render TOPs, 66-70 ms per frame, b3 12.5-16.6 fps; docs/builds/RENDER_COST.md "Cook triggers"). No slots row = on.
_SLOT_E = "parent(2).op('slots')[parent().name, '%s']"
OUT_SEL_E = ("0 if parent().par.Amount.eval() <= 0 or (parent(2).op('slots') is not None and "
             "(str(getattr(" + _SLOT_E % 'enabled' + ", 'val', '1')).strip() in ('0', '') or "
             "float(getattr(" + _SLOT_E % 'mix' + ", 'val', '1') or 0) <= 0)) "
             "else (2 if parent().par.Persist.eval() > 0 else 1)")


def _module_network(m, M):
    in1 = _mk(m, inTOP, 'in1')
    clk = _const_chop(m, 'clock', [('rate', "parent().par.Speed.eval() * (1.0 + parent().par.Audiospeed.eval() * "
                                            "float(parent(2).op('drive')['level']))")])
    clk.comment = 'Module clock rate = Speed x (1 + Audiospeed x rack level); integrated by clock_int.'
    ci = _mk(m, speedCHOP, 'clock_int')
    ci.inputConnectors[0].connect(clk)
    ci.comment = 'Module time (s). The state pass steps by its change per frame (Speed 0 / freeze = hold).'
    _pulses(m)
    fb = _feedback(m, 'state_fb', 'state')
    aux = _aux(m, M)
    text = state_text(M)
    pre = effector_prefix(M)
    if pre:
        text = _eff()['_logic']()['with_prefix'](text, pre)
    st = _pass(m, 'state', text, [fb, in1] + ([aux] if aux is not None else []), SIDE_E, SIDE_E, spec=state_spec(M),
               filt='linear')
    st.comment = 'Point state (one rgba32f texel per point + the clock texel): pt_seed / pt_step (%s).' % M['MODULE']
    eff = _attach_effectors(m, M)
    r = _points_render(m, M)
    for old in ('acc_fb_blank', 'acc_fb', 'acc', 'acc_compute', 'acc_sel'):   # v1 trail pass (now in look)
        _sd(m.op(old))
    lk = _pass(m, 'look', look_text(), [r, in1], OW_E, OH_E, fmt='rgba16float', spec=LOOK_SPEC, filt='linear')
    la = _pass(m, 'look_acc', look_text(True), [r, in1], OW_E, OH_E, fmt='rgba16float', spec=LOOK_SPEC,
               filt='linear', bufs=2)
    for g_ in (lk, la):
        _expr(g_.par.inputfiltertype, "'mipmap' if parent().par.Glow.eval() > 0 else 'linear'")   # mips only for glow
    lk.comment = ('Persist 0: tone (soft / linear / log) + glow (render mips, only when Glow > 0) + beat flash of the '
                  'render, blended over in1.')
    la.comment = ('Persist > 0: acc (colour buffer 1, in place) = render + Persist x last acc, then the same look. '
                  'One pass instead of acc + feedback + look.')
    sel = _mk(m, switchTOP, 'out_sel')
    sel.inputConnectors[0].connect(in1)
    sel.inputConnectors[1].connect(lk)
    sel.inputConnectors[2].connect(la)
    _expr(sel.par.index, OUT_SEL_E)
    sel.comment = ('Amount 0 or slot off (slots enabled 0 / mix 0) = the slot input untouched (nothing cooks, also '
                   'when a viewer shows the rack, RENDER_COST.md); Persist 0 -> look, > 0 -> look_acc.')
    out1 = _mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(sel)
    stages = [
        {'title': '1 In + clock', 'role': 'input', 'ops': ['in1', 'clock', 'clock_int', 'pulses'],
         'body': 'in1 = the slot input (background or the slot before). clock_int = module time.'},
        {'title': '2 State: %s' % M['MODULE'], 'role': 'process',
         'ops': ['aux', 'aux_callbacks', 'state_fb_blank', 'state_fb', 'state', 'state_compute', 'eff_none', 'eff_in'],
         'body': M.get('BLURB', 'Point state.') + ' One texel per point; state_fb = last frame.'},
        {'title': '3 Points render', 'role': 'process',
         'ops': ['pts', 'mat', 'mat_vertex', 'mat_pixel', 'geo', 'cam', 'render'],
         'body': 'Grid POP points -> mat reads state -> 1-px points / sprites, additive 32F.'},
        {'title': '4 Accumulate + look', 'role': 'process', 'ops': ['look', 'look_compute', 'look_acc',
                                                                     'look_acc_compute'],
         'body': 'look (Persist 0) / look_acc (trails in its buffer 1, in place): tone + glow over in1.'},
        {'title': '5 Out', 'role': 'output', 'ops': ['out_sel', 'out1'], 'body': 'Amount 0 = in1 untouched.'},
    ]
    if eff:
        stages[1]['body'] += ' Effectors page: Effon (default off).'
    return stages


_rack_instance = _instance
_rack_build = build
_rack_pars = _pars


def _pars(c, pages, defaults=None):
    """The rack's _pars, plus: an EXISTING menu par whose menu grew gets the new names / labels (value kept). The rack
    version skips existing pars, so a module menu extended later (form Shape 'clip', lane G) never reached instances
    built before (live b3 / main 27 Oct: preset 6 set index 4 and got 'plane'). Rack callers find this one by name."""
    _rack_pars(c, pages, defaults)
    for _pg, pars in pages:
        for name, style, default, o in pars:
            p = getattr(c.par, name, None) if style == 'Menu' else None
            if p is not None and list(p.menuNames) != list(o['names']):
                v0 = p.eval()
                p.menuNames, p.menuLabels = o['names'], o['labels']
                if v0 in o['names']:
                    p.val = v0


def _refresh_presets(m, module):
    """Rewrite the zkit rows of the module's built-in preset slots with the current full state (defaults + preset),
    so a recall never brings back an older default (e.g. wave 1 Counts); other slots (the user's own) are kept."""
    pt = m.op('controls/zk_presets')
    lg = m.op('controls/zk_logic')
    if pt is None or lg is None:
        return 0
    M = module_ns(module)
    L = lg.module
    n = 0
    for slot, pname, vals in M['PRESETS']:
        row = [slot, pname, L.DEFAULT_COLOR, L.preset_dump(module_pars(M, vals))]
        for r in range(1, pt.numRows):
            if pt[r, 0].val == str(slot):
                for k, v in enumerate(row):
                    pt[r, k] = v
                break
        else:
            pt.appendRow(row)
        n += 1
    return n


def _instance(c, name, module, panel=True):
    r = _rack_instance(c, name, module, panel)
    m = c.op(name)
    if m is not None:
        _refresh_presets(m, module)
        m.comment = ('GEN_points module %s (%s). Pars on its pages (Points / Look / View / Drive / Effectors); '
                     'pulse Opencontrols for the zkit panel, Reset to re-seed.' % (name, module))
    return r


def build(parent_path='/project1/lab', panel=True, first=FIRST):
    res = _rack_build(parent_path, panel, first)
    c = op(parent_path).op(NAME)
    c.comment = ('GEN_points: additive point generators (density maps, attractors, flow lines, Form grid...). In: '
                 'in1 TOP (optional background). Out: out1 TOP. Slots from `slots` (builders/gen_points.py add / '
                 'remove / rewire). Rack Drive: Bpm / beat CHOP / audio level. Panic = background only.')
    return res


# ------------------------------------------------------------------ live checks (docs/builds/gen_points.md)
_PL = {}


def plogic():
    if not _PL:
        ns = {'__file__': PLOGIC_FILE}
        exec(compile(_read(PLOGIC_FILE), PLOGIC_FILE, 'exec'), ns)
        _PL.update(ns)
    return _PL


def _module_of(m):
    return m.parent().op('slots')[m.name, 'module'].val


def probe(inst_path, dt=1.0 / 60.0):
    """chk_step: the module's state shader forced to one step of dt from state_fb (GP_PROBE_DT); same uniforms.
    Run after freeze() (state_fb = state, stable); read it >= 3 frames later with check_step()."""
    m = op(inst_path)
    M = module_ns(_module_of(m))
    text = state_text(M, probe_dt=dt)
    pre = effector_prefix(M)
    if pre:
        text = _eff()['_logic']()['with_prefix'](text, pre)
    ins = [m.op('state_fb'), m.op('in1')] + ([m.op('aux')] if m.op('aux') is not None else [])
    g = _pass(m, 'chk_step', text, ins, SIDE_E, SIDE_E, spec=state_spec(M), filt='linear')
    st = m.op('state')
    for k in range(int(st.seq.vec.numBlocks)):            # effector selection uniforms + buffer as on `state`
        n = getattr(st.par, 'vec%dname' % k).eval()
        if not n:
            continue
        g.seq.vec.numBlocks = max(int(g.seq.vec.numBlocks), k + 1)
        getattr(g.par, 'vec%dname' % k).val = n
        for ax in 'xyzw':
            sp, gp_ = getattr(st.par, 'vec%dvalue%s' % (k, ax)), getattr(g.par, 'vec%dvalue%s' % (k, ax))
            if sp.mode == ParMode.EXPRESSION:
                _expr(gp_, sp.expr)
            else:
                gp_.val = sp.eval()
    if int(st.seq.array.numBlocks):
        g.seq.array.numBlocks = int(st.seq.array.numBlocks)
        for k in range(int(st.seq.array.numBlocks)):
            for f in ('name', 'type', 'chop', 'arraytype'):
                getattr(g.par, 'array%d%s' % (k, f)).val = getattr(st.par, 'array%d%s' % (k, f)).eval()
    g.viewer = False
    g.comment = 'CHECK ONLY (gen_points.probe): one forced step of dt from state_fb. Remove with unprobe().'
    return {'probe': g.path, 'dt': dt}


def unprobe(inst_path):
    m = op(inst_path)
    for n in ('chk_step', 'chk_step_compute'):
        _sd(m.op(n))
    return {'unprobed': inst_path}


def read_uniforms(g):
    """gen_pattern.read_uniforms, but array blocks only when the CHOP has the palette channels (r g b pos): a GEN_points
    state also carries the effector buffer arrays (other channels), which the rack version tried to read as a palette
    (TypeError in check_step, lane G 27 Oct)."""
    U = {}
    for k in range(g.seq.vec.numBlocks):
        n = getattr(g.par, 'vec%dname' % k).eval()
        if n:
            U[n] = tuple(float(getattr(g.par, 'vec%dvalue%s' % (k, ch)).eval()) for ch in 'xyzw')
    for k in range(g.seq.array.numBlocks):
        n = getattr(g.par, 'array%dname' % k).eval()
        ch = getattr(g.par, 'array%dchop' % k).eval()
        if n and ch is not None and all(ch[cn] is not None for cn in ('r', 'g', 'b', 'pos')):
            U[n] = [[float(ch[cn][i]) for cn in ('r', 'g', 'b', 'pos')] for i in range(ch.numSamples)]
    return U


def _arr(o):
    import numpy
    return numpy.array(o.numpyArray(delayed=False), dtype=numpy.float64)


def check_step(inst_path, n=2000, seed=7, tol=1e-3):
    """Probe output vs gen_points_logic.step on n random points of the frozen state (same frame counter, dt)."""
    import numpy
    L = plogic()
    m = op(inst_path)
    module = _module_of(m)
    S0 = _arr(m.op('state_fb'))
    S1 = _arr(m.op('chk_step'))
    side = S0.shape[1]
    U = read_uniforms(m.op('chk_step'))
    flat0 = S0.reshape(-1, 4)
    flat1 = S1.reshape(-1, 4)
    clk = flat0[side * side - 1]
    g = L['Glob'](U, asp=U['uSt2'][1], fr=int(max(clk[1], 0)) + 1, npts=int(U['uSt'][0] + 0.5))
    rng = numpy.random.RandomState(seed)
    N = min(int(U['uSt'][0] + 0.5), side * side - 1)
    idx = numpy.sort(rng.choice(N, min(n, N), replace=False))
    img = _arr(m.op('in1')) if module in L['USES_IMG'] else None
    aux = _arr(m.op('aux')) if module in L['USES_AUX'] else None
    dtp = float(m.op('chk_step_compute').text.split('GP_PROBE_DT ', 1)[1].split('\n', 1)[0])
    exp_ = L['step'](module, idx, flat0[idx], U, g, dtp, img, aux, flat0)
    got = flat1[idx]
    err = numpy.abs(got - exp_)
    if module_ns(module).get('W_IS_ANGLE'):              # w = an angle (colour only): compare wrapped
        err[:, 3] = numpy.abs((got[:, 3] - exp_[:, 3] + math.pi) % (2.0 * math.pi) - math.pi)
    scale = numpy.maximum(1.0, numpy.abs(exp_))
    relall = err / scale
    rel = relall[:, :3].max(-1)                           # position parity
    relw = numpy.sort(relall[:, 3])
    rel.sort()
    return {'module': module, 'n': len(idx), 'dt': dtp, 'fr': g.FR, 'max_rel': float(rel[-1]),
            'p99_rel': float(rel[int(0.99 * (len(rel) - 1))]), 'median_rel': float(rel[len(rel) // 2]),
            'within_tol': float((rel <= tol).mean()), 'w_median': float(relw[len(relw) // 2]),
            'w_p99': float(relw[int(0.99 * (len(relw) - 1))]), 'w_within_tol': float((relw <= tol).mean()),
            'clock_texel': [float(x) for x in clk]}


def check_render(inst_path):
    """render (Persist 0, frozen) vs the numpy splat of the state: alpha / rgb totals + per-pixel L1 share."""
    import numpy
    L = plogic()
    m = op(inst_path)
    module = _module_of(m)
    S = _arr(m.op('state_fb')).reshape(-1, 4)
    R = _arr(m.op('render'))
    H, W = R.shape[0], R.shape[1]
    U = read_uniforms(m.op('mat'))
    N = min(int(U['uV'][0] + 0.5), len(S) - 1)
    img = _arr(m.op('in1')) if module in ('form', 'sparkle') else None
    exp_, nvis = L['points_render'](module, S[:N], U, W, H, img=img)
    out = {'module': module, 'W': W, 'H': H, 'points': N, 'visible_expected': nvis}
    for c_, nm in ((3, 'alpha'), (0, 'r'), (1, 'g'), (2, 'b')):
        a, e = float(R[..., c_].sum()), float(exp_[..., c_].sum())
        out[nm + '_sum'] = [round(a, 3), round(e, 3), round(abs(a - e) / max(abs(e), 1e-9), 6)]
    d = numpy.abs(R[..., 3] - exp_[..., 3]).sum() / max(float(exp_[..., 3].sum()), 1e-9)
    out['alpha_L1_share'] = round(float(d), 6)
    return out


def check_look(inst_path, n=400, seed=7):
    """out1 vs gen_points_logic tone + compose of the render at n random pixels (Persist 0, Glow 0, Quality 1: the
    look's acc is then the render itself)."""
    import numpy
    L = plogic()
    m = op(inst_path)
    if m.par.Persist.eval() > 0 or m.par.Glow.eval() > 0:
        return {'error': 'check_look needs Persist 0 and Glow 0'}
    A = _arr(m.op('render'))
    C = _arr(m.op('in1'))
    O = _arr(m.op('out1'))
    U = read_uniforms(m.op('look'))
    g = L['Glob'](U)
    H, W = O.shape[0], O.shape[1]
    rng = numpy.random.RandomState(seed)
    ys, xs = rng.randint(0, H, n), rng.randint(0, W, n)
    lit = numpy.argwhere(A[..., 3] > 0)
    if len(lit):
        k = lit[rng.randint(0, len(lit), n // 2)]
        ys, xs = numpy.concatenate([ys, k[:, 0]]), numpy.concatenate([xs, k[:, 1]])
    col = L['tone'](A[ys, xs], U)
    e = L['compose'](C[ys, xs], col, U, g)
    d = (numpy.abs(O[ys, xs] - e) / (2.0 / 255.0 + 2e-3 * numpy.abs(e))).max(-1)   # 16-bit float out (HDR kept)
    d.sort()
    return {'n': len(d), 'max_in_tol_units': float(d[-1]), 'p95': float(d[int(0.95 * (len(d) - 1))]),
            'within_tol': float((d <= 1.0).mean()), 'out_max': float(O.max())}


COST_CB = """def gpt_cost_tick(path, k):
    m = op(path)
    o = m.op('out1')
    o.cook(force=True)
    f = o.cookAbsFrame
    cpu = gpu = 0.0
    names = {}
    for c in m.findChildren(depth=None):
        if c.family in ('TOP', 'CHOP', 'POP') and c.cookAbsFrame == f:
            cpu += float(getattr(c, 'cpuCookTime', 0.0) or 0.0)
            gpu += float(getattr(c, 'gpuCookTime', 0.0) or 0.0)
            names[c.name] = [round(float(getattr(c, 'cpuCookTime', 0.0) or 0.0), 3),
                             round(float(getattr(c, 'gpuCookTime', 0.0) or 0.0), 3)]
    st = m.fetch('gpt_cost', {}, search=False)
    st.setdefault('rows', []).append([cpu, gpu, names])
    m.store('gpt_cost', st)
"""


def cost_start(inst_path, n=120):
    """T-102: pull out1 once a frame for n frames (one queued sampler, never overlap T-124 (3)); read with
    cost_read() > n frames later."""
    m = op(inst_path)
    m.store('gpt_cost', {'rows': []})
    script = COST_CB + 'gpt_cost_tick(args[0], args[1])\n'      # run() takes script text (+ args)
    for k in range(n):
        run(script, inst_path, k, delayFrames=k + 1)
    return {'cost_started': inst_path, 'frames': n}


def cost_read(inst_path):
    m = op(inst_path)
    rows = (m.fetch('gpt_cost', {}, search=False) or {}).get('rows', [])
    if not rows:
        return {'rows': 0}
    tot = sorted(r[0] + r[1] for r in rows)
    gpu = sorted(r[1] for r in rows)
    per = {}
    for r in rows:
        for k, v in r[2].items():
            per.setdefault(k, []).append(v if isinstance(v, (list, tuple)) else [v, 0.0])
    med = lambda v: sorted(v)[len(v) // 2]
    ops = [(k, round(med([a + b for a, b in v]), 3), round(med([a for a, _b in v]), 3), round(med([b for _a, b in v]), 3))
           for k, v in per.items()]
    ops.sort(key=lambda r: -r[1])
    return {'rows': len(rows), 'median_ms': round(med(tot), 3), 'p90_ms': round(tot[int(0.9 * (len(tot) - 1))], 3),
            'gpu_median_ms': round(med(gpu), 3), 'cpu_median_ms': round(med(sorted(r[0] for r in rows)), 3),
            'per_op_median': dict((k, {'ms': t, 'cpu': a, 'gpu': b}) for k, t, a, b in ops[:8]),
            'per_op_mean': dict(sorted(((k, round(sum(a + b for a, b in v) / len(rows), 3)) for k, v in per.items()),
                                       key=lambda kv: -kv[1])[:10])}
