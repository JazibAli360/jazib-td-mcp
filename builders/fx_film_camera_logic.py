# fx_film_camera_logic - pure maths of FX_film module 'camera' (FX3 C1 shutter / motion blur, C2 rolling shutter +
# flash banding, C3 exposure flicker + auto exposure, C4 ISO noise, C8 handheld moves). The GLSL in
# builders/fx_film_camera.py mirrors these; test/test_fx_film_wavec.py checks them offline and docs/builds/fx_film.md
# quotes expected_numbers(). Offline / live-check only (TD never needs this file). ASCII only.
import math
import os

try:
    import numpy as np
except ImportError:          # pragma: no cover
    np = None

HERE = '~/Documents/StageLab_PrismFest/jazib-td-mcp/builders'
_RL = {}


def rack_logic():
    """fx_film_logic (hash / fbm / sRGB) as a dict, loaded by path (TD has no sys.path entry for builders/)."""
    if not _RL:
        exec(open(os.path.join(HERE, 'fx_film_logic.py')).read(), _RL)
    return _RL


PATH_N = 257                 # shake path texels; texel 128 = exactly t0 (odd count, centre exact)
DIRECTIONS = ['topdown', 'bottomup', 'leftright', 'rightleft']


# ------------------------------------------------------------------ shutter / trail (C1)
def shutter_seconds(angle, fps):
    return angle / 360.0 / fps


def shutter_frames(angle, fps, rate=60.0):
    """Shutter open time in timeline frames (rate = TD cook rate)."""
    return angle / 360.0 * rate / fps


def trail_a(angle, fps, trail, rate=60.0):
    """Exponential trail factor with the same mean age as an S-frame box: a / (1 - a) = (S - 1) / 2."""
    s = shutter_frames(angle, fps, rate)
    if s <= 1.0 or trail <= 0:
        return 0.0
    return min(trail * (s - 1.0) / (s + 1.0), 0.995)


def trail_step(a, n):
    """Value n cooks after a 0 -> 1 step (state starts at 0)."""
    return 1.0 - a ** n


# ------------------------------------------------------------------ rolling shutter (C2)
def row_frac(x, y, w, h, direction):
    """0 = first row read, 1 = last; pixel (x, y), y = 0 bottom."""
    if direction == 'topdown':
        return 1.0 - (y + 0.5) / h
    if direction == 'bottomup':
        return (y + 0.5) / h
    if direction == 'leftright':
        return (x + 0.5) / w
    return 1.0 - (x + 0.5) / w


def row_time(rf, readout, fps):
    """Row time offset (s) from the frame centre: Readout = fraction of one camera frame for the full readout."""
    return (rf - 0.5) * readout / fps


def pan_shift(x, y, w, h, readout, fps, panx, direction='topdown'):
    """Row shift (px) of a pan velocity panx (px/s) under rolling readout: the jello / skew."""
    return panx * row_time(row_frac(x, y, w, h, direction), readout, fps)


def sinc(x):
    return 1.0 if abs(x) < 1e-9 else math.sin(x) / x


def flicker_gain(phase0, f_lamp, tr, depth, tsh):
    """Mains lamp flicker integrated over the exposure window T: 1 + depth sinc(pi f T) cos(2 pi (phase0 + f tr))."""
    return max(1.0 + depth * sinc(math.pi * f_lamp * tsh) * math.cos(2 * math.pi * (phase0 + f_lamp * tr)), 0.0)


def flash_cov(age_row, tsh, flen):
    """Share of the flash [0, flen] inside the row's exposure window [age - T/2, age + T/2] (age = s since flash)."""
    t = max(tsh, 1e-4)
    ov = max(0.0, min(age_row + 0.5 * t, flen) - max(age_row - 0.5 * t, 0.0))
    return ov / max(min(flen, t), 1e-6)


def flash_rows(h, readout, fps, tsh, flen, age, direction='topdown'):
    """Rows lit (cov > 0.5) for a flash age s at the frame centre."""
    return sum(1 for y in range(h)
               if flash_cov(age + row_time(row_frac(0, y, 1, h, direction), readout, fps), tsh, flen) > 0.5)


# ------------------------------------------------------------------ handheld path (C8) - mirrors the GLSL PATH pass
def footstep(f):
    """Zero-mean footfall bump on f = fract(phase)."""
    return math.exp(-7.0 * f) - (1.0 - math.exp(-7.0)) / 7.0


def path_at(dt, P):
    """(dx px, dy px, rot rad, log2 zoom) at dt s from t0. P: n0 freq oct seed shake rot zoomshake steps stepsroll
    ph0 rate wobble wph0 wfreq panx pany zoom (dict)."""
    R = rack_logic()
    na = P['n0'] + dt * P['freq']
    s, o = int(P['seed']), int(P['oct'])
    sx, sy, sr, sz = (2.0 * R['fbm'](na, yo, s, o) - 1.0 for yo in (0.5, 37.5, 71.5, 113.5))
    ph = P['ph0'] + dt * P['rate']
    f = ph - math.floor(ph)
    side = -1.0 if (math.floor(ph) % 2) < 0.5 else 1.0
    e = footstep(f)
    dx = P['shake'] * sx + P['wobble'] * math.sin(2 * math.pi * (P['wph0'] + dt * P['wfreq'])) + P['panx'] * dt
    dy = P['shake'] * sy - P['steps'] * e + P['pany'] * dt
    rot = math.radians(P['rot'] * sr + side * P['stepsroll'] * e)
    z = P['zoom'] + P['zoomshake'] * sz
    return dx, dy, rot, z


def src_point(px, py, T, pivot, overscan_log2=0.0):
    """Screen point (pixel centre coords) -> source point under camera transform T (dx, dy, rot, z)."""
    qx, qy = px - pivot[0] - T[0], py - pivot[1] - T[1]
    sc = 2.0 ** (-(T[3] + overscan_log2))
    c, s = math.cos(-T[2]), math.sin(-T[2])
    return pivot[0] + sc * (c * qx - s * qy), pivot[1] + sc * (s * qx + c * qy)


# ------------------------------------------------------------------ exposure + ISO (C3, C4)
def ae_target_ev(geomean, target, maxstops):
    return max(-maxstops, min(maxstops, math.log2(target / max(geomean, 1e-4))))


def ae_step(before, des, dt, attack, release):
    tau = attack if des < before else release
    return before + (des - before) * (1.0 - math.exp(-dt / max(tau, 1e-3)))


def iso_sigma(i, iso, shot, read):
    """Poisson-Gaussian sensor noise std at linear level i: sqrt(a i + b), a = shot ISO/100, b = (read ISO/100)^2."""
    k = iso / 100.0
    return math.sqrt(max(shot * k * max(i, 0.0) + (read * k) ** 2, 0.0))


def box_muller(x, y, s):
    """GLSL bm(ivec2(x, y), s): unit gaussian from two lowbias32 hashes."""
    R = rack_logic()
    u1 = max(R['hsh'](x, y, s & 0xffffffff), 1e-9)
    u2 = R['hsh'](x, y, (s * 7 + 13) & 0xffffffff)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2 * math.pi * u2)


def expected_numbers():
    ex = {}
    ex['cam_shutter_frames_180_24'] = round(shutter_frames(180, 24), 4)
    ex['cam_trail_a_360_24'] = round(trail_a(360, 24, 1.0), 4)
    ex['cam_trail_a_720_24'] = round(trail_a(720, 24, 1.0), 4)
    ex['cam_trail_step3_720'] = round(trail_step(trail_a(720, 24, 1.0), 3), 4)
    # rolling: Pan 600 px/s, Readout 1, Fps 24, top-down: shift (px) at the top / bottom rows and per row
    ex['cam_pan_top'] = round(pan_shift(0, 1919, 1080, 1920, 1.0, 24, 600.0), 3)
    ex['cam_pan_bottom'] = round(pan_shift(0, 0, 1080, 1920, 1.0, 24, 600.0), 3)
    # mains 50 Hz (lamp 100 Hz) on a 180 deg / 24 fps shutter: sinc factor; 1/100 s (360 deg at 100 fps) kills it
    ex['cam_flicker_sinc_180_24'] = round(sinc(math.pi * 100 * shutter_seconds(180, 24)), 4)
    ex['cam_flicker_sinc_1_100'] = round(abs(sinc(math.pi * 100 * 0.01)), 6)
    # flash band: Readout 1, Fps 24, Shutter 45 deg, flash 2 ms, age 0 at the frame centre -> rows lit
    ex['cam_flash_rows_45'] = flash_rows(1920, 1.0, 24, shutter_seconds(45, 24), 0.002, 0.0)
    ex['cam_iso_sigma_018_3200'] = round(iso_sigma(0.18, 3200, 0.0004, 0.002), 5)
    ex['cam_iso_sigma_05_800'] = round(iso_sigma(0.5, 800, 0.0004, 0.002), 5)
    ex['cam_ae_ev_009'] = round(ae_target_ev(0.09, 0.18, 4.0), 4)
    return ex
