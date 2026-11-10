# metavido_logic - reference decoder for Metavido video frames (27 Oct 2026, FX7c card 27, lane T). numpy only;
# used by the tests and live checks (outside TD, T-184). td/metavido.py does the same maths in GLSL. ASCII only.
#
# Format (clean-room from the spec in Keijiro Takahashi's Metavido repo, github.com/keijiro/Metavido, Unlicense;
# read 27 Oct 2026, no code copied): a 1920x1080 video frame packs four planes; image origin BOTTOM-left:
#   right half  x 960..1919, all rows    = colour (sRGB as stored in the video)
#   top-left    x 0..959,  y 540..1079   = depth, hue-encoded (see depth_from_rgb), metres
#   bottom-left x 0..959,  y 0..539      = human stencil in RED, metadata barcode in BLUE
# Barcode: 12 float32 values, value k in the 8-px column block k (x 8k..8k+7), bit i (LSB first) in the 8-px row
# block i (y 8i..8i+7) counted from the bottom; a bit is 1 when blue(8k+3, 8i+4) + blue(8k+5, 8i+4) > 0.4.
# Values: camera position xyz, rotation quaternion xyz (w = +sqrt(1 - x^2 - y^2 - z^2)), projection centre shift xy,
# vertical FOV (radians), depth range near / far (metres), a per-frame random hash. Coordinates are Unity's
# (left-handed, Y-up, camera looks +Z); TD (right-handed, camera looks -Z) = mirror Z: p -> (x, y, -z),
# q -> (-x, -y, z, w).
# Unprojection of depth texel uv (0..1 over the depth plane) with depth d: ray = ((uv - 0.5) * 2 + shift) *
# (tan(fov/2) * 16/9, tan(fov/2)); camera-local point = (ray.x * d, ray.y * d, d) (Unity) = (.., .., -d) (TD).
import math
import struct

W, H = 1920, 1080
HW, HH = W // 2, H // 2
NAMES = ('px', 'py', 'pz', 'rx', 'ry', 'rz', 'sx', 'sy', 'fov', 'near', 'far', 'hash')
HUE_MARGIN = 0.01
HUE_PADDING = 0.01


def decode_bits(frame):
    """frame: (1080, 1920, 3+) float 0..1, row 0 = BOTTOM. -> 12 uint32 words."""
    words = []
    for k in range(12):
        acc = 0
        for i in range(32):
            y = i * 8 + 4
            b = float(frame[y, k * 8 + 3, 2]) + float(frame[y, k * 8 + 5, 2])
            if b > 0.4:
                acc |= 1 << i
        words.append(acc)
    return words


def words_to_floats(words):
    return [struct.unpack('<f', struct.pack('<I', w & 0xffffffff))[0] for w in words]


def decode_meta(frame):
    v = dict(zip(NAMES, words_to_floats(decode_bits(frame))))
    q2 = v['rx'] ** 2 + v['ry'] ** 2 + v['rz'] ** 2
    v['rw'] = math.sqrt(1.0 - q2) if q2 < 1.0 else 0.0
    v['valid'] = bool(v['fov'] == v['fov'] and 0.0 < v['fov'] < math.pi and v['near'] < v['far'])
    return v


def hue_encode(depth, near, far):
    """Encoder side of the hue mapping (for synthetic tests): depth -> rgb."""
    d = (depth - near) / (far - near)
    d = d * (1 - HUE_PADDING * 2) + HUE_PADDING
    d = min(max(d, 0.0), 1.0) * (1 - HUE_MARGIN * 2) + HUE_MARGIN
    h = d * 6 - 2
    return tuple(min(max(c, 0.0), 1.0) for c in (abs(h - 1) - 1, 2 - abs(h), 2 - abs(h - 2)))


def rgb_to_hue(r, g, b):
    mn, mx = min(r, g, b), max(r, g, b)
    div = 1.0 / (6.0 * max(mx - mn, 1e-5))
    hr = (g - b) * div
    hg = 1.0 / 3 + (b - r) * div
    hb = 2.0 / 3 + (r - g) * div
    d = (hb if g < b else hg) if r < max(g, b) else hr
    x = d + 1 - HUE_PADDING / 2
    return (x - math.floor(x)) + HUE_PADDING / 2


def depth_from_rgb(rgb, near, far):
    d = rgb_to_hue(*rgb)
    d = (d - HUE_MARGIN) / (1 - HUE_MARGIN * 2)
    d = (d - HUE_PADDING) / (1 - HUE_PADDING * 2)
    return near + (far - near) * d


def depth_image(frame, near, far, margin=1):
    """(540, 960) depth in metres, row 0 = bottom (vectorised depth_from_rgb with the demux margin clamp)."""
    import numpy as np
    xs = np.minimum(np.arange(HW), HW - 1 - margin)
    ys = np.maximum(np.arange(HH) + HH, HH + margin)
    c = np.asarray(frame, dtype=np.float64)[ys][:, xs, :3]
    r, g, b = c[..., 0], c[..., 1], c[..., 2]
    mn, mx = c.min(axis=-1), c.max(axis=-1)
    div = 1.0 / (6.0 * np.maximum(mx - mn, 1e-5))
    hr, hg, hb = (g - b) * div, 1.0 / 3 + (b - r) * div, 2.0 / 3 + (r - g) * div
    d = np.where(r < np.maximum(g, b), np.where(g < b, hb, hg), hr)
    x = d + 1 - HUE_PADDING / 2
    d = (x - np.floor(x)) + HUE_PADDING / 2
    d = (d - HUE_MARGIN) / (1 - HUE_MARGIN * 2)
    d = (d - HUE_PADDING) / (1 - HUE_PADDING * 2)
    return near + (far - near) * d


def quat_to_td(m):
    """Unity quaternion (rx, ry, rz, rw) -> TD (x, y, z, w)."""
    return (-m['rx'], -m['ry'], m['rz'], m['rw'])


def pos_to_td(m):
    return (m['px'], m['py'], -m['pz'])


def quat_matrix(q):
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]


def euler_zxy_deg(R):
    """R = Ry(b) Rx(a) Rz(c) (TD rotate order zxy: z first, yaw outermost, so a walking camera never flips) ->
    (rx, ry, rz) = (a, b, c) degrees."""
    sa = -max(-1.0, min(1.0, R[1][2]))
    a = math.asin(sa)
    if abs(sa) < 0.999999:
        b = math.atan2(R[0][2], R[2][2])
        c = math.atan2(R[1][0], R[1][1])
    else:
        b = math.atan2(-R[2][0], R[0][0])
        c = 0.0
    return tuple(math.degrees(v) for v in (a, b, c))


def euler_matrix_zxy(a_deg, b_deg, c_deg):
    """Ry(b) Rx(a) Rz(c)."""
    a, b, c = (math.radians(v) for v in (a_deg, b_deg, c_deg))
    Rx = [[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]]
    Ry = [[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]]
    Rz = [[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]]
    mul = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]  # noqa: E731
    return mul(Ry, mul(Rx, Rz))


def pose_td(m):
    """TD camera pose: dict tx ty tz rx ry rz (deg, rotate order zxy), fov (vertical deg), hfov (deg), near, far,
    shiftx, shifty, valid, hash (the order of td/metavido.POSE_NAMES)."""
    t = pos_to_td(m)
    r = euler_zxy_deg(quat_matrix(quat_to_td(m)))
    h = math.tan(m['fov'] * 0.5)
    return {'tx': t[0], 'ty': t[1], 'tz': t[2], 'rx': r[0], 'ry': r[1], 'rz': r[2],
            'fov': math.degrees(m['fov']), 'hfov': math.degrees(2 * math.atan(h * 16.0 / 9.0)),
            'near': m['near'], 'far': m['far'], 'shiftx': m['sx'], 'shifty': m['sy'],
            'valid': 1.0 if m['valid'] else 0.0, 'hash': m['hash']}


def unproject(m, u, v, d):
    """Depth texel uv + depth (m) -> TD world point."""
    h = math.tan(m['fov'] * 0.5)
    rx = ((u - 0.5) * 2 + m['sx']) * h * 16.0 / 9.0
    ry = ((v - 0.5) * 2 + m['sy']) * h
    local = (rx * d, ry * d, -d)
    R = quat_matrix(quat_to_td(m))
    t = pos_to_td(m)
    return tuple(sum(R[i][j] * local[j] for j in range(3)) + t[i] for i in range(3))


def read_frame_ffmpeg(path, index, ffmpeg='ffmpeg'):
    """Frame `index` of a video as (1080, 1920, 3) float 0..1, row 0 = BOTTOM (TD texel order)."""
    import subprocess
    import numpy as np
    out = subprocess.run([ffmpeg, '-v', 'error', '-i', path, '-vf', 'select=eq(n\\,{})'.format(int(index)),
                          '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True, timeout=120).stdout
    a = np.frombuffer(out, dtype=np.uint8)
    if a.size != W * H * 3:
        raise ValueError('expected a 1920x1080 frame, got {} bytes'.format(a.size))
    return a.reshape(H, W, 3)[::-1].astype(np.float64) / 255.0
