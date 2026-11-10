# gen_sdf_fractal2d - GEN_sdf module 'fractal2d' (FX5 G14 2D part, FX0 row 67): escape-time fractals (Mandelbrot,
# Julia, Burning Ship, Tricorn, Multibrot z^n) with smooth iteration colour, orbit traps (point / line / circle),
# distance-estimate edges, dive zoom (Zoomspeed octaves/s, beat + audio kicks) and DEEP ZOOM: Precision 'perturb'
# iterates float32 deltas against a reference orbit computed on the CPU in float64 (or Decimal when Deepx / Deepy
# hold more digits; stored as float32 hi + lo pairs) by the `ref` Script TOP, with rebasing (when |z| < |dz| or the reference ends: dz = z - Z0,
# restart the reference) instead of glitch detection. Mandelbrot + Julia only (power 2). Mirror:
# gen_sdf_logic.fractal2d_*; the reference code below is shared by TD and the mirror. ASCII only.
MODULE = 'fractal2d'
KIND = 'flat'
BLURB = 'Escape-time 2D fractals, smooth colour / traps / DE edges, dive zoom, perturbation deep zoom.'
TYPES = ['mandelbrot', 'julia', 'burningship', 'tricorn', 'multibrot']
COLOURING = ['smooth', 'trappoint', 'trapline', 'trapcircle', 'edge']

PAGES = [('Fractal2d', [
    ('Amount', 'Float', 1.0, {'min': 0, 'max': 1, 'label': 'Amount'}),
    ('Type', 'Menu', 'mandelbrot', {'names': TYPES, 'labels': ['Mandelbrot', 'Julia', 'Burning Ship', 'Tricorn', 'Multibrot z^n']}),
    ('Iterations', 'Int', 256, {'min': 16, 'max': 4096, 'label': 'Iterations (cap 8192)'}),
    ('Centerx', 'Float', -0.5, {'min': -2, 'max': 2, 'label': 'Centre x (re)'}),
    ('Centery', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Centre y (im)'}),
    ('Zoom', 'Float', 1.0, {'min': 0.1, 'max': 1000, 'label': 'Zoom (1 = 3 units per screen height)'}),
    ('Zoomspeed', 'Float', 0.0, {'min': -4, 'max': 4, 'label': 'Dive (zoom octaves/s)'}),
    ('Beatzoom', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Beat pulse -> zoom octaves'}),
    ('Rotate', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Rotate deg'}),
    ('Rotspeed', 'Float', 0.0, {'min': -90, 'max': 90, 'label': 'Rotate deg/s'}),
    ('Juliacx', 'Float', -0.8, {'min': -2, 'max': 2, 'label': 'Julia c re'}),
    ('Juliacy', 'Float', 0.156, {'min': -2, 'max': 2, 'label': 'Julia c im'}),
    ('Juliaorbit', 'Float', 0.0, {'min': 0, 'max': 1, 'label': 'Julia c orbit radius'}),
    ('Juliaspeed', 'Float', 0.2, {'min': -4, 'max': 4, 'label': 'Julia c orbit rad/s'}),
    ('Power', 'Float', 3.0, {'min': 2, 'max': 12, 'label': 'Power (multibrot)'}),
    ('Powerswing', 'Float', 0.0, {'min': 0, 'max': 4, 'label': 'Power swing'}),
    ('Powerspeed', 'Float', 0.3, {'min': 0, 'max': 4, 'label': 'Power swing rad/s'}),
    ('Colouring', 'Menu', 'smooth', {'names': COLOURING, 'labels': ['Smooth iteration', 'Trap: point', 'Trap: line', 'Trap: circle', 'Edge (distance estimate)']}),
    ('Interior', 'Menu', 'black', {'names': ['black', 'trap'], 'labels': ['Black', 'Trap colour']}),
    ('Trapx', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Trap x'}),
    ('Trapy', 'Float', 0.0, {'min': -2, 'max': 2, 'label': 'Trap y'}),
    ('Trapr', 'Float', 0.5, {'min': 0, 'max': 2, 'label': 'Trap circle radius'}),
    ('Edgewidth', 'Float', 1.5, {'min': 0.1, 'max': 20, 'label': 'Edge glow width px'}),
    ('Bailout', 'Float', 256.0, {'min': 2, 'max': 4096, 'label': 'Bailout radius'}),
    ('Cyclecheck', 'Toggle', True, {'label': 'Interior cycle check (float mode; stops repeating orbits early)'}),
    ('Precision', 'Menu', 'float', {'names': ['float', 'perturb'], 'labels': ['Float (fast, zoom < ~1e4)', 'Perturbation (deep zoom; Mandelbrot / Julia)']}),
    ('Deepx', 'Str', '', {'label': 'Deep centre x (digits; overrides, perturb)'}),
    ('Deepy', 'Str', '', {'label': 'Deep centre y (digits; overrides, perturb)'}),
])]
DEFAULTS = {'Palette': 2}
PANEL_PAGES = ['Fractal2d', 'Render', 'Colour', 'Drive']
SEAHORSE = (-0.743643887037151, 0.131825904205330)
PRESETS = [
    (1, 'mandelbrot', {'Type': 0, 'Centerx': -0.6, 'Centery': 0.0, 'Zoom': 0.8, 'Palette': 2, 'Spread': 1.0}),
    (2, 'seahorse dive', {'Type': 0, 'Centerx': SEAHORSE[0], 'Centery': SEAHORSE[1], 'Zoom': 1.0, 'Zoomspeed': 0.5,
                          'Iterations': 600, 'Precision': 1, 'Quality': 0.35, 'Palette': 7, 'Spread': 0.5,
                          'Huecycle': 0.05}),
    (3, 'julia orbit', {'Type': 1, 'Centerx': 0.0, 'Centery': 0.0, 'Zoom': 0.9, 'Juliaorbit': 0.05,
                        'Juliaspeed': 0.3, 'Colouring': 4, 'Edgewidth': 2.0, 'Palette': 6}),
    (4, 'burning ship', {'Type': 2, 'Centerx': -1.755, 'Centery': -0.03, 'Zoom': 12.0, 'Rotate': 180.0,
                         'Palette': 3, 'Spread': 0.7}),
    (5, 'multibrot traps', {'Type': 4, 'Centerx': 0.0, 'Centery': 0.0, 'Zoom': 0.9, 'Iterations': 96, 'Power': 3.0,
                            'Powerswing': 1.0,
                            'Powerspeed': 0.2, 'Colouring': 3, 'Interior': 1, 'Trapr': 0.6, 'Palette': 7,
                            'Rotspeed': 5.0}),
    (6, 'deep 1e10 still', {'Type': 0, 'Centerx': SEAHORSE[0], 'Centery': SEAHORSE[1], 'Zoom': 1e10,
                            'Iterations': 3000, 'Precision': 1, 'Quality': 0.5, 'Palette': 4,
                            'Spread': 0.25}),
]
CHECK = {'t': 1.0, 'beats': 0.0}
UNIFORMS = [('uM0', ['{Type#}', '{Iterations}', '{Colouring#}', '{Interior#}']),
            ('uM1', ['{Centerx}', '{Centery}', 'math.log2(3.0 / max({Zoom}, 1e-30))', '{Zoomspeed}']),   # log2: pars < 1e-5 read 0
            ('uM2', ['{Juliacx}', '{Juliacy}', '{Juliaorbit}', '{Juliaspeed}']),
            ('uM3', ['{Power}', '{Powerspeed}', '{Beatzoom}', 'math.radians({Rotate})']),
            ('uM4', ['math.radians({Rotspeed})', '{Trapx}', '{Trapy}', '{Trapr}']),
            ('uM5', ['{Edgewidth}', '{Precision#}', '{Bailout} * {Bailout}', '{Powerswing}']),
            ('uM6', ['{Cyclecheck}', '0', '0', '0'])]

GLSL = """
vec2 cmul(vec2 a, vec2 b) { return vec2(a.x * b.x - a.y * b.y, a.x * b.y + a.y * b.x); }
float trapd(vec2 z, int cm) {
    if (cm == 2) return abs(z.y - uM4.z);
    if (cm == 3) return abs(length(z - uM4.yz) - uM4.w);
    return length(z - uM4.yz);
}
vec4 render2d(vec2 P) {
    int ty = int(uM0.x + 0.5), IT = int(uM0.y + 0.5), cm = int(uM0.z + 0.5);
    float pw = uM3.x + uM5.w * sin(uM3.y * T);
    float sc = exp2(uM1.z - (uM1.w * T + uM3.z * ENV + LEVEL));
    vec2 uv = rot2((P - 0.5 * RES) / RES.y, uM3.w + uM4.x * T) * sc;
    float wj = uM2.w * T;
    vec2 J = uM2.xy + uM2.z * vec2(cos(wj), sin(wj));
    float dadd = ty == 1 ? 0.0 : 1.0;
    vec2 der = ty == 1 ? vec2(1.0, 0.0) : vec2(0.0);
    vec2 z;
    float trap = 1e10, r2 = 0.0;
    int it = 0;
    bool esc = false;
    if (uM5.y > 0.5 && ty <= 1) {
        int RL = max(textureSize(sTD2DInputs[0], 0).x - 1, 1);
        vec4 R0 = texelFetch(sTD2DInputs[0], ivec2(0, 0), 0);
        vec2 dz = ty == 1 ? uv : vec2(0.0);
        vec2 dc = ty == 1 ? vec2(0.0) : uv;
        int m = 0;
        z = R0.xy + (R0.zw + dz);
        for (int i = 0; i < MAXIT2D; i++) {
            if (i >= IT) break;
            vec2 Zm = texelFetch(sTD2DInputs[0], ivec2(m, 0), 0).xy;
            der = 2.0 * cmul(z, der) + vec2(dadd, 0.0);
            dz = cmul(2.0 * Zm + dz, dz) + dc;
            m++;
            vec4 Rm = texelFetch(sTD2DInputs[0], ivec2(m, 0), 0);
            z = Rm.xy + (Rm.zw + dz);
            r2 = dot(z, z);
            trap = min(trap, trapd(z, cm));
            it = i + 1;
            if (r2 > uM5.z) { esc = true; break; }
            if (r2 < dot(dz, dz) || m >= RL - 1) { dz = (Rm.xy - R0.xy) + (Rm.zw - R0.zw + dz); m = 0; }
        }
    } else {
        vec2 c;
        if (ty == 1) { z = uM1.xy + uv; c = J; } else { z = vec2(0.0); c = uM1.xy + uv; }
        bool cyc = uM6.x > 0.5;
        vec2 zs = z;
        int pk = 8, pc = 0;
        for (int i = 0; i < MAXIT2D; i++) {
            if (i >= IT) break;
            if (ty == 4) {
                float r = length(z);
                if (r < 1e-20) { der = vec2(dadd, 0.0); z = c; }
                else {
                    float a = atan(z.y, z.x);
                    vec2 zp = pow(r, pw) * vec2(cos(pw * a), sin(pw * a));     // z^pw
                    der = pw * cmul(cmul(zp, vec2(z.x, -z.y)) / max(r * r, 1e-30), der) + vec2(dadd, 0.0);   // z^(pw-1) = z^pw conj(z) / r^2
                    z = zp + c;
                }
            } else {
                der = 2.0 * cmul(z, der) + vec2(dadd, 0.0);
                if (ty == 2) z = abs(z);
                if (ty == 3) z.y = -z.y;
                z = cmul(z, z) + c;
            }
            r2 = dot(z, z);
            trap = min(trap, trapd(z, cm));
            it = i + 1;
            if (r2 > uM5.z) { esc = true; break; }
            if (cyc) {                                   // Brent periodicity: a repeating orbit is interior
                vec2 dd = z - zs;
                if (dot(dd, dd) < 1e-12) break;
                pc++;
                if (pc == pk) { zs = z; pc = 0; pk *= 2; }
            }
        }
    }
    float lp = log(ty == 4 ? max(pw, 1.0001) : 2.0);
    float mu = esc ? float(it) + 1.0 - log(max(0.5 * log(r2), 1e-9)) / lp : -1.0;
    float dep = esc ? 0.5 * sqrt(r2) * log(r2) / max(length(der), 1e-30) / (sc / RES.y) : -1.0;
    if (int(uMat.y + 0.5) == 1) return vec4(mu, esc ? 1.0 : 0.0, trap, dep);
    float k, v;
    bool inner = uM0.w > 0.5;
    float ks = 0.3 * log2(1.0 + max(mu, 0.0));
    if (cm == 0) { k = esc ? ks : trap; v = esc || inner ? 1.0 : 0.0; }
    else if (cm == 4) { k = esc ? ks : trap; v = esc ? exp(-dep / max(uM5.x, 1e-3)) : (inner ? 1.0 : 0.0); }
    else { k = trap; v = esc || inner ? 1.0 : 0.0; }
    return vec4(palk(k) * v, v);
}
"""

# ------------------------------------------------------------------ reference orbit (TD Script TOP + offline mirror)
REF_PY = '''# GEN_sdf fractal2d reference orbit (builders/gen_sdf_fractal2d.py REF_PY; the offline mirror runs this same text)
import math


def ref_orbit(kind, cx, cy, jx, jy, n, digits=0):
    """kind 0 Mandelbrot (Z0 = 0, C = centre), 1 Julia (Z0 = centre, C = j). cx / cy float or digit strings.
    digits > 0: Decimal arithmetic at that precision (deep zoom). Returns [(x, y)] Z_0 .. Z_{L-1}, L <= n + 1,
    stopping after the first |Z|^2 > 4."""
    if digits > 0:
        from decimal import Decimal, getcontext
        getcontext().prec = int(digits)
        X, Y, JX, JY, four = Decimal(str(cx)), Decimal(str(cy)), Decimal(repr(jx)), Decimal(repr(jy)), Decimal(4)
    else:
        X, Y, JX, JY, four = float(cx), float(cy), float(jx), float(jy), 4.0
    if kind == 0:
        zx, zy, ax, ay = X * 0, Y * 0, X, Y
    else:
        zx, zy, ax, ay = X, Y, JX, JY
    out = [(float(zx), float(zy))]
    for _ in range(int(n)):
        zx, zy = zx * zx - zy * zy + ax, 2 * zx * zy + ay
        out.append((float(zx), float(zy)))
        if zx * zx + zy * zy > four:
            break
    return out


def ref_array(orb):
    """numpy rgba32 row of len(orb) + 1 texels (the shader's reference length = width - 1): texel n = Z_n as two
    floats, (hi x, hi y, lo x, lo y) with hi = float32(Z), lo = float32(Z - hi), so z = hi + (lo + dz) keeps the
    float64 reference where z is small (rebasing)."""
    import numpy as np
    a = np.zeros((1, len(orb) + 1, 4), dtype=np.float32)
    for i, (x, y) in enumerate(orb):
        hx, hy = np.float32(x), np.float32(y)
        a[0, i] = (hx, hy, np.float32(x - float(hx)), np.float32(y - float(hy)))
    return a
'''

REF_CALLBACK = '''

def onSetupParameters(scriptOp):
    return


def onCook(scriptOp):
    import numpy as np
    m = scriptOp.parent()
    ty = m.par.Type.menuIndex
    if m.par.Precision.menuIndex == 0 or ty > 1:             # float mode: nothing to compute, no dependencies
        scriptOp.copyNumpyArray(np.zeros((1, 2, 4), dtype=np.float32))
        return
    n = min(int(m.par.Iterations.eval()), 16383)
    jx, jy = m.par.Juliacx.eval(), m.par.Juliacy.eval()
    if ty == 1 and m.par.Juliaorbit.eval() != 0:             # orbiting Julia c: follows the module clock
        t = float(m.op('clock_int')[0]) + m.par.Phase.eval()
        w = m.par.Juliaspeed.eval() * t
        jx += m.par.Juliaorbit.eval() * math.cos(w)
        jy += m.par.Juliaorbit.eval() * math.sin(w)
    sx, sy = m.par.Deepx.eval().strip(), m.par.Deepy.eval().strip()
    cx = sx if sx else m.par.Centerx.eval()
    cy = sy if sy else m.par.Centery.eval()
    digits = max(len(sx), len(sy)) + 10 if (sx or sy) else 0
    scriptOp.copyNumpyArray(ref_array(ref_orbit(ty, cx, cy, jx, jy, n, digits)))
    return
'''
