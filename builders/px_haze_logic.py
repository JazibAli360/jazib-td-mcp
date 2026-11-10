# px_haze_logic: pure logic for the W1-D haze pass (glsl/px_haze.glsl + px_haze_comp.glsl) and the two-scale bloom
# (glsl/px_bloom.glsl). No td import: usable from PX (wave 2), the standalone builder (px_haze.py, copied into a Text
# DAT) and the offline tests. Uniform row packing, camera basis, light rows, colour source, numpy reference maths that
# mirror the shaders line by line, closed forms for the checks, and a cost model. Doc: docs/builds/px_haze.md.
# Maths sources: equiangular sampling for point lights in media (Kulla & Fajardo, "Importance Sampling Techniques for
# Path Tracing in Participating Media", EGSR 2012); exponential height fog optical depth (closed form, as in UE /
# Quilez "better fog"); screen-space light shafts (Mitchell, GPU Gems 3 ch. 13); Henyey-Greenstein phase.
# ASCII only.
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

HZ_ROWS = 13           # uH rows (haze_rows)
HZ_LMAX = 8            # lights per pass (uHL = 4 rows each)
HZ_LROWS = 5           # rows per light in uHL (uHL[40])
HZ_STEPS_MAX = 32      # in-scatter samples per light (shader loop bound)
HZ_TAPS_MAX = 64       # shaft taps per light (shader loop bound)
LIGHT_TYPES = ('point', 'spot', 'area', 'directional')
DEPTH_MODES = ('none', 'viewz', 'ndc', 'raydist')
BR_ROWS = ('uB', 'uB2', 'uBt', 'uBr')

# ---------------------------------------------------------------------------------------------- tiny vector helpers


def _v(a):
    return [float(a[0]), float(a[1]), float(a[2])]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _norm(a, fb=(0.0, 0.0, -1.0)):
    n = math.sqrt(_dot(a, a))
    return [a[0] / n, a[1] / n, a[2] / n] if n > 1e-12 else list(fb)


def _cl(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


# --------------------------------------------------------------------------------------------------------- camera


def camera_basis(eye, target, up=(0.0, 1.0, 0.0)):
    """(right, up, fwd) unit vectors of a look-at camera (right-handed, TD/OpenGL: camera looks down -z)."""
    f = _norm(_sub(_v(target), _v(eye)))
    r = _norm(_cross(f, _v(up)), (1.0, 0.0, 0.0))
    u = _cross(r, f)
    return r, u, f


def camera(eye, right, up, fwd, fov_y_deg, aspect, near=0.01, far=1000.0):
    """Camera dict used by haze_rows. fov_y_deg = VERTICAL field of view; aspect = width / height."""
    return {'pos': _v(eye), 'right': _norm(right), 'up': _norm(up), 'fwd': _norm(fwd),
            'tany': math.tan(math.radians(_cl(float(fov_y_deg), 1e-3, 179.0)) * 0.5), 'aspect': float(aspect),
            'near': float(near), 'far': float(far)}


def camera_lookat(eye, target, fov_y_deg, aspect, up=(0.0, 1.0, 0.0), near=0.01, far=1000.0):
    r, u, f = camera_basis(eye, target, up)
    return camera(eye, r, u, f, fov_y_deg, aspect, near, far)


def camera_from_world(world, fov_deg, aspect, fov_axis='x', near=0.01, far=1000.0):
    """A TD Camera COMP: world = its 4x4 worldTransform as rows (list of 4 lists, column 3 = translation), fov_deg its
    `fov` par (TD's default fovaxis is horizontal: fov_axis 'x'; LIVE CHECK on 31550). Columns 0/1/2 = right/up/back."""
    m = [list(map(float, r)) for r in world]
    right = [m[0][0], m[1][0], m[2][0]]
    upv = [m[0][1], m[1][1], m[2][1]]
    back = [m[0][2], m[1][2], m[2][2]]
    pos = [m[0][3], m[1][3], m[2][3]]
    fy = float(fov_deg)
    if fov_axis == 'x':
        fy = math.degrees(2.0 * math.atan(math.tan(math.radians(fy) * 0.5) / max(float(aspect), 1e-6)))
    return camera(pos, right, upv, [-back[0], -back[1], -back[2]], fy, aspect, near, far)


def camera_from_px(cam_row, fov_h_deg, resx, resy, near=0.01, far=1000.0):
    """PX_pointfx's own camera (px_logic.cam_viewproj: orbit numbers tx ty tz ry deg + horizontal FOV)."""
    tx, ty, tz, ry = [float(v) for v in cam_row[:4]]
    a = math.radians(ry)
    ca, sa = math.cos(a), math.sin(a)
    # view rotation rows of px_logic: [[ca,0,-sa],[0,1,0],[sa,0,ca]] -> camera axes in world = its columns
    right = [ca, 0.0, -sa]
    back = [sa, 0.0, ca]
    aspect = float(resx) / max(float(resy), 1.0)
    fy = math.degrees(2.0 * math.atan(math.tan(math.radians(max(float(fov_h_deg), 1e-3)) * 0.5) / aspect))
    return camera([tx, ty, tz], right, [0.0, 1.0, 0.0], [-back[0], -back[1], -back[2]], fy, aspect, near, far)


def project(cam, p, directional=False):
    """World point (or a direction toward a far source when directional) -> (u, v, z) screen uv 0..1 + view depth;
    None when behind the camera. Same maths as pxhScreen in px_haze.glsl."""
    v = [-p[0], -p[1], -p[2]] if directional else _sub(_v(p), cam['pos'])
    z = _dot(v, cam['fwd'])
    if z <= (1e-6 if directional else cam['near']):
        return None
    sx = _dot(v, cam['right']) / (z * cam['tany'] * cam['aspect'])
    sy = _dot(v, cam['up']) / (z * cam['tany'])
    return 0.5 + 0.5 * sx, 0.5 + 0.5 * sy, z


# ------------------------------------------------------------------------------------------------- colour source


def _pal():
    """builders/palette_map_logic (W1-B shared palette). Imported lazily: inside TD the standalone builder copies it
    into a Text DAT next to this module."""
    import palette_map_logic
    return palette_map_logic


PAL_IDENTITY_ROWS = [[1.0, 1.0, 1.0, 0.0]] * 16
PAL_IDENTITY_CTL = [0.0, 0.0, 0.0, 0.0]     # count 0: palette modes give black; solid / source never read it


def colsrc(cs, solid, src, attr_t, pal_rows=None, pal_ctl=None):
    """W1-B colour source on the CPU (= pxColSrc): cs = palette_map_logic.colsrc_vec(...) (mode, pos, spread, keep)."""
    return list(_pal().colsrc_eval(cs, solid, src, attr_t, pal_rows or PAL_IDENTITY_ROWS, pal_ctl or PAL_IDENTITY_CTL))


def shader_text(name):
    """GLSL text for a TOP: px_palette.glsl (W1-B include, uPal[16] + uPalCtl) prepended to px_haze.glsl /
    px_bloom.glsl (both call pxColSrc); px_haze_comp.glsl needs no palette."""
    g = os.path.join(HERE, 'glsl')
    with open(os.path.join(g, name)) as fh:
        body = fh.read()
    if name in ('px_haze.glsl', 'px_bloom.glsl'):
        with open(os.path.join(g, 'px_palette.glsl')) as fh:
            return fh.read() + '\n' + body
    return body


# ----------------------------------------------------------------------------------------------------- haze rows

HAZE_DEFAULTS = {
    'colour': (0.55, 0.6, 0.7),   # Hazecol: ambient haze colour (and every light's fog colour in cs mode solid)
    'cs': (3.0, 0.0, 1.0, 0.0),   # uHazeCs (W1-B colsrc_vec): default mode 3 source = each light's own colour
    'density': 0.08,              # scattering coefficient per world unit at / below the floor
    'floor': 0.0,                 # height where the falloff starts (world y)
    'falloff': 0.35,              # 1 / units above the floor (0 = homogeneous)
    'noise': 0.5,                 # 0..1 patchiness (fbm drift)
    'noisescale': 0.35,           # noise frequency (1 / units)
    'wind': (0.3, 0.05, 0.1),     # noise drift (units / s)
    'extinction': 1.0,            # 0 = light-only (no dimming of the scene), 1 = physical
    'tint': (1.0, 1.0, 1.0),      # lit-fog tint (x the cs colour of each light)
    'gain': 1.0,                  # in-scatter gain
    'g': 0.35,                    # Henyey-Greenstein anisotropy (-0.9..0.9; > 0 = glow toward the light)
    'ambient': 0.25,              # ambient haze amount (0 = only lights make haze visible)
    'steps': 8,                   # in-scatter samples per light (1..32); default case 0.9 % vs exact
    'shafts': 0.6,                # shaft amount (0 = off, no taps)
    'decay': 0.96,                # per-tap decay
    'length': 0.85,               # fraction of the way to the light covered by the taps
    'taps': 12,                   # shaft taps per light (1..64); dithered start, so few taps read as grain, not bands
    'threshold': 0.0,             # > 0: pixels brighter than this also emit shafts
    'disc': 0.06,                 # light source disc radius (fraction of screen height)
    'occlusion': 1.0,             # how strongly scene alpha blocks the shafts
    'depthmode': 'none',          # none / viewz / ndc / raydist
    'depthscale': 1.0,
    'objdist': 6.0,               # no depth input: distance assumed for covered pixels (alpha 1)
    'maxdist': 60.0,              # march end for empty pixels (sky)
    'softradius': 0.05,           # light size: intensity / (d^2 + r^2), keeps a ray through the light finite
    'jitter': 0.0,                # 1 = per-pixel / per-frame sample offset (needs a temporal blur after)
    'shaftlod': 1.0,              # mip level the shaft taps read (0 = full haze res; 1 = half of it: cache-friendly)
    'noisemode': 'light',         # 'light' = one fbm per light (cheap), 'sample' = per in-scatter sample
    'depthalpha': False,          # with a depth input: covered pixels (scene alpha) also end the march at objdist
}


def haze_params(raw=None):
    p = dict(HAZE_DEFAULTS)
    p.update(raw or {})
    return p


def haze_cs(params):
    return [float(x) for x in haze_params(params)['cs']]


def haze_rows(params, cam, nlights=0):
    """-> HZ_ROWS x 4 floats for `uniform vec4 uH[13]` (see the table in px_haze.glsl). The colour source vec4
    `uHazeCs` = haze_cs(params)."""
    p = haze_params(params)
    dm = p['depthmode']
    dmi = DEPTH_MODES.index(dm) if isinstance(dm, str) else int(dm)
    rows = [
        cam['pos'] + [cam['tany'] * cam['aspect']],           # tan(fovx/2); the shader divides by its own aspect
        cam['right'] + [cam['aspect']],
        cam['up'] + [cam['near']],
        cam['fwd'] + [cam['far']],
        _v(p['colour']) + [max(float(p['density']), 0.0)],
        [float(p['floor']), max(float(p['falloff']), 0.0), _cl(float(p['noise']), 0.0, 1.0), float(p['noisescale'])],
        _v(p['wind']) + [_cl(float(p['extinction']), 0.0, 1.0)],
        _v(p['tint']) + [float(p['gain'])],
        [_cl(float(p['g']), -0.95, 0.95), max(float(p['ambient']), 0.0), float(_cl(int(p['steps']), 1, HZ_STEPS_MAX)),
         max(float(p['softradius']), 1e-4)],
        [max(float(p['shafts']), 0.0), _cl(float(p['decay']), 0.0, 1.0), _cl(float(p['length']), 0.0, 1.0),
         float(_cl(int(p['taps']), 1, HZ_TAPS_MAX))],
        [float(p['threshold']), max(float(p['disc']), 1e-4), _cl(float(p['occlusion']), 0.0, 1.0),
         float(_cl(int(nlights), 0, HZ_LMAX))],
        [float(dmi), float(p['depthscale']), max(float(p['objdist']), 0.0), max(float(p['maxdist']), 1e-3)],
        [1.0 if p['noisemode'] == 'sample' else 0.0, 1.0 if float(p['jitter']) > 0 else 0.0,
         max(float(p['shaftlod']), 0.0), 1.0 if p.get('depthalpha') else 0.0],
    ]
    assert len(rows) == HZ_ROWS
    return [[float(x) for x in r] for r in rows]


# ---------------------------------------------------------------------------------------------------- light rows

LIGHT_DEFAULTS = {'type': 'point', 'pos': (0.0, 2.0, 0.0), 'dir': (0.0, -1.0, 0.0), 'colour': (1.0, 1.0, 1.0),
                  'intensity': 1.0, 'range': 0.0, 'cone': 40.0, 'delta': 10.0, 'size': (1.0, 1.0), 'shaft': 1.0,
                  'enabled': True}


def light_rows(lights):
    """lights: [{type point|spot|area|directional, pos, dir (spot axis / area normal / directional travel dir),
    colour, intensity, range (0 = unbounded), cone deg (full angle, TD Light COMP coneangle: full beam inside cone/2),
    delta deg (TD conedelta: fades to 0 at cone/2 + delta), or exact cosin / cosout, size (w, h) area, uaxis (area
    U axis; else derived from the normal), shaft weight, enabled}] -> (HZ_LMAX * HZ_LROWS rows, count).
    Disabled lights are skipped; more than HZ_LMAX are dropped (brightest first kept)."""
    ls = []
    for raw in lights or []:
        l = dict(LIGHT_DEFAULTS)
        l.update(raw)
        if not l.get('enabled', True) or float(l['intensity']) == 0.0:
            continue
        ls.append(l)
    ls.sort(key=lambda l: -abs(float(l['intensity'])) * max(l['colour'][:3]))
    ls = ls[:HZ_LMAX]
    rows = []
    for l in ls:
        t = l['type']
        ti = LIGHT_TYPES.index(t) if isinstance(t, str) else int(t)
        half = math.radians(_cl(float(l['cone']), 0.1, 179.0)) * 0.5
        dl = math.radians(max(float(l['delta']), 0.0))
        cos_in = float(l['cosin']) if l.get('cosin') is not None else math.cos(half)      # TD / W1-A convention:
        cos_out = (float(l['cosout']) if l.get('cosout') is not None                      # full beam inside cone/2,
                   else math.cos(min(half + dl, math.pi * 0.999)))                        # fades out by + delta
        if cos_in < cos_out + 1e-4:                  # smoothstep needs edge0 < edge1 (undefined in GLSL otherwise)
            cos_in = min(cos_out + 1e-4, 1.0)
            cos_out = cos_in - 1e-4
        sz = l['size']
        rows += [_v(l['pos']) + [float(ti)],
                 _norm(_v(l['dir']), (0.0, -1.0, 0.0)) + [max(float(l['range']), 0.0)],
                 _v(l['colour']) + [max(float(l['shaft']), 0.0)],
                 [cos_out, cos_in, max(float(sz[0]), 0.0) * 0.5, max(float(sz[1]), 0.0) * 0.5],
                 [float(l['intensity'])] + (_norm(_v(l['uaxis'])) if l.get('uaxis') else [0.0, 0.0, 0.0])]
    n = len(ls)
    rows += [[0.0] * 4] * ((HZ_LMAX - n) * HZ_LROWS)
    return rows, n


# Lights from /project1/effectors (lane W1-A, docs/builds/effectors.md "Lights"): the packed buffer's light region =
# header (K, stride LW = 7) + one 7-texel block per ENABLED light:
#   0 colour rgb (palette applied), intensity | 1 position xyz, type | 2 forward xyz, row index
#   3 attenuation start, end, exponent, on | 4 cos(cone/2), cos(cone/2 + delta), roll, 0 | 5 half-U xyz | 6 half-V xyz
# The haze takes these as uniforms (uHL) through this adapter (Python, from the same numpy block the buffer is packed
# from), so the haze shader needs no buffer input. Range = attenuation end when on (haze keeps physical 1/d^2 inside
# it with a smooth window; W1-A's start / exponent shape surface lighting only).


def lights_from_block(blocks):
    """W1-A light blocks (each 7 texels of 4 floats) -> light dicts for light_rows (exact cone cosines and area axes)."""
    out = []
    for b in blocks or []:
        t = [list(map(float, x)) for x in b]
        hu, hv = t[5][:3], t[6][:3]
        lu = math.sqrt(_dot(hu, hu))
        lv = math.sqrt(_dot(hv, hv))
        out.append({'type': int(round(t[1][3])), 'pos': t[1][:3], 'dir': t[2][:3], 'colour': t[0][:3],
                    'intensity': t[0][3], 'range': t[3][1] if t[3][3] > 0.5 else 0.0,
                    'cosin': t[4][0], 'cosout': t[4][1], 'size': (2.0 * lu, 2.0 * lv),
                    'uaxis': [x / lu for x in hu] if lu > 1e-9 else None, 'shaft': 1.0})
    return out


# ----------------------------------------------------------------------------------------------------- bloom rows

BLOOM_DEFAULTS = {'threshold': 0.8, 'intensity': 1.0, 'spacing': 1.5, 'knee': 0.0, 'wide': 1.0, 'tight': 0.0,
                  'tightspacing': 1.0, 'clamp': 0.0, 'tint': (1.0, 1.0, 1.0), 'saturation': 1.0, 'ring': 0.0,
                  'ringradius': 0.12, 'ringwidth': 0.5, 'ringchroma': 0.0, 'cs': (0.0, 0.0, 1.0, 0.0)}


def bloom_rows(raw=None):
    """-> {'uB','uB2','uBt','uBr','uGlowCs'} vec4s for px_bloom.glsl. Defaults = the old px_glow (one 1/8 scale,
    white). Tint = pxColSrc(uGlowCs, uBt.rgb, vec3(1), 0): cs mode solid (default) = Bloomtint."""
    p = dict(BLOOM_DEFAULTS)
    p.update(raw or {})
    return {'uB': [float(p['threshold']), float(p['intensity']), float(p['spacing']), max(float(p['knee']), 0.0)],
            'uB2': [max(float(p['wide']), 0.0), max(float(p['tight']), 0.0), float(p['tightspacing']),
                    max(float(p['clamp']), 0.0)],
            'uBt': _v(p['tint']) + [max(float(p['saturation']), 0.0)],
            'uBr': [max(float(p['ring']), 0.0), max(float(p['ringradius']), 1e-4), _cl(float(p['ringwidth']), 0.0, 1.0),
                    _cl(float(p['ringchroma']), 0.0, 0.5)],
            'uGlowCs': [float(x) for x in p['cs']]}


def bloom_is_legacy(rows):
    return (rows['uB'][3] == 0.0 and rows['uB2'][:2] == [1.0, 0.0] and rows['uB2'][3] == 0.0
            and rows['uBt'] == [1.0, 1.0, 1.0, 1.0] and rows['uBr'][0] == 0.0
            and int(rows.get('uGlowCs', [0.0])[0] + 0.5) == 0 and rows.get('uGlowCs', [0, 0, 0, 0.0])[3] == 0.0)


# ----------------------------------------------------------------------------------------------------- cost model


def haze_cost_ms(w=270, h=480, lights=4, steps=8, taps=12, shafts=True, noise_per_sample=False, comp_full=(1080, 1920)):
    """GPU estimate fitted to the LIVE b5 numbers (31550, 27 Oct, 3 TDs building on the same GPU): 4 lights, 8
    steps, 12 taps: quarter res (270 x 480) 0.56 ms, half (540 x 960) 2.2-3.2 ms; no lights 0.17 ms. An in-scatter
    sample ~3 tap-equivalents, an fbm ~4, a shaft tap ~1.2. Returns {'haze', 'composite', 'total'}."""
    mpx = w * h / 1e6
    k = 0.022
    eq = lights * steps * (3.0 + (4.0 if noise_per_sample else 0.0)) + lights * 4.0 + 6.0
    if shafts:
        eq += lights * taps * 1.2
    haze = 0.15 + k * mpx * eq
    comp = 0.15 + 0.0045 * (comp_full[0] * comp_full[1] / 1e6) * 2.0
    return {'haze': round(haze, 3), 'composite': round(comp, 3), 'total': round(haze + comp, 3)}


def bloom_cost_ms(resx=1080, resy=1920, tight=True, ring=False, ring_taps=16):
    """old glow: 49 taps at 1/8 (~0.4-0.6 ms live, mostly the fixed op cost). Two-scale adds 49 taps at 1/4 res and
    the wide taps move to 1/4 res output; ring adds 3 x ring_taps."""
    k = 0.0045
    q = (resx / 4.0) * (resy / 4.0) / 1e6
    e = (resx / 8.0) * (resy / 8.0) / 1e6
    old = 0.2 + k * e * 49
    out = q if tight else e
    new = 0.2 + k * out * (49 + (49 if tight else 0) + (3 * ring_taps if ring else 0))
    return {'old': round(old, 3), 'new': round(new, 3), 'delta': round(new - old, 3)}


# ========================================================================================== numpy reference maths
# Mirrors of the shaders (float64). Used by the tests; the live checks compare the GPU against these.


def _np():
    import numpy as np
    return np


def hg(cos_t, g):
    """Henyey-Greenstein normalised so an isotropic medium (g = 0) gives 1 (= 4 pi x the usual pdf)."""
    np = _np()
    q = np.maximum(1.0 + g * g - 2.0 * g * cos_t, 1e-6)
    return (1.0 - g * g) / (q * np.sqrt(q))


def _fy(y, y0, H):
    """antiderivative of exp(-H max(y - y0, 0)) dy (0 at the floor)."""
    np = _np()
    u = y - y0
    if H <= 1e-6:
        return u
    return np.where(u <= 0.0, u, (1.0 - np.exp(-H * np.maximum(u, 0.0))) / H)


def opt_depth(oy, dy, t, D, y0, H):
    """Optical depth (no noise) from the ray origin height oy, direction y component dy, over distance t."""
    np = _np()
    oy, dy, t = np.broadcast_arrays(np.asarray(oy, float), np.asarray(dy, float), np.asarray(t, float))
    small = np.abs(dy) < 1e-4
    dys = np.where(small, 1.0, dy)
    tau = D * (_fy(oy + dy * t, y0, H) - _fy(oy, y0, H)) / dys
    ym = oy + dy * t * 0.5
    tau_s = D * t * (np.exp(-H * np.maximum(ym - y0, 0.0)) if H > 1e-6 else 1.0)
    return np.where(small, tau_s, tau)


def sigma(y, D, y0, H):
    np = _np()
    return D * (np.exp(-H * np.maximum(y - y0, 0.0)) if H > 1e-6 else np.ones_like(np.asarray(y, float)))


def _fract(x):
    np = _np()
    return x - np.floor(x)


def vnoise_hash(p):
    """iq's 3D hash (same as pxhHash): p (..., 3) -> (...)."""
    np = _np()
    q = _fract(p * 0.3183099 + 0.1) * 17.0
    return _fract(q[..., 0] * q[..., 1] * q[..., 2] * (q[..., 0] + q[..., 1] + q[..., 2]))


def vnoise(x):
    np = _np()
    i = np.floor(x)
    f = x - i
    f = f * f * (3.0 - 2.0 * f)

    def hh(a, b, c):
        return vnoise_hash(i + np.array([a, b, c], float))
    x00 = hh(0, 0, 0) + (hh(1, 0, 0) - hh(0, 0, 0)) * f[..., 0]
    x10 = hh(0, 1, 0) + (hh(1, 1, 0) - hh(0, 1, 0)) * f[..., 0]
    x01 = hh(0, 0, 1) + (hh(1, 0, 1) - hh(0, 0, 1)) * f[..., 0]
    x11 = hh(0, 1, 1) + (hh(1, 1, 1) - hh(0, 1, 1)) * f[..., 0]
    y0 = x00 + (x10 - x00) * f[..., 1]
    y1 = x01 + (x11 - x01) * f[..., 1]
    return y0 + (y1 - y0) * f[..., 2]


def fbm(p):
    return (0.5 * vnoise(p) + 0.25 * vnoise(p * 2.03 + 17.1) + 0.125 * vnoise(p * 4.01 + 31.7)) / 0.875


def noise_factor(p, U, time=0.0):
    """max(1 + N (2 fbm - 1), 0) at world points p (..., 3); 1 when noise is 0."""
    np = _np()
    N, sc = U[5][2], U[5][3]
    if N <= 0.0:
        return np.ones(p.shape[:-1])
    w = np.array(U[6][:3], float)
    return np.maximum(1.0 + N * (2.0 * fbm((p - w * time) * sc) - 1.0), 0.0)


def dir_at(U, uv, asp=None):
    """Unit view ray through screen uv (..., 2) (mirrors pxhDir)."""
    np = _np()
    asp = asp or U[1][3]
    tanx = U[0][3]
    tany = tanx / asp
    r, u, f = (np.array(U[k][:3], float) for k in (1, 2, 3))
    X = uv[..., 0] * 2.0 - 1.0
    Y = uv[..., 1] * 2.0 - 1.0
    d = f + r * (X * tanx)[..., None] + u * (Y * tany)[..., None]
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def ray_dirs(U, w, h):
    """Unit view rays of the haze output pixels (TD uv: (0, 0) bottom-left), (h, w, 3); aspect = w / h (the shader
    uses its own output aspect)."""
    np = _np()
    x = (np.arange(w) + 0.5) / w
    y = (np.arange(h) + 0.5) / h
    X, Y = np.meshgrid(x, y)
    return dir_at(U, np.stack([X, Y], -1), w / float(h))


def ray_end(U, d, alpha, depth=None):
    """March end distance per ray (mirrors pxhEnd)."""
    np = _np()
    dm, ds, objd, maxd = int(U[11][0]), U[11][1], U[11][2], U[11][3]
    near, far = U[2][3], U[3][3]
    f = np.array(U[3][:3], float)
    cosf = np.maximum(d @ f, 1e-4)
    if dm == 0 or depth is None:
        te = maxd + (objd - maxd) * np.clip(alpha, 0.0, 1.0)
    else:
        r = depth * (1.0 if dm == 2 else ds)
        if dm == 1:
            te = r / cosf
            sky = (depth <= 0.0) | (r >= far * 0.999)
        elif dm == 2:
            zn = depth * 2.0 - 1.0
            z = 2.0 * near * far / np.maximum(far + near - zn * (far - near), 1e-6)
            te = z / cosf
            sky = depth >= 0.99999
        else:
            te = r
            sky = (depth <= 0.0) | (r >= far * 0.999)
        te = np.where(sky, maxd, te)
        if len(U) > 12 and U[12][3] > 0.5:          # depth + alpha (PX wave 3: depth from the geometry only)
            te = np.minimum(te, maxd + (objd - maxd) * np.clip(alpha, 0.0, 1.0))
    return np.minimum(te, maxd)


def _area_frame(n, ua=None):
    np = _np()
    if ua is not None and np.linalg.norm(ua) > 0.5:
        u = np.asarray(ua, float)
        return u, np.cross(n, u)
    a = np.array([0.0, 1.0, 0.0]) if abs(n[1]) < 0.99 else np.array([1.0, 0.0, 0.0])
    u = np.cross(a, n)
    u = u / np.linalg.norm(u)
    return u, np.cross(n, u)


def light_cols(U, L, nl, cs=None, pal_rows=None, pal_ctl=None):
    """Fog colour x intensity of each light (mirrors pxhLightCol): pxColSrc(uHazeCs, Hazecol, light colour, k)."""
    cs = list(cs) if cs is not None else [3.0, 0.0, 1.0, 0.0]
    out = []
    for i in range(nl):
        c = colsrc(cs, U[4][:3], L[i * HZ_LROWS + 2][:3], float(i), pal_rows, pal_ctl)
        out.append([x * L[i * HZ_LROWS + 4][0] for x in c])
    return out


def inscatter(o, d, te, U, L, nl, time=0.0, jit=None, cols=None):
    """Lit-fog radiance along rays o + d t, t in [0, te] (mirrors pxhLight + pxhInscatter): o (3,), d (N, 3),
    te (N,) -> (N, 3) (before tint / gain), plus S = integral of sigma T dt (N,) and T(te) (N,)."""
    np = _np()
    o = np.asarray(o, float)
    D, y0, H = U[4][3], U[5][0], U[5][1]
    ext, g, steps, r0 = U[6][3], U[8][0], int(U[8][2]), U[8][3]
    per_sample = U[12][0] > 0.5
    N = d.shape[0]
    tm = te * 0.5
    nmid = noise_factor(o + d * tm[:, None], U, time)
    tauE = opt_depth(o[1], d[:, 1], te, D, y0, H) * nmid
    TE = np.exp(-ext * tauE)
    S = np.where(ext > 1e-4, (1.0 - TE) / max(ext, 1e-4), tauE)
    out = np.zeros((N, 3))
    j = np.full(N, 0.5) if jit is None else jit
    for i in range(nl):
        L0, L1, L2, L3 = (np.array(L[i * HZ_LROWS + k], float) for k in range(4))
        typ = int(L0[3])
        col = np.array(cols[i] if cols is not None else L2[:3] * L[i * HZ_LROWS + 4][0], float)
        if typ == 3:
            ax = L1[:3]
            out += col * (hg(-(d @ ax), g) * S)[:, None]
            continue
        P = L0[:3]
        rel = P - o
        dl = d @ rel
        perp = rel[None, :] - d * dl[:, None]
        h0 = np.linalg.norm(perp, axis=-1)
        hs = np.sqrt(h0 * h0 + r0 * r0)
        rng = L1[3]
        ta = np.zeros(N)
        tb = te.copy()
        ok = np.ones(N, bool)
        if rng > 0.0:
            half = np.sqrt(np.maximum(rng * rng - h0 * h0, 0.0))
            ok &= h0 < rng
            ta = np.maximum(ta, dl - half)
            tb = np.minimum(tb, dl + half)
        ok &= tb > ta
        tha = np.arctan((ta - dl) / hs)
        thb = np.arctan((tb - dl) / hs)
        if not per_sample:
            pc = o + d * np.clip(dl, ta, tb)[:, None]
            nl_f = noise_factor(pc, U, time)
        acc = np.zeros(N)
        for k in range(steps):
            uk = (k + j) / steps                 # smoothstep warp: dense samples at both ends where T moves fast
            wk = 6.0 * uk * (1.0 - uk)
            th = tha + (thb - tha) * (uk * uk * (3.0 - 2.0 * uk))
            t = dl + hs * np.tan(th)
            p = o + d * t[:, None]
            nf = noise_factor(p, U, time) if per_sample else nl_f
            T = np.exp(-ext * opt_depth(o[1], d[:, 1], t, D, y0, H) * nmid)
            sg = sigma(p[:, 1], D, y0, H) * nf
            lv = p - P
            if typ == 2:                     # area: nearest point on the rect, one-sided (normal = axis)
                n = L1[:3]
                u, v = _area_frame(n, np.array(L[i * HZ_LROWS + 4][1:4], float))
                q = (P + u * np.clip(lv @ u, -L3[2], L3[2])[:, None] + v * np.clip(lv @ v, -L3[3], L3[3])[:, None])
                lq = p - q
                dq2 = np.sum(lq * lq, -1) + r0 * r0
                wi = lq / np.maximum(np.linalg.norm(lq, axis=-1), 1e-6)[:, None]
                geo = (np.sum(lv * lv, -1) + r0 * r0) / dq2 * np.maximum(wi @ n, 0.0)
                dist = np.sqrt(dq2)
            else:
                dist = np.linalg.norm(lv, axis=-1)
                wi = lv / np.maximum(dist, 1e-6)[:, None]
                geo = np.ones(N)
                if typ == 1:
                    c = wi @ L1[:3]
                    e0, e1 = L3[0], L3[1]
                    x = np.clip((c - e0) / (e1 - e0), 0.0, 1.0)
                    geo = x * x * (3.0 - 2.0 * x)
            win = np.ones(N) if rng <= 0.0 else np.clip(1.0 - (dist / rng) ** 4, 0.0, 1.0) ** 2
            acc += sg * T * hg(-np.sum(wi * d, -1), g) * geo * win * wk
        nrm = 1.0 / (steps * (1.0 + 0.5 / (steps * steps)))   # sum of the midpoint weights = N (1 + 1 / 2N^2)
        out += col * (np.where(ok, (thb - tha) / hs * acc * nrm, 0.0))[:, None]
    return out, S, TE


def light_screen(U, L, i, asp=None, zl=None):
    """(uv (2,), dist, ok) of light i on screen (mirrors pxhScreen); zl (a 1-list) receives its view z."""
    np = _np()
    zl = zl if zl is not None else [0.0]
    L0, L1 = L[i * HZ_LROWS], L[i * HZ_LROWS + 1]
    pos = np.array(U[0][:3], float)
    r, u, f = (np.array(U[k][:3], float) for k in (1, 2, 3))
    if int(L0[3]) == 3:
        v = -np.array(L1[:3], float)
        dist = 1e30
        zmin = 1e-6
    else:
        v = np.array(L0[:3], float) - pos
        dist = float(np.linalg.norm(v))
        zmin = U[2][3]
    z = float(v @ f)
    zl[0] = z
    if z <= zmin:
        return None, dist, False
    asp = asp or U[1][3]
    sx = float(v @ r) / (z * U[0][3])
    sy = float(v @ u) / (z * U[0][3] / asp)
    return np.array([0.5 + 0.5 * sx, 0.5 + 0.5 * sy]), dist, True


def tex_bilinear(img, uv):
    """GL texture() with linear filter + clamp to edge: img (h, w, c), uv (..., 2) -> (..., c)."""
    np = _np()
    h, w = img.shape[:2]
    x = uv[..., 0] * w - 0.5
    y = uv[..., 1] * h - 0.5
    x0 = np.floor(x)
    y0 = np.floor(y)
    fx = (x - x0)[..., None]
    fy = (y - y0)[..., None]
    x0 = x0.astype(int)
    y0 = y0.astype(int)

    def at(yy, xx):
        return img[np.clip(yy, 0, h - 1), np.clip(xx, 0, w - 1)]
    a = at(y0, x0) * (1 - fx) + at(y0, x0 + 1) * fx
    b = at(y0 + 1, x0) * (1 - fx) + at(y0 + 1, x0 + 1) * fx
    return a * (1 - fy) + b * fy


def _luma(c):
    return c[..., 0] * 0.2126 + c[..., 1] * 0.7152 + c[..., 2] * 0.0722


def shafts(U, L, nl, scene, w, h, depth=None, jit=None, cols=None):
    """Screen-space light shafts at the haze resolution (mirrors pxhShafts): (h, w, 3) before tint / gain. Reads
    `scene` / `depth` at mip 0: compare with the GPU at shaftlod 0 (the GPU reads mip uH[12].z)."""
    np = _np()
    amt, dec, ln, taps = U[9][0], U[9][1], U[9][2], int(U[9][3])
    thr, disc, occs = U[10][0], U[10][1], U[10][2]
    asp = w / float(h)
    out = np.zeros((h, w, 3))
    if amt <= 0.0:
        return out
    x = (np.arange(w) + 0.5) / w
    y = (np.arange(h) + 0.5) / h
    X, Y = np.meshgrid(x, y)
    uv = np.stack([X, Y], -1)
    j = np.zeros((h, w)) if jit is None else jit
    dmode = int(U[11][0])
    use_depth = depth is not None and dmode > 0
    for i in range(nl):
        L2 = L[i * HZ_LROWS + 2]
        if L2[3] <= 0.0:
            continue
        zl = [0.0]
        suv, ldist, ok = light_screen(U, L, i, asp, zl)
        if not ok:
            continue
        lz = -1.0                                   # depth threshold in the depth input's units (pxhShafts)
        if use_depth and int(L[i * HZ_LROWS][3]) != 3:
            if dmode == 1:
                lz = zl[0] / max(U[11][1], 1e-9)
            elif dmode == 2:
                nr, fr = U[2][3], U[3][3]
                lz = 0.5 + 0.5 * (fr + nr - 2.0 * fr * nr / zl[0]) / (fr - nr)
            else:
                lz = ldist / max(U[11][1], 1e-9)
        delta = (uv - suv) * (ln / taps)
        acc = np.zeros((h, w))
        dcy = 1.0
        for k in range(taps):
            c = uv - delta * (k + 1 + j)[..., None]
            inside = (c[..., 0] >= 0) & (c[..., 0] <= 1) & (c[..., 1] >= 0) & (c[..., 1] <= 1)
            s = tex_bilinear(scene, c)
            occ = np.where(inside, s[..., 3] * occs, 0.0)
            if lz > 0.0:
                dd = tex_bilinear(depth[..., None], c)[..., 0]
                occ = np.where(inside & (dd > 0.0) & (dd < lz), 1.0, occ)
            q = (c - suv) * np.array([asp, 1.0])
            src = np.exp(-np.sum(q * q, -1) / (disc * disc))
            if thr > 0.0:
                src = src + np.where(inside, np.maximum(_luma(s) - thr, 0.0), 0.0)
            acc += (1.0 - np.clip(occ, 0.0, 1.0)) * src * dcy
            dcy *= dec
        col = np.array(cols[i] if cols is not None else [c * L[i * HZ_LROWS + 4][0] for c in L2[:3]], float)
        out += col * (acc * (L2[3] * amt / taps))[..., None]
    return out


def ign(w, h, frame=0.0):
    """Interleaved gradient noise per pixel (h, w) (Jimenez 2014; the shaft tap offset, frame 0 when Jitter is off)."""
    np = _np()
    X, Y = np.meshgrid(np.arange(w, dtype=float), np.arange(h, dtype=float))
    o = 5.588238 * (frame % 64.0)
    return _fract(52.9829189 * _fract((X + o) * 0.06711056 + (Y + o) * 0.00583715))


def ref_haze(U, L, nl, scene, w, h, depth=None, time=0.0, cs=None, pal_rows=None, pal_ctl=None):
    """Whole haze pass at (w, h): returns (h, w, 4): rgb = ambient + tint x gain x (in-scatter + shafts),
    a = 1 - T. scene (H, W, 4) premultiplied (any res), depth (H, W) or None (mirrors main() of px_haze.glsl)."""
    np = _np()
    d = ray_dirs(U, w, h)
    x = (np.arange(w) + 0.5) / w
    y = (np.arange(h) + 0.5) / h
    X, Y = np.meshgrid(x, y)
    uv = np.stack([X, Y], -1)
    al = tex_bilinear(scene, uv)[..., 3]
    dep = tex_bilinear(depth[..., None], uv)[..., 0] if depth is not None else None
    te = ray_end(U, d, al, dep)
    cols = light_cols(U, L, nl, cs, pal_rows, pal_ctl)
    ins, S, TE = inscatter(U[0][:3], d.reshape(-1, 3), te.reshape(-1), U, L, nl, time, cols=cols)
    ins = ins.reshape(h, w, 3)
    S = S.reshape(h, w)
    TE = TE.reshape(h, w)
    tint = np.array(U[7][:3]) * U[7][3]
    jit = ign(w, h)
    csv = list(cs) if cs is not None else [3.0, 0.0, 1.0, 0.0]
    if int(csv[0] + 0.5) in (0, 3):              # solid / source: Hazecol everywhere
        amb = np.broadcast_to(np.array(colsrc(csv, U[4][:3], U[4][:3], 0.0), float), (h, w, 3))
    else:                                        # palette modes: attrT = march end / maxdist (colour by distance)
        tn = te / U[11][3]
        amb = np.array([[colsrc(csv, U[4][:3], U[4][:3], float(tn[y, x]), pal_rows, pal_ctl) for x in range(w)]
                        for y in range(h)], float)
    rgb = amb * (U[8][1] * S)[..., None] + tint * (ins + shafts(U, L, nl, scene, w, h, depth, jit=jit, cols=cols))
    return np.concatenate([rgb, (1.0 - TE)[..., None]], -1)


def ref_composite(src, haze, amount=1.0, alpha_mode=1.0):
    """px_haze_comp.glsl: src (H, W, 4) premultiplied, haze (h, w, 4) any res (bilinear up)."""
    np = _np()
    if amount <= 0.0:
        return src.copy()
    H, W = src.shape[:2]
    x = (np.arange(W) + 0.5) / W
    y = (np.arange(H) + 0.5) / H
    X, Y = np.meshgrid(x, y)
    hz = tex_bilinear(haze, np.stack([X, Y], -1)) * amount
    out = src.copy()
    out[..., :3] = src[..., :3] * (1.0 - hz[..., 3:4]) + hz[..., :3]
    if alpha_mode > 0.5:
        out[..., 3] = src[..., 3] * (1.0 - hz[..., 3]) + hz[..., 3]
    return out


def airlight_point(o, d, te, P, I, D, r0):
    """Closed form: single scattering of a point light in a homogeneous medium without extinction, isotropic phase
    (normalised to 1): D I integral_0^te dt / (|o + d t - P|^2 + r0^2) = D I (atan((te - dl)/h) - atan(-dl/h)) / h."""
    rel = [P[k] - o[k] for k in range(3)]
    dl = _dot(rel, d)
    perp = [rel[k] - d[k] * dl for k in range(3)]
    h = math.sqrt(_dot(perp, perp) + r0 * r0)
    return D * I * (math.atan((te - dl) / h) - math.atan(-dl / h)) / h


# ---- bloom references


def ref_glow_legacy(src8, out_wh, thr, inten, spacing):
    """px_glow.glsl as it is (7x7 gaussian of per-channel excess at 1/8, x intensity, alpha 0)."""
    np = _np()
    w, h = out_wh
    ih, iw = src8.shape[:2]
    x = (np.arange(w) + 0.5) / w
    y = (np.arange(h) + 0.5) / h
    X, Y = np.meshgrid(x, y)
    uv = np.stack([X, Y], -1)
    stp = np.array([max(spacing, 0.0) / iw, max(spacing, 0.0) / ih])
    s = np.zeros((h, w, 3))
    ws = 0.0
    for j in range(-3, 4):
        for i in range(-3, 4):
            wk = math.exp(-float(i * i + j * j) / 4.5)
            c = tex_bilinear(src8, uv + np.array([i, j], float) * stp)[..., :3]
            s += np.maximum(c - thr, 0.0) * wk
            ws += wk
    o = s / max(ws, 1e-6) * inten
    return np.concatenate([o, np.zeros((h, w, 1))], -1)


def _knee(c, thr, kn):
    np = _np()
    br = np.max(c[..., :3], -1)
    rq = np.clip(br - thr + kn, 0.0, 2.0 * kn)
    rq = rq * rq / (4.0 * kn + 1e-5)
    return c * (np.maximum(rq, br - thr) / np.maximum(br, 1e-5))[..., None]


def _excess(c, B, B2):
    np = _np()
    e = _knee(c, B[0], B[3]) if B[3] > 0.0 else np.maximum(c - B[0], 0.0)
    if B2[3] > 0.0:                                   # firefly clamp: excess luma <= clamp (lone hot splats)
        l = _luma(e)
        e = e * (np.minimum(l, B2[3]) / np.maximum(l, 1e-6))[..., None]
    return e


def _blur7(src, uv, stp, B, B2):
    np = _np()
    s = 0.0
    ws = 0.0
    for j in range(-3, 4):
        for i in range(-3, 4):
            wk = math.exp(-float(i * i + j * j) / 4.5)
            c = tex_bilinear(src, uv + np.array([i, j], float) * stp)[..., :3]
            s = s + _excess(c, B, B2) * wk
            ws += wk
    return s / max(ws, 1e-6)


def ref_bloom(src8, src4, out_wh, rows, ring_taps=16, pal_rows=None, pal_ctl=None):
    """px_bloom.glsl: wide 7x7 on input 0 (1/8), tight 7x7 on input 1 (1/4), ring halo, tint + saturation."""
    np = _np()
    B, B2, Bt, Br = rows['uB'], rows['uB2'], rows['uBt'], rows['uBr']
    w, h = out_wh
    x = (np.arange(w) + 0.5) / w
    y = (np.arange(h) + 0.5) / h
    X, Y = np.meshgrid(x, y)
    uv = np.stack([X, Y], -1)
    i8 = np.array([src8.shape[1], src8.shape[0]], float)
    i4 = np.array([src4.shape[1], src4.shape[0]], float)
    o = np.zeros((h, w, 3))
    if B2[0] > 0.0:
        o = o + _blur7(src8, uv, max(B[2], 0.0) / i8, B, B2) * B2[0]
    if B2[1] > 0.0:
        o = o + _blur7(src4, uv, max(B2[2], 0.0) / i4, B, B2) * B2[1]
    o = o * B[1]
    if Br[0] > 0.0:
        asp = w / float(h)
        r = np.zeros((h, w, 3))
        jr = ign(w, h)[..., None]
        for k in range(ring_taps):
            a = 6.283185307179586 * (k + jr) / ring_taps
            dv = np.concatenate([np.cos(a) / asp, np.sin(a)], -1)
            for ch, sc in enumerate((1.0 - Br[3], 1.0, 1.0 + Br[3])):
                cu = uv + dv * (Br[1] * sc)
                c = (tex_bilinear(src4, cu) * (1.0 - Br[2]) + tex_bilinear(src8, cu) * Br[2])[..., :3]
                r[..., ch] += _excess(c, B, B2)[..., ch]
        o = o + r * (Br[0] / ring_taps)
    tint = colsrc(rows.get('uGlowCs', [0.0, 0.0, 1.0, 0.0]), Bt[:3], [1.0, 1.0, 1.0], 0.0, pal_rows, pal_ctl)
    o = o * np.array(tint)
    if Bt[3] != 1.0:
        l = _luma(o)[..., None]
        o = np.maximum(l + (o - l) * Bt[3], 0.0)
    return np.concatenate([o, np.zeros((h, w, 1))], -1)
