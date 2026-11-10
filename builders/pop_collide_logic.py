# pop_collide_logic - numpy mirror of POP_collide's particle step (lane H TC-14; builder builders/pop_collide.py, doc
# docs/builds/pop_lane_h.md "TC-14") + the GLSL / par pieces POP_collide and POP_fillbody (TC-15) both use today
# (hash + value noise, points MAT, Persist look pass, Look page). Pure Python + numpy; runs OUTSIDE TD for references
# (T-184); the builders exec this file only to read its GLSL strings. Every numpy function matches the GLSL line by line
# (same hash, same order of colliders, same constants). ASCII only.
import math

import numpy as np

TAU = 6.283185307179586
M32 = 0xFFFFFFFF
SUBSTEPS_MAX = 4          # GLSL #define SUBSTEPS (bounded loop, T-35)
COUNT_CAP = 262144        # Count hard cap (T-124 / T-193)
EMIT_SHAPES = ['point', 'disc', 'line']

# ------------------------------------------------------------------------------------------------ shared GLSL
HASH_GLSL = """
const float TAU = 6.283185307179586;
uint lowbias(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float h1(int i, int s) { return float(lowbias(uint(i) * 747796405u + uint(s) * 2891336453u + 1u) >> 8) / 16777216.0; }
float h2(int x, int y, int s)
{
    uint h = lowbias(uint(y) * 2891336453u + uint(s) * 1597334677u + 7u);
    h = lowbias(h ^ (uint(x) * 747796405u));
    return float(h >> 8) / 16777216.0;
}
float vnoise(vec2 p, int s)
{
    vec2 i = floor(p);
    vec2 f = p - i;
    vec2 w = f * f * (3.0 - 2.0 * f);
    ivec2 k = ivec2(i);
    float a = h2(k.x, k.y, s), b = h2(k.x + 1, k.y, s), c = h2(k.x, k.y + 1, s), d = h2(k.x + 1, k.y + 1, s);
    return (a + (b - a) * w.x) * (1.0 - w.y) + (c + (d - c) * w.x) * w.y;
}
bool bad(vec4 a) { return any(isnan(a)) || any(isinf(a)); }
"""

POINTS_VERTEX = """// lane-H particle points (POP_collide / POP_fillbody): static Grid POP side x side points; TDPos() -> state texel
// (T-112). b0 = pos.xyz + life (<= 0 = not drawn), b1 = vel.xyz. Colour by speed (hue ramp), additive sprites.
uniform vec4 uD;    // side, count, size px, bright
uniform vec4 uC;    // hue slow, hue fast, saturation, speed for the fast hue
uniform sampler2D sP;
uniform sampler2D sV;
out Vertex { vec4 color; float size; } oV;
vec3 hsv2rgb(vec3 c)
{
    vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
    return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}
void main()
{
    int side = int(uD.x + 0.5);
    ivec2 t = ivec2(floor((TDPos().xy + 0.5) * float(max(side - 1, 0)) + 0.5));
    int i = t.y * side + t.x;
    vec4 p = texelFetch(sP, t, 0);
    vec4 v = texelFetch(sV, t, 0);
    bool alive = i < int(uD.y + 0.5) && p.w > 0.0;
    gl_Position = alive ? TDWorldToProj(TDDeform(p.xyz)) : vec4(2.0, 2.0, 2.0, 1.0);
    gl_PointSize = max(uD.z, 1.0);
    float k = clamp(length(v.xyz) * uC.w, 0.0, 1.0);
    vec3 rgb = hsv2rgb(vec3(mix(uC.x, uC.y, k), uC.z, 1.0)) * uD.w;
    oV.color = alive ? vec4(rgb, 1.0) : vec4(0.0);
    oV.size = gl_PointSize;
#ifdef TD_PICKING_ACTIVE
    TDWritePickingValues();
#endif
}
"""

POINTS_PIXEL = """// lane-H particle points pixel: 1 px = colour as is (exact additive), bigger = soft round sprite.
in Vertex { vec4 color; float size; } iV;
layout(location = 0) out vec4 fragColor;
void main()
{
    TDCheckDiscard();
    float w = 1.0;
    if (iV.size > 1.5) {
        vec2 d = gl_PointCoord * 2.0 - 1.0;
        w = max(1.0 - dot(d, d), 0.0);
        w *= w;
    }
    fragColor = TDOutputSwizzle(iV.color * w);
}
"""

LOOK_COMPUTE = """// lane-H look: acc (colour buffer 1, in place) = render x Gain + Persist x acc; out = acc over in1 (premultiplied).
layout(local_size_x = 8, local_size_y = 8) in;
uniform vec4 uL;    // persist, gain, -, -
void main()
{
    ivec2 p = ivec2(gl_GlobalInvocationID.xy);
    if (p.x >= int(uTDOutputInfo.res.z) || p.y >= int(uTDOutputInfo.res.w)) return;
    vec2 uv = (vec2(p) + 0.5) * uTDOutputInfo.res.xy;
    vec4 r = texture(sTD2DInputs[0], uv) * uL.y;
    vec4 acc = r + TDImageLoadOutput(1, ivec3(p, 0)) * uL.x;
    TDImageStoreOutput(1, ivec3(p, 0), acc);
    vec4 c = vec4(acc.rgb, clamp(acc.a, 0.0, 1.0));
    vec4 bg = texture(sTD2DInputs[1], uv);
    TDImageStoreOutput(0, ivec3(p, 0), c + bg * (1.0 - c.a));
}
"""

SIDE_E = "int(math.ceil(math.sqrt(max(min(parent().par.Count.eval(), %d), 1))))" % COUNT_CAP
POINT_SPEC = [
    ('uD', ("float(" + SIDE_E + ")", "float(parent().par.Count.eval())", "parent().par.Size.eval()",
            "parent().par.Bright.eval()")),
    ('uC', ("parent().par.Hue1.eval()", "parent().par.Hue2.eval()", "parent().par.Sat.eval()",
            "parent().par.Colorspeed.eval()")),
]
LOOK_SPEC = [('uL', ("parent().par.Persist.eval()", "parent().par.Gain.eval()", "0.0", "0.0"))]

LOOK_PAGE = ('Look', [
    ('Size', 'Float', 2.0, {'min': 1, 'max': 16, 'label': 'Point size px'}),
    ('Bright', 'Float', 0.6, {'min': 0, 'max': 4, 'label': 'Brightness'}),
    ('Hue1', 'Float', 0.55, {'min': 0, 'max': 1, 'label': 'Hue slow'}),
    ('Hue2', 'Float', 0.95, {'min': 0, 'max': 1, 'label': 'Hue fast'}),
    ('Sat', 'Float', 0.7, {'min': 0, 'max': 1, 'label': 'Saturation'}),
    ('Colorspeed', 'Float', 2.0, {'min': 0, 'max': 20, 'label': 'Speed for the fast hue (1 / units per s)'}),
    ('Gain', 'Float', 1.0, {'min': 0, 'max': 4, 'label': 'Render gain'}),
    ('Persist', 'Float', 0.0, {'min': 0, 'max': 0.99, 'label': 'Trails (0 = none)'}),
    ('Tilt', 'Float', 0.0, {'min': -80, 'max': 80, 'label': 'Tilt deg (x)'}),
    ('Orbit', 'Float', 0.0, {'min': -180, 'max': 180, 'label': 'Orbit deg (y)'}),
    ('Dist', 'Float', 1.2, {'min': 0.2, 'max': 5, 'label': 'Camera distance'}),
    ('Zoom', 'Float', 1.0, {'min': 0.25, 'max': 4, 'label': 'Zoom (1 = 1 unit tall frame at z 0)'}),
])

CAM = {'tz': "parent().par.Dist.eval()", 'viewanglemethod': ('menu', 'vertfov'),
       'fov': "2.0 * math.degrees(math.atan(0.5 / max(parent().par.Dist.eval(), 0.01))) / "
              "max(parent().par.Zoom.eval(), 0.01)",
       'near': 0.01, 'far': 100.0}

RESET_E = "1.0 if absTime.frame - (lambda k, f: k if k <= f else -99)(parent().fetch('jz_reset', -99, search=False), absTime.frame) < 3 else 0.0"
PEXEC = """# lane-H reset stamps: Reset pulse or a structural par change -> store the frame; the state pass resets while
# absTime.frame - jz_reset < 3 (idempotent: generation 0 -> spawn 1 every reset frame).
def onPulse(par):
    if par.name == 'Reset':
        parent().store('jz_reset', absTime.frame)
    return

def onValueChange(par, prev):
    parent().store('jz_reset', absTime.frame)
    return
"""


def side_of(count):
    return int(math.ceil(math.sqrt(max(min(count, COUNT_CAP), 1))))


# ------------------------------------------------------------------------------------------------ hash / noise
def lowbias(x):
    x = np.asarray(x, dtype=np.uint64) & M32
    x ^= x >> np.uint64(16)
    x = (x * np.uint64(0x7feb352d)) & M32
    x ^= x >> np.uint64(15)
    x = (x * np.uint64(0x846ca68b)) & M32
    x ^= x >> np.uint64(16)
    return x


def _u(i):
    return np.asarray(i, dtype=np.int64).astype(np.uint64) & M32


def h1(i, s):
    h = lowbias((_u(i) * np.uint64(747796405) + _u(s) * np.uint64(2891336453) + np.uint64(1)) & M32)
    return (h >> np.uint64(8)).astype(np.float64) / 16777216.0


def h2(x, y, s):
    h = lowbias((_u(y) * np.uint64(2891336453) + _u(s) * np.uint64(1597334677) + np.uint64(7)) & M32)
    h = lowbias(h ^ ((_u(x) * np.uint64(747796405)) & M32))
    return (h >> np.uint64(8)).astype(np.float64) / 16777216.0


def vnoise(px, py, s):
    px, py = np.asarray(px, dtype=np.float64), np.asarray(py, dtype=np.float64)
    ix, iy = np.floor(px), np.floor(py)
    fx, fy = px - ix, py - iy
    wx, wy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    ix, iy = ix.astype(np.int64), iy.astype(np.int64)
    a, b = h2(ix, iy, s), h2(ix + 1, iy, s)
    c, d = h2(ix, iy + 1, s), h2(ix + 1, iy + 1, s)
    return (a + (b - a) * wx) * (1 - wy) + (c + (d - c) * wx) * wy


# ------------------------------------------------------------------------------------------------ collide step
DEFAULTS = {
    'count': 16384, 'dt': 1.0 / 60.0, 'substeps': 2, 'time': 0.0, 'reset': 0, 'testmode': 0, 'testh': 0.4,
    'seed': 1, 'emitshape': 'line', 'emit': (0.0, 0.48, 0.0), 'emitsize': 0.25, 'emitv': (0.0, -0.1, 0.0),
    'spread': 0.05, 'life': 6.0, 'gravity': -0.8, 'drag': 0.1, 'wind': 0.2, 'windfreq': 3.0,
    'floor': 1, 'floory': -0.45, 'restitution': 0.5, 'friction': 0.1,
    'spheres': [(0.0, -0.1, 0.0, 0.12), (0.12, 0.15, 0.0, 0.07), (0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0)],
    'boxes': [((-0.12, -0.3, 0.0), (0.08, 0.03, 0.2), 1), ((0.0, 0.0, 0.0), (0.1, 0.1, 0.1), 0)],
}


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


def blank_state(count):
    s = side_of(count)
    return np.zeros((s * s, 4)), np.zeros((s * s, 4))


def _resolve(P, V, mask, n, d, e, fr):
    """mask (N,), n (N,3) unit normal, d (N,) penetration (< 0). p -= n d; outgoing: v = vt (1 - f) - e vn n."""
    if not mask.any():
        return
    p = P[mask, :3] - n[mask] * d[mask, None]
    v = V[mask, :3]
    vn = (v * n[mask]).sum(-1)
    vt = v - vn[:, None] * n[mask]
    out = vt * (1.0 - fr) - e * vn[:, None] * n[mask]
    inn = vn < 0
    v = np.where(inn[:, None], out, v)
    P[mask, :3] = p
    V[mask, :3] = v


def collide(P, V, p):
    e, fr = p['restitution'], p['friction']
    N = P.shape[0]
    if p['floor']:
        d = P[:, 1] - p['floory']
        n = np.tile([0.0, 1.0, 0.0], (N, 1))
        _resolve(P, V, d < 0, n, d, e, fr)
    for (cx, cy, cz, r) in p['spheres']:
        if r <= 0:
            continue
        q = P[:, :3] - np.array([cx, cy, cz])
        L = np.linalg.norm(q, axis=-1)
        d = L - r
        n = np.where((L > 1e-6)[:, None], q / np.maximum(L, 1e-6)[:, None], np.array([0.0, 1.0, 0.0]))
        _resolve(P, V, d < 0, n, d, e, fr)
    for (c, hb, on) in p['boxes']:
        if not on:
            continue
        q = P[:, :3] - np.array(c)
        dq = np.abs(q) - np.array(hb)
        inside = (dq < 0).all(-1)
        a = np.where(dq[:, 0] >= dq[:, 1], np.where(dq[:, 0] >= dq[:, 2], 0, 2), np.where(dq[:, 1] >= dq[:, 2], 1, 2))
        d = dq[np.arange(N), a]
        sg = np.where(q[np.arange(N), a] < 0, -1.0, 1.0)
        n = np.zeros((N, 3))
        n[np.arange(N), a] = sg
        _resolve(P, V, inside, n, d, e, fr)


def spawn(i, gen, p):
    """Particle ids i (array), new generation gen (array) -> pos (N,3), vel (N,3), life (N,)."""
    i = np.asarray(i, dtype=np.int64)
    s = np.asarray(gen, dtype=np.int64) * 7919 + int(p['seed'])
    r = [h1(i * 8 + k, s) for k in range(6)]
    shape = EMIT_SHAPES.index(p['emitshape']) if isinstance(p['emitshape'], str) else int(p['emitshape'])
    off = np.zeros((len(i), 3))
    if shape == 1:
        a, rad = TAU * r[0], np.sqrt(r[1]) * p['emitsize']
        off[:, 0], off[:, 2] = np.cos(a) * rad, np.sin(a) * rad
    elif shape == 2:
        off[:, 0] = (r[0] - 0.5) * 2.0 * p['emitsize']
    pos = np.array(p['emit']) + off
    vel = np.array(p['emitv']) + p['spread'] * 2.0 * np.stack([r[2] - 0.5, r[3] - 0.5, r[4] - 0.5], -1)
    life = p['life'] * (0.5 + r[5])
    return pos, vel, life


def step(P, V, p):
    """One state cook (= GLSL main) on float64 copies. P (N,4) = pos + life, V (N,4) = vel + generation (Testmode:
    steps since reset)."""
    P, V = P.copy(), V.copy()
    N = P.shape[0]
    n = 1 if p['testmode'] else min(int(p['count']), N)
    idx = np.arange(N)
    dead = idx >= n
    if p['reset']:
        P[:, 3] = 0.0
        V[:, 3] = 0.0
    badm = ~np.isfinite(P).all(-1) | ~np.isfinite(V).all(-1)
    P[badm] = 0.0
    V[badm] = 0.0
    if p['testmode']:
        sp = (~dead) & ((P[:, 3] <= 0) | (p['reset'] > 0))
        P[sp] = [0.0, p['testh'], 0.0, 1.0]
        V[sp] = 0.0
        run = (~dead) & ~sp
    else:
        sp = (~dead) & (P[:, 3] <= 0)
        if sp.any():
            g = np.floor(V[sp, 3] + 0.5) + 1
            pos, vel, life = spawn(idx[sp], g, p)
            P[sp, :3], P[sp, 3] = pos, life
            V[sp, :3], V[sp, 3] = vel, g
        run = (~dead) & ~sp
    P[dead] = [0.0, -1000.0, 0.0, -1.0]
    V[dead] = 0.0
    if run.any():
        Pr, Vr = P[run], V[run]
        nsub = max(1, min(int(p['substeps']), SUBSTEPS_MAX))
        h = p['dt'] / nsub
        t = p['time']
        for _ in range(nsub):
            acc = np.zeros((len(Pr), 3))
            acc[:, 1] = p['gravity']
            if not p['testmode']:
                bx, by = Pr[:, 0] * p['windfreq'], Pr[:, 1] * p['windfreq']
                acc[:, 0] += p['wind'] * (vnoise(bx + t, by, int(p['seed'])) - 0.5)
                acc[:, 1] += p['wind'] * (vnoise(bx + 17.3, by + t, int(p['seed'])) - 0.5)
            Vr[:, :3] += acc * h
            if not p['testmode']:
                Vr[:, :3] *= max(1.0 - p['drag'] * h, 0.0)
            Pr[:, :3] += Vr[:, :3] * h
            collide(Pr, Vr, p)
        if p['testmode']:
            Vr[:, 3] += 1.0
        else:
            Pr[:, 3] -= p['dt']
        P[run], V[run] = Pr, Vr
    return P, V


def test_series(p, frames):
    """Testmode particle 0 per cook after a Reset cook: list of (steps, y, vy). Matches V.w = steps live."""
    q = dict(p, testmode=1)
    P, V = blank_state(1)
    P, V = step(P, V, dict(q, reset=1))
    out = []
    for _ in range(frames):
        P, V = step(P, V, dict(q, reset=0))
        out.append((int(V[0, 3]), P[0, 1], V[0, 1]))
    return out


def apexes(series):
    """Local maxima of y after the first impact (the bounce apexes)."""
    ys = [s[1] for s in series]
    return [ys[k] for k in range(1, len(ys) - 1) if ys[k] >= ys[k - 1] and ys[k] > ys[k + 1]]
