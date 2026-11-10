# fx_film_dof_logic - pure maths of FX_film module 'dof' (FX3 L10 depth of field + L11 bokeh shapes; FX0 row 36).
# Mirrors builders/fx_film_dof.py (depth sources, CoC, aperture shape mapping, gather coverage); checked by
# test/test_fx_film_wavec.py. ASCII only.
import math

SOURCES = ['auto', 'top', 'plane', 'radial', 'luma']
DC_DEPTH = '/project1/lab/DC_depth_cam/depth'     # DC_depth_cam's depth null (R = nearness, 1 near)


def fstop_k(fstop):
    """CoC gain per unit of depth outside the focus zone: f/1.4 reaches full Maxblur at 0.25 depth units."""
    return 4.0 * 1.4 / max(fstop, 0.1)


def coc_px(d, focus, rng, fstop, maxblur, nearscale=1.0):
    """Signed CoC in full-res px (negative = in front of the focus plane)."""
    s = d - focus
    dz = math.copysign(max(abs(s) - 0.5 * rng, 0.0), s)
    c = max(-1.0, min(1.0, dz * fstop_k(fstop))) * maxblur
    return c * nearscale if s < 0 else c


def plane_depth(u, v, angle_deg=0.0, tilt=1.0, cx=0.5, cy=0.5):
    a = math.radians(angle_deg)
    return 0.5 + tilt * ((u - cx) * math.sin(a) + (v - cy) * math.cos(a))


def radial_depth(u, v, w, h, tilt=1.0, cx=0.5, cy=0.5):
    return 0.5 + tilt * math.hypot((u - cx) * w / float(h), v - cy)


def map_depth(r, conv='nearness', near=0.0, far=1.0):
    d = 1.0 - r if conv == 'nearness' else r
    return (d - near) / max(far - near, 1e-6)


def poly_scale(theta, blades, rot):
    """Unit-disk sample at angle theta -> inside the regular polygon of circumradius 1 (blades sides)."""
    seg = 2.0 * math.pi / blades
    t = (theta - rot) % seg
    return math.cos(math.pi / blades) / math.cos(t - math.pi / blades)


def vogel(k, n):
    rho = math.sqrt((k + 0.5) / n)
    th = k * 2.39996323
    return rho * math.cos(th), rho * math.sin(th)


def gather_radius(acoc_texels, rmax_texels, nearreach):
    return max(acoc_texels, rmax_texels * nearreach)


def sprite_excess(col, cc, amt, thr, sc):
    """Share of a texel's colour moved into highlight sprites (GLSL spriteEx): only blurred texels (|CoC| 1.5-3
    texels fade in), per channel above thr."""
    x = min(max((abs(cc) / sc - 1.5) / 1.5, 0.0), 1.0)
    f = x * x * (3.0 - 2.0 * x)
    return [amt * f * max(c - thr, 0.0) for c in col]


def tile_size(rmax_texels):
    """Sprite tile edge T (coc texels): a power of two 4..32 with rmax <= 3.5 T, so a 9 x 9 tile loop reaches it."""
    return int(min(32, max(4, 2 ** math.ceil(math.log2(max(rmax_texels, 1e-3) / 3.5)))))


def aperture_area(blades, polygon=True, squeeze=1.0):
    """Area of the unit aperture (circumradius 1): polygon B / 2 sin(2 pi / B), disc pi."""
    return (0.5 * blades * math.sin(2.0 * math.pi / blades) if polygon else math.pi) * squeeze


def aperture_cov(ox, oy, rad, blades=6, rot=0.0, polygon=True):
    """Soft (1 texel) coverage of offset (ox, oy) / rad in the aperture (GLSL apert without swirl / squeeze / cat)."""
    pr = math.hypot(ox, oy)
    if polygon:
        seg = 2.0 * math.pi / blades
        pr *= math.cos((math.atan2(oy, ox) - rot) % seg - math.pi / blades) / math.cos(math.pi / blades)
    return min(max(0.5 - (pr - 1.0) * rad, 0.0), 1.0)


def expected_numbers():
    ex = {}
    # plane source, angle 0, tilt 1, focus 0.5, Range 0.05, f/2.8, Maxblur 24: CoC at full-res rows (pixel centre v)
    for y in (960, 1400, 1800, 200):
        v = (y + 0.5) / 1920.0
        ex['dof_coc_row_%d' % y] = round(coc_px(plane_depth(0.5, v), 0.5, 0.05, 2.8, 24.0), 3)
    ex['dof_poly_edge_6'] = round(poly_scale(math.pi / 6, 6, 0.0), 4)
    ex['dof_flat_coc_f14'] = round(coc_px(0.5, 0.0, 0.0, 1.4, 30.0), 3)
    ex['dof_sprite_tile_15'] = tile_size(15.0)          # Maxblur 30, Quality half
    ex['dof_aperture_area_6'] = round(aperture_area(6), 4)
    return ex
