# pop_terrain_logic - numpy mirror of POP_terrain's vertex maths (TC-19; builder builders/pop_terrain.py, doc
# docs/builds/pop_lane_h.md "TC-19"). Runs OUTSIDE TD (T-184): the LIVE CHECK dumps out1 in Style 'data' (r = height /
# Heightscale, g = world-fixed x, b = world-fixed z, a = 1) and compares it here, camera-free. Same hash / noise as
# pop_meshwarp_logic (imported, not copied). ASCII only.
import math

import numpy as np

import pop_meshwarp_logic as MW

STYLES = ['shaded', 'contour', 'wire', 'ramp', 'data']
STYLE_LABELS = ['Shaded (lambert)', 'Contour lines', 'Wire (grid lines)', 'Height colour ramp',
                'Data (r height/Heightscale, g x, b z; LIVE CHECK)']
MAXOCT = 8

DEFAULTS = {'extent': 40.0, 'lodpow': 2.0, 'freq': 0.08, 'heightscale': 6.0, 'octaves': 5, 'ridge': 0, 'seed': 1,
            'scroll': 0.0, 'cols': 160, 'rows': 160, 'snap': 1}


def params(**kw):
    p = dict(DEFAULTS)
    p.update(kw)
    return p


def remap(g, p):
    """Grid coord g in [-1, 1] -> world: sign(g) |g|^Lodpow Extent (dense round the camera at the origin)."""
    g = np.clip(np.asarray(g, dtype=np.float64), -1.0, 1.0)
    return np.sign(g) * np.abs(g) ** p['lodpow'] * p['extent']


def fbm(x, z, p):
    """Normalised fbm of value noise (0..1): octave o samples vnoise(W * Freq * 2^o, Seed + o), weight 0.5^o."""
    x = np.asarray(x, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    oct_ = int(min(max(p['octaves'], 1), MAXOCT))
    s, wsum, a, f = np.zeros_like(x), 0.0, 1.0, p['freq']
    for o in range(oct_):
        s = s + a * MW.vnoise(x * f, z * f, int(p['seed']) + o)
        wsum += a
        a *= 0.5
        f *= 2.0
    n = s / wsum
    if p['ridge']:
        n = 1.0 - np.abs(2.0 * n - 1.0)
    return n


def height(x, z, p):
    return p['heightscale'] * fbm(x, z, p)


def cell(p):
    """Finest grid spacing (round the camera) = Extent (2 / (Rows - 1))^Lodpow."""
    return p['extent'] * (2.0 / max(p['rows'] - 1.0, 1.0)) ** p['lodpow']


def snapped(p):
    return math.floor(p['scroll'] / cell(p)) * cell(p) if p['snap'] else p['scroll']


def vertices(p):
    """Every grid vertex: render position (x, h, z_render) and world-fixed (Wx, Wz) as the vertex shader does."""
    gx = np.linspace(-1.0, 1.0, int(p['cols']))
    gy = np.linspace(-1.0, 1.0, int(p['rows']))
    GX, GY = np.meshgrid(gx, gy)
    x, zg = remap(GX, p), remap(GY, p)
    sn = snapped(p)
    Wx, Wz = x, zg - sn
    h = height(Wx, Wz, p)
    return np.stack([x, h, zg - sn + p['scroll']], -1), np.stack([Wx, Wz], -1)


def interp_error(p, n=4000, rng=None):
    """Height error of linear interpolation inside one grid cell (what a data-style pixel shows) at random cells:
    returns |h(mid) - mean(h(corners))| / Heightscale samples. Sets the LIVE CHECK tolerance."""
    rng = rng or np.random.default_rng(0)
    i = rng.integers(0, int(p['cols']) - 1, n)
    j = rng.integers(0, int(p['rows']) - 1, n)
    g = lambda k, m: -1.0 + 2.0 * k / (m - 1.0)
    x0, x1 = remap(g(i, p['cols']), p), remap(g(i + 1, p['cols']), p)
    z0, z1 = remap(g(j, p['rows']), p), remap(g(j + 1, p['rows']), p)
    sn = snapped(p)
    z0, z1 = z0 - sn, z1 - sn
    c = (height(x0, z0, p) + height(x1, z0, p) + height(x0, z1, p) + height(x1, z1, p)) / 4.0
    m = height((x0 + x1) / 2, (z0 + z1) / 2, p)
    return np.abs(m - c) / p['heightscale']


def check_data(arr, p, tol_med=0.01, tol_p99=0.05):
    """LIVE CHECK on a dumped Style 'data' frame (H x W x 4 float): r vs height(g, b)/Heightscale on covered pixels.
    Returns a dict with coverage, median / p99 abs error, extents of g / b and pass."""
    a = np.asarray(arr, dtype=np.float64)
    m = a[..., 3] > 0.5
    if not m.any():
        return {'pass': False, 'cover': 0.0}
    r, wx, wz = a[..., 0][m], a[..., 1][m], a[..., 2][m]
    err = np.abs(r - fbm(wx, wz, p))
    out = {'cover': float(m.mean()), 'med': float(np.median(err)), 'p99': float(np.percentile(err, 99)),
           'xmin': float(wx.min()), 'xmax': float(wx.max()), 'zmin': float(wz.min()), 'zmax': float(wz.max())}
    out['pass'] = out['med'] <= tol_med and out['p99'] <= tol_p99
    return out
