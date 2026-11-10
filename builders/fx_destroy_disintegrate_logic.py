# fx_destroy_disintegrate_logic - numpy reference for FX_destroy module 'disintegrate'
# (builders/fx_destroy_disintegrate.py). Mirrors the `grains` shader (release time per grain), the shared time model
# (flight time), the `dust` particle motion + square splats, and the `fx` remnant, for the offline tests and the live
# parity checks (docs/builds/fx_destroy_disintegrate.md). Arrays are in texel order: row 0 = texel y 0 (bottom), as
# TOP.numpyArray() returns them; x right, y up. Hash / value noise come from the crack reference (exact uint32).
# CLI: python3 -I builders/fx_destroy_disintegrate_logic.py expect   (numbers quoted in the doc). ASCII only.
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fx_destroy_crack_logic as CL  # noqa: E402

M32 = 0xffffffff
FRONTS = ['dir', 'point', 'inward', 'noise', 'luma', 'mask']
MENUS = {'Mode': ['away', 'assemble'], 'Drive': ['hits', 'manual'], 'Front': FRONTS, 'Blend': ['over', 'add'],
         'Back': ['dim', 'alpha'], 'Masksource': ['none', 'luma', 'dark', 'top', 'radial']}
SPLAT_MAX = 12


def mi(P, name):
    v = P[name]
    return int(v) if not isinstance(v, str) else MENUS[name].index(v)


def hsh3_np(gx, gy, k, s):
    """GLSL hsh3(ivec3(g, k), s) of the rack lib."""
    return CL.hsh_np(gx, gy, (s ^ CL.lb32((k + 0x9e3779b9) & M32)) & M32)


def fbm_np(x, y, s, octaves):
    v = np.zeros_like(x, dtype=np.float64)
    a, n = 0.5, 0.0
    for k in range(min(int(octaves), 6)):
        v = v + a * CL.vnoise_np(x, y, (s + k * 101) & M32)
        n += a
        x, y = x * 2.03 + 17.1, y * 2.03 + 17.1
        a *= 0.5
    return v / n


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / (b - a), 0.0, 1.0) if b != a else (np.asarray(x) >= a) * 1.0
    return t * t * (3 - 2 * t)


def grain_size(P):
    return max(1, int(P['Grain']))


def grid(P, W, H):
    """(gw, gh, rest x, rest y) - grain centres px, arrays of shape (gh, gw)."""
    G = grain_size(P)
    gw, gh = int(math.ceil(W / G)), int(math.ceil(H / G))
    gx, gy = np.meshgrid(np.arange(gw), np.arange(gh))
    return gw, gh, gx, gy, (gx + 0.5) * G, (gy + 0.5) * G


def sample(img, x, y, W, H):
    """Bilinear sample (hold at the edges) of img (H, W, C) at pixel coords x, y (texel centres at i + 0.5)."""
    fx, fy = np.clip(x - 0.5, 0, W - 1), np.clip(y - 0.5, 0, H - 1)
    x0, y0 = np.floor(fx).astype(int), np.floor(fy).astype(int)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    tx, ty = (fx - x0)[..., None], (fy - y0)[..., None]
    a = img[y0, x0] * (1 - tx) + img[y0, x1] * tx
    b = img[y1, x0] * (1 - tx) + img[y1, x1] * tx
    return a * (1 - ty) + b * ty


def luma(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def grains(P, W, H, ctr, img=None, mask=None):
    """(tb, f): release time s per grain (-1 = protected) and the front value, shape (gh, gw). ctr = centre px
    (latched hit centre, or the live Point when Drive = manual). img (H, W, 3+) needed for Front luma; mask = per-grain
    fxMask value (gh, gw) or None (= 1 everywhere: Masksource none)."""
    gw, gh, gx, gy, rx, ry = grid(P, W, H)
    mode = mi(P, 'Front')
    sd = (int(P['Seed']) * 7919) & M32
    m = np.ones((gh, gw)) if mask is None else mask
    n = np.clip((fbm_np(rx / max(P['Noisescale'], 1.0), ry / max(P['Noisescale'], 1.0), (sd + 13) & M32,
                        int(P['Detail'] + 0.5)) - 0.25) * 2.0, 0.0, 1.0)
    if mode == 0:
        a = math.radians(P['Frontangle'])
        dx, dy = math.cos(a), math.sin(a)
        c = [0.0, W * dx + H * dy, W * dx, H * dy]
        f0 = (rx * dx + ry * dy - min(c)) / max(max(c) - min(c), 1e-3)
    elif mode in (1, 2):
        cx, cy = ctr
        md = max(math.hypot(cx, cy), math.hypot(cx - W, cy), math.hypot(cx, cy - H), math.hypot(cx - W, cy - H))
        f0 = np.hypot(rx - cx, ry - cy) / max(md, 1e-3)
        if mode == 2:
            f0 = 1.0 - f0
    elif mode == 3:
        f0 = n
    elif mode == 4:
        f0 = 1.0 - luma(sample(img, rx, ry, W, H))
    else:
        f0 = 1.0 - m
    f = f0 + (n - f0) * P['Roughness']
    if P['Reverse']:
        f = 1.0 - f
    f = np.clip(f + P['Jitter'] * (hsh3_np(gx, gy, 9, sd) - 0.5), 0.0, 1.0)
    tb = P['Sweep'] * f
    if mode != 5:
        tb = np.where(m < 0.5, -1.0, tb)
    return tb, f


def age_of(P, now=None, hit=None):
    """(valid, age s): manual = Progress x Duration; hits = now - hit time."""
    if mi(P, 'Drive') == 1:
        t = P['Progress'] * P['Duration']
        return t > 0, t
    if hit is None or hit < 0 or now < hit:
        return False, 0.0
    return True, now - hit


def flight(P, age, tb):
    """Flight time s of grains released at tb (0 = at rest / intact). Mirror of TIME_GLSL flight()."""
    tb = np.asarray(tb, dtype=np.float64)
    if mi(P, 'Mode') == 1:
        tau = np.clip(P['Duration'] - (age - tb), 0.0, P['Duration'])
        return np.where(tb < 0, 0.0, tau)
    tau = age - tb
    if P['Return'] > 0:
        h, r = P['Hold'], P['Return']
        back = h * (1.0 - smoothstep(h, h + r, tau))
        tau = np.where(tau >= h + r, 0.0, np.where(tau > h, back, tau))
    return np.where((tb < 0) | (tau <= 0), 0.0, tau)


def end_time(P):
    """Seconds after the hit when every grain is back at rest (None = never: Return 0 leaves the picture gone)."""
    if mi(P, 'Mode') == 1:
        return P['Sweep'] + P['Duration']
    if P['Return'] > 0:
        return P['Sweep'] + P['Hold'] + P['Return']
    return None


def _curl(qx, qy, s):
    e = 0.35
    nx = CL.vnoise_np(qx + e, qy, s) - CL.vnoise_np(qx - e, qy, s)
    ny = CL.vnoise_np(qx, qy + e, s) - CL.vnoise_np(qx, qy - e, s)
    return ny / (2 * e), -nx / (2 * e)


def particles(P, W, H, age, ctr, tb, live=None):
    """Per grain: dict(x, y (px), tau, alpha, size (int px), on (drawn)). ctr = latched centre (hits) / live
    centre (manual); live = live Effector / Point px for Push (defaults to ctr)."""
    gw, gh, gx, gy, rx, ry = grid(P, W, H)
    G = grain_size(P)
    live = ctr if live is None else live
    if mi(P, 'Drive') == 1:
        ctr = live
    tau = flight(P, age, tb)
    life = P['Life']
    lt = np.clip(tau / life, 0, 1) if life > 0 else np.zeros_like(tau)
    al = 1.0 - smoothstep(0.3 * life, life, tau) if life > 0 else np.ones_like(tau)
    al = 1.0 + (al - 1.0) * P['Amount']
    sd = (int(P['Seed']) * 7919) & M32
    h1, h2, h3, h4 = (hsh3_np(gx, gy, k, sd).astype(np.float64) for k in (1, 2, 3, 4))
    wa = math.radians(P['Windangle'])
    wx, wy = math.cos(wa), math.sin(wa)
    an = (h1 - 0.5) * math.radians(P['Cone'])
    dx, dy = np.cos(an) * wx - np.sin(an) * wy, np.sin(an) * wx + np.cos(an) * wy
    sp = P['Windspeed'] * (1 - 0.5 * P['Spread'] + P['Spread'] * h2)
    r_x, r_y = rx - ctr[0], ry - ctr[1]
    rl = np.hypot(r_x, r_y)
    d = rl / math.hypot(W, H)
    big = rl > 1e-3
    ox, oy = np.where(big, r_x / np.maximum(rl, 1e-9), 0.0), np.where(big, r_y / np.maximum(rl, 1e-9), 1.0)
    v = P['Blast'] * np.exp(-P['Falloff'] * d * 4) * (0.5 + h3)
    k = P['Drag']
    I = (1 - np.exp(-k * tau)) / k if k > 1e-4 else tau
    px = rx + dx * sp * tau + ox * v * I
    py = ry + dy * sp * tau + oy * v * I - 0.5 * P['Gravity'] * tau * tau
    if P['Turbulence'] != 0:
        sc = max(P['Turbscale'], 1.0)
        qx = (rx + dx * sp * tau * 0.5) / sc
        qy = (ry + dy * sp * tau * 0.5) / sc + tau * P['Turbspeed']
        cx, cy = _curl(qx, qy, (sd + 31) & M32)
        px = px + cx * P['Turbulence'] * tau * (0.5 + h4)
        py = py + cy * P['Turbulence'] * tau * (0.5 + h4)
    if P['Push'] != 0:
        qx, qy = px - live[0], py - live[1]
        dl = np.hypot(qx, qy)
        ux = np.where(dl > 1e-3, qx / np.maximum(dl, 1e-9), ox)
        uy = np.where(dl > 1e-3, qy / np.maximum(dl, 1e-9), oy)
        f = P['Push'] * np.exp(-(dl * dl) / max(P['Pushradius'] ** 2, 1.0)) * np.minimum(tau * 4, 1.0)
        px, py = px + ux * f, py + uy * f
    px, py = rx + (px - rx) * P['Amount'], ry + (py - ry) * P['Amount']
    s = P['Size'] * G * (1 + (P['Shrink'] - 1) * lt)
    si = np.clip(np.floor(s + 0.5).astype(int), 1, SPLAT_MAX)
    on = (tau > 0) & (al > 0.002) & (P['Amount'] > 0)
    return {'x': px, 'y': py, 'tau': tau, 'alpha': al, 'size': si, 'on': on, 'lt': lt}


def dust_alpha(P, W, H, pr, img=None):
    """Coverage (H, W) bool of the drawn squares (order-free: the shader's last write wins, so only coverage and
    per-particle colours are comparable)."""
    cov = np.zeros((H, W), bool)
    idx = np.nonzero(pr['on'])
    for x, y, s in zip(pr['x'][idx], pr['y'][idx], pr['size'][idx]):
        ox, oy = int(math.floor(x - 0.5 * s + 0.5)), int(math.floor(y - 0.5 * s + 0.5))
        x0, y0, x1, y1 = max(ox, 0), max(oy, 0), min(ox + s, W), min(oy + s, H)
        if x1 > x0 and y1 > y0:
            cov[y0:y1, x0:x1] = True
    return cov


def remnant(P, W, H, age, tb):
    """Per pixel (H, W) bool: True where the grain under it is released (shows Back), False = picture."""
    G = grain_size(P)
    tau = flight(P, age, tb)
    rel = tau > 0
    return np.repeat(np.repeat(rel, G, axis=0), G, axis=1)[:H, :W]


def expected_numbers(W=1080, H=1920):
    """Released share and drawn-particle count of every preset, Drive manual, at a few manual times."""
    ns = _module_ns()
    out = []
    for slot, name, vals in ns['PRESETS']:
        P = dict(vals, Drive=1, Duration=1.0, Progress=0.0)
        ctr = (0.5 * W, 0.5 * H)
        if mi(P, 'Front') == 4:
            continue
        tb, _f = grains(P, W, H, ctr)
        row = []
        for t in (0.5, 1.5, 3.0):
            tau = flight(P, t, tb)
            row.append((t, round(float((tau > 0).mean()), 4)))
        out.append((slot, name, row))
    return out


def _module_ns():
    here = os.path.dirname(os.path.abspath(__file__))
    rack = {}
    with open(os.path.join(here, 'fx_destroy.py')) as fh:
        exec(fh.read(), rack)
    ns = dict(rack)
    with open(os.path.join(here, 'fx_destroy_disintegrate.py')) as fh:
        exec(fh.read(), ns)
    return ns


if __name__ == '__main__':
    if sys.argv[1:2] == ['expect']:
        for slot, name, row in expected_numbers():
            print(slot, name, ' '.join('t=%.1f released %.4f' % r for r in row))
