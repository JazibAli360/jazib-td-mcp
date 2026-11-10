# fx_analog_crtfault - FX_analog module 'crtfault' (FX2 AV-07 CRT faults; FX0 row 15). Works on any picture, before
# or after `crt` (before = the faults move the raster the tube then draws: physically right for deflection faults).
# Template: docs/builds/fx_glitch.md "Module template" (FX_analog rack = builders/fx_analog.py). ONE compute pass:
#   power collapse / warm-up (Power toggle: squeeze to a bright line, then a dot that fades; on = dim and small growing)
#   -> raster breathing (picture grows with its brightness: HV sag; Analyze TOP average, pulled only while Breathe > 0)
#   -> Degauss wobble -> V-hold roll + blanking bar (JZB_Lofi_CRT Roll) -> H-hold tear (diagonal bands, H blanking)
#   -> H-sync jitter per line -> top bend (flagging) -> S-wobble -> sample -> hum bars (count, softness, speed)
#   -> arc flashes + streak -> purity swirl (Degauss) -> border.
# Amount scales the continuous faults; Degauss and Power act at any Amount (hits / transitions). Amount 0 with Power
# steady on and no Degauss running = texelFetch of the input (exact passthrough). Motion state = the `clock` Script
# CHOP (builders/fx_analog_crt_logic.py clock_step, same as crt). ASCII only.
import os

MODULE = 'crtfault'
_HERE = globals().get('HERE') or '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
LOGIC_FILE = os.path.join(_HERE, 'fx_analog_crt_logic.py')
CL = dict(globals())                     # TD names (textDAT, scriptCHOP, ...) for td_common (live fix)
with open(LOGIC_FILE) as _fh:
    exec(_fh.read(), CL)

PAGES = [
    ('Faults', [
        ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
        ('Roll', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Roll'}),
        ('Tear', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'H-hold tear'}),
        ('Jitter', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'H-sync jitter (1 = 8 px)'}),
        ('Humbar', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Hum Bar'}),
        ('Degauss', 'Pulse', None, {'label': 'Degauss'}),
        ('Power', 'Toggle', True, {'label': 'Power (off = collapse, on = warm-up)'}),
    ]),
    ('Deflection', [
        ('Rollbar', 'Float', 0.08, {'min': 0, 'max': 0.5, 'label': 'V blanking bar (heights)'}),
        ('Tearbands', 'Float', 2.0, {'min': 0.5, 'max': 8, 'label': 'Tear bands'}),
        ('Tearspeed', 'Float', 0.5, {'min': -4, 'max': 4, 'label': 'Tear speed, bands/s'}),
        ('Tearblank', 'Float', 0.12, {'min': 0, 'max': 0.5, 'label': 'H blanking (widths)'}),
        ('Bend', 'Float', 0.0, {'min': -1, 'max': 1, 'label': 'Top bend (flagging)'}),
        ('Wobble', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'S-wobble'}),
        ('Wobblefreq', 'Float', 2.0, {'min': 0.5, 'max': 8, 'label': 'Wobble cycles per height'}),
        ('Breathe', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Raster breathing (size follows brightness)'}),
    ]),
    ('Hum', [
        ('Humspeed', 'Float', 0.1, {'min': -1, 'max': 1, 'label': 'Hum speed, screens/s (+ up)'}),
        ('Humcount', 'Int', 1, {'min': 1, 'max': 6, 'label': 'Hum bars'}),
        ('Humsoft', 'Float', 0.5, {'min': 0, 'max': 1, 'label': 'Hum bar narrowness'}),
        ('Arc', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Arcing flashes'}),
        ('Degaussamt', 'Float', 1.0, {'min': 0, 'max': 2, 'label': 'Degauss strength'}),
        ('Powerdur', 'Float', 0.6, {'min': 0.1, 'max': 3, 'label': 'Power off/on time, s'}),
        ('Border', 'Menu', 'black', {'names': ['black', 'transparent'], 'labels': ['Black', 'Transparent'],
                                     'label': 'Border'}),
    ]),
    ('Random', [
        ('Seed', 'Int', 1, {'min': 0, 'max': 99, 'label': 'Seed'}),
        ('Randomness', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Randomness'}),
    ]),
    ('State', [
        ('Degausstime', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Last Degauss (absTime s)'}),
        ('Degausscount', 'Int', 0, {'min': 0, 'max': 100, 'label': 'Degauss count'}),
        ('Powertime', 'Float', -1.0, {'min': -1, 'max': 1, 'label': 'Last Power change (absTime s)'}),
    ]),
]
PANEL_PAGES = ['Faults', 'Deflection', 'Hum', 'Random']

_Z = {'Roll': 0.0, 'Tear': 0.0, 'Jitter': 0.0, 'Humbar': 0.0, 'Power': 1, 'Rollbar': 0.08, 'Tearbands': 2.0,
      'Tearspeed': 0.5, 'Tearblank': 0.12, 'Bend': 0.0, 'Wobble': 0.0, 'Wobblefreq': 2.0, 'Breathe': 0.0,
      'Humspeed': 0.1, 'Humcount': 1, 'Humsoft': 0.5, 'Arc': 0.0, 'Degaussamt': 1.0, 'Powerdur': 0.6, 'Border': 0,
      'Randomness': 0.0}
PRESETS = [
    (1, 'lost hold', dict(_Z, Amount=1.0, Roll=0.5, Tear=0.3, Humbar=0.4, Randomness=0.4)),
    (2, 'bad sync', dict(_Z, Amount=1.0, Tear=0.6, Tearbands=3.0, Tearspeed=1.2, Jitter=0.6, Bend=0.5,
                         Randomness=0.6)),
    (3, 'worn yoke', dict(_Z, Amount=1.0, Wobble=0.5, Bend=0.3, Breathe=0.6, Jitter=0.1, Randomness=0.3)),
    (4, 'hum + arcs', dict(_Z, Amount=1.0, Humbar=0.8, Humcount=2, Humsoft=0.3, Humspeed=0.25, Arc=0.4)),
    (5, 'clean (hits only)', dict(_Z, Amount=0.0)),
]

SHADER = """// FX_analog crtfault (compute, T-47; FX2 AV-07). in0 = picture, in1 = 1x1 average luma (Breathe) or a constant.
layout (local_size_x = 8, local_size_y = 8) in;
uniform vec4 uA;   // amount tear tearbands tearblank
uniform vec4 uB;   // jitter bend wobble wobblefreq
uniform vec4 uC;   // breathe arc border (0 black 1 transparent) humcount
uniform vec4 uD;   // humsoft 0 0 0
%(LIB)s
void main() {
    ivec2 P = ivec2(gl_GlobalInvocationID.xy);
    ivec2 R = ivec2(uTDOutputInfo.res.zw);
    if (P.x >= R.x || P.y >= R.y) return;
    vec4 src = texelFetch(sTD2DInputs[0], P, 0);
    float A = uA.x;
    vec4 pw = uK[11];                                   // power: sy sx gain dot
    bool steady = pw.x == 1.0 && pw.y == 1.0 && pw.z == 1.0 && pw.w == 0.0;
    if (A <= 0.0 && uK[3].w <= 0.0 && steady) { TDImageStoreOutput(0, ivec3(P, 0), src); return; }
    vec2 so = vec2(R);
    float aspect = so.x / so.y;
    vec2 uv = (vec2(P) + 0.5) / so;
    vec2 c = uv - 0.5;
    bool blank = !(abs(c.x) <= 0.5 * pw.y && abs(c.y) <= 0.5 * pw.x && pw.x > 0.0 && pw.y > 0.0);
    vec2 s = c / max(pw.yx, vec2(1e-4)) + 0.5;
    if (uC.x != 0.0) {                                  // raster breathing
        float lum = texelFetch(sTD2DInputs[1], ivec2(0), 0).r;
        s = (s - 0.5) / (1.0 + uC.x * 0.08 * (lum - 0.3) * A) + 0.5;
    }
    s = degaussShake(s);
    float rs = uK[0].x * A;
    if (rs != 0.0) {                                    // V-hold roll + blanking bar
        float v = mod(s.y - rs, 1.0 + uK[0].y);
        blank = blank || v > 1.0;
        s.y = min(v, 1.0);
    }
    float tear = uA.y * A;
    if (tear != 0.0) s.x += tear * 0.5 * mod(s.y * uA.z + uK[10].x, 1.0);
    float jit = uB.x * A;
    if (jit != 0.0) {
        int row = int(floor(s.y * so.y)) + 8192;
        s.x += (h01(uint(row) * 2654435761u ^ uint(uK[10].y), uint(uK[2].w) + 7u) - 0.5) * 2.0 * jit * 8.0 / so.x;
    }
    float bend = uB.y * A;
    if (bend != 0.0) s.x += bend * 0.05 * exp(-(1.0 - s.y) * 10.0);
    float wob = uB.z * A;
    if (wob != 0.0) s.x += wob * 0.01 * sin(6.2831853 * (s.y * uB.w + uK[10].z));
    if (tear != 0.0) {                                  // H blanking between the torn copies
        float xx = mod(s.x, 1.0 + uA.w);
        blank = blank || xx > 1.0;
        s.x = min(xx, 1.0);
    }
    vec4 col = texture(sTD2DInputs[0], clamp(s, 0.0, 1.0));
    float kk = pw.z;
    float hd = uK[1].y * A;
    if (hd > 0.0) {
        float hb = pow(0.5 + 0.5 * cos(6.2831853 * uC.w * (uv.y - uK[1].z)), 1.0 + 6.0 * uD.x);
        kk *= 1.0 - hd * hb;
    }
    col.rgb *= kk;
    if (uK[10].w > 0.0 && A > 0.0)                      // arc flash + a bright streak at a random row
        col.rgb += uK[10].w * A * (0.25 + 0.75 * exp(-abs(uv.y - uK[12].x) * so.y / 3.0));
    col.rgb *= purity(s, aspect);
    if (blank) col = vec4(0.0, 0.0, 0.0, uC.z > 0.5 ? 0.0 : 1.0);
    if (pw.w > 0.0) {                                   // the dot left after a power-off
        float r = length(vec2(c.x * aspect, c.y));
        float dv = pw.w * exp(-(r / 0.012) * (r / 0.012));
        col.rgb = max(col.rgb, vec3(dv));
        col.a = max(col.a, dv);
    }
    col = clamp(col, 0.0, 1.0);
    col.rgb = min(col.rgb, vec3(col.a));
    TDImageStoreOutput(0, ivec3(P, 0), col);
}
"""


def shader_texts():
    return {'fx': SHADER.replace('%(LIB)s', CL['GLSL_LIB'])}


P = "parent().par.{}.eval()"


def build(m, H):
    """Fill instance COMP m: in1 (+ avg luma) -> fx (one compute pass) -> out1, + crt_logic, clock, pulse_exec."""
    mk, expr = H['mk'], H['expr']
    in1 = mk(m, inTOP, 'in1')
    CL['td_common'](m, H, LOGIC_FILE, 'crt_logic', ['Degauss'], ['Power'])
    av = mk(m, analyzeTOP, 'avg')
    if not av.inputConnectors[0].connections:
        av.inputConnectors[0].connect(in1)
    av.par.op = 'average'
    av.par.analyzechannel = 'luminance'
    av.comment = 'Average luma (1x1) for Breathe; pulled only while Breathe != 0.'
    ln = mk(m, constantTOP, 'lum_none')
    ln.par.outputresolution = 'custom'
    ln.par.resolutionw, ln.par.resolutionh = 1, 1
    ln.par.colorr = ln.par.colorg = ln.par.colorb = 0.3
    ls = mk(m, switchTOP, 'lum_src')
    ls.inputConnectors[0].connect(ln)
    ls.inputConnectors[1].connect(av)
    expr(ls.par.index, '1 if %s != 0 else 0' % P.format('Breathe'))
    g = H['compute'](m, 'fx', shader_texts()['fx'], [in1, ls])
    g.par.inputextenduv = 'hold'
    g.par.inputfiltertype = 'linear'
    H['uniforms'](g, [
        ('uA', [P.format('Amount'), P.format('Tear'), P.format('Tearbands'), P.format('Tearblank')]),
        ('uB', [P.format('Jitter'), P.format('Bend'), P.format('Wobble'), P.format('Wobblefreq')]),
        ('uC', [P.format('Breathe'), P.format('Arc'), 'parent().par.Border.menuIndex', P.format('Humcount')]),
        ('uD', [P.format('Humsoft'), '0', '0', '0']),
    ])
    CL['td_clock_uniform'](g)
    g.comment = 'crtfault: power, breathing, roll, tear, jitter, bend, wobble, hum, arcs, Degauss. Amount 0 = exact.'
    out1 = mk(m, outTOP, 'out1')
    out1.inputConnectors[0].connect(g)
    return [
        {'title': '1 In', 'role': 'input', 'ops': ['in1', 'avg', 'lum_none', 'lum_src']},
        {'title': '2 Clock', 'role': 'control', 'ops': ['crt_logic', 'clock', 'clock_callbacks', 'pulse_exec'],
         'body': 'Per-frame state (roll, hum, tear, jitter, arcs, power, Degauss) -> uniform array uK.'},
        {'title': '3 Faults', 'role': 'process', 'ops': ['fx', 'fx_compute'], 'body': 'One compute pass.'},
        {'title': '4 Out', 'role': 'output', 'ops': ['out1']},
    ]
