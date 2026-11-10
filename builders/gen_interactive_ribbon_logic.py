"""gen_interactive_ribbon_logic - float64 numpy twin of GEN_interactive 'ribbon' (builders/glsl/
gen_interactive_ribbon_{hist,segs,draw}.glsl): the history ring step, the segment list and the per-pixel draw. Arrays
are [y, x, 4] with y = 0 the bottom row (TD texel space, T-58). Live parity: read hist / segs / fx with numpyArray in
TD (after a freeze: Speed 0), feed hist + uniforms here, compare (docs/builds/gen_interactive.md LIVE CHECKS R*).
numpy imported inside functions. ASCII only."""
import math
import os

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
_GI = {}


def gi():
    if not _GI:
        with open(os.path.join(HERE, 'gen_interactive_logic.py')) as fh:
            exec(fh.read(), _GI)
    return _GI


def _np():
    import numpy
    return numpy


def defaults():
    """{par: value} defaults of the ribbon pages (menus as index) - the same values the module file declares."""
    return dict(Ribbons=8, Pointstart=0, Length=96, Sampleevery=0.0, Subdiv=3, Strands=1, Spread=6.0, Fade=2.5,
                Fadecurve=1.0, Width=18.0, Widthlaw=1, Speedref=600.0, Taper=0.6, Widthmin=0.5, Widthmax=400.0,
                Wobble=0.0, Wobblefreq=2.0, Wobblespeed=0.0, Seed=1, Style=0, Glow=0.0, Glowwidth=12.0, Edge=2.0,
                Colormode=0, Colourspread=1.0, Speed=1.0, Beatgain=0.0, Beatdecay=0.25, Audiogain=0.0, Manual=0.0,
                Palette=4, Palshift=0.0, Blend=1, Amount=1.0, Colora=(0.95, 0.3, 0.2), Colorb=(0.2, 0.6, 1.0))


# ------------------------------------------------------------------ hist (== gen_interactive_ribbon_hist.glsl)
def hist_step(state, pts, now, speed, epoch, sampleevery, R, L, pointstart, W, H):
    """One cook. state = last output [R + 1, L, 4] or None; pts = [(x, y, vx, vy)] (rack layout, absent x = -10).
    Returns the new state (float64)."""
    np = _np()
    fresh = state is None or state.shape[0] != R + 1 or state.shape[1] != L
    if not fresh:
        m0, m1 = state[R, 0].copy(), state[R, 1].copy()
        fresh = m0[3] != epoch
    if fresh:
        m0 = np.array([L - 1.0, 0.0, now, epoch])
        m1 = np.array([-1e9, 0.0, 0.0, 0.0])
        out = np.zeros((R + 1, L, 4))
    else:
        out = state.copy()
        if m0[2] == now:
            return out
    dt = 0.0 if fresh else min(max(now - m0[2], 0.0), 0.1)
    T = m0[1] + dt * speed
    take = (T - m1[0]) >= max(sampleevery, 0.0) and (fresh or T != m1[0])
    head = int(round(m0[0]))
    if take:
        head = (head + 1) % L
        for r in range(R):
            i = r + pointstart
            q = pts[i] if 0 <= i < len(pts) else (-10.0, -10.0, 0.0, 0.0)
            ok = q[0] > -1.0
            out[r, head] = [q[0] * W if ok else 0.0, q[1] * H if ok else 0.0, T, 1.0 if ok else 0.0]
    out[R, :] = 0.0
    out[R, 0] = [head, T, now, epoch]
    out[R, 1] = [T if take else m1[0], m1[1] + (1.0 if take else 0.0), 0.0, 0.0]
    return out


# ------------------------------------------------------------------ segs (== gen_interactive_ribbon_segs.glsl)
def _smp(hist, i, j, head, n, L):
    if j < 0 or j >= n or j >= L:
        return (0.0, 0.0, 0.0, 0.0)
    k = (head - j) % L
    return tuple(float(v) for v in hist[i, k])


def _speed(hist, i, j, head, n, L):
    a, b = _smp(hist, i, j, head, n, L), _smp(hist, i, j + 1, head, n, L)
    if a[3] < 0.5 or b[3] < 0.5:
        c = _smp(hist, i, j - 1, head, n, L)
        if a[3] > 0.5 and c[3] > 0.5:
            return math.hypot(c[0] - a[0], c[1] - a[1]) / max(c[2] - a[2], 1e-4)
        return 0.0
    return math.hypot(a[0] - b[0], a[1] - b[1]) / max(a[2] - b[2], 1e-4)


def width_law(sp, P):
    r = sp / max(P['Speedref'], 1e-6)
    w = P['Width']
    if P['Widthlaw'] == 1:
        w = P['Width'] * r
    elif P['Widthlaw'] == 2:
        w = P['Width'] / (1.0 + r)
    return min(max(w, P['Widthmin']), max(P['Widthmax'], P['Widthmin']))


def catmull(a, b, c, d, u):
    u2, u3 = u * u, u * u * u
    pos = [0.5 * (2 * b[k] + (c[k] - a[k]) * u + (2 * a[k] - 5 * b[k] + 4 * c[k] - d[k]) * u2
                  + (3 * b[k] - a[k] - 3 * c[k] + d[k]) * u3) for k in (0, 1)]
    tan = [0.5 * ((c[k] - a[k]) + 2 * (2 * a[k] - 5 * b[k] + 4 * c[k] - d[k]) * u
                  + 3 * (3 * b[k] - a[k] - 3 * c[k] + d[k]) * u2) for k in (0, 1)]
    return pos, tan


def segments(hist, P, drive=(0.0, 120.0, 0.0, 0.0), src=None):
    """hist [R + 1, L, 4] -> list of segments {i, s, j, q, p0, p1, w0, w1, a0, a1, rgb} (valid ones only), the
    same numbers the segs pass writes. drive = rack (beats, bpm, level, 0); src = slot input [H, W, 4] (colour mode
    'source')."""
    G = gi()
    gs = G['gs']()
    R, L = hist.shape[0] - 1, hist.shape[1]
    SUB, S = max(int(P['Subdiv']), 1), max(int(P['Strands']), 1)
    m0, m1 = hist[R, 0], hist[R, 1]
    head, T, n = int(round(m0[0])), float(m0[1]), int(round(m1[1]))
    boost = 1.0 + G['env'](drive[0], drive[1], P['Beatgain'], P['Beatdecay']) + \
        G['level'](drive[2], P['Audiogain'], P['Manual'])
    fade = P['Fade']
    out = []
    for i in range(R):
        for s in range(S):
            off = (s - 0.5 * (S - 1)) * P['Spread']
            for j in range(L - 1):
                P1, P2 = _smp(hist, i, j, head, n, L), _smp(hist, i, j + 1, head, n, L)
                if P1[3] < 0.5 or P2[3] < 0.5:
                    continue
                P0, P3 = _smp(hist, i, j - 1, head, n, L), _smp(hist, i, j + 2, head, n, L)
                P0 = P1 if P0[3] < 0.5 else P0
                P3 = P2 if P3[3] < 0.5 else P3
                sp1, sp2 = _speed(hist, i, j, head, n, L), _speed(hist, i, j + 1, head, n, L)
                for q in range(SUB):
                    ends = []
                    for u in (q / float(SUB), (q + 1) / float(SUB)):
                        pos, tan = catmull(P0, P1, P2, P3, u)
                        if tan[0] * tan[0] + tan[1] * tan[1] < 1e-12:
                            tan = [P2[0] - P1[0], P2[1] - P1[1]]
                        t = P1[2] + (P2[2] - P1[2]) * u
                        age = max(T - t, 0.0)
                        al = (min(max(1 - age / fade, 0.0), 1.0) ** max(P['Fadecurve'], 1e-3)) if fade > 0 else 1.0
                        w = width_law(sp1, P) + (width_law(sp2, P) - width_law(sp1, P)) * u
                        if fade > 0:
                            w *= 1.0 + (min(max(1 - age / fade, 0.0), 1.0) - 1.0) * min(max(P['Taper'], 0.0), 1.0)
                        w *= boost
                        tl = max(math.hypot(tan[0], tan[1]), 1e-9)
                        nx, ny = -tan[1] / tl, tan[0] / tl
                        wob = 0.0
                        if P['Wobble'] != 0.0:
                            wob = P['Wobble'] * (2.0 * float(gs['vnoise'](t * P['Wobblefreq'] + T * P['Wobblespeed'],
                                                                          (i * 8 + s) * 7.31, int(P['Seed']) + 3)) - 1.0)
                        o = off * max(w / max(P['Width'], 1e-6), 0.0) + wob
                        ends.append(((pos[0] + nx * o, pos[1] + ny * o), max(w, 0.0), al))
                    (p0, w0, a0), (p1, w1, a1) = ends
                    mode = int(P['Colormode'])
                    um = (q + 0.5) / float(SUB)
                    if mode == 1:
                        key = math.atan2(p1[1] - p0[1], p1[0] - p0[0]) / (2 * math.pi) + 0.5
                    elif mode == 2:
                        key = (T - (P1[2] + (P2[2] - P1[2]) * um)) / fade if fade > 0 else 0.0
                    elif mode == 3:
                        key = (sp1 + (sp2 - sp1) * um) / max(P['Speedref'], 1e-6)
                    else:
                        key = (i + s / float(S)) / max(float(R), 1.0)
                    key *= P['Colourspread']
                    if mode == 4 and src is not None:
                        hh, ww = src.shape[0], src.shape[1]
                        cx = min(max(int(0.5 * (p0[0] + p1[0])), 0), ww - 1)
                        cy = min(max(int(0.5 * (p0[1] + p1[1])), 0), hh - 1)
                        rgb = tuple(float(v) for v in src[cy, cx, :3])
                    else:
                        rgb = tuple(float(v) for v in gs['palette'](_np().array([key]), int(P['Palette']),
                                                                    P['Colora'], P['Colorb'], P['Palshift'])[0])
                    out.append({'g': (i * S + s) * (L - 1) * SUB + j * SUB + q, 'i': i, 's': s, 'j': j, 'q': q, 'p0': p0, 'p1': p1, 'w0': w0, 'w1': w1, 'a0': a0,
                                'a1': a1, 'rgb': rgb})
    return out


# ------------------------------------------------------------------ draw (== gen_interactive_ribbon_draw.glsl)
def shade(x, y, segs, P):
    """Picture (premultiplied rgb, coverage a) of the ribbons at pixel centre (x, y) px."""
    style = int(P['Style'])
    glow, gw, edge = max(P['Glow'], 0.0), max(P['Glowwidth'], 1e-3), max(P['Edge'], 0.0)
    best, bcol, csum, asum, gsum = 0.0, (0.0, 0.0, 0.0), [0.0, 0.0, 0.0], 0.0, [0.0, 0.0, 0.0]
    for sg in segs:
        (ax, ay), (bx, by) = sg['p0'], sg['p1']
        pax, pay, bax, bay = x - ax, y - ay, bx - ax, by - ay
        bb = bax * bax + bay * bay
        h = min(max((pax * bax + pay * bay) / bb, 0.0), 1.0) if bb > 1e-12 else 0.0
        d = math.hypot(pax - bax * h, pay - bay * h)
        sd = d - 0.5 * (sg['w0'] + (sg['w1'] - sg['w0']) * h)
        al = sg['a0'] + (sg['a1'] - sg['a0']) * h
        c = sg['rgb']
        if glow > 0 and sd < 4.5 * gw:
            g = al * glow * math.exp(-max(sd, 0.0) / gw)
            gsum = [gsum[k] + c[k] * g for k in range(3)]
        if style == 2:
            v = al * min(max(0.5 + 0.5 * edge - abs(sd), 0.0), 1.0)
        else:
            v = al * min(max(0.5 - sd, 0.0), 1.0)
        if style == 1:
            csum = [csum[k] + c[k] * v for k in range(3)]
            asum += v
        elif v > best:
            best, bcol = v, c
    lum = 0.2126 * gsum[0] + 0.7152 * gsum[1] + 0.0722 * gsum[2]
    if style == 1:
        return [csum[k] + gsum[k] for k in range(3)], min(max(asum + lum, 0.0), 1.0)
    return [bcol[k] * best + gsum[k] for k in range(3)], min(max(best + lum, 0.0), 1.0)


def draw(base, segs, P, pts_xy, clip=True):
    """rgba at pixel indices [(x, y)] (TD texel coords, y up) over base [H, W, 4] (== the fx pass + gs_blend);
    clip = the 8-bit output's [0, 1] range (fx is `useinput` = 8-bit for the 8-bit background)."""
    np = _np()
    gs = gi()['gs']()
    out = []
    for x, y in pts_xy:
        col, a = shade(x + 0.5, y + 0.5, segs, P)
        b = np.asarray(base[y, x], dtype=np.float64)[None, :]
        out.append(gs['blend'](b, np.array([col]), np.array([a]), int(P['Blend']), P['Amount'])[0])
    out = np.array(out)
    return np.clip(out, 0.0, 1.0) if clip else out


def coverage_area(segs, P, W, H, step=1):
    """Sum of coverage over a W x H pixel grid (the area of the ribbons, px^2) - for the analytic checks."""
    tot = 0.0
    for y in range(0, H, step):
        for x in range(0, W, step):
            tot += shade(x + 0.5, y + 0.5, segs, P)[1] * step * step
    return tot


def shade_grid(xs, ys, segs, P):
    """Vectorised shade() over pixel-centre arrays xs, ys (same shape) -> (rgb [..., 3], a [...])."""
    np = _np()
    x, y = np.asarray(xs, dtype=np.float64), np.asarray(ys, dtype=np.float64)
    style = int(P['Style'])
    glow, gw, edge = max(P['Glow'], 0.0), max(P['Glowwidth'], 1e-3), max(P['Edge'], 0.0)
    best = np.zeros(x.shape)
    bcol = np.zeros(x.shape + (3,))
    csum = np.zeros(x.shape + (3,))
    asum = np.zeros(x.shape)
    gsum = np.zeros(x.shape + (3,))
    for sg in segs:
        (ax, ay), (bx, by) = sg['p0'], sg['p1']
        bax, bay = bx - ax, by - ay
        bb = bax * bax + bay * bay
        pax, pay = x - ax, y - ay
        h = np.clip((pax * bax + pay * bay) / bb, 0.0, 1.0) if bb > 1e-12 else np.zeros(x.shape)
        d = np.hypot(pax - bax * h, pay - bay * h)
        sd = d - 0.5 * (sg['w0'] + (sg['w1'] - sg['w0']) * h)
        al = sg['a0'] + (sg['a1'] - sg['a0']) * h
        c = np.array(sg['rgb'])
        if glow > 0:
            gsum += np.where(sd < 4.5 * gw, al * glow * np.exp(-np.maximum(sd, 0.0) / gw), 0.0)[..., None] * c
        if style == 2:
            v = al * np.clip(0.5 + 0.5 * edge - np.abs(sd), 0.0, 1.0)
        else:
            v = al * np.clip(0.5 - sd, 0.0, 1.0)
        if style == 1:
            csum += v[..., None] * c
            asum += v
        else:
            w = v > best
            best = np.where(w, v, best)
            bcol = np.where(w[..., None], c, bcol)
    lum = gsum[..., 0] * 0.2126 + gsum[..., 1] * 0.7152 + gsum[..., 2] * 0.0722
    if style == 1:
        return csum + gsum, np.clip(asum + lum, 0.0, 1.0)
    return bcol * best[..., None] + gsum, np.clip(best + lum, 0.0, 1.0)


def run(P, frames, pts_fn, W=1080, H=1920, fps=60.0, epoch=1.0):
    """Drive hist_step for `frames` cooks at fps with points pts_fn(k) -> [(x, y, vx, vy)]; returns the history."""
    st = None
    R, L = int(P['Ribbons']), max(4, int(P['Length']))
    for k in range(frames):
        st = hist_step(st, pts_fn(k), 100.0 + k / fps, P['Speed'], epoch, P['Sampleevery'], R, L,
                       int(P['Pointstart']), W, H)
    return st


def chunk_boxes(segs_list, total):
    """== the cbox pass: boxes (min x, min y, max x, max y) of chunks of 256 segment slots (segment slot index g =
    row * SW + x / 3, row-major like the texture); segs_list items carry 'g' = their slot. Empty = (1e9, 1e9, -1e9,
    -1e9)."""
    n = max(1, (total + 255) // 256)
    out = [[1e9, 1e9, -1e9, -1e9] for _ in range(n)]
    for s in segs_list:
        if max(s['a0'], s['a1']) <= 0.0:                   # faded out: the pass skips it too
            continue
        c = s['g'] // 256
        rr = 0.5 * max(s['w0'], s['w1'])
        b = out[c]
        b[0] = min(b[0], s['p0'][0] - rr, s['p1'][0] - rr)
        b[1] = min(b[1], s['p0'][1] - rr, s['p1'][1] - rr)
        b[2] = max(b[2], s['p0'][0] + rr, s['p1'][0] + rr)
        b[3] = max(b[3], s['p0'][1] + rr, s['p1'][1] + rr)
    return out
