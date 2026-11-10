# fx_film_gate_logic - pure maths of FX_film module 'gate' (FX3 F8 gate / format overlays, L7 physical vignette,
# L12 vintage-lens character; FX0 row 79). Mirrors builders/fx_film_gate.py; checked by test/test_fx_film_wavec.py.
# ASCII only.
import math

ASPECTS = ['off', 'a239', 'a200', 'a185', 'a166', 'a143', 'a133', 'a100', 'custom']
ASPECT_VALUES = [0.0, 2.39, 2.0, 1.85, 1.66, 1.43, 4.0 / 3.0, 1.0, -1.0]
ASPECT_LABELS = ['Off (full frame)', '2.39 scope', '2.00 univisium', '1.85 flat', '1.66 Euro', '1.43 IMAX',
                 '4:3 academy', '1:1 square', 'Custom']
SPROCKETS = ['off', 'p4', 'p2', 'super8', 'mm16']
HOLES = {'off': 0, 'p4': 4, 'p2': 2, 'super8': 1, 'mm16': 1}


def aspect_value(name, custom):
    v = ASPECT_VALUES[ASPECTS.index(name)]
    return custom if v < 0 else v


def aperture(w, h, aspect, rotate=False):
    """Half size (px) of the gate aperture centred in a w x h canvas. aspect 0 = the canvas itself."""
    a = aspect if aspect > 0 else w / float(h)
    if rotate:
        a = 1.0 / a
    if w / float(h) > a:
        return h * a / 2.0, h / 2.0
    return w / 2.0, w / a / 2.0


def rbox(px, py, cx, cy, hx, hy, r):
    """Signed distance to a rounded box (negative inside)."""
    r = min(r, hx, hy)
    dx, dy = abs(px - cx) - (hx - r), abs(py - cy) - (hy - r)
    return math.hypot(max(dx, 0.0), max(dy, 0.0)) + min(max(dx, dy), 0.0) - r


def gate_mask(sd, soft):
    if soft > 0:
        return min(max(0.5 - sd / soft, 0.0), 1.0)
    return 1.0 if sd <= 0 else 0.0


def picture_rows(w, h, aspect, rotate=False, soft=1.0):
    """Rows of the centre column whose gate mask is > 0.5 (mask mode)."""
    hx, hy = aperture(w, h, aspect, rotate)
    return sum(1 for y in range(h) if gate_mask(rbox(w / 2.0, y + 0.5, w / 2.0, h / 2.0, hx, hy, 0.0), soft) > 0.5)


def vignette(rn, k):
    """cos^4 law: 1 / (1 + (k rn)^2)^2 (= cos^4 of the field angle with tan = k rn)."""
    return 1.0 / (1.0 + (k * rn) ** 2) ** 2


def rnorm(sx, sy, w, h, oval=1.0):
    """Normalised field radius: 0 at the picture centre, 1 at the corner (oval scales x)."""
    qx, qy = (sx - w / 2.0) / (w / 2.0) * oval, (sy - h / 2.0) / (h / 2.0)
    return math.hypot(qx, qy) / math.sqrt(2.0)


def strip_cell(w, h, frames, frameline, sideband):
    """(cell height, aperture half size x, y) of the film-strip mode."""
    ch = h / float(max(frames, 1))
    return ch, w / 2.0 - sideband * w, ch / 2.0 - frameline / 2.0


def holes_per_cell(kind):
    return HOLES[kind]


def vogel(k, n):
    rho = math.sqrt((k + 0.5) / n)
    th = k * 2.39996323
    return rho * math.cos(th), rho * math.sin(th)


def expected_numbers():
    ex = {}
    ex['gate_rows_239'] = picture_rows(1080, 1920, 2.39)
    ex['gate_rows_185'] = picture_rows(1080, 1920, 1.85)
    ex['gate_cols_239_rot'] = int(round(2 * aperture(1080, 1920, 2.39, True)[0]))
    ex['gate_vig_corner_k1'] = round(vignette(1.0, 1.0), 4)
    ex['gate_vig_mid_k1'] = round(vignette(rnorm(540, 1440, 1080, 1920), 1.0), 4)
    ex['gate_strip_cell_3'] = [round(v, 2) for v in strip_cell(1080, 1920, 3, 14, 0.12)]
    return ex
