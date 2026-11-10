"""fx_stylise_saber_logic - numpy mirror of FX_stylise 'saber' (builders/fx_stylise_saber.py). Pure: no td.
pts(rows) == the segs callback; path_distance == the path branch (capsules, Start..End, tip); mask_distance == the mask
branch (outline seed + JFA mirrors); look == the light + composite (Distort 0; flicker passed as a factor). ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402
import fx_stylise_outline_logic as OL  # noqa: E402

NPTS = 64


def pts(rows):
    """rows: [(x, y) or None (pen up)] -> [[x, y, u, pen]] (<= 64), u = arc length 0..1 over joined segments."""
    P, pen, acc, last = [], 0.0, 0.0, None
    for r in rows:
        if r is None:
            pen = 0.0
            continue
        if last is not None and pen > 0:
            acc += math.hypot(r[0] - last[0], r[1] - last[1])
        P.append([r[0], r[1], acc, pen])
        last, pen = r, 1.0
        if len(P) >= NPTS:
            break
    tot = acc if acc > 0 else 1.0
    for q in P:
        q[2] /= tot
    return P


def path_distance(W, H, P, start=0.0, end=1.0, units_px=False):
    """-> d (px), u, tipd for every pixel (== the shader's path loop)."""
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5
    d = np.full((H, W), 1e6)
    u = np.zeros((H, W))
    tipd = np.full((H, W), 1e6)
    sx, sy = (1.0, 1.0) if units_px else (float(W), float(H))
    for i in range(1, len(P)):
        b, a = P[i], P[i - 1]
        if b[3] < 0.5:
            continue
        ua, ub = a[2], b[2]
        if ub < start or ua > end:
            continue
        Ax, Ay, Bx, By = a[0] * sx, a[1] * sy, b[0] * sx, b[1] * sy
        fa = min(max((start - ua) / (ub - ua), 0), 1) if ub > ua else 0.0
        fb = min(max((end - ua) / (ub - ua), 0), 1) if ub > ua else 1.0
        A2x, A2y = Ax + (Bx - Ax) * fa, Ay + (By - Ay) * fa
        B2x, B2y = Ax + (Bx - Ax) * fb, Ay + (By - Ay) * fb
        abx, aby = B2x - A2x, B2y - A2y
        h = np.clip(((pcx - A2x) * abx + (pcy - A2y) * aby) / max(abx * abx + aby * aby, 1e-6), 0, 1)
        dd = np.hypot(pcx - A2x - abx * h, pcy - A2y - aby * h)
        upd = dd < d
        d = np.where(upd, dd, d)
        uu = (ua + (ub - ua) * fa) + ((ua + (ub - ua) * fb) - (ua + (ub - ua) * fa)) * h
        u = np.where(upd, uu, u)
        if ua <= end <= ub:
            tipd = np.minimum(tipd, np.hypot(pcx - B2x, pcy - B2y))
    return d, u, tipd


def mask_distance(img, P, Pm=None):
    """-> d, u (reveal parameter) for a mask source (img = the mask picture at in1 size)."""
    D = {0: 1, 1: 2, 2: 4}[P['Res']]
    sm = OL.seed_map(img, D, P['Threshold'], P['Matte'], P['Invert'])
    if Pm is None:
        rng = abs(P['Offset']) + P['Distort'] + 2 + 6 * max(P['Corewidth'], P['Glow'] * P['Spread'])
        Pm = OL.jfa_passes_for(sm.shape[1], sm.shape[0], rng, D)
    jf = OL.jfa_pm(sm, Pm, 1)
    sd, ins = OL.signed_distance(img, jf, D, P['Threshold'], P['Matte'], P['Invert'])
    sd = sd - P['Offset']
    d = np.maximum(sd, 0) if P['Solid'] else np.abs(sd)
    H, W = img.shape[:2]
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5
    if P['Revmode'] == 0:
        rcx, rcy = P['Revcentrex'] * W, P['Revcentrey'] * H
        u = np.mod(np.arctan2(pcy - rcy, pcx - rcx) / (2 * math.pi) + 1.0, 1.0)
    else:
        a = math.radians(P['Wipeangle'])
        dx, dy = math.cos(a), math.sin(a)
        ext = 0.5 * (abs(dx) * W + abs(dy) * H)
        u = np.clip(((pcx - 0.5 * W) * dx + (pcy - 0.5 * H) * dy) / max(2 * ext, 1) + 0.5, 0, 1)
    d = np.where((u < P['Start']) | (u > P['End']), 1e6, d)
    return d, u


def look(img, d, u, tipd, P, flick=1.0, pal=None):
    """== the fx light + composite for Colsrc solid (or palette via pal(u)), Distort 0."""
    c = np.asarray(img, np.float32).astype(np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    with np.errstate(over='ignore'):
        core = 1.0 / (1.0 + np.power(d / max(P['Corewidth'], 1e-3), P['Corepow']))
    glow = P['Glowint'] * (P['Bias'] * np.exp(-d / max(P['Glow'], 1e-3)) +
                           (1 - P['Bias']) * np.exp(-d / max(P['Glow'] * P['Spread'], 1e-3)))
    tip = P['Tip'] * np.exp(-tipd / max(P['Glow'], 1e-3))
    if P['Colsrc'] == 0 or pal is None:
        gcol = np.broadcast_to(np.array([P['Glowr'], P['Glowg'], P['Glowb']]), c.shape[:2] + (3,))
    else:
        gcol = pal(u)
    corec = np.array([P['Corer'], P['Coreg'], P['Coreb']])
    L = (core[..., None] * corec + (glow + tip)[..., None] * gcol) * P['Intensity'] * flick
    k = P['Back']
    if k == 1:
        base = c * P['Backdim']
    elif k == 2:
        base = np.zeros_like(c)
        base[..., 3] = 1
    elif k == 3:
        base = np.zeros_like(c)
    else:
        base = c
    cov = np.clip(np.maximum(core, glow + tip) * flick, 0, 1)
    o = np.concatenate([base[..., :3] + L, np.maximum(base[..., 3], cov)[..., None]], -1)
    return c + (o - c) * P['Amount']


def flicker(t, hz, seed, amount):
    """== fl = 1 + Flicker (2 hsh(ivec2(floor(t hz), 3), seed) - 1)."""
    return 1.0 + amount * (2.0 * float(X.hsh(np.array([int(math.floor(t * hz))]), np.array([3]), int(seed))[0]) - 1.0)
