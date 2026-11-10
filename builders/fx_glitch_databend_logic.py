# fx_glitch_databend_logic - numpy mirror of FX_glitch 'databend' (builders/fx_glitch_databend.py; DG-25). Arrays:
# [y, x, rgba], row 0 = BOTTOM, 0..1 (8-bit values). The stream is built exactly as the shader indexes it (rows from
# the top). Pure numpy, no TD names. ASCII only.
import numpy as np

EFFECTS = ['echo', 'delay', 'lowpass', 'highpass', 'crush', 'hold', 'reverse', 'wah', 'reverb']
ORDERS = ['rows', 'columns', 'planar']
DEFAULTS = {'Amount': 1.0, 'Effect': 0, 'Order': 0, 'Delay': 3000, 'Drift': 0.0, 'Feedback': 0.6, 'Repeats': 4,
            'Mix': 0.6, 'Cutoff': 0.15, 'Taps': 12, 'Bits': 3, 'Hold': 24, 'Chunk': 600, 'Rate': 3.0, 'Depth': 0.8,
            'Seed': 1}


def pars_of(over=None):
    d = dict(DEFAULTS)
    d.update(over or {})
    return d


def to_stream(img, order):
    """[H, W, >=3] (row 0 = bottom) -> flat byte stream (float, 0..255) in the shader's order."""
    b = np.floor(np.asarray(img, dtype=np.float64)[::-1, :, :3] * 255.0 + 0.5)    # rows from the top
    if order == 2:
        return b.transpose(2, 0, 1).reshape(-1)
    if order == 1:
        return b.transpose(1, 0, 2).reshape(-1)
    return b.reshape(-1)


def from_stream(s, H, W, order):
    if order == 2:
        b = s.reshape(3, H, W).transpose(1, 2, 0)
    elif order == 1:
        b = s.reshape(W, H, 3).transpose(1, 0, 2)
    else:
        b = s.reshape(H, W, 3)
    return b[::-1]


def bend(x, P, t=0.0):
    NB = len(x)
    k = np.arange(NB)

    def B(i):
        i = np.asarray(i)
        ok = (i >= 0) & (i < NB)
        return np.where(ok, x[np.clip(i, 0, NB - 1)], 0.0)

    def lowpass(a, taps):
        a = np.asarray(a, dtype=np.float64)
        s, w, g = 0.0, 0.0, a
        for m in range(min(int(taps), 32)):
            s = s + g * B(k - m)
            w = w + g
            g = g * (1.0 - a)
        return s / np.maximum(w, 1e-6)
    ef = int(P['Effect'])
    D = max(int(P['Delay'] + P['Drift'] * t), 1)
    mx = P['Mix']
    if ef == 0:
        s, g = x.copy(), 1.0
        for n in range(1, min(int(P['Repeats'] + 0.5), 8) + 1):
            g *= P['Feedback']
            s = s + g * B(k - n * D)
        y = x + (s - x) * mx
    elif ef == 1:
        y = x + (B(k - D) - x) * mx
    elif ef == 2:
        y = x + (lowpass(P['Cutoff'], P['Taps']) - x) * mx
    elif ef == 3:
        y = x + (np.clip(x - lowpass(P['Cutoff'], P['Taps']) + 128.0, 0, 255) - x) * mx
    elif ef == 4:
        st = 2.0 ** (8.0 - np.floor(P['Bits'] + 0.5))
        y = x + (np.floor(x / st) * st - x) * mx
    elif ef == 5:
        h = max(int(P['Hold'] + 0.5), 1)
        y = x + (B((k // h) * h) - x) * mx
    elif ef == 6:
        c = max(int(P['Chunk'] + 0.5), 2)
        b = (k // c) * c
        y = x + (B(b + c - 1 - (k - b)) - x) * mx
    elif ef == 7:
        a = P['Cutoff'] * (1.0 - P['Depth'] * (0.5 + 0.5 * np.sin(6.2831853 * P['Rate'] * k / 10000.0)))
        y = x + (lowpass(np.maximum(a, 0.001), P['Taps']) - x) * mx
    else:
        s, g = x.copy(), 1.0
        for n, mm in enumerate((1.0, 1.37, 1.71, 2.13)):
            g *= P['Feedback']
            s = s + g * B(k - int(np.float32(D) * np.float32(mm)) - n * int(P['Seed']))
        y = x + (s / (1.0 + P['Feedback']) - x) * mx
    return np.floor(np.clip(y, 0.0, 255.0) + 0.5)


def reference(img, pars=None, t=0.0):
    P = pars_of(pars)
    img = np.asarray(img, dtype=np.float64)
    if P['Amount'] <= 0:
        return img.copy()
    H, W = img.shape[:2]
    o = from_stream(bend(to_stream(img, int(P['Order'])), P, t), H, W, int(P['Order'])) / 255.0
    out = img.copy()
    out[..., :3] = img[..., :3] + (o - img[..., :3]) * P['Amount']
    return out


def compare(td_out, ref, tol=1.5 / 255.0):
    a = np.asarray(td_out, dtype=np.float64)[..., :3]
    b = np.clip(np.asarray(ref, dtype=np.float64), 0.0, 1.0)[..., :3]
    d = np.abs(a - b).max(-1)
    return {'max': float(d.max()), 'mean': float(d.mean()), 'within': float((d <= tol).mean())}
