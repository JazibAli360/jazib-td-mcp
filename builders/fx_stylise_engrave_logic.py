"""fx_stylise_engrave_logic - numpy mirror of FX_stylise 'engrave' (builders/fx_stylise_engrave.py). Pure: no td.
look(img, P, drift=0, pal=None) == fx. ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402


def _lines(pcx, pcy, ang, sp, lb, hw, P, drift):
    a = math.radians(ang)
    nx, ny = -math.sin(a), math.cos(a)
    tx, ty = math.cos(a), math.sin(a)
    along = pcx * tx + pcy * ty
    v = pcx * nx + pcy * ny + P['Bend'] * sp * lb + P['Wave'] * np.sin(
        2 * math.pi * (along * P['Wavefreq'] + 0.137 * P['Seed'])) + drift * sp
    f = v / sp - np.floor(v / sp)
    dist = np.abs(f - 0.5) * sp
    return (1 - X.smoothstep(hw - 0.5 * P['Aa'], hw + 0.5 * P['Aa'], dist)) * np.clip(2 * hw / max(P['Aa'], 1e-3), 0, 1)


def smoothed_luma(img, s):
    H, W = img.shape[:2]
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5

    def Lt(x, y):
        return X.luma(X.bilinear(img, x, y)).astype(np.float64)
    return (Lt(pcx, pcy) + Lt(pcx + s, pcy) + Lt(pcx - s, pcy) + Lt(pcx, pcy + s) + Lt(pcx, pcy - s)) * 0.2


def look(img, P, drift=0.0, pal=None):
    c = np.asarray(img, np.float32).astype(np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    H, W = c.shape[:2]
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5
    lb = smoothed_luma(np.asarray(img, np.float32), P['Smooth'])
    sp = max(P['Spacing'], 1.0)
    dk = np.clip(1 - lb, 0, 1) ** P['Gamma']
    ink = _lines(pcx, pcy, P['Angle'], sp, lb, 0.5 * P['Width'] * dk * sp, P, drift)
    dk2 = np.clip((P['Cross'] - lb) / max(P['Cross'], 1e-3), 0, 1)
    ink2 = _lines(pcx, pcy, P['Angle'] + P['Crossangle'], sp, lb, 0.5 * P['Width'] * dk2 * sp, P, drift)
    ink = np.where(lb < P['Cross'], np.maximum(ink, ink2), ink)
    fm = P['Fill']
    if fm == 0:
        base = np.broadcast_to(np.array([P['Paperr'], P['Paperg'], P['Paperb']]), (H, W, 3))
    elif fm == 1:
        base = c[..., :3]
    else:
        base = pal(lb) if pal is not None else np.repeat(lb[..., None], 3, -1)
    ic = c[..., :3] if P['Inkcolour'] == 1 else np.broadcast_to(np.array([P['Inkr'], P['Inkg'], P['Inkb']]), (H, W, 3))
    o = base + (ic - base) * ink[..., None]
    out = np.concatenate([o, c[..., 3:]], -1)
    return c + (out - c) * P['Amount']
