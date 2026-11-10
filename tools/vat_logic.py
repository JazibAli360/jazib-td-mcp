# vat_logic - pure maths + file formats for vertex animation textures (VAT), 27 Oct 2026 (FX7c card 26, lane T).
#
# Used by tools/blender_vat.py (inside Blender 5.2.2, writes the bake) and by the tests / live checks (outside TD,
# T-184: references never run inside TD). No Blender, no TD here; numpy only. ASCII only.
#
# The VAT layout (docs/USING_TD.md "VAT"; td_vat_load reads it):
#   * one COLUMN per point (Blender vertex, all baked objects concatenated), one ROW BAND per frame. A band is
#     R = ceil(points / W) rows when the point count is wider than the max width W (default 8192), so
#     point i of frame f lives at texel  x = i % W,  y = f * R + i // W   (y counted from the BOTTOM row, the
#     OpenGL / TD texelFetch convention; the EXR file stores its top scanline first, so file row = H - 1 - y).
#   * <name>_pos.exr: RGBA 32-bit float, RGB = ABSOLUTE world position in TD space (Y-up, metres; Blender
#     (x, y, z) -> TD (x, z, -y) times the scene unit scale), A = 1.
#   * <name>_nrm.exr (optional): RGB = world normal (unit, TD space), A = 0.
#   * <name>.obj: the rest mesh (first baked frame): v = rest positions (TD space), vt = (u, v, POINT INDEX):
#     the third uv component carries the VAT column index, so TD's point/vertex order never matters (31550 File In
#     SOP keeps vt w in uv[0].z: probed 27 Oct). f = polygons, 1-based v/vt.
#   * <name>.json: the sidecar (SCHEMA below): frames, fps, points, width, rows_per_frame, height, bounds, files.
#   Houdini (SideFX Labs VAT) uses the same idea (frames along V, one column per point, float EXR, json with
#   frame count + bounds) but stores OFFSETS from the rest pose and its own lookup UV channel: Houdini files are not
#   read here (U6: Blender only); this layout is documented so a converter could be added later.
import json
import math
import struct

SCHEMA = 'jazib-vat/1'
MAX_W = 8192
MAX_H = 16384
LOOP_MODES = ('loop', 'once', 'pingpong')


def to_td(p, unit=1.0):
    """Blender Z-up -> TD Y-up (same as blender_td_logic.point_to_td), metres."""
    return (p[0] * unit, p[2] * unit, -p[1] * unit)


def to_td_np(a, unit=1.0):
    """(N, 3) Blender array -> TD space (numpy)."""
    import numpy as np
    a = np.asarray(a, dtype=np.float64)
    return np.stack([a[:, 0] * unit, a[:, 2] * unit, -a[:, 1] * unit], axis=1)


def layout(points, frames, max_w=MAX_W):
    """Texture size for `points` points x `frames` frames -> {width, rows_per_frame, height}. ValueError past
    MAX_H rows (bake fewer frames, a bigger step, or a lower-poly mesh)."""
    points, frames = int(points), int(frames)
    if points < 1 or frames < 1:
        raise ValueError('need >= 1 point and >= 1 frame')
    w = min(points, int(max_w))
    r = int(math.ceil(points / float(w)))
    h = frames * r
    if h > MAX_H:
        raise ValueError('VAT too tall: {} frames x {} rows = {} > {} (bake fewer frames / a step / fewer points)'
                         .format(frames, r, h, MAX_H))
    return {'width': w, 'rows_per_frame': r, 'height': h}


def texel(i, f, w, r):
    """(x, y) of point i in frame f, y from the bottom (TD texelFetch)."""
    return (i % w, f * r + i // w)


def frame_pick(raw, frames, mode='loop', interp=True):
    """The shader's frame logic (td/vat.py VAT_COMMON) in Python: raw frame (float) -> (f0, f1, t)."""
    n = int(frames)
    if n <= 1:
        return 0, 0, 0.0
    raw = float(raw)
    if mode == 'loop':
        f = raw % n
        f0 = int(math.floor(f))
        f1 = (f0 + 1) % n
    elif mode == 'once':
        f = min(max(raw, 0.0), n - 1.0)
        f0 = int(math.floor(f))
        f1 = min(f0 + 1, n - 1)
    elif mode == 'pingpong':
        period = 2.0 * (n - 1)
        g = raw % period
        f = g if g <= n - 1 else period - g
        f0 = int(math.floor(f))
        f1 = min(f0 + 1, n - 1)
    else:
        raise ValueError('mode must be one of {}'.format(LOOP_MODES))
    t = (f - f0) if interp else 0.0
    return f0, f1, t


def pack(frames_xyz, w, r, alpha=1.0):
    """frames_xyz: (F, N, 3) -> (H, W, 4) float32 image with row 0 = BOTTOM (texel y). Unused texels are 0."""
    import numpy as np
    a = np.asarray(frames_xyz, dtype=np.float32)
    F, N = a.shape[0], a.shape[1]
    img = np.zeros((F * r, w, 4), dtype=np.float32)
    idx = np.arange(N)
    xs, ys = idx % w, idx // w
    for f in range(F):
        img[f * r + ys, xs, :3] = a[f]
        img[f * r + ys, xs, 3] = alpha
    return img


def unpack(img, f, n, w, r):
    """(H, W, 4) bottom-row-first image -> (n, 3) positions of frame f."""
    import numpy as np
    idx = np.arange(int(n))
    return np.asarray(img)[f * r + idx // w, idx % w, :3]


def sample(img, raw, frames, n, w, r, mode='loop', interp=True):
    """Reference of what the shader draws for raw frame `raw` (positions, (n, 3))."""
    f0, f1, t = frame_pick(raw, frames, mode, interp)
    a, b = unpack(img, f0, n, w, r), unpack(img, f1, n, w, r)
    return a + (b - a) * t


# ------------------------------------------------------------------ OpenEXR (scanline, uncompressed, FLOAT)
# Minimal writer/reader for the subset we make: 4 channels A B G R (sorted), FLOAT (pixel type 2), NO_COMPRESSION,
# one scanline per chunk, INCREASING_Y. Spec: openexr.com "OpenEXR File Layout".
def _attr(name, typ, data):
    return name.encode('ascii') + b'\0' + typ.encode('ascii') + b'\0' + struct.pack('<i', len(data)) + data


def write_exr(path, img_bottom_first):
    """img: (H, W, 4) float32 RGBA, row 0 = bottom (texel y = 0). Written top scanline first (EXR y = 0 = top)."""
    import numpy as np
    img = np.asarray(img_bottom_first, dtype='<f4')
    h, w = img.shape[0], img.shape[1]
    chans = b''.join(c.encode('ascii') + b'\0' + struct.pack('<iB3xii', 2, 0, 1, 1) for c in 'ABGR') + b'\0'
    box = struct.pack('<iiii', 0, 0, w - 1, h - 1)
    hdr = (b'\x76\x2f\x31\x01' + struct.pack('<i', 2)
           + _attr('channels', 'chlist', chans)
           + _attr('compression', 'compression', b'\0')
           + _attr('dataWindow', 'box2i', box)
           + _attr('displayWindow', 'box2i', box)
           + _attr('lineOrder', 'lineOrder', b'\0')
           + _attr('pixelAspectRatio', 'float', struct.pack('<f', 1.0))
           + _attr('screenWindowCenter', 'v2f', struct.pack('<ff', 0.0, 0.0))
           + _attr('screenWindowWidth', 'float', struct.pack('<f', 1.0))
           + b'\0')
    line = w * 4 * 4
    chunk = 8 + line
    base = len(hdr) + 8 * h
    offsets = struct.pack('<{}Q'.format(h), *[base + k * chunk for k in range(h)])
    top_first = img[::-1]
    planar = np.ascontiguousarray(top_first[:, :, [3, 2, 1, 0]].transpose(0, 2, 1))  # (H, ABGR, W)
    with open(path, 'wb') as f:
        f.write(hdr)
        f.write(offsets)
        for y in range(h):
            f.write(struct.pack('<ii', y, line))
            f.write(planar[y].tobytes())


def read_exr(path):
    """Reader for files written by write_exr (and other uncompressed FLOAT/HALF scanline EXRs).
    Returns (H, W, 4) float32 RGBA, row 0 = bottom."""
    import numpy as np
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'\x76\x2f\x31\x01':
        raise ValueError('not an OpenEXR file: {}'.format(path))
    p = 8
    attrs = {}
    while data[p] != 0:
        e = data.index(b'\0', p)
        name = data[p:e].decode('ascii')
        e2 = data.index(b'\0', e + 1)
        size = struct.unpack('<i', data[e2 + 1:e2 + 5])[0]
        attrs[name] = data[e2 + 5:e2 + 5 + size]
        p = e2 + 5 + size
    p += 1
    if attrs.get('compression', b'\0') != b'\0':
        raise ValueError('compressed EXR not supported by this reader')
    x0, y0, x1, y1 = struct.unpack('<iiii', attrs['dataWindow'])
    w, h = x1 - x0 + 1, y1 - y0 + 1
    chans, q, cl = [], 0, attrs['channels']
    while cl[q] != 0:
        e = cl.index(b'\0', q)
        nm = cl[q:e].decode('ascii')
        pt = struct.unpack('<i', cl[e + 1:e + 5])[0]
        chans.append((nm, pt))
        q = e + 17
    offs = struct.unpack('<{}Q'.format(h), data[p:p + 8 * h])
    out = np.zeros((h, w, 4), dtype=np.float32)
    slot = {'R': 0, 'G': 1, 'B': 2, 'A': 3}
    for o in offs:
        y = struct.unpack('<i', data[o:o + 4])[0] - y0
        q = o + 8
        for nm, pt in chans:
            dt, sz = ('<f4', 4) if pt == 2 else ('<f2', 2)
            row = np.frombuffer(data, dtype=dt, count=w, offset=q).astype(np.float32)
            q += w * sz
            if nm in slot:
                out[h - 1 - y, :, slot[nm]] = row
    return out


# ------------------------------------------------------------------ OBJ rest mesh
def obj_text(rest_xyz, polys, corner_uvs=None, header=''):
    """rest_xyz: (N, 3) TD space; polys: list of point-index lists; corner_uvs: list (per poly) of (u, v) per corner,
    or None. vt = (u, v, point index) (TD File In SOP keeps the 3rd component in uv[0].z)."""
    out = ['# ' + ln for ln in header.splitlines()] if header else []
    for p in rest_xyz:
        out.append('v {:.6f} {:.6f} {:.6f}'.format(float(p[0]), float(p[1]), float(p[2])))
    vt_index, vts, faces = {}, [], []
    for k, poly in enumerate(polys):
        uvs = corner_uvs[k] if corner_uvs is not None else [(0.0, 0.0)] * len(poly)
        refs = []
        for pi, uv in zip(poly, uvs):
            key = (round(float(uv[0]), 6), round(float(uv[1]), 6), int(pi))
            t = vt_index.get(key)
            if t is None:
                t = vt_index[key] = len(vts) + 1
                vts.append(key)
            refs.append('{}/{}'.format(int(pi) + 1, t))
        faces.append('f ' + ' '.join(refs))
    out += ['vt {:.6f} {:.6f} {}'.format(u, v, i) for u, v, i in vts]
    out += faces
    return '\n'.join(out) + '\n'


def read_obj_ids(text):
    """For tests: [(point index from v/vt, uv w)] per corner, plus the v count."""
    vs, vts, corners = 0, [], []
    for ln in text.splitlines():
        if ln.startswith('v '):
            vs += 1
        elif ln.startswith('vt '):
            vts.append([float(x) for x in ln.split()[1:]])
        elif ln.startswith('f '):
            for ref in ln.split()[1:]:
                a = ref.split('/')
                corners.append((int(a[0]) - 1, vts[int(a[1]) - 1][2]))
    return vs, corners


# ------------------------------------------------------------------ sidecar
def bounds(frames_xyz):
    import numpy as np
    a = np.asarray(frames_xyz, dtype=np.float64).reshape(-1, 3)
    return {'min': [round(float(x), 6) for x in a.min(axis=0)], 'max': [round(float(x), 6) for x in a.max(axis=0)]}


def sidecar(name, frames, points, lay, fps, start, end, step, files, bnds, rest_bnds, objects, source=None,
            warnings=None):
    return {'schema': SCHEMA, 'name': name, 'frames': int(frames), 'points': int(points),
            'width': lay['width'], 'rows_per_frame': lay['rows_per_frame'], 'height': lay['height'],
            'fps': float(fps) / max(int(step), 1), 'scene_fps': float(fps), 'start': int(start), 'end': int(end),
            'step': int(step), 'positions': 'absolute', 'coords': 'td-yup-metres', 'texel_origin': 'bottom-left',
            'files': files, 'bounds': bnds, 'rest_bounds': rest_bnds, 'objects': objects,
            'source': source or {}, 'warnings': list(warnings or [])}


def check_sidecar(side):
    """Validation shared by the tests and src/vat.js expectations: returns a list of problems (empty = ok)."""
    bad = []
    if side.get('schema') != SCHEMA:
        bad.append('schema is {!r}, want {!r}'.format(side.get('schema'), SCHEMA))
    for k in ('frames', 'points', 'width', 'rows_per_frame', 'height'):
        if not isinstance(side.get(k), int) or side.get(k) < 1:
            bad.append('{} must be a positive int'.format(k))
    if not bad:
        if side['width'] * side['rows_per_frame'] < side['points']:
            bad.append('width x rows_per_frame < points')
        if side['height'] != side['frames'] * side['rows_per_frame']:
            bad.append('height != frames x rows_per_frame')
    files = side.get('files') or {}
    for k in ('mesh', 'pos'):
        if not files.get(k):
            bad.append('files.{} missing'.format(k))
    return bad


def dumps(side):
    return json.dumps(side, indent=1)
