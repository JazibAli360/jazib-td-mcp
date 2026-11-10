# fx_destroy_crack_logic - pure Python / numpy reference for FX_destroy module 'crack' (builders/fx_destroy_crack.py).
# Mirrors the GLSL: the rack's lowbias32 hash (bit-exact in uint32, T-108), the log-polar Voronoi glass layer (float32,
# so GPU vs numpy differ only at near-tie cell borders), the stuck lines + dead pixels (exact integer maths), and the
# hits state machine. Coordinates are texel coordinates (x right, y up from the bottom row = numpyArray row 0).
# No TD imports: offline tests (test/test_fx_destroy_crack.py) and the live checks (docs/builds/fx_destroy_crack.md).
import math

try:
    import numpy as np
except ImportError:          # pragma: no cover - the live checks need numpy, the hit logic does not
    np = None

M32 = 0xffffffff
PAL7 = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 0), (1, 1, 1)]


# ------------------------------------------------------------------ hash (scalar, exact)
def lb32(x):
    x &= M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def hsh(cx, cy, s):
    """GLSL hsh(ivec2(cx, cy), s) as a Python float (the float32 value)."""
    u = lb32(((cx & M32) * 1597334677) & M32 ^ lb32((cy & M32) ^ ((s * 2654435761) & M32)))
    return float(np.float32(u) * np.float32(1.0 / 4294967296.0)) if np is not None else u / 4294967296.0


# ------------------------------------------------------------------ hash (numpy, exact)
def _u(a):
    return (np.asarray(a, dtype=np.int64) & M32).astype(np.uint32)


def lb32_np(x):
    x = x.astype(np.uint32)
    with np.errstate(over='ignore'):
        x = x ^ (x >> np.uint32(16))
        x = x * np.uint32(0x7feb352d)
        x = x ^ (x >> np.uint32(15))
        x = x * np.uint32(0x846ca68b)
        x = x ^ (x >> np.uint32(16))
    return x


def hsh_np(cx, cy, s):
    s = np.uint32(s & M32)
    with np.errstate(over='ignore'):
        inner = lb32_np(_u(cy) ^ (s * np.uint32(2654435761)))
        v = lb32_np((_u(cx) * np.uint32(1597334677)) ^ inner)
    return v.astype(np.float32) * np.float32(1.0 / 4294967296.0)


def vnoise_np(x, y, s):
    ix, iy = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - np.floor(x)).astype(np.float32), (y - np.floor(y)).astype(np.float32)
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = hsh_np(ix, iy, s), hsh_np(ix + 1, iy, s)
    c, d = hsh_np(ix, iy + 1, s), hsh_np(ix + 1, iy + 1, s)
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy


# ------------------------------------------------------------------ params
def defaults(pages):
    """Par name -> default from a module PAGES list (RGB pars expand to name + r/g/b)."""
    d = {}
    for _page, pars in pages:
        for name, style, default, _o in pars:
            if style == 'RGB':
                for k, v in zip('rgb', default):
                    d[name + k] = v
            elif style not in ('Pulse', 'TOP', 'COMP', 'CHOP'):
                d[name] = default
    return d


MENUS = {'Source': ['point', 'hits'], 'Back': ['black', 'alpha'], 'View': ['look', 'map'],
         'Bardir': ['v', 'h', 'both'], 'Linedir': ['v', 'h', 'both']}


def menu_index(P, name):
    v = P[name]
    return v if isinstance(v, int) else MENUS[name].index(v)


# ------------------------------------------------------------------ hits state machine (mirror of the HITS shader)
def hits_init(hit, now):
    return {'hits': [[0.0, 0.0, -1.0, 0.0] for _ in range(8)], 'hd': [hit, 0.0, 7.0, now]}


def hits_step(st, now, hit, reset, maxhits, point, scatter, seed, W, H):
    """One cook of the hits TOP. st = None (fresh texture) or the previous state. Returns the new state."""
    if st is not None and not st['hd'][0] <= now + 0.05:       # seen hit from another clock: void, no replay (T-160)
        st = {'hits': st['hits'], 'hd': [hit] + list(st['hd'][1:])}
    if st is None or st['hd'][2] != 7.0 or reset >= st['hd'][3]:
        seen = reset if (st is not None and st['hd'][2] == 7.0 and hit > reset) else hit
        return hits_init(seen, now)                            # a hit after the Reset stays pending
    st = {'hits': [list(h) for h in st['hits']], 'hd': list(st['hd'])}
    hd = st['hd']
    if hit > hd[0] + 1e-4 and hit <= now + 0.05:
        n = int(hd[1] + 0.5)
        k = n % max(1, min(8, int(maxhits + 0.5)))
        rx, ry = hsh(n, 1, seed + 70) * W, hsh(n, 2, seed + 70) * H
        sc = min(1.0, max(0.0, scatter))
        st['hits'][k] = [point[0] + (rx - point[0]) * sc, point[1] + (ry - point[1]) * sc, hit, float(n + 1)]
        hd[0], hd[1] = hit, float(n + 1)
    hd[3] = now
    return st


def ease3(x):
    x = min(1.0, max(0.0, x))
    return 1.0 - (1.0 - x) ** 3


def active_hits(st, now, P, H):
    """The fx shader's sH / sH2 for Source hits: [(x, y, reach px, weight, ink px, growth, number)], off ones skipped."""
    out = []
    for t in st['hits'][:max(1, min(8, int(P['Maxhits'] + 0.5)))]:
        age = now - t[2]
        if t[2] < 0 or age < 0:
            continue
        f = min(1.0, max(0.0, 1.0 - age / P['Fade'])) if P['Fade'] > 0 else 1.0
        if f <= 0:
            continue
        g = ease3(age * P['Speed'])
        out.append((t[0], t[1], P['Radius'] * H * g, f, P['Ink'] * H * math.sqrt(min(1.0, max(0.0, age * P['Speed'] * 0.35))),
                    g, t[3]))
    return out


# ------------------------------------------------------------------ glass (numpy float32 mirror of glassLayer)
def _wrap(x, n):
    return ((x % n) + n) % n


def _cell_seed(kx, ky, NR, s, jit):
    kw = _wrap(kx, NR)
    j = np.float32(jit)
    return (kx.astype(np.float32) + np.float32(0.5) + (hsh_np(kw, ky, s) - np.float32(0.5)) * j,
            ky.astype(np.float32) + np.float32(0.5) + (hsh_np(kw, ky, s + 1) - np.float32(0.5)) * j)


def glass_layer(dx, dy, R, NRf, b, w, s, jit, ringp):
    """Returns (k line 0..1, bid int64 cell id, rc seed radius px) per pixel; dx, dy float32 arrays (px)."""
    f32 = np.float32
    NR = max(3, int(NRf + 0.5))
    a = f32(NR) / f32(6.2831853)
    b = f32(b)
    rr = np.maximum(np.sqrt(dx * dx + dy * dy), f32(1.0)).astype(f32)
    th = np.arctan2(dy, dx).astype(f32)
    qx = ((th + f32(3.14159265)) * a).astype(f32)
    qy = (np.log(rr) * b).astype(f32)
    cx, cy = np.floor(qx).astype(np.int64), np.floor(qy).astype(np.int64)
    d1 = np.full(dx.shape, 1e20, f32)
    bx, by = cx.copy(), cy.copy()
    s1x, s1y = np.zeros_like(qx), np.zeros_like(qy)
    for j in (-1, 0, 1):
        for i in (-1, 0, 1):
            kx, ky = cx + i, cy + j
            sx, sy = _cell_seed(kx, ky, NR, s, jit)
            dd = (sx - qx) ** 2 + (sy - qy) ** 2
            m = dd < d1
            d1 = np.where(m, dd, d1)
            bx, by = np.where(m, kx, bx), np.where(m, ky, by)
            s1x, s1y = np.where(m, sx, s1x), np.where(m, sy, s1y)
    bid = by * NR + _wrap(bx, NR)
    rc = np.exp(s1y / b).astype(f32)
    taper = f32(1.0) - f32(0.6) * np.clip(rr / f32(max(R, 1.0)), 0, 1)
    kmax = np.zeros_like(qx)
    for j in (-1, 0, 1):
        for i in (-1, 0, 1):
            if i == 0 and j == 0:
                continue
            kx, ky = bx + i, by + j
            sx, sy = _cell_seed(kx, ky, NR, s, jit)
            nx, ny = sx - s1x, sy - s1y
            L = np.sqrt(nx * nx + ny * ny)
            okL = L >= 1e-5
            L = np.where(okL, L, f32(1.0))
            nx, ny = nx / L, ny / L
            e = (f32(0.5) * (s1x + sx) - qx) * nx + (f32(0.5) * (s1y + sy) - qy) * ny
            g = np.sqrt(a * a * nx * nx + b * b * ny * ny)
            epx = e * rr / np.maximum(g, f32(1e-6))
            nid = ky * NR + _wrap(kx, NR)
            lo, hi = np.minimum(bid, nid), np.maximum(bid, nid)
            ring = np.abs(ny) * b > np.abs(nx) * a
            skip = ring & (hsh_np(lo, hi, s + 6) >= f32(ringp))
            reach = f32(R) * (f32(0.55) + f32(0.6) * hsh_np(lo, hi, s + 5))
            t = np.clip((rr - reach * f32(0.8)) / (reach * f32(0.2)), 0, 1)
            wk = f32(w) * taper * (f32(1.0) - t * t * (f32(3.0) - f32(2.0) * t))
            k1 = np.clip(f32(1.0) - epx / np.where(wk > 0, wk, f32(1.0)), 0, 1)
            k1 = np.where(okL & ~skip & (wk > 0), k1, f32(0.0))
            kmax = np.maximum(kmax, k1)
    return kmax, bid, rc


def crack_map(W, H, impacts, P):
    """View = map reference: (line, chip, cmap) float32 (H, W) for impacts [(x, y, reach px, weight, ink, g, num)].
    Wobble is applied as in the shader; set Wobble 0 for the tightest comparison."""
    f32 = np.float32
    ys, xs = np.mgrid[0:H, 0:W]
    pcx, pcy = xs.astype(f32) + f32(0.5), ys.astype(f32) + f32(0.5)
    line = np.zeros((H, W), f32)
    chip = np.zeros((H, W), f32)
    cmap = np.zeros((H, W), f32)
    sd = int(P['Seed'])
    for (x, y, R, wgt, _ink, _g, num) in impacts:
        if R <= 0 or wgt <= 0:
            continue
        hs = (sd + int(num) * 977) & M32
        dx, dy = pcx - f32(x), pcy - f32(y)
        r = np.sqrt(dx * dx + dy * dy)
        inside = r < f32(R) * f32(1.15) + f32(P['Wobble']) + f32(2.0)
        if P['Wobble'] > 0:
            dx = dx + f32(P['Wobble']) * (vnoise_np(pcx / f32(40.0), pcy / f32(40.0), hs + 60) * 2 - 1)
            dy = dy + f32(P['Wobble']) * (vnoise_np(pcx / f32(40.0) + f32(19.3), pcy / f32(40.0) + f32(19.3), hs + 61) * 2 - 1)
        k1, bid, rc = glass_layer(dx, dy, R, P['Radials'], P['Rings'], P['Crackwidth'], hs, P['Jitter'], P['Ringcracks'])
        lin = k1 * f32(wgt)
        piece = rc < f32(R * 0.9)
        cm = np.where(piece, hsh_np(bid, 7, hs), f32(0.0))
        pch = np.clip(f32(1.0) - rc / f32(R * 0.6), 0, 1) * f32(P['Chips'])
        ch = np.where(piece & (hsh_np(bid, 9, hs) < pch), f32(wgt), f32(0.0))
        if P['Detail'] > 0:
            k2, _b2, _r2 = glass_layer(dx, dy, R * 0.6, P['Radials'] * 2.3, P['Rings'] * 2.0, P['Crackwidth'] * 0.5,
                                       hs + 101, P['Jitter'], P['Ringcracks'])
            lin = np.maximum(lin, k2 * f32(P['Detail']) * f32(wgt))
        if P['Core'] > 0:
            C = f32(P['Core'])
            t = np.clip((r - C * f32(0.4)) / (C * f32(0.6)), 0, 1)
            kc = (f32(1.0) - t * t * (f32(3.0) - f32(2.0) * t)) * f32(wgt)
            gx, gy = np.floor(pcx / f32(2.0)).astype(np.int64), np.floor(pcy / f32(2.0)).astype(np.int64)
            core = np.where(r < C, kc * (f32(0.4) + f32(0.6) * hsh_np(gx, gy, hs + 30)), f32(0.0))
            lin = np.maximum(lin, core)
        line = np.where(inside, np.maximum(line, lin), line)
        chip = np.where(inside, np.maximum(chip, ch), chip)
        cmap = np.where(inside, np.maximum(cmap, cm), cmap)
    return line, chip, cmap


# ------------------------------------------------------------------ stuck lines + dead pixels (exact)
def stuck_lines(W, H, P, now=0.0):
    """[(axis 0 = vertical, first px, width, kind 0 black / 1..7 colour / 8 smear, smear pos 0..1)] as the shader."""
    out = []
    sd = int(P['Seed'])
    dirn = menu_index(P, 'Linedir')
    fl = P.get('Flicker', 0.0)
    for i in range(max(0, min(64, int(P['Lines'] + 0.5)))):
        ax = (i & 1) if dirn == 2 else dirn
        if fl > 0 and not hsh(i + 100, int(math.floor(now * fl)), sd + 9) > 0.3:
            continue
        r1, r2, r3 = hsh(i, 11, sd), hsh(i, 12, sd), hsh(i, 13, sd)
        pos = int(math.floor(np.float32(r1) * np.float32(W if ax == 0 else H)))
        kf = np.float32(math.floor(np.float32(r2) * np.float32(9.0))) + np.float32(r3) * np.float32(0.5)
        sp = float((kf - np.float32(math.floor(kf))) * np.float32(2.0))
        out.append((ax, pos, max(1, int(math.floor(P['Linewidth'] + 0.5))), int(math.floor(kf)), sp))
    return out


def dead_mask(W, H, P):
    """(dead bool (H, W), colour float32 (H, W, 3)) for Dead / Cluster / Clusterfill / Deadlit."""
    sd = int(P['Seed'])
    ys, xs = np.mgrid[0:H, 0:W]
    cl = max(1, int(P['Cluster'] + 0.5))
    cx, cy = xs // cl, ys // cl
    dead = (hsh_np(cx, cy, sd + 40) < np.float32(P['Dead'])) & (hsh_np(xs, ys, sd + 41) < np.float32(P['Clusterfill']))
    lit = hsh_np(cx, cy, sd + 42) < np.float32(P['Deadlit'])
    t = np.floor(hsh_np(cx, cy, sd + 43) * np.float32(4.0)).astype(np.int64)
    pal = np.array([PAL7[0], PAL7[1], PAL7[2], (1, 1, 1)], np.float32)
    col = np.where(lit[..., None], pal[t], np.float32(0.0))
    return dead & (P['Dead'] > 0), col


def lcd_apply(img, P, now=0.0):
    """Expected `fx` output for a picture img (H, W, 4 float32, texel rows) with only stuck lines + dead pixels on
    (no glass: Radius 0; Ink 0; Bars 0), Amount 1. Bit-exact apart from the TOP's own 8-bit quantisation."""
    H, W = img.shape[:2]
    o = img.copy()
    ys, xs = np.mgrid[0:H, 0:W]
    for ax, pos, w, kind, sp in stuck_lines(W, H, P, now):
        cc = xs if ax == 0 else ys
        m = (cc >= pos) & (cc < pos + w)
        if kind == 0:
            o[m, :3] = 0.0
        elif kind < 8:
            o[m, :3] = PAL7[kind - 1]
        elif ax == 0:
            o[m, :3] = img[min(H - 1, int(np.float32(sp) * np.float32(H))), xs[m], :3]
        else:
            o[m, :3] = img[ys[m], min(W - 1, int(np.float32(sp) * np.float32(W))), :3]
    dead, col = dead_mask(W, H, P)
    o[dead, :3] = col[dead]
    return o


def expected_numbers(W=1080, H=1920, pages=None, presets=None):
    """The numbers the live checks quote (docs/builds/fx_destroy_crack.md)."""
    P0 = defaults(pages)
    res = {}
    for slot, name, vals in presets:
        P = dict(P0)
        P.update(vals)
        if name == 'dead LED wall':
            P['Flicker'] = 0.0
            dead, _c = dead_mask(W, H, P)
            ln = stuck_lines(W, H, P)
            ys, xs = np.mgrid[0:H, 0:W]
            lm = np.zeros((H, W), bool)
            for ax, pos, w, _k, _s in ln:
                cc = xs if ax == 0 else ys
                lm |= (cc >= pos) & (cc < pos + w)
            res['dead_px'] = int(dead.sum())
            res['line_px'] = int(lm.sum())
            res['lcd_px'] = int((dead | lm).sum())
            res['lines'] = [(a, p, k) for a, p, _w, k, _s in ln]
    return res


# ------------------------------------------------------------------ CLI for the live checks (runs outside TD)
def _module_ns():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    ns = {}
    exec(open(os.path.join(here, 'fx_destroy.py')).read(), ns)
    exec(open(os.path.join(here, 'fx_destroy_crack.py')).read(), ns)
    return ns


def _preset(ns, slot):
    P = defaults(ns['PAGES'])
    if slot:
        P.update(next(v for s, _n, v in ns['PRESETS'] if s == slot))
    return P


def main(argv=None):
    """expect | map <out.npy> [preset] [x y] | lcd <in.npy> <out.npy> [preset]  (npy = numpyArray of a TOP)."""
    import sys
    a = list(sys.argv[1:] if argv is None else argv)
    ns = _module_ns()
    if not a or a[0] == 'expect':
        print(expected_numbers(pages=ns['PAGES'], presets=ns['PRESETS']))
        return 0
    if a[0] == 'map':
        o = np.load(a[1]).astype(np.float32)
        H, W = o.shape[:2]
        P = _preset(ns, int(a[2]) if len(a) > 2 else 0)
        x, y = (float(a[3]), float(a[4])) if len(a) > 4 else (W * 0.5, H * 0.5)
        line, chip, cmap = crack_map(W, H, [(x, y, P['Radius'] * H, 1.0, 0.0, 1.0, 0.0)], P)
        for k, ref, got in (('line', line, o[..., 0]), ('chip', chip, o[..., 1]), ('cell', cmap, o[..., 2])):
            d = np.abs(ref - got)
            print('%s: ref>0 %.4f got>0 %.4f  |d|>0.1 %.4f%%  max %.3f' % (
                k, (ref > 0).mean(), (got > 0.5 / 255).mean(), 100 * (d > 0.1).mean(), d.max()))
        return 0
    if a[0] == 'lcd':
        i, o = np.load(a[1]).astype(np.float32), np.load(a[2]).astype(np.float32)
        P = _preset(ns, int(a[3]) if len(a) > 3 else 4)
        P['Flicker'] = 0.0
        ref = lcd_apply(i, P)
        d = np.abs(ref - o).max(axis=2)
        print('lcd: max |d| %.5f, px |d| > 1/255: %d, changed px got %d ref %d' % (
            d.max(), int((d > 1.01 / 255).sum()), int((np.abs(o - i).max(axis=2) > 0).sum()),
            int((np.abs(ref - i).max(axis=2) > 0).sum())))
        return 0
    print(main.__doc__)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
