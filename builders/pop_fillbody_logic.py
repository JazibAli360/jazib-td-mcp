# pop_fillbody_logic - numpy mirror of POP_fillbody (lane H TC-15; builder builders/pop_fillbody.py, doc
# docs/builds/pop_lane_h.md "TC-15"): the procedural dancer pose (12 capsules), the capsule table the `caps` pass writes,
# the union-of-capsules SDF and the particle step. Runs OUTSIDE TD (T-184). Hash / value noise come from
# pop_collide_logic (one copy, shared with TC-14). Every function matches the GLSL in pop_fillbody.py. ASCII only.
import math

import numpy as np

from pop_collide_logic import TAU, h1, vnoise, side_of, COUNT_CAP  # noqa: F401

MAXCAPS = 16           # GLSL #define MAXCAPS (caps texture 16 x 2)
TRIES = 32             # GLSL #define TRIES (rejection sampling at spawn)
SUBSTEPS_MAX = 4
EPS = 1e-3             # central-difference step of the SDF gradient
BODYSRC = ['dancer', 'chop']
DANCER_CAPS = 12

DEFAULTS = {'count': 16384, 'dt': 1.0 / 60.0, 'substeps': 2, 'time': 0.0, 'reset': 0, 'seed': 1,
            'wander': 1.5, 'wanderfreq': 6.0, 'damp': 2.0, 'margin': 0.004, 'respawn': 0.02,
            'tb': 0.0, 'pose': 1.0, 'origin': (0.0, 0.04, 0.0), 'scale': 0.9}


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


def _v(x, y, z):
    return np.array([x, y, z], dtype=np.float64)


def dancer(t, amt):
    """Joint maths of the dancer at body time t (s), Pose amount amt -> list of 12 (a, b, r) capsules (units: frame
    height 1, before Body origin / scale). Same order as the GLSL dancer()."""
    ph = TAU * t
    sw, cw, s2 = math.sin(ph), math.cos(ph), math.sin(2.0 * ph)
    pelvis = _v(0.05 * amt * sw, -0.08 + 0.015 * amt * s2, 0.0)
    neck = pelvis + _v(0.03 * amt * math.sin(ph + 0.6), 0.27, 0.02 * amt * cw)
    head = neck + _v(0.01 * amt * sw, 0.085, 0.0)
    shl, shr = neck + _v(-0.085, -0.025, 0.0), neck + _v(0.085, -0.025, 0.0)
    al = 0.3 + amt * (1.3 + 1.0 * math.sin(ph))
    ar = 0.3 + amt * (1.3 + 1.0 * math.sin(ph + 3.14159))
    el = shl + 0.14 * _v(-math.sin(al), -math.cos(al), 0.15 * amt * cw)
    er = shr + 0.14 * _v(math.sin(ar), -math.cos(ar), -0.15 * amt * cw)
    fl = al + 0.4 + 0.8 * amt * (0.5 + 0.5 * math.sin(2.0 * ph))
    fr = ar + 0.4 + 0.8 * amt * (0.5 + 0.5 * math.sin(2.0 * ph + 1.0))
    hdl = el + 0.13 * _v(-math.sin(fl), -math.cos(fl), 0.0)
    hdr = er + 0.13 * _v(math.sin(fr), -math.cos(fr), 0.0)
    hl, hr = pelvis + _v(-0.06, -0.02, 0.0), pelvis + _v(0.06, -0.02, 0.0)
    kl_, kr_ = amt * 0.35 * max(sw, 0.0), amt * 0.35 * max(-sw, 0.0)
    ll, lr = 0.08 + kl_, 0.08 + kr_
    knl = hl + 0.2 * _v(-math.sin(ll), -math.cos(ll), 0.3 * amt * max(sw, 0.0))
    knr = hr + 0.2 * _v(math.sin(lr), -math.cos(lr), 0.3 * amt * max(-sw, 0.0))
    ftl = knl + 0.2 * _v(-math.sin(ll * 0.3), -math.cos(ll * 0.3), -0.2 * amt * max(sw, 0.0))
    ftr = knr + 0.2 * _v(math.sin(lr * 0.3), -math.cos(lr * 0.3), -0.2 * amt * max(-sw, 0.0))
    return [(pelvis, neck, 0.075), (head, head, 0.065), (shl, shr, 0.035), (hl, hr, 0.05),
            (shl, el, 0.035), (shr, er, 0.035), (el, hdl, 0.028), (er, hdr, 0.028),
            (hl, knl, 0.05), (hr, knr, 0.05), (knl, ftl, 0.04), (knr, ftr, 0.04)]


def caps_table(p, chop_rows=None):
    """The `caps` texture (MAXCAPS x 2 rgba32f): row 0 = (a.xyz, r), row 1 = (b.xyz, valid). chop_rows = (2K, 4)
    samples x y z w (sample 2k = a + r, 2k + 1 = b) when Bodysrc = chop. Body origin / scale applied to both."""
    A, B = np.zeros((MAXCAPS, 4)), np.zeros((MAXCAPS, 4))
    if chop_rows is None:
        caps = [(a, b, r) for a, b, r in dancer(p['tb'], p['pose'])]
    else:
        rows = np.asarray(chop_rows, dtype=np.float64)
        caps = [(rows[2 * k, :3], rows[2 * k + 1, :3], rows[2 * k, 3]) for k in range(min(MAXCAPS, len(rows) // 2))]
    o, s = np.array(p['origin']), p['scale']
    for k, (a, b, r) in enumerate(caps):
        A[k] = [*(o + s * np.asarray(a)), r * s]
        B[k] = [*(o + s * np.asarray(b)), 1.0]
    return A, B


def sdf(P3, A, B, nc):
    """Union of capsules at points P3 (N, 3); capsules k < nc with valid flag."""
    d = np.full(P3.shape[0], 1e9)
    for k in range(min(nc, MAXCAPS)):
        if B[k, 3] < 0.5:
            continue
        a, b, r = A[k, :3], B[k, :3], A[k, 3]
        ba = b - a
        pa = P3 - a
        hh = np.clip((pa @ ba) / max(ba @ ba, 1e-12), 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(pa - hh[:, None] * ba, axis=-1) - r)
    return d


def grad(P3, A, B, nc):
    g = np.zeros_like(P3)
    for ax in range(3):
        e = np.zeros(3)
        e[ax] = EPS
        g[:, ax] = sdf(P3 + e, A, B, nc) - sdf(P3 - e, A, B, nc)
    L = np.linalg.norm(g, axis=-1, keepdims=True)
    return np.where(L > 1e-12, g / np.maximum(L, 1e-12), 0.0)


def bbox(A, B, nc):
    lo, hi = np.full(3, 1e9), np.full(3, -1e9)
    for k in range(min(nc, MAXCAPS)):
        if B[k, 3] < 0.5:
            continue
        r = A[k, 3]
        lo = np.minimum(lo, np.minimum(A[k, :3], B[k, :3]) - r)
        hi = np.maximum(hi, np.maximum(A[k, :3], B[k, :3]) + r)
    return lo, hi


def cap_sdf(P3, A, B, k):
    """Distance to capsule k alone (per point: k is an int array) and the outward unit normal (analytic)."""
    a, b, r = A[k, :3], B[k, :3], A[k, 3]
    ba = b - a
    pa = P3 - a
    hh = np.clip((pa * ba).sum(-1) / np.maximum((ba * ba).sum(-1), 1e-12), 0.0, 1.0)
    e = pa - hh[:, None] * ba
    L = np.linalg.norm(e, axis=-1)
    nrm = np.where(L[:, None] > 1e-12, e / np.maximum(L, 1e-12)[:, None], 0.0)
    return L - r, nrm


def owner(P3, A, B, nc):
    """Capsule a point belongs to = the one with the smallest own distance (first on ties), as the GLSL loop."""
    best, kk = np.full(P3.shape[0], 1e9), np.zeros(P3.shape[0], dtype=np.int64)
    for k in range(min(nc, MAXCAPS)):
        if B[k, 3] < 0.5:
            continue
        d, _ = cap_sdf(P3, A, B, np.full(P3.shape[0], k))
        m = d < best
        best[m], kk[m] = d[m], k
    return kk


def spawn(i, s, A, B, nc, margin):
    """Rejection sampling inside the body (TRIES per particle, bounded); fallback = point a of capsule i % nc.
    -> pos, capsule (the owner of the spawn point: the particle stays bound to it, 27 Oct polish)."""
    i = np.asarray(i, dtype=np.int64)
    lo, hi = bbox(A, B, nc)
    pos = A[i % max(nc, 1), :3].copy()
    cap = i % max(nc, 1)
    done = np.zeros(len(i), dtype=bool)
    for k in range(TRIES):
        q = np.stack([h1(i * 64 + 3 * k + j, s) for j in range(3)], -1)
        q = lo + (hi - lo) * q
        ok = (~done) & (sdf(q, A, B, nc) < -margin)
        pos[ok] = q[ok]
        done |= ok
    cap[done] = owner(pos[done], A, B, nc)
    return pos, cap


def step(P, V, A, B, p):
    """One state cook on float64 copies. P (N,4) = pos + (capsule + phase), V (N,4) = vel + steps (0 = needs spawn).
    P.w = k + phase (phase 0.5..1): k = the capsule the particle was born in; it is kept inside THAT capsule (was: the
    nearest one, which drained the swarm into the feet while dancing, 27 Oct look finding). A k that is no longer a
    valid capsule respawns."""
    P, V = P.copy(), V.copy()
    N = P.shape[0]
    nc = int(p['ncaps'])
    n = min(int(p['count']), N)
    idx = np.arange(N)
    dead = idx >= n
    if p['reset']:
        V[:, 3] = 0.0
    badm = ~np.isfinite(P).all(-1) | ~np.isfinite(V).all(-1)
    P[badm] = 0.0
    V[badm] = 0.0
    steps = np.floor(V[:, 3] + 0.5).astype(np.int64)
    resp = h1(idx, steps * 7919 + int(p['seed']) + 3) < p['respawn'] * p['dt']
    kc = np.floor(P[:, 3]).astype(np.int64)
    lost = (kc < 0) | (kc >= min(nc, MAXCAPS))
    lost[~lost] = B[kc[~lost], 3] < 0.5
    sp = (~dead) & ((V[:, 3] < 0.5) | resp | lost)
    if sp.any():
        s = int(p['seed']) * 7919 + steps[sp]
        pos = np.zeros((sp.sum(), 3))
        cap = np.zeros(sp.sum(), dtype=np.int64)
        for u in np.unique(s):                         # per-seed batches (spawn() takes one seed)
            mk = s == u
            pos[mk], cap[mk] = spawn(idx[sp][mk], int(u), A, B, nc, p['margin'])
        P[sp, :3] = pos
        P[sp, 3] = cap + 0.5 + 0.5 * h1(idx[sp], int(p['seed']) + 11)   # capsule + phase 0.5..1 (> 0 = drawn)
        V[sp, :3] = 0.0
        V[sp, 3] = np.floor(V[sp, 3] + 0.5) + 1.0
    run = (~dead) & ~sp
    P[dead] = [0.0, -1000.0, 0.0, -1.0]
    V[dead] = 0.0
    if run.any():
        p3, v3 = P[run, :3], V[run, :3]
        kr = np.floor(P[run, 3]).astype(np.int64)
        nsub = max(1, min(int(p['substeps']), SUBSTEPS_MAX))
        h = p['dt'] / nsub
        t, F, sd = p['time'], p['wanderfreq'], int(p['seed'])
        for _ in range(nsub):
            w = np.stack([vnoise(p3[:, 1] * F + t * 0.3, p3[:, 2] * F, sd) - 0.5,
                          vnoise(p3[:, 2] * F + 13.1, p3[:, 0] * F + t * 0.3, sd) - 0.5,
                          vnoise(p3[:, 0] * F + t * 0.3, p3[:, 1] * F + 27.7, sd) - 0.5], -1)
            v3 = v3 + 2.0 * p['wander'] * w * h
            v3 = v3 * max(1.0 - p['damp'] * h, 0.0)
            p3 = p3 + v3 * h
            d, nrm = cap_sdf(p3, A, B, kr)                 # own capsule, analytic normal
            out = d > -p['margin']
            if out.any():
                nrm = nrm[out]
                p3[out] = p3[out] - nrm * (d[out] + p['margin'])[:, None]
                vn = (v3[out] * nrm).sum(-1)
                v3[out] = v3[out] - np.maximum(vn, 0.0)[:, None] * nrm
        P[run, :3], V[run, :3] = p3, v3
        V[run, 3] += 1.0
    return P, V


def run(p, frames, chop_rows=None, dance=0.0):
    """Reset + frames cooks; the body time advances by dance x dt per cook (0 = frozen pose)."""
    s = side_of(p['count'])
    P, V = np.zeros((s * s, 4)), np.zeros((s * s, 4))
    q = dict(p)
    for f in range(frames + 1):
        q['tb'] = p['tb'] + dance * f * p['dt']
        q['time'] = f * p['dt']
        A, B = caps_table(q, chop_rows)
        q['ncaps'] = DANCER_CAPS if chop_rows is None else min(MAXCAPS, len(chop_rows) // 2)
        P, V = step(P, V, A, B, dict(q, reset=1 if f == 0 else 0))
    return P, V, A, B, q['ncaps']


def inside_fraction(P, A, B, nc, count):
    live = P[:count]
    return float((sdf(live[:, :3], A, B, nc) <= 0.0).mean())
