"""fx_glass_liquid_logic - numpy mirror of FX_glass 'liquid' (builders/fx_glass_liquid.py), Source shapes. Pure: no td.
sdf(pcx, pcy, shapes, P, W, H, t) == sdf(); look(img, backdrop, shapes, P, t=0, pal_step=None) == fx. ASCII only."""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402

NSHP = 8


def shapes_from_rows(rows):
    out = []
    for r in rows:
        try:
            v = [float(x) for x in r[:6]]
        except Exception:
            continue
        if len(v) < 4:
            continue
        out.append(v + [0.0] * (6 - len(v)))
        if len(out) >= NSHP:
            break
    return out


def sd_box(qx, qy, bx, by, r):
    r = min(r, min(bx, by))
    dx, dy = np.abs(qx) - bx + r, np.abs(qy) - by + r
    return np.hypot(np.maximum(dx, 0), np.maximum(dy, 0)) + np.minimum(np.maximum(dx, dy), 0) - r


def sdf(pcx, pcy, shapes, P, W, H, t=0.0):
    d = np.full(np.shape(pcx), 1e6)
    best = np.full(np.shape(pcx), 1e6)
    idx = np.zeros(np.shape(pcx))
    k = max(P['Smooth'], 1e-3)
    for i, s in enumerate(shapes):
        cx = s[0] * W + P['Drift'] * math.sin(t * 0.7 + i * 1.9 + P['Seed'])
        cy = s[1] * H + P['Drift'] * math.cos(t * 0.53 + i * 2.7 + P['Seed'])
        a = math.radians(s[5])
        qx, qy = pcx - cx, pcy - cy
        rx, ry = math.cos(a) * qx + math.sin(a) * qy, -math.sin(a) * qx + math.cos(a) * qy
        di = sd_box(rx, ry, 0.5 * s[2], 0.5 * s[3], s[4])
        upd = di < best
        best = np.where(upd, di, best)
        idx = np.where(upd, i, idx)
        hh = np.maximum(k - np.abs(d - di), 0) / k
        d = np.minimum(d, di) - hh * hh * k * 0.25
    return d, idx


def refract(nx, ny, nz, eta):
    """GLSL refract(I = (0, 0, -1), N, eta)."""
    ndi = -nz
    k = 1 - eta * eta * (1 - ndi * ndi)
    sq = np.sqrt(np.maximum(k, 0))
    f = eta * ndi + sq
    rx, ry, rz = -f * nx, -f * ny, -eta - f * nz
    ok = k >= 0
    return np.where(ok, rx, 0), np.where(ok, ry, 0), np.where(ok, rz, 0)


def look(img, bd, shapes, P, t=0.0, pal_step=None):
    c = np.asarray(img, np.float32).astype(np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    H, W = c.shape[:2]
    BH, BW = bd.shape[:2]
    px, py = X.grid(H, W)
    pcx, pcy = px + 0.5, py + 0.5
    d, idx = sdf(pcx, pcy, shapes, P, W, H, t)
    far = (d > 1.0) & ((P['Shadow'] <= 0) | (d > abs(P['Shadowoffset']) + 6 * P['Shadowsoft']))
    e = 0.75
    gx = (sdf(pcx + e, pcy, shapes, P, W, H, t)[0] - sdf(pcx - e, pcy, shapes, P, W, H, t)[0]) / (2 * e)
    gy = (sdf(pcx, pcy + e, shapes, P, W, H, t)[0] - sdf(pcx, pcy - e, shapes, P, W, H, t)[0]) / (2 * e)
    gl = np.hypot(gx, gy)
    ok = gl * gl > 1e-12
    gx, gy = np.where(ok, gx / np.where(ok, gl, 1), 0), np.where(ok, gy / np.where(ok, gl, 1), 0)
    tt = np.clip(-d / max(P['Bevel'], 1e-3), 0, 1)
    u = 1 - tt
    slope = np.minimum(u / np.sqrt(np.maximum(1 - u * u, 1e-4)), 8.0)
    nx, ny, nz = gx * slope, gy * slope, np.ones_like(gx)
    nl = np.sqrt(nx * nx + ny * ny + nz * nz)
    nx, ny, nz = nx / nl, ny / nl, nz / nl
    col = np.zeros((H, W, 3))
    for k, s in enumerate((-1, 0, 1)):
        ior = P['Ior'] * (1 + P['Dispersion'] * s)
        rx, ry, rz = refract(nx, ny, nz, 1.0 / ior)
        den = np.maximum(-rz, 0.05)
        qx, qy = pcx + rx / den * P['Thickness'], pcy + ry / den * P['Thickness']
        sharp = X.bilinear(c, qx, qy)[..., k]
        blur = X.bilinear(bd, qx * BW / W, qy * BH / H)[..., k]
        col[..., k] = sharp + (blur - sharp) * P['Frost']
    if P['Tintsrc'] == 1 and pal_step is not None:
        tint = pal_step(idx)
    else:
        tint = np.broadcast_to(np.array([P['Tintr'], P['Tintg'], P['Tintb']]), (H, W, 3))
    col = (col + (tint - col) * P['Tintamt']) * P['Bright']
    la = math.radians(P['Lightangle'])
    Lx, Ly, Lz = math.cos(la), math.sin(la), 1.2
    ll = math.sqrt(Lx * Lx + Ly * Ly + Lz * Lz)
    hx, hy, hz = Lx / ll, Ly / ll, Lz / ll + 1.0
    hl = math.sqrt(hx * hx + hy * hy + hz * hz)
    spec = np.maximum(nx * hx / hl + ny * hy / hl + nz * hz / hl, 0) ** P['Shine'] * P['Spec']
    rim = np.clip(1 - nz, 0, 1) ** (max(P['Rimpow'], 0.1) * 0.25) * P['Rim'] * (1 - tt)
    edge = P['Edge'] * (1 - X.smoothstep(0.0, 1.5, np.abs(d)))
    col = col + (spec + rim + edge)[..., None]
    cov = 1 - X.smoothstep(-0.75, 0.75, d)
    ds = sdf(pcx, pcy + P['Shadowoffset'], shapes, P, W, H, t)[0]
    sh = P['Shadow'] * np.exp(-np.maximum(ds, 0) / max(P['Shadowsoft'], 1e-3)) * (1 - cov)
    back = np.concatenate([c[..., :3] * (1 - sh)[..., None], np.maximum(c[..., 3], sh)[..., None]], -1)
    glass = np.concatenate([col, np.ones((H, W, 1))], -1)
    o = back + (glass - back) * cov[..., None]
    o = np.where(far[..., None], c, o)                                       # far outside: the shader returns c
    return c + (o - c) * P['Amount']
