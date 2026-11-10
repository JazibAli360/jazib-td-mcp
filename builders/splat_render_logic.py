"""splat_render_logic: pure logic for /project1/lab/BL_splat_render (Gaussian splat renderer).

Clean-room, from the published 3DGS maths (docs/research/BL_gaussian_splats_pointclouds.md sections 2 + 5 + 7.1).
No `td` import: tested offline (test/test_splat_render.py) and copied into the COMP as the Text DAT
`splat_render_logic`. numpy is imported lazily so the module still loads (and reports why) if TD's numpy breaks (T-48).

Conventions (TD, right-handed, Y up, camera looks down -Z):
- splat arrays: P (n,3) world position, S (n,3) LINEAR scale (sigma), Q (n,4) unit quaternion (w,x,y,z),
  C (n,4) rgb = SH degree-0 colour (0.5 + C0 * f_dc, >= 0) + alpha (0..1, already sigmoid), SH1 (n,3,3) [coeff][rgb]
  or None. Coefficient order of SH1: INRIA's (c1 ~ -y, c2 ~ z, c3 ~ -x).
- pixel coords: u right, v UP from the bottom row (= numpyArray row order, T-58).
"""
import gzip
import math
import struct

SH_C0 = 0.28209479177387814
SH_C1 = 0.4886025119029199

FORMATS = [('auto', 'Auto (extension)'), ('ply', 'PLY (INRIA / points)'), ('splat', '.splat (antimatter15)'),
           ('spz', '.spz v2/v3 (Niantic)')]
COORDFIX = [('auto', 'Auto (ply/splat rotX180, spz none)'), ('none', 'None'), ('flipy', 'Flip Y'), ('flipz', 'Flip Z'),
            ('rotx180', 'Rotate X 180')]
SORTMODE = [('sortpop', 'Sort POP (GPU radix)'), ('cpu', 'CPU (numpy radix)'), ('sortfree', 'Sort-free (weighted sum)'),
            ('frozen', 'Frozen (keep order)')]
CAMMODE = [('orbit', 'Internal orbit'), ('external', 'External camera')]
ORBITSYNC = [('none', 'None (deg/s)'), ('bpm', 'BPM (beats per rev)'), ('audio', 'Audio (speed x level)')]
AUDIOTARGETS = ('scale', 'opacity', 'explode', 'noise', 'orbit')
SHDEGREE = [('0', 'SH 0 (flat colour)'), ('1', 'SH 1 (view-dependent)')]
# Render size vs Resolution (perf wave 27 Oct): the splat render can run smaller and post scales it back up
RENDERSCALE = [('full', 'Full (Resolution)'), ('s75', '3/4'), ('s50', '1/2')]  # vertex-bound: 3/4 saves ~0.6 ms GPU, its upscale costs ~0.45
_RSCALE = {'full': 1.0, 's75': 0.75, 's50': 0.5}


def render_size(w, h, scale='full'):
    """Splat render width, height for Resolution w x h at a Renderscale menu value (unknown = full)."""
    s = _RSCALE.get(scale, 1.0)
    return max(1, int(round(float(w) * s))), max(1, int(round(float(h) * s)))


def post_identity(sortmode, has_bg, bg_alpha, outputalpha, premult, scale='full'):
    """True when the post pass would only copy the render (no sort-free normalise, no background, alpha kept,
    premultiplied, render already at Resolution): out1 then takes the render directly and post does not cook."""
    return (sortmode != 'sortfree' and not has_bg and bg_alpha <= 0.0 and bool(outputalpha) and bool(premult)
            and _RSCALE.get(scale, 1.0) == 1.0)

PLY_TYPES = {'char': 'i1', 'int8': 'i1', 'uchar': 'u1', 'uint8': 'u1', 'short': 'i2', 'int16': 'i2',
             'ushort': 'u2', 'uint16': 'u2', 'int': 'i4', 'int32': 'i4', 'uint': 'u4', 'uint32': 'u4',
             'float': 'f4', 'float32': 'f4', 'double': 'f8', 'float64': 'f8'}


def _np():
    import numpy
    return numpy


def menu_index(menu, name):
    for i, m in enumerate(menu):
        if m[0] == name:
            return i
    return 0


# ---------------------------------------------------------------- formats

def detect_format(path, fmt='auto'):
    if fmt and fmt != 'auto':
        return fmt
    p = str(path).lower()
    for ext in ('ply', 'splat', 'spz'):
        if p.endswith('.' + ext):
            return ext
    raise ValueError('unknown splat file extension: {}'.format(path))


def parse_ply_header(data):
    """bytes -> (format, count, [(name, np type)], header_len). Only the first element (vertex) is used."""
    end = data.find(b'end_header')
    if not data.startswith(b'ply') or end < 0:
        raise ValueError('not a PLY file')
    nl = data.find(b'\n', end)
    header_len = nl + 1
    fmt, count, props, in_vertex = None, 0, [], False
    for line in data[:end].decode('ascii', 'replace').splitlines():
        w = line.split()
        if not w:
            continue
        if w[0] == 'format':
            fmt = w[1]
        elif w[0] == 'element':
            in_vertex = (w[1] == 'vertex')
            if in_vertex:
                count = int(w[2])
        elif w[0] == 'property' and in_vertex:
            if w[1] == 'list':
                raise ValueError('list properties in the vertex element are not supported')
            props.append((w[2], PLY_TYPES[w[1]]))
    if fmt not in ('binary_little_endian', 'ascii'):
        raise ValueError('PLY format {} not supported (binary_little_endian / ascii)'.format(fmt))
    return fmt, count, props, header_len


def _sigmoid(x):
    np = _np()
    return 1.0 / (1.0 + np.exp(-x))


def load_ply(path):
    """INRIA Gaussian .ply (x y z f_dc_* f_rest_* opacity scale_* rot_*) or a plain point cloud
    (x y z [red green blue [alpha]] uchar or float). Returns a raw dict (see _finish)."""
    np = _np()
    with open(path, 'rb') as f:
        head = f.read(65536)
    fmt, n, props, hl = parse_ply_header(head)
    dt = np.dtype([(nm, '<' + t) for nm, t in props])
    if fmt == 'ascii':
        rows = np.loadtxt(path, skiprows=head[:hl].count(b'\n'), max_rows=n, ndmin=2)
        v = np.zeros(n, dtype=dt)
        for i, (nm, _) in enumerate(props):
            v[nm] = rows[:, i]
    else:
        v = np.fromfile(path, dtype=dt, count=n, offset=hl)
    names = [p[0] for p in props]
    P = np.stack([v['x'], v['y'], v['z']], 1).astype(np.float32)
    if 'scale_0' in names:
        S = np.exp(np.stack([v['scale_0'], v['scale_1'], v['scale_2']], 1).astype(np.float32))
        Q = np.stack([v['rot_0'], v['rot_1'], v['rot_2'], v['rot_3']], 1).astype(np.float32)
        A = _sigmoid(v['opacity'].astype(np.float32)) if 'opacity' in names else np.ones(n, np.float32)
        dc = np.stack([v['f_dc_0'], v['f_dc_1'], v['f_dc_2']], 1).astype(np.float32)
        rest = sorted([nm for nm in names if nm.startswith('f_rest_')], key=lambda s: int(s[7:]))
        sh1 = None
        if len(rest) >= 9:
            per = len(rest) // 3                      # coefficients per channel (channel-major)
            R = np.stack([v[nm] for nm in rest], 1).astype(np.float32).reshape(n, 3, per)
            sh1 = np.transpose(R[:, :, :3], (0, 2, 1)).copy()   # (n, coeff, rgb)
        return {'P': P, 'S': S, 'Q': Q, 'dc': dc, 'A': A, 'sh1': sh1, 'kind': 'gaussian', 'sh_degree': _sh_deg(len(rest))}
    # plain point cloud
    rgb = None
    for keys in (('red', 'green', 'blue'), ('r', 'g', 'b'), ('diffuse_red', 'diffuse_green', 'diffuse_blue')):
        if all(k in names for k in keys):
            rgb = np.stack([v[k] for k in keys], 1).astype(np.float32)
            break
    if rgb is None:
        rgb = np.ones((n, 3), np.float32)
    elif rgb.max() > 1.0:
        rgb = rgb / (255.0 if rgb.max() > 127.5 else 127.0)
    A = np.ones(n, np.float32)
    for k in ('alpha', 'a'):
        if k in names:
            A = v[k].astype(np.float32)
            A = A / 255.0 if A.max() > 1.0 else A
    Q = np.zeros((n, 4), np.float32)
    Q[:, 0] = 1.0
    return {'P': P, 'S': None, 'Q': Q, 'rgb': rgb, 'A': A, 'sh1': None, 'kind': 'points', 'sh_degree': 0}


def _sh_deg(rest_count):
    per = rest_count // 3
    return {0: 0, 3: 1, 8: 2, 15: 3}.get(per, 0)


def load_splat(path):
    """antimatter15 .splat: 32 B/splat = f32x3 pos, f32x3 LINEAR scale, u8x4 RGBA, u8x4 quat (w,x,y,z) (u8-128)/128."""
    np = _np()
    raw = np.fromfile(path, dtype=np.uint8)
    if raw.size % 32:
        raise ValueError('.splat size {} is not a multiple of 32'.format(raw.size))
    n = raw.size // 32
    rec = raw.reshape(n, 32)
    f = rec[:, :24].copy().view('<f4').reshape(n, 6)
    rgba = rec[:, 24:28].astype(np.float32) / 255.0
    Q = (rec[:, 28:32].astype(np.float32) - 128.0) / 128.0
    return {'P': f[:, :3].copy(), 'S': f[:, 3:6].copy(), 'Q': Q, 'rgb': rgba[:, :3].copy(), 'A': rgba[:, 3].copy(),
            'sh1': None, 'kind': 'gaussian', 'sh_degree': 0}


def spz_header(data):
    magic, version, n, shdeg, frac, flags, _ = struct.unpack('<IIIBBBB', data[:16])
    if magic != 0x5053474E:
        raise ValueError('not an SPZ (magic {:#x})'.format(magic))
    return {'version': version, 'count': n, 'sh_degree': shdeg, 'fractional_bits': frac, 'flags': flags}


def _spz_quat_v3(r):
    """'smallest three' 32-bit packing (spz v3): 2 bits index of the largest, 3 x (1 sign + 9 magnitude bits)."""
    np = _np()
    comp = (r[:, 0].astype(np.uint32) | (r[:, 1].astype(np.uint32) << 8) | (r[:, 2].astype(np.uint32) << 16)
            | (r[:, 3].astype(np.uint32) << 24))
    largest = (comp >> 30).astype(np.int64)
    xyzw = np.zeros((r.shape[0], 4), np.float32)
    mask = np.uint32(511)
    ss = np.zeros(r.shape[0], np.float32)
    c = comp.copy()
    for i in (3, 2, 1, 0):
        sel = largest != i
        mag = (c & mask).astype(np.float32)
        neg = ((c >> 9) & 1).astype(bool)
        val = np.float32(math.sqrt(0.5)) * mag / 511.0
        val = np.where(neg, -val, val)
        xyzw[sel, i] = val[sel]
        ss[sel] += val[sel] ** 2
        c = np.where(sel, c >> 10, c)
    xyzw[np.arange(r.shape[0]), largest] = np.sqrt(np.maximum(0.0, 1.0 - ss))
    return np.stack([xyzw[:, 3], xyzw[:, 0], xyzw[:, 1], xyzw[:, 2]], 1)


def load_spz(path):
    """Niantic .spz v2/v3 (gzip): positions 24-bit fixed, alpha u8, colour u8 -> f_dc, log-scale u8, rotation
    (v2 3 bytes xyz, v3 4 bytes smallest-three), SH u8 (per splat: coeff-major, rgb). Coordinates as stored (RUB)."""
    np = _np()
    with gzip.open(path, 'rb') as f:
        data = f.read()
    h = spz_header(data)
    n, v = h['count'], h['version']
    if v not in (2, 3):
        raise ValueError('SPZ version {} not supported (2/3; SPZ 4 needs zstd)'.format(v))
    o = 16
    pos = np.frombuffer(data, np.uint8, n * 9, o).reshape(n, 3, 3).astype(np.int32)
    o += n * 9
    fixed = pos[:, :, 0] | (pos[:, :, 1] << 8) | (pos[:, :, 2] << 16)
    fixed = np.where(fixed & 0x800000, fixed - (1 << 24), fixed)
    P = (fixed.astype(np.float32) / float(1 << h['fractional_bits'])).astype(np.float32)
    A = np.frombuffer(data, np.uint8, n, o).astype(np.float32) / 255.0
    o += n
    col = np.frombuffer(data, np.uint8, n * 3, o).reshape(n, 3).astype(np.float32)
    o += n * 3
    dc = (col / 255.0 - 0.5) / 0.15
    S = np.exp(np.frombuffer(data, np.uint8, n * 3, o).reshape(n, 3).astype(np.float32) / 16.0 - 10.0)
    o += n * 3
    if v == 2:
        r = np.frombuffer(data, np.uint8, n * 3, o).reshape(n, 3).astype(np.float32) / 127.5 - 1.0
        o += n * 3
        w = np.sqrt(np.maximum(0.0, 1.0 - (r * r).sum(1)))
        Q = np.concatenate([w[:, None], r], 1).astype(np.float32)
    else:
        Q = _spz_quat_v3(np.frombuffer(data, np.uint8, n * 4, o).reshape(n, 4))
        o += n * 4
    dim = {0: 0, 1: 3, 2: 8, 3: 15}[h['sh_degree']]
    sh1 = None
    if dim:
        sh = np.frombuffer(data, np.uint8, n * dim * 3, o).reshape(n, dim, 3)
        sh1 = (sh[:, :3, :].astype(np.float32) - 128.0) / 128.0
        o += n * dim * 3
    out = {'P': P, 'S': S.astype(np.float32), 'Q': Q, 'dc': dc.astype(np.float32), 'A': A, 'sh1': sh1,
           'kind': 'gaussian', 'sh_degree': h['sh_degree'], 'tail_bytes': len(data) - o}
    return out


def load_any(path, fmt='auto'):
    f = detect_format(path, fmt)
    return f, {'ply': load_ply, 'splat': load_splat, 'spz': load_spz}[f](path)


# ---------------------------------------------------------------- prep

def coordfix_matrix(fix, fmt):
    if fix == 'auto':
        fix = 'none' if fmt == 'spz' else 'rotx180'
    return {'none': (1, 1, 1), 'flipy': (1, -1, 1), 'flipz': (1, 1, -1), 'rotx180': (1, -1, -1)}[fix]


def apply_coordfix(P, Q, sh1, sign):
    """p' = F p with F = diag(sign). Rotation R' = F R F -> q' = (w, d*sx*x, d*sy*y, d*sz*z), d = det F.
    SH1 (c1~-y, c2~z, c3~-x) coefficients flip with sy, sz, sx."""
    np = _np()
    s = np.array(sign, np.float32)
    d = float(s[0] * s[1] * s[2])
    P = P * s
    Q = Q * np.array([1.0, d * s[0], d * s[1], d * s[2]], np.float32)
    if sh1 is not None:
        sh1 = sh1 * np.array([s[1], s[2], s[0]], np.float32)[None, :, None]
    return P, Q, sh1


def normalize_quats(Q):
    np = _np()
    n = np.linalg.norm(Q, axis=1, keepdims=True)
    bad = n[:, 0] < 1e-12
    Q = Q / np.maximum(n, 1e-12)
    Q[bad] = (1.0, 0.0, 0.0, 0.0)
    return Q.astype(np.float32)


def thin_indices(n, step=1, random_frac=0.0, seed=0):
    """Index thinning: every step-th splat, then keep a random fraction (1 - random_frac) of those."""
    np = _np()
    idx = np.arange(0, n, max(1, int(step)), dtype=np.int64)
    if random_frac > 0:
        rng = np.random.default_rng(int(seed))
        idx = idx[rng.random(idx.size) >= float(random_frac)]
    return idx


def crop_mask(P, center=(0, 0, 0), size=(0, 0, 0), radius=0.0):
    """True = keep. size component <= 0 = no crop on that axis; radius <= 0 = no sphere crop."""
    np = _np()
    keep = np.ones(P.shape[0], bool)
    c = np.array(center, np.float32)
    for ax in range(3):
        if size[ax] > 0:
            keep &= np.abs(P[:, ax] - c[ax]) <= size[ax] * 0.5
    if radius > 0:
        keep &= ((P - c) ** 2).sum(1) <= radius * radius
    return keep


def importance(A, S):
    """opacity x ellipsoid volume (scale product), the budget ranking."""
    return A * S[:, 0] * S[:, 1] * S[:, 2]


def importance_budget(A, S, k):
    """Indices of the k most important splats (k <= 0 or >= n: all), in original order."""
    np = _np()
    n = A.shape[0]
    if k <= 0 or k >= n:
        return np.arange(n)
    imp = importance(A, S)
    part = np.argpartition(-imp, k - 1)[:k]
    return np.sort(part)


def prepare(raw, fmt, coordfix='auto', shdegree=1, point_scale=0.01, maxsplats=0, thinstep=1, thinrandom=0.0,
            opacitycull=0.0, crop_center=(0, 0, 0), crop_size=(0, 0, 0), crop_radius=0.0, seed=0):
    """raw loader dict -> render arrays (P, S, Q, C, SH1) + stats. Order: thin -> coordfix -> crop -> cull -> budget."""
    np = _np()
    P, Q, A = raw['P'], raw['Q'], raw['A']
    S = raw['S'] if raw.get('S') is not None else np.full_like(P, float(point_scale))
    if 'dc' in raw:
        rgb = 0.5 + SH_C0 * raw['dc']
    else:
        rgb = raw['rgb']
    sh1 = raw.get('sh1') if int(shdegree) >= 1 else None
    n0 = P.shape[0]
    idx = thin_indices(n0, thinstep, thinrandom, seed)
    P, Q, A, S, rgb = P[idx], Q[idx], A[idx], S[idx], rgb[idx]
    sh1 = sh1[idx] if sh1 is not None else None
    P, Q, sh1 = apply_coordfix(P, Q, sh1, coordfix_matrix(coordfix, fmt))
    keep = crop_mask(P, crop_center, crop_size, crop_radius) & (A >= float(opacitycull))
    P, Q, A, S, rgb = P[keep], Q[keep], A[keep], S[keep], rgb[keep]
    sh1 = sh1[keep] if sh1 is not None else None
    sel = importance_budget(A, S, int(maxsplats))
    P, Q, A, S, rgb = P[sel], Q[sel], A[sel], S[sel], rgb[sel]
    sh1 = sh1[sel] if sh1 is not None else None
    C = np.concatenate([np.maximum(rgb, 0.0), A[:, None]], 1).astype(np.float32)
    out = {'P': P.astype(np.float32), 'S': S.astype(np.float32), 'Q': normalize_quats(Q), 'C': C,
           'SH1': None if sh1 is None else sh1.astype(np.float32), 'file_count': n0, 'count': int(P.shape[0])}
    out['bounds'] = bounds(out['P'])
    return out


def bounds(P):
    np = _np()
    if P.shape[0] == 0:
        return {'min': [0, 0, 0], 'max': [0, 0, 0], 'center': [0, 0, 0], 'radius': 0.0, 'p50_radius': 0.0}
    mn, mx = P.min(0), P.max(0)
    med = np.median(P, 0)
    r = np.sqrt(((P - med) ** 2).sum(1))
    return {'min': mn.tolist(), 'max': mx.tolist(), 'center': med.tolist(), 'radius': float(np.percentile(r, 98)),
            'p50_radius': float(np.percentile(r, 50))}


CHANNELS = ['tx', 'ty', 'tz', 'sx', 'sy', 'sz', 'sid', 'qw', 'qx', 'qy', 'qz', 'r', 'g', 'b', 'a']
SH_CHANNELS = ['shr0', 'shr1', 'shr2', 'shg0', 'shg1', 'shg2', 'shb0', 'shb1', 'shb2']


def channel_matrix(prep, order=None, with_sh=True):
    """(channels, samples) float32 for a Script CHOP; order = permutation (draw order) or None."""
    np = _np()
    sid = np.arange(prep['count'], dtype=np.float32)[:, None]      # stable splat id (dissolve hash survives sorting)
    cols = [prep['P'], prep['S'], sid, prep['Q'], prep['C']]
    names = list(CHANNELS)
    if with_sh:
        sh = prep['SH1'] if prep['SH1'] is not None else np.zeros((prep['count'], 3, 3), np.float32)
        cols.append(np.transpose(sh, (0, 2, 1)).reshape(-1, 9))      # rgb-major: r(c1 c2 c3), g(...), b(...)
        names += SH_CHANNELS
    M = np.concatenate(cols, 1)
    if order is not None:
        M = M[order]
    return names, np.ascontiguousarray(M.T, dtype=np.float32)


# ---------------------------------------------------------------- maths (mirrors the GLSL MAT)

def quat_to_mat3(q):
    """(w,x,y,z) -> 3x3 rotation (normalised first). Works on (4,) or (n,4)."""
    np = _np()
    q = np.asarray(q, np.float64)
    single = q.ndim == 1
    q = q.reshape(-1, 4)
    q = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-12)
    w, x, y, z = q.T
    R = np.stack([
        np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], 1),
        np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], 1),
        np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], 1)], 1)
    return R[0] if single else R


def cov3d(s, q):
    """Sigma = R S S^T R^T (s = linear scale)."""
    np = _np()
    R = quat_to_mat3(q)
    M = R @ np.diag(np.asarray(s, np.float64))
    return M @ M.T


def orbit_camera(az_deg, el_deg, dist, target=(0, 0, 0)):
    """Camera on a sphere around target looking at it. Returns pos, forward, rx, ry (TD rotate order xyz:
    R = Ry(ry) Rx(rx)) and the 4x4 view matrix (world -> camera, camera looks down -Z)."""
    np = _np()
    a, e = math.radians(az_deg), math.radians(el_deg)
    t = np.asarray(target, np.float64)
    off = np.array([math.cos(e) * math.sin(a), math.sin(e), math.cos(e) * math.cos(a)])
    pos = t + dist * off
    rx, ry = -el_deg, az_deg
    world = np.eye(4)
    world[:3, :3] = _rot_y(ry) @ _rot_x(rx)
    world[:3, 3] = pos
    view = np.linalg.inv(world)
    return {'pos': pos, 'forward': -off, 'rx': rx, 'ry': ry, 'world': world, 'view': view}


def _rot_x(deg):
    np = _np()
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_y(deg):
    np = _np()
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def focal_px(h, vfov_deg):
    """Square pixels: focal length in pixels from the vertical fov and the image height."""
    return 0.5 * h / math.tan(math.radians(vfov_deg) * 0.5)


def project_cov2d(p_world, sigma, view, fx, fy, w, h, lowpass=0.3):
    """Mean (u,v pixels, v up) and 2x2 covariance (pixels^2) of a 3D Gaussian. None if behind the camera.
    Camera space x right, y up, z back; depth z' = -z. u = w/2 + fx x/z', v = h/2 + fy y/z'."""
    np = _np()
    pc = view[:3, :3] @ np.asarray(p_world, np.float64) + view[:3, 3]
    zp = -pc[2]
    if zp <= 1e-6:
        return None
    limx, limy = 1.3 * (0.5 * w / fx), 1.3 * (0.5 * h / fy)
    tx = min(max(pc[0] / zp, -limx), limx) * zp
    ty = min(max(pc[1] / zp, -limy), limy) * zp
    J = np.array([[fx / zp, 0.0, fx * tx / (zp * zp)],
                  [0.0, fy / zp, fy * ty / (zp * zp)]])
    T = J @ view[:3, :3]
    cov = T @ sigma @ T.T
    cov[0, 0] += lowpass
    cov[1, 1] += lowpass
    mean = np.array([0.5 * w + fx * pc[0] / zp, 0.5 * h + fy * pc[1] / zp])
    return mean, cov, zp


def conic_from_cov(cov):
    a, b, c = cov[0, 0], cov[0, 1], cov[1, 1]
    det = a * c - b * b
    if det <= 0:
        return None
    return (c / det, -b / det, a / det)


def eigen2(cov):
    """Eigenvalues (l1 >= l2) and the major axis unit vector of a symmetric 2x2."""
    a, b, c = cov[0, 0], cov[0, 1], cov[1, 1]
    mid = 0.5 * (a + c)
    rad = math.sqrt(max(mid * mid - (a * c - b * b), 0.0))
    l1, l2 = mid + rad, max(mid - rad, 1e-12)
    if abs(b) > 1e-12:
        v = (b, l1 - a)
    else:
        v = (1.0, 0.0) if a >= c else (0.0, 1.0)
    n = math.hypot(*v)
    return l1, l2, (v[0] / n, v[1] / n)


def quad_sigma_extent(alpha, thr):
    """Quad half-size in sigmas: where alpha*exp(-k^2/2) drops to the discard threshold, at most 3."""
    t = max(thr, 1.0 / 255.0)
    if alpha <= t:
        return 0.0
    return min(3.0, math.sqrt(2.0 * math.log(alpha / t)))


def sh_eval_deg1(dc_rgb, sh1, direction):
    """Colour = (0.5 + C0 f_dc) + C1 (-y c1 + z c2 - x c3); direction = normalize(p - cam), in the splat's frame."""
    np = _np()
    d = np.asarray(direction, np.float64)
    d = d / np.linalg.norm(d)
    x, y, z = d
    sh1 = np.asarray(sh1, np.float64)
    return np.maximum(np.asarray(dc_rgb, np.float64) + SH_C1 * (-y * sh1[0] + z * sh1[1] - x * sh1[2]), 0.0)


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------- sort

def view_depth(P, cam_pos, forward):
    np = _np()
    f = np.asarray(forward, np.float32)
    f = f / max(float(np.linalg.norm(f)), 1e-12)
    return (P - np.asarray(cam_pos, np.float32)) @ f


def depth_keys_u16(depth):
    """Quantise depth to uint16 over [min, max], FAR = 0 (so an ascending sort is back to front)."""
    np = _np()
    d = np.asarray(depth, np.float32)
    lo, hi = float(d.min()), float(d.max())
    span = hi - lo if hi > lo else 1.0
    q = np.clip((hi - d) / span * 65535.0, 0, 65535).astype(np.uint16)
    return q


def radix_order(keys):
    """Stable ascending order of uint16 keys (numpy uses radix sort for 16-bit with kind='stable')."""
    np = _np()
    return np.argsort(keys, kind='stable')


def back_to_front(P, cam_pos, forward):
    return radix_order(depth_keys_u16(view_depth(P, cam_pos, forward)))


def inversion_fraction(depth_in_draw_order):
    """Fraction of adjacent pairs drawn front before back (depth increasing = wrong for back-to-front)."""
    np = _np()
    d = np.asarray(depth_in_draw_order, np.float64)
    if d.size < 2:
        return 0.0
    return float((np.diff(d) > 0).sum()) / (d.size - 1)


def angle_between_deg(a, b):
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na < 1e-12 or nb < 1e-12:
        return 180.0
    c = sum(x * y for x, y in zip(a, b)) / (na * nb)
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def need_sort(mode, frame, last_frame, every_n, fwd, last_fwd, pos, last_pos, move_deg, scene_radius, pulse=False,
              data_changed=False):
    """Gate for re-sorting. frozen: only data_changed/pulse. Otherwise: pulse, data change, every N frames (N > 0),
    view direction turned > move_deg, or camera moved > move_deg (as an angle seen from the scene radius)."""
    if pulse or data_changed or last_fwd is None:
        return True
    if mode in ('frozen', 'sortfree'):
        return False
    if every_n > 0 and frame - last_frame >= every_n:
        return True
    if angle_between_deg(fwd, last_fwd) > move_deg:
        return True
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(pos, last_pos)))
    ang = math.degrees(math.atan2(dist, max(scene_radius, 1e-6)))
    return ang > move_deg


# ---------------------------------------------------------------- motion / audio

def orbit_rate_deg_s(autorbit, sync, bpm, beats_per_rev, level=0.0):
    if sync == 'bpm':
        return 0.0 if beats_per_rev <= 0 or bpm <= 0 else 360.0 / (beats_per_rev * 60.0 / bpm)
    if sync == 'audio':
        return autorbit * max(0.0, level)
    return autorbit


def beat_env(t_s, bpm, decay=6.0):
    """BPM-locked kick envelope 1 -> 0 per beat."""
    if bpm <= 0:
        return 0.0
    ph = (t_s * bpm / 60.0) % 1.0
    return math.exp(-ph * decay)


def audio_mods(rows, values):
    """rows = [(chan, target, gain)], values = {chan: level}. Sum gain*level per target (unknown targets ignored)."""
    out = {t: 0.0 for t in AUDIOTARGETS}
    for chan, target, gain in rows:
        if target in out and chan in values:
            out[target] += float(gain) * float(values[chan])
    return out


def uniform_mods(scalemult, opacitygain, explode, noiseamp, beatpulse, beat, mods):
    """Final scale / opacity / explode / noise after beat + audio modulation."""
    return (scalemult * (1.0 + beatpulse * beat) * (1.0 + mods.get('scale', 0.0)),
            opacitygain * (1.0 + mods.get('opacity', 0.0)),
            explode + mods.get('explode', 0.0),
            noiseamp + mods.get('noise', 0.0))


# ---------------------------------------------------------------- reference raster (ground truth, small sizes)

def cpu_reference_raster(prep, view, fx, fy, w, h, order=None, scale=1.0, alpha_thr=0.015, lowpass=0.3,
                         base=None, depth=None, bias=0.0):
    """Premultiplied RGBA float image (h, w, 4), row 0 = bottom, same maths as the GLSL MAT
    (oriented 3-sigma quads, discard power > 0 or alpha < thr, alpha capped 0.99, 'over' back to front).
    Geo mode (W1-E, docs/builds/px_geo.md): base = the geometry render (premultiplied (h, w, 4)) the splats are drawn
    over, depth = its view depth per pixel (inf = empty); a splat fragment is rejected where depth < the splat
    centre's view depth - bias (depth test on, write off: the whole quad uses the centre depth, as the MAT)."""
    np = _np()
    img = np.zeros((h, w, 4), np.float64) if base is None else np.array(base, np.float64, copy=True)
    P, S, Q, C = prep['P'], prep['S'], prep['Q'], prep['C']
    if order is None:
        cam = np.linalg.inv(view)
        order = back_to_front(P, cam[:3, 3], -cam[:3, 2])
    ys, xs = np.mgrid[0:h, 0:w]
    px, py = xs + 0.5, ys + 0.5
    for i in order:
        a0 = float(C[i, 3])
        if a0 <= 0:
            continue
        pr = project_cov2d(P[i], cov3d(S[i] * scale, Q[i]), view, fx, fy, w, h, lowpass)
        if pr is None:
            continue
        mean, cov, _ = pr
        con = conic_from_cov(cov)
        if con is None:
            continue
        l1, l2, _ = eigen2(cov)
        k = quad_sigma_extent(min(a0, 0.99), alpha_thr)
        r = k * math.sqrt(l1)
        x0, x1 = int(max(0, math.floor(mean[0] - r))), int(min(w, math.ceil(mean[0] + r) + 1))
        y0, y1 = int(max(0, math.floor(mean[1] - r))), int(min(h, math.ceil(mean[1] + r) + 1))
        if x0 >= x1 or y0 >= y1:
            continue
        dx = px[y0:y1, x0:x1] - mean[0]
        dy = py[y0:y1, x0:x1] - mean[1]
        power = -0.5 * (con[0] * dx * dx + con[2] * dy * dy) - con[1] * dx * dy
        a = np.minimum(0.99, a0 * np.exp(power))
        a = np.where((power > 0) | (a < max(alpha_thr, 1.0 / 255.0)), 0.0, a)
        if depth is not None:
            zc = -float((np.asarray(view, np.float64) @ np.append(P[i], 1.0))[2]) - bias
            a = np.where(np.asarray(depth)[y0:y1, x0:x1] < zc, 0.0, a)
        src = np.concatenate([C[i, :3][None, None, :] * a[..., None], a[..., None]], 2)
        img[y0:y1, x0:x1] = src + img[y0:y1, x0:x1] * (1.0 - a[..., None])
    return img


def psnr(a, b, peak=1.0):
    np = _np()
    mse = float(np.mean((np.asarray(a, np.float64) - np.asarray(b, np.float64)) ** 2))
    return float('inf') if mse == 0 else 10.0 * math.log10(peak * peak / mse)


def status_line(fmt, prep, load_ms, err=None):
    if err:
        return 'ERROR: {}'.format(err)[:200]
    return '{} {:,} of {:,} splats, load {:.0f} ms, radius {:.2f}'.format(
        fmt, prep['count'], prep['file_count'], load_ms, prep['bounds']['radius'])


# ---------------------------------------------------------------- geometry in the splat scene (W1-E)
# docs/builds/px_geo.md. Geo page on BL_splat_render (and, in wave 2, PX_pointfx): user Geometry COMPs render first
# (geo_render: opaque, depth write, lit by Light COMPs), then the splats on top in a Render Pass TOP (geo_pass) with
# depth test on / write off. builders/glsl/splat_geo_adapter.glsl goes in front of the splat shader only while Geoon.

GEO_MARK_A = '// >>> geo adapter (splat_render_logic.geo_patch: regenerated while Geoon, do not edit inside)'
GEO_MARK_B = '// <<< geo adapter'
EFF_MARK_B = '// <<< effectors adapter'          # = effectors_logic.MARK_B (tested): the geo block goes after it
LIGHTMODES = [('halflambert', 'Half-lambert'), ('lambert', 'Lambert'), ('wrap', 'Wrap'),
              ('glow', 'No normal (glow by distance)')]
GEO_PARS = ('Geoon',)                     # par changes that re-patch the shader text (the rest are expressions)


def geo_strip(text):
    """Shader text without the geo block (exact inverse of geo_patch(on=True))."""
    a = text.find(GEO_MARK_A)
    if a < 0:
        return text
    b = text.find(GEO_MARK_B, a)
    if b < 0:
        return text
    e = text.find('\n', b)
    return text[:a] + (text[e + 1:] if e >= 0 else '')


def geo_patch(text, adapter, on):
    """Splat shader text with (on) or without (off) the geo adapter block. off = geo_strip (the text BL had before
    Geoon was ever set, byte for byte). on: the block goes right after the effectors block if there is one (it uses
    the W1-A light functions declared there), else at the top after any leading '#define' lines (as
    effectors_logic.with_prefix does, so either attach order gives the same text)."""
    t = geo_strip(text)
    if not on:
        return t
    lights = '#define SGEO_LIGHTS 1\n' if geo_has_lights(t) else ''
    block = GEO_MARK_A + '\n' + lights + adapter.rstrip('\n') + '\n' + GEO_MARK_B + '\n'
    b = t.find(EFF_MARK_B)
    if b >= 0:
        e = t.find('\n', b)
        e = len(t) if e < 0 else e + 1
        return t[:e] + block + t[e:]
    lines = t.split('\n')
    k = 0
    while k < len(lines) and lines[k].startswith('#define'):
        k += 1
    head = '\n'.join(lines[:k])
    return (head + '\n' if k else '') + block + '\n'.join(lines[k:])


def geo_has_lights(text):
    """True when the shader text already carries W1-A's light functions (the effectors block, header v2)."""
    return 'vec3 pxeLights(' in text and 'vec3 pxeSplatNormal(' in text


def geo_tokens(text):
    """Space-separated tokens of a par (names, paths, patterns, '#tag'); commas allowed."""
    return [x for x in str(text or '').replace(',', ' ').split() if x]


def geo_geometry(comps, splat_geo='draw'):
    """geo_render's `geometry` par value: the user's Geometry COMPs only (the splats are drawn by the pass).
    Empty = no geometry (the pass then draws the splats over a clear frame)."""
    return ' '.join(t for t in geo_tokens(comps) if t != splat_geo)


def resolve_lights(tokens, candidates):
    """Render TOP `lights` value. tokens: paths / patterns (passed through) or '#tag' (every candidate carrying the
    tag; '#light' = all candidates). candidates: [(path, tags)] of the Light COMPs found (e.g. in /project1/effectors).
    Order kept, no duplicates."""
    out = []
    for t in geo_tokens(tokens) if isinstance(tokens, str) else list(tokens):
        if t.startswith('#'):
            tag = t[1:]
            for path, tags in candidates:
                if tag in ('light', 'lights', '') or tag in tags:
                    out.append(path)
        else:
            out.append(t)
    seen = set()
    return ' '.join(x for x in out if not (x in seen or seen.add(x)))


def geo_uniform(relight, ambient, mode, bias):
    """uGeo (splat_geo_adapter.glsl): relight 0..1, ambient, light mode index (LIGHTMODES), depth bias."""
    return (float(relight), float(ambient), float(menu_index(LIGHTMODES, mode)), float(bias))


def geo_warning(on, sortmode):
    """Status text for setups the geo path does not support ('' = fine)."""
    if on and sortmode == 'sortfree':
        return 'Geo: sort-free adds splats (no order), so geometry is not occluded correctly; use a sorted mode'
    return ''


def env_render_now(frame, every_n):
    """Scene environment cube (MX env capture): render on this frame? every_n <= 1 = every frame."""
    n = int(every_n)
    return n <= 1 or int(frame) % n == 0


def splat_normal(q, s):
    """Numpy twin of W1-A's pxeSplatNormal: world axis of the smallest scale (unit, sign arbitrary). (4,)/(3,) or
    (n,4)/(n,3)."""
    np = _np()
    R = quat_to_mat3(q)
    s = np.asarray(s, np.float64)
    if R.ndim == 2:
        return R[:, int(np.argmin(s))]
    k = np.argmin(s, axis=1)
    return R[np.arange(len(k)), :, k]


def geo_relight_ref(rgb, p, q, s, cam_pos, lights, relight, ambient):
    """Numpy twin of splat_geo_adapter's sgeoLight: n = smallest-scale axis of (q, s) facing the eye (as W1-A's
    pxeSplatNormal), lights = [callable(p, n, v) -> rgb] (W1-A's pxeLight per light, e.g. effectors_logic.ref_light)."""
    np = _np()
    rgb, p = np.asarray(rgb, np.float64), np.asarray(p, np.float64)
    if relight <= 0.0:
        return rgb
    v = np.asarray(cam_pos, np.float64) - p
    v = v / max(float(np.linalg.norm(v)), 1e-12)
    n = splat_normal(q, s)
    if float(np.dot(n, v)) < 0.0:
        n = -n
    L = np.full(3, float(ambient))
    for f in lights:
        L = L + np.asarray(f(p, n, v), np.float64)
    return rgb + (rgb * L - rgb) * relight

