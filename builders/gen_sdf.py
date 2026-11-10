# gen_sdf builder - GEN_sdf: background -> a short chain of SDF / fractal generator slots -> Panic -> out1.
# The rack IS GEN_pattern's (builders/gen_pattern.py is exec'd into this namespace and reused read-only: slots table,
# drive clock, Panic, background, rewire / remove / freeze); only the module network differs, because a raymarch
# needs its own resolution (Quality) and float output:
#   module COMP: clock -> clock_int (module time) ; rm (compute GLSL at Quality x input res, rgba32float,
#   premultiplied rgb + alpha; fractal2d: input 0 = `ref`, a Script TOP holding the perturbation reference orbit)
#   in1 + rm -> fx (shared composite at input res: bilinear upscale + Blend + Amount; Amount 0 = exact passthrough)
#   -> out1.
# Kinds: 'ray' modules (scene, fractal) write `float map(vec3 p)` + `float mapk(vec3 p)` + `void setup()`; the shared
# raymarch core here does camera paths, sphere tracing (bounded loops), normals, soft shadows, AO, materials, fog,
# glow, views. 'flat' modules (fractal2d) write `vec4 render2d(vec2 P)`.
# Shared GLSL lives here because 2+ modules use it today (no-bloat rule). Mirror: builders/gen_sdf_logic.py (numpy).
# Doc + LIVE CHECKS: docs/builds/gen_sdf.md. Run inside TD (2025.31550) through td_exec:
#   ns = dict(globals()); exec(open('<repo>/builders/gen_sdf.py').read(), ns)
#   ns['build']('/project1/lab')                       # rack + 'scene1' on first build; idempotent
#   ns['add']('/project1/lab/GEN_sdf', 'fractal')       # fractal1 (zkit panel + presets)
#   ns['preset'](inst, 3); ns['freeze'](inst); ns['check'](inst) (another exec, >= 3 frames later)
# Every loop has a compile-time cap (T-124: an unbounded raymarch can hang the GPU and kill the other TDs):
# MAXSTEPS 512 march, 64 shadow, 8 AO, 32 fractal iterations, 8192 2D iterations. ASCII only.
import os

_GP = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders/gen_pattern.py'
exec(open(_GP).read(), globals())                    # GEN_pattern's rack helpers (read-only reuse)

NAME = 'GEN_sdf'
HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
SDF_LOGIC_FILE = os.path.join(HERE, 'gen_sdf_logic.py')
MODULES = ['scene', 'fractal', 'fractal2d', 'aurora', 'sky', 'planet', 'ocean', 'cloud', 'blackhole', 'terrain']
CAPS = {'MAXSTEPS': 512, 'MAXSHADOW': 64, 'MAXAO': 8, 'MAXIT': 32, 'MAXIT2D': 8192, 'MAXLAYER': 64}


def module_ns(module):
    ns = {}
    exec(open(os.path.join(HERE, 'gen_sdf_%s.py' % module)).read(), ns)
    return ns


# ------------------------------------------------------------------ shared pages
BLENDS = ['replace', 'over', 'add', 'screen', 'multiply', 'difference', 'alpha']
BLEND_LABELS = ['Replace (opaque, bg colour behind)', 'Over the input', 'Add', 'Screen', 'Multiply', 'Difference',
                'Alpha out (premultiplied)']
VIEWS_RAY = ['shaded', 'data', 'normals', 'steps']
VIEW_LABELS_RAY = ['Shaded', 'Data (t, hit, steps, k; checks)', 'Normals', 'Step count heat']
VIEWS_FLAT = ['shaded', 'data']
VIEW_LABELS_FLAT = ['Shaded', 'Data (mu, escaped, trap, edge px; checks)']
MATERIALS = ['matte', 'glossy', 'chrome', 'neon', 'toon']
CAMPATHS = ['orbit', 'fly', 'wander']

UPSCALES = ['bilinear', 'fsr']
UPSCALE_PARS = [
    ('Upscale', 'Menu', 'bilinear', {'names': UPSCALES, 'labels': ['Bilinear (soft)', 'FSR 1 (EASU + RCAS, crisp edges)']}),
    ('Sharpness', 'Float', 0.2, {'min': 0, 'max': 2, 'label': 'FSR sharpness (stops: 0 = strongest)'}),
]
RENDER_RAY = ('Render', [
    ('Quality', 'Float', 0.5, {'min': 0.1, 'max': 2, 'label': 'Quality (render scale x output res)'}),
    ('Steps', 'Int', 96, {'min': 8, 'max': 512, 'label': 'March steps (cap 512)'}),
    ('Epsilon', 'Float', 0.5, {'min': 0.05, 'max': 4, 'label': 'Hit threshold (px)'}),
    ('Far', 'Float', 40.0, {'min': 2, 'max': 200, 'label': 'Far distance'}),
    ('Stepscale', 'Float', 0.9, {'min': 0.2, 'max': 1, 'label': 'Step scale (lower for twist / fractals)'}),
    ('Overrelax', 'Float', 1.0, {'min': 1, 'max': 2, 'label': 'Over-relaxation (1 = classic; > 1 longer steps, safe fallback)'}),
    ('View', 'Menu', 'shaded', {'names': VIEWS_RAY, 'labels': VIEW_LABELS_RAY}),
    ('Still', 'Toggle', False, {'label': 'Still: lock the render (no cost; deep zooms, stills)'}),
] + UPSCALE_PARS)
RENDER_FLAT = ('Render', [
    ('Quality', 'Float', 0.75, {'min': 0.1, 'max': 2, 'label': 'Quality (render scale x output res; 2 = 4x SSAA)'}),
    ('View', 'Menu', 'shaded', {'names': VIEWS_FLAT, 'labels': VIEW_LABELS_FLAT}),
    ('Still', 'Toggle', False, {'label': 'Still: lock the render (no cost; deep zooms, stills)'}),
] + UPSCALE_PARS)
CAMERA_PAGE = ('Camera', [
    ('Campath', 'Menu', 'orbit', {'names': CAMPATHS, 'labels': ['Orbit target', 'Fly forward', 'Wander (orbit + drift)']}),
    ('Camdist', 'Float', 4.0, {'min': 0.5, 'max': 30, 'label': 'Distance (orbit)'}),
    ('Camyaw', 'Float', 30.0, {'min': -180, 'max': 180, 'label': 'Yaw deg'}),
    ('Campitch', 'Float', 15.0, {'min': -89, 'max': 89, 'label': 'Pitch deg'}),
    ('Orbitspeed', 'Float', 10.0, {'min': -90, 'max': 90, 'label': 'Orbit deg/s'}),
    ('Flyspeed', 'Float', 1.0, {'min': -8, 'max': 8, 'label': 'Fly units/s'}),
    ('Fov', 'Float', 60.0, {'min': 10, 'max': 150, 'label': 'FOV deg (vertical)'}),
    ('Roll', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Roll deg'}),
    ('Rollspeed', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Roll deg/s'}),
    ('Sway', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Sway (fly / wander)'}),
    ('Beatyaw', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Yaw jump per beat step deg'}),
    ('Beatzoom', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Beat pulse -> dolly in'}),
    ('Audiozoom', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Audio -> dolly in'}),
    ('Targetx', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Target x'}),
    ('Targety', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Target y'}),
    ('Targetz', 'Float', 0.0, {'min': -10, 'max': 10, 'label': 'Target z'}),
    ('Spin', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Object spin deg'}),
    ('Spinspeed', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Object spin deg/s'}),
])
LOOK_PAGE = ('Look', [
    ('Material', 'Menu', 'glossy', {'names': MATERIALS, 'labels': ['Matte', 'Glossy', 'Chrome', 'Neon (rim + emissive)', 'Toon']}),
    ('Rim', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Rim (neon) / outline (toon)'}),
    ('Emissive', 'Float', 0.0, {'min': 0, 'max': 2, 'label': 'Emissive'}),
    ('Lightyaw', 'Float', 40.0, {'min': -180, 'max': 180, 'label': 'Light yaw deg'}),
    ('Lightpitch', 'Float', 50.0, {'min': -89, 'max': 89, 'label': 'Light pitch deg'}),
    ('Lightcolor', 'RGB', (1.0, 0.95, 0.9), {'label': 'Light colour'}),
    ('Lightintensity', 'Float', 1.2, {'min': 0, 'max': 4, 'label': 'Light intensity'}),
    ('Ambient', 'Float', 0.25, {'min': 0, 'max': 2, 'label': 'Ambient'}),
    ('Specpower', 'Float', 32.0, {'min': 1, 'max': 256, 'label': 'Specular power'}),
    ('Shadowsteps', 'Int', 24, {'min': 0, 'max': 64, 'label': 'Soft shadow steps (0 off, cap 64)'}),
    ('Shadowsoft', 'Float', 8.0, {'min': 1, 'max': 64, 'label': 'Shadow sharpness k'}),
    ('Aosteps', 'Int', 5, {'min': 0, 'max': 8, 'label': 'AO taps (0 off, cap 8)'}),
    ('Aostrength', 'Float', 3.0, {'min': 0, 'max': 10, 'label': 'AO strength'}),
    ('Fogdensity', 'Float', 0.05, {'min': 0, 'max': 1, 'label': 'Fog density'}),
    ('Glow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Glow (near misses)'}),
    ('Glowfalloff', 'Float', 8.0, {'min': 0.5, 'max': 64, 'label': 'Glow falloff'}),
    ('Beatglow', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Beat pulse -> glow'}),
    ('Glowhue', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Glow palette position'}),
])
COLOUR_SDF = ('Colour', [
    ('Palette', 'Menu', 'neon', {'names': PALETTES, 'labels': PAL_LABELS}),
    ('Spread', 'Float', 1.0, {'min': -4, 'max': 4, 'label': 'Palette spread'}),
    ('Offset', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Palette offset'}),
    ('Huecycle', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Palette cycle /s'}),
    ('Colora', 'RGB', (1.0, 1.0, 1.0), {'label': 'Colour A'}),
    ('Colorb', 'RGB', (0.95, 0.7, 0.25), {'label': 'Colour B'}),
    ('Bgcolor', 'RGB', (0.0, 0.0, 0.0), {'label': 'Background / fog colour'}),
    ('Blend', 'Menu', 'replace', {'names': BLENDS, 'labels': BLEND_LABELS}),
])


def shared_pages(kind, *_rest):
    # *_rest: gen_pattern's module_pars may pass its own extras (e.g. a palette flag); GEN_sdf's pages ignore them
    if kind == 'ray':
        return [DRIVE_PAGE, RENDER_RAY, CAMERA_PAGE, LOOK_PAGE, COLOUR_SDF]
    return [DRIVE_PAGE, RENDER_FLAT, COLOUR_SDF]


# uniform specs (same mini-language as GEN_pattern: {Par} {Par#} $t $step $age $level $W $H)
_R = 'math.radians'
SHARED_UNIFORMS = {
    'ray': [('uRes', ['$W', '$H', '0', '0']),
            ('uDrv', ['$t', '$step', '$age', '$level']),
            ('uBeat', ['{Beatgain}', '{Beatdecay}', '{Audiogain}', '{Seed}']),
            ('uQ', ['{Steps}', '{Epsilon}', '{Far}', '{Stepscale}']),
            ('uQ2', ['{Shadowsteps}', '{Shadowsoft}', '{Aosteps}', '{Aostrength}']),
            ('uCam', ['{Campath#}', '{Camdist}', _R + '({Camyaw})', _R + '({Campitch})']),
            ('uCam2', [_R + '({Orbitspeed})', '{Flyspeed}', _R + '({Fov})', _R + '({Roll})']),
            ('uCam3', [_R + '({Beatyaw})', '{Beatzoom}', '{Audiozoom}', _R + '({Rollspeed})']),
            ('uCam4', ['{Targetx}', '{Targety}', '{Targetz}', '{Sway}']),
            ('uObj', [_R + '({Spin})', _R + '({Spinspeed})', '{Overrelax}', '0']),
            ('uLt', [_R + '({Lightyaw})', _R + '({Lightpitch})', '{Ambient}', '{Specpower}']),
            ('uLtc', ['{Lightcolorr}', '{Lightcolorg}', '{Lightcolorb}', '{Lightintensity}']),
            ('uMat', ['{Material#}', '{View#}', '{Rim}', '{Emissive}']),
            ('uFog', ['{Bgcolorr}', '{Bgcolorg}', '{Bgcolorb}', '{Fogdensity}']),
            ('uGlow', ['{Glow}', '{Glowfalloff}', '{Beatglow}', '{Glowhue}']),
            ('uPal', ['{Palette#}', '{Spread}', '{Offset}', '{Huecycle}']),
            ('uCa', ['{Colorar}', '{Colorag}', '{Colorab}', '0']),
            ('uCb', ['{Colorbr}', '{Colorbg}', '{Colorbb}', '0'])],
    'flat': [('uRes', ['$W', '$H', '0', '0']),
             ('uDrv', ['$t', '$step', '$age', '$level']),
             ('uBeat', ['{Beatgain}', '{Beatdecay}', '{Audiogain}', '{Seed}']),
             ('uMat', ['0', '{View#}', '0', '0']),
             ('uPal', ['{Palette#}', '{Spread}', '{Offset}', '{Huecycle}']),
             ('uCa', ['{Colorar}', '{Colorag}', '{Colorab}', '0']),
             ('uCb', ['{Colorbr}', '{Colorbg}', '{Colorbb}', '0'])],
}
FX_UNIFORMS = [('uAmt', ['{Amount}', '{Blend#}', '0', '0']),
               ('uBg', ['{Bgcolorr}', '{Bgcolorg}', '{Bgcolorb}', '0'])]
# FSR 1 (shared files builders/glsl/fsr_easu.glsl + fsr_rcas.glsl, FX7a SX-10): EASU at the input (output) size, RCAS
# at the same size; `up` (Switch) feeds fx either rm (bilinear in fx, as before) or rcas (full res: fx's linear read at
# texel centres is exact). Only the selected branch cooks.
EASU_UNIFORMS = [('uEasu', ["op('in1').width", "op('in1').height", '1', '0'])]
RCAS_UNIFORMS = [('uRcas', ['{Sharpness}', '0', '1', '0'])]
FSR_FILES = ('fsr_easu.glsl', 'fsr_rcas.glsl')


def uniform_spec(M):
    return SHARED_UNIFORMS[M['KIND']] + M['UNIFORMS']


# ------------------------------------------------------------------ GLSL (gen_sdf_logic.py mirrors every line)
GLSL_COMMON = """
const float TAU = 6.283185307;
const float PI = 3.14159265;
float T; float STEP; float AGE; float ENV; float LEVEL; uint SEED; vec2 RES;
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float h2(ivec2 c, uint s) { return float(lb32(uint(c.x) * 1597334677u ^ lb32(uint(c.y) ^ (s * 2654435761u)))) * (1.0 / 4294967296.0); }
vec2 rot2(vec2 v, float a) { float c = cos(a), s = sin(a); return vec2(c * v.x - s * v.y, s * v.x + c * v.y); }
float smin(float a, float b, float k) { k = max(k, 1e-5); float h = max(k - abs(a - b), 0.0) / k; return min(a, b) - h * h * k * 0.25; }
float sdBox(vec3 p, vec3 b) { vec3 q = abs(p) - b; return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0); }
float tri(float k) { return 1.0 - abs(fract(k * 0.5) * 2.0 - 1.0); }
const vec3 PA[6] = vec3[6](vec3(0.5, 0.5, 0.5), vec3(0.5, 0.5, 0.5), vec3(0.4, 0.6, 0.8), vec3(0.6, 0.45, 0.2), vec3(0.5, 0.5, 0.5), vec3(0.8, 0.5, 0.4));
const vec3 PB[6] = vec3[6](vec3(0.5, 0.5, 0.5), vec3(0.5, 0.5, 0.5), vec3(0.4, 0.4, 0.2), vec3(0.4, 0.35, 0.2), vec3(0.5, 0.5, 0.5), vec3(0.2, 0.4, 0.2));
const vec3 PC[6] = vec3[6](vec3(1.0, 1.0, 1.0), vec3(1.0, 0.7, 0.4), vec3(1.0, 1.0, 1.0), vec3(1.0, 1.0, 1.0), vec3(2.0, 1.0, 0.0), vec3(2.0, 1.0, 1.0));
const vec3 PD[6] = vec3[6](vec3(0.0, 0.33, 0.67), vec3(0.0, 0.15, 0.2), vec3(0.0, 0.05, 0.1), vec3(0.0, 0.05, 0.15), vec3(0.5, 0.2, 0.25), vec3(0.0, 0.25, 0.25));
vec3 pal(float k, int i) {
    if (i <= 0) return mix(uCa.rgb, uCb.rgb, tri(k));
    if (i == 1) return uCa.rgb;
    int j = min(i - 2, 5);
    return PA[j] + PB[j] * cos(TAU * (PC[j] * k + PD[j]));
}
vec3 palk(float k) { return pal(k * uPal.y + uPal.z + uPal.w * T, int(uPal.x + 0.5)); }
void drive_globals(vec2 res) {
    RES = res; T = uDrv.x; STEP = uDrv.y; AGE = uDrv.z;
    ENV = uBeat.x * exp(-uDrv.z / max(uBeat.y, 1e-3)); LEVEL = uBeat.z * uDrv.w; SEED = uint(int(uBeat.w));
}
"""

GLSL_RAY = """
vec2 SPIN;
float sdf(vec3 p) { return map(vec3(SPIN.x * p.x + SPIN.y * p.z, p.y, -SPIN.y * p.x + SPIN.x * p.z)); }
float sdfk(vec3 p) { return mapk(vec3(SPIN.x * p.x + SPIN.y * p.z, p.y, -SPIN.y * p.x + SPIN.x * p.z)); }
vec3 fwd_dir(float yaw, float pitch) { return vec3(cos(pitch) * sin(yaw), sin(pitch), cos(pitch) * cos(yaw)); }
float camera(vec2 P, out vec3 ro, out vec3 rd) {
    vec2 uv = (P - 0.5 * RES) / RES.y;
    int path = int(uCam.x + 0.5);
    float yaw = uCam.z + uCam2.x * T + uCam3.x * STEP;
    float pitch = uCam.w;
    float dist = uCam.y * (1.0 - uCam3.y * ENV) * (1.0 - uCam3.z * LEVEL);
    vec3 ta = uCam4.xyz, look;
    if (path == 1) {
        vec3 f = fwd_dir(yaw - uCam2.x * T, pitch);
        float s = uCam2.y * T;
        ro = ta + f * s + uCam4.w * vec3(sin(0.7 * s), 0.6 * sin(0.53 * s), 0.0);
        look = ro + f + uCam4.w * 0.3 * vec3(cos(0.7 * s), 0.0, 0.0);
    } else {
        if (path == 2) { pitch += uCam4.w * 0.6 * sin(0.37 * T); dist *= 1.0 + 0.3 * uCam4.w * sin(0.23 * T); }
        ro = ta + dist * fwd_dir(yaw, pitch);
        look = ta;
    }
    vec3 ww = normalize(look - ro);
    float roll = uCam2.w + uCam3.w * T;
    vec3 up = vec3(sin(roll), cos(roll), 0.0);
    vec3 uu = cross(ww, up);
    uu = length(uu) < 1e-4 ? vec3(1.0, 0.0, 0.0) : normalize(uu);
    vec3 vv = cross(uu, ww);
    float fk = 0.5 / tan(0.5 * uCam2.z);
    rd = normalize(uv.x * uu + uv.y * vv + fk * ww);
    return fk;
}
vec3 normal(vec3 p, float h) {
    const vec2 k = vec2(1.0, -1.0);
    return normalize(k.xyy * sdf(p + k.xyy * h) + k.yyx * sdf(p + k.yyx * h) + k.yxy * sdf(p + k.yxy * h) + k.xxx * sdf(p + k.xxx * h));
}
float shadow(vec3 ro, vec3 rd, float k, int ns) {
    float res = 1.0, t = 0.02;
    for (int i = 0; i < MAXSHADOW; i++) {
        if (i >= ns) break;
        float h = sdf(ro + rd * t);
        res = min(res, k * h / t);
        t += clamp(h, 0.02, 0.4);
        if (res < 0.001 || t > 12.0) break;
    }
    return clamp(res, 0.0, 1.0);
}
float ambocc(vec3 p, vec3 n, int na, float s) {
    if (na <= 0) return 1.0;
    float occ = 0.0, sca = 1.0;
    for (int i = 0; i < MAXAO; i++) {
        if (i >= na) break;
        float h = 0.01 + 0.12 * float(i) / max(float(na - 1), 1.0);
        occ += (h - sdf(p + h * n)) * sca;
        sca *= 0.95;
    }
    return clamp(1.0 - s * occ, 0.0, 1.0);
}
vec3 sky(vec3 r, vec3 L) { return mix(uFog.rgb, uLtc.rgb, 0.5 + 0.5 * r.y) * 0.6 + uLtc.rgb * pow(max(dot(r, L), 0.0), 24.0); }
vec3 shade(int m, vec3 base, vec3 n, vec3 rd, vec3 L, float sh, float oc) {
    vec3 lc = uLtc.rgb * uLtc.w;
    float dif = max(dot(n, L), 0.0) * sh;
    float amb = uLt.z * oc;
    float fre = pow(clamp(1.0 + dot(n, rd), 0.0, 1.0), 3.0);
    float spe = pow(max(dot(n, normalize(L - rd)), 0.0), uLt.w) * sh;
    if (m == 0) return base * (lc * dif + amb);
    if (m == 1) return base * (lc * dif + amb) + lc * spe * (0.25 + 0.75 * fre);
    if (m == 2) return base * sky(reflect(rd, n), L) * (0.35 + 0.65 * oc) + lc * spe;
    if (m == 3) return base * (0.2 * dif + 0.2 * amb) + base * fre * uMat.z * 2.0 + base * uMat.w;
    vec3 c = base * (lc * (floor(dif * 3.0 + 0.5) / 3.0) + amb);
    return dot(n, -rd) < uMat.z * 0.5 ? c * 0.08 : c;
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = ivec2(int(uRes.x + 0.5), int(uRes.y + 0.5));
    if (p.x >= isz.x || p.y >= isz.y) return;
    drive_globals(vec2(isz));
    float sa = uObj.x + uObj.y * T;
    SPIN = vec2(cos(sa), sin(sa));
    setup();
    vec3 ro, rd;
    float fk = camera(vec2(p) + 0.5, ro, rd);
    float pa = 1.0 / (RES.y * fk);
    int N = int(uQ.x + 0.5);
    float t = 0.0, gl = 0.0, st = 0.0, e = 0.0, tp = 0.0, rp = 0.0;
    float om0 = max(uObj.z, 1.0), om = om0;
    bool hit = false;
    if (om0 > 1.0) {
        for (int i = 0; i < MAXSTEPS; i++) {    // over-relaxed sphere tracing (Keinert et al. 2014)
            if (i >= N) break;
            float d = sdf(ro + rd * t);
            float r = d * uQ.w;
            if (om > 1.0 && r + rp < t - tp) { t = tp + rp; om = 1.0; st += 1.0; continue; }   // spheres apart: safe step
            gl += exp(-max(d, 0.0) * uGlow.y) * om;   // weighted by the step factor: glow stays per unit of ray
            e = uQ.y * pa * max(t, 0.05);
            if (d < e) { hit = true; break; }
            tp = t; rp = r;
            t += r * om;
            om = om0;
            st += 1.0;
            if (t > uQ.z) break;
        }
    } else {                                     // classic sphere tracing (Overrelax 1: the cheaper loop on a GPU)
        for (int i = 0; i < MAXSTEPS; i++) {
            if (i >= N) break;
            float d = sdf(ro + rd * t);
            gl += exp(-max(d, 0.0) * uGlow.y);
            e = uQ.y * pa * max(t, 0.05);
            if (d < e) { hit = true; break; }
            t += d * uQ.w;
            st += 1.0;
            if (t > uQ.z) break;
        }
    }
    int view = int(uMat.y + 0.5);
    vec3 pos = ro + rd * t;
    if (view == 1) { TDImageStoreOutput(0, ivec3(p, 0), vec4(t, hit ? 1.0 : 0.0, st, hit ? sdfk(pos) : 0.0)); return; }
    vec3 col = vec3(0.0);
    float a = 0.0;
    if (hit) {
        float h = max(e, 1e-4);
        vec3 n = normal(pos, h);
        if (view == 2) { TDImageStoreOutput(0, ivec3(p, 0), vec4(n * 0.5 + 0.5, 1.0)); return; }
        vec3 L = fwd_dir(uLt.x, uLt.y);
        int ns = int(uQ2.x + 0.5);
        float sh = ns > 0 ? shadow(pos + n * h * 2.0, L, uQ2.y, ns) : 1.0;
        float oc = ambocc(pos, n, int(uQ2.z + 0.5), uQ2.w);
        vec3 c = shade(int(uMat.x + 0.5), palk(sdfk(pos)), n, rd, L, sh, oc);
        a = exp(-uFog.w * t);
        col = c * a;
    }
    if (view == 3) { col = palk(st / max(float(N), 1.0)); a = 1.0; }
    float g = uGlow.x * (1.0 + uGlow.z * ENV) * gl / 64.0;
    col += palk(uGlow.w) * g;
    a = clamp(a + g, 0.0, 1.0);
    TDImageStoreOutput(0, ivec3(p, 0), vec4(col, a));
}
"""

GLSL_FLAT = """
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = ivec2(int(uRes.x + 0.5), int(uRes.y + 0.5));
    if (p.x >= isz.x || p.y >= isz.y) return;
    drive_globals(vec2(isz));
    TDImageStoreOutput(0, ivec3(p, 0), render2d(vec2(p) + 0.5));
}
"""

FX_GLSL = """// GEN_sdf composite (shared by every module; builders/gen_sdf.py): rm (premultiplied) upscaled over in1
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uAmt;
uniform vec4 uBg;
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    ivec2 isz = textureSize(sTD2DInputs[0], 0);
    if (p.x >= isz.x || p.y >= isz.y) return;
    vec4 c = texelFetch(sTD2DInputs[0], p, 0);
    if (uAmt.x <= 0.0) { TDImageStoreOutput(0, ivec3(p, 0), c); return; }   // exact passthrough
    vec4 s = texture(sTD2DInputs[1], (vec2(p) + 0.5) / vec2(isz));
    int mode = int(uAmt.y + 0.5);
    vec4 o;
    if (mode == 0) o = vec4(s.rgb + uBg.rgb * (1.0 - s.a), 1.0);
    else if (mode == 1) o = vec4(s.rgb + c.rgb * (1.0 - s.a), s.a + c.a * (1.0 - s.a));
    else if (mode == 2) o = vec4(c.rgb + s.rgb, c.a);
    else if (mode == 3) o = vec4(1.0 - (1.0 - c.rgb) * (1.0 - s.rgb), c.a);
    else if (mode == 4) o = vec4(c.rgb * (s.rgb + (1.0 - s.a)), c.a);
    else if (mode == 5) o = vec4(abs(c.rgb - s.rgb), c.a);
    else o = s;
    TDImageStoreOutput(0, ivec3(p, 0), mix(c, o, uAmt.x));
}
"""


def shader(M):
    """The module's rm compute shader (compiled offline by test_gen_sdf with glslc)."""
    decl = ''.join('uniform vec4 %s;\n' % n for n, _e in uniform_spec(M))
    caps = ''.join('#define %s %d\n' % (k, v) for k, v in sorted(CAPS.items()))
    head = '// GEN_sdf %s (%s, compute; builders/gen_sdf.py + gen_sdf_%s.py)\n' % (M['MODULE'], M['KIND'], M['MODULE'])
    return (head + 'layout (local_size_x = 8, local_size_y = 8) in;\n' + caps + decl + GLSL_COMMON + M['GLSL']
            + (GLSL_RAY if M['KIND'] == 'ray' else GLSL_FLAT))


def fx_shader():
    return FX_GLSL


def fsr_shader(which):
    """'easu' / 'rcas': the shared FSR 1 file text (builders/glsl/fsr_<which>.glsl)."""
    return open(os.path.join(HERE, 'glsl', 'fsr_%s.glsl' % which)).read()


# ------------------------------------------------------------------ TD side
RM_RES = ("max(8, int(round(op('in1').width * parent().par.Quality.eval())))",
          "max(8, int(round(op('in1').height * parent().par.Quality.eval())))")


def _glsl(m, name, text, comment):
    g = _mk(m, glslTOP, name)
    d = m.op(name + '_compute')
    if d is None:
        d = _mk(m, textDAT, name + '_compute')
    d.text = text
    d.dock = g
    for extra in (name + '_pixel', name + '_info', name + '_compute1', name + '_vertex'):   # T-115 (5), T-123 (1)
        _sd(m.op(extra))
    g.par.mode = 'compute'
    g.par.computedat = d
    g.comment = comment
    return g


def _uniforms(g, spec):
    g.seq.vec.numBlocks = max(len(spec), g.seq.vec.numBlocks)
    for k, (un, ex) in enumerate(spec):
        getattr(g.par, 'vec{}name'.format(k)).val = un
        for comp, e in zip('xyzw', ex):
            _expr(getattr(g.par, 'vec{}value{}'.format(k, comp)), td_expr(e))


def _module_network(m, M):
    """clock -> clock_int; [ref (Script TOP) ->] rm (compute, Quality res, rgba32float); in1 + rm -> fx -> out1."""
    in1 = _mk(m, inTOP, 'in1')
    clk = _const_chop(m, 'clock', [('rate', "parent().par.Speed.eval() * (1.0 + parent().par.Audiospeed.eval() * "
                                            "float(parent(2).op('drive')['level']))")])
    clk.comment = 'Module clock rate = Speed x (1 + Audiospeed x rack level); integrated by clock_int.'
    ci = _mk(m, speedCHOP, 'clock_int')
    ci.inputConnectors[0].connect(clk)
    ci.comment = 'Module time (s, Speed-scaled, no jump when Speed changes). freeze() resets it to 0.'
    stages_in = ['in1', 'clock', 'clock_int']
    rm = _glsl(m, 'rm', shader(M), 'GEN_sdf %s (%s): render at Quality x input res, rgba32float, premultiplied rgb + '
               'alpha (View data = t/hit/steps/k for checks).' % (M['MODULE'], M['KIND']))
    rm.par.outputresolution = 'custom'
    _expr(rm.par.resolutionw, RM_RES[0])
    _expr(rm.par.resolutionh, RM_RES[1])
    rm.par.format = 'rgba32float'
    rm.par.inputextenduv = 'hold'
    rm.par.inputfiltertype = 'nearest'
    if M.get('REF_PY'):
        ref = _mk(m, scriptTOP, 'ref')
        cb = m.op('ref_callbacks')
        if cb is None:
            cb = _mk(m, textDAT, 'ref_callbacks')
        cb.text = M['REF_PY'] + M['REF_CALLBACK']
        ref.par.callbacks = cb
        ref.par.format = 'rgba32float'
        ref.comment = ('Perturbation reference orbit (Python float64 / Decimal) at the centre: 1 row, Z_n as hi/lo float pairs, '
                       'width = length + 1. Recooks only when centre / type / Julia c / iterations change.')
        for extra in ('ref_callbacks1',):
            _sd(m.op(extra))
        rm.inputConnectors[0].connect(ref)
        stages_in += ['ref', 'ref_callbacks']
    _uniforms(rm, uniform_spec(M))
    easu = _glsl(m, 'easu', fsr_shader('easu'), 'FSR 1 EASU (shared builders/glsl/fsr_easu.glsl): rm -> input res, '
                 'edge-adaptive. Cooks only with Upscale fsr.')
    rcas = _glsl(m, 'rcas', fsr_shader('rcas'), 'FSR 1 RCAS (shared builders/glsl/fsr_rcas.glsl): contrast-adaptive '
                 'sharpen at input res (Sharpness stops).')
    for g in (easu, rcas):
        g.par.outputresolution = 'custom'
        _expr(g.par.resolutionw, "op('in1').width")
        _expr(g.par.resolutionh, "op('in1').height")
        g.par.format = 'rgba16float'
        g.par.inputextenduv = 'hold'
        g.par.inputfiltertype = 'nearest'
    easu.inputConnectors[0].connect(rm)
    rcas.inputConnectors[0].connect(easu)
    _uniforms(easu, EASU_UNIFORMS)
    _uniforms(rcas, RCAS_UNIFORMS)
    up = _mk(m, switchTOP, 'up')
    up.inputConnectors[0].connect(rm)
    up.inputConnectors[1].connect(rcas)
    _expr(up.par.index, 'parent().par.Upscale.menuIndex')
    up.comment = 'Upscale: 0 = rm (fx upscales bilinear), 1 = FSR (easu -> rcas at input res). Only the picked branch cooks.'
    fx = _glsl(m, 'fx', fx_shader(), 'Composite: up (rm bilinear, or FSR at full res) + Blend over in1; Amount 0 = exact passthrough.')
    fx.par.outputresolution = 'custom'
    _expr(fx.par.resolutionw, 'me.inputs[0].width')
    _expr(fx.par.resolutionh, 'me.inputs[0].height')
    fx.par.format = 'useinput'
    fx.par.inputextenduv = 'hold'
    fx.par.inputfiltertype = 'linear'
    fx.inputConnectors[0].connect(in1)
    fx.inputConnectors[1].connect(up)
    _uniforms(fx, FX_UNIFORMS)
    out1 = _mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(fx)
    pe = m.op('still_pexec')
    if pe is None:
        pe = _mk(m, parameterexecuteDAT, 'still_pexec')
    pe.text = ("def onValueChange(par, prev):\n    if par.name == 'Still':\n"
               "        op('rm').lock = bool(par.eval())\n    return\n")
    pe.par.op = '..'  # relative: a dropped copy watches itself (drop-in, 28 Oct)
    pe.par.pars = 'Still'
    pe.par.active = False
    pe.par.active = True                                   # recompile after the text change (T-113 (3))
    pe.comment = 'Still on = rm locked (holds its last frame, cooks never; Quality / scene changes wait for Still off).'
    return [
        {'title': '1 In + clock', 'role': 'input', 'ops': stages_in,
         'body': 'in1 = the slot input. clock_int = module time.' + (' ref = reference orbit.' if M.get('REF_PY') else '')},
        {'title': '2 %s' % M['MODULE'], 'role': 'process', 'ops': ['rm', 'rm_compute'],
         'body': M.get('BLURB', 'Raymarch.')},
        {'title': 'Still', 'role': 'control', 'ops': ['still_pexec'], 'body': 'Still toggle -> rm.lock.'},
        {'title': '2b Upscale', 'role': 'process', 'ops': ['easu', 'easu_compute', 'rcas', 'rcas_compute', 'up'],
         'body': 'Upscale bilinear: up = rm. FSR: EASU + RCAS at input res (shared fsr_*.glsl).'},
        {'title': '3 Composite', 'role': 'process', 'ops': ['fx', 'fx_compute'],
         'body': 'Upscale + Blend over the slot input.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out1']},
    ]


def _instance(c, name, module, panel=True):
    M = module_ns(module)
    m = c.op(name)
    if m is None or not m.isCOMP:
        m = _mk(c, baseCOMP, name)
    m.allowCooking = True
    pages = M['PAGES'] + shared_pages(M['KIND'])
    _pars(m, pages, M.get('DEFAULTS'))
    m.comment = 'GEN_sdf module %s (%s). Pars on its pages; pulse Opencontrols for the zkit panel.' % (name, module)
    stages = _slot_gate(m, _module_network(m, M))   # gen_pattern's slot gate (T-198)
    m.par.opviewer.expr = "me.op('out1')"
    m.par.opviewer.mode = ParMode.EXPRESSION
    m.viewer = True
    info = None
    if panel:
        ns = dict(globals())
        exec(open(ZKIT_FILE).read(), ns)
        info = ns['build_controls'](m.path, pages=M['PANEL_PAGES'], d=56, cols=6)
        pt = m.op('controls/zk_presets')
        if pt is not None and pt.numRows <= 1:
            L = m.op('controls/zk_logic').module
            for slot, pname, vals in M['PRESETS']:          # full state (T-124 (1))
                pt.appendRow([slot, pname, L.DEFAULT_COLOR, L.preset_dump(module_pars(M, vals))])
        stages = [{'title': 'Controls', 'role': 'control', 'ops': ['controls', 'controls_window']}] + stages
    for s_ in stages:
        s_['ops'] = [n for n in s_['ops'] if m.op(n) is not None]
    op('/jazib_mcp/handlers').module.layout_stages(m, [s_ for s_ in stages if s_['ops']], True, arrange='mixed')
    _slot_ops(c, name)
    return {'instance': m.path, 'panel': bool(info)}


def build(parent_path='/project1/lab', panel=True, first='scene'):
    par_ = op(parent_path)
    c = par_.op(NAME) or par_.create(baseCOMP, NAME)
    c.allowCooking = True
    c.comment = ('GEN_sdf: SDF raymarch + fractal rack. In: in1 TOP (optional background). Out: out1 TOP. Slots from '
                 '`slots` (builders/gen_sdf.py add/remove/rewire). Panic = background straight out.')
    _pars(c, [('Rack', [
        ('Panic', 'Toggle', False, {'label': 'Panic (background only)'}),
        ('Input', 'Menu', 'auto', {'names': ['auto', 'black', 'live', 'test'],
                                   'labels': ['Auto (in1 if wired)', 'Black', 'Live (in1)', 'Test clip']}),
        ('Resw', 'Int', 1080, {'min': 64, 'max': 4096, 'label': 'Width'}),
        ('Resh', 'Int', 1920, {'min': 64, 'max': 4096, 'label': 'Height'}),
    ]), ('Drive', [
        ('Beatsource', 'Menu', 'internal', {'names': ['internal', 'chop'],
                                            'labels': ['Internal (Bpm)', 'Beat CHOP (count + phase)']}),
        ('Bpm', 'Float', 120.0, {'min': 40, 'max': 200, 'label': 'Bpm'}),
        ('Bpmchop', 'CHOP', '', {'label': 'Bpm CHOP (e.g. AU_features/out1)'}),
        ('Bpmchan', 'Str', 'bpm', {'label': 'Bpm channel'}),
        ('Beatchop', 'CHOP', '', {'label': 'Beat CHOP (e.g. AU_features/out1)'}),
        ('Phasechan', 'Str', 'beat_phase', {'label': 'Beat phase channel'}),
        ('Countchan', 'Str', 'beat_count', {'label': 'Beat count channel'}),
        ('Audiochop', 'CHOP', '', {'label': 'Audio CHOP (e.g. AC_audio/out_ctl)'}),
        ('Audiochan', 'Str', 'low', {'label': 'Audio channel'}),
        ('Resync', 'Pulse', None, {'label': 'Resync (beat 1 now)'}),
    ])])
    _drive(c)
    bg = _mk(c, constantTOP, 'bg')
    bg.par.colorr = bg.par.colorg = bg.par.colorb = 0
    bg.par.alpha = 1
    bg.par.outputresolution = 'custom'
    _expr(bg.par.resolutionw, 'parent().par.Resw.eval()')
    _expr(bg.par.resolutionh, 'parent().par.Resh.eval()')
    bg.par.format = 'rgba8fixed'
    bg.comment = 'Black background at Resw x Resh (static: cooks once).'
    in1 = _mk(c, inTOP, 'in1')
    tc = _mk(c, moviefileinTOP, 'test_clip')
    tc.par.file = TEST_CLIP
    tc.par.outputresolution = 'custom'
    _expr(tc.par.resolutionw, 'parent().par.Resw.eval()')
    _expr(tc.par.resolutionh, 'parent().par.Resh.eval()')
    tc.par.outputaspect = 'resolution'
    tc.par.fillmode = 'fill'
    tc.comment = 'Test picture: stored 5 s webcam clip (cooks only while selected).'
    img = _mk(c, switchTOP, 'img_src')
    img.inputConnectors[0].connect(bg)
    img.inputConnectors[1].connect(in1)
    img.inputConnectors[2].connect(tc)
    _expr(img.par.index, "(lambda m, w: 1 if m == 'live' or (m == 'auto' and w) else (2 if m == 'test' else 0))("
          "parent().par.Input.eval(), any(len(cn.connections) for cn in parent().inputConnectors "
          "if cn.inOP is not None and cn.inOP.name == 'in1'))")
    pn = _mk(c, switchTOP, 'panic')
    _expr(pn.par.index, '1 if parent().par.Panic.eval() else 0')
    pn.comment = 'Panic: 1 = background straight to out1 (same frame; slots stop cooking).'
    _mk(c, outTOP, 'out1')
    t = c.op('slots')
    if t is None:
        t = _mk(c, tableDAT, 'slots')
        t.clear()
        t.appendRow(COLS)
        t.appendRow([first + '1', first, 1, 1, 1])
    t.comment = 'Rack state: one row per module instance. enabled 0/1, mix 0..1 act live; order -> rewire.'
    out = []
    for r in _rows(c):
        out.append(_instance(c, r['name'], r['module'], panel=panel and c.op(r['name']) is None))
    wires = rewire(c)
    c.par.opviewer.expr = "me.op('out1')"
    c.par.opviewer.mode = ParMode.EXPRESSION
    c.viewer = True
    lay = _layout(c)
    return {'comp': c.path, 'instances': out, 'wires_changed': wires, 'layout': str(lay)[:300]}


def rebuild_shaders(inst_path):
    """Rewrite rm / fx shader text + uniforms of an instance from the module file (after a code change)."""
    m = op(inst_path)
    M = module_ns(m.parent().op('slots')[m.name, 'module'].val)
    _pars(m, M['PAGES'] + shared_pages(M['KIND']), M.get('DEFAULTS'))
    m.op('rm_compute').text = shader(M)
    _uniforms(m.op('rm'), uniform_spec(M))
    m.op('fx_compute').text = fx_shader()
    for w, spec in (('easu', EASU_UNIFORMS), ('rcas', RCAS_UNIFORMS)):
        if m.op(w + '_compute') is not None:
            m.op(w + '_compute').text = fsr_shader(w)
            _uniforms(m.op(w), spec)
    if M.get('REF_PY') and m.op('ref_callbacks') is not None:
        m.op('ref_callbacks').text = M['REF_PY'] + M['REF_CALLBACK']
    pt = m.op('controls/zk_presets')                # the module's own slots re-seeded (full state); other slots kept
    if pt is not None:
        L = m.op('controls/zk_logic').module
        for slot, pname, vals in M['PRESETS']:
            row = [slot, pname, L.DEFAULT_COLOR, L.preset_dump(module_pars(M, vals))]
            hit = next((i for i in range(1, pt.numRows) if pt[i, 'slot'].val == str(slot)), None)
            if hit is None:
                pt.appendRow(row)
            else:
                pt.replaceRow(hit, row)
    return {'rebuilt': inst_path}


# ------------------------------------------------------------------ live checks (docs/builds/gen_sdf.md)
_SDFL = {}


def _sdf_logic():
    if not _SDFL:
        ns = {}
        exec(open(SDF_LOGIC_FILE).read(), ns)
        _SDFL.update(ns)
    return _SDFL


def check_state(module):
    st = module_ns(module).get('CHECK', {})
    return st.get('t', 1.0), st.get('beats', 0.0)


def check(inst_path, n=200, seed=7, tol_t=0.02, tol_c=4.0 / 255.0):
    """rm parity with gen_sdf_logic at n random rm texels (uniforms read from rm; fractal2d also reads `ref`).
    Run in its own exec after freeze() (T-74 / T-116 (4)). Reports the data view when View = data, else colour."""
    import random
    L = _sdf_logic()
    m = op(inst_path)
    module = m.parent().op('slots')[m.name, 'module'].val
    U = read_uniforms(m.op('rm'))
    rm = m.op('rm').numpyArray(delayed=False)
    ref = m.op('ref').numpyArray(delayed=False) if m.op('ref') is not None else None
    H, W = rm.shape[0], rm.shape[1]
    rnd = random.Random(seed)
    pts = [(rnd.randrange(W), rnd.randrange(H)) for _ in range(n)]
    exp_ = L['expect_rm'](module, U, [x for x, _y in pts], [y for _x, y in pts], W, H, ref=ref)
    got = [[float(rm[y][x][c]) for c in range(4)] for x, y in pts]
    r = L['compare'](module, U, got, exp_, tol_t=tol_t, tol_c=tol_c)
    r.update({'module': module, 'W': W, 'H': H, 'n': n})
    return r


def check_fx(inst_path, n=300, seed=11, tol=3.0 / 255.0):
    """Composite parity: out1 vs gen_sdf_logic.compose(bilinear(rm), in1) using the live rm / in1 pixels."""
    import random
    L = _sdf_logic()
    m = op(inst_path)
    U = read_uniforms(m.op('fx'))
    rm = (m.op('up') or m.op('rm')).numpyArray(delayed=False)     # what fx reads: rm, or the FSR output
    src = m.op('in1').numpyArray(delayed=False)
    out = m.op('out1').numpyArray(delayed=False)
    H, W = out.shape[0], out.shape[1]
    rnd = random.Random(seed)
    diffs = []
    for _ in range(n):
        x, y = rnd.randrange(W), rnd.randrange(H)
        e = L['compose_px'](U, rm, src, x, y, W, H)
        diffs.append(max(abs(float(out[y][x][c]) - e[c]) for c in range(4)))
    diffs.sort()
    return {'n': n, 'max': round(diffs[-1], 4), 'median': round(diffs[n // 2], 5),
            'within_tol': round(sum(d <= tol for d in diffs) / float(n), 4)}


def stats(inst_path, n=1000, seed=7):
    """Mean rgb + lit share of out1 at the fixed sample points (doc table)."""
    L = _logic()
    a = op(inst_path).op('out1').numpyArray(delayed=False)
    H, W = a.shape[0], a.shape[1]
    return L['stats']([[float(v) for v in a[y][x]] for x, y in L['sample_points'](W, H, n, seed)])


_FSRL = {}


def _fsr_logic():
    if not _FSRL:
        exec(open(os.path.join(HERE, 'fsr_logic.py')).read(), _FSRL)
    return _FSRL


def check_fsr(inst_path, n=400, seed=5):
    """FSR parity (Upscale fsr, own exec >= 3 frames after a change; T-74): easu vs fsr_logic.easu(rm) at n random
    output texels, rcas vs fsr_logic.rcas(easu) (the live easu as input, so each pass is checked alone)."""
    import random
    import numpy as np
    F = _fsr_logic()
    m = op(inst_path)
    rm = np.asarray(m.op('rm').numpyArray(delayed=False), dtype=np.float64)
    ea = np.asarray(m.op('easu').numpyArray(delayed=False), dtype=np.float64)
    rc = np.asarray(m.op('rcas').numpyArray(delayed=False), dtype=np.float64)
    H, W = ea.shape[0], ea.shape[1]
    rnd = random.Random(seed)
    xs = [rnd.randrange(W) for _ in range(n)]
    ys = [rnd.randrange(H) for _ in range(n)]
    e_exp = F['easu'](rm, W, H, np.array(xs), np.array(ys))
    e_got = ea[ys, xs]
    sh = float(m.par.Sharpness.eval())
    r_exp = F['rcas'](ea, sh)[ys, xs]
    r_got = rc[ys, xs]
    de = np.abs(e_got - e_exp).max(axis=-1)
    dr = np.abs(r_got - r_exp).max(axis=-1)
    # relative to the value scale (rgba16float keeps ~3 decimal digits)
    sc = np.maximum(1.0, np.abs(e_exp).max(axis=-1))
    return {'rm': [rm.shape[1], rm.shape[0]], 'out': [W, H], 'n': n,
            'easu_max': round(float((de / sc).max()), 5), 'easu_median': round(float(np.median(de)), 6),
            'rcas_max': round(float((dr / sc).max()), 5), 'rcas_median': round(float(np.median(dr)), 6),
            'easu_ringing': round(float(F['overshoot'](ea, rm.min(axis=(0, 1)), rm.max(axis=(0, 1)))), 5)}


def _menus(m, pages):
    """Existing Menu pars take the builder's names / labels (new entries, e.g. a scene, append; the value is kept).
    _pars skips existing pars, so without this a new menu entry never reaches an upgraded COMP (lane C, 27 Oct)."""
    changed = []
    for _pg, pars in pages:
        for name, style, _d, o in pars:
            p = getattr(m.par, name, None)
            if style != 'Menu' or p is None:
                continue
            if list(p.menuNames) != list(o['names']) or list(p.menuLabels) != list(o['labels']):
                v = p.eval()
                p.menuNames, p.menuLabels = o['names'], o['labels']
                p.val = v if v in o['names'] else o['names'][0]
                changed.append(name)
    return changed


def upgrade(comp_path, name):
    """Bring one existing instance up to this builder (new pars, menu entries, FSR branch, shaders, presets) without a
    new panel. One instance per exec in main (T-152); call _layout(comp) after the last one."""
    c = op(comp_path)
    module = c.op('slots')[name, 'module'].val
    r = _instance(c, name, module, panel=False)
    M = module_ns(module)
    r['menus'] = _menus(c.op(name), M['PAGES'] + shared_pages(M['KIND']))
    rebuild_shaders(c.op(name).path)
    return r

