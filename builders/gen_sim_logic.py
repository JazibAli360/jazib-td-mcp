"""gen_sim_logic - pure maths for GEN_sim (builders/gen_sim.py + gen_sim_<module>.py): rule parsing, the expression
strings the modules put on TD pars, and float64/uint32 numpy references of every compute pass
(builders/glsl/gen_sim_*.glsl). Arrays are [y, x] with y = 0 the BOTTOM row (TD texel space; numpyArray row 0 =
bottom, T-58). numpy is imported lazily so TD never loads this file for a build. ASCII only.

Live parity: in TD dump the arrays + uniforms with `dump_code(...)` (td_exec, `# allow-readback`), then outside TD
    python3 -I builders/gen_sim_logic.py check <ca|vor|dla|blobs|lic> <dir>
prints the numbers docs/builds/gen_sim.md "LIVE CHECKS" asks for."""
import json
import math
import os
import sys

M32 = 0xFFFFFFFF


def _np():
    import numpy
    return numpy


# ------------------------------------------------------------------ hash / noise / colour (== gen_sim_common.glsl)
def hash_u32(x):
    """lowbias32 (Wellons), uint32 wraparound == gs_hashu()."""
    np = _np()
    x = np.asarray(x).astype(np.uint64) & M32
    x ^= x >> 16
    x = (x * 0x7feb352d) & M32
    x ^= x >> 15
    x = (x * 0x846ca68b) & M32
    x ^= x >> 16
    return x


def hash3(i, j, s):
    """float in [0, 1) from three ints == gs_hash3() (exact in float32: 24 bits)."""
    np = _np()
    i = np.asarray(i).astype(np.int64) & M32
    j = np.asarray(j).astype(np.int64) & M32
    s = np.asarray(s).astype(np.int64) & M32
    h = hash_u32(i + hash_u32(j + hash_u32(s)))
    return (h >> 8).astype(np.float64) * (1.0 / 16777216.0)


def vnoise(x, y, s):
    """value noise in [0, 1), smoothstep blend == gs_vnoise()."""
    np = _np()
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    ix, iy = ix.astype(np.int64), iy.astype(np.int64)
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = hash3(ix, iy, s), hash3(ix + 1, iy, s)
    c, d = hash3(ix, iy + 1, s), hash3(ix + 1, iy + 1, s)
    return (a + (b - a) * ux) * (1 - uy) + (c + (d - c) * ux) * uy


def luma(rgb):
    np = _np()
    rgb = np.asarray(rgb, dtype=np.float64)
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


PALETTES = ['ab', 'fire', 'ice', 'neon', 'rainbow', 'mono', 'input']
BLENDS = ['replace', 'over', 'add', 'screen', 'multiply', 'lighten', 'difference', 'alpha']


def palette(t, mode, ca=(1, 1, 1), cb=(1, 1, 1), shift=0.0):
    """== gs_pal(); t array -> (..., 3)."""
    np = _np()
    u = np.asarray(t, dtype=np.float64) + shift
    c = np.clip(u, 0, 1)[..., None]
    if mode == 1:
        return np.clip(np.concatenate([c * 3, c * 3 - 1, c * 3 - 2], -1), 0, 1)
    if mode == 2:
        lo, hi = np.array([0.0, 0.05, 0.2]), np.array([0.55, 0.9, 1.0])
        return lo + (hi - lo) * c + c ** 3 * 0.45
    if mode in (3, 4):
        d = np.array([0.3, 0.2, 0.2]) if mode == 3 else np.array([0.0, 0.33, 0.67])
        return 0.5 + 0.5 * np.cos(2 * math.pi * (u[..., None] + d))
    if mode == 5:
        return np.ones(u.shape + (3,))
    ca, cb = np.asarray(ca, dtype=np.float64), np.asarray(cb, dtype=np.float64)
    return ca + (cb - ca) * c


def blend(base, col, a, mode, amount):
    """== gs_blend(); base (..., 4), col (..., 3) premultiplied, a (...)."""
    np = _np()
    base = np.asarray(base, dtype=np.float64)
    a = np.asarray(a, dtype=np.float64)[..., None]
    b, ba = base[..., :3], base[..., 3:4]
    one = np.ones_like(a)
    if mode == 0:
        o = np.concatenate([col, one], -1)
    elif mode == 1:
        o = np.concatenate([col + b * (1 - a), a + ba * (1 - a)], -1)
    elif mode == 2:
        o = np.concatenate([b + col, ba], -1)
    elif mode == 3:
        o = np.concatenate([1 - (1 - b) * (1 - col), ba], -1)
    elif mode == 4:
        o = np.concatenate([b * col, ba], -1)
    elif mode == 5:
        o = np.concatenate([np.maximum(b, col), ba], -1)
    elif mode == 6:
        o = np.concatenate([np.abs(b - col), ba], -1)
    else:
        o = np.concatenate([col, a], -1)
    return base + (o - base) * amount


# ------------------------------------------------------------------ ca: rules + expressions
FAMILIES = ['life', 'wireworld', 'cyclic', 'ltl', 'lenia']
CA_SEEDS = ['noise', 'blob', 'input', 'wires', 'empty']
HMAX = 16                                     # shared-memory halo of gen_sim_ca_step.glsl (max neighbourhood radius)
_RULE_SRC = "{rule}.upper().replace(' ', '').split('/')"
RULE_LAMBDAS = {
    'b': "lambda t: sum(1 << d for d in set(int(ch) for p in t if p[:1] == 'B' for ch in p[1:] "
         "if ch.isdigit() and int(ch) <= 8))",
    's': "lambda t: sum(1 << d for d in set(int(ch) for p in t if p[:1] == 'S' for ch in p[1:] "
         "if ch.isdigit() and int(ch) <= 8))",
    'c': "lambda t: max([2] + [int(p[1:]) for p in t if p[:1] == 'C' and p[1:].isdigit()])",
}


def rule_expr(key, rule="parent().par.Rule.eval()"):
    """TD par expression for the B mask / S mask / state count C of a Golly-style rule string ('B3/S23', 'B2/S/C3')."""
    return "(%s)(%s)" % (RULE_LAMBDAS[key], _RULE_SRC.format(rule=rule))


def parse_rule(rule):
    """(bmask, smask, C) exactly as the TD expressions compute them (same lambdas)."""
    t = rule.upper().replace(' ', '').split('/')
    return tuple(eval(RULE_LAMBDAS[k], {'__builtins__': __builtins__})(t) for k in 'bsc')


RULESETS = [('life', 'Life B3/S23', 'B3/S23'), ('highlife', 'HighLife B36/S23', 'B36/S23'),
            ('seeds', 'Seeds B2/S', 'B2/S'), ('daynight', 'Day & Night', 'B3678/S34678'),
            ('coral', 'Coral B3/S45678', 'B3/S45678'), ('maze', 'Maze B3/S12345', 'B3/S12345'),
            ('brian', "Brian's Brain B2/S/C3", 'B2/S/C3'), ('starwars', 'Star Wars B2/S345/C4', 'B2/S345/C4'),
            ('custom', 'Custom (Rule)', None)]       # the 'ca' Ruleset menu (life family: Generations when C > 2)


def ruleset_rule(ruleset, custom):
    """Rule string the 'ca' module uses: the named Ruleset, or the Rule par when Ruleset = custom."""
    for name, _label, rule in RULESETS:
        if name == ruleset and rule:
            return rule
    return custom


def lenia_kernel(R):
    """(2R+1)^2 weights, row dy = -R..R, col dx = -R..R: exp(4 - 1 / (r (1 - r))), r = |d| / R in (0, 1)."""
    np = _np()
    d = np.arange(-R, R + 1, dtype=np.float64)
    r = np.hypot(d[None, :], d[:, None]) / R
    k = np.zeros_like(r)
    m = (r > 0) & (r < 1)
    k[m] = np.exp(4.0 - 1.0 / (r[m] * (1.0 - r[m])))
    return k


LENIA_NORM_LAMBDA = ("lambda R: sum(math.exp(4.0 - 1.0 / (r * (1.0 - r))) for r in "
                     "(math.hypot(x, y) / R for x in range(-R, R + 1) for y in range(-R, R + 1)) if 0.0 < r < 1.0)")


def lenia_norm_expr(rpar="parent().par.Leniar.eval()"):
    return "(%s)(max(1, min(%d, int(%s + 0.5))))" % (LENIA_NORM_LAMBDA, HMAX, rpar)


def lenia_norm(R):
    return eval(LENIA_NORM_LAMBDA, {'math': math})(max(1, min(HMAX, int(R + 0.5))))


def ca_radius(fam, P):
    """Neighbourhood radius the step shader uses (== uRule.w after its clamp)."""
    if fam in (0, 1):
        return 1
    v = {2: P.get('Cycrange', 1), 3: P.get('Ltlr', 5), 4: P.get('Leniar', 13)}[fam]
    return max(1, min(HMAX, int(v + 0.5)))


def step_seed(frame, tdpass, seed):
    """per-step random stream id == int((uint(frame) * 8u + uint(pass)) * 7919u + uint(seed)) (int32 bits)."""
    v = ((int(frame) * 8 + int(tdpass)) * 7919 + (int(seed) & M32)) & M32
    return v - (1 << 32) if v >= (1 << 31) else v


def _shift(a, dx, dy, wrap):
    """out[y, x] = a[y + dy, x + dx]; outside = 0 unless wrap."""
    np = _np()
    if wrap:
        return np.roll(a, (-dy, -dx), axis=(0, 1))
    H, W = a.shape
    o = np.zeros_like(a)
    ys, yd = (slice(dy, H), slice(0, H - dy)) if dy >= 0 else (slice(0, H + dy), slice(-dy, H))
    xs, xd = (slice(dx, W), slice(0, W - dx)) if dx >= 0 else (slice(0, W + dx), slice(-dx, W))
    o[yd, xd] = a[ys, xs]
    return o


def _in_luma_cells(inp, W, H):
    """slot input luma at each cell centre (texelFetch of the input pixel under it) -> (H, W)."""
    np = _np()
    ih, iw = inp.shape[:2]
    qx = np.clip(np.floor((np.arange(W) + 0.5) * iw / W).astype(int), 0, iw - 1)
    qy = np.clip(np.floor((np.arange(H) + 0.5) * ih / H).astype(int), 0, ih - 1)
    return luma(inp[qy][:, qx][..., :3])


def ca_init(W, H, fam, P, inp=None):
    """Seed state r (H, W) == initCell() in gen_sim_ca_step.glsl. P: Seedmode index, Density, Threshold, Seed,
    States, Wirespacing, Sparks (+ the radius pars)."""
    np = _np()
    mode, dens, sd = int(P.get('Seedmode', 0)), float(P.get('Density', 0.35)), int(P.get('Seed', 1))
    thr = float(P.get('Threshold', 0.5))
    N = max(float(P.get('States', 12)), 2.0)
    x, y = np.meshgrid(np.arange(W), np.arange(H))
    h = hash3(x, y, sd)
    if mode == 4:
        return np.zeros((H, W))
    if mode == 2:
        lum = _in_luma_cells(inp, W, H)
        if fam == 4:
            return lum
        if fam == 2:
            return np.minimum(np.floor(lum * N), N - 1)
        if fam == 1:
            return np.where(lum > thr, np.where(hash3(x, y, sd + 7) < P.get('Sparks', 0.02), 1.0, 3.0), 0.0)
        return (lum > thr).astype(float)
    if mode == 3 or (fam == 1 and mode == 0):
        sp = max(int(P.get('Wirespacing', 12) + 0.5), 2)
        wire = ((x % sp == 0) | (y % sp == 0)) & (hash3(x // sp, y // sp, sd + 3) > dens * 0.5)
        if fam != 1:
            return wire.astype(float)
        return np.where(wire, np.where(hash3(x, y, sd + 7) < P.get('Sparks', 0.02), 1.0, 3.0), 0.0)
    keep = np.ones((H, W), bool)
    if mode == 1:
        keep = np.hypot(x + 0.5 - 0.5 * W, y + 0.5 - 0.5 * H) <= 0.2 * min(W, H)
    if fam == 2:
        v = np.minimum(np.floor(h * N), N - 1)
    elif fam == 4:
        R = ca_radius(4, P)
        v = np.where(vnoise(x / (2.0 * R), y / (2.0 * R), sd + 1) < dens, h, 0.0)
    elif fam == 1:
        v = np.where(h < dens, np.where(hash3(x, y, sd + 7) < P.get('Sparks', 0.02), 1.0, 3.0), 0.0)
    else:
        v = (h < dens).astype(float)
    return np.where(keep, v, 0.0)


def ca_step(st, fam, P, frame=0, tdpass=0, inp=None):
    """One step == gen_sim_ca_step.glsl main() (not the init / copy branches). st (H, W, 4): r state, g glow, b age,
    a epoch. P: Rule (string), States, Cycthresh, Cycrange, Ltlr, Ltlb1/2, Ltls1/2, Leniar/mu/sigma/dt, Wrap, Decay,
    Mutate, Inject, Threshold, Seed."""
    np = _np()
    s = st[..., 0].astype(np.float64)
    H, W = s.shape
    wrap = bool(P.get('Wrap', 1))
    si = np.floor(s + 0.5).astype(int)
    R = ca_radius(fam, P)
    if fam in (0, 1):
        n = sum((np.floor(_shift(s, dx, dy, wrap) + 0.5).astype(int) == 1).astype(int)
                for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)
        if fam == 0:
            bm, sm, C = parse_rule(P.get('Rule', 'B3/S23'))
            C = max(C, 2)
            ns = np.where(si == 0, (bm >> n) & 1,
                          np.where(si == 1, np.where((sm >> n) & 1 == 1, 1, 2 if C > 2 else 0),
                                   np.where(si + 1 >= C, 0, si + 1))).astype(float)
        else:
            ns = np.select([si == 1, si == 2, si == 3], [2.0, 3.0, np.where((n == 1) | (n == 2), 1.0, 3.0)], s)
    elif fam in (2, 3):
        N = max(int(P.get('States', 12) + 0.5), 2)
        want = (si + 1) % N if fam == 2 else np.ones_like(si)
        n = sum((np.floor(_shift(s, dx, dy, wrap) + 0.5).astype(int) == want).astype(int)
                for dy in range(-R, R + 1) for dx in range(-R, R + 1) if dx or dy)
        if fam == 2:
            ns = np.where(n >= P.get('Cycthresh', 3), want, s).astype(float)
        else:
            b1, b2, s1, s2 = (P.get(k, d) for k, d in (('Ltlb1', 34), ('Ltlb2', 45), ('Ltls1', 34), ('Ltls2', 58)))
            ns = np.where(si == 0, (n >= b1) & (n <= b2), (n >= s1) & (n <= s2)).astype(float)
    else:
        K = lenia_kernel(R)
        U = np.zeros_like(s)
        for iy, dy in enumerate(range(-R, R + 1)):
            for ix, dx in enumerate(range(-R, R + 1)):
                if K[iy, ix] != 0:
                    U += K[iy, ix] * _shift(s, dx, dy, wrap)
        U /= max(lenia_norm(R), 1e-9)
        d = (U - P.get('Leniamu', 0.15)) / max(P.get('Leniasigma', 0.015), 1e-6)
        ns = np.clip(s + P.get('Leniadt', 0.1) * (2 * np.exp(-0.5 * d * d) - 1), 0, 1)
    x, y = np.meshgrid(np.arange(W), np.arange(H))
    rs = step_seed(frame, tdpass, P.get('Seed', 1))
    mut = float(P.get('Mutate', 0.0))
    if mut > 0:
        hit = hash3(x, y, rs) < mut
        h2 = hash3(x, y, rs + 11)
        if fam == 4:
            ns = np.where(hit, np.maximum(ns, h2), ns)
        elif fam == 2:
            N = max(float(P.get('States', 12)), 2.0)
            ns = np.where(hit, np.minimum(np.floor(h2 * N), N - 1), ns)
        elif fam == 1:
            ns = np.where(hit & (ns == 3), 1.0, ns)
        else:
            ns = np.where(hit, 1.0, ns)
    if P.get('Inject') and inp is not None:
        li = _in_luma_cells(inp, W, H)
        on = li > P.get('Threshold', 0.5)
        if fam == 4:
            ns = np.where(on, np.maximum(ns, li), ns)
        elif fam == 1:
            ns = np.where(on & (ns == 0), 3.0, ns)
        elif fam != 2:
            ns = np.where(on, 1.0, ns)
    if fam == 2:
        live = (ns != s).astype(float)
    elif fam == 4:
        live = ns
    else:
        live = (ns == 1).astype(float)
    glow = np.maximum(live, st[..., 1] * P.get('Decay', 0.85))
    age = np.where(live > 0.5, st[..., 2] + 1, 0.0)
    return np.stack([ns, glow, age, st[..., 3]], -1)


def ca_value(st, fam, C, colormode=0, agescale=30.0):
    """(t, v) per cell == cellTV() in gen_sim_ca_look.glsl."""
    np = _np()
    s = st[..., 0]
    si = np.floor(s + 0.5).astype(int)
    C = max(float(C), 2.0)
    if fam == 0:
        sv = np.where(si == 1, 1.0, np.where(si >= 2, 1 - (si - 1) / (C - 1), 0.0))
    elif fam == 1:
        sv = np.select([si == 1, si == 2, si == 3], [1.0, 0.6, 0.25], 0.0)
    elif fam == 2:
        sv = s / (C - 1)
    else:
        sv = np.clip(s, 0, 1)
    if colormode == 1:
        return st[..., 1], st[..., 1]
    if colormode == 2:
        return 1 - np.exp(-st[..., 2] / max(agescale, 1e-3)), np.maximum(sv, st[..., 1] * 0.5)
    return sv, sv


# ------------------------------------------------------------------ voronoi (JFA)
VOR_MODES = ['cells', 'stained', 'edges', 'distance', 'delaunay', 'worleyf1', 'worleyf2', 'worleyedge', 'worleycells']
VOR_SOURCES = ['random', 'grid', 'input']


def jfa_passes(W, H):
    """Pm = number of halving steps: ceil(log2(max(W, H)))."""
    return max(1, int(math.ceil(math.log2(max(W, H, 2)))))


def seed_positions(n, W, H, t=0.0, mode=0, seed=1, wander=0.0, jitter=0.6, bias=1.0, inp=None):
    """(n, 2) seed px == seedPos() in gen_sim_vor_seed.glsl."""
    np = _np()
    k = np.arange(n)
    sz = np.array([W, H], dtype=np.float64)
    cell = math.sqrt(W * H / max(n, 1))
    if mode == 1:
        cols = max(1, int(math.floor(math.sqrt(n * W / H) + 0.5)))
        rows = (n + cols - 1) // cols
        i, j = k % cols, k // cols
        cw = np.array([W / cols, H / rows])
        b = np.stack([(i + 0.5 + 0.5 * (j & 1)) * cw[0], (j + 0.5) * cw[1]], -1) \
            + (np.stack([hash3(k, 1, seed), hash3(k, 2, seed)], -1) - 0.5) * jitter * cw
    elif mode == 2:
        ih, iw = inp.shape[:2]
        lum = luma(inp[..., :3])
        b = np.zeros((n, 2))
        done = np.zeros(n, bool)
        for tr in range(8):
            cand = np.stack([hash3(k, 2 * tr + 1, seed), hash3(k, 2 * tr + 2, seed)], -1) * sz
            b = np.where(done[:, None], b, cand)
            qx = np.clip((cand[:, 0] * iw / W).astype(int), 0, iw - 1)
            qy = np.clip((cand[:, 1] * ih / H).astype(int), 0, ih - 1)
            acc = hash3(k, 40 + tr, seed) < np.maximum(lum[qy, qx], 0) ** bias
            done |= acc
    else:
        b = np.stack([hash3(k, 1, seed), hash3(k, 2, seed)], -1) * sz
    w1, w2 = 0.3 + hash3(k, 5, seed), 0.3 + hash3(k, 6, seed)
    p1, p2 = 2 * math.pi * hash3(k, 7, seed), 2 * math.pi * hash3(k, 8, seed)
    b = b + wander * cell * np.stack([np.sin(t * w1 + p1), np.cos(t * w2 + p2)], -1)
    return sz - np.abs(np.mod(b, 2 * sz) - sz)


def scatter(seeds, W, H):
    """Seed texture (H, W, 4): vec4(px, id + 1, 1) at floor(px); later k wins a shared texel (GPU: any one)."""
    np = _np()
    m = np.zeros((H, W, 4))
    px = np.clip(np.floor(seeds).astype(int), 0, [W - 1, H - 1])
    for k in range(len(seeds)):
        m[px[k, 1], px[k, 0]] = (seeds[k, 0], seeds[k, 1], k + 1, 1)
    return m


def jfa(seedmap, extra=1):
    """Jump flood == gen_sim_vor_jfa.glsl over Pm + extra passes (float32 distances, strict <, dy then dx)."""
    np = _np()
    H, W = seedmap.shape[:2]
    Pm = jfa_passes(W, H)
    cur = seedmap.astype(np.float32)
    px, py = np.meshgrid(np.arange(W, dtype=np.float32) + 0.5, np.arange(H, dtype=np.float32) + 0.5)
    for i in range(Pm + extra):
        step = (1 << (Pm - 1 - i)) if i < Pm else 1
        best = cur.copy()
        dxs, dys = px - best[..., 0], py - best[..., 1]
        bd = np.where(best[..., 2] > 0, dxs * dxs + dys * dys, np.float32(1e30)).astype(np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                s = np.zeros_like(cur)
                ys, yd = (slice(dy * step, H), slice(0, H - dy * step)) if dy >= 0 else \
                    (slice(0, H + dy * step), slice(-dy * step, H))
                xs, xd = (slice(dx * step, W), slice(0, W - dx * step)) if dx >= 0 else \
                    (slice(0, W + dx * step), slice(-dx * step, W))
                if abs(dy * step) < H and abs(dx * step) < W:
                    s[yd, xd] = cur[ys, xs]
                ex, ey = px - s[..., 0], py - s[..., 1]
                dd = (ex * ex + ey * ey).astype(np.float32)
                upd = (s[..., 2] > 0) & (dd < bd)
                best[upd] = s[upd]
                bd = np.where(upd, dd, bd)
        cur = best
    return cur


def voronoi_brute(seeds, W, H):
    """Exact nearest-seed id (1-based) per texel centre, (H, W)."""
    np = _np()
    px, py = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
    best = np.full((H, W), np.inf)
    ids = np.zeros((H, W), int)
    for k, (sx, sy) in enumerate(seeds):
        d = (px - sx) ** 2 + (py - sy) ** 2
        m = d < best
        best[m], ids[m] = d[m], k + 1
    return ids


def gabriel_edges(seeds):
    """Pairs (i, j) whose diametral circle holds no other seed (Gabriel graph, a subgraph of Delaunay)."""
    np = _np()
    n = len(seeds)
    out = []
    for i in range(n):
        for j in range(i + 1, n):
            m = 0.5 * (seeds[i] + seeds[j])
            r2 = 0.25 * np.sum((seeds[i] - seeds[j]) ** 2)
            d2 = np.sum((seeds - m) ** 2, -1)
            d2[[i, j]] = np.inf
            if np.all(d2 >= r2):
                out.append((i, j))
    return out


def worley(W, H, cellpx, jitter=1.0, wander=0.0, seed=1, t=0.0):
    """(F1, F2, id1) in cell units == gen_sim_vor_worley.glsl."""
    np = _np()
    cs = max(cellpx, 2.0)
    px, py = np.meshgrid((np.arange(W) + 0.5) / cs, (np.arange(H) + 0.5) / cs)
    gx, gy = np.floor(px).astype(int), np.floor(py).astype(int)
    amp = min(max(jitter, 0), 1) * (1 - 0.5 * min(max(wander, 0), 1))
    wa = 0.25 * min(max(wander, 0), 1)
    f1 = np.full(px.shape, 1e9)
    f2 = np.full(px.shape, 1e9)
    id1 = np.zeros(px.shape, int)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            cx, cy = gx + dx, gy + dy
            ph = 2 * math.pi * hash3(cx, cy, seed + 2)
            fx = cx + 0.5 + (hash3(cx, cy, seed) - 0.5) * amp + wa * np.sin(t + ph)
            fy = cy + 0.5 + (hash3(cx, cy, seed + 1) - 0.5) * amp + wa * np.cos(t * 0.9 + ph)
            d = np.hypot(px - fx, py - fy)
            a = d < f1
            b = (~a) & (d < f2)
            f2 = np.where(a, f1, np.where(b, d, f2))
            id1 = np.where(a, cx * 7919 + cy, id1)
            f1 = np.where(a, d, f1)
    return f1, f2, id1


# ------------------------------------------------------------------ dla (Laplacian growth)
DLA_SHAPES = ['centre', 'bottom', 'top', 'ring', 'input', 'scatter']
DLA_BC = {0: (1, 1, 1, 1), 1: (-1, -1, -1, 1), 2: (-1, -1, 1, -1), 3: (-1, -1, -1, -1), 4: (1, 1, 1, 1),
          5: (1, 1, 1, 1)}                     # left right bottom top; < 0 Neumann
DLA_BLOCK = 8                                  # Jacobi iterations per field pass (temporal blocking)


def dla_bc_expr(side, shape="parent().par.Shape.menuIndex"):
    return "%r[%s]" % ([DLA_BC[k][side] for k in range(len(DLA_SHAPES))], shape)


def dla_electrode(shape, FW, FH):
    """(cx, cy, radius) field px: ring growth gets a centre electrode disc, others none."""
    if shape == 3:
        return (0.5 * FW, 0.5 * FH, max(2.0, 0.03 * min(FW, FH)))
    return (0.0, 0.0, 0.0)


def dla_fixed(occ, FW, FH, el=(0, 0, 0)):
    """Fixed values per field cell == fixedAt(): 0 grounded (cluster under any of 4x4 samples), 1 electrode, -1 free."""
    np = _np()
    H, W = occ.shape
    sx, sy = W / FW, H / FH
    gx, gy = np.meshgrid(np.arange(FW), np.arange(FH))
    g = np.zeros((FH, FW), bool)
    for b in range(4):
        for a in range(4):
            x = np.clip(np.floor((gx + (a + 0.5) * 0.25) * sx).astype(int), 0, W - 1)
            y = np.clip(np.floor((gy + (b + 0.5) * 0.25) * sy).astype(int), 0, H - 1)
            g |= occ[y, x] > 0.5
    f = np.full((FH, FW), -1.0)
    if el[2] > 0:
        f[np.hypot(gx + 0.5 - el[0], gy + 0.5 - el[1]) <= el[2]] = 1.0
    f[g] = 0.0
    return f


def jacobi(phi, fixed, bc, iters):
    """Plain Jacobi: free cells = mean of 4 neighbours, sides by bc (< 0 Neumann = own value, else Dirichlet)."""
    np = _np()
    p = np.where(fixed >= 0, fixed, phi).astype(np.float64)
    free = fixed < 0
    for _ in range(iters):
        L = np.empty_like(p)
        R = np.empty_like(p)
        B = np.empty_like(p)
        T = np.empty_like(p)
        L[:, 1:], R[:, :-1], B[1:, :], T[:-1, :] = p[:, :-1], p[:, 1:], p[:-1, :], p[1:, :]
        L[:, 0] = p[:, 0] if bc[0] < 0 else bc[0]
        R[:, -1] = p[:, -1] if bc[1] < 0 else bc[1]
        B[0, :] = p[0, :] if bc[2] < 0 else bc[2]
        T[-1, :] = p[-1, :] if bc[3] < 0 else bc[3]
        p = np.where(free, 0.25 * (L + R + B + T), p)
    return p


def dla_init(W, H, shape, seed=1, thr=0.5, inp=None):
    np = _np()
    x, y = np.meshgrid(np.arange(W), np.arange(H))
    if shape == 0:
        return ((x == W // 2) & (y == H // 2)).astype(float)
    if shape == 1:
        return (y == 0).astype(float)
    if shape == 2:
        return ((x == W // 2) & (y == H - 1)).astype(float)
    if shape == 3:
        return (np.abs(np.hypot(x + 0.5 - 0.5 * W, y + 0.5 - 0.5 * H) - 0.45 * min(W, H)) < 0.75).astype(float)
    if shape == 4:
        return (_in_luma_cells(inp, W, H) > thr).astype(float)
    return (hash3(x, y, seed) < 0.0004).astype(float)


def dla_phi_at(field, W, H):
    """Manual bilinear of the field at every sim cell centre == phiAt()."""
    np = _np()
    FH, FW = field.shape
    fx = np.clip((np.arange(W) + 0.5) * FW / W - 0.5, 0, FW - 1)
    fy = np.clip((np.arange(H) + 0.5) * FH / H - 0.5, 0, FH - 1)
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
    wx, wy = fx - ix, fy - iy
    jx, jy = np.minimum(ix + 1, FW - 1), np.minimum(iy + 1, FH - 1)
    a, b = field[iy][:, ix], field[iy][:, jx]
    c, d = field[jy][:, ix], field[jy][:, jx]
    wx, wy = wx[None, :], wy[:, None]
    return (a + (b - a) * wx) * (1 - wy) + (c + (d - c) * wx) * wy


def dla_probability(phi, growth, eta, phiref):
    np = _np()
    return np.clip(growth * (np.maximum(phi, 0) / max(phiref, 1e-6)) ** eta, 0, 1)


def dla_grow(occ, stamp, field, P, frame=0, tdpass=0, field_iters=1e9, phimax=1.0):
    """One growth step == gen_sim_dla_grow.glsl (non-init). Returns (occ, stamp). No growth while the field has had
    fewer than Warmup Jacobi iterations since its restart; phi is normalised by phimax x Phiref."""
    np = _np()
    H, W = occ.shape
    if field_iters < P.get('Warmup', 256):
        return occ, stamp
    n = sum(_shift(occ, dx, dy, False) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    su = (int(frame) * 8 + int(tdpass)) & M32
    rs = (su * 7919 + (int(P.get('Seed', 1)) & M32)) & M32
    x, y = np.meshgrid(np.arange(W), np.arange(H))
    p = dla_probability(dla_phi_at(field, W, H), P.get('Growth', 1.0), P.get('Eta', 1.0), P.get('Phiref', 1.0) * phimax)
    hit = (occ < 0.5) & (n > 0.5) & (hash3(x, y, rs) < p)
    return np.where(hit, 1.0, occ), np.where(hit, float(su), stamp)


def dla_touched(occ, shape, el_sim=None):
    """True when an occupied cell sits next to an electrode side or within 1.5 cells of the electrode disc
    == gen_sim_dla_touch.glsl (the epoch filter is the caller's: pass only current cells)."""
    np = _np()
    H, W = occ.shape
    bc = DLA_BC[shape]
    o = occ > 0.5
    h = (bc[0] >= 0 and o[:, 0].any()) or (bc[1] >= 0 and o[:, -1].any()) or \
        (bc[2] >= 0 and o[0, :].any()) or (bc[3] >= 0 and o[-1, :].any())
    if el_sim and el_sim[2] > 0:
        x, y = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)
        h = h or bool((o & (np.hypot(x - el_sim[0], y - el_sim[1]) <= el_sim[2] + 1.5)).any())
    return bool(h)


def dla_phimax(phi):
    """Largest phi on the frontier (phi > 0 with a 4-neighbour at exactly 0; outside the frame counts as 1), 1 when
    there is none == the touch pass's texel 1."""
    np = _np()
    pad = np.pad(phi, 1, constant_values=1.0)
    nb0 = (pad[1:-1, 2:] == 0) | (pad[1:-1, :-2] == 0) | (pad[2:, 1:-1] == 0) | (pad[:-2, 1:-1] == 0)
    fr = (phi > 0) & nb0
    return float(phi[fr].max()) if fr.any() else 1.0


def dla_run(W, H, FW, FH, P, frames=300, steps=2, iters=32, return_field=False, fps=60.0):
    """Offline simulation in TD's per-frame order: touch pass (last frame's cluster + field: touched, phimax,
    regrow) -> field passes (Jacobi, grounded = last frame's cluster) -> growth steps. Returns (occ, stamp[, phi,
    regrows])."""
    np = _np()
    shape = int(P.get('Shape', 0))
    el = dla_electrode(shape, FW, FH)
    el_sim = (el[0] * W / FW, el[1] * H / FH, el[2] * W / FW)
    bc = DLA_BC[shape]
    nit = DLA_BLOCK * max(1, int(math.ceil(iters / DLA_BLOCK)))
    regrows, touched, t_touch = 0, False, 0.0
    occ = stamp = phi = None
    its, pm = 0, 1.0
    for f in range(frames):
        now = f / fps
        restart = occ is None
        if not restart:                               # touch pass (cluster + field of the last frame, same E)
            pm = dla_phimax(phi)
            if not touched and dla_touched(occ, shape, el_sim):
                touched, t_touch = True, now
            if touched and P.get('Autoregrow', 1) and now - t_touch >= P.get('Hold', 1.0):
                touched, regrows, restart = False, regrows + 1, True
        if restart:      # field: init pass (phi 1) + the frame's other passes, nothing grounded (old epoch)
            phi = jacobi(np.ones((FH, FW)), dla_fixed(np.zeros((H, W)), FW, FH, el), bc, nit - DLA_BLOCK)
            its = nit - DLA_BLOCK
            occ = dla_init(W, H, shape, P.get('Seed', 1))  # growth pass: init
            stamp = np.zeros_like(occ)
            continue
        phi = jacobi(phi, dla_fixed(occ, FW, FH, el), bc, nit)
        its += nit
        if touched:
            continue
        for k in range(steps):
            occ, stamp = dla_grow(occ, stamp, phi, P, f + 1, k, its, pm)
    return (occ, stamp, phi, regrows) if return_field else (occ, stamp)


# ------------------------------------------------------------------ blobs (metaballs / SDF blend)
BLOB_FIELDS = ['metaball', 'sdf']
BLOB_MOTIONS = ['wander', 'lava', 'orbit', 'drift']
BLOB_STYLES = ['flat', 'mercury', 'neon', 'bands', 'glass']
MAXB = 1024


def blob_params(n, W, H, t, P):
    """(n, 4) cx cy r S and hue (n,) == blobAt() in gen_sim_blobs.glsl."""
    np = _np()
    sd = int(P.get('Seed', 1))
    k = np.arange(min(n, MAXB))
    h = [hash3(k, j, sd) for j in range(1, 7)]
    hue = hash3(k, 9, sd)
    m = min(W, H)
    motion = int(P.get('Motion', 0))
    w1, w2 = 0.2 + 0.4 * h[2], 0.2 + 0.4 * h[3]
    p1, p2 = 2 * math.pi * h[4], 2 * math.pi * h[5]
    if motion == 1:
        c = np.stack([W * (0.1 + 0.8 * h[0]) + 0.06 * m * np.sin(t * w2 + p2),
                      H * (0.5 + 0.42 * np.sin(t * w1 * 0.5 + p1))], -1)
    elif motion == 2:
        a = t * (w1 - 0.4) * 1.5 + p1
        c = 0.5 * np.array([W, H]) + ((0.1 + 0.35 * h[1]) * m)[:, None] * np.stack([np.cos(a), np.sin(a)], -1)
    elif motion == 3:
        c = np.stack([W * vnoise(t * 0.25 * w1, k * 7.31, sd + 11), H * vnoise(t * 0.25 * w2, k * 3.17, sd + 12)], -1)
    else:
        c = np.array([W, H]) * (0.5 + 0.42 * np.stack([np.sin(t * w1 + p1), np.sin(t * w2 + p2)], -1))
    r = P.get('Radius', 90.0) * (1 + P.get('Rvar', 0.4) * (2 * h[1] - 1)) * \
        (1 + P.get('Pulse', 0.0) * np.sin(t * P.get('Pulserate', 0.5) * 2 * math.pi + p2))
    r = np.maximum(r, 0.5)
    T = min(max(P.get('Threshold', 0.5), 0.001), 0.999)
    if int(P.get('Field', 0)) == 0:
        S = r / math.sqrt(1 - T ** (1 / 3.0))
    else:
        S = r + max(P.get('Softness', 40.0), 0)
    return np.concatenate([c, r[:, None], S[:, None]], -1), hue


def blob_field(x, y, blobs, P):
    """Signed distance sd (px, < 0 inside) and coverage at points (x, y) == the per-pixel loop (all blobs, k order)."""
    np = _np()
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    T = min(max(P.get('Threshold', 0.5), 0.001), 0.999)
    if int(P.get('Field', 0)) == 0:
        F = np.zeros_like(x)
        gx, gy = np.zeros_like(x), np.zeros_like(x)
        for cx, cy, r, S in blobs:
            dx, dy = x - cx, y - cy
            dd = dx * dx + dy * dy
            q = np.where(dd < S * S, 1 - dd / (S * S), 0.0)
            F += q ** 3
            gx += -6 * q * q * dx / (S * S)
            gy += -6 * q * q * dy / (S * S)
        gl = np.hypot(gx, gy)
        sd = np.where(F > 0, (T - F) / np.maximum(gl, 1e-6), 1e9)
    else:
        k = max(P.get('Softness', 40.0), 1e-3)
        sd = np.full(x.shape, 1e9)
        first = True
        for cx, cy, r, S in blobs:
            si = np.hypot(x - cx, y - cy) - r
            if first:
                sd, first = si, False
                continue
            h = np.maximum(k - np.abs(sd - si), 0) / k
            sd = np.minimum(sd, si) - h * h * k * 0.25
    return sd, np.clip(0.5 - sd, 0, 1)


# ------------------------------------------------------------------ lic
LIC_SOURCES = ['curl', 'edges', 'gradient', 'vortex', 'fieldtop', 'circuit']
LIC_COLOURS = ['value', 'angle', 'speed', 'input']


def lic_curl_field(FW, FH, W, H, scale, octaves=3, seed=1, t=0.0, rotate=0.0, snap=0):
    """(FH, FW, 4) == gen_sim_lic_field.glsl sources 0 (curl) / 5 (circuit, snap > 0)."""
    np = _np()
    fx, fy = np.meshgrid((np.arange(FW) + 0.5) * W / FW, (np.arange(FH) + 0.5) * H / FH)
    qx, qy = fx / max(scale, 1.0), fy / max(scale, 1.0)
    oc = min(max(int(octaves + 0.5), 1), 6)

    def fbm(ax, ay):
        a, w, s = 0.0, 1.0, 0.0
        for o in range(oc):
            a = a + w * vnoise(ax * 2 ** o + t * (0.37 + 0.11 * o), ay * 2 ** o + t * 0.23, seed + o)
            s += w
            w *= 0.5
        return a / s
    h = 0.25
    dx = fbm(qx + h, qy) - fbm(qx - h, qy)
    dy = fbm(qx, qy + h) - fbm(qx, qy - h)
    vx, vy = dy / (2 * h), -dx / (2 * h)
    if snap:
        n = max(math.floor(snap + 0.5), 1)
        an = np.floor(np.arctan2(vy, vx) / (2 * math.pi) * n + 0.5) * (2 * math.pi) / n
        m = np.hypot(vx, vy)
        vx, vy = m * np.cos(an), m * np.sin(an)
    cr, sr = math.cos(rotate), math.sin(rotate)
    vx, vy = cr * vx - sr * vy, sr * vx + cr * vy
    m = np.hypot(vx, vy)
    safe = np.where(m > 1e-9, m, 1.0)
    return np.stack([np.where(m > 1e-9, vx / safe, 0), np.where(m > 1e-9, vy / safe, 0), m, np.ones_like(m)], -1)


def sample_bilinear(tex, u, v, quant=0):
    """texture() with linear filter + hold (clamp) extend at uv; quant = subtexel weight bits (GPU ~8) or 0 exact."""
    np = _np()
    Hh, Ww = tex.shape[:2]
    x = np.clip(np.asarray(u) * Ww - 0.5, 0, Ww - 1)
    y = np.clip(np.asarray(v) * Hh - 0.5, 0, Hh - 1)
    ix, iy = np.floor(x).astype(int), np.floor(y).astype(int)
    wx, wy = x - ix, y - iy
    if quant:
        wx, wy = np.round(wx * (1 << quant)) / (1 << quant), np.round(wy * (1 << quant)) / (1 << quant)
    jx, jy = np.minimum(ix + 1, Ww - 1), np.minimum(iy + 1, Hh - 1)
    wx, wy = wx[..., None], wy[..., None]
    a, b, c, d = tex[iy, ix], tex[iy, jx], tex[jy, ix], tex[jy, jx]
    return (a + (b - a) * wx) * (1 - wy) + (c + (d - c) * wx) * wy


def lic(field, W, H, xs, ys, P, phase=0.0, quant=0):
    """LIC value v at pixel centres (xs, ys) == gen_sim_lic.glsl (before colouring)."""
    np = _np()
    T = min(max(int(P.get('Taps', 20) + 0.5), 1), 64)
    h = P.get('Step', 1.5)
    fl, rp = P.get('Flow', 0.5), P.get('Ripples', 2.0)
    g = max(P.get('Grain', 1.5), 1.0)
    sd = int(P.get('Seed', 1))
    x0 = np.stack([np.asarray(xs) + 0.5, np.asarray(ys) + 0.5], -1).astype(np.float64)

    def noise(p):
        return hash3(np.floor(p[..., 0] / g).astype(np.int64), np.floor(p[..., 1] / g).astype(np.int64), sd)

    def dirat(p):
        return sample_bilinear(field, p[..., 0] / W, p[..., 1] / H, quant)[..., :2]
    w0 = max(1 + fl * math.cos(-2 * math.pi * phase), 0)
    acc, ws = w0 * noise(x0), np.full(x0.shape[:-1], w0)
    for sgn in (-1, 1):
        y = x0.copy()
        for i in range(1, T + 1):
            d1 = dirat(y)
            d2 = dirat(y + 0.5 * h * sgn * d1)
            y = y + h * sgn * d2
            s = i * sgn / T
            w = (0.5 + 0.5 * math.cos(math.pi * abs(s))) * max(1 + fl * math.cos(2 * math.pi * (s * rp - phase)), 0)
            acc = acc + w * noise(y)
            ws = ws + w
    return np.clip((acc / np.maximum(ws, 1e-6) - 0.5) * P.get('Contrast', 3.0) + 0.5 + P.get('Bright', 0.0), 0, 1)


# ------------------------------------------------------------------ live parity: dump in TD, check outside
# ------------------------------------------------------------------ ripple (== gen_sim_ripple_step.glsl, lane A 27 Oct)
RIPPLE_EDGES = ['wrap', 'reflect', 'absorb']


def _ripple_shift(h, dx, dy, e):
    """h at c + (dx, dy): wrap / reflect (clamp) / absorb (0 outside); arrays [y, x]."""
    np = _np()
    if e == 0:
        return np.roll(h, (-dy, -dx), axis=(0, 1))
    pad = np.pad(h, 1, mode='edge' if e == 1 else 'constant')
    Hh, Ww = h.shape
    return pad[1 + dy:1 + dy + Hh, 1 + dx:1 + dx + Ww]


def _bump(px, py, cx, cy, r):
    np = _np()
    d = np.hypot(px - cx, py - cy)
    k = np.cos(0.5 * math.pi * d / r)
    return np.where(d < r, k * k, 0.0)


def ripple_step(st, U, tdpass=0, inp=None):
    """One step of the water (float64). st [H, W, 4] = (h, h_prev, hits applied, epoch); U = the step's uniforms
    {uSim, uWave, uRain, uHit, uHitp}; inp = slot input [h, w, 4] or None (black)."""
    np = _np()
    sim, wave, rain, hit, hitp = U['uSim'], U['uWave'], U['uRain'], U['uHit'], U['uHitp']
    Hh, Ww = st.shape[:2]
    if abs(st[0, 0, 3] - sim[3]) > 0.5 or (Ww, Hh) != (int(sim[0] + 0.5), int(sim[1] + 0.5)):
        out = np.zeros((int(sim[1] + 0.5), int(sim[0] + 0.5), 4))
        out[..., 2], out[..., 3] = hit[0], sim[3]
        return out
    if tdpass >= wave[2]:
        return st.copy()
    e = int(sim[2] + 0.5)
    h, hp = st[..., 0], st[..., 1]
    nb = _ripple_shift(h, 1, 0, e) + _ripple_shift(h, -1, 0, e) + _ripple_shift(h, 0, 1, e) + _ripple_shift(h, 0, -1, e)
    hn = wave[1] * (2.0 * h - hp + wave[0] * (nb - 4.0 * h))
    ys, xs = np.mgrid[0:Hh, 0:Ww]
    px, py = xs + 0.5, ys + 0.5
    sid, seed = int(wave[3]) * 8 + tdpass, int(rain[3])
    for j in range(4):
        if float(hash3(sid, j, seed)) >= rain[0] - j:
            continue
        cx, cy = float(hash3(sid, j + 4, seed)) * Ww, float(hash3(sid, j + 8, seed)) * Hh
        hn = hn - rain[1] * _bump(px, py, cx, cy, rain[2])
    done = float(st[0, 0, 2])
    if tdpass == 0 and hit[0] > done:
        for k in range(1, 9):
            n = done + k
            if n > hit[0]:
                break
            pm = int(hit[2] + 0.5)
            if pm == 1:
                cx, cy = 0.5 * Ww, 0.5 * Hh
            elif pm == 2:
                cx, cy = hitp[0] * Ww, hitp[1] * Hh
            else:
                cx, cy = float(hash3(int(n), 1, seed)) * Ww, float(hash3(int(n), 2, seed)) * Hh
            hn = hn - hit[1] * _bump(px, py, cx, cy, hit[3])
        done = hit[0]
    if hitp[3] > 0.0 and inp is not None:
        ih, iw = inp.shape[:2]
        qx = np.clip((px * iw / Ww).astype(np.int64), 0, iw - 1)
        qy = np.clip((py * ih / Hh).astype(np.int64), 0, ih - 1)
        hn = hn - hitp[3] * np.maximum(luma(inp[qy, qx, :3]) - hitp[2], 0.0)
    return np.stack([hn, h, np.full_like(h, done), np.full_like(h, sim[3])], -1)


def ripple_energy(st):
    """Sum of h^2 + h_prev^2 (decays by Damp per step for free waves: |root|^2 = Damp)."""
    return float((st[..., 0] ** 2 + st[..., 1] ** 2).sum())


# ------------------------------------------------------------------ lavalamp (== gen_sim_lava_*.glsl, lane A 27 Oct)
LAVA_SEEDS = ['layers', 'blobs', 'input']


def _clamped(f, dx, dy):
    np = _np()
    p = np.pad(f, ((1, 1), (1, 1), (0, 0)), mode='edge')
    Hh, Ww = f.shape[:2]
    return p[1 + dy:1 + dy + Hh, 1 + dx:1 + dx + Ww]


def _in_luma_at(inp, px, py, W, H):
    np = _np()
    if inp is None:
        return np.zeros_like(px)
    ih, iw = inp.shape[:2]
    qx = np.clip((px * iw / W).astype(np.int64), 0, iw - 1)
    qy = np.clip((py * ih / H).astype(np.int64), 0, ih - 1)
    return luma(inp[qy, qx, :3])


def lava_seed(U, inp=None):
    np = _np()
    sim, sd = U['uSim'], U['uSd']
    W, H = int(sim[0] + 0.5), int(sim[1] + 0.5)
    ys, xs = np.mgrid[0:H, 0:W]
    px, py = xs + 0.5, ys + 0.5
    mode, seed = int(sim[2] + 0.5), int(sd[1])
    if mode == 2:
        rho = _in_luma_at(inp, px, py, W, H)
    elif mode == 1:
        rho = np.zeros((H, W))
        for i in range(12):
            cx, cy = float(hash3(i, 1, seed)) * W, float(hash3(i, 2, seed)) * H
            rad = (0.04 + 0.08 * float(hash3(i, 3, seed))) * H
            rho = np.maximum(rho, (np.hypot(px - cx, py - cy) < rad).astype(np.float64))
    else:
        y = H * (1.0 - sd[0]) + 0.02 * H * np.sin(px * 0.11 + seed) + 2.0 * (hash3(xs, ys, seed) - 0.5)
        rho = (py > y).astype(np.float64)
    out = np.zeros((H, W, 4))
    out[..., 2] = rho
    return out


def lava_step(st, U, mass, tdpass=0, inp=None, quant=8):
    """One fluid step (float64; GPU bilinear weights ~8 bits: quant). st [H, W, 4] = (vx, vy, density, pressure);
    mass = (target, mean, 0, epoch) of the last frame."""
    np = _np()
    sim, fl, sd, run = U['uSim'], U['uFl'], U['uSd'], U['uRun']
    W, H = int(sim[0] + 0.5), int(sim[1] + 0.5)
    if st.shape[:2] != (H, W) or abs(mass[3] - sim[3]) > 0.5:
        return lava_seed(U, inp)
    if tdpass >= run[0]:
        return st.copy()
    ys, xs = np.mgrid[0:H, 0:W]
    px, py = xs + 0.5, ys + 0.5
    adv = sample_bilinear(st, (px - st[..., 0]) / W, (py - st[..., 1]) / H, quant)
    l, r, d, u = _clamped(st, -1, 0), _clamped(st, 1, 0), _clamped(st, 0, -1), _clamped(st, 0, 1)
    div = 0.5 * ((r[..., 0] - l[..., 0]) + (u[..., 1] - d[..., 1]))
    pn = 0.25 * (l[..., 3] + r[..., 3] + u[..., 3] + d[..., 3] - div)
    vx = adv[..., 0] - 0.5 * (r[..., 3] - l[..., 3])
    vy = adv[..., 1] - 0.5 * (u[..., 3] - d[..., 3])
    rho = adv[..., 2].copy()
    vy = vy - fl[0] * (rho - mass[0])
    vx, vy = vx * (1.0 - fl[1]), vy * (1.0 - fl[1])
    vx[:, 0] = vx[:, -1] = 0.0
    vy[0, :] = vy[-1, :] = 0.0
    if fl[2] > 0.0:
        hz = fl[3] * H
        k = fl[2] * (1.0 + run[2] * (vnoise(px / max(0.08 * W, 1.0), np.full_like(px, run[3] * 0.3), int(sd[1])) - 0.5) * 2.0)
        k = np.clip(k, 0.0, 1.0)
        rho = np.where(py < hz, rho - rho * k, np.where(py > H - hz, rho + (1.0 - rho) * k, rho))
    if sd[2] > 0.0:
        rho = rho + (_in_luma_at(inp, px, py, W, H) - rho) * sd[2]
    if tdpass == 0 and sd[3] > 0.5:
        rho = rho + (mass[0] - mass[1])
    return np.stack([vx, vy, rho, pn], -1)


def lava_mass(avg, last, epoch):
    """== gen_sim_lava_mass.glsl: (target, mean, 0, epoch)."""
    target = avg[2] if abs(last[3] - epoch) > 0.5 else last[0]
    return (target, avg[2], 0.0, epoch)


# ------------------------------------------------------------------ sand (== gen_sim_sand_step.glsl, lane A 27 Oct)
SAND_SEEDS = ['empty', 'pile', 'input', 'layers']
SAND_MATS = ['empty', 'sand', 'water', 'wall']


def _q8(x):
    np = _np()
    return np.round(np.asarray(x, dtype=np.float64) * 255.0) / 255.0


def sand_seed(U, inp=None):
    np = _np()
    sim, hit, inn = U['uSim'], U['uHit'], U['uIn']
    W, H = int(sim[0] + 0.5), int(sim[1] + 0.5)
    ys, xs = np.mgrid[0:H, 0:W]
    mode, sd = int(sim[2] + 0.5), int(hit[3])
    h, g = hash3(xs, ys, sd), hash3(xs, ys, sd + 1)
    m = np.zeros((H, W))
    if mode == 1:
        m = np.where((ys > 0.45 * H) & (h < inn[2]), 1.0, 0.0)
    elif mode == 2:
        lum = _in_luma_at(inp, xs + 0.5, ys + 0.5, W, H) if inp is not None else np.zeros((H, W))
        m = np.where(lum > inn[1], 1.0, 0.0)
        g = np.where(lum > inn[1], lum, g)
    elif mode == 3:
        m = np.where(h < inn[2], np.where(ys > 0.5 * H, 1.0, 2.0), 0.0)
    out = np.zeros((H, W, 4))
    out[..., 0], out[..., 1] = m / 3.0, g
    out[..., 2], out[..., 3] = (hit[0] % 256.0) / 255.0, sim[3] / 255.0
    return _q8(out)


def sand_counts(st):
    """{material: cell count} of a state."""
    np = _np()
    m = np.floor(st[..., 0] * 3.0 + 0.5).astype(int)
    return dict((SAND_MATS[k], int((m == k).sum())) for k in range(4))


def sand_step(st, U, tdpass=0, inp=None):
    """One Margolus step (exact integer CA; rgba8 state as stored)."""
    np = _np()
    sim, rule, src, hit, inn, run = U['uSim'], U['uRule'], U['uSrc'], U['uHit'], U['uIn'], U['uRun']
    W, H = int(sim[0] + 0.5), int(sim[1] + 0.5)
    ep = sim[3] / 255.0
    if st.shape[:2] != (H, W) or abs(st[0, 0, 3] - ep) > 0.5 / 255.0:
        return sand_seed(U, inp)
    if tdpass >= inn[3]:
        return st.copy()
    sd = int(hit[3])
    sid = int(run[0]) * 8 + tdpass
    o = (int(run[0]) * int(inn[3] + 0.5) + tdpass) & 1
    ys, xs = np.mgrid[0:H, 0:W]
    m = np.floor(st[..., 0] * 3.0 + 0.5).astype(int)
    g = st[..., 1].copy()
    done = math.floor(st[0, 0, 2] * 255.0 + 0.5)
    if inn[0] > 0.5:                                     # walls from the slot input
        lum = _in_luma_at(inp, xs + 0.5, ys + 0.5, W, H) if inp is not None else np.zeros((H, W))
        wall = lum > inn[1]
        g = np.where(wall & (m == 0), 0.5, g)
        m = np.where(wall & (m == 0), 3, np.where(~wall & (m == 3), 0, m))
    if src[0] > 0.0:                                     # pour
        pour = ((m == 0) & (ys >= H - 2) & (np.abs((xs + 0.5) / W - src[1]) <= src[2])
                & (hash3(xs, ys, sid * 3 + 1 + sd) < src[0]))
        g = np.where(pour, hash3(xs, ys, sid * 3 + 2 + sd), g)
        m = np.where(pour, int(src[3] + 0.5), m)
    if tdpass == 0:                                      # hits not applied yet
        empty = m == 0
        pend = (hit[0] - done) % 256.0
        for k in range(1, 9):
            if k > pend:
                break
            N = int(hit[0] - pend) + k
            cx, cy = float(hash3(N, 7, sd)) * W, H - hit[1] - 2.0
            ins = empty & (np.hypot(xs + 0.5 - cx, ys + 0.5 - cy) < hit[1])
            m = np.where(ins, int(hit[2] + 0.5), m)
            g = np.where(ins, hash3(xs, ys, N + 4096 * sd), g)
    if rule[3] > 0.0:                                    # drain
        dr = (ys == 0) & ((m == 1) | (m == 2)) & (hash3(xs, np.full_like(xs, sid), 99 + sd) < rule[3])
        m = np.where(dr, 0, m)
    M2 = np.full((H + 2, W + 2), 3)
    G2 = np.zeros((H + 2, W + 2))
    M2[1:-1, 1:-1], G2[1:-1, 1:-1] = m, g
    sx = np.arange(o - 2, W, 2)
    sx = sx[sx + 1 >= 0]
    sy = np.arange(o - 2, H, 2)
    sy = sy[sy + 1 >= 0]
    bx, by = np.meshgrid(sx, sy)
    ia, ja = (by + 2, bx + 1)
    ib, jb = (by + 2, bx + 2)
    ic, jc = (by + 1, bx + 1)
    id_, jd = (by + 1, bx + 2)
    mA, mB, mC, mD = M2[ia, ja], M2[ib, jb], M2[ic, jc], M2[id_, jd]
    gA, gB, gC, gD = G2[ia, ja], G2[ib, jb], G2[ic, jc], G2[id_, jd]
    w = lambda q: np.where(q == 1, 2.0, np.where(q == 2, 1.0, 0.0))
    mv = lambda q: (q == 1) | (q == 2)
    r0, r1 = hash3(bx, by, sid * 5 + sd), hash3(bx, by, sid * 5 + 1 + sd)
    r2, r3 = hash3(bx, by, sid * 5 + 2 + sd), hash3(bx, by, sid * 5 + 3 + sd)

    def swap(cond, p, q, gp, gq):
        return np.where(cond, q, p), np.where(cond, p, q), np.where(cond, gq, gp), np.where(cond, gp, gq)
    f = r0 < rule[0]
    s1 = f & mv(mA) & (mC != 3) & (w(mA) > w(mC))
    mA, mC, gA, gC = swap(s1, mA, mC, gA, gC)
    s2 = f & mv(mB) & (mD != 3) & (w(mB) > w(mD))
    mB, mD, gB, gD = swap(s2, mB, mD, gB, gD)
    ad = mv(mA) & (mD != 3) & (w(mA) > w(mD)) & ((mC == 3) | (w(mC) >= w(mA)))
    bc = mv(mB) & (mC != 3) & (w(mB) > w(mC)) & ((mD == 3) | (w(mD) >= w(mB)))
    t = r2 < rule[1]
    doad = t & ad & (~bc | (r1 < 0.5))
    dobc = t & ~doad & bc
    mA, mD, gA, gD = swap(doad, mA, mD, gA, gD)
    mB, mC, gB, gC = swap(dobc, mB, mC, gB, gC)
    fl = r3 < rule[2]
    s3 = fl & (((mC == 2) & (mD == 0)) | ((mD == 2) & (mC == 0)))
    mC, mD, gC, gD = swap(s3, mC, mD, gC, gD)
    s4 = fl & (((mA == 2) & (mB == 0)) | ((mB == 2) & (mA == 0)))
    mA, mB, gA, gB = swap(s4, mA, mB, gA, gB)
    for (i, j), q, gq in (((ia, ja), mA, gA), ((ib, jb), mB, gB), ((ic, jc), mC, gC), ((id_, jd), mD, gD)):
        keep = (i >= 1) & (i <= H) & (j >= 1) & (j <= W)
        M2[i[keep], j[keep]] = q[keep]
        G2[i[keep], j[keep]] = gq[keep]
    out = np.zeros((H, W, 4))
    out[..., 0], out[..., 1] = M2[1:-1, 1:-1] / 3.0, G2[1:-1, 1:-1]
    out[..., 2] = ((hit[0] % 256.0) if tdpass == 0 else done) / 255.0
    out[..., 3] = ep
    return _q8(out)


def dump_code(module_path, outdir, tops):
    """td_exec snippet: saves numpyArray of each named TOP (in `module_path`) + every GLSL TOP's vec uniforms."""
    return (
        "import numpy as _n, json as _j, os as _o\n"
        "_m = op(%r); _d = %r; _o.makedirs(_d, exist_ok=True)\n"
        "for _t in %r:\n"
        "    _n.save(_o.path.join(_d, _t + '.npy'), _m.op(_t).numpyArray(delayed=False))\n"
        "_u = {}\n"
        "for _g in _m.findChildren(type=glslTOP, depth=1):\n"
        "    for _k in range(_g.seq.vec.numBlocks):\n"
        "        _nm = getattr(_g.par, 'vec%%dname' %% _k).eval()\n"
        "        if _nm:\n"
        "            _u[_g.name + '.' + _nm] = [getattr(_g.par, 'vec%%dvalue%%s' %% (_k, _c)).eval() for _c in 'xyzw']\n"
        "_u['_pars'] = dict((p.name, p.eval()) for p in _m.customPars if p.style not in ('Pulse', 'TOP', 'CHOP'))\n"
        "_u['_frame'] = absTime.frame\n"
        "open(_o.path.join(_d, 'uniforms.json'), 'w').write(_j.dumps(_u, default=str))\n"
        "result = sorted(_o.listdir(_d))\n" % (module_path, outdir, list(tops)))


def _load(d):
    np = _np()
    u = json.load(open(os.path.join(d, 'uniforms.json')))
    arrs = dict((f[:-4], np.load(os.path.join(d, f))) for f in os.listdir(d) if f.endswith('.npy'))
    return u, arrs


def check(kind, d):
    """Compare a live dump with the reference. Returns a dict of numbers (printed by the CLI)."""
    np = _np()
    u, A = _load(d)
    P = u['_pars']
    if kind == 'ca':
        fam = FAMILIES.index(P['Family']) if isinstance(P['Family'], str) else int(P['Family'])
        P['Seed'] = int(P['Seed'])
        P['Rule'] = ruleset_rule(P.get('Ruleset', 'custom'), P.get('Rule', 'B3/S23'))
        before, after = A['state_fb'].astype(np.float64), A['step'].astype(np.float64)
        frame = int(u['step.uRun'][1])
        ref = before
        for k in range(int(u['step.uRun'][0])):
            ref = ca_step(ref, fam, P, frame, k, A.get('in1'))
        dif = np.abs(ref[..., 0] - after[..., 0])
        return {'cells': int(dif.size), 'state_mismatch': int((dif > (1e-4 if fam == 4 else 0.5)).sum()),
                'max_abs': float(dif.max()), 'alive_frac': float((after[..., 0] > 0.5).mean())}
    if kind == 'vor':
        jf = A['jfa'].astype(np.float64)
        Hh, Ww = jf.shape[:2]
        seeds = A['seed'][..., :3].reshape(-1, 3)
        seeds = seeds[seeds[:, 2] > 0]
        order = np.argsort(seeds[:, 2])
        seeds = seeds[order]
        ref = jfa(A['seed'], extra=int(P.get('Extra', 1)))
        same = (ref[..., 2] == jf[..., 2]).mean()
        brute = voronoi_brute(seeds[:, :2], Ww, Hh)
        idmap = np.zeros(int(seeds[:, 2].max()) + 2, int)
        idmap[seeds[:, 2].astype(int)] = np.arange(1, len(seeds) + 1)
        exact = (idmap[jf[..., 2].astype(int)] == brute).mean()
        return {'jfa_vs_ref_same': float(same), 'jfa_vs_bruteforce_exact': float(exact), 'seeds': int(len(seeds))}
    if kind == 'dla':
        fb, fl = A['field_fb'][..., 0].astype(np.float64), A['field'][..., 0].astype(np.float64)
        cl = A['cluster_fb'][..., 0].astype(np.float64)
        FH, FW = fl.shape
        shape = DLA_SHAPES.index(P['Shape']) if isinstance(P['Shape'], str) else int(P['Shape'])
        el = dla_electrode(shape, FW, FH)
        iters = DLA_BLOCK * int(math.ceil(P['Iters'] / DLA_BLOCK))
        ref = jacobi(fb, dla_fixed(cl, FW, FH, el), DLA_BC[shape], iters)
        return {'field_max_abs': float(np.abs(ref - fl).max()), 'field_mean': float(fl.mean()),
                'cluster_cells': int((cl > 0.5).sum())}
    if kind == 'blobs':
        out = A['fx'].astype(np.float64)
        Hh, Ww = out.shape[:2]
        t = float(A['clock'][0, 0, 0])
        blobs, _hue = blob_params(int(P['Count']), Ww, Hh, t, dict(P, Field=BLOB_FIELDS.index(P['Field']),
                                                                    Motion=BLOB_MOTIONS.index(P['Motion'])))
        ys, xs = np.mgrid[0:Hh:7, 0:Ww:7]
        sd, cov = blob_field(xs + 0.5, ys + 0.5, blobs, dict(P, Field=BLOB_FIELDS.index(P['Field'])))
        inside_ref = cov > 0.5
        inside_live = out[ys, xs, 3] > 0.5 if P.get('Blend') == 'alpha' else out[ys, xs, :3].max(-1) > 0.02
        return {'samples': int(cov.size), 'coverage_ref': float(inside_ref.mean()),
                'agree': float((inside_ref == inside_live).mean())}
    if kind == 'lic':
        fl = A['field'].astype(np.float64)
        out = A['fx'].astype(np.float64)
        Hh, Ww = out.shape[:2]
        rng = np.random.default_rng(1)
        xs, ys = rng.integers(0, Ww, 2000), rng.integers(0, Hh, 2000)
        ph = float(A['clock'][0, 0, 0]) * float(P.get('Flowspeed', 0.5))
        v = lic(fl, Ww, Hh, xs, ys, P, ph, quant=8)
        live = out[ys, xs, 0]                    # Palette mono + Blend replace: r = v
        e = np.abs(v - live)
        return {'median_abs': float(np.median(e)), 'p99_abs': float(np.percentile(e, 99))}
    if kind == 'ripple':
        before, after = A['state_fb'].astype(np.float64), A['step'].astype(np.float64)
        U = dict((k.split('.', 1)[1], [float(x) for x in v]) for k, v in u.items() if k.startswith('step.'))
        ref = before
        for k in range(max(1, int(U['uWave'][2]))):
            ref = ripple_step(ref, U, k, A.get('in1'))
        dif = np.abs(ref[..., :3] - after[..., :3])
        return {'texels': int(dif[..., 0].size), 'max_abs': float(dif.max()), 'h_rms': float(np.sqrt((after[..., 0] ** 2).mean())),
                'energy_live': ripple_energy(after), 'energy_ref': ripple_energy(ref), 'hits_applied': float(after[0, 0, 2])}
    if kind == 'lava':
        before, after = A['state_fb'].astype(np.float64), A['step'].astype(np.float64)
        U = dict((k.split('.', 1)[1], [float(x) for x in v]) for k, v in u.items() if k.startswith('step.'))
        mass = [float(x) for x in A['mass_fb'][0, 0]]
        ref = before
        for k in range(max(1, int(U['uRun'][0]))):
            ref = lava_step(ref, U, mass, k, A.get('in1'))
        dz = np.abs(ref[..., 2] - after[..., 2])
        dv = np.abs(ref[..., :2] - after[..., :2])
        return {'texels': int(dz.size), 'rho_max_abs': float(dz.max()), 'rho_p99': float(np.percentile(dz, 99)),
                'vel_max_abs': float(dv.max()), 'mean_live': float(after[..., 2].mean()), 'mean_ref': float(ref[..., 2].mean()),
                'target': mass[0], 'mass_mean_last': mass[1]}
    if kind == 'sand':
        before, after = A['state_fb'].astype(np.float64), A['step'].astype(np.float64)
        U = dict((k.split('.', 1)[1], [float(x) for x in v]) for k, v in u.items() if k.startswith('step.'))
        ref = before
        for k in range(max(1, int(U['uIn'][3]))):
            ref = sand_step(ref, U, k, A.get('in1'))
        mm = np.floor(after[..., 0] * 3 + 0.5) != np.floor(ref[..., 0] * 3 + 0.5)
        return {'cells': int(mm.size), 'material_mismatch': int(mm.sum()),
                'shade_max_abs': float(np.abs(after[..., 1] - ref[..., 1]).max()),
                'counts_before': sand_counts(before), 'counts_after': sand_counts(after), 'counts_ref': sand_counts(ref)}
    raise ValueError(kind)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'check':
        print(json.dumps(check(sys.argv[2], sys.argv[3]), indent=1))
    else:
        print(__doc__)
