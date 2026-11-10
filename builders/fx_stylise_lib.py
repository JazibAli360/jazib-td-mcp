"""fx_stylise_lib - GLSL snippets + their numpy mirrors shared by FX_stylise / FX_glass modules (boil, ink, saber,
watercolour, engrave, glass ...; 2+ users each, no-bloat rule). Pure: no td. Images (H, W, C) row 0 = bottom.
GLSL_LIB: lb32 / hsh (lowbias32 hash -> 0..1), vnoise (value noise, smooth), vnoise2, luma, bilin helpers.
ASCII only."""
import numpy as np

GLSL_LIB = """
uint lb32(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hsh(ivec2 c, uint s) { return float(lb32(uint(c.x) * 1597334677u ^ lb32(uint(c.y) ^ (s * 2654435761u)))) * (1.0 / 4294967296.0); }
float vnoise(vec2 x, uint s) {
    vec2 i = floor(x), f = fract(x);
    vec2 u = f * f * (3.0 - 2.0 * f);
    ivec2 c = ivec2(i);
    float a = hsh(c, s), b = hsh(c + ivec2(1, 0), s), d = hsh(c + ivec2(0, 1), s), e = hsh(c + ivec2(1, 1), s);
    return mix(mix(a, b, u.x), mix(d, e, u.x), u.y);
}
vec2 vnoise2(vec2 x, uint s) { return vec2(vnoise(x, s), vnoise(x + vec2(17.31, 9.73), s + 101u)); }
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
"""

LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)
U = np.uint32


def lb32(x):
    x = np.asarray(x, np.uint32).copy()
    with np.errstate(over='ignore'):
        x ^= x >> U(16)
        x = (x * U(0x7feb352d)).astype(np.uint32)
        x ^= x >> U(15)
        x = (x * U(0x846ca68b)).astype(np.uint32)
        x ^= x >> U(16)
    return x


def hsh(cx, cy, s):
    """== hsh(ivec2(cx, cy), s) (negative ints wrap like uint())."""
    cx = np.asarray(cx, np.int64).astype(np.uint32)
    cy = np.asarray(cy, np.int64).astype(np.uint32)
    with np.errstate(over='ignore'):
        a = (cx * U(1597334677)).astype(np.uint32)
        b = lb32(cy ^ (U(int(s) & 0xffffffff) * U(2654435761)).astype(np.uint32))
    return lb32(a ^ b).astype(np.float64) * (1.0 / 4294967296.0)


def vnoise(x, y, s):
    x = np.asarray(x, np.float64)
    y = np.asarray(y, np.float64)
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    ix, iy = ix.astype(np.int64), iy.astype(np.int64)
    a, b = hsh(ix, iy, s), hsh(ix + 1, iy, s)
    d, e = hsh(ix, iy + 1, s), hsh(ix + 1, iy + 1, s)
    return (a + (b - a) * ux) + ((d + (e - d) * ux) - (a + (b - a) * ux)) * uy


def vnoise2(x, y, s):
    return vnoise(x, y, s), vnoise(np.asarray(x) + 17.31, np.asarray(y) + 9.73, int(s) + 101)


def luma(c):
    return np.asarray(c, np.float32)[..., :3] @ LUMA


def bilinear(img, px, py):
    """TD texture() at pixel coords (px, py) (texel centres at +0.5), inputextenduv hold: img (H, W, C)."""
    img = np.asarray(img, np.float32)
    H, W = img.shape[:2]
    x = np.clip(np.asarray(px, np.float64) - 0.5, 0, W - 1)
    y = np.clip(np.asarray(py, np.float64) - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    return ((img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy) + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy)


def grid(H, W):
    py, px = np.mgrid[0:H, 0:W].astype(np.float64)
    return px, py


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / np.where(b - a == 0, 1e-9, b - a), 0, 1)
    return t * t * (3 - 2 * t)


def compare(a, b, tol=2.0 / 255):
    d = np.abs(np.asarray(a, np.float64) - np.asarray(b, np.float64))
    return {'max': float(d.max()), 'mean': float(d.mean()), 'over_tol': float((d.max(-1) > tol).mean())}
