# fx_glitch_timedisplace - FX_glitch module 'timedisplace' (FX1 DG-13 slit-scan / time displacement, D10).
# Template: docs/builds/fx_glitch.md "Module template"; doc + LIVE CHECKS: docs/builds/fx_glitch_timedisplace.md.
# FX6 probe 4b: native texture3dTOP ring -> timemachineTOP (no Cache TOP: the time machine refuses it); the only GLSL
# is the time map (one compute pass, T-46/T-47), shared ring chain in builders/fx_time_ring.py. Map modes: ramp
# (slit-scan at any angle), radial, spiral, luma (bright parts lag), noise (liquid time), external (any TOP: flow,
# mask, audio texture). Shaping: Repeat (several slits), Mirror, Phase (scrolling time wave), Curve, Steps (hard time
# bands), row Jitter, Invert, Smooth (the map integrates: feedback melt). Offset = Delay + shape * Amount * (Depth-1)
# ring cooks, clamped to the cooks the ring holds. Amount 0 = exact passthrough. Pure maths: fx_time_logic.td_offsets.
# ASCII only.
import os

MODULE = 'timedisplace'
_RING = os.path.join(globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders',
                     'fx_time_ring.py')
exec(open(_RING).read())                            # GLSL_HASH, STAMP_RING, RING_PAR, build_ring, map_size_exprs

MODES = ['ramp', 'radial', 'spiral', 'luma', 'noise', 'external']

PAGES = [
    ('Time', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount (x ring span)'}),
        ('Depth', 'Int', 32, {'min': 2, 'max': 120, 'label': 'Depth (ring cooks)'}),
        RING_PAR,
        ('Delay', 'Float', 0.0, {'min': 0, 'max': 60, 'label': 'Delay (frames, all pixels)'}),
        ('Mode', 'Menu', 'ramp', {'names': MODES, 'labels': ['Ramp (slit-scan)', 'Radial', 'Spiral', 'Luma',
                                                             'Noise (liquid)', 'External TOP']}),
        ('Angle', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Ramp angle (0 = bottom now)'}),
        ('Centerx', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre x'}),
        ('Centery', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Centre y'}),
        ('Twist', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Spiral twist'}),
        ('Smooth', 'Float', 0.0, {'min': 0, 'max': 0.99, 'label': 'Smooth (map melt)'}),
        ('Maptop', 'TOP', '', {'label': 'External map TOP'}),
        ('Mapres', 'Menu', 'half', {'names': ['full', 'half', 'quarter'], 'labels': ['Map full', 'Map half',
                                                                                     'Map quarter']}),
    ]),
    ('Shape', [
        ('Repeat', 'Float', 1.0, {'min': 0.25, 'max': 8, 'label': 'Repeat'}),
        ('Mirror', 'Toggle', False, {'label': 'Mirror (triangle)'}),
        ('Phase', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Phase scroll (cycles/s)'}),
        ('Curve', 'Float', 1.0, {'min': 0.2, 'max': 5, 'label': 'Curve (gamma)'}),
        ('Steps', 'Int', 0, {'min': 0, 'max': 64, 'label': 'Steps (0 = smooth)'}),
        ('Invert', 'Toggle', False, {'label': 'Invert'}),
        ('Scale', 'Float', 3.0, {'min': 0.5, 'max': 20, 'label': 'Noise scale'}),
        ('Speed', 'Float', 0.2, {'min': 0, 'max': 3, 'label': 'Noise speed'}),
        ('Jitter', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Row jitter'}),
        ('Jittersize', 'Float', 8.0, {'min': 1, 'max': 200, 'label': 'Jitter rows px'}),
        ('Jitterrate', 'Float', 8.0, {'min': 0, 'max': 60, 'label': 'Jitter rate Hz'}),
        ('Seed', 'Int', 1, {'min': 1, 'max': 100, 'label': 'Seed'}),
    ]),
]
PANEL_PAGES = ['Time', 'Shape']

_Z = {'Delay': 0.0, 'Repeat': 1.0, 'Mirror': 0, 'Phase': 0.0, 'Curve': 1.0, 'Steps': 0, 'Invert': 0,
      'Jitter': 0.0, 'Smooth': 0.0, 'Twist': 0.0, 'Centerx': 0.5, 'Centery': 0.5, 'Angle': 0.0}
PRESETS = [
    (1, 'slitscan', dict(_Z, Amount=1.0, Depth=32, Mode=0)),
    (2, 'time tunnel', dict(_Z, Amount=1.0, Depth=32, Mode=1, Curve=0.7)),
    (3, 'spiral warp', dict(_Z, Amount=1.0, Depth=32, Mode=2, Twist=1.5, Mirror=1, Phase=0.25)),
    (4, 'liquid time', dict(_Z, Amount=1.0, Depth=48, Mode=4, Scale=2.5, Speed=0.3, Smooth=0.6, Seed=4)),
    (5, 'scan bands', dict(_Z, Amount=1.0, Depth=32, Mode=0, Angle=90.0, Steps=12, Jitter=0.35, Jittersize=24.0,
                           Jitterrate=6.0, Seed=5)),
]

MAP = """// FX_glitch timedisplace: time map (compute, T-47; FX6 4b). in0 picture, in1 map source (Maptop or the
// picture), in2 stamp (z = cooks since the ring restarted). Writes grey m = 1 - offset/(Depth-1) for the Time
// Machine (white = now). offset = Delay + shape * Amount * (Depth-1), clamped to [0, min(Depth-1, z)].
// = fx_time_logic.td_offsets.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount depthm1 delay mode
uniform vec4 uB;   // angle centrex centrey twist
uniform vec4 uC;   // repeat mirror steps invert
uniform vec4 uD;   // scale speed phase curve
uniform vec4 uE;   // time smooth seed jitter
uniform vec4 uF;   // jittersize jitterrate aspect(picture W/H) mapw
uniform vec4 uG;   // maph pictureh
""" + GLSL_HASH + """const float TAU = 6.28318530718;
float vn(vec3 x, uint s) {                                     // value noise on the pcg lattice (= _vn)
    vec3 i = floor(x); vec3 f = x - i; f = f * f * (3.0 - 2.0 * f);
    ivec3 b = ivec3(i);
    float v[8];
    for (int k = 0; k < 8; k++) {
        ivec3 o = ivec3(k & 1, (k >> 1) & 1, (k >> 2) & 1);
        v[k] = h(uvec4(uvec3(b + o), s));
    }
    return mix(mix(mix(v[0], v[1], f.x), mix(v[2], v[3], f.x), f.y),
               mix(mix(v[4], v[5], f.x), mix(v[6], v[7], f.x), f.y), f.z);
}
float shape(vec2 uv) {
    int mode = int(uA.w + 0.5);
    vec2 c = uB.yz;
    float asp = uF.z;
    if (mode == 0) {
        float a = radians(uB.x); vec2 d = vec2(sin(a), cos(a));
        return dot(uv - c, d) / (abs(d.x) + abs(d.y)) + 0.5;
    }
    vec2 q = (uv - c) * vec2(asp, 1.0);
    float r = length(q) / length(vec2(0.5 * asp, 0.5));
    if (mode == 1) return r;
    if (mode == 2) return fract(atan(q.y, q.x) / TAU + 0.5 + r * uB.w);
    if (mode == 3) return lum(texture(sTD2DInputs[0], uv).rgb);
    if (mode == 4) {
        vec3 x = vec3(uv.x * asp * uD.x, uv.y * uD.x, uE.x * uD.y);
        uint s = uint(uE.z) * 7919u;
        return clamp(vn(x, s) * 0.667 + vn(x * 2.03 + 17.0, s + 1u) * 0.333, 0.0, 1.0);
    }
    return lum(texture(sTD2DInputs[1], uv).rgb);
}
void main() {
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= int(uF.w) || p.y >= int(uG.x)) return;
    vec2 uv = (vec2(p) + 0.5) / vec2(uF.w, uG.x);
    float s = shape(uv);
    float w = s * uC.x + uD.z * uE.x;
    if (uC.y > 0.5) s = 1.0 - abs(fract(w * 0.5) * 2.0 - 1.0);
    else if (abs(uC.x - 1.0) > 1e-6 || uD.z != 0.0) s = fract(w);
    else s = clamp(s, 0.0, 1.0);
    s = pow(max(s, 0.0), max(uD.w, 1e-3));
    if (uE.w != 0.0) {
        float row = floor(uv.y * uG.y / max(uF.x, 1.0));
        uint ep = uint(floor(uE.x * uF.y));
        s = clamp(s + (h(uvec4(uint(row), ep, uint(uE.z), 3u)) - 0.5) * uE.w, 0.0, 1.0);
    }
    if (uC.z >= 2.0) s = min(floor(s * uC.z) / (uC.z - 1.0), 1.0);
    if (uC.w > 0.5) s = 1.0 - s;
    float D = max(uA.y, 1.0);
    float off = uA.z + s * uA.x * D;
    float n = texelFetch(sTD2DInputs[2], ivec2(0), 0).z;
    if (n > 0.5 && uE.y > 0.0) off = mix(off, (1.0 - TDImageLoadOutput(0, ivec3(p, 0)).r) * (D + 1.0) - 1.0, uE.y);
    off = clamp(off, 0.0, min(D, n));
    float m = 1.0 - (off + 1.0) / (D + 1.0);           // 31550 Time Machine reads (1-m)*Depth - 1 slices (T-122)
    TDImageStoreOutput(0, ivec3(p, 0), vec4(m, m, m, 1.0));
}
"""

P = "parent().par.{}.eval()"
SCALE = "{'full': 1.0, 'half': 0.5, 'quarter': 0.25}[parent().par.Mapres.eval()]"


def uniforms():
    """[(uniform, [x, y, z, w expressions])] of the map pass (names = the MAP declarations; tested offline)."""
    mw, mh = map_size_exprs(SCALE)
    tog = '1 if parent().par.{}.eval() else 0'
    return [
        ('uA', [P.format('Amount'), '%s - 1' % DEPTH, P.format('Delay'), 'parent().par.Mode.menuIndex']),
        ('uB', [P.format('Angle'), P.format('Centerx'), P.format('Centery'), P.format('Twist')]),
        ('uC', [P.format('Repeat'), tog.format('Mirror'), P.format('Steps'), tog.format('Invert')]),
        ('uD', [P.format('Scale'), P.format('Speed'), P.format('Phase'), P.format('Curve')]),
        ('uE', ['absTime.seconds', P.format('Smooth'), P.format('Seed'), P.format('Jitter')]),
        ('uF', [P.format('Jittersize'), P.format('Jitterrate'),
                "op('in1').width / max(1, op('in1').height)", mw]),
        ('uG', [mh, "op('in1').height", '0', '0']),
    ]


def build(m, H):
    """in1 (+ map_sel = Maptop or in1) -> ring / stamp / map -> tmachine -> out_sw -> out1 (fx_time_ring)."""
    H['mk'](m, inTOP, 'in1')
    sel = H['mk'](m, selectTOP, 'map_sel')
    H['expr'](sel.par.top, "parent().par.Maptop.eval() or op('in1')")
    sel.comment = 'External map (Mode external): Maptop, else the picture.'
    stages = build_ring(m, H, MAP, uniforms(), map_scale=SCALE, map_src=sel, title='2 Time map')
    m.op('map').comment = 'timedisplace map: ramp/radial/spiral/luma/noise/external -> offset (DG-13).'
    return stages
