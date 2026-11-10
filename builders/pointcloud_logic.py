"""pointcloud_logic: pure logic for /project1/lab/BL_cloud_morph (point-cloud viewer + A/B morph).

Clean-room, spec docs/research/BL_gaussian_splats_pointclouds.md section 7.2 (+ 4, 4.1, 5.1). No `td` import: tested
offline by test/test_pointcloud.py and copied into the COMP as the Text DAT `pointcloud_logic`. numpy is imported lazily
so the module loads (and the COMP's Status says why) if TD's numpy breaks (T-48). ASCII only. No limits (user rule):
every range is open; Count 0 = automatic, nothing is capped.

Conventions (TD, right-handed, Y up, camera looks down -Z):
- cloud dict: P (n,3) float32 positions, C (n,4) float32 straight rgba 0..1, 'n', 'src' (text), optional UV (n,2)
  for live depth-TOP sides (the GPU unprojects them, P is a proxy plane used only for matching).
- image uv: u right, v UP from the bottom row (TD texture space, T-58); array rows from files are top-first.
- pairs: A[pa[i]] <-> B[pb[i]] for i in 0..N-1 (equal counts after resampling).
The GLSL MAT (builders/glsl/pointcloud_vertex.glsl) mirrors point_morph(), ease(), unproject_depth(), radius_px():
change both together.
"""
import gzip
import math
import struct

SH_C0 = 0.28209479177387814

SOURCES = [('file', 'File (ply xyz obj csv pts splat spz)'), ('gen', 'Generator'),
           ('depthfile', 'Depth image file (npy pfm pgm, png/exr via cv2)'), ('depthtex', 'Depth TOP (live, GPU)')]
GENERATORS = [('sphere', 'Sphere'), ('grid', 'Grid cube'), ('torus', 'Torus'), ('cube', 'Cube surface'),
              ('helix', 'Helix'), ('blob', 'Gaussian blob'), ('plane', 'Plane'), ('ring', 'Ring'),
              ('spiral', 'Galaxy spiral')]
MATCHES = [('morton', 'Morton (Z-order)'), ('kd', 'k-d split pairs'), ('sliced', 'Sliced OT + k-d (Slices rounds)'),
           ('index', 'Index (file order)'), ('random', 'Random')]
MORPHMODES = [('manual', 'Manual'), ('bpm', 'BPM'), ('lfo', 'LFO'), ('audio', 'Audio level')]
TEMPOS = [('project', 'Project tempo'), ('manual', 'Bpm par')]
EASES = [('linear', 'Linear'), ('in', 'In'), ('out', 'Out'), ('inout', 'In-out (smoothstep)'), ('sine', 'Sine')]
STAGGERS = [('radial', 'Radial (centre first)'), ('axis', 'Height (bottom first)'), ('noise', 'Noise'),
            ('index', 'Index')]
SHAPES = [('disc', 'Disc'), ('soft', 'Soft (gaussian)'), ('square', 'Square'), ('ring', 'Ring'),
          ('streak', 'Streak (morph motion)')]
BLENDS = [('add', 'Additive'), ('over', 'Over (unsorted)'), ('opaque', 'Opaque (depth test)')]
UPAXES = [('y', 'Y up (TD)'), ('z', 'Z up (scans, CAD)'), ('-y', 'Y down (INRIA splats)'), ('-z', 'Z down')]
DEPTHKINDS = [('inverse', 'Inverse depth (Depth Anything)'), ('depth', 'Depth (near dark)')]
CAMMODES = [('orbit', 'Internal orbit'), ('external', 'External camera')]
DATAPATHS = [('chop', 'CHOP instancing'), ('pop', 'POP instancing (CHOP to POP)')]

# instance data: one sample per point; slots = Geometry COMP custom instance attributes 0..4 (vec4 each)
CHANNELS = ['ax', 'ay', 'az', 'dl', 'bx', 'by', 'bz', 'sd', 'ar', 'ag', 'ab', 'aa', 'br', 'bg', 'bb', 'ba',
            'ua', 'va', 'ub', 'vb']
SLOTS = [('Pa', ['ax', 'ay', 'az', 'dl']), ('Pb', ['bx', 'by', 'bz', 'sd']), ('Ca', ['ar', 'ag', 'ab', 'aa']),
         ('Cb', ['br', 'bg', 'bb', 'ba']), ('Uv', ['ua', 'va', 'ub', 'vb'])]

PLY_TYPES = {'char': 'i1', 'int8': 'i1', 'uchar': 'u1', 'uint8': 'u1', 'short': 'i2', 'int16': 'i2',
             'ushort': 'u2', 'uint16': 'u2', 'int': 'i4', 'int32': 'i4', 'uint': 'u4', 'uint32': 'u4',
             'float': 'f4', 'float32': 'f4', 'double': 'f8', 'float64': 'f8'}


def _np():
    import numpy
    return numpy


def names(menu):
    return [m[0] for m in menu]


def labels(menu):
    return [m[1] for m in menu]


def menu_index(menu, name):
    for i, m in enumerate(menu):
        if m[0] == name:
            return i
    return 0


# ---------------------------------------------------------------- file formats

def detect_kind(path):
    p = str(path).lower()
    for ext in ('ply', 'splat', 'spz', 'obj', 'xyz', 'pts', 'csv', 'txt', 'npy', 'pfm', 'pgm', 'png', 'jpg', 'jpeg',
                'exr', 'tif', 'tiff'):
        if p.endswith('.' + ext):
            return ext
    raise ValueError('unknown point-cloud file extension: {}'.format(path))


def parse_ply_header(data):
    """-> (fmt, header_len, elements=[(name, count, [(prop, type) | (prop, ('list', ctype, itype))])])."""
    end = data.find(b'end_header')
    if not data.startswith(b'ply') or end < 0:
        raise ValueError('not a PLY file')
    hl = data.find(b'\n', end) + 1
    fmt, els = None, []
    for line in data[:hl].decode('ascii', 'replace').splitlines():
        t = line.split()
        if not t or t[0] in ('ply', 'comment', 'obj_info', 'end_header'):
            continue
        if t[0] == 'format':
            fmt = t[1]
        elif t[0] == 'element':
            els.append((t[1], int(t[2]), []))
        elif t[0] == 'property' and els:
            if t[1] == 'list':
                els[-1][2].append((t[4], ('list', t[2], t[3])))
            else:
                els[-1][2].append((t[2], t[1]))
    if fmt not in ('ascii', 'binary_little_endian', 'binary_big_endian'):
        raise ValueError('PLY format {!r} not supported'.format(fmt))
    return fmt, hl, els


def _colour_from_fields(np, get, have, n):
    """rgba 0..1 from PLY-ish fields: red/green/blue[/alpha] (u8 /255, float as is), r/g/b, or 3DGS f_dc_* + opacity."""
    C = np.ones((n, 4), np.float32)
    div = {'u1': 255.0, 'i1': 127.0, 'u2': 65535.0, 'i2': 32767.0}
    for keys in (('red', 'green', 'blue', 'alpha'), ('r', 'g', 'b', 'a'), ('diffuse_red', 'diffuse_green',
                                                                          'diffuse_blue', 'diffuse_alpha')):
        if all(k in have for k in keys[:3]):
            for i, k in enumerate(keys):
                if k in have:
                    v = get(k).astype(np.float32)
                    t = PLY_TYPES.get(have[k], have[k])
                    if t in div:
                        v = v / div[t]
                    elif v.size and float(v.max()) > 1.0:      # float colours stored 0..255
                        v = v / 255.0
                    C[:, i] = v
            return C, 'rgb'
    if all('f_dc_%d' % i in have for i in range(3)):
        for i in range(3):
            C[:, i] = np.maximum(0.5 + SH_C0 * get('f_dc_%d' % i).astype(np.float32), 0.0)
        if 'opacity' in have:
            C[:, 3] = 1.0 / (1.0 + np.exp(-get('opacity').astype(np.float32)))
        return C, 'sh0'
    return None, 'none'


def load_ply(path):
    np = _np()
    with open(path, 'rb') as f:
        data = f.read()
    fmt, hl, els = parse_ply_header(data)
    if not els or els[0][0] != 'vertex':
        idx = [e[0] for e in els].index('vertex') if 'vertex' in [e[0] for e in els] else -1
        if idx < 0:
            raise ValueError('PLY has no vertex element')
        if fmt != 'ascii' and any(isinstance(t, tuple) for e in els[:idx] for _, t in e[2]):
            raise ValueError('binary PLY with list elements before the vertices is not supported')
    vi = [e[0] for e in els].index('vertex')
    _, n, props = els[vi]
    if any(isinstance(t, tuple) for _, t in props):
        raise ValueError('PLY vertex element with list properties is not supported')
    if fmt == 'ascii':
        lines = data[hl:].split(b'\n')
        skip = sum(e[1] for e in els[:vi])
        rows = [ln.decode('ascii', 'replace') for ln in lines[skip:skip + n] if ln.strip()]
        A = np.loadtxt(rows, dtype=np.float64, ndmin=2) if rows else np.zeros((0, len(props)))
        if A.shape[0] < n:
            raise ValueError('PLY ascii: {} vertex rows, header says {}'.format(A.shape[0], n))
        col = dict((nm, i) for i, (nm, _) in enumerate(props))
        get = lambda k: A[:, col[k]]  # noqa: E731
        have = dict((nm, t) for nm, t in props)
    else:
        end = '<' if fmt == 'binary_little_endian' else '>'
        off = hl
        for e in els[:vi]:
            off += e[1] * int(sum(np.dtype(PLY_TYPES[t]).itemsize for _, t in e[2]))
        dt = np.dtype([(nm, end + PLY_TYPES[t]) for nm, t in props])
        if len(data) - off < n * dt.itemsize:
            raise ValueError('PLY truncated: {} bytes for {} vertices of {} B'.format(len(data) - off, n, dt.itemsize))
        A = np.frombuffer(data, dtype=dt, count=n, offset=off)
        get = lambda k: A[k]  # noqa: E731
        have = dict((nm, PLY_TYPES[t]) for nm, t in props)
    for k in ('x', 'y', 'z'):
        if k not in have:
            raise ValueError('PLY vertex has no {!r} property'.format(k))
    P = np.stack([get('x'), get('y'), get('z')], 1).astype(np.float32)
    C, how = _colour_from_fields(np, get, have, n)
    return {'P': P, 'C': C, 'n': n, 'src': 'ply {} {} colour {}'.format(fmt.split('_')[0], n, how)}


def load_text_points(path):
    """.xyz/.pts/.txt/.csv: whitespace or comma columns. A non-numeric first line is a header (names used: x y z,
    r g b [a] / red green blue); .pts may start with a count line. Without a header: x y z [r g b] when >= 6
    columns (0..255 values scaled to 0..1)."""
    np = _np()
    with open(path, 'r') as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith(('#', '//'))]
    if not lines:
        raise ValueError('empty point file')
    sep = ',' if ',' in lines[0] or (len(lines) > 1 and ',' in lines[1]) else None
    split = lambda s: [t for t in (s.split(sep) if sep else s.split()) if t != '']  # noqa: E731

    def numeric(s):
        try:
            [float(t) for t in split(s)]
            return True
        except ValueError:
            return False
    header = None
    if not numeric(lines[0]):
        header = [t.strip().lower() for t in split(lines[0])]
        lines = lines[1:]
    elif len(split(lines[0])) == 1 and len(lines) > 1 and len(split(lines[1])) >= 3:
        lines = lines[1:]                                   # .pts count line
    ncol = min(len(split(ln)) for ln in lines[:1000]) if lines else 0
    if ncol < 3:
        raise ValueError('point file needs >= 3 numeric columns')
    A = np.array([[float(t) for t in split(ln)[:ncol]] for ln in lines], dtype=np.float64).reshape(-1, ncol)
    n = A.shape[0]
    cols = {}
    if header:
        for i, h in enumerate(header[:ncol]):
            cols[h] = i
        xi = [cols.get(k, cols.get(k.upper(), None)) for k in ('x', 'y', 'z')]
        if None in xi:
            xi = [0, 1, 2]
    else:
        xi = [0, 1, 2]
    P = A[:, xi].astype(np.float32)
    C = None
    rgb = None
    if header:
        for keys in (('r', 'g', 'b'), ('red', 'green', 'blue')):
            if all(k in cols for k in keys):
                rgb = [cols[k] for k in keys] + ([cols[a] for a in ('a', 'alpha') if a in cols][:1])
                break
    elif ncol >= 6:
        rgb = [3, 4, 5]
    if rgb:
        C = np.ones((n, 4), np.float32)
        v = A[:, rgb].astype(np.float32)
        if v.size and float(v.max()) > 1.0:
            v = v / 255.0
        C[:, :len(rgb)] = v
    return {'P': P, 'C': C, 'n': n, 'src': 'text {} cols {} colour {}'.format(n, ncol, 'rgb' if C is not None
                                                                            else 'none')}


def load_obj(path):
    """Wavefront .obj vertices: 'v x y z [r g b]' (faces ignored)."""
    np = _np()
    pts, cols = [], []
    with open(path, 'r') as f:
        for ln in f:
            if ln.startswith('v '):
                t = ln.split()
                pts.append([float(t[1]), float(t[2]), float(t[3])])
                if len(t) >= 7:
                    cols.append([float(t[4]), float(t[5]), float(t[6])])
    if not pts:
        raise ValueError('obj has no vertices')
    P = np.array(pts, np.float32)
    C = None
    if cols and len(cols) == len(pts):
        C = np.ones((len(pts), 4), np.float32)
        v = np.array(cols, np.float32)
        C[:, :3] = v / 255.0 if float(v.max()) > 1.0 else v
    return {'P': P, 'C': C, 'n': len(pts), 'src': 'obj {}'.format(len(pts))}


def load_splat_centres(path):
    """antimatter15 .splat: 32 B/splat (f32 pos x3, f32 scale x3, u8 rgba, u8 quat); centres + colour only."""
    np = _np()
    raw = np.fromfile(path, dtype=np.uint8)
    if raw.size % 32:
        raise ValueError('.splat size {} is not a multiple of 32'.format(raw.size))
    n = raw.size // 32
    rec = raw.reshape(n, 32)
    P = rec[:, 0:12].copy().view('<f4').reshape(n, 3).astype(np.float32)
    C = rec[:, 24:28].astype(np.float32) / 255.0
    return {'P': P, 'C': C, 'n': n, 'src': 'splat {}'.format(n)}


def spz_header(data):
    if data[:2] == b'\x1f\x8b':
        raise ValueError('gzip data: decompress first')
    if len(data) < 16:
        raise ValueError('spz too short')
    magic, ver, n, shd, frac, flags, _ = struct.unpack('<IIIBBBB', data[:16])
    if magic != 0x5053474e:
        raise ValueError('not an SPZ (magic {:#x})'.format(magic))
    return {'version': ver, 'n': n, 'shdegree': shd, 'frac': frac, 'flags': flags}


def load_spz_centres(path):
    """Niantic .spz v1-v3 (gzip): centres (24-bit fixed point), alpha, colour (DC). SPZ 4 (ZSTD) is not supported."""
    np = _np()
    with open(path, 'rb') as f:
        head = f.read(4)
    if head == b'NGSP':
        raise ValueError('SPZ 4 (ZSTD streams) is not supported on TD 2025.31550 Python (FUTURE)')
    with gzip.open(path, 'rb') as f:
        data = f.read()
    h = spz_header(data)
    n, off = h['n'], 16
    if h['version'] not in (1, 2, 3):
        raise ValueError('SPZ version {} not supported'.format(h['version']))
    if h['version'] == 1:
        raise ValueError('SPZ v1 (float16 positions) not supported')
    need = off + n * 9 + n + n * 3
    if len(data) < need:
        raise ValueError('SPZ truncated')
    pb = np.frombuffer(data, np.uint8, n * 9, off).reshape(n, 3, 3).astype(np.int32)
    v = pb[:, :, 0] | (pb[:, :, 1] << 8) | (pb[:, :, 2] << 16)
    v = np.where(v & 0x800000, v - (1 << 24), v)
    P = (v.astype(np.float64) / float(1 << h['frac'])).astype(np.float32)
    off += n * 9
    a = np.frombuffer(data, np.uint8, n, off).astype(np.float32) / 255.0
    off += n
    c = np.frombuffer(data, np.uint8, n * 3, off).reshape(n, 3).astype(np.float32)
    fdc = (c / 255.0 - 0.5) / 0.15
    C = np.empty((n, 4), np.float32)
    C[:, :3] = np.maximum(0.5 + SH_C0 * fdc, 0.0)
    C[:, 3] = a
    return {'P': P, 'C': C, 'n': n, 'src': 'spz v{} {} sh{}'.format(h['version'], n, h['shdegree'])}


def load_cloud(path):
    k = detect_kind(path)
    if k == 'ply':
        return load_ply(path)
    if k == 'splat':
        return load_splat_centres(path)
    if k == 'spz':
        return load_spz_centres(path)
    if k == 'obj':
        return load_obj(path)
    if k in ('xyz', 'pts', 'csv', 'txt'):
        return load_text_points(path)
    raise ValueError('{} is an image: use Source = depth image file'.format(path))


# ---------------------------------------------------------------- depth images

def read_pfm(path):
    """PFM (Pf grey / PF colour), float32; returns rows TOP-first (PFM stores bottom-first)."""
    np = _np()
    with open(path, 'rb') as f:
        kind = f.readline().strip()
        w, h = [int(x) for x in f.readline().split()]
        scale = float(f.readline().strip())
        ch = 3 if kind == b'PF' else 1
        a = np.fromfile(f, dtype=('<f4' if scale < 0 else '>f4'), count=w * h * ch).reshape(h, w, ch)
    return np.ascontiguousarray(a[::-1, :, 0]).astype(np.float32)


def read_pgm(path):
    """Binary PGM (P5) 8 or 16 bit -> float 0..1, rows top-first."""
    np = _np()
    with open(path, 'rb') as f:
        data = f.read()
    toks, i = [], 0
    while len(toks) < 4:
        while data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b'#':
            i = data.index(b'\n', i) + 1
            continue
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        toks.append(data[i:j])
        i = j
    i += 1
    if toks[0] != b'P5':
        raise ValueError('only binary PGM (P5)')
    w, h, mx = int(toks[1]), int(toks[2]), int(toks[3])
    dt = '>u2' if mx > 255 else 'u1'
    a = np.frombuffer(data, dtype=dt, count=w * h, offset=i).reshape(h, w)
    return a.astype(np.float32) / float(mx)


def read_depth_file(path):
    """2D float array, rows top-first. npy/pfm/pgm offline; png/jpg/exr/tif through cv2 (TD's Python has it)."""
    np = _np()
    k = detect_kind(path)
    if k == 'npy':
        a = np.load(path).astype(np.float32)
    elif k == 'pfm':
        a = read_pfm(path)
    elif k == 'pgm':
        a = read_pgm(path)
    else:
        import cv2
        a = cv2.imread(path, cv2.IMREAD_UNCHANGED | cv2.IMREAD_ANYDEPTH)
        if a is None:
            raise ValueError('cv2 could not read {}'.format(path))
        if a.dtype == np.uint8:
            a = a.astype(np.float32) / 255.0
        elif a.dtype == np.uint16:
            a = a.astype(np.float32) / 65535.0
        a = a.astype(np.float32)
    if a.ndim == 3:
        a = a[:, :, 0] if a.shape[2] < 3 else a[:, :, :3].mean(2)
    return a


def read_colour_file(path):
    """rgb float 0..1 rows top-first (cv2, BGR -> RGB), or None if cv2 is missing."""
    np = _np()
    try:
        import cv2
    except ImportError:
        return None
    a = cv2.imread(path, cv2.IMREAD_COLOR)
    if a is None:
        return None
    return a[:, :, ::-1].astype(np.float32) / 255.0


def depth_to_z(dn, kind, znear, zfar):
    """Normalised depth value 0..1 -> camera distance. inverse: 1 = near (Depth Anything); depth: 0 = near."""
    np = _np()
    dn = np.clip(dn, 0.0, 1.0)
    if kind == 'depth':
        return znear + dn * (zfar - znear)
    return zfar / (1.0 + dn * (zfar / max(znear, 1e-6) - 1.0))


def unproject_uv(u, v, dn, fov_deg, aspect, znear, zfar, kind='inverse'):
    """uv (v up) + normalised depth -> camera-space points (x right, y up, -z forward). aspect = w/h."""
    np = _np()
    z = depth_to_z(np.asarray(dn, np.float64), kind, znear, zfar)
    t = math.tan(math.radians(fov_deg) * 0.5)
    x = (np.asarray(u) - 0.5) * 2.0 * t * aspect * z
    y = (np.asarray(v) - 0.5) * 2.0 * t * z
    return np.stack([x, y, -z], -1).astype(np.float32)


def unproject_depth(depth, fov_deg=60.0, znear=1.0, zfar=10.0, lo=None, hi=None, kind='inverse', step=1,
                    colour=None):
    """Depth map (rows top-first) -> cloud. lo/hi default = 2nd/98th percentile (the helper sends its own)."""
    np = _np()
    d = np.asarray(depth, np.float32)
    h, w = d.shape
    if lo is None or hi is None:
        plo, phi = np.percentile(d, [2.0, 98.0])
        lo = plo if lo is None else lo
        hi = phi if hi is None else hi
    rows = np.arange(0, h, max(1, int(step)))
    colsx = np.arange(0, w, max(1, int(step)))
    rr, cc = np.meshgrid(rows, colsx, indexing='ij')
    u = (cc + 0.5) / w
    v = 1.0 - (rr + 0.5) / h
    dn = (d[rr, cc] - lo) / max(hi - lo, 1e-9)
    P = unproject_uv(u.ravel(), v.ravel(), dn.ravel(), fov_deg, w / float(h), znear, zfar, kind)
    n = P.shape[0]
    C = np.ones((n, 4), np.float32)
    if colour is not None and colour.shape[:2] == (h, w):
        C[:, :3] = colour[rr, cc].reshape(n, 3)
    else:
        g = np.clip(dn.ravel(), 0, 1).astype(np.float32)
        C[:, 0] = C[:, 1] = C[:, 2] = g
    UV = np.stack([u.ravel(), v.ravel()], 1).astype(np.float32)
    return {'P': P, 'C': C, 'n': n, 'UV': UV, 'src': 'depth {}x{} step {} -> {}'.format(w, h, step, n),
            'lo': float(lo), 'hi': float(hi)}


def grid_uv(n, aspect=1.0):
    """Exactly n uv cell centres on a near-square grid of the image (row-major from the bottom row)."""
    np = _np()
    n = max(1, int(n))
    gw = max(1, int(math.ceil(math.sqrt(n * max(aspect, 1e-6)))))
    gh = max(1, int(math.ceil(n / float(gw))))
    i = np.arange(n)
    u = (i % gw + 0.5) / gw
    v = (i // gw + 0.5) / gh
    return np.stack([u, v], 1).astype(np.float32), (gw, gh)


def depthtex_proxy(n, aspect, fov_deg, znear, zfar, kind='inverse'):
    """Live depth-TOP side: uv grid + proxy positions (mid depth plane) used only for matching/bounds."""
    np = _np()
    UV, g = grid_uv(n, aspect)
    P = unproject_uv(UV[:, 0], UV[:, 1], np.full(n, 0.5), fov_deg, aspect, znear, zfar, kind)
    return {'P': P, 'C': np.ones((n, 4), np.float32), 'n': n, 'UV': UV,
            'src': 'depth TOP grid {}x{} ({} pts)'.format(g[0], g[1], n)}


# ---------------------------------------------------------------- generators

def generate(kind, n, seed=0):
    """Unit-size procedural clouds (radius ~1) with a position colour ramp."""
    np = _np()
    n = max(1, int(n))
    rng = np.random.default_rng(seed)
    i = np.arange(n, dtype=np.float64)
    if kind == 'sphere':
        ga = math.pi * (3.0 - math.sqrt(5.0))
        y = 1.0 - 2.0 * (i + 0.5) / n
        r = np.sqrt(np.maximum(1.0 - y * y, 0.0))
        P = np.stack([r * np.cos(ga * i), y, r * np.sin(ga * i)], 1)
    elif kind == 'grid':
        k = int(math.ceil(n ** (1.0 / 3.0)))
        g = (np.stack(np.unravel_index(np.arange(n), (k, k, k)), 1) + 0.5) / k * 2.0 - 1.0
        P = g[:, ::-1] * 0.8
    elif kind == 'torus':
        k = max(1, int(round(math.sqrt(n / 3.0))))
        a = 2 * math.pi * (i % (3 * k)) / (3 * k)
        b = 2 * math.pi * (i // (3 * k)) / max(1, math.ceil(n / (3.0 * k)))
        R, r = 0.75, 0.25
        P = np.stack([(R + r * np.cos(b)) * np.cos(a), r * np.sin(b), (R + r * np.cos(b)) * np.sin(a)], 1)
    elif kind == 'cube':
        u = rng.uniform(-1, 1, (n, 3))
        ax = rng.integers(0, 3, n)
        u[np.arange(n), ax] = np.sign(rng.uniform(-1, 1, n))
        P = u * 0.7
    elif kind == 'helix':
        t = i / n
        a = t * 2 * math.pi * 6
        P = np.stack([0.5 * np.cos(a), t * 2.0 - 1.0, 0.5 * np.sin(a)], 1) + rng.normal(0, 0.03, (n, 3))
    elif kind == 'blob':
        P = rng.normal(0, 0.4, (n, 3))
    elif kind == 'plane':
        k = max(1, int(math.ceil(math.sqrt(n))))
        P = np.stack([(i % k + 0.5) / k * 2 - 1, (i // k + 0.5) / k * 2 - 1, np.zeros(n)], 1)
    elif kind == 'ring':
        a = rng.uniform(0, 2 * math.pi, n)
        r = 0.8 + rng.normal(0, 0.05, n)
        P = np.stack([r * np.cos(a), rng.normal(0, 0.03, n), r * np.sin(a)], 1)
    elif kind == 'spiral':
        arm = rng.integers(0, 3, n)
        r = rng.uniform(0.02, 1.0, n) ** 0.7
        a = r * 5.0 + arm * (2 * math.pi / 3) + rng.normal(0, 0.18, n)
        P = np.stack([r * np.cos(a), rng.normal(0, 0.04, n) * (1.2 - r), r * np.sin(a)], 1)
    else:
        raise ValueError('unknown generator {!r}'.format(kind))
    P = P.astype(np.float32)
    C = np.ones((n, 4), np.float32)
    C[:, :3] = np.clip(P * 0.5 + 0.5, 0, 1)
    return {'P': P, 'C': C, 'n': n, 'src': 'gen {} {}'.format(kind, n)}


# ---------------------------------------------------------------- prepare

def up_axis_fix(P, up='y'):
    """Rotate so the file's up axis becomes TD's +Y. z: (x,y,z) -> (x,z,-y); -y: rotate X 180; -z: (x,-z,y)."""
    np = _np()
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    if up == 'z':
        return np.stack([x, z, -y], 1).astype(np.float32)
    if up == '-y':
        return np.stack([x, -y, -z], 1).astype(np.float32)
    if up == '-z':
        return np.stack([x, -z, y], 1).astype(np.float32)
    return P


def outlier_keep(P, pct=100.0):
    """Keep points whose distance from the median centre is within the pct-th percentile (100 = keep all)."""
    np = _np()
    if pct >= 100.0 or P.shape[0] < 4:
        return np.ones(P.shape[0], bool)
    c = np.median(P, 0)
    d = np.linalg.norm(P - c, axis=1)
    return d <= np.percentile(d, max(pct, 0.0))


def fit_unit(P):
    """Centre on the bbox centre and scale to radius 1 (max distance). -> (P', centre, radius)."""
    np = _np()
    if P.shape[0] == 0:
        return P, np.zeros(3, np.float32), 1.0
    c = (P.min(0) + P.max(0)) * 0.5
    r = float(np.linalg.norm(P - c, axis=1).max())
    r = r if r > 1e-12 else 1.0
    return ((P - c) / r).astype(np.float32), c.astype(np.float32), r


def resample_indices(n_in, n_out, seed=0, mode='even'):
    """n_out indices into n_in: fewer = evenly spaced (or random), more = every point then repeats (even spread)."""
    np = _np()
    n_in, n_out = int(n_in), int(n_out)
    if n_in <= 0:
        raise ValueError('empty cloud')
    if n_out == n_in:
        return np.arange(n_in)
    if mode == 'random':
        rng = np.random.default_rng(seed)
        if n_out < n_in:
            return np.sort(rng.choice(n_in, n_out, replace=False))
        return np.concatenate([np.arange(n_in), rng.integers(0, n_in, n_out - n_in)])
    if n_out < n_in:
        return np.floor(np.arange(n_out) * (n_in / float(n_out))).astype(np.int64)
    reps = np.floor(np.arange(n_out - n_in) * (n_in / float(max(n_out - n_in, 1)))).astype(np.int64) % n_in
    return np.concatenate([np.arange(n_in), reps])


def morton_codes(P, bits=10, lo=None, hi=None):
    """3D Morton (Z-order) codes of points normalised to [lo, hi] (default: own bbox). bits per axis <= 21."""
    np = _np()
    P = np.asarray(P, np.float64)
    lo = P.min(0) if lo is None else np.asarray(lo, np.float64)
    hi = P.max(0) if hi is None else np.asarray(hi, np.float64)
    span = np.where(hi - lo > 1e-12, hi - lo, 1.0)
    m = (1 << bits) - 1
    q = np.clip(((P - lo) / span * m).astype(np.int64), 0, m).astype(np.uint64)
    code = np.zeros(P.shape[0], np.uint64)
    for b in range(bits):
        for ax in range(3):
            code |= ((q[:, ax] >> np.uint64(b)) & np.uint64(1)) << np.uint64(3 * b + ax)
    return code


def morton_order(P, bits=10, lo=None, hi=None):
    np = _np()
    return np.argsort(morton_codes(P, bits, lo, hi), kind='stable')


def _random_dirs(rng, k):
    np = _np()
    d = rng.normal(size=(k, 3))
    return d / np.linalg.norm(d, axis=1, keepdims=True)


def sliced_distance(X, Y, dirs):
    """Mean squared 1D Wasserstein distance over the given unit directions (equal counts)."""
    np = _np()
    tot = 0.0
    for th in dirs:
        tot += float(np.mean((np.sort(X @ th) - np.sort(Y @ th)) ** 2))
    return tot / max(len(dirs), 1)


def sliced_flow(A, B, rounds=8, seed=0, history=False):
    """Move a copy of A toward B's distribution: per round a random direction, sort both along it, shift each A point
    along it to its rank partner. Returns Z (and the sliced distance after each round when history=True)."""
    np = _np()
    rng = np.random.default_rng(seed)
    Z = np.asarray(A, np.float64).copy()
    Bd = np.asarray(B, np.float64)
    probe = _random_dirs(np.random.default_rng(seed + 9973), 16)
    hist = [sliced_distance(Z, Bd, probe)] if history else None
    for _ in range(max(0, int(rounds))):
        th = _random_dirs(rng, 1)[0]
        za, zb = Z @ th, Bd @ th
        ia, ib = np.argsort(za, kind='stable'), np.argsort(zb, kind='stable')
        Z[ia] += (zb[ib] - za[ia])[:, None] * th[None, :]
        if history:
            hist.append(sliced_distance(Z, Bd, probe))
    return (Z, hist) if history else Z


def kd_match(X, Y, dirs=None):
    """Balanced k-d pairing of two equal-count sets: every level splits each group of both sets at its median along
    the same direction (equal halves on both sides), until groups hold one point. dirs: (levels, 3) unit vectors or
    None = cycle the axes by the union's extent. Exact for a translated copy. -> (px, py) index arrays."""
    np = _np()
    X = np.asarray(X, np.float64)
    Y = np.asarray(Y, np.float64)
    n = X.shape[0]
    ax, ay = np.arange(n), np.arange(n)
    ga = np.zeros(n, np.int64)
    gb = np.zeros(n, np.int64)
    if n <= 1:
        return ax, ay
    levels = int(math.ceil(math.log(n, 2))) + 1
    if dirs is None:
        ext = np.maximum(X.max(0), Y.max(0)) - np.minimum(X.min(0), Y.min(0))
        axes = list(np.argsort(-ext, kind='stable'))
        dirs = np.eye(3)[[axes[i % 3] for i in range(levels)]]
    pos = np.arange(n)
    for lv in range(levels):
        d = dirs[lv % len(dirs)]
        # groups are contiguous runs in both orders and have the same sizes on both sides
        starts = np.concatenate([[0], np.flatnonzero(np.diff(ga)) + 1])
        sizes = np.diff(np.append(starts, n))
        if int(sizes.max()) <= 1:
            break
        gi = np.repeat(np.arange(len(starts)), sizes)
        hi_bit = (pos - starts[gi]) >= (sizes[gi] // 2)
        new_g = np.cumsum(np.concatenate([[0], (np.diff(gi * 2 + hi_bit) != 0).astype(np.int64)]))
        for side in (0, 1):
            idx, P = (ax, X) if side == 0 else (ay, Y)
            pr = P[idx] @ d
            lo_, hi_ = float(pr.min()), float(pr.max())
            key = ga + (pr - lo_) * (0.999 / (hi_ - lo_ if hi_ > lo_ else 1.0))   # group id + fraction: 1 sort
            idx = idx[np.argsort(key)]
            if side == 0:
                ax = idx
            else:
                ay = idx
        ga = gb = new_g                         # same split pattern on both sides (sorted by group, then proj)
    return ax, ay


def match(Pa, Pb, mode='morton', slices=8, seed=0, bits=10):
    """Equal-count pairing -> (pa, pb) index arrays: A[pa[i]] flies to B[pb[i]].
    morton: rank along each cloud's own Z-order curve (fast, keeps neighbourhoods together, loose pairs);
    kd: balanced k-d split pairing; sliced: `slices` rounds of sliced-OT flow of A toward B, then k-d pairing of the
    flowed A with B along random directions (closest pairs, slowest); index; random."""
    np = _np()
    n = Pa.shape[0]
    if Pb.shape[0] != n:
        raise ValueError('match needs equal counts ({} vs {})'.format(n, Pb.shape[0]))
    if mode == 'index':
        return np.arange(n), np.arange(n)
    if mode == 'random':
        return np.arange(n), np.random.default_rng(seed).permutation(n)
    if mode == 'kd':
        return kd_match(Pa, Pb)
    if mode == 'sliced':
        Z = sliced_flow(Pa, Pb, slices, seed)
        levels = int(math.ceil(math.log(max(n, 2), 2))) + 1
        return kd_match(Z, Pb, _random_dirs(np.random.default_rng(seed + 31), levels))
    return morton_order(Pa, bits), morton_order(Pb, bits)


def pair_cost(Pa, Pb, pa, pb):
    """Mean travel distance of a pairing."""
    np = _np()
    return float(np.mean(np.linalg.norm(Pa[pa] - Pb[pb], axis=1)))


def stagger_delay(P, mode='radial', seed=0):
    """Per-point delay 0..1 used by Stagger (radial = centre first, axis = bottom first, noise, index)."""
    np = _np()
    n = P.shape[0]
    if n == 0:
        return np.zeros(0, np.float32)
    if mode == 'axis':
        d = P[:, 1].astype(np.float64)
    elif mode == 'noise':
        d = np.random.default_rng(seed + 17).random(n)
    elif mode == 'index':
        d = np.arange(n, dtype=np.float64)
    else:
        d = np.linalg.norm(P - P.mean(0), axis=1)
    lo, hi = float(d.min()), float(d.max())
    return ((d - lo) / (hi - lo) if hi - lo > 1e-12 else np.zeros(n)).astype(np.float32)


def prepare_side(cloud, up='y', outlier=100.0, fit=True, scale=1.0, offset=(0.0, 0.0, 0.0)):
    """Up axis, outlier crop, unit fit, then Scale/Offset. Live depth-TOP sides keep their UV (fit on the proxy)."""
    np = _np()
    P = up_axis_fix(np.asarray(cloud['P'], np.float32), up)
    C = cloud.get('C')
    UV = cloud.get('UV')
    keep = outlier_keep(P, outlier)
    if not keep.all():
        P = P[keep]
        C = C[keep] if C is not None else None
        UV = UV[keep] if UV is not None else None
    centre, radius = np.zeros(3, np.float32), 1.0
    if fit:
        P, centre, radius = fit_unit(P)
    P = (P * float(scale) + np.asarray(offset, np.float32)).astype(np.float32)
    if C is None:
        C = np.ones((P.shape[0], 4), np.float32)
    return {'P': P, 'C': np.asarray(C, np.float32), 'UV': UV, 'n': P.shape[0], 'src': cloud.get('src', ''),
            'centre': centre, 'radius': radius, 'scale': float(scale), 'offset': tuple(offset)}


def build_pair(a, b, count=0, match_mode='kd', slices=8, seed=0, stagger='radial', resample='even'):
    """Two prepared sides -> instance arrays (equal count, matched, delay + seed per point).
    count 0 = max of the two counts. Returns dict with M (20, N) float32 channel matrix (CHANNELS order)."""
    np = _np()
    n = int(count) if int(count) > 0 else max(a['n'], b['n'])
    ia = resample_indices(a['n'], n, seed, resample)
    ib = resample_indices(b['n'], n, seed + 1, resample)
    Pa, Pb = a['P'][ia], b['P'][ib]
    pa, pb = match(Pa, Pb, match_mode, slices, seed)
    ia, ib = ia[pa], ib[pb]
    Pa, Pb = a['P'][ia], b['P'][ib]
    M = np.zeros((len(CHANNELS), n), np.float32)
    M[0:3] = Pa.T
    M[3] = stagger_delay(Pa, stagger, seed)
    M[4:7] = Pb.T
    M[7] = np.random.default_rng(seed + 5).random(n).astype(np.float32)
    M[8:12] = a['C'][ia].T
    M[12:16] = b['C'][ib].T
    if a.get('UV') is not None:
        M[16:18] = a['UV'][ia].T
    if b.get('UV') is not None:
        M[18:20] = b['UV'][ib].T
    return {'M': M, 'n': n, 'ia': ia, 'ib': ib, 'cost': float(np.mean(np.linalg.norm(Pa - Pb, axis=1))),
            'bounds_a': bounds(Pa), 'bounds_b': bounds(Pb)}


SIDE_DEFAULTS = {'source': 'gen', 'file': '', 'gen': 'sphere', 'depthfile': '', 'colourfile': '', 'up': 'y',
                 'outlier': 100.0, 'fit': True, 'scale': 1.0, 'offset': (0.0, 0.0, 0.0), 'kind': 'inverse',
                 'fov': 60.0, 'znear': 1.0, 'zfar': 10.0, 'lo': 0.0, 'hi': 1.0, 'depthauto': True, 'step': 4,
                 'aspect': 16.0 / 9.0, 'has_colour_top': False, 'seed': 0}


def load_side(spec, n_hint=100000):
    """One side from its spec (SIDE_DEFAULTS keys) -> prepared side + 'tex' uniforms (for depth-TOP sides).
    Depth sides are already TD camera space: the Up axis applies to files only."""
    s = dict(SIDE_DEFAULTS)
    s.update(spec or {})
    src = s['source']
    up = s['up']
    if src == 'file':
        cloud = load_cloud(s['file'])
    elif src == 'depthfile':
        d = read_depth_file(s['depthfile'])
        col = read_colour_file(s['colourfile']) if s['colourfile'] else None
        lo, hi = (None, None) if s['depthauto'] else (s['lo'], s['hi'])
        cloud = unproject_depth(d, s['fov'], s['znear'], s['zfar'], lo, hi, s['kind'], s['step'], col)
        up = 'y'
    elif src == 'depthtex':
        cloud = depthtex_proxy(max(1, int(n_hint)), s['aspect'], s['fov'], s['znear'], s['zfar'], s['kind'])
        up = 'y'
    else:
        cloud = generate(s['gen'], max(1, int(n_hint)), s['seed'])
    side = prepare_side(cloud, up, 100.0 if src == 'depthtex' else s['outlier'], s['fit'], s['scale'], s['offset'])
    if src == 'depthtex':
        k = (s['scale'] / side['radius']) if s['fit'] else s['scale']
        c = side['centre'] if s['fit'] else (0.0, 0.0, 0.0)
        side['tex'] = {'tex': (1.0, s['fov'], s['znear'], s['zfar']), 'fit': (float(c[0]), float(c[1]), float(c[2]), k),
                       'off': (float(s['offset'][0]), float(s['offset'][1]), float(s['offset'][2]), s['aspect']),
                       'kind': 1.0 if s['kind'] == 'depth' else 0.0, 'hascol': 1.0 if s['has_colour_top'] else 0.0,
                       'lohi': (s['lo'], s['hi'])}
    else:
        side['tex'] = {'tex': (0.0, s['fov'], s['znear'], s['zfar']), 'fit': (0.0, 0.0, 0.0, 1.0),
                       'off': (0.0, 0.0, 0.0, 1.0), 'kind': 0.0, 'hascol': 0.0, 'lohi': (0.0, 1.0)}
    return side


def load_pair(spec_a, spec_b, count=0, match_mode='kd', slices=8, seed=0, stagger='radial', resample='even'):
    """Both sides: files/depth files first; generators and depth-TOP grids get N = Count or the file side's count."""
    sa = dict(SIDE_DEFAULTS, **(spec_a or {}))
    sb = dict(SIDE_DEFAULTS, **(spec_b or {}))
    fixed = ('file', 'depthfile')
    n_hint = int(count) if int(count) > 0 else 0
    a = load_side(sa, n_hint or 100000) if sa['source'] in fixed else None
    b = load_side(sb, n_hint or 100000) if sb['source'] in fixed else None
    if not n_hint:
        n_hint = max([x['n'] for x in (a, b) if x is not None] or [100000])
    if a is None:
        a = load_side(sa, n_hint)
    if b is None:
        b = load_side(sb, n_hint)
    return a, b, build_pair(a, b, count, match_mode, slices, seed, stagger, resample)


def bounds(P):
    np = _np()
    if P.shape[0] == 0:
        return {'min': (0.0, 0.0, 0.0), 'max': (0.0, 0.0, 0.0), 'center': (0.0, 0.0, 0.0), 'radius': 0.0}
    lo, hi = P.min(0), P.max(0)
    c = (lo + hi) * 0.5
    return {'min': tuple(float(x) for x in lo), 'max': tuple(float(x) for x in hi),
            'center': tuple(float(x) for x in c), 'radius': float(np.linalg.norm(P - c, axis=1).max())}


# ---------------------------------------------------------------- morph maths (mirrored in the vertex shader)

def ease(x, kind='linear'):
    """Scalar or numpy array, clamped to 0..1."""
    try:
        import numpy as np
        arr = isinstance(x, np.ndarray)
    except ImportError:  # pragma: no cover
        arr = False
    if arr:
        x = np.clip(x, 0.0, 1.0)
        cos = np.cos
    else:
        x = 0.0 if x < 0 else (1.0 if x > 1 else float(x))
        cos = math.cos
    if kind == 'in':
        return x * x
    if kind == 'out':
        return 1.0 - (1.0 - x) * (1.0 - x)
    if kind == 'inout':
        return x * x * (3.0 - 2.0 * x)
    if kind == 'sine':
        return 0.5 - 0.5 * cos(math.pi * x)
    return x


def point_morph(m, delay, stagger=0.0, kind='linear'):
    """Per-point eased morph: e = ease(clamp(m*(1+s) - d*s)). m=0 -> 0 and m=1 -> 1 for every delay d in 0..1."""
    np = _np()
    s = max(float(stagger), 0.0)
    return ease(np.clip(float(m) * (1.0 + s) - np.asarray(delay, np.float64) * s, 0.0, 1.0), kind)


def morph_positions(Pa, Pb, e, arc=0.0, offset=None):
    """mix(Pa, Pb, e) + arc * offset * sin(pi e): offset (n,3) = the shader's noise direction (any; 0 at both ends)."""
    np = _np()
    e = np.asarray(e, np.float64)[..., None]
    P = Pa + (Pb - Pa) * e
    if arc and offset is not None:
        P = P + float(arc) * np.asarray(offset) * np.sin(math.pi * e)
    return P


def morph_bpm(beats, beats_per_swap=4.0, morph_beats=1.0):
    """Ping-pong: hold A, fly to B over morph_beats, hold B, fly back. A cycle = 2 * beats_per_swap beats.
    Returns the raw morph 0..1 (easing is per point, in the shader)."""
    bps = max(float(beats_per_swap), 1e-6)
    mb = min(max(float(morph_beats), 0.0), bps)
    ph = math.fmod(float(beats), 2.0 * bps)
    if ph < 0:
        ph += 2.0 * bps
    half, local = (0, ph) if ph < bps else (1, ph - bps)
    hold = bps - mb
    if local < hold:
        x = 0.0
    else:
        x = 1.0 if mb <= 0 else (local - hold) / mb
    return x if half == 0 else 1.0 - x


def morph_lfo(t, rate_hz):
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * float(rate_hz) * float(t))


def smooth(prev, x, dt, attack=0.05, release=0.3):
    """One-pole follower: separate rise/fall times in seconds (0 = instant)."""
    if prev is None:
        return float(x)
    tau = attack if x > prev else release
    if tau <= 0 or dt <= 0:
        return float(x)
    k = 1.0 - math.exp(-dt / tau)
    return prev + (x - prev) * k


def orbit_position(az_deg, el_deg, dist, target=(0.0, 0.0, 0.0)):
    """Camera position on a sphere around target; az 0 / el 0 = on +Z looking at the target (TD default view)."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    return (target[0] + dist * math.cos(e) * math.sin(a), target[1] + dist * math.sin(e),
            target[2] + dist * math.cos(e) * math.cos(a))


def frame_distance(radius, fov_deg, margin=1.15):
    return margin * max(radius, 1e-6) / math.tan(math.radians(max(fov_deg, 1e-3)) * 0.5)


def focal_px(h, vfov_deg):
    return 0.5 * h / math.tan(math.radians(vfov_deg) * 0.5)


def radius_px(size, sizebydepth, refdist, z, dof=0.0, focus=0.0):
    """Point radius in pixels (shader mirror): Size at refdist, perspective blend, plus DOF growth |z-focus|*dof."""
    persp = refdist / max(z, 1e-4)
    r = size * ((1.0 - sizebydepth) + sizebydepth * persp)
    return r + abs(z - focus) * dof if dof > 0 else r


def shape_alpha(shape, qx, qy):
    """Pixel-shader mirror without the 1-px anti-alias band: coverage of a quad corner coordinate (-1..1)."""
    r = math.hypot(qx, qy)
    if shape == 'soft':
        return math.exp(-4.0 * r * r) if r < 1.0 else 0.0
    if shape == 'square':
        return 1.0
    if shape == 'ring':
        return 1.0 if 0.6 <= r < 1.0 else 0.0
    if shape == 'streak':
        return (1.0 if abs(qy) < 1.0 else 0.0) * (0.15 + 0.85 * (qx * 0.5 + 0.5))
    return 1.0 if r < 1.0 else 0.0


def post_pixel(rgba, gain=1.0, tonemap=False, bg=(0.0, 0.0, 0.0, 0.0), outputalpha=True, premult=True):
    """Compute-post mirror for one premultiplied pixel."""
    r, g, b, a = [float(x) for x in rgba]
    c = [r * gain, g * gain, b * gain]
    if tonemap:
        c = [x / (1.0 + x) for x in c]
    a = min(max(a, 0.0), 1.0)
    c = [x + bg[i] * bg[3] * (1.0 - a) for i, x in enumerate(c)]
    a = a + bg[3] * (1.0 - a)
    if not outputalpha:
        return (c[0], c[1], c[2], 1.0)
    if not premult:
        c = [x / max(a, 1e-6) for x in c]
    return (c[0], c[1], c[2], a)


DEFAULTS = {'mode': 'manual', 'morph': 0.0, 'tempo': 'project', 'bpm': 120.0, 'project_bpm': 120.0,
            'beatsperswap': 4.0, 'morphbeats': 1.0, 'rate': 0.1, 'audiogain': 1.0, 'attack': 0.05, 'release': 0.3,
            'autorbit': 0.0, 'orbitaz': 0.0, 'orbitel': 10.0, 'orbitdist': 3.0, 'target': (0.0, 0.0, 0.0)}


def engine_step(st, t, p, level=0.0):
    """Once per frame (Script CHOP `engine`). st: plain dict (None = fresh). -> (st, out) with out =
    morph (raw 0..1), beat, bpm, level (smoothed), az, camx, camy, camz, t."""
    q = dict(DEFAULTS)
    q.update(p or {})
    if st is None:
        st = {'t0': float(t), 'last_t': float(t), 'lvl': None, 'az_off': 0.0}
    dt = max(float(t) - st['last_t'], 0.0)
    st['last_t'] = float(t)
    bpm = float(q['bpm']) if q['tempo'] == 'manual' else float(q['project_bpm'])
    beats = (float(t) - st['t0']) * bpm / 60.0
    st['lvl'] = smooth(st['lvl'], float(level), dt, q['attack'], q['release'])
    mode = q['mode']
    if mode == 'bpm':
        m = morph_bpm(beats, q['beatsperswap'], q['morphbeats'])
    elif mode == 'lfo':
        m = morph_lfo(float(t) - st['t0'], q['rate'])
    elif mode == 'audio':
        m = st['lvl'] * float(q['audiogain'])
    else:
        m = float(q['morph'])
    st['az_off'] = math.fmod(st['az_off'] + float(q['autorbit']) * dt, 360.0)
    az = float(q['orbitaz']) + st['az_off']
    cam = orbit_position(az, float(q['orbitel']), float(q['orbitdist']), tuple(q['target']))
    out = {'morph': m, 'beat': beats, 'bpm': bpm, 'level': st['lvl'], 'az': az, 'camx': cam[0], 'camy': cam[1],
           'camz': cam[2], 't': float(t) - st['t0']}
    return st, out


ENGINE_CHANNELS = ['morph', 'beat', 'bpm', 'level', 'az', 'camx', 'camy', 'camz', 't']


def status_line(pair, a, b, load_ms, err=None):
    if err:
        return 'ERROR: {}'.format(err)[:200]
    return 'A {} | B {} | N {} | travel {:.3f} | {:.0f} ms'.format(a.get('src', '?'), b.get('src', '?'), pair['n'],
                                                                    pair['cost'], load_ms)[:200]
