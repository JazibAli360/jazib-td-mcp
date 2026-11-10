# fx_retro_cycle_logic - numpy mirror of FX_retro 'cycle' (builders/fx_retro_cycle.py) for the analytic ramps (the
# Machine ramp reads the rack bank: checked by colours-in-palette). shifts = the 4 range shift uniforms (indices).
import numpy as np

LUMA = np.array([0.2126, 0.7152, 0.0722])
DEFAULTS = {'Amount': 1.0, 'Source': 0, 'Indices': 32, 'Ramp': 0, 'Blend': 1, 'Contrast': 1.0, 'Offset': 0.0,
            'Seed': 1, 'R1start': 0.0, 'R1end': 1.0, 'R1speed': 8.0, 'R2start': 0.0, 'R2end': 0.0, 'R2speed': 0.0,
            'R3start': 0.0, 'R3end': 0.0, 'R3speed': 0.0, 'R4start': 0.0, 'R4end': 0.0, 'R4speed': 0.0}


def pars_of(over=None):
    d = dict(DEFAULTS)
    d.update(over or {})
    return d


def ranges(P, t=0.0, shifts=None):
    N = max(2, int(P['Indices'] + 0.5))
    out = []
    for k in range(4):
        s0 = np.floor(P['R%dstart' % (k + 1)] * N + 0.5)
        s1 = np.floor(P['R%dend' % (k + 1)] * N + 0.5)
        sh = shifts[k] if shifts is not None else (P['R%dspeed' % (k + 1)] * t) % max(1.0, s1 - s0)
        out.append((s0, s1, sh))
    return out


def ramp(u, r):
    u = np.clip(u, 0.0, 1.0)[..., None]
    if r == 0:
        return np.clip(np.concatenate([u * 3, u * 3 - 1, u * 3 - 2], -1), 0, 1)
    if r == 1:
        return np.clip(np.concatenate([u * u, 0.25 + 0.75 * u, 0.45 + 0.55 * np.sqrt(u)], -1), 0, 1) * \
            np.concatenate([np.ones_like(u), u + 0.2, np.ones_like(u)], -1)
    if r == 2:
        return np.clip(np.abs(((u + np.array([0.0, 2 / 3, 1 / 3])) % 1.0) * 6 - 3) - 1, 0, 1)
    if r == 3:
        return np.repeat(u, 3, -1)
    if r == 4:
        return np.clip(np.concatenate([0.15 + 0.85 * np.sqrt(u), 0.05 + 0.9 * u * u,
                                       0.35 * (1 - u) + 0.6 * u ** 3], -1), 0, 1)
    raise NotImplementedError('Machine ramp reads the rack bank')


def hue(c):
    mx, mn = c.max(-1), c.min(-1)
    d = mx - mn
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    sd = np.where(d > 1e-6, d, 1.0)
    h = np.where(mx == r, np.mod((g - b) / sd, 6.0), np.where(mx == g, (b - r) / sd + 2.0, (r - g) / sd + 4.0))
    return np.where(d > 1e-6, h / 6.0, 0.0)


def render(img, P, t=0.0, shifts=None):
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0:
        return img.copy()
    c = img[..., :3]
    sm = int(P['Source'])
    if sm == 0:
        v = (c * LUMA).sum(-1)
    elif sm == 1:
        v = hue(c)
    else:
        mx = c.max(-1)
        v = np.where(mx > 1e-6, (mx - c.min(-1)) / np.maximum(mx, 1e-12), 0.0)
    v = np.clip((v - 0.5) * P['Contrast'] + 0.5 + P['Offset'], 0, 1)
    N = float(max(2, int(P['Indices'] + 0.5)))
    i = np.minimum(np.floor(v * N), N - 1)
    R = ranges(P, t, shifts)
    j = i
    for s0, s1, sh in R:
        L = s1 - s0
        if L >= 1:
            inr = (j >= s0) & (j < s1)
            j = np.where(inr, s0 + np.mod(j - s0 + sh, L), j)
    r = int(P['Ramp'])
    if P['Blend']:
        f = j - np.floor(j)
        j0 = np.floor(j)
        j1 = j0 + 1
        for s0, s1, _sh in R:
            if s1 - s0 >= 1:
                j1 = np.where((j0 >= s0) & (j0 < s1) & (j1 >= s1), s0, j1)
        col = ramp((j0 + 0.5) / N, r) * (1 - f[..., None]) + ramp((np.minimum(j1, N - 1) + 0.5) / N, r) * f[..., None]
    else:
        col = ramp((np.floor(j) + 0.5) / N, r)
    fin = c + (col - c) * P['Amount']
    return np.concatenate([fin * img[..., 3:4], img[..., 3:4]], -1)


def reference(img, pars=None, t=0.0, shifts=None):
    return render(img, pars_of(pars), t, shifts)


def compare(td_out, ref, tol=2.0 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
