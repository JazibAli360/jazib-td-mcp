"""fx_stylise_boil_logic - numpy mirror of FX_stylise 'boil' (builders/fx_stylise_boil.py) fx pass. Pure: no td.
look(held, live, P, seed_k, pal=None) == fx; tick(t, holdfps) / boil_seed == the uniform expressions; hold_ticks counts
the copies a Holdfps clock makes over a run of frame times. ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402


def tick(t, holdfps):
    return math.floor(t * (holdfps if holdfps > 0 else 12.0))


def boil_seed(t, P):
    return (tick(t, P['Holdfps']) % max(1, int(P['Boilframes']))) + 1000 * int(P['Seed'])


def hold_ticks(times, holdfps):
    """Number of hold copies (stamp changes) over frame times (first cook counts)."""
    n, last = 0, None
    prev_t = None
    for t in times:
        k = tick(t, holdfps)
        if last is None or k != last or (prev_t is not None and t - prev_t > 0.25):
            n += 1
        last, prev_t = k, t
    return n


def look(held, live, P, seed_k, pal=None):
    """== fx. held / live (H, W, 4) float; pal = callable(t array) -> (..., 3) for Fill palette (else grey)."""
    held = np.asarray(held, np.float32)
    live = np.asarray(live, np.float32)
    if P['Amount'] <= 0:
        return live.copy()
    H, W = live.shape[:2]
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5
    sc = max(P['Boilscale'], 1.0)
    nx, ny = X.vnoise2(pcx / sc, pcy / sc, int(seed_k))
    ox, oy = (2 * nx - 1) * P['Boil'], (2 * ny - 1) * P['Boil']
    qx, qy = pcx + ox, pcy + oy
    w = max(P['Linewidth'], 0.5)

    def L(dx, dy):
        return X.luma(X.bilinear(held, qx + dx, qy + dy))
    tl, tc, tr = L(-w, w), L(0, w), L(w, w)
    ml, mr = L(-w, 0), L(w, 0)
    bl, bc, br = L(-w, -w), L(0, -w), L(w, -w)
    gx = (tr + 2 * mr + br) - (tl + 2 * ml + bl)
    gy = (tl + 2 * tc + tr) - (bl + 2 * bc + br)
    g = np.hypot(gx, gy) * 0.25
    line = X.smoothstep(P['Edgethr'], P['Edgethr'] + max(P['Edgesoft'], 1e-4), g)
    f = X.bilinear(held, pcx + ox * P['Fillboil'], pcy + oy * P['Fillboil'])
    lv = max(P['Levels'] - 1.0, 1.0)
    fm = P['Fill']
    if fm == 0:
        fill = np.floor(f[..., :3] * lv + 0.5) / lv
    elif fm == 1:
        fill = np.broadcast_to(np.array([P['Paperr'], P['Paperg'], P['Paperb']]), (H, W, 3)).astype(np.float64)
    elif fm == 2:
        fill = f[..., :3].astype(np.float64)
    else:
        t = np.floor(X.luma(f) * lv + 0.5) / lv
        fill = pal(t) if pal is not None else np.repeat(t[..., None], 3, -1)
    gs = max(P['Grainscale'], 1.0)
    gr = (X.hsh(np.floor(pcx / gs).astype(np.int64), np.floor(pcy / gs).astype(np.int64), int(P['Seed']) + 7) - 0.5) \
        * P['Paper']
    fill = fill * (1 + gr)[..., None]
    ink = np.array([P['Inkr'], P['Inkg'], P['Inkb']])
    k = np.clip(line * P['Inkamount'], 0, 1)[..., None]
    o3 = fill + (ink - fill) * k
    o = np.concatenate([o3, live[..., 3:]], -1)
    return live + (o - live) * P['Amount']


def edge_share(out, live, thr=0.25):
    """Share of pixels pulled toward dark ink (luma drop > thr) - a cheap 'lines drawn' number."""
    return float(((X.luma(live) - X.luma(out)) > thr).mean())
