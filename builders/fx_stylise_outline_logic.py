"""fx_stylise_outline_logic - numpy mirror of FX_stylise 'outline' (builders/fx_stylise_outline.py). Pure: no td.
Images are (H, W, 4) float arrays, row 0 = bottom (TD numpyArray order, = the compute shader's p.y).
  seed_map(img, D, thr, matte, inv)  == the seed pass (JFA seeds at the box-mean matte crossings)
  jfa(seedmap, extra)                == builders/glsl/gen_sim_vor_jfa.glsl (gen_sim_logic.jfa, the same file's mirror)
  brute(seedmap)                     exact nearest-seed distance per texel (for the JFA error check)
  signed_distance(img, jf, D, ...)   == the fx pass's sd (2x2 nearest seeds, sign from the full-res matte)
  look(img, sd, P)                   == the fx pass's look with Colsrc solid (palette: palette_map_logic.colsrc_eval)
ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import gen_sim_logic  # noqa: E402

MODES = ['outline', 'halo', 'contour', 'sticker', 'distance']
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def matte(img, mt=0, inv=0):
    img = np.asarray(img, np.float32)
    if mt == 1:
        m = img[..., 3]
    elif mt == 2:
        m = img[..., :3].max(-1)
    else:
        m = img[..., :3] @ LUMA
    return (1.0 - m) if inv else m


def cell_means(img, D, mt=0, inv=0):
    """== cellM: matte of the D x D block's mean colour (GPU: one bilinear tap per 2x2 at its shared corner; blocks
    past the edge clamp to the last pixel, = inputextenduv hold)."""
    img = np.asarray(img, np.float32)
    H, W = img.shape[:2]
    JH, JW = -(-H // D), -(-W // D)
    acc = np.zeros((JH, JW, img.shape[2]), np.float32)
    for y in range(D):
        for x in range(D):
            ys = np.minimum(np.arange(JH) * D + y, H - 1)
            xs = np.minimum(np.arange(JW) * D + x, W - 1)
            acc += img[np.ix_(ys, xs)]
    return matte(acc / np.float32(D * D), mt, inv)


def jfa_passes_for(JW, JH, rng_px, D):
    """== PM: passes the look needs: min(full, ceil(log2(range / D + 2)))."""
    full = gen_sim_logic.jfa_passes(JW, JH)
    return min(full, max(1, int(math.ceil(math.log2(min(rng_px, 1e7) / D + 2)))))


def look_range(P):
    """== RANGE (full px) the look reaches from the edge."""
    if P.get('Maxdist', 0) > 0:
        return P['Maxdist']
    m = P['Mode']
    c = (P['Spacing'] * (P['Bands'] + 1) if P['Bands'] > 0 else 1e9) if m == 2 else 0
    return (abs(P['Offset']) + P['Soft'] + P.get('Wobble', 0) + 2 + (1 + P.get('Pulsegain', 1)) *
            max(P['Width'], 6 * P['Glow'] if m == 1 else 0, c, 1e9 if m == 4 else 0))


def jfa_pm(seedmap, Pm, extra=1):
    """gen_sim_vor_jfa.glsl with an explicit Pm (uJ.z): Pm + extra passes, steps 2^(Pm-1) .. 1, then 1."""
    H, W = seedmap.shape[:2]
    full = gen_sim_logic.jfa_passes(W, H)
    if Pm >= full:
        return gen_sim_logic.jfa(seedmap, extra=extra)
    old = gen_sim_logic.jfa_passes
    try:
        gen_sim_logic.jfa_passes = lambda w, h: Pm
        return gen_sim_logic.jfa(seedmap, extra=extra)
    finally:
        gen_sim_logic.jfa_passes = old


def seed_map(img, D=2, thr=0.5, mt=0, inv=0):
    m0 = cell_means(img, D, mt, inv)
    JH, JW = m0.shape
    out = np.zeros((JH, JW, 4), np.float32)
    bt = np.full((JH, JW), 2.0, np.float32)
    bp = np.zeros((JH, JW, 2), np.float32)
    py, px = np.mgrid[0:JH, 0:JW].astype(np.float32)
    inside = m0 > thr
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        m1 = np.full((JH, JW), np.inf, np.float32)               # out of bounds: never an outside neighbour
        ys, yd = (slice(dy, JH), slice(0, JH - dy)) if dy >= 0 else (slice(0, JH + dy), slice(-dy, JH))
        xs, xd = (slice(dx, JW), slice(0, JW - dx)) if dx >= 0 else (slice(0, JW + dx), slice(-dx, JW))
        m1[yd, xd] = m0[ys, xs]
        ok = inside & (m1 <= thr)
        t = (m0 - thr) / np.maximum(m0 - np.where(np.isfinite(m1), m1, 0), 1e-6)
        upd = ok & (t < bt)
        bt = np.where(upd, t, bt)
        bp[..., 0] = np.where(upd, px + 0.5 + t * dx, bp[..., 0])
        bp[..., 1] = np.where(upd, py + 0.5 + t * dy, bp[..., 1])
    has = bt < 2.0
    out[has, 0] = bp[has, 0]
    out[has, 1] = bp[has, 1]
    out[has, 2] = 1.0
    out[has, 3] = 1.0
    return out


def jfa(seedmap, extra=1):
    return gen_sim_logic.jfa(seedmap, extra=extra)


def jfa_dist(jf):
    """Distance (texels) from each texel centre to the seed the JFA picked (inf where none)."""
    H, W = jf.shape[:2]
    py, px = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
    d = np.hypot(px - jf[..., 0], py - jf[..., 1])
    return np.where(jf[..., 2] > 0, d, np.inf)


def brute(seedmap):
    """Exact distance from each texel centre to the nearest seed point (inf when there is none)."""
    H, W = seedmap.shape[:2]
    pts = seedmap[seedmap[..., 2] > 0][:, :2].astype(np.float64)
    if len(pts) == 0:
        return np.full((H, W), np.inf)
    py, px = np.mgrid[0:H, 0:W].astype(np.float64) + 0.5
    q = np.stack([px.ravel(), py.ravel()], -1)
    best = np.full(len(q), np.inf)
    for i in range(0, len(pts), 256):
        P = pts[i:i + 256]
        d2 = ((q[:, None, :] - P[None, :, :]) ** 2).sum(-1)
        best = np.minimum(best, d2.min(1))
    return np.sqrt(best).reshape(H, W)


def signed_distance(img, jf, D, thr=0.5, mt=0, inv=0):
    """== fx: nearest seed among the 2x2 JFA texels around each full pixel; x D; sign from the full-res matte."""
    H, W = img.shape[:2]
    JH, JW = jf.shape[:2]
    py, px = np.mgrid[0:H, 0:W].astype(np.float32)
    qx, qy = (px + 0.5) / D, (py + 0.5) / D
    bx, by = np.floor(qx - 0.5).astype(int), np.floor(qy - 0.5).astype(int)
    bd = np.full((H, W), 1e30, np.float32)
    for j in (0, 1):
        for i in (0, 1):
            tx, ty = np.clip(bx + i, 0, JW - 1), np.clip(by + j, 0, JH - 1)
            s = jf[ty, tx]
            e2 = (qx - s[..., 0]) ** 2 + (qy - s[..., 1]) ** 2
            bd = np.where((s[..., 2] > 0) & (e2 < bd), e2, bd)
    d = np.where(bd < 1e29, np.sqrt(bd) * D, 1e6).astype(np.float32)
    ins = matte(img, mt, inv) > thr
    return np.where(ins, -d, d), ins


def _band(x, w, soft):
    lo, hi = 0.5 * (w - soft), 0.5 * (w + soft)
    t = np.clip((np.abs(x) - lo) / max(hi - lo, 1e-9), 0, 1)
    return 1.0 - t * t * (3 - 2 * t)


def _smooth(a, b, x):
    t = np.clip((x - a) / max(b - a, 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


def _base(k, c, dim):
    if k == 1:
        return c * dim
    if k == 2:
        z = np.zeros_like(c)
        z[..., 3] = 1
        return z
    if k == 3:
        return np.zeros_like(c)
    return c


def look(img, sd, ins, P):
    """== fx look for Colsrc solid, Wobble 0. P: dict with the module par values (menus as indices)."""
    c = np.asarray(img, np.float32)
    amt = P.get('Amount', 1.0)
    if amt <= 0:
        return c.copy()
    S = 1.0 + P.get('Pulse', 0.0) * P.get('Pulsegain', 1.0)
    W, off, soft, I = P['Width'] * S, P['Offset'], max(P['Soft'], 1e-3), P['Intensity'] * S
    mode = P['Mode']
    a = np.zeros(sd.shape, np.float32)
    inCov = ins.astype(np.float32)
    if mode == 0:
        a = _band(sd - off, W, soft)
    elif mode == 1:
        e = sd - off
        a = _band(e, W, soft) + np.where(e > 0, np.exp(-np.maximum(e, 0) / max(P['Glow'] * S, 1e-3)) * P['Glowgain'], 0)
    elif mode == 2:
        dr = P['Direction']
        u = (sd if dr == 0 else (-sd if dr == 1 else np.abs(sd))) - off
        sp = max(P['Spacing'], 1e-3)
        ph = u / sp - P.get('_phase', 0.0)
        f = ph - np.floor(ph)
        fn = P['Function']
        if fn == 0:
            a = _band(np.minimum(f, 1 - f) * sp, W, soft)
        else:
            a = (1 - f) if fn == 1 else ((1 - np.abs(2 * f - 1)) if fn == 2 else 0.5 + 0.5 * np.cos(6.2831853 * f))
            a = a * (f <= 1 - P['Gap'])
        if P['Bands'] > 0:
            fd = P['Fade']
            x = u / sp + (0.5 if fn == 0 else 0.0)
            a = a * (1 - np.clip((x - (P['Bands'] - fd)) / max(fd, 1e-3), 0, 1))
        a = np.where(u >= 0, a, 0)
    elif mode == 3:
        e = sd - off
        a = 1 - _smooth(W - 0.5 * soft, W + 0.5 * soft, e)
        inCov = 1 - _smooth(-0.5 * soft, 0.5 * soft, sd)
    if mode == 4:
        sc = max(P['Spacing'] * max(P['Bands'], 1), 1)
        g = np.clip(0.5 + 0.5 * sd / sc, 0, 1)
        o = np.stack([g, g, g, np.ones_like(g)], -1)
    else:
        a = a.astype(np.float32)
        ic = inCov[..., None]
        base = _base(P['Back'], c, P['Backdim']) * (1 - ic) + _base(P['Inside'], c, P['Backdim']) * ic
        C = np.array([P['Colr'], P['Colg'], P['Colb']], np.float32) * I
        cov = np.clip(a, 0, 1)[..., None]
        if mode == 3:
            st = np.concatenate([C * cov, cov], -1) + base * (1 - cov)
            o = st * (1 - ic) + _base(P['Inside'], c, P['Backdim']) * ic
        elif P['Blend'] == 1:
            o = np.concatenate([base[..., :3] + C * a[..., None], np.maximum(base[..., 3:], cov)], -1)
        else:
            o = np.concatenate([C * cov + base[..., :3] * (1 - cov), cov + base[..., 3:] * (1 - cov)], -1)
    return c + (o - c) * amt


def reference(img, P, extra=1):
    """Whole module (Colsrc solid, Wobble 0): -> (out, sd, jfa texture)."""
    D = {0: 1, 1: 2, 2: 4}[P['Res']]
    sm = seed_map(img, D, P['Threshold'], P['Matte'], P['Invert'])
    jf = jfa_pm(sm, jfa_passes_for(sm.shape[1], sm.shape[0], look_range(P), D), extra)
    sd, ins = signed_distance(img, jf, D, P['Threshold'], P['Matte'], P['Invert'])
    return look(img, sd, ins, P), sd, jf


def disc_matte(W, H, cx, cy, r, soft=1.0):
    """Test picture: white disc (anti-aliased) on black, alpha 1."""
    py, px = np.mgrid[0:H, 0:W].astype(np.float32) + 0.5
    d = np.hypot(px - cx, py - cy) - r
    v = np.clip(0.5 - d / soft, 0, 1)
    img = np.ones((H, W, 4), np.float32)
    img[..., 0] = img[..., 1] = img[..., 2] = v
    return img


def pm_check(img):
    """Premultiplied: rgb <= alpha everywhere (within 8-bit rounding) when the look writes no HDR colour."""
    return float(np.max(img[..., :3].max(-1) - img[..., 3]))


def compare(a, b, tol=2.0 / 255):
    d = np.abs(np.asarray(a, np.float64) - np.asarray(b, np.float64))
    return {'max': float(d.max()), 'mean': float(d.mean()), 'over_tol': float((d.max(-1) > tol).mean())}


if __name__ == '__main__':                                   # quick self check
    im = disc_matte(96, 64, 40.3, 30.7, 18.0)
    sm = seed_map(im, 2)
    e = np.abs(jfa_dist(jfa(sm)) - brute(sm))
    print('seeds', int((sm[..., 2] > 0).sum()), 'jfa max err', float(e[np.isfinite(e)].max()), math.pi)
