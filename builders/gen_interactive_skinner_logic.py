"""gen_interactive_skinner_logic - float64 references of GEN_interactive 'skinner' (FX7c 7C-25 Skinner shards on a
performer; lane F, 27 Oct 2026). == builders/glsl/gen_interactive_skinner_{slots,tris,draw}.glsl. Pure (numpy inside
functions); hash3 = gen_sim_logic.hash3 (== gs_hash3). ASCII only."""
import math
import os
import sys

_B = globals().get('HERE') or os.path.dirname(os.path.abspath(__file__))
if _B not in sys.path:
    sys.path.insert(0, _B)
import gen_sim_logic as _GS  # noqa: E402

hash3 = _GS.hash3


def _h(i, j, s):
    return float(hash3(int(i), int(j), int(s)))


def sample(mask, u, v, ch):
    import numpy as np
    m = np.asarray(mask)
    H, W = m.shape[:2]
    x = min(max(u * W - 0.5, 0.0), W - 1.0)
    y = min(max(v * H - 0.5, 0.0), H - 1.0)
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    x1, y1 = min(x0 + 1, W - 1), min(y0 + 1, H - 1)
    fx, fy = x - x0, y - y0
    c = m[..., ch]
    return float((c[y0, x0] * (1 - fx) + c[y0, x1] * fx) * (1 - fy) + (c[y1, x0] * (1 - fx) + c[y1, x1] * fx) * fy)


def slots_step(prev, mask, P, U, W, H):
    """prev (R + 1, 64, 4) or None, mask (h, w, 4) (None = presence 1, motion 0) -> (R + 1, 64, 4)."""
    import numpy as np
    N = max(int(P['Slots']), 1)
    R = (N + 63) // 64
    now, epoch = U['now'], U['epoch']
    fresh = prev is None or prev.shape[:2] != (R + 1, 64)
    m0 = np.zeros(4) if fresh else prev[R, 0]
    fresh = fresh or m0[3] != epoch
    same = (not fresh) and m0[2] == now
    dt = 0.0 if (same or fresh) else min(max(now - m0[2], 0.0), 0.1) * P['Speed']
    hold = same or ((not fresh) and dt <= 0)
    cnt = m0[0] if hold else (0.0 if fresh else m0[0]) + 1.0
    out = np.zeros((R + 1, 64, 4))
    out[R, 0] = [cnt, (0.0 if fresh else m0[1]) + dt, now, epoch]
    pres = (lambda x, y: 1.0) if mask is None else (lambda x, y: sample(mask, x / W, y / H, 0))
    mot = (lambda x, y: 0.0) if mask is None else (lambda x, y: sample(mask, x / W, y / H, 1))
    c, sd, thr = int(cnt), int(P['Seed']), P['Threshold']
    for i in range(R * 64):
        y, x = i // 64, i % 64
        old = np.zeros(4) if fresh else prev[y, x]
        if i >= N:
            continue
        if hold:
            out[y, x] = old
            continue
        if (not fresh) and old[2] > 0.5 and pres(old[0], old[1]) > thr and _h(i, c, sd) >= P['Respawn'] * dt:
            out[y, x] = [old[0], old[1], 1.0, mot(old[0], old[1])]
            continue
        for t in range(8):
            q = (_h(i, c * 8 + t, sd + 1) * W, _h(i, c * 8 + t, sd + 2) * H)
            if pres(*q) > thr:
                out[y, x] = [q[0], q[1], 1.0, mot(*q)]
                break
    return out


def tris(slots, P):
    """slots (R + 1, 64, 4) -> (ceil(M / 64), 128, 4)."""
    import numpy as np
    M, N = max(int(P['Shards']), 1), max(int(P['Slots']), 1)
    R = (N + 63) // 64
    rows = (M + 63) // 64
    out = np.zeros((rows, 128, 4))
    ok = slots is not None and slots.shape[:2] == (R + 1, 64)
    T = slots[R, 0, 1] if ok else 0.0
    sd = int(P['Seed'])
    S = lambda k: slots[k // 64, k % 64]
    for j in range(M):
        ph = T * P['Rerollhz'] + _h(j, 7, sd)
        ep = int(math.floor(ph))
        f = ph - math.floor(ph)
        A = B = C = np.zeros(4)
        got = False
        for t in range(6):
            if not ok:
                break
            a = min(int(_h(j, ep * 6 + t, sd + 3) * N), N - 1)
            b = min(int(_h(j, ep * 6 + t, sd + 4) * N), N - 1)
            c = min(int(_h(j, ep * 6 + t, sd + 5) * N), N - 1)
            if a == b or b == c or a == c:
                continue
            A, B, C = S(a), S(b), S(c)
            if A[2] < 0.5 or B[2] < 0.5 or C[2] < 0.5:
                continue
            L = max(math.hypot(*(B[:2] - A[:2])), math.hypot(*(C[:2] - B[:2])), math.hypot(*(A[:2] - C[:2])))
            if P['Minlen'] <= L <= P['Maxlen']:
                got = True
                break
        mo = (A[3] + B[3] + C[3]) / 3.0
        show = got and _h(j, ep, sd + 9) < P['Density'] + P['Motiongain'] * mo
        al = math.sin(math.pi * f) if show else 0.0
        out[j // 64, 2 * (j % 64)] = [A[0], A[1], B[0], B[1]]
        out[j // 64, 2 * (j % 64) + 1] = [C[0], C[1], al, _h(j, ep, sd + 11)]
    return out


def _seg(p, a, b):
    pa = (p[0] - a[0], p[1] - a[1])
    ba = (b[0] - a[0], b[1] - a[1])
    bb = ba[0] * ba[0] + ba[1] * ba[1]
    h = min(max((pa[0] * ba[0] + pa[1] * ba[1]) / bb, 0.0), 1.0) if bb > 1e-12 else 0.0
    return math.hypot(pa[0] - ba[0] * h, pa[1] - ba[1] * h)


def pixel(px, py, sh, P):
    """-> (total, colour t) of the draw at pixel (px, py) over every shard (the GPU tile list keeps all that reach)."""
    M = max(int(P['Shards']), 1)
    pc = (px + 0.5, py + 0.5)
    w, gw = max(P['Edgewidth'], 0.05), max(P['Glowwidth'], 1e-3)
    best, bt = 0.0, 0.0
    for j in range(M):
        a, b = sh[j // 64, 2 * (j % 64)], sh[j // 64, 2 * (j % 64) + 1]
        if b[2] <= 0:
            continue
        A, B, C = (a[0], a[1]), (a[2], a[3]), (b[0], b[1])
        ar = (B[0] - A[0]) * (C[1] - A[1]) - (B[1] - A[1]) * (C[0] - A[0])
        if abs(ar) < 1.0:
            continue
        s = 1.0 if ar > 0 else -1.0

        def e(P0, P1):
            ln = max(math.hypot(P1[0] - P0[0], P1[1] - P0[1]), 1e-6)
            return s * ((P1[0] - P0[0]) * (pc[1] - P0[1]) - (P1[1] - P0[1]) * (pc[0] - P0[0])) / ln
        sdi = min(e(A, B), e(B, C), e(C, A))
        d = min(_seg(pc, A, B), _seg(pc, B, C), _seg(pc, C, A))
        fl = P['Fill'] * min(max(sdi + 0.5, 0.0), 1.0) * b[2]
        ed = min(max(0.5 * w - d + 0.5, 0.0), 1.0) * b[2]
        gl = P['Glow'] * math.exp(-d / gw) * b[2] if d < 6.0 * gw else 0.0
        tot = fl + ed + gl
        if tot > best:
            best, bt = tot, b[3]
    return best, bt


def look(base, best, t, P, palette, blend):
    import numpy as np
    col = palette(np.array(t), int(P['Palette']), (P['Colorar'], P['Colorag'], P['Colorab']),
                  (P['Colorbr'], P['Colorbg'], P['Colorbb']), P['Palshift']) * best
    return blend(np.asarray(base, np.float64), col, np.array(min(max(best, 0.0), 1.0)), int(P['Blend']), P['Amount'])
