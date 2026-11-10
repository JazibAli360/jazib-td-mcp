# fx_time_logic - pure maths of the FX_glitch time modules 'timedisplace' (DG-13), 'timeshuffle' (DG-12) and
# 'feedbackkill' (DG-21). No TD. Each function mirrors the GLSL in builders/fx_glitch_<module>.py line for line, so
# the live lane can compare the GPU result with these references (docs/builds/fx_glitch_<module>.md LIVE CHECKS).
# Conventions: images are numpy arrays (H, W[, C]) with row 0 = TD pixel y 0 = the BOTTOM of the picture (TD texture
# space); u, v = pixel centre / size. Offsets are in ring cooks ("frames"), 0 = now. ASCII only.
import math

try:
    import numpy as np
except ImportError:          # pragma: no cover - TD and the tests have numpy
    np = None

M32 = 0xFFFFFFFF
LUMA = (0.2126, 0.7152, 0.0722)


# ------------------------------------------------------------------ hash (= GLSL pcg / h in every module shader)
def pcg(v):
    v &= M32
    s = (v * 747796405 + 2891336453) & M32
    w = (((s >> ((s >> 28) + 4)) ^ s) * 277803737) & M32
    return ((w >> 22) ^ w) & M32


def h(a, b, c, d):
    """GLSL h(uvec4(a, b, c, d)) -> [0, 1], 24-bit exact."""
    return float(pcg((a & M32) ^ pcg((b & M32) ^ pcg((c & M32) ^ pcg(d & M32)))) >> 8) / 16777215.0


def np_pcg(v):
    v = np.asarray(v).astype(np.uint64) & np.uint64(M32)
    s = (v * np.uint64(747796405) + np.uint64(2891336453)) & np.uint64(M32)
    w = (((s >> ((s >> np.uint64(28)) + np.uint64(4))) ^ s) * np.uint64(277803737)) & np.uint64(M32)
    return ((w >> np.uint64(22)) ^ w) & np.uint64(M32)


def np_h(a, b, c, d):
    """Vectorised h(); float32 like the GPU (int24 / 16777215.0 in float32)."""
    m = np.uint64(M32)
    u = lambda x: np.asarray(x).astype(np.int64).astype(np.uint64) & m     # noqa: E731 (two's complement wrap)
    x = np_pcg(u(a) ^ np_pcg(u(b) ^ np_pcg(u(c) ^ np_pcg(u(d)))))
    return (x >> np.uint64(8)).astype(np.float32) / np.float32(16777215.0)


# ------------------------------------------------------------------ ring sizes (timedisplace / timeshuffle)
def ring_depth(depth):
    """Ring slices actually allocated: max(2, int(Depth)). Offsets run 0 .. ring_depth - 1."""
    return max(2, int(depth))


def ring_key(depth, quality):
    """Stamp key: a change = a new ring (Depth or Quality changed) -> history restarts."""
    return ring_depth(depth) * 4 + (1 if quality == 'half' else 0)


def vram_mb(w, h_, depth, quality='full', bytes_px=4):
    """Ring VRAM in MB (texture3dTOP, input format; half = half width and height)."""
    s = 0.5 if quality == 'half' else 1.0
    return max(1, int(w * s)) * max(1, int(h_ * s)) * bytes_px * ring_depth(depth) / 1e6


def encode(off, depth):
    """Map grey the Time Machine reads (blackoffset -(D-1), whiteoffset 0). Measured on 31550 (T-122): it reads
    (1 - m) * D - 1 slices back (clamped to 0..D-1), so whole offset k needs m = 1 - (k + 1) / D; 0 = oldest slice."""
    return 1.0 - (off + 1.0) / float(max(ring_depth(depth), 2))


def decode_frame_code(cur, out):
    """LIVE CHECK helper: input = frame code r = (absTime.frame % 256) / 255 -> per pixel offset in frames."""
    d = np.round((np.asarray(cur, np.float64) - np.asarray(out, np.float64)) * 255.0)
    return np.mod(d, 256.0)


def ref_timemachine(ring, off):
    """Reference Time Machine read: ring = [frame_now, frame_1_ago, ...] (H, W[, C]); off (H, W) float frames;
    linear between slices (FX6 4b: interpolated)."""
    ring = np.asarray(ring, np.float64)
    off = np.clip(np.asarray(off, np.float64), 0, len(ring) - 1)
    i0 = np.floor(off).astype(int)
    i1 = np.minimum(i0 + 1, len(ring) - 1)
    f = off - i0
    yy, xx = np.indices(off.shape)
    a, b = ring[i0, yy, xx], ring[i1, yy, xx]
    if a.ndim == 3:
        f = f[..., None]
    return a * (1 - f) + b * f


# ------------------------------------------------------------------ timedisplace map (= fx_glitch_timedisplace MAP)
TD_MODES = ['ramp', 'radial', 'spiral', 'luma', 'noise', 'external']


def td_defaults():
    return {'Amount': 1.0, 'Depth': 32, 'Delay': 0.0, 'Mode': 0, 'Angle': 0.0, 'Centerx': 0.5, 'Centery': 0.5,
            'Twist': 0.0, 'Repeat': 1.0, 'Mirror': 0, 'Steps': 0, 'Invert': 0, 'Scale': 3.0, 'Speed': 0.2,
            'Phase': 0.0, 'Curve': 1.0, 'Smooth': 0.0, 'Seed': 1, 'Jitter': 0.0, 'Jittersize': 8.0,
            'Jitterrate': 8.0}


def _vn(x, y, z, s):
    """Value noise on the pcg lattice (= GLSL vn)."""
    ix, iy, iz = np.floor(x), np.floor(y), np.floor(z)
    fx, fy, fz = [(f * f * (3.0 - 2.0 * f)) for f in (x - ix, y - iy, z - iz)]
    ix, iy, iz = ix.astype(np.int64), iy.astype(np.int64), np.asarray(iz).astype(np.int64)
    v = [np_h(ix + (k & 1), iy + ((k >> 1) & 1), iz + ((k >> 2) & 1), s).astype(np.float64) for k in range(8)]
    lerp = lambda a, b, t: a + (b - a) * t      # noqa: E731
    return lerp(lerp(lerp(v[0], v[1], fx), lerp(v[2], v[3], fx), fy),
                lerp(lerp(v[4], v[5], fx), lerp(v[6], v[7], fx), fy), fz)


def td_shape(P, W, H, t=0.0, aspect=None, luma=None, ext=None):
    """Raw shape s (H, W) before wrap/curve/steps. aspect = picture W/H (default W/H); luma/ext = (H, W) arrays."""
    asp = float(W) / H if aspect is None else aspect
    yy, xx = np.indices((H, W)).astype(np.float64)
    u, v = (xx + 0.5) / W, (yy + 0.5) / H
    cx, cy = P['Centerx'], P['Centery']
    mode = int(P['Mode'])
    if mode == 0:
        a = math.radians(P['Angle'])
        dx, dy = math.sin(a), math.cos(a)
        return ((u - cx) * dx + (v - cy) * dy) / (abs(dx) + abs(dy)) + 0.5
    qx, qy = (u - cx) * asp, (v - cy)
    r = np.sqrt(qx * qx + qy * qy) / math.hypot(0.5 * asp, 0.5)
    if mode == 1:
        return r
    if mode == 2:
        w = np.arctan2(qy, qx) / (2 * math.pi) + 0.5 + r * P['Twist']
        return w - np.floor(w)
    if mode == 3:
        return np.asarray(luma, np.float64)
    if mode == 4:
        s = (int(P['Seed']) * 7919) & M32
        x, y, z = u * asp * P['Scale'], v * P['Scale'], np.full_like(u, t * P['Speed'])
        n = _vn(x, y, z, s) * 0.667 + _vn(x * 2.03 + 17.0, y * 2.03 + 17.0, z * 2.03 + 17.0, s + 1) * 0.333
        return np.clip(n, 0.0, 1.0)
    return np.asarray(ext, np.float64)


def td_offsets(P, W, H, n=1e9, t=0.0, pic_h=None, aspect=None, luma=None, ext=None, prev_off=None):
    """Offsets in frames (H, W) the timedisplace map encodes, = MAP main(). n = stamp count (cooks since the ring
    restarted); prev_off = the previous map's offsets (Smooth)."""
    s = td_shape(P, W, H, t, aspect, luma, ext)
    w = s * P['Repeat'] + P['Phase'] * t
    if P['Mirror']:
        s = 1.0 - np.abs((w * 0.5 - np.floor(w * 0.5)) * 2.0 - 1.0)
    elif abs(P['Repeat'] - 1.0) > 1e-6 or P['Phase'] != 0.0:
        s = w - np.floor(w)
    else:
        s = np.clip(s, 0.0, 1.0)
    s = np.power(np.maximum(s, 0.0), max(P['Curve'], 1e-3))
    if P['Jitter'] != 0.0:
        ph = pic_h or H
        yy = np.indices((H, W))[0].astype(np.float64)
        row = np.floor((yy + 0.5) / H * ph / max(P['Jittersize'], 1.0)).astype(np.int64)
        ep = int(math.floor(t * P['Jitterrate']))
        s = np.clip(s + (np_h(row, ep, int(P['Seed']), 3).astype(np.float64) - 0.5) * P['Jitter'], 0.0, 1.0)
    if P['Steps'] >= 2:
        s = np.minimum(np.floor(s * P['Steps']) / (P['Steps'] - 1.0), 1.0)
    if P['Invert']:
        s = 1.0 - s
    D = float(max(ring_depth(P['Depth']) - 1, 1))
    off = P['Delay'] + s * P['Amount'] * D
    if n > 0.5 and P['Smooth'] > 0.0 and prev_off is not None:
        off = off + (np.asarray(prev_off) - off) * P['Smooth']
    return np.clip(off, 0.0, min(D, n))


# ------------------------------------------------------------------ timeshuffle (= fx_glitch_timeshuffle MAP)
TS_MODES = ['random', 'permute', 'reverse', 'hold', 'luma', 'wave', 'cadence']
TS_SHAPES = ['squares', 'rows', 'columns']


def ts_defaults():
    return {'Amount': 1.0, 'Depth': 32, 'Mode': 0, 'Length': 16, 'Blocksize': 64.0, 'Shape': 0, 'Chance': 1.0,
            'Rate': 4.0, 'Perblock': 0, 'Gridshift': 0.0, 'Seed': 1, 'Angle': 0.0, 'Repeat': 1.0, 'Phase': 0.0,
            'Invert': 0}


def perm(i, L, key):
    """Bijection on [0, L) (= GLSL perm): cycle-walk a bit mix on the next power of two."""
    L = max(1, int(L))
    P = 1
    while P < L:
        P <<= 1
    M = P - 1
    r = max(1, (P.bit_length() - 1) // 2)
    x = int(i) & M32
    for _ in range(512):
        x = (x * 5 + (key & M)) & M
        x ^= x >> r
        x = (x * 9 + ((key >> 8) & M)) & M
        x ^= x >> 1
        if x < L:
            break
    return x


def ts_block_offset(P, bx, by, n, t, W, H, cell, g, picture_luma=None):
    """Offset k (frames, before the ring clamp) of block (bx, by). cell, g = block size and grid shift (px)."""
    seed = (int(P['Seed']) * 7919) & M32
    mode = int(P['Mode'])
    L = float(max(1, int(math.floor(P['Length']))))
    ep = int(math.floor(np.float32(t) * np.float32(P['Rate'])))
    ce = ep
    if mode == 0:
        k = math.floor(np.float32(h(bx, by, ep, seed)) * np.float32(L))
    elif mode <= 3:
        c = float(n) + (math.floor(np.float32(h(bx, by, seed, 11)) * np.float32(L)) if P['Perblock'] else 0.0)
        chunk = math.floor(c / L)
        i = c - chunk * L
        ce = int(chunk)
        if mode == 1:
            blk = pcg(bx ^ pcg(by)) if P['Perblock'] else 0
            key = pcg(int(chunk) ^ pcg(seed ^ blk))
            k = i + L - perm(int(i), int(L), key)
        elif mode == 2:
            k = 2.0 * i
        else:
            k = i
    else:
        cx, cy = (bx + 0.5) * cell[0] - g[0], (by + 0.5) * cell[1] - g[1]
        if mode == 4:
            px = int(min(max(math.floor(cx), 0), W - 1))
            py = int(min(max(math.floor(cy), 0), H - 1))
            s = float(picture_luma[py, px]) if picture_luma is not None else 0.0
        else:
            a = math.radians(P['Angle'])
            dx, dy = math.sin(a), math.cos(a)
            s = ((cx / W - 0.5) * dx + (cy / H - 0.5) * dy) / (abs(dx) + abs(dy)) + 0.5
            w = s * P['Repeat'] + P['Phase'] * t
            s = 1.0 - abs((w * 0.5 - math.floor(w * 0.5)) * 2.0 - 1.0)
        if P['Invert']:
            s = 1.0 - s
        k = math.floor(s * (L - 1.0) + 0.5)
    if np.float32(h(bx, by, ce, seed + 5)) >= np.float32(P['Chance']) * np.float32(P['Amount']):
        k = 0.0
    return float(k)


def ts_grid(P, W, H, t):
    """Block cell size (px) and grid shift (px) for this epoch (= GLSL)."""
    seed = (int(P['Seed']) * 7919) & M32
    bs = max(1.0, math.floor(P['Blocksize']))
    shp = int(P['Shape'])
    cell = (float(W) if shp == 1 else bs, float(H) if shp == 2 else bs)
    ep = int(math.floor(np.float32(t) * np.float32(P['Rate'])))
    g = (math.floor(np.float32(h(ep, seed, 1, 9)) * np.float32(P['Gridshift']) * np.float32(bs)),
         math.floor(np.float32(h(ep, seed, 2, 9)) * np.float32(P['Gridshift']) * np.float32(bs)))
    return cell, g


def ts_offsets(P, W, H, n=1e9, t=0.0, picture_luma=None):
    """Per-pixel offsets (H, W) in frames, after the ring clamp (= what the map encodes)."""
    cell, g = ts_grid(P, W, H, t)
    yy, xx = np.indices((H, W))
    bx = np.floor((xx + g[0]) / cell[0]).astype(np.int64)
    by = np.floor((yy + g[1]) / cell[1]).astype(np.int64)
    D = float(max(ring_depth(P['Depth']) - 1, 1))
    out = np.zeros((H, W))
    cache = {}
    for key in set(zip(bx.ravel().tolist(), by.ravel().tolist())):
        cache[key] = ts_block_offset(P, key[0], key[1], n, t, W, H, cell, g, picture_luma)
    for (kx, ky), k in cache.items():
        out[(bx == kx) & (by == ky)] = k
    return np.clip(out, 0.0, min(D, n))


# ------------------------------------------------------------------ feedbackkill (= fx_glitch_feedbackkill FX)
FK_FEEDS = ['mix', 'lighten', 'darken', 'difference', 'add']
FK_EDGES = ['mirror', 'repeat', 'clamp', 'black']


def fk_defaults():
    return {'Amount': 1.0, 'Leak': 0.08, 'Feed': 0, 'Key': 0.0, 'Decay': 1.0, 'Rate': 0.0, 'Hold': 0, 'Reset': 0,
            'Precision': 0, 'Zoom': 1.0, 'Rotate': 0.0, 'Shiftx': 0.0, 'Shifty': 0.0, 'Centerx': 0.5,
            'Centery': 0.5, 'Edge': 0, 'Displace': 0.0, 'Curl': 0, 'Radius': 1.5, 'Soften': 0.0, 'Sharpen': 0.0,
            'Burn': 0.0, 'Huestep': 0.0, 'Saturation': 1.0, 'Contrast': 1.0, 'Bright': 0.0, 'Fold': 0.0,
            'Crush': 0, 'Dither': 0.0, 'Noise': 0.0, 'Autogain': 0.0, 'Target': 0.45, 'Seed': 1}


def lum(c):
    c = np.asarray(c, np.float64)
    return c[..., 0] * LUMA[0] + c[..., 1] * LUMA[1] + c[..., 2] * LUMA[2]


def hue_rotate(c, deg):
    """Rodrigues rotation about the grey axis: exact identity at 0, keeps r+g+b; 120 deg maps r -> g -> b."""
    c = np.asarray(c, np.float64)
    a = math.radians(deg)
    k = np.array([1.0, 1.0, 1.0]) / math.sqrt(3.0)
    cr = np.cross(np.broadcast_to(k, c.shape), c)
    return c * math.cos(a) + cr * math.sin(a) + k * (c @ k)[..., None] * (1.0 - math.cos(a))


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def fk_colour(c, live, P, mean=0.5, dz=None, nz=None):
    """Point-wise part of one generation (= GLSL kill()). c = sampled previous state after geometry/filters,
    live = live picture (both (..., 3)); dz / nz = dither / noise hashes in [0, 1] (..., 3) or None."""
    c = np.asarray(c, np.float64).copy()
    live = np.asarray(live, np.float64)
    if P['Huestep'] != 0.0:
        c = hue_rotate(c, P['Huestep'])
    y = lum(c)[..., None]
    c = y + (c - y) * P['Saturation']
    c = (c - 0.5) * P['Contrast'] + 0.5 + P['Bright']
    if P['Fold'] > 0.0:
        c = 1.0 - np.abs(1.0 - np.mod(c * (1.0 + P['Fold']), 2.0))
    c = c * P['Decay']
    kw = 1.0 if P['Key'] <= 0.0 else smoothstep(P['Key'] - 0.05, P['Key'] + 0.05, lum(live))[..., None]
    Lk = P['Leak'] * kw
    f = int(P['Feed'])
    if f == 0:
        c = c + (live - c) * Lk
    elif f == 1:
        c = np.maximum(c, live * Lk)
    elif f == 2:
        c = np.minimum(c, 1.0 + (live - 1.0) * Lk)
    elif f == 3:
        c = np.abs(c - live * Lk)
    else:
        c = c + live * Lk
    if P['Autogain'] > 0.0:
        g = P['Target'] / max(mean, 0.02)
        c = c * (1.0 + (g - 1.0) * 0.2 * P['Autogain']) + (P['Target'] - mean) * 0.05 * P['Autogain']
    if P['Crush'] >= 1:
        lv = 2.0 ** math.floor(P['Crush']) - 1.0
        d = (np.asarray(dz) - 0.5) * P['Dither'] if (P['Dither'] > 0.0 and dz is not None) else 0.0
        c = np.floor(c * lv + 0.5 + d) / lv
    if P['Noise'] > 0.0 and nz is not None:
        c = c + (np.asarray(nz) - 0.5) * P['Noise']
    return np.clip(c, 0.0, 1.0)


def fk_edge(q, size, edge):
    """Edge fold of a pixel-space coordinate (= GLSL edgep). edge 3 (black) is handled by the caller."""
    if edge == 1:
        return np.mod(q, size)
    if edge == 0:
        t_ = np.mod(q, 2.0 * size)
        return np.minimum(t_, 2.0 * size - t_)
    return np.clip(q, 0.5, size - 0.5)


def fk_shift(img, sx, sy, edge=0):
    """One generation of an integer shift (Zoom 1, Rotate 0) = what the exact (texelFetch) path does."""
    img = np.asarray(img)
    H, W = img.shape[:2]
    yy, xx = np.indices((H, W)).astype(np.float64)
    qx, qy = xx + 0.5 - sx, yy + 0.5 - sy
    if edge == 3:
        ok = (qx >= 0) & (qx <= W) & (qy >= 0) & (qy <= H)
    ex = np.clip(np.floor(fk_edge(qx, W, edge)).astype(int), 0, W - 1)
    ey = np.clip(np.floor(fk_edge(qy, H, edge)).astype(int), 0, H - 1)
    out = img[ey, ex]
    if edge == 3:
        out = np.where(ok[..., None] if out.ndim == 3 else ok, out, 0)
    return out


def fk_mean_grid(W, H):
    """The 64x64 texel grid the stamp meter averages (= METER): list of (x, y)."""
    return [(int((gx + 0.5) / 64.0 * W), int((gy + 0.5) / 64.0 * H)) for gy in range(64) for gx in range(64)]


def fk_ticks(times, rate):
    """Which cooks run a generation: Rate 0 = every cook, else floor(t*Rate) changed since the previous cook."""
    out = []
    for i, t in enumerate(times):
        if rate <= 0 or i == 0:
            out.append(rate <= 0)
            continue
        out.append(math.floor(t * rate) != math.floor(times[i - 1] * rate))
    return out


def cadence_offset(steps, n, shift=0.0):
    """timeshuffle Mode cadence (TC-31) = the map's mode 6 branch: steps [(code, cooks)] (codes p h r v b w = 0..5),
    n = cooks since the ring restarted, shift = per-block phase. -> (k cooks back before the ring clamp, keep 1 / 0
    fill / 0.5 white, cycle index)."""
    T = max(float(sum(l for _c, l in steps)), 1.0)
    c = float(n) + shift
    cyc = math.floor(c / T)
    c -= cyc * T
    st, prevl = 0.0, 0.0
    for code, l in steps[:16]:
        if c < st + l:
            i = c - st
            if code == 1:
                return i, 1.0, cyc
            if code == 2:
                return prevl, 1.0, cyc
            if code == 3:
                return 2.0 * i, 1.0, cyc
            if code == 4:
                return 0.0, 0.0, cyc
            if code == 5:
                return 0.0, 0.5, cyc
            return 0.0, 1.0, cyc
        st += l
        prevl = float(l)
    return 0.0, 1.0, cyc


def cadence_frames(steps, n0, count, depth):
    """Whole-frame cadence (Chance 1, no blocks): for cooks n0 .. n0 + count - 1 -> [(cook shown or None, keep)] with
    the ring clamp min(depth - 1, n)."""
    out = []
    for n in range(n0, n0 + count):
        k, keep, _c = cadence_offset(steps, n)
        k = min(max(k, 0.0), min(depth - 1, n))
        out.append((n - int(k) if keep == 1.0 else None, keep))
    return out
