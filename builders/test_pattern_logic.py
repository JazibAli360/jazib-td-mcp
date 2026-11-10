"""test_pattern logic: pure Python (no td), copied into TP_test_pattern/tp_logic as a Text DAT module.

Spec: docs/research/BB_test_patterns_sync.md section 5 (our own clean-room design). Pattern names follow
stagelab/guides/JZB_Slice_Test.md (Cabinets, Slices, Solid, Bars, Ramp, Checker, Crosshatch, Walk) plus Circles,
Gradient and Pixel check. Everything exact: a lit pixel = exactly the Level code on the Channel's components, whole-pixel
lines, deterministic (no seed); only text is anti-aliased.

Coordinates: composition pixels, origin TOP-LEFT (x right, y down). The face table is in LED px; composition px =
LED px * Resx / Nativewidth (Nativewidth 0 = 1:1). `pixel()` is the reference the GLSL shader mirrors (tests + live
checks compare the two). Pure ASCII.
"""
import math

PATTERNS = (('cabinets', 'Cabinets'), ('slices', 'Slices'), ('solid', 'Solid'), ('bars', 'Bars'), ('ramp', 'Ramp'),
            ('checker', 'Checker'), ('crosshatch', 'Crosshatch'), ('walk', 'Walk'), ('circles', 'Circles'),
            ('gradient', 'Gradient'), ('pixelcheck', 'Pixel check'))
CHANNELS = (('white', 'White'), ('red', 'Red'), ('green', 'Green'), ('blue', 'Blue'), ('cyan', 'Cyan'),
            ('magenta', 'Magenta'), ('yellow', 'Yellow'), ('black', 'Black'))
CHANNEL_RGB = {'white': (1, 1, 1), 'red': (1, 0, 0), 'green': (0, 1, 0), 'blue': (0, 0, 1), 'cyan': (0, 1, 1),
               'magenta': (1, 0, 1), 'yellow': (1, 1, 0), 'black': (0, 0, 0)}
AREAS = (('slices', 'Slices (per face)'), ('canvas', 'Canvas (whole frame)'))
WALKS = (('across', 'Line Across'), ('down', 'Line Down'), ('diagonal', 'Diagonal'), ('dot', 'Dot'),
         ('cabinet', 'Cabinet'))
# Bars: white, yellow, cyan, green, magenta, red, blue, black (JZB order), all at Level
BARS = ((1, 1, 1), (1, 1, 0), (0, 1, 1), (0, 1, 0), (1, 0, 1), (1, 0, 0), (0, 0, 1), (0, 0, 0))
WHEEL_RATES = (24, 30, 48, 60, 120)          # fixed rings, inner -> outer; outermost ring = project frames (dynamic)
RES_PRESETS = (('custom', 'Custom'), ('1920x1080', '1920x1080 HD'), ('1080x1920', '1080x1920 portrait'),
               ('3840x2160', '3840x2160 UHD'), ('7488x2880', '7488x2880'), ('9984x3840', '9984x3840'))
MAX_FACES = 16
FACE_HEADER = ['name', 'x', 'y', 'w', 'h']
DEFAULT_FACES = [FACE_HEADER, ['Wall', '0', '0', '1920', '1080']]
COUNTER_BITS = 24


def names(menu):
    return [n for n, _ in menu]


def labels(menu):
    return [lb for _, lb in menu]


def menu_index(menu, name, default=0):
    for k, (n, _label) in enumerate(menu):
        if n == name:
            return k
    return default


def rnd(v):
    """Round half up (same as GLSL floor(v + 0.5))."""
    return int(math.floor(v + 0.5))


def preset_res(name):
    if 'x' not in name:
        return None
    a, b = name.split('x')
    return int(a), int(b)


# ------------------------------------------------------------------ faces

def parse_faces(rows):
    """rows: list of lists of str (a Table DAT). Header row optional. Returns [{name, x, y, w, h}] in LED px;
    rows with a non-number or w/h <= 0 are skipped; at most MAX_FACES."""
    out = []
    for r in rows:
        if not r or (r[0].strip().lower() == 'name'):
            continue
        cells = list(r) + [''] * (5 - len(r))
        try:
            x, y, w, h = (float(cells[k]) for k in (1, 2, 3, 4))
        except ValueError:
            continue
        if w <= 0 or h <= 0:
            continue
        out.append({'name': cells[0].strip() or 'Face%d' % (len(out) + 1), 'x': x, 'y': y, 'w': w, 'h': h})
        if len(out) >= MAX_FACES:
            break
    return out


def scale(resx, nativewidth):
    """Composition px per LED px."""
    return float(resx) / float(nativewidth) if nativewidth and nativewidth > 0 else 1.0


def face_rects(faces, resx, resy, nativewidth):
    """Faces -> integer composition rects (x, y, w, h), top-left origin, clipped to the frame; empty ones dropped
    (the face keeps its index in the returned list as None so labels and rects stay paired)."""
    s = scale(resx, nativewidth)
    out = []
    for f in faces:
        x0, y0 = rnd(f['x'] * s), rnd(f['y'] * s)
        x1, y1 = rnd((f['x'] + f['w']) * s), rnd((f['y'] + f['h']) * s)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(int(resx), x1), min(int(resy), y1)
        out.append((x0, y0, x1 - x0, y1 - y0) if x1 > x0 and y1 > y0 else None)
    return out


def areas(rects, area, resx, resy):
    if area == 'canvas' or not any(rects):
        return [(0, 0, int(resx), int(resy))]
    return [r for r in rects if r]


# ------------------------------------------------------------------ grid maths (mirrored in GLSL)

def cell_index(l, c):
    """Which cell (size c comp px, may be fractional) holds integer pixel l: k with round(k*c) <= l < round((k+1)*c)."""
    return int(math.ceil((l + 0.5) / c)) - 1


def cell_bound(k, c):
    return int(math.floor(k * c + 0.5))


def cell_size(cell, cab, s):
    """Cell (LED px, 0 = one cabinet) in comp px."""
    return float(cell) * s if cell and cell > 0 else cab * s


def count_cells(n, c):
    return cell_index(n - 1, c) + 1 if n > 0 else 0


def fmt_num(v):
    return str(int(v)) if abs(v - round(v)) < 1e-6 else '%.1f' % v


# ------------------------------------------------------------------ labels (Text TOP spec rows, bottom-left origin)

def cabinet_font(cw, ch):
    return max(6, int(min(cw, ch) * 0.26))


def cabinet_labels(area_list, cw, ch, resy, min_px=20):
    """`column-row` (1-based, from each area's top-left) at the centre of every cabinet. Rows: (x, y_from_bottom, text).
    Empty when cabinets are smaller than min_px (text would not fit)."""
    rows = []
    if min(cw, ch) < min_px:
        return rows
    for (ax, ay, aw, ah) in area_list:
        nx, ny = count_cells(aw, cw), count_cells(ah, ch)
        for j in range(ny):
            y0, y1 = cell_bound(j, ch), min(cell_bound(j + 1, ch), ah)
            for i in range(nx):
                x0, x1 = cell_bound(i, cw), min(cell_bound(i + 1, cw), aw)
                cx, cy = ax + (x0 + x1) / 2.0, ay + (y0 + y1) / 2.0
                rows.append((round(cx, 2), round(resy - cy, 2), '%d-%d' % (i + 1, j + 1)))
    return rows


def centre_rows(rows, size, measure=None):
    """Text TOP spec rows are drawn from their x (left) and baseline y on 31550 whatever alignx/aligny say (probed):
    shift centre points by half the text width (measure(text) -> px; default estimate 0.55 * size per char) and half
    the cap height (0.36 * size), so labels sit centred."""
    m = measure or (lambda t: 0.55 * size * len(t))
    return [(round(x - m(t) / 2.0, 2), round(y - 0.36 * size, 2), t) for (x, y, t) in rows]


def slice_font(rects):
    r = [x for x in rects if x]
    if not r:
        return 12
    return max(10, int(min(min(w, h) for (_x, _y, w, h) in r) / 12))


def slice_labels(faces, rects, cabw, cabh, resy, size):
    """Per face: name, LED size `WxH`, cabinets `6x30 cab`, three centred lines."""
    rows = []
    for f, r in zip(faces, rects):
        if not r:
            continue
        x, y, w, h = r
        cx, cy = x + w / 2.0, y + h / 2.0
        lines = [f['name'], '%sx%s' % (fmt_num(f['w']), fmt_num(f['h'])),
                 '%sx%s cab' % (fmt_num(f['w'] / float(cabw)), fmt_num(f['h'] / float(cabh)))]
        for k, t in enumerate(lines):
            rows.append((round(cx, 2), round(resy - (cy + (k - 1) * size * 1.4), 2), t))
    return rows


# ------------------------------------------------------------------ clock / sync

def fps_int(fps):
    return max(1, int(round(float(fps))))


def timecode(frame, fps):
    f = fps_int(fps)
    frame = int(frame)
    ff = frame % f
    s = frame // f
    return '%02d:%02d:%02d:%02d' % (s // 3600, (s // 60) % 60, s % 60, ff)


def counter_text(frame, fps):
    return 'F %07d  %s  %s fps' % (int(frame), timecode(frame, fps), fmt_num(float(fps)))


def frame_bits(frame, n=COUNTER_BITS):
    """MSB first."""
    frame = int(frame)
    return [(frame >> (n - 1 - k)) & 1 for k in range(n)]


def decode_bits(bits):
    v = 0
    for b in bits:
        v = (v << 1) | (1 if b else 0)
    return v


def counter_layout(size):
    """Counter box: text line (size px font) above a strip of start + 24 bits + end cells (cell = size px).
    Returns (text_w, text_h, box_w, box_h, pad)."""
    size = max(4, int(size))
    pad = max(2, size // 2)
    tw, th = int(size * 20), int(size * 1.5)
    bw = max(tw, (COUNTER_BITS + 2) * size) + 2 * pad
    bh = th + size + 3 * pad
    return tw, th, bw, bh, pad


def flash_now(frame, every, on=True):
    every = max(1, int(every))
    return bool(on) and int(frame) % every == 0


def blip_gate(frame, every, length, on):
    """Audio blip on while frame % every < length (starts on the flash frame)."""
    every = max(1, int(every))
    return 1.0 if on and (int(frame) % every) < max(0, int(length)) else 0.0


def wheel_segment(t_seconds, rate, n=None):
    """Lit segment of a fixed-rate ring: one segment per 1/rate s, n = rate segments (one turn per second)."""
    n = n or int(rate)
    return int(math.floor(t_seconds * rate + 1e-6)) % n


def walk_span(walk, aw, ah, lw, cw, ch):
    """Steps in one pass of the walk over one area."""
    lw = max(1, int(lw))
    if walk == 'across':
        return int(math.ceil(aw / float(lw)))
    if walk == 'down':
        return int(math.ceil(ah / float(lw)))
    if walk == 'diagonal':
        return int(math.ceil((aw + ah) / float(lw)))
    if walk == 'dot':
        return int(math.ceil(math.ceil(cw) / float(lw))) * int(math.ceil(math.ceil(ch) / float(lw)))
    return count_cells(aw, cw) * count_cells(ah, ch)


# ------------------------------------------------------------------ uniforms

def uniforms(p, rects):
    """p: dict of the COMP's pars (+ frame, step, seconds). Returns [(name, [x, y, z, w])] for the GLSL TOP."""
    W, H = int(p['resx']), int(p['resy'])
    s = scale(W, p.get('nativewidth', 0))
    cw, ch = p['cabw'] * s, p['cabh'] * s
    cellw, cellh = cell_size(p.get('cell', 0), p['cabw'], s), cell_size(p.get('cell', 0), p['cabh'], s)
    lw = max(1, int(round(p.get('linewidth', 2))))
    rgb = CHANNEL_RGB.get(p.get('channel', 'white'), (1, 1, 1))
    level = max(0, min(255, int(round(p.get('level', 255)))))
    nf = len([r for r in rects if r])
    frame = int(p.get('frame', 0))
    fps = fps_int(p.get('fps', 60))
    size = int(p.get('countersize', 24))
    tw, th, bw, bh, pad = counter_layout(size)
    wr = float(p.get('wheelsize', 360)) / 2.0
    return [
        ('uRes', [W, H, nf, 1 if p.get('area') == 'canvas' or nf == 0 else 0]),
        ('uPat', [menu_index(PATTERNS, p.get('pattern', 'cabinets')), menu_index(WALKS, p.get('walk', 'across')),
                  int(p.get('step', 0)), lw]),
        ('uLit', [rgb[0], rgb[1], rgb[2], level / 255.0]),
        ('uCab', [cw, ch, cellw, cellh]),
        ('uOpt', [max(2, int(p.get('steps', 16))), 1 if p.get('showfaces') else 0,
                  1 if flash_now(frame, p.get('flashevery', 60), p.get('flash')) else 0, max(1, rnd(cw))]),
        ('uWheel', [1 if p.get('wheel') else 0, float(p.get('wheelu', 0.5)) * W, float(p.get('wheelv', 0.5)) * H, wr]),
        ('uClock', [frame, fps, float(p.get('seconds', 0.0)), 1 if p.get('counter') else 0]),
        ('uCnt', [int(p.get('counterx', 16)), int(p.get('countery', 16)), bw, bh]),
        ('uCnt2', [max(4, size), pad, tw, th]),
    ]


def needs_clock(p):
    return bool(p.get('counter') or p.get('wheel') or p.get('flash') or p.get('blip') or p.get('pattern') == 'walk')


# ------------------------------------------------------------------ reference pixel (the shader mirrors this)

def _area_of(ix, iy, rects, canvas, W, H):
    if canvas:
        return (0, 0, W, H)
    for r in rects:
        if r and r[0] <= ix < r[0] + r[2] and r[1] <= iy < r[1] + r[3]:
            return r
    return None


def _pattern(pat, lx, ly, aw, ah, U, face):
    """Lit amount (1/0) or an explicit colour tuple for one area-local pixel. face = (w, h) for slices geometry."""
    cw, ch, cellw, cellh = U['uCab']
    walk, step, lw = int(U['uPat'][1]), int(U['uPat'][2]), int(U['uPat'][3])
    if pat == 'solid':
        return 1
    if pat == 'cabinets':
        kx, ky = cell_index(lx, cw), cell_index(ly, ch)
        x0, x1 = cell_bound(kx, cw), min(cell_bound(kx + 1, cw), aw)
        y0, y1 = cell_bound(ky, ch), min(cell_bound(ky + 1, ch), ah)
        fx, fy = lx - x0, ly - y0
        return 1 if (fx < lw or fx >= (x1 - x0) - lw or fy < lw or fy >= (y1 - y0) - lw) else 0
    if pat == 'slices':
        w, h = face
        if lx < lw or lx >= w - lw or ly < lw or ly >= h - lw:
            return 1
        px, py = lx + 0.5, ly + 0.5
        n = math.sqrt(float(w) * w + float(h) * h)
        d1 = abs(px * h - py * w) / n
        d2 = abs((w - px) * h - py * w) / n
        return 1 if (d1 < lw / 2.0 or d2 < lw / 2.0) else 0
    if pat == 'bars':
        return BARS[min(7, (lx * 8) // aw)]
    if pat == 'ramp':
        steps = int(U['uOpt'][0])
        t = (lx / float(aw)) if aw >= ah else (ly / float(ah))
        k = min(steps - 1, int(math.floor(t * steps)))
        return ('code', rnd(k * (U['uLit'][3] * 255.0) / (steps - 1)))
    if pat == 'gradient':
        t = (lx / float(max(1, aw - 1))) if aw >= ah else (ly / float(max(1, ah - 1)))
        return ('float', t)
    if pat == 'checker':
        return 1 if (cell_index(lx, cellw) + cell_index(ly, cellh)) % 2 == 0 else 0
    if pat == 'crosshatch':
        if lx < lw or lx >= aw - lw or ly < lw or ly >= ah - lw:
            return 1
        ux, uy = lx - aw // 2, ly - ah // 2
        mx = ux - cellw * math.floor(ux / cellw)
        my = uy - cellh * math.floor(uy / cellh)
        return 1 if (mx < lw or my < lw) else 0
    if pat == 'circles':
        if lx < lw or lx >= aw - lw or ly < lw or ly >= ah - lw:
            return 1
        dx, dy = lx + 0.5 - aw / 2.0, ly + 0.5 - ah / 2.0
        d = math.sqrt(dx * dx + dy * dy)
        R = min(aw, ah) / 2.0 - lw / 2.0
        if abs(d - R) < lw / 2.0:
            return 1
        return 1 if (d - cellw * math.floor(d / cellw)) < lw else 0
    if pat == 'pixelcheck':
        if ly < ah // 2:
            return 1 if (lx + ly) % 2 == 0 else 0
        if lx < aw // 2:
            return 1 if lx % lw == 0 else 0
        return 1 if ly % lw == 0 else 0
    if pat == 'walk':
        wk = names(WALKS)[walk]
        span = walk_span(wk, aw, ah, lw, cw, ch)
        k = step % max(1, span)
        if wk == 'across':
            return 1 if lx // lw == k else 0
        if wk == 'down':
            return 1 if ly // lw == k else 0
        if wk == 'diagonal':
            return 1 if (lx + ly) // lw == k else 0
        kx, ky = cell_index(lx, cw), cell_index(ly, ch)
        if wk == 'dot':
            nx = int(math.ceil(math.ceil(cw) / float(lw)))
            fx, fy = lx - cell_bound(kx, cw), ly - cell_bound(ky, ch)
            dx, dy = (k % nx) * lw, (k // nx) * lw
            return 1 if (dx <= fx < dx + lw and dy <= fy < dy + lw) else 0
        ncx = count_cells(aw, cw)
        return 1 if (kx == k % ncx and ky == k // ncx) else 0
    return 0


def pixel(ix, iy, U, rects):
    """Reference value of composition pixel (ix, iy) (top-left origin) WITHOUT text, wheel, counter, flash.
    Returns (r, g, b, a) as 8-bit codes (gradient: floats 0..1)."""
    W, H = int(U['uRes'][0]), int(U['uRes'][1])
    canvas = U['uRes'][3] > 0.5
    pat = names(PATTERNS)[int(U['uPat'][0])]
    if pat == 'slices':
        canvas = False
        if not any(rects):
            canvas = True
    a = _area_of(ix, iy, rects, canvas, W, H)
    if a is None:
        return (0, 0, 0, 0)
    ax, ay, aw, ah = a
    v = _pattern(pat, ix - ax, iy - ay, aw, ah, U, (aw, ah))
    level = U['uLit'][3] * 255.0
    rgb = U['uLit'][:3]
    if isinstance(v, tuple) and v and v[0] == 'code':
        c = [rnd(v[1] * m) for m in rgb]
    elif isinstance(v, tuple) and v and v[0] == 'float':
        return tuple([v[1] * m * U['uLit'][3] for m in rgb] + [1.0])
    elif isinstance(v, tuple):
        c = [rnd(level * m) for m in v]
    else:
        c = [rnd(level * m * v) for m in rgb]
    if U['uOpt'][1] > 0.5:                                   # Showfaces: face outlines, XOR over the pattern
        lw = int(U['uPat'][3])
        for r in rects:
            if r and r[0] <= ix < r[0] + r[2] and r[1] <= iy < r[1] + r[3]:
                lx, ly = ix - r[0], iy - r[1]
                if lx < lw or lx >= r[2] - lw or ly < lw or ly >= r[3] - lw:
                    lit = any(c)
                    c = [0, 0, 0] if lit else [rnd(level * m) for m in rgb]
                break
    return (c[0], c[1], c[2], 255)
