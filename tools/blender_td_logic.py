# blender_td_logic - pure maths for Blender -> TouchDesigner (26 Oct 2026). No bpy, no td imports: the Blender-side
# exporter (tools/blender_export.py) imports it; tests: test/test_blender_td.py. ASCII only.
#
# Conventions (sources: Blender 5.2 manual/API; TD side as probed live for LK_projection_room, see
# builders/projector_dome_logic.py header, TD 2025.31550):
# - Blender world: right-handed, Z up, front view looks along +Y. TD world: right-handed, Y up.
#   Point map (same as Blender's USD/FBX exporter with forward -Z, up Y): td = (x, z, -y).
# - Cameras and spot/sun/area lights in BOTH apps look down their local -Z with local +Y up, so their local frame
#   needs no change: M_td = C * M_blender. Meshes/empties get their local geometry converted by the exporter too:
#   M_td = C * M_blender * C^-1.
# - TD rotation order xyz: M = Rz * Ry * Rx (degrees). Blender Euler 'XYZ' is the same order.
# - TD Camera COMP winx / winy: window shift in fractions of the frame width / height (+ = window moves right / up).
#   Blender shift_x / shift_y are fractions of the sensor-fit dimension (AUTO = the larger one), same direction.
# - TD Light COMP projmapmode simplehorzfov: projangle = full horizontal FOV across the projection map width.
import math

C3 = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))   # blender -> td
C3_INV = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))

LIGHT_TYPES = {'POINT': 'point', 'SPOT': 'cone', 'SUN': 'distant', 'AREA': 'cone'}
# Heuristic watts -> TD dimmer (TD has no physical units): this much power = dimmer 1.0.
DIMMER_REF = {'POINT': 1000.0, 'SPOT': 1000.0, 'AREA': 1000.0, 'SUN': 5.0}
DIMMER_MAX = 10.0
SCHEMA = 'jazib-blender-td/1'


def _mat3_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def mat4(m):
    """Any 4x4 (nested sequences, e.g. a mathutils Matrix) -> tuple of 4 row tuples of floats."""
    rows = [tuple(float(v) for v in r) for r in m]
    if len(rows) != 4 or any(len(r) != 4 for r in rows):
        raise ValueError('need a 4x4 matrix')
    return tuple(rows)


def mat4_to_td(m, kind='object'):
    """Blender world matrix -> TD world matrix. kind 'camera' / 'light' keep their local frame (both look -Z, +Y up);
    'object' (mesh, empty) also converts the local axes."""
    m = mat4(m)
    r = tuple(row[:3] for row in m[:3])
    t = tuple(row[3] for row in m[:3])
    r2 = _mat3_mul(C3, r)
    if kind == 'object':
        r2 = _mat3_mul(r2, C3_INV)
    t2 = tuple(sum(C3[i][k] * t[k] for k in range(3)) for i in range(3))
    return tuple(tuple(r2[i]) + (t2[i],) for i in range(3)) + ((0.0, 0.0, 0.0, 1.0),)


def point_to_td(p):
    x, y, z = (float(v) for v in p)
    return (x, z, -y)


def decompose(m, unit=1.0):
    """TD-convention 4x4 -> {'t': metres, 'r': degrees (xyz order, M = Rz*Ry*Rx), 's': scale}. Shear is ignored;
    a negative determinant flips the x scale."""
    m = mat4(m)
    t = [m[i][3] * unit for i in range(3)]
    cols = [[m[i][j] for i in range(3)] for j in range(3)]
    s = [math.sqrt(sum(v * v for v in c)) for c in cols]
    det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
           + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    if det < 0:
        s[0] = -s[0]
    r = [[(m[i][j] / s[j]) if s[j] else 0.0 for j in range(3)] for i in range(3)]
    # R = Rz*Ry*Rx: r[2][0] = -sin(ry)
    sy = -max(-1.0, min(1.0, r[2][0]))
    ry = math.asin(sy)
    if abs(math.cos(ry)) > 1e-6:
        rx = math.atan2(r[2][1], r[2][2])
        rz = math.atan2(r[1][0], r[0][0])
    else:  # gimbal lock: put it all in rx
        rz = 0.0
        rx = math.atan2(-r[1][2], r[1][1])
    return {'t': [_r(v) for v in t], 'r': [_r(math.degrees(a)) for a in (rx, ry, rz)], 's': [_r(v) for v in s]}


def compose(t, r_deg, s=(1.0, 1.0, 1.0)):
    """Inverse of decompose (tests): TD xform 'srt' with rotation xyz."""
    rx, ry, rz = (math.radians(a) for a in r_deg)
    cx, sx, cy, sy, cz, sz = math.cos(rx), math.sin(rx), math.cos(ry), math.sin(ry), math.cos(rz), math.sin(rz)
    Rx = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    Ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    Rz = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))
    R = _mat3_mul(Rz, _mat3_mul(Ry, Rx))
    return tuple(tuple(R[i][j] * s[j] for j in range(3)) + (t[i],) for i in range(3)) + ((0.0, 0.0, 0.0, 1.0),)


def _r(v, n=6):
    v = round(float(v), n)
    return 0.0 if v == 0 else v


def aspect(resx, resy, pax=1.0, pay=1.0):
    return (float(resx) * float(pax)) / max(float(resy) * float(pay), 1e-9)


def camera_view(lens_mm, sensor_w, sensor_h, sensor_fit, resx, resy, pax=1.0, pay=1.0, shift_x=0.0, shift_y=0.0,
                ortho=False, ortho_scale=6.0, clip_start=0.1, clip_end=1000.0, unit=1.0):
    """Blender camera -> TD Camera COMP View values: hfov/vfov (deg), winx/winy, near/far (m), orthowidth (m)."""
    a = aspect(resx, resy, pax, pay)
    fit = str(sensor_fit or 'AUTO').upper()
    if fit == 'AUTO':
        horiz, sensor = a >= 1.0, float(sensor_w)
    elif fit == 'HORIZONTAL':
        horiz, sensor = True, float(sensor_w)
    elif fit == 'VERTICAL':
        horiz, sensor = False, float(sensor_h)
    else:
        raise ValueError('sensor_fit must be AUTO, HORIZONTAL or VERTICAL')
    out = {'aspect': _r(a), 'fit': 'horizontal' if horiz else 'vertical', 'near': _r(clip_start * unit),
           'far': _r(clip_end * unit), 'projection': 'ortho' if ortho else 'perspective'}
    if horiz:
        out['winx'], out['winy'] = _r(shift_x), _r(shift_y * a)
    else:
        out['winx'], out['winy'] = _r(shift_x / a), _r(shift_y)
    if ortho:
        out['orthowidth'] = _r((ortho_scale if horiz else ortho_scale * a) * unit)
        out['hfov'] = out['vfov'] = None
        return out
    half = math.atan(sensor / (2.0 * max(float(lens_mm), 1e-6)))
    if horiz:
        h, v = half, math.atan(math.tan(half) / a)
    else:
        v, h = half, math.atan(math.tan(half) * a)
    out['hfov'], out['vfov'] = _r(math.degrees(2 * h)), _r(math.degrees(2 * v))
    return out


def hfov_from_throw(T):
    return math.degrees(2.0 * math.atan(1.0 / (2.0 * max(float(T), 1e-3))))


def throw_from_hfov(deg):
    return 1.0 / (2.0 * math.tan(math.radians(max(min(float(deg), 179.0), 0.01)) / 2.0))


def light_values(btype, color, energy, spot_size_rad=None, spot_blend=0.0):
    """Blender light -> TD Light COMP values. Cone angle = Blender spot_size (full angle, deg); conedelta = the
    blend part of the half-angle (Blender softens inside the cone, TD fades outside it: approximation)."""
    bt = str(btype).upper()
    if bt not in LIGHT_TYPES:
        raise ValueError('unknown light type {}'.format(btype))
    out = {'kind': bt.lower(), 'lighttype': LIGHT_TYPES[bt], 'color': [_r(c, 4) for c in list(color)[:3]],
           'energy': _r(energy, 4), 'dimmer': _r(min(DIMMER_MAX, max(0.0, float(energy) / DIMMER_REF[bt])), 4)}
    if bt == 'SPOT':
        cone = math.degrees(float(spot_size_rad if spot_size_rad is not None else math.radians(45)))
        out['coneangle'] = _r(cone, 4)
        out['conedelta'] = _r(max(0.0, float(spot_blend)) * cone / 2.0, 4)
    elif bt == 'AREA':
        out['coneangle'], out['conedelta'] = 160.0, 10.0
    return out


def parse_res(v):
    """'1920x1080' / [1920, 1080] / None -> (w, h) or None."""
    if v is None or v == '':
        return None
    if isinstance(v, str):
        p = v.lower().replace(' ', '').split('x')
        if len(p) != 2:
            raise ValueError('resolution must look like 1920x1080')
        v = p
    w, h = int(float(v[0])), int(float(v[1]))
    if w < 8 or h < 8:
        raise ValueError('resolution too small')
    return (w, h)


def projector_values(props, cone_deg):
    """Custom props on a Blender light -> projector block, or None when the light is not a projector.
    props: projector (texture path, or true for a test pattern), projector_throw (D/W), projector_res ('WxH'),
    projector_shift ([h, v] fraction of the image)."""
    p = props.get('projector')
    if p in (None, '', 0, False):
        return None
    tex = p if isinstance(p, str) and p not in ('1', 'true', 'True') else ''
    throw = props.get('projector_throw')
    if throw not in (None, ''):
        T = float(throw)
        hf = hfov_from_throw(T)
    else:
        hf = float(cone_deg)
        T = throw_from_hfov(hf)
    sh = props.get('projector_shift') or (0.0, 0.0)
    sh = [float(x) for x in list(sh)[:2]] + [0.0] * (2 - len(list(sh)[:2]))
    return {'texture': tex, 'throw': _r(T, 5), 'hfov': _r(hf, 4), 'res': parse_res(props.get('projector_res')),
            'shift': [_r(sh[0]), _r(sh[1])]}


def unit_scale(scale_length, system='METRIC'):
    """Blender units -> metres. Internally 1 BU = scale_length m in every unit system."""
    s = 1.0 if scale_length is None else float(scale_length)
    if s <= 0:
        raise ValueError('scale_length must be > 0')
    return s
