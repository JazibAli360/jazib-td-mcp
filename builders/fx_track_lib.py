"""fx_track_lib - shared GLSL + numpy mirrors of FX_track (lane F, 27 Oct 2026; doc docs/builds/fx_track.md).
Used by the rack tracker (det / cells / pts passes in builders/fx_track.py) and the modules plexus, hud, analytics (2+
users each: no-bloat rule). Pure: no td. Images (H, W, C) with row 0 = bottom (TD texture order).

Points texture `trk_pts` (rgba32f, width 4 * FT_SIDE, height ceil(N / FT_SIDE)); point i -> texels
((i % FT_SIDE) * 4 + k, i // FT_SIDE):
  T0 = world x, y, 0, valid      (x, y on PX_lines' own camera plane z = 0; absent: x = 1e4 + 10 i, y = 1e4)
  T1 = centre u, v, strength, fill   (uv 0..1, v up)
  T2 = box u0, v0, u1, v1
  T3 = id, age s, velocity u/s, velocity v/s
Detectors: cells (GPU: one point per grid cell = key-weighted centroid of the pixels over Threshold, box = their
bounds) or blobs (Blob Track TOP, OpenCV, CPU; Script TOP `bt_pack` packs its Info DAT rows).
Font: builders/fx_retro_font8x8.py (dhepper font8x8, Public Domain), read-only reuse. ASCII only."""
import math
import os
import sys

import numpy as np

_HERE = globals().get('HERE') or os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import fx_retro_font8x8 as _F8  # noqa: E402

FT_SIDE = 64
FT_STRIDE = 4
FT_REACH = 4                 # cells searched each side of a pixel's cell (bounded loops, T-124)
FT_MAXBLOBS = 256
KEYS = [('bright', 'Bright (luma)'), ('dark', 'Dark (1 - luma)'), ('motion', 'Motion (frame difference)'),
        ('brightmotion', 'Bright x motion'), ('alpha', 'Alpha (mask TOP)'), ('red', 'Red (mask TOP / matte)')]
DETECTORS = [('cells', 'Cells (GPU grid, centroid + bounds)'), ('blobs', 'Blob Track TOP (OpenCV, ids)')]
LABELS = [('none', 'None'), ('id', 'ID 017'), ('tag', '#017'), ('position', 'X0512 Y0960 (px)'),
          ('idpos', 'ID + position'), ('idspeed', 'ID + speed px/s'), ('idage', 'ID + age s'),
          ('tagpos', '#tag + position')]
LABEL_LINES = {0: (0, 0), 1: (1, 0), 2: (5, 0), 3: (2, 0), 4: (1, 2), 5: (1, 3), 6: (1, 4), 7: (5, 2)}
LINE_LEN = {0: 0, 1: 6, 2: 11, 3: 6, 4: 7, 5: 4, 6: 9, 7: 10, 8: 12, 9: 6, 10: 8}
COLSRC = [('solid', 'Solid colour'), ('id', 'Palette by id'), ('strength', 'Palette by strength'),
          ('speed', 'Palette by speed')]
WX = 5.0 * math.tan(math.radians(22.5))   # PX_lines' own camera: tz 5, fov 45 (horizontal) -> half width at z = 0


def font_words():
    """ASCII 32..127 -> 192 uints: word 2c = rows 0-3, 2c + 1 = rows 4-7 (row r at bits 8 (r % 4) .. +7, bit 0 =
    leftmost pixel, row 0 = top)."""
    g = dict((cp, bytes.fromhex(h)) for cp, h in _F8.GLYPHS if cp < 128)
    out = []
    for c in range(32, 128):
        b = g.get(c, bytes(8))
        out.append(b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24))
        out.append(b[4] | (b[5] << 8) | (b[6] << 16) | (b[7] << 24))
    return out


FONT = font_words()


def font_bytes():
    """768 glyph row bytes (ASCII 32..127 x 8 rows, row 0 top, bit 0 = leftmost) = the font row of trk_pts."""
    g = dict((cp, bytes.fromhex(h)) for cp, h in _F8.GLYPHS if cp < 128)
    return [b for c in range(32, 128) for b in g.get(c, bytes(8))]


FONT_BYTES = font_bytes()
FONT_GLSL = "const float FT_FONTB[768] = float[768](%s);\n" % ', '.join('%d.0' % b for b in FONT_BYTES)

GLSL_LIB = """
// ---- FX_track common (builders/fx_track_lib.py). Needs: #define FT_PTS sTD2DInputs[k] and uniform vec4 uG
// (detector 0 cells / 1 blobs, cells x, cells y, point count N).
#define FT_SIDE %d
#define FT_REACH %d
vec4 ftT(int i, int k) { return texelFetch(FT_PTS, ivec2((i %% FT_SIDE) * 4 + k, i / FT_SIDE), 0); }
// font = the LAST row of trk_pts: byte b = glyph (code - 32) row r (0 top) at b = 8 (code - 32) + r, texel b / 4,
// channel b %% 4 (a const array here would be copied per thread: slow, T-141 / T-187)
float ftGlyph(int code, ivec2 q) {
    if (code < 32 || code > 127 || q.x < 0 || q.y < 0 || q.x > 7 || q.y > 7) return 0.0;
    int b = (code - 32) * 8 + q.y;
    vec4 t = texelFetch(FT_PTS, ivec2(b / 4, textureSize(FT_PTS, 0).y - 1), 0);
    uint w = uint(t[b %% 4] + 0.5);
    return float((w >> uint(q.x)) & 1u);
}
// integer digits (pow() in float32 is not exact: 1500 / pow(10, 2) gave a '4', live 31550)
int ftDig(float v, int place) {
    int iv = int(floor(min(max(v, 0.0), 2.0e9)));
    int p10 = place <= 0 ? 1 : place == 1 ? 10 : place == 2 ? 100 : place == 3 ? 1000 : place == 4 ? 10000 : 100000;
    return 48 + (iv / p10) %% 10;
}
int ftLineLen(int kind) {
    if (kind == 1) return 6; if (kind == 2) return 11; if (kind == 3) return 6; if (kind == 4) return 7;
    if (kind == 5) return 4; if (kind == 6) return 9; if (kind == 7) return 10; if (kind == 8) return 12;
    if (kind == 9) return 6; if (kind == 10) return 8; return 0;
}
// line kinds: 1 "ID 017" (v.x id), 2 "X0512 Y0960" (v.y, v.z px), 3 "V 0123" (v.w px/s), 4 "T 012.3" (v.w s),
// 5 "#017", 6 "COUNT 012", 7 "MOVING 004", 8 "REC 00:01:23" (v.x s), 9 "CAM 01", 10 "Z01 045%%" (v.x zone, v.y pct)
int ftChar(int kind, int k, vec4 v) {
    if (kind == 1) { if (k == 0) return 73; if (k == 1) return 68; if (k == 2) return 32; return ftDig(v.x, 5 - k); }
    if (kind == 2) { if (k == 0) return 88; if (k == 5) return 32; if (k == 6) return 89;
                     if (k < 5) return ftDig(v.y, 4 - k); return ftDig(v.z, 10 - k); }
    if (kind == 3) { if (k == 0) return 86; if (k == 1) return 32; return ftDig(v.w, 5 - k); }
    if (kind == 4) { if (k == 0) return 84; if (k == 1) return 32; if (k == 5) return 46;
                     if (k == 6) return ftDig(v.w * 10.0, 0); return ftDig(v.w, 4 - k); }
    if (kind == 5) { if (k == 0) return 35; return ftDig(v.x, 3 - k); }
    if (kind == 6) { if (k < 6) return int[6](67, 79, 85, 78, 84, 32)[k]; return ftDig(v.x, 8 - k); }
    if (kind == 7) { if (k < 7) return int[7](77, 79, 86, 73, 78, 71, 32)[k]; return ftDig(v.x, 9 - k); }
    if (kind == 8) { if (k < 4) return int[4](82, 69, 67, 32)[k]; if (k == 6 || k == 9) return 58;
                     if (k < 6) return ftDig(floor(v.x / 3600.0), 5 - k);
                     if (k < 9) return ftDig(floor(mod(v.x, 3600.0) / 60.0), 8 - k);
                     return ftDig(floor(mod(v.x, 60.0)), 11 - k); }
    if (kind == 9) { if (k < 4) return int[4](67, 65, 77, 32)[k]; return ftDig(v.x, 5 - k); }
    if (kind == 10) { if (k == 0) return 90; if (k == 3) return 32; if (k == 7) return 37;
                      if (k < 3) return ftDig(v.x, 2 - k); return ftDig(v.y, 6 - k); }
    return 32;
}
// one text line, bottom-left corner org (px), glyph pixel sc px: 1 on a set font pixel
float ftText(vec2 p, vec2 org, float sc, int kind, vec4 v) {
    vec2 d = (p - org) / max(sc, 1e-3);
    int n = ftLineLen(kind);
    if (d.x < 0.0 || d.y < 0.0 || d.y >= 8.0 || d.x >= float(8 * n)) return 0.0;
    int qx = int(floor(d.x)), qy = int(floor(d.y));
    int k = qx / 8;
    return ftGlyph(ftChar(kind, k, v), ivec2(qx - 8 * k, 7 - qy));
}
// candidate points near uv: cells = the pixel's cell +- reach (reach in uv, <= FT_REACH cells), blobs = all N
ivec4 ftRange(vec2 uv, vec2 reach) {
    if (uG.x < 0.5) {
        ivec2 cn = ivec2(max(uG.yz, vec2(1.0)));
        ivec2 c = clamp(ivec2(floor(uv * vec2(cn))), ivec2(0), cn - 1);
        ivec2 r = min(ivec2(ceil(reach * vec2(cn))), ivec2(FT_REACH));
        return ivec4(max(c - r, ivec2(0)), min(c + r, cn - 1));
    }
    return ivec4(0, 0, int(uG.w) - 1, 0);
}
// asymmetric: points up to rneg below / left of the pixel and rpos above / right (labels grow right + up)
ivec4 ftRange2(vec2 uv, vec2 rneg, vec2 rpos) {
    if (uG.x < 0.5) {
        ivec2 cn = ivec2(max(uG.yz, vec2(1.0)));
        ivec2 c = clamp(ivec2(floor(uv * vec2(cn))), ivec2(0), cn - 1);
        ivec2 rn = min(ivec2(ceil(rneg * vec2(cn))), ivec2(FT_REACH));
        ivec2 rp = min(ivec2(ceil(rpos * vec2(cn))), ivec2(FT_REACH));
        return ivec4(max(c - rn, ivec2(0)), min(c + rp, cn - 1));
    }
    return ivec4(0, 0, int(uG.w) - 1, 0);
}
int ftIndex(int x, int y) { return uG.x < 0.5 ? y * int(uG.y) + x : x; }
uint ftH(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float ftHash(float id, uint s) { return float(ftH(uint(max(id, 0.0)) * 747796405u ^ ftH(s + 0x9e3779b9u))) / 4294967296.0; }
""" % (FT_SIDE, FT_REACH)

# candidate loops in the shaders (bounded: y <= 2 FT_REACH + 1 rows, x <= 256 columns; T-124)
LOOP_OPEN = """    ivec4 rg = ftRange(uv, reach);
    for (int jy = 0; jy < 2 * FT_REACH + 1; jy++) {
        int cy = rg.y + jy;
        if (cy > rg.w) break;
        for (int jx = 0; jx < 256; jx++) {
            int cx = rg.x + jx;
            if (cx > rg.z) break;
            int i = ftIndex(cx, cy);
            vec4 T0 = ftT(i, 0);
            if (T0.w < 0.5) continue;
            vec4 T1 = ftT(i, 1), T2 = ftT(i, 2), T3 = ftT(i, 3);
"""
# hud variant: asymmetric range (rneg / rpos); T1 / T2 fetched only after the cheap T0 / T3 tests (CULL = a GLSL
# condition on T0 / T3 that skips the point)
LOOP_OPEN2 = """    ivec4 rg = ftRange2(uv, rneg, rpos);
    for (int jy = 0; jy < 2 * FT_REACH + 1; jy++) {
        int cy = rg.y + jy;
        if (cy > rg.w) break;
        for (int jx = 0; jx < 256; jx++) {
            int cx = rg.x + jx;
            if (cx > rg.z) break;
            int i = ftIndex(cx, cy);
            vec4 T0 = ftT(i, 0);
            if (T0.w < 0.5) continue;
            vec4 T3 = ftT(i, 3);
            if (CULL) continue;
            vec4 T1 = ftT(i, 1), T2 = ftT(i, 2);
"""
LOOP_CLOSE = """        }
    }
"""


# ------------------------------------------------------------------ numpy mirrors
LUMA = np.array([0.2126, 0.7152, 0.0722])


def glyph(code, qx, qy):
    if code < 32 or code > 127 or qx < 0 or qy < 0 or qx > 7 or qy > 7:
        return 0.0
    w = FONT[(code - 32) * 2 + (qy >> 2)]
    return float((w >> ((qy & 3) * 8 + qx)) & 1)


def dig(v, place):
    iv = int(math.floor(min(max(v, 0.0), 2.0e9)))
    return 48 + (iv // 10 ** max(min(place, 5), 0)) % 10


def line_chars(kind, v):
    """The characters of a line kind (= ftChar for k < ftLineLen)."""
    x, y, z, w = (list(v) + [0, 0, 0, 0])[:4]
    n = LINE_LEN.get(kind, 0)
    out = []
    for k in range(n):
        if kind == 1:
            c = [73, 68, 32][k] if k < 3 else dig(x, 5 - k)
        elif kind == 2:
            c = 88 if k == 0 else 32 if k == 5 else 89 if k == 6 else dig(y, 4 - k) if k < 5 else dig(z, 10 - k)
        elif kind == 3:
            c = [86, 32][k] if k < 2 else dig(w, 5 - k)
        elif kind == 4:
            c = 84 if k == 0 else 32 if k == 1 else 46 if k == 5 else dig(w * 10.0, 0) if k == 6 else dig(w, 4 - k)
        elif kind == 5:
            c = 35 if k == 0 else dig(x, 3 - k)
        elif kind == 6:
            c = [67, 79, 85, 78, 84, 32][k] if k < 6 else dig(x, 8 - k)
        elif kind == 7:
            c = [77, 79, 86, 73, 78, 71, 32][k] if k < 7 else dig(x, 9 - k)
        elif kind == 8:
            if k < 4:
                c = [82, 69, 67, 32][k]
            elif k in (6, 9):
                c = 58
            elif k < 6:
                c = dig(math.floor(x / 3600.0), 5 - k)
            elif k < 9:
                c = dig(math.floor((x % 3600.0) / 60.0), 8 - k)
            else:
                c = dig(math.floor(x % 60.0), 11 - k)
        elif kind == 9:
            c = [67, 65, 77, 32][k] if k < 4 else dig(x, 5 - k)
        elif kind == 10:
            c = 90 if k == 0 else 32 if k == 3 else 37 if k == 7 else dig(x, 2 - k) if k < 3 else dig(y, 6 - k)
        else:
            c = 32
        out.append(c)
    return out


def text_at(p, org, sc, kind, v):
    """= ftText at pixel centre p."""
    sc = max(sc, 1e-3)
    dx, dy = (p[0] - org[0]) / sc, (p[1] - org[1]) / sc
    n = LINE_LEN.get(kind, 0)
    if dx < 0 or dy < 0 or dy >= 8 or dx >= 8 * n:
        return 0.0
    qx, qy = int(math.floor(dx)), int(math.floor(dy))
    k = qx // 8
    return glyph(line_chars(kind, v)[k], qx - 8 * k, 7 - qy)


def text_string(kind, v):
    return ''.join(chr(c) for c in line_chars(kind, v))


def lb32(x):
    x &= 0xffffffff
    x ^= x >> 16
    x = (x * 0x7feb352d) & 0xffffffff
    x ^= x >> 15
    x = (x * 0x846ca68b) & 0xffffffff
    x ^= x >> 16
    return x


def fthash(idv, s):
    return float(lb32(((int(max(idv, 0.0)) & 0xffffffff) * 747796405) & 0xffffffff ^ lb32((s + 0x9e3779b9) & 0xffffffff))
                 ) / 4294967296.0


def bilinear(img, u, v):
    """TD texture() at uv (texel centres at +0.5), extend hold."""
    img = np.asarray(img, np.float64)
    H, W = img.shape[:2]
    x = np.clip(np.asarray(u) * W - 0.5, 0, W - 1)
    y = np.clip(np.asarray(v) * H - 0.5, 0, H - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, W - 1), np.minimum(y0 + 1, H - 1)
    fx, fy = (x - x0)[..., None], (y - y0)[..., None]
    return (img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy) + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy


def det_ref(src, prev, w, h, key, keygain, motiongain):
    """= the det pass: src picture (any size), prev = last det (h, w, 4) or None -> (h, w, 4) key, luma, motion, 1."""
    py, px = np.mgrid[0:h, 0:w].astype(np.float64)
    c = bilinear(src, (px + 0.5) / w, (py + 0.5) / h)
    L = c[..., :3] @ LUMA
    pl = prev[..., 1] if prev is not None and prev.shape[:2] == (h, w) else np.zeros((h, w))
    m = np.abs(L - pl) * motiongain
    k = [L, 1.0 - L, m, L * m, c[..., 3], c[..., 0]][int(key)] * keygain
    return np.stack([k, L, m, np.ones_like(L)], -1)


CELL_MAX = 128               # det pixels scanned per cell axis (bounded loop); larger cells are scanned partly


def cell_bounds(n, size, c):
    """= the cells pass: integer division, then at most CELL_MAX pixels."""
    a, b = (c * size) // n, ((c + 1) * size) // n
    return a, min(b, a + CELL_MAX)


def peak_hash(x, y):
    """= the cells pass tie-break hash (lb32 of x * 73856093 ^ y * 19349663, uint wrap) in 0..1."""
    M = 0xffffffff
    return lb32(((int(x) * 73856093) & M) ^ ((int(y) * 19349663) & M)) / 4294967296.0


def cells_ref(det, cx_n, cy_n, thr, pick=0):
    """= the cells pass -> (cy_n, 2 cx_n, 4): T0 point u v (pick 0 = peak: highest key + 0.02 hash, 1 = key-weighted
    centroid), fill, mean key; T1 box u0 v0 u1 v1 (pixel edges)."""
    H, W = det.shape[:2]
    out = np.zeros((cy_n, 2 * cx_n, 4))
    for cy in range(cy_n):
        y0, y1 = cell_bounds(cy_n, H, cy)
        for cx in range(cx_n):
            x0, x1 = cell_bounds(cx_n, W, cx)
            k = det[y0:y1, x0:x1, 0]
            tot = max(k.size, 1)
            on = k >= thr
            n = int(on.sum())
            mean = float(k.sum()) / tot
            if n == 0:
                out[cy, 2 * cx] = [(x0 + x1) / 2.0 / W, (y0 + y1) / 2.0 / H, 0.0, mean]
                out[cy, 2 * cx + 1] = [x0 / W, y0 / H, x1 / W, y1 / H]
                continue
            yy, xx = np.nonzero(on)
            wk = k[on]
            sw = max(float(wk.sum()), 1e-9)
            if int(pick) == 0:
                sc = np.array([wk[j] + 0.02 * peak_hash(xx[j] + x0, yy[j] + y0) for j in range(len(wk))], np.float32)
                j = int(np.argmax(sc))
                pu, pv = (xx[j] + x0 + 0.5) / W, (yy[j] + y0 + 0.5) / H
            else:
                pu, pv = float(((xx + x0 + 0.5) * wk).sum()) / sw / W, float(((yy + y0 + 0.5) * wk).sum()) / sw / H
            out[cy, 2 * cx] = [pu, pv, n / tot, mean]
            out[cy, 2 * cx + 1] = [(xx.min() + x0) / W, (yy.min() + y0) / H, (xx.max() + x0 + 1) / W,
                                   (yy.max() + y0 + 1) / H]
    return out


def n_points(detector, cx_n, cy_n, maxblobs):
    return int(cx_n * cy_n) if int(detector) == 0 else int(maxblobs)


def pts_shape(n):
    """(rows, width): point rows + the font row."""
    return (max(1, (n + FT_SIDE - 1) // FT_SIDE) + 1, FT_SIDE * FT_STRIDE)


def pts_ref(detector, cells, blobs, prev, n, cx_n, wx, wy, now, smooth, minfill):
    """= the pts pass -> (rows, 256, 4). cells (cy, 2cx, 4) or blobs (2, maxblobs, 4): row 0 u v w h, row 1 id age
    active 0; prev = the last pts or None."""
    rows, wid = pts_shape(n)
    out = np.zeros((rows, wid, 4))
    fb = FONT_BYTES + [0] * (wid * 4 - len(FONT_BYTES))
    out[rows - 1] = np.array(fb, np.float64).reshape(wid, 4)
    out[rows - 1, wid - 1] = [now, 0, 0, 0]
    hp = prev is not None and prev.shape == out.shape
    last = prev[rows - 1, wid - 1, 0] if hp else -1.0
    dt = now - last if last > 0 else -1.0
    for i in range((rows - 1) * FT_SIDE):
        x, y = (i % FT_SIDE) * 4, i // FT_SIDE
        if i >= n:
            out[y, x] = [1e4 + 10.0 * i, 1e4, 0, 0]
            continue
        if int(detector) == 0:
            cx, cy = i % cx_n, i // cx_n
            c0, c1 = cells[cy, 2 * cx], cells[cy, 2 * cx + 1]
            valid = c0[2] >= minfill and c0[2] > 0
            cen, stren, fill, box, idv, age = c0[:2].copy(), c0[3], c0[2], c1.copy(), float(i), 0.0
        else:
            b0, b1 = blobs[0, i], blobs[1, i]
            valid = b1[2] > 0.5
            cen, stren, fill = b0[:2].copy(), 1.0, 1.0
            box = np.array([b0[0] - b0[2] / 2, b0[1] - b0[3] / 2, b0[0] + b0[2] / 2, b0[1] + b0[3] / 2])
            idv, age = float(b1[0]), float(b1[1])
        vel = np.zeros(2)
        if valid and hp and 0 <= dt <= 0.25:
            p0, p1, p3 = prev[y, x], prev[y, x + 1], prev[y, x + 3]
            if p0[3] > 0.5 and p3[0] == idv:
                nc = cen * (1 - smooth) + p1[:2] * smooth
                vel = (nc - p1[:2]) / dt if dt > 0 else p3[2:4]
                cen = nc
                if int(detector) == 0:
                    age = p3[1] + dt
        if not valid:
            out[y, x] = [1e4 + 10.0 * i, 1e4, 0, 0]
            out[y, x + 1] = [cen[0], cen[1], stren, fill]
            out[y, x + 2] = box
            out[y, x + 3] = [idv, 0.0, 0.0, 0.0]
            continue
        out[y, x] = [(cen[0] - 0.5) * 2 * wx, (cen[1] - 0.5) * 2 * wy, 0.0, 1.0]
        out[y, x + 1] = [cen[0], cen[1], stren, fill]
        out[y, x + 2] = box
        out[y, x + 3] = [idv, age, vel[0], vel[1]]
    return out


def pt(pts, i, k):
    return pts[i // FT_SIDE, (i % FT_SIDE) * 4 + k]


def candidates(uv, reach, detector, cx_n, cy_n, n):
    """= ftRange + ftIndex: point indices a pixel at uv looks at."""
    if int(detector) == 0:
        c = [min(max(int(math.floor(uv[0] * cx_n)), 0), cx_n - 1), min(max(int(math.floor(uv[1] * cy_n)), 0), cy_n - 1)]
        r = [min(int(math.ceil(reach[0] * cx_n)), FT_REACH), min(int(math.ceil(reach[1] * cy_n)), FT_REACH)]
        return [y * cx_n + x for y in range(max(c[1] - r[1], 0), min(c[1] + r[1], cy_n - 1) + 1)
                for x in range(max(c[0] - r[0], 0), min(c[0] + r[0], cx_n - 1) + 1)]
    return list(range(min(int(n), 256)))


def candidates2(uv, rneg, rpos, detector, cx_n, cy_n, n):
    """= ftRange2 + ftIndex."""
    if int(detector) == 0:
        c = [min(max(int(math.floor(uv[0] * cx_n)), 0), cx_n - 1), min(max(int(math.floor(uv[1] * cy_n)), 0), cy_n - 1)]
        rn = [min(int(math.ceil(rneg[0] * cx_n)), FT_REACH), min(int(math.ceil(rneg[1] * cy_n)), FT_REACH)]
        rp = [min(int(math.ceil(rpos[0] * cx_n)), FT_REACH), min(int(math.ceil(rpos[1] * cy_n)), FT_REACH)]
        return [y * cx_n + x for y in range(max(c[1] - rn[1], 0), min(c[1] + rp[1], cy_n - 1) + 1)
                for x in range(max(c[0] - rn[0], 0), min(c[0] + rp[0], cx_n - 1) + 1)]
    return list(range(min(int(n), 256)))


def blob_rows(table_rows, maxblobs):
    """Blob Track Info DAT rows (dicts: id u v width height ... age) -> (2, maxblobs, 4) float32 for bt_pack
    (row 0 u v w h, row 1 id age active 0); first maxblobs rows, empty slots 0."""
    a = np.zeros((2, int(maxblobs), 4), np.float32)
    for i, r in enumerate(table_rows[:int(maxblobs)]):
        a[0, i] = [float(r['u']), float(r['v']), float(r['width']), float(r['height'])]
        a[1, i] = [float(r['id']), float(r.get('age', 0) or 0), 1.0 if str(r.get('active', '1')) != '0' else 0.0, 0.0]
    return a


def compare(a, b, tol=2.0 / 255):
    d = np.abs(np.asarray(a, np.float64) - np.asarray(b, np.float64))
    return {'max': float(d.max()) if d.size else 0.0, 'mean': float(d.mean()) if d.size else 0.0,
            'over_tol': float((d.reshape(len(d), -1).max(-1) > tol).mean()) if d.size else 0.0}


# colour helper for the modules that colour points (plexus dots, hud); needs px_palette.glsl before GLSL_LIB
GLSL_COL = """
// colour source: 0 solid, 1 palette by id hash, 2 palette by strength, 3 palette by speed / sref (px/s)
vec3 ftCol(int mode, vec3 solid, vec4 T1, vec4 T3, vec2 res, float sref) {
    if (mode == 1) return pxPal(ftHash(T3.x, 11u));
    if (mode == 2) return pxPal(T1.z);
    if (mode == 3) return pxPal(length(T3.zw * res) / max(sref, 1e-3));
    return solid;
}
"""


def col_ref(mode, solid, T1, T3, res, sref, pal):
    """= ftCol; pal(t) -> rgb (palette_map_logic.pal_eval bound to the live rows / ctl)."""
    if mode == 1:
        return np.array(pal(fthash(T3[0], 11)))
    if mode == 2:
        return np.array(pal(T1[2]))
    if mode == 3:
        return np.array(pal(math.hypot(T3[2] * res[0], T3[3] * res[1]) / max(sref, 1e-3)))
    return np.array(solid, np.float64)
