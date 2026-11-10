# pop_linegrowth_logic - numpy mirror of POP_linegrowth (TC-09 differential line growth; builder
# builders/pop_linegrowth.py, doc docs/builds/pop_lane_h.md "TC-09"). Same algorithm as the two compute passes:
# `forces` (seed / spring / align / brute-force repulsion / boundary / jitter / step clamp) then `insert` (split
# flags, exclusive scan, budgeted midpoint insertion). Runs OUTSIDE TD (T-184). dtype float32 follows the GPU closely
# (sum order differs, so long runs drift: compare statistics after ~60 frames). ASCII only.
import math

import numpy as np

from pop_scan import exclusive_scan

NW = 128            # state texture width
NROWS = 64          # node rows (count texel at row NROWS)
MAXN = NW * NROWS   # 8192 hard cap
CHUNK = MAXN // 1024
SHAPES = ['circle', 'polygon', 'line']
TAU = 6.283185307179586
M32 = 0xFFFFFFFF

DEFAULTS = {'shape': 'circle', 'seedcount': 64, 'seedradius': 0.1, 'sides': 5, 'maxnodes': 1024,
            'rest': 0.006, 'maxedge': 0.009, 'radius': 0.02, 'dt': 0.5,
            'spring': 0.5, 'align': 0.2, 'repel': 0.02, 'jitter': 0.1,
            'bound': 0.45, 'boundk': 1.0, 'maxstep': 0.003, 'seed': 1, 'play': 1}


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


def lowbias(x):
    x = np.asarray(x, dtype=np.uint64) & M32
    x ^= x >> np.uint64(16)
    x = (x * np.uint64(0x7feb352d)) & M32
    x ^= x >> np.uint64(15)
    x = (x * np.uint64(0x846ca68b)) & M32
    x ^= x >> np.uint64(16)
    return x


def hh(i, s):
    """GLSL hh(uint i, uint s) = float(lowbias(i * 747796405u + s * 2891336453u + 1u) >> 8) / 16777216.0"""
    i = np.asarray(i, dtype=np.int64).astype(np.uint64) & M32
    s = np.uint64(int(s) & M32)
    h = lowbias((i * np.uint64(747796405) + s * np.uint64(2891336453) + np.uint64(1)) & M32)
    return (h >> np.uint64(8)).astype(np.float64) / 16777216.0


def closed(p):
    return (SHAPES.index(p['shape']) if isinstance(p['shape'], str) else int(p['shape'])) != 2


def maxn(p):
    return int(min(max(int(p['maxnodes']), 3), MAXN))


def seed_nodes(p):
    n = int(min(max(int(p['seedcount']), 3), maxn(p)))
    i = np.arange(n, dtype=np.float64)
    R = p['seedradius']
    m = SHAPES.index(p['shape']) if isinstance(p['shape'], str) else int(p['shape'])
    if m == 0:
        a = TAU * i / n
        P = np.stack([R * np.cos(a), R * np.sin(a)], -1)
    elif m == 1:
        sides = max(int(p['sides']), 3)
        s = i / n * sides
        k = np.floor(s)
        f = (s - k)[:, None]
        a0 = TAU * k / sides + math.pi / 2
        a1 = TAU * (k + 1) / sides + math.pi / 2
        v0 = np.stack([R * np.cos(a0), R * np.sin(a0)], -1)
        v1 = np.stack([R * np.cos(a1), R * np.sin(a1)], -1)
        P = v0 + (v1 - v0) * f
    else:
        P = np.stack([-R + 2 * R * i / (n - 1), np.zeros(n)], -1)
    return P, n


def _salt(p, frame, axis):
    return (int(p['seed']) * 65537 + int(frame) * 2 + axis) & M32


def forces(P, cnt, frame, p, dtype=np.float64):
    """One `forces` step for nodes 0..cnt-1 (P: cnt x 2). Returns the new positions (cnt x 2)."""
    P = np.asarray(P, dtype=dtype)[:cnt]
    if not p['play']:
        return P.copy()
    n = cnt
    idx = np.arange(n)
    cl = closed(p)
    ia = (idx - 1) % n if cl else np.maximum(idx - 1, 0)
    ib = (idx + 1) % n if cl else np.minimum(idx + 1, n - 1)
    f = np.zeros_like(P)
    for nb in (ia, ib):
        d = P[nb] - P
        L = np.linalg.norm(d, axis=-1)
        ok = (nb != idx) & (L > 1e-9)
        Ls = np.where(ok, L, 1.0)
        f += np.where(ok[:, None], p['spring'] * (Ls - p['rest'])[:, None] * d / Ls[:, None], 0)
    inner = np.ones(n, bool) if cl else (idx > 0) & (idx < n - 1)
    f += np.where(inner[:, None], p['align'] * (0.5 * (P[ia] + P[ib]) - P), 0)
    D = P[:, None, :] - P[None, :, :]
    r = np.linalg.norm(D, axis=-1)
    ok = (r < p['radius']) & (r > 1e-9)
    np.fill_diagonal(ok, False)
    rs = np.where(ok, r, 1.0)
    w = np.where(ok, p['repel'] * (p['radius'] - rs) / p['radius'] / rs, 0.0)
    f += (w[:, :, None] * D).sum(1)
    L = np.linalg.norm(P, axis=-1)
    out = L > p['bound']
    Ls = np.where(out, L, 1.0)
    f -= np.where(out[:, None], p['boundk'] * (Ls - p['bound'])[:, None] * P / Ls[:, None], 0)
    jx = (hh(idx, _salt(p, frame, 0)) - 0.5) * 2.0
    jy = (hh(idx, _salt(p, frame, 1)) - 0.5) * 2.0
    dp = p['dt'] * f + p['jitter'] * p['rest'] * np.stack([jx, jy], -1)
    dl = np.linalg.norm(dp, axis=-1)
    sc = np.where(dl > p['maxstep'], p['maxstep'] / np.maximum(dl, 1e-30), 1.0)
    return (P + dp * sc[:, None]).astype(dtype)


def split_flags(P, cnt, p):
    if not p['play']:
        return np.zeros(cnt, bool)
    idx = np.arange(cnt)
    nxt = (idx + 1) % cnt
    e = np.linalg.norm(P[nxt] - P[idx], axis=-1)
    fl = e > p['maxedge']
    if not closed(p):
        fl[cnt - 1] = False
    return fl


def insert(P, cnt, p):
    """`insert`: accepted splits = the first (maxnodes - cnt) flags in index order; node i -> i + accepted before it,
    accepted split -> midpoint at the next index. Returns (P2, newcnt). Uses the per-thread chunk scan of the GPU."""
    P = np.asarray(P)[:cnt]
    fl = split_flags(P, cnt, p).astype(np.int64)
    budget = max(maxn(p) - cnt, 0)
    full = np.zeros(MAXN, np.int64)
    full[:cnt] = fl
    loc = full.reshape(1024, CHUNK).sum(1)                 # per-thread chunk sums (same as the shader)
    pre_t, total = exclusive_scan(loc)
    pre = np.repeat(pre_t, CHUNK) + np.concatenate([np.zeros((1024, 1), np.int64),
                                                    np.cumsum(full.reshape(1024, CHUNK), 1)[:, :-1]], 1).ravel()
    pre = pre[:cnt]
    acc = np.minimum(pre, budget)
    newcnt = cnt + min(total, budget)
    out = np.zeros((newcnt, 2), P.dtype)
    dst = np.arange(cnt) + acc
    out[dst] = P
    take = (fl > 0) & (pre < budget)
    nxt = (np.arange(cnt) + 1) % cnt
    out[dst[take] + 1] = 0.5 * (P[take] + P[nxt[take]])
    return out, int(newcnt)


def run(frames, p, dtype=np.float64):
    """Frame 0 seeds (forces pass with count 0) then insert; every next frame forces + insert. Returns (P, counts)."""
    P, cnt = seed_nodes(p)
    P = P.astype(dtype)
    counts = []
    for fr in range(frames):
        if fr > 0:
            P = forces(P, cnt, fr, p, dtype)
        P, cnt = insert(P, cnt, p)
        counts.append(cnt)
    return P, counts


def node_texel(i):
    return (i % NW, i // NW)
