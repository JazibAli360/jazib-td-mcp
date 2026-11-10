"""fx_stylise_clean_logic - numpy mirror of FX_stylise 'clean' (builders/fx_stylise_clean.py). Pure: no td.
median3(img) == med (per-channel 3x3 median, clamped); median_net(v) == the shader's exchange network on 9 values;
bilateral1(img, R, ss, sr, axis, luma) == one bilateral pass; clean(img, P) == the whole module. ASCII only."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import numpy as np  # noqa: E402
import fx_stylise_lib as X  # noqa: E402

NET = [(1, 2), (4, 5), (7, 8), (0, 1), (3, 4), (6, 7), (1, 2), (4, 5), (7, 8), (0, 3), (5, 8), (4, 7), (3, 6), (1, 4),
       (2, 5), (4, 7), (4, 2), (6, 4), (4, 2)]


def median_net(v):
    """The shader's network on a list of 9 arrays (elementwise) -> v[4]."""
    v = [np.array(x, dtype=np.float64) for x in v]
    for a, b in NET:
        lo, hi = np.minimum(v[a], v[b]), np.maximum(v[a], v[b])
        v[a], v[b] = lo, hi
    return v[4]


def _shift(img, dx, dy):
    H, W = img.shape[:2]
    ys = np.clip(np.arange(H) + dy, 0, H - 1)
    xs = np.clip(np.arange(W) + dx, 0, W - 1)
    return img[np.ix_(ys, xs)]


def median3(img):
    img = np.asarray(img, np.float64)
    st = np.stack([_shift(img, i, j) for j in (-1, 0, 1) for i in (-1, 0, 1)], 0)
    out = np.median(st[..., :3], axis=0)
    return np.concatenate([out, img[..., 3:]], -1)


def bilateral1(img, R, ss, sr, axis, lm=False):
    img = np.asarray(img, np.float64)
    c0 = img[..., :3]
    acc = c0.copy()
    ws = np.ones(img.shape[:2])
    is2 = 1.0 / (2.0 * max(ss * ss, 1e-6))
    ir2 = 1.0 / (2.0 * max(sr * sr, 1e-8))
    for i in range(1, int(R) + 1):
        for s in (1, -1):
            a = _shift(img, s * i, 0)[..., :3] if axis == 0 else _shift(img, 0, s * i)[..., :3]
            d = a - c0
            r = (d @ X.LUMA.astype(np.float64)) ** 2 if lm else (d * d).sum(-1)
            w = np.exp(-(i * i * is2 + r * ir2))
            acc += w[..., None] * a
            ws += w
    return np.concatenate([acc / ws[..., None], img[..., 3:]], -1)


def clean(img, P):
    c = np.asarray(img, np.float64)
    if P['Amount'] <= 0:
        return c.copy()
    s = median3(c) if P['Median'] else c
    lm = P['Rangemode'] == 1
    h = bilateral1(s, P['Radius'], P['Sigma'], P['Edge'], 0, lm)
    v = bilateral1(h, P['Radius'], P['Sigma'], P['Edge'], 1, lm)
    sm = v[..., :3]
    r = sm + P['Detail'] * (c[..., :3] - sm)
    o = np.concatenate([r, c[..., 3:]], -1)
    return c + (o - c) * P['Amount']


def noise_std(img, ref):
    return float((np.asarray(img, np.float64) - ref)[..., :3].std())
