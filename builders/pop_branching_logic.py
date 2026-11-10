# pop_branching_logic - numpy mirror of POP_branching (TC-10 emergent feedback branching; builder
# builders/pop_branching.py, doc docs/builds/pop_lane_h.md "TC-10"). Same algorithm as the compute passes: `tips`
# (seed / sense 3 sensors / steer away from trail / wander / move / die / split flag), `alloc` (two exclusive scans in
# one workgroup: survivors densely first, then children, capped at Maxtips), deposit (1 px per tip, additive) and
# `trail` (wrap 3x3 mean mix x decay + deposit: the sum follows S_t = decay S_{t-1} + dep N_t exactly).
# Runs OUTSIDE TD (T-184). ASCII only.
import math

import numpy as np

from pop_scan import exclusive_scan

TW = 64
TROWS = 64
MAXT = TW * TROWS   # 4096 hard cap
CHUNK = MAXT // 1024
SEEDMODES = ['center', 'bottom']
TAU = 6.283185307179586
M32 = 0xFFFFFFFF
WALL = 1e9

DEFAULTS = {'seedmode': 'center', 'seedcount': 8, 'maxtips': 256, 'step': 1.0, 'sensorangle': 30.0,
            'sensordist': 6.0, 'turn': 20.0, 'wander': 10.0, 'killthresh': 2.0, 'splitrate': 0.02,
            'splitangle': 25.0, 'maxage': 600, 'deposit': 1.0, 'decay': 0.995, 'diffuse': 0.0,
            'simw': 540, 'simh': 960, 'seed': 1, 'play': 1}


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
    i = np.asarray(i, dtype=np.int64).astype(np.uint64) & M32
    s = np.uint64(int(s) & M32)
    h = lowbias((i * np.uint64(747796405) + s * np.uint64(2891336453) + np.uint64(1)) & M32)
    return (h >> np.uint64(8)).astype(np.float64) / 16777216.0


def maxt(p):
    return int(min(max(int(p['maxtips']), 1), MAXT))


def salt(p, frame, k):
    return (int(p['seed']) * 65537 + int(frame) * 4 + k) & M32


def seed_tips(p, dtype=np.float64):
    n = int(min(max(int(p['seedcount']), 1), maxt(p)))
    i = np.arange(n, dtype=np.float64)
    W, H = p['simw'], p['simh']
    if (SEEDMODES.index(p['seedmode']) if isinstance(p['seedmode'], str) else int(p['seedmode'])) == 0:
        T = np.stack([np.full(n, W * 0.5), np.full(n, H * 0.5), TAU * i / n, np.zeros(n)], -1)
    else:
        T = np.stack([W * (i + 0.5) / n, np.full(n, 2.0), np.full(n, math.pi / 2), np.zeros(n)], -1)
    return T.astype(dtype), n


def sense(trail, x, y):
    H, W = trail.shape[:2]
    xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    ok = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
    v = np.full(np.shape(x), WALL)
    v[ok] = trail[yi[ok], xi[ok], 0]
    return v


def tips(T, cnt, frame, trail, p, dtype=np.float64):
    """`tips` for 0..cnt-1. Returns cnt x 4: (x, y, heading, w) with w = -1 dead, else age + 1 (+ 0.25 = split)."""
    T = np.asarray(T, dtype=dtype)[:cnt].copy()
    if not p['play']:
        return T
    x, y, h, age = T[:, 0], T[:, 1], T[:, 2], T[:, 3]
    sa, so, ra = math.radians(p['sensorangle']), p['sensordist'], math.radians(p['turn'])
    idx = np.arange(cnt)
    F = sense(trail, x + so * np.cos(h), y + so * np.sin(h))
    Lf = sense(trail, x + so * np.cos(h + sa), y + so * np.sin(h + sa))
    Rf = sense(trail, x + so * np.cos(h - sa), y + so * np.sin(h - sa))
    keep = (F <= Lf) & (F <= Rf)
    h = np.where(keep, h, np.where(Lf < Rf, h + ra, h - ra)).astype(dtype)
    h = (h + math.radians(p['wander']) * (hh(idx, salt(p, frame, 0)) - 0.5) * 2.0).astype(dtype)
    x = (x + p['step'] * np.cos(h)).astype(dtype)
    y = (y + p['step'] * np.sin(h)).astype(dtype)
    W, H = p['simw'], p['simh']
    out = (x < 0) | (x >= W) | (y < 0) | (y >= H)
    dead = (F > p['killthresh']) | out | (age + 1 > p['maxage'])
    dens = sense(trail, x, y)
    pr = p['splitrate'] * (1.0 - np.clip(dens / p['killthresh'], 0.0, 1.0))
    split = (~dead) & (hh(idx, salt(p, frame, 1)) < pr)
    w = np.where(dead, -1.0, age + 1 + np.where(split, 0.25, 0.0))
    return np.stack([x, y, h, w], -1).astype(dtype)


def alloc(T, cnt, p):
    """Survivors densely in order, then children (heading - Splitangle; parent + Splitangle), capped at Maxtips."""
    T = np.asarray(T)[:cnt]
    w = T[:, 3]
    alive = w >= 0
    split = alive & ((w - np.floor(w)) > 0.1)
    mx = maxt(p)
    full_s = np.zeros(MAXT, np.int64)
    full_c = np.zeros(MAXT, np.int64)
    full_s[:cnt] = alive
    full_c[:cnt] = split
    _ps, S = exclusive_scan(full_s.reshape(1024, CHUNK).sum(1))
    _pc, C = exclusive_scan(full_c.reshape(1024, CHUNK).sum(1))
    sa = math.radians(p['splitangle'])
    newcnt = min(S + C, mx)
    out = np.zeros((newcnt, 4), T.dtype)
    rs = np.cumsum(alive) - 1
    rc = np.cumsum(split) - 1
    for i in np.nonzero(alive)[0]:
        if rs[i] < mx:
            out[rs[i]] = (T[i, 0], T[i, 1], T[i, 2] + (sa if split[i] else 0.0), math.floor(w[i]))
    for i in np.nonzero(split)[0]:
        d = S + rc[i]
        if d < mx:
            out[d] = (T[i, 0], T[i, 1], T[i, 2] - sa, 0.0)
    return out, int(newcnt)


def deposit(T, cnt, p):
    W, H = int(p['simw']), int(p['simh'])
    D = np.zeros((H, W, 4))
    T = np.asarray(T)[:cnt]
    if cnt:
        xi, yi = np.floor(T[:, 0]).astype(int), np.floor(T[:, 1]).astype(int)
        ag = np.clip(T[:, 3] / max(p['maxage'], 1), 0, 1)
        np.add.at(D, (yi, xi, 0), p['deposit'])
        np.add.at(D, (yi, xi, 1), p['deposit'] * ag)
        np.add.at(D, (yi, xi, 3), p['deposit'])
    return D


def trail_step(Tr, D, p, reset=False):
    if reset:
        Tr = np.zeros_like(Tr)
    m = sum(np.roll(np.roll(Tr, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9.0
    t = Tr + (m - Tr) * p['diffuse']
    return t * p['decay'] + D


def run(frames, p, dtype=np.float64):
    """Frame 0 seeds; each frame: tips -> alloc -> deposit -> trail. Returns (T, cnt, trail, counts, sums)."""
    W, H = int(p['simw']), int(p['simh'])
    Tr = np.zeros((H, W, 4))
    T, cnt = np.zeros((0, 4), dtype), 0
    counts, sums = [], []
    for fr in range(frames):
        if fr == 0:
            T, cnt = seed_tips(p, dtype)
        else:
            T = tips(T, cnt, fr, Tr, p, dtype)
        T, cnt = alloc(T, cnt, p)
        D = deposit(T, cnt, p)
        Tr = trail_step(Tr, D, p, reset=(fr == 0))
        counts.append(cnt)
        sums.append(float(Tr[..., 0].sum()))
    return T, cnt, Tr, counts, sums


def closed_form_sums(counts, p):
    s, out = 0.0, []
    for n in counts:
        s = p['decay'] * s + p['deposit'] * n
        out.append(s)
    return out
