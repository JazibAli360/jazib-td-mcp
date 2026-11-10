"""gen_interactive_strings_logic - float64 references of GEN_interactive 'strings' (FX7b TC-28 repelling strings;
lane F, 27 Oct 2026; doc docs/builds/gen_interactive.md "strings"). == builders/glsl/gen_interactive_strings_step.glsl
(step) and gen_interactive_strings_draw.glsl (pixel). Pure (numpy imported inside functions). ASCII only.
P = module par values (menus as index); U = {'now', 'epoch', 'beats', 'bpm', 'level'} rack drive at the cook."""
import math


def rest(s, k, S, K, P, W, H):
    c = P['Margin'] + (s + 0.5) / S * (1.0 - 2.0 * P['Margin'])
    a = k / float(K - 1)
    return (c * W, a * H) if int(P['Orient']) == 0 else (a * W, c * H)


def level(P, U):
    return P['Audiogain'] * U.get('level', 0.0) + P['Manual']


def _bilin_r(img, u, v):
    import numpy as np
    H, W = img.shape[:2]
    x = min(max(u * W - 0.5, 0.0), W - 1.0)
    y = min(max(v * H - 0.5, 0.0), H - 1.0)
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    x1, y1 = min(x0 + 1, W - 1), min(y0 + 1, H - 1)
    fx, fy = x - x0, y - y0
    r = np.asarray(img)[..., 0]
    return (r[y0, x0] * (1 - fx) + r[y0, x1] * fx) * (1 - fy) + (r[y1, x0] * (1 - fx) + r[y1, x1] * fx) * fy


def step(prev, pts, mask, P, U, W, H):
    """One cook: prev (S + 1, K, 4) or None, pts (N, 4) rack points (x y vx vy, absent x = -10), mask (h, w, 4) or
    None -> (S + 1, K, 4)."""
    import numpy as np
    S, K = max(int(P['Strings']), 1), min(max(int(P['Nodes']), 2), 256)
    now, epoch = U['now'], U['epoch']
    fresh = prev is None or prev.shape[:2] != (S + 1, K)
    m0 = np.zeros(4) if fresh else prev[S, 0]
    m1 = np.zeros(4) if fresh else prev[S, 1]
    fresh = fresh or m0[3] != epoch
    same = (not fresh) and m0[2] == now
    dt = 0.0 if (same or fresh) else min(max(now - m0[2], 0.0), 0.1) * P['Speed']
    T = (0.0 if fresh else m0[1]) + dt
    beat = math.floor(U.get('beats', 0.0))
    kick = (not fresh) and (not same) and beat > m1[0]
    out = np.zeros((S + 1, K, 4))
    out[S, 0] = [0.0, T, now, epoch]
    out[S, 1] = [m1[0] if same else beat, 0, 0, 0]
    if fresh:
        return out
    out[:S] = prev[:S]
    if same or dt <= 0:
        return out
    lev = 1.0 + level(P, U)
    side = np.array([1.0, 0.0]) if int(P['Orient']) == 0 else np.array([0.0, 1.0])
    pin = int(P['Pin'])
    n = min(max(int(math.ceil(dt / max(P['Substep'], 1e-4))), 1), 16)
    h = dt / n
    np_ = min(int(P['Pointsused']), 64, len(pts) if pts is not None else 0)
    for s in range(S):
        off = prev[s, :, :2].astype(np.float64).copy()
        vel = prev[s, :, 2:].astype(np.float64).copy()
        P0 = np.array([rest(s, k, S, K, P, W, H) for k in range(K)])
        if kick:
            sg = 1.0 if s % 2 == 0 else -1.0
            vel += side[None, :] * P['Kick'] * lev * sg * np.sin(math.pi * np.arange(K) / (K - 1))[:, None]
        pinned = np.zeros(K, bool)
        if pin < 2:
            pinned[0] = True
        if pin == 1:
            pinned[K - 1] = True
        for _it in range(n):
            o = off.copy()
            lap = np.zeros_like(o)
            lap[1:-1] = o[:-2] + o[2:] - 2 * o[1:-1]
            lap[0] = o[1] - o[0]
            lap[-1] = o[-2] - o[-1]
            Pp = P0 + o
            a = -P['Stiffness'] * o + P['Tension'] * lap - P['Damping'] * vel + np.array([0.0, -P['Gravity']])
            a += side[None, :] * P['Wind'] * np.sin(T * 1.7 + s * 0.9 + np.arange(K) * 0.13)[:, None]
            for i in range(np_):
                q = pts[i]
                if q[0] <= -1.0:
                    continue
                d = Pp - np.array([q[0] * W, q[1] * H])
                r = np.hypot(d[:, 0], d[:, 1])
                ok = (r < P['Radius']) & (r >= 1e-4)
                f = np.where(ok, P['Force'] * lev * (1 - r / P['Radius']) ** 2, 0.0)
                dr = d / np.maximum(r, 1e-12)[:, None]
                md = int(P['Mode'])
                dv = dr if md == 0 else (-dr if md == 1 else np.stack([-dr[:, 1], dr[:, 0]], -1))
                a += f[:, None] * dv
            if P['Maskforce'] != 0 and mask is not None:
                ex, ey = 2.0 / W, 2.0 / H
                g = np.array([[_bilin_r(mask, x / W + ex, y / H) - _bilin_r(mask, x / W - ex, y / H),
                               _bilin_r(mask, x / W, y / H + ey) - _bilin_r(mask, x / W, y / H - ey)] for x, y in Pp])
                a -= P['Maskforce'] * g
            vel = vel + a * h
            off = off + vel * h
            off[pinned] = 0.0
            vel[pinned] = 0.0
        out[s, :, :2] = off
        out[s, :, 2:] = vel
    return out


def pixel(px, py, state, P, W, H):
    """= the draw pass at pixel (px, py) -> (core, glow, t) (colour param before + Flow x T). Every segment (the GPU
    tile list keeps all that can reach the pixel: bounding box + draw extent; glow is 0 beyond 6 Glowwidth)."""
    import numpy as np
    S, K = max(int(P['Strings']), 1), min(max(int(P['Nodes']), 2), 256)
    pc = np.array([px + 0.5, py + 0.5])
    w, gw = max(P['Linewidth'], 0.05), max(P['Glowwidth'], 1e-3)
    best, core, glow, t = 1e30, 0.0, 0.0, 0.0
    R = np.array([[rest(s, k, S, K, P, W, H) for k in range(K)] for s in range(S)])
    X = R + state[:S, :, :2]
    A, Bp = X[:, :-1], X[:, 1:]
    ba = Bp - A
    pa = pc - A
    bb = (ba ** 2).sum(-1)
    hh = np.where(bb > 1e-12, np.clip((pa * ba).sum(-1) / np.maximum(bb, 1e-30), 0, 1), 0.0)
    d = np.hypot(*(pa - ba * hh[..., None]).transpose(2, 0, 1))
    core = float(np.clip(0.5 * w - d + 0.5, 0, 1).max())
    g = np.where(d < 6.0 * gw, P['Glow'] * np.exp(-d / gw), 0.0)
    glow = float(g.max())
    j = int(np.argmin(d))                                     # first minimum = lower segment index on ties
    s, k = j // (K - 1), j % (K - 1)
    h = hh[s, k]
    M = state[s, k] + (state[s, k + 1] - state[s, k]) * h
    cm = int(P['Colourmode'])
    if cm == 0:
        t = (k + h) / float(K - 1)
    elif cm == 1:
        t = math.hypot(M[0], M[1]) / max(P['Bendref'], 1e-3)
    elif cm == 2:
        t = s / float(max(S - 1, 1))
    else:
        t = math.hypot(M[2], M[3]) / max(P['Speedref'], 1e-3)
    return core, glow, t


def look(base, core, glow, t, T, P, palette, blend):
    """Final colour at one pixel: palette(t + Flow T) x (core + glow) blended (gen_sim_logic palette / blend)."""
    import numpy as np
    a = min(max(core + glow, 0.0), 1.0)
    col = palette(np.array(t + P['Flow'] * T), int(P['Palette']), (P['Colorar'], P['Colorag'], P['Colorab']),
                  (P['Colorbr'], P['Colorbg'], P['Colorbb']), P['Palshift']) * (core + glow)
    return blend(np.asarray(base, np.float64), col, np.array(a), int(P['Blend']), P['Amount'])
