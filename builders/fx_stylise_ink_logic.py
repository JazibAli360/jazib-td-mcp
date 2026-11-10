"""fx_stylise_ink_logic - numpy mirror of FX_stylise 'ink' (builders/fx_stylise_ink.py). Pure: no td.
blur2(img, sigma, k) == blurh + blurv (two separable Gaussians of luma, exact normalised weights, clamped taps);
xdog_E(g, P) == the XDoG E; look(img, g, P, pal=None) == fx. ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402

RMAX = 48


def radius(sigma, k):
    return min(RMAX, int(math.ceil(3 * sigma * k)))


def _blur1(a, s, R, axis):
    """1-D Gaussian of a (H, W) along axis with clamped taps."""
    n = a.shape[axis]
    acc = np.zeros_like(a, dtype=np.float64)
    wsum = 0.0
    for i in range(-R, R + 1):
        w = math.exp(-i * i / (2.0 * s * s))
        idx = np.clip(np.arange(n) + i, 0, n - 1)
        acc += w * np.take(a, idx, axis=axis)
        wsum += w
    return acc / wsum


def blur2(img, sigma, k):
    """-> (H, W, 2): G_sigma(luma), G_(k sigma)(luma) (separable, = blurh then blurv; 16F rounding not modelled)."""
    L = X.luma(img).astype(np.float64)
    R = radius(sigma, k)
    s1, s2 = max(sigma, 1e-3), max(sigma * k, 1e-3)
    g1 = _blur1(_blur1(L, s1, R, 1), s1, R, 0)
    g2 = _blur1(_blur1(L, s2, R, 1), s2, R, 0)
    return np.stack([g1, g2], -1)


def xdog_E(g, P):
    S = (1 + P['Sharpen']) * g[..., 0] - P['Sharpen'] * g[..., 1]
    return np.where(S >= P['Eps'], 1.0, 1.0 + np.tanh(P['Phi'] * (S - P['Eps'])))


def look(img, g, P, pal=None):
    """== fx; pal = callable(t array) -> (..., 3) for palette fills (else grey t)."""
    c = np.asarray(img, np.float32).astype(np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    H, W = c.shape[:2]
    E = xdog_E(g, P)
    ink = np.clip((1 - E) * P['Inkamount'], 0, 1)
    mode, fm = P['Mode'], P['Fill']

    def palf(t):
        return pal(t) if pal is not None else np.repeat(np.asarray(t)[..., None], 3, -1)
    if mode == 0:
        if fm == 0:
            col = np.broadcast_to(np.array([P['Paperr'], P['Paperg'], P['Paperb']]), (H, W, 3))
        elif fm == 1:
            col = c[..., :3]
        else:
            col = palf(E)
    else:
        L = X.luma(c).astype(np.float64)
        n = max(P['Bands'], 2.0)
        x = L * n
        f = x - np.floor(x)
        lq = (np.floor(x) + X.smoothstep(0.5 - P['Bandsoft'], 0.5 + P['Bandsoft'], f)) / n
        if P['Toonpal']:
            col = palf(lq)
        else:
            sat = L[..., None] + (c[..., :3] - L[..., None]) * P['Saturation']
            col = sat * (lq / np.maximum(L, 1e-3))[..., None]
        if mode == 2:
            a = math.radians(P['Dotangle'])
            px, py = X.grid(H, W)
            qx = math.cos(a) * (px + 0.5) - math.sin(a) * (py + 0.5)
            qy = math.sin(a) * (px + 0.5) + math.cos(a) * (py + 0.5)
            cs = max(P['Dotsize'], 1.0)
            cx, cy = np.floor(qx / cs), np.floor(qy / cs)
            sd = int(P['Seed'])
            jx = (X.hsh(cx.astype(np.int64), cy.astype(np.int64), sd) - 0.5) * P['Dotjitter']
            jy = (X.hsh(cx.astype(np.int64) + 7, cy.astype(np.int64) + 3, sd) - 0.5) * P['Dotjitter']
            fx_, fy_ = qx / cs - cx - 0.5 - jx, qy / cs - cy - 0.5 - jy
            r = np.sqrt(np.clip((P['Dotthr'] - L) / max(P['Dotthr'], 1e-3), 0, 1)) * 0.5
            t = np.clip((np.hypot(fx_, fy_) - (r - 0.06)) / 0.12, 0, 1)
            dot = 1 - t * t * (3 - 2 * t)
            ink = np.where(L < P['Dotthr'], np.maximum(ink, dot * P['Inkamount']), ink)
    inkc = np.array([P['Inkr'], P['Inkg'], P['Inkb']])
    k = np.clip(ink, 0, 1)[..., None]
    o3 = col + (inkc - col) * k
    o = np.concatenate([o3, c[..., 3:]], -1)
    return c + (o - c) * P['Amount']
