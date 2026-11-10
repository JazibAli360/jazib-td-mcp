# fx_glitch_misc_logic - numpy reference of FX_glitch module 'misc' (builders/fx_glitch_misc.py), the same maths as
# the fx / stats compute shaders, for offline tests and LIVE parity (exec this file inside TD, feed it in1's pixels).
# Arrays are [y, x, rgba] float in TD pixel coords: row 0 = BOTTOM (as TOP.numpyArray() returns them), 0..1.
# Sampling mirrors the GLSL TOP: texelFetch = img[y, x]; texture() = bilinear at pixel centres with extend hold.
# The uint hash is the shader's lowbias32 (fx_destroy GLSL_LIB), done in uint64 & 0xffffffff (exact).
# Pure Python + numpy, no TD names. ASCII only.
import math

import numpy as np

TYPES = ['bend', 'suck', 'tri', 'longshadow', 'electrify', 'autolevel', 'displace', 'zap', 'arcs']

DEFAULTS = {
    'Amount': 1.0, 'Type': 0, 'Strength': 1.0, 'Size': 40.0, 'Angle': 0.0, 'Length': 240.0, 'Threshold': 0.5,
    'Softness': 0.1, 'Decay': 0.6, 'Width': 3.0, 'Rate': 0.0, 'Seed': 1,
    'Pointu': 0.5, 'Pointv': 0.5, 'Point2u': 0.5, 'Point2v': 0.95,
    'Colr': 0.55, 'Colg': 0.75, 'Colb': 1.0, 'Glow': 1.5,
    'Detail': 0.08, 'Levels': 3, 'Edges': 0.3,
    'Clip': 0.0, 'Linked': 0, 'Smooth': 0.3, 'Level': 4,
    'Prism': 0.0, 'Jag': 0.15, 'Branches': 3,
    'Lattice': 1, 'Pointspace': 0, 'Arcmode': 0, 'Reach': 0.4, 'Arcfalloff': 1.0, 'Maxarcs': 16,
}

M32 = 0xFFFFFFFF
LUMA = np.array([0.2126, 0.7152, 0.0722])


def type_index(t):
    return TYPES.index(t) if isinstance(t, str) else int(t)


def full_pars(pars=None):
    p = dict(DEFAULTS)
    p.update(pars or {})
    p['Type'] = type_index(p['Type'])
    return p


# ------------------------------------------------------------------ hash / noise (exact uint32)
def _u(x):
    """any int-like (negative ok) -> uint64 array holding the uint32 two's complement value"""
    return (np.asarray(x, dtype=np.int64) & M32).astype(np.uint64)


def lb32(x):
    x = _u(x)
    x = x ^ (x >> np.uint64(16))
    x = (x * np.uint64(0x7feb352d)) & np.uint64(M32)
    x = x ^ (x >> np.uint64(15))
    x = (x * np.uint64(0x846ca68b)) & np.uint64(M32)
    x = x ^ (x >> np.uint64(16))
    return x


def hsh(cx, cy, s):
    """GLSL hsh(ivec2(cx, cy), uint s) -> [0, 1)"""
    a = (_u(cx) * np.uint64(1597334677)) & np.uint64(M32)
    b = lb32(_u(cy) ^ ((_u(s) * np.uint64(2654435761)) & np.uint64(M32)))
    return lb32(a ^ b).astype(np.float64) * (1.0 / 4294967296.0)


def vnoise(x, y, s):
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    fx = fx * fx * (3.0 - 2.0 * fx)
    fy = fy * fy * (3.0 - 2.0 * fy)
    ix, iy = ix.astype(np.int64), iy.astype(np.int64)
    a, b = hsh(ix, iy, s), hsh(ix + 1, iy, s)
    c, d = hsh(ix, iy + 1, s), hsh(ix + 1, iy + 1, s)
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy


def vn1(x, s):
    i = np.floor(x)
    f = x - i
    f = f * f * (3.0 - 2.0 * f)
    i = i.astype(np.int64)
    a, b = hsh(i, 0, s), hsh(i + 1, 0, s)
    return a + (b - a) * f


def fbm1(x, s):
    v, a, n = 0.0, 0.5, 0.0
    x = np.asarray(x, dtype=np.float64)
    for k in range(5):
        v = v + a * vn1(x, (int(s) + k * 101) & M32)
        n += a
        x = x * 2.03 + 17.1
        a *= 0.5
    return v / n


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------ sampling
def tex(img, qx, qy):
    """texture() at pixel-space points (centre of pixel i = i + 0.5), bilinear, extend hold -> [..., 4]"""
    h, w = img.shape[:2]
    x, y = np.asarray(qx, dtype=np.float64) - 0.5, np.asarray(qy, dtype=np.float64) - 0.5
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    x0, y0 = x0.astype(np.int64), y0.astype(np.int64)
    xa, xb = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1)
    ya, yb = np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
    a = img[ya, xa] * (1 - fx) + img[ya, xb] * fx
    b = img[yb, xa] * (1 - fx) + img[yb, xb] * fx
    return a * (1 - fy) + b * fy


def tex_uv(img, u, v):
    h, w = img.shape[:2]
    return tex(img, np.asarray(u) * w, np.asarray(v) * h)


def luma(c):
    return c[..., 0] * LUMA[0] + c[..., 1] * LUMA[1] + c[..., 2] * LUMA[2]


def grid(h, w):
    y, x = np.mgrid[0:h, 0:w]
    return x + 0.5, y + 0.5


def epoch(t, rate):
    return int(math.floor(t * rate))


def seed_mix(seed, ep):
    return (int(seed) * 7919 + int(ep) * 104729) & M32


# ------------------------------------------------------------------ the types (o = effect before the Amount mix)
def _bend(img, p, px, py):
    h, w = img.shape[:2]
    cx, cy = p['Pointu'] * w, p['Pointv'] * h
    rx, ry = px - cx, py - cy
    a = np.arctan2(ry, rx)
    up = a / 6.2831853 + 0.5 + p['Angle'] / 360.0
    up = up - np.floor(up)
    sx, sy = up * w, np.hypot(rx, ry) / max(p['Length'], 1e-3) * h
    k = p['Strength']
    return tex(img, px + (sx - px) * k, py + (sy - py) * k)


def _suck(img, p, px, py):
    h, w = img.shape[:2]
    cx, cy = p['Pointu'] * w, p['Pointv'] * h
    dx, dy = px - cx, py - cy
    r = np.hypot(dx, dy)
    L = max(p['Length'], 1e-3)
    rs = r * (1.0 + p['Strength'] * L / (r + L))
    sw = math.radians(p['Angle']) * np.exp(-r / L)
    safe = np.where(r > 1e-4, r, 1.0)
    ux, uy = np.where(r > 1e-4, dx / safe, 0.0), np.where(r > 1e-4, dy / safe, 0.0)
    cs, sn = np.cos(sw), np.sin(sw)
    s = tex(img, cx + (cs * ux - sn * uy) * rs, cy + (sn * ux + cs * uy) * rs)
    Rh = p['Size']
    hole = 1.0 - smoothstep(Rh, Rh * (1.0 + p['Softness']) + 1.0, r)
    o = s.copy()
    o[..., :3] = s[..., :3] * (1.0 - hole)[..., None]
    return o


def _bary(a, b, c, q):
    v0, v1, v2 = b - a, c - a, q - a
    d00 = (v0 * v0).sum(-1)
    d01 = (v0 * v1).sum(-1)
    d11 = (v1 * v1).sum(-1)
    d20 = (v2 * v0).sum(-1)
    d21 = (v2 * v1).sum(-1)
    den = d00 * d11 - d01 * d01
    v = (d11 * d20 - d01 * d21) / den
    ww = (d00 * d21 - d01 * d20) / den
    return np.stack([1.0 - v - ww, v, ww], -1)


def _tri(img, p, px, py):
    h, w = img.shape[:2]
    s = max(p['Size'], 1.0)
    an = math.radians(p['Angle'])
    ca, sa = math.cos(an), math.sin(an)
    q0x, q0y = px - 0.5 * w, py - 0.5 * h
    q = np.stack([ca * q0x + sa * q0y, -sa * q0x + ca * q0y], -1)
    hh = s * 0.8660254
    j = np.floor(q[..., 1] / hh)
    fy = q[..., 1] / hh - j
    xs = q[..., 0] / s - 0.5 * (q[..., 1] / hh if p.get('Lattice', 1) else j)   # 0 = the 26 Oct row-shifted look
    i = np.floor(xs)
    fx = xs - i
    up = (fx + fy >= 1.0)[..., None]

    def cart(a, b):
        return np.stack([(a + 0.5 * b) * s, b * hh], -1)
    V0 = np.where(up, cart(i + 1, j), cart(i, j))
    V1 = np.where(up, cart(i + 1, j + 1), cart(i + 1, j))
    V2 = cart(i, j + 1)

    def unrot(v):
        return ca * v[..., 0] - sa * v[..., 1] + 0.5 * w, sa * v[..., 0] + ca * v[..., 1] + 0.5 * h

    def lt(v):
        return luma(tex(img, *unrot(v)))
    active = np.ones(q.shape[:2], bool)
    for k in range(4):
        if k >= p['Levels']:
            break
        G = (V0 + V1 + V2) / 3.0
        lg = lt(G)
        var = np.maximum(np.maximum(np.abs(lt(V0) - lg), np.abs(lt(V1) - lg)), np.abs(lt(V2) - lg))
        active = active & (var > p['Detail'])
        if not active.any():
            break
        l = _bary(V0, V1, V2, q)
        m01, m12, m20 = (V0 + V1) / 2, (V1 + V2) / 2, (V2 + V0) / 2
        c0 = l[..., 0] > 0.5
        c1 = ~c0 & (l[..., 1] > 0.5)
        c2 = ~c0 & ~c1 & (l[..., 2] > 0.5)
        cc = ~c0 & ~c1 & ~c2
        a = active[..., None]
        n0 = np.where(c0[..., None], V0, np.where(c1[..., None], m01, np.where(c2[..., None], m20, m12)))
        n1 = np.where(c0[..., None], m01, np.where(c1[..., None], V1, np.where(c2[..., None], m12, m20)))
        n2 = np.where(c0[..., None], m20, np.where(c1[..., None], m12, np.where(c2[..., None], V2, m01)))
        del cc
        V0, V1, V2 = np.where(a, n0, V0), np.where(a, n1, V1), np.where(a, n2, V2)
    G = (V0 + V1 + V2) / 3.0
    col = tex(img, *unrot(G))
    l = _bary(V0, V1, V2, q)
    dpx = l.min(-1) * np.hypot(*(V1 - V0).transpose(2, 0, 1)) * 0.8660254
    o = col.copy()
    o[..., :3] = col[..., :3] * (1.0 - p['Edges'] * (1.0 - smoothstep(0.0, 1.5, dpx)))[..., None]
    return o


def _cast(c, p):
    t, sft = p['Threshold'], p['Softness']
    return smoothstep(t - sft, t + sft + 1e-4, luma(c)) * c[..., 3]


def _longshadow(img, p, px, py, c):
    an = math.radians(p['Angle'])
    dx, dy = math.sin(an), -math.cos(an)
    L = p['Length']
    N = int(min(max(math.ceil(L / 6.0), 1.0), 32.0))
    stp = L / N
    sh = np.zeros(px.shape)
    for k in range(1, N + 1):
        s = tex(img, px - dx * stp * k, py - dy * stp * k)
        sh = np.maximum(sh, _cast(s, p) * (1.0 - (k / N) * p['Decay']))
    sh = sh * (1.0 - _cast(c, p))
    t = (sh * p['Strength'])[..., None]
    o = c.copy()
    col = np.array([p['Colr'], p['Colg'], p['Colb']])
    o[..., :3] = c[..., :3] + (col - c[..., :3]) * t
    return o


def _electrify(img, p, px, py, ep, c):
    sd = seed_mix(p['Seed'], ep)
    sz = max(p['Size'], 1.0)
    nx, ny = px / sz, py / sz
    jx = (vnoise(nx, ny, sd) - 0.5) * 2.0 * p['Length']
    jy = (vnoise(nx + 31.7, ny + 31.7, (sd + 17) & M32) - 0.5) * 2.0 * p['Length']
    qx, qy = px + jx, py + jy
    w = max(p['Width'], 0.5)

    def L(ox, oy):
        return luma(tex(img, qx + ox, qy + oy))
    tl, t, tr = L(-w, w), L(0, w), L(w, w)
    l, r = L(-w, 0), L(w, 0)
    bl, b, br = L(-w, -w), L(0, -w), L(w, -w)
    gx = (tr + 2 * r + br) - (tl + 2 * l + bl)
    gy = (tl + 2 * t + tr) - (bl + 2 * b + br)
    e = np.hypot(gx, gy)
    g = smoothstep(p['Threshold'], p['Threshold'] + p['Softness'] + 1e-4, e)
    fl = 0.4 + 0.6 * float(hsh(7, 11, sd))
    o = c.copy()
    col = np.array([p['Colr'], p['Colg'], p['Colb']])
    o[..., :3] = c[..., :3] + col * (p['Glow'] * fl * p['Strength']) * g[..., None]
    return o


def ref_stats(img, level=4):
    """APPROXIMATE stats texel pair (lo rgb, hi rgb, mean luma) from a 2x2 box mip chain with floor sizes. TD's own
    mips may differ at odd sizes; live parity feeds the real stats texels to reference(stats=...)."""
    m = np.asarray(img, dtype=np.float64)
    for _ in range(int(level)):
        h, w = m.shape[0] // 2, m.shape[1] // 2
        if h < 1 or w < 1:
            break
        m = 0.25 * (m[0:2 * h:2, 0:2 * w:2] + m[1:2 * h:2, 0:2 * w:2] + m[0:2 * h:2, 1:2 * w:2] +
                    m[1:2 * h:2, 1:2 * w:2])
    rgb = m[..., :3].reshape(-1, 3)
    return rgb.min(0), rgb.max(0), float(luma(rgb).mean())


def _autolevel(img, p, stats, c):
    lo, hi, _mean = stats if stats is not None else ref_stats(img, p['Level'])
    lo, hi = np.array(lo, dtype=np.float64), np.array(hi, dtype=np.float64)
    if p['Linked']:
        lo, hi = np.full(3, lo.min()), np.full(3, hi.max())
    rg = hi - lo
    lo, hi = lo + rg * p['Clip'], hi - rg * p['Clip']
    o = c.copy()
    o[..., :3] = (c[..., :3] - lo) / np.maximum(hi - lo, 1e-4)
    return o


def _displace(img, p, px, py, map_img):
    h, w = img.shape[:2]
    sp = max(p['Size'], 1.0)
    src = img if map_img is None else map_img

    def L(qx, qy):
        return luma(tex_uv(src, qx / w, qy / h))
    gx = (L(px + sp, py) - L(px - sp, py)) * 0.5
    gy = (L(px, py + sp) - L(px, py - sp)) * 0.5
    k = p['Strength'] * p['Length']
    ox, oy = gx * k, gy * k
    pr = p['Prism']
    sr = tex(img, px - ox * (1 - pr), py - oy * (1 - pr))
    sg = tex(img, px - ox, py - oy)
    sb = tex(img, px - ox * (1 + pr), py - oy * (1 + pr))
    return np.stack([sr[..., 0], sg[..., 1], sb[..., 2], sg[..., 3]], -1)


def _bolt(px, py, p0, p1, s, jag):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = max(math.hypot(dx, dy), 1e-3)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    rx, ry = px - p0[0], py - p0[1]
    t = (rx * ux + ry * uy) / L
    dp = rx * nx + ry * ny
    tc = np.clip(t, 0.0, 1.0)
    off = jag * L * (fbm1(tc * 6.0, s) - 0.5) * 4.0 * tc * (1.0 - tc)
    return np.hypot((t - tc) * L, dp - off)


def zap_branches(p, w, h, ep):
    """[(P0, P1, seed)] of the branches, as the shader computes them (for tests / overlays)."""
    sd = seed_mix(p['Seed'], ep)
    A = (p['Pointu'] * w, p['Pointv'] * h)
    B = (p['Point2u'] * w, p['Point2v'] * h)
    dx, dy = B[0] - A[0], B[1] - A[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / max(L, 1e-3), dy / max(L, 1e-3)
    nx, ny = -uy, ux
    out = []
    for k in range(6):
        if k >= int(p['Branches'] + 0.5):
            break
        sk = (sd + k * 7 + 1000) & M32
        s0 = 0.15 + 0.6 * float(hsh(k, 1, sk))
        off0 = p['Jag'] * L * (float(fbm1(np.array(s0 * 6.0), sd)) - 0.5) * 4.0 * s0 * (1.0 - s0)
        P0 = (A[0] + ux * s0 * L + nx * off0, A[1] + uy * s0 * L + ny * off0)
        ang = (0.35 + 0.6 * float(hsh(k, 2, sk))) * (-1.0 if float(hsh(k, 3, sk)) < 0.5 else 1.0)
        bx, by = math.cos(ang) * ux - math.sin(ang) * uy, math.sin(ang) * ux + math.cos(ang) * uy
        bl = L * (0.15 + 0.3 * float(hsh(k, 4, sk)))
        out.append((P0, (P0[0] + bx * bl, P0[1] + by * bl), sk))
    return A, B, sd, out


def _zap(img, p, px, py, ep, c):
    h, w = img.shape[:2]
    A, B, sd, br = zap_branches(p, w, h, ep)
    W = max(p['Width'], 0.25)
    v = np.exp(-_bolt(px, py, A, B, sd, p['Jag']) / W)
    for P0, P1, sk in br:
        v = v + 0.6 * np.exp(-_bolt(px, py, P0, P1, sk, p['Jag']) / (W * 0.7))
    fl = 0.6 + 0.4 * float(hsh(5, 9, sd))
    o = c.copy()
    col = np.array([p['Colr'], p['Colg'], p['Colb']])
    o[..., :3] = c[..., :3] + col * (p['Glow'] * fl * p['Strength']) * v[..., None]
    return o


def _arcs(img, p, px, py, ep, c, arcs):
    """arcs = [(x0, y0, x1, y1, power, seed)] as the arcs Script CHOP makes them (ARCS_PY.arc_list).
    Same per-pixel cull as the shader (it only skips pixels whose glow < exp(-14))."""
    sd = seed_mix(p['Seed'], ep)
    W = max(p['Width'], 0.25)
    v = np.zeros(px.shape)
    for x0, y0, x1, y1, pw, sk in (arcs or [])[:32]:
        if pw <= 0:
            continue
        dx, dy = x1 - x0, y1 - y0
        L = max(math.hypot(dx, dy), 1e-3)
        t = np.clip(((px - x0) * dx + (py - y0) * dy) / (L * L), 0.0, 1.0)
        near = np.hypot(px - x0 - dx * t, py - y0 - dy * t) <= W * 14.0 + 0.5 * p['Jag'] * L + 2.0
        b = _bolt(px, py, (x0, y0), (x1, y1), (sd + int(sk) * 7 + 1000) & M32, p['Jag'])
        v = v + np.where(near, pw * np.exp(-b / W), 0.0)
    fl = 0.6 + 0.4 * float(hsh(5, 9, sd))
    o = c.copy()
    col = np.array([p['Colr'], p['Colg'], p['Colb']])
    o[..., :3] = c[..., :3] + col * (p['Glow'] * fl * p['Strength']) * v[..., None]
    return o


def reference(img, pars=None, t=0.0, stats=None, map_img=None, region=None, arcs=None):
    """The module's out1 for picture img ([y, x, 4], row 0 = bottom) -> float64 [y, x, 4] (unquantised, unclamped
    except where the shader clamps). t = absTime.seconds (only floor(t * Rate) matters); stats = (lo rgb, hi rgb,
    mean) read from the live `stats` TOP (else ref_stats approx); map_img = the Map TOP's pixels (displace);
    region = (x0, y0, w, h): only that window of the output (sampling still sees the whole picture; use it live:
    full-res numpy of the tap-heavy types takes 5-20 s)."""
    p = full_pars(pars)
    img = np.asarray(img, dtype=np.float64)
    h, w = img.shape[:2]
    x0, y0, rw, rh = region or (0, 0, w, h)
    c = img[y0:y0 + rh, x0:x0 + rw]
    if p['Amount'] <= 0.0:
        return c.copy()
    px, py = grid(rh, rw)
    px, py = px + x0, py + y0
    ty = p['Type']
    ep = epoch(t, p['Rate'])
    if ty == 0:
        o = _bend(img, p, px, py)
    elif ty == 1:
        o = _suck(img, p, px, py)
    elif ty == 2:
        o = _tri(img, p, px, py)
    elif ty == 3:
        o = _longshadow(img, p, px, py, c)
    elif ty == 4:
        o = _electrify(img, p, px, py, ep, c)
    elif ty == 5:
        o = _autolevel(img, p, stats, c)
    elif ty == 6:
        o = _displace(img, p, px, py, map_img)
    elif ty == 7:
        o = _zap(img, p, px, py, ep, c)
    else:
        o = _arcs(img, p, px, py, ep, c, arcs)
    return c + (o - c) * p['Amount']


def compare(td_out, ref, tol=3.0 / 255.0, rgb_only=True, clip=True):
    """td_out (out1 numpyArray) vs reference. clip: an 8-bit output clamps to 0..1, so the reference is clipped too.
    -> dict(max, mean, within = share of pixels whose max channel error <= tol)."""
    a = np.asarray(td_out, dtype=np.float64)
    b = np.asarray(ref, dtype=np.float64)
    if clip:
        b = np.clip(b, 0.0, 1.0)
    if rgb_only:
        a, b = a[..., :3], b[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
